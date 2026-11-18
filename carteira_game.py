"""Carteira no formato mobile game (só HTML/CSS; sem Streamlit, sem banco e sem rede).

Layout da referência do TickerHunters (nov/2026):
  1. Topo com o mascote e a sua ficha (o mesmo do Ranking)
  2. Cartão "Carteira": título, frase e o valor total (T$) com a variação desde o último fechamento
  3. Disponível · Investido · Resultado desde o início
  4. Abas por categoria (Todos, Ações, FIIs, Cripto, ETFs, Fundos, Renda fixa), cada uma com quantos ativos você tem
  5. Grade de cartões dos ativos: logo, código, nome, quantidade, valor, resultado e o peso na carteira

Tudo vem do que a Wallet Game já calcula (carteira_visual.posicoes, competicao.patrimonio). Sem dado, estado vazio; nada inventado.
Em vez do "nível" do mockup (que não existe no jogo), a barra de baixo de cada cartão mostra o peso do ativo na carteira.
"""
from __future__ import annotations

import html

import ativos_jogo as A
from wallet_game import moeda

_E = html.escape
Q = "html body .stApp.stApp.stApp"
ARTE = "app/static/carteira/"

ABAS = (  # (chave, rótulo, classes, arte do ícone ou emoji)
    ("todos", "Todos", None, "valor"),
    ("acao", "Ações", ("acao",), "acoes"),
    ("fii", "FIIs", ("fii",), "🏢"),
    ("cripto", "Cripto", ("cripto",), "cripto"),
    ("etf", "ETFs", ("etf",), "etf"),
    ("fundo", "Fundos", ("fundo",), "fundo"),
    ("rf", "Renda fixa", ("rf",), "🏦"),
)
ORDENS = ("Maior valor", "Melhor resultado", "Pior resultado", "Nome")
_UNID = {"acao": "ações", "fii": "cotas", "etf": "cotas", "fundo": "cotas", "rf": "títulos", "cripto": "un."}
_COR = {"acao": "#3DA9FF", "fii": "#2EE5D0", "etf": "#B06BFF", "cripto": "#FFB020", "fundo": "#3DDC6A", "rf": "#8BA6FF"}


def arte(nome: str) -> str:
    return f"{ARTE}{nome}.webp"


def _icone(ic: str, alt: str = "") -> str:
    return f"<img src='{arte(ic)}' alt='{_E(alt)}'>" if ic.isascii() else f"<span class='cg-emo'>{ic}</span>"


def pct(v, casas: int = 2) -> str:
    if v is None:
        return "—"
    s = f"{float(v):+.{casas}f}%".replace(".", ",")
    return s.replace("-", "−")


def _cls(v) -> str:
    return "" if v is None or abs(float(v)) < 0.005 else ("u" if v > 0 else "d")


def filtrar(pos: list[dict], aba: str) -> list[dict]:
    cl = next((a[2] for a in ABAS if a[0] == aba), None)
    return list(pos) if not cl else [r for r in pos if r.get("classe") in cl]


def contar(pos: list[dict]) -> dict[str, int]:
    return {a[0]: len(filtrar(pos, a[0])) for a in ABAS}


def ordenar(pos: list[dict], ordem: str) -> list[dict]:
    if ordem == "Melhor resultado":
        return sorted(pos, key=lambda r: -float(r.get("res") or 0))
    if ordem == "Pior resultado":
        return sorted(pos, key=lambda r: float(r.get("res") or 0))
    if ordem == "Nome":
        return sorted(pos, key=lambda r: str(r.get("tk") or ""))
    return sorted(pos, key=lambda r: -float(r.get("valor") or 0))


# ------------------------------------------------------------------ 2. cartão Carteira · 3. resumo
def html_cab(pat: float, var_dia, n_pos: int) -> str:
    seta = "" if _cls(var_dia) == "" else ("▲" if var_dia > 0 else "▼")
    delta = (f"<span class='cg-dl {_cls(var_dia)}'>{seta} {_E(pct(var_dia))} <i>(último fechamento)</i></span>" if var_dia is not None
             else "<span class='cg-dl'><i>variação após o 1º fechamento</i></span>")
    frase = "Seus ativos, seu poder!" if n_pos else "Monte sua carteira: toque em Comprar!"
    return ("<div class='cg-cab'>"
            f"<div class='cg-ic'>{_icone('carteira')}</div>"
            f"<div class='cg-t'><b>Carteira</b><span>{_E(frase)}</span></div>"
            f"<div class='cg-vt'><small>Valor total</small><b>{_E(moeda(pat))}</b>{delta}</div>"
            "</div>")


def html_resumo(caixa: float, inv: float, ret) -> str:
    def item(rot, val, extra=""):
        return f"<div class='cg-r'><small>{_E(rot)}</small><b{extra}>{_E(val)}</b></div>"
    return ("<div class='cg-res'>" + item("Disponível", moeda(caixa, 0 if caixa >= 1000 else 2)) + item("Investido", moeda(inv, 0 if inv >= 1000 else 2))
            + item("Resultado", pct(None if ret is None else ret * 100), f" class='{_cls(None if ret is None else ret * 100)}'") + "</div>")


# ------------------------------------------------------------------ 4. abas
def html_aba(chave: str, n: int, ativa: bool) -> str:
    _c, rot, _cl, ic = next(a for a in ABAS if a[0] == chave)
    return (f"<div class='cg-aba{' on' if ativa else ''}'><i class='cg-n'>{int(n)}</i>{_icone(ic)}<b>{_E(rot)}</b></div>")


# ------------------------------------------------------------------ 5. cartões
def html_cartao(r: dict, icone_src: str = "") -> str:
    c = r.get("classe") or "acao"
    cor = _COR.get(c, "#8B6CFF")
    rot = A.rotulo(r["tk"])
    codigo = rot.split(" · ")[-1] if " · " in rot else rot
    nome = rot.split(" · ")[0] if " · " in rot else (A.CLASSES.get(c) or {}).get("singular", "")
    ic = (f"<img src='{_E(icone_src)}' alt=''>" if icone_src
          else f"<span class='cg-emo'>{(A.CLASSES.get(c) or {}).get('icone', '•')}</span>")
    res = r.get("res")
    seta = "" if _cls(res) == "" else ("▲" if res > 0 else "▼")
    peso = max(0.0, min(100.0, float(r.get("peso") or 0)))
    return (f"<div class='cg-card' style='--c:{cor}'>"
            f"<div class='cg-logo'>{ic}</div>"
            f"<b class='cg-cod'>{_E(codigo)}</b><span class='cg-nome'>{_E(nome)}</span>"
            f"<span class='cg-q'>{_E(A.texto_qtd(r['tk'], r['q']))} {_UNID.get(c, 'un.')}</span>"
            f"<b class='cg-v'>{_E(moeda(r['valor']))}</b>"
            f"<span class='cg-p {_cls(res)}'>{seta} {_E(pct(res))}</span>"
            f"<div class='cg-peso'><span>Peso</span><i><u style='width:{peso:.0f}%'></u></i><span>{peso:.0f}%</span></div>"
            "</div>")


def html_vazio(aba: str) -> str:
    if aba == "todos":
        return "<div class='cg-vz'>Nenhum ativo ainda. Todo o seu capital está disponível: toque em <b>Comprar</b> para começar.</div>"
    rot = next(a[1] for a in ABAS if a[0] == aba)
    return f"<div class='cg-vz'>Você ainda não tem {_E(rot)}. Toque em <b>Comprar</b> para escolher.</div>"


# ------------------------------------------------------------------ CSS
def css() -> str:
    c = Q
    br = "color:#F4F6FF !important;-webkit-text-fill-color:#F4F6FF !important"
    li = "color:#C9C2F2 !important;-webkit-text-fill-color:#C9C2F2 !important"
    verde = "color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important"
    verm = "color:#FF5B6E !important;-webkit-text-fill-color:#FF5B6E !important"
    return ("<style>"
            f"{c} .st-key-cg_tela{{max-width:520px !important;margin:0 auto !important;gap:8px !important}}"
            f"{c} .st-key-cg_tela [data-testid='stElementContainer'],{c} .st-key-cg_tela [data-testid='stMarkdownContainer']{{margin-bottom:0 !important}}"
            f"{c} :is(.cg-dl,.cg-p,.cg-r b).u{{{verde}}}{c} :is(.cg-dl,.cg-p,.cg-r b).d{{{verm}}}"
            # 2. cabeçalho
            f"{c} .cg-cab{{display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:8px;padding:8px 10px;border-radius:16px;"
            "background:linear-gradient(160deg,#1C2070,#0F1240);border:1.5px solid #4A5BD0;box-shadow:inset 0 1px 0 rgba(255,255,255,.12),0 0 16px -6px #4A5BD0}"
            f"{c} .cg-ic{{width:50px;height:50px;border-radius:50%;display:grid;place-items:center;background:radial-gradient(circle,#1E3A7A,#0B1236);border:1.5px solid #3DDC97}}"
            f"{c} .cg-ic img{{width:40px;height:40px;object-fit:contain}}"
            f"{c} .cg-t{{display:flex;flex-direction:column;min-width:0;line-height:1.1}}"
            f"{c} .cg-t b{{font-size:clamp(1.2rem,6vw,1.5rem);font-weight:900;{br}}}{c} .cg-t span{{font-size:.7rem;font-weight:700;{li}}}"
            f"{c} .cg-vt{{display:flex;flex-direction:column;align-items:flex-end;text-align:right;padding:5px 9px;border-radius:12px;background:rgba(8,10,40,.7);"
            "border:1px solid #3A4FB0;line-height:1.15}"
            f"{c} .cg-vt small{{font-size:.6rem;font-weight:700;{li}}}{c} .cg-vt b{{font-size:clamp(.86rem,4vw,1.02rem);font-weight:900;white-space:nowrap;{br}}}"
            f"{c} .cg-dl{{font-size:.64rem;font-weight:900;white-space:nowrap;{li}}}{c} .cg-dl i{{font-style:normal;font-weight:700;opacity:.8}}"
            # 3. resumo
            f"{c} .cg-res{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}}"
            f"{c} .cg-r{{display:flex;flex-direction:column;align-items:center;padding:5px 4px;border-radius:12px;background:linear-gradient(180deg,#1C2366,#121646);"
            "border:1px solid #2B3A8C;line-height:1.2}"
            f"{c} .cg-r small{{font-size:.6rem;font-weight:700;{li}}}{c} .cg-r b{{font-size:.84rem;font-weight:900;white-space:nowrap;{br}}}"
            # 4. abas (fileira que rola de lado; cada uma com o número de ativos)
            f"{c} .st-key-cg_abas{{display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;gap:6px !important;overflow-x:auto;"
            "padding:8px 2px 4px;scrollbar-width:none;-webkit-overflow-scrolling:touch}"
            f"{c} .st-key-cg_abas::-webkit-scrollbar{{display:none}}"
            f"{c} .st-key-cg_abas>*{{flex:0 0 calc((100% - 18px) / 4) !important;min-width:74px}}"
            f"{c} .cg-aba{{position:relative;height:58px;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;"
            "border-radius:12px;background:linear-gradient(180deg,#1C2366,#121646);border:1.5px solid #2B3A8C}"
            f"{c} .cg-aba img{{height:24px;width:auto}}{c} .cg-aba .cg-emo{{font-size:1.2rem;line-height:1}}"
            f"{c} .cg-aba b{{font-size:.72rem;font-weight:900;white-space:nowrap;{br}}}"
            f"{c} .cg-aba.on{{background:linear-gradient(180deg,#4A2FB0,#25157A);border:2px solid #B06BFF;box-shadow:0 0 14px -2px #B06BFF}}"
            f"{c} .cg-n{{position:absolute;top:-7px;left:-3px;min-width:20px;height:20px;padding:0 4px;box-sizing:border-box;display:grid;place-items:center;"
            "font-style:normal;font-size:.66rem;font-weight:900;color:#2A1800 !important;-webkit-text-fill-color:#2A1800 !important;"
            "background:linear-gradient(180deg,#FFE27A,#E9A80C);clip-path:polygon(25% 0,75% 0,100% 50%,75% 100%,25% 100%,0 50%)}"
            f"{c} .cg-aba:not(.on) .cg-n{{background:linear-gradient(180deg,#8B8FFF,#4A4FB0);color:#fff !important;-webkit-text-fill-color:#fff !important}}"
            # barra Meus Ativos + Ordenar
            f"{c} .st-key-cg_barra{{display:grid !important;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:6px !important;align-items:center}}"
            f"{c} .st-key-cg_barra>*{{min-width:0}}"
            f"{c} .cg-ma{{height:38px;display:flex;align-items:center;gap:8px;padding:0 12px;border-radius:12px;background:#121646;border:1.5px solid #3A4FB0;"
            f"font-size:.86rem;font-weight:900;{br}}}"
            f"{c} .st-key-cg_barra [data-baseweb='select']>div{{min-height:38px !important;border-radius:12px !important;background:#121646 !important;border:1.5px solid #3A4FB0 !important}}"
            # 5. grade de cartões
            f"{c} .st-key-cg_grade{{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px !important}}"
            f"{c} .st-key-cg_grade>*{{min-width:0}}"
            f"{c} .st-key-cg_grade>:has(.cg-vz){{grid-column:1 / -1}}"
            f"{c} .cg-card{{position:relative;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;text-align:center;gap:1px;padding:8px 7px 7px;"
            "border-radius:14px;background:linear-gradient(170deg,color-mix(in srgb,var(--c) 22%,#141A5A),#0E1140 70%);border:2px solid var(--c);"
            "box-shadow:0 0 14px -5px var(--c),inset 0 1px 0 rgba(255,255,255,.14)}"
            f"{c} .cg-logo{{width:40px;height:40px;border-radius:12px;display:grid;place-items:center;background:rgba(255,255,255,.08);margin-bottom:2px}}"
            f"{c} .cg-logo img{{width:32px;height:32px;object-fit:contain}}{c} .cg-logo .cg-emo{{font-size:1.4rem}}"
            f"{c} .cg-cod{{font-size:.92rem;font-weight:900;line-height:1.1;{br}}}"
            f"{c} .cg-nome{{font-size:.62rem;font-weight:700;line-height:1.15;max-width:100%;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;{li}}}"
            f"{c} .cg-q{{margin:3px 0 1px;padding:1px 8px;border-radius:99px;background:rgba(0,0,0,.3);font-size:.62rem;font-weight:700;{li}}}"
            f"{c} .cg-v{{font-size:.9rem;font-weight:900;white-space:nowrap;{br}}}"
            f"{c} .cg-p{{font-size:.74rem;font-weight:900;{li}}}"
            f"{c} .cg-peso{{width:100%;display:grid;grid-template-columns:auto minmax(0,1fr) auto;align-items:center;gap:4px;margin-top:4px;padding:2px 6px;"
            "border-radius:8px;background:rgba(0,0,0,.35)}"
            f"{c} .cg-peso span{{font-size:.56rem;font-weight:800;{li}}}"
            f"{c} .cg-peso i{{height:6px;border-radius:99px;background:rgba(255,255,255,.14);overflow:hidden}}"
            f"{c} .cg-peso u{{display:block;height:100%;border-radius:99px;background:var(--c);box-shadow:0 0 6px var(--c)}}"
            f"{c} .cg-vz{{grid-column:1 / -1;text-align:center;padding:16px 10px;border-radius:12px;border:1.5px dashed #3A4FB0;font-size:.82rem;font-weight:700;{li}}}"
            f"{c} .cg-vz b{{{br}}}"
            "@media (min-width:560px){"
            f"{c} .st-key-cg_grade{{grid-template-columns:repeat(3,minmax(0,1fr))}}}}"
            "@media (max-width:380px){"
            f"{c} .cg-cab{{grid-template-columns:auto minmax(0,1fr)}}"
            f"{c} .cg-vt{{grid-column:1 / -1;flex-direction:row;flex-wrap:wrap;align-items:baseline;justify-content:space-between;gap:2px 8px;text-align:left}}}}"
            "@media (max-width:350px){"
            f"{c} .cg-vt b{{font-size:.8rem}}{c} .cg-r b{{font-size:.74rem}}}}"
            "</style>")
