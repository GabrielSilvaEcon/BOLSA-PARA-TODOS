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


def test_solo_confirmar_ja_comeca_e_a_ordem_planejada_executa_no_primeiro_preco():
    p, cen, ref = _p()
    TB.salvar_estrategia(p, EU, _compra(ref), None, ref, 1010.0)
    assert p["fase"] == "replay" and p["t_fase"] == 1010.0                     # sem botão 'iniciar replay'
    (a,) = p["acoes"]
    assert (a["aid"], a["tipo"], a["q"], a["n_rev"]) == ("plano", "mercado", 100, 0)
    v = TB.visao(p, cen, 1010.0 + 3 * TB.cfg_de(p)["t_replay_s"] / TB.cfg_de(p)["n_replay"], EU)
    pos = v["mesa"]["posicao"]
    assert pos["q"] == 100 and pos["preco_entrada"] == cen["candles"][cen["n_analise"]]["o"] and pos["stop"] == round(ref * 0.97, 2)


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
    assert p["fase"] == "replay"
    assert [a["jogador"] for a in p["acoes"]] == [EU]                         # quem só observou não tem ordem automática


def test_tempo_acabou_quem_confirmou_entra_e_quem_nao_confirmou_aguarda():
    p, cen, ref = _p((EU, ANA), multi=True)
    TB.salvar_estrategia(p, EU, _compra(ref), None, ref, 1010.0)
    TB.avancar(p, 1000.0 + TB.T_ANALISE_S + 1)
    assert p["fase"] == "replay" and [a["jogador"] for a in p["acoes"]] == [EU]
    assert p["estrategias"]["1:" + ANA].get("sem_registro")


@pytest.mark.parametrize("ruim,msg", [({"stop": 999.0}, "stop"), ({"q": 10_000_000}, "cabem no máximo|capital"),
                                      ({"ordem": "limite", "preco": 999.0}, "limite"), ({"direcao": "talvez"}, "comprar ou vender")])
def test_boleta_validada_com_as_regras_do_jogo(ruim, msg):
    p, cen, ref = _p()
    with pytest.raises(TB.ErroTrader, match=msg):
        TB.salvar_estrategia(p, EU, {**_compra(ref), **ruim}, None, ref, 1010.0)
    assert p["fase"] == "analise" and not p.get("acoes")


def test_qualidade_sem_confianca():
    p, cen, ref = _p()
    TB.salvar_estrategia(p, EU, _compra(ref), None, ref, 1010.0)
    TB.avancar(p, 1010.0 + TB.cfg_de(p)["t_replay_s"] + 1, TD.por_id([cen]))
    r = p["resultados"]["1:" + EU]
    q = r["partes"]["q"]
    assert r["estrategia"]["confianca"] is None and q["confianca"] == 0.0
    assert r["partes"]["qual"] == pytest.approx((q["direcao"] + q["entrada"] + q["risco"]) / 3, abs=1e-3)
    linhas = dict(TB.explicar_mesa(r))
    assert "Comprar 100 ações" in linhas["Sua estratégia"] and "confiança" not in linhas["Qualidade"]


def test_componente_manda_a_boleta_e_o_servidor_converte():
    import trader_grafico as TG
    p, cen, ref = _p()
    est = {"seq": 1, "evento": "confirmar", "plano": {"direcao": "baixa", "ordem": "stop_entrada", "q": 50, "preco": round(ref * 0.99, 2),
                                                    "stop": round(ref * 1.02, 2), "alvo": round(ref * 0.95, 2)}}
    assert TG.processar(p, est, {}, EU, ref, 1010.0, cen=cen)
    a = p["acoes"][0]
    assert (a["tipo"], a["direcao"], a["q"], a["preco"]) == ("stop_entrada", "baixa", 50, round(ref * 0.99, 2))
    args = TG.args_mesa(TB.visao(p, cen, 1010.5, EU), p, {}, 1010.5)
    assert args["corrida"] and args["plano_cfg"]["capital"] == 10_000.0
