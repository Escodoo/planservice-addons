# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestListDefaultView(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.action_model = cls.env["ir.actions.act_window"]

    def _create_action(self, view_mode, **vals):
        return self.action_model.create(
            {
                "name": "Test action",
                "res_model": "res.partner",
                "view_mode": view_mode,
                **vals,
            }
        )

    def _modes(self, action):
        return [mode for _view_id, mode in action.views]

    def test_list_moved_first(self):
        action = self._create_action("kanban,list,form")
        self.assertEqual(self._modes(action), ["list", "kanban", "form"])

    def test_already_first_unchanged(self):
        action = self._create_action("list,kanban,form")
        self.assertEqual(self._modes(action), ["list", "kanban", "form"])

    def test_without_list_keeps_order(self):
        action = self._create_action("kanban,form")
        self.assertEqual(self._modes(action), ["kanban", "form"])

    def test_explicit_view_ids(self):
        kanban = self.env.ref("base.res_partner_kanban_view")
        tree = self.env.ref("base.view_partner_tree")
        form = self.env.ref("base.view_partner_form")
        action = self._create_action(
            "kanban,list,form",
            view_ids=[
                (0, 0, {"sequence": 1, "view_mode": "kanban", "view_id": kanban.id}),
                (0, 0, {"sequence": 2, "view_mode": "list", "view_id": tree.id}),
                (0, 0, {"sequence": 3, "view_mode": "form", "view_id": form.id}),
            ],
        )
        self.assertEqual(
            action.views,
            [(tree.id, "list"), (kanban.id, "kanban"), (form.id, "form")],
        )

    def test_view_id_without_view_ids(self):
        tree = self.env.ref("base.view_partner_tree")
        action = self._create_action("kanban,list,form", view_id=tree.id)
        self.assertEqual(
            action.views,
            [(tree.id, "list"), (False, "kanban"), (False, "form")],
        )

    def test_standard_action_opens_in_list(self):
        action = self.env.ref("base.action_partner_form")
        self.assertEqual(action.views[0][1], "list")
        self.assertIn("kanban", self._modes(action))

    def test_action_dict_sent_to_client(self):
        action = self.env.ref("base.action_partner_form")
        action_dict = action._get_action_dict()
        self.assertEqual(action_dict["views"][0][1], "list")
        self.assertEqual(
            sorted(self._modes(action)),
            sorted(mode for _view_id, mode in action_dict["views"]),
        )

    def test_read_sent_to_client(self):
        action = self.env.ref("base.action_partner_form")
        self.assertEqual(action.read(["views"])[0]["views"][0][1], "list")
