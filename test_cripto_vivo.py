"""Candles de cripto ao vivo (cripto_vivo): normalização, cache curto, falha da Binance e a rota /vivo/candles. Sem rede (o buscador é injetado)."""
import threading

import pytest

import cripto_vivo as CV
from test_api import cli  # noqa: F401  (mesma conta de teste)


def linha(i, base=100.0, tf_ms=300_000):
    ini = 1_700_000_000_000 + i * tf_ms
    return [ini, str(base + i), str(base + i + 2), str(base + i - 1), str(base + i + 1), "5.0", ini + tf_ms - 1, "0", 1, "0", "0", "0"]


def binance(n=60):
    return [linha(i) for i in range(n)]


@pytest.fixture(autouse=True)
def limpo():
    CV._cache.clear()
    yield
    CV._cache.clear()


def test_normaliza_para_o_formato_do_jogo_e_marca_o_candle_em_formacao():
    fim_ultimo = (1_700_000_000_000 + 59 * 300_000 + 299_999) / 1000
    v = CV.normalizar(binance(60), "5m", fim_ultimo - 10)                 # "agora" ainda está dentro do último candle
    assert len(v) == 60 and v[0]["o"] == 100.0 and v[0]["h"] == 102.0 and v[0]["l"] == 99.0 and v[0]["c"] == 101.0
    assert v[0]["t"] == "2023-11-14T22:13" and v[-2]["fechado"] is True and v[-1]["fechado"] is False


def test_descarta_linhas_quebradas():
    ruins = [["x"], [1, "0", "1", "1", "1", "1", 2], [1, "5", "4", "6", "5", "1", 2], linha(1)]
    assert len(CV.normalizar(ruins, "5m", 9e9)) == 1                       # sem preço positivo ou com máxima < mínima: fora


def test_cache_serve_todos_com_uma_consulta_e_renova_depois_do_ttl():
    chamadas = []
    relogio = {"t": 1000.0}

    def buscar(sim, tf, n):
        chamadas.append((sim, tf))
        return binance(60)
    a = CV.candles("BTC", "5m", 40, buscar, lambda: relogio["t"])
    b = CV.candles("btc", "5m", 40, buscar, lambda: relogio["t"] + 3)       # dentro do TTL: sem nova consulta
    assert len(chamadas) == 1 and a["candles"] == b["candles"] and len(a["candles"]) == 40 and a["atrasado"] is False
    CV.candles("BTC", "5m", 40, buscar, lambda: relogio["t"] + 9)           # passou do TTL (8 s)
    assert len(chamadas) == 2 and chamadas[0] == ("BTCUSDT", "5m")


def test_consultas_simultaneas_fazem_uma_so_chamada():
    chamadas, portao = [], threading.Event()

    def buscar(sim, tf, n):
        chamadas.append(1)
        portao.wait(1.0)
        return binance(60)
    res = []
    ts = [threading.Thread(target=lambda: res.append(CV.candles("ETH", "1m", 30, buscar))) for _ in range(6)]
    [t.start() for t in ts]
    portao.set()
    [t.join() for t in ts]
    assert len(res) == 6 and len(chamadas) == 1


def test_binance_fora_do_ar_mostra_o_ultimo_grafico_atrasado_e_sem_historico_falha():
    relogio = {"t": 1000.0}

    def quebrado(sim, tf, n):
        raise ConnectionError("fora")
    with pytest.raises(CV.SemDados):
        CV.candles("SOL", "5m", 30, quebrado, lambda: relogio["t"])        # nunca houve resposta
    CV.candles("SOL", "5m", 30, lambda s, t, n: binance(60), lambda: relogio["t"])
    r = CV.candles("SOL", "5m", 30, quebrado, lambda: relogio["t"] + 60)   # passou do TTL e a Binance caiu
    assert r["atrasado"] is True and len(r["candles"]) == 30


def test_entradas_invalidas():
    with pytest.raises(ValueError):
        CV.candles("PETR4", "5m")
    with pytest.raises(ValueError):
        CV.candles("BTC", "1h")


def test_rota_exige_login_e_devolve_o_grafico(cli, monkeypatch):  # noqa: F811
    monkeypatch.setattr(CV, "_buscar_binance", lambda s, tf, n: binance(80))
    from fastapi.testclient import TestClient
    import api.main as API
    assert TestClient(API.app).get("/vivo/candles").status_code in (401, 403)         # sem login não entra
    r = cli.get("/vivo/candles", params={"moeda": "BTC", "tf": "5m", "n": 50})
    assert r.status_code == 200 and r.json()["moeda"] == "BTC" and len(r.json()["candles"]) == 50
    assert cli.get("/vivo/candles", params={"moeda": "PETR4"}).status_code == 400
    monkeypatch.setattr(CV, "_buscar_binance", lambda s, tf, n: (_ for _ in ()).throw(ConnectionError("x")))
    CV._cache.clear()
    assert cli.get("/vivo/candles", params={"moeda": "ETH", "tf": "1m"}).status_code == 503
