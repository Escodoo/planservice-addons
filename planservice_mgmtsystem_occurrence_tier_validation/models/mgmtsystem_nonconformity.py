# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, models


class MgmtsystemNonconformity(models.Model):
    _name = "mgmtsystem.nonconformity"
    _inherit = ["mgmtsystem.nonconformity", "tier.validation"]
    _tier_validation_state_field_is_computed = True
    _state_field = "state"
    _state_from = ["waiting_verification"]
    _state_to = ["done"]
    _cancel_state = "cancel"
    _tier_validation_manual_config = False

    def _check_state_conditions(self, vals):
        if super()._check_state_conditions(vals):
            return True
        if "stage_id" not in vals:
            return False
        stage = self.env["mgmtsystem.nonconformity.stage"].browse(vals["stage_id"])
        return (
            self._check_state_from_condition() and stage.state in self._state_to
        )

    def _allow_to_remove_reviews(self, values):
        if super()._allow_to_remove_reviews(values):
            return True
        if "stage_id" not in values:
            return False
        stage = self.env["mgmtsystem.nonconformity.stage"].browse(values["stage_id"])
        return stage.state in ("waiting_supplier", "open", "draft", "cancel")

    @api.model
    def _get_under_validation_exceptions(self):
        exceptions = super()._get_under_validation_exceptions()
        extra = [
            "evaluation_comments",
            "verification_result",
            "verification_date",
            "reinspection_required",
            "reinspection_date",
            "closure_decision",
            "stage_id",
            "kanban_state",
            "message_ids",
            "activity_ids",
        ]
        return list(set(exceptions + extra))

    def action_submit_response(self):
        result = super().action_submit_response()
        self.flush_recordset(["stage_id", "state"])
        self.invalidate_recordset(["state", "need_validation"])
        self.request_validation()
        return result

    def action_reject(self):
        result = super().action_reject()
        self.mapped("review_ids").unlink()
        return result

    def _rejected_tier(self, tiers=False):
        result = super()._rejected_tier(tiers)
        self.with_context(skip_validation_check=True).write(
            {
                "verification_result": "rejected",
                "closure_decision": "keep_open",
            }
        )
        self.with_context(skip_validation_check=True)._move_to_stage(
            "waiting_supplier"
        )
        return result
