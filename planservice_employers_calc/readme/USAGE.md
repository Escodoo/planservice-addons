**Cadastro (RH e gerente de timesheet)**

- Ficha do colaborador, aba **Definições**: preencha **Salário + benefícios
  (mensal)** e **Provisões (mensal)**. O **Custo mensal total** é a soma dos dois.
- Uma alteração vale a partir do **dia seguinte** (fuso do usuário). Várias
  alterações no mesmo dia geram uma única versão, com o último valor. Não há
  vigência retroativa. A aba **Histórico de custo** da ficha mostra as versões,
  somente leitura.
- Formulário da empresa: **Horas mensais do plano** (padrão 160), as horas que
  valem 100% de um mês no planejamento.

**Como o custo é calculado**

- Cada lançamento custa `custo mensal × (% do dia) / dias úteis do mês`. Quem
  lança 100% de todos os dias úteis tem o custo mensal inteiro no mês, com 18, 20
  ou 23 dias úteis. Ninguém deve lançar em feriado nem em fim de semana.
- O custo previsto vem das tarefas: horas previstas ÷ horas mensais do plano ×
  custo mensal do responsável (dividido entre os responsáveis). Tarefas sem
  responsável, ou com responsável sem colaborador, ficam fora e são sinalizadas.
- O previsto de cada tarefa é dividido pelos dias úteis do período dela (do
  início ao prazo). Assim, o previsto até uma data pode ser comparado com o
  real lançado até a mesma data.
- Enquanto o projeto está em "Pendente" (ou sem status), o previsto é calculado
  na hora, com o custo vigente hoje.
- Ao passar para "Em andamento", o previsto é gravado na **linha de base**
  (por tarefa, colaborador e mês), e a data aparece no projeto em **Custo
  previsto travado em**. Daí em diante o previsto não muda: aumento de salário,
  horas a mais, tarefa nova ou troca de responsável aparecem só no realizado e
  no desvio. Não há replanejamento.

**Onde ver**

- Menu Timesheets > Relatórios > **Custo do colaborador por obra** (pivot, lista e
  gráfico).
- Menu Timesheets > Relatórios > **Linha de base do custo previsto** (lista e
  pivot, somente leitura).
- Ficha do projeto, abaixo de Tempo previsto: **Custo previsto**, **Custo
  Realizado** e **Desvio de custo** (previsto − realizado: positivo = gastou menos
  que o previsto), visíveis ao gerente de timesheet.
- Painel de rentabilidade do projeto: linha "Custo de pessoal (salário,
  benefícios, provisões)". O Odoo só exibe a seção Rentabilidade a usuários com o
  grupo **Contabilidade analítica** (`analytic.group_analytic_accounting`). O custo
  nativo de timesheet não é alterado; para colaboradores com custo por hora
  preenchido, o salário pode aparecer em duplicidade.
