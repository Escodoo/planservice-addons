Demonstrativo do custo de cada colaborador por obra (projeto), rateando o custo
mensal do colaborador pela fração do mês dedicada à obra::

    custo da linha = custo mensal × (% do dia lançada) / dias úteis do mês

O RH preenche na ficha do colaborador dois valores **mensais**: salário +
benefícios e provisões. Quem lança 100% de todos os dias úteis de um mês tem o
custo mensal inteiro apropriado, com 18, 20 ou 23 dias úteis. Os dias úteis são
de segunda a sexta, menos os feriados globais do calendário do colaborador.

Cada alteração de salário + benefícios ou de provisões gera uma **versão de
custo** que vale a partir do **dia seguinte** à alteração. Cada lançamento usa a
versão vigente na sua data, então um aumento não muda o custo de lançamentos
anteriores.

No projeto, o módulo mostra o custo previsto (horas previstas das tarefas ÷ horas
mensais do plano × custo mensal do responsável), o custo real e o desvio. Quando
o projeto sai do status que permite replanejar ("Pendente"), o previsto é gravado
numa **linha de base** e não muda mais. Mudanças de salário, horas ou tarefas
depois disso só afetam o realizado e o desvio. O custo real é calculado na
consulta (views SQL), e nada é gravado nas linhas de timesheet.
