"""Tela inicial no formato "mobile game" (só HTML/CSS e regras de apresentação; sem Streamlit, sem banco e sem rede).

Layout da referência visual do TickerHunters (nov/2026), de cima para baixo:
  1. HUD: nível com barra de XP · saldo de Ticker Coins (coroa) · posição no ranking
  2. Banner: plaquinha com o nome, touro, logo TICKER HUNTERS e o cartão HUNTER PASS (passe da temporada)
  3. Pregão Orbit: arte do touro contra o urso no anel neon, com quatro indicadores reais nos cantos
  4. Missões diárias: troféu, barra de progresso e o cofre com a recompensa que ainda dá para ganhar
  5. Três acessos: Carteira · JOGAR AGORA (o grande, dourado) · Mercado

Cada função recebe dados que o app já tem e devolve HTML. Dado ausente vira estado vazio ("—", "sem cotações agora"), nunca um número
inventado. A leitura dos dados fica em home_game_app.py. As artes ficam em static/home (servidas pelo Streamlit em app/static/home).
"""
from __future__ import annotations

import html

import game_ui as G

_E = html.escape
Q = G.Q

ARTE = "app/static/home/"          # arena.webp (touro x urso), touro.webp (logo), trofeu.webp, cofre.webp


def arte(nome: str) -> str:
    return f"{ARTE}{nome}.webp"


# ------------------------------------------------------------------ formatação
def fmt_inteiro(v) -> str:
    """12345 -> '12.345'. Sem valor -> '—'."""
    try:
        return f"{int(v):,}".replace(",", ".")
    except (TypeError, ValueError):
        return "—"


def fmt_var(v) -> str:
    try:
        return f"{float(v):+.2f}%".replace(".", ",").replace("-", "−")
    except (TypeError, ValueError):
        return ""


ROTULO_CURTO = {"Ibovespa": "IBOV", "Dólar": "DÓLAR", "Bitcoin": "BTC", "Índice do medo": "MEDO"}


def rotulo_curto(r: str) -> str:
    r = str(r or "")
    return ROTULO_CURTO.get(r, r.upper()[:8])


# ------------------------------------------------------------------ SVGs pequenos
_COROA = ("<svg class='hg-coroa' viewBox='0 0 40 30' aria-hidden='true'><defs><linearGradient id='hgcr' x1='0' y1='0' x2='0' y2='1'>"
          "<stop offset='0' stop-color='#FFE9A0'/><stop offset='1' stop-color='#E39A12'/></linearGradient></defs>"
          "<path d='M4 24 L2 6 L12 14 L20 2 L28 14 L38 6 L36 24 Z' fill='url(#hgcr)' stroke='#8A4E00' stroke-width='2' stroke-linejoin='round'/>"
          "<rect x='4' y='23' width='32' height='5' rx='2' fill='#F2B84B' stroke='#8A4E00' stroke-width='2'/>"
          "<circle cx='20' cy='16' r='2.6' fill='#FF5B9A'/></svg>")


def _spark(sobe: bool | None) -> str:
    """Mini gráfico decorativo (ícone de tendência, não é série de preços): sobe em verde, cai em vermelho."""
    if sobe is None:
        pts, cor = "0,12 8,10 16,12 24,9 32,11 40,10", "#C9C1F0"
    elif sobe:
        pts, cor = "0,16 7,13 13,14 20,8 27,10 34,4 40,2", G.VERDE
    else:
        pts, cor = "0,4 7,8 13,6 20,12 27,10 34,15 40,17", G.VERMELHO
    seta = ("<path d='M33 1 L40 1 L40 8' fill='none' stroke='{c}' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/>".format(c=cor)
            if sobe else "")
    return (f"<svg class='hg-sp' viewBox='-1 -1 42 20' aria-hidden='true'><polyline points='{pts}' fill='none' stroke='{cor}' "
            f"stroke-width='2' stroke-linecap='round' stroke-linejoin='round'/>{seta}</svg>")


# ------------------------------------------------------------------ 1. HUD
def html_hud_nivel(nivel: dict | None, avatar_src: str = "", cor_anel: str = "#34E85E", nome: str = "") -> str:
    if nivel:
        n = f"Nível {int(nivel['nivel'])}"
        xp = (f"{fmt_inteiro(nivel['xp'])} XP" if nivel.get("maximo")
              else f"{fmt_inteiro(nivel['xp_no_nivel'])} / {fmt_inteiro(nivel['xp_faixa'])} XP")
        pct = 100 * float(nivel.get("pct") or 0)
    else:
        n, xp, pct = "Nível —", "", 0
    av = (f"<img src='{_E(avatar_src)}' alt=''>" if avatar_src else f"<span>{_E((nome[:1] or '?').upper())}</span>")
    return (f"<div class='hg-h hg-lv'><div class='hg-av' style='--r:{_E(cor_anel)}'>{av}</div>"
            f"<div class='hg-lvc'><div class='hg-lvt'><b>{_E(n)}</b><span>{_E(xp)}</span></div>"
            f"<div class='hg-xpb'><i style='width:{max(0, min(100, round(pct)))}%'></i></div></div></div>")


def html_hud_moedas(moedas, moeda_html: str = "") -> str:
    return (f"<div class='hg-h hg-tc' title='Seu saldo de Ticker Coins'>{_COROA}<span class='hg-mo'>{moeda_html or '🪙'}</span>"
            f"<b>{_E(fmt_inteiro(moedas))}</b><small>TC</small></div>")


def html_hud_rank(pos, total, delta=None) -> str:
    """Posição no ranking geral. `delta` (subiu/caiu desde a última leitura) só aparece se vier de verdade."""
    titulo = (f"Você é o {int(pos)}º entre {int(total)} jogadores" if pos and total
              else ("Sua posição no ranking" if pos else "Sem posição no ranking ainda"))
    d = ""
    try:
        if delta:
            k = int(delta)
            d = f"<i class='{'u' if k > 0 else 'd'}'>{'▲' if k > 0 else '▼'}{abs(k)}</i>"
    except (TypeError, ValueError):
        d = ""
    return (f"<div class='hg-h hg-rk' title='{_E(titulo)}'><img src='{arte('touro')}' alt=''>"
            f"<b>{_E(f'#{int(pos)}' if pos else '—')}</b>{d}</div>")


# ------------------------------------------------------------------ 2. banner (nome + marca + Hunter Pass)
def html_banner(nome: str, passe: dict | None) -> str:
    if passe and passe.get("total"):
        feitos, total = int(passe.get("feitos") or 0), int(passe["total"])
        pct = 100 if passe.get("completo") else round(100 * (feitos + float(passe.get("pct") or 0)) / total)
        contagem = f"{feitos}/{total}"
    else:
        pct, contagem = 0, "—"
    return ("<div class='hg-ban'>"
            f"<div class='hg-nome'><span>{_E(nome or 'Jogador')}</span></div>"
            f"<img class='hg-lg' src='{arte('touro')}' alt=''>"
            "<div class='hg-logo'><span class='t'>TICKER</span><span class='h'>HUNTERS</span></div>"
            f"<div class='hg-pass'><b>HUNTER PASS</b><span>{_E(contagem)}</span>"
            f"<div class='hg-pb'><i style='width:{max(0, min(100, pct))}%'></i></div></div>"
            "</div>")


# ------------------------------------------------------------------ 3. Pregão Orbit
_CANTOS = ("tl", "tr", "bl", "br")


def _tile(it: dict, canto: str) -> str:
    v = it.get("var")
    nota = it.get("nota")
    sobe = None if v is None else float(v) >= 0
    if v is not None:
        cor = G.VERDE if sobe else G.VERMELHO
        principal = f"<em class='{'u' if sobe else 'd'}'><i>{'▲' if sobe else '▼'}</i>{_E(fmt_var(v))}</em>"
    else:
        cor = G.OURO
        principal = f"<em class='n'>{_E(str(it.get('valor', '')))}</em>"
    rodape = _E(nota) if nota else _E(str(it.get("valor", ""))) if v is not None else ""
    return (f"<div class='hg-tk {canto}' style='--c:{cor}'><div class='hg-tkh'><span>{_E(rotulo_curto(it.get('rotulo', '')))}</span>"
            f"{_spark(sobe)}</div>{principal}<small>{rodape}</small></div>")


def html_orbit(itens: list | None) -> str:
    """Arena: touro (compradores) contra urso (vendedores) e, nos cantos, os indicadores que o app já busca."""
    itens = [i for i in (itens or []) if isinstance(i, dict) and i.get("valor")][:4]
    tiles = "".join(_tile(i, c) for i, c in zip(itens, _CANTOS))
    vazio = "" if itens else "<div class='hg-ovz'>Sem cotações agora. Elas voltam assim que a fonte responder.</div>"
    return ("<div class='hg-orb'><div class='hg-ot'>PREGÃO ORBIT</div>"
            f"<div class='hg-art'><img class='hg-arena' src='{arte('arena')}' alt='Touro contra urso no pregão' loading='eager'>"
            f"{tiles}{vazio}</div></div>")


# ------------------------------------------------------------------ 4. missões diárias
def resumo_missoes(missoes: list | None) -> dict:
    """De `jogar.resumo(...)['missoes']` para o que o cartão mostra: total, feitas, próxima pendente e pontos ainda a ganhar."""
    ms = [m for m in (missoes or []) if isinstance(m, dict)]
    pend = [m for m in ms if not m.get("ok")]
    pts = 0
    for m in pend:
        try:
            pts += max(0, int(m.get("pontos") or 0))
        except (TypeError, ValueError):
            pass
    return {"total": len(ms), "feitas": len(ms) - len(pend), "proxima": (pend[0].get("titulo") if pend else None), "pontos": pts}


def html_missoes(r: dict) -> str:
    total, feitas = int(r.get("total") or 0), int(r.get("feitas") or 0)
    if not total:
        sub, premio = "Sem missões disponíveis agora.", ""
    elif feitas >= total:
        sub, premio = "Missões de hoje concluídas!", "<b class='ok'>✓ Feito</b>"
    else:
        sub = "Complete desafios e ganhe recompensas!"
        premio = f"<b>+{int(r['pontos'])} pts</b>" if r.get("pontos") else ""
    pct = round(100 * feitas / total) if total else 0
    return ("<div class='hg-ms'>"
            f"<img class='hg-tr' src='{arte('trofeu')}' alt=''>"
            "<div class='hg-mc'><b class='hg-mt'>MISSÕES DIÁRIAS</b>"
            f"<small>{_E(sub)}</small>"
            f"<div class='hg-mr'><div class='hg-mbar'><i style='width:{pct}%'></i></div><span>{feitas} / {total}</span></div></div>"
            f"<div class='hg-cf'><img src='{arte('cofre')}' alt=''>{premio}</div>"
            "</div>")


# ------------------------------------------------------------------ 5. acessos principais
ACESSOS = (
    # (chave, rótulo, página de destino)
    ("carteira", "Carteira", "competicao"),
    ("jogar", "Jogar agora", "jogos"),
    ("mercado", "Mercado", "analisar"),
)


_ALT = {"carteira": "Carteira", "jogar": "Jogar agora", "mercado": "Mercado"}


def html_acesso(chave: str) -> str:
    """Botão com a arte do TickerHunters (static/home/btn_<chave>.webp, o texto já vem na arte)."""
    if chave not in _ALT:
        raise KeyError(chave)
    return f"<div class='hg-bt hg-b-{chave}'><img src='{arte('btn_' + chave)}' alt='{_ALT[chave]}' loading='eager'></div>"


# ------------------------------------------------------------------ CSS da tela
def css_hud_topo() -> str:
    """HUD dentro do cabeçalho (linha única): ícone do app à esquerda, nível/moedas/ranking no meio, busca e sino à direita."""
    t = f"{Q} .st-key-topo_perfil"
    return ("<style>"
            f"{t} [data-testid='stLayoutWrapper']:has(>.st-key-hg_hud),{t} .st-key-hg_hud{{flex:1 1 auto !important;min-width:0 !important;width:auto !important}}"
            f"{t} .st-key-hg_hud{{display:grid !important;grid-template-columns:minmax(0,1.45fr) minmax(0,1fr) minmax(0,.8fr);gap:4px !important;margin:0 4px !important}}"
            f"{t} .st-key-hg_hud .hg-h{{height:36px;padding:2px 6px;border-radius:11px}}"
            f"{t} .st-key-hg_hud .hg-av{{width:28px;height:28px}}"
            f"{t} .st-key-hg_hud .hg-lvt span{{display:none}}{t} .st-key-hg_hud .hg-lvt b{{font-size:.78rem}}"
            f"{t} .st-key-hg_hud .hg-tc b,{t} .st-key-hg_hud .hg-rk b{{font-size:.9rem}}{t} .st-key-hg_hud .hg-tc small{{font-size:.6rem}}"
            f"{t} .st-key-hg_hud .hg-tc svg,{t} .st-key-hg_hud .hg-tc .hg-co{{display:none}}"
            f"{t} .st-key-hg_hud .hg-rk img{{width:22px;height:22px}}"
            f"{t} .st-key-hg_hud [data-testid='stElementContainer']{{margin:0 !important}}"
            "@media (max-width:400px){" f"{t} .st-key-hg_hud .hg-tc small{{display:none}}" "}"
            "</style>")


def css() -> str:
    c = Q
    t = f"{c} .st-key-hg_tela"
    lila = "#CFC8F5"
    return ("<style>"
            # fundo da Home: noite roxa com grade neon (a arte da cidade vem do fundo da tela, se houver)
            f"{t}{{display:flex !important;flex-direction:column !important;gap:8px !important;margin-top:2px}}"
            f"{t}>*,{t} [data-testid='stElementContainer']{{flex:none !important;height:auto !important;min-height:0;margin:0 !important}}"
            f"{t} [data-testid='stMarkdownContainer']{{margin-bottom:0 !important}}"
            f"{t} :is(b,span,small,div,em,i){{-webkit-text-fill-color:currentColor}}"
            # ---- 1. HUD
            f"{c} .st-key-hg_hud{{display:grid !important;grid-template-columns:minmax(0,1.5fr) minmax(0,1fr) minmax(0,.75fr);gap:6px !important}}"
            f"{c} .st-key-hg_hud>*{{min-width:0}}"
            f"{c} .hg-h{{position:relative;box-sizing:border-box;height:40px;border-radius:12px;padding:3px 8px;display:flex;align-items:center;gap:6px;"
            "background:linear-gradient(180deg,rgba(40,36,92,.92),rgba(16,14,48,.92));border:1.5px solid rgba(120,170,255,.45);"
            "box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 0 14px -6px rgba(80,160,255,.8);color:#fff}"
            f"{c} .hg-lv{{padding-left:3px;gap:6px}}"
            f"{c} .hg-av{{flex:0 0 auto;width:32px;height:32px;border-radius:50%;overflow:hidden;display:grid;place-items:center;background:#1B1545;"
            "font-weight:900;color:#fff;box-shadow:0 0 0 2px var(--r),0 0 8px var(--r)}"
            f"{c} .hg-av img{{width:100%;height:100%;object-fit:cover;display:block}}"
            f"{c} .hg-lvc{{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;justify-content:center;gap:3px}}"
            f"{c} .hg-lvt{{display:flex;align-items:baseline;justify-content:space-between;gap:4px;min-width:0}}"
            f"{c} .hg-lvt b{{font-size:.86rem;line-height:1;font-weight:900;white-space:nowrap;color:#DDEBFF}}"
            f"{c} .hg-lvt span{{font-size:.62rem;font-weight:700;color:{lila};white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
            f"{c} .hg-xpb{{height:7px;border-radius:99px;background:rgba(0,0,0,.45);overflow:hidden;box-shadow:inset 0 1px 2px rgba(0,0,0,.6)}}"
            f"{c} .hg-xpb i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#16E0FF,#7CF7FF);box-shadow:0 0 10px #16E0FF}}"
            f"{c} .hg-tc{{justify-content:center;overflow:visible}}"
            f"{c} .hg-coroa{{position:absolute;top:-11px;right:-4px;width:24px;height:18px;transform:rotate(14deg);filter:drop-shadow(0 2px 3px rgba(0,0,0,.6))}}"
            f"{c} .hg-mo{{line-height:0;flex:0 0 auto}}{c} .hg-mo img{{width:22px !important;height:22px !important}}"
            f"{c} .hg-tc b{{font-size:clamp(.9rem,4vw,1.05rem);line-height:1;font-weight:900;color:#FFD76A;white-space:nowrap}}"
            f"{c} .hg-tc small{{font-size:.68rem;font-weight:800;color:#FFE8A8;align-self:flex-end;margin-bottom:6px}}"
            f"{c} .hg-rk{{justify-content:center;gap:5px}}{c} .hg-rk img{{width:26px;height:26px;object-fit:contain;flex:0 0 auto;"
            "-webkit-mask:radial-gradient(circle,#000 60%,transparent 72%);mask:radial-gradient(circle,#000 60%,transparent 72%)}"
            f"{c} .hg-rk b{{font-size:clamp(.9rem,4vw,1.05rem);line-height:1;font-weight:900;color:#FFD76A}}"
            f"{c} .hg-rk i{{font-style:normal;font-size:.72rem;font-weight:900}}{c} .hg-rk i.u{{color:{G.VERDE}}}{c} .hg-rk i.d{{color:{G.VERMELHO}}}"
            # ---- 2. banner
            f"{c} .hg-ban{{position:relative;margin-top:14px;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px;"
            "padding:11px 8px 5px 4px;border-radius:16px;color:#fff;"
            "background:linear-gradient(180deg,rgba(32,30,74,.96),rgba(12,10,36,.96));border:2px solid #5D6694;"
            "box-shadow:inset 0 0 0 1px rgba(0,0,0,.6),inset 0 1px 0 rgba(255,255,255,.18),0 0 22px -8px rgba(120,150,255,.8)}"
            f"{c} .hg-nome{{position:absolute;left:50%;top:-15px;transform:translateX(-50%);max-width:70%}}"
            f"{c} .hg-nome span{{display:block;padding:3px 20px;font-size:.86rem;font-weight:800;color:#EDEBFF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"
            "background:linear-gradient(180deg,#3A3C62,#1C1C3A);border:1.5px solid #6B7099;"
            "clip-path:polygon(10px 0,calc(100% - 10px) 0,100% 50%,calc(100% - 10px) 100%,10px 100%,0 50%)}"
            f"{c} .hg-lg{{width:54px;height:48px;object-fit:cover;-webkit-mask:radial-gradient(ellipse at 50% 48%,#000 58%,transparent 72%);"
            "mask:radial-gradient(ellipse at 50% 48%,#000 58%,transparent 72%);filter:drop-shadow(0 0 10px rgba(160,90,255,.7))}"
            f"{c} .hg-logo{{display:flex;flex-direction:column;line-height:.92;font-style:italic;font-weight:900;letter-spacing:-.02em;min-width:0}}"
            f"{c} .hg-logo span{{display:block;font-size:clamp(1.2rem,6.4vw,1.6rem);line-height:.95 !important}}"
            f"{c} .hg-logo .t{{color:#F4F6FF;text-shadow:0 2px 0 #6C7AA8,0 3px 6px rgba(0,0,0,.6)}}"
            f"{c} .hg-logo .h{{color:#FFC233;background:linear-gradient(180deg,#FFE68A,#F2A50C);-webkit-background-clip:text;background-clip:text;"
            "-webkit-text-fill-color:transparent;filter:drop-shadow(0 2px 0 #8A4E00)}"
            f"{c} .hg-pass{{display:flex;flex-direction:column;align-items:center;gap:1px;padding:4px 8px 5px;border-radius:10px;min-width:92px;"
            "background:linear-gradient(180deg,#FFE79A,#F2B33A 55%,#D98E12);border:1.5px solid #FFF1B8;box-shadow:0 3px 0 #8A5200,0 0 16px -4px rgba(255,200,60,.8)}"
            f"{c} .hg-pass b{{line-height:1.1;font-size:.7rem;font-weight:900;color:#3B2400;letter-spacing:.02em;white-space:nowrap}}"
            f"{c} .hg-pass span{{line-height:1.1;font-size:.74rem;font-weight:900;color:#3B2400}}"
            f"{c} .hg-pb{{width:100%;height:7px;border-radius:99px;background:rgba(60,36,0,.55);overflow:hidden}}"
            f"{c} .hg-pb i{{display:block;height:100%;background:linear-gradient(90deg,#FFF6CF,#FFD24A);border-radius:99px}}"
            # ---- 3. Pregão Orbit
            f"{c} .hg-orb{{position:relative}}"
            f"{c} .hg-ot{{text-align:center;font-size:clamp(1.05rem,5.4vw,1.4rem);font-weight:900;letter-spacing:.02em;color:#9FF3FF;"
            "text-shadow:0 0 10px rgba(60,230,255,.85),0 0 22px rgba(60,230,255,.45);margin:0 0 -2px}"
            f"{c} .hg-art{{position:relative;aspect-ratio:768/490;margin:0 -6px}}"
            f"{c} .hg-arena{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover;"
            "-webkit-mask:radial-gradient(ellipse 72% 70% at 50% 50%,#000 62%,transparent 100%);mask:radial-gradient(ellipse 72% 70% at 50% 50%,#000 62%,transparent 100%)}"
            f"{c} .hg-tk{{position:absolute;width:min(27%,132px);box-sizing:border-box;padding:3px 6px 3px;border-radius:10px;color:#fff;"
            "background:linear-gradient(180deg,rgba(38,42,78,.94),rgba(14,14,40,.94));border:1.5px solid #5A6290;"
            "box-shadow:inset 0 1px 0 rgba(255,255,255,.14),0 0 12px -5px var(--c);"
            "clip-path:polygon(8px 0,100% 0,100% calc(100% - 8px),calc(100% - 8px) 100%,0 100%,0 8px)}"
            f"{c} .hg-tk.tl{{left:6px;top:-4px}}{c} .hg-tk.tr{{right:6px;top:-4px}}{c} .hg-tk.bl{{left:6px;bottom:2px}}{c} .hg-tk.br{{right:6px;bottom:2px}}"
            f"{c} .hg-tkh{{display:flex;align-items:center;justify-content:space-between;gap:4px}}"
            f"{c} .hg-tkh span{{font-size:.66rem;font-weight:900;letter-spacing:.03em;line-height:1.1}}"
            f"{c} .hg-sp{{width:26px;height:12px;flex:0 0 auto}}"
            f"{c} .hg-tk em{{display:flex;align-items:center;gap:3px;font-style:normal;font-size:clamp(.74rem,3.3vw,.88rem);font-weight:900;white-space:nowrap;line-height:1.1}}"
            f"{c} .hg-tk em i{{font-style:normal;font-size:.7em}}"
            f"{c} .hg-tk em.u{{color:{G.VERDE}}}{c} .hg-tk em.d{{color:{G.VERMELHO}}}{c} .hg-tk em.n{{color:#FFD76A}}"
            f"{c} .hg-tk small{{display:block;font-size:.56rem;font-weight:700;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
            f"{c} .hg-ovz{{position:absolute;left:10%;right:10%;bottom:4px;text-align:center;font-size:.78rem;font-weight:700;color:{lila};"
            "background:rgba(10,8,30,.8);border-radius:10px;padding:6px}"
            # cores forçadas: o CSS global do app pinta alguns <span>/<b> de escuro
            f"{c} :is(.hg-lvt b){{color:#DDEBFF !important;-webkit-text-fill-color:#DDEBFF !important}}"
            f"{c} :is(.hg-lvt span,.hg-tk small,.hg-mc small){{color:{lila} !important;-webkit-text-fill-color:{lila} !important}}"
            f"{c} :is(.hg-tkh span,.hg-mt,.hg-mr span,.hg-nome span,.hg-logo .t,.hg-av span,.hg-ovz){{color:#F4F6FF !important;-webkit-text-fill-color:#F4F6FF !important}}"
            f"{c} :is(.hg-tc b,.hg-rk b,.hg-cf b){{color:#FFD76A !important;-webkit-text-fill-color:#FFD76A !important}}"
            f"{c} .hg-tc small{{color:#FFE8A8 !important;-webkit-text-fill-color:#FFE8A8 !important}}"
            f"{c} :is(.hg-pass b,.hg-pass span){{color:#3B2400 !important;-webkit-text-fill-color:#3B2400 !important}}"
            f"{c} .hg-tk em.u{{color:{G.VERDE} !important;-webkit-text-fill-color:{G.VERDE} !important}}"
            f"{c} .hg-tk em.d{{color:{G.VERMELHO} !important;-webkit-text-fill-color:{G.VERMELHO} !important}}"
            f"{c} .hg-tk em.n{{color:#FFD76A !important;-webkit-text-fill-color:#FFD76A !important}}"
            f"{c} .hg-ot{{color:#9FF3FF !important;-webkit-text-fill-color:#9FF3FF !important}}"
            f"{c} .hg-logo .h{{-webkit-text-fill-color:transparent !important}}"
            # ---- 4. missões
            f"{c} .hg-ms{{position:relative;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px;padding:4px 8px 4px 4px;"
            "border-radius:16px;color:#fff;background:linear-gradient(100deg,rgba(70,36,140,.95),rgba(24,18,62,.95) 45%,rgba(18,16,50,.95));"
            "border:1.5px solid #6E5BC4;box-shadow:inset 0 1px 0 rgba(255,255,255,.14),0 0 18px -8px rgba(160,110,255,.9)}"
            f"{c} .hg-tr{{width:58px;height:60px;object-fit:cover;-webkit-mask:radial-gradient(ellipse at 50% 45%,#000 55%,transparent 72%);"
            "mask:radial-gradient(ellipse at 50% 45%,#000 55%,transparent 72%)}"
            f"{c} .hg-mc{{display:flex;flex-direction:column;gap:2px;min-width:0}}{c} .hg-mc *{{line-height:1.15}}"
            f"{c} .hg-mt{{font-size:clamp(.95rem,4.6vw,1.12rem);font-weight:900;letter-spacing:.01em}}"
            f"{c} .hg-mc small{{font-size:.68rem;font-weight:600;color:{lila};line-height:1.2}}"
            f"{c} .hg-mr{{display:flex;align-items:center;gap:8px;margin-top:3px}}"
            f"{c} .hg-mbar{{flex:1 1 auto;height:10px;border-radius:99px;background:rgba(0,0,0,.5);overflow:hidden;box-shadow:inset 0 1px 2px rgba(0,0,0,.6)}}"
            f"{c} .hg-mbar i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#7B3CFF,#C07BFF);box-shadow:0 0 10px #9B5CFF}}"
            f"{c} .hg-mr span{{font-size:.8rem;font-weight:800;white-space:nowrap}}"
            f"{c} .hg-cf{{display:flex;flex-direction:column;align-items:center;gap:0}}"
            f"{c} .hg-cf img{{width:52px;height:50px;object-fit:cover;-webkit-mask:radial-gradient(ellipse at 50% 50%,#000 58%,transparent 74%);"
            "mask:radial-gradient(ellipse at 50% 50%,#000 58%,transparent 74%)}"
            f"{c} .hg-cf b{{font-size:.8rem;font-weight:900;color:#FFD76A;white-space:nowrap;margin-top:-4px}}{c} .hg-cf b.ok{{color:#7CF0C0}}"
            # ---- 5. acessos: a mesma fileira de três (Carteira · JOGAR AGORA maior, no meio · Mercado), cada botão é a arte inteira
            f"{c} .st-key-hg_acessos{{display:grid !important;grid-template-columns:minmax(0,1fr) minmax(0,1.38fr) minmax(0,1fr);gap:0 !important;align-items:end}}"
            f"{c} .st-key-hg_acessos>*{{min-width:0}}"
            f"{c} .hg-bt{{position:relative;line-height:0}}"
            f"{c} .hg-bt img{{display:block;width:100%;height:auto}}"
            # bordas das artes dissolvidas no fundo da tela (o fundo da arte não é exatamente o da tela)
            f"{c} .hg-bt img{{-webkit-mask:linear-gradient(90deg,transparent,#000 7%,#000 93%,transparent),linear-gradient(180deg,transparent,#000 9%,#000 92%,transparent);"
            "-webkit-mask-composite:source-in;mask:linear-gradient(90deg,transparent,#000 7%,#000 93%,transparent),linear-gradient(180deg,transparent,#000 9%,#000 92%,transparent);"
            "mask-composite:intersect}"
            f"{c} .st-key-hg_acessos [class*='st-key-hg_ac_']:has(button:active) .hg-bt{{filter:brightness(1.15)}}"
            "@media (max-width:360px){"
            f"{c} .hg-lvt span{{display:none}}{c} .hg-pass{{min-width:80px;padding:5px 6px}}{c} .hg-lg{{width:52px;height:48px}}"
            f"{c} .hg-tk{{width:31%;padding:3px 5px}}{c} .hg-tk small{{display:none}}{c} .hg-tk.tl,{c} .hg-tk.tr{{top:-8px}}"
            f"{c} .hg-tr{{width:56px;height:60px}}{c} .hg-cf img{{width:50px;height:48px}}}}"
            f"{t}{{max-width:500px !important;margin-left:auto !important;margin-right:auto !important}}"
            "</style>")
