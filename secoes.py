"""Menu suspenso de seções: substitui `st.tabs` quando há muitas abas (celular).

Uso igual ao do st.tabs:  abas = secoes.abas(["A", "B", "C", "D"]);  with abas[0]: ...
Mostra um seletor compacto com a seção atual e só exibe o conteúdo dela. Com menos de `minimo` seções, usa as abas normais
(2 ou 3 abas curtas cabem na tela). A escolha fica guardada no session_state, então a pessoa volta à mesma seção.
"""
from __future__ import annotations

import hashlib
import re
import sys

import streamlit as st

_ICONE = re.compile(r":material/[a-z0-9_]+:\s*")

_CSS = """<style>
[class*="st-key-abaoff_"] {display:none !important;}
[class*="st-key-abasel_"] {margin:0 0 .6rem 0;}
[class*="st-key-abasel_"] [data-baseweb="select"] > div {min-height:44px; border-radius:14px; font-weight:800;}
[class*="st-key-abasel_"] [data-baseweb="select"] div[value], [class*="st-key-abasel_"] [data-baseweb="select"] span {font-weight:800;}
</style>"""


CORES = ("#8B6CFF", "#2BA7C9", "#3DDC97", "#F2B84B", "#FF9B3D", "#FF6B8A", "#B02FC8", "#6E8BFF")
# palavra do rótulo (sem acento, minúscula) -> ícone Material; vale a primeira que aparecer
ICONES = (("resumo", "dashboard"), ("painel", "dashboard"), ("visao geral", "dashboard"), ("aloca", "pie_chart"), ("diversific", "hub"),
          ("risco", "shield"), ("rentab", "trending_up"), ("desempenho", "trending_up"), ("renda", "payments"), ("otimiz", "tune"),
          ("rebal", "balance"), ("cenario", "insights"), ("relatorio", "description"), ("preco justo", "price_check"), ("multiplo", "calculate"),
          ("dividend", "savings"), ("saude", "health_and_safety"), ("dcf", "account_tree"), ("fluxo", "account_tree"), ("tecnic", "candlestick_chart"),
          ("grafico", "candlestick_chart"), ("principais", "star"), ("ultimas", "schedule"), ("economi", "public"), ("corporativ", "business"),
          ("cripto", "currency_bitcoin"), ("carteira", "account_balance_wallet"), ("token", "toll"), ("on-chain", "link"), ("seguranca", "lock"),
          ("historico", "history"), ("compar", "compare_arrows"), ("ajuda", "help"), ("composicao", "donut_small"), ("custo", "request_quote"),
          ("noticia", "newspaper"), ("liga", "groups"), ("ranking", "leaderboard"), ("simul", "science"), ("estresse", "bolt"), ("meta", "flag"))
_FALLBACK = ("bolt", "category", "insights", "tune", "flag", "widgets")


def _sem_acento(t: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFD", t.lower()) if unicodedata.category(c) != "Mn")


def icone_da_secao(nome: str, i: int = 0) -> str:
    """Ícone Material da seção pelo nome; sem palavra conhecida, um ícone neutro que varia com a posição."""
    n = _sem_acento(nome)
    for chave, ic in ICONES:
        if chave in n:
            return f":material/{ic}:"
    return f":material/{_FALLBACK[i % len(_FALLBACK)]}:"


def _limpo(rotulo: str) -> str:
    return _ICONE.sub("", str(rotulo)).strip()


def _alternar(chave: str, rotulo: str) -> None:
    """Toque na barra: abre a seção; tocar na que já está aberta fecha. Só uma fica aberta por vez (menos rolagem)."""
    st.session_state[chave] = None if st.session_state.get(chave) == rotulo else rotulo


def aberta(key: str) -> str | None:
    """Rótulo da seção aberta no acordeão de `key` (None se todas estiverem fechadas). Serve para só calcular a seção visível."""
    return st.session_state.get(f"acd_{key}")


def abas(rotulos: list[str], key: str | None = None, minimo: int = 4, resumos: dict | None = None) -> list:
    """Devolve uma lista de containers (um por seção). Com `minimo` seções ou mais, cada uma vira uma barra que abre e fecha (acordeão);
    `resumos` ({rótulo: texto curto}) coloca o resultado da análise na própria barra. Só a seção aberta fica visível.
    Com menos seções, usa as abas normais."""
    rotulos = [str(r) for r in rotulos]
    if len(rotulos) < minimo:
        return st.tabs(rotulos)
    if key is None:
        quadro = sys._getframe(1)
        ident = f"{quadro.f_code.co_filename}:{quadro.f_lineno}|" + "|".join(r.replace("🔒 ", "") for r in rotulos)
        key = hashlib.md5(ident.encode("utf-8")).hexdigest()[:10]
    chave = f"acd_{key}"
    if st.session_state.get(chave) not in rotulos:
        st.session_state.pop(chave, None)
    aberto = st.session_state.get(chave)
    resumos = resumos or {}
    saida = []
    st.markdown("<style>" + "".join(f'.st-key-acdbar_{key}_{i}{{--ac:{CORES[i % len(CORES)]}}}' for i in range(len(rotulos))) + "</style>", unsafe_allow_html=True)
    for i, r in enumerate(rotulos):
        on = aberto == r
        res = resumos.get(r) or resumos.get(r.replace("🔒 ", ""))
        nome = _limpo(r)
        with st.container(key=f"acdbar_{key}_{i}"):
            st.button(f"{nome}  ·  {res}" if res else nome, key=f"{chave}_b{i}", type="primary" if on else "secondary",
                      icon=icone_da_secao(nome, i), on_click=_alternar, args=(chave, r), width="stretch")
        saida.append(st.container(key=f"acdon_{key}_{i}" if on else f"abaoff_{key}_{i}"))
    return saida
