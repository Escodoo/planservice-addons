# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import contextlib
from types import SimpleNamespace
from unittest.mock import patch

import odoo.http
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import DotDict

from odoo.addons.planservice_mgmtsystem_occurrence_portal.controllers.portal import (
    OccurrenceCustomerPortal,
)


@contextlib.contextmanager
def mock_request(env):
    """Push a portal request on the HTTP stack without depending on website."""
    lang_code = env.context.get("lang") or "en_US"
    env = env(context=dict(env.context, lang=lang_code))
    request = SimpleNamespace(
        env=env,
        cr=env.cr,
        uid=env.uid,
        context=env.context,
        db=env.registry.db_name,
        registry=env.registry,
        params={},
        session=DotDict(odoo.http.get_default_session()),
        httprequest=SimpleNamespace(
            form=SimpleNamespace(getlist=lambda _name: []),
            files=SimpleNamespace(getlist=lambda _name: []),
        ),
        lang=env["res.lang"]._get_data(code=lang_code),
        is_frontend=True,
        redirect=env["ir.http"]._redirect,
        render=lambda *_args, **_kwargs: "<MockResponse>",
    )
    odoo.http._request_stack.push(request)
    try:
        yield request
    finally:
        odoo.http._request_stack.pop()


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
        self.assertEqual(
            controller._occurrence_get_search_domain("classification", "Confirmed"),
            controller._occurrence_classification_search_domain("Confirmed"),
        )

    def test_portal_list_search_and_stage_filter(self):
        controller = OccurrenceCustomerPortal()
        with mock_request(self.env(user=self.portal_user)):
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

    def test_search_domains_and_defaults(self):
        controller = OccurrenceCustomerPortal()
        self.assertEqual(
            controller._occurrence_get_search_domain("ref", "004"),
            [("ref", "ilike", "004")],
        )
        self.assertEqual(
            controller._occurrence_get_search_domain("stage_id", "Draft"),
            [("stage_id.name", "ilike", "Draft")],
        )
        self.assertEqual(
            controller._occurrence_get_search_domain("project_id", "P001"),
            [("project_id.name", "ilike", "P001")],
        )
        content = controller._occurrence_get_search_domain("content", "column")
        self.assertIn(("description", "ilike", "column"), content)
        fallback = controller._occurrence_get_search_domain("unknown", "x")
        self.assertIn(("name", "ilike", "x"), fallback)
        self.assertEqual(
            controller._occurrence_classification_search_domain("missing-xyz"),
            [("classification", "ilike", "missing-xyz")],
        )
        with mock_request(self.env(user=self.portal_user)):
            values = controller._prepare_my_occurrences_values(
                sortby="invalid",
                filterby="invalid",
                projectby="invalid",
                groupby="invalid",
                search_in="invalid",
            )
            self.assertEqual(values["sortby"], "date")
            self.assertEqual(values["filterby"], "all")
            self.assertEqual(values["projectby"], "all")
            self.assertEqual(values["groupby"], "none")
            self.assertEqual(values["search_in"], "content")
            grouped = controller._prepare_my_occurrences_values(groupby="project_id")
            self.assertTrue(grouped["grouped_occurrences"])
            orphan = self.env["mgmtsystem.nonconformity"].create(
                {
                    "name": "Occurrence without project",
                    "partner_id": self.partner.id,
                    "manager_user_id": self.env.user.id,
                    "responsible_user_id": self.env.user.id,
                    "description": "No project linked.",
                    "origin_ids": [(6, 0, self.origin.ids)],
                    "classification": "observation",
                }
            )
            values = controller._prepare_my_occurrences_values()
            self.assertIn("no_project", values["searchbar_projects"])
            without_project = controller._prepare_my_occurrences_values(
                projectby="no_project"
            )
            self.assertIn(orphan, without_project["occurrences"])
            self.assertNotIn(self.nc, without_project["occurrences"])

    def test_home_counter_and_access_action(self):
        controller = OccurrenceCustomerPortal()
        with mock_request(self.env(user=self.portal_user)):
            values = controller._prepare_home_portal_values(["occurrence_count"])
            self.assertGreaterEqual(values["occurrence_count"], 1)
        action = self.nc.with_user(self.portal_user)._get_access_action()
        self.assertEqual(action["type"], "ir.actions.act_url")
        self.assertEqual(action["url"], self.nc.access_url)
        self.nc.action_release_to_supplier()
        self.assertTrue(self.nc.access_token)

    def test_prepare_supplier_vals_and_action_from_post(self):
        controller = OccurrenceCustomerPortal()
        vals = controller._prepare_supplier_vals(
            {
                "containment_text": "Isolated.",
                "disposition": "repair",
                "concession_required": "on",
                "deadline_impact": "",
                "supplier_representative_id": str(self.partner.id),
            }
        )
        self.assertEqual(vals["containment_text"], "Isolated.")
        self.assertTrue(vals["concession_required"])
        self.assertFalse(vals["deadline_impact"])
        self.assertEqual(vals["supplier_representative_id"], self.partner.id)
        self.assertNotIn("classification", vals)

    def test_internal_user_keeps_backend_access_action(self):
        action = self.nc._get_access_action()
        self.assertNotEqual(action.get("type"), "ir.actions.act_url")

    def test_portal_routes_and_post_helpers(self):
        controller = OccurrenceCustomerPortal()
        self.nc.action_release_to_supplier()
        with mock_request(self.env(user=self.portal_user)) as req:
            req.httprequest.form.getlist = lambda name: {
                "evidence_name": ["", "Axis photo"],
                "evidence_type": ["photo", "photo"],
                "document_type": ["", "report"],
                "document_name": ["", "Lab report"],
            }.get(name, [])
            req.httprequest.files.getlist = lambda name: []
            listing = controller.portal_my_occurrences()
            self.assertEqual(getattr(listing, "status_code", 200), 200)
            page = controller.portal_my_occurrence(self.nc.id)
            self.assertEqual(getattr(page, "status_code", 200), 200)
            missing = controller.portal_my_occurrence(self.other_nc.id)
            self.assertIn(getattr(missing, "status_code", 303), (200, 302, 303))
            update = controller.portal_occurrence_update(
                self.nc.id,
                containment_text="Isolated on site.",
                cause_justification="Formwork failure.",
                disposition="correct",
            )
            self.assertIn(getattr(update, "status_code", 303), (200, 302, 303))
            self.assertEqual(self.nc.containment_text, "Isolated on site.")
            controller._create_evidence_from_post(self.nc, {})
            controller._create_document_from_post(self.nc, {})
            self.assertTrue(self.nc.supplier_evidence_ids)
            self.assertTrue(self.nc.document_ids)
            submit_error = controller.portal_occurrence_submit(self.nc.id)
            self.assertEqual(getattr(submit_error, "status_code", 200), 200)

            upload = SimpleNamespace(filename="axis.jpg", read=lambda: b"fake-image")
            evidence = self.nc.supplier_evidence_ids[:1]
            controller._save_upload(evidence, upload)
            self.assertTrue(evidence.attachment_ids)
            controller._save_upload(evidence, None)
            controller._create_action_from_post(self.nc, {"action_name": ""})
            Action = type(self.env["mgmtsystem.action"])
            with patch.object(Action, "send_mail_for_action", return_value=True):
                controller._create_action_from_post(
                    self.nc,
                    {
                        "action_name": "Realign the column",
                        "action_deadline": "2026-08-20",
                        "action_description": "Check formwork.",
                    },
                )
            self.assertTrue(
                self.nc.action_ids.filtered(
                    lambda act: act.name == "Realign the column"
                )
            )
            submit_ok = controller.portal_occurrence_submit(
                self.nc.id,
                containment_text="Isolated on site.",
                cause_justification="Formwork failure.",
                disposition="correct",
            )
            self.assertIn(getattr(submit_ok, "status_code", 303), (200, 302, 303))
            self.assertEqual(self.nc.state, "waiting_verification")
            blocked = controller.portal_occurrence_update(self.nc.id)
            self.assertIn(getattr(blocked, "status_code", 303), (200, 302, 303))
            missing_update = controller.portal_occurrence_update(self.other_nc.id)
            self.assertIn(getattr(missing_update, "status_code", 303), (200, 302, 303))
            missing_submit = controller.portal_occurrence_submit(self.other_nc.id)
            self.assertIn(getattr(missing_submit, "status_code", 303), (200, 302, 303))

    def test_portal_list_redirects_without_read_access(self):
        user = (
            self.env["res.users"]
            .with_context(no_reset_password=True)
            .create(
                {
                    "name": "Internal without SGI",
                    "login": "no_occurrence_access",
                    "groups_id": [(6, 0, [self.env.ref("base.group_user").id])],
                }
            )
        )
        Occurrence = self.env["mgmtsystem.nonconformity"].with_user(user)
        self.assertFalse(Occurrence.has_access("read"))
        controller = OccurrenceCustomerPortal()
        with mock_request(self.env(user=user)):
            response = controller.portal_my_occurrences()
            self.assertIn(getattr(response, "status_code", 303), (200, 302, 303))
            values = controller._prepare_home_portal_values(["occurrence_count"])
            self.assertEqual(values["occurrence_count"], 0)

    def test_get_occurrence_returns_none_without_access(self):
        controller = OccurrenceCustomerPortal()
        with mock_request(self.env(user=self.portal_user)):
            self.assertFalse(controller._get_occurrence(self.other_nc.id))
            self.assertTrue(controller._get_occurrence(self.nc.id))
