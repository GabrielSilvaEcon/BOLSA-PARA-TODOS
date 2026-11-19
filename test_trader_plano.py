"""Partida corrida: a estratégia é a boleta do início (pop-up), confirmada UMA vez; solo começa sozinho; em sala, só quando todos confirmam."""
import pytest

import trader_battle as TB
import trader_dados as TD

EU, ANA = "eu@x.com", "ana@x.com"


def _p(jogs=(EU,), multi=False):
    cen = TD.demo_corrida("rapida", 4)
    p = TB.nova_partida(cen, cen["tf"], list(jogs), 1000.0, multi=multi, corrida="rapida",
                        apostas={j: {"stake": 10_000.0, "pat": 200_000.0} for j in jogs})
    return p, cen, cen["candles"][cen["n_analise"] - 1]["c"]


def _compra(ref, q=100, **kw):
    return {"direcao": "alta", "ordem": "mercado", "q": q, "stop": round(ref * 0.97, 2), "alvo": round(ref * 1.05, 2), **kw}


def test_solo_confirmar_ja_comeca_e_nenhuma_ordem_nasce_da_estrategia():
    p, cen, ref = _p()
    TB.salvar_estrategia(p, EU, _compra(ref), None, ref, 1010.0)               # mesmo que a tela mande campos de ordem, viram só a leitura
    assert p["fase"] == "replay" and p["t_fase"] == 1010.0                     # sem botão 'iniciar replay'
    assert not p.get("acoes") and p["estrategias"]["1:" + EU]["direcao"] == "alta"
    v = TB.visao(p, cen, 1010.0 + 3 * TB.cfg_de(p)["t_replay_s"] / TB.cfg_de(p)["n_replay"], EU)
    assert v["mesa"]["posicao"] is None                                        # comprar e vender só com o gráfico andando


def test_estrategia_so_uma_vez_por_partida():
    p, cen, ref = _p((EU, ANA), multi=True)
    TB.salvar_estrategia(p, EU, _compra(ref), None, ref, 1010.0)
    with pytest.raises(TB.ErroTrader, match="já foi confirmada"):
        TB.salvar_estrategia(p, EU, _compra(ref, q=5), None, ref, 1011.0)


def test_sala_espera_todos_confirmarem():
    p, cen, ref = _p((EU, ANA), multi=True)
    TB.salvar_estrategia(p, EU, _compra(ref), None, ref, 1010.0)
    assert p["fase"] == "analise"
    assert TB.visao(p, cen, 1011.0, EU)["confirmados"] == {"eu": True, "n": 1, "total": 2}
    assert TB.visao(p, cen, 1011.0, ANA)["confirmados"]["eu"] is False
    TB.salvar_estrategia(p, ANA, {"direcao": None, "tipo": "aguardar"}, None, ref, 1020.0)   # "só observar"
    assert p["fase"] == "replay" and not p.get("acoes")


def test_tempo_acabou_quem_confirmou_entra_e_quem_nao_confirmou_aguarda():
    p, cen, ref = _p((EU, ANA), multi=True)
    TB.salvar_estrategia(p, EU, _compra(ref), None, ref, 1010.0)
    TB.avancar(p, 1000.0 + TB.T_ANALISE_S + 1)
    assert p["fase"] == "replay" and not p.get("acoes")
    assert p["estrategias"]["1:" + ANA].get("sem_registro")


def test_estrategia_invalida_e_recusada():
    p, cen, ref = _p()
    with pytest.raises(TB.ErroTrader, match="Subir, Cair ou Aguardar"):
        TB.salvar_estrategia(p, EU, {"direcao": "talvez"}, None, ref, 1010.0)
    assert p["fase"] == "analise"


def test_qualidade_sem_confianca():
    import trader_grafico as TG
    p, cen, ref = _p()
    TB.salvar_estrategia(p, EU, _compra(ref), None, ref, 1010.0)
    t = 1010.0 + 2 * TB.cfg_de(p)["t_replay_s"] / TB.cfg_de(p)["n_replay"]
    TG.processar(p, {"seq": 1, "evento": "acao", "dados": {"aid": "c", "tipo": "mercado", "direcao": "alta", "q": 100}}, {}, EU, ref, t, cen=cen)
    TB.avancar(p, 1010.0 + TB.cfg_de(p)["t_replay_s"] + 1, TD.por_id([cen]))
    r = p["resultados"]["1:" + EU]
    q = r["partes"]["q"]
    assert r["estrategia"]["confianca"] is None and q["confianca"] == 0.0
    assert r["partes"]["qual"] == pytest.approx((q["direcao"] + q["entrada"] + q["risco"]) / 3, abs=1e-3)
    linhas = dict(TB.explicar_mesa(r))
    assert "subir" in linhas["Sua estratégia"] and "confiança" not in linhas["Qualidade"]


def test_componente_manda_a_leitura_e_o_servidor_converte():
    import trader_grafico as TG
    p, cen, ref = _p()
    est = {"seq": 1, "evento": "confirmar", "plano": {"direcao": "baixa", "tipo": "continuacao"}}
    assert TG.processar(p, est, {}, EU, ref, 1010.0, cen=cen)
    assert p["estrategias"]["1:" + EU]["direcao"] == "baixa" and p["fase"] == "replay" and not p.get("acoes")
    args = TG.args_mesa(TB.visao(p, cen, 1010.5, EU), p, {}, 1010.5)
    assert args["corrida"]


def test_comprar_e_stop_movel_pela_tela_levam_quantidade_e_distancia():
    # caminho real da tela: componente -> TG.processar -> motor (antes a quantidade e a distância eram descartadas no caminho)
    import trader_grafico as TG
    p, cen, ref = _p()
    TB.salvar_estrategia(p, EU, {"direcao": None, "tipo": "aguardar"}, None, ref, 1010.0)
    est = {}
    t = 1010.0 + 2 * TB.cfg_de(p)["t_replay_s"] / TB.cfg_de(p)["n_replay"]
    TG.processar(p, {"seq": 1, "evento": "acao", "dados": {"aid": "c1", "tipo": "mercado", "direcao": "alta", "q": 120}}, est, EU, ref, t, cen=cen)
    assert est.get("erro", "") == "" and p["acoes"][-1]["q"] == 120
    t2 = t + 3 * TB.cfg_de(p)["t_replay_s"] / TB.cfg_de(p)["n_replay"]
    TG.processar(p, {"seq": 2, "evento": "acao", "dados": {"aid": "c2", "tipo": "stop_movel", "dist": 0.3}}, est, EU, ref, t2, cen=cen)
    assert est.get("erro", "") == "" and p["acoes"][-1]["dist"] == 0.3


def test_lote_e_10_por_cento_do_capital_fixo_na_partida():
    p, cen, ref = _p()                                                         # capital T$ 10.000
    L = TB.lote_de(p, EU, ref)
    assert L == int(1000 // (ref * (1 + TB.cfg_de(p)["taxa"])))
    assert 10 * L * ref <= 10_000 and 11 * L * ref * (1 + TB.cfg_de(p)["taxa"]) > 10_000   # cabem 10 lotes, não 11
    assert TB.lote_de(p, EU, 999_999.0) == 1                                  # ação cara: lote mínimo de 1 ação
