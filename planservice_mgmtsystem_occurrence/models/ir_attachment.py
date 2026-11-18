# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import fields, models
from odoo.exceptions import UserError

CONTENT_FIELDS = {"raw", "datas", "db_datas", "store_fname", "checksum", "name"}


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    # Revision of the occurrence in which the file was first attached.
    occurrence_revision = fields.Char(copy=False, readonly=True)

    def _stamp_occurrence_revision(self, revision):
        """Keep the revision of the first attachment; later links do not change it."""
        self.filtered(lambda att: not att.occurrence_revision).write(
            {"occurrence_revision": revision}
        )

    def _check_not_revision_snapshot(self, vals=None):
        if self.env.context.get("module_uninstall") or not self.ids:
            return
        if vals is not None and not CONTENT_FIELDS & set(vals):
            return
        # Snapshots always belong to their occurrence.
        occurrence_files = self.filtered(
            lambda att: att.res_model == "mgmtsystem.nonconformity"
        )
        if not occurrence_files:
            return
        snapshots = (
            self.env["mgmtsystem.nonconformity.revision"]
            .sudo()
            .search_count([("attachment_id", "in", occurrence_files.ids)], limit=1)
        )
        if snapshots:
            raise UserError(
                self.env._("The document of a revision snapshot cannot be changed.")
            )

    def write(self, vals):
        self._check_not_revision_snapshot(vals)
        return super().write(vals)

    def unlink(self):
        self._check_not_revision_snapshot()
        return super().unlink()
