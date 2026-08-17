# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MgmtsystemNonconformityEvidence(models.Model):
    _name = "mgmtsystem.nonconformity.evidence"
    _description = "Nonconformity Evidence"
    _order = "date desc, id desc"

    nonconformity_id = fields.Many2one(
        "mgmtsystem.nonconformity",
        required=True,
        ondelete="cascade",
        index=True,
    )
    section = fields.Selection(
        [
            ("inspector", "Inspector"),
            ("supplier", "Supplier"),
        ],
        required=True,
        default="inspector",
    )
    evidence_type = fields.Selection(
        [
            ("photo", "Photographs"),
            ("measurement", "Measurements"),
            ("sketch", "Sketch"),
            ("document", "Document"),
            ("report", "Report / Test"),
            ("other", "Other"),
        ],
        required=True,
        default="photo",
    )
    name = fields.Char("Title", required=True)
    date = fields.Date(default=fields.Date.context_today)
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mgmtsystem_nc_evidence_attachment_rel",
        "evidence_id",
        "attachment_id",
        string="Attachments",
    )
    value = fields.Char()
    uom = fields.Char("Unit")
    method = fields.Char("Method / Equipment")
    notes = fields.Text()
    company_id = fields.Many2one(
        related="nonconformity_id.company_id",
        store=True,
    )
