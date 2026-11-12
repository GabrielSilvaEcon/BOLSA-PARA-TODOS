"""Visual da Loja Ticker / Economia Ticker, copiado da referência enviada pelo Gabriel (cabeçalho, saldo, abas, baú em destaque, Outros itens).
Módulo puro: só gera HTML/CSS (sem Streamlit, sem banco). Valores e regras vêm de quem chama; aqui nada é inventado."""
from __future__ import annotations

import html
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

import arte_loja as AL

Q = "html body .stApp.stApp.stApp"
_BRT = timezone(timedelta(hours=-3))


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def renova_hoje(agora: datetime | None = None) -> str:
    """Tempo até a meia-noite de Brasília (quando o baú diário e o limite diário renovam), ex.: '12h 34min'."""
    a = (agora or datetime.now(timezone.utc)).astimezone(_BRT)
    fim = (a + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    m = max(0, int((fim - a).total_seconds() // 60))
    return f"{m // 60}h {m % 60:02d}min"


def _fundo(svg: str) -> str:
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def fundo_cartao(tema: str = "saldo") -> str:
    """Ilustração própria de fundo: gráfico de barras em alta + brilho (saldo/baú) ou degraus suaves (itens)."""
    barras = "".join(f"<rect x='{x}' y='{y}' width='26' height='{200 - y}' rx='4' fill='#6C8CFF' opacity='.13'/>" for x, y in ((250, 140), (282, 110), (314, 80), (346, 40)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 200' preserveAspectRatio='xMaxYMax slice'><defs>"
           "<radialGradient id='o' cx='.85' cy='.15' r='.65'><stop offset='0' stop-color='#8B6CFF' stop-opacity='.35'/><stop offset='1' stop-color='#8B6CFF' stop-opacity='0'/></radialGradient>"
           "<radialGradient id='b' cx='.12' cy='.9' r='.5'><stop offset='0' stop-color='#2BA7FF' stop-opacity='.22'/><stop offset='1' stop-color='#2BA7FF' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='200' fill='url(#o)'/><rect width='400' height='200' fill='url(#b)'/>" + barras +
           "<polyline points='230,170 290,150 330,120 400,60' fill='none' stroke='#2EE59D' stroke-width='2' opacity='.35' stroke-linecap='round'/>"
           "<circle cx='60' cy='30' r='2' fill='#fff' opacity='.5'/><circle cx='370' cy='170' r='2.5' fill='#FFD76A' opacity='.6'/></svg>")
    return _fundo(svg)


def _m(nome: str) -> str:
    return f'url("{AL.uri("m_" + nome)}")'


def icone(nome: str, cor: str, tam: int = 22) -> str:
    return f"<i class='lv-ic' style='--m:{_m(nome)};--c:{_e(cor)};width:{tam}px;height:{tam}px'></i>"


def img(nome: str, alt: str = "") -> str:
    u = AL.uri(nome)
    return f"<img src='{u}' alt='{_e(alt)}' loading='lazy'>" if u else ""


def html_titulo() -> str:
    return (f"<div class='lv-tit'>{icone('cart', '#2EE59D', 40)}<div><div class='a'>Loja <span>Ticker</span></div>"
            "<div class='b'>Troque seus Ticker Coins por itens incríveis!</div></div></div>")


def html_saldo(saldo) -> str:
    v = "—" if saldo is None else f"{int(saldo):,}".replace(",", ".")
    return (f"<div class='lv-sd'><div class='lv-sd-a'>{img('moedas', 'Pilha de moedas')}</div><div class='lv-sd-l'></div>"
            f"<div class='lv-sd-v'><div class='n'>{img('tc')}<b>{_e(v)}</b></div><div class='t'>Ticker Coins disponíveis</div></div></div>")


def html_secao(titulo: str, ic: str, cor: str, pill: str = "") -> str:
    p = f"<span class='lv-pill'>{icone('relogio', '#2EE59D', 18)}<span>Renova em: <b>{_e(pill)}</b></span></span>" if pill else ""
    return f"<div class='lv-sec'><div class='l'>{icone(ic, cor, 30)}<span>{_e(titulo)}</span></div>{p}</div>"


def html_bau(disponivel: int) -> str:
    return (f"<div class='lv-bau'><div class='lv-bau-a'>{img('bau', 'Baú diário')}</div>"
            f"<div class='lv-bau-t'><div class='n'>Baú diário</div><div class='d'>Receba uma recompensa surpresa!</div>"
            f"<div class='p'>{img('tc')}<b>Grátis hoje</b></div></div>"
            f"<span class='lv-disp'>Disponível: {int(disponivel)}</span></div>")


def html_item(previa_html: str, nome: str, preco: int, descricao: str = "") -> str:
    d = f"<div class='d'>{_e(descricao)}</div>" if descricao else ""
    return (f"<div class='lv-it'><div class='top'><div class='pv'>{previa_html}</div><div class='tx'><div class='n'>{_e(nome)}</div>{d}</div></div>"
            f"<div class='pr'>{img('tc')}<b>{int(preco)}</b></div></div>")


def css_abas(chave: str, n: int = 3) -> str:
    k = f"{Q} .st-key-ab_{chave}"
    ic = ("estrela", "loja", "extrato")
    regras = "".join(
        f"{k}>*:nth-child({i + 1}) button:before{{content:'';width:22px;height:22px;flex:none;background:#B89CFF;-webkit-mask:{_m(ic[i])} center/contain no-repeat;mask:{_m(ic[i])} center/contain no-repeat}}"
        f"{k}>*:nth-child({i + 1}) button[data-testid$='primary']:before{{background:#06361F}}" for i in range(min(n, 3)))
    return ("<style>"
            f"{k}{{gap:10px !important;margin:6px 0 10px !important}}"
            f"{k} button{{min-height:50px !important;border-radius:999px !important;display:flex !important;align-items:center;justify-content:center;gap:8px !important;"
            "background:linear-gradient(180deg,rgba(40,30,120,.85),rgba(20,14,70,.95)) !important;border:2px solid #1FC99A !important;box-shadow:0 0 14px -6px rgba(31,201,154,.8),0 4px 0 rgba(8,6,40,.6) !important}"
            f"{k} button p{{font-size:1.02rem !important;font-weight:800 !important;color:#fff !important}}"
            f"{k} button[data-testid$='primary']{{background:linear-gradient(180deg,#5BF5A0,#18DB7C) !important;border:0 !important;box-shadow:0 4px 0 #0F8F51,0 0 18px -4px rgba(61,220,151,.8) !important}}"
            f"{k} button[data-testid$='primary'] p{{color:#06361F !important}}"
            + regras + "</style>")


def css() -> str:
    q = Q
    fs, fi = fundo_cartao("saldo"), fundo_cartao("item")
    return ("<style>"
            # ícones em máscara
            ".lv-ic{display:inline-block;flex:none;background:var(--c);-webkit-mask:var(--m) center/contain no-repeat;mask:var(--m) center/contain no-repeat}"
            # título
            ".lv-tit{display:flex;align-items:center;gap:10px;min-width:0}"
            ".lv-tit .a{font-weight:900;font-size:clamp(1.5rem,6.5vw,2.1rem);line-height:1.05;color:#fff !important}.lv-tit .a span{color:#2EE59D !important}"
            ".lv-tit .b{margin-top:3px;font-size:clamp(.72rem,3vw,.95rem);line-height:1.25;color:#CFC8EE !important}"
            f"{q} .st-key-lj_cab [data-testid='stHorizontalBlock']{{flex-wrap:nowrap !important;gap:8px !important;align-items:center !important}}"
            f"{q} .st-key-lj_cab [data-testid='stColumn']{{min-width:0 !important}}"
            # botões-pílula (Meus itens, Como ganhar?)
            f"{q} .st-key-lj_meus button,{q} .st-key-lj_como button{{min-height:44px !important;height:auto !important;padding:6px 16px 6px 12px !important;border-radius:999px !important;display:flex !important;align-items:center;gap:8px;"
            "background:linear-gradient(180deg,#5B3FD6,#3B24A8) !important;border:1.5px solid #8B6CFF !important;box-shadow:0 0 16px -4px rgba(139,108,255,.9),0 3px 0 #1E0F6B !important}"
            f"{q} .st-key-lj_meus button p,{q} .st-key-lj_como button p{{font-size:.95rem !important;font-weight:800 !important;color:#fff !important;white-space:nowrap}}"
            f"{q} .st-key-lj_meus button:before{{content:'';width:22px;height:22px;flex:none;background:#C5B3FF;-webkit-mask:{_m('presente')} center/contain no-repeat;mask:{_m('presente')} center/contain no-repeat}}"
            f"{q} .st-key-lj_como button:before{{content:'';width:26px;height:26px;flex:none;background:url(\"{AL.uri('tc')}\") center/contain no-repeat}}"
            # saldo
            f"{q} .st-key-lj_saldo{{position:relative;margin:8px 0 12px;border-radius:24px;border:2px solid transparent;overflow:hidden;"
            f"background:url(\"{fs}\") right bottom/cover no-repeat padding-box,linear-gradient(120deg,#2A1B86,#18105A 60%,#120B45) padding-box,linear-gradient(90deg,#2BA7FF,#8B6CFF,#2BA7FF) border-box;"
            "box-shadow:0 0 24px -10px rgba(43,167,255,.8)}"
            ".lv-sd{display:flex;align-items:center;gap:10px;min-height:120px;padding:6px 8px}"
            ".lv-sd-a{flex:0 0 32%;max-width:190px}.lv-sd-a img,.lv-bau-a img{width:100%;height:auto;display:block;-webkit-mask-image:radial-gradient(ellipse at 50% 52%,#000 58%,transparent 98%);mask-image:radial-gradient(ellipse at 50% 52%,#000 58%,transparent 98%)}"
            ".lv-sd-l{align-self:stretch;width:1px;margin:14px 2px;background:rgba(197,179,255,.35)}"
            ".lv-sd-v{flex:1;min-width:0}.lv-sd-v .n{display:flex;align-items:center;gap:8px}.lv-sd-v .n img{width:clamp(26px,7vw,40px);height:auto}"
            ".lv-sd-v b{font-size:clamp(1.9rem,8vw,2.8rem);font-weight:900;line-height:1;color:#fff !important}"
            ".lv-sd-v .t{margin-top:4px;font-size:clamp(.78rem,3.2vw,1rem);color:#E3DDFF !important}"
            f"{q} .st-key-lj_como{{position:absolute !important;right:16px;top:50%;transform:translateY(-50%);width:auto !important;z-index:2}}"
            "@media (max-width:620px){.lv-sd{padding-bottom:64px}" + f"{q} .st-key-lj_como{{top:auto;bottom:12px;transform:none;right:12px}}}}"
            # seção
            ".lv-sec{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:16px 0 8px}"
            ".lv-sec .l{display:flex;align-items:center;gap:10px;min-width:0;font-weight:900;font-size:clamp(1.05rem,4.6vw,1.45rem);color:#fff !important}"
            ".lv-pill{display:inline-flex;align-items:center;gap:6px;flex:none;padding:6px 12px;border-radius:999px;border:1.5px solid #1FC99A;background:rgba(8,40,60,.7);font-size:clamp(.68rem,2.9vw,.88rem);color:#E3DDFF !important}"
            ".lv-pill b{color:#2EE59D !important}"
            # baú em destaque
            f"{q} .st-key-lj_bau{{position:relative;margin:6px 0 14px;border-radius:24px;border:2px solid transparent;overflow:hidden;"
            f"background:url(\"{fs}\") right bottom/cover no-repeat padding-box,linear-gradient(120deg,#2A1B86,#18105A 60%,#120B45) padding-box,linear-gradient(90deg,#8B6CFF,#2BA7FF,#8B6CFF) border-box;"
            "box-shadow:0 0 24px -10px rgba(139,108,255,.9)}"
            ".lv-bau{display:flex;align-items:center;gap:6px;min-height:190px;padding:10px 12px 72px 0}"
            ".lv-bau-a{flex:0 0 38%;max-width:260px}"
            ".lv-bau-t{flex:1;min-width:0}.lv-bau-t .n{font-weight:900;font-size:clamp(1.25rem,5.4vw,1.8rem);color:#fff !important;line-height:1.1}"
            ".lv-bau-t .d{margin-top:6px;font-size:clamp(.8rem,3.3vw,1.05rem);line-height:1.3;color:#E3DDFF !important}"
            ".lv-bau-t .p{display:flex;align-items:center;gap:8px;margin-top:8px}.lv-bau-t .p img{width:28px;height:auto}.lv-bau-t .p b{font-size:clamp(1.1rem,4.6vw,1.6rem);color:#FFD76A !important}"
            ".lv-disp{position:absolute;top:12px;right:12px;padding:5px 12px;border-radius:999px;background:#2B1C9A;border:1px solid #6C5CFF;font-size:clamp(.66rem,2.8vw,.85rem);font-weight:700;color:#fff !important}"
            f"{q} .st-key-tc_bau_abrir{{position:absolute !important;right:14px;bottom:14px;width:min(58%,300px) !important}}"
            f"{q} .st-key-tc_bau_abrir button,{q} .st-key-tc_bau_abrir button{{min-height:50px !important;border-radius:999px !important;border:0 !important;"
            "background:linear-gradient(180deg,#5BF5A0,#18DB7C) !important;box-shadow:0 4px 0 #0F8F51,0 0 18px -4px rgba(61,220,151,.8) !important}"
            f"{q} .st-key-tc_bau_abrir button :is(p,span),{q} .st-key-tc_bau_abrir button :is(p,span){{color:#06361F !important;-webkit-text-fill-color:#06361F !important;font-weight:900 !important;font-size:1.1rem !important}}"
            f"{q} .st-key-tc_bau_abrir button:disabled{{opacity:.55 !important;filter:grayscale(.4)}}"
            # itens
            f"{q} [class*='st-key-lj_it_']{{border-radius:20px;border:1.5px solid #5B4BE0;padding:10px 10px 12px !important;gap:8px !important;"
            f"background:url(\"{fi}\") right bottom/cover no-repeat,linear-gradient(160deg,#1E1566,#140E48);box-shadow:0 0 16px -8px rgba(108,92,255,.9)}}"
            ".lv-it .top{display:flex;align-items:center;gap:8px;min-height:64px}.lv-it .pv{flex:0 0 52px;display:grid;place-items:center}"
            ".lv-it .n{font-weight:800;font-size:clamp(.82rem,3.4vw,1rem);line-height:1.15;color:#fff !important}"
            ".lv-it .d{margin-top:2px;font-size:clamp(.66rem,2.7vw,.8rem);line-height:1.25;color:#CFC8EE !important}"
            ".lv-it .pr{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:6px}.lv-it .pr img{width:24px;height:auto}.lv-it .pr b{font-size:1.15rem;color:#FFD76A !important}"
            f"{q} [class*='st-key-lj_it_'] button{{min-height:42px !important;border-radius:999px !important;border:1.5px solid #8B6CFF !important;"
            "background:linear-gradient(180deg,#6A4BEA,#3F27B0) !important;box-shadow:0 3px 0 #1E0F6B !important}"
            f"{q} [class*='st-key-lj_it_'] button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important}}"
            f"{q} [class*='st-key-lj_it_'] button:disabled{{opacity:.5 !important}}"
            f"{q} .st-key-lj_itens [data-testid='stHorizontalBlock']{{flex-wrap:nowrap !important;gap:8px !important}}"
            f"{q} .st-key-lj_itens [data-testid='stColumn']{{min-width:0 !important}}"
            "</style>")
