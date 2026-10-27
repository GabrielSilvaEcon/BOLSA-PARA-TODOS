"""
Painel B3 - Fundamentalista + DCF + Stock Picking + Técnica + Macro & Micro + Perfis do investidor

Rodar com: streamlit run app.py
Requer streamlit >= 1.46 (navegação no topo) e os módulos tecnica.py e recursos.py ao lado.

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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
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

try:
    import recursos as rec
except ImportError:
    st.error("Arquivo **recursos.py** não encontrado. Ele precisa estar na mesma pasta do app.py no GitHub "
             "(raiz do repositório, junto com o tecnica.py).")
    st.stop()
import tecnica as tec

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except Exception:  # versões sem esse caminho: segue sem contexto nas threads
    def add_script_run_ctx(*a, **k):
        return None

    def get_script_run_ctx(*a, **k):
        return None

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
.logo {{border-radius:10px; background:#ffffff; padding:3px; object-fit:contain; flex-shrink:0;}}
p, span, label, div {{color: {TEXT};}}
</style>
""",
    unsafe_allow_html=True,
)

PLOT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": TEXT}, margin=dict(l=10, r=10, t=40, b=10))
GRID = dict(gridcolor="#30363d", zeroline=False)

FONTES = ["Yahoo Finance", "Fundamentus", "Brapi"]
PERFIS = rec.PERFIS
FINANCEIRAS = ("ITSA", "ITUB", "BBDC", "BBAS", "BPAC", "SANB", "BBSE", "CXSE", "SULA",
               "INBR", "BRSR", "BPAN", "XPBR", "PSSA", "ROXO", "ABCB")

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
    "Nota": ("Pontuação de 0 a 100 que combina os seis pilares com os pesos do seu perfil.",
             "Ordena os ativos para uma triagem inicial; não substitui a análise da empresa."),
    "Valor": ("Pilar de preço: margem de segurança, P/L, P/VP, EV/EBITDA e DCF.", "Mede se a ação está barata em relação ao que entrega."),
    "Qualidade": ("Pilar de rentabilidade: ROE e margem líquida.", "Mede se a empresa transforma capital e receita em lucro de forma eficiente."),
    "Dividendos": ("Pilar de renda: dividend yield e regularidade nos últimos 5 anos.", "Mede o retorno em proventos e a consistência do pagamento."),
    "Solidez": ("Pilar de endividamento: Dív./PL (não se aplica a financeiras).", "Mede a resistência da empresa a juros altos e crises."),
    "Tendência": ("Pilar técnico: distância do preço à média de 200 dias e cruzamento das médias de 50 e 200.",
                  "Mede se o mercado está comprando ou vendendo o ativo no momento."),
    "Atratividade": ("Faixa da nota: Alta (≥70), Moderada (50–70) ou Baixa (<50).", "Leitura rápida do ranking."),
    "Cobertura": ("Quantos dos 6 pilares tiveram dados disponíveis.", "Notas com cobertura baixa são menos confiáveis."),
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
    "Risco": ("Pilar de adequação ao risco: compara a volatilidade anualizada do último ano com a oscilação que o seu perfil tolera.",
              "Perfis conservadores penalizam ativos que oscilam muito; perfis arrojados toleram mais."),
    "Perfil": ("Perfil do investidor (Conservador, Moderado ou Arrojado).",
               "Define os pesos da nota, a margem de segurança, o yield de Bazin e as premissas do DCF. A mesma empresa pode ter notas diferentes em cada perfil."),
    "Volatilidade": ("Desvio-padrão anualizado dos retornos diários do último ano.",
                     "Mede o tamanho típico das oscilações do preço: quanto maior, maior o risco de curto prazo."),
    "Valor de mercado": ("Preço × número de ações (aproximado, a partir da fonte de dados).",
                         "Indica o tamanho da empresa; empresas maiores costumam ter mais liquidez."),
    "Anos c/ dividendos": ("Quantos dos últimos 5 anos completos a empresa pagou proventos.",
                           "Mede a regularidade dos pagamentos, importante para quem busca renda."),
    "Aderência": ("Leitura da nota frente ao mínimo do perfil: Aderente, Neutro ou Pouco aderente.",
                  "Resume se o ativo combina com o perfil escolhido; não é recomendação."),
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
# O app começa vazio: nenhuma empresa vem pré-selecionada.
st.session_state.setdefault("universo", [])
st.session_state.setdefault("sel_ativos", [])
st.session_state.setdefault("fonte_dados", "Yahoo Finance")
st.session_state.setdefault("perfil", "Moderado")
st.session_state.setdefault("tour_visto", False)
st.session_state.setdefault("tour_passo", 0)


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
        estado_vazio()
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


# ---------------------------------------------------------------- componentes de interface (logos, boas-vindas, tutorial)
def perfil_atual() -> str:
    p = st.session_state.get("perfil", "Moderado")
    return p if p in PERFIS else "Moderado"


def logo_img(tk: str, tam: int = 40) -> str:
    return f'<img class="logo" src="{rec.logo_uri(tk)}" width="{tam}" height="{tam}">'


def logos_df(df: pd.DataFrame, col: str = "Ativo") -> pd.DataFrame:
    uris = rec.logos_em_lote(list(df[col]))
    out = df.copy()
    out.insert(0, "Logo", [uris.get(rec.normalizar_ticker(t)) for t in out[col]])
    return out


CFG_LOGO = {"Logo": st.column_config.ImageColumn("Logo", width="small")}


def _adicionar(tk: str):
    tk = normaliza(tk)
    if tk not in st.session_state.universo:
        st.session_state.universo.append(tk)
    if tk not in st.session_state.sel_ativos:
        st.session_state.sel_ativos = st.session_state.sel_ativos + [tk]


def _adicionar_varios(chave: str):
    for tk in st.session_state.get(chave, []):
        _adicionar(tk)
    st.session_state[chave] = []


def estado_vazio():
    md('<div class="ctx neu"><div class="t">👋 Nenhuma empresa em análise ainda</div>'
       '<div class="x">Digite o <b>nome</b> de uma empresa (ex.: <b>Petrobras</b>) no campo '
       '<b>Ativos em análise</b>, lá em cima, ou use <b>Descobrir → Buscar empresa</b>.</div></div>')
    c1, c2, _ = st.columns([1.4, 1.2, 3])
    c1.page_link(PG_BUSCA, label="Buscar empresa pelo nome", icon="🔎")
    if c2.button("🎓 Abrir tutorial"):
        st.session_state.tour_passo = 0
        tutorial()


def boas_vindas():
    md(f"""<div class="card" style="border-top:3px solid {ACCENT};">
<div class="tk">Bem-vindo ao Painel B3 👋</div>
<div class="nm">Analise ações da bolsa brasileira com preço justo, fluxo de caixa descontado e uma nota ajustada
ao seu perfil de investidor. Nenhuma empresa vem pré-selecionada: você escolhe o que quer estudar.</div></div>""")
    c1, c2, c3 = st.columns(3)
    passos = [
        ("1 · Escolha seu perfil", "Conservador, Moderado ou Arrojado. O perfil muda os pesos da nota, a margem de "
                                   "segurança exigida e as premissas do DCF. Fica logo abaixo do título, no topo."),
        ("2 · Busque empresas", "Digite o nome (ex.: <b>Itaú</b>, <b>WEG</b>) e o painel encontra o ticker. "
                                "Cada empresa aparece com a sua logo."),
        ("3 · Compare e decida", "Veja o preço justo, o DCF, o ranking e como a mesma empresa se sai em cada perfil "
                                 "(Avaliação → Perfis e cenários)."),
    ]
    for col, (t, x) in zip((c1, c2, c3), passos):
        with col:
            md(f'<div class="card"><div class="sec" style="margin-top:0">{t}</div>'
               f'<div class="nm" style="margin-bottom:0">{x}</div></div>')
    b1, b2, b3 = st.columns(3)
    if b1.button("🎓 Fazer o tutorial guiado", type="primary", width="stretch"):
        st.session_state.tour_passo = 0
        tutorial()
    b2.page_link(PG_BUSCA, label="Buscar uma empresa pelo nome", icon="🔎")
    b3.page_link(PG_SCREENER, label="Buscar oportunidades por critérios", icon="🧪")
    st.divider()


TOUR = ["Boas-vindas", "Seu perfil", "Encontre empresas", "Preço justo", "Descubra oportunidades", "Pronto!"]


def _tour_ir(delta: int):
    st.session_state.tour_passo = max(0, min(len(TOUR) - 1, st.session_state.get("tour_passo", 0) + delta))


def _tour_perfil():
    st.session_state["perfil"] = st.session_state["tour_perfil"]


@st.dialog("🎓 Tutorial do Painel B3", width="large")
def tutorial():
    i = st.session_state.get("tour_passo", 0)
    st.progress((i + 1) / len(TOUR), text=f"Passo {i + 1} de {len(TOUR)} · {TOUR[i]}")

    if i == 0:
        st.markdown("### Bem-vindo! 👋")
        md("Este painel ajuda você a **estudar ações da B3** de forma organizada: quanto a empresa vale, "
           "se o preço está atrativo, quanto ela entrega em dividendos e se o risco combina com o seu perfil.")
        c1, c2, c3 = st.columns(3)
        c1.markdown("**🔎 Encontre**  \nBusque pelo nome e veja logo e ticker.")
        c2.markdown("**⚖️ Avalie**  \nPreço justo, DCF, múltiplos e nota.")
        c3.markdown("**🧭 Compare**  \nOs mesmos ativos em cada perfil.")
        st.caption("Ferramenta educacional: nada aqui é recomendação de compra ou venda.")

    elif i == 1:
        st.markdown("### Qual é o seu perfil de investidor?")
        st.session_state["tour_perfil"] = perfil_atual()
        st.radio("Escolha o perfil que mais combina com você", list(PERFIS), key="tour_perfil",
                 on_change=_tour_perfil, format_func=lambda x: f"{PERFIS[x]['icone']} {x}")
        pf = perfil_atual()
        P = PERFIS[pf]
        md(f"**{P['icone']} {pf}** — {P['resumo']}")
        md(f"- Margem de segurança exigida: **{P['margem_alvo']}%**\n"
           f"- Dividend yield desejado (Bazin): **{pct(P['yield_alvo'], 1)}**\n"
           f"- Taxa de desconto do DCF: **{pct(P['taxa'], 1)}**\n"
           f"- Oscilação anual tolerada: **~{P['vol_tol']:.0f}%**")
        st.caption("Você pode trocar o perfil a qualquer momento no topo da tela.")

    elif i == 2:
        st.markdown("### Encontre uma empresa pelo nome")
        st.caption("Experimente digitar *Petrobras*, *banco*, *energia* ou *WEG* e clique em **➕** para adicionar.")
        q = st.text_input("Nome da empresa", key="tour_q", placeholder="Ex.: Petrobras, WEG, Itaú...")
        if q.strip():
            res = rec.buscar_catalogo(q, 4)
            if res:
                render_resultados(res, "tour")
            else:
                st.info("Não encontrei no catálogo. Depois use **Descobrir → Buscar empresa** para procurar na internet.")
        sel = st.session_state.get("sel_ativos", [])
        if sel:
            st.success("Em análise: " + ", ".join(rec.nome_curto(t) for t in sel))

    elif i == 3:
        st.markdown("### Como ler o preço justo")
        md("O painel combina dois métodos clássicos. Exemplo **fictício**:")
        md("- **Graham**: √(22,5 × LPA × VPA) = √(22,5 × 4,00 × 30,00) = **R$ 51,96**\n"
           "- **Bazin**: dividendo médio ÷ yield desejado = R$ 2,40 ÷ 6% = **R$ 40,00**\n"
           "- **Preço justo** (média): **R$ 45,98**. Com preço atual de R$ 35,00, a **margem de segurança** "
           "é (45,98 − 35) ÷ 45,98 = **23,9%**")
        md("**Status:** 🟢 *Com margem* (acima da margem alvo do seu perfil), 🟡 *Preço justo* (margem entre 0 e o alvo) "
           "e 🔴 *Acima do justo* (preço maior que o valor estimado).")
        st.caption("Passe o mouse no ⓘ de qualquer indicador para ver o que ele significa.")

    elif i == 4:
        st.markdown("### Descubra oportunidades")
        md("- **🧪 Buscador de oportunidades** (Descobrir): marque critérios de uma boa empresa (ROE, dívida, "
           "dividendos, margem de segurança...) e veja quais do catálogo passam no filtro.\n"
           "- **🏆 Stock picking** (Avaliação): ranking com nota de 0 a 100 em seis pilares, com pesos do seu perfil.\n"
           "- **🧭 Perfis e cenários** (Avaliação): a mesma empresa avaliada nos três perfis, com cenários de DCF "
           "pessimista, base e otimista.")

    else:
        st.markdown("### Tudo pronto! ✅")
        pf = perfil_atual()
        n = len(st.session_state.get("sel_ativos", []))
        md(f"- Perfil escolhido: **{PERFIS[pf]['icone']} {pf}**\n"
           f"- Empresas em análise: **{n}**")
        md("Dicas: use **🔄** para atualizar os dados e **❓** para rever este tutorial.")

    st.write("")
    c1, c2, c3 = st.columns(3)
    c1.button("← Voltar", on_click=_tour_ir, args=(-1,), disabled=i == 0, width="stretch")
    if i < len(TOUR) - 1:
        c2.button("Próximo →", on_click=_tour_ir, args=(1,), type="primary", width="stretch")
        if c3.button("Pular tutorial", width="stretch"):
            st.rerun()
    elif c2.button("Concluir ✅", type="primary", width="stretch"):
        st.session_state.tour_passo = 0
        st.rerun()


# ---------------------------------------------------------------- página: visão geral
def pagina_inicio():
    perfil = perfil_atual()
    P = PERFIS[perfil]
    vazio = not st.session_state.get("sel_ativos")
    if vazio:
        boas_vindas()

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
    if vazio:
        return

    st.markdown("#### Resumo dos ativos")
    dados = dados_ativos()
    if not dados:
        return
    linhas = []
    for d in dados.values():
        r = analisar(d, "Média", P["yield_alvo"], P["margem_alvo"])
        m = multiplos(d)
        linhas.append({"Ativo": d["ticker"], "Empresa": rec.nome_curto(d["ticker"]), "Preço": d["preco"],
                       "Preço justo": r["justo"], "Margem (%)": r["margem"], "P/L": m["pl"], "P/VP": m["pvp"],
                       "DY 12m (%)": m["dy"], "Status": r["status"]})
    df = logos_df(pd.DataFrame(linhas))
    st.dataframe(estilizar(df, {"Preço": brl, "Preço justo": brl, "Margem (%)": pct, "P/L": num,
                                "P/VP": num, "DY 12m (%)": pct}),
                 width="stretch", hide_index=True, column_config={**cfg_ajuda(df), **CFG_LOGO})
    st.caption(f"Preço justo = média de Graham e Bazin com os parâmetros do perfil {perfil} "
               f"(yield {pct(P['yield_alvo'], 1)}, margem alvo {P['margem_alvo']}%). "
               "Ajuste em Fundamentalista → Preço justo.")


# ---------------------------------------------------------------- páginas: fundamentalista
def pagina_preco_justo():
    dados = dados_ativos()
    if not dados:
        return
    perfil = perfil_atual()
    P = PERFIS[perfil]
    c1, c2, c3 = st.columns(3)
    metodo = c1.selectbox("Método", ["Média (Graham + Bazin)", "Graham", "Bazin"])
    yield_alvo = c2.slider("Dividend yield desejado (Bazin)", 4.0, 12.0, float(P["yield_alvo"]), 0.5,
                           format="%.1f%%", key=f"yield_{perfil}")
    margem_alvo = c3.slider("Margem de segurança alvo", 5, 50, int(P["margem_alvo"]), 5,
                            format="%d%%", key=f"margem_{perfil}")
    st.caption(f"Valores iniciais do perfil {P['icone']} {perfil}; ajuste à vontade.")
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
<div style="display:flex; align-items:center; gap:12px; margin-bottom:10px;">
{logo_img(r['ticker'])}
<div><div class="tk">{html.escape(r['ticker'])}</div>
<div class="nm" style="margin-bottom:0;">{html.escape(str(r['nome']))}</div></div></div>
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
    tk = st.selectbox("Ativo", list(dados), key="dcf_ativo", format_func=rec.rotulo)
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
    perfil = perfil_atual()
    P = PERFIS[perfil]
    st.caption(f"Premissas iniciais do perfil {P['icone']} {perfil} (taxa, crescimento e perpetuidade); ajuste à vontade.")
    p1, p2, p3 = st.columns(3)
    modo = p1.radio("FCL base", ["Média dos últimos N anos", "Último ano"], horizontal=False)
    n_anos = p1.slider("Anos na média", 2, 5, 3) if modo.startswith("Média") else 1
    horizonte = p2.slider("Horizonte explícito (anos)", 5, 10, 5)
    taxa = p2.slider("Taxa de desconto", 8.0, 25.0, float(P["taxa"]), 0.5, format="%.1f%%",
                     key=f"dcf_taxa_{perfil}") / 100
    g = p3.slider("Crescimento do FCL no período", -5.0, 20.0, float(P["g"]), 0.5, format="%.1f%%",
                  key=f"dcf_g_{perfil}") / 100
    gp = p3.slider("Crescimento na perpetuidade", 0.0, 6.0, float(P["gp"]), 0.5, format="%.1f%%",
                   key=f"dcf_gp_{perfil}") / 100
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


# ---------------------------------------------------------------- página: stock picking (com perfil do investidor)
PILARES = ["Valor", "Qualidade", "Dividendos", "Solidez", "Tendência", "Risco"]
COR_PERFIL = {"Conservador": "#33b3ae", "Moderado": ACCENT, "Arrojado": "#f0883e"}


def sinais_tecnicos(ticker: str) -> dict:
    """Distância à média de 200 dias, cruzamento 50×200 e volatilidade anualizada (1 ano)."""
    out = {"dist200": None, "cruz": None, "vol": None}
    df, _ = historico(ticker, "1y", "1d")
    if df.empty:
        return out
    c = df["Close"].dropna()
    if len(c) >= 60:
        out["vol"] = float(c.pct_change().dropna().std() * sqrt(252) * 100)
    if len(c) >= 200:
        mm50, mm200 = c.rolling(50).mean().iloc[-1], c.rolling(200).mean().iloc[-1]
        if pd.notna(mm50) and pd.notna(mm200) and mm200 > 0:
            out["dist200"] = float((c.iloc[-1] / mm200 - 1) * 100)
            out["cruz"] = bool(mm50 > mm200)
    return out


def pontuar(d: dict, r: dict, margem_dcf, tecn: dict, perfil: str) -> dict:
    """Nota 0-100 de cada pilar. O perfil entra aqui no pilar Risco (tolerância à volatilidade)."""
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
    tend = None
    if tecn and tecn.get("dist200") is not None:
        tend = media([escala(tecn["dist200"], -10, 15), 100.0 if tecn["cruz"] else 0.0])
    tol = PERFIS[perfil]["vol_tol"]
    risco = escala(tecn.get("vol"), tol * 1.6, tol * 0.6) if tecn else None
    return {"Valor": valor, "Qualidade": qualidade, "Dividendos": dividendos,
            "Solidez": solidez, "Tendência": tend, "Risco": risco}


def avaliar(d: dict, perfil: str, caixa: pd.DataFrame, tecn: dict, pesos: dict | None = None,
            usar_tend: bool = True) -> dict:
    """Avalia um ativo sob as regras de um perfil: preço justo, DCF, pilares e nota final."""
    P = PERFIS[perfil]
    r = analisar(d, "Média", P["yield_alvo"], P["margem_alvo"])
    dcf_val = pot = margem_dcf = None
    if not eh_financeiro(d["ticker"]):
        res, _ = dcf_modelo(fcl_base(caixa, "Média", 3), d.get("acoes"),
                            P["taxa"] / 100, P["g"] / 100, P["gp"] / 100, 5, 0.0)
        if res and d.get("preco"):
            dcf_val = res["valor"]
            margem_dcf = (dcf_val - d["preco"]) / dcf_val * 100
            pot = (dcf_val / d["preco"] - 1) * 100
    pil = pontuar(d, r, margem_dcf, tecn, perfil)
    pesos = dict(pesos or P["pesos"])
    if not usar_tend:
        pesos["Tendência"] = 0
    disp = {p: v for p, v in pil.items() if v is not None and pesos.get(p, 0) > 0}
    soma = sum(pesos[p] for p in disp)
    nota = sum(pil[p] * pesos[p] for p in disp) / soma if soma > 0 else None
    return {"r": r, "pil": pil, "nota": nota, "dcf": dcf_val, "pot": pot, "margem_dcf": margem_dcf}


def veredito(nota, perfil: str) -> str:
    if nota is None or pd.isna(nota):
        return "Sem dados"
    mn = PERFIS[perfil]["nota_min"]
    return "Aderente" if nota >= mn else ("Neutro" if nota >= mn - 10 else "Pouco aderente")


def pagina_picking():
    dados = dados_ativos()
    if not dados:
        return
    perfil = perfil_atual()
    P = PERFIS[perfil]
    st.caption(f"Ranking quantitativo no perfil **{P['icone']} {perfil}**. Troque o perfil no topo da página, "
               "ou veja os três lado a lado em Avaliação → Perfis e cenários.")

    with st.expander("Pesos e critérios", expanded=False):
        cols = st.columns(len(PILARES))
        pesos = {p: cols[i].slider(p, 0, 100, int(P["pesos"][p]), 5, key=f"w_{perfil}_{p}", help=ajuda_txt(p))
                 for i, p in enumerate(PILARES)}
        usar_tend = st.checkbox("Incluir tendência (preço vs. médias de 50 e 200 dias)", value=True)
        st.markdown(
            "- **Valor**: margem de segurança (Graham/Bazin), P/L, P/VP, EV/EBITDA e margem do DCF\n"
            "- **Qualidade**: ROE e margem líquida\n"
            "- **Dividendos**: dividend yield 12m e regularidade nos últimos 5 anos\n"
            "- **Solidez**: Dív./PL (não se aplica a financeiras)\n"
            "- **Tendência**: distância da média de 200 dias e cruzamento 50×200\n"
            "- **Risco**: volatilidade do último ano frente à oscilação que o perfil tolera\n\n"
            "O perfil define os pesos iniciais, a margem de segurança, o yield e as premissas do DCF usados no "
            "Valor. Cada indicador vira nota de 0 a 100 entre um piso e um teto fixos; pilares sem dados "
            "são ignorados e os pesos são reponderados.")

    linhas = []
    with st.spinner("Calculando notas..."):
        for tk, d in dados.items():
            cx = pd.DataFrame() if eh_financeiro(tk) else buscar_caixa(tk)[0]
            a = avaliar(d, perfil, cx, sinais_tecnicos(tk), pesos, usar_tend)
            linhas.append({"Ativo": tk, "Nota": a["nota"], **a["pil"],
                           "Cobertura": f"{sum(v is not None for v in a['pil'].values())}/{len(PILARES)}",
                           "Preço": d.get("preco"), "Preço justo": a["r"]["justo"],
                           "Margem (%)": a["r"]["margem"], "Status": a["r"]["status"]})

    df = pd.DataFrame(linhas).sort_values("Nota", ascending=False, na_position="last").reset_index(drop=True)
    df.insert(0, "#", range(1, len(df) + 1))

    def rotulo(n):
        return "—" if n is None or pd.isna(n) else ("Alta" if n >= 70 else "Moderada" if n >= 50 else "Baixa")
    df.insert(3, "Atratividade", df["Nota"].map(rotulo))
    df = logos_df(df)
    df.insert(1, "Logo", df.pop("Logo"))

    pc = {p: st.column_config.ProgressColumn(p, help=ajuda_txt(p), min_value=0, max_value=100, format="%.0f")
          for p in ["Nota"] + PILARES}
    pc.update({"Preço": st.column_config.NumberColumn("Preço", help=ajuda_txt("Preço"), format="R$ %.2f"),
               "Preço justo": st.column_config.NumberColumn("Preço justo", help=ajuda_txt("Preço justo"), format="R$ %.2f"),
               "Margem (%)": st.column_config.NumberColumn("Margem (%)", help=ajuda_txt("Margem (%)"), format="%.1f%%"),
               "Atratividade": st.column_config.Column(help=ajuda_txt("Atratividade")),
               "Cobertura": st.column_config.Column(help=ajuda_txt("Cobertura")),
               "Status": st.column_config.Column(help=ajuda_txt("Status"))})
    pc.update(CFG_LOGO)
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
    sel = st.multiselect("Ativos no radar", list(df["Ativo"]), default=list(df["Ativo"])[:3], key="radar_sel",
                         format_func=rec.rotulo)
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


# ---------------------------------------------------------------- página: perfis e cenários
def pagina_perfis():
    dados = dados_ativos()
    if not dados:
        return
    st.caption("Os mesmos ativos avaliados com as regras de cada perfil: pesos da nota, margem de segurança, "
               "yield de Bazin, premissas do DCF e tolerância à volatilidade.")
    pre = {}
    with st.spinner("Calculando os cenários dos três perfis..."):
        for tk in dados:
            cx = pd.DataFrame() if eh_financeiro(tk) else buscar_caixa(tk)[0]
            pre[tk] = (cx, sinais_tecnicos(tk))
        aval = {(tk, pf): avaliar(d, pf, *pre[tk]) for tk, d in dados.items() for pf in PERFIS}

    t1, t2, t3 = st.tabs(["Comparativo", "Cenários de DCF", "Premissas dos perfis"])

    with t1:
        resumo = []
        for tk in dados:
            linha = {"Ativo": tk}
            folga = {}
            for pf in PERFIS:
                n = aval[(tk, pf)]["nota"]
                linha[pf] = n
                if n is not None:
                    folga[pf] = n - PERFIS[pf]["nota_min"]
            linha["Mais aderente a"] = max(folga, key=folga.get) if folga else "—"
            resumo.append(linha)
        dfr = logos_df(pd.DataFrame(resumo))
        cfg = {pf: st.column_config.ProgressColumn(f"{PERFIS[pf]['icone']} {pf}", min_value=0, max_value=100,
                                                   format="%.0f", help=ajuda_txt("Nota")) for pf in PERFIS}
        cfg.update(CFG_LOGO)
        cfg["Mais aderente a"] = st.column_config.Column(help=ajuda_txt("Aderência"))
        st.dataframe(dfr, width="stretch", hide_index=True, column_config=cfg)
        st.caption("“Mais aderente a” compara a nota com o mínimo de cada perfil (Conservador 65, Moderado 60, "
                   "Arrojado 55), porque cada perfil é mais ou menos exigente.")

        g1, g2 = st.columns(2)
        tks = list(dados)
        with g1:
            fig = go.Figure()
            for pf in PERFIS:
                fig.add_bar(x=tks, y=[aval[(t, pf)]["nota"] for t in tks], name=pf, marker_color=COR_PERFIL[pf])
            fig.update_layout(barmode="group", title="Nota por perfil", height=280,
                              legend=dict(orientation="h", y=1.18, x=0), **PLOT)
            fig.update_yaxes(range=[0, 100], **GRID)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        with g2:
            fig = go.Figure()
            for pf in PERFIS:
                fig.add_bar(x=tks, y=[aval[(t, pf)]["pot"] for t in tks], name=pf, marker_color=COR_PERFIL[pf])
            fig.add_hline(y=0, line_color=MUTED)
            fig.update_layout(barmode="group", title="Potencial do DCF por perfil (%)", height=280,
                              legend=dict(orientation="h", y=1.18, x=0), **PLOT)
            fig.update_yaxes(**GRID)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        if any(eh_financeiro(t) for t in dados):
            st.caption("Bancos e seguradoras ficam sem DCF (modelo não se aplica); a nota usa os demais pilares.")

        with st.expander("Detalhes por ativo e perfil (preço justo, margem, DCF e aderência)"):
            det = []
            for tk, d in dados.items():
                for pf in PERFIS:
                    a = aval[(tk, pf)]
                    det.append({"Ativo": tk, "Perfil": f"{PERFIS[pf]['icone']} {pf}", "Preço": d.get("preco"),
                                "Preço justo": a["r"]["justo"], "Margem (%)": a["r"]["margem"],
                                "Valor DCF": a["dcf"], "Potencial (%)": a["pot"], "Nota": a["nota"],
                                "Aderência": veredito(a["nota"], pf)})
            dfd = pd.DataFrame(det)
            st.dataframe(estilizar(dfd, {"Preço": brl, "Preço justo": brl, "Margem (%)": pct, "Valor DCF": brl,
                                         "Potencial (%)": pct, "Nota": lambda v: num(v, 0)}),
                         width="stretch", hide_index=True, column_config=cfg_ajuda(dfd))

    with t2:
        nao_fin = [t for t in dados if not eh_financeiro(t)]
        if not nao_fin:
            st.info("Todos os ativos selecionados são financeiros: o DCF tradicional não se aplica.")
        else:
            tk = st.selectbox("Ativo", nao_fin, format_func=rec.rotulo, key="perf_dcf_ativo")
            d = dados[tk]
            base = fcl_base(pre[tk][0], "Média", 3)
            variacoes = {"Pessimista": (2.0, -3.0, -1.0), "Base": (0.0, 0.0, 0.0), "Otimista": (-1.0, 3.0, 0.5)}
            linhas = []
            for pf, Pp in PERFIS.items():
                for cen, (dt, dg, dgp) in variacoes.items():
                    r_, e_ = dcf_modelo(base, d.get("acoes"), (Pp["taxa"] + dt) / 100, (Pp["g"] + dg) / 100,
                                        max(0.0, Pp["gp"] + dgp) / 100, 5, 0.0)
                    linhas.append({"Perfil": pf, "Cenário": cen, "Taxa (%)": Pp["taxa"] + dt,
                                   "Cresc. FCL (%)": Pp["g"] + dg, "Perpetuidade (%)": max(0.0, Pp["gp"] + dgp),
                                   "Valor DCF": r_["valor"] if r_ else None,
                                   "Potencial (%)": (r_["valor"] / d["preco"] - 1) * 100 if r_ and d.get("preco") else None})
            dfc = pd.DataFrame(linhas)
            if dfc["Valor DCF"].notna().sum() == 0:
                st.warning("Sem fluxo de caixa livre positivo para este ativo: DCF não calculado.")
            else:
                fig = go.Figure()
                for pf in PERFIS:
                    sub = dfc[dfc["Perfil"] == pf]
                    fig.add_bar(x=sub["Cenário"], y=sub["Valor DCF"], name=pf, marker_color=COR_PERFIL[pf])
                if d.get("preco"):
                    fig.add_hline(y=d["preco"], line_dash="dot", line_color=MUTED,
                                  annotation_text=f"preço atual {brl(d['preco'])}", annotation_font_color=MUTED)
                fig.update_layout(barmode="group", title=f"Valor justo por DCF · {rec.nome_curto(tk)}", height=300,
                                  legend=dict(orientation="h", y=1.18, x=0), **PLOT)
                fig.update_yaxes(**GRID)
                st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
            st.dataframe(estilizar(dfc, {"Taxa (%)": pct, "Cresc. FCL (%)": pct, "Perpetuidade (%)": pct,
                                         "Valor DCF": brl, "Potencial (%)": pct}),
                         width="stretch", hide_index=True)
            st.caption("Cada perfil parte das suas premissas-base. Pessimista: taxa +2 p.p., crescimento −3 p.p., "
                       "perpetuidade −1 p.p. Otimista: taxa −1 p.p., crescimento +3 p.p., perpetuidade +0,5 p.p.")

    with t3:
        linhas = []
        for pf, Pp in PERFIS.items():
            linhas.append({"Perfil": f"{Pp['icone']} {pf}", "Yield Bazin (%)": Pp["yield_alvo"],
                           "Margem alvo (%)": Pp["margem_alvo"], "Taxa DCF (%)": Pp["taxa"],
                           "Cresc. FCL (%)": Pp["g"], "Perpetuidade (%)": Pp["gp"],
                           "Volatilidade tolerada (%)": Pp["vol_tol"], "Nota mínima": Pp["nota_min"],
                           **{f"Peso {p}": Pp["pesos"][p] for p in PILARES}})
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
        for pf, Pp in PERFIS.items():
            st.markdown(f"**{Pp['icone']} {pf}** — {Pp['resumo']}")
        st.caption("Premissas educacionais e simplificadas. Um perfil de investidor de verdade é definido por "
                   "questionário de suitability com a sua instituição financeira.")


# ---------------------------------------------------------------- páginas: descobrir (busca por nome e buscador de oportunidades)
def render_resultados(res: list, pref: str = "r"):
    """Cartões com logo, nome, setor e botões ➕ por ticker."""
    if not res:
        return
    logos = rec.logos_em_lote([r["ticker"] for r in res])
    for j, r in enumerate(res):
        with st.container(border=True):
            a, b, c = st.columns([0.8, 3.6, 2.6], vertical_alignment="center")
            a.markdown(f'<img class="logo" src="{logos.get(rec.normalizar_ticker(r["ticker"]))}" '
                       f'width="44" height="44">', unsafe_allow_html=True)
            b.markdown(f"**{r['nome']}**  \n<span style='color:{MUTED};font-size:.8rem'>{html.escape(r['setor'])}</span>",
                       unsafe_allow_html=True)
            with c:
                cols = st.columns(len(r["tickers"]))
                for k, tk in enumerate(r["tickers"]):
                    ja = tk in st.session_state.get("sel_ativos", [])
                    cols[k].button(f"✔ {tk}" if ja else f"➕ {tk}", key=f"{pref}_{j}_{tk}",
                                   on_click=_adicionar, args=(tk,), disabled=ja, width="stretch")


def pagina_busca():
    st.markdown("#### Encontre uma empresa pelo nome")
    q = st.text_input("Nome da empresa, ticker ou setor", key="busca_q",
                      placeholder="Ex.: Petrobras, WEG, banco, energia, saneamento...")
    c1, c2 = st.columns([1, 1.4], vertical_alignment="center")
    setor = c1.selectbox("Ou explore por setor", ["—"] + rec.SETORES, key="busca_setor")
    online = c2.checkbox("Incluir resultados da internet (Yahoo Finance) para empresas fora do catálogo",
                         key="busca_online")

    if q.strip():
        res = rec.buscar_catalogo(q, 12)
        st.markdown(f"##### Resultados para “{q.strip()}”")
        if online:
            res = res + rec.buscar_online(q.strip())
        if not res:
            st.info("Não encontrei no catálogo. Marque a opção da internet acima ou digite o ticker "
                    "(ex.: ABCD3) no botão **➕ Ativo** da barra superior.")
    elif setor != "—":
        res = rec.por_setor(setor)
        st.markdown(f"##### Empresas do setor: {setor}")
    else:
        res = rec.populares()
        st.markdown("##### Mais conhecidas")
        st.caption("Digite um nome acima para buscar entre as empresas do catálogo.")
    with st.spinner("Carregando logos..."):
        render_resultados(res, "busca")
    st.caption(f"Catálogo com {len(rec.CATALOGO)} empresas e {len(rec.TODOS_TICKERS)} tickers. "
               "Empresas fora do catálogo podem ser adicionadas pelo ticker no botão ➕ Ativo.")


# --- buscador de oportunidades (screener)
def _aplicar_preset(nome: str):
    cfg = rec.PRESETS[nome]
    for k in rec.CRITERIOS:
        st.session_state[f"on_{k}"] = k in cfg
        if k in cfg:
            st.session_state[f"crit_{k}"] = cfg[k]


def coletar_universo(tickers: list) -> dict:
    """Busca os dados (Yahoo) de várias empresas em paralelo."""
    ctx = get_script_run_ctx()

    def tarefa(tk):
        try:
            if ctx is not None:
                add_script_run_ctx(threading.current_thread(), ctx)
            d = dict(buscar_yahoo(tk))
            d["alertas"] = list(d.get("alertas", []))
            return tk, d
        except Exception:
            return tk, None

    out = {}
    prog = st.progress(0.0, text="Coletando dados...")
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(tarefa, tk) for tk in tickers]
        for n, f in enumerate(as_completed(futs), start=1):
            tk, d = f.result()
            if d and d.get("preco"):
                out[tk] = d
            prog.progress(n / len(futs), text=f"Coletando dados... {n}/{len(futs)}")
    prog.empty()
    for d in out.values():
        converter_moeda(d)
        validar(d)
    return out


def metricas_empresa(d: dict, P: dict) -> dict:
    r = analisar(d, "Média", P["yield_alvo"], P["margem_alvo"])
    m = multiplos(d)
    da = d.get("div_ano")
    anos = None
    if da is not None and len(da) > 0:
        compl = da[da.index < datetime.now().year].tail(5)
        anos = int((compl > 0).sum()) if len(compl) else None
    preco, acoes = d.get("preco"), d.get("acoes")
    e = rec.info(d["ticker"])
    return {"ticker": d["ticker"], "empresa": e["nome"] if e else (d.get("nome") or d["ticker"]),
            "setor": e["setor"] if e else (d.get("setor") or "—"), "preco": preco,
            "pl": m["pl"], "pvp": m["pvp"], "ev_ebitda": d.get("ev_ebitda"), "dy": m["dy"],
            "anos_div": anos, "roe": m["roe"], "margem_liq": m["margem"], "div_pl": d.get("div_pl"),
            "margem_seg": r["margem"], "mcap": preco * acoes / 1e9 if preco and acoes else None,
            "fin": eh_financeiro(d["ticker"])}


def _passa(k: str, v, lim, fin: bool) -> bool:
    if k in ("div_pl", "ev_ebitda") and fin:
        return True  # não se aplica a bancos e seguradoras
    if v is None or pd.isna(v):
        return False
    if k in ("pl", "pvp", "ev_ebitda"):
        return 0 < v <= lim
    if k == "div_pl":
        return 0 <= v <= lim
    return v >= lim if rec.CRITERIOS[k]["tipo"] == "min" else v <= lim


def pagina_screener():
    perfil = perfil_atual()
    P = PERFIS[perfil]
    padrao = rec.PRESETS[rec.PRESET_PADRAO]
    for k, c in rec.CRITERIOS.items():
        st.session_state.setdefault(f"on_{k}", k in padrao)
        st.session_state.setdefault(f"crit_{k}", padrao.get(k, c["padrao"]))

    st.markdown("#### 1 · Onde procurar")
    esc = st.radio("Universo", ["Todo o catálogo", "Setores específicos", "Meus ativos selecionados"],
                   horizontal=True, label_visibility="collapsed", key="scr_univ")
    if esc == "Todo o catálogo":
        tickers = list(rec.PRINCIPAIS)
    elif esc == "Setores específicos":
        setores = st.multiselect("Setores", rec.SETORES, key="scr_setores", placeholder="Escolha um ou mais setores")
        tickers = [e["ticker"] for e in rec.CATALOGO if e["setor"] in setores]
    else:
        tickers = list(st.session_state.get("sel_ativos", []))
    cA, cB = st.columns([1.3, 4], vertical_alignment="center")
    if cA.button("📥 Coletar dados", type="primary", disabled=not tickers, width="stretch"):
        st.session_state.scr_base = coletar_universo(tickers)
        st.session_state.scr_quando = datetime.now()
    cB.caption(f"{len(tickers)} empresa(s). A coleta leva cerca de {max(5, len(tickers) // 4)} segundos "
               "(dados do Yahoo Finance) e fica guardada enquanto você ajusta os critérios.")

    base = st.session_state.get("scr_base")
    if not base:
        st.info("Clique em **Coletar dados** para começar. Depois, ajuste os critérios sem precisar coletar de novo.")
        return
    st.caption(f"Base com {len(base)} empresas coletadas às {st.session_state.scr_quando:%H:%M}.")

    st.markdown("#### 2 · Critérios de uma boa empresa")
    cols = st.columns(len(rec.PRESETS))
    for col, nome in zip(cols, rec.PRESETS):
        col.button(nome, key=f"preset_{nome}", on_click=_aplicar_preset, args=(nome,), width="stretch")
    with st.expander("Ajustar critérios", expanded=True):
        gcols = st.columns(3)
        for n, (k, c) in enumerate(rec.CRITERIOS.items()):
            with gcols[n % 3]:
                st.checkbox(c["rotulo"], key=f"on_{k}",
                            help=ajuda_txt(c["glos"]) if c["glos"] in GLOSSARIO else None)
                st.slider(c["rotulo"], c["min"], c["max"], step=c["passo"], key=f"crit_{k}",
                          disabled=not st.session_state[f"on_{k}"], label_visibility="collapsed")
        st.caption("Critérios de endividamento (Dív./PL e EV/EBITDA) não se aplicam a bancos e seguradoras e "
                   "são ignorados para elas. Dado ausente conta como critério não atendido.")
    ativos = [k for k in rec.CRITERIOS if st.session_state[f"on_{k}"]]
    if not ativos:
        st.warning("Marque ao menos um critério.")
        return
    min_ok = len(ativos) if len(ativos) == 1 else st.slider(
        "Mínimo de critérios atendidos", 1, len(ativos), len(ativos),
        help="Reduza para ver também as empresas que ficaram perto de passar.")

    linhas = []
    for d in base.values():
        m = metricas_empresa(d, P)
        ok, falhas = 0, []
        for k in ativos:
            if _passa(k, m.get(k), st.session_state[f"crit_{k}"], m["fin"]):
                ok += 1
            else:
                falhas.append(rec.CRITERIOS[k]["rotulo"].split(" (")[0])
        linhas.append({"Ativo": m["ticker"], "Empresa": m["empresa"], "Setor": m["setor"], "Preço": m["preco"],
                       "P/L": m["pl"], "P/VP": m["pvp"], "EV/EBITDA": m["ev_ebitda"], "DY 12m (%)": m["dy"],
                       "ROE (%)": m["roe"], "Margem líq. (%)": m["margem_liq"], "Dív./PL (%)": m["div_pl"],
                       "Margem seg. (%)": m["margem_seg"], "Anos c/ dividendos": m["anos_div"],
                       "Valor de mercado": m["mcap"], "Critérios": f"{ok}/{len(ativos)}",
                       "Falhou em": ", ".join(falhas) or "—", "_ok": ok})

    aprovadas = [r for r in linhas if r["_ok"] == len(ativos)]
    res = [r for r in linhas if r["_ok"] >= min_ok]
    res.sort(key=lambda r: (-r["_ok"], -(r["Margem seg. (%)"] if pd.notna(r["Margem seg. (%)"]) else -999)))

    st.markdown("#### 3 · Resultado")
    k1, k2, k3 = st.columns(3)
    with k1:
        kpi("Empresas analisadas", str(len(linhas)))
    with k2:
        kpi("Passaram em todos", str(len(aprovadas)), cor=GOOD if aprovadas else MUTED)
    with k3:
        kpi("Exibidas (filtro atual)", str(len(res)))
    if not res:
        st.warning("Nenhuma empresa atende aos critérios. Afrouxe algum limite ou reduza o mínimo de critérios.")
        return

    mostrar = res[:60]
    df = pd.DataFrame(mostrar).drop(columns=["_ok"])
    if st.checkbox(f"Calcular a nota do perfil {perfil} para as exibidas (mais lento, até 25 empresas)", key="scr_nota"):
        notas = {}
        with st.spinner("Calculando notas..."):
            for r in mostrar[:25]:
                tk, d = r["Ativo"], base[r["Ativo"]]
                cx = pd.DataFrame() if eh_financeiro(tk) else buscar_caixa(tk)[0]
                notas[tk] = avaliar(d, perfil, cx, sinais_tecnicos(tk))["nota"]
        df["Nota do perfil"] = df["Ativo"].map(notas)
    df = logos_df(df)
    fmts = {c: num for c in ("P/L", "P/VP", "EV/EBITDA")}
    fmts.update({"Preço": brl, "DY 12m (%)": pct, "ROE (%)": pct, "Margem líq. (%)": pct, "Dív./PL (%)": pct,
                 "Margem seg. (%)": pct,
                 "Anos c/ dividendos": lambda v: f"{int(v)}/5",
                 "Valor de mercado": lambda v: _sep(f"R$ {v:,.1f} bi")})
    cfg = {**cfg_ajuda(df), **CFG_LOGO}
    if "Nota do perfil" in df:
        cfg["Nota do perfil"] = st.column_config.ProgressColumn("Nota do perfil", min_value=0, max_value=100,
                                                                format="%.0f", help=ajuda_txt("Nota"))
    st.dataframe(estilizar(df, fmts), width="stretch", hide_index=True, column_config=cfg)
    if len(res) > len(mostrar):
        st.caption(f"Mostrando as {len(mostrar)} primeiras de {len(res)}. Aperte os critérios para refinar.")

    st.multiselect("Adicionar à análise", [r["Ativo"] for r in mostrar], key="scr_pick",
                   format_func=rec.rotulo, placeholder="Escolha as empresas que quer estudar a fundo")
    st.button("➕ Adicionar selecionadas", on_click=_adicionar_varios, args=("scr_pick",))
    st.caption("Filtro quantitativo para triagem inicial, com dados do Yahoo Finance. Não é recomendação de investimento; "
               "confira balanços e fatos relevantes antes de qualquer decisão.")


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
        delta = _sep(f"{s.iloc[-1] - s.iloc[-2]:+.2f}"