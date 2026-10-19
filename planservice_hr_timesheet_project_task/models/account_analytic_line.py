# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.osv import expression
from odoo.tools.misc import format_date


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

    planned_day_percentage = fields.Float(
        string="Planned %",
        compute="_compute_planned_day_percentage",
        digits=(16, 2),
        help="Capacity planned in the project plan for this collaborator, "
        "task and month.",
    )
    is_timesheet_manager = fields.Boolean(
        compute="_compute_is_timesheet_manager",
    )
    task_id = fields.Many2one(
        domain=(
            "[('allow_timesheets', '=', True), ('project_id', '=?', project_id)]"
            " + ([] if is_timesheet_manager else [('user_ids', 'in', uid)])"
        ),
    )

    @api.depends("attachment_ids")
    def _compute_attachment_count(self):
        for line in self:
            line.attachment_count = len(line.attachment_ids)

    @api.depends_context("uid")
    def _compute_is_timesheet_manager(self):
        self.is_timesheet_manager = self.env.user.has_group(
            "hr_timesheet.group_timesheet_manager"
        )

    @api.depends("task_id.plan_line_id", "date", "user_id", "employee_id.user_id")
    def _compute_planned_day_percentage(self):
        # The plan is restricted to project groups; timesheet users only get
        # the planned percentage of their own lines.
        lines = self.filtered(lambda line: line.task_id and line.date)
        (self - lines).planned_day_percentage = 0.0
        if not lines:
            return
        plan_lines = lines.task_id.sudo().plan_line_id
        cells = (
            self.env["project.plan.cell"]
            .sudo()
            .search(
                [
                    ("line_id", "in", plan_lines.ids),
                    ("month", "in", list({line.date.replace(day=1) for line in lines})),
                ]
            )
        )
        capacity = {
            (cell.line_id.id, cell.month): cell.capacity_percent for cell in cells
        }
        for line in lines:
            plan_line = line.task_id.sudo().plan_line_id
            user = line.user_id or line.employee_id.user_id
            if plan_line.user_id != user:
                line.planned_day_percentage = 0.0
                continue
            line.planned_day_percentage = capacity.get(
                (plan_line.id, line.date.replace(day=1)), 0.0
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
        return expression.AND([[("id", "in", project_ids)], domain])

    @api.model
    def _get_timesheet_user(self, employee):
        """User whose plan applies to a timesheet of *employee*."""
        return employee.user_id or self.env.user

    def _get_default_task(self, project_id, user=None):
        """Return the first task of the project assigned to *user*."""
        if not project_id:
            return self.env["project.task"]
        user = user or self.env.user
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
        self.task_id = self._get_default_task(
            self.project_id.id, self._get_timesheet_user(self.employee_id)
        )
        self._onchange_planned_percentage()

    def _get_planned_percentage(self, task, date, user):
        """Return the capacity planned for *user* on *task* in the month of *date*."""
        if not task or not date:
            return 0.0
        plan_line = task.sudo().plan_line_id
        if not plan_line or plan_line.user_id != user:
            return 0.0
        cell = (
            self.env["project.plan.cell"]
            .sudo()
            .search(
                [
                    ("line_id", "=", plan_line.id),
                    ("month", "=", fields.Date.to_date(date).replace(day=1)),
                ],
                limit=1,
            )
        )
        return cell.capacity_percent

    @api.constrains("date", "project_id")
    def _check_timesheet_not_in_future(self):
        today = fields.Date.context_today(self)
        for line in self:
            if line.project_id and line.date and line.date > today:
                raise ValidationError(
                    _(
                        "You cannot log hours for a future date (%(date)s).",
                        date=format_date(self.env, line.date),
                    )
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            employee = self.env["hr.employee"].browse(vals.get("employee_id"))
            user = self._get_timesheet_user(employee)
            if vals.get("project_id") and not vals.get("task_id"):
                vals["task_id"] = self._get_default_task(vals["project_id"], user).id
            if (
                vals.get("task_id")
                and vals.get("date")
                and "unit_amount" not in vals
                and "day_percentage" not in vals
            ):
                task = self.env["project.task"].browse(vals["task_id"])
                percent = self._get_planned_percentage(task, vals["date"], user)
                if percent:
                    hours_per_day = self._hours_per_day_for_vals(vals)
                    vals["unit_amount"] = hours_per_day * percent / 100.0
        lines = super().create(vals_list)
        lines.filtered("attachment_ids")._link_attachments()
        return lines

    def write(self, vals):
        if vals.get("project_id") and not vals.get("task_id"):
            lines_without_task = self.filtered(lambda line: not line.task_id)
            for line in lines_without_task:
                task = self._get_default_task(
                    vals["project_id"], self._get_timesheet_user(line.employee_id)
                )
                super(AccountAnalyticLine, line).write(dict(vals, task_id=task.id))
            res = super(AccountAnalyticLine, self - lines_without_task).write(vals)
        else:
            res = super().write(vals)
        if "attachment_ids" in vals:
            self._link_attachments()
        return res

    def _link_attachments(self):
        """Attach the files to the timesheet line itself.

        Access to an attachment follows its res_model/res_id, so files uploaded
        elsewhere would not stay readable from the timesheet.
        """
        for line in self:
            line.attachment_ids.filtered(
                lambda att, line=line: (att.res_model, att.res_id)
                != (line._name, line.id)
            ).write({"res_model": line._name, "res_id": line.id})

    @api.onchange("date", "task_id")
    def _onchange_planned_percentage(self):
        """Default the day percentage from the plan cell of the month."""
        if not self.task_id or not self.date or self.unit_amount:
            return
        percent = self._get_planned_percentage(
            self.task_id, self.date, self._get_timesheet_user(self.employee_id)
        )
        if percent:
            hours_per_day = self._get_timesheet_hours_per_day()
            self.unit_amount = hours_per_day * percent / 100.0
