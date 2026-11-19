"""Etapa D do Trade Battle: o candle se forma com os candles menores REAIS (nada inventado) e a partida opera passo a passo."""
import pandas as pd
import pytest

import trader_battle as TB
import trader_dados as TD
import trader_qtd as TQ

EU = "eu@x.com"


def _k(t, o, h, l, c, v=1000.0):
    return {"t": t, "o": o, "h": h, "l": l, "c": c, "v": v}


# ------------------------------------------------------------------ agrupamento
def test_agrupar_monta_o_candle_do_grafico_com_os_passos_revelados():
    subs = [_k("2024-03-04T10:00", 10, 10.5, 9.8, 10.2), _k("2024-03-04T10:05", 10.2, 10.9, 10.1, 10.8), _k("2024-03-04T10:10", 10.8, 10.8, 10.0, 10.1),
            _k("2024-03-04T10:15", 10.1, 10.3, 10.0, 10.2)]
    v = TB.agrupar(subs, [0, 0, 0, 1], ["2024-03-04T10:00", "2024-03-04T10:15"])
    assert v[0] == {"t": "2024-03-04T10:00", "o": 10, "h": 10.9, "l": 9.8, "c": 10.1, "v": 3000.0}
    assert v[1]["o"] == 10.1 and v[1]["c"] == 10.2
    parcial = TB.agrupar(subs[:2], [0, 0], ["2024-03-04T10:00"])                # candle ainda se formando: só o que já aconteceu
    assert parcial == [{"t": "2024-03-04T10:00", "o": 10, "h": 10.9, "l": 9.8, "c": 10.8, "v": 2000.0}]


def _partida(formato="intermediaria"):
    cen = TD.demo_corrida(formato, 5)
    p = TB.nova_partida(cen, cen["tf"], [EU], 1000.0, apostas={EU: {"stake": 10_000.0, "pat": 200_000.0}}, corrida=formato)
    TB.salvar_estrategia(p, EU, {"direcao": "alta", "tipo": "continuacao", "confianca": 3}, None, 0, 1001.0)
    TB.iniciar_replay(p, EU, 1002.0)
    return p, cen


def _t_passos(p, n):
    cfg = TB.cfg_de(p)
    return 1002.0 + n * cfg["t_replay_s"] / cfg["n_replay"] + 0.01


def test_visao_mostra_o_candle_se_formando_e_nunca_o_futuro():
    p, cen = _partida()
    na, k = cen["n_analise"], TB.CORRIDAS["intermediaria"]["k"]
    v = TB.visao(p, cen, _t_passos(p, k + 5), EU)                              # 1 candle completo + 5 passos do 2º
    assert len(v["candles"]) == na + 2 and v["revelados"] == 2 and v["total_replay"] == TB.CORRIDAS["intermediaria"]["n_replay"]
    rep = cen["candles"][na:]
    ultimo = v["candles"][-1]
    passos = rep[k:k + 5]
    assert ultimo["o"] == passos[0]["o"] and ultimo["c"] == passos[-1]["c"]
    assert ultimo["h"] == max(x["h"] for x in passos) and ultimo["l"] == min(x["l"] for x in passos)
    completo = TB.visao(p, cen, _t_passos(p, 2 * k), EU)["candles"][-1]
    assert completo["c"] == rep[2 * k - 1]["c"]                                   # o candle fechado tem o fechamento do último passo dele


def test_quatro_segundos_por_candle_do_grafico():
    for f, sp in TB.CORRIDAS.items():
        p, _cen = _partida(f)
        assert TB.cfg_de(p)["t_replay_s"] == sp["n_replay"] * 4.0


def test_ordem_a_mercado_executa_no_preco_real_do_proximo_passo():
    p, cen = _partida()
    na = cen["n_analise"]
    TB.registrar_acao(p, cen, EU, {"aid": "c", "tipo": "mercado", "direcao": "alta", "q": 10}, _t_passos(p, 5))
    v = TB.visao(p, cen, _t_passos(p, 7), EU)
    assert v["mesa"]["posicao"]["preco_entrada"] == cen["candles"][na + 5]["o"]   # abertura do 6º candle de 5 min (dentro do candle de 1 h)
    assert v["mesa"]["posicao"]["indice_entrada"] == na + 0                       # desenhado no 1º candle do gráfico


def test_stop_e_alvo_na_ordem_em_que_os_precos_aconteceram():
    # candle de 1 h que sobe até o alvo e depois cai até o stop: com os passos reais, vale o alvo (aconteceu primeiro)
    subs = [_k("2024-03-04T10:00", 10.0, 10.1, 9.95, 10.05), _k("2024-03-04T10:05", 10.05, 10.6, 10.0, 10.5),
            _k("2024-03-04T10:10", 10.5, 10.5, 9.4, 9.5)]
    acoes = [{"tipo": "mercado", "direcao": "alta", "q": 100, "stop": 9.6, "alvo": 10.4, "n_rev": 0, "ordem": 1}]
    st = TQ.simular(subs, acoes, 10.0, 10_000.0, final=True)
    assert [(t["motivo"], t["saida"]) for t in st["trades"]] == [("alvo", 10.4)]
    so_vela = TQ.simular(TB.agrupar(subs, [0, 0, 0]), acoes, 10.0, 10_000.0, final=True)   # sem os passos não dá para saber: o jogo antigo assumia o stop
    assert so_vela["trades"][0]["motivo"] == "stop"


def test_resultado_e_pontos_usam_os_candles_do_grafico():
    p, cen = _partida("rapida")
    TB.registrar_acao(p, cen, EU, {"aid": "c", "tipo": "mercado", "direcao": "alta", "q": 50}, _t_passos(p, 1))
    fim = 1002.0 + TB.cfg_de(p)["t_replay_s"] + 1
    TB.avancar(p, fim, TD.por_id([cen]))
    res = p["resultados"]["1:" + EU]
    n_velas = TB.CORRIDAS["rapida"]["n_replay"]
    assert all(0 <= t["i_saida"] < n_velas for t in res["operacoes"])
    assert res["real"]["fim"] == cen["candles"][-1]["c"]
    TB.proxima_rodada(p, fim + 1)
    rv = TB.visao(p, cen, fim + 2, EU)["revelado"]
    assert rv["de"] == "04/03/2024" or rv["de"].endswith("/2024")


def test_cenario_sem_passos_e_recusado():
    cen = TD.demo_corrida("longa", 2)
    velho = {k: v for k, v in cen.items() if k not in ("grupo", "velas_t")}
    assert not TB.validar_cenario(velho)[0]
    buraco = {**cen, "grupo": cen["grupo"][:-1]}
    assert not TB.validar_cenario(buraco)[0]


# ------------------------------------------------------------------ preparação dos dados (Yahoo) e biblioteca
def _df(inicio, n, passo_min, por_dia, preco=10.0):
    idx, t, dia = [], pd.Timestamp(inicio), 0
    while len(idx) < n:
        base = pd.Timestamp(inicio).normalize() + pd.Timedelta(days=dia) + pd.Timedelta(hours=10)
        if base.weekday() < 5:
            for j in range(por_dia):
                idx.append(base + pd.Timedelta(minutes=passo_min * j))
                if len(idx) >= n:
                    break
        dia += 1
    vals = [preco + (i % 7) * 0.01 for i in range(len(idx))]
    return pd.DataFrame({"Open": vals, "High": [v + 0.05 for v in vals], "Low": [v - 0.05 for v in vals], "Close": vals, "Volume": [1000.0] * len(idx)},
                        index=pd.DatetimeIndex(idx))


def test_montar_corridas_so_com_trechos_completos_e_sem_sobrepor():
    sp = TB.CORRIDAS["intermediaria"]
    dv = _df("2024-01-01", 7 * 140, 60, 7)                                   # 1 h cobre tudo (no Yahoo: 2 anos), 7 por pregão
    ds = _df("2024-03-11", 7 * 12 * 30, 5, 84)                               # 5 min só dos últimos 30 pregões (84 por pregão = 7 h)
    cs = TD.montar_corridas(dv, ds, "intermediaria", "PETR4", "2026-11-19T19:00", max_n=2)
    assert len(cs) == 2
    for c in cs:
        assert TB.validar_cenario(c)[0] and c["sub"] == "5m" and len(c["velas_t"]) == sp["n_replay"]
        assert all(c["grupo"].count(g) == 12 for g in range(sp["n_replay"]))   # cada candle de 1 h = 12 candles reais de 5 min
    a, b = cs
    assert a["velas_t"][0] > b["velas_t"][-1]                                # do mais recente para trás, sem sobrepor
    ocup = [(c["velas_t"][0], c["velas_t"][-1]) for c in cs]
    outros = TD.montar_corridas(dv, ds, "intermediaria", "PETR4", "2026-11-20T19:00", max_n=5, ocupados=ocup)
    assert all(not (c["velas_t"][-1] >= de and c["velas_t"][0] <= ate) for c in outros for de, ate in ocup)


def test_trecho_com_candle_menor_faltando_fica_de_fora():
    dv = _df("2024-01-01", 7 * 140, 60, 7)
    ds = _df("2024-03-11", 7 * 12 * 12, 5, 84)
    furado = ds.drop(ds.index[[100, 400, 700, 950]])                         # um 5 min faltando em vários pregões
    furos = {t.strftime("%Y-%m-%d") for t in ds.index[[100, 400, 700, 950]]}
    cs = TD.montar_corridas(dv, furado, "intermediaria", "VALE3", "2026-11-19T19:00", max_n=5)
    inteiros = TD.montar_corridas(dv, ds, "intermediaria", "VALE3", "2026-11-19T19:00", max_n=5)
    assert len(cs) < len(inteiros)                                           # os trechos com buraco somem
    for c in cs:
        assert not {x[:10] for x in c["velas_t"]} & furos                     # nenhum replay passa por um pregão com candle faltando


class _BancoFalso:
    def __init__(self):
        self.d = {}

    def cfg_ler(self, k):
        return self.d.get(k, {})

    def cfg_gravar(self, k, v):
        self.d[k] = v

    def cfg_apagar(self, k):
        self.d.pop(k, None)


def test_biblioteca_cresce_um_registro_por_cenario_e_partida_so_com_grafico_real():
    b = _BancoFalso()
    with pytest.raises(TD.SemCenarios):
        TD.escolher_corrida("longa", 1, banco=b)
    assert TD.escolher_corrida("longa", 1, banco=b, permitir_demo=True)["demo"]
    reais = []
    for s in (1, 2):
        c = TD.demo_corrida("longa", s)
        reais.append({**c, "id": f"REAL-{s}", "ticker": "PETR4", "demo": False})
    assert TD.salvar_corrida("longa", reais, banco=b) == 2
    assert TD.salvar_corrida("longa", reais[:1], banco=b) == 2                  # o mesmo cenário não entra duas vezes
    assert set(b.d) == {"tb_corrida_longa", "tb_cc|longa|REAL-1", "tb_cc|longa|REAL-2"}
    assert {x["id"] for x in TD.listar_corrida("longa", banco=b)} == {"REAL-1", "REAL-2"}
    c = TD.escolher_corrida("longa", 7, banco=b)
    assert not c["demo"] and c["id"] in ("REAL-1", "REAL-2")
    assert TD.resolver({"id": c["id"], "tf": "1d", "corrida": "longa"}, banco=b)["id"] == c["id"]


def test_preparar_baixa_os_dois_tempos_graficos_e_guarda_so_os_novos():
    b = _BancoFalso()
    dv = _df("2023-01-02", 900, 1440, 1)
    dv.index = dv.index.normalize()
    ds = _df("2026-06-01", 7 * 90, 60, 7)
    dv = dv[dv.index < ds.index[0].normalize()]
    pedidos = []

    def baixar(cod, per, iv):
        pedidos.append((cod, per, iv))
        return {"df": dv if iv == "1d" else ds}
    rel = TD.preparar_corrida("longa", baixar, "2026-11-19T19:00", ativos=("PETR4",), por_ativo=1, banco=b)
    assert ("PETR4", "10y", "1d") in pedidos and ("PETR4", "2y", "60m") in pedidos
    assert rel["novos"] == 1 and rel["total"] == 1
    rel2 = TD.preparar_corrida("longa", baixar, "2026-11-20T19:00", ativos=("PETR4",), por_ativo=1, banco=b)
    assert rel2["total"] == 1 + rel2["novos"]                                    # roda de novo: só entram trechos que ainda não existem


def test_job_diario_prepara_e_guarda_no_banco(monkeypatch):
    import trader_cenarios_job as JOB
    from test_trader_mesa import banco_isolado
    dv = _df("2023-01-02", 900, 1440, 1)
    dv.index = dv.index.normalize()
    ds = _df("2026-06-01", 7 * 90, 60, 7)
    dv = dv[dv.index < ds.index[0].normalize()]
    monkeypatch.setattr(JOB, "baixador", lambda: (lambda cod, per, iv: {"df": dv if iv == "1d" else ds}))
    monkeypatch.setattr(TD, "ATIVOS", ("PETR4",))
    monkeypatch.setattr(TD.preparar_corrida, "__defaults__", (("PETR4",), 1, None))
    with banco_isolado():
        assert JOB.main(["longa"]) == 0
        assert len(TD.listar_corrida("longa")) == 1
        assert not TD.escolher_corrida("longa", 3)["demo"]


def test_candle_menor_faltando_so_vale_se_o_candle_do_grafico_bate_com_o_real():
    idx = pd.date_range("2024-03-04 10:00", periods=12, freq="5min")
    sub = pd.DataFrame({"Open": [10.0 + i * 0.01 for i in range(12)], "High": [10.2] + [10.1] * 11, "Low": [9.9] * 12,
                        "Close": [10.0 + i * 0.01 for i in range(12)], "Volume": [1000.0] * 12}, index=idx)
    furado = sub.drop(idx[5])                                                 # 10:25 não veio do Yahoo (máxima e mínima estão em outros minutos)
    real = pd.DataFrame({"Open": [10.0], "High": [10.2], "Low": [9.9], "Close": [10.11], "Volume": [12000.0]}, index=[pd.Timestamp("2024-03-04 10:00")])
    assert TD._velas_completas(furado, "1h", "5m", real)[0] is not None       # igual ao candle real de 1 h: entra (sem inventar o 10:25)
    diferente = real.assign(High=[10.6])                                     # a máxima real aconteceu justo no minuto que faltou: fica de fora
    assert TD._velas_completas(furado, "1h", "5m", diferente)[0] is None
    assert TD._velas_completas(furado, "1h", "5m", None)[0] is None
