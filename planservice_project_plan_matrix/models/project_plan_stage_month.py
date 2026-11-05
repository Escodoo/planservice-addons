# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class ProjectPlanStageMonth(models.Model):
    _name = "project.plan.stage.month"
    _description = "Project Plan Stage Month"
    _order = "date_from, id"

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
    stage_id = fields.Many2one(
        comodel_name="project.plan.stage",
        string="Stage",
        required=True,
        ondelete="restrict",
    )
    date_from = fields.Date(string="From", required=True)
    date_to = fields.Date(string="To", required=True)

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for mapping in self:
            if mapping.date_from > mapping.date_to:
                raise ValidationError(
                    _("The stage start month must be before its end month.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        self.env["project.project"].browse(
            {vals["project_id"] for vals in vals_list if vals.get("project_id")}
        )._check_can_replan()
        return super().create(vals_list)

    def write(self, vals):
        projects = self.project_id
        if vals.get("project_id"):
            projects |= projects.browse(vals["project_id"])
        projects._check_can_replan()
        return super().write(vals)

    def unlink(self):
        self.project_id._check_can_replan()
        return super().unlink()
