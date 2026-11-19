# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import api, fields, models

EMPLOYER_COST_FIELDS = ("employer_salary_benefits_cost", "employer_provisions_cost")
EMPLOYER_COST_DEFAULT_TZ = "America/Sao_Paulo"


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    employer_salary_benefits_cost = fields.Monetary(
        string="Salary + benefits (monthly)",
        currency_field="currency_id",
        groups="hr.group_hr_user",
        help="Monthly salary plus benefits amount. A change applies from the "
        "next day on.",
    )
    employer_provisions_cost = fields.Monetary(
        string="Provisions (monthly)",
        currency_field="currency_id",
        groups="hr.group_hr_user",
        help="Monthly provisions amount (vacation, 13th salary etc.). A change "
        "applies from the next day on.",
    )
    employer_monthly_total_cost = fields.Monetary(
        string="Total monthly cost",
        currency_field="currency_id",
        groups="hr.group_hr_user",
        compute="_compute_employer_monthly_total_cost",
        help="Salary + benefits + provisions.",
    )
    employer_cost_version_ids = fields.One2many(
        "planservice.employer.cost.version",
        "employee_id",
        string="Cost history",
        groups="hr.group_hr_user",
        readonly=True,
    )

    @api.depends("employer_salary_benefits_cost", "employer_provisions_cost")
    def _compute_employer_monthly_total_cost(self):
        for employee in self:
            employee.employer_monthly_total_cost = (
                employee.employer_salary_benefits_cost
                + employee.employer_provisions_cost
            )

    def _employer_cost_today(self):
        """Hoje no fuso do usuário (America/Sao_Paulo se ele não tiver fuso)."""
        tz = self.env.context.get("tz") or self.env.user.tz or EMPLOYER_COST_DEFAULT_TZ
        return fields.Date.context_today(self.with_context(tz=tz))

    def _sync_employer_cost_version(self):
        """Registra o custo atual da ficha como versão de custo.

        Sem versão anterior, a versão vale desde sempre. Senão vale a partir de
        amanhã; nova alteração no mesmo dia atualiza essa mesma versão.
        """
        versions = self.env["planservice.employer.cost.version"].sudo()
        for employee in self.sudo():
            values = {
                "salary_benefits_cost": employee.employer_salary_benefits_cost,
                "provisions_cost": employee.employer_provisions_cost,
            }
            if not versions.search_count([("employee_id", "=", employee.id)]):
                versions.create(dict(values, employee_id=employee.id, date_from=False))
                continue
            date_from = employee._employer_cost_today() + timedelta(days=1)
            pending = versions.search(
                [("employee_id", "=", employee.id), ("date_from", "=", date_from)],
                limit=1,
            )
            if pending:
                pending.write(values)
            else:
                versions.create(
                    dict(values, employee_id=employee.id, date_from=date_from)
                )

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        employees.sudo().filtered(
            lambda e: e.employer_salary_benefits_cost or e.employer_provisions_cost
        )._sync_employer_cost_version()
        return employees

    def write(self, vals):
        if not set(EMPLOYER_COST_FIELDS) & set(vals):
            return super().write(vals)
        before = {
            employee.id: tuple(employee[name] for name in EMPLOYER_COST_FIELDS)
            for employee in self.sudo()
        }
        res = super().write(vals)
        changed = self.sudo().filtered(
            lambda e: tuple(e[name] for name in EMPLOYER_COST_FIELDS) != before[e.id]
        )
        changed._sync_employer_cost_version()
        return res
