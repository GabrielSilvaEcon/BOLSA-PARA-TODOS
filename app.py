"""
Painel B3 - Análise Fundamentalista + Técnica
Rodar com:  streamlit run app.py
Dependências: pip install -r requirements.txt   (streamlit>=1.49, pandas, plotly, requests)

Token da Brapi (NUNCA coloque o token direto no código):
  - Local:  crie o arquivo .streamlit/secrets.toml com a linha
              BRAPI_TOKEN = "seu_token_aqui"
  - Ou defina a variável de ambiente BRAPI_TOKEN.
  - Streamlit Cloud: Settings > Secrets.
"""
import json
import os
import unicodedata
from datetime import datetime
from io import StringIO
from math import sqrt

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components

import tecnica as tec

st.set_page_config(page_title="Painel B3", page_icon="📈", layout="wide")

# ---------------------------------------------------------------- paleta neutra
BG, SURFACE, BORDER = "#15171c", "#1b1e25", "#2a2e37"
TEXT, MUTED = "#cfd3da", "#8b919c"
ACCENT = "#8aa0b8"
GOOD, FAIR, BAD = "#7fae93", "#c2ad7e", "#c08580"

st.markdown(
    f"""
<style>
.stApp {{background:{BG};}}
header[data-testid="stHeader"] {{background:transparent;}}
section[data-testid="stSidebar"] {{background:{SURFACE}; border-right:1px solid {BORDER};}}
.block-container {{padding-top:2.2rem; max-width:1400px;}}
.topo {{display:flex; align-items:baseline; gap:14px; padding-bottom:10px;
        border-bottom:1px solid {BORDER}; margin-bottom:14px;}}
.hero {{font-size:1.45rem; font-weight:700; color:#d9dce2; letter-spacing:.2px;}}
.sub {{font-size:.78rem; color:{MUTED};}}
.card {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px;
        padding:16px 18px; margin-bottom:10px;}}
.tk {{font-size:1.3rem; font-weight:700; letter-spacing:.4px;}}
.nm {{font-size:.78rem; color:{MUTED}; margin-bottom:8px;}}
.aviso {{font-size:.72rem; color:{FAIR}; margin-top:6px;}}
.badge {{display:inline-block; padding:3px 11px; border-radius:999px;
         font-size:.72rem; font-weight:600; float:right;}}
.good {{background:rgba(127,174,147,.14); color:{GOOD};}}
.fair {{background:rgba(194,173,126,.14); color:{FAIR};}}
.bad  {{background:rgba(192,133,128,.14); color:{BAD};}}
.na   {{background:rgba(139,145,156,.14); color:{MUTED};}}
.lbl {{font-size:.68rem; color:{MUTED}; text-transform:uppercase; letter-spacing:.8px;}}
.val {{font-size:1.15rem; font-weight:600;}}
h4 {{font-weight:600; color:#d9dce2;}}
</style>
""",
    unsafe_allow_html=True,
)

PLOT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": TEXT}, margin=dict(l=10, r=10, t=40, b=10))
GRID = dict(gridcolor="#262a33", zeroline=False)

# ---------------------------------------------------------------- estado
if "ativos" not in st.session_state:
    st.session_state.ativos = ["PETR4", "ITSA4", "BBAS3", "VALE3"]


def normaliza(t: str) -> str:
    return t.upper().strip().replace(".SA", "")


# ---------------------------------------------------------------- Brapi (cliente)
BRAPI = "https://brapi.dev/api"


def _token() -> str:
    """Lê o token do st.secrets (BRAPI_TOKEN) ou da variável de ambiente."""
    try:
        t = st.secrets.get("BRAPI_TOKEN")
    except Exception:
        t = None
    return str(t or os.environ.get("BRAPI_TOKEN") or "").strip()


def _get(path: str, params: dict | None = None):
    """GET na Brapi. Retorna (json, None) ou (None, mensagem_de_erro)."""
    tok = _token()
    headers = {"Authorization": f"Bearer {tok}"} if tok else {}
    try:
        r = requests.get(f"{BRAPI}{path}", params=params, headers=headers, timeout=15)
    except requests.RequestException as e:
        return None, f"falha de conexão ({e.__class__.__name__})"
    if r.status_code != 200:
        try:
            msg = r.json().get("message")
        except ValueError:
            msg = None
        return None, f"HTTP {r.status_code}" + (f": {msg}" if msg else "")
    try:
        return r.json(), None
    except ValueError:
        return None, "resposta inválida"


def _primeiro(js):
    """Primeiro item de results (ou None)."""
    if isinstance(js, dict):
        res = js.get("results")
        if isinstance(res, list) and res:
            return res[0]
    return None


def _num(x):
    try:
        return None if x is None else float(x)
    except (TypeError, ValueError):
        return None


def _proventos(lista):
    """Converte cashDividends em (série por ano, média 5 anos completos, soma 12 meses)."""
    vazio = pd.Series(dtype=float)
    if not lista:
        return vazio, None, None
    df = pd.DataFrame(lista)
    if "rate" not in df:
        return vazio, None, None
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")

    data = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
    for col in ("paymentDate", "exDate", "lastDatePrior"):
        if col in df:
            data = data.fillna(pd.to_datetime(df[col], errors="coerce", utc=True))
    df["data"] = data
    df = df.dropna(subset=["rate", "data"])
    if df.empty:
        return vazio, None, None

    por_ano = df.groupby(df["data"].dt.year)["rate"].sum()
    por_ano.index = por_ano.index.astype(int)
    por_ano.index.name = "ano"

    hoje = pd.Timestamp.now(tz="UTC")
    mask12 = (df["data"] >= hoje - pd.Timedelta(days=365)) & (df["data"] <= hoje)
    div_12m = float(df.loc[mask12, "rate"].sum())

    # Média dos últimos 5 anos completos (se não houver, usa tudo o que existir)
    completos = por_ano[por_ano.index < hoje.year].tail(5)
    base = completos if len(completos) else por_ano
    return por_ano, float(base.mean()), div_12m


# ---------------------------------------------------------------- fontes de reserva
# Ordem: Brapi (principal) -> Fundamentus -> Yahoo Finance. Só se busca fora da Brapi o que
# ela não trouxe. LPA e VPA são sempre adotados em par, da mesma fonte, para não misturar moedas.
_UA = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept-Language": "pt-BR,pt;q=0.9",
}


def _f(x):
    """float ou None (trata NaN e texto)."""
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(v) else v


def _pt_num(x):
    """Número no formato brasileiro ('1.234,56', '12,3%', '-') -> float ou None."""
    if x is None:
        return None
    if isinstance(x, (int, float)):
        return _f(x)
    s = str(x).strip().replace("%", "").replace("\xa0", "").replace(" ", "")
    if s in ("", "-", "—", "nan", "None"):
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def _norm_cab(c) -> str:
    s = unicodedata.normalize("NFKD", str(c)).encode("ascii", "ignore").decode().lower()
    return "".join(ch for ch in s if not ch.isspace())


def _parse_fundamentus(html: str):
    """Lê a tabela do resultado.php (todas as ações). Colunas casadas pelo nome do
    cabeçalho, não pela posição. Retorna (DataFrame indexado por papel, erro)."""
    vazio = pd.DataFrame()
    try:
        from lxml import html as lxml_html
    except ImportError:
        return vazio, "biblioteca lxml não instalada (pip install lxml)"
    try:
        tabelas = lxml_html.fromstring(html).xpath("//table")
    except Exception as e:
        return vazio, f"não consegui ler a página ({e.__class__.__name__})"
    if not tabelas:
        return vazio, "tabela não encontrada"
    # lê o texto cru das células (o pandas "adivinharia" os números e confundiria a vírgula decimal)
    titulos, linhas = None, []
    for tr in tabelas[0].xpath(".//tr"):
        ths = [c.text_content().strip() for c in tr.xpath("./th")]
        tds = [c.text_content().strip() for c in tr.xpath("./td")]
        if ths and titulos is None:
            titulos = ths
        elif tds:
            linhas.append(tds)
    if not titulos or not linhas:
        return vazio, "tabela vazia"
    linhas = [ln for ln in linhas if len(ln) == len(titulos)]
    if not linhas:
        return vazio, "layout da tabela mudou (nº de colunas diferente)"
    t = pd.DataFrame(linhas, columns=titulos)
    cab = {_norm_cab(c): c for c in t.columns}

    def col(*prefixos):
        for k, orig in cab.items():
            if any(k.startswith(p) for p in prefixos):
                return orig
        return None

    mapa = {"papel": col("papel"), "preco": col("cotacao"), "pl": col("p/l"), "pvp": col("p/vp"),
            "dy": col("div.yield", "divyield"), "ev_ebitda": col("ev/ebitda"),
            "mrg_liq": col("mrg.liq", "mrg.l"), "roe": col("roe"), "div_pat": col("div.brut", "divbrut")}
    if mapa["papel"] is None or mapa["preco"] is None:
        return vazio, "layout da tabela mudou (colunas Papel/Cotação não encontradas)"

    out = pd.DataFrame({"papel": t[mapa["papel"]].astype(str).str.strip().str.upper()})
    for k, c in mapa.items():
        if k != "papel":
            out[k] = pd.to_numeric(t[c].map(_pt_num), errors="coerce") if c is not None else float("nan")
    for k in ("dy", "mrg_liq", "roe"):  # vêm em %, guardamos como fração
        out[k] = out[k] / 100
    out = out.set_index("papel")
    return out[~out.index.duplicated(keep="first")], None


@st.cache_data(ttl=900, show_spinner=False)
def _fundamentus_tabela():
    try:
        r = requests.get("https://www.fundamentus.com.br/resultado.php", headers=_UA, timeout=20)
    except requests.RequestException as e:
        return pd.DataFrame(), f"falha de conexão ({e.__class__.__name__})"
    if r.status_code != 200:
        return pd.DataFrame(), f"HTTP {r.status_code}"
    return _parse_fundamentus(r.content.decode("latin-1"))  # o site usa ISO-8859-1


def fonte_fundamentus(tk: str):
    """Dados do Fundamentus para um papel. Retorna (dict | None, erro).
    LPA = cotação ÷ P/L e VPA = cotação ÷ P/VP: como o preço está em R$, saem sempre em R$."""
    tab, err = _fundamentus_tabela()
    if tab.empty:
        return None, err
    if tk not in tab.index:
        return None, "papel não encontrado"
    r = tab.loc[tk]
    preco, pl, pvp, dy = _f(r["preco"]), _f(r["pl"]), _f(r["pvp"]), _f(r["dy"])
    dpat = _f(r["div_pat"])
    return {
        "preco": preco,
        "lpa": preco / pl if preco and pl else None,
        "vpa": preco / pvp if preco and pvp else None,
        "ev_ebitda": _f(r["ev_ebitda"]), "roe": _f(r["roe"]), "margem_liq": _f(r["mrg_liq"]),
        "div_pl": dpat * 100 if dpat is not None else None,  # razão -> %
        "div_12m": dy * preco if dy is not None and preco else None,
        "moeda_api": "BRL",
    }, None


def _yf():
    try:
        import yfinance as yf
        return yf
    except ImportError:
        return None


@st.cache_data(ttl=900, show_spinner=False)
def yahoo_info(ticker: str):
    """Cotação e indicadores do Yahoo. Retorna (dict | None, erro)."""
    yf = _yf()
    if yf is None:
        return None, "Yahoo: biblioteca yfinance não instalada (pip install yfinance)"
    try:
        info = yf.Ticker(f"{ticker}.SA").info or {}
    except Exception as e:
        return None, f"Yahoo: {e.__class__.__name__}"
    preco = _f(info.get("currentPrice")) or _f(info.get("regularMarketPrice"))
    if preco is None and _f(info.get("trailingEps")) is None:
        return None, "Yahoo: sem dados para o ativo"
    td, tc = _f(info.get("totalDebt")), _f(info.get("totalCash"))
    moeda = info.get("financialCurrency")
    return {
        "nome": info.get("longName") or info.get("shortName"),
        "preco": preco, "lpa": _f(info.get("trailingEps")), "vpa": _f(info.get("bookValue")),
        "ev_ebitda": _f(info.get("enterpriseToEbitda")), "roe": _f(info.get("returnOnEquity")),
        "margem_liq": _f(info.get("profitMargins")),
        "div_pl": _f(info.get("debtToEquity")),  # o Yahoo já entrega em %
        "acoes": _f(info.get("sharesOutstanding")), "mcap": _f(info.get("marketCap")),
        "divida_liq": td - tc if td is not None and tc is not None else None,
        "moeda_api": str(moeda).upper() if moeda else None,
    }, None


@st.cache_data(ttl=900, show_spinner=False)
def yahoo_dividendos(ticker: str):
    """Proventos do Yahoo (data ex) no mesmo formato da Brapi. Retorna (lista, erro)."""
    yf = _yf()
    if yf is None:
        return [], None
    try:
        s = yf.Ticker(f"{ticker}.SA").dividends
    except Exception as e:
        return [], f"Yahoo (dividendos): {e.__class__.__name__}"
    if s is None or len(s) == 0:
        return [], None
    return [{"paymentDate": ts.isoformat(), "rate": float(v)} for ts, v in s.items()], None


@st.cache_data(ttl=900, show_spinner=False)
def yahoo_caixa(ticker: str):
    """Fluxo de caixa anual do Yahoo. Retorna (DataFrame, moeda do balanço)."""
    vazio = (pd.DataFrame(), None)
    yf = _yf()
    if yf is None:
        return vazio
    try:
        cf = yf.Ticker(f"{ticker}.SA").cashflow
    except Exception:
        return vazio
    if cf is None or cf.empty:
        return vazio
    nomes = {"Operating Cash Flow": "Caixa operacional", "Investing Cash Flow": "Caixa de investimento",
             "Free Cash Flow": "Fluxo de caixa livre"}
    cols = {pt: cf.loc[k] for k, pt in nomes.items() if k in cf.index}
    if "Fluxo de caixa livre" not in cols and {"Operating Cash Flow", "Capital Expenditure"} <= set(cf.index):
        cols["Fluxo de caixa livre"] = cf.loc["Operating Cash Flow"] + cf.loc["Capital Expenditure"]
    if not cols:
        return vazio
    out = pd.DataFrame(cols).apply(pd.to_numeric, errors="coerce")
    anos = pd.to_datetime(out.index, errors="coerce").year
    out = out[~pd.isna(anos)]
    out.index = [int(a) for a in anos[~pd.isna(anos)]]
    out = out[~out.index.duplicated(keep="first")].dropna(how="all").sort_index()
    info, _ = yahoo_info(ticker)
    return out, (info or {}).get("moeda_api")


@st.cache_data(ttl=900, show_spinner=False)
def yahoo_historico(ticker: str, periodo: str, intervalo: str):
    """Histórico OHLCV do Yahoo. Retorna (DataFrame, erro)."""
    yf = _yf()
    if yf is None:
        return pd.DataFrame(), "Yahoo: biblioteca yfinance não instalada"
    try:
        df = yf.Ticker(f"{ticker}.SA").history(period=periodo, interval=intervalo)
    except Exception as e:
        return pd.DataFrame(), f"Yahoo: {e.__class__.__name__}"
    if df is None or df.empty:
        return pd.DataFrame(), "Yahoo: sem histórico"
    df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
    idx = pd.DatetimeIndex(df.index)
    if idx.tz is not None:
        idx = idx.tz_localize(None)  # já está no horário de São Paulo
    df.index = idx.normalize()
    df.index.name = "Date"
    df = df[~df.index.duplicated(keep="first")].sort_index()
    return df.dropna(subset=["Open", "High", "Low", "Close"]), None


def _completar(d: dict, tk: str, erros: list) -> None:
    """Preenche com Fundamentus e Yahoo o que a Brapi não trouxe (altera d no lugar)."""
    razoes = ("ev_ebitda", "roe", "margem_liq", "div_pl")
    notas = []
    estado = {"yi": None, "buscou": False}

    def nucleo_ok():
        return d["lpa"] is not None and d["vpa"] is not None

    def yahoo():
        if not estado["buscou"]:
            estado["buscou"] = True
            estado["yi"], err = yahoo_info(tk)
            if err:
                erros.append(err)
        return estado["yi"]

    precisa = (d["preco"] is None or not nucleo_ok() or len(d["div_ano"]) == 0
               or any(d[k] is None for k in razoes))
    if not precisa:
        return
    fund, err = fonte_fundamentus(tk)
    if err:
        erros.append(f"Fundamentus: {err}")

    # cotação
    if d["preco"] is None:
        if fund and fund.get("preco"):
            d["preco"] = fund["preco"]
            notas.append("Cotação via Fundamentus (Brapi sem dados).")
        else:
            y = yahoo()
            if y and y.get("preco"):
                d["preco"] = y["preco"]
                notas.append("Cotação via Yahoo Finance (Brapi sem dados).")

    # LPA e VPA: sempre o par inteiro de uma única fonte
    def adotar(f, nome):
        d["lpa"], d["vpa"] = f["lpa"], f["vpa"]
        d["moeda_api"] = f.get("moeda_api")
        d["divida_liq"] = f.get("divida_liq")  # a dívida da Brapi pode estar em outra moeda
        for k in razoes + ("acoes", "mcap"):
            if d[k] is None and f.get(k) is not None:
                d[k] = f[k]
        notas.append(f"LPA e VPA via {nome} (Brapi sem esses dados).")

    if not nucleo_ok():
        if fund and fund.get("lpa") is not None and fund.get("vpa") is not None:
            adotar(fund, "Fundamentus")
        else:
            y = yahoo()
            if y and y.get("lpa") is not None and y.get("vpa") is not None:
                adotar(y, "Yahoo Finance")

    # indicadores em razão (ROE, margens...) não dependem de moeda
    faltavam = [k for k in razoes if d[k] is None]
    for k in faltavam:
        for f in (fund, estado["yi"]):
            if f and f.get(k) is not None:
                d[k] = f[k]
                break
    if any(d[k] is not None for k in faltavam):
        notas.append("Alguns indicadores (ROE, margem, Dív./PL, EV/EBITDA) completados por Fundamentus/Yahoo.")

    # ações, valor de mercado, dívida líquida e nome (Yahoo, se já consultado)
    yi = estado["yi"]
    if yi:
        for k in ("acoes", "mcap"):
            if d[k] is None and yi.get(k) is not None:
                d[k] = yi[k]
        if (d["divida_liq"] is None and yi.get("divida_liq") is not None and yi.get("moeda_api")
                and yi["moeda_api"] == str(d["moeda_api"] or "").upper()):
            d["divida_liq"] = yi["divida_liq"]
        if d["nome"] == tk and yi.get("nome"):
            d["nome"] = yi["nome"]

    # dividendos
    if len(d["div_ano"]) == 0:
        lista, err = yahoo_dividendos(tk)
        if err:
            erros.append(err)
        por_ano, medio, d12 = _proventos(lista)
        if len(por_ano):
            d["div_ano"], d["div_medio"], d["div_12m"] = por_ano, medio, d12
            notas.append("Dividendos via Yahoo Finance (agrupados pela data ex, não a de pagamento).")
        elif d["div_12m"] is None and fund and fund.get("div_12m") is not None:
            d["div_12m"] = fund["div_12m"]
            notas.append("DY 12m via Fundamentus (sem histórico por ano: Bazin indisponível).")

    d["fontes_aviso"] = notas


# ---------------------------------------------------------------- dados
@st.cache_data(ttl=900, show_spinner=False)
def buscar_cambio():
    """Dólar comercial (USD→BRL): média de compra e venda. None se indisponível."""
    js, _ = _get("/v2/currency", {"currency": "USD-BRL"})
    try:
        c = js["currency"][0]
        vals = [v for v in (_num(c.get("bidPrice")), _num(c.get("askPrice"))) if v]
        return sum(vals) / len(vals) if vals else None
    except (TypeError, KeyError, IndexError):
        return None


@st.cache_data(ttl=900, show_spinner=False)
def buscar(ticker: str) -> dict:
    """Cotação, LPA/VPA, múltiplos e proventos de um ativo via Brapi."""
    tk = normaliza(ticker)
    d = {
        "ticker": tk, "nome": tk, "preco": None, "lpa": None, "vpa": None,
        "div_ano": pd.Series(dtype=float), "div_medio": None, "div_12m": None,
        "ev_ebitda": None, "roe": None, "margem_liq": None, "div_pl": None,
        "acoes": None, "mcap": None, "divida_liq": None, "pl_api": None,
        "moeda_api": None, "moeda": "BRL", "erro": None, "fontes_aviso": [],
    }
    erros = []

    # 1) Cotação + proventos (uma única chamada)
    js, err = _get(f"/quote/{tk}", {"dividends": "true"})
    if err:
        erros.append(f"cotação: {err}")
    q = _primeiro(js)
    lista_div = None
    if q:
        d["nome"] = q.get("longName") or q.get("shortName") or tk
        d["preco"] = _num(q.get("regularMarketPrice"))
        d["lpa"] = _num(q.get("earningsPerShare"))
        d["mcap"] = _num(q.get("marketCap"))
        d["pl_api"] = _num(q.get("priceEarnings"))
        lista_div = (q.get("dividendsData") or {}).get("cashDividends")

    if lista_div is None:  # fallback: endpoint v2 de dividendos
        js, err = _get("/v2/stocks/dividends", {"symbols": tk})
        if err:
            erros.append(f"dividendos: {err}")
        item = _primeiro(js)
        if item:
            lista_div = (item.get("data") or {}).get("cashDividends")
    d["div_ano"], d["div_medio"], d["div_12m"] = _proventos(lista_div)

    # 2) Múltiplos: VPA, LPA, EV/EBITDA, nº de ações
    js, err = _get("/v2/stocks/statistics", {"symbols": tk})
    if err:
        erros.append(f"múltiplos: {err}")
    item = _primeiro(js)
    est = (item or {}).get("data") or {}
    if isinstance(est, dict):
        d["vpa"] = _num(est.get("bookValue"))
        d["lpa"] = _num(est.get("trailingEps")) or d["lpa"]
        d["ev_ebitda"] = _num(est.get("enterpriseToEbitda"))
        d["acoes"] = _num(est.get("sharesOutstanding"))
        d["margem_liq"] = _num(est.get("profitMargins"))

    # 3) Dados financeiros: ROE, margem líquida, dívida/PL
    js, err = _get("/v2/stocks/financial-data", {"symbols": tk})
    if err:
        erros.append(f"dados financeiros: {err}")
    item = _primeiro(js)
    fin = (item or {}).get("data") or {}
    if isinstance(fin, dict):
        d["roe"] = _num(fin.get("returnOnEquity"))
        d["margem_liq"] = _num(fin.get("profitMargins")) if _num(fin.get("profitMargins")) is not None else d["margem_liq"]
        dpl = _num(fin.get("debtToEquity"))
        d["div_pl"] = dpl * 100 if dpl is not None else None  # vem como razão (0,55) -> %
        d["moeda_api"] = fin.get("financialCurrency") or None
        divida, caixa_total = _num(fin.get("totalDebt")), _num(fin.get("totalCash"))
        if divida is not None and caixa_total is not None:
            d["divida_liq"] = divida - caixa_total

    _completar(d, tk, erros)  # Fundamentus e Yahoo preenchem o que faltou

    d["erro"] = "; ".join(erros) or None
    return d


@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa(ticker: str):
    """Fluxo de caixa anual. Brapi primeiro, Yahoo como reserva.
    Retorna (DataFrame, fonte, moeda do dado, ou None se for a mesma do balanço)."""
    df = _caixa_brapi(ticker)
    if not df.empty:
        return df, "Brapi", None
    df, moeda = yahoo_caixa(ticker)
    if not df.empty:
        return df, "Yahoo Finance", moeda
    return pd.DataFrame(), None, None


def _caixa_brapi(ticker: str) -> pd.DataFrame:
    """Fluxo de caixa anual da Brapi (operacional, investimento, livre), na moeda do balanço."""
    js, _ = _get("/v2/stocks/cash-flow", {"symbols": normaliza(ticker), "period": "annual"})
    item = _primeiro(js)
    linhas = (item or {}).get("data")
    if not linhas:
        return pd.DataFrame()
    df = pd.DataFrame(linhas)
    if "endDate" not in df:
        return pd.DataFrame()
    nomes = {
        "operatingCashFlow": "Caixa operacional",
        "investmentCashFlow": "Caixa de investimento",
        "freeCashFlow": "Fluxo de caixa livre",
    }
    cols = [k for k in nomes if k in df]
    if not cols:
        return pd.DataFrame()
    out = df[cols].apply(pd.to_numeric, errors="coerce").rename(columns=nomes)
    out.index = pd.to_datetime(df["endDate"], errors="coerce").dt.year
    out = out[out.index.notna()]
    out.index = out.index.astype(int)
    out = out[~out.index.duplicated(keep="last")]
    return out.dropna(how="all").sort_index()


@st.cache_data(ttl=900, show_spinner=False)
def historico(ticker: str, periodo: str, intervalo: str):
    """Histórico OHLCV: Brapi primeiro; se vier vazio ou curto, tenta o Yahoo.
    Retorna (DataFrame, mensagem_de_erro, fonte)."""
    df, err = _historico_brapi(ticker, periodo, intervalo)
    fonte = "Brapi"
    if len(df) < 30:
        dy, err_y = yahoo_historico(normaliza(ticker), periodo, intervalo)
        if len(dy) > len(df):
            df, fonte, err = dy, "Yahoo Finance", None
        else:
            err = err or err_y
    return df, (err if df.empty else None), fonte


def _historico_brapi(ticker: str, periodo: str, intervalo: str):
    """Histórico OHLCV da Brapi. Retorna (DataFrame, mensagem_de_erro)."""
    js, err = _get(f"/quote/{normaliza(ticker)}", {"range": periodo, "interval": intervalo})
    item = _primeiro(js)
    dados = (item or {}).get("historicalDataPrice")
    if not dados:
        return pd.DataFrame(), err or "a API não devolveu histórico para esse ativo/período"
    df = pd.DataFrame(dados).rename(columns={
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume"})
    # epoch (s) -> data local de São Paulo, sem fuso (alinha o candle ao dia do pregão)
    df["Date"] = (pd.to_datetime(df["Date"], unit="s", utc=True)
                  .dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None).dt.normalize())
    df = df.drop_duplicates("Date").set_index("Date").sort_index()
    df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"]), None


def _mi(x):
    """Número em milhões, no formato brasileiro (ex.: 13.200)."""
    return f"{x / 1e6:,.0f}".replace(",", ".")


def normalizar(d: dict, moeda_forcada: str, fx) -> dict:
    """Leva LPA, VPA e dívida líquida para R$ quando o balanço está em dólar,
    define o nº de ações e reúne os avisos de qualidade dos dados.
    Preço e dividendos já vêm em R$ (B3); múltiplos/margens/ROE são razões e não mudam."""
    d = dict(d)
    avisos = list(d.get("fontes_aviso", []))
    d["moeda_forcada"], d["fx_cambio"] = moeda_forcada, fx

    # 1) moeda do balanço: escolha do usuário > informada pela API > detectada > R$
    if moeda_forcada in ("BRL", "USD"):
        moeda, origem = moeda_forcada, "definida por você"
    elif d.get("moeda_api"):
        moeda, origem = str(d["moeda_api"]).upper(), "informada pela API"
    else:
        moeda, origem = "BRL", "assumida"
        p, lpa, pl_api = d["preco"], d["lpa"], d["pl_api"]
        if fx and p and lpa and lpa > 0 and pl_api and pl_api > 0:
            # se o P/L da API já considera o câmbio, preço/LPA fica ~fx vezes menor que ele
            razao = (p / lpa) / pl_api
            if 0.8 * fx <= razao <= 1.2 * fx:
                moeda, origem = "USD", "detectada pelo P/L da API"
    d["moeda"], d["fx"] = moeda, None

    # 2) conversão para R$
    if moeda == "USD":
        if fx:
            d["fx"] = fx
            for k in ("lpa", "vpa", "divida_liq"):
                if d[k] is not None:
                    d[k] *= fx
            avisos.append(f"Balanço em US$ ({origem}): convertido a R$ {fx:.2f}/US$ (câmbio atual).")
        else:
            d["lpa"] = d["vpa"] = d["divida_liq"] = None
            avisos.append("Balanço em US$ e câmbio indisponível: Graham e DCF omitidos.")
    elif moeda != "BRL":
        d["lpa"] = d["vpa"] = d["divida_liq"] = None
        avisos.append(f"Balanço em {moeda}: conversão não suportada; Graham e DCF omitidos.")

    # 3) nº de ações: valor de mercado ÷ preço costuma cobrir todas as classes (ON+PN)
    acoes_cap = d["mcap"] / d["preco"] if d["mcap"] and d["preco"] else None
    acoes_api = d["acoes"]
    if acoes_cap and acoes_api and abs(acoes_cap / acoes_api - 1) > 0.10:
        avisos.append(f"Nº de ações diverge (valor de mercado ÷ preço: {_mi(acoes_cap)} mi; "
                      f"API: {_mi(acoes_api)} mi). Usei o primeiro.")
    d["acoes"] = acoes_cap or acoes_api
    d["avisos"] = avisos
    return d


def caixa_ajustada(d: dict):
    """Fluxo de caixa em R$ (converte do dólar quando preciso). Retorna (DataFrame, fonte)."""
    c, fonte, moeda_cx = buscar_caixa(d["ticker"])
    if c.empty:
        return c, None
    forcada = d.get("moeda_forcada")
    moeda = forcada if forcada in ("BRL", "USD") else (moeda_cx or d["moeda"])
    if moeda == "BRL":
        return c, fonte
    if moeda == "USD" and d.get("fx_cambio"):
        return c * d["fx_cambio"], fonte
    return pd.DataFrame(), None


def carregar(ativos):
    out = {}
    with st.spinner("Buscando dados..."):
        fx = buscar_cambio()
        for tk in ativos:
            try:
                d = buscar(tk)
            except Exception as e:
                st.warning(f"Não consegui carregar {tk}: {e}")
                continue
            if d["preco"] is None and d["erro"]:
                st.warning(f"{tk}: {d['erro']}")
            out[tk] = normalizar(d, st.session_state.get(f"moeda_{tk}", "Auto"), fx)
    return out


# ---------------------------------------------------------------- cálculos
def analisar(d: dict, metodo: str, yield_alvo: float, margem_alvo: float) -> dict:
    graham = None
    if d["lpa"] and d["vpa"] and d["lpa"] > 0 and d["vpa"] > 0:
        graham = sqrt(22.5 * d["lpa"] * d["vpa"])

    bazin = None
    if d["div_medio"] and d["div_medio"] > 0:
        bazin = d["div_medio"] / (yield_alvo / 100)

    if metodo == "Graham":
        justo = graham
    elif metodo == "Bazin":
        justo = bazin
    else:
        vals = [v for v in (graham, bazin) if v]
        justo = sum(vals) / len(vals) if vals else None

    margem = None
    if justo and d["preco"]:
        margem = (justo - d["preco"]) / justo * 100

    if margem is None:
        status, cls = "Sem dados", "na"
    elif margem >= margem_alvo:
        status, cls = "Com margem", "good"
    elif margem >= 0:
        status, cls = "Preço justo", "fair"
    else:
        status, cls = "Acima do justo", "bad"

    avisos = list(d.get("avisos", []))
    if justo and d["preco"] and not (0.25 <= justo / d["preco"] <= 4):
        avisos.append("Preço justo muito distante do preço atual: confira moeda e unidades dos dados.")

    return {**d, "graham": graham, "bazin": bazin, "justo": justo,
            "margem": margem, "status": status, "cls": cls, "avisos": avisos}


def multiplos(d: dict) -> dict:
    p = d["preco"]
    return {
        "pl": p / d["lpa"] if p and d["lpa"] and d["lpa"] > 0 else None,
        "pvp": p / d["vpa"] if p and d["vpa"] and d["vpa"] > 0 else None,
        "dy": d["div_12m"] / p * 100 if p and d["div_12m"] is not None else None,
        "roe": d["roe"] * 100 if d["roe"] is not None else None,
        "margem": d["margem_liq"] * 100 if d["margem_liq"] is not None else None,
    }


def dcf(caixa: pd.DataFrame, acoes, divida_liq, taxa: float, g: float, gp: float,
        descontar_divida: bool = True):
    """Valor por ação: FCL médio de 3 anos projetado 5 anos + perpetuidade, a valor presente.
    O resultado é o valor da empresa; com descontar_divida, subtrai a dívida líquida antes de
    dividir pelas ações. Tudo em R$. Retorna (valor_por_acao, fcl_base, valor_da_empresa)."""
    if not acoes or caixa.empty or "Fluxo de caixa livre" not in caixa or taxa <= gp:
        return None, None, None
    base = caixa["Fluxo de caixa livre"].dropna().tail(3).mean()
    if pd.isna(base) or base <= 0:
        return None, base, None
    pv = sum(base * (1 + g) ** t / (1 + taxa) ** t for t in range(1, 6))
    vt = base * (1 + g) ** 5 * (1 + gp) / (taxa - gp)
    empresa = pv + vt / (1 + taxa) ** 5
    patrimonio = empresa - (divida_liq if descontar_divida and divida_liq is not None else 0)
    if patrimonio <= 0:
        return None, base, empresa
    return patrimonio / acoes, base, empresa


def brl(v):
    return "—" if v is None or pd.isna(v) else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gauge(margem):
    v = 0 if margem is None else max(-60, min(60, margem))
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=v,
        number={"suffix": "%", "font": {"size": 26, "color": TEXT}},
        gauge={
            "axis": {"range": [-60, 60], "tickcolor": "#5d6470"},
            "bar": {"color": "#aeb4bf", "thickness": 0.22},
            "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
            "steps": [
                {"range": [-60, 0], "color": "rgba(192,133,128,.30)"},
                {"range": [0, 20], "color": "rgba(194,173,126,.30)"},
                {"range": [20, 60], "color": "rgba(127,174,147,.30)"},
            ],
        },
    ))
    fig.update_layout(height=150, margin=dict(l=10, r=10, t=10, b=0), **{
        k: v_ for k, v_ in PLOT.items() if k != "margin"})
    return fig


# ---------------------------------------------------------------- páginas: fundamentalista
def pagina_preco_justo(dados):
    c1, c2, c3 = st.columns(3)
    metodo = c1.selectbox("Método", ["Média (Graham + Bazin)", "Graham", "Bazin"])
    yield_alvo = c2.slider("Dividend yield desejado (Bazin)", 4.0, 12.0, 6.0, 0.5, format="%.1f%%")
    margem_alvo = c3.slider("Margem de segurança alvo", 5, 50, 20, 5, format="%d%%")
    st.caption("Graham = √(22,5 × LPA × VPA)  ·  Bazin = dividendo médio dos últimos 5 anos completos ÷ yield desejado")

    resultados = [analisar(d, metodo.split(" ")[0], yield_alvo, margem_alvo) for d in dados.values()]
    t_painel, t_comp = st.tabs(["Painel", "Comparativo"])

    with t_painel:
        por_linha = 3
        for i in range(0, len(resultados), por_linha):
            cols = st.columns(por_linha)
            for col, r in zip(cols, resultados[i:i + por_linha]):
                with col:
                    aviso = "".join(f'<div class="aviso">{m}</div>' for m in r["avisos"])
                    st.markdown(
                        f"""<div class="card">
                        <span class="badge {r['cls']}">{r['status']}</span>
                        <div class="tk">{r['ticker']}</div>
                        <div class="nm">{r['nome']}</div>
                        <div style="display:flex; gap:22px;">
                          <div><div class="lbl">Preço atual</div><div class="val">{brl(r['preco'])}</div></div>
                          <div><div class="lbl">Preço justo</div><div class="val">{brl(r['justo'])}</div></div>
                        </div>
                        <div style="margin-top:10px;">
                          <div class="lbl">Média de dividendos (5 anos)</div>
                          <div class="val">{brl(r['div_medio'])} <span style="font-size:.72rem;color:{MUTED}">/ ano</span></div>
                        </div>{aviso}</div>""",
                        unsafe_allow_html=True,
                    )
                    st.plotly_chart(gauge(r["margem"]), width="stretch",
                                    key=f"g_{r['ticker']}", config={"displayModeBar": False})
                    st.caption(f"Margem de segurança · Graham {brl(r['graham'])} · Bazin {brl(r['bazin'])}")

    with t_comp:
        df = pd.DataFrame([{
            "Ticker": r["ticker"], "Preço": r["preco"], "Preço justo": r["justo"],
            "Margem (%)": r["margem"], "Status": r["status"],
        } for r in resultados])

        fig = go.Figure()
        fig.add_bar(x=df["Ticker"], y=df["Preço"], name="Preço atual", marker_color="#6b7a8f")
        fig.add_bar(x=df["Ticker"], y=df["Preço justo"], name="Preço justo", marker_color="#7fae93")
        fig.update_layout(barmode="group", height=340, legend=dict(orientation="h", y=1.1), **PLOT)
        fig.update_yaxes(**GRID)
        st.plotly_chart(fig, width="stretch")

        d2 = df.dropna(subset=["Margem (%)"]).sort_values("Margem (%)")
        if not d2.empty:
            fig2 = go.Figure(go.Bar(
                x=d2["Margem (%)"], y=d2["Ticker"], orientation="h",
                marker_color=[BAD if m < 0 else GOOD if m >= margem_alvo else FAIR for m in d2["Margem (%)"]],
                text=[f"{m:.1f}%" for m in d2["Margem (%)"]], textposition="outside"))
            fig2.update_layout(title="Margem de segurança", height=90 + 46 * len(d2), **PLOT)
            fig2.update_xaxes(**GRID)
            st.plotly_chart(fig2, width="stretch")

        st.dataframe(df.style.format({"Preço": "R$ {:.2f}", "Preço justo": "R$ {:.2f}",
                                      "Margem (%)": "{:.1f}%"}, na_rep="—"),
                     width="stretch", hide_index=True)


def pagina_valuation(dados):
    linhas = []
    for tk, d in dados.items():
        m = multiplos(d)
        linhas.append({
            "Ticker": tk, "Preço": d["preco"], "P/L": m["pl"], "P/VP": m["pvp"],
            "EV/EBITDA": d["ev_ebitda"], "DY 12m (%)": m["dy"], "ROE (%)": m["roe"],
            "Margem líq. (%)": m["margem"], "Dív./PL (%)": d["div_pl"],
        })
    df = pd.DataFrame(linhas)
    metricas = [c for c in df.columns if c not in ("Ticker", "Preço")]
    metrica = st.selectbox("Comparar por", metricas)

    d2 = df.dropna(subset=[metrica]).sort_values(metrica)
    if d2.empty:
        st.info("Sem dados disponíveis para esse indicador nos ativos selecionados.")
    else:
        fig = go.Figure(go.Bar(x=d2["Ticker"], y=d2[metrica], marker_color="#6b7a8f",
                               text=[f"{v:.2f}" for v in d2[metrica]], textposition="outside"))
        fig.update_layout(title=metrica, height=340, **PLOT)
        fig.update_yaxes(**GRID)
        st.plotly_chart(fig, width="stretch")

    st.dataframe(df.style.format({c: "{:.2f}" for c in df.columns if c != "Ticker"}, na_rep="—"),
                 width="stretch", hide_index=True)
    st.caption("P/L = preço ÷ LPA · P/VP = preço ÷ VPA (LPA/VPA em R$, convertidos do dólar quando o balanço "
               "é em US$) · DY 12m = proventos dos últimos 12 meses ÷ preço · Dív./PL = dívida bruta ÷ "
               "patrimônio líquido, em %. Indicadores de balanço vêm da Brapi (CVM) e podem estar defasados.")


def pagina_caixa(dados):
    st.markdown("#### Fluxo de caixa histórico")
    tk = st.selectbox("Ativo", list(dados), key="cx_ativo")
    caixa, fonte_cx = caixa_ajustada(dados[tk])
    if caixa.empty:
        st.info(f"Sem dados de fluxo de caixa em R$ para {tk}.")
    else:
        cores = {"Caixa operacional": "#6b7a8f", "Caixa de investimento": "#c08580",
                 "Fluxo de caixa livre": "#7fae93"}
        fig = go.Figure()
        for col in caixa.columns:
            fig.add_bar(x=[str(a) for a in caixa.index], y=caixa[col] / 1e6, name=col,
                        marker_color=cores.get(col))
        fig.update_layout(barmode="group", height=340, title="R$ milhões por ano",
                          legend=dict(orientation="h", y=1.12), **PLOT)
        fig.update_yaxes(**GRID)
        st.plotly_chart(fig, width="stretch")
        st.dataframe((caixa / 1e6).T.style.format("{:,.0f}", na_rep="—"), width="stretch")
        st.caption(f"Fonte: {fonte_cx}. Na Brapi, fluxo livre = caixa operacional + caixa de investimento; "
                   "no Yahoo, fluxo livre = caixa operacional − capex.")
        if dados[tk]["fx_cambio"] and dados[tk]["moeda"] == "USD":
            st.caption(f"Valores convertidos de US$ para R$ ao câmbio atual (R$ {dados[tk]['fx_cambio']:.2f}).")

    st.markdown("#### Valor estimado por fluxo de caixa descontado (DCF)")
    c1, c2, c3 = st.columns(3)
    taxa = c1.slider("Taxa de desconto", 8.0, 20.0, 12.0, 0.5, format="%.1f%%") / 100
    g = c2.slider("Crescimento do FCL (5 anos)", -5.0, 15.0, 4.0, 0.5, format="%.1f%%") / 100
    gp = c3.slider("Crescimento na perpetuidade", 0.0, 5.0, 3.0, 0.5, format="%.1f%%") / 100

    descontar = st.checkbox("Descontar dívida líquida (recomendado)", value=True)

    linhas = []
    for t, d in dados.items():
        cx, _ = caixa_ajustada(d)
        valor, base, _ = dcf(cx, d["acoes"], d["divida_liq"], taxa, g, gp, descontar)
        margem = (valor - d["preco"]) / valor * 100 if valor and d["preco"] else None
        alerta = ""
        if valor and d["preco"] and not (0.25 <= valor / d["preco"] <= 4):
            alerta = "Valor muito distante do preço: confira moeda/unidades"
        elif descontar and d["divida_liq"] is None and valor:
            alerta = "Sem dívida líquida na API: não descontada"
        linhas.append({
            "Ticker": t,
            "FCL médio 3a (R$ mi)": base / 1e6 if base is not None and not pd.isna(base) else None,
            "Dív. líquida (R$ mi)": d["divida_liq"] / 1e6 if d["divida_liq"] is not None else None,
            "Valor DCF": valor, "Preço": d["preco"], "Margem (%)": margem, "Alerta": alerta})
    st.dataframe(pd.DataFrame(linhas).style.format({
        "FCL médio 3a (R$ mi)": "{:,.0f}", "Dív. líquida (R$ mi)": "{:,.0f}",
        "Valor DCF": "R$ {:.2f}", "Preço": "R$ {:.2f}", "Margem (%)": "{:.1f}%"}, na_rep="—"),
        width="stretch", hide_index=True)
    st.caption("Aproximação: FCL = caixa operacional + caixa de investimento (média dos últimos 3 anos), "
               "projetado por 5 anos + perpetuidade, descontado à taxa escolhida. Com a opção marcada, "
               "subtrai a dívida líquida (dívida total − caixa) e divide pelo nº de ações. "
               "Não é adequado para bancos e holdings financeiras, e fica em branco quando o FCL é negativo "
               "ou quando a taxa de desconto é menor ou igual à da perpetuidade.")


def pagina_dividendos(dados):
    fig = go.Figure()
    for d in dados.values():
        if len(d["div_ano"]):
            fig.add_bar(x=[str(a) for a in d["div_ano"].index], y=d["div_ano"].values, name=d["ticker"])
    fig.update_layout(barmode="group", title="Dividendos por ação (R$/ano)", height=360,
                      colorway=["#6b7a8f", "#7fae93", "#c2ad7e", "#c08580", "#9a8fb0", "#8fb0ad"], **PLOT)
    fig.update_yaxes(**GRID)
    st.plotly_chart(fig, width="stretch")

    linhas = []
    for t, d in dados.items():
        p = d["preco"]
        linhas.append({"Ticker": t, "Proventos 12m": d["div_12m"], "Média 5 anos": d["div_medio"],
                       "DY 12m (%)": d["div_12m"] / p * 100 if p and d["div_12m"] is not None else None,
                       "DY s/ média 5a (%)": d["div_medio"] / p * 100 if p and d["div_medio"] else None})
    st.dataframe(pd.DataFrame(linhas).style.format({
        "Proventos 12m": "R$ {:.2f}", "Média 5 anos": "R$ {:.2f}",
        "DY 12m (%)": "{:.2f}%", "DY s/ média 5a (%)": "{:.2f}%"}, na_rep="—"),
        width="stretch", hide_index=True)
    st.caption("Proventos em dinheiro (dividendos + JCP) agrupados pelo ano de pagamento. "
               "A média usa os últimos 5 anos completos.")


# ---------------------------------------------------------------- página: técnica
def tradingview(ticker: str, intervalo: str, altura: int):
    """Gráfico limpo oficial do TradingView (widget embutido, sem sinais)."""
    cfg = {
        "autosize": True, "symbol": f"BMFBOVESPA:{ticker}", "interval": intervalo,
        "timezone": "America/Sao_Paulo", "theme": "dark", "style": "1", "locale": "br",
        "enable_publishing": False, "hide_side_toolbar": True, "allow_symbol_change": False,
        "backgroundColor": BG, "toolbar_bg": BG, "gridColor": "#262a33", "container_id": "tv_chart",
    }
    html = f"""
    <style>body{{margin:0;background:{BG};}}</style>
    <div style="height:{altura}px;width:100%;"><div id="tv_chart" style="height:100%;width:100%;"></div></div>
    <script src="https://s3.tradingview.com/tv.js"></script>
    <script>new TradingView.widget({json.dumps(cfg)});</script>"""
    components.html(html, height=altura)


def pagina_tecnica(ativos):
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.4])
    ticker = c1.selectbox("Ativo", ativos, key="tec_ativo")
    tf = c2.selectbox("Timeframe", ["Diário", "Semanal"])
    periodo_lbl = c3.selectbox("Período", ["6 meses", "1 ano", "2 anos", "5 anos"], index=1)
    layout = c4.radio("Exibição", ["Empilhado", "Lado a lado"], horizontal=True)

    with st.expander("Sinais e parâmetros"):
        e1, e2 = st.columns(2)
        grupos = e1.multiselect("Grupos de sinais",
                                ["Candlestick", "Padrões gráficos", "Indicadores (MM, IFR, volume)"],
                                default=["Candlestick", "Padrões gráficos", "Indicadores (MM, IFR, volume)"])
        candles_sel = e2.multiselect("Padrões de candle", tec.CANDLE_NOMES,
                                     default=[n for n in tec.CANDLE_NOMES if n != "Doji"])
        p1, p2, p3 = st.columns(3)
        mm_c = p1.number_input("Média móvel curta", 5, 100, 21)
        mm_l = p2.number_input("Média móvel longa", 10, 300, 50)
        mostrar_mm = p3.checkbox("Mostrar médias no gráfico", value=True)

    intervalo, tv_int = {"Diário": ("1d", "D"), "Semanal": ("1wk", "W")}[tf]
    periodo = {"6 meses": "6mo", "1 ano": "1y", "2 anos": "2y", "5 anos": "5y"}[periodo_lbl]
    df, erro, fonte_precos = historico(ticker, periodo, intervalo)
    if df.empty or len(df) < 30:
        msg = "Histórico insuficiente para esse ativo/período. Tente um período maior."
        if erro:
            msg += f" (Brapi: {erro})"
        st.warning(msg)
        return

    sinais, padroes, niveis = [], [], []
    ind = tec.indicadores(df, int(mm_c), int(mm_l))
    if "Candlestick" in grupos:
        sinais += [s for s in tec.candlesticks(df) if s["sinal"] in candles_sel]
    if "Padrões gráficos" in grupos:
        padroes, niveis = tec.padroes_graficos(df)
    if "Indicadores (MM, IFR, volume)" in grupos:
        sinais += ind["sinais"]

    # resumo dos últimos 10 candles
    corte = df.index[-10]
    rec = [s for s in sinais + padroes if s["data"] >= corte]
    m1, m2, m3 = st.columns(3)
    m1.metric("Sinais de alta (10 candles)", sum(s["tipo"] == "alta" for s in rec))
    m2.metric("Sinais de baixa (10 candles)", sum(s["tipo"] == "baixa" for s in rec))
    m3.metric("Indecisão (10 candles)", sum(s["tipo"] == "neutro" for s in rec))

    link = f"https://br.tradingview.com/chart/?symbol=BMFBOVESPA%3A{ticker}"
    lado = layout == "Lado a lado"
    alt_tv, alt_sinais = (620, 620) if lado else (520, 720)

    def bloco_limpo():
        st.markdown("#### Gráfico limpo · TradingView")
        tradingview(ticker, tv_int, alt_tv)
        st.link_button("Abrir no TradingView ↗", link)

    def bloco_sinais():
        st.markdown("#### Gráfico com sinais")
        fig = tec.figura(df, sinais, padroes, niveis, ind, diario=(tf == "Diário"),
                         altura=alt_sinais, mostrar_mm=mostrar_mm)
        st.plotly_chart(fig, width="stretch", config={"displaylogo": False})

    if lado:
        a, b = st.columns(2)
        with a:
            bloco_limpo()
        with b:
            bloco_sinais()
    else:
        bloco_limpo()
        bloco_sinais()

    st.markdown("#### Sinais recentes")
    linhas = [{"Data": s["data"], "Categoria": s["categoria"], "Sinal": s["sinal"],
               "Viés": s["tipo"].capitalize(), "Preço": s["preco"]} for s in sinais]
    linhas += [{"Data": p["data"], "Categoria": p["categoria"], "Sinal": p["nome"],
                "Viés": p["tipo"].capitalize(), "Preço": p["preco"]} for p in padroes]
    if linhas:
        tabela = pd.DataFrame(linhas).sort_values("Data", ascending=False).head(30)
        st.dataframe(tabela, width="stretch", hide_index=True, column_config={
            "Data": st.column_config.DatetimeColumn(format="DD/MM/YYYY"),
            "Preço": st.column_config.NumberColumn(format="R$ %.2f"),
        })
    else:
        st.caption("Nenhum sinal detectado com os filtros atuais.")
    if niveis:
        st.caption("Níveis detectados: " + " · ".join(
            f"{n['tipo']} R$ {n['preco']:.2f} ({n['toques']} toques)" for n in niveis))
    st.caption(f"O gráfico limpo é o widget oficial do TradingView. Os sinais são detectados pelo app com regras "
               f"simples sobre os preços de {fonte_precos} (o TradingView não permite buscar os desenhos ou "
               f"sinais de volta), então podem divergir do que você marcaria à mão.")


# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.markdown("### Ativos")
    with st.form("add", clear_on_submit=True):
        novo = st.text_input("Adicionar ticker(s)", placeholder="Ex.: WEGE3, TAEE11")
        if st.form_submit_button("Adicionar", width="stretch"):
            for t in novo.replace(";", ",").replace(" ", ",").split(","):
                t = normaliza(t)
                if t and t not in st.session_state.ativos:
                    st.session_state.ativos.append(t)

    st.session_state.ativos = st.multiselect(
        "Na análise", options=st.session_state.ativos, default=st.session_state.ativos
    )
    if st.button("Atualizar dados", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    with st.expander("Moeda do balanço (avançado)"):
        st.caption("Auto usa a moeda informada pela API (ou detecta). Force US$ se o LPA/VPA de um ativo "
                   "vier em dólar, como em empresas que reportam em dólar (ex.: Vale). "
                   "Preço e dividendos já são em R$.")
        for t in st.session_state.ativos:
            st.selectbox(t, ["Auto", "BRL", "USD"], key=f"moeda_{t}")
    if not _token():
        st.warning("Token da Brapi não configurado: só funcionam os tickers de teste "
                   "(PETR4, VALE3, MGLU3, ITUB4). Veja o topo do app.py.")
    if _yf() is None:
        st.info("Yahoo Finance como reserva está desligado: instale com pip install yfinance.")
    st.caption("Fonte principal: Brapi (B3/CVM). Reserva: Fundamentus e Yahoo Finance, só para o que a "
               "Brapi não trouxer (os cards avisam). Gráfico: TradingView.")

# ---------------------------------------------------------------- cabeçalho
st.markdown(
    f'<div class="topo"><span class="hero">Painel B3</span>'
    f'<span class="sub">Atualizado em {datetime.now():%d/%m/%Y %H:%M}</span></div>',
    unsafe_allow_html=True,
)

CATS = ["Fundamentalista", "Técnica"]
SECOES = ["Valuation", "Fluxo de caixa", "Preço justo", "Dividendos"]

categoria = st.segmented_control("Categoria", CATS, default=CATS[0], key="cat",
                                 label_visibility="collapsed") or CATS[0]
secao = None
if categoria == "Fundamentalista":
    secao = st.segmented_control("Seção", SECOES, default=SECOES[0], key="secao",
                                 label_visibility="collapsed") or SECOES[0]

if not st.session_state.ativos:
    st.info("Adicione um ticker na barra lateral para começar.")
    st.stop()

if categoria == "Técnica":
    pagina_tecnica(st.session_state.ativos)
else:
    dados = carregar(st.session_state.ativos)
    if not dados:
        st.stop()
    {"Valuation": pagina_valuation, "Fluxo de caixa": pagina_caixa,
     "Preço justo": pagina_preco_justo, "Dividendos": pagina_dividendos}[secao](dados)

st.caption("Ferramenta educacional. Graham, Bazin, DCF e sinais técnicos são modelos simplificados "
           "e não são recomendação de investimento.")
