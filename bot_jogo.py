"""Bots de treino que JOGAM de verdade: cada bot tem um plano de operações montado quando a partida começa e executa esse plano pelo mesmo sistema de
ordens das pessoas (nada de atalho no placar). O plano usa a "visão de futuro" que o servidor tem do gráfico (o jogador não vê) para escolher a direção
com uma taxa de acerto por nível: é assim que a dificuldade é controlada. O bot é sempre identificado como bot (ver bots.py).

Dificuldade (bots.NIVEIS): Normal, Difícil e Mestre. O nível sai dos troféus do jogador (quem tem mais enfrenta bot mais forte).
"""
from __future__ import annotations

import random

import bots as BOTS
import trader_battle as TB


def _atr_passos(passos: list[dict], e: int, n: int = 20) -> float:
    ini = max(0, e - n)
    trs = [max(x["h"] - x["l"], abs(x["h"] - passos[k - 1]["c"]) if k else 0, abs(x["l"] - passos[k - 1]["c"]) if k else 0) for k, x in enumerate(passos[ini:e], ini)]
    return (sum(trs) / len(trs)) if trs else 0.0


def planejar(passos: list[dict], nivel: dict, semente: int) -> list[dict]:
    """Operações do bot (em passos do replay): quando abrir, quando fechar, para que lado e a que distância ficam o stop e o alvo."""
    rnd = random.Random(semente)
    n = len(passos)
    k = rnd.randint(*nivel["trades"])
    ini, fim = 6, n - 6
    larg = max(1, (fim - ini) // k)
    plano = []
    for i in range(k):
        j0 = ini + i * larg
        e = j0 + rnd.randint(0, max(0, int(larg * 0.4)))
        x = min(e + rnd.randint(*nivel["horizonte"]), j0 + larg - 1, n - 3)
        if x <= e + 2 or e >= n - 4:
            continue
        futuro = passos[x]["c"] - passos[e - 1]["c"]                  # o que o gráfico fez de verdade entre a entrada e a saída
        certo = 1 if futuro >= 0 else -1
        lado = certo if rnd.random() < nivel["acerto"] else -certo
        atr = _atr_passos(passos, e) or abs(passos[e - 1]["c"]) * 0.002
        plano.append({"abre": e, "fecha": x, "dir": "alta" if lado > 0 else "baixa", "stop_d": round(atr * nivel["stop_atr"], 4),
                      "alvo_d": round(atr * nivel["stop_atr"] * nivel["alvo_r"], 4), "estado": "espera"})
    return plano


def plano_do_bot(cen: dict, ini: int, n_passos: int, nivel: dict, semente: int) -> dict:
    passos = cen["candles"][ini:ini + n_passos]
    plano = planejar(passos, nivel, semente)
    lado = (passos[-1]["c"] - passos[0]["c"]) if passos else 0.0
    return {"plano": plano, "direcao": "alta" if lado >= 0 else "baixa"}


def _posicao(p: dict, cen: dict, jog: str, n: int) -> dict | None:
    ini = TB.inicio_rodada(cen, p["rodada"], TB._nrp(p))
    sim = TB._sim_jog(p, jog, cen["candles"][ini:ini + n], TB.acoes_da_rodada(p, p["rodada"], jog), cen["candles"][ini - 1]["c"], False)
    return sim.get("posicao")


def _tamanho(p: dict, jog: str, preco: float, nivel: dict) -> int:
    lote = max(1, int(TB.lote_de(p, jog, preco)))
    cap = float(TB.capital_de(p, jog))
    return max(1, int(cap * nivel["capital"] / (preco * lote))) * lote


def agir(p: dict, cen: dict, agora: float) -> bool:
    """Executa o que o plano de cada bot manda neste instante (chamar a cada consulta). Idempotente: cada ordem tem `aid` próprio. True se algo mudou."""
    bots = p.get("bots") or {}
    if not bots or p["fase"] != "replay" or TB.pausada(p):
        return False
    n = TB.n_revelados(p, agora)
    ini = TB.inicio_rodada(cen, p["rodada"], TB._nrp(p))
    mudou = False
    for jog, b in bots.items():
        nivel = BOTS.NIVEL[b["nivel"]]
        for i, t in enumerate(b["plano"]):
            if t["estado"] == "espera":
                if n < t["abre"]:
                    continue
                if n >= t["fecha"]:
                    t["estado"], mudou = "pulada", True               # a consulta chegou tarde demais: essa operação já passou
                    continue
                preco = cen["candles"][ini + n - 1]["c"]
                sinal = 1 if t["dir"] == "alta" else -1
                base = {"aid": f"bot:{i}:a", "tipo": "mercado", "direcao": t["dir"], "q": _tamanho(p, jog, preco, nivel)}
                prot = {"stop": round(preco - sinal * t["stop_d"], 4), "alvo": round(preco + sinal * t["alvo_d"], 4)}
                try:
                    try:
                        TB.registrar_acao(p, cen, jog, {**base, **prot}, agora)
                    except TB.ErroTrader:
                        TB.registrar_acao(p, cen, jog, base, agora)    # o preço andou: entra sem proteção em vez de perder a operação
                    t["estado"] = "aberta"
                except TB.ErroTrader:
                    t["estado"] = "pulada"
                mudou = True
            elif t["estado"] == "aberta" and n >= t["fecha"]:
                pos = _posicao(p, cen, jog, n)
                if pos:                                               # stop ou alvo ainda não pegaram: o bot sai a mercado no horário que planejou
                    try:
                        TB.registrar_acao(p, cen, jog, {"aid": f"bot:{i}:f", "tipo": "mercado", "direcao": "baixa" if t["dir"] == "alta" else "alta", "q": pos["q"]}, agora)
                    except TB.ErroTrader:
                        pass
                t["estado"], mudou = "fechada", True
    if mudou:
        p["versao"] += 1
    return mudou
