"""Cartas de padrão de candle (Martelo, Engolfo de Alta, Estrela Cadente): nunca ativam só pela aparência do candle.
Precisam do padrão (regras matemáticas), de uma região que o jogador marcou ANTES da partida, do candle FECHADO e das proporções da carta."""
import json

import pytest

import setups as SU
import setups_vivo as SV
import trader_battle as TB
import trader_dados as TD
from test_setups import A, B, T0, tick

DT = 4.0                                   # cada candle do gráfico dura 4 s no replay (3 passos de 4/3 s)


# ------------------------------------------------------------------ montagem
def candle(o, h, l, c, v=1000.0):
    return {"t": "x", "o": o, "h": h, "l": l, "c": c, "v": v}


def martelo(base=100.0):          # corpo pequeno no alto, sombra inferior longa, sombra superior curta
    return candle(base, base + 0.12, base - 1.0, base + 0.10)


def engolfo(base=100.0):          # dois candles: um de baixa e outro de alta que envolve o corpo do anterior
    return [candle(base + 0.5, base + 0.6, base - 0.1, base + 0.0), candle(base - 0.1, base + 0.9, base - 0.2, base + 0.7)]


def estrela(base=100.0):          # corpo pequeno embaixo, sombra superior longa, sombra inferior curta
    return candle(base, base + 1.0, base - 0.12, base - 0.10)


def regiao(tipo, lo, hi):
    return {"id": "r1", "tipo": tipo, "min": lo, "max": hi, "partida": "p", "criada_em": 0.0}


FUNDO = [candle(101, 101.3, 100.7, 101.1)] * 6          # histórico qualquer antes do padrão


# ------------------------------------------------------------------ o detector (cenários 1, 2, 5, 6, 7)
def test_1_martelo_fora_de_suporte_nao_ativa():
    v = FUNDO + [martelo()]
    assert SU.detectar("martelo", v, [regiao("suporte", 90.0, 91.0)]) is None            # a mínima (99) está longe do suporte
    assert SU.detectar("martelo", v, []) is None and SU.detectar("martelo", v) is None   # e sem região marcada nunca ativa


def test_2_martelo_em_suporte_mas_sem_as_proporcoes_nao_ativa():
    reg = [regiao("suporte", 98.5, 99.5)]
    assert SU.detectar("martelo", FUNDO + [martelo()], reg)                                # controle: este é válido
    sombra_curta = candle(100, 100.12, 99.85, 100.10)                                     # sombra inferior < 2x o corpo
    corpo_grande = candle(99.0, 100.1, 98.95, 100.0)                                     # corpo > 35% da amplitude
    sombra_alta = candle(100, 100.4, 99.0, 100.10)                                       # sombra superior grande
    fecha_embaixo = candle(100.0, 100.0, 99.0, 99.2)                                     # fecha na metade de baixo
    for ruim in (sombra_curta, corpo_grande, sombra_alta, fecha_embaixo):
        assert SU.detectar("martelo", FUNDO + [ruim], [regiao("suporte", ruim["l"] - 0.1, ruim["l"] + 0.1)]) is None


def test_5_engolfo_valido_fora_de_suporte_nao_ativa():
    v = FUNDO + engolfo()
    assert SU.detectar("engolfo_alta", v, [regiao("suporte", 99.7, 100.2)])               # controle: dentro do suporte, ativa
    assert SU.detectar("engolfo_alta", v, [regiao("suporte", 80.0, 81.0)]) is None


def test_engolfo_exige_corpo_envolvendo_por_completo_e_cores_certas():
    reg = [regiao("suporte", 99.7, 100.2)]
    a, b = engolfo()
    assert SU.detectar("engolfo_alta", FUNDO + [a, candle(b["o"], b["h"], b["l"], a["o"] - 0.05)], reg) is None   # o corpo atual não cobre todo o anterior
    assert SU.detectar("engolfo_alta", FUNDO + [candle(a["c"], a["h"], a["l"], a["o"]), b], reg) is None          # o anterior era de alta
    assert SU.detectar("engolfo_alta", FUNDO + [a, candle(b["c"], b["h"], b["l"], b["o"])], reg) is None          # o atual é de baixa


def test_6_estrela_cadente_fora_de_resistencia_nao_ativa():
    v = FUNDO + [estrela()]
    assert SU.detectar("estrela_cadente", v, [regiao("resistencia", 100.5, 101.5)])
    assert SU.detectar("estrela_cadente", v, [regiao("resistencia", 120.0, 121.0)]) is None


def test_regiao_de_tipo_errado_nunca_serve_a_direcao_oposta():
    assert SU.detectar("martelo", FUNDO + [martelo()], [regiao("resistencia", 98.5, 99.5)]) is None          # compra em resistência: não
    assert SU.detectar("martelo", FUNDO + [martelo()], [regiao("zona_baixa", 98.5, 99.5)]) is None
    assert SU.detectar("estrela_cadente", FUNDO + [estrela()], [regiao("suporte", 100.5, 101.5)]) is None    # venda em suporte: não
    assert SU.detectar("martelo", FUNDO + [martelo()], [regiao("zona_alta", 98.5, 99.5)])                     # zona de alta serve à compra
    assert SU.detectar("estrela_cadente", FUNDO + [estrela()], [regiao("zona_baixa", 100.5, 101.5)])          # zona de baixa serve à venda


def test_7_padrao_valido_com_regiao_marcada_ativa_com_entrada_stop_e_alvo_2_para_1():
    v = FUNDO + [martelo()]
    s = SU.detectar("martelo", v, [regiao("suporte", 98.5, 99.5)])
    entrada = v[-1]["c"]
    assert s["direcao"] == "alta" and s["stop"] < v[-1]["l"]                              # stop abaixo da mínima do padrão
    assert s["alvo"] == pytest.approx(entrada + 2 * (entrada - s["stop"]), abs=1e-3)      # risco/retorno de 2:1
    assert s["regiao"]["tipo"] == "suporte"
    e = SU.detectar("engolfo_alta", FUNDO + engolfo(), [regiao("suporte", 99.7, 100.2)])
    assert e["stop"] < min(x["l"] for x in engolfo())                                      # abaixo da menor mínima dos dois candles
    c = SU.detectar("estrela_cadente", FUNDO + [estrela()], [regiao("resistencia", 100.5, 101.5)])
    assert c["direcao"] == "baixa" and c["stop"] > estrela()["h"] and c["alvo"] < estrela()["c"]


def test_regioes_das_marcas_guardam_id_tipo_faixa_partida_e_momento():
    marcas = {"niveis": [{"preco": 99.0, "rotulo": "Suporte", "papel": "suporte"}, {"preco": 105.0, "rotulo": "Resistência", "papel": "resistencia"},
                         {"preco": 110.0, "rotulo": "Alvo", "papel": "alvo"}],
              "zonas": [{"i1": 1, "p1": 97.0, "i2": 5, "p2": 96.0, "reacao": "alta"}]}
    r = SU.regioes_das_marcas(marcas, atr=1.0, ref=100.0, partida="p9", jog_n=2, rodada=1, criada_em=123.0)
    assert [x["tipo"] for x in r] == ["suporte", "resistencia", "zona_alta"]               # só o que serve de contexto; o alvo não vira região
    assert all(x["partida"] == "p9" and x["criada_em"] == 123.0 and x["id"].startswith("p9:2:1:") for x in r)
    assert (r[0]["min"], r[0]["max"]) == (98.5, 99.5)                                      # tolerância de meio ATR para cada lado
    assert (r[2]["min"], r[2]["max"]) == (95.5, 97.5)                                      # zona: os limites que o jogador desenhou, mais a tolerância


# ------------------------------------------------------------------ o motor da partida (cenários 3, 4, 7, 8, 9, 10)
def _plantar(cen, k, o, h, l, c):
    """Troca o candle k do replay (3 passos) por um candle com esse formato."""
    ini = cen["n_analise"]
    cen["candles"][ini + 3 * k] = {**cen["candles"][ini + 3 * k], "o": o, "h": o, "l": l, "c": l}
    cen["candles"][ini + 3 * k + 1] = {**cen["candles"][ini + 3 * k + 1], "o": l, "h": h, "l": l, "c": h}
    cen["candles"][ini + 3 * k + 2] = {**cen["candles"][ini + 3 * k + 2], "o": h, "h": h, "l": min(h, c), "c": c}


def _partida(carta="martelo", marcas="suporte", plantar=True):
    cen = TD.demo_corrida("rapida", 11)
    sp = TB.CORRIDAS["rapida"]
    ref = cen["candles"][cen["n_analise"] - 1]["c"]
    base = round(ref * 0.97, 2)
    if plantar:
        _plantar(cen, 2, base, base + 0.12, base - 1.0, base + 0.10)
    p = TB.nova_partida(cen, sp["tf"], [A, B], 1000.0, pid="sala1", multi=True, apostas={j: {"stake": 10_000.0, "pat": 500_000.0} for j in (A, B)}, corrida="rapida")
    mk = {"niveis": [{"preco": base - 1.0, "rotulo": "Suporte", "papel": marcas}] if marcas else [], "tendencias": [], "notas": [], "zonas": []}
    for j in (A, B):
        TB.salvar_estrategia(p, j, {"direcao": "alta", "tipo": "continuacao", "confianca": 3}, mk if j == A else None, 0, T0)
    p["setups"] = SV.iniciar([A, B], {A: [carta], B: []})
    return p, cen, base


def test_3_martelo_valido_em_suporte_com_o_candle_ainda_aberto_nao_ativa():
    p, cen, _ = _partida()
    tick(p, cen, T0 + 11.0)                                                               # o candle do martelo ainda está se formando (faltam passos)
    assert p["setups"]["evento"] is None and p["setups"]["sinais"] == []


def test_4_e_7_martelo_valido_em_suporte_marcado_com_o_candle_fechado_ativa():
    p, cen, base = _partida()
    tick(p, cen, T0 + 11.0)
    assert tick(p, cen, T0 + 3 * DT + 0.2)                                                # o candle fechou
    ev = p["setups"]["evento"]
    assert ev, "o martelo fechado dentro do suporte marcado tem que ativar"
    sinal = p["setups"]["sinais"][0]
    assert sinal["setup"] == "martelo" and sinal["direcao"] == "alta" and sinal["regiao"]["tipo"] == "suporte"
    assert sinal["stop"] < base - 1.0 and sinal["alvo"] > sinal["preco"]
    dono, outro = SV.visao(p, A, T0 + 13)["evento"], SV.visao(p, B, T0 + 13)["evento"]
    assert dono["regiao"]["tipo"] == "suporte" and outro["regiao"] is None                # o adversário não vê onde ficam as marcas do outro


def test_padrao_valido_sem_regiao_marcada_nao_ativa_nem_com_o_candle_fechado():
    p, cen, _ = _partida(marcas=None)
    tick(p, cen, T0 + 3 * DT + 0.2)
    assert p["setups"]["evento"] is None and p["setups"]["sinais"] == []


def test_marca_de_resistencia_nao_serve_para_o_martelo():
    p, cen, _ = _partida(marcas="resistencia")
    tick(p, cen, T0 + 3 * DT + 0.2)
    assert p["setups"]["evento"] is None


def test_8_o_mesmo_sinal_processado_duas_vezes_ativa_uma_vez_so():
    p, cen, _ = _partida()
    tick(p, cen, T0 + 3 * DT + 0.2)
    tick(p, cen, T0 + 3 * DT + 0.3)
    tick(p, cen, T0 + 3 * DT + 0.4)
    assert len(p["setups"]["sinais"]) == 1


def test_9_regiao_marcada_depois_do_inicio_da_partida_nao_e_aceita():
    p, cen, base = _partida(marcas=None)
    tick(p, cen, T0 + 1.0)                                                                # o replay já começou: as regiões ficam congeladas (vazias)
    assert p["setups"]["regioes"] == {"1|" + A: []}                                       # congeladas já no começo, e vazias: não havia marcação
    with pytest.raises(TB.ErroTrader):
        TB.salvar_estrategia(p, A, {"direcao": "alta", "tipo": "continuacao", "confianca": 3},
                             {"niveis": [{"preco": base - 1.0, "rotulo": "Suporte", "papel": "suporte"}], "tendencias": [], "notas": [], "zonas": []}, 0, T0 + 2.0)
    tick(p, cen, T0 + 3 * DT + 0.2)
    assert p["setups"]["evento"] is None and p["setups"]["sinais"] == []


def test_regioes_ficam_congeladas_com_id_tipo_faixa_partida_e_momento():
    p, cen, base = _partida()
    tick(p, cen, T0 + 1.0)
    reg = p["setups"]["regioes"]["1|" + A]
    assert len(reg) == 1 and reg[0]["tipo"] == "suporte" and reg[0]["partida"] == "sala1" and reg[0]["criada_em"] == T0 and reg[0]["id"]
    assert reg[0]["min"] < base - 1.0 < reg[0]["max"]
    antes = json.dumps(reg)
    tick(p, cen, T0 + 5.0)
    assert json.dumps(p["setups"]["regioes"]["1|" + A]) == antes                          # não muda mais durante a partida


def test_10_reinicializacao_ou_reconexao_nao_duplica_sinais():
    p, cen, _ = _partida()
    tick(p, cen, T0 + 3 * DT + 0.2)
    assert len(p["setups"]["sinais"]) == 1
    p2 = json.loads(json.dumps(p))                                                         # o servidor reiniciou: o estado volta do banco
    for t in (T0 + 3 * DT + 0.3, T0 + 3 * DT + 1.0, T0 + 3 * DT + 2.0):                    # o jogador reconecta e consulta várias vezes
        tick(p2, cen, t)
    assert len(p2["setups"]["sinais"]) == 1 and p2["setups"]["sinais"][0]["id"] == p["setups"]["sinais"][0]["id"]


def test_os_tres_padroes_usam_um_motor_so():
    assert set(SU.PADROES) == {"martelo", "engolfo_alta", "estrela_cadente"}
    assert all(set(v) == {"nome", "direcao", "regioes", "criterio", "n", "licao"} for v in SU.PADROES.values())
    assert {s["id"]: s["raridade"] for s in SU.catalogo() if s["id"] in SU.PADROES} == {"martelo": "comum", "engolfo_alta": "rara", "estrela_cadente": "comum"}


def test_cadastro_de_cada_setup_tem_o_que_o_pop_up_de_escolha_mostra():
    cat = {s["id"]: s for s in SU.catalogo()}
    for s in cat.values():
        assert s["tipo"] in ("candle", "estrategia") and s["direcao"] in ("compra", "venda", "ambos")
        assert s["regiao"] and s["subtitulo"] and s["stop_texto"] and s["alvo_texto"]
    for sid, spec in SU.PADROES.items():                                                    # as cartas de candle dizem a mesma coisa que as regras do motor
        assert cat[sid]["tipo"] == "candle" and cat[sid]["direcao"] == ("compra" if spec["direcao"] == "alta" else "venda")
        assert ("Suporte" in cat[sid]["regiao"]) == ("suporte" in spec["regioes"]) and ("Resistência" in cat[sid]["regiao"]) == ("resistencia" in spec["regioes"])
    assert all(s["tipo"] == "estrategia" and s["regiao"] == "Qualquer região" for sid, s in cat.items() if sid not in SU.PADROES)
