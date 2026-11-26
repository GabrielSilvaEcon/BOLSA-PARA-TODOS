"""Troféus, divisões e temporadas (trofeus.py) e a central de rankings (/trofeus e /ranking/*/tela)."""
import trofeus as TF
from test_social_api import dois  # noqa: F401  (duas contas)


def test_delta_elo():
    assert TF.delta(0, 0, 1) == 20 and TF.delta(0, 0, 0) == -20 and TF.delta(0, 0, 0.5) == 0
    assert TF.delta(500, 1000, 1) > 30                     # vencer quem é bem mais forte vale mais
    assert TF.delta(1000, 500, 1) == TF.MIN_GANHO          # vencer quem é bem mais fraco vale o mínimo
    assert TF.placar_por_posicao(1, 4) == 1 and TF.placar_por_posicao(4, 4) == 0


def test_divisoes_e_registro_sem_repetir():
    assert TF.divisao(0)["nome"] == "Bronze" and TF.divisao(750)["nome"] == "Ouro" and TF.divisao(1000)["nome"] == "Platina" and TF.divisao(9999)["prox"] is None
    d = TF.vazio("2026-11")
    d, x = TF.registrar(d, "ticker", "p1", 0, 1)
    assert x == 20 and d["ticker"]["t"] == 20
    d, x = TF.registrar(d, "ticker", "p1", 0, 1)
    assert x is None and d["ticker"]["t"] == 20
    d, x = TF.registrar(d, "ticker", "p2", 0, 0)
    assert d["ticker"]["t"] == 0 and d["ticker"]["max"] == 20          # nunca abaixo de zero; o máximo da temporada fica


def test_virada_de_temporada():
    d = {"temp": "2026-10", "trade": {"t": 1500, "max": 1900}, "ticker": {"t": 100, "max": 300}, "ids": [], "premios": {}}
    n, fim = TF.sanear(d, "2026-11")
    assert n["temp"] == "2026-11" and n["trade"]["t"] == 500 + 500 and n["ticker"]["t"] == 100
    assert fim["premio"] == 80 and fim["jogos"]["trade"]["divisao"] == "Platina"
    assert TF.sanear(n, "2026-11")[1] is None


def test_partida_online_da_trofeus_e_ranking(dois):
    ana, bia = dois
    ana.post("/social/pedir", json={"usuario": "bia_h"})
    h_ana = bia.get("/social").json()["recebidos"][0]["h"]
    bia.post("/social/responder", json={"h": h_ana, "aceitar": True})
    h_bia = ana.get("/social").json()["amigos"][0]["h"]
    pid = ana.post("/social/desafiar", json={"h": h_bia, "jogo": "ticker"}).json()["id"]
    bia.post("/social/convite/entrar", json={"h": h_ana})
    assert bia.post(f"/ticker/online/{pid}/sair").status_code == 200      # bia desiste: vitória da ana
    v = ana.get(f"/ticker/online/{pid}").json()
    assert v["encerrada"] and v["trofeus"]["delta"] > 0
    bia.get(f"/ticker/online/{pid}")
    t = ana.get("/trofeus").json()
    assert t["jogos"]["ticker"]["t"] > 0 and t["jogos"]["ticker"]["divisao"]["nome"] == "Bronze" and len(t["divisoes"]) == 6
    rk = ana.get("/ranking/ticker/tela").json()
    assert any(l["eu"] and l["valor"] > 0 for l in rk["linhas"]) and rk["unidade"] == "troféus"
    assert [x["nome"] for x in ana.get("/ranking/ticker/tela", params={"filtro": "amigos"}).json()["linhas"]] == ["ANA_H", "BIA_H"]
    assert bia.get("/trofeus").json()["jogos"]["ticker"]["t"] == 0
    c = ana.get("/ranking/carteira/tela", params={"periodo": "mes"})
    assert c.status_code == 200 and c.json()["jogo"] == "carteira"
