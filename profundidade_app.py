"""Seletor Essencial · Detalhada · Aprofundada e abas por profundidade (interface). A regra pura fica em profundidade.py."""
from __future__ import annotations

import streamlit as st
import secoes

import experiencia_app
import profundidade as PROF


def _gravar(escolhido: str):
    st.session_state["prof_v"] = escolhido
    try:                                         # fica salva na conta: vale nos outros aparelhos e na próxima visita
        import prefs as P
        import usuarios
        st.session_state["prefs"] = P.normalizar({**P.normalizar(st.session_state.get("prefs")), "profundidade": escolhido})
        usuarios.salvar()
    except Exception:
        pass


def _trocar():
    escolhido = st.session_state.get("prof_home")
    if escolhido in PROF.PROFUNDIDADES:          # clicar na opção ativa a desmarca: mantém a atual
        _gravar(escolhido)


def _ciclar():
    """Um toque passa para o próximo modo: Essencial → Detalhada → Aprofundada → Essencial."""
    lista = list(PROF.PROFUNDIDADES)
    a = atual()
    _gravar(lista[(lista.index(a) + 1) % len(lista)] if a in lista else lista[0])


def botao(chave: str) -> None:
    """Botão único que mostra o modo atual e alterna entre os três a cada toque (fica ao lado do nome do ativo)."""
    a = atual()
    st.button(PROF.ROTULOS[a], key=chave, icon=":material/layers:", on_click=_ciclar, width="stretch",
              help="Toque para alternar entre Essencial, Detalhada e Aprofundada")


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


_EXP_ORIGINAL = getattr(st.expander, "_original", st.expander)


def _expander_seguro(label, expanded=False, **kw):
    """O Streamlit não deixa um menu expansivo dentro de outro. Dentro de uma seção da análise, o 'menu' interno vira um bloco com título."""
    if st.session_state.get("_em_secao", 0) > 0:
        c = st.container(border=True)
        c.markdown(f"**{label}**")
        return c
    return _EXP_ORIGINAL(label, expanded=expanded, **kw)


_expander_seguro._original = _EXP_ORIGINAL
st.expander = _expander_seguro


class _Secao:
    """Uma categoria de resultados num menu expansivo (igual às Ações). A primeira pode trazer o cabeçalho do ativo (nome, modo e botões)."""

    def __init__(self, titulo: str, icone: str, aberto: bool, cabecalho=None):
        self._args = (f"{icone} {titulo}", aberto)
        self._cab = cabecalho
        self._exp = None

    def __enter__(self):
        self._exp = _EXP_ORIGINAL(self._args[0], expanded=self._args[1])
        self._exp.__enter__()
        st.session_state["_em_secao"] = st.session_state.get("_em_secao", 0) + 1
        if self._cab is not None:
            self._cab()
        return self

    def __exit__(self, *exc):
        st.session_state["_em_secao"] = max(0, st.session_state.get("_em_secao", 1) - 1)
        return self._exp.__exit__(*exc)


def abas(classe: str, nomes: list[str], resumos: dict | None = None, cabecalho=None) -> list:
    """Cada análise é um menu expansivo (o primeiro já aberto). Só as da profundidade escolhida; a escondida vem como None.
    Com `cabecalho` (função), ele aparece dentro do primeiro menu, com o botão de modo; sem ele, o botão de modo fica acima dos menus."""
    prof = atual()
    st.session_state["_em_secao"] = 0
    if cabecalho is None:
        with st.container(key=f"prof_modo_{classe}"):                   # um botão só: cada toque troca Essencial → Detalhada → Aprofundada
            botao(f"prof_btn_{classe}")
    vis = PROF.abas_visiveis(classe, nomes, prof)
    esconde = [n for n, v in zip(nomes, vis) if not v]
    out, primeiro = [], True
    for i, (n, v) in enumerate(zip(nomes, vis)):
        if not v:
            out.append(None)
            continue
        rot = secoes._limpo(n)
        r = (resumos or {}).get(n)
        titulo = f"{rot} · {r}" if r and len(str(r)) <= 38 else rot
        out.append(_Secao(titulo, secoes.icone_da_secao(rot, i), primeiro, cabecalho if primeiro else None))
        primeiro = False
    if esconde:
        st.caption(f"Análise {PROF.ROTULOS[prof].lower()}: {len(esconde)} análise(s) a mais no modo Aprofundada ({', '.join(esconde[:4])}{'…' if len(esconde) > 4 else ''}).")
    return out
