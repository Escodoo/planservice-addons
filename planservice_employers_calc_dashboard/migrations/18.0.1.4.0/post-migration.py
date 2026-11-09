# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json
import re

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_employers_calc_dashboard.hooks import (
    DASHBOARD_XMLID,
    MODULE,
    S_CURVE_ITEM,
)

# os cards ocupam as linhas 0 a 3 do grid; a curva S vem logo depois
CARDS_END = 4


def rename_actual(text):
    """ "Custo real" vira "Custo Realizado"; nos demais textos, "real" vira
    "realizado" (ex.: "Previsto x real por obra")."""
    text = re.sub(r"\bCusto real\b", "Custo Realizado", text)
    return re.sub(r"\breal\b", "realizado", text)


def move_s_curve_after_cards(dashboard):
    """Põe a curva S logo abaixo dos cards e desce os outros gráficos.

    Não faz nada se a curva já está lá e nada ocupa o lugar dela.
    """
    curve = dashboard.item_ids.filtered(lambda item: item.name == S_CURVE_ITEM)
    layout = json.loads(dashboard.layout_json or "{}")
    curve_pos = layout.get(str(curve.id)) if curve else None
    if not curve_pos:
        return
    height = curve_pos["h"]
    others = [pos for key, pos in layout.items() if key != str(curve.id)]
    in_the_way = [pos for pos in others if CARDS_END <= pos["y"] < CARDS_END + height]
    if curve_pos["y"] == CARDS_END and not in_the_way:
        return
    for pos in others:
        if pos["y"] >= CARDS_END:
            pos["y"] += height
    curve_pos.update(x=0, y=CARDS_END)
    dashboard.layout_json = json.dumps(layout)


def migrate(cr, version):
    """Troca "real" por "realizado" nos textos e sobe a curva S.

    Itens e filtros salvos ficam como estão; do layout, só muda a posição da
    curva S (logo após os cards) e dos gráficos abaixo dela.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    dashboard = env.ref(f"{MODULE}.{DASHBOARD_XMLID}", raise_if_not_found=False)
    if not dashboard:
        return
    for record in [dashboard, *dashboard.item_ids]:
        for field in ("name", "description"):
            if record[field]:
                record[field] = rename_actual(record[field])
    move_s_curve_after_cards(dashboard)
