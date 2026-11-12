"""Visual do pop-up 'Você ganhou!', copiado da referência enviada pelo Gabriel: moldura neon, título com 'ganhou!' em verde, mascote comemorando
à esquerda, ganhos à direita (estrela, troféu, moedas) e botão verde. Módulo puro: só gera HTML/CSS. As mensagens vêm de ganhos.py; nada aqui paga valor."""
from __future__ import annotations

import html

import arte_ganhos as AG
import arte_tickerhunters as AT

SUB = {"⚡": "Experiência", "🪙": "Ticker Coins", "🔥": "Sequência de estudo", "🏆": "Nível"}
_D = "html body [data-testid=\"stDialog\"] [role=\"dialog\"]"


def _icone(ic: str) -> str:
    nome = {"⚡": "estrela", "🏆": "trofeu", "🪙": "moedas"}.get(ic)
    if nome and AG.existe(nome):
        return f"<img src='{AG.uri(nome)}' alt=''>"
    return AT.img("fogo" if ic == "🔥" else "tc", 56)


def html_ganhos(msgs: list[dict]) -> str:
    itens = "".join(f"<div class='it'><div class='im'>{_icone(m.get('icone', ''))}</div><div class='tx'><b>{html.escape(str(m.get('texto', '')))}</b>"
                    f"<span>{html.escape(SUB.get(m.get('icone', ''), ''))}</span></div></div>" for m in msgs)
    mascote = f"<img src='{AG.uri('mascote')}' alt='Caramelo comemorando'>" if AG.existe("mascote") else AT.img(AT.pose("celebrando"), 150)
    chuva = "".join(f"<i class='fx f{i}{'' if i % 3 else ' est'}'></i>" for i in range(7)) if AG.existe("moedas") else ""
    return (f"<div class='gv-box'><div class='gv-fx' aria-hidden='true'>{chuva}</div><div class='gv-t'>Você <i>ganhou!</i></div><div class='gv-g'><div class='gv-m'>{mascote}</div><div class='gv-l'></div>"
            f"<div class='gv-i'>{itens}</div></div></div>")


def css() -> str:
    return ("<style>"
            f"{_D}{{background:radial-gradient(circle at 20% 30%,rgba(139,108,255,.25),transparent 55%),#15124B !important;border:3px solid transparent !important;border-radius:28px !important;padding:0 6px 10px !important;"
            "background-clip:padding-box,border-box !important;background-origin:border-box !important;"
            "box-shadow:0 0 0 3px rgba(108,92,255,.55),0 0 34px rgba(108,92,255,.65),0 18px 50px rgba(0,0,0,.6) !important}"
            f"{_D} [data-testid=\"stVerticalBlock\"]{{gap:.4rem !important}}"
            f"{_D} h2{{position:absolute !important;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);padding:0 !important;margin:0 !important}}"
            f"{_D} .gv-t{{font-size:clamp(1.7rem,6.5vw,2.4rem);font-weight:900;font-style:italic;line-height:1.1;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;margin:0 0 4px 6px}}"
            f"{_D} .gv-t i{{color:#5BF5A0 !important;-webkit-text-fill-color:#5BF5A0 !important}}"
            f"{_D} .gv-g{{display:flex;align-items:center;gap:8px}}"
            f"{_D} .gv-m{{flex:0 0 48%;max-width:300px}}{_D} .gv-m img{{width:100%;height:auto;display:block}}"
            f"{_D} .gv-l{{align-self:stretch;width:1px;margin:16px 0;background:rgba(197,179,255,.35);flex:none}}"
            f"{_D} .gv-i{{flex:1;min-width:0;display:flex;flex-direction:column;gap:12px;padding:0 4px}}"
            f"{_D} .gv-i .it{{display:flex;align-items:center;gap:12px}}"
            f"{_D} .gv-i .im{{flex:0 0 58px;display:grid;place-items:center}}{_D} .gv-i .im img{{width:58px;height:auto;display:block}}"
            f"{_D} .gv-i .tx b{{display:block;color:#fff !important;-webkit-text-fill-color:#fff !important;font-size:clamp(.95rem,3.8vw,1.25rem);font-weight:800;line-height:1.15}}"
            f"{_D} .gv-i .tx span{{display:block;margin-top:2px;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important;font-size:clamp(.72rem,2.9vw,.9rem)}}"
            f"{_D} [class*=\"st-key-ganhos_ok\"] button{{min-height:54px !important;border-radius:999px !important;border:0 !important;"
            "background:linear-gradient(180deg,#8CFFB4,#4BE38A) !important;box-shadow:0 4px 0 #1E8F52,0 0 20px -4px rgba(61,220,151,.7) !important}"
            f"{_D} [class*=\"st-key-ganhos_ok\"] button :is(p,span){{color:#06361F !important;-webkit-text-fill-color:#06361F !important;font-weight:900 !important;font-size:1.25rem !important}}"
            f"{_D} .gv-box{{position:relative}}"
            "@keyframes gvPop{0%{opacity:0;transform:scale(.3) translateY(14px)}60%{transform:scale(1.12)}100%{opacity:1;transform:none}}"
            "@keyframes gvMasc{0%{opacity:0;transform:translateX(-30px) scale(.8)}65%{transform:translateX(4px) scale(1.04)}100%{opacity:1;transform:none}}"
            "@keyframes gvBoia{0%,100%{transform:translateY(0)}50%{transform:translateY(-5px)}}"
            "@keyframes gvChuva{0%{opacity:0;transform:translateY(-30px) rotate(0)}12%{opacity:.95}100%{opacity:0;transform:translateY(300px) rotate(300deg)}}"
            "@keyframes gvPulso{0%,100%{filter:drop-shadow(0 0 0 rgba(242,184,75,0))}50%{filter:drop-shadow(0 0 10px rgba(242,184,75,.9))}}"
            f"{_D} .gv-m img{{animation:gvMasc .6s cubic-bezier(.2,.9,.3,1.2) both,gvBoia 3.2s ease-in-out .7s infinite}}"
            f"{_D} .gv-t{{animation:gvPop .5s ease both}}"
            f"{_D} .gv-i .it{{animation:gvPop .5s cubic-bezier(.2,.9,.3,1.3) both}}"
            f"{_D} .gv-i .it:nth-child(1){{animation-delay:.25s}}{_D} .gv-i .it:nth-child(2){{animation-delay:.45s}}"
            f"{_D} .gv-i .it:nth-child(3){{animation-delay:.65s}}{_D} .gv-i .it:nth-child(4){{animation-delay:.85s}}"
            f"{_D} .gv-i .im img{{animation:gvPulso 1.8s ease-in-out .9s 3}}"
            f"{_D} .gv-fx{{position:absolute;inset:0;overflow:hidden;pointer-events:none;border-radius:24px;z-index:0}}"
            f"{_D} .gv-fx .fx{{position:absolute;top:0;width:24px;height:24px;background:url('{AG.uri('moedas')}') center/contain no-repeat;opacity:0;animation:gvChuva 2.4s ease-in both}}"
            f"{_D} .gv-fx .fx.est{{background-image:url('{AG.uri('estrela')}')}}"
            f"{_D} .gv-fx .f0{{left:8%;animation-delay:.1s}}{_D} .gv-fx .f1{{left:22%;animation-delay:.5s}}{_D} .gv-fx .f2{{left:38%;animation-delay:.25s}}"
            f"{_D} .gv-fx .f3{{left:54%;animation-delay:.7s}}{_D} .gv-fx .f4{{left:68%;animation-delay:.35s}}{_D} .gv-fx .f5{{left:82%;animation-delay:.6s}}{_D} .gv-fx .f6{{left:92%;animation-delay:.15s}}"
            f"{_D} .gv-t,{_D} .gv-g{{position:relative;z-index:1}}"
            "@media (prefers-reduced-motion:reduce){" + _D + " *{animation:none !important}}"
            "</style>")
