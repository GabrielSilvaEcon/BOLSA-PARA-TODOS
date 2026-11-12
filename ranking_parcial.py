"""Ranking parcial do dia (regra de negócio pura, sem Streamlit nem banco).

Durante o pregão a classificação é recalculada com os preços do momento, só para acompanhar. O ranking OFICIAL continua sendo o do
fechamento (~18h30): temporada, ligas, selos e prêmios usam só ele. A parcial é gravada dentro do documento público do ranking
(campo "parcial") e some sozinha quando o fechamento publica o documento novo."""
from __future__ import annotations

from datetime import date

import competicao as C


def estado_parcial(est: dict, precos: dict | None, dia: str) -> dict | None:
    """Cópia da carteira com um ponto do dia no histórico (patrimônio ao preço atual). None se a carteira ainda não tem fechamento
    (quem não está no ranking oficial também não aparece na parcial) ou se o dia já foi fechado."""
    if not isinstance(est, dict) or est.get("v") != 1:
        return None
    hist = list(est.get("hist") or [])
    if len(hist) < C.MIN_DIAS_RANKING or (hist and str(hist[-1].get("d")) >= dia):
        return None
    novo = dict(est)
    novo["hist"] = hist + [{"d": dia, "p": round(C.patrimonio(est, precos), 2), "a": hist[-1].get("a", 0.0)}]
    return novo


def montar(participantes: list[dict], precos: dict | None, hoje: date) -> dict | None:
    """participantes: [{'apelido','email','estado'}] como no ranking oficial. Devolve as listas públicas (geral, mês, semana, risco)."""
    part = []
    for p in participantes:
        e = estado_parcial(p["estado"], precos, hoje.isoformat())
        if e:
            part.append({**p, "estado": e})
    if not part:
        return None
    return C.montar_ranking(part, hoje)["listas"]


def escolher(rk: dict | None) -> tuple[dict, str | None]:
    """(listas, rótulo) a mostrar. Usa a parcial só se for de um dia mais novo que o fechamento publicado; senão, o oficial (rótulo None).
    Rótulo: 'Parcial de hoje, às 10h34'."""
    rk = rk or {}
    oficial = rk.get("listas") or {}
    par = rk.get("parcial")
    if isinstance(par, dict) and par.get("listas") and str(par.get("dia") or "") > str(rk.get("dia") or ""):
        return par["listas"], f"Parcial de hoje, às {par.get('hora') or '?'}"
    return oficial, None


def hora_br(agora) -> str:
    return f"{agora.hour}h{agora.minute:02d}"
