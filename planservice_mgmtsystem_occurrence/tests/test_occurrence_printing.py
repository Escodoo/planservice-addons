# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError
from odoo.tests import tagged

from ..models.ir_actions_report import (
    OCCURRENCE_OFFICIAL_REPORT_NAME,
    OCCURRENCE_REPORT_NAME,
)
from .common import OccurrenceTestCase

WATERMARK = b"DRAFT - UNCONTROLLED"


@tagged("post_install", "-at_install")
class TestOccurrencePrinting(OccurrenceTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Print Supplier", "is_company": True}
        )
        cls.nc = cls.env["mgmtsystem.nonconformity"].create(
            {
                "name": "Printing occurrence",
                "partner_id": cls.partner.id,
                "manager_user_id": cls.env.user.id,
                "description": "Original description.",
                "classification": "nc",
            }
        )

    def _reject_revision_zero(self):
        self.nc.action_release_to_supplier()
        self.env["mgmtsystem.action"].create(
            {"name": "Fix", "type_action": "correction", "user_id": self.env.user.id}
        )
        self.nc.write(
            {
                "containment_text": "Contained.",
                "cause_justification": "Cause.",
                "disposition": "conclude",
            }
        )
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Not accepted."
        self.nc.action_reject()

    def _official(self, nc=None):
        nc = nc or self.nc
        content, kind = self.env["ir.actions.report"]._render_qweb_pdf(
            OCCURRENCE_OFFICIAL_REPORT_NAME, nc.ids
        )
        self.assertEqual(kind, "pdf")
        return content

    def _draft(self, nc=None):
        nc = nc or self.nc
        html, _kind = self.env["ir.actions.report"]._render_qweb_html(
            OCCURRENCE_REPORT_NAME, nc.ids
        )
        return html

    def test_both_prints_are_bound_to_the_model(self):
        names = (
            self.env["ir.actions.report"]
            .search(
                [
                    ("binding_model_id.model", "=", "mgmtsystem.nonconformity"),
                    (
                        "report_name",
                        "in",
                        [
                            OCCURRENCE_REPORT_NAME,
                            OCCURRENCE_OFFICIAL_REPORT_NAME,
                        ],
                    ),
                ]
            )
            .mapped("name")
        )
        self.assertCountEqual(
            names, ["Occurrence Record - Draft", "Occurrence Record - Official"]
        )

    def test_official_is_unavailable_before_the_first_decision(self):
        with self.assertRaises(UserError):
            self._official()

    def test_draft_carries_the_watermark_and_live_data(self):
        html = self._draft()
        self.assertIn(WATERMARK, html)
        self.assertIn(b"Original description.", html)

    def test_official_prints_the_last_decided_revision_without_watermark(self):
        self._reject_revision_zero()
        self.nc.description = "Edited in revision 01."
        official = self._official()
        self.assertEqual(official, self.nc.revision_ids.attachment_id.raw)
        self.assertNotIn(WATERMARK, official)
        self.assertIn(b"Original description.", official)
        self.assertNotIn(b"Edited in revision 01.", official)

    def test_draft_shows_the_revision_in_progress(self):
        self._reject_revision_zero()
        self.nc.description = "Edited in revision 01."
        html = self._draft()
        self.assertIn(WATERMARK, html)
        self.assertIn(b"Edited in revision 01.", html)

    def test_official_filename_names_the_decided_revision(self):
        self._reject_revision_zero()
        self.assertEqual(
            self.nc.get_occurrence_report_filename(official=True),
            f"Occurrence Record - {self.nc.ref} - 00",
        )
