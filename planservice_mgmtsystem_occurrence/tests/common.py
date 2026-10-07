# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo.tests import TransactionCase

# Tests create nonconformities, which draw numbers from a sequence that is not
# rolled back. A distant month keeps the current month's counter untouched.
TEST_SEQUENCE_DATE = "2031-01-15"


class OccurrenceTestCase(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(cls.env.context, ir_sequence_date=TEST_SEQUENCE_DATE)
        )
