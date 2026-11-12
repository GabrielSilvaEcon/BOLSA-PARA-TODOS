"""Visual da Home (só texto HTML/CSS, sem Streamlit): nível e XP, Ranking Geral e Meu Desempenho. As regras vêm de home_dados.py."""
from __future__ import annotations

import html

import ativos_jogo as A
from wallet_game import moeda

_E = html.escape
OURO, PRATA, BRONZE = "#F2B84B", "#C7CEDB", "#CD7F32"
_COR_POS = {1: OURO, 2: PRATA, 3: BRONZE}
VERDE, VERMELHO = "#3DDC97", "#FF5B6E"


def _pct(v, sinal: bool = True) -> str:
    try:
        x = float(v)
    except (TypeError, ValueError):
        return "—"
    s = f"{abs(x):.1f}".replace(".", ",")
    return (("+" if x >= 0 else "−") if sinal else "") + s + "%"


def _ret_ranking(v) -> str:
    """O ranking guarda o retorno como fração (0,042 = 4,2%)."""
    try:
        return _pct(float(v) * 100.0)
    except (TypeError, ValueError):
        return "—"


# ------------------------------------------------------------------ nível e XP (cartão principal)
def html_nivel(est: dict | None) -> str:
    """Selo de nível com barra de XP. `est` = nivel.estado(xp). Sem dado, não desenha nada."""
    if not est:
        return ""
    if est.get("maximo"):
        faixa = f"{est['xp']} XP · nível máximo"
    else:
        faixa = f"{est['xp_no_nivel']} / {est['xp_faixa']} XP"
    pct = int(round(100 * float(est.get("pct") or 0)))
    return (f"<div class='hm-niv'><div class='hm-niv-n'>Nível {est['nivel']}</div><div class='hm-niv-t'>{_E(str(est['titulo']))}</div>"
            f"<div class='hm-niv-b'><i style='width:{pct}%'></i></div><div class='hm-niv-x'>{_E(faixa)}</div></div>")


# ------------------------------------------------------------------ ranking geral
def _chip_top(x: dict) -> str:
    cor = _COR_POS.get(x["pos"], "#8B6CFF")
    ini = _E((x["apelido"][:1] or "?").upper())
    return (f"<div class='hm-rk' style='--c:{cor}'><span class='hm-med'>{x['pos']}</span><span class='hm-av'>{ini}</span>"
            f"<span class='hm-rk-t'><b>{_E(x['apelido'][:14])}</b><em>{_ret_ranking(x.get('ret'))}</em></span></div>")


_CAB = ("<div class='hm-cab'><span class='hm-ico'>🏆</span><span><b>Ranking Geral</b><small>Veja sua posição e os líderes</small></span></div>")


def html_ranking_cab() -> str:
    return _CAB


def html_ranking_corpo(r: dict, logado: bool, participa: bool) -> str:
    """Fichas dos líderes e a sua, ou o estado vazio. r = home_dados.ranking_resumo(...)."""
    if r.get("vazio"):
        msg = ("O ranking aparece no primeiro fechamento de mercado com participantes. Ele é atualizado nos dias úteis, depois do fechamento."
               if participa else "O ranking compara o retorno em % de quem joga a Wallet Game. Entre no jogo para disputar uma posição.")
        return f"<div class='hm-vazio'>{_E(msg)}</div>"
    chips = "".join(_chip_top(x) for x in r["top"])
    eu = r.get("eu")
    if eu:
        extra = (f"<div class='hm-rk hm-eu'><span class='hm-med'>{eu['pos']}º</span><span class='hm-av'>★</span>"
                 f"<span class='hm-rk-t'><b>Você</b><em>{_ret_ranking(eu.get('ret')) if eu.get('ret') is not None else ''}"
                 f"{(' · de ' + str(r['total'])) if r.get('total') else ''}</em></span></div>")
    elif logado and not participa:
        extra = "<div class='hm-rk hm-eu hm-eu-v'><span class='hm-rk-t'><b>Você ainda não está no jogo</b><em>Entre para ter posição</em></span></div>"
    elif participa:
        extra = "<div class='hm-rk hm-eu hm-eu-v'><span class='hm-rk-t'><b>Sua posição</b><em>Aparece no próximo fechamento</em></span></div>"
    else:
        extra = "<div class='hm-rk hm-eu hm-eu-v'><span class='hm-rk-t'><b>Entre para jogar</b><em>E apareça no ranking</em></span></div>"
    return f"<div class='hm-rk-grid'>{chips}{extra}</div>"


def html_ranking(r: dict, logado: bool, participa: bool) -> str:
    """Cartão completo (usado nos testes e como alternativa sem botão)."""
    return f"<div class='hm-card hm-ranking'>{_CAB}{html_ranking_corpo(r, logado, participa)}</div>"


# ------------------------------------------------------------------ desempenho da carteira
def _linha(x: dict, positivo: bool) -> str:
    cl = A.CLASSES.get(x.get("classe")) or {"cor": "#8B6CFF", "icone": "•"}
    cor = VERDE if positivo else VERMELHO
    seta = "↑" if positivo else "↓"
    res = x.get("resultado")
    sub = f"{'+' if (res or 0) >= 0 else '−'}{moeda(abs(res)).replace('T$ ', 'T$ ')}" if res is not None else ""
    return (f"<div class='hm-ln'><span class='hm-ic' style='--c:{_E(cl['cor'])}'>{_E(cl['icone'])}</span>"
            f"<span class='hm-ln-t'><b>{_E(x['sigla'])}</b><em>{_E(x['nome'])}</em></span>"
            f"<span class='hm-ln-v' style='--v:{cor}'><b>{seta} {_pct(x['pct'])}</b><small>{_E(sub)}</small></span></div>")


def _vazio_perf(msg: str) -> str:
    return f"<div class='hm-vazio'>{_E(msg)}</div>"


def html_altas(d: dict) -> str:
    corpo = "".join(_linha(x, True) for x in d["altas"]) or _vazio_perf(
        "Sem ativos em alta na carteira." if not d["vazio"] else "Compre seu primeiro ativo para acompanhar o desempenho.")
    return f"<div class='hm-card hm-alta'><div class='hm-tit'><span>📈</span><b>Maiores altas</b></div>{corpo}</div>"


def html_quedas(d: dict) -> str:
    corpo = "".join(_linha(x, False) for x in d["quedas"]) or _vazio_perf(
        "Nenhum ativo em queda na carteira." if not d["vazio"] else "Compre seu primeiro ativo para acompanhar o desempenho.")
    return f"<div class='hm-card hm-queda'><div class='hm-tit'><span>📉</span><b>Maiores quedas</b></div>{corpo}</div>"


def html_mais_rentavel(d: dict) -> str:
    m = d.get("mais_rentavel")
    if not m:
        msg = "Ainda não há ativo com resultado positivo." if not d["vazio"] else "Compre seu primeiro ativo para ver quem mais rende."
        return f"<div class='hm-card hm-top'><div class='hm-tit'><span>🥇</span><b>Mais rentável (total)</b></div>{_vazio_perf(msg)}</div>"
    cl = A.CLASSES.get(m.get("classe")) or {"cor": "#8B6CFF", "icone": "•"}
    pct = f"<small>{_pct(m['pct'])} no ativo</small>" if m.get("pct") is not None else "<small>já realizado em vendas</small>"
    return (f"<div class='hm-card hm-top'><div class='hm-tit'><span>🥇</span><b>Mais rentável (total)</b></div>"
            f"<div class='hm-ln'><span class='hm-ic' style='--c:{_E(cl['cor'])}'>{_E(cl['icone'])}</span>"
            f"<span class='hm-ln-t'><b>{_E(m['sigla'])}</b><em>{_E(m['nome'])}</em></span>"
            f"<span class='hm-ln-v' style='--v:{OURO}'><b>+{_E(moeda(m['resultado']))}</b>{pct}</span></div></div>")


def html_titulo_desempenho(criterio: str) -> str:
    return (f"<div class='hm-sec'><b>Meu Desempenho</b><small>Meus melhores e piores ativos · {_E(criterio.lower())}</small></div>")


# ------------------------------------------------------------------ estilo
def css() -> str:
    q = "html body .stApp.stApp"
    return (f"<style>"
            f"{q} .hm-card{{border-radius:22px;padding:12px 14px;margin:0 0 10px;border:1.5px solid rgba(139,108,255,.5);"
            "background:linear-gradient(160deg,#241C5A,#140E36 80%);box-shadow:0 8px 22px rgba(2,6,23,.45),inset 0 0 0 1px rgba(255,255,255,.04)}"
            f"{q} .hm-ranking{{border-color:rgba(242,184,75,.55);background:radial-gradient(circle at 12% 0%,rgba(242,184,75,.16),transparent 55%),linear-gradient(160deg,#1E2E5C,#12113A 80%)}}"
            f"{q} .hm-alta{{border-color:rgba(61,220,151,.55);background:radial-gradient(circle at 0% 0%,rgba(61,220,151,.16),transparent 55%),linear-gradient(160deg,#143A3A,#0F1A34 80%)}}"
            f"{q} .hm-queda{{border-color:rgba(255,91,110,.55);background:radial-gradient(circle at 0% 0%,rgba(255,91,110,.16),transparent 55%),linear-gradient(160deg,#3A1A3A,#170F34 80%)}}"
            f"{q} .hm-top{{border-color:rgba(242,184,75,.55);background:radial-gradient(circle at 0% 0%,rgba(242,184,75,.16),transparent 55%),linear-gradient(160deg,#3A3014,#17112F 80%)}}"
            f"{q} .hm-cab{{display:flex;align-items:center;gap:10px;margin-bottom:8px}}{q} .hm-ico{{font-size:1.9rem;filter:drop-shadow(0 0 8px rgba(242,184,75,.6))}}"
            f"{q} .hm-cab b{{display:block;color:#fff;font-size:1.15rem;font-weight:900}}{q} .hm-cab small{{display:block;color:#C9C2F2;font-size:.8rem}}"
            f"{q} .hm-rk-grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px}}"
            f"{q} .hm-rk{{display:flex;align-items:center;gap:7px;min-width:0;padding:7px 9px;border-radius:14px;border:1.5px solid var(--c);background:rgba(8,6,30,.55)}}"
            f"{q} .hm-med{{flex:0 0 auto;min-width:24px;height:24px;border-radius:50%;display:grid;place-items:center;background:var(--c);color:#1B1030;font-weight:900;font-size:.78rem;padding:0 3px}}"
            f"{q} .hm-av{{flex:0 0 30px;height:30px;border-radius:50%;display:grid;place-items:center;background:rgba(255,255,255,.12);color:#fff;font-weight:900;border:1.5px solid var(--c)}}"
            f"{q} .hm-rk-t{{min-width:0;display:flex;flex-direction:column;line-height:1.15}}"
            f"{q} .hm-rk-t b{{color:#fff;font-size:.86rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}{q} .hm-rk-t em{{font-style:normal;color:var(--c);font-weight:800;font-size:.78rem}}"
            f"{q} .hm-eu{{--c:{VERDE};background:rgba(61,220,151,.14);box-shadow:0 0 14px rgba(61,220,151,.35)}}{q} .hm-eu .hm-med{{color:#06281A}}"
            f"{q} .hm-eu-v{{box-shadow:none}}{q} .hm-eu-v .hm-rk-t em{{color:#B8F5DC}}"
            f"{q} .hm-vazio{{color:#C9C2F2;font-size:.84rem;line-height:1.35;padding:8px 2px}}"
            f"{q} .hm-sec{{margin:14px 2px 8px}}{q} .hm-sec b{{display:block;color:#fff;font-size:1.2rem;font-weight:900}}{q} .hm-sec small{{color:#C9C2F2;font-size:.78rem}}"
            f"{q} .hm-tit{{display:flex;align-items:center;gap:8px;margin-bottom:6px;font-size:1.1rem}}{q} .hm-tit b{{color:#fff;font-weight:900}}"
            f"{q} .hm-ln{{display:flex;align-items:center;gap:9px;padding:7px 9px;margin-top:6px;border-radius:14px;background:rgba(8,6,30,.5);border:1px solid rgba(255,255,255,.1)}}"
            f"{q} .hm-ic{{flex:0 0 34px;height:34px;border-radius:11px;display:grid;place-items:center;font-size:1.05rem;background:color-mix(in srgb,var(--c) 38%,#120C30);border:1.5px solid var(--c)}}"
            f"{q} .hm-ln-t{{flex:1 1 auto;min-width:0;display:flex;flex-direction:column;line-height:1.15}}"
            f"{q} .hm-ln-t b{{color:#fff;font-size:.95rem}}{q} .hm-ln-t em{{font-style:normal;color:#BDB5E6;font-size:.76rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}"
            f"{q} .hm-ln-v{{flex:0 0 auto;text-align:right;display:flex;flex-direction:column;line-height:1.15}}"
            f"{q} .hm-ln-v b{{color:var(--v);font-size:.92rem;font-weight:900;white-space:nowrap}}{q} .hm-ln-v small{{color:#C9C2F2;font-size:.72rem;white-space:nowrap}}"
            f"{q} .hm-niv{{text-align:center;padding:8px 10px;border-radius:18px;border:1.5px solid rgba(242,184,75,.6);background:rgba(8,6,30,.45);min-width:128px}}"
            f"{q} .hm-niv-n{{color:{OURO};font-weight:900;font-size:1.15rem}}{q} .hm-niv-t{{color:#fff;font-weight:800;font-size:.72rem;line-height:1.2}}"
            f"{q} .hm-niv-b{{height:9px;border-radius:99px;background:rgba(255,255,255,.14);margin:6px 0 3px;overflow:hidden}}"
            f"{q} .hm-niv-b i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#8B6CFF,#3DDC97)}}"
            f"{q} .hm-niv-x{{color:#E6E1FF;font-weight:800;font-size:.72rem}}"
            "</style>")


def css_layout() -> str:
    q = "html body .stApp.stApp.stApp"
    return ("<style>"
            # cartão principal: mascote | texto | nível, e os três botões embaixo
            f"{q} .st-key-hm_hero{{display:grid !important;grid-template-columns:minmax(0,31%) minmax(0,1fr) minmax(0,auto);grid-template-rows:auto auto;column-gap:8px !important;row-gap:8px !important;"
            "padding:10px 12px 12px 6px !important;border-radius:26px;align-items:center;margin:6px 0 12px;"
            "background:radial-gradient(circle at 12% 40%,rgba(60,110,255,.45),transparent 55%),linear-gradient(135deg,#0F3A3A,#1B1442 70%);"
            "border:1px solid rgba(120,150,255,.55);box-shadow:0 0 28px -8px rgba(80,120,255,.6)}"
            f"{q} .st-key-hm_hero>[data-testid='stElementContainer'],{q} .st-key-hm_hero>.st-key-hm_hero_b{{min-width:0;width:100% !important}}"
            f"{q} .st-key-hm_hero>[data-testid='stElementContainer']:nth-child(1){{grid-column:1;grid-row:1}}"
            f"{q} .st-key-hm_hero>[data-testid='stElementContainer']:nth-child(2){{grid-column:2;grid-row:1}}"
            f"{q} .st-key-hm_hero>[data-testid='stElementContainer']:nth-child(3){{grid-column:3;grid-row:1}}"
            f"{q} .st-key-hm_hero>.st-key-hm_hero_b{{grid-column:1 / -1;grid-row:2}}"
            f"{q} .st-key-hm_hero .hh-mas{{margin:-14px 0 -10px -4px}}{q} .st-key-hm_hero .hh-mas :is(img,svg){{width:clamp(96px,26vw,190px) !important}}"
            f"{q} .st-key-hm_hero .hh-txt{{padding-bottom:0}}{q} .st-key-hm_hero .hh-b{{font-size:clamp(.85rem,3vw,1.3rem)}}"
            f"{q} .st-key-hm_hero .hh-t{{font-size:clamp(1.15rem,4.6vw,2.1rem)}}{q} .st-key-hm_hero .hh-l{{font-size:clamp(.7rem,2.5vw,1rem)}}"
            f"{q} .st-key-hm_hero .hm-niv{{min-width:0;width:clamp(96px,22vw,170px)}}"
            # três botões
            f"{q} .st-key-hm_hero_b{{display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr)) !important;gap:8px !important}}"
            f"{q} .st-key-hm_hero_b>[data-testid='stElementContainer']{{width:100% !important;min-width:0}}"
            f"{q} .st-key-hm_hero_b button{{width:100% !important;min-height:58px !important;height:auto !important;padding:6px 8px !important;border-radius:18px !important;"
            "display:flex !important;align-items:center !important;justify-content:flex-start !important;gap:6px !important;text-align:left !important;"
            "background:linear-gradient(135deg,color-mix(in srgb,var(--ac) 22%,#14123F),#120F38 80%) !important;border:1.5px solid var(--ac) !important;"
            "box-shadow:0 3px 0 color-mix(in srgb,var(--ac) 35%,#0B0821),0 0 14px -6px var(--ac) !important}"
            f"{q} .st-key-hm_hero_b button [data-testid='stIconMaterial']{{color:var(--ac) !important;font-size:1.7rem !important;flex:0 0 auto}}"
            f"{q} .st-key-hm_hero_b button p{{margin:0 !important;color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:900 !important;font-size:clamp(.85rem,2.6vw,1.05rem) !important;line-height:1.1 !important;text-align:left !important}}"
            f"{q} .st-key-hm_hero_b button p:after{{content:var(--sub);display:block;font-weight:600;font-size:clamp(.6rem,1.9vw,.76rem);color:#CFCBFF;-webkit-text-fill-color:#CFCBFF;margin-top:1px}}"
            f"{q} .st-key-hm_b_missoes{{--ac:#F2B84B;--sub:'Desafios diários'}}{q} .st-key-hm_b_aprender{{--ac:#2BA7C9;--sub:'Conteúdos e trilhas'}}{q} .st-key-hm_b_jogar{{--ac:#3DDC97;--sub:'Wallet Game'}}"
            # ranking: título e botão na mesma linha, fichas em uma linha só
            f"{q} .st-key-hm_rk{{display:grid !important;grid-template-columns:minmax(0,1fr) auto;column-gap:10px !important;row-gap:6px !important;align-items:center;padding:12px 14px !important;"
            "border-radius:22px;border:1.5px solid rgba(242,184,75,.55);margin:0 0 12px;background:radial-gradient(circle at 12% 0%,rgba(242,184,75,.16),transparent 55%),linear-gradient(160deg,#1E2E5C,#12113A 80%);box-shadow:0 8px 22px rgba(2,6,23,.45)}"
            f"{q} .st-key-hm_rk>[data-testid='stElementContainer']{{min-width:0}}"
            f"{q} .st-key-hm_rk>[data-testid='stElementContainer']:nth-child(1){{grid-column:1;grid-row:1}}"
            f"{q} .st-key-hm_rk>[data-testid='stElementContainer']:nth-child(2){{grid-column:2;grid-row:1}}"
            f"{q} .st-key-hm_rk>[data-testid='stElementContainer']:nth-child(3){{grid-column:1 / -1;grid-row:2}}"
            f"{q} .st-key-hm_rk .hm-cab{{margin:0}}"
            f"{q} .st-key-hm_rk button{{min-height:38px !important;padding:2px 12px !important;border-radius:999px !important;background:rgba(8,6,30,.5) !important;border:1.5px solid #3DDC97 !important}}"
            f"{q} .st-key-hm_rk button p{{color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important;font-weight:800 !important;font-size:.82rem !important;white-space:nowrap}}"
            f"{q} .st-key-hm_rk .hm-rk-grid{{grid-template-columns:repeat(4,minmax(0,1fr))}}"
            "@media (max-width:520px){"
            f"{q} .st-key-hm_rk .hm-rk-grid{{grid-template-columns:repeat(2,minmax(0,1fr))}}{q} .st-key-hm_rk button{{padding:2px 8px !important}}"
            f"{q} .st-key-hm_rk button p{{font-size:.72rem !important}}}}"
            # desempenho: altas e quedas lado a lado, mais rentável embaixo
            f"{q} .st-key-hm_perf{{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr)) !important;column-gap:10px !important;row-gap:0 !important}}"
            f"{q} .st-key-hm_perf>[data-testid='stElementContainer']{{min-width:0;width:100% !important}}"
            f"{q} .st-key-hm_perf>[data-testid='stElementContainer']:nth-child(1),{q} .st-key-hm_perf>[data-testid='stElementContainer']:nth-child(n+4){{grid-column:1 / -1}}"
            f"{q} .st-key-hm_perf .hm-card{{height:calc(100% - 10px)}}"
            "@media (max-width:560px){"
            f"{q} .st-key-hm_perf{{grid-template-columns:minmax(0,1fr) !important}}{q} .st-key-hm_perf>[data-testid='stElementContainer']{{grid-column:1 / -1}}}}"
            "</style>")
