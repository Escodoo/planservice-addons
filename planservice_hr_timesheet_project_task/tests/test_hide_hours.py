# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import TransactionCase, tagged

HIDDEN = ("1", "True", "true")


def _visible_fields(root, name):
    """Nós do campo ``name`` que o usuário vê (sem invisible no nó nem no pai)."""
    return [
        node
        for node in root.xpath(".//field[@name=$name]", name=name)
        if not any(
            n.get("invisible") in HIDDEN or n.get("column_invisible") in HIDDEN
            for n in [node, *node.iterancestors()]
        )
    ]


@tagged("post_install", "-at_install")
class TestHideHoursTimesheetTask(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.manager = cls.env["res.users"].create(
            {
                "name": "Gestor timesheet",
                "login": "manager.hide.hours@test.com",
                "groups_id": [
                    (4, cls.env.ref("base.group_user").id),
                    (4, cls.env.ref("hr_timesheet.group_timesheet_manager").id),
                ],
            }
        )

    def _root(self, view_type, user):
        model = self.env["account.analytic.line"].with_user(user)
        return etree.fromstring(model.get_view(view_type=view_type)["arch"])

    def test_gestor_tambem_nao_ve_horas(self):
        """Nem o gestor de timesheet vê a quantidade de horas."""
        for view_type in ("list", "form"):
            root = self._root(view_type, self.manager)
            self.assertFalse(_visible_fields(root, "unit_amount"), view_type)
