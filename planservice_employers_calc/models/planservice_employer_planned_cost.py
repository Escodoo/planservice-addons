# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models
from odoo.exceptions import UserError
from odoo.tools import SQL

# Chave de contexto que libera escrita interna (gravação pelo projeto/migração).
BASELINE_WRITE_KEY = "planservice_employer_baseline_write"


class PlanserviceEmployerPlannedCost(models.Model):
    """Linha de base do custo previsto de um projeto (imutável).

    Copiada do previsto ao vivo (planservice.employer.planned.live) quando o
    projeto deixa um status que permite replanejar. Depois disso o previsto do
    projeto vem só daqui: mudanças de salário, horas, tarefas ou responsáveis
    não a alteram.
    """

    _name = "planservice.employer.planned.cost"
    _description = "Planned cost baseline by project, task, employee and month"
    _order = "project_id, date, task_id, employee_id"
    _rec_name = "project_id"

    project_id = fields.Many2one(
        "project.project",
        string="Job site",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
    )
    task_id = fields.Many2one(
        "project.task",
        ondelete="set null",
        readonly=True,
        help="Empty when the task was deleted after the baseline: its planned "
        "cost still counts.",
    )
    task_name = fields.Char(readonly=True)
    employee_id = fields.Many2one(
        "hr.employee",
        string="Team member",
        ondelete="restrict",
        readonly=True,
    )
    date = fields.Date(readonly=True, help="First day of the month.")
    date_start = fields.Date(
        string="Period start",
        readonly=True,
        help="First day of the task period inside this month, frozen with the "
        "baseline. The planned cost is spread over its business days.",
    )
    date_end = fields.Date(
        string="Period end",
        readonly=True,
        help="Last day of the task period inside this month, frozen with the "
        "baseline.",
    )
    company_id = fields.Many2one("res.company", readonly=True)
    currency_id = fields.Many2one(related="company_id.currency_id")
    allocated_hours = fields.Float(string="Planned hours", readonly=True)
    plan_monthly_hours = fields.Float(readonly=True)
    monthly_cost = fields.Monetary(
        string="Monthly cost",
        currency_field="currency_id",
        readonly=True,
    )
    planned_cost = fields.Monetary(
        string="Planned cost",
        currency_field="currency_id",
        readonly=True,
    )
    baseline_date = fields.Date(readonly=True)

    def _check_baseline_write(self):
        if not self.env.context.get(BASELINE_WRITE_KEY):
            raise UserError(
                self.env._("The planned cost baseline of a project cannot be changed.")
            )

    def write(self, vals):
        self._check_baseline_write()
        return super().write(vals)

    def unlink(self):
        self._check_baseline_write()
        return super().unlink()

    def _insert_from_live(self, projects, baseline_date):
        """Copia o previsto ao vivo dos projetos para a linha de base."""
        if not projects:
            return
        self.env.flush_all()
        self.env.cr.execute(
            SQL(
                """
                INSERT INTO %(table)s (
                    project_id, task_id, task_name, employee_id, date,
                    date_start, date_end, company_id,
                    allocated_hours, plan_monthly_hours,
                    monthly_cost, planned_cost, baseline_date,
                    create_uid, create_date, write_uid, write_date
                )
                SELECT
                    l.project_id, l.task_id, t.name, l.employee_id,
                    l.date, l.date_start, l.date_end,
                    COALESCE(l.company_id, p.company_id),
                    l.allocated_hours, l.plan_monthly_hours, l.monthly_cost,
                    l.planned_cost, %(baseline_date)s,
                    %(uid)s, now() AT TIME ZONE 'UTC',
                    %(uid)s, now() AT TIME ZONE 'UTC'
                FROM planservice_employer_planned_live l
                JOIN project_project p ON p.id = l.project_id
                LEFT JOIN project_task t ON t.id = l.task_id
                WHERE l.project_id IN %(project_ids)s
                """,
                table=SQL.identifier(self._table),
                baseline_date=baseline_date,
                uid=self.env.uid,
                project_ids=tuple(projects.ids),
            )
        )
        self.invalidate_model()
