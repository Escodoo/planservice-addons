# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.tools.misc import format_date


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    day_percentage = fields.Float(
        string="Day %",
        compute="_compute_day_percentage",
        inverse="_inverse_day_percentage",
        store=True,
        digits=(16, 2),
        help="Percentage of the employee's working day. Updates Time Spent "
        "from the resource calendar hours per day.",
    )

    def _get_timesheet_hours_per_day(self):
        """Average working hours of the employee (or company) calendar."""
        self.ensure_one()
        calendar = (
            self.employee_id.resource_calendar_id
            or self.company_id.resource_calendar_id
            or self.env.company.resource_calendar_id
        )
        return calendar.hours_per_day if calendar else 8.0

    def _hours_per_day_for_vals(self, vals):
        employee = self.env["hr.employee"].browse(vals.get("employee_id"))
        company = (
            self.env["res.company"].browse(vals.get("company_id")) or self.env.company
        )
        calendar = (
            employee.resource_calendar_id if employee else False
        ) or company.resource_calendar_id
        return calendar.hours_per_day if calendar else 8.0

    @api.depends(
        "unit_amount",
        "employee_id",
        "employee_id.resource_calendar_id.hours_per_day",
        "company_id",
        "company_id.resource_calendar_id.hours_per_day",
    )
    def _compute_day_percentage(self):
        for line in self:
            hours_per_day = line._get_timesheet_hours_per_day()
            if float_is_zero(hours_per_day, precision_digits=2):
                line.day_percentage = 0.0
            else:
                line.day_percentage = float_round(
                    (line.unit_amount or 0.0) / hours_per_day * 100.0,
                    precision_digits=2,
                )

    def _inverse_day_percentage(self):
        for line in self:
            hours_per_day = line._get_timesheet_hours_per_day()
            line.unit_amount = float_round(
                hours_per_day * (line.day_percentage or 0.0) / 100.0,
                precision_digits=2,
            )

    @api.onchange("day_percentage")
    def _onchange_day_percentage(self):
        self._inverse_day_percentage()

    @api.onchange("unit_amount", "employee_id")
    def _onchange_unit_amount_day_percentage(self):
        self._compute_day_percentage()

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if (
                vals.get("project_id")
                and "day_percentage" in vals
                and "unit_amount" not in vals
            ):
                hours_per_day = self._hours_per_day_for_vals(vals)
                vals["unit_amount"] = float_round(
                    hours_per_day * (vals.get("day_percentage") or 0.0) / 100.0,
                    precision_digits=2,
                )
        return super().create(vals_list)

    @api.constrains("date", "employee_id", "unit_amount", "project_id")
    def _check_timesheet_day_capacity(self):
        timesheets = self.filtered(
            lambda line: line.project_id and line.employee_id and line.date
        )
        checked = set()
        for line in timesheets:
            key = (line.employee_id.id, line.date)
            if key in checked:
                continue
            checked.add(key)
            hours_per_day = line._get_timesheet_hours_per_day()
            if float_is_zero(hours_per_day, precision_digits=2):
                raise ValidationError(
                    _(
                        "Employee %(employee)s has no working hours defined "
                        "on the calendar.",
                        employee=line.employee_id.display_name,
                    )
                )
            day_lines = self.search(
                [
                    ("employee_id", "=", line.employee_id.id),
                    ("date", "=", line.date),
                    ("project_id", "!=", False),
                ]
            )
            total_hours = sum(day_lines.mapped("unit_amount"))
            if float_compare(total_hours, hours_per_day, precision_digits=2) > 0:
                used_percent = float_round(
                    total_hours / hours_per_day * 100.0, precision_digits=2
                )
                raise ValidationError(
                    _(
                        "You cannot log more than 100%% of the working day "
                        "(%(hours_per_day).2f h). %(employee)s would have "
                        "%(used_percent).2f%% (%(used_hours).2f h) on %(date)s.",
                        employee=line.employee_id.display_name,
                        hours_per_day=hours_per_day,
                        used_percent=used_percent,
                        used_hours=float_round(total_hours, precision_digits=2),
                        date=format_date(self.env, line.date),
                    )
                )
