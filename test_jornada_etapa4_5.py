"""Etapa 4 (revisão, meta e frase da meta) e Etapa 5 (conteúdo completo da jornada). Sem Streamlit real."""
import sys
from collections import Counter
from datetime import datetime, timezone
from unittest.mock import MagicMock

try:
    import streamlit  # noqa: F401
except ImportError:
    sys.modules["streamlit"] = MagicMock()
sys.modules.setdefault("conta_app", MagicMock())          # a tela de conta não é necessária para estes testes

import streamlit as st

import edu_conteudo as E
import educacao as ED
import jornada as JO
import jornada_app as APP
import jornada_conteudo as J
import jornada_player as PL
from test_jornada import _certo, _errado


# ------------------------------------------------------------------ Etapa 5: conteúdo
def test_conteudo_sem_problemas():
    assert JO.validar_conteudo() == []


def test_toda_aula_tem_uma_licao_e_toda_licao_esta_em_uma_unidade():
    assert {l["aula"] for l in J.LICOES} == {a["id"] for a in E.AULAS}
    em_unidades = [lid for u in J.UNIDADES for lid in u["licoes"]]
    assert sorted(em_unidades) == sorted(J.LICAO_POR_ID) and len(em_unidades) == len(set(em_unidades))


def test_licoes_curtas_e_variadas():
    for l in J.LICOES:
        assert 5 <= len(l["exercicios"]) <= 6, l["id"]
        assert len(Counter(e["tipo"] for e in l["exercicios"])) >= 3, l["id"]
    ids = [e["id"] for l in J.LICOES for e in l["exercicios"]]
    assert len(ids) == len(set(ids))


def test_perguntas_nao_se_repetem_e_opcoes_sao_distintas():
    ps = [e["pergunta"] for l in J.LICOES for e in l["exercicios"]]
    assert len(ps) == len(set(ps))
    for l in J.LICOES:
        for e in l["exercicios"]:
            if e["tipo"] in ("escolha", "completar"):
                assert len(set(e["opcoes"])) == len(e["opcoes"]) >= 3, e["id"]
            if e["tipo"] == "pares":
                assert len({a for a, _ in e["pares"]}) == len(e["pares"]) and len({b for _, b in e["pares"]}) == len(e["pares"]), e["id"]


def test_a_resposta_certa_nao_e_sempre_a_primeira_opcao():
    """Evita um vício do conteúdo: se todas as certas fossem a opção 0, dava para acertar sem ler."""
    pos = Counter(e["correta"] for l in J.LICOES for e in l["exercicios"] if e["tipo"] in ("escolha", "completar"))
    assert len(pos) >= 2


def test_jornada_inteira_em_ordem_libera_uma_proxima_por_vez():
    p = ED.novo_progresso()
    agora = datetime(2026, 11, 9, 12, 0, tzinfo=timezone.utc)
    for u in J.UNIDADES:
        for lid in u["licoes"]:
            proximas = [l["id"] for un in JO.mapa(p) for l in un["licoes"] if l["estado"] == "proxima"]
            assert proximas == [lid]
            s = JO.iniciar_sessao(lid)
            while not JO.terminada(s):
                ok, s = JO.responder(s, _certo(JO.exercicio_atual(s)))
            p, r = JO.concluir_sessao(p, s, agora)
    assert all(un["completa"] for un in JO.mapa(p)) and not [l for un in JO.mapa(p) for l in un["licoes"] if l["estado"] == "proxima"]


# ------------------------------------------------------------------ Etapa 4: revisão, meta, frase
def _estado():
    st.session_state = {}
    caixa = {"p": ED.novo_progresso()}
    return caixa, (lambda: caixa["p"]), (lambda p: caixa.update(p=p))


def test_revisao_pelo_player():
    caixa, prog, set_prog = _estado()
    PL.iniciar_revisao(prog())
    assert "jor_sessao" not in st.session_state                 # sem erros, nada começa
    PL.iniciar("l_risco")
    ex = JO.exercicio_atual(st.session_state["jor_sessao"])
    PL._verificar(ex["id"], _errado(ex))
    while st.session_state["jor_fase"] != "fim":
        PL._continuar(prog, set_prog)
        if st.session_state["jor_fase"] == "fim":
            break
        ex = JO.exercicio_atual(st.session_state["jor_sessao"])
        PL._verificar(ex["id"], _certo(ex))
    assert JO.erros_para_revisar(caixa["p"]) == 1
    PL.iniciar_revisao(caixa["p"])
    s = st.session_state["jor_sessao"]
    assert s["revisao"] and s["total"] == 1 and st.session_state["jor_fase"] == "pergunta"
    ex = JO.exercicio_atual(s)
    PL._verificar(ex["id"], _certo(ex))
    PL._continuar(prog, set_prog)
    assert st.session_state["jor_resultado"]["revisao"] and JO.erros_para_revisar(caixa["p"]) == 0


def test_mudar_meta_diaria():
    caixa, prog, set_prog = _estado()
    st.session_state["jor_meta"] = 50
    APP._mudar_meta(prog, set_prog)
    assert JO.resumo(caixa["p"])["meta_dia"] == 50
    st.session_state["jor_meta"] = 9999                          # fora do limite: vira o máximo permitido
    APP._mudar_meta(prog, set_prog)
    assert JO.resumo(caixa["p"])["meta_dia"] == 200


def test_frase_da_meta():
    base = {"meta_dia": 20, "xp_hoje": 0, "ofensiva": 0, "meta_atingida": False}
    assert "Faltam 20 XP" in APP.texto_meta(base)
    assert "concluída" in APP.texto_meta({**base, "xp_hoje": 20, "meta_atingida": True})
    assert "manter 3 dias" in APP.texto_meta({**base, "ofensiva": 3})
    assert "Faltam 5 XP" in APP.texto_meta({**base, "xp_hoje": 15, "ofensiva": 3})


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
