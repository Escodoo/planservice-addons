# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestProjectPlanMatrix(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create(
            {
                "name": "Test Plan Project",
                "date_start": "2026-01-01",
                "date": "2026-03-31",
            }
        )
        cls.role1 = cls.env["project.plan.role"].create({"name": "Project Manager"})
        cls.role2 = cls.env["project.plan.role"].create({"name": "Architect"})
        cls.user = cls.env.user

    def test_generate_month_range(self):
        months = self.project._generate_month_range(
            date(2026, 1, 15), date(2026, 3, 10)
        )
        self.assertEqual(len(months), 3)
        self.assertEqual(months[0], date(2026, 1, 1))
        self.assertEqual(months[-1], date(2026, 3, 1))

    def test_onchange_plan_dates(self):
        self.project._onchange_plan_dates()
        line = self.env["project.plan.line"].create(
            {
                "project_id": self.project.id,
                "role_id": self.role1.id,
                "user_id": self.user.id,
            }
        )
        self.project._onchange_plan_dates()
        self.assertEqual(len(line.cell_ids), 3)

    def test_action_generate_plan(self):
        line = self.env["project.plan.line"].create(
            {
                "project_id": self.project.id,
                "role_id": self.role1.id,
                "user_id": self.user.id,
            }
        )
        self.project._onchange_plan_dates()
        jan_cell = line.cell_ids.filtered(lambda c: c.month.month == 1)
        jan_cell.capacity_percent = 50.0
        self.project.action_generate_plan()
        task = self.env["project.task"].search(
            [
                ("project_id", "=", self.project.id),
                ("name", "=", "Project Manager"),
            ],
            limit=1,
        )
        self.assertTrue(task.exists())
        self.assertEqual(task.allocated_hours, 80.0)
        self.assertEqual(len(task.hour_plan_ids), 1)
