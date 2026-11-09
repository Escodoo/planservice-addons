Módulo **temporário**, a ser removido quando o módulo financeiro for
implantado. Desenho pensado para a saída:

- Depende só de `hr_timesheet`, `hr_hourly_cost` e `project`. O único módulo que
  depende dele é `planservice_employers_calc_dashboard`, que deve ser
  desinstalado **antes**.
- Não altera `account.analytic.line` nem grava custos nas linhas de timesheet.
- Os dados persistidos são as colunas em `hr_employee`
  (`employer_salary_benefits_cost` e `employer_provisions_cost`) e o parâmetro
  `employer_plan_monthly_hours` em `res_company`. Migrar esses valores para o
  financeiro **antes** de desinstalar (a desinstalação remove as colunas).
- Os relatórios são views SQL (`planservice_employer_cost_report` e
  `planservice_employer_cost_project_report`), removidas junto com o módulo.

Limitações conhecidas:

- **Horas mensais do plano**: o parâmetro da empresa (padrão 160) deve acompanhar
  `hour_plan_monthly_hours`, de `project_task_hour_plan`. Se um mudar, o outro
  precisa mudar, senão o custo previsto diverge do plano.
- **Dias úteis**: segunda a sexta, menos os feriados globais do calendário do
  colaborador. Calendários com outra semana de trabalho não são tratados.
- **Moeda**: as views usam a moeda da empresa, sem conversão.
- **Previsto por mês**: o previsto da tarefa é dividido pelos dias de cada mês,
  entre o início e o prazo, e não pelos percentuais mensais do plano. O início
  usa `planned_date_start` (do `project_timeline`) só se o campo existir quando o
  módulo é atualizado.
- **Painel de rentabilidade**: pode mostrar o salário em duplicidade para quem
  tem `hourly_cost` preenchido, porque o custo nativo de timesheet não é alterado.

Passos para a saída: desinstalar o módulo do dashboard, migrar os valores,
desinstalar este módulo, remover da `addons.yaml` e apagar o diretório do
repositório `planservice-addons`.
