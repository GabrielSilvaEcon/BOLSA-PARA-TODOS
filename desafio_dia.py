"""Desafio do dia · regras puras (sem banco e sem rede).

Todo dia (horário de Brasília) sai UM gráfico real do Trade Battle, igual para todo mundo, e cada conta tem UMA tentativa: começar
a partida já gasta a tentativa (sair no meio não dá direito a outra). A nota é a pontuação da partida, calculada pelo mesmo motor
do Trade Battle (70% operação, 30% leitura). O ranking do dia ordena pela nota (empate: quem terminou antes).
Prêmios, pagos uma vez no dia seguinte a quem jogou: top 10, top 100 e participação.
"""
from __future__ import annotations

import hashlib

CORRIDA = "intermediaria"            # duração do gráfico do desafio
PREMIOS = (("top10", "Top 10", 10, 30), ("top100", "Top 100", 100, 10), ("participacao", "Participação", None, 5))


def semente(dia: str) -> int:
    """Semente fixa do dia: o mesmo gráfico para todos (vem da data, não de quem joga)."""
    return int(hashlib.sha256(f"desafio|{dia}".encode()).hexdigest()[:8], 16) % 100000


def premio(pos: int | None) -> dict | None:
    """Prêmio de quem terminou o desafio na posição `pos` (None = não terminou: sem prêmio)."""
    if not pos:
        return None
    for pid, rot, lim, tc in PREMIOS:
        if lim is None or pos <= lim:
            return {"id": pid, "rotulo": rot, "tc": tc}
    return None


def tabela_premios() -> list[dict]:
    return [{"id": i, "rotulo": r, "ate": lim, "tc": tc} for i, r, lim, tc in PREMIOS]


def ordenar(resultados: list[dict]) -> list[dict]:
    """Só quem terminou (tem nota), da maior nota para a menor; empate: quem terminou antes. Acrescenta a posição."""
    feitos = [r for r in resultados if isinstance(r.get("nota"), (int, float))]
    feitos.sort(key=lambda r: (-float(r["nota"]), str(r.get("fim") or "")))
    return [{**r, "pos": i} for i, r in enumerate(feitos, 1)]
