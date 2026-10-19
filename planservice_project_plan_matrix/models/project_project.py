# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from calendar import monthrange

from dateutil.relativedelta import relativedelta

from odoo import Command, _, api, fields, models
from odoo.exceptions import UserError


class ProjectProject(models.Model):
    _inherit = "project.project"

    label_tasks = fields.Char(
        string="Use Tasks as",
        default=lambda self: self.env._("Role"),
        translate=True,
    )
    privacy_visibility = fields.Selection(default="followers")
    allocated_hours = fields.Float(string="Planned Time")
    effective_hours = fields.Float(string="Actual Time")
    plan_line_ids = fields.One2many(
        comodel_name="project.plan.line",
        inverse_name="project_id",
        string="Plan Lines",
        copy=True,
    )
    stage_month_ids = fields.One2many(
        comodel_name="project.plan.stage.month",
        inverse_name="project_id",
        string="Stage Months",
        copy=True,
    )
    project_status = fields.Many2one(
        default=lambda self: self._default_project_status()
    )
    can_replan = fields.Boolean(
        compute="_compute_can_replan",
        compute_sudo=True,
        help="The plan can only change while the project has no status or a "
        "status that allows re-planning.",
    )
    plan_first_month = fields.Date(
        compute="_compute_plan_months",
        store=True,
    )
    plan_last_month = fields.Date(
        compute="_compute_plan_months",
        store=True,
    )

    @api.model
    def _default_project_status(self):
        return self.env.ref(
            "project_status.project_status_pending", raise_if_not_found=False
        )

    @api.depends("project_status.allow_replan")
    def _compute_can_replan(self):
        # Projects created before the status existed have none: keep them open.
        for project in self:
            status = project.project_status
            project.can_replan = not status or status.allow_replan

    def _check_can_replan(self):
        locked = self.filtered(lambda project: not project.can_replan)
        if locked:
            raise UserError(
                _(
                    "The plan of %(projects)s can only be changed while the "
                    "project status allows re-planning.",
                    projects=", ".join(locked.mapped("display_name")),
                )
            )

    @api.depends("date_start", "date")
    def _compute_plan_months(self):
        for project in self:
            if project.date_start and project.date:
                project.plan_first_month = project.date_start.replace(day=1)
                project.plan_last_month = project.date.replace(day=1)
            else:
                project.plan_first_month = False
                project.plan_last_month = False

    def _generate_month_range(self, date_start, date_end):
        """Return a list of month first-days between date_start and date_end."""
        if not date_start or not date_end or date_end < date_start:
            return []
        months = []
        current = date_start.replace(day=1)
        end_month = date_end.replace(day=1)
        while current <= end_month:
            months.append(current)
            current += relativedelta(months=1)
        return months

    @api.onchange("date_start", "date")
    def _onchange_plan_dates(self):
        """Snap dates to full months and update plan cells."""
        if self.date_start:
            self.date_start = self.date_start.replace(day=1)
        if self.date:
            last_day = monthrange(self.date.year, self.date.month)[1]
            self.date = self.date.replace(day=last_day)
        if not self.date_start or not self.date or not self.can_replan:
            return
        self._update_plan_cells()

    def _update_plan_cells(self):
        """Update plan cells for all lines based on project dates."""
        for project in self:
            if not project.date_start or not project.date:
                continue
            months = project._generate_month_range(project.date_start, project.date)
            for line in project.plan_line_ids:
                existing_months = line.cell_ids.mapped("month")
                new_cells = []
                for month in months:
                    if month not in existing_months:
                        new_cells.append(
                            Command.create(
                                {
                                    "month": month,
                                    "capacity_percent": 0.0,
                                }
                            )
                        )
                if new_cells:
                    line.cell_ids = new_cells

    def write(self, vals):
        res = super().write(vals)
        if {"date_start", "date"} & set(vals):
            self.filtered("can_replan")._update_plan_cells()
        return res

    def action_load_months(self):
        """Load months based on project dates."""
        self.ensure_one()
        self._check_can_replan()
        if not self.date_start or not self.date:
            return
        self._update_plan_cells()
        return True

    def action_load_stages(self):
        """Apply stage-month associations to the plan cells."""
        self.ensure_one()
        self._check_can_replan()
        for mapping in self.stage_month_ids:
            if not mapping.stage_id or not mapping.date_from or not mapping.date_to:
                continue
            cells = self.env["project.plan.cell"].search(
                [
                    ("project_id", "=", self.id),
                    ("month", ">=", mapping.date_from),
                    ("month", "<=", mapping.date_to),
                ]
            )
            cells.write({"stage_id": mapping.stage_id.id})
        return True

    def action_generate_plan(self):
        """Generate/update project tasks from the plan matrix."""
        self.ensure_one()
        self._check_can_replan()

        role_stage = self.env.ref("planservice_project_plan_matrix.task_type_role")
        if self not in role_stage.project_ids:
            role_stage.project_ids = [Command.link(self.id)]

        project_total_hours = 0.0
        for line in self.plan_line_ids:
            cells = line._get_cells_in_period().filtered(
                lambda c: c.capacity_percent > 0
            )
            if not cells:
                continue

            total_hours = sum(cells.mapped("hours"))
            project_total_hours += total_hours
            first_month = min(cells.mapped("month"))
            last_month = max(cells.mapped("month"))
            last_day = monthrange(last_month.year, last_month.month)[1]

            existing_task = self.env["project.task"].search(
                [("plan_line_id", "=", line.id)],
                limit=1,
            )

            # Tasks with timesheets are also updated: re-planning only rewrites
            # the task plan, dates and planned time, never the logged hours.
            planned_date_end = self.env["project.task"]._date_to_planned_datetime(
                last_month.replace(day=last_day)
            )

            task_vals = {
                "project_id": self.id,
                "plan_line_id": line.id,
                "user_ids": [Command.link(line.user_id.id)],
                "allocated_hours": total_hours,
                "planned_date_start": self.env[
                    "project.task"
                ]._date_to_planned_datetime(first_month),
                "planned_date_end": planned_date_end,
                "date_deadline": planned_date_end,
            }

            if existing_task:
                existing_task.with_context(skip_hour_plan_generate=True).write(
                    task_vals
                )
                task = existing_task
            else:
                task_vals.update(name=line.role_id.name, stage_id=role_stage.id)
                task = (
                    self.env["project.task"]
                    .with_context(skip_hour_plan_generate=True)
                    .create(task_vals)
                )

            self._sync_task_hour_plan(task, line, cells)

        self.write({"allocated_hours": project_total_hours})

        return True

    def _sync_task_hour_plan(self, task, line, cells):
        """Sync task hour plan from plan line cells."""
        task.hour_plan_ids.with_context(skip_hour_plan_generate=True).unlink()

        plan_lines = []
        for cell in cells:
            first, last = self.env["project.task.hour.plan"]._month_bounds(cell.month)
            plan_lines.append(
                Command.create(
                    {
                        "date_from": first,
                        "date_to": last,
                        "hours": cell.hours,
                    }
                )
            )

        if plan_lines:
            task.with_context(skip_hour_plan_generate=True).write(
                {"hour_plan_ids": plan_lines}
            )
