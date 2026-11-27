# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_employers_calc_dashboard.hooks import (
    DASHBOARD_XMLID,
    MODULE,
    create_project_menu,
)


def migrate(cr, version):
    """Repete o menu do dashboard no app Projetos.

    Só cria o menu: o dashboard e os filtros salvos pelos usuários ficam como
    estão.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    dashboard = env.ref(f"{MODULE}.{DASHBOARD_XMLID}", raise_if_not_found=False)
    if dashboard and dashboard.menu_id:
        create_project_menu(env, dashboard)
