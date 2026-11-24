"""Aprender · área INVESTIMENTOS (fase 3, complemento) — SÓ DADOS. Formato em jornada_conteudo.py; aulas como em edu_conteudo.py.

Duas trilhas novas que aprofundam o que já existia (sem repetir as lições atuais de renda fixa e de carteira):
renda fixa na prática (Tesouro Direto; CDB, LCI e LCA; CDI, Selic e IPCA) e gestão de carteira (rebalanceamento, aportes, objetivos).
Regras de imposto e de garantia mudam: o texto indica a revisão em edu_conteudo.REVISAO e remete às fontes oficiais.
Números são HIPOTÉTICOS; nada recomenda título, banco ou produto específico.
"""
from __future__ import annotations

AREA = "investimentos"

UNIDADES = [
    dict(id="ui_rf_pratica", area=AREA, titulo="Renda fixa na prática", icone="🏦", icone_svg="cofre", cor="#38D0E0",
         descricao="Tesouro Direto; CDB, LCI e LCA; CDI, Selic e IPCA.",
         licoes=["li_tesouro", "li_cdb_lci", "li_indexadores"]),
    dict(id="ui_gestao", area=AREA, titulo="Gestão de carteira", icone="🧭", icone_svg="escudo", cor="#B07CFF",
         descricao="Rebalanceamento, aportes com disciplina e carteira por objetivo.",
         licoes=["li_rebalancear", "li_aportes", "li_objetivos"]),
]

NIVEIS = {"li_indexadores": "intermediario", "li_rebalancear": "intermediario", "li_objetivos": "intermediario"}

_A = dict(dificuldade="iniciante", relacionadas=[])
AULAS = [
    dict(_A, id="ai_tesouro", assunto="renda_fixa", fontes=["tesouro"], titulo="Tesouro Direto", min=5,
         iniciante="No **Tesouro Direto** você empresta dinheiro para o governo federal e recebe juros. É considerado o investimento de **menor risco de "
                   "crédito** do país, e dá para começar com valores pequenos.\n\n"
                   "**Principais títulos:** **Tesouro Selic** (acompanha a Selic; bom para a reserva, porque oscila pouco), **Tesouro Prefixado** (taxa fixa "
                   "conhecida na compra) e **Tesouro IPCA+** (inflação mais uma taxa; protege o poder de compra no longo prazo). Há também títulos com objetivo, "
                   "como o **Renda+** (aposentadoria) e o **Educa+** (estudos).\n\n"
                   "**Exemplo do dia a dia:** a reserva de emergência costuma ficar no Tesouro Selic; uma meta para daqui a 15 anos combina mais com IPCA+.\n\n"
                   "**Na prática:** prefixados e IPCA+ oscilam antes do vencimento. Se vender antes, pode receber mais ou menos do que a taxa contratada.",
         intermediario="O título prefixado e o IPCA+ sofrem **marcação a mercado**: quando os juros sobem, o preço cai, e mais forte nos títulos longos. "
                       "Há taxa de custódia da B3 e Imposto de Renda regressivo sobre o rendimento. Confira as regras atualizadas no site do Tesouro Direto."),
    dict(_A, id="ai_cdb_lci", assunto="renda_fixa", fontes=["anbima", "bcb"], titulo="CDB, LCI e LCA", min=5,
         iniciante="São títulos emitidos por **bancos**: você empresta para o banco e recebe juros.\n\n"
                   "**CDB:** o dinheiro pode ir para qualquer atividade do banco. Tem **Imposto de Renda** sobre o rendimento.\n\n"
                   "**LCI e LCA:** o dinheiro financia o setor **imobiliário** (LCI) ou o **agronegócio** (LCA). Para pessoa física, são **isentas de IR**, mas "
                   "têm um prazo mínimo antes de poder sacar.\n\n"
                   "Os três têm a garantia do **FGC** até o limite vigente por CPF e por instituição.\n\n"
                   "**Exemplo (hipotético):** um CDB de 100% do CDI pode render menos, depois do IR, do que uma LCI de 90% do CDI.\n\n"
                   "**Na prática:** compare sempre o rendimento **líquido** (depois do imposto) e o prazo em que o dinheiro fica preso.",
         intermediario="Para comparar um título isento com um tributado, use a **taxa equivalente**: taxa isenta ÷ (1 − alíquota de IR). Ex. hipotético: "
                       "90% do CDI isento equivale a 90 ÷ (1 − 0,15) ≈ 106% do CDI num CDB com IR de 15%. Veja também a liquidez: CDBs de liquidez diária "
                       "costumam pagar menos que os de prazo fixo."),
    dict(_A, id="ai_indexadores", assunto="renda_fixa", fontes=["bcb", "tesouro"], titulo="CDI, Selic e IPCA", min=5,
         iniciante="Três siglas aparecem em quase todo investimento de renda fixa:\n\n"
                   "**Selic:** a taxa básica de juros da economia, definida pelo **Copom**, do Banco Central, a cada 45 dias mais ou menos.\n\n"
                   "**CDI:** a taxa dos empréstimos entre bancos. Anda muito perto da Selic e é a referência dos CDBs (\"100% do CDI\").\n\n"
                   "**IPCA:** a inflação oficial, medida pelo **IBGE**. Títulos \"IPCA+\" pagam a inflação mais uma taxa.\n\n"
                   "**Exemplo do dia a dia:** quando a Selic sobe, os pós-fixados passam a render mais; quando a inflação sobe, o IPCA+ protege o poder de compra.\n\n"
                   "**Na prática:** o que importa é o **retorno real**, ou seja, quanto o investimento rendeu acima da inflação.",
         intermediario="Retorno real ≈ (1 + nominal) ÷ (1 + inflação) − 1. Ex. hipotético: rendeu 11% com inflação de 5%: (1,11 ÷ 1,05) − 1 ≈ 5,7% reais. "
                       "Pós-fixados (CDI/Selic) ganham com juros em alta; prefixados ganham se os juros caírem depois da compra; IPCA+ protege da inflação."),
    dict(_A, id="ai_rebalancear", assunto="carteiras", fontes=["cvm"], titulo="Rebalanceamento", min=4,
         iniciante="Com o tempo, os investimentos rendem de forma diferente e a carteira sai dos **pesos** que você planejou. **Rebalancear** é voltar a esses pesos.\n\n"
                   "**Exemplo (hipotético):** você queria 70% em renda fixa e 30% em ações. As ações subiram e agora são 40%. Rebalancear é levar de volta para 30%.\n\n"
                   "**Jeito mais simples:** usar os **novos aportes** para comprar o que ficou abaixo do peso, sem precisar vender nada.\n\n"
                   "**Na prática:** escolha uma regra (por data, como a cada 6 meses, ou por desvio, como 5 pontos) e siga.",
         intermediario="Rebalancear obriga a vender o que subiu e comprar o que caiu, o contrário do impulso. Vender pode gerar **imposto** e custos: por isso "
                       "rebalancear com aportes costuma ser mais eficiente. Desvios pequenos não precisam de ajuste."),
    dict(_A, id="ai_aportes", assunto="carteiras", fontes=["cvm"], titulo="Aportes e disciplina", min=4,
         iniciante="**Aporte** é cada valor novo que você coloca nos investimentos. A constância vale mais do que acertar o melhor momento.\n\n"
                   "**Aportes regulares** (todo mês, por exemplo) fazem você comprar mais cotas quando o preço está baixo e menos quando está alto. Isso "
                   "reduz o peso de escolher o \"dia certo\".\n\n"
                   "**Exemplo (hipotético):** R$ 300 por mês compram 30 cotas a R$ 10 e 20 cotas a R$ 15. O preço médio fica em R$ 12 por cota.\n\n"
                   "**Na prática:** automatize o aporte para o dia do salário.",
         intermediario="Tentar acertar o momento perfeito costuma levar a ficar parado. Para quem recebe salário, aportar todo mês é a forma natural de "
                       "investir. O que mais pesa no resultado de longo prazo é a taxa de poupança e o tempo investido."),
    dict(_A, id="ai_objetivos", assunto="carteiras", fontes=["cvm", "anbima"], titulo="Carteira por objetivo", min=5,
         iniciante="Em vez de uma carteira única, muita gente separa o dinheiro **por objetivo**: reserva, viagem, casa, aposentadoria. Cada objetivo tem um "
                   "**prazo** e aceita um nível diferente de risco.\n\n"
                   "**Regra geral:** prazo curto pede segurança e liquidez; prazo longo permite mais risco em busca de retorno.\n\n"
                   "**Exemplo:** a reserva fica em algo com saque rápido; a aposentadoria pode ter ações e títulos IPCA+ longos.\n\n"
                   "**Na prática:** dê um nome a cada \"pote\" e acompanhe o progresso de cada um.",
         intermediario="Conforme o objetivo se aproxima, reduza o risco aos poucos, para uma queda perto da data não estragar o plano. Use o **perfil de "
                       "investidor** como limite e revise os objetivos quando a vida mudar."),
]

LICOES = [
    # -------- Renda fixa na prática
    dict(id="li_tesouro", unidade="ui_rf_pratica", titulo="Tesouro Direto", icone="🏛️", aula="ai_tesouro", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada título do Tesouro ao seu uso mais comum.",
             pares=[("Tesouro Selic", "Reserva de emergência"), ("Tesouro IPCA+", "Proteger o poder de compra no longo prazo"),
                    ("Tesouro Prefixado", "Taxa fixa conhecida na compra")],
             explicacao="Cada título combina com um tipo de objetivo e prazo."),
        dict(tipo="escolha", pergunta="No Tesouro Direto, você empresta dinheiro para:",
             opcoes=["Um banco", "O governo federal", "Uma empresa", "A B3"], correta=1,
             explicacao="Os títulos do Tesouro são dívida do governo federal."),
        dict(tipo="vf", pergunta="Vender um Tesouro IPCA+ antes do vencimento pode render mais ou menos do que a taxa contratada.", correta=True,
             explicacao="Por causa da marcação a mercado, o preço oscila antes do vencimento."),
        dict(tipo="escolha", pergunta="Para a reserva de emergência, qual título costuma ser mais indicado?",
             opcoes=["Tesouro IPCA+ com vencimento longo", "Tesouro Selic", "Tesouro Prefixado longo", "Qualquer um"], correta=1,
             explicacao="O Tesouro Selic oscila pouco e permite sacar com facilidade."),
        dict(tipo="completar", pergunta="O ___ é um título do Tesouro pensado para complementar a aposentadoria.",
             opcoes=["Renda+", "Educa+", "Selic", "CDB"], correta=0,
             explicacao="O Renda+ paga uma renda mensal por um período na aposentadoria; o Educa+ é para os estudos."),
    ]),
    dict(id="li_cdb_lci", unidade="ui_rf_pratica", titulo="CDB, LCI e LCA", icone="🏦", aula="ai_cdb_lci", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada título ao destino do dinheiro.",
             pares=[("CDB", "Atividades em geral do banco"), ("LCI", "Setor imobiliário"), ("LCA", "Agronegócio")],
             explicacao="LCI e LCA financiam setores específicos e, por isso, têm isenção de IR para pessoa física."),
        dict(tipo="vf", pergunta="Para pessoa física, LCI e LCA são isentas de Imposto de Renda.", correta=True,
             explicacao="A isenção vale para pessoa física, segundo as regras vigentes."),
        dict(tipo="escolha", pergunta="Caso: LCI de 90% do CDI isenta e CDB com IR de 15%. Qual % do CDI o CDB precisa pagar para empatar?",
             opcoes=["Cerca de 90%", "Cerca de 100%", "Cerca de 106%", "Cerca de 115%"], correta=2,
             explicacao="Taxa equivalente = 90 ÷ (1 − 0,15) ≈ 106% do CDI."),
        dict(tipo="completar", pergunta="CDB, LCI e LCA têm a garantia do ___ até o limite vigente por CPF e instituição.",
             opcoes=["FGC", "Copom", "IBGE", "Tesouro"], correta=0,
             explicacao="O Fundo Garantidor de Créditos protege até um limite, se o banco quebrar."),
        dict(tipo="vf", pergunta="Para comparar um título isento com um tributado, basta olhar a taxa bruta.", correta=False,
             explicacao="Compare o rendimento líquido, depois do imposto, e o prazo."),
    ]),
    dict(id="li_indexadores", unidade="ui_rf_pratica", titulo="CDI, Selic e IPCA", icone="📐", aula="ai_indexadores", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada sigla a quem a define ou mede.",
             pares=[("Selic", "Copom, do Banco Central"), ("IPCA", "IBGE"), ("CDI", "Empréstimos entre bancos")],
             explicacao="A Selic é decidida pelo Copom; o IPCA é medido pelo IBGE; o CDI vem do mercado entre bancos."),
        dict(tipo="vf", pergunta="O CDI costuma andar muito perto da Selic.", correta=True,
             explicacao="Por isso os pós-fixados que pagam % do CDI acompanham a Selic."),
        dict(tipo="escolha", pergunta="Caso: o investimento rendeu 11% e a inflação foi de 5%. Qual foi o retorno real, aproximadamente?",
             opcoes=["16%", "6%", "5,7%", "11%"], correta=2,
             explicacao="(1,11 ÷ 1,05) − 1 ≈ 5,7%. Subtrair direto (11 − 5 = 6%) é só uma aproximação."),
        dict(tipo="escolha", pergunta="Se os juros subirem depois da compra, qual tipo de título tende a se beneficiar?",
             opcoes=["Prefixado", "Pós-fixado (CDI/Selic)", "Nenhum", "Todos igualmente"], correta=1,
             explicacao="O pós-fixado passa a render mais quando os juros sobem; o prefixado perde valor de mercado."),
        dict(tipo="completar", pergunta="Retorno ___ é quanto o investimento rendeu acima da inflação.",
             opcoes=["real", "bruto", "nominal", "garantido"], correta=0,
             explicacao="É o retorno que mede o ganho de poder de compra."),
    ]),
    # -------- Gestão de carteira
    dict(id="li_rebalancear", unidade="ui_gestao", titulo="Rebalanceamento", icone="⚖️", aula="ai_rebalancear", exercicios=[
        dict(tipo="escolha", pergunta="Caso: o plano era 70% renda fixa e 30% ações, mas as ações subiram e viraram 40%. Rebalancear é:",
             opcoes=["Comprar mais ações", "Voltar as ações para perto de 30%", "Vender toda a renda fixa", "Não fazer nada nunca"], correta=1,
             explicacao="Rebalancear é voltar aos pesos que você planejou."),
        dict(tipo="vf", pergunta="Usar os novos aportes para comprar o que ficou abaixo do peso é uma forma de rebalancear sem vender.", correta=True,
             explicacao="Evita custos e impostos da venda."),
        dict(tipo="pares", pergunta="Ligue cada regra de rebalanceamento ao exemplo.",
             pares=[("Por data", "A cada 6 meses"), ("Por desvio", "Quando o peso se afastar 5 pontos do alvo")],
             explicacao="As duas funcionam; o importante é escolher uma e seguir."),
        dict(tipo="escolha", pergunta="Por que rebalancear é difícil emocionalmente?",
             opcoes=["Porque obriga a vender o que subiu e comprar o que caiu", "Porque é proibido", "Porque só dá prejuízo", "Porque exige muito dinheiro"], correta=0,
             explicacao="É o contrário do impulso, e por isso a regra ajuda."),
        dict(tipo="vf", pergunta="Qualquer desvio pequeno nos pesos exige ajuste imediato.", correta=False,
             explicacao="Desvios pequenos podem esperar; ajustar demais gera custos à toa."),
    ]),
    dict(id="li_aportes", unidade="ui_gestao", titulo="Aportes e disciplina", icone="🔁", aula="ai_aportes", exercicios=[
        dict(tipo="completar", pergunta="___ é cada valor novo que você coloca nos investimentos.",
             opcoes=["Aporte", "Resgate", "Dividendo", "Spread"], correta=0,
             explicacao="Aportes regulares fazem o patrimônio crescer."),
        dict(tipo="escolha", pergunta="Caso: R$ 300 compram 30 cotas a R$ 10 num mês e 20 cotas a R$ 15 no outro. Qual o preço médio?",
             opcoes=["R$ 12,50", "R$ 12", "R$ 10", "R$ 15"], correta=1,
             explicacao="Total investido R$ 600 ÷ 50 cotas = R$ 12 por cota."),
        dict(tipo="vf", pergunta="Esperar o momento perfeito para investir costuma levar a ficar parado.", correta=True,
             explicacao="Constância vale mais do que tentar acertar o dia certo."),
        dict(tipo="escolha", pergunta="O que mais pesa no resultado de longo prazo?",
             opcoes=["Acertar o dia exato de comprar", "A taxa de poupança e o tempo investido", "Trocar de investimento todo mês", "Seguir as notícias do dia"], correta=1,
             explicacao="Guardar mais e por mais tempo é o que mais faz diferença."),
        dict(tipo="vf", pergunta="Automatizar o aporte para o dia do salário ajuda a manter a disciplina.", correta=True,
             explicacao="O que é automático não depende de força de vontade."),
    ]),
    dict(id="li_objetivos", unidade="ui_gestao", titulo="Carteira por objetivo", icone="🎯", aula="ai_objetivos", exercicios=[
        dict(tipo="pares", pergunta="Ligue cada objetivo ao tipo de investimento que combina mais.",
             pares=[("Reserva de emergência", "Segurança e saque rápido"), ("Aposentadoria em 25 anos", "Pode ter mais risco em busca de retorno"),
                    ("Viagem em 8 meses", "Algo seguro com vencimento curto")],
             explicacao="O prazo e a necessidade de liquidez definem o risco aceitável."),
        dict(tipo="vf", pergunta="Prazo longo permite assumir mais risco do que prazo curto.", correta=True,
             explicacao="Com mais tempo, dá para esperar as oscilações passarem."),
        dict(tipo="escolha", pergunta="O que fazer quando um objetivo de longo prazo se aproxima da data?",
             opcoes=["Aumentar o risco", "Reduzir o risco aos poucos", "Sacar tudo de uma vez sem pensar", "Nada"], correta=1,
             explicacao="Assim uma queda perto da data não estraga o plano."),
        dict(tipo="completar", pergunta="O ___ de investidor funciona como um limite para o risco da carteira.",
             opcoes=["perfil", "extrato", "boleto", "limite do cartão"], correta=0,
             explicacao="Ele resume quanto risco você aceita e consegue suportar."),
        dict(tipo="vf", pergunta="Separar o dinheiro por objetivo ajuda a acompanhar o progresso de cada meta.", correta=True,
             explicacao="Cada pote com nome e prazo deixa claro quanto falta."),
    ]),
]

for _a in AULAS:
    if _a.get("intermediario"):
        _a["intermediario"] = _a["iniciante"] + "\n\n**Para ir além:** " + _a["intermediario"]
