# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import base64
from operator import itemgetter

from markupsafe import Markup

from odoo import _, fields, http
from odoo.exceptions import AccessError, MissingError, UserError
from odoo.http import request
from odoo.osv.expression import AND
from odoo.tools import groupby as groupbyelem

from odoo.addons.portal.controllers.portal import CustomerPortal
from odoo.addons.portal.controllers.portal import pager as portal_pager
from odoo.addons.planservice_mgmtsystem_occurrence.models.occurrence_selection import (
    CLASSIFICATION_SELECTION,
    DISPOSITION_SELECTION,
)


class OccurrenceCustomerPortal(CustomerPortal):
    def _prepare_home_portal_values(self, counters):
        values = super()._prepare_home_portal_values(counters)
        if "occurrence_count" in counters:
            model = request.env["mgmtsystem.nonconformity"]
            values["occurrence_count"] = (
                model.search_count([]) if model.has_access("read") else 0
            )
        return values

    def _occurrence_domain(self):
        partner = request.env.user.commercial_partner_id
        return [("partner_id", "child_of", [partner.id])]

    def _occurrence_get_searchbar_sortings(self):
        return {
            "date": {"label": _("Newest"), "order": "create_date desc, id desc"},
            "ref": {"label": _("Reference"), "order": "ref desc, id desc"},
            "name": {"label": _("Title"), "order": "name, id desc"},
            "stage": {"label": _("Stage"), "order": "stage_id, id desc"},
            "classification": {
                "label": _("Classification"),
                "order": "classification, id desc",
            },
        }

    def _occurrence_get_searchbar_filters(self):
        filters = {
            "all": {"label": _("All"), "domain": []},
            "open": {
                "label": _("Open"),
                "domain": [("state", "not in", ("done", "cancel"))],
            },
            "closed": {
                "label": _("Closed"),
                "domain": [("state", "=", "done")],
            },
        }
        stages = request.env["mgmtsystem.nonconformity.stage"].search(
            [], order="sequence, id"
        )
        for stage in stages:
            filters[f"stage_{stage.id}"] = {
                "label": stage.name,
                "domain": [("stage_id", "=", stage.id)],
            }
        return filters

    def _occurrence_get_searchbar_projects(self):
        projects = {
            "all": {"label": _("All Projects"), "domain": []},
        }
        occurrences = request.env["mgmtsystem.nonconformity"].search(
            self._occurrence_domain()
        )
        for project in occurrences.sudo().mapped("project_id").sorted("name"):
            projects[f"project_{project.id}"] = {
                "label": project.display_name,
                "domain": [("project_id", "=", project.id)],
            }
        if any(not occ.project_id for occ in occurrences):
            projects["no_project"] = {
                "label": _("No Project"),
                "domain": [("project_id", "=", False)],
            }
        return projects

    def _occurrence_get_searchbar_inputs(self):
        return {
            "content": {
                "input": "content",
                "label": _(
                    "Search%(left)s Occurrences%(right)s",
                    left=Markup('<span class="nolabel">'),
                    right=Markup("</span>"),
                ),
                "sequence": 10,
            },
            "ref": {"input": "ref", "label": _("Search in Reference"), "sequence": 20},
            "name": {"input": "name", "label": _("Search in Title"), "sequence": 30},
            "classification": {
                "input": "classification",
                "label": _("Search in Classification"),
                "sequence": 40,
            },
            "stage_id": {
                "input": "stage_id",
                "label": _("Search in Stage"),
                "sequence": 50,
            },
            "project_id": {
                "input": "project_id",
                "label": _("Search in Project"),
                "sequence": 60,
            },
        }

    def _occurrence_get_searchbar_groupby(self):
        return {
            "none": {"input": "none", "label": _("None"), "sequence": 10},
            "stage_id": {"input": "stage_id", "label": _("Stage"), "sequence": 20},
            "classification": {
                "input": "classification",
                "label": _("Classification"),
                "sequence": 30,
            },
            "project_id": {
                "input": "project_id",
                "label": _("Project"),
                "sequence": 40,
            },
        }

    def _occurrence_get_search_domain(self, search_in, search):
        if search_in == "content":
            return [
                "|",
                "|",
                ("name", "ilike", search),
                ("ref", "ilike", search),
                ("description", "ilike", search),
            ]
        if search_in == "ref":
            return [("ref", "ilike", search)]
        if search_in == "name":
            return [("name", "ilike", search)]
        if search_in == "classification":
            return self._occurrence_classification_search_domain(search)
        if search_in == "stage_id":
            return [("stage_id.name", "ilike", search)]
        if search_in == "project_id":
            return [("project_id.name", "ilike", search)]
        return [
            "|",
            "|",
            ("name", "ilike", search),
            ("ref", "ilike", search),
            ("description", "ilike", search),
        ]

    def _occurrence_classification_search_domain(self, search):
        term = (search or "").lower()
        keys = [
            key
            for key, label in CLASSIFICATION_SELECTION
            if term in key or term in (label or "").lower()
        ]
        if keys:
            return [("classification", "in", keys)]
        return [("classification", "ilike", search)]

    def _prepare_my_occurrences_values(
        self,
        page=1,
        sortby=None,
        filterby="all",
        projectby="all",
        search=None,
        groupby="none",
        search_in="content",
        **kw,
    ):
        values = self._prepare_portal_layout_values()
        Occurrence = request.env["mgmtsystem.nonconformity"]
        searchbar_sortings = self._occurrence_get_searchbar_sortings()
        searchbar_filters = self._occurrence_get_searchbar_filters()
        searchbar_projects = self._occurrence_get_searchbar_projects()
        searchbar_inputs = dict(
            sorted(
                self._occurrence_get_searchbar_inputs().items(),
                key=lambda item: item[1]["sequence"],
            )
        )
        searchbar_groupby = dict(
            sorted(
                self._occurrence_get_searchbar_groupby().items(),
                key=lambda item: item[1]["sequence"],
            )
        )
        if not sortby or sortby not in searchbar_sortings:
            sortby = "date"
        if filterby not in searchbar_filters:
            filterby = "all"
        if projectby not in searchbar_projects:
            projectby = "all"
        if groupby not in searchbar_groupby:
            groupby = "none"
        if search_in not in searchbar_inputs:
            search_in = "content"

        domain = AND(
            [
                self._occurrence_domain(),
                searchbar_filters[filterby]["domain"],
                searchbar_projects[projectby]["domain"],
            ]
        )
        if search and search_in:
            domain = AND([domain, self._occurrence_get_search_domain(search_in, search)])

        occurrence_count = Occurrence.search_count(domain)
        pager = portal_pager(
            url="/my/occurrences",
            url_args={
                "sortby": sortby,
                "filterby": filterby,
                "projectby": projectby,
                "search": search,
                "search_in": search_in,
                "groupby": groupby,
            },
            total=occurrence_count,
            page=page,
            step=self._items_per_page,
        )
        order = searchbar_sortings[sortby]["order"]
        if groupby != "none":
            order = f"{groupby}, {order}"
        occurrences = Occurrence.search(
            domain,
            order=order,
            limit=self._items_per_page,
            offset=pager["offset"],
        )
        request.session["my_occurrences_history"] = occurrences.ids[:100]
        if not occurrences:
            grouped_occurrences = []
        elif groupby != "none":
            grouped_occurrences = [
                Occurrence.concat(*group)
                for _key, group in groupbyelem(occurrences, itemgetter(groupby))
            ]
        else:
            grouped_occurrences = [occurrences]

        values.update(
            {
                "occurrences": occurrences,
                "grouped_occurrences": grouped_occurrences,
                "page_name": "occurrence",
                "default_url": "/my/occurrences",
                "pager": pager,
                "searchbar_sortings": searchbar_sortings,
                "searchbar_filters": searchbar_filters,
                "searchbar_projects": searchbar_projects,
                "searchbar_inputs": searchbar_inputs,
                "searchbar_groupby": searchbar_groupby,
                "sortby": sortby,
                "filterby": filterby,
                "projectby": projectby,
                "groupby": groupby,
                "search_in": search_in,
                "search": search,
            }
        )
        return values

    def _get_occurrence(self, occurrence_id, access_token=None):
        try:
            return self._document_check_access(
                "mgmtsystem.nonconformity",
                occurrence_id,
                access_token=access_token,
            )
        except (AccessError, MissingError):
            return None

    @http.route(
        ["/my/occurrences", "/my/occurrences/page/<int:page>"],
        type="http",
        auth="user",
        website=True,
    )
    def portal_my_occurrences(
        self,
        page=1,
        sortby=None,
        filterby="all",
        projectby="all",
        search=None,
        groupby="none",
        search_in="content",
        **kw,
    ):
        Occurrence = request.env["mgmtsystem.nonconformity"]
        if not Occurrence.has_access("read"):
            return request.redirect("/my")
        values = self._prepare_my_occurrences_values(
            page=page,
            sortby=sortby,
            filterby=filterby,
            projectby=projectby,
            search=search,
            groupby=groupby,
            search_in=search_in,
            **kw,
        )
        return request.render(
            "planservice_mgmtsystem_occurrence_portal.portal_my_occurrences",
            values,
        )

    @http.route(
        ["/my/occurrences/<int:occurrence_id>"],
        type="http",
        auth="public",
        website=True,
    )
    def portal_my_occurrence(self, occurrence_id, access_token=None, **kw):
        occurrence = self._get_occurrence(occurrence_id, access_token=access_token)
        if occurrence is None:
            return request.redirect("/my")
        values = self._occurrence_page_values(occurrence, access_token)
        return request.render(
            "planservice_mgmtsystem_occurrence_portal.portal_my_occurrence",
            values,
        )

    def _occurrence_page_values(self, occurrence, access_token):
        supplier_can_edit = occurrence.state in ("waiting_supplier", "open")
        values = {
            "page_name": "occurrence",
            "occurrence": occurrence,
            "supplier_can_edit": supplier_can_edit,
            "disposition_selection": DISPOSITION_SELECTION,
            "error": request.params.get("error"),
        }
        return self._get_page_view_values(
            occurrence,
            access_token,
            values,
            "my_occurrences_history",
            False,
        )

    @http.route(
        ["/my/occurrences/<int:occurrence_id>/update"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def portal_occurrence_update(self, occurrence_id, **post):
        occurrence = self._get_occurrence(occurrence_id)
        if occurrence is None:
            return request.redirect("/my")
        if occurrence.state not in ("waiting_supplier", "open"):
            return request.redirect(occurrence.access_url)
        vals = self._prepare_supplier_vals(post)
        if vals:
            occurrence.sudo().write(vals)
        self._create_action_from_post(occurrence, post)
        self._create_evidence_from_post(occurrence, post)
        self._create_document_from_post(occurrence, post)
        return request.redirect(occurrence.access_url)

    @http.route(
        ["/my/occurrences/<int:occurrence_id>/submit"],
        type="http",
        auth="user",
        website=True,
        methods=["POST"],
        csrf=True,
    )
    def portal_occurrence_submit(self, occurrence_id, **post):
        occurrence = self._get_occurrence(occurrence_id)
        if occurrence is None:
            return request.redirect("/my")
        vals = self._prepare_supplier_vals(post)
        if vals:
            occurrence.sudo().write(vals)
        self._create_action_from_post(occurrence, post)
        self._create_evidence_from_post(occurrence, post)
        self._create_document_from_post(occurrence, post)
        try:
            occurrence.sudo().action_submit_response()
        except UserError as err:
            values = self._occurrence_page_values(occurrence, None)
            values["error"] = err.args[0]
            return request.render(
                "planservice_mgmtsystem_occurrence_portal.portal_my_occurrence",
                values,
            )
        return request.redirect(occurrence.access_url)

    def _prepare_supplier_vals(self, post):
        fields_map = {
            "containment_text": "containment_text",
            "cause_justification": "cause_justification",
            "disposition": "disposition",
            "final_condition": "final_condition",
            "supplier_proposed_deadline": "supplier_proposed_deadline",
            "new_deadline": "new_deadline",
            "supplier_conclusion_date": "supplier_conclusion_date",
        }
        vals = {}
        for key, field_name in fields_map.items():
            if key in post and post.get(key) not in (None, ""):
                vals[field_name] = post.get(key)
        if "concession_required" in post:
            vals["concession_required"] = bool(post.get("concession_required"))
        if "deadline_impact" in post:
            vals["deadline_impact"] = bool(post.get("deadline_impact"))
        if post.get("supplier_representative_id"):
            vals["supplier_representative_id"] = int(post["supplier_representative_id"])
        return vals

    def _create_action_from_post(self, occurrence, post):
        name = (post.get("action_name") or "").strip()
        if not name:
            return
        deadline = post.get("action_deadline") or False
        action = (
            request.env["mgmtsystem.action"]
            .sudo()
            .create(
                {
                    "name": name,
                    "type_action": "correction",
                    "user_id": occurrence.responsible_user_id.id or request.env.uid,
                    "date_deadline": deadline or False,
                    "description": post.get("action_description") or False,
                }
            )
        )
        occurrence.sudo().write({"action_ids": [fields.Command.link(action.id)]})

    def _create_evidence_from_post(self, occurrence, post):
        names = request.httprequest.form.getlist("evidence_name")
        types = request.httprequest.form.getlist("evidence_type")
        files = request.httprequest.files.getlist("evidence_file")
        today = fields.Date.context_today(occurrence)
        for index, raw_name in enumerate(names):
            name = (raw_name or "").strip()
            if not name:
                continue
            evidence_type = types[index] if index < len(types) else "photo"
            evidence = (
                request.env["mgmtsystem.nonconformity.evidence"]
                .sudo()
                .create(
                    {
                        "nonconformity_id": occurrence.id,
                        "section": "supplier",
                        "name": name,
                        "evidence_type": evidence_type or "photo",
                        "date": today,
                    }
                )
            )
            upload = files[index] if index < len(files) else None
            self._save_upload(evidence, upload)

    def _create_document_from_post(self, occurrence, post):
        types = request.httprequest.form.getlist("document_type")
        names = request.httprequest.form.getlist("document_name")
        files = request.httprequest.files.getlist("document_file")
        for index, doc_type in enumerate(types):
            if not doc_type:
                continue
            name = names[index] if index < len(names) else False
            document = (
                request.env["mgmtsystem.nonconformity.document"]
                .sudo()
                .create(
                    {
                        "nonconformity_id": occurrence.id,
                        "document_type": doc_type,
                        "name": name or False,
                    }
                )
            )
            upload = files[index] if index < len(files) else None
            self._save_upload(document, upload)

    def _save_upload(self, record, upload):
        if not upload or not upload.filename:
            return
        attachment = (
            request.env["ir.attachment"]
            .sudo()
            .create(
                {
                    "name": upload.filename,
                    "datas": base64.b64encode(upload.read()),
                    "res_model": record._name,
                    "res_id": record.id,
                }
            )
        )
        record.sudo().write({"attachment_ids": [fields.Command.link(attachment.id)]})
