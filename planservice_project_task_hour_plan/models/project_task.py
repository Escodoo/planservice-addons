# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from calendar import monthrange
from datetime import datetime, time

import pytz
from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models
from odoo.tools.float_utils import float_compare, float_is_zero, float_round


class ProjectTask(models.Model):
    _inherit = "project.task"

    hour_plan_ids = fields.One2many(
        comodel_name="project.task.hour.plan",
        inverse_name="task_id",
        string="Hour Plan",
        copy=True,
    )
    hour_plan_manual = fields.Boolean(
        string="Hour Plan Manually Adjusted",
        copy=True,
        help="When set, changing allocated hours or planned dates will not "
        "rebuild the monthly hour plan.",
    )
    hour_plan_drives_task = fields.Boolean(
        copy=True,
        help="When set, the hour plan updates allocated time and planned "
        "dates. Set automatically when the plan is filled first.",
    )
    hour_plan_hours = fields.Float(
        string="Planned Hours Total",
        compute="_compute_hour_plan_totals",
        digits=(16, 2),
    )
    hour_plan_diff = fields.Float(
        string="Hour Plan Difference",
        compute="_compute_hour_plan_totals",
        digits=(16, 2),
        help="Allocated time minus the sum of monthly planned hours.",
    )
    hour_plan_outdated = fields.Boolean(
        compute="_compute_hour_plan_outdated",
    )

    def _hour_plan_trigger_fields(self):
        return ("allocated_hours", "planned_date_start", "planned_date_end")

    def _hour_plan_date(self, value):
        """Convert a datetime (UTC naive) or date to a date in the user timezone."""
        if not value:
            return False
        if isinstance(value, datetime):
            return fields.Datetime.context_timestamp(self, value).date()
        return value

    def _date_to_planned_datetime(self, day):
        """Store a calendar date as a naive UTC datetime that maps back to *day*."""
        if not day:
            return False
        local = datetime.combine(day, time(12, 0, 0))
        tz_name = self.env.context.get("tz") or self.env.user.tz or "UTC"
        context_tz = pytz.timezone(tz_name)
        return (
            context_tz.localize(local, is_dst=False)
            .astimezone(pytz.utc)
            .replace(tzinfo=None)
        )

    def _sync_task_from_hour_plan(self, update_allocated=None, update_dates=True):
        """Fill allocated hours and/or planned dates from the monthly hour plan."""
        if self.env.context.get("skip_hour_plan_generate"):
            return
        for task in self:
            lines = task.hour_plan_ids
            vals = {}
            if update_allocated is None:
                update_allocated = task.hour_plan_drives_task or float_is_zero(
                    task.allocated_hours, precision_digits=2
                )
            if update_allocated:
                total = float_round(sum(lines.mapped("hours")), precision_digits=2)
                if float_compare(task.allocated_hours, total, precision_digits=2):
                    vals["allocated_hours"] = total
            if update_dates and lines:
                date_from = min(lines.mapped("date_from"))
                date_to = max(lines.mapped("date_to"))
                if task._hour_plan_date(task.planned_date_start) != date_from:
                    vals["planned_date_start"] = task._date_to_planned_datetime(
                        date_from
                    )
                if task._hour_plan_date(task.planned_date_end) != date_to:
                    vals["planned_date_end"] = task._date_to_planned_datetime(date_to)
            if vals:
                task.with_context(skip_hour_plan_generate=True).write(vals)

    def _get_hour_plan_periods(self):
        """Return full calendar months covering the planned date window."""
        self.ensure_one()
        start = self._hour_plan_date(self.planned_date_start)
        end = self._hour_plan_date(self.planned_date_end)
        if not start or not end or end < start:
            return []
        periods = []
        cursor = start.replace(day=1)
        end_month = end.replace(day=1)
        while cursor <= end_month:
            last_day = monthrange(cursor.year, cursor.month)[1]
            periods.append((cursor, cursor.replace(day=last_day)))
            cursor += relativedelta(months=1)
        return periods

    def _split_hours_evenly(self, total, count):
        """Split *total* into *count* parts; put the rounding remainder on the last."""
        if count <= 0:
            return []
        base = float_round(total / count, precision_digits=2)
        hours = [base] * count
        hours[-1] = float_round(total - base * (count - 1), precision_digits=2)
        return hours

    def _generate_hour_plan_lines(self):
        for task in self:
            periods = task._get_hour_plan_periods()
            # Unlink first: clear+create in the same write hits the month unique
            # constraint because inserts run before deletes.
            task.hour_plan_ids.with_context(skip_hour_plan_generate=True).unlink()
            if periods and not float_is_zero(task.allocated_hours, precision_digits=2):
                hours_list = task._split_hours_evenly(
                    task.allocated_hours, len(periods)
                )
                task.with_context(skip_hour_plan_generate=True).write(
                    {
                        "hour_plan_ids": [
                            Command.create(
                                {
                                    "date_from": date_from,
                                    "date_to": date_to,
                                    "hours": hours,
                                }
                            )
                            for (date_from, date_to), hours in zip(
                                periods, hours_list, strict=True
                            )
                        ]
                    }
                )

    def action_reset_hour_plan(self):
        self.write({"hour_plan_manual": False, "hour_plan_drives_task": False})
        self._generate_hour_plan_lines()
        return True

    @api.depends("hour_plan_ids.hours", "allocated_hours")
    def _compute_hour_plan_totals(self):
        for task in self:
            total = sum(task.hour_plan_ids.mapped("hours"))
            task.hour_plan_hours = total
            task.hour_plan_diff = float_round(
                task.allocated_hours - total, precision_digits=2
            )

    @api.depends(
        "hour_plan_ids.date_from",
        "hour_plan_ids.date_to",
        "planned_date_start",
        "planned_date_end",
    )
    def _compute_hour_plan_outdated(self):
        for task in self:
            expected = {
                date_from for date_from, _date_to in task._get_hour_plan_periods()
            }
            actual = {line.month for line in task.hour_plan_ids}
            task.hour_plan_outdated = bool(actual) and actual != expected

    @api.model_create_multi
    def create(self, vals_list):
        tasks = super().create(vals_list)
        if self.env.context.get("skip_hour_plan_generate"):
            return tasks
        tasks.filtered(
            lambda task: not task.hour_plan_manual
            and not task.hour_plan_ids
            and task.allocated_hours
            and task.planned_date_start
            and task.planned_date_end
        )._generate_hour_plan_lines()
        return tasks

    def copy(self, default=None):
        return super(ProjectTask, self.with_context(skip_hour_plan_generate=True)).copy(
            default
        )

    def write(self, vals):
        if self.env.context.get("skip_hour_plan_generate"):
            return super().write(vals)
        trigger_fields = self._hour_plan_trigger_fields()
        regenerating = any(field in vals for field in trigger_fields)
        extra = {}
        if "hour_plan_ids" in vals and not regenerating:
            extra["hour_plan_manual"] = True
        if regenerating:
            extra["hour_plan_drives_task"] = False
        if extra:
            vals = dict(vals, **extra)
        res = super().write(vals)
        if regenerating:
            self.filtered(
                lambda task: not task.hour_plan_manual
            )._generate_hour_plan_lines()
        return res
