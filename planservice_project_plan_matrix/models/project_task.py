# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from lxml import etree

from odoo import api, fields, models


class ProjectTask(models.Model):
    _inherit = "project.task"

    allocated_hours = fields.Float(string="Planned Time")
    effective_hours = fields.Float(string="Actual Time")
    user_ids = fields.Many2many(string="Collaborator")
    plan_line_id = fields.Many2one(
        comodel_name="project.plan.line",
        string="Plan Line",
        ondelete="set null",
        index="btree_not_null",
        copy=False,
        readonly=True,
        help="Project plan line that generated this task.",
    )
    has_plan = fields.Boolean(
        compute="_compute_has_plan",
        help="The project has a plan, so its planning fields are driven by it.",
    )

    @api.depends("project_id.plan_line_ids")
    def _compute_has_plan(self):
        for task in self:
            task.has_plan = bool(task.project_id.plan_line_ids)

    @api.model
    def _get_view_postprocessed(self, view, arch, **options):
        """Oculta o tempo planejado e o realizado em horas nas views da tarefa.

        O Odoo aplica atributos de herança só na primeira ocorrência de um xpath,
        e os campos de horas aparecem em mais de um lugar (inclusive sob condição).
        Ocultar os nós depois do pós-processamento cobre todas as views. Os nós
        não são removidos: condições da tela (ex.: ``allocated_hours == 0.0``)
        precisam do campo no arch, senão o formulário quebra no navegador.
        """
        arch, models = super()._get_view_postprocessed(view, arch, **options)
        root = etree.fromstring(arch)
        for node in root.xpath(
            "//field[@name='allocated_hours' or @name='effective_hours']"
        ):
            in_list = node.getparent().tag == "list"
            node.set("column_invisible" if in_list else "invisible", "True")
        return etree.tostring(root, encoding="unicode"), models
