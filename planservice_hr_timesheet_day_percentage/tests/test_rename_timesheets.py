# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase, tagged

from ..models.ir_module_module import rename_text


@tagged("post_install", "-at_install")
class TestRenameTimesheets(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_lang("pt_BR")
        cls.Module = cls.env["ir.module.module"]
        cls.Module._load_module_terms(["hr_timesheet"], ["pt_BR"])

    def _pt(self, xmlid, field="name"):
        return self.env.ref(xmlid).with_context(lang="pt_BR")[field]

    def test_rename_text_keeps_gender(self):
        cases = {
            "Planilhas de horas": "Lançamentos",
            "Minhas planilhas de horas": "Meus lançamentos",
            "Todas as planilhas de horas": "Todos os lançamentos",
            "Somente suas planilhas de horas": "Somente seus lançamentos",
            "Locais da Planilha de Horas": "Locais de lançamento",
            "Atividades da planilha de horas": "Atividades dos lançamentos",
            "Análise de planilhas de horas": "Análise de lançamentos",
            "Tempo de planilha de horas": "Tempo lançado",
            "registrar planilhas de horas": "registrar lançamentos",
        }
        for original, expected in cases.items():
            self.assertEqual(rename_text(original), expected)

    def test_menus_and_actions_renamed(self):
        self.assertEqual(self._pt("hr_timesheet.timesheet_menu_root"), "Lançamentos")
        self.assertEqual(
            self._pt("hr_timesheet.timesheet_action_all"), "Todos os lançamentos"
        )
        self.assertEqual(
            self._pt("hr_timesheet.act_hr_timesheet_line"), "Meus lançamentos"
        )
        # o inglês continua como está
        self.assertEqual(
            self.env.ref("hr_timesheet.timesheet_menu_root")
            .with_context(lang="en_US")
            .name,
            "Timesheets",
        )

    def test_fields_and_views_renamed(self):
        project = self.env["project.project"].with_context(lang="pt_BR")
        string = project.fields_get(["allow_timesheets"])["allow_timesheets"]
        self.assertEqual(string["string"], "Lançamentos")
        arch = self._pt("hr_timesheet.view_task_form2_inherited", "arch_db")
        self.assertNotIn("lanilha", arch)

    def test_reload_with_overwrite_keeps_new_names(self):
        self.Module._load_module_terms(["hr_timesheet"], ["pt_BR"], overwrite=True)
        self.assertEqual(self._pt("hr_timesheet.timesheet_menu_root"), "Lançamentos")

    def test_other_languages_untouched(self):
        menu = self.env.ref("hr_timesheet.timesheet_menu_root")
        self.Module._load_module_terms(["hr_timesheet"], ["en_US"])
        self.assertEqual(menu.with_context(lang="en_US").name, "Timesheets")
        self.assertEqual(menu.with_context(lang="pt_BR").name, "Lançamentos")
