"""Escolha de ativo nas telas de análise (interface Streamlit), no padrão do Wallet Game: cartão único com título, campo de busca instantânea
e o Caramelo com balão; sugestões em botões logo abaixo; o ativo escolhido aparece numa etiqueta com ✕.
Só interface: quem decide o que buscar é a página (ações, FIIs, ETFs, fundos, cripto), que passa a função de busca. O visual está em analise_visual.py."""
from __future__ import annotations

import html

import streamlit as st

import arte_analisar as AA
import componentes_ux as CUX


def cartao_busca(chave: str, placeholder: str, tem: bool = False, n: int = 0, debounce: int = 250,
                 titulo_vazio: str = "Escolha para começar", titulo_tem: str = "Adicionar outro",
                 balao_vazio: str = "Digite o nome ou o código!", balao_tem: str = "Boa! Veja os resultados abaixo.") -> str:
    """Desenha o cartão de busca e devolve o que foi digitado (atualiza a cada letra). `n` muda o campo para zerá-lo depois de escolher."""
    r = {}
    with st.container(key=f"an_busca_card_{chave}"):
        ce, cd = st.columns([1.5, 1])
        with ce:
            st.markdown(f"<div class='abc-t'>{html.escape(titulo_tem if tem else titulo_vazio)}</div>", unsafe_allow_html=True)
            with st.container(key=f"an_busca_campo_{chave}"):
                r["q"] = CUX.busca(f"an_q_{chave}_{n}", placeholder, debounce)
        with cd:
            bal = balao_tem if tem else balao_vazio
            st.markdown(f"<div class='abc-r'><div class='abc-b'>{html.escape(bal)}</div>{AA.img('m_vitoria' if tem else 'm_lupa', 'abc-m', 'Caramelo')}</div>",
                        unsafe_allow_html=True)
    return (r.get("q") or "").strip()


def sugestoes(chave: str, itens: list[tuple[str, str]], ja=(), n: int = 0):
    """Botões de sugestão [(valor, rótulo)]. Devolve o valor tocado (ou None)."""
    escolhido = None
    with st.container(key=f"an_sugs_{chave}"):
        for k, (v, rot) in enumerate(itens):
            usada = v in ja
            if st.button(rot, key=f"an_s_{chave}_{n}_{k}", icon=":material/check:" if usada else ":material/add:", disabled=usada, width="stretch"):
                escolhido = v
    return escolhido


def chips(chave: str, itens: list[tuple[str, str]], ao_remover) -> None:
    """Etiquetas [(valor, rótulo)] com ✕; `ao_remover(valor)` roda no toque (recarrega a página)."""
    if not itens:
        return
    with st.container(key=f"an_chips_{chave}"):
        for v, rot in itens:
            st.button(rot, key=f"an_x_{chave}_{v}", icon=":material/close:", on_click=ao_remover, args=(v,))


def escolher_unico(chave: str, buscar, placeholder: str, rotulo=lambda v: str(v), livre=None, minimo: int = 1, debounce: int = 250,
                   titulo_vazio: str = "Escolha para começar", titulo_tem: str = "Trocar de ativo",
                   balao_vazio: str = "Digite o código ou o nome!", balao_tem: str = "Boa! A análise está abaixo.") -> str | None:
    """Escolha de UM ativo, guardado em st.session_state[chave] (que também pode ser preenchido por outras telas).
    `buscar(texto)` devolve [(valor, rótulo)]; `livre(código)` diz se um código digitado fora da lista vale (aparece o botão 'Usar …')."""
    ss = st.session_state
    rot_chave = f"an_rot_{chave}"

    @CUX.fragmento                                         # digitar só atualiza este bloco; escolher recarrega a página
    def _bloco():
        n = ss.get(f"an_qn_{chave}", 0)
        q = cartao_busca(chave, placeholder, tem=bool(ss.get(chave)), n=n, debounce=debounce, titulo_vazio=titulo_vazio, titulo_tem=titulo_tem,
                         balao_vazio=balao_vazio, balao_tem=balao_tem)
        if not q:
            return
        if len(q) < minimo:
            st.caption(f"Digite pelo menos {minimo} letras.")
            return
        achados = list(buscar(q) or [])
        if not achados and livre is not None:
            cod = "".join(ch for ch in q.upper() if ch.isalnum() or ch in "-.")[:14]
            if cod and livre(cod):
                achados = [(cod, f"Usar “{cod}”")]
        if not achados:
            st.caption("Nada encontrado. Confira o nome ou o código.")
            return
        for v, r in achados:
            ss.setdefault(rot_chave, {})[v] = r
        v = sugestoes(chave, achados, ja=(ss.get(chave),), n=n)
        if v is not None:
            ss[chave] = v
            ss[f"an_qn_{chave}"] = n + 1                   # campo zerado
            st.rerun()

    _bloco()
    atual = ss.get(chave)
    if atual:
        rot = (ss.get(rot_chave) or {}).get(atual) or rotulo(atual)
        chips(chave, [(atual, str(rot).replace("Usar “", "").replace("”", ""))], lambda _v: ss.pop(chave, None))
    return ss.get(chave) or None
