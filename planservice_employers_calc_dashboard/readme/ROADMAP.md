Módulo **temporário**, a ser removido junto com `planservice_employers_calc`
quando o módulo financeiro for implantado.

- Plano de saída: desinstalar este módulo antes do principal. O dashboard criado
  na instalação leva um xmlid do módulo e é apagado na desinstalação.
- O Boardkit não oferece um seletor de obra com busca nem filtro por URL; o botão
  do projeto contorna isso gravando o filtro do usuário. Se o Boardkit ganhar
  esses recursos, o botão pode ser simplificado.
- Os nomes do dashboard e dos itens ficam em português nos dados e não passam
  pelo `pt_BR.po`. Se o dashboard virar multilíngue, traduzir pelos registros.
