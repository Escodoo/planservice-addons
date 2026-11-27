Módulo **temporário**, a ser removido quando o módulo financeiro for
implantado. Desenho pensado para a saída:

- Depende de `hr_timesheet`, `hr_hourly_cost`, `project` e
  `planservice_project_plan_matrix` (status que trava o planejamento). O único módulo que
  depende dele é `planservice_employers_calc_dashboard`, que deve ser
  desinstalado **antes**.
- Não altera `account.analytic.line` nem grava custos nas linhas de timesheet.
- Os dados persistidos são a coluna `employer_salary_benefits_cost` em
  `hr_employee`, o histórico de
  versões de custo (`planservice_employer_cost_version`), a linha de base do
  previsto (`planservice_employer_planned_cost` e `employer_baseline_date` em
  `project_project`) e o parâmetro `employer_plan_monthly_hours` em
  `res_company`. Migrar esses valores para o financeiro **antes** de desinstalar
  (a desinstalação remove tabelas e colunas).
- Os relatórios são views SQL (`planservice_employer_cost_report` e
  `planservice_employer_cost_project_report`), removidas junto com o módulo.

Limitações conhecidas:

- **Vigência**: uma alteração vale a partir do dia seguinte; não há retroativo
  (dissídio) nem correção de versões antigas pela interface.
- **Fuso**: a versão usa o fuso do usuário (padrão America/Sao_Paulo); o
  previsto ao vivo, calculado em SQL, usa sempre America/Sao_Paulo para "hoje".
- **Linha de base**: é gravada quando o projeto deixa um status com "Permitir
  replanejar". Se a configuração dos status mudar depois, projetos já travados
  sem linha de base continuam com o previsto calculado na hora.

- **Horas mensais do plano**: o parâmetro da empresa (padrão 160) deve acompanhar
  `hour_plan_monthly_hours`, de `project_task_hour_plan`. Se um mudar, o outro
  precisa mudar, senão o custo previsto diverge do plano.
- **Dias úteis**: segunda a sexta, menos os feriados globais do calendário do
  colaborador. Vale para o previsto (distribuído por dia) e para o real.
  Calendários com outra semana de trabalho não são tratados.
- **Moeda**: as views e o custo previsto do projeto usam a moeda da empresa,
  sem conversão pela moeda do colaborador.
- **Previsto por dia útil**: o previsto da tarefa é dividido pelos dias úteis
  entre o início e o prazo, e não pelos percentuais mensais do plano. Cada mês
  fica com a parte dos dias úteis dele, e no relatório o valor aparece só nos
  dias úteis do período da tarefa (os demais dias do período ficam com zero).
  Tarefa sem nenhum dia útil (só fim de semana ou feriado) é dividida pelos
  dias corridos. O início usa `planned_date_start` (do `project_timeline`) só
  se o campo existir quando o módulo é atualizado.
- **Linha de base gravada antes da 18.0.1.2.0**: não tinha o período da tarefa;
  a migração preenche o mês inteiro, então essas obras continuam com o previsto
  espalhado pelos dias úteis do mês todo, como antes.
- **Painel de rentabilidade**: pode mostrar o salário em duplicidade para quem
  tem `hourly_cost` preenchido, porque o custo nativo de timesheet não é alterado.

Passos para a saída: desinstalar o módulo do dashboard, migrar os valores,
desinstalar este módulo, remover da `addons.yaml` e apagar o diretório do
repositório `planservice-addons`.
