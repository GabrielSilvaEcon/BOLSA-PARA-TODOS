"""Execução ao preço do meio-dia (competicao.processar_meio_dia) e a escolha de fase/dia das ordens."""
from datetime import datetime

import competicao as C

SEG = "2026-11-09"       # segunda-feira


def _est():
    e = C.novo_estado("2026-11-06")
    e["ult_dia"] = "2026-11-06"
    return e


def test_executar_agora_compra_e_venda_na_hora():
    agora = datetime(2026, 11, 9, 10, 30)
    ok, msg, e = C.executar_agora(_est(), [], "C", "PETR4", 100, 40.0, agora)
    assert ok and e["pos"]["PETR4"]["q"] == 100 and e["caixa"] < C.CAPITAL_INICIAL - 4000 + 1e-6
    assert e["meio"]["d"] == SEG and e["meio"]["q"] == {}          # provento de hoje não vale para a compra de hoje
    assert e["ext"][-1]["tipo"] == "compra" and e["ext"][-1]["p"] == 40.0
    ok, msg, e2 = C.executar_agora(e, [], "V", "PETR4", 40, 41.0, agora)
    assert ok and e2["pos"]["PETR4"]["q"] == 60 and e2["ext"][-1]["tipo"] == "venda"


def test_executar_agora_recusa_sem_alterar_o_estado():
    agora = datetime(2026, 11, 9, 10, 30)
    est = _est()
    for lado, qtd in (("C", 100_000), ("V", 1)):                    # sem caixa/concentração e sem posição
        ok, msg, e = C.executar_agora(est, [], lado, "PETR4", qtd, 40.0, agora)
        assert not ok and msg and e == est
    ok, _, e = C.executar_agora(est, [], "C", "PETR4", 10, 0, agora)
    assert not ok and e == est


def test_fechamento_depois_da_execucao_imediata_nao_duplica_e_fecha_o_dia():
    agora = datetime(2026, 11, 9, 10, 30)
    _, _, e = C.executar_agora(_est(), [], "C", "PETR4", 100, 40.0, agora)
    f = C.processar_dia(e, [], SEG, {"PETR4": {"c": 41.0, "div": 1.0}})
    assert f["pos"]["PETR4"]["q"] == 100 and f["ult_dia"] == SEG and "meio" not in f
    assert not any(x["tipo"] == "provento" for x in f["ext"])      # comprou no dia da data ex: sem provento
