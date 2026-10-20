# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import models


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    def _compute_views(self):
        """Open in list view the actions that would open in kanban.

        Only kanban is replaced: an action that opens in another view (a form,
        a calendar, a report) does so on purpose.
        """
        res = super()._compute_views()
        for act in self:
            views = act.views
            if not views or views[0][1] != "kanban":
                continue
            list_index = next(
                (index for index, view in enumerate(views) if view[1] == "list"), 0
            )
            if list_index:
                act.views = (
                    [views[list_index]] + views[:list_index] + views[list_index + 1 :]
                )
        return res
