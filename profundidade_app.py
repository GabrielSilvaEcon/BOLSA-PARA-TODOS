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


def _alternar(chave: str, nome: str) -> None:
    """Toque na barra: abre a seção; tocar na que já está aberta fecha. Só uma fica aberta (menos rolagem)."""
    st.session_state[chave] = None if st.session_state.get(chave) == nome else nome


def _acordeao(classe: str, nomes: list[str], vis: list, resumos: dict) -> list:
    """Cada análise vira uma barra com o resultado em destaque; o conteúdo só aparece quando a barra é aberta."""
    chave = f"acd_{classe}"
    aberto = st.session_state.get(chave)
    saida = []
    for i, (nome, v) in enumerate(zip(nomes, vis)):
        if not v:
            saida.append(None)
            continue
        on = aberto == nome
        res = resumos.get(nome)
        with st.container(key=f"acdbar_{classe}_{i}"):
            st.button(f"{nome}  ·  {res}" if res else nome, key=f"{chave}_b{i}", type="primary" if on else "secondary",
                      icon=":material/expand_less:" if on else ":material/expand_more:", on_click=_alternar, args=(chave, nome), width="stretch")
        saida.append(st.container(key=f"acdon_{classe}_{i}" if on else f"abaoff_{classe}_{i}"))
    return saida


def abas(classe: str, nomes: list[str], resumos: dict | None = None) -> list:
    """Como st.tabs, mas só com as abas da profundidade escolhida. Devolve uma lista do mesmo tamanho: a aba escondida vem como None.
    Com `resumos` ({nome: texto curto}), as seções viram barras que abrem e fecham (acordeão) em vez de fichas."""
    prof = seletor()
    vis = PROF.abas_visiveis(classe, nomes, prof)
    esconde = [n for n, v in zip(nomes, vis) if not v]
    if esconde:
        st.caption(f"Análise {PROF.ROTULOS[prof].lower()}: {len(esconde)} aba(s) a mais na análise Aprofundada ({', '.join(esconde[:4])}{'…' if len(esconde) > 4 else ''}).")
    if resumos is not None:
        return _acordeao(classe, nomes, vis, resumos)
    criadas = iter(secoes.abas([n for n, v in zip(nomes, vis) if v]))
    return [next(criadas) if v else None for v in vis]
