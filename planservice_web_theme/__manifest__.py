# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Planservice Web Theme",
    "summary": "Apply Planservice brand colors to the backend navbar and buttons",
    "version": "18.0.1.0.0",
    "category": "Hidden",
    "author": "Escodoo",
    "website": "https://github.com/Escodoo/planservice-addons",
    "license": "AGPL-3",
    "development_status": "Beta",
    "maintainers": ["marcelsavegnago"],
    "depends": ["web"],
    "assets": {
        "web._assets_primary_variables": [
            (
                "prepend",
                "planservice_web_theme/static/src/scss/primary_variables.scss",
            ),
        ],
        "web.dark_mode_variables": [
            (
                "prepend",
                "planservice_web_theme/static/src/scss/primary_variables.dark.scss",
            ),
        ],
    },
    "installable": True,
}
