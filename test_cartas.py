"""Cartas colecionáveis: catálogo, raridade, coleção, evolução, equipar, baús e atributos de jogo (regras puras)."""
import pytest

import cartas as C
import cartas_catalogo as CAT

AG = "2026-11-24T10:00:00"


def test_pontuacao_e_faixas_de_raridade():
    assert CAT.pontuacao(50, 30, 20) == 100 and CAT.pontuacao(99, 99, 99) == 100 and CAT.pontuacao(-5, 0, 0) == 0
    assert [CAT.raridade_da_pontuacao(p) for p in (0, 34, 35, 54, 55, 79, 80, 100)] == ["comum", "comum", "rara", "rara", "epica", "epica", "lendaria", "lendaria"]


def test_catalogo_completo_e_sem_logos():
    assert len(CAT.EMPRESAS) == len(CAT.POR_TK) >= 19
    for e in CAT.EMPRESAS:
        assert all(e[k] for k in ("tk", "nome", "setor", "icone", "atividade", "fato"))
        assert e["raridade_fixa"] == CAT.raridade_da_pontuacao(e["pontos"]["total"])
        assert e["arte"] is None or e["arte"].startswith("arte_")
    assert all(CAT.da_raridade(r) for r in CAT.RARIDADES)            # há cartas de todas as raridades
    assert {"CVCB3", "VAMO3", "LWSA3"} <= set(CAT.POR_TK)


def test_duplicata_vira_copia_e_raridade_fica_fixa():
    d = C.colecao_vazia()
    assert C.adicionar(d, "CVCB3", "comum", AG)["nova"]
    r = C.adicionar(d, "CVCB3", "rara", AG)                          # mesmo se o catálogo mudar depois, a raridade da carta não muda
    assert not r["nova"] and r["copias"] == 1 and d["cartas"]["CVCB3"]["rar"] == "comum" and d["cartas"]["CVCB3"]["total"] == 2


def test_evolucao_gasta_copias_da_mesma_carta_e_guarda_a_escolha():
    cfg = C.config_padrao()
    d = C.colecao_vazia()
    C.adicionar(d, "CVCB3", "comum", AG)
    C.adicionar(d, "VAMO3", "comum", AG)
    C.adicionar(d, "VAMO3", "comum", AG)
    C.adicionar(d, "VAMO3", "comum", AG)
    with pytest.raises(C.ErroCarta):
        C.evoluir(d, cfg, "CVCB3", "roe", AG)                        # cópias de outra carta não servem
    with pytest.raises(C.ErroCarta):
        C.evoluir(d, cfg, "VAMO3", "pvp", AG)                        # só P/L, DY ou ROE
    r = C.evoluir(d, cfg, "VAMO3", "roe", AG)
    assert r["nivel"] == 2 and r["gasto"] == cfg["evolucao"]["comum"][0] and d["cartas"]["VAMO3"]["copias"] == 0
    assert d["cartas"]["VAMO3"]["escolhas"] == ["roe"] and d["log"][0]["tipo"] == "evolucao"
    p = C.progresso(cfg, d["cartas"]["VAMO3"])
    assert p["precisa"] == cfg["evolucao"]["comum"][1] and not p["pode"]


def test_nivel_maximo():
    cfg = C.validar_config({"evolucao": {"lendaria": [1]}})
    d = C.colecao_vazia()
    for _ in range(3):
        C.adicionar(d, "PETR4", "lendaria", AG)
    C.evoluir(d, cfg, "PETR4", "pl", AG)
    assert C.progresso(cfg, d["cartas"]["PETR4"])["maximo"]
    with pytest.raises(C.ErroCarta):
        C.evoluir(d, cfg, "PETR4", "pl", AG)


def test_baralho_repete_comum_mas_nao_epica_nem_lendaria():
    d = C.colecao_vazia()
    for t, r in (("CVCB3", "comum"), ("VAMO3", "comum"), ("SUZB3", "rara"), ("WEGE3", "epica"), ("ITUB4", "epica"),
                 ("PETR4", "lendaria"), ("VALE3", "lendaria")):
        C.adicionar(d, t, r, AG)
    for t in ("CVCB3", "VAMO3", "SUZB3", "WEGE3", "PETR4"):          # duas comuns juntas: antes era impossível
        C.equipar(d, t, AG)
    assert C.equipadas(d) == ["CVCB3", "VAMO3", "SUZB3", "WEGE3", "PETR4"]
    with pytest.raises(C.ErroCarta):                                 # 2ª épica
        C.equipar(d, "ITUB4", AG)
    C.desequipar(d, "WEGE3", AG)
    with pytest.raises(C.ErroCarta):                                 # 2ª lendária, mesmo com espaço
        C.equipar(d, "VALE3", AG)
    assert C.equipadas(d) == ["CVCB3", "VAMO3", "SUZB3", "PETR4"]


def test_baralho_cheio_e_carta_que_nao_tem():
    d = C.colecao_vazia()
    for i in range(C.BARALHO_EQUIP + 1):
        C.adicionar(d, f"AAA{i}", "comum", AG)
    for i in range(C.BARALHO_EQUIP):
        C.equipar(d, f"AAA{i}", AG)
    with pytest.raises(C.ErroCarta):                                 # passou do tamanho do baralho
        C.equipar(d, f"AAA{C.BARALHO_EQUIP}", AG)
    with pytest.raises(C.ErroCarta):
        C.equipar(d, "NAOTENHO3", AG)


def test_normalizar_migra_formato_antigo_e_descarta_invalida():
    d = C.colecao_vazia()
    for t, r in (("CVCB3", "comum"), ("SUZB3", "rara")):
        C.adicionar(d, t, r, AG)
    d["equip"] = {"comum": "CVCB3", "rara": "SUZB3", "epica": "XXXX3", "lendaria": None}   # formato antigo em disco
    n = C.normalizar(d)
    assert n["equip"] == ["CVCB3", "SUZB3"]                          # vira lista, sem a carta que a pessoa não tem


def test_bau_deterministico_com_garantia_e_entrega_unica():
    cfg = C.config_padrao()
    por = {r: CAT.da_raridade(r) for r in CAT.RARIDADES}
    a = C.sortear_bau("conta|marco:1", cfg["baus"]["epico"], por)
    assert a == C.sortear_bau("conta|marco:1", cfg["baus"]["epico"], por) and len(a) == cfg["baus"]["epico"]["qtd"]
    for i in range(40):
        tks = C.sortear_bau(f"s{i}", cfg["baus"]["lendario"], por)
        assert any(CAT.raridade(t) == "lendaria" for t in tks)
    d = C.colecao_vazia()
    r1 = C.entregar(d, "bau:x", a, CAT.raridade, "bau", AG)
    r2 = C.entregar(d, "bau:x", a, CAT.raridade, "bau", AG)
    assert not r1["ja"] and r2["ja"] and sum(c["total"] for c in d["cartas"].values()) == len(a)


def test_chances_respeitam_a_configuracao():
    por = {r: CAT.da_raridade(r) for r in CAT.RARIDADES}
    conf = {"qtd": 1, "chances": {"comum": 0, "rara": 0, "epica": 0, "lendaria": 1}, "garantia": None}
    assert all(CAT.raridade(C.sortear_bau(f"z{i}", conf, por)[0]) == "lendaria" for i in range(20))
    with pytest.raises(C.ErroCarta):
        C.validar_config({"baus": {"comum": {"qtd": 2, "chances": {"comum": -1}}}})
    with pytest.raises(C.ErroCarta):
        C.validar_config({"evolucao": {"rara": [0, 2]}})


def test_atributos_de_jogo_separados_dos_reais():
    cfg = C.config_padrao()
    base = {"tk": "WEGE3", "classe": "acao", "ind": {"pl": 30.0, "dy_12m": 0.02, "roe": 0.25, "vol": 0.3}}
    c = {"rar": "epica", "nivel": 4, "escolhas": ["pl", "pl", "roe"]}
    j = C.carta_de_jogo(base, c, cfg, "WEGE3-abc")
    assert base["ind"]["pl"] == 30.0                                  # o dado real não muda
    assert j["real"]["pl"] == 30.0 and j["ind"]["pl"] == pytest.approx(30 * 0.96 ** 2)
    assert j["ind"]["roe"] == pytest.approx(0.26) and j["ind"]["dy_12m"] == 0.02 and j["ind"]["vol"] == 0.3
    assert j["id"] == "WEGE3-abc" and j["tk"] == "WEGE3" and j["melhorias"] == {"pl": 2, "dy_12m": 0, "roe": 1}


def test_bonus_da_raridade_nao_existe_so_do_nivel():
    cfg = C.config_padrao()
    base = {"tk": "X", "ind": {"roe": 0.1}}
    a = C.carta_de_jogo(base, {"rar": "lendaria", "nivel": 1, "escolhas": []}, cfg, "a")
    b = C.carta_de_jogo(base, {"rar": "comum", "nivel": 1, "escolhas": []}, cfg, "b")
    assert a["ind"] == b["ind"] == base["ind"]                       # lendária não vence só por ser lendária


# ------------------------------------------------------------------ sinergia de setor
def test_passos_de_sinergia_por_cartas_do_setor():
    assert [C.passos_sinergia(n) for n in (0, 1, 2, 3, 4, 5)] == [0, 0, 1, 2, 2, 2]      # teto de 2: nunca passa por cima da evolução


def test_sinergias_so_para_setor_com_duas_cartas_ou_mais():
    setor = {"A": "Bancos", "B": "Bancos", "C": "Varejo", "D": "Varejo", "E": "Varejo", "F": "Saúde", "G": None}
    s = C.sinergias(list("ABCDEFG"), setor.get)
    assert [(x["setor"], x["n"], x["passos"]) for x in s] == [("Bancos", 2, 1), ("Varejo", 3, 2)]    # Saúde (1) e sem setor ficam de fora
    assert s[0]["tks"] == ["A", "B"] and C.sinergias([], setor.get) == []


def test_aplicar_sinergia_melhora_no_sentido_certo_e_preserva_o_real():
    cfg = C.config_padrao()
    carta = {"ind": {"pl": 10.0, "dy_12m": 0.05, "roe": 0.15, "vol": 0.3}, "real": {"pl": 10.0, "dy_12m": 0.05, "roe": 0.15, "vol": 0.3}}
    out = C.aplicar_sinergia(carta, 2, cfg)
    assert out["ind"]["pl"] < 10.0                                    # P/L: menor é melhor
    assert out["ind"]["dy_12m"] > 0.05 and out["ind"]["roe"] > 0.15   # DY e ROE: maior é melhor
    assert out["ind"]["vol"] == 0.3                                   # indicador sem bônus configurado não muda
    assert out["real"] == {"pl": 10.0, "dy_12m": 0.05, "roe": 0.15, "vol": 0.3}   # o dado financeiro real nunca é alterado


def test_aplicar_sinergia_sem_passos_ou_com_valor_ausente_nao_quebra():
    cfg = C.config_padrao()
    assert C.aplicar_sinergia({"ind": {"pl": 10.0}}, 0, cfg)["ind"] == {"pl": 10.0}
    assert C.aplicar_sinergia({"ind": {"pl": None, "roe": 0.1}}, 1, cfg)["ind"]["pl"] is None
