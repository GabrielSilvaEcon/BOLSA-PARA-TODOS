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
    if p["fase"] != "replay" or TB.pausada(p):
        return None                                           # em pausa técnica nada é revelado
    cfg = TB.cfg_de(p)
    n = int(cfg["n_replay"])
    passo = cfg["t_replay_s"] / n
    dec = TB._decorrido(p, agora)
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
    mesa = v.get("motor") == TB.MOTOR_MESA
    e = v.get("estrategia")
    inicial = None
    if e:
        inicial = {k: e.get(k) for k in ("direcao", "tipo", "confianca") + (() if mesa else ("entrada", "stop", "alvo"))}
        inicial["marcas"] = e.get("marcas") or {}
    rep = v["fase"] == "replay"
    modo = "replay" if rep else ("resultado" if v["fase"] == "resultado" else "analise")
    prox = prox_revelacao_s(p, agora) if (rep and agora is not None and TB.cfg_de(p)["t_replay_s"] / TB.cfg_de(p)["n_replay"] >= 0.8) else None   # ritmo rápido: a revelação vem na consulta de 1 s e o gráfico anima em fila
    return {"modo": modo, "fase_key": f"{v['rodada']}-{modo}", "adversarios": v.get("adversarios") or [], "propria": v.get("propria"), "operacao": texto_operacao(v.get("operacao"), v.get("aposta")), "marcas_ant": v.get("marcas_ant") or {},
            "resultado": payload_resultado(v, p) if modo == "resultado" else None, "multi": bool(v.get("multi")), "aposta_txt": texto_aposta(v.get("aposta")), "prontos": v.get("prontos"), "seq0": int(estado.get("seq", 0)), "revelados": v["revelados"], "total_replay": v["total_replay"], "prox_ms": None if prox is None else int(prox * 1000),
            "candles": cand, "ticker": v["ticker"], "tf_nome": TB.TIMEFRAMES[v["tf"]]["nome"], "demo": v["demo"], "rodada": v["rodada"], "rodadas": v["rodadas"],
            "seg": v["segundos"], "ref": cand[-1]["c"], "token": p["id"], "sr": sr, "inicial": inicial, "limites": dict(TB.MAX_MARCAS),
            "erro": estado.get("erro", ""), "erro_seq": estado.get("erro_seq", 0), "ok_seq": estado.get("ok_seq", 0),
            "motor": v.get("motor", TB.MOTOR_LEGADO), "pausada": bool(v.get("pausada")), "mesa": texto_mesa(v.get("mesa")) if mesa else None}


def _sinal(x: float) -> str:
    return "+" if x > 0 else ("−" if x < 0 else "")


def _pc(x: float, casas: int = 2) -> str:
    return f"{abs(x):.{casas}f}".replace(".", ",")


def texto_fin(fin: dict | None) -> dict | None:
    """Lucro ou prejuízo da rodada em T$ e em %, já formatado. Vem do servidor (financeiro_rodada), a tela só mostra."""
    if not fin:
        return None
    import wallet_game as WG
    pnl = fin["pnl"]
    cor = "up" if pnl > 0 else ("down" if pnl < 0 else "zero")
    if not fin["operou"]:
        t1 = "Sem operação: seu patrimônio não mudou"
    else:
        nops = f" · {fin['n_ops']} operações" if fin.get("n_ops", 0) > 1 else ""
        t1 = f"{_sinal(pnl)}{WG.moeda(abs(pnl))} · {_sinal(pnl)}{_pc(fin['pct_aposta'])}% da aposta{nops}"
    out = {"cor": cor, "t1": t1, "t2": f"Aposta de {WG.moeda(fin['aposta'])} (1% do patrimônio) · {_sinal(pnl)}{_pc(fin['pct_pat'], 3)}% do patrimônio"}
    if fin.get("n_ops") is not None:                           # mesa: o resultado soma várias operações, cada uma com a mesma aposta de referência
        out["nota"] = "Cada operação usa a mesma aposta de referência e os resultados se somam: a perda da rodada pode passar de 1% do patrimônio."
    return out


def texto_mesa(m: dict | None) -> dict | None:
    """Mesa PRIVADA do jogador (posição, stop, alvo, ordens, resultados) já com os textos formatados. Só este jogador recebe isto."""
    if not m:
        return None
    import wallet_game as WG

    def din(x):
        return None if x is None else f"{_sinal(x)}{WG.moeda(abs(x))}"

    def cor(x):
        return "up" if x > 0 else ("down" if x < 0 else "zero")
    return {**m, "aberto_txt": f"{_sinal(m['aberto_pct'])}{_pc(m['aberto_pct'])}%" + (f" ({din(m['aberto_val'])})" if m["aberto_val"] is not None else ""),
            "acum_txt": f"{_sinal(m['realizado_pct'])}{_pc(m['realizado_pct'])}%" + (f" ({din(m['realizado_val'])})" if m["realizado_val"] is not None else ""),
            "cor_aberto": cor(m["aberto_pct"]), "cor_acum": cor(m["realizado_pct"]),
            "aposta_txt": None if m.get("stake") is None else f"Aposta por operação: {WG.moeda(m['stake'])} (1% do patrimônio no início da rodada)"}


_ROT_ENCERRO = {"stop": "no stop", "alvo": "no alvo", "manual": "por você", "fim": "no fim do replay"}


def texto_operacao(op: dict | None, ap: dict | None) -> dict | None:
    """Situação da operação durante o replay, já formatada (a conta é do servidor: TB.operacao_viva). Só candles revelados."""
    if not op:
        return None
    import wallet_game as WG
    estado, pct = op["estado"], op["pct"]
    if estado == "aguardando":
        return {"estado": estado, "encerravel": op["encerravel"], "cor": "zero", "txt": "Ordem aguardando o preço de entrada", "saida": None}
    if estado == "cancelada":
        return {"estado": estado, "encerravel": False, "cor": "zero", "txt": "Ordem cancelada por você (sem lucro nem prejuízo)", "saida": None}
    cor = "up" if pct > 0 else ("down" if pct < 0 else "zero")
    din = ""
    if ap:
        v = round(float(ap["stake"]) * pct / 100, 2)
        din = f" ({_sinal(v)}{WG.moeda(abs(v))})"
    base = f"{_sinal(pct)}{_pc(pct)}%{din}"
    if estado == "aberta":
        txt = f"Aberta · {base}"
    else:
        txt = f"Encerrada {_ROT_ENCERRO.get(op['por'], '')} · {base}"
    saida = None if estado != "fechada" or op.get("indice_saida") is None else {"indice": op["indice_saida"], "preco": op["preco_saida"]}
    return {"estado": estado, "encerravel": op["encerravel"], "cor": cor, "txt": txt, "saida": saida}


def texto_aposta(ap: dict | None) -> str | None:
    if not ap:
        return None
    import wallet_game as WG
    return f"Aposta {WG.moeda(ap['stake'])}"


SELO_MIN_PONTOS = 70      # só enfeite: o selo "Ótima análise!" aparece quando a rodada rende 70+ pontos de 100 (a pontuação em si não muda)


def payload_resultado(v: dict, p: dict) -> dict | None:
    """Resumo da rodada para o cartão dentro do gráfico. Vem pronto do servidor (pontuação já calculada)."""
    r = v.get("resultado")
    if not r:
        return None
    op = r.get("operacao")
    mesa = r.get("motor") == TB.MOTOR_MESA
    faixa = {True: "faixa_vitoria", False: "faixa_derrota"}.get(r.get("acertou_direcao"), "faixa_empate")
    return {"pontos": r["pontos"], "total": p["pontos"].get(v.get("jogador"), v["pontos"]), "faixa": faixa, "acertou": r.get("acertou_direcao"),
            "executada": bool(r.get("operacoes")) if mesa else (None if op is None else bool(op["executada"])), "r": None if mesa or not op or not op.get("executada") else round(op["r"], 2),
            "n_ops": len(r.get("operacoes") or []) if mesa else None,
            "fin": texto_fin(r.get("fin")), "img": CT.uri(faixa), "selo": ART.uri("selo_otima") if r["pontos"] >= SELO_MIN_PONTOS else None, "linhas": [[t, x] for t, x in TB.explicar(r)], "ultima": v["rodada"] >= v["rodadas"]}


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


_CAMPOS_ACAO = ("tipo", "direcao", "preco", "stop", "alvo", "qual", "aid")


def acao_de(dados) -> dict:
    """Só estes campos saem do navegador para o motor; n_rev, ordem, hora e jogador são SEMPRE do servidor. Valores estranhos viram erro no motor."""
    d = dados if isinstance(dados, dict) else {}
    return {k: d[k] for k in _CAMPOS_ACAO if k in d and isinstance(d[k], (str, int, float, type(None))) and not isinstance(d[k], bool)}


def processar(p: dict, val, estado: dict, jog: str, ref: float, agora: float, ops=None, cen: dict | None = None) -> bool:
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
        elif ev == "encerrar":
            if ops:
                ops.encerrar(agora)
            elif cen is not None:
                TB.encerrar_operacao(p, cen, jog, agora)
            estado["erro"] = ""
        elif ev == "acao":                                # mesa: comprar, vender, ordem, stop/alvo, mover, cancelar, encerrar
            acao = acao_de(val.get("dados"))
            if ops:
                ops.agir(acao, agora)
            elif cen is not None:
                TB.registrar_acao(p, cen, jog, acao, agora)
            estado["erro"] = ""
        elif ev == "replay":
            ops.replay(agora) if ops else TB.iniciar_replay(p, jog, agora)
        elif ev == "tempo":
            ops.tempo(agora) if ops else TB.avancar(p, agora)
        elif ev == "voltar":
            estado["voltar"] = True                   # a tela (Streamlit) decide como sair: individual encerra, sala só desanexa
        elif ev == "proxima":
            if p["fase"] != "resultado":
                return True
            ops.proxima(agora) if ops else TB.proxima_rodada(p, agora)
        else:
            return False
    except TB.ErroTrader as e:
        estado["erro"], estado["erro_seq"] = str(e), seq
    return True
