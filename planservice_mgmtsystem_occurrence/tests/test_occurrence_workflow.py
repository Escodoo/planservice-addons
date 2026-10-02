# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import Mock

from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import OccurrenceTestCase


@tagged("post_install", "-at_install")
class TestOccurrenceWorkflow(OccurrenceTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Supplier Partner", "is_company": True}
        )
        cls.project = cls.env["project.project"].create({"name": "Work P001"})
        cls.origin = cls.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence"
        )
        cls.nc = cls._create_occurrence()

    @classmethod
    def _create_occurrence(cls, **extra):
        vals = {
            "name": "Column out of plumb",
            "partner_id": cls.partner.id,
            "project_id": cls.project.id,
            "manager_user_id": cls.env.user.id,
            "responsible_user_id": cls.env.user.id,
            "description": "Expected plumb column, found 15mm deviation.",
            "origin_ids": [(6, 0, cls.origin.ids)],
            "classification": "nc",
            "work_division": "superstructure",
            "priority": "high",
        }
        vals.update(extra)
        return cls.env["mgmtsystem.nonconformity"].create(vals)

    def _fill_supplier_response(self, nc, disposition="correct"):
        action = self.env["mgmtsystem.action"].create(
            {
                "name": "Realign the column",
                "type_action": "correction",
                "user_id": self.env.user.id,
            }
        )
        nc.write(
            {
                "containment_text": "Area isolated and work suspended.",
                "cause_justification": "Formwork was not checked before pouring.",
                "disposition": disposition,
                "action_ids": [(4, action.id)],
            }
        )
        return action

    def _force_tier_validated(self, nc):
        if "review_ids" not in nc._fields:
            return
        nc.invalidate_recordset(["review_ids", "validation_status", "need_validation"])
        if not nc.review_ids and hasattr(nc, "request_validation"):
            nc.request_validation()
            nc.invalidate_recordset(["review_ids"])
        if nc.review_ids:
            nc.review_ids.write({"status": "approved", "done_by": self.env.user.id})
            nc.invalidate_recordset(["validation_status", "need_validation"])

    def _clear_tier_reviews(self, nc):
        if "review_ids" in nc._fields and nc.review_ids:
            nc.review_ids.unlink()

    def test_tier_helpers_approve_and_clear_reviews(self):
        reviews = Mock()
        reviews.__bool__ = lambda _self: True
        nc = Mock()
        nc._fields = {"review_ids": True}
        nc.review_ids = self.env["res.partner"]
        nc.request_validation = Mock()
        self._force_tier_validated(nc)
        nc.request_validation.assert_called_once()
        nc.review_ids = reviews
        self._force_tier_validated(nc)
        reviews.write.assert_called_once_with(
            {"status": "approved", "done_by": self.env.user.id}
        )
        self._clear_tier_reviews(nc)
        reviews.unlink.assert_called_once()
        self._force_tier_validated(self.nc)
        self._clear_tier_reviews(self.nc)

    def test_release_requires_classification(self):
        nc = self._create_occurrence(classification=False)
        with self.assertRaises(UserError):
            nc.action_release_to_supplier()

    def test_release_requires_description_and_partner(self):
        draft = self.env.ref("mgmtsystem_nonconformity.stage_draft")
        missing_description = self.env["mgmtsystem.nonconformity"].new(
            {
                "name": "Incomplete description",
                "classification": "nc",
                "description": False,
                "partner_id": self.partner.id,
                "stage_id": draft.id,
                "manager_user_id": self.env.user.id,
                "responsible_user_id": self.env.user.id,
            }
        )
        with self.assertRaises(UserError):
            missing_description._check_can_release()
        missing_partner = self.env["mgmtsystem.nonconformity"].new(
            {
                "name": "Incomplete partner",
                "classification": "nc",
                "description": "Observed deviation.",
                "partner_id": False,
                "stage_id": draft.id,
                "manager_user_id": self.env.user.id,
                "responsible_user_id": self.env.user.id,
            }
        )
        with self.assertRaises(UserError):
            missing_partner._check_can_release()

    def test_release_and_submit_and_approve(self):
        self.nc.action_release_to_supplier()
        self.assertEqual(self.nc.state, "waiting_supplier")
        action = self._fill_supplier_response(self.nc)
        self.assertEqual(self.nc.state, "open")
        self.nc.action_submit_response()
        self.assertEqual(self.nc.state, "waiting_verification")
        self.nc.evaluation_comments = "Condition restored, released."
        close_stage = self.env.ref("mgmtsystem_action.stage_close")
        action.stage_id = close_stage
        self._force_tier_validated(self.nc)
        self.nc.action_approve()
        self.assertEqual(self.nc.state, "waiting_verification")
        self.assertEqual(self.nc.verification_result, "approved")
        self.nc.action_close()
        self.assertEqual(self.nc.state, "done")
        self.assertEqual(self.nc.closure_decision, "close")

    def test_submit_requires_containment(self):
        self.nc.action_release_to_supplier()
        with self.assertRaises(UserError):
            self.nc.action_submit_response()

    def test_reject_returns_to_inspector(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Rework is incomplete."
        self.nc.action_reject()
        self.assertEqual(self.nc.state, "draft")
        self.assertEqual(self.nc.revision_ids.result, "rejected")
        self.assertFalse(self.nc.verification_result)
        self.assertFalse(self.nc.evaluation_comments)
        self.assertEqual(self.nc.rejection_opinion, "Rework is incomplete.")

    def test_supplier_cannot_edit_after_rejection(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Rework is incomplete."
        self.nc.action_reject()
        portal_user = self.env["res.users"].create(
            {
                "name": "Supplier Portal",
                "login": "supplier.portal.reject",
                "groups_id": [(6, 0, [self.env.ref("base.group_portal").id])],
            }
        )
        with self.assertRaises(AccessError):
            self.nc.with_user(portal_user).write({"containment_text": "Late edit"})

    def test_supplier_response_is_prefilled_in_the_next_revision(self):
        self.nc.action_release_to_supplier()
        action = self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Rework is incomplete."
        self.nc.action_reject()
        self.assertEqual(self.nc.containment_text, "Area isolated and work suspended.")
        self.assertEqual(self.nc.disposition, "correct")
        self.assertIn(action, self.nc.action_ids)

    def test_revision_cycle_reject_edit_and_release_again(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Description is ambiguous."
        self.nc.action_reject()
        self.assertEqual((self.nc.state, self.nc.revision), ("draft", "01"))
        self.nc.write({"description": "Clarified: 15mm deviation on axis B3."})
        self.nc.action_release_to_supplier()
        self.assertEqual(self.nc.state, "waiting_supplier")
        self.assertEqual(self.nc.revision, "01")
        self.assertEqual(self.nc.description, "Clarified: 15mm deviation on axis B3.")
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Still incomplete."
        self.nc.action_reject()
        self.assertEqual(self.nc.revision, "02")
        self.assertEqual(self.nc.revision_ids.mapped("revision"), ["01", "00"])

    def test_revision_starts_at_zero(self):
        self.assertEqual(self.nc.revision, "00")
        self.assertEqual(self.nc.revision_number, 0)

    def test_revision_cannot_be_edited(self):
        with self.assertRaises(UserError):
            self.nc.write({"revision": "07"})
        with self.assertRaises(UserError):
            self.nc.write({"revision_number": 7})
        self.assertEqual(self.nc.revision, "00")

    def test_reject_bumps_revision_and_keeps_reference(self):
        ref = self.nc.ref
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Rework is incomplete."
        self.nc.action_reject()
        self.assertEqual(self.nc.revision, "01")
        self.assertEqual(self.nc.ref, ref)

    def test_reject_creates_snapshot_of_the_rejected_revision(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Rework is incomplete."
        self.nc.action_reject()
        snapshot = self.nc.revision_ids
        self.assertEqual(len(snapshot), 1)
        self.assertEqual(snapshot.revision, "00")
        self.assertEqual(snapshot.result, "rejected")
        self.assertEqual(snapshot.user_id, self.env.user)
        self.assertTrue(snapshot.decision_date)
        self.assertTrue(snapshot.attachment_id.raw)
        self.assertEqual(self.nc.revision, "01")

    def test_close_creates_snapshot(self):
        action = self._to_waiting_verification("Condition restored, released.")
        action.stage_id = self.env.ref("mgmtsystem_action.stage_close")
        self._force_tier_validated(self.nc)
        self.nc.action_approve()
        self.assertFalse(self.nc.revision_ids)
        self.nc.action_close()
        self.assertEqual(self.nc.revision_ids.result, "approved")
        self.assertEqual(self.nc.revision_ids.revision, "00")

    def test_snapshot_is_immutable_even_for_admin(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Rework is incomplete."
        self.nc.action_reject()
        admin = self.env.ref("base.user_admin")
        snapshot = self.nc.revision_ids.with_user(admin).sudo()
        with self.assertRaises(UserError):
            snapshot.write({"revision": "99"})
        with self.assertRaises(UserError):
            snapshot.unlink()
        with self.assertRaises(UserError):
            snapshot.attachment_id.write({"raw": b"tampered"})
        with self.assertRaises(UserError):
            snapshot.attachment_id.unlink()

    def test_snapshot_survives_editing_the_next_revision(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Rework is incomplete."
        self.nc.action_reject()
        before = self.nc.revision_ids.attachment_id.raw
        self.nc.description = "Description corrected in revision 01."
        self.assertEqual(self.nc.revision_ids.attachment_id.raw, before)

    def test_reclassify_returns_to_draft(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self._clear_tier_reviews(self.nc)
        self.nc.action_reclassify("observation", "Reclassified after field review.")
        self.assertEqual(self.nc.state, "draft")
        self.assertEqual(self.nc.classification, "observation")
        self.assertEqual(self.nc.closure_decision, "reclassify")

    def test_stop_work_requires_date(self):
        with self.assertRaises(ValidationError):
            self._create_occurrence(
                classification="stop_work",
                stop_work=True,
                stop_work_date=False,
            )

    def test_work_division_other_requires_text(self):
        with self.assertRaises(ValidationError):
            self._create_occurrence(work_division="other", work_division_other=False)

    def test_approve_requires_evaluation(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        with self.assertRaises(UserError):
            self.nc.action_approve()

    def test_occurrence_report_renders(self):
        html, _report_type = (
            self.env["ir.actions.report"]
            .with_context(lang="en_US")
            ._render_qweb_html(
                "mgmtsystem_nonconformity.report_mgmtsystem_nonconformity",
                self.nc.ids,
            )
        )
        self.assertIn(self.nc.ref.encode(), html)
        self.assertIn(b"o-ro-page", html)
        self.assertIn(b"o-ro-title", html)

    def test_release_only_from_draft(self):
        self.nc.action_release_to_supplier()
        with self.assertRaises(UserError):
            self.nc.action_release_to_supplier()

    def test_submit_requires_cause_disposition_and_actions(self):
        self.nc.action_release_to_supplier()
        self.nc.containment_text = "Isolated."
        with self.assertRaises(UserError):
            self.nc.action_submit_response()
        self.nc.cause_justification = "Formwork failure."
        with self.assertRaises(UserError):
            self.nc.action_submit_response()
        self.nc.disposition = "correct"
        with self.assertRaises(UserError):
            self.nc.action_submit_response()

    def test_submit_conclude_without_actions(self):
        self.nc.action_release_to_supplier()
        self.nc.write(
            {
                "containment_text": "No intervention needed.",
                "cause_justification": "Within tolerance after remeasure.",
                "disposition": "conclude",
            }
        )
        self.nc.action_submit_response()
        self.assertEqual(self.nc.state, "waiting_verification")
        self.assertTrue(self.nc.supplier_response_date)

    def test_submit_from_draft_is_blocked(self):
        with self.assertRaises(UserError):
            self.nc.action_submit_response()

    def _to_waiting_verification(self, opinion="Inspector opinion."):
        self.nc.action_release_to_supplier()
        action = self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = opinion
        return action

    def _add_comment(self, **extra):
        vals = {
            "nonconformity_id": self.nc.id,
            "name": "Repaint the touched-up area.",
            "user_id": self.env.user.id,
            "deadline": "2031-02-01",
        }
        vals.update(extra)
        return self.env["mgmtsystem.nonconformity.verification.comment"].create(vals)

    def test_approve_with_comments_requires_a_comment(self):
        self._to_waiting_verification()
        with self.assertRaises(UserError):
            self.nc.action_approve_with_comments()

    def test_approve_with_comments_requires_complete_comments(self):
        self._to_waiting_verification()
        self._add_comment(user_id=False)
        with self.assertRaises(UserError):
            self.nc.action_approve_with_comments()
        self.nc.verification_comment_ids.unlink()
        self._add_comment(deadline=False)
        with self.assertRaises(UserError):
            self.nc.action_approve_with_comments()
        self.assertFalse(self.nc.verification_result)

    def test_approve_with_comments_does_not_close_by_itself(self):
        action = self._to_waiting_verification()
        self._add_comment()
        self.nc.action_approve_with_comments()
        self.assertEqual(self.nc.state, "waiting_verification")
        self.assertEqual(self.nc.verification_result, "approved_with_comments")
        self.assertFalse(self.nc.revision_ids)
        action.stage_id = self.env.ref("mgmtsystem_action.stage_close")
        self._force_tier_validated(self.nc)
        self.nc.action_close()
        self.assertEqual(self.nc.state, "done")
        self.assertEqual(self.nc.revision_ids.result, "approved_with_comments")
        self.assertEqual(len(self.nc.verification_comment_ids), 1)

    def test_approve_with_comments_and_keep_open(self):
        self._to_waiting_verification("Keep monitoring the axis.")
        self._add_comment()
        self.nc.action_approve_with_comments()
        self.nc.action_keep_open()
        self.assertEqual(self.nc.state, "open")
        self.assertEqual(self.nc.closure_decision, "keep_open")
        self.assertFalse(self.nc.verification_result)
        self.assertEqual(len(self.nc.verification_comment_ids), 1)
        self.assertFalse(self.nc.revision_ids)

    def test_result_cannot_be_recorded_twice(self):
        self._to_waiting_verification()
        self.nc.action_approve()
        with self.assertRaises(UserError):
            self.nc.action_approve()

    def test_close_requires_an_approved_result(self):
        self._to_waiting_verification()
        with self.assertRaises(UserError):
            self.nc.action_close()

    def test_close_blocked_while_reinspection_is_pending(self):
        action = self._to_waiting_verification()
        action.stage_id = self.env.ref("mgmtsystem_action.stage_close")
        self._force_tier_validated(self.nc)
        self.nc.write(
            {"reinspection_required": True, "reinspection_date": "2031-03-01"}
        )
        self.nc.action_approve()
        with self.assertRaises(UserError):
            self.nc.action_close()
        self.nc.write({"reinspection_done_date": "2031-03-01"})
        with self.assertRaises(UserError):
            self.nc.action_close()
        self.nc.write({"reinspection_result": "satisfactory"})
        self.nc.action_close()
        self.assertEqual(self.nc.state, "done")

    def test_reinspection_requires_a_planned_date(self):
        with self.assertRaises(ValidationError):
            self.nc.write({"reinspection_required": True})

    def test_decision_requires_the_inspector_opinion(self):
        self._to_waiting_verification(opinion=False)
        with self.assertRaises(UserError):
            self.nc.action_approve()
        with self.assertRaises(UserError):
            self.nc.action_reject()

    def test_reclassify_opens_wizard_and_blocks_wrong_stage(self):
        action = self.nc.action_reclassify()
        self.assertEqual(action["res_model"], "mgmtsystem.nonconformity.reclassify")
        self.nc.action_release_to_supplier()
        with self.assertRaises(UserError):
            self.nc.action_reclassify("rfi", "Too early.")

    def test_reclassify_wizard(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        wizard = self.env["mgmtsystem.nonconformity.reclassify"].create(
            {
                "nonconformity_id": self.nc.id,
                "classification": "rfi",
                "note": "It is a design query.",
            }
        )
        self._clear_tier_reviews(self.nc)
        wizard.action_reclassify()
        self.assertEqual(self.nc.state, "draft")
        self.assertEqual(self.nc.classification, "rfi")

    def test_stop_work_requires_flag(self):
        with self.assertRaises(ValidationError):
            self._create_occurrence(
                classification="stop_work",
                stop_work=False,
                stop_work_date="2026-08-14",
            )

    def test_unknown_state_and_default_origin(self):
        with self.assertRaises(UserError):
            self.nc._get_stage_by_state("unknown")
        self.assertIn(
            self.origin,
            self.env["mgmtsystem.nonconformity"]._default_origin_ids(),
        )

    def test_onchange_helpers_and_evidence(self):
        rec = self.env["mgmtsystem.nonconformity"].new({"classification": "stop_work"})
        rec._onchange_classification()
        self.assertTrue(rec.stop_work)
        self.assertEqual(rec.priority, "immediate")
        rec.disposition = "concession"
        rec._onchange_disposition()
        self.assertTrue(rec.concession_required)
        evidence = self.env["mgmtsystem.nonconformity.evidence"].create(
            {
                "nonconformity_id": self.nc.id,
                "section": "inspector",
                "name": "Plumb measurement",
                "evidence_type": "measurement",
                "value": "15",
                "uom": "mm",
            }
        )
        self.assertIn(evidence, self.nc.inspector_evidence_ids)
        self.assertNotIn(evidence, self.nc.supplier_evidence_ids)

    def test_immediate_action_code_unique(self):
        existing = self.env.ref(
            "planservice_mgmtsystem_occurrence.immediate_action_protect"
        )
        self.env.flush_all()
        with mute_logger("odoo.sql_db"), self.assertRaises(Exception):
            self.env["mgmtsystem.occurrence.immediate.action"].create(
                {"name": "Duplicate protect", "code": existing.code}
            )

    def test_occurrence_report_translates_pt_br(self):
        lang = self.env["res.lang"]._activate_lang("pt_BR")
        if not lang:
            self.skipTest("pt_BR language is not available")
        self.env.user.lang = lang.code
        html, _report_type = (
            self.env["ir.actions.report"]
            .with_context(lang=lang.code)
            ._render_qweb_html(
                "mgmtsystem_nonconformity.report_mgmtsystem_nonconformity",
                self.nc.ids,
            )
        )
        self.assertIn("Classificação e encaminhamento".encode(), html)
        self.assertIn("Dúvida de Projeto".encode(), html)
        self.assertIn(b"Inspetor", html)

    def test_verify_blocked_outside_waiting_verification(self):
        with self.assertRaises(UserError):
            self.nc.action_approve()
        with self.assertRaises(UserError):
            self.nc.action_keep_open()
        with self.assertRaises(UserError):
            self.nc.action_reject()

    def test_stage_states_include_occurrence_steps(self):
        states = dict(self.env["mgmtsystem.nonconformity.stage"]._get_states())
        self.assertIn("waiting_supplier", states)
        self.assertIn("waiting_verification", states)
        self.nc._check_open_with_action_comments()

    def test_document_and_supplier_evidence(self):
        document = self.env["mgmtsystem.nonconformity.document"].create(
            {
                "nonconformity_id": self.nc.id,
                "document_type": "report",
                "name": "Lab report",
            }
        )
        evidence = self.env["mgmtsystem.nonconformity.evidence"].create(
            {
                "nonconformity_id": self.nc.id,
                "section": "supplier",
                "name": "Axis photo",
                "evidence_type": "photo",
            }
        )
        self.assertIn(document, self.nc.document_ids)
        self.assertIn(evidence, self.nc.supplier_evidence_ids)
        self.assertNotIn(evidence, self.nc.inspector_evidence_ids)

    def test_submit_keeps_existing_response_date(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc, disposition="conclude")
        self.nc.supplier_response_date = "2026-08-01"
        self.nc.action_submit_response()
        self.assertEqual(str(self.nc.supplier_response_date), "2026-08-01")

    def test_reclassify_from_open_without_note(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self._clear_tier_reviews(self.nc)
        self.assertTrue(self.nc.action_reclassify("punch_list"))
        self.assertEqual(self.nc.state, "draft")
        self.assertEqual(self.nc.classification, "punch_list")
