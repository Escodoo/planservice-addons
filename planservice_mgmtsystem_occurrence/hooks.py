# Copyright 2026 Dener William - Escodoo <https://escodoo.com.br>
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

# Stage names as (English source, Brazilian Portuguese). The base stages get
# their pt_BR names from mgmtsystem_nonconformity's .po, which wins over ours,
# and stage records are noupdate, so the names are written here.
STAGE_NAMES = {
    "mgmtsystem_nonconformity.stage_draft": (
        "Inspector (opening)",
        "Inspetor (abertura)",
    ),
    "planservice_mgmtsystem_occurrence.stage_waiting_supplier": (
        "Supplier (waiting)",
        "Fornecedor (aguardando)",
    ),
    "planservice_mgmtsystem_occurrence.stage_waiting_verification": (
        "Inspector (closing)",
        "Inspetor (fechamento)",
    ),
    "mgmtsystem_nonconformity.stage_done": ("Closed", "Encerrada"),
}


def rename_stages(env):
    """Name the occurrence stages in English and, when active, pt_BR."""
    has_pt_br = bool(env["res.lang"]._lang_get("pt_BR"))
    for xmlid, (name, name_pt_br) in STAGE_NAMES.items():
        stage = env.ref(xmlid, raise_if_not_found=False)
        if not stage:
            continue
        stage.with_context(lang="en_US").name = name
        if has_pt_br:
            stage.with_context(lang="pt_BR").name = name_pt_br


def post_init_hook(env):
    rename_stages(env)
