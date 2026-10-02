# Copyright 2026 - TODAY, Dener William <dener.gimenes@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import calendar

from psycopg2 import IntegrityError

from odoo import fields, models
from odoo.exceptions import UserError

NONCONFORMITY_SEQUENCE_CODE = "mgmtsystem.nonconformity"


def _month_bounds(day):
    """First and last day of the month that contains ``day``."""
    last_day = calendar.monthrange(day.year, day.month)[1]
    return day.replace(day=1), day.replace(day=last_day)


class IrSequence(models.Model):
    _inherit = "ir.sequence"

    def _get_next_preview(self, date):
        """Return the next number of the nonconformity sequence without drawing it.

        The value is a forecast: another user may save first. When the month's
        range does not exist yet, nothing is created and the number is 1.
        """
        self.ensure_one()
        day = fields.Date.to_date(date)
        date_from, date_to = _month_bounds(day)
        date_range = (
            self.env["ir.sequence.date_range"]
            .sudo()
            .search(
                [
                    ("sequence_id", "=", self.id),
                    ("date_from", "<=", day),
                    ("date_to", ">=", day),
                ],
                limit=1,
            )
        )
        number = 1
        if date_range:
            # Not stored: drop the cached value, numbers may have been drawn since.
            date_range.invalidate_recordset(["number_next_actual"])
            number = date_range.number_next_actual
            date_from = date_range.date_from
        return self.with_context(
            ir_sequence_date=fields.Date.to_string(day),
            ir_sequence_date_range=fields.Date.to_string(date_from),
        ).get_next_char(number)

    def _create_date_range_seq(self, date):
        """Create one range per month for the nonconformity reference.

        The other sequences keep the standard yearly ranges.
        """
        if self.code != NONCONFORMITY_SEQUENCE_CODE:
            return super()._create_date_range_seq(date)
        date_from, date_to = _month_bounds(fields.Date.to_date(date))
        vals = {
            "sequence_id": self.id,
            "date_from": date_from,
            "date_to": date_to,
        }
        try:
            with self.env.cr.savepoint():
                return self.env["ir.sequence.date_range"].sudo().create(vals)
        except IntegrityError as exc:
            # Another transaction created this month's range first. This one
            # cannot see it (REPEATABLE READ), so saving again is needed.
            raise UserError(
                self.env._(
                    "The reference for this month was being created by another "
                    "user. Please save again."
                )
            ) from exc
