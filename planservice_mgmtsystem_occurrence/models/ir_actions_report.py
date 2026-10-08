# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import UserError
from odoo.tools.pdf import merge_pdf

OCCURRENCE_REPORT_NAME = "mgmtsystem_nonconformity.report_mgmtsystem_nonconformity"
OCCURRENCE_OFFICIAL_REPORT_NAME = (
    "planservice_mgmtsystem_occurrence.report_occurrence_official"
)


class IrActionsReport(models.Model):
    _inherit = "ir.actions.report"

    def _occurrence_report_in_user_lang(self, report_ref):
        """Render the occurrence report in the user's language.

        An HTTP print request carries its own ``lang`` in the context, which
        is not necessarily the user's, so the report would come out in English.
        """
        report = self._get_report(report_ref)
        if report.report_name != OCCURRENCE_REPORT_NAME:
            return self
        return self.with_context(lang=self.env.user.lang)

    def _render_qweb_html(self, report_ref, docids, data=None):
        report = self._occurrence_report_in_user_lang(report_ref)
        return super(IrActionsReport, report)._render_qweb_html(
            report_ref, docids, data=data
        )

    def _render_occurrence_official(self, res_ids):
        """Official print: the frozen document of the last decided revision."""
        records = self.env["mgmtsystem.nonconformity"].browse(res_ids)
        contents = []
        for rec in records:
            snapshot = rec.revision_ids[:1]
            if not snapshot:
                raise UserError(
                    self.env._(
                        "The official print is only available after the first "
                        "decision (approval or rejection). Use the draft print."
                    )
                )
            contents.append(snapshot.sudo().attachment_id.raw)
        return contents[0] if len(contents) == 1 else merge_pdf(contents)

    def _render_qweb_pdf(self, report_ref, res_ids=None, data=None):
        if self._get_report(report_ref).report_name == OCCURRENCE_OFFICIAL_REPORT_NAME:
            return self._render_occurrence_official(res_ids), "pdf"
        report = self._occurrence_report_in_user_lang(report_ref)
        return super(IrActionsReport, report)._render_qweb_pdf(
            report_ref, res_ids=res_ids, data=data
        )
