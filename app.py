"""
Painel B3 - Fundamentalista + DCF + Stock Picking + Técnica + Macro & Micro

Rodar com: streamlit run app.py
Requer streamlit >= 1.46 (navegação no topo) e o módulo tecnica.py ao lado.

Convenções internas dos dados (todas as fontes são normalizadas para isso):
  preco, lpa, vpa, div_12m, div_medio, divida_liq ..... R$ (já convertidos se o balanço for em USD)
  roe, margem_liq ..................................... fração (0.15 = 15%)
  div_pl .............................................. percentual (150 = 150%)
  acoes ............................................... unidades
"""

import html
import json
import os
import re
from datetime import date, datetime, timedelta
from math import sqrt
from numbers import Number

import fundamentus
import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st
import streamlit.components.v1 as components
import yfinance as yf

import tecnica as tec

st.set_page_config(page_title="Painel B3", page_icon="📈", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- paleta neutra
BG, SURFACE, BORDER = "#0e1117", "#161b22", "#30363d"
TEXT, MUTED = "#e6edf3", "#8b949e"
ACCENT = "#58a6ff"
GOOD, FAIR, BAD = "#3fb950", "#d29922", "#f85149"

st.markdown(
    f"""
<style>
.stApp {{background:{BG};}}
header[data-testid="stHeader"] {{background:{BG}; border-bottom:1px solid {BORDER};}}
.block-container {{padding-top:4.2rem; max-width:1400px;}}
.hero {{font-size:1.35rem; font-weight:700; color:{TEXT}; letter-spacing:.2px; line-height:1.1;}}
.sub {{font-size:.72rem; color:{MUTED};}}
.card {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px;
padding:16px 18px; margin-bottom:10px;}}
.tk {{font-size:1.3rem; font-weight:700; color:{TEXT}; letter-spacing:.4px;}}
.nm {{font-size:.78rem; color:{MUTED}; margin-bottom:8px;}}
.aviso {{font-size:.72rem; color:{FAIR}; margin-top:6px;}}
.badge {{display:inline-block; padding:3px 11px; border-radius:999px;
font-size:.72rem; font-weight:600; float:right;}}
.good {{background:rgba(63,185,80,.15); color:{GOOD};}}
.fair {{background:rgba(210,153,34,.15); color:{FAIR};}}
.bad {{background:rgba(248,81,73,.15); color:{BAD};}}
.na {{background:rgba(139,148,158,.15); color:{MUTED};}}
.lbl {{font-size:.68rem; color:{MUTED}; text-transform:uppercase; letter-spacing:.8px;}}
.val {{font-size:1.15rem; font-weight:600; color:{TEXT};}}
h4 {{font-weight:600; color:{TEXT};}}
.sec {{font-size:1.05rem; font-weight:600; color:{TEXT}; margin:.6rem 0 .3rem;}}
.tip {{position:relative; display:inline-block; cursor:help; color:{MUTED}; font-size:.85em;
margin-left:5px; outline:none; text-transform:none; letter-spacing:0; font-weight:400;}}
.tip .tipbox {{visibility:hidden; opacity:0; position:absolute; z-index:99999; left:50%;
transform:translateX(-50%); bottom:140%; width:280px; background:#1c2128; border:1px solid {BORDER};
border-radius:8px; padding:9px 11px; font-size:.74rem; line-height:1.4; font-weight:400;
color:{TEXT}; text-align:left; box-shadow:0 6px 18px rgba(0,0,0,.5); transition:opacity .15s;}}
.tip:hover .tipbox, .tip:focus .tipbox {{visibility:visible; opacity:1;}}
.kpi {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:12px; padding:12px 14px;}}
.kpi .v {{font-size:1.3rem; font-weight:700;}}
.kpi .d {{font-size:.72rem; color:{MUTED}; margin-top:2px;}}
.ctx {{background:{SURFACE}; border:1px solid {BORDER}; border-left-width:4px; border-radius:10px;
padding:12px 14px; margin-bottom:10px;}}
.ctx.pos {{border-left-color:{GOOD};}}
.ctx.neg {{border-left-color:{BAD};}}
.ctx.neu {{border-left-color:{FAIR};}}
.ctx .t {{font-weight:600; font-size:.95rem;}}
.ctx .x {{font-size:.78rem; color:{MUTED}; margin-top:4px; line-height:1.5;}}
p, span, label, div {{color: {TEXT};}}
</style>
""",
    unsafe_allow_html=True,
)

PLOT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": TEXT}, margin=dict(l=10, r=10, t=40, b=10))
GRID = dict(gridcolor="#30363d", zeroline=False)

FONTES = ["Yahoo Finance", "Fundamentus", "Brapi"]
UNIVERSO_PADRAO = ["PETR4", "ITSA4", "BBAS3", "VALE3"]
FINANCEIRAS = ("ITSA", "ITUB", "BBDC", "BBAS", "BPAC", "SANB", "BBSE", "CXSE", "SULA")

# ---------------------------------------------------------------- cor fixa por ativo
PALETA = ["#58a6ff", "#f0883e", "#bc8cff", "#33b3ae", "#f778ba", "#e3b341",
          "#79c0ff", "#7ee787", "#ff7b72", "#a371f7", "#56d364", "#d2a8ff"]


def cor_ativo(tk: str) -> str:
    """Cada ativo tem sempre a mesma cor, em todas as páginas e gráficos."""
    tk = str(tk).upper().replace(".SA", "").strip()
    uni = st.session_state.get("universo", [])
    i = uni.index(tk) if tk in uni else sum(map(ord, tk))
    return PALETA[i % len(PALETA)]


# ---------------------------------------------------------------- glossário (tooltips ⓘ)
GLOSSARIO = {
    "Preço": ("Cotação atual da ação na B3.",
              "Base para comparar com o preço justo e para calcular múltiplos (P/L, P/VP) e dividend yield."),
    "Preço justo": ("Estimativa do valor intrínseco da ação pelos métodos de Graham e/ou Bazin.",
                    "Indica se o mercado cobra menos (ação barata) ou mais (ação cara) do que o valor estimado."),
    "Margem (%)": ("Diferença entre o preço justo e o preço atual, dividida pelo preço justo.",
                   "Mede a margem de segurança: quanto maior, maior o desconto e a proteção contra erros de estimativa."),
    "Média 5 anos": ("Média anual dos dividendos por ação nos últimos 5 anos completos.",
                     "É a base do preço-teto de Bazin e suaviza anos atípicos de proventos."),
    "Proventos 12m": ("Soma de dividendos e JCP por ação pagos nos últimos 12 meses.",
                      "Serve para calcular o dividend yield atual."),
    "P/L": ("Preço ÷ lucro por ação (LPA): quantos anos de lucro o preço atual 'paga'.",
            "Compara o preço com o lucro. Baixo sugere ação barata; alto sugere expectativa de crescimento ou ação cara. Compare dentro do mesmo setor."),
    "P/VP": ("Preço ÷ valor patrimonial por ação (VPA).",
             "Mostra quanto o mercado paga sobre o patrimônio contábil; abaixo de 1 indica negociação abaixo do patrimônio. Muito usado para bancos."),
    "EV/EBITDA": ("Valor da firma (valor de mercado + dívida líquida) ÷ EBITDA (lucro operacional antes de juros, impostos e depreciação).",
                  "Compara empresas com estruturas de dívida diferentes: quanto menor, mais barata a operação. Não se aplica bem a bancos."),
    "DY 12m (%)": ("Dividend yield: proventos dos últimos 12 meses ÷ preço.",
                   "Mostra o retorno em dividendos sobre o preço atual; útil para estratégias de renda. Yield muito alto pode indicar queda de preço ou pagamento extraordinário."),
    "DY s/ média 5a (%)": ("Dividend yield calculado com a média anual de proventos dos últimos 5 anos.",
                           "Versão menos sensível a pagamentos extraordinários."),
    "ROE (%)": ("Return on Equity: lucro líquido ÷ patrimônio líquido.",
                "Mede a rentabilidade gerada com o capital dos acionistas; acima de ~15% costuma indicar boa qualidade."),
    "Margem líq. (%)": ("Lucro líquido ÷ receita líquida.",
                        "Mostra quanto da receita sobra como lucro; indica eficiência e poder de preço. Compare dentro do setor."),
    "Dív./PL (%)": ("Dívida bruta ÷ patrimônio líquido.",
                    "Mede alavancagem e risco financeiro; valores altos aumentam a fragilidade com juros altos. Não se aplica a bancos."),
    "LPA": ("Lucro por ação dos últimos 12 meses.", "Base do P/L e do preço justo de Graham."),
    "VPA": ("Valor patrimonial por ação.", "Base do P/VP e do preço justo de Graham."),
    "FCL": ("Fluxo de caixa livre: caixa gerado pela operação menos os investimentos para manter o negócio.",
            "É o dinheiro que sobra para acionistas e credores; base do DCF."),
    "FCL base (R$ mi)": ("Fluxo de caixa livre médio usado como ponto de partida da projeção, em R$ milhões.",
                         "Define a escala de todo o DCF: se a base estiver errada, o valor justo também estará."),
    "Valor DCF": ("Valor por ação obtido ao trazer a valor presente os fluxos de caixa livres projetados.",
                  "Estimativa de valor intrínseco baseada na capacidade da empresa de gerar caixa."),
    "Taxa de desconto": ("Retorno mínimo exigido para investir na empresa (custo de capital).",
                         "Quanto maior, menor o valor presente dos fluxos futuros. Costuma partir da Selic mais um prêmio de risco."),
    "Perpetuidade": ("Crescimento anual do fluxo de caixa após o período explícito, para sempre.",
                     "Resume o valor da empresa depois do horizonte projetado; deve ficar abaixo do crescimento da economia."),
    "Valor terminal": ("Valor presente de todos os fluxos depois do período explícito.",
                       "Se passa de ~75% do valor total, o resultado depende demais de premissas de longo prazo."),
    "Potencial": ("Valor justo ÷ preço atual − 1.", "Mostra quanto a ação teria de subir (ou cair) para chegar ao valor estimado."),
    "Nota": ("Pontuação de 0 a 100 que combina os cinco pilares com os pesos escolhidos.",
             "Ordena os ativos para uma triagem inicial; não substitui a análise da empresa."),
    "Valor": ("Pilar de preço: margem de segurança, P/L, P/VP, EV/EBITDA e DCF.", "Mede se a ação está barata em relação ao que entrega."),
    "Qualidade": ("Pilar de rentabilidade: ROE e margem líquida.", "Mede se a empresa transforma capital e receita em lucro de forma eficiente."),
    "Dividendos": ("Pilar de renda: dividend yield e regularidade nos últimos 5 anos.", "Mede o retorno em proventos e a consistência do pagamento."),
    "Solidez": ("Pilar de endividamento: Dív./PL (não se aplica a financeiras).", "Mede a resistência da empresa a juros altos e crises."),
    "Tendência": ("Pilar técnico: distância do preço à média de 200 dias e cruzamento das médias de 50 e 200.",
                  "Mede se o mercado está comprando ou vendendo o ativo no momento."),
    "Atratividade": ("Faixa da nota: Alta (≥70), Moderada (50–70) ou Baixa (<50).", "Leitura rápida do ranking."),
    "Cobertura": ("Quantos dos 5 pilares tiveram dados disponíveis.", "Notas com cobertura baixa são menos confiáveis."),
    "Status": ("Situação do preço frente ao preço justo e à margem alvo.", "Resume se há margem de segurança, se está justo ou caro."),
    "Selic": ("Taxa básica de juros da economia, definida pelo Copom.",
              "Referência para o custo do crédito e para a renda fixa: juros altos reduzem o valor das ações e favorecem a renda fixa."),
    "IPCA 12m": ("Inflação oficial acumulada em 12 meses.",
                 "Indica a pressão sobre custos e poder de compra e orienta o rumo dos juros. A meta é 3% com tolerância de 1,5 ponto."),
    "Dólar": ("Cotação do dólar comercial em reais.",
              "Afeta exportadoras (ganham com dólar alto) e importadoras e empresas endividadas em dólar (perdem)."),
    "Desemprego": ("Taxa de desocupação da PNAD Contínua (trimestre móvel).",
                   "Mede a força do consumo e da renda: desemprego baixo favorece varejo, crédito e imobiliário."),
    "EMBI": ("Risco-país: sobretaxa que o Brasil paga sobre títulos dos EUA, em pontos-base.",
             "Indica a percepção de risco dos investidores; alto encarece o capital e pressiona ativos domésticos."),
    "IGP-M": ("Índice Geral de Preços do Mercado, muito ligado a atacado, commodities e câmbio.",
              "Reajusta aluguéis, contratos e tarifas (utilidades, FIIs); alto favorece quem recebe e pesa para quem paga."),
    "Juro real": ("Selic menos IPCA 12m: o juro acima da inflação.", "Mede o quanto a política monetária é restritiva (acima de ~8% é muito alto)."),
}


def ajuda_txt(k: str) -> str:
    o, p = GLOSSARIO[k]
    return f"**O que é:** {o}\n\n**Para que serve:** {p}"


def tip(k: str) -> str:
    """Ícone ⓘ com balão (passar o mouse ou tocar/clicar)."""
    if k not in GLOSSARIO:
        return ""
    o, p = GLOSSARIO[k]
    return (f'<span class="tip" tabindex="0">ⓘ<span class="tipbox"><b>O que é:</b> {html.escape(o)}'
            f'<br><b>Para que serve:</b> {html.escape(p)}</span></span>')


def md(h: str):
    st.markdown(h.replace("$", "&#36;"), unsafe_allow_html=True)


def kpi(label, valor, chave=None, detalhe=None, cor=None):
    d = f'<div class="d">{detalhe}</div>' if detalhe else ""
    md(f'<div class="kpi"><div class="lbl">{html.escape(label)}{tip(chave) if chave else ""}</div>'
       f'<div class="v" style="color:{cor or TEXT}">{valor}</div>{d}</div>')


def explica(k: str):
    o, p = GLOSSARIO[k]
    md(f'<div class="ctx neu"><div class="t">{html.escape(k)}</div>'
       f'<div class="x"><b>O que é:</b> {html.escape(o)}<br><b>Para que serve:</b> {html.escape(p)}</div></div>')


def cfg_ajuda(df) -> dict:
    """column_config com o ⓘ do glossário nos cabeçalhos da tabela."""
    return {c: st.column_config.Column(help=ajuda_txt(c)) for c in df.columns if c in GLOSSARIO}

# ---------------------------------------------------------------- estado
if "universo" not in st.session_state:
    st.session_state.universo = list(UNIVERSO_PADRAO)
    st.session_state.sel_ativos = list(UNIVERSO_PADRAO)
st.session_state.setdefault("fonte_dados", "Yahoo Finance")


def normaliza(t: str) -> str:
    return str(t).upper().strip().replace(".SA", "")


def eh_financeiro(tk: str) -> bool:
    return normaliza(tk).startswith(FINANCEIRAS)


# ---------------------------------------------------------------- parsing numérico e formatação
def _num(x):
    try:
        if x is None or pd.isna(x):
            return None
        val = float(x)
        return None if pd.isna(val) else val
    except (TypeError, ValueError):
        return None


def parse_num(val):
    """Converte número ou texto (formato BR ou US, com R$, %, parênteses) em float."""
    if val is None:
        return None
    if isinstance(val, Number) and not isinstance(val, bool):
        return _num(val)
    s = str(val).strip().replace("R$", "").replace("%", "").replace("\xa0", "").replace(" ", "")
    if s in ("", "-", "—", "nan", "None", "N/A"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def parse_pct(val):
    """Devolve SEMPRE fração (0.15 = 15%). Texto com '%' é dividido por 100;
    número puro com |v| <= 1 já é tratado como fração, acima disso como pontos percentuais."""
    if val is None:
        return None
    tem_pct = isinstance(val, str) and "%" in val
    v = parse_num(val)
    if v is None:
        return None
    if tem_pct:
        return v / 100.0
    return v if abs(v) <= 1.0 else v / 100.0


def _sep(s: str) -> str:
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v, casas=2):
    return "—" if v is None or pd.isna(v) else _sep(f"R$ {v:,.{casas}f}")


def pct(v, casas=1):
    return "—" if v is None or pd.isna(v) else _sep(f"{v:,.{casas}f}%")


def num(v, casas=2):
    return "—" if v is None or pd.isna(v) else _sep(f"{v:,.{casas}f}")


def mi(v):
    return "—" if v is None or pd.isna(v) else _sep(f"{v / 1e6:,.0f}")


def estilizar(df: pd.DataFrame, fmts: dict):
    return df.style.format(fmts, na_rep="—")


# ---------------------------------------------------------------- Banco Central (macro + câmbio)
@st.cache_data(ttl=3600, show_spinner=False)
def buscar_macro_bcb(codigo_serie: int, anos: int = 10) -> pd.DataFrame:
    """
    432   Selic meta (% a.a.)            433   IPCA mensal (%)
    13522 IPCA acumulado 12m (%)        1     Dólar comercial venda (R$)
    24369 Taxa de desocupação PNAD (%)
    A API do SGS exige janela de datas em séries diárias, por isso sempre filtramos.
    """
    fim = date.today()
    ini = fim - timedelta(days=int(365.25 * anos))
    url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados"
           f"?formato=json&dataInicial={ini:%d/%m/%Y}&dataFinal={fim:%d/%m/%Y}")
    for _ in range(2):
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                df = pd.DataFrame(r.json())
                if not df.empty and {"data", "valor"} <= set(df.columns):
                    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
                    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
                    return df.dropna(subset=["data", "valor"]).set_index("data").sort_index()
        except Exception:
            continue
    return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def serie_cambio() -> pd.Series:
    """USD/BRL diário (BCB; Yahoo como reserva)."""
    df = buscar_macro_bcb(1, anos=8)
    if not df.empty:
        return df["valor"]
    try:
        h = yf.Ticker("BRL=X").history(period="8y")["Close"]
        h.index = pd.to_datetime(h.index).tz_localize(None)
        return h.dropna()
    except Exception:
        return pd.Series(dtype=float)


def fx_atual():
    s = serie_cambio()
    return float(s.iloc[-1]) if not s.empty else None


def fx_anual() -> dict:
    s = serie_cambio()
    if s.empty:
        return {}
    return {int(a): float(v) for a, v in s.groupby(s.index.year).mean().items()}


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_macro_ipea(codigo_serie: str) -> pd.DataFrame:
    urls = [
        f"https://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo_serie}')",
        f"http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo_serie}')",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                continue
            dados = r.json().get("value", [])
            if not dados:
                continue
            df = pd.DataFrame(dados)
            cd = "VALDATA" if "VALDATA" in df.columns else ("Data" if "Data" in df.columns else None)
            cv = "VALVALOR" if "VALVALOR" in df.columns else ("Valor" if "Valor" in df.columns else None)
            if cd and cv:
                df[cd] = pd.to_datetime(df[cd], errors="coerce", utc=True).dt.tz_localize(None)
                df[cv] = pd.to_numeric(df[cv], errors="coerce")
                df = df.dropna(subset=[cd, cv]).set_index(cd).sort_index()
                return df[[cv]].rename(columns={cv: "valor"})
        except Exception:
            continue
    return pd.DataFrame()


# ---------------------------------------------------------------- clientes de dados
def dict_base(tk: str) -> dict:
    return {
        "ticker": tk, "nome": tk, "preco": None, "lpa": None, "vpa": None,
        "div_ano": pd.Series(dtype=float), "div_medio": None, "div_12m": None,
        "ev_ebitda": None, "roe": None, "margem_liq": None, "div_pl": None,
        "acoes": None, "moeda": "BRL", "moeda_balanco": "BRL", "divida_liq": None,
        "setor": None, "data_balanco": None,
        "erro": None, "alertas": [],
    }


def _proventos_series(df: pd.DataFrame, col_data: str, col_valor: str):
    """Série anual de proventos + média dos últimos 5 anos completos + últimos 12 meses."""
    por_ano = df.groupby(df[col_data].dt.year)[col_valor].sum()
    por_ano.index = por_ano.index.astype(int)
    por_ano.index.name = "ano"
    hoje = pd.Timestamp.now(tz=df[col_data].dt.tz) if df[col_data].dt.tz is not None else pd.Timestamp.now()
    mask12 = (df[col_data] >= hoje - pd.Timedelta(days=365)) & (df[col_data] <= hoje)
    div_12m = float(df.loc[mask12, col_valor].sum())
    completos = por_ano[por_ano.index < hoje.year].tail(5)
    base = completos if len(completos) else por_ano
    return por_ano, (float(base.mean()) if not base.empty else 0.0), div_12m


# --- 1. Brapi
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


def _proventos_brapi(lista):
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
        return _proventos_series(df, "data", "rate")
    except Exception:
        return vazio, None, None


@st.cache_data(ttl=900, show_spinner=False)
def buscar_brapi(ticker: str) -> dict:
    tk = normaliza(ticker)
    d = dict_base(tk)
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
        d["div_ano"], d["div_medio"], d["div_12m"] = _proventos_brapi(lista_div)

        js, err = _get("/v2/stocks/statistics", {"symbols": tk})
        if err:
            erros.append(f"múltiplos: {err}")
        est = (_primeiro(js) or {}).get("data") or {}
        if isinstance(est, dict):
            d["vpa"] = _num(est.get("bookValue"))
            d["lpa"] = _num(est.get("trailingEps")) or d["lpa"]
            d["ev_ebitda"] = _num(est.get("enterpriseToEbitda"))
            d["acoes"] = _num(est.get("sharesOutstanding"))
            d["margem_liq"] = _num(est.get("profitMargins"))

        js, err = _get("/v2/stocks/financial-data", {"symbols": tk})
        if err:
            erros.append(f"dados financeiros: {err}")
        fin = (_primeiro(js) or {}).get("data") or {}
        if isinstance(fin, dict):
            d["roe"] = _num(fin.get("returnOnEquity"))
            ml = _num(fin.get("profitMargins"))
            d["margem_liq"] = ml if ml is not None else d["margem_liq"]
            # debtToEquity já vem em percentual (padrão Yahoo): não multiplicar
            d["div_pl"] = _num(fin.get("debtToEquity"))
            if fin.get("financialCurrency"):
                d["moeda_balanco"] = fin["financialCurrency"]
            td, tc = _num(fin.get("totalDebt")), _num(fin.get("totalCash"))
            if td is not None and tc is not None:
                d["divida_liq"] = td - tc
    except Exception as e:
        erros.append(f"exceção brapi: {e}")
    d["erro"] = "; ".join(erros) or None
    return d


@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa_brapi(ticker: str) -> pd.DataFrame:
    try:
        js, _ = _get("/v2/stocks/cash-flow", {"symbols": normaliza(ticker), "period": "annual"})
        linhas = (_primeiro(js) or {}).get("data")
        if not linhas:
            return pd.DataFrame()
        df = pd.DataFrame(linhas)
        if "endDate" not in df:
            return pd.DataFrame()
        nomes = {"operatingCashFlow": "Caixa operacional",
                 "investmentCashFlow": "Caixa de investimento",
                 "freeCashFlow": "Fluxo de caixa livre"}
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


@st.cache_data(ttl=900, show_spinner=False)
def historico_brapi(ticker: str, periodo: str, intervalo: str):
    try:
        js, err = _get(f"/quote/{normaliza(ticker)}", {"range": periodo, "interval": intervalo})
        dados = (_primeiro(js) or {}).get("historicalDataPrice")
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


# --- 2. Yahoo Finance
@st.cache_data(ttl=900, show_spinner=False)
def buscar_yahoo(ticker: str) -> dict:
    d = dict_base(normaliza(ticker))
    try:
        t = yf.Ticker(d["ticker"] + ".SA")
        info = t.info or {}
        d["nome"] = info.get("longName") or info.get("shortName") or d["ticker"]
        d["preco"] = _num(info.get("currentPrice") or info.get("regularMarketPrice"))
        d["lpa"] = _num(info.get("trailingEps"))
        d["vpa"] = _num(info.get("bookValue"))
        d["ev_ebitda"] = _num(info.get("enterpriseToEbitda"))
        d["roe"] = _num(info.get("returnOnEquity"))
        d["margem_liq"] = _num(info.get("profitMargins"))
        d["div_pl"] = _num(info.get("debtToEquity"))  # já em %
        d["acoes"] = _num(info.get("sharesOutstanding"))
        d["moeda"] = info.get("currency") or "BRL"
        d["moeda_balanco"] = info.get("financialCurrency") or d["moeda"]
        td, tc = _num(info.get("totalDebt")), _num(info.get("totalCash"))
        if td is not None and tc is not None:
            d["divida_liq"] = td - tc
        d["setor"] = info.get("sector")
        try:
            mrq = info.get("mostRecentQuarter")
            if mrq:
                d["data_balanco"] = pd.to_datetime(mrq, unit="s").strftime("%Y-%m-%d")
        except Exception:
            pass

        divs = t.dividends
        if divs is not None and not divs.empty:
            df = divs.rename("rate").to_frame()
            df["data"] = pd.to_datetime(df.index).tz_localize(None)
            d["div_ano"], d["div_medio"], d["div_12m"] = _proventos_series(df, "data", "rate")
    except Exception as e:
        d["erro"] = f"Erro Yahoo Finance: {e}"
    return d


@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa_yahoo(ticker: str) -> pd.DataFrame:
    try:
        cf = yf.Ticker(normaliza(ticker) + ".SA").cashflow
        if cf is None or cf.empty:
            return pd.DataFrame()
        cf = cf.T.apply(pd.to_numeric, errors="coerce")
        out = pd.DataFrame(index=cf.index)
        if "Operating Cash Flow" in cf:
            out["Caixa operacional"] = cf["Operating Cash Flow"]
        if "Investing Cash Flow" in cf:
            out["Caixa de investimento"] = cf["Investing Cash Flow"]
        if "Free Cash Flow" in cf:
            out["Fluxo de caixa livre"] = cf["Free Cash Flow"]
        elif "Operating Cash Flow" in cf and "Capital Expenditure" in cf:
            out["Fluxo de caixa livre"] = cf["Operating Cash Flow"] + cf["Capital Expenditure"]
        if out.empty:
            return pd.DataFrame()
        out.index = pd.to_datetime(out.index).year
        out = out[out.index.notna()]
        out.index = out.index.astype(int)
        out = out[~out.index.duplicated(keep="first")]
        return out.dropna(how="all").sort_index()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def historico_yahoo(ticker: str, periodo: str, intervalo: str):
    tk = normaliza(ticker) + ".SA"
    p = {"6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y"}.get(periodo, "1y")
    try:
        df = yf.download(tk, period=p, interval=intervalo, progress=False)
        if df.empty:
            return pd.DataFrame(), "Sem dados históricos do Yahoo."
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
        return df.dropna(subset=["Open", "High", "Low", "Close"]), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# --- 3. Fundamentus
@st.cache_data(ttl=900, show_spinner=False)
def buscar_fundamentus(ticker: str) -> dict:
    tk = normaliza(ticker)
    d = dict_base(tk)
    try:
        df = fundamentus.get_detalhes_papel(tk)
        if df is None or df.empty:
            d["erro"] = "Ativo não encontrado no Fundamentus."
            return d
        row = df.loc[tk] if tk in df.index else df.iloc[0]
        d["preco"] = parse_num(row.get("Cotacao"))
        d["lpa"] = parse_num(row.get("LPA"))
        d["vpa"] = parse_num(row.get("VPA"))
        d["ev_ebitda"] = parse_num(row.get("EV_EBITDA"))
        d["roe"] = parse_pct(row.get("ROE"))
        d["margem_liq"] = parse_pct(row.get("Marg_Liquida"))
        dbp = parse_num(row.get("Div_Br_Patrim"))  # razão (1,5 = 150%)
        d["div_pl"] = dbp * 100 if dbp is not None else None
        d["acoes"] = parse_num(row.get("Nro_Acoes"))
        dy = parse_pct(row.get("Div_Yield"))
        if dy is not None and d["preco"]:
            d["div_12m"] = dy * d["preco"]
            d["div_medio"] = d["div_12m"]
            d["alertas"].append("Fundamentus não traz histórico de proventos: a média de 5 anos "
                                "foi aproximada pelo dividend yield atual.")
    except Exception as e:
        d["erro"] = f"Erro Fundamentus: {e}"
    return d


# ---------------------------------------------------------------- normalização e validação
def converter_moeda(d: dict) -> dict:
    """Se o balanço vem em USD e o preço em BRL, converte LPA, VPA e dívida líquida para R$."""
    mb, mp = d.get("moeda_balanco") or "BRL", d.get("moeda") or "BRL"
    if mb == mp:
        return d
    if mp == "BRL" and mb == "USD":
        fx = fx_atual()
        if not fx:
            d["lpa"], d["vpa"], d["divida_liq"] = None, None, None
            d["alertas"].append("Balanço em USD e câmbio indisponível: LPA/VPA descartados "
                                "para não gerar preço justo incorreto.")
            return d
        for k in ("lpa", "vpa", "divida_liq"):
            if d.get(k) is not None:
                d[k] *= fx
        d["fx_aplicado"] = fx
        d["alertas"].append(f"Balanço em USD convertido para R$ (dólar a {num(fx, 4)}).")
    else:
        d["alertas"].append(f"Balanço em {mb} e preço em {mp}: sem conversão automática, "
                            "confira LPA/VPA.")
    return d


def conferir_preco(d: dict, ref: dict):
    """Compara o preço da fonte com o do Yahoo e corrige erros de escala (x100 / ÷100)."""
    p, r = d.get("preco"), ref.get("preco")
    if not p or not r or p <= 0 or r <= 0:
        return
    razao = p / r
    if 95 <= razao <= 105:
        for k in ("preco", "lpa", "vpa"):
            if d.get(k) is not None:
                d[k] /= 100
        d["alertas"].append("Preço/LPA/VPA vieram 100x maiores que a referência e foram reescalados.")
    elif 0.0095 <= razao <= 0.0105:
        for k in ("preco", "lpa", "vpa"):
            if d.get(k) is not None:
                d[k] *= 100
        d["alertas"].append("Preço/LPA/VPA vieram 100x menores que a referência e foram reescalados.")
    elif abs(razao - 1) > 0.15:
        d["alertas"].append(f"Preço da fonte ({brl(p)}) diverge mais de 15% do Yahoo ({brl(r)}).")


def validar(d: dict):
    a, p = d["alertas"], d.get("preco")
    if not p or p <= 0:
        a.append("Preço indisponível.")
    for campo, rot in (("roe", "ROE"), ("margem_liq", "Margem líquida")):
        v = d.get(campo)
        if v is not None and abs(v) > 5:
            d[campo] = v / 100
            a.append(f"{rot} veio fora de escala ({num(v, 0)}) e foi tratado como percentual.")
    if p and d.get("div_12m") is not None and d["div_12m"] / p > 0.5:
        a.append("Dividend yield acima de 50%: provável erro na fonte, confira os proventos.")
    if p and d.get("lpa") is not None and abs(d["lpa"]) > 3 * p:
        a.append("LPA muito acima do preço: possível descompasso de moeda ou unidade.")
    if p and d.get("vpa") is not None and d["vpa"] > 20 * p:
        a.append("VPA muito acima do preço: possível descompasso de moeda ou unidade.")
    if d.get("div_pl") is not None and d["div_pl"] < 0:
        a.append("Dív./PL negativo (patrimônio líquido negativo?).")


def buscar(ticker: str) -> dict:
    fonte = st.session_state.get("fonte_dados", "Yahoo Finance")
    d = {"Brapi": buscar_brapi, "Fundamentus": buscar_fundamentus}.get(fonte, buscar_yahoo)(ticker)
    d = dict(d)
    d["alertas"] = list(d.get("alertas", []))

    if fonte != "Yahoo Finance":
        ref = buscar_yahoo(ticker)
        if not d.get("preco"):
            if ref.get("preco"):
                erro_ant = d.get("erro")
                d = dict(ref)
                d["alertas"] = list(ref.get("alertas", []))
                d["alertas"].append("Fonte escolhida sem preço: dados recuperados do Yahoo Finance.")
                d["erro"] = erro_ant
        else:
            conferir_preco(d, ref)
            for k in ("acoes", "divida_liq", "setor", "data_balanco"):
                if d.get(k) is None and ref.get(k) is not None:
                    d[k] = ref[k]
            if ref.get("moeda_balanco") and fonte == "Fundamentus":
                d["moeda_balanco"] = ref["moeda_balanco"]
    converter_moeda(d)
    validar(d)
    return d


def buscar_caixa(ticker: str):
    """Fluxo de caixa anual em R$. Devolve (DataFrame, aviso)."""
    fonte = st.session_state.get("fonte_dados", "Yahoo Finance")
    df = buscar_caixa_brapi(ticker) if fonte == "Brapi" else pd.DataFrame()
    if df.empty:
        df = buscar_caixa_yahoo(ticker)
    if df.empty:
        return df, None
    d = buscar(ticker)
    mb, mp = d.get("moeda_balanco") or "BRL", d.get("moeda") or "BRL"
    if mb == "USD" and mp == "BRL":
        anual, atual = fx_anual(), fx_atual()
        if not anual and not atual:
            return pd.DataFrame(), "Fluxo de caixa em USD e câmbio indisponível."
        df = df.copy()
        for ano in df.index:
            df.loc[ano] = df.loc[ano] * anual.get(int(ano), atual)
        return df, "Fluxo de caixa convertido de USD para R$ pelo dólar médio de cada ano."
    return df, None


def historico(ticker: str, periodo: str, intervalo: str):
    if st.session_state.get("fonte_dados") == "Brapi":
        df, err = historico_brapi(ticker, periodo, intervalo)
        if not df.empty:
            return df, err
    return historico_yahoo(ticker, periodo, intervalo)


def carregar(ativos):
    out = {}
    with st.spinner(f"Buscando dados via {st.session_state.get('fonte_dados')}..."):
        for tk in ativos:
            try:
                out[tk] = buscar(tk)
            except Exception as e:
                st.warning(f"Não consegui carregar {tk}: {e}")
    return out


def dados_ativos():
    ativos = st.session_state.get("sel_ativos", [])
    if not ativos:
        st.info("Selecione ao menos um ativo na barra superior ou adicione um ticker em **➕ Ativo**.")
        return {}
    dados = carregar(ativos)
    painel_alertas(dados)
    return dados


def painel_alertas(dados: dict):
    itens = []
    for tk, d in dados.items():
        itens += [f"**{tk}** — {a}" for a in d.get("alertas", [])]
        if d.get("erro"):
            itens.append(f"**{tk}** — {d['erro']}")
    if itens:
        with st.expander(f"⚠️ Qualidade dos dados ({len(itens)} aviso(s))"):
            for i in itens:
                st.markdown(f"- {i}")


# ---------------------------------------------------------------- cálculos
def analisar(d: dict, metodo: str, yield_alvo: float, margem_alvo: float) -> dict:
    lpa, vpa, preco, div_medio = d.get("lpa"), d.get("vpa"), d.get("preco"), d.get("div_medio")
    graham = None
    if lpa is not None and vpa is not None and lpa > 0 and vpa > 0:
        graham = sqrt(22.5 * lpa * vpa)
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

    margem = None
    if justo and preco and justo > 0:
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
    p, lpa, vpa = d.get("preco"), d.get("lpa"), d.get("vpa")
    div_12m, roe, ml = d.get("div_12m"), d.get("roe"), d.get("margem_liq")
    return {
        "pl": p / lpa if p and lpa and lpa > 0 else None,
        "pvp": p / vpa if p and vpa and vpa > 0 else None,
        "dy": div_12m / p * 100 if p and p > 0 and div_12m is not None else None,
        "roe": roe * 100 if roe is not None else None,
        "margem": ml * 100 if ml is not None else None,
    }


def dcf_modelo(base, acoes, taxa, g, gp, anos=5, divida_liq=0.0):
    """DCF de dois estágios. Devolve (resultado, erro)."""
    if base is None or pd.isna(base) or base <= 0:
        return None, "Fluxo de caixa livre base não positivo."
    if not acoes or acoes <= 0:
        return None, "Número de ações indisponível."
    if taxa <= gp:
        return None, "A taxa de desconto precisa ser maior que o crescimento na perpetuidade."
    fluxos = [base * (1 + g) ** t for t in range(1, anos + 1)]
    vps = [f / (1 + taxa) ** t for t, f in enumerate(fluxos, start=1)]
    vt = fluxos[-1] * (1 + gp) / (taxa - gp)
    vp_vt = vt / (1 + taxa) ** anos
    ev = sum(vps) + vp_vt
    equity = ev - (divida_liq or 0.0)
    if equity <= 0:
        return None, "Valor do equity ≤ 0 após descontar a dívida líquida."
    return {"valor": equity / acoes, "ev": ev, "vp_explicito": sum(vps), "vp_terminal": vp_vt,
            "pct_terminal": vp_vt / ev * 100, "fluxos": fluxos, "vps": vps}, None


def fcl_base(caixa: pd.DataFrame, modo: str, n: int):
    if caixa.empty or "Fluxo de caixa livre" not in caixa:
        return None
    s = caixa["Fluxo de caixa livre"].dropna()
    if s.empty:
        return None
    return float(s.tail(n).mean()) if modo.startswith("Média") else float(s.iloc[-1])


def gauge(margem, cor=ACCENT):
    v = 0 if margem is None or pd.isna(margem) else max(-60, min(60, margem))
    fig = go.Figure(go.Indicator(
        mode="gauge+number", value=v,
        number={"suffix": "%", "font": {"size": 26, "color": TEXT}},
        gauge={"axis": {"range": [-60, 60], "tickcolor": MUTED},
               "bar": {"color": cor, "thickness": 0.22},
               "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
               "steps": [{"range": [-60, 0], "color": "rgba(248,81,73,.20)"},
                         {"range": [0, 20], "color": "rgba(210,153,34,.20)"},
                         {"range": [20, 60], "color": "rgba(63,185,80,.20)"}]},
    ))
    fig.update_layout(height=115, margin=dict(l=10, r=10, t=10, b=0),
                      **{k: v_ for k, v_ in PLOT.items() if k != "margin"})
    return fig


def escala(v, ruim, bom):
    """Nota 0-100 linear entre 'ruim' (0) e 'bom' (100); funciona nos dois sentidos."""
    if v is None or pd.isna(v) or ruim == bom:
        return None
    return max(0.0, min(1.0, (v - ruim) / (bom - ruim))) * 100


def media(lista):
    vals = [x for x in lista if x is not None]
    return sum(vals) / len(vals) if vals else None


# ---------------------------------------------------------------- página: visão geral
def pagina_inicio():
    st.markdown("#### Contexto macro")
    selic, ipca, dol = buscar_macro_bcb(432, 2), buscar_macro_bcb(13522, 2), buscar_macro_bcb(1, 2)
    c1, c2, c3, c4 = st.columns(4)
    s_v = selic["valor"].iloc[-1] if not selic.empty else None
    i_v = ipca["valor"].iloc[-1] if not ipca.empty else None
    d_v = dol["valor"].iloc[-1] if not dol.empty else None
    def _ref(df, mensal=False):
        return "Ref. " + df.index[-1].strftime("%m/%Y" if mensal else "%d/%m/%Y") if not df.empty else None
    with c1:
        kpi("Selic meta", pct(s_v, 2), "Selic", _ref(selic))
    with c2:
        kpi("IPCA 12 meses", pct(i_v, 2), "IPCA 12m", _ref(ipca, True))
    with c3:
        kpi("Dólar (venda)", brl(d_v), "Dólar", _ref(dol))
    with c4:
        kpi("Juro real (Selic − IPCA 12m)",
            pct(s_v - i_v, 2) if s_v is not None and i_v is not None else "—", "Juro real")
    st.caption("Leitura completa, época dos dados e impacto por ação e setor em Técnica & Macro → Macroeconomia.")

    st.markdown("#### Resumo dos ativos")
    dados = dados_ativos()
    if not dados:
        return
    linhas = []
    for d in dados.values():
        r = analisar(d, "Média", 6.0, 20)
        m = multiplos(d)
        linhas.append({"Ativo": d["ticker"], "Preço": d["preco"], "Preço justo": r["justo"],
                       "Margem (%)": r["margem"], "P/L": m["pl"], "P/VP": m["pvp"],
                       "DY 12m (%)": m["dy"], "Status": r["status"]})
    df = pd.DataFrame(linhas)
    st.dataframe(estilizar(df, {"Preço": brl, "Preço justo": brl, "Margem (%)": pct, "P/L": num,
                                "P/VP": num, "DY 12m (%)": pct}),
                 width="stretch", hide_index=True, column_config=cfg_ajuda(df))
    st.caption("Preço justo = média de Graham e Bazin (yield 6%, margem alvo 20%). "
               "Ajuste os parâmetros em Fundamentalista → Preço justo.")


# ---------------------------------------------------------------- páginas: fundamentalista
def pagina_preco_justo():
    dados = dados_ativos()
    if not dados:
        return
    c1, c2, c3 = st.columns(3)
    metodo = c1.selectbox("Método", ["Média (Graham + Bazin)", "Graham", "Bazin"])
    yield_alvo = c2.slider("Dividend yield desejado (Bazin)", 4.0, 12.0, 6.0, 0.5, format="%.1f%%")
    margem_alvo = c3.slider("Margem de segurança alvo", 5, 50, 20, 5, format="%d%%")
    st.caption("Graham = √(22,5 × LPA × VPA) · Bazin = dividendo médio dos últimos 5 anos completos ÷ yield desejado")

    resultados = [analisar(d, metodo.split(" ")[0], yield_alvo, margem_alvo) for d in dados.values()]
    t_painel, t_comp = st.tabs(["Painel", "Comparativo"])

    with t_painel:
        por_linha = 3
        for i in range(0, len(resultados), por_linha):
            cols = st.columns(por_linha)
            for col, r in zip(cols, resultados[i:i + por_linha]):
                with col:
                    aviso_moeda = ""
                    if r.get("fx_aplicado"):
                        aviso_moeda = (f'<div class="aviso">Balanço em USD convertido (dólar {num(r["fx_aplicado"], 2)})</div>')
                    sem_graham = (r.get("lpa") or 0) <= 0 or (r.get("vpa") or 0) <= 0
                    aviso_lpa = ('<div class="aviso" style="color:#f85149;">⚠️ LPA ou VPA negativo/ausente (Graham indisponível)</div>'
                                 if sem_graham else "")
                    st.markdown(
                        f"""<div class="card" style="border-top:3px solid {cor_ativo(r['ticker'])};">
<span class="badge {r['cls']}">{r['status']}</span>
<div class="tk">{html.escape(r['ticker'])}</div>
<div class="nm">{html.escape(str(r['nome']))}</div>
<div style="display:flex; gap:22px;">
<div><div class="lbl">Preço atual{tip('Preço')}</div><div class="val">{brl(r['preco'])}</div></div>
<div><div class="lbl">Preço justo{tip('Preço justo')}</div><div class="val">{brl(r['justo'])}</div></div>
</div>
<div style="margin-top:10px;">
<div class="lbl">Média de dividendos (5 anos){tip('Média 5 anos')}</div>
<div class="val">{brl(r['div_medio'])} <span style="font-size:.72rem;color:{MUTED}">/ ano</span></div>
</div>{aviso_moeda}{aviso_lpa}</div>""",
                        unsafe_allow_html=True)
                    st.plotly_chart(gauge(r["margem"], cor_ativo(r["ticker"])), width="stretch",
                                    key=f"g_{r['ticker']}", config={"displayModeBar": False})
                    st.caption(f"Margem de segurança · Graham {brl(r['graham'])} · Bazin {brl(r['bazin'])}")

    with t_comp:
        df = pd.DataFrame([{"Ticker": r["ticker"], "Preço": r["preco"], "Preço justo": r["justo"],
                            "Margem (%)": r["margem"], "Status": r["status"]} for r in resultados])
        g1, g2 = st.columns(2)
        with g1:
            md(f'<div class="sec">Preço atual × preço justo{tip("Preço justo")}</div>')
            cores = [cor_ativo(t) for t in df["Ticker"]]
            fig = go.Figure()
            fig.add_bar(x=df["Ticker"], y=df["Preço"], name="Preço atual (tom claro)",
                        marker_color=cores, marker_opacity=0.45)
            fig.add_bar(x=df["Ticker"], y=df["Preço justo"], name="Preço justo (tom cheio)", marker_color=cores)
            fig.update_layout(barmode="group", height=250, legend=dict(orientation="h", y=1.15, x=0), **PLOT)
            fig.update_yaxes(**GRID)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        with g2:
            md(f'<div class="sec">Margem de segurança{tip("Margem (%)")}</div>')
            d2 = df.dropna(subset=["Margem (%)"]).sort_values("Margem (%)")
            if d2.empty:
                st.info("Sem margem calculável para os ativos selecionados.")
            else:
                fig2 = go.Figure(go.Bar(
                    x=d2["Margem (%)"], y=d2["Ticker"], orientation="h",
                    marker_color=[cor_ativo(t) for t in d2["Ticker"]],
                    text=[pct(m) for m in d2["Margem (%)"]], textposition="outside"))
                fig2.add_vline(x=margem_alvo, line_dash="dot", line_color=MUTED,
                               annotation_text=f"alvo {margem_alvo}%", annotation_font_color=MUTED)
                fig2.update_layout(height=max(200, 70 + 34 * len(d2)), **PLOT)
                fig2.update_xaxes(**GRID)
                st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
        st.dataframe(estilizar(df, {"Preço": brl, "Preço justo": brl, "Margem (%)": pct}),
                     width="stretch", hide_index=True, column_config=cfg_ajuda(df))


def pagina_valuation():
    dados = dados_ativos()
    if not dados:
        return
    linhas = []
    for tk, d in dados.items():
        m = multiplos(d)
        linhas.append({"Ticker": tk, "Preço": d["preco"], "P/L": m["pl"], "P/VP": m["pvp"],
                       "EV/EBITDA": d["ev_ebitda"], "DY 12m (%)": m["dy"], "ROE (%)": m["roe"],
                       "Margem líq. (%)": m["margem"], "Dív./PL (%)": d["div_pl"]})
    df = pd.DataFrame(linhas)
    metrica = st.selectbox("Comparar por", [c for c in df.columns if c not in ("Ticker", "Preço")])
    gA, gB = st.columns([1.3, 1])
    d2 = df.dropna(subset=[metrica]).sort_values(metrica)
    with gA:
        if d2.empty:
            st.info("Sem dados disponíveis para esse indicador nos ativos selecionados.")
        else:
            fig = go.Figure(go.Bar(x=d2["Ticker"], y=d2[metrica],
                                   marker_color=[cor_ativo(t) for t in d2["Ticker"]],
                                   text=[num(v) for v in d2[metrica]], textposition="outside"))
            fig.update_layout(title=metrica, height=260, **PLOT)
            fig.update_yaxes(**GRID)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with gB:
        explica(metrica)
    fmts = {c: num for c in df.columns if c != "Ticker"}
    fmts.update({"Preço": brl, "DY 12m (%)": pct, "ROE (%)": pct, "Margem líq. (%)": pct, "Dív./PL (%)": pct})
    st.dataframe(estilizar(df, fmts), width="stretch", hide_index=True, column_config=cfg_ajuda(df))


def pagina_dividendos():
    dados = dados_ativos()
    if not dados:
        return
    fig = go.Figure()
    for d in dados.values():
        if d.get("div_ano") is not None and len(d["div_ano"]) > 0:
            fig.add_bar(x=[str(a) for a in d["div_ano"].index], y=d["div_ano"].values,
                        name=d["ticker"], marker_color=cor_ativo(d["ticker"]))
    fig.update_layout(barmode="group", title="Dividendos por ação (R$/ano)", height=270,
                      legend=dict(orientation="h", y=1.15, x=0), **PLOT)
    fig.update_yaxes(**GRID)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    linhas = []
    for t, d in dados.items():
        p, d12, dm = d.get("preco"), d.get("div_12m"), d.get("div_medio")
        linhas.append({"Ticker": t, "Proventos 12m": d12, "Média 5 anos": dm,
                       "DY 12m (%)": d12 / p * 100 if p and p > 0 and d12 is not None else None,
                       "DY s/ média 5a (%)": dm / p * 100 if p and p > 0 and dm is not None else None})
    df_div = pd.DataFrame(linhas)
    st.dataframe(estilizar(df_div, {
        "Proventos 12m": brl, "Média 5 anos": brl, "DY 12m (%)": pct, "DY s/ média 5a (%)": pct}),
        width="stretch", hide_index=True, column_config=cfg_ajuda(df_div))


# ---------------------------------------------------------------- página: DCF
def grafico_caixa(caixa: pd.DataFrame):
    cores = {"Caixa operacional": "#8b949e", "Caixa de investimento": BAD, "Fluxo de caixa livre": GOOD}
    fig = go.Figure()
    for col in caixa.columns:
        fig.add_bar(x=[str(a) for a in caixa.index], y=caixa[col] / 1e6, name=col, marker_color=cores.get(col))
    fig.update_layout(barmode="group", height=250, title="Fluxo de caixa histórico (R$ milhões)",
                      legend=dict(orientation="h", y=1.15), **PLOT)
    fig.update_yaxes(**GRID)
    return fig


def pagina_dcf():
    dados = dados_ativos()
    if not dados:
        return
    tk = st.selectbox("Ativo", list(dados), key="dcf_ativo")
    d = dados[tk]
    if eh_financeiro(tk):
        st.info(f"ℹ️ **{tk} é do setor financeiro.** Fluxo de caixa livre e DCF tradicional sofrem "
                "distorções estruturais em bancos e seguradoras; prefira Graham, Bazin e P/VP.")

    caixa, aviso = buscar_caixa(tk)
    if aviso:
        st.caption(f"ℹ️ {aviso}")
    if caixa.empty or "Fluxo de caixa livre" not in caixa:
        st.warning(f"Sem dados de fluxo de caixa livre para {tk} na fonte atual.")
        return

    st.plotly_chart(grafico_caixa(caixa), width="stretch")

    st.markdown("#### Premissas")
    selic = buscar_macro_bcb(432, 1)
    if not selic.empty:
        st.caption(f"Referência: Selic meta atual {pct(selic['valor'].iloc[-1], 2)} a.a.")
    p1, p2, p3 = st.columns(3)
    modo = p1.radio("FCL base", ["Média dos últimos N anos", "Último ano"], horizontal=False)
    n_anos = p1.slider("Anos na média", 2, 5, 3) if modo.startswith("Média") else 1
    horizonte = p2.slider("Horizonte explícito (anos)", 5, 10, 5)
    taxa = p2.slider("Taxa de desconto", 8.0, 25.0, 13.0, 0.5, format="%.1f%%") / 100
    g = p3.slider("Crescimento do FCL no período", -5.0, 20.0, 4.0, 0.5, format="%.1f%%") / 100
    gp = p3.slider("Crescimento na perpetuidade", 0.0, 6.0, 3.0, 0.5, format="%.1f%%") / 100
    desc_div = st.checkbox("Descontar dívida líquida do valor da firma",
                           value=False,
                           help="Marque se o fluxo de caixa for da firma (antes de juros). "
                                "Com FCL já após juros, deixe desmarcado.")

    base = fcl_base(caixa, modo, n_anos)
    divida = d.get("divida_liq") if desc_div else 0.0
    if desc_div and divida is None:
        st.warning("Dívida líquida indisponível para este ativo; considerando zero.")
        divida = 0.0
    res, erro = dcf_modelo(base, d.get("acoes"), taxa, g, gp, horizonte, divida)
    if erro:
        st.warning(f"DCF não calculado: {erro}")
        return

    preco = d.get("preco")
    margem = (res["valor"] - preco) / res["valor"] * 100 if preco else None
    potencial = (res["valor"] / preco - 1) * 100 if preco else None
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        kpi("Valor justo (DCF)", brl(res["valor"]), "Valor DCF", cor=cor_ativo(tk))
    with m2:
        kpi("Preço atual", brl(preco), "Preço")
    with m3:
        kpi("Margem de segurança", pct(margem), "Margem (%)")
    with m4:
        kpi("Potencial", pct(potencial), "Potencial")
    with st.expander("ⓘ O que significam os termos do DCF?"):
        for k_ in ("FCL", "Taxa de desconto", "Perpetuidade", "Valor terminal"):
            explica(k_)
    if res["pct_terminal"] > 75:
        st.warning(f"⚠️ {pct(res['pct_terminal'], 0)} do valor vem da perpetuidade: o resultado é muito "
                   "sensível às premissas de longo prazo.")
    else:
        st.caption(f"Valor terminal = {pct(res['pct_terminal'], 0)} do valor da firma · "
                   f"FCL base {brl(base / 1e6)} mi")

    cA, cB = st.columns(2)
    anos_lbl = [f"Ano {i}" for i in range(1, horizonte + 1)]
    fig = go.Figure()
    fig.add_bar(x=anos_lbl, y=[f / 1e6 for f in res["fluxos"]], name="FCL projetado", marker_color="#8b949e")
    fig.add_bar(x=anos_lbl, y=[v / 1e6 for v in res["vps"]], name="Valor presente", marker_color=ACCENT)
    fig.update_layout(barmode="group", height=290, title="Fluxos projetados (R$ milhões)",
                      legend=dict(orientation="h", y=-0.15), **PLOT)
    fig.update_yaxes(**GRID)
    with cA:
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with cB:
        st.caption("Sensibilidade: potencial vs. preço atual conforme taxa de desconto e perpetuidade")
    taxas = [taxa + x for x in (-0.02, -0.01, 0, 0.01, 0.02)]
    gps = sorted({round(max(0.0, gp + x), 4) for x in (-0.01, -0.005, 0, 0.005, 0.01)})
    z, txt = [], []
    for t_ in taxas:
        lz, lt = [], []
        for gp_ in gps:
            r_, _ = dcf_modelo(base, d.get("acoes"), t_, g, gp_, horizonte, divida)
            lz.append((r_["valor"] / preco - 1) * 100 if r_ and preco else None)
            lt.append(brl(r_["valor"]) if r_ else "—")
        z.append(lz)
        txt.append(lt)
    heat = go.Figure(go.Heatmap(
        z=z, x=[pct(x * 100) for x in gps], y=[pct(x * 100) for x in taxas], text=txt,
        texttemplate="%{text}", colorscale="RdYlGn", zmid=0,
        colorbar=dict(title="Potencial %")))
    heat.update_layout(height=290, xaxis_title="Crescimento na perpetuidade",
                       yaxis_title="Taxa de desconto", **PLOT)
    with cB:
        st.plotly_chart(heat, width="stretch", config={"displayModeBar": False})

    st.markdown("#### Cenários")
    cen = {"Pessimista": (taxa + 0.02, g - 0.03, max(0.0, gp - 0.01)),
           "Base": (taxa, g, gp),
           "Otimista": (taxa - 0.01, g + 0.03, gp + 0.005)}
    linhas = []
    for nome, (t_, g_, gp_) in cen.items():
        r_, e_ = dcf_modelo(base, d.get("acoes"), t_, g_, gp_, horizonte, divida)
        linhas.append({"Cenário": nome, "Taxa (%)": t_ * 100, "Cresc. FCL (%)": g_ * 100,
                       "Perpetuidade (%)": gp_ * 100, "Valor DCF": r_["valor"] if r_ else None,
                       "Potencial (%)": (r_["valor"] / preco - 1) * 100 if r_ and preco else None})
    st.dataframe(estilizar(pd.DataFrame(linhas), {
        "Taxa (%)": pct, "Cresc. FCL (%)": pct, "Perpetuidade (%)": pct,
        "Valor DCF": brl, "Potencial (%)": pct}), width="stretch", hide_index=True)

    st.markdown("#### Todos os ativos selecionados (mesmas premissas)")
    linhas = []
    for t, dd in dados.items():
        cx, _ = buscar_caixa(t)
        b = fcl_base(cx, modo, n_anos)
        dv = dd.get("divida_liq") if desc_div else 0.0
        r_, e_ = dcf_modelo(b, dd.get("acoes"), taxa, g, gp, horizonte, dv or 0.0)
        p_ = dd.get("preco")
        obs = "Financeira: DCF pouco confiável" if eh_financeiro(t) else (e_ or "")
        linhas.append({"Ticker": t, "FCL base (R$ mi)": b / 1e6 if b is not None else None,
                       "Valor DCF": r_["valor"] if r_ else None, "Preço": p_,
                       "Margem (%)": (r_["valor"] - p_) / r_["valor"] * 100 if r_ and p_ else None,
                       "Observação": obs})
    st.dataframe(estilizar(pd.DataFrame(linhas), {
        "FCL base (R$ mi)": lambda v: num(v, 0), "Valor DCF": brl, "Preço": brl, "Margem (%)": pct}),
        width="stretch", hide_index=True)
    st.caption("Modelo educacional: o resultado depende das premissas e não é recomendação de investimento.")


# ---------------------------------------------------------------- página: stock picking
PILARES = ["Valor", "Qualidade", "Dividendos", "Solidez", "Tendência"]


def tendencia(ticker: str):
    df, _ = historico(ticker, "1y", "1d")
    if df.empty or len(df) < 200:
        return None
    c = df["Close"]
    mm50, mm200 = c.rolling(50).mean().iloc[-1], c.rolling(200).mean().iloc[-1]
    if pd.isna(mm50) or pd.isna(mm200) or mm200 <= 0:
        return None
    return {"dist200": (c.iloc[-1] / mm200 - 1) * 100, "cruz": bool(mm50 > mm200)}


def pontuar(d: dict, r: dict, margem_dcf, trend) -> dict:
    m = multiplos(d)
    fin = eh_financeiro(d["ticker"])
    lpa, vpa, ev = d.get("lpa"), d.get("vpa"), d.get("ev_ebitda")

    valor = media([
        escala(r["margem"], -20, 40),
        0.0 if (lpa is not None and lpa <= 0) else escala(m["pl"], 25, 6),
        0.0 if (vpa is not None and vpa <= 0) else escala(m["pvp"], 4, 0.8),
        None if fin else (0.0 if (ev is not None and ev <= 0) else escala(ev, 12, 3)),
        None if fin else escala(margem_dcf, -30, 40),
    ])
    qualidade = media([escala(m["roe"], 0, 20), escala(m["margem"], 0, 20)])

    consist = None
    da = d.get("div_ano")
    if da is not None and len(da) > 0:
        completos = da[da.index < datetime.now().year].tail(5)
        if len(completos) >= 3:
            consist = float((completos > 0).sum() / len(completos) * 100)
    dividendos = media([escala(m["dy"], 0, 8), consist])

    solidez = None if fin else escala(d.get("div_pl"), 300, 40)
    tend = media([escala(trend["dist200"], -10, 15), 100.0 if trend["cruz"] else 0.0]) if trend else None
    return {"Valor": valor, "Qualidade": qualidade, "Dividendos": dividendos,
            "Solidez": solidez, "Tendência": tend}


def pagina_picking():
    dados = dados_ativos()
    if not dados:
        return
    st.caption("Ranking quantitativo para comparar os ativos selecionados. "
               "Adicione mais tickers na barra superior para ampliar o universo.")

    with st.expander("Pesos e critérios", expanded=False):
        cols = st.columns(5)
        pesos = {p: cols[i].slider(p, 0, 100, v, 5, key=f"w_{p}", help=ajuda_txt(p))
                 for i, (p, v) in enumerate(zip(PILARES, [30, 25, 20, 15, 10]))}
        usar_tend = st.checkbox("Incluir tendência (preço vs. médias de 50 e 200 dias)", value=True)
        st.markdown(
            "- **Valor**: margem de segurança (Graham/Bazin), P/L, P/VP, EV/EBITDA e margem do DCF\n"
            "- **Qualidade**: ROE e margem líquida\n"
            "- **Dividendos**: dividend yield 12m e regularidade nos últimos 5 anos\n"
            "- **Solidez**: Dív./PL (não se aplica a financeiras)\n"
            "- **Tendência**: distância da média de 200 dias e cruzamento 50×200\n\n"
            "Cada indicador vira nota de 0 a 100 entre um piso e um teto fixos; pilares sem dados "
            "são ignorados e os pesos são reponderados.")
    if not usar_tend:
        pesos["Tendência"] = 0

    linhas = []
    with st.spinner("Calculando notas..."):
        for tk, d in dados.items():
            r = analisar(d, "Média", 6.0, 20)
            margem_dcf = None
            if not eh_financeiro(tk):
                cx, _ = buscar_caixa(tk)
                res, _e = dcf_modelo(fcl_base(cx, "Média", 3), d.get("acoes"), 0.13, 0.04, 0.03, 5, 0.0)
                if res and d.get("preco"):
                    margem_dcf = (res["valor"] - d["preco"]) / res["valor"] * 100
            tr = tendencia(tk) if usar_tend else None
            pil = pontuar(d, r, margem_dcf, tr)
            disp = {p: v for p, v in pil.items() if v is not None and pesos[p] > 0}
            soma = sum(pesos[p] for p in disp)
            nota = sum(pil[p] * pesos[p] for p in disp) / soma if soma > 0 else None
            linhas.append({"Ativo": tk, "Nota": nota, **pil,
                           "Cobertura": f"{sum(v is not None for v in pil.values())}/5",
                           "Preço": d.get("preco"), "Preço justo": r["justo"],
                           "Margem (%)": r["margem"], "Status": r["status"]})

    df = pd.DataFrame(linhas).sort_values("Nota", ascending=False, na_position="last").reset_index(drop=True)
    df.insert(0, "#", range(1, len(df) + 1))

    def rotulo(n):
        return "—" if n is None or pd.isna(n) else ("Alta" if n >= 70 else "Moderada" if n >= 50 else "Baixa")
    df.insert(3, "Atratividade", df["Nota"].map(rotulo))

    pc = {p: st.column_config.ProgressColumn(p, help=ajuda_txt(p), min_value=0, max_value=100, format="%.0f")
          for p in ["Nota"] + PILARES}
    pc.update({"Preço": st.column_config.NumberColumn("Preço", help=ajuda_txt("Preço"), format="R$ %.2f"),
               "Preço justo": st.column_config.NumberColumn("Preço justo", help=ajuda_txt("Preço justo"), format="R$ %.2f"),
               "Margem (%)": st.column_config.NumberColumn("Margem (%)", help=ajuda_txt("Margem (%)"), format="%.1f%%"),
               "Atratividade": st.column_config.Column(help=ajuda_txt("Atratividade")),
               "Cobertura": st.column_config.Column(help=ajuda_txt("Cobertura")),
               "Status": st.column_config.Column(help=ajuda_txt("Status"))})
    st.dataframe(df, width="stretch", hide_index=True, column_config=pc)

    g1, g2 = st.columns(2)
    with g1:
        top = df.dropna(subset=["Nota"]).sort_values("Nota")
        if not top.empty:
            fig = go.Figure(go.Bar(
                x=top["Nota"], y=top["Ativo"], orientation="h", text=[num(v, 0) for v in top["Nota"]],
                textposition="outside",
                marker_color=[cor_ativo(t) for t in top["Ativo"]]))
            fig.update_layout(title="Nota geral", height=max(200, 80 + 32 * len(top)),
                              xaxis=dict(range=[0, 110]), **PLOT)
            fig.update_xaxes(**GRID)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with g2:
        q = df.dropna(subset=["Valor", "Qualidade"])
        if not q.empty:
            fig = go.Figure(go.Scatter(
                x=q["Valor"], y=q["Qualidade"], mode="markers+text", text=q["Ativo"],
                textposition="top center",
                marker=dict(size=13, color=[cor_ativo(t) for t in q["Ativo"]])))
            fig.add_vline(x=50, line_color=BORDER)
            fig.add_hline(y=50, line_color=BORDER)
            fig.update_layout(title="Valor × Qualidade (alto-direito = barato e bom)", height=260,
                              xaxis=dict(range=[-5, 105], title="Valor"),
                              yaxis=dict(range=[-5, 105], title="Qualidade"), **PLOT)
            fig.update_xaxes(**GRID)
            fig.update_yaxes(**GRID)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown("#### Perfil por ativo")
    sel = st.multiselect("Ativos no radar", list(df["Ativo"]), default=list(df["Ativo"])[:3], key="radar_sel")
    if sel:
        radar = go.Figure()
        for tk in sel:
            row = df[df["Ativo"] == tk].iloc[0]
            vals = [0 if pd.isna(row[p]) else row[p] for p in PILARES]
            radar.add_trace(go.Scatterpolar(r=vals + vals[:1], theta=PILARES + PILARES[:1],
                                            fill="toself", name=tk, opacity=0.55,
                                            line=dict(color=cor_ativo(tk))))
        radar.update_layout(height=330, polar=dict(bgcolor="rgba(0,0,0,0)",
                                                   radialaxis=dict(range=[0, 100], gridcolor=BORDER),
                                                   angularaxis=dict(gridcolor=BORDER)),
                            legend=dict(orientation="h", y=-0.1), **PLOT)
        st.plotly_chart(radar, width="stretch")
    st.caption("Ferramenta educacional para triagem. A nota não é recomendação de compra ou venda; "
               "pilar vazio no radar significa dado indisponível (plotado como 0).")


# ---------------------------------------------------------------- páginas: macro & micro
def cartao_serie(titulo, df, anos, fmt, cor, unid="", barra=False, degrau=False):
    if df.empty:
        st.warning(f"{titulo}: dados indisponíveis no momento.")
        return
    s = df.loc[df.index >= df.index.max() - pd.DateOffset(years=anos), "valor"].dropna()
    if s.empty:
        st.warning(f"{titulo}: sem dados no período.")
        return
    delta = None
    if len(s) > 1:
        delta = _sep(f"{s.iloc[-1] - s.iloc[-2]:+.2f}") + (f" {unid}" if unid else "")
    st.metric(titulo, fmt(s.iloc[-1]), delta=delta, delta_color="off",
              help=f"Última leitura: {s.index[-1]:%d/%m/%Y}")
    fig = go.Figure()
    if barra:
        fig.add_bar(x=s.index, y=s, marker_color=cor)
    else:
        fig.add_scatter(x=s.index, y=s, mode="lines", line=dict(color=cor, width=2, shape="hv" if degrau else "linear"))
    fig.update_layout(height=250, **PLOT)
    fig.update_yaxes(**GRID)
    st.plotly_chart(fig, width="stretch", key=f"serie_{titulo}")


def pagina_macro():
    anos = st.segmented_control("Período", [1, 2, 5, 10], default=2,
                                format_func=lambda x: f"{x} ano{'s' if x > 1 else ''}", key="macro_anos") or 2
    t_bcb, t_ipea = st.tabs(["🏦 Banco Central (SGS)", "🏛️ IPEADATA"])
    with t_bcb:
        c1, c2 = st.columns(2)
        with c1:
            cartao_serie("Selic meta (% a.a.)", buscar_macro_bcb(432, 10), anos, lambda v: pct(v, 2), GOOD, "p.p.", degrau=True)
        with c2:
            cartao_serie("IPCA acumulado 12m (%)", buscar_macro_bcb(13522, 10), anos, lambda v: pct(v, 2), FAIR, "p.p.")
        st.markdown("---")
        c3, c4 = st.columns(2)
        with c3:
            cartao_serie("Dólar comercial venda (R$)", buscar_macro_bcb(1, 10), anos, brl, ACCENT, "R$")
        with c4:
            cartao_serie("Desemprego PNAD (%)", buscar_macro_bcb(24369, 10), anos, lambda v: pct(v, 1), BAD, "p.p.")
    with t_ipea:
        i1, i2 = st.columns(2)
        with i1:
            cartao_serie("Risco-País EMBI+ (pontos)", buscar_macro_ipea("JPM366_EMBI366"), anos,
                         lambda v: f"{num(v, 0)} pts", "#bc8cff", "pts")
        with i2:
            cartao_serie("IGP-M mensal (%)", buscar_macro_ipea("IGP12_IGPMG12"), anos,
                         lambda v: pct(v, 2), "#33b3ae", "p.p.", barra=True)


def pagina_micro():
    dados = dados_ativos()
    if not dados:
        return
    st.markdown("#### Matriz de indicadores microeconômicos")
    linhas = []
    for tk, d in dados.items():
        m = multiplos(d)
        linhas.append({"Ativo": tk, "Preço": d.get("preco"), "LPA": d.get("lpa"), "VPA": d.get("vpa"),
                       "EV/EBITDA": d.get("ev_ebitda"), "DY 12m (%)": m["dy"], "ROE (%)": m["roe"],
                       "Margem líq. (%)": m["margem"], "Dív./PL (%)": d.get("div_pl")})
    st.dataframe(estilizar(pd.DataFrame(linhas), {
        "Preço": brl, "LPA": brl, "VPA": brl, "EV/EBITDA": num, "DY 12m (%)": pct,
        "ROE (%)": pct, "Margem líq. (%)": pct, "Dív./PL (%)": pct}),
        width="stretch", hide_index=True)
    st.caption("LPA e VPA em R$ (balanços em dólar são convertidos automaticamente). "
               "ROE e margens em %, Dív./PL em % do patrimônio.")


# ---------------------------------------------------------------- página: técnica
def tradingview(ticker: str, intervalo: str, altura: int):
    cfg = {"autosize": True, "symbol": f"BMFBOVESPA:{ticker}", "interval": intervalo,
           "timezone": "America/Sao_Paulo", "theme": "dark", "style": "1", "locale": "br",
           "enable_publishing": False, "hide_side_toolbar": True, "allow_symbol_change": False,
           "backgroundColor": BG, "toolbar_bg": BG, "gridColor": BORDER, "container_id": "tv_chart"}
    components.html(f"""
<style>body{{margin:0;background:{BG};}}</style>
<div style="height:{altura}px;width:100%;"><div id="tv_chart" style="height:100%;width:100%;"></div></div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>new TradingView.widget({json.dumps(cfg)});</script>""", height=altura)


def pagina_tecnica():
    ativos = st.session_state.get("sel_ativos", [])
    if not ativos:
        st.info("Selecione ao menos um ativo na barra superior.")
        return
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
            msg += f" (Erro: {erro})"
        st.warning(msg)
        return

    sinais, padroes, niveis = [], [], []
    try:
        ind = tec.indicadores(df, int(mm_c), int(mm_l))
        if "Candlestick" in grupos:
            sinais += [s for s in tec.candlesticks(df) if s["sinal"] in candles_sel]
        if "Padrões gráficos" in grupos:
            padroes, niveis = tec.padroes_graficos(df)
        if "Indicadores (MM, IFR, volume)" in grupos:
            sinais += ind["sinais"]
    except Exception as e:
        st.warning(f"Erro ao calcular indicadores técnicos: {e}")
        ind = {"sinais": []}

    corte = df.index[-10] if len(df) >= 10 else df.index[0]
    rec = [s for s in sinais + padroes if s["data"] >= corte]
    m1, m2, m3 = st.columns(3)
    m1.metric("Sinais de alta (10 candles)", sum(s["tipo"] == "alta" for s in rec))
    m2.metric("Sinais de baixa (10 candles)", sum(s["tipo"] == "baixa" for s in rec))
    m3.metric("Indecisão (10 candles)", sum(s["tipo"] == "neutro" for s in rec))

    link = f"https://br.tradingview.com/chart/?symbol=BMFBOVESPA%3A{ticker}"
    lado = layout == "Lado a lado"
    alt_tv, alt_sinais = (440, 500) if lado else (400, 520)

    def bloco_limpo():
        st.markdown("#### Gráfico limpo · TradingView")
        tradingview(ticker, tv_int, alt_tv)
        st.link_button("Abrir no TradingView ↗", link)

    def bloco_sinais():
        st.markdown("#### Gráfico com sinais")
        try:
            fig = tec.figura(df, sinais, padroes, niveis, ind, diario=(tf == "Diário"),
                             altura=alt_sinais, mostrar_mm=mostrar_mm)
            st.plotly_chart(fig, width="stretch", config={"displaylogo": False})
        except Exception as e:
            st.error(f"Erro ao renderizar gráfico técnico: {e}")

    if lado:
        a, b = st.columns(2)
        with a:
            bloco_limpo()
        with b:
            bloco_sinais()
    else:
        bloco_limpo()
        bloco_sinais()


# ---------------------------------------------------------------- barra superior (substitui a sidebar)
def _adicionar_ticker():
    invalidos, novos = [], []
    for t in re.split(r"[,\s;]+", st.session_state.get("novo_ticker", "")):
        t = normaliza(t)
        if not t:
            continue
        if not re.fullmatch(r"[A-Z]{4}\d{1,2}", t):
            invalidos.append(t)
            continue
        if t not in st.session_state.universo:
            st.session_state.universo.append(t)
        if t not in st.session_state.sel_ativos:
            st.session_state.sel_ativos = st.session_state.sel_ativos + [t]
        novos.append(t)
    partes = []
    if novos:
        partes.append("Adicionado: " + ", ".join(novos))
    if invalidos:
        partes.append("Formato inválido (use ex.: WEGE3, TAEE11): " + ", ".join(invalidos))
    st.session_state["msg_add"] = " · ".join(partes)


def barra_superior():
    c1, c2, c3, c4, c5 = st.columns([2.2, 4.4, 1.2, 2.0, 0.8], vertical_alignment="center")
    c1.markdown(f'<div class="hero">Painel B3</div>'
                f'<div class="sub">Atualizado em {datetime.now():%d/%m/%Y %H:%M}</div>',
                unsafe_allow_html=True)
    c2.multiselect("Ativos em análise", options=st.session_state.universo, key="sel_ativos",
                   label_visibility="collapsed", placeholder="Selecione os ativos em análise")
    with c3.popover("➕ Ativo"):
        with st.form("add", clear_on_submit=True):
            st.text_input("Tickers", key="novo_ticker", placeholder="Ex.: WEGE3, TAEE11")
            st.form_submit_button("Adicionar", on_click=_adicionar_ticker)
        if st.session_state.get("msg_add"):
            st.caption(st.session_state["msg_add"])
    c4.selectbox("Fonte de dados", FONTES, key="fonte_dados", label_visibility="collapsed",
                 format_func=lambda f: f"Fonte: {f}")
    if c5.button("🔄", help="Limpar cache e atualizar dados", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    if st.session_state.fonte_dados == "Brapi" and not _token():
        st.warning("Token da Brapi não configurado (BRAPI_TOKEN). Os dados virão do Yahoo Finance quando faltarem.")


# ---------------------------------------------------------------- navegação
paginas = {
    "Fundamentalista": [
        st.Page(pagina_inicio, title="Visão geral", icon="🏠", url_path="inicio", default=True),
        st.Page(pagina_preco_justo, title="Preço justo", icon="🎯", url_path="preco-justo"),
        st.Page(pagina_valuation, title="Valuation", icon="⚖️", url_path="valuation"),
        st.Page(pagina_dividendos, title="Dividendos", icon="💰", url_path="dividendos"),
    ],
    "Avaliação": [
        st.Page(pagina_dcf, title="Fluxo de caixa descontado", icon="🧮", url_path="dcf"),
        st.Page(pagina_picking, title="Stock picking", icon="🏆", url_path="stock-picking"),
    ],
    "Técnica & Macro": [
        st.Page(pagina_tecnica, title="Análise técnica", icon="📉", url_path="tecnica"),
        st.Page(pagina_macro, title="Macroeconomia", icon="🌐", url_path="macro"),
        st.Page(pagina_micro, title="Microeconomia", icon="🏢", url_path="micro"),
    ],
}

try:
    pg = st.navigation(paginas, position="top")
    st.markdown('<style>section[data-testid="stSidebar"], '
                '[data-testid="stSidebarCollapsedControl"], '
                '[data-testid="collapsedControl"] {display:none !important;}</style>',
                unsafe_allow_html=True)
except TypeError:
    st.warning("Navegação no topo requer streamlit >= 1.46 (`pip install -U streamlit`). "
               "Usando o menu lateral como alternativa.")
    pg = st.navigation(paginas)

barra_superior()
pg.run()

st.caption("Ferramenta educacional. Graham, Bazin, DCF e a nota de Stock Picking são modelos simplificados "
           "e dependem da qualidade das fontes; não constituem recomendação de investimento.")
