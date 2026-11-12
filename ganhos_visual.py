"""Visual do pop-up 'Você ganhou!' no mesmo padrão do pop-up de compra (moldura dourada, título dourado, mascote, cartões com ilustração própria).
Módulo puro: só gera HTML/CSS. As mensagens vêm de ganhos.py; nada aqui paga ou cria valor."""
from __future__ import annotations

import html
from urllib.parse import quote

import arte_tickerhunters as AT

SPRITE = {"⚡": "xp", "🪙": "tc", "🔥": "fogo", "🏆": "trofeu"}
SUB = {"⚡": "Experiência", "🪙": "Ticker Coins", "🔥": "Sequência de estudo", "🏆": "Nível"}
COR = {"⚡": "#7FB2FF", "🪙": "#FFD66B", "🔥": "#FF9B3D", "🏆": "#C5B3FF"}
_D = "html body [data-testid=\"stDialog\"] [role=\"dialog\"]"


def _fundo(cor: str) -> str:
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 120' preserveAspectRatio='xMaxYMid slice'><defs>"
           f"<radialGradient id='o' cx='.9' cy='.3' r='.6'><stop offset='0' stop-color='{cor}' stop-opacity='.35'/><stop offset='1' stop-color='{cor}' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='120' fill='url(#o)'/>"
           + "".join(f"<rect x='{x}' y='{y}' width='20' height='{120 - y}' rx='4' fill='#8B6CFF' opacity='.12'/>" for x, y in ((270, 80), (296, 62), (322, 44), (348, 26)))
           + "<circle cx='40' cy='24' r='2' fill='#fff' opacity='.5'/><circle cx='370' cy='100' r='2.5' fill='#FFD76A' opacity='.6'/></svg>")
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def html_ganhos(msgs: list[dict]) -> str:
    topo = f"<div class='gv-top'>{AT.img(AT.pose('celebrando'), 92)}</div>"
    cards = []
    for m in msgs:
        ic = m.get("icone", "")
        sp = SPRITE.get(ic, "tc")
        cor = COR.get(ic, "#FFD66B")
        cards.append(f"<div class='gv-c' style='--c:{cor};--bg:url(&quot;{_fundo(cor)}&quot;)'><div class='im'>{AT.img(sp, 52)}</div>"
                     f"<div class='tx'><b>{html.escape(str(m.get('texto', '')))}</b><span>{html.escape(SUB.get(ic, ''))}</span></div></div>")
    return f"<div class='gv-box'>{topo}{''.join(cards)}</div>"


def css() -> str:
    return ("<style>"
            f"{_D}{{background:linear-gradient(160deg,#2A2060,#161240 70%) !important;border:1.5px solid rgba(242,184,75,.6) !important;border-radius:24px !important;padding:4px 6px 8px !important;box-shadow:0 18px 50px rgba(0,0,0,.6),0 0 24px -8px #F2B84B !important}}"
            f"{_D} [data-testid=\"stVerticalBlock\"]{{gap:.55rem !important}}"
            f"{_D} h2,{_D} h2 *{{color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important;font-weight:900 !important;font-size:1.15rem !important;padding:0 !important}}"
            f"{_D} .gv-box{{text-align:center}}"
            f"{_D} .gv-top{{display:flex;justify-content:center;margin:0 0 4px}}.gv-top img{{filter:drop-shadow(0 4px 10px rgba(0,0,0,.5))}}"
            f"{_D} .gv-c{{display:flex;align-items:center;gap:12px;text-align:left;margin:6px 0;padding:8px 14px;border-radius:18px;border:1.5px solid color-mix(in srgb,var(--c) 55%,transparent);"
            "background:var(--bg) right center/cover no-repeat,linear-gradient(160deg,#2A2160,#1A1440 80%);box-shadow:0 0 16px -8px var(--c)}"
            f"{_D} .gv-c .im{{flex:none;width:56px;display:grid;place-items:center}}.gv-c .im img{{filter:drop-shadow(0 3px 6px rgba(0,0,0,.5))}}"
            f"{_D} .gv-c .tx b{{display:block;color:var(--c) !important;-webkit-text-fill-color:var(--c) !important;font-size:1.15rem;font-weight:900;line-height:1.15}}"
            f"{_D} .gv-c .tx span{{color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;font-size:.85rem}}"
            f"{_D} [class*=\"st-key-ganhos_ok\"] button{{min-height:46px !important;border-radius:16px !important;border:1.5px solid rgba(255,214,107,.85) !important;background:linear-gradient(135deg,#F2B84B,#D98E1F) !important;box-shadow:0 4px 0 #7A4D0B !important}}"
            f"{_D} [class*=\"st-key-ganhos_ok\"] button :is(p,span){{color:#2A1A00 !important;-webkit-text-fill-color:#2A1A00 !important;font-weight:900 !important}}"
            "</style>")
