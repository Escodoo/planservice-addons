# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestOccurrenceTierValidation(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {"name": "Tier Supplier", "is_company": True}
        )
        cls.origin = cls.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence"
        )
        cls.nc = cls.env["mgmtsystem.nonconformity"].create(
            {
                "name": "Tier occurrence",
                "partner_id": cls.partner.id,
                "manager_user_id": cls.env.user.id,
                "responsible_user_id": cls.env.user.id,
                "inspector_id": cls.env.user.id,
                "description": "Deviation pending formal verification.",
                "origin_ids": [(6, 0, cls.origin.ids)],
                "classification": "nc",
            }
        )

    def _submit_for_verification(self, nc):
        nc.action_release_to_supplier()
        action = self.env["mgmtsystem.action"].create(
            {
                "name": "Correct the deviation",
                "type_action": "correction",
                "user_id": self.env.user.id,
            }
        )
        nc.write(
            {
                "containment_text": "Isolated.",
                "cause_justification": "Process failure.",
                "disposition": "correct",
                "action_ids": [(4, action.id)],
            }
        )
        nc.action_submit_response()
        return action

    def test_model_is_registered(self):
        names = self.env["tier.definition"]._get_tier_validation_model_names()
        self.assertIn("mgmtsystem.nonconformity", names)

    def test_submit_requests_validation(self):
        self._submit_for_verification(self.nc)
        self.assertEqual(self.nc.state, "waiting_verification")
        self.assertTrue(self.nc.review_ids)

    def test_approve_blocked_until_validated(self):
        action = self._submit_for_verification(self.nc)
        action.stage_id = self.env.ref("mgmtsystem_action.stage_close")
        self.nc.evaluation_comments = "Ready to close."
        if self.nc.need_validation or self.nc.review_ids:
            with self.assertRaises(ValidationError):
                self.nc.action_approve()

    def test_reject_clears_reviews(self):
        self._submit_for_verification(self.nc)
        self.nc.evaluation_comments = "Rework needed."
        self.nc.action_reject()
        self.assertEqual(self.nc.state, "waiting_supplier")
        self.assertFalse(self.nc.review_ids)

    def test_verification_fields_are_exceptions(self):
        exceptions = self.env[
            "mgmtsystem.nonconformity"
        ]._get_under_validation_exceptions()
        self.assertIn("evaluation_comments", exceptions)
        self.assertIn("verification_result", exceptions)
        self.assertIn("stage_id", exceptions)

    def test_state_conditions_and_review_cleanup(self):
        self._submit_for_verification(self.nc)
        done = self.env.ref("mgmtsystem_nonconformity.stage_done")
        draft = self.env.ref("mgmtsystem_nonconformity.stage_draft")
        self.assertTrue(self.nc._check_state_conditions({"stage_id": done.id}))
        self.assertTrue(self.nc._check_state_conditions({"state": "done"}))
        self.assertFalse(self.nc._check_state_conditions({"name": "No state change"}))
        self.assertTrue(self.nc._allow_to_remove_reviews({"stage_id": draft.id}))
        self.assertFalse(self.nc._allow_to_remove_reviews({"name": "Keep reviews"}))

    def test_rejected_tier_returns_to_supplier(self):
        self._submit_for_verification(self.nc)
        self.nc._rejected_tier(self.nc.review_ids)
        self.assertEqual(self.nc.state, "waiting_supplier")
        self.assertEqual(self.nc.verification_result, "rejected")
        self.assertEqual(self.nc.closure_decision, "keep_open")
