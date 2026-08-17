# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MgmtsystemNonconformityDocument(models.Model):
    _name = "mgmtsystem.nonconformity.document"
    _description = "Nonconformity Complementary Document"
    _order = "id"

    nonconformity_id = fields.Many2one(
        "mgmtsystem.nonconformity",
        required=True,
        ondelete="cascade",
        index=True,
    )
    document_type = fields.Selection(
        [
            ("calculation_memo", "Calculation Memo"),
            ("revised_project", "Revised Project"),
            ("report", "Report"),
            ("certificate", "Certificate"),
            ("test", "Test"),
            ("as_built", "As Built"),
            ("punch_list", "Punch List"),
            ("other", "Other"),
        ],
        required=True,
        default="report",
    )
    name = fields.Char("Title")
    notes = fields.Text()
    attachment_ids = fields.Many2many(
        "ir.attachment",
        "mgmtsystem_nc_document_attachment_rel",
        "document_id",
        "attachment_id",
        string="Attachments",
    )
    company_id = fields.Many2one(
        related="nonconformity_id.company_id",
        store=True,
    )
