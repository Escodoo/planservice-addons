# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


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
