# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProjectPlanLine(models.Model):
    _name = "project.plan.line"
    _description = "Project Plan Line"
    _order = "sequence, id"

    sequence = fields.Integer(default=10)
    project_id = fields.Many2one(
        comodel_name="project.project",
        required=True,
        ondelete="cascade",
        index=True,
    )
    company_id = fields.Many2one(
        related="project_id.company_id",
        store=True,
        index=True,
    )
    role_id = fields.Many2one(
        comodel_name="project.plan.role",
        string="Role",
        required=True,
        ondelete="restrict",
    )
    user_id = fields.Many2one(
        comodel_name="res.users",
        string="Assigned To",
        required=True,
        domain="[('share', '=', False)]",
    )
    active = fields.Boolean(default=True)
    cell_ids = fields.One2many(
        comodel_name="project.plan.cell",
        inverse_name="line_id",
        string="Plan Cells",
        copy=True,
    )
    total_hours = fields.Float(
        compute="_compute_total_hours",
        store=True,
        digits=(16, 2),
    )

    def _get_cells_in_period(self):
        """Cells of the months inside the project period.

        Cells outside the period are kept, so they come back when the period
        is extended, but they are not planned.
        """
        self.ensure_one()
        first_month = self.project_id.plan_first_month
        last_month = self.project_id.plan_last_month
        return self.cell_ids.filtered(
            lambda c: (not first_month or c.month >= first_month)
            and (not last_month or c.month <= last_month)
        )

    @api.depends(
        "cell_ids.hours",
        "cell_ids.month",
        "project_id.plan_first_month",
        "project_id.plan_last_month",
    )
    def _compute_total_hours(self):
        for line in self:
            line.total_hours = sum(line._get_cells_in_period().mapped("hours"))

    @api.constrains("role_id", "user_id")
    def _check_unique_role_user(self):
        for line in self:
            duplicate = self.search(
                [
                    ("project_id", "=", line.project_id.id),
                    ("role_id", "=", line.role_id.id),
                    ("user_id", "=", line.user_id.id),
                    ("id", "!=", line.id),
                ],
                limit=1,
            )
            if duplicate:
                raise ValidationError(
                    _(
                        "A plan line with the same role and user already "
                        "exists in this project."
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        lines = super().create(vals_list)
        cell_vals_list = []
        for line in lines:
            months = line.project_id._generate_month_range(
                line.project_id.date_start, line.project_id.date
            )
            existing_months = line.cell_ids.mapped("month")
            cell_vals_list += [
                {"line_id": line.id, "month": month, "capacity_percent": 0.0}
                for month in months
                if month not in existing_months
            ]
        if cell_vals_list:
            self.env["project.plan.cell"].create(cell_vals_list)
        return lines
