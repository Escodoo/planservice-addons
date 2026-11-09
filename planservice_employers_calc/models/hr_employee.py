# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    employer_salary_benefits_cost = fields.Monetary(
        string="Salary + benefits (monthly)",
        currency_field="currency_id",
        groups="hr.group_hr_user",
        help="Monthly salary plus benefits amount.",
    )
    employer_provisions_cost = fields.Monetary(
        string="Provisions (monthly)",
        currency_field="currency_id",
        groups="hr.group_hr_user",
        help="Monthly provisions amount (vacation, 13th salary etc.).",
    )
    employer_monthly_total_cost = fields.Monetary(
        string="Total monthly cost",
        currency_field="currency_id",
        groups="hr.group_hr_user",
        compute="_compute_employer_monthly_total_cost",
        help="Salary + benefits + provisions.",
    )

    @api.depends("employer_salary_benefits_cost", "employer_provisions_cost")
    def _compute_employer_monthly_total_cost(self):
        for employee in self:
            employee.employer_monthly_total_cost = (
                employee.employer_salary_benefits_cost
                + employee.employer_provisions_cost
            )
