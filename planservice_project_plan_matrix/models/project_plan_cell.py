# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from calendar import monthrange

from odoo import api, fields, models
from odoo.tools.float_utils import float_round
from odoo.tools.misc import format_date


class ProjectPlanCell(models.Model):
    _name = "project.plan.cell"
    _description = "Project Plan Cell"
    _order = "line_id, month"
    _sql_constraints = [
        (
            "line_month_uniq",
            "unique(line_id, month)",
            "A plan line cannot have two cells for the same month.",
        ),
    ]

    name = fields.Char(compute="_compute_name", store=True)
    line_id = fields.Many2one(
        comodel_name="project.plan.line",
        required=True,
        ondelete="cascade",
        index=True,
    )
    project_id = fields.Many2one(
        related="line_id.project_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="line_id.company_id",
        store=True,
        index=True,
    )
    role_id = fields.Many2one(
        related="line_id.role_id",
        store=True,
    )
    user_id = fields.Many2one(
        related="line_id.user_id",
        store=True,
    )
    month = fields.Date(
        required=True,
        index=True,
        help="First day of the calendar month.",
    )
    stage_id = fields.Many2one(
        comodel_name="project.plan.stage",
        string="Stage",
        ondelete="restrict",
    )
    capacity_percent = fields.Float(
        string="Capacity (%)",
        digits=(16, 2),
        default=0.0,
    )
    monthly_hours = fields.Float(
        compute="_compute_monthly_hours",
        store=True,
        digits=(16, 2),
        help="Hours of one resource used as 100% capacity for this month.",
    )
    hours = fields.Float(
        compute="_compute_hours",
        store=True,
        digits=(16, 2),
    )

    @api.model
    def _month_bounds(self, day):
        """Return (first_day, last_day) of the calendar month of *day*."""
        first = fields.Date.to_date(day).replace(day=1)
        last_day = monthrange(first.year, first.month)[1]
        return first, first.replace(day=last_day)

    @api.depends("month")
    def _compute_name(self):
        for cell in self:
            cell.name = (
                format_date(self.env, cell.month, date_format="MMM yy")
                if cell.month
                else False
            )

    @api.depends("company_id", "company_id.hour_plan_monthly_hours")
    def _compute_monthly_hours(self):
        for cell in self:
            company = cell.company_id or self.env.company
            cell.monthly_hours = company.hour_plan_monthly_hours or 160.0

    @api.depends("capacity_percent", "monthly_hours")
    def _compute_hours(self):
        for cell in self:
            cell.hours = float_round(
                cell.monthly_hours * cell.capacity_percent / 100.0,
                precision_digits=2,
            )

    def action_apply_stage_to_range(self, stage_id, date_from, date_to):
        """Apply a stage to a range of months."""
        for cell in self:
            if date_from <= cell.month <= date_to:
                cell.stage_id = stage_id
