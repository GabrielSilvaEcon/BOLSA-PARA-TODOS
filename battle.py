"""Ticker Battle · regras do jogo (módulo PURO: sem Streamlit, sem rede, sem gravar nada).

Este módulo NÃO calcula indicadores financeiros: recebe as "cartas" prontas (ver battle_dados.py, que usa a infraestrutura de dados do app) e só
decide o duelo. Tudo aqui é determinístico e roda no servidor; o navegador nunca envia valores, só escolhas (qual carta, qual atributo).

REGRAS
 · Duelo Clássico: 3 rodadas. Vence quem ganhar 2 (ou mais pontos no total). Cada carta só pode ser usada UMA vez por duelo.
 · Por rodada: o jogador escolhe uma carta; o sistema escolhe a adversária por regra fixa (`escolher_adversaria`); o jogador escolhe o atributo;
   o servidor lê os valores da própria carta e aplica a regra do indicador (`resolver`).
 · Regra de cada indicador (INDICADORES): "maior" ou "menor" vence; "menor_positivo" vence o menor valor MAIOR QUE ZERO (P/L e P/VP negativos não valem).
 · Empate: valores iguais na precisão mostrada (`PRECISAO`) → rodada empatada, ninguém pontua. Duelo com placar igual no fim = empate.
 · Comparabilidade: só se compara a MESMA categoria. Entre categorias diferentes só os indicadores marcados `cruzado` (estatística calculada do mesmo
   jeito), e apenas com a mesma moeda. Valor ausente, dado desatualizado (> MAX_IDADE_DIAS) ou indicador fora da categoria bloqueiam a disputa.
 · Nenhuma nota ou pontuação própria é criada: o que vence é o valor real do indicador.
"""
from __future__ import annotations

import hashlib
import math
from datetime import date, datetime

RODADAS = 3
BARALHO_MIN = 3
BARALHO_MAX = 12
MAX_IDADE_DIAS = 10          # dado de referência mais velho que isso não entra em disputa
MIN_ATRIBUTOS_CARTA = 2      # carta com menos indicadores válidos não é jogável
PRECISAO = 4                 # casas usadas para decidir empate (em fração/razão; ex.: 0,0001 = 0,01 p.p.)

CATEGORIAS = {
    "acao": {"nome": "Ações", "cor": "#8B6CFF", "icone": "📈"},
    "fii": {"nome": "FIIs", "cor": "#2BA7C9", "icone": "🏢"},
    "etf": {"nome": "ETFs", "cor": "#D23FC8", "icone": "🧺"},
    "cripto": {"nome": "Criptomoedas", "cor": "#F2B84B", "icone": "🪙"},
}

# id: dados do indicador. `melhor`: quem vence. `fmt`: pct | x. `classes`: categorias em que o indicador existe e tem o mesmo significado.
# `cruzado`: pode comparar categorias diferentes (mesma conta, mesma moeda).
INDICADORES = {
    "dy_12m": {"nome": "Dividendos", "curto": "Div. Yield 12m", "grupo": "Dividendos", "icone": "paid", "melhor": "maior", "fmt": "pct",
               "classes": ("acao", "fii", "etf"), "cruzado": False,
               "significa": "Quanto o ativo pagou de proventos nos últimos 12 meses em relação ao preço atual (dividend yield).",
               "relevancia": "Mostra a renda que o ativo gerou para quem o segurou. É muito usado por quem busca renda recorrente.",
               "regra": "Maior é melhor: mais renda por real investido.",
               "limites": "Olha só o passado. Pode subir porque o preço caiu, ou por um provento extraordinário que não se repete.",
               "nao_conclui": "Não diz se a empresa ou o fundo vai continuar pagando, nem se o ativo é bom ou barato."},
    "ret_12m": {"nome": "Rentabilidade", "curto": "Retorno 12m", "grupo": "Rentabilidade", "icone": "show_chart", "melhor": "maior", "fmt": "pct",
                "classes": ("acao", "fii", "etf", "cripto"), "cruzado": True,
                "significa": "Retorno total dos últimos 12 meses: variação do preço somada aos proventos reinvestidos.",
                "relevancia": "Resume o que o ativo entregou no período, já contando a renda recebida.",
                "regra": "Maior é melhor.",
                "limites": "Depende do período escolhido (12 meses) e da moeda em que o preço é cotado. Retorno passado não se repete por regra.",
                "nao_conclui": "Não diz o risco que foi assumido para chegar nesse retorno nem o que acontecerá daqui para frente."},
    "vol": {"nome": "Volatilidade", "curto": "Volatilidade", "grupo": "Volatilidade", "icone": "swap_vert", "melhor": "menor", "fmt": "pct",
            "classes": ("acao", "fii", "etf", "cripto"), "cruzado": True,
            "significa": "Oscilação anualizada dos retornos diários. Quanto maior, mais o preço balança para cima e para baixo.",
            "relevancia": "É uma medida simples de risco de preço: ativos mais calmos assustam menos no curto prazo.",
            "regra": "Menor é melhor (menos oscilação).",
            "limites": "Trata altas e baixas do mesmo jeito e usa só o histórico recente.",
            "nao_conclui": "Baixa volatilidade não é ausência de risco, e alta volatilidade não é, sozinha, sinal de ativo ruim."},
    "queda_max": {"nome": "Queda máxima", "curto": "Queda máx. 12m", "grupo": "Solidez", "icone": "trending_down", "melhor": "menor", "fmt": "pct",
                  "classes": ("acao", "fii", "etf", "cripto"), "cruzado": True,
                  "significa": "Maior queda do pico ao vale nos últimos 12 meses (drawdown máximo).",
                  "relevancia": "Mostra o pior tombo que um investidor teria enfrentado no período.",
                  "regra": "Menor é melhor (queda menos profunda).",
                  "limites": "Considera só 12 meses e um único pior momento.",
                  "nao_conclui": "Não prevê quedas futuras nem diz se o ativo se recuperou depois."},
    "roe": {"nome": "ROE", "curto": "ROE", "grupo": "Rentabilidade", "icone": "savings", "melhor": "maior", "fmt": "pct",
            "classes": ("acao",), "cruzado": False,
            "significa": "Retorno sobre o patrimônio líquido: quanto lucro a empresa gera para cada real de capital dos acionistas.",
            "relevancia": "Indica a eficiência da empresa em transformar o capital dos sócios em lucro.",
            "regra": "Maior é melhor.",
            "limites": "Empresas muito endividadas podem ter ROE alto por causa da dívida, não só da eficiência. Setores diferentes têm patamares diferentes.",
            "nao_conclui": "Não diz se o preço da ação está caro ou barato."},
    "margem_liq": {"nome": "Margem líquida", "curto": "Margem líquida", "grupo": "Rentabilidade", "icone": "percent", "melhor": "maior", "fmt": "pct",
                   "classes": ("acao",), "cruzado": False,
                   "significa": "Parte da receita que sobra como lucro depois de todos os custos, despesas e impostos.",
                   "relevancia": "Mostra quanto do que a empresa vende vira lucro de verdade.",
                   "regra": "Maior é melhor.",
                   "limites": "Varia muito entre setores (varejo costuma ter margem baixa; software, alta) e pode ser afetada por ganhos não recorrentes.",
                   "nao_conclui": "Não mostra se o lucro está crescendo nem se ele é sustentável."},
    "pl": {"nome": "Valuation (P/L)", "curto": "P/L", "grupo": "Valuation", "icone": "calculate", "melhor": "menor_positivo", "fmt": "x",
           "classes": ("acao",), "cruzado": False,
           "significa": "Preço dividido pelo lucro por ação: quantos anos de lucro atual o mercado está pagando pela ação.",
           "relevancia": "É a régua mais comum para saber se uma ação está cara ou barata em relação ao que lucra.",
           "regra": "Menor (e positivo) é melhor. P/L negativo (prejuízo) não entra na disputa.",
           "limites": "Lucro de um único ano pode ser fora do normal. Empresas que crescem rápido costumam ter P/L maior por bons motivos.",
           "nao_conclui": "P/L baixo pode indicar uma armadilha de valor; não é recomendação de compra."},
    "pvp": {"nome": "Preço/Valor Patrimonial", "curto": "P/VP", "grupo": "Valuation", "icone": "balance", "melhor": "menor_positivo", "fmt": "x",
            "classes": ("acao",), "cruzado": False,
            "significa": "Preço dividido pelo valor patrimonial por ação: quanto o mercado paga por cada real de patrimônio contábil.",
            "relevancia": "Compara o preço com o que a empresa tem registrado em seu balanço.",
            "regra": "Menor (e positivo) é melhor.",
            "limites": "O valor contábil pode estar defasado em relação ao valor real dos ativos, e empresas leves em ativos têm P/VP alto naturalmente.",
            "nao_conclui": "Não diz se a empresa lucra bem nem se o balanço é saudável."},
    "div_pl": {"nome": "Solidez (Dívida/PL)", "curto": "Dívida/PL", "grupo": "Solidez", "icone": "shield", "melhor": "menor", "fmt": "pct",
               "classes": ("acao",), "cruzado": False,
               "significa": "Dívida da empresa em relação ao patrimônio dos acionistas.",
               "relevancia": "Mostra o quanto a empresa depende de dinheiro emprestado, o que pesa mais em crises e com juros altos.",
               "regra": "Menor é melhor (menos dívida para o mesmo patrimônio).",
               "limites": "Alguns setores (bancos, concessões) usam dívida como parte do negócio, e o prazo e o custo da dívida não aparecem aqui.",
               "nao_conclui": "Não diz se a empresa consegue pagar a dívida: isso depende do caixa e do prazo."},
}
ORDEM_IND = tuple(INDICADORES)


# ------------------------------------------------------------------ valores
def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if math.isfinite(x) else None


def valor_valido(ind: str, v) -> bool:
    """O valor existe e faz sentido para a regra do indicador (ex.: P/L negativo não vale; volatilidade zero indica série sem variação)."""
    x = _num(v)
    if x is None or ind not in INDICADORES:
        return False
    if INDICADORES[ind]["melhor"] == "menor_positivo":
        return x > 0
    if ind in ("dy_12m", "div_pl", "vol", "queda_max"):
        return x >= 0 if ind != "vol" else x > 0
    return True


def formatar(ind: str, v) -> str:
    x = _num(v)
    if x is None:
        return "—"
    if INDICADORES[ind]["fmt"] == "x":
        return f"{x:.1f}x".replace(".", ",")
    return f"{x * 100:.1f}%".replace(".", ",")


def idade_dias(carta: dict, hoje: date) -> int | None:
    try:
        return (hoje - date.fromisoformat(str(carta.get("ref"))[:10])).days
    except (TypeError, ValueError):
        return None


def desatualizada(carta: dict, hoje: date) -> bool:
    i = idade_dias(carta, hoje)
    return i is None or i > MAX_IDADE_DIAS


def indicadores_validos(carta: dict) -> list[str]:
    """Indicadores da carta que existem na categoria dela e têm valor válido, na ordem padrão."""
    cl = carta.get("classe")
    ind = carta.get("ind") or {}
    return [i for i in ORDEM_IND if cl in INDICADORES[i]["classes"] and valor_valido(i, ind.get(i))]


def jogavel(carta: dict, hoje: date) -> tuple[bool, str]:
    if carta.get("classe") not in CATEGORIAS:
        return False, "Categoria não suportada no Battle."
    if desatualizada(carta, hoje):
        return False, "Dados desatualizados: a carta fica de fora até a próxima atualização."
    if len(indicadores_validos(carta)) < MIN_ATRIBUTOS_CARTA:
        return False, "Poucos indicadores disponíveis para este ativo."
    return True, ""


# ------------------------------------------------------------------ comparação
def bloqueio(a: dict, b: dict, ind: str, hoje: date) -> str:
    """Motivo pelo qual `ind` NÃO pode ser disputado entre as cartas `a` e `b` (texto vazio = pode)."""
    if ind not in INDICADORES:
        return "Indicador desconhecido."
    meta = INDICADORES[ind]
    ca, cb = a.get("classe"), b.get("classe")
    if ca not in meta["classes"] or cb not in meta["classes"]:
        return f"{meta['curto']} não existe para esta categoria."
    if ca != cb:
        if not meta["cruzado"]:
            return f"{meta['curto']} só compara ativos da mesma categoria."
        if a.get("moeda") != b.get("moeda"):
            return "As cartas usam moedas diferentes: não há comparação direta."
    for c in (a, b):
        if desatualizada(c, hoje):
            return f"Dados de {c.get('tk')} desatualizados."
        if not valor_valido(ind, (c.get("ind") or {}).get(ind)):
            return f"Sem dado válido de {meta['curto']} para {c.get('tk')}."
    return ""


def atributos_disputaveis(a: dict, b: dict, hoje: date) -> dict:
    """{'ok': [ids], 'bloqueados': {id: motivo}} para o par de cartas (só entre indicadores que o jogador veria nas duas)."""
    ok, bl = [], {}
    for i in ORDEM_IND:
        if a.get("classe") not in INDICADORES[i]["classes"] and b.get("classe") not in INDICADORES[i]["classes"]:
            continue
        m = bloqueio(a, b, i, hoje)
        if m:
            bl[i] = m
        else:
            ok.append(i)
    return {"ok": ok, "bloqueados": bl}


def resolver(a: dict, b: dict, ind: str, hoje: date) -> dict:
    """Compara `a` (jogador) e `b` (adversário) em `ind`. Levanta ValueError se a disputa for inválida.
    Devolve {venc: 'jogador'|'adversario'|'empate', va, vb, melhor, barra_a (0..1, só visual)}."""
    m = bloqueio(a, b, ind, hoje)
    if m:
        raise ValueError(m)
    va, vb = float(a["ind"][ind]), float(b["ind"][ind])
    melhor = INDICADORES[ind]["melhor"]
    if round(va, PRECISAO) == round(vb, PRECISAO):
        venc = "empate"
    elif melhor == "maior":
        venc = "jogador" if va > vb else "adversario"
    else:                                                     # "menor" e "menor_positivo": o menor valor vence (os inválidos já foram barrados)
        venc = "jogador" if va < vb else "adversario"
    ma, mb = abs(va), abs(vb)
    barra = 0.5 if (ma + mb) == 0 else ma / (ma + mb)         # só proporção visual das barras; não é nota
    return {"venc": venc, "va": va, "vb": vb, "melhor": melhor, "barra_a": barra}


# ------------------------------------------------------------------ adversário (regra fixa, reproduzível)
def escolher_adversaria(seed: str, rodada: int, carta_jog: dict, pool: list[dict], usadas: list[str], hoje: date) -> dict | None:
    """O sistema escolhe a carta adversária SEM olhar o atributo (que o jogador ainda não escolheu) nem os valores:
    1) candidatas = cartas do pool (fora do baralho do jogador e ainda não usadas pelo sistema) da MESMA categoria, jogáveis e com pelo menos um
       atributo disputável com a carta do jogador; 2) ordena por ticker; 3) escolhe o índice = hash(seed|rodada|ticker do jogador) mod N.
    Mesmo duelo + mesmas escolhas = mesma adversária."""
    cand = sorted((c for c in pool if c["tk"] not in usadas and c.get("classe") == carta_jog.get("classe") and c["tk"] != carta_jog["tk"]
                   and jogavel(c, hoje)[0] and atributos_disputaveis(carta_jog, c, hoje)["ok"]), key=lambda c: c["tk"])
    if not cand:
        return None
    h = int(hashlib.sha256(f"{seed}|{rodada}|{carta_jog['tk']}".encode()).hexdigest()[:12], 16)
    return cand[h % len(cand)]


# ------------------------------------------------------------------ baralho
def validar_baralho(tks: list[str], cartas: dict, hoje: date) -> tuple[bool, str]:
    """Regras do baralho: sem repetição, entre BARALHO_MIN e BARALHO_MAX cartas, todas existentes e jogáveis."""
    if len(set(tks)) != len(tks):
        return False, "Há cartas repetidas no baralho."
    if len(tks) < BARALHO_MIN:
        return False, f"Escolha pelo menos {BARALHO_MIN} cartas (uma para cada rodada)."
    if len(tks) > BARALHO_MAX:
        return False, f"O baralho aceita no máximo {BARALHO_MAX} cartas."
    for t in tks:
        c = cartas.get(t)
        if not c:
            return False, f"A carta {t} não está disponível."
        ok, m = jogavel(c, hoje)
        if not ok:
            return False, f"{t}: {m}"
    return True, ""


def baralho_padrao(cartas: dict, hoje: date, ordem: tuple = ("PETR4", "VALE3", "ITUB4", "WEGE3", "HGLG11", "KNRI11", "BOVA11", "IVVB11", "CRIPTO:BTC", "CRIPTO:ETH")) -> list[str]:
    """Sugestão inicial (a pessoa edita): as primeiras cartas jogáveis da lista fixa, até 6."""
    return [t for t in ordem if t in cartas and jogavel(cartas[t], hoje)[0]][:6]


# ------------------------------------------------------------------ duelo
def novo_duelo(duelo_id: str, seed: str, deck: list[str], agora: datetime, ref_dados: str = "") -> dict:
    return {"id": duelo_id, "seed": seed, "ts": agora.strftime("%Y-%m-%dT%H:%M:%S"), "deck": list(deck), "modo": "classico", "adversario": "sistema",
            "rodadas": [], "usadas_jog": [], "usadas_adv": [], "placar": {"jogador": 0, "adversario": 0, "empates": 0}, "final": None,
            "dados_gerados_em": ref_dados}


def rodada_atual(duelo: dict) -> int:
    return len(duelo["rodadas"]) + 1


def terminou(duelo: dict) -> bool:
    return len(duelo["rodadas"]) >= RODADAS


def cartas_disponiveis(duelo: dict) -> list[str]:
    return [t for t in duelo["deck"] if t not in duelo["usadas_jog"]]


def adversaria_da_rodada(duelo: dict, cartas: dict, tk_jog: str, hoje: date) -> dict | None:
    """Adversária que o sistema usará se o jogador escolher `tk_jog` agora (recalculada no servidor, nunca aceita do navegador)."""
    if tk_jog not in cartas_disponiveis(duelo) or tk_jog not in cartas:
        return None
    pool = [c for t, c in cartas.items() if t not in duelo["deck"]]
    return escolher_adversaria(duelo["seed"], rodada_atual(duelo), cartas[tk_jog], pool, duelo["usadas_adv"], hoje)


def jogar_rodada(duelo: dict, cartas: dict, tk_jog: str, ind: str, hoje: date) -> dict:
    """Executa a rodada atual e devolve o duelo atualizado (cópia rasa). ValueError se a jogada for inválida."""
    if terminou(duelo):
        raise ValueError("O duelo já terminou.")
    if tk_jog not in duelo["deck"] or tk_jog in duelo["usadas_jog"]:
        raise ValueError("Carta indisponível nesta rodada.")
    adv = adversaria_da_rodada(duelo, cartas, tk_jog, hoje)
    if adv is None:
        raise ValueError("Não há carta adversária compatível com esta carta.")
    a = cartas[tk_jog]
    res = resolver(a, adv, ind, hoje)
    n = rodada_atual(duelo)
    reg = {"n": n, "jog": tk_jog, "adv": adv["tk"], "ind": ind, "va": res["va"], "vb": res["vb"], "venc": res["venc"], "melhor": res["melhor"],
           "barra_a": res["barra_a"], "ref_jog": a.get("ref"), "ref_adv": adv.get("ref"), "fonte_jog": a.get("fonte", ""), "fonte_adv": adv.get("fonte", "")}
    d = {**duelo, "rodadas": duelo["rodadas"] + [reg], "usadas_jog": duelo["usadas_jog"] + [tk_jog], "usadas_adv": duelo["usadas_adv"] + [adv["tk"]],
         "placar": dict(duelo["placar"])}
    chave = {"jogador": "jogador", "adversario": "adversario", "empate": "empates"}[res["venc"]]
    d["placar"][chave] += 1
    if terminou(d):
        d["final"] = resultado_final(d)
    return d


def resultado_final(duelo: dict) -> str:
    p = duelo["placar"]
    return "vitoria" if p["jogador"] > p["adversario"] else ("derrota" if p["jogador"] < p["adversario"] else "empate")


def pode_jogar_alguma(duelo: dict, cartas: dict, hoje: date) -> bool:
    """Ainda existe ao menos uma carta do jogador com adversária e atributo possíveis? (evita duelo travado)."""
    return any(adversaria_da_rodada(duelo, cartas, t, hoje) for t in cartas_disponiveis(duelo))


# ------------------------------------------------------------------ texto educativo (Raio-X)
def explicar(reg: dict, cartas: dict) -> dict:
    """Textos da rodada, a partir do registro dela: significado, relevância, regra, quem venceu e por quê, limites e o que não se pode concluir."""
    m = INDICADORES[reg["ind"]]
    a, b = cartas.get(reg["jog"], {}), cartas.get(reg["adv"], {})
    ta, tb = a.get("tk", reg["jog"]), b.get("tk", reg["adv"])
    fa, fb = formatar(reg["ind"], reg["va"]), formatar(reg["ind"], reg["vb"])
    if reg["venc"] == "empate":
        porque = f"{ta} e {tb} ficaram com o mesmo valor ({fa}); pela regra, a rodada empata e ninguém pontua."
    else:
        v, p = (ta, tb) if reg["venc"] == "jogador" else (tb, ta)
        fv, fp = (fa, fb) if reg["venc"] == "jogador" else (fb, fa)
        how = "maior" if m["melhor"] == "maior" else "menor"
        porque = f"{v} venceu com {fv} contra {fp} de {p}: nesta métrica, o {how} valor leva a rodada."
    return {"nome": m["nome"], "significa": m["significa"], "relevancia": m["relevancia"], "regra": m["regra"], "porque": porque,
            "limites": m["limites"], "nao_conclui": m["nao_conclui"]}


def resumo_educativo(reg: dict, cartas: dict) -> str:
    """Uma frase curta para a Arena (o Raio-X completo fica na tela final)."""
    e = explicar(reg, cartas)
    return f"{e['nome']}: {e['significa']} {e['porque']}"
