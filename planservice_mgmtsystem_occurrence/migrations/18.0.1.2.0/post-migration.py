# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

from odoo import SUPERUSER_ID, api

_logger = logging.getLogger(__name__)

# Stage records are noupdate, so renamed labels from data/ never reach
# databases that already have the module installed. Write them here.
STAGE_NAMES = {
    "mgmtsystem_nonconformity.stage_draft": "Inspetor (abertura)",
    "planservice_mgmtsystem_occurrence.stage_waiting_supplier": (
        "Fornecedor (aguardando)"
    ),
    "planservice_mgmtsystem_occurrence.stage_waiting_verification": (
        "Inspetor (fechamento)"
    ),
    "mgmtsystem_nonconformity.stage_done": "Encerrada",
}


def _move_open_to_waiting_supplier(env):
    """Occurrences "open" were merged into the supplier step.

    The ids are logged before the move so the change can be rolled back.
    "cancel" is not touched here: its destination is still undecided.
    """
    open_stage = env.ref("mgmtsystem_nonconformity.stage_open", False)
    waiting = env.ref("planservice_mgmtsystem_occurrence.stage_waiting_supplier", False)
    if not open_stage or not waiting:
        return
    occurrences = (
        env["mgmtsystem.nonconformity"]
        .with_context(active_test=False, tracking_disable=True)
        .search([("stage_id", "=", open_stage.id)])
    )
    _logger.info(
        "Moving %s occurrence(s) from open to waiting_supplier. Ids: %s",
        len(occurrences),
        occurrences.ids,
    )
    occurrences.write({"stage_id": waiting.id})


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, name in STAGE_NAMES.items():
        stage = env.ref(xmlid, raise_if_not_found=False)
        if not stage:
            continue
        for lang in ("en_US", "pt_BR"):
            localized = stage.with_context(lang=lang)
            if localized.name != name:
                localized.name = name
    _move_open_to_waiting_supplier(env)
