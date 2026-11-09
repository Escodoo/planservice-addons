# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import json

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged

from ..hooks import post_init_hook

REPORT_MODEL = "planservice.employer.cost.project.report"


@tagged("post_install", "-at_install")
class TestCostDashboard(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.dashboard = cls.env.ref(
            "planservice_employers_calc_dashboard.dashboard_cost"
        )
        cls.project = cls.env["project.project"].create(
            {"name": "Obra do dashboard", "privacy_visibility": "employees"}
        )
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Gerente",
                "login": "manager.dash@test.com",
                "groups_id": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("hr_timesheet.group_timesheet_manager").id),
                ],
            }
        )

    def test_dashboard_created_on_install(self):
        self.assertTrue(self.dashboard.published)
        self.assertEqual(self.dashboard.name, "Custo de pessoal por obra")
        self.assertEqual(len(self.dashboard.item_ids), 8)
        self.assertEqual(
            set(self.dashboard.item_ids.mapped("model_name")), {REPORT_MODEL}
        )
        self.assertIn(
            self.env.ref("hr_timesheet.group_timesheet_manager"),
            self.dashboard.group_ids,
        )

    def test_button_opens_dashboard_with_project_filter(self):
        action = self.project.with_user(self.manager).action_open_cost_dashboard()
        self.assertEqual(action["type"], "ir.actions.client")
        self.assertEqual(action["tag"], "boardkit_dashboard")
        self.assertEqual(action["params"]["dashboard_id"], self.dashboard.id)
        layout = self.env["boardkit.dashboard.layout"].search(
            [
                ("dashboard_id", "=", self.dashboard.id),
                ("user_id", "=", self.manager.id),
            ]
        )
        state = json.loads(layout.filters_json)
        self.assertEqual(state["date_preset"], "none")
        spec = state["custom_filters"][0]
        self.assertEqual(spec["model"], REPORT_MODEL)
        self.assertEqual(spec["field"], "project_key")
        self.assertEqual(spec["operator"], "=")
        self.assertEqual(spec["value"], self.project.id)
        self.assertIn("Obra do dashboard", spec["label"])

    def test_saved_filter_is_accepted_and_exact(self):
        """O Boardkit aceita o filtro e ele vira um domínio exato pelo ID."""
        self.project.with_user(self.manager).action_open_cost_dashboard()
        layout = self.env["boardkit.dashboard.layout"].search(
            [
                ("dashboard_id", "=", self.dashboard.id),
                ("user_id", "=", self.manager.id),
            ]
        )
        spec = json.loads(layout.filters_json)["custom_filters"][0]
        item = self.dashboard.item_ids[0]
        self.assertEqual(
            item._custom_filters_domain({"custom_filters": [spec]}),
            [("project_key", "=", self.project.id)],
        )

    def test_button_replaces_previous_project_filter(self):
        other = self.env["project.project"].create({"name": "Outra obra"})
        self.project.with_user(self.manager).action_open_cost_dashboard()
        other.with_user(self.manager).action_open_cost_dashboard()
        layout = self.env["boardkit.dashboard.layout"].search(
            [
                ("dashboard_id", "=", self.dashboard.id),
                ("user_id", "=", self.manager.id),
            ]
        )
        filters = json.loads(layout.filters_json)["custom_filters"]
        self.assertEqual([f["value"] for f in filters], [other.id])

    def test_button_manager_only(self):
        plain = self.env["res.users"].create(
            {
                "name": "Sem permissão",
                "login": "plain.dash@test.com",
                "groups_id": [
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("project.group_project_user").id),
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.project.with_user(plain).action_open_cost_dashboard()

    def test_button_without_dashboard_raises(self):
        self.dashboard.unlink()
        with self.assertRaises(UserError):
            self.project.with_user(self.manager).action_open_cost_dashboard()

    def test_post_init_hook_replaces_existing_dashboard(self):
        """Reinstalar o módulo recria o dashboard sem duplicá-lo."""
        post_init_hook(self.env)
        dashboard = self.env.ref("planservice_employers_calc_dashboard.dashboard_cost")
        self.assertTrue(dashboard.published)
        self.assertFalse(self.dashboard.exists())
