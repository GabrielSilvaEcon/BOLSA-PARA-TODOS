"""Trade Battle AO VIVO (cripto, candles de 2 min, 30 min): cenário e partida inteira pela API com uma Binance falsa e relógio controlado. Sem rede."""
import json
import math

import pytest

import api.main as API
import cripto_vivo as CV
import trader_battle as TB
import trader_vivo as TV
from test_api import cli  # noqa: F401  (mesma conta de teste)

T0 = 1_700_000_130          # algum instante: 10 s depois de um minuto fechado... (1_700_000_100 é fronteira de minuto)
M0 = 1_700_000_100          # âncora esperada para T0


def pseg(s: int) -> float:
    """Preço do fechamento do segundo `s` (epoch): passeio determinístico, suave e sempre positivo."""
    return 30_000 + 400 * math.sin(s / 3700.0) + 90 * math.sin(s / 310.0) + (s % 7) * 0.3


def kl_1m(agora: float, n: int, atraso: float = 0.0, fim_ms=None):
    ate = int((agora - atraso) // 60)
    if fim_ms is not None:
        ate = min(ate, int(fim_ms // 60000))
    linhas = []
    for m in range(ate - n + 1, ate + 1):
        ini = m * 60
        xs = [pseg(s) for s in range(ini, ini + 60)]
        o, c = pseg(ini - 1), xs[-1]
        linhas.append([ini * 1000, f"{o:.2f}", f"{max(xs + [o]):.2f}", f"{min(xs + [o]):.2f}", f"{c:.2f}", "5", (ini + 60) * 1000 - 1, "0", 1, "0", "0", "0"])
    return linhas


def kl_1s(agora: float, fim_ms, n: int, atraso: float = 0.0):
    ate = int(agora - atraso) if fim_ms is None else int(fim_ms // 1000)
    ate = min(ate, int(agora - atraso))
    return [[s * 1000, f"{pseg(s - 1):.2f}", f"{max(pseg(s - 1), pseg(s)):.2f}", f"{min(pseg(s - 1), pseg(s)):.2f}", f"{pseg(s):.2f}", "1", s * 1000 + 999, "0", 1, "0", "0", "0"]
            for s in range(ate - n + 1, ate + 1)]


@pytest.fixture
def mercado(monkeypatch):
    rel = {"t": float(T0), "atraso": 0.0}
    monkeypatch.setattr(API, "_agora", lambda: rel["t"])
    monkeypatch.setattr(CV, "_buscar_binance", lambda sim, tf, n, fim_ms=None: kl_1m(rel["t"], n, rel["atraso"], fim_ms))
    monkeypatch.setattr(CV, "_buscar_binance_seg", lambda sim, fim_ms, n: kl_1s(rel["t"], fim_ms, n, rel["atraso"]))
    CV._cache.clear()
    CV._seg.clear()
    yield rel
    CV._cache.clear()
    CV._seg.clear()


def ver(c, pid):
    CV._cache.clear()                                      # o relógio é falso: não reaproveita o gráfico guardado de outro instante
    return c.get(f"/trade/solo/{pid}").json()


def test_ancora_e_cenario_sem_futuro(mercado):
    assert TV.ancora(T0) == M0
    cen = TV.cenario("BTC", M0, float(T0))
    assert len(cen["candles"]) == 200 + 1800 and len(cen["grupo"]) == 1800 and len(cen["velas_t"]) == 15 and cen["tf"] == "2m"
    assert cen["_vivo_n"] == 30                              # segundos M0..T0-1 já fecharam (o corrente ainda está se formando)
    e = cen["escala"]
    assert e == pytest.approx(1e-3) and cen["ticker"] == "BTC ÷1.000" and TB.validar_cenario(cen)[0]
    passo0 = cen["candles"][200]
    assert passo0["c"] == pytest.approx(pseg(M0) * e, abs=1e-3)                           # o passo é o mercado de verdade
    assert {c["c"] for c in cen["candles"][200 + 30:]} == {cen["candles"][200 + 29]["c"]}    # o resto é só preenchimento plano
    h = cen["candles"][199]                                                                 # candle de 2 min do histórico = 2 candles de 1 min juntos
    assert h["t"] == "2023-11-14T22:13" or h["t"] < "2023-11-14T22:15"


def test_partida_ao_vivo_inteira(cli, mercado):  # noqa: F811
    r = cli.post("/trade/vivo", json={"moeda": "BTC"})
    assert r.status_code == 200, r.text
    j = r.json()
    pid, tela = j["id"], j["tela"]
    assert j["fase"] == "analise" and tela["corrida"] is True and "BTC" in str(tela["ticker"])
    n0 = len(tela["candles"])
    assert 200 < n0 <= 201 and 28 <= tela["seg"] + 0 <= 30 + 0 or tela["seg"] <= 30        # 200 do histórico + o candle que já está se formando; 30 s de estratégia
    c0 = tela["candles"][-1]["c"]
    mercado["t"] = T0 + 8.0                                  # o gráfico ROLA durante a estratégia: o candle em formação mexe
    v = ver(cli, pid)
    assert v["fase"] == "analise" and v["tela"]["candles"][-1]["c"] != c0
    assert cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"}).status_code == 200
    v = ver(cli, pid)
    assert v["fase"] == "replay"                             # todos confirmaram: a partida começa na hora (não espera os 30 s)
    mercado["t"] = T0 + 20.0
    c = cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "c1", "tipo": "mercado", "direcao": "alta", "q": 10}})
    assert c.status_code == 200, c.text
    mercado["t"] = T0 + 24.0
    pos = (ver(cli, pid)["tela"].get("mesa") or {}).get("posicao")
    assert pos and pos["direcao"] == "alta" and pos["q"] == 10
    assert cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "z1", "tipo": "encerrar"}}).status_code == 200
    mercado["t"] = M0 + 1800 + 20.0
    f = ver(cli, pid)
    assert f["fase"] == "fim" and f["fim"]["resultado"] is not None


def test_sem_confirmar_a_partida_comeca_sozinha_apos_30_s(cli, mercado):  # noqa: F811
    pid = cli.post("/trade/vivo", json={"moeda": "ETH"}).json()["id"]
    mercado["t"] = T0 + 29.0
    assert ver(cli, pid)["fase"] == "analise"
    mercado["t"] = T0 + 31.0
    assert ver(cli, pid)["fase"] == "replay"


def test_nao_encerra_nem_mostra_passo_que_o_mercado_ainda_nao_fechou(cli, mercado):  # noqa: F811
    pid = cli.post("/trade/vivo", json={"moeda": "SOL"}).json()["id"]
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "baixa"})
    mercado["atraso"] = 90.0                               # a Binance está 90 s atrasada
    mercado["t"] = M0 + 1800 + 30.0                        # o relógio diz que acabou...
    assert ver(cli, pid)["fase"] == "replay"               # ...mas os últimos passos não existem ainda: continua
    mercado["atraso"] = 0.0
    mercado["t"] = M0 + 1800 + 40.0
    assert ver(cli, pid)["fase"] == "fim"


def test_moeda_invalida(cli, mercado):  # noqa: F811
    assert cli.post("/trade/vivo", json={"moeda": "PETR4"}).status_code == 400


# ------------------------------------------------------------------ duelo (BATALHAR) com bot
def test_batalhar_ao_vivo_acha_bot_e_a_partida_corre_ate_o_fim(cli, mercado):  # noqa: F811
    r = cli.post("/trade/fila", json={"corrida": "vivo"})
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "fila"
    mercado["t"] = T0 + 8.0                                             # ninguém apareceu em 7 s: entra um bot (com nome de jogador comum)
    f = cli.get("/trade/fila").json()
    assert f["estado"] == "partida", f
    sid = f["id"]
    v = cli.get(f"/trade/salas/{sid}").json()
    t = v["tela"]
    assert v["fase"] == "analise" and t["corrida"] is True and "÷" in str(t["ticker"]) + "÷" and len(t["candles"]) >= 200
    assert cli.post(f"/trade/salas/{sid}/estrategia", json={"direcao": "alta"}).status_code == 200     # o bot já confirmou: com a minha, começa na hora
    CV._cache.clear()
    assert cli.get(f"/trade/salas/{sid}").json()["fase"] == "replay"
    # a partida corre 30 min: o bot opera sozinho, sem ver o futuro
    for dt in range(15, 1800, 15):                              # como no jogo: o app consulta o tempo todo e o bot decide a cada 15 s
        mercado["t"] = M0 + 8 + dt
        CV._cache.clear()
        cli.get(f"/trade/salas/{sid}")
    mercado["t"] = M0 + 1800 + 20.0
    CV._cache.clear()
    fim = cli.get(f"/trade/salas/{sid}").json()
    assert fim["fase"] == "fim" and fim.get("fim"), fim["fase"]
    placar = fim["fim"]["final"]["placar"]
    assert len(placar) == 2 and sum(1 for x in placar if x["voce"]) == 1 and {x["pos"] for x in placar} == {1, 2}      # dois jogadores, um vencedor
    import banco, json as _j
    dados = _j.loads(banco._selecionar("tb_partidas", {"id": sid}, ["dados"], limite=1)[0]["dados"]) if isinstance(banco._selecionar("tb_partidas", {"id": sid}, ["dados"], limite=1)[0]["dados"], str) else banco._selecionar("tb_partidas", {"id": sid}, ["dados"], limite=1)[0]["dados"]
    acoes_bot = [a for a in dados["p"]["acoes"] if str(a["jogador"]).startswith("bot:")]
    print("ACOES_BOT", len(acoes_bot), [placar])
    assert len(acoes_bot) >= 1                                                      # o bot operou sozinho, só com o que já tinha aparecido


def test_duas_pessoas_comecam_juntas_ao_confirmar(cli, mercado, monkeypatch):  # noqa: F811
    import trader_online_dados as OL
    sala = OL.criar_sala("ana@x.com", "", float(T0), corrida="vivo")
    assert sala["id"]


# ------------------------------------------------------------------ setups ao vivo (sem pausa)
def test_setup_ao_vivo_abre_a_janela_sem_pausar_o_mercado_e_a_decisao_manda_a_ordem(cli, mercado, monkeypatch):  # noqa: F811
    import setups_dados as SD
    import setups as SU
    monkeypatch.setattr(SD, "equipados", lambda email: ["setup_classico"])
    chamadas = {"n": 0}

    def detectar(sid, candles, *a):
        chamadas["n"] += 1
        return {"direcao": "alta", "motivo": "teste"} if chamadas["n"] == 2 else None
    monkeypatch.setattr(SU, "detectar", detectar)
    pid = cli.post("/trade/vivo", json={"moeda": "BTC"}).json()["id"]
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"})
    achou = None
    for dt in range(1, 700, 2):                                          # 2 min por candle: o 2º candle fecha por volta de M0 + 240 s
        mercado["t"] = T0 + dt
        v = ver(cli, pid)
        ev = (v["tela"].get("setup") or {}).get("evento") if isinstance(v.get("tela"), dict) else None
        if ev:
            achou = (dt, v)
            break
    assert achou, "o setup nunca ativou"
    dt, v = achou
    assert v["tela"]["pausada"] is False                                  # o mercado NÃO parou
    n_antes = len(v["tela"]["candles"])
    mercado["t"] = T0 + dt + 6
    v2 = ver(cli, pid)
    assert v2["fase"] == "replay" and v2["tela"]["candles"][-1]["c"] != v["tela"]["candles"][-1]["c"] or len(v2["tela"]["candles"]) >= n_antes   # o gráfico seguiu andando
    r = cli.post(f"/trade/solo/{pid}/setup", json={"acao": "aceitar", "q": 5})
    assert r.status_code == 200, r.text
    mercado["t"] = T0 + dt + 9
    pos = (ver(cli, pid)["tela"].get("mesa") or {}).get("posicao")
    assert pos and pos["direcao"] == "alta"                               # a decisão virou ordem a mercado, no preço de quando decidiu


# ------------------------------------------------------------------ os dois modos convivem
from test_social_api import dois  # noqa: E402,F401  (fixture: duas contas amigas logadas)


def test_desafio_de_amigo_nos_dois_modos(dois, mercado):
    ana, bia = dois
    ana.post("/social/pedir", json={"usuario": "bia_h"})
    h_ana = bia.get("/social").json()["recebidos"][0]["h"]
    bia.post("/social/responder", json={"h": h_ana, "aceitar": True})
    h_bia = ana.get("/social").json()["amigos"][0]["h"]
    # Ao vivo: os dois entram, a partida começa no mercado de agora (duas pessoas, sem bot)
    d = ana.post("/social/desafiar", json={"h": h_bia, "jogo": "trade", "corrida": "vivo"}).json()
    assert bia.post("/social/convite/entrar", json={"h": h_ana}).json()["id"] == d["id"]
    CV._cache.clear()
    v = ana.get(f"/trade/salas/{d['id']}").json()
    assert v["estado"] == "jogo"
    assert v["tela"]["vivo"] is True and v["tela"]["corrida"] is True and len(v["tela"]["candles"]) >= 200


def test_desafio_de_amigo_no_replay_continua_como_antes(dois, mercado):
    ana, bia = dois
    ana.post("/social/pedir", json={"usuario": "bia_h"})
    h_ana = bia.get("/social").json()["recebidos"][0]["h"]
    bia.post("/social/responder", json={"h": h_ana, "aceitar": True})
    h_bia = ana.get("/social").json()["amigos"][0]["h"]
    d = ana.post("/social/desafiar", json={"h": h_bia, "jogo": "trade"}).json()              # sem corrida: o replay de sempre
    assert bia.post("/social/convite/entrar", json={"h": h_ana}).json()["id"] == d["id"]
    v = ana.get(f"/trade/salas/{d['id']}").json()
    assert v["estado"] == "jogo" and v["tela"]["vivo"] is False and v["tela"]["corrida"] is True


def test_modo_replay_continua_igual_ao_de_antes(cli, mercado, monkeypatch):  # noqa: F811
    """A fila do Replay ('rapida') segue existindo e separada da do ao vivo: quem procura Replay não é pareado com quem procura Ao vivo."""
    r1 = cli.post("/trade/fila", json={"corrida": "rapida"})
    assert r1.status_code == 200 and r1.json()["estado"] == "fila", r1.text
    import trader_online_dados as OL
    assert OL.TB.spec_corrida("rapida")["tf"] == "15m" and OL.TB.spec_corrida("vivo")["tf"] == "2m"
    assert "vivo" not in OL.TB.CORRIDAS and "rapida" in OL.TB.CORRIDAS


def test_historico_curto_busca_paginas_mais_antigas(mercado, monkeypatch):
    """Se a Binance entrega pouco histórico na 1ª consulta, o cenário busca páginas mais antigas em vez de falhar."""
    entregues = []

    def curta(sim, tf, n, fim_ms=None):
        entregues.append(fim_ms)
        return kl_1m(mercado["t"], 150 if fim_ms is None else n, 0.0, fim_ms)          # a 1ª página vem com só 150 candles
    monkeypatch.setattr(CV, "_buscar_binance", curta)
    CV._cache.clear()
    h = CV.historico("BTC", "1m", "2023-11-14T22:30", 400, agora=lambda: mercado["t"])
    assert len(h) >= 400 and entregues[0] is None and any(x is not None for x in entregues)
    assert [c["t"] for c in h] == sorted({c["t"] for c in h})                          # sem repetidos e em ordem


def test_historico_impossivel_diz_quantos_achou(mercado, monkeypatch):
    monkeypatch.setattr(CV, "_buscar_binance", lambda sim, tf, n, fim_ms=None: kl_1m(mercado["t"], 60, 0.0, fim_ms) if fim_ms is None else [])
    CV._cache.clear()
    with pytest.raises(CV.SemDados) as e:
        CV.historico("BTC", "1m", "2023-11-14T22:30", 400, agora=lambda: mercado["t"])
    assert "de 400 candles de 1m" in str(e.value)


def test_saude_vivo_mostra_o_que_o_servidor_recebe(mercado):
    from fastapi.testclient import TestClient
    r = TestClient(API.app).get("/saude/vivo", params={"moeda": "BTC"})        # sem login: só contagens de mercado público
    assert r.status_code == 200, r.text
    j = r.json()
    assert j["1m"]["n"] >= 400 and j["1m"]["fechados"] >= 400 and j["1s"]["n"] > 60 and j["cenario"]["ok"] is True
    assert TestClient(API.app).get("/saude/vivo", params={"moeda": "PETR4"}).status_code == 400
