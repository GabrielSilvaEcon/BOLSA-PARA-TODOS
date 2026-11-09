"""Painel da tela Início: mercado hoje, seus ativos, atalhos por tipo de ativo e cartão de aprendizado.

Aqui ficam só as partes SEM Streamlit: buscar cotações, montar o HTML e o CSS. O app.py desenha os blocos e guarda as cotações em cache.
Regra: nada daqui derruba a tela. Cotação que não chega vira "n/d" e o bloco inteiro some se não houver nenhum dado.
"""
from __future__ import annotations

import html
from concurrent.futures import ThreadPoolExecutor

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
def html_mercado(itens: list) -> str:
    if not itens:
        return ""
    cards = ""
    for it in itens:
        v = "" if it.get("sem_var") else f'<i class="{classe_var(it["var"])}">{html.escape(fmt_var(it["var"]))}</i>'
        cards += f'<div class="in-mk"><span>{html.escape(it["rotulo"])}</span><b>{html.escape(it["valor"])}</b>{v}</div>'
    return f'<div class="in-mkg">{cards}</div>'


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
    return (f'<div class="in-ap"><div class="in-ap-k">{html.escape(unidade)}</div>'
            f'<div class="in-ap-t">{html.escape(titulo_licao)}</div>'
            f'<div class="in-ap-bar"><i style="width:{pct}%"></i></div>'
            f'<div class="in-ap-s"><span>{feitas} de {total} lições</span><span>{xp} XP</span>{seq}</div></div>')


def html_secao(titulo: str, sub: str = "") -> str:
    s = f"<small>{html.escape(sub)}</small>" if sub else ""
    return f'<div class="in-sec"><b>{html.escape(titulo)}</b>{s}</div>'


# ------------------------------------------------------------------ CSS
def css() -> str:
    atalhos = "".join(f".st-key-in_atalhos .st-key-in_at_{i}{{--ac:{cor};}}" for i, _, _, _, cor in ATALHOS)
    return "<style>" + _CSS + atalhos + "</style>"


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

/* atalhos por tipo de ativo */
.st-key-in_atalhos [data-testid="stHorizontalBlock"]{display:grid !important; grid-template-columns:repeat(2,minmax(0,1fr)) !important; gap:10px !important;}
@media (min-width:900px){.st-key-in_atalhos [data-testid="stHorizontalBlock"]{grid-template-columns:repeat(4,minmax(0,1fr)) !important;}}
.st-key-in_atalhos [data-testid="stColumn"]{width:auto !important; min-width:0 !important; flex:none !important;}
.stApp [data-testid="stMain"] .st-key-in_atalhos a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]){
  flex-direction:column !important; justify-content:center !important; align-items:center !important; gap:8px !important; min-height:104px;
  padding:14px 8px !important; border-radius:20px !important; text-align:center; background:#1B1442 !important;
  border:1px solid rgba(189,181,230,.22) !important; box-shadow:0 16px 30px -22px rgba(0,0,0,.8) !important; transform:none !important;}
.stApp [data-testid="stMain"] .st-key-in_atalhos a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]):hover{
  background:color-mix(in srgb,var(--ac) 14%,#1B1442) !important; border-color:color-mix(in srgb,var(--ac) 60%,transparent) !important;}
.stApp [data-testid="stMain"] .st-key-in_atalhos a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]) [data-testid="stIconMaterial"]{
  color:var(--ac) !important; font-size:1.9rem !important; width:52px; height:52px; border-radius:16px; display:grid !important; place-items:center;
  background:color-mix(in srgb,var(--ac) 16%,transparent); margin:0 !important;}
.stApp [data-testid="stMain"] .st-key-in_atalhos a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]) p{font-weight:800; font-size:.95rem;}

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
