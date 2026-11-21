"""Torneio de fim de semana, ranking semanal entre amigos (coroa), confronto direto (rival) e revanche."""
from datetime import date, datetime, timedelta, timezone

import trofeus as TF
from test_social_api import dois  # noqa: F401  (duas contas)

BRT = timezone(timedelta(hours=-3))


def test_regras_puras():
    assert TF.torneio_id(date(2026, 11, 21)) == "2026-11-20" and TF.torneio_id(date(2026, 11, 23)) is None   # sábado / segunda
    assert TF.semana_id(date(2026, 11, 23)) == "2026-W48"
    d = TF.vazio("2026-11")
    TF.anotar_semana(d, "2026-W47", 20)
    TF.anotar_semana(d, "2026-W48", -8)
    assert d["sem"] == {"id": "2026-W48", "pts": -8} and d["sem_ant"] == {"id": "2026-W47", "pts": 20}
    TF.anotar_torneio(d, "2026-11-20", 30)                       # sem inscrição: não conta
    TF.inscrever(d, "2026-11-20")
    for x in (30, -20, 10, 5, 25, 8, 40):
        TF.anotar_torneio(d, "2026-11-20", x)
    assert TF.pontos_torneio(d["trn"]) == 40 + 30 + 25 + 10 + 8          # as 5 melhores, perder não tira
    for p in (1, 1, 0):
        TF.anotar_h2h(d, "bia", p)
    assert d["h2h"]["bia"] == {"v": 2, "e": 0, "d": 1} and TF.rival(d) == "bia" and TF.rival(d, {"outro"}) is None
    assert TF.sanear(d, "2026-11")[0]["h2h"]["bia"]["v"] == 2            # os campos novos sobrevivem ao sanear


def _amigos(ana, bia):
    ana.post("/social/pedir", json={"usuario": "bia_h"})
    h_ana = bia.get("/social").json()["recebidos"][0]["h"]
    bia.post("/social/responder", json={"h": h_ana, "aceitar": True})
    return ana.get("/social").json()["amigos"][0]["h"], h_ana


def _duelo(ana, bia, h_bia, h_ana, revanche=False):
    rota = "/social/revanche?jogo=ticker" if revanche else "/social/desafiar"
    pid = ana.post(rota, json={"h": h_bia, "jogo": "ticker"}).json()["id"]
    bia.post("/social/convite/entrar", json={"h": h_ana})
    bia.post(f"/ticker/online/{pid}/sair")                     # bia desiste: vitória da ana
    v = ana.get(f"/ticker/online/{pid}").json()
    bia.get(f"/ticker/online/{pid}")
    ana.post("/social/desafio/cancelar", json={"h": h_bia})
    return v


def test_torneio_semana_rival_e_revanche(dois, monkeypatch):
    import api.main as API
    ana, bia = dois
    agora = {"t": datetime(2026, 11, 21, 15, 0, tzinfo=BRT)}           # sábado
    monkeypatch.setattr(API, "_agora_brt", lambda: agora["t"])
    h_bia, h_ana = _amigos(ana, bia)
    assert ana.get("/torneio").json()["aberto"] and ana.post("/torneio/inscrever").status_code == 200
    v = _duelo(ana, bia, h_bia, h_ana)
    assert v["trofeus"]["revanche"]["h"] == h_bia and v["trofeus"]["revanche"]["amigo"]
    _duelo(ana, bia, h_bia, h_ana, revanche=True)
    _duelo(ana, bia, h_bia, h_ana)
    t = ana.get("/torneio").json()
    assert t["inscrito"] and t["pontos"] > 0 and t["partidas"] == 3 and t["eu"]["pos"] == 1
    assert ana.get("/ranking/torneio/tela").json()["linhas"][0]["eu"]
    s = ana.get("/ranking/semana/tela").json()
    assert s["linhas"][0]["eu"] and s["linhas"][0]["valor"] > 0 and len(s["linhas"]) == 2
    am = ana.get("/social").json()["amigos"][0]
    assert am["h2h"] == {"v": 3, "e": 0, "d": 0} and am["rival"]
    agora["t"] = datetime(2026, 11, 23, 10, 0, tzinfo=BRT)             # segunda: torneio fechado, prêmio do 1º lugar
    t = ana.get("/torneio").json()
    assert not t["aberto"] and t["premio_anterior"]["pos"] == 1 and t["premio_anterior"]["tc"] == 100
    assert ana.post("/torneio/inscrever").status_code == 400
    assert ana.get("/social").json()["eu"]["coroa"]                    # 1º da semana passada entre os amigos
