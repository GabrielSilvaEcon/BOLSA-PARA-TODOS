"""Glossário central do Bússola B3 (puro, sem Streamlit, sem consulta externa).

Uma só fonte para siglas e termos técnicos: nome completo em português, nome original em inglês, definição,
explicação por nível (Iniciante / Intermediário / Avançado), fórmula, exemplo, interpretação, limitações e classes de ativos.
Os exemplos são hipotéticos e servem só para ilustrar o cálculo. Nenhum indicador é "bom" ou "ruim" isoladamente.
"""
from __future__ import annotations

import re
import unicodedata

CLASSES = ("acoes_br", "acoes_eua", "fiis", "etfs", "fundos", "cripto", "renda_fixa", "economia", "carteira", "tecnica")
CLASSE_ROTULO = {"acoes_br": "Ações brasileiras", "acoes_eua": "Ações dos EUA", "fiis": "FIIs", "etfs": "ETFs", "fundos": "Fundos",
                 "cripto": "Criptomoedas", "renda_fixa": "Renda fixa", "economia": "Economia", "carteira": "Carteira e risco",
                 "tecnica": "Análise técnica"}
_ACOES = ("acoes_br", "acoes_eua")
_TODAS = CLASSES

TERMOS: dict[str, dict] = {}


def _t(sigla, pt, en, definicao, ini, inter, avanc, formula="", exemplo="", interp="", limites="", classes=_TODAS, alias=()):
    TERMOS[sigla] = dict(sigla=sigla, pt=pt, en=en, definicao=definicao, iniciante=ini, intermediario=inter, avancado=avanc,
                         formula=formula, exemplo=exemplo, interpretacao=interp, limitacoes=limites, classes=tuple(classes), alias=tuple(alias))


# ------------------------------------------------------------------------------------------------ ações: valor e múltiplos
_t("P/L", "Preço sobre Lucro", "Price-to-Earnings (P/E)",
   "Relação entre o preço da ação e o lucro líquido por ação dos últimos 12 meses.",
   "Mostra quantos anos de lucro, mais ou menos, seriam necessários para a empresa 'devolver' o preço que você paga pela ação, se o lucro se mantiver igual.",
   "Preço ÷ lucro por ação. Múltiplos baixos podem indicar ação barata ou lucro que o mercado espera que caia; múltiplos altos, o contrário. Compare com o setor e com o histórico da própria empresa.",
   "Usa lucro contábil dos últimos 12 meses, sujeito a itens não recorrentes. Para empresas cíclicas, prefira lucro normalizado (média de vários anos). Não é definido com lucro negativo. Diferenças de alavancagem tornam P/L menos comparável que EV/EBITDA.",
   "P/L = Preço da ação ÷ LPA", "Ação a R$ 30 com lucro de R$ 3 por ação: P/L = 10. Seriam cerca de 10 anos de lucro para igualar o preço.",
   "Compare sempre com empresas do mesmo setor e com o próprio histórico. P/L baixo isolado não significa barata.",
   "Lucro negativo ou muito baixo distorce. Lucros pontuais (venda de ativos) distorcem. Setores com crescimento alto têm P/L naturalmente maior.",
   _ACOES, ("P/E",))
_t("P/VP", "Preço sobre Valor Patrimonial", "Price-to-Book (P/B)",
   "Relação entre o preço de mercado e o valor patrimonial por ação ou cota.",
   "Compara o que você paga com o 'patrimônio' registrado da empresa ou do fundo. Abaixo de 1, você paga menos do que o patrimônio contábil indica.",
   "Preço ÷ valor patrimonial por ação (VPA). Muito usado em bancos e FIIs. Abaixo de 1 pode indicar desconto, mas também dúvida do mercado sobre a qualidade dos ativos ou a rentabilidade.",
   "Depende da contabilização dos ativos (custo histórico x valor justo). Em empresas de ativos intangíveis, o patrimônio contábil subestima o valor. Em FIIs de papel, o patrimônio segue a marcação dos CRIs; em FIIs de tijolo, o laudo de avaliação dos imóveis.",
   "P/VP = Preço ÷ VPA", "Ação a R$ 20 com VPA de R$ 25: P/VP = 0,8.",
   "Avalie junto com a rentabilidade (ROE). P/VP baixo com ROE baixo costuma ser justificado.",
   "O valor patrimonial é contábil, não é o valor de venda dos ativos.", ("acoes_br", "acoes_eua", "fiis", "etfs"), ("P/B",))
_t("EV/EBITDA", "Valor da Empresa sobre EBITDA", "Enterprise Value to EBITDA",
   "Valor total da empresa (inclui a dívida líquida) dividido pelo EBITDA.",
   "Mostra quantos anos de lucro operacional da empresa seriam necessários para pagar tudo o que ela vale, incluindo a dívida. Ajuda a comparar empresas com níveis de dívida diferentes.",
   "EV = valor de mercado + dívida líquida (+ minoritários). EBITDA é o resultado operacional antes de depreciação e amortização. Útil para comparar empresas com estruturas de capital distintas.",
   "EBITDA ignora capex, capital de giro e impostos, o que favorece setores intensivos em capital. Verifique a definição de dívida líquida (leasing, minoritários, caixa restrito). Não use em bancos.",
   "EV/EBITDA = (valor de mercado + dívida líquida) ÷ EBITDA", "Valor de mercado R$ 100 mi, dívida líquida R$ 40 mi, EBITDA R$ 20 mi: EV/EBITDA = 7.",
   "Compare dentro do mesmo setor. Valores muito baixos podem indicar queda esperada do lucro.",
   "Ignora investimentos necessários para manter o negócio. Não se aplica a instituições financeiras.", _ACOES)
_t("LPA", "Lucro por Ação", "Earnings per Share (EPS)",
   "Lucro líquido dividido pelo número de ações da empresa.",
   "É a parte do lucro da empresa que 'cabe' a cada ação.",
   "Lucro líquido ÷ número de ações. Base do P/L e do preço justo de Graham.",
   "Usar média ponderada de ações em circulação; o diluído considera opções e conversíveis. Bonificações e desdobramentos exigem ajuste histórico.",
   "LPA = Lucro líquido ÷ número de ações", "Lucro de R$ 1 bi com 500 mi de ações: LPA = R$ 2.",
   "Crescimento consistente do LPA costuma sustentar o preço da ação ao longo do tempo.", "Lucro contábil pode incluir itens não recorrentes.", _ACOES, ("EPS",))
_t("VPA", "Valor Patrimonial por Ação", "Book Value per Share (BVPS)",
   "Patrimônio líquido dividido pelo número de ações (ou cotas).",
   "É o patrimônio contábil da empresa dividido por cada ação.",
   "Patrimônio líquido ÷ número de ações. Base do P/VP e do preço justo de Graham.",
   "Valor contábil sujeito às políticas de avaliação de ativos e a recompras de ações.",
   "VPA = Patrimônio líquido ÷ número de ações", "Patrimônio de R$ 5 bi e 500 mi de ações: VPA = R$ 10.",
   "Compare com o preço para formar o P/VP.", "Não é valor de liquidação da empresa.", ("acoes_br", "acoes_eua", "fiis"), ("BVPS",))
_t("DY", "Rendimento de Dividendos (Dividend Yield)", "Dividend Yield",
   "Proventos pagos nos últimos 12 meses divididos pelo preço atual.",
   "Mostra quanto a empresa ou o fundo devolveu em dinheiro em um ano, comparado com o preço que você paga hoje.",
   "Proventos dos últimos 12 meses ÷ preço. Pode subir porque o provento aumentou ou porque o preço caiu.",
   "Distinguir recorrente de extraordinário. Verificar payout e geração de caixa para avaliar sustentabilidade. Para FIIs, distribuição mensal e obrigatoriedade de repasse do resultado caixa.",
   "DY = Proventos por ação em 12 meses ÷ Preço", "Pagou R$ 3 em 12 meses e a ação custa R$ 50: DY = 6%.",
   "DY alto pode ser sinal de preço caído. Confira se o pagamento é sustentável.", "Passado não garante o futuro. Proventos extraordinários inflam o número.", ("acoes_br", "acoes_eua", "fiis", "etfs"), ("Dividend Yield",))
_t("ROE", "Retorno sobre o Patrimônio Líquido", "Return on Equity",
   "Lucro líquido dividido pelo patrimônio líquido médio.",
   "Mostra quanto a empresa lucra para cada R$ 100 que pertencem aos donos dela.",
   "Lucro líquido ÷ patrimônio líquido. Mede a rentabilidade para o acionista. Pode ser inflado por dívida alta.",
   "Decompor por DuPont (margem × giro × alavancagem). Patrimônio reduzido por recompras ou prejuízos acumulados infla o ROE. Usar patrimônio médio do período.",
   "ROE = Lucro líquido ÷ Patrimônio líquido médio", "Lucro de R$ 20 e patrimônio de R$ 100: ROE = 20%.",
   "Compare com o custo do capital e com o setor. ROE alto sustentado indica negócio rentável.", "Alavancagem eleva o ROE junto com o risco.", _ACOES)
_t("ROIC", "Retorno sobre o Capital Investido", "Return on Invested Capital",
   "Lucro operacional após impostos dividido pelo capital investido (dívida + patrimônio).",
   "Mostra quanto a empresa ganha com todo o dinheiro colocado no negócio, seja dos donos ou emprestado.",
   "NOPAT ÷ capital investido. Compare com o custo de capital (WACC): se o ROIC supera o WACC, a empresa cria valor.",
   "Definição de capital investido varia (com ou sem caixa, leasing, goodwill). Use média do período e alíquota efetiva coerente.",
   "ROIC = NOPAT ÷ (dívida líquida + patrimônio líquido)", "NOPAT de R$ 15 e capital investido de R$ 100: ROIC = 15%.",
   "ROIC acima do WACC por vários anos sugere vantagem competitiva.", "Sensível à definição de capital. Pouco útil para bancos.", _ACOES)
_t("ROI", "Retorno sobre o Investimento", "Return on Investment",
   "Ganho obtido dividido pelo valor investido.",
   "Mostra quanto você ganhou em relação ao que colocou.",
   "(Valor final − valor investido) ÷ valor investido. Não considera o tempo, por isso compare períodos iguais.",
   "Para comparar investimentos de prazos diferentes, anualize (CAGR) ou use TIR.",
   "ROI = (Valor final − Investido) ÷ Investido", "Colocou R$ 1.000 e hoje vale R$ 1.200: ROI = 20%.",
   "Compare sempre com a inflação e com a renda fixa do mesmo período.", "Ignora prazo e risco.", _TODAS)
_t("EBITDA", "Lucro antes de Juros, Impostos, Depreciação e Amortização", "Earnings Before Interest, Taxes, Depreciation and Amortization",
   "Resultado operacional da empresa antes de juros, impostos, depreciação e amortização.",
   "É uma medida do quanto a empresa gera em suas operações, antes de pagar dívida, impostos e desgaste de equipamentos.",
   "Aproxima a geração operacional de caixa. Base do EV/EBITDA e da relação dívida líquida/EBITDA.",
   "Não é medida contábil padronizada (IFRS). Exclui capex, variação de capital de giro e impostos; pode superestimar a geração de caixa em setores intensivos em capital.",
   "EBITDA = Lucro operacional (EBIT) + depreciação + amortização", "EBIT de R$ 80 + depreciação de R$ 20 = EBITDA de R$ 100.",
   "Use junto com fluxo de caixa livre.", "Não é caixa.", _ACOES)
_t("CAGR", "Taxa de Crescimento Anual Composta", "Compound Annual Growth Rate",
   "Taxa anual constante que levaria do valor inicial ao valor final no período.",
   "É a média de quanto algo cresceu por ano, considerando o efeito dos juros sobre juros.",
   "Permite comparar crescimentos de prazos diferentes. Sensível às datas de início e fim.",
   "Valor inicial e final negativos ou zero invalidam o cálculo. Não mostra a volatilidade no caminho.",
   "CAGR = (Valor final ÷ Valor inicial)^(1 ÷ anos) − 1", "De R$ 100 para R$ 161 em 5 anos: CAGR ≈ 10% ao ano.",
   "Verifique se o período escolhido não pegou só o fundo ou o topo do ciclo.", "Esconde quedas e subidas intermediárias.", _TODAS)
_t("FCL", "Fluxo de Caixa Livre", "Free Cash Flow (FCF)",
   "Caixa gerado pela operação depois dos investimentos necessários para manter e crescer o negócio.",
   "É o dinheiro que realmente sobra na empresa depois de pagar as despesas e os investimentos. Dele saem dividendos e pagamento de dívidas.",
   "Fluxo de caixa operacional menos investimentos (capex). Base do DCF.",
   "Distinguir FCL da firma (antes da dívida) do FCL do acionista (após dívida). Normalize capex de expansão x manutenção.",
   "FCL = Caixa operacional − Capex", "Caixa operacional de R$ 50 e capex de R$ 20: FCL = R$ 30.",
   "FCL consistentemente positivo sustenta dividendos.", "Volátil em empresas em expansão.", _ACOES, ("FCF", "Fluxo de caixa livre"))
_t("Fluxo de caixa", "Fluxo de caixa", "Cash flow",
   "Entradas e saídas de dinheiro de uma empresa em um período.",
   "Mostra quanto dinheiro entrou e saiu de verdade, diferente do lucro contábil, que pode incluir valores que ainda não foram recebidos.",
   "Dividido em operacional, de investimento e de financiamento. Lucro alto com caixa fraco é sinal de alerta.",
   "Reconciliar lucro e caixa operacional (variação de capital de giro, itens não caixa).",
   "", "", "Compare o caixa operacional com o lucro líquido ao longo de vários anos.", "", _ACOES)
_t("Margem líquida", "Margem Líquida", "Net Margin",
   "Lucro líquido dividido pela receita.",
   "Mostra quanto sobra de lucro para cada R$ 100 vendidos.",
   "Lucro líquido ÷ receita líquida. Margens variam muito por setor.",
   "Considere itens não recorrentes e efeitos fiscais. Compare com margem operacional para ver o peso de juros e impostos.",
   "Margem líquida = Lucro líquido ÷ Receita líquida", "Receita de R$ 200 e lucro de R$ 20: margem de 10%.",
   "Compare com a própria história e com pares do setor.", "Margens baixas são normais em varejo e altas em software.", _ACOES, ("Margem líq.",))
_t("Margem operacional", "Margem Operacional", "Operating Margin",
   "Lucro operacional (EBIT) dividido pela receita.",
   "Mostra quanto sobra de cada R$ 100 vendidos depois de pagar os custos do negócio, antes de juros e impostos.",
   "EBIT ÷ receita. Mede a eficiência da operação.",
   "Atenção a itens não recorrentes dentro do EBIT.",
   "Margem operacional = EBIT ÷ Receita líquida", "EBIT de R$ 30 e receita de R$ 200: 15%.", "Queda sustentada pode indicar pressão de custos ou concorrência.", "", _ACOES)
_t("Dív./PL", "Dívida sobre Patrimônio Líquido", "Debt-to-Equity",
   "Dívida total (ou líquida) dividida pelo patrimônio líquido.",
   "Compara o que a empresa deve com o que pertence aos donos. Quanto maior, mais ela depende de dinheiro emprestado.",
   "Indicador de alavancagem. Em bancos não se aplica da mesma forma.",
   "Definições variam (bruta/líquida; com ou sem leasing). Patrimônio reduzido infla o indicador.",
   "Dív./PL = Dívida ÷ Patrimônio líquido", "Dívida de R$ 60 e patrimônio de R$ 100: 60%.", "Avalie junto com geração de caixa e custo da dívida.", "", _ACOES, ("Dívida/PL", "Dív. Líq./PL"))
_t("Dívida líquida/EBITDA", "Dívida Líquida sobre EBITDA", "Net Debt to EBITDA",
   "Quantos anos de geração operacional seriam necessários para pagar a dívida líquida.",
   "Mostra em quantos anos a empresa pagaria suas dívidas usando só o que gera nas operações.",
   "Indicador de alavancagem e de risco. Limites variam por setor e contratos.",
   "EBITDA cíclico torna o indicador instável; use EBITDA normalizado.",
   "Dívida líquida ÷ EBITDA", "Dívida líquida de R$ 200 e EBITDA de R$ 100: 2 anos.", "Valores acima de 3 a 4 pedem atenção na maioria dos setores.", "", _ACOES, ("DL/EBITDA",))
_t("Payout", "Percentual do Lucro Distribuído", "Payout Ratio",
   "Parte do lucro que a empresa distribui como dividendos.",
   "Mostra quanto do lucro vira dinheiro para os acionistas.",
   "Dividendos ÷ lucro líquido. Payout muito alto pode não ser sustentável.",
   "Alternativamente, use dividendos ÷ fluxo de caixa livre.", "Payout = Dividendos ÷ Lucro líquido", "Lucro de R$ 100 e dividendos de R$ 40: payout de 40%.",
   "Reflete a política de dividendos da empresa.", "", ("acoes_br", "acoes_eua"))
_t("Graham", "Preço justo de Graham", "Graham Number",
   "Estimativa de valor baseada em lucro e patrimônio por ação (Benjamin Graham).",
   "É uma conta simples que estima o preço 'razoável' de uma ação, usando o lucro e o patrimônio dela.",
   "Fórmula clássica para ações de empresas lucrativas e estáveis.",
   "Assume empresa estável e lucrativa; ignora crescimento, setor e qualidade. É heurística, não valuation completo.",
   "Preço justo = √(22,5 × LPA × VPA)", "LPA R$ 2 e VPA R$ 25: √(22,5×2×25) ≈ R$ 33,5.",
   "Compare com o preço atual para a margem de segurança.", "Não serve para empresas com prejuízo ou setor financeiro com cautela.", ("acoes_br", "acoes_eua"))
_t("Bazin", "Preço-teto de Bazin", "Bazin ceiling price",
   "Preço máximo que se aceita pagar para obter um rendimento mínimo desejado em dividendos (método de Décio Bazin).",
   "Calcula até que preço vale a pena pagar para receber, em dividendos, o rendimento mínimo que você quer.",
   "Dividendo médio ÷ rendimento mínimo desejado (tradicionalmente 6%).",
   "Depende de dividendos passados estáveis; não considera crescimento nem retenção de lucros.",
   "Preço-teto = Dividendo médio por ação ÷ rendimento mínimo", "Dividendo médio de R$ 3 e meta de 6%: teto de R$ 50.",
   "Se o preço está abaixo do teto, o rendimento esperado supera o mínimo desejado.", "Passado não garante dividendos futuros.", ("acoes_br", "acoes_eua"))
_t("DCF", "Fluxo de Caixa Descontado", "Discounted Cash Flow",
   "Valor atual de todo o caixa que a empresa deve gerar no futuro.",
   "Estima quanto a empresa vale hoje somando o dinheiro que ela deve gerar nos próximos anos, trazido a valor de hoje.",
   "Projeta fluxos e desconta por uma taxa (WACC). Muito sensível à taxa e ao crescimento na perpetuidade.",
   "Premissas: período explícito, crescimento terminal g < crescimento da economia, WACC consistente com a moeda. Pequenas mudanças em g e WACC mudam muito o resultado; use cenários.",
   "Valor = Σ FCLₜ ÷ (1+WACC)ᵗ + Valor terminal ÷ (1+WACC)ⁿ", "",
   "Use como faixa de valores, não como preço único.", "Alta sensibilidade às premissas.", _ACOES)
_t("WACC", "Custo Médio Ponderado de Capital", "Weighted Average Cost of Capital",
   "Taxa média que a empresa paga para financiar suas operações, combinando dívida e capital próprio.",
   "É o 'retorno mínimo' que o negócio precisa dar para compensar quem financia a empresa.",
   "Taxa de desconto usada no DCF.",
   "Custo do capital próprio por CAPM (taxa livre de risco + beta × prêmio de risco); custo da dívida após imposto. Pesos a valor de mercado.",
   "WACC = E/V·Re + D/V·Rd·(1−t)", "", "Quanto maior o WACC, menor o valor presente.", "Estimativa de beta e prêmio de risco é incerta.", _ACOES)
_t("Margem de segurança", "Margem de Segurança", "Margin of Safety",
   "Diferença entre o valor estimado e o preço pago, em relação ao valor estimado.",
   "É a folga entre o que você acha que o ativo vale e o que paga. Quanto maior a folga, mais proteção contra erros na conta.",
   "(Valor estimado − preço) ÷ valor estimado. Depende da qualidade da estimativa.",
   "Defina margem mínima conforme a incerteza do modelo.",
   "Margem = (Valor estimado − Preço) ÷ Valor estimado", "Valor de R$ 100 e preço de R$ 70: margem de 30%.", "", "Uma estimativa errada gera margem enganosa.", _TODAS)
_t("Valuation", "Avaliação de Valor (Valuation)", "Valuation",
   "Processo de estimar quanto um ativo vale.",
   "É a tentativa de descobrir se o preço de um ativo está caro, barato ou justo, com base nos números dele.",
   "Combina múltiplos (P/L, EV/EBITDA), fluxo de caixa descontado e comparação com pares.",
   "Resultados dependem de premissas; use mais de um método e cenários.", "", "", "Trate o resultado como faixa, não como número exato.", "", _TODAS)

# ------------------------------------------------------------------------------------------------ risco e carteira
_t("Volatilidade", "Volatilidade", "Volatility",
   "Medida de quanto o preço oscila em torno da média.",
   "Mostra o tamanho dos 'sobe e desce'. Quanto maior, mais o valor muda de um dia para o outro.",
   "Desvio-padrão dos retornos, geralmente anualizado.",
   "Estimativa histórica; assume retornos simétricos e estáveis. Caudas gordas e regimes de crise subestimam o risco.",
   "σ anual ≈ desvio-padrão dos retornos diários × √252", "Desvio diário de 1%: ≈ 15,9% ao ano.",
   "Compare com ativos parecidos e com o seu prazo. Volatilidade não é perda definitiva.", "Olha o passado; não mede risco de perda permanente.", _TODAS, ("oscilação",))
_t("Drawdown", "Queda Máxima desde o Topo (Drawdown)", "Maximum Drawdown",
   "Maior queda do valor em relação ao ponto mais alto anterior.",
   "Mostra o tamanho do tombo no pior momento: quanto o valor caiu desde o ponto mais alto.",
   "Mede a pior perda histórica no período. Tempo de recuperação também importa.",
   "Dependente da janela escolhida; use também duração e recuperação.",
   "Drawdown = Preço ÷ Máximo anterior − 1", "Foi de R$ 100 para R$ 60: drawdown de −40%.", "Pergunte-se se aguentaria uma queda dessas.", "Passado não limita o futuro.", _TODAS)
_t("Sharpe", "Índice de Sharpe", "Sharpe Ratio",
   "Retorno acima da taxa livre de risco por unidade de volatilidade.",
   "Mostra se o ganho compensou o risco assumido. Quanto maior, melhor a relação entre ganho e risco.",
   "(Retorno − taxa livre de risco) ÷ volatilidade.",
   "Assume retornos aproximadamente normais; penaliza também as oscilações para cima. Sensível ao período.",
   "Sharpe = (Rp − Rf) ÷ σp", "Retorno 15%, CDI 10%, volatilidade 20%: Sharpe = 0,25.", "Compare com ativos da mesma classe e período.", "", _TODAS)
_t("Beta", "Beta", "Beta",
   "Sensibilidade do ativo aos movimentos do mercado.",
   "Se for maior que 1, o ativo costuma oscilar mais que o mercado; se for menor que 1, oscila menos.",
   "Covariância com o índice ÷ variância do índice.",
   "Depende do índice e da janela; instável no tempo.", "β = Cov(ativo, mercado) ÷ Var(mercado)", "Beta 1,2: tende a variar 20% mais que o mercado.", "", "", _TODAS)
_t("Correlação", "Correlação", "Correlation",
   "Medida de −1 a +1 de quanto dois ativos se movem juntos.",
   "Perto de 1: sobem e caem juntos. Perto de 0: andam de forma independente. Negativa: tendem a ir em direções opostas.",
   "Coeficiente de Pearson dos retornos. Base da diversificação.",
   "Correlações sobem em crises; medem relação linear.", "ρ = Cov(A,B) ÷ (σA × σB)", "", "", "", _TODAS)
_t("VaR", "Valor em Risco", "Value at Risk",
   "Perda máxima estimada em um período, para um nível de confiança.",
   "Estima quanto você poderia perder em um dia ruim, não no pior dos casos.",
   "Perda que não deve ser excedida com probabilidade dada (ex.: 95%).",
   "Não diz o tamanho da perda além do limite (use Expected Shortfall). Histórico, paramétrico e Monte Carlo diferem.",
   "VaR = quantil dos retornos no nível de confiança", "", "", "Subestima eventos extremos.", ("carteira", "acoes_br", "acoes_eua", "etfs", "cripto"))
_t("Alavancagem", "Alavancagem", "Leverage",
   "Uso de dinheiro emprestado para ampliar a exposição.",
   "É investir com dinheiro de dívida. Aumenta os ganhos quando dá certo e também as perdas.",
   "Medida por dívida/PL, dívida líquida/EBITDA ou exposição bruta/patrimônio.", "Eleva retorno esperado e risco de ruína.", "", "", "", "", _TODAS)
_t("Diversificação", "Diversificação", "Diversification",
   "Distribuir o dinheiro entre ativos que não se movem juntos.",
   "É não colocar todos os ovos na mesma cesta. Um problema em um ativo pesa menos no total.",
   "Reduz risco específico, não o risco de mercado. Depende da correlação entre os ativos.",
   "Número efetivo de ativos = 1 ÷ Σ peso². Correlações sobem em crises.", "", "", "", "", ("carteira", "etfs", "fundos"))
_t("Benchmark", "Referência de Comparação (Benchmark)", "Benchmark",
   "Índice ou taxa usada para comparar o desempenho.",
   "É a régua para saber se o investimento foi bem: por exemplo, o CDI para renda fixa e o Ibovespa para ações.",
   "Escolha uma referência compatível com a estratégia do ativo.", "Benchmark inadequado distorce a conclusão.", "", "", "", "", _TODAS)
_t("Liquidez", "Liquidez", "Liquidity",
   "Facilidade de transformar o ativo em dinheiro sem mexer no preço.",
   "Mostra o quanto é fácil vender quando você quiser. Ativos negociados em grande volume saem rápido.",
   "Medida por volume financeiro médio diário e diferença entre compra e venda (spread).",
   "Liquidez some em crises; volume agregado pode incluir negociações artificiais (cripto).", "", "", "", "", _TODAS)
_t("Spread", "Diferença entre Compra e Venda (Spread)", "Bid-Ask Spread",
   "Diferença entre o preço de venda e o de compra de um ativo. Em crédito, é o prêmio sobre a taxa de referência.",
   "É o custo escondido de comprar e vender na mesma hora: a diferença entre quanto pedem e quanto pagam.",
   "Spreads maiores indicam menor liquidez.", "Em crédito: taxa do título − taxa livre de risco.", "Spread = Preço de venda − Preço de compra", "", "", "", _TODAS)
_t("Tracking error", "Erro de Rastreamento", "Tracking Error",
   "Quanto o retorno do fundo se afasta do índice de referência.",
   "Mostra se o fundo ou ETF consegue copiar bem o índice que promete acompanhar. Quanto menor, melhor a cópia.",
   "Desvio-padrão da diferença de retorno entre fundo e índice.", "Custos, caixa e amostragem explicam diferenças.",
   "TE = σ(retorno do fundo − retorno do índice)", "", "", "", ("etfs", "fundos"))
_t("Taxa de administração", "Taxa de Administração", "Management Fee",
   "Percentual anual cobrado do patrimônio do fundo.",
   "É o que o fundo cobra por ano para administrar o seu dinheiro. Sai do rendimento, sem você ver a cobrança.",
   "Descontada diariamente da cota. Reduz o retorno líquido ano após ano.",
   "Fundos podem ter também taxa de performance, de entrada ou saída.", "", "Taxa de 2% ao ano reduz em 2 pontos o rendimento anual.", "Compare com fundos parecidos.", "", ("fundos", "etfs", "fiis"))
_t("Vacância", "Vacância", "Vacancy Rate",
   "Parte dos imóveis de um fundo imobiliário sem inquilino.",
   "Mostra quanto dos imóveis do fundo está vazio, sem pagar aluguel.", "Área vaga ÷ área total. Vacância alta reduz o rendimento.",
   "Distinguir vacância física e financeira.", "Vacância = Área vaga ÷ Área total", "", "", "", ("fiis",))

# ------------------------------------------------------------------------------------------------ economia e renda fixa
_t("Selic", "Taxa Básica de Juros (Selic)", "Selic rate",
   "Taxa básica de juros da economia brasileira, definida pelo Copom.",
   "É o juro de referência do país. Quando sobe, a renda fixa rende mais e o crédito fica mais caro.",
   "Meta definida pelo Copom; influencia CDI e toda a curva de juros.", "Afeta o desconto de fluxos futuros e o apetite por risco.", "", "", "", "", ("economia", "renda_fixa", "acoes_br", "fiis"))
_t("CDI", "Certificado de Depósito Interbancário (CDI)", "Interbank deposit rate",
   "Taxa dos empréstimos entre bancos, muito próxima da Selic.",
   "É a referência de rendimento da renda fixa. Um CDB de 100% do CDI rende a taxa do CDI.", "Referência de fundos e títulos pós-fixados.", "", "", "", "", "", ("renda_fixa", "fundos", "economia"))
_t("IPCA", "Índice Nacional de Preços ao Consumidor Amplo (IPCA)", "Consumer price index",
   "Índice oficial de inflação do Brasil, medido pelo IBGE.",
   "Mede quanto os preços subiram. Seu dinheiro precisa render mais que isso para não perder valor.", "Referência de títulos IPCA+ e de reajustes.", "", "", "", "", "", ("economia", "renda_fixa"))
_t("Juro real", "Juro Real", "Real interest rate",
   "Rendimento depois de descontada a inflação.",
   "É o ganho de verdade: o que sobra depois que os preços sobem.", "Calculado pela relação entre a taxa nominal e a inflação.",
   "Ex-post usa inflação passada; ex-ante usa expectativas.", "(1 + taxa nominal) ÷ (1 + inflação) − 1", "10% de rendimento e 5% de inflação: ≈ 4,76% de juro real.", "", "", ("renda_fixa", "economia"))
_t("Marcação a mercado", "Marcação a Mercado", "Mark-to-market",
   "Atualização diária do preço de um título pela taxa de mercado.",
   "O preço do título muda todo dia. Se vender antes do vencimento, pode receber mais ou menos do que esperava.",
   "Quando as taxas sobem, os preços de títulos prefixados caem.", "A sensibilidade é dada pela duração.", "", "", "", "", ("renda_fixa", "fundos"))

# ------------------------------------------------------------------------------------------------ cripto
_t("TVL", "Valor Total Bloqueado (TVL)", "Total Value Locked",
   "Valor dos ativos depositados em protocolos de finanças descentralizadas.",
   "Mostra quanto dinheiro as pessoas colocaram para usar um serviço de criptomoedas.",
   "Métrica de adoção de protocolos DeFi. Estimada por provedores como o DefiLlama.", "Sensível ao preço dos ativos depositados. Não é lida diretamente pelo app na blockchain.", "", "", "", "", ("cripto",))
_t("FDV", "Valor de Mercado Totalmente Diluído (FDV)", "Fully Diluted Valuation",
   "Valor de mercado se toda a oferta máxima de moedas já estivesse em circulação.",
   "Mostra quanto o projeto valeria se todas as moedas que ainda serão criadas já existissem. Se for bem maior que o valor atual, ainda há muita moeda por liberar.",
   "FDV = preço × oferta máxima. Comparado ao valor de mercado, indica diluição futura.", "Oferta máxima pode ser indefinida em alguns projetos.",
   "FDV = Preço × Oferta máxima", "", "", "", ("cripto",))
_t("Market cap", "Valor de Mercado", "Market Capitalization",
   "Preço de um ativo multiplicado pela quantidade em circulação.",
   "É o valor total de tudo o que existe do ativo, pelo preço atual.", "Mede o tamanho do ativo; não é dinheiro entrando no projeto.", "", "Valor de mercado = Preço × Quantidade em circulação", "", "", "", _TODAS, ("mcap", "Valor de mercado"))

# ------------------------------------------------------------------------------------------------ técnica
_t("IFR", "Índice de Força Relativa (IFR)", "Relative Strength Index (RSI)",
   "Oscilador de 0 a 100 que compara altas e baixas recentes do preço.",
   "Mostra se o preço subiu ou caiu muito rápido nos últimos dias. Valores muito altos indicam ritmo forte de alta; muito baixos, de queda.",
   "Acima de 70 sugere sobrecompra; abaixo de 30, sobrevenda. Em tendências fortes, pode permanecer nesses extremos.",
   "Período padrão de 14; calculado com média móvel de ganhos e perdas de Wilder. Sinais isolados geram falsos positivos.",
   "IFR = 100 − 100 ÷ (1 + média das altas ÷ média das baixas)", "", "Combine com tendência e volume.", "", ("tecnica", "acoes_br", "acoes_eua", "etfs", "fiis", "cripto"), ("RSI",))
_t("MACD", "Convergência e Divergência de Médias Móveis (MACD)", "Moving Average Convergence Divergence",
   "Diferença entre duas médias móveis exponenciais, com uma linha de sinal.",
   "Indica se o preço está ganhando ou perdendo força e quando a direção pode estar mudando.",
   "Cruzamentos da linha MACD com a de sinal indicam mudança de ritmo.", "Atraso em mercados laterais gera sinais falsos.",
   "MACD = MME(12) − MME(26); sinal = MME(9) do MACD", "", "", "", ("tecnica", "acoes_br", "acoes_eua", "etfs", "fiis", "cripto"))
_t("Média móvel", "Média Móvel", "Moving Average",
   "Média do preço nos últimos N períodos, que se atualiza a cada dia.",
   "Suaviza o sobe e desce do preço para mostrar a direção geral. Preço acima da média sugere tendência de alta.",
   "SMA: média simples; EMA: dá mais peso aos dados recentes.", "Indicador atrasado por construção.", "SMA(n) = soma dos últimos n preços ÷ n", "", "", "", ("tecnica",), ("SMA", "MME", "EMA"))
_t("Come-cotas", "Come-cotas", "Semiannual fund tax",
   "Cobrança antecipada de imposto de renda de fundos, em maio e novembro.",
   "É um imposto que o fundo cobra duas vezes ao ano, tirando uma parte das suas cotas. Seu dinheiro não some: é o imposto sendo pago antes.",
   "Reduz a quantidade de cotas, não o valor investido.", "Alíquotas de 15% ou 20% conforme o tipo de fundo.", "", "", "", "", ("fundos",))


# ------------------------------------------------------------------------------------------------ consulta
def _norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9/]+", " ", s).strip()


_INDICE: dict[str, str] = {}
for _k, _v in TERMOS.items():
    for _n in (_k, _v["pt"], _v["en"], *_v["alias"]):
        _INDICE[_norm(_n)] = _k
        _INDICE[_norm(re.sub(r"\s*\([^)]*\)\s*", " ", _n))] = _k


def achar(termo) -> dict | None:
    """Entrada do glossário para uma sigla, nome em português, nome em inglês ou apelido (sem diferenciar acento/caixa)."""
    return TERMOS.get(_INDICE.get(_norm(termo), ""))


def sigla_de(rotulo) -> str | None:
    """Sigla do glossário para um rótulo de tela ('P/L', 'ROE (%)', 'DY 12m (%)'); None se não for um termo conhecido."""
    e = achar(rotulo)
    if e:
        return e["sigla"]
    r = _norm(re.sub(r"\s*\([^)]*\)\s*", " ", str(rotulo)))
    for suf in (" 12m", " 5a", " 5 anos", " s/ media 5a"):
        r = r.removesuffix(suf)
    return _INDICE.get(r.strip())


def nome_completo(termo, com_sigla: bool = True) -> str:
    """'Preço sobre Lucro (P/L)'. Se o termo não existe, devolve o texto recebido."""
    e = achar(termo)
    if not e:
        return str(termo)
    if f"({e['sigla']})" in e["pt"]:
        return e["pt"]
    if com_sigla and _norm(e["pt"]) != _norm(e["sigla"]):
        return f"{e['pt']} ({e['sigla']})"
    return e["pt"]


def explicacao(termo, modo: str = "intermediario") -> dict | None:
    """Blocos de texto do termo no nível pedido: {'titulo','resumo','linhas':[(rótulo, texto)],'classes'}."""
    e = achar(termo)
    if not e:
        return None
    modo = modo if modo in ("iniciante", "intermediario", "avancado") else "intermediario"
    L = []
    if modo == "iniciante":
        L = [("O que é", e["iniciante"]), ("Exemplo", e["exemplo"]), ("Como interpretar", e["interpretacao"])]
        resumo = e["iniciante"]
    elif modo == "intermediario":
        L = [("Conceito", e["definicao"]), ("Como ler", e["intermediario"]), ("Fórmula", e["formula"]), ("Interpretação", e["interpretacao"]),
             ("Limitações", e["limitacoes"])]
        resumo = e["definicao"]
    else:
        L = [("Metodologia", e["avancado"] or e["intermediario"]), ("Fórmula", e["formula"]), ("Exemplo", e["exemplo"]),
             ("Interpretação", e["interpretacao"]), ("Limitações", e["limitacoes"]), ("Original em inglês", e["en"])]
        resumo = e["definicao"]
    cls = [CLASSE_ROTULO[c] for c in e["classes"]] if len(e["classes"]) < len(CLASSES) else ["Todas as classes de ativos"]
    return {"titulo": nome_completo(e["sigla"]), "resumo": resumo, "linhas": [(a, b) for a, b in L if b], "classes": cls}


def por_classe(classe: str) -> list[str]:
    return [k for k, v in TERMOS.items() if classe in v["classes"]]


def todos() -> list[dict]:
    return list(TERMOS.values())
