"""Aba "Jornada" da Educação financeira: trilha em zigue-zague, estilo Duolingo.

- Só desenha o mapa a partir de jornada.mapa(); a lógica (XP, sessão, ofensiva) fica em jornada.py e os ícones em jornada_icones.py.
- Nada é trancado: a lição "próxima" é só destacada (balão COMEÇAR); as demais ficam livres.
- Não importa educacao_app (evita import circular): a função da aba recebe `prog` (devolve o progresso atual).
- Cada nó é um st.button de verdade (clicável) estilizado por CSS: a classe `st-key-<key>` do Streamlit identifica o estado
  (jor_nc_ concluída, jor_np_ próxima, jor_nl_ livre) e o ícone entra como imagem de fundo.
- Clicar num nó inicia a lição e a aba passa a mostrar o player (jornada_player.py) até a pessoa concluir ou sair.
"""
from __future__ import annotations

import html

import streamlit as st

import conta_app as C
import jornada as JO
import jornada_icones as IC
import jornada_player as PLAYER

COLUNAS = 5
ONDA = (2, 3, 2, 1)          # coluna do nó em cada linha (0..4): centro, direita, centro, esquerda
LARGURA = 380                # largura máxima do mapa (px), centralizado
PREFIXO = {"concluida": "jor_nc_", "proxima": "jor_np_", "livre": "jor_nl_"}

CSS_BASE = f"""<style>
.jor-stats{{display:flex;gap:8px;justify-content:center;flex-wrap:wrap;margin:2px 0 6px;}}
.jor-pill{{display:flex;align-items:center;gap:7px;background:#1B1442;border:1px solid #3D3182;border-radius:99px;padding:5px 13px 5px 9px;color:#F6F3FF !important;font-weight:800;font-size:.92rem;}}
.jor-pill img{{width:20px;height:20px;display:block;}}
.jor-pill small{{color:#BDB5E6 !important;font-weight:600;font-size:.72rem;}}
.jor-un{{max-width:{LARGURA}px;margin:20px auto 18px;border-radius:18px;padding:14px 16px;box-shadow:0 5px 0 rgba(0,0,0,.38);}}
.jor-un .top{{display:flex;align-items:center;gap:12px;}}
.jor-un .ic{{flex:0 0 46px;width:46px;height:46px;border-radius:13px;background:rgba(0,0,0,.18);display:flex;align-items:center;justify-content:center;}}
.jor-un .ic img{{width:28px;height:28px;display:block;}}
.jor-un .tx{{flex:1;min-width:0;}}
.jor-un .t{{font-weight:900;font-size:1.05rem;line-height:1.25;}}
.jor-un .s{{font-size:.84rem;line-height:1.3;opacity:.9;margin-top:2px;}}
.jor-un .n{{font-weight:900;font-size:.95rem;white-space:nowrap;}}
.jor-un .bar{{height:8px;background:rgba(0,0,0,.28);border-radius:99px;overflow:hidden;margin-top:11px;}}
.jor-un .bar i{{display:block;height:100%;background:#fff;border-radius:99px;}}
.jor-con{{max-width:{LARGURA}px;margin:-8px auto;height:30px;}}
.jor-con svg{{display:block;width:100%;height:100%;overflow:visible;}}
.jor-leg{{position:relative;left:50%;transform:translateX(-50%);width:128px;text-align:center;color:#EDE9FF !important;font-weight:700;font-size:.8rem;line-height:1.2;margin-top:12px;}}
.jor-bolha{{position:relative;left:50%;width:max-content;transform:translateX(-50%);background:#fff;color:#5B3FD6 !important;font-weight:900;font-size:.7rem;letter-spacing:.07em;padding:5px 11px;border-radius:11px;margin-bottom:9px;animation:jor-quica 1.5s ease-in-out infinite;}}
.jor-bolha:after{{content:"";position:absolute;left:50%;bottom:-6px;margin-left:-6px;border:6px solid transparent;border-bottom:0;border-top-color:#fff;}}
@keyframes jor-quica{{0%,100%{{transform:translate(-50%,0)}}50%{{transform:translate(-50%,-5px)}}}}
@keyframes jor-pulso{{0%{{box-shadow:0 6px 0 #5B3FD6,0 0 0 0 rgba(139,108,255,.55)}}100%{{box-shadow:0 6px 0 #5B3FD6,0 0 0 16px rgba(139,108,255,0)}}}}
/* mantém o zigue-zague no celular: o Streamlit empilha colunas em telas estreitas, e aqui isso desmancharia o caminho */
div[data-testid="stHorizontalBlock"]:has(.jor-zz){{flex-wrap:nowrap !important;gap:0 !important;max-width:{LARGURA}px;margin:0 auto;width:100%;}}
div[data-testid="stHorizontalBlock"]:has(.jor-zz) > div[data-testid="stColumn"],
div[data-testid="stHorizontalBlock"]:has(.jor-zz) > div[data-testid="column"]{{min-width:0 !important;flex:1 1 0 !important;width:auto !important;}}
/* nó redondo em 3D */
div[class*="st-key-jor_n"]{{display:flex;justify-content:center;}}
div[class*="st-key-jor_n"] button{{position:relative;width:76px !important;height:76px !important;min-height:76px !important;padding:0 !important;border-radius:50% !important;
  border:0 !important;background-repeat:no-repeat !important;background-position:center !important;background-size:38px !important;
  box-shadow:0 6px 0 var(--sh) !important;transition:transform .08s,box-shadow .08s,filter .15s;}}
div[class*="st-key-jor_n"] button *{{font-size:0 !important;color:transparent !important;}}
div[class*="st-key-jor_n"] button:hover{{filter:brightness(1.1);}}
div[class*="st-key-jor_n"] button:active,div[class*="st-key-jor_n"] button:focus:active{{transform:translateY(4px);box-shadow:0 2px 0 var(--sh) !important;}}
div[class*="st-key-jor_n"] button:focus{{outline:none !important;}}
div[class*="st-key-jor_nc_"] button{{--sh:#178A68;background-color:#2DD4A0 !important;}}
div[class*="st-key-jor_np_"] button{{--sh:#5B3FD6;background-color:#8B6CFF !important;animation:jor-pulso 1.8s ease-out infinite;}}
div[class*="st-key-jor_nl_"] button{{--sh:#150F38;background-color:#2A2060 !important;border:2px solid #4B3E99 !important;}}
div[class*="st-key-jor_nc_"] button:after{{content:"";position:absolute;top:-3px;right:-3px;width:26px;height:26px;border-radius:50%;border:3px solid #110C2E;
  background:#FFC94D url("{IC.uri('check', '#5A3B00')}") center/13px no-repeat;}}
</style>"""


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _cor_ok(cor: str) -> str:
    c = str(cor)
    return c if len(c) == 7 and c[0] == "#" and all(h in "0123456789abcdefABCDEF" for h in c[1:]) else "#2DD4A0"


def _texto_sobre(cor: str) -> str:
    """Texto escuro sobre cor clara e branco sobre cor escura (contraste legível)."""
    c = _cor_ok(cor)
    r, g, b = (int(c[i:i + 2], 16) / 255 for i in (1, 3, 5))
    lum = 0.2126 * r + 0.7152 * g + 0.0722 * b
    return "#0B0821" if lum > 0.45 else "#FFFFFF"


# ------------------------------------------------------------------ pedaços de HTML (funções puras, testáveis sem Streamlit)
def css_icones(mapa: list[dict]) -> str:
    """Regras que colocam o ícone de cada lição como fundo do botão (a cor do ícone depende do estado)."""
    regras = []
    for u in mapa:
        for l in u["licoes"]:
            cor = "#9A8FD6" if l["estado"] == "livre" else "#FFFFFF"
            regras.append(f'div[class*="st-key-{PREFIXO[l["estado"]]}{l["id"]}"] button{{background-image:url("{IC.uri(l["svg"], cor)}") !important;}}')
    return "<style>" + "".join(regras) + "</style>"


def html_stats(r: dict) -> str:
    def pill(icone, cor, valor, rotulo):
        return f"<div class='jor-pill'><img src='{IC.uri(icone, cor)}' alt=''>{_e(valor)} <small>{_e(rotulo)}</small></div>"
    return ("<div class='jor-stats'>" + pill("chama", "#FF9B3D", r["ofensiva"], "dia seguido" if r["ofensiva"] == 1 else "dias seguidos") + pill("raio", "#FFC94D", r["xp"], "XP")
            + pill("alvo", "#2DD4A0", f"{min(r['xp_hoje'], r['meta_dia'])}/{r['meta_dia']}", "meta de hoje") + "</div>")


def html_unidade(u: dict) -> str:
    cor = _cor_ok(u["cor"])
    txt = _texto_sobre(cor)
    pct = (u["feitas"] / u["total"]) if u["total"] else 0.0
    return (f"<div class='jor-un' style='background:linear-gradient(135deg,rgba(255,255,255,.18),rgba(0,0,0,.2)),{cor};color:{txt} !important'>"
            f"<div class='top'><div class='ic'><img src='{IC.uri(u['svg'], txt)}' alt=''></div>"
            f"<div class='tx'><div class='t' style='color:{txt} !important'>{_e(u['titulo'])}</div><div class='s' style='color:{txt} !important'>{_e(u['descricao'])}</div></div>"
            f"<div class='n' style='color:{txt} !important'>{u['feitas']}/{u['total']}</div></div>"
            f"<div class='bar'><i style='width:{pct * 100:.0f}%;background:#fff'></i></div></div>")


def _x(coluna: int) -> float:
    return (coluna * 2 + 1) / (COLUNAS * 2) * 300


def html_conector(col_a: int, col_b: int, feito: bool) -> str:
    """Linha pontilhada curva entre dois nós. Verde quando a lição de cima já foi concluída."""
    xa, xb = _x(col_a), _x(col_b)
    cor = "#2DD4A0" if feito else "#4B3E99"
    return (f"<div class='jor-con'><svg viewBox='0 0 300 30' preserveAspectRatio='none'><path d='M{xa:.1f} 0 C{xa:.1f} 15 {xb:.1f} 15 {xb:.1f} 30' fill='none' "
            f"stroke='{cor}' stroke-width='4' stroke-linecap='round' stroke-dasharray='1 9' vector-effect='non-scaling-stroke'/></svg></div>")


def html_legenda(titulo: str) -> str:
    return f"<div class='jor-leg'>{_e(titulo)}</div>"


HTML_BOLHA = "<div class='jor-bolha'>COMEÇAR</div>"
HTML_MARCADOR = "<span class='jor-zz'></span>"


# ------------------------------------------------------------------ ações
def _comecar(lid: str) -> None:
    PLAYER.iniciar(lid)


def _no(col, l: dict) -> None:
    """Um nó da trilha: balão (só na próxima), botão redondo com o ícone e o título embaixo."""
    feita = l["estado"] == "concluida"
    if l["estado"] == "proxima":
        col.markdown(HTML_BOLHA, unsafe_allow_html=True)
    ajuda = f"{l['titulo']} · {l['exercicios']} exercícios" + (f" · melhor resultado {l['melhor'] * 100:.0f}%" if feita else "")
    col.button("\u200b", key=f"{PREFIXO[l['estado']]}{l['id']}", help=ajuda, on_click=_comecar, args=(l["id"],))
    col.markdown(html_legenda(l["titulo"]), unsafe_allow_html=True)


def aba(prog, set_prog) -> None:
    """Desenha a trilha ou, com uma lição em andamento, o player. `prog` devolve o progresso normalizado e `set_prog` o grava (educacao_app)."""
    st.markdown(CSS_BASE, unsafe_allow_html=True)
    C._css()
    if st.session_state.get("jor_sessao"):
        PLAYER.tela(prog, set_prog)
        return
    p = prog()
    mapa = JO.mapa(p)
    if not mapa:
        st.markdown(C._msg("A jornada ainda não tem lições.", "info"), unsafe_allow_html=True)
        return
    st.markdown(css_icones(mapa), unsafe_allow_html=True)
    st.markdown(html_stats(JO.resumo(p)), unsafe_allow_html=True)
    for u in mapa:
        st.markdown(html_unidade(u), unsafe_allow_html=True)
        anterior = None
        for i, l in enumerate(u["licoes"]):
            pos = ONDA[i % len(ONDA)]
            if anterior is not None:
                st.markdown(html_conector(anterior[0], pos, anterior[1]), unsafe_allow_html=True)
            cols = st.columns(COLUNAS)
            cols[0].markdown(HTML_MARCADOR, unsafe_allow_html=True)      # marcador usado pelo CSS do zigue-zague
            _no(cols[pos], l)
            anterior = (pos, l["estado"] == "concluida")
    st.caption("Conteúdo educacional. XP e conquistas premiam só o estudo, nunca operações ou risco.")
