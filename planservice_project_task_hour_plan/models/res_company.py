# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResCompany(models.Model):
    _inherit = "res.company"

    hour_plan_monthly_hours = fields.Float(
        default=160.0,
        digits=(16, 2),
        help="Hours of one resource used as 100% capacity for each month "
        "in the task hour plan.",
    )
