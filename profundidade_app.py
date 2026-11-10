"""Seletor Essencial · Detalhada · Aprofundada e abas por profundidade (interface). A regra pura fica em profundidade.py."""
from __future__ import annotations

import streamlit as st
import secoes

import experiencia_app
import profundidade as PROF


def _trocar():
    escolhido = st.session_state.get("prof_home")
    if escolhido in PROF.PROFUNDIDADES:          # clicar na opção ativa a desmarca: mantém a atual
        st.session_state["prof_v"] = escolhido
        try:                                     # fica salva na conta: vale nos outros aparelhos e na próxima visita
            import prefs as P
            import usuarios
            st.session_state["prefs"] = P.normalizar({**P.normalizar(st.session_state.get("prefs")), "profundidade": escolhido})
            usuarios.salvar()
        except Exception:
            pass


def atual() -> str:
    escolha = st.session_state.get("prof_v")
    if escolha is None:                          # primeira vez nesta visita: usa a que ficou salva na conta
        try:
            import prefs as P
            salva = P.normalizar(st.session_state.get("prefs")).get("profundidade")
            escolha = None if salva == "auto" else salva
        except Exception:
            escolha = None
    return PROF.normalizar(escolha, experiencia_app.modo())


def seletor() -> str:
    """Essencial · Detalhada · Aprofundada: quanto mostrar na análise. Começa no que combina com o nível da pessoa e ela troca quando quiser."""
    a = atual()
    with st.container(key="home_prof"):
        st.segmented_control("Escolha a profundidade da análise", PROF.PROFUNDIDADES, default=a, key="prof_home",
                             format_func=lambda p: PROF.ROTULOS[p], on_change=_trocar)
    return a


def abas(classe: str, nomes: list[str], resumos: dict | None = None) -> list:
    """Como st.tabs, mas só com as abas da profundidade escolhida. Devolve uma lista do mesmo tamanho: a aba escondida vem como None.
    As seções são barras que abrem e fecham; `resumos` ({nome: texto curto}) mostra o resultado na própria barra."""
    prof = seletor()
    vis = PROF.abas_visiveis(classe, nomes, prof)
    esconde = [n for n, v in zip(nomes, vis) if not v]
    if esconde:
        st.caption(f"Análise {PROF.ROTULOS[prof].lower()}: {len(esconde)} aba(s) a mais na análise Aprofundada ({', '.join(esconde[:4])}{'…' if len(esconde) > 4 else ''}).")
    criadas = iter(secoes.abas([n for n, v in zip(nomes, vis) if v], key=f"prof_{classe}", resumos=resumos))
    return [next(criadas) if v else None for v in vis]
