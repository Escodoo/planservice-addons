# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

import importlib.util
from datetime import date, timedelta

from psycopg2 import IntegrityError

from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, freeze_time, tagged
from odoo.tools import mute_logger
from odoo.tools.misc import file_path


def _load_migration(version="18.0.1.1.0"):
    path = file_path(
        f"planservice_employers_calc/migrations/{version}/post-migration.py"
    )
    name = "employers_calc_post_" + version.replace(".", "_")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@tagged("post_install", "-at_install")
class TestCostBaseline(TransactionCase):
    """Versões de custo com vigência e linha de base do previsto."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.Version = cls.env["planservice.employer.cost.version"]
        cls.Baseline = cls.env["planservice.employer.planned.cost"]
        cls.calendar = cls.env["resource.calendar"].create(
            {"name": "Teste 8h baseline", "hours_per_day": 8.0}
        )
        cls.status_pending = cls.env.ref("project_status.project_status_pending")
        cls.status_progress = cls.env.ref("project_status.project_status_in_progress")
        cls.status_complete = cls.env.ref("project_status.project_status_complete")
        cls.user = cls.env["res.users"].create(
            {
                "name": "Dora",
                "login": "dora.baseline@test.com",
                "groups_id": [(4, cls.env.ref("base.group_user").id)],
            }
        )
        # custo mensal 10000 (8000 + 2000), desde sempre
        cls.dora = cls.env["hr.employee"].create(
            {
                "name": "Dora",
                "user_id": cls.user.id,
                "resource_calendar_id": cls.calendar.id,
                "employer_salary_benefits_cost": 8000.0,
                "employer_provisions_cost": 2000.0,
            }
        )
        cls.today = cls.env["hr.employee"]._employer_cost_today()

    def _project(self, name="Obra"):
        project = self.env["project.project"].create(
            {"name": name, "privacy_visibility": "employees"}
        )
        self.assertEqual(project.project_status, self.status_pending)
        return project

    def _task(self, project, hours, users=None, **vals):
        users = self.user if users is None else users
        return self.env["project.task"].create(
            dict(
                {
                    "name": "Tarefa",
                    "project_id": project.id,
                    "allocated_hours": hours,
                    "user_ids": [(6, 0, users.ids)],
                },
                **vals,
            )
        )

    def _line(self, project, employee, day, hours=8.0):
        return self.env["account.analytic.line"].create(
            {
                "name": "Horas",
                "project_id": project.id,
                "employee_id": employee.id,
                "unit_amount": hours,
                "date": day,
            }
        )

    def _lock(self, project):
        project.project_status = self.status_progress

    def _versions(self, employee):
        return self.Version.search([("employee_id", "=", employee.id)])

    def _real_cost(self, project):
        report = self.env["planservice.employer.cost.report"].search(
            [("project_id", "=", project.id)]
        )
        return sum(report.mapped("total_cost"))

    # Versões de custo

    def test_initial_version_since_always(self):
        version = self._versions(self.dora)
        self.assertEqual(len(version), 1)
        self.assertFalse(version.date_from)
        self.assertAlmostEqual(version.total_cost, 10000.0)
        self.assertEqual(
            version.with_context(lang="en_US").date_from_label, "Since always"
        )

    def test_no_version_for_employee_without_cost(self):
        employee = self.env["hr.employee"].create({"name": "Sem custo"})
        self.assertFalse(self._versions(employee))
        employee.employer_salary_benefits_cost = 3000.0
        version = self._versions(employee)
        self.assertEqual(len(version), 1)
        self.assertFalse(version.date_from, "first value applies since always")

    @freeze_time("2026-04-14 15:00:00")
    def test_change_applies_next_day(self):
        # banco criado só com pt_BR deixa o en_US inativo
        self.env["res.lang"]._activate_lang("en_US")
        self.env.user.tz = "America/Sao_Paulo"
        self.dora.employer_salary_benefits_cost = 18000.0
        versions = self._versions(self.dora)
        self.assertEqual(versions.mapped("date_from"), [date(2026, 4, 15), False])
        self.assertEqual(
            versions[0].with_context(lang="en_US").date_from_label, "04/15/2026"
        )
        self.assertAlmostEqual(versions[0].total_cost, 20000.0)
        self.assertAlmostEqual(versions[1].total_cost, 10000.0)

    @freeze_time("2026-04-15 01:00:00")
    def test_change_at_night_uses_local_day(self):
        # 22h de 14/04 em São Paulo (01h de 15/04 em UTC)
        self.env.user.tz = "America/Sao_Paulo"
        self.dora.employer_provisions_cost = 3000.0
        self.assertEqual(self._versions(self.dora)[0].date_from, date(2026, 4, 15))

    @freeze_time("2026-04-15 01:00:00")
    def test_user_without_tz_uses_sao_paulo(self):
        self.env.user.tz = False
        self.dora.with_context(tz=False).employer_provisions_cost = 3000.0
        self.assertEqual(self._versions(self.dora)[0].date_from, date(2026, 4, 15))

    def test_save_without_change_creates_no_version(self):
        self.dora.write(
            {
                "employer_salary_benefits_cost": 8000.0,
                "employer_provisions_cost": 2000.0,
                "job_title": "Engenheira",
            }
        )
        self.assertEqual(len(self._versions(self.dora)), 1)

    def test_same_day_correction_single_version(self):
        self.dora.employer_salary_benefits_cost = 18000.0
        self.dora.employer_salary_benefits_cost = 16000.0
        versions = self._versions(self.dora)
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0].date_from, self.today + timedelta(days=1))
        self.assertAlmostEqual(versions[0].total_cost, 18000.0)

    def test_single_initial_version_per_employee(self):
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.Version.create({"employee_id": self.dora.id, "date_from": False})

    def test_version_access(self):
        hr_user = self.env["res.users"].create(
            {
                "name": "RH",
                "login": "rh.baseline@test.com",
                "groups_id": [(4, self.env.ref("hr.group_hr_user").id)],
            }
        )
        other = self.env["res.users"].create(
            {
                "name": "Outro",
                "login": "outro.baseline@test.com",
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )
        self.assertEqual(
            self.Version.with_user(hr_user).search_count(
                [("employee_id", "=", self.dora.id)]
            ),
            1,
        )
        with self.assertRaises(AccessError):
            self.Version.with_user(hr_user).create({"employee_id": self.dora.id})
        with self.assertRaises(AccessError):
            self._versions(self.dora).with_user(hr_user).unlink()
        with self.assertRaises(AccessError):
            self.Version.with_user(other).search_count([])
        # RH altera pela ficha: a versão é gravada mesmo sem acesso de escrita
        self.dora.with_user(hr_user).employer_provisions_cost = 2500.0
        self.assertEqual(len(self._versions(self.dora)), 2)

    # Custo real pela versão vigente

    def test_real_cost_uses_version_valid_on_entry_date(self):
        """10000 até 12/12 (sexta), 20000 a partir de 15/12; dezembro/2025: 23 dias."""
        project = self._project()
        self.Version.create(
            {
                "employee_id": self.dora.id,
                "date_from": date(2025, 12, 15),
                "salary_benefits_cost": 18000.0,
                "provisions_cost": 2000.0,
            }
        )
        self._line(project, self.dora, date(2025, 12, 12))
        self._line(project, self.dora, date(2025, 12, 15))
        report = self.env["planservice.employer.cost.report"].search(
            [("project_id", "=", project.id)], order="date"
        )
        self.assertAlmostEqual(report[0].total_cost, 10000.0 / 23)
        self.assertAlmostEqual(report[1].total_cost, 20000.0 / 23)

    def test_raise_does_not_rewrite_past(self):
        project = self._project()
        self._line(project, self.dora, self.today)
        self._line(project, self.dora, self.today - timedelta(days=40))
        before = self._real_cost(project)
        self.dora.employer_salary_benefits_cost = 38000.0
        self.assertAlmostEqual(self._real_cost(project), before)

    def test_month_with_raise_in_the_middle(self):
        """Todos os dias úteis de dezembro/2025, aumento vigente em 15/12."""
        project = self._project()
        self.Version.create(
            {
                "employee_id": self.dora.id,
                "date_from": date(2025, 12, 15),
                "salary_benefits_cost": 18000.0,
                "provisions_cost": 2000.0,
            }
        )
        day = date(2025, 12, 1)
        before = after = 0
        while day.month == 12:
            if day.weekday() < 5:
                self._line(project, self.dora, day)
                if day < date(2025, 12, 15):
                    before += 1
                else:
                    after += 1
            day += timedelta(days=1)
        self.assertEqual(before + after, 23)
        expected = before * 10000.0 / 23 + after * 20000.0 / 23
        self.assertAlmostEqual(self._real_cost(project), expected)

    # Linha de base do previsto

    def test_baseline_created_when_plan_locks(self):
        project = self._project()
        self._task(project, 160.0)
        self.assertAlmostEqual(project.employer_planned_cost, 10000.0)
        self.assertFalse(project.employer_baseline_date)
        self._lock(project)
        self.assertEqual(project.employer_baseline_date, self.today)
        baseline = self.Baseline.search([("project_id", "=", project.id)])
        self.assertTrue(baseline)
        self.assertAlmostEqual(sum(baseline.mapped("planned_cost")), 10000.0)
        self.assertAlmostEqual(project.employer_planned_cost, 10000.0)

    def test_next_status_keeps_baseline(self):
        project = self._project()
        self._task(project, 160.0)
        self._lock(project)
        baseline = self.Baseline.search([("project_id", "=", project.id)])
        project.project_status = self.status_complete
        self.assertEqual(
            self.Baseline.search([("project_id", "=", project.id)]), baseline
        )
        self.assertEqual(project.employer_baseline_date, self.today)

    def test_planned_fixed_after_raise(self):
        locked = self._project("Travada")
        pending = self._project("Pendente")
        self._task(locked, 160.0)
        self._task(pending, 160.0)
        self._lock(locked)
        # aumento já vigente hoje
        self.Version.create(
            {
                "employee_id": self.dora.id,
                "date_from": self.today - timedelta(days=1),
                "salary_benefits_cost": 18000.0,
                "provisions_cost": 2000.0,
            }
        )
        locked.invalidate_recordset()
        pending.invalidate_recordset()
        self.assertAlmostEqual(locked.employer_planned_cost, 10000.0)
        self.assertAlmostEqual(pending.employer_planned_cost, 20000.0)

    def test_scope_change_after_lock_keeps_planned(self):
        other_user = self.env["res.users"].create(
            {
                "name": "Eli",
                "login": "eli.baseline@test.com",
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )
        self.env["hr.employee"].create(
            {
                "name": "Eli",
                "user_id": other_user.id,
                "employer_salary_benefits_cost": 50000.0,
            }
        )
        project = self._project()
        task = self._task(project, 160.0)
        self._lock(project)
        task.allocated_hours = 320.0
        task.user_ids = other_user
        self._task(project, 160.0)
        project.invalidate_recordset()
        self.assertAlmostEqual(project.employer_planned_cost, 10000.0)
        self._line(project, self.dora, self.today)
        project.invalidate_recordset()
        self.assertGreater(project.employer_real_cost, 0.0)
        self.assertAlmostEqual(
            project.employer_cost_deviation,
            10000.0 - project.employer_real_cost,
        )

    def test_deleted_task_still_counts(self):
        project = self._project()
        task = self._task(project, 160.0)
        self._lock(project)
        task.unlink()
        project.invalidate_recordset()
        self.assertAlmostEqual(project.employer_planned_cost, 10000.0)
        baseline = self.Baseline.search([("project_id", "=", project.id)])
        self.assertFalse(baseline.task_id)
        self.assertEqual(baseline.task_name, "Tarefa")

    def test_baseline_spread_by_month(self):
        """Tarefa de 01/11 a 31/12/2026: 21 dias úteis em nov, 23 em dez (44)."""
        project = self._project()
        project.date_start = date(2026, 11, 1)
        self._task(
            project,
            160.0,
            planned_date_start="2026-11-01 08:00:00",
            date_deadline="2026-12-31 18:00:00",
        )
        self._lock(project)
        report = self.env["planservice.employer.cost.project.report"]
        november = report.search(
            [
                ("project_id", "=", project.id),
                ("date", ">=", "2026-11-01"),
                ("date", "<=", "2026-11-30"),
            ]
        )
        december = report.search(
            [
                ("project_id", "=", project.id),
                ("date", ">=", "2026-12-01"),
                ("date", "<=", "2026-12-31"),
            ]
        )
        self.assertAlmostEqual(sum(november.mapped("planned_cost")), 10000.0 * 21 / 44)
        self.assertAlmostEqual(sum(december.mapped("planned_cost")), 10000.0 * 23 / 44)

    def test_baseline_keeps_task_period(self):
        """O período da tarefa fica na linha de base: mudar o prazo depois de
        travar não muda a distribuição por dia."""
        project = self._project()
        project.date_start = date(2026, 11, 16)
        task = self._task(
            project,
            160.0,
            planned_date_start="2026-11-16 08:00:00",
            date_deadline="2026-11-20 18:00:00",
        )
        self._lock(project)
        baseline = self.Baseline.search([("project_id", "=", project.id)])
        self.assertEqual(baseline.date_start, date(2026, 11, 16))
        self.assertEqual(baseline.date_end, date(2026, 11, 20))
        task.date_deadline = "2026-12-31 18:00:00"
        self.env.flush_all()
        rows = self.env["planservice.employer.cost.project.report"].search(
            [("project_id", "=", project.id), ("planned_cost", "!=", 0)]
        )
        # seg 16 a sex 20/11: 5 dias úteis de 2000
        self.assertEqual(
            sorted(rows.mapped("date")), [date(2026, 11, d) for d in range(16, 21)]
        )
        for row in rows:
            self.assertAlmostEqual(row.planned_cost, 2000.0)

    def test_live_planned_while_pending(self):
        project = self._project()
        task = self._task(project, 160.0)
        self.assertAlmostEqual(project.employer_planned_cost, 10000.0)
        task.allocated_hours = 80.0
        self.assertAlmostEqual(project.employer_planned_cost, 5000.0)

    def test_change_not_yet_valid_keeps_live_planned(self):
        project = self._project()
        self._task(project, 160.0)
        self.dora.employer_salary_benefits_cost = 18000.0
        project.invalidate_recordset()
        self.assertAlmostEqual(project.employer_planned_cost, 10000.0)

    def test_tasks_without_cost_only_while_pending(self):
        project = self._project()
        self._task(project, 160.0, users=self.env["res.users"])
        self.assertEqual(project.employer_tasks_without_cost, 1)
        self._lock(project)
        project.invalidate_recordset()
        self.assertEqual(project.employer_tasks_without_cost, 0)

    def test_baseline_is_read_only(self):
        project = self._project()
        self._task(project, 160.0)
        self._lock(project)
        baseline = self.Baseline.search([("project_id", "=", project.id)])
        with self.assertRaises(UserError):
            baseline.write({"planned_cost": 1.0})
        with self.assertRaises(UserError):
            baseline.unlink()
        manager = self.env["res.users"].create(
            {
                "name": "Gestor",
                "login": "gestor.baseline@test.com",
                "groups_id": [
                    (4, self.env.ref("hr_timesheet.group_timesheet_manager").id)
                ],
            }
        )
        self.assertEqual(
            self.Baseline.with_user(manager).search_count(
                [("project_id", "=", project.id)]
            ),
            len(baseline),
        )
        with self.assertRaises(AccessError):
            self.Baseline.with_user(manager).create({"project_id": project.id})

    def test_baseline_internal_write_key(self):
        """Só a chave interna (gravação pelo projeto/migração) libera escrita."""
        project = self._project()
        self._task(project, 160.0)
        self._lock(project)
        internal = self.Baseline.with_context(planservice_employer_baseline_write=True)
        internal._insert_from_live(self.env["project.project"], self.today)
        baseline = internal.search([("project_id", "=", project.id)])
        baseline.write({"planned_cost": 1.0})
        self.assertAlmostEqual(sum(baseline.mapped("planned_cost")), len(baseline))
        baseline.unlink()
        self.assertFalse(self.Baseline.search([("project_id", "=", project.id)]))

    def test_baseline_hidden_without_permission(self):
        user = self.env["res.users"].create(
            {
                "name": "Sem permissão",
                "login": "noperm.baseline@test.com",
                "groups_id": [
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("project.group_project_user").id),
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.Baseline.with_user(user).search_count([])
        with self.assertRaises(AccessError):
            self.env["planservice.employer.planned.live"].with_user(user).search_count(
                []
            )

    # Migração 18.0.1.1.0

    def test_migration_creates_versions_and_baselines(self):
        migration = _load_migration()
        locked = self._project("Travada antiga")
        pending = self._project("Pendente antiga")
        self._task(locked, 160.0)
        self._task(pending, 160.0)
        self.env.flush_all()
        # estado da 18.0.1.0.0: sem versões e projeto travado sem linha de base
        self.env.cr.execute(
            "DELETE FROM planservice_employer_cost_version WHERE employee_id = %s",
            (self.dora.id,),
        )
        self.env.cr.execute(
            "UPDATE project_project SET project_status = %s WHERE id = %s",
            (self.status_complete.id, locked.id),
        )
        self.env.invalidate_all()
        migration.migrate(self.env.cr, None)
        self.assertFalse(self._versions(self.dora), "fresh install: no-op")
        for _run in range(2):
            migration.migrate(self.env.cr, "18.0.1.0.0")
            self.env.invalidate_all()
            version = self._versions(self.dora)
            self.assertEqual(len(version), 1)
            self.assertFalse(version.date_from)
            self.assertAlmostEqual(version.total_cost, 10000.0)
            baseline = self.Baseline.search([("project_id", "=", locked.id)])
            self.assertAlmostEqual(sum(baseline.mapped("planned_cost")), 10000.0)
            self.assertTrue(locked.employer_baseline_date)
            self.assertFalse(pending.employer_baseline_date)
            self.assertFalse(self.Baseline.search([("project_id", "=", pending.id)]))

    # Migração 18.0.1.2.0

    def test_migration_fills_baseline_period_with_whole_month(self):
        """Linha de base da 18.0.1.1.0 (sem período) fica com o mês inteiro e
        mantém o valor e a distribuição de antes."""
        migration = _load_migration("18.0.1.2.0")
        project = self._project()
        project.date_start = date(2026, 11, 16)
        self._task(
            project,
            160.0,
            planned_date_start="2026-11-16 08:00:00",
            date_deadline="2026-11-20 18:00:00",
        )
        self._lock(project)
        self.env.flush_all()
        # estado da 18.0.1.1.0: linha de base sem período
        self.env.cr.execute(
            "UPDATE planservice_employer_planned_cost "
            "SET date_start = NULL, date_end = NULL WHERE project_id = %s",
            (project.id,),
        )
        self.env.invalidate_all()
        migration.migrate(self.env.cr, None)
        baseline = self.Baseline.search([("project_id", "=", project.id)])
        self.assertFalse(baseline.date_start, "fresh install: no-op")
        for _run in range(2):
            migration.migrate(self.env.cr, "18.0.1.1.0")
            self.env.invalidate_all()
            self.assertEqual(baseline.date_start, date(2026, 11, 1))
            self.assertEqual(baseline.date_end, date(2026, 11, 30))
            rows = self.env["planservice.employer.cost.project.report"].search(
                [("project_id", "=", project.id), ("planned_cost", "!=", 0)]
            )
            # como antes: o mês inteiro, 21 dias úteis em novembro/2026
            self.assertEqual(len(rows), 21)
            self.assertAlmostEqual(sum(rows.mapped("planned_cost")), 10000.0)
