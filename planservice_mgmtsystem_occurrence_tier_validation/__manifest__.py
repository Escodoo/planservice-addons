# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).
{
    "name": "Planservice Occurrence Tier Validation",
    "summary": "Tier validation for occurrence verification and concessions",
    "version": "18.0.1.0.0",
    "category": "Management System",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": [
        "planservice_mgmtsystem_occurrence",
        "base_tier_validation",
    ],
    "data": [
        "data/tier_definition.xml",
    ],
    "installable": True,
}
