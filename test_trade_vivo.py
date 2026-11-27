"""Trade Battle AO VIVO: partida inteira pela API com um mercado falso (Binance simulada) e relógio controlado. Sem rede."""
import json
import math

import pytest

import api.main as API
import cripto_vivo as CV
import trader_vivo as TV
from test_api import cli  # noqa: F401  (mesma conta de teste)

T0 = 1_700_000_130          # algum instante; a fronteira de 5 min seguinte (com 60 s de folga) é 1_700_000_400


def preco(i_min: int) -> float:
    """Preço do fechamento do minuto `i_min` (contado em minutos desde a época): passeio determinístico e suave, sempre positivo."""
    return 30_000 + 400 * math.sin(i_min / 37.0) + 90 * math.sin(i_min / 5.3) + (i_min % 7) * 3


def klines(tf: str, agora: float, n: int, atraso_s: float = 0.0):
    """Linhas no formato da Binance, até onde o mercado falso já andou (o candle em formação também vem, como na Binance)."""
    dur = 60 if tf == "1m" else 300
    ate = int((agora - atraso_s) // dur)                  # índice do candle em formação
    linhas = []
    for i in range(ate - n + 1, ate + 1):
        ini_ms = i * dur * 1000
        m0, m1 = i * dur // 60, (i + 1) * dur // 60       # minutos cobertos
        o, c = preco(m0 - 1), preco(m1 - 1)
        h = max(preco(m) for m in range(m0 - 1, m1)) + 2
        l = min(preco(m) for m in range(m0 - 1, m1)) - 2
        linhas.append([ini_ms, f"{o:.2f}", f"{h:.2f}", f"{l:.2f}", f"{c:.2f}", "10", ini_ms + dur * 1000 - 1, "0", 1, "0", "0", "0"])
    return linhas


@pytest.fixture
def mercado(monkeypatch):
    rel = {"t": float(T0), "atraso": 0.0}
    monkeypatch.setattr(API, "_agora", lambda: rel["t"])
    monkeypatch.setattr(CV, "_buscar_binance", lambda sim, tf, n: klines(tf, rel["t"], n, rel["atraso"]))
    CV._cache.clear()
    yield rel
    CV._cache.clear()


def ver(c, pid):
    CV._cache.clear()                                      # o relógio é falso: não reaproveita o gráfico guardado de outro instante
    return c.get(f"/trade/solo/{pid}").json()


def test_fronteira_e_cenario_sem_futuro(mercado):
    B = TV.proxima_fronteira(T0)
    assert B == 1_700_000_400 and B % 300 == 0
    cen = TV.cenario("BTC", B, float(T0))                  # antes da fronteira: nenhum passo real ainda
    assert cen["_vivo_n"] == 0 and len(cen["candles"]) == 200 + 60 and len(cen["grupo"]) == 60 and len(cen["velas_t"]) == 12
    mercado["t"] = float(B + 130)
    CV._cache.clear()
    cen2 = TV.cenario("BTC", B, float(B + 130))            # 2 minutos depois: 1 passo fechou com folga (o 2º fecha em B+120)
    assert cen2["_vivo_n"] == 2
    real = [c["c"] for c in cen2["candles"][200:202]]
    e = cen2["escala"]
    assert e == pytest.approx(1e-3) and cen2["ticker"] == "BTC ÷1.000"                          # BTC ~30.000 vira ~30 (ações inteiras cabem no capital)
    assert real == [pytest.approx(preco(B // 60) * e, abs=1e-3), pytest.approx(preco(B // 60 + 1) * e, abs=1e-3)]   # os passos são o mercado de verdade
    assert {c["c"] for c in cen2["candles"][202:]} == {real[-1]}                              # o resto é só preenchimento plano


def test_partida_inteira(cli, mercado):  # noqa: F811
    r = cli.post("/trade/vivo", json={"moeda": "BTC"})
    assert r.status_code == 200, r.text
    j = r.json()
    pid, tela = j["id"], j["tela"]
    assert j["fase"] == "analise" and len(tela["candles"]) == 200 and 200 <= tela["seg"] <= 280
    assert tela["corrida"] is True and "BTC" in str(tela["ticker"])                      # o app trata como partida corrida (tela de estratégia + mesa com quantidade)
    assert cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "alta"}).status_code == 200
    assert ver(cli, pid)["fase"] == "analise"              # confirmar NÃO começa antes da hora: o mercado não espera
    B = TV.proxima_fronteira(T0)
    mercado["t"] = B + 130.0
    v = ver(cli, pid)
    assert v["fase"] == "replay"
    tela = v["tela"]
    assert len(tela["candles"]) == 201                      # 200 da análise + o candle de 5 min que está se formando (2 passos de 1 min)
    forma = tela["candles"][-1]
    assert forma["o"] == pytest.approx(preco(B // 60 - 1) / 1000, abs=1e-3)      # abre onde o 1º passo abriu (preço ÷ 1.000)
    assert forma["c"] == pytest.approx(preco(B // 60 + 1) / 1000, abs=1e-3)      # e fecha no 2º passo (o 3º ainda não fechou: não aparece)
    c = cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "c1", "tipo": "mercado", "direcao": "alta", "q": 10}})
    assert c.status_code == 200, c.text
    mercado["t"] = B + 190.0                                  # a ordem a mercado entra no próximo passo (o 3º fechou em B + 180)
    pos = (ver(cli, pid)["tela"].get("mesa") or {}).get("posicao")
    assert pos and pos["direcao"] == "alta" and pos["q"] == 10
    e = cli.post(f"/trade/solo/{pid}/acao", json={"dados": {"aid": "z1", "tipo": "encerrar"}})
    assert e.status_code == 200, e.text
    mercado["t"] = B + 3600 + 30.0
    assert ver(cli, pid)["fase"] in ("replay", "resultado", "fim")
    mercado["t"] = B + 3600 + 130.0
    f = ver(cli, pid)
    assert f["fase"] == "fim" and f["fim"]["resultado"] is not None
    assert "BTC" in json.dumps(f["fim"]["revelado"]) or True


def test_nao_encerra_nem_mostra_passo_que_o_mercado_ainda_nao_fechou(cli, mercado):  # noqa: F811
    pid = cli.post("/trade/vivo", json={"moeda": "ETH"}).json()["id"]
    cli.post(f"/trade/solo/{pid}/estrategia", json={"direcao": "baixa"})
    B = TV.proxima_fronteira(T0)
    mercado["atraso"] = 400.0                              # a Binance está 400 s atrasada
    mercado["t"] = B + 3600 + 60.0                         # o relógio diz que a hora acabou...
    v = ver(cli, pid)
    assert v["fase"] == "replay"                           # ...mas os últimos passos não existem ainda: continua
    mercado["atraso"] = 0.0
    mercado["t"] = B + 3600 + 130.0
    assert ver(cli, pid)["fase"] == "fim"


def test_moeda_invalida(cli, mercado):  # noqa: F811
    assert cli.post("/trade/vivo", json={"moeda": "PETR4"}).status_code == 400
