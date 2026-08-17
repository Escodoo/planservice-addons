# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class MgmtsystemNonconformity(models.Model):
    _name = "mgmtsystem.nonconformity"
    _inherit = ["mgmtsystem.nonconformity", "portal.mixin"]

    def _compute_access_url(self):
        result = super()._compute_access_url()
        for rec in self:
            rec.access_url = f"/my/occurrences/{rec.id}"
        return result

    def _get_access_action(self, access_uid=None, force_website=False):
        self.ensure_one()
        user = (
            self.env["res.users"].sudo().browse(access_uid)
            if access_uid
            else self.env.user
        )
        if force_website or user.share:
            self.sudo()._portal_ensure_token()
            return {
                "type": "ir.actions.act_url",
                "url": self.access_url,
                "target": "self",
                "res_model": self._name,
                "res_id": self.id,
            }
        return super()._get_access_action(
            access_uid=access_uid, force_website=force_website
        )

    def action_release_to_supplier(self):
        result = super().action_release_to_supplier()
        self._portal_ensure_token()
        return result
