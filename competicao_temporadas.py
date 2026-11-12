"""Janelas de calendário (mês e trimestre), em módulo puro. Hoje só o Passe mensal usa estas janelas.
Não há mais ranking por temporada nem selos: eventos sazonais futuros terão a própria lógica."""
from __future__ import annotations

import re
from datetime import date, timedelta

TIPOS = ("mensal", "trimestral")
_ID_MES = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")
_ID_TRI = re.compile(r"(\d{4})-T([1-4])")
_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def id_temporada(tipo: str, dia: date) -> str:
    if tipo == "mensal":
        return f"{dia.year:04d}-{dia.month:02d}"
    if tipo == "trimestral":
        return f"{dia.year:04d}-T{(dia.month - 1) // 3 + 1}"
    raise ValueError(f"tipo inválido: {tipo}")


def tipo_de(tid: str) -> str:
    if _ID_MES.fullmatch(tid or ""):
        return "mensal"
    if _ID_TRI.fullmatch(tid or ""):
        return "trimestral"
    raise ValueError(f"id de temporada inválido: {tid}")


def limites(tid: str) -> tuple[date, date]:
    """(primeiro dia, último dia) da janela, inclusive."""
    if tipo_de(tid) == "mensal":
        a, m = (int(x) for x in tid.split("-"))
        ini = date(a, m, 1)
        fim = (date(a + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)
    else:
        a, t = int(tid[:4]), int(tid[-1])
        ini = date(a, 3 * t - 2, 1)
        fim = date(a + (t == 4), (3 * t) % 12 + 1, 1) - timedelta(days=1)
    return ini, fim


def encerrada(tid: str, hoje: date) -> bool:
    return hoje > limites(tid)[1]


def anterior(tid: str) -> str:
    """Janela imediatamente anterior, do mesmo tipo."""
    return id_temporada(tipo_de(tid), limites(tid)[0] - timedelta(days=1))


def rotulo(tid: str) -> str:
    """'2026-11' -> 'Novembro de 2026'; '2026-T4' -> '4º trimestre de 2026'."""
    ini, _ = limites(tid)
    if tipo_de(tid) == "mensal":
        return f"{_MESES[ini.month - 1].capitalize()} de {ini.year}"
    return f"{(ini.month - 1) // 3 + 1}º trimestre de {ini.year}"


def recentes(tipo: str, hoje: date, quantas: int) -> list[str]:
    """A janela atual e as anteriores do mesmo tipo (da mais nova para a mais antiga)."""
    tid = id_temporada(tipo, hoje)
    out = [tid]
    while len(out) < quantas:
        tid = anterior(tid)
        out.append(tid)
    return out
