"""Aprender · CERTIFICAÇÕES · C-Pro I (fase 5) — SÓ DADOS. Formato das lições em jornada_conteudo.py; aulas como em edu_conteudo.py.

Conteúdo de ESTUDO para a C-Pro I (ANBIMA, antiga CEA), voltada a quem orienta investidores e indica produtos: teoria de carteiras,
CAPM e avaliação de desempenho, renda fixa avançada, valuation de ações, gestão de riscos e alocação para o cliente.
Sem vínculo com a ANBIMA: confira o programa oficial vigente, o formato da prova e a nota de corte no site da ANBIMA.
Números são HIPOTÉTICOS; nada recomenda produto específico.
"""
from __future__ import annotations

AREA = "certificacoes"
CERT = "cpro_i"

UNIDADES = [
    dict(id="uci_carteiras", area=AREA, cert=CERT, titulo="Teoria de carteiras", icone="🧠", icone_svg="grafico", cor="#F7C84A",
         descricao="Fronteira eficiente, CAPM e beta.",
         licoes=["lci_markowitz", "lci_capm"]),
    dict(id="uci_desempenho", area=AREA, cert=CERT, titulo="Desempenho e riscos", icone="📏", icone_svg="alvo", cor="#FF5A7A",
         descricao="Sharpe, Treynor, tracking error, VaR e stress test.",
         licoes=["lci_indices", "lci_var"]),
    dict(id="uci_ativos", area=AREA, cert=CERT, titulo="Avaliação de ativos", icone="🔎", icone_svg="cofre", cor="#4DA3FF",
         descricao="Curva de juros e convexidade, valuation de ações (DCF, Gordon e múltiplos).",
         licoes=["lci_curva", "lci_valuation", "lci_multiplos"]),
    dict(id="uci_cliente", area=AREA, cert=CERT, titulo="Recomendação ao cliente", icone="🤝", icone_svg="escudo", cor="#2DD4A0",
         descricao="Política de investimento, alocação de ativos e rebalanceamento.",
         licoes=["lci_politica", "lci_alocacao"]),
]

NIVEIS = {lid: "avancado" for lid in ("lci_markowitz", "lci_capm", "lci_indices", "lci_var", "lci_curva", "lci_valuation", "lci_multiplos", "lci_politica", "lci_alocacao")}

_A = dict(dificuldade="avancado", fontes=["anbima", "cvm"], relacionadas=[])
AULAS = [
    dict(_A, id="aci_markowitz", assunto="carteiras", titulo="Markowitz e a fronteira eficiente", min=6,
         iniciante="A **teoria moderna de carteiras** (Markowitz) mostra que o risco de uma carteira depende das **correlações** entre os ativos, e não só do risco "
                   "de cada um. Combinar ativos pouco correlacionados reduz o risco total para um mesmo retorno esperado.\n\n"
                   "**Fronteira eficiente:** o conjunto de carteiras com o **maior retorno esperado para cada nível de risco** (ou o menor risco para cada retorno). "
                   "Carteiras abaixo da fronteira são **ineficientes**.\n\n"
                   "**Carteira de variância mínima:** a de menor risco possível na fronteira.\n\n"
                   "**Na prática:** a carteira ideal para o cliente fica na fronteira, no ponto compatível com a tolerância a risco dele.",
         intermediario="Com um ativo livre de risco, surge a **linha do mercado de capitais (CML)**, que liga a taxa livre de risco à **carteira de mercado**. "
                       "Combinações sobre essa linha dominam as demais carteiras de ativos de risco."),
    dict(_A, id="aci_capm", assunto="carteiras", titulo="CAPM e beta", min=6,
         iniciante="O **CAPM** estima o **retorno exigido** de um ativo a partir do risco sistemático dele:\n\n"
                   "**E(R) = Rf + β × (Rm − Rf)**\n\n"
                   "**Rf:** taxa livre de risco. **Rm − Rf:** prêmio de risco do mercado. **β (beta):** sensibilidade do ativo ao mercado.\n\n"
                   "**Beta:** igual a 1 acompanha o mercado; **maior que 1** oscila mais que o mercado (agressivo); **menor que 1** oscila menos (defensivo).\n\n"
                   "**Exemplo (hipotético):** Rf = 10%, Rm = 16% e β = 1,5: E(R) = 10 + 1,5 × 6 = **19%**.",
         intermediario="O CAPM só remunera o **risco sistemático**, porque o não sistemático pode ser eliminado com diversificação. O **alfa de Jensen** mede o "
                       "retorno acima do previsto pelo CAPM: alfa positivo indica desempenho superior ao exigido pelo risco."),
    dict(_A, id="aci_indices", assunto="riscos", titulo="Avaliação de desempenho", min=6,
         iniciante="**Sharpe:** (retorno − Rf) ÷ desvio padrão. Mede retorno por unidade de **risco total**.\n\n"
                   "**Treynor:** (retorno − Rf) ÷ beta. Mede retorno por unidade de **risco sistemático**; útil para carteiras já diversificadas.\n\n"
                   "**Tracking error:** o desvio padrão da diferença entre o retorno da carteira e o do **benchmark**. Fundos passivos buscam tracking error baixo.\n\n"
                   "**Índice de informação:** (retorno − benchmark) ÷ tracking error. Mede o retorno ativo por unidade de risco ativo.\n\n"
                   "**Exemplo (hipotético):** retorno 15%, Rf 10%, beta 1,25: Treynor = (15 − 10) ÷ 1,25 = **4**.",
         intermediario="Use o índice adequado ao contexto: Sharpe para a carteira inteira do cliente; Treynor e alfa para um componente de uma carteira "
                       "diversificada; tracking error e índice de informação para gestores comparados a um benchmark."),
    dict(_A, id="aci_var", assunto="riscos", titulo="VaR, stress test e gestão de riscos", min=5,
         iniciante="**VaR (Value at Risk):** a **perda máxima esperada** num horizonte, com um nível de confiança. Ex. hipotético: VaR de 1 dia de R$ 10 mil "
                   "a 95% significa que, em 95% dos dias, a perda não deve passar de R$ 10 mil.\n\n"
                   "**Limitação:** o VaR **não diz o tamanho** da perda nos piores casos (os 5% restantes).\n\n"
                   "**Stress test:** simula cenários extremos (crises, choques de juros) para ver o impacto na carteira.\n\n"
                   "**Na prática:** VaR e stress test se complementam: um mede o \"normal ruim\", o outro, o \"muito ruim\".",
         intermediario="O VaR paramétrico assume distribuição normal; o histórico usa os retornos passados; o de Monte Carlo simula cenários. Mercados têm "
                       "\"caudas gordas\": eventos extremos acontecem mais do que a normal prevê. Gerencie também risco de liquidez e de concentração."),
    dict(_A, id="aci_curva", assunto="renda_fixa", titulo="Curva de juros e convexidade", min=6, fontes=["anbima", "tesouro"],
         iniciante="A **curva de juros** (estrutura a termo) mostra as taxas para cada prazo. Ela costuma ser **positivamente inclinada** (prazos longos pagam mais), "
                   "mas pode ficar **plana** ou **invertida**, quando o mercado espera queda de juros.\n\n"
                   "**Taxa a termo (forward):** a taxa implícita entre dois prazos futuros, calculada a partir da curva.\n\n"
                   "**Convexidade:** corrige a aproximação da duration. Entre dois títulos de mesma duration, o de **maior convexidade** ganha mais quando os juros caem "
                   "e perde menos quando sobem.\n\n"
                   "**Na prática:** a NTN-B (Tesouro IPCA+) é referência de juros reais; os prefixados, de juros nominais.",
         intermediario="A diferença entre a taxa prefixada e a taxa real de mesmo prazo é a **inflação implícita** esperada pelo mercado. Estratégias de "
                       "**imunização** casam a duration da carteira com o prazo do passivo do cliente."),
    dict(_A, id="aci_valuation", assunto="valuation", titulo="Valuation: fluxo de caixa descontado e Gordon", min=6,
         iniciante="O **valor de uma empresa** é o valor presente dos fluxos de caixa futuros, descontados por uma taxa que reflete o risco (**DCF**).\n\n"
                   "**Modelo de Gordon** (dividendos que crescem a uma taxa constante):\n\n"
                   "**P = D1 ÷ (k − g)**\n\n"
                   "**D1:** dividendo esperado no próximo ano. **k:** retorno exigido pelo acionista. **g:** crescimento constante dos dividendos (precisa ser menor que k).\n\n"
                   "**Exemplo (hipotético):** D1 = R$ 2, k = 12% e g = 4%: P = 2 ÷ 0,08 = **R$ 25**.",
         intermediario="No DCF da firma, os fluxos livres de caixa são descontados pelo **WACC** (custo médio ponderado de capital próprio e de terceiros). O "
                       "valor é muito sensível às premissas de crescimento e de taxa: faça análise de sensibilidade."),
    dict(_A, id="aci_multiplos", assunto="indicadores", titulo="Múltiplos de mercado", min=5,
         iniciante="**Múltiplos** comparam o preço com alguma medida da empresa:\n\n"
                   "**P/L:** preço ÷ lucro por ação. **P/VPA:** preço ÷ valor patrimonial por ação. **EV/EBITDA:** valor da firma ÷ geração de caixa operacional. "
                   "**Dividend yield:** dividendos por ação ÷ preço.\n\n"
                   "**Exemplo (hipotético):** preço R$ 30 e lucro por ação R$ 3: P/L = **10**.\n\n"
                   "**Na prática:** compare múltiplos de empresas do **mesmo setor**; múltiplo baixo não é sinônimo de \"barato\".",
         intermediario="O **EV** (enterprise value) soma o valor de mercado das ações à dívida líquida; por isso o EV/EBITDA permite comparar empresas com "
                       "estruturas de capital diferentes. O ROE (lucro ÷ patrimônio líquido) ajuda a explicar diferenças de P/VPA."),
    dict(_A, id="aci_politica", assunto="carteiras", titulo="Política de investimento do cliente", min=5,
         iniciante="Antes de recomendar, o profissional monta a **política de investimento** do cliente, com:\n\n"
                   "**Objetivos:** retorno exigido e tolerância a risco (vontade e **capacidade** de assumir risco).\n"
                   "**Restrições:** **horizonte**, **liquidez** (quando vai precisar de dinheiro), **impostos**, **questões legais** e **preferências** do cliente.\n\n"
                   "**Exemplo do dia a dia:** um cliente com alta tolerância emocional, mas que vai comprar um imóvel em 1 ano, tem **baixa capacidade** de risco para "
                   "esse dinheiro.\n\n"
                   "**Na prática:** quando vontade e capacidade divergem, prevalece a **menor**.",
         intermediario="O ciclo de vida importa: jovens com renda estável costumam ter mais capacidade de risco pelo capital humano. Reveja a política quando "
                       "houver eventos relevantes (herança, aposentadoria, mudança de renda) e documente as recomendações."),
    dict(_A, id="aci_alocacao", assunto="carteiras", titulo="Alocação de ativos e rebalanceamento", min=5,
         iniciante="**Alocação estratégica:** os pesos de longo prazo de cada classe (renda fixa, ações, imobiliário, exterior) definidos pela política do cliente. "
                   "Ela explica a **maior parte** da variação dos resultados de uma carteira.\n\n"
                   "**Alocação tática:** desvios temporários em relação à estratégica, para aproveitar oportunidades.\n\n"
                   "**Rebalanceamento:** voltar aos pesos-alvo, por calendário ou por faixas de tolerância. Considere custos e impostos.\n\n"
                   "**Na prática:** \"comprar barato e vender caro\" de forma disciplinada é o efeito do rebalanceamento.",
         intermediario="Faixas de tolerância evitam rebalanceamentos frequentes demais. Usar os fluxos de caixa (aportes e resgates) para rebalancear reduz "
                       "custos. Diversificação internacional pode reduzir o risco quando as correlações com o mercado local são baixas."),
]

def _ex(tipo, pergunta, explicacao, **kw):
    return dict(tipo=tipo, pergunta=pergunta, explicacao=explicacao, **kw)


LICOES = [
    dict(id="lci_markowitz", unidade="uci_carteiras", titulo="Fronteira eficiente", icone="🧠", aula="aci_markowitz", exercicios=[
        _ex("escolha", "O que é a fronteira eficiente?", "São as carteiras com o melhor retorno esperado para cada nível de risco.",
            opcoes=["Carteiras com o maior retorno para cada nível de risco", "Carteiras sem nenhum risco", "As ações mais negociadas", "O limite do FGC"], correta=0),
        _ex("vf", "Uma carteira abaixo da fronteira eficiente é ineficiente.", "Existe outra carteira com mais retorno para o mesmo risco.", correta=True),
        _ex("completar", "A carteira de menor risco possível na fronteira é a de ___ mínima.", "É o ponto mais à esquerda da fronteira.",
            opcoes=["variância", "liquidez", "taxa", "duration"], correta=0),
        _ex("escolha", "Com um ativo livre de risco, a linha que liga a taxa livre de risco à carteira de mercado se chama:", "É a linha do mercado de capitais (CML).",
            opcoes=["CML", "SML", "Curva de juros", "Fronteira mínima"], correta=0),
        _ex("pares", "Ligue cada conceito de Markowitz ao seu significado.", "O risco da carteira depende das correlações.",
            pares=[("Correlação baixa", "Maior redução de risco ao combinar"), ("Ponto na fronteira", "Melhor retorno para aquele risco"), ("Ponto abaixo", "Carteira ineficiente")]),
    ]),
    dict(id="lci_capm", unidade="uci_carteiras", titulo="CAPM e beta", icone="📈", aula="aci_capm", exercicios=[
        _ex("escolha", "Caso: Rf = 10%, Rm = 16% e β = 1,5. Qual é o retorno exigido pelo CAPM?", "10 + 1,5 × (16 − 10) = 19%.",
            opcoes=["16%", "19%", "24%", "15%"], correta=1),
        _ex("pares", "Ligue cada beta ao comportamento do ativo.", "Beta mede a sensibilidade ao mercado.",
            pares=[("β = 1", "Acompanha o mercado"), ("β > 1", "Oscila mais que o mercado"), ("β < 1", "Oscila menos que o mercado")]),
        _ex("vf", "O CAPM remunera o risco não sistemático, porque ele não pode ser diversificado.", "É o contrário: só o sistemático é remunerado.", correta=False),
        _ex("completar", "O retorno acima do previsto pelo CAPM é o alfa de ___.", "Alfa positivo indica desempenho superior ao exigido pelo risco.",
            opcoes=["Jensen", "Sharpe", "Gordon", "Markowitz"], correta=0),
        _ex("escolha", "No CAPM, o termo (Rm − Rf) representa:", "É o prêmio que o mercado paga acima da taxa livre de risco.",
            opcoes=["O prêmio de risco do mercado", "A inflação", "O beta", "A taxa Selic"], correta=0),
    ]),
    dict(id="lci_indices", unidade="uci_desempenho", titulo="Índices de desempenho", icone="🏅", aula="aci_indices", exercicios=[
        _ex("escolha", "Caso: retorno de 15%, Rf de 10% e beta de 1,25. Qual é o índice de Treynor?", "(15 − 10) ÷ 1,25 = 4.",
            opcoes=["4", "5", "6,25", "0,4"], correta=0),
        _ex("pares", "Ligue cada medida de desempenho ao seu uso principal.", "Escolha o índice adequado ao contexto.",
            pares=[("Sharpe", "Carteira inteira, risco total"), ("Treynor", "Carteira diversificada, risco sistemático"), ("Tracking error", "Distância em relação ao benchmark")]),
        _ex("vf", "Um fundo passivo busca tracking error baixo.", "Ele quer acompanhar o índice de perto.", correta=True),
        _ex("completar", "O índice de ___ divide o retorno acima do benchmark pelo tracking error.", "Mede o retorno ativo por unidade de risco ativo.",
            opcoes=["informação", "Treynor", "Gordon", "liquidez"], correta=0),
        _ex("escolha", "Para comparar gestores que seguem o mesmo benchmark, a medida mais adequada é:", "O índice de informação compara o retorno ativo com o risco ativo.",
            opcoes=["Índice de informação", "P/L", "Duration", "Dividend yield"], correta=0),
    ]),
    dict(id="lci_var", unidade="uci_desempenho", titulo="VaR e stress test", icone="🌪️", aula="aci_var", exercicios=[
        _ex("escolha", "VaR de 1 dia de R$ 10 mil a 95% significa que:", "Em 95% dos dias, a perda não deve passar de R$ 10 mil.",
            opcoes=["Em 95% dos dias a perda não passa de R$ 10 mil", "A perda máxima possível é R$ 10 mil", "Há 95% de chance de perder R$ 10 mil", "O lucro mínimo é R$ 10 mil"], correta=0),
        _ex("vf", "O VaR informa o tamanho da perda nos piores dias, além do nível de confiança.", "O VaR não diz quanto se perde nos casos extremos.", correta=False),
        _ex("pares", "Ligue cada método de VaR à sua base.", "Cada método tem vantagens e limitações.",
            pares=[("Paramétrico", "Assume distribuição normal"), ("Histórico", "Usa os retornos passados"), ("Monte Carlo", "Simula muitos cenários")]),
        _ex("completar", "O ___ test simula cenários extremos, como crises e choques de juros.", "Ele complementa o VaR.",
            opcoes=["stress", "back", "suitability", "tracking"], correta=0),
        _ex("escolha", "\"Caudas gordas\" significam que:", "Eventos extremos são mais frequentes do que a normal prevê.",
            opcoes=["Eventos extremos acontecem mais do que a normal prevê", "Não há risco", "O VaR é sempre exato", "O mercado nunca cai"], correta=0),
    ]),
    dict(id="lci_curva", unidade="uci_ativos", titulo="Curva de juros", icone="〰️", aula="aci_curva", exercicios=[
        _ex("pares", "Ligue cada formato da curva de juros à expectativa típica.", "A inclinação reflete expectativas e prêmios de prazo.",
            pares=[("Positivamente inclinada", "Prazos longos pagam mais"), ("Invertida", "Mercado espera queda de juros")]),
        _ex("escolha", "Entre dois títulos de mesma duration, qual é preferível pela convexidade?", "Maior convexidade ganha mais na queda e perde menos na alta dos juros.",
            opcoes=["O de maior convexidade", "O de menor convexidade", "Tanto faz", "O de menor prazo, sempre"], correta=0),
        _ex("completar", "A diferença entre a taxa prefixada e a taxa real de mesmo prazo é a inflação ___.", "É a inflação esperada pelo mercado.",
            opcoes=["implícita", "passada", "oficial", "garantida"], correta=0),
        _ex("vf", "Imunização é casar a duration da carteira com o prazo do passivo do cliente.", "Assim a carteira fica protegida de variações de juros para aquele objetivo.", correta=True),
        _ex("escolha", "Qual título é a referência de juros reais no Brasil?", "A NTN-B (Tesouro IPCA+) paga inflação mais uma taxa real.",
            opcoes=["NTN-B (Tesouro IPCA+)", "LTN (Prefixado)", "LFT (Tesouro Selic)", "CDB"], correta=0),
    ]),
    dict(id="lci_valuation", unidade="uci_ativos", titulo="DCF e Gordon", icone="💰", aula="aci_valuation", exercicios=[
        _ex("escolha", "Caso: D1 = R$ 2, k = 12% e g = 4%. Qual é o preço pelo modelo de Gordon?", "2 ÷ (0,12 − 0,04) = R$ 25.",
            opcoes=["R$ 16,67", "R$ 25", "R$ 50", "R$ 12,50"], correta=1),
        _ex("vf", "No modelo de Gordon, a taxa de crescimento g precisa ser menor que o retorno exigido k.", "Senão o denominador fica nulo ou negativo.", correta=True),
        _ex("completar", "No DCF da firma, os fluxos livres de caixa são descontados pelo ___.", "O WACC pondera o custo do capital próprio e o de terceiros.",
            opcoes=["WACC", "IPCA", "beta", "CDI"], correta=0),
        _ex("escolha", "Por que fazer análise de sensibilidade no valuation?", "Pequenas mudanças nas premissas mudam muito o valor.",
            opcoes=["Porque o valor depende muito das premissas", "Porque é exigido pela B3", "Para aumentar o preço", "Não há motivo"], correta=0),
        _ex("pares", "Ligue cada variável do modelo de Gordon ao seu significado.", "P = D1 ÷ (k − g).",
            pares=[("D1", "Dividendo esperado no próximo ano"), ("k", "Retorno exigido pelo acionista"), ("g", "Crescimento constante dos dividendos")]),
    ]),
    dict(id="lci_multiplos", unidade="uci_ativos", titulo="Múltiplos", icone="✖️", aula="aci_multiplos", exercicios=[
        _ex("escolha", "Caso: preço de R$ 30 e lucro por ação de R$ 3. Qual é o P/L?", "30 ÷ 3 = 10.",
            opcoes=["3", "10", "33", "90"], correta=1),
        _ex("pares", "Ligue cada múltiplo à sua fórmula.", "Compare sempre dentro do mesmo setor.",
            pares=[("P/L", "Preço ÷ lucro por ação"), ("P/VPA", "Preço ÷ valor patrimonial por ação"), ("Dividend yield", "Dividendos por ação ÷ preço")]),
        _ex("vf", "Um múltiplo baixo sempre indica que a ação está barata.", "Pode refletir risco ou baixo crescimento; compare dentro do setor.", correta=False),
        _ex("completar", "O EV soma o valor de mercado das ações à dívida ___.", "Por isso o EV/EBITDA compara empresas com estruturas de capital diferentes.",
            opcoes=["líquida", "bruta de curto prazo", "do governo", "dos clientes"], correta=0),
        _ex("escolha", "Qual múltiplo permite comparar empresas com níveis de dívida diferentes?", "O EV inclui a dívida líquida.",
            opcoes=["EV/EBITDA", "P/L", "Dividend yield", "P/VPA"], correta=0),
    ]),
    dict(id="lci_politica", unidade="uci_cliente", titulo="Política de investimento", icone="📋", aula="aci_politica", exercicios=[
        _ex("pares", "Ligue cada item da política de investimento ao seu tipo.", "Objetivos e restrições formam a política.",
            pares=[("Retorno exigido", "Objetivo de retorno"), ("Tolerância a risco", "Objetivo de risco"), ("Horizonte", "Restrição de prazo")]),
        _ex("escolha", "Quando a vontade e a capacidade de assumir risco divergem, qual deve prevalecer?", "Prevalece a menor, para proteger o cliente.",
            opcoes=["A maior", "A menor", "A do profissional", "Nenhuma"], correta=1),
        _ex("escolha", "Caso: cliente arrojado emocionalmente, mas que vai comprar um imóvel em 1 ano com esse dinheiro. A capacidade de risco é:", "O prazo curto limita a capacidade de risco.",
            opcoes=["Alta", "Baixa", "Ilimitada", "Irrelevante"], correta=1),
        _ex("vf", "A política de investimento deve ser revista em eventos relevantes, como herança ou aposentadoria.", "Mudanças de vida mudam objetivos e restrições.", correta=True),
        _ex("completar", "Jovens com renda estável costumam ter mais capacidade de risco por causa do capital ___.", "A renda futura do trabalho funciona como um ativo.",
            opcoes=["humano", "social", "de giro", "estrangeiro"], correta=0),
    ]),
    dict(id="lci_alocacao", unidade="uci_cliente", titulo="Alocação e rebalanceamento", icone="🧭", aula="aci_alocacao", exercicios=[
        _ex("pares", "Ligue cada tipo de alocação ao seu horizonte.", "A estratégica é a base; a tática, um desvio temporário.",
            pares=[("Estratégica", "Pesos de longo prazo"), ("Tática", "Desvios temporários")]),
        _ex("vf", "A alocação estratégica explica a maior parte da variação dos resultados de uma carteira.", "A escolha das classes pesa mais do que a escolha dos ativos.", correta=True),
        _ex("escolha", "Qual é uma forma eficiente de rebalancear com menos custos?", "Usar os aportes e resgates evita vender e gerar impostos.",
            opcoes=["Usar os aportes e resgates", "Vender tudo todo mês", "Nunca rebalancear", "Trocar de corretora"], correta=0),
        _ex("completar", "Faixas de ___ evitam rebalanceamentos frequentes demais.", "Só se rebalanceia quando o peso sai da faixa.",
            opcoes=["tolerância", "isenção", "liquidez", "garantia"], correta=0),
        _ex("escolha", "A diversificação internacional reduz o risco quando:", "Correlações baixas com o mercado local trazem benefício.",
            opcoes=["As correlações com o mercado local são baixas", "O dólar está barato", "Sempre, em qualquer caso", "Nunca"], correta=0),
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
