# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import io
import zipfile
from unittest.mock import patch

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

    def _reject_revision_zero(self, nc=None):
        nc = nc or self.nc
        nc.action_release_to_supplier()
        self.env["mgmtsystem.action"].create(
            {"name": "Fix", "type_action": "correction", "user_id": self.env.user.id}
        )
        nc.write(
            {
                "containment_text": "Contained.",
                "cause_justification": "Cause.",
                "disposition": "conclude",
            }
        )
        nc.action_submit_response()
        nc.evaluation_comments = "Not accepted."
        nc.action_reject()

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
            f"{self.nc.ref} - 00",
        )

    def test_decision_attachment_carries_the_project_name(self):
        project = self.env["project.project"].create({"name": "Projeto Norte Sul"})
        self.nc.project_id = project
        self._reject_revision_zero()
        attachment = self.nc.revision_ids[:1].attachment_id
        self.assertEqual(
            attachment.name,
            f"ProjetoNorteSul - {self.nc.ref} - 00.pdf",
        )

    def test_filename_puts_project_code_and_name_without_spaces(self):
        if "code" not in self.env["project.project"]._fields:
            self.skipTest("project.project has no code field in this database")
        project = self.env["project.project"].create(
            {"name": "Projeto Norte Sul", "code": "PXXX"}
        )
        self.nc.project_id = project
        self.assertEqual(
            self.nc.get_occurrence_report_filename(),
            f"(Draft) - PXXXProjetoNorteSul - {self.nc.ref}",
        )

    def test_filename_without_code_keeps_only_the_project_name(self):
        project = self.env["project.project"].create({"name": "Projeto Norte Sul"})
        self.nc.project_id = project
        self.assertEqual(
            self.nc.get_occurrence_report_filename(),
            f"(Draft) - ProjetoNorteSul - {self.nc.ref}",
        )

    def test_official_print_of_several_records_merges_their_snapshots(self):
        other = self.nc.copy({"name": "Second printing occurrence"})
        self._reject_revision_zero()
        self._reject_revision_zero(other)
        merge = "odoo.addons.planservice_mgmtsystem_occurrence.models.ir_actions_report"
        with patch(f"{merge}.merge_pdf", return_value=b"merged") as merge_pdf:
            content = self._official(self.nc | other)
        self.assertEqual(content, b"merged")
        merged = merge_pdf.call_args.args[0]
        self.assertEqual(
            merged,
            [
                self.nc.revision_ids.attachment_id.raw,
                other.revision_ids.attachment_id.raw,
            ],
        )

    def test_other_reports_keep_the_request_language(self):
        other = self.env["ir.actions.report"].search(
            [
                (
                    "report_name",
                    "not in",
                    [OCCURRENCE_REPORT_NAME, OCCURRENCE_OFFICIAL_REPORT_NAME],
                )
            ],
            limit=1,
        )
        report = self.env["ir.actions.report"].with_context(lang="en_US")
        same = report._occurrence_report_in_user_lang(other.report_name)
        self.assertEqual(same.env.context["lang"], "en_US")

    def test_evidence_image_renders_in_the_report(self):
        attachment = self.env["ir.attachment"].create(
            {
                "name": "axis.png",
                "datas": (
                    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
                    "YPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
                ),
                "mimetype": "image/png",
            }
        )
        self.env["mgmtsystem.nonconformity.evidence"].create(
            {
                "nonconformity_id": self.nc.id,
                "section": "supplier",
                "name": "Axis photo",
                "evidence_type": "photo",
                "attachment_ids": [(6, 0, attachment.ids)],
            }
        )
        html = self.env["ir.actions.report"]._render_qweb_html(
            OCCURRENCE_REPORT_NAME, self.nc.ids
        )[0]
        self.assertIn(b"data:image/png;base64,", html)

    def test_attachments_are_packed_into_one_zip(self):
        photo = self.env["ir.attachment"].create(
            {"name": "axis.jpg", "raw": b"photo-bytes", "mimetype": "image/jpeg"}
        )
        report = self.env["ir.attachment"].create(
            {"name": "lab.pdf", "raw": b"report-bytes", "mimetype": "application/pdf"}
        )
        self.env["mgmtsystem.nonconformity.evidence"].create(
            {
                "nonconformity_id": self.nc.id,
                "section": "supplier",
                "name": "Axis photo",
                "evidence_type": "photo",
                "attachment_ids": [(6, 0, photo.ids)],
            }
        )
        self.env["mgmtsystem.nonconformity.document"].create(
            {
                "nonconformity_id": self.nc.id,
                "document_type": "report",
                "name": "Lab report",
                "attachment_ids": [(6, 0, report.ids)],
            }
        )
        zip_attachment = self.nc._create_attachments_zip()
        self.assertEqual(
            zip_attachment.name,
            f"{self.nc.ref} - {self.nc.revision} - anexos.zip",
        )
        self.assertEqual(
            (zip_attachment.res_model, zip_attachment.res_id),
            (self.nc._name, self.nc.id),
        )
        with zipfile.ZipFile(io.BytesIO(zip_attachment.raw)) as archive:
            self.assertEqual(
                sorted(archive.namelist()), ["rev00-axis.jpg", "rev00-lab.pdf"]
            )
            self.assertEqual(archive.read("rev00-axis.jpg"), b"photo-bytes")
            self.assertEqual(archive.read("rev00-lab.pdf"), b"report-bytes")

    def test_no_zip_without_attachments(self):
        self.assertFalse(self.nc._create_attachments_zip())

    def test_zip_prefix_is_the_revision_where_each_file_was_attached(self):
        first = self.env["ir.attachment"].create(
            {"name": "axis.jpg", "raw": b"first", "mimetype": "image/jpeg"}
        )
        self.env["mgmtsystem.nonconformity.evidence"].create(
            {
                "nonconformity_id": self.nc.id,
                "section": "supplier",
                "name": "Axis photo",
                "evidence_type": "photo",
                "attachment_ids": [(6, 0, first.ids)],
            }
        )
        self.nc._bump_revision()
        second = self.env["ir.attachment"].create(
            {"name": "lab.pdf", "raw": b"second", "mimetype": "application/pdf"}
        )
        self.env["mgmtsystem.nonconformity.document"].create(
            {
                "nonconformity_id": self.nc.id,
                "document_type": "report",
                "name": "Lab report",
                "attachment_ids": [(6, 0, second.ids)],
            }
        )
        self.assertEqual(self.nc.revision, "01")
        zip_attachment = self.nc._create_attachments_zip()
        with zipfile.ZipFile(io.BytesIO(zip_attachment.raw)) as archive:
            self.assertEqual(
                sorted(archive.namelist()), ["rev00-axis.jpg", "rev01-lab.pdf"]
            )

    def test_snapshot_is_rendered_with_the_draft_paper_format(self):
        draft = self.env.ref(
            "planservice_mgmtsystem_occurrence.action_occurrence_report_draft"
        )
        report_model = type(self.env["ir.actions.report"])
        original = report_model._render_qweb_pdf
        with patch.object(
            report_model, "_render_qweb_pdf", autospec=True, side_effect=original
        ) as render:
            self.nc._create_revision_snapshot("rejected")
        self.assertEqual(render.call_args.args[1], draft.id)

    def test_base_release_link_is_empty_without_the_portal(self):
        from ..models.mgmtsystem_nonconformity import MgmtsystemNonconformity

        self.assertEqual(
            MgmtsystemNonconformity._supplier_portal_link_html(self.nc), ""
        )

    def test_zip_keeps_files_with_the_same_name_apart(self):
        same_name = {"name": "photo.jpg", "raw": b"one", "mimetype": "image/jpeg"}
        first = self.env["ir.attachment"].create(same_name)
        second = self.env["ir.attachment"].create(dict(same_name, raw=b"two"))
        for attachment in (first, second):
            self.env["mgmtsystem.nonconformity.evidence"].create(
                {
                    "nonconformity_id": self.nc.id,
                    "section": "supplier",
                    "name": "Photo",
                    "evidence_type": "photo",
                    "attachment_ids": [(6, 0, attachment.ids)],
                }
            )
        zip_attachment = self.nc._create_attachments_zip()
        with zipfile.ZipFile(io.BytesIO(zip_attachment.raw)) as archive:
            names = sorted(archive.namelist())
        self.assertEqual(len(names), 2)
        self.assertIn("rev00-photo.jpg", names)
        self.assertIn(f"{second.id}-rev00-photo.jpg", names)

    def test_document_attachment_added_later_is_stamped_with_the_revision(self):
        document = self.env["mgmtsystem.nonconformity.document"].create(
            {"nonconformity_id": self.nc.id, "document_type": "report", "name": "Lab"}
        )
        attachment = self.env["ir.attachment"].create(
            {"name": "lab.pdf", "raw": b"lab", "mimetype": "application/pdf"}
        )
        document.write({"attachment_ids": [(6, 0, attachment.ids)]})
        self.assertEqual(attachment.occurrence_revision, "00")
