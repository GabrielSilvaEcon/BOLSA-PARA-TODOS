"""
Painel B3 - Análise Fundamentalista + Técnica + Macro & Micro (Versão Blindada)

Rodar com: streamlit run app.py

Dependências: pip install -r requirements.txt (streamlit>=1.49, pandas, plotly, requests, yfinance, fundamentus)

Token da Brapi (NUNCA coloque o token direto no código):
- Local: crie o arquivo .streamlit/secrets.toml com a linha BRAPI_TOKEN = "seu_token_aqui"
- Ou defina a variável de ambiente BRAPI_TOKEN.
"""

import json
import os
from datetime import datetime
from math import sqrt

import fundamentus
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

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
.bad {{background:rgba(192,133,128,.14); color:{BAD};}}
.na {{background:rgba(139,145,156,.14); color:{MUTED};}}
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

if "fonte_dados" not in st.session_state:
    st.session_state.fonte_dados = "Yahoo Finance"

def normaliza(t: str) -> str:
    return t.upper().strip().replace(".SA", "")

# ---------------------------------------------------------------- Clientes de Dados

# --- 1. Brapi ---
BRAPI = "https://brapi.dev/api"

def _token() -> str:
    try:
        t = st.secrets.get("BRAPI_TOKEN")
    except Exception:
        t = None
    return str(t or os.environ.get("BRAPI_TOKEN") or "").strip()

def _get(path: str, params: dict | None = None):
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
    if isinstance(js, dict):
        res = js.get("results")
        if isinstance(res, list) and res:
            return res[0]
    return None

def _num(x):
    """Regra de Ouro: Tratamento seguro de números e vazios (NaN)"""
    try:
        if x is None or pd.isna(x):
            return None
        val = float(x)
        return None if pd.isna(val) else val
    except (TypeError, ValueError):
        return None

def _proventos(lista):
    vazio = pd.Series(dtype=float)
    if not lista:
        return vazio, None, None
    try:
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

        completos = por_ano[por_ano.index < hoje.year].tail(5)
        base = completos if len(completos) else por_ano
        return por_ano, float(base.mean()) if not base.empty else 0.0, div_12m
    except Exception:
        return vazio, None, None

def buscar_brapi(ticker: str) -> dict:
    tk = normaliza(ticker)
    d = {
        "ticker": tk, "nome": tk, "preco": None, "lpa": None, "vpa": None,
        "div_ano": pd.Series(dtype=float), "div_medio": None, "div_12m": None,
        "ev_ebitda": None, "roe": None, "margem_liq": None, "div_pl": None,
        "acoes": None, "moeda": "BRL", "erro": None,
    }
    erros = []
    try:
        js, err = _get(f"/quote/{tk}", {"dividends": "true"})
        if err:
            erros.append(f"cotação: {err}")
        q = _primeiro(js)
        lista_div = None
        if q:
            d["nome"] = q.get("longName") or q.get("shortName") or tk
            d["preco"] = _num(q.get("regularMarketPrice"))
            d["lpa"] = _num(q.get("earningsPerShare"))
            d["moeda"] = q.get("currency") or "BRL"
            lista_div = (q.get("dividendsData") or {}).get("cashDividends")

        if lista_div is None:
            js, err = _get("/v2/stocks/dividends", {"symbols": tk})
            if err:
                erros.append(f"dividendos: {err}")
            item = _primeiro(js)
            if item:
                lista_div = (item.get("data") or {}).get("cashDividends")
        d["div_ano"], d["div_medio"], d["div_12m"] = _proventos(lista_div)

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

        js, err = _get("/v2/stocks/financial-data", {"symbols": tk})
        if err:
            erros.append(f"dados financeiros: {err}")
        item = _primeiro(js)
        fin = (item or {}).get("data") or {}
        if isinstance(fin, dict):
            d["roe"] = _num(fin.get("returnOnEquity"))
            d["margem_liq"] = _num(fin.get("profitMargins")) if _num(fin.get("profitMargins")) is not None else d["margem_liq"]
            dpl = _num(fin.get("debtToEquity"))
            d["div_pl"] = dpl * 100 if dpl is not None else None
            if fin.get("financialCurrency"):
                d["moeda"] = fin["financialCurrency"]
    except Exception as e:
        erros.append(f"exceção brapi: {e}")

    d["erro"] = "; ".join(erros) or None
    return d

def buscar_caixa_brapi(ticker: str) -> pd.DataFrame:
    try:
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
    except Exception:
        return pd.DataFrame()

def historico_brapi(ticker: str, periodo: str, intervalo: str):
    try:
        js, err = _get(f"/quote/{normaliza(ticker)}", {"range": periodo, "interval": intervalo})
        item = _primeiro(js)
        dados = (item or {}).get("historicalDataPrice")
        if not dados:
            return pd.DataFrame(), err or "a API não devolveu histórico para esse ativo/período"
        df = pd.DataFrame(dados).rename(columns={
            "date": "Date", "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "volume": "Volume"})
        df["Date"] = (pd.to_datetime(df["Date"], unit="s", utc=True)
                      .dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None).dt.normalize())
        df = df.drop_duplicates("Date").set_index("Date").sort_index()
        df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
        return df.dropna(subset=["Open", "High", "Low", "Close"]), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# --- 2. Yahoo Finance (Com Fallback Seguro) ---
@st.cache_data(ttl=900, show_spinner=False)
def buscar_yahoo(ticker: str) -> dict:
    tk = normaliza(ticker) + ".SA"
    d = {
        "ticker": normaliza(ticker), "nome": normaliza(ticker), "preco": None, "lpa": None, "vpa": None,
        "div_ano": pd.Series(dtype=float), "div_medio": None, "div_12m": None,
        "ev_ebitda": None, "roe": None, "margem_liq": None, "div_pl": None,
        "acoes": None, "moeda": "BRL", "erro": None,
    }
    try:
        t = yf.Ticker(tk)
        info = t.info
        d["nome"] = info.get("longName") or info.get("shortName") or normaliza(ticker)
        d["preco"] = _num(info.get("currentPrice") or info.get("regularMarketPrice"))
        d["lpa"] = _num(info.get("trailingEps"))
        d["vpa"] = _num(info.get("bookValue"))
        d["ev_ebitda"] = _num(info.get("enterpriseToEbitda"))
        d["roe"] = _num(info.get("returnOnEquity"))
        d["margem_liq"] = _num(info.get("profitMargins"))
        debt_to_equity = _num(info.get("debtToEquity"))
        d["div_pl"] = debt_to_equity if debt_to_equity is not None else None
        d["acoes"] = _num(info.get("sharesOutstanding"))
        d["moeda"] = info.get("currency") or "BRL"

        divs = t.dividends
        if not divs.empty:
            divs.index = pd.to_datetime(divs.index).tz_localize(None)
            por_ano = divs.groupby(divs.index.year).sum()
            por_ano.index = por_ano.index.astype(int)
            por_ano.index.name = "ano"
            hoje = pd.Timestamp.now()
            mask12 = (divs.index >= hoje - pd.Timedelta(days=365)) & (divs.index <= hoje)
            div_12m = float(divs.loc[mask12].sum())
            completos = por_ano[por_ano.index < hoje.year].tail(5)
            base = completos if len(completos) else por_ano
            d["div_ano"] = por_ano
            d["div_medio"] = float(base.mean()) if not base.empty else 0.0
            d["div_12m"] = div_12m
    except Exception as e:
        d["erro"] = f"Erro Yahoo Finance: {e}"
    return d

@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa_yahoo(ticker: str) -> pd.DataFrame:
    tk = normaliza(ticker) + ".SA"
    try:
        t = yf.Ticker(tk)
        cf = t.cashflow
        if cf.empty:
            return pd.DataFrame()
        cf = cf.T
        nomes = {
            "Operating Cash Flow": "Caixa operacional",
            "Investing Cash Flow": "Caixa de investimento",
            "Free Cash Flow": "Fluxo de caixa livre",
        }
        cols = [k for k in nomes if k in cf.columns]
        if not cols:
            return pd.DataFrame()
        out = cf[cols].apply(pd.to_numeric, errors="coerce").rename(columns=nomes)
        out.index = pd.to_datetime(out.index).year
        out = out[out.index.notna()]
        out.index = out.index.astype(int)
        return out.dropna(how="all").sort_index()
    except Exception:
        return pd.DataFrame()

def historico_yahoo(ticker: str, periodo: str, intervalo: str):
    tk = normaliza(ticker) + ".SA"
    map_periodo = {"6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y"}
    p = map_periodo.get(periodo, "1y")
    try:
        df = yf.download(tk, period=p, interval=intervalo, progress=False)
        if df.empty:
            return pd.DataFrame(), "Sem dados históricos do Yahoo."
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df.rename(columns={"Open": "Open", "High": "High", "Low": "Low", "Close": "Close", "Volume": "Volume"})
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
        return df.dropna(subset=["Open", "High", "Low", "Close"]), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# --- 3. Fundamentus (Com Fallback Seguro) ---
@st.cache_data(ttl=900, show_spinner=False)
def buscar_fundamentus(ticker: str) -> dict:
    tk = normaliza(ticker)
    d = {
        "ticker": tk, "nome": tk, "preco": None, "lpa": None, "vpa": None,
        "div_ano": pd.Series(dtype=float), "div_medio": None, "div_12m": None,
        "ev_ebitda": None, "roe": None, "margem_liq": None, "div_pl": None,
        "acoes": None, "moeda": "BRL", "erro": None,
    }
    try:
        df = fundamentus.get_detalhes_papel(tk)
        if df is None or df.empty:
            d["erro"] = "Ativo não encontrado no Fundamentus."
            return d
        if tk in df.index:
            row = df.loc[tk]
        else:
            row = df.iloc[0]

        def _conv(val):
            if pd.isna(val):
                return None
            if isinstance(val, (int, float)):
                return float(val)
            try:
                clean = str(val).replace(".", "").replace(",", ".").replace("%", "").strip()
                return float(clean)
            except Exception:
                return None

        d["preco"] = _conv(row.get("Cotacao"))
        d["lpa"] = _conv(row.get("LPA"))
        d["vpa"] = _conv(row.get("VPA"))
        d["ev_ebitda"] = _conv(row.get("EV_EBITDA"))
        roe = _conv(row.get("ROE"))
        d["roe"] = roe / 100.0 if roe is not None else None

        m_liq = _conv(row.get("Marg_Liquida"))
        d["margem_liq"] = m_liq / 100.0 if m_liq is not None else None

        div_br_patr = _conv(row.get("Div_Br_Patrim"))
        d["div_pl"] = div_br_patr * 100 if div_br_patr is not None else None

        dy = _conv(row.get("Div_Yield"))
        if dy is not None and d["preco"]:
            d["div_12m"] = (dy / 100.0) * d["preco"]
            d["div_medio"] = d["div_12m"]
    except Exception as e:
        d["erro"] = f"Erro Fundamentus: {e}"
    return d

def buscar_caixa_fundamentus(ticker: str) -> pd.DataFrame:
    return pd.DataFrame()


# --- 4. Banco Central do Brasil (Macro) ---
@st.cache_data(ttl=3600, show_spinner=False)
def buscar_macro_bcb(codigo_serie: int) -> pd.DataFrame:
    """
    432 - Taxa SELIC meta (% a.a.)
    433 - IPCA (% mensal)
    10813 - Dólar PTAX (Venda)
    """
    url = f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados?formato=json"
    try:
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            df = pd.DataFrame(r.json())
            df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
            df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
            return df.set_index("data").sort_index()
    except Exception as e:
        st.error(f"Erro ao buscar série {codigo_serie} no BCB: {e}")
    return pd.DataFrame()


# ---------------------------------------------------------------- Funções unificadas com Fallback Automático
def buscar(ticker: str) -> dict:
    fonte = st.session_state.get("fonte_dados", "Yahoo Finance")
    d = {}
    if fonte == "Brapi":
        d = buscar_brapi(ticker)
    elif fonte == "Fundamentus":
        d = buscar_fundamentus(ticker)
    else:
        d = buscar_yahoo(ticker)
    
    # Regra de Ouro: Fallback automático se a fonte principal falhar ou retornar preço nulo
    if (d.get("preco") is None or d.get("preco") == 0) and fonte != "Yahoo Finance":
        d_fb = buscar_yahoo(ticker)
        if d_fb.get("preco") is not None and d_fb.get("preco") > 0:
            d = d_fb
            d["erro"] = (d.get("erro", "") or "") + " [Fallback ativado: dados recuperados do Yahoo Finance]"
            
    return d

def buscar_caixa(ticker: str) -> pd.DataFrame:
    fonte = st.session_state.get("fonte_dados", "Yahoo Finance")
    if fonte == "Brapi":
        df = buscar_caixa_brapi(ticker)
        if df.empty:
            df = buscar_caixa_yahoo(ticker)
        return df
    elif fonte == "Fundamentus":
        return buscar_caixa_yahoo(ticker)
    else:
        return buscar_caixa_yahoo(ticker)

def historico(ticker: str, periodo: str, intervalo: str):
    fonte = st.session_state.get("fonte_dados", "Yahoo Finance")
    if fonte == "Brapi":
        df, err = historico_brapi(ticker, periodo, intervalo)
        if not df.empty:
            return df, err
    return historico_yahoo(ticker, periodo, intervalo)

def carregar(ativos):
    out = {}
    with st.spinner(f"Buscando dados via {st.session_state.get('fonte_dados', 'Yahoo Finance')}..."):
        for tk in ativos:
            try:
                d = buscar(tk)
            except Exception as e:
                st.warning(f"Não consegui carregar {tk}: {e}")
                continue
            if d.get("preco") is None and d.get("erro"):
                st.warning(f"{tk}: {d['erro']}")
            out[tk] = d
    return out


# ---------------------------------------------------------------- Cálculos Blindados (Regras de Ouro)
def analisar(d: dict, metodo: str, yield_alvo: float, margem_alvo: float) -> dict:
    lpa = d.get("lpa")
    vpa = d.get("vpa")
    preco = d.get("preco")
    div_medio = d.get("div_medio")

    # Regra de Ouro: Graham Blindado (Evita raiz de número negativo ou prejuízo)
    graham = None
    if lpa is not None and vpa is not None and lpa > 0 and vpa > 0:
        try:
            graham = sqrt(22.5 * lpa * vpa)
        except Exception:
            graham = None

    # Regra de Ouro: Bazin Blindado (Evita divisão por zero)
    bazin = None
    if div_medio is not None and div_medio > 0 and yield_alvo > 0:
        bazin = div_medio / (yield_alvo / 100)

    if metodo == "Graham":
        justo = graham
    elif metodo == "Bazin":
        justo = bazin
    else:
        vals = [v for v in (graham, bazin) if v is not None and v > 0]
        justo = sum(vals) / len(vals) if vals else None

    # Regra de Ouro: Margem de Segurança blindada contra divisão por zero
    margem = None
    if justo is not None and preco is not None and justo > 0:
        margem = (justo - preco) / justo * 100

    if margem is None:
        status, cls = "Sem dados", "na"
    elif margem >= margem_alvo:
        status, cls = "Com margem", "good"
    elif margem >= 0:
        status, cls = "Preço justo", "fair"
    else:
        status, cls = "Acima do justo", "bad"

    return {**d, "graham": graham, "bazin": bazin, "justo": justo,
            "margem": margem, "status": status, "cls": cls}

def multiplos(d: dict) -> dict:
    p = d.get("preco")
    lpa = d.get("lpa")
    vpa = d.get("vpa")
    div_12m = d.get("div_12m")
    roe = d.get("roe")
    margem_liq = d.get("margem_liq")

    # Regra de Ouro: Proteção contra Divisão por Zero em Múltiplos
    return {
        "pl": p / lpa if p and lpa and lpa > 0 else None,
        "pvp": p / vpa if p and vpa and vpa > 0 else None,
        "dy": div_12m / p * 100 if p and p > 0 and div_12m is not None else None,
        "roe": roe * 100 if roe is not None else None,
        "margem": margem_liq * 100 if margem_liq is not None else None,
    }

def dcf(caixa: pd.DataFrame, acoes, moeda: str, taxa: float, g: float, gp: float):
    # Regra de Ouro: Validação contra moedas estrangeiras, ações nulas e denominadores inválidos
    if moeda != "BRL" or not acoes or acoes <= 0 or caixa.empty or "Fluxo de caixa livre" not in caixa:
        return None, None
    try:
        base = caixa["Fluxo de caixa livre"].dropna().tail(3).mean()
        if pd.isna(base) or base <= 0:
            return None, base
        if taxa <= gp:
            return None, base
        pv = sum(base * (1 + g) ** t / (1 + taxa) ** t for t in range(1, 6))
        vt = base * (1 + g) ** 5 * (1 + gp) / (taxa - gp)
        val_Acao = (pv + vt / (1 + taxa) ** 5) / acoes
        return val_Acao, base
    except Exception:
        return None, None

def brl(v):
    return "—" if v is None or pd.isna(v) else f"R$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

def gauge(margem):
    v = 0 if margem is None or pd.isna(margem) else max(-60, min(60, margem))
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
    st.caption("Graham = √(22,5 × LPA × VPA) · Bazin = dividendo médio dos últimos 5 anos completos ÷ yield desej
