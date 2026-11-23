# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import TransactionCase, tagged
from odoo.tools import convert_file

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
class TestHideHoursPlan(TransactionCase):
    def _root(self, model, view_type):
        arch = self.env[model].get_view(view_type=view_type)["arch"]
        return etree.fromstring(arch)

    def test_plano_mostra_capacidade_sem_horas(self):
        """A lista do plano mostra capacidade %, sem horas."""
        root = self._root("project.task.hour.plan", "list")
        self.assertFalse(_visible_fields(root, "hours"))
        self.assertFalse(_visible_fields(root, "monthly_hours"))
        self.assertTrue(_visible_fields(root, "capacity_percent"))

    def test_pivot_e_grafico_do_plano_sem_horas(self):
        for view_type in ("pivot", "graph"):
            root = self._root("project.task.hour.plan", view_type)
            self.assertFalse(root.xpath("//field[@name='hours']"), view_type)

    def test_aba_de_plano_da_tarefa_sem_horas(self):
        """Cabeçalho da aba de plano na tarefa não mostra horas."""
        root = self._root("project.task", "form")
        self.assertFalse(_visible_fields(root, "hour_plan_hours"))
        self.assertFalse(_visible_fields(root, "hour_plan_diff"))

    def test_pivot_de_tarefas_sem_tempo_alocado(self):
        root = self._root("project.task", "pivot")
        self.assertFalse(root.xpath("//field[@name='allocated_hours']"))

    def test_menu_do_plano_de_horas_so_no_modo_desenvolvedor(self):
        """Relatórios > Planos de Horas das Tarefas some do menu do dia a dia.

        Também na base já instalada, em que o menu tinha o grupo de usuário do
        projeto: a atualização do módulo tira esse grupo.
        """
        menu = self.env.ref(
            "planservice_project_task_hour_plan.menu_project_task_hour_plan"
        )
        no_one = self.env.ref("base.group_no_one")
        self.assertEqual(menu.groups_id, no_one)
        menu.groups_id |= self.env.ref("project.group_project_user")
        convert_file(
            self.env,
            "planservice_project_task_hour_plan",
            "views/project_task_hour_plan_views.xml",
            {},
            mode="update",
        )
        self.assertEqual(menu.groups_id, no_one)
