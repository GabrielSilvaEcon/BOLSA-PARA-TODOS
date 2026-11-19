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
