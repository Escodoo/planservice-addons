# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class ResConfigSettings(models.TransientModel):
    _inherit = "res.config.settings"

    hour_plan_monthly_hours = fields.Float(
        related="company_id.hour_plan_monthly_hours",
        string="Monthly Hours (100% Capacity)",
        readonly=False,
    )
