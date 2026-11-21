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
        sug = BT.baralho_padrao(T._cartas_teste(), date.today())
        for e in ("ana@x.com", "bia@x.com"):
            BD.gravar_pessoa(banco, e, {"deck": sug[:4], "hist": []})
        cs = []
        for e, u in (("ana@x.com", "ana_h"), ("bia@x.com", "bia_h")):
            banco.sis_atualizar_conta("id-" + e, {"status": "ativa"})
            c = TestClient(API.app)
            c.headers["Authorization"] = f"Bearer {contas.criar_sessao('id-' + e)}"
            assert c.post("/perfil", json={"usuario": u, "nome": u.upper()}).status_code == 200
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
    d = ana.post("/social/desafiar", json={"h": h_bia, "jogo": "ticker"}).json()
    assert d["id"] and d["codigo"]
    cv = bia.get("/social").json()["convites"]
    assert len(cv) == 1 and cv[0]["jogo"] == "ticker" and cv[0]["usuario"] == "ana_h"
    e = bia.post("/social/convite/entrar", json={"h": cv[0]["h"]}).json()
    assert e["jogo"] == "ticker" and e["id"] == d["id"]
    assert bia.get("/social").json()["convites"] == []
    t = ana.post("/social/desafiar", json={"h": h_bia, "jogo": "trade"})
    assert t.status_code == 200 and t.json()["id"] and t.json()["codigo"]
    e2 = bia.post("/social/convite/entrar", json={"h": cv[0]["h"]}).json()
    assert e2["jogo"] == "trade" and e2["id"] == t.json()["id"]


def test_nao_desafia_quem_nao_e_amigo_e_bloqueio_esconde(dois):
    ana, bia = dois
    h_bia = ana.get("/social/buscar", params={"texto": "bia"}).json()["itens"][0]["h"]
    assert ana.post("/social/desafiar", json={"h": h_bia, "jogo": "trade"}).status_code == 400
    assert ana.post("/social/bloquear", json={"h": h_bia}).status_code == 200
    assert ana.get("/social/buscar", params={"texto": "bia"}).json()["itens"] == []
    assert bia.get("/social/buscar", params={"texto": "ana"}).json()["itens"] == []
    assert ana.post("/social/pedir", json={"usuario": "ninguem_aqui"}).status_code == 400
