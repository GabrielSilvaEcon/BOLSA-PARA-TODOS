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
from datetime import datetime
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


# ---------------------------------------------------------------- dados
@st.cache_data(ttl=900, show_spinner=False)
def buscar(ticker: str) -> dict:
    """Cotação, LPA/VPA, múltiplos e proventos de um ativo via Brapi."""
    tk = normaliza(ticker)
    d = {
        "ticker": tk, "nome": tk, "preco": None, "lpa": None, "vpa": None,
        "div_ano": pd.Series(dtype=float), "div_medio": None, "div_12m": None,
        "ev_ebitda": None, "roe": None, "margem_liq": None, "div_pl": None,
        "acoes": None, "moeda": "BRL", "erro": None,
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
        d["moeda"] = q.get("currency") or "BRL"
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
        if fin.get("financialCurrency"):
            d["moeda"] = fin["financialCurrency"]

    d["erro"] = "; ".join(erros) or None
    return d


@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa(ticker: str) -> pd.DataFrame:
    """Fluxo de caixa anual (operacional, investimento, livre) por ano, em R$."""
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


def carregar(ativos):
    out = {}
    with st.spinner("Buscando dados..."):
        for tk in ativos:
            try:
                d = buscar(tk)
            except Exception as e:
                st.warning(f"Não consegui carregar {tk}: {e}")
                continue
            if d["preco"] is None and d["erro"]:
                st.warning(f"{tk}: {d['erro']}")
            out[tk] = d
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

    return {**d, "graham": graham, "bazin": bazin, "justo": justo,
            "margem": margem, "status": status, "cls": cls}


def multiplos(d: dict) -> dict:
    p = d["preco"]
    return {
        "pl": p / d["lpa"] if p and d["lpa"] and d["lpa"] > 0 else None,
        "pvp": p / d["vpa"] if p and d["vpa"] and d["vpa"] > 0 else None,
        "dy": d["div_12m"] / p * 100 if p and d["div_12m"] is not None else None,
        "roe": d["roe"] * 100 if d["roe"] is not None else None,
        "margem": d["margem_liq"] * 100 if d["margem_liq"] is not None else None,
    }


def dcf(caixa: pd.DataFrame, acoes, moeda: str, taxa: float, g: float, gp: float):
    """Valor por ação a partir da média do FCL dos últimos 3 anos (aproximação)."""
    if moeda != "BRL" or not acoes or caixa.empty or "Fluxo de caixa livre" not in caixa:
        return None, None
    base = caixa["Fluxo de caixa livre"].dropna().tail(3).mean()
    if pd.isna(base) or base <= 0:
        return None, base
    pv = sum(base * (1 + g) ** t / (1 + taxa) ** t for t in range(1, 6))
    vt = base * (1 + g) ** 5 * (1 + gp) / (taxa - gp)
    return (pv + vt / (1 + taxa) ** 5) / acoes, base


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
                    aviso = (f'<div class="aviso">Balanço em {r["moeda"]}: LPA/VPA podem não estar em R$</div>'
                             if r["moeda"] != "BRL" else "")
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
    st.caption("P/L = preço ÷ LPA · P/VP = preço ÷ VPA · DY 12m = proventos dos últimos 12 meses ÷ preço. "
               "Indicadores de balanço vêm da Brapi (CVM) e podem estar defasados.")


def pagina_caixa(dados):
    st.markdown("#### Fluxo de caixa histórico")
    tk = st.selectbox("Ativo", list(dados), key="cx_ativo")
    caixa = buscar_caixa(tk)
    if caixa.empty:
        st.info(f"Sem dados de fluxo de caixa para {tk}.")
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
        if dados[tk]["moeda"] != "BRL":
            st.caption(f"Valores na moeda do balanço ({dados[tk]['moeda']}).")

    st.markdown("#### Valor estimado por fluxo de caixa descontado (DCF)")
    c1, c2, c3 = st.columns(3)
    taxa = c1.slider("Taxa de desconto", 8.0, 20.0, 12.0, 0.5, format="%.1f%%") / 100
    g = c2.slider("Crescimento do FCL (5 anos)", -5.0, 15.0, 4.0, 0.5, format="%.1f%%") / 100
    gp = c3.slider("Crescimento na perpetuidade", 0.0, 5.0, 3.0, 0.5, format="%.1f%%") / 100

    linhas = []
    for t, d in dados.items():
        valor, base = dcf(buscar_caixa(t), d["acoes"], d["moeda"], taxa, g, gp)
        margem = (valor - d["preco"]) / valor * 100 if valor and d["preco"] else None
        linhas.append({"Ticker": t, "FCL médio 3a (R$ mi)": base / 1e6 if base is not None and not pd.isna(base) else None,
                       "Valor DCF": valor, "Preço": d["preco"], "Margem (%)": margem})
    st.dataframe(pd.DataFrame(linhas).style.format({
        "FCL médio 3a (R$ mi)": "{:,.0f}", "Valor DCF": "R$ {:.2f}", "Preço": "R$ {:.2f}",
        "Margem (%)": "{:.1f}%"}, na_rep="—"), width="stretch", hide_index=True)
    st.caption("Aproximação: usa a média do fluxo de caixa livre dos últimos 3 anos como fluxo ao acionista, "
               "sem ajustar dívida líquida. Não é adequado para bancos e holdings financeiras, e fica em branco "
               "quando o FCL é negativo ou o balanço não está em reais.")


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
    df, erro = historico(ticker, periodo, intervalo)
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
    st.caption("O gráfico limpo é o widget oficial do TradingView. Os sinais são detectados pelo app com regras "
               "simples sobre os dados da Brapi (o TradingView não permite buscar os desenhos ou sinais "
               "de volta), então podem divergir do que você marcaria à mão.")


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
    if not _token():
        st.warning("Token da Brapi não configurado: só funcionam os tickers de teste "
                   "(PETR4, VALE3, MGLU3, ITUB4). Veja o topo do app.py.")
    st.caption("Fonte: Brapi (B3/CVM) e TradingView (gráfico).")

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
