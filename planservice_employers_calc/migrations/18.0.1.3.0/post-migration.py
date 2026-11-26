# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def migrate(cr, version):
    """Recarrega as traduções pt_BR do módulo por cima das gravadas.

    "Custo real" passou a "Custo Realizado". Sem o overwrite, o Odoo mantém a
    tradução que já está no banco e o nome novo não aparece.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    langs = [code for code, _name in env["res.lang"].get_installed() if code == "pt_BR"]
    env["ir.module.module"]._load_module_terms(
        ["planservice_employers_calc"], langs, overwrite=True
    )
