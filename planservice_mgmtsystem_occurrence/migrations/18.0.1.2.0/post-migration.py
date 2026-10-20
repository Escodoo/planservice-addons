# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import logging

from odoo import SUPERUSER_ID, api

from odoo.addons.planservice_mgmtsystem_occurrence.hooks import rename_stages

_logger = logging.getLogger(__name__)

# Base stages outside the occurrence flow. Stage records are noupdate, so
# databases that already have the module installed are archived here.
ARCHIVED_STAGES = (
    "mgmtsystem_nonconformity.stage_analysis",
    "mgmtsystem_nonconformity.stage_pending",
    "mgmtsystem_nonconformity.stage_open",
    "mgmtsystem_nonconformity.stage_cancel",
)


def _move_open_to_waiting_supplier(env):
    """Occurrences "open" were merged into the supplier step.

    The ids are logged before the move so the change can be rolled back.
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


def _archive_base_stages(env):
    for xmlid in ARCHIVED_STAGES:
        stage = env.ref(xmlid, raise_if_not_found=False)
        if stage:
            stage.active = False


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    rename_stages(env)
    _move_open_to_waiting_supplier(env)
    _archive_base_stages(env)
