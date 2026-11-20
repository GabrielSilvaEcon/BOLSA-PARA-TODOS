"""Mercado do app novo: contas puras (preço justo, indicadores, resumo) e as rotas /mercado, sem rede."""
from math import sqrt

import pytest

import mercado_api as MA
from test_api import cli  # noqa: F401  (mesma conta de teste)

ACAO = {"ticker": "PETR4", "preco": 30.0, "lpa": 5.0, "vpa": 25.0, "div_12m": 3.0, "roe": 0.2, "margem_liq": 0.18, "div_pl": 80.0,
        "div_ano": {2021: 2.0, 2022: 4.0, 2023: 3.0, 2024: 3.0, 2025: 3.0, 2026: 9.0}}


def test_indicadores_e_faixas():
    ind = MA.indicadores(ACAO)
    assert ind["pl"] == pytest.approx(6) and ind["pvp"] == pytest.approx(1.2) and ind["dy"] == pytest.approx(10)
    assert ind["roe"] == pytest.approx(20) and ind["margem"] == pytest.approx(18)
    faixas = {i["id"]: i["faixa"] for i in MA.lista_indicadores(ACAO)}
    assert faixas == {"pl": "bom", "pvp": "bom", "dy": "bom", "roe": "bom", "margem": "bom", "div_pl": "medio"}


def test_banco_sem_divida_pl():
    assert "div_pl" not in {i["id"] for i in MA.lista_indicadores({**ACAO, "ticker": "ITUB4"})}


def test_preco_justo_graham_e_bazin():
    pj = MA.preco_justo(ACAO, ano=2026)
    assert pj["graham"]["justo"] == pytest.approx(sqrt(22.5 * 5 * 25))
    assert pj["bazin"]["justo"] == pytest.approx(3.0 / 0.06)           # média 2021–2025 = 3,0 (o ano corrente fica de fora)
    assert pj["bazin"]["status"] == "bom" and pj["bazin"]["margem"] == pytest.approx(40)


def test_preco_justo_sem_dados_nao_inventa():
    pj = MA.preco_justo({"preco": 10.0, "lpa": -1.0, "vpa": 5.0}, ano=2026)
    assert pj["graham"]["justo"] is None and "prejuízo" in pj["graham"]["aviso"]
    assert pj["bazin"]["justo"] is None and pj["bazin"]["status"] == "na"


def test_resumo_tres_cartoes():
    r = MA.resumo(ACAO, MA.preco_justo(ACAO, ano=2026))
    assert [c["id"] for c in r] == ["preco", "saude", "dividendos"]
    assert r[1]["status"] == "bom" and r[2]["texto"] == "Paga bem"
    vazio = MA.resumo({"ticker": "X", "preco": 1.0}, MA.preco_justo({"preco": 1.0}))
    assert all(c["status"] == "na" for c in vazio)


def test_rotas_mercado(cli, monkeypatch):
    import inicio_painel as IP
    import api.main as API
    API._MERC_CACHE.clear()
    monkeypatch.setattr(IP, "mercado_hoje", lambda: [{"rotulo": "Ibovespa", "valor": "130.000", "var": 0.5}])
    monkeypatch.setattr(MA, "dados_acao", lambda tk: {**ACAO, "ticker": tk})
    monkeypatch.setattr(MA, "historico", lambda tk, p="1a": [{"t": "2026-11-18", "c": 29.0}, {"t": "2026-11-19", "c": 30.0}])
    m = cli.get("/mercado").json()
    assert m["hoje"][0]["rotulo"] == "Ibovespa" and m["populares"] and any(t["pronto"] for t in m["tipos"])
    b = cli.get("/mercado/busca", params={"texto": "petro"}).json()["itens"]
    assert any(i["ticker"] == "PETR4" for i in b)
    a = cli.get("/mercado/acao/petr4").json()
    assert a["ticker"] == "PETR4" and a["nome"] == "Petrobras" and a["var_dia"] == pytest.approx(100 / 29)
    assert a["preco_justo"]["graham"]["justo"] and len(a["serie"]) == 2 and len(a["resumo"]) == 3
    assert cli.get("/mercado/acao/ZZZZ3").status_code == 404
    assert cli.get("/mercado/acao/PETR4/historico", params={"periodo": "5a"}).json()["periodo"] == "5a"
