"""Aprender · CERTIFICAÇÕES · C-Pro R (fase 5) — SÓ DADOS. Formato das lições em jornada_conteudo.py; aulas como em edu_conteudo.py.

Conteúdo de ESTUDO para a C-Pro R (ANBIMA, antiga CPA-20): aprofunda os temas da CPA para o atendimento do varejo de alta renda,
com estatística aplicada, renda fixa (precificação e duration), renda variável e derivativos, fundos e previdência.
Sem vínculo com a ANBIMA: confira o programa oficial vigente, o formato da prova e a nota de corte no site da ANBIMA.
Regras de impostos e normas mudam: valores valem para a data de revisão (edu_conteudo.REVISAO).
"""
from __future__ import annotations

AREA = "certificacoes"
CERT = "cpro_r"

UNIDADES = [
    dict(id="ucr_regra", area=AREA, cert=CERT, titulo="Regulação, perfil e PLD", icone="⚖️", icone_svg="balanca", cor="#B07CFF",
         descricao="Tipos de investidor, suitability aprofundado e prevenção à lavagem de dinheiro.",
         licoes=["lcr_investidores", "lcr_pld"]),
    dict(id="ucr_estat", area=AREA, cert=CERT, titulo="Estatística e risco", icone="📐", icone_svg="grafico", cor="#2DD4A0",
         descricao="Média, desvio padrão, correlação, Sharpe e diversificação.",
         licoes=["lcr_estatistica", "lcr_sharpe"]),
    dict(id="ucr_mercados", area=AREA, cert=CERT, titulo="Renda fixa, renda variável e derivativos", icone="📊", icone_svg="cofre", cor="#4DA3FF",
         descricao="Preço e duration, mercado primário e secundário, termo, futuro, opções e swap.",
         licoes=["lcr_rf_preco", "lcr_mercados_rv", "lcr_derivativos"]),
    dict(id="ucr_fundos", area=AREA, cert=CERT, titulo="Fundos, previdência e tributação", icone="🧾", icone_svg="escudo", cor="#F7C84A",
         descricao="Estrutura dos fundos, PGBL e VGBL e a tributação de cada produto.",
         licoes=["lcr_fundos", "lcr_previdencia", "lcr_tributos"]),
]

NIVEIS = {lid: "avancado" for lid in ("lcr_sharpe", "lcr_rf_preco", "lcr_derivativos")}
NIVEIS.update({lid: "intermediario" for lid in ("lcr_investidores", "lcr_pld", "lcr_estatistica", "lcr_mercados_rv", "lcr_fundos", "lcr_previdencia", "lcr_tributos")})

_A = dict(dificuldade="intermediario", fontes=["anbima", "cvm"], relacionadas=[])
AULAS = [
    dict(_A, id="acr_investidores", assunto="fundamentos", titulo="Tipos de investidor e suitability", min=5,
         iniciante="As normas da CVM separam os investidores em categorias, porque cada uma pode acessar produtos diferentes:\n\n"
                   "**Investidor de varejo:** a maioria das pessoas.\n"
                   "**Investidor qualificado:** quem tem mais de **R$ 1 milhão** em aplicações financeiras e atesta essa condição por escrito, entre outros casos "
                   "previstos (como alguns profissionais certificados).\n"
                   "**Investidor profissional:** quem tem mais de **R$ 10 milhões** em aplicações e atesta isso, além de instituições financeiras.\n\n"
                   "**Suitability:** o dever de verificar a adequação vale para todos, mas algumas regras têm dispensas para investidores profissionais.\n\n"
                   "**Na prática:** produtos mais complexos podem ser restritos a qualificados ou profissionais. Os valores podem mudar: confira as normas vigentes.",
         intermediario="O perfil considera objetivos, situação financeira e conhecimento. Se a carteira do cliente ficar desenquadrada do perfil, a instituição "
                       "deve alertar e registrar a ciência dele. A atualização do perfil tem prazo máximo definido nas normas."),
    dict(_A, id="acr_pld", assunto="fundamentos", titulo="PLD/FT: abordagem baseada em risco", min=5, fontes=["cvm", "bcb"],
         iniciante="A prevenção à lavagem de dinheiro e ao financiamento do terrorismo (**PLD/FT**) segue uma **abordagem baseada em risco**: clientes, produtos e "
                   "canais de maior risco recebem mais atenção.\n\n"
                   "**Pessoas Expostas Politicamente (PEP):** agentes públicos de alto cargo e pessoas próximas a eles. Exigem **diligência reforçada**.\n\n"
                   "**Cadastro e monitoramento:** conhecer o cliente (KYC), o beneficiário final e a origem dos recursos; monitorar operações atípicas.\n\n"
                   "**Comunicação:** situações suspeitas são comunicadas ao **COAF**, sem informar o cliente.\n\n"
                   "**Na prática:** a responsabilidade é da instituição e de cada profissional, que devem ser treinados.",
         intermediario="Sinais de alerta incluem operações incompatíveis com o patrimônio, uso de terceiros, recusa em informar a origem dos recursos e "
                       "fracionamento de operações. Os registros devem ser mantidos pelo prazo previsto nas normas."),
    dict(_A, id="acr_estatistica", assunto="indicadores", titulo="Estatística aplicada a investimentos", min=6,
         iniciante="**Média:** o retorno médio de um período. **Desvio padrão:** o quanto os retornos se espalham em torno da média; é a medida usual de "
                   "**volatilidade** (risco). **Variância:** o desvio padrão ao quadrado.\n\n"
                   "**Correlação:** mede como dois ativos se movem juntos, de **−1** (opostos) a **+1** (juntos). Quanto **menor** a correlação, **maior** o "
                   "benefício da diversificação.\n\n"
                   "**Exemplo (hipotético):** dois ativos com correlação −1 podem, combinados, reduzir bastante a oscilação da carteira.\n\n"
                   "**Na prática:** na distribuição normal, cerca de 68% dos resultados ficam a 1 desvio padrão da média e cerca de 95% a 2 desvios.",
         intermediario="**Covariância** indica a direção do movimento conjunto; a correlação é a covariância padronizada. O risco de uma carteira depende dos "
                       "pesos, dos desvios padrão e das correlações entre os ativos, e não só da média dos riscos individuais."),
    dict(_A, id="acr_sharpe", assunto="riscos", titulo="Índice de Sharpe e diversificação", min=5,
         iniciante="O **Índice de Sharpe** mede o **retorno por unidade de risco**:\n\n"
                   "**Sharpe = (retorno da carteira − taxa livre de risco) ÷ desvio padrão da carteira.**\n\n"
                   "**Exemplo (hipotético):** retorno de 14%, taxa livre de risco de 10% e desvio padrão de 8%: (14 − 10) ÷ 8 = **0,5**.\n\n"
                   "**Quanto maior o Sharpe, melhor** a relação entre retorno e risco. Um Sharpe negativo indica retorno abaixo da taxa livre de risco.\n\n"
                   "**Risco sistemático × não sistemático:** a diversificação reduz o risco específico (não sistemático), mas não o de mercado (sistemático).",
         intermediario="O Sharpe usa o **risco total** (desvio padrão). Quando a carteira já é diversificada, o índice de **Treynor** usa o **beta** (risco "
                       "sistemático) no denominador. Compare Sharpe entre carteiras no mesmo período e com a mesma taxa livre de risco."),
    dict(_A, id="acr_rf_preco", assunto="renda_fixa", titulo="Renda fixa: preço, taxa e duration", min=6, fontes=["anbima", "tesouro"],
         iniciante="O **preço** de um título de renda fixa é o **valor presente** dos fluxos que ele vai pagar, descontados pela taxa de mercado.\n\n"
                   "**Relação inversa:** quando a **taxa de mercado sobe**, o **preço cai**; quando a taxa cai, o preço sobe. É a **marcação a mercado**.\n\n"
                   "**Duration:** o prazo médio ponderado dos fluxos do título. Num título **sem cupom** (zero cupom), a duration é igual ao **prazo**. Títulos com "
                   "cupom têm duration **menor** que o prazo.\n\n"
                   "**Na prática:** quanto **maior a duration**, **maior a sensibilidade** do preço à variação dos juros.",
         intermediario="**Duration modificada** = duration de Macaulay ÷ (1 + taxa). A variação percentual aproximada do preço é **−duration modificada × "
                       "variação da taxa**. Ex. hipotético: duration modificada de 4 e alta de 1 ponto na taxa ≈ queda de 4% no preço. A **convexidade** corrige essa aproximação."),
    dict(_A, id="acr_mercados_rv", assunto="acoes", titulo="Mercado primário, secundário e renda variável", min=5, fontes=["b3", "cvm"],
         iniciante="**Mercado primário:** a empresa **emite** títulos ou ações e recebe o dinheiro (por exemplo, num **IPO**, a primeira oferta pública de ações).\n\n"
                   "**Mercado secundário:** os investidores negociam **entre si** os títulos já emitidos, na bolsa ou no balcão. A empresa não recebe esse dinheiro.\n\n"
                   "**Proventos:** dividendos (isentos de IR para pessoa física, pela regra vigente na revisão), juros sobre capital próprio (com IR retido na "
                   "fonte), bonificação e direito de subscrição.\n\n"
                   "**Na prática:** o mercado secundário dá **liquidez**; sem ele, quem compra no primário teria dificuldade para vender.",
         intermediario="**Desdobramento (split)** aumenta a quantidade de ações e reduz o preço proporcionalmente, sem mudar o valor total. **Grupamento** faz o "
                       "inverso. Oferta **primária** traz dinheiro novo para a empresa; oferta **secundária** é a venda de ações por acionistas existentes."),
    dict(_A, id="acr_derivativos", assunto="riscos", titulo="Derivativos: termo, futuro, opções e swap", min=6, fontes=["b3"],
         iniciante="**Derivativos** têm o valor ligado a outro ativo (o \"ativo-objeto\"). Servem para **proteção (hedge)**, **especulação** e **arbitragem**.\n\n"
                   "**Termo:** compra ou venda para uma data futura, a um preço combinado; em geral, liquida no vencimento.\n"
                   "**Futuro:** parecido com o termo, mas **padronizado** e com **ajuste diário** das posições.\n"
                   "**Opções:** dão um **direito**. A **opção de compra (call)** dá o direito de comprar; a **opção de venda (put)**, o de vender. O **titular** paga "
                   "um **prêmio**; o **lançador** recebe o prêmio e assume a **obrigação**.\n"
                   "**Swap:** troca de rentabilidades (por exemplo, prefixado por CDI) entre duas partes.\n\n"
                   "**Na prática:** quem tem dólar a pagar no futuro pode comprar dólar futuro para se proteger da alta.",
         intermediario="O risco do titular de uma opção é limitado ao prêmio pago; o do lançador descoberto pode ser muito maior. No mercado futuro, o **ajuste "
                       "diário** e a **margem de garantia** reduzem o risco de crédito entre as partes, com a B3 atuando como contraparte central."),
    dict(_A, id="acr_fundos", assunto="fundos", titulo="Estrutura dos fundos de investimento", min=5, fontes=["cvm", "anbima"],
         iniciante="Os fundos seguem as regras da **CVM**. Pela regulação atual, um fundo pode ter **classes** de cotas (com políticas de investimento próprias) "
                   "e **subclasses**.\n\n"
                   "**Prestadores essenciais:** o **administrador** (parte legal, operacional e fiscalização) e o **gestor** (decisões de investimento).\n\n"
                   "**Documentos:** o **regulamento** (regras do fundo), a **lâmina** (resumo das informações essenciais) e os informes periódicos.\n\n"
                   "**Assembleia de cotistas:** decide temas importantes, como mudanças relevantes no regulamento.\n\n"
                   "**Na prática:** fundos podem prever responsabilidade **limitada** dos cotistas, conforme o regulamento.",
         intermediario="**Condomínio aberto** permite resgates; **fechado** não, e as cotas são negociadas em mercado. **Marcação a mercado** das cotas evita "
                       "transferência de riqueza entre cotistas que entram e saem. Fundos exclusivos e restritos atendem públicos específicos."),
    dict(_A, id="acr_previdencia", assunto="tributacao", titulo="Previdência complementar: PGBL e VGBL", min=6, fontes=["receita"],
         iniciante="**PGBL:** permite deduzir as contribuições da base do IR, até **12% da renda bruta tributável**, para quem faz a **declaração completa** e "
                   "contribui para a previdência oficial. No resgate, o IR incide sobre **o valor total**.\n\n"
                   "**VGBL:** não deduz; no resgate, o IR incide **apenas sobre os rendimentos**.\n\n"
                   "**Regimes de tributação:** **progressivo** (igual à tabela do IR, com retenção de 15% na fonte e ajuste na declaração) e **regressivo** (a "
                   "alíquota cai com o tempo de cada aporte: **35%** até 2 anos, caindo 5 pontos a cada 2 anos até **10%** acima de 10 anos).\n\n"
                   "**Na prática:** o regressivo favorece quem vai deixar o dinheiro por muito tempo.",
         intermediario="As fases são **acumulação** (contribuições) e **benefício** (renda ou resgate). A **portabilidade** entre planos não gera IR quando "
                       "feita entre planos do mesmo tipo. Na sucessão, os planos costumam não entrar no inventário, mas as regras podem mudar: confira a legislação."),
    dict(_A, id="acr_tributos", assunto="tributacao", titulo="Tributação por produto", min=6, fontes=["receita"],
         iniciante="**Renda fixa e fundos** (pessoa física, na revisão): tabela regressiva de 22,5% a 15%. **Come-cotas** em maio e novembro nos fundos abertos "
                   "(15% longo prazo; 20% curto prazo). **IOF** em resgates com menos de 30 dias.\n\n"
                   "**Ações:** 15% sobre o ganho em operações comuns e 20% no day trade. Há IR retido na fonte, o \"dedo-duro\": 0,005% sobre a venda em "
                   "operações comuns e 1% sobre o ganho no day trade. Vendas de até R$ 20 mil por mês em operações comuns são isentas.\n\n"
                   "**Fundos de ações:** 15% no resgate, sem come-cotas.\n\n"
                   "**Na prática:** o investidor recolhe o IR sobre ações por DARF até o último dia útil do mês seguinte.",
         intermediario="Prejuízos em operações comuns compensam lucros de operações comuns, e prejuízos de day trade compensam lucros de day trade. As regras "
                       "tributárias mudam com frequência: estude pelo programa oficial vigente e pela legislação da Receita Federal."),
]

def _ex(tipo, pergunta, explicacao, **kw):
    return dict(tipo=tipo, pergunta=pergunta, explicacao=explicacao, **kw)


LICOES = [
    dict(id="lcr_investidores", unidade="ucr_regra", titulo="Tipos de investidor", icone="🧑‍💼", aula="acr_investidores", exercicios=[
        _ex("pares", "Ligue cada categoria de investidor ao critério de aplicações financeiras (regra vigente na revisão).", "Além do valor, é preciso atestar a condição por escrito.",
            pares=[("Qualificado", "Mais de R$ 1 milhão"), ("Profissional", "Mais de R$ 10 milhões")]),
        _ex("escolha", "Por que existem categorias de investidor?", "Produtos mais complexos podem ser restritos a qualificados ou profissionais.",
            opcoes=["Para cobrar taxas diferentes", "Porque cada uma pode acessar produtos diferentes", "Para definir o imposto", "Para escolher a corretora"], correta=1),
        _ex("vf", "O dever de verificar a adequação do produto (suitability) vale para todos os investidores, sem nenhuma dispensa.", "As normas preveem algumas dispensas, como para investidores profissionais.", correta=False),
        _ex("escolha", "A carteira do cliente ficou desenquadrada do perfil. O que a instituição deve fazer?", "Alertar o cliente e registrar a ciência dele.",
            opcoes=["Vender tudo sem avisar", "Alertar e registrar a ciência do cliente", "Ignorar", "Mudar o perfil do cliente sozinha"], correta=1),
        _ex("completar", "Para ser investidor qualificado pelo critério de patrimônio, a pessoa precisa ___ essa condição por escrito.", "A declaração faz parte do enquadramento.",
            opcoes=["atestar", "esconder", "pagar", "transferir"], correta=0),
    ]),
    dict(id="lcr_pld", unidade="ucr_regra", titulo="PLD/FT baseada em risco", icone="🕵️", aula="acr_pld", exercicios=[
        _ex("escolha", "O que significa a abordagem baseada em risco na PLD/FT?", "Clientes, produtos e canais de maior risco recebem mais atenção.",
            opcoes=["Todos os clientes são tratados igual", "Mais atenção para o que tem mais risco", "Só clientes novos são monitorados", "Só operações acima de R$ 1 milhão"], correta=1),
        _ex("completar", "Agentes públicos de alto cargo e pessoas próximas a eles são chamados de ___.", "Pessoas Expostas Politicamente exigem diligência reforçada.",
            opcoes=["PEP", "COAF", "KYC", "CVM"], correta=0),
        _ex("pares", "Ligue cada termo da PLD ao seu significado.", "Esses conceitos aparecem com frequência na prova.",
            pares=[("KYC", "Conhecer o cliente"), ("Beneficiário final", "Quem de fato controla o recurso"), ("COAF", "Recebe as comunicações de operações suspeitas")]),
        _ex("escolha", "Qual destes é um sinal de alerta em PLD?", "Recusar informar a origem do dinheiro é um sinal clássico.",
            opcoes=["Cliente atualiza o cadastro", "Cliente se recusa a informar a origem dos recursos", "Cliente aplica todo mês", "Cliente pede extrato"], correta=1),
        _ex("vf", "A responsabilidade pela PLD é só da área de compliance, e não dos profissionais de atendimento.", "Cada profissional também tem responsabilidade e deve ser treinado.", correta=False),
    ]),
    dict(id="lcr_estatistica", unidade="ucr_estat", titulo="Estatística aplicada", icone="📐", aula="acr_estatistica", exercicios=[
        _ex("pares", "Ligue cada medida estatística ao que ela representa.", "São a base para medir risco e diversificação.",
            pares=[("Média", "Retorno médio do período"), ("Desvio padrão", "Dispersão dos retornos (volatilidade)"), ("Correlação", "Como dois ativos se movem juntos")]),
        _ex("escolha", "Qual correlação traz o maior benefício de diversificação?", "Quanto menor a correlação, maior o benefício.",
            opcoes=["+1", "+0,5", "0", "−1"], correta=3),
        _ex("escolha", "Na distribuição normal, cerca de quantos % dos resultados ficam a até 2 desvios padrão da média?",
            "Cerca de 68% a 1 desvio e cerca de 95% a 2 desvios.", opcoes=["50%", "68%", "95%", "100%"], correta=2),
        _ex("completar", "A variância é o desvio padrão elevado ao ___.", "Desvio padrão = raiz quadrada da variância.",
            opcoes=["quadrado", "cubo", "dobro", "inverso"], correta=0),
        _ex("vf", "O risco de uma carteira é sempre a média simples dos riscos dos ativos.", "Depende dos pesos e das correlações; a diversificação pode reduzir o risco.", correta=False),
    ]),
    dict(id="lcr_sharpe", unidade="ucr_estat", titulo="Sharpe e diversificação", icone="📏", aula="acr_sharpe", exercicios=[
        _ex("escolha", "Caso: retorno de 14%, taxa livre de risco de 10% e desvio padrão de 8%. Qual é o Índice de Sharpe?", "(14 − 10) ÷ 8 = 0,5.",
            opcoes=["0,5", "1,75", "4", "0,25"], correta=0),
        _ex("vf", "Quanto maior o Índice de Sharpe, melhor a relação entre retorno e risco.", "Mais retorno excedente por unidade de risco.", correta=True),
        _ex("pares", "Ligue cada índice ao risco que usa no denominador.", "Sharpe usa o risco total; Treynor, o sistemático.",
            pares=[("Sharpe", "Desvio padrão (risco total)"), ("Treynor", "Beta (risco sistemático)")]),
        _ex("escolha", "Um Sharpe negativo indica:", "A carteira rendeu menos que a taxa livre de risco.",
            opcoes=["Retorno abaixo da taxa livre de risco", "Risco zero", "Retorno garantido", "Erro de cálculo sempre"], correta=0),
        _ex("completar", "A diversificação reduz o risco não sistemático, mas não o risco ___.", "O risco de mercado atinge todos os ativos.",
            opcoes=["sistemático", "específico", "de uma empresa", "de setor"], correta=0),
    ]),
    dict(id="lcr_rf_preco", unidade="ucr_mercados", titulo="Preço e duration", icone="⏳", aula="acr_rf_preco", exercicios=[
        _ex("escolha", "Se a taxa de mercado de um título prefixado sobe, o preço dele:", "Taxa e preço têm relação inversa.",
            opcoes=["Sobe", "Cai", "Não muda", "Dobra"], correta=1),
        _ex("vf", "Num título zero cupom, a duration é igual ao prazo.", "Sem fluxos intermediários, todo o valor está no vencimento.", correta=True),
        _ex("escolha", "Caso: duration modificada de 4 e alta de 1 ponto percentual na taxa. Qual a variação aproximada do preço?", "−4 × 1% ≈ −4%.",
            opcoes=["+4%", "−4%", "−1%", "−0,25%"], correta=1),
        _ex("completar", "Quanto maior a duration, ___ a sensibilidade do preço à variação dos juros.", "Títulos longos oscilam mais.",
            opcoes=["maior", "menor", "nula", "igual"], correta=0),
        _ex("pares", "Ligue cada medida de risco de juros ao seu significado.", "São ferramentas para medir o risco de juros.",
            pares=[("Duration de Macaulay", "Prazo médio ponderado dos fluxos"), ("Duration modificada", "Sensibilidade do preço à taxa"), ("Convexidade", "Correção da aproximação da duration")]),
    ]),
    dict(id="lcr_mercados_rv", unidade="ucr_mercados", titulo="Mercados e proventos", icone="🏦", aula="acr_mercados_rv", exercicios=[
        _ex("pares", "Ligue cada mercado ao que acontece nele.", "No primário a empresa recebe o dinheiro; no secundário, não.",
            pares=[("Primário", "A empresa emite e recebe o dinheiro"), ("Secundário", "Investidores negociam entre si")]),
        _ex("escolha", "Num IPO, os recursos vão para:", "Na oferta primária, o dinheiro novo vai para a empresa.",
            opcoes=["A empresa emissora", "Os outros investidores", "A CVM", "O Banco Central"], correta=0),
        _ex("escolha", "Qual provento tem IR retido na fonte para pessoa física, pela regra vigente na revisão?", "Os JCP têm retenção; os dividendos são isentos.",
            opcoes=["Dividendos", "Juros sobre capital próprio", "Bonificação", "Desdobramento"], correta=1),
        _ex("vf", "O desdobramento de ações aumenta o valor total do investimento do acionista.", "Aumenta a quantidade e reduz o preço proporcionalmente; o total não muda.", correta=False),
        _ex("completar", "O mercado secundário dá ___ aos investidores.", "Sem ele, seria difícil vender o que se comprou.",
            opcoes=["liquidez", "garantia do FGC", "isenção de IR", "rentabilidade fixa"], correta=0),
    ]),
    dict(id="lcr_derivativos", unidade="ucr_mercados", titulo="Derivativos", icone="🔀", aula="acr_derivativos", exercicios=[
        _ex("pares", "Ligue cada derivativo à sua característica.", "Termo, futuro, opção e swap funcionam de formas diferentes.",
            pares=[("Termo", "Preço combinado, liquida no vencimento"), ("Futuro", "Padronizado, com ajuste diário"), ("Opção", "Dá um direito, mediante prêmio"),
                   ("Swap", "Troca de rentabilidades entre as partes")]),
        _ex("escolha", "Quem compra uma opção de compra (call) tem:", "O titular tem o direito, não a obrigação.",
            opcoes=["A obrigação de comprar", "O direito de comprar", "A obrigação de vender", "O direito de vender"], correta=1),
        _ex("vf", "O risco do titular de uma opção é limitado ao prêmio pago.", "Se não exercer, perde no máximo o prêmio.", correta=True),
        _ex("escolha", "Uma empresa vai pagar dólares daqui a 6 meses e quer se proteger da alta. O que pode fazer?", "Comprar dólar futuro trava o preço.",
            opcoes=["Vender dólar futuro", "Comprar dólar futuro", "Vender ações", "Não há proteção possível"], correta=1),
        _ex("completar", "No mercado futuro, o ajuste ___ e a margem de garantia reduzem o risco de crédito.", "As posições são acertadas todo dia.",
            opcoes=["diário", "anual", "semestral", "único"], correta=0),
    ]),
    dict(id="lcr_fundos", unidade="ucr_fundos", titulo="Estrutura dos fundos", icone="🏗️", aula="acr_fundos", exercicios=[
        _ex("pares", "Ligue cada prestador essencial do fundo à sua função.", "Administrador e gestor são os prestadores essenciais.",
            pares=[("Administrador", "Parte legal, operacional e fiscalização"), ("Gestor", "Decisões de investimento")]),
        _ex("pares", "Ligue cada documento do fundo ao seu conteúdo.", "Leia os dois antes de investir.",
            pares=[("Regulamento", "Todas as regras do fundo"), ("Lâmina", "Resumo das informações essenciais")]),
        _ex("escolha", "Quem decide mudanças relevantes no regulamento de um fundo?", "A assembleia de cotistas delibera sobre temas importantes.",
            opcoes=["Só o gestor", "A assembleia de cotistas", "A B3", "O cotista sozinho"], correta=1),
        _ex("vf", "Num fundo de condomínio fechado, o cotista pode pedir resgate a qualquer momento.", "No fechado não há resgate; as cotas são negociadas em mercado.", correta=False),
        _ex("completar", "Pela regulação atual, um fundo pode ter ___ de cotas, cada uma com política de investimento própria.", "As classes podem ter subclasses.",
            opcoes=["classes", "ações", "debêntures", "letras"], correta=0),
    ]),
    dict(id="lcr_previdencia", unidade="ucr_fundos", titulo="PGBL, VGBL e regimes de IR", icone="🧓", aula="acr_previdencia", exercicios=[
        _ex("escolha", "Quem faz a declaração completa do IR e quer deduzir as contribuições deve olhar para o:", "O PGBL permite deduzir até 12% da renda bruta tributável.",
            opcoes=["VGBL", "PGBL", "CDB", "Tesouro Selic"], correta=1),
        _ex("pares", "Ligue cada prazo à alíquota do regime regressivo da previdência.", "A alíquota cai 5 pontos a cada 2 anos.",
            pares=[("Até 2 anos", "35%"), ("De 4 a 6 anos", "25%"), ("Acima de 10 anos", "10%")]),
        _ex("vf", "No regime progressivo da previdência, há retenção de 15% na fonte e ajuste na declaração anual.", "O imposto final segue a tabela do IR.", correta=True),
        _ex("escolha", "No VGBL, o IR do resgate incide sobre:", "No VGBL, só os rendimentos são tributados.",
            opcoes=["O valor total", "Apenas os rendimentos", "Nada, é isento", "O valor das contribuições"], correta=1),
        _ex("completar", "A ___ entre planos do mesmo tipo não gera cobrança de IR.", "A portabilidade transfere os recursos de um plano para outro.",
            opcoes=["portabilidade", "contribuição", "carência", "assembleia"], correta=0),
    ]),
    dict(id="lcr_tributos", unidade="ucr_fundos", titulo="Tributação por produto", icone="🧾", aula="acr_tributos", exercicios=[
        _ex("pares", "Ligue cada operação com ações à alíquota de IR sobre o ganho (pessoa física, na revisão).", "Day trade tem alíquota maior.",
            pares=[("Operações comuns", "15%"), ("Day trade", "20%")]),
        _ex("escolha", "Qual é o IR retido na fonte (\"dedo-duro\") nas operações comuns com ações?", "0,005% sobre a venda; no day trade, 1% sobre o ganho.",
            opcoes=["0,005% sobre a venda", "1% sobre a venda", "15% sobre a venda", "Não há retenção"], correta=0),
        _ex("vf", "Fundos de ações têm come-cotas em maio e novembro.", "Fundos de ações não têm come-cotas; pagam 15% no resgate.", correta=False),
        _ex("escolha", "Prejuízo em day trade pode ser compensado com:", "Cada modalidade compensa com a mesma modalidade.",
            opcoes=["Lucro de day trade", "Lucro de renda fixa", "Lucro de operações comuns, sempre", "Nada"], correta=0),
        _ex("completar", "O IR sobre ganhos com ações é pago por ___ até o último dia útil do mês seguinte.", "O investidor calcula e recolhe o imposto.",
            opcoes=["DARF", "DAS", "boleto do condomínio", "Pix para a corretora"], correta=0),
    ]),
]

for _a in AULAS:
    if _a.get("intermediario"):
        _a["intermediario"] = _a["iniciante"] + "\n\n**Para ir além:** " + _a["intermediario"]

# Espalha a posição da resposta certa nas questões de escolha (fixo, sem sorteio), para a certa não ficar sempre no mesmo lugar.
for _i, _e in enumerate(e for _l in LICOES for e in _l["exercicios"] if e["tipo"] in ("escolha", "completar")):
    _k = (_i * 3 + 1) % len(_e["opcoes"])
    _ops = list(_e["opcoes"])
    _certa = _ops.pop(_e["correta"])
    _ops.insert(_k, _certa)
    _e["opcoes"], _e["correta"] = _ops, _k
