# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from lxml import etree

from odoo.tests import tagged

from .common import OccurrenceTestCase

LEFT_COLUMN = [
    "name",
    "create_date",
    "project_id",
    "ref",
    "revision",
    "inspector_id",
    "partner_id",
    "opening_date",
]
RIGHT_COLUMN = [
    "responsible_user_id",
    "user_id",
    "work_division",
    "work_division_other",
    "reference",
    "origin_ids",
    "classification",
    "priority",
    "stop_work",
    "stop_work_date",
    "manager_user_id",
    "system_id",
]


@tagged("post_install", "-at_install")
class TestFormLayout(OccurrenceTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.model = cls.env["mgmtsystem.nonconformity"]
        cls.arch = etree.fromstring(cls.model.get_view(view_type="form")["arch"])

    def _group_fields(self, name):
        group = self.arch.xpath(f"//group[@name='{name}']")[0]
        return group.findall("field")

    def test_left_column_order(self):
        names = [f.get("name") for f in self._group_fields("config")]
        self.assertEqual(names, LEFT_COLUMN)

    def test_right_column_order(self):
        names = [f.get("name") for f in self._group_fields("meta")]
        self.assertEqual(names, RIGHT_COLUMN)

    def test_no_layout_field_is_duplicated(self):
        names = [
            f.get("name")
            for group in ("config", "meta")
            for f in self._group_fields(group)
        ]
        self.assertEqual(len(names), len(set(names)))

    def test_responsible_and_filled_in_by_are_hidden(self):
        fields_by_name = {f.get("name"): f for f in self._group_fields("meta")}
        self.assertEqual(fields_by_name["responsible_user_id"].get("invisible"), "1")
        self.assertEqual(fields_by_name["user_id"].get("invisible"), "1")

    def test_filled_in_by_stays_visible_in_action_plan_list(self):
        """Hiding user_id in the header must not hide it in the actions list."""
        action_user = self.arch.xpath(
            "//field[@name='action_ids']//field[@name='user_id']"
        )
        self.assertTrue(action_user)
        self.assertNotEqual(action_user[0].get("invisible"), "1")

    def test_manager_keeps_its_read_only_rule(self):
        manager = self.arch.xpath(
            "//group[@name='meta']/field[@name='manager_user_id']"
        )[0]
        self.assertEqual(manager.get("readonly"), "state not in ('draft', 'analysis')")

    def test_reference_is_read_only(self):
        ref = self.arch.xpath("//group[@name='config']/field[@name='ref']")[0]
        self.assertEqual(ref.get("readonly"), "1")

    def test_inspector_is_locked(self):
        inspector = self.arch.xpath(
            "//group[@name='config']/field[@name='inspector_id']"
        )[0]
        self.assertEqual(inspector.get("readonly"), "1")

    def test_conditional_fields_keep_their_rules(self):
        other = self.arch.xpath("//field[@name='work_division_other']")[0]
        self.assertEqual(other.get("invisible"), "work_division != 'other'")
        self.assertEqual(other.get("required"), "work_division == 'other'")
        stop_date = self.arch.xpath("//field[@name='stop_work_date']")[0]
        self.assertEqual(stop_date.get("invisible"), "not stop_work")
        self.assertEqual(stop_date.get("required"), "stop_work")

    def test_revision_history_is_a_read_only_page(self):
        page = self.arch.xpath("//page[@name='revision_history']")[0]
        field = page.xpath(".//field[@name='revision_ids']")[0]
        self.assertEqual(field.get("readonly"), "1")
        self.assertEqual(page.get("invisible"), "not revision_ids")

    def test_rejection_opinion_is_highlighted_on_the_supplier_page(self):
        page = self.arch.xpath("//page[@name='supplier_response']")[0]
        self.assertEqual(
            page.get("invisible"), "state == 'draft' and not revision_number"
        )
        alert = page.xpath(".//div[hasclass('alert-warning')]")[0]
        self.assertEqual(alert.get("invisible"), "not rejection_opinion")
        self.assertTrue(alert.xpath(".//field[@name='rejection_opinion']"))

    def test_defaults_are_the_current_user(self):
        defaults = self.model.default_get(
            ["responsible_user_id", "user_id", "inspector_id"]
        )
        for field in ("responsible_user_id", "user_id", "inspector_id"):
            self.assertEqual(defaults[field], self.env.user.id, field)

    def test_responsible_is_still_required(self):
        self.assertTrue(self.model._fields["responsible_user_id"].required)

    def test_create_without_hidden_fields_uses_current_user(self):
        """A record can be saved from the form, where the hidden fields are not sent."""
        partner = self.env["res.partner"].create({"name": "Layout Partner"})
        origin = self.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence"
        )
        nc = self.model.create(
            {
                "name": "Layout check",
                "partner_id": partner.id,
                "manager_user_id": self.env.user.id,
                "description": "Created without the hidden fields.",
                "origin_ids": [(6, 0, origin.ids)],
            }
        )
        self.assertEqual(nc.responsible_user_id, self.env.user)
        self.assertEqual(nc.user_id, self.env.user)
        self.assertEqual(nc.inspector_id, self.env.user)

    def test_form_shows_occurrence_record_title(self):
        title = self.arch.xpath("//div[hasclass('oe_title')]/h1")
        self.assertEqual([t.text for t in title], ["Occurrence Record"])

    def _load_pt_br(self):
        """CI databases do not have pt_BR, so install it with the module terms."""
        self.env["res.lang"]._activate_lang("pt_BR")
        self.env["ir.module.module"]._load_module_terms(
            ["mgmtsystem_nonconformity", "planservice_mgmtsystem_occurrence"],
            ["pt_BR"],
            overwrite=True,
        )

    def test_menu_is_named_ro(self):
        self._load_pt_br()
        menu = self.env.ref("mgmtsystem_nonconformity.menu_open_nonconformity")
        self.assertEqual(menu.with_context(lang="en_US").name, "R.O.")
        self.assertEqual(menu.with_context(lang="pt_BR").name, "R.O.")

    def test_action_is_named_occurrence_record(self):
        self._load_pt_br()
        action = self.env.ref(
            "mgmtsystem_nonconformity.open_mgmtsystem_nonconformity_list"
        )
        self.assertEqual(action.with_context(lang="en_US").name, "Occurrence Record")
        self.assertEqual(
            action.with_context(lang="pt_BR").name, "Registro de Ocorrência"
        )
