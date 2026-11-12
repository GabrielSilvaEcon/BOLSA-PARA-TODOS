"""Aba Aprender no layout de referência: hero "Sua Jornada de Investidor" e trilha vertical de módulos (concluído, em andamento, a começar).
Módulo puro: só HTML/CSS e regras de apresentação (sem Streamlit, rede ou banco). O estado de cada módulo vem de jornada.mapa().
Nada é trancado (regra da Jornada): módulos futuros aparecem como "A começar" com a contagem de lições, nunca com bloqueio inventado.
Cada card tem ilustração própria de fundo (SVG em data URI)."""
from __future__ import annotations

import html
from urllib.parse import quote

import arte_tickerhunters as AT
import jornada_icones as IC

Q = "html body .stApp.stApp.stApp"
VERDE, OURO, ROXO = "#3DDC97", "#F2B84B", "#8B6CFF"
ESTADOS = ("feito", "atual", "futuro")


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


def _uri_svg(svg: str) -> str:
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def estado_modulo(u: dict, primeiro_aberto: str | None) -> str:
    """feito = todas as lições concluídas; atual = primeiro módulo ainda não concluído; futuro = os demais."""
    if u.get("completa"):
        return "feito"
    return "atual" if u["id"] == primeiro_aberto else "futuro"


def primeiro_aberto(mapa: list[dict]) -> str | None:
    return next((u["id"] for u in mapa if not u.get("completa")), None)


def progresso(mapa: list[dict]) -> tuple[int, int]:
    return sum(1 for u in mapa if u.get("completa")), len(mapa)


def proxima_licao_do_modulo(u: dict) -> str | None:
    """Lição a abrir ao tocar em Continuar: a 'proxima' (ou a primeira não concluída) do módulo."""
    for estado in ("proxima", "livre"):
        for l in u["licoes"]:
            if l["estado"] == estado:
                return l["id"]
    return u["licoes"][0]["id"] if u["licoes"] else None


def rotulo_botao(est: str) -> str:
    return {"feito": "Revisar", "atual": "Continuar", "futuro": "Começar"}[est]


# ------------------------------------------------------------------ ilustrações de fundo
def fundo_hero() -> str:
    """Prédios e candles verdes com seta de alta à esquerda e brilho dourado à direita."""
    barras = "".join(f"<rect x='{x}' y='{y}' width='16' height='{240 - y}' rx='3' fill='#2EE59D' opacity='{o}'/>"
                     for x, y, o in ((14, 150, .12), (40, 118, .16), (66, 168, .10), (92, 90, .14), (118, 130, .10), (144, 60, .16)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 240' preserveAspectRatio='xMidYMid slice'><defs>"
           "<radialGradient id='d' cx='.88' cy='.4' r='.5'><stop offset='0' stop-color='#FFC94B' stop-opacity='.32'/><stop offset='1' stop-color='#FFC94B' stop-opacity='0'/></radialGradient>"
           "<radialGradient id='v' cx='.1' cy='.6' r='.6'><stop offset='0' stop-color='#2EE59D' stop-opacity='.28'/><stop offset='1' stop-color='#2EE59D' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='240' fill='url(#v)'/><rect width='400' height='240' fill='url(#d)'/>" + barras +
           "<polyline points='10,200 70,160 110,175 170,110 220,90' fill='none' stroke='#2EE59D' stroke-width='4' stroke-linecap='round' opacity='.35'/>"
           "<polygon points='220,70 246,92 218,100' fill='#2EE59D' opacity='.4'/>"
           "<circle cx='330' cy='36' r='3' fill='#FFD76A' opacity='.7'/><circle cx='372' cy='120' r='2.5' fill='#fff' opacity='.5'/><circle cx='260' cy='28' r='2' fill='#fff' opacity='.5'/></svg>")
    return _uri_svg(svg)


def fundo_modulo(est: str) -> str:
    """Fundo do card de cada módulo: feito (verde com check), atual (dourado com brilhos) e futuro (roxo com velas)."""
    if est == "feito":
        corpo = ("<defs><radialGradient id='g' cx='.9' cy='.5' r='.6'><stop offset='0' stop-color='#3DDC97' stop-opacity='.3'/><stop offset='1' stop-color='#3DDC97' stop-opacity='0'/></radialGradient></defs>"
                 "<rect width='400' height='120' fill='url(#g)'/><circle cx='352' cy='60' r='46' fill='none' stroke='#3DDC97' stroke-width='3' opacity='.12'/>"
                 "<path d='M330 62l16 16 30-34' fill='none' stroke='#3DDC97' stroke-width='6' stroke-linecap='round' stroke-linejoin='round' opacity='.18'/>")
    elif est == "atual":
        estrelas = "".join(f"<path d='M{x} {y - r}L{x + r * .3} {y - r * .3}L{x + r} {y}L{x + r * .3} {y + r * .3}L{x} {y + r}L{x - r * .3} {y + r * .3}L{x - r} {y}L{x - r * .3} {y - r * .3}Z' fill='#FFE08A' opacity='{o}'/>"
                           for x, y, r, o in ((300, 22, 6, .7), (372, 36, 4, .6), (250, 96, 3.5, .5), (384, 98, 5, .6)))
        corpo = ("<defs><radialGradient id='g' cx='.85' cy='.5' r='.65'><stop offset='0' stop-color='#E7F63A' stop-opacity='.28'/><stop offset='1' stop-color='#E7F63A' stop-opacity='0'/></radialGradient></defs>"
                 "<rect width='400' height='120' fill='url(#g)'/>" + estrelas
                 + "<polyline points='230,100 270,80 300,90 340,52 390,30' fill='none' stroke='#E7F63A' stroke-width='3' stroke-linecap='round' opacity='.22'/>")
    else:
        velas = "".join(f"<line x1='{x + 5}' y1='{y - 14}' x2='{x + 5}' y2='{y + h + 12}' stroke='#8B6CFF' stroke-width='2' opacity='.18'/>"
                        f"<rect x='{x}' y='{y}' width='10' height='{h}' rx='2' fill='#8B6CFF' opacity='.16'/>"
                        for x, y, h in ((290, 52, 30), (316, 36, 40), (342, 62, 24), (368, 30, 44)))
        corpo = ("<defs><radialGradient id='g' cx='.9' cy='.4' r='.6'><stop offset='0' stop-color='#8B6CFF' stop-opacity='.25'/><stop offset='1' stop-color='#8B6CFF' stop-opacity='0'/></radialGradient></defs>"
                 "<rect width='400' height='120' fill='url(#g)'/>" + velas)
    return _uri_svg(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 120' preserveAspectRatio='xMaxYMid slice'>{corpo}</svg>")


def fundo_card(tema: str) -> str:
    """Fundos de apoio para os demais cards da tela: 'wallet' (controle e brilhos), 'nivel' (raio e degraus), 'erros' (setas de revisão), 'atalho' (pontos)."""
    if tema == "wallet":
        corpo = ("<defs><radialGradient id='g' cx='.15' cy='.5' r='.6'><stop offset='0' stop-color='#FFBE3C' stop-opacity='.3'/><stop offset='1' stop-color='#FFBE3C' stop-opacity='0'/></radialGradient></defs>"
                 "<rect width='400' height='160' fill='url(#g)'/><circle cx='360' cy='36' r='22' fill='none' stroke='#C5B3FF' stroke-width='3' opacity='.2'/>"
                 "<circle cx='330' cy='120' r='14' fill='none' stroke='#FFD76A' stroke-width='3' opacity='.22'/><circle cx='376' cy='100' r='3' fill='#fff' opacity='.5'/>")
    elif tema == "nivel":
        corpo = ("<defs><radialGradient id='g' cx='.1' cy='.2' r='.7'><stop offset='0' stop-color='#F2B84B' stop-opacity='.22'/><stop offset='1' stop-color='#F2B84B' stop-opacity='0'/></radialGradient></defs>"
                 "<rect width='400' height='160' fill='url(#g)'/>"
                 + "".join(f"<rect x='{x}' y='{y}' width='24' height='{160 - y}' rx='4' fill='#3DDC97' opacity='.09'/>" for x, y in ((250, 120), (282, 96), (314, 70), (346, 44)))
                 + "<path d='M372 18l-14 24h10l-6 20 18-28h-11z' fill='#F2B84B' opacity='.28'/>")
    elif tema == "erros":
        corpo = ("<defs><radialGradient id='g' cx='.9' cy='.5' r='.6'><stop offset='0' stop-color='#FF6B8A' stop-opacity='.3'/><stop offset='1' stop-color='#FF6B8A' stop-opacity='0'/></radialGradient></defs>"
                 "<rect width='400' height='80' fill='url(#g)'/><path d='M330 40a22 22 0 1 1 8 17' fill='none' stroke='#FF6B8A' stroke-width='4' stroke-linecap='round' opacity='.3'/>"
                 "<polygon points='326,30 346,34 332,50' fill='#FF6B8A' opacity='.3'/>")
    else:
        corpo = ("<defs><radialGradient id='g' cx='.85' cy='.2' r='.7'><stop offset='0' stop-color='#8B6CFF' stop-opacity='.28'/><stop offset='1' stop-color='#8B6CFF' stop-opacity='0'/></radialGradient></defs>"
                 "<rect width='200' height='120' fill='url(#g)'/><circle cx='168' cy='28' r='3' fill='#fff' opacity='.4'/><circle cx='140' cy='84' r='2' fill='#FFD76A' opacity='.5'/>")
    alt = {"wallet": 160, "nivel": 160, "erros": 80}.get(tema, 120)
    larg = 200 if tema == "atalho" else 400
    return _uri_svg(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {larg} {alt}' preserveAspectRatio='xMaxYMid slice'>{corpo}</svg>")


# ------------------------------------------------------------------ HTML
def html_hero(mapa: list[dict]) -> str:
    feitos, total = progresso(mapa)
    pct = (feitos / total * 100) if total else 0
    return (f"<div class='jt-hero'><div class='jt-hm'><img src='{AT.uri('caramelo_animado')}' alt='' aria-hidden='true'></div>"
            f"<div class='jt-ht'><span class='jt-tag'>Sua Jornada de Investidor</span>"
            f"<div class='jt-h'>Construindo sua <b>liberdade financeira!</b></div>"
            "<div class='jt-s'>Aprenda, evolua e faça seu patrimônio crescer com o TickerHunters.</div>"
            f"<div class='jt-pg'><div class='jt-bar'><i style='width:{pct:.0f}%'></i></div><span>{feitos} / {total}</span></div></div>"
            f"<div class='jt-bau'><img src='{AT.uri('bau_lendario')}' alt='' aria-hidden='true'></div></div>")


def html_modulo(n: int, u: dict, est: str) -> str:
    cor = {"feito": VERDE, "atual": "#E7F63A", "futuro": ROXO}[est]
    ic = IC.uri(u.get("svg", "estrela"), "#FFFFFF" if est != "feito" else "#3DDC97")
    badge = {"feito": "<i class='jt-bd ok'>✓</i>", "atual": "<i class='jt-bd go'>▶</i>", "futuro": ""}[est]
    feitas, total = u["feitas"], u["total"]
    if est == "feito":
        st = f"<div class='jt-st ok'><i>✓</i>Concluído · {feitas}/{total} lições</div>"
    elif est == "atual":
        pct = (feitas / total * 100) if total else 0
        st = (f"<div class='jt-st go'><i>▶</i>Em andamento · {feitas}/{total} lições</div>"
              f"<div class='jt-mb'><i style='width:{pct:.0f}%'></i></div>")
    else:
        st = f"<div class='jt-st'>{total} lições · livre para estudar</div>"
    return (f"<div class='jt-row {est}' style='--ac:{cor};--bg:url(\"{fundo_modulo(est)}\")'>"
            f"<div class='jt-no'><span><img src='{ic}' alt=''></span>{badge}</div>"
            f"<div class='jt-c'><div class='jt-t'>{n}. {_e(u['titulo'])}</div><div class='jt-d'>{_e(u['descricao'])}</div>{st}</div></div>")


def html_fala(texto: str = "Você está indo muito bem!") -> str:
    return (f"<div class='jt-fala'><div class='jt-bal'>{_e(texto)}<span>🐾</span></div>"
            f"<img src='{AT.uri('caramelo_celebrando')}' alt='' aria-hidden='true'></div>")


def css() -> str:
    q = Q
    return ("<style>"
            # hero
            f"{q} .st-key-jt_hero{{max-width:560px;margin:4px auto 16px;padding:0 !important;border-radius:26px;overflow:hidden;border:1.5px solid rgba(61,220,151,.4);"
            f"background:url(\"{fundo_hero()}\") center/cover no-repeat,linear-gradient(160deg,#0F2A3A,#0B1233 80%);box-shadow:0 0 26px -12px rgba(46,229,157,.6)}}"
            ".jt-hero{display:flex;align-items:center;gap:6px;padding:10px 10px 12px 0;position:relative}"
            ".jt-hm{flex:0 0 31%;max-width:150px;align-self:flex-end}.jt-hm img{width:100%;height:auto;display:block;filter:drop-shadow(0 8px 10px rgba(0,0,0,.5))}"
            ".jt-ht{flex:1;min-width:0}"
            ".jt-tag{display:inline-block;padding:4px 10px;border-radius:99px;font-weight:700;font-size:.72rem;color:#CFF7E4 !important;background:rgba(61,220,151,.14);border:1px solid rgba(61,220,151,.5)}"
            ".jt-h{margin-top:6px;font-size:clamp(1.15rem,5.4vw,1.7rem);font-weight:800;line-height:1.1;color:#fff !important}.jt-h b{color:#7CFFA3 !important;display:block}"
            ".jt-s{margin-top:6px;font-size:clamp(.74rem,3vw,.92rem);line-height:1.3;color:#D6E4F5 !important}"
            ".jt-pg{display:flex;align-items:center;gap:8px;margin-top:10px}.jt-pg span{font-weight:800;font-size:.82rem;color:#fff !important;white-space:nowrap}"
            ".jt-bar{flex:1;height:10px;border-radius:99px;background:rgba(255,255,255,.12);overflow:hidden}"
            ".jt-bar i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#3DDC97,#7CFFA3)}"
            ".jt-bau{flex:0 0 22%;max-width:96px}.jt-bau img{width:100%;height:auto;display:block;filter:drop-shadow(0 0 14px rgba(255,201,75,.65))}"
            # trilha
            f"{q} .st-key-jt_trilha{{max-width:560px;margin:0 auto 8px;position:relative;gap:12px !important}}"
            f"{q} .st-key-jt_trilha:before{{content:'';position:absolute;left:41px;top:20px;bottom:20px;border-left:3px dotted rgba(61,220,151,.45)}}"
            f"{q} [class*='st-key-jt_m_']{{position:relative;margin:0}}"
            ".jt-row{position:relative;display:flex;align-items:center;gap:12px;min-height:96px;padding-right:118px}"
            ".jt-no{position:relative;flex:0 0 66px;z-index:2}"
            ".jt-no span{display:grid;place-items:center;width:66px;height:66px;border-radius:50%;border:3px solid var(--ac);background:radial-gradient(circle at 35% 25%,color-mix(in srgb,var(--ac) 38%,#17205A),#0B1233);box-shadow:0 0 16px -2px var(--ac)}"
            ".jt-no img{width:34px;height:34px;display:block}"
            ".jt-bd{position:absolute;top:-4px;right:-6px;width:24px;height:24px;border-radius:50%;display:grid;place-items:center;font-style:normal;font-size:.7rem;font-weight:900;color:#06281A !important;border:2px solid #0B1233}"
            ".jt-bd.ok{background:#3DDC97}.jt-bd.go{background:#F2B84B}"
            ".jt-c{flex:1;min-width:0;align-self:stretch;display:flex;flex-direction:column;justify-content:center;gap:2px;padding:10px 12px;border-radius:20px;"
            "border:1.5px solid color-mix(in srgb,var(--ac) 55%,transparent);background:var(--bg) right center/cover no-repeat,linear-gradient(135deg,color-mix(in srgb,var(--ac) 14%,#10173E),#0D1235 85%);margin-right:-118px;padding-right:122px}"
            ".jt-row.atual .jt-c{border-color:#E7F63A;box-shadow:0 0 18px -4px rgba(231,246,58,.55)}"
            ".jt-t{font-weight:800;font-size:clamp(.98rem,4vw,1.15rem);color:#fff !important;line-height:1.2}"
            ".jt-d{font-size:clamp(.78rem,3.2vw,.9rem);line-height:1.25;color:#C9D3F0 !important}"
            ".jt-st{display:flex;align-items:center;gap:6px;margin-top:4px;font-size:.8rem;font-weight:700;color:#B9B0E6 !important}"
            ".jt-st i{font-style:normal;display:grid;place-items:center;width:18px;height:18px;border-radius:50%;font-size:.6rem;color:#06281A !important}"
            ".jt-st.ok{color:#5BE9A6 !important}.jt-st.ok i{background:#3DDC97}.jt-st.go{color:#F2B84B !important}.jt-st.go i{background:#F2B84B}"
            ".jt-mb{height:7px;margin-top:5px;border-radius:99px;background:rgba(255,255,255,.12);overflow:hidden}.jt-mb i{display:block;height:100%;border-radius:99px;background:#E7F63A}"
            # botão do módulo (sobre o card, à direita)
            f"{q} [class*='st-key-jt_m_'] [data-testid='stElementContainer']:has(button){{position:absolute !important;right:12px;top:50%;transform:translateY(-50%);width:auto !important;z-index:3}}"
            f"{q} [class*='st-key-jt_m_'] button{{min-height:38px !important;padding:0 14px !important;border-radius:999px !important;background:rgba(10,8,40,.55) !important;"
            "border:1.5px solid #3DDC97 !important;box-shadow:none !important}"
            f"{q} [class*='st-key-jt_m_'] button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important;font-size:.86rem !important}}"
            f"{q} [class*='st-key-jt_m_atual_'] button{{background:linear-gradient(180deg,#C6F94A,#8BE02F) !important;border:0 !important;box-shadow:0 4px 0 #4E8A12 !important}}"
            f"{q} [class*='st-key-jt_m_atual_'] button :is(p,span){{color:#10240A !important;-webkit-text-fill-color:#10240A !important}}"
            f"{q} [class*='st-key-jt_m_futuro_'] button{{border-color:#8B6CFF !important}}"
            # mascote com balão
            ".jt-fala{position:relative;display:flex;align-items:flex-end;gap:4px;max-width:560px;margin:6px auto 4px}"
            ".jt-fala img{flex:0 0 34%;max-width:150px;height:auto;filter:drop-shadow(0 8px 10px rgba(0,0,0,.5))}"
            ".jt-bal{position:relative;align-self:flex-start;max-width:52%;padding:10px 14px;border-radius:18px;border:2px solid #7CFFA3;background:rgba(8,14,40,.85);"
            "font-weight:800;font-size:clamp(.95rem,4vw,1.15rem);line-height:1.15;color:#fff !important}"
            ".jt-bal span{display:block;margin-top:4px}"
            # cards de apoio
            f"{q} .st-key-jor_wg{{background:url(\"{fundo_card('wallet')}\") right center/cover no-repeat,radial-gradient(circle at 12% 40%,rgba(255,190,60,.25),transparent 50%),linear-gradient(135deg,#3A1C8F,#2A1470 70%) !important}}"
            f"{q} .nv{{background:url(\"{fundo_card('nivel')}\") right center/cover no-repeat,linear-gradient(160deg,rgba(60,110,255,.22),rgba(16,24,63,.9) 70%) !important}}"
            f"{q} .st-key-jor_revisar button{{background:url(\"{fundo_card('erros')}\") right center/cover no-repeat,linear-gradient(135deg,rgba(255,107,138,.28),#17154F 80%) !important}}"
            f"{q} [class*='st-key-jor_mais_'] button{{background:url(\"{fundo_card('atalho')}\") right top/cover no-repeat,linear-gradient(135deg,color-mix(in srgb,var(--ac) 18%,#1B1B5E),#17154F 75%) !important}}"
            "</style>")
