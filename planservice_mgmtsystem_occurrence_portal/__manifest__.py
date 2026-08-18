# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Planservice Occurrence Portal",
    "summary": "Let suppliers answer occurrence records from the portal",
    "version": "18.0.1.0.0",
    "category": "Management System",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": ["planservice_mgmtsystem_occurrence", "portal"],
    "data": [
        "security/ir.model.access.csv",
        "security/occurrence_portal_security.xml",
        "views/portal_templates.xml",
    ],
    "installable": True,
}
