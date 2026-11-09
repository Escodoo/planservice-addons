# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_employers_calc_dashboard.hooks import post_init_hook


def migrate(cr, version):
    """Recria o dashboard com os itens novos (previsto e desvio até hoje e o
    gráfico semanal).

    O dashboard só é criado na instalação (post_init_hook) e o xmlid é
    noupdate, então atualizar o módulo não traria os itens novos. O hook apaga
    o dashboard do módulo e importa de novo o JSON; os filtros salvos pelos
    usuários são perdidos, e o botão do projeto grava o filtro de novo.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    post_init_hook(env)
