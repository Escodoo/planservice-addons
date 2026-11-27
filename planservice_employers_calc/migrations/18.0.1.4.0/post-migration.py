# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api
from odoo.tools.sql import column_exists


def migrate(cr, version):
    """Descarta as provisões: o custo mensal passa a ser só salário + benefícios.

    A linha de base do previsto foi gravada com o custo total da versão vigente
    na data dela (salário + benefícios + provisões). O custo mensal e o previsto
    dessas linhas são reduzidos na proporção salário ÷ (salário + provisões)
    dessa versão, para comparar com o realizado na mesma base. A proporção, e
    não o valor da versão, preserva o que mais tenha entrado na linha de base.
    Depois o total das versões é recalculado e as colunas de provisões são
    apagadas.

    As ajudas dos campos sem "provisões" são recarregadas por cima das gravadas:
    sem o overwrite, o Odoo mantém a tradução antiga no banco.
    """
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    langs = [code for code, _name in env["res.lang"].get_installed() if code == "pt_BR"]
    env["ir.module.module"]._load_module_terms(
        ["planservice_employers_calc"], langs, overwrite=True
    )
    if column_exists(cr, "hr_employee", "employer_provisions_cost"):
        cr.execute("ALTER TABLE hr_employee DROP COLUMN employer_provisions_cost")
    if not column_exists(cr, "planservice_employer_cost_version", "provisions_cost"):
        return
    cr.execute(
        """
        UPDATE planservice_employer_planned_cost b
        SET planned_cost = b.planned_cost * s.ratio,
            monthly_cost = b.monthly_cost * s.ratio
        FROM (
            SELECT
                base.id,
                (
                    SELECT COALESCE(ver.salary_benefits_cost, 0) / NULLIF(
                        COALESCE(ver.salary_benefits_cost, 0)
                        + COALESCE(ver.provisions_cost, 0),
                        0
                    )
                    FROM planservice_employer_cost_version ver
                    WHERE ver.employee_id = base.employee_id
                        AND COALESCE(ver.date_from, '-infinity'::date)
                            <= base.baseline_date
                    ORDER BY ver.date_from DESC NULLS LAST
                    LIMIT 1
                ) AS ratio
            FROM planservice_employer_planned_cost base
        ) s
        WHERE s.id = b.id AND s.ratio IS NOT NULL
        """
    )
    cr.execute(
        """
        UPDATE planservice_employer_cost_version
        SET total_cost = COALESCE(salary_benefits_cost, 0)
        """
    )
    cr.execute(
        "ALTER TABLE planservice_employer_cost_version DROP COLUMN provisions_cost"
    )
