"""Jogadores da casa: adversários para quando ninguém mais está procurando partida. Módulo puro (sem banco, sem rede).

Decisão do produto: eles se passam por jogadores comuns (nome de usuário normal, "Jogador N" na mesa); só o servidor sabe quem é quem (e-mail com o
prefixo `bot:`). Partida com eles conta para ranking e troféus, então têm níveis de dificuldade (Normal, Difícil e Mestre) escolhidos pelos troféus
do jogador, e no cálculo de troféus valem os do jogador mais um bônus do nível. Capital igual ao do jogador. No Trade Battle jogam pelo mesmo sistema
de ordens (bot_jogo.py); no Ticker Battle jogam cartas e atributos (bot_ticker.py). Nas telas de ranking aparecem alguns com pontuação baixa.
"""
from __future__ import annotations

PREFIXO = "bot:"
BOT_ESPERA_S = 12            # quanto a busca espera por gente de verdade antes de oferecer o bot
BOTS_ATIVOS = True           # desligue quando houver jogadores suficientes online
NOMES = ("rafa_trader", "lu.invest", "CarolBull", "pedroh78", "thi_ago", "juliana.fx", "MarcosAlves", "bia_candle", "gustavo_ti", "nanda.bolsa",
         "dudu_swing", "FeLima", "paulo.r", "camila_trend", "vini_ações", "leo.fiis", "TaisM", "ricardo_opt", "mari.day", "joaoPedro22",
         "Kaique_B3", "analu.trade", "betoinvest", "sofia_rm", "diegoSilva", "yasmin.t", "caio_scalp", "fer.nunes", "otavio_h", "lari.dividendos")

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
    return "Jogador"                     # o bot não se anuncia: na mesa todo adversário é "Jogador N"


def semente_de(txt: str) -> int:
    import hashlib
    return int(hashlib.sha256(str(txt).encode()).hexdigest()[:8], 16)


def fantasmas_do_ranking(jogo: str, temporada: str, dia: int, n: int = 14, teto: int = 260) -> list[dict]:
    """Jogadores da casa que aparecem nos rankings de troféus (Trade e Ticker) com pontuação baixa: nunca passam de `teto` (meio da Prata) e
    sobem devagar ao longo do mês. Determinístico (mesma temporada = mesmos nomes), sem gravar nada."""
    saida = []
    for i in range(n):
        h = semente_de(f"{jogo}|{temporada}|{i}")
        nome = NOMES[h % len(NOMES)]
        final = 15 + (h >> 8) % (teto - 15)                      # onde ele termina o mês
        andamento = 0.35 + 0.65 * min(1.0, max(1, dia) / 28)      # começa o mês com ~35% disso
        saida.append({"nome": nome, "trofeus": int(final * andamento), "chave": f"{PREFIXO}rk{i}"})
    vistos, unicos = set(), []
    for x in saida:                                              # sem nomes repetidos na mesma lista
        if x["nome"] not in vistos:
            vistos.add(x["nome"])
            unicos.append(x)
    return unicos
