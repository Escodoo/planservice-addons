# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo.tests import tagged

from .common import OccurrenceTestCase


@tagged("post_install", "-at_install")
class TestProjectOccurrences(OccurrenceTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.project = cls.env["project.project"].create({"name": "Occurrence Project"})
        cls.origin = cls.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence"
        )
        cls.partner = cls.env["res.partner"].create(
            {"name": "Project Supplier", "is_company": True}
        )

    def _create_occurrence(self, project):
        return self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "Project occurrence",
                "project_id": project.id,
                "partner_id": self.partner.id,
                "manager_user_id": self.env.user.id,
                "responsible_user_id": self.env.user.id,
                "description": "Field deviation.",
                "origin_ids": [(6, 0, self.origin.ids)],
                "classification": "nc",
            }
        )

    def test_occurrence_count_follows_the_project(self):
        self.assertEqual(self.project.occurrence_count, 0)
        self._create_occurrence(self.project)
        self._create_occurrence(self.project)
        self.project.invalidate_recordset(["occurrence_count"])
        self.assertEqual(self.project.occurrence_count, 2)

    def test_view_action_filters_by_project(self):
        action = self.project.action_view_occurrences()
        self.assertEqual(action["domain"], [("project_id", "=", self.project.id)])
        self.assertEqual(action["context"]["default_project_id"], self.project.id)

    def test_new_action_prefills_the_project(self):
        action = self.project.action_new_occurrence()
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["context"]["default_project_id"], self.project.id)

    def _project_user(self, *groups):
        return self.env["res.users"].create(
            {
                "name": "Project only",
                "login": f"project_only_{len(groups)}",
                "groups_id": [(6, 0, [self.env.ref("project.group_project_user").id])]
                + [(4, self.env.ref(group).id) for group in groups],
            }
        )

    def _form_buttons(self, user):
        form = self.project.with_user(user).get_views([(False, "form")])
        arch = form["views"]["form"]["arch"]
        return {
            name
            for name in ("action_view_occurrences", "action_new_occurrence")
            if name in arch
        }

    def test_project_form_opens_without_occurrence_access(self):
        user = self._project_user()
        self.assertFalse(self._form_buttons(user))
        project = self.project.with_user(user)
        self.assertEqual(project.read(["name"])[0]["name"], "Occurrence Project")

    def test_viewer_sees_the_count_but_cannot_create(self):
        user = self._project_user("mgmtsystem.group_mgmtsystem_viewer")
        self._create_occurrence(self.project)
        self.assertEqual(self._form_buttons(user), {"action_view_occurrences"})
        self.assertEqual(self.project.with_user(user).occurrence_count, 1)
