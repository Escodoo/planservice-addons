# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.tools import SQL, format_date


class PlanserviceEmployerCostVersion(models.Model):
    """Custo mensal do colaborador vigente a partir de uma data.

    Gerada só pela ficha do colaborador (``hr.employee``): a primeira versão vale
    desde sempre (``date_from`` vazio) e as seguintes a partir do dia seguinte à
    alteração. Somente leitura na interface.
    """

    _name = "planservice.employer.cost.version"
    _description = "Employee monthly cost version"
    _order = "employee_id, date_from desc nulls last, id desc"
    _rec_name = "employee_id"

    employee_id = fields.Many2one(
        "hr.employee",
        string="Team member",
        required=True,
        ondelete="cascade",
        index=True,
        readonly=True,
    )
    date_from = fields.Date(
        string="Valid from",
        readonly=True,
        help="First day this cost applies. Empty: applies since always.",
    )
    date_from_label = fields.Char(
        string="Validity",
        compute="_compute_date_from_label",
        help="Date this cost applies from, or 'Since always' for the first one.",
    )
    salary_benefits_cost = fields.Monetary(
        string="Salary + benefits (monthly)",
        currency_field="currency_id",
        readonly=True,
    )
    total_cost = fields.Monetary(
        string="Total monthly cost",
        currency_field="currency_id",
        compute="_compute_total_cost",
        store=True,
    )
    company_id = fields.Many2one(related="employee_id.company_id", store=True)
    currency_id = fields.Many2one(related="employee_id.currency_id")

    _sql_constraints = [
        (
            "employee_date_from_unique",
            "UNIQUE(employee_id, date_from)",
            "There is already a cost version for this team member on this date.",
        ),
    ]

    def init(self):
        # UNIQUE não barra dois NULL: só uma versão "desde sempre" por colaborador.
        self.env.cr.execute(
            SQL(
                "CREATE UNIQUE INDEX IF NOT EXISTS %s ON %s (employee_id) "
                "WHERE date_from IS NULL",
                SQL.identifier(f"{self._table}_employee_initial_unique"),
                SQL.identifier(self._table),
            )
        )

    @api.depends("date_from")
    def _compute_date_from_label(self):
        for version in self:
            version.date_from_label = (
                format_date(self.env, version.date_from)
                if version.date_from
                else self.env._("Since always")
            )

    @api.depends("salary_benefits_cost")
    def _compute_total_cost(self):
        for version in self:
            version.total_cost = version.salary_benefits_cost
