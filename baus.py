"""Baús ganhos por progresso (marcos do passe e semana de ofensiva). Módulo puro, sem Streamlit, rede ou banco: só decide QUAIS baús a pessoa
tem direito a abrir, a partir do estado já derivado do estudo. Quem sorteia, credita e impede abrir duas vezes é o servidor (tickercoins.py).
O passe continua gratuito e sem pagar nada por si: o baú é um bônus separado, aberto por ação da pessoa, em TC (XP e T$ seguem independentes)."""
from __future__ import annotations

from datetime import date

ORIGENS = ("marco", "semanal")
DIAS_SEMANA_OFENSIVA = 7
# raridade do baú de cada marco do passe (1 a 10): quanto mais longe, mais raro
RARIDADE_MARCO = {1: "comum", 2: "comum", 3: "comum", 4: "raro", 5: "raro", 6: "raro", 7: "epico", 8: "epico", 9: "epico", 10: "lendario"}


def baus_do_passe(estado: dict) -> list[dict]:
    """Um baú por marco já alcançado na temporada (`passe.estado`). `ref` = temporada + número do marco: único por temporada."""
    out = []
    for m in (estado or {}).get("marcos", []):
        if m.get("ok"):
            n = int(m["n"])
            out.append({"origem": "marco", "ref": f"{estado['id']}:{n}", "raridade": RARIDADE_MARCO.get(n, "comum"), "rotulo": f"Baú do marco {n}"})
    return out


def bau_semanal(ofensiva: int, hoje: date) -> dict | None:
    """Um baú por semana (ISO) em que a ofensiva atual está em 7 dias ou mais. A raridade só sai no sorteio, ao abrir."""
    if int(ofensiva) < DIAS_SEMANA_OFENSIVA:
        return None
    ano, sem, _ = hoje.isocalendar()
    return {"origem": "semanal", "ref": f"{ano}-W{sem:02d}", "raridade": None, "rotulo": "Baú da semana: 7 dias seguidos"}


def todos(estado_passe: dict, ofensiva: int, hoje: date) -> list[dict]:
    b = baus_do_passe(estado_passe)
    s = bau_semanal(ofensiva, hoje)
    return b + ([s] if s else [])
