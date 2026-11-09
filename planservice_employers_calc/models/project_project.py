# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

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
        "of the assignee (split among the assignees).",
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
        "has no employee, which are left out of the planned cost.",
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

        Por tarefa: horas previstas / horas mensais do plano x custo mensal total
        do responsável. Com vários responsáveis as horas são divididas
        igualmente; responsável sem colaborador contribui com zero e a tarefa é
        contada como sem custo previsto.
        """
        self.ensure_one()
        plan_hours = (
            self.company_id.employer_plan_monthly_hours
            or self.env.company.employer_plan_monthly_hours
        )
        tasks = (
            self.env["project.task"]
            .sudo()
            .with_context(active_test=False)
            .search([("project_id", "=", self.id), ("allocated_hours", ">", 0)])
        )
        total = 0.0
        without_cost = 0
        for task in tasks:
            assignees = task.user_ids
            if not assignees:
                without_cost += 1
                continue
            share = task.allocated_hours / len(assignees)
            incomplete = False
            for user in assignees:
                employee = user.employee_id
                if not employee:
                    incomplete = True
                    continue
                monthly = employee.employer_monthly_total_cost
                if employee.currency_id and employee.currency_id != self.currency_id:
                    monthly = employee.currency_id._convert(
                        monthly,
                        self.currency_id,
                        self.company_id or self.env.company,
                        fields.Date.context_today(self),
                    )
                total += share / plan_hours * monthly
            if incomplete:
                without_cost += 1
        return total, without_cost

    @api.depends("company_id", "task_ids.allocated_hours", "task_ids.user_ids")
    def _compute_employer_costs(self):
        for project in self:
            real = project._get_employer_extra_cost()
            planned, without_cost = project._get_employer_planned_cost()
            project.employer_real_cost = real
            project.employer_planned_cost = planned
            project.employer_cost_deviation = planned - real
            project.employer_tasks_without_cost = without_cost

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
