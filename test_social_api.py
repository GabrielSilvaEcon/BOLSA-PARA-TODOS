"""Social do app novo (rotas /social*): pedido de amizade, aceite, lista com classificação, perfil, desafio e convite entre duas contas."""
import pytest
from fastapi.testclient import TestClient

import api.main as API
import trader_dados as TD


@pytest.fixture
def dois(monkeypatch):
    import banco
    import contas
    from test_trader_mesa import banco_isolado, livro
    from test_perfil_foto import _contas
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    with banco_isolado(), livro(pat=300_000.0, caixa=200_000.0):
        _contas(banco, "ana@x.com", "bia@x.com")
        import battle as BT
        import battle_dados as BD
        import test_api as T
        from datetime import date
        T._cartas_teste()
        cs = []
        for e, u in (("ana@x.com", "ana_h"), ("bia@x.com", "bia_h")):
            banco.sis_atualizar_conta("id-" + e, {"status": "ativa"})
            c = TestClient(API.app)
            c.headers["Authorization"] = f"Bearer {contas.criar_sessao('id-' + e)}"
            assert c.post("/perfil", json={"usuario": u, "nome": u.upper()}).status_code == 200
            t = c.post("/ticker/tutorial/bau").json()        # desde INICIAL = (), o baralho só existe depois do Baú Iniciante
            for it in t["cartas"]:
                c.post("/cartas/equipar", json={"tk": it["tk"]})
            cs.append(c)
        yield cs


def test_fluxo_de_amizade_e_desafio(dois):
    ana, bia = dois
    b = ana.get("/social/buscar", params={"texto": "bia"}).json()["itens"]
    assert [x["usuario"] for x in b] == ["bia_h"] and b[0]["estado"] is None
    assert ana.post("/social/pedir", json={"usuario": "@bia_h"}).json()["resultado"] == "enviado"
    assert [x["usuario"] for x in ana.get("/social").json()["enviados"]] == ["bia_h"]
    rec = bia.get("/social").json()["recebidos"]
    assert [x["usuario"] for x in rec] == ["ana_h"]
    assert bia.post("/social/responder", json={"h": rec[0]["h"], "aceitar": True}).status_code == 200
    s = ana.get("/social").json()
    assert [x["usuario"] for x in s["amigos"]] == ["bia_h"] and s["eu"]["usuario"] == "ana_h" and "trade" in s["amigos"][0]
    h_bia = s["amigos"][0]["h"]
    p = ana.get(f"/social/perfil/{h_bia}").json()
    assert p["usuario"] == "bia_h" and p["rel"] == "amigos" and not p["restrito"]
    h_ana = bia.get("/social").json()["amigos"][0]["h"]
    for jogo in ("ticker", "trade"):
        d = ana.post("/social/desafiar", json={"h": h_bia, "jogo": jogo}).json()
        assert d["id"] and "codigo" not in d
        assert ana.get("/social/desafio", params={"h": h_bia}).json()["estado"] == "aguardando"
        cv = bia.get("/social").json()["convites"]
        assert len(cv) == 1 and cv[0]["jogo"] == jogo and cv[0]["usuario"] == "ana_h"
        e = bia.post("/social/convite/entrar", json={"h": h_ana}).json()
        assert e["jogo"] == jogo and e["id"] == d["id"]
        st = ana.get("/social/desafio", params={"h": h_bia}).json()
        assert st["estado"] == "aceito" and st["id"] == d["id"]          # a partida começou sozinha para os dois
        if jogo == "ticker":
            assert ana.get(f"/ticker/online/{d['id']}").json()["fase"] == "em_jogo"
        else:
            assert ana.get(f"/trade/salas/{d['id']}").json()["estado"] == "jogo"
        assert bia.get("/social").json()["convites"] == []
        ana.post("/social/desafio/cancelar", json={"h": h_bia})


def test_desafio_recusado_e_cancelado(dois):
    ana, bia = dois
    h_bia = ana.get("/social/buscar", params={"texto": "bia"}).json()["itens"][0]["h"]
    ana.post("/social/pedir", json={"usuario": "bia_h"})
    h_ana = bia.get("/social").json()["recebidos"][0]["h"]
    bia.post("/social/responder", json={"h": h_ana, "aceitar": True})
    ana.post("/social/desafiar", json={"h": h_bia, "jogo": "ticker"})
    assert bia.post("/social/convite/recusar", json={"h": h_ana}).status_code == 200
    assert ana.get("/social/desafio", params={"h": h_bia}).json()["estado"] == "recusado"
    assert ana.post("/social/desafio/cancelar", json={"h": h_bia}).status_code == 200
    assert ana.get("/social/desafio", params={"h": h_bia}).json()["estado"] == "expirado"
    ana.post("/social/desafiar", json={"h": h_bia, "jogo": "ticker"})                   # a primeira foi fechada: dá para desafiar de novo
    ana.post("/social/desafio/cancelar", json={"h": h_bia})
    assert bia.get("/social").json()["convites"] == []

def test_nao_desafia_quem_nao_e_amigo_e_bloqueio_esconde(dois):
    ana, bia = dois
    h_bia = ana.get("/social/buscar", params={"texto": "bia"}).json()["itens"][0]["h"]
    assert ana.post("/social/desafiar", json={"h": h_bia, "jogo": "trade"}).status_code == 400
    assert ana.post("/social/bloquear", json={"h": h_bia}).status_code == 200
    assert ana.get("/social/buscar", params={"texto": "bia"}).json()["itens"] == []
    assert bia.get("/social/buscar", params={"texto": "ana"}).json()["itens"] == []
    assert ana.post("/social/pedir", json={"usuario": "ninguem_aqui"}).status_code == 400
