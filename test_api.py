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
    hist = cli.get("/jogos/historico").json()["trade"]                      # a partida solo aparece no histórico pessoal
    assert len(hist) == 1 and hist[0]["modo"] == "solo"


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
    pid, velas = r["id"], r["tela"]["candles"]
    ref = velas[-1]["c"]
    amplitude = sum(c["h"] - c["l"] for c in velas[-14:]) / len(velas[-14:])   # ~ATR: o alvo precisa ficar a mais de 2 ATR para contar como previsão
    marcas = {"niveis": [{"preco": round(ref + 5 * amplitude, 2), "papel": "alvo"}, {"preco": round(ref * 0.5, 2), "papel": "suporte"}]}
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta", "marcas": marcas})
    t["agora"] += 5
    cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "a1", "tipo": "mercado", "direcao": "alta", "q": 50}})
    t["agora"] += TB.CORRIDAS["rapida"]["n_replay"] * TB.SEG_POR_CANDLE + 5
    fim = cli.get(f"/trade/solo/{pid}").json()
    lt = fim["fim"]["resultado"]["leitura"]
    assert [x["papel"] for x in lt["itens"]] == ["alvo", "suporte"]
    assert lt["itens"][1]["ok"] is None                                    # suporte muito longe: o preço não chegou, não conta
    assert lt["avaliados"] == 1 and lt["nota"] in (0.0, 100.0)
    datas = fim["fim"]["revelado"]["datas"]
    assert len(datas) == len(fim["tela"]["candles"]) and "/" in datas[0]                # datas reais, uma por candle do gráfico (só no fim)
    html = cli.get(f"/trade/solo/{pid}/relatorio").json()["html"]
    assert "Seus desenhos" in html


def _cartas_teste():
    import banco
    """Cartas de teste (todas as ações do universo, dados de hoje) no snapshot do banco isolado: nenhuma rede."""
    import random as R
    from datetime import datetime, timedelta, timezone
    import battle_dados as BD
    hoje = datetime.now(timezone(timedelta(hours=-3)))
    rnd = R.Random(7)
    cartas = {}
    for b in BD.universo():
        ind = {"dy_12m": rnd.uniform(0.01, 0.12), "ret_12m": rnd.uniform(-0.3, 0.6), "vol": rnd.uniform(0.15, 0.6), "queda_max": rnd.uniform(0.05, 0.5),
               "roe": rnd.uniform(0.02, 0.35), "margem_liq": rnd.uniform(0.02, 0.3), "pl": rnd.uniform(3, 25), "pvp": rnd.uniform(0.5, 4), "div_pl": rnd.uniform(0.1, 2)}
        cartas[b["tk"]] = {**{k: b[k] for k in ("tk", "nome", "classe", "moeda")}, "ind": ind, "ref": hoje.date().isoformat(),
                           "gerado": hoje.replace(tzinfo=None).isoformat(timespec="seconds"), "fonte": "teste", "avisos": []}
    banco.cfg_gravar(BD.CH_SNAPSHOT, {"v": 1, "cartas": cartas})
    return cartas


def test_ticker_battle_duelo_inteiro(cli):
    _cartas_teste()
    t = cli.post("/ticker/tutorial/bau").json()
    import battle as BT
    assert not t["ja"] and len(t["cartas"]) == BT.BARALHO_MAX               # o Baú entrega o baralho inteiro: uma carta por rodada
    for it in t["cartas"]:                                                  # equipa as cartas recebidas (simula passo da Coleção)
        cli.post("/cartas/equipar", json={"tk": it["tk"]})
    c = cli.get("/ticker/central").json()
    assert len(c["cartas"]) >= 10 and len(c["deck"]) >= 1 and c["valido"]   # baralho formado pelas cartas equipadas
    assert c["cartas"][0]["ind"] and c["cartas"][0]["ind"][0]["txt"]
    assert all(len(k["ind"]) <= 3 for k in c["cartas"]) and set(c["indicadores"]) == {"dy_12m", "roe", "pl"}
    assert all("-" in t for t in c["deck"]) and [e["tk"] for e in c["equipadas"]] == c["deck"]
    r = cli.post("/ticker/baralho", json={"deck": ["PETR4", "VALE3", "ITUB4"]}).json()
    assert r["deck"] == c["deck"]                                           # o baralho vem da Coleção, não do pedido
    d = cli.post("/ticker/duelo").json()
    did = d["id"]
    assert d["rodada"] == 1 and len(d["mao"]) == BT.BARALHO_MAX and d["final"] is None   # a mão começa com o baralho inteiro
    for n in range(1, BT.RODADAS + 1):                                          # uma rodada por carta do baralho
        carta = next(m["tk"] for m in d["mao"] if not m["sem_adv"])
        adv = cli.get(f"/ticker/duelo/{did}/adversaria", params={"carta": carta}).json()
        assert adv["adversaria"]["tk"] != carta and "ind" not in adv["adversaria"]     # os valores do sistema ficam escondidos
        assert set(adv["disputaveis"]) <= {"dy_12m", "roe", "pl"} and adv["adversaria"]["ticker"] != carta.split("-")[0]
        assert cli.post(f"/ticker/duelo/{did}/rodada", json={"carta": carta, "ind": "vol"}).status_code == 400   # fora dos 3
        d = cli.post(f"/ticker/duelo/{did}/rodada", json={"carta": carta, "ind": adv["disputaveis"][0]}).json()
        assert len(d["rodadas"]) == n and d["rodadas"][-1]["raio_x"]["porque"]
    assert d["final"] in ("vitoria", "derrota", "empate") and sum(d["placar"].values()) == BT.RODADAS
    assert cli.post(f"/ticker/duelo/{did}/rodada", json={"carta": carta, "ind": "roe"}).status_code == 400      # acabou
    h = cli.get("/ticker/central").json()["historico"]
    assert h["ultimos"][0]["id"] == did and h[d["final"]] == 1              # entrou no histórico uma vez


def test_ticker_online_sala_duas_pessoas(cli):
    import banco
    import contas
    from test_perfil_foto import _contas
    _cartas_teste()
    _contas(banco, "bia@x.com")
    banco.sis_atualizar_conta("id-bia@x.com", {"status": "ativa"})
    bia = TestClient(API.app)
    bia.headers["Authorization"] = f"Bearer {contas.criar_sessao('id-bia@x.com')}"
    for c in (cli, bia):
        t = c.post("/ticker/tutorial/bau").json()
        for it in t["cartas"]:
            c.post("/cartas/equipar", json={"tk": it["tk"]})
        assert c.get("/ticker/central").json()["valido"]
    sala = cli.post("/ticker/online/sala").json()
    assert len(sala["codigo"]) == 6
    assert bia.post("/ticker/online/sala/entrar", json={"codigo": sala["codigo"].lower()}).json()["id"] == sala["id"]
    pid = sala["id"]
    assert cli.get(f"/ticker/online/{pid}").json()["fase"] == "pronta"
    cli.post(f"/ticker/online/{pid}/pronto")
    v = bia.post(f"/ticker/online/{pid}/pronto").json()
    assert v["fase"] == "em_jogo" and v["op"]["nick"]
    import battle as BT
    for n in range(BT.RODADAS):                                                   # uma rodada por carta do baralho
        ea = cli.get(f"/ticker/online/{pid}").json()
        eb = bia.get(f"/ticker/online/{pid}").json()
        ta = next(t for t in ea["eu"]["deck"] if t not in ea["eu"]["usadas"])
        tb = next(t for t in eb["eu"]["deck"] if t not in eb["eu"]["usadas"])
        assert cli.post(f"/ticker/online/{pid}/jogar", json={"carta": ta, "ind": "vol"}).status_code == 400   # fora dos 3
        va = cli.post(f"/ticker/online/{pid}/jogar", json={"carta": ta, "ind": "dy_12m"}).json()
        assert va["eu"]["escolha"] and "escolha" not in (bia.get(f"/ticker/online/{pid}").json()["op"] or {})   # a escolha fica secreta
        vb = bia.post(f"/ticker/online/{pid}/jogar", json={"carta": tb, "ind": "dy_12m"}).json()
        assert len(vb["reg"]) == n + 1 and vb["reg"][-1]["cmp"][0]["txt_a"]
    fa, fb = cli.get(f"/ticker/online/{pid}").json(), bia.get(f"/ticker/online/{pid}").json()
    assert fa["encerrada"] and fa["final"]["resultado"] in ("vitoria", "derrota", "empate")
    oposto = {"vitoria": "derrota", "derrota": "vitoria", "empate": "empate"}
    assert fb["final"]["resultado"] == oposto[fa["final"]["resultado"]]
    import json
    doc = banco.jogos_placar_ler(banco.Ator(id="id-" + EU, email=EU, papel="usuario"))
    assert pid in json.dumps(doc)                                           # o duelo online entrou no placar (ranking)


def test_ticker_online_fila_emparelha(cli):
    import banco
    import contas
    from test_perfil_foto import _contas
    _cartas_teste()
    _contas(banco, "caio@x.com")
    banco.sis_atualizar_conta("id-caio@x.com", {"status": "ativa"})
    caio = TestClient(API.app)
    caio.headers["Authorization"] = f"Bearer {contas.criar_sessao('id-caio@x.com')}"
    for c in (cli, caio):
        t = c.post("/ticker/tutorial/bau").json()
        for it in t["cartas"]:
            c.post("/cartas/equipar", json={"tk": it["tk"]})
    assert cli.post("/ticker/online/fila").json()["estado"] == "fila"
    r = caio.post("/ticker/online/fila").json()
    assert r["estado"] == "partida"
    assert cli.get("/ticker/online/fila").json() == {"estado": "partida", "id": r["id"]}
    assert cli.get("/ticker/online/ativa").json()["id"] == r["id"]
    v = caio.post(f"/ticker/online/{r['id']}/sair").json()                  # sair antes de alguém ficar pronto: cancela
    assert v["encerrada"]


def test_perfil_ver_editar_e_avatar(cli):
    p = cli.get("/perfil").json()
    assert {"nome", "usuario", "avatar_img", "nivel", "estat", "conquistas", "privacidade", "jogos"} <= set(p)
    r = cli.post("/perfil", json={"nome": "Ana Trader", "usuario": "ana_trader", "bio": "Aprendendo a investir."})
    assert r.status_code == 200, r.text
    assert r.json()["usuario"] == "ana_trader" and r.json()["bio"] == "Aprendendo a investir."
    assert cli.post("/perfil", json={"usuario": "outro_nome"}).status_code == 200          # a 1ª troca é livre e marca a data
    assert cli.post("/perfil", json={"usuario": "mais_um"}).status_code == 400             # trocar de novo logo em seguida: só depois de 7 dias
    col = cli.get("/perfil/avatares").json()
    assert col["total"] >= col["liberados"] > 0
    livre = next(a for a in col["itens"] if a["liberado"] and not a["equipado"])
    bloq = next((a for a in col["itens"] if not a["liberado"]), None)
    assert cli.post("/perfil", json={"avatar": livre["id"]}).json()["avatar"] == livre["id"]
    if bloq:
        assert cli.post("/perfil", json={"avatar": bloq["id"]}).status_code == 400       # avatar bloqueado não é equipado
    assert cli.post("/perfil", json={"privacidade": {"visivel": "amigos", "mostrar_bio": False}}).json()["privacidade"]["visivel"] == "amigos"


def _resposta_certa(ex):
    import jornada_conteudo as JC
    e = JC.EX_POR_ID[ex["id"]]
    t = e["tipo"]
    if t in ("escolha", "completar"):
        return e["correta"]
    if t == "vf":
        return e["correta"]
    if t == "ordenar":
        return list(e["itens"])
    return {a: b for a, b in e["pares"]}


def test_aprender_licao_inteira(cli):
    m = cli.get("/aprender").json()
    lic = m["mapa"][0]["licoes"][0]
    assert lic["estado"] == "proxima" and m["resumo"]["xp"] == 0
    assert cli.get(f"/aprender/aula/{lic['aula']}").json()["texto"]
    e = cli.post(f"/aprender/licao/{lic['id']}").json()["exercicio"]
    assert "correta" not in e and "pares" not in e                         # a resposta nunca vai para a tela
    errado = {"escolha": 99, "completar": 99, "vf": "x", "ordenar": [], "pares": {}}[e["tipo"]]
    r = cli.post("/aprender/responder", json={"id": e["id"], "resposta": errado}).json()
    assert r["ok"] is False and r["certa"] and r["exercicio"]                # errou: a pergunta volta para o fim da fila
    assert cli.post("/aprender/responder", json={"id": e["id"], "resposta": errado}).status_code == 409   # já respondida
    while r.get("exercicio"):
        r = cli.post("/aprender/responder", json={"id": r["exercicio"]["id"], "resposta": _resposta_certa(r["exercicio"])}).json()
    f = r["fim"]
    assert f["xp"] == 10 and not f["perfeita"] and f["ofensiva"] == 1        # 10 XP (sem bônus de perfeita), 1º dia de sequência
    m2 = cli.get("/aprender").json()
    assert m2["resumo"]["xp"] == 10 and m2["resumo"]["erros"] == 1 and m2["mapa"][0]["licoes"][0]["estado"] == "concluida"
    rv = cli.post("/aprender/licao/revisao").json()["exercicio"]           # o que errou entra na revisão
    assert rv["id"] == e["id"]


def test_colecao_pacote_inicial_bau_evolucao_e_equipar(cli):
    _cartas_teste()
    # jogadores começam sem cartas; o tutorial entrega as 3 iniciais
    c0 = cli.get("/cartas/colecao").json()
    assert len([x for x in c0["cartas"] if x["possui"]]) == 0
    t = cli.post("/ticker/tutorial/bau").json()
    import battle as BT
    assert not t["ja"] and len(t["cartas"]) == BT.BARALHO_MAX              # o Baú entrega o baralho inteiro
    c = cli.get("/cartas/colecao").json()
    minhas = [x for x in c["cartas"] if x["possui"]]
    assert len(minhas) == BT.BARALHO_MAX and {x["raridade"] for x in minhas} == {"comum", "rara", "epica"}
    assert all(x["equipada"] for x in minhas) and c["descobertas"] == BT.BARALHO_MAX and c["total"] >= 19
    trancada = next(x for x in c["cartas"] if not x["possui"])
    assert "nome" not in trancada and trancada["setor"]                    # silhueta: só raridade e setor
    assert cli.post("/ticker/tutorial/bau").json()["ja"]                   # o baú tutorial sai uma vez só
    r = cli.post("/loja/bau").json()
    assert r["cartas"] and all(k["tk"] and k["raridade"] for k in r["cartas"])
    assert "cartas" not in cli.post("/loja/bau").json()                    # mesmo baú não dá cartas de novo
    c2 = cli.get("/cartas/colecao").json()
    assert sum(x.get("total", 0) for x in c2["cartas"]) == BT.BARALHO_MAX + len(r["cartas"])
    # evolução: dá cópias de uma carta e evolui escolhendo o ROE
    import cartas_dados as CD
    import cartas as C
    doc = CD.ler(EU)
    alvo = next(x["tk"] for x in minhas if x["raridade"] == "epica")
    for _ in range(3):
        C.adicionar(doc, alvo, "epica", "2026-11-24T10:00:00")
    CD.gravar(EU, doc)
    assert cli.post("/cartas/evoluir", json={"tk": alvo, "ind": "vol"}).status_code == 400
    assert cli.post("/cartas/evoluir", json={"tk": "NAOTEM3", "ind": "roe"}).status_code == 400
    e = cli.post("/cartas/evoluir", json={"tk": alvo, "ind": "roe"}).json()
    x = next(k for k in e["cartas"] if k["tk"] == alvo)
    assert e["evolucao"]["nivel"] == 2 and x["nivel"] == 2 and x["escolhas"] == ["roe"] and x["melhorias"]["roe"] == 1
    assert x["real"]["roe"] != x["jogo"]["roe"]                            # dado real separado do atributo de jogo
    # no duelo, a carta equipada entra com o ROE melhorado (o valor real continua guardado)
    d = cli.post("/ticker/duelo").json()
    m = next(k for k in d["mao"] if k["ticker"] == alvo)
    roe = next(i for i in m["ind"] if i["id"] == "roe")
    assert m["nivel"] == 2 and roe["real"] != roe["txt"]
    # baralho: o Baú já entrega as BARALHO_EQUIP cartas, então ele nasce cheio
    import cartas as C
    col = cli.get("/cartas/colecao").json()
    assert len(col["equip"]) == C.BARALHO_EQUIP and col["equip_max"] == C.BARALHO_EQUIP
    outra = next((k["tk"] for k in col["cartas"] if k["possui"] and not k["equipada"]), None)
    if outra:
        assert cli.post("/cartas/equipar", json={"tk": outra}).status_code == 400   # cheio: não entra mais
    assert cli.post("/cartas/equipar", json={"tk": "NAOTEM3"}).status_code == 400
    saiu = col["equip"][0]
    dep = cli.post("/cartas/desequipar", json={"tk": saiu}).json()
    assert saiu not in dep["equip"] and len(dep["equip"]) == C.BARALHO_EQUIP - 1
    assert cli.post("/cartas/equipar", json={"tk": saiu}).status_code == 200        # abriu espaço, volta a caber
    assert cli.post("/ticker/duelo").status_code in (200, 400)


def test_catalogo_e_admin_das_cartas(cli):
    cat = cli.get("/cartas/catalogo").json()["empresas"]
    assert cat["CVCB3"]["arte"] == "arte_CVCB3.webp" and cat["PETR4"]["raridade"] == "lendaria"
    assert cli.get("/admin/cartas").status_code == 403
    assert cli.post("/admin/cartas/empresa", json={"tk": "RENT3", "dados": {}}).status_code == 403
    import banco
    banco.sis_atualizar_conta("id-" + EU, {"papel": "admin"})
    import api.main as A
    A._CACHE_AUTH.clear()
    novo = {"nome": "Localiza", "setor": "Locação de veículos", "icone": "🚗", "atividade": "Aluga carros.", "fato": "Grande locadora.",
            "pontos": {"mercado": 30, "liquidez": 20, "relevancia": 10}}
    r = cli.post("/admin/cartas/empresa", json={"tk": "RENT3", "dados": novo})
    assert r.status_code == 200, r.text
    assert r.json()["raridade_fixa"] == "epica"
    assert cli.get("/cartas/catalogo").json()["empresas"]["RENT3"]["nome"] == "Localiza"
    assert cli.post("/admin/cartas/empresa", json={"tk": "RENT3", "dados": {"pontos": {"mercado": 90, "liquidez": 1, "relevancia": 1}}}).status_code == 400
    assert cli.post("/admin/cartas/regras", json={"evolucao": {"comum": [0]}}).status_code == 400
    assert cli.post("/admin/cartas/regras", json={"baus": {"comum": {"qtd": 3}}}).json()["baus"]["comum"]["qtd"] == 3
    import cartas_catalogo as CAT
    CAT.EXTRAS.clear()
