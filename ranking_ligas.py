"""Ranking por liga de rank (Bronze a Mestre) da Wallet Game.

DEMONSTRAÇÃO: enquanto não há participantes reais suficientes, a lista é completada com perfis FICTÍCIOS (marcados como demonstração na tela).
Para desligar, ponha DEMO = False: aí só aparecem pessoas reais (quando existirem dados reais, passe-os em `reais`).
Função pura, sem rede: o patrimônio da pessoa vem de fora e nunca é gravado aqui."""
from __future__ import annotations

import random

DEMO = True
POR_LIGA = 12

_NOMES = ["Lobo da Bolsa", "Tati Dividendos", "Renda Zen", "Mestre Selic", "Bia Valor", "Caçador de Alta", "Nina FIIs", "Pedro Graham",
          "Lu Bazin", "Aporte Diário", "Gui Longo Prazo", "Clara Carteira", "Zeca Trader", "Duda Índice", "Ravi Quant", "Maju Cripto",
          "Téo Small Caps", "Sofi Reserva", "Leo Fluxo", "Ana Paciente", "Rafa Tendência", "Kaká Bonds", "Ju Rebalanceia", "Davi Hedge"]


def _faixas(faixas: list) -> list[tuple[str, float, float | None]]:
    """[(nome, minimo, proximo_minimo ou None)] a partir de rk['faixas'] = [(nome, minimo, cor)]."""
    return [(n, m, faixas[i + 1][1] if i + 1 < len(faixas) else None) for i, (n, m, _c) in enumerate(faixas)]


def demonstracao(faixas: list, indice: int) -> list[dict]:
    """Perfis fictícios da liga `indice`, com patrimônio dentro da faixa. Determinístico (mesma lista a cada abertura)."""
    nome, minimo, prox = _faixas(faixas)[indice]
    teto = prox - 1 if prox else minimo * 1.6
    rnd = random.Random(f"liga-{nome}")
    nomes = _NOMES[:]
    rnd.shuffle(nomes)
    out = []
    for i in range(POR_LIGA):
        pat = round(minimo + (teto - minimo) * rnd.random() ** 0.8, 2)
        out.append({"apelido": nomes[i % len(nomes)], "patrimonio": pat, "demo": True})
    return out


def montar(faixas: list, indice: int, eu: dict | None = None, reais: list[dict] | None = None) -> list[dict]:
    """Ranking da liga por patrimônio (maior primeiro). `eu` = {"apelido", "patrimonio"} entra só se estiver nesta liga."""
    nome, minimo, prox = _faixas(faixas)[indice]
    itens = [dict(x, demo=False) for x in (reais or []) if minimo <= float(x.get("patrimonio", 0)) and (prox is None or float(x["patrimonio"]) < prox)]
    if DEMO:
        itens += demonstracao(faixas, indice)
    if eu and minimo <= float(eu.get("patrimonio", 0)) and (prox is None or float(eu["patrimonio"]) < prox):
        itens.append({"apelido": eu.get("apelido") or "Você", "patrimonio": float(eu["patrimonio"]), "demo": False, "eu": True})
    itens.sort(key=lambda x: -x["patrimonio"])
    for i, x in enumerate(itens, 1):
        x["pos"] = i
    return itens
