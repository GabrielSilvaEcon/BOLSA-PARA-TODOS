"""Tela de perguntas da lição no layout de referência (Quiz): cabeçalho com título e "Pergunta N de T", Caramelo pensativo com balão claro,
alternativas A-D em cartões com bolinha, botão Verificar verde largo e "Sair da lição" em contorno. Módulo puro (HTML/CSS, sem Streamlit).
Só a fase de pergunta usa estas peças; o feedback e a tela final continuam em jornada_player.py."""
from __future__ import annotations

import html
from urllib.parse import quote

import arte_tickerhunters as AT
import jornada_icones as IC

P = 'html body .stApp.stApp.stApp div[class*="st-key-jor_player"]'


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def numero_pergunta(s: dict) -> tuple[int, int]:
    """(pergunta atual, total) da sessão: a atual é feitos+1, limitada ao total."""
    total = int(s.get("total") or 0)
    return min(int(s.get("feitos") or 0) + 1, max(total, 1)), total


def titulo_partes(nome: str) -> tuple[str, str]:
    """Separa a última palavra do título (ela ganha a cor lavanda, como na referência)."""
    partes = str(nome or "Lição").split()
    return (" ".join(partes[:-1]), partes[-1]) if len(partes) > 1 else ("", partes[0])


def html_topo(nome: str, s: dict) -> str:
    """Título e pílula "Pergunta N de T" (o botão Voltar do app fica à esquerda, numa coluna própria)."""
    atual, total = numero_pergunta(s)
    ini, fim = titulo_partes(nome)
    return (f"<span class='jor-tl'></span><div class='jr-top'><div class='jr-nm'><img src='{IC.uri('grafico', '#3DDC97')}' alt=''><span>{_e(ini)} <b>{_e(fim)}</b></span></div>"
            f"<div class='jr-pill'><span>💡</span>Pergunta {atual} de {total}</div></div>")


def html_trilho(pct: float, de: float | None = None) -> str:
    pct = max(0.0, min(1.0, float(pct)))
    anima = de is not None and 0.0 <= float(de) < pct
    barra = (f" class='anima' style='width:{pct * 100:.0f}%;--de:{max(0.0, float(de)) * 100:.0f}%'" if anima else f" style='width:{pct * 100:.0f}%'")
    return f"<div class='jor-trilho jr-trilho'><i{barra}></i></div>"


_ICONE_GRAFICO = ("<svg viewBox='0 0 48 40' aria-hidden='true'><rect x='4' y='24' width='9' height='14' rx='2'/><rect x='18' y='16' width='9' height='22' rx='2'/>"
                  "<rect x='32' y='8' width='9' height='30' rx='2'/><path d='M6 16l14-9 8 5 14-10' fill='none' stroke-width='3' stroke-linecap='round'/></svg>")


def html_pergunta(ex: dict, dica: str) -> str:
    texto = _e(ex["pergunta"])
    if ex["tipo"] == "completar":
        texto = texto.replace("___", "<span class='lacuna'></span>")
    return (f"<div class='jr-ask'><div class='jr-m'><i class='jr-halo'></i><img src='{AT.uri('caramelo_pensativo')}' alt='' aria-hidden='true'><b class='jr-qm'>?</b></div>"
            f"<div class='jr-q'><div class='t'>{texto}</div><div class='s'>{_e(dica)}</div>{_ICONE_GRAFICO}</div></div>")


def fundo_player() -> str:
    """Brilho azul no topo, velas ao fundo à direita, linha de luz e barras de alta no canto inferior direito."""
    velas = "".join(f"<line x1='{x + 5}' y1='{y - 12}' x2='{x + 5}' y2='{y + h + 10}' stroke='#6C8CFF' stroke-width='2' opacity='.18'/>"
                    f"<rect x='{x}' y='{y}' width='10' height='{h}' rx='2' fill='#6C8CFF' opacity='.16'/>" for x, y, h in ((250, 40, 36), (276, 24, 48), (302, 52, 28), (328, 16, 52), (354, 44, 34)))
    barras = "".join(f"<rect x='{x}' y='{y}' width='16' height='{500 - y}' rx='3' fill='url(#b)' opacity='.85'/>" for x, y in ((290, 462), (312, 448), (334, 430), (356, 412), (378, 386)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 500' preserveAspectRatio='xMaxYMax slice'><defs>"
           "<linearGradient id='b' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#6CF0A0'/><stop offset='1' stop-color='#3D5CFF' stop-opacity='.4'/></linearGradient>"
           "<linearGradient id='l' x1='0' y1='1' x2='1' y2='0'><stop offset='0' stop-color='#6C4DFF' stop-opacity='0'/><stop offset='1' stop-color='#7CFFA3' stop-opacity='.7'/></linearGradient>"
           "<radialGradient id='g' cx='.5' cy='0' r='.7'><stop offset='0' stop-color='#3D7CFF' stop-opacity='.3'/><stop offset='1' stop-color='#3D7CFF' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='500' fill='url(#g)'/>" + velas
           + "<path d='M0 500 Q160 470 400 392' fill='none' stroke='url(#l)' stroke-width='3'/>"
           + barras + "<polygon points='398,362 386,376 400,378' fill='#7CFFA3'/></svg>")
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def css() -> str:
    p = P
    return ("<style>"
            # cartão da lição
            f"{p}{{max-width:560px !important;padding:14px 14px 18px !important;border-radius:28px;border:2px solid #5B4BE0;"
            f"background:url(\"{fundo_player()}\") right bottom/cover no-repeat,linear-gradient(180deg,#16114F,#0A0832 90%) !important;"
            "box-shadow:0 0 30px -8px rgba(108,77,255,.75),inset 0 0 40px rgba(60,40,200,.18) !important}"
            # topo
            ".jr-top{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:0}"
            ".jr-nm{display:flex;align-items:center;gap:8px;min-width:0;font-weight:900;font-size:clamp(1.05rem,4.6vw,1.45rem);color:#fff !important;line-height:1.1}"
            ".jr-nm img{width:34px;height:34px;flex:none}.jr-nm span{min-width:0;overflow-wrap:anywhere;color:#fff !important}.jr-nm b{color:#C5B3FF !important}"
            ".jr-pill{flex:none;display:flex;align-items:center;gap:6px;padding:7px 12px;border-radius:16px;border:1.5px solid #6C5CFF;background:rgba(20,14,80,.7);"
            "font-weight:700;font-size:.82rem;color:#E4DCFF !important;white-space:nowrap}"
            ".jr-trilho{margin:0 0 6px}"
            # mascote + balão
            ".jr-ask{display:flex;align-items:center;gap:0;margin:2px 0 8px}"
            ".jr-m{position:relative;flex:0 0 112px;margin:0 -2px 0 -8px}.jr-m img{position:relative;z-index:1;width:112px;height:auto;display:block;filter:drop-shadow(0 8px 10px rgba(0,0,0,.5))}"
            ".jr-halo{position:absolute;left:8px;right:8px;bottom:-2px;height:70%;border-radius:50%;background:radial-gradient(circle,rgba(61,220,151,.55),rgba(61,124,255,.25) 60%,transparent 72%);z-index:0}"
            ".jr-qm{position:absolute;z-index:2;right:-2px;top:-4px;font-size:2.2rem;font-weight:900;color:#5BE9A6 !important;text-shadow:0 0 14px rgba(61,220,151,.9)}"
            ".jr-q{position:relative;flex:1;min-width:0;padding:12px 56px 12px 16px;border-radius:24px;background:linear-gradient(135deg,#FFFFFF,#DCCFFF);box-shadow:0 0 24px -4px rgba(120,150,255,.7)}"
            ".jr-q:before{content:'';position:absolute;left:-9px;top:50%;margin-top:-9px;border:9px solid transparent;border-left:0;border-right-color:#F3EDFF}"
            ".jr-q .t{font-weight:900;font-size:clamp(1.02rem,4.4vw,1.35rem);line-height:1.2;color:#1D1450 !important;overflow-wrap:anywhere}"
            ".jr-q .s{margin-top:4px;font-style:italic;font-size:clamp(.78rem,3.2vw,.95rem);line-height:1.25;color:#4A3E8C !important}"
            ".jr-q svg{position:absolute;right:12px;top:50%;margin-top:-17px;width:38px;height:34px;fill:#7C6AE0;stroke:#7C6AE0;opacity:.85}"
            ".jr-q .lacuna{display:inline-block;min-width:60px;border-bottom:3px solid #5B3FD6;margin:0 4px}"
            # alternativas
            f"{p} div[class*='st-key-jor_r_'] label{{min-height:62px;padding:8px 12px !important;border-radius:22px !important;gap:10px !important;border:2px solid #5B4BE0 !important;"
            "background:linear-gradient(135deg,#1E1360,#140C42) !important;box-shadow:0 0 14px -6px rgba(108,77,255,.8) !important}"
            f"{p} div[class*='st-key-jor_r_'] label:before{{order:-2;flex:0 0 46px !important;height:46px !important;border-radius:13px !important;font-size:1.3rem !important;color:#fff !important;"
            "background:#120B3A !important;border:2px solid #6C5CFF !important}"
            f"{p} div[class*='st-key-jor_r_'] label:after{{content:'';order:-1;flex:0 0 26px;height:26px;border-radius:50%;border:2px solid #4B3E99;background:#0D0A2E;box-sizing:border-box}}"
            f"{p} div[class*='st-key-jor_r_'] label p{{font-size:clamp(1rem,4.2vw,1.25rem) !important;font-weight:600;color:#fff !important}}"
            f"{p} div[class*='st-key-jor_r_'] label:has(input:checked){{border-color:#7CFFA3 !important;background:linear-gradient(135deg,#1B4A66,#16286B) !important;box-shadow:0 0 18px -4px rgba(124,255,163,.7) !important}}"
            f"{p} div[class*='st-key-jor_r_'] label:has(input:checked):before{{background:#3D5CFF !important;border-color:#9FB4FF !important}}"
            f"{p} div[class*='st-key-jor_r_'] label:has(input:checked):after{{border-color:#7CFFA3;background:radial-gradient(circle,#7CFFA3 0 40%,#0D0A2E 46%)}}"
            # Verificar
            f"{p} div[class*='st-key-jor_sv'] button{{position:relative;min-height:62px !important;border-radius:999px !important;border:0 !important;"
            "background:linear-gradient(180deg,#8CFFA0,#2EE06A) !important;box-shadow:0 5px 0 #1B9A45,0 0 22px -4px rgba(61,220,151,.7) !important}"
            f"{p} div[class*='st-key-jor_sv'] button :is(p,span){{color:#08301A !important;-webkit-text-fill-color:#08301A !important;font-weight:900 !important;font-size:1.4rem !important}}"
            f"{p} div[class*='st-key-jor_sv'] button:before,{p} div[class*='st-key-jor_sv'] button:after{{position:absolute;top:50%;transform:translateY(-50%);font-weight:900;font-size:1.6rem;color:rgba(255,255,255,.75);letter-spacing:-3px}}"
            f"{p} div[class*='st-key-jor_sv'] button:before{{content:'»';left:20px}}{p} div[class*='st-key-jor_sv'] button:after{{content:'«';right:20px}}"
            f"{p} div[class*='st-key-jor_sv'] button:disabled{{opacity:.5 !important;filter:saturate(.7)}}"
            # Sair da lição
            f"html body .stApp.stApp.stApp.stApp div[class*='st-key-jor_ss']{{display:block !important}}"
            f"html body .stApp.stApp.stApp.stApp div[class*='st-key-jor_ss'] button{{min-height:48px !important;padding:0 18px !important;border-radius:999px !important;"
            "background:rgba(8,12,44,.6) !important;border:2px solid #3DDC97 !important;box-shadow:none !important;width:auto !important}"
            f"html body .stApp.stApp.stApp.stApp div[class*='st-key-jor_ss'] button :is(p,span,svg){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important;font-size:1rem !important}}"
            "</style>")
