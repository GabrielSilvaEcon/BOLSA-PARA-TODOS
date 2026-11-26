"""Trader Battle · MESA DE OPERAÇÕES (motor 2). Sem rede, sem Streamlit. Etapa 1: ordens, pontuação, financeiro, multiplayer, relógio, compatibilidade."""
from datetime import datetime, timedelta

import pytest

import trader_battle as TB

T0 = 1_000_000.0
NR = TB.N_REPLAY_MESA


# ------------------------------------------------------------------ ferramentas
def K(o, h=None, l=None, c=None):
    """Candle de teste: K(10) é um candle plano em 10; K(10, 10.5, 9.8, 10.2) é OHLC completo."""
    c = o if c is None else c
    return {"t": "2026-01-05T10:00", "o": o, "h": max(o, c) if h is None else h, "l": min(o, c) if l is None else l, "c": c, "v": 1000.0}


def plano(n=NR, px=10.0):
    return [K(px) for _ in range(n)]


def A(tipo, n_rev, ordem, jog="ana", **kw):
    """Ação já registrada (como ficaria em p['acoes'])."""
    return {"aid": f"{jog}{ordem}", "jogador": jog, "rodada": 1, "tipo": tipo, "n_rev": n_rev, "ordem": ordem, "t": 0.0, **kw}


def sim(cand, acoes, ref=10.0, final=False, jog="ana"):
    return TB.simular_jogador(cand, [a for a in acoes if a["jogador"] == jog], ref, final)


def _cenario(tf="15m", fn_replay=None, base=10.0, tam_bloco=None):
    """Cenário válido: histórico plano em `base`; replay dado por fn_replay(i) -> (o, h, l, c). Tamanho = o do formato novo (24 candles × 10 blocos)."""
    cfg = TB.TIMEFRAMES[tf]
    na = cfg["n_analise"]
    cand = []
    for i in range(na + TB.RODADAS * (tam_bloco or NR)):
        o, h, l, c = (base, base + 0.05, base - 0.05, base) if i < na else fn_replay(i - na)
        cand.append({"t": (datetime(2026, 1, 5, 10, 0) + timedelta(minutes=cfg["passo_min"] * i)).isoformat(), "o": o, "h": h, "l": l, "c": c, "v": 1000})
    return {"id": "m1", "ticker": "TEST3", "tf": tf, "n_analise": na, "candles": cand, "demo": True}


def _plano_flat(i):
    return 10.0, 10.05, 9.95, 10.0


# ------------------------------------------------------------------ 1. ordem a mercado
def test_mercado_compra_executa_no_fechamento_do_ultimo_candle_revelado():
    cand = [K(10.0, 10.3, 9.9, 10.2), K(10.2, 10.6, 10.1, 10.5), K(10.5, 10.9, 10.4, 10.8)]
    s = sim(cand, [A("mercado", 2, 1, direcao="alta")])                    # 2 candles revelados: fecha em 10,5
    assert s["pos"]["entrada"] == 10.5 and s["pos"]["tipo_entrada"] == "mercado" and s["pos"]["i_entrada"] == 1
    s = sim(cand, [A("mercado", 0, 1, direcao="alta")], ref=9.9)           # nada revelado: usa o último preço visível (referência)
    assert s["pos"]["entrada"] == 9.9


def test_mercado_venda_lucra_quando_o_preco_cai():
    cand = [K(10.0, 10.0, 9.0, 9.0)]
    s = sim(cand, [A("mercado", 0, 1, direcao="baixa")], final=True)
    assert s["trades"][0]["ret"] == pytest.approx(0.10) and s["trades"][0]["motivo"] == "fim"


# ------------------------------------------------------------------ 2. limite
def test_limite_de_compra_so_executa_quando_o_preco_toca_o_nivel():
    cand = [K(10.0, 10.1, 9.9, 10.0), K(10.0, 10.1, 9.4, 9.6), K(9.6)]
    s = sim(cand, [A("limite", 0, 1, direcao="alta", preco=9.5)])
    assert s["pos"] and s["pos"]["entrada"] == 9.5 and s["pos"]["i_entrada"] == 1 and s["pos"]["tipo_entrada"] == "limite"
    s = sim(cand[:1], [A("limite", 0, 1, direcao="alta", preco=9.5)])
    assert s["pos"] is None and s["pend"]["preco"] == 9.5                   # ainda esperando


def test_limite_de_venda_executa_acima_do_preco_atual():
    cand = [K(10.0, 10.6, 9.9, 10.4)]
    s = sim(cand, [A("limite", 0, 1, direcao="baixa", preco=10.5)])
    assert s["pos"]["entrada"] == 10.5 and s["pos"]["direcao"] == "baixa"


# ------------------------------------------------------------------ 3. stop de entrada
def test_stop_de_entrada_compra_acima_e_venda_abaixo():
    cand = [K(10.0, 10.2, 9.9, 10.1), K(10.1, 10.8, 10.0, 10.7)]
    s = sim(cand, [A("stop_entrada", 0, 1, direcao="alta", preco=10.5)])
    assert s["pos"]["entrada"] == 10.5 and s["pos"]["i_entrada"] == 1
    cand = [K(10.0, 10.1, 9.9, 10.0), K(10.0, 10.0, 9.2, 9.3)]
    s = sim(cand, [A("stop_entrada", 0, 1, direcao="baixa", preco=9.5)])
    assert s["pos"]["entrada"] == 9.5 and s["pos"]["direcao"] == "baixa"


def test_ordem_pendente_nao_executa_retroativamente():
    # o preço JÁ tinha tocado 9,5 no candle 0; a ordem só é enviada com 1 candle revelado → só vale do candle 1 em diante
    cand = [K(10.0, 10.0, 9.4, 9.8), K(9.8, 9.9, 9.7, 9.8), K(9.8)]
    s = sim(cand, [A("limite", 1, 1, direcao="alta", preco=9.5)])
    assert s["pos"] is None and s["pend"] is not None


# ------------------------------------------------------------------ 4. gaps
def test_gap_favoravel_na_entrada_executa_na_abertura():
    cand = [K(10.0), K(9.0, 9.3, 8.9, 9.2)]                                  # abre abaixo do limite de compra 9,5: entra na abertura (9,0)
    s = sim(cand, [A("limite", 1, 1, direcao="alta", preco=9.5)], ref=10.0)
    assert s["pos"]["entrada"] == 9.0
    cand = [K(10.0), K(11.0, 11.4, 10.9, 11.2)]                              # stop de entrada de compra em 10,5 e o preço abre acima: entra na abertura
    s = sim(cand, [A("stop_entrada", 1, 1, direcao="alta", preco=10.5)])
    assert s["pos"]["entrada"] == 11.0


def test_gap_desfavoravel_no_stop_sai_na_abertura_e_gap_alem_do_alvo_tambem():
    cand = [K(10.0), K(8.0, 8.2, 7.9, 8.1)]                                  # compra a mercado em 10 com stop 9: abre em 8 → sai em 8, não em 9
    s = sim(cand, [A("mercado", 1, 1, direcao="alta", stop=9.0)], final=True)
    assert s["trades"][0]["saida"] == 8.0 and s["trades"][0]["motivo"] == "stop"
    cand = [K(10.0), K(12.0, 12.5, 11.9, 12.2)]                              # alvo 11 e o preço abre em 12: sai em 12
    s = sim(cand, [A("mercado", 1, 1, direcao="alta", alvo=11.0)], final=True)
    assert s["trades"][0]["saida"] == 12.0 and s["trades"][0]["motivo"] == "alvo"
    cand = [K(10.0), K(12.0, 12.3, 11.0, 11.5)]                              # venda com stop 11: abre em 12 (acima) → sai em 12
    s = sim(cand, [A("mercado", 1, 1, direcao="baixa", stop=11.0)], final=True)
    assert s["trades"][0]["saida"] == 12.0 and s["trades"][0]["ret"] == pytest.approx(-0.2)


# ------------------------------------------------------------------ 5. stop e alvo no mesmo candle
def test_stop_e_alvo_no_mesmo_candle_prevalece_o_stop():
    cand = [K(10.0), K(10.0, 12.5, 8.5, 11.0)]
    s = sim(cand, [A("mercado", 1, 1, direcao="alta", stop=9.0, alvo=12.0)], final=True)
    assert s["trades"][0]["motivo"] == "stop" and s["trades"][0]["saida"] == 9.0
    s = sim(cand, [A("mercado", 1, 1, direcao="baixa", stop=12.0, alvo=8.0)], final=True)      # venda: idem
    assert s["trades"][0]["motivo"] == "stop" and s["trades"][0]["saida"] == 12.0


# ------------------------------------------------------------------ 6. OCO
def test_oco_quando_um_executa_o_outro_deixa_de_existir():
    cand = [K(10.0), K(10.0, 12.5, 9.95, 12.2), K(10.0, 10.5, 8.0, 8.5)]     # o alvo (12) executa; o stop (9) NÃO pode executar depois no candle 2
    s = sim(cand, [A("mercado", 1, 1, direcao="alta", stop=9.0, alvo=12.0)], final=True)
    assert len(s["trades"]) == 1 and s["trades"][0]["motivo"] == "alvo" and s["pos"] is None


# ------------------------------------------------------------------ 7. cancelamento
def test_cancelar_ordem_pendente_nao_gera_lucro_nem_prejuizo():
    cand = [K(10.0), K(10.0, 10.1, 9.0, 9.2), K(9.2)]
    s = sim(cand, [A("limite", 0, 1, direcao="alta", preco=9.5), A("cancelar", 1, 2, qual="entrada")], final=True)
    assert s["pos"] is None and s["pend"] is None and s["trades"] == []       # tocaria no candle 1, mas já tinha sido cancelada


def test_cancelar_stop_e_alvo_mantem_a_posicao():
    cand = [K(10.0), K(10.0), K(8.0, 8.1, 7.0, 7.5)]
    s = sim(cand, [A("mercado", 1, 1, direcao="alta", stop=9.0, alvo=12.0), A("cancelar", 2, 2, qual="todas")], final=False)
    assert s["pos"] is not None and s["pos"]["stop"] is None and s["pos"]["alvo"] is None and s["trades"] == []


# ------------------------------------------------------------------ 8. mover stop e alvo
def test_mover_stop_vale_a_partir_do_candle_seguinte_sem_efeito_retroativo():
    # o candle 1 tocou 9,5 (stop original 9,0 não é tocado). Depois subo o stop para 9,6 com 2 candles revelados: não pode "ter saído" no candle 1.
    cand = [K(10.0), K(10.0, 10.1, 9.5, 9.8), K(9.8, 9.9, 9.7, 9.8)]
    s = sim(cand, [A("mercado", 1, 1, direcao="alta", stop=9.0), A("mover_stop", 2, 2, preco=9.6)], final=True)
    assert s["trades"][0]["motivo"] == "fim"                                  # candle 2 ficou em 9,7+: stop 9,6 não tocado
    s = sim(cand[:2] + [K(9.8, 9.9, 9.5, 9.6)], [A("mercado", 1, 1, direcao="alta", stop=9.0), A("mover_stop", 2, 2, preco=9.6)], final=True)
    assert s["trades"][0]["motivo"] == "stop" and s["trades"][0]["saida"] == 9.6


def test_mover_alvo():
    cand = [K(10.0), K(10.0, 11.2, 9.9, 11.0)]
    s = sim(cand, [A("mercado", 1, 1, direcao="alta", alvo=12.0), A("mover_alvo", 1, 2, preco=11.0)], final=True)
    assert s["trades"][0]["motivo"] == "alvo" and s["trades"][0]["saida"] == 11.0


# ------------------------------------------------------------------ 9. encerramento manual
def test_encerrar_manual_sai_no_fechamento_do_ultimo_candle_revelado():
    cand = [K(10.0), K(10.0, 10.6, 9.9, 10.5), K(10.5, 11.5, 10.4, 11.4)]
    s = sim(cand, [A("mercado", 1, 1, direcao="alta"), A("encerrar", 2, 2)], final=True)
    t = s["trades"][0]
    assert t["motivo"] == "manual" and t["saida"] == 10.5 and t["i_saida"] == 1 and t["ret"] == pytest.approx(0.05) and s["pos"] is None


# ------------------------------------------------------------------ 10-12. várias operações, uma posição por vez, nova operação na hora
def test_varias_operacoes_na_mesma_rodada_e_nova_entrada_logo_apos_encerrar_inclusive_invertida():
    cand = [K(10.0), K(10.0, 10.6, 9.9, 10.5), K(10.5, 10.6, 9.4, 9.5), K(9.5, 9.6, 9.0, 9.0)]
    acoes = [A("mercado", 1, 1, direcao="alta"), A("encerrar", 2, 2), A("mercado", 2, 3, direcao="baixa")]   # encerra e vende NO MESMO instante (candle 2)
    s = sim(cand, acoes, final=True)
    assert [t["direcao"] for t in s["trades"]] == ["alta", "baixa"]
    assert s["trades"][0]["saida"] == 10.5 and s["trades"][1]["entrada"] == 10.5 and s["trades"][1]["saida"] == 9.0 and s["trades"][1]["motivo"] == "fim"


def test_segunda_posicao_simultanea_e_ignorada_pelo_simulador_e_recusada_no_registro():
    s = sim([K(10.0), K(10.0)], [A("mercado", 0, 1, direcao="alta"), A("mercado", 1, 2, direcao="baixa")])
    assert s["pos"]["direcao"] == "alta" and s["ignoradas"] == 1


def test_fim_da_rodada_fecha_no_ultimo_preco_e_pendentes_expiram():
    cand = [K(10.0), K(10.0, 10.5, 9.9, 10.4)]
    s = sim(cand, [A("mercado", 0, 1, direcao="alta"), ], final=True)
    assert s["trades"][0]["motivo"] == "fim" and s["trades"][0]["saida"] == 10.4
    s = sim(cand, [A("limite", 0, 1, direcao="alta", preco=5.0)], final=True)
    assert s["pend"] is None and s["trades"] == [] and s["pos"] is None


def test_jogadores_sao_independentes_no_simulador():
    cand = [K(10.0), K(10.0, 10.9, 9.5, 10.8)]
    acoes = [A("mercado", 0, 1, jog="ana", direcao="alta"), A("mercado", 0, 2, jog="bia", direcao="baixa", stop=10.5)]
    r = TB.simular_mesa(cand, acoes, 10.0, final=True, jogadores=["ana", "bia"])
    assert r["ana"]["trades"][0]["ret"] == pytest.approx(0.08) and r["bia"]["trades"][0]["motivo"] == "stop" and r["bia"]["trades"][0]["ret"] == pytest.approx(-0.05)


def test_simulacao_e_deterministica_e_nao_depende_da_ordem_da_lista():
    cand = [K(10.0), K(10.0, 10.6, 9.9, 10.5), K(10.5, 10.6, 9.4, 9.5)]
    acoes = [A("mercado", 1, 1, direcao="alta"), A("encerrar", 2, 2)]
    assert sim(cand, acoes, final=True) == sim(cand, list(reversed(acoes)), final=True) == sim(cand, acoes, final=True)


# ====================================================================================================================================
# ESTADO DA PARTIDA · registro de ações, financeiro, pontuação, privacidade, relógio, rodadas, compatibilidade
# ====================================================================================================================================
import json


def _sobe(i):
    o = 10.0 + 0.02 * i
    return o, o + 0.03, o - 0.01, o + 0.02


def _degraus(i):                                        # 10 → 15 (candle 4) → 22,5 (candle 8) → 33,75 (candle 12): cada degrau é +50%
    nivel = 10.0 * 1.5 ** (i // 4)
    ant = 10.0 * 1.5 ** ((i - 1) // 4) if i > 0 else 10.0
    return ant, max(ant, nivel), min(ant, nivel), nivel


EST = {"direcao": "alta", "tipo": "continuacao", "confianca": 3}


def _partida(c, jogs=("ana", "bia"), formato="normal", pat=100000.0, multi=True):
    ap = {j: {"stake": round(pat * 0.01, 2), "pat": pat, "conta": "c"} for j in jogs}
    p = TB.nova_partida(c, c["tf"], list(jogs), T0, multi=multi, apostas=ap, formato=formato)
    for j in jogs:
        TB.salvar_estrategia(p, j, dict(EST), None, 10.0, T0 + 1)
    if not multi:
        TB.iniciar_replay(p, jogs[0], T0 + 2)
    return p


def ag(p, k):
    """Instante do servidor em que exatamente k candles do replay estão revelados."""
    cfg = TB.cfg_de(p)
    return p["t_fase"] + cfg["t_replay_s"] / cfg["n_replay"] * k + 0.01


def op(p, c, jog, k, tipo, aid, **kw):
    return TB.registrar_acao(p, c, jog, {"tipo": tipo, "aid": aid, **kw}, ag(p, k))


def fim(p, c, folga=1.0):
    TB.avancar(p, p["t_fase"] + TB.cfg_de(p)["t_replay_s"] + folga, {c["id"]: c})


# ------------------------------------------------------------------ registro: campos, ordem, clique duplo, fase
def test_acao_registra_campos_e_o_servidor_decide_candles_ordem_e_hora():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    a, nova = TB.registrar_acao(p, c, "ana", {"tipo": "mercado", "direcao": "alta", "aid": "a1", "n_rev": 0, "ordem": 99, "t": 5}, ag(p, 5))
    assert nova and a["n_rev"] == 5 and a["ordem"] == 1 and a["t"] == ag(p, 5)           # o que o navegador mandou em n_rev/ordem/t é ignorado
    assert {"aid", "jogador", "rodada", "tipo", "direcao", "n_rev", "ordem", "t"} <= set(a) and a["jogador"] == "ana" and a["rodada"] == 1
    b, _ = op(p, c, "bia", 5, "mercado", "b1", direcao="baixa")
    assert b["ordem"] == 2 and p["acoes"] == [a, b]


def test_clique_duplo_nao_duplica_a_acao_nem_o_resultado():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    a, nova = op(p, c, "ana", 3, "mercado", "clique", direcao="alta")
    v = p["versao"]
    b, nova2 = op(p, c, "ana", 4, "mercado", "clique", direcao="alta")                   # mesmo aid, outro instante: é o mesmo clique
    assert nova and not nova2 and b is a and len(p["acoes"]) == 1 and p["versao"] == v
    c2, nova3 = op(p, c, "bia", 3, "mercado", "clique", direcao="alta")                  # aid igual de OUTRO jogador não é duplicata
    assert nova3 and len(p["acoes"]) == 2


def test_segunda_posicao_do_mesmo_jogador_e_recusada_mas_exige_nova_apos_encerrar():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "a1", direcao="alta")
    with pytest.raises(TB.ErroTrader, match="posição aberta"):
        op(p, c, "ana", 4, "mercado", "a2", direcao="baixa")
    with pytest.raises(TB.ErroTrader, match="posição aberta"):
        op(p, c, "ana", 4, "limite", "a3", direcao="alta", preco=9.0)
    assert len(p["acoes"]) == 1                                                          # a recusada não foi gravada
    op(p, c, "ana", 5, "encerrar", "a4")
    op(p, c, "ana", 5, "mercado", "a5", direcao="baixa")                                 # nova operação NA HORA, inclusive na direção contrária
    v = TB.visao(p, c, ag(p, 5), "ana")["mesa"]
    assert v["posicao"]["direcao"] == "baixa" and v["n_encerradas"] == 1


def test_uma_so_ordem_de_entrada_pendente_por_jogador():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    op(p, c, "ana", 2, "limite", "a1", direcao="alta", preco=9.0)
    with pytest.raises(TB.ErroTrader, match="pendente"):
        op(p, c, "ana", 3, "mercado", "a2", direcao="alta")
    op(p, c, "ana", 3, "cancelar", "a3", qual="entrada")
    op(p, c, "ana", 3, "mercado", "a4", direcao="alta")                                  # depois de cancelar, pode


def test_acoes_fora_da_rodada_sao_recusadas():
    c = _cenario(fn_replay=_sobe)
    p = TB.nova_partida(c, "15m", ["ana", "bia"], T0, multi=True, formato="normal", apostas={})
    with pytest.raises(TB.ErroTrader, match="durante o replay"):                         # análise
        TB.registrar_acao(p, c, "ana", {"tipo": "mercado", "direcao": "alta", "aid": "x"}, T0 + 5)
    p = _partida(c)
    fim(p, c)                                                                            # replay acabou → resultado
    with pytest.raises(TB.ErroTrader, match="durante o replay"):
        TB.registrar_acao(p, c, "ana", {"tipo": "mercado", "direcao": "alta", "aid": "y"}, p["t_fase"] + 1)
    with pytest.raises(TB.ErroTrader):                                                   # jogador de fora
        TB.registrar_acao(_partida(c), c, "zeca", {"tipo": "mercado", "direcao": "alta", "aid": "z"}, T0 + 5)


def test_precos_incoerentes_sao_recusados():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)                                                                      # preço atual com 4 candles revelados ≈ 10,14
    for kw in ({"tipo": "limite", "direcao": "alta", "preco": 11.0}, {"tipo": "limite", "direcao": "baixa", "preco": 9.0},
               {"tipo": "stop_entrada", "direcao": "alta", "preco": 9.0}, {"tipo": "stop_entrada", "direcao": "baixa", "preco": 11.0},
               {"tipo": "mercado", "direcao": "alta", "stop": 11.0}, {"tipo": "mercado", "direcao": "baixa", "alvo": 11.0},
               {"tipo": "mercado", "direcao": "lado"}, {"tipo": "limite", "direcao": "alta", "preco": -1}):
        with pytest.raises(TB.ErroTrader):
            op(p, c, "ana", 4, kw.pop("tipo"), f"i{len(p['acoes'])}{id(kw)}", **kw)
    assert p["acoes"] == []


def test_gestao_de_stop_e_alvo_pela_mesa():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "a1", direcao="alta")
    op(p, c, "ana", 3, "definir_stop", "a2", preco=9.5)
    op(p, c, "ana", 3, "definir_alvo", "a3", preco=11.0)
    with pytest.raises(TB.ErroTrader, match="mova-o"):
        op(p, c, "ana", 4, "definir_stop", "a4", preco=9.6)
    with pytest.raises(TB.ErroTrader, match="lado errado"):
        op(p, c, "ana", 4, "mover_stop", "a5", preco=12.0)
    op(p, c, "ana", 4, "mover_stop", "a6", preco=9.8)
    m = TB.visao(p, c, ag(p, 4), "ana")["mesa"]
    assert m["posicao"]["stop"] == 9.8 and m["posicao"]["alvo"] == 11.0 and [o["id"] for o in m["ordens"]] == ["stop", "alvo"] and m["pode_cancelar"]
    op(p, c, "ana", 5, "cancelar", "a7", qual="todas")
    assert TB.visao(p, c, ag(p, 5), "ana")["mesa"]["ordens"] == []


# ------------------------------------------------------------------ patrimônio e pontuação: fluxo completo
def _tres_perdas(c, p):
    op(p, c, "ana", 3, "mercado", "1", direcao="baixa")
    op(p, c, "ana", 5, "encerrar", "2")
    op(p, c, "ana", 5, "mercado", "3", direcao="baixa")
    op(p, c, "ana", 9, "encerrar", "4")
    op(p, c, "ana", 9, "mercado", "5", direcao="baixa")
    op(p, c, "ana", 13, "encerrar", "6")


def test_operacoes_sequenciais_prejuizo_acumulado_reduz_patrimonio_e_pontos_e_pode_passar_de_1_por_cento():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)                                                                      # aposta de referência: 1% de 100.000 = 1.000
    _tres_perdas(c, p)
    fim(p, c)
    r = p["resultados"]["1:ana"]
    assert [round(t["ret"], 6) for t in r["operacoes"]] == [-0.5, -0.5, -0.5]
    assert r["fin"]["pnl"] == -1500.0 and r["fin"]["n_ops"] == 3 and r["fin"]["pct_pat"] == pytest.approx(-1.5)   # 1,5% do patrimônio: passou de 1%
    assert r["pontos"] < 0 and p["pontos"]["ana"] == r["pontos"]                          # perdeu patrimônio E pontos, sem compensação
    assert r["fin"]["aposta"] == 1000.0                                                  # a aposta de referência não foi recalculada a cada operação


def test_lucro_apos_prejuizo_soma_tudo_e_o_resultado_liquido_decide():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="baixa")                                  # perde 50%
    op(p, c, "ana", 5, "encerrar", "2")
    op(p, c, "ana", 5, "mercado", "3", direcao="alta")                                   # compra a 15 e vai a 33,75: +125%
    op(p, c, "ana", 13, "encerrar", "4")
    fim(p, c)
    r = p["resultados"]["1:ana"]
    assert r["fin"]["pnl"] == 750.0 and r["pontos"] > 0 and p["pontos"]["ana"] > 0
    assert [o["pnl"] for o in r["fin"]["ops"]] == [-500.0, 1250.0]


def test_perdas_e_ganhos_que_se_anulam_dao_zero_patrimonio_e_zero_ponto():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="baixa")                                  # −50%
    op(p, c, "ana", 5, "encerrar", "2")
    op(p, c, "ana", 5, "mercado", "3", direcao="alta")                                   # +50% (15 → 22,5)
    op(p, c, "ana", 9, "encerrar", "4")
    fim(p, c)
    r = p["resultados"]["1:ana"]
    assert r["fin"]["pnl"] == 0.0 and r["pontos"] == 0.0 and r["fin"]["operou"]


def test_sem_operacao_zero_ponto_e_patrimonio_inalterado():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    fim(p, c)
    r = p["resultados"]["1:ana"]
    assert r["pontos"] == 0.0 and r["fin"]["pnl"] == 0.0 and not r["fin"]["operou"] and r["operacoes"] == []


def test_encerramento_automatico_no_ultimo_candle_e_ordens_pendentes_expiram():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="alta")                                   # fica aberta até o fim
    op(p, c, "bia", 3, "limite", "2", direcao="alta", preco=8.0)                         # nunca toca: expira
    fim(p, c)
    ana, bia = p["resultados"]["1:ana"], p["resultados"]["1:bia"]
    rep = c["candles"][c["n_analise"]:c["n_analise"] + NR]
    assert ana["operacoes"][0]["motivo"] == "fim" and ana["operacoes"][0]["saida"] == rep[-1]["c"] and ana["fin"]["pnl"] > 0 and ana["pontos"] > 0
    assert bia["operacoes"] == [] and bia["fin"]["pnl"] == 0.0 and bia["pontos"] == 0.0


def test_resultado_e_calculado_uma_vez_e_reprocessar_nao_duplica():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    _tres_perdas(c, p)
    fim(p, c)
    antes = json.dumps(p, sort_keys=True)
    for _ in range(3):
        TB.fechar_rodada(p, c)
        TB.avancar(p, p["t_fase"] + 1, {c["id"]: c})
    assert json.dumps(p, sort_keys=True) == antes and p["pontos"]["ana"] == p["resultados"]["1:ana"]["pontos"]


def test_jogadores_isolados_um_perde_o_outro_ganha_sem_interferencia():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="baixa")                                  # ana vende e o preço sobe
    op(p, c, "bia", 3, "mercado", "2", direcao="alta")                                   # bia compra
    op(p, c, "ana", 5, "encerrar", "3")
    op(p, c, "bia", 5, "encerrar", "4")
    fim(p, c)
    ana, bia = p["resultados"]["1:ana"], p["resultados"]["1:bia"]
    assert ana["fin"]["pnl"] == -500.0 and bia["fin"]["pnl"] == 500.0 and ana["pontos"] < 0 < bia["pontos"]


def test_acoes_simultaneas_no_multiplayer_no_mesmo_instante_sao_processadas_em_ordem_e_independentes():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    agora = ag(p, 3)
    for jog, aid, dirc in (("ana", "1", "alta"), ("bia", "2", "baixa"), ("ana", "3", "baixa")):      # mesmo instante exato
        try:
            TB.registrar_acao(p, c, jog, {"tipo": "mercado", "direcao": dirc, "aid": aid}, agora)
        except TB.ErroTrader:
            pass                                                                         # a 3ª é a segunda posição da ana: recusada
    assert [(a["jogador"], a["ordem"], a["n_rev"]) for a in p["acoes"]] == [("ana", 1, 3), ("bia", 2, 3)]
    assert TB.visao(p, c, agora, "ana")["mesa"]["posicao"]["direcao"] == "alta" and TB.visao(p, c, agora, "bia")["mesa"]["posicao"]["direcao"] == "baixa"


# ------------------------------------------------------------------ pontuação (função pura)
def _t(ret, com_stop=True, i_exc=0, i_saida=5, direcao="alta", entrada=10.0, n=1):
    return {"n": n, "direcao": direcao, "entrada": entrada, "i_entrada": 0, "i_exc": i_exc, "tipo_entrada": "mercado", "saida": entrada * (1 + ret), "i_saida": i_saida,
            "motivo": "manual", "ret": ret, "com_stop": com_stop}


def _cen_r(fn=_sobe):
    return TB.cenario_da_rodada(_cenario(fn_replay=fn), 1, NR)


def test_lucro_sempre_positivo_prejuizo_sempre_negativo_zero_sempre_zero_para_qualquer_modulador():
    cen = _cen_r()
    for decl in ("alta", "baixa", "lateral", None):
        for conf in (None, 1, 3, 5):
            for com_stop in (True, False):
                est = {"direcao": decl, "tipo": "continuacao", "confianca": conf}
                for x in (1e-9, 1e-4, 0.002, 0.02, 0.2, 5.0):
                    assert TB.avaliar_mesa(cen, est, [_t(x, com_stop)])["pontos"] > 0
                    assert TB.avaliar_mesa(cen, est, [_t(-x, com_stop, direcao="baixa")])["pontos"] < 0
                assert TB.avaliar_mesa(cen, est, [_t(0.0, com_stop)])["pontos"] == 0.0
                assert TB.avaliar_mesa(cen, est, [])["pontos"] == 0.0


def test_pontos_crescem_com_o_lucro_e_a_penalizacao_cresce_com_o_prejuizo_e_ha_teto():
    cen = _cen_r()
    est = {"direcao": "alta", "tipo": "continuacao", "confianca": 3}
    ganhos = [TB.avaliar_mesa(cen, est, [_t(x)])["pontos"] for x in (0.001, 0.005, 0.01, 0.02, 0.05)]
    perdas = [TB.avaliar_mesa(cen, est, [_t(-x)])["pontos"] for x in (0.001, 0.005, 0.01, 0.02, 0.05)]
    assert ganhos == sorted(ganhos) and perdas == sorted(perdas, reverse=True) and len(set(ganhos)) == 5
    assert max(ganhos) <= TB.PONTOS_MAX and min(perdas) >= -TB.PONTOS_MAX
    assert TB.avaliar_mesa(cen, est, [_t(50.0)])["pontos"] == TB.PONTOS_MAX


def test_quantidade_de_operacoes_nao_gera_pontos_artificiais():
    cen = _cen_r()
    est = {"direcao": "alta", "tipo": "continuacao", "confianca": 3}
    uma = TB.avaliar_mesa(cen, est, [_t(0.02)])
    dez = TB.avaliar_mesa(cen, est, [_t(0.002, n=i + 1) for i in range(10)])
    assert dez["partes"]["base"] == pytest.approx(uma["partes"]["base"], abs=1e-6)       # mesmo resultado líquido, mesma base, sem bônus por operar mais
    cem = TB.avaliar_mesa(cen, est, [_t(0.01 if i % 2 == 0 else -0.01, n=i + 1) for i in range(100)])
    assert cem["pontos"] == 0.0                                                          # 100 operações que se anulam: zero


def test_componentes_do_modulador_q_sao_deterministicos():
    cen = _cen_r()                                                                       # mercado sobe 0,48 (> 1 ATR): direção real = alta
    q = lambda decl, conf, trades: TB.avaliar_mesa(cen, {"direcao": decl, "tipo": "continuacao", "confianca": conf}, trades)["partes"]["q"]
    assert q("alta", 3, [_t(0.01)])["direcao"] == 1.0 and q("baixa", 3, [_t(0.01)])["direcao"] == -1.0
    assert q("lateral", 3, [_t(0.01)])["direcao"] == 0.0 and q(None, None, [_t(0.01)])["direcao"] == 0.0
    assert q("alta", 5, [_t(0.01)])["confianca"] == 1.0 and q("baixa", 5, [_t(0.01)])["confianca"] == -1.0
    assert q("alta", 1, [_t(0.01)])["confianca"] == 0.0 and q("lateral", 5, [_t(0.01)])["confianca"] == 0.0 and q("alta", 3, [_t(0.01)])["confianca"] == 0.5
    assert q("alta", 3, [_t(0.01, True)])["risco"] == 1.0 and q("alta", 3, [_t(0.01, False)])["risco"] == -1.0
    assert q("alta", 3, [_t(0.01, True), _t(0.01, False)])["risco"] == 0.0
    assert q("alta", 3, [_t(0.01, direcao="alta")])["entrada"] > 0 > q("alta", 3, [_t(-0.01, direcao="baixa", entrada=10.0)])["entrada"]
    tot = q("alta", 5, [_t(0.01, True)])
    assert tot["total"] == pytest.approx((tot["direcao"] + tot["entrada"] + tot["risco"] + tot["confianca"]) / 4, abs=1e-3)


def test_modulador_muda_no_maximo_25_por_cento_e_nunca_o_sinal():
    cen = _cen_r()
    bom = TB.avaliar_mesa(cen, {"direcao": "alta", "tipo": "continuacao", "confianca": 5}, [_t(0.01, True)])
    ruim = TB.avaliar_mesa(cen, {"direcao": "baixa", "tipo": "continuacao", "confianca": 5}, [_t(0.01, False)])
    assert 0 < ruim["pontos"] < bom["pontos"] and bom["pontos"] / ruim["pontos"] <= 1.25 / 0.75 + 1e-6
    assert TB.avaliar_mesa(cen, {"direcao": "alta", "tipo": "continuacao", "confianca": 5}, [_t(-0.01, True, direcao="baixa")])["pontos"] > \
        TB.avaliar_mesa(cen, {"direcao": "baixa", "tipo": "continuacao", "confianca": 5}, [_t(-0.01, False, direcao="baixa")])["pontos"]   # boa disciplina perde menos


def test_pontuacao_e_deterministica_e_explicavel():
    cen = _cen_r()
    est = {"direcao": "alta", "tipo": "continuacao", "confianca": 4}
    a, b = TB.avaliar_mesa(cen, est, [_t(0.01)]), TB.avaliar_mesa(cen, est, [_t(0.01)])
    assert a == b
    linhas = dict(TB.explicar(a))
    assert "Pontos" in linhas and "Resultado" in linhas and "Qualidade" in linhas


# ------------------------------------------------------------------ multiplayer: o adversário vê entradas e saídas, mas nunca o que é privado
STOP_SECRETO, ALVO_SECRETO, LIMITE_SECRETO = 8.7654, 13.4321, 9.1234


def test_adversario_ve_entrada_e_saida_executadas_sem_ter_operado_e_sem_ver_stop_alvo_nem_pendentes():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="alta", stop=STOP_SECRETO, alvo=ALVO_SECRETO)
    bia = TB.visao(p, c, ag(p, 3), "bia")                                                # bia NUNCA operou
    assert bia["adversarios"] == [{"rotulo": "Jogador 1", "ops": [{"direcao": "alta", "preco_entrada": pytest.approx(10.0 + 0.02 * 2 + 0.02), "indice_entrada": c["n_analise"] + 2,
                                                                  "aberta": True, "preco_saida": None, "indice_saida": None}], "total_pct": 0.0}]
    op(p, c, "ana", 6, "encerrar", "2")
    op(p, c, "ana", 6, "limite", "3", direcao="baixa", preco=LIMITE_SECRETO + 5)         # pendente: invisível
    bia = TB.visao(p, c, ag(p, 6), "bia")
    ops = bia["adversarios"][0]["ops"]
    assert len(ops) == 1 and not ops[0]["aberta"] and ops[0]["preco_saida"] == pytest.approx(10.0 + 0.02 * 5 + 0.02) and ops[0]["indice_saida"] == c["n_analise"] + 5
    assert set(ops[0]) == {"direcao", "preco_entrada", "indice_entrada", "aberta", "preco_saida", "indice_saida"}      # lista fechada de campos
    assert bia["adversarios"][0]["total_pct"] == pytest.approx((ops[0]["preco_saida"] / ops[0]["preco_entrada"] - 1) * 100, abs=1e-3)   # placar: só do que é público
    txt = json.dumps(bia)
    for segredo in (STOP_SECRETO, ALVO_SECRETO, LIMITE_SECRETO + 5, "motivo", '"aid"'):
        assert str(segredo) not in txt


def test_ordem_pendente_do_adversario_so_aparece_quando_executada():
    c = _cenario(fn_replay=lambda i: (10.0, 10.05, 9.4, 9.9) if i == 6 else (10.0, 10.05, 9.95, 10.0))
    p = _partida(c)
    op(p, c, "ana", 2, "limite", "1", direcao="alta", preco=9.5)
    assert TB.visao(p, c, ag(p, 6), "bia")["adversarios"][0]["ops"] == []                # candle 6 ainda não foi revelado (só 0..5)
    ops = TB.visao(p, c, ag(p, 7), "bia")["adversarios"][0]["ops"]                       # agora o candle 6 apareceu e a ordem executou nele
    assert len(ops) == 1 and ops[0]["preco_entrada"] == 9.5 and ops[0]["indice_entrada"] == c["n_analise"] + 6


def test_visao_propria_traz_stop_alvo_e_pendentes_so_para_o_dono():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="alta", stop=STOP_SECRETO, alvo=ALVO_SECRETO)
    m = TB.visao(p, c, ag(p, 3), "ana")["mesa"]
    assert m["posicao"]["stop"] == STOP_SECRETO and m["posicao"]["alvo"] == ALVO_SECRETO
    assert TB.visao(p, c, ag(p, 3), "bia")["mesa"]["posicao"] is None and TB.visao(p, c, ag(p, 3), "bia")["mesa"]["ordens"] == []


# ------------------------------------------------------------------ futuro nunca vaza + sincronização do relógio
FUTURO = 77.77


def _com_futuro(i):
    return (10.0, FUTURO, 9.9, 10.0) if i == 20 else (10.0, 10.05, 9.95, 10.0)


def test_nenhum_candle_futuro_chega_ao_navegador_nem_pela_mesa_nem_pelos_adversarios():
    c = _cenario(fn_replay=_com_futuro)
    p = _partida(c)
    op(p, c, "ana", 4, "mercado", "1", direcao="alta")
    for jog in ("ana", "bia"):
        for k in (0, 5, 19):
            v = TB.visao(p, c, ag(p, k), jog)
            assert len(v["candles"]) == c["n_analise"] + k and v["revelados"] == k and v["resultado"] is None
            assert str(FUTURO) not in json.dumps(v)
    assert str(FUTURO) in json.dumps(TB.visao(p, c, ag(p, 21), "ana")["candles"])        # depois de revelado, aparece


def test_ordem_pendente_nao_enxerga_o_futuro_para_executar():
    c = _cenario(fn_replay=lambda i: (10.0, 10.05, 9.0, 9.5) if i == 15 else (10.0, 10.05, 9.95, 10.0))
    p = _partida(c)
    op(p, c, "ana", 2, "limite", "1", direcao="alta", preco=9.5)
    assert TB.visao(p, c, ag(p, 10), "ana")["mesa"]["posicao"] is None and len(TB.visao(p, c, ag(p, 10), "ana")["mesa"]["ordens"]) == 1


def test_os_dois_jogadores_veem_os_mesmos_candles_no_mesmo_instante_e_o_estado_sobrevive_ao_banco():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="alta")
    p2 = json.loads(json.dumps(p))                                                       # o que o banco devolveria (reconexão/outra sessão)
    for k in (1, 7, 22):
        a, b, a2 = TB.visao(p, c, ag(p, k), "ana"), TB.visao(p, c, ag(p, k), "bia"), TB.visao(p2, c, ag(p, k), "ana")
        assert a["candles"] == b["candles"] == a2["candles"] and a["revelados"] == b["revelados"] == k and a["segundos"] == b["segundos"]
    assert p["t_fase"] == p2["t_fase"] and TB.n_revelados(p, ag(p, 9)) == TB.n_revelados(p2, ag(p, 9)) == 9


def test_o_navegador_nao_avanca_o_relogio_so_o_servidor():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    assert TB.cfg_de(p)["t_replay_s"] / TB.cfg_de(p)["n_replay"] == 2.5 and TB.cfg_de(p)["n_replay"] == 24
    assert TB.n_revelados(p, p["t_fase"] + 2.49) == 0 and TB.n_revelados(p, p["t_fase"] + 2.5) == 1 and TB.n_revelados(p, p["t_fase"] + 59.9) == 23


# ------------------------------------------------------------------ pausa técnica compartilhada
def test_pausa_tecnica_congela_para_os_dois_e_a_retomada_e_sincronizada():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    t = p["t_fase"]
    cens = {c["id"]: c}
    assert TB.pausar(p, t + 10, cens) and not TB.pausar(p, t + 11, cens) and TB.pausada(p)
    for jog in ("ana", "bia"):
        assert TB.visao(p, c, t + 500, jog)["revelados"] == 4 and TB.visao(p, c, t + 500, jog)["pausada"]
    with pytest.raises(TB.ErroTrader, match="pausa"):
        TB.registrar_acao(p, c, "ana", {"tipo": "mercado", "direcao": "alta", "aid": "p"}, t + 20)
    assert TB.retomar(p, t + 30) and not TB.pausada(p) and not TB.retomar(p, t + 31)
    assert TB.n_revelados(p, t + 30) == 4 and TB.n_revelados(p, t + 35) == 6             # 20 s parados não contam
    TB.avancar(p, t + 79, cens)
    assert p["fase"] == "replay"                                                         # o fim da rodada foi empurrado em 20 s
    TB.avancar(p, t + 80.5, cens)
    assert p["fase"] == "resultado" and p["t_fase"] == t + 80
    assert TB.visao(p, c, t + 81, "ana")["candles"] == TB.visao(p, c, t + 81, "bia")["candles"]


def test_pausa_em_aberto_impede_o_fim_da_rodada_e_o_relogio_continua_depois_de_retomar():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    t = p["t_fase"]
    TB.pausar(p, t + 50, {c["id"]: c})
    TB.avancar(p, t + 10_000, {c["id"]: c})
    assert p["fase"] == "replay" and TB.segundos_restantes(p, t + 10_000) == 10
    TB.retomar(p, t + 10_000)
    TB.avancar(p, t + 10_009, {c["id"]: c})
    assert p["fase"] == "replay"
    TB.avancar(p, t + 10_010.5, {c["id"]: c})
    assert p["fase"] == "resultado"


# ------------------------------------------------------------------ rodadas configuráveis
def test_formatos_de_rodadas_sao_3_5_e_10_e_so_eles():
    assert TB.FORMATOS == {"rapida": 3, "normal": 5, "longa": 10} and TB.FORMATO_PADRAO == "normal"
    c = _cenario(fn_replay=_sobe)
    for f, n in TB.FORMATOS.items():
        p = TB.nova_partida(c, "15m", ["ana"], T0, formato=f)
        assert TB.cfg_de(p)["rodadas"] == n and len(p["cenarios"]) == n
    with pytest.raises(TB.ErroTrader):
        TB.nova_partida(c, "15m", ["ana"], T0, formato="infinita")


def test_partida_rapida_termina_na_rodada_3_e_cada_rodada_tem_24_candles_em_60s():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c, formato="rapida")
    cens = {c["id"]: c}
    vistos = []
    for r in (1, 2, 3):
        assert p["rodada"] == r and p["fase"] == "replay"
        vistos.append(TB.visao(p, c, ag(p, 5), "ana")["n_analise"])
        fim(p, c, 0.5)                                                                   # replay termina → resultado
        TB.avancar(p, p["t_fase"] + TB.T_RESULTADO_S + 0.1, cens)                        # resultado termina → próxima rodada (ou fim)
        if r < 3:
            assert p["fase"] == "analise"
            for j in ("ana", "bia"):
                TB.salvar_estrategia(p, j, dict(EST), None, 10.0, p["t_fase"] + 1)
    assert p["fase"] == "fim" and vistos == [c["n_analise"] + NR * i for i in range(3)]
    assert TB.visao(p, c, p["t_fase"] + 5, "ana")["rodadas"] == 3


def test_cenario_1h_antigo_comporta_rapida_e_normal_mas_nao_longa():
    c = _cenario("1h", fn_replay=_sobe, tam_bloco=TB.TIMEFRAMES["1h"]["n_replay"])       # 100 + 10×16 = 260 candles (formato antigo)
    ok, why = TB.validar_cenario(c)
    assert ok, why
    assert TB.capacidade_rodadas(c) == 6
    for f in ("rapida", "normal"):
        assert TB.cfg_de(TB.nova_partida(c, "1h", ["ana"], T0, formato=f))["n_replay"] == 24
    with pytest.raises(TB.ErroTrader, match="comporta"):
        TB.nova_partida(c, "1h", ["ana"], T0, formato="longa")
    novo = _cenario("1h", fn_replay=_sobe)                                               # 100 + 10×24 = 340 candles (formato novo)
    assert TB.validar_cenario(novo)[0] and TB.capacidade_rodadas(novo) == 10 and TB.nova_partida(novo, "1h", ["ana"], T0, formato="longa")


# ------------------------------------------------------------------ compatibilidade com partidas antigas
GOLD = {"15m": {"pontos": 66.1, "partes": {"direcao": 40.0, "operacao": 21.1, "confianca": 5.0}, "pnl": 7.91, "pct_aposta": 0.791, "saida": 10.2, "entrada": 10.12},
        "1h": {"pontos": 66.6, "partes": {"direcao": 40.0, "operacao": 21.6, "confianca": 5.0}, "pnl": 11.9, "pct_aposta": 1.19, "saida": 10.2, "entrada": 10.08}}


def test_partida_antiga_sem_acoes_mantem_pontos_valores_e_regras_originais():
    """Valores de referência gerados com o código ANTES da mesa (mesmo cenário, mesmo fluxo): têm que continuar idênticos."""
    for tf, g in GOLD.items():
        nr = TB.TIMEFRAMES[tf]["n_replay"]
        c = _cenario(tf, fn_replay=_sobe, tam_bloco=nr)
        p = TB.nova_partida(c, tf, ["ana"], T0, apostas={"ana": {"stake": 1000.0, "pat": 100000.0}})        # sem formato = motor antigo
        assert TB.motor_de(p) == 1 and "cfg" not in p and p.get("acoes", []) == []
        cfg = TB.cfg_de(p)
        assert (cfg["rodadas"], cfg["n_replay"], cfg["t_replay_s"]) == (10, nr, 30.0)
        p = json.loads(json.dumps(p))                                                    # como vem do banco
        est = {"direcao": "alta", "tipo": "continuacao", "confianca": 3, "entrada": 9.5, "stop": 9.0, "alvo": 12.0}
        TB.salvar_estrategia(p, "ana", est, None, 10.0, T0 + 1)
        TB.iniciar_replay(p, "ana", T0 + 2)
        t = p["t_fase"]
        TB.encerrar_operacao(p, c, "ana", t + TB.T_REPLAY_S / nr * 10 + 0.01)           # encerramento antigo: p["encerradas"]
        assert p["encerradas"]["1:ana"] == 10
        TB.avancar(p, t + TB.T_REPLAY_S + 1, {c["id"]: c})
        r = p["resultados"]["1:ana"]
        assert r["pontos"] == g["pontos"] and r["partes"] == g["partes"] and p["pontos"]["ana"] == g["pontos"]
        assert r["operacao"]["saida"] == g["saida"] and r["operacao"]["preco_entrada"] == g["entrada"]
        assert r["fin"]["pnl"] == g["pnl"] and r["fin"]["pct_aposta"] == g["pct_aposta"] and set(r["fin"]) == {"aposta", "pnl", "pct_aposta", "pct_pat", "pat_ini", "operou"}
        v = TB.visao(p, c, t + TB.T_REPLAY_S + 1, "ana")
        assert v["rodadas"] == 10 and v["total_replay"] == nr and v["motor"] == 1 and "mesa" not in v and v["pontos_rodadas"] == [g["pontos"]]
        assert TB.segundos_restantes(p, t + 5) == 0                                      # já está no resultado


def test_partida_antiga_pontuacao_original_continua_com_piso_zero_e_nao_aceita_acoes_da_mesa():
    c = _cenario(fn_replay=_sobe, tam_bloco=24)
    p = TB.nova_partida(c, "15m", ["ana"], T0, apostas={"ana": {"stake": 1000.0, "pat": 100000.0}})
    with pytest.raises(TB.ErroTrader, match="regras antigas"):
        TB.registrar_acao(p, c, "ana", {"tipo": "mercado", "direcao": "alta", "aid": "x"}, T0 + 5)
    r = TB.avaliar(TB.cenario_da_rodada(c, 1), {"direcao": "baixa", "tipo": "continuacao", "confianca": 5, "entrada": 10.5, "stop": 11.0, "alvo": 8.0})
    assert r["pontos"] >= 0.0 and "motor" not in r                                       # a regra antiga nunca pontua negativo


def test_estado_antigo_sem_chaves_novas_abre_e_finaliza_sem_erro():
    c = _cenario(fn_replay=_sobe, tam_bloco=24)
    p = TB.nova_partida(c, "15m", ["ana", "bia"], T0, multi=True, apostas={})
    for k in ("cfg", "acoes", "seq_acao", "pausas", "stakes"):
        p.pop(k, None)
    for j in ("ana", "bia"):
        TB.salvar_estrategia(p, j, {"direcao": "lateral", "tipo": "aguardar", "confianca": 2}, None, 10.0, T0 + 1)
    assert TB.visao(p, c, p["t_fase"] + 3, "ana")["adversarios"] == [] and not TB.pausada(p)
    for _ in range(10):
        fim(p, c, 0.5)
        TB.avancar(p, p["t_fase"] + TB.T_RESULTADO_S + 0.1, {c["id"]: c})
        if p["fase"] == "analise":
            for j in ("ana", "bia"):
                TB.salvar_estrategia(p, j, {"direcao": "lateral", "tipo": "aguardar", "confianca": 2}, None, 10.0, p["t_fase"] + 1)
    assert p["fase"] == "fim" and p["rodada"] == 10


# ====================================================================================================================================
# WALLET GAME · um lançamento consolidado por rodada (livro falso em memória; sem rede)
# ====================================================================================================================================
import contextlib

import trader_carteira as TCA


@contextlib.contextmanager
def livro(pat=100000.0, caixa=50000.0):
    """Troca o livro real por um dicionário: _inserir_credito devolve True só na 1ª vez de cada chave (como a restrição de unicidade do banco)."""
    lanc = {}
    orig = (TCA.WG._inserir_credito, TCA.WG.sincronizar, TCA.conta_id, TCA.situacao)

    def inserir(email, conta, chave, tipo, valor, dia, desc, meta, agora):
        if chave in lanc:
            return False
        lanc[chave] = {"valor": valor, "tipo": tipo, "desc": desc, "meta": meta}
        return True
    TCA.WG._inserir_credito, TCA.WG.sincronizar, TCA.conta_id = inserir, lambda e: {}, lambda e: "conta-" + e
    def do(e):
        return sum(v["valor"] for k, v in lanc.items() if k.endswith(":" + e))          # o lançamento é de quem tem o e-mail na chave
    TCA.situacao = lambda e: {"pat": pat + do(e), "caixa": caixa + do(e)}
    try:
        yield lanc
    finally:
        TCA.WG._inserir_credito, TCA.WG.sincronizar, TCA.conta_id, TCA.situacao = orig


def test_tres_operacoes_da_rodada_viram_um_unico_lancamento_consolidado_com_sinal():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    _tres_perdas(c, p)
    fim(p, c)
    with livro() as lanc:
        assert TCA.liquidar(p) == 1
        assert list(lanc) == [f"trader:{p['id']}:1:ana"] and lanc[f"trader:{p['id']}:1:ana"]["valor"] == -1500.0 and lanc[f"trader:{p['id']}:1:ana"]["tipo"] == "trader"
        assert lanc[f"trader:{p['id']}:1:ana"]["meta"]["n_ops"] == 3                      # bia não operou: sem lançamento


def test_reprocessar_recarregar_ou_outra_sessao_nunca_lanca_duas_vezes():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    _tres_perdas(c, p)
    fim(p, c)
    with livro() as lanc:
        assert TCA.liquidar(p) == 1
        assert TCA.liquidar(p) == 0 and TCA.liquidar(json.loads(json.dumps(p))) == 0       # F5, reconexão, outra aba
        for _ in range(3):
            TB.fechar_rodada(p, c)
            TCA.liquidar(p)
        assert len(lanc) == 1 and sum(v["valor"] for v in lanc.values()) == -1500.0


def test_cada_rodada_lanca_uma_vez_e_o_patrimonio_acumula_as_rodadas():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    with livro() as lanc:
        op(p, c, "ana", 3, "mercado", "1", direcao="alta")
        op(p, c, "ana", 13, "encerrar", "2")                                              # rodada 1: 10 → 33,75 = +237,5%
        fim(p, c, 0.5)
        TB.avancar(p, p["t_fase"] + TB.T_RESULTADO_S + 0.1, {c["id"]: c})
        assert TCA.liquidar(p) == 1 and p["rodada"] == 2
        for j in ("ana", "bia"):
            TB.salvar_estrategia(p, j, dict(EST), None, 10.0, p["t_fase"] + 1)
        fim(p, c, 0.5)                                                                    # rodada 2 sem operar
        assert TCA.liquidar(p) == 0                                      # rodada 2 sem operação: nada a lançar
        assert len(lanc) == 1 and lanc[f"trader:{p['id']}:1:ana"]["valor"] == 2375.0
        assert TCA.situacao("ana")["pat"] == 100000.0 + 2375.0                            # o patrimônio da carteira mudou uma vez


def test_pontos_da_batalha_e_saldo_da_carteira_sao_independentes():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    _tres_perdas(c, p)
    fim(p, c)
    with livro() as lanc:
        TCA.liquidar(p)
        assert p["pontos"]["ana"] < 0 and list(lanc.values())[0]["valor"] == -1500.0 and "pontos" not in list(lanc.values())[0]["meta"]


def test_resultado_zero_nao_gera_lancamento_e_visitante_sem_aposta_nao_mexe_na_carteira():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    fim(p, c)
    with livro() as lanc:
        assert TCA.liquidar(p) == 0 and lanc == {}
    pv = TB.nova_partida(c, "15m", ["v"], T0, formato="rapida", apostas={})              # visitante: sem aposta
    TB.salvar_estrategia(pv, "v", dict(EST), None, 10.0, T0 + 1)
    TB.iniciar_replay(pv, "v", T0 + 2)
    TB.registrar_acao(pv, c, "v", {"tipo": "mercado", "direcao": "alta", "aid": "1"}, ag(pv, 3))
    fim(pv, c)
    assert pv["resultados"]["1:v"]["fin"] is None and pv["resultados"]["1:v"]["pontos"] > 0        # joga pelos pontos, sem dinheiro
    with livro() as lanc:
        assert TCA.liquidar(pv) == 0 and lanc == {}


def test_liquidar_respeita_o_numero_de_rodadas_da_partida_e_partida_antiga_continua_igual():
    with livro() as lanc:
        c = _cenario(fn_replay=_sobe, tam_bloco=24)
        p = TB.nova_partida(c, "15m", ["ana"], T0, apostas={"ana": {"stake": 1000.0, "pat": 100000.0, "conta": "c"}})      # motor antigo
        for rod in range(1, 11):
            p["resultados"][f"{rod}:ana"] = {"fin": {"aposta": 1000.0, "pnl": 10.0, "pct_aposta": 1.0}}
        assert TCA.liquidar(p) == 10 and len(lanc) == 10                                 # 10 rodadas, como antes (sem n_ops no resultado antigo)
    with livro() as lanc:
        pm = _partida(_cenario(fn_replay=_sobe), formato="rapida")
        for rod in range(1, 11):
            pm["resultados"][f"{rod}:ana"] = {"fin": {"aposta": 1000.0, "pnl": 10.0, "pct_aposta": 1.0, "n_ops": 1}}
        assert TCA.liquidar(pm) == 3 and len(lanc) == 3                                  # partida Rápida: só as 3 rodadas dela


def test_aposta_da_rodada_e_1_por_cento_do_patrimonio_atual_e_sem_caixa_nao_derruba_a_partida():
    with livro(pat=200000.0, caixa=50000.0):
        a = TCA.aposta_rodada("ana")
        assert a["stake"] == 2000.0 and a["pat"] == 200000.0 and "sem_saldo" not in a
    with livro(pat=200000.0, caixa=100.0):
        a = TCA.aposta_rodada("ana")
        assert a["stake"] == 0.0 and a["sem_saldo"] and a["pat"] == 200000.0
        with pytest.raises(TCA.SemSaldo):
            TCA.aposta_de("ana")                                                          # entrar na partida continua exigindo o caixa


# ====================================================================================================================================
# MULTIPLAYER ONLINE · banco SQLite de verdade (CAS por versão), carteira falsa, relógio do servidor
# ====================================================================================================================================
import os
import shutil
import tempfile

import banco
import trader_online_dados as OL

TS = 1_700_000_000.0
EMAILS = ("a@x.com", "b@x.com")


@contextlib.contextmanager
def banco_isolado():
    """Banco SQLite TEMPORÁRIO só para o teste. Todo acesso a `banco` (cenários, salas, contas) fica nele: o `usuarios.db` do projeto nunca é aberto, criado ou lido.
    Guarda o estado anterior do módulo `banco`, restaura SEMPRE (mesmo se uma asserção falhar) e apaga a pasta temporária."""
    anterior = (banco._caminho_sqlite, banco._forcar_sqlite)
    pasta = tempfile.mkdtemp(prefix="tb_teste_")
    try:
        banco.usar_sqlite(os.path.join(pasta, "t.db"))
        banco.migrar_sqlite()
        yield pasta
    finally:
        banco._caminho_sqlite, banco._forcar_sqlite = anterior
        banco._pronto_cache.clear()
        shutil.rmtree(pasta, ignore_errors=True)


def _contas(emails=EMAILS):
    for e in emails:
        banco._inserir("contas", {"id": "id-" + e, "email": e, "nome": e, "criado_em": "2026-01-01T00:00:00Z"})


@contextlib.contextmanager
def sala_online(formato="rapida", tf="15m", pat=100000.0):
    """Banco SQLite temporário (isolado) + livro falso da Wallet + sala iniciada. Devolve (pid, lanc)."""
    with banco_isolado():
        _contas()
        with livro(pat=pat, caixa=pat) as lanc:
            r = OL.criar_sala(EMAILS[0], tf, TS, formato)
            OL.entrar_na_sala(EMAILS[1], r["codigo"], TS + 1)
            OL.iniciar(r["id"], EMAILS[0], TS + 2)
            yield r["id"], lanc


def _leitura(pid, e, t, est=None):
    OL.salvar(pid, e, est or dict(EST), None, t)


def _comecar_replay(pid, t=TS + 10):
    for e in EMAILS:
        _leitura(pid, e, t)
    return t                                                                              # replay começou em t


def test_sala_guarda_o_formato_e_a_partida_nasce_com_a_configuracao_certa():
    for formato, n in TB.FORMATOS.items():
        with sala_online(formato) as (pid, _):
            v = OL.ler(pid, EMAILS[0], TS + 3)["v"]
            assert (v["motor"], v["formato"], v["rodadas"], v["total_replay"]) == (2, formato, n, 24)
    with banco_isolado():
        _contas((EMAILS[0],))
        with livro():
            with pytest.raises(OL.ErroSala, match="Formato"):
                OL.criar_sala(EMAILS[0], "15m", TS, "infinita")


def test_online_entrada_do_adversario_aparece_sem_ele_ter_operado_e_clique_duplo_nao_duplica():
    with sala_online() as (pid, _):
        t = _comecar_replay(pid)
        OL.agir(pid, EMAILS[0], {"tipo": "mercado", "direcao": "alta", "aid": "u1", "stop": 1.0, "alvo": 9999.0}, t + 12.6)
        OL.agir(pid, EMAILS[0], {"tipo": "mercado", "direcao": "alta", "aid": "u1", "stop": 1.0, "alvo": 9999.0}, t + 12.7)       # reenvio
        bia = OL.ler(pid, EMAILS[1], t + 13)
        assert len(bia["v"]["adversarios"][0]["ops"]) == 1 and bia["v"]["mesa"]["posicao"] is None and bia["v"]["mesa"]["pode_abrir"]
        assert "9999" not in json.dumps(bia) and '"stop"' not in json.dumps(bia["v"]["adversarios"])
        row = OL._row(pid)["dados"]["p"]
        assert len(row["acoes"]) == 1


def test_online_acao_recusada_nao_grava_nada_e_fora_do_replay_e_bloqueada():
    with sala_online() as (pid, _):
        with pytest.raises(TB.ErroTrader, match="replay"):
            OL.Ops(pid, EMAILS[0]).agir({"tipo": "mercado", "direcao": "alta", "aid": "x"}, TS + 5)          # ainda na análise
        t = _comecar_replay(pid)
        v0 = OL._row(pid)["versao"]
        with pytest.raises(TB.ErroTrader, match="lado errado"):
            OL.Ops(pid, EMAILS[0]).agir({"tipo": "mercado", "direcao": "alta", "aid": "y", "stop": 10_000.0}, t + 12.6)
        assert OL._row(pid)["versao"] == v0 and OL._row(pid)["dados"]["p"]["acoes"] == []
        with pytest.raises(TB.ErroTrader, match="replay"):
            OL.agir(pid, EMAILS[0], {"tipo": "mercado", "direcao": "alta", "aid": "z"}, t + 61)            # depois do fim da rodada
        with pytest.raises(OL.ErroSala, match="participa"):
            OL.agir(pid, "intruso@x.com", {"tipo": "mercado", "direcao": "alta", "aid": "w"}, t + 20)


def test_online_acoes_simultaneas_dos_dois_jogadores_nao_se_sobrescrevem():
    with sala_online() as (pid, _):
        t = _comecar_replay(pid)
        agora = t + 12.6                                                                  # exatamente o mesmo instante para os dois
        OL.agir(pid, EMAILS[0], {"tipo": "mercado", "direcao": "alta", "aid": "a1"}, agora)
        OL.agir(pid, EMAILS[1], {"tipo": "mercado", "direcao": "baixa", "aid": "b1"}, agora)
        ac = OL._row(pid)["dados"]["p"]["acoes"]
        assert [(a["jogador"], a["ordem"], a["n_rev"]) for a in ac] == [(EMAILS[0], 1, 5), (EMAILS[1], 2, 5)]
        a, b = OL.ler(pid, EMAILS[0], agora)["v"], OL.ler(pid, EMAILS[1], agora)["v"]
        assert a["mesa"]["posicao"]["direcao"] == "alta" and b["mesa"]["posicao"]["direcao"] == "baixa" and a["candles"] == b["candles"]


def test_online_conflito_de_escrita_e_refeito_sobre_os_dados_novos_cas():
    """Simula duas sessões: a gravação da outra acontece ENTRE a leitura e a escrita da primeira. O CAS recusa, relê e reaplica: nenhuma ação se perde."""
    with sala_online() as (pid, _):
        t = _comecar_replay(pid)
        original = OL.banco._atualizar_n
        estado = {"n": 0}

        def com_corrida(tabela, filtros, campos):
            if tabela == "tb_partidas" and estado["n"] == 0:
                estado["n"] = 1
                OL.banco._atualizar_n = original                                         # a "outra sessão" grava primeiro
                OL.agir(pid, EMAILS[1], {"tipo": "mercado", "direcao": "baixa", "aid": "b1"}, t + 12.6)
                OL.banco._atualizar_n = com_corrida
            return original(tabela, filtros, campos)
        OL.banco._atualizar_n = com_corrida
        try:
            OL.agir(pid, EMAILS[0], {"tipo": "mercado", "direcao": "alta", "aid": "a1"}, t + 12.7)
        finally:
            OL.banco._atualizar_n = original
        ac = OL._row(pid)["dados"]["p"]["acoes"]
        assert sorted(a["jogador"] for a in ac) == sorted(EMAILS) and sorted(a["ordem"] for a in ac) == [1, 2]


def test_online_rodada_fecha_sozinha_lanca_uma_vez_e_a_aposta_da_rodada_seguinte_usa_o_patrimonio_novo():
    with sala_online("rapida", pat=100000.0) as (pid, lanc):
        t = _comecar_replay(pid)
        OL.agir(pid, EMAILS[0], {"tipo": "mercado", "direcao": "alta", "aid": "a1"}, t + 2.6)           # fica aberta até o fim da rodada
        v = OL.ler(pid, EMAILS[0], t + 61)["v"]                                                          # só ler já fecha a rodada (idempotente)
        assert v["fase"] == "resultado" and v["resultado"]["operacoes"][0]["motivo"] == "fim"
        pnl = v["resultado"]["fin"]["pnl"]
        assert len(lanc) == 1 and list(lanc.values())[0]["valor"] == pnl
        for _ in range(3):
            OL.ler(pid, EMAILS[0], t + 62)
            OL.ler(pid, EMAILS[1], t + 62)
        assert len(lanc) == 1                                                             # várias leituras/sessões: ainda 1 lançamento
        v2 = OL.ler(pid, EMAILS[0], t + 61 + TB.T_RESULTADO_S + 1)["v"]                   # rodada 2
        assert v2["rodada"] == 2 and v2["fase"] == "analise"
        st = OL._row(pid)["dados"]["p"]["stakes"]
        assert st[f"2:{EMAILS[0]}"]["pat"] == pytest.approx(100000.0 + pnl) and st[f"2:{EMAILS[0]}"]["stake"] == pytest.approx(round((100000.0 + pnl) * 0.01, 2))
        assert st[f"2:{EMAILS[1]}"]["pat"] == 100000.0 and st["1:" + EMAILS[0]]["pat"] == 100000.0     # a de bia não mudou; a rodada 1 não foi reescrita


def test_online_sala_antiga_sem_formato_inicia_com_as_regras_antigas():
    with banco_isolado():
        _contas()
        with livro():
            r = OL.criar_sala(EMAILS[0], "15m", TS, "rapida")
            OL.entrar_na_sala(EMAILS[1], r["codigo"], TS + 1)
            d = OL._row(r["id"])["dados"]
            d["sala"].pop("formato")                                                      # como uma sala gravada antes desta versão
            banco._atualizar_n("tb_partidas", {"id": r["id"]}, {"dados": banco._js(d)})
            OL.iniciar(r["id"], EMAILS[0], TS + 2)
            v = OL.ler(r["id"], EMAILS[0], TS + 3)["v"]
            assert v["motor"] == 1 and v["rodadas"] == 10 and "mesa" not in v
            p = OL._row(r["id"])["dados"]["p"]
            assert "cfg" not in p and p.get("acoes", []) == []


# ====================================================================================================================================
# PONTE COM O NAVEGADOR (trader_grafico): argumentos do componente e eventos
# ====================================================================================================================================
import trader_grafico as G


def test_argumentos_do_componente_nao_vazam_futuro_nem_segredos_do_adversario():
    c = _cenario(fn_replay=_com_futuro)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="alta", stop=STOP_SECRETO, alvo=ALVO_SECRETO)
    agora = ag(p, 5)
    bia = G.args_mesa(TB.visao(p, c, agora, "bia"), p, {}, agora)
    txt = json.dumps(bia, default=str)
    for segredo in (STOP_SECRETO, ALVO_SECRETO, FUTURO):
        assert str(segredo) not in txt
    assert bia["motor"] == 2 and bia["mesa"]["pode_abrir"] and bia["adversarios"][0]["ops"][0]["aberta"] and bia["mesa"]["posicao"] is None
    ana = G.args_mesa(TB.visao(p, c, agora, "ana"), p, {}, agora)
    assert ana["mesa"]["posicao"]["stop"] == STOP_SECRETO and ana["mesa"]["pode_encerrar"] and ana["mesa"]["aposta_txt"] and {k: ana["inicial"][k] for k in EST} == EST and ana["inicial"]["marcas"] == {"niveis": [], "tendencias": [], "notas": [], "zonas": []}
    assert ana["propria"] is None and ana["operacao"] is None                             # o motor antigo não aparece na mesa


def test_tela_mostra_o_ativo_e_o_horario_mas_nunca_a_data_do_historico():
    import re
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    for agora in (p["t_fase"] - 1, ag(p, 5)):                         # na análise e no replay
        a = G.args_mesa(TB.visao(p, c, agora, "ana"), p, {}, agora)
        txt = json.dumps(a, default=str)
        assert a["ticker"] == "TEST3"
        assert "2026" not in txt and not re.search(r"\d{4}-\d{2}-\d{2}|\d{2}/\d{2}", txt)     # nem ISO nem dd/mm
        assert all(re.fullmatch(r"\d{2}:\d{2}", k["t"]) for k in a["candles"])
        dias = [k["d"] for k in a["candles"]]
        assert dias[0] == 1 and dias == sorted(dias) and dias[-1] > 1          # o dia da partida avança, sem dizer qual é
    assert a["candles"][0]["t"] == "10:00" and a["candles"][-1]["d"] == TB.candles_sem_data(c["candles"])[len(a["candles"]) - 1]["d"]
    assert TB.rotulo_horario(a["candles"][0]) == "D1 10:00"


def test_placar_ordena_pelo_resultado_da_rodada_e_destaca_voce_sem_vazar_o_adversario():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="alta", stop=STOP_SECRETO, alvo=ALVO_SECRETO)
    agora = ag(p, 8)
    pb = G.args_mesa(TB.visao(p, c, agora, "bia"), p, {}, agora)["placar"]
    assert pb["rodada"] == "1/5" and [j["rotulo"] for j in pb["jogadores"]] == ["Jogador 1", "Você"]
    assert pb["jogadores"][0]["pos"] == 1 and pb["jogadores"][0]["cor"] == "up" and pb["jogadores"][0]["txt"].startswith("+")
    assert pb["jogadores"][1] == {"rotulo": "Você", "pct": 0.0, "voce": True, "pos": 2, "txt": "0,00%", "cor": "zero"}
    assert str(STOP_SECRETO) not in json.dumps(pb) and str(ALVO_SECRETO) not in json.dumps(pb)
    pa = G.args_mesa(TB.visao(p, c, agora, "ana"), p, {}, agora)["placar"]
    assert pa["jogadores"][0]["voce"] and pa["jogadores"][0]["pct"] == pytest.approx(pb["jogadores"][0]["pct"])   # mesmo número visto pelos dois lados


def test_ritmo_de_2_5_segundos_vem_do_servidor_e_para_na_pausa():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    t = p["t_fase"]
    assert G.prox_revelacao_s(p, t + 1.0) == pytest.approx(1.5)
    assert G.args_mesa(TB.visao(p, c, t + 1.0, "ana"), p, {}, t + 1.0)["prox_ms"] == 1500
    TB.pausar(p, t + 6.0, {c["id"]: c})
    assert G.prox_revelacao_s(p, t + 9.0) is None and G.args_mesa(TB.visao(p, c, t + 9.0, "ana"), p, {}, t + 9.0)["pausada"]


def test_evento_acao_passa_so_campos_permitidos_e_n_rev_e_ordem_continuam_do_servidor():
    assert G.acao_de({"tipo": "mercado", "direcao": "alta", "aid": "x", "n_rev": 0, "ordem": 7, "t": 1, "jogador": "bia", "stop": 9.5, "extra": [1]}) == \
        {"tipo": "mercado", "direcao": "alta", "aid": "x", "stop": 9.5}
    assert G.acao_de("lixo") == {} and G.acao_de({"tipo": ["a"]}) == {} and G.acao_de({"preco": True}) == {}
    c = _cenario(fn_replay=_sobe)
    p = _partida(c)
    est = {}
    jog = "ana"
    ev = {"seq": 1, "evento": "acao", "dados": {"tipo": "mercado", "direcao": "alta", "aid": "k1", "n_rev": 0, "jogador": "bia"}}
    assert G.processar(p, ev, est, jog, 10.0, ag(p, 6), None, c) and est["erro"] == ""
    a = p["acoes"][0]
    assert a["jogador"] == "ana" and a["n_rev"] == 6 and a["ordem"] == 1                  # nada do que o navegador mandou em n_rev/jogador valeu
    assert not G.processar(p, ev, est, jog, 10.0, ag(p, 6), None, c) and len(p["acoes"]) == 1       # mesmo seq: ignorado
    ev2 = {"seq": 2, "evento": "acao", "dados": {"tipo": "mercado", "direcao": "baixa", "aid": "k2"}}
    G.processar(p, ev2, est, jog, 10.0, ag(p, 7), None, c)
    assert "posição aberta" in est["erro"] and est["erro_seq"] == 2 and len(p["acoes"]) == 1       # recusado e mostrado ao jogador, sem gravar


def test_evento_acao_via_ops_vai_para_o_banco_da_sala():
    with sala_online() as (pid, _):
        t = _comecar_replay(pid)
        p = OL._row(pid)["dados"]["p"]
        est = {}
        G.processar(p, {"seq": 1, "evento": "acao", "dados": {"tipo": "mercado", "direcao": "alta", "aid": "z"}}, est, EMAILS[0], 10.0, t + 7.6, OL.Ops(pid, EMAILS[0]))
        assert est["erro"] == "" and len(OL._row(pid)["dados"]["p"]["acoes"]) == 1


def test_resultado_da_mesa_mostra_varias_operacoes_e_avisa_que_a_perda_pode_passar_de_1_por_cento():
    c = _cenario(fn_replay=_degraus)
    p = _partida(c)
    _tres_perdas(c, p)
    fim(p, c)
    v = TB.visao(p, c, p["t_fase"] + 1, "ana")
    pr = G.payload_resultado(v, p)
    assert pr["executada"] and pr["n_ops"] == 3 and pr["pontos"] < 0 and pr["r"] is None and pr["faixa"]
    assert pr["faixa"] == "faixa_derrota"                                               # três perdas: faixa de derrota (e não "empate técnico")
    assert pr["fin"]["cor"] == "down" and "3 operações" in pr["fin"]["t1"] and "pode passar de 1%" in pr["fin"]["nota"]
    assert any(t == "Operação 3" for t, _ in pr["linhas"]) and any(t == "Pontos" for t, _ in pr["linhas"])
    vb = G.payload_resultado(TB.visao(p, c, p["t_fase"] + 1, "bia"), p)
    assert vb["executada"] is False and vb["pontos"] == 0.0 and vb["faixa"] == "faixa_empate"   # quem não operou: empate de verdade


# ====================================================================================================================================
# TELA STREAMLIT · lógica do modo individual e do seletor de formato (Streamlit falso: só o que não é desenho)
# ====================================================================================================================================
import sys
import types


@contextlib.contextmanager
def app_falso(jog="ana@x.com", pat=100000.0, caixa=100000.0):
    from unittest import mock
    fake = mock.MagicMock()
    fake.session_state = {}
    fake.fragment = lambda *a, **k: (lambda f: f)                                         # @st.fragment(...) deixa a função como está
    fake.cache_data = fake.cache_resource = lambda *a, **k: (lambda f: f)
    antigos = {n: sys.modules.get(n) for n in ("streamlit", "streamlit.components", "streamlit.components.v1", "trader_battle_app")}
    for n in ("streamlit", "streamlit.components", "streamlit.components.v1"):
        sys.modules[n] = fake
    sys.modules.pop("trader_battle_app", None)
    try:
        import trader_battle_app as APP
        import trader_dados as _TD
        _orig = _TD.escolher_corrida
        _TD.escolher_corrida = lambda f, s, banco=None, permitir_demo=False: _TD.demo_corrida(f, s)   # sem banco de cenários reais no teste
        with banco_isolado(), livro(pat=pat, caixa=caixa) as lanc:
            APP._jogador = lambda: jog
            APP._conta = lambda: {"id": "c-" + jog}
            yield APP, lanc
    finally:
        import trader_dados as _TD
        if "_orig" in locals():
            _TD.escolher_corrida = _orig
        for n, m in antigos.items():
            if m is None:
                sys.modules.pop(n, None)
            else:
                sys.modules[n] = m


def test_app_individual_inicia_a_partida_corrida_na_duracao_escolhida_com_5_por_cento_do_caixa():
    with app_falso(pat=300000.0, caixa=200000.0) as (APP, _):
        for f, sp in TB.CORRIDAS.items():
            APP._ss().clear()
            APP._ss()["tb_corrida"] = f
            APP._iniciar()
            p = APP._partida()
            assert p is not None and TB.qtd_de(p) and p["tf"] == sp["tf"] and TB.cfg_de(p)["rodadas"] == 1
            assert p["stakes"]["1:ana@x.com"] == {"stake": 10000.0, "pat": 300000.0}             # 5% de T$ 200.000 de caixa livre
        APP._ss().clear()
        APP._iniciar()
        assert TB.cfg_de(APP._partida())["formato"] == "intermediaria"                       # padrão (o recomendado)


def test_app_sem_conta_nao_inicia_partida():
    with app_falso(jog="") as (APP, lanc):
        APP._ss()["tb_tf"] = "15m"
        APP._iniciar()
        assert APP._partida() is None and "Entre na sua conta" in APP._ss()["tb_erro"] and lanc == {}


def test_app_sem_caixa_nao_inicia_e_mostra_a_mensagem():
    with app_falso(pat=100000.0, caixa=10.0) as (APP, _):
        APP._ss()["tb_tf"] = "15m"
        APP._iniciar()
        assert APP._partida() is None and "livres no caixa" in APP._ss()["tb_erro"]


def test_app_individual_resultado_da_partida_corrida_volta_para_a_carteira_uma_vez():
    with app_falso(pat=300000.0, caixa=200000.0) as (APP, lanc):
        APP._ss()["tb_corrida"] = "rapida"
        APP._iniciar()
        p = APP._partida()
        cen = APP._cen()[p["cenarios"][0]]
        TB.salvar_estrategia(p, "ana@x.com", dict(EST), None, 10.0, T0 + 1)
        TB.iniciar_replay(p, "ana@x.com", T0 + 2)
        TB.registrar_acao(p, cen, "ana@x.com", {"tipo": "mercado", "direcao": "alta", "q": 100, "aid": "1"}, ag(p, 3))
        TB.avancar(p, p["t_fase"] + TB.cfg_de(p)["t_replay_s"] + 1, {cen["id"]: cen})     # fim da partida
        APP._liquidar(p)
        APP._liquidar(p)
        pnl = p["resultados"]["1:ana@x.com"]["fin"]["pnl"]
        assert len(lanc) == (1 if pnl else 0)


def test_app_formatos_so_oferece_o_que_existe_e_rotulos():
    with app_falso() as (APP, _):
        assert APP._formatos("15m") == ["rapida", "normal", "longa"] and APP._formato("15m") == "normal"
        APP._ss()["tb_fmt_15m"] = "longa"
        assert APP._formato("15m") == "longa"
        APP._ss()["tb_fmts_1h"] = ["rapida", "normal"]                                     # 1h só com cenários antigos: Longa não existe
        APP._ss()["tb_fmt_1h"] = "longa"
        assert APP._formato("1h") == "normal"                                              # escolha inválida cai no padrão, não quebra
        assert APP._rot_formato("rapida") == "Rápida · 3 rodadas" and "anteriores" in APP._rot_formato(None)


def test_app_mesa_sem_componente_mostra_aviso_e_nao_cai_na_tela_classica():
    with app_falso() as (APP, _):
        APP._ss()["tb_tf"] = "15m"
        APP._iniciar()
        APP._ss()["tb_sem_mesa"] = True
        APP.TG.disponivel = lambda: True
        APP.st.markdown.reset_mock()
        APP.st.button.reset_mock()
        APP.pagina_trader()
        txt = " ".join(str(c) for c in APP.st.markdown.call_args_list)
        assert "não carregou" in txt and APP.st.button.call_args[1]["key"] == "tb_sem_mesa_sair"


# ====================================================================================================================================
# CENÁRIOS · estratégia aditiva do 1h (nada antigo é alterado ou apagado)
# ====================================================================================================================================
import pandas as pd

import trader_dados as TD


class BancoCfg:
    """Banco falso só com a configuração (cfg_ler / cfg_gravar), como o trader_dados usa."""
    def __init__(self):
        self.d = {}

    def cfg_ler(self, chave):
        return self.d.get(chave, {})

    def cfg_gravar(self, chave, valor):
        self.d[chave] = json.loads(json.dumps(valor))


def _df_1h(n, dias_uteis_de_8=True, inicio="2025-03-03 10:00"):
    """DataFrame de candles de 1h, 8 por pregão (10h–17h), só dias úteis, sem buracos."""
    idx, t = [], pd.Timestamp(inicio)
    while len(idx) < n:
        if t.weekday() < 5 and 10 <= t.hour <= 17:
            idx.append(t)
        t += pd.Timedelta(hours=1)
        if t.hour > 17:
            t = (t + pd.Timedelta(days=1)).replace(hour=10)
    return pd.DataFrame({"Open": 10.0, "High": 10.1, "Low": 9.9, "Close": 10.0, "Volume": 1000.0}, index=pd.DatetimeIndex(idx))


def test_janelas_1h_de_24_candles_precisam_de_340_candles_e_de_mais_dias_que_o_formato_antigo():
    df = _df_1h(345)                                                                       # 345 candles ≈ 43 pregões ≈ 60 dias corridos
    assert TD.janelas(_df_1h(300), "1h", 3, b24=True) == []                                # 300 candles não bastam para 340
    antigo = TD.janelas(_df_1h(300), "1h", 3)
    assert antigo and antigo[0][1] - antigo[0][0] == 260                                   # o formato antigo continua pedindo 260
    novo = TD.janelas(df, "1h", 3, b24=True)
    assert novo and all(j - i == 340 for i, j in novo)
    dias = (df.index[novo[0][1] - 1] - df.index[novo[0][0]]).days
    assert 56 <= dias <= 70                                                                 # cabe no limite antigo aqui; o novo (90) dá folga para feriados
    assert TD.MAX_DIAS_B24["1h"] == 90 and TB.TIMEFRAMES["1h"]["max_dias"] == 70            # o limite do formato antigo não foi alterado


def test_cenario_novo_do_1h_tem_id_proprio_e_o_do_15m_continua_identico():
    df = _df_1h(345)
    (i, j), = TD.janelas(df, "1h", 1, b24=True)
    antigo_df = _df_1h(300)
    (ia, ja), = TD.janelas(antigo_df, "1h", 1)
    a = TD.cenario_de_df(antigo_df, ia, ja, "PETR4", "1h", "2026-01-01")
    n = TD.cenario_de_df(df, i, j, "PETR4", "1h", "2026-01-01", b24=True)
    assert n["id"] == a["id"].replace(a["id"][-5:], "") + "a100-b24" or n["id"].endswith("-b24")
    assert not a["id"].endswith("-b24") and n["id"] != a["id"] and TB.validar_cenario(n)[0] and TB.validar_cenario(a)[0]
    assert TB.capacidade_rodadas(a) == 6 and TB.capacidade_rodadas(n) == 10
    c15 = TD.demo_cenario("15m", 5)
    assert TD.demo_cenario("15m", 5, b24=True)["id"] == c15["id"] == "DEMO-15m-5"        # 15m: bloco já era 24, nada muda


def test_salvar_o_novo_nunca_expulsa_os_cenarios_antigos_mesmo_no_teto():
    b = BancoCfg()
    antigos = []
    for k in range(TD.MAX_POR_FUSO):                                                      # 80 antigos: o teto cheio
        c = _cenario("1h", fn_replay=_sobe, tam_bloco=16)
        c["id"], c["demo"] = f"ANT-{k:03d}", False
        c["candles"] = [{**x, "t": (datetime(2024, 1, 1) + timedelta(days=k, hours=i)).isoformat()} for i, x in enumerate(c["candles"])]
        antigos.append(c)
    assert TD.salvar("1h", antigos, b) == TD.MAX_POR_FUSO
    novos = []
    for k in range(3):
        c = _cenario("1h", fn_replay=_sobe)
        c["id"], c["demo"] = f"NOVO-{k}-b24", False
        c["candles"] = [{**x, "t": (datetime(2025, 1, 1) + timedelta(days=k, hours=i)).isoformat()} for i, x in enumerate(c["candles"])]
        novos.append(c)
    assert TD.salvar("1h", TD.listar("1h", b) + novos, b) == TD.MAX_POR_FUSO + 3          # os 80 antigos continuam, os 3 novos entraram
    ids = {c["id"] for c in TD.listar("1h", b)}
    assert all(f"ANT-{k:03d}" in ids for k in range(TD.MAX_POR_FUSO)) and {f"NOVO-{k}-b24" for k in range(3)} <= ids


def test_escolher_por_rodadas_respeita_a_capacidade_e_nunca_serve_cenario_que_nao_comporta():
    b = BancoCfg()
    antigo = _cenario("1h", fn_replay=_sobe, tam_bloco=16)
    antigo["id"], antigo["demo"] = "ANT-1", False
    TD.salvar("1h", [antigo], b)
    assert TD.formatos_disponiveis("1h", b) == ["rapida", "normal"]
    assert TD.escolher("1h", 1, b, rodadas=5)["id"] == "ANT-1"
    with pytest.raises(TB.ErroTrader, match="Ainda não há cenários reais"):
        TD.escolher("1h", 1, b, rodadas=10)                                                # nunca cai em demonstração escondida quando há reais
    novo = _cenario("1h", fn_replay=_sobe)
    novo["id"], novo["demo"] = "NOVO-1-b24", False
    novo["candles"] = [{**x, "t": (datetime(2025, 1, 1) + timedelta(hours=i)).isoformat()} for i, x in enumerate(novo["candles"])]
    TD.salvar("1h", TD.listar("1h", b) + [novo], b)
    assert TD.formatos_disponiveis("1h", b) == ["rapida", "normal", "longa"] and TD.escolher("1h", 1, b, rodadas=10)["id"] == "NOVO-1-b24"
    assert TD.escolher("1h", 1, BancoCfg(), rodadas=10)["demo"] and TD.escolher("1h", 1, BancoCfg())["id"].startswith("DEMO-1h-")   # sem reais: demonstração, como antes


def test_cenario_demo_antigo_em_andamento_continua_identico_ao_de_antes():
    """Uma partida antiga em demonstração resolve o cenário pela semente: os candles têm que ser exatamente os mesmos de antes (260 no 1h)."""
    antigo = TD.demo_cenario("1h", 4242)
    novo = TD.demo_cenario("1h", 4242, b24=True)
    assert len(antigo["candles"]) == 260 and len(novo["candles"]) == 340 and novo["candles"][:260] == antigo["candles"] and antigo["id"] == "DEMO-1h-4242"
    assert TD.resolver({"id": "DEMO-1h-4242", "demo": True, "semente": 4242, "tf": "1h"})["candles"] == antigo["candles"]
    assert len(TD.resolver({"id": "DEMO-1h-4242-b24", "demo": True, "semente": 4242, "tf": "1h"})["candles"]) == 340


# ====================================================================================================================================
# ISOLAMENTO · estes testes nunca podem abrir, criar ou ler o banco real do projeto (usuarios.db)
# ====================================================================================================================================


def test_isolamento_restaura_o_banco_mesmo_quando_o_teste_falha():
    anterior = (banco._caminho_sqlite, banco._forcar_sqlite)
    with pytest.raises(RuntimeError):
        with banco_isolado() as pasta:
            assert banco._caminho_sqlite != anterior[0] and os.path.isdir(pasta)
            raise RuntimeError("falha no meio do teste")
    assert (banco._caminho_sqlite, banco._forcar_sqlite) == anterior and not os.path.exists(pasta)         # restaurado e pasta temporária apagada


# ====================================================================================================================================
# LIMITE DE PERDA DA RODADA · 3% do patrimônio do início da rodada (realizado + não realizado) · gate de caixa · gaps · privacidade
# ====================================================================================================================================
LIM = TB.LIMITE_PERDA_X


def _spike(i, alto=45.0):
    """Rodada 1: 4 candles planos em 10; o candle 4 sobe até `alto` e fica lá."""
    if i < 4:
        return 10.0, 10.05, 9.95, 10.0
    return (10.0, alto, 10.0, alto) if i == 4 else (alto, alto, alto, alto)


def _gap(i):
    return (10.0, 10.05, 9.95, 10.0) if i < 4 else (60.0, 60.0, 60.0, 60.0)


def test_limite_e_derivado_de_3_por_cento_do_patrimonio_sobre_1_por_cento_da_aposta():
    assert TB.LIMITE_PERDA_PCT_PAT == 0.03 and TB.PCT_APOSTA == 0.01 and LIM == pytest.approx(3.0)


def test_limite_01_venda_sem_stop_sai_no_preco_do_limite():
    s = sim([K(10.0, 45.0, 10.0, 45.0)], [A("mercado", 0, 1, direcao="baixa")])
    t = s["trades"][0]
    assert t["saida"] == pytest.approx(40.0) and t["ret"] == pytest.approx(-3.0) and t["motivo"] == "limite" and s["bloq"] and s["pos"] is None


def test_limite_02_gap_alem_do_limite_sai_na_abertura_e_o_prejuizo_nao_e_truncado():
    s = sim([K(50.0, 50.0, 50.0, 50.0)], [A("mercado", 0, 1, direcao="baixa")])
    t = s["trades"][0]
    assert t["saida"] == 50.0 and t["ret"] == pytest.approx(-4.0) and t["motivo"] == "limite" and s["bloq"]


def test_limite_03_considera_realizado_mais_nao_realizado():
    cand = [K(10.0, 30.0, 10.0, 30.0), K(30.0, 50.0, 30.0, 50.0), K(50.0, 70.0, 50.0, 70.0)]
    acoes = [A("mercado", 0, 1, direcao="baixa"), A("encerrar", 1, 2), A("mercado", 1, 3, direcao="baixa")]
    antes = sim(cand[:2], acoes)                                                            # realizado −2,0; 2ª venda aberta em 30
    assert antes["trades"][0]["ret"] == pytest.approx(-2.0) and not antes["bloq"] and antes["pos"]["entrada"] == 30.0
    assert TB.preco_limite_perda(antes["pos"], -2.0) == pytest.approx(60.0)                  # 30 × (1 + 3 − 2)
    s = sim(cand, acoes)
    assert [t["motivo"] for t in s["trades"]] == ["manual", "limite"] and s["trades"][1]["saida"] == pytest.approx(60.0)
    assert sum(t["ret"] for t in s["trades"]) == pytest.approx(-3.0) and s["bloq"]


def test_limite_03b_ganho_realizado_afasta_o_limite():
    cand = [K(10.0, 10.0, 5.0, 5.0), K(5.0, 22.0, 5.0, 22.0)]
    acoes = [A("mercado", 0, 1, direcao="baixa"), A("encerrar", 1, 2), A("mercado", 1, 3, direcao="baixa")]
    s = sim(cand[:1], acoes[:2])
    assert s["trades"][0]["ret"] == pytest.approx(0.5)                                      # +0,5 realizado
    s = sim(cand, acoes)
    assert s["pos"] is not None and not s["bloq"]                                           # 2ª venda a 5: limite em 5·(1+3+0,5)=22,5 → 22 não alcança


def test_limite_04_stop_do_jogador_mais_perto_vale_e_stop_alem_do_limite_perde_para_o_limite():
    cand = [K(10.0, 45.0, 10.0, 45.0)]
    s = sim(cand, [A("mercado", 0, 1, direcao="baixa", stop=12.0)])
    assert s["trades"][0]["motivo"] == "stop" and s["trades"][0]["saida"] == 12.0 and not s["bloq"]
    s = sim(cand, [A("mercado", 0, 1, direcao="baixa", stop=50.0)])
    assert s["trades"][0]["motivo"] == "limite" and s["trades"][0]["saida"] == pytest.approx(40.0)
    s = sim(cand, [A("mercado", 0, 1, direcao="baixa", stop=40.0)])                           # empate: vale o stop do jogador
    assert s["trades"][0]["motivo"] == "stop"


def test_limite_05_depois_do_limite_nenhuma_entrada_nova_no_simulador_e_no_registro():
    cand = [K(10.0, 45.0, 10.0, 45.0), K(45.0)]
    acoes = [A("mercado", 0, 1, direcao="baixa"), A("mercado", 1, 2, direcao="alta"), A("limite", 1, 3, direcao="alta", preco=40.0), A("stop_entrada", 1, 4, direcao="alta", preco=46.0)]
    s = sim(cand, acoes)
    assert len(s["trades"]) == 1 and s["pos"] is None and s["pend"] is None and s["ignoradas"] == 3 and s["bloq"]
    c = _cenario(fn_replay=_spike)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="baixa")
    m = TB.visao(p, c, ag(p, 6), "ana")["mesa"]
    assert m["limite"]["bloqueado"] and not m["pode_abrir"] and m["n_encerradas"] == 1
    n = len(p["acoes"])
    for tipo, extra in (("mercado", {}), ("limite", {"preco": 40.0}), ("stop_entrada", {"preco": 46.0})):
        with pytest.raises(TB.ErroTrader, match="limite de perda"):
            op(p, c, "ana", 6, tipo, "x" + tipo, direcao="alta", **extra)
    assert len(p["acoes"]) == n                                                              # recusada não grava
    op(p, c, "bia", 6, "mercado", "b1", direcao="alta")                                       # o outro jogador não é afetado


def test_limite_06_cancelamento_defensivo_das_pendentes_ao_atingir_o_limite():
    st = TB.simular_jogador([], [], 10.0)
    TB._abrir(st, "baixa", 10.0, 0, 0, "mercado", None, None)
    st["pend"] = {"tipo": "limite", "direcao": "alta", "preco": 9.0, "stop": None, "alvo": None, "ordem": 1}
    TB._fechar(st, 40.0, 0, "manual")                                                         # perda realizada de −3,0 por saída manual
    assert st["pend"] is None and st["bloq"] and st["pos"] is None


def test_limite_07_compra_com_limite_pequeno_gap_e_nivel_invalido():
    s = TB.simular_jogador([K(10.0, 10.0, 4.0, 4.0)], [A("mercado", 0, 1, direcao="alta")], 10.0, limite_x=0.5)
    assert s["trades"][0]["saida"] == pytest.approx(5.0) and s["trades"][0]["motivo"] == "limite"
    s = TB.simular_jogador([K(4.0, 4.0, 4.0, 4.0)], [A("mercado", 0, 1, direcao="alta")], 10.0, limite_x=0.5)
    assert s["trades"][0]["saida"] == 4.0 and s["trades"][0]["ret"] == pytest.approx(-0.6)
    pos = {"direcao": "alta", "entrada": 10.0}
    assert TB.preco_limite_perda(pos, 0.0, 1.5) is None and TB.preco_limite_perda(None, 0.0) is None
    assert TB.preco_limite_perda(pos, 0.0, 0.5) == pytest.approx(5.0)
    assert TB.preco_limite_perda({"direcao": "baixa", "entrada": 10.0}, 0.0, 3.0) == pytest.approx(40.0)


def test_limite_07b_compra_nunca_perde_mais_que_a_aposta_por_operacao_mesmo_sem_stop():
    s = sim([K(10.0, 10.0, 0.5, 0.5)], [A("mercado", 0, 1, direcao="alta")], final=True)
    assert s["trades"][0]["ret"] == pytest.approx(-0.95) and not s["bloq"]                   # sozinha, a compra não alcança −3,0


def test_limite_08_fluxo_completo_pnl_menos_3_por_cento_pontos_negativos_e_reset_na_rodada_seguinte():
    c = _cenario(fn_replay=_spike)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="baixa")
    fim(p, c)
    r = p["resultados"]["1:ana"]
    assert r["limite_atingido"] is True and r["fin"]["pnl"] == pytest.approx(-3000.0) and r["fin"]["pct_pat"] == pytest.approx(-3.0)
    assert r["pontos"] < 0 and p["pontos"]["ana"] == r["pontos"]
    assert any("Limite de perda" in t for t, _ in TB.explicar_mesa(r)) and any("Limite de perda" in t for t, _ in TB.explicar(r))
    assert p["resultados"]["1:bia"]["limite_atingido"] is False
    TB.avancar(p, p["t_fase"] + TB.T_RESULTADO_S + 0.1, {c["id"]: c})
    for j in ("ana", "bia"):
        TB.salvar_estrategia(p, j, dict(EST), None, 10.0, p["t_fase"] + 1)
    assert p["rodada"] == 2 and p["fase"] == "replay"
    a, nova = op(p, c, "ana", 3, "mercado", "r2", direcao="baixa")                           # rodada 2: o limite recomeça do zero
    assert nova and TB.visao(p, c, ag(p, 3), "ana")["mesa"]["limite"]["bloqueado"] is False


def test_limite_09_gap_no_fluxo_perda_real_de_5_por_cento_sem_truncar():
    c = _cenario(fn_replay=_gap)
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="baixa")
    fim(p, c)
    r = p["resultados"]["1:ana"]
    assert r["limite_atingido"] and r["operacoes"][0]["saida"] == 60.0 and r["fin"]["pnl"] == pytest.approx(-5000.0) and r["fin"]["pct_pat"] == pytest.approx(-5.0)


def test_limite_10_privacidade_o_adversario_nao_recebe_preco_nem_estado_do_limite_do_outro():
    c = _cenario(fn_replay=lambda i: (12.3456, 12.40, 12.30, 12.3456))
    p = _partida(c)
    op(p, c, "ana", 3, "mercado", "1", direcao="baixa")
    agora = ag(p, 5)
    propria = TB.visao(p, c, agora, "ana")["mesa"]["limite"]
    assert propria["preco"] == pytest.approx(12.3456 * 4)
    bia = TB.visao(p, c, agora, "bia")
    txt = json.dumps(bia, default=str) + json.dumps(G.args_mesa(bia, p, {}, agora), default=str)
    assert str(propria["preco"]) not in txt and str(round(propria["preco"], 2)) not in txt and str(round(propria["preco"], 4)) not in txt
    assert bia["mesa"]["limite"]["preco"] is None and bia["mesa"]["limite"]["bloqueado"] is False
    assert set(bia["adversarios"][0]["ops"][0]) == {"direcao", "preco_entrada", "indice_entrada", "aberta", "preco_saida", "indice_saida"}


def test_limite_12a_decisao_6_stop_de_entrada_de_venda_com_gap_abre_na_abertura_e_compra_nao_dispara_caindo():
    s = sim([K(10.0), K(8.0, 8.2, 7.9, 8.1)], [A("stop_entrada", 1, 1, direcao="baixa", preco=9.0)])
    assert s["pos"]["entrada"] == 8.0 and s["pos"]["direcao"] == "baixa"
    s = sim([K(10.0), K(10.0, 10.1, 9.0, 9.2)], [A("stop_entrada", 1, 1, direcao="alta", preco=10.5)])
    assert s["pos"] is None and s["pend"] is not None


def test_limite_12b_decisao_7_nao_ha_botao_nem_caminho_de_pausa_para_o_jogador():
    import pathlib
    raiz = pathlib.Path(__file__).parent
    html = (raiz / "trader_front" / "index.html").read_text(encoding="utf-8").lower()
    import re
    assert not re.search(r"<button[^>]*(paus|pause)", html) and not re.search(r"<button[^>]*>[^<]*paus", html) and "pausa t" in html     # só o aviso de pausa técnica, sem botão
    assert "pausar" not in (raiz / "trader_battle_app.py").read_text(encoding="utf-8")
    import inspect
    assert "pausar" not in inspect.getsource(G.processar) and "pausar" not in inspect.getsource(OL.Ops)


# ------------------------------------------------------------------ gate de caixa de 3% e o caixa nunca ajustado artificialmente
def test_caixa_minimo_de_3_por_cento_para_a_mesa_e_1_por_cento_para_as_regras_antigas():
    with livro(pat=100000.0, caixa=2999.0):
        with pytest.raises(TCA.SemSaldo, match="3%"):
            TCA.aposta_de("a@x.com", mesa=True)
        assert TCA.aposta_de("a@x.com")["stake"] == 1000.0                                    # regras antigas: 1% basta
    with livro(pat=100000.0, caixa=3000.0):
        assert TCA.aposta_de("a@x.com", mesa=True)["stake"] == 1000.0
    with livro(pat=100000.0, caixa=2000.0):
        a = TCA.aposta_rodada("a@x.com")                                                      # rodadas seguintes: não derruba a partida, só zera a aposta
        assert a["stake"] == 0.0 and a["sem_saldo"]


def test_online_sala_da_mesa_recusa_quem_tem_menos_de_3_por_cento_e_sala_antiga_continua_com_1_por_cento():
    with banco_isolado():
        _contas()
        with livro(pat=100000.0, caixa=2000.0):
            r = OL.criar_sala(EMAILS[0], "15m", TS, "rapida")
            OL.entrar_na_sala(EMAILS[1], r["codigo"], TS + 1)
            with pytest.raises(OL.ErroSala, match="3%"):
                OL.iniciar(r["id"], EMAILS[0], TS + 2)
            assert OL._row(r["id"])["dados"].get("p") is None                                  # nada foi iniciado
    with banco_isolado():                                                                      # sala criada antes da mesa (sem formato): regra antiga de 1%
        _contas()
        with livro(pat=100000.0, caixa=2000.0):
            r = OL.criar_sala(EMAILS[0], "15m", TS, "rapida")
            OL.entrar_na_sala(EMAILS[1], r["codigo"], TS + 1)
            d = OL._row(r["id"])["dados"]
            d["sala"].pop("formato")
            banco._atualizar_n("tb_partidas", {"id": r["id"]}, {"dados": banco._js(d)})
            OL.iniciar(r["id"], EMAILS[0], TS + 2)
            assert OL.ler(r["id"], EMAILS[0], TS + 3)["v"]["motor"] == 1


def test_app_individual_sem_caixa_livre_suficiente_nao_inicia_a_partida():
    with app_falso(pat=100000.0, caixa=1000.0) as (APP, _):
        APP._ss().clear()
        APP._iniciar()
        assert "pelo menos" in APP._ss().get("tb_erro", "") and "tb_p" not in APP._ss()


def test_caixa_com_gap_o_prejuizo_real_e_lancado_inteiro_sem_ajuste_artificial():
    """Com exatamente 3% de caixa: o limite sem gap zera o caixa (nunca negativo); com gap a perda real passa de 3% e é lançada INTEIRA (o caixa pode ficar negativo)."""
    for fn, perda, caixa_final in ((_spike, -3000.0, 0.0), (_gap, -5000.0, -2000.0)):
        c = _cenario(fn_replay=fn)
        p = _partida(c)
        op(p, c, "ana", 3, "mercado", "1", direcao="baixa")
        fim(p, c)
        with livro(pat=100000.0, caixa=3000.0) as lanc:
            TCA.liquidar(p)
            assert lanc[f"trader:{p['id']}:1:ana"]["valor"] == pytest.approx(perda)
            assert TCA.situacao("ana")["caixa"] == pytest.approx(caixa_final)


# ====================================================================================================================================
# FIM DE RODADA / FIM DE PARTIDA · placar por pontos, retorno, tela final sem e-mail
# ====================================================================================================================================
def _rodada_com_vencedor():
    c = _cenario(fn_replay=_sobe)
    p = _partida(c, jogs=("ana@x.com", "bia@x.com", "caio@x.com"), formato="rapida")
    op(p, c, "ana@x.com", 2, "mercado", "1", direcao="alta")                  # sobe: ana ganha
    op(p, c, "bia@x.com", 2, "mercado", "1", direcao="baixa")                 # bia perde; caio não opera
    fim(p, c)
    return c, p


def test_placar_da_rodada_fechada_ordena_por_pontos_e_traz_o_retorno():
    c, p = _rodada_com_vencedor()
    agora = p["t_fase"] + 0.5
    a = G.args_mesa(TB.visao(p, c, agora, "caio@x.com"), p, {}, agora)
    pl = a["placar"]
    assert p["fase"] == "resultado" and pl["fechada"]
    assert [j["rotulo"] for j in pl["jogadores"]] == ["Jogador 1", "Você", "Jogador 2"]
    pts = [j["pts"] for j in pl["jogadores"]]
    assert pts == sorted(pts, reverse=True) and pts[0] > 0 > pts[2] and pl["jogadores"][1]["pts_txt"] == "0,0"
    assert pl["jogadores"][0]["cor"] == "up" and pl["jogadores"][2]["txt"].startswith("−")
    assert "@" not in json.dumps(a)                                                       # nunca o e-mail
    r = G.args_mesa(TB.visao(p, c, agora, "ana@x.com"), p, {}, agora)["resultado"]
    assert r["rodada_txt"] == "1/3" and r["ret_cor"] == "up" and r["ret_txt"].startswith("+") and r["ret_val"].startswith("+T$")
    assert r["ret_txt"] == f"+{TB.retorno_pct(p['resultados']['1:ana@x.com']):.2f}%".replace(".", ",")


def test_placar_final_soma_pontos_e_retorno_de_todas_as_rodadas():
    c, p = _rodada_com_vencedor()
    pl = TB.placar_final(p)
    assert [x["jog"] for x in pl] == ["ana@x.com", "caio@x.com", "bia@x.com"] and [x["pos"] for x in pl] == [1, 2, 3]
    assert pl[0]["pontos"] == round(p["pontos"]["ana@x.com"], 1) and pl[0]["ret_pct"] > 0 > pl[2]["ret_pct"] and pl[1]["ret_pct"] == 0.0
    assert TB.retorno_pct({"motor": 1}) is None


def test_tela_final_mostra_lugar_placar_e_analise_sem_email():
    c, p = _rodada_com_vencedor()
    with app_falso(jog="bia@x.com") as (APP, _):
        APP.st.markdown.reset_mock()
        APP._tela_final(TB.resumo_final(p, "bia@x.com"), None, True, ["TEST3"] * 3)
        txt = " ".join(str(x) for x in APP.st.markdown.call_args_list)
        assert "FIM DE PARTIDA" in txt and "3º lugar" in txt and "Placar da Batalha" in txt and "@" not in txt
        assert "tb-pr p3 eu" in txt and APP.ART.uri("trofeu")[:60] not in txt                               # troféu só para quem ganhou
        assert "tb-ri" in txt and "Sua leitura" in txt                                    # análise completa com o Raio-X no padrão do app
        APP.st.markdown.reset_mock()
        APP._tela_final(TB.resumo_final(p, "ana@x.com"), None, True, ["TEST3"] * 3)
        txt = " ".join(str(x) for x in APP.st.markdown.call_args_list)
        assert "1º lugar!" in txt and APP.ART.uri("trofeu")[:60] in txt


def test_sala_online_resultado_e_fim_montam_placar_e_resumo_so_pela_visao():
    """A sala online entrega ao app uma partida ENXUTA (sem jogadores nem resultados): placar e tela final precisam vir só de `visao`."""
    with sala_online() as (pid, _):
        with livro():
            t = _comecar_replay(pid)
            OL.agir(pid, EMAILS[0], {"tipo": "mercado", "direcao": "alta", "aid": "z1"}, t + 5)
            tr = t + 61                                                                    # rodada 1 fechada
            b = OL.ler(pid, EMAILS[1], tr)
            assert b["p"]["fase"] == "resultado" and "jogadores" not in b["p"]
            a = G.args_mesa(b["v"], b["p"], {}, tr)
            assert a["placar"]["fechada"] and {j["rotulo"] for j in a["placar"]["jogadores"]} == {"Você", "Jogador 1"} and "@" not in json.dumps(a)
            fim = None
            for k in range(2, 4):                                                          # rodadas 2 e 3 sem operar até o fim
                tk = tr + TB.T_RESULTADO_S + 1 + (k - 2) * (61 + TB.T_RESULTADO_S + 1)
                for e in EMAILS:
                    _leitura(pid, e, tk)
                fim = OL.ler(pid, EMAILS[1], tk + 61 + TB.T_RESULTADO_S + 1)
            assert fim["p"]["fase"] == "fim"
            fz = fim["v"]["final"]
            assert [x["rotulo"] for x in fz["placar"]] in (["Jogador 1", "Você"], ["Você", "Jogador 1"]) and len(fz["rodadas"]) == 3 and fz["raiox"]
            assert "@" not in json.dumps(fz)


# ====================================================================================================================================
# XP POR COLOCAÇÃO · única recompensa; nenhuma TickerCoin
# ====================================================================================================================================
def test_xp_por_colocacao_entre_quem_jogou():
    c, p = _rodada_com_vencedor()
    assert TB.xp_da_partida(p, "ana@x.com")["xp"] == 0                                    # partida ainda não terminou
    p["fase"] = "fim"
    xs = {j: TB.xp_da_partida(p, j) for j in p["jogadores"]}
    bonus = int(p["pontos"]["ana@x.com"] // TB.XP_POR_PONTOS)
    assert p["pontos"]["ana@x.com"] > 0 > p["pontos"]["bia@x.com"] and bonus > 0
    assert (xs["ana@x.com"]["xp"], xs["caio@x.com"]["xp"], xs["bia@x.com"]["xp"]) == (30 + bonus, 18, 10)     # pontuação negativa não tira XP
    assert xs["ana@x.com"]["pos"] == 1 and xs["ana@x.com"]["n"] == 3 and xs["ana@x.com"]["xp_pts"] == bonus and xs["bia@x.com"]["xp_pts"] == 0
    p["pontos"]["caio@x.com"] = p["pontos"]["ana@x.com"]                                   # empate divide a melhor colocação
    assert TB.xp_da_partida(p, "caio@x.com")["xp"] == TB.xp_da_partida(p, "ana@x.com")["xp"] == 30 + bonus


def test_xp_cresce_com_o_tamanho_da_sala_e_nunca_e_negativo():
    for n, tab in TB.XP_POSICAO.items():
        assert len(tab) == n and list(tab) == sorted(tab, reverse=True) and min(tab) > 0
    assert [TB.XP_POSICAO[n][0] for n in (2, 3, 4)] == sorted({TB.XP_POSICAO[n][0] for n in (2, 3, 4)}) and TB.XP_POSICAO[2][0] > TB.XP_SOLO
    c, p = _rodada_com_vencedor()
    p["fase"] = "fim"
    for pts in (-300.0, -0.1, 0.0, 9.9, 10.0, 250.0):
        p["pontos"]["bia@x.com"] = pts
        x = TB.xp_da_partida(p, "bia@x.com")
        assert x["xp"] >= 0 and x["xp_pts"] == max(0, int(pts // 10)) and x["xp"] == x["xp_pos"] + x["xp_pts"]


def test_xp_sala_com_fantasma_vale_como_solo_e_fantasma_nao_ganha():
    c, p = _rodada_com_vencedor()
    p["fase"] = "fim"
    for k in [k for k in p["estrategias"] if not k.endswith("ana@x.com")]:
        p["estrategias"][k] = {**p["estrategias"][k], "sem_registro": True}               # só a ana registrou leitura
    x = TB.xp_da_partida(p, "ana@x.com")
    assert (x["pos"], x["n"], x["xp_pos"]) == (None, 1, TB.XP_SOLO) and x["xp"] == TB.XP_SOLO + max(0, int(p["pontos"]["ana@x.com"] // 10))
    assert TB.xp_da_partida(p, "bia@x.com")["xp"] == 0


def test_pagar_xp_uma_vez_por_partida_com_limite_diario_e_sem_tickercoins():
    from unittest import mock
    import educacao as ED
    estado = {"p": ED.normalizar(None)}
    ea = types.SimpleNamespace(prog=lambda: estado["p"], _set=lambda p: estado.__setitem__("p", ED.normalizar(p)))
    with app_falso() as (APP, _), mock.patch.dict(sys.modules, {"educacao_app": ea}):
        import usuarios
        with mock.patch.object(usuarios, "usuario", return_value={"email": "ana@x.com"}):
            info = {"xp": 25, "pos": 1, "n": 3}
            assert APP._pagar_xp("p1", info) == {"xp": 25, "status": "pago"}
            assert APP._pagar_xp("p1", info) == {"xp": 25, "status": "pago"} and estado["p"]["jornada"]["xp"] == 25   # atualizar a página não paga de novo
            APP._pagar_xp("p2", info); APP._pagar_xp("p3", info)
            assert APP._pagar_xp("p4", info) == {"xp": 0, "status": "limite"} and estado["p"]["jornada"]["xp"] == 75
            assert APP._pagar_xp("p5", {"xp": 0}) == {"xp": 0, "status": "zero"}
            assert set(ED.normalizar(estado["p"])["trader_xp"]) == {"p1", "p2", "p3"}            # sobrevive à gravação no perfil
            assert "+25 XP" in APP._linha_xp(info, {"xp": 25, "status": "pago"}) and "1º lugar entre 3" in APP._linha_xp(info, {"xp": 25, "status": "pago"})
        with mock.patch.object(usuarios, "usuario", return_value=None):              # sem conta (o app nem abre assim): nada é creditado
            assert APP._pagar_xp("p9", {"xp": 25}) == {"xp": 0, "status": "erro"} and APP._linha_xp({}, {"status": "erro"}) == ""
    src = open("trader_battle_app.py", encoding="utf-8").read() + open("trader_battle.py", encoding="utf-8").read()
    import re
    assert not re.search(r"import\s+tickercoins|tickercoins\.|\bTC\.creditar", src)          # o Trader Battle nunca paga TickerCoins
