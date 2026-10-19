# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_project_plan_matrix.hooks import (
    translate_project_statuses,
)


def migrate(cr, version):
    """Translate the project statuses that now lock the plan."""
    translate_project_statuses(api.Environment(cr, SUPERUSER_ID, {}))
