# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class TimesheetAttachmentWizard(models.TransientModel):
    _name = "timesheet.attachment.wizard"
    _description = "Timesheet Attachment Wizard"

    line_id = fields.Many2one(
        comodel_name="account.analytic.line",
        required=True,
        ondelete="cascade",
    )
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Attachments",
    )

    def action_attach(self):
        self.ensure_one()
        self.line_id.attachment_ids |= self.attachment_ids
        return {"type": "ir.actions.act_window_close"}
