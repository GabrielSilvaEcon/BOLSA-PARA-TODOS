"""Execução ao preço do meio-dia (competicao.processar_meio_dia) e a escolha de fase/dia das ordens."""
from datetime import datetime

import competicao as C

SEG = "2026-11-09"       # segunda-feira


def _est():
    e = C.novo_estado("2026-11-06")
    e["ult_dia"] = "2026-11-06"
    return e


def test_fase_e_dia_da_ordem():
    assert C.fase_execucao(datetime(2026, 11, 9, 10, 0)) == "M" and C.dia_execucao(datetime(2026, 11, 9, 10, 0)) == SEG
    assert C.fase_execucao(datetime(2026, 11, 9, 14, 0)) == "F" and C.dia_execucao(datetime(2026, 11, 9, 14, 0)) == SEG
    assert C.fase_execucao(datetime(2026, 11, 9, 18, 0)) == "M" and C.dia_execucao(datetime(2026, 11, 9, 18, 0)) == "2026-11-10"
    assert C.fase_execucao(datetime(2026, 11, 7, 11, 0)) == "M" and C.dia_execucao(datetime(2026, 11, 7, 11, 0)) == SEG      # sábado


def test_nova_ordem_guarda_a_fase_e_o_perfil_mantem():
    o = C.nova_ordem(datetime(2026, 11, 9, 10, 0), "C", "PETR4", 10)
    assert o["f"] == "M"
    d = C.sanear_perfil({"apelido": "Ana123", "aceite": True, "pend": [o]})
    assert d["pend"] and d["pend"][0]["f"] == "M"


def test_meio_dia_executa_ao_preco_atual_e_nao_fecha_o_dia():
    o = C.nova_ordem(datetime(2026, 11, 9, 10, 0), "C", "PETR4", 100)
    e = C.processar_meio_dia(_est(), [o], SEG, {"PETR4": 40.0})
    assert e["pos"]["PETR4"]["q"] == 100 and o["id"] in e["proc"]
    assert e["caixa"] < C.CAPITAL_INICIAL - 4000 + 1e-6 and e["ult_dia"] == "2026-11-06"      # não valorizou nem fechou
    assert any(x["tipo"] == "compra" and x["p"] == 40.0 for x in e["ext"])


def test_ordem_de_fechamento_nao_executa_ao_meio_dia():
    o = C.nova_ordem(datetime(2026, 11, 9, 14, 0), "C", "PETR4", 100)
    e = C.processar_meio_dia(_est(), [o], SEG, {"PETR4": 40.0})
    assert not e["pos"] and o["id"] not in e["proc"]


def test_sem_preco_fica_para_o_fechamento():
    o = C.nova_ordem(datetime(2026, 11, 9, 10, 0), "C", "PETR4", 100)
    e = C.processar_meio_dia(_est(), [o], SEG, {})
    assert not e["pos"] and o["id"] not in e["proc"]
    f = C.processar_dia(e, [o], SEG, {"PETR4": {"c": 41.0, "div": 0.0, "split": 1.0}})
    assert f["pos"]["PETR4"]["q"] == 100 and f["ult_dia"] == SEG


def test_fechamento_nao_repete_ordem_do_meio_dia_e_valoriza():
    o = C.nova_ordem(datetime(2026, 11, 9, 10, 0), "C", "PETR4", 100)
    e = C.processar_meio_dia(_est(), [o], SEG, {"PETR4": 40.0})
    f = C.processar_dia(e, [o], SEG, {"PETR4": {"c": 42.0, "div": 0.0, "split": 1.0}})
    assert f["pos"]["PETR4"]["q"] == 100 and f["ult_dia"] == SEG and "meio" not in f
    assert f["hist"][-1]["p"] > C.CAPITAL_INICIAL - 500          # 100 × (42 − 40) de ganho menos o custo


def test_provento_do_dia_nao_vai_para_quem_comprou_ao_meio_dia():
    o = C.nova_ordem(datetime(2026, 11, 9, 10, 0), "C", "PETR4", 100)
    e = C.processar_meio_dia(_est(), [o], SEG, {"PETR4": 40.0})
    f = C.processar_dia(e, [o], SEG, {"PETR4": {"c": 40.0, "div": 1.0, "split": 1.0}})
    assert not any(x["tipo"] == "provento" for x in f["ext"])


def test_recusa_por_limite_de_concentracao_tambem_vale_ao_meio_dia():
    o = C.nova_ordem(datetime(2026, 11, 9, 10, 0), "C", "PETR4", 2000)      # 2000 × 40 = 80 mil (> 40%)
    e = C.processar_meio_dia(_est(), [o], SEG, {"PETR4": 40.0})
    assert not e["pos"] and any(x["tipo"] == "recusada" for x in e["ext"]) and o["id"] in e["proc"]
