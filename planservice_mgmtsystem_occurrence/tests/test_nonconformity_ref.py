# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from freezegun import freeze_time
from psycopg2 import IntegrityError

from odoo import api
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tools import mute_logger

from .common import OccurrenceTestCase

SEQUENCE_CODE = "mgmtsystem.nonconformity"


@tagged("post_install", "-at_install")
class TestNonconformityRef(OccurrenceTestCase):
    """Reference numbering: YYYYMM-NNN, one counter per month, never reused.

    Every test draws numbers from distant months (2031) so the real counter
    of the current month is never consumed.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.partner = cls.env["res.partner"].create({"name": "Ref Partner"})
        cls.origin = cls.env.ref(
            "planservice_mgmtsystem_occurrence.origin_field_occurrence"
        )

    def _create(self, date=None, env=None):
        env = env or self.env
        model = env["mgmtsystem.nonconformity"]
        if date:
            model = model.with_context(ir_sequence_date=date)
        return model.create(
            {
                "name": "Ref check",
                "partner_id": self.partner.id,
                "manager_user_id": self.env.user.id,
                "description": "Reference numbering.",
                "origin_ids": [(6, 0, self.origin.ids)],
            }
        )

    def _env_without_fixed_date(self, tz):
        context = {k: v for k, v in self.env.context.items() if k != "ir_sequence_date"}
        context["tz"] = tz
        return api.Environment(self.env.cr, self.env.uid, context)

    def test_sequence_configuration(self):
        seq = self.env.ref("mgmtsystem_nonconformity.seq_mgmtsystem_nonconformity")
        self.assertEqual(seq.prefix, "%(range_year)s%(range_month)s-")
        self.assertEqual(seq.padding, 3)
        self.assertTrue(seq.use_date_range)

    def test_format_and_counter(self):
        first = self._create("2031-01-10")
        second = self._create("2031-01-25")
        self.assertRegex(first.ref, r"^\d{6}-\d{3}$")
        self.assertEqual(first.ref, "203101-001")
        self.assertEqual(second.ref, "203101-002")

    def test_counter_restarts_each_month(self):
        self._create("2031-01-10")
        self._create("2031-01-11")
        self.assertEqual(self._create("2031-02-01").ref, "203102-001")

    def test_months_are_independent(self):
        self.assertEqual(self._create("2031-02-10").ref, "203102-001")
        self.assertEqual(self._create("2031-01-10").ref, "203101-001")
        self.assertEqual(self._create("2031-01-11").ref, "203101-002")
        self.assertEqual(self._create("2031-02-11").ref, "203102-002")

    def test_range_covers_exactly_one_month(self):
        self._create("2031-02-10")
        seq = self.env.ref("mgmtsystem_nonconformity.seq_mgmtsystem_nonconformity")
        date_range = seq.date_range_ids.filtered(
            lambda r: str(r.date_from) == "2031-02-01"
        )
        self.assertEqual(str(date_range.date_to), "2031-02-28")

    def test_month_follows_user_timezone(self):
        """01:00 UTC on Feb 1st is still Jan 31st (22:00) in Sao Paulo."""
        with freeze_time("2031-02-01 01:00:00"):
            sao_paulo = self._create(
                env=self._env_without_fixed_date("America/Sao_Paulo")
            )
            utc = self._create(env=self._env_without_fixed_date("UTC"))
        self.assertEqual(sao_paulo.ref, "203101-001")
        self.assertEqual(utc.ref, "203102-001")

    def _month_ranges(self, prefix="2031-01"):
        seq = self.env.ref("mgmtsystem_nonconformity.seq_mgmtsystem_nonconformity")
        return seq.date_range_ids.filtered(
            lambda r: str(r.date_from).startswith(prefix)
        )

    def _preview(self, env=None):
        return (env or self.env)["mgmtsystem.nonconformity"].default_get(["ref"])["ref"]

    def test_new_form_shows_first_number_of_the_month(self):
        self.assertEqual(self._preview(), "203101-001")
        self.assertFalse(self._month_ranges())

    def test_new_form_shows_next_number(self):
        self._create("2031-01-10")
        self._create("2031-01-11")
        self.assertEqual(self._preview(), "203101-003")

    def test_preview_does_not_consume_numbers(self):
        self._create("2031-01-10")
        for _i in range(3):
            self.assertEqual(self._preview(), "203101-002")
        self.assertEqual(self._create("2031-01-11").ref, "203101-002")

    def test_saved_number_matches_the_preview(self):
        self._create("2031-01-10")
        shown = self._preview()
        self.assertEqual(self._create("2031-01-11").ref, shown)

    def test_preview_may_differ_when_someone_saves_first(self):
        shown = self._preview()
        self._create("2031-01-10")
        self.assertEqual(self._create("2031-01-11").ref, "203101-002")
        self.assertEqual(shown, "203101-001")

    def test_preview_restarts_on_month_change(self):
        self._create("2031-01-10")
        env = self.env(context=dict(self.env.context, ir_sequence_date="2031-02-03"))
        self.assertEqual(self._preview(env), "203102-001")

    def test_preview_follows_user_timezone(self):
        with freeze_time("2031-02-01 01:00:00"):
            sao_paulo = self._preview(self._env_without_fixed_date("America/Sao_Paulo"))
            utc = self._preview(self._env_without_fixed_date("UTC"))
        self.assertEqual(sao_paulo, "203101-001")
        self.assertEqual(utc, "203102-001")

    def test_new_shown_when_sequence_is_missing(self):
        self.env.ref("mgmtsystem_nonconformity.seq_mgmtsystem_nonconformity").unlink()
        self.assertEqual(self._preview(), "NEW")

    def test_existing_reference_is_untouched(self):
        record = self._create("2031-01-10")
        record.write({"name": "Renamed"})
        self.assertEqual(record.ref, "203101-001")

    def test_other_sequences_keep_yearly_ranges(self):
        other = self.env["ir.sequence"].create(
            {"name": "Other", "code": "test.other", "use_date_range": True}
        )
        other.next_by_id(sequence_date="2031-05-10")
        self.assertEqual(
            [(str(r.date_from), str(r.date_to)) for r in other.date_range_ids],
            [("2031-01-01", "2031-12-31")],
        )

    def test_deleted_middle_number_is_not_reused(self):
        records = [self._create("2031-01-10") for _ in range(3)]
        records[1].unlink()
        self.assertEqual(self._create("2031-01-11").ref, "203101-004")

    def test_deleted_last_number_is_not_reused(self):
        records = [self._create("2031-01-10") for _ in range(3)]
        records[2].unlink()
        self.assertEqual(self._create("2031-01-11").ref, "203101-004")

    def test_deleting_every_record_does_not_restart_the_month(self):
        records = self._create("2031-01-10") + self._create("2031-01-11")
        records.unlink()
        self.assertEqual(self._create("2031-01-12").ref, "203101-003")

    @mute_logger("odoo.sql_db")
    def test_concurrent_range_creation_asks_to_save_again(self):
        """Losing the race on the month's first record gives a clear message."""
        range_model = type(self.env["ir.sequence.date_range"])
        with (
            patch.object(range_model, "create", side_effect=IntegrityError),
            self.assertRaises(UserError),
        ):
            self._create("2031-03-10")
