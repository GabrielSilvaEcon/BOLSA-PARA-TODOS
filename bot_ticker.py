"""Jogador da casa no Ticker Battle online: entra quando ninguém aparece na fila e joga como uma pessoa (confirma "pronto", escolhe carta e atributo
em segredo depois de um tempo de "pensar"). Funções puras sobre os dados da partida (battle_online); quem grava é battle_online_dados.

Dificuldade (bots.NIVEIS): o bot compara as suas cartas livres com um palpite do que o adversário pode jogar e escolhe a melhor carta/atributo
com a probabilidade `acerto` do nível; no resto das vezes escolhe ao acaso, como alguém distraído.
"""
from __future__ import annotations

import random
from datetime import datetime

import battle as B
import battle_online as O
import bots as BOTS


def monta_baralho(snapshot: dict, hoje, tamanho: int, semente: int) -> list[str]:
    """Baralho do bot: cartas jogáveis do snapshot do servidor sorteadas, do mesmo tamanho do baralho do jogador."""
    rnd = random.Random(semente)
    tamanho = max(B.BARALHO_MIN, min(B.BARALHO_MAX, int(tamanho)))
    boas = sorted(t for t, c in snapshot.items() if B.jogavel(c, hoje)[0] and B.indicadores_validos(c) and c.get("rar") not in B.MAX_POR_RARIDADE)
    rnd.shuffle(boas)
    return boas[:tamanho]


def _pensa_s(d: dict, rod: int) -> float:
    """Tempo que o bot 'pensa' nesta rodada (3 a 14 s), fixo por partida/rodada para não mudar entre consultas."""
    return 3.0 + (BOTS.semente_de(f"{d['id']}|{rod}") % 110) / 10.0


def _escolha(d: dict, lado: str, nivel: dict, rnd: random.Random) -> tuple[str, str] | None:
    livres = O.cartas_livres(d, lado)
    if not livres:
        return None
    op = O.outro(lado)
    ref = [d["cartas"][t] for t in O.cartas_livres(d, op) if t in d["cartas"]]
    h = O.hoje_de(datetime.now())
    melhor = None
    if rnd.random() < nivel["acerto"] and ref:
        pontos = []
        for t in livres:
            for ind in O.atributos_da_carta(d, t):
                v = 0
                for c in ref:
                    try:
                        v += B.resolver(d["cartas"][t], c, ind, h)["venc"] == "jogador"
                    except ValueError:
                        pass
                pontos.append((v, rnd.random(), t, ind))
        if pontos:
            _, _, t, ind = max(pontos)
            melhor = (t, ind)
    if melhor:
        return melhor
    t = rnd.choice(livres)
    inds = O.atributos_da_carta(d, t)
    return (t, rnd.choice(inds)) if inds else None


def agir(d: dict, agora: datetime) -> dict:
    """Aplica o que o bot faria agora: sinal de presença, ficar pronto e confirmar a jogada. Devolve o MESMO objeto se nada mudou."""
    b = d["jog"].get("b")
    if not b or not BOTS.eh_bot(b["email"]) or d["fase"] not in ("pronta", "em_jogo"):
        return d
    nivel = BOTS.NIVEL.get((d.get("bot") or {}).get("nivel") or "normal", BOTS.NIVEL["normal"])
    n = O.batida(d, "b", agora)                                         # o bot está "online": presença renovada a cada consulta
    if n["fase"] == "pronta":
        if not n["pronto"]["b"] and (agora - (O.de_iso(n.get("criada")) or agora)).total_seconds() >= 3:
            n = O.marcar_pronto(n, "b", agora)
        return n
    if n["fase"] == "em_jogo":
        if n.get("bot_rod") != n["rod"]:                                # começou uma rodada nova: o bot começa a "pensar" agora
            n["bot_rod"], n["bot_rod_em"] = n["rod"], O.iso(agora)
        if n["esc"]["b"] is None:
            pensa = _pensa_s(n, n["rod"])
            desde = (agora - (O.de_iso(n["bot_rod_em"]) or agora)).total_seconds()
            if desde >= pensa:
                rnd = random.Random(BOTS.semente_de(f"{n['id']}|{n['rod']}|j"))
                e = _escolha(n, "b", nivel, rnd)
                if e:
                    n = O.escolher(n, "b", e[0], e[1], agora)
    return n
