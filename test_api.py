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


def test_login_pelo_supabase_auth_cria_a_conta_do_jogo(monkeypatch):
    import banco
    from test_trader_mesa import banco_isolado
    jwt = "aaa.bbb.ccc"
    usuarios = {jwt: {"email": "nova@x.com", "email_confirmed_at": "2026-11-19T10:00:00Z", "user_metadata": {"full_name": "Nova Jogadora"}},
                "ddd.eee.fff": {"email": "sem@x.com"}}                                  # e-mail ainda não confirmado
    monkeypatch.setattr(API, "_usuario_supabase", lambda t: usuarios.get(t))
    API._CACHE_AUTH.clear()
    with banco_isolado():
        c = TestClient(API.app)
        r = c.get("/eu", headers={"Authorization": f"Bearer {jwt}"})
        assert r.status_code == 200 and r.json()["conta"]["email"] == "nova@x.com"
        assert banco.sis_conta_por_email("nova@x.com")["nome"] == "Nova Jogadora"      # a conta do jogo nasceu no 1º acesso
        assert c.get("/eu", headers={"Authorization": "Bearer ddd.eee.fff"}).status_code == 401
        assert c.get("/eu", headers={"Authorization": "Bearer xxx.yyy.zzz"}).status_code == 401   # token que o Supabase não reconhece


def test_eu_traz_nivel_moedas_e_passe(cli):
    r = cli.get("/eu").json()
    assert {"xp", "nivel", "moedas", "passe"} <= set(r)                       # chaves sempre presentes (valores podem ser zero/vazios)
    assert r["moedas"] is None or r["moedas"] >= 0
    if r["nivel"]:
        assert r["nivel"]["nivel"] >= 1


def test_eu_traz_a_posicao_no_ranking(cli):
    r = cli.get("/eu").json()
    assert {"pos", "total", "rotulo", "participa"} <= set(r["ranking"])      # chaves sempre presentes (sem competição: vazias)


def test_carteira_traz_caixa_patrimonio_e_posicoes(cli):
    r = cli.get("/carteira")
    assert r.status_code == 200, r.text
    assert {"disponivel", "investido", "valor_atual", "patrimonio", "posicoes"} <= set(r.json())
    assert isinstance(r.json()["posicoes"], list)
    assert r.json()["patrimonio"] >= r.json()["disponivel"]


def test_comecar_e_comprar_pela_api(cli, monkeypatch):
    import cotacoes_jogo as CJ
    monkeypatch.setattr(CJ, "preco_agora", lambda tk, **k: 10.0)
    r = cli.get("/carteira").json()
    assert r["comecou"] is False
    assert cli.post("/carteira/ordem", json={"ativo": "PETR4", "qtd": 10, "lado": "C"}).status_code == 400   # antes de começar
    assert cli.post("/carteira/comecar", json={"apelido": "ana_teste", "aceito": False}).status_code == 400   # sem confirmar
    assert cli.post("/carteira/comecar", json={"apelido": "ana_teste", "aceito": True}).status_code == 200
    r = cli.post("/carteira/ordem", json={"ativo": "PETR4", "qtd": 10, "lado": "C"})
    assert r.status_code == 200, r.text
    cart = cli.get("/carteira").json()
    assert cart["comecou"] is True
    assert any(p["id"] == "PETR4" and p["qtd"] == 10 for p in cart["posicoes"])
    assert cli.get("/carteira/preco", params={"ativo": "PETR4"}).json()["px"] == 10.0


def test_alertas_lista_e_marca_lidas(cli):
    import banco
    assert "alertas" in cli.get("/eu").json()
    r = cli.get("/alertas")
    assert r.status_code == 200, r.text
    assert isinstance(r.json()["itens"], list)
    r = cli.post("/alertas/lidas", json={"ids": []})
    assert r.status_code == 200 and r.json()["marcados"] == 0


def test_central_de_jogos(cli):
    r = cli.get("/jogos/central")
    assert r.status_code == 200, r.text
    d = r.json()
    assert {"vitorias", "partidas", "melhor", "ofensiva", "desafio"} <= set(d)
    assert d["vitorias"] >= 0 and d["partidas"] >= 0


def test_tela_inicial_do_trade_battle(cli):
    r = cli.get("/trade/central")
    assert r.status_code == 200, r.text
    d = r.json()
    assert [c["id"] for c in d["corridas"]] == list(TB.CORRIDAS)
    assert all(c["minutos"] > 0 and c["grafico"] for c in d["corridas"])
