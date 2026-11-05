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
