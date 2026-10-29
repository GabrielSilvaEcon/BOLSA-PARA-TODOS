"""
Bolsa para Todos - Preço justo, DCF, múltiplos, dividendos, técnica, ranking por perfil, economia e carteira.

Rodar com: streamlit run app.py
Requer streamlit >= 1.46 e os módulos tecnica.py, recursos.py, dados.py, glossario.py,
leitura_macro.py, carteira.py e assistente.py ao lado.

Estrutura do menu (pensada como uma jornada para quem está começando):
  Início     -> escolher uma empresa e ver o resumo
  Analisar separadamente -> preço justo, múltiplos, saúde financeira, dividendos, DCF e gráfico, um por vez
  Ranking    -> notas por empresa, por perfil de investidor, das selecionadas ou de setores
  Economia   -> Selic, inflação, dólar, atividade
  Carteira   -> acompanhar a carteira
  Ajuda      -> termos, tutorial, fontes de dados

Convenções internas dos dados (todas as fontes são normalizadas para isso):
  preco, lpa, vpa, div_12m, div_medio, divida_liq ..... R$ (já convertidos se o balanço for em USD)
  roe, margem_liq ..................................... fração (0.15 = 15%)
  div_pl .............................................. percentual (150 = 150%)
  acoes ............................................... unidades
"""

import base64
import colorsys
import html
import json
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime
from math import sqrt

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import streamlit.components.v1 as components

try:
    import dados as _dados  # noqa: F401  (confere se o arquivo existe)
    import glossario as _glossario  # noqa: F401
    import recursos as rec
except ImportError as e:
    st.error(f"Não consegui importar **{e.name}**. Se for um arquivo do projeto (recursos.py, dados.py, "
             "glossario.py, tecnica.py), ele precisa estar na raiz do repositório, ao lado do app.py. "
             "Se for um pacote, inclua no requirements.txt.")
    st.stop()
import tecnica as tec
import leitura_macro as lm

import assistente
import carteira

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except Exception:  # versões sem esse caminho: segue sem contexto nas threads
    def add_script_run_ctx(*a, **k):
        return None

    def get_script_run_ctx(*a, **k):
        return None

st.set_page_config(page_title="Bolsa para Todos", page_icon="🌱", layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- paleta neutra (confortável para os olhos)
BG, SURFACE, BORDER = "#EEF0F3", "#F9FAFB", "#D5DAE0"
TEXT, MUTED = "#1F2933", "#5B6675"
ACCENT = "#3B6BC4"  # destaque neutro dos gráficos
BRAND, BRAND_DARK, SUN = "#1F7A55", "#17604A", "#C9A227"
GOOD, FAIR, BAD = "#2E7D4F", "#A8650B", "#B83A3A"
SOFT = "#E3E8EE"    # fundo de realce suave (hover, menu ativo)


def svg_uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


LOGO_SVG = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">
<rect width="48" height="48" rx="14" fill="#1F7A55"/>
<rect x="10" y="26" width="7" height="12" rx="2" fill="#C8E6D5"/>
<rect x="21" y="19" width="7" height="19" rx="2" fill="#8FCFAE"/>
<rect x="32" y="11" width="7" height="27" rx="2" fill="#E9C85A"/></svg>"""

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&display=swap');
.stApp {{background:{BG};}}
.stApp, .stApp p, .stApp label, .stApp li, .stApp h1, .stApp h2, .stApp h3, .stApp h4,
.stApp button, .stApp input, .stApp textarea {{font-family:'Nunito','Segoe UI',sans-serif;}}
header[data-testid="stHeader"] {{background:{SURFACE}; border-bottom:2px solid {BORDER};}}
.block-container {{padding-top:4.6rem; padding-bottom:7rem; max-width:1280px;}}
p, span, label, div {{color:{TEXT};}}
h4 {{font-weight:800; color:{TEXT};}}
/* marca e cabeçalho de página */
.brand {{display:flex; align-items:center; gap:8px;}}
.hero {{font-size:1.1rem; font-weight:800; color:{BRAND}; line-height:1.05; white-space:nowrap;}}
.pghead {{margin:.2rem 0 .8rem;}}
.pgt {{font-size:1.55rem; font-weight:800; color:{TEXT}; line-height:1.15;}}
.pgsub {{font-size:.92rem; color:{MUTED}; margin-top:2px;}}
.sec {{font-size:1.05rem; font-weight:800; color:{TEXT}; margin:.6rem 0 .3rem;}}
/* cartões */
.card {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:16px; padding:14px 16px; margin-bottom:10px;}}
.tk {{font-size:1.2rem; font-weight:800; color:{TEXT}; letter-spacing:.4px;}}
.nm {{font-size:.8rem; color:{MUTED}; margin-bottom:8px;}}
.aviso {{font-size:.74rem; color:{FAIR}; margin-top:6px;}}
.badge {{display:inline-block; padding:3px 11px; border-radius:999px; font-size:.72rem; font-weight:800; display:block; width:fit-content; margin:0 0 8px auto;}}
.good {{background:rgba(46,125,79,.14); color:{GOOD};}}
.fair {{background:rgba(168,101,11,.14); color:{FAIR};}}
.bad {{background:rgba(184,58,58,.14); color:{BAD};}}
.na {{background:rgba(91,102,117,.16); color:{MUTED};}}
.lbl {{font-size:.68rem; color:{MUTED}; text-transform:uppercase; letter-spacing:.6px; font-weight:700;}}
.val {{font-size:1.1rem; font-weight:800; color:{TEXT};}}
.kpi {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px; padding:11px 14px;}}
.kpi .v {{font-size:1.25rem; font-weight:800;}}
.kpi .d {{font-size:.72rem; color:{MUTED}; margin-top:2px;}}
.ctx {{background:{SURFACE}; border:1px solid {BORDER}; border-left-width:5px; border-radius:12px;
padding:11px 14px; margin-bottom:10px;}}
.ctx.pos {{border-left-color:{GOOD};}} .ctx.neg {{border-left-color:{BAD};}} .ctx.neu {{border-left-color:{SUN};}}
.ctx .t {{font-weight:800; font-size:.95rem;}}
.ctx .x {{font-size:.8rem; color:{MUTED}; margin-top:4px; line-height:1.5;}}
.logo {{border-radius:10px; background:#ffffff; padding:3px; object-fit:contain; flex-shrink:0; border:1px solid {BORDER};}}
.mini {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px; padding:12px 14px; height:100%;}}
.mini .tt {{font-weight:800; font-size:.95rem;}}
.mini .xx {{font-size:.8rem; color:{MUTED}; margin-top:2px; line-height:1.45;}}
/* balão de ajuda ⓘ */
.tip {{position:relative; display:inline-block; cursor:help; color:{MUTED}; font-size:.85em;
margin-left:5px; outline:none; text-transform:none; letter-spacing:0; font-weight:400;}}
.tip .tipbox {{visibility:hidden; opacity:0; position:absolute; z-index:99999; left:50%;
transform:translateX(-50%); bottom:140%; width:280px; background:{SURFACE}; border:1px solid {BORDER};
border-radius:12px; padding:10px 12px; max-width:70vw; font-size:.76rem; line-height:1.45; font-weight:400;
color:{TEXT}; text-align:left; box-shadow:0 8px 22px rgba(0,0,0,.18); transition:opacity .15s;}}
.tip:hover .tipbox, .tip:focus .tipbox {{visibility:visible; opacity:1;}}
/* início */
.hero2 {{text-align:center; padding:26px 8px 6px;}}
.hero2 h1 {{font-size:2.1rem; font-weight:800; color:{TEXT}; margin:0 0 6px; padding:0; line-height:1.15;}}
.hero2 p {{font-size:1.02rem; color:{MUTED}; margin:0;}}
.stp {{display:flex; justify-content:center; gap:8px; flex-wrap:wrap; margin:6px 0 14px;}}
.stp span {{display:inline-block; padding:5px 14px; border-radius:999px; font-size:.8rem; font-weight:700;
background:{SURFACE}; border:1px solid {BORDER}; color:{MUTED};}}
.stp span.on {{background:{BRAND}; border-color:{BRAND}; color:#ffffff;}}
.chips {{display:flex; gap:8px; flex-wrap:wrap; margin:4px 0 6px;}}
.chip {{display:inline-flex; gap:8px; align-items:baseline; background:{SURFACE}; border:1px solid {BORDER};
border-radius:999px; padding:5px 14px; font-size:.9rem;}}
.st-key-home_busca_box [data-testid="stForm"] {{border:none; padding:0; background:transparent;}}
.st-key-home_busca_box {{max-width:720px; margin:0 auto;}}
/* botões */
.stButton > button, .stFormSubmitButton > button {{border-radius:999px; font-weight:700;}}
button[data-testid^="stBaseButton-primary"] {{background:{BRAND}; border-color:{BRAND};}}
button[data-testid^="stBaseButton-primary"]:hover {{background:{BRAND_DARK}; border-color:{BRAND_DARK};}}
button[data-testid^="stBaseButton-primary"] p {{color:#ffffff !important;}}
a[data-testid="stPageLink-NavLink"] {{border:1px solid {BORDER}; border-radius:999px; background:{SURFACE};}}
a[data-testid="stPageLink-NavLink"]:hover {{background:{SOFT};}}
/* barra de contexto (ativos, perfil, ajustes) */
.st-key-ctx_bar {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px; padding:8px 12px; margin-bottom:10px;}}
/* menu próprio: uma barra no computador, botão ☰ no celular */
.st-key-nav_desktop, .st-key-nav_mobile {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px;
padding:4px 8px; margin:2px 0 10px;}}
.st-key-nav_desktop [data-testid="stHorizontalBlock"], .st-key-nav_mobile [data-testid="stHorizontalBlock"] {{
flex-wrap:nowrap !important; gap:.25rem !important; align-items:center;}}
.st-key-nav_desktop [data-testid="stColumn"], .st-key-nav_desktop [data-testid="column"],
.st-key-nav_mobile [data-testid="stColumn"], .st-key-nav_mobile [data-testid="column"] {{
min-width:0 !important; flex:1 1 0 !important; width:auto !important;}}
.st-key-nav_desktop button, .st-key-nav_mobile button {{width:100%; border:none !important;
background:transparent !important; box-shadow:none !important; justify-content:center;}}
.st-key-nav_desktop button p, .st-key-nav_mobile button p {{font-weight:800; white-space:nowrap;
overflow:hidden; text-overflow:ellipsis;}}
.st-key-nav_desktop button:hover, .st-key-nav_mobile button:hover {{background:{SOFT} !important;}}
.st-key-nav_desktop a[data-testid="stPageLink-NavLink"] {{border:none; background:transparent; justify-content:center;}}
.st-key-nav_desktop a[data-testid="stPageLink-NavLink"] p {{font-weight:800; white-space:nowrap;}}
.st-key-nav_desktop a[aria-current="page"] {{background:{SOFT};}}
.st-key-nav_mobile {{display:none;}}
[data-testid="stPopoverBody"] a[data-testid="stPageLink-NavLink"] {{border:none; border-radius:10px;
background:transparent; padding:.45rem .6rem;}}
[data-testid="stPopoverBody"] a[data-testid="stPageLink-NavLink"]:hover {{background:{SOFT};}}
[data-testid="stPopoverBody"] a[aria-current="page"] {{background:{SOFT};}}
/* trilha de etapas (mostra em que passo da análise a pessoa está) */
.st-key-trilha_bar {{background:{SURFACE}; border:1px solid {BORDER}; border-radius:14px; padding:8px 12px; margin-bottom:10px;}}
.st-key-trilha_bar [data-testid="stHorizontalBlock"] {{flex-wrap:wrap !important; gap:.3rem !important;}}
.st-key-trilha_bar [data-testid="stColumn"], .st-key-trilha_bar [data-testid="column"] {{
min-width:0 !important; flex:0 0 auto !important; width:auto !important;}}
.st-key-trilha_bar a[data-testid="stPageLink-NavLink"] {{border:1px solid {BORDER}; border-radius:999px; background:{BG};}}
.st-key-trilha_bar a[data-testid="stPageLink-NavLink"] p {{white-space:nowrap; font-weight:700; font-size:.85rem;}}
.st-key-trilha_bar a[aria-current="page"] {{background:{BRAND}; border-color:{BRAND};}}
.st-key-trilha_bar a[aria-current="page"] p, .st-key-trilha_bar a[aria-current="page"] span {{color:#ffffff !important;}}
@media (max-width:1100px) {{
.st-key-nav_desktop {{display:none;}}
.st-key-nav_mobile {{display:block;}}
}}
@media (max-width:768px) {{
.block-container {{padding-left:.8rem; padding-right:.8rem;}}
.hero2 h1 {{font-size:1.6rem;}}
}}
section[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"],
[data-testid="collapsedControl"] {{display:none !important;}}
</style>
""",
    unsafe_allow_html=True,
)

PLOT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font={"color": TEXT}, margin=dict(l=10, r=10, t=40, b=10))
GRID = dict(gridcolor="#DDE1E6", zeroline=False)
PLOT_LEG = {**PLOT, "margin": dict(l=10, r=10, t=40, b=60)}  # margem extra p/ legenda abaixo do gráfico

FONTES = ["Yahoo Finance", "Fundamentus", "Brapi"]
PERFIS = rec.PERFIS
FINANCEIRAS = ("ITSA", "ITUB", "BBDC", "BBAS", "BPAC", "SANB", "BBSE", "CXSE", "SULA",
               "INBR", "BRSR", "BPAN", "XPBR", "PSSA", "ROXO", "ABCB")

# ---------------------------------------------------------------- cor fixa e única por ativo
PALETA = ["#3B6BC4", "#D9622B", "#2E8B57", "#C0392B", "#7B5EA7", "#B8941F",
          "#1F8FA3", "#C2457F", "#6B8E23", "#8C4A2F", "#2C4A8C", "#7FA832",
          "#A23CB0", "#1E7F74", "#A8650B", "#556270", "#A93A55", "#2B7BA8",
          "#5B4BB0", "#8F7A1E"]


def _cor_gerada(n: int) -> str:
    """Cor extra (ângulo áureo no matiz) para quando a paleta fixa acaba."""
    r, g, b = colorsys.hls_to_rgb((n * 0.61803398875) % 1, 0.42, 0.55)
    return "#%02X%02X%02X" % (int(r * 255), int(g * 255), int(b * 255))


def cor_ativo(tk: str) -> str:
    """Cada ativo tem sempre a mesma cor em todas as páginas, e dois ativos nunca dividem a mesma cor."""
    tk = str(tk).upper().replace(".SA", "").strip()
    mapa = st.session_state.setdefault("cores_ativos", {})
    if tk not in mapa:
        usadas = set(mapa.values())
        cor = next((c for c in PALETA if c not in usadas), None)
        n = len(mapa)
        while cor is None:
            cand = _cor_gerada(n)
            if cand not in usadas:
                cor = cand
            n += 1
        mapa[tk] = cor
    return mapa[tk]


# ---------------------------------------------------------------- glossário (tooltips ⓘ)
from glossario import GLOSSARIO  # noqa: E402


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


def cabecalho(emoji: str, titulo: str, sub: str = ""):
    """Título curto da página com uma linha de apoio."""
    s = f'<div class="pgsub">{html.escape(sub)}</div>' if sub else ""
    md(f'<div class="pghead"><div class="pgt">{emoji} {html.escape(titulo)}</div>{s}</div>')


def cfg_ajuda(df) -> dict:
    """column_config com o ⓘ do glossário nos cabeçalhos da tabela."""
    return {c: st.column_config.Column(help=ajuda_txt(c)) for c in df.columns if c in GLOSSARIO}

# ---------------------------------------------------------------- estado
# O app começa vazio: nenhuma empresa vem pré-selecionada.
st.session_state.setdefault("universo", [])
st.session_state.setdefault("sel_ativos", [])
st.session_state.setdefault("fonte_dados", "Yahoo Finance")
st.session_state.setdefault("perfil", "Moderado")
st.session_state.setdefault("tour_passo", 0)


def eh_financeiro(tk: str) -> bool:
    return normaliza(tk).startswith(FINANCEIRAS)


from dados import (  # camada de dados (arquivo dados.py)
    _sep,
    _token,
    brl,
    buscar_brapi,
    buscar_caixa_brapi,
    buscar_caixa_yahoo,
    buscar_fundamentus,
    buscar_macro_bcb,
    buscar_macro_ipea,
    buscar_yahoo,
    estilizar,
    fx_anual,
    fx_atual,
    historico_brapi,
    historico_yahoo,
    normaliza,
    num,
    pct,
)


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


_ULTIMO_BOM: dict = {}  # ticker -> (dados, hora da leitura): reserva quando todas as fontes falham


def _buscar_fonte(ticker: str, fonte: str) -> dict:
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


@st.cache_data(ttl=900, show_spinner=False)
def _buscar_cache(ticker: str, fonte: str) -> dict:
    d = _buscar_fonte(ticker, fonte)
    if not d.get("preco"):
        raise ValueError(d.get("erro") or "sem preço")  # erro não é guardado em cache
    return d


def buscar(ticker: str) -> dict:
    """Busca com cache de 15 min, troca de fonte se faltar preço e última leitura boa como reserva."""
    fonte = st.session_state.get("fonte_dados", "Yahoo Finance")
    for f in [fonte] + [x for x in FONTES if x != fonte]:
        try:
            d = dict(_buscar_cache(ticker, f))
        except Exception:
            continue
        d["alertas"] = list(d.get("alertas", []))
        if f != fonte:
            d["alertas"].append(f"{fonte} sem preço agora: dados vindos de {f}.")
        _ULTIMO_BOM[ticker] = (d, datetime.now())
        return d
    if ticker in _ULTIMO_BOM:
        d, quando = _ULTIMO_BOM[ticker]
        d = dict(d)
        d["alertas"] = list(d["alertas"]) + [
            f"Fontes indisponíveis agora: usando a última leitura bem-sucedida ({quando:%d/%m %H:%M})."]
        return d
    return _buscar_fonte(ticker, fonte)  # sem nada em cache: devolve o formato original, com o erro


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
            fx = anual.get(int(ano)) or atual  # sem câmbio do ano, usa o atual (nunca quebra)
            if not fx:
                return pd.DataFrame(), "Fluxo de caixa em USD e câmbio indisponível para algum ano."
            df.loc[ano] = df.loc[ano] * fx
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
                st.warning(f"Não consegui carregar {tk}: {e}. Se persistir, troque a **Fonte** em ⚙️ "
                           "(Fundamentus ou Brapi) ou abra Ajuda → Fontes de dados.")
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
def _status_margem(margem, margem_alvo):
    if margem is None:
        return "Sem dados", "na"
    if margem >= margem_alvo:
        return "Abaixo do justo", "good"
    if margem >= 0:
        return "No preço justo", "fair"
    return "Acima do justo", "bad"


def _margem(justo, preco):
    """Margem de segurança = (justo − preço) ÷ justo."""
    return (justo - preco) / justo * 100 if justo and justo > 0 and preco else None


def base_bazin(d: dict):
    """Dividendo anual médio dos últimos 5 anos completos (ano em curso fica de fora).
    Anos sem pagamento entram como zero. Devolve (média, nº de anos, tem_ano_atipico)."""
    da = d.get("div_ano")
    try:
        if da is not None and len(da) > 0:
            serie = pd.Series(list(da.values), index=[int(a) for a in da.index]).astype(float)
            ano = datetime.now().year
            serie = serie[serie.index < ano]
            if len(serie) >= 1:
                ini = max(int(serie.index.min()), ano - 5)
                serie = serie.reindex(range(ini, ano)).fillna(0.0)
                if len(serie) >= 2:
                    med = float(serie.median())
                    atipico = med > 0 and float(serie.max()) > 2 * med
                    return float(serie.mean()), len(serie), atipico
    except Exception:
        pass
    dm = d.get("div_medio")
    return (dm if dm is not None else None), None, False


def graham_calc(d: dict, margem_alvo: float) -> dict:
    """Graham: √(22,5 × LPA × VPA), só para LPA e VPA positivos."""
    lpa, vpa = d.get("lpa"), d.get("vpa")
    justo = aviso = None
    if lpa is None or vpa is None:
        aviso = "LPA ou VPA indisponível na fonte."
    elif lpa <= 0 or vpa <= 0:
        aviso = "LPA ou VPA negativo: Graham não se aplica."
    else:
        justo = sqrt(22.5 * lpa * vpa)
    margem = _margem(justo, d.get("preco"))
    status, cls = _status_margem(margem, margem_alvo)
    return {"justo": justo, "margem": margem, "status": status, "cls": cls, "aviso": aviso, "lpa": lpa, "vpa": vpa}


def bazin_calc(d: dict, yield_alvo: float, margem_alvo: float) -> dict:
    """Bazin: dividendo médio anual ÷ yield desejado."""
    base, anos, atipico = base_bazin(d)
    justo = aviso = None
    if base is None or base <= 0:
        aviso = "Sem dividendos nos últimos anos: Bazin não se aplica."
    elif yield_alvo <= 0:
        aviso = "Yield desejado inválido."
    else:
        justo = base / (yield_alvo / 100)
        if atipico:
            aviso = "Um dos anos pagou bem mais que os demais (talvez extraordinário): a média pode estar inflada."
    margem = _margem(justo, d.get("preco"))
    status, cls = _status_margem(margem, margem_alvo)
    return {"justo": justo, "margem": margem, "status": status, "cls": cls, "aviso": aviso,
            "base": base, "anos": anos, "yield": yield_alvo}


def cfgs_preco_justo(d: dict, g: dict, b: dict, cor: str, completo: bool = False):
    """Configuração dos dois quadrados (Graham e Bazin), usada na página inicial e na página Preço justo."""
    def cm(x):
        return (GOOD if x["margem"] >= 0 else BAD) if x["margem"] is not None else None
    l_g = [("Preço justo", brl(g["justo"]), "Preço justo", None), ("Margem", pct(g["margem"], 0), "Margem (%)", cm(g))]
    l_b = [("Preço justo", brl(b["justo"]), "Preço justo", None), ("Margem", pct(b["margem"], 0), "Margem (%)", cm(b))]
    if completo:
        l_g = [("Preço atual", brl(d.get("preco")), "Preço", None)] + l_g + [
            ("LPA", brl(g["lpa"]), None, None), ("VPA", brl(g["vpa"]), None, None)]
        l_b = [("Preço atual", brl(d.get("preco")), "Preço", None)] + l_b + [
            ("Dividendo médio/ano", brl(b.get("base")), "Média 5 anos", None),
            ("Yield desejado", pct(b["yield"], 1), None, None),
            ("Anos considerados", str(b["anos"]) if b.get("anos") else "—", None, None)]
    cg = dict(titulo="Preço justo · Graham", icone="🎯", status=g["status"], cls=g["cls"], cor_borda=cor,
              linhas=l_g, nota="√(22,5 × LPA × VPA)", aviso=g["aviso"] or "")
    cb = dict(titulo="Preço justo · Bazin", icone="💵", status=b["status"], cls=b["cls"], cor_borda=cor,
              linhas=l_b, nota="Dividendo médio ÷ yield desejado", aviso=b["aviso"] or "")
    return cg, cb


def analisar(d: dict, metodo: str, yield_alvo: float, margem_alvo: float) -> dict:
    """Preço justo por Graham e/ou Bazin (a média é usada só no Ranking)."""
    preco = d.get("preco")
    graham = graham_calc(d, margem_alvo)["justo"]
    bazin = bazin_calc(d, yield_alvo, margem_alvo)["justo"]

    if metodo == "Graham":
        justo, base = graham, "Graham"
    elif metodo == "Bazin":
        justo, base = bazin, "Bazin"
    else:
        vals = [v for v in (graham, bazin) if v is not None and v > 0]
        justo = sum(vals) / len(vals) if vals else None
        base = {2: "Graham + Bazin", 1: "só Graham" if graham else "só Bazin"}.get(len(vals), "sem base")

    margem = None
    if justo and preco and justo > 0:
        margem = (justo - preco) / justo * 100

    if margem is None:
        status, cls = "Sem dados", "na"
    elif margem >= margem_alvo:
        status, cls = "Abaixo do justo", "good"
    elif margem >= 0:
        status, cls = "No preço justo", "fair"
    else:
        status, cls = "Acima do justo", "bad"
    return {**d, "graham": graham, "bazin": bazin, "justo": justo, "base": base,
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


def juro_real(selic, ipca):
    """Juro real pela equação de Fisher: (1 + Selic) ÷ (1 + IPCA) − 1 (a subtração simples superestima)."""
    if selic is None or ipca is None:
        return None
    return ((1 + selic / 100) / (1 + ipca / 100) - 1) * 100


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
    """Velocímetro da margem. O número mostra o valor real; só a barra é limitada à escala (−60% a 60%)."""
    sem = margem is None or pd.isna(margem)
    fig = go.Figure(go.Indicator(
        mode="gauge" if sem else "gauge+number", value=0 if sem else float(margem),
        number={"suffix": "%", "valueformat": ".1f", "font": {"size": 26, "color": TEXT}},
        gauge={"axis": {"range": [-60, 60], "tickcolor": MUTED},
               "bar": {"color": cor, "thickness": 0.22},
               "bgcolor": "rgba(0,0,0,0)", "borderwidth": 0,
               "steps": [{"range": [-60, 0], "color": "rgba(184,58,58,.20)"},
                         {"range": [0, 20], "color": "rgba(168,101,11,.20)"},
                         {"range": [20, 60], "color": "rgba(46,125,79,.20)"}]},
    ))
    if sem:
        fig.add_annotation(text="Sem dados", x=0.5, y=0.1, showarrow=False, font={"size": 14, "color": MUTED})
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


# ---------------------------------------------------------------- tendência do gráfico diário (5 anos)
TEND_VIS = {"Alta": ("▲", GOOD), "Lateral": ("►", FAIR), "Baixa": ("▼", BAD)}


def _rotular_tendencia(acima: bool, cruz: bool, incl: bool) -> str:
    """Três sinais: preço acima da média de 200 dias, média de 50 acima da de 200 e média de 200 subindo."""
    pts = int(acima) + int(cruz) + int(incl)
    return "Alta" if pts == 3 else ("Baixa" if pts == 0 else "Lateral")


@st.cache_data(ttl=3600, show_spinner=False)
def _tendencia_cache(ticker: str, fonte: str) -> str:
    """Lê o gráfico diário (até 5 anos). Levanta erro sem dados, para a falha não ficar em cache."""
    df, _ = historico(ticker, "5y", "1d")
    if df is None or df.empty or "Close" not in df:
        raise ValueError("sem histórico")
    c = df["Close"].dropna()
    if len(c) < 200:
        raise ValueError("histórico curto")
    mm50, mm200 = c.rolling(50).mean(), c.rolling(200).mean()
    m200 = float(mm200.iloc[-1])
    if not m200 > 0:
        raise ValueError("média inválida")
    ref = mm200.iloc[-21] if len(c) >= 220 else None
    cruz = float(mm50.iloc[-1]) > m200
    incl = (m200 > float(ref)) if ref is not None and pd.notna(ref) else cruz
    return _rotular_tendencia(float(c.iloc[-1]) > m200, cruz, incl)


def tendencia_5a(ticker: str):
    """'Alta', 'Lateral', 'Baixa' ou None quando não há histórico suficiente."""
    try:
        return _tendencia_cache(ticker, st.session_state.get("fonte_dados", "Yahoo Finance"))
    except Exception:
        return None


def linha_tendencia(t) -> str:
    if not t:
        return (f'<div style="margin-top:10px;"><div class="lbl">Tendência · diário, 5 anos{tip("Tendência")}</div>'
                f'<div class="val" style="color:{MUTED}">— sem dados</div></div>')
    ic, cor = TEND_VIS[t]
    return (f'<div style="margin-top:10px;"><div class="lbl">Tendência · diário, 5 anos{tip("Tendência")}</div>'
            f'<div class="val" style="color:{cor}">{ic} {t}</div></div>')


# ---------------------------------------------------------------- componentes de interface
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


def _processar_termos(texto: str) -> str:
    """Aceita tickers ou nomes de empresa, separados por vírgula. Devolve a mensagem para a pessoa."""
    termos = []
    for p in re.split(r"[,;]+", texto or ""):
        sub = p.split()
        if len(sub) > 1 and all(rec.REGEX_TICKER.fullmatch(rec.normalizar_ticker(s)) for s in sub):
            termos += sub
        elif p.strip():
            termos.append(p.strip())
    novos, falhas = [], []
    for termo in termos:
        tk = rec.resolver_termo(termo)
        if tk:
            _adicionar(tk)
            novos.append(tk)
        else:
            falhas.append(termo)
    partes = []
    if novos:
        partes.append("Adicionado: " + ", ".join(novos))
    if falhas:
        partes.append("Não encontrei: " + ", ".join(falhas) + ". Confira o nome ou digite o ticker (ex.: WEGE3).")
    return " · ".join(partes)


def _adicionar_ticker():  # formulário do ⚙️
    st.session_state["msg_add"] = _processar_termos(st.session_state.get("novo_ticker", ""))


def _home_adicionar():  # caixa de busca da página inicial
    st.session_state["msg_home"] = _processar_termos(st.session_state.get("home_q", ""))


def estado_vazio():
    md('<div class="ctx neu"><div class="t">👋 Nenhuma empresa em análise ainda</div>'
       '<div class="x">Escolha uma empresa no campo <b>Ativos em análise</b> (acima) ou comece pela página inicial.</div></div>')
    st.page_link(PG_INICIO, label="Escolher na página inicial", icon="🏠")


# ---------------------------------------------------------------- tutorial (curto)
TOUR = ["Como funciona", "Seu perfil", "Escolha uma empresa", "Leia o resultado", "Os limites"]


def _tour_ir(delta: int):
    st.session_state.tour_passo = max(0, min(len(TOUR) - 1, st.session_state.get("tour_passo", 0) + delta))


def _tour_perfil():
    st.session_state["perfil"] = st.session_state["tour_perfil"]


@st.dialog("🎓 Tutorial rápido", width="large")
def tutorial():
    i = st.session_state.get("tour_passo", 0)
    st.progress((i + 1) / len(TOUR), text=f"Passo {i + 1} de {len(TOUR)} · {TOUR[i]}")

    if i == 0:
        st.markdown("### Cada tela responde a uma pergunta")
        md("- 💲 **O preço está de acordo com o valor?** → Analisar separadamente → Preço justo, Múltiplos, DCF\n"
           "- 🏗️ **A empresa é saudável?** → Analisar separadamente → Saúde financeira\n"
           "- 💰 **Ela reparte lucro?** → Analisar separadamente → Dividendos\n"
           "- 📈 **Para onde o preço caminhou?** → Analisar separadamente → Gráfico e tendência\n"
           "- 🏆 **Qual combina mais comigo?** → Ranking\n"
           "- 🌐 **Como está a economia?** → Economia")
        st.caption("Nenhuma tela decide sozinha: o objetivo é cruzar as informações. "
                   "Ferramenta educacional, nada aqui é recomendação de compra ou venda.")

    elif i == 1:
        st.markdown("### Qual é o seu perfil de investidor?")
        md("O perfil muda as réguas do app: margem de segurança, dividend yield desejado, taxa de desconto do DCF "
           "e oscilação tolerada.")
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
        st.caption("Troque a qualquer momento no topo. O perfil de verdade é definido no questionário de "
                   "suitability da sua corretora.")

    elif i == 2:
        st.markdown("### Encontre uma empresa pelo nome")
        st.caption("Experimente *Petrobras*, *banco*, *energia* ou *WEG* e clique em ➕.")
        q = st.text_input("Nome da empresa", key="tour_q", placeholder="Ex.: Petrobras, WEG, Itaú...")
        if q.strip():
            res = rec.buscar_catalogo(q, 4)
            if res:
                render_resultados(res, "tour")
            else:
                st.info("Não encontrei no catálogo. Tente outro nome ou digite o ticker (ex.: WEGE3).")
        sel = st.session_state.get("sel_ativos", [])
        if sel:
            st.success("Em análise: " + ", ".join(rec.nome_curto(t) for t in sel))

    elif i == 3:
        st.markdown("### 🎯 Preço justo e margem de segurança")
        md("O app estima quanto a ação *deveria* valer por **Graham** (lucro e patrimônio por ação) e **Bazin** "
           "(dividendos). A **margem de segurança** = (preço justo − preço) ÷ preço justo: quanto maior, mais folga "
           "para a estimativa errar. O semáforo resume: abaixo, no ponto ou acima do justo.")
        md("Exemplo **fictício**: Graham = √(22,5 × 4,00 × 30,00) = **R$ 51,96**; Bazin = R$ 2,40 ÷ 6% = **R$ 40,00**; "
           "preço justo (média) = **R$ 45,98**. Com preço de R$ 35,00, a margem é **23,9%**.")
        st.caption("Aviso: o preço justo depende de lucro, patrimônio e dividendos, que podem estar distorcidos "
                   "por um ano atípico. Não é previsão.")

    else:
        st.markdown("### Os limites de qualquer método")
        md("- Números olham o **passado**; o futuro pode ser diferente.\n"
           "- Cada setor tem seus patamares normais; bancos e seguradoras não usam DCF nem Dív./PL como as demais.\n"
           "- O **💬 Assistente** explica termos, mas não indica compra ou venda.\n"
           "- Para recomendação personalizada, procure um profissional registrado na CVM.")
        pf = perfil_atual()
        n = len(st.session_state.get("sel_ativos", []))
        md(f"✅ Perfil: **{PERFIS[pf]['icone']} {pf}** · Empresas em análise: **{n}**")

    st.write("")
    c1, c2, c3 = st.columns(3)
    c1.button("← Voltar", on_click=_tour_ir, args=(-1,), disabled=i == 0, width="stretch")
    if i < len(TOUR) - 1:
        c2.button("Próximo →", on_click=_tour_ir, args=(1,), type="primary", width="stretch")
        if c3.button("Fechar", width="stretch"):
            st.rerun()
    elif c2.button("Concluir ✅", type="primary", width="stretch"):
        st.session_state.tour_passo = 0
        st.rerun()


# ---------------------------------------------------------------- página: início (voltada a iniciantes)
def termos_basicos():
    termos = [
        ("🏢", "Ação", "Um pedacinho de uma empresa. Quem tem ações é sócio dela."),
        ("💰", "Dividendo", "Parte do lucro que a empresa reparte com os sócios."),
        ("🎯", "Preço justo", "Estimativa de quanto a ação deveria valer. É uma conta, não uma promessa."),
        ("📈", "Tendência", "Para onde o preço caminhou: alta, lateral ou baixa."),
    ]
    for col, (ico, t, x) in zip(st.columns(4), termos):
        with col:
            md(f'<div class="mini"><div class="tt">{ico} {t}</div><div class="xx">{x}</div></div>')


# ---------------------------------------------------------------- resumo de cada análise (página inicial)
# ---------------------------------------------------------------- adicionar à carteira (guardada na sessão, como em carteira.py)
def _adicionar_carteira(tk: str, destino: str, qtd: int, preco: float, dt: date):
    """Registra a compra na carteira fictícia ou real. Devolve uma mensagem de erro, ou None se deu certo."""
    chave = "cart_ficticia" if destino == "Fictícia" else "cart_real"
    lotes = st.session_state.setdefault(chave, [])
    custo = qtd * preco
    if chave == "cart_ficticia":
        capital = st.session_state.get("cart_capital", 100000.0)
        caixa = capital - sum(l["qtd"] * l["preco_medio"] for l in lotes)
        if custo > caixa + 1e-9:
            return f"Essa compra custa {brl(custo)}, mas o caixa disponível na carteira fictícia é {brl(caixa)}."
    lotes.append({"ticker": normaliza(tk), "qtd": int(qtd), "preco_medio": float(preco), "data": dt.isoformat()})
    return None


def botao_carteira(tk: str, preco):
    """Botão com formulário curto para levar a empresa analisada para a carteira."""
    with st.popover("💼 Adicionar à carteira"):
        destino = st.radio("Carteira", ["Fictícia", "Real"], horizontal=True, key=f"cw_dest_{tk}",
                           help="Fictícia = simulação sem dinheiro de verdade. Real = registro do que você comprou.")
        qtd = st.number_input("Quantidade", min_value=1, step=1, value=100, key=f"cw_qtd_{tk}")
        pm = st.number_input("Preço pago (R$)", min_value=0.01, step=0.01, format="%.2f",
                             value=round(float(preco), 2) if preco else 0.01, key=f"cw_pm_{tk}")
        dt = st.date_input("Data da compra", value=date.today(), max_value=date.today(), format="DD/MM/YYYY",
                           key=f"cw_dt_{tk}")
        if st.button("Confirmar", type="primary", key=f"cw_ok_{tk}"):
            erro = _adicionar_carteira(tk, destino, int(qtd), float(pm), dt)
            if erro:
                st.error(erro)
            else:
                st.toast(f"{tk} adicionada à carteira {destino.lower()}.", icon="✅")
                st.caption("Veja em **Carteira** no menu.")


def _card_resumo(titulo, icone, status, cls, linhas, cor_borda, nota="", aviso=""):
    """Quadrado resumido de uma análise. linhas = [(rótulo, valor, chave do glossário ou None, cor ou None)]."""
    itens = "".join(
        f'<div><div class="lbl">{html.escape(r)}{tip(k) if k else ""}</div>'
        f'<div class="val" style="color:{c or TEXT}">{v}</div></div>' for r, v, k, c in linhas)
    n = f'<div class="nm" style="margin:2px 0 0;">{html.escape(nota)}</div>' if nota else ""
    a = f'<div class="aviso">⚠️ {html.escape(aviso)}</div>' if aviso else ""
    md(f'<div class="card" style="border-top:3px solid {cor_borda}; min-height:190px;">'
       f'<span class="badge {cls}">{html.escape(status)}</span>'
       f'<div class="sec" style="margin-top:0;">{icone} {html.escape(titulo)}</div>{n}'
       f'<div style="display:flex; flex-wrap:wrap; gap:10px 22px; margin-top:8px;">{itens}</div>{a}</div>')


def resumo_ativo(d: dict, P: dict):
    """Para uma empresa: um quadrado por análise (preço justo, múltiplos, saúde, dividendos e fluxo de caixa)."""
    tk, preco, fin = d["ticker"], d.get("preco"), eh_financeiro(d["ticker"])
    cor = cor_ativo(tk)
    m = multiplos(d)

    _cab, _btn = st.columns([3, 1.3], vertical_alignment="center")
    with _btn:
        botao_carteira(tk, preco)
    with _cab:
        md(f'''<div style="display:flex; align-items:center; gap:12px; margin:14px 0 6px;">{logo_img(tk, 40)}
<div><div class="tk">{html.escape(tk)} · {brl(preco)}</div>
<div class="nm" style="margin:0;">{html.escape(rec.nome_curto(tk))}</div></div></div>''')

    # 1 e 2 · preço justo: um quadrado para cada método
    c_graham, c_bazin = cfgs_preco_justo(d, graham_calc(d, P["margem_alvo"]),
                                         bazin_calc(d, P["yield_alvo"], P["margem_alvo"]), cor)

    # 2 · múltiplos
    pts = int(m["pl"] is not None and 0 < m["pl"] <= 15) + int(m["pvp"] is not None and 0 < m["pvp"] <= 1.5)
    if m["pl"] is None and m["pvp"] is None:
        st_m, cl_m = "Sem dados", "na"
    else:
        st_m, cl_m = {2: ("Múltiplos baixos", "good"), 1: ("Intermediário", "fair")}.get(pts, ("Múltiplos altos", "bad"))
    c_mult = dict(titulo="Múltiplos", icone="⚖️", status=st_m, cls=cl_m, cor_borda=cor,
                  linhas=[("P/L", num(m["pl"]), "P/L", None), ("P/VP", num(m["pvp"]), "P/VP", None),
                          ("EV/EBITDA", "n/a" if fin else num(d.get("ev_ebitda")), "EV/EBITDA", None)])

    # 3 · saúde financeira
    roe, ml, dpl = m["roe"], m["margem"], d.get("div_pl")
    if roe is None and ml is None and (dpl is None or fin):
        st_s, cl_s = "Sem dados", "na"
    else:
        ok = (int(roe is not None and roe >= 10) + int(ml is not None and ml >= 8)
              + int(fin or dpl is None or dpl <= 100))
        st_s, cl_s = {3: ("Sólida", "good"), 2: ("Moderada", "fair")}.get(ok, ("Frágil", "bad"))
    c_saude = dict(titulo="Saúde financeira", icone="🏢", status=st_s, cls=cl_s, cor_borda=cor,
                   linhas=[("ROE", pct(roe, 1), "ROE (%)", None), ("Margem líq.", pct(ml, 1), "Margem líq. (%)", None),
                           ("Dív./PL", "n/a" if fin else pct(dpl, 0), "Dív./PL (%)", None)])

    # 4 · dividendos
    anos = None
    try:
        da = d.get("div_ano")
        if da is not None and len(da) > 0:
            compl = da[da.index < datetime.now().year].tail(5)
            anos = int((compl > 0).sum()) if len(compl) else None
    except Exception:
        anos = None
    dy = m["dy"]
    if dy is None:
        st_d, cl_d = "Sem dados", "na"
    elif dy >= 6:
        st_d, cl_d = "Bom pagador", "good"
    elif dy >= 3:
        st_d, cl_d = "Moderado", "fair"
    else:
        st_d, cl_d = "Pouco provento", "na"
    c_div = dict(titulo="Dividendos", icone="💰", status=st_d, cls=cl_d, cor_borda=cor,
                 linhas=[("DY 12m", pct(dy, 1), "DY 12m (%)", None), ("Média 5 anos", brl(base_bazin(d)[0]), "Média 5 anos", None),
                         ("Anos pagando", f"{anos}/5" if anos is not None else "—", None, None)])

    # 5 · fluxo de caixa (DCF)
    if fin:
        c_dcf = dict(titulo="Fluxo de caixa (DCF)", icone="🧮", status="Não se aplica", cls="na", cor_borda=cor,
                     linhas=[("Motivo", "Bancos e seguradoras não usam DCF tradicional", None, None)])
    else:
        try:
            caixa, _ = buscar_caixa(tk)
        except Exception:
            caixa = pd.DataFrame()
        base = fcl_base(caixa, "Média", 3)
        res, erro = dcf_modelo(base, d.get("acoes"), P["taxa"] / 100, P["g"] / 100, P["gp"] / 100, 5, 0.0)
        if res and preco:
            md_ = (res["valor"] - preco) / res["valor"] * 100
            st_f, cl_f = (("Abaixo do justo", "good") if md_ >= P["margem_alvo"]
                          else ("No preço justo", "fair") if md_ >= 0 else ("Acima do justo", "bad"))
            c_dcf = dict(titulo="Fluxo de caixa (DCF)", icone="🧮", status=st_f, cls=cl_f, cor_borda=cor,
                         linhas=[("Valor DCF", brl(res["valor"]), "Valor DCF", None),
                                 ("Potencial", pct((res["valor"] / preco - 1) * 100, 0), "Potencial", None),
                                 ("FCL base (R$ mi)", num(base / 1e6, 0), "FCL", None)])
        else:
            c_dcf = dict(titulo="Fluxo de caixa (DCF)", icone="🧮", status="Sem dados", cls="na", cor_borda=cor,
                         linhas=[("Motivo", html.escape(erro or "Fluxo de caixa indisponível"), None, None)])

    linha1 = [(c_graham, PG_PRECO), (c_bazin, PG_PRECO), (c_mult, PG_VAL)]
    linha2 = [(c_saude, PG_MICRO), (c_div, PG_DIV), (c_dcf, PG_DCF)]
    for grupo in (linha1, linha2):
        for col, (cfg, pg_) in zip(st.columns(3), grupo):
            with col:
                _card_resumo(**cfg)
                st.page_link(pg_, label="Ver detalhes", icon="➡️")


def pagina_inicio():
    ativos = st.session_state.get("sel_ativos", [])
    perfil = perfil_atual()
    P = PERFIS[perfil]

    if not ativos:
        md('<div class="hero2"><h1>Qual empresa você quer entender?</h1>'
           '<p>Digite o nome e veja, em linguagem simples, se o preço está justo.</p></div>')
        with st.container(key="home_busca_box"):
            with st.form("home_busca", clear_on_submit=True):
                c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
                c1.text_input("Empresa", key="home_q", label_visibility="collapsed",
                              placeholder="Ex.: Petrobras, WEG, Itaú...")
                c2.form_submit_button("Analisar", type="primary", on_click=_home_adicionar, width="stretch")
            msg = st.session_state.pop("msg_home", "")
            if msg:
                st.caption(msg)
        pops = rec.populares()[:6]
        if pops:
            st.caption("Ou comece por uma destas:")
            for col, r in zip(st.columns(len(pops)), pops):
                col.button(rec.nome_curto(r["ticker"]), key=f"pop_{r['ticker']}", on_click=_adicionar,
                           args=(r["ticker"],), width="stretch")
        return

    cabecalho("🏠", "Suas empresas", f"Resumo com as regras do perfil {P['icone']} {perfil}.")
    dados = carregar(ativos)
    mostrar = list(dados.values())[:4]
    with st.spinner("Montando o resumo de cada análise..."):
        for d in mostrar:
            resumo_ativo(d, P)
    if len(dados) > len(mostrar):
        st.caption(f"Mostrando {len(mostrar)} de {len(dados)} empresas. Veja as demais em Analisar separadamente.")
    st.caption("Resumos simplificados, com faixas de referência gerais: cada setor tem seus próprios patamares normais.")


# ---------------------------------------------------------------- página: ajuda
def pagina_ajuda():
    cabecalho("❓", "Ajuda", "Termos, tutorial e diagnóstico das fontes de dados.")
    secoes = ["Termos básicos", "Tutorial", "Fontes de dados"]
    aba = st.segmented_control("Seção", secoes, default=secoes[0], key="ajuda_aba",
                               label_visibility="collapsed") or secoes[0]
    if aba == "Termos básicos":
        termos_basicos()
        st.write("")
        k = st.selectbox("Procure qualquer termo do app", sorted(GLOSSARIO), index=None,
                         placeholder="Ex.: P/L, ROE, Margem de segurança...")
        if k:
            explica(k)
    elif aba == "Tutorial":
        st.write("Um passeio de poucos minutos pelas telas do app.")
        if st.button("🎓 Abrir o tutorial", type="primary"):
            st.session_state.tour_passo = 0
            tutorial()
    else:
        diagnostico_fontes()


# ---------------------------------------------------------------- páginas: analisar (fundamentalista)
def pagina_preco_justo():
    cabecalho("🎯", "Preço justo",
              "Dois métodos, cada um com o seu resultado: Graham (lucro e patrimônio) e Bazin (dividendos).")
    dados = dados_ativos()
    if not dados:
        return
    perfil = perfil_atual()
    P = PERFIS[perfil]
    yield_alvo, margem_alvo = float(P["yield_alvo"]), int(P["margem_alvo"])

    calc = {tk: (graham_calc(d, margem_alvo), bazin_calc(d, yield_alvo, margem_alvo)) for tk, d in dados.items()}
    t_painel, t_comp = st.tabs(["Painel", "Comparativo"])

    with t_painel:
        for tk, d in dados.items():
            g, b = calc[tk]
            cor = cor_ativo(tk)
            _cab, _btn = st.columns([3, 1.3], vertical_alignment="center")
            with _btn:
                botao_carteira(tk, d.get("preco"))
            with _cab:
                md(f'''<div style="display:flex; align-items:center; gap:12px; margin:14px 0 6px;">{logo_img(tk, 40)}
<div><div class="tk">{html.escape(tk)} · {brl(d.get("preco"))}</div>
<div class="nm" style="margin:0;">{html.escape(rec.nome_curto(tk))}</div></div></div>''')
            if d.get("fx_aplicado"):
                md(f'<div class="aviso">Balanço em USD convertido (dólar {num(d["fx_aplicado"], 2)})</div>')
            for col, cfg, c in zip(st.columns(2), cfgs_preco_justo(d, g, b, cor, completo=True), (g, b)):
                with col:
                    _card_resumo(**cfg)
                    st.plotly_chart(gauge(c["margem"], cor), width="stretch",
                                    key=f"g_{cfg['titulo']}_{tk}", config={"displayModeBar": False})
                    st.caption("Margem de segurança")

    with t_comp:
        df = pd.DataFrame([{"Ticker": tk, "Preço": d.get("preco"),
                            "Graham": calc[tk][0]["justo"], "Margem Graham (%)": calc[tk][0]["margem"],
                            "Bazin": calc[tk][1]["justo"], "Margem Bazin (%)": calc[tk][1]["margem"]}
                           for tk, d in dados.items()])
        g1, g2 = st.columns(2)
        with g1:
            md(f'<div class="sec">Preço atual × Graham × Bazin{tip("Preço justo")}</div>')
            fig = go.Figure()
            fig.add_bar(x=df["Ticker"], y=df["Preço"], name="Preço atual", marker_color=MUTED)
            fig.add_bar(x=df["Ticker"], y=df["Graham"], name="Graham", marker_color=ACCENT)
            fig.add_bar(x=df["Ticker"], y=df["Bazin"], name="Bazin", marker_color=BRAND)
            fig.update_layout(barmode="group", height=270, legend=dict(orientation="h", y=1.15, x=0), **PLOT)
            fig.update_yaxes(**GRID)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        with g2:
            md(f'<div class="sec">Margem de segurança por método{tip("Margem (%)")}</div>')
            fig2 = go.Figure()
            fig2.add_bar(x=df["Ticker"], y=df["Margem Graham (%)"], name="Graham", marker_color=ACCENT)
            fig2.add_bar(x=df["Ticker"], y=df["Margem Bazin (%)"], name="Bazin", marker_color=BRAND)
            fig2.add_hline(y=margem_alvo, line_dash="dot", line_color=MUTED,
                           annotation_text=f"alvo {margem_alvo}%", annotation_font_color=MUTED)
            fig2.add_hline(y=0, line_color=BORDER)
            fig2.update_layout(barmode="group", height=270, legend=dict(orientation="h", y=1.15, x=0), **PLOT)
            fig2.update_yaxes(**GRID)
            st.plotly_chart(fig2, width="stretch", config={"displayModeBar": False})
        st.dataframe(estilizar(df, {"Preço": brl, "Graham": brl, "Bazin": brl,
                                    "Margem Graham (%)": pct, "Margem Bazin (%)": pct}),
                     width="stretch", hide_index=True)
        st.caption("Cada método é calculado por si só. Quando um não se aplica (LPA/VPA negativos ou sem dividendos), "
                   "ele aparece como “Sem dados” em vez de ser misturado com o outro.")


def pagina_valuation():
    cabecalho("⚖️", "Múltiplos", "P/L, P/VP e outros indicadores para comparar empresas. Passe o mouse no ⓘ.")
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
        if metrica in GLOSSARIO:
            explica(metrica)
    fmts = {c: num for c in df.columns if c != "Ticker"}
    fmts.update({"Preço": brl, "DY 12m (%)": pct, "ROE (%)": pct, "Margem líq. (%)": pct, "Dív./PL (%)": pct})
    st.dataframe(estilizar(df, fmts), width="stretch", hide_index=True, column_config=cfg_ajuda(df))


def pagina_dividendos():
    cabecalho("💰", "Dividendos", "Quanto a empresa repartiu com os sócios e quanto isso rendeu sobre o preço (DY).")
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
        p, d12, dm = d.get("preco"), d.get("div_12m"), base_bazin(d)[0]
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
    fig.update_layout(barmode="group", height=300, title="Fluxo de caixa histórico (R$ milhões)",
                      legend=dict(orientation="h", y=-0.15, x=0), **PLOT_LEG)
    fig.update_yaxes(**GRID)
    return fig


def pagina_dcf():
    cabecalho("🧮", "Fluxo de caixa descontado (DCF)",
              "Valor da empresa pelo dinheiro que ela deve gerar. Método mais avançado: comece pelo Preço justo.")
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

    perfil = perfil_atual()
    P = PERFIS[perfil]
    with st.expander(f"Premissas · iniciais do perfil {P['icone']} {perfil}", expanded=True):
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
        desc_div = st.checkbox("Descontar dívida líquida do valor da firma", value=False,
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
            if k_ in GLOSSARIO:
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
    fig.update_layout(barmode="group", height=330, title="Fluxos projetados (R$ milhões)",
                      legend=dict(orientation="h", y=-0.15, x=0), **PLOT_LEG)
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

    with st.expander("Todos os ativos selecionados (mesmas premissas)"):
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


# ---------------------------------------------------------------- página: ranking (stock picking)
PILARES = ["Valor", "Qualidade", "Dividendos", "Solidez", "Tendência", "Risco"]
COR_PERFIL = {"Conservador": "#1E7F74", "Moderado": "#3B6BC4", "Arrojado": "#D9622B"}


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


def _perfil_ranking():
    st.session_state["perfil"] = st.session_state["rank_perfil"]


def _coletar_ranking(tickers: list) -> dict:
    """Busca em paralelo (poucas threads) dados, fluxo de caixa e sinais técnicos de cada empresa."""
    ctx = get_script_run_ctx()

    def tarefa(tk):
        try:
            if ctx is not None:
                add_script_run_ctx(threading.current_thread(), ctx)
            d = buscar(tk)
            cx = pd.DataFrame() if eh_financeiro(tk) else buscar_caixa(tk)[0]
            return tk, (d, cx, sinais_tecnicos(tk))
        except Exception:
            return tk, None

    out = {}
    prog = st.progress(0.0, text="Coletando dados...")
    with ThreadPoolExecutor(max_workers=4) as ex:
        futs = [ex.submit(tarefa, tk) for tk in tickers]
        for n, f in enumerate(as_completed(futs), start=1):
            tk, v = f.result()
            if v is not None:
                out[tk] = v
            prog.progress(n / len(futs), text=f"Coletando dados... {n}/{len(futs)}")
    prog.empty()
    return out


def pagina_picking():
    perfil = perfil_atual()
    P = PERFIS[perfil]
    cabecalho("🏆", "Ranking", f"Nota de 0 a 100 no perfil {P['icone']} {perfil}. Serve para triagem, não é ordem de compra.")
    st.session_state["rank_perfil"] = perfil
    st.radio("Perfil do investidor", list(PERFIS), key="rank_perfil", horizontal=True, on_change=_perfil_ranking,
             format_func=lambda x: f"{PERFIS[x]['icone']} {x}")
    modo = st.segmented_control("Ranking de", ["Empresas selecionadas", "Setores específicos"],
                                default="Empresas selecionadas", key="rank_modo") or "Empresas selecionadas"

    base = None  # no modo por setor: ticker -> (dados, fluxo de caixa, sinais técnicos)
    if modo == "Empresas selecionadas":
        dados = dados_ativos()
        if not dados:
            return
    else:
        setores = st.multiselect("Setores", rec.SETORES, key="rank_setores", placeholder="Escolha um ou mais setores")
        tickers = [e["ticker"] for e in rec.CATALOGO if e["setor"] in setores]
        if not tickers:
            st.info("Escolha ao menos um setor para montar o ranking.")
            return
        if len(tickers) > 30:
            st.caption(f"Os setores escolhidos têm {len(tickers)} empresas; o ranking usa as 30 primeiras do catálogo.")
            tickers = tickers[:30]
        chave = (tuple(tickers), st.session_state.get("fonte_dados"))
        cA, cB = st.columns([1.6, 4], vertical_alignment="center")
        if cA.button("📥 Calcular o ranking", type="primary", width="stretch"):
            st.session_state["rank_base"] = {"chave": chave, "dados": _coletar_ranking(tickers)}
        cB.caption(f"{len(tickers)} empresa(s). A coleta leva alguns segundos e fica guardada enquanto você ajusta "
                   "perfil e pesos.")
        rb = st.session_state.get("rank_base")
        if not rb or rb["chave"] != chave:
            st.info("Clique em **Calcular o ranking** para buscar os dados dos setores escolhidos.")
            return
        base = rb["dados"]
        if not base:
            st.warning("Não consegui dados para essas empresas agora. Tente de novo ou troque a fonte em ⚙️.")
            return
        dados = {tk: v[0] for tk, v in base.items()}

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
            if base is not None:
                _, cx, tecn = base[tk]
            else:
                cx = pd.DataFrame() if eh_financeiro(tk) else buscar_caixa(tk)[0]
                tecn = sinais_tecnicos(tk)
            a = avaliar(d, perfil, cx, tecn, pesos, usar_tend)
            linhas.append({"Ativo": tk, "Nota": a["nota"], **a["pil"],
                           "Cobertura": f"{sum(v is not None for v in a['pil'].values())}/{len(PILARES)}",
                           "Preço": d.get("preco"), "Preço justo": a["r"]["justo"],
                           "Margem (%)": a["r"]["margem"], "Status": a["r"]["status"],
                           **({"Setor": (rec.info(tk) or {}).get("setor", "—")} if base is not None else {})})

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

    with st.expander("Radar por ativo"):
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
        st.caption("Pilar vazio no radar significa dado indisponível (plotado como 0).")
    st.caption("Ferramenta educacional para triagem. A nota não é recomendação de compra ou venda.")


# ---------------------------------------------------------------- cartões de resultado (usados no tutorial)
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


# ---------------------------------------------------------------- páginas: economia e saúde das empresas
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


# (título, [(código, modo), ...], formatador, cor, unidade do delta, o que monitorar)
# O 1º código é o que você pediu; os seguintes são reserva, usados só se o primeiro vier vazio.
# modo: "valor"  -> mostra a série como vem
#       "preco"  -> índice de preços: se vier como nível, vira variação % mensal
#       "indice" -> número-índice: mostra o nível e a variação em 12 meses
IPEA_CATEGORIAS = {
    "💹 Macro e valuation": [
        ("Selic acumulada no mês (%)", [("BM12_SELC12", "valor"), ("BM12_TJOVER12", "valor")],
         lambda v: pct(v, 2), GOOD, "p.p.",
         "Custo de capital e taxa de desconto das empresas (WACC)."),
        ("Câmbio R$/US$ (média)", [("BM12_ERC12", "valor"), ("BM12_ERV12", "valor")],
         brl, ACCENT, "R$",
         "Impacto em exportadoras (Vale, Suzano) e importadoras."),
        ("Risco-País EMBI+ Brasil (pontos)", [("BM12_EMBI12", "valor"), ("JPM366_EMBI366", "valor")],
         lambda v: f"{num(v, 0)} pts", "#7B5EA7", "pts",
         "Prêmio de risco exigido para investir no Brasil."),
    ],
    "🏷️ Preços e contratos": [
        ("IPCA mensal (%)", [("PRECOS12_IPCA12", "preco"), ("PRECOS12_IPCAG12", "valor")],
         lambda v: pct(v, 2), FAIR, "p.p.",
         "Reajuste de contratos e inflação repassada ao consumidor."),
        ("IGP-M mensal (%)", [("PRECOS12_IGPM12", "preco"), ("IGP12_IGPMG12", "valor"), ("IGP12_IGPM12", "preco")],
         lambda v: pct(v, 2), "#1E7F74", "p.p.",
         "Indexador de aluguéis (shoppings, galpões) e contratos de elétricas."),
        ("INCC mensal (%)", [("PRECOS12_INCC12", "preco")],
         lambda v: pct(v, 2), "#B8941F", "p.p.",
         "Pressão de custos em construtoras e incorporadoras."),
    ],
    "🏭 Atividade econômica": [
        ("IBC-Br (prévia do PIB)", [("SGS12_IBCBR12", "indice")],
         lambda v: num(v, 1), "#2B7BA8", "pts",
         "Termômetro mensal da economia: o país está crescendo?"),
        ("Produção industrial (geral)", [("PIMPF12_INDG12", "indice")],
         lambda v: num(v, 1), "#6B8E23", "pts",
         "Demanda e desempenho de indústrias e bens de capital."),
    ],
    "🛒 Varejo, consumo e crédito": [
        ("Vendas no varejo (PMC)", [("PMC12_RVT12", "indice")],
         lambda v: num(v, 1), "#C2457F", "pts",
         "Força do consumo (Assaí, Carrefour, Magazine Luiza)."),
        ("Desemprego PNAD (%)", [("PNADC12_TDES12", "valor")],
         lambda v: pct(v, 1), BAD, "p.p.",
         "Capacidade de endividamento da população e inadimplência."),
    ],
}


def _serie_ipea(codigos, modo_unused=None):
    """Tenta cada código na ordem. Devolve (código usado, modo, DataFrame com coluna 'valor')."""
    for cod, modo in codigos:
        try:
            df = buscar_macro_ipea(cod)
        except Exception:
            continue
        if df is None or df.empty or "valor" not in df:
            continue
        s = df["valor"].dropna()
        if s.empty:
            continue
        if modo == "preco" and s.abs().median() > 30:  # veio como número-índice: converte em % mensal
            s = (s.pct_change() * 100).dropna()
        if not s.empty:
            return cod, modo, s.to_frame("valor")
    return None, None, pd.DataFrame()


# versão com cache de 1 hora: evita refazer as chamadas ao Ipeadata a cada clique
_serie_ipea_cache = st.cache_data(ttl=3600, show_spinner=False)(_serie_ipea)


def painel_assistente(anos: int):
    """Resume, em frases, o que os números atuais estão dizendo (sem explicar o que cada indicador é)."""
    st.markdown("#### 🤖 O que os dados estão dizendo")
    with st.spinner("Lendo os indicadores..."):
        selic, ipca = buscar_macro_bcb(432, 10), buscar_macro_bcb(13522, 10)
        leituras = [lm.ler_selic(selic, ipca, anos), lm.ler_ipca(ipca, anos),
                    lm.ler_dolar(buscar_macro_bcb(1, 10), anos),
                    lm.ler_desemprego(buscar_macro_bcb(24369, 10), anos)]
        for cats in IPEA_CATEGORIAS.values():
            for titulo, codigos, *_ in cats:
                if titulo in lm.SPEC_IPEA:
                    _, _, df_ = _serie_ipea_cache(codigos)
                    leituras.append(lm.ler_ipea(titulo, df_, unidade_pts="pontos" in titulo))
    leituras = [l for l in leituras if l]
    sintese = lm.montar_sintese(leituras)
    md(f'<div class="ctx neu"><div class="t">Resumo do cenário</div>'
       f'<div class="x">{html.escape(sintese)}</div></div>')
    with st.expander(f"Ver as {len(leituras)} leituras individuais"):
        cols = st.columns(2)
        for i, l in enumerate(leituras):
            with cols[i % 2]:
                md(f'<div class="ctx {l["tom"]}"><div class="t">{html.escape(l["titulo"])}</div>'
                   f'<div class="x">{html.escape(l["texto"])}</div></div>')
        st.code(lm.texto_plano(sintese, leituras), language=None)
    st.caption("Leitura automática por regras simples. Verde = favorável à bolsa, vermelho = pede atenção, "
               "amarelo = neutro. Não é recomendação de investimento.")


def pagina_macro():
    cabecalho("🌐", "Cenário econômico",
              "Juros, inflação, dólar, atividade e desemprego influenciam o preço das ações.")
    anos = st.segmented_control("Período", [1, 2, 5, 10], default=2,
                                format_func=lambda x: f"{x} ano{'s' if x > 1 else ''}", key="macro_anos") or 2
    painel_assistente(anos)
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
        for categoria, itens in IPEA_CATEGORIAS.items():
            st.markdown(f"#### {categoria}")
            for i in range(0, len(itens), 2):
                cols = st.columns(2)
                for col, (titulo, codigos, fmt, cor, unid, monitorar) in zip(cols, itens[i:i + 2]):
                    with col:
                        cod, modo, df = _serie_ipea_cache(codigos)
                        if df.empty:
                            st.warning(f"{titulo}: sem dados no Ipeadata agora "
                                       f"(código {codigos[0][0]}). Confira o código ou tente 🔄 mais tarde.")
                            st.caption(f"👀 {monitorar}")
                            continue
                        cartao_serie(titulo, df, anos, fmt, cor, unid, barra=(modo == "preco"))
                        extra = ""
                        if modo == "indice" and len(df) > 12:
                            v12 = (df["valor"].iloc[-1] / df["valor"].iloc[-13] - 1) * 100
                            extra = f" · 12 meses: {pct(v12, 1)}"
                        nota_cod = "" if cod == codigos[0][0] else f" (código reserva {cod})"
                        st.caption(f"👀 {monitorar}{extra}  \nIpeadata: {cod}{nota_cod}")
        st.caption("Séries do Ipeadata. Se o código pedido não devolver dados, o app tenta um código reserva da "
                   "mesma série. Alguns indicadores saem com defasagem de 1 a 2 meses.")


def pagina_micro():
    cabecalho("🏢", "Saúde financeira", "Lucro, dívida e rentabilidade (ROE) mostram se a empresa está forte.")
    dados = dados_ativos()
    if not dados:
        return
    linhas = []
    for tk, d in dados.items():
        m = multiplos(d)
        linhas.append({"Ativo": tk, "Preço": d.get("preco"), "LPA": d.get("lpa"), "VPA": d.get("vpa"),
                       "EV/EBITDA": d.get("ev_ebitda"), "DY 12m (%)": m["dy"], "ROE (%)": m["roe"],
                       "Margem líq. (%)": m["margem"], "Dív./PL (%)": d.get("div_pl")})
    df = pd.DataFrame(linhas)
    st.dataframe(estilizar(df, {
        "Preço": brl, "LPA": brl, "VPA": brl, "EV/EBITDA": num, "DY 12m (%)": pct,
        "ROE (%)": pct, "Margem líq. (%)": pct, "Dív./PL (%)": pct}),
        width="stretch", hide_index=True, column_config=cfg_ajuda(df))
    st.caption("LPA e VPA em R$ (balanços em dólar são convertidos automaticamente). "
               "ROE e margens em %, Dív./PL em % do patrimônio.")


# ---------------------------------------------------------------- página: técnica
def tradingview(ticker: str, intervalo: str, altura: int):
    cfg = {"autosize": True, "symbol": f"BMFBOVESPA:{ticker}", "interval": intervalo,
           "timezone": "America/Sao_Paulo", "theme": "light", "style": "1", "locale": "br",
           "enable_publishing": False, "hide_side_toolbar": True, "allow_symbol_change": False,
           "backgroundColor": BG, "toolbar_bg": BG, "gridColor": BORDER, "container_id": "tv_chart"}
    components.html(f"""
<style>body{{margin:0;background:{BG};}}</style>
<div style="height:{altura}px;width:100%;"><div id="tv_chart" style="height:100%;width:100%;"></div></div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>new TradingView.widget({json.dumps(cfg)});</script>""", height=altura)


def pagina_tecnica():
    cabecalho("📉", "Gráfico e tendência",
              "Alta = subindo, Baixa = caindo, Lateral = de lado. Os sinais são indicadores técnicos e podem errar.")
    ativos = st.session_state.get("sel_ativos", [])
    if not ativos:
        estado_vazio()
        return
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.4])
    ticker = c1.selectbox("Ativo", ativos, key="tec_ativo", format_func=rec.rotulo)
    tf = c2.selectbox("Timeframe", ["Diário", "Semanal"])
    periodo_lbl = c3.selectbox("Período", ["6 meses", "1 ano", "2 anos", "5 anos"], index=1)
    layout = c4.radio("Exibição", ["Empilhado", "Lado a lado"], horizontal=True)

    with st.container(border=True):
        md(linha_tendencia(tendencia_5a(ticker)).replace("margin-top:10px;", "margin-top:0;"))
        st.caption("Tendência (diário, até 5 anos): ▲ Alta = preço acima da média de 200 dias, média de 50 acima da "
                   "de 200 e média de 200 subindo; ▼ Baixa = os três sinais contrários; ► Lateral = sinais mistos. "
                   "Indicador técnico, não recomendação.")

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
    recentes = [s for s in sinais + padroes if s["data"] >= corte]
    m1, m2, m3 = st.columns(3)
    m1.metric("Sinais de alta (10 candles)", sum(s["tipo"] == "alta" for s in recentes))
    m2.metric("Sinais de baixa (10 candles)", sum(s["tipo"] == "baixa" for s in recentes))
    m3.metric("Indecisão (10 candles)", sum(s["tipo"] == "neutro" for s in recentes))

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


# ---------------------------------------------------------------- diagnóstico das fontes de dados (página Ajuda)
def diagnostico_fontes():
    """Testa as três fontes sem cache e mostra o que cada uma devolveu (ou o erro)."""
    st.write("Use se preço ou dividendos não aparecerem. Cada fonte é testada sem cache.")
    tk = st.text_input("Ticker para testar", value="PETR4", key="diag_tk")
    if st.button("Testar as 3 fontes agora", key="diag_btn"):
        try:
            from importlib.metadata import version
            st.caption(f"yfinance instalado: {version('yfinance')}")
        except Exception:
            st.caption("yfinance: versão não identificada")
        linhas = []
        for f in FONTES:
            try:
                d = _buscar_fonte(normaliza(tk), f)
                linhas.append({"Fonte": f, "Preço": d.get("preco"), "LPA": d.get("lpa"), "VPA": d.get("vpa"),
                               "Proventos 12m": d.get("div_12m"), "Média 5 anos": d.get("div_medio"),
                               "Erro": str(d.get("erro") or "—"),
                               "Avisos": " | ".join(d.get("alertas", [])) or "—"})
            except Exception as e:
                linhas.append({"Fonte": f, "Preço": None, "LPA": None, "VPA": None, "Proventos 12m": None,
                               "Média 5 anos": None, "Erro": f"{e.__class__.__name__}: {e}", "Avisos": "—"})
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
        st.caption("“Too Many Requests” ou 429 no Yahoo = o Yahoo bloqueou o servidor onde o app roda (comum no "
                   "Streamlit Cloud). Se Fundamentus ou Brapi funcionarem, escolha uma delas em ⚙️ → Fonte de dados.")


# ---------------------------------------------------------------- navegação
# Menu organizado pela jornada de quem está começando:
#   Início -> Analisar separadamente -> Ranking, mais Economia, Carteira e Ajuda.
# Os url_path das páginas de análise são os mesmos de antes.
PG_INICIO = st.Page(pagina_inicio, title="Início", icon="🏠", url_path="inicio", default=True)
PG_PRECO = st.Page(pagina_preco_justo, title="Preço justo", icon="🎯", url_path="preco-justo")
PG_DCF = st.Page(pagina_dcf, title="Fluxo de caixa (DCF)", icon="🧮", url_path="dcf")
PG_VAL = st.Page(pagina_valuation, title="Múltiplos", icon="⚖️", url_path="valuation")
PG_DIV = st.Page(pagina_dividendos, title="Dividendos", icon="💰", url_path="dividendos")
PG_MICRO = st.Page(pagina_micro, title="Saúde financeira", icon="🏢", url_path="micro")
PG_TEC = st.Page(pagina_tecnica, title="Gráfico e tendência", icon="📉", url_path="tecnica")
PG_PICK = st.Page(pagina_picking, title="Ranking", icon="🏆", url_path="stock-picking")
PG_MACRO = st.Page(pagina_macro, title="Economia", icon="🌐", url_path="macro")
PG_CART = st.Page(carteira.pagina_carteira, title="Carteira", icon="💼", url_path="carteira")
PG_AJUDA = st.Page(pagina_ajuda, title="Ajuda", icon="❓", url_path="ajuda")


def contexto_assistente() -> str:
    """Resumo dos ativos selecionados (até 6) para a assistente explicar o significado dos números."""
    P = PERFIS[perfil_atual()]
    linhas = []
    for tk in st.session_state.get("sel_ativos", [])[:6]:
        try:
            d = buscar(tk)
            r = analisar(d, "Média", P["yield_alvo"], P["margem_alvo"])
            m = multiplos(d)
            linhas.append(
                f"- {tk} ({rec.nome_curto(tk)}): preço {brl(d.get('preco'))}; preço justo do app (Graham/Bazin) "
                f"{brl(r['justo'])}; margem de segurança {pct(r['margem'], 1)}; P/L {num(m['pl'])}; "
                f"P/VP {num(m['pvp'])}; DY 12m {pct(m['dy'], 1)}; ROE {pct(m['roe'], 1)}; "
                f"Dív./PL {pct(d.get('div_pl'), 0)}; tendência 5a {tendencia_5a(tk) or 'sem dados'}")
        except Exception:
            continue
    if not linhas:
        return ""
    return f"Perfil escolhido no app: {perfil_atual()}.\n" + "\n".join(linhas)


paginas = {
    "🏠 Início": [PG_INICIO],
    "🔬 Analisar separadamente": [PG_PRECO, PG_VAL, PG_MICRO, PG_DIV, PG_DCF, PG_TEC],
    "🏆 Ranking": [PG_PICK],
    "🌐 Economia": [PG_MACRO],
    "💼 Carteira": [PG_CART],
    "❓ Ajuda": [PG_AJUDA],
}

# A navegação nativa do Streamlit fica escondida: o menu do topo some no celular.
# O menu próprio (menu_navegacao) funciona em qualquer tela.
try:
    pg = st.navigation(paginas, position="hidden")
except TypeError:
    st.warning("Esta versão do Streamlit é antiga (`pip install -U streamlit`). Usando o menu lateral.")
    pg = st.navigation(paginas)


def _marca_html(tam: int = 34) -> str:
    return (f'<div class="brand"><img src="{svg_uri(LOGO_SVG)}" width="{tam}" height="{tam}">'
            f'<div class="hero">Bolsa para Todos</div></div>')


def menu_navegacao():
    """Computador: marca + um item por grupo (menu suspenso só quando o grupo tem várias páginas).
    Celular: marca + botão ☰ com todos os grupos."""
    with st.container(key="nav_desktop"):
        cols = st.columns([1.7] + [1] * len(paginas), vertical_alignment="center")
        cols[0].markdown(_marca_html(), unsafe_allow_html=True)
        for col, (grupo, itens) in zip(cols[1:], paginas.items()):
            if len(itens) == 1:
                col.page_link(itens[0], label=itens[0].title, icon=itens[0].icon)
            else:
                with col.popover(grupo):
                    for p in itens:
                        st.page_link(p, label=p.title, icon=p.icon)
    with st.container(key="nav_mobile"):
        a, b = st.columns([2, 1], vertical_alignment="center")
        a.markdown(_marca_html(30), unsafe_allow_html=True)
        with b.popover("☰ Menu"):
            for grupo, itens in paginas.items():
                st.markdown(f"**{grupo}**")
                for p in itens:
                    st.page_link(p, label=p.title, icon=p.icon)


def barra_contexto():
    """Uma linha só: empresas em análise, perfil do investidor e ajustes (fonte, atualizar, adicionar ticker)."""
    with st.container(key="ctx_bar"):
        c1, c2, c3 = st.columns([5, 2.2, 0.8], vertical_alignment="center")
        opcoes = list(dict.fromkeys(st.session_state.universo + rec.TODOS_TICKERS))
        c1.multiselect("Ativos em análise", options=opcoes, key="sel_ativos", format_func=rec.rotulo,
                       label_visibility="collapsed",
                       placeholder="Empresas em análise: digite o nome (ex.: Petrobras) ou o ticker")
        for t in st.session_state.sel_ativos:
            if t not in st.session_state.universo:
                st.session_state.universo.append(t)
        c2.selectbox("Perfil do investidor", list(PERFIS), key="perfil", label_visibility="collapsed",
                     format_func=lambda x: f"{PERFIS[x]['icone']} Perfil {x}")
        with c3.popover("⚙️"):
            st.selectbox("Fonte de dados", FONTES, key="fonte_dados")
            if st.button("🔄 Atualizar dados", width="stretch"):
                st.cache_data.clear()
                st.rerun()
            st.markdown("**Adicionar por ticker**")
            with st.form("add", clear_on_submit=True):
                st.text_input("Nome ou ticker", key="novo_ticker", placeholder="Ex.: WEGE3, ABCB4",
                              label_visibility="collapsed")
                st.form_submit_button("Adicionar", on_click=_adicionar_ticker)
            if st.session_state.get("msg_add"):
                st.caption(st.session_state["msg_add"])
            st.page_link(PG_AJUDA, label="Ajuda e diagnóstico", icon="❓")
    if st.session_state.fonte_dados == "Brapi" and not _token():
        st.warning("Token da Brapi não configurado (BRAPI_TOKEN). Os dados virão do Yahoo Finance quando faltarem.")


menu_navegacao()   # marca e menu no topo
barra_contexto()   # empresas em análise, perfil e ajustes
pg.run()
try:  # Assistente de Investimentos: botão flutuante 💬 em todas as páginas
    assistente.flutuante(contexto_fn=contexto_assistente)
except Exception as e:
    st.caption(f"Assistente indisponível no momento ({e.__class__.__name__}).")

st.caption("Ferramenta educacional. Graham, Bazin, DCF e a nota do Ranking são modelos simplificados "
           "e dependem da qualidade das fontes; não constituem recomendação de investimento.")
