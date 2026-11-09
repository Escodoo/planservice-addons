**Cadastro (RH e gerente de timesheet)**

- Ficha do colaborador, aba **Definições**: preencha **Salário + benefícios
  (mensal)** e **Provisões (mensal)**. O **Custo mensal total** é a soma dos dois.
- Formulário da empresa: **Horas mensais do plano** (padrão 160), as horas que
  valem 100% de um mês no planejamento.

**Como o custo é calculado**

- Cada lançamento custa `custo mensal × (% do dia) / dias úteis do mês`. Quem
  lança 100% de todos os dias úteis tem o custo mensal inteiro no mês, com 18, 20
  ou 23 dias úteis. Ninguém deve lançar em feriado nem em fim de semana.
- O custo previsto vem das tarefas: horas previstas ÷ horas mensais do plano ×
  custo mensal do responsável (dividido entre os responsáveis). Tarefas sem
  responsável, ou com responsável sem colaborador, ficam fora e são sinalizadas.

**Onde ver**

- Menu Timesheets > Relatórios > **Custo do colaborador por obra** (pivot, lista e
  gráfico).
- Ficha do projeto, abaixo de Tempo previsto: **Custo previsto**, **Custo real**
  e **Desvio de custo** (previsto − real: positivo = gastou menos que o previsto), visíveis ao gerente de
  timesheet.
- Painel de rentabilidade do projeto: linha "Custo de pessoal (salário,
  benefícios, provisões)". O Odoo só exibe a seção Rentabilidade a usuários com o
  grupo **Contabilidade analítica** (`analytic.group_analytic_accounting`). O custo
  nativo de timesheet não é alterado; para colaboradores com custo por hora
  preenchido, o salário pode aparecer em duplicidade.
