"""Visual dos itens cosméticos da Loja Ticker (Fase 8): CSS do tema aplicado ao app, molduras, fundos de perfil e confete dos efeitos.
Módulo puro (só gera texto HTML/CSS), sem Streamlit, sem banco. As cores vêm de `loja_catalogo.py`.
Texto de elementos próprios sempre com cor forçada (!important): regras globais do app deixam texto escuro."""
from __future__ import annotations

import html

_Q = "html body .stApp.stApp.stApp"


def _e(x) -> str:
    return html.escape(str(x), quote=True)


# ------------------------------------------------------------------ tema aplicado ao app inteiro
def css_tema(p: dict | None) -> str:
    """CSS que sobrepõe o visual do app com a paleta do tema equipado. Vazio se não há tema (visual original intacto)."""
    if not p:
        return ""
    b0, b1 = p.get("brilho") or (p["secundaria"], p["destaque"])
    luz = bool(p.get("luz"))
    fundo = (f"radial-gradient(circle at 12% -5%,color-mix(in srgb,{b0} 34%,transparent),transparent 46%),"
             f"radial-gradient(circle at 100% 28%,color-mix(in srgb,{b1} 20%,transparent),transparent 52%),{p['fundo']}")
    r = [f":root{{--dz-fundo:{p['fundo']};--dz-cartao:{p['cartao']};--dz-elevado:{p['elevado']};--dz-borda:{p['borda']};--dz-texto:{p['texto']};"
         f"--dz-apoio:{p['apoio']};--dz-destaque:{p['destaque']};--dz-sobre:{p['sobre_destaque']};--dz-concha:{p['cartao']};--dz-concha-borda:{p['borda']};"
         f"--dz-ativo:{p['destaque']}}}",
         f"{_Q}{{background:{fundo} !important;background-attachment:fixed !important}}",
         f'{_Q} header[data-testid="stHeader"]{{background:{p["fundo"]} !important;border-bottom:1px solid {p["borda"]} !important}}',
         # cartões da Início, atalhos da Jornada e cabeçalhos
         f'{_Q} [class*="st-key-in_c_"] button,{_Q} [class*="st-key-jor_mais_"] button{{background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 16%,{p["cartao"]}),{p["fundo"]} 80%) !important}}',
         f"{_Q} .st-key-in_hero,{_Q} .st-key-jor_hero{{background:radial-gradient(circle at 12% 40%,color-mix(in srgb,{b0} 40%,transparent),transparent 55%),linear-gradient(135deg,{p['elevado']},{p['cartao']} 70%) !important;border-color:{p['borda']} !important}}",
         f"{_Q} .nv,{_Q} .pf-top{{background:linear-gradient(135deg,{p['elevado']},{p['cartao']}) !important;border-color:{p['borda']} !important}}",
         # botões principais e seleção em pílula
         f'{_Q} [data-testid="stBaseButton-primary"]{{background:linear-gradient(180deg,{p["destaque"]},color-mix(in srgb,{p["destaque"]} 72%,#000)) !important;border-color:{p["destaque"]} !important}}',
         f'{_Q} [data-testid="stBaseButton-primary"] :is(p,span,svg){{color:{p["sobre_destaque"]} !important;-webkit-text-fill-color:{p["sobre_destaque"]} !important}}',
         f'{_Q} [data-testid$="Active"][data-testid^="stBaseButton-pills"],{_Q} [data-testid$="Active"][data-testid^="stBaseButton-segmented"]{{background:linear-gradient(180deg,{p["secundaria"]},color-mix(in srgb,{p["secundaria"]} 70%,#000)) !important}}']
    if luz:
        r.append(f"{_Q}{{background-size:100% 100%,100% 100%,auto !important;animation:tl-luz 22s ease-in-out infinite alternate}}"
                 "@keyframes tl-luz{0%{background-position:0 0,0 0,0 0}100%{background-position:6% 4%,-5% 2%,0 0}}"
                 f"@media (prefers-reduced-motion:reduce){{{_Q}{{animation:none !important}}}}")
    return "<style>" + "".join(r) + "</style>"


# ------------------------------------------------------------------ molduras
CSS_MOLDURA = """<style>
.mo{position:relative;display:inline-grid;place-items:center;padding:5px;border-radius:50%;background:var(--mc);flex:0 0 auto;line-height:0}
.mo>*{border-radius:50%;background:#1A1438;overflow:hidden}
.mo.brilho{box-shadow:0 0 12px var(--mc),0 0 26px color-mix(in srgb,var(--mc) 55%,transparent)}
.mo.pulsa{animation:mo-p 2.8s ease-in-out infinite}
.mo.gira{background:conic-gradient(from 0deg,var(--mg));animation:mo-g 9s linear infinite}
.mo.gira>*{animation:mo-gi 9s linear infinite}
@keyframes mo-p{0%,100%{box-shadow:0 0 8px var(--mc)}50%{box-shadow:0 0 20px var(--mc),0 0 34px color-mix(in srgb,var(--mc) 50%,transparent)}}
@keyframes mo-g{to{transform:rotate(360deg)}}@keyframes mo-gi{to{transform:rotate(-360deg)}}
@media (prefers-reduced-motion:reduce){.mo.pulsa,.mo.gira,.mo.gira>*{animation:none}}
</style>"""


def html_moldura(interior: str, ef: dict | None) -> str:
    """Envolve `interior` (HTML do Caramelo, por exemplo) com a moldura equipada. Sem moldura devolve o interior como está."""
    if not ef:
        return interior
    cor = ef.get("cor") or "#C5B3FF"
    estilo = ef.get("estilo") if ef.get("estilo") in ("solido", "brilho", "pulsa", "gira") else "solido"
    cores = [c for c in (ef.get("cores") or []) if isinstance(c, str)] or [cor]
    mg = ",".join(_e(c) for c in cores + [cores[0]])
    return f"<div class='mo {estilo}' style='--mc:{_e(cor)};--mg:{mg}'>{interior}</div>"


# ------------------------------------------------------------------ fundo do cartão de perfil
def estilo_fundo(ef: dict | None) -> str:
    """Valor do atributo style para o cartão do perfil (vazio sem fundo equipado)."""
    if not ef:
        return ""
    luz = f"radial-gradient(circle at 100% 0%,color-mix(in srgb,{_e(ef['luz'])} 38%,transparent),transparent 55%)," if ef.get("luz") else ""
    return f"background:{luz}linear-gradient(135deg,{_e(ef.get('de', '#3A2C86'))},{_e(ef.get('para', '#1B1545'))}) !important"


# ------------------------------------------------------------------ efeitos de celebração (confete)
CSS_CONFETE = """<style>
.fx{position:absolute;inset:0;pointer-events:none;overflow:hidden}
.fx i{position:absolute;top:-14px;width:9px;height:14px;border-radius:2px;opacity:.95;background:var(--k) !important;animation:fx-c 2.8s linear infinite;animation-delay:var(--d)}
.fx i.estrela{width:14px;height:14px;border-radius:0;clip-path:polygon(50% 0,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%)}
.fx i.bolha{width:10px;height:10px;border-radius:50%;box-shadow:0 0 8px var(--k)}
@keyframes fx-c{to{transform:translateY(240px) rotate(320deg);opacity:0}}
@media (prefers-reduced-motion:reduce){.fx{display:none}}
</style>"""
_CORES_PADRAO = ["#FFD66B", "#3DDC97", "#FF6B8A", "#8B6CFF", "#2BA7C9", "#FFD66B"]


def html_confete(ef: dict | None, n: int = 12) -> str:
    """Camada de confete para colocar dentro de um cartão com position:relative. `ef` = efeito equipado (cores e formas) ou None (confete padrão)."""
    cores = [c for c in ((ef or {}).get("cores") or []) if isinstance(c, str)] or _CORES_PADRAO
    forma = (ef or {}).get("formas") if (ef or {}).get("formas") in ("estrela", "bolha") else ""
    itens = "".join(f"<i class='{forma}' style='left:{4 + (i * 83 // n) % 92}%;--k:{_e(cores[i % len(cores)])};--d:{(i * 0.37) % 2.2:.2f}s'></i>" for i in range(n))
    return f"<div class='fx'>{itens}</div>"


# ------------------------------------------------------------------ prévia do item na vitrine
CSS_PREVIA = """<style>
.vp{flex:0 0 74px;width:74px;height:74px;display:grid;place-items:center;border-radius:18px;position:relative;overflow:hidden;background:#1A1438;border:1px solid rgba(197,179,255,.25)}
.vp.emoji,.vp.texto{border-radius:50%;font-size:1.8rem;font-weight:900;color:#fff !important;background:radial-gradient(circle at 30% 20%,rgba(255,255,255,.35),transparent 55%),var(--c)}
.vp.tema{display:block;padding:0;border:1px solid var(--bd)}
.vp.tema .a{position:absolute;inset:0;background:var(--bg)}
.vp.tema .b{position:absolute;left:7px;right:7px;top:9px;height:15px;border-radius:6px;background:var(--cr);border:1px solid var(--bd)}
.vp.tema .c{position:absolute;left:7px;width:26px;top:30px;height:15px;border-radius:6px;background:var(--cr);border:1px solid var(--bd)}
.vp.tema .d{position:absolute;left:38px;right:7px;top:30px;height:15px;border-radius:6px;background:var(--ds)}
.vp.tema .e{position:absolute;left:7px;right:7px;bottom:7px;height:11px;border-radius:6px;background:var(--cr);border:1px solid var(--bd)}
.vp.tema .e:before{content:"";position:absolute;left:8px;top:3px;width:30px;height:4px;border-radius:3px;background:var(--ds)}
.vp.fundo{background:linear-gradient(135deg,var(--de),var(--pa))}
.vp.fundo .l{position:absolute;inset:0;background:radial-gradient(circle at 100% 0%,color-mix(in srgb,var(--lz) 45%,transparent),transparent 60%)}
.vp.efeito{background:linear-gradient(160deg,#2A2070,#14103A)}
.vp.efeito i{position:absolute;top:8px;width:9px;height:9px;border-radius:2px;background:var(--k);opacity:.95}
.vp.efeito i.estrela{clip-path:polygon(50% 0,61% 35%,98% 35%,68% 57%,79% 91%,50% 70%,21% 91%,32% 57%,2% 35%,39% 35%);border-radius:0;width:12px;height:12px}
.vp.efeito i.bolha{border-radius:50%;box-shadow:0 0 6px var(--k)}
.vp.anel{background:transparent;border:0;overflow:visible}
</style>"""


def html_previa(pv: dict) -> str:
    """Miniatura do item (antes da compra): tema = mini-app com as cores do tema; fundo = degradê; efeito = confete; moldura = aro."""
    t, cor = pv.get("tipo"), _e(pv.get("cor", "#8B6CFF"))
    if t == "tema":
        p = pv.get("paleta") or {}
        st = f"--bg:{_e(p.get('fundo', '#111'))};--cr:{_e(p.get('cartao', '#222'))};--bd:{_e(p.get('borda', '#444'))};--ds:{_e(p.get('destaque', '#fff'))}"
        return f"<div class='vp tema' style='{st}'><div class='a'></div><div class='b'></div><div class='c'></div><div class='d'></div><div class='e'></div></div>"
    if t == "fundo":
        luz = f"<div class='l' style='--lz:{_e(pv['luz'])}'></div>" if pv.get("luz") else ""
        return f"<div class='vp fundo' style='--de:{_e(pv.get('de'))};--pa:{_e(pv.get('para'))}'>{luz}</div>"
    if t == "efeito":
        cores = pv.get("cores") or [cor]
        itens = "".join(f"<i class='{_e(pv.get('formas', ''))}' style='left:{8 + i * 13}%;top:{8 + (i * 17) % 40}px;--k:{_e(cores[i % len(cores)])}'></i>" for i in range(5))
        return f"<div class='vp efeito'>{itens}</div>"
    if t == "anel":
        interior = "<div style='width:46px;height:46px'></div>"
        return "<div class='vp anel'>" + html_moldura(interior, {"cor": pv.get("cor"), "estilo": pv.get("estilo"), "cores": pv.get("cores")}) + "</div>"
    cls = "emoji" if t == "emoji" else "texto"
    return f"<div class='vp {cls}' style='--c:{cor}'>{_e(pv.get('valor', ''))}</div>"
