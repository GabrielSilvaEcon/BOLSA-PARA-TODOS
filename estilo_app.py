"""Estilo compartilhado das telas novas (Fase 4 a 6): seletores em pílula e botão Voltar no mesmo visual dos cartões da Início.
Só CSS (sem Streamlit e sem dados). Cada tela injeta o que usa com `st.markdown(estilo_app.css_...(), unsafe_allow_html=True)`.
Texto sempre com cor forçada (!important): o app tem regras globais que deixam texto de elementos próprios escuro."""
from __future__ import annotations

_Q = "html body .stApp.stApp.stApp"


def css_selecao(chaves: list[str]) -> str:
    """Pílulas (st.pills e st.segmented_control) com as chaves dadas: arredondadas, quebram de linha e a escolhida em roxo."""
    r = []
    for k in chaves:
        b = f'{_Q} .st-key-{k} [data-testid^="stBaseButton-pills"],{_Q} .st-key-{k} [data-testid^="stBaseButton-segmented"]'
        r.append(
            f'{_Q} .st-key-{k} [data-testid="stButtonGroup"]{{flex-wrap:wrap !important;gap:8px !important}}'
            f'{b}{{border-radius:999px !important;min-height:38px !important;padding:0 14px !important;background:rgba(255,255,255,.06) !important;'
            'border:1.5px solid rgba(197,179,255,.4) !important;box-shadow:0 3px 0 rgba(10,8,40,.5) !important}'
            f'{b} :is(p,span,div){{color:#E8E2FF !important;-webkit-text-fill-color:#E8E2FF !important;font-weight:700 !important;font-size:.88rem !important}}'
            f'{_Q} .st-key-{k} [data-testid$="Active"]{{background:linear-gradient(180deg,#8B6CFF,#6B47F5) !important;border-color:#C5B3FF !important}}'
            f'{_Q} .st-key-{k} [data-testid$="Active"] :is(p,span,div){{color:#fff !important;-webkit-text-fill-color:#fff !important}}')
    return "<style>" + "".join(r) + "</style>"


def css_voltar(prefixo: str) -> str:
    """Botão Voltar (chaves que começam com `prefixo`) em pílula translúcida."""
    s = f'{_Q} [class*="st-key-{prefixo}"] button'
    return ("<style>" + f'{s}{{border-radius:999px !important;min-height:42px !important;padding:0 18px !important;width:auto !important;'
            'background:rgba(255,255,255,.06) !important;border:1.5px solid rgba(197,179,255,.45) !important;box-shadow:0 3px 0 rgba(10,8,40,.5) !important}'
            f'{s} :is(p,span,svg){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important}}</style>')


def css_abas(chave: str, n: int) -> str:
    """Abas em grade (n colunas) para os botões da função `abas`: mesmo padrão dos botões Recompensas/Loja/Extrato (secundário escuro, principal em degradê)."""
    k = f".st-key-ab_{chave}"
    s = (f'{_Q} {k}{{display:grid !important;grid-template-columns:repeat({n},minmax(0,1fr)) !important;gap:8px !important;margin:6px 0 10px !important}}'
         f'{_Q} {k}>[data-testid="stElementContainer"]{{width:100% !important;min-width:0 !important}}'
         f'{_Q} {k} button{{width:100% !important;min-height:42px !important;height:auto !important;padding:4px 8px !important}}'
         f'{_Q} {k} button p{{margin:0 !important;font-size:.85rem !important;font-weight:700 !important;line-height:1.15 !important;white-space:normal !important;overflow-wrap:anywhere}}')
    if n > 2:
        s += f'@media (max-width:360px){{{_Q} {k}{{grid-template-columns:repeat(2,minmax(0,1fr)) !important}}}}'
    return "<style>" + s + "</style>"


def _escolher(chave: str, valor) -> None:
    import streamlit as st
    st.session_state[chave] = valor


def abas(chave: str, opcoes, default=None, rotulo=str, colunas: int | None = None):
    """Seletor padrão do app: fileira/grade de botões (o escolhido em degradê). Guarda a escolha em st.session_state[chave] e devolve o valor.
    Substitui st.pills/st.segmented_control: usa o mesmo botão das abas da Economia, que já aparece igual em celular, tablet e computador."""
    import streamlit as st
    opcoes = list(opcoes)
    if st.session_state.get(chave) not in opcoes:
        st.session_state[chave] = default if default in opcoes else opcoes[0]
    atual = st.session_state[chave]
    n = colunas or (2 if len(opcoes) == 4 else min(len(opcoes), 3))
    st.markdown(css_abas(chave, n), unsafe_allow_html=True)
    with st.container(key=f"ab_{chave}"):
        for i, o in enumerate(opcoes):
            st.button(rotulo(o), key=f"ab_{chave}_{i}", type="primary" if o == atual else "secondary", width="stretch", on_click=_escolher, args=(chave, o))
    return st.session_state[chave]
