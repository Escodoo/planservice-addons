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
        self.assertEqual(len(self.dashboard.item_ids), 12)
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
        self._assert_project_menu(dashboard)

    def _project_menu(self):
        return self.env.ref(
            "planservice_employers_calc_dashboard.menu_dashboard_cost_project"
        )

    def _assert_project_menu(self, dashboard):
        """O menu de Projetos abre o mesmo dashboard, com os mesmos grupos."""
        menu = self._project_menu()
        self.assertEqual(menu.parent_id, self.env.ref("project.menu_main_pm"))
        self.assertEqual(menu.name, dashboard.menu_id.name)
        self.assertEqual(menu.action, dashboard.client_action_id)
        self.assertEqual(menu.groups_id, dashboard.menu_id.groups_id)

    def test_dashboard_menu_also_in_project(self):
        self.assertEqual(
            self.dashboard.menu_id.parent_id,
            self.env.ref("hr_timesheet.timesheet_menu_root"),
        )
        self._assert_project_menu(self.dashboard)
        menus = self.env["ir.ui.menu"].with_user(self.manager)._visible_menu_ids()
        self.assertIn(self._project_menu().id, menus)
        user = self.env["res.users"].create(
            {
                "name": "Usuário sem gestão",
                "login": "user.dash@test.com",
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )
        menus = self.env["ir.ui.menu"].with_user(user)._visible_menu_ids()
        self.assertNotIn(self._project_menu().id, menus)

    def test_migration_adds_project_menu(self):
        """A migração 18.0.1.2.0 cria o menu em Projetos sem recriar o dashboard."""
        path = file_path(
            "planservice_employers_calc_dashboard/migrations/18.0.1.2.0/"
            "post-migration.py"
        )
        spec = importlib.util.spec_from_file_location("dashboard_post_120", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        old_menu = self._project_menu()
        migration.migrate(self.env.cr, None)
        self.assertTrue(old_menu.exists(), "fresh install: no-op")
        migration.migrate(self.env.cr, "18.0.1.1.0")
        self.assertTrue(self.dashboard.exists())
        self.assertFalse(old_menu.exists())
        self._assert_project_menu(self.dashboard)
        self.dashboard.menu_parent_id = False
        migration.migrate(self.env.cr, "18.0.1.1.0")
        self.assertTrue(self._project_menu().exists(), "sem menu do dashboard: no-op")

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
        deviation = self._item("Desvio até hoje (previsto - realizado)")._get_tile_data(
            params
        )["value"]
        self.assertAlmostEqual(planned, sum(rows.mapped("planned_cost")), places=2)
        self.assertAlmostEqual(deviation, sum(rows.mapped("cost_deviation")), places=2)
        # há previsto depois de hoje, que fica fora do bloco "até hoje"
        total = self._item("Custo previsto")._get_tile_data(params)["value"]
        self.assertGreater(total, planned)

    def test_weekly_chart(self):
        item = self._item("Custo previsto x realizado por semana")
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
        self.assertEqual(len(dashboard.item_ids), 12)

    def test_s_curve_accumulates_month_by_month(self):
        """A curva S é a soma corrida do gráfico mensal, previsto e realizado."""
        user = self.env["res.users"].create(
            {
                "name": "Rui",
                "login": "rui.dash@test.com",
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )
        self.env["hr.employee"].create(
            {
                "name": "Rui",
                "user_id": user.id,
                "employer_salary_benefits_cost": 10000.0,
            }
        )
        today = fields.Date.context_today(self.project)
        self.project.date_start = today - timedelta(days=70)
        self.env["project.task"].create(
            {
                "name": "Tarefa da curva S",
                "project_id": self.project.id,
                "allocated_hours": 480.0,
                "user_ids": [(6, 0, user.ids)],
                "date_deadline": fields.Datetime.to_datetime(today)
                + timedelta(days=30, hours=12),
            }
        )
        self.env.flush_all()
        params = {"date_preset": "none"}
        monthly = self._item("Custo previsto x realizado por mês")._get_chart_data(
            params
        )
        curve_item = self._item("Curva S: previsto x realizado acumulado")
        self.assertTrue(curve_item.cumulative)
        curve = curve_item._get_chart_data(params)
        self.assertEqual(curve["labels"], monthly["labels"])
        self.assertGreater(len(curve["labels"]), 2)
        for month_set, curve_set in zip(
            monthly["datasets"], curve["datasets"], strict=True
        ):
            running = 0
            for value, cumulative in zip(
                month_set["data"], curve_set["data"], strict=True
            ):
                running += value
                self.assertAlmostEqual(cumulative, running, places=2)
        planned = curve["datasets"][0]["data"]
        self.assertEqual(planned, sorted(planned), "acumulado nunca diminui")

    def test_cumulative_is_exported(self):
        """A opção de acumulado entra no export/import do Boardkit."""
        curve_item = self._item("Curva S: previsto x realizado acumulado")
        self.assertIn("cumulative", type(curve_item)._EXPORT_SIMPLE_FIELDS)
        vals = curve_item._import_prepare_vals(
            {"name": "Cópia", "model": REPORT_MODEL, "cumulative": True},
            self.dashboard.id,
        )
        self.assertTrue(vals["cumulative"])

    def test_migration_adds_s_curve(self):
        """A migração 18.0.1.3.0 acrescenta a curva S sem recriar o dashboard."""
        path = file_path(
            "planservice_employers_calc_dashboard/migrations/18.0.1.3.0/"
            "post-migration.py"
        )
        spec = importlib.util.spec_from_file_location("dashboard_post_130", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        curve_item = self._item("Curva S: previsto x realizado acumulado")
        curve_item.unlink()
        migration.migrate(self.env.cr, None)
        self.assertEqual(len(self.dashboard.item_ids), 11, "fresh install: no-op")
        migration.migrate(self.env.cr, "18.0.1.2.0")
        self.assertTrue(self.dashboard.exists())
        curve_item = self._item("Curva S: previsto x realizado acumulado")
        self.assertTrue(curve_item.cumulative)
        layout = json.loads(self.dashboard.layout_json)
        self.assertEqual(layout[str(curve_item.id)]["y"], 4)
        migration.migrate(self.env.cr, "18.0.1.2.0")
        self.assertEqual(len(self.dashboard.item_ids), 12, "sem duplicar")
        self.dashboard.unlink()
        migration.migrate(self.env.cr, "18.0.1.2.0")

    def test_migration_renames_actual_to_realizado(self):
        """A migração 18.0.1.4.0 troca "real" por "realizado" nos textos."""
        path = file_path(
            "planservice_employers_calc_dashboard/migrations/18.0.1.4.0/"
            "post-migration.py"
        )
        spec = importlib.util.spec_from_file_location("dashboard_post_140", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        kpi = self._item("Custo Realizado")
        curve = self._item("Curva S: previsto x realizado acumulado")
        tile = self._item("Previsto até hoje")
        # estado da 18.0.1.3.0
        kpi.name = "Custo real"
        curve.name = "Curva S: previsto x real acumulado"
        tile.description = "Compare com o custo real."
        self.dashboard.description = "Custo previsto x real de pessoal por obra."
        migration.migrate(self.env.cr, None)
        self.assertEqual(kpi.name, "Custo real", "fresh install: no-op")
        for _run in range(2):
            migration.migrate(self.env.cr, "18.0.1.3.0")
            self.assertEqual(kpi.name, "Custo Realizado")
            self.assertEqual(curve.name, "Curva S: previsto x realizado acumulado")
            self.assertEqual(tile.description, "Compare com o custo realizado.")
            self.assertEqual(
                self.dashboard.description,
                "Custo previsto x realizado de pessoal por obra.",
            )
        self.dashboard.unlink()
        migration.migrate(self.env.cr, "18.0.1.3.0")

    def _layout_y(self):
        layout = json.loads(self.dashboard.layout_json)
        return {
            item.name: layout[str(item.id)]["y"] for item in self.dashboard.item_ids
        }

    def test_migration_moves_s_curve_after_cards(self):
        """A migração 18.0.1.4.0 põe a curva S logo abaixo dos cards."""
        path = file_path(
            "planservice_employers_calc_dashboard/migrations/18.0.1.4.0/"
            "post-migration.py"
        )
        spec = importlib.util.spec_from_file_location("dashboard_post_140b", path)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        curve = "Curva S: previsto x realizado acumulado"
        expected = self._layout_y()
        # estado da 18.0.1.3.0: curva no fim, gráficos a partir da linha 4
        old = {name: y - 6 if y >= 10 else y for name, y in expected.items()}
        old[curve] = 25
        layout = json.loads(self.dashboard.layout_json)
        for item in self.dashboard.item_ids:
            layout[str(item.id)]["y"] = old[item.name]
        self.dashboard.layout_json = json.dumps(layout)
        for _run in range(2):
            migration.migrate(self.env.cr, "18.0.1.3.0")
            self.assertEqual(self._layout_y(), expected)
        # vindo da 18.0.1.2.0, a 18.0.1.3.0 já cria a curva na linha 4,
        # em cima dos gráficos: eles descem
        layout = json.loads(self.dashboard.layout_json)
        for item in self.dashboard.item_ids:
            layout[str(item.id)]["y"] = 4 if item.name == curve else old[item.name]
        self.dashboard.layout_json = json.dumps(layout)
        migration.migrate(self.env.cr, "18.0.1.3.0")
        self.assertEqual(self._layout_y(), expected)
        # sem a curva, o layout fica como está
        self._item(curve).unlink()
        before = self.dashboard.layout_json
        migration.migrate(self.env.cr, "18.0.1.3.0")
        self.assertEqual(self.dashboard.layout_json, before)
