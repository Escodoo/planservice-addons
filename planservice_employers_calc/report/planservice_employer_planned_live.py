# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools
from odoo.tools import SQL

# Fuso usado para "hoje" no SQL do previsto ao vivo (a view não sabe o usuário).
PLANNED_LIVE_TZ = "America/Sao_Paulo"


def business_day_sql(day, calendar_id):
    """Expressão SQL verdadeira quando ``day`` é dia útil no calendário.

    Mesma regra do custo real: segunda a sexta, menos os feriados globais (sem
    recurso) do calendário ou sem calendário. Um feriado cobre o dia se incluir
    o meio-dia UTC.
    """
    return SQL(
        """(
            EXTRACT(isodow FROM %(day)s) < 6
            AND NOT EXISTS (
                SELECT 1
                FROM resource_calendar_leaves cl
                WHERE cl.resource_id IS NULL
                    AND (cl.calendar_id = %(calendar)s OR cl.calendar_id IS NULL)
                    AND cl.date_from <= %(day)s + INTERVAL '12 hours'
                    AND cl.date_to >= %(day)s + INTERVAL '12 hours'
            )
        )""",
        day=day,
        calendar=calendar_id,
    )


class PlanserviceEmployerPlannedLive(models.Model):
    """Previsto calculado na hora, por projeto, tarefa, colaborador e mês.

    Fonte única da regra do previsto: alimenta o relatório de previsto x real
    dos projetos sem linha de base e é copiada para a linha de base
    (planservice.employer.planned.cost) quando o projeto trava o planejamento.
    """

    _name = "planservice.employer.planned.live"
    _description = "Live planned cost by project, task, employee and month"
    _auto = False
    _order = "project_id, task_id, employee_id, date"

    project_id = fields.Many2one("project.project", string="Job site", readonly=True)
    task_id = fields.Many2one("project.task", readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Team member", readonly=True)
    date = fields.Date(readonly=True, help="First day of the month.")
    date_start = fields.Date(
        string="Period start",
        readonly=True,
        help="First day of the task period inside this month.",
    )
    date_end = fields.Date(
        string="Period end",
        readonly=True,
        help="Last day of the task period inside this month.",
    )
    company_id = fields.Many2one("res.company", readonly=True)
    allocated_hours = fields.Float(
        string="Planned hours",
        readonly=True,
        help="Planned hours of the task for this assignee (split equally).",
    )
    plan_monthly_hours = fields.Float(readonly=True)
    monthly_cost = fields.Float(
        string="Monthly cost",
        readonly=True,
        help="Total monthly cost of the team member valid today.",
    )
    planned_cost = fields.Float(readonly=True)

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
        """Previsto por tarefa e responsável, distribuído pelos dias úteis da tarefa.

        custo = horas previstas / nº de responsáveis / horas mensais do plano x
        custo mensal total do colaborador vigente hoje (versão de custo).
        O custo é dividido pelos dias úteis do período da tarefa (início até o
        prazo; seg-sex sem feriados do calendário do colaborador). Cada mês fica
        com a parte dos dias úteis que caem nele; mês sem dia útil da tarefa não
        gera linha. Tarefa sem nenhum dia útil (ex.: só fim de semana) usa os
        dias corridos, para o custo não sumir.
        A data da linha é o dia 1 do mês; date_start e date_end guardam o pedaço
        do período da tarefa dentro do mês, usado para espalhar o valor por dia.
        Início: planned_date_start, se existir, senão o início do projeto, senão
        a criação da tarefa. Fim: prazo da tarefa, senão o fim do projeto, senão
        o próprio início.
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
                        t.id AS task_id,
                        t.project_id,
                        r.user_id,
                        t.allocated_hours / a.cnt AS hours,
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
                        ta.task_id,
                        ta.project_id,
                        e.id AS employee_id,
                        ta.plan_company_id,
                        ta.start_d,
                        ta.end_d,
                        ta.hours,
                        COALESCE(pc.employer_plan_monthly_hours, 160)
                            AS plan_monthly_hours,
                        COALESCE(ver.total_cost, 0) AS monthly_cost,
                        -- calendário dos dias úteis: do colaborador, senão da empresa
                        COALESCE(e.resource_calendar_id, pc.resource_calendar_id)
                            AS calendar_id
                    FROM task_assignees ta
                    JOIN hr_employee e ON e.user_id = ta.user_id
                    LEFT JOIN res_company pc ON pc.id = ta.plan_company_id
                    LEFT JOIN LATERAL (
                        SELECT v.total_cost
                        FROM planservice_employer_cost_version v
                        WHERE v.employee_id = e.id
                            AND COALESCE(v.date_from, '-infinity'::date)
                                <= (now() AT TIME ZONE %(tz)s)::date
                        ORDER BY v.date_from DESC NULLS LAST
                        LIMIT 1
                    ) ver ON TRUE
                ),
                task_days AS (
                    -- cada dia do período da tarefa, marcando se é dia útil
                    SELECT
                        c.task_id,
                        c.employee_id,
                        date_trunc('month', d.day)::date AS month_start,
                        d.day::date AS day,
                        %(is_business)s AS is_business
                    FROM planned_task_cost c
                    CROSS JOIN LATERAL generate_series(
                        c.start_d::timestamp, c.end_d::timestamp, INTERVAL '1 day'
                    ) AS d(day)
                ),
                task_months AS (
                    -- pedaço da tarefa em cada mês: período e contagem de dias
                    SELECT
                        task_id,
                        employee_id,
                        month_start,
                        MIN(day) AS date_start,
                        MAX(day) AS date_end,
                        COUNT(*) AS days,
                        COUNT(*) FILTER (WHERE is_business) AS business_days
                    FROM task_days
                    GROUP BY task_id, employee_id, month_start
                ),
                task_totals AS (
                    SELECT
                        task_id,
                        employee_id,
                        SUM(days) AS days,
                        SUM(business_days) AS business_days
                    FROM task_months
                    GROUP BY task_id, employee_id
                )
                SELECT
                    ROW_NUMBER() OVER (
                        ORDER BY c.project_id, c.task_id, c.employee_id,
                            m.month_start
                    ) AS id,
                    c.project_id,
                    c.task_id,
                    c.employee_id,
                    m.month_start AS date,
                    m.date_start,
                    m.date_end,
                    c.plan_company_id AS company_id,
                    c.hours AS allocated_hours,
                    c.plan_monthly_hours,
                    c.monthly_cost,
                    c.hours
                        / NULLIF(c.plan_monthly_hours, 0)
                        * c.monthly_cost
                        * CASE
                            WHEN tt.business_days > 0
                                THEN m.business_days::float / tt.business_days
                            ELSE m.days::float / tt.days
                        END AS planned_cost
                FROM planned_task_cost c
                JOIN task_months m
                    ON m.task_id = c.task_id AND m.employee_id = c.employee_id
                JOIN task_totals tt
                    ON tt.task_id = c.task_id AND tt.employee_id = c.employee_id
                WHERE tt.business_days = 0 OR m.business_days > 0
            )
            """,
                table=SQL.identifier(self._table),
                start=start_expr,
                end=end_expr,
                tz=PLANNED_LIVE_TZ,
                is_business=business_day_sql(SQL("d.day::date"), SQL("c.calendar_id")),
            )
        )
