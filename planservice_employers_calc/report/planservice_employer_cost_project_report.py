# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools
from odoo.tools import SQL


class PlanserviceEmployerCostProjectReport(models.Model):
    _name = "planservice.employer.cost.project.report"
    _description = "Planned and actual cost by project, employee and date"
    _auto = False
    _order = "project_id, employee_id, date"

    project_id = fields.Many2one("project.project", string="Job site", readonly=True)
    project_key = fields.Integer(
        string="Job site ID",
        readonly=True,
        help="Same value as Job site, as a number: allows exact filters in "
        "dashboards, which only offer 'contains' for project fields.",
    )
    employee_id = fields.Many2one("hr.employee", string="Team member", readonly=True)
    date = fields.Date(
        readonly=True,
        help="Actual: date of the timesheet entry. Planned: first day of each "
        "month of the task period.",
    )
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    unit_amount = fields.Float(string="Logged hours", readonly=True)
    planned_cost = fields.Monetary(string="Planned cost", readonly=True)
    real_cost = fields.Monetary(string="Actual cost", readonly=True)
    cost_deviation = fields.Monetary(string="Cost deviation", readonly=True)

    def _planned_start_expression(self):
        """Início da tarefa: planned_date_start (project_timeline) se existir."""
        self.env.cr.execute(
            """
            SELECT 1 FROM information_schema.columns
            WHERE table_name = 'project_task' AND column_name = 'planned_date_start'
            """
        )
        if self.env.cr.fetchone():
            return (
                "COALESCE(t.planned_date_start::date, p.date_start, "
                "t.create_date::date)"
            )
        return "COALESCE(p.date_start, t.create_date::date)"

    def init(self):
        """Fonte única para dashboards: previsto e real lado a lado.

        Duas famílias de linhas, somáveis entre si:
        - previsto: por tarefa e responsável, com o custo horas previstas / nº de
          responsáveis / horas mensais do plano x custo mensal total do colaborador,
          distribuído pelos meses do período da tarefa (início até o prazo) em
          proporção aos dias de cada mês; a data da linha é o dia 1 do mês;
        - real: uma linha por lançamento de horas, vinda do relatório de custo.
        O desvio de cada linha é previsto - real (positivo = gastou menos que o
        previsto), então a soma por obra, colaborador ou período dá o desvio
        correto. Valores na moeda da empresa (sem conversão).
        Início da tarefa: planned_date_start, se o campo existir, senão o início do
        projeto, senão a criação da tarefa. Fim: prazo da tarefa, senão o fim do
        projeto, senão o próprio início.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        start_expr = SQL(self._planned_start_expression())
        end_expr = SQL("COALESCE(t.date_deadline::date, p.date, %s)", start_expr)
        self.env.cr.execute(
            SQL(
                """
            CREATE OR REPLACE VIEW %(table)s AS (
                WITH assignees AS (
                    SELECT task_id, COUNT(*) AS cnt
                    FROM project_task_user_rel
                    GROUP BY task_id
                ),
                task_assignees AS (
                    SELECT
                        t.project_id,
                        r.user_id,
                        a.cnt,
                        t.allocated_hours,
                        COALESCE(p.company_id, t.company_id) AS plan_company_id,
                        %(start)s AS start_d,
                        GREATEST(%(end)s, %(start)s) AS end_d
                    FROM project_task t
                    JOIN project_project p ON p.id = t.project_id
                    JOIN assignees a ON a.task_id = t.id
                    JOIN project_task_user_rel r ON r.task_id = t.id
                    WHERE t.allocated_hours > 0
                ),
                planned_task_cost AS (
                    SELECT
                        ta.project_id,
                        e.id AS employee_id,
                        ta.start_d,
                        ta.end_d,
                        ta.allocated_hours / ta.cnt
                            / NULLIF(COALESCE(pc.employer_plan_monthly_hours, 160), 0)
                            * (
                                COALESCE(e.employer_salary_benefits_cost, 0)
                                + COALESCE(e.employer_provisions_cost, 0)
                            ) AS cost
                    FROM task_assignees ta
                    JOIN hr_employee e ON e.user_id = ta.user_id
                    LEFT JOIN res_company pc ON pc.id = ta.plan_company_id
                ),
                planned_rows AS (
                    SELECT
                        c.project_id,
                        c.employee_id,
                        m.month_start::date AS date,
                        0::float AS unit_amount,
                        c.cost
                            * (
                                LEAST(
                                    c.end_d,
                                    (m.month_start + INTERVAL '1 month'
                                        - INTERVAL '1 day')::date
                                ) - GREATEST(c.start_d, m.month_start::date) + 1
                            )
                            / (c.end_d - c.start_d + 1) AS planned_cost,
                        0::numeric AS real_cost
                    FROM planned_task_cost c
                    CROSS JOIN LATERAL generate_series(
                        date_trunc('month', c.start_d::timestamp),
                        date_trunc('month', c.end_d::timestamp),
                        INTERVAL '1 month'
                    ) AS m(month_start)
                ),
                real_rows AS (
                    SELECT
                        project_id,
                        employee_id,
                        date,
                        unit_amount,
                        0::numeric AS planned_cost,
                        total_cost AS real_cost
                    FROM planservice_employer_cost_report
                ),
                all_rows AS (
                    SELECT * FROM planned_rows
                    UNION ALL
                    SELECT * FROM real_rows
                )
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY ar.project_id, ar.employee_id, ar.date,
                            ar.planned_cost, ar.real_cost
                    ) AS id,
                    ar.project_id AS project_id,
                    ar.project_id AS project_key,
                    ar.employee_id AS employee_id,
                    ar.date AS date,
                    rc.id AS company_id,
                    rc.currency_id AS currency_id,
                    ar.unit_amount AS unit_amount,
                    ar.planned_cost AS planned_cost,
                    ar.real_cost AS real_cost,
                    ar.planned_cost - ar.real_cost AS cost_deviation
                FROM all_rows ar
                JOIN project_project p ON p.id = ar.project_id
                LEFT JOIN res_company rc
                    ON rc.id = COALESCE(
                        p.company_id, (SELECT MIN(id) FROM res_company)
                    )
            )
            """,
                table=SQL.identifier(self._table),
                start=start_expr,
                end=end_expr,
            )
        )
