# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError

CONTENT_FIELDS = {"raw", "datas", "db_datas", "store_fname", "checksum", "name"}


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def _check_not_revision_snapshot(self, vals=None):
        if self.env.context.get("module_uninstall") or not self.ids:
            return
        if vals is not None and not CONTENT_FIELDS & set(vals):
            return
        snapshots = (
            self.env["mgmtsystem.nonconformity.revision"]
            .sudo()
            .search_count([("attachment_id", "in", self.ids)], limit=1)
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
