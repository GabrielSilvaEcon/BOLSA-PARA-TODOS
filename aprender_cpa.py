"""Aprender · CERTIFICAÇÕES · CPA (fase 5) — SÓ DADOS. Formato das lições em jornada_conteudo.py; aulas como em edu_conteudo.py.

Conteúdo de ESTUDO para a CPA (ANBIMA, antiga CPA-10), organizado pelos grandes temas do programa público da certificação:
sistema financeiro, ética e regulação, economia e finanças, princípios de investimento, produtos e fundos, e tributação.
Sem vínculo com a ANBIMA: o programa oficial vigente, o formato da prova e a nota de corte ficam no site da ANBIMA.
Regras de impostos e de garantia mudam: valores e alíquotas valem para a data de revisão (edu_conteudo.REVISAO).
"""
from __future__ import annotations

AREA = "certificacoes"
CERT = "cpa"

UNIDADES = [
    dict(id="ucpa_sfn", area=AREA, cert=CERT, titulo="Sistema financeiro e regulação", icone="🏛️", icone_svg="predio", cor="#4DA3FF",
         descricao="Órgãos do SFN, autorregulação e o papel de cada instituição.",
         licoes=["lcpa_sfn", "lcpa_auto"]),
    dict(id="ucpa_etica", area=AREA, cert=CERT, titulo="Ética, suitability e PLD", icone="⚖️", icone_svg="balanca", cor="#B07CFF",
         descricao="Conduta, análise de perfil do investidor e prevenção à lavagem de dinheiro.",
         licoes=["lcpa_etica", "lcpa_suitability", "lcpa_pld"]),
    dict(id="ucpa_economia", area=AREA, cert=CERT, titulo="Economia e finanças", icone="📈", icone_svg="grafico", cor="#2DD4A0",
         descricao="Indicadores econômicos, política monetária e matemática financeira.",
         licoes=["lcpa_indicadores", "lcpa_matematica"]),
    dict(id="ucpa_produtos", area=AREA, cert=CERT, titulo="Investimentos, fundos e tributação", icone="🧾", icone_svg="cofre", cor="#F7C84A",
         descricao="Risco e retorno, produtos de renda fixa e variável, fundos e impostos.",
         licoes=["lcpa_risco", "lcpa_produtos", "lcpa_fundos", "lcpa_tributacao"]),
]

NIVEIS = {"lcpa_pld": "intermediario", "lcpa_matematica": "intermediario", "lcpa_fundos": "intermediario", "lcpa_tributacao": "intermediario"}

_A = dict(dificuldade="iniciante", fontes=["anbima", "cvm", "bcb"], relacionadas=[])
AULAS = [
    dict(_A, id="acpa_sfn", assunto="fundamentos", titulo="O Sistema Financeiro Nacional", min=6,
         iniciante="O **Sistema Financeiro Nacional (SFN)** organiza quem dá as regras, quem fiscaliza e quem opera no mercado.\n\n"
                   "**Órgãos normativos (fazem as regras):** o **CMN** (Conselho Monetário Nacional) é o órgão máximo: define as diretrizes da moeda e do crédito "
                   "e a **meta de inflação**. Para seguros, há o CNSP; para previdência fechada, o CNPC.\n\n"
                   "**Supervisores (fiscalizam):** o **Banco Central** fiscaliza bancos e instituições financeiras e executa a política monetária; a **CVM** "
                   "fiscaliza o mercado de capitais (ações, fundos, debêntures); a **Susep**, seguros e previdência aberta; a **Previc**, os fundos de pensão.\n\n"
                   "**Operadores:** bancos, corretoras, distribuidoras, bolsas (B3) e outras instituições que atendem os clientes.\n\n"
                   "**Na prática:** na prova, é comum perguntar \"quem regula o quê\". Associe cada mercado ao seu supervisor.",
         intermediario="O **Copom**, comitê do Banco Central, define a meta da **Selic** para buscar a meta de inflação fixada pelo CMN. A CVM também disciplina "
                       "a oferta pública de valores mobiliários e a atuação de administradores e gestores de fundos."),
    dict(_A, id="acpa_auto", assunto="fundamentos", titulo="Autorregulação e o papel da ANBIMA", min=4,
         iniciante="Além das leis e das normas dos órgãos públicos, o mercado tem a **autorregulação**: regras que as próprias instituições criam e se "
                   "comprometem a seguir.\n\n"
                   "A **ANBIMA** reúne instituições do mercado e mantém **códigos de autorregulação** (por exemplo, para distribuição de produtos e para "
                   "fundos). Quem adere precisa cumprir, e há supervisão e punições previstas.\n\n"
                   "**As certificações** (como a CPA) fazem parte disso: elas atestam que o profissional tem o conhecimento mínimo para atender investidores.\n\n"
                   "**Na prática:** autorregulação complementa a regulação oficial; ela não substitui a CVM nem o Banco Central.",
         intermediario="A autorregulação busca elevar padrões de transparência e de conduta além do mínimo legal. O descumprimento dos códigos pode levar a "
                       "advertências, multas e até exclusão da instituição aderente, conforme as regras da própria associação."),
    dict(_A, id="acpa_etica", assunto="fundamentos", titulo="Ética e conduta no atendimento", min=4,
         iniciante="O profissional que atende investidores deve agir com **ética, transparência e diligência**, colocando o interesse do cliente em primeiro lugar.\n\n"
                   "**Princípios importantes:** não prometer rentabilidade; informar riscos e custos; guardar **sigilo** das informações do cliente; evitar e "
                   "informar **conflitos de interesse**; e não usar **informação privilegiada**.\n\n"
                   "**Exemplo do dia a dia:** dizer ao cliente que um fundo \"não tem como perder\" é uma conduta inadequada.\n\n"
                   "**Na prática:** na dúvida, a resposta certa na prova costuma ser a que protege o cliente e a transparência.",
         intermediario="Usar informação relevante ainda não divulgada ao mercado para negociar (**insider trading**) é crime. Conflitos de interesse, como "
                       "receber remuneração maior por um produto, devem ser informados de forma clara ao cliente."),
    dict(_A, id="acpa_suitability", assunto="fundamentos", titulo="Suitability: perfil do investidor", min=5, fontes=["cvm", "anbima"],
         iniciante="**Suitability** é o dever de verificar se o produto **é adequado ao perfil** do cliente antes de recomendá-lo. A regra está nas normas da "
                   "CVM e nos códigos da ANBIMA.\n\n"
                   "**O que se avalia:** os **objetivos** do cliente (prazo, finalidade), a **situação financeira** (renda, patrimônio, necessidade de liquidez) e o "
                   "**conhecimento e experiência** com investimentos.\n\n"
                   "**Resultado:** um perfil (por exemplo conservador, moderado ou arrojado). Os produtos também recebem uma classificação de risco.\n\n"
                   "**Na prática:** se o cliente quiser um produto acima do perfil, a instituição deve **alertá-lo** e obter uma declaração dele antes de seguir.",
         intermediario="O perfil deve ser **atualizado periodicamente** e sempre que houver mudança relevante. Sem perfil atualizado, a recomendação fica "
                       "comprometida. Há dispensas previstas nas normas (por exemplo, para alguns investidores profissionais): confira as regras vigentes."),
    dict(_A, id="acpa_pld", assunto="fundamentos", titulo="Prevenção à lavagem de dinheiro", min=5, fontes=["bcb", "cvm"],
         iniciante="**Lavagem de dinheiro** é dar aparência legal a dinheiro de origem criminosa. É crime previsto na **Lei 9.613/1998**.\n\n"
                   "**As três etapas:** **colocação** (o dinheiro entra no sistema, muitas vezes em pequenos valores), **ocultação** (operações para esconder a "
                   "origem) e **integração** (o dinheiro volta à economia como se fosse legal).\n\n"
                   "**O que as instituições fazem:** conhecem o cliente (**KYC**), monitoram operações atípicas e **comunicam ao COAF** as situações suspeitas.\n\n"
                   "**Na prática:** o cliente **não deve ser avisado** de que foi comunicado ao COAF.",
         intermediario="O **COAF** é a unidade de inteligência financeira do país. Operações sem fundamento econômico, fracionamento para fugir de limites e "
                       "incompatibilidade entre patrimônio e movimentação são sinais de alerta típicos."),
    dict(_A, id="acpa_indicadores", assunto="inflacao", titulo="Indicadores econômicos e política monetária", min=5, fontes=["bcb"],
         iniciante="**Indicadores importantes:**\n\n"
                   "**PIB:** a soma da produção do país. **IPCA:** a inflação oficial, medida pelo IBGE e usada no regime de metas. **Selic:** a taxa básica de "
                   "juros, com a meta definida pelo Copom. **CDI:** a taxa dos empréstimos entre bancos, próxima da Selic. **Câmbio:** o preço das moedas estrangeiras.\n\n"
                   "**Política monetária:** para conter a inflação, o Banco Central **eleva os juros**; para estimular a economia, pode reduzi-los.\n\n"
                   "**Na prática:** juros altos tendem a valorizar a renda fixa pós-fixada e a pressionar as ações e os títulos prefixados.",
         intermediario="**Regime de metas de inflação:** o CMN fixa a meta e o intervalo de tolerância; o Banco Central persegue a meta usando principalmente "
                       "a Selic. Política **fiscal** é a do governo (gastos e impostos); política **monetária** é a do Banco Central (juros e liquidez)."),
    dict(_A, id="acpa_matematica", assunto="juros", titulo="Matemática financeira básica", min=6,
         iniciante="**Juros simples:** os juros incidem só sobre o valor inicial. **Juros compostos:** os juros incidem sobre o valor inicial **e** sobre os juros "
                   "já acumulados (\"juros sobre juros\"). Investimentos usam juros compostos.\n\n"
                   "**Taxa nominal × real:** a taxa real desconta a inflação: (1 + nominal) ÷ (1 + inflação) − 1.\n\n"
                   "**Exemplo (hipotético):** R$ 1.000 a 10% ao ano por 2 anos. Simples: R$ 1.200. Compostos: 1.000 × 1,1 × 1,1 = R$ 1.210.\n\n"
                   "**Na prática:** na prova, leia com atenção se a taxa é simples ou composta, e se é ao mês ou ao ano.",
         intermediario="**Taxas equivalentes** (compostas): 1% ao mês não é 12% ao ano, e sim (1,01)^12 − 1 ≈ 12,68% ao ano. **Taxas proporcionais** valem para "
                       "juros simples. Ganho real só existe quando a rentabilidade supera a inflação do período."),
    dict(_A, id="acpa_risco", assunto="riscos", titulo="Princípios de investimento: risco e retorno", min=5,
         iniciante="Todo investimento tem **risco**. Os principais tipos:\n\n"
                   "**Risco de mercado:** o preço oscila (juros, câmbio, bolsa). **Risco de crédito:** o emissor não paga. **Risco de liquidez:** não conseguir "
                   "vender rápido sem perda.\n\n"
                   "**Retorno e risco andam juntos:** quem quer mais retorno precisa aceitar mais risco. **Diversificar** reduz o risco específico de cada "
                   "ativo, mas não elimina o risco de mercado (sistemático).\n\n"
                   "**Na prática:** a prova costuma pedir o tipo de risco de uma situação descrita.",
         intermediario="**Volatilidade** (desvio padrão) mede o quanto o retorno oscila. **Risco sistemático** atinge todo o mercado; **não sistemático** é próprio "
                       "de uma empresa ou setor e pode ser reduzido com diversificação. Títulos prefixados longos têm mais risco de mercado que os curtos."),
    dict(_A, id="acpa_produtos", assunto="renda_fixa", titulo="Produtos de renda fixa e variável", min=6, fontes=["anbima", "tesouro", "b3"],
         iniciante="**Renda fixa:** títulos públicos (Tesouro Selic, Prefixado, IPCA+), **CDB**, **LCI/LCA**, **debêntures**, **CRI/CRA** e a poupança.\n\n"
                   "**Garantia do FGC:** cobre CDB, LCI, LCA, poupança e alguns outros, até **R$ 250 mil por CPF por instituição** (com teto global), segundo "
                   "a regra vigente na revisão. **Debêntures, CRI e CRA não têm FGC.**\n\n"
                   "**Renda variável:** **ações** (ON dão voto; PN têm preferência nos dividendos), **FIIs** e **ETFs**. Ações remuneram com valorização, dividendos e "
                   "juros sobre capital próprio.\n\n"
                   "**Na prática:** associe cada produto ao emissor, ao risco e à garantia.",
         intermediario="Títulos públicos têm o menor risco de crédito do país. **Debêntures incentivadas** (de infraestrutura) têm isenção de IR para pessoa "
                       "física, como LCI e LCA. Na poupança, a remuneração segue regras próprias ligadas à Selic e à TR."),
    dict(_A, id="acpa_fundos", assunto="fundos", titulo="Fundos de investimento", min=6, fontes=["cvm", "anbima"],
         iniciante="Um **fundo** reúne o dinheiro de vários investidores, que compram **cotas**. Um **gestor** decide os investimentos e um **administrador** "
                   "cuida da parte legal e operacional. Os fundos seguem as regras da **CVM**.\n\n"
                   "**Custos:** **taxa de administração** (anual, sobre o patrimônio) e, em alguns, **taxa de performance** (sobre o que superar um referencial).\n\n"
                   "**Classes comuns:** **renda fixa**, **ações**, **multimercado** e **cambial**. Cada uma tem uma política de investimento descrita no regulamento.\n\n"
                   "**Na prática:** o valor da cota muda todo dia; o investidor ganha ou perde conforme a cota varia. Fundos **não têm FGC**.",
         intermediario="**Cota de abertura** × **de fechamento**: define com qual valor a aplicação ou o resgate é calculado. Fundos abertos permitem resgate "
                       "pelas regras do regulamento; fundos fechados não, e as cotas podem ser negociadas em bolsa. Leia a lâmina e o regulamento antes de investir."),
    dict(_A, id="acpa_tributacao", assunto="tributacao", titulo="Tributação dos investimentos", min=6, fontes=["receita"],
         iniciante="**Renda fixa e fundos (tabela regressiva de IR, para pessoa física, na revisão):** até 180 dias, **22,5%**; de 181 a 360 dias, **20%**; de 361 a "
                   "720 dias, **17,5%**; acima de 720 dias, **15%**. O imposto incide sobre o **rendimento**.\n\n"
                   "**IOF:** cobrado em resgates com **menos de 30 dias**, de forma regressiva.\n\n"
                   "**Isenções (pessoa física):** poupança, LCI, LCA, CRI, CRA e debêntures incentivadas.\n\n"
                   "**Come-cotas:** nos fundos abertos, há antecipação do IR em **maio e novembro** (15% nos de longo prazo; 20% nos de curto prazo).\n\n"
                   "**Ações:** 15% sobre o ganho em operações comuns e 20% no day trade; há **isenção** para vendas de até **R$ 20 mil por mês** em operações comuns.",
         intermediario="Fundos de ações não têm come-cotas e pagam 15% no resgate. Prejuízos em ações podem ser compensados com lucros futuros da mesma "
                       "modalidade. As regras tributárias mudam: confira sempre a legislação vigente na Receita Federal e no programa oficial da prova."),
]

def _ex(tipo, pergunta, explicacao, **kw):
    return dict(tipo=tipo, pergunta=pergunta, explicacao=explicacao, **kw)


LICOES = [
    dict(id="lcpa_sfn", unidade="ucpa_sfn", titulo="Sistema Financeiro Nacional", icone="🏛️", aula="acpa_sfn", exercicios=[
        _ex("pares", "Ligue cada órgão do SFN à sua função principal.", "Associe cada mercado ao seu supervisor: é tema frequente de prova.",
            pares=[("CMN", "Órgão normativo máximo; fixa a meta de inflação"), ("Banco Central", "Fiscaliza bancos e executa a política monetária"),
                   ("CVM", "Fiscaliza o mercado de capitais"), ("Susep", "Fiscaliza seguros e previdência aberta")]),
        _ex("escolha", "Quem define a meta para a taxa Selic?", "O Copom é o comitê do Banco Central que define a meta da Selic.",
            opcoes=["O CMN", "O Copom", "A CVM", "A B3"], correta=1),
        _ex("escolha", "Uma oferta pública de ações é fiscalizada por qual órgão?", "Ações e outros valores mobiliários são supervisionados pela CVM.",
            opcoes=["Susep", "Previc", "CVM", "Receita Federal"], correta=2),
        _ex("vf", "O CMN é um órgão normativo, e não um fiscalizador do dia a dia das instituições.", "O CMN faz as regras; Banco Central e CVM fiscalizam.", correta=True),
        _ex("completar", "Os fundos de pensão (previdência fechada) são supervisionados pela ___.", "A Previc supervisiona as entidades fechadas de previdência.",
            opcoes=["Previc", "Susep", "CVM", "ANBIMA"], correta=0),
    ]),
    dict(id="lcpa_auto", unidade="ucpa_sfn", titulo="Autorregulação", icone="📜", aula="acpa_auto", exercicios=[
        _ex("escolha", "O que é autorregulação?", "São regras criadas pelas próprias instituições, que se comprometem a cumpri-las.",
            opcoes=["Leis aprovadas pelo Congresso", "Regras criadas pelas próprias instituições do mercado", "Normas do Banco Central", "Impostos sobre investimentos"], correta=1),
        _ex("vf", "A autorregulação substitui a fiscalização da CVM e do Banco Central.", "Ela complementa a regulação oficial; não a substitui.", correta=False),
        _ex("escolha", "Qual é a função das certificações como a CPA?", "Elas atestam o conhecimento mínimo para atender investidores.",
            opcoes=["Garantir rentabilidade aos clientes", "Atestar o conhecimento do profissional", "Substituir o suitability", "Isentar o profissional de regras"], correta=1),
        _ex("completar", "A ANBIMA mantém ___ de autorregulação que as instituições aderentes devem cumprir.", "Os códigos trazem regras e punições previstas.",
            opcoes=["códigos", "impostos", "fundos", "taxas Selic"], correta=0),
        _ex("vf", "O descumprimento dos códigos de autorregulação pode gerar punições à instituição aderente.", "Há advertências, multas e até exclusão.", correta=True),
    ]),
    dict(id="lcpa_etica", unidade="ucpa_etica", titulo="Ética e conduta", icone="🤝", aula="acpa_etica", exercicios=[
        _ex("escolha", "Um profissional diz ao cliente que um fundo \"não tem como perder\". Essa conduta é:", "Prometer resultado é inadequado: todo investimento tem risco.",
            opcoes=["Adequada, se o fundo for bom", "Inadequada, porque promete resultado", "Obrigatória", "Recomendada pela ANBIMA"], correta=1),
        _ex("pares", "Ligue cada princípio de conduta ao seu exemplo.", "A resposta certa costuma ser a que protege o cliente.",
            pares=[("Sigilo", "Não divulgar dados do cliente"), ("Transparência", "Informar riscos e custos"), ("Conflito de interesse", "Informar se ganha mais com um produto")]),
        _ex("completar", "Negociar com informação relevante ainda não divulgada ao mercado é o ___ trading.", "Insider trading é crime.",
            opcoes=["insider", "day", "swing", "home"], correta=0),
        _ex("vf", "Conflitos de interesse devem ser informados ao cliente de forma clara.", "A transparência protege o cliente e o profissional.", correta=True),
        _ex("escolha", "Qual atitude mostra diligência no atendimento?", "Diligência é cuidado e atenção ao interesse do cliente.",
            opcoes=["Indicar o produto que paga mais comissão", "Entender o objetivo do cliente antes de recomendar", "Recomendar o mesmo produto a todos", "Não explicar os riscos para não assustar"], correta=1),
    ]),
    dict(id="lcpa_suitability", unidade="ucpa_etica", titulo="Suitability", icone="🧭", aula="acpa_suitability", exercicios=[
        _ex("escolha", "O que é suitability?", "É o dever de recomendar produtos adequados ao perfil do cliente.",
            opcoes=["Um tipo de fundo", "Verificar se o produto é adequado ao perfil do cliente", "Uma taxa cobrada no resgate", "Um imposto"], correta=1),
        _ex("pares", "Ligue cada item da análise de perfil ao que ele avalia.", "Os três juntos formam o perfil do investidor.",
            pares=[("Objetivos", "Prazo e finalidade do investimento"), ("Situação financeira", "Renda, patrimônio e liquidez"), ("Conhecimento", "Experiência com investimentos")]),
        _ex("escolha", "O cliente conservador quer um produto de risco alto. O que a instituição deve fazer?",
            "Ela deve alertar sobre o desenquadramento e obter a declaração do cliente antes de seguir.",
            opcoes=["Recusar sempre, sem explicar", "Alertar o cliente e obter a declaração dele", "Mudar o perfil sem perguntar", "Aplicar sem avisar"], correta=1),
        _ex("vf", "O perfil do investidor, uma vez definido, nunca precisa ser atualizado.", "Ele deve ser atualizado periodicamente e quando a vida do cliente mudar.", correta=False),
        _ex("completar", "As regras de suitability estão nas normas da ___ e nos códigos da ANBIMA.", "A CVM disciplina o dever de verificar a adequação.",
            opcoes=["CVM", "Susep", "Receita Federal", "B3"], correta=0),
    ]),
    dict(id="lcpa_pld", unidade="ucpa_etica", titulo="Prevenção à lavagem de dinheiro", icone="🧺", aula="acpa_pld", exercicios=[
        _ex("ordenar", "Coloque as etapas da lavagem de dinheiro na ordem.", "Colocação, ocultação e integração.",
            itens=["Colocação", "Ocultação", "Integração"]),
        _ex("escolha", "A quem as instituições comunicam operações suspeitas de lavagem de dinheiro?", "O COAF é a unidade de inteligência financeira do país.",
            opcoes=["Ao próprio cliente", "Ao COAF", "À B3", "À ANBIMA"], correta=1),
        _ex("vf", "O cliente deve ser avisado de que foi comunicado ao COAF.", "Não: o cliente não deve ser informado da comunicação.", correta=False),
        _ex("pares", "Ligue cada etapa ao que acontece nela.", "Cada etapa afasta o dinheiro da sua origem.",
            pares=[("Colocação", "O dinheiro entra no sistema"), ("Ocultação", "Operações para esconder a origem"), ("Integração", "O dinheiro volta como se fosse legal")]),
        _ex("escolha", "Qual destas situações é um sinal de alerta?", "Movimentação incompatível com o patrimônio é típico sinal de alerta.",
            opcoes=["Cliente aplica todo mês o mesmo valor do salário", "Movimentação muito acima do patrimônio declarado", "Cliente atualiza o cadastro", "Cliente pede o informe de rendimentos"], correta=1),
    ]),
    dict(id="lcpa_indicadores", unidade="ucpa_economia", titulo="Indicadores e política monetária", icone="📊", aula="acpa_indicadores", exercicios=[
        _ex("pares", "Ligue cada indicador ao que ele mede.", "Indicadores aparecem muito na prova.",
            pares=[("IPCA", "Inflação oficial"), ("PIB", "Produção do país"), ("Selic", "Taxa básica de juros"), ("CDI", "Juros entre bancos")]),
        _ex("escolha", "Para conter a inflação, o Banco Central costuma:", "Juros mais altos encarecem o crédito e desaceleram os preços.",
            opcoes=["Reduzir a Selic", "Elevar a Selic", "Imprimir dinheiro", "Reduzir os impostos"], correta=1),
        _ex("completar", "No regime de metas, quem fixa a meta de inflação é o ___.", "O CMN fixa a meta; o Banco Central a persegue.",
            opcoes=["CMN", "Copom", "IBGE", "Tesouro"], correta=0),
        _ex("pares", "Ligue cada política ao responsável.", "Fiscal é do governo; monetária é do Banco Central.",
            pares=[("Política fiscal", "Governo (gastos e impostos)"), ("Política monetária", "Banco Central (juros e liquidez)")]),
        _ex("vf", "Uma alta da Selic tende a favorecer os investimentos pós-fixados.", "Pós-fixados passam a render mais com juros maiores.", correta=True),
    ]),
    dict(id="lcpa_matematica", unidade="ucpa_economia", titulo="Matemática financeira", icone="🧮", aula="acpa_matematica", exercicios=[
        _ex("escolha", "Caso: R$ 1.000 a 10% ao ano, juros compostos, por 2 anos. Qual o montante?", "1.000 × 1,1 × 1,1 = 1.210.",
            opcoes=["R$ 1.200", "R$ 1.210", "R$ 1.100", "R$ 1.020"], correta=1),
        _ex("escolha", "Caso: R$ 1.000 a 10% ao ano, juros simples, por 2 anos. Qual o montante?", "1.000 + 2 × 100 = 1.200.",
            opcoes=["R$ 1.200", "R$ 1.210", "R$ 1.100", "R$ 2.000"], correta=0),
        _ex("escolha", "Caso: uma aplicação rendeu 8% num ano com inflação de 4%. Qual a taxa real, aproximadamente?",
            "(1,08 ÷ 1,04) − 1 ≈ 3,85%.", opcoes=["4%", "3,85%", "12%", "2%"], correta=1),
        _ex("vf", "Em juros compostos, 1% ao mês equivale a exatamente 12% ao ano.", "Equivale a (1,01)^12 − 1 ≈ 12,68% ao ano.", correta=False),
        _ex("completar", "Juros compostos incidem sobre o valor inicial e sobre os juros já ___.", "É o famoso \"juros sobre juros\".",
            opcoes=["acumulados", "pagos ao governo", "isentos", "resgatados"], correta=0),
    ]),
    dict(id="lcpa_risco", unidade="ucpa_produtos", titulo="Risco e retorno", icone="🎯", aula="acpa_risco", exercicios=[
        _ex("pares", "Ligue cada risco ao seu significado.", "A prova costuma pedir o tipo de risco de uma situação.",
            pares=[("Risco de mercado", "O preço oscila"), ("Risco de crédito", "O emissor não paga"), ("Risco de liquidez", "Não conseguir vender rápido sem perda")]),
        _ex("escolha", "Um banco emissor de CDB quebra e não honra o título. Que risco é esse?", "É o risco de o emissor não pagar.",
            opcoes=["Risco de mercado", "Risco de crédito", "Risco de liquidez", "Risco cambial"], correta=1),
        _ex("vf", "A diversificação elimina o risco sistemático (de mercado).", "Ela reduz o risco específico, mas não elimina o de mercado.", correta=False),
        _ex("completar", "A ___ (desvio padrão) mede o quanto o retorno de um ativo oscila.", "Quanto maior, mais o retorno varia.",
            opcoes=["volatilidade", "liquidez", "duration", "alíquota"], correta=0),
        _ex("escolha", "Qual título tende a ter mais risco de mercado?", "Prefixados longos oscilam mais com a variação dos juros.",
            opcoes=["Tesouro Selic", "Prefixado de prazo longo", "Prefixado de prazo curto", "Poupança"], correta=1),
    ]),
    dict(id="lcpa_produtos", unidade="ucpa_produtos", titulo="Produtos de investimento", icone="🏦", aula="acpa_produtos", exercicios=[
        _ex("escolha", "Qual destes produtos NÃO tem a garantia do FGC?", "Debêntures não têm FGC; o risco é da empresa emissora.",
            opcoes=["CDB", "LCI", "Debênture", "Poupança"], correta=2),
        _ex("completar", "O FGC garante até R$ ___ mil por CPF por instituição, pela regra vigente na revisão.", "Há também um teto global por CPF.",
            opcoes=["250", "100", "500", "1.000"], correta=0),
        _ex("pares", "Ligue cada tipo de ação ao seu direito principal.", "ON dão voto; PN têm preferência nos dividendos.",
            pares=[("Ordinária (ON)", "Direito a voto"), ("Preferencial (PN)", "Preferência no recebimento de dividendos")]),
        _ex("vf", "Títulos públicos federais têm o menor risco de crédito do país.", "Por isso são a referência de baixo risco de crédito.", correta=True),
        _ex("escolha", "Qual destes é um produto de renda variável?", "Ações oscilam com o mercado e não têm rendimento definido.",
            opcoes=["CDB", "LCA", "Ação", "Tesouro Selic"], correta=2),
    ]),
    dict(id="lcpa_fundos", unidade="ucpa_produtos", titulo="Fundos de investimento", icone="🗂️", aula="acpa_fundos", exercicios=[
        _ex("pares", "Ligue cada participante do fundo ao seu papel.", "Gestor decide os investimentos; administrador cuida da parte legal e operacional.",
            pares=[("Gestor", "Decide onde o fundo investe"), ("Administrador", "Cuida da parte legal e operacional"), ("Cotista", "Investidor que tem cotas")]),
        _ex("pares", "Ligue cada taxa à sua base de cobrança.", "A de administração é anual sobre o patrimônio; a de performance, sobre o que supera o referencial.",
            pares=[("Taxa de administração", "Sobre o patrimônio, ao ano"), ("Taxa de performance", "Sobre o que superar o referencial")]),
        _ex("vf", "Fundos de investimento têm a garantia do FGC.", "Fundos não têm FGC; o cotista assume os riscos da carteira.", correta=False),
        _ex("escolha", "Num fundo fechado, como o investidor costuma sair antes do fim do prazo?", "Não há resgate; as cotas podem ser vendidas em bolsa.",
            opcoes=["Pedindo resgate a qualquer momento", "Vendendo as cotas em bolsa", "Pelo FGC", "Não há como sair"], correta=1),
        _ex("completar", "Antes de investir, leia a ___ e o regulamento do fundo.", "A lâmina resume as informações essenciais do fundo.",
            opcoes=["lâmina", "fatura", "nota fiscal", "declaração do IR"], correta=0),
    ]),
    dict(id="lcpa_tributacao", unidade="ucpa_produtos", titulo="Tributação", icone="🧾", aula="acpa_tributacao", exercicios=[
        _ex("pares", "Ligue cada prazo à alíquota da tabela regressiva de IR (renda fixa, pessoa física, na revisão).", "Quanto mais tempo, menor a alíquota.",
            pares=[("Até 180 dias", "22,5%"), ("181 a 360 dias", "20%"), ("361 a 720 dias", "17,5%"), ("Acima de 720 dias", "15%")]),
        _ex("escolha", "Em quais meses acontece o come-cotas nos fundos abertos?", "A antecipação do IR ocorre em maio e novembro.",
            opcoes=["Janeiro e julho", "Maio e novembro", "Todo mês", "Só no resgate"], correta=1),
        _ex("escolha", "Qual destes é isento de IR para pessoa física?", "LCI e LCA são isentas para pessoa física.",
            opcoes=["CDB", "LCI", "Fundo de renda fixa", "Tesouro Prefixado"], correta=1),
        _ex("completar", "O IOF incide em resgates feitos com menos de ___ dias.", "O IOF é regressivo e zera a partir do 30º dia.",
            opcoes=["30", "180", "360", "720"], correta=0),
        _ex("vf", "Vendas de ações de até R$ 20 mil por mês, em operações comuns, são isentas de IR para pessoa física.", "A isenção não vale para day trade.", correta=True),
    ]),
]

for _a in AULAS:
    if _a.get("intermediario"):
        _a["intermediario"] = _a["iniciante"] + "\n\n**Para ir além:** " + _a["intermediario"]
