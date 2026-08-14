# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import timedelta

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools.float_utils import float_compare


@tagged("post_install", "-at_install")
class TestHrTimesheetDayPercentage(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project_a = cls.env["project.project"].create(
            {"name": "Day % Project A", "allow_timesheets": True}
        )
        cls.project_b = cls.env["project.project"].create(
            {"name": "Day % Project B", "allow_timesheets": True}
        )
        cls.task_a = cls.env["project.task"].create(
            {"name": "Task A", "project_id": cls.project_a.id}
        )
        cls.task_b = cls.env["project.task"].create(
            {"name": "Task B", "project_id": cls.project_b.id}
        )
        cls.employee = cls.env["hr.employee"].create(
            {"name": "Day % Employee", "employee_type": "freelance"}
        )
        cls.employee_other = cls.env["hr.employee"].create(
            {"name": "Day % Other Employee", "employee_type": "freelance"}
        )
        calendar = (
            cls.employee.resource_calendar_id or cls.env.company.resource_calendar_id
        )
        cls.hours_per_day = calendar.hours_per_day if calendar else 8.0
        cls.date = fields.Date.today()

    def _create_timesheet(self, **vals):
        values = {
            "name": "Timesheet",
            "project_id": self.project_a.id,
            "task_id": self.task_a.id,
            "employee_id": self.employee.id,
            "date": self.date,
        }
        values.update(vals)
        return self.env["account.analytic.line"].create(values)

    def test_day_percentage_sets_hours(self):
        line = self._create_timesheet(day_percentage=50.0)
        self.assertEqual(
            float_compare(
                line.unit_amount, self.hours_per_day * 0.5, precision_digits=2
            ),
            0,
        )
        self.assertEqual(
            float_compare(line.day_percentage, 50.0, precision_digits=2), 0
        )

    def test_hours_set_day_percentage(self):
        line = self._create_timesheet(unit_amount=self.hours_per_day * 0.25)
        self.assertEqual(
            float_compare(line.day_percentage, 25.0, precision_digits=2), 0
        )
        line.unit_amount = self.hours_per_day * 0.5
        self.assertEqual(
            float_compare(line.day_percentage, 50.0, precision_digits=2), 0
        )

    def test_edit_day_percentage_updates_hours(self):
        line = self._create_timesheet(unit_amount=self.hours_per_day * 0.25)
        line.day_percentage = 50.0
        self.assertEqual(
            float_compare(
                line.unit_amount, self.hours_per_day * 0.5, precision_digits=2
            ),
            0,
        )

    def test_split_across_projects_and_tasks_up_to_100(self):
        first = self._create_timesheet(day_percentage=40.0)
        second = self._create_timesheet(
            name="Other project",
            project_id=self.project_b.id,
            task_id=self.task_b.id,
            day_percentage=60.0,
        )
        self.assertEqual(
            float_compare(
                first.day_percentage + second.day_percentage,
                100.0,
                precision_digits=2,
            ),
            0,
        )

    def test_cannot_exceed_100_percent_same_day(self):
        self._create_timesheet(day_percentage=40.0)
        self._create_timesheet(
            name="Other project",
            project_id=self.project_b.id,
            task_id=self.task_b.id,
            day_percentage=60.0,
        )
        with self.assertRaises(ValidationError):
            self._create_timesheet(day_percentage=1.0)

    def test_other_employee_can_log_full_day(self):
        self._create_timesheet(day_percentage=100.0)
        other = self._create_timesheet(
            employee_id=self.employee_other.id,
            day_percentage=100.0,
        )
        self.assertEqual(
            float_compare(other.day_percentage, 100.0, precision_digits=2), 0
        )

    def test_cannot_move_line_to_full_day(self):
        self._create_timesheet(day_percentage=100.0)
        other_day = self.date + timedelta(days=1)
        line = self._create_timesheet(date=other_day, day_percentage=10.0)
        with self.assertRaises(ValidationError):
            line.date = self.date

    def test_onchange_day_percentage_and_hours(self):
        line = self.env["account.analytic.line"].new(
            {
                "name": "Onchange",
                "project_id": self.project_a.id,
                "task_id": self.task_a.id,
                "employee_id": self.employee.id,
                "date": self.date,
                "unit_amount": 0.0,
            }
        )
        line.day_percentage = 25.0
        line._onchange_day_percentage()
        self.assertEqual(
            float_compare(
                line.unit_amount, self.hours_per_day * 0.25, precision_digits=2
            ),
            0,
        )
        line.unit_amount = self.hours_per_day
        line._onchange_unit_amount_day_percentage()
        self.assertEqual(
            float_compare(line.day_percentage, 100.0, precision_digits=2), 0
        )

    def test_create_with_both_uses_percentage_inverse(self):
        line = self._create_timesheet(day_percentage=50.0, unit_amount=1.0)
        self.assertEqual(
            float_compare(
                line.unit_amount, self.hours_per_day * 0.5, precision_digits=2
            ),
            0,
        )

    def test_write_hours_cannot_exceed_day(self):
        line = self._create_timesheet(day_percentage=50.0)
        with self.assertRaises(ValidationError):
            line.unit_amount = self.hours_per_day * 1.1

    def test_batch_create_same_day_up_to_100(self):
        lines = self.env["account.analytic.line"].create(
            [
                {
                    "name": "First",
                    "project_id": self.project_a.id,
                    "task_id": self.task_a.id,
                    "employee_id": self.employee.id,
                    "date": self.date,
                    "day_percentage": 40.0,
                },
                {
                    "name": "Second",
                    "project_id": self.project_b.id,
                    "task_id": self.task_b.id,
                    "employee_id": self.employee.id,
                    "date": self.date,
                    "day_percentage": 60.0,
                },
            ]
        )
        self.assertEqual(
            float_compare(
                sum(lines.mapped("day_percentage")), 100.0, precision_digits=2
            ),
            0,
        )

    def test_batch_create_same_day_cannot_exceed_100(self):
        with self.assertRaises(ValidationError):
            self.env["account.analytic.line"].create(
                [
                    {
                        "name": "First",
                        "project_id": self.project_a.id,
                        "task_id": self.task_a.id,
                        "employee_id": self.employee.id,
                        "date": self.date,
                        "day_percentage": 60.0,
                    },
                    {
                        "name": "Second",
                        "project_id": self.project_b.id,
                        "task_id": self.task_b.id,
                        "employee_id": self.employee.id,
                        "date": self.date,
                        "day_percentage": 50.0,
                    },
                ]
            )

    def test_non_timesheet_line_skips_day_capacity(self):
        line = self.env["account.analytic.line"].create(
            {
                "name": "Not a timesheet",
                "employee_id": self.employee.id,
                "date": self.date,
                "unit_amount": self.hours_per_day * 3,
            }
        )
        self.assertFalse(line.project_id)
        self.assertGreater(line.unit_amount, self.hours_per_day)

    def test_employee_without_calendar_uses_company(self):
        self.employee.resource_calendar_id = False
        line = self._create_timesheet(day_percentage=50.0)
        company_hours = self.env.company.resource_calendar_id.hours_per_day
        self.assertEqual(
            float_compare(line.unit_amount, company_hours * 0.5, precision_digits=2),
            0,
        )

    def test_no_calendar_falls_back_to_eight_hours(self):
        company = self.env["res.company"].create({"name": "No Calendar Co"})
        company.resource_calendar_id = False
        hours = self.env["account.analytic.line"]._hours_per_day_for_vals(
            {"company_id": company.id}
        )
        self.assertEqual(float_compare(hours, 8.0, precision_digits=2), 0)
        line = (
            self.env["account.analytic.line"]
            .with_company(company)
            .new({"company_id": company.id, "unit_amount": 4.0})
        )
        self.assertEqual(
            float_compare(line._get_timesheet_hours_per_day(), 8.0, precision_digits=2),
            0,
        )

    def test_zero_hours_calendar_refuses_timesheet(self):
        calendar = self.env["resource.calendar"].create(
            {"name": "No Hours", "attendance_ids": [(5, 0, 0)]}
        )
        self.employee.resource_calendar_id = calendar
        self.assertEqual(
            float_compare(calendar.hours_per_day, 0.0, precision_digits=2), 0
        )
        with self.assertRaises(ValidationError):
            self._create_timesheet(unit_amount=1.0)

    def test_zero_hours_calendar_computes_zero_percentage(self):
        calendar = self.env["resource.calendar"].create(
            {"name": "No Hours Compute", "attendance_ids": [(5, 0, 0)]}
        )
        self.employee.resource_calendar_id = calendar
        line = self.env["account.analytic.line"].new(
            {
                "employee_id": self.employee.id,
                "company_id": self.env.company.id,
                "unit_amount": 4.0,
            }
        )
        line._compute_day_percentage()
        self.assertEqual(float_compare(line.day_percentage, 0.0, precision_digits=2), 0)

    def test_hours_per_day_for_vals_uses_employee_calendar(self):
        hours = self.env["account.analytic.line"]._hours_per_day_for_vals(
            {"employee_id": self.employee.id}
        )
        self.assertEqual(
            float_compare(hours, self.hours_per_day, precision_digits=2), 0
        )
