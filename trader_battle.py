"""Trader Battle · regras puras (sem Streamlit, sem rede).

Jogo de análise técnica sobre cenários históricos reais: o jogador analisa o gráfico até um ponto, registra a estratégia e depois assiste
ao replay candle a candle. Este módulo guarda TUDO o que decide o jogo: validação de cenários, relógio do servidor, proteção dos candles
futuros, indicadores sobre o que já foi revelado e a avaliação da estratégia. A interface só desenha o que `visao()` devolve.

CONTINUIDADE: a partida é UM cenário contínuo (mesmo ativo e timeframe): n_analise candles de histórico + RODADAS blocos de replay, um por
rodada, em sequência cronológica. A rodada r começa vendo tudo até o fim da rodada r-1; a pontuação de cada rodada é calculada sobre a fatia
daquela rodada, com a mesma fórmula de sempre.

Pensado para o multiplayer (2 a 4 jogadores): o estado da partida é um dicionário JSON com `versao`, sem candles dentro; as estratégias
ficam por jogador; todas as funções recebem `agora` (relógio do servidor) e nenhuma depende do navegador.
"""
from __future__ import annotations

import math
import uuid
from datetime import datetime

RODADAS = 3
T_ANALISE_S = 120
T_REPLAY_S = 90
T_RESULTADO_S = 15                         # só no multiplayer: tempo do resultado antes da próxima rodada começar sozinha (igual para todos)
TIMEFRAMES = {"15m": {"nome": "15 minutos", "n_analise": 60, "n_replay": 24, "passo_min": 15},
              "1h": {"nome": "1 hora", "n_analise": 50, "n_replay": 16, "passo_min": 60}}
JOGADORES_MIN, JOGADORES_MAX = 1, 4          # nesta etapa joga 1; a estrutura já aceita 2 a 4
DIRECOES = ("alta", "baixa", "lateral")
ESTRATEGIAS = ("continuacao", "reversao", "rompimento", "aguardar")
ROTULO_ESTRATEGIA = {"continuacao": "Continuação", "reversao": "Reversão", "rompimento": "Rompimento", "aguardar": "Aguardar"}
MAX_MARCAS = {"niveis": 6, "tendencias": 4, "notas": 6}
FASES = ("analise", "replay", "resultado", "fim")


class ErroTrader(ValueError):
    """Ação inválida (estratégia fora das regras, fase errada, cenário inconsistente)."""


# ------------------------------------------------------------------ cenários
def _num(x) -> float | None:
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def validar_cenario(c: dict) -> tuple[bool, str]:
    """Um cenário só entra no jogo se estiver completo e coerente. Nada é preenchido ou corrigido: na dúvida, é recusado."""
    try:
        tf = c["tf"]
        cfg = TIMEFRAMES[tf]
        cand = c["candles"]
        na = int(c["n_analise"])
    except (KeyError, TypeError, ValueError):
        return False, "cenário incompleto"
    if not c.get("id") or not c.get("ticker"):
        return False, "sem identificação"
    if na != cfg["n_analise"] or len(cand) != cfg["n_analise"] + RODADAS * cfg["n_replay"]:
        return False, "quantidade de candles diferente da prevista"
    ant = None
    for k in cand:
        if not isinstance(k, dict):
            return False, "candle em formato inesperado"
        o, h, l, cl, v = (_num(k.get(x)) for x in ("o", "h", "l", "c", "v"))
        if None in (o, h, l, cl, v) or min(o, h, l, cl) <= 0 or v < 0:
            return False, "candle com valor ausente ou inválido"
        if h < max(o, cl) - 1e-9 or l > min(o, cl) + 1e-9 or h < l:
            return False, "candle impossível (máxima/mínima inconsistentes)"
        try:
            t = datetime.fromisoformat(str(k["t"]))
        except (KeyError, ValueError):
            return False, "horário inválido"
        if ant is not None:
            dh = (t - ant).total_seconds() / 60
            if dh <= 0:
                return False, "candles fora de ordem"
            if dh > cfg["passo_min"] and dh > 5 * 24 * 60:      # lacuna de mais de 5 dias: histórico interrompido
                return False, "lacuna grande no histórico"
        ant = t
    return True, ""


def dataframe(candles: list[dict]):
    """Candles do jogo → DataFrame OHLCV (formato do analise_tecnica)."""
    import pandas as pd
    idx = pd.to_datetime([k["t"] for k in candles])
    return pd.DataFrame({"Open": [k["o"] for k in candles], "High": [k["h"] for k in candles], "Low": [k["l"] for k in candles],
                         "Close": [k["c"] for k in candles], "Volume": [k["v"] for k in candles]}, index=idx)


# ------------------------------------------------------------------ rodadas contínuas
def _nr(c: dict) -> int:
    return TIMEFRAMES[c["tf"]]["n_replay"]


def inicio_rodada(c: dict, r: int) -> int:
    """Quantos candles já são histórico quando a análise da rodada r começa (índice do primeiro candle do replay da rodada r)."""
    return c["n_analise"] + (r - 1) * _nr(c)


def cenario_da_rodada(c: dict, r: int) -> dict:
    """Fatia do cenário usada para avaliar a rodada r: histórico até o começo dela + o replay dela. Os blocos seguintes ficam de fora."""
    ini = inicio_rodada(c, r)
    return {**c, "candles": c["candles"][:ini + _nr(c)], "n_analise": ini}


# ------------------------------------------------------------------ partida (estado JSON, sem candles)
def nova_partida(cenario: dict, tf: str, jogadores: list[str], agora: float, pid: str | None = None, multi: bool = False) -> dict:
    if tf not in TIMEFRAMES:
        raise ErroTrader("timeframe inválido")
    if not (JOGADORES_MIN <= len(jogadores) <= JOGADORES_MAX) or len(set(jogadores)) != len(jogadores):
        raise ErroTrader("número de jogadores inválido")
    ok, why = validar_cenario(cenario)
    if not ok or cenario["tf"] != tf:
        raise ErroTrader(f"cenário recusado: {why or 'timeframe diferente'}")
    return {"id": pid or uuid.uuid4().hex[:10], "tf": tf, "jogadores": list(jogadores), "cenario": cenario["id"], "cenarios": [cenario["id"]] * RODADAS,
            "demo": bool(cenario.get("demo")), "rodada": 1, "fase": "analise", "t_fase": float(agora), "versao": 1,
            "estrategias": {}, "travadas": {}, "resultados": {}, "pontos": {j: 0.0 for j in jogadores}, "multi": bool(multi), "prontos": {}}


def _chave(rod: int, jog: str) -> str:
    return f"{rod}:{jog}"


def inicio_replay(p: dict) -> float:
    return p["t_fase"] + T_ANALISE_S if p["fase"] == "analise" else p["t_fase"]


def segundos_restantes(p: dict, agora: float) -> int:
    """Cronômetro do servidor: análise (120 s) ou replay (90 s). Nas outras fases, 0."""
    if p["fase"] == "analise":
        return max(0, math.ceil(p["t_fase"] + T_ANALISE_S - agora))
    if p["fase"] == "replay":
        return max(0, math.ceil(p["t_fase"] + T_REPLAY_S - agora))
    if p["fase"] == "resultado" and p.get("multi"):
        return max(0, math.ceil(p["t_fase"] + T_RESULTADO_S - agora))
    return 0


def n_revelados(p: dict, agora: float) -> int:
    """Quantos candles do replay já podem aparecer, pelo relógio do servidor. Só existe na fase do replay (e vale tudo depois)."""
    n = TIMEFRAMES[p["tf"]]["n_replay"]
    if p["fase"] in ("resultado", "fim"):
        return n
    if p["fase"] != "replay":
        return 0
    dec = max(0.0, agora - p["t_fase"])
    return min(n, int(dec / (T_REPLAY_S / n)))


# ------------------------------------------------------------------ estratégia
def validar_estrategia(est: dict, preco_ref: float) -> dict:
    """Normaliza e valida a estratégia. Aguardar é sempre válida. Operar exige direção alta/baixa, entrada, stop e alvo coerentes."""
    if not isinstance(est, dict):
        raise ErroTrader("estratégia inválida")
    direcao = est.get("direcao")
    tipo = est.get("tipo")
    if direcao not in DIRECOES:
        raise ErroTrader("escolha a direção esperada")
    if tipo not in ESTRATEGIAS:
        raise ErroTrader("escolha a estratégia")
    conf = est.get("confianca")
    if not isinstance(conf, int) or not 1 <= conf <= 5:
        raise ErroTrader("a confiança vai de 1 a 5")
    out = {"direcao": direcao, "tipo": tipo, "confianca": conf, "entrada": None, "stop": None, "alvo": None}
    if tipo != "aguardar" and direcao in ("alta", "baixa"):
        e, s, a = (_num(est.get(k)) for k in ("entrada", "stop", "alvo"))
        if None in (e, s, a) or min(e, s, a) <= 0:
            raise ErroTrader("para operar, informe entrada, stop e alvo")
        ok = (s < e < a) if direcao == "alta" else (a < e < s)
        if not ok:
            raise ErroTrader("stop e alvo precisam ficar em lados opostos da entrada" + (" (stop abaixo e alvo acima)" if direcao == "alta" else " (alvo abaixo e stop acima)"))
        if abs(e / preco_ref - 1) > 0.08:
            raise ErroTrader("a entrada está muito longe do preço atual")
        out.update(entrada=e, stop=s, alvo=a)
    elif tipo != "aguardar" and direcao == "lateral":
        raise ErroTrader("para operar, a direção precisa ser alta ou baixa; para lateralização, escolha Aguardar")
    return out


def validar_marcas(m: dict | None) -> dict:
    """Desenhos e anotações registrados no gráfico (níveis de preço, linhas de tendência por dois pontos e notas curtas)."""
    m = m or {}
    niveis = []
    for x in (m.get("niveis") or [])[:MAX_MARCAS["niveis"]]:
        v = _num(x.get("preco") if isinstance(x, dict) else x)
        if v and v > 0:
            niveis.append({"preco": v, "rotulo": str((x.get("rotulo") if isinstance(x, dict) else "") or "")[:20]})
    tend = []
    for x in (m.get("tendencias") or [])[:MAX_MARCAS["tendencias"]]:
        try:
            i1, i2 = int(x["i1"]), int(x["i2"])
            p1, p2 = float(x["p1"]), float(x["p2"])
        except (KeyError, TypeError, ValueError):
            continue
        if i1 != i2 and p1 > 0 and p2 > 0 and min(i1, i2) >= 0:
            tend.append({"i1": i1, "p1": p1, "i2": i2, "p2": p2})
    notas = []
    for x in (m.get("notas") or [])[:MAX_MARCAS["notas"]]:
        try:
            notas.append({"i": int(x["i"]), "preco": float(x["preco"]), "texto": str(x.get("texto") or "")[:40]})
        except (KeyError, TypeError, ValueError):
            continue
    return {"niveis": niveis, "tendencias": tend, "notas": notas}


def salvar_estrategia(p: dict, jog: str, est: dict, marcas: dict | None, preco_ref: float, agora: float) -> dict:
    """Registra (ou atualiza) a estratégia durante a análise. Depois de travada ou fora da análise, é recusada: ninguém muda a estratégia vendo o replay."""
    if jog not in p["jogadores"]:
        raise ErroTrader("jogador desconhecido")
    avancar(p, agora)
    if p["fase"] != "analise":
        raise ErroTrader("a análise já terminou")
    k = _chave(p["rodada"], jog)
    if p["travadas"].get(k):
        raise ErroTrader("a estratégia já foi travada")
    p["estrategias"][k] = {**validar_estrategia(est, preco_ref), "marcas": validar_marcas(marcas), "salva_em": float(agora)}
    p["versao"] += 1
    return p["estrategias"][k]


def _travar(p: dict) -> None:
    """Fecha a análise: quem não registrou nada fica com 'Aguardar' sem estratégia (também é uma decisão válida)."""
    for j in p["jogadores"]:
        k = _chave(p["rodada"], j)
        p["travadas"][k] = True
        p["estrategias"].setdefault(k, {"direcao": None, "tipo": "aguardar", "confianca": None, "entrada": None, "stop": None, "alvo": None,
                                        "marcas": {"niveis": [], "tendencias": [], "notas": []}, "sem_registro": True})


def iniciar_replay(p: dict, jog: str, agora: float) -> None:
    """Fim antecipado da análise (nesta etapa, com 1 jogador; no multiplayer só quando todos estiverem prontos)."""
    avancar(p, agora)
    if p["fase"] != "analise":
        return
    if _chave(p["rodada"], jog) not in p["estrategias"]:
        raise ErroTrader("salve a estratégia antes de iniciar o replay")
    _travar(p)
    p["fase"], p["t_fase"] = "replay", float(agora)
    p["versao"] += 1


def _avancar_uma(p: dict, agora: float, cenarios_por_id: dict | None) -> None:
    if p["fase"] == "analise" and agora >= p["t_fase"] + T_ANALISE_S:
        t0 = p["t_fase"] + T_ANALISE_S
        _travar(p)
        p["fase"], p["t_fase"] = "replay", t0              # o replay começa na hora certa, mesmo que ninguém estivesse olhando
        p["versao"] += 1
    if p["fase"] == "replay" and agora >= p["t_fase"] + T_REPLAY_S:
        p["fase"], p["t_fase"] = "resultado", p["t_fase"] + T_REPLAY_S
        p["versao"] += 1
        if cenarios_por_id:
            fechar_rodada(p, cenarios_por_id[p["cenarios"][p["rodada"] - 1]])
    if p.get("multi") and p["fase"] == "resultado" and cenarios_por_id and agora >= p["t_fase"] + T_RESULTADO_S:
        fechar_rodada(p, cenarios_por_id[p["cenarios"][p["rodada"] - 1]])      # idempotente
        proxima_rodada(p, p["t_fase"] + T_RESULTADO_S)     # a próxima rodada começa no instante oficial, igual para todos


def avancar(p: dict, agora: float, cenarios_por_id: dict | None = None) -> dict:
    """Aplica as mudanças de fase que o relógio do servidor já determinou. Chamar de novo é inofensivo.
    Se ninguém consultou por um tempo, encadeia quantas fases forem necessárias (cada uma com o seu horário oficial)."""
    for _ in range(16):
        antes = (p["versao"], p["fase"], p["rodada"])
        _avancar_uma(p, agora, cenarios_por_id)
        if (p["versao"], p["fase"], p["rodada"]) == antes:
            break
    return p


# ------------------------------------------------------------------ multiplayer: ninguém avança a partida sozinho
def marcar_pronto(p: dict, jog: str, agora: float) -> bool:
    """Multiplayer: o jogador diz 'estou pronto' (fim antecipado da análise ou do resultado). A fase só muda quando TODOS marcarem
    (ou quando o relógio do servidor decidir). Devolve True se esta chamada fez a fase mudar. Marcar de novo é inofensivo."""
    if jog not in p["jogadores"]:
        raise ErroTrader("jogador desconhecido")
    avancar(p, agora)
    fase = p["fase"]
    if fase not in ("analise", "resultado"):
        return False
    if fase == "analise" and _chave(p["rodada"], jog) not in p["estrategias"]:
        raise ErroTrader("salve a estratégia antes de iniciar o replay")
    k = f"{p['rodada']}:{fase}:{jog}"
    if p["prontos"].get(k):
        return False
    p["prontos"][k] = True
    p["versao"] += 1
    if not all(p["prontos"].get(f"{p['rodada']}:{fase}:{j}") for j in p["jogadores"]):
        return False
    if fase == "analise":
        _travar(p)
        p["fase"], p["t_fase"] = "replay", float(agora)
    else:
        proxima_rodada(p, agora)
        return True
    p["versao"] += 1
    return True


def prontos_da_fase(p: dict, jog: str) -> dict:
    fase = p["fase"]
    ks = [f"{p['rodada']}:{fase}:{j}" for j in p["jogadores"]]
    return {"eu": bool(p["prontos"].get(f"{p['rodada']}:{fase}:{jog}")), "n": sum(1 for k in ks if p["prontos"].get(k)), "total": len(ks)}


def fechar_rodada(p: dict, cenario: dict) -> None:
    """Calcula no servidor o resultado de cada jogador na rodada atual (uma única vez)."""
    novo = False
    for j in p["jogadores"]:
        k = _chave(p["rodada"], j)
        if k in p["resultados"]:
            continue
        r = avaliar(cenario_da_rodada(cenario, p["rodada"]), p["estrategias"][k])
        p["resultados"][k] = r
        p["pontos"][j] = round(p["pontos"][j] + r["pontos"], 1)
        novo = True
    if novo:
        p["versao"] += 1


def proxima_rodada(p: dict, agora: float) -> None:
    if p["fase"] != "resultado":
        raise ErroTrader("a rodada ainda não terminou")
    if p["rodada"] >= RODADAS:
        p["fase"] = "fim"
    else:
        p["rodada"] += 1
        p["fase"], p["t_fase"] = "analise", float(agora)
    p["versao"] += 1


# ------------------------------------------------------------------ o que o jogador pode ver
def _n_rev_rodada(p: dict, r: int, agora: float) -> int:
    """Candles do replay da rodada r já revelados (rodadas passadas: todos; futuras: nenhum)."""
    n = TIMEFRAMES[p["tf"]]["n_replay"]
    if r < p["rodada"] or p["fase"] in ("resultado", "fim") and r == p["rodada"]:
        return n
    if r > p["rodada"]:
        return 0
    return n_revelados(p, agora) if p["fase"] == "replay" else 0


def entrada_executada(p: dict, cenario: dict, agora: float, r: int, jog: str) -> dict | None:
    """Entrada JÁ EXECUTADA do jogador na rodada r: só existe se a estratégia está travada e um candle REVELADO tocou o preço de entrada.
    Devolve o preço real da execução (ordem limite = o próprio preço de entrada) e o candle; nunca a intenção ainda não executada."""
    k = _chave(r, jog)
    est = p["estrategias"].get(k)
    if not est or not p["travadas"].get(k) or est.get("tipo") == "aguardar" or est.get("entrada") is None:
        return None
    ini, nr = inicio_rodada(cenario, r), _nr(cenario)
    rev = cenario["candles"][ini:ini + _n_rev_rodada(p, r, agora)]
    i = indice_execucao(rev, est["entrada"])
    if i is None:
        return None
    return {"rodada": r, "jogador": jog, "preco": est["entrada"], "indice": ini + i, "direcao": est["direcao"]}


def pode_ver_adversarios(p: dict, cenario: dict, agora: float, jog: str) -> bool:
    """Regra de visibilidade: o jogador só enxerga as entradas executadas dos adversários depois de ter executado ao menos uma entrada
    própria na partida (vale individualmente e permanece até o fim)."""
    return any(entrada_executada(p, cenario, agora, r, jog) for r in range(1, p["rodada"] + 1))


def entradas_adversarios(p: dict, cenario: dict, agora: float, jog: str) -> list[dict]:
    """Entradas executadas dos adversários na rodada atual, rotuladas por posição ('Jogador N'). Sem identidade real, sem stop/alvo, sem planejado."""
    if not pode_ver_adversarios(p, cenario, agora, jog):
        return []
    out = []
    for n, j in enumerate(p["jogadores"], 1):
        if j == jog:
            continue
        e = entrada_executada(p, cenario, agora, p["rodada"], j)
        if e:
            out.append({"rotulo": f"Jogador {n}", "preco": e["preco"], "indice": e["indice"]})
    return out


def _marcas_anteriores(p: dict, jog: str) -> dict:
    """Desenhos pessoais mais recentes do próprio jogador em rodadas anteriores (só dele; serve para reconstruir a tela se o gráfico for remontado)."""
    for r in range(p["rodada"] - 1, 0, -1):
        m = (p["estrategias"].get(_chave(r, jog)) or {}).get("marcas")
        if m and any(m.get(k) for k in ("niveis", "tendencias", "notas")):
            return m
    return {}


def visao(p: dict, cenario: dict, agora: float, jog: str) -> dict:
    """ÚNICO caminho de dados para a tela: só devolve candles já revelados da rodada atual (e o histórico das anteriores).
    Os candles futuros não existem aqui, então não há como vazar. O jogador precisa ser da partida (identidade validada pelo servidor)."""
    if jog not in p["jogadores"]:
        raise ErroTrader("jogador desconhecido")
    cand = cenario["candles"]
    ini = inicio_rodada(cenario, p["rodada"])
    nr = _nr(cenario)
    if p["fase"] == "analise":
        visiveis = cand[:ini]
    elif p["fase"] == "replay":
        visiveis = cand[:ini + n_revelados(p, agora)]
    else:
        visiveis = cand[:ini + nr]
    k = _chave(p["rodada"], jog)
    fim = p["fase"] in ("resultado", "fim")
    return {"ticker": cenario["ticker"], "nome": cenario.get("nome") or cenario["ticker"], "tf": cenario["tf"], "demo": bool(cenario.get("demo")),
            "fonte": cenario.get("fonte", ""), "rodada": p["rodada"], "rodadas": RODADAS, "fase": p["fase"], "segundos": segundos_restantes(p, agora),
            "n_analise": ini, "candles": [dict(c) for c in visiveis], "revelados": max(0, len(visiveis) - ini),
            "total_replay": nr,
            "estrategia": p["estrategias"].get(k), "travada": bool(p["travadas"].get(k)), "pontos": p["pontos"].get(jog, 0.0),
            "resultado": p["resultados"].get(k) if fim else None,
            "adversarios": entradas_adversarios(p, cenario, agora, jog), "jogador": jog, "marcas_ant": _marcas_anteriores(p, jog),
            "multi": bool(p.get("multi")), "prontos": prontos_da_fase(p, jog) if p["fase"] in ("analise", "resultado") else None,
            "pontos_rodadas": [round(p["resultados"][_chave(r, jog)]["pontos"], 1) for r in range(1, RODADAS + 1) if _chave(r, jog) in p["resultados"]],
            "propria": entrada_executada(p, cenario, agora, p["rodada"], jog)}


# ------------------------------------------------------------------ indicadores (sempre sobre o que já foi revelado)
def indicadores(candles: list[dict], cfg: dict) -> dict:
    """Médias móveis, RSI e zonas de suporte/resistência calculados só com os candles recebidos (nunca com o futuro).
    cfg: {'sma': n|0, 'ema': n|0, 'rsi': n|0, 'sr': bool}. Devolve listas alinhadas aos candles (None onde não há valor)."""
    import analise_tecnica as AT
    out = {"sma": None, "ema": None, "rsi": None, "sr": {"suportes": [], "resistencias": []}, "avisos": []}
    if len(candles) < 5:
        return out
    df = dataframe(candles)

    def _serie(nome, col, **kw):
        r, why = AT.tentar(nome, df, **kw)
        if r is None:
            out["avisos"].append(f"{nome}: {why}")
            return None
        return [None if (v != v) else float(v) for v in r[col].tolist()]
    if cfg.get("sma"):
        out["sma"] = _serie("SMA", "SMA", n=int(cfg["sma"]))
    if cfg.get("ema"):
        out["ema"] = _serie("EMA", "EMA", n=int(cfg["ema"]))
    if cfg.get("rsi"):
        out["rsi"] = _serie("RSI", "RSI", n=int(cfg["rsi"]))
    if cfg.get("sr"):
        try:
            z = AT.suportes_resistencias(df)
            out["sr"] = {"suportes": [{"preco": x["preco"], "toques": x["toques"]} for x in z["suportes"]],
                         "resistencias": [{"preco": x["preco"], "toques": x["toques"]} for x in z["resistencias"]]}
        except Exception:
            out["avisos"].append("Suporte/resistência indisponível agora.")
    return out


# ------------------------------------------------------------------ avaliação (servidor)
def _atr(cand: list[dict], n: int = 14) -> float:
    base = cand[-(n + 1):]
    trs = []
    for i in range(1, len(base)):
        pc = base[i - 1]["c"]
        trs.append(max(base[i]["h"] - base[i]["l"], abs(base[i]["h"] - pc), abs(base[i]["l"] - pc)))
    return sum(trs) / len(trs) if trs else 0.0


def mercado_real(cenario: dict) -> dict:
    """O que o mercado fez no replay: movimento líquido, direção real (lateral se o movimento ficou dentro de 1 ATR) e extremos."""
    na = cenario["n_analise"]
    cand = cenario["candles"]
    ref = cand[na - 1]["c"]
    rep = cand[na:]
    fim = rep[-1]["c"]
    atr = _atr(cand[:na])
    mov = fim - ref
    if atr <= 0 or abs(mov) < atr:
        d = "lateral"
    else:
        d = "alta" if mov > 0 else "baixa"
    return {"ref": ref, "fim": fim, "mov_pct": (fim / ref - 1) * 100, "direcao": d, "atr": atr,
            "maxima": max(k["h"] for k in rep), "minima": min(k["l"] for k in rep)}


def indice_execucao(cand_replay: list[dict], entrada: float) -> int | None:
    """Índice do primeiro candle do replay que tocou a entrada (ordem a preço limite: executa exatamente no preço da entrada)."""
    for i, k in enumerate(cand_replay):
        if k["l"] <= entrada <= k["h"]:
            return i
    return None


def simular_operacao(cand_replay: list[dict], est: dict) -> dict:
    """Entrada a preço limite: só executa se o preço tocar a entrada. Depois, stop ou alvo (se os dois caírem no mesmo candle, vale o stop:
    hipótese conservadora). Sem stop nem alvo no fim, encerra no último fechamento."""
    e, s, a, alta = est["entrada"], est["stop"], est["alvo"], est["direcao"] == "alta"
    exec_i = indice_execucao(cand_replay, e)
    if exec_i is None:
        return {"executada": False, "saida": None, "motivo": "O preço não chegou à entrada.", "r": 0.0, "candle_entrada": None, "candle_saida": None}
    risco = abs(e - s)
    for i in range(exec_i, len(cand_replay)):
        k = cand_replay[i]
        bateu_stop = k["l"] <= s if alta else k["h"] >= s
        bateu_alvo = k["h"] >= a if alta else k["l"] <= a
        if i == exec_i and not (bateu_stop or bateu_alvo):
            continue
        if bateu_stop:
            return {"executada": True, "saida": s, "motivo": "Stop atingido.", "r": -1.0, "candle_entrada": exec_i, "candle_saida": i}
        if bateu_alvo:
            return {"executada": True, "saida": a, "motivo": "Alvo atingido.", "r": abs(a - e) / risco, "candle_entrada": exec_i, "candle_saida": i}
    fim = cand_replay[-1]["c"]
    r = ((fim - e) if alta else (e - fim)) / risco
    return {"executada": True, "saida": fim, "motivo": "Replay terminou sem stop nem alvo; encerrada no último preço.", "r": r,
            "candle_entrada": exec_i, "candle_saida": len(cand_replay) - 1}


def avaliar(cenario: dict, est: dict) -> dict:
    """Pontuação educativa (0 a 100), calculada no servidor:
    · direção (até 40): acertou 40; 'aguardar' vale 40 se o mercado ficou lateral, senão 15 (ficou de fora);
    · operação (até 40): R realizado de −1 a 3 vira 0 a 40 (0 R = 20); entrada não executada vale 15;
    · confiança (±10): quem acerta com mais confiança ganha, quem erra com mais confiança perde.
    Não é recomendação nem mede lucro real."""
    real = mercado_real(cenario)
    rep = cenario["candles"][cenario["n_analise"]:]
    aguardou = est["tipo"] == "aguardar" or est["direcao"] in (None, "lateral")
    acertou = None
    if est["direcao"] is None:
        pts_dir, acertou = (40.0 if real["direcao"] == "lateral" else 15.0), real["direcao"] == "lateral"
    elif est["tipo"] == "aguardar":
        pts_dir = 40.0 if real["direcao"] == "lateral" else 15.0
        acertou = real["direcao"] == "lateral"
    else:
        acertou = est["direcao"] == real["direcao"]
        pts_dir = 40.0 if acertou else 0.0
    op = None
    pts_op = 20.0 if aguardou else 0.0
    if not aguardou:
        op = simular_operacao(rep, est)
        pts_op = 15.0 if not op["executada"] else max(0.0, min(40.0, 20.0 + max(-1.0, min(3.0, op["r"])) * (20.0 / 3.0 if op["r"] >= 0 else 20.0)))
    conf = est.get("confianca")
    pts_conf = 0.0
    if conf and acertou is not None:
        pts_conf = (conf - 1) * 2.5 * (1 if acertou else -1)
    total = max(0.0, min(100.0, pts_dir + pts_op + pts_conf))
    return {"pontos": round(total, 1), "real": real, "acertou_direcao": acertou, "operacao": op, "partes": {"direcao": pts_dir, "operacao": round(pts_op, 1),
            "confianca": pts_conf}, "estrategia": est}


def explicar(r: dict) -> list[tuple[str, str]]:
    """Raio-X em linguagem simples: o que a pessoa previu, o que o mercado fez e como cada parte virou pontos."""
    est, real, op, pt = r["estrategia"], r["real"], r["operacao"], r["partes"]
    nome = {"alta": "alta", "baixa": "baixa", "lateral": "lateralização"}
    linhas = []
    if est.get("sem_registro"):
        linhas.append(("Estratégia", "Nenhuma estratégia foi registrada no tempo: contou como Aguardar, sem operação."))
    else:
        prev = "aguardar" if est["tipo"] == "aguardar" else f"{nome.get(est['direcao'], '')} ({ROTULO_ESTRATEGIA[est['tipo']].lower()})"
        linhas.append(("Sua leitura", f"Você registrou: {prev}" + (f", confiança {est['confianca']}/5." if est.get("confianca") else ".")))
    linhas.append(("O mercado", f"O preço foi de {real['ref']:.2f} para {real['fim']:.2f} ({real['mov_pct']:+.1f}%): {nome[real['direcao']]}. "
                   "Lateral = movimento líquido menor que 1 ATR (a variação média dos candles)."))
    if op is not None:
        if not op["executada"]:
            linhas.append(("Operação", "A entrada não foi tocada, então a operação não aconteceu."))
        else:
            linhas.append(("Operação", f"{op['motivo']} Resultado: {op['r']:+.1f} R (R = o risco entre entrada e stop)."))
    elif est["tipo"] == "aguardar" or est.get("sem_registro"):
        linhas.append(("Operação", "Você ficou de fora. Aguardar vale pontos quando o mercado não oferece direção clara."))
    linhas.append(("Pontos", f"Direção {pt['direcao']:.0f} + operação {pt['operacao']:.0f} + confiança {pt['confianca']:+.1f} = {r['pontos']:.1f} de 100."))
    return linhas
