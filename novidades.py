"""Novidades a celebrar (Fase 7): emblema novo e marco novo do passe da temporada. Módulo puro, sem Streamlit.
O que a pessoa já viu fica em `jornada["vistos"] = {"emb": [ids], "passe": ["tid:xp"]}` (junto do progresso, por conta).
Primeira leitura (sem `vistos`): só registra o que já existe, sem festejar o passado."""
from __future__ import annotations

LIMITE = 400


def ids_passe(estado_passe: dict) -> list[str]:
    """Um id por marco já alcançado na temporada atual: 'AAAA-MM:xp'."""
    return [f"{estado_passe['id']}:{m['xp']}" for m in estado_passe["marcos"] if m["ok"]]


def ids_emblemas(colecao: list[dict]) -> list[str]:
    return [i["id"] for c in colecao for i in c["itens"] if i.get("ok")]


def vistos(j: dict) -> dict | None:
    v = (j or {}).get("vistos")
    if not isinstance(v, dict):
        return None
    return {"emb": [str(x) for x in (v.get("emb") or [])][-LIMITE:], "passe": [str(x) for x in (v.get("passe") or [])][-LIMITE:]}


def comparar(v: dict | None, emb: list[str], passe: list[str]) -> dict:
    """{'primeira': bool, 'emb': [novos], 'passe': [novos]}. Sem registro anterior, nada é 'novo'."""
    if v is None:
        return {"primeira": True, "emb": [], "passe": []}
    return {"primeira": False, "emb": [x for x in emb if x not in v["emb"]], "passe": [x for x in passe if x not in v["passe"]]}


def registrar(j: dict, emb: list[str], passe: list[str]) -> dict:
    """Cópia da jornada com tudo que está conquistado hoje marcado como visto (guarda também o que já existia)."""
    v = vistos(j) or {"emb": [], "passe": []}
    out = dict(j)
    out["vistos"] = {"emb": sorted(set(v["emb"]) | set(emb))[-LIMITE:], "passe": sorted(set(v["passe"]) | set(passe))[-LIMITE:]}
    return out
