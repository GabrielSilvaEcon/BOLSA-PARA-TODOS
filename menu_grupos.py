"""Menu de botões internos de uma tela (estilo da Wallet Game): botões principais agrupados e, quando o grupo tem mais de uma análise,
uma segunda linha de pílulas. Sempre há uma análise ativa. Só apresentação: quem chama decide o que mostrar para a análise ativa."""
from __future__ import annotations

import streamlit as st

CORES = ("#8B6CFF", "#3DDC97", "#F2B84B", "#FF6B8A", "#2BA7C9")


def _css(chave: str, ativo_idx: int, n_grupos: int, n_sub: int) -> str:
    q = "html body .stApp.stApp.stApp"
    n = f"{q} .st-key-mgnav_{chave}"
    sb = f"{q} .st-key-mgsub_{chave}"
    r = "".join(f"{q} .st-key-mg_{chave}_g{i}{{--ac:{c}}}" for i, c in enumerate(CORES))
    ac = CORES[ativo_idx % len(CORES)]
    return (
        r + f"{sb}{{--ac:{ac}}}"
        # as linhas viram grade CSS (a regra global de 3+ colunas do app não alcança); cada botão é uma célula
        f"{n}[data-testid=\"stVerticalBlock\"],{n}>[data-testid=\"stVerticalBlock\"]{{display:grid !important;grid-template-columns:repeat({n_grupos},minmax(0,1fr)) !important;gap:8px !important}}"
        f"{sb}[data-testid=\"stVerticalBlock\"],{sb}>[data-testid=\"stVerticalBlock\"]{{display:grid !important;grid-template-columns:repeat({max(n_sub, 1)},minmax(0,1fr)) !important;gap:6px !important}}"
        f"{n},{sb}{{margin:0 0 6px}}"
        f"{n} button{{width:100% !important;min-height:62px !important;height:auto !important;border-radius:16px !important;padding:6px 3px !important;gap:3px !important;display:flex !important;flex-direction:column !important;align-items:center !important;justify-content:center !important;"
        "background:linear-gradient(160deg,color-mix(in srgb,var(--ac) 14%,var(--dz-cartao)),var(--dz-cartao) 75%) !important;"
        "border:1px solid color-mix(in srgb,var(--ac) 45%,transparent) !important;box-shadow:0 3px 0 color-mix(in srgb,var(--ac) 28%,#0B0821) !important;transition:transform .08s,box-shadow .08s}"
        f"{n} button:active{{transform:translateY(2px);box-shadow:0 1px 0 color-mix(in srgb,var(--ac) 28%,#0B0821) !important}}"
        f"{n} button>div,{n} button [data-testid=\"stMarkdownContainer\"]{{display:flex !important;flex-direction:column !important;align-items:center !important;justify-content:center !important;gap:3px !important;width:100% !important;margin:0 !important;padding:0 !important}}"
        f"{n} button [data-testid=\"stIconMaterial\"]{{flex:0 0 26px;width:26px !important;height:26px !important;border-radius:50%;display:grid !important;place-items:center;font-size:16px !important;color:#fff !important;margin:0 !important;"
        "background:radial-gradient(circle at 30% 18%,rgba(255,255,255,.45),transparent 52%),var(--ac);box-shadow:0 2px 0 color-mix(in srgb,var(--ac) 55%,#0B0821)}"
        f"{n} button :is(p,span):not([data-testid=\"stIconMaterial\"]){{font-size:.72rem !important;font-weight:800 !important;line-height:1.1 !important;color:var(--dz-texto) !important;text-align:center !important;white-space:nowrap !important}}"
        f"{n}.st-key-mgnav_{chave}.st-key-mgnav_{chave} button[data-testid^=\"stBaseButton-primary\"] :is(p,span):not([data-testid=\"stIconMaterial\"]){{color:var(--dz-texto) !important;-webkit-text-fill-color:var(--dz-texto) !important}}"
        f"{n} button[data-testid^=\"stBaseButton-primary\"]{{border-color:var(--ac) !important;"
        "background:linear-gradient(160deg,color-mix(in srgb,var(--ac) 34%,var(--dz-cartao)),color-mix(in srgb,var(--ac) 12%,var(--dz-cartao)) 80%) !important;"
        "box-shadow:0 3px 0 color-mix(in srgb,var(--ac) 50%,#0B0821),0 0 0 2px color-mix(in srgb,var(--ac) 22%,transparent) !important}"
        f"{sb} button{{width:100% !important;min-height:36px !important;height:auto !important;border-radius:999px !important;padding:0 6px !important;justify-content:center !important;"
        "background:var(--dz-cartao) !important;border:1px solid color-mix(in srgb,var(--ac) 35%,transparent) !important;box-shadow:0 3px 0 rgba(0,0,0,.35) !important}"
        f"{sb} button :is(p,span){{font-size:.78rem !important;font-weight:800 !important;line-height:1.1 !important;color:var(--dz-texto) !important;text-align:center !important;white-space:nowrap !important}}"
        f"{sb} button[data-testid^=\"stBaseButton-primary\"]{{background:var(--ac) !important;border-color:var(--ac) !important;box-shadow:0 3px 0 color-mix(in srgb,var(--ac) 50%,#000) !important}}"
        f"{sb} button[data-testid^=\"stBaseButton-primary\"] :is(p,span){{color:#10091F !important}}"
    )



def _ir(chave: str, item: str) -> None:
    st.session_state[f"mg_{chave}"] = item


def menu(chave: str, grupos: list) -> str:
    """grupos = [(nome, ícone Material, [itens])]. Devolve o item ativo (o primeiro, no começo). Toque no grupo abre o primeiro item dele."""
    grupos = [g for g in grupos if g[2]]
    todos = [i for g in grupos for i in g[2]]
    atual = st.session_state.get(f"mg_{chave}")
    if atual not in todos:
        atual = todos[0]
        st.session_state[f"mg_{chave}"] = atual
    idx = next((i for i, g in enumerate(grupos) if atual in g[2]), 0)
    ativo = grupos[idx]
    st.markdown(f"<style>{_css(chave, idx, len(grupos), len(ativo[2]) if len(ativo[2]) > 1 else 1)}</style>", unsafe_allow_html=True)
    with st.container(key=f"mgnav_{chave}"):
        for i, (nome, ic, itens) in enumerate(grupos):
            st.button(nome, key=f"mg_{chave}_g{i}", icon=ic, type="primary" if i == idx else "secondary",
                      on_click=_ir, args=(chave, itens[0]), width="stretch")
    if len(ativo[2]) > 1:
        with st.container(key=f"mgsub_{chave}"):
            for j, item in enumerate(ativo[2]):
                st.button(item, key=f"mg_{chave}_n{j}_{idx}", type="primary" if item == atual else "secondary",
                          on_click=_ir, args=(chave, item), width="stretch")
    return atual
