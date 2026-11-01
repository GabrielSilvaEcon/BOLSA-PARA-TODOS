"""
Renda Fixa & ETFs (páginas do Streamlit):
  - pagina_tesouro: calculadora de Tesouro Direto / CDB / LCI-LCA (CDI, prefixado ou IPCA+) com IR regressivo
  - pagina_eua: Bolsa Americana e ETFs (preço, retorno, risco e médias móveis, via Yahoo Finance)

Fontes: Banco Central (SGS, sem chave) para CDI e IPCA; yfinance para os papéis americanos.
Ferramenta educacional, não é recomendação de investimento.
"""
from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import tema

SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados/ultimos/1?formato=json"
ETFS_POPULARES = ["VOO", "SPY", "QQQ", "VT", "IVV", "SCHD", "AAPL", "MSFT", "NVDA"]


# ----------------------------------------------------------------------- cálculo (puro)
def aliquota_ir(dias: int) -> float:
    """Tabela regressiva de IR sobre o rendimento de renda fixa."""
    return 0.225 if dias <= 180 else 0.20 if dias <= 360 else 0.175 if dias <= 720 else 0.15


def taxa_anual(indexador: str, taxa: float, cdi: float, ipca: float) -> float:
    """Taxa efetiva anual (fração) a partir do indexador. taxa vem em % (110 = 110% do CDI; 12 = 12% a.a.)."""
    if indexador == "CDI":
        return cdi * taxa / 100
    if indexador == "IPCA+":
        return (1 + ipca) * (1 + taxa / 100) - 1
    return taxa / 100  # prefixado


def simular(inicial: float, aporte: float, meses: int, anual: float, custodia: float = 0.0) -> dict:
    """Juros compostos com aporte mensal no fim de cada mês. IR regressivo calculado por aporte
    (cada parcela tem a sua idade). custodia = taxa anual da B3 (% a.a., ex.: 0,20), descontada do rendimento."""
    mensal = (1 + anual) ** (1 / 12) - 1
    parcelas = [(0, inicial)] + [(m, aporte) for m in range(1, meses + 1) if aporte > 0]
    linhas, investido = [], 0.0
    for mes in range(meses + 1):
        bruto = ir = 0.0
        for m0, v in parcelas:
            if m0 > mes:
                continue
            valor = v * (1 + mensal) ** (mes - m0)
            rend = max(valor - v, 0.0)
            bruto += valor
            ir += rend * aliquota_ir((mes - m0) * 30)
        investido = inicial + aporte * mes
        cust = (bruto - investido) * (custodia / 100) * mes / 12 if custodia and bruto > investido else 0.0
        linhas.append({"mes": mes, "investido": investido, "bruto": bruto, "liquido": bruto - ir - cust})
    ult = linhas[-1]
    return {"linhas": linhas, "investido": ult["investido"], "bruto": ult["bruto"], "liquido": ult["liquido"],
            "imposto": ult["bruto"] - ult["liquido"], "rendimento": ult["liquido"] - ult["investido"]}


def brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ----------------------------------------------------------------------- dados
@st.cache_data(ttl=3600, show_spinner=False)
def _sgs(codigo: int) -> float | None:
    try:
        r = requests.get(SGS.format(codigo), timeout=15, headers={"User-Agent": "bolsa-para-todos/1.0"})
        r.raise_for_status()
        return float(str(r.json()[-1]["valor"]).replace(",", "."))
    except Exception:
        return None


def cdi_aa() -> float | None:
    v = _sgs(4389)  # CDI anualizado base 252, % a.a.
    return v / 100 if v else None


def ipca_12m() -> float | None:
    v = _sgs(13522)  # IPCA acumulado em 12 meses, %
    return v / 100 if v else None


# ----------------------------------------------------------------------- páginas
def pagina_tesouro():
    st.markdown(tema.cabecalho("💵", "Calculadora Tesouro / CDI",
                               "Simule Tesouro Direto, CDB, LCI/LCA com aportes mensais e IR regressivo."),
                unsafe_allow_html=True)
    cdi, ipca = cdi_aa(), ipca_12m()
    c1, c2 = st.columns(2)
    inicial = c1.number_input("Valor inicial (R$)", min_value=0.0, value=10000.0, step=500.0)
    aporte = c2.number_input("Aporte mensal (R$)", min_value=0.0, value=500.0, step=50.0)
    c3, c4, c5 = st.columns(3)
    meses = int(c3.number_input("Prazo (meses)", min_value=1, max_value=600, value=60, step=6))
    ind = c4.selectbox("Indexador", ["CDI", "Prefixado", "IPCA+"], format_func=lambda x: {
        "CDI": "% do CDI (CDB, Selic)", "Prefixado": "Prefixado (a.a.)", "IPCA+": "IPCA + taxa (a.a.)"}[x])
    taxa = c5.number_input("% do CDI" if ind == "CDI" else "Taxa (% a.a.)", min_value=0.0,
                           value=100.0 if ind == "CDI" else 6.0, step=0.5)
    c6, c7, c8 = st.columns(3)
    cdi_v = c6.number_input("CDI atual (% a.a.)", min_value=0.0, value=round((cdi or 0.14) * 100, 2), step=0.1,
                            help="Preenchido com o último valor do Banco Central; edite se quiser.")
    ipca_v = c7.number_input("IPCA esperado (% a.a.)", min_value=0.0, value=round((ipca or 0.045) * 100, 2), step=0.1)
    cust = c8.number_input("Custódia B3 (% a.a.)", min_value=0.0, value=0.0, step=0.05,
                           help="Tesouro Direto cobra 0,20% a.a. sobre o valor; títulos bancários não cobram. "
                                "Aqui é descontada do rendimento, como aproximação.")
    if cdi is None or ipca is None:
        st.caption("ℹ️ Não consegui ler CDI/IPCA do Banco Central agora; usei valores de referência editáveis.")

    a = taxa_anual(ind, taxa, cdi_v / 100, ipca_v / 100)
    r = simular(inicial, aporte, meses, a, cust)
    m1, m2, m3, m4 = st.columns(4)
    for col, (rot, val, cls) in zip((m1, m2, m3, m4), (
            ("Total investido", brl(r["investido"]), "info"), ("Valor bruto", brl(r["bruto"]), "info"),
            ("Imposto + custódia", brl(r["imposto"]), "fair"), ("Valor líquido", brl(r["liquido"]), "good"))):
        col.markdown(tema.card_status(rot, val, cls), unsafe_allow_html=True)
    liq_aa = (r["liquido"] / r["investido"]) ** (12 / meses) - 1 if r["investido"] and aporte == 0 else None
    st.caption(f"Taxa bruta usada: {a * 100:.2f}% a.a. · rendimento líquido de {brl(r['rendimento'])}"
               + (f" · {liq_aa * 100:.2f}% a.a. líquido" if liq_aa is not None else "")
               + f" · alíquota do IR do primeiro aporte ao fim do prazo: {aliquota_ir(meses * 30):.1%}.")

    df = pd.DataFrame(r["linhas"])
    fig = go.Figure()
    fig.add_scatter(x=df["mes"], y=df["investido"], name="Investido", line={"color": "#A0AEC0", "width": 2})
    fig.add_scatter(x=df["mes"], y=df["liquido"], name="Líquido", line={"color": "#2FB67C", "width": 3},
                    fill="tonexty", fillcolor="rgba(47,182,124,.12)")
    fig.update_layout(height=340, margin={"l": 0, "r": 0, "t": 10, "b": 0}, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Meses",
                      legend={"orientation": "h", "y": 1.1})
    st.plotly_chart(fig, width="stretch", key="tesouro_graf", config={"displayModeBar": False})
    st.caption("Simulação simplificada: ignora feriados, IOF (só nos primeiros 30 dias), marcação a mercado e a "
               "variação futura do CDI/IPCA. Não é recomendação de investimento.")


@st.cache_data(ttl=900, show_spinner=False)
def _historico_eua(ticker: str) -> pd.DataFrame:
    import yfinance as yf
    df = yf.Ticker(ticker).history(period="5y", auto_adjust=True)
    return df[["Close"]].dropna() if df is not None and not df.empty else pd.DataFrame()


def indicadores_eua(close: pd.Series) -> dict:
    """Retornos, risco e tendência a partir do preço de fechamento diário."""
    def ret(d):
        return float(close.iloc[-1] / close.iloc[-1 - d] - 1) * 100 if len(close) > d else None
    pico = close.cummax()
    mm50, mm200 = close.rolling(50).mean(), close.rolling(200).mean()
    tend = None
    if len(close) >= 200:
        pts = int(close.iloc[-1] > mm200.iloc[-1]) + int(mm50.iloc[-1] > mm200.iloc[-1])
        tend = {2: "Alta", 1: "Lateral", 0: "Baixa"}[pts]
    return {"preco": float(close.iloc[-1]), "r1m": ret(21), "r6m": ret(126), "r12m": ret(252),
            "vol": float(close.pct_change().dropna().std() * (252 ** 0.5) * 100) if len(close) > 30 else None,
            "queda": float((close.iloc[-1] / pico.iloc[-1] - 1) * 100), "tend": tend,
            "dd_max": float((close / pico - 1).min() * 100)}


def pagina_eua():
    st.markdown(tema.cabecalho("🗽", "Bolsa Americana & ETFs",
                               "Preço, retorno, risco e tendência de ETFs e ações dos EUA (em dólar)."),
                unsafe_allow_html=True)
    with st.form("form_eua"):
        c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
        c1.text_input("Ticker", key="eua_q", label_visibility="collapsed", placeholder="Ex.: VOO, QQQ, AAPL, SCHD")
        c2.form_submit_button("Analisar", type="primary", width="stretch")
    for col, t in zip(st.columns(5), ETFS_POPULARES[:5]):
        col.button(t, key=f"eua_pop_{t}", width="stretch", on_click=lambda x=t: st.session_state.update(eua_q=x))
    ticker = (st.session_state.get("eua_q") or "").strip().upper().replace(" ", "")
    if not ticker:
        st.info("Digite um ticker americano ou toque em um atalho.")
        return
    try:
        with st.spinner(f"Consultando {ticker}…"):
            df = _historico_eua(ticker)
    except Exception:
        df = pd.DataFrame()
    if df.empty or len(df) < 30:
        st.warning(f"Não encontrei dados para “{ticker}”. Confira o código (ex.: VOO) ou tente de novo em instantes.")
        return
    close = df["Close"]
    i = indicadores_eua(close)

    def p(v):
        return "n/d" if v is None else f"{v:+.1f}%".replace(".", ",")
    cls = lambda v: "na" if v is None else ("good" if v > 0 else "bad")  # noqa: E731
    itens = [("Preço", f"US$ {i['preco']:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."), "info"),
             ("Retorno 1 mês", p(i["r1m"]), cls(i["r1m"])), ("Retorno 6 meses", p(i["r6m"]), cls(i["r6m"])),
             ("Retorno 12 meses", p(i["r12m"]), cls(i["r12m"])),
             ("Volatilidade anual", "n/d" if i["vol"] is None else f"{i['vol']:.1f}%".replace(".", ","),
              "na" if i["vol"] is None else "good" if i["vol"] < 18 else "fair" if i["vol"] < 30 else "bad"),
             ("Queda desde o pico (5a)", p(i["queda"]), "good" if i["queda"] > -10 else "fair" if i["queda"] > -25 else "bad"),
             ("Pior queda (5a)", p(i["dd_max"]), "na"),
             ("Tendência SMA 50/200", {"Alta": "▲ Alta", "Lateral": "► Lateral", "Baixa": "▼ Baixa"}.get(i["tend"], "n/d"),
              {"Alta": "good", "Lateral": "fair", "Baixa": "bad"}.get(i["tend"], "na"))]
    for k in range(0, len(itens), 4):
        for col, (rot, val, c) in zip(st.columns(4), itens[k:k + 4]):
            col.markdown(tema.card_status(rot, val, c), unsafe_allow_html=True)

    fig = go.Figure()
    fig.add_scatter(x=df.index, y=close, name=ticker, line={"color": "#2FB67C", "width": 2})
    fig.add_scatter(x=df.index, y=close.rolling(50).mean(), name="SMA 50", line={"color": "#DDA735", "width": 1.2})
    fig.add_scatter(x=df.index, y=close.rolling(200).mean(), name="SMA 200", line={"color": "#6B9BFF", "width": 1.2})
    fig.update_layout(height=380, margin={"l": 0, "r": 0, "t": 10, "b": 0}, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend={"orientation": "h", "y": 1.1})
    st.plotly_chart(fig, width="stretch", key=f"eua_{ticker}", config={"displayModeBar": False})
    st.caption("Dados do Yahoo Finance (preço ajustado, 5 anos). Investir no exterior envolve risco cambial e regras "
               "tributárias próprias. Ferramenta educacional, não é recomendação de investimento.")
