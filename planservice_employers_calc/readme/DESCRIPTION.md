Demonstrativo do custo de cada colaborador por obra (projeto), rateando o custo
mensal do colaborador pela fração do mês dedicada à obra::

    custo da linha = custo mensal × (% do dia lançada) / dias úteis do mês

O RH preenche na ficha do colaborador dois valores **mensais**: salário +
benefícios e provisões. Quem lança 100% de todos os dias úteis de um mês tem o
custo mensal inteiro apropriado, com 18, 20 ou 23 dias úteis. Os dias úteis são
de segunda a sexta, menos os feriados globais do calendário do colaborador.

No projeto, o módulo mostra o custo previsto (horas previstas das tarefas ÷ horas
mensais do plano × custo mensal do responsável), o custo real e o desvio. O
cálculo é feito na consulta (views SQL); nada é gravado nas linhas de timesheet.
