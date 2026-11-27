"""Cenário do Trade Battle AO VIVO (cripto, Binance): o MESMO motor da partida corrida, alimentado pelo mercado de agora.

Como funciona (sem mudar a mesa nem o motor, só quem entrega o cenário):
  · A partida marca uma hora B (uma fronteira de 5 min, pelo menos 60 s no futuro). Até B é a análise (leitura e desenhos); em B começa o replay.
  · Análise: os últimos 200 candles de 5 min já fechados até B (alinhados com a bolsa).
  · Replay: 12 candles de 5 min feitos de 60 passos de 1 min REAIS, um por minuto. Ainda não aconteceu = ainda não existe: os passos futuros são só
    preenchimento chato e plano, que o motor nunca mostra (ele limita o que revela ao que o mercado já fechou: `_vivo_n`). Nada do futuro vaza.
O cenário é reconstruído a cada consulta a partir do que a Binance já fechou (cripto_vivo guarda por poucos segundos), então não se grava candle algum.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone

import cripto_vivo as CV
import trader_battle as TB

FMT = "%Y-%m-%dT%H:%M"
ANTECEDENCIA_S = 60            # a análise dura pelo menos isto
FRONTEIRA_S = 300              # o replay começa numa fronteira de 5 min da bolsa
MOEDAS = tuple(CV.SIMBOLOS)


def proxima_fronteira(agora: float) -> int:
    """Próximo múltiplo de 5 min que deixa pelo menos ANTECEDENCIA_S de análise."""
    return int(-(-(agora + ANTECEDENCIA_S) // FRONTEIRA_S) * FRONTEIRA_S)


def _iso(epoch: float) -> str:
    return datetime.fromtimestamp(epoch, timezone.utc).strftime(FMT)


def escala_de(preco: float) -> float:
    """Potência de 10 que traz o preço para a faixa de 10 a 100 (BTC 59.800 → ÷1.000 = 59,80; DOGE 0,35 → ×100 = 35). O motor negocia ações INTEIRAS: com o preço
    de verdade, 1 BTC custaria mais que o capital da partida. Só a escala muda (retornos, indicadores e desenhos são iguais); o rótulo diz a escala."""
    import math
    return 10.0 ** (1 - math.floor(math.log10(max(preco, 1e-12))))


def _rotulo_escala(e: float) -> str:
    return f"÷{int(round(1 / e)):,}".replace(",", ".") if e < 1 else (f"×{int(round(e)):,}".replace(",", ".") if e > 1 else "")


def _limpo(c: dict, e: float = 1.0) -> dict:
    return {"t": c["t"], "o": round(c["o"] * e, 4), "h": round(c["h"] * e, 4), "l": round(c["l"] * e, 4), "c": round(c["c"] * e, 4), "v": c["v"]}


def cenario(moeda: str, B: int, agora: float, escala: float | None = None) -> dict:
    """Cenário de `moeda` com o replay marcado para a fronteira `B` (epoch, s), com o que o mercado já fechou até `agora`. Levanta CV.SemDados.
    `escala` fixa a escala de preço da partida (se faltar, sai do último fechamento da análise: só na criação)."""
    sp = TB.CORRIDA_VIVO
    n_ana, k, n_vel = sp["n_analise"], sp["k"], sp["n_replay"]
    n_passos = n_vel * k
    relogio = lambda: agora                                    # noqa: E731
    c5 = CV.candles(moeda, "5m", CV.N_MAX, agora=relogio)["candles"]
    c1 = CV.candles(moeda, "1m", CV.N_MAX, agora=relogio)["candles"]
    b_iso = _iso(B)
    limite5 = _iso(B - FRONTEIRA_S)                            # o último candle de 5 min da análise começa em B − 5 min
    analise = [c for c in c5 if c["fechado"] and c["t"] <= limite5][-n_ana:]
    if len(analise) < n_ana:
        raise CV.SemDados("histórico curto demais")
    reais = []
    for c in c1:                                               # passos reais, seguidos, a partir de B
        if not c["fechado"] or c["t"] < b_iso:
            continue
        if c["t"] != _iso(B + 60 * len(reais)):
            break
        reais.append(c)
        if len(reais) == n_passos:
            break
    e = escala if escala else escala_de(analise[-1]["c"])
    rot = _rotulo_escala(e)
    ref = round((reais[-1] if reais else analise[-1])["c"] * e, 4)
    passos = [_limpo(c, e) for c in reais]
    for i in range(len(reais), n_passos):                      # preenchimento do futuro (nunca revelado pelo motor)
        passos.append({"t": _iso(B + 60 * i), "o": ref, "h": ref, "l": ref, "c": ref, "v": 0.0})
    return {"id": f"VIVO-{moeda}-{B}", "ticker": f"{moeda} {rot}".strip(), "nome": f"{CV.NOMES[moeda]} ao vivo" + (f" (preço {rot})" if rot else ""), "tf": sp["tf"], "corrida": "vivo",
            "sub": sp["sub"], "demo": False, "escala": e, "fonte": "Binance (dados públicos de mercado, ao vivo)", "n_analise": n_ana, "candles": [_limpo(c, e) for c in analise] + passos,
            "grupo": [i // k for i in range(n_passos)], "velas_t": [_iso(B + FRONTEIRA_S * g) for g in range(n_vel)], "_vivo_n": len(reais)}


def referencia(c: dict, moeda: str, B: int) -> dict:
    """O que vai para o banco da partida: a moeda, a hora do replay e a escala de preço (nenhum candle fica gravado)."""
    return {"id": c["id"], "demo": False, "semente": 0, "tf": c["tf"], "corrida": "vivo", "vivo": {"moeda": moeda, "B": int(B), "escala": c["escala"]}}


def resolver(ref: dict, agora: float | None = None) -> dict:
    v = ref["vivo"]
    try:
        return cenario(v["moeda"], int(v["B"]), time.time() if agora is None else agora, v.get("escala"))
    except CV.SemDados as e:
        raise TB.ErroTrader(f"Sem dados do mercado agora ({e}). Tente de novo em instantes.")
