# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools
from odoo.tools import SQL

from .planservice_employer_planned_live import leave_days_ctes


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
        help="Actual: date of the timesheet entry. Planned: each day of the "
        "task period; only business days carry cost, the others show zero.",
    )
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    unit_amount = fields.Float(string="Logged hours", readonly=True)
    planned_cost = fields.Monetary(string="Planned cost", readonly=True)
    real_cost = fields.Monetary(string="Actual cost", readonly=True)
    cost_deviation = fields.Monetary(string="Cost deviation", readonly=True)

    def init(self):
        """Fonte única para dashboards: previsto e real lado a lado.

        Duas famílias de linhas, somáveis entre si:
        - previsto: por tarefa, responsável e dia. Projeto com linha de base
          (planejamento travado) usa só a linha de base gravada
          (planservice.employer.planned.cost); os demais usam o previsto ao vivo
          (planservice.employer.planned.live), com o custo vigente hoje. O valor
          de cada mês é espalhado pelos dias úteis do pedaço da tarefa naquele
          mês (date_start a date_end; seg-sex, sem feriados do calendário do
          colaborador); os demais dias do período aparecem com valor zero. Sem
          dia útil no período, o valor é dividido pelos dias corridos;
        - real: uma linha por lançamento de horas, vinda do relatório de custo.
        O desvio de cada linha é previsto - real (positivo = gastou menos que o
        previsto), então a soma por obra, colaborador ou período dá o desvio
        correto. Valores na moeda da empresa (sem conversão).
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            SQL(
                """
            CREATE OR REPLACE VIEW %(table)s AS (
                WITH %(leave_ctes)s,
                planned_monthly AS (
                    -- previsto mensal (1 linha por mês) com o período da tarefa
                    -- no mês; linha de base sem período usa o mês inteiro
                    SELECT
                        b.project_id,
                        b.employee_id,
                        COALESCE(b.date_start, b.date) AS date_start,
                        COALESCE(
                            b.date_end,
                            (b.date + INTERVAL '1 month' - INTERVAL '1 day')::date
                        ) AS date_end,
                        b.planned_cost::numeric AS planned_cost
                    FROM planservice_employer_planned_cost b
                    UNION ALL
                    SELECT
                        l.project_id,
                        l.employee_id,
                        l.date_start,
                        l.date_end,
                        l.planned_cost::numeric AS planned_cost
                    FROM planservice_employer_planned_live l
                    JOIN project_project lp ON lp.id = l.project_id
                    WHERE lp.employer_baseline_date IS NULL
                ),
                planned_monthly_calendar AS (
                    -- calendário de cada linha: do colaborador, senão da empresa
                    SELECT
                        ROW_NUMBER() OVER () AS line_id,
                        pm.project_id,
                        pm.employee_id,
                        pm.date_start,
                        pm.date_end,
                        pm.planned_cost,
                        COALESCE(emp.resource_calendar_id, comp.resource_calendar_id)
                            AS calendar_id
                    FROM planned_monthly pm
                    JOIN project_project p ON p.id = pm.project_id
                    JOIN res_company comp
                        ON comp.id = COALESCE(
                            p.company_id, (SELECT MIN(id) FROM res_company)
                        )
                    LEFT JOIN hr_employee emp ON emp.id = pm.employee_id
                ),
                planned_days_raw AS (
                    -- cada dia do período da linha, com flag de dia útil
                    SELECT
                        pc.line_id,
                        d.day::date AS day,
                        (
                            EXTRACT(isodow FROM d.day::date) < 6
                            AND ld.day IS NULL
                        ) AS is_business
                    FROM planned_monthly_calendar pc
                    CROSS JOIN LATERAL generate_series(
                        pc.date_start::timestamp,
                        pc.date_end::timestamp,
                        INTERVAL '1 day'
                    ) AS d(day)
                    LEFT JOIN leave_days_by_calendar ld
                        ON ld.calendar_key = COALESCE(pc.calendar_id, 0)
                        AND ld.day = d.day::date
                ),
                planned_days AS (
                    SELECT
                        line_id,
                        day,
                        is_business,
                        COUNT(*) OVER (PARTITION BY line_id) AS days,
                        COUNT(*) FILTER (WHERE is_business)
                            OVER (PARTITION BY line_id) AS business_days
                    FROM planned_days_raw
                ),
                planned_rows AS (
                    -- uma linha por dia do período; só dias úteis recebem custo
                    SELECT
                        pc.project_id,
                        pc.employee_id,
                        pd.day AS date,
                        0::float AS unit_amount,
                        CASE
                            WHEN pd.business_days = 0
                                THEN pc.planned_cost / pd.days
                            WHEN pd.is_business
                                THEN pc.planned_cost / pd.business_days
                            ELSE 0
                        END AS planned_cost,
                        0::numeric AS real_cost
                    FROM planned_monthly_calendar pc
                    JOIN planned_days pd ON pd.line_id = pc.line_id
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
                leave_ctes=leave_days_ctes(),
            )
        )
