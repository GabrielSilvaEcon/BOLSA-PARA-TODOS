"""Tela da coleção de emblemas (Fase 3). Só apresentação: as regras estão em emblemas.py."""
from __future__ import annotations

import html

import emblemas as EM

_e = lambda x: html.escape(str(x), quote=True)

CSS = """<style>
.em-top{display:flex;align-items:center;gap:12px;padding:12px 14px;border-radius:18px;margin:4px 0 12px;background:linear-gradient(135deg,#34286F,#1B1545);border:1px solid rgba(242,184,75,.35)}
.em-top b{font-size:1.5rem;font-weight:900;color:#FFD66B !important}
.em-top span{color:#EDE9FF !important;font-size:.9rem}
.em-sec{display:flex;justify-content:space-between;align-items:center;margin:18px 2px 8px;font-weight:900;font-size:1.02rem;color:#F6F3FF !important}
.em-sec i{font-style:normal;font-weight:800;font-size:.8rem;color:#CFC8EE !important}
.em-grade{display:grid;grid-template-columns:repeat(2,1fr);gap:10px}
@media (min-width:640px){.em-grade{grid-template-columns:repeat(3,1fr)}}
.em-c{position:relative;border-radius:16px;padding:12px 10px;text-align:center;background:#241C4D;border:1px solid color-mix(in srgb,var(--c) 55%,transparent);box-shadow:0 3px 0 rgba(0,0,0,.25)}
.em-c .e{width:52px;height:52px;margin:0 auto 6px;border-radius:50%;display:grid;place-items:center;font-size:1.7rem;background:radial-gradient(circle at 30% 20%,rgba(255,255,255,.35),transparent 55%),var(--c)}
.em-c .n{font-weight:800;font-size:.9rem;line-height:1.15;color:#F6F3FF !important}
.em-c .d{margin-top:4px;font-size:.74rem;line-height:1.3;color:#CFC8EE !important}
.em-c .s{margin-top:6px;font-size:.7rem;font-weight:800;color:#3DDC97 !important}
.em-c.off{background:#1A1438;border-color:rgba(255,255,255,.12);box-shadow:none}
.em-c.off .e{background:#2A2358;filter:grayscale(1);opacity:.55}
.em-c.off .n,.em-c.off .d{opacity:.7}
.em-c.off .s{color:#9C94C9 !important}
.em-nota{margin-top:14px;font-size:.78rem;color:#BDB5E6 !important}
</style>"""


def html_colecao(col: list[dict]) -> str:
    ok, total = EM.totais(col)
    partes = [f"<div class='em-top'><b>{ok}/{total}</b><span>emblemas conquistados</span></div>"]
    for c in col:
        cards = "".join(
            f"<div class='em-c{'' if i['ok'] else ' off'}' style='--c:{_e(i['cor'])}'><div class='e'>{_e(i['emblema'])}</div>"
            f"<div class='n'>{_e(i['nome'])}</div><div class='d'>{_e(i['descricao'])}</div>"
            f"<div class='s'>{'Conquistado' if i['ok'] else 'Bloqueado'}</div></div>" for i in c["itens"])
        partes.append(f"<div class='em-sec'>{_e(c['categoria'])}<i>{c['ok']}/{c['total']}</i></div><div class='em-grade'>{cards}</div>")
    partes.append("<div class='em-nota'>Emblemas são honrarias: não pagam XP, Ticker Coins nem T$. Os prêmios continuam nas missões e conquistas.</div>")
    return "".join(partes)


def contexto_da_tela(res: dict, cart: dict | None) -> dict:
    """ctx dos emblemas com o que a Wallet Game e a Jornada já calcularam. Qualquer falha de leitura vira 'sem dado', nunca erro."""
    resumo, unidades, nivel = {}, 0, 1
    try:
        import educacao_app as EA
        import jornada as JO
        import nivel as NV
        p = EA.prog()
        resumo = JO.resumo(p)
        unidades = sum(1 for u in JO.mapa(p) if u.get("completa"))
        nivel = NV.nivel_de(resumo.get("xp", 0))
    except Exception:
        pass
    return EM.contexto(resumo, unidades, nivel, (res or {}).get("conquistas") or [], True, (cart or {}).get("selos") or [])
