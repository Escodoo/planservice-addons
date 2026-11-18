# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import api, models


class OccurrenceAttachmentMixin(models.AbstractModel):
    """Stamp the occurrence revision on the files linked to a record.

    The record needs ``nonconformity_id`` and ``attachment_ids``. The revision
    of a file is the one in force when it was first attached.
    """

    _name = "mgmtsystem.occurrence.attachment.mixin"
    _description = "Occurrence Attachment Revision Mixin"

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for rec in records:
            rec.attachment_ids._stamp_occurrence_revision(rec.nonconformity_id.revision)
        return records

    def write(self, vals):
        result = super().write(vals)
        if "attachment_ids" in vals:
            for rec in self:
                rec.attachment_ids._stamp_occurrence_revision(
                    rec.nonconformity_id.revision
                )
        return result
