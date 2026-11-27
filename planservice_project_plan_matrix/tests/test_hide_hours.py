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
class TestHideHoursPlanMatrix(TransactionCase):
    def _root(self, model, view_type, view_xmlid=None):
        view_id = self.env.ref(view_xmlid).id if view_xmlid else None
        arch = self.env[model].get_view(view_id=view_id, view_type=view_type)["arch"]
        return etree.fromstring(arch)

    def test_tarefa_sem_tempo_em_horas_na_lista_e_no_formulario(self):
        """Tempo planejado e realizado não aparecem em horas na tarefa."""
        views = (
            ("list", "project.view_task_tree2"),
            ("form", "project.view_task_form2"),
        )
        for view_type, xmlid in views:
            root = self._root("project.task", view_type, xmlid)
            self.assertFalse(_visible_fields(root, "allocated_hours"), xmlid)
            self.assertFalse(_visible_fields(root, "effective_hours"), xmlid)

    def test_matriz_sem_horas(self):
        """A matriz de plano mostra percentual, sem horas."""
        for view_type in ("list", "pivot"):
            root = self._root("project.plan.cell", view_type)
            self.assertFalse(_visible_fields(root, "hours"), view_type)

    def test_aba_plano_do_projeto_sem_total_de_horas(self):
        """As linhas do plano, na ficha do projeto, não mostram o total em horas."""
        root = self._root("project.project", "form")
        self.assertTrue(root.xpath(".//field[@name='plan_line_ids']"))
        self.assertFalse(_visible_fields(root, "total_hours"))

    def test_formulario_da_tarefa_mantem_campos_das_condicoes(self):
        """Os campos de horas ficam ocultos, mas no arch: condições da tela usam.

        Sem o nó, ``invisible="allocated_hours == 0.0"`` quebra o formulário no
        navegador ("Name 'allocated_hours' is not defined").
        """
        root = self._root("project.task", "form", "project.view_task_form2")
        for name in ("allocated_hours", "effective_hours"):
            used = root.xpath(
                "//*[contains(@invisible, $name) or contains(@readonly, $name)]",
                name=name,
            )
            self.assertTrue(used, name)
            self.assertTrue(root.xpath("//field[@name=$name]", name=name), name)
            self.assertFalse(_visible_fields(root, name), name)

    def test_cabecalho_da_tarefa_sem_tempo_alocado_nem_progresso(self):
        """O tempo alocado e o progresso "(0%)" ao lado dele não aparecem."""
        root = self._root("project.task", "form", "project.view_task_form2")
        planned = root.xpath(
            "//div[field[@name='allocated_hours'][hasclass('o_task_planned_hours')]]"
        )[0]
        self.assertIn(planned.get("invisible"), HIDDEN)
        for label in root.xpath("//label[@for='allocated_hours']"):
            self.assertIn(label.get("invisible"), HIDDEN)
