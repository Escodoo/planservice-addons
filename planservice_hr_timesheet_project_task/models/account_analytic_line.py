# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models


class AccountAnalyticLine(models.Model):
    _inherit = "account.analytic.line"

    location_id = fields.Many2one(
        comodel_name="timesheet.location",
        string="Location",
        ondelete="restrict",
    )
    attachment_ids = fields.Many2many(
        comodel_name="ir.attachment",
        string="Attachments",
    )
    attachment_count = fields.Integer(
        compute="_compute_attachment_count",
    )

    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for line in self:
            line.attachment_count = len(line.attachment_ids)

    task_id = fields.Many2one(
        "project.task",
        "Task",
        index="btree_not_null",
        compute="_compute_task_id",
        store=True,
        readonly=False,
        domain=(
            "[('allow_timesheets', '=', True), ('project_id', '=', project_id),"
            " ('user_ids', 'in', uid)]"
        ),
    )

    @api.model
    def _domain_project_id(self):
        """Only projects that have at least one task assigned to the user."""
        domain = super()._domain_project_id()
        user = self.env.user
        if user.has_group("hr_timesheet.group_timesheet_manager"):
            return domain
        assigned_task_ids = self.env["project.task"].search(
            [("user_ids", "in", user.id)]
        )
        project_ids = assigned_task_ids.mapped("project_id").ids
        return [("id", "in", project_ids)] + domain

    def _get_default_task(self, project_id):
        """Return the first task of the project assigned to the current user."""
        if not project_id:
            return self.env["project.task"]
        user = self.env.user
        return self.env["project.task"].search(
            [
                ("project_id", "=", project_id),
                ("user_ids", "in", user.id),
                ("allow_timesheets", "=", True),
            ],
            limit=1,
        )

    @api.onchange("project_id")
    def _onchange_project_id(self):
        super()._onchange_project_id()
        if not self.project_id:
            return
        self.task_id = self._get_default_task(self.project_id.id)
        self._onchange_planned_percentage()

    def _get_planned_percentage(self, task_id, date):
        """Return the planned capacity percent for the task's month."""
        if not task_id or not date:
            return 0.0
        task = self.env["project.task"].browse(task_id)
        month = fields.Date.to_date(date).replace(day=1)
        line = self.env["project.plan.line"].search(
            [
                ("project_id", "=", task.project_id.id),
                ("role_id.name", "=", task.name),
                ("user_id", "=", self.env.user.id),
            ],
            limit=1,
        )
        if not line:
            return 0.0
        cell = self.env["project.plan.cell"].search(
            [("line_id", "=", line.id), ("month", "=", month)],
            limit=1,
        )
        return cell.capacity_percent if cell else 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("project_id") and not vals.get("task_id"):
                vals["task_id"] = self._get_default_task(vals["project_id"]).id
            if vals.get("task_id") and vals.get("date") and not vals.get("unit_amount"):
                percent = self._get_planned_percentage(vals["task_id"], vals["date"])
                if percent:
                    hours_per_day = self._hours_per_day_for_vals(vals)
                    vals["unit_amount"] = hours_per_day * percent / 100.0
        return super().create(vals_list)

    def write(self, vals):
        if vals.get("project_id") and not vals.get("task_id"):
            for line in self:
                if not line.task_id:
                    vals["task_id"] = self._get_default_task(vals["project_id"]).id
        return super().write(vals)

    @api.onchange("date", "task_id")
    def _onchange_planned_percentage(self):
        """Default the day percentage from the plan cell of the month."""
        if not self.task_id or not self.date:
            return
        percent = self._get_planned_percentage(self.task_id.id, self.date)
        if percent:
            hours_per_day = self._get_timesheet_hours_per_day()
            self.unit_amount = hours_per_day * percent / 100.0
