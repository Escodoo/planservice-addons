# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    @api.depends("view_ids.view_mode", "view_mode", "view_id.type")
    def _compute_views(self):
        """Put the list view first so it is the one the action opens with."""
        res = super()._compute_views()
        for act in self:
            views = act.views
            list_index = next(
                (index for index, view in enumerate(views) if view[1] == "list"), 0
            )
            if list_index:
                act.views = (
                    [views[list_index]] + views[:list_index] + views[list_index + 1 :]
                )
        return res
