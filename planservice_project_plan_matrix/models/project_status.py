# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models


class ProjectStatus(models.Model):
    _inherit = "project.status"

    allow_replan = fields.Boolean(
        string="Allow Re-planning",
        help="Projects with this status can edit the plan matrix and run "
        "Generate Plan.",
    )
