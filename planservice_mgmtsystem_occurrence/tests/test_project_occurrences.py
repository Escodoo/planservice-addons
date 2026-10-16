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
