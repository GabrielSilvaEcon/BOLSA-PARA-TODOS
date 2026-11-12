"""Seletor único de destino ao adicionar um ativo: Carteira Virtual (simulação) ou Carteira Real (registro declarado).

Todos os botões "Adicionar à carteira" do app usam `popover_destino`, para o comportamento ser o mesmo em ações, ETFs, FIIs,
fundos e cripto. Nada é gravado antes da escolha; depois de gravar, a escolha é limpa e a próxima inclusão pergunta de novo.
"""
from __future__ import annotations

try:
    import streamlit as st
except ImportError:        # testes puros rodam sem o Streamlit
    st = None

VIRTUAL, REAL = "virtual", "real"
ROTULOS = {VIRTUAL: "Carteira Virtual", REAL: "Carteira Real"}
CHAVE_LOTES = {VIRTUAL: "cart_ficticia", REAL: "cart_real"}          # chaves de sessão já existentes: nada muda nos cálculos
CHAVE_FUNDOS = {VIRTUAL: "cart_fundos_virtual", REAL: "cart_fundos_cvm"}
AVISO_VIRTUAL = "Simulação: não envolve dinheiro de verdade."
AVISO_REAL = "Registro informado por você (ou importado da sua corretora). O app não compra nem vende nada e não envia ordens."


def eh_virtual(destino) -> bool:
    """Aceita o código novo ('virtual') e o texto antigo ('Fictícia')."""
    return str(destino).strip().lower() in ("virtual", "fictícia", "ficticia", "cart_ficticia")


def normalizar(destino) -> str:
    return VIRTUAL if eh_virtual(destino) else REAL


def chave_lotes(destino) -> str:
    return CHAVE_LOTES[normalizar(destino)]


def _definir(chave: str, valor):
    st.session_state[chave] = valor


def seletor(key: str) -> str | None:
    """Mostra as duas opções. Devolve 'virtual', 'real' ou None (ainda sem escolha: nada deve ser gravado)."""
    sk = f"cd_{key}"
    atual = st.session_state.get(sk)
    if atual not in (VIRTUAL, REAL):
        atual = None
    c1, c2 = st.columns(2)
    c1.button(ROTULOS[VIRTUAL], key=f"cdb_v_{key}", icon=":material/science:", width="stretch",
              type="primary" if atual == VIRTUAL else "secondary", on_click=_definir, args=(sk, VIRTUAL))
    c2.button(ROTULOS[REAL], key=f"cdb_r_{key}", icon=":material/account_balance_wallet:", width="stretch",
              type="primary" if atual == REAL else "secondary", on_click=_definir, args=(sk, REAL))
    if atual:
        st.caption(AVISO_VIRTUAL if atual == VIRTUAL else AVISO_REAL)
    return atual


def limpar(key: str) -> None:
    st.session_state.pop(f"cd_{key}", None)


def popover_destino(key: str, formulario) -> None:
    """Botão 'Adicionar à carteira' com a escolha Virtual/Real. `formulario(destino)` desenha os campos e devolve True se gravou."""
    with st.popover("💼 Adicionar à carteira"):
        destino = VIRTUAL                       # só existe a carteira virtual (a carteira real foi retirada do app)
        st.caption(AVISO_VIRTUAL)
        if formulario(destino):
            limpar(key)
            st.rerun()
