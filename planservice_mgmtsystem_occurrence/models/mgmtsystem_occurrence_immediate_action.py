# Copyright 2026 - TODAY, Marcel Savegnago <marcel.savegnago@escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import fields, models


class MgmtsystemOccurrenceImmediateAction(models.Model):
    _name = "mgmtsystem.occurrence.immediate.action"
    _description = "Occurrence Immediate Action"
    _order = "sequence, id"

    name = fields.Char(required=True, translate=True)
    code = fields.Char(required=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "code_uniq",
            "unique(code)",
            "The immediate action code must be unique.",
        )
    ]
