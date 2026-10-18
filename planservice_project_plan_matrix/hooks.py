# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import Command


def disable_project_milestones(env):
    """Turn off the Milestones project setting and the flag on every project."""
    milestone_group = env.ref("project.group_project_milestone")
    for xmlid in ("base.group_user", "base.group_portal"):
        env.ref(xmlid).write({"implied_ids": [Command.unlink(milestone_group.id)]})
    milestone_group.write({"users": [Command.clear()]})
    env["project.project"].with_context(active_test=False).search(
        [("allow_milestones", "=", True)]
    ).write({"allow_milestones": False})


def post_init_hook(env):
    disable_project_milestones(env)
