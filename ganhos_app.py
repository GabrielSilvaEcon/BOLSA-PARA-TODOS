"""Pop-up de ganhos (adaptador Streamlit de ganhos.py): XP, Ticker Coins, sequência e nível, no padrão visual dos outros pop-ups.

O HUD do topo registra os ganhos; o pop-up abre no fim da execução (depois da página). O Streamlit só deixa um pop-up aberto por vez: se a
página já abriu o dela (conquista, bônus, recibo), os ganhos esperam e aparecem na próxima execução."""
from __future__ import annotations

import html

import streamlit as st

CHAVE = "_ganhos_pend"
_SUB = {"⚡": "Experiência", "🪙": "Ticker Coins", "🔥": "Sequência de estudo", "🏆": "Nível"}


def registrar(msgs: list[dict]) -> None:
    if msgs:
        st.session_state[CHAVE] = list(st.session_state.get(CHAVE) or []) + [dict(m) for m in msgs]


def _corpo(msgs: list[dict]) -> None:
    import perfil_app as PF
    cartoes = "".join(f"<div class='cl-pop'><div class='ic'>{html.escape(m['icone'])}</div><div class='tx'><b>{html.escape(m['texto'])}</b>"
                      f"<span>{html.escape(_SUB.get(m['icone'], ''))}</span></div></div>" for m in msgs)
    st.markdown(PF._POP_CSS + cartoes, unsafe_allow_html=True)
    if st.button("Legal!", key="ganhos_ok", type="primary", width="stretch"):
        st.rerun()


def mostrar() -> None:
    """Abre o pop-up com o que está pendente. Nunca levanta erro: se não der agora (outro pop-up aberto), tenta na próxima execução."""
    msgs = st.session_state.get(CHAVE)
    if not msgs:
        return
    try:
        dlg = getattr(st, "dialog", None)
        if dlg is None:
            for m in msgs:
                st.toast(m["texto"], icon=m["icone"])
        else:
            dlg("Você ganhou!", width="small")(_corpo)(list(msgs))
        st.session_state[CHAVE] = []                      # aberto: fechar pelo X também conta como visto
    except Exception:
        pass
