"""Bots de treino: adversários da casa para quando ninguém mais está procurando partida. Módulo puro (sem banco, sem rede).

Regras, para o jogador nunca ser enganado e para o ranking ficar honesto:
 · O bot é SEMPRE identificado como bot (nos rótulos da partida: "Bot 2").
 · Partida com bot CONTA para o ranking e os troféus, então o bot precisa ser um adversário de verdade: tem níveis de dificuldade (Normal, Difícil e Mestre)
   escolhidos pelos troféus do jogador, e no ranking ele vale os troféus do jogador mais um bônus do nível (nunca é um adversário "barato").
 · Capital igual ao do jogador: a comparação é justa. O bot opera pelo mesmo sistema de ordens, com stop e alvo, sem pausar a partida (bot_jogo.py).
"""
from __future__ import annotations

PREFIXO = "bot:"
BOT_ESPERA_S = 12            # quanto a busca espera por gente de verdade antes de oferecer o bot
BOTS_ATIVOS = True           # desligue quando houver jogadores suficientes online
NOMES = ("Bot Touro", "Bot Urso", "Bot Candle", "Bot Tendência", "Bot Pivô")

# Níveis de dificuldade. `acerto`: chance de o bot escolher o lado certo de cada operação (ele enxerga o que o gráfico fez; o jogador não);
# `stop_atr`/`alvo_r`: distância do stop (em ATR) e alvo (múltiplo do risco); `capital`: fração do capital usada; `trofeus`: quanto acima dos troféus do jogador
# ele conta no ranking. O nível sai dos troféus do jogador (de 0 em diante): quem está melhor enfrenta bot mais forte.
NIVEIS = (
    {"id": "normal", "nome": "Normal", "acerto": 0.62, "trades": (2, 3), "horizonte": (18, 36), "stop_atr": 3.0, "alvo_r": 1.5, "capital": 0.5, "trofeus": 0, "de": 0},
    {"id": "dificil", "nome": "Difícil", "acerto": 0.72, "trades": (2, 4), "horizonte": (18, 40), "stop_atr": 3.0, "alvo_r": 1.5, "capital": 0.7, "trofeus": 40, "de": 200},
    {"id": "mestre", "nome": "Mestre", "acerto": 0.82, "trades": (3, 4), "horizonte": (20, 42), "stop_atr": 3.0, "alvo_r": 1.5, "capital": 0.9, "trofeus": 100, "de": 1000},
)
NIVEL = {n["id"]: n for n in NIVEIS}


def nivel_para(trofeus) -> dict:
    """O nível do bot para quem tem `trofeus` (Bronze enfrenta Normal, Prata e Ouro enfrentam Difícil, Platina para cima enfrenta Mestre)."""
    t = max(0, int(trofeus or 0))
    return [n for n in NIVEIS if t >= n["de"]][-1]


def trofeus_do_bot(trofeus_jogador, nivel: dict) -> int:
    """Quanto o bot vale no ranking (troféus): os do jogador mais o bônus do nível. É o que entra na conta de ganho e perda de troféus."""
    return max(0, int(trofeus_jogador or 0)) + int(nivel["trofeus"])


def eh_bot(email) -> bool:
    return str(email or "").startswith(PREFIXO)


def tem_bot(p: dict) -> bool:
    return any(eh_bot(j) for j in (p or {}).get("jogadores") or [])


def novo(pid: str, semente: int, trofeus_jogador=0) -> dict:
    """O bot de uma partida: um e-mail só dele (nunca se repete entre partidas), o nome e o nível de dificuldade escolhido pelos troféus do jogador."""
    nivel = nivel_para(trofeus_jogador)
    return {"email": f"{PREFIXO}{pid[:10]}", "nome": NOMES[semente % len(NOMES)], "nivel": nivel["id"], "nivel_nome": nivel["nome"],
            "trofeus": trofeus_do_bot(trofeus_jogador, nivel), "semente": semente}


def rotulo(j: str) -> str:
    return "Bot" if eh_bot(j) else "Jogador"
