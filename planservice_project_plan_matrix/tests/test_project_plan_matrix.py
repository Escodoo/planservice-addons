# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo import Command
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.float_utils import float_compare


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
        cls.stage = cls.env["project.plan.stage"].create({"name": "Stage 1"})
        cls.user = cls.env.user

    def _create_line(self, **vals):
        values = {
            "project_id": self.project.id,
            "role_id": self.role1.id,
            "user_id": self.user.id,
        }
        values.update(vals)
        return self.env["project.plan.line"].create(values)

    def test_generate_month_range(self):
        months = self.project._generate_month_range(
            date(2026, 1, 15), date(2026, 3, 10)
        )
        self.assertEqual(len(months), 3)
        self.assertEqual(months[0], date(2026, 1, 1))
        self.assertEqual(months[-1], date(2026, 3, 1))

    def test_generate_month_range_empty(self):
        self.assertEqual(self.project._generate_month_range(False, False), [])
        self.assertEqual(
            self.project._generate_month_range(date(2026, 3, 1), date(2026, 1, 1)), []
        )

    def test_compute_plan_months(self):
        self.project._compute_plan_months()
        self.assertEqual(self.project.plan_first_month, date(2026, 1, 1))
        self.assertEqual(self.project.plan_last_month, date(2026, 3, 1))

    def test_compute_plan_months_empty(self):
        project = self.env["project.project"].create({"name": "No dates"})
        project._compute_plan_months()
        self.assertFalse(project.plan_first_month)
        self.assertFalse(project.plan_last_month)

    def test_onchange_plan_dates(self):
        self.project._onchange_plan_dates()
        line = self._create_line()
        self.project._onchange_plan_dates()
        self.assertEqual(len(line.cell_ids), 3)

    def test_onchange_plan_dates_snaps(self):
        project = self.env["project.project"].new(
            {"date_start": date(2026, 1, 15), "date": date(2026, 3, 10)}
        )
        project._onchange_plan_dates()
        self.assertEqual(project.date_start, date(2026, 1, 1))
        self.assertEqual(project.date, date(2026, 3, 31))

    def test_update_plan_cells(self):
        line = self._create_line()
        self.project._update_plan_cells()
        self.assertEqual(len(line.cell_ids), 3)

    def test_write_dates_updates_cells(self):
        line = self._create_line()
        self.project.write({"date": "2026-04-30"})
        self.assertEqual(len(line.cell_ids), 4)

    def test_action_load_months(self):
        line = self._create_line()
        self.project.action_load_months()
        self.assertEqual(len(line.cell_ids), 3)

    def test_action_load_stages(self):
        line = self._create_line()
        self.env["project.plan.stage.month"].create(
            {
                "project_id": self.project.id,
                "stage_id": self.stage.id,
                "date_from": date(2026, 1, 1),
                "date_to": date(2026, 2, 28),
            }
        )
        self.project.action_load_stages()
        jan = line.cell_ids.filtered(lambda c: c.month.month == 1)
        self.assertEqual(jan.stage_id, self.stage)

    def test_action_generate_plan(self):
        line = self._create_line()
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

    def test_action_generate_plan_updates_existing(self):
        line = self._create_line()
        self.project._onchange_plan_dates()
        jan_cell = line.cell_ids.filtered(lambda c: c.month.month == 1)
        jan_cell.capacity_percent = 50.0
        self.project.action_generate_plan()
        task = self.env["project.task"].search(
            [("project_id", "=", self.project.id), ("name", "=", "Project Manager")]
        )
        jan_cell.capacity_percent = 100.0
        self.project.action_generate_plan()
        self.assertEqual(task.allocated_hours, 160.0)

    def test_action_generate_plan_task_with_timesheets(self):
        line = self._create_line()
        cells = {cell.month.month: cell for cell in line.cell_ids}
        cells[1].capacity_percent = 50.0
        self.project.action_generate_plan()
        task = self.project.task_ids.filtered(lambda t: t.name == "Project Manager")
        employee = self.env["hr.employee"].create({"name": "Plan Employee"})
        timesheet = self.env["account.analytic.line"].create(
            {
                "name": "Logged",
                "project_id": self.project.id,
                "task_id": task.id,
                "employee_id": employee.id,
                "date": date(2026, 1, 10),
                "unit_amount": 2.0,
            }
        )
        cells[1].capacity_percent = 0.0
        cells[2].capacity_percent = 50.0
        self.project.action_generate_plan()
        self.assertEqual(task.hour_plan_ids.mapped("month"), [date(2026, 2, 1)])
        self.assertEqual(task.planned_date_start.date().month, 2)
        self.assertEqual(task.allocated_hours, 80.0)
        self.assertTrue(timesheet.exists())
        self.assertEqual(timesheet.unit_amount, 2.0)

    def test_action_generate_plan_ignores_months_outside_project(self):
        line = self._create_line()
        for cell in line.cell_ids:
            cell.capacity_percent = 50.0
        self.project.date_start = date(2026, 2, 1)
        self.project.action_generate_plan()
        task = self.project.task_ids.filtered(lambda t: t.name == "Project Manager")
        self.assertEqual(
            task.hour_plan_ids.mapped("month"), [date(2026, 2, 1), date(2026, 3, 1)]
        )
        self.assertEqual(task.allocated_hours, 160.0)

    def test_action_generate_plan_no_cells(self):
        self._create_line()
        self.project.action_generate_plan()
        task = self.env["project.task"].search(
            [("project_id", "=", self.project.id), ("name", "=", "Project Manager")]
        )
        self.assertFalse(task)

    def test_action_generate_plan_creates_cargos_stage(self):
        self.env["project.task.type"].search([("name", "ilike", "cargos")]).write(
            {"name": "Old Stage"}
        )
        line = self._create_line()
        line.cell_ids.filtered(lambda c: c.month.month == 1).capacity_percent = 50.0
        self.project.action_generate_plan()
        task = self.project.task_ids.filtered(lambda t: t.name == "Project Manager")
        self.assertEqual(task.stage_id.name, "Cargos")

    def test_project_without_dates(self):
        project = self.env["project.project"].create({"name": "No dates"})
        line = self._create_line(project_id=project.id)
        self.assertFalse(line.cell_ids)
        project._update_plan_cells()
        self.assertFalse(line.cell_ids)
        self.assertIsNone(project.action_load_months())

    def test_onchange_plan_dates_without_dates(self):
        project = self.env["project.project"].new({"name": "No dates"})
        project._onchange_plan_dates()
        self.assertFalse(project.date_start)
        self.assertFalse(project.date)

    def test_line_create_keeps_given_cells(self):
        line = self._create_line(
            cell_ids=[
                Command.create({"month": date(2026, 1, 1), "capacity_percent": 30.0})
            ]
        )
        self.assertEqual(len(line.cell_ids), 3)
        jan = line.cell_ids.filtered(lambda c: c.month.month == 1)
        self.assertEqual(jan.capacity_percent, 30.0)

    def test_action_load_stages_skips_incomplete_mapping(self):
        project = self.env["project.project"].new(
            {
                "name": "Draft",
                "stage_month_ids": [
                    Command.create(
                        {"date_from": date(2026, 1, 1), "date_to": date(2026, 1, 31)}
                    )
                ],
            }
        )
        self.assertTrue(project.action_load_stages())

    def test_sync_task_hour_plan_no_cells(self):
        line = self._create_line()
        task = self.env["project.task"].create(
            {"name": "Project Manager", "project_id": self.project.id}
        )
        self.project._sync_task_hour_plan(task, line, line.cell_ids.browse())
        self.assertFalse(task.hour_plan_ids)

    def test_sync_task_hour_plan(self):
        line = self._create_line()
        self.project._onchange_plan_dates()
        jan_cell = line.cell_ids.filtered(lambda c: c.month.month == 1)
        jan_cell.capacity_percent = 50.0
        task = self.env["project.task"].create(
            {"name": "Project Manager", "project_id": self.project.id}
        )
        cells = line.cell_ids.filtered(lambda c: c.capacity_percent > 0)
        self.project._sync_task_hour_plan(task, line, cells)
        self.assertEqual(len(task.hour_plan_ids), 1)

    def test_line_total_hours(self):
        line = self._create_line()
        jan_cell = line.cell_ids.filtered(lambda c: c.month.month == 1)
        jan_cell.capacity_percent = 50.0
        self.assertEqual(float_compare(line.total_hours, 80.0, precision_digits=2), 0)

    def test_line_unique_constraint(self):
        self._create_line()
        with self.assertRaises(ValidationError):
            self._create_line()

    def test_cell_name(self):
        line = self._create_line()
        jan_cell = line.cell_ids.filtered(lambda c: c.month.month == 1)
        self.assertTrue(jan_cell.name)

    def test_cell_monthly_hours(self):
        line = self._create_line()
        jan_cell = line.cell_ids.filtered(lambda c: c.month.month == 1)
        self.assertEqual(
            float_compare(jan_cell.monthly_hours, 160.0, precision_digits=2), 0
        )

    def test_cell_hours(self):
        line = self._create_line()
        jan_cell = line.cell_ids.filtered(lambda c: c.month.month == 1)
        jan_cell.capacity_percent = 25.0
        self.assertEqual(float_compare(jan_cell.hours, 40.0, precision_digits=2), 0)

    def test_cell_month_bounds(self):
        first, last = self.env["project.plan.cell"]._month_bounds(date(2026, 2, 15))
        self.assertEqual(first, date(2026, 2, 1))
        self.assertEqual(last, date(2026, 2, 28))

    def test_cell_apply_stage_to_range(self):
        line = self._create_line()
        cells = line.cell_ids
        cells.action_apply_stage_to_range(
            self.stage.id, date(2026, 1, 1), date(2026, 2, 28)
        )
        jan = line.cell_ids.filtered(lambda c: c.month.month == 1)
        mar = line.cell_ids.filtered(lambda c: c.month.month == 3)
        self.assertEqual(jan.stage_id, self.stage)
        self.assertFalse(mar.stage_id)

    def test_label_tasks_default(self):
        project = self.env["project.project"].create({"name": "Label Project"})
        self.assertEqual(project.label_tasks, "Cargo")

    def test_privacy_visibility_default(self):
        project = self.env["project.project"].create({"name": "Private Project"})
        self.assertEqual(project.privacy_visibility, "followers")

    def test_milestones_disabled(self):
        milestone_group = self.env.ref("project.group_project_milestone")
        self.assertNotIn(milestone_group, self.env.ref("base.group_user").implied_ids)
        self.assertFalse(milestone_group.users)
        # The superuser passes every has_group() check, so use a real user.
        admin = self.env.ref("base.user_admin")
        project = (
            self.env["project.project"]
            .with_user(admin)
            .create({"name": "No Milestones"})
        )
        self.assertFalse(project.allow_milestones)
