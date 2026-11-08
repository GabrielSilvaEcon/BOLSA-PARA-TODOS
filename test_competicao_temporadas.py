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


def test_retorno_mede_so_dentro_da_janela():
    # outubro: 100k -> 110k; novembro começa de 110k e termina em 99k: -10% em novembro, +10% em outubro
    est = _est([("2026-10-30", 110_000.0), ("2026-11-03", 105_000.0), ("2026-11-04", 99_000.0)])
    nov = T.desempenho(est, "2026-11")
    assert abs(nov["ret"] - (99_000 / 110_000 - 1)) < 1e-12 and nov["dias"] == 2
    assert abs(nov["dd"] - (99_000 / 110_000 - 1)) < 1e-12
    out = T.desempenho(est, "2026-10")
    assert abs(out["ret"] - 0.10) < 1e-12                           # parte do capital inicial (sem histórico anterior)
    assert T.desempenho(est, "2026-12") is None                     # sem pregão na janela


def test_temporada_encerrada_e_congelada():
    est = _est([("2026-10-02", 101_000.0), ("2026-10-30", 108_000.0)])
    antes = T.desempenho(est, "2026-10")
    est["hist"].append({"d": "2026-11-05", "p": 50_000.0})          # o que vem depois não altera outubro
    assert T.desempenho(est, "2026-10") == antes


def test_minimo_de_pregoes_na_temporada():
    part = [{"apelido": "a", "email": "a@x", "estado": _serie("2026-11-02", 4, 0.001)},
            {"apelido": "b", "email": "b@x", "estado": _serie("2026-11-02", 5, 0.001)}]
    r = T.montar_temporada(part, "2026-11", date(2026, 11, 20))
    assert [x["apelido"] for x in r["lista"]] == ["b"] and r["n"] == 1
    tri = T.montar_temporada(part, "2026-T4", date(2026, 11, 20))
    assert tri["n"] == 0                                            # trimestral exige 10 pregões


def test_ranking_ordena_por_retorno_e_nao_vaza_email():
    part = [{"apelido": n, "email": f"{n}@x", "estado": _serie("2026-11-02", 8, p)} for n, p in (("lenta", 0.001), ("rapida", 0.004), ("media", 0.002))]
    r = T.montar_temporada(part, "2026-11", date(2026, 11, 20))
    assert [x["apelido"] for x in r["lista"]] == ["rapida", "media", "lenta"]
    assert r["posicoes"]["rapida@x"] == 1 and not r["encerrada"]
    pub = T.publico(r)
    assert "posicoes" not in pub and "@" not in repr(pub)


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


def test_selos_so_depois_do_encerramento():
    part = _grupo(8)
    em_andamento = T.montar_temporada(part, "2026-10", date(2026, 10, 20))
    assert T.conceder_selos(em_andamento) == {}
    final = T.montar_temporada(part, "2026-10", date(2026, 11, 2))
    selos = T.conceder_selos(final)
    assert {s["selo"] for s in selos["p0@x"]} == {"ouro"}
    assert [s["selo"] for s in selos["p1@x"]] == ["prata"] and [s["selo"] for s in selos["p2@x"]] == ["bronze"]
    assert "p3@x" not in selos                                      # 9 participantes: sem Top 10 (ninguém fica de fora)
    assert [s["selo"] for s in selos["calmo@x"]] == ["equilibrio"]


def test_poucos_participantes_nao_geram_podio():
    final = T.montar_temporada(_grupo(2), "2026-10", date(2026, 11, 2))      # 3 qualificados
    assert final["n"] == 3 and T.conceder_selos(final) == {}


def test_top10_com_campo_grande():
    part = [{"apelido": f"u{i:02d}", "email": f"u{i}@x", "estado": _serie("2026-10-01", 6, 0.0001 * (30 - i))} for i in range(14)]
    selos = T.conceder_selos(T.montar_temporada(part, "2026-10", date(2026, 11, 2)))
    assert [s["selo"] for s in selos["u0@x"]] == ["ouro"]
    assert [s["selo"] for s in selos["u5@x"]] == ["top10"] and "u12@x" not in selos
    assert selos["u5@x"][0]["id"] == "top10|2026-10" and selos["u5@x"][0]["tipo"] == "mensal"


def test_juntar_selos_e_idempotente():
    s = [{"id": "ouro|2026-10", "selo": "ouro", "temp": "2026-10", "tipo": "mensal", "pos": 1}]
    novo = [dict(s[0]), {"id": "top10|2026-T3", "selo": "top10", "temp": "2026-T3", "tipo": "trimestral", "pos": 7}]
    r = T.juntar_selos(s, novo)
    assert [x["id"] for x in r] == ["ouro|2026-10", "top10|2026-T3"] and T.juntar_selos(r, novo) == r


def test_planejar_publica_atuais_congela_anterior_uma_vez():
    part = _grupo(8)
    p = T.planejar(part, date(2026, 11, 2))
    assert set(p["publicar"]) == {"2026-11", "2026-T4", "2026-10", "2026-T3"}
    assert p["encerradas"] == ["2026-10", "2026-T3"] and p["publicar"]["2026-10"]["encerrada"] and not p["publicar"]["2026-11"]["encerrada"]
    assert [s["selo"] for s in p["selos"]["p0@x"]] == ["ouro"]
    assert p["posicoes"]["p0@x"]["2026-T4"] == {"pos": 1, "n": 9}
    assert "@" not in repr(p["publicar"])
    # já congelada: nada recalculado, nenhum selo novo
    q = T.planejar(part, date(2026, 11, 3), ja_encerrada=lambda tid: True)
    assert set(q["publicar"]) == {"2026-11", "2026-T4"} and q["selos"] == {} and q["encerradas"] == []


def test_planejar_sem_conseguir_conferir_recalcula():
    def quebra(tid):
        raise RuntimeError("banco fora")
    assert T.planejar(_grupo(8), date(2026, 11, 2), ja_encerrada=quebra)["encerradas"] == ["2026-10", "2026-T3"]


def test_rotulos_e_recentes():
    assert T.rotulo("2026-11") == "Novembro de 2026" and T.rotulo("2026-03") == "Março de 2026" and T.rotulo("2026-T4") == "4º trimestre de 2026"
    assert T.recentes("mensal", date(2026, 2, 10), 4) == ["2026-02", "2026-01", "2025-12", "2025-11"]
    assert T.recentes("trimestral", date(2026, 11, 8), 3) == ["2026-T4", "2026-T3", "2026-T2"]


def test_descricao_ignora_selo_malformado():
    assert T.descricao_selo({"selo": "ouro", "temp": "2026-10"}) == "Ouro · 1º lugar · Outubro de 2026"
    assert T.descricao_selo({"selo": "xyz", "temp": "2026-10"}) is None and T.descricao_selo({"selo": "ouro", "temp": "lixo"}) is None
    assert T.descricao_selo({}) is None


def test_avisos_de_selos():
    from datetime import datetime, timezone
    quando = datetime(2026, 11, 2, 21, 30, tzinfo=timezone.utc)
    selos = [{"id": "ouro|2026-10", "selo": "ouro", "temp": "2026-10", "tipo": "mensal", "pos": 1},
             {"id": "equilibrio|2026-10", "selo": "equilibrio", "temp": "2026-10", "tipo": "mensal", "pos": 1},
             {"id": "top10|2026-T3", "selo": "top10", "temp": "2026-T3", "tipo": "trimestral", "pos": 7},
             {"id": "lixo|x", "selo": "lixo", "temp": "x"}]
    av = T.avisos_de_selos(selos, quando)
    assert [a["dedup"] for a in av] == ["comp|selo|ouro|2026-10", "comp|selo|equilibrio|2026-10", "comp|selo|top10|2026-T3"]
    assert av[0]["titulo"] == "Você ganhou o selo Ouro" and "1º lugar" in av[0]["texto"] and av[0]["importancia"] == "media"
    assert av[1]["titulo"] == "Você ganhou o selo Equilíbrio" and "ajustado ao risco" in av[1]["texto"]
    assert av[2]["importancia"] == "baixa" and "7º" in av[2]["texto"] and "R$" not in " ".join(a["texto"] for a in av)
    assert T.avisos_de_selos(selos, quando, {"global": False}) == [] and T.avisos_de_selos(None, quando) == []
