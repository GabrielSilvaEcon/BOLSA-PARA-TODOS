"""Trader Battle · regras puras (sem Streamlit, sem rede).

Jogo de análise técnica sobre cenários históricos reais: o jogador analisa o gráfico até um ponto, registra a estratégia e depois assiste
ao replay candle a candle. Este módulo guarda TUDO o que decide o jogo: validação de cenários, relógio do servidor, proteção dos candles
futuros, indicadores sobre o que já foi revelado e a avaliação da estratégia. A interface só desenha o que `visao()` devolve.

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
    if na != cfg["n_analise"] or len(cand) != cfg["n_analise"] + cfg["n_replay"]:
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


# ------------------------------------------------------------------ partida (estado JSON, sem candles)
def nova_partida(cenarios: list[dict], tf: str, jogadores: list[str], agora: float, pid: str | None = None) -> dict:
    if tf not in TIMEFRAMES:
        raise ErroTrader("timeframe inválido")
    if not (JOGADORES_MIN <= len(jogadores) <= JOGADORES_MAX) or len(set(jogadores)) != len(jogadores):
        raise ErroTrader("número de jogadores inválido")
    if len(cenarios) != RODADAS:
        raise ErroTrader(f"a partida precisa de {RODADAS} cenários")
    for c in cenarios:
        ok, why = validar_cenario(c)
        if not ok or c["tf"] != tf:
            raise ErroTrader(f"cenário recusado: {why or 'timeframe diferente'}")
    return {"id": pid or uuid.uuid4().hex[:10], "tf": tf, "jogadores": list(jogadores), "cenarios": [c["id"] for c in cenarios],
            "demo": any(c.get("demo") for c in cenarios), "rodada": 1, "fase": "analise", "t_fase": float(agora), "versao": 1,
            "estrategias": {}, "travadas": {}, "resultados": {}, "pontos": {j: 0.0 for j in jogadores}}


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


def avancar(p: dict, agora: float, cenarios_por_id: dict | None = None) -> dict:
    """Aplica as mudanças de fase que o relógio do servidor já determinou. Chamar de novo é inofensivo."""
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
    return p


def fechar_rodada(p: dict, cenario: dict) -> None:
    """Calcula no servidor o resultado de cada jogador na rodada atual (uma única vez)."""
    for j in p["jogadores"]:
        k = _chave(p["rodada"], j)
        if k in p["resultados"]:
            continue
        r = avaliar(cenario, p["estrategias"][k])
        p["resultados"][k] = r
        p["pontos"][j] = round(p["pontos"][j] + r["pontos"], 1)
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
def visao(p: dict, cenario: dict, agora: float, jog: str) -> dict:
    """ÚNICO caminho de dados para a tela: só devolve candles já revelados. Os candles futuros não existem aqui, então não há como vazar."""
    na = cenario["n_analise"]
    cand = cenario["candles"]
    if p["fase"] == "analise":
        visiveis = cand[:na]
    elif p["fase"] == "replay":
        visiveis = cand[:na + n_revelados(p, agora)]
    else:
        visiveis = list(cand)
    k = _chave(p["rodada"], jog)
    return {"ticker": cenario["ticker"], "nome": cenario.get("nome") or cenario["ticker"], "tf": cenario["tf"], "demo": bool(cenario.get("demo")),
            "fonte": cenario.get("fonte", ""), "rodada": p["rodada"], "rodadas": RODADAS, "fase": p["fase"], "segundos": segundos_restantes(p, agora),
            "n_analise": na, "candles": [dict(c) for c in visiveis], "revelados": max(0, len(visiveis) - na),
            "total_replay": len(cand) - na,
            "estrategia": p["estrategias"].get(k), "travada": bool(p["travadas"].get(k)), "pontos": p["pontos"].get(jog, 0.0),
            "resultado": p["resultados"].get(k) if p["fase"] in ("resultado", "fim") else None}


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


def simular_operacao(cand_replay: list[dict], est: dict) -> dict:
    """Entrada a preço limite: só executa se o preço tocar a entrada. Depois, stop ou alvo (se os dois caírem no mesmo candle, vale o stop:
    hipótese conservadora). Sem stop nem alvo no fim, encerra no último fechamento."""
    e, s, a, alta = est["entrada"], est["stop"], est["alvo"], est["direcao"] == "alta"
    exec_i = None
    for i, k in enumerate(cand_replay):
        if k["l"] <= e <= k["h"]:
            exec_i = i
            break
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
