"""Cenário do Trade Battle AO VIVO (cripto, Binance): o MESMO motor da partida corrida, alimentado pelo mercado de agora, segundo a segundo.

Uma partida ao vivo é o gráfico de 2 min, 15 candles = 30 min, e cada candle se forma JUNTO com o mercado (passos de 1 s reais):
  · Âncora M = o último minuto fechado (fronteira de minuto) antes do pareamento. O replay é feito de 1800 passos de 1 s a partir de M; os primeiros
    segundos (até 59) já aconteceram quando a partida começa e aparecem na hora, como o gráfico "atual".
  · Análise: os últimos 200 candles de 2 min, montados juntando candles de 1 min já fechados, terminando em M.
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
    """Último minuto fechado (a âncora do cenário): o replay conta os passos de 1 s a partir daqui."""
    return int(agora // 60 * 60)


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
    """Cenário de `moeda` ancorado no minuto `M` (epoch, s), com o que o mercado já fechou até `agora`. Levanta CV.SemDados."""
    sp = TB.CORRIDA_VIVO
    n_ana, k, n_vel = sp["n_analise"], sp["k"], sp["n_replay"]
    n_passos = n_vel * k
    relogio = lambda: agora                                    # noqa: E731
    # histórico: candles de 1 min fechados até M, juntados de 2 em 2 de trás para a frente a partir de M
    c1 = CV.historico(moeda, "1m", _iso(M), n_ana * 2, agora=relogio)
    pares = []
    fim = len(c1)
    while fim - 2 >= 0 and len(pares) < n_ana:
        pares.append(c1[fim - 2:fim])
        fim -= 2
    pares.reverse()
    if len(pares) < n_ana:
        raise CV.SemDados("histórico curto demais")
    e = escala if escala else escala_de(pares[-1][-1]["c"])
    analise = [_vela(par[0]["t"], *_juntar(par), e) for par in pares]
    # replay: passos de 1 s reais a partir de M
    reais = CV.segundos(moeda, M, M + n_passos, agora=relogio)
    ref = round((reais[-1]["c"] if reais else pares[-1][-1]["c"]) * e, 4)
    passos = [_vela(_iso(x["s"], FMT_S), x["o"], x["h"], x["l"], x["c"], x["v"], e) for x in reais]
    for i in range(len(reais), n_passos):                      # preenchimento do futuro (nunca revelado pelo motor)
        passos.append({"t": _iso(M + i, FMT_S), "o": ref, "h": ref, "l": ref, "c": ref, "v": 0.0})
    rot = _rotulo_escala(e)
    return {"id": f"VIVO-{moeda}-{M}", "ticker": f"{moeda} {rot}".strip(), "nome": f"{CV.NOMES[moeda]} ao vivo" + (f" (preço {rot})" if rot else ""), "tf": sp["tf"],
            "corrida": FORMATO, "sub": sp["sub"], "demo": False, "escala": e, "fonte": "Binance (dados públicos de mercado, ao vivo)", "n_analise": n_ana,
            "candles": analise + passos, "grupo": [i // k for i in range(n_passos)], "velas_t": [_iso(M + 120 * g) for g in range(n_vel)], "_vivo_n": len(reais)}


def referencia(c: dict, moeda: str, M: int) -> dict:
    """O que vai para o banco da partida: a moeda, a âncora e a escala de preço (nenhum candle fica gravado)."""
    return {"id": c["id"], "demo": False, "semente": 0, "tf": c["tf"], "corrida": FORMATO, "vivo": {"moeda": moeda, "M": int(M), "escala": c["escala"]}}


def resolver(ref: dict, agora: float | None = None) -> dict:
    v = ref["vivo"]
    try:
        return cenario(v["moeda"], int(v["M"]), time.time() if agora is None else agora, v.get("escala"))
    except CV.SemDados as e:
        raise TB.ErroTrader(f"Sem dados do mercado agora ({e}). Tente de novo em instantes.")
