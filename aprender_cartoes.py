"""Aprender · área CARTÕES E MILHAS (fase 2) — SÓ DADOS. Formato das lições em jornada_conteudo.py; aulas como em edu_conteudo.py.

Três trilhas: introdução aos cartões, pontos e milhas, e como usar bem (valor da milha, passagens, cashback, benefícios).
Números de exemplo são HIPOTÉTICOS e dizem isso. Regras de programas mudam: o texto ensina a conferir o regulamento de cada um,
sem recomendar cartão, banco ou programa específico.
"""
from __future__ import annotations

AREA = "cartoes"

UNIDADES = [
    dict(id="uc_intro", area=AREA, titulo="Introdução aos cartões", icone="💳", icone_svg="cofre", cor="#FF8A3D",
         descricao="Como funcionam, como escolher, anuidade e benefícios.",
         licoes=["lc_funciona", "lc_escolher", "lc_anuidade"]),
    dict(id="uc_pontos", area=AREA, titulo="Pontos e milhas", icone="✈️", icone_svg="grafico", cor="#4DA3FF",
         descricao="Programas de pontos, como acumular e transferências bonificadas.",
         licoes=["lc_programas", "lc_acumular", "lc_bonificadas"]),
    dict(id="uc_uso", area=AREA, titulo="Usando bem", icone="🧳", icone_svg="alvo", cor="#2DD4A0",
         descricao="Valor da milha, passagens, cashback e benefícios sem gastar à toa.",
         licoes=["lc_valor_milha", "lc_passagens", "lc_cashback", "lc_beneficios"]),
]

NIVEIS = {"lc_bonificadas": "intermediario", "lc_valor_milha": "intermediario", "lc_passagens": "intermediario"}

_A = dict(assunto="fundamentos", dificuldade="iniciante", fontes=["bcb"], relacionadas=[])
AULAS = [
    dict(_A, id="ac_funciona", titulo="Como funciona o cartão de crédito", min=4,
         iniciante="No cartão de crédito, o banco paga a compra para a loja e você paga o banco depois, de uma vez só, na **fatura**. Se você paga tudo até o "
                   "vencimento, não há juros. É por isso que o cartão pode ser uma ferramenta útil ou uma armadilha.\n\n"
                   "**Débito × crédito:** no débito o dinheiro sai da conta na hora; no crédito, sai só no vencimento da fatura.\n\n"
                   "**Exemplo do dia a dia:** usar o crédito para concentrar as contas do mês e pagar tudo no vencimento ajuda a organizar e, às vezes, gera pontos.\n\n"
                   "**Na prática:** o cartão só vale a pena para quem paga a fatura inteira, sempre.",
         intermediario="As vantagens do cartão (prazo, pontos, cashback, seguros) só compensam se a fatura é paga integralmente. Um único mês no rotativo costuma "
                       "custar mais do que um ano inteiro de pontos ou cashback."),
    dict(_A, id="ac_escolher", titulo="Como escolher um cartão", min=4,
         iniciante="O melhor cartão é o que combina com **o seu jeito de gastar**, não o mais famoso.\n\n"
                   "**Perguntas que ajudam:** tem anuidade? Quanto eu gasto por mês? Eu viajo? Prefiro dinheiro de volta (cashback) ou pontos? O app é bom?\n\n"
                   "**Exemplo (hipotético):** quem gasta R$ 800 por mês e não viaja costuma ganhar mais com um cartão sem anuidade e com cashback do que com um "
                   "cartão de pontos com anuidade alta.\n\n"
                   "**Na prática:** compare a anuidade com o que você realmente ganharia de benefício em um ano.",
         intermediario="Faça a conta anual: (benefícios que você de fato usaria) − (anuidade e tarifas). Benefício que você não usa não conta. Muitos bancos "
                       "isentam a anuidade com um gasto mínimo mensal ou com investimento na própria instituição: confira as condições."),
    dict(_A, id="ac_anuidade", titulo="Anuidade e benefícios", min=4,
         iniciante="**Anuidade** é a tarifa anual do cartão, normalmente cobrada em parcelas mensais na fatura. Cartões com mais benefícios costumam ter anuidade maior.\n\n"
                   "**Benefícios comuns:** pontos por compra, salas VIP em aeroportos, seguros de viagem, proteção de compra e garantia estendida.\n\n"
                   "**Exemplo (hipotético):** anuidade de R$ 600 por ano para ter sala VIP. Quem viaja duas vezes por ano talvez não aproveite o suficiente.\n\n"
                   "**Na prática:** peça isenção ou desconto da anuidade ao banco. Muitas vezes eles aceitam negociar.",
         intermediario="Leia o regulamento dos benefícios: seguros e garantias têm regras (como pagar a passagem com o próprio cartão). Benefício sem "
                       "condições conhecidas pode não valer na hora em que você precisar."),
    dict(_A, id="ac_programas", titulo="Programas de pontos e de milhas", min=5,
         iniciante="Existem dois tipos de programa:\n\n"
                   "**Programas de pontos dos bancos:** o cartão gera pontos por cada dólar ou real gasto. Esses pontos podem ser trocados por produtos ou "
                   "**transferidos** para programas de companhias aéreas.\n\n"
                   "**Programas de milhas das companhias aéreas:** as milhas são usadas para emitir passagens.\n\n"
                   "**Exemplo (hipotético):** um cartão que dá 2 pontos por dólar, com o dólar a R$ 5, gera 400 pontos num gasto de R$ 1.000 (1.000 ÷ 5 × 2).\n\n"
                   "**Na prática:** pontos e milhas **vencem**. Confira o prazo de validade no regulamento.",
         intermediario="A conversão \"pontos por dólar\" depende da cotação usada pelo banco. Pontos de banco geralmente são mais flexíveis (podem ir para vários "
                       "programas); milhas de companhia aérea são mais específicas. Transferir só quando for usar reduz o risco de vencimento e de mudança de regras."),
    dict(_A, id="ac_acumular", titulo="Como acumular milhas", min=4,
         iniciante="As formas mais comuns de acumular são: **gastos no cartão**, **compras em lojas parceiras** (que dão pontos extras por real gasto), "
                   "**voos** e **clubes de assinatura** dos programas.\n\n"
                   "**Exemplo (hipotético):** uma loja parceira dá 5 pontos por real. Uma compra de R$ 200 que você já ia fazer rende 1.000 pontos.\n\n"
                   "**Na prática:** concentre os gastos que você **já faria** no cartão. Gastar mais só para ganhar pontos é prejuízo.",
         intermediario="Pontos por compra em lojas parceiras só valem se o preço for o mesmo de outras lojas. Clubes de assinatura compensam apenas para quem já "
                       "vai usar as milhas: faça a conta de quanto você paga por milheiro."),
    dict(_A, id="ac_bonificadas", titulo="Transferências bonificadas", min=4,
         iniciante="Às vezes, os programas de companhias aéreas oferecem **bônus** para quem transfere pontos do banco: por exemplo, 100% de bônus.\n\n"
                   "**Exemplo (hipotético):** com 100% de bônus, 10.000 pontos do banco viram 20.000 milhas. Com 50%, viram 15.000.\n\n"
                   "**Na prática:** quem não tem pressa costuma esperar uma promoção de bônus para transferir. Mas leia as regras: às vezes o bônus é maior "
                   "só para quem assina o clube do programa.",
         intermediario="Bônus maior não compensa se as milhas vencerem antes de você usar, ou se o programa de destino tiver passagens caras em milhas. "
                       "Calcule o custo final do milheiro e compare com o preço das passagens em dinheiro."),
    dict(_A, id="ac_valor_milha", titulo="Quanto vale uma milha", min=5,
         iniciante="Para saber se vale a pena usar milhas, calcule **quanto você economiza por milha**.\n\n"
                   "**Conta:** (preço da passagem em dinheiro − taxas pagas na emissão com milhas) ÷ milhas usadas. Multiplicando por 1.000, você tem o valor do "
                   "**milheiro** (1.000 milhas).\n\n"
                   "**Exemplo (hipotético):** passagem de R$ 800, ou 30.000 milhas + R$ 50 de taxas. (800 − 50) ÷ 30.000 = R$ 0,025 por milha, ou "
                   "**R$ 25 o milheiro**.\n\n"
                   "**Na prática:** compare esse valor com o que as milhas custaram para você. Se o resgate vale menos do que custou, pague em dinheiro.",
         intermediario="O valor do milheiro varia muito entre rotas, datas e programas. Use o cálculo para escolher a melhor forma de pagar em cada emissão, e "
                       "não uma regra fixa. Milhas paradas não rendem e podem desvalorizar quando o programa muda a tabela."),
    dict(_A, id="ac_passagens", titulo="Passagens com milhas", min=4,
         iniciante="Emitir passagens com milhas é como comprar com outra moeda. **Dicas:** pesquise com antecedência, tenha datas flexíveis e compare o preço em "
                   "milhas com o preço em dinheiro.\n\n"
                   "**Taxas:** mesmo com milhas, você paga taxas de embarque e, às vezes, outras taxas.\n\n"
                   "**Exemplo do dia a dia:** a mesma rota pode custar 10.000 milhas numa terça e 40.000 num feriado.\n\n"
                   "**Na prática:** confira as regras de cancelamento e de remarcação antes de emitir.",
         intermediario="Use a conta do valor do milheiro para decidir. Muitos programas permitem combinar milhas e dinheiro. Emissões em parceiros (outras "
                       "companhias) podem render mais por milha, mas têm regras próprias."),
    dict(_A, id="ac_cashback", titulo="Cashback", min=4,
         iniciante="**Cashback** é dinheiro de volta: uma porcentagem do que você gasta volta para você, como crédito ou dinheiro na conta.\n\n"
                   "**Exemplo (hipotético):** 1% de cashback em R$ 2.000 de gastos no mês devolve R$ 20. Em um ano, R$ 240.\n\n"
                   "**Cashback × milhas:** cashback é simples e serve para tudo; milhas podem valer mais, mas só para quem viaja e sabe usar.\n\n"
                   "**Na prática:** para quem não viaja, cashback costuma ser a escolha mais simples.",
         intermediario="Compare o cashback anual com o valor que as milhas teriam para você (usando o valor do milheiro dos seus resgates reais). Descontado da "
                       "anuidade, o cartão sem anuidade e com cashback costuma ganhar para quem gasta pouco."),
    dict(_A, id="ac_beneficios", titulo="Benefícios sem gastar à toa", min=4,
         iniciante="Pontos, milhas e cashback são **descontos sobre o que você já gastaria**. Eles nunca compensam um gasto que você não faria.\n\n"
                   "**Armadilhas comuns:** gastar mais para bater a meta de isenção da anuidade, parcelar para \"ganhar pontos\" e pagar juros que custam mais do "
                   "que os pontos.\n\n"
                   "**Exemplo (hipotético):** gastar R$ 500 a mais para ganhar R$ 10 em pontos é perder R$ 490.\n\n"
                   "**Na prática:** primeiro o orçamento, depois os pontos. A fatura paga inteira vem antes de qualquer benefício.",
         intermediario="O melhor uso de benefícios é **passivo**: concentrar no cartão os gastos que já existem (contas, mercado) e pagar a fatura inteira. "
                       "Benefício que exige mudar o consumo para pior raramente compensa."),
]

LICOES = [
    # -------- Introdução aos cartões
    dict(id="lc_funciona", unidade="uc_intro", titulo="Como funciona o cartão", icone="💳", aula="ac_funciona", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada forma de pagamento ao momento em que o dinheiro sai.",
             pares=[("Débito", "Na hora da compra"), ("Crédito", "No vencimento da fatura"), ("Crédito parcelado", "Em várias faturas")],
             explicacao="No crédito, o banco paga a loja e você paga o banco depois."),
        dict(tipo="vf", pergunta="O cartão de crédito só vale a pena para quem paga a fatura inteira.", correta=True,
             explicacao="Pontos e cashback não compensam os juros do rotativo."),
        dict(tipo="escolha", pergunta="Um mês no rotativo comparado a um ano de pontos e cashback costuma ser:",
             opcoes=["Mais barato", "Mais caro", "Igual", "Sem relação"], correta=1,
             explicacao="Os juros do rotativo costumam superar, com folga, o valor dos benefícios do ano."),
        dict(tipo="escolha", pergunta="Qual é uma boa forma de usar o cartão?",
             opcoes=["Concentrar as contas do mês e pagar tudo no vencimento", "Pagar sempre o mínimo", "Usar como renda extra", "Emprestar para amigos"], correta=0,
             explicacao="Concentrar os gastos que já existem e pagar tudo ajuda a organizar e pode gerar benefícios."),
        dict(tipo="completar", pergunta="No crédito, o banco paga a loja agora e você paga o banco na ___.",
             opcoes=["fatura", "loja", "conta poupança", "maquininha"], correta=0,
             explicacao="A fatura reúne as compras do período e tem uma data de vencimento."),
    ]),
    dict(id="lc_escolher", unidade="uc_intro", titulo="Como escolher um cartão", icone="🔍", aula="ac_escolher", exercicios=[
        dict(tipo="escolha", pergunta="Qual é o melhor cartão?",
             opcoes=["O mais famoso", "O que combina com o seu jeito de gastar", "O de anuidade mais cara", "O com mais propaganda"], correta=1,
             explicacao="O cartão ideal depende de quanto você gasta, se viaja e se prefere cashback ou pontos."),
        dict(tipo="escolha", pergunta="Caso: você gasta R$ 800 por mês e não viaja. Qual tende a ser melhor?",
             opcoes=["Cartão de pontos com anuidade alta", "Cartão sem anuidade com cashback", "Ter cinco cartões", "Usar só o cheque especial"], correta=1,
             explicacao="Com gasto baixo e sem viagens, os benefícios de um cartão caro raramente pagam a anuidade."),
        dict(tipo="vf", pergunta="Benefício que você não usa deve entrar na conta de quanto o cartão vale.", correta=False,
             explicacao="Só conta o que você de fato usaria."),
        dict(tipo="completar", pergunta="A conta anual do cartão é: benefícios que você usaria ___ anuidade e tarifas.",
             opcoes=["menos", "mais", "vezes", "dividido pela"], correta=0,
             explicacao="Se o resultado é negativo, o cartão custa mais do que devolve."),
        dict(tipo="vf", pergunta="Alguns bancos isentam a anuidade com gasto mínimo ou investimento na instituição.", correta=True,
             explicacao="Confira as condições antes de escolher, e não gaste mais só para ganhar a isenção."),
    ]),
    dict(id="lc_anuidade", unidade="uc_intro", titulo="Anuidade e benefícios", icone="🎟️", aula="ac_anuidade", exercicios=[
        dict(tipo="completar", pergunta="___ é a tarifa anual do cartão, normalmente cobrada em parcelas na fatura.",
             opcoes=["Anuidade", "Cashback", "Rotativo", "IOF"], correta=0,
             explicacao="Cartões com mais benefícios costumam ter anuidade maior."),
        dict(tipo="pares", pergunta="Ligue o benefício à sua descrição.",
             pares=[("Sala VIP", "Espaço de espera em aeroportos"), ("Garantia estendida", "Mais tempo de garantia no produto"), ("Seguro viagem", "Cobertura em viagens")],
             explicacao="Cada benefício tem regras próprias no regulamento."),
        dict(tipo="escolha", pergunta="Caso: anuidade de R$ 600 por ano para ter sala VIP, e você viaja duas vezes por ano. O que fazer?",
             opcoes=["Assinar sem pensar", "Comparar o valor que você usaria com os R$ 600", "Viajar mais só para usar", "Ignorar a anuidade"], correta=1,
             explicacao="Faça a conta: se o uso vale menos que a anuidade, o cartão não compensa para você."),
        dict(tipo="vf", pergunta="É possível pedir ao banco isenção ou desconto da anuidade.", correta=True,
             explicacao="Muitas vezes o banco aceita negociar, principalmente para bons pagadores."),
        dict(tipo="vf", pergunta="Benefícios como seguros funcionam em qualquer situação, sem regras.", correta=False,
             explicacao="Costumam exigir condições, como pagar a passagem com o próprio cartão. Leia o regulamento."),
    ]),
    # -------- Pontos e milhas
    dict(id="lc_programas", unidade="uc_pontos", titulo="Programas de pontos", icone="⭐", aula="ac_programas", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada programa ao seu uso principal.",
             pares=[("Pontos do banco", "Trocar por produtos ou transferir"), ("Milhas da companhia aérea", "Emitir passagens")],
             explicacao="Pontos de banco são mais flexíveis; milhas de companhia aérea são mais específicas."),
        dict(tipo="escolha", pergunta="Caso: 2 pontos por dólar, dólar a R$ 5. Quantos pontos rende um gasto de R$ 1.000?",
             opcoes=["200", "400", "2.000", "5.000"], correta=1,
             explicacao="1.000 ÷ 5 = 200 dólares; 200 × 2 = 400 pontos."),
        dict(tipo="vf", pergunta="Pontos e milhas podem vencer.", correta=True,
             explicacao="Confira a validade no regulamento e planeje o uso."),
        dict(tipo="escolha", pergunta="Quando transferir os pontos do banco para uma companhia aérea?",
             opcoes=["Assim que ganhar", "Quando for usar, de preferência com bônus", "Nunca", "Só no fim do ano"], correta=1,
             explicacao="Transferir perto do uso reduz o risco de vencimento e de mudança nas regras do programa."),
        dict(tipo="completar", pergunta="A conversão \"pontos por dólar\" depende da ___ usada pelo banco.",
             opcoes=["cotação do dólar", "taxa Selic", "inflação", "data de vencimento"], correta=0,
             explicacao="O gasto em reais é convertido em dólares pela cotação que o banco usa."),
    ]),
    dict(id="lc_acumular", unidade="uc_pontos", titulo="Como acumular milhas", icone="🧲", aula="ac_acumular", exercicios=[
        dict(tipo="escolha", pergunta="Qual destas NÃO é uma boa forma de acumular milhas?",
             opcoes=["Concentrar no cartão os gastos que já faria", "Comprar em parceiros pelo mesmo preço", "Gastar mais só para ganhar pontos", "Voar com a companhia do programa"], correta=2,
             explicacao="Gastar mais só para ganhar pontos é prejuízo: o ponto vale muito menos que o gasto."),
        dict(tipo="escolha", pergunta="Caso: loja parceira com 5 pontos por real, numa compra de R$ 200 que você já faria. Quantos pontos?",
             opcoes=["200", "500", "1.000", "40"], correta=2,
             explicacao="200 × 5 = 1.000 pontos."),
        dict(tipo="vf", pergunta="Comprar em loja parceira só vale a pena se o preço for o mesmo de outras lojas.", correta=True,
             explicacao="Se o produto estiver mais caro, os pontos podem não cobrir a diferença."),
        dict(tipo="vf", pergunta="Clube de assinatura de milhas compensa para qualquer pessoa.", correta=False,
             explicacao="Só compensa para quem vai usar as milhas. Calcule quanto você paga por milheiro."),
        dict(tipo="pares", pergunta="Ligue a forma de acumular ao exemplo.",
             pares=[("Cartão", "Pagar o mercado no crédito"), ("Parceiros", "Comprar na loja que dá pontos extras"), ("Voos", "Viajar com a companhia do programa")],
             explicacao="O ideal é acumular com o que você já faria."),
    ]),
    dict(id="lc_bonificadas", unidade="uc_pontos", titulo="Transferências bonificadas", icone="🎁", aula="ac_bonificadas", exercicios=[
        dict(tipo="escolha", pergunta="Caso: 10.000 pontos transferidos com 100% de bônus viram quantas milhas?",
             opcoes=["10.000", "15.000", "20.000", "100.000"], correta=2,
             explicacao="100% de bônus dobra: 10.000 + 10.000 = 20.000."),
        dict(tipo="escolha", pergunta="Caso: 10.000 pontos com 50% de bônus viram quantas milhas?",
             opcoes=["10.500", "15.000", "20.000", "5.000"], correta=1,
             explicacao="50% de 10.000 = 5.000; total de 15.000 milhas."),
        dict(tipo="vf", pergunta="Às vezes o bônus maior é só para quem assina o clube do programa.", correta=True,
             explicacao="Leia as regras da promoção antes de transferir."),
        dict(tipo="vf", pergunta="Bônus alto sempre compensa, mesmo que as milhas vençam antes do uso.", correta=False,
             explicacao="Milha vencida vale zero. O bônus só ajuda se você usar as milhas."),
        dict(tipo="completar", pergunta="Quem não tem pressa costuma esperar uma promoção de ___ para transferir.",
             opcoes=["bônus", "anuidade", "juros", "parcelamento"], correta=0,
             explicacao="A promoção aumenta as milhas recebidas pelos mesmos pontos."),
    ]),
    # -------- Usando bem
    dict(id="lc_valor_milha", unidade="uc_uso", titulo="Quanto vale uma milha", icone="🧮", aula="ac_valor_milha", exercicios=[
        dict(tipo="escolha", pergunta="Caso: passagem de R$ 800, ou 30.000 milhas + R$ 50 de taxas. Quanto vale o milheiro nesse resgate?",
             opcoes=["R$ 25", "R$ 26,67", "R$ 30", "R$ 15"], correta=0,
             explicacao="(800 − 50) ÷ 30.000 × 1.000 = 25. Cada mil milhas economizaram R$ 25."),
        dict(tipo="completar", pergunta="Milheiro é o valor de ___ milhas.",
             opcoes=["1.000", "100", "10.000", "1"], correta=0,
             explicacao="Falar em milheiro facilita comparar resgates e compras de milhas."),
        dict(tipo="escolha", pergunta="Se o resgate vale menos por milheiro do que as milhas custaram para você, o melhor é:",
             opcoes=["Usar as milhas mesmo assim", "Pagar a passagem em dinheiro", "Comprar mais milhas", "Desistir de viajar"], correta=1,
             explicacao="Guarde as milhas para um resgate que valha mais."),
        dict(tipo="vf", pergunta="O valor do milheiro é sempre o mesmo, em qualquer rota e data.", correta=False,
             explicacao="Varia muito com a rota, a data e o programa. Calcule a cada emissão."),
        dict(tipo="ordenar", pergunta="Coloque na ordem o cálculo do valor do milheiro.",
             itens=["Ver o preço da passagem em dinheiro", "Subtrair as taxas da emissão com milhas", "Dividir pelas milhas usadas", "Multiplicar por 1.000"],
             explicacao="(preço − taxas) ÷ milhas × 1.000 = valor do milheiro."),
    ]),
    dict(id="lc_passagens", unidade="uc_uso", titulo="Passagens com milhas", icone="🛫", aula="ac_passagens", exercicios=[
        dict(tipo="escolha", pergunta="O que costuma baratear uma passagem em milhas?",
             opcoes=["Datas flexíveis e antecedência", "Comprar na véspera de feriado", "Escolher sempre o voo mais cheio", "Não comparar preços"], correta=0,
             explicacao="A mesma rota pode custar muito menos fora de feriados e com antecedência."),
        dict(tipo="vf", pergunta="Mesmo emitindo com milhas, você pode pagar taxas, como a de embarque.", correta=True,
             explicacao="Inclua as taxas na conta do valor da milha."),
        dict(tipo="escolha", pergunta="Caso: a rota custa 10.000 milhas na terça e 40.000 no feriado. Quantas vezes mais caro é o feriado?",
             opcoes=["2 vezes", "3 vezes", "4 vezes", "10 vezes"], correta=2,
             explicacao="40.000 ÷ 10.000 = 4."),
        dict(tipo="vf", pergunta="É importante conferir as regras de cancelamento e remarcação antes de emitir.", correta=True,
             explicacao="Mudanças podem ter custo em milhas ou dinheiro."),
        dict(tipo="completar", pergunta="Muitos programas permitem combinar milhas e ___ na mesma emissão.",
             opcoes=["dinheiro", "cashback", "anuidade", "pontos de outro país"], correta=0,
             explicacao="Combinar pode ajudar quando faltam poucas milhas."),
    ]),
    dict(id="lc_cashback", unidade="uc_uso", titulo="Cashback", icone="💸", aula="ac_cashback", exercicios=[
        dict(tipo="completar", pergunta="Cashback é ___ de volta.",
             opcoes=["dinheiro", "milha", "anuidade", "limite"], correta=0,
             explicacao="Uma porcentagem do gasto volta como crédito ou dinheiro."),
        dict(tipo="escolha", pergunta="Caso: 1% de cashback sobre R$ 2.000 por mês. Quanto volta em um ano?",
             opcoes=["R$ 20", "R$ 120", "R$ 240", "R$ 2.400"], correta=2,
             explicacao="2.000 × 1% = 20 por mês; 20 × 12 = 240 por ano."),
        dict(tipo="pares", pergunta="Ligue o perfil à opção que costuma combinar mais.",
             pares=[("Não viaja e gasta pouco", "Cashback sem anuidade"), ("Viaja muito e sabe usar milhas", "Programa de pontos")],
             explicacao="Cashback é simples; milhas podem valer mais para quem viaja e calcula."),
        dict(tipo="vf", pergunta="Para comparar cashback com milhas, use o valor do milheiro dos seus resgates reais.", correta=True,
             explicacao="Assim a comparação é com o valor que você de fato obtém."),
        dict(tipo="vf", pergunta="Cashback sempre compensa uma anuidade alta.", correta=False,
             explicacao="Desconte a anuidade do cashback do ano para ver o ganho real."),
    ]),
    dict(id="lc_beneficios", unidade="uc_uso", titulo="Benefícios sem gastar à toa", icone="🧠", aula="ac_beneficios", exercicios=[
        dict(tipo="escolha", pergunta="Caso: gastar R$ 500 a mais para ganhar R$ 10 em pontos. O resultado é:",
             opcoes=["Lucro de R$ 10", "Perda de R$ 490", "Empate", "Lucro de R$ 500"], correta=1,
             explicacao="Benefício só compensa sobre o gasto que você já faria."),
        dict(tipo="vf", pergunta="Parcelar com juros para ganhar pontos costuma compensar.", correta=False,
             explicacao="Os juros custam mais do que os pontos valem."),
        dict(tipo="ordenar", pergunta="Coloque na ordem de prioridade.",
             itens=["Seguir o orçamento", "Pagar a fatura inteira", "Aproveitar pontos e cashback"],
             explicacao="Primeiro o orçamento, depois a fatura em dia; os benefícios vêm por último."),
        dict(tipo="escolha", pergunta="Qual é o melhor uso de benefícios do cartão?",
             opcoes=["Concentrar no cartão os gastos que já existem", "Gastar mais para bater metas", "Abrir vários cartões para ganhar bônus", "Atrasar a fatura"], correta=0,
             explicacao="O uso passivo, sem mudar o consumo, é o que realmente compensa."),
        dict(tipo="vf", pergunta="Gastar mais só para bater a meta de isenção de anuidade pode sair mais caro do que pagar a anuidade.", correta=True,
             explicacao="Compare o gasto extra com o valor da anuidade antes de decidir."),
    ]),
]

# Cada modo de leitura mostra a aula inteira: o intermediário é o texto do iniciante mais um trecho "Para ir além".
for _a in AULAS:
    if _a.get("intermediario"):
        _a["intermediario"] = _a["iniciante"] + "\n\n**Para ir além:** " + _a["intermediario"]
