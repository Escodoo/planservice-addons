# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import UserError, ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOccurrenceWorkflow(TransactionCase):
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

    def test_release_requires_classification(self):
        nc = self._create_occurrence(classification=False)
        with self.assertRaises(UserError):
            nc.action_release_to_supplier()

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
        self.nc.action_approve()
        self.assertEqual(self.nc.state, "done")
        self.assertEqual(self.nc.verification_result, "approved")

    def test_submit_requires_containment(self):
        self.nc.action_release_to_supplier()
        with self.assertRaises(UserError):
            self.nc.action_submit_response()

    def test_reject_returns_to_supplier(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
        self.nc.evaluation_comments = "Rework is incomplete."
        self.nc.action_reject()
        self.assertEqual(self.nc.state, "waiting_supplier")
        self.assertEqual(self.nc.verification_result, "rejected")

    def test_reclassify_returns_to_draft(self):
        self.nc.action_release_to_supplier()
        self._fill_supplier_response(self.nc)
        self.nc.action_submit_response()
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
        html, _report_type = self.env["ir.actions.report"]._render_qweb_html(
            "mgmtsystem_nonconformity.report_mgmtsystem_nonconformity",
            self.nc.ids,
        )
        self.assertIn(b"Occurrence Record", html)
        self.assertIn(self.nc.ref.encode(), html)
        self.assertIn(b"Classification and routing", html)
        self.assertIn(b"Supplier response", html)
