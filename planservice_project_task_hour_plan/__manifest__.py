# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Project Task Hour Plan",
    "summary": "Plan task hours by month and sync with planned dates",
    "version": "18.0.1.0.0",
    "category": "Project Management",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": ["project_timeline", "hr_timesheet"],
    "data": [
        "security/ir.model.access.csv",
        "security/project_task_hour_plan_security.xml",
        "views/res_config_settings_views.xml",
        "views/project_task_hour_plan_views.xml",
        "views/project_task_views.xml",
    ],
    "installable": True,
}
