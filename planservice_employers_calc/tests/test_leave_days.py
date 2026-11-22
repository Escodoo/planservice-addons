# Copyright 2026 Escodoo
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

from datetime import date, datetime

from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class TestLeaveDays(TransactionCase):
    """Afastamento por calendário: só o calendário afetado perde o dia útil.

    Semana de 16 a 20/11/2026 (segunda a sexta). O afastamento do calendário A
    cobre quarta, 18/11. O calendário B não tem afastamento.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.cal_a = cls.env["resource.calendar"].create(
            {"name": "Calendário A", "hours_per_day": 8.0}
        )
        cls.cal_b = cls.env["resource.calendar"].create(
            {"name": "Calendário B", "hours_per_day": 8.0}
        )
        cls.env["resource.calendar.leaves"].create(
            {
                "name": "Afastamento só do calendário A",
                "calendar_id": cls.cal_a.id,
                "date_from": datetime(2026, 11, 18, 3, 0, 0),
                "date_to": datetime(2026, 11, 19, 2, 59, 59),
            }
        )

    def _employee(self, name, calendar):
        return self.env["hr.employee"].create(
            {
                "name": name,
                "resource_calendar_id": calendar.id,
                "employer_salary_benefits_cost": 8000.0,
                "employer_provisions_cost": 2000.0,
            }
        )

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

    def _dated_task(self, project, user, start, end):
        project.date_start = start
        task = self.env["project.task"].create(
            {
                "name": "Tarefa",
                "project_id": project.id,
                "allocated_hours": 160.0,
                "user_ids": [(6, 0, [user.id])],
            }
        )
        task.date_deadline = datetime.combine(end, datetime.min.time()).replace(hour=12)
        # project_timeline preenche o início planejado com a data de criação;
        # só grava o campo quando ele existe (como em test_employer_cost)
        planned_start = {
            "planned_date_start": datetime.combine(start, datetime.min.time()).replace(
                hour=12
            )
        }
        task.write({k: v for k, v in planned_start.items() if k in task._fields})
        self.env.flush_all()
        return task

    def _planned_by_day(self, project, employee):
        rows = self.env["planservice.employer.cost.project.report"].search(
            [("project_id", "=", project.id), ("employee_id", "=", employee.id)]
        )
        result = {}
        for row in rows:
            result[row.date] = result.get(row.date, 0.0) + row.planned_cost
        return result

    def test_afastamento_so_no_calendario_afetado(self):
        """O dia de afastamento do calendário A não tem previsto; o B tem."""
        ana = self._employee("Ana", self.cal_a)
        bia = self._employee("Bia", self.cal_b)
        user_ana = self._link_user(ana, "ana.leave@test.com")
        user_bia = self._link_user(bia, "bia.leave@test.com")
        project_ana = self.env["project.project"].create({"name": "Obra Ana"})
        project_bia = self.env["project.project"].create({"name": "Obra Bia"})
        self._dated_task(project_ana, user_ana, date(2026, 11, 16), date(2026, 11, 20))
        self._dated_task(project_bia, user_bia, date(2026, 11, 16), date(2026, 11, 20))

        ana_by_day = self._planned_by_day(project_ana, ana)
        bia_by_day = self._planned_by_day(project_bia, bia)

        self.assertEqual(ana_by_day.get(date(2026, 11, 18), 0.0), 0.0)
        self.assertGreater(ana_by_day.get(date(2026, 11, 17), 0.0), 0.0)
        self.assertGreater(bia_by_day.get(date(2026, 11, 18), 0.0), 0.0)

    def test_previsto_so_nos_dias_uteis_de_cada_calendario(self):
        """Com 4 dias úteis para Ana (sem quarta), cada dia recebe 1/4 do custo."""
        ana = self._employee("Ana Dias", self.cal_a)
        user_ana = self._link_user(ana, "ana.dias@test.com")
        project = self.env["project.project"].create({"name": "Obra dias"})
        self._dated_task(project, user_ana, date(2026, 11, 16), date(2026, 11, 20))

        by_day = self._planned_by_day(project, ana)
        uteis = [
            date(2026, 11, 16),
            date(2026, 11, 17),
            date(2026, 11, 19),
            date(2026, 11, 20),
        ]
        monthly_cost = 10000.0
        for day in uteis:
            self.assertAlmostEqual(by_day[day], monthly_cost / 4, places=2)
        # a soma do previsto da tarefa é o custo mensal inteiro (160 h de 160 h)
        self.assertAlmostEqual(sum(by_day.values()), monthly_cost, places=2)
        self.assertEqual(
            sorted(d for d, v in by_day.items() if v > 0),
            uteis,
        )

    def _uteis_do_mes(self, afastamentos=()):
        """Dias de segunda a sexta de novembro/2026, menos os afastamentos dados."""
        return sum(
            1
            for dia in range(1, 31)
            if date(2026, 11, dia).weekday() < 5
            and date(2026, 11, dia) not in afastamentos
        )

    def test_previsto_e_real_usam_o_mesmo_dia_util(self):
        """Um dia de 8 h de real vale o mesmo que o previsto desse dia.

        Mesmo mês e mesmo calendário dos dois lados: o real divide o custo
        mensal pelos dias úteis do mês, e o previsto de uma tarefa de 160 h
        cai igualmente nesses dias.
        """
        cases = (
            (self.cal_a, "ana.util@test.com", date(2026, 11, 17), {date(2026, 11, 18)}),
            (self.cal_b, "bia.util@test.com", date(2026, 11, 18), set()),
        )
        for calendar, login, dia, afastamentos in cases:
            employee = self._employee("Util " + login.split("@")[0], calendar)
            user = self._link_user(employee, login)
            project = self.env["project.project"].create({"name": "Obra " + login})
            self._dated_task(project, user, date(2026, 11, 1), date(2026, 11, 30))
            self.env["account.analytic.line"].create(
                {
                    "name": "Horas",
                    "project_id": project.id,
                    "employee_id": employee.id,
                    "unit_amount": 8.0,
                    "date": dia,
                }
            )
            self.env.flush_all()
            previsto_do_dia = self._planned_by_day(project, employee)[dia]
            real_do_dia = sum(
                self.env["planservice.employer.cost.project.report"]
                .search(
                    [
                        ("project_id", "=", project.id),
                        ("employee_id", "=", employee.id),
                        ("date", "=", dia),
                    ]
                )
                .mapped("real_cost")
            )
            dias_uteis = self._uteis_do_mes(afastamentos)
            self.assertAlmostEqual(previsto_do_dia, 10000.0 / dias_uteis, places=2)
            self.assertAlmostEqual(real_do_dia, 10000.0 / dias_uteis, places=2)
