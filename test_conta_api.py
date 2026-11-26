"""Minha conta no app (rotas /conta*): resumo, trocar nome, atividades e cópia dos dados da própria conta."""
import json

from test_social_api import dois  # noqa: F401  (fixture: duas contas logadas)


def test_resumo_nome_atividades_e_dados(dois):
    ana, bia = dois
    r = ana.get("/conta").json()
    assert r["email"] == "ana@x.com" and r["tipo"] == "Usuário" and "senha_hash" not in r and set(r) >= {"nome", "cadastro", "provedor", "email_verificado"}
    n = ana.post("/conta/nome", json={"nome": "Ana Paula"})
    assert n.status_code == 200 and n.json()["nome"] == "Ana Paula"
    assert ana.get("/conta").json()["nome"] == "Ana Paula"
    assert bia.get("/conta").json()["nome"] != "Ana Paula"                         # cada pessoa só mexe na própria conta
    assert ana.post("/conta/nome", json={"nome": "   "}).status_code == 400          # nome vazio é recusado
    d = json.loads(ana.get("/conta/dados").json()["json"])
    assert d["conta"]["email"] == "ana@x.com" and "senha_hash" not in json.dumps(d)
    ativ = ana.get("/conta/atividades").json()["itens"]
    assert {"Nome atualizado", "Dados baixados"} <= {a["rotulo"] for a in ativ}
    assert bia.get("/conta/atividades").json()["itens"] == [] or all(a["rotulo"] != "Nome atualizado" for a in bia.get("/conta/atividades").json()["itens"])


def test_sem_login_nao_acessa(dois):
    from fastapi.testclient import TestClient

    import api.main as API
    anon = TestClient(API.app)
    for rota in ("/conta", "/conta/atividades", "/conta/dados"):
        assert anon.get(rota).status_code == 401
    assert anon.post("/conta/nome", json={"nome": "x"}).status_code == 401
