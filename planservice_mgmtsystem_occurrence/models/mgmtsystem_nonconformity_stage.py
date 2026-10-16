# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MgmtsystemNonconformityStage(models.Model):
    _inherit = "mgmtsystem.nonconformity.stage"

    state = fields.Selection(selection="_get_states")

    def _get_states(self):
        # Only the four steps of the occurrence flow are offered. The keys are
        # kept on purpose: draft and done are also used by the base module, and
        # waiting_supplier / waiting_verification are referenced across the
        # module. "open" was merged into waiting_supplier and "cancel" is gone.
        return [
            ("draft", self.env._("Inspetor (abertura)")),
            ("waiting_supplier", self.env._("Fornecedor (aguardando)")),
            ("waiting_verification", self.env._("Inspetor (fechamento)")),
            ("done", self.env._("Encerrada")),
        ]
