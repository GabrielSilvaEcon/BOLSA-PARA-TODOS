# Trabalho sujo (revisão manual, depois de TODAS as etapas)

Gabriel grava a tela usando o app e envia; correções saem agrupadas.

1. Revisão visual de todos os módulos no tablet e no celular.
2. Testar limites, bloqueio e suspensão no painel Consumo; observar os números por alguns dias antes de usar "bloquear".
3. Testar o canal de e-mail.
4. Monitor no GitHub Actions: o cron pode atrasar; pausa após 60 dias sem atividade.
5. Contar usos restantes do Yahoo (mercados, fundos, evolução, recursos) e chamadas urllib da IA (hoje não contadas).
6. Validar ao vivo: dado antigo (fallback), erro 429 e disjuntor.
7. Conferir visualmente os painéis novos: cartões de plano em Minha conta, Planos e limites, Custos, Preços e Assinaturas.
8. **Pagamento automático (adiado na Etapa 9):** escolher provedor (Asaas tem tarifas confirmadas: cartão recorrente R$ 0,49 + 1,99% na promoção de 3 meses, Pix R$ 0,79 promo / R$ 1,59 depois, sem mensalidade; Mercado Pago e Stripe ainda sem tarifa confirmada), criar a conta, ligar a cobrança automática e preencher as taxas em Administração > Preços. Hoje o admin ativa/renova planos manualmente em Administração > Consumo > Assinaturas.
9. Modos globais Iniciante/Intermediário/Avançado (hoje só em Educação financeira).
10. Painéis novos para olhar no tablet/celular: Preços, Assinaturas (regras e cupons), Uso, Continuidade, e o bloco "Assinatura: cupom, teste grátis e cancelamento" em Minha conta.
11. Gerar um backup das configurações (Continuidade), guardá-lo fora do app e testar a restauração uma vez (precisa da chave de backup nos Secrets).
12. Carga real: abrir o app em vários aparelhos ao mesmo tempo e observar lentidão e erros; ver Consumo e Uso depois.
13. Decidir preços dos planos Plus/Premium (Administração > Preços) e, se quiser, ligar o teste grátis e criar o primeiro cupom.
14. Ler AUDITORIA_FINAL.md (seção "Ainda não comprovado").

15. **Modo de experiência (visual):** no tablet/celular, abrir "Meu modo" no menu lateral e trocar entre os 3 modos (conferir a prévia, o botão Confirmar e a mensagem de sucesso); conferir o menu de cada modo, a faixa no topo das telas e a tabela de Múltiplos. Sair e entrar de novo (e abrir em outro aparelho) e ver se o último modo volta.

16. **Leitura por modo (visual):** abrir Preço justo, Múltiplos, Carteira, Evolução e crescimento, Fundos (visão geral) e Cripto (visão geral) nos modos Iniciante e Avançado e conferir se o texto está claro (Iniciante sem siglas) e se o cartão não sobrepõe nada. Mandar print do que estranhar.
17. **Celular (390 px):** revisar Planos, menu lateral e os cartões de leitura; ver se nada corta nem sobrepõe.
18. **Início:** barra de abas ("Criptomoedas Binance" cortada/encostando no topo) — ajuste de espaçamento pendente.
19. **Cripto restante:** páginas on-chain, receitas, fundamentalista e avançada ainda sem leitura por modo (fazer depois).

20. **Nível de conhecimento no Início:** entrar com conta nova (ou antiga) e ver a caixa de boas-vindas só uma vez; escolher, sair, entrar de novo e em outro aparelho; trocar em Minha conta; conferir o quadro "O que significa cada indicador" em cada tela nos 3 níveis, no tablet e no celular.

21. **Tutoriais:** abrir "Como utilizar esta página?" em várias páginas nos 3 níveis (celular e tablet), avançar/voltar/fechar/concluir, sair e voltar para ver se retoma; Ajuda > Tutoriais, busca e Meu aprendizado; conferir se a introdução aparece só uma vez. Ler os textos e avisar o que estiver impreciso.
22. **Tutorial com destaque visual:** o Streamlit não permite apontar com seta para um botão da página; os tutoriais dizem "Onde fica". Decidir se vale uma solução maior depois.

## Cenário econômico — conferências manuais
- As fontes (BCB, IBGE, Ipeadata, FRED) não puderam ser testadas ao vivo no ambiente de desenvolvimento. Abrir Economia > aba Fontes e conferir quais indicadores aparecem como indisponíveis; cada um mostra a causa exata por fonte. Códigos de SGS/SIDRA de crédito, fiscal, PIM, ICC e núcleo são "melhor esforço" e protegidos por validação de faixa e frequência.
- Revisar visualmente a página Economia (9 seções) nos três níveis de conhecimento.


## Menu, profundidades, escolha de nível e roteiro de decisão — conferências manuais
- Abrir o app com uma conta nova (ou apagar a escolha de nível) e ver se a PRIMEIRA tela mostra só os três cartões de nível, sem busca; depois de escolher, a busca e a análise aparecem.
- Conferir no tablet se os cartões de nível cabem sem cortar (as três colunas empilham em tela estreita) e se os textos estão legíveis.
- Em cada nível (Iniciante, Intermediário, Avançado): ver o menu lateral (itens escondidos e a chave "Ver todas as páginas"), o Início e a profundidade padrão (Rápida, Mediana, Completa).
- Trocar a profundidade, fechar e reabrir o app: a escolha deve voltar salva. Conferir também em outro aparelho.
- Abrir FIIs, ETFs, Fundos, Renda fixa e Cripto (Análise avançada) nas três profundidades e ver se as abas mudam e a linha "mais abas na Completa" aparece.
- Roteiro de decisão (4 perguntas coloridas) e selo de atualização do balanço na leitura rápida: conferir cores e textos com uma empresa conhecida (ex.: Petrobras) e com uma sem dividendos.
- "Resumo do dia da economia" no Início: mostra a última leitura válida com a data ("leitura de 05/11 às 11:20"). Ela é gravada pelo monitor e também ao abrir a página Economia (sem mexer no histórico de alertas). Sem nenhuma leitura aparece o botão "Calcular agora". Conferir: abrir Economia, voltar ao Início e ver a data; com leitura de mais de 3 dias aparece o aviso de leitura antiga.
- Tutorial "Como utilizar esta página": confirmar que o texto da janela fica legível enquanto a página carrega (correção em tema.py).
- Economia > aba Fontes: ver quais indicadores seguem indisponíveis (Fed Funds e minério dependem só do FRED); mandar print se algum continuar sem dado.
- Introdução: depois de escolher o nível, ela abre numa JANELA própria, uma única vez; ao clicar em Início de novo (ou fechar no X) não volta. Conferir também o mini-mapa "Onde olhar na tela" (a parte da etapa fica brilhando) na introdução e em "Como utilizar esta página?". Para rever: Ajuda > Meu aprendizado > Rever a introdução.

## Cabeçalho, nível em todos os ativos e fotos nas notícias — conferências manuais
- Abrir várias páginas (Preço justo, Múltiplos, FIIs, Cripto...): cada uma deve COMEÇAR pelo próprio título; "Como utilizar esta página?" e o quadro de indicadores aparecem logo abaixo dele. Conferir que a linha branca fina no topo sumiu (se continuar, mandar print).
- O nível de conhecimento aparece no rodapé do menu lateral ("Nível: ...") e leva à Minha conta; a conta/saída continuam acessíveis pelo menu.
- Renda fixa: aba de visão geral mostra o cartão de leitura por nível (Iniciante vê só 4 itens simples).
- Notícias: conferir se as fotos aparecem nos cartões (destaque grande, demais pequenas); fontes sem foto no feed ficam sem imagem. Se alguma foto quebrar, o espaço dela some sozinho. Só fotos https são exibidas.

## Etapa 1 da nova navegação — conferências manuais
- Menu: Início e Alertas no topo; 7 grupos (Analisar por tipo de ativo, Ferramentas de análise, Minha carteira, Mercado e economia, Calculadoras e simuladores, Aprender e ajuda, Configurações); Administração só para administrador. Conferir no tablet e no celular (☰).
- Em todos os níveis todas as páginas aparecem; só ficam marcadas com ★ as sugeridas do nível. A chave "Ver todas as páginas" não existe mais.
- Alertas: o contador de não lidas aparece no nome do item. A página é a antiga Central de notificações (mesma lógica).
- Entrar com conta comum: não deve aparecer "Ajustes técnicos" (fonte de dados e atualizar). Com conta administradora/suporte deve aparecer. "Adicionar ativo por ticker" fica visível para todos até a busca universal (etapa 3).
- Cadeado: por padrão nenhuma página é trancada. Em Administração > Consumo > Planos e limites > "Páginas por plano", escolha um plano mínimo para uma página de teste, salve, espere 1 minuto: com conta Gratuita o menu mostra o cadeado e abrir a página (ou digitar o endereço /dcf direto) mostra a explicação com o botão para Planos. Depois volte para "Todos os planos".
