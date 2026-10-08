# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.exceptions import UserError


class MgmtsystemNonconformityRevision(models.Model):
    """Frozen copy of a decided revision of an occurrence record.

    Created once, when a revision is approved or rejected. It is read-only for
    everyone, including administrators, so it can back an audit trail.
    """

    _name = "mgmtsystem.nonconformity.revision"
    _description = "Occurrence Revision Snapshot"
    _order = "nonconformity_id, revision desc, id desc"
    _rec_name = "revision"

    nonconformity_id = fields.Many2one(
        "mgmtsystem.nonconformity",
        required=True,
        ondelete="restrict",
        index=True,
        readonly=True,
    )
    revision = fields.Char(required=True, readonly=True)
    result = fields.Selection(
        [
            ("approved", "Approved and Released"),
            ("approved_with_comments", "Approved with Comments"),
            ("rejected", "Rejected"),
        ],
        required=True,
        readonly=True,
    )
    user_id = fields.Many2one(
        "res.users",
        "Decided By",
        required=True,
        readonly=True,
        default=lambda self: self.env.user,
    )
    decision_date = fields.Datetime(
        required=True,
        readonly=True,
        default=fields.Datetime.now,
    )
    attachment_id = fields.Many2one(
        "ir.attachment",
        "Document",
        required=True,
        ondelete="restrict",
        readonly=True,
    )
    company_id = fields.Many2one(
        related="nonconformity_id.company_id",
        store=True,
    )

    def write(self, vals):
        if vals:
            raise UserError(self.env._("Revision snapshots cannot be modified."))
        return super().write(vals)

    def unlink(self):
        if not self.env.context.get("module_uninstall"):
            raise UserError(self.env._("Revision snapshots cannot be deleted."))
        return super().unlink()
