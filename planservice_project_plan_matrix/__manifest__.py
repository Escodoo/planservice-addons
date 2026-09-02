# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Project Plan Matrix",
    "summary": "Plan project resources by month with a matrix view",
    "version": "18.0.1.0.0",
    "category": "Project",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": [
        "project",
        "project_timeline",
        "hr_timesheet",
        "planservice_project_task_hour_plan",
    ],
    "data": [
        "security/ir.model.access.csv",
        "security/project_plan_security.xml",
        "views/project_plan_stage_views.xml",
        "views/project_plan_role_views.xml",
        "views/project_plan_cell_views.xml",
        "views/project_project_views.xml",
    ],
    "installable": True,
}
