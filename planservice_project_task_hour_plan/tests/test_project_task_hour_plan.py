# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, datetime

from psycopg2.errors import UniqueViolation

from odoo import Command, fields
from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger
from odoo.tools.float_utils import float_compare


@tagged("post_install", "-at_install")
class TestProjectTaskHourPlan(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env.user.tz = "UTC"
        cls.project = cls.env["project.project"].create({"name": "Hour Plan Project"})

    def _create_task(self, allocated_hours, start, end, **vals):
        values = {
            "name": "Architect hours",
            "project_id": self.project.id,
            "allocated_hours": allocated_hours,
            "planned_date_start": start,
            "planned_date_end": end,
        }
        values.update(vals)
        return self.env["project.task"].create(values)

    def test_equal_split_four_months(self):
        task = self._create_task(
            200.0,
            datetime(2026, 1, 15, 12, 0, 0),
            datetime(2026, 4, 10, 12, 0, 0),
        )
        self.assertEqual(len(task.hour_plan_ids), 4)
        self.assertEqual(task.hour_plan_ids.mapped("hours"), [50.0, 50.0, 50.0, 50.0])
        self.assertEqual(task.hour_plan_ids[0].month.isoformat(), "2026-01-01")
        self.assertEqual(task.hour_plan_ids[0].date_from.isoformat(), "2026-01-01")
        self.assertEqual(task.hour_plan_ids[0].date_to.isoformat(), "2026-01-31")
        self.assertEqual(task.hour_plan_ids[1].date_from.isoformat(), "2026-02-01")
        self.assertEqual(task.hour_plan_ids[1].date_to.isoformat(), "2026-02-28")
        self.assertEqual(task.hour_plan_ids[-1].date_from.isoformat(), "2026-04-01")
        self.assertEqual(task.hour_plan_ids[-1].date_to.isoformat(), "2026-04-30")
        self.assertFalse(task.hour_plan_manual)
        self.assertEqual(float_compare(task.hour_plan_diff, 0.0, precision_digits=2), 0)
        self.assertFalse(task.hour_plan_outdated)

    def test_remainder_on_last_month(self):
        task = self._create_task(
            200.0,
            datetime(2026, 1, 1, 12, 0, 0),
            datetime(2026, 3, 31, 12, 0, 0),
        )
        hours = task.hour_plan_ids.mapped("hours")
        self.assertEqual(len(hours), 3)
        self.assertEqual(hours[0], hours[1])
        self.assertEqual(sum(hours), 200.0)

    def test_single_month(self):
        task = self._create_task(
            40.0,
            datetime(2026, 2, 5, 12, 0, 0),
            datetime(2026, 2, 20, 12, 0, 0),
        )
        self.assertEqual(len(task.hour_plan_ids), 1)
        self.assertEqual(task.hour_plan_ids.hours, 40.0)
        self.assertEqual(task.hour_plan_ids.month.isoformat(), "2026-02-01")
        self.assertEqual(task.hour_plan_ids.date_from.isoformat(), "2026-02-01")
        self.assertEqual(task.hour_plan_ids.date_to.isoformat(), "2026-02-28")

    def test_manual_edit_is_kept_when_hours_change(self):
        task = self._create_task(
            200.0,
            datetime(2026, 1, 15, 12, 0, 0),
            datetime(2026, 4, 10, 12, 0, 0),
        )
        lines = task.hour_plan_ids.sorted("date_from")
        lines[0].hours = 20.0
        lines[1].hours = 100.0
        lines[2].hours = 40.0
        lines[3].hours = 40.0
        self.assertTrue(task.hour_plan_manual)
        task.allocated_hours = 180.0
        self.assertEqual(
            task.hour_plan_ids.sorted("date_from").mapped("hours"),
            [
                20.0,
                100.0,
                40.0,
                40.0,
            ],
        )
        self.assertEqual(
            float_compare(task.hour_plan_diff, -20.0, precision_digits=2), 0
        )

    def test_reset_equal_split(self):
        task = self._create_task(
            200.0,
            datetime(2026, 1, 15, 12, 0, 0),
            datetime(2026, 4, 10, 12, 0, 0),
        )
        task.hour_plan_ids[0].hours = 20.0
        self.assertTrue(task.hour_plan_manual)
        task.action_reset_hour_plan()
        self.assertFalse(task.hour_plan_manual)
        self.assertEqual(task.hour_plan_ids.mapped("hours"), [50.0, 50.0, 50.0, 50.0])

    def test_auto_rebuild_when_not_manual(self):
        task = self._create_task(
            200.0,
            datetime(2026, 1, 15, 12, 0, 0),
            datetime(2026, 4, 10, 12, 0, 0),
        )
        task.planned_date_end = datetime(2026, 2, 28, 12, 0, 0)
        self.assertEqual(len(task.hour_plan_ids), 2)
        self.assertEqual(task.hour_plan_ids.mapped("hours"), [100.0, 100.0])

    def test_outdated_when_manual_and_dates_change(self):
        task = self._create_task(
            200.0,
            datetime(2026, 1, 15, 12, 0, 0),
            datetime(2026, 4, 10, 12, 0, 0),
        )
        task.hour_plan_ids[0].hours = 20.0
        task.planned_date_end = datetime(2026, 6, 30, 12, 0, 0)
        self.assertTrue(task.hour_plan_manual)
        self.assertEqual(len(task.hour_plan_ids), 4)
        self.assertTrue(task.hour_plan_outdated)

    def test_copy_keeps_manual_distribution(self):
        task = self._create_task(
            200.0,
            datetime(2026, 1, 15, 12, 0, 0),
            datetime(2026, 4, 10, 12, 0, 0),
        )
        lines = task.hour_plan_ids.sorted("date_from")
        lines[0].hours = 20.0
        lines[1].hours = 100.0
        lines[2].hours = 40.0
        lines[3].hours = 40.0
        copy = task.copy()
        self.assertTrue(copy.hour_plan_manual)
        self.assertEqual(
            copy.hour_plan_ids.sorted("date_from").mapped("hours"),
            [20.0, 100.0, 40.0, 40.0],
        )

    def test_days_encoding_still_stores_hours(self):
        self.env.company.timesheet_encode_uom_id = self.env.ref("uom.product_uom_day")
        task = self._create_task(
            16.0,
            datetime(2026, 1, 1, 12, 0, 0),
            datetime(2026, 2, 28, 12, 0, 0),
        )
        self.assertEqual(task.hour_plan_ids.mapped("hours"), [8.0, 8.0])
        self.assertEqual(sum(task.hour_plan_ids.mapped("hours")), 16.0)

    def test_capacity_percent_uses_configured_monthly_hours(self):
        self.env.company.hour_plan_monthly_hours = 160.0
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        line = task.hour_plan_ids
        self.assertEqual(
            float_compare(line.monthly_hours, 160.0, precision_digits=2), 0
        )
        self.assertEqual(
            float_compare(line.capacity_percent, 25.0, precision_digits=2), 0
        )

    def test_edit_capacity_percent_updates_hours(self):
        self.env.company.hour_plan_monthly_hours = 160.0
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        line = task.hour_plan_ids
        line.capacity_percent = 50.0
        self.assertEqual(float_compare(line.hours, 80.0, precision_digits=2), 0)
        self.assertTrue(task.hour_plan_manual)

    def test_edit_hours_updates_capacity_percent(self):
        self.env.company.hour_plan_monthly_hours = 160.0
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        line = task.hour_plan_ids
        line.hours = 80.0
        self.assertEqual(
            float_compare(line.capacity_percent, 50.0, precision_digits=2), 0
        )

    def test_plan_lines_fill_dates_and_allocated_hours(self):
        task = self.env["project.task"].create(
            {
                "name": "Plan first",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-01-15",
                            "date_to": "2026-01-31",
                            "hours": 40.0,
                        }
                    ),
                    Command.create(
                        {
                            "date_from": "2026-02-01",
                            "date_to": "2026-02-28",
                            "hours": 80.0,
                        }
                    ),
                    Command.create(
                        {
                            "date_from": "2026-03-01",
                            "date_to": "2026-03-10",
                            "hours": 20.0,
                        }
                    ),
                ],
            }
        )
        self.assertTrue(task.hour_plan_manual)
        self.assertTrue(task.hour_plan_drives_task)
        self.assertEqual(
            float_compare(task.allocated_hours, 140.0, precision_digits=2), 0
        )
        self.assertEqual(
            task._hour_plan_date(task.planned_date_start).isoformat(), "2026-01-01"
        )
        self.assertEqual(
            task._hour_plan_date(task.planned_date_end).isoformat(), "2026-03-31"
        )
        self.assertEqual(float_compare(task.hour_plan_diff, 0.0, precision_digits=2), 0)

    def test_edit_plan_hours_updates_allocated_hours(self):
        task = self.env["project.task"].create(
            {
                "name": "Plan first hours",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-02-01",
                            "date_to": "2026-02-28",
                            "hours": 40.0,
                        }
                    ),
                ],
            }
        )
        self.assertTrue(task.hour_plan_drives_task)
        task.hour_plan_ids.hours = 80.0
        self.assertEqual(
            float_compare(task.allocated_hours, 80.0, precision_digits=2), 0
        )
        self.assertEqual(float_compare(task.hour_plan_diff, 0.0, precision_digits=2), 0)

    def test_add_and_remove_plan_line_updates_task(self):
        task = self.env["project.task"].create(
            {
                "name": "Grow plan",
                "project_id": self.project.id,
            }
        )
        self.env["project.task.hour.plan"].create(
            {
                "task_id": task.id,
                "date_from": "2026-01-01",
                "date_to": "2026-01-31",
                "hours": 40.0,
            }
        )
        self.assertEqual(
            float_compare(task.allocated_hours, 40.0, precision_digits=2), 0
        )
        self.assertEqual(
            task._hour_plan_date(task.planned_date_start).isoformat(), "2026-01-01"
        )
        self.assertEqual(
            task._hour_plan_date(task.planned_date_end).isoformat(), "2026-01-31"
        )
        self.env["project.task.hour.plan"].create(
            {
                "task_id": task.id,
                "date_from": "2026-02-01",
                "date_to": "2026-02-28",
                "hours": 60.0,
            }
        )
        self.assertEqual(
            float_compare(task.allocated_hours, 100.0, precision_digits=2), 0
        )
        self.assertEqual(
            task._hour_plan_date(task.planned_date_end).isoformat(), "2026-02-28"
        )
        task.hour_plan_ids.filtered(lambda line: line.date_from.month == 2).unlink()
        self.assertEqual(
            float_compare(task.allocated_hours, 40.0, precision_digits=2), 0
        )
        self.assertEqual(
            task._hour_plan_date(task.planned_date_end).isoformat(), "2026-01-31"
        )

    def test_edit_plan_dates_updates_planned_dates(self):
        task = self.env["project.task"].create(
            {
                "name": "Shift plan",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-01-01",
                            "date_to": "2026-01-31",
                            "hours": 40.0,
                        }
                    ),
                ],
            }
        )
        task.hour_plan_ids.write({"month": "2026-03-05"})
        self.assertEqual(task.hour_plan_ids.month.isoformat(), "2026-03-01")
        self.assertEqual(task.hour_plan_ids.date_from.isoformat(), "2026-03-01")
        self.assertEqual(task.hour_plan_ids.date_to.isoformat(), "2026-03-31")
        self.assertEqual(
            task._hour_plan_date(task.planned_date_start).isoformat(), "2026-03-01"
        )
        self.assertEqual(
            task._hour_plan_date(task.planned_date_end).isoformat(), "2026-03-31"
        )

    def test_month_snaps_to_full_calendar_month(self):
        task = self.env["project.task"].create(
            {
                "name": "Snap month",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "month": "2026-04-18",
                            "hours": 16.0,
                        }
                    ),
                ],
            }
        )
        line = task.hour_plan_ids
        self.assertEqual(line.month.isoformat(), "2026-04-01")
        self.assertEqual(line.date_from.isoformat(), "2026-04-01")
        self.assertEqual(line.date_to.isoformat(), "2026-04-30")

    def test_duplicate_month_constraint(self):
        task = self.env["project.task"].create(
            {
                "name": "Duplicate month",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-02-01",
                            "date_to": "2026-02-28",
                            "hours": 8.0,
                        }
                    ),
                ],
            }
        )
        with mute_logger("odoo.sql_db"), self.assertRaises(UniqueViolation):
            self.env["project.task.hour.plan"].create(
                {
                    "task_id": task.id,
                    "month": "2026-02-10",
                    "hours": 8.0,
                }
            )

    def test_next_period_defaults_to_following_month(self):
        task = self.env["project.task"].create(
            {
                "name": "Defaults",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-01-01",
                            "date_to": "2026-01-31",
                            "hours": 40.0,
                        }
                    ),
                ],
            }
        )
        date_from, date_to = (
            self.env["project.task.hour.plan"]
            .with_context(default_task_id=task.id)
            ._next_period(task)
        )
        self.assertEqual(date_from.isoformat(), "2026-02-01")
        self.assertEqual(date_to.isoformat(), "2026-02-28")

    def test_line_name_is_month(self):
        task = self._create_task(
            40.0,
            datetime(2026, 2, 5, 12, 0, 0),
            datetime(2026, 2, 20, 12, 0, 0),
        )
        self.assertTrue(task.hour_plan_ids.name)
        empty = self.env["project.task.hour.plan"].new(
            {"month": False, "date_from": False, "date_to": False}
        )
        empty._compute_name()
        self.assertFalse(empty.name)

    def test_settings_related_field(self):
        settings = self.env["res.config.settings"].create({})
        settings.hour_plan_monthly_hours = 120.0
        self.assertEqual(
            float_compare(
                self.env.company.hour_plan_monthly_hours, 120.0, precision_digits=2
            ),
            0,
        )

    def test_default_get_next_month(self):
        task = self.env["project.task"].create(
            {
                "name": "Defaults",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-01-01",
                            "date_to": "2026-01-31",
                            "hours": 40.0,
                        }
                    ),
                ],
            }
        )
        vals = (
            self.env["project.task.hour.plan"]
            .with_context(default_task_id=task.id)
            .default_get(["date_from", "date_to", "month"])
        )
        self.assertEqual(vals["date_from"].isoformat(), "2026-02-01")
        self.assertEqual(vals["date_to"].isoformat(), "2026-02-28")
        self.assertEqual(vals["month"].isoformat(), "2026-02-01")

    def test_next_period_from_planned_start(self):
        task = self._create_task(
            40.0,
            datetime(2026, 3, 10, 12, 0, 0),
            datetime(2026, 3, 20, 12, 0, 0),
            hour_plan_manual=True,
        )
        self.assertFalse(task.hour_plan_ids)
        date_from, date_to = self.env["project.task.hour.plan"]._next_period(task)
        self.assertEqual(date_from.isoformat(), "2026-03-01")
        self.assertEqual(date_to.isoformat(), "2026-03-31")

    def test_next_period_defaults_to_today(self):
        today = fields.Date.context_today(self.env["project.task.hour.plan"])
        date_from, date_to = self.env["project.task.hour.plan"]._next_period(
            self.env["project.task"]
        )
        self.assertEqual(date_from, today.replace(day=1))
        self.assertEqual(date_to.month, today.month)

    def test_onchange_month_hours_and_capacity(self):
        self.env.company.hour_plan_monthly_hours = 160.0
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        line = task.hour_plan_ids
        line.month = date(2026, 7, 20)
        line._onchange_month()
        self.assertEqual(line.date_from, date(2026, 7, 1))
        self.assertEqual(line.date_to, date(2026, 7, 31))
        line.month = False
        self.assertIsNone(line._onchange_month())
        line.capacity_percent = 75.0
        line._onchange_capacity_percent()
        self.assertEqual(
            float_compare(line.hours, line.monthly_hours * 0.75, precision_digits=2),
            0,
        )
        line.hours = 40.0
        line._onchange_hours()
        self.assertEqual(
            float_compare(line.capacity_percent, 25.0, precision_digits=2), 0
        )

    def test_apply_month_bounds_from_date_to_or_empty(self):
        plan = self.env["project.task.hour.plan"]
        vals = plan._apply_month_bounds({"date_to": date(2026, 6, 20), "hours": 8.0})
        self.assertEqual(vals["month"], date(2026, 6, 1))
        self.assertEqual(vals["date_from"], date(2026, 6, 1))
        self.assertEqual(vals["date_to"], date(2026, 6, 30))
        unchanged = plan._apply_month_bounds({"hours": 10.0})
        self.assertEqual(unchanged, {"hours": 10.0})

    def test_write_date_to_snaps_to_month(self):
        task = self.env["project.task"].create(
            {
                "name": "Snap to",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-01-01",
                            "date_to": "2026-01-31",
                            "hours": 8.0,
                        }
                    ),
                ],
            }
        )
        task.hour_plan_ids.write({"date_to": date(2026, 8, 15)})
        self.assertEqual(task.hour_plan_ids.month, date(2026, 8, 1))
        self.assertEqual(task.hour_plan_ids.date_from, date(2026, 8, 1))
        self.assertEqual(task.hour_plan_ids.date_to, date(2026, 8, 31))

    def test_check_dates_constraint(self):
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        line = task.hour_plan_ids
        line._write({"date_from": date(2026, 3, 1), "date_to": date(2026, 2, 1)})
        line.invalidate_recordset(["date_from", "date_to"])
        with self.assertRaises(ValidationError):
            line._check_dates()

    def test_helpers_empty_and_date_inputs(self):
        task = self.env["project.task"].create(
            {"name": "Helpers", "project_id": self.project.id}
        )
        self.assertFalse(task._hour_plan_date(False))
        self.assertEqual(task._hour_plan_date(date(2026, 1, 15)), date(2026, 1, 15))
        self.assertFalse(task._date_to_planned_datetime(False))
        self.assertEqual(task._split_hours_evenly(100.0, 0), [])
        self.assertEqual(task._get_hour_plan_periods(), [])
        task._write(
            {
                "planned_date_start": datetime(2026, 3, 10, 12, 0, 0),
                "planned_date_end": datetime(2026, 2, 1, 12, 0, 0),
            }
        )
        task.invalidate_recordset(["planned_date_start", "planned_date_end"])
        self.assertEqual(task._get_hour_plan_periods(), [])

    def test_no_lines_without_dates_or_hours(self):
        no_dates = self.env["project.task"].create(
            {
                "name": "No dates",
                "project_id": self.project.id,
                "allocated_hours": 40.0,
            }
        )
        self.assertFalse(no_dates.hour_plan_ids)
        no_hours = self._create_task(
            0.0,
            datetime(2026, 1, 1, 12, 0, 0),
            datetime(2026, 2, 28, 12, 0, 0),
        )
        self.assertFalse(no_hours.hour_plan_ids)

    def test_skip_generate_on_create_and_write(self):
        task = (
            self.env["project.task"]
            .with_context(skip_hour_plan_generate=True)
            .create(
                {
                    "name": "Skip create",
                    "project_id": self.project.id,
                    "allocated_hours": 80.0,
                    "planned_date_start": datetime(2026, 1, 1, 12, 0, 0),
                    "planned_date_end": datetime(2026, 2, 28, 12, 0, 0),
                }
            )
        )
        self.assertFalse(task.hour_plan_ids)
        generated = self._create_task(
            80.0,
            datetime(2026, 1, 1, 12, 0, 0),
            datetime(2026, 2, 28, 12, 0, 0),
        )
        generated.with_context(skip_hour_plan_generate=True).write(
            {"planned_date_end": datetime(2026, 4, 30, 12, 0, 0)}
        )
        self.assertEqual(len(generated.hour_plan_ids), 2)

    def test_create_manual_skips_generate(self):
        task = self._create_task(
            80.0,
            datetime(2026, 1, 1, 12, 0, 0),
            datetime(2026, 2, 28, 12, 0, 0),
            hour_plan_manual=True,
        )
        self.assertFalse(task.hour_plan_ids)

    def test_edit_hours_on_generated_plan_keeps_allocated(self):
        task = self._create_task(
            200.0,
            datetime(2026, 1, 15, 12, 0, 0),
            datetime(2026, 4, 10, 12, 0, 0),
        )
        task.hour_plan_ids[0].hours = 10.0
        self.assertEqual(
            float_compare(task.allocated_hours, 200.0, precision_digits=2), 0
        )
        self.assertNotEqual(
            float_compare(task.hour_plan_diff, 0.0, precision_digits=2), 0
        )

    def test_changing_allocated_on_plan_driven_task_stops_driving(self):
        task = self.env["project.task"].create(
            {
                "name": "Driven",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-02-01",
                            "date_to": "2026-02-28",
                            "hours": 40.0,
                        }
                    ),
                ],
            }
        )
        self.assertTrue(task.hour_plan_drives_task)
        task.allocated_hours = 200.0
        self.assertFalse(task.hour_plan_drives_task)
        self.assertTrue(task.hour_plan_ids)

    def test_unlink_generated_line_marks_manual(self):
        task = self._create_task(
            80.0,
            datetime(2026, 1, 1, 12, 0, 0),
            datetime(2026, 2, 28, 12, 0, 0),
        )
        self.assertFalse(task.hour_plan_manual)
        task.hour_plan_ids[0].unlink()
        self.assertTrue(task.hour_plan_manual)

    def test_mark_plan_manual_skipped_by_context(self):
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        self.assertIsNone(
            task.hour_plan_ids.with_context(
                skip_hour_plan_generate=True
            )._mark_task_plan_manual()
        )
        self.assertFalse(task.hour_plan_manual)

    def test_unlink_all_lines_on_driven_task(self):
        task = self.env["project.task"].create(
            {
                "name": "Clear plan",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-02-01",
                            "date_to": "2026-02-28",
                            "hours": 40.0,
                        }
                    ),
                ],
            }
        )
        task.hour_plan_ids.unlink()
        self.assertEqual(
            float_compare(task.allocated_hours, 0.0, precision_digits=2), 0
        )

    def test_skip_unlink_does_not_sync_task(self):
        task = self.env["project.task"].create(
            {
                "name": "Skip unlink",
                "project_id": self.project.id,
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-02-01",
                            "date_to": "2026-02-28",
                            "hours": 40.0,
                        }
                    ),
                ],
            }
        )
        task.hour_plan_ids.with_context(skip_hour_plan_generate=True).unlink()
        self.assertEqual(
            float_compare(task.allocated_hours, 40.0, precision_digits=2), 0
        )

    def test_write_hour_plan_ids_sets_manual(self):
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        self.assertFalse(task.hour_plan_manual)
        task.write(
            {
                "hour_plan_ids": [
                    Command.create(
                        {
                            "date_from": "2026-03-01",
                            "date_to": "2026-03-31",
                            "hours": 8.0,
                        }
                    )
                ]
            }
        )
        self.assertTrue(task.hour_plan_manual)

    def test_monthly_hours_zero_falls_back_to_default(self):
        self.env.company.hour_plan_monthly_hours = 0.0
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        self.assertEqual(
            float_compare(task.hour_plan_ids.monthly_hours, 160.0, precision_digits=2),
            0,
        )

    def test_capacity_percent_when_monthly_hours_zero(self):
        line = self.env["project.task.hour.plan"].new(
            {"hours": 40.0, "monthly_hours": 0.0}
        )
        line._compute_capacity_percent()
        self.assertEqual(
            float_compare(line.capacity_percent, 0.0, precision_digits=2), 0
        )

    def test_timezone_roundtrip(self):
        self.env.user.tz = "America/Sao_Paulo"
        task = self.env["project.task"].create(
            {"name": "TZ", "project_id": self.project.id}
        )
        planned = task._date_to_planned_datetime(date(2026, 1, 15))
        self.assertEqual(task._hour_plan_date(planned), date(2026, 1, 15))

    def test_partner_related_on_plan_line(self):
        partner = self.env["res.partner"].create({"name": "Hour Plan Client"})
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
            partner_id=partner.id,
        )
        self.assertEqual(task.hour_plan_ids.partner_id, partner)

    def test_sync_skipped_by_context(self):
        task = self._create_task(
            40.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        self.assertIsNone(
            task.with_context(skip_hour_plan_generate=True)._sync_task_from_hour_plan()
        )
        self.assertIsNone(
            task.hour_plan_ids.with_context(
                skip_hour_plan_generate=True
            )._sync_related_tasks()
        )

    def test_company_monthly_hours_change_recomputes_capacity(self):
        self.env.company.hour_plan_monthly_hours = 160.0
        task = self._create_task(
            80.0,
            datetime(2026, 2, 2, 12, 0, 0),
            datetime(2026, 2, 6, 12, 0, 0),
        )
        line = task.hour_plan_ids
        self.assertEqual(
            float_compare(line.capacity_percent, 50.0, precision_digits=2), 0
        )
        company = (line.company_id or self.env.company).sudo()
        company.write({"hour_plan_monthly_hours": 80.0})
        line.invalidate_recordset(["monthly_hours", "capacity_percent"])
        line._compute_monthly_hours()
        line._compute_capacity_percent()
        self.assertEqual(
            float_compare(line.monthly_hours, 80.0, precision_digits=2),
            0,
            f"monthly_hours={line.monthly_hours} "
            f"company={company.hour_plan_monthly_hours}",
        )
        self.assertEqual(
            float_compare(line.capacity_percent, 100.0, precision_digits=2),
            0,
        )
