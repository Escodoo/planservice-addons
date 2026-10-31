# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    allocated_hours = fields.Float(string="Planned Time")
    effective_hours = fields.Float(string="Actual Time")
    user_ids = fields.Many2many(string="Collaborator")
    plan_line_id = fields.Many2one(
        comodel_name="project.plan.line",
        string="Plan Line",
        ondelete="set null",
        index="btree_not_null",
        copy=False,
        readonly=True,
        help="Project plan line that generated this task.",
    )
    has_plan = fields.Boolean(
        compute="_compute_has_plan",
        help="The project has a plan, so its planning fields are driven by it.",
    )

    @api.depends("project_id.plan_line_ids")
    def _compute_has_plan(self):
        for task in self:
            task.has_plan = bool(task.project_id.plan_line_ids)
