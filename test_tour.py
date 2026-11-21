"""Tour guiado do primeiro acesso (tour.py) e as rotas /tour."""
import tour as TO
from test_api import cli  # noqa: F401  (mesma conta de teste)


def test_regras_do_tour():
    d = TO.sanear(None)
    assert TO.ativo(d) and d["passo"] == 0
    d, g = TO.avancar(d, 3, "analisar")
    assert g == TO.PREMIOS["analisar"] and d["passo"] == 3 and d["marcos"] == ["analisar"]
    d, g = TO.avancar(d, 4, "analisar")
    assert g == 0                                                    # prêmio de cada marco é pago uma vez
    d, g = TO.avancar(d, 9, "fim")
    assert g == 50 and d["feito"] and not TO.ativo(d)
    d = TO.reiniciar(d)
    assert TO.ativo(d) and d["passo"] == 0 and "fim" in d["marcos"]  # rever o tour não paga de novo
    _, g = TO.avancar(d, 9, "fim")
    assert g == 0
    assert not TO.ativo(TO.pular(TO.sanear({})))
    assert TO.sanear({"passo": "x", "marcos": ["hack", "jogar"]})["marcos"] == ["jogar"]


def test_rotas_do_tour(cli):
    t = cli.get("/tour").json()
    assert t["ativo"] and t["passo"] == 0 and t["premios"]["fim"] == 50
    r = cli.post("/tour", json={"passo": 2}).json()
    assert r["passo"] == 2 and r["tc"] == 0
    assert cli.post("/tour", json={"marco": "trapaca"}).status_code == 400
    assert cli.post("/tour", json={"marco": "comprar"}).status_code == 409     # sem compra na carteira, o marco não vale
    r = cli.post("/tour", json={"passo": 5, "marco": "analisar"}).json()
    assert r["marcos"] == ["analisar"] and r["passo"] == 5
    r = cli.post("/tour", json={"passo": 30, "marco": "fim"}).json()
    assert r["feito"] and not r["ativo"]
    r = cli.post("/tour", json={"reiniciar": True}).json()
    assert r["ativo"] and r["passo"] == 0
    r = cli.post("/tour", json={"pular": True}).json()
    assert not r["ativo"] and r["pulado"]
