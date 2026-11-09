# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Planservice Employer Cost Calculation",
    "summary": "Demonstrativo do custo do colaborador por obra (projeto) "
    "com base nos lançamentos de horas",
    "version": "18.0.1.0.0",
    "category": "Tools",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Alpha",
    "depends": ["hr_timesheet", "hr_hourly_cost", "project"],
    "data": [
        "security/ir.model.access.csv",
        "views/hr_employee_views.xml",
        "views/project_project_views.xml",
        "report/planservice_employer_cost_report_views.xml",
        "report/planservice_employer_cost_project_report_views.xml",
    ],
    "installable": True,
}
