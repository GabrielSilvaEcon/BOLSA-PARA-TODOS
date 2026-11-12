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
                   aceita_livre: bool = True, limite: int = 5):
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
            if livre and st.button(f"Usar “{livre}”", key=f"{chave}__livre", icon=":material/check:", width="stretch"):
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
