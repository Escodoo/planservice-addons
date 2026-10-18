# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_project_plan_matrix.hooks import (
    disable_project_milestones,
)


def migrate(cr, version):
    """Turn off milestones on databases where the module is already installed."""
    disable_project_milestones(api.Environment(cr, SUPERUSER_ID, {}))
