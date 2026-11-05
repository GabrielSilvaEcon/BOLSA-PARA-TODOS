"""Modos de experiência (Iniciante · Intermediário · Avançado): regras de apresentação. Módulo puro (sem Streamlit).

O modo muda SÓ a apresentação: organização do menu, painel, explicações, nível de detalhe, tom da IA e dos alertas, quantidade de
indicadores nas tabelas e o estilo dos gráficos. Nunca muda dados, cálculos, carteiras, histórico, alertas, relatórios, assinatura,
preço ou acesso: os três modos têm as mesmas ferramentas, as mesmas classes de ativos e o mesmo plano.
A escolha fica em prefs["modo"] (salva na conta, vale em qualquer aparelho). Ajustes finos em prefs["exp"] (detalhe, explicações, dicas).
"""
from __future__ import annotations

import prefs as P

MODOS = P.MODOS
ROTULOS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}

INFO = {
    "iniciante": {
        "resumo": "Linguagem simples, poucos números e explicações em cada tela.",
        "muda": ["Menu enxuto: as ferramentas avançadas ficam agrupadas em “Mais ferramentas”",
                 "Cada tela abre dizendo para que serve e como ler",
                 "Tabelas com poucos indicadores (os seus favoritos), com opção de ver todos",
                 "Alertas e assistente de IA explicam em palavras simples"],
    },
    "intermediario": {
        "resumo": "Equilíbrio: indicadores principais, menu completo e explicações só quando você pedir.",
        "muda": ["Menu completo como hoje", "Tela limpa, sem faixas explicativas (você pode ligar as dicas)",
                 "Tabelas com os indicadores principais", "Alertas e IA com linguagem direta"],
    },
    "avancado": {
        "resumo": "Tudo à vista: todos os indicadores, notas técnicas e detalhes dos alertas.",
        "muda": ["Ferramentas avançadas sobem para o início do menu", "Cada tela mostra a nota técnica (método, fonte e limites)",
                 "Tabelas com todos os indicadores", "Alertas com detalhes técnicos e IA mais técnica"],
    },
}
NAO_MUDA = ("Carteiras, investimentos, histórico, operações, alertas, relatórios, preferências, progresso educacional, cálculos, "
            "assinatura e preço continuam exatamente iguais. Só muda a apresentação, e você pode voltar quando quiser.")

# ferramentas mais técnicas: no Iniciante ficam agrupadas em "Mais ferramentas"; no Avançado vão para o topo do menu
AVANCADAS = ("tecnica-avancada", "risco", "evolucao", "cripto-onchain", "cripto-receitas", "cripto-fundamentalista", "cripto-avancada", "gestao-carteira")

_LIMITE_IND = {"iniciante": 4, "intermediario": 8, "avancado": 99}
_AJUSTE_DETALHE = {"menos": -2, "auto": 0, "mais": 4}
BLOCOS_OCULTOS_INICIANTE = ("relatorios",)          # só quando a pessoa nunca personalizou o painel


def modo_de(prefs) -> str:
    return P.normalizar(prefs)["modo"]


def trocar_modo(prefs, novo: str) -> dict:
    """Devolve as preferências com SÓ o modo trocado (tudo mais fica idêntico). Modo inválido é ignorado."""
    atual = P.normalizar(prefs)
    if novo not in MODOS:
        return atual
    return P.normalizar({**atual, "modo": novo})


def efetivo(prefs) -> dict:
    """Regras de apresentação que valem para a pessoa: o modo mais os ajustes dela."""
    p = P.normalizar(prefs)
    m, e = p["modo"], p["exp"]
    dicas = {"sim": True, "nao": False}.get(e["dicas"], m != "intermediario")
    expl = {"sim": True, "nao": False}.get(e["explicacoes"], m == "iniciante")
    return {
        "modo": m, "menu": {"iniciante": "essencial", "intermediario": "padrao", "avancado": "completo"}[m],
        "faixa": ("tecnica" if m == "avancado" else "guia") if dicas else None,        # faixa no topo de cada tela
        "explicar_alertas": expl, "alertas_tecnicos": m == "avancado" and e["explicacoes"] != "nao",
        "detalhe": e["detalhe"], "limite_indicadores": max(3, _LIMITE_IND[m] + _AJUSTE_DETALHE[e["detalhe"]]),
        "ia": ia_estilo(m, e["detalhe"], expl),
        "grafico_barra": {"iniciante": False, "intermediario": None, "avancado": True}[m],
    }


def ia_estilo(modo: str, detalhe: str = "auto", explicar: bool | None = None) -> str:
    base = {
        "iniciante": "ESTILO PARA ESTA PESSOA (modo Iniciante): use palavras simples, frases curtas e exemplos do dia a dia; explique todo termo técnico na "
                     "primeira vez que aparecer; no máximo 3 ideias por resposta.",
        "intermediario": "ESTILO PARA ESTA PESSOA (modo Intermediário): linguagem direta; use termos do mercado e explique só os menos comuns.",
        "avancado": "ESTILO PARA ESTA PESSOA (modo Avançado): pode usar termos técnicos sem explicá-los; mostre premissas, fórmulas e limites do método quando ajudar.",
    }[modo if modo in MODOS else "intermediario"]
    extra = {"menos": " Seja ainda mais breve.", "mais": " Dê mais detalhes e passos intermediários."}.get(detalhe, "")
    return base + extra + " Nunca recomende compra ou venda."


def blocos_do_painel(prefs) -> list[str]:
    """Blocos do painel da pessoa, na ordem dela. No Iniciante, quem nunca personalizou o painel recebe uma versão mais enxuta."""
    p = P.normalizar(prefs)
    d = p["dashboard"]
    ocultos = set(d["ocultos"])
    if p["modo"] == "iniciante" and not d["ocultos"] and d["ordem"] == list(P.BLOCOS):
        ocultos |= set(BLOCOS_OCULTOS_INICIANTE)
    return [b for b in d["ordem"] if b not in ocultos]


_IND_COLUNA = {"P/L": "P/L", "P/VP": "P/VP", "Dividend Yield": "DY 12m (%)", "ROE": "ROE (%)", "Margem líquida": "Margem líq. (%)",
               "Dívida/PL": "Dív./PL (%)", "ROIC": None, "Payout": None, "CAGR": None, "Volatilidade": None, "Sharpe": None,
               "Drawdown máximo": None, "Beta": None}


def colunas_indicadores(todas: list[str], prefs) -> list[str]:
    """Quais colunas de indicadores mostrar numa tabela de múltiplos. `todas` = as colunas disponíveis (sem Ticker/Preço).
    Primeiro vêm os indicadores favoritos da pessoa; o limite do modo completa com os demais. Nunca remove dado: só escolhe o que exibir."""
    lim = efetivo(prefs)["limite_indicadores"]
    fav = [c for c in (_IND_COLUNA.get(i) for i in P.normalizar(prefs)["indicadores"]) if c in todas]
    resto = [c for c in todas if c not in fav]
    return (fav + resto)[:lim] if len(todas) > lim else list(todas)


# ---------------------------------------------------------------- textos por tela: (para que serve, como ler, nota técnica)
PAGINAS = {
    "inicio": ("Ponto de partida: escolha o que quer analisar e veja o resumo.", "Comece escolhendo o tipo de ativo e o código; depois siga para a análise.",
               "Os cartões usam as mesmas fontes e cálculos das telas de análise; nada é recalculado aqui."),
    "preco-justo": ("Compara o preço de hoje com um valor justo estimado por Graham e Bazin.", "Margem positiva = preço abaixo do valor estimado. É uma referência, não uma previsão.",
                    "Graham: √(22,5 × LPA × VPA). Bazin: dividendo médio ÷ yield alvo. Não se aplicam bem a empresas sem lucro ou sem dividendos."),
    "dcf": ("Estima quanto a empresa vale pelo dinheiro que deve gerar no futuro.", "Mexer nas premissas mostra como o valor muda: quanto mais incerto o futuro, maior a faixa.",
            "Fluxo de caixa descontado: fluxos projetados trazidos a valor presente por uma taxa de desconto, mais valor terminal. Sensível a crescimento e taxa."),
    "valuation": ("Compara empresas por múltiplos como P/L e P/VP.", "Compare sempre empresas do mesmo setor; múltiplo baixo não significa, sozinho, que está barato.",
                  "Múltiplos vêm de fontes públicas (Fundamentus/Yahoo) e dependem da data do balanço."),
    "dividendos": ("Mostra quanto a empresa distribuiu aos sócios e o rendimento sobre o preço (DY).", "DY muito alto pode ser um sinal de alerta: veja se o dividendo é recorrente.",
                   "DY = dividendos dos últimos 12 meses ÷ preço. Payout e histórico ajudam a avaliar a sustentabilidade."),
    "micro": ("Avalia a saúde financeira: dívida, lucro e eficiência.", "Dívida alta e lucro instável pedem cuidado; compare com o setor.",
              "Indicadores de balanço (dívida/PL, ROE, margens) na data do último balanço disponível."),
    "tecnica": ("Lê o comportamento do preço no gráfico: tendência, suportes e resistências.", "Tendência de alta/baixa descreve o passado; não garante o futuro.",
                "Médias móveis, IFR, MACD e padrões gráficos calculados sobre o histórico de preços."),
    "tecnica-avancada": ("Reúne setups técnicos e testes para quem já lê gráficos.", "Use um setup por vez e olhe o histórico de acertos antes de confiar.",
                         "Setups como inside bar, 9.1, cruzamento de médias, rompimento com volume, FVG e pin bar; sinais são educacionais."),
    "tecnica-cripto": ("Mostra a tendência de uma criptomoeda pelos preços da Binance.", "Cripto oscila muito mais que ações: olhe o risco antes do retorno.",
                       "Dados públicos da Binance; médias móveis, IFR e MACD."),
    "stock-picking": ("Ordena empresas por uma nota de 0 a 100.", "A nota resume vários critérios; olhe os pilares, não só o total.",
                      "Nota ponderada por perfil; modelo simplificado e dependente da qualidade das fontes."),
    "macro": ("Resume a economia: juros, inflação, câmbio e atividade.", "Juros altos tendem a favorecer renda fixa; inflação alta corrói o poder de compra.",
              "Séries do Banco Central, IBGE/Ipeadata e Tesouro; a leitura é descritiva."),
    "carteira": ("Registra suas compras e mostra quanto você ganhou ou perdeu.", "Use a carteira fictícia para praticar sem dinheiro de verdade.",
                 "Preço médio por lote, conversão de dólar pelo câmbio da data e caixa da carteira fictícia."),
    "gestao-carteira": ("Mostra como seu dinheiro está distribuído e sugere equilíbrio.", "Concentração em poucos ativos aumenta o risco.",
                        "Pesos, correlações e otimização educacional; não é recomendação."),
    "risco": ("Mede o quanto sua carteira pode oscilar.", "Volatilidade alta = oscilações maiores, para cima e para baixo.",
              "Volatilidade, drawdown, VaR histórico e limites configuráveis."),
    "relatorios": ("Resumos e fotografias da sua carteira ao longo do tempo.", "Compare fotografias de datas diferentes para ver a evolução.",
                   "Relatórios calculados a partir do histórico real registrado; exportáveis."),
    "simulador": ("Simula como seu dinheiro pode crescer.", "É uma conta com premissas: mude os números e veja o efeito.", "Juros compostos com aportes e taxa informada; sem garantia de retorno."),
    "noticias": ("Notícias e eventos dos seus ativos.", "Leia a fonte antes de tirar conclusões.", "Feeds públicos agregados; a classificação de importância é automática."),
    "inteligencia": ("Cria regras e alertas que acompanham seus ativos.", "Crie poucos alertas e importantes.", "Regras avaliadas pelo monitor automático a cada ciclo."),
    "notificacoes": ("Reúne os avisos do app.", "Comece pelos de importância alta.", "Entrega por canais configuráveis; deduplicação por regra e dia."),
    "educacao": ("Aulas, trilhas e exercícios para aprender investindo.", "Siga uma trilha por vez.", "Conteúdo aberto a todos; o progresso fica salvo na sua conta."),
    "comparar": ("Coloca ativos lado a lado.", "Compare ativos parecidos; misturar classes usa só critérios comuns.",
                 "Pontuação por classe com critérios próprios; períodos e moedas harmonizados."),
    "evolucao": ("Mostra como a empresa cresceu ao longo do tempo.", "Crescimento constante vale mais que um ano excepcional.", "CAGR e séries de balanço de fontes públicas."),
    "fiis": ("Analisa fundos imobiliários.", "Olhe renda mensal, vacância e valor patrimonial.", "Dados da CVM e Fundamentus; P/VP e DY por cota."),
    "fundos-acoes": ("Analisa fundos que investem em ações.", "Compare taxa e retorno com um índice.", "Informes diários da CVM; taxas e retorno em janelas."),
    "multimercados": ("Analisa fundos multimercados.", "Veja se o risco compensou o retorno.", "Informes da CVM; Sharpe e drawdown."),
    "fundos-renda-fixa": ("Analisa fundos de renda fixa.", "Compare com o CDI.", "Informes da CVM; retorno acumulado vs CDI."),
    "etfs": ("Analisa ETFs, fundos que seguem um índice.", "Veja o que tem dentro e quanto cobra.", "Preços e composição de fontes públicas."),
    "renda-fixa": ("Analisa títulos de renda fixa.", "Compare prazo, juros e imposto.", "Marcação simplificada e IR regressivo."),
    "tesouro-cdi": ("Taxas do Tesouro Direto e do CDI.", "Taxa maior costuma vir com prazo maior.", "Taxas do Tesouro e séries do Banco Central."),
    "calculadoras": ("Contas rápidas de investimento.", "Preencha os campos e leia o resultado.", "Fórmulas padrão de matemática financeira."),
    "criptomoedas": ("Visão geral de criptomoedas e como elas são emitidas.", "Valor de mercado e oferta ajudam a comparar moedas.", "Dados públicos de Binance e DefiLlama."),
    "cripto-onchain": ("Mostra o uso real das redes.", "Mais endereços ativos costuma indicar mais uso.", "Dados on-chain públicos (mempool, Blockchair, Snapshot)."),
    "cripto-receitas": ("Mostra quanto os protocolos ganham e emitem.", "Receita do protocolo não é o mesmo que valor para quem tem o token.", "Receita, fees e emissão por protocolo."),
    "cripto-fundamentalista": ("Dá uma nota fundamentalista a criptoativos.", "A nota depende do tipo de ativo.", "Sete pilares com pesos por tipo; sem dado, sem nota."),
    "cripto-avancada": ("Análise aprofundada de criptoativos.", "Use depois de entender o básico.", "Indicadores de DeFi, tokenomics e risco."),
    "ajuda": ("Respostas e diagnóstico do app.", "Procure pelo assunto.", "Mostra o estado das fontes e dos módulos."),
    "planos": ("Mostra o que cada plano oferece por dia.", "Os três modos de experiência e todas as ferramentas valem em todos os planos; muda só a quantidade de uso.", "Limites lidos de planos.py; preços definidos pelo administrador em precificacao.py. Sem cobrança nesta tela."),
    "conta": ("Seus dados, preferências e segurança.", "Aqui você muda seu modo de experiência quando quiser.", "Preferências ficam salvas só na sua conta."),
}


def faixa_da_pagina(url_path: str, prefs) -> dict | None:
    """Conteúdo da faixa no topo da tela para a pessoa: {'tipo': 'guia'|'tecnica', 'titulo', 'linhas': [...]} ou None."""
    ef = efetivo(prefs)
    t = PAGINAS.get(url_path)
    if not ef["faixa"] or not t:
        return None
    if ef["faixa"] == "tecnica":
        return {"tipo": "tecnica", "titulo": "Nota técnica", "linhas": [t[2]]}
    return {"tipo": "guia", "titulo": "Para que serve esta tela", "linhas": [t[0], "Como ler: " + t[1]]}
