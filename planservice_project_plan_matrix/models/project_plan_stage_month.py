# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


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
