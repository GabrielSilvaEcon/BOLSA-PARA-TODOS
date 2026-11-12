"""Central de missões no layout de referência: banner com mascote e prancheta, quatro cartões de resumo, abas com ícone e cartões de missão
(ícone redondo, barra, selo "+N pts" e ✓ ou seta). Módulo puro: só HTML/CSS e contas de tempo, sem Streamlit, rede ou banco.
As imagens (mascote, prancheta, ícones das missões e o selo de concluída) vêm de arte_missoes.py, recortadas da referência."""
from __future__ import annotations

import html
from datetime import datetime, timedelta
from urllib.parse import quote
from zoneinfo import ZoneInfo

import arte_missoes as AM
import arte_tickerhunters as AT

Q = "html body .stApp.stApp.stApp"
BR = ZoneInfo("America/Sao_Paulo")

# id da missão -> imagem do ícone (diárias e semanais usam os três ícones da referência)
ICONE_MISSAO = {"estudar": "ic_estudar", "meta": "ic_meta", "dourado": "ic_dourado", "dias": "ic_meta", "metas": "ic_meta", "xp": "ic_estudar"}


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _uri_svg(svg: str) -> str:
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


# ------------------------------------------------------------------ tempo até renovar
def _agora(agora: datetime | None) -> datetime:
    a = agora or datetime.now(BR)
    return a.astimezone(BR) if a.tzinfo else a.replace(tzinfo=BR)


def renova_hoje(agora: datetime | None = None) -> str:
    """Tempo até a meia-noite de Brasília, como '12h 34min'."""
    a = _agora(agora)
    fim = (a + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    mins = max(int((fim - a).total_seconds() // 60), 0)
    return f"{mins // 60}h {mins % 60:02d}min"


def renova_semana(agora: datetime | None = None) -> str:
    """Tempo até a próxima segunda-feira 00h (Brasília), como '3d 12h' (ou '5h 10min' no último dia)."""
    a = _agora(agora)
    dias = 7 - a.weekday()
    fim = (a + timedelta(days=dias)).replace(hour=0, minute=0, second=0, microsecond=0)
    mins = max(int((fim - a).total_seconds() // 60), 0)
    d, resto = divmod(mins, 1440)
    return f"{d}d {resto // 60}h" if d else f"{resto // 60}h {resto % 60:02d}min"


# ------------------------------------------------------------------ fundos (ilustração própria de cada cartão)
def fundo_hero() -> str:
    velas = "".join(f"<line x1='{x + 4}' y1='{y - 10}' x2='{x + 4}' y2='{y + h + 8}' stroke='#3DDC97' stroke-width='2' opacity='.22'/>"
                    f"<rect x='{x}' y='{y}' width='8' height='{h}' rx='2' fill='#3DDC97' opacity='.2'/>" for x, y, h in ((210, 80, 24), (230, 62, 34), (250, 92, 20), (270, 52, 40), (290, 72, 26)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 170' preserveAspectRatio='xMidYMid slice'><defs>"
           "<radialGradient id='g' cx='.08' cy='1' r='.6'><stop offset='0' stop-color='#3DDC97' stop-opacity='.4'/><stop offset='1' stop-color='#3DDC97' stop-opacity='0'/></radialGradient>"
           "<radialGradient id='b' cx='.15' cy='.1' r='.7'><stop offset='0' stop-color='#3D7CFF' stop-opacity='.45'/><stop offset='1' stop-color='#3D7CFF' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='170' fill='url(#b)'/><rect width='400' height='170' fill='url(#g)'/>" + velas
           + "<circle cx='190' cy='30' r='2.5' fill='#fff' opacity='.6'/><circle cx='330' cy='24' r='2' fill='#FFD76A' opacity='.7'/></svg>")
    return _uri_svg(svg)


def fundo_missao(ok: bool) -> str:
    cor = "#3DDC97" if ok else "#8B6CFF"
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 120' preserveAspectRatio='xMaxYMid slice'><defs>"
           f"<radialGradient id='g' cx='.95' cy='.5' r='.55'><stop offset='0' stop-color='{cor}' stop-opacity='.3'/><stop offset='1' stop-color='{cor}' stop-opacity='0'/></radialGradient></defs>"
           f"<rect width='400' height='120' fill='url(#g)'/><polyline points='250,100 290,78 320,88 360,50 400,32' fill='none' stroke='{cor}' stroke-width='3' stroke-linecap='round' opacity='.22'/>"
           f"<circle cx='300' cy='24' r='2.5' fill='#fff' opacity='.4'/><circle cx='372' cy='100' r='2' fill='#FFD76A' opacity='.5'/></svg>")
    return _uri_svg(svg)


def fundo_stat() -> str:
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 120 90' preserveAspectRatio='xMaxYMin slice'><defs>"
           "<radialGradient id='g' cx='.9' cy='.1' r='.7'><stop offset='0' stop-color='#8B6CFF' stop-opacity='.35'/><stop offset='1' stop-color='#8B6CFF' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='120' height='90' fill='url(#g)'/><circle cx='104' cy='16' r='2' fill='#fff' opacity='.5'/></svg>")
    return _uri_svg(svg)


# ------------------------------------------------------------------ ícones SVG (traço) dos cartões de resumo e das abas
def _svg(corpo: str, cor: str) -> str:
    return f"<svg viewBox='0 0 32 32' aria-hidden='true' fill='none' stroke='{cor}' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round'>{corpo}</svg>"


ICONES = {
    "estrela": "<path d='M16 3l3.8 8 8.7 1.1-6.4 6 1.7 8.7L16 22.5 8.2 26.8 9.9 18 3.5 12l8.7-1.1z' fill='currentColor'/>",
    "alvo": "<circle cx='16' cy='17' r='11'/><circle cx='16' cy='17' r='6'/><circle cx='16' cy='17' r='1.6' fill='currentColor'/><path d='M17 16l9-9M22 6v5h5'/>",
    "calendario": "<rect x='4' y='7' width='24' height='21' rx='4'/><path d='M4 14h24M10 4v6M22 4v6'/><path d='M10 19h2M15 19h2M20 19h2M10 24h2M15 24h2M20 24h2' stroke-width='3'/>",
    "xp": "<path d='M16 3l11 5v9c0 6-5 10-11 12C10 27 5 23 5 17V8z' fill='currentColor' fill-opacity='.25'/><path d='M11 12l6 8M17 12l-6 8M20 12v8h4' stroke-width='2.2'/>",
    "relogio": "<circle cx='16' cy='16' r='12'/><path d='M16 9v7l5 3'/>",
}


def icone(nome: str, cor: str = "currentColor") -> str:
    return _svg(ICONES[nome], cor)


def icone_uri(nome: str, cor: str) -> str:
    return _uri_svg(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32' fill='none' stroke='{cor}' stroke-width='2.4' stroke-linecap='round' stroke-linejoin='round' "
                    f"color='{cor}'>{ICONES[nome]}</svg>")


# ------------------------------------------------------------------ HTML
def html_hero(regra: str) -> str:
    return (f"<div class='ms-hero'><div class='ms-hm'><img src='{AM.uri('mascote')}' alt='' aria-hidden='true'></div>"
            "<div class='ms-ht'><div class='ms-h'>Central de missões</div>"
            "<div class='ms-s'>Complete desafios, ganhe XP e evolua no TickerHunters!</div></div>"
            f"<div class='ms-hp'><img src='{AM.uri('prancheta')}' alt='' aria-hidden='true'></div>"
            f"<details class='ms-i'><summary aria-label='Como funcionam as missões'>i</summary><div>{_e(regra)}</div></details></div>")


def html_stats(pontos: int, feitas: int, total: int, ofensiva: int, xp_hoje: int) -> str:
    def c(ic: str, cor: str, v, rot: str, cls: str = "") -> str:
        return f"<div class='ms-st {cls}'><div class='v'><span class='ic' style='color:{cor}'>{icone(ic, cor)}</span><b>{_e(v)}</b></div><div class='l'>{_e(rot)}</div></div>"
    return ("<div class='ms-stats'>" + c("estrela", "#A58BFF", pontos, "Pontos na semana", "dest") + c("alvo", "#5BE9A6", f"{feitas}/{total}", "Missões hoje")
            + c("calendario", "#5BE9A6", ofensiva, "Dias seguidos") + c("xp", "#A58BFF", xp_hoje, "XP hoje") + "</div>")


def html_secao(titulo: str, renova: str = "") -> str:
    dir_ = f"<div class='r'>{icone('relogio', '#5BE9A6')}<span>Renova em: <b>{_e(renova)}</b></span></div>" if renova else ""
    return f"<div class='ms-sec'><div class='l'><img src='{AT.uri('trofeu')}' alt='' aria-hidden='true'><b>{_e(titulo)}</b></div>{dir_}</div>"


def icone_missao(mid: str) -> str:
    nome = ICONE_MISSAO.get(mid, "ic_estudar")
    return f"<img src='{AM.uri(nome)}' alt='' aria-hidden='true'>"


def icone_circulo(src: str, cor: str = "#8B6CFF") -> str:
    """Ícone de uma imagem qualquer (ex.: SVG da Jornada) dentro de um círculo com anel, no mesmo tamanho dos ícones das missões."""
    return f"<span class='ms-cir' style='--ac:{cor}'><img src='{src}' alt='' aria-hidden='true'></span>"


def html_missao(titulo: str, texto: str, atual, alvo, ok: bool, pontos: int | None, icone_html: str, selo: str = "", chips: str = "", rodape: str = "",
                seta: bool = True, estado: str = "") -> str:
    """Cartão de missão. `atual`/`alvo` desenham a barra e o '1 de 1'; `ok` mostra o selo ✓; `seta` reserva o espaço do botão › (o botão é do Streamlit).
    `estado` = 'trancado' deixa o cartão mais apagado."""
    try:
        pct = 100.0 if ok else max(0.0, min(1.0, float(atual) / float(alvo))) * 100 if alvo else 0.0
    except (TypeError, ValueError, ZeroDivisionError):
        pct = 0.0
    barra = f"<div class='ms-bar'><i style='width:{pct:.0f}%'></i></div><div class='ms-n'>{_e(atual)} de {_e(alvo)}</div>" if alvo not in (None, "") else ""
    pts = f"<div class='ms-pts'><span>★</span>+{int(pontos)} pts</div>" if pontos is not None else ""
    fim = f"<img class='ms-tick' src='{AM.uri('tick')}' alt='Concluída'>" if ok else ("<span class='ms-seta'></span>" if seta else "")
    selo_h = f"<span class='ms-selo'>{_e(selo)}</span>" if selo else ""
    return (f"<div class='ms-card {'ok' if ok else 'pend'} {estado}' style='--bg:url(\"{fundo_missao(ok)}\")'><div class='ms-ic'>{icone_html}</div>"
            f"<div class='ms-b'><div class='ms-t'>{_e(titulo)}{selo_h}</div><div class='ms-x'>{_e(texto)}</div>{barra}{chips}{rodape}</div>"
            f"<div class='ms-r'>{pts}</div><div class='ms-f'>{fim}</div></div>")


# ------------------------------------------------------------------ CSS
_TAB_IC = {"cal": "calendario", "est": "estrela"}


def css_abas(chave: str, n: int = 3) -> str:
    k = f"{Q} .st-key-ab_{chave}"
    ic = ("cal", "cal", "est")
    regras = "".join(
        f"{k}>*:nth-child({i + 1}) button:before{{content:'';width:20px;height:20px;flex:none;background:var(--i) center/contain no-repeat;"
        f"--i:url(\"{icone_uri(_TAB_IC[ic[i]], '#CFC8EE')}\")}}"
        f"{k}>*:nth-child({i + 1}) button[data-testid$='primary']:before{{--i:url(\"{icone_uri(_TAB_IC[ic[i]], '#08301A')}\")}}"
        for i in range(min(n, 3)))
    return ("<style>"
            f"{k}{{gap:10px !important;margin:6px 0 12px !important}}"
            f"{k} button{{min-height:50px !important;border-radius:999px !important;display:flex !important;align-items:center;justify-content:center;gap:8px !important;"
            "background:linear-gradient(180deg,#1E1560,#140E48) !important;border:1.5px solid #5B4BE0 !important;box-shadow:0 0 14px -6px rgba(108,92,255,.8) !important}"
            f"{k} button p{{font-size:1.05rem !important;font-weight:800 !important;color:#fff !important}}"
            f"{k} button[data-testid$='primary']{{background:linear-gradient(180deg,#8CFFA0,#2EE06A) !important;border:0 !important;box-shadow:0 4px 0 #1B9A45,0 0 18px -4px rgba(61,220,151,.7) !important}}"
            f"{k} button[data-testid$='primary'] p{{color:#08301A !important}}"
            + regras + "</style>")


def css() -> str:
    q = Q
    return ("<style>"
            # banner
            f"{q} .ms-hero{{position:relative;display:flex;align-items:center;gap:6px;min-height:140px;margin:2px 0 12px;padding:8px 10px 8px 0;border-radius:24px;overflow:hidden;"
            f"border:1.5px solid rgba(80,150,255,.5);background:url(\"{fundo_hero()}\") center/cover no-repeat,linear-gradient(120deg,#17327F,#0E2658 50%,#0C1540);box-shadow:0 0 24px -10px rgba(80,140,255,.7)}}"
            ".ms-hm{flex:0 0 36%;max-width:170px;align-self:flex-end;margin:0 -4px 0 0}.ms-hm img{width:100%;height:auto;display:block}"
            ".ms-ht{flex:1;min-width:0}.ms-h{font-weight:900;font-size:clamp(1.3rem,6vw,1.9rem);line-height:1.1;color:#fff !important}"
            ".ms-s{margin-top:6px;font-size:clamp(.74rem,3.1vw,.95rem);line-height:1.3;color:#D6E4F5 !important}"
            ".ms-hp{flex:0 0 22%;max-width:100px}.ms-hp img{width:100%;height:auto;display:block}"
            ".ms-i{position:absolute;top:8px;right:8px;z-index:3}.ms-i summary{list-style:none;cursor:pointer;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;font-style:italic;font-weight:800;color:#fff;"
            "background:rgba(10,8,40,.6);border:1.5px solid rgba(140,160,255,.6)}.ms-i summary::-webkit-details-marker{display:none}"
            ".ms-i[open] div{position:absolute;right:0;top:36px;width:min(78vw,300px);padding:10px 12px;border-radius:12px;background:#1B1442;border:1px solid #3D3182;color:#EDE9FF !important;font-size:.84rem;line-height:1.35}"
            # cartões de resumo
            ".ms-stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:0 0 10px}"
            f"{q} .ms-st{{padding:8px 8px 7px;border-radius:18px;border:1.5px solid rgba(120,110,255,.45);background:url(\"{fundo_stat()}\") right top/cover no-repeat,linear-gradient(160deg,#1B1366,#120C42)}}"
            f"{q} .ms-st.dest{{border-color:#9B7BFF;background:url(\"{fundo_stat()}\") right top/cover no-repeat,linear-gradient(135deg,#5B3FD6,#2E1A8C)}}"
            ".ms-st .v{display:flex;align-items:center;gap:5px}.ms-st .ic svg{width:22px;height:22px;display:block}"
            ".ms-st b{font-size:clamp(1.05rem,5vw,1.5rem);font-weight:900;color:#fff !important;line-height:1}"
            ".ms-st .l{margin-top:5px;font-size:clamp(.5rem,2.3vw,.7rem);font-weight:700;letter-spacing:.03em;text-transform:uppercase;line-height:1.15;color:#CFC8EE !important}"
            # cabeçalho da seção
            ".ms-sec{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:14px 0 8px}"
            ".ms-sec .l{display:flex;align-items:center;gap:8px;min-width:0}.ms-sec .l img{width:34px;height:auto;flex:none}"
            ".ms-sec .l b{font-size:clamp(1.1rem,5vw,1.5rem);font-weight:900;color:#fff !important}"
            ".ms-sec .r{display:flex;align-items:center;gap:5px;font-size:clamp(.7rem,3vw,.9rem);color:#5BE9A6 !important;white-space:nowrap}.ms-sec .r svg{width:18px;height:18px}.ms-sec .r b{color:#5BE9A6 !important}"
            # cartão de missão
            ".ms-wrap{position:relative}"
            f"{q} .ms-card{{position:relative;display:grid;grid-template-columns:58px minmax(0,1fr) auto 44px;align-items:center;column-gap:10px;padding:10px 10px 10px 10px;margin:0 0 10px;border-radius:22px;"
            "border:1.5px solid #5B4BE0;background:var(--bg) right center/cover no-repeat,linear-gradient(135deg,#1A1460,#120C42);box-shadow:0 0 16px -8px rgba(108,92,255,.8)}"
            f"{q} .ms-card.ok{{border-color:rgba(61,220,151,.55)}}{q} .ms-card.trancado{{opacity:.75}}"
            ".ms-ic img,.ms-cir{width:58px;height:58px;display:block;border-radius:50%}"
            ".ms-cir{display:grid;place-items:center;border:2.5px solid var(--ac);background:radial-gradient(circle at 35% 25%,color-mix(in srgb,var(--ac) 35%,#17205A),#0B1233);box-shadow:0 0 12px -3px var(--ac)}"
            ".ms-cir img{width:30px;height:30px;border-radius:0}"
            ".ms-b{min-width:0}.ms-t{font-weight:800;font-size:clamp(1rem,4.2vw,1.2rem);line-height:1.2;color:#fff !important;overflow-wrap:anywhere}"
            ".ms-selo{display:inline-block;margin-left:6px;padding:1px 8px;border-radius:99px;background:rgba(139,108,255,.28);color:#D8CCFF !important;font-size:.62rem;font-weight:800;vertical-align:middle}"
            ".ms-x{margin-top:2px;font-size:clamp(.78rem,3.2vw,.92rem);line-height:1.3;color:#C9D3F0 !important}"
            ".ms-bar{height:7px;margin-top:7px;border-radius:99px;background:rgba(255,255,255,.13);overflow:hidden}.ms-bar i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#4DA3FF,#7C6CFF)}"
            ".ms-card.ok .ms-bar i{background:linear-gradient(90deg,#3DDC97,#7CFFA3)}"
            ".ms-n{margin-top:3px;font-size:.78rem;color:#C9C2F0 !important}"
            ".ms-r{align-self:start}.ms-pts{display:flex;align-items:center;gap:4px;padding:4px 10px;border-radius:99px;border:1.5px solid #6C5CFF;background:rgba(10,8,50,.55);font-weight:800;font-size:.82rem;color:#C5B3FF !important;white-space:nowrap}"
            ".ms-pts span{color:#FFD76A !important}.ms-card.ok .ms-pts{border-color:#3DDC97;color:#7CF0C0 !important}"
            ".ms-f{width:44px;height:44px;display:grid;place-items:center}.ms-tick{width:44px;height:44px;display:block}.ms-seta{width:40px;height:40px;border-radius:12px;border:1.5px solid rgba(255,255,255,.25);background:rgba(10,8,50,.4)}"
            ".ms-chs{margin-top:6px}.ms-ch{display:inline-block;margin:0 6px 0 0;padding:2px 9px;border-radius:99px;background:rgba(61,220,151,.16);color:#7CF0C0 !important;font-size:.74rem;font-weight:800}"
            # botão › sobre a seta do cartão
            f"{q} [class*='st-key-ms_c_'] [data-testid='stElementContainer']:has(button){{position:absolute !important;right:10px;top:50%;transform:translateY(-50%);width:auto !important;z-index:3}}"
            f"{q} [class*='st-key-ms_c_']{{position:relative;margin:0}}"
            f"{q} [class*='st-key-ms_c_'] button{{width:40px !important;min-width:40px !important;height:40px !important;min-height:40px !important;padding:0 !important;border-radius:12px !important;background:rgba(10,8,50,.01) !important;border:0 !important;box-shadow:none !important}}"
            f"{q} [class*='st-key-ms_c_'] button :is(p,span,svg){{color:#fff !important;font-size:26px !important}}"
            "</style>")
