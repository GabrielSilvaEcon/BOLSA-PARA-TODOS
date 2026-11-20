"""Avaliação dos desenhos da estratégia (trader_leitura): cada papel conferido contra candles conhecidos."""
import trader_leitura as TL


def v(o, h, l, c):
    return {"o": o, "h": h, "l": l, "c": c}


# preço no fim da análise: 10,00; ATR 0,40 → tolerância 0,10
REF, ATR = 10.0, 0.4
CAI_E_VOLTA = [v(10, 10.1, 9.6, 9.7), v(9.7, 9.8, 9.0, 9.05), v(9.05, 9.6, 9.0, 9.5), v(9.5, 10.4, 9.4, 10.3), v(10.3, 10.6, 10.2, 10.5)]
DESPENCA = [v(10, 10.1, 9.4, 9.5), v(9.5, 9.6, 8.6, 8.7), v(8.7, 8.8, 8.0, 8.1), v(8.1, 8.2, 7.6, 7.7)]


def nivel(papel, p):
    return {"niveis": [{"preco": p, "papel": papel}]}


def test_suporte_que_segura_e_que_rompe():
    assert TL.avaliar_desenhos(nivel("suporte", 9.0), 100, CAI_E_VOLTA, REF, ATR)["itens"][0]["ok"] is True
    assert TL.avaliar_desenhos(nivel("suporte", 9.0), 100, DESPENCA, REF, ATR)["itens"][0]["ok"] is False


def test_desenho_que_o_preco_nao_alcancou_nao_conta():
    r = TL.avaliar_desenhos(nivel("suporte", 5.0), 100, CAI_E_VOLTA, REF, ATR)
    assert r["itens"][0]["ok"] is None and r["nota"] is None and r["avaliados"] == 0


def test_resistencia_rompimento_e_alvo():
    sobe = [v(10, 10.6, 9.9, 10.5), v(10.5, 11.2, 10.4, 11.1), v(11.1, 11.6, 11.0, 11.5)]
    assert TL.avaliar_desenhos(nivel("resistencia", 10.6), 100, sobe, REF, ATR)["itens"][0]["ok"] is False
    assert TL.avaliar_desenhos(nivel("rompimento", 10.6), 100, sobe, REF, ATR)["itens"][0]["ok"] is True
    assert TL.avaliar_desenhos(nivel("alvo", 11.5), 100, sobe, REF, ATR)["itens"][0]["ok"] is True
    assert TL.avaliar_desenhos(nivel("alvo", 9.0), 100, sobe, REF, ATR)["itens"][0]["ok"] is False


def test_zona_de_reacao_e_nota():
    m = {"zonas": [{"i1": 90, "i2": 99, "p1": 9.0, "p2": 9.3, "reacao": "alta"}], "niveis": [{"preco": 5.0, "papel": "suporte"}]}
    r = TL.avaliar_desenhos(m, 100, CAI_E_VOLTA, REF, ATR)
    assert r["itens"][1]["ok"] is True and r["nota"] == 100.0 and r["avaliados"] == 1     # o suporte não alcançado não puxa a nota para baixo
    m["zonas"][0]["reacao"] = "baixa"
    assert TL.avaliar_desenhos(m, 100, CAI_E_VOLTA, REF, ATR)["nota"] == 0.0


def test_tendencia_de_alta_respeitada():
    sobe = [v(10 + k * 0.1, 10.2 + k * 0.1, 9.95 + k * 0.1, 10.1 + k * 0.1) for k in range(10)]
    t = {"tendencias": [{"i1": 90, "p1": 9.0, "i2": 99, "p2": 9.9}]}                       # linha de alta abaixo do preço
    r = TL.avaliar_desenhos(t, 100, sobe, REF, ATR)
    assert r["itens"][0]["ok"] is True and r["nota"] == 100.0
    assert TL.avaliar_desenhos(t, 100, DESPENCA, REF, ATR)["itens"][0]["ok"] is False
