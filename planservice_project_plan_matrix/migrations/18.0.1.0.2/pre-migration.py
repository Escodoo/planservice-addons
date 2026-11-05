# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_project_plan_matrix.hooks import link_role_stage


def migrate(cr, version):
    """Reuse the "Cargos" stage instead of creating the module stage again."""
    link_role_stage(api.Environment(cr, SUPERUSER_ID, {}))
