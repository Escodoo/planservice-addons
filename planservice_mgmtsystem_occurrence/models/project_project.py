# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

    occurrence_count = fields.Integer(
        string="Occurrences",
        compute="_compute_occurrence_count",
        groups="mgmtsystem.group_mgmtsystem_viewer",
    )

    def _compute_occurrence_count(self):
        groups = self.env["mgmtsystem.nonconformity"]._read_group(
            [("project_id", "in", self.ids)], ["project_id"], ["__count"]
        )
        counts = {project.id: count for project, count in groups}
        for project in self:
            project.occurrence_count = counts.get(project.id, 0)

    def action_view_occurrences(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("Occurrence Records"),
            "res_model": "mgmtsystem.nonconformity",
            "view_mode": "list,form",
            "domain": [("project_id", "=", self.id)],
            "context": {"default_project_id": self.id},
        }

    def action_new_occurrence(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": self.env._("New Occurrence Record"),
            "res_model": "mgmtsystem.nonconformity",
            "view_mode": "form",
            "target": "current",
            "context": {"default_project_id": self.id},
        }
