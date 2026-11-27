"""Leitura ao vivo (vivo_partida e rotas /vivo/*): criar, conferir depois do horizonte, nota, limites. Candles sintéticos, sem rede."""
import pytest

import cripto_vivo as CV
import vivo_partida as VP
from test_api import cli  # noqa: F401  (mesma conta de teste)


def vela(i, c, fechado=True):
    return {"t": f"2025-01-01T{i // 60:02d}:{i % 60:02d}", "o": c, "h": c + 0.5, "l": c - 0.5, "c": c, "v": 1.0, "fechado": fechado}


def serie(n, passo=0.0, base=100.0, ultimo_aberto=False):
    v = [vela(i, base + i * passo) for i in range(n)]
    if ultimo_aberto:
        v[-1]["fechado"] = False
    return v


def test_cria_usando_so_candles_fechados_e_guarda_o_preco_de_referencia():
    velas = serie(60, ultimo_aberto=True)                                  # 59 fechados
    p = VP.criar("BTC", "1m", "alta", {"niveis": [{"preco": 105, "papel": "alvo"}]}, 40, velas, 1000.0, "x1")
    assert p["t_ref"] == velas[39]["t"] and p["ref"] == velas[39]["c"] and p["estado"] == "aberta" and p["horizonte"] == 15
    with pytest.raises(VP.ErroVivo):
        VP.criar("BTC", "1m", "alta", None, 61, velas, 1.0, "x")           # viu mais candles fechados do que existem: o gráfico mudou
    with pytest.raises(VP.ErroVivo):
        VP.criar("BTC", "1m", "lateral", None, 40, velas, 1.0, "x")
    with pytest.raises(VP.ErroVivo):
        VP.criar("BTC", "2h", "alta", None, 40, velas, 1.0, "x")


def test_so_confere_depois_do_horizonte_fechar():
    velas = serie(50)
    p = VP.criar("BTC", "1m", "alta", None, 40, velas, 1000.0, "x1")      # 10 candles fechados depois do de referência (índices 40 a 49): faltam 5 dos 15
    r = VP.conferir(p, velas, 2000.0)
    assert r["estado"] == "aberta" and r["faltam"] == 5


def test_confere_direcao_certa_e_errada():
    # sobe forte depois da leitura (passo 1.0 por candle >> ATR ~1): direção real = alta
    velas = serie(60, passo=1.0)
    alta = VP.conferir(VP.criar("BTC", "1m", "alta", None, 40, velas, 1000.0, "a"), velas, 2000.0)
    baixa = VP.conferir(VP.criar("BTC", "1m", "baixa", None, 40, velas, 1000.0, "b"), velas, 2000.0)
    assert alta["estado"] == "conferida" and alta["resultado"]["real"] == "alta" and alta["resultado"]["nota"] == 100.0
    assert baixa["resultado"]["direcao_ok"] is False and baixa["resultado"]["nota"] == 0.0


def test_aguardar_sem_desenhos_fecha_sem_nota_e_nao_conta_como_acerto():
    velas = serie(60, passo=1.0)
    r = VP.conferir(VP.criar("BTC", "1m", None, None, 40, velas, 1000.0, "a"), velas, 2000.0)
    assert r["estado"] == "conferida" and r["resultado"]["nota"] is None and r["resultado"]["direcao_ok"] is None


def test_nota_mistura_direcao_e_desenhos():
    velas = serie(60, passo=1.0)
    marcas = {"niveis": [{"preco": velas[39]["c"] + 8.0, "papel": "alvo"}]}      # o preço passa dos 8 de alta
    r = VP.conferir(VP.criar("BTC", "1m", "alta", marcas, 40, velas, 1000.0, "a"), velas, 2000.0)["resultado"]
    assert r["desenhos"]["nota"] is not None and r["nota"] == round((100.0 + r["desenhos"]["nota"]) / 2, 1)


def test_referencia_fora_da_janela_expira_depois_de_seis_horas():
    p = VP.criar("BTC", "1m", "alta", None, 40, serie(60), 1000.0, "a")
    outra = [{**c, "t": c["t"].replace("2025-01-01", "2025-02-01")} for c in serie(60)]
    assert VP.conferir(p, outra, 1000.0 + 3600)["estado"] == "aberta"
    assert VP.conferir(p, outra, 1000.0 + VP.EXPIRA_S + 1)["estado"] == "expirada"


def test_rotas_leitura_inteira(cli, monkeypatch):  # noqa: F811
    estado = {"velas": 60}

    def binance(sim, tf, n):
        base = 1_700_000_000_000
        return [[base + i * 60_000, str(100 + i), str(100.5 + i), str(99.5 + i), str(100 + i), "1", base + i * 60_000 + 59_999, "0", 1, "0", "0", "0"] for i in range(estado["velas"])]
    monkeypatch.setattr(CV, "_buscar_binance", binance)
    CV._cache.clear()
    assert cli.get("/vivo/moedas").json()["moedas"][0]["id"] == "BTC"
    tela = cli.get("/vivo/BTC/1m/tela").json()["tela"]
    assert len(tela["candles"]) == 60 and tela["ticker"] == "BTC" and tela["vivo"] is True
    r = cli.post("/vivo/BTC/1m/estrategia", json={"direcao": "alta", "n_candles": 40})
    assert r.status_code == 200 and r.json()["previsao"]["estado"] == "aberta"
    assert cli.post("/vivo/BTC/1m/estrategia", json={"direcao": "baixa", "n_candles": 40}).status_code == 409   # já tem uma aberta nesta moeda/duração
    assert cli.post("/vivo/PETR4/1m/estrategia", json={"direcao": "alta", "n_candles": 40}).status_code in (400, 503)
    assert cli.get("/vivo/previsoes").json()["itens"][0]["estado"] == "conferida"          # 60 candles já cobrem o horizonte (40 + 15)
    CV._cache.clear()
    estado["velas"] = 50
    r2 = cli.post("/vivo/ETH/1m/estrategia", json={"direcao": "alta", "n_candles": 40})
    CV._cache.clear()
    it = [x for x in cli.get("/vivo/previsoes").json()["itens"] if x["moeda"] == "ETH"][0]
    assert r2.status_code == 200 and it["estado"] == "aberta" and it["faltam"] == 5


def test_limite_de_leituras_abertas(cli, monkeypatch):  # noqa: F811
    monkeypatch.setattr(CV, "_buscar_binance", lambda s, tf, n: [[1_700_000_000_000 + i * 60_000, "100", "101", "99", "100", "1", 1_700_000_000_000 + i * 60_000 + 59_999, "0", 1, "0", "0", "0"] for i in range(45)])
    CV._cache.clear()
    codigos = [cli.post(f"/vivo/{m}/1m/estrategia", json={"direcao": "alta", "n_candles": 35}).status_code for m in ("BTC", "ETH", "SOL", "BNB", "XRP")]
    assert codigos == [200, 200, 200, 200, 409]
