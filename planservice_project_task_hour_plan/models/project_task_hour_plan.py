# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from calendar import monthrange

from dateutil.relativedelta import relativedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools.float_utils import float_is_zero, float_round
from odoo.tools.misc import format_date


class ProjectTaskHourPlan(models.Model):
    _name = "project.task.hour.plan"
    _description = "Task Hour Plan"
    _order = "month, id"
    _sql_constraints = [
        (
            "task_month_uniq",
            "unique(task_id, month)",
            "A task cannot have two hour plan lines for the same month.",
        ),
    ]

    name = fields.Char(compute="_compute_name", store=True)
    task_id = fields.Many2one(
        comodel_name="project.task",
        required=True,
        ondelete="cascade",
        index=True,
    )
    project_id = fields.Many2one(
        related="task_id.project_id",
        store=True,
        index=True,
    )
    company_id = fields.Many2one(
        related="task_id.company_id",
        store=True,
        index=True,
    )
    partner_id = fields.Many2one(
        related="task_id.partner_id",
        store=True,
    )
    month = fields.Date(
        index=True,
        help="Calendar month of this line. From and To are the first and "
        "last day of that month.",
    )
    date_from = fields.Date(string="From", required=True, index=True)
    date_to = fields.Date(string="To", required=True)
    hours = fields.Float(required=True, digits=(16, 2))
    monthly_hours = fields.Float(
        compute="_compute_monthly_hours",
        store=True,
        digits=(16, 2),
        help="Hours of one resource used as 100% capacity for this month.",
    )
    capacity_percent = fields.Float(
        string="Capacity (%)",
        compute="_compute_capacity_percent",
        inverse="_inverse_capacity_percent",
        store=True,
        digits=(16, 2),
        help="Planned hours as a percentage of the configured monthly "
        "hours of one resource.",
    )

    @api.model
    def _month_bounds(self, day):
        """Return (first_day, last_day) of the calendar month of *day*."""
        first = fields.Date.to_date(day).replace(day=1)
        last_day = monthrange(first.year, first.month)[1]
        return first, first.replace(day=last_day)

    def _apply_month_bounds(self, vals):
        """Force From/To to the full calendar month of month or date_from."""
        vals = dict(vals)
        # Prefer an explicit month (UI / API). date_from is used when generating
        # lines, where default_get may also inject today's month.
        if vals.get("month"):
            day = vals["month"]
        elif vals.get("date_from"):
            day = vals["date_from"]
        elif vals.get("date_to"):
            day = vals["date_to"]
        else:
            return vals
        first, last = self._month_bounds(day)
        vals["month"] = first
        vals["date_from"] = first
        vals["date_to"] = last
        return vals

    @api.depends("month", "date_from")
    def _compute_name(self):
        for line in self:
            day = line.month or line.date_from
            line.name = (
                format_date(self.env, day, date_format="MMMM y") if day else False
            )

    def _get_monthly_hours(self):
        """Configured monthly hours of one resource (100% capacity)."""
        self.ensure_one()
        company = self.company_id or self.env.company
        return company.hour_plan_monthly_hours or 160.0

    @api.depends(
        "company_id",
        "company_id.hour_plan_monthly_hours",
        "task_id.company_id",
        "task_id.company_id.hour_plan_monthly_hours",
    )
    def _compute_monthly_hours(self):
        for line in self:
            line.monthly_hours = line._get_monthly_hours()

    @api.depends("hours", "monthly_hours")
    def _compute_capacity_percent(self):
        for line in self:
            if float_is_zero(line.monthly_hours, precision_digits=2):
                line.capacity_percent = 0.0
            else:
                line.capacity_percent = float_round(
                    line.hours / line.monthly_hours * 100.0, precision_digits=2
                )

    def _inverse_capacity_percent(self):
        for line in self:
            line.hours = float_round(
                line.monthly_hours * line.capacity_percent / 100.0,
                precision_digits=2,
            )

    @api.onchange("capacity_percent")
    def _onchange_capacity_percent(self):
        self._inverse_capacity_percent()

    @api.onchange("hours")
    def _onchange_hours(self):
        self._compute_capacity_percent()

    @api.model
    def _next_period(self, task):
        """Suggest the next calendar month for a new line."""
        if task and task.hour_plan_ids.filtered("date_to"):
            last = max(task.hour_plan_ids.mapped("date_to"))
            nxt = last + relativedelta(days=1)
            return self._month_bounds(nxt)
        if task and task.planned_date_start:
            start = task._hour_plan_date(task.planned_date_start)
            return self._month_bounds(start)
        today = fields.Date.context_today(self)
        return self._month_bounds(today)

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        task = self.env["project.task"].browse(self.env.context.get("default_task_id"))
        date_from, date_to = self._next_period(task)
        # Only default month when date_from is also missing. Generated lines
        # already pass date_from; injecting today's month would overwrite them.
        if "date_from" in fields_list:
            res.setdefault("date_from", date_from)
            if "month" in fields_list:
                res.setdefault("month", res["date_from"])
        if "date_to" in fields_list:
            res.setdefault("date_to", date_to)
        return res

    @api.onchange("month")
    def _onchange_month(self):
        if not self.month:
            return
        first, last = self._month_bounds(self.month)
        self.month = first
        self.date_from = first
        self.date_to = last

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for line in self:
            if line.date_from and line.date_to and line.date_to < line.date_from:
                raise ValidationError(
                    _("The hour plan end date must be on or after the start date.")
                )

    def _mark_task_plan_manual(self):
        if self.env.context.get("skip_hour_plan_generate"):
            return
        tasks = self.mapped("task_id").filtered(lambda task: not task.hour_plan_manual)
        if tasks:
            tasks.with_context(skip_hour_plan_generate=True).write(
                {"hour_plan_manual": True}
            )

    def _enable_plan_as_source(self):
        """Mark tasks whose plan was filled before dates/allocated hours."""
        tasks = self.mapped("task_id").filtered(
            lambda task: not task.hour_plan_drives_task
            and (
                float_is_zero(task.allocated_hours, precision_digits=2)
                or not task.planned_date_start
                or not task.planned_date_end
            )
        )
        if tasks:
            tasks.with_context(skip_hour_plan_generate=True).write(
                {"hour_plan_drives_task": True}
            )

    def _sync_related_tasks(self, hours_only=False):
        if self.env.context.get("skip_hour_plan_generate"):
            return
        self._mark_task_plan_manual()
        self._enable_plan_as_source()
        tasks = self.mapped("task_id")
        if hours_only:
            tasks.filtered("hour_plan_drives_task")._sync_task_from_hour_plan(
                update_allocated=True, update_dates=False
            )
        else:
            tasks._sync_task_from_hour_plan()

    @api.model_create_multi
    def create(self, vals_list):
        vals_list = [self._apply_month_bounds(vals) for vals in vals_list]
        lines = super().create(vals_list)
        lines._sync_related_tasks()
        return lines

    def write(self, vals):
        if {"month", "date_from", "date_to"} & set(vals):
            vals = self._apply_month_bounds(vals)
        res = super().write(vals)
        changed = {"hours", "capacity_percent", "month", "date_from", "date_to"} & set(
            vals
        )
        if changed:
            self._sync_related_tasks(
                hours_only=changed <= {"hours", "capacity_percent"}
            )
        return res

    def unlink(self):
        if self.env.context.get("skip_hour_plan_generate"):
            return super().unlink()
        tasks = self.mapped("task_id")
        res = super().unlink()
        existing = tasks.exists()
        to_flag = existing.filtered(lambda task: not task.hour_plan_manual)
        if to_flag:
            to_flag.with_context(skip_hour_plan_generate=True).write(
                {"hour_plan_manual": True}
            )
        existing._sync_task_from_hour_plan()
        return res
