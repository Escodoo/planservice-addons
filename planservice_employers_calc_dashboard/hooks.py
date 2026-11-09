# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo.tools import file_open

MODULE = "planservice_employers_calc_dashboard"
DASHBOARD_XMLID = "dashboard_cost"
PROJECT_MENU_XMLID = "menu_dashboard_cost_project"
PAYLOAD_PATH = f"{MODULE}/data/dashboard_cost.json"
S_CURVE_ITEM = "Curva S: previsto x realizado acumulado"


def post_init_hook(env):
    """Cria o dashboard de custo de pessoal e o registra com um xmlid do módulo.

    O xmlid faz o Odoo apagar o dashboard quando o módulo for desinstalado e
    permite ao botão do projeto encontrá-lo.
    """
    # Apaga dashboard existente com o mesmo xmlid, se houver
    existing_dashboard = env.ref(
        f"{MODULE}.{DASHBOARD_XMLID}", raise_if_not_found=False
    )
    if existing_dashboard:
        existing_dashboard.unlink()

    with file_open(PAYLOAD_PATH) as payload_file:
        payload = json.load(payload_file)
    dashboard_ids = env["boardkit.dashboard"].import_config(payload)
    dashboard = env["boardkit.dashboard"].browse(dashboard_ids[:1])
    dashboard.write(
        {
            "published": True,
            "group_ids": [(4, env.ref("hr_timesheet.group_timesheet_manager").id)],
            "menu_parent_id": env.ref("hr_timesheet.timesheet_menu_root").id,
            "menu_name": dashboard.name,
        }
    )
    env["ir.model.data"].create(
        {
            "module": MODULE,
            "name": DASHBOARD_XMLID,
            "model": "boardkit.dashboard",
            "res_id": dashboard.id,
            "noupdate": True,
        }
    )
    create_project_menu(env, dashboard)


def add_dashboard_item(env, dashboard, name):
    """Acrescenta ao dashboard o item ``name`` do JSON, sem recriar o dashboard.

    Mantém os filtros salvos pelos usuários. Não faz nada se o item já existe.
    """
    if dashboard.item_ids.filtered(lambda item: item.name == name):
        return
    with file_open(PAYLOAD_PATH) as payload_file:
        payload = json.load(payload_file)
    item_data = next(
        data for data in payload["dashboards"][0]["items"] if data["name"] == name
    )
    item_model = env["boardkit.dashboard.item"]
    item = item_model.create(item_model._import_prepare_vals(item_data, dashboard.id))
    layout = json.loads(dashboard.layout_json or "{}")
    layout[str(item.id)] = item_data["layout"]
    dashboard.layout_json = json.dumps(layout)


def create_project_menu(env, dashboard):
    """Repete o menu do dashboard no app Projetos.

    O Boardkit guarda um só menu por dashboard (o de Timesheets). Este segundo
    menu usa a mesma ação e os mesmos grupos. O xmlid faz o Odoo apagá-lo na
    desinstalação; quando o dashboard é recriado, o menu antigo é trocado.
    """
    existing_menu = env.ref(f"{MODULE}.{PROJECT_MENU_XMLID}", raise_if_not_found=False)
    if existing_menu:
        existing_menu.unlink()
    action = dashboard.client_action_id
    menu = env["ir.ui.menu"].create(
        {
            "name": dashboard.menu_id.name,
            "parent_id": env.ref("project.menu_main_pm").id,
            "sequence": dashboard.menu_id.sequence,
            "action": f"{action._name},{action.id}",
            "groups_id": [(6, 0, dashboard.menu_id.groups_id.ids)],
        }
    )
    env["ir.model.data"].create(
        {
            "module": MODULE,
            "name": PROJECT_MENU_XMLID,
            "model": "ir.ui.menu",
            "res_id": menu.id,
            "noupdate": True,
        }
    )
