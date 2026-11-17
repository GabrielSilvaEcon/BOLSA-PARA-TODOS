"""Testa o encadeamento do player (callbacks) sem abrir a tela. Se o Streamlit não estiver instalado, usa um substituto simples."""
import sys

try:
    import streamlit  # noqa: F401
except ImportError:                                       # ambiente sem Streamlit: só os callbacks são exercitados
    from unittest.mock import MagicMock
    sys.modules["streamlit"] = MagicMock()

import streamlit as st

import educacao as ED
import jornada as JO
import jornada_conteudo as J
import jornada_player as PL
from test_jornada import _certo, _errado


def _novo_estado():
    st.session_state = {}                                 # estado limpo (dicionário comum)
    caixa = {"p": ED.novo_progresso()}
    return caixa, (lambda: caixa["p"]), (lambda p: caixa.update(p=p))


def _jogar(lid, errar_primeiro):
    caixa, prog, set_prog = _novo_estado()
    PL.iniciar(lid)
    assert st.session_state["jor_fase"] == "pergunta"
    primeira = True
    while st.session_state["jor_fase"] != "fim":
        ex = JO.exercicio_atual(st.session_state["jor_sessao"])
        resp = _errado(ex) if (errar_primeiro and primeira) else _certo(ex)
        primeira = False
        PL._verificar(ex["id"], resp)
        assert st.session_state["jor_fase"] == "feedback"
        PL._continuar(prog, set_prog)
    return caixa, st.session_state["jor_resultado"]


def test_licao_completa_sem_erros_grava_xp():
    for lid in J.LICAO_POR_ID:
        caixa, r = _jogar(lid, False)
        assert r["ok"] and r["perfeita"] and r["xp"] == JO.XP_LICAO + JO.XP_BONUS_PERFEITA
        assert lid in ED.normalizar(caixa["p"])["jornada"]["licoes"]      # gravado no progresso da conta


def test_nada_e_gravado_antes_do_fim_e_sair_limpa():
    caixa, prog, set_prog = _novo_estado()
    PL.iniciar("l_risco")
    ex = JO.exercicio_atual(st.session_state["jor_sessao"])
    PL._verificar(ex["id"], _certo(ex))
    assert JO.xp_total(caixa["p"]) == 0                   # ainda em andamento
    PL.sair()
    assert not any(k in st.session_state for k in PL.CHAVES)


def test_clique_duplicado_ou_atrasado_e_ignorado():
    caixa, prog, set_prog = _novo_estado()
    PL.iniciar("l_risco")
    ex = JO.exercicio_atual(st.session_state["jor_sessao"])
    PL._verificar(ex["id"], _certo(ex))
    feitos = st.session_state["jor_sessao"]["feitos"]
    PL._verificar(ex["id"], _certo(ex))                   # mesmo exercício de novo: já passou
    assert st.session_state["jor_sessao"]["feitos"] == feitos


def test_ordenar_toque_a_toque():
    _novo_estado()
    PL._add_item("a"); PL._add_item("b"); PL._add_item("a")
    assert st.session_state["jor_ord"] == ["a", "b"]      # item repetido não entra duas vezes
    PL._desfazer()
    assert st.session_state["jor_ord"] == ["a"]


def test_licao_inexistente_nao_inicia():
    _novo_estado()
    PL.iniciar("nao_existe")
    assert "jor_sessao" not in st.session_state


