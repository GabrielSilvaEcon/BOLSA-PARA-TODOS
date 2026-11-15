"""Trader Battle · toda operação se conclui (tocando ou não a entrada) e o jogador pode encerrá-la quando quiser. Sem rede, sem Streamlit."""
from datetime import datetime, timedelta

import pytest

import trader_battle as TB

T0 = 1_000_000.0


def _cenario(tf="15m", fn_replay=None, base=10.0):
    """Cenário válido: histórico plano em `base` e replay dado por fn_replay(i) -> (o, h, l, c) (i = índice dentro do replay inteiro)."""
    cfg = TB.TIMEFRAMES[tf]
    na, nr = cfg["n_analise"], cfg["n_replay"]
    cand = []
    for i in range(na + TB.RODADAS * nr):
        if i < na:
            o, h, l, c = base, base + 0.05, base - 0.05, base
        else:
            o, h, l, c = fn_replay(i - na)
        cand.append({"t": (datetime(2026, 1, 5, 10, 0) + timedelta(minutes=cfg["passo_min"] * i)).isoformat(), "o": o, "h": h, "l": l, "c": c, "v": 1000})
    return {"id": "c1", "ticker": "TEST3", "tf": tf, "n_analise": na, "candles": cand, "demo": True}


def _sobe(i):                       # sobe 0,02 por candle sem nunca voltar à faixa de 9,50
    o = 10.0 + 0.02 * i
    return o, o + 0.03, o - 0.01, o + 0.02


def _est(direcao="alta", entrada=9.5, stop=9.0, alvo=12.0):
    return {"direcao": direcao, "tipo": "continuacao", "confianca": 3, "entrada": entrada, "stop": stop, "alvo": alvo}


def _rep(c, r=1):
    ini = TB.inicio_rodada(c, r)
    return c["candles"][ini:ini + TB._nr(c)]


def test_entrada_nunca_tocada_entra_a_mercado_e_tem_resultado():
    c = _cenario(fn_replay=_sobe)
    op = TB.simular_operacao(_rep(c), _est())
    assert op["executada"] and op["tipo_entrada"] == "mercado"
    assert op["preco_entrada"] == pytest.approx(10.0 + 0.02 * 6)          # abertura do candle depois da espera (25% de 24 = 6)
    assert op["por"] == "fim" and op["saida"] == _rep(c)[-1]["c"] and op["r"] > 0


def test_entrada_tocada_executa_no_preco_limite():
    c = _cenario(fn_replay=lambda i: (10.0, 10.05, 9.4, 9.9) if i == 2 else (10.0, 10.05, 9.95, 10.0))
    op = TB.simular_operacao(_rep(c), _est(entrada=9.5, stop=9.0, alvo=12.0))
    assert op["tipo_entrada"] == "limite" and op["preco_entrada"] == 9.5 and op["candle_entrada"] == 2


def test_stop_e_alvo_continuam_valendo():
    c = _cenario(fn_replay=lambda i: (10.0, 10.05, 8.0, 9.0) if i == 10 else (10.0, 10.05, 9.95, 10.0))
    op = TB.simular_operacao(_rep(c), _est(entrada=10.0, stop=9.0, alvo=12.0))
    assert op["por"] == "stop" and op["saida"] == 9.0 and op["r"] == pytest.approx(-1.0)
    c = _cenario(fn_replay=lambda i: (10.0, 12.5, 9.95, 12.2) if i == 10 else (10.0, 10.05, 9.95, 10.0))
    op = TB.simular_operacao(_rep(c), _est(entrada=10.0, stop=9.0, alvo=12.0))
    assert op["por"] == "alvo" and op["saida"] == 12.0 and op["r"] == pytest.approx(2.0)


def test_venda_a_mercado_lucra_quando_o_preco_cai():
    c = _cenario(fn_replay=lambda i: (10.0 - 0.02 * i, 10.0 - 0.02 * i + 0.01, 10.0 - 0.02 * i - 0.03, 10.0 - 0.02 * i - 0.02))
    op = TB.simular_operacao(_rep(c), _est("baixa", entrada=10.5, stop=11.0, alvo=8.0))
    assert op["executada"] and op["tipo_entrada"] == "mercado" and op["r"] > 0


def test_encerramento_manual_sai_no_fechamento_do_ultimo_candle_revelado():
    c = _cenario(fn_replay=_sobe)
    rep = _rep(c)
    op = TB.simular_operacao(rep, _est(), ate=10)
    assert op["por"] == "manual" and op["saida"] == rep[9]["c"] and op["candle_saida"] == 9


def test_encerrar_antes_da_ordem_executar_cancela_sem_lucro_nem_prejuizo():
    c = _cenario(fn_replay=_sobe)
    op = TB.simular_operacao(_rep(c), _est(), ate=3)
    assert not op["executada"] and op["por"] == "cancelada" and op["r"] == 0.0


def _partida(c, est, apostas=None):
    p = TB.nova_partida(c, c["tf"], ["ana"], T0, apostas=apostas or {"ana": {"stake": 1000.0, "pat": 100000.0}})
    TB.salvar_estrategia(p, "ana", est, None, 10.0, T0 + 1)
    TB.iniciar_replay(p, "ana", T0 + 2)
    return p


def test_fluxo_completo_com_encerramento_manual_e_financeiro():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c, _est())
    t_replay = p["t_fase"]
    passo = TB.T_REPLAY_S / TB.TIMEFRAMES["15m"]["n_replay"]
    with pytest.raises(TB.ErroTrader):                                   # nada revelado ainda
        TB.encerrar_operacao(p, c, "ana", t_replay + 0.1)
    agora = t_replay + passo * 10 + 0.01                                 # 10 candles revelados
    v = TB.visao(p, c, agora, "ana")
    assert v["operacao"]["estado"] == "aberta" and v["operacao"]["encerravel"] and v["propria"]["tipo"] == "mercado"
    TB.encerrar_operacao(p, c, "ana", agora)
    TB.encerrar_operacao(p, c, "ana", agora + 3)                          # repetir é inofensivo
    assert p["encerradas"]["1:ana"] == 10
    v = TB.visao(p, c, agora + 1, "ana")
    assert v["operacao"]["estado"] == "fechada" and v["operacao"]["por"] == "manual" and not v["operacao"]["encerravel"]
    TB.avancar(p, t_replay + TB.T_REPLAY_S + 1, {c["id"]: c})            # replay acaba; o resultado respeita o encerramento manual
    r = p["resultados"]["1:ana"]
    rep = _rep(c)
    assert r["operacao"]["saida"] == rep[9]["c"]
    esperado = round(1000.0 * (rep[9]["c"] - r["operacao"]["preco_entrada"]) / r["operacao"]["preco_entrada"], 2)
    assert r["fin"]["operou"] and r["fin"]["pnl"] == esperado and esperado > 0


def test_operacao_que_nao_toca_entrada_agora_mexe_no_patrimonio():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c, _est())
    TB.avancar(p, p["t_fase"] + TB.T_REPLAY_S + 1, {c["id"]: c})
    fin = p["resultados"]["1:ana"]["fin"]
    assert fin["operou"] and fin["pnl"] > 0


def test_nao_encerra_depois_do_stop_nem_fora_do_replay():
    c = _cenario(fn_replay=lambda i: (10.0, 10.05, 8.0, 9.0) if i == 8 else (10.0, 10.05, 9.95, 10.0))
    p = _partida(c, _est(entrada=10.0, stop=9.0, alvo=12.0))
    passo = TB.T_REPLAY_S / TB.TIMEFRAMES["15m"]["n_replay"]
    with pytest.raises(TB.ErroTrader, match="stop"):
        TB.encerrar_operacao(p, c, "ana", p["t_fase"] + passo * 12)
    TB.avancar(p, p["t_fase"] + TB.T_REPLAY_S + 1, {c["id"]: c})
    with pytest.raises(TB.ErroTrader):
        TB.encerrar_operacao(p, c, "ana", p["t_fase"] + 1)


def test_aguardar_nao_tem_operacao_para_encerrar():
    c = _cenario(fn_replay=_sobe)
    p = TB.nova_partida(c, "15m", ["ana"], T0)
    TB.salvar_estrategia(p, "ana", {"direcao": "lateral", "tipo": "aguardar", "confianca": 3}, None, 10.0, T0 + 1)
    TB.iniciar_replay(p, "ana", T0 + 2)
    with pytest.raises(TB.ErroTrader):
        TB.encerrar_operacao(p, c, "ana", p["t_fase"] + 10)
    assert TB.visao(p, c, p["t_fase"] + 10, "ana")["operacao"] is None


def test_adversario_so_ve_entrada_ja_executada_sem_vazar_o_futuro():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c, _est())
    # antes da espera acabar, a entrada (nunca tocada) ainda não foi executada: nada a mostrar
    assert TB.entrada_executada(p, c, p["t_fase"] + 1, 1, "ana") is None
