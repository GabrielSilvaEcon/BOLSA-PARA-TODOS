"""Competição · etapa 3, parte 2: temporadas e selos. Lógica pura."""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import competicao as C  # noqa: E402
import competicao_temporadas as T  # noqa: E402


def _est(pares):
    e = C.novo_estado("2026-09-01")
    e["hist"] = [{"d": d, "p": p} for d, p in pares]
    return e


def _dias(inicio, n):
    d, out = date.fromisoformat(inicio), []
    while len(out) < n:
        if d.weekday() < 5:
            out.append(d.isoformat())
        d += timedelta(days=1)
    return out


def _serie(inicio, n, passo):
    return _est([(d, 100_000 * (1 + passo * (i + 1))) for i, d in enumerate(_dias(inicio, n))])


def test_janelas_de_mes_e_trimestre():
    assert T.limites("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert T.limites("2028-02")[1] == date(2028, 2, 29)
    assert T.limites("2026-12") == (date(2026, 12, 1), date(2026, 12, 31))
    assert T.limites("2026-T1") == (date(2026, 1, 1), date(2026, 3, 31))
    assert T.limites("2026-T4") == (date(2026, 10, 1), date(2026, 12, 31))
    assert T.id_temporada("mensal", date(2026, 11, 8)) == "2026-11"
    assert T.id_temporada("trimestral", date(2026, 11, 8)) == "2026-T4"
    assert T.anterior("2026-01") == "2025-12" and T.anterior("2026-T1") == "2025-T4" and T.anterior("2026-T3") == "2026-T2"
    assert T.encerrada("2026-10", date(2026, 11, 1)) and not T.encerrada("2026-10", date(2026, 10, 31))


def test_id_invalido():
    for ruim in ("2026-13", "2026-T5", "26-01", "", "abc"):
        try:
            T.tipo_de(ruim)
        except ValueError:
            continue
        raise AssertionError(ruim)


def _grupo(n, estavel_primeiro=False):
    """n participantes em outubro; 'p0' lidera em retorno; 'calmo' tem o melhor Sharpe."""
    dias = _dias("2026-10-01", 12)
    part = []
    for i in range(n):
        pas = 0.003 - 0.0002 * i
        part.append({"apelido": f"p{i}", "email": f"p{i}@x",
                     "estado": _est([(d, 100_000 * (1 + pas * (k + 1) + (0.01 if k % 2 else -0.01))) for k, d in enumerate(dias)])})
    part.append({"apelido": "calmo", "email": "calmo@x", "estado": _est([(d, 100_000 * (1 + 0.0004 * (k + 1) + (0.0002 if k % 2 else -0.0002))) for k, d in enumerate(dias)])})
    return part


def test_rotulos_e_recentes():
    assert T.rotulo("2026-11") == "Novembro de 2026" and T.rotulo("2026-03") == "Março de 2026" and T.rotulo("2026-T4") == "4º trimestre de 2026"
    assert T.recentes("mensal", date(2026, 2, 10), 4) == ["2026-02", "2026-01", "2025-12", "2025-11"]
    assert T.recentes("trimestral", date(2026, 11, 8), 3) == ["2026-T4", "2026-T3", "2026-T2"]


