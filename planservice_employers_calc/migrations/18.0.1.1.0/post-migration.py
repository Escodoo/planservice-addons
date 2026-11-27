# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from odoo import SUPERUSER_ID, api


def _create_initial_versions(env):
    """Custo atual da ficha vira a versão inicial (desde sempre).

    Só salário + benefícios: as provisões deixaram de existir na 18.0.1.4.0.
    """
    env.cr.execute(
        """
        INSERT INTO planservice_employer_cost_version (
            employee_id, date_from, salary_benefits_cost, total_cost, company_id,
            create_uid, create_date, write_uid, write_date
        )
        SELECT
            e.id, NULL,
            e.employer_salary_benefits_cost,
            e.employer_salary_benefits_cost,
            e.company_id,
            %(uid)s, now() AT TIME ZONE 'UTC', %(uid)s, now() AT TIME ZONE 'UTC'
        FROM hr_employee e
        WHERE COALESCE(e.employer_salary_benefits_cost, 0) <> 0
            AND NOT EXISTS (
                SELECT 1 FROM planservice_employer_cost_version v
                WHERE v.employee_id = e.id
            )
        """,
        {"uid": SUPERUSER_ID},
    )


def _create_locked_baselines(env):
    """Linha de base para projetos cujo status já não permite replanejar."""
    projects = (
        env["project.project"]
        .with_context(active_test=False)
        .search(
            [
                ("project_status", "!=", False),
                ("project_status.allow_replan", "=", False),
                ("employer_baseline_date", "=", False),
            ]
        )
    )
    projects._create_employer_baseline()


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    _create_initial_versions(env)
    _create_locked_baselines(env)
