# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_project_plan_matrix.hooks import (
    allow_replan_on_pending,
    translate_project_statuses,
)


def migrate(cr, version):
    """Open Pending for re-planning and translate the project statuses."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    allow_replan_on_pending(env)
    translate_project_statuses(env)
