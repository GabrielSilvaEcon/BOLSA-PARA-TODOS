"""Painel da tela Início: mercado hoje, seus ativos, atalhos por tipo de ativo e cartão de aprendizado.

Aqui ficam só as partes SEM Streamlit: buscar cotações, montar o HTML e o CSS. O app.py desenha os blocos e guarda as cotações em cache.
Regra: nada daqui derruba a tela. Cotação que não chega vira "n/d" e o bloco inteiro some se não houver nenhum dado.
"""
from __future__ import annotations

import html
from concurrent.futures import ThreadPoolExecutor

import jornada_arte as ART
import jornada_icones as IC

# Atalhos por tipo de ativo: (id de CSS, rótulo, url_path da página, ícone Material, cor). A cor segue a dos cartões da tela Analisar.
ATALHOS = (
    ("acoes", "Ações", "preco-justo", ":material/candlestick_chart:", "#8B6CFF"),
    ("fundos", "FIIs e fundos", "fiis", ":material/apartment:", "#2BA7C9"),
    ("rf", "Renda fixa", "renda-fixa", ":material/account_balance:", "#3DDC97"),
    ("cripto", "Cripto", "criptomoedas", ":material/currency_bitcoin:", "#F2B84B"),
)

# (rótulo, símbolo no Yahoo, prefixo do valor, casas decimais)
MERCADO = (
    ("Ibovespa", "^BVSP", "", 0),
    ("Dólar", "BRL=X", "R$ ", 2),
    ("Bitcoin", "BTC-USD", "US$ ", 0),
)


def _num(v, casas: int) -> str:
    """Número no padrão brasileiro (milhar com ponto, decimal com vírgula)."""
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_var(v) -> str:
    return "n/d" if v is None else f"{v:+.2f}%".replace(".", ",")


def classe_var(v) -> str:
    return "na" if v is None else ("up" if v >= 0 else "dn")


def _cotacao(simbolo: str):
    """(último fechamento, variação % sobre o fechamento anterior) ou None se a fonte não respondeu."""
    try:
        import yfinance as yf
        h = yf.Ticker(simbolo).history(period="7d", interval="1d", auto_adjust=True)["Close"].dropna()
        if len(h) < 2:
            return None
        ult, ant = float(h.iloc[-1]), float(h.iloc[-2])
        return ult, ((ult / ant - 1) * 100 if ant else None)
    except Exception:
        return None


def cotacoes(simbolos: list) -> dict:
    """{símbolo: (preço, variação %)}; símbolo sem resposta fica de fora."""
    simbolos = list(dict.fromkeys(simbolos))
    if not simbolos:
        return {}
    with ThreadPoolExecutor(max_workers=min(6, len(simbolos))) as ex:
        res = list(ex.map(_cotacao, simbolos))
    return {s: r for s, r in zip(simbolos, res) if r}


def selic_atual():
    """Meta da Selic (% ao ano) pelo catálogo de indicadores do app, ou None."""
    try:
        import macro_rede
        v = (macro_rede.indicador("selic_meta") or {}).get("valor")
        return float(v) if v is not None else None
    except Exception:
        return None


def mercado_hoje() -> list:
    """Itens do bloco 'Mercado hoje': [{rotulo, valor, var}]. Lista vazia se nada respondeu."""
    cot = cotacoes([s for _, s, _, _ in MERCADO])
    itens = []
    for rotulo, sim, pre, casas in MERCADO:
        if sim in cot:
            p, v = cot[sim]
            itens.append({"rotulo": rotulo, "valor": pre + _num(p, casas), "var": v})
    s = selic_atual()
    if s is not None:
        itens.append({"rotulo": "Selic (meta)", "valor": _num(s, 2) + "% a.a.", "var": None, "sem_var": True})
    return itens


# ------------------------------------------------------------------ HTML
ICONE_MERCADO = {"Ibovespa": ("grafico", "#8B6CFF"), "Dólar": ("moeda", "#3DDC97"), "Bitcoin": ("bitcoin", "#F2B84B"), "Selic": ("percent", "#2BA7C9")}
ICONE_ATALHO = {"acoes": "velas", "fundos": "predio", "rf": "cofre", "cripto": "bitcoin"}


def _icone_sobre(cor: str) -> str:
    """Branco sobre cor escura, azul-noite sobre cor clara."""
    r, g, b = (int(cor[k:k + 2], 16) / 255 for k in (1, 3, 5))
    return "#1B1442" if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.5 else "#FFFFFF"


def html_mercado(itens: list) -> str:
    if not itens:
        return ""
    cards = ""
    for it in itens:
        nome, cor = next((v for k, v in ICONE_MERCADO.items() if str(it["rotulo"]).startswith(k)), ("estrela", "#8B6CFF"))
        v = f'<i class="na">taxa básica</i>' if it.get("sem_var") else f'<i class="{classe_var(it["var"])}">{html.escape(fmt_var(it["var"]))}</i>'
        cards += (f'<div class="in-mk" style="--ac:{cor}"><img class="bg" src="{IC.uri(nome, cor)}" alt="">'
                  f'<div class="top"><span class="ch"><img src="{IC.uri(nome, cor)}" alt=""></span><span>{html.escape(it["rotulo"])}</span></div>'
                  f'<b>{html.escape(it["valor"])}</b>{v}</div>')
    return f'<div class="in-mkg">{cards}</div>'


def html_atalho(rotulo: str, cor: str, id_: str, travado: bool = False) -> str:
    """Cartão ilustrado de um tipo de ativo. O clique vem de um page_link invisível por cima (ver CSS)."""
    cadeado = f'<span class="lk"><img src="{IC.uri("escudo", "#FFFFFF")}" alt=""></span>' if travado else ""
    return (f'<div class="in-sc{" trav" if travado else ""}" style="--ac:{cor}"><span class="ic"><img src="{IC.uri(ICONE_ATALHO.get(id_, "estrela"), _icone_sobre(cor))}" alt="">{cadeado}</span>'
            f'<b>{html.escape(rotulo)}</b></div>')


def html_ativos(itens: list) -> str:
    """Carrossel horizontal: [{codigo, nome, preco (texto), var}]."""
    if not itens:
        return ""
    cards = ""
    for it in itens:
        cards += (f'<div class="in-at"><em>{html.escape(it["codigo"])}</em><span>{html.escape(it["nome"])}</span>'
                  f'<b>{html.escape(it["preco"])}</b><i class="{classe_var(it["var"])}">{html.escape(fmt_var(it["var"]))}</i></div>')
    return f'<div class="in-car">{cards}</div>'


def html_aprender(titulo_licao: str, unidade: str, feitas: int, total: int, ofensiva: int, xp: int) -> str:
    pct = int(round(100 * feitas / total)) if total else 0
    seq = f'<span>{ofensiva} {"dia seguido" if ofensiva == 1 else "dias seguidos"}</span>' if ofensiva else ""
    humor = "festa" if total and feitas >= total else "normal"
    return (f'<div class="in-ap"><div class="in-ap-tico">{ART.mascote(humor=humor, tamanho=72)}</div><div class="in-ap-k">{html.escape(unidade)}</div>'
            f'<div class="in-ap-t">{html.escape(titulo_licao)}</div>'
            f'<div class="in-ap-bar"><i style="width:{pct}%"></i></div>'
            f'<div class="in-ap-s"><span>{feitas} de {total} lições</span><span>{xp} XP</span>{seq}</div></div>')


def html_secao(titulo: str, sub: str = "", icone: str = "") -> str:
    s = f"<small>{html.escape(sub)}</small>" if sub else ""
    ic = f'<span class="ch"><img src="{IC.uri(icone, "#FFFFFF")}" alt=""></span>' if icone else ""
    return f'<div class="in-sec">{ic}<b>{html.escape(titulo)}</b>{s}</div>'


# ------------------------------------------------------------------ CSS
def css() -> str:
    atalhos = "".join(f".st-key-in_atalhos .st-key-in_at_{i}{{--ac:{cor};}}" for i, _, _, _, cor in ATALHOS)
    return "<style>" + _CSS + _ARTE + atalhos + "</style>"


_CSS = """
.in-sec{margin:24px 2px 8px; display:flex; align-items:baseline; gap:10px; flex-wrap:wrap;}
.in-sec b{font-size:1.05rem; font-weight:800; color:#fff !important;}
.in-sec small{font-size:.84rem; color:#BDB5E6 !important;}
.in-wrap{max-width:100%;}

/* mercado hoje */
.in-mkg{display:grid; grid-template-columns:repeat(2,minmax(0,1fr)); gap:10px;}
@media (min-width:900px){.in-mkg{grid-template-columns:repeat(4,minmax(0,1fr));}}
.in-mk{display:flex; flex-direction:column; gap:2px; padding:12px 14px; border-radius:16px; background:#1B1442;
  border:1px solid rgba(189,181,230,.20);}
.in-mk span{font-size:.8rem; font-weight:700; color:#BDB5E6 !important;}
.in-mk b{font-size:1.15rem; font-weight:800; color:#fff !important; white-space:nowrap;}
.in-mk i, .in-at i{font-style:normal; font-size:.84rem; font-weight:800;}
.in-mk i.up, .in-at i.up{color:#3DDC97 !important;}
.in-mk i.dn, .in-at i.dn{color:#FF6B6B !important;}
.in-mk i.na, .in-at i.na{color:#BDB5E6 !important;}

/* seus ativos: carrossel */
.in-car{display:flex; gap:10px; overflow-x:auto; padding:2px 2px 10px; scroll-snap-type:x proximity; -webkit-overflow-scrolling:touch;}
.in-at{flex:none; min-width:138px; scroll-snap-align:start; display:flex; flex-direction:column; gap:2px; padding:12px 14px;
  border-radius:16px; background:#1B1442; border:1px solid rgba(189,181,230,.20);}
.in-at em{font-style:normal; font-size:.95rem; font-weight:800; color:#fff !important;}
.in-at span{font-size:.78rem; color:#BDB5E6 !important; max-width:150px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;}
.in-at b{margin-top:6px; font-size:1.05rem; font-weight:800; color:#fff !important;}

/* atalhos por tipo de ativo: cartão em HTML + page_link invisível por cima */
.st-key-in_atalhos [data-testid="stHorizontalBlock"]{display:grid !important; grid-template-columns:repeat(2,minmax(0,1fr)) !important; gap:12px !important;}
@media (min-width:900px){.st-key-in_atalhos [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(4,minmax(0,1fr)) !important;}}
.st-key-in_atalhos [data-testid="stColumn"]{width:100% !important; min-width:0 !important; flex:none !important;}
.st-key-in_atalhos [data-testid="stColumn"] > div, .st-key-in_atalhos [data-testid="stColumn"] [data-testid="stVerticalBlock"]{width:100% !important; gap:0 !important;}
.st-key-in_atalhos [class*="st-key-in_at_"]{position:relative; width:100% !important; gap:0 !important;}
.st-key-in_atalhos [class*="st-key-in_at_"] [data-testid="stElementContainer"]:has(a){position:absolute !important; inset:0; z-index:3; margin:0 !important;}
.st-key-in_atalhos [class*="st-key-in_at_"] a{display:block !important; position:absolute; inset:0; width:100% !important; height:100% !important; opacity:0; padding:0 !important; margin:0 !important;}
.st-key-in_atalhos [class*="st-key-in_at_"]:has(a:focus-visible) .in-sc{outline:3px solid #C5B3FF; outline-offset:2px;}
.st-key-in_atalhos [class*="st-key-in_at_"]:active .in-sc{transform:translateY(4px); box-shadow:0 1px 0 color-mix(in srgb,var(--ac) 30%,#0B0821);}
/* continuar de onde parou */
.st-key-in_continuar a[data-testid="stPageLink-NavLink"]{border-radius:16px !important; justify-content:flex-start !important; min-height:52px;}

/* para aprender */
.st-key-in_aprender{padding:16px !important; border-radius:20px; background:linear-gradient(135deg,rgba(91,63,214,.40),rgba(27,20,66,.95));
  border:1px solid rgba(189,181,230,.28);}
.in-ap-k{font-size:.82rem; font-weight:700; color:#C5B3FF !important;}
.in-ap-t{margin-top:2px; font-size:1.15rem; font-weight:800; line-height:1.25; color:#fff !important;}
.in-ap-bar{margin-top:12px; height:8px; border-radius:99px; background:rgba(255,255,255,.14); overflow:hidden;}
.in-ap-bar i{display:block; height:100%; border-radius:99px; background:linear-gradient(90deg,#F2B84B,#FFD98A);}
.in-ap-s{margin-top:8px; display:flex; flex-wrap:wrap; gap:4px 14px; font-size:.82rem; font-weight:600; color:#BDB5E6 !important;}
.in-ap-s span{color:#BDB5E6 !important;}
"""


_ARTE = """
/* ---- arte: títulos, mercado, atalhos, continuar, aprender ---- */
.in-sec{margin:30px 2px 14px; padding-bottom:2px; line-height:1.3; position:relative; z-index:1; align-items:center;}
.in-sec .ch,.in-mk .ch{flex:0 0 28px; width:28px; height:28px; border-radius:50%; display:grid; place-items:center;
  background:radial-gradient(circle at 30% 20%,rgba(255,255,255,.45),transparent 55%),linear-gradient(135deg,#6E4BFF,#B02FC8); box-shadow:0 3px 0 #3A2A86;}
.in-sec .ch img{width:16px; height:16px; display:block;}
.in-mk{position:relative; overflow:hidden; gap:4px; padding:12px 14px 13px; background:linear-gradient(160deg,color-mix(in srgb,var(--ac) 16%,#1B1442),#1B1442 65%);
  border:1px solid color-mix(in srgb,var(--ac) 35%,transparent); box-shadow:0 4px 0 rgba(0,0,0,.28);}
.in-mk .bg{position:absolute; right:-10px; bottom:-12px; width:76px; height:76px; opacity:.10; transform:rotate(-12deg); pointer-events:none;}
.in-mk .top{display:flex; align-items:center; gap:8px; position:relative;}
.in-mk .ch{flex:0 0 26px; width:26px; height:26px; background:color-mix(in srgb,var(--ac) 20%,transparent); box-shadow:none;}
.in-mk .ch img{width:15px; height:15px; display:block;}
.in-mk b,.in-mk i{position:relative;}
.in-mk i{align-self:flex-start; padding:2px 10px 2px 8px; border-radius:99px; background:rgba(255,255,255,.07); display:inline-flex; align-items:center; gap:5px;}
.in-mk i.up:before,.in-mk i.dn:before{content:""; border:5px solid transparent;}
.in-mk i.up:before{border-bottom:7px solid #3DDC97; border-top:0;}
.in-mk i.dn:before{border-top:7px solid #FF6B6B; border-bottom:0;}
.in-sc{position:relative; overflow:hidden; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:11px; min-height:118px; padding:16px 8px 14px; text-align:center; border-radius:20px;
  background:radial-gradient(circle at 88% 10%,color-mix(in srgb,var(--ac) 35%,transparent),transparent 45%),linear-gradient(160deg,color-mix(in srgb,var(--ac) 16%,#1B1442),#1B1442 72%);
  border:1px solid color-mix(in srgb,var(--ac) 42%,transparent); box-shadow:0 5px 0 color-mix(in srgb,var(--ac) 30%,#0B0821); transition:transform .08s,box-shadow .08s;}
.in-sc .ic{position:relative; width:58px; height:58px; border-radius:50%; display:grid; place-items:center;
  background:radial-gradient(circle at 30% 18%,rgba(255,255,255,.5),transparent 52%),var(--ac); box-shadow:0 4px 0 color-mix(in srgb,var(--ac) 55%,#0B0821);}
.in-sc .ic img{width:30px; height:30px; display:block;}
.in-sc .lk{position:absolute; right:-4px; bottom:-4px; width:22px; height:22px; border-radius:50%; background:#5B3FD6; border:2px solid #1B1442; display:grid; place-items:center;}
.in-sc .lk img{width:12px; height:12px;}
.in-sc.trav .ic{filter:saturate(.5) brightness(.85);}
.in-sc b{font-size:.98rem; font-weight:800; line-height:1.2; color:#fff !important;}
.st-key-in_continuar [data-testid="stElementContainer"], .st-key-in_continuar a[data-testid="stPageLink-NavLink"]{width:100% !important; box-sizing:border-box;}
.st-key-in_continuar a[data-testid="stPageLink-NavLink"]{display:flex !important; background:rgba(242,184,75,.10) !important; border:1px dashed rgba(242,184,75,.55) !important;}
.st-key-in_aprender{position:relative; overflow:hidden;}
.in-ap{position:relative; padding-right:78px; min-height:84px;}
.in-ap-tico{position:absolute; right:-4px; top:-2px; animation:in-tico 3.2s ease-in-out infinite; transform-origin:50% 100%;}
.in-ap-tico svg{display:block;}
@keyframes in-tico{0%,100%{transform:rotate(-2deg)}50%{transform:translateY(-3px) rotate(2deg)}}
@media (prefers-reduced-motion:reduce){.in-ap-tico{animation:none;}}
"""
