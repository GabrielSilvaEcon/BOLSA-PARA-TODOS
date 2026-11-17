"""Competição · etapa 3, parte 1: ranking ajustado ao risco (Sharpe). Lógica pura."""
import math
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import competicao as C  # noqa: E402


def _est(pats):
    e = C.novo_estado("2026-11-02")
    e["hist"] = [{"d": (date(2026, 11, 2) + timedelta(days=i)).isoformat(), "p": p} for i, p in enumerate(pats)]
    return e


def test_sem_pregoes_suficientes_ou_sem_variacao_nao_tem_sharpe():
    assert C.metricas_risco(_est([100_000 * 1.01] * 9)) is None
    assert C.metricas_risco(_est([100_000.0] * 12)) is None            # tudo em caixa: desvio zero, não é "Sharpe infinito"
    assert C.metricas_risco({}) is None


def test_sharpe_confere_com_calculo_manual():
    pats = [100_000 * (1 + 0.002 * i + (0.003 if i % 2 else -0.003)) for i in range(1, 13)]
    m = C.metricas_risco(_est(pats))
    base = [C.CAPITAL_INICIAL] + pats
    r = [b / a - 1 for a, b in zip(base, base[1:])]
    mu = sum(r) / len(r)
    dp = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1))
    assert math.isclose(m["sharpe"], mu / dp * math.sqrt(252), rel_tol=1e-9)
    assert math.isclose(m["vol"], dp * math.sqrt(252), rel_tol=1e-9)


def test_participante_fora_do_ranking_minimo_nao_entra_no_risco():
    part = [{"apelido": "x", "email": "a", "estado": _est([100_000 * (1 + 0.001 * i) for i in range(1, 4)])}]
    assert C.montar_ranking(part, date(2026, 11, 20))["listas"]["risco"] == []


def test_entra_no_ranking_ja_no_primeiro_fechamento():
    assert C.MIN_DIAS_RANKING == 1
    part = [{"apelido": "novo", "email": "a", "estado": _est([100_500.0])}, {"apelido": "sem", "email": "b", "estado": _est([])}]
    rk = C.montar_ranking(part, date(2026, 11, 3))
    assert [x["apelido"] for x in rk["listas"]["geral"]] == ["novo"] and rk["listas"]["risco"] == []      # risco continua exigindo 10 pregões
    assert C.pregoes(1) == "1 pregão" and C.pregoes(5) == "5 pregões"
