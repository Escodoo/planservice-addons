# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import models
from odoo.exceptions import AccessError, UserError

DASHBOARD_XMLID = "planservice_employers_calc_dashboard.dashboard_cost"
REPORT_MODEL = "planservice.employer.cost.project.report"


class ProjectProject(models.Model):
    _inherit = "project.project"

    def action_open_cost_dashboard(self):
        """Abre o dashboard de custo já filtrado nesta obra.

        O Boardkit não recebe filtros pela URL: ele restaura os filtros salvos do
        usuário. Por isso gravamos o filtro (ID da obra = esta obra, todo o período)
        com a chamada pública ``save_filters`` e depois abrimos o dashboard.
        """
        self.ensure_one()
        if not self.env.user.has_group("hr_timesheet.group_timesheet_manager"):
            raise AccessError(
                self.env._("Only timesheet managers can open the cost dashboard.")
            )
        dashboard = self.env.ref(DASHBOARD_XMLID, raise_if_not_found=False)
        if not dashboard:
            raise UserError(
                self.env._("The cost dashboard was not found. Reinstall the module.")
            )
        model_label = self.env["ir.model"]._get(REPORT_MODEL).name
        # sudo mantém o uid: o filtro é gravado para o usuário atual
        self.env["boardkit.dashboard"].sudo().save_filters(
            dashboard.id,
            {
                "date_preset": "none",
                "filter_ids": [],
                "custom_filters": [
                    {
                        "model": REPORT_MODEL,
                        "field": "project_key",
                        "operator": "=",
                        "value": self.id,
                        "label": self.env._("Project: %s", self.display_name),
                        "modelLabel": model_label,
                    }
                ],
            },
        )
        return {
            "type": "ir.actions.client",
            "tag": "boardkit_dashboard",
            "name": dashboard.name,
            "params": {"dashboard_id": dashboard.id},
        }
