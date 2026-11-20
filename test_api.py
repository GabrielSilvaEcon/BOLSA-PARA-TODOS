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


def test_relatorio_da_partida_solo(cli, monkeypatch):
    t = {"agora": 2_000_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    pid = cli.post("/trade/solo", json={"corrida": "rapida"}).json()["id"]
    assert cli.get(f"/trade/solo/{pid}/relatorio").status_code == 400            # ainda não terminou
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"})
    t["agora"] += 5
    cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "a1", "tipo": "mercado", "direcao": "alta", "q": 50}})
    t["agora"] += TB.CORRIDAS["rapida"]["n_replay"] * TB.SEG_POR_CANDLE + 20
    assert cli.get(f"/trade/solo/{pid}").json()["fase"] == "fim"
    r = cli.get(f"/trade/solo/{pid}/relatorio")
    assert r.status_code == 200, r.text
    h = r.json()["html"]
    assert "Resumo" in h and "Operações" in h and "Raio-X" in h and "section role='dialog'" in h


def test_partida_solo_paga_xp_uma_vez(cli, monkeypatch):
    t = {"agora": 3_000_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    xp0 = cli.get("/eu").json()["xp"] or 0
    pid = cli.post("/trade/solo", json={"corrida": "rapida"}).json()["id"]
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"})
    t["agora"] += 5
    cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "a1", "tipo": "mercado", "direcao": "alta", "q": 50}})
    t["agora"] += TB.CORRIDAS["rapida"]["n_replay"] * TB.SEG_POR_CANDLE + 20
    xp = cli.get(f"/trade/solo/{pid}").json()["fim"]["xp"]
    assert xp["status"] == "pago" and xp["xp"] > 0
    cli.get(f"/trade/solo/{pid}")                                            # consultar de novo não paga outra vez
    assert (cli.get("/eu").json()["xp"] or 0) == xp0 + xp["xp"]


def test_tela_do_ranking(cli):
    r = cli.get("/ranking/trade/tela")
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["nome"] == "Trade Battle" and isinstance(d["linhas"], list) and "total" in d
    assert all("email" not in x for x in d["linhas"])                       # nunca manda e-mail
    assert cli.get("/ranking/ticker/tela").status_code == 200
    assert cli.get("/ranking/xadrez/tela").status_code == 404


def test_sala_com_dois_jogadores_do_comeco_ao_fim(cli, monkeypatch):
    import banco
    import contas
    from test_perfil_foto import _contas
    t = {"agora": 4_000_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    _contas(banco, "bia@x.com")
    banco.sis_atualizar_conta("id-bia@x.com", {"status": "ativa"})
    bia = TestClient(API.app)
    bia.headers["Authorization"] = f"Bearer {contas.criar_sessao('id-bia@x.com')}"
    sala = cli.post("/trade/salas", json={"corrida": "rapida"})
    assert sala.status_code == 200, sala.text
    pid = sala.json()["id"]
    espera = cli.get(f"/trade/salas/{pid}").json()
    assert espera["estado"] == "sala" and espera["sala"]["criador"] and espera["sala"]["n"] == 1
    assert bia.post("/trade/salas/entrar", json={"codigo": espera["sala"]["codigo"]}).status_code == 200
    assert bia.post(f"/trade/salas/{pid}/iniciar").status_code == 400                # só o criador inicia
    r = cli.post(f"/trade/salas/{pid}/iniciar")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "jogo" and r.json()["tela"]["multi"] is True
    for c in (cli, bia):
        assert c.post(f"/trade/salas/{pid}/estrategia", json={"direcao": "alta"}).status_code == 200
    t["agora"] += 10
    r = cli.post(f"/trade/salas/{pid}/acao", json={"dados": {"aid": "s1", "tipo": "mercado", "direcao": "alta", "q": 50}})
    assert r.status_code == 200, r.text
    t["agora"] += TB.CORRIDAS["rapida"]["n_replay"] * TB.SEG_POR_CANDLE + 60
    fim = cli.get(f"/trade/salas/{pid}").json()
    assert fim["fase"] == "fim" and fim["fim"]["xp"]["status"] in ("pago", "zero", "limite")
    rel = cli.get(f"/trade/salas/{pid}/relatorio")
    assert rel.status_code == 200 and "Raio-X" in rel.json()["html"]


def test_loja_mostra_saldo_itens_e_extrato(cli):
    r = cli.get("/loja")
    assert r.status_code == 200, r.text
    d = r.json()
    assert {"saldo", "bau", "baus", "itens", "compras", "totais", "historico", "beneficios"} <= set(d)
    for it in d["itens"]:
        assert {"id", "nome", "preco", "raridade", "status", "previa"} <= set(it)
    sem_saldo = next((it for it in d["itens"] if it["preco"] > d["saldo"] and not it["status"]["tem"]), None)
    if sem_saldo:
        assert cli.post("/loja/comprar", json={"pid": sem_saldo["id"], "req": "t1"}).status_code == 400


def test_loja_so_tem_tema_e_moldura(cli):
    d = cli.get("/loja").json()
    assert d["itens"] and {it["kind"] for it in d["itens"]} <= {"tema", "moldura"}
    import tickercoins as TC
    outro = next(p for p in TC.produtos() if p["efeito"]["kind"] not in ("tema", "moldura"))
    assert cli.post("/loja/comprar", json={"pid": outro["id"], "req": "z"}).status_code == 400


def test_loja_bau_compra_e_usa(cli):
    import tickercoins as TC
    assert cli.post("/loja/bau").json()["valor"] > 0                       # baú diário credita
    assert cli.post("/loja/bau").json().get("novo") is False                # só um por dia: abrir de novo não credita outra vez
    TC.creditar("id-" + EU, 500, "teste", "Moedas de teste", "teste:500")
    d = cli.get("/loja").json()
    item = next(it for it in d["itens"] if not it["status"]["tem"] and it["preco"] <= d["saldo"])
    r = cli.post("/loja/comprar", json={"pid": item["id"], "req": "pedido-1"})
    assert r.status_code == 200, r.text
    assert cli.post("/loja/comprar", json={"pid": item["id"], "req": "pedido-1"}).json().get("duplicada")   # mesmo pedido não cobra de novo
    d2 = cli.get("/loja").json()
    assert d2["saldo"] == d["saldo"] - item["preco"]
    assert any(c["nome"] == item["nome"] for c in d2["compras"])
    eqp = next((it for it in d2["itens"] if it["status"]["tem"] and it["equipavel"]), None)
    if eqp:
        assert cli.post("/loja/equipar", json={"pid": eqp["id"], "tipo": eqp["kind"]}).status_code == 200
        assert next(it for it in cli.get("/loja").json()["itens"] if it["id"] == eqp["id"])["em_uso"]


def test_estrategia_guarda_os_desenhos(cli):
    pid = cli.post("/trade/solo", json={"corrida": "rapida"}).json()["id"]
    marcas = {"niveis": [{"preco": 25.4, "rotulo": "Suporte", "papel": "suporte"}, {"preco": 27.0, "papel": "inventado"}],
              "tendencias": [{"i1": 10, "p1": 25.0, "i2": 40, "p2": 26.0}],
              "zonas": [{"i1": 50, "i2": 30, "p1": 26.2, "p2": 25.8, "reacao": "alta"}, {"i1": 1, "i2": 2, "p1": 1, "p2": 2, "reacao": "?"}],
              "notas": [{"i": 5, "preco": 25.5, "texto": "fundo duplo"}]}
    r = cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta", "marcas": marcas})
    assert r.status_code == 200, r.text
    m = r.json()["tela"]["inicial"]["marcas"]
    assert m["niveis"][0]["papel"] == "suporte" and "papel" not in m["niveis"][1]          # papel desconhecido é descartado
    assert m["zonas"] == [{"i1": 30, "i2": 50, "p1": 25.8, "p2": 26.2, "reacao": "alta"}]   # zona inválida é descartada
    assert m["tendencias"] and m["notas"][0]["texto"] == "fundo duplo"


def test_desenhos_sao_avaliados_no_fim(cli, monkeypatch):
    t = {"agora": 1_000_000.0}
    monkeypatch.setattr(API, "_agora", lambda: t["agora"])
    r = cli.post("/trade/solo", json={"corrida": "rapida"}).json()
    pid, ref = r["id"], r["tela"]["candles"][-1]["c"]
    marcas = {"niveis": [{"preco": round(ref * 1.001, 2), "papel": "alvo"}, {"preco": round(ref * 0.5, 2), "papel": "suporte"}]}
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta", "marcas": marcas})
    t["agora"] += 5
    cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "a1", "tipo": "mercado", "direcao": "alta", "q": 50}})
    t["agora"] += TB.CORRIDAS["rapida"]["n_replay"] * TB.SEG_POR_CANDLE + 5
    fim = cli.get(f"/trade/solo/{pid}").json()
    lt = fim["fim"]["resultado"]["leitura"]
    assert [x["papel"] for x in lt["itens"]] == ["alvo", "suporte"]
    assert lt["itens"][1]["ok"] is None                                    # suporte muito longe: o preço não chegou, não conta
    assert lt["avaliados"] == 1 and lt["nota"] in (0.0, 100.0)
    html = cli.get(f"/trade/solo/{pid}/relatorio").json()["html"]
    assert "Seus desenhos" in html
