# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models

from ..models.occurrence_selection import CLASSIFICATION_SELECTION


class MgmtsystemNonconformityReclassify(models.TransientModel):
    _name = "mgmtsystem.nonconformity.reclassify"
    _description = "Reclassify Occurrence"

    nonconformity_id = fields.Many2one(
        "mgmtsystem.nonconformity",
        required=True,
        ondelete="cascade",
    )
    classification = fields.Selection(CLASSIFICATION_SELECTION, required=True)
    note = fields.Text("Inspector Comments")

    def action_reclassify(self):
        self.ensure_one()
        self.nonconformity_id.action_reclassify(self.classification, self.note)
        return {"type": "ir.actions.act_window_close"}
