"""Cenário econômico do app novo (cenario_api.py) e as rotas /cenario e /home, com indicadores falsos (sem rede)."""
import pandas as pd

import cenario_api as CA
from test_api import cli  # noqa: F401  (mesma conta de teste)

BASE = {"selic_meta": 15.0, "focus_selic": 14.5, "ipca_12m": 4.7, "focus_ipca": 4.6, "pib": 2.1, "desemprego": 5.8, "dolar": 5.4, "vix": 16,
        "fed_funds": 4.0, "us10y": 4.2, "brent": 65, "minerio": 100, "dxy": 120, "embi": 200, "divida_bruta": 78, "primario_12m": -0.5}


def _foto():
    import macro_cenario as MC
    import macro_fontes as MF
    R = {}
    for i, spec in MF.CATALOGO.items():
        v = BASE.get(i, 1.0)
        datas = pd.date_range(end="2026-10-31", periods=30, freq="MS")
        serie = [[d.strftime("%Y-%m-%d"), v * (1 + 0.002 * (k - 15))] for k, d in enumerate(datas)]
        R[i] = {"id": i, "nome": spec["nome"], "grupo": spec["grupo"], "unidade": spec["unidade"], "freq": spec["freq"], "status": "atualizado",
                "valor": v, "data": serie[-1][0], "serie": serie, "periodo_ref": "out/2026", "fonte": "BCB", "codigo": "x"}
    return {"indicadores": R, **MC.calcular(R)}


def test_montar_cenario():
    r = CA.montar(_foto())
    assert r["geral"]["veredito"] in ("BOM", "NEUTRO", "RUIM") and r["geral"]["texto"]
    p = {x["id"]: x for x in r["principais"]}
    assert p["selic_meta"]["valor"] == 15.0 and round(p["juro_real"]["valor"], 1) == 9.8 and len(p["selic_meta"]["serie"]) == 24
    assert all(s["classe"] in ("acao", "cripto") for s in r["beneficiados"] + r["pressionados"])     # sem fundos nem renda fixa
    assert r["fatores"] and all(-1 <= f["valor"] <= 1 for f in r["fatores"])


def test_rotas_cenario_e_home(cli, monkeypatch):
    import api.main as API
    import inicio_painel as IP
    import macro_servico as MS
    API._MERC_CACHE.clear()
    monkeypatch.setattr(MS, "cenario_compartilhado", _foto)
    monkeypatch.setattr(IP, "mercado_hoje", lambda: [{"rotulo": "Ibovespa", "valor": "130.000", "var": 0.5}])
    c = cli.get("/cenario")
    assert c.status_code == 200 and c.json()["principais"][0]["id"] == "selic_meta"
    h = cli.get("/home").json()
    assert "total" in h["missoes"] and "hoje" not in h        # a Home não espera a fonte externa de cotações
    assert cli.get("/home/cotacoes").json()["hoje"][0]["rotulo"] == "Ibovespa"
    API._MERC_CACHE.clear()
    monkeypatch.setattr(MS, "cenario_compartilhado", lambda: {})
    assert cli.get("/cenario").status_code == 424
