"""Menu suspenso de seções: substitui `st.tabs` quando há muitas abas (celular).

Uso igual ao do st.tabs:  abas = secoes.abas(["A", "B", "C", "D"]);  with abas[0]: ...
Mostra um seletor compacto com a seção atual e só exibe o conteúdo dela. Com menos de `minimo` seções, usa as abas normais
(2 ou 3 abas curtas cabem na tela). A escolha fica guardada no session_state, então a pessoa volta à mesma seção.
"""
from __future__ import annotations

import hashlib
import re
import sys

import streamlit as st

_ICONE = re.compile(r":material/[a-z0-9_]+:\s*")

_CSS = """<style>
[class*="st-key-abaoff_"] {display:none !important;}
[class*="st-key-abasel_"] {margin:0 0 .6rem 0;}
[class*="st-key-abasel_"] [data-baseweb="select"] > div {min-height:44px; border-radius:14px; font-weight:800;}
[class*="st-key-abasel_"] [data-baseweb="select"] div[value], [class*="st-key-abasel_"] [data-baseweb="select"] span {font-weight:800;}
</style>"""


def _limpo(rotulo: str) -> str:
    return _ICONE.sub("", str(rotulo)).strip()


def abas(rotulos: list[str], key: str | None = None, minimo: int = 4) -> list:
    """Devolve uma lista de containers (um por seção). Só o da seção escolhida fica visível."""
    rotulos = [str(r) for r in rotulos]
    if len(rotulos) < minimo:
        return st.tabs(rotulos)
    if key is None:
        quadro = sys._getframe(1)
        ident = f"{quadro.f_code.co_filename}:{quadro.f_lineno}|" + "|".join(r.replace("🔒 ", "") for r in rotulos)
        key = hashlib.md5(ident.encode("utf-8")).hexdigest()[:10]
    chave = f"secao_{key}"
    if st.session_state.get(chave) not in rotulos:
        st.session_state.pop(chave, None)
    st.markdown(_CSS, unsafe_allow_html=True)
    ult = f"{chave}_ult"
    with st.container(key=f"abasel_{key}"):
        if hasattr(st, "pills"):        # fichas que rolam de lado (jeito de aplicativo); sem pills, cai no menu suspenso
            if st.session_state.get(chave) not in rotulos:
                st.session_state.pop(chave, None)
            padrao = st.session_state.get(ult) if st.session_state.get(ult) in rotulos else rotulos[0]

            def _manter():          # tocar na ficha ativa a desmarcaria: volta para a última seção
                if st.session_state.get(chave) is None:
                    st.session_state[chave] = st.session_state.get(ult)

            kw = {} if chave in st.session_state else {"default": padrao}
            escolhida = st.pills("Seção", rotulos, selection_mode="single", key=chave, label_visibility="collapsed", on_change=_manter, **kw)
            escolhida = escolhida if escolhida in rotulos else padrao
            st.session_state[ult] = escolhida
        else:
            escolhida = st.selectbox("Seção", rotulos, key=chave, format_func=_limpo, label_visibility="collapsed")
    atual = rotulos.index(escolhida) if escolhida in rotulos else 0
    return [st.container(key=(f"abaon_{key}_{i}" if i == atual else f"abaoff_{key}_{i}")) for i in range(len(rotulos))]
