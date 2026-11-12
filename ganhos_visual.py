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
    return (f"<div class='gv-box'><div class='gv-t'>Você <i>ganhou!</i></div><div class='gv-g'><div class='gv-m'>{mascote}</div><div class='gv-l'></div>"
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
            "</style>")
