# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .occurrence_selection import (
    CLASSIFICATION_SELECTION,
    DISCIPLINE_SELECTION,
    DISPOSITION_SELECTION,
    WORK_DIVISION_SELECTION,
)

STAGE_XMLID = {
    "draft": "mgmtsystem_nonconformity.stage_draft",
    "waiting_supplier": "planservice_mgmtsystem_occurrence.stage_waiting_supplier",
    "open": "mgmtsystem_nonconformity.stage_open",
    "waiting_verification": (
        "planservice_mgmtsystem_occurrence.stage_waiting_verification"
    ),
    "done": "mgmtsystem_nonconformity.stage_done",
    "cancel": "mgmtsystem_nonconformity.stage_cancel",
}


class MgmtsystemNonconformity(models.Model):
    _inherit = "mgmtsystem.nonconformity"

    origin_ids = fields.Many2many(default=lambda self: self._default_origin_ids())

    project_id = fields.Many2one("project.project", "Project / Work")
    inspector_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        tracking=True,
    )
    opening_date = fields.Date(default=fields.Date.context_today)
    revision = fields.Char(default="00")
    work_division = fields.Selection(WORK_DIVISION_SELECTION)
    work_division_other = fields.Char()
    classification = fields.Selection(CLASSIFICATION_SELECTION, tracking=True)
    priority = fields.Selection(
        [
            ("normal", "Normal"),
            ("high", "High"),
            ("immediate", "Immediate"),
        ],
        default="normal",
        tracking=True,
    )
    stop_work = fields.Boolean("Work Stoppage")
    stop_work_date = fields.Date()

    location = fields.Char("Location / Axis / Elevation")
    service_activity = fields.Char("Service / Activity")
    equipment = fields.Char("Installation / Equipment")
    discipline = fields.Selection(DISCIPLINE_SELECTION)
    identification_date = fields.Date(default=fields.Date.context_today)
    reference_type = fields.Selection(
        [
            ("executive_project", "Executive Project"),
            ("report_test", "Report / Test"),
            ("field_visual", "Field Visual"),
        ],
        string="Occurrence Reference",
    )
    reference_title = fields.Char()
    reference_revision = fields.Char()
    reference_date = fields.Date()
    reference_sheet = fields.Char("Sheet / Page / Detail")
    reference_na = fields.Boolean("Reference N/A")

    immediate_action_ids = fields.Many2many(
        "mgmtsystem.occurrence.immediate.action",
        "mgmtsystem_nc_immediate_action_rel",
        "nonconformity_id",
        "immediate_action_id",
        string="Immediate Actions",
    )
    immediate_action_date = fields.Date()
    immediate_action_user_id = fields.Many2one("res.users", "Immediate Action Owner")
    area_protected = fields.Selection(
        [
            ("na", "N/A"),
            ("no", "No"),
            ("yes", "Yes"),
        ],
        default="na",
    )

    evidence_ids = fields.One2many(
        "mgmtsystem.nonconformity.evidence",
        "nonconformity_id",
    )
    inspector_evidence_ids = fields.One2many(
        "mgmtsystem.nonconformity.evidence",
        "nonconformity_id",
        domain=[("section", "=", "inspector")],
    )
    supplier_evidence_ids = fields.One2many(
        "mgmtsystem.nonconformity.evidence",
        "nonconformity_id",
        domain=[("section", "=", "supplier")],
    )
    document_ids = fields.One2many(
        "mgmtsystem.nonconformity.document",
        "nonconformity_id",
    )

    supplier_representative_id = fields.Many2one(
        "res.partner",
        domain="[('id', 'child_of', partner_id)]",
    )
    supplier_technical_user_id = fields.Many2one("res.users", "Technical Responsible")
    supplier_response_date = fields.Date()
    supplier_proposed_deadline = fields.Date()
    containment_text = fields.Text("Containment and Current Condition")
    cause_justification = fields.Text("Identified Cause or Technical Justification")
    disposition = fields.Selection(DISPOSITION_SELECTION)
    concession_required = fields.Boolean()
    deadline_impact = fields.Boolean("Impact on Deadline")
    new_deadline = fields.Date()
    supplier_conclusion_date = fields.Date()
    supplier_conclusion_user_id = fields.Many2one(
        "res.users",
        "Supplier Conclusion Responsible",
    )
    final_condition = fields.Text()

    verification_result = fields.Selection(
        [
            ("approved", "Approved and Released"),
            ("approved_with_comments", "Approved with Comments"),
            ("rejected", "Rejected"),
        ],
        tracking=True,
    )
    verification_date = fields.Date()
    reinspection_required = fields.Boolean()
    reinspection_date = fields.Date()
    closure_decision = fields.Selection(
        [
            ("close", "Close"),
            ("keep_open", "Keep Open"),
            ("reclassify", "Reclassify"),
        ]
    )

    def _default_origin_ids(self):
        origin = self.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence",
            raise_if_not_found=False,
        )
        return origin

    def _get_stage_by_state(self, state):
        xmlid = STAGE_XMLID.get(state)
        if not xmlid:
            raise UserError(self.env._("Unknown occurrence state: %s", state))
        return self.env.ref(xmlid)

    def _move_to_stage(self, state):
        stage = self._get_stage_by_state(state)
        self.write({"stage_id": stage.id})
        return True

    def _get_supplier_writable_fields(self):
        return {
            "supplier_representative_id",
            "supplier_technical_user_id",
            "supplier_response_date",
            "supplier_proposed_deadline",
            "containment_text",
            "cause_justification",
            "disposition",
            "concession_required",
            "deadline_impact",
            "new_deadline",
            "supplier_conclusion_date",
            "supplier_conclusion_user_id",
            "final_condition",
            "evidence_ids",
            "inspector_evidence_ids",
            "supplier_evidence_ids",
            "document_ids",
            "action_ids",
            "message_follower_ids",
            "message_ids",
        }

    def _check_portal_write(self, vals):
        if not self.env.user.share:
            return
        allowed = self._get_supplier_writable_fields() | {"stage_id"}
        forbidden = set(vals) - allowed
        if forbidden:
            raise AccessError(
                self.env._("Portal users can only update supplier response fields.")
            )
        if any(rec.state not in ("waiting_supplier", "open") for rec in self):
            raise AccessError(
                self.env._(
                    "The supplier can only update the occurrence while it is "
                    "released or in treatment."
                )
            )

    @api.onchange("classification")
    def _onchange_classification(self):
        if self.classification == "stop_work":
            self.stop_work = True
            self.priority = "immediate"

    @api.onchange("disposition")
    def _onchange_disposition(self):
        if self.disposition == "concession":
            self.concession_required = True

    @api.constrains("work_division", "work_division_other")
    def _check_work_division_other(self):
        for rec in self:
            if rec.work_division == "other" and not rec.work_division_other:
                raise ValidationError(
                    self.env._("Please describe the work division when Other is set.")
                )

    @api.constrains("classification", "stop_work", "stop_work_date")
    def _check_stop_work(self):
        for rec in self:
            if rec.classification == "stop_work" and not rec.stop_work:
                raise ValidationError(
                    self.env._(
                        "Critical Risk (Stop Work) requires the work stoppage flag."
                    )
                )
            if rec.stop_work and not rec.stop_work_date:
                raise ValidationError(self.env._("Please set the work stoppage date."))

    @api.constrains("stage_id")
    def _check_open_with_action_comments(self):
        """Occurrence workflow does not use OCA action-plan comments."""
        return

    def _check_can_release(self):
        for rec in self:
            if rec.state != "draft":
                raise UserError(
                    self.env._(
                        "Only draft occurrences can be released to the supplier."
                    )
                )
            if not rec.classification:
                raise UserError(self.env._("Please set the classification."))
            if not rec.description:
                raise UserError(self.env._("Please describe the observed condition."))
            if not rec.partner_id:
                raise UserError(self.env._("Please set the supplier partner."))

    def _check_can_submit(self):
        for rec in self:
            if rec.state not in ("waiting_supplier", "open"):
                raise UserError(
                    self.env._(
                        "The supplier response can only be submitted while the "
                        "occurrence is released or in treatment."
                    )
                )
            if not rec.containment_text:
                raise UserError(
                    self.env._("Please describe the containment and current condition.")
                )
            if not rec.cause_justification:
                raise UserError(
                    self.env._(
                        "Please provide the identified cause or "
                        "technical justification."
                    )
                )
            if not rec.disposition:
                raise UserError(self.env._("Please set the disposition."))
            if rec.disposition != "conclude" and not rec.action_ids:
                raise UserError(
                    self.env._("Please add at least one treatment plan action.")
                )

    def _check_can_verify(self):
        for rec in self:
            if rec.state != "waiting_verification":
                raise UserError(
                    self.env._(
                        "Verification is only available when the occurrence is "
                        "waiting for verification."
                    )
                )
            if not rec.evaluation_comments:
                raise UserError(
                    self.env._("Please enter the inspector opinion before closing.")
                )

    def action_release_to_supplier(self):
        self._check_can_release()
        for rec in self:
            rec._move_to_stage("waiting_supplier")
            if rec.partner_id:
                rec.message_subscribe(partner_ids=rec.partner_id.ids)
                rec.message_post(
                    body=self.env._(
                        "Occurrence %(ref)s was released to %(partner)s.",
                        ref=rec.ref,
                        partner=rec.partner_id.display_name,
                    ),
                    partner_ids=rec.partner_id.ids,
                    subtype_xmlid="mail.mt_comment",
                )
        return True

    def action_submit_response(self):
        self._check_can_submit()
        for rec in self:
            vals = {}
            if not rec.supplier_response_date:
                vals["supplier_response_date"] = fields.Date.context_today(rec)
            if vals:
                rec.write(vals)
            rec._move_to_stage("waiting_verification")
            rec.activity_schedule(
                "mail.mail_activity_data_todo",
                user_id=(rec.inspector_id or rec.user_id or rec.responsible_user_id).id,
                summary=self.env._("Verify occurrence %s", rec.ref),
            )
            rec.message_post(
                body=self.env._("Supplier response submitted for verification."),
                subtype_xmlid="mail.mt_comment",
            )
        return True

    def action_approve(self):
        return self._action_verify("approved", "close", "done")

    def action_approve_with_comments(self):
        return self._action_verify("approved_with_comments", "close", "done")

    def action_reject(self):
        self._check_can_verify()
        for rec in self:
            rec.write(
                {
                    "verification_result": "rejected",
                    "verification_date": fields.Date.context_today(rec),
                    "closure_decision": "keep_open",
                }
            )
            rec._move_to_stage("waiting_supplier")
            rec.message_post(
                body=self.env._("Occurrence rejected and returned to the supplier."),
                subtype_xmlid="mail.mt_comment",
            )
        return True

    def action_keep_open(self):
        self._check_can_verify()
        for rec in self:
            rec.write(
                {
                    "closure_decision": "keep_open",
                    "verification_date": fields.Date.context_today(rec),
                }
            )
            rec._move_to_stage("open")
        return True

    def action_reclassify(self, classification=None, note=None):
        self.ensure_one()
        if self.state not in ("waiting_verification", "draft", "open"):
            raise UserError(
                self.env._(
                    "This occurrence cannot be reclassified in the current stage."
                )
            )
        if not classification:
            return {
                "name": self.env._("Reclassify Occurrence"),
                "type": "ir.actions.act_window",
                "res_model": "mgmtsystem.nonconformity.reclassify",
                "view_mode": "form",
                "target": "new",
                "context": {"default_nonconformity_id": self.id},
            }
        self.write(
            {
                "classification": classification,
                "closure_decision": "reclassify",
                "verification_date": fields.Date.context_today(self),
            }
        )
        if note:
            self.message_post(body=note, subtype_xmlid="mail.mt_comment")
        self._move_to_stage("draft")
        return True

    def _action_verify(self, result, decision, target_state):
        self._check_can_verify()
        for rec in self:
            rec.write(
                {
                    "verification_result": result,
                    "verification_date": fields.Date.context_today(rec),
                    "closure_decision": decision,
                }
            )
            rec._move_to_stage(target_state)
        return True

    def write(self, vals):
        self._check_portal_write(vals)
        result = super().write(vals)
        if self.env.context.get("occurrence_skip_auto_open"):
            return result
        supplier_keys = self._get_supplier_writable_fields()
        if supplier_keys & set(vals) and "stage_id" not in vals:
            to_open = self.filtered(lambda rec: rec.state == "waiting_supplier")
            if to_open:
                to_open.with_context(occurrence_skip_auto_open=True)._move_to_stage(
                    "open"
                )
        return result
