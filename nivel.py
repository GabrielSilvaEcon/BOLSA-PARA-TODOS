"""Nível geral do TickerHunter (Fase 2). Módulo puro, sem Streamlit.

O nível é derivado SÓ do XP de estudo da Jornada (`jornada.xp_total`). Não mexe em Ticker Coins, T$ nem no rank da Wallet Game:
as três economias seguem independentes e nada é convertido automaticamente. Nada é gravado: o nível sai do XP já salvo.
"""
from __future__ import annotations

# XP acumulado necessário para ENTRAR em cada nível (curva suave: cada nível pede um pouco mais que o anterior)
_BASE, _PASSO = 40, 20
TITULOS = ((1, "Curioso"), (3, "Aprendiz"), (6, "Observador"), (10, "Investidor em Formação"), (15, "Analista"),
           (20, "Estrategista"), (30, "Mestre Ticker"), (40, "Lenda TickerHunter"))
NIVEL_MAX = 50


def xp_para_entrar(nivel: int) -> int:
    """XP total necessário para alcançar `nivel` (nível 1 = 0 XP)."""
    n = max(1, min(int(nivel), NIVEL_MAX)) - 1
    return _BASE * n + _PASSO * n * (n - 1) // 2


def titulo(nivel: int) -> str:
    t = TITULOS[0][1]
    for n, nome in TITULOS:
        if nivel >= n:
            t = nome
    return t


def nivel_de(xp) -> int:
    try:
        xp = max(0, int(xp))
    except (TypeError, ValueError):
        xp = 0
    n = 1
    while n < NIVEL_MAX and xp >= xp_para_entrar(n + 1):
        n += 1
    return n


def estado(xp) -> dict:
    """Nível atual, progresso até o próximo e XP que falta."""
    try:
        xp = max(0, int(xp))
    except (TypeError, ValueError):
        xp = 0
    n = nivel_de(xp)
    ini = xp_para_entrar(n)
    maximo = n >= NIVEL_MAX
    fim = ini if maximo else xp_para_entrar(n + 1)
    faixa = max(1, fim - ini)
    pct = 1.0 if maximo else min(1.0, (xp - ini) / faixa)
    return {"nivel": n, "titulo": titulo(n), "xp": xp, "xp_nivel_ini": ini, "xp_proximo": fim, "xp_no_nivel": xp - ini,
            "xp_faixa": 0 if maximo else faixa, "falta": 0 if maximo else fim - xp, "pct": pct, "maximo": maximo,
            "proximo_titulo": None if maximo else titulo(n + 1)}


def historico(xp_total: int, xp_dia: dict) -> list[dict]:
    """Datas em que cada nível foi alcançado, dentro da janela de dias guardada (XP anterior à janela entra como ponto de partida)."""
    dias = sorted((d, int(v)) for d, v in (xp_dia or {}).items() if isinstance(v, (int, float)) and v > 0)
    acum = max(0, int(xp_total)) - sum(v for _, v in dias)
    acum = max(0, acum)
    atual, saida = nivel_de(acum), []
    for d, v in dias:
        acum += v
        n = nivel_de(acum)
        while atual < n:
            atual += 1
            saida.append({"nivel": atual, "titulo": titulo(atual), "data": d})
    return saida


def subiu(xp_antes, xp_depois) -> dict | None:
    """Dados da celebração se o XP novo cruzou um nível; senão None."""
    a, b = nivel_de(xp_antes), nivel_de(xp_depois)
    return {"de": a, "para": b, "titulo": titulo(b)} if b > a else None
