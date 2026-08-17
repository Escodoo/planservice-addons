# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models


class MgmtsystemNonconformityStage(models.Model):
    _inherit = "mgmtsystem.nonconformity.stage"

    def _get_states(self):
        states = super()._get_states()
        extra = {
            "draft": ("waiting_supplier", self.env._("Waiting Supplier")),
            "open": ("waiting_verification", self.env._("Waiting Verification")),
        }
        result = []
        for key, label in states:
            result.append((key, label))
            if key in extra:
                result.append(extra[key])
        return result
