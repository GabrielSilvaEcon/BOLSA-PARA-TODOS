"""Tour guiado do primeiro acesso (onboarding interativo) · regras puras, sem banco e sem rede.

O app conduz o jogador por uma sequência de passos (aprender → analisar → comprar → jogar). O servidor só guarda onde o
jogador parou e paga, uma vez cada, os prêmios dos marcos. Documento por conta:
    {"passo": int, "marcos": [..], "pulado": bool, "feito": bool}
"""
from __future__ import annotations

# marco -> Ticker Coins (pagos uma vez, quando o marco é cumprido)
PREMIOS = {"aprender": 10, "analisar": 10, "comprar": 15, "jogar": 15, "fim": 50}
MARCOS = tuple(PREMIOS)
PASSO_MAX = 60


def vazio() -> dict:
    return {"passo": 0, "marcos": [], "pulado": False, "feito": False}


def sanear(doc: dict | None) -> dict:
    d = dict(doc or {})
    out = vazio()
    try:
        out["passo"] = max(0, min(PASSO_MAX, int(d.get("passo") or 0)))
    except (TypeError, ValueError):
        pass
    out["marcos"] = [m for m in MARCOS if m in (d.get("marcos") or [])]
    out["pulado"] = bool(d.get("pulado"))
    out["feito"] = bool(d.get("feito"))
    return out


def avancar(doc: dict, passo: int | None = None, marco: str | None = None) -> tuple[dict, int]:
    """Guarda o passo atual e cumpre um marco. Devolve (doc, TC a pagar agora: 0 se o marco já tinha sido cumprido)."""
    doc = sanear(doc)
    if passo is not None:
        doc["passo"] = max(0, min(PASSO_MAX, int(passo)))
    ganho = 0
    if marco is not None:
        if marco not in PREMIOS:
            raise ValueError("marco inválido")
        if marco not in doc["marcos"]:
            doc["marcos"] = [m for m in MARCOS if m in doc["marcos"] or m == marco]
            ganho = PREMIOS[marco]
        if marco == "fim":
            doc["feito"] = True
    return doc, ganho


def pular(doc: dict) -> dict:
    doc = sanear(doc)
    doc["pulado"] = True
    return doc


def reiniciar(doc: dict) -> dict:
    """Rever o tour (pela Ajuda): volta ao começo; os marcos já pagos continuam pagos."""
    doc = sanear(doc)
    doc.update(passo=0, pulado=False, feito=False)
    return doc


def ativo(doc: dict) -> bool:
    d = sanear(doc)
    return not d["pulado"] and not d["feito"]
