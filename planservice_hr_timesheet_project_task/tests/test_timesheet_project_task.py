# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date

from odoo.tests import TransactionCase, tagged
from odoo.tools.float_utils import float_compare


@tagged("post_install", "-at_install")
class TestTimesheetProjectTask(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create(
            {
                "name": "Timesheet Project",
                "allow_timesheets": True,
                "date_start": "2026-01-01",
                "date": "2026-03-31",
            }
        )
        cls.other_project = cls.env["project.project"].create(
            {"name": "Other Project", "allow_timesheets": True}
        )
        cls.role = cls.env["project.plan.role"].create({"name": "Architect"})
        cls.user = cls.env.user
        cls.task = cls.env["project.task"].create(
            {
                "name": "Architect",
                "project_id": cls.project.id,
                "user_ids": [(4, cls.user.id)],
            }
        )
        cls.other_task = cls.env["project.task"].create(
            {
                "name": "Other Task",
                "project_id": cls.other_project.id,
                "user_ids": [(4, cls.user.id)],
            }
        )
        cls.location = cls.env["timesheet.location"].create({"name": "Remote"})
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Timesheet Employee", "employee_type": "freelance"}
        )
        cls.date = date(2026, 1, 15)

    def _create_line(self, **vals):
        values = {
            "name": "Timesheet",
            "project_id": self.project.id,
            "task_id": self.task.id,
            "employee_id": self.employee.id,
            "date": self.date,
        }
        values.update(vals)
        return self.env["account.analytic.line"].create(values)

    def test_location_field(self):
        line = self._create_line(location_id=self.location.id)
        self.assertEqual(line.location_id, self.location)

    def test_attachment_count(self):
        line = self._create_line()
        self.assertEqual(line.attachment_count, 0)
        attachment = self.env["ir.attachment"].create(
            {"name": "test.txt", "raw": b"data"}
        )
        line.attachment_ids = [(4, attachment.id)]
        self.assertEqual(line.attachment_count, 1)

    def test_domain_project_id_manager(self):
        self.env.user.groups_id |= self.env.ref("hr_timesheet.group_timesheet_manager")
        domain = self.env["account.analytic.line"]._domain_project_id()
        self.assertIn(("allow_timesheets", "=", True), domain)

    def test_domain_project_id_user(self):
        self.env.user.groups_id -= self.env.ref("hr_timesheet.group_timesheet_manager")
        domain = self.env["account.analytic.line"]._domain_project_id()
        id_domain = next(
            item for item in domain if isinstance(item, tuple) and item[0] == "id"
        )
        self.assertLessEqual(
            {self.project.id, self.other_project.id}, set(id_domain[2])
        )

    def test_get_default_task(self):
        task = self.env["account.analytic.line"]._get_default_task(self.project.id)
        self.assertEqual(task, self.task)

    def test_get_default_task_no_project(self):
        task = self.env["account.analytic.line"]._get_default_task(False)
        self.assertFalse(task)

    def test_onchange_project_id(self):
        line = self.env["account.analytic.line"].new(
            {"project_id": self.project.id, "date": self.date}
        )
        line._onchange_project_id()
        self.assertEqual(line.task_id, self.task)

    def test_get_planned_percentage_no_task(self):
        line = self.env["account.analytic.line"].new({})
        self.assertEqual(line._get_planned_percentage(False, self.date), 0.0)

    def test_get_planned_percentage_no_line(self):
        line = self.env["account.analytic.line"].new({})
        self.assertEqual(line._get_planned_percentage(self.task.id, self.date), 0.0)

    def test_get_planned_percentage_with_plan(self):
        plan_line = self.env["project.plan.line"].create(
            {
                "project_id": self.project.id,
                "role_id": self.role.id,
                "user_id": self.user.id,
            }
        )
        cell = plan_line.cell_ids.filtered(lambda c: c.month.month == 1)
        cell.capacity_percent = 50.0
        line = self.env["account.analytic.line"].new({})
        self.assertEqual(line._get_planned_percentage(self.task.id, self.date), 50.0)

    def test_create_auto_task(self):
        line = self.env["account.analytic.line"].create(
            {
                "name": "Auto task",
                "project_id": self.project.id,
                "employee_id": self.employee.id,
                "date": self.date,
            }
        )
        self.assertEqual(line.task_id, self.task)

    def test_create_auto_unit_amount(self):
        plan_line = self.env["project.plan.line"].create(
            {
                "project_id": self.project.id,
                "role_id": self.role.id,
                "user_id": self.user.id,
            }
        )
        cell = plan_line.cell_ids.filtered(lambda c: c.month.month == 1)
        cell.capacity_percent = 50.0
        line = self.env["account.analytic.line"].create(
            {
                "name": "Auto hours",
                "project_id": self.project.id,
                "task_id": self.task.id,
                "employee_id": self.employee.id,
                "date": self.date,
            }
        )
        hours_per_day = line._get_timesheet_hours_per_day()
        self.assertEqual(
            float_compare(line.unit_amount, hours_per_day * 0.5, precision_digits=2),
            0,
        )

    def test_write_auto_task(self):
        line = self._create_line(task_id=False)
        line.write({"project_id": self.project.id})
        self.assertEqual(line.task_id, self.task)

    def test_onchange_planned_percentage(self):
        plan_line = self.env["project.plan.line"].create(
            {
                "project_id": self.project.id,
                "role_id": self.role.id,
                "user_id": self.user.id,
            }
        )
        cell = plan_line.cell_ids.filtered(lambda c: c.month.month == 1)
        cell.capacity_percent = 25.0
        line = self.env["account.analytic.line"].new(
            {
                "project_id": self.project.id,
                "task_id": self.task.id,
                "date": self.date,
            }
        )
        line._onchange_planned_percentage()
        hours_per_day = line._get_timesheet_hours_per_day()
        self.assertEqual(
            float_compare(line.unit_amount, hours_per_day * 0.25, precision_digits=2),
            0,
        )

    def test_attachment_wizard_action_attach(self):
        line = self._create_line()
        attachment = self.env["ir.attachment"].create(
            {"name": "wizard.txt", "raw": b"data"}
        )
        wizard = self.env["timesheet.attachment.wizard"].create(
            {
                "line_id": line.id,
                "attachment_ids": [(4, attachment.id)],
            }
        )
        result = wizard.action_attach()
        self.assertEqual(result["type"], "ir.actions.act_window_close")
        self.assertIn(attachment, line.attachment_ids)
