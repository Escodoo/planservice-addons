# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import tagged

from .common import OccurrenceTestCase

REPORT_REF = "mgmtsystem_nonconformity.report_mgmtsystem_nonconformity"


@tagged("post_install", "-at_install")
class TestOccurrenceReportLang(OccurrenceTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env["res.lang"]._activate_and_install_lang("pt_BR")
        cls.env.user.lang = "pt_BR"
        cls.partner = cls.env["res.partner"].create(
            {"name": "Supplier Partner", "is_company": True}
        )
        cls.nc = cls.env["mgmtsystem.nonconformity"].create(
            {
                "name": "Column out of plumb",
                "partner_id": cls.partner.id,
                "manager_user_id": cls.env.user.id,
                "description": "Expected plumb column, found 15mm deviation.",
                "classification": "nc",
            }
        )
        cls.report = cls.env.ref(
            "planservice_mgmtsystem_occurrence.action_occurrence_report_draft"
        )

    def _report_env(self):
        """Environment like an HTTP print request: user is pt_BR, no lang key."""
        admin = self.env.ref("base.user_admin")
        admin.lang = "pt_BR"
        context = {k: v for k, v in self.env.context.items() if k != "lang"}
        return self.env(user=admin, context=context)

    def test_report_follows_user_lang_when_context_has_none(self):
        """A print request that arrives without lang uses the user's language."""
        html, _report_type = self._report_env()["ir.actions.report"]._render_qweb_html(
            REPORT_REF, self.nc.ids
        )
        self.assertIn("Classificação e encaminhamento".encode(), html)
        self.assertNotIn(b"Classification and routing", html)

    def test_report_ignores_context_lang_of_the_request(self):
        """The request's own lang (e.g. en_US) must not override the user's."""
        env = self._report_env()
        env = env(context=dict(env.context, lang="en_US"))
        html, _report_type = env["ir.actions.report"]._render_qweb_html(
            REPORT_REF, self.nc.ids
        )
        self.assertIn("Classificação e encaminhamento".encode(), html)
        self.assertNotIn(b"Classification and routing", html)

    def test_report_action_names_are_translated(self):
        draft = self.report.with_context(lang="pt_BR")
        self.assertEqual(draft.name, "Registro de Ocorrência - Minuta")
        official = self.env.ref(
            "planservice_mgmtsystem_occurrence.action_occurrence_report_official"
        ).with_context(lang="pt_BR")
        self.assertEqual(official.name, "Registro de Ocorrência - Oficial")

    def test_report_filename_follows_user_lang(self):
        admin = self.env.ref("base.user_admin")
        admin.lang = "pt_BR"
        nc = self.nc.with_user(admin).with_context(lang="en_US")
        self.assertEqual(
            nc.get_occurrence_report_filename(),
            f"Registro de Ocorrência (Minuta) - {self.nc.ref}",
        )
        admin.lang = "en_US"
        self.assertEqual(
            nc.get_occurrence_report_filename(),
            f"Occurrence Record (Draft) - {self.nc.ref}",
        )
