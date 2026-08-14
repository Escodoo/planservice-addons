# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged

from odoo.addons.planservice_mgmtsystem_occurrence_portal.controllers.portal import (
    OccurrenceCustomerPortal,
)
from odoo.addons.website.tools import MockRequest


@tagged("post_install", "-at_install")
class TestOccurrencePortal(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create(
            {
                "name": "Portal Supplier Co",
                "is_company": True,
                "email": "supplier@example.com",
            }
        )
        cls.other_partner = cls.env["res.partner"].create(
            {"name": "Other Supplier", "is_company": True}
        )
        portal_group = cls.env.ref("base.group_portal")
        cls.portal_user = (
            cls.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Supplier Portal User",
                    "login": "occurrence_portal_user",
                    "email": "supplier@example.com",
                    "partner_id": cls.partner.id,
                    "groups_id": [(6, 0, [portal_group.id])],
                }
            )
        )
        cls.origin = cls.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence"
        )
        cls.project = cls.env["project.project"].create({"name": "Portal Work P001"})
        cls.nc = cls.env["mgmtsystem.nonconformity"].create(
            {
                "name": "Portal occurrence",
                "partner_id": cls.partner.id,
                "project_id": cls.project.id,
                "manager_user_id": cls.env.user.id,
                "responsible_user_id": cls.env.user.id,
                "description": "Field deviation found on site.",
                "origin_ids": [(6, 0, cls.origin.ids)],
                "classification": "nc",
            }
        )
        cls.other_nc = cls.env["mgmtsystem.nonconformity"].create(
            {
                "name": "Other occurrence",
                "partner_id": cls.other_partner.id,
                "manager_user_id": cls.env.user.id,
                "responsible_user_id": cls.env.user.id,
                "description": "Another supplier record.",
                "origin_ids": [(6, 0, cls.origin.ids)],
                "classification": "observation",
            }
        )

    def test_access_url(self):
        self.assertEqual(self.nc.access_url, f"/my/occurrences/{self.nc.id}")

    def test_portal_user_reads_own_record(self):
        rec = self.nc.with_user(self.portal_user)
        self.assertEqual(rec.name, "Portal occurrence")

    def test_portal_user_cannot_read_other_partner(self):
        with self.assertRaises(AccessError):
            self.other_nc.with_user(self.portal_user).read(["name"])

    def test_portal_user_writes_supplier_fields_after_release(self):
        self.nc.action_release_to_supplier()
        self.nc.with_user(self.portal_user).write(
            {"containment_text": "Area isolated by the supplier."}
        )
        self.assertEqual(self.nc.containment_text, "Area isolated by the supplier.")
        self.assertEqual(self.nc.state, "open")

    def test_portal_user_cannot_change_classification(self):
        self.nc.action_release_to_supplier()
        with self.assertRaises(AccessError):
            self.nc.with_user(self.portal_user).write({"classification": "rfi"})

    def test_portal_user_cannot_write_in_draft(self):
        with self.assertRaises(AccessError):
            self.nc.with_user(self.portal_user).write(
                {"containment_text": "Too early."}
            )

    def test_search_domain_matches_title_and_classification(self):
        controller = OccurrenceCustomerPortal()
        self.assertEqual(
            controller._occurrence_get_search_domain("name", "Portal"),
            [("name", "ilike", "Portal")],
        )
        self.assertIn(
            "nc",
            controller._occurrence_classification_search_domain("Confirmed")[0][2],
        )

    def test_portal_list_search_and_stage_filter(self):
        controller = OccurrenceCustomerPortal()
        with MockRequest(self.env(user=self.portal_user)):
            values = controller._prepare_my_occurrences_values(
                search="Portal",
                search_in="name",
            )
            self.assertEqual(values["occurrences"], self.nc)
            stage_key = f"stage_{self.nc.stage_id.id}"
            self.assertIn(stage_key, values["searchbar_filters"])
            filtered = controller._prepare_my_occurrences_values(filterby=stage_key)
            self.assertIn(self.nc, filtered["occurrences"])
            empty = controller._prepare_my_occurrences_values(
                search="missing-term-xyz",
                search_in="content",
            )
            self.assertFalse(empty["occurrences"])
            project_key = f"project_{self.project.id}"
            self.assertNotIn(project_key, values["searchbar_filters"])
            self.assertIn(project_key, values["searchbar_projects"])
            by_project = controller._prepare_my_occurrences_values(
                projectby=project_key
            )
            self.assertEqual(by_project["occurrences"], self.nc)
            combined = controller._prepare_my_occurrences_values(
                filterby="closed",
                projectby=project_key,
            )
            self.assertNotIn(self.nc, combined["occurrences"])
