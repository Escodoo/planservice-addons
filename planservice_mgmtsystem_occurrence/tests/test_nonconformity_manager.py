# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from psycopg2 import IntegrityError

from odoo.tests import Form, tagged
from odoo.tools import mute_logger

from .common import OccurrenceTestCase


@tagged("post_install", "-at_install")
class TestNonconformityManager(OccurrenceTestCase):
    """The manager follows the project manager when the project changes."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        users = cls.env["res.users"].with_context(no_reset_password=True)
        cls.user_a, cls.user_b, cls.other_user = (
            users.create({"name": name, "login": login, "email": f"{login}@test.com"})
            for name, login in (
                ("Manager A", "manager_a"),
                ("Manager B", "manager_b"),
                ("Other Manager", "manager_other"),
            )
        )
        project = cls.env["project.project"]
        cls.project_a = project.create({"name": "Project A", "user_id": cls.user_a.id})
        cls.project_b = project.create({"name": "Project B", "user_id": cls.user_b.id})
        cls.project_without_manager = project.create(
            {"name": "No manager", "user_id": False}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Manager Partner"})
        cls.origin = cls.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence"
        )

    def _create(self, **extra):
        vals = {
            "name": "Manager check",
            "partner_id": self.partner.id,
            "description": "Manager follows the project.",
            "origin_ids": [(6, 0, self.origin.ids)],
        }
        vals.update(extra)
        return self.env["mgmtsystem.nonconformity"].create(vals)

    def test_create_with_project_only(self):
        nc = self._create(project_id=self.project_a.id)
        self.assertEqual(nc.manager_user_id, self.user_a)

    def test_create_with_explicit_manager_wins(self):
        nc = self._create(
            project_id=self.project_a.id, manager_user_id=self.other_user.id
        )
        self.assertEqual(nc.manager_user_id, self.other_user)

    def test_changing_project_changes_manager(self):
        nc = self._create(project_id=self.project_a.id)
        nc.write({"project_id": self.project_b.id})
        self.assertEqual(nc.manager_user_id, self.user_b)

    def test_writing_project_and_manager_together_keeps_the_given_manager(self):
        nc = self._create(project_id=self.project_a.id)
        nc.write(
            {
                "project_id": self.project_b.id,
                "manager_user_id": self.other_user.id,
            }
        )
        self.assertEqual(nc.manager_user_id, self.other_user)

    def test_manual_manager_is_replaced_when_project_changes(self):
        nc = self._create(project_id=self.project_a.id)
        nc.write({"manager_user_id": self.other_user.id})
        nc.write({"project_id": self.project_b.id})
        self.assertEqual(nc.manager_user_id, self.user_b)

    def test_project_without_manager_keeps_manager(self):
        nc = self._create(project_id=self.project_a.id)
        nc.write({"project_id": self.project_without_manager.id})
        self.assertEqual(nc.manager_user_id, self.user_a)

    def test_removing_project_keeps_manager(self):
        nc = self._create(project_id=self.project_a.id)
        nc.write({"project_id": False})
        self.assertEqual(nc.manager_user_id, self.user_a)

    def test_no_project_and_no_manager_fails(self):
        with mute_logger("odoo.sql_db"), self.assertRaises(IntegrityError):
            self._create()

    def test_manager_without_project_is_kept(self):
        nc = self._create(manager_user_id=self.other_user.id)
        self.assertEqual(nc.manager_user_id, self.other_user)
        self.assertFalse(nc.project_id)

    def test_adjusting_manager_without_changing_project_is_kept(self):
        nc = self._create(project_id=self.project_a.id)
        nc.write({"manager_user_id": self.other_user.id})
        nc.write({"name": "Renamed"})
        self.assertEqual(nc.manager_user_id, self.other_user)

    def test_changing_the_project_manager_does_not_touch_existing_records(self):
        nc = self._create(project_id=self.project_a.id)
        self.project_a.write({"user_id": self.user_b.id})
        self.assertEqual(nc.manager_user_id, self.user_a)

    def test_form_fills_manager_when_project_is_chosen(self):
        """Simulate the screen without saving, so required fields can stay empty."""
        form = Form(self.env["mgmtsystem.nonconformity"])
        form.project_id = self.project_a
        self.assertEqual(form.manager_user_id, self.user_a)
        form.manager_user_id = self.other_user
        self.assertEqual(form.manager_user_id, self.other_user)
        form.project_id = self.project_b
        self.assertEqual(form.manager_user_id, self.user_b)
