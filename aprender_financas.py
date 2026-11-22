"""Aprender · área EDUCAÇÃO FINANCEIRA (fase 2) — SÓ DADOS. Formato das lições em jornada_conteudo.py; aulas como em edu_conteudo.py.

Quatro trilhas novas (orçamento, cartão, dívidas e patrimônio), ao lado de "Primeiros passos" (que já existia e não muda).
Cada lição tem uma aula (explicação simples, exemplo do dia a dia e situação prática) e de 5 a 6 exercícios com explicação.
Números de exemplo são HIPOTÉTICOS e dizem isso; nada recomenda produto, banco ou investimento específico.
"""
from __future__ import annotations

AREA = "financas"

UNIDADES = [
    dict(id="uf_orc", area=AREA, titulo="Orçamento na prática", icone="🧮", icone_svg="livro", cor="#2DD4A0",
         descricao="Organizar o salário, gastar menos do que ganha e controlar as despesas.",
         licoes=["lf_salario", "lf_gastar_menos", "lf_despesas", "lf_orcamento"]),
    dict(id="uf_cartao", area=AREA, titulo="Cartão sem sustos", icone="💳", icone_svg="cofre", cor="#FF8A3D",
         descricao="Fatura, limite, fechamento, vencimento, juros e parcelamentos.",
         licoes=["lf_fatura", "lf_datas", "lf_rotativo", "lf_parcelas"]),
    dict(id="uf_dividas", area=AREA, titulo="Saindo das dívidas", icone="🧗", icone_svg="escudo", cor="#FF5A7A",
         descricao="Entender as dívidas, negociar e não voltar a se endividar.",
         licoes=["lf_div_mapa", "lf_div_negociar", "lf_div_nunca_mais"]),
    dict(id="uf_patrimonio", area=AREA, titulo="Construindo patrimônio", icone="🏗️", icone_svg="predio", cor="#4DA3FF",
         descricao="Quanto investir por mês, metas e planejamento financeiro.",
         licoes=["lf_quanto_investir", "lf_metas", "lf_plano"]),
]

NIVEIS = {"lf_rotativo": "intermediario", "lf_div_negociar": "intermediario", "lf_plano": "intermediario", "lf_quanto_investir": "intermediario"}

# ---------------------------------------------------------------------------------------------------- aulas
_A = dict(assunto="fundamentos", dificuldade="iniciante", fontes=["bcb", "cvm"], relacionadas=[])
AULAS = [
    dict(_A, id="af_salario", titulo="Como organizar o salário", min=4,
         iniciante="Organizar o salário é decidir **para onde cada real vai antes de gastar**, e não descobrir no fim do mês para onde ele foi.\n\n"
                   "**Passo a passo:** (1) anote quanto entra de verdade, já sem descontos; (2) separe primeiro as contas fixas (aluguel, luz, transporte); "
                   "(3) separe uma parte para guardar logo no dia do pagamento (\"pague-se primeiro\"); (4) o que sobra é para o dia a dia e o lazer.\n\n"
                   "**Exemplo do dia a dia (hipotético):** Ana recebe R$ 2.500 líquidos. Ela paga R$ 1.300 de contas fixas e, no mesmo dia, separa R$ 250 "
                   "para a reserva. Sobram R$ 950 para mercado, lazer e imprevistos pequenos.\n\n"
                   "**Na prática:** use contas ou \"caixinhas\" separadas para cada destino. Dinheiro misturado some sem você perceber.",
         intermediario="Uma referência simples é a regra **50/30/20**: 50% para necessidades, 30% para desejos e 20% para objetivos (reserva, dívidas, "
                       "investimentos). Ela é um ponto de partida, não uma lei: quem tem aluguel alto ou dívidas ajusta as fatias. O importante é que a fatia de "
                       "objetivos saia **no início** do mês, de forma automática, e não do que sobrar."),
    dict(_A, id="af_gastar_menos", titulo="Gastar menos do que ganha", min=4,
         iniciante="A regra de ouro das finanças é simples: **gastar menos do que se ganha**. A diferença é o que permite guardar, investir e ter paz.\n\n"
                   "Há dois caminhos: **gastar menos** (cortar desperdícios) ou **ganhar mais** (renda extra, qualificação). Os dois funcionam melhor juntos.\n\n"
                   "**Exemplo do dia a dia (hipotético):** um café de R$ 8 todo dia útil custa cerca de R$ 176 por mês. Trocar por café de casa três vezes por "
                   "semana libera uns R$ 100 por mês, sem abrir mão de tudo.\n\n"
                   "**Na prática:** antes de uma compra não planejada, espere 24 horas. Muitas vontades passam, e o dinheiro fica.",
         intermediario="Cortes pequenos e constantes somam mais do que cortes grandes que não duram. Comece pelos **gastos invisíveis**: assinaturas "
                       "esquecidas, tarifas bancárias, juros de atraso e delivery. Revise-os a cada três meses."),
    dict(_A, id="af_despesas", titulo="Controle de despesas", min=4,
         iniciante="Controlar despesas é **anotar o que sai** e separar por tipo. Sem anotar, a gente sempre acha que gastou menos do que gastou.\n\n"
                   "**Tipos de despesa:** **fixas** (quase iguais todo mês, como aluguel), **variáveis** (mudam, como mercado e combustível) e "
                   "**eventuais** (aparecem de vez em quando, como IPVA, material escolar e presentes).\n\n"
                   "**Exemplo do dia a dia:** João anotou tudo por um mês e descobriu que gastava mais com delivery do que com o mercado.\n\n"
                   "**Na prática:** use o app do banco, uma planilha ou um caderno. O melhor método é o que você consegue manter.",
         intermediario="As **despesas eventuais** são as que mais desorganizam o orçamento, porque parecem surpresa. Some o total do ano (IPVA, IPTU, matrícula, "
                       "seguros) e divida por 12: esse valor deve ser guardado todo mês numa reserva própria."),
    dict(_A, id="af_orcamento", titulo="Orçamento mensal", min=5,
         iniciante="O orçamento é o **plano do mês**: quanto vai entrar, quanto vai sair e quanto vai sobrar. É feito **antes** do mês começar.\n\n"
                   "**Como montar:** liste as receitas; liste as despesas fixas; estime as variáveis pela média dos últimos meses; reserve uma parte para "
                   "objetivos; confira se a conta fecha. Se não fechar, corte antes de gastar, não depois.\n\n"
                   "**Exemplo (hipotético):** renda de R$ 3.000; fixas R$ 1.500; variáveis R$ 900; objetivos R$ 400; folga R$ 200 para imprevistos.\n\n"
                   "**Na prática:** no fim do mês, compare o planejado com o realizado e ajuste o próximo.",
         intermediario="Orçamento bom tem **folga**: uma linha para imprevistos pequenos evita que qualquer gasto fora do plano vire dívida. Se o orçamento "
                       "nunca fecha, o problema é estrutural (renda baixa ou custo fixo alto demais) e pede uma mudança maior, como renegociar aluguel ou planos."),
    dict(_A, id="af_fatura", titulo="Como o cartão e a fatura funcionam", min=5, fontes=["bcb"],
         iniciante="O cartão de crédito é um **empréstimo de curto prazo**: o banco paga a loja agora e você paga o banco depois, na fatura.\n\n"
                   "A **fatura** junta tudo o que foi comprado num período e mostra: o **valor total**, o **pagamento mínimo**, a **data de vencimento** "
                   "e as **parcelas futuras** que ainda vão aparecer.\n\n"
                   "**Exemplo do dia a dia:** você compra uma geladeira em 10 vezes. Cada fatura traz só 1 parcela, mas o limite do cartão fica comprometido "
                   "com o valor inteiro até tudo ser pago.\n\n"
                   "**Na prática:** confira a fatura todo mês, linha por linha. Compra que você não reconhece deve ser contestada com o banco.",
         intermediario="Pagar a fatura **inteira** no vencimento é o único jeito de usar o cartão sem pagar juros. Olhe também o campo **\"próximas faturas\"**: "
                       "parcelas acumuladas são a causa mais comum de faturas que crescem sem você perceber."),
    dict(_A, id="af_datas", titulo="Limite, fechamento e vencimento", min=4, fontes=["bcb"],
         iniciante="Três palavras explicam o cartão:\n\n"
                   "**Limite** é o máximo que você pode dever no cartão. Não é dinheiro seu: é crédito do banco.\n\n"
                   "**Fechamento** é o dia em que a fatura \"fecha\": o que você compra depois dele só entra na fatura do mês seguinte.\n\n"
                   "**Vencimento** é o último dia para pagar a fatura sem multa e juros. Costuma ser alguns dias depois do fechamento.\n\n"
                   "**Exemplo:** fechamento dia 5 e vencimento dia 15. Uma compra no dia 6 só será paga no vencimento do mês seguinte: quase 40 dias depois.\n\n"
                   "**Na prática:** o \"melhor dia de compra\" é logo depois do fechamento. Mas prazo maior não é dinheiro a mais.",
         intermediario="Escolha o **vencimento** para alguns dias depois do dia em que o salário cai. Assim a fatura é paga com o dinheiro do mês, e não com o "
                       "que ainda não entrou. Um limite muito acima da sua renda é um risco: ele convida a gastar o que você não tem."),
    dict(_A, id="af_rotativo", titulo="Juros do cartão e o rotativo", min=5, fontes=["bcb"],
         iniciante="Se você paga **menos do que o total** da fatura, o resto vira dívida no **rotativo**, uma das linhas de crédito com os **juros mais altos** do "
                   "país. Pagar só o mínimo parece um alívio, mas a dívida cresce rápido.\n\n"
                   "**Regras importantes (Banco Central):** o rotativo só pode ser usado até a fatura seguinte; depois disso, o banco deve oferecer um "
                   "**parcelamento** da dívida, com juros menores. E, desde 2024, os juros e encargos do rotativo e do parcelamento da fatura **não podem "
                   "passar de 100% do valor original da dívida**.\n\n"
                   "**Exemplo (hipotético):** uma dívida de R$ 1.000 no rotativo pode virar, no máximo, R$ 2.000 em juros e encargos somados. Ainda é muito.\n\n"
                   "**Na prática:** se não der para pagar tudo, troque o rotativo por um crédito mais barato (empréstimo pessoal ou consignado) e pare de usar o cartão.",
         intermediario="Compare sempre o **Custo Efetivo Total (CET)**, que soma juros, tarifas e impostos. O teto de 100% limita o estrago, mas não torna o "
                       "rotativo barato: ele continua sendo uma das opções mais caras. A ordem para sair é: parar de usar, trocar por crédito mais barato e quitar."),
    dict(_A, id="af_parcelas", titulo="Parcelamentos", min=4, fontes=["bcb"],
         iniciante="Parcelar é dividir uma compra em várias faturas. Existem dois tipos:\n\n"
                   "**Parcelado sem juros:** o preço final é o mesmo do à vista (às vezes o à vista tem desconto, e aí o parcelado sai mais caro).\n\n"
                   "**Parcelado com juros:** você paga mais do que o preço à vista. Some todas as parcelas para ver o preço real.\n\n"
                   "**Exemplo (hipotético):** R$ 1.200 à vista ou 12 × R$ 120 = R$ 1.440. Os R$ 240 a mais são juros.\n\n"
                   "**Na prática:** antes de parcelar, pergunte: \"Eu compraria isso se tivesse de pagar à vista?\" e some as parcelas que já existem.",
         intermediario="O perigo do parcelamento é a **soma**: várias parcelas pequenas comprometem a renda dos próximos meses. Uma regra prática é não deixar "
                       "as parcelas somarem mais de uma fatia pequena da renda mensal. Desconto à vista maior que o rendimento do seu dinheiro favorece pagar à vista."),
    dict(_A, id="af_div_mapa", titulo="Entendendo as suas dívidas", min=4, fontes=["bcb"],
         iniciante="O primeiro passo para sair das dívidas é **saber exatamente quanto e para quem você deve**. Muita gente evita olhar, e a dívida cresce no escuro.\n\n"
                   "**Faça uma lista:** credor, valor total, parcela, taxa de juros e se está atrasada. O **Registrato**, do Banco Central, mostra gratuitamente "
                   "as dívidas registradas no seu CPF.\n\n"
                   "**Exemplo do dia a dia:** Carla achava que devia R$ 3 mil, mas a lista mostrou R$ 5.200 somando cartão, cheque especial e um carnê.\n\n"
                   "**Na prática:** ordene as dívidas da **maior taxa de juros para a menor**. As mais caras são as primeiras a atacar.",
         intermediario="Separe dívidas **caras** (rotativo, cheque especial) de **baratas** (consignado, financiamento imobiliário). Atacar primeiro a de maior juros "
                       "é o método \"avalanche\", que economiza mais. O método \"bola de neve\" (menor saldo primeiro) motiva mais. Escolha o que você vai cumprir."),
    dict(_A, id="af_div_negociar", titulo="Negociar e trocar dívidas", min=5, fontes=["bcb"],
         iniciante="Dívida pode ser **negociada**. Bancos e lojas preferem receber menos a não receber nada.\n\n"
                   "**Como negociar:** saiba quanto você consegue pagar por mês **sem fazer nova dívida**; peça desconto para pagar à vista ou parcelas que caibam; "
                   "peça tudo por escrito antes de pagar.\n\n"
                   "**Trocar dívida cara por barata:** pegar um empréstimo com juros menores para quitar o rotativo ou o cheque especial pode reduzir muito o custo, "
                   "desde que você **pare de usar** o crédito caro.\n\n"
                   "**Na prática:** desconfie de quem cobra antecipado para \"limpar seu nome\". Negocie direto com o credor ou em canais oficiais.",
         intermediario="A **Lei do Superendividamento (Lei 14.181/2021)** permite a quem não consegue pagar as dívidas de consumo sem comprometer o mínimo para viver "
                       "pedir uma **repactuação** conjunta com os credores. Compare propostas pelo **valor total pago** e pelo CET, não só pela parcela."),
    dict(_A, id="af_div_nunca_mais", titulo="Para não voltar a se endividar", min=4,
         iniciante="Sair da dívida é metade do caminho; a outra metade é **não voltar**.\n\n"
                   "**Hábitos que protegem:** ter uma **reserva de emergência** (para o imprevisto não virar dívida), usar o cartão só para o que já está no "
                   "orçamento, evitar o cheque especial e desconfiar de \"crédito fácil\".\n\n"
                   "**Exemplo do dia a dia:** o pneu do carro furou. Quem tem reserva paga e repõe a reserva; quem não tem entra no cartão e paga juros.\n\n"
                   "**Na prática:** depois de quitar uma dívida, continue \"pagando a parcela\" para você mesmo, guardando o mesmo valor.",
         intermediario="Reduza o **limite** do cartão e do cheque especial para algo compatível com a sua renda. Menos crédito disponível é menos tentação. "
                       "Acompanhe o orçamento todo mês: dívida quase sempre começa com pequenos meses no vermelho."),
    dict(_A, id="af_quanto_investir", titulo="Quanto investir por mês", min=5, fontes=["cvm"],
         iniciante="Não existe valor mínimo mágico: **o importante é começar e manter a constância**. Muitos investimentos aceitam valores pequenos.\n\n"
                   "**Ordem sugerida:** (1) sair das dívidas caras; (2) montar a reserva de emergência; (3) investir para objetivos.\n\n"
                   "**Exemplo (hipotético, sem considerar juros):** guardar R$ 200 por mês vira R$ 2.400 em um ano e R$ 24.000 em dez anos. Com rendimento, o valor "
                   "final fica maior, por causa dos juros compostos.\n\n"
                   "**Na prática:** programe o investimento para o dia do salário. O que sai automático não depende de força de vontade.",
         intermediario="Uma meta comum é investir de **10% a 20% da renda**, mas o valor certo vem do objetivo: quanto você precisa, em quanto tempo e com que "
                       "rendimento esperado. Aumente o aporte a cada aumento de salário, antes de aumentar o padrão de vida."),
    dict(_A, id="af_metas", titulo="Metas financeiras", min=4,
         iniciante="Meta financeira é um **objetivo com valor e prazo**. \"Quero viajar\" é um desejo; \"quero R$ 6.000 para viajar em 12 meses\" é uma meta.\n\n"
                   "**Prazos:** curto (até 1 ano), médio (1 a 5 anos) e longo (mais de 5 anos). Quanto mais curto o prazo, mais seguro deve ser o lugar onde o "
                   "dinheiro fica.\n\n"
                   "**Exemplo (hipotético):** R$ 6.000 em 12 meses dá R$ 500 por mês, sem contar rendimento.\n\n"
                   "**Na prática:** escreva as metas, ponha valor e data, e acompanhe todo mês.",
         intermediario="Metas boas são **específicas, mensuráveis e com prazo**. Separe o dinheiro de cada meta (contas ou caixinhas diferentes) e escolha o "
                       "investimento pelo **prazo** da meta, não pelo maior rendimento do momento."),
    dict(_A, id="af_plano", titulo="Planejamento financeiro", min=5, fontes=["cvm", "anbima"],
         iniciante="Planejamento financeiro junta tudo: **orçamento, dívidas, reserva, metas, investimentos e proteção** (seguros, quando fazem sentido).\n\n"
                   "**O ciclo:** saber onde você está (renda, gastos, dívidas, patrimônio), decidir aonde quer chegar (metas) e montar o caminho (quanto guardar e onde).\n\n"
                   "**Patrimônio** é tudo o que você tem menos tudo o que você deve. Ele cresce quando você gasta menos do que ganha e investe a diferença.\n\n"
                   "**Na prática:** revise o plano uma vez por ano ou quando a vida muda (emprego, casamento, filhos).",
         intermediario="Acompanhe o **patrimônio líquido** (ativos − dívidas) uma vez por mês. Ele mostra o progresso melhor do que o saldo da conta. Um bom plano "
                       "considera também riscos que podem derrubar tudo (doença, perda de renda) e como se proteger deles."),
]

# ---------------------------------------------------------------------------------------------------- lições
LICOES = [
    # -------- Orçamento na prática
    dict(id="lf_salario", unidade="uf_orc", titulo="Organizar o salário", icone="💵", aula="af_salario", exercicios=[
        dict(tipo="escolha", pergunta="Qual é a ideia de \"pagar-se primeiro\"?",
             opcoes=["Guardar o que sobrar no fim do mês", "Separar a parte de guardar logo que o salário entra",
                     "Pagar as próprias compras antes das contas", "Gastar com lazer antes de tudo"], correta=1,
             explicacao="Guardar no começo do mês, de forma automática, funciona melhor do que esperar sobrar, porque quase nunca sobra."),
        dict(tipo="escolha", pergunta="Caso: Ana recebe R$ 2.500 e tem R$ 1.300 de contas fixas. Ela separa R$ 250 para a reserva no dia do pagamento. Quanto sobra para o resto do mês?",
             opcoes=["R$ 1.200", "R$ 950", "R$ 1.050", "R$ 2.250"], correta=1,
             explicacao="2.500 − 1.300 − 250 = 950. Esse é o valor para mercado, lazer e imprevistos pequenos."),
        dict(tipo="vf", pergunta="Manter todo o dinheiro numa só conta ajuda a controlar melhor os gastos.", correta=False,
             explicacao="Separar destinos (contas ou caixinhas) ajuda a ver o que é de cada coisa. Dinheiro misturado some sem perceber."),
        dict(tipo="ordenar", pergunta="Coloque na ordem a organização do salário.",
             itens=["Anotar quanto entra de verdade", "Separar as contas fixas", "Guardar a parte dos objetivos", "Usar o resto no dia a dia"],
             explicacao="Primeiro saber quanto entra, depois garantir as contas e os objetivos, e só então gastar com o resto."),
        dict(tipo="completar", pergunta="Na regra 50/30/20, a fatia de 20% vai para ___.",
             opcoes=["objetivos, como reserva e investimentos", "lazer", "aluguel", "impostos"], correta=0,
             explicacao="50% necessidades, 30% desejos e 20% objetivos. É uma referência que pode ser ajustada."),
    ]),
    dict(id="lf_gastar_menos", unidade="uf_orc", titulo="Gastar menos do que ganha", icone="🪙", aula="af_gastar_menos", exercicios=[
        dict(tipo="vf", pergunta="A regra de ouro das finanças pessoais é gastar menos do que se ganha.", correta=True,
             explicacao="É a diferença entre o que entra e o que sai que permite guardar e investir."),
        dict(tipo="escolha", pergunta="Caso: um café de R$ 8 em 22 dias úteis. Quanto custa por mês?",
             opcoes=["R$ 88", "R$ 176", "R$ 240", "R$ 22"], correta=1,
             explicacao="8 × 22 = 176. Gastos pequenos e repetidos pesam muito no mês."),
        dict(tipo="escolha", pergunta="Qual destas é uma boa estratégia contra compras por impulso?",
             opcoes=["Comprar logo antes que acabe a promoção", "Esperar 24 horas antes de uma compra não planejada",
                     "Parcelar para caber no mês", "Usar o cartão de outra pessoa"], correta=1,
             explicacao="Esperar um dia faz muitas vontades passarem e protege o orçamento."),
        dict(tipo="pares", pergunta="Ligue cada caminho ao seu exemplo.",
             pares=[("Gastar menos", "Cancelar uma assinatura que não usa"), ("Ganhar mais", "Fazer um curso para uma promoção"),
                    ("Gasto invisível", "Tarifa bancária que ninguém percebe")],
             explicacao="Os dois caminhos funcionam melhor juntos, e os gastos invisíveis são o melhor lugar para começar a cortar."),
        dict(tipo="vf", pergunta="Cortes pequenos e constantes costumam funcionar melhor do que cortes radicais que não duram.", correta=True,
             explicacao="Mudança que você consegue manter vence a que você abandona em duas semanas."),
    ]),
    dict(id="lf_despesas", unidade="uf_orc", titulo="Controle de despesas", icone="📝", aula="af_despesas", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada despesa ao seu tipo.",
             pares=[("Aluguel", "Fixa"), ("Mercado", "Variável"), ("IPVA", "Eventual")],
             explicacao="Fixas quase não mudam, variáveis mudam todo mês e eventuais aparecem de vez em quando."),
        dict(tipo="escolha", pergunta="Por que as despesas eventuais costumam desorganizar o orçamento?",
             opcoes=["Porque são proibidas", "Porque parecem surpresa, mas são previsíveis", "Porque sempre são pequenas", "Porque só acontecem com quem tem dívida"], correta=1,
             explicacao="IPVA, matrícula e presentes acontecem todo ano. Guardar 1/12 por mês evita o susto."),
        dict(tipo="escolha", pergunta="Caso: IPVA de R$ 1.200 e material escolar de R$ 600 por ano. Quanto guardar por mês para eles?",
             opcoes=["R$ 100", "R$ 150", "R$ 180", "R$ 1.800"], correta=1,
             explicacao="(1.200 + 600) ÷ 12 = 150 por mês."),
        dict(tipo="vf", pergunta="O melhor método de controle de gastos é o que você consegue manter.", correta=True,
             explicacao="Planilha, app ou caderno: o que importa é anotar sempre."),
        dict(tipo="completar", pergunta="Sem anotar, a gente costuma achar que gastou ___ do que realmente gastou.",
             opcoes=["menos", "mais", "exatamente o mesmo", "o dobro"], correta=0,
             explicacao="A memória esquece os gastos pequenos. Anotar mostra o valor real."),
    ]),
    dict(id="lf_orcamento", unidade="uf_orc", titulo="Orçamento mensal", icone="📅", aula="af_orcamento", exercicios=[
        dict(tipo="escolha", pergunta="Quando o orçamento do mês deve ser feito?",
             opcoes=["No fim do mês, para ver o que aconteceu", "Antes do mês começar", "Só quando faltar dinheiro", "Uma vez por ano"], correta=1,
             explicacao="Orçamento é um plano: faz-se antes, e no fim do mês compara-se com o que aconteceu."),
        dict(tipo="escolha", pergunta="Caso: renda R$ 3.000; fixas R$ 1.500; variáveis R$ 900; objetivos R$ 400. Quanto sobra de folga?",
             opcoes=["R$ 0", "R$ 200", "R$ 600", "R$ 400"], correta=1,
             explicacao="3.000 − 1.500 − 900 − 400 = 200. Essa folga cobre imprevistos pequenos."),
        dict(tipo="vf", pergunta="Um orçamento sem nenhuma folga para imprevistos é o mais seguro.", correta=False,
             explicacao="Sem folga, qualquer gasto fora do plano vira dívida. Uma pequena reserva no orçamento evita isso."),
        dict(tipo="ordenar", pergunta="Coloque na ordem a montagem do orçamento.",
             itens=["Listar as receitas", "Listar as despesas fixas", "Estimar as variáveis", "Reservar para os objetivos", "Conferir se a conta fecha"],
             explicacao="Do que entra para o que sai, e no fim a conferência: se não fechar, corte antes de gastar."),
        dict(tipo="escolha", pergunta="Se o orçamento nunca fecha, mesmo cortando o supérfluo, o que isso indica?",
             opcoes=["Que é preciso parar de anotar", "Um problema estrutural, como custo fixo alto ou renda baixa",
                     "Que o cartão de crédito resolve", "Nada, é normal"], correta=1,
             explicacao="Aí a solução é maior: renegociar contas fixas, mudar planos ou buscar renda extra."),
    ]),
    # -------- Cartão sem sustos
    dict(id="lf_fatura", unidade="uf_cartao", titulo="Como funciona a fatura", icone="🧾", aula="af_fatura", exercicios=[
        dict(tipo="vf", pergunta="O cartão de crédito é uma forma de empréstimo de curto prazo.", correta=True,
             explicacao="O banco paga a loja agora e você paga o banco depois, na fatura."),
        dict(tipo="escolha", pergunta="Qual é o único jeito de usar o cartão sem pagar juros?",
             opcoes=["Pagar o mínimo", "Pagar a fatura inteira até o vencimento", "Pagar metade e o resto no mês seguinte", "Usar só em compras pequenas"], correta=1,
             explicacao="Pagando o total até o vencimento, não há juros. Qualquer valor menor vira dívida com juros altos."),
        dict(tipo="escolha", pergunta="Caso: uma geladeira de R$ 3.000 em 10 vezes. Quanto do limite fica comprometido logo após a compra?",
             opcoes=["R$ 300", "R$ 3.000", "R$ 1.500", "Nada"], correta=1,
             explicacao="O limite fica ocupado pelo valor total e vai sendo liberado conforme as parcelas são pagas."),
        dict(tipo="completar", pergunta="O campo \"próximas faturas\" mostra as ___ que ainda vão aparecer.",
             opcoes=["parcelas", "promoções", "tarifas de saque", "metas"], correta=0,
             explicacao="Parcelas acumuladas são a causa mais comum de faturas que crescem sem perceber."),
        dict(tipo="vf", pergunta="Uma compra que você não reconhece na fatura deve ser contestada com o banco.", correta=True,
             explicacao="Confira a fatura todo mês. Compras desconhecidas podem ser erro ou fraude."),
    ]),
    dict(id="lf_datas", unidade="uf_cartao", titulo="Limite, fechamento e vencimento", icone="🗓️", aula="af_datas", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada termo do cartão ao seu significado.",
             pares=[("Limite", "Máximo que você pode dever no cartão"), ("Fechamento", "Dia em que a fatura do mês é fechada"),
                    ("Vencimento", "Último dia para pagar sem multa e juros")],
             explicacao="Esses três termos explicam quase tudo sobre o funcionamento da fatura."),
        dict(tipo="escolha", pergunta="Caso: fechamento no dia 5 e vencimento no dia 15. Uma compra no dia 6 entra em qual fatura?",
             opcoes=["Na fatura que vence dia 15 deste mês", "Na fatura do mês seguinte", "Em nenhuma", "É cobrada na hora"], correta=1,
             explicacao="Compras depois do fechamento entram na próxima fatura, por isso o dia seguinte ao fechamento é o \"melhor dia de compra\"."),
        dict(tipo="vf", pergunta="O limite do cartão é dinheiro que pertence a você.", correta=False,
             explicacao="Limite é crédito do banco: é dinheiro emprestado, que precisa ser devolvido."),
        dict(tipo="escolha", pergunta="Qual é uma boa escolha para o dia de vencimento?",
             opcoes=["Antes do salário cair", "Alguns dias depois do salário cair", "No meio do mês, sempre", "Tanto faz"], correta=1,
             explicacao="Assim a fatura é paga com o dinheiro que já entrou, e não com o que ainda vai entrar."),
        dict(tipo="vf", pergunta="Comprar logo após o fechamento dá mais prazo, mas não aumenta o seu dinheiro.", correta=True,
             explicacao="Prazo maior ajuda o fluxo do mês, mas a compra continua tendo de caber no orçamento."),
    ]),
    dict(id="lf_rotativo", unidade="uf_cartao", titulo="Juros do cartão e rotativo", icone="🌀", aula="af_rotativo", exercicios=[
        dict(tipo="escolha", pergunta="O que acontece se você paga só o mínimo da fatura?",
             opcoes=["Nada, o resto é perdoado", "O resto vai para o rotativo, com juros muito altos", "O banco cancela as compras", "O resto passa para o mês seguinte sem juros"], correta=1,
             explicacao="O saldo não pago entra no rotativo, uma das linhas de crédito mais caras do país."),
        dict(tipo="vf", pergunta="O rotativo pode ser usado só até a fatura seguinte; depois o banco deve oferecer um parcelamento.", correta=True,
             explicacao="É uma regra do Banco Central: o rotativo não pode se arrastar mês após mês."),
        dict(tipo="escolha", pergunta="Caso: uma dívida original de R$ 1.000 no rotativo. Pela regra em vigor desde 2024, qual é o máximo de juros e encargos somados?",
             opcoes=["R$ 100", "R$ 500", "R$ 1.000", "Não há limite"], correta=2,
             explicacao="Juros e encargos do rotativo e do parcelamento da fatura não podem passar de 100% do valor original da dívida."),
        dict(tipo="completar", pergunta="Para comparar créditos, olhe o ___, que soma juros, tarifas e impostos.",
             opcoes=["CET (Custo Efetivo Total)", "valor da parcela", "limite", "cashback"], correta=0,
             explicacao="O CET mostra o custo real. A parcela sozinha engana."),
        dict(tipo="ordenar", pergunta="Coloque na ordem o caminho para sair do rotativo.",
             itens=["Parar de usar o cartão", "Trocar por um crédito mais barato", "Quitar a dívida"],
             explicacao="Sem parar de usar, a dívida volta a crescer; trocar por crédito mais barato reduz o custo."),
    ]),
    dict(id="lf_parcelas", unidade="uf_cartao", titulo="Parcelamentos", icone="✂️", aula="af_parcelas", exercicios=[
        dict(tipo="escolha", pergunta="Caso: R$ 1.200 à vista ou 12 × R$ 120. Quanto de juros há no parcelado?",
             opcoes=["Nenhum", "R$ 120", "R$ 240", "R$ 1.440"], correta=2,
             explicacao="12 × 120 = 1.440. A diferença para o à vista, R$ 240, são juros."),
        dict(tipo="vf", pergunta="Se o à vista tem desconto, o \"parcelado sem juros\" na verdade sai mais caro.", correta=True,
             explicacao="O preço real do parcelado é o total das parcelas. Compare com o à vista com desconto."),
        dict(tipo="escolha", pergunta="Qual é o maior perigo de parcelar muitas compras?",
             opcoes=["As parcelas somadas comprometem a renda dos próximos meses", "O banco não aceita", "As lojas cobram mais", "Nenhum"], correta=0,
             explicacao="Várias parcelas pequenas viram uma fatura grande todo mês."),
        dict(tipo="completar", pergunta="Antes de parcelar, uma boa pergunta é: \"Eu compraria isso se tivesse de pagar ___?\"",
             opcoes=["à vista", "em 24 vezes", "no próximo ano", "com o cartão de outra pessoa"], correta=0,
             explicacao="Se não compraria à vista, talvez a compra não caiba no seu orçamento."),
        dict(tipo="vf", pergunta="Para saber o preço real de uma compra parcelada com juros, basta olhar o valor da parcela.", correta=False,
             explicacao="É preciso somar todas as parcelas e comparar com o preço à vista."),
    ]),
    # -------- Saindo das dívidas
    dict(id="lf_div_mapa", unidade="uf_dividas", titulo="Entendendo as dívidas", icone="🗺️", aula="af_div_mapa", exercicios=[
        dict(tipo="escolha", pergunta="Qual é o primeiro passo para sair das dívidas?",
             opcoes=["Pegar outro empréstimo", "Fazer uma lista com todas as dívidas", "Ignorar as ligações", "Pagar a menor parcela"], correta=1,
             explicacao="Sem saber quanto e para quem você deve, não dá para planejar a saída."),
        dict(tipo="vf", pergunta="O Registrato, do Banco Central, mostra gratuitamente dívidas registradas no seu CPF.", correta=True,
             explicacao="É um serviço oficial e gratuito do Banco Central."),
        dict(tipo="pares", pergunta="Ligue cada dívida ao seu custo típico.",
             pares=[("Rotativo do cartão", "Uma das mais caras do país"), ("Empréstimo consignado", "Mais barata, descontada do salário"),
                    ("Financiamento imobiliário", "Mais barata, com o imóvel de garantia")],
             explicacao="Rotativo e cheque especial estão entre os créditos mais caros; créditos com garantia ou desconto em folha costumam ser mais baratos."),
        dict(tipo="escolha", pergunta="Pelo método \"avalanche\", qual dívida você ataca primeiro?",
             opcoes=["A de menor saldo", "A de maior taxa de juros", "A mais antiga", "A do maior credor"], correta=1,
             explicacao="Quitar primeiro a mais cara economiza mais juros. O método \"bola de neve\" (menor saldo) motiva mais."),
        dict(tipo="vf", pergunta="Evitar olhar as dívidas faz elas diminuírem com o tempo.", correta=False,
             explicacao="Dívida ignorada cresce com juros e multas. Olhar é o primeiro passo."),
    ]),
    dict(id="lf_div_negociar", unidade="uf_dividas", titulo="Negociar e trocar dívidas", icone="🤝", aula="af_div_negociar", exercicios=[
        dict(tipo="escolha", pergunta="Antes de negociar uma dívida, o que você precisa saber?",
             opcoes=["Quanto consegue pagar por mês sem fazer nova dívida", "O nome do gerente", "A cotação do dólar", "Nada, é só aceitar a primeira proposta"], correta=0,
             explicacao="Acordo que não cabe no bolso vira nova dívida."),
        dict(tipo="vf", pergunta="Trocar o rotativo por um empréstimo mais barato só ajuda se você parar de usar o crédito caro.", correta=True,
             explicacao="Senão você fica com as duas dívidas."),
        dict(tipo="escolha", pergunta="Alguém cobra uma taxa adiantada para \"limpar seu nome\". O que fazer?",
             opcoes=["Pagar logo", "Desconfiar e negociar direto com o credor ou canais oficiais", "Passar os dados do cartão", "Indicar para amigos"], correta=1,
             explicacao="Cobrança antecipada para limpar o nome é um golpe comum."),
        dict(tipo="completar", pergunta="A Lei do Superendividamento permite pedir uma ___ conjunta das dívidas de consumo.",
             opcoes=["repactuação", "anulação", "transferência para outra pessoa", "isenção total"], correta=0,
             explicacao="A lei protege o mínimo necessário para viver e prevê um plano de pagamento com os credores."),
        dict(tipo="escolha", pergunta="Caso: proposta A de 10 × R$ 150; proposta B de 18 × R$ 100. Qual custa menos no total?",
             opcoes=["A, com R$ 1.500", "B, com R$ 1.800", "As duas custam igual", "Não dá para saber"], correta=0,
             explicacao="Compare pelo total: 10 × 150 = 1.500 e 18 × 100 = 1.800. A parcela menor sai mais cara."),
    ]),
    dict(id="lf_div_nunca_mais", unidade="uf_dividas", titulo="Para não voltar às dívidas", icone="🛡️", aula="af_div_nunca_mais", exercicios=[
        dict(tipo="escolha", pergunta="O que mais protege contra uma nova dívida quando surge um imprevisto?",
             opcoes=["Limite alto no cartão", "Uma reserva de emergência", "Cheque especial", "Empréstimo pré-aprovado"], correta=1,
             explicacao="Com reserva, o imprevisto é pago sem juros. Sem reserva, ele vira dívida."),
        dict(tipo="vf", pergunta="Depois de quitar uma dívida, continuar guardando o valor da antiga parcela é um bom hábito.", correta=True,
             explicacao="Você já estava acostumado a viver sem esse dinheiro: ele pode virar reserva ou investimento."),
        dict(tipo="escolha", pergunta="Por que reduzir o limite do cartão pode ajudar?",
             opcoes=["Porque diminui a tentação de gastar o que não tem", "Porque aumenta os pontos", "Porque o banco paga você", "Não ajuda em nada"], correta=0,
             explicacao="Crédito disponível demais convida a gastar além da renda."),
        dict(tipo="pares", pergunta="Ligue o imprevisto à melhor solução.",
             pares=[("Pneu furado", "Usar a reserva e repor depois"), ("Vontade de compra", "Esperar e pôr no orçamento"), ("Salário atrasou", "Usar a reserva, não o cheque especial")],
             explicacao="A reserva existe justamente para não usar crédito caro em imprevistos."),
        dict(tipo="vf", pergunta="Dívida grande quase sempre começa com pequenos meses no vermelho.", correta=True,
             explicacao="Acompanhar o orçamento todo mês pega o problema cedo."),
    ]),
    # -------- Construindo patrimônio
    dict(id="lf_quanto_investir", unidade="uf_patrimonio", titulo="Quanto investir por mês", icone="📈", aula="af_quanto_investir", exercicios=[
        dict(tipo="ordenar", pergunta="Coloque na ordem as prioridades.",
             itens=["Sair das dívidas caras", "Montar a reserva de emergência", "Investir para os objetivos"],
             explicacao="Investir com dívida cara aberta costuma render menos do que os juros que você paga."),
        dict(tipo="escolha", pergunta="Caso (sem juros): guardar R$ 200 por mês. Quanto você terá em 10 anos?",
             opcoes=["R$ 2.400", "R$ 20.000", "R$ 24.000", "R$ 200.000"], correta=2,
             explicacao="200 × 12 × 10 = 24.000. Com rendimento, o valor final fica maior por causa dos juros compostos."),
        dict(tipo="vf", pergunta="É preciso ter muito dinheiro para começar a investir.", correta=False,
             explicacao="Muitos investimentos aceitam valores pequenos. Constância importa mais do que o valor inicial."),
        dict(tipo="escolha", pergunta="Qual é um bom momento para programar o investimento do mês?",
             opcoes=["No dia em que o salário cai", "No fim do mês, com o que sobrar", "Só quando a bolsa cai", "Uma vez por ano"], correta=0,
             explicacao="Investimento automático no dia do salário não depende de força de vontade."),
        dict(tipo="completar", pergunta="A cada aumento de salário, aumente o ___ antes de aumentar o padrão de vida.",
             opcoes=["aporte", "limite do cartão", "número de parcelas", "cheque especial"], correta=0,
             explicacao="Assim o patrimônio cresce junto com a renda."),
    ]),
    dict(id="lf_metas", unidade="uf_patrimonio", titulo="Metas financeiras", icone="🎯", aula="af_metas", exercicios=[
        dict(tipo="escolha", pergunta="Qual destas é uma meta financeira bem definida?",
             opcoes=["Quero ficar rico", "Quero R$ 6.000 para viajar em 12 meses", "Quero gastar menos", "Quero investir algum dia"], correta=1,
             explicacao="Meta boa tem valor e prazo. Assim dá para saber quanto guardar por mês."),
        dict(tipo="escolha", pergunta="Caso (sem juros): R$ 6.000 em 12 meses. Quanto guardar por mês?",
             opcoes=["R$ 400", "R$ 500", "R$ 600", "R$ 1.200"], correta=1,
             explicacao="6.000 ÷ 12 = 500 por mês."),
        dict(tipo="pares", pergunta="Ligue cada prazo ao seu exemplo.",
             pares=[("Curto prazo", "Viagem no fim do ano"), ("Médio prazo", "Entrada de um carro em 3 anos"), ("Longo prazo", "Aposentadoria")],
             explicacao="O prazo da meta ajuda a escolher onde guardar o dinheiro."),
        dict(tipo="vf", pergunta="Para uma meta de curto prazo, o dinheiro deve ficar em algo mais seguro.", correta=True,
             explicacao="Com pouco tempo, não dá para esperar uma eventual queda passar."),
        dict(tipo="vf", pergunta="O melhor investimento para qualquer meta é o que rendeu mais no último mês.", correta=False,
             explicacao="Escolha pelo prazo e pelo risco da meta, não pelo rendimento recente."),
    ]),
    dict(id="lf_plano", unidade="uf_patrimonio", titulo="Planejamento financeiro", icone="🧭", aula="af_plano", exercicios=[
        dict(tipo="completar", pergunta="Patrimônio líquido é tudo o que você tem ___ tudo o que você deve.",
             opcoes=["menos", "mais", "vezes", "dividido por"], correta=0,
             explicacao="Ativos − dívidas = patrimônio líquido. É o melhor termômetro do progresso."),
        dict(tipo="escolha", pergunta="Caso: você tem R$ 15.000 em investimentos e um carro de R$ 30.000, e deve R$ 20.000. Qual é o seu patrimônio líquido?",
             opcoes=["R$ 45.000", "R$ 25.000", "R$ 65.000", "R$ 5.000"], correta=1,
             explicacao="15.000 + 30.000 − 20.000 = 25.000."),
        dict(tipo="ordenar", pergunta="Coloque na ordem o ciclo do planejamento.",
             itens=["Saber onde você está", "Decidir aonde quer chegar", "Montar o caminho", "Revisar periodicamente"],
             explicacao="Diagnóstico, metas, plano e revisão: o ciclo se repete conforme a vida muda."),
        dict(tipo="vf", pergunta="O plano financeiro deve ser revisado quando a vida muda, como num novo emprego ou com a chegada de filhos.", correta=True,
             explicacao="Mudanças de renda e de família mudam as metas e as prioridades."),
        dict(tipo="escolha", pergunta="Qual item também faz parte de um bom planejamento?",
             opcoes=["Proteção contra riscos que podem derrubar tudo", "Usar todo o limite do cartão", "Ter só um objetivo para sempre", "Evitar olhar os números"], correta=0,
             explicacao="Doença ou perda de renda podem desfazer anos de esforço. Reserva e, quando fizer sentido, seguros protegem o plano."),
    ]),
]

# Cada modo de leitura mostra a aula inteira: o intermediário é o texto do iniciante mais um trecho "Para ir além".
for _a in AULAS:
    if _a.get("intermediario"):
        _a["intermediario"] = _a["iniciante"] + "\n\n**Para ir além:** " + _a["intermediario"]
