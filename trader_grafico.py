"""Trader Battle · mesa de operações (componente do gráfico). Camada fina entre o front (trader_front/index.html) e o motor.

Regras de negócio continuam em `trader_battle.py`: aqui só se (1) montam os argumentos do componente com o que `TB.visao()` já revelou
e (2) traduz o evento do componente (confirmar / replay / tempo) em chamadas ao motor. Sem Streamlit neste módulo, exceto no `mesa()`.
"""
from __future__ import annotations

import os

import trader_battle as TB

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trader_front")
_comp = None


def disponivel() -> bool:
    return os.path.isfile(os.path.join(_DIR, "index.html"))


def mesa(chave: str, **args):
    """Renderiza o componente e devolve o último valor enviado por ele (ou None)."""
    global _comp
    import streamlit.components.v1 as components
    if _comp is None:
        _comp = components.declare_component("trader_mesa", path=_DIR)
    return _comp(key=chave, default=None, **args)


def args_mesa(v: dict, p: dict, estado: dict) -> dict:
    """Argumentos do componente. `v` é o resultado de TB.visao(): só candles já revelados, nada do futuro."""
    cand = v["candles"]
    sr = {"suportes": [], "resistencias": []}
    try:
        z = TB.indicadores(cand, {"sma": 0, "ema": 0, "rsi": 0, "sr": True})["sr"]
        sr = {"suportes": [x["preco"] for x in z["suportes"][:3]], "resistencias": [x["preco"] for x in z["resistencias"][:3]]}
    except Exception:
        pass
    e = v.get("estrategia")
    inicial = None
    if e:
        inicial = {k: e.get(k) for k in ("direcao", "tipo", "confianca", "entrada", "stop", "alvo")}
        inicial["marcas"] = e.get("marcas") or {}
    return {"candles": cand, "ticker": v["ticker"], "tf_nome": TB.TIMEFRAMES[v["tf"]]["nome"], "demo": v["demo"], "rodada": v["rodada"], "rodadas": v["rodadas"],
            "seg": v["segundos"], "ref": cand[-1]["c"], "token": f"{p['id']}-{v['rodada']}", "sr": sr, "inicial": inicial, "limites": dict(TB.MAX_MARCAS),
            "erro": estado.get("erro", ""), "erro_seq": estado.get("erro_seq", 0), "ok_seq": estado.get("ok_seq", 0)}


def estrategia_de(val: dict) -> dict:
    """Converte o valor do componente na estratégia que o motor valida. Nada é corrigido: valor estranho vira erro do motor."""
    tipo = val.get("tipo")
    direcao = val.get("direcao")
    if direcao not in ("alta", "baixa"):
        direcao = "lateral" if tipo == "aguardar" else None
    esp = tipo == "aguardar"
    try:
        conf = int(val.get("confianca"))
    except (TypeError, ValueError):
        conf = None
    return {"direcao": direcao, "tipo": tipo, "confianca": conf,
            "entrada": None if esp else val.get("entrada"), "stop": None if esp else val.get("stop"), "alvo": None if esp else val.get("alvo")}


def processar(p: dict, val, estado: dict, jog: str, ref: float, agora: float) -> bool:
    """Aplica UMA vez cada evento do componente (por `seq`). Devolve True se algo mudou e a tela precisa redesenhar."""
    if not isinstance(val, dict):
        return False
    seq = val.get("seq")
    if not isinstance(seq, int) or seq <= estado.get("seq", 0):
        return False
    estado["seq"] = seq
    ev = val.get("evento")
    try:
        if ev == "confirmar":
            TB.salvar_estrategia(p, jog, estrategia_de(val), val.get("marcas"), ref, agora)
            estado["ok_seq"], estado["erro"] = seq, ""
        elif ev == "replay":
            TB.iniciar_replay(p, jog, agora)
        elif ev == "tempo":
            TB.avancar(p, agora)
        else:
            return False
    except TB.ErroTrader as e:
        estado["erro"], estado["erro_seq"] = str(e), seq
    return True
