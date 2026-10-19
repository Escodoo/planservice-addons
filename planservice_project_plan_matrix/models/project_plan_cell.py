# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

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
    can_replan = fields.Boolean(related="project_id.can_replan")
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
            cell.monthly_hours = company.hour_plan_monthly_hours

    @api.depends("capacity_percent", "monthly_hours")
    def _compute_hours(self):
        for cell in self:
            cell.hours = float_round(
                cell.monthly_hours * cell.capacity_percent / 100.0,
                precision_digits=2,
            )

    @api.model_create_multi
    def create(self, vals_list):
        self.env["project.plan.line"].browse(
            {vals["line_id"] for vals in vals_list if vals.get("line_id")}
        ).project_id._check_can_replan()
        return super().create(vals_list)

    def write(self, vals):
        self.project_id._check_can_replan()
        return super().write(vals)

    def unlink(self):
        self.project_id._check_can_replan()
        return super().unlink()
