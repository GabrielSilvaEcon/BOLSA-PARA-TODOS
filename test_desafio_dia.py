"""Desafio do dia: o mesmo gráfico para todos, uma tentativa, ranking do dia e prêmio no dia seguinte."""
import pytest

import desafio_dia as DD
from test_social_api import dois  # noqa: F401  (duas contas)


def test_regras_puras():
    assert DD.semente("2026-11-21") == DD.semente("2026-11-21") != DD.semente("2026-11-22")
    assert DD.premio(1)["tc"] == 30 and DD.premio(50)["id"] == "top100" and DD.premio(500)["id"] == "participacao" and DD.premio(None) is None
    o = DD.ordenar([{"nota": 5, "fim": "b"}, {"nota": 9, "fim": "c"}, {"nota": 5, "fim": "a"}, {"nota": None}])
    assert [(x["nota"], x["fim"], x["pos"]) for x in o] == [(9, "c", 1), (5, "a", 2), (5, "b", 3)]


def _jogar_ate_o_fim(cli, monkeypatch, t):
    r = cli.post("/desafio/jogar")
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta", "tipo": "continuacao"})
    t["agora"] += 10_000
    f = cli.get(f"/trade/solo/{pid}").json()
    assert f["fase"] == "fim"
    return pid


def test_mesmo_grafico_uma_tentativa_e_ranking(dois, monkeypatch):
    import api.main as API
    ana, bia = dois
    t = {"agora": 1_000_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    p1 = _jogar_ate_o_fim(ana, monkeypatch, t)
    assert ana.post("/desafio/jogar").status_code == 409                     # uma tentativa só
    p2 = _jogar_ate_o_fim(bia, monkeypatch, t)
    c1 = ana.get(f"/trade/solo/{p1}").json()["fim"]["revelado"]["ticker"]
    c2 = bia.get(f"/trade/solo/{p2}").json()["fim"]["revelado"]["ticker"]
    assert c1 == c2                                                         # o mesmo gráfico para todos
    d = ana.get("/desafio").json()
    assert d["jogaram"] == 2 and d["meu"]["terminou"] and d["meu"]["pos"] in (1, 2) and d["meu"]["de"] == 2
    h = ana.get("/home").json()["competicao"]
    assert h["divisao"]["nome"] == "Bronze" and h["desafio_max"] == d["meu"]["nota"]       # melhor nota no topo da Home
    rk = ana.get("/desafio/ranking").json()
    assert rk["total"] == 2 and len(rk["linhas"]) == 2 and any(x["eu"] for x in rk["linhas"])
