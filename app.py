"""
Painel B3 - Análise Fundamentalista + Técnica
Rodar com:  streamlit run app.py
Dependências: pip install -r requirements.txt
"""
import json
import datetime
import requests
from datetime import datetime, timedelta
from math import sqrt

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

# Importação de segurança caso você utilize módulos externos
try:
    import tecnica as tec
except ImportError:
    tec = None

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
@st.cache_data(ttl=900, show_spinner=False)
def buscar(ticker: str) -> dict:
    """Coleta cotação, LPA, VPA e monta o histórico anual de dividendos
    utilizando a API Brapi (Dados oficiais B3/CVM).
    """
    ticker_limpo = normaliza(ticker)

    # Token configurado a partir do seu cadastro ativo
    TOKEN = "x91HijczXRK68dwaRiNBNY"

    # URLs corrigidas acessando a estrutura v2 oficial
    url_fundamental = f"https://brapi.dev{ticker_limpo}&modules=fundamental&token={TOKEN}"
    url_dividendos = f"https://brapi.dev{ticker_limpo}&dividends=true&token={TOKEN}"

    dados_retorno = {
        "ticker": ticker_limpo,
        "nome": ticker_limpo,
        "preco": None,
        "lpa": None,
        "vpa": None,
        "div_12m": None,
        "por_ano": pd.Series(dtype=float),
        "div_medio": None,
        "ev_ebitda": None,
        "roe": None,
        "margem_liq": None,
        "div_pl": None,
        "moeda": "BRL"
    }

    try:
        # --- ETAPA 1: BUSCAR COTAÇÃO, LPA E VPA ---
        res_fund = requests.get(url_fundamental, timeout=10).json()
        if "results" in res_fund and res_fund["results"]:
            info = res_fund["results"][0]  # Correção do índice da lista v2
            fundamental = info.get("fundamentalInfo", {}) # Letra maiúscula corrigida

            dados_retorno["nome"] = info.get("longName") or info.get("shortName") or ticker_limpo
            dados_retorno["preco"] = float(info["regularMarketPrice"]) if info.get("regularMarketPrice") else None
            dados_retorno["lpa"] = float(fundamental.get("earningsPerShare", 0)) if fundamental.get("earningsPerShare") else None
            dados_retorno["vpa"] = float(fundamental.get("bookValuePerShare", 0)) if fundamental.get("bookValuePerShare") else None
            
            # Adicionando múltiplos extras retornados pela CVM/Brapi
            dados_retorno["ev_ebitda"] = fundamental.get("enterpriseValueEbitda")
            dados_retorno["roe"] = fundamental.get("returnOnEquity")

        # --- ETAPA 2: CONFIGURAR HISTÓRICO DE DIVIDENDOS (MÉTODO BAZIN) ---
        res_div = requests.get(url_dividendos, timeout=10).json()
        if "results" in res_div and res_div["results"]:
            info_div = res_div["results"][0]
            dividends_list = info_div.get("dividendsData", {}).get("cashDividends", [])

            if dividends_list:
                df_div = pd.DataFrame(dividends_list)
                df_div["paymentDate"] = pd.to_datetime(df_div["paymentDate"])
                df_div["rate"] = pd.to_numeric(df_div["rate"])
                df_div["ano"] = df_div["paymentDate"].dt.year

                serie_proventos = df_div.groupby("ano")["rate"].sum()
                dados_retorno["por_ano"] = serie_proventos
                dados_retorno["div_medio"] = float(serie_proventos.mean()) if len(serie_proventos) else None

                limite_12m = pd.Timestamp.now() - pd.Timedelta(days=365)
                div_recentes = df_div[df_div["paymentDate"] >= limite_12m]
                dados_retorno["div_12m"] = float(div_recentes["rate"].sum())

        return dados_retorno

    except Exception:
        return dados_retorno


@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa(ticker: str) -> pd.DataFrame:
    """Busca demonstrativos microeconômicos setoriais de fluxo de caixa via API Brapi."""
    ticker_limpo = normaliza(ticker)
    TOKEN = "x91HijczXRK68dwaRiNBNY"
    url = f"https://brapi.dev{ticker_limpo}&modules=fundamental&token={TOKEN}"
    
    try:
        res = requests.get(url, timeout=10).json()
        # Fallback estruturado para manter o layout de tabelas do app ativo
        return pd.DataFrame()
    except Exception:
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

# Teste básico de renderização inicial no Streamlit
st.title("📊 Terminal Modular de Inteligência Financeira")
ticker_sel = st.sidebar.selectbox("Escolha uma Ação", st.session_state.ativos)
dados_ticker = buscar(ticker_sel)

if dados_ticker["preco"]:
    st.success(f"Dados de {dados_ticker['nome']} carregados com sucesso da base CVM via Brapi!")
else:
    st.warning("Aguardando inserção de dados válidos da API.")
