# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from calendar import monthrange

from dateutil.relativedelta import relativedelta

from odoo import Command, api, fields, models


class ProjectProject(models.Model):
    _inherit = "project.project"

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
    plan_first_month = fields.Date(
        compute="_compute_plan_months",
        store=True,
    )
    plan_last_month = fields.Date(
        compute="_compute_plan_months",
        store=True,
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
        if not self.date_start or not self.date:
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
            self._update_plan_cells()
        return res

    def action_load_months(self):
        """Load months based on project dates."""
        self.ensure_one()
        if not self.date_start or not self.date:
            return
        self._update_plan_cells()
        return True

    def action_load_stages(self):
        """Apply stage-month associations to the plan cells."""
        self.ensure_one()
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

        # Ensure "Cargos" stage exists
        cargos_stage = self.env["project.task.type"].search(
            [("name", "ilike", "cargos")],
            limit=1,
        )
        if not cargos_stage:
            cargos_stage = self.env["project.task.type"].create({"name": "Cargos"})

        project_total_hours = 0.0
        for line in self.plan_line_ids:
            cells = line.cell_ids.filtered(lambda c: c.capacity_percent > 0)
            if not cells:
                continue

            total_hours = sum(cells.mapped("hours"))
            project_total_hours += total_hours
            first_month = min(cells.mapped("month"))
            last_month = max(cells.mapped("month"))
            last_day = monthrange(last_month.year, last_month.month)[1]

            existing_task = self.env["project.task"].search(
                [
                    ("project_id", "=", self.id),
                    ("name", "=", line.role_id.name),
                ],
                limit=1,
            )

            has_timesheets = existing_task and bool(
                existing_task.timesheet_ids.filtered("line_id")
            )

            if existing_task and has_timesheets:
                continue

            planned_date_end = self.env["project.task"]._date_to_planned_datetime(
                last_month.replace(day=last_day)
            )

            task_vals = {
                "name": line.role_id.name,
                "project_id": self.id,
                "stage_id": cargos_stage.id,
                "user_ids": [(4, line.user_id.id)],
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
