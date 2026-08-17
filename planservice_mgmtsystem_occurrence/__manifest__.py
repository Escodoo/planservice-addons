# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Planservice Occurrence Record",
    "summary": "Field occurrence register on management-system nonconformities",
    "version": "18.0.1.0.0",
    "category": "Management System",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": ["mgmtsystem_nonconformity", "project"],
    "data": [
        "security/ir.model.access.csv",
        "data/mgmtsystem_nonconformity_origin.xml",
        "data/mgmtsystem_nonconformity_stage.xml",
        "data/mgmtsystem_occurrence_immediate_action.xml",
        "wizards/reclassify_wizard_views.xml",
        "views/mgmtsystem_nonconformity_views.xml",
        "reports/occurrence_report.xml",
        "reports/occurrence_report_templates.xml",
    ],
    "installable": True,
}
