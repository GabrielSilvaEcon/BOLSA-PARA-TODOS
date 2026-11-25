"""Setups de trading colecionáveis do Trade Game: catálogo, detecção, coleção e sorteio nos baús (módulo PURO: sem rede, sem banco).

Cada setup mora numa pasta própria, `app/assets/setups/<id>/`, com um `setup.json` e as artes dele:

    setup.json   id, nome, raridade, resumo, caracteristicas[], indicadores[], regra{compra, venda}, cores{principal, brilho},
                 assets{carta, ativacao, moldura, icone, efeitos[]}      (nomes de arquivo DENTRO da pasta; null = ainda provisório)
    carta.webp, ativacao.webp, moldura.webp, icone.webp, efeitos/...     as artes, quando forem enviadas

Trocar uma arte provisória pela definitiva = copiar o arquivo para a pasta do setup e preencher o nome no setup.json. Nenhum código muda.
O arquivo só vale se existir de fato na pasta: um nome digitado errado não vira link quebrado no app, o setup continua provisório.
Setup novo = pasta nova + uma função em DETECTORES + uma linha no pubspec.yaml (o Flutter só empacota as pastas que estão listadas lá).

DETECÇÃO. Cada detector recebe os candles FECHADOS, do mais antigo ao mais novo, e avalia somente o último deles. Não existe parâmetro por onde o
futuro possa entrar, e o histórico entra só como insumo das médias e dos canais (nunca como lugar onde procurar sinal). Quem decide QUAL candle avaliar,
e quando, é setups_vivo.py.
"""
from __future__ import annotations

import functools
import json
import os

import cartas as C
import cartas_catalogo as CAT

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "assets", "setups")
SLOTS = ("carta", "ativacao", "moldura", "icone")        # artes únicas por setup; `efeitos` é uma lista
CAMPOS_TEXTO = ("resumo",)


class ErroSetup(ValueError):
    pass


# ------------------------------------------------------------------ indicadores (só o que os detectores usam)
def _sma(v: list[float], n: int, fim: int | None = None) -> float | None:
    """Média simples dos `n` valores que terminam em `fim` (exclusivo; padrão: o último)."""
    fim = len(v) if fim is None else fim
    if n <= 0 or fim < n or fim > len(v):
        return None
    return sum(v[fim - n:fim]) / n


def _ema(v: list[float], n: int) -> list[float | None]:
    """Média exponencial, semeada pela média simples dos `n` primeiros valores. Alinhada a `v`: None antes de existir."""
    out: list[float | None] = [None] * len(v)
    if len(v) < n:
        return out
    e = sum(v[:n]) / n
    out[n - 1] = e
    k = 2 / (n + 1)
    for i in range(n, len(v)):
        e = v[i] * k + e * (1 - k)
        out[i] = e
    return out


def _rsi(c: list[float], n: int = 14) -> float | None:
    """IFR de Wilder no último candle."""
    if len(c) <= n:
        return None
    ganho = perda = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]
        ganho, perda = ganho + max(d, 0.0), perda + max(-d, 0.0)
    ganho, perda = ganho / n, perda / n
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]
        ganho, perda = (ganho * (n - 1) + max(d, 0.0)) / n, (perda * (n - 1) + max(-d, 0.0)) / n
    return 100.0 if perda == 0 else 100 - 100 / (1 + ganho / perda)


# ------------------------------------------------------------------ detectores
# Parâmetros nomeados: são o que se ajusta para o setup ficar mais ou menos frequente. Cada ativação pausa os DOIS jogadores por alguns segundos,
# então a frequência é parte do jogo. Valores escolhidos por medição, em 360 partidas simuladas (60 por duração, com e sem regimes de tendência),
# com as constantes finais do motor (recarga de 8 candles, teto de 2 por jogador): média de ativações por partida e % das partidas com pelo menos uma —
#   Clássico 0,94 (66%) · Turtle 1,03 (64%) · Larry Williams 1,30 (74%) · Minervini 0,39 (24%).
# É mercado simulado (o ambiente não tem dado real): serve para dar a ordem de grandeza, não para prometer a frequência do mercado de verdade.
# Os primeiros valores que escolhi davam 30 sinais a cada 100 candles num setup e quase nenhum em outro.
CLASSICO_RAPIDA, CLASSICO_LENTA, CLASSICO_MARGEM_IFR = 9, 21, 7      # compra pede IFR >= 50 + margem; venda, IFR <= 50 - margem
TURTLE_CANAL, TURTLE_SAIDA, TURTLE_ATR, TURTLE_STOP_ATR = 20, 10, 20, 2.0      # a carta: máxima de 20 candles; stop = o mais curto entre a mínima de 10 e 2 ATR
LW_MEDIA, LW_ALVO_R, LW_VALIDADE, LW_MIN_CANDLES = 9, 2.0, 1, 40   # MME9; alvo = 2x o risco; o gatilho vale só para o candle seguinte
LW_TENDENCIA, LW_VENDE = 50, False                                  # só opera a favor da MME50; a carta só descreve a COMPRA (LW_VENDE liga o espelho)
MM_TOPO = 0.75                                                         # fechamento a no máximo 25% do topo da janela (a regra original)
MM_JANELA, MM_CONTRACAO, MM_PIVO, MM_VOLUME = 250, 1.0, 5, 0.8
MM_BASE, MM_ALVO_R = 15, 3.0                                           # fundo da contração (VCP) = mínima dos últimos 15 candles; alvo 3:1 (a carta)


def _classico(v: list[dict]) -> dict | None:
    """Setup Clássico: a média exponencial de 9 cruza a de 21, o candle fecha do lado certo da de 21 e o IFR confirma a força (57 ou mais na
    compra, 43 ou menos na venda)."""
    if len(v) < CLASSICO_LENTA + 15:
        return None
    c = [x["c"] for x in v]
    rapida, lenta = _ema(c, CLASSICO_RAPIDA), _ema(c, CLASSICO_LENTA)
    ifr = _rsi(c)
    if None in (rapida[-1], rapida[-2], lenta[-1], lenta[-2], ifr):
        return None
    if rapida[-2] <= lenta[-2] and rapida[-1] > lenta[-1] and c[-1] > lenta[-1] and ifr >= 50 + CLASSICO_MARGEM_IFR:
        return {"direcao": "alta", "motivo": f"A média de {CLASSICO_RAPIDA} cruzou para cima a de {CLASSICO_LENTA}, com IFR em {ifr:.0f}."}
    if rapida[-2] >= lenta[-2] and rapida[-1] < lenta[-1] and c[-1] < lenta[-1] and ifr <= 50 - CLASSICO_MARGEM_IFR:
        return {"direcao": "baixa", "motivo": f"A média de {CLASSICO_RAPIDA} cruzou para baixo a de {CLASSICO_LENTA}, com IFR em {ifr:.0f}."}
    return None


def _atr(v: list[dict], n: int) -> float | None:
    """Média do intervalo verdadeiro dos últimos `n` candles (o candle atual entra)."""
    if len(v) < n + 1:
        return None
    tr = [max(v[i]["h"] - v[i]["l"], abs(v[i]["h"] - v[i - 1]["c"]), abs(v[i]["l"] - v[i - 1]["c"])) for i in range(len(v) - n, len(v))]
    return sum(tr) / n


def _turtle(v: list[dict]) -> dict | None:
    """Turtle Trading (só compra, como na carta): o candle fecha acima da máxima dos `TURTLE_CANAL` candles anteriores (canal de Donchian) e é o
    PRIMEIRO a fazer isso: depois de um rompimento os candles seguintes também fecham acima do canal antigo, e isso não é um sinal novo.
    Stop: o mais curto entre a mínima dos últimos `TURTLE_SAIDA` candles e `TURTLE_STOP_ATR` ATR abaixo da entrada. Sem alvo fixo: segue a tendência."""
    if len(v) < max(TURTLE_CANAL + 2, TURTLE_ATR + 2):
        return None
    janela, a, ant = v[-TURTLE_CANAL - 1:-1], v[-1], v[-2]
    canal_ant = v[-TURTLE_CANAL - 2:-2]
    if not (a["c"] > max(x["h"] for x in janela) and not ant["c"] > max(x["h"] for x in canal_ant)):
        return None
    atr = _atr(v, TURTLE_ATR)
    if not atr:
        return None
    stop = max(min(x["l"] for x in v[-TURTLE_SAIDA - 1:-1]), a["c"] - TURTLE_STOP_ATR * atr)
    if stop >= a["c"]:
        return None
    return {"direcao": "alta", "stop": round(stop, 4), "motivo": f"Primeiro fechamento acima da máxima dos últimos {TURTLE_CANAL} candles."}


def _larry(v: list[dict]) -> dict | None:
    """Larry Williams, como diz a carta: "compra na superação da máxima do candle que fez a MME9 virar para cima". Alvo 2:1, stop na mínima.
    Este é um setup ARMADO: no fechamento do candle de virada ele só prepara o gatilho (a máxima do candle); quem dispara é o preço, nos candles
    seguintes. Devolve o gatilho, o stop (a mínima do candle) e o alvo (2 vezes o risco). Espelhado para a venda."""
    if len(v) < LW_MIN_CANDLES:
        return None
    c = [x["c"] for x in v]
    e = _ema(c, LW_MEDIA)
    if None in (e[-1], e[-2], e[-3]):
        return None
    a = v[-1]
    tend = _ema(c, LW_TENDENCIA)[-1] if LW_TENDENCIA else None
    if e[-1] > e[-2] and e[-2] <= e[-3] and (tend is None or a["c"] > tend):
        risco = a["h"] - a["l"]
        if risco > 0:
            return {"direcao": "alta", "gatilho": a["h"], "stop": a["l"], "alvo": a["h"] + LW_ALVO_R * risco, "validade": LW_VALIDADE,
                    "motivo": f"A média de {LW_MEDIA} virou para cima: compra na superação da máxima do candle."}
    if LW_VENDE and e[-1] < e[-2] and e[-2] >= e[-3] and (tend is None or a["c"] < tend):
        risco = a["h"] - a["l"]
        if risco > 0:
            return {"direcao": "baixa", "gatilho": a["l"], "stop": a["h"], "alvo": a["l"] - LW_ALVO_R * risco, "validade": LW_VALIDADE,
                    "motivo": f"A média de {LW_MEDIA} virou para baixo: venda na perda da mínima do candle."}
    return None


def _minervini(v: list[dict]) -> dict | None:
    """Mark Minervini (SEPA/VCP simplificado, só compra): tendência de alta saudável (fechamento > média 50 > 150 > 200, com a de 200 subindo),
    preço a no máximo 25% do topo da janela, volatilidade contraída e rompimento do pivô sem o volume secar."""
    if len(v) < 221:
        return None
    c, h, lo, vol = ([x[k] for x in v] for k in ("c", "h", "l", "v"))
    m50, m150, m200 = _sma(c, 50), _sma(c, 150), _sma(c, 200)
    m200_antes = _sma(c, 200, len(c) - 20)
    if None in (m50, m150, m200, m200_antes):
        return None
    if not (c[-1] > m50 > m150 > m200 and m200 > m200_antes):
        return None
    janela = v[-MM_JANELA:]
    if c[-1] < MM_TOPO * max(x["h"] for x in janela):
        return None
    amp = [h[i] - lo[i] for i in range(len(v))]
    recente, anterior = _sma(amp[:-1], 5), _sma(amp[:-6], 15)
    if not recente or not anterior or recente >= MM_CONTRACAO * anterior:
        return None
    if c[-1] <= max(h[-MM_PIVO - 1:-1]):
        return None
    media_vol = _sma(vol[:-1], 20)
    if not media_vol or vol[-1] < MM_VOLUME * media_vol:
        return None
    stop = min(lo[-MM_BASE - 1:-1])
    if stop >= c[-1]:
        return None
    return {"direcao": "alta", "stop": round(stop, 4), "alvo": round(c[-1] + MM_ALVO_R * (c[-1] - stop), 4),
            "motivo": "Tendência de alta, volatilidade contraída e rompimento do pivô."}


DETECTORES = {"setup_classico": _classico, "turtle_trading": _turtle, "larry_williams": _larry, "mark_minervini": _minervini}


def detectar(setup_id: str, fechados: list[dict]) -> dict | None:
    """Sinal do ÚLTIMO candle fechado da lista ({'direcao', 'motivo'}) ou None. Só olha para trás: não há como enxergar o futuro daqui."""
    fn = DETECTORES.get(setup_id)
    return fn(fechados) if fn and fechados else None


# ------------------------------------------------------------------ catálogo (uma pasta por setup)
def _ler_um(pasta: str) -> dict:
    id_ = os.path.basename(pasta)
    with open(os.path.join(pasta, "setup.json"), encoding="utf-8") as f:
        d = json.load(f)
    if d.get("id") != id_:
        raise ErroSetup(f"{id_}/setup.json: o id precisa ser igual ao nome da pasta.")
    if id_ not in DETECTORES:
        raise ErroSetup(f"{id_}: não há detector para este setup.")
    if d.get("raridade") not in CAT.RARIDADES:
        raise ErroSetup(f"{id_}: raridade inválida.")
    if not str(d.get("nome") or "").strip():
        raise ErroSetup(f"{id_}: falta o nome.")
    a = d.get("assets") or {}

    def existe(nome):
        return bool(nome) and os.path.isfile(os.path.join(pasta, str(nome)))
    assets = {s: (f"assets/setups/{id_}/{a[s]}" if existe(a.get(s)) else None) for s in SLOTS}
    assets["efeitos"] = [f"assets/setups/{id_}/{n}" for n in (a.get("efeitos") or []) if existe(n)]
    cores = {"principal": "#8FB4F0", "brilho": "#FFFFFF", **(d.get("cores") or {})}
    return {"id": id_, "nome": str(d["nome"]).strip(), "raridade": d["raridade"], "resumo": str(d.get("resumo") or ""),
            "caracteristicas": [str(x) for x in d.get("caracteristicas") or []], "indicadores": [str(x) for x in d.get("indicadores") or []],
            "regra": {"compra": str((d.get("regra") or {}).get("compra") or ""), "venda": str((d.get("regra") or {}).get("venda") or "")},
            "cores": cores, "assets": assets, "provisorio": not (assets["carta"] and assets["ativacao"])}


@functools.lru_cache(maxsize=1)
def catalogo() -> tuple[dict, ...]:
    """Todos os setups do jogo, na ordem da raridade e do nome. Lê as pastas uma vez; `recarregar()` lê de novo."""
    if not os.path.isdir(PASTA):
        return ()
    itens = [_ler_um(os.path.join(PASTA, n)) for n in sorted(os.listdir(PASTA)) if os.path.isfile(os.path.join(PASTA, n, "setup.json"))]
    ordem = {r: i for i, r in enumerate(CAT.RARIDADES)}
    return tuple(sorted(itens, key=lambda s: (ordem[s["raridade"]], s["nome"])))


def recarregar() -> None:
    catalogo.cache_clear()


def info(setup_id: str) -> dict | None:
    return next((s for s in catalogo() if s["id"] == setup_id), None)


# ------------------------------------------------------------------ coleção de uma pessoa
def colecao_vazia() -> dict:
    return {"v": 1, "itens": {}, "equipados": [], "ids": [], "log": []}


IDS_MAX, LOG_MAX = 500, 100
MAX_EQUIPADOS = 2      # cada jogador usa até 2 setups ao mesmo tempo, desde que tenha a carta de cada um


def normalizar(doc) -> dict:
    d = colecao_vazia()
    if isinstance(doc, dict) and doc.get("v") == 1:
        d["itens"] = {str(k): dict(v) for k, v in (doc.get("itens") or {}).items() if isinstance(v, dict)}      # o que foi conquistado nunca sai
        bruto = doc.get("equipados")
        if bruto is None:
            bruto = [doc.get("equipado")]                                                                          # formato antigo (um só)
        eqs = []
        for x in bruto if isinstance(bruto, list) else []:
            if x in d["itens"] and info(x) and x not in eqs:                                                       # só se equipa o que existe e é dela
                eqs.append(x)
        d["equipados"] = eqs[:MAX_EQUIPADOS]
        d["ids"] = list(doc.get("ids") or [])[-IDS_MAX:]
        d["log"] = list(doc.get("log") or [])[:LOG_MAX]
    return d


def _registrar(doc: dict, tipo: str, agora_iso: str, **kw) -> None:
    doc["log"] = ([{"t": agora_iso, "tipo": tipo, **kw}] + doc["log"])[:LOG_MAX]


def conquistar(doc: dict, setup_id: str, origem: str, agora_iso: str) -> bool:
    """Registra o setup como conquistado. Devolve False se já era dela (nada muda): conquista é permanente e não duplica."""
    if not info(setup_id):
        raise ErroSetup("Setup desconhecido.")
    if setup_id in doc["itens"]:
        return False
    doc["itens"][setup_id] = {"desde": agora_iso, "origem": origem}
    _registrar(doc, "conquista", agora_iso, setup=setup_id, origem=origem)
    return True


def equipar(doc: dict, setup_id: str, agora_iso: str) -> dict:
    """Equipa um setup cuja carta a pessoa tem. Até MAX_EQUIPADOS ao mesmo tempo; com todos os espaços ocupados, é preciso desequipar um antes."""
    if not info(setup_id):
        raise ErroSetup("Setup desconhecido.")
    if setup_id not in doc["itens"]:
        raise ErroSetup("Você ainda não tem a carta deste setup.")
    if setup_id not in doc["equipados"]:
        if len(doc["equipados"]) >= MAX_EQUIPADOS:
            raise ErroSetup(f"Você já está usando {MAX_EQUIPADOS} setups. Desequipe um para equipar outro.")
        doc["equipados"].append(setup_id)
        _registrar(doc, "equipar", agora_iso, setup=setup_id)
    return {"equipados": list(doc["equipados"])}


def desequipar(doc: dict, setup_id: str, agora_iso: str) -> dict:
    if setup_id in doc["equipados"]:
        doc["equipados"].remove(setup_id)
        _registrar(doc, "desequipar", agora_iso, setup=setup_id)
    return {"equipados": list(doc["equipados"])}


# ------------------------------------------------------------------ baús
# Chance de um baú de cada tier trazer UM setup, além do que ele já traz. É uma rolagem à parte: as cartas e as moedas do baú não mudam.
# A raridade do setup sai da MESMA tabela de pesos do baú (cartas_catalogo.BAUS[...]["chances"]), então baú melhor favorece setup mais raro.
CHANCE_BAU = {"comum": 0.04, "raro": 0.08, "epico": 0.15, "lendario": 0.30}


def sortear_do_bau(seed: str, rar_bau: str, doc: dict, baus: dict, chance: dict | None = None) -> str | None:
    """Setup que veio neste baú, ou None. Determinístico: mesma semente, mesmo resultado. Só sai o que ela ainda NÃO conquistou."""
    rng = C._rng("setup|" + seed)
    if rng.random() >= float((chance or CHANCE_BAU).get(rar_bau, 0.0)):
        return None
    livres = {r: sorted(s["id"] for s in catalogo() if s["raridade"] == r and s["id"] not in doc["itens"]) for r in CAT.RARIDADES}
    if not any(livres.values()):
        return None
    conf = baus.get(rar_bau) or baus["comum"]
    return rng.choice(livres[C._sortear_raridade(rng, conf["chances"], livres)])
