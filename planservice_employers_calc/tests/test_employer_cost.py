# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, datetime, timedelta
from unittest.mock import patch

from psycopg2 import IntegrityError

from odoo import fields
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged
from odoo.tools import mute_logger


def _business_days(year, month, holidays=()):
    """Dias úteis (segunda a sexta) do mês, sem os feriados informados."""
    day = date(year, month, 1)
    days = []
    while day.month == month:
        if day.weekday() < 5 and day not in holidays:
            days.append(day)
        day += timedelta(days=1)
    return days


@tagged("post_install", "-at_install")
class TestEmployerCost(TransactionCase):
    """Custo mensal rateado pela fração do mês trabalhada.

    Novembro/2026 tem 21 dias de segunda a sexta; com o feriado global de
    20/11 sobram 20 dias úteis. Dezembro/2026 tem 23 dias úteis.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.calendar = cls.env["resource.calendar"].create(
            {"name": "Teste 8h", "hours_per_day": 8.0}
        )
        cls.env["resource.calendar.leaves"].create(
            {
                "name": "Feriado teste",
                "calendar_id": cls.calendar.id,
                "date_from": datetime(2026, 11, 20, 3, 0, 0),
                "date_to": datetime(2026, 11, 21, 2, 59, 59),
            }
        )
        cls.holiday = date(2026, 11, 20)

        def _employee(name, salary_benefits, provisions):
            return cls.env["hr.employee"].create(
                {
                    "name": name,
                    "resource_calendar_id": cls.calendar.id,
                    "employer_salary_benefits_cost": salary_benefits,
                    "employer_provisions_cost": provisions,
                }
            )

        # custo mensal: Ana 10000, Carlos 6000, Bia 5000 (sem lançamentos)
        cls.ana = _employee("Ana", 8000.0, 2000.0)
        cls.carlos = _employee("Carlos", 6000.0, 0.0)
        cls.bia = _employee("Bia", 4000.0, 1000.0)
        cls.project_a = cls.env["project.project"].create(
            {"name": "Edifício Aurora", "privacy_visibility": "employees"}
        )
        cls.project_b = cls.env["project.project"].create(
            {"name": "Galpão Norte", "privacy_visibility": "employees"}
        )

        def _line(project, employee, day, hours):
            return cls.env["account.analytic.line"].create(
                {
                    "name": "Horas",
                    "project_id": project.id,
                    "employee_id": employee.id,
                    "unit_amount": hours,
                    "date": day,
                }
            )

        cls._line = staticmethod(_line)
        # Novembro/2026 (20 dias úteis, 8 h por dia)
        _line(cls.project_a, cls.ana, date(2026, 11, 2), 4.0)  # 50%  -> 250
        _line(cls.project_a, cls.ana, date(2026, 11, 3), 8.0)  # 100% -> 500
        _line(cls.project_a, cls.carlos, date(2026, 11, 2), 8.0)  # 100% -> 300
        _line(cls.project_b, cls.ana, date(2026, 11, 4), 2.0)  # 25%  -> 125
        _line(cls.project_b, cls.carlos, date(2026, 11, 4), 4.0)  # 50%  -> 150

    def _report(self, project):
        return self.env["planservice.employer.cost.report"].search(
            [("project_id", "=", project.id)]
        )

    def test_monthly_total_cost(self):
        self.assertAlmostEqual(self.ana.employer_monthly_total_cost, 10000.0)
        self.assertAlmostEqual(self.carlos.employer_monthly_total_cost, 6000.0)
        self.assertAlmostEqual(self.bia.employer_monthly_total_cost, 5000.0)

    def test_monthly_total_cost_defaults_to_zero(self):
        employee = self.env["hr.employee"].create({"name": "Sem valores"})
        self.assertAlmostEqual(employee.employer_monthly_total_cost, 0.0)

    def test_line_cost_split(self):
        """50% de um dia, mês de 20 dias úteis, custo mensal 10000 -> 250."""
        line = self._report(self.project_a).filtered(
            lambda r: r.employee_id == self.ana and r.date == date(2026, 11, 2)
        )
        self.assertEqual(len(line), 1)
        self.assertAlmostEqual(line.day_percentage, 50.0)
        self.assertAlmostEqual(line.salary_benefits_cost, 200.0)
        self.assertAlmostEqual(line.provisions_cost, 50.0)
        self.assertAlmostEqual(line.total_cost, 250.0)

    def test_report_totals_per_project(self):
        report_a = self._report(self.project_a)
        report_b = self._report(self.project_b)
        self.assertEqual(len(report_a), 3)
        self.assertEqual(len(report_b), 2)
        self.assertAlmostEqual(sum(report_a.mapped("total_cost")), 1050.0)
        self.assertAlmostEqual(sum(report_a.mapped("salary_benefits_cost")), 900.0)
        self.assertAlmostEqual(sum(report_a.mapped("provisions_cost")), 150.0)
        self.assertAlmostEqual(sum(report_b.mapped("total_cost")), 275.0)
        self.assertAlmostEqual(sum(report_b.mapped("salary_benefits_cost")), 250.0)
        self.assertAlmostEqual(sum(report_b.mapped("provisions_cost")), 25.0)

    def test_employee_without_hours_not_in_report(self):
        report = self.env["planservice.employer.cost.report"].search(
            [("employee_id", "=", self.bia.id)]
        )
        self.assertFalse(report)

    def test_full_month_closes_monthly_cost(self):
        """100% de todos os dias úteis fecha o custo mensal, com feriado (mar/2026,
        21 dias úteis) e sem feriado (jun/2026, 22 dias úteis).

        Usa meses passados e um colaborador sem outros lançamentos: módulos do
        repositório bloqueiam datas futuras e dias acima de 100%.
        """
        calendar = self.env["resource.calendar"].create(
            {"name": "Teste feriado março", "hours_per_day": 8.0}
        )
        holiday = date(2026, 3, 18)
        self.env["resource.calendar.leaves"].create(
            {
                "name": "Feriado",
                "calendar_id": calendar.id,
                "date_from": datetime(2026, 3, 18, 3, 0, 0),
                "date_to": datetime(2026, 3, 18, 2, 59, 59) + timedelta(days=1),
            }
        )
        davi = self.env["hr.employee"].create(
            {
                "name": "Davi",
                "resource_calendar_id": calendar.id,
                "employer_salary_benefits_cost": 8000.0,
                "employer_provisions_cost": 2000.0,
            }
        )
        project = self.env["project.project"].create({"name": "Mês fechado"})
        march = _business_days(2026, 3, holidays=(holiday,))
        june = _business_days(2026, 6)
        self.assertEqual(len(march), 21)
        self.assertEqual(len(june), 22)
        for day in march + june:
            self._line(project, davi, day, 8.0)
        report = self._report(project)
        for month in (3, 6):
            month_lines = report.filtered(lambda r, m=month: r.date.month == m)
            self.assertAlmostEqual(sum(month_lines.mapped("total_cost")), 10000.0)

    def test_project_profitability(self):
        self.env.user.groups_id |= self.env.ref("hr_timesheet.group_timesheet_manager")
        for project, expected in ((self.project_a, 1050.0), (self.project_b, 275.0)):
            items = project._get_profitability_items(with_action=False)
            row = next(
                r for r in items["costs"]["data"] if r["id"] == "employer_extra_costs"
            )
            self.assertAlmostEqual(row["billed"], -expected)

    # ------------------------------------------------------------------
    # Custo previsto, real e desvio no projeto
    # ------------------------------------------------------------------
    def _link_user(self, employee, login):
        user = self.env["res.users"].create(
            {
                "name": employee.name,
                "login": login,
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )
        employee.user_id = user
        return user

    def _task(self, project, hours, users=()):
        return self.env["project.task"].create(
            {
                "name": "Tarefa",
                "project_id": project.id,
                "allocated_hours": hours,
                "user_ids": [(6, 0, [u.id for u in users])],
            }
        )

    def test_plan_monthly_hours_default_and_constraint(self):
        self.assertAlmostEqual(self.env.company.employer_plan_monthly_hours, 160.0)
        with self.assertRaises(IntegrityError), mute_logger("odoo.sql_db"):
            with self.env.cr.savepoint():
                self.env.company.employer_plan_monthly_hours = 0.0
                self.env.flush_all()

    def test_planned_cost_full_month(self):
        """160 h / 160 x 10000 = 10000; 80 h = 5000; 480 h = 30000."""
        user = self._link_user(self.ana, "ana.plan@test.com")
        for hours, expected in ((160.0, 10000.0), (80.0, 5000.0), (480.0, 30000.0)):
            project = self.env["project.project"].create({"name": f"P{hours}"})
            self._task(project, hours, user)
            self.assertAlmostEqual(project.employer_planned_cost, expected)
            self.assertEqual(project.employer_tasks_without_cost, 0)

    def test_planned_cost_two_assignees_split_equally(self):
        ana = self._link_user(self.ana, "ana.split@test.com")
        carlos = self._link_user(self.carlos, "carlos.split@test.com")
        project = self.env["project.project"].create({"name": "Dois responsáveis"})
        self._task(project, 160.0, ana | carlos)
        # 80/160 x 10000 + 80/160 x 6000 = 8000
        self.assertAlmostEqual(project.employer_planned_cost, 8000.0)

    def test_planned_cost_task_without_cost_is_flagged(self):
        user_no_employee = self.env["res.users"].create(
            {
                "name": "Sem colaborador",
                "login": "noemp.plan@test.com",
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )
        project = self.env["project.project"].create({"name": "Sem custo"})
        self._task(project, 160.0)  # sem responsável
        self._task(project, 160.0, user_no_employee)  # sem colaborador
        self.assertAlmostEqual(project.employer_planned_cost, 0.0)
        self.assertEqual(project.employer_tasks_without_cost, 2)

    def test_planned_cost_project_without_tasks(self):
        project = self.env["project.project"].create({"name": "Vazio"})
        self.assertAlmostEqual(project.employer_planned_cost, 0.0)
        self.assertAlmostEqual(project.employer_real_cost, 0.0)
        self.assertAlmostEqual(project.employer_cost_deviation, 0.0)

    def test_real_cost_and_deviation(self):
        ana = self._link_user(self.ana, "ana.dev@test.com")
        # project_a tem custo real 1050 (história do setUpClass)
        self._task(self.project_a, 160.0, ana)  # previsto 10000
        self.assertAlmostEqual(self.project_a.employer_real_cost, 1050.0)
        self.assertAlmostEqual(self.project_a.employer_planned_cost, 10000.0)
        self.assertAlmostEqual(self.project_a.employer_cost_deviation, 8950.0)

    def test_deviation_is_negative_when_overspent(self):
        """Gasto: previsto - real. Gastou mais que o previsto fica negativo."""
        ana = self._link_user(self.ana, "ana.over@test.com")
        self._task(self.project_a, 8.0, ana)  # previsto 8/160 x 10000 = 500
        self.assertAlmostEqual(self.project_a.employer_planned_cost, 500.0)
        self.assertAlmostEqual(self.project_a.employer_real_cost, 1050.0)
        self.assertAlmostEqual(self.project_a.employer_cost_deviation, -550.0)

    def test_cost_fields_manager_only(self):
        plain = self.env["res.users"].create(
            {
                "name": "Usuario simples",
                "login": "plain.cost@test.com",
                "groups_id": [
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("project.group_project_user").id),
                ],
            }
        )
        # campos calculados só passam pela checagem de grupo na leitura (read)
        with self.assertRaises(AccessError):
            self.project_a.with_user(plain).read(["employer_planned_cost"])
        manager = self.env["res.users"].create(
            {
                "name": "Gerente",
                "login": "manager.cost@test.com",
                "groups_id": [
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("hr_timesheet.group_timesheet_manager").id),
                ],
            }
        )
        values = self.project_a.with_user(manager).read(["employer_real_cost"])
        self.assertAlmostEqual(values[0]["employer_real_cost"], 1050.0)

    def test_month_closes_with_18_20_and_23_business_days(self):
        """O mesmo colaborador fecha o custo mensal (8000) em meses com 18, 20 e 23
        dias úteis. Ninguém lança em feriado nem em fim de semana."""
        calendar = self.env["resource.calendar"].create(
            {"name": "Teste feriados", "hours_per_day": 8.0}
        )
        holidays = {
            # setembro/2026: 2 feriados -> 20 dias úteis
            date(2026, 9, 7),
            date(2026, 9, 24),
            # outubro/2026: 4 feriados -> 18 dias úteis
            date(2026, 10, 2),
            date(2026, 10, 12),
            date(2026, 10, 15),
            date(2026, 10, 28),
        }
        for day in holidays:
            self.env["resource.calendar.leaves"].create(
                {
                    "name": "Feriado",
                    "calendar_id": calendar.id,
                    "date_from": datetime(day.year, day.month, day.day, 3, 0, 0),
                    "date_to": datetime(day.year, day.month, day.day, 2, 59, 59)
                    + timedelta(days=1),
                }
            )
        gustavo = self.env["hr.employee"].create(
            {
                "name": "Gustavo",
                "resource_calendar_id": calendar.id,
                "employer_salary_benefits_cost": 6000.0,
                "employer_provisions_cost": 2000.0,
            }
        )
        project = self.env["project.project"].create({"name": "Meses diferentes"})
        expected_days = {7: 23, 9: 20, 10: 18}
        for month, n_days in expected_days.items():
            days = _business_days(2026, month, holidays=holidays)
            self.assertEqual(len(days), n_days)
            for day in days:
                self._line(project, gustavo, day, 8.0)
        report = self._report(project)
        for month, n_days in expected_days.items():
            lines = report.filtered(lambda r, m=month: r.date.month == m)
            self.assertEqual(len(lines), n_days)
            self.assertAlmostEqual(sum(lines.mapped("total_cost")), 8000.0)

    def test_project_report_matches_project_fields(self):
        """A view única do dashboard bate com os campos do projeto."""
        ana = self._link_user(self.ana, "ana.dash@test.com")
        carlos = self._link_user(self.carlos, "carlos.dash@test.com")
        self._task(self.project_a, 160.0, ana)  # previsto 10000
        self._task(self.project_b, 80.0, ana | carlos)  # 40/160x10000 + 40/160x6000
        self.env.flush_all()  # a view SQL lê direto do banco
        rows = self.env["planservice.employer.cost.project.report"].search([])
        for project, planned, real in (
            (self.project_a, 10000.0, 1050.0),
            (self.project_b, 4000.0, 275.0),
        ):
            project_rows = rows.filtered(lambda r, p=project: r.project_id == p)
            self.assertAlmostEqual(sum(project_rows.mapped("planned_cost")), planned)
            self.assertAlmostEqual(sum(project_rows.mapped("real_cost")), real)
            self.assertAlmostEqual(
                sum(project_rows.mapped("cost_deviation")), planned - real
            )
            self.assertAlmostEqual(
                sum(project_rows.mapped("planned_cost")), project.employer_planned_cost
            )
            self.assertAlmostEqual(
                sum(project_rows.mapped("real_cost")), project.employer_real_cost
            )

    def test_project_report_per_employee_planned_vs_real(self):
        """Previsto e real também ficam por colaborador (previsto sem data)."""
        ana = self._link_user(self.ana, "ana.emp@test.com")
        self._task(self.project_a, 160.0, ana)
        self.env.flush_all()
        rows = self.env["planservice.employer.cost.project.report"].search(
            [("project_id", "=", self.project_a.id), ("employee_id", "=", self.ana.id)]
        )
        self.assertAlmostEqual(sum(rows.mapped("planned_cost")), 10000.0)
        self.assertAlmostEqual(sum(rows.mapped("real_cost")), 750.0)  # 250 + 500
        self.assertAlmostEqual(sum(rows.mapped("unit_amount")), 12.0)  # 4 h + 8 h
        planned_rows = rows.filtered(lambda r: r.planned_cost)
        # o previsto é datado no dia 1 do mês (aqui, mês de criação da tarefa)
        self.assertTrue(planned_rows.date)
        self.assertTrue(all(row.date.day == 1 for row in planned_rows))

    def test_project_report_spreads_planned_cost_by_month(self):
        """O previsto da tarefa é distribuído pelos meses, proporcional aos dias."""
        ana = self._link_user(self.ana, "ana.spread@test.com")
        project = self.env["project.project"].create(
            {
                "name": "Distribuição mensal",
                "date_start": date(2026, 1, 1),
                "date": date(2026, 3, 31),
            }
        )
        task = self._task(project, 160.0, ana)  # previsto 10000
        task.date_deadline = datetime(2026, 3, 31, 12, 0, 0)
        # outros módulos (project_timeline) preenchem o início planejado com a
        # data de criação; só grava o campo quando ele existe
        planned_start = {"planned_date_start": datetime(2026, 1, 1, 12, 0, 0)}
        task.write({k: v for k, v in planned_start.items() if k in task._fields})
        self.env.flush_all()
        rows = self.env["planservice.employer.cost.project.report"].search(
            [("project_id", "=", project.id)], order="date"
        )
        self.assertEqual(
            rows.mapped("date"), [date(2026, 1, 1), date(2026, 2, 1), date(2026, 3, 1)]
        )
        # 90 dias: janeiro 31, fevereiro 28, março 31
        expected = [10000 * 31 / 90, 10000 * 28 / 90, 10000 * 31 / 90]
        for row, value in zip(rows, expected, strict=False):
            self.assertAlmostEqual(row.planned_cost, value, places=2)
        self.assertAlmostEqual(sum(rows.mapped("planned_cost")), 10000.0)
        self.assertAlmostEqual(project.employer_planned_cost, 10000.0)

    def test_project_report_manager_only(self):
        user = self.env["res.users"].create(
            {
                "name": "Sem acesso",
                "login": "noaccess.dash@test.com",
                "groups_id": [(4, self.env.ref("base.group_user").id)],
            }
        )
        with self.assertRaises(AccessError):
            self.env["planservice.employer.cost.project.report"].with_user(
                user
            ).search_count([])

    def test_profitability_labels_and_sequence(self):
        """O painel recebe o rótulo e a posição da seção de custo de pessoal."""
        self.assertIn(
            "employer_extra_costs", self.project_a._get_profitability_labels()
        )
        self.assertIn(
            "employer_extra_costs",
            self.project_a._get_profitability_sequence_per_invoice_type(),
        )

    def test_profitability_without_hours_adds_no_row(self):
        """Projeto sem horas lançadas não ganha linha de custo de pessoal."""
        self.env.user.groups_id |= self.env.ref("hr_timesheet.group_timesheet_manager")
        project = self.env["project.project"].create({"name": "Sem horas"})
        items = project._get_profitability_items(with_action=False)
        rows = [
            r
            for r in (items.get("costs") or {}).get("data", [])
            if r["id"] == "employer_extra_costs"
        ]
        self.assertFalse(rows)

    def test_planned_cost_converts_employee_currency(self):
        """Projeto em outra moeda recebe o custo do colaborador convertido."""
        currency = self.env.ref("base.EUR")
        currency.active = True
        other = self.env["res.company"].create(
            {"name": "Outra empresa", "currency_id": currency.id}
        )
        self.env["res.currency.rate"].create(
            {
                "currency_id": currency.id,
                "name": "2026-01-01",
                "rate": 0.5,
                "company_id": other.id,
            }
        )
        user = self._link_user(self.ana, "ana.currency@test.com")
        project = self.env["project.project"].create(
            {"name": "Multimoeda", "company_id": other.id}
        )
        self._task(project, 160.0, user)
        converted = self.ana.currency_id._convert(
            10000.0, currency, other, fields.Date.context_today(project)
        )
        self.assertNotEqual(converted, 10000.0)
        self.assertAlmostEqual(project.employer_planned_cost, converted)

    def test_planned_start_expression_with_and_without_project_timeline(self):
        """A data inicial usa planned_date_start só se a coluna existir."""
        model = self.env["planservice.employer.cost.project.report"]
        cursor = type(self.env.cr)
        for found, has_column in (((1,), True), (None, False)):
            with patch.object(cursor, "fetchone", create=True, return_value=found):
                expression = model._planned_start_expression()
            self.assertEqual("planned_date_start" in expression, has_column)

    def test_no_permission_denied_access(self):
        user = self.env["res.users"].create(
            {
                "name": "Sem permissão",
                "login": "noperm.employer@test.com",
                "groups_id": [
                    (4, self.env.ref("base.group_user").id),
                    (4, self.env.ref("project.group_project_user").id),
                ],
            }
        )
        with self.assertRaises(AccessError):
            self.env["planservice.employer.cost.report"].with_user(user).search_count(
                []
            )
        items = self.project_a.with_user(user)._get_profitability_items(
            with_action=False
        )
        rows = [
            r
            for r in (items.get("costs") or {}).get("data", [])
            if r["id"] == "employer_extra_costs"
        ]
        self.assertFalse(rows)
