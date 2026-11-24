"""Cartas colecionáveis do TickerHunters · CADASTRO GLOBAL (só dados, independente de qualquer jogador).

Para incluir uma empresa nova, basta acrescentar um item em EMPRESAS (o app e o servidor leem tudo daqui; nada fica em componentes
visuais). Os dados financeiros REAIS (P/L, DY e ROE) não ficam aqui: vêm do snapshot do Ticker Battle (battle_dados.py), com fonte e
data. A raridade sai de uma pontuação própria do TickerHunters:
    valor de mercado (0–50) + liquidez (0–30) + relevância de mercado (0–20) = 0–100
    0–34 Comum · 35–54 Rara · 55–79 Épica · 80–100 Lendária
A raridade é FIXADA no cadastro (campo `raridade_fixa`): revisões anuais da pontuação valem só para cartas novas ou correções de cadastro.
Os pontos abaixo são a CLASSIFICAÇÃO INICIAL do TickerHunters (ordem de grandeza de valor de mercado, liquidez e relevância), a revisar.
Sem logotipos oficiais: cada carta usa uma ilustração temática (arquivo em app/assets/cartas/) ou o ícone do setor enquanto não houver arte.
"""
from __future__ import annotations

RARIDADES = ("comum", "rara", "epica", "lendaria")
ROTULO_RARIDADE = {"comum": "Comum", "rara": "Rara", "epica": "Épica", "lendaria": "Lendária"}
FAIXAS = ((80, "lendaria"), (55, "epica"), (35, "rara"), (0, "comum"))
PESOS = {"mercado": 50, "liquidez": 30, "relevancia": 20}
REVISAO = "nov/2026"


def pontuacao(mercado: float, liquidez: float, relevancia: float) -> int:
    """Soma dos três critérios, cada um limitado ao seu teto."""
    return int(round(max(0, min(PESOS["mercado"], mercado)) + max(0, min(PESOS["liquidez"], liquidez)) + max(0, min(PESOS["relevancia"], relevancia))))


def raridade_da_pontuacao(p: float) -> str:
    for minimo, r in FAIXAS:
        if p >= minimo:
            return r
    return "comum"


def _e(tk, nome, setor, icone, atividade, fato, mercado, liquidez, relevancia, arte=None):
    p = pontuacao(mercado, liquidez, relevancia)
    return {"tk": tk, "nome": nome, "setor": setor, "icone": icone, "atividade": atividade, "fato": fato,
            "pontos": {"mercado": mercado, "liquidez": liquidez, "relevancia": relevancia, "total": p},
            "raridade_fixa": raridade_da_pontuacao(p), "arte": arte, "desde": REVISAO}


EMPRESAS = [
    _e("PETR4", "Petrobras", "Petróleo e gás", "🛢️", "Explora, produz e refina petróleo e gás natural.",
       "Maior produtora de petróleo do Brasil, com forte atuação no pré-sal.", 50, 30, 20),
    _e("VALE3", "Vale", "Mineração", "⛏️", "Produz minério de ferro, níquel e cobre.",
       "Uma das maiores produtoras de minério de ferro do mundo.", 48, 29, 19),
    _e("ITUB4", "Itaú Unibanco", "Bancos", "🏦", "Oferece contas, crédito, cartões, seguros e investimentos.",
       "Um dos maiores bancos privados da América Latina.", 48, 28, 19),
    _e("BBAS3", "Banco do Brasil", "Bancos", "🏦", "Banco com forte atuação no crédito ao agronegócio.",
       "Um dos bancos mais antigos do Brasil, fundado em 1808.", 36, 27, 15),
    _e("BBDC4", "Bradesco", "Bancos", "🏦", "Oferece contas, crédito, cartões, seguros e investimentos.",
       "Tem uma das maiores redes de atendimento bancário do país.", 36, 26, 15),
    _e("ABEV3", "Ambev", "Bebidas", "🍺", "Produz e vende cervejas, refrigerantes e outras bebidas.",
       "Faz parte de um dos maiores grupos cervejeiros do mundo.", 38, 22, 14),
    _e("WEGE3", "WEG", "Bens industriais", "⚙️", "Fabrica motores elétricos, geradores e equipamentos de energia.",
       "Nasceu em Jaraguá do Sul (SC) e exporta para muitos países.", 40, 20, 14),
    _e("B3SA3", "B3", "Serviços financeiros", "📈", "Opera a bolsa de valores brasileira e seus sistemas de negociação.",
       "É por ela que passam as negociações de ações no Brasil.", 30, 24, 16),
    _e("SANB11", "Santander Brasil", "Bancos", "🏦", "Banco de varejo e de empresas.",
       "Faz parte de um grupo financeiro espanhol com presença global.", 30, 14, 10),
    _e("SUZB3", "Suzano", "Papel e celulose", "🌳", "Produz celulose de eucalipto e papel.",
       "Uma das maiores produtoras de celulose de eucalipto do mundo.", 26, 16, 10),
    _e("EMBR3", "Embraer", "Aeronáutica", "✈️", "Fabrica aviões comerciais, executivos e de defesa.",
       "Uma das maiores fabricantes de jatos comerciais do mundo.", 24, 18, 11),
    _e("TIMS3", "TIM", "Telecomunicações", "📡", "Oferece telefonia móvel, internet e serviços digitais.",
       "Uma das principais operadoras de celular do Brasil.", 22, 12, 9),
    _e("UGPA3", "Ultrapar", "Combustíveis", "⛽", "Distribui combustíveis e gás pelo país.",
       "É a dona da rede de postos Ipiranga.", 14, 12, 7),
    _e("MGLU3", "Magazine Luiza", "Varejo", "🛍️", "Vende eletrônicos, móveis e muitos outros produtos em lojas e pela internet.",
       "Conhecida pelo marketplace e pela assistente virtual Lu.", 10, 16, 7),
    _e("CPFE3", "CPFL Energia", "Energia elétrica", "⚡", "Gera, transmite e distribui energia elétrica.",
       "Atende milhões de clientes, principalmente no interior de São Paulo.", 18, 8, 7),
    _e("BRKM5", "Braskem", "Petroquímica", "🧪", "Produz resinas plásticas e produtos químicos.",
       "Uma das maiores petroquímicas das Américas.", 8, 10, 7),
    _e("CVCB3", "CVC Brasil", "Turismo", "🏖️", "Oferece pacotes de viagens, passagens e serviços turísticos.",
       "Uma das maiores operadoras de turismo do Brasil.", 2, 6, 5, arte="arte_CVCB3.webp"),
    _e("VAMO3", "Vamos", "Transporte", "🚛", "Aluga e vende caminhões, máquinas e equipamentos pesados.",
       "Atende empresas que preferem alugar a frota em vez de comprar.", 4, 6, 4, arte="arte_VAMO3.webp"),
    _e("LWSA3", "LWSA", "Tecnologia", "☁️", "Oferece soluções de tecnologia, como serviços de nuvem e software.",
       "Atua em áreas como cloud, e-commerce e softwares.", 3, 7, 4, arte="arte_LWSA3.webp"),
]
POR_TK = {e["tk"]: e for e in EMPRESAS}
EXTRAS: dict = {}          # empresas cadastradas pelo admin (tk → nome), preenchido por cartas_dados.catalogo()


def raridade(tk: str) -> str | None:
    e = POR_TK.get(tk)
    return e["raridade_fixa"] if e else None


def da_raridade(r: str) -> list[str]:
    return [e["tk"] for e in EMPRESAS if e["raridade_fixa"] == r]


def setores() -> list[str]:
    return sorted({e["setor"] for e in EMPRESAS})


# ---------------------------------------------------------------------------------------------------- progressão (configurável)
# Cópias EXTRAS (além da primeira) gastas para subir do nível n para n+1, por raridade. Nível máximo = 1 + len(lista).
EVOLUCAO = {
    "comum": [2, 4, 8, 14, 24, 40, 60, 90, 130],
    "rara": [2, 3, 6, 10, 16, 26, 40, 58, 80],
    "epica": [1, 2, 4, 7, 11, 17, 25, 36, 50],
    "lendaria": [1, 1, 2, 3, 5, 8, 12, 16, 22],
}
NIVEL_MAX = 10

# Indicadores do jogo e o bônus de cada melhoria escolhida (a raridade NÃO dá bônus: só nível e escolhas mudam os atributos de jogo).
# rel: fator relativo sobre o valor (P/L menor é melhor → bônus reduz o P/L); pp: soma em pontos (fração: 0,0025 = 0,25 p.p.).
INDICADORES = ("pl", "dy_12m", "roe")
ROTULO_IND = {"pl": "P/L", "dy_12m": "DY", "roe": "ROE"}
BONUS = {"pl": ("rel", -0.04), "dy_12m": ("pp", 0.0025), "roe": ("pp", 0.01)}

# ---------------------------------------------------------------------------------------------------- baús (configurável)
# Cada raridade de baú (as mesmas dos baús que já existem) dá `qtd` cartas, sorteadas por `chances` (pesos por raridade da carta).
# `garantia`: pelo menos uma carta desta raridade ou superior. Duplicatas são normais (são elas que evoluem as cartas).
BAUS = {
    "comum": {"qtd": 2, "chances": {"comum": 72, "rara": 23, "epica": 4, "lendaria": 1}, "garantia": None},
    "raro": {"qtd": 3, "chances": {"comum": 55, "rara": 33, "epica": 10, "lendaria": 2}, "garantia": "rara"},
    "epico": {"qtd": 4, "chances": {"comum": 40, "rara": 35, "epica": 20, "lendaria": 5}, "garantia": "epica"},
    "lendario": {"qtd": 6, "chances": {"comum": 25, "rara": 35, "epica": 28, "lendaria": 12}, "garantia": "lendaria"},
}
# Primeiro acesso à coleção: uma carta de cada raridade jogável no início (comum, rara e épica), para já montar um time de 3.
INICIAL = ("comum", "rara", "epica")
