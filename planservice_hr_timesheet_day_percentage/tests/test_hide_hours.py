# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import TransactionCase, tagged

HIDDEN = ("1", "True", "true")


def _visible_fields(root, name):
    """Nós do campo ``name`` que o usuário vê (sem invisible no nó nem no pai)."""
    visible = []
    for node in root.xpath(".//field[@name=$name]", name=name):
        hidden = any(
            n.get("invisible") in HIDDEN or n.get("column_invisible") in HIDDEN
            for n in [node, *node.iterancestors()]
        )
        if not hidden:
            visible.append(node)
    return visible


@tagged("post_install", "-at_install")
class TestHideHoursDayPercentage(TransactionCase):
    def _root(self, model, view_type, view_xmlid=None):
        view_id = self.env.ref(view_xmlid).id if view_xmlid else None
        arch = self.env[model].get_view(view_id=view_id, view_type=view_type)["arch"]
        return etree.fromstring(arch)

    def test_lancamento_so_em_percentual(self):
        """Lista e formulário de timesheet não mostram a quantidade de horas."""
        views = (
            ("list", "hr_timesheet.hr_timesheet_line_tree"),
            ("form", "hr_timesheet.hr_timesheet_line_form"),
        )
        for view_type, xmlid in views:
            root = self._root("account.analytic.line", view_type, xmlid)
            self.assertFalse(_visible_fields(root, "unit_amount"), xmlid)
            self.assertTrue(_visible_fields(root, "day_percentage"), xmlid)

    def test_aba_de_timesheet_da_tarefa_so_em_percentual(self):
        """A aba de timesheet da tarefa mostra só o % do dia."""
        root = self._root("project.task", "form")
        subviews = root.xpath("//field[@name='timesheet_ids']/list")
        self.assertTrue(subviews)
        for sub in subviews:
            self.assertFalse(_visible_fields(sub, "unit_amount"))
            self.assertTrue(_visible_fields(sub, "day_percentage"))
