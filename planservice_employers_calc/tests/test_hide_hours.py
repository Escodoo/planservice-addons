# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import TransactionCase, tagged

HIDDEN = ("1", "True", "true")


def _visible_fields(root, name):
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
class TestHideHoursCostReport(TransactionCase):
    def _root(self, model, view_type):
        arch = self.env[model].get_view(view_type=view_type)["arch"]
        return etree.fromstring(arch)

    def test_relatorio_de_custo_sem_horas(self):
        """Relatório de custo por colaborador: sem quantidade de horas."""
        model = "planservice.employer.cost.report"
        root = self._root(model, "list")
        self.assertFalse(_visible_fields(root, "unit_amount"))
        self.assertTrue(_visible_fields(root, "day_percentage"))
        self.assertTrue(_visible_fields(root, "total_cost"))
        pivot = self._root(model, "pivot")
        self.assertFalse(pivot.xpath("//field[@name='unit_amount']"))

    def test_custo_planejado_sem_tempo_alocado(self):
        root = self._root("planservice.employer.planned.cost", "list")
        self.assertFalse(_visible_fields(root, "allocated_hours"))
        self.assertTrue(_visible_fields(root, "planned_cost"))

    def test_ficha_do_colaborador_so_com_salario_e_beneficios(self):
        """Aba Definições: sem custo por hora, provisões nem custo mensal total."""
        root = self._root("hr.employee", "form")
        self.assertTrue(_visible_fields(root, "employer_salary_benefits_cost"))
        self.assertFalse(_visible_fields(root, "hourly_cost"))
        self.assertFalse(_visible_fields(root, "employer_monthly_total_cost"))
        labels = root.xpath("//label[@for='hourly_cost']")
        self.assertTrue(all(label.get("invisible") in HIDDEN for label in labels))
        self.assertNotIn("employer_provisions_cost", self.env["hr.employee"]._fields)
        self.assertNotIn(
            "provisions_cost", self.env["planservice.employer.cost.report"]._fields
        )
