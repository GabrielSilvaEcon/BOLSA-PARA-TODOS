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


def kl_1m(agora: float, n: int, atraso: float = 0.0):
    ate = int((agora - atraso) // 60)
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
    monkeypatch.setattr(CV, "_buscar_binance", lambda sim, tf, n: kl_1m(rel["t"], n, rel["atraso"]))
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
