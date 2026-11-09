# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo.tools import file_open

MODULE = "planservice_employers_calc_dashboard"
DASHBOARD_XMLID = "dashboard_cost"
PAYLOAD_PATH = f"{MODULE}/data/dashboard_cost.json"


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
