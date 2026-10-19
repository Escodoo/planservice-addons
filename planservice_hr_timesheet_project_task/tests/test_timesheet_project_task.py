# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, timedelta

from lxml import etree

from odoo import Command, fields
from odoo.exceptions import ValidationError
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
        cls.plan_line = cls.env["project.plan.line"].create(
            {
                "project_id": cls.project.id,
                "role_id": cls.role.id,
                "user_id": cls.user.id,
            }
        )
        cls.task = cls.env["project.task"].create(
            {
                "name": "Architect",
                "project_id": cls.project.id,
                "user_ids": [Command.link(cls.user.id)],
                "plan_line_id": cls.plan_line.id,
            }
        )
        cls.other_task = cls.env["project.task"].create(
            {
                "name": "Other Task",
                "project_id": cls.other_project.id,
                "user_ids": [Command.link(cls.user.id)],
            }
        )
        cls.location = cls.env["timesheet.location"].create({"name": "Remote"})
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Timesheet Employee", "employee_type": "freelance"}
        )
        cls.timesheet_user = cls.env["res.users"].create(
            {
                "name": "Timesheet Only",
                "login": "timesheet_only",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("hr_timesheet.group_hr_timesheet_user").id,
                        ]
                    )
                ],
            }
        )
        cls.timesheet_employee = cls.env["hr.employee"].create(
            {"name": "Timesheet Only", "user_id": cls.timesheet_user.id}
        )
        cls.manager_user = cls.env["res.users"].create(
            {
                "name": "Timesheet Manager",
                "login": "timesheet_manager",
                "groups_id": [
                    Command.set(
                        [
                            cls.env.ref("base.group_user").id,
                            cls.env.ref("project.group_project_manager").id,
                            cls.env.ref("hr_timesheet.group_timesheet_manager").id,
                        ]
                    )
                ],
            }
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

    def _set_capacity(self, plan_line, month, percent):
        plan_line.cell_ids.filtered(
            lambda c: c.month.month == month
        ).capacity_percent = percent

    def _get_user_employee(self):
        employee = self.env["hr.employee"].search(
            [("user_id", "=", self.user.id)], limit=1
        )
        return employee or self.env["hr.employee"].create(
            {"name": "Planned Employee", "user_id": self.user.id}
        )

    def _plan_for_timesheet_user(self, percent):
        plan_line = self.env["project.plan.line"].create(
            {
                "project_id": self.project.id,
                "role_id": self.role.id,
                "user_id": self.timesheet_user.id,
            }
        )
        self._set_capacity(plan_line, 1, percent)
        task = self.env["project.task"].create(
            {
                "name": "Architect",
                "project_id": self.project.id,
                "user_ids": [Command.link(self.timesheet_user.id)],
                "plan_line_id": plan_line.id,
            }
        )
        self.project.message_subscribe(partner_ids=self.timesheet_user.partner_id.ids)
        return task

    def test_location_field(self):
        line = self._create_line(location_id=self.location.id)
        self.assertEqual(line.location_id, self.location)

    def test_attachment_count(self):
        line = self._create_line()
        self.assertEqual(line.attachment_count, 0)
        attachment = self.env["ir.attachment"].create(
            {"name": "test.txt", "raw": b"data"}
        )
        line.attachment_ids = [Command.link(attachment.id)]
        self.assertEqual(line.attachment_count, 1)

    def test_attachment_linked_to_line(self):
        attachment = self.env["ir.attachment"].create(
            {"name": "upload.txt", "raw": b"data"}
        )
        line = self._create_line(attachment_ids=[Command.link(attachment.id)])
        self.assertEqual(attachment.res_model, "account.analytic.line")
        self.assertEqual(attachment.res_id, line.id)
        other = self.env["ir.attachment"].create({"name": "later.txt", "raw": b"x"})
        line.attachment_ids = [Command.link(other.id)]
        self.assertEqual((other.res_model, other.res_id), (line._name, line.id))

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

    def test_task_domain_by_manager_group(self):
        lines = self.env["account.analytic.line"]
        self.assertTrue(lines.with_user(self.manager_user).new().is_timesheet_manager)
        self.assertFalse(
            lines.with_user(self.timesheet_user).new().is_timesheet_manager
        )
        domain = lines._fields["task_id"].domain
        self.assertIn("'=?'", domain)
        self.assertIn("is_timesheet_manager", domain)

    def test_get_default_task(self):
        task = self.env["account.analytic.line"]._get_default_task(self.project.id)
        self.assertEqual(task, self.task)

    def test_get_default_task_no_project(self):
        task = self.env["account.analytic.line"]._get_default_task(False)
        self.assertFalse(task)

    def test_default_task_of_employee_user(self):
        task = self._plan_for_timesheet_user(50.0)
        line = (
            self.env["account.analytic.line"]
            .with_user(self.manager_user)
            .create(
                {
                    "name": "For a collaborator",
                    "project_id": self.project.id,
                    "employee_id": self.timesheet_employee.id,
                    "date": self.date,
                }
            )
        )
        self.assertEqual(line.task_id, task)

    def test_onchange_project_id(self):
        line = self.env["account.analytic.line"].new(
            {"project_id": self.project.id, "date": self.date}
        )
        line._onchange_project_id()
        self.assertEqual(line.task_id, self.task)

    def test_get_planned_percentage_no_task(self):
        lines = self.env["account.analytic.line"]
        self.assertEqual(
            lines._get_planned_percentage(lines.task_id, self.date, self.user), 0.0
        )

    def test_get_planned_percentage_no_plan_line(self):
        self.assertEqual(
            self.env["account.analytic.line"]._get_planned_percentage(
                self.other_task, self.date, self.user
            ),
            0.0,
        )

    def test_get_planned_percentage_with_plan(self):
        self._set_capacity(self.plan_line, 1, 50.0)
        lines = self.env["account.analytic.line"]
        self.assertEqual(
            lines._get_planned_percentage(self.task, self.date, self.user), 50.0
        )

    def test_get_planned_percentage_other_user(self):
        self._set_capacity(self.plan_line, 1, 50.0)
        lines = self.env["account.analytic.line"]
        self.assertEqual(
            lines._get_planned_percentage(self.task, self.date, self.timesheet_user),
            0.0,
        )

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
        self._set_capacity(self.plan_line, 1, 50.0)
        line = self._create_line(name="Auto hours")
        hours_per_day = line._get_timesheet_hours_per_day()
        self.assertEqual(
            float_compare(line.unit_amount, hours_per_day * 0.5, precision_digits=2),
            0,
        )

    def test_create_day_percentage_wins(self):
        self._set_capacity(self.plan_line, 1, 50.0)
        line = self._create_line(day_percentage=30.0)
        self.assertEqual(line.day_percentage, 30.0)
        hours_per_day = line._get_timesheet_hours_per_day()
        self.assertEqual(
            float_compare(line.unit_amount, hours_per_day * 0.3, precision_digits=2),
            0,
        )

    def test_timesheet_user_reads_plan(self):
        task = self._plan_for_timesheet_user(40.0)
        line = (
            self.env["account.analytic.line"]
            .with_user(self.timesheet_user)
            .create(
                {
                    "name": "Own timesheet",
                    "project_id": self.project.id,
                    "date": self.date,
                }
            )
        )
        self.assertEqual(line.task_id, task)
        self.assertEqual(line.planned_day_percentage, 40.0)
        hours_per_day = line._get_timesheet_hours_per_day()
        self.assertEqual(
            float_compare(line.unit_amount, hours_per_day * 0.4, precision_digits=2),
            0,
        )

    def test_write_auto_task(self):
        line = self._create_line(task_id=False)
        line.write({"project_id": self.project.id})
        self.assertEqual(line.task_id, self.task)

    def test_write_auto_task_keeps_existing_tasks(self):
        unassigned_task = self.env["project.task"].create(
            {"name": "Unassigned", "project_id": self.project.id, "user_ids": False}
        )
        line_with_task = self._create_line(task_id=unassigned_task.id)
        line_without_task = self._create_line()
        line_without_task.task_id = False
        (line_with_task | line_without_task).write({"project_id": self.project.id})
        self.assertEqual(line_with_task.task_id, unassigned_task)
        self.assertEqual(line_without_task.task_id, self.task)

    def test_onchange_project_id_no_project(self):
        line = self.env["account.analytic.line"].new({"date": self.date})
        line._onchange_project_id()
        self.assertFalse(line.task_id)

    def test_onchange_planned_percentage_no_task(self):
        line = self.env["account.analytic.line"].new({"unit_amount": 3.0})
        line._onchange_planned_percentage()
        self.assertEqual(line.unit_amount, 3.0)

    def test_onchange_planned_percentage_no_date(self):
        self._set_capacity(self.plan_line, 1, 50.0)
        line = self.env["account.analytic.line"].new(
            {"project_id": self.project.id, "task_id": self.task.id, "date": False}
        )
        line._onchange_planned_percentage()
        self.assertFalse(line.unit_amount)

    def test_onchange_planned_percentage_keeps_hours(self):
        self._set_capacity(self.plan_line, 1, 25.0)
        line = self.env["account.analytic.line"].new(
            {
                "project_id": self.project.id,
                "task_id": self.task.id,
                "date": self.date,
                "unit_amount": 3.0,
            }
        )
        line._onchange_planned_percentage()
        self.assertEqual(line.unit_amount, 3.0)

    def test_planned_day_percentage_no_task(self):
        line = self.env["account.analytic.line"].new({"date": self.date})
        self.assertEqual(line.planned_day_percentage, 0.0)

    def test_onchange_planned_percentage(self):
        self._set_capacity(self.plan_line, 1, 25.0)
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

    def test_planned_day_percentage(self):
        self._set_capacity(self.plan_line, 1, 40.0)
        self._set_capacity(self.plan_line, 2, 70.0)
        employee = self._get_user_employee()
        january = self._create_line(employee_id=employee.id, unit_amount=1.0)
        february = self._create_line(
            employee_id=employee.id, unit_amount=1.0, date=date(2026, 2, 10)
        )
        self.assertEqual(january.planned_day_percentage, 40.0)
        self.assertEqual(february.planned_day_percentage, 70.0)

    def test_plan_status(self):
        self._set_capacity(self.plan_line, 1, 50.0)
        employee = self._get_user_employee()
        line = self._create_line(employee_id=employee.id, day_percentage=50.0)
        self.assertEqual(line.plan_status, "on_plan")
        line.day_percentage = 50.01
        self.assertEqual(line.plan_status, "on_plan")
        line.day_percentage = 30.0
        self.assertEqual(line.plan_status, "below")
        line.day_percentage = 60.0
        self.assertEqual(line.plan_status, "above")

    def test_plan_status_nothing_planned(self):
        line = self._create_line(unit_amount=1.0)
        self.assertFalse(line.planned_day_percentage)
        self.assertFalse(line.plan_status)

    def test_planned_day_percentage_other_user(self):
        self._set_capacity(self.plan_line, 1, 40.0)
        line = self._create_line(unit_amount=1.0)
        self.assertEqual(line.planned_day_percentage, 0.0)

    def _visible_unit_amount(self, user, view_type):
        """Whether *user* sees a Time Spent field in the timesheet view."""
        lines = self.env["account.analytic.line"].with_user(user)
        view_ref = {
            "list": "hr_timesheet.hr_timesheet_line_tree",
            "form": "hr_timesheet.hr_timesheet_line_form",
        }[view_type]
        arch = lines.get_views([(self.env.ref(view_ref).id, view_type)])["views"][
            view_type
        ]["arch"]
        hidden_attr = "column_invisible" if view_type == "list" else "invisible"
        return any(
            node.get(hidden_attr) not in ("1", "True")
            for node in etree.fromstring(arch).xpath("//field[@name='unit_amount']")
        )

    def test_unit_amount_visible_for_managers(self):
        for view_type in ("list", "form"):
            self.assertFalse(self._visible_unit_amount(self.timesheet_user, view_type))
            self.assertTrue(self._visible_unit_amount(self.manager_user, view_type))

    def test_cannot_log_future_date(self):
        tomorrow = fields.Date.context_today(self.env.user) + timedelta(days=1)
        with self.assertRaises(ValidationError):
            self._create_line(unit_amount=1.0, date=tomorrow)

    def test_cannot_move_line_to_future_date(self):
        line = self._create_line(unit_amount=1.0)
        with self.assertRaises(ValidationError):
            line.date = fields.Date.context_today(line) + timedelta(days=1)

    def test_can_log_today(self):
        line = self._create_line(
            unit_amount=1.0, date=fields.Date.context_today(self.env.user)
        )
        self.assertTrue(line.exists())
