# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Timesheet Project Task",
    "summary": "Log timesheets by project with auto-filled task",
    "version": "18.0.1.0.0",
    "category": "Human Resources",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": [
        "hr_timesheet",
        "planservice_hr_timesheet_day_percentage",
        "planservice_project_plan_matrix",
    ],
    "data": [
        "security/ir.model.access.csv",
        "views/timesheet_location_views.xml",
        "views/timesheet_attachment_wizard_views.xml",
        "views/hr_timesheet_views.xml",
    ],
    "installable": True,
}
