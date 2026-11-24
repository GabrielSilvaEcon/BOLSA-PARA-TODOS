"""Histórico de partidas (historico_jogos.py) e as rotas /jogos/historico e /missoes."""
import historico_jogos as HJ
from test_api import cli  # noqa: F401  (mesma conta de teste)


def test_anotar_trade_sem_duplicar():
    d, m = HJ.anotar_trade({}, "p1", "2026-11-20 10:00", 1, 12.34, None, "corrida", 150.0, 1.5, 70)
    assert m and d["itens"][0]["modo"] == "solo" and d["itens"][0]["pos"] is None and d["itens"][0]["pontos"] == 12.3
    d, m = HJ.anotar_trade(d, "p1", "2026-11-20 10:05", 1, 5)
    assert not m and len(d["itens"]) == 1
    d, _ = HJ.anotar_trade(d, "p2", "2026-11-20 11:00", 3, -4, 1)
    assert d["itens"][0]["id"] == "p2" and d["itens"][0]["modo"] == "online"


def test_montar_junta_os_dois_jogos():
    trade = {"itens": [{"id": "p2", "em": "2026-11-20 11:00", "modo": "online", "n": 3, "pos": 1, "pontos": 8.0},
                       {"id": "p1", "em": "2026-11-20 10:00", "modo": "solo", "n": 1, "pos": None, "pontos": 3.0}]}
    placar = {"trade": {"hist": [{"id": "velho", "em": "2026-11-01 09:00", "pts": 5.0, "pos": 2, "n": 2}]},
              "ticker": {"hist": [{"id": "on1", "em": "2026-11-19 20:00", "r": "v", "modo": "online"}]}}
    tk = [{"id": "s1", "ts": "2026-11-20T12:00:00", "modo": "solo", "final": "derrota", "placar": {"jogador": 1, "adversario": 2},
           "rodadas": [{"jog": "PETR4", "adv": "VALE3", "nome_jog": "Petrobras", "nome_adv": "Vale", "ind": "roe", "venc": "adversario"}]}]
    r = HJ.montar(trade, placar, tk)
    assert [h["id"] for h in r["trade"]] == ["p2", "p1", "velho"]
    assert r["trade"][0]["resultado"] == "vitoria" and r["trade"][1]["resultado"] is None and r["trade"][2]["resultado"] == "derrota"
    assert [h["id"] for h in r["ticker"]] == ["s1", "on1"] and r["ticker"][1]["resultado"] == "vitoria"
    assert r["ticker"][0]["rodadas"][0]["jog"] == "Petrobras"
    assert r["resumo"]["trade"]["total"] == 3 and r["resumo"]["trade"]["melhor"] == 8.0 and r["resumo"]["ticker"]["vitoria"] == 1


def test_rotas(cli):
    h = cli.get("/jogos/historico")
    assert h.status_code == 200 and {"trade", "ticker", "resumo"} <= set(h.json())
    m = cli.get("/missoes").json()
    assert len(m["estudo"]["dia"]) == 3 and m["estudo"]["semana"]["alvo"] > 0
    assert {x["periodo"] for x in m["carteira"]} <= {"dia", "semana", "especial"}


def test_eventos_e_glossario(cli):
    e = cli.get("/eventos")
    assert e.status_code == 200 and {"campanhas", "bau", "passe", "desafio", "recompensas"} <= set(e.json())
    assert e.json()["passe"]["total"] > 0
    g = cli.get("/ajuda/glossario").json()["termos"]
    assert len(g) > 20 and all(t["oque"] for t in g)


def test_carteira_historico_e_conquistas(cli):
    h = cli.get("/carteira/historico")
    assert h.status_code == 200 and {"itens", "resumo"} <= set(h.json())
    c = cli.get("/carteira/conquistas")
    assert c.status_code == 200 and "total" in c.json()
