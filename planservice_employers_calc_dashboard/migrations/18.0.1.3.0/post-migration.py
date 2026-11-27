# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_employers_calc_dashboard.hooks import (
    DASHBOARD_XMLID,
    MODULE,
    S_CURVE_ITEM,
    add_dashboard_item,
)


def migrate(cr, version):
    """Acrescenta a curva S (previsto x realizado acumulado por mês) ao dashboard.

    Só cria o item: o dashboard e os filtros salvos pelos usuários ficam como
    estão.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    dashboard = env.ref(f"{MODULE}.{DASHBOARD_XMLID}", raise_if_not_found=False)
    if dashboard:
        add_dashboard_item(env, dashboard, S_CURVE_ITEM)
