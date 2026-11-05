"""Glossário central na tela: ajuda por termo e painel de termos, sempre no nível de conhecimento escolhido.
Tudo local (glossario_central.py): sem consulta externa e sem custo."""
from __future__ import annotations

import streamlit as st

import experiencia_app as EA
import glossario_central as G


def _linhas_md(e: dict) -> str:
    return "\n\n".join(f"**{r}:** {t}" for r, t in e["linhas"])


def mostrar_termo(termo, modo: str | None = None, _st=None) -> bool:
    """Texto completo do termo (título, explicação do nível, classes). False se o termo não existe."""
    e = G.explicacao(termo, modo or EA.modo())
    if not e:
        return False
    s = _st or st
    s.markdown(f"**{e['titulo']}**")
    s.markdown(_linhas_md(e))
    s.caption("Vale para: " + ", ".join(e["classes"]))
    return True


def ajuda(termo, chave: str = "") -> None:
    """Ícone de ajuda (?) que abre a explicação do termo no nível escolhido. Ignora termos desconhecidos."""
    if not G.achar(termo):
        return
    with st.popover(":material/help:", help=f"O que é {G.nome_completo(termo)}?"):
        mostrar_termo(termo)


def painel(termos, titulo: str = "O que significa cada indicador", aberto: bool = False) -> None:
    """Um quadro com os termos usados na tela, explicados no nível do usuário. Sem termos válidos, não mostra nada."""
    ok = [t for t in dict.fromkeys(termos) if G.achar(t)]
    if not ok:
        return
    with st.expander(f"{titulo} · {EA.E.ROTULOS[EA.modo()]}", icon=":material/help:", expanded=aberto):
        for t in ok:
            with st.container(border=True):
                mostrar_termo(t)
