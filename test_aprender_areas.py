"""Áreas do Aprender (aprender_areas.py) e as rotas /aprender e /aprender/area."""
import aprender_areas as AA
import jornada_conteudo as J
from test_api import cli  # noqa: F401  (mesma conta de teste)


def test_toda_unidade_tem_area_e_nada_se_perde():
    assert all(AA.area_da_unidade(u["id"]) in AA.AREA_POR_ID for u in J.UNIDADES)
    todas = set()
    for a in AA.AREAS:
        if a["id"] == "certificacoes":
            for c in AA.CERTIFICACOES:
                todas |= AA.licoes_da_area("certificacoes", c["id"])
        else:
            todas |= AA.licoes_da_area(a["id"])
    assert todas == {l["id"] for l in J.LICOES}                       # toda lição aparece em exatamente uma área
    assert all(AA.nivel(l["id"]) in AA.NIVEIS for l in J.LICOES)


def test_mapa_da_area_e_proxima_por_area():
    m = AA.mapa_area({"l_risco": {"melhor": 1.0}}, "financas")
    ls = [l for u in m for l in u["licoes"]]
    assert ls[0]["estado"] == "concluida" and ls[1]["estado"] == "proxima"
    inv = [l for u in AA.mapa_area({}, "investimentos") for l in u["licoes"]]
    assert inv[0]["estado"] == "proxima"                                # cada área tem a sua próxima lição
    assert AA.mapa_area({}, "certificacoes", "cpa") == []                # certificações ainda sem trilhas (fase 5)


def test_revisao_so_da_area():
    erros = ["l_risco_1", "l_acoes_1", "l_juros_2"]
    s = AA.iniciar_revisao_area(erros, "financas")
    assert s["ids"] == ["l_risco_1", "l_juros_2"] and s["revisao"]
    assert AA.iniciar_revisao_area(erros, "trading") is None
    r = {a["id"]: a for a in AA.resumo_areas({}, erros)}
    assert r["financas"]["erros"] == 2 and r["investimentos"]["erros"] == 1


def test_rotas(cli):
    d = cli.get("/aprender").json()
    assert "mapa" in d and len(d["areas"]) == len(AA.AREAS)            # o mapa antigo continua para apps antigos
    a = cli.get("/aprender/area/financas").json()
    assert a["area"]["id"] == "financas" and a["mapa"][0]["id"] == "u_inicio" and "nivel" in a["mapa"][0]["licoes"][0]
    c = cli.get("/aprender/area/certificacoes").json()
    assert [x["id"] for x in c["certificacoes"]] == ["cpa", "cpro_r", "cpro_i"]
    assert cli.get("/aprender/area/xyz").status_code == 404
    assert cli.post("/aprender/licao/revisao:trading").status_code == 400
