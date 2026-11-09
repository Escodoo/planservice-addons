# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from itertools import accumulate

from odoo import fields, models

from odoo.addons.boardkit_dashboard.models.boardkit_dashboard_item import (
    BoardkitDashboardItem,
)


class BoardkitDashboardItemCumulative(models.Model):
    _inherit = "boardkit.dashboard.item"

    # entra no export/import, para o JSON do dashboard poder ligar a opção
    _EXPORT_SIMPLE_FIELDS = BoardkitDashboardItem._EXPORT_SIMPLE_FIELDS + ["cumulative"]

    cumulative = fields.Boolean(
        help="Mostra cada série somando os grupos anteriores (ex.: curva S com "
        "o custo acumulado mês a mês). Os filtros do dashboard continuam valendo."
    )

    def _get_chart_data(self, params):
        data = super()._get_chart_data(params)
        if self.cumulative:
            for dataset in data["datasets"]:
                dataset["data"] = list(accumulate(dataset["data"]))
        return data
