# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Planservice Employer Cost Dashboard",
    "summary": "Dashboard Boardkit de custo previsto x real por obra, com botão "
    "no projeto que abre o dashboard filtrado nessa obra",
    "version": "18.0.1.0.0",
    "category": "Tools",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Alpha",
    "depends": [
        "hr_timesheet",
        "planservice_employers_calc",
        "boardkit_dashboard",
    ],
    "data": [
        "views/project_project_views.xml",
    ],
    "post_init_hook": "post_init_hook",
    "installable": True,
}
