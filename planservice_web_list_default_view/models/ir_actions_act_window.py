# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class IrActionsActWindow(models.Model):
    _inherit = "ir.actions.act_window"

    @api.depends("view_ids.view_mode", "view_mode", "view_id.type")
    def _compute_views(self):
        """Put the list view first so it is the one the action opens with."""
        res = super()._compute_views()
        for act in self:
            views = act.views
            list_views = [view for view in views if view[1] == "list"]
            if list_views and views[0][1] != "list":
                act.views = list_views[:1] + [
                    view for view in views if view is not list_views[0]
                ]
        return res
