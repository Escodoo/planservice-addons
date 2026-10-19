# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_project_plan_matrix.hooks import link_plan_tasks


def migrate(cr, version):
    """Link tasks generated before plan_line_id existed to their plan lines."""
    link_plan_tasks(api.Environment(cr, SUPERUSER_ID, {}))
