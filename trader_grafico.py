"""Trader Battle · mesa de operações (componente do gráfico). Camada fina entre o front (trader_front/index.html) e o motor.

Regras de negócio continuam em `trader_battle.py`: aqui só se (1) montam os argumentos do componente com o que `TB.visao()` já revelou
e (2) traduz o evento do componente (confirmar / replay / tempo / proxima) em chamadas ao motor. O componente é UM só por partida
(mesmo token): análise, replay e resultado acontecem no mesmo gráfico, e as rodadas seguem em sequência cronológica. Sem Streamlit neste módulo, exceto no `mesa()`.
"""
from __future__ import annotations

import os

import arte_cartela as CT
import arte_trader as ART
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


def prox_revelacao_s(p: dict, agora: float) -> float | None:
    """Segundos até o servidor liberar o próximo candle do replay (None se não há mais). Só informa o instante; não revela nada."""
    if p["fase"] != "replay":
        return None
    n = TB.TIMEFRAMES[p["tf"]]["n_replay"]
    passo = TB.T_REPLAY_S / n
    dec = max(0.0, agora - p["t_fase"])
    k = int(dec / passo)
    return None if k >= n else max(0.05, (k + 1) * passo - dec)


def args_mesa(v: dict, p: dict, estado: dict, agora: float | None = None) -> dict:
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
    rep = v["fase"] == "replay"
    modo = "replay" if rep else ("resultado" if v["fase"] == "resultado" else "analise")
    prox = prox_revelacao_s(p, agora) if (rep and agora is not None and TB.T_REPLAY_S / TB.TIMEFRAMES[p["tf"]]["n_replay"] >= 0.8) else None   # ritmo rápido: a revelação vem na consulta de 1 s e o gráfico anima em fila
    return {"modo": modo, "fase_key": f"{v['rodada']}-{modo}", "adversarios": v.get("adversarios") or [], "propria": v.get("propria"), "marcas_ant": v.get("marcas_ant") or {},
            "resultado": payload_resultado(v, p) if modo == "resultado" else None, "multi": bool(v.get("multi")), "prontos": v.get("prontos"), "seq0": int(estado.get("seq", 0)), "revelados": v["revelados"], "total_replay": v["total_replay"], "prox_ms": None if prox is None else int(prox * 1000),
            "candles": cand, "ticker": v["ticker"], "tf_nome": TB.TIMEFRAMES[v["tf"]]["nome"], "demo": v["demo"], "rodada": v["rodada"], "rodadas": v["rodadas"],
            "seg": v["segundos"], "ref": cand[-1]["c"], "token": p["id"], "sr": sr, "inicial": inicial, "limites": dict(TB.MAX_MARCAS),
            "erro": estado.get("erro", ""), "erro_seq": estado.get("erro_seq", 0), "ok_seq": estado.get("ok_seq", 0)}


SELO_MIN_PONTOS = 70      # só enfeite: o selo "Ótima análise!" aparece quando a rodada rende 70+ pontos de 100 (a pontuação em si não muda)


def payload_resultado(v: dict, p: dict) -> dict | None:
    """Resumo da rodada para o cartão dentro do gráfico. Vem pronto do servidor (pontuação já calculada)."""
    r = v.get("resultado")
    if not r:
        return None
    op = r.get("operacao")
    faixa = {True: "faixa_vitoria", False: "faixa_derrota"}.get(r.get("acertou_direcao"), "faixa_empate")
    return {"pontos": r["pontos"], "total": p["pontos"].get(v.get("jogador"), v["pontos"]), "faixa": faixa, "acertou": r.get("acertou_direcao"),
            "executada": None if op is None else bool(op["executada"]), "r": None if not op or not op.get("executada") else round(op["r"], 2),
            "img": CT.uri(faixa), "selo": ART.uri("selo_otima") if r["pontos"] >= SELO_MIN_PONTOS else None, "linhas": [[t, x] for t, x in TB.explicar(r)], "ultima": v["rodada"] >= v["rodadas"]}


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


def processar(p: dict, val, estado: dict, jog: str, ref: float, agora: float, ops=None) -> bool:
    """Aplica UMA vez cada evento do componente (por `seq`). Devolve True se algo mudou e a tela precisa redesenhar.
    `jog` vem sempre da sessão no servidor (nunca do valor do componente). `ops` (opcional) troca o destino das ações: na partida
    compartilhada elas vão para o banco (trader_online_dados.Ops); sem `ops`, agem direto no motor (modo individual)."""
    if not isinstance(val, dict):
        return False
    seq = val.get("seq")
    if not isinstance(seq, int) or seq <= estado.get("seq", 0):
        return False
    estado["seq"] = seq
    ev = val.get("evento")
    try:
        if ev == "confirmar":
            if ops:
                ops.salvar(estrategia_de(val), val.get("marcas"), ref, agora)
            else:
                TB.salvar_estrategia(p, jog, estrategia_de(val), val.get("marcas"), ref, agora)
            estado["ok_seq"], estado["erro"] = seq, ""
        elif ev == "replay":
            ops.replay(agora) if ops else TB.iniciar_replay(p, jog, agora)
        elif ev == "tempo":
            ops.tempo(agora) if ops else TB.avancar(p, agora)
        elif ev == "proxima":
            if p["fase"] != "resultado":
                return True
            ops.proxima(agora) if ops else TB.proxima_rodada(p, agora)
        else:
            return False
    except TB.ErroTrader as e:
        estado["erro"], estado["erro_seq"] = str(e), seq
    return True
