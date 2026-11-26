"""Bots de treino: adversários da casa para quando ninguém mais está procurando partida. Módulo puro (sem banco, sem rede).

Regras, para o jogador nunca ser enganado e para o ranking ficar honesto:
 · O bot é SEMPRE identificado como bot (nos rótulos da partida: "Bot 2").
 · Partida com bot não conta para troféus nem para o ranking online (é treino), mas o resultado em dinheiro da Carteira funciona como o do solo.
 · Capital igual ao do jogador: a comparação é justa.
 · O bot joga com um dos setups que não dependem de marcação do jogador (Clássico, Turtle, Larry Williams) e entra na hora, sem pausar a partida.
"""
from __future__ import annotations

PREFIXO = "bot:"
BOT_ESPERA_S = 12            # quanto a busca espera por gente de verdade antes de oferecer o bot
BOTS_ATIVOS = True           # desligue quando houver jogadores suficientes online
NOMES = ("Bot Touro", "Bot Urso", "Bot Candle", "Bot Tendência", "Bot Pivô")
SETUPS = ("setup_classico", "turtle_trading", "larry_williams")


def eh_bot(email) -> bool:
    return str(email or "").startswith(PREFIXO)


def tem_bot(p: dict) -> bool:
    return any(eh_bot(j) for j in (p or {}).get("jogadores") or [])


def novo(pid: str, semente: int) -> dict:
    """O bot de uma partida: um e-mail só dele (nunca se repete entre partidas), o nome e o setup que usa."""
    return {"email": f"{PREFIXO}{pid[:10]}", "nome": NOMES[semente % len(NOMES)], "setup": SETUPS[(semente // len(NOMES)) % len(SETUPS)]}


def rotulo(j: str) -> str:
    return "Bot" if eh_bot(j) else "Jogador"
