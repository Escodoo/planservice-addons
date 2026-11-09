# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    employer_plan_monthly_hours = fields.Float(
        string="Plan monthly hours",
        default=160.0,
        help="Hours that correspond to 100% of a month in the project plan. "
        "Used to convert the planned hours of the tasks into a fraction of the "
        "month in the planned cost. It must follow the value used by the "
        "project plan (default 160).",
    )

    _sql_constraints = [
        (
            "employer_plan_monthly_hours_positive",
            "CHECK(employer_plan_monthly_hours > 0)",
            "The plan monthly hours must be greater than zero.",
        ),
    ]
