"""Incorpora um trecho de HTML/JavaScript numa moldura (iframe) do Streamlit.

O Streamlit trocou `st.components.v1.html` por `st.iframe` (o antigo está marcado para sair). Aqui o app usa o novo quando a
versão instalada tem e o antigo quando não tem, então funciona nas duas.
"""
from __future__ import annotations


def html(st_mod, codigo: str, altura: int = 0) -> None:
    f = getattr(st_mod, "iframe", None)
    if callable(f) and type(f).__module__ != "unittest.mock":
        f(codigo, width="stretch", height=max(int(altura), 1))
        return
    import streamlit.components.v1 as comp
    comp.html(codigo, height=altura)
