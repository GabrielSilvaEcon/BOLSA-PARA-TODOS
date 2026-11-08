"""Etapa 2 — Aba "Jornada" da Educação financeira: trilha em zigue-zague, estilo Duolingo.

- Só desenha o mapa a partir de jornada.mapa(); a lógica (XP, sessão, ofensiva) fica em jornada.py.
- Nada é trancado: a lição "próxima" é só destacada; as demais ficam livres para quem quiser pular.
- Não importa educacao_app (evita import circular): a função da aba recebe `prog` (devolve o progresso atual).
- O player da lição (um exercício por vez) chega na Etapa 3; por enquanto o clique inicia a sessão e mostra um aviso.
"""
from __future__ import annotations

import html

import streamlit as st

import conta_app as C
import jornada as JO

# Posição do botão em cada linha (0 = esquerda, 1 = centro, 2 = direita): onda que dá o zigue-zague.
ONDA = (1, 2, 1, 0)

CSS = """<style>
.jor-un{background:linear-gradient(145deg,#1E1650,#160F36);border:1px solid #3D3182;border-radius:16px;padding:12px 14px;margin:14px 0 6px;color:#EDE9FF !important;}
.jor-un .t{font-weight:800;font-size:1.05rem;color:#F6F3FF !important;}
.jor-un .s{margin-top:3px;color:#CFC8EE !important;font-size:.88rem;}
.jor-bar{height:8px;background:#2A2060;border-radius:99px;overflow:hidden;margin-top:8px;}
.jor-bar i{display:block;height:100%;background:linear-gradient(90deg,#7C5CFF,#2DD4A0);}
.jor-leg{text-align:center;color:#CFC8EE !important;font-size:.78rem;line-height:1.2;margin-top:-6px;word-break:break-word;}
/* mantém o zigue-zague no celular: o Streamlit empilha colunas em telas estreitas, e aqui isso desmancharia o caminho */
div[data-testid="stHorizontalBlock"]:has(.jor-zz){flex-wrap:nowrap !important;gap:.4rem !important;}
div[data-testid="stHorizontalBlock"]:has(.jor-zz) > div[data-testid="stColumn"],
div[data-testid="stHorizontalBlock"]:has(.jor-zz) > div[data-testid="column"]{min-width:0 !important;flex:1 1 0 !important;width:auto !important;}
</style>"""


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _comecar(lid: str) -> None:
    st.session_state["jor_sessao"] = JO.iniciar_sessao(lid)


def _cancelar() -> None:
    st.session_state.pop("jor_sessao", None)


def _cabecalho_unidade(u: dict) -> str:
    pct = (u["feitas"] / u["total"]) if u["total"] else 0.0
    selo = C._chip("Completa", "ok") if u["completa"] else C._chip(f"{u['feitas']}/{u['total']} lições")
    return (f"<div class='jor-un' style='border-left:5px solid {_e(u['cor'])}'>"
            f"<div class='t'>{_e(u['icone'])} {_e(u['titulo'])}</div><div class='s'>{_e(u['descricao'])}</div>"
            f"<div class='jor-bar'><i style='width:{pct * 100:.0f}%'></i></div><div style='margin-top:6px'>{selo}</div></div>")


def _no(col, l: dict, chave: str) -> None:
    """Um 'nó' da trilha: botão com o ícone da lição e o título embaixo."""
    feita = l["estado"] == "concluida"
    rotulo = ("✔ " if feita else "") + l["icone"]
    ajuda = f"{l['titulo']} · {l['exercicios']} exercícios" + (f" · melhor resultado {l['melhor'] * 100:.0f}%" if feita else "")
    col.button(rotulo, key=chave, type="primary" if l["estado"] == "proxima" else "secondary", help=ajuda,
               on_click=_comecar, args=(l["id"],), width="stretch")
    col.markdown(f"<div class='jor-leg'>{_e(l['titulo'])}</div>", unsafe_allow_html=True)


def _aviso_sessao(s: dict) -> None:
    from jornada_conteudo import LICAO_POR_ID  # import local: só para mostrar o nome
    nome = LICAO_POR_ID[s["licao"]]["titulo"] if s.get("licao") in LICAO_POR_ID else "Revisão"
    st.markdown(C._msg(f"Lição \"{nome}\" iniciada com {s['total']} exercícios. A tela de exercícios chega na próxima etapa.", "info"),
                unsafe_allow_html=True)
    st.button("← Voltar ao mapa", key="jor_voltar", on_click=_cancelar)


def aba(prog) -> None:
    """Desenha a trilha. `prog` é a função que devolve o progresso normalizado (educacao_app.prog)."""
    st.markdown(CSS, unsafe_allow_html=True)
    C._css()
    s = st.session_state.get("jor_sessao")
    if s:
        _aviso_sessao(s)
        return
    p = prog()
    st.markdown(C._titulo("Sua jornada", "Lições curtas, uma por vez. Comece pela destacada ou escolha qualquer outra: nada fica trancado."),
                unsafe_allow_html=True)
    mapa = JO.mapa(p)
    if not mapa:
        st.markdown(C._msg("A jornada ainda não tem lições.", "info"), unsafe_allow_html=True)
        return
    n = 0
    for u in mapa:
        st.markdown(_cabecalho_unidade(u), unsafe_allow_html=True)
        for l in u["licoes"]:
            cols = st.columns(3)
            pos = ONDA[n % len(ONDA)]
            cols[0].markdown("<span class='jor-zz'></span>", unsafe_allow_html=True)   # marcador usado pelo CSS do zigue-zague
            _no(cols[pos], l, f"jor_no_{l['id']}")
            n += 1
    st.caption("Conteúdo educacional. XP e conquistas premiam só o estudo, nunca operações ou risco.")
