# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import re

from odoo import api, models
from odoo.tools import SQL

LANG = "pt_BR"

# Trocas em ordem: primeiro as frases que mudam de gênero ou de sentido, depois
# o caso geral. O \1 guarda a maiúscula ou minúscula do original.
RENAMES = [
    (r"Tempo de planilha de horas", "Tempo lançado"),
    (r"([Tt])odas as planilhas de horas( trabalhadas)?", r"\1odos os lançamentos"),
    (r"([Mm])inhas planilhas de horas", r"\1eus lançamentos"),
    (r"([Ss])uas planilhas de horas", r"\1eus lançamentos"),
    (r"([Ss])ua planilha de horas", r"\1eus lançamentos"),
    (r"([Ll])ocais da [Pp]lanilha de [Hh]oras", r"\1ocais de lançamento"),
    (r"([Ll])ocal da [Pp]lanilha de [Hh]oras", r"\1ocal de lançamento"),
    (r"\ba planilha de horas", "os lançamentos"),
    (r"\bda [Pp]lanilha de [Hh]oras", "dos lançamentos"),
    (r"\bde [Pp]lanilhas? de [Hh]oras", "de lançamentos"),
    (r"Planilhas? de [Hh]oras", "Lançamentos"),
    (r"planilhas? de horas", "lançamentos"),
]
PATTERN = r"[Pp]lanilhas? de [Hh]oras"

# Colunas traduzíveis que aparecem na interface: menus, ações, campos, grupos
# de acesso e views. Ficam de fora a lista de apps e as dicas do digest.
TARGETS = [
    ("ir_ui_menu", "name"),
    ("ir_act_window", "name"),
    ("ir_act_window", "help"),
    ("ir_act_report_xml", "name"),
    ("ir_embedded_actions", "name"),
    ("ir_model", "name"),
    ("ir_model_fields", "field_description"),
    ("ir_model_fields", "help"),
    ("ir_model_fields_selection", "name"),
    ("ir_module_category", "name"),
    ("res_groups", "name"),
    ("ir_ui_view", "arch_db"),
]


def rename_text(text):
    for pattern, replacement in RENAMES:
        text = re.sub(pattern, replacement, text)
    return text


def rename_timesheets(env):
    """Troca "Planilha(s) de horas" por "Lançamentos" nos textos em pt_BR.

    O lançamento é em % do dia, então nada na interface deve falar em horas.
    Grava direto no jsonb da tradução: um .po não serve, porque o Odoo não
    sobrescreve a tradução que o hr_timesheet já gravou.
    """
    env.flush_all()
    cr = env.cr
    for table, column in TARGETS:
        cr.execute(
            SQL(
                "SELECT id, %(col)s->>%(lang)s FROM %(table)s "
                "WHERE %(col)s->>%(lang)s ~ %(pattern)s",
                col=SQL.identifier(column),
                table=SQL.identifier(table),
                lang=LANG,
                pattern=PATTERN,
            )
        )
        for record_id, value in cr.fetchall():
            cr.execute(
                SQL(
                    "UPDATE %(table)s SET %(col)s = %(col)s || jsonb_build_object("
                    "%(lang)s, %(value)s::text) WHERE id = %(id)s",
                    col=SQL.identifier(column),
                    table=SQL.identifier(table),
                    lang=LANG,
                    value=rename_text(value),
                    id=record_id,
                )
            )
    env.invalidate_all()
    env.registry.clear_all_caches()


class IrModuleModule(models.Model):
    _inherit = "ir.module.module"

    @api.model
    def _load_module_terms(
        self, modules, langs, overwrite=False, imported_module=False
    ):
        """Refaz a troca sempre que as traduções são carregadas.

        Cobre a instalação do pt_BR depois do módulo, a atualização do
        hr_timesheet e o --i18n-overwrite, que trariam o nome antigo de volta.
        """
        res = super()._load_module_terms(
            modules, langs, overwrite=overwrite, imported_module=imported_module
        )
        if LANG in langs:
            rename_timesheets(self.env)
        return res
