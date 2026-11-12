"""Classificação da Wallet Game no layout de referência: título com troféu, pódio (2º, 1º, 3º), "Sua posição", "Ranking Completo" e o
aviso "Continue evoluindo!". Só HTML/CSS e formatação: nada de Streamlit, rede ou regra de negócio (a ordem e o ranking vêm de ranking_ligas).

Cada item é uma linha de `ranking_ligas.ordenar`: {pos, apelido, ret, pat, sh, eu, ...}."""
from __future__ import annotations

import html

import arte_tickerhunters as AT

Q = "html body .stApp.stApp.stApp"
_E = html.escape
LIMITE = 50            # quantas pessoas a tela lista (o ranking publicado guarda até 100); sua posição aparece mesmo abaixo disso
PALETA = ("#6A2BC9", "#1E56C4", "#E4731F", "#2E9E52", "#C43E5E", "#1F8FA8")
MEDALHA = {1: ("#F5C84B", "#FFE58F"), 2: ("#C9D1E4", "#EEF1FA"), 3: ("#D98B4F", "#F2B488")}
ROTULO_ORDEM = {"Retorno": "Por retorno (%)", "Patrimônio": "Por patrimônio", "Risco": "Por risco (Sharpe)"}
ROTULO_PERIODO = {"Geral": "Ranking Atual", "Mês": "Ranking do mês", "Semana": "Ranking da semana"}


def cor_de(nome: str) -> str:
    """Cor estável do avatar: a mesma pessoa tem sempre a mesma cor."""
    s = sum(ord(c) for c in str(nome or "?"))
    return PALETA[s % len(PALETA)]


def inicial(nome: str) -> str:
    n = str(nome or "").strip()
    return (n[:1] or "?").upper()


def ret_txt(v) -> str:
    """'+24,87%' / '-3,10%' / '0,00%' (duas casas)."""
    if v is None:
        return "—"
    x = float(v) * 100
    if abs(x) < 0.005:
        return "0,00%"
    return f"{'+' if x > 0 else '−'}{abs(x):.2f}".replace(".", ",") + "%"


def _seta(v) -> str:
    if v is None or abs(float(v)) * 100 < 0.005:
        return ""
    return "<s class='up'>▲</s>" if float(v) > 0 else "<s class='dn'>▼</s>"


def _cls(v) -> str:
    return "" if v is None or abs(float(v)) * 100 < 0.005 else ("pos" if float(v) > 0 else "neg")


def moeda(v) -> str:
    if v is None or v != v:
        return "—"
    return "T$ " + f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def ordinal(p) -> str:
    return f"{int(p)}º"


def valor_principal(r: dict, ordem: str) -> tuple[str, str, str]:
    """(texto, classe, seta) do número em destaque: retorno na maioria das ordens; Sharpe quando a ordem é Risco."""
    if ordem == "Risco" and r.get("sh") is not None:
        return f"Sharpe {str(round(r['sh'], 2)).replace('.', ',')}", "", ""
    return ret_txt(r.get("ret")), _cls(r.get("ret")), _seta(r.get("ret"))


def avatar(nome: str, px: int, anel: str | None = None) -> str:
    ring = f"box-shadow:0 0 0 3px {anel},0 0 14px {anel}88;" if anel else ""
    return (f"<span class='ck-av' style='width:{px}px;height:{px}px;font-size:{px * 0.46:.0f}px;background:{cor_de(nome)};{ring}'>"
            f"{_E(inicial(nome))}</span>")


def _louros(cor: str) -> str:
    """Dois ramos de louro (SVG simples) ao redor do número do pódio."""
    folhas = "".join(f"<ellipse cx='{6 + i * 2.2:.1f}' cy='{36 - i * 6.2:.1f}' rx='2.3' ry='5' transform='rotate({-35 + i * 9} {6 + i * 2.2:.1f} {36 - i * 6.2:.1f})'/>"
                     for i in range(6))
    lado = f"<g fill='{cor}' opacity='.95'>{folhas}</g>"
    return (f"<svg class='ck-lou' viewBox='0 0 80 44' aria-hidden='true'>{lado}<g transform='translate(80 0) scale(-1 1)'>{lado}</g></svg>")


def _fundo() -> str:
    """Ilustração de fundo do topo (feixes de luz verdes e roxos, brilho dourado atrás do 1º lugar e estrelinhas), como data URI de SVG."""
    from urllib.parse import quote
    estrelas = "".join(
        f"<path d='M{x} {y - r} L{x + r * .28:.1f} {y - r * .28:.1f} L{x + r} {y} L{x + r * .28:.1f} {y + r * .28:.1f} L{x} {y + r} L{x - r * .28:.1f} {y + r * .28:.1f} L{x - r} {y} L{x - r * .28:.1f} {y - r * .28:.1f}Z' fill='{c}' opacity='{o}'/>"
        for x, y, r, c, o in ((40, 70, 5, "#FFD76A", .8), (96, 150, 3.5, "#fff", .6), (330, 60, 5, "#FFD76A", .8), (366, 140, 3.5, "#fff", .6),
                              (150, 40, 3, "#fff", .5), (260, 120, 3, "#FFD76A", .6), (22, 210, 3, "#fff", .5), (385, 220, 3, "#FFD76A", .6)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 440' preserveAspectRatio='xMidYMin slice'><defs>"
           "<linearGradient id='v' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#2EE59D' stop-opacity='.34'/><stop offset='1' stop-color='#2EE59D' stop-opacity='0'/></linearGradient>"
           "<linearGradient id='r' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#8B6CFF' stop-opacity='.36'/><stop offset='1' stop-color='#8B6CFF' stop-opacity='0'/></linearGradient>"
           "<radialGradient id='o' cx='.5' cy='.42' r='.5'><stop offset='0' stop-color='#FFC94B' stop-opacity='.38'/><stop offset='1' stop-color='#FFC94B' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='440' fill='url(#o)'/>"
           "<polygon points='0,60 0,150 190,440 120,440' fill='url(#v)'/><polygon points='400,60 400,150 210,440 280,440' fill='url(#v)'/>"
           "<polygon points='150,0 250,0 330,440 70,440' fill='url(#r)'/><polygon points='0,0 60,0 160,440 60,440' fill='url(#r)' opacity='.6'/>"
           "<polygon points='340,0 400,0 340,440 240,440' fill='url(#r)' opacity='.6'/>"
           + estrelas + "</svg>")
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def fundo_card(tema: str) -> str:
    """Ilustração própria de fundo para cards (data URI de SVG). Temas: 'ranking' (degraus + linha de alta + moedas) e 'posicao' (explosão verde)."""
    from urllib.parse import quote
    if tema == "posicao":
        raios = "".join(f"<polygon points='330,60 {330 + 260 * __import__('math').cos(a):.0f},{60 + 260 * __import__('math').sin(a):.0f} {330 + 260 * __import__('math').cos(a + .14):.0f},{60 + 260 * __import__('math').sin(a + .14):.0f}' fill='#3DDC97' opacity='.07'/>" for a in [i * .42 for i in range(15)])
        svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 120' preserveAspectRatio='xMaxYMid slice'><defs>"
               "<radialGradient id='g' cx='.82' cy='.4' r='.55'><stop offset='0' stop-color='#3DDC97' stop-opacity='.35'/><stop offset='1' stop-color='#3DDC97' stop-opacity='0'/></radialGradient></defs>"
               "<rect width='400' height='120' fill='url(#g)'/>" + raios +
               "<circle cx='356' cy='30' r='3' fill='#fff' opacity='.6'/><circle cx='300' cy='96' r='2.5' fill='#FFD76A' opacity='.7'/><circle cx='380' cy='88' r='2' fill='#fff' opacity='.5'/></svg>")
    else:
        degraus = "".join(f"<rect x='{x}' y='{y}' width='34' height='{440 - y}' rx='5' fill='#8B6CFF' opacity='.09'/>" for x, y in ((200, 330), (244, 290), (288, 240), (332, 190)))
        moedas = "".join(f"<circle cx='{x}' cy='{y}' r='{r}' fill='none' stroke='#FFD76A' stroke-width='2' opacity='{o}'/><circle cx='{x}' cy='{y}' r='{r * .55:.1f}' fill='#FFD76A' opacity='{o / 3:.2f}'/>" for x, y, r, o in ((60, 420, 18, .22), (360, 130, 14, .25), (110, 350, 10, .18)))
        svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 440' preserveAspectRatio='xMidYMax slice'><defs>"
               "<linearGradient id='l' x1='0' y1='0' x2='1' y2='0'><stop offset='0' stop-color='#2EE59D' stop-opacity='0'/><stop offset='1' stop-color='#2EE59D' stop-opacity='.55'/></linearGradient>"
               "<radialGradient id='o' cx='.85' cy='.12' r='.6'><stop offset='0' stop-color='#8B6CFF' stop-opacity='.35'/><stop offset='1' stop-color='#8B6CFF' stop-opacity='0'/></radialGradient></defs>"
               "<rect width='400' height='440' fill='url(#o)'/>" + degraus +
               "<polyline points='0,400 70,370 130,385 200,320 260,300 320,240 400,170' fill='none' stroke='url(#l)' stroke-width='3' stroke-linecap='round'/>"
               "<circle cx='400' cy='170' r='5' fill='#2EE59D' opacity='.7'/>" + moedas + "</svg>")
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def html_titulo() -> str:
    return (f"<div class='ck-tit'>{AT.img('trofeu', 86)}<div><div class='a'>Classificação</div><div class='b'>Wallet Game</div>"
            "<div class='c'>Mostre que você é o melhor investidor do TickerHunters!</div></div></div>")


def html_podio(itens: list[dict], ordem: str) -> str:
    """Pódio com até 3 pessoas, na ordem visual 2º · 1º · 3º. Posição sem ninguém fica vazia (nada inventado)."""
    por_pos = {r["pos"]: r for r in itens if r.get("pos") in (1, 2, 3)}
    if not por_pos:
        return ""
    cols = []
    for p in (2, 1, 3):
        r = por_pos.get(p)
        if not r:
            cols.append("<div class='ck-p vazio'></div>")
            continue
        c1, c2 = MEDALHA[p]
        txt, cls, seta = valor_principal(r, ordem)
        px = 76 if p == 1 else 60
        cols.append(
            f"<div class='ck-p p{p}' style='--m:{c1};--m2:{c2}'>"
            f"<div class='ck-lw'>{_louros(c1)}<b>{p}</b></div>"
            f"<div class='ck-pil'>{avatar(r.get('apelido', ''), px, c1)}<i class='ck-base'></i></div>"
            f"<div class='ck-cx'><div class='n'>{_E(str(r.get('apelido', '')))}</div><div class='v {cls}'>{_E(txt)} {seta}</div>"
            f"<div class='s'>{_E(moeda(r.get('pat')))}</div></div></div>")
    return "<div class='ck-pod'>" + "".join(cols) + "</div>"


def html_minha_posicao(r: dict, total: int | None, ordem: str) -> str:
    txt, cls, seta = valor_principal(r, ordem)
    de = f"<small>de {int(total)}</small>" if total else ""
    return (f"<div class='ck-eu'><div class='e'><span>Sua posição</span><b>{ordinal(r['pos'])}</b>{de}</div>"
            f"<div class='d'>{avatar(r.get('apelido', ''), 58, '#3DDC97')}<div class='t'><div class='n'>{_E(str(r.get('apelido', '')))}</div>"
            f"<div class='v {cls}'>{_E(txt)} {seta}</div><div class='s'>{_E(moeda(r.get('pat')))}</div></div></div>"
            "</div>")


def html_completo_cab() -> str:
    return f"<div class='ck-rc-cab'>{AT.img('trofeu', 30)}<b>Ranking Completo</b></div>"


def html_linhas(itens: list[dict], ordem: str, rolar: bool = False) -> str:
    """Linhas do Ranking Completo. `rolar`: lista aberta com rolagem própria (a página não cresce com muita gente)."""
    out = []
    for r in itens:
        txt, cls, seta = valor_principal(r, ordem)
        out.append(f"<div class='ck-r{' eu' if r.get('eu') else ''}'><b class='p'>{int(r['pos'])}</b>{avatar(r.get('apelido', ''), 42)}"
                   f"<span class='n'>{_E(str(r.get('apelido', '')))}</span><span class='v {cls}'>{_E(txt)} {seta}</span>"
                   f"<span class='s'>{_E(moeda(r.get('pat')))}</span></div>")
    return f"<div class='ck-rs{' rol' if rolar else ''}'>" + "".join(out) + "</div>"


def css(rotulo_ordem: str) -> str:
    """CSS da tela. `rotulo_ordem` = segunda linha do botão de filtros (vem por variável CSS)."""
    lb = rotulo_ordem.replace("\\", "").replace('"', "")
    s = f"{Q}"
    return ("<style>"
            # topo ilustrado: título, filtros e pódio sobre feixes de luz e brilho
            f'{s} .st-key-ck_hero{{padding:12px 10px 8px !important;margin:0 0 12px;border-radius:24px;border:1px solid rgba(139,108,255,.3);'
            f'background:url("{_fundo()}") center top/100% auto no-repeat,linear-gradient(180deg,#1B1352,#0D0A2B 85%);box-shadow:0 8px 24px rgba(2,6,23,.45)}}'
            # título + botão de filtros
            f'{s} .ck-tit{{display:flex;align-items:center;gap:12px}}{s} .ck-tit img{{flex:none;filter:drop-shadow(0 6px 10px rgba(0,0,0,.5))}}'
            f'{s} .ck-tit .a{{font-size:1.9rem;font-weight:900;color:#fff;line-height:1.05}}{s} .ck-tit .b{{font-size:1.25rem;font-weight:600;color:#CFC8EE;line-height:1.15}}'
            f'{s} .ck-tit .c{{font-size:.8rem;color:#9A8CFF;margin-top:6px;line-height:1.3}}'
            f'{s} .st-key-ck_pill{{--lb:" · {lb}";justify-self:start;max-width:100%;margin-top:14px}}{s} .st-key-ck_rc>*:nth-child(1){{padding-bottom:10px}}{s} .st-key-ck_rc>*:nth-child(3){{padding-bottom:6px}}'
            f'{s} .st-key-ck_pill button{{min-height:30px !important;height:30px !important;width:auto !important;max-width:100%;border-radius:999px !important;padding:0 10px 0 8px !important;'
            "background:linear-gradient(160deg,#2B2266,#1B1442) !important;border:1px solid #4B3C9C !important;box-shadow:none !important;outline:none !important;justify-content:flex-start !important;gap:5px !important}"
            f'{s} .st-key-ck_pill button:is(:hover,:focus,:focus-visible,:active){{border-color:#8B77F0 !important;box-shadow:none !important;outline:none !important}}'
            ""
            f'{s} .st-key-ck_pill button :is(p,span):not([data-testid="stIconMaterial"]){{color:#CBB8FF !important;font-weight:800 !important;font-size:.72rem !important;line-height:1 !important;text-align:left !important;margin:0 !important;white-space:nowrap}}'
            f'{s} .st-key-ck_pill button p::after{{content:var(--lb);color:#CFC8EE;font-weight:600}}'
            f'{s} .st-key-ck_pill button [data-testid="stIconMaterial"]{{color:#B79CFF !important;font-size:16px !important}}'
            # pódio
            f'{s} .ck-pod{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;align-items:end;margin:6px 0 10px}}'
            f'{s} .ck-p{{display:flex;flex-direction:column;align-items:center;min-width:0}}{s} .ck-p.p2,{s} .ck-p.p3{{padding-bottom:0}}'
            f'{s} .ck-lw{{position:relative;width:70px;height:46px;display:grid;place-items:center}}{s} .ck-lw .ck-lou{{position:absolute;inset:0;width:100%;height:100%}}'
            f'{s} .ck-lw b{{position:relative;font-size:1.25rem;font-weight:900;color:#2B1C00;width:30px;height:30px;border-radius:50%;display:grid;place-items:center;'
            "background:radial-gradient(circle at 35% 25%,var(--m2),var(--m));box-shadow:0 2px 6px rgba(0,0,0,.4)}"
            f'{s} .ck-p.p1 .ck-lw{{width:84px;height:54px}}{s} .ck-p.p1 .ck-lw b{{width:38px;height:38px;font-size:1.5rem}}'
            f'{s} .ck-pil{{position:relative;display:grid;place-items:center;padding-bottom:12px;margin-top:2px}}'
            f'{s} .ck-av{{display:grid;place-items:center;border-radius:50%;color:#fff;font-weight:900;flex:none;position:relative;z-index:1}}'
            f'{s} .ck-base{{position:absolute;bottom:2px;left:50%;transform:translateX(-50%);width:128%;height:16px;border-radius:50%;'
            "background:radial-gradient(ellipse at center,var(--m2),var(--m) 60%,transparent 72%);opacity:.85;z-index:0}"
            f'{s} .ck-cx{{width:100%;box-sizing:border-box;text-align:center;padding:10px 6px 10px;border-radius:16px 16px 6px 6px;'
            "background:linear-gradient(180deg,#171244,#0E0B2B);border:1px solid rgba(255,255,255,.1);border-top-color:var(--m)}"
            f'{s} .ck-p.p1 .ck-cx{{padding-top:16px;padding-bottom:16px;border-color:rgba(245,200,75,.55);box-shadow:0 0 22px rgba(245,200,75,.22)}}'
            f'{s} .ck-cx .n{{font-weight:800;color:#fff;font-size:.9rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}'
            f'{s} .ck-cx .v{{font-weight:900;font-size:1.02rem;color:#CFC8EE;margin-top:3px;white-space:nowrap}}{s} .ck-cx .s{{font-size:.72rem;color:#B9B0E6;margin-top:2px}}'
            f'{s} .v.pos{{color:#3DDC97 !important}}{s} .v.neg{{color:#FF6B8A !important}}{s} .v s{{text-decoration:none;font-size:.7em}}'
            # sua posição
            f'{s} .st-key-ck_eu{{position:relative;margin:0 0 12px}}'
            f'{s} .ck-eu{{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:22px;border:2px solid #3DDC97;'
            f'background:url("{fundo_card("posicao")}") right center/cover no-repeat,linear-gradient(110deg,#15493A,#10302F 60%,#0E2430);box-shadow:0 0 24px rgba(61,220,151,.28)}}'
            f'{s} .ck-eu .e{{flex:0 0 26%;min-width:84px;border-right:1px solid rgba(255,255,255,.14);padding-right:8px}}'
            f'{s} .ck-eu .e span{{display:block;color:#E8F7EF;font-size:.84rem;font-weight:700}}{s} .ck-eu .e b{{font-size:2.5rem;font-weight:900;color:#5BE9A6;line-height:1.05}}'
            f'{s} .ck-eu .e small{{margin-left:5px;color:#E8F7EF;font-size:.9rem}}'
            f'{s} .ck-eu .d{{display:flex;align-items:center;gap:12px;min-width:0;flex:1}}{s} .ck-eu .t{{min-width:0}}'
            f'{s} .ck-eu .n{{color:#fff;font-weight:800;font-size:1.1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}'
            f'{s} .ck-eu .v{{font-weight:900;font-size:1.2rem;color:#CFC8EE}}{s} .ck-eu .s{{color:#CDEBDD;font-size:.8rem}}'
            # ranking completo
            f'{s} .st-key-ck_rc{{display:grid !important;grid-template-columns:minmax(0,1fr) auto;align-items:center;column-gap:8px;row-gap:10px;margin:0 0 12px;'
            f'padding:12px 12px 16px !important;border-radius:22px;border:1px solid #4B3F9A;background:url("{fundo_card("ranking")}") center bottom/cover no-repeat,linear-gradient(170deg,#1A1450,#0F0B2E);box-shadow:0 6px 18px rgba(2,6,23,.4)}}'
            f'{s} .st-key-ck_rc>*:nth-child(1){{grid-column:1;grid-row:1}}{s} .st-key-ck_rc>*:nth-child(2){{grid-column:2;grid-row:1}}'
            f'{s} .st-key-ck_rc>*:nth-child(3){{grid-column:1 / -1;grid-row:2}}{s} .st-key-ck_rc>*:nth-child(4){{grid-column:1 / -1;grid-row:3}}'
            f'{s} .ck-rc-cab{{display:flex;align-items:center;gap:10px}}{s} .ck-rc-cab b{{font-size:1.35rem;font-weight:800;color:#fff}}'
            f'{s} .st-key-ck_rc_ver button{{background:transparent !important;border:0 !important;box-shadow:none !important;min-height:36px !important;padding:0 4px !important}}'
            f'{s} .st-key-ck_rc_ver button :is(p,span){{color:#B79CFF !important;font-weight:800 !important;font-size:.95rem !important;white-space:nowrap}}'
            f'{s} .ck-rs{{display:flex;flex-direction:column;border-top:1px solid rgba(255,255,255,.1);margin-top:4px;padding-bottom:6px}}'
            f'{s} .ck-r{{display:grid;grid-template-columns:30px 44px minmax(0,1fr) auto auto;align-items:center;gap:10px;padding:12px 2px;border-bottom:1px solid rgba(255,255,255,.08)}}'
            f'{s} .ck-rs.rol{{max-height:min(58vh,440px);overflow-y:auto;overscroll-behavior:contain;padding-right:4px}}{s} .ck-r:last-child{{border-bottom:0}}{s} .ck-r.eu{{background:rgba(61,220,151,.08);border-radius:12px}}'
            f'{s} .ck-r .p{{font-size:1.35rem;font-weight:800;color:#fff;text-align:center}}{s} .ck-r .n{{color:#fff;font-weight:600;font-size:1rem;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}'
            f'{s} .ck-r .v{{font-weight:800;color:#CFC8EE;white-space:nowrap}}{s} .ck-r .s{{color:#CFC8EE;font-size:.92rem;white-space:nowrap;text-align:right;min-width:92px}}'
            f"@media (max-width:560px){{{s} .ck-r{{grid-template-columns:26px 40px minmax(0,1fr) auto;row-gap:0}}{s} .ck-r .s{{grid-column:4;grid-row:2;font-size:.74rem;min-width:0}}"
            f"{s} .ck-r .v{{grid-column:4;grid-row:1}}{s} .ck-r .p{{grid-row:1 / span 2}}{s} .ck-r .ck-av{{grid-row:1 / span 2}}{s} .ck-r .n{{grid-row:1 / span 2}}"
            f"{s} .ck-eu .e{{flex-basis:30%}}}}"
            "</style>")
