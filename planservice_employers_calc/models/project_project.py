# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

from .planservice_employer_planned_cost import BASELINE_WRITE_KEY

EMPLOYER_SECTION_ID = "employer_extra_costs"


class ProjectProject(models.Model):
    _inherit = "project.project"

    employer_real_cost = fields.Monetary(
        string="Actual cost",
        currency_field="currency_id",
        compute="_compute_employer_costs",
        groups="hr_timesheet.group_timesheet_manager",
        help="Personnel cost of the logged hours (salary, benefits and "
        "provisions prorated by the % of the day).",
    )
    employer_planned_cost = fields.Monetary(
        string="Planned cost",
        currency_field="currency_id",
        compute="_compute_employer_costs",
        groups="hr_timesheet.group_timesheet_manager",
        help="Planned hours of the tasks / plan monthly hours x monthly cost "
        "of the assignee (split among the assignees). Fixed from the date the "
        "plan was locked on.",
    )
    employer_baseline_date = fields.Date(
        string="Planned cost locked on",
        readonly=True,
        copy=False,
        groups="hr_timesheet.group_timesheet_manager",
        help="Date the project left a status that allows re-planning. From "
        "then on the planned cost no longer changes.",
    )
    employer_planned_cost_ids = fields.One2many(
        "planservice.employer.planned.cost",
        "project_id",
        string="Planned cost baseline",
        groups="hr_timesheet.group_timesheet_manager",
        readonly=True,
    )
    employer_cost_deviation = fields.Monetary(
        string="Cost deviation",
        currency_field="currency_id",
        compute="_compute_employer_costs",
        groups="hr_timesheet.group_timesheet_manager",
        help="Planned cost minus actual cost. Positive = spent less than planned.",
    )
    employer_tasks_without_cost = fields.Integer(
        string="Tasks without planned cost",
        compute="_compute_employer_costs",
        groups="hr_timesheet.group_timesheet_manager",
        help="Tasks with planned hours without an assignee, or whose assignee "
        "has no employee, which are left out of the planned cost. Only while "
        "the plan is not locked.",
    )

    def _get_profitability_labels(self):
        labels = super()._get_profitability_labels()
        labels[EMPLOYER_SECTION_ID] = self.env._(
            "Employer costs (salary, benefits, provisions)"
        )
        return labels

    def _get_profitability_sequence_per_invoice_type(self):
        sequences = super()._get_profitability_sequence_per_invoice_type()
        sequences[EMPLOYER_SECTION_ID] = 14
        return sequences

    def _get_employer_extra_cost(self):
        """Custo de pessoal (salário, benefícios e provisões) apropriado ao projeto.

        Soma o custo total do relatório, rateado pela % do dia lançada. O custo
        nativo de timesheet do painel não é alterado.
        """
        self.ensure_one()
        groups = (
            self.env["planservice.employer.cost.report"]
            .sudo()
            ._read_group(
                [("project_id", "=", self.id)],
                groupby=["currency_id"],
                aggregates=["total_cost:sum"],
            )
        )
        total = 0.0
        for currency, cost in groups:
            total += currency._convert(
                cost,
                self.currency_id,
                self.company_id,
            )
        return total

    def _get_employer_planned_cost(self):
        """Custo previsto do projeto e nº de tarefas com custo incompleto.

        O valor vem do relatório de previsto x real: a linha de base, se o
        planejamento já foi travado, ou o previsto ao vivo. As tarefas sem
        custo previsto (sem responsável ou responsável sem colaborador) só são
        contadas enquanto o planejamento não está travado.
        """
        self.ensure_one()
        groups = (
            self.env["planservice.employer.cost.project.report"]
            .sudo()
            ._read_group(
                [("project_id", "=", self.id)],
                aggregates=["planned_cost:sum"],
            )
        )
        total = groups[0][0] if groups else 0.0
        if self.sudo().employer_baseline_date:
            return total or 0.0, 0
        tasks = (
            self.env["project.task"]
            .sudo()
            .with_context(active_test=False)
            .search([("project_id", "=", self.id), ("allocated_hours", ">", 0)])
        )
        without_cost = len(
            tasks.filtered(
                lambda task: not task.user_ids
                or any(not user.employee_id for user in task.user_ids)
            )
        )
        return total or 0.0, without_cost

    @api.depends(
        "company_id",
        "task_ids.allocated_hours",
        "task_ids.user_ids",
        "employer_baseline_date",
    )
    def _compute_employer_costs(self):
        # Os valores vêm de views SQL que leem outros modelos (versões de custo,
        # tarefas, lançamentos): grava as pendências antes de consultar.
        self.env.flush_all()
        for project in self:
            real = project._get_employer_extra_cost()
            planned, without_cost = project._get_employer_planned_cost()
            project.employer_real_cost = real
            project.employer_planned_cost = planned
            project.employer_cost_deviation = planned - real
            project.employer_tasks_without_cost = without_cost

    def _create_employer_baseline(self, baseline_date=None):
        """Grava a linha de base do previsto dos projetos que ainda não têm."""
        projects = self.sudo().filtered(lambda p: not p.employer_baseline_date)
        if not projects:
            return
        baseline_date = baseline_date or self.env["hr.employee"]._employer_cost_today()
        self.env["planservice.employer.planned.cost"].sudo().with_context(
            **{BASELINE_WRITE_KEY: True}
        )._insert_from_live(projects, baseline_date)
        projects.write({"employer_baseline_date": baseline_date})
        # As views SQL decidem entre linha de base e previsto ao vivo por esta
        # data: grava já, senão uma consulta na mesma transação soma os dois.
        projects.flush_recordset(["employer_baseline_date"])

    def write(self, vals):
        replannable = self.browse()
        if "project_status" in vals:
            replannable = self.sudo().filtered("can_replan")
        res = super().write(vals)
        if replannable:
            replannable.invalidate_recordset(["can_replan"])
            replannable.filtered(lambda p: not p.can_replan)._create_employer_baseline()
        return res

    def _get_profitability_items(self, with_action=True):
        items = super()._get_profitability_items(with_action)
        if not self.env.user.has_group("hr_timesheet.group_timesheet_manager"):
            return items
        amount = self._get_employer_extra_cost()
        if not amount:
            return items
        costs = items["costs"]
        costs["data"].append(
            {
                "id": EMPLOYER_SECTION_ID,
                "sequence": self._get_profitability_sequence_per_invoice_type()[
                    EMPLOYER_SECTION_ID
                ],
                "billed": -amount,
                "to_bill": 0.0,
            }
        )
        costs["total"]["billed"] -= amount
        return items
