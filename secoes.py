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


def _alternar(chave: str, rotulo: str) -> None:
    """Toque na barra: abre a seção; tocar na que já está aberta fecha. Só uma fica aberta por vez (menos rolagem)."""
    st.session_state[chave] = None if st.session_state.get(chave) == rotulo else rotulo


def abas(rotulos: list[str], key: str | None = None, minimo: int = 4, resumos: dict | None = None) -> list:
    """Devolve uma lista de containers (um por seção). Com `minimo` seções ou mais, cada uma vira uma barra que abre e fecha (acordeão);
    `resumos` ({rótulo: texto curto}) coloca o resultado da análise na própria barra. Só a seção aberta fica visível.
    Com menos seções, usa as abas normais."""
    rotulos = [str(r) for r in rotulos]
    if len(rotulos) < minimo:
        return st.tabs(rotulos)
    if key is None:
        quadro = sys._getframe(1)
        ident = f"{quadro.f_code.co_filename}:{quadro.f_lineno}|" + "|".join(r.replace("🔒 ", "") for r in rotulos)
        key = hashlib.md5(ident.encode("utf-8")).hexdigest()[:10]
    chave = f"acd_{key}"
    if st.session_state.get(chave) not in rotulos:
        st.session_state.pop(chave, None)
    aberto = st.session_state.get(chave)
    resumos = resumos or {}
    saida = []
    for i, r in enumerate(rotulos):
        on = aberto == r
        res = resumos.get(r) or resumos.get(r.replace("🔒 ", ""))
        nome = _limpo(r)
        with st.container(key=f"acdbar_{key}_{i}"):
            st.button(f"{nome}  ·  {res}" if res else nome, key=f"{chave}_b{i}", type="primary" if on else "secondary",
                      icon=":material/expand_less:" if on else ":material/expand_more:", on_click=_alternar, args=(chave, r), width="stretch")
        saida.append(st.container(key=f"acdon_{key}_{i}" if on else f"abaoff_{key}_{i}"))
    return saida
