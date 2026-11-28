"""Cenário do Trade Battle AO VIVO (cripto, Binance): o MESMO motor da partida corrida, alimentado pelo mercado de agora, segundo a segundo.

Uma partida ao vivo é o gráfico de 30 s, 60 candles = 30 min, e cada candle se forma JUNTO com o mercado (passos de 1 s reais):
  · Âncora M = a última fronteira de 30 s fechada antes do pareamento. O replay é feito de 1800 passos de 1 s a partir de M; os primeiros
    segundos (até 29) já aconteceram quando a partida começa e aparecem na hora, como o gráfico "atual".
  · Análise: os últimos 120 candles de 30 s (1 hora), montados com os segundos já fechados, terminando em M.
  · O futuro não existe: passos que o mercado ainda não fechou são preenchimento plano que o motor nunca mostra (ele limita o que revela ao que a Binance já fechou,
    `_vivo_n`). Nada do futuro vaza.
O cenário é reconstruído a cada consulta a partir do que a Binance já fechou (cripto_vivo guarda por poucos segundos), então não se grava candle algum.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone

import cripto_vivo as CV
import trader_battle as TB

FMT = "%Y-%m-%dT%H:%M"
FMT_S = "%Y-%m-%dT%H:%M:%S"
FORMATO = "vivo"
MOEDAS = tuple(CV.SIMBOLOS)


def ancora(agora: float) -> int:
    """Última fronteira de 30 s fechada (a âncora do cenário): o replay conta os passos de 1 s a partir daqui."""
    return int(agora // 30 * 30)


def escala_de(preco: float) -> float:
    """Potência de 10 que traz o preço para a faixa de 10 a 100 (BTC 59.800 → ÷1.000 = 59,80; DOGE 0,35 → ×100 = 35). O motor negocia ações INTEIRAS: com o preço
    de verdade, 1 BTC custaria mais que o capital da partida. Só a escala muda (retornos, indicadores e desenhos são iguais); o rótulo diz a escala."""
    import math
    return 10.0 ** (1 - math.floor(math.log10(max(preco, 1e-12))))


def _rotulo_escala(e: float) -> str:
    return f"÷{int(round(1 / e)):,}".replace(",", ".") if e < 1 else (f"×{int(round(e)):,}".replace(",", ".") if e > 1 else "")


def _iso(epoch: float, fmt: str = FMT) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime(fmt)


def _vela(t: str, o: float, h: float, l: float, c: float, v: float, e: float) -> dict:
    return {"t": t, "o": round(o * e, 4), "h": round(h * e, 4), "l": round(l * e, 4), "c": round(c * e, 4), "v": v}


def _juntar(velas: list[dict]) -> tuple[float, float, float, float, float]:
    return velas[0]["o"], max(x["h"] for x in velas), min(x["l"] for x in velas), velas[-1]["c"], sum(x["v"] for x in velas)


def cenario(moeda: str, M: int, agora: float, escala: float | None = None) -> dict:
    """Cenário de `moeda` ancorado em `M` (epoch, s), com o que o mercado já fechou até `agora`. Levanta CV.SemDados."""
    sp = TB.CORRIDA_VIVO
    n_ana, k, n_vel = sp["n_analise"], sp["k"], sp["n_replay"]
    n_passos = n_vel * k
    relogio = lambda: agora                                    # noqa: E731
    # um passe só pelos segundos: o histórico (n_ana candles de k segundos, até M) e os passos do replay (a partir de M)
    ini_hist = M - n_ana * k
    segs = CV.segundos(moeda, ini_hist, M + n_passos, agora=relogio)
    hist = [x for x in segs if x["s"] < M]
    if len(hist) < n_ana * k:
        raise CV.SemDados(f"histórico curto demais: {len(hist)} de {n_ana * k} segundos")
    reais = [x for x in segs if x["s"] >= M]
    e = escala if escala else escala_de(hist[-1]["c"])
    analise = []
    for i in range(n_ana):
        g = hist[i * k:(i + 1) * k]
        analise.append(_vela(_iso(g[0]["s"], FMT_S), g[0]["o"], max(x["h"] for x in g), min(x["l"] for x in g), g[-1]["c"], sum(x["v"] for x in g), e))
    ref = round((reais[-1]["c"] if reais else hist[-1]["c"]) * e, 4)
    passos = [_vela(_iso(x["s"], FMT_S), x["o"], x["h"], x["l"], x["c"], x["v"], e) for x in reais]
    for i in range(len(reais), n_passos):                      # preenchimento do futuro (nunca revelado pelo motor)
        passos.append({"t": _iso(M + i, FMT_S), "o": ref, "h": ref, "l": ref, "c": ref, "v": 0.0})
    rot = _rotulo_escala(e)
    return {"id": f"VIVO-{moeda}-{M}", "ticker": f"{moeda} {rot}".strip(), "nome": f"{CV.NOMES[moeda]} ao vivo" + (f" (preço {rot})" if rot else ""), "tf": sp["tf"],
            "corrida": FORMATO, "sub": sp["sub"], "demo": False, "escala": e, "fonte": "Binance (dados públicos de mercado, ao vivo)", "n_analise": n_ana,
            "candles": analise + passos, "grupo": [i // k for i in range(n_passos)], "velas_t": [_iso(M + k * g, FMT_S) for g in range(n_vel)], "_vivo_n": len(reais)}


def referencia(c: dict, moeda: str, M: int) -> dict:
    """O que vai para o banco da partida: a moeda, a âncora e a escala de preço (nenhum candle fica gravado)."""
    return {"id": c["id"], "demo": False, "semente": 0, "tf": c["tf"], "corrida": FORMATO, "vivo": {"moeda": moeda, "M": int(M), "escala": c["escala"]}}


def resolver(ref: dict, agora: float | None = None) -> dict:
    v = ref["vivo"]
    try:
        return cenario(v["moeda"], int(v["M"]), time.time() if agora is None else agora, v.get("escala"))
    except CV.SemDados as e:
        raise TB.ErroTrader(f"Sem dados do mercado agora ({e}). Tente de novo em instantes.")
