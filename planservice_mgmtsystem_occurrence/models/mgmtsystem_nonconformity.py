# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import io
import zipfile

from odoo import api, fields, models
from odoo.exceptions import AccessError, UserError, ValidationError

from .ir_sequence import NONCONFORMITY_SEQUENCE_CODE
from .occurrence_selection import (
    CLASSIFICATION_SELECTION,
    DISCIPLINE_SELECTION,
    DISPOSITION_SELECTION,
    WORK_DIVISION_SELECTION,
)

STAGE_XMLID = {
    "draft": "mgmtsystem_nonconformity.stage_draft",
    "waiting_supplier": "planservice_mgmtsystem_occurrence.stage_waiting_supplier",
    "waiting_verification": (
        "planservice_mgmtsystem_occurrence.stage_waiting_verification"
    ),
    "done": "mgmtsystem_nonconformity.stage_done",
}


REVISION_FIELDS = {"revision", "revision_number"}
APPROVED_RESULTS = ("approved", "approved_with_comments")


class MgmtsystemNonconformity(models.Model):
    _inherit = "mgmtsystem.nonconformity"

    ref = fields.Char(default=lambda self: self._default_ref())
    origin_ids = fields.Many2many(default=lambda self: self._default_origin_ids())
    responsible_user_id = fields.Many2one(default=lambda self: self.env.user)
    manager_user_id = fields.Many2one(
        compute="_compute_manager_user_id",
        store=True,
        readonly=False,
        precompute=True,
    )

    project_id = fields.Many2one("project.project", "Project / Work")
    inspector_id = fields.Many2one(
        "res.users",
        default=lambda self: self.env.user,
        tracking=True,
    )
    opening_date = fields.Date(default=fields.Date.context_today)
    revision_number = fields.Integer(default=0, copy=False, readonly=True)
    revision = fields.Char(
        compute="_compute_revision",
        store=True,
        readonly=True,
        copy=False,
    )
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
    revision_ids = fields.One2many(
        "mgmtsystem.nonconformity.revision",
        "nonconformity_id",
        string="Revision History",
        copy=False,
        readonly=True,
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
    reinspection_done_date = fields.Date("Reinspection Performed On")
    reinspection_result = fields.Selection(
        [
            ("satisfactory", "Satisfactory"),
            ("unsatisfactory", "Unsatisfactory"),
        ],
    )
    verification_comment_ids = fields.One2many(
        "mgmtsystem.nonconformity.verification.comment",
        "nonconformity_id",
        string="Verification Comments",
        copy=False,
    )
    closure_decision = fields.Selection(
        [
            ("close", "Close"),
            ("keep_open", "Keep Open"),
            ("reclassify", "Reclassify"),
        ]
    )
    rejection_opinion = fields.Text(
        readonly=True,
        copy=False,
        help="Inspector opinion that rejected the previous revision.",
    )

    @api.depends("revision_number")
    def _compute_revision(self):
        for nc in self:
            nc.revision = f"{nc.revision_number:02d}"

    @api.depends("project_id")
    def _compute_manager_user_id(self):
        """Follow the project manager when the project changes.

        Keeps the current manager if the project has none or was removed.
        """
        for nc in self:
            nc.manager_user_id = nc.project_id.sudo().user_id or nc.manager_user_id

    def _default_ref(self):
        """Provisional reference shown in a new form; the real one is drawn on save."""
        sequence = (
            self.env["ir.sequence"]
            .sudo()
            .search(
                [
                    ("code", "=", NONCONFORMITY_SEQUENCE_CODE),
                    ("company_id", "in", [self.env.company.id, False]),
                ],
                order="company_id",
                limit=1,
            )
        )
        if not sequence:
            return "NEW"
        day = self.env.context.get("ir_sequence_date") or fields.Date.to_string(
            fields.Date.context_today(self)
        )
        return sequence._get_next_preview(day)

    def _default_origin_ids(self):
        origin = self.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence",
            raise_if_not_found=False,
        )
        return origin

    @api.model_create_multi
    def create(self, vals_list):
        """Number the reference (YYYYMM-NNN) by the user's local date, not UTC."""
        if not self.env.context.get("ir_sequence_date"):
            today = fields.Date.to_string(fields.Date.context_today(self))
            self = self.with_context(ir_sequence_date=today)
        return super().create(vals_list)

    def _get_occurrence_report_labels(self):
        return {
            "classification_section": self.env._("1. Classification and routing"),
            "design_query": self.env._("Design Query (RFI/TQ)"),
            "inspector": self.env._("Inspector"),
        }

    def _get_project_filename_part(self):
        """Project code followed by the project name, without spaces."""
        project = self.project_id
        if not project:
            return ""
        code = getattr(project, "code", False) or ""
        name = (project.name or "").replace(" ", "")
        return f"{code}{name}"

    def _get_report_filename(self, official=False, revision=None):
        """Report file name in the user's language, without the extension."""
        self.ensure_one()
        env = self.with_context(lang=self.env.user.lang).env
        parts = []
        if not official:
            draft = env._("Draft")
            parts.append(f"({draft})")
        project = self._get_project_filename_part()
        if project:
            parts.append(project)
        parts.append(self.ref)
        if official:
            parts.append(revision or self.revision_ids[:1].revision or self.revision)
        return " - ".join(parts)

    def get_occurrence_report_filename(self, official=False):
        """Report file name used by the print actions."""
        return self._get_report_filename(official=official)

    def _create_revision_snapshot(self, result):
        """Freeze the revision being decided as a read-only PDF with metadata."""
        snapshots = self.env["mgmtsystem.nonconformity.revision"]
        for rec in self:
            # Render through the action, not the report name: the name points to
            # the base report, which has no paper format and leaves a wide margin.
            draft_report = self.env.ref(
                "planservice_mgmtsystem_occurrence.action_occurrence_report_draft"
            )
            content, _report_type = (
                self.env["ir.actions.report"]
                .with_context(occurrence_official=True)
                ._render_qweb_pdf(draft_report.id, rec.ids)
            )
            filename = rec._get_report_filename(official=True, revision=rec.revision)
            attachment = self.env["ir.attachment"].create(
                {
                    "name": f"{filename}.pdf",
                    "raw": content,
                    "res_model": rec._name,
                    "res_id": rec.id,
                }
            )
            snapshots |= (
                self.env["mgmtsystem.nonconformity.revision"]
                .sudo()
                .create(
                    {
                        "nonconformity_id": rec.id,
                        "revision": rec.revision,
                        "result": result,
                        "user_id": self.env.user.id,
                        "attachment_id": attachment.id,
                    }
                )
            )
        return snapshots

    def _bump_revision(self):
        """Start the next revision (00 -> 01 -> 02...); the reference is kept."""
        for rec in self.with_context(occurrence_revision_bump=True):
            rec.revision_number += 1

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
        if self.env.su or not self.env.user.share:
            return
        allowed = self._get_supplier_writable_fields() | {"stage_id"}
        forbidden = set(vals) - allowed
        if forbidden:
            raise AccessError(
                self.env._("Portal users can only update supplier response fields.")
            )
        if any(rec.state != "waiting_supplier" for rec in self):
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

    @api.constrains("reinspection_required", "reinspection_date")
    def _check_reinspection_date(self):
        for rec in self:
            if rec.reinspection_required and not rec.reinspection_date:
                raise ValidationError(
                    self.env._("Please set the planned reinspection date.")
                )

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
            if rec.state != "waiting_supplier":
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

    def _check_verification_comments(self):
        for rec in self:
            comments = rec.verification_comment_ids
            if not comments:
                raise UserError(
                    self.env._("Please add at least one verification comment.")
                )
            if not all(comment._is_complete() for comment in comments):
                raise UserError(
                    self.env._(
                        "Every verification comment needs a description, "
                        "a responsible and a deadline."
                    )
                )

    def _check_can_close(self):
        for rec in self:
            if rec.state != "waiting_verification":
                raise UserError(
                    self.env._(
                        "Only an occurrence waiting for verification can be closed."
                    )
                )
            if rec.verification_result not in APPROVED_RESULTS:
                raise UserError(
                    self.env._("Only an approved occurrence can be closed.")
                )
            if rec.reinspection_required and not (
                rec.reinspection_done_date and rec.reinspection_result
            ):
                raise UserError(
                    self.env._(
                        "The reinspection is pending: register its date and "
                        "result before closing."
                    )
                )

    def _supplier_portal_link_html(self):
        """Link to the record in the supplier portal, added to the release e-mail.

        The portal module overrides this; without it the e-mail has no link.
        """
        return ""

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
                    )
                    + rec._supplier_portal_link_html(),
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
        return self._record_verification_result("approved")

    def action_approve_with_comments(self):
        return self._record_verification_result("approved_with_comments")

    def action_close(self):
        """Close an approved occurrence; this freezes the revision."""
        self._check_can_close()
        for rec in self:
            rec.write({"closure_decision": "close"})
            rec._move_to_stage("done")
            rec._create_revision_snapshot(rec.verification_result)
            rec._create_attachments_zip()
        return True

    def _create_attachments_zip(self):
        """Pack the evidence and document attachments into one zip on the record."""
        self.ensure_one()
        attachments = (
            self.evidence_ids.attachment_ids | self.document_ids.attachment_ids
        ).filtered(lambda att: att.raw)
        if not attachments:
            return self.env["ir.attachment"]
        buffer = io.BytesIO()
        used_names = set()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for attachment in attachments.sorted("id"):
                revision = attachment.occurrence_revision or self.revision
                name = f"rev{revision}-{attachment.name or attachment.id}"
                if name in used_names:
                    name = f"{attachment.id}-{name}"
                used_names.add(name)
                archive.writestr(name, attachment.raw)
        filename = self._get_report_filename(official=True, revision=self.revision)
        return self.env["ir.attachment"].create(
            {
                "name": f"{filename} - anexos.zip",
                "raw": buffer.getvalue(),
                "mimetype": "application/zip",
                "res_model": self._name,
                "res_id": self.id,
            }
        )

    def action_reject(self):
        """Reject the response: freeze the revision and hand the record back.

        The record returns to the supplier as the next revision. The supplier
        response stays filled in so it can be adjusted, not redone.
        """
        self._check_can_verify()
        for rec in self:
            rec.write(
                {
                    "verification_result": "rejected",
                    "verification_date": fields.Date.context_today(rec),
                    "closure_decision": "keep_open",
                }
            )
            rec._create_revision_snapshot("rejected")
            rec._bump_revision()
            rec.write(
                {
                    "rejection_opinion": rec.evaluation_comments,
                    "evaluation_comments": False,
                    "verification_result": False,
                    "verification_date": False,
                    "reinspection_required": False,
                    "reinspection_date": False,
                    "closure_decision": False,
                }
            )
            rec._move_to_stage("waiting_supplier")
            rec.message_post(
                body=self.env._(
                    "Occurrence rejected and returned to the inspector as "
                    "revision %s.",
                    rec.revision,
                ),
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
                    "verification_result": False,
                }
            )
            rec._move_to_stage("waiting_supplier")
        return True

    def action_reclassify(self, classification=None, note=None):
        self.ensure_one()
        if self.state not in ("waiting_verification", "draft"):
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

    def _record_verification_result(self, result):
        """Record an approval; closing or keeping open is a separate decision."""
        self._check_can_verify()
        for rec in self:
            if rec.verification_result:
                raise UserError(
                    self.env._("The verification result was already recorded.")
                )
            if result == "approved_with_comments":
                rec._check_verification_comments()
            rec.write(
                {
                    "verification_result": result,
                    "verification_date": fields.Date.context_today(rec),
                }
            )
        return True

    def write(self, vals):
        if REVISION_FIELDS & set(vals) and not self.env.context.get(
            "occurrence_revision_bump"
        ):
            raise UserError(
                self.env._(
                    "The revision is managed by the system and cannot be edited."
                )
            )
        self._check_portal_write(vals)
        if "stage_id" in vals:
            self._check_not_reopened(vals["stage_id"])
        return super().write(vals)

    def _check_not_reopened(self, stage_id):
        """A closed occurrence cannot leave the "Encerrada" step."""
        new_stage = self.env["mgmtsystem.nonconformity.stage"].browse(stage_id)
        for rec in self:
            if rec.state == "done" and new_stage != rec.stage_id:
                raise UserError(
                    self.env._("Closed occurrences cannot be moved to another stage.")
                )
