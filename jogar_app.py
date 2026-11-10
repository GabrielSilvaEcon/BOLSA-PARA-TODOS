"""Página "Jogar": missões do dia, desafio da semana, desafios temáticos, boa decisão da semana e ranking da liga (J3 do PLANO_AREAS.md).

- Só desenha: as regras estão em jogar.py (lógica pura) e o placar da liga em jornada_liga_app.py (liga de estudo, já existente).
- Pontos premiam estudo e boas decisões de processo; nunca lucro, retorno ou risco. Nada da Jornada é bloqueado.
- Qualquer falha de banco ou da liga mostra um aviso curto e a página continua.
"""
from __future__ import annotations

import html

import streamlit as st

import educacao_app as EA
import jogar as JG
import jornada_icones as IC
import jornada_liga_app as LIGA
import jornada_player as PLAYER
import tema
import usuarios

_PAGINAS: dict = {}

CSS = """<style>
.jg-pills{display:flex;gap:8px;flex-wrap:wrap;margin:4px 0 10px;}
.jg-pill{background:#1B1442;border:1px solid #3D3182;border-radius:14px;padding:8px 14px;color:#F6F3FF !important;min-width:96px;}
.jg-pill b{display:block;font-size:1.3rem;line-height:1.2;color:#FFFFFF !important;}
.jg-pill span{font-size:.74rem;color:#BDB5E6 !important;text-transform:uppercase;letter-spacing:.05em;}
.jg-pill.dest{background:linear-gradient(135deg,#5B3FD6,#9B3FC8);border-color:#8B6CFF;}
.jg-sec{font-weight:900;font-size:1.08rem;margin:20px 0 6px;color:#F6F3FF !important;}
.jg-card{background:linear-gradient(145deg,#1E1650,#160F36);border:1px solid #3D3182;border-left:5px solid #7C5CFF;border-radius:16px;padding:12px 14px;margin:8px 0;color:#EDE9FF !important;}
.jg-card.ok{border-left-color:#2DD4A0;} .jg-card.trancado{opacity:.72;border-left-color:#5A5290;}
.jg-top{display:flex;align-items:center;gap:12px;}
.jg-ic{flex:0 0 42px;width:42px;height:42px;border-radius:12px;background:rgba(255,255,255,.08);display:flex;align-items:center;justify-content:center;}
.jg-ic img{width:26px;height:26px;display:block;}
.jg-t{font-weight:800;font-size:1.02rem;color:#F6F3FF !important;line-height:1.3;}
.jg-s{font-size:.88rem;color:#CFC8EE !important;line-height:1.4;margin-top:2px;}
.jg-pt{margin-left:auto;font-weight:900;font-size:.85rem;white-space:nowrap;color:#C5B3FF !important;}
.jg-card.ok .jg-pt{color:#2DD4A0 !important;}
.jg-bar{height:8px;background:#2A2060;border-radius:99px;overflow:hidden;margin-top:9px;}
.jg-bar i{display:block;height:100%;background:linear-gradient(90deg,#7C5CFF,#2DD4A0);border-radius:99px;}
.jg-nota{font-size:.82rem;color:#BDB5E6 !important;margin-top:4px;}
</style>"""


def registrar_paginas(paginas: dict) -> None:
    _PAGINAS.update({k: v for k, v in paginas.items() if v is not None})


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _barra(atual, alvo) -> str:
    pct = 0 if not alvo else max(0.0, min(1.0, atual / alvo)) * 100
    return f"<div class='jg-bar'><i style='width:{pct:.0f}%'></i></div>"


def _card_progresso(titulo: str, texto: str, atual, alvo, ok: bool, pontos: int, extra: str = "") -> str:
    marca = "✓ " if ok else ""
    return (f"<div class='jg-card {'ok' if ok else ''}'><div class='jg-top'><div style='min-width:0'>"
            f"<div class='jg-t'>{marca}{_e(titulo)}</div><div class='jg-s'>{_e(texto)}</div></div>"
            f"<div class='jg-pt'>+{pontos} pts</div></div>{_barra(atual, alvo)}"
            f"<div class='jg-nota'>{_e(atual)} de {_e(alvo)}</div>{extra}</div>")


# ------------------------------------------------------------------ ações
def _iniciar_desafio(unidade_id: str) -> None:
    PLAYER.iniciar_sessao(JG.iniciar_desafio(unidade_id, EA.prog()))


# ------------------------------------------------------------------ blocos
def _boa_decisao() -> tuple[bool, str]:
    """(cumpriu, texto). Lê a carteira virtual só para ver COMO ela foi montada; qualquer falha vira 'não cumpriu', sem erro na tela."""
    try:
        a = usuarios.ator()
        if not a:
            return False, "Entre na sua conta e participe da Competição para esta boa decisão contar."
        import banco
        import competicao_app as CA
        if not banco.cfg_disponivel():
            return False, "A Competição está indisponível agora."
        d = JG.diversificada(CA._pessoa(a)["cart"])
    except Exception:
        return False, "Não consegui ler sua carteira virtual agora."
    if d["ativos"] == 0 and not d["ok"]:
        return False, "Você ainda não tem posições na carteira virtual da Competição."
    return d["ok"], f"{d['ativos']} ativos relevantes em {d.get('classes', 0)} classe(s), maior peso {d['maior_peso'] * 100:.0f}%."


def _bloco_pontos(r: dict) -> None:
    pt = r["pontos"]
    st.markdown(
        "<div class='jg-pills'>"
        f"<div class='jg-pill dest'><b>{pt['total']}</b><span>pontos na semana</span></div>"
        f"<div class='jg-pill'><b>{r['feitas']}/{len(r['missoes'])}</b><span>missões hoje</span></div>"
        f"<div class='jg-pill'><b>{r['ofensiva']}</b><span>dias seguidos</span></div>"
        f"<div class='jg-pill'><b>{r['xp_hoje']}</b><span>XP hoje</span></div></div>", unsafe_allow_html=True)
    st.caption(f"Pontos da semana: {pt['estudo']} de estudo (XP) + {pt['missoes']} de missões + {pt['desafio']} do desafio da semana"
               f" + {pt['decisao']} de boa decisão. {JG.REGRA}")


def _bloco_missoes(r: dict) -> None:
    st.markdown("<div class='jg-sec'>Missões do dia</div>", unsafe_allow_html=True)
    for m in r["missoes"]:
        st.markdown(_card_progresso(m["titulo"], m["texto"], m["atual"], m["alvo"], m["ok"], m["pontos"]), unsafe_allow_html=True)
    if not r["feitas"]:
        st.button("Começar a estudar", key="jg_ir_jornada", icon=":material/school:", on_click=_ir, args=("jornada",))


def _bloco_semana(r: dict) -> None:
    d = r["semanal"]
    st.markdown("<div class='jg-sec'>Desafio da semana</div>", unsafe_allow_html=True)
    st.markdown(_card_progresso(d["titulo"], d["texto"], d["atual"], d["alvo"], d["ok"], d["pontos"]), unsafe_allow_html=True)


def _bloco_decisao(ok: bool, texto: str) -> None:
    st.markdown("<div class='jg-sec'>Boa decisão da semana</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='jg-card {'ok' if ok else ''}'><div class='jg-top'><div style='min-width:0'>"
        f"<div class='jg-t'>{'✓ ' if ok else ''}Carteira virtual diversificada</div>"
        f"<div class='jg-s'>No Wallet Game, monte uma carteira com {JG.MIN_ATIVOS} ou mais ativos, de pelo menos {JG.MIN_CLASSES} classes "
        f"(ações, FIIs, ETFs, fundos, renda fixa, cripto) e nenhum acima de {JG.PESO_MAXIMO * 100:.0f}% do patrimônio. "
        "Vale pela forma como a carteira foi montada, não pelo resultado.</div></div>"
        f"<div class='jg-pt'>+{JG.PTS_DECISAO} pts</div></div><div class='jg-nota'>{_e(texto)}</div></div>", unsafe_allow_html=True)


def _bloco_desafios(p: dict) -> None:
    st.markdown("<div class='jg-sec'>Desafios por tema</div>", unsafe_allow_html=True)
    st.caption("Conclua todas as lições de uma unidade da Jornada para abrir o desafio dela: 5 perguntas sorteadas da unidade. "
               "A Jornada continua toda aberta, com ou sem desafio.")
    for d in JG.desafios_tematicos(p):
        icone = IC.uri(d["svg"], d["cor"]) if IC.existe(d["svg"]) else ""
        img = f"<img src='{icone}' alt=''>" if icone else ""
        if d["liberado"]:
            nota = f"{d['perguntas']} perguntas na unidade · desafio aberto"
        else:
            nota = f"Falta{'m' if d['falta'] != 1 else ''} {d['falta']} lição{'ões' if d['falta'] != 1 else ''} da unidade na Jornada"
        st.markdown(
            f"<div class='jg-card {'' if d['liberado'] else 'trancado'}'><div class='jg-top'><div class='jg-ic'>{img}</div>"
            f"<div style='min-width:0'><div class='jg-t'>{'' if d['liberado'] else '🔒 '}{_e(d['titulo'])}</div>"
            f"<div class='jg-s'>{_e(d['descricao'])}</div></div></div><div class='jg-nota'>{_e(nota)}</div></div>", unsafe_allow_html=True)
        if d["liberado"]:
            st.button(f"Jogar desafio: {d['titulo']}", key=f"jg_des_{d['id']}", type="primary", width="stretch",
                      on_click=_iniciar_desafio, args=(d["id"],))


def _ir(url_path: str) -> None:
    alvo = _PAGINAS.get(url_path)
    if alvo is not None:
        st.switch_page(alvo)


# ------------------------------------------------------------------ página
def pagina_jogar() -> None:
    st.markdown(tema.cabecalho("🎯", "Missões", "Missões do dia, desafio da semana e desafios por tema. Os pontos vêm de estudar, nunca de arriscar."),
                unsafe_allow_html=True)
    st.markdown(CSS, unsafe_allow_html=True)
    if st.session_state.get("jor_sessao"):                  # desafio em andamento: mesmo player da Jornada
        PLAYER.tela(EA.prog, EA._set)
        return
    p = EA.prog()
    ok_dec, txt_dec = _boa_decisao()
    r = JG.resumo(p, boa_decisao=ok_dec)
    _bloco_pontos(r)
    _bloco_missoes(r)
    _bloco_semana(r)
    _bloco_decisao(ok_dec, txt_dec)
    _bloco_desafios(p)
    if not usuarios.usuario():
        st.caption("Sem entrar na conta, seu progresso vale só para esta sessão.")
    st.caption("Conteúdo educacional. Pontos e desafios premiam só o estudo e boas decisões de processo, nunca lucro, retorno ou risco.")
