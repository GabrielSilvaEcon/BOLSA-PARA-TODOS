"""
Renda Fixa, Calculadoras, ETFs e Fundos (páginas do Streamlit):
  - pagina_tesouro: Tesouro Direto / CDI (CDB, LCI/LCA; CDI, prefixado ou IPCA+) com IR regressivo
  - pagina_calculadoras: juros compostos, rentabilidade real, CDB × LCI/LCA e meta de patrimônio
  - pagina_etfs: ETFs brasileiros e americanos (preço, retorno, risco e médias móveis, via Yahoo Finance)
  - pagina_fiis / _fundos_acoes / _multimercados / _fundos_rf: classes de Fundos de Investimento (em construção)

Fontes: Banco Central (SGS, sem chave) para CDI e IPCA; yfinance para os papéis americanos.
Ferramenta educacional, não é recomendação de investimento.
"""
from __future__ import annotations

import re

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import secoes

import cache_central

import assistente
import renda_fixa as rf
import tema

SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{}/dados/ultimos/1?formato=json"
ETFS_POPULARES = ["BOVA11", "IVVB11", "VOO", "QQQ", "SCHD", "VT"]   # só ETFs: ações têm a sua própria página


# ----------------------------------------------------------------------- cálculo (puro)
def aliquota_ir(dias: int) -> float:
    """Tabela regressiva de IR sobre o rendimento de renda fixa (regra única em renda_fixa.py, Passo 11)."""
    return rf.aliquota_ir(dias)


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
    st.markdown(tema.cabecalho("💵", "Tesouro Direto / CDI",
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
    try:                                              # leitura em palavras, conforme o modo de experiência
        import experiencia_app as _ea
        import leitura as _lt
        _ea.mostrar(_lt.simulacao_rf(r["investido"], r["bruto"], r["imposto"], r["liquido"], r["rendimento"], a * 100, meses, ind, _ea.modo()))
    except Exception:
        pass
    liq_aa = (r["liquido"] / r["investido"]) ** (12 / meses) - 1 if r["investido"] and aporte == 0 else None
    st.caption(f"Taxa bruta usada: {a * 100:.2f}% a.a. · rendimento líquido de {brl(r['rendimento'])}"
               + (f" · {liq_aa * 100:.2f}% a.a. líquido" if liq_aa is not None else "")
               + f" · alíquota do IR do primeiro aporte ao fim do prazo: {aliquota_ir(meses * 30):.1%}.")

    df = pd.DataFrame(r["linhas"])
    fig = go.Figure()
    fig.add_scatter(x=df["mes"], y=df["investido"], name="Investido", line={"color": "#BDB5E6", "width": 2})
    fig.add_scatter(x=df["mes"], y=df["liquido"], name="Líquido", line={"color": "#2FB67C", "width": 3},
                    fill="tonexty", fillcolor="rgba(47,182,124,.12)")
    fig.update_layout(height=340, margin={"l": 0, "r": 0, "t": 10, "b": 0}, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", xaxis_title="Meses",
                      legend={"orientation": "h", "y": 1.1})
    st.plotly_chart(fig, width="stretch", key="tesouro_graf", config={"displayModeBar": False})
    st.caption("Simulação simplificada: ignora feriados, IOF (só nos primeiros 30 dias), marcação a mercado e a "
               "variação futura do CDI/IPCA. Para um título específico (impostos, riscos, marcação a mercado, cenários e "
               "comparação), use Renda fixa → Análise de títulos. Não é recomendação de investimento.")


@cache_central.dados(ttl=900)
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


def _ticker_yahoo(t: str) -> str:
    """ETFs da B3 (BOVA11, IVVB11…) precisam do sufixo .SA no Yahoo; os americanos (VOO, QQQ…) não."""
    t = t.strip().upper().replace(" ", "")
    return t + ".SA" if re.fullmatch(r"[A-Z]{4}\d{1,2}", t) else t


def pagina_etfs():
    st.markdown(tema.cabecalho("🧺", "ETFs",
                               "Fundos de índice negociados em bolsa, brasileiros e americanos: preço, retorno, risco e "
                               "tendência. Ações têm as suas próprias páginas."), unsafe_allow_html=True)
    with st.form("form_etf"):
        c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
        c1.text_input("ETF", key="eua_q", label_visibility="collapsed", placeholder="Ex.: BOVA11, IVVB11, VOO, QQQ, SCHD")
        c2.form_submit_button("Analisar", type="primary", width="stretch")
    for col, t in zip(st.columns(len(ETFS_POPULARES)), ETFS_POPULARES):
        col.button(t, key=f"etf_pop_{t}", width="stretch", on_click=lambda x=t: st.session_state.update(eua_q=x))
    ticker = _ticker_yahoo(st.session_state.get("eua_q") or "")
    if not ticker:
        st.info("Digite o código de um ETF ou toque em um atalho.")
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
    assistente.painel_resumo_auto(ticker, lambda: assistente.resumo_etf(ticker, i))

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
    fig.add_scatter(x=df.index, y=close.rolling(200).mean(), name="SMA 200", line={"color": "#8EA2FF", "width": 1.2})
    fig.update_layout(height=380, margin={"l": 0, "r": 0, "t": 10, "b": 0}, template="plotly_dark",
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", legend={"orientation": "h", "y": 1.1})
    st.plotly_chart(fig, width="stretch", key=f"etf_{ticker}", config={"displayModeBar": False})
    st.caption("Dados do Yahoo Finance (preço ajustado, 5 anos; ETFs americanos em dólar). Investir no exterior envolve risco "
               "cambial e regras tributárias próprias. Ferramenta educacional, não é recomendação de investimento.")


# ----------------------------------------------------------------------- calculadoras (puras)
def valor_futuro(inicial: float, aporte: float, meses: int, anual: float) -> float:
    """Juros compostos com aporte no fim de cada mês, sem imposto."""
    i = (1 + anual) ** (1 / 12) - 1
    return inicial * (1 + i) ** meses + (aporte * ((1 + i) ** meses - 1) / i if i else aporte * meses)


def rentabilidade_real(nominal: float, inflacao: float) -> float:
    """Equação de Fisher: ganho acima da inflação, em fração."""
    return (1 + nominal) / (1 + inflacao) - 1


def taxa_equivalente_isenta(taxa_isenta: float, dias: int) -> float:
    """Quanto um título tributado (CDB) precisa pagar para empatar com um isento (LCI/LCA), em fração."""
    return rf.taxa_equivalente_tributavel(taxa_isenta, dias)


def aporte_necessario(meta: float, inicial: float, meses: int, anual: float) -> float:
    """Aporte mensal para chegar à meta (0 se o valor inicial já basta)."""
    i = (1 + anual) ** (1 / 12) - 1
    falta = meta - inicial * (1 + i) ** meses
    if falta <= 0:
        return 0.0
    return falta * i / ((1 + i) ** meses - 1) if i else falta / meses


def pagina_calculadoras():
    st.markdown(tema.cabecalho("🧮", "Calculadoras",
                               "Contas rápidas de renda fixa e planejamento. Para simular Tesouro e CDB com imposto, "
                               "use Tesouro Direto / CDI."), unsafe_allow_html=True)
    t1, t2, t3, t4 = secoes.abas(["Juros compostos", "Rentabilidade real", "CDB × LCI/LCA", "Meta de patrimônio"])
    with t1:
        c1, c2 = st.columns(2)
        ini = c1.number_input("Valor inicial (R$)", min_value=0.0, value=5000.0, step=500.0, key="cj_ini")
        apo = c2.number_input("Aporte mensal (R$)", min_value=0.0, value=300.0, step=50.0, key="cj_apo")
        c3, c4 = st.columns(2)
        meses = int(c3.number_input("Prazo (meses)", min_value=1, max_value=600, value=120, step=6, key="cj_m"))
        taxa = c4.number_input("Taxa (% ao ano)", min_value=0.0, value=10.0, step=0.5, key="cj_t")
        vf = valor_futuro(ini, apo, meses, taxa / 100)
        inv = ini + apo * meses
        for col, (r, v, c) in zip(st.columns(3), (("Total investido", brl(inv), "info"), ("Valor final (bruto)", brl(vf), "good"),
                                                  ("Juros ganhos", brl(vf - inv), "good"))):
            col.markdown(tema.card_status(r, v, c), unsafe_allow_html=True)
        st.caption("Sem imposto e sem inflação. Aporte no fim de cada mês.")
    with t2:
        c1, c2 = st.columns(2)
        nom = c1.number_input("Rentabilidade nominal (% ao ano)", value=12.0, step=0.5, key="rr_n")
        inf = c2.number_input("Inflação (% ao ano)", value=4.5, step=0.1, key="rr_i")
        rr = rentabilidade_real(nom / 100, inf / 100) * 100
        st.markdown(tema.card_status("Rentabilidade real", f"{rr:+.2f}%".replace(".", ",") + " a.a.", "good" if rr > 0 else "bad",
                                     "Quanto o dinheiro cresce acima da inflação: (1 + nominal) ÷ (1 + inflação) − 1."),
                    unsafe_allow_html=True)
    with t3:
        c1, c2 = st.columns(2)
        iso = c1.number_input("Taxa da LCI/LCA (% ao ano)", min_value=0.0, value=10.0, step=0.25, key="eq_t")
        dias = int(c2.number_input("Prazo (dias)", min_value=1, value=365, step=30, key="eq_d"))
        eq = taxa_equivalente_isenta(iso / 100, dias) * 100
        st.markdown(tema.card_status("CDB equivalente", f"{eq:.2f}%".replace(".", ",") + " a.a.", "info",
                                     f"Para empatar com a isenta de {iso:.2f}%, o CDB precisa pagar isto "
                                     f"(IR de {aliquota_ir(dias):.1%} no prazo)."), unsafe_allow_html=True)
        st.caption("Acima desse valor o CDB compensa mais; abaixo, a LCI/LCA vence.")
    with t4:
        c1, c2 = st.columns(2)
        meta = c1.number_input("Meta de patrimônio (R$)", min_value=0.0, value=500000.0, step=10000.0, key="mp_m")
        ini = c2.number_input("Já tenho (R$)", min_value=0.0, value=10000.0, step=1000.0, key="mp_i")
        c3, c4 = st.columns(2)
        meses = int(c3.number_input("Prazo (meses)", min_value=1, max_value=600, value=180, step=6, key="mp_p"))
        taxa = c4.number_input("Rentabilidade (% ao ano)", min_value=0.0, value=9.0, step=0.5, key="mp_t")
        ap = aporte_necessario(meta, ini, meses, taxa / 100)
        st.markdown(tema.card_status("Aporte mensal necessário", brl(ap), "good" if ap == 0 else "info",
                                     "Valor que precisa ser guardado todo mês para chegar à meta no prazo."), unsafe_allow_html=True)


# ----------------------------------------------------------------------- fundos de investimento (em construção)
_FUNDOS = {
    "fiis": ("🏢", "FIIs", "Fundos imobiliários: dividend yield, P/VP, vacância e liquidez, separados por tijolo e papel."),
    "acoes": ("📊", "Fundos de Ações", "Fundos de ações: rentabilidade contra o Ibovespa, taxas, patrimônio e cotistas."),
    "multi": ("🎛️", "Multimercados", "Multimercados: rentabilidade ajustada ao risco contra o CDI, volatilidade e taxas."),
    "rf": ("💵", "Fundos de Renda Fixa", "Fundos de renda fixa: rentabilidade contra o CDI, taxa de administração e come-cotas."),
}


def _pagina_fundo(chave: str):
    ic, nome, texto = _FUNDOS[chave]
    st.markdown(tema.cabecalho(ic, nome, texto), unsafe_allow_html=True)
    st.info("Esta classe ainda está em construção. Os dados de fundos vêm da CVM (cadastro e informe diário), uma fonte "
            "diferente das usadas para ações, e entram numa próxima etapa. O menu já está pronto para recebê-la.")


def pagina_fiis():
    _pagina_fundo("fiis")


def pagina_fundos_acoes():
    _pagina_fundo("acoes")


def pagina_multimercados():
    _pagina_fundo("multi")


def pagina_fundos_rf():
    _pagina_fundo("rf")
