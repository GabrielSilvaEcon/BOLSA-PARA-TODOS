import re
from datetime import date
from pathlib import Path

import jogo as G

SEG = date(2026, 11, 2)          # segunda-feira
QUI = date(2026, 11, 5)
DOM = date(2026, 11, 8)


# ---- missões
def test_missao_repetida_nao_soma_e_tipo_invalido_e_ignorado():
    d = G.concluir_missao({}, QUI, "licao")
    d = G.concluir_missao(d, QUI, "licao")
    d = G.concluir_missao(d, QUI, "inventada")
    assert G.missoes_do_dia(d, QUI) == ["licao"]
    assert G.pontos_missoes_dia(d, QUI) == G.PONTOS_MISSAO


def test_tres_missoes_dao_bonus():
    d = {}
    for t in G.MISSOES:
        d = G.concluir_missao(d, QUI, t)
    assert G.pontos_missoes_dia(d, QUI) == 3 * G.PONTOS_MISSAO + G.BONUS_TODAS


def test_missoes_nao_alteram_o_original_e_dia_novo_comeca_zerado():
    orig = {"dias": {"2026-11-05": ["licao"]}}
    novo = G.concluir_missao(orig, "2026-11-06", "termo")
    assert orig == {"dias": {"2026-11-05": ["licao"]}}
    assert G.missoes_do_dia(novo, "2026-11-06") == ["termo"] and G.missoes_do_dia(novo, "2026-11-07") == []


def test_normalizar_missoes_aceita_lixo():
    assert G.normalizar_missoes(None) == {"dias": {}}
    assert G.normalizar_missoes({"dias": {"x": ["licao"], "2026-11-05": ["licao", "licao", "zzz"], "2026-11-06": 5}}) == {"dias": {"2026-11-05": ["licao"]}}


def test_historico_de_missoes_tem_limite():
    d = {}
    for i in range(30):
        d = G.concluir_missao(d, date(2026, 10, 1 + i % 28), "licao")
    assert len(d["dias"]) <= G.DIAS_GUARDADOS


def test_missoes_da_semana_so_contam_de_segunda_ate_hoje():
    d = {"dias": {"2026-11-01": ["licao", "revisao", "termo"], "2026-11-02": ["licao"], "2026-11-05": ["termo"], "2026-11-09": ["licao"]}}
    assert G.pontos_missoes_semana(d, QUI) == 2 * G.PONTOS_MISSAO          # 02/11 e 05/11; domingo anterior e dia futuro ficam de fora


# ---- estudo
def test_estudo_tem_teto_por_dia_e_so_conta_a_semana():
    xp = {"2026-11-01": 500, "2026-11-02": 500, "2026-11-03": 20, "2026-11-04": "lixo", "2026-11-09": 50}
    assert G.pontos_estudo_semana(xp, QUI) == G.TETO_XP_DIA + 20
    assert G.pontos_estudo_semana(None, QUI) == 0


# ---- nota da carteira (o coração da regra: nunca retorno ou risco)
def _pos(*itens):
    return {tk: {"q": q, "pm": pm} for tk, q, pm in itens}


def test_nota_sobe_com_diversificacao():
    uma = G.nota_carteira(_pos(("BOVA11", 100, 100.0)))
    tres = G.nota_carteira(_pos(("BOVA11", 100, 100.0), ("HGLG11", 100, 100.0), ("IVVB11", 100, 100.0)))
    cinco = G.nota_carteira(_pos(*[(t, 100, 100.0) for t in ("BOVA11", "HGLG11", "IVVB11", "KNRI11", "MXRF11")]))
    assert uma < tres < cinco
    assert cinco == 100                                 # 5 ativos iguais (20% cada): 40 + 40 de 80 = nota máxima sem classes


def test_nota_cai_com_concentracao():
    equilibrada = G.nota_carteira(_pos(("A", 100, 10.0), ("B", 100, 10.0), ("C", 100, 10.0), ("D", 100, 10.0)))
    concentrada = G.nota_carteira(_pos(("A", 390, 10.0), ("B", 10, 10.0), ("C", 10, 10.0), ("D", 10, 10.0)))
    assert equilibrada > concentrada


def test_nota_ignora_preco_atual_lucro_e_retorno():
    base = _pos(("A", 100, 10.0), ("B", 50, 20.0), ("C", 80, 12.5))
    ricas = {tk: {**p, "ult": 999.0, "retorno": 9.99, "lucro": 1e6, "vol": 0.0} for tk, p in base.items()}
    pobres = {tk: {**p, "ult": 0.01, "retorno": -0.99, "lucro": -1e6, "vol": 9.9} for tk, p in base.items()}
    assert G.nota_carteira(base) == G.nota_carteira(ricas) == G.nota_carteira(pobres)


def test_nota_com_classes_premia_mais_de_uma_classe():
    pos = _pos(("A", 100, 10.0), ("B", 100, 10.0), ("C", 100, 10.0), ("D", 100, 10.0), ("E", 100, 10.0))
    uma = G.nota_carteira(pos, {t: "acao" for t in pos})
    tres = G.nota_carteira(pos, {"A": "acao", "B": "fii", "C": "etf", "D": "acao", "E": "fii"})
    assert tres == 100 and uma < tres


def test_nota_carteira_vazia_ou_lixo_e_zero():
    assert G.nota_carteira({}) == 0 and G.nota_carteira(None) == 0
    assert G.nota_carteira({"A": {"q": 0, "pm": 10}, "B": {"q": "x"}, "C": 5}) == 0


def test_pontos_do_desafio():
    assert G.pontos_desafio(None) == 0 and G.pontos_desafio(0) == 0
    assert G.pontos_desafio(100) == G.PONTOS_DESAFIO and G.pontos_desafio(500) == G.PONTOS_DESAFIO and G.pontos_desafio(-5) == 0
    assert G.pontos_desafio(50) == G.PONTOS_DESAFIO // 2


# ---- placar
def test_placar_da_semana_soma_as_tres_fontes():
    xp = {"2026-11-02": 30, "2026-11-03": 100}
    miss = G.concluir_missao({}, SEG, "licao")
    r = G.pontos_semana(xp, miss, 80, DOM)
    assert r == {"estudo": 30 + G.TETO_XP_DIA, "missoes": G.PONTOS_MISSAO, "desafio": G.pontos_desafio(80),
                 "total": 30 + G.TETO_XP_DIA + G.PONTOS_MISSAO + G.pontos_desafio(80)}


def test_pontos_nao_dependem_de_retorno_nem_risco():
    # o módulo não importa nem chama nada de retorno, patrimônio ou risco da Competição
    src = Path(__file__).with_name("jogo.py").read_text(encoding="utf-8")
    codigo = "\n".join(l for l in src.splitlines() if not l.lstrip().startswith("#"))
    assert not re.search(r"import\s+competicao|retorno_total|retorno_periodo|metricas_risco|queda_maxima|patrimonio\(", codigo)
    assert "competicao" not in src.split('"""', 2)[2]
