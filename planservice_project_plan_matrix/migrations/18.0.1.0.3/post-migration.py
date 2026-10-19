# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_project_plan_matrix.hooks import (
    configure_project_settings,
)


def migrate(cr, version):
    """Enable project stages, which now decide when the plan can change."""
    configure_project_settings(api.Environment(cr, SUPERUSER_ID, {}))
