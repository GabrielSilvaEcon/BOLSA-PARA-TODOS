"""Card do nível geral (Fase 2): reaproveitável em Jornada, Perfil e Home. Só apresentação; a regra está em nivel.py."""
from __future__ import annotations

import html

import nivel as NV

CSS = """<style>
.nv{max-width:560px;margin:0 auto 14px;padding:14px 16px;border-radius:22px;border:1px solid rgba(255,255,255,.1);
  background:linear-gradient(160deg,rgba(60,110,255,.22),rgba(16,24,63,.9) 70%);color:#fff}
.nv,.nv .a,.nv .b,.nv .nv-f,.nv .nv-f span,.nv .nv-hist{color:#fff !important}
.nv .nv-n,.nv .nv-n small,.nv .nv-n b{color:#1a1200 !important}
.nv-t{display:flex;align-items:center;gap:12px}
.nv-n{flex:0 0 auto;width:54px;height:54px;border-radius:16px;display:flex;flex-direction:column;align-items:center;justify-content:center;
  background:linear-gradient(145deg,#F2B84B,#FF9B3D);color:#1a1200;font-weight:900;line-height:1}
.nv-n small{font-size:.58rem;font-weight:800;letter-spacing:.06em}.nv-n b{font-size:1.45rem}
.nv-h{min-width:0}.nv-h .a{font-weight:800;font-size:1.05rem}.nv-h .b{font-size:.8rem;opacity:.75}
.nv-bar{height:10px;border-radius:99px;background:rgba(255,255,255,.12);margin:12px 0 6px;overflow:hidden}
.nv-bar i{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#3DDC97,#2BA7C9)}
.nv-f{display:flex;justify-content:space-between;gap:8px;font-size:.76rem;opacity:.8}
.nv-hist{margin-top:10px;font-size:.76rem;opacity:.8;border-top:1px solid rgba(255,255,255,.1);padding-top:8px}
</style>"""


def html_nivel(xp: int, xp_dia: dict | None = None) -> str:
    e = NV.estado(xp)
    if e["maximo"]:
        sub, rod = "Nível máximo alcançado", f"{e['xp']} XP"
    else:
        sub = f"Faltam {e['falta']} XP para {html.escape(e['proximo_titulo'])}"
        rod = f"{e['xp_no_nivel']} / {e['xp_faixa']} XP"
    hist = ""
    if xp_dia is not None:
        h = NV.historico(e["xp"], xp_dia)[-3:]
        if h:
            itens = " · ".join(f"Nível {x['nivel']} em {x['data'][8:10]}/{x['data'][5:7]}" for x in h)
            hist = f"<div class='nv-hist'>Evolução recente: {html.escape(itens)}</div>"
    return (f"<div class='nv'><div class='nv-t'><div class='nv-n'><small>NÍVEL</small><b>{e['nivel']}</b></div>"
            f"<div class='nv-h'><div class='a'>{html.escape(e['titulo'])}</div><div class='b'>{sub}</div></div></div>"
            f"<div class='nv-bar'><i style='width:{e['pct'] * 100:.0f}%'></i></div>"
            f"<div class='nv-f'><span>{rod}</span><span>XP vem só de estudar</span></div>{hist}</div>")


def celebracao_html(antes: int, depois: int) -> str:
    s = NV.subiu(antes, depois)
    if not s:
        return ""
    return (f"<div class='nv' style='text-align:center'><div style='font-size:1.6rem'>🎉</div><div class='nv-h'><div class='a'>"
            f"Você subiu para o nível {s['para']}!</div><div class='b'>Novo título: {html.escape(s['titulo'])}</div></div></div>")
