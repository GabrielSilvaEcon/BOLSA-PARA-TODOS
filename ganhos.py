"""Avisos de ganho (XP, Ticker Coins, sequência e nível): regra pura, sem Streamlit.

Compara a foto anterior dos indicadores com a atual e devolve as mensagens a mostrar. Não paga nada: só avisa o que já foi creditado.
T$ (patrimônio do jogo) fica de fora de propósito: oscila com o mercado e não é "ganho" no sentido de recompensa. XP, TC e T$ seguem separados."""
from __future__ import annotations

import nivel as NV


def foto(xp, tc, dias) -> dict:
    """Foto dos indicadores. Valor ausente vira None (não compara)."""
    def n(v):
        try:
            return int(v)
        except (TypeError, ValueError):
            return None
    return {"xp": n(xp), "tc": n(tc), "dias": n(dias)}


def comparar(antes: dict | None, agora: dict) -> list[dict]:
    """Mensagens [{'icone','texto'}] do que subiu desde `antes`. Sem foto anterior (primeira vez na sessão) não avisa nada."""
    if not antes:
        return []
    out = []
    a, b = antes.get("xp"), agora.get("xp")
    if a is not None and b is not None and b > a:
        out.append({"icone": "⚡", "texto": f"+{b - a} XP"})
        na, nb = NV.estado(a), NV.estado(b)
        if nb["nivel"] > na["nivel"]:
            out.append({"icone": "🏆", "texto": f"Subiu para o nível {nb['nivel']}: {nb['titulo']}!"})
    a, b = antes.get("tc"), agora.get("tc")
    if a is not None and b is not None and b > a:
        out.append({"icone": "🪙", "texto": f"+{b - a} Ticker Coins"})
    a, b = antes.get("dias"), agora.get("dias")
    if a is not None and b is not None and b > a:
        out.append({"icone": "🔥", "texto": f"Sequência de {b} {'dia' if b == 1 else 'dias'}!"})
    return out
