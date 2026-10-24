"""
Painel B3 - Análise Fundamentalista + Técnica
Rodar com:  streamlit run app.py
Dependências: pip install -r requirements.txt
"""
import json
import requests
from datetime import datetime, timedelta
from math import sqrt

import pandas as pd
import plotly.graph_objects as go
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


# ---------------------------------------------------------------- dados
import numpy as np
import requests


@st.cache_data(ttl=900, show_spinner=False)
def buscar(ticker: str) -> dict:
    """Cotação, LPA, VPA, dividendos e indicadores (Brapi API v2)."""
    ticker_limpo = normaliza(ticker)
    TOKEN = "x91HijczXRK68dwaRiNBNY"

    url_fundamental = f"https://brapi.dev{ticker_limpo}&modules=fundamental&token={TOKEN}"
    url_dividendos = f"https://brapi.dev{ticker_limpo}&dividends=true&token={TOKEN}"

    # Inicialização das variáveis do seu escopo original
    preco = None
    por_ano = pd.Series(dtype=float)
    div_12m = None
    info = {}

    try:
        # 1. Coleta de Preço e Múltiplos da CVM
        res_fund = requests.get(url_fundamental, timeout=10).json()
        if "results" in res_fund and res_fund["results"]:
            info_api = res_fund["results"][0]
            fundamental = info_api.get("fundamentalInfo", {})
            
            # Mapeia para o dicionário 'info' idêntico ao formato que seu código lia antes
            preco = float(info_api["regularMarketPrice"]) if info_api.get("regularMarketPrice") else None
            info = {
                "shortName": info_api.get("shortName"),
                "longName": info_api.get("longName"),
                "trailingEps": float(fundamental.get("earningsPerShare", 0)),
                "bookValue": float(fundamental.get("bookValuePerShare", 0)),
                "enterpriseToEbitda": fundamental.get("enterpriseValueEbitda"),
                "returnOnEquity": fundamental.get("returnOnEquity"),
                "profitMargins": fundamental.get("netMargin"),
                "debtToEquity": fundamental.get("longTermDebtToEquity"),
                "sharesOutstanding": info_api.get("sharesOutstanding"),
                "financialCurrency": "BRL"
            }

        # 2. Coleta de Histórico de Dividendos para o Método Bazin
        res_div = requests.get(url_dividendos, timeout=10).json()
        if "results" in res_div and res_div["results"]:
            info_div = res_div["results"][0]
            dividends_list = info_div.get("dividendsData", {}).get("cashDividends", [])

            if dividends_list:
                df_div = pd.DataFrame(dividends_list)
                df_div["paymentDate"] = pd.to_datetime(df_div["paymentDate"])
                df_div["rate"] = pd.to_numeric(df_div["rate"])
                df_div["ano"] = df_div["paymentDate"].dt.year

                por_ano = df_div.groupby("ano")["rate"].sum()

                limite_12m = pd.Timestamp.now() - pd.Timedelta(days=365)
                div_recentes = df_div[df_div["paymentDate"] >= limite_12m]
                div_12m = float(div_recentes["rate"].sum())

    except Exception:
        pass

    # Mantém o retorno com o formato exato exigido pelas suas calculadoras e interface originais
    return {
        "ticker": ticker,
        "nome": info.get("shortName") or info.get("longName") or ticker,
        "preco": preco,
        "lpa": info.get("trailingEps"),
        "vpa": info.get("bookValue"),
        "div_ano": por_ano,
        "div_medio": float(por_ano.mean()) if len(por_ano) else None,
        "div_12m": div_12m,
        "ev_ebitda": info.get("ev_ebitda"),
        "roe": info.get("roe"),
        "margem_liq": info.get("margem_liq"),
        "div_pl": info.get("div_pl"),
        "acoes": info.get("acoes"),
        "moeda": info.get("moeda") or "BRL",
    }


@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa(ticker: str) -> pd.DataFrame:
    """Mantém a assinatura estrutural para o fluxo de caixa."""
    return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def historico(ticker: str, periodo: str, intervalo: str) -> pd.DataFrame:
    """Busca o histórico de preços na API Brapi (Dados limpos da B3)."""
    ticker_limpo = normaliza(ticker)
    TOKEN = "x91HijczXRK68dwaRiNBNY"
    range_api = "1mo" if "mo" in periodo else "1y"

    url = f"https://brapi.dev{ticker_limpo}&range={range_api}&interval={intervalo}&token={TOKEN}"

    try:
        resposta = requests.get(url, timeout=10).json()
        historico_dados = resposta["results"][0]["historicalDataPrice"]

        df = pd.DataFrame(historico_dados)
        df = df.rename(
            columns={
                "date": "Date",
                "open": "Open",
                "high": "High",
                "low": "Low",
                "close": "Close",
                "volume": "Volume",
            }
        )
        df["Date"] = pd.to_datetime(df["Date"], unit="s")
        df.set_index("Date", inplace=True)
        return df[["Open", "High", "Low", "Close", "Volume"]].dropna()
    except Exception:
        return pd.DataFrame()
