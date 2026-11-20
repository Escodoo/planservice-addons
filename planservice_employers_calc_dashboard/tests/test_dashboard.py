# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import importlib.util
import json
from datetime import timedelta

from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, tagged
from odoo.tools.misc import file_path

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
        self.assertEqual(len(self.dashboard.item_ids), 11)
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

    def _item(self, name):
        item = self.dashboard.item_ids.filtered(lambda i: i.name == name)
        self.assertEqual(len(item), 1)
        return item

    def test_to_date_tiles_only_count_until_today(self):
        """Previsto e desvio até hoje somam só as linhas com data até hoje."""
        user = self.env["res.users"].create(
            {
                "name": "Fábio",
                "login": "fabio.dash@test.com",
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )
        self.env["hr.employee"].create(
            {
                "name": "Fábio",
                "user_id": user.id,
                "employer_salary_benefits_cost": 10000.0,
            }
        )
        today = fields.Date.context_today(self.project)
        self.project.date_start = today - timedelta(days=14)
        self.env["project.task"].create(
            {
                "name": "Tarefa do dashboard",
                "project_id": self.project.id,
                "allocated_hours": 160.0,
                "user_ids": [(6, 0, user.ids)],
                "date_deadline": fields.Datetime.to_datetime(today)
                + timedelta(days=14, hours=12),
            }
        )
        self.env.flush_all()
        rows = self.env[REPORT_MODEL].search([("date", "<=", today)])
        params = {"date_preset": "none"}
        planned = self._item("Previsto até hoje")._get_tile_data(params)["value"]
        deviation = self._item("Desvio até hoje (previsto - real)")._get_tile_data(
            params
        )["value"]
        self.assertAlmostEqual(planned, sum(rows.mapped("planned_cost")), places=2)
        self.assertAlmostEqual(deviation, sum(rows.mapped("cost_deviation")), places=2)
        # há previsto depois de hoje, que fica fora do bloco "até hoje"
        total = self._item("Custo previsto")._get_tile_data(params)["value"]
        self.assertGreater(total, planned)

    def test_weekly_chart(self):
        item = self._item("Custo previsto x real por semana")
        self.assertEqual(item.group_by_granularity, "week")
        self.assertEqual(item.group_by_field_id.name, "date")

    def test_migration_recreates_dashboard(self):
        """A migração 18.0.1.1.0 recria o dashboard com os itens novos."""
        path = file_path(
            "planservice_employers_calc_dashboard/migrations/18.0.1.1.0/"
            "post-migration.py"
        )
        spec = importlib.util.spec_from_file_location("dashboard_post_110", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.migrate(self.env.cr, None)
        self.assertTrue(self.dashboard.exists(), "fresh install: no-op")
        migration.migrate(self.env.cr, "18.0.1.0.0")
        self.assertFalse(self.dashboard.exists())
        dashboard = self.env.ref("planservice_employers_calc_dashboard.dashboard_cost")
        self.assertEqual(len(dashboard.item_ids), 11)
