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
    assert AA.mapa_area({}, "certificacoes", "cpo_inexistente") == []   # certificação sem trilhas não traz nada


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


def test_fase2_educacao_financeira_e_cartoes():
    import edu_conteudo as E
    import educacao as ED
    fin = AA.mapa_area({}, "financas")
    assert [u["id"] for u in fin] == ["u_inicio", "uf_orc", "uf_cartao", "uf_dividas", "uf_patrimonio"]   # "Primeiros passos" continua primeiro
    assert [u["id"] for u in AA.mapa_area({}, "cartoes")] == ["uc_intro", "uc_pontos", "uc_uso"]
    novas = [l for l in J.LICOES if l["unidade"].startswith(("uf_", "uc_"))]
    assert len(novas) == 24
    for l in novas:
        for modo in ("iniciante", "intermediario", "avancado"):                # toda aula nova tem o texto inteiro em todo modo
            assert len(ED.texto_aula(E.POR_ID[l["aula"]], modo)) > 300, (l["id"], modo)
    assert AA.nivel("lf_rotativo") == "intermediario" and AA.nivel("lf_salario") == "iniciante"
    assert not any(a["id"].startswith(("af_", "ac_")) for a in E.AULAS)


def test_fase3_trading_investimentos_e_nivelamento(cli):
    assert [u["id"] for u in AA.mapa_area({}, "trading")] == ["ut_bolsa", "ut_grafico", "ut_wyckoff", "ut_gestao"]
    inv = [u["id"] for u in AA.mapa_area({}, "investimentos")]
    assert inv[:2] == ["u_rf", "ui_rf_pratica"] and "ui_gestao" in inv                 # trilhas novas perto do assunto
    assert AA.tem_nivelamento("financas") and not AA.tem_nivelamento("certificacoes")
    # nivelamento pela API: errar a 1ª pergunta recomenda a 1ª trilha; não dá XP nem muda o progresso
    antes = cli.get("/aprender").json()["resumo"]
    r = cli.post("/aprender/licao/nivel:trading").json()
    assert r["sessao"]["titulo"] == "Teste de nivelamento"
    import jornada_conteudo as JC
    fim, primeira = None, True
    while fim is None:
        ex = JC.EX_POR_ID[r["exercicio"]["id"]]
        certa = {"escolha": ex.get("correta"), "completar": ex.get("correta"), "vf": ex.get("correta"),
                 "ordenar": ex.get("itens"), "pares": dict(ex.get("pares") or [])}[ex["tipo"]]
        if primeira:
            certa = {"vf": not ex["correta"]}.get(ex["tipo"], -1)
            primeira = False
        r = cli.post("/aprender/responder", json={"id": ex["id"], "resposta": certa}).json()
        fim = r.get("fim")
    assert fim["nivelamento"] and fim["xp"] == 0 and fim["recomendada"]["id"] == "ut_bolsa"
    depois = cli.get("/aprender").json()["resumo"]
    assert depois["xp"] == antes["xp"] and depois["erros"] == antes["erros"]
    assert cli.get("/aprender/area/trading").json()["recomendada"] == "ut_bolsa"
    assert cli.post("/aprender/licao/nivel:certificacoes").status_code == 400


def test_fase4_cripto_e_especializacoes():
    assert [u["id"] for u in AA.mapa_area({}, "cripto")] == ["uk_fund", "uk_seg", "uk_avanc"]
    esp = [u["id"] for u in AA.mapa_area({}, "especializacoes")]
    assert esp == ["ue_mei", "ue_autonomo", "ue_familia", "ue_financiamento", "ue_aposentadoria", "ue_golpes", "ue_economia"]
    r = {a["id"]: a for a in AA.resumo_areas({}, [])}
    assert r["cripto"]["total"] == 8 and r["especializacoes"]["total"] == 21 and not r["cripto"]["em_breve"]
    assert AA.tem_nivelamento("cripto") and AA.tem_nivelamento("especializacoes")


def test_fase5_cpa_e_simulado(cli):
    assert [u["id"] for u in AA.mapa_area({}, "certificacoes", "cpa")] == ["ucpa_sfn", "ucpa_etica", "ucpa_economia", "ucpa_produtos"]
    assert AA.mapa_area({}, "certificacoes", "cpro_r") == []                     # certificações não se misturam
    c = {x["id"]: x for x in AA.certificacoes({})}
    assert c["cpa"]["total"] == 11 and not c["cpa"]["em_breve"] and c["cpro_r"]["em_breve"]
    s = AA.iniciar_simulado("cpa", "2026-11-24")
    assert s["total"] == AA.SIMULADO_QUESTOES and s["ids"] == AA.iniciar_simulado("cpa", "2026-11-24")["ids"]
    assert all(J.EX_POR_ID[e]["licao"].startswith("lcpa_") for e in s["ids"])
    assert AA.iniciar_simulado("cpro_r", "x") is None
    # pela API: simulado inteiro, acertando tudo → 100% e aprovado
    a = cli.get("/aprender/area/certificacoes?cert=cpa").json()
    assert a["simulado"]["questoes"] == 20 and a["mapa"]
    r = cli.post("/aprender/licao/simulado:cpa").json()
    assert r["sessao"]["titulo"] == "Simulado"
    fim = None
    while fim is None:
        ex = J.EX_POR_ID[r["exercicio"]["id"]]
        certa = {"escolha": ex.get("correta"), "completar": ex.get("correta"), "vf": ex.get("correta"),
                 "ordenar": ex.get("itens"), "pares": dict(ex.get("pares") or [])}[ex["tipo"]]
        r = cli.post("/aprender/responder", json={"id": ex["id"], "resposta": certa}).json()
        fim = r.get("fim")
    assert fim["simulado"] and fim["aprovado"] and fim["pct"] == 1.0 and fim["xp"] > 0
    assert cli.post("/aprender/licao/simulado:cpro_i").status_code == 400
