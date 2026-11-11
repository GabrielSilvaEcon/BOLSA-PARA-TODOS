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
