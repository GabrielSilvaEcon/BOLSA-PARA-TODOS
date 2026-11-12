"""Componentes compartilhados de interação do TickerHunters (busca instantânea, atualização parcial, avisos).

Uma melhoria aqui vale para todas as telas que usam estes componentes. Nada aqui guarda dados nem mexe em regra financeira.
Sem o pacote opcional `streamlit-keyup`, a busca atualiza ao dar Enter (o app continua funcionando).
"""
from __future__ import annotations

import unicodedata

try:
    import streamlit as st
except ImportError:                                  # testes puros rodam sem o Streamlit
    st = None


# ---------------------------------------------------------------- busca
def _norm(t) -> str:
    """Minúsculas e sem acento: 'Petrobrás', 'petrobras' e 'PETROBRAS' são a mesma busca."""
    s = unicodedata.normalize("NFKD", str(t or ""))
    return "".join(c for c in s if not unicodedata.combining(c)).lower().strip()


def filtrar(opcoes, consulta: str, rotulo=lambda x: str(x), limite: int | None = None) -> list:
    """Opções cujo rótulo contém todas as palavras digitadas. Quem COMEÇA com a busca vem primeiro (PETR → PETR4 antes de 'Alpetra')."""
    palavras = _norm(consulta).split()
    if not palavras:
        return []
    achados = []
    for o in opcoes:
        r = _norm(rotulo(o))
        if all(p in r for p in palavras):
            inicio = any(parte.startswith(palavras[0]) for parte in r.replace("·", " ").split())
            achados.append((0 if inicio else 1, r, o))
    achados.sort(key=lambda x: (x[0], x[1]))
    out = [o for _, _, o in achados]
    return out[:limite] if limite else out


def busca(key: str, placeholder: str = "Ticker ou nome: PETR4, Petrobras...", debounce: int = 250) -> str:
    """Campo de busca que atualiza a cada letra (streamlit-keyup). Sem o pacote, atualiza ao dar Enter."""
    try:
        from st_keyup import st_keyup
        try:
            return st_keyup("Buscar", key=key, placeholder=placeholder, debounce=debounce, label_visibility="collapsed") or ""
        except TypeError:
            return st_keyup("Buscar", key=key, debounce=debounce) or ""
    except Exception:
        pass
    try:
        return st.text_input("Buscar", key=key, placeholder=placeholder, max_chars=30, label_visibility="collapsed", icon=":material/search:")
    except TypeError:
        return st.text_input("Buscar", key=key, placeholder=placeholder, max_chars=30, label_visibility="collapsed")


def escolher_ativo(chave: str, opcoes, rotulo=lambda x: str(x), placeholder: str = "Digite o nome ou o ticker: petr, vale, itaú…",
                   aceita_livre: bool = True, limite: int = 5, valida=None):
    """Escolha de ativo com busca instantânea e sugestões em botões. Devolve o ativo escolhido (ou None) e o guarda em st.session_state[chave].
    Ao escolher ou trocar, a página inteira recarrega (st.rerun) para os outros blocos verem a escolha; a digitação só recarrega a busca."""
    atual = st.session_state.get(chave)
    if atual:
        c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
        c1.markdown("<style>html body .stApp.stApp .cux-esc{background:rgba(46,229,157,.12);border:1.5px solid #2EE59D;border-radius:14px;padding:10px 14px;color:#fff;font-weight:800}</style>"
                    f"<div class='cux-esc'>{rotulo(atual)}</div>", unsafe_allow_html=True)
        if c2.button("Trocar", key=f"{chave}__trocar", icon=":material/swap_horiz:", width="stretch"):
            st.session_state.pop(chave, None)
            st.session_state.pop(f"{chave}__q", None)
            st.rerun()
        return atual

    def _busca():
        q = busca(f"{chave}__q", placeholder)
        if not q.strip():
            return
        achados = filtrar(opcoes, q, rotulo, limite)
        for i, t in enumerate(achados):
            if st.button(rotulo(t), key=f"{chave}__s{i}", width="stretch"):
                st.session_state[chave] = t
                st.rerun()
        if aceita_livre and not achados:
            livre = "".join(ch for ch in q.upper() if ch.isalnum() or ch in "-.")[:14]
            if livre and valida is not None and not valida(livre):
                st.caption("Nenhum ativo encontrado. Confira o código (ex.: HGLG11).")
            elif livre and st.button(f"Usar “{livre}”", key=f"{chave}__livre", icon=":material/check:", width="stretch"):
                st.session_state[chave] = livre
                st.rerun()
        elif not achados:
            st.caption("Nenhum ativo encontrado com essa busca.")
    fragmento(_busca)()
    return None


# ---------------------------------------------------------------- atualização parcial
def fragmento(funcao):
    """Faz só esta parte da tela recarregar quando o usuário interage com ela (st.fragment). Em versão antiga do Streamlit, não faz nada.
    Dentro de um fragmento: botões com on_click só reexecutam o fragmento; para mudar de tela, o botão deve ficar FORA dele."""
    frag = getattr(st, "fragment", None) if st is not None else None
    return frag(funcao) if frag else funcao


# ---------------------------------------------------------------- avisos
def aviso(msg: str, icone: str = "✅") -> None:
    """Aviso rápido que some sozinho, sem interromper a navegação."""
    try:
        st.toast(msg, icon=icone)
    except Exception:
        pass


# ---------------------------------------------------------------- cartão de busca (mesmo padrão do Comprar Ativo)
def cartao_busca(chave: str, balao: str, corpo, pose: str = "animado"):
    """Cartão com fundo ilustrado, o campo de busca (função `corpo`) à esquerda e o mascote com balão à direita."""
    import html as _h
    import arte_tickerhunters as AT
    k = f"ux_cb_{chave}"
    st.markdown("<style>"
                f"html body .stApp.stApp .st-key-{k}{{margin:6px 0 10px;border:1px solid #2B4A8C;border-radius:22px;padding:12px;min-height:150px;"
                f"background:url(\"{URI_FUNDO}\") right bottom/auto 75% no-repeat,radial-gradient(circle at 85% 20%,rgba(54,183,232,.22),transparent 55%),linear-gradient(160deg,#10204A,#0A1433 78%);box-shadow:0 8px 22px rgba(2,6,23,.45)}}"
                f"html body .stApp.stApp .st-key-{k} [data-testid='stHorizontalBlock']{{flex-wrap:nowrap !important;gap:8px !important;align-items:center !important}}"
                f"html body .stApp.stApp .st-key-{k} [data-testid='stColumn']{{min-width:0 !important}}"
                f"html body .stApp.stApp .st-key-{k} .cux-bal{{background:#FFE9C2;color:#4A2E08;font-weight:800;font-size:.7rem;line-height:1.2;border-radius:14px 14px 4px 14px;padding:6px 8px;margin-bottom:4px;box-shadow:0 3px 8px rgba(0,0,0,.35)}}"
                f"html body .stApp.stApp .st-key-{k} .cux-tr{{display:flex;flex-direction:column;align-items:flex-end}}"
                f"html body .stApp.stApp .st-key-{k} .cux-tr img{{max-height:110px;width:auto}}"
                "</style>", unsafe_allow_html=True)
    with st.container(key=k):
        ce, cd = st.columns([1.5, 1])
        with ce:
            corpo()
        with cd:
            st.markdown(f"<div class='cux-tr'><div class='cux-bal'>{_h.escape(balao)}</div>{AT.img(AT.pose(pose), 92, alt='Caramelo, o mascote')}</div>", unsafe_allow_html=True)


URI_FUNDO = "data:image/svg+xml;utf8,%3Csvg%20xmlns=%27http://www.w3.org/2000/svg%27%20viewBox=%270%200%20400%20200%27%20preserveAspectRatio=%27xMidYMax%20slice%27%3E%3Cdefs%3E%3ClinearGradient%20id=%27g%27%20x1=%270%27%20y1=%270%27%20x2=%270%27%20y2=%271%27%3E%3Cstop%20offset=%270%27%20stop-color=%27%232EE59D%27%20stop-opacity=%27.14%27/%3E%3Cstop%20offset=%271%27%20stop-color=%27%232EE59D%27%20stop-opacity=%270%27/%3E%3C/linearGradient%3E%3C/defs%3E%3Cg%20stroke-width=%273%27%20stroke-linecap=%27round%27%20opacity=%27.2%27%3E%3Cg%20stroke=%27%232EE59D%27%3E%3Cpath%20d=%27M250%20150v-40M250%20135v-20%27/%3E%3Cpath%20d=%27M280%20140v-50%27/%3E%3Cpath%20d=%27M310%20120v-60%27/%3E%3Cpath%20d=%27M340%20100v-60%27/%3E%3Cpath%20d=%27M370%2080v-55%27/%3E%3C/g%3E%3Cg%20stroke=%27%23FF5B6E%27%3E%3Cpath%20d=%27M220%20160v-30%27/%3E%3Cpath%20d=%27M190%20170v-25%27/%3E%3C/g%3E%3C/g%3E%3Cg%20fill=%27%232EE59D%27%20opacity=%27.12%27%3E%3Crect%20x=%27243%27%20y=%27115%27%20width=%2714%27%20height=%2728%27%20rx=%273%27/%3E%3Crect%20x=%27273%27%20y=%2798%27%20width=%2714%27%20height=%2734%27%20rx=%273%27/%3E%3Crect%20x=%27303%27%20y=%2775%27%20width=%2714%27%20height=%2738%27%20rx=%273%27/%3E%3Crect%20x=%27333%27%20y=%2755%27%20width=%2714%27%20height=%2736%27%20rx=%273%27/%3E%3Crect%20x=%27363%27%20y=%2735%27%20width=%2714%27%20height=%2734%27%20rx=%273%27/%3E%3C/g%3E%3Cg%20fill=%27%23FF5B6E%27%20opacity=%27.12%27%3E%3Crect%20x=%27213%27%20y=%27135%27%20width=%2714%27%20height=%2720%27%20rx=%273%27/%3E%3Crect%20x=%27183%27%20y=%27148%27%20width=%2714%27%20height=%2716%27%20rx=%273%27/%3E%3C/g%3E%3Cpath%20d=%27M20%20175%20L90%20150%20L140%20160%20L200%20120%20L260%20125%20L330%2070%20L395%2025%20L395%20200%20L20%20200Z%27%20fill=%27url%28%23g%29%27/%3E%3Cpath%20d=%27M20%20175%20L90%20150%20L140%20160%20L200%20120%20L260%20125%20L330%2070%20L395%2025%27%20fill=%27none%27%20stroke=%27%2336B7E8%27%20stroke-width=%273%27%20opacity=%27.22%27/%3E%3Cg%20fill=%27%23FFD76A%27%20opacity=%27.14%27%3E%3Ccircle%20cx=%2740%27%20cy=%2730%27%20r=%272%27/%3E%3Ccircle%20cx=%27120%27%20cy=%2755%27%20r=%271.6%27/%3E%3Ccircle%20cx=%27190%27%20cy=%2725%27%20r=%272%27/%3E%3Ccircle%20cx=%2770%27%20cy=%2795%27%20r=%271.5%27/%3E%3Ccircle%20cx=%27160%27%20cy=%2785%27%20r=%271.5%27/%3E%3C/g%3E%3C/svg%3E"
