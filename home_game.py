"""Tela inicial no formato "mobile game" (só HTML/CSS e regras de apresentação; sem Streamlit, sem banco e sem rede).

Cada função recebe dados que o app já tem (XP, Ticker Coins, ranking, missões, cotações) e devolve HTML. Dado ausente vira estado vazio
("—", "sem cotações agora"), nunca um número inventado. A leitura dos dados fica em home_game_app.py, para a futura API reaproveitar este módulo.

Ordem da tela (cabe numa tela de celular): jogador, marca, pregão, missões do dia, três acessos (Carteira, Jogar agora, Mercado).
"""
from __future__ import annotations

import html

import game_ui as G

_E = html.escape
Q = G.Q


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


def _rotulo_curto(r: str) -> str:
    r = str(r or "")
    return "Medo" if r.startswith("Índice do medo") else r


# ------------------------------------------------------------------ A. cabeçalho do jogador
def html_jogador(nome: str, avatar_src: str, cor_anel: str, cor_anel2: str, nivel: dict | None, moedas, pos, total, moeda_html: str = "") -> str:
    """Avatar, nome, nível com barra de XP, saldo de Ticker Coins e posição no ranking, em um único cartão compacto."""
    if nivel:
        txt_nv = f"Nível {int(nivel['nivel'])} · {_E(str(nivel['titulo']))}"
        xp = (f"{int(nivel['xp'])} XP · máximo" if nivel.get("maximo") else f"{int(nivel['xp_no_nivel'])}/{int(nivel['xp_faixa'])} XP")
        bloco_xp = f"<span class='hg-nv'>{txt_nv}</span>{G.barra(100 * float(nivel.get('pct') or 0))}<span class='hg-xp'>{_E(xp)}</span>"
    else:
        bloco_xp = ""
    av = (f"<img src='{_E(avatar_src)}' alt='' loading='eager'>" if avatar_src else f"<span>{_E((nome[:1] or '?').upper())}</span>")
    rk_titulo = f"Você é o {int(pos)}º entre {int(total)} jogadores" if pos and total else ("Sua posição no ranking" if pos else "Sem posição no ranking ainda")
    rk = f"#{int(pos)}" if pos else "—"
    return (f"<div class='gu-card hg-jog' style=\"--ac:{G.ROXO};--bg:url('{G.fundo('jogador')}')\">"
            f"<div class='hg-av' style='--r1:{_E(cor_anel)};--r2:{_E(cor_anel2)}'>{av}</div>"
            f"<div class='hg-id'><b>{_E(nome or 'Jogador')}</b>{bloco_xp}</div>"
            f"<div class='hg-fichas'>"
            f"{G.ficha((moeda_html or '🪙') + '<b>' + fmt_inteiro(moedas) + '</b>', G.OURO, 'Seu saldo de Ticker Coins')}"
            f"{G.ficha(G.icone('trofeu', 18) + '<b>' + _E(rk) + '</b>', G.VERDE if pos else G.ROXO, rk_titulo)}"
            "</div></div>")


# ------------------------------------------------------------------ B. marca
def html_marca(mascote_html: str) -> str:
    return (f"<div class='gu-card hg-marca' style=\"--ac:{G.AZUL};--bg:url('{G.fundo('marca')}')\">"
            f"<div class='hg-mas'>{mascote_html}</div>"
            "<div class='hg-mt'><div class='hg-logo'>Ticker<span>Hunters</span></div>"
            "<div class='hg-tag'>Mercado. Competição. Evolução.</div></div></div>")


# ------------------------------------------------------------------ C. pregão (mercado como arena)
def _tile(it: dict) -> str:
    v = it.get("var")
    nota = it.get("nota")
    if nota:
        cor, chip = G.OURO, f"<i class='n'>{_E(nota)}</i>"
    elif v is None:
        cor, chip = G.ROXO, "<i class='n'>sem variação</i>"
    else:
        sobe = float(v) >= 0
        cor = G.VERDE if sobe else G.VERMELHO
        chip = f"<i class='{'u' if sobe else 'd'}'>{'▲' if sobe else '▼'} {_E(fmt_var(v))}</i>"
    valor = str(it.get("valor", ""))
    longo = " l" if len(valor) > 8 else ""            # valores longos (US$ 98.123) usam fonte menor para caber inteiros
    return (f"<div class='hg-tl{longo}' style='--c:{cor}'><span>{_E(_rotulo_curto(it.get('rotulo', '')))}</span>"
            f"<b>{_E(valor)}</b>{chip}</div>")


def html_pregao(itens: list | None) -> str:
    """Arena com compradores de um lado e vendedores do outro, e os indicadores que o app já busca (Ibovespa, dólar, Bitcoin, medo)."""
    itens = [i for i in (itens or []) if isinstance(i, dict) and i.get("valor")]
    corpo = ("".join(_tile(i) for i in itens) if itens
             else "<div class='hg-vz'>Sem cotações agora. Elas voltam assim que a fonte responder.</div>")
    n = max(3, min(len(itens), 4))                  # no mínimo 3 colunas: poucos indicadores não viram cartões gigantes
    return (f"<div class='gu-card hg-arena' style=\"--ac:{G.ROXO};--bg:url('{G.fundo('arena')}')\">"
            "<div class='hg-at'><span class='c'>▲ Compradores</span><b>Pregão</b><span class='v'>Vendedores ▼</span></div>"
            f"<div class='hg-mk' style='--n:{n}'>{corpo}</div></div>")


# ------------------------------------------------------------------ D. missões do dia
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
        rodape = "<span class='hg-pr'>Sem missões disponíveis agora.</span>"
    elif feitas >= total:
        rodape = f"<span class='hg-pr ok'>{G.icone('check', 18)}<em>Missões de hoje concluídas</em></span>"
    else:
        pts = (G.ficha(G.icone("estrela", 16) + f"<b>+{int(r['pontos'])} pts</b>", G.OURO, "Pontos que você ainda pode ganhar hoje") if r.get("pontos") else "")
        rodape = f"<span class='hg-pr'><em>{_E(str(r.get('proxima') or ''))}</em></span>{pts}"
    return (f"<div class='gu-card hg-miss' style=\"--ac:{G.OURO};--bg:url('{G.fundo('missoes')}')\">"
            f"<div class='hg-mh'>{G.icone('alvo', 26)}<b>Missões do dia</b><span class='hg-ver'>Ver todas ›</span></div>"
            f"<div class='hg-mb'>{G.segmentos(feitas, total)}<span class='hg-ct'><b>{feitas}</b>/{total}</span></div>"
            f"<div class='hg-mf'>{rodape}</div></div>")


# ------------------------------------------------------------------ E. acessos principais
ACESSOS = (
    # (chave, rótulo, subtítulo, ícone, cor, fundo, página de destino)
    ("carteira", "Carteira", "Seu patrimônio", "carteira", G.ROXO, "carteira", "competicao"),
    ("jogar", "Jogar agora", "Trade Battle\nTicker Battle", "jogar", "#FFC23D", "jogar", "jogos"),
    ("mercado", "Mercado", "Análises e ferramentas", "mercado", G.CIANO, "mercado", "analisar"),
)


def html_acesso(chave: str) -> str:
    _c, rot, sub, ic, cor, fnd, _d = next(a for a in ACESSOS if a[0] == chave)
    grande = " hg-grande" if chave == "jogar" else ""
    return (f"<div class='gu-card hg-ac{grande}' style=\"--ac:{cor};--bg:url('{G.fundo(fnd)}')\">"
            f"<span class='hg-ic'>{G.icone(ic, 44 if chave == 'jogar' else 36)}</span><b>{_E(rot)}</b><small>{_E(sub).replace(chr(10), "<br>")}</small></div>")


# ------------------------------------------------------------------ CSS da tela
def css() -> str:
    c = Q
    return ("<style>"
            # coluna da tela: espaços curtos entre os blocos
            f"{c} .st-key-hg_tela{{display:flex !important;flex-direction:column !important;gap:8px !important;margin-top:2px}}"
            f"{c} .st-key-hg_tela>*,{c} .st-key-hg_tela [data-testid='stElementContainer']{{flex:none !important;height:auto !important;min-height:0}}"
            f"{c} .st-key-hg_tela [data-testid='stElementContainer']{{margin:0 !important}}"
            f"{c} .st-key-hg_tela .gu-card{{flex:none}}"
            # o Streamlit dá margem inferior negativa (-1rem) aos blocos de Markdown: sem zerar, o contêiner encolhe 16 px e o cartão seguinte sobrepõe este
            f"{c} .st-key-hg_tela [data-testid='stMarkdownContainer']{{margin-bottom:0 !important}}"
            f"{c} .st-key-hg_tela .gu-card{{margin:0}}"
            # A. jogador
            f"{c} .hg-jog{{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:10px;padding:9px 10px}}"
            f"{c} .hg-av{{width:54px;height:54px;border-radius:50%;display:grid;place-items:center;background:#1B1545;font-weight:900;font-size:1.4rem;overflow:hidden;"
            "box-shadow:0 0 0 2.5px var(--r1),0 0 0 4px var(--r2),0 0 14px var(--r1)}"
            f"{c} .hg-av img{{width:100%;height:100%;object-fit:cover;display:block}}"
            f"{c} .hg-id{{min-width:0;display:flex;flex-direction:column;gap:2px}}"
            f"{c} .hg-id>b{{font-size:1rem;font-weight:900;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
            f"{c} .hg-nv{{font-size:.74rem;font-weight:800;color:#F2B84B;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
            f"{c} .hg-xp{{font-size:.66rem;font-weight:700;color:#D7D0FF;line-height:1}}"
            f"{c} .hg-fichas{{display:flex;flex-direction:column;gap:5px;align-items:stretch}}"
            f"{c} .hg-fichas .gu-chip{{justify-content:flex-start;font-size:.86rem;min-height:26px}}"
            f"{c} .hg-fichas .gu-chip img{{width:20px;height:20px}}"
            # B. marca
            f"{c} .hg-marca{{display:flex;align-items:center;gap:8px;padding:6px 12px 6px 6px;min-height:68px;overflow:visible;"
            "background:var(--bg) center/cover no-repeat,radial-gradient(circle at 12% 50%,rgba(60,110,255,.45),transparent 55%),linear-gradient(135deg,#142468,#1B1442 70%)}"
            f"{c} .hg-mas{{flex:0 0 auto;margin:-14px 0 -8px -2px;line-height:0}}{c} .hg-mas :is(img,svg){{width:78px !important;height:78px !important;filter:drop-shadow(0 6px 10px rgba(0,0,0,.5))}}"
            f"{c} .hg-mt{{min-width:0;flex:1 1 auto}}"
            f"{c} .hg-logo{{font-size:clamp(1.35rem,6.4vw,1.9rem);font-weight:900;font-style:italic;letter-spacing:-.03em;line-height:1.05;text-shadow:0 2px 0 rgba(0,0,0,.35)}}"
            f"{c} .hg-logo span{{color:#A8E10C;-webkit-text-fill-color:#A8E10C}}"
            f"{c} .hg-tag{{margin-top:3px;font-size:clamp(.72rem,3.2vw,.9rem);font-weight:700;color:#CFCBFF;line-height:1.15}}"
            f"{c} .hg-tag:after{{content:'';display:block;height:2px;width:58%;margin-top:4px;border-radius:2px;background:linear-gradient(90deg,#F2B84B,transparent)}}"
            # C. pregão
            f"{c} .hg-arena{{padding:8px 10px 10px}}"
            f"{c} .hg-at{{display:flex;align-items:center;justify-content:space-between;gap:6px;margin-bottom:7px}}"
            f"{c} .hg-at b{{font-size:1.02rem;font-weight:900;text-shadow:0 0 12px rgba(255,215,106,.7)}}"
            f"{c} .hg-at span{{font-size:.72rem;font-weight:800}}{c} .hg-at .c{{color:{G.VERDE};-webkit-text-fill-color:{G.VERDE}}}{c} .hg-at .v{{color:{G.VERMELHO};-webkit-text-fill-color:{G.VERMELHO}}}"
            f"{c} .hg-mk{{display:grid;grid-template-columns:repeat(var(--n,4),minmax(0,1fr));gap:6px}}"
            f"{c} .hg-tl{{display:flex;flex-direction:column;gap:1px;min-width:0;padding:5px 6px 6px;border-radius:12px;border:1.5px solid var(--c);"
            "background:rgba(7,5,28,.72);box-shadow:0 0 12px -6px var(--c)}"
            f"{c} .hg-tl span{{font-size:.64rem;font-weight:800;color:#CFCBFF;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
            f"{c} .hg-tl b{{font-size:clamp(.74rem,3.3vw,.92rem);font-weight:900;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
            f"{c} .hg-tl.l b{{font-size:clamp(.62rem,2.9vw,.76rem)}}"
            f"{c} .hg-tl i{{font-style:normal;font-size:.66rem;font-weight:900;white-space:nowrap}}"
            f"{c} .hg-tl i.u{{color:{G.VERDE};-webkit-text-fill-color:{G.VERDE}}}{c} .hg-tl i.d{{color:{G.VERMELHO};-webkit-text-fill-color:{G.VERMELHO}}}"
            f"{c} .hg-tl i.n{{color:#F2B84B;-webkit-text-fill-color:#F2B84B}}"
            f"{c} .hg-vz{{grid-column:1 / -1;font-size:.8rem;font-weight:600;color:#CFCBFF;padding:8px 4px}}"
            # D. missões
            f"{c} .hg-miss{{padding:9px 12px 10px;display:flex;flex-direction:column;gap:7px}}"
            f"{c} .hg-mh{{display:flex;align-items:center;gap:8px}}{c} .hg-mh b{{flex:1 1 auto;font-size:1.02rem;font-weight:900}}"
            f"{c} .hg-ver{{font-size:.74rem;font-weight:900;color:#1B1442;-webkit-text-fill-color:#1B1442;background:linear-gradient(180deg,#FFD76A,#F2B84B);"
            "padding:4px 10px;border-radius:99px;box-shadow:0 2px 0 #B96F00}"
            f"{c} .hg-mb{{display:flex;align-items:center;gap:10px}}"
            f"{c} .hg-ct{{font-size:.8rem;font-weight:800;color:#D7D0FF}}{c} .hg-ct b{{font-size:1.1rem;color:#FFD76A;-webkit-text-fill-color:#FFD76A}}"
            f"{c} .hg-mf{{display:flex;align-items:center;justify-content:space-between;gap:8px;min-height:26px}}"
            f"{c} .hg-pr{{min-width:0;display:flex;align-items:center;gap:6px;font-size:.8rem;font-weight:700;color:#E6E1FF}}"
            f"{c} .hg-pr em{{font-style:normal;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}{c} .hg-pr.ok{{color:#7CF0C0;-webkit-text-fill-color:#7CF0C0}}"
            f"{c} .hg-mf .gu-chip{{flex:0 0 auto;font-size:.78rem}}"
            # E. acessos
            f"{c} .st-key-hg_acessos{{display:grid !important;grid-template-columns:minmax(0,1fr) minmax(0,1.3fr) minmax(0,1fr);gap:8px !important;align-items:end}}"
            f"{c} .st-key-hg_acessos>*{{min-width:0}}"
            f"{c} .hg-ac{{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;text-align:center;padding:8px 4px 9px;min-height:98px}}"
            f"{c} .hg-ic{{display:block;line-height:0;margin-bottom:2px;filter:drop-shadow(0 4px 5px rgba(0,0,0,.5))}}"
            f"{c} .hg-ac b{{font-size:clamp(.88rem,3.8vw,1.05rem);font-weight:900;line-height:1.1}}"
            f"{c} .hg-ac small{{font-size:.64rem;font-weight:700;color:#CFCBFF;-webkit-text-fill-color:#CFCBFF;line-height:1.15;padding:0 2px}}"
            f"{c} .hg-grande{{min-height:116px;border-width:2px;"
            "background:var(--bg) center/cover no-repeat,linear-gradient(180deg,#FF9F1C,#C25A00 85%);"
            "box-shadow:0 5px 0 #8A3F00,0 0 24px -4px rgba(255,194,61,.75),inset 0 1px 0 rgba(255,255,255,.5)}"
            f"{c} .hg-grande b{{font-size:clamp(1rem,4.6vw,1.25rem);color:#fff;text-shadow:0 2px 0 rgba(90,40,0,.6)}}"
            f"{c} .hg-grande small{{color:#FFF1C9;-webkit-text-fill-color:#FFF1C9}}"
            "@media (max-width:340px){"
            f"{c} .hg-fichas .gu-chip{{font-size:.76rem}}{c} .hg-av{{width:46px;height:46px}}{c} .hg-tl span{{font-size:.58rem}}{c} .hg-tl.l b{{font-size:.56rem}}}}"
            "@media (min-width:700px){"
            f"{c} .st-key-hg_tela{{max-width:560px;margin-left:auto;margin-right:auto}}}}"
            "</style>")
