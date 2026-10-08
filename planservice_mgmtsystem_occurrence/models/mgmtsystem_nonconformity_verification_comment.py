# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MgmtsystemNonconformityVerificationComment(models.Model):
    _name = "mgmtsystem.nonconformity.verification.comment"
    _description = "Occurrence Verification Comment"
    _order = "id"

    nonconformity_id = fields.Many2one(
        "mgmtsystem.nonconformity",
        required=True,
        ondelete="cascade",
        index=True,
    )
    revision = fields.Char(
        default=lambda self: self.env.context.get("default_revision"),
        readonly=True,
    )
    name = fields.Text("Comment")
    user_id = fields.Many2one("res.users", "Responsible")
    deadline = fields.Date()
    company_id = fields.Many2one(
        related="nonconformity_id.company_id",
        store=True,
    )

    def _is_complete(self):
        self.ensure_one()
        return bool(self.name and self.user_id and self.deadline)
