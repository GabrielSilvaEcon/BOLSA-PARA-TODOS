"""Partida corrida do Trade Battle no motor: uma rodada longa, quantidade livre, capital de 5% do caixa, ativo oculto até o fim."""
import pytest

import trader_battle as TB
import trader_dados as TD


def partida(formato="rapida", cap=10_000.0, pat=500_000.0):
    cen = TD.demo_corrida(formato, 11)
    sp = TB.CORRIDAS[formato]
    p = TB.nova_partida(cen, sp["tf"], ["eu@x.com"], 1000.0, apostas={"eu@x.com": {"stake": cap, "pat": pat}}, corrida=formato)
    return p, cen


def test_tres_duracoes_com_os_tempos_graficos_pedidos_e_historico_3x():
    assert {f: s["tf"] for f, s in TB.CORRIDAS.items()} == {"rapida": "5m", "intermediaria": "1h", "longa": "1d"}
    assert all(s["n_analise"] >= 300 for s in TB.CORRIDAS.values())          # 3x o histórico de antes (100 a 120 candles)
    for f in TB.CORRIDAS:
        p, cen = partida(f)
        cfg = TB.cfg_de(p)
        assert cfg["rodadas"] == 1 and cfg["qtd"] and cfg["n_replay"] == TB.CORRIDAS[f]["n_replay"]


def test_partida_inteira_com_quantidade_e_resultado_em_dinheiro():
    p, cen = partida()
    TB.salvar_estrategia(p, "eu@x.com", {"direcao": "alta", "tipo": "continuacao", "confianca": 3}, None, 0, 1001.0)
    TB.iniciar_replay(p, "eu@x.com", 1002.0)
    t = 1002.0 + 2 * TB.SEG_POR_CANDLE + 0.1                                    # 2 candles revelados
    TB.registrar_acao(p, cen, "eu@x.com", {"aid": "a1", "tipo": "mercado", "direcao": "alta", "q": 100}, t)
    with pytest.raises(TB.ErroTrader, match="cabem no máximo"):
        TB.registrar_acao(p, cen, "eu@x.com", {"aid": "a2", "tipo": "mercado", "direcao": "alta", "q": 10_000}, t)
    v = TB.visao(p, cen, t + 3 * TB.SEG_POR_CANDLE, "eu@x.com")
    assert v["mesa"]["qtd"] and v["mesa"]["posicao"]["q"] == 100 and v["oculto"] and v["ticker"] == "Ativo oculto"
    fim = 1002.0 + TB.cfg_de(p)["t_replay_s"] + 1
    TB.avancar(p, fim, TD.por_id([cen]))
    assert p["fase"] == "resultado"
    res = p["resultados"]["1:eu@x.com"]
    assert res["qtd"] and res["fin"]["n_ops"] == 1 and res["fin"]["aposta"] == 10_000.0
    TB.proxima_rodada(p, fim + 1)
    assert p["fase"] == "fim"
    vf = TB.visao(p, cen, fim + 2, "eu@x.com")
    assert not vf["oculto"] and vf["revelado"]["ticker"] == "DEMO3" and vf["revelado"]["de"]


def test_partidas_antigas_continuam_com_a_aposta_fixa():
    cen = TD.demo_cenario("15m", 3, b24=True)
    p = TB.nova_partida(cen, "15m", ["eu@x.com"], 1000.0, formato="rapida")
    assert not TB.qtd_de(p) and TB.cfg_de(p)["rodadas"] == 3


def test_cenario_de_outra_duracao_e_recusado():
    cen = TD.demo_corrida("longa", 1)
    with pytest.raises(TB.ErroTrader):
        TB.nova_partida(cen, "5m", ["eu@x.com"], 0.0, corrida="rapida")


def test_sala_online_corrida_capital_5_por_cento_do_caixa_e_resultado_volta_para_a_carteira():
    import trader_online_dados as OL
    from test_trader_mesa import EMAILS, TS, _contas, banco_isolado, livro
    with banco_isolado():
        _contas()
        with livro(pat=300_000.0, caixa=200_000.0) as lanc:
            r = OL.criar_sala(EMAILS[0], "15m", TS, corrida="rapida")
            OL.entrar_na_sala(EMAILS[1], r["codigo"], TS + 1)
            OL.iniciar(r["id"], EMAILS[0], TS + 2)
            v = OL.ler(r["id"], EMAILS[0], TS + 3)["v"]
            assert (v["motor"], v["formato"], v["rodadas"], v["tf"]) == (2, "rapida", 1, "5m") and v["ticker"] == "Ativo oculto"
            d = OL._row(r["id"])["dados"]
            assert d["p"]["stakes"]["1:" + EMAILS[0]]["stake"] == 10_000.0            # 5% de T$ 200.000 de caixa livre
    with banco_isolado():
        _contas()
        with livro(pat=300_000.0, caixa=1_000.0):
            with pytest.raises(OL.ErroSala, match="pelo menos"):
                OL.criar_sala(EMAILS[0], "15m", TS, corrida="rapida")


def test_resultado_da_partida_vira_um_lancamento_na_carteira():
    import trader_carteira as TCA
    from test_trader_mesa import livro
    p, cen = partida()
    p["apostas"] = {"eu@x.com": {"stake": 10_000.0, "pat": 500_000.0, "conta": "c1"}}
    TB.salvar_estrategia(p, "eu@x.com", {"direcao": "alta", "tipo": "continuacao", "confianca": 3}, None, 0, 1001.0)
    TB.iniciar_replay(p, "eu@x.com", 1002.0)
    TB.registrar_acao(p, cen, "eu@x.com", {"aid": "a1", "tipo": "mercado", "direcao": "alta", "q": 300}, 1002.0 + 0.1)
    TB.avancar(p, 1002.0 + TB.cfg_de(p)["t_replay_s"] + 1, TD.por_id([cen]))
    pnl = p["resultados"]["1:eu@x.com"]["fin"]["pnl"]
    with livro() as lanc:
        assert TCA.liquidar(p) == (1 if pnl else 0)
        assert TCA.liquidar(p) == 0                                              # nunca lança duas vezes
        if pnl:
            (chave, l), = lanc.items()
            assert chave == f"trader:{p['id']}:1:eu@x.com" and l["valor"] == pnl and "partida" in l["desc"]


def _fim_com(trades_fn, est=None):
    p, cen = partida()
    TB.salvar_estrategia(p, "eu@x.com", est or {"direcao": "alta", "tipo": "continuacao", "confianca": 5}, None, 0, 1001.0)
    TB.iniciar_replay(p, "eu@x.com", 1002.0)
    trades_fn(p, cen)
    TB.avancar(p, 1002.0 + TB.cfg_de(p)["t_replay_s"] + 1, TD.por_id([cen]))
    return p["resultados"]["1:eu@x.com"]


def test_pontos_da_partida_70_por_cento_resultado_e_30_qualidade():
    r = _fim_com(lambda p, cen: TB.registrar_acao(p, cen, "eu@x.com", {"aid": "a", "tipo": "mercado", "direcao": "alta", "q": 200}, 1002.1))
    pt = r["partes"]
    assert pt["peso_res"] == 0.7
    assert r["pontos"] == pytest.approx(max(-100, min(100, 0.7 * pt["res"] + 0.3 * pt["qual"] * 100)), abs=0.11)
    assert 0 <= r["qualidade_nota"] <= 100
    assert any(t == "Pontos" and "70%" in x for t, x in TB.explicar_mesa(r))


def test_sem_operar_0_ponto_mas_a_leitura_tem_nota_de_qualidade():
    r = _fim_com(lambda p, cen: None)
    assert r["pontos"] == 0.0 and r["qualidade_nota"] is not None
    assert any(t == "Qualidade" for t, _ in TB.explicar_mesa(r))


def test_lucro_pesa_mais_que_a_qualidade():
    # mesma qualidade, resultados opostos: quem lucrou fica à frente mesmo com nota de qualidade menor
    import trader_battle as T
    rep = TD.demo_corrida("rapida", 11)
    cen_r = {**rep, "candles": rep["candles"]}
    est = {"direcao": "alta", "tipo": "continuacao", "confianca": 1}
    ganha = [{"direcao": "alta", "entrada": 10.0, "saida": 10.4, "i_exc": 0, "i_saida": 3, "ret": 0.02, "com_stop": False}]
    perde = [{"direcao": "alta", "entrada": 10.0, "saida": 9.6, "i_exc": 0, "i_saida": 3, "ret": -0.02, "com_stop": True}]
    assert T.avaliar_corrida(cen_r, est, ganha)["pontos"] > T.avaliar_corrida(cen_r, est, perde)["pontos"]


def test_placar_guarda_lucro_retorno_qualidade_e_ranking_tem_as_tres_visoes():
    import jogos as J
    docs = {}
    partidas = {"a@x.com": [(500.0, 5.0, 80), (300.0, 3.0, 70), (-100.0, -1.0, 60)],      # lucro alto, qualidade média 70
                "b@x.com": [(50.0, 9.0, 95), (40.0, 8.0, 90), (30.0, 7.0, 85)],            # capital pequeno: lucro baixo, retorno e qualidade altos
                "c@x.com": [(900.0, 4.0, 40)]}                                              # só 1 partida: fica fora das médias
    for em, lista in partidas.items():
        d = J.vazio()
        for i, (lc, rt, ql) in enumerate(lista):
            d, ok = J.registrar_trade(d, f"{em}-{i}", 10, 1, "rapida", None, 1, "2026-11-19 10:00", em.split("@")[0], lucro=lc, retorno=rt, qualidade=ql)
            assert ok
        d, ok = J.registrar_trade(d, f"{em}-0", 10, 1, "rapida", None, 1, "x", lucro=999, retorno=9, qualidade=9)
        assert not ok                                                                       # a mesma partida não soma duas vezes
        docs[em] = d
    linhas = [{"email": e, "dados": d} for e, d in docs.items()]
    luc = J.montar_ranking(J.TRADE, linhas, metrica="lucro")["linhas"]
    assert [x["apelido"] for x in luc] == ["c", "a", "b"] and luc[1]["valor"] == 700.0
    ret = J.montar_ranking(J.TRADE, linhas, metrica="retorno")["linhas"]
    assert [x["apelido"] for x in ret] == ["b", "a"] and ret[0]["valor"] == 8.0           # média; "c" tem só 1 partida
    qual = J.montar_ranking(J.TRADE, linhas, metrica="qualidade")["linhas"]
    assert [(x["apelido"], x["valor"]) for x in qual] == [("b", 90.0), ("a", 70.0)]


def test_placar_antigo_sem_os_campos_novos_continua_valido():
    import jogos as J
    antigo = {"apelido": "x", "trade": {"pts": 50, "partidas": 2, "vitorias": 1, "melhor": 30, "ids": ["p1", "p2"], "hist": []}}
    d = J.sanear(antigo)
    assert d["trade"]["pts"] == 50 and d["trade"]["n_ret"] == 0 and d["trade"]["lucro"] == 0.0
    assert J.montar_ranking(J.TRADE, [{"email": "x@x.com", "dados": antigo}], metrica="lucro")["total"] == 0
    assert J.montar_ranking(J.TRADE, [{"email": "x@x.com", "dados": antigo}])["total"] == 1
