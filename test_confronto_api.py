"""Tela de confronto antes do duelo (GET /trade/salas/{id}/confronto): quem joga, com nome, avatar e divisão; só para quem está na partida."""
from fastapi.testclient import TestClient

import api.main as API
from test_social_api import dois  # noqa: F401  (fixture: duas contas amigas logadas)


def test_confronto_mostra_os_dois_lados_so_para_quem_joga(dois):
    ana, bia = dois
    ana.post("/social/pedir", json={"usuario": "bia_h"})
    h_ana = bia.get("/social").json()["recebidos"][0]["h"]
    bia.post("/social/responder", json={"h": h_ana, "aceitar": True})
    h_bia = ana.get("/social").json()["amigos"][0]["h"]
    d = ana.post("/social/desafiar", json={"h": h_bia, "jogo": "trade"}).json()
    assert bia.post("/social/convite/entrar", json={"h": h_ana}).json()["id"] == d["id"]
    c = ana.get(f"/trade/salas/{d['id']}/confronto")
    assert c.status_code == 200
    j = c.json()
    assert j["voce"]["nome"] == "ANA_H" and [a["nome"] for a in j["adversarios"]] == ["BIA_H"]
    for lado in (j["voce"], *j["adversarios"]):
        assert isinstance(lado["trofeus"], int) and lado["divisao"]["nome"] == "Bronze" and lado["avatar_img"]
    assert bia.get(f"/trade/salas/{d['id']}/confronto").json()["voce"]["nome"] == "BIA_H"          # cada um se vê como "você"
    assert TestClient(API.app).get(f"/trade/salas/{d['id']}/confronto").status_code == 401


def test_bot_aparece_como_jogador_comum_e_sempre_com_o_mesmo_avatar():
    bots = {"bot1@x": {"nome": "Rafa_Trader", "trofeus": 230, "nivel": "normal"}}
    a = API._lado_confronto("bot1@x", bots)
    assert a["nome"] == "Rafa_Trader" and a["trofeus"] == 230 and a["divisao"]["nome"] == "Prata" and a["avatar_img"]
    assert a == API._lado_confronto("bot1@x", bots)                                  # estável: o avatar não muda a cada consulta
    assert "bot" not in str(a).lower() and "nivel" not in a                          # nada que denuncie que é bot
