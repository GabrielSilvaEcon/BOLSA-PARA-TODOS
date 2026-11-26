"""Partida corrida com quantidade livre (trader_qtd): teto de 5% do caixa, preço médio, execução na abertura do próximo candle, taxa, gap e perda máxima."""
import pytest

import trader_qtd as Q

CAP = 10_000.0          # capital da partida (5% de um caixa livre de T$ 200.000)


def k(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c, "v": 1000}


def ac(ordem, n_rev, tipo, **kw):
    return {"ordem": ordem, "n_rev": n_rev, "tipo": tipo, **kw}


PLANO = [k(10, 10.2, 9.9, 10.1)] * 3


def sim(candles, acoes, final=False, taxa=0.0):
    return Q.simular(candles, acoes, 10.0, CAP, final, taxa)


def test_capital_e_5_por_cento_do_caixa_livre():
    assert Q.capital_da_partida(200_000) == 10_000.0
    assert Q.capital_da_partida(-5) == 0.0


def test_mercado_executa_na_abertura_do_proximo_candle_e_nao_no_preco_passado():
    cand = [k(10, 10.5, 9.8, 10.4), k(10.6, 10.9, 10.5, 10.8)]
    st = sim(cand, [ac(1, 1, "mercado", direcao="alta", q=100)])          # enviada com 1 candle revelado (fechou 10,4)
    assert st["pos"]["entrada"] == 10.6 and st["pos"]["i_entrada"] == 1     # executou na abertura do candle seguinte
    st0 = sim(cand[:1], [ac(1, 1, "mercado", direcao="alta", q=100)])       # o próximo candle ainda não saiu: a ordem espera
    assert st0["pos"] is None and st0["mkt"]


def test_aumentar_posicao_faz_preco_medio_e_vender_parte_realiza():
    cand = [k(10, 10, 10, 10), k(12, 12, 12, 12), k(14, 14, 14, 14)]
    st = sim(cand, [ac(1, 0, "mercado", direcao="alta", q=100), ac(2, 1, "mercado", direcao="alta", q=100), ac(3, 2, "mercado", direcao="baixa", q=50)])
    assert st["pos"]["q"] == 150 and st["pos"]["entrada"] == pytest.approx(11.0)       # PM de 100 a 10 e 100 a 12
    assert st["trades"][0]["q"] == 50 and st["trades"][0]["pnl"] == pytest.approx(150.0)   # vendeu 50 a 14 com PM 11


def test_teto_do_capital_na_validacao():
    st = sim(PLANO[:1], [])
    maior = Q.validar({"tipo": "mercado", "direcao": "alta", "q": 1001}, st, 10.0, 1, 10, lambda d, c="preco": float(d[c]))
    assert maior["q"] == 1000 and maior["ajustada"]                         # pediu demais: entra com o máximo que cabe (nunca recusa por saldo)
    ok = Q.validar({"tipo": "mercado", "direcao": "alta", "q": 1000}, st, 10.0, 1, 10, lambda d, c="preco": float(d[c]))
    assert ok["q"] == 1000


def test_cinco_entradas_de_1_por_cento_ou_uma_de_5_e_depois_so_encerrando():
    pr = lambda d, c="preco": float(d[c])
    acoes = [ac(i, 0, "mercado", direcao="alta", q=200) for i in range(1, 6)]           # 5 × T$ 2.000 = T$ 10.000 (todo o capital)
    st = sim(PLANO[:1], acoes)
    assert st["pos"]["q"] == 1000
    with pytest.raises(Q.ErroQtd, match="todo aplicado"):
        Q.validar({"tipo": "mercado", "direcao": "alta", "q": 1}, st, 10.0, 1, 10, pr)
    st2 = sim(PLANO[:2], acoes + [ac(6, 1, "encerrar")])                                 # encerrou: o capital volta
    assert st2["pos"] is None and Q.max_qtd(st2, 10.1) > 900


def test_vender_comprado_reduz_e_nao_inverte():
    pr = lambda d, c="preco": float(d[c])
    st = sim(PLANO[:1], [ac(1, 0, "mercado", direcao="alta", q=100)])
    with pytest.raises(Q.ErroQtd, match="você tem 100 ações para vender"):
        Q.validar({"tipo": "mercado", "direcao": "baixa", "q": 150}, st, 10.1, 1, 10, pr)
    with pytest.raises(Q.ErroQtd, match="ordem a mercado"):
        Q.validar({"tipo": "limite", "direcao": "baixa", "q": 10, "preco": 11}, st, 10.1, 1, 10, pr)


def test_venda_a_descoberto_ganha_na_queda():
    cand = [k(10, 10, 10, 10), k(9, 9, 9, 9)]
    st = sim(cand, [ac(1, 0, "mercado", direcao="baixa", q=100), ac(2, 1, "encerrar")], final=True)
    assert st["trades"][0]["pnl"] == pytest.approx(100.0)


def test_taxa_da_b3_entra_no_resultado():
    cand = [k(10, 10, 10, 10), k(10, 10, 10, 10)]
    st = Q.simular(cand, [ac(1, 0, "mercado", direcao="alta", q=900), ac(2, 1, "encerrar")], 10.0, CAP, True, Q.TAXA_B3)
    assert st["trades"][0]["pnl"] == pytest.approx(-5.4)                  # 0,03% de T$ 9.000 na compra e na venda
    st2 = Q.simular(cand[:1], [ac(1, 0, "mercado", direcao="alta", q=1000)], 10.0, CAP, False, Q.TAXA_B3)
    assert st2["pos"]["q"] == 999                                          # com a taxa, 1.000 passa do capital: executa só o que cabe


def test_stop_com_gap_sai_na_abertura():
    cand = [k(10, 10, 10, 10), k(9.0, 9.1, 8.8, 8.9)]                      # abriu abaixo do stop de 9,5
    st = sim(cand, [ac(1, 0, "mercado", direcao="alta", q=100, stop=9.5)])
    assert st["trades"][0]["saida"] == 9.0 and st["trades"][0]["motivo"] == "stop"


def test_perda_nunca_passa_do_capital_e_bloqueia():
    cand = [k(10, 10, 10, 10), k(10, 10, 4, 5), k(0.5, 0.6, 0.4, 0.5)]
    st = sim(cand, [ac(1, 0, "mercado", direcao="alta", q=1000)])          # todo o capital comprado
    assert st["pos"]["q"] == 1000 and st["trades"] == []
    st2 = Q.simular([k(10, 10, 10, 10), k(10, 30, 10, 25)], [ac(1, 0, "mercado", direcao="baixa", q=1000)], 10.0, CAP, False, 0.0)
    assert st2["bloq"] and st2["trades"][0]["motivo"] == "limite"           # vendido: o preço dobrou e a perda chegou ao capital
    assert st2["trades"][0]["pnl"] == pytest.approx(-CAP)
    with pytest.raises(Q.ErroQtd, match="chegou ao capital"):
        Q.validar({"tipo": "mercado", "direcao": "alta", "q": 1}, st2, 25, 2, 10, lambda d, c="preco": float(d[c]))


def test_limite_so_executa_se_o_preco_chegar():
    cand = [k(10, 10.2, 9.8, 10), k(10, 10.1, 9.6, 9.7)]
    st = sim(cand, [ac(1, 0, "limite", direcao="alta", q=100, preco=9.5)])
    assert st["pos"] is None and st["pend"]
    st2 = sim(cand + [k(9.6, 9.6, 9.4, 9.5)], [ac(1, 0, "limite", direcao="alta", q=100, preco=9.5)])
    assert st2["pos"]["entrada"] == 9.5


def test_visao_traz_quantidade_preco_medio_exposicao_e_poder():
    st = sim(PLANO, [ac(1, 0, "mercado", direcao="alta", q=300)])
    v = Q.visao(st, 360, True, 3, 84, 1, 40, 200_000.0)
    assert v["qtd"] and v["posicao"]["q"] == 300 and v["exposicao"] == pytest.approx(3030.0)
    assert v["poder"] == pytest.approx(CAP - 3030.0) and v["pode_abrir"] and v["pode_reduzir"]
    assert v["limite"]["pct_pat"] == 5.0


def test_relatorio_taxa_de_acerto_payoff_e_maior_queda():
    cand = [k(10, 10, 10, 10), k(11, 11, 11, 11), k(9, 9, 9, 9), k(9, 9, 9, 9), k(12, 12, 12, 12), k(13, 13, 13, 13)]
    acoes = [ac(1, 0, "mercado", direcao="alta", q=100), ac(2, 1, "encerrar"),                 # compra 10, vende 11: +100
             ac(3, 2, "mercado", direcao="alta", q=100), ac(4, 3, "encerrar"),                 # compra 9, vende 9: 0
             ac(5, 4, "mercado", direcao="baixa", q=100), ac(6, 5, "encerrar")]                # vende 12, recompra 13: −100
    st = sim(cand, acoes, final=True)
    r = Q.relatorio(st)
    assert [t["pnl"] for t in st["trades"]] == [100.0, 0.0, -100.0]          # cada ordem executa na abertura do candle seguinte
    assert (r["n_ops"], r["acertos"], r["erros"], r["taxa_acerto"]) == (3, 1, 1, 33.3)
    assert r["payoff"] == 1.0                                                  # ganho médio 100 ÷ perda média 100
    assert r["maior_queda"] == 100.0 and r["maior_queda_pct"] == 1.0          # resultado da partida: pico de +100, depois volta a 0


def test_relatorio_sem_operacoes():
    r = Q.relatorio(sim(PLANO, [], final=True))
    assert r["n_ops"] == 0 and r["taxa_acerto"] is None and r["maior_queda"] == 0.0


def test_stop_movel_acompanha_a_alta_nunca_recua_e_executa():
    pr = lambda d, c="preco": float(d[c])
    cand = [k(10, 10, 10, 10), k(10, 11, 10, 11), k(11, 12, 11, 12), k(12, 12.2, 11.6, 11.7), k(11.4, 11.5, 11.0, 11.1)]
    base = [ac(1, 0, "mercado", direcao="alta", q=100), ac(2, 1, "stop_movel", dist=0.5)]
    st = sim(cand[:3], base)
    assert st["pos"]["stop"] == pytest.approx(11.5) and st["pos"]["trail"] == 0.5        # máxima 12 − 0,5
    st2 = sim(cand[:4], base)
    assert st2["pos"]["stop"] == pytest.approx(11.7)                                      # subiu com a máxima 12,2 e não recuou na queda
    st3 = sim(cand, base)
    assert st3["pos"] is None and st3["trades"][0]["motivo"] == "stop_movel" and st3["trades"][0]["saida"] == 11.4   # gap abaixo do stop: sai na abertura
    with pytest.raises(Q.ErroQtd, match="posição aberta"):
        Q.validar({"tipo": "stop_movel", "dist": 0.5}, sim(PLANO[:1], []), 10, 1, 10, pr)
    with pytest.raises(Q.ErroQtd, match="maior que zero"):
        Q.validar({"tipo": "stop_movel", "dist": 0}, st, 12, 3, 10, pr)


def test_stop_movel_na_venda_desce_com_a_minima():
    cand = [k(10, 10, 10, 10), k(10, 10, 9, 9), k(9, 9, 8, 8)]
    st = sim(cand, [ac(1, 0, "mercado", direcao="baixa", q=100), ac(2, 1, "stop_movel", dist=0.5)])
    assert st["pos"]["stop"] == pytest.approx(8.5)
