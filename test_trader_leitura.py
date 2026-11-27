"""Avaliação dos desenhos da estratégia (trader_leitura): cada papel conferido contra candles conhecidos."""
import pytest
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
    # os preços ficam a mais de 2 ATR (0,80) de REF: mais perto que isso não é avaliado
    sobe = [v(10, 10.6, 9.9, 10.5), v(10.5, 11.2, 10.4, 11.1), v(11.1, 11.6, 11.0, 11.5)]
    assert TL.avaliar_desenhos(nivel("resistencia", 10.9), 100, sobe, REF, ATR)["itens"][0]["ok"] is False
    assert TL.avaliar_desenhos(nivel("rompimento", 10.9), 100, sobe, REF, ATR)["itens"][0]["ok"] is True
    assert TL.avaliar_desenhos(nivel("alvo", 11.5), 100, sobe, REF, ATR)["itens"][0]["ok"] is True
    assert TL.avaliar_desenhos(nivel("alvo", 9.0), 100, sobe, REF, ATR)["itens"][0]["ok"] is False


def test_zona_de_reacao_e_nota():
    m = {"zonas": [{"i1": 90, "i2": 99, "p1": 8.8, "p2": 9.2, "reacao": "alta"}], "niveis": [{"preco": 5.0, "papel": "suporte"}]}
    r = TL.avaliar_desenhos(m, 100, CAI_E_VOLTA, REF, ATR)
    assert r["itens"][1]["ok"] is True and r["nota"] >= 50 and r["avaliados"] == 1        # o suporte não alcançado não puxa a nota para baixo
    m["zonas"][0]["reacao"] = "baixa"
    assert TL.avaliar_desenhos(m, 100, CAI_E_VOLTA, REF, ATR)["nota"] <= 50               # errou: no máximo neutro


def test_acerto_vale_proporcional_a_distancia_do_preco_de_partida():
    """Pode desenhar em qualquer lugar, mas o acerto vale o quanto o preço andou: colado no preço quase não pontua."""
    sobe = [v(10, 10.6, 9.9, 10.5), v(10.5, 11.2, 10.4, 11.1), v(11.1, 11.6, 11.0, 11.5)]
    plena = TL.distancia_plena(ATR, REF)                                    # 2 ATR = 0,80
    longe = TL.avaliar_desenhos(nivel("alvo", REF + plena + 0.1), 100, sobe, REF, ATR)["itens"][0]
    meio = TL.avaliar_desenhos(nivel("alvo", REF + plena / 2), 100, sobe, REF, ATR)["itens"][0]
    colado = TL.avaliar_desenhos(nivel("alvo", REF + 0.04), 100, sobe, REF, ATR)["itens"][0]
    assert longe["ok"] and meio["ok"] and colado["ok"]                       # todos acertaram (✔ no gráfico)...
    assert longe["peso"] == 1.0 and meio["peso"] == 0.5 and colado["peso"] == 0.05      # ...mas valem 100%, 50% e 5%
    for it in (longe, meio, colado):                                         # valor = 0,5 + peso × (acerto − acaso)/2
        assert it["valor"] == pytest.approx(0.5 + it["peso"] * (1 - it["acaso"]) / 2)
    assert colado["valor"] == pytest.approx(0.5, abs=0.03)                  # colado no preço: neutro, não ajuda nem atrapalha
    assert longe["valor"] >= meio["valor"] >= colado["valor"]
    assert "Vale 50%" in meio["texto"] and "Vale" not in longe["texto"]


def test_desenho_colado_no_preco_nao_ajuda_a_nota():
    """A nota é a média: somar desenhos fáceis e colados (neutros, ~50) ao desenho honesto não sobe a nota, então não há como encher de acertos baratos."""
    sobe = [v(10, 10.6, 9.9, 10.5), v(10.5, 11.2, 10.4, 11.1), v(11.1, 11.6, 11.0, 11.5)]
    honesto = {"niveis": [{"preco": 11.0, "papel": "alvo"}]}
    com_colados = {"niveis": honesto["niveis"] + [{"preco": 10.05 + i * 0.01, "papel": "alvo"} for i in range(3)]}
    so = TL.avaliar_desenhos(honesto, 100, sobe, REF, ATR)["nota"]
    junto = TL.avaliar_desenhos(com_colados, 100, sobe, REF, ATR)["nota"]
    assert junto <= so + 1e-9 and junto == pytest.approx(50, abs=5)          # os colados puxam para o neutro, nunca para cima


def test_desenho_que_o_preco_nao_alcancou_continua_sem_contar():
    r = TL.avaliar_desenhos(nivel("alvo", 20.0), 100, CAI_E_VOLTA, REF, ATR)
    assert r["itens"][0]["ok"] is False or r["itens"][0]["ok"] is None
    r2 = TL.avaliar_desenhos(nivel("suporte", 5.0), 100, CAI_E_VOLTA, REF, ATR)
    assert r2["itens"][0]["ok"] is None and r2["nota"] is None


def test_zona_em_volta_do_preco_vale_zero_mas_a_vizinha_vale():
    dentro = {"zonas": [{"i1": 90, "i2": 99, "p1": 9.8, "p2": 10.2, "reacao": "alta"}]}      # o preço (10,0) está dentro dela: distância 0
    r = TL.avaliar_desenhos(dentro, 100, CAI_E_VOLTA, REF, ATR)["itens"][0]
    assert r["peso"] == 0.0 and r["valor"] in (None, 0.5)                    # em cima do preço: neutro
    longe = {"zonas": [{"i1": 90, "i2": 99, "p1": 8.8, "p2": 9.2, "reacao": "alta"}]}        # borda mais próxima a 0,8 = distância plena
    assert TL.avaliar_desenhos(longe, 100, CAI_E_VOLTA, REF, ATR)["itens"][0]["peso"] == 1.0


def test_tendencia_de_alta_respeitada():
    sobe = [v(10 + k * 0.1, 10.2 + k * 0.1, 9.95 + k * 0.1, 10.1 + k * 0.1) for k in range(10)]
    t = {"tendencias": [{"i1": 90, "p1": 9.0, "i2": 99, "p2": 9.9}]}                       # linha de alta abaixo do preço
    r = TL.avaliar_desenhos(t, 100, sobe, REF, ATR)
    assert r["itens"][0]["ok"] is True and r["nota"] == 100.0
    assert TL.avaliar_desenhos(t, 100, DESPENCA, REF, ATR)["itens"][0]["ok"] is False


def test_acaso_acertar_onde_o_acaso_sempre_acerta_vale_neutro_e_errar_vale_pouco():
    """Mercado que só sobe: um alvo acima sempre é alcançado, em qualquer distância (o acaso acerta sempre). Acertar isso vale ~50, não 100."""
    sobe = [v(10 + k * 0.3, 10.4 + k * 0.3, 9.95 + k * 0.3, 10.3 + k * 0.3) for k in range(12)]
    r = TL.avaliar_desenhos(nivel("alvo", REF + 1.0), 100, sobe, REF, ATR)
    it = r["itens"][0]
    assert it["ok"] is True and it["acaso"] == 1.0 and r["nota"] == pytest.approx(50.0)
    # a resistência acima que o preço atravessou: errou onde o acaso (outras distâncias) quase sempre também erra -> perto do neutro, nunca premia
    r2 = TL.avaliar_desenhos(nivel("resistencia", REF + 1.0), 100, sobe, REF, ATR)
    assert r2["itens"][0]["ok"] is False and r2["nota"] <= 50


def test_acaso_sem_alcance_assume_cinquenta_e_em_cima_do_preco_tambem():
    assert TL.taxa_acaso(lambda f: None, 1.0) == 0.5
    assert TL.taxa_acaso(lambda f: True, 0.0) == 0.5
    assert TL.taxa_acaso(lambda f: f < 1, 1.0) == 0.5          # 2 dos 4 testes acertam (0,6 e 0,8)
    assert TL.valor_sobre_acaso(None, 0.5, 1.0) is None
    assert TL.valor_sobre_acaso(True, 0.0, 1.0) == 1.0 and TL.valor_sobre_acaso(False, 1.0, 1.0) == 0.0
    assert TL.valor_sobre_acaso(True, 0.5, 0.0) == 0.5


def test_chutar_as_cegas_rende_perto_de_50_e_ver_o_futuro_passa_disso():
    """O que a auditoria mediu: suporte/resistência às cegas rendiam ~66; agora ~50. Quem de fato acerta (aqui, o oráculo) passa disso."""
    import trader_battle as TB
    import trader_dados as TD
    chutes, oraculo = [], []
    for seed in range(60):
        cen = TD.demo_corrida("rapida", 7000 + seed)
        na = cen["n_analise"]
        cand = cen["candles"]
        ref, atr, rep = cand[na - 1]["c"], TB._atr(cand[:na]), cand[na:]
        m = {"niveis": [{"papel": "resistencia", "preco": ref + 2 * atr}, {"papel": "suporte", "preco": ref - 2 * atr}]}
        r = TL.avaliar_desenhos(m, na, rep, ref, atr)["nota"]
        if r is not None:
            chutes.append(r)
        o = {"niveis": [{"papel": "alvo", "preco": max(c["h"] for c in rep)}, {"papel": "alvo", "preco": min(c["l"] for c in rep)}]}
        oraculo.append(TL.avaliar_desenhos(o, na, rep, ref, atr)["nota"])
    assert 42 <= sum(chutes) / len(chutes) <= 58
    assert sum(oraculo) / len(oraculo) > 60
