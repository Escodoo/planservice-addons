# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models, tools
from odoo.tools import SQL


class PlanserviceEmployerCostReport(models.Model):
    _name = "planservice.employer.cost.report"
    _description = "Employee cost by project"
    _auto = False
    _order = "date desc, project_id, employee_id"

    date = fields.Date(readonly=True)
    project_id = fields.Many2one("project.project", string="Job site", readonly=True)
    task_id = fields.Many2one("project.task", string="Task", readonly=True)
    employee_id = fields.Many2one("hr.employee", string="Team member", readonly=True)
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one("res.currency", readonly=True)
    unit_amount = fields.Float(string="Hours", readonly=True)
    day_percentage = fields.Float(string="% of day", readonly=True)
    salary_benefits_cost = fields.Monetary(string="Salary + benefits", readonly=True)
    provisions_cost = fields.Monetary(string="Provisions", readonly=True)
    total_cost = fields.Monetary(string="Total cost", readonly=True)

    def init(self):
        """Rateia o custo mensal do colaborador pela fração do mês trabalhada.

        custo da linha = custo mensal x (horas / horas por dia) / dias úteis do mês

        Dias úteis: segunda a sexta do mês da data do lançamento, excluídos os
        feriados globais do calendário do colaborador (ou da empresa, se ele não
        tiver calendário). Um feriado cobre o dia se incluir o meio-dia UTC.
        """
        tools.drop_view_if_exists(self.env.cr, self._table)
        self.env.cr.execute(
            SQL(
                """
            CREATE OR REPLACE VIEW %s AS (
                WITH line AS (
                    SELECT
                        aal.id,
                        aal.date,
                        aal.project_id,
                        aal.task_id,
                        aal.employee_id,
                        aal.company_id,
                        aal.unit_amount,
                        comp.currency_id,
                        COALESCE(cal.hours_per_day, ccal.hours_per_day, 8.0)
                            AS hours_per_day,
                        COALESCE(emp.resource_calendar_id, comp.resource_calendar_id)
                            AS calendar_id,
                        date_trunc('month', aal.date)::date AS month_start,
                        COALESCE(emp.employer_salary_benefits_cost, 0)
                            AS salary_benefits,
                        COALESCE(emp.employer_provisions_cost, 0) AS provisions
                    FROM account_analytic_line aal
                    JOIN hr_employee emp ON emp.id = aal.employee_id
                    JOIN res_company comp ON comp.id = aal.company_id
                    LEFT JOIN resource_calendar cal
                        ON cal.id = emp.resource_calendar_id
                    LEFT JOIN resource_calendar ccal
                        ON ccal.id = comp.resource_calendar_id
                    WHERE aal.project_id IS NOT NULL
                ),
                months AS (
                    SELECT DISTINCT calendar_id, month_start
                    FROM line
                    WHERE calendar_id IS NOT NULL
                ),
                business_days AS (
                    SELECT m.calendar_id, m.month_start, COUNT(*) AS days
                    FROM months m
                    CROSS JOIN LATERAL generate_series(
                        m.month_start::timestamp,
                        (m.month_start + INTERVAL '1 month'
                            - INTERVAL '1 day')::timestamp,
                        INTERVAL '1 day'
                    ) AS d(day)
                    WHERE EXTRACT(isodow FROM d.day) < 6
                        AND NOT EXISTS (
                            SELECT 1
                            FROM resource_calendar_leaves l
                            WHERE l.resource_id IS NULL
                                AND (
                                    l.calendar_id = m.calendar_id
                                    OR l.calendar_id IS NULL
                                )
                                AND l.date_from <= d.day + INTERVAL '12 hours'
                                AND l.date_to >= d.day + INTERVAL '12 hours'
                        )
                    GROUP BY m.calendar_id, m.month_start
                ),
                costed AS (
                    SELECT
                        line.*,
                        COALESCE(
                            line.unit_amount
                            / NULLIF(line.hours_per_day, 0)
                            / NULLIF(bd.days, 0),
                            0
                        ) AS month_fraction
                    FROM line
                    LEFT JOIN business_days bd
                        ON bd.calendar_id = line.calendar_id
                        AND bd.month_start = line.month_start
                )
                SELECT
                    costed.id AS id,
                    costed.date AS date,
                    costed.project_id AS project_id,
                    costed.task_id AS task_id,
                    costed.employee_id AS employee_id,
                    costed.company_id AS company_id,
                    costed.currency_id AS currency_id,
                    costed.unit_amount AS unit_amount,
                    COALESCE(
                        costed.unit_amount / NULLIF(costed.hours_per_day, 0) * 100,
                        0
                    ) AS day_percentage,
                    costed.salary_benefits * costed.month_fraction
                        AS salary_benefits_cost,
                    costed.provisions * costed.month_fraction AS provisions_cost,
                    (costed.salary_benefits + costed.provisions)
                        * costed.month_fraction AS total_cost
                FROM costed
            )
            """,
                SQL.identifier(self._table),
            )
        )
