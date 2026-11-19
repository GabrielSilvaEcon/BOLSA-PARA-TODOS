"""Servidor do jogo (api/main.py): o app novo usa o MESMO motor, banco e contas do Streamlit."""
import pytest
from fastapi.testclient import TestClient

import api.main as API
import trader_battle as TB
import trader_dados as TD

EU = "ana@x.com"


@pytest.fixture
def cli(monkeypatch):
    import banco
    import contas
    from test_trader_mesa import banco_isolado, livro
    from test_perfil_foto import _contas
    monkeypatch.setattr(TD, "escolher_corrida", lambda f, s, banco=None, permitir_demo=False: TD.demo_corrida(f, s))
    with banco_isolado(), livro(pat=300_000.0, caixa=200_000.0):
        _contas(banco, EU)
        banco.sis_atualizar_conta("id-" + EU, {"status": "ativa"})
        tok = contas.criar_sessao("id-" + EU)
        c = TestClient(API.app)
        c.headers["Authorization"] = f"Bearer {tok}"
        yield c


def test_sem_token_nao_entra():
    r = TestClient(API.app).get("/eu")
    assert r.status_code == 401


def test_eu_com_o_mesmo_token_do_streamlit(cli):
    r = cli.get("/eu")
    assert r.status_code == 200 and r.json()["conta"]["email"] == EU


def test_partida_solo_inteira_pela_api(cli, monkeypatch):
    t = {"agora": 1_000_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    r = cli.post("/trade/solo", json={"corrida": "rapida"})
    assert r.status_code == 200, r.text
    pid = r.json()["id"]
    assert r.json()["fase"] == "analise" and r.json()["tela"]["corrida"]
    r = cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"})
    assert r.json()["fase"] == "replay"                                    # solo: confirmar já começa
    t["agora"] += 5
    r = cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "a1", "tipo": "mercado", "direcao": "alta", "q": 50}})
    assert r.status_code == 200, r.text
    t["agora"] += 10
    pos = cli.get(f"/trade/solo/{pid}").json()["tela"]["mesa"]["posicao"]
    assert pos["direcao"] == "alta" and pos["q"] == 50                     # a ordem executou no próximo preço real
    t["agora"] += TB.CORRIDAS["rapida"]["n_replay"] * TB.SEG_POR_CANDLE + 5
    fim = cli.get(f"/trade/solo/{pid}").json()
    assert fim["fase"] == "fim" and fim["fim"]["revelado"]["ticker"] and fim["fim"]["resultado"]["fin"]["n_ops"] == 1


def test_ordem_invalida_volta_como_erro_claro(cli):
    pid = cli.post("/trade/solo", json={"corrida": "rapida"}).json()["id"]
    r = cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "x", "tipo": "mercado", "direcao": "alta", "q": 5}})
    assert r.status_code == 400 and "replay" in r.json()["detail"]          # ainda na estratégia: não dá para operar


def test_ranking_pela_api(cli):
    r = cli.get("/ranking/trade", params={"metrica": "lucro"})
    assert r.status_code == 200 and "linhas" in r.json()
    assert cli.get("/ranking/xadrez").status_code == 404
