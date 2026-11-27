"""Bot do Trade Battle AO VIVO. O futuro não existe, então este bot NÃO enxerga nada à frente: decide só com o que já apareceu no gráfico, a cada 15 s,
pelo mesmo sistema de ordens das pessoas (nada de atalho no placar). A dificuldade (Normal, Difícil, Mestre, ver bots.py) muda quanto ele opera e o capital que
usa, não a sorte: ele segue a tendência curta quase sempre e às vezes vai contra, como uma pessoa. Perde e ganha; o bot nunca é garantia de vitória.
"""
from __future__ import annotations

import math
import random

import bot_jogo as BJ
import bots as BOTS
import trader_battle as TB

BLOCO = 15                                        # decide a cada 15 passos de 1 s
CURTA, LONGA = 30, 120                            # médias (em segundos) que dão a tendência
CHANCE_ENTRADA = {"normal": 0.10, "dificil": 0.16, "mestre": 0.22}      # por bloco, sem posição
HOLD_S = (120, 480)                               # quanto segura a posição (stop e alvo podem fechar antes)


def tendencia(passos: list[dict]) -> int:
    """+1 se a média curta está acima da longa (com folga), −1 se abaixo, 0 se o mercado está parado."""
    if len(passos) < LONGA:
        return 0
    fechamentos = [x["c"] for x in passos]
    curta = sum(fechamentos[-CURTA:]) / CURTA
    longa = sum(fechamentos[-LONGA:]) / LONGA
    folga = longa * 0.00015
    return 1 if curta > longa + folga else (-1 if curta < longa - folga else 0)


def estrategia_inicial(cen: dict, nivel: dict, semente: int) -> dict:
    """A leitura que o bot confirma no começo: a tendência dos últimos candles do histórico (o futuro não existe), com o lado errado de vez em quando."""
    hist = cen["candles"][:cen["n_analise"]]
    rnd = random.Random(semente + 11)
    sobe = hist[-1]["c"] >= hist[-30]["c"]
    certo = "alta" if sobe else "baixa"
    lado = certo if rnd.random() < nivel["acerto"] else ("baixa" if certo == "alta" else "alta")
    return {"direcao": lado, "tipo": rnd.choice(("continuacao", "continuacao", "reversao", "rompimento")), "confianca": rnd.randint(2, 4)}


def agir(p: dict, cen: dict, agora: float) -> bool:
    """Chamar a cada consulta. Idempotente: cada decisão tem o seu bloco e as ordens têm `aid` próprio. True se algo mudou."""
    bots = p.get("bots") or {}
    if not bots or p["fase"] != "replay" or TB.pausada(p):
        return False
    n = TB.n_revelados(p, agora)
    if n < LONGA:
        return False
    ini = TB.inicio_rodada(cen, p["rodada"], TB._nrp(p))
    passos = cen["candles"][ini:ini + n]
    px = passos[-1]["c"]
    bloco = n // BLOCO
    mudou = False
    for jog, b in bots.items():
        st = b.setdefault("vivo", {"bloco": -1, "abriu": None})
        if st["bloco"] == bloco:
            continue
        st["bloco"], mudou = bloco, True
        nivel = BOTS.NIVEL[b["nivel"]]
        rnd = random.Random(f"{p['id']}|{jog}|{bloco}")
        pos = BJ._posicao(p, cen, jog, n)
        if pos is None:
            st["abriu"] = None
            sinal = tendencia(passos)
            if sinal == 0 or rnd.random() > CHANCE_ENTRADA.get(b["nivel"], 0.1):
                continue
            lado = sinal if rnd.random() < 0.7 else -sinal            # segue a tendência na maioria das vezes, como uma pessoa
            atr = BJ._atr_passos(passos, n) * math.sqrt(30)
            stop_d = max(atr * nivel["stop_atr"], px * 0.0008)
            alvo_d = stop_d * nivel["alvo_r"]
            direcao = "alta" if lado > 0 else "baixa"
            base = {"aid": f"bot:{bloco}:a", "tipo": "mercado", "direcao": direcao, "q": BJ._tamanho(p, jog, px, nivel)}
            prot = {"stop": round(px - lado * stop_d, 4), "alvo": round(px + lado * alvo_d, 4)}
            try:
                try:
                    TB.registrar_acao(p, cen, jog, {**base, **prot}, agora)
                except TB.ErroTrader:
                    TB.registrar_acao(p, cen, jog, base, agora)           # o preço andou: entra sem proteção em vez de perder a operação
                st["abriu"] = bloco
                st["segura"] = rnd.randint(*HOLD_S) // BLOCO
            except TB.ErroTrader:
                pass
        elif st.get("abriu") is not None and bloco - st["abriu"] >= int(st.get("segura") or 0):
            try:                                                          # stop e alvo não pegaram: sai a mercado depois de segurar o tempo que quis
                TB.registrar_acao(p, cen, jog, {"aid": f"bot:{bloco}:f", "tipo": "mercado", "direcao": "baixa" if pos["direcao"] == "alta" else "alta", "q": pos["q"]}, agora)
                st["abriu"] = None
            except TB.ErroTrader:
                pass
    if mudou:
        p["versao"] += 1
    return mudou
