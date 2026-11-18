"""Tela de Ranking no formato mobile game (só HTML/CSS; sem Streamlit, sem banco e sem rede).

Layout da referência do TickerHunters (nov/2026), tela inteira, sem janela nem botão de fechar:
  1. Topo: arte do mascote com a sua ficha (avatar, nome, posição) e o saldo de Ticker Coins
  2. Título RANKING com a coroa
  3. Três abas centralizadas: Ticker Battle · Trade Battle · Carteira
  4. Global / Amigos
  5. Faixa MODO RANQUEADO e a regra de classificação do jogo
  6. Linhas: posição (ouro, prata, bronze, demais), avatar no escudo, nome e @usuário, pontuação

Cada linha é um dict: {pos, nome, sub, valor, src, eu}. Dado ausente vira estado vazio, nunca número inventado.
As artes ficam em static/ranking (servidas pelo Streamlit em app/static/ranking).
"""
from __future__ import annotations

import html

_E = html.escape
Q = "html body .stApp.stApp.stApp"
ARTE = "app/static/ranking/"

ABAS = (  # (chave, rótulo, arte do ícone, cor)
    ("ticker", "Ticker Battle", "ticker", "#B06BFF"),
    ("trade", "Trade Battle", "trade", "#3DA9FF"),
    ("carteira", "Carteira", "carteira", "#3DDC6A"),
)
ESCOPOS = (("global", "Global"), ("amigos", "Amigos"))
_COR_POS = {1: ("#FFE27A", "#E9A80C", "#5A3A00"), 2: ("#EEF2FA", "#9FAAC0", "#2B3346"), 3: ("#FFB27A", "#C9672A", "#4A1F00")}
_COR_ESCUDO = ("#B06BFF", "#3DA9FF", "#3DDC6A", "#FF5BA8", "#FFC23D", "#2EE5D0")


def arte(nome: str) -> str:
    return f"{ARTE}{nome}.webp"


def _num(v) -> str:
    try:
        return f"{int(v):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


# ------------------------------------------------------------------ 1. topo
def html_topo(nome: str, avatar_src: str, pos, tc) -> str:
    av = f"<img src='{_E(avatar_src)}' alt=''>" if avatar_src else f"<span>{_E((nome[:1] or '?').upper())}</span>"
    p = f"#{int(pos)}" if pos else "—"
    return ("<div class='rk-topo'>"
            f"<img class='rk-masc' src='{arte('mascote')}' alt=''>"
            "<div class='rk-ficha'>"
            f"<div class='rk-esc rk-esc-eu'><div class='rk-av'>{av}</div></div>"
            f"<div class='rk-fn'><b>{_E(nome or 'Jogador')}</b><span>🏆 {_E(p)}</span></div></div>"
            f"<div class='rk-tc' title='Seu saldo de Ticker Coins'>🪙 <b>{_E(_num(tc))}</b></div>"
            "</div>")


# ------------------------------------------------------------------ 2. título · 3. abas · 4. escopo
def html_titulo() -> str:
    return f"<div class='rk-tit'><img src='{arte('coroa')}' alt=''><b>RANKING</b></div>"


def html_aba(chave: str, ativa: bool) -> str:
    _c, rot, ic, cor = next(a for a in ABAS if a[0] == chave)
    return (f"<div class='rk-aba{' on' if ativa else ''}' style='--c:{cor}'><img src='{arte(ic)}' alt=''><b>{_E(rot)}</b></div>")


def html_escopo(chave: str, ativo: bool) -> str:
    rot = dict(ESCOPOS)[chave]
    ic = "👥 " if chave == "amigos" else ""
    return f"<div class='rk-esc-b{' on' if ativo else ''}'>{ic}{_E(rot)}</div>"


# ------------------------------------------------------------------ 5. faixa
def html_faixa(regra: str) -> str:
    return (f"<div class='rk-faixa'><img src='{arte('faixa')}' alt='Modo ranqueado'></div>"
            f"<div class='rk-regra'>{_E(regra)}</div>")


# ------------------------------------------------------------------ 6. linhas
def html_linha(r: dict) -> str:
    pos = int(r.get("pos") or 0)
    claro, escuro, txt = _COR_POS.get(pos, ("#5B78C9", "#2A3C8A", "#FFFFFF"))
    escudo = _COR_ESCUDO[(pos - 1) % len(_COR_ESCUDO)] if pos else _COR_ESCUDO[0]
    src = r.get("src") or ""
    nome = str(r.get("nome") or "Jogador")
    av = f"<img src='{_E(src)}' alt=''>" if src else f"<span>{_E(nome[:1].upper())}</span>"
    top = " top" if pos == 1 else ""
    eu = " eu" if r.get("eu") else ""
    sub = str(r.get("sub") or "")
    return (f"<div class='rk-lin{top}{eu}'>"
            f"<span class='rk-pos' style='--a:{claro};--b:{escuro};--t:{txt}'>{pos or '—'}</span>"
            f"<span class='rk-esc' style='--e:{escudo}'><span class='rk-av'>{av}</span></span>"
            f"<span class='rk-nm'><b>{_E(nome)}{' 👑' if pos == 1 else ''}</b><small>{_E(sub)}</small></span>"
            f"<span class='rk-pts'><img src='{arte('pts')}' alt=''><b>{_E(str(r.get('valor') or '—'))}</b></span>"
            "</div>")


def html_vazio(texto: str) -> str:
    return f"<div class='rk-vazio'>{_E(texto)}</div>"


# ------------------------------------------------------------------ CSS
def css() -> str:
    c = Q
    t = f"{c} .st-key-rk_tela"
    branco = "color:#F4F6FF !important;-webkit-text-fill-color:#F4F6FF !important"
    lila = "color:#C9C2F2 !important;-webkit-text-fill-color:#C9C2F2 !important"
    return ("<style>"
            # a tela tem a altura do celular (menos o cabeçalho do app e a barra de baixo): nada rola além da lista
            f"{t}{{max-width:500px !important;margin:0 auto !important;gap:8px !important;box-sizing:border-box;"
            "height:calc(100dvh - 3.85rem - var(--dz-barra-h,64px) - env(safe-area-inset-bottom,0px) - 76px) !important;min-height:520px;flex-wrap:nowrap !important;overflow:hidden}"
            f"{c} :has(>.st-key-rk_tela){{flex-shrink:0 !important;height:auto !important;max-height:none !important}}{t}{{flex:0 0 auto !important}}"
            f"{t}>*{{flex:0 0 auto !important}}"
            # a caixa da lista (o Streamlit a embrulha num stLayoutWrapper) ocupa o que sobra da altura e rola por dentro
            f"{t}>:has(.st-key-rk_lista){{flex:1 1 0 !important;min-height:180px !important;display:flex !important;flex-direction:column}}"
            f"{t} [data-testid='stElementContainer'],{t} [data-testid='stMarkdownContainer']{{margin-bottom:0 !important}}"
            # 1. topo
            f"{c} .rk-topo{{position:relative;height:96px;border-radius:16px;overflow:hidden;display:flex;align-items:flex-end;justify-content:space-between;gap:8px;padding:8px}}"
            f"{c} .rk-masc{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;object-position:50% 30%;"
            "-webkit-mask:linear-gradient(180deg,#000 55%,transparent);mask:linear-gradient(180deg,#000 55%,transparent)}"
            f"{c} .rk-ficha{{position:relative;display:flex;align-items:center;gap:6px;padding:4px 12px 4px 4px;border-radius:12px;"
            "background:linear-gradient(90deg,rgba(14,10,46,.92),rgba(14,10,46,.6));border:1.5px solid rgba(176,107,255,.6)}"
            f"{c} .rk-fn{{display:flex;flex-direction:column;line-height:1.1}}"
            f"{c} .rk-fn b{{font-size:.9rem;font-weight:900;{branco}}}{c} .rk-fn span{{font-size:.76rem;font-weight:900;color:#FFD76A !important;-webkit-text-fill-color:#FFD76A !important}}"
            f"{c} .rk-tc{{position:relative;padding:4px 10px;border-radius:99px;background:rgba(14,10,46,.9);border:1.5px solid #F2B84B;font-size:.8rem}}"
            f"{c} .rk-tc b{{font-weight:900;color:#FFD76A !important;-webkit-text-fill-color:#FFD76A !important}}"
            # 2. título
            f"{c} .rk-tit{{display:flex;flex-direction:column;align-items:center;line-height:1;margin:2px 0 0}}"
            f"{c} .rk-tit img{{width:30px;height:auto;margin-bottom:-2px}}"
            f"{c} .rk-tit b{{font-size:clamp(1.6rem,8vw,2.1rem);font-weight:900;letter-spacing:.04em;{branco};text-shadow:0 3px 0 #3A1F8E,0 0 14px rgba(176,107,255,.7)}}"
            # 3. abas: três do mesmo tamanho, centralizadas na linha
            f"{c} .st-key-rk_abas{{display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px !important;justify-content:center;max-width:420px;"
            "width:100%;margin:0 auto !important}"
            f"{c} .st-key-rk_abas>*{{min-width:0}}"
            f"{c} .rk-aba{{height:62px;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;border-radius:12px;"
            "background:linear-gradient(180deg,#1C2366,#121646);border:1.5px solid color-mix(in srgb,var(--c) 55%,transparent)}"
            f"{c} .rk-aba img{{height:28px;width:auto;object-fit:contain}}"
            f"{c} .rk-aba b{{font-size:.7rem;font-weight:900;white-space:nowrap;{branco}}}"
            f"{c} .rk-aba.on{{background:linear-gradient(180deg,color-mix(in srgb,var(--c) 45%,#1C1466),#1A0F55);border:2px solid var(--c);"
            "box-shadow:0 0 14px -2px var(--c),inset 0 1px 0 rgba(255,255,255,.25)}"
            # 4. escopo
            f"{c} .st-key-rk_escopo{{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr));gap:6px !important;padding:4px;border-radius:12px;"
            "background:#121646;border:1.5px solid #2B3A8C;max-width:320px;width:100%;margin:0 auto !important;box-sizing:border-box}"
            f"{c} .st-key-rk_escopo>*{{min-width:0}}"
            f"{c} .rk-esc-b{{height:32px;display:flex;align-items:center;justify-content:center;border-radius:9px;font-size:.84rem;font-weight:900;{branco};"
            "background:#1C2366}"
            f"{c} .rk-esc-b.on{{background:linear-gradient(180deg,#9A5CFF,#6A2FE0);box-shadow:0 0 12px -2px #9A5CFF}}"
            # 5. faixa
            f"{c} .rk-faixa{{line-height:0;border-radius:12px;overflow:hidden;border:1.5px solid #4A2FA8}}{c} .rk-faixa img{{width:100%;height:auto;max-height:64px;object-fit:cover;display:block}}"
            f"{c} .rk-regra{{text-align:center;font-size:.68rem;font-weight:700;{lila};margin-top:-2px}}"
            # 6. linhas
            f"{t} .st-key-rk_lista{{gap:5px !important;flex:1 1 0 !important;min-height:0 !important;height:100% !important;overflow-y:auto !important;overscroll-behavior:contain;"
            "-webkit-overflow-scrolling:touch;padding:2px 2px 6px;border-radius:12px;scrollbar-width:thin;scrollbar-color:#4A62D0 transparent}"
            f"{c} .st-key-rk_lista>*{{flex:0 0 auto}}"
            f"{c} .rk-lin{{display:grid;grid-template-columns:auto auto minmax(0,1fr) auto;align-items:center;gap:8px;padding:5px 8px;border-radius:12px;"
            "background:linear-gradient(180deg,#22307A,#18205C);border:1.5px solid #3A4FB0}"
            f"{c} .rk-lin.top{{background:linear-gradient(180deg,#5A4314,#2A2140);border-color:#FFC23D;box-shadow:0 0 14px -4px #FFC23D}}"
            f"{c} .rk-lin.eu{{border-color:#3DDC97;box-shadow:0 0 12px -4px #3DDC97}}"
            f"{c} .rk-pos{{width:30px;height:30px;display:grid;place-items:center;font-weight:900;font-size:.95rem;"
            "color:var(--t) !important;-webkit-text-fill-color:var(--t) !important;background:linear-gradient(180deg,var(--a),var(--b));"
            "clip-path:polygon(25% 0,75% 0,100% 25%,100% 75%,75% 100%,25% 100%,0 75%,0 25%)}"
            f"{c} .rk-esc{{width:36px;height:40px;display:grid;place-items:center;background:var(--e,#B06BFF);"
            "clip-path:polygon(50% 0,100% 18%,100% 70%,50% 100%,0 70%,0 18%)}"
            f"{c} .rk-esc .rk-av{{width:30px;height:34px;clip-path:polygon(50% 0,100% 18%,100% 70%,50% 100%,0 70%,0 18%);background:#120C3A;display:grid;place-items:center;overflow:hidden}}"
            f"{c} .rk-av img{{width:100%;height:100%;object-fit:cover;display:block}}{c} .rk-av span{{font-weight:900;{branco}}}"
            f"{c} .rk-esc-eu{{--e:#3DDC97;width:42px;height:46px}}{c} .rk-esc-eu .rk-av{{width:36px;height:40px}}"
            f"{c} .rk-nm{{min-width:0;display:flex;flex-direction:column;line-height:1.15}}"
            f"{c} .rk-nm b{{font-size:.86rem;font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;{branco}}}"
            f"{c} .rk-nm small{{font-size:.66rem;font-weight:700;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#7FB2FF !important;-webkit-text-fill-color:#7FB2FF !important}}"
            f"{c} .rk-pts{{display:flex;align-items:center;gap:4px;padding:2px 9px 2px 2px;border-radius:9px;background:rgba(8,8,36,.75);border:1px solid #3A4FB0}}"
            f"{c} .rk-pts img{{width:24px;height:24px;object-fit:contain}}"
            f"{c} .rk-pts b{{font-size:.84rem;font-weight:900;white-space:nowrap;{branco}}}"
            f"{c} .rk-vazio{{text-align:center;padding:16px 10px;border-radius:12px;border:1.5px dashed #3A4FB0;font-size:.82rem;font-weight:700;{lila}}}"
            # telas baixas: topo e título menores para sobrar espaço para a lista
            "@media (max-height:760px){"
            f"{c} .rk-topo{{height:74px}}{c} .rk-tit b{{font-size:1.5rem}}{c} .rk-tit img{{width:22px}}{c} .rk-aba{{height:52px}}{c} .rk-aba img{{height:22px}}}}"
            "@media (max-width:360px){"
            f"{c} .rk-aba b{{font-size:.62rem}}{c} .rk-nm b{{font-size:.8rem}}{c} .rk-pts b{{font-size:.76rem}}{c} .rk-lin{{gap:6px;padding:5px 6px}}}}"
            "</style>")
