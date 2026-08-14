# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Timesheet Day Percentage",
    "summary": "Log timesheets as a percentage of the working day",
    "version": "18.0.1.0.0",
    "category": "Human Resources",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": ["hr_timesheet"],
    "data": [
        "views/hr_timesheet_views.xml",
        "views/project_task_views.xml",
    ],
    "installable": True,
}
