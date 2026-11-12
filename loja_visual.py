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
    return (f"<div class='lv-tit'>{icone('cart', '#2EE59D', 32)}<div><div class='a'>Loja <span>Ticker</span></div>"
            "<div class='b'>Troque seus Ticker Coins por itens incríveis!</div></div></div>")


def html_saldo(saldo) -> str:
    v = "—" if saldo is None else f"{int(saldo):,}".replace(",", ".")
    return (f"<div class='lv-sd'><div class='lv-sd-a'>{img('moedas', 'Pilha de moedas')}</div><div class='lv-sd-l'></div>"
            f"<div class='lv-sd-v'><div class='n'>{img('tc')}<b>{_e(v)}</b></div><div class='t'>Ticker Coins disponíveis</div></div></div>")


def html_secao(titulo: str, ic: str, cor: str, pill: str = "") -> str:
    p = f"<span class='lv-pill'>{icone('relogio', '#2EE59D', 16)}<span>Renova em: <b>{_e(pill)}</b></span></span>" if pill else ""
    return f"<div class='lv-sec'><div class='l'>{icone(ic, cor, 26)}<span>{_e(titulo)}</span></div>{p}</div>"


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
            ".lv-tit .a{font-weight:900;font-size:clamp(1.25rem,5vw,1.8rem);line-height:1.05;color:#fff !important}.lv-tit .a span{color:#2EE59D !important}"
            ".lv-tit .b{margin-top:2px;font-size:clamp(.66rem,2.6vw,.85rem);line-height:1.25;color:#CFC8EE !important}"
            f"{q} .st-key-lj_cab{{display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;align-items:center !important;gap:10px !important;margin:0 0 4px !important}}"
            f"{q} .st-key-lj_cab>*{{width:auto !important;flex:0 0 auto !important;min-width:0 !important}}"
            f"{q} .st-key-lj_cab>[data-testid='stElementContainer']:has(.lv-tit){{flex:1 1 0 !important}}"
            # botões-pílula (Meus itens, Como ganhar?)
            f"{q} .st-key-lj_meus button,{q} .st-key-lj_como button{{min-height:38px !important;height:auto !important;padding:4px 14px 4px 10px !important;border-radius:999px !important;display:flex !important;align-items:center;gap:8px;"
            "background:linear-gradient(180deg,#5B3FD6,#3B24A8) !important;border:1.5px solid #8B6CFF !important;box-shadow:0 0 16px -4px rgba(139,108,255,.9),0 3px 0 #1E0F6B !important}"
            f"{q} .st-key-lj_meus button p,{q} .st-key-lj_como button p{{font-size:.85rem !important;font-weight:800 !important;color:#fff !important;white-space:nowrap}}"
            f"{q} .st-key-lj_meus button:before{{content:'';width:22px;height:22px;flex:none;background:#C5B3FF;-webkit-mask:{_m('presente')} center/contain no-repeat;mask:{_m('presente')} center/contain no-repeat}}"
            f"{q} .st-key-lj_como button:before{{content:'';width:26px;height:26px;flex:none;background:url(\"{AL.uri('tc')}\") center/contain no-repeat}}"
            # saldo
            f"{q} .st-key-lj_saldo{{position:relative;margin:6px 0 8px;border-radius:22px;border:2px solid transparent;overflow:hidden;"
            f"background:url(\"{fs}\") right bottom/cover no-repeat padding-box,linear-gradient(120deg,#2A1B86,#18105A 60%,#120B45) padding-box,linear-gradient(90deg,#2BA7FF,#8B6CFF,#2BA7FF) border-box;"
            "box-shadow:0 0 24px -10px rgba(43,167,255,.8)}"
            ".lv-sd{display:flex;align-items:center;gap:10px;min-height:84px;padding:4px 8px}"
            ".lv-sd-a{flex:0 0 26%;max-width:140px}.lv-sd-a img,.lv-bau-a img{width:100%;height:auto;display:block;-webkit-mask-image:radial-gradient(ellipse at 50% 52%,#000 58%,transparent 98%);mask-image:radial-gradient(ellipse at 50% 52%,#000 58%,transparent 98%)}"
            ".lv-sd-l{align-self:stretch;width:1px;margin:10px 2px;background:rgba(197,179,255,.35)}"
            ".lv-sd-v{flex:1;min-width:0}.lv-sd-v .n{display:flex;align-items:center;gap:8px}.lv-sd-v .n img{width:clamp(26px,7vw,40px);height:auto}"
            ".lv-sd-v b{font-size:clamp(1.6rem,6.5vw,2.3rem);font-weight:900;line-height:1;color:#fff !important}"
            ".lv-sd-v .t{margin-top:4px;font-size:clamp(.7rem,2.8vw,.9rem);color:#E3DDFF !important}"
            f"{q} .st-key-lj_como{{position:absolute !important;right:16px;top:50%;transform:translateY(-50%);width:auto !important;z-index:2}}"
            "@media (max-width:620px){.lv-sd{padding-bottom:64px}" + f"{q} .st-key-lj_como{{top:auto;bottom:12px;transform:none;right:12px}}}}"
            # seção
            ".lv-sec{display:flex;align-items:center;justify-content:space-between;gap:8px;margin:8px 0 6px}"
            ".lv-sec .l{display:flex;align-items:center;gap:8px;min-width:0}.lv-sec .l span{font-weight:900;font-size:clamp(1rem,4vw,1.3rem);color:#fff !important;-webkit-text-fill-color:#fff !important}"
            ".lv-pill{display:inline-flex;align-items:center;gap:6px;flex:none;padding:6px 12px;border-radius:999px;border:1.5px solid #1FC99A;background:rgba(8,40,60,.7);font-size:clamp(.66rem,2.6vw,.8rem)}.lv-pill span{color:#E3DDFF !important;-webkit-text-fill-color:#E3DDFF !important}"
            ".lv-pill b{color:#2EE59D !important;-webkit-text-fill-color:#2EE59D !important}"
            # baú em destaque
            f"{q} .st-key-lj_bau{{position:relative;margin:4px 0 10px;border-radius:22px;border:2px solid transparent;overflow:hidden;"
            f"background:url(\"{fs}\") right bottom/cover no-repeat padding-box,linear-gradient(120deg,#2A1B86,#18105A 60%,#120B45) padding-box,linear-gradient(90deg,#8B6CFF,#2BA7FF,#8B6CFF) border-box;"
            "box-shadow:0 0 24px -10px rgba(139,108,255,.9)}"
            ".lv-bau{display:flex;align-items:center;gap:6px;min-height:132px;padding:8px 232px 8px 0}"
            ".lv-bau-a{flex:0 0 32%;max-width:190px}"
            ".lv-bau-t{flex:1;min-width:0}.lv-bau-t .n{font-weight:900;font-size:clamp(1.1rem,4.4vw,1.5rem);color:#fff !important;line-height:1.1}"
            ".lv-bau-t .d{margin-top:4px;font-size:clamp(.72rem,2.9vw,.92rem);line-height:1.3;color:#E3DDFF !important}"
            ".lv-bau-t .p{display:flex;align-items:center;gap:6px;margin-top:6px}.lv-bau-t .p img{width:22px;height:auto}.lv-bau-t .p b{font-size:clamp(.95rem,3.6vw,1.2rem);color:#FFD76A !important}"
            ".lv-disp{position:absolute;top:12px;right:12px;padding:5px 12px;border-radius:999px;background:#2B1C9A;border:1px solid #6C5CFF;font-size:clamp(.66rem,2.8vw,.85rem);font-weight:700;color:#fff !important}"
            f"{q} .st-key-tc_bau_abrir{{position:absolute !important;right:14px;bottom:12px;width:210px !important}}"
            f"{q} .st-key-tc_bau_abrir button,{q} .st-key-tc_bau_abrir button{{min-height:44px !important;border-radius:999px !important;border:0 !important;"
            "background:linear-gradient(180deg,#5BF5A0,#18DB7C) !important;box-shadow:0 4px 0 #0F8F51,0 0 18px -4px rgba(61,220,151,.8) !important}"
            f"{q} .st-key-tc_bau_abrir button :is(p,span),{q} .st-key-tc_bau_abrir button :is(p,span){{color:#06361F !important;-webkit-text-fill-color:#06361F !important;font-weight:900 !important;font-size:1rem !important}}"
            f"{q} .st-key-tc_bau_abrir button:disabled{{opacity:.55 !important;filter:grayscale(.4)}}"
            "@media (max-width:620px){.lv-bau{padding:8px 8px 62px 0;min-height:150px}" + f"{q} .st-key-tc_bau_abrir{{left:12px !important;right:12px !important;width:auto !important}}}}"
            # itens
            f"{q} [class*='st-key-lj_it_']{{border-radius:20px;border:1.5px solid #5B4BE0;padding:8px 8px 10px !important;gap:6px !important;"
            f"background:url(\"{fi}\") right bottom/cover no-repeat,linear-gradient(160deg,#1E1566,#140E48);box-shadow:0 0 16px -8px rgba(108,92,255,.9)}}"
            ".lv-it .top{display:flex;align-items:center;gap:6px;min-height:46px}.lv-it .pv{flex:0 0 40px;width:40px;height:40px;display:grid;place-items:center;overflow:visible}"
            ".lv-it .n{font-weight:800;font-size:clamp(.82rem,3.4vw,1rem);line-height:1.15;color:#fff !important}"
            ".lv-it .d{margin-top:2px;font-size:clamp(.66rem,2.7vw,.8rem);line-height:1.25;color:#CFC8EE !important}"
            ".lv-it .pr{display:flex;align-items:center;justify-content:center;gap:6px;margin-top:2px}.lv-it .pr img{width:24px;height:auto}.lv-it .pr b{font-size:1.15rem;color:#FFD76A !important}"
            f"{q} [class*='st-key-lj_it_'] button{{min-height:38px !important;border-radius:999px !important;border:1.5px solid #8B6CFF !important;"
            "background:linear-gradient(180deg,#6A4BEA,#3F27B0) !important;box-shadow:0 3px 0 #1E0F6B !important}"
            f"{q} [class*='st-key-lj_it_'] button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important}}"
            f"{q} [class*='st-key-lj_it_'] button:disabled{{opacity:.5 !important}}"
            f"{q} .st-key-lj_itens{{display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr)) !important;gap:8px !important;margin:0 0 8px}}"
            f"{q} .st-key-lj_itens>*{{min-width:0 !important;width:auto !important}}"
            ".lv-it .pv .vp{transform:scale(.7);transform-origin:center}"
            "</style>")
