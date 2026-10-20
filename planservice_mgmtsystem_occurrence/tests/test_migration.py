# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

import importlib.util

from odoo.tests import tagged
from odoo.tools.misc import file_path

from ..hooks import rename_stages
from .common import OccurrenceTestCase


def _load_migration(name):
    path = file_path(f"planservice_mgmtsystem_occurrence/migrations/18.0.1.2.0/{name}")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestMigration(OccurrenceTestCase):
    def test_post_migration_cleans_up_the_base_stages(self):
        migration = _load_migration("post-migration.py")
        open_stage = self.env.ref("mgmtsystem_nonconformity.stage_open")
        draft = self.env.ref("mgmtsystem_nonconformity.stage_draft")
        old_stages = open_stage | self.env.ref("mgmtsystem_nonconformity.stage_cancel")
        old_stages.active = True
        draft.with_context(lang="en_US").name = "Draft"
        partner = self.env["res.partner"].create({"name": "Supplier"})
        occurrence = self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "Open occurrence",
                "partner_id": partner.id,
                "manager_user_id": self.env.user.id,
                "responsible_user_id": self.env.user.id,
                "description": "Left in progress by an older version.",
                "stage_id": open_stage.id,
            }
        )

        migration.migrate(self.env.cr, "18.0.1.0.0")

        self.assertEqual(
            occurrence.stage_id,
            self.env.ref("planservice_mgmtsystem_occurrence.stage_waiting_supplier"),
        )
        self.assertFalse(any(old_stages.mapped("active")))
        self.assertEqual(draft.with_context(lang="en_US").name, "Inspector (opening)")

    def test_stages_are_named_in_pt_br(self):
        """The base module's .po would leave "Rascunho" and "Fechado"."""
        self.env["res.lang"]._activate_lang("pt_BR")
        draft = self.env.ref("mgmtsystem_nonconformity.stage_draft")
        done = self.env.ref("mgmtsystem_nonconformity.stage_done")
        draft.with_context(lang="pt_BR").name = "Rascunho"
        done.with_context(lang="pt_BR").name = "Fechado"

        rename_stages(self.env)

        self.assertEqual(draft.with_context(lang="pt_BR").name, "Inspetor (abertura)")
        self.assertEqual(done.with_context(lang="pt_BR").name, "Encerrada")

    def test_pre_migration_seeds_the_revision_number(self):
        migration = _load_migration("pre-migration.py")
        partner = self.env["res.partner"].create({"name": "Supplier"})
        occurrence = self.env["mgmtsystem.nonconformity"].create(
            {
                "name": "Revised occurrence",
                "partner_id": partner.id,
                "manager_user_id": self.env.user.id,
                "responsible_user_id": self.env.user.id,
                "description": "Revised before the numeric revision existed.",
            }
        )
        self.env.flush_all()
        self.env.cr.execute(
            "UPDATE mgmtsystem_nonconformity "
            "SET revision = '03', revision_number = NULL WHERE id = %s",
            [occurrence.id],
        )

        migration.migrate(self.env.cr, "18.0.1.0.0")

        self.env.cr.execute(
            "SELECT revision_number FROM mgmtsystem_nonconformity WHERE id = %s",
            [occurrence.id],
        )
        self.assertEqual(self.env.cr.fetchone()[0], 3)
