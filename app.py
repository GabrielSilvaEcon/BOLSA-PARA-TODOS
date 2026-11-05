"""
Bússola B3 - Preço justo, DCF, múltiplos, dividendos, técnica, ranking por perfil, economia e carteira.

Rodar com: streamlit run app.py
Requer streamlit >= 1.46 e os módulos tecnica.py, recursos.py, dados.py, glossario.py,
leitura_macro.py, carteira.py, cripto.py e assistente.py ao lado.

Estrutura do menu (pensada como uma jornada para quem está começando):
  Início     -> escolher uma ação (B3) ou uma criptomoeda (Binance) e ver o resumo
  Analisar separadamente -> preço justo, múltiplos, saúde financeira, dividendos, DCF e gráfico, um por vez
  Ranking    -> notas por empresa, por perfil de investidor, das selecionadas ou de setores
  Economia   -> Selic, inflação, dólar, atividade
  Carteira   -> acompanhar a carteira
  Cripto     -> análise de fundamentos (CoinGecko + DefiLlama) e análise gráfica (Binance)
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
import incorporar

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
import marca
import tema
import usuarios
import conta_app
import experiencia as EXP
import experiencia_app
import profundidade as PROF
import profundidade_app
import ajuda_app
import macro_app
import leitura as LT
import planos_app
import notif_app
import educacao_app
import protecao
import cripto
import moeda
import cripto_analise
import cripto_app
import fundamentalista_cripto
import mercados
import comparador
import evolucao
import fiis_app
import fundos_app
import renda_fixa_app
import gestao_app
import intel_app
import analise_tecnica_app
import noticias_app
import risco_app
import simulador_app
import relatorios_app
import comparador_app
import tendencia

try:
    from streamlit.runtime.scriptrunner import add_script_run_ctx, get_script_run_ctx
except Exception:  # versões sem esse caminho: segue sem contexto nas threads
    def add_script_run_ctx(*a, **k):
        return None

    def get_script_run_ctx(*a, **k):
        return None

def _favicon():
    try:
        import io
        from PIL import Image
        return Image.open(io.BytesIO(base64.b64decode(marca.FAVICON.split(",", 1)[1])))
    except Exception:
        return "🧭"


protecao.iniciar()      # Passo 22: máscara de segredos nos logs + proteção de rede (SSRF, timeout, certificado)
st.set_page_config(page_title="Bússola B3", page_icon=_favicon(), layout="wide",
                   initial_sidebar_state="collapsed")

# ---------------------------------------------------------------- paleta neutra (confortável para os olhos)
BG, SURFACE, BORDER = "#F2F4F7", "#FBFCFD", "#DDE2E8"
TEXT, MUTED = "#16202B", "#4B5767"
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
/* celular: a coluna da marca ocupa o espaço que sobra e o botão ☰ fica com a largura do próprio texto
   (antes as duas colunas dividiam 50/50 e o nome do app passava por baixo do botão) */
.st-key-nav_mobile [data-testid="stColumn"]:first-child, .st-key-nav_mobile [data-testid="column"]:first-child {{
flex:1 1 auto !important; min-width:0 !important; overflow:hidden;}}
.st-key-nav_mobile [data-testid="stColumn"]:last-child, .st-key-nav_mobile [data-testid="column"]:last-child {{
flex:0 0 auto !important; width:auto !important; min-width:max-content !important;}}
.st-key-nav_mobile button {{width:auto; padding:.35rem .8rem;}}
.brand {{min-width:0; overflow:hidden;}}
.brand img {{flex-shrink:0;}}
.hero {{overflow:hidden; text-overflow:ellipsis; min-width:0;}}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] > div {{white-space:normal !important; overflow:visible !important;
text-overflow:clip !important; overflow-wrap:anywhere; line-height:1.15;}}
@media (max-width:900px) {{[data-testid="stMetricValue"] {{font-size:1.45rem !important;}}}}
[data-testid="stPopoverBody"] {{max-width:calc(100vw - 1.6rem) !important;}}
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
[data-testid="stPopoverBody"] a[data-testid="stPageLink-NavLink"] {{padding:.65rem .7rem;}}
}}
@media (max-width:480px) {{
.hero {{font-size:.98rem;}}
.st-key-nav_mobile {{padding:4px 6px;}}
.st-key-nav_mobile button {{padding:.3rem .65rem;}}
}}

</style>
""",
    unsafe_allow_html=True,
)

st.markdown(tema.css(), unsafe_allow_html=True)   # camada de acabamento visual (espaçamento, sombras, hover, foco)
tema.instalar_graficos(st)   # identidade visual única para todos os gráficos (Passo 19)


def _preparar_cabecalho_do_navegador():
    """Uma vez por sessão: ajusta o <head> da página para celulares (área segura do iPhone, cor da barra, modo app)."""
    if st.session_state.get("_head_ok"):
        return
    st.session_state["_head_ok"] = True
    try:
        incorporar.html(st, """<script>
try {
  const d = window.parent.document;
  const v = d.querySelector('meta[name="viewport"]');
  if (v && !/viewport-fit/.test(v.content)) v.content += ', viewport-fit=cover';
  const add = (n, c) => { if (!d.querySelector('meta[name="' + n + '"]')) { const m = d.createElement('meta'); m.name = n; m.content = c; d.head.appendChild(m); } };
  add('theme-color', '#110C2E'); add('color-scheme', 'dark'); add('mobile-web-app-capable', 'yes');
  add('apple-mobile-web-app-capable', 'yes'); add('apple-mobile-web-app-status-bar-style', 'black'); add('apple-mobile-web-app-title', 'Bússola B3');
} catch (e) {}
</script>""", 0)
    except Exception:
        pass


_preparar_cabecalho_do_navegador()

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
    """Título curto da página com uma linha de apoio. Dentro da página inicial (embutido) vira só a linha de apoio."""
    if st.session_state.get("_embutido"):
        if sub:
            st.caption(sub)
        return
    md(tema.cabecalho(emoji, titulo, sub))


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


FINANCEIRAS_EUA = {"JPM", "BAC", "WFC", "C", "GS", "MS", "V", "MA", "AXP", "SCHW", "BLK", "USB", "PNC", "COF", "BRK-B", "BRK-A"}


def eh_financeiro(tk: str) -> bool:
    tk = normaliza(tk)
    return tk in FINANCEIRAS_EUA if not eh_b3(tk) else tk.startswith(FINANCEIRAS)


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
    eh_b3,
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


def converter_eua_para_reais(d: dict) -> dict:
    """Ação americana: preço, LPA, VPA, proventos e dívida vêm em dólar. Converte tudo para R$ (câmbio do dia) para o
    app inteiro (preço justo, DCF, carteira) falar uma moeda só. Sem câmbio, descarta o preço em vez de misturar moedas."""
    mb = d.get("moeda_balanco")
    if mb and mb != "USD":  # ADR com balanço em outra moeda (ex.: TWD): melhor descartar do que misturar
        for k in ("lpa", "vpa", "divida_liq"):
            d[k] = None
        d["alertas"].append(f"Balanço em {mb}: LPA, VPA e dívida descartados para não gerar números incorretos.")
    fx = fx_atual()
    if not fx:
        d["erro"] = "Câmbio indisponível agora: não dá para converter a ação americana para R$."
        d["preco"] = None
        return d
    for k in ("preco", "lpa", "vpa", "div_12m", "div_medio", "divida_liq"):
        if d.get(k) is not None:
            d[k] = d[k] * fx
    if d.get("div_ano") is not None and len(d["div_ano"]):
        d["div_ano"] = d["div_ano"] * fx
    d["moeda_origem"], d["moeda"], d["moeda_balanco"], d["fx_aplicado"] = "USD", "BRL", "BRL", fx
    d["alertas"].append(f"Ação americana: valores em dólar convertidos para R$ (dólar a {num(fx, 4)}).")
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
    if not eh_b3(ticker):
        fonte = "Yahoo Finance"  # Brapi e Fundamentus cobrem só a B3
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
    if eh_b3(ticker):
        converter_moeda(d)
    elif d.get("preco"):
        converter_eua_para_reais(d)
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
    fontes = [fonte] + [x for x in FONTES if x != fonte] if eh_b3(ticker) else ["Yahoo Finance"]
    for f in fontes:
        try:
            d = dict(_buscar_cache(ticker, f))
        except Exception:
            continue
        d["alertas"] = list(d.get("alertas", []))
        if f != fonte and eh_b3(ticker):
            d["alertas"].append(f"{fonte} sem preço agora: dados vindos de {f}.")
        if not eh_b3(ticker):
            rec.registrar(ticker, d.get("nome"))
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
    nota = f" Fonte: {df.attrs['fonte']} (reserva do Yahoo)." if df.attrs.get("fonte") else ""
    mb, mp = d.get("moeda_balanco") or "BRL", d.get("moeda") or "BRL"
    if (mb == "USD" and mp == "BRL") or d.get("moeda_origem") == "USD":
        anual, atual = fx_anual(), fx_atual()
        if not anual and not atual:
            return pd.DataFrame(), "Fluxo de caixa em USD e câmbio indisponível."
        df = df.copy()
        for ano in df.index:
            fx = anual.get(int(ano)) or atual  # sem câmbio do ano, usa o atual (nunca quebra)
            if not fx:
                return pd.DataFrame(), "Fluxo de caixa em USD e câmbio indisponível para algum ano."
            df.loc[ano] = df.loc[ano] * fx
        return df, "Fluxo de caixa convertido de USD para R$ pelo dólar médio de cada ano." + nota
    return df, (nota.strip() or None)


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
                st.warning(f"Não consegui carregar {tk}: {e}. Se persistir, troque a **Fonte de dados** em Ajustes (menu lateral) "
                           "(Fundamentus ou Brapi) ou abra Ajuda → Fontes de dados.")
    return out


def dados_ativos(perfil: bool = False):
    seletor_ativos(perfil)
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
    fontes = sorted({d.get("fonte") or ("Yahoo Finance" if not eh_b3(tk) else st.session_state.get("fonte_dados", "Yahoo Finance"))
                     for tk, d in dados.items() if not d.get("erro")})
    if fontes:
        st.caption("Fonte dos dados: " + ", ".join(fontes))


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
        partes.append("Não encontrei: " + ", ".join(falhas) + ". Confira o nome ou digite o ticker (ex.: WEGE3 ou AAPL).")
    return " · ".join(partes)


def _adicionar_ticker():  # formulário de Ajustes
    st.session_state["msg_add"] = _processar_termos(st.session_state.get("novo_ticker", ""))


def _home_adicionar():  # caixa de busca da página inicial
    st.session_state["msg_home"] = _processar_termos(st.session_state.get("home_q", ""))


def estado_vazio():
    md('<div class="ctx neu"><div class="t">👋 Nenhuma empresa em análise ainda</div>'
       '<div class="x">Escolha uma empresa no campo acima ou comece pela página inicial.</div></div>')
    st.page_link(PG_INICIO, label="Escolher na página inicial", icon=":material/home:")


def seletor_ativos(perfil: bool = False):
    """Escolha das empresas (e, onde o resultado depende dele, do perfil do investidor) dentro da própria página de análise."""
    if st.session_state.get("_embutido"):                 # dentro das abas do Início o seletor já está no topo da página
        return
    opcoes = list(dict.fromkeys(st.session_state.universo + rec.TODOS_TICKERS))
    cols = st.columns([4, 1.6] if perfil else [1], vertical_alignment="bottom")
    cols[0].multiselect("Empresas em análise", options=opcoes, key="sel_ativos", format_func=rec.rotulo,
                        placeholder="Digite o nome (ex.: Petrobras) ou o ticker")
    if perfil:
        cols[1].selectbox("Perfil do investidor", list(PERFIS), key="perfil",
                          format_func=lambda x: f"{PERFIS[x]['icone']} Perfil {x}")
    for t in st.session_state.get("sel_ativos", []):
        if t not in st.session_state.universo:
            st.session_state.universo.append(t)
    if st.session_state.get("fonte_dados") == "Brapi" and not _token():
        st.warning("Token da Brapi não configurado (BRAPI_TOKEN). Os dados virão do Yahoo Finance quando faltarem.")


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
        md("- 💲 **O preço está de acordo com o valor?** → Ações → Análise fundamentalista → Preço justo, Múltiplos, DCF\n"
           "- 🏗️ **A empresa é saudável?** → Ações → Análise fundamentalista → Saúde financeira\n"
           "- 💰 **Ela reparte lucro?** → Ações → Análise fundamentalista → Dividendos\n"
           "- 📈 **Para onde o preço caminhou?** → Análise gráfica (criptomoedas, ao vivo da Binance)\n"
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
        q = st.text_input("Nome da empresa", key="tour_q", placeholder="Ex.: Petrobras, WEG, Itaú, Apple, AAPL...")
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
    """Registra a compra na carteira fictícia ou real. Ativo do exterior entra com o preço em US$.
    Devolve uma mensagem de erro, ou None se deu certo."""
    chave = "cart_ficticia" if destino == "Fictícia" else "cart_real"
    lotes = st.session_state.setdefault(chave, [])
    tk = normaliza(tk)
    if tk not in {normaliza(x.get("ticker", "")) for x in lotes}:       # Etapa 10: limite de posições do plano (comprar mais de um ativo já presente não conta)
        import planos
        pode, msg = planos.permitido_max("carteira_posicoes", len({normaliza(x.get("ticker", "")) for x in lotes}))
        if not pode:
            return msg
    custo = qtd * preco
    if moeda.eh_dolar(tk):
        f = moeda.cambio_em(moeda.cambio_serie(), dt)
        if not f:
            return "Não consegui a cotação do dólar para converter essa compra. Tente de novo em instantes."
        custo = custo * f
    if chave == "cart_ficticia":
        capital = st.session_state.get("cart_capital", 100000.0)
        gasto = moeda.custo_total_brl(lotes)
        if gasto is None:
            return "Não consegui a cotação do dólar para calcular o caixa da carteira fictícia. Tente de novo em instantes."
        caixa = capital - gasto
        if custo > caixa + 1e-9:
            return f"Essa compra custa {brl(custo)}, mas o caixa disponível na carteira fictícia é {brl(caixa)}."
    lotes.append({"ticker": tk, "qtd": int(qtd), "preco_medio": float(preco), "data": dt.isoformat()})
    return None


def botao_carteira(tk: str, preco, sufixo: str = ""):
    """Botão com formulário curto para levar o ativo analisado para a carteira (R$ na B3, US$ no exterior)."""
    usd = moeda.eh_dolar(normaliza(tk))
    with st.popover("💼 Adicionar à carteira"):
        destino = st.radio("Carteira", ["Fictícia", "Real"], horizontal=True, key=f"cw_dest_{tk}{sufixo}",
                           help="Fictícia = simulação sem dinheiro de verdade. Real = registro do que você comprou.")
        qtd = st.number_input("Quantidade", min_value=1, step=1, value=100, key=f"cw_qtd_{tk}{sufixo}")
        pm = st.number_input("Preço pago (US$)" if usd else "Preço pago (R$)", min_value=0.01, step=0.01, format="%.2f",
                             value=round(float(preco), 2) if preco else 0.01, key=f"cw_pm_{tk}{sufixo}")
        dt = st.date_input("Data da compra", value=date.today(), max_value=date.today(), format="DD/MM/YYYY",
                           key=f"cw_dt_{tk}{sufixo}")
        if usd:
            st.caption("Ativo do exterior: o preço entra em dólar e a carteira converte para reais pelo dólar do dia.")
        if st.button("Confirmar", type="primary", key=f"cw_ok_{tk}{sufixo}"):
            erro = _adicionar_carteira(tk, destino, int(qtd), float(pm), dt)
            if erro:
                st.error(erro)
            else:
                st.toast(f"{tk} adicionada à carteira {destino.lower()}.", icon="✅")
                st.caption("Veja em **Carteira** no menu.")


def barra_carteira(dados: dict, chave: str):
    """Uma linha com o botão de adicionar à carteira para cada empresa em análise (páginas de tabela)."""
    itens = list(dados.items())
    if not itens:
        return
    for i in range(0, len(itens), 4):
        for col, (tk, d) in zip(st.columns(4), itens[i:i + 4]):
            with col:
                st.caption(tk)
                botao_carteira(tk, d.get("preco"), f"_{chave}")


def _card_resumo(titulo, icone, status, cls, linhas, cor_borda, nota="", aviso=""):
    """Card de uma análise. linhas = [(rótulo, valor, chave do glossário ou None, cor ou None)]."""
    itens = "".join(
        f'<div class="rc-m"><div class="rc-l">{html.escape(r)}{tip(k) if k else ""}</div>'
        f'<div class="rc-v"' + (f' style="color:{c}"' if c else "") + f'>{v}</div></div>' for r, v, k, c in linhas)
    n = f'<div class="rc-n">{html.escape(nota)}</div>' if nota else ""
    w = f'<div class="rc-w">⚠️ {html.escape(aviso)}</div>' if aviso else ""
    md(f'<div class="rc {cls}"><div class="rc-h"><div class="rc-ic">{icone}</div>'
       f'<div class="rc-t">{html.escape(titulo)}</div><span class="rc-b">{html.escape(status)}</span></div>'
       f'{n}<div class="rc-g">{itens}</div>{w}</div>')


def resumo_ativo(d: dict, P: dict, com_dcf: bool = True):
    """Para uma empresa: um quadrado por análise (preço justo, múltiplos, saúde, dividendos e fluxo de caixa)."""
    tk, preco, fin = d["ticker"], d.get("preco"), eh_financeiro(d["ticker"])
    cor = cor_ativo(tk)
    m = multiplos(d)

    _cab, _btn = st.columns([3, 1.3], vertical_alignment="center")
    with _btn:
        botao_carteira(tk, preco, "_resumo")
        evolucao.atalho_evolucao(PG_EVOLUCAO, tk, f"resumo_{tk}", "Evolução e crescimento")
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
    linha2 = [(c_saude, PG_MICRO), (c_div, PG_DIV)] + ([(c_dcf, PG_DCF)] if com_dcf else [])
    for grupo in (linha1, linha2):
        for col, (cfg, pg_) in zip(st.columns(3), grupo):
            with col:
                _card_resumo(**cfg)


MODOS = ["Ações", "Ações EUA", "FIIs", "ETFs", "Fundos", "Renda fixa", "Criptomoedas"]
ROTULO_MODO = {"Ações": "Ações B3", "Ações EUA": "Ações EUA", "FIIs": "FIIs", "ETFs": "ETFs", "Fundos": "Fundos",
               "Renda fixa": "Renda fixa", "Criptomoedas": "Criptomoedas Binance"}
COTAS_HOME_CRIPTO = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "ETH/BRL", "BNB/USDT", "XRP/USDT"]


def modo_atual() -> str:
    """Tipo de ativo escolhido no Início (ações B3, ações EUA, FIIs, ETFs, fundos, renda fixa ou cripto). Fica numa chave comum (não de widget) para não se perder ao trocar de página."""
    m = st.session_state.get("modo_ativo_v", "Ações")
    return m if m in MODOS else "Ações"


def _trocar_modo():
    escolhido = st.session_state.get("modo_home")
    if escolhido in MODOS:  # clicar na opção ativa a desmarca; nesse caso o modo atual é mantido
        st.session_state["modo_ativo_v"] = escolhido


def seletor_modo():
    """Abas com o tipo de ativo (Ações B3, Ações EUA, FIIs, ETFs, Fundos, Renda fixa, Cripto) no topo do card principal (o CSS as sobrepõe à borda do card)."""
    with st.container(key="home_modo"):
        st.segmented_control("O que você quer analisar?", MODOS, default=modo_atual(), key="modo_home",
                             format_func=lambda m: ROTULO_MODO[m], on_change=_trocar_modo,
                             label_visibility="collapsed")


# ---------------------------------------------------------------- Início: criptomoedas
def _qtd(v) -> str:
    """Quantidade de tokens em formato curto (21 mi, 120,2 mi)."""
    if v is None:
        return "n/d"
    for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return f"{v / lim:,.1f}{suf}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{v:,.0f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _simbolos_cripto():
    """(pares da Binance, a Binance respondeu?). Sem resposta, vale a lista de pares populares."""
    if ccxt is not None:
        try:
            return set(binance_simbolos(binance_exchange())), True
        except Exception:
            pass
    return set(PARES_POPULARES), False


def _gecko_do_par(base: str):
    """(id, nome) da moeda na CoinGecko a partir do símbolo do par, ou (None, None)."""
    try:
        res = cripto.buscar_moedas(base)
    except Exception:
        return None, None
    alvo = next((r for r in res if str(r["simbolo"]).upper() == base), res[0] if res else None)
    return (alvo["id"], alvo["nome"]) if alvo else (None, None)


def _home_cripto_adicionar(texto=None):
    """Aceita BTC/USDT, btcusdt, eth/brl ou o nome da moeda (Bitcoin, Solana…) e guarda o par."""
    texto = (texto if texto is not None else st.session_state.get("home_q_cripto", "") or "").strip()
    if not texto:
        st.session_state["msg_home_cripto"] = "Digite um par (BTC/USDT) ou o nome de uma criptomoeda."
        return
    simbolos, binance_ok = _simbolos_cripto()
    par = normaliza_par(texto, simbolos)
    if binance_ok and par not in simbolos:  # pode ter digitado o nome (Bitcoin) em vez do símbolo
        try:
            for r in cripto.buscar_moedas(texto):
                cand = f"{str(r['simbolo']).upper()}/USDT"
                if cand in simbolos:
                    par = cand
                    break
        except Exception:
            pass
    if not par or (binance_ok and par not in simbolos):
        st.session_state["msg_home_cripto"] = (f"Não encontrei “{texto}” no mercado à vista da Binance. "
                                               "Tente o par completo, como SOL/USDT.")
        return
    pares = list(st.session_state.get("home_pares_cripto", []))
    if par in pares:
        pares.remove(par)
    st.session_state["home_pares_cripto"] = [par] + pares          # o mais recente aparece primeiro
    st.session_state["graf_par"] = par                              # a Análise gráfica abre neste par
    st.session_state["msg_home_cripto"] = ""
    gid, nome = _gecko_do_par(par.split("/")[0])                    # as páginas de fundamentos usam a CoinGecko
    if gid:
        cripto._adicionar_cripto(gid, nome)


def _home_cripto_remover(par: str):
    st.session_state["home_pares_cripto"] = [p for p in st.session_state.get("home_pares_cripto", []) if p != par]


def _leitura_tecnica(par: str):
    """Tendência SMA 20/50, IFR 14 e %B de Bollinger do par, no diário, com as velas e os indicadores da Binance.
    Usa as mesmas funções e as mesmas regras da página Análise gráfica. None se a Binance não responder."""
    if ccxt is None:
        return None
    try:
        df = binance_ohlcv(par, "1d", 200)
        if len(df) < 30:
            return None
        ind = indicadores_cripto(df)
        tk = binance_ticker(par)
    except Exception:
        return None
    c, u = float(df["Close"].iloc[-1]), ind.iloc[-1]
    s20, s50, r, bl, bu = u["SMA20"], u["SMA50"], u["RSI14"], u["BBL"], u["BBU"]
    if pd.isna(s20) or pd.isna(s50):
        tend = None
    elif c > s50 and s20 > s50:
        tend = "Alta"
    elif c < s50 and s20 < s50:
        tend = "Baixa"
    else:
        tend = "Lateral"
    pb = None if pd.isna(bl) or pd.isna(bu) or bu == bl else (c - bl) / (bu - bl)
    return {"tend": tend, "ifr": None if pd.isna(r) else float(r), "pb": pb, "preco": tk.get("last") or c}


def resumo_cripto(par: str):
    """Para um par: um quadrado por análise (visão geral, on-chain, emissão e gráfica), no mesmo padrão das ações."""
    base, cot = par.split("/")
    gid, nome = _gecko_do_par(base)
    m, a_defi, infl = None, None, None
    if gid:
        try:
            m = cripto.analisar_moeda(gid)
        except Exception:
            m = None
        if m is not None:
            try:
                for slug in cripto.slugs_defi(gid, cripto.listar_protocolos())[:3]:
                    try:
                        a_defi = cripto.analisar_protocolo(slug)
                        break
                    except Exception:
                        continue
            except Exception:
                a_defi = None
            infl = cripto.inflacao_anual(gid)
    tec_ = _leitura_tecnica(par)
    cor = BRAND
    preco_txt = _fmt_preco((tec_ or {}).get("preco")) + f" {cot}" if tec_ else (cripto._preco_usd(m["preco"]) if m else "n/d")

    _cab, _btn = st.columns([3, 1.3], vertical_alignment="center")
    with _cab:
        md(f'''<div style="display:flex; align-items:center; gap:12px; margin:14px 0 6px;">
<div><div class="tk">{html.escape(par)} · {preco_txt}</div>
<div class="nm" style="margin:0;">{html.escape(nome or base)}</div></div></div>''')
    with _btn:
        st.button("Remover", icon=":material/close:", key=f"rm_cripto_{par}", on_click=_home_cripto_remover, args=(par,),
                  width="stretch")
    if m is None:
        st.caption("Não consegui carregar os dados da CoinGecko para esta moeda agora (limite de consultas ou moeda "
                   "fora da lista). O cartão de análise gráfica continua disponível.")

    if m is not None and gid:  # resumo executivo pronto, com a nota fundamentalista da moeda
        try:
            tipo_ = fundamentalista_cripto._detectar_tipo(gid, m)
            dados_f, _av = fundamentalista_cripto.montar_dados(gid, m, tipo_, None, {})
            res_f = fundamentalista_cripto.mf.analisar(dados_f, None)
            assistente.painel_resumo_auto(f"{par} · {nome or base}",
                                          lambda: assistente.resumo_cripto(nome or base, res_f))
        except Exception:
            pass

    por_titulo = {x["titulo"]: x for x in (cripto.indicadores(a_defi) if a_defi else [])}
    gerais = cripto.indicadores_moeda(m) if m else []
    dil = gerais[4] if len(gerais) > 4 else None                    # diluição: Market Cap ÷ FDV (regra do módulo)

    # 1 · visão geral e tokenomics
    if m:
        c_geral = dict(titulo="Visão Geral & Tokenomics", icone="🪙", status=dil["status"], cls=dil["cls"], cor_borda=cor,
                       linhas=[("Market Cap", cripto.usd(m["mcap"]), None, None), ("FDV", cripto.usd(m["fdv"]), None, None),
                               ("Suprimento circ.", cripto._pct(m["mc_fdv"]), None, None)],
                       nota="Suprimento circulante = Market Cap ÷ FDV")
    else:
        c_geral = dict(titulo="Visão Geral & Tokenomics", icone="🪙", status="Sem dados", cls="na", cor_borda=cor,
                       linhas=[("Motivo", "CoinGecko indisponível", None, None)])

    # 2 · métricas de rede / on-chain
    uso = por_titulo.get("Uso do protocolo (TVL)")
    st_rede, cl_rede = (uso["status"], uso["cls"]) if uso else (("Parcial", "na") if m and m.get("vol24") else ("Sem dados", "na"))
    c_rede = dict(titulo="Métricas de Rede / On-Chain", icone="🌐", status=st_rede, cls=cl_rede, cor_borda=cor,
                  linhas=[("Endereços ativos", "n/d", None, None),
                          ("Volume 24h", cripto.usd(m["vol24"]) if m else "n/d", None, None),
                          ("TVL atual", cripto.usd(a_defi["tvl"]) if a_defi else "n/d", None, None)],
                  nota="TVL pelo DefiLlama · volume pela CoinGecko",
                  aviso="Endereços ativos exigem um provedor on-chain, fora das fontes gratuitas do app.")

    # 3 · modelo econômico / emissão
    if m:
        taxas = a_defi["fees30"] if a_defi else None
        c_emissao = dict(titulo="Modelo Econômico / Emissão", icone="📈", status=dil["status"], cls=dil["cls"], cor_borda=cor,
                         linhas=[("Inflação anual (est.)", "n/d" if infl is None else f"{infl:+.2f}%".replace(".", ","), None, None),
                                 ("Receita de taxas 30d", cripto.usd(taxas), None, None),
                                 ("Máx. de tokens", _qtd(m.get("maximo")), None, None)],
                         nota="Inflação: crescimento da oferta em circulação em 12 meses")
    else:
        c_emissao = dict(titulo="Modelo Econômico / Emissão", icone="📈", status="Sem dados", cls="na", cor_borda=cor,
                         linhas=[("Motivo", "CoinGecko indisponível", None, None)])

    # 4 · análise gráfica e técnica (Binance)
    if tec_:
        cls_t = {"Alta": "good", "Baixa": "bad", "Lateral": "fair"}.get(tec_["tend"], "na")
        icone_t = {"Alta": "▲ Alta", "Baixa": "▼ Baixa", "Lateral": "► Lateral"}.get(tec_["tend"], "n/d")
        r = tec_["ifr"]
        ifr_txt = "n/d" if r is None else f"{r:.1f}".replace(".", ",") + (" · sobrecompra" if r >= 70 else " · sobrevenda" if r <= 30 else " · neutro")
        pb = tec_["pb"]
        c_graf = dict(titulo="Análise Gráfica & Técnica", icone="📊", status=tec_["tend"] or "Sem dados", cls=cls_t, cor_borda=cor,
                      linhas=[("Tendência SMA 20/50", icone_t, None, None), ("IFR (14)", ifr_txt, None, None),
                              ("Bollinger %B", "n/d" if pb is None else f"{pb:.2f}".replace(".", ","), None, None)],
                      nota="Diário · velas e cotação ao vivo da Binance")
    else:
        c_graf = dict(titulo="Análise Gráfica & Técnica", icone="📊", status="Sem dados", cls="na", cor_borda=cor,
                      linhas=[("Motivo", "Binance indisponível agora", None, None)])

    for grupo in ([(c_geral, PG_CRIPTO), (c_rede, PG_ONCHAIN)], [(c_emissao, PG_RECEITAS), (c_graf, PG_TEC)]):
        for col, (cfg, pg_) in zip(st.columns(2), grupo):
            with col:
                _card_resumo(**cfg)


def _analise_completa_cripto(par: str):
    """Tudo que as páginas de cripto mostram para um par, em abas (sem links para outras páginas)."""
    base, cot = par.split("/")
    gid, nome = _gecko_do_par(base)
    st.session_state["_embutido"] = True
    try:
        t_nota, t_geral, t_rede, t_emis, t_graf = st.tabs(
            ["⭐ Nota fundamentalista", "🪙 Visão geral", "🔗 Rede e adoção", "📈 Emissão e receitas", "📊 Gráfico"])
        with t_nota:
            if gid:
                fundamentalista_cripto._mostrar_moeda(gid)
            else:
                st.info("Não achei esta moeda na CoinGecko, então a nota fundamentalista não está disponível.")
        for aba, modo in ((t_geral, "cripto"), (t_rede, "onchain"), (t_emis, "receitas")):
            with aba:
                if gid:
                    cripto._mostrar_moeda(gid, modo)
                else:
                    st.info("Moeda não encontrada na CoinGecko.")
        with t_graf:
            try:
                _painel_binance(par, base, cot, "Diário", 500, False)
            except Exception as e:
                st.warning(f"Gráfico indisponível agora ({e.__class__.__name__}).")
    finally:
        st.session_state["_embutido"] = False


def _inicio_cripto():
    """Início no modo Criptomoedas: mesmo card de busca das ações, com exemplos e atalhos de pares da Binance."""
    pares = st.session_state.get("home_pares_cripto", [])
    if not pares:
        md('<div class="hero2 com-abas"><h1>Qual criptoativo você quer entender?</h1>'
           '<p>Digite o par ou o nome e veja fundamentos, rede, emissão e análise gráfica em linguagem simples.</p></div>')
    with st.container(key="home_busca_box"):
        with st.form("home_busca_cripto", clear_on_submit=True):
            c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
            c1.text_input("Criptoativo", key="home_q_cripto", label_visibility="collapsed",
                          placeholder="Ex.: BTC/USDT, ETH/BRL, Solana...")
            c2.form_submit_button("Analisar", type="primary", on_click=_home_cripto_adicionar, width="stretch")
        msg = st.session_state.get("msg_home_cripto", "")
        if msg:
            st.caption(msg)
    if not pares:
        st.caption("Ou comece por uma destas:")
        for col, p in zip(st.columns(len(COTAS_HOME_CRIPTO)), COTAS_HOME_CRIPTO):
            col.button(p, key=f"home_pop_{p}", on_click=_home_cripto_adicionar, args=(p,), width="stretch")
        return
    cabecalho("🏠", "Suas criptomoedas", "Resumo de fundamentos, rede, emissão e análise gráfica (Binance).")
    with st.spinner("Montando o resumo de cada análise..."):
        for par in pares[:3]:
            resumo_cripto(par)
    if len(pares) > 3:
        st.caption(f"Mostrando 3 de {len(pares)} pares, para não estourar o limite de consultas da CoinGecko.")
    md('<div class="sec" style="margin-top:22px;">📚 Análise completa</div>')
    alvo = pares[:3][0] if len(pares[:3]) == 1 else st.selectbox("Par", pares[:3], key="home_cripto_full",
                                                                  help="A análise completa abre para um par por vez.")
    _analise_completa_cripto(alvo)
    st.caption("Resumos simplificados. Criptomoedas são muito voláteis e você pode perder todo o valor investido. "
               "Indicadores técnicos servem para estudo, não são recomendação.")


def _inicio_fundos():
    """Fundos de investimento (CVM): o tipo é escolhido aqui e a análise é a mesma das páginas de fundos."""
    tipos = {"acoes": "Fundos de Ações", "multi": "Multimercados", "rf": "Fundos de Renda Fixa"}
    t = st.segmented_control("Tipo de fundo", list(tipos), default="acoes", format_func=tipos.get, key="home_tipo_fundo") or "acoes"
    fundos_app.pagina_fundos(t, atalho_comparar=atalho_comparar)


def pagina_inicio():
    experiencia_app.inicio()
    seletor_modo()
    modo = modo_atual()
    if modo == "Criptomoedas":
        _inicio_cripto()
        return
    if modo == "Fundos":
        _inicio_fundos()
        return
    paginas = {"FIIs": pagina_fiis_app, "ETFs": pagina_etfs_app, "Renda fixa": pagina_renda_fixa_app}
    if modo in paginas:
        paginas[modo]()
        return
    eua = modo == "Ações EUA"
    ativos = [t for t in st.session_state.get("sel_ativos", []) if eh_b3(t) != eua]
    perfil = perfil_atual()
    P = PERFIS[perfil]

    if not ativos:
        titulo = "Qual empresa americana você quer entender?" if eua else "Qual empresa você quer entender?"
        sub = ("Digite o código de uma ação dos EUA (ex.: AAPL) e veja, em linguagem simples, se o preço está justo."
               if eua else "Digite o nome de uma empresa do Brasil e veja, em linguagem simples, se o preço está justo.")
        md(f'<div class="hero2 com-abas"><h1>{titulo}</h1><p>{sub}</p></div>')
        with st.container(key="home_busca_box"):
            with st.form("home_busca", clear_on_submit=True):
                c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
                c1.text_input("Empresa", key="home_q", label_visibility="collapsed",
                              placeholder="Ex.: Apple, AAPL, Microsoft..." if eua else "Ex.: Petrobras, WEG, Itaú...")
                c2.form_submit_button("Analisar", type="primary", on_click=_home_adicionar, width="stretch")
            msg = st.session_state.pop("msg_home", "")
            if msg:
                st.caption(msg)
        pops = ([{"ticker": t} for t in EUA_POPULARES[:6]] if eua else rec.populares()[:6])
        if pops:
            st.caption("Ou comece por uma destas:")
            for col, r in zip(st.columns(len(pops)), pops):
                col.button(r["ticker"] if eua else rec.nome_curto(r["ticker"]), key=f"pop_{r['ticker']}", on_click=_adicionar,
                           args=(r["ticker"],), width="stretch")
        return

    seletor_ativos()
    cabecalho("🏠", "Suas empresas", f"Resumo com as regras do perfil {P['icone']} {perfil}.")
    prof = seletor_profundidade()
    bl = PROF.blocos_inicio(prof)
    dados = carregar(ativos)
    mostrar = list(dados.values())[:bl["max_empresas"]]
    if mostrar and bl["resumo_ia"]:
        resumo_acoes("inicio", {d["ticker"]: d for d in mostrar})
    with st.spinner("Montando a leitura de cada empresa..."):
        for d in mostrar:
            if bl["cartoes"]:
                resumo_ativo(d, P, com_dcf=bl["dcf"])
            else:
                leitura_rapida_ativo(d, P)
    if len(dados) > len(mostrar):
        st.caption(f"Mostrando {len(mostrar)} de {len(dados)} empresas. Escolha menos empresas acima para ver todas.")
    if bl["cartoes"]:
        st.caption("Cartões simplificados, com faixas de referência gerais: cada setor tem seus próprios patamares normais.")
    else:
        st.caption("Quer ver as contas por trás? Troque para a análise Mediana ou Completa acima. Isto é uma leitura educativa, não uma recomendação.")
    if bl["atalhos"]:
        if len(ativos) >= 2:
            st.page_link(PG_COMPARAR, label="Comparar estas empresas lado a lado", icon=":material/compare_arrows:")
        if bl["intel"]:
            st.page_link(PG_EVOLUCAO, label="Evolução e crescimento (balanços, CAGR, análise automática)", icon=":material/timeline:")
            st.page_link(PG_INTEL, label="Central de inteligência (sinais, riscos, notícias e alertas)", icon=":material/psychology:")
    if bl["intel"]:
        _bloco_intel(st.selectbox("Sinais e notícias de uma empresa", [d["ticker"] for d in mostrar], key="inicio_intel_sel") if mostrar else None)
    if bl["abas"]:
        md('<div class="sec" style="margin-top:22px;">📚 Análise completa</div>')
        st.caption("Tudo que as páginas de análise mostram, aqui mesmo: escolha o assunto nas abas.")
        abas = [("🎯 Preço justo", pagina_preco_justo), ("⚖️ Múltiplos", pagina_valuation),
                ("🏢 Saúde financeira", pagina_micro), ("💰 Dividendos", pagina_dividendos),
                ("🧮 Fluxo de caixa", pagina_dcf)]
        st.session_state["_embutido"] = True
        try:
            for aba, (_, fn) in zip(st.tabs([r for r, _ in abas]), abas):
                with aba:
                    fn()
        finally:
            st.session_state["_embutido"] = False


def profundidade_atual() -> str:
    return profundidade_app.atual()


def seletor_profundidade() -> str:
    return profundidade_app.seletor()


def leitura_rapida_ativo(d: dict, P: dict):
    """Análise rápida de uma empresa: veredito em texto, preço de hoje, preço justo, confiança e o risco principal."""
    tk, preco, fin = d["ticker"], d.get("preco"), eh_financeiro(d["ticker"])
    m = multiplos(d)
    g = graham_calc(d, P["margem_alvo"])
    b = bazin_calc(d, P["yield_alvo"], P["margem_alvo"])
    r = PROF.leitura_rapida(rec.nome_curto(tk), preco, g["justo"], b["justo"], P["margem_alvo"], m["roe"], m["margem"], d.get("div_pl"), fin,
                            m["dy"], experiencia_app.modo())
    _cab, _btn = st.columns([3, 1.3], vertical_alignment="center")
    with _btn:
        botao_carteira(tk, preco, "_rapida")
    with _cab:
        md(f'''<div style="display:flex; align-items:center; gap:12px; margin:14px 0 6px;">{logo_img(tk, 40)}
<div><div class="tk">{html.escape(tk)}</div><div class="nm" style="margin:0;">{html.escape(rec.nome_curto(tk))}</div></div></div>''')
    cls = {"bom": "good", "ok": "fair", "ruim": "bad", "na": "na"}[r["nivel"]]
    linhas = [("Preço hoje", brl(preco), None, None), ("Preço justo", brl(r["justo"]) if r["justo"] else "n/d", "Preço justo", None),
              ("Confiança", r["confianca"], None, None)]
    if experiencia_app.modo() != "iniciante" and r.get("margem") is not None:
        linhas.append(("Margem", pct(r["margem"], 0), "Margem (%)", None))
    _card_resumo(titulo="Leitura rápida", icone="🧭", status=r["selo"], cls=cls, linhas=linhas, cor_borda=cor_ativo(tk),
                 nota=r["frase"], aviso="Risco principal: " + r["risco"])
    st.caption(r["motivo"])


# ---------------------------------------------------------------- página: comparar ativos (motor universal: comparador.py)
# A lógica de comparação, pontuação por classe e validação dos dados fica em comparador.py (sem Streamlit).
# Aqui ficam só os coletores (reaproveitam as funções que o app já tem) e a tela.
CMP_MAX = 8


def _ativo_de_preco(chave: str, nome: str, classe_id: str, serie: pd.Series, moeda: str, fonte: str) -> comparador.Ativo:
    m = comparador.metricas_preco(serie)
    a = comparador.Ativo(chave, nome, classe_id, moeda, m["data_ref"], fonte, comparador.inds_de_preco(m))
    if m["ret12m"] is None:
        a.avisos.append("Histórico de preços com menos de ~12 meses: retorno, volatilidade e queda em 12 meses indisponíveis.")
    return a


def _ativo_acao(tk: str, d: dict, cx: pd.DataFrame, tecn: dict, perfil: str) -> comparador.Ativo:
    """Ação (B3 ou EUA): mesmos dados e mesma nota do Ranking; retorno/risco do histórico de 12 meses."""
    nome = rec.nome_curto(tk)
    if d.get("erro") or not d.get("preco"):
        return comparador.Ativo(tk, nome, "acao", erro=d.get("erro") or "sem cotação")
    df, _ = historico(tk, "2y", "1d")
    serie = df["Close"] if df is not None and not df.empty and "Close" in df else pd.Series(dtype=float)
    m = comparador.metricas_preco(serie)
    P = PERFIS[perfil]
    av = avaliar(d, perfil, cx, tecn)
    av["pesos"] = dict(P["pesos"])
    mu, fin = multiplos(d), eh_financeiro(tk)
    I, ind = comparador.Ind, comparador.inds_de_preco(m)
    ind.update({
        "pl": I(mu["pl"], "calculado", "TTM"), "pvp": I(mu["pvp"], "calculado", "último balanço"),
        "ev_ebitda": I(None, aplica=False) if fin else I(d.get("ev_ebitda"), "dado", "TTM"),
        "roe": I(mu["roe"], "dado", "TTM"), "margem_liq": I(mu["margem"], "dado", "TTM"),
        "dy": I(mu["dy"], "calculado", "12m"),
        "div_pl": I(None, aplica=False) if fin else I(d.get("div_pl"), "dado", "último balanço"),
        "margem_graham": I(av["r"].get("margem"), "calculado"),
    })
    a = comparador.Ativo(tk, nome, "acao", d.get("moeda_origem") or d.get("moeda") or "BRL", m["data_ref"],
                         d.get("fonte") or ("Yahoo Finance" if not eh_b3(tk) else st.session_state.get("fonte_dados", "")), ind)
    a.pontuacao = comparador.de_avaliacao_acao(av, perfil)
    a.avisos = [x for x in d.get("alertas", []) if "convertid" not in x]
    if d.get("data_balanco"):
        a.avisos.append(f"Fundamentos do balanço de {d['data_balanco']}; preços e retornos até "
                        f"{m['data_ref'] or 'data indisponível'}.")
    if m["ret12m"] is None:
        a.avisos.append("Histórico de preços com menos de ~12 meses: retorno, volatilidade e queda em 12 meses indisponíveis.")
    return a


@st.cache_data(ttl=900, show_spinner=False)
def _ativo_etf(tk: str, classe_id: str = "etf") -> comparador.Ativo:
    """ETF (ou FII/fundo, só com indicadores de preço): histórico do Yahoo, 12 meses, mesma janela das ações."""
    t = mercados._ticker_yahoo(tk)
    try:
        df = mercados._historico_eua(t)
    except Exception:
        df = pd.DataFrame()
    moeda = "BRL" if eh_b3(tk) else "USD"
    if df is None or df.empty or len(df) < 30:
        return comparador.Ativo(tk, tk, classe_id, erro="sem histórico de preços no Yahoo Finance")
    a = _ativo_de_preco(tk, tk, classe_id, df["Close"], moeda, "Yahoo Finance")
    if classe_id == "etf":
        a.pontuacao = comparador.pontuar_etf(a.ind)
        fundos_app.enriquecer_etf(a)                     # Passo 10: taxa, patrimônio, tracking, Sharpe e categoria
    return a


@st.cache_data(ttl=900, show_spinner=False)
def _ativo_fii(tk: str) -> comparador.Ativo:
    """FII: preço e rendimentos do Yahoo Finance; P/VP, vacância, nº de imóveis e liquidez do Fundamentus; classificação por
    segmento (fiis.py). Se a lista do Fundamentus falhar, cai no cálculo anterior (só Yahoo) e avisa."""
    tk = normaliza(tk)
    precos = evolucao.coletar_precos(tk)
    serie = precos["ajustado"]
    if serie is None or len(serie) < 30:
        return comparador.Ativo(tk, tk, "fii", erro="sem histórico de preços no Yahoo Finance")
    L = fiis_app.lista_fiis()
    d = fiis_app.preparar(tk, L["df"], evolucao.coletar_fii_fundamentus(tk), precos, None)
    ind = fiis_app.inds_comparador(d)
    a = comparador.Ativo(tk, tk, "fii", "BRL", d["pm"].get("data_ref"), "Yahoo Finance + Fundamentus", ind,
                         subgrupo=d["classe"].estrategia if d["classe"].estrategia != "outros" else "",
                         subgrupo_nome=fiis_app.fiis.ESTRATEGIAS[d["classe"].estrategia])
    a.avisos.append(f"Classificação: {d['classe'].rotulo}.")
    if L["aviso"]:
        a.avisos.append(L["aviso"] + " P/VP, vacância e liquidez ficaram de fora.")
    if d["ind"].get("dy12m") is None:
        a.avisos.append("Rendimentos dos últimos 12 meses indisponíveis no Yahoo (ou histórico curto): DY e regularidade ficam de fora.")
    a.avisos.append("Retorno em 12 meses com rendimentos reinvestidos (preço ajustado). P/VP e vacância são o valor de hoje (Fundamentus).")
    a.pontuacao = comparador.pontuar_fii(a.ind)
    if d["classe"].estrategia in ("papel", "hibrido"):
        a.avisos.append("Risco de crédito da carteira de CRIs (devedores, garantias, inadimplência) não é avaliado: sem fonte no app. "
                        "A nota não mede a qualidade dos devedores.")
    a.avisos.append(f"Estratégia: {fiis_app.fiis.ESTRATEGIAS[d['classe'].estrategia]}; compare com fundos da mesma estratégia.")
    return a


@st.cache_data(ttl=900, show_spinner=False)
def _ativo_cripto(gid: str) -> comparador.Ativo:
    """Criptomoeda: dados da CoinGecko/DefiLlama e a MESMA nota da Análise Fundamentalista de cripto."""
    try:
        m = cripto.analisar_moeda(gid)
        tipo = fundamentalista_cripto._detectar_tipo(gid, m)
        dados, avisos = fundamentalista_cripto.montar_dados(gid, m, tipo, None, {})
        res = fundamentalista_cripto.mf.analisar(dados)
    except cripto.ErroAPI as e:
        return comparador.Ativo(gid, gid, "cripto", erro=f"CoinGecko não respondeu ({e})")
    except Exception as e:
        return comparador.Ativo(gid, gid, "cripto", erro=f"erro inesperado ({e.__class__.__name__})")
    hist = m.get("hist") or []
    serie = pd.Series([p for _, p in hist], index=[t for t, _ in hist], dtype=float) if hist else pd.Series(dtype=float)
    pm = comparador.metricas_preco(serie)
    I, ind = comparador.Ind, comparador.inds_de_preco(pm)
    mc, v24, circ, mx = m.get("mcap"), m.get("vol24"), m.get("circ"), m.get("maximo")
    ind.update({"mcap": I(mc, "dado"), "vol24": I(v24, "dado", "24h"),
                "liquidez": I(v24 / mc * 100 if mc and v24 is not None else None, "calculado", "24h"),
                "ret30": I(m.get("var30"), "dado", "30d"),
                "circ_pct": I(circ / mx * 100 if circ and mx else None, "calculado")})
    # Passo 9: diluição, crescimento da oferta e múltiplos (só onde os dados existem; sem dado = traço, nunca zero)
    fdv, tvl, f30 = m.get("fdv"), dados.get("tvl"), dados.get("fees30")
    if tvl is None and f30 is None and gid != "bitcoin":
        try:                    # o motor antigo não achou o protocolo: tenta a coleta robusta do Passo 9 (vários protocolos)
            extra = cripto_app.linha_comparacao(gid)
            tvl, f30 = extra.get("tvl"), extra.get("fees30")
        except Exception:
            pass
    if gid == "bitcoin":        # o "TVL" e as taxas do DefiLlama para Bitcoin não medem a rede (BTC embrulhado em outras redes)
        tvl = f30 = None
    ind.update({"mc_fdv": I(mc / fdv * 100 if mc and fdv else None, "calculado"),
                "inflacao": I(dados.get("infl"), "calculado", "12m"),
                "tvl": I(tvl if tvl and tvl > 0 else None, "dado"),
                "mc_tvl": I(mc / tvl if mc and tvl and tvl > 0 else None, "calculado"),
                "p_taxas": I(mc / (f30 * cripto_analise.FATOR_ANUAL) if mc and f30 and f30 > 0 else None, "calculado", "30d anualizado")})
    princ = cripto_analise.principal(cripto_analise.classificar(gid, m.get("categorias_todas")))
    nome = f"{m['nome']} ({m['simbolo']})" if m.get("simbolo") else m["nome"]
    a = comparador.Ativo(gid, nome, "cripto", "USD", pm["data_ref"], "CoinGecko / DefiLlama", ind,
                         subgrupo=princ, subgrupo_nome=cripto_analise.CATEGORIAS[princ])
    a.pontuacao = comparador.de_resultado_cripto(res)
    a.avisos = list(dict.fromkeys(avisos + m.get("avisos", [])))
    return a


@st.cache_data(ttl=3600, show_spinner=False)
def _tipo_yahoo(tk: str):
    """Tipo do papel no Yahoo (ETF, EQUITY...). None se não responder: a classificação fica "provável"."""
    try:
        import yfinance as yf
        return (yf.Ticker(mercados._ticker_yahoo(tk)).info or {}).get("quoteType")
    except Exception:
        return None


def _eh_fii_da_lista(tk: str) -> bool:
    """O código está na lista de FIIs do Fundamentus? (units como TAEE11 e KLBN11 não estão.) Falha de rede = não."""
    try:
        return tk in fiis_app.lista_fiis()["df"].index
    except Exception:
        return False


def _classificar_selecao(acoes: list, outros: list, criptos: list) -> list:
    """[(código, classe)] sem repetir. A classe é identificada pelo código (e pelo tipo no Yahoo quando a dúvida existe)."""
    vistos, out = set(), []
    for bruto in list(acoes) + list(outros):
        cod_rf = str(bruto or "").strip().upper()
        if comparador.identificar_classe(cod_rf)[0] == "renda_fixa":                          # TD-IPCA-2035 / RF-<id>
            if cod_rf not in vistos:
                vistos.add(cod_rf)
                out.append((cod_rf, "renda_fixa"))
            continue
        if len(fundos_app.fd.so_digitos(bruto)) == 14 and fundos_app.fd.cnpj_valido(bruto):     # CNPJ = fundo (CVM)
            cn = fundos_app.fd.formatar_cnpj(bruto)
            if cn not in vistos:
                vistos.add(cn)
                out.append((cn, "fundo"))
            continue
        tk = normaliza(bruto)
        if not tk or tk in vistos:
            continue
        vistos.add(tk)
        if _eh_fii_da_lista(tk):
            out.append((tk, "fii"))
            continue
        cl, conf = comparador.identificar_classe(tk, rec.TODOS_TICKERS)
        if conf == "provável" and cl in ("acao", "fii"):
            tipo = _tipo_yahoo(tk)
            if tipo:
                cl, _ = comparador.identificar_classe(tk, rec.TODOS_TICKERS, tipo)
        out.append((tk, cl))
    for g in criptos:
        if g not in vistos:
            vistos.add(g)
            out.append((g, "cripto"))
    return out


def _montar_ativos(sel: list, perfil: str) -> list:
    acoes = [tk for tk, c in sel if c == "acao"]
    base = _coletar_ranking(acoes) if acoes else {}
    out = []
    for tk, c in sel:
        if c == "acao":
            v = base.get(tk)
            if v is None:
                out.append(comparador.Ativo(tk, rec.nome_curto(tk), "acao", erro="não consegui os dados agora"))
            else:
                try:
                    out.append(_ativo_acao(tk, v[0], v[1], v[2], perfil))
                except Exception as e:
                    out.append(comparador.Ativo(tk, rec.nome_curto(tk), "acao", erro=f"erro inesperado ({e.__class__.__name__})"))
        elif c == "cripto":
            out.append(_ativo_cripto(tk))
        elif c == "fii":
            out.append(_ativo_fii(tk))
        elif c == "fundo":
            out.append(fundos_app.ativo_fundo(tk))
        elif c == "renda_fixa":
            out.append(renda_fixa_app.ativo_rf(tk))
        else:
            out.append(_ativo_etf(tk, c))
    return out


def _enriquecer_crescimento(ativos: list) -> list:
    """Passo 7: acrescenta o crescimento histórico (CAGR de 3 anos etc.) aos ativos já montados. Não muda nenhuma nota."""
    for a in ativos:
        if a.erro:
            continue
        if a.classe in ("acao", "etf", "fii"):
            try:
                r = evolucao.coletar_resumo(a.chave, a.classe)
                a.ind.update(evolucao.inds_comparador(r["resumo"], r["fonte"], r["data_ref"]))
                if a.classe != "acao":
                    a.avisos.append("Crescimento histórico: só preço, retorno total e dividendos (sem balanço para esta classe).")
                a.avisos.extend(x for x in r["avisos"] if x not in a.avisos)
            except Exception as e:
                a.avisos.append(f"Crescimento histórico indisponível ({e.__class__.__name__}).")
        elif a.classe == "cripto":
            a.avisos.append("Crescimento histórico: a fonte gratuita de criptomoedas só entrega 365 dias; CAGR de 3 anos não se aplica.")
    return ativos


def _cls_nota(n):
    return "na" if n is None else ("good" if n >= 70 else "fair" if n >= 50 else "bad")


def _mostrar_comparacao(c, perfil: str):
    cl = comparador.CLASSES
    if c.modo == "vazio":
        st.warning("Não consegui dados de nenhum dos ativos agora. Tente de novo em instantes.")
    avisos = [a for a in c.alertas if a != comparador.AVISO_LEGAL]  # o aviso legal é mostrado à parte, no fim
    for a in [x for x in avisos if x.startswith(comparador.PREFIXO_MODELOS)]:
        st.warning(a[len(comparador.PREFIXO_MODELOS):])         # modelos econômicos incompatíveis: sempre à vista
    avisos = [x for x in avisos if not x.startswith(comparador.PREFIXO_MODELOS)]
    if avisos:
        with st.expander(f"⚠️ Qualidade e confiabilidade dos dados ({len(avisos)})", expanded=len(avisos) <= 3 or c.modo == "vazio"):
            for a in avisos:
                st.markdown(f"- {a}")
    if c.modo == "vazio":
        return
    if c.modo == "classes_diferentes":
        st.info("Ativos de classes diferentes: só os critérios comuns são comparados (retorno, volatilidade e queda em "
                "12 meses; com renda fixa, também liquidez, prazo e proteção contra a inflação). As notas de cada "
                "classe usam régua própria e não são colocadas lado a lado.")

    st.markdown("#### Pontuação por classe")
    for cid in c.classes:
        membros = [a for a in c.ativos if a.classe == cid]
        st.caption(f"{cl[cid].nome} — {cl[cid].criterios}" + (f" (perfil {perfil})" if cid == "acao" else ""))
        if not cl[cid].suportada:
            st.info(cl[cid].motivo)
            continue
        if cl[cid].parcial:
            st.caption("⚠️ Análise parcial: " + cl[cid].parcial)
        for col, a in zip(st.columns(min(len(membros), 4)), membros[:4]):
            nota = a.pontuacao.nota if a.pontuacao else None
            pos = comparador.posicionamento(c, a.chave) if nota is not None else "Sem pontuação: dados insuficientes."
            prov = " · provisória" if a.pontuacao and a.pontuacao.provisoria else ""
            col.markdown(tema.card_status(a.chave, "indisponível" if nota is None else f"{nota:.0f}/100",
                                          _cls_nota(nota), f"{pos}{prov}"), unsafe_allow_html=True)
        for a in membros[4:]:
            nota = a.pontuacao.nota if a.pontuacao else None
            st.caption(f"{a.chave}: " + ("indisponível" if nota is None else f"{nota:.0f}/100"))

    st.markdown("#### Comparação lado a lado")
    linhas = comparador.tabela(c)
    if linhas:
        st.dataframe(pd.DataFrame(linhas), width="stretch", hide_index=True)
        st.caption("✅ melhor valor entre os comparados · ⚠️ pior valor · ᶜ calculado a partir de dados · "
                   "(*) períodos diferentes, sem destaque. “Melhor indicador” não significa melhor investimento.")
    else:
        st.info("Não há indicadores com dados para comparar.")

    pts = [(a, a.ind.get("vol"), a.ind.get("ret12m")) for a in c.ativos]
    pts = [(a, v.valor, r.valor) for a, v, r in pts if v and r and v.valor is not None and r.valor is not None]
    if len(pts) >= 2:
        fig = go.Figure()
        for cid in c.classes:
            sub = [p for p in pts if p[0].classe == cid]
            if sub:
                fig.add_scatter(x=[p[1] for p in sub], y=[p[2] for p in sub], mode="markers+text", name=cl[cid].nome,
                                text=[p[0].chave for p in sub], textposition="top center", marker={"size": 13})
        fig.update_layout(height=340, xaxis_title="Volatilidade anual (%) — risco", yaxis_title="Retorno em 12 meses (%)",
                          legend={"orientation": "h", "y": -0.25}, **PLOT)
        st.plotly_chart(fig, width="stretch", key="cmp_risco_retorno", config={"displayModeBar": False})
        st.caption("Risco × retorno dos últimos 12 meses, na moeda de cada ativo. Desempenho passado não garante o futuro.")

    st.markdown("#### Vantagens e desvantagens relativas")
    comparador_app._css()
    cols = st.columns(min(len(c.ativos), 3))
    for i, a in enumerate(c.ativos):
        with cols[i % len(cols)]:
            dd = c.destaques.get(a.chave, {})
            L = [comparador_app.linha_cartao("ok", t, icone="✅") for t in dd.get("vantagens", [])[:6]]
            L += [comparador_app.linha_cartao("aviso", t, icone="⚠️") for t in dd.get("desvantagens", [])[:6]]
            if not L:
                L = [comparador_app.linha_cartao("lim", "Sem diferenças marcantes entre os comparados.", icone="➖")]
            st.markdown(comparador_app._bloco(f"{a.chave} · {a.nome}", L), unsafe_allow_html=True)
            st.caption(f"Fonte: {a.fonte or 'n/d'} · preços até {a.data_ref or 'data indisponível'}")

    with st.expander("O que influenciou cada pontuação"):
        for a in c.ativos:
            if a.pontuacao and a.pontuacao.influencias:
                comparador_app._cards_lista(a.pontuacao.influencias, "info", "🎯", f"{a.chave} — {a.pontuacao.metodo}")
    with st.expander("O que ainda não dá para comparar (sem fonte de dados)"):
        for cid in c.classes:
            if cl[cid].sem_fonte:
                st.markdown(f"**{cl[cid].nome}:** " + ", ".join(cl[cid].sem_fonte) + ".")
        st.markdown("**Ainda sem fonte no app:** contratos, inquilinos e carteira de CRIs dos FIIs e "
                    "renda fixa (base de títulos). Fundos de investimento entram pelo CNPJ (CVM). FIIs usam P/VP e vacância de hoje (Fundamentus) mais preço e rendimentos "
                    "(Yahoo); a nota é provisória. Compare FIIs da mesma estratégia: tijolo com tijolo, papel com papel.")
    st.caption(comparador.AVISO_LEGAL)


def _preparar_comparacao(codigos: list):
    """Guarda os códigos para a página Comparar abri-la já preenchida (e descarta a comparação anterior)."""
    st.session_state["cmp_pre"] = list(dict.fromkeys(normaliza(c) for c in codigos if c))[:CMP_MAX]
    st.session_state.pop("cmp_base", None)


def atalho_comparar(codigos: list, chave: str, rotulo: str = "Comparar com outros ativos"):
    """Botão que leva os ativos da tela atual para a página Comparar (usado na Carteira, ETFs e Análise Técnica)."""
    codigos = [c for c in codigos if c]
    if codigos and st.button(rotulo, key=f"cmp_atalho_{chave}", icon=":material/compare_arrows:",
                             on_click=_preparar_comparacao, args=(codigos,)):
        st.switch_page(PG_COMPARAR)


def _preparar_comparacao_cripto(ids: list):
    """Leva as moedas escolhidas para a página Comparar (o Streamlit apaga o estado de widgets fora da tela: o valor
    passa por chaves 'pre' e é aplicado lá)."""
    ids = list(dict.fromkeys(i for i in ids if i))[:CMP_MAX]
    st.session_state["cmp_pre_cripto"] = ids
    cur = st.session_state.setdefault("cripto_ativos", [])
    st.session_state.setdefault("cripto_nomes", {})
    for i in ids:
        if i not in cur:
            cur.append(i)


def atalho_comparar_cripto(ids: list):
    ids = [i for i in ids if i]
    if len(ids) >= 2 and st.button("Abrir no Comparador universal", key="cmp_atalho_cripto_av", icon=":material/compare_arrows:",
                                   on_click=_preparar_comparacao_cripto, args=(ids,)):
        st.switch_page(PG_COMPARAR)


def pagina_cripto_av_app():
    cripto_app.pagina_cripto_avancada(atalho_comparar_cripto)
    _bloco_intel(st.session_state.get("cripto_av_gid"), cripto=True)


def pagina_carteira_app():
    """Carteira (carteira.py, sem alteração) + atalho para comparar os ativos que estão nela."""
    carteira.pagina_carteira()
    tks = []
    for chave in ("cart_ficticia", "cart_real"):
        tks += [l.get("ticker") for l in st.session_state.get(chave, []) if isinstance(l, dict)]
    st.divider()
    atalho_comparar(list(dict.fromkeys(t for t in tks if t)), "carteira", "Comparar os ativos da minha carteira")
    lotes_fii = [l for chave in ("cart_ficticia", "cart_real") for l in st.session_state.get(chave, []) if isinstance(l, dict)]
    if lotes_fii:
        with st.expander("Análise dos FIIs da carteira", icon=":material/apartment:"):
            fiis_app.painel_carteira(lotes_fii)
    if any(cripto_app.simbolo_cripto(l.get("ticker")) for l in lotes_fii):
        with st.expander("Análise das criptomoedas da carteira", icon=":material/currency_bitcoin:"):
            cripto_app.painel_carteira(lotes_fii)
    with st.expander("Análise dos ETFs e fundos da carteira", icon=":material/stacked_line_chart:"):
        fundos_app.painel_carteira(lotes_fii)
    with st.expander("Renda fixa da carteira", icon=":material/savings:"):
        renda_fixa_app.painel_carteira_rf()
    uniq = list(dict.fromkeys(t for t in tks if t))
    if uniq:
        esc = st.selectbox("Ver evolução e crescimento de um ativo da carteira", uniq, key="cart_ev_sel")
        evolucao.atalho_evolucao(PG_EVOLUCAO, esc, "carteira", "Evolução e crescimento")
        st.page_link(PG_INTEL, label="Central de inteligência (oportunidades, riscos, notícias e alertas)", icon=":material/psychology:")
        _bloco_intel(esc)


def _coletar_para_intel(codigos: list, criptos: list, perfil: str) -> list:
    """Coletor da Central de inteligência: o MESMO caminho do Comparar (classificação, notas por classe e crescimento do Passo 7)."""
    sel = _classificar_selecao(list(codigos), [], list(criptos))
    return _enriquecer_crescimento(_montar_ativos(sel, perfil))


def pagina_intel_app():
    """Central de inteligência (intel_app.py, Passo 13): lê o que o app já sabe analisar e monitora. Só leitura; nada é negociado."""
    intel_app.pagina_intel(_coletar_para_intel, perfil_atual())


def _bloco_intel(codigo, cripto: bool = False):
    """Sinais, riscos e notícias de UM ativo dentro das páginas dele (usa a leitura da central ou analisa só este)."""
    if codigo:
        intel_app.painel_ativo(str(codigo), _coletar_para_intel, perfil_atual(), cripto=cripto)


def pagina_tecnica_avancada_app():
    """Análise técnica avançada (analise_tecnica_app.py, Passo 14). Só leitura: nada é negociado. Reaproveita a classificação de ativos,
    a Binance e a carteira do Passo 12; os dados vêm do Yahoo Finance (e da Binance em cripto)."""
    def _classe_de(cod):
        try:
            return _classificar_selecao([cod], [], [])[0][1]
        except Exception:
            return "acao"
    analise_tecnica_app.pagina_tecnica_avancada({
        "classe_de": _classe_de,
        "carteira": lambda: gestao_app.posicoes_para_tecnica("cart_real"),
        "binance_ohlcv": binance_ohlcv,
        "favoritos": lambda: list(st.session_state.get("sel_ativos", []) or [])[:10]})


def pagina_noticias_app():
    """Central de notícias e eventos (noticias_app.py, Passo 15). Só leitura: nada é negociado. Usa a carteira do Passo 12 e os favoritos."""
    def _ativos():
        out = {p["id"]: p for p in gestao_app.posicoes_para_noticias("cart_real")}
        for cod in list(st.session_state.get("sel_ativos", []) or [])[:10] + list(st.session_state.get("cripto_ativos", []) or [])[:5]:
            c = str(cod).strip().upper()
            if c and c not in out:
                try:
                    cl = _classificar_selecao([c], [], [])[0][1]
                except Exception:
                    cl = "acao"
                out[c] = {"id": c, "nome": c, "classe": cl, "setor": None, "subgrupo": None, "peso": 0}
        return list(out.values())

    def _rf():
        try:
            return [{"id": f"RF-{t.id}", "nome": t.nome or t.emissor or f"Título {t.id}", "vencimento": t.vencimento.isoformat()} for t in renda_fixa_app._titulos_carteira()]
        except Exception:
            return []
    noticias_app.pagina_noticias({"ativos": _ativos, "rf_vencimentos": _rf})


def pagina_risco_app():
    """Gestão de risco (risco_app.py, Passo 16): lê a carteira do Passo 12 e calcula risco por classe, VaR, concentração, correlação, liquidez, estresse e limites. Só leitura."""
    risco_app.pagina_risco()


def pagina_simulador_app():
    """Simulador financeiro (simulador_app.py, Passo 18): juros compostos, aposentadoria, renda passiva, metas, cenários, crises, carteira e histórico."""
    simulador_app.pagina_simulador()


def pagina_relatorios_app():
    """Relatórios e dashboard executivo (relatorios_app.py, Passo 19): lê a carteira do Passo 12; exporta PDF, Excel e CSV. Só leitura."""
    relatorios_app.pagina_relatorios()


def _indicadores_da_classe(classe: str, codigo: str):
    """Indicadores do ativo na régua da sua classe (mesmo caminho do Comparar, Passo 6), para o relatório individual do Passo 19."""
    if classe == "cripto":
        base = re.split(r"[-/]", str(codigo).strip().upper())[0]           # BNB-USD -> BNB (a carteira guarda SÍMBOLO-USD)
        gid, _nome = _gecko_do_par(base) if base else (None, None)         # a CoinGecko usa o id (binancecoin), não o símbolo
        if not gid:
            return comparador.Ativo(codigo, codigo, "cripto", erro=f"não achei {base} na CoinGecko agora")
        sel = _classificar_selecao([], [], [gid])
    else:
        sel = _classificar_selecao([codigo], [], [])
    ativos_ = _enriquecer_crescimento(_montar_ativos(sel, perfil_atual()))
    return ativos_[0] if ativos_ else None


relatorios_app.PROVEDOR_ATIVO = _indicadores_da_classe


def pagina_calculadoras_app():
    """Calculadoras (mercados.py) com atalho para o Simulador financeiro completo (Passo 18)."""
    mercados.pagina_calculadoras()
    st.divider()
    st.page_link(PG_SIM, label="Simulador financeiro completo (aposentadoria, renda passiva, metas, cenários, crises e carteira)", icon=":material/calculate:")


def pagina_gestao_app():
    """Gestão de carteira (gestao_app.py, Passo 12): lê a carteira da página Carteira, a renda fixa e os fundos por CNPJ. Só leitura e
    simulação. Os atalhos levam os mesmos ativos ao Comparador universal (Passo 6) e à Evolução e crescimento (Passo 7)."""
    gestao_app.pagina_gestao()
    cods = []
    for chave in ("cart_real", "cart_ficticia"):
        cods += [l.get("ticker") for l in st.session_state.get(chave, []) if isinstance(l, dict)]
    try:
        cods += [renda_fixa_app.codigo_de(t) for t in renda_fixa_app._titulos_carteira()]
    except Exception:
        pass
    cods = list(dict.fromkeys(c for c in cods if c))
    if cods:
        st.divider()
        atalho_comparar(cods, "gestao", "Comparar os ativos da minha carteira")
        so_bolsa = [c for c in cods if not str(c).upper().startswith(("RF-", "TD-"))]
        if so_bolsa:
            esc = st.selectbox("Ver evolução e crescimento de um ativo da carteira", so_bolsa, key="gestao_ev_sel")
            evolucao.atalho_evolucao(PG_EVOLUCAO, esc, "gestao", "Evolução e crescimento")
    st.page_link(PG_INTEL, label="Monitoramento inteligente da carteira (notícias, alertas e o que mudou)", icon=":material/psychology:")
    st.page_link(PG_NOTICIAS, label="Notícias, eventos e calendário dos ativos da carteira", icon=":material/newspaper:")
    st.page_link(PG_RISCO, label="Risco da carteira (nota por classe, VaR, estresse, limites e tamanho de posição)", icon=":material/shield:")
    st.page_link(PG_REL, label="Relatórios e dashboard (rentabilidade, exportação em PDF, Excel e CSV, histórico)", icon=":material/monitoring:")
    st.page_link(PG_TEC_AV, label="Situação técnica da carteira (tendências, riscos e alertas técnicos)", icon=":material/candlestick_chart:")
    if cods:
        _bloco_intel(st.selectbox("Sinais e notícias de um ativo da carteira", cods, key="gestao_intel_sel"))
    st.caption("Análises detalhadas de FIIs, criptomoedas, ETFs, fundos e renda fixa da carteira: página Carteira.")


def _atalho_ev(cod, ch, rot):
    evolucao.atalho_evolucao(PG_EVOLUCAO, cod, ch, rot)


def pagina_etfs_app():
    """ETFs (fundos_app.py, Passo 10): 10 abas com classificação, custos, tracking, risco, carteira e comparação."""
    fundos_app.pagina_etfs(atalho_comparar=atalho_comparar, atalho_evolucao=_atalho_ev, botao_carteira=botao_carteira)


def pagina_fundos_acoes_app():
    fundos_app.pagina_fundos("acoes", atalho_comparar=atalho_comparar)


def pagina_multimercados_app():
    fundos_app.pagina_fundos("multi", atalho_comparar=atalho_comparar)


def pagina_fundos_rf_app():
    fundos_app.pagina_fundos("rf", atalho_comparar=atalho_comparar)


def pagina_renda_fixa_app():
    """Renda fixa (renda_fixa_app.py, Passo 11): Tesouro Direto com preço oficial e títulos privados informados pelo usuário."""
    renda_fixa_app.pagina_renda_fixa(atalho_comparar=atalho_comparar)


def pagina_comparar():
    cabecalho("🧭", "Comparar ativos",
              "Compare ações, ETFs e criptomoedas com indicadores próprios de cada classe. Misturar classes só usa critérios comuns.")
    perfil = perfil_atual()
    secao = st.segmented_control("O que comparar", ["Ativos", "Carteiras"], default="Ativos", key="cmp_secao", label_visibility="collapsed") or "Ativos"
    if secao == "Carteiras":
        comparador_app.pagina_carteiras()                 # Passo 20: duas ou mais carteiras (real, fictícia e modelos)
        return
    pre = st.session_state.pop("cmp_pre", None)          # vindo de um atalho (Carteira, ETFs, Análise Técnica)
    pre_c = st.session_state.pop("cmp_pre_cripto", None)  # vindo da página de criptomoedas (Passo 9)
    if pre or pre_c:
        st.session_state["cmp_acoes"], st.session_state["cmp_outros"], st.session_state["cmp_cripto"] = list(pre or []), "", list(pre_c or [])
    base = list(dict.fromkeys(st.session_state.get("sel_ativos", []) + rec.TODOS_TICKERS))
    st.session_state.setdefault("cmp_acoes", [t for t in st.session_state.get("sel_ativos", []) if t in base][:CMP_MAX])
    st.session_state.setdefault("cmp_outros", normaliza(st.session_state.get("fa_etf_q") or st.session_state.get("eua_q") or "") if (st.session_state.get("fa_etf_q") or st.session_state.get("eua_q")) else "")
    cripto_ops = list(dict.fromkeys(st.session_state.get("cripto_ativos", []) + list(cripto.POPULARES.values())))
    nomes = {**{v: k for k, v in cripto.POPULARES.items()}, **st.session_state.get("cripto_nomes", {})}
    st.session_state.setdefault("cmp_cripto", [g for g in st.session_state.get("cripto_ativos", [])][:CMP_MAX])
    c1, c2 = st.columns(2)
    acoes = c1.multiselect("Ações (ou qualquer código da bolsa)", base, key="cmp_acoes", format_func=rec.rotulo,
                           accept_new_options=True, placeholder="Ex.: ITUB4, BBDC4, AAPL")
    outros = c2.text_input("ETFs e outros códigos", key="cmp_outros", placeholder="Ex.: BOVA11, VOO, HGLG11, CNPJ de fundo ou TD-IPCA-2035",
                           help="O app identifica a classe pelo código. Fundos de investimento: o CNPJ (dados da CVM). Renda fixa: "
                                "TD-IPCA-2035, TD-SELIC-2029, TD-PRE-2031 (Tesouro Direto) ou RF-<código> de um título salvo em "
                                "Análise de títulos.")
    criptos = st.multiselect("Criptomoedas", cripto_ops, key="cmp_cripto", placeholder="Ex.: Bitcoin, Ethereum",
                             format_func=lambda g: nomes.get(g) or g.replace("-", " ").title())
    lista_outros = [x for x in re.split(r"[,\s;]+", outros or "") if x]
    sel = _classificar_selecao(acoes, lista_outros, criptos)
    if len(sel) > CMP_MAX:
        st.caption(f"Comparando os {CMP_MAX} primeiros de {len(sel)} ativos, para respeitar os limites das fontes de dados.")
        sel = sel[:CMP_MAX]
    import planos                                                # Etapa 10: ativos no comparador conforme o plano
    lim_plano, nome_plano = planos.limite_atual("comparador_ativos")
    if len(sel) > lim_plano:
        st.caption(f"O plano {nome_plano} compara até {lim_plano} ativos por vez. Comparando os {lim_plano} primeiros de {len(sel)}.")
        sel = sel[:lim_plano]
    if sel:
        st.caption("Classe identificada: " + " · ".join(f"{t} → {comparador.CLASSES[c].nome}" for t, c in sel))
    if len(sel) < 2:
        st.info("Escolha pelo menos 2 ativos para comparar. Dá para misturar classes: nesse caso só os critérios comuns entram.")
        return
    cresc = st.checkbox("Incluir crescimento histórico (CAGR de 3 anos de preço, receita, lucro, caixa e dividendos)",
                        key="cmp_cresc", help="Não altera as notas; só acrescenta linhas na tabela. Demora um pouco mais.")
    chave = (tuple(sel), perfil, st.session_state.get("fonte_dados"), bool(cresc))
    if st.button("🔍 Comparar", type="primary"):
        with st.spinner("Coletando os dados de cada ativo..."):
            ativos_ = _montar_ativos(sel, perfil)
            if cresc:
                ativos_ = _enriquecer_crescimento(ativos_)
            st.session_state["cmp_base"] = {"chave": chave, "ativos": ativos_}
    cb = st.session_state.get("cmp_base")
    if not cb or cb["chave"] != chave:
        st.info("Toque em **Comparar** para buscar os dados e montar a comparação.")
        return
    comp_ = comparador.comparar(cb["ativos"], extras=comparador.SPECS_CRESCIMENTO if cresc else None)
    _mostrar_comparacao(comp_, perfil)
    comparador_app.pagina_avancada(cb["ativos"], sel, comp_)      # Passo 20: desempenho, risco, pontuação histórica, IA e exportação


# ---------------------------------------------------------------- página: ajuda
def pagina_ajuda():
    cabecalho("❓", "Ajuda", "Tutoriais de cada página, seu aprendizado, termos e diagnóstico das fontes de dados.")
    secoes = ["Tutoriais", "Meu aprendizado", "Termos básicos", "Fontes de dados"]
    aba = st.segmented_control("Seção", secoes, default=secoes[0], key="ajuda_aba",
                               label_visibility="collapsed") or secoes[0]
    if aba == "Tutoriais":
        ajuda_app.tutoriais_da_central()
    elif aba == "Meu aprendizado":
        ajuda_app.meu_aprendizado(PG_INICIO)
    elif aba == "Termos básicos":
        termos_basicos()
        st.write("")
        k = st.selectbox("Procure qualquer termo do app", sorted(GLOSSARIO), index=None,
                         placeholder="Ex.: P/L, ROE, Margem de segurança...")
        if k:
            explica(k)
            educacao_app.explicador(k, "ajuda")      # explicação completa (Passo 24), só se o termo for um indicador conhecido
    else:
        diagnostico_fontes()


# ---------------------------------------------------------------- páginas: analisar (fundamentalista)
def pagina_preco_justo():
    cabecalho("🎯", "Preço justo",
              "Dois métodos, cada um com o seu resultado: Graham (lucro e patrimônio) e Bazin (dividendos).")
    dados = dados_ativos(perfil=True)
    if not dados:
        return
    resumo_acoes("pj", dados)
    perfil = perfil_atual()
    P = PERFIS[perfil]
    yield_alvo, margem_alvo = float(P["yield_alvo"]), int(P["margem_alvo"])

    calc = {tk: (graham_calc(d, margem_alvo), bazin_calc(d, yield_alvo, margem_alvo)) for tk, d in dados.items()}
    t_painel, t_comp = st.tabs(["Painel", "Comparativo"])

    with t_painel:
        experiencia_app.mostrar_varios([LT.preco_justo(
            rec.nome_curto(tk), d.get("preco"), calc[tk][0]["justo"], calc[tk][1]["justo"], calc[tk][0]["margem"], calc[tk][1]["margem"],
            margem_alvo, d.get("lpa"), d.get("vpa"), base_bazin(d)[0], yield_alvo, experiencia_app.modo()) for tk, d in dados.items()])
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
                    md(tema.barra_margem(c["margem"]))

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
    resumo_acoes("val", dados)
    barra_carteira(dados, "val")
    linhas = []
    for tk, d in dados.items():
        m = multiplos(d)
        linhas.append({"Ticker": tk, "Preço": d["preco"], "P/L": m["pl"], "P/VP": m["pvp"],
                       "EV/EBITDA": d["ev_ebitda"], "DY 12m (%)": m["dy"], "ROE (%)": m["roe"],
                       "Margem líq. (%)": m["margem"], "Dív./PL (%)": d["div_pl"]})
    df = pd.DataFrame(linhas)
    experiencia_app.mostrar_varios([LT.multiplos(rec.nome_curto(l["Ticker"]), l["Preço"], l["P/L"], l["P/VP"], l["DY 12m (%)"], l["ROE (%)"],
                                                 l["Margem líq. (%)"], l["Dív./PL (%)"], l["EV/EBITDA"], experiencia_app.modo()) for l in linhas])
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
    _todas = [c for c in df.columns if c not in ("Ticker", "Preço")]
    _mostrar = EXP.colunas_indicadores(_todas, st.session_state.get("prefs"))
    _df_exib = df[["Ticker", "Preço"] + _mostrar] if "Preço" in df.columns else df[["Ticker"] + _mostrar]
    _d1, _f1 = experiencia_app.rotular_df(_df_exib, fmts)
    st.dataframe(estilizar(_d1, _f1), width="stretch", hide_index=True, column_config=cfg_ajuda(_d1))
    if len(_mostrar) < len(_todas):
        with st.expander("Ver todos os indicadores"):
            _d2, _f2 = experiencia_app.rotular_df(df, fmts)
            st.dataframe(estilizar(_d2, _f2), width="stretch", hide_index=True, column_config=cfg_ajuda(_d2))


def pagina_dividendos():
    cabecalho("💰", "Dividendos", "Quanto a empresa repartiu com os sócios e quanto isso rendeu sobre o preço (DY).")
    dados = dados_ativos()
    if not dados:
        return
    resumo_acoes("div", dados)
    barra_carteira(dados, "div")
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
    experiencia_app.mostrar_varios([LT.dividendos(rec.nome_curto(l["Ticker"]), dados[l["Ticker"]].get("preco"), l["Proventos 12m"], l["Média 5 anos"],
                                                  l["DY 12m (%)"], l["DY s/ média 5a (%)"], experiencia_app.modo()) for l in linhas])
    _dd, _fd = experiencia_app.rotular_df(df_div, {"Proventos 12m": brl, "Média 5 anos": brl, "DY 12m (%)": pct, "DY s/ média 5a (%)": pct})
    st.dataframe(estilizar(_dd, _fd), width="stretch", hide_index=True, column_config=cfg_ajuda(_dd))


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
    dados = dados_ativos(perfil=True)
    if not dados:
        return
    tk = st.selectbox("Ativo", list(dados), key="dcf_ativo", format_func=rec.rotulo)
    d = dados[tk]
    botao_carteira(tk, d.get("preco"), "_dcf")
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

    experiencia_app.mostrar_varios([LT.dcf(rec.nome_curto(tk), preco, res["valor"], margem, potencial, res["pct_terminal"], taxa, g, gp, horizonte, base,
                                           experiencia_app.modo())])
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
    st.page_link(PG_COMPARAR, label="Comparar ativos lado a lado (ações, ETFs, cripto)", icon=":material/compare_arrows:")
    st.page_link(PG_EVOLUCAO, label="Evolução e crescimento (balanços, CAGR)", icon=":material/timeline:")
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
            st.warning("Não consegui dados para essas empresas agora. Tente de novo ou troque a fonte em Ajustes (menu lateral).")
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
    experiencia_app.mostrar_varios([LT.ranking([{"nome": rec.nome_curto(r_["Ativo"]), "nota": r_["Nota"], "pilares": {p_: r_[p_] for p_ in PILARES}}
                                                for _, r_ in df.iterrows()], perfil, experiencia_app.modo())], "Leitura do ranking")
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
            a.markdown(f'<img class="logo" src="{html.escape(str(logos.get(rec.normalizar_ticker(r["ticker"])) or ""), quote=True)}" '
                       f'width="44" height="44">', unsafe_allow_html=True)
            b.markdown(f"**{html.escape(str(r['nome']))}**  \n<span style='color:{MUTED};font-size:.8rem'>{html.escape(r['setor'])}</span>",
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
    """Página Economia (inteligência econômica): ver macro_app.py. A versão anterior continua abaixo, sem uso, como referência."""
    macro_app.pagina(cabecalho, md, PLOT, GRID)


def _pagina_macro_anterior():
    cabecalho("🌐", "Cenário econômico",
              "Juros, inflação, dólar, atividade e desemprego influenciam o preço das ações.")
    anos = st.segmented_control("Período", [1, 2, 5, 10], default=2,
                                format_func=lambda x: f"{x} ano{'s' if x > 1 else ''}", key="macro_anos") or 2
    painel_assistente(anos)

    def _ult(cod):
        try:
            df_ = buscar_macro_bcb(cod, 10)
            return float(df_["valor"].iloc[-1]) if df_ is not None and len(df_) else None
        except Exception:
            return None
    experiencia_app.mostrar_varios([LT.macro(_ult(432), _ult(13522), _ult(1), _ult(24369), experiencia_app.modo())], "Leitura da economia")
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


def resumo_acoes(chave: str, dados: dict):
    """Resumo executivo (IA ou regras) das ações selecionadas; usado nas páginas de análise fundamentalista."""
    if st.session_state.get("_embutido"):
        return
    assistente.painel_resumo_executivo(
        dados, rec.nome_curto, lambda d: {**multiplos(d), "financeira": eh_financeiro(d["ticker"])}, chave)


def pagina_micro():
    cabecalho("🏢", "Saúde financeira", "Lucro, dívida e rentabilidade (ROE) mostram se a empresa está forte.")
    dados = dados_ativos()
    if not dados:
        return
    resumo_acoes("micro", dados)
    barra_carteira(dados, "micro")
    linhas = []
    for tk, d in dados.items():
        m = multiplos(d)
        linhas.append({"Ativo": tk, "Preço": d.get("preco"), "LPA": d.get("lpa"), "VPA": d.get("vpa"),
                       "EV/EBITDA": d.get("ev_ebitda"), "DY 12m (%)": m["dy"], "ROE (%)": m["roe"],
                       "Margem líq. (%)": m["margem"], "Dív./PL (%)": d.get("div_pl")})
    df = pd.DataFrame(linhas)
    experiencia_app.mostrar_varios([LT.saude(rec.nome_curto(l["Ativo"]), l["LPA"], l["VPA"], l["ROE (%)"], l["Margem líq. (%)"], l["Dív./PL (%)"],
                                             l["DY 12m (%)"], experiencia_app.modo()) for l in linhas])
    _dm, _fm = experiencia_app.rotular_df(df, {"Preço": brl, "LPA": brl, "VPA": brl, "EV/EBITDA": num, "DY 12m (%)": pct,
                                               "ROE (%)": pct, "Margem líq. (%)": pct, "Dív./PL (%)": pct})
    st.dataframe(estilizar(_dm, _fm), width="stretch", hide_index=True, column_config=cfg_ajuda(_dm))
    st.caption("LPA e VPA em R$ (balanços em dólar são convertidos automaticamente). "
               "ROE e margens em %, Dív./PL em % do patrimônio.")


# ---------------------------------------------------------------- página: técnica
# ---------------------------------------------------------------- página: análise gráfica (Binance via ccxt)
# Preços, velas e gráfico vêm SÓ da Binance (ccxt). Os indicadores usam pandas-ta; se o pandas-ta não carregar
# (versões antigas quebram com numpy 2), o mesmo cálculo é feito direto em pandas. A parte fundamentalista
# (Market Cap, FDV, circulação) continua na CoinGecko/DefiLlama, na página Criptomoedas.
try:
    import ccxt
except ImportError:  # sem ccxt a página mostra o aviso em vez de derrubar o app
    ccxt = None
_pta = None
for _nome_pta in ("pandas_ta", "pandas_ta_classic"):
    try:
        _pta = __import__(_nome_pta)
        break
    except Exception:
        continue

# Binance bloqueia alguns países (ex.: EUA, onde o Streamlit Cloud costuma rodar) no endereço padrão.
# O endereço data-api.binance.vision serve só dados públicos de mercado e costuma funcionar nesses casos.
BINANCE_HOSTS = ["https://data-api.binance.vision/api/v3", None]  # None = endereço padrão do ccxt
TIMEFRAMES = {"1 min": "1m", "5 min": "5m", "15 min": "15m", "1 hora": "1h", "4 horas": "4h",
              "Diário": "1d", "Semanal": "1w"}
COTACOES = ("USDT", "USDC", "FDUSD", "BRL", "BTC", "ETH", "BNB")
PARES_POPULARES = ["BTC/USDT", "ETH/USDT", "SOL/USDT", "BNB/USDT", "XRP/USDT", "ADA/USDT", "DOGE/USDT",
                   "RENDER/USDT", "LINK/USDT", "AVAX/USDT", "BTC/BRL", "ETH/BRL"]


def _chaves_binance():
    """(chave, segredo) da Binance lidos dos secrets do Streamlit (ou variáveis de ambiente). Nunca ficam no código.
    Aceita BINANCE_API_KEY/BINANCE_API_SECRET no topo, ou um bloco [binance] com api_key e api_secret."""
    import os
    k = s = ""
    try:
        sec = st.secrets
        k = sec.get("BINANCE_API_KEY") or (sec.get("binance") or {}).get("api_key") or ""
        s = sec.get("BINANCE_API_SECRET") or (sec.get("binance") or {}).get("api_secret") or ""
    except Exception:
        pass
    k = k or os.environ.get("BINANCE_API_KEY", "")
    s = s or os.environ.get("BINANCE_API_SECRET", "")
    return cripto._limpa_chave(k), cripto._limpa_chave(s)


def _nova_exchange(host, chave=""):
    cfg = {"enableRateLimit": True, "timeout": 15000, "options": {"defaultType": "spot"}}
    if host:
        cfg["urls"] = {"api": {"public": host}}
    if chave:  # a chave (só ela, nunca o segredo) vai no cabeçalho de todas as consultas de dados de mercado
        cfg["headers"] = {"X-MBX-APIKEY": chave}
    ex = ccxt.binance(cfg)
    ex.options["defaultType"] = "spot"
    fm = ex.options.get("fetchMarkets")  # só mercado à vista: futuros são bloqueados em vários países
    if isinstance(fm, dict):
        fm["types"] = ["spot"]
    else:
        ex.options["fetchMarkets"] = ["spot"]
    try:
        ex.has["fetchCurrencies"] = False  # essa chamada exige chave de API
    except Exception:
        pass
    return ex


@st.cache_resource(ttl=6 * 3600, show_spinner=False)
def binance_exchange():
    """Conexão com a Binance para dados de mercado (velas, cotações, lista de pares). Usa a chave de API quando ela
    existe nos secrets; se a Binance recusar a chave, tenta sem ela. Testa os endereços em ordem."""
    chave, _ = _chaves_binance()
    ultimo = None
    for host in BINANCE_HOSTS:
        for k in ([chave, ""] if chave else [""]):
            try:
                ex = _nova_exchange(host, k)
                ex.load_markets()
                ex.options["_com_chave"] = bool(k)
                return ex
            except Exception as e:
                ultimo = e
    raise ultimo


def binance_simbolos(ex) -> list[str]:
    """Pares à vista ativos nas cotações mais usadas, com os populares primeiro."""
    todos = {s for s, m in ex.markets.items()
             if m.get("spot") and m.get("active", True) and m.get("quote") in COTACOES}
    resto = sorted(todos - set(PARES_POPULARES))
    return [p for p in PARES_POPULARES if p in todos] + resto


def normaliza_par(texto: str, simbolos: set):
    """Aceita btc, BTCUSDT, btc/usdt, render/usdt… e devolve BASE/COTAÇÃO. Sem cotação, assume USDT."""
    s = re.sub(r"[^A-Za-z0-9/]", "", texto or "").upper().strip("/")
    if not s:
        return None
    if "/" in s:
        base, cot = s.split("/", 1)
        return f"{base}/{cot}"
    for q in COTACOES:
        if s.endswith(q) and len(s) > len(q) and f"{s[:-len(q)]}/{q}" in simbolos:
            return f"{s[:-len(q)]}/{q}"
    return f"{s}/USDT"


@st.cache_data(ttl=15, show_spinner=False)
def binance_ohlcv(par: str, timeframe: str, limite: int) -> pd.DataFrame:
    """Velas (OHLCV) da Binance. Horário de Brasília."""
    raw = binance_exchange().fetch_ohlcv(par, timeframe=timeframe, limit=int(limite))
    df = pd.DataFrame(raw, columns=["ts", "Open", "High", "Low", "Close", "Volume"])
    idx = pd.to_datetime(df.pop("ts"), unit="ms", utc=True).dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
    df.index = pd.DatetimeIndex(idx, name="Data")
    return df.astype(float)


@st.cache_data(ttl=10, show_spinner=False)
def binance_ticker(par: str) -> dict:
    """Cotação em tempo real: último preço, variação e extremos de 24h, volume."""
    t = binance_exchange().fetch_ticker(par)
    return {k: t.get(k) for k in ("last", "percentage", "high", "low", "quoteVolume", "baseVolume", "timestamp")}


def indicadores_cripto(df: pd.DataFrame) -> pd.DataFrame:
    """SMA 20 e 50, IFR (RSI) 14 e Bandas de Bollinger (20, 2). Usa pandas-ta; sem ele, o mesmo cálculo em pandas."""
    c = df["Close"]
    if _pta is not None:
        try:
            out = pd.DataFrame(index=df.index)
            out["SMA20"] = _pta.sma(c, length=20)
            out["SMA50"] = _pta.sma(c, length=50)
            out["RSI14"] = _pta.rsi(c, length=14)
            bb = _pta.bbands(c, length=20, std=2)
            for nome, pref in (("BBL", "BBL"), ("BBM", "BBM"), ("BBU", "BBU")):
                out[nome] = bb[[col for col in bb.columns if col.startswith(pref)][0]]
            out.attrs["motor"] = "pandas-ta"
            return out
        except Exception:
            pass
    out = pd.DataFrame(index=df.index)
    out["SMA20"], out["SMA50"] = c.rolling(20).mean(), c.rolling(50).mean()
    d = c.diff()
    ganho = d.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    perda = (-d.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    out["RSI14"] = 100 - 100 / (1 + ganho / perda.where(perda != 0))
    out["BBM"] = c.rolling(20).mean()
    desvio = c.rolling(20).std(ddof=0)
    out["BBU"], out["BBL"] = out["BBM"] + 2 * desvio, out["BBM"] - 2 * desvio
    out.attrs["motor"] = "pandas"
    return out


def _fmt_preco(v) -> str:
    if v is None or pd.isna(v):
        return "n/d"
    v = float(v)
    casas = 2 if abs(v) >= 100 else 3 if abs(v) >= 10 else 4 if abs(v) >= 1 else 6 if abs(v) >= 0.01 else 8
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def figura_cripto(df: pd.DataFrame, ind: pd.DataFrame, altura: int = 720, visiveis: int = 150,
                  sinais=None, zonas=None):
    """Candlestick interativo (Plotly) no estilo TradingView: velas, SMA 20/50, Bandas de Bollinger, volume e IFR."""
    from plotly.subplots import make_subplots
    t = tec.TV["claro"]
    x, n = df.index, len(df)
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.66, 0.14, 0.20], vertical_spacing=0.012)
    # Bandas de Bollinger: linhas finas e faixa sombreada entre elas
    fig.add_trace(go.Scatter(x=x, y=ind["BBU"], mode="lines", line=dict(color=t["ifr"], width=1), showlegend=False,
                             hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Scatter(x=x, y=ind["BBL"], mode="lines", line=dict(color=t["ifr"], width=1), showlegend=False,
                             fill="tonexty", fillcolor="rgba(126,87,194,.07)", hoverinfo="skip"), row=1, col=1)
    fig.add_trace(go.Candlestick(
        x=x, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing=dict(line=dict(color=t["alta"], width=1), fillcolor=t["alta"]),
        decreasing=dict(line=dict(color=t["baixa"], width=1), fillcolor=t["baixa"]),
        whiskerwidth=0, showlegend=False, name="Preço"), row=1, col=1)
    legenda = []
    for col, nome, cor in (("SMA20", "SMA 20", t["mm1"]), ("SMA50", "SMA 50", t["mm2"])):
        fig.add_trace(go.Scatter(x=x, y=ind[col], mode="lines", line=dict(color=cor, width=1.4), showlegend=False,
                                 hoverinfo="skip"), row=1, col=1)
        ult = ind[col].dropna()
        if len(ult):
            legenda.append(f"<span style='color:{cor}'>● {nome} {_fmt_preco(ult.iloc[-1])}</span>")
    legenda.append(f"<span style='color:{t['ifr']}'>● Bollinger (20, 2)</span>")

    # sinais atuais (só os últimos candles): triângulos encostados na vela, texto no hover
    ampl = float((df["High"] - df["Low"]).tail(30).mean()) or float(df["Close"].iloc[-1]) * 0.01
    estilos = {"alta": ("triangle-up", t["alta"], -1), "baixa": ("triangle-down", t["baixa"], 1),
               "neutro": ("diamond", t["neutro"], 1)}
    for tipo, (simb, cor, sgn) in estilos.items():
        pts = [s for s in (sinais or []) if s["tipo"] == tipo]
        if pts:
            fig.add_trace(go.Scatter(
                x=[p["data"] for p in pts], y=[p["preco"] + sgn * 0.45 * ampl for p in pts], mode="markers",
                showlegend=False, customdata=[p["sinal"] for p in pts],
                marker=dict(symbol=simb, size=10, color=cor, line=dict(width=1, color=t["bg"])),
                hovertemplate="<b>%{customdata}</b><br>%{x|%d/%m/%Y %H:%M}<extra></extra>"), row=1, col=1)
    for z in (zonas or []):
        fig.add_shape(type="rect", x0=z["x0"], x1=z["x1"], y0=z["y0"], y1=z["y1"], line=dict(width=0), layer="below",
                      fillcolor=t["zona_a"] if z["tipo"] == "alta" else t["zona_b"], row=1, col=1)

    ult, ab = float(df["Close"].iloc[-1]), float(df["Open"].iloc[-1])
    cor_ult = t["alta"] if ult >= ab else t["baixa"]
    fig.add_hline(y=ult, row=1, col=1, line=dict(color=cor_ult, width=1, dash="dot"))
    fig.add_annotation(xref="paper", x=1, yref="y", y=ult, text=f"<b>{_fmt_preco(ult)}</b>", showarrow=False,
                       xanchor="left", xshift=2, bgcolor=cor_ult, font=dict(color="#ffffff", size=11), borderpad=3)

    sobe = (df["Close"] >= df["Open"]).to_numpy()
    fig.add_trace(go.Bar(x=x, y=df["Volume"], marker=dict(color=[t["vol_a"] if s else t["vol_b"] for s in sobe]),
                         showlegend=False, hovertemplate="Vol. %{y:,.2f}<extra></extra>"), row=2, col=1)
    fig.add_hrect(y0=30, y1=70, fillcolor=t["faixa"], line_width=0, row=3, col=1)
    for nivel in (30, 70):
        fig.add_hline(y=nivel, row=3, col=1, line=dict(color=t["muted"], width=1, dash="dash"))
    fig.add_trace(go.Scatter(x=x, y=ind["RSI14"], mode="lines", showlegend=False, line=dict(color=t["ifr"], width=1.4),
                             hovertemplate="IFR %{y:.1f}<extra></extra>"), row=3, col=1)
    r = ind["RSI14"].dropna()
    if len(r):
        fig.add_annotation(xref="x domain", yref="y3 domain", x=0.005, y=0.95, showarrow=False, xanchor="left",
                           yanchor="top", font=dict(size=11, color=t["ifr"]), text=f"IFR 14 · {r.iloc[-1]:.1f}")
    fig.add_annotation(xref="x domain", yref="y2 domain", x=0.005, y=0.95, showarrow=False, xanchor="left",
                       yanchor="top", font=dict(size=11, color=t["muted"]), text="Volume")
    fig.add_annotation(xref="x domain", yref="y domain", x=0.005, y=0.995, showarrow=False, xanchor="left",
                       yanchor="top", align="left", font=dict(size=12, color=t["texto"]), text="  ".join(legenda))

    fig.update_layout(height=altura, paper_bgcolor=t["bg"], plot_bgcolor=t["bg"], showlegend=False,
                      font=dict(color=t["texto"], size=12, family="Inter, -apple-system, 'Segoe UI', Roboto, sans-serif"),
                      margin=dict(l=8, r=72, t=8, b=8), xaxis_rangeslider_visible=False, bargap=0.15,
                      dragmode="pan", hovermode="x", spikedistance=-1,
                      hoverlabel=dict(bgcolor=t["bg"], bordercolor=t["borda"], font=dict(color=t["texto"], size=12)))
    ini = max(0, n - visiveis)  # janela inicial; o resto fica disponível arrastando
    vis = slice(ini, n)
    lo = min(float(df["Low"].iloc[vis].min()), float(ind["BBL"].iloc[vis].min(skipna=True) if ind["BBL"].iloc[vis].notna().any() else 1e300))
    hi = max(float(df["High"].iloc[vis].max()), float(ind["BBU"].iloc[vis].max(skipna=True) if ind["BBU"].iloc[vis].notna().any() else -1e300))
    folga = (hi - lo) * 0.06
    passo = x.to_series().diff().median() if n > 2 else pd.Timedelta(hours=1)
    fig.update_xaxes(range=[x[ini], x[-1] + passo * 6], showgrid=True, gridcolor=t["grade"], zeroline=False,
                     showline=True, linecolor=t["borda"], tickfont=dict(color=t["muted"], size=11),
                     showspikes=True, spikemode="across", spikesnap="cursor", spikecolor=t["muted"],
                     spikethickness=1, spikedash="dash")
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_yaxes(side="right", showgrid=True, gridcolor=t["grade"], zeroline=False, showline=True,
                     linecolor=t["borda"], tickfont=dict(color=t["muted"], size=11), showspikes=True,
                     spikemode="across", spikecolor=t["muted"], spikethickness=1, spikedash="dash")
    fig.update_yaxes(range=[lo - folga, hi + folga], row=1, col=1)
    fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], row=3, col=1)
    fig.update_yaxes(tickformat=".2s", row=2, col=1)
    return fig






TV_INTERVALOS = {"1m": "1", "5m": "5", "15m": "15", "1h": "60", "4h": "240", "1d": "D", "1w": "W"}


def tradingview_cripto(par: str, intervalo_binance: str, altura: int = 640):
    """Gráfico do TradingView para um par da Binance (ex.: BINANCE:BTCUSDT), com SMA, Bollinger, volume e IFR.
    O gráfico carrega direto no navegador de quem usa o app, então funciona mesmo se o servidor do app estiver
    num país bloqueado pela Binance."""
    simbolo = "BINANCE:" + par.replace("/", "")
    cfg = {"autosize": True, "symbol": simbolo, "interval": TV_INTERVALOS.get(intervalo_binance, "D"),
           "timezone": "America/Sao_Paulo", "theme": "dark", "style": "1", "locale": "br",
           "enable_publishing": False, "hide_side_toolbar": False, "allow_symbol_change": False,
           "withdateranges": True, "save_image": True, "backgroundColor": "#110C2E", "toolbar_bg": "#110C2E",
           "gridColor": "rgba(160,174,192,0.12)", "container_id": "tv_cripto",
           "studies": ["MASimple@tv-basicstudies", "BB@tv-basicstudies", "Volume@tv-basicstudies",
                       "RSI@tv-basicstudies"]}
    incorporar.html(st, f"""
<style>html,body{{margin:0;background:#110C2E;}}</style>
<div style="height:{altura}px;width:100%;"><div id="tv_cripto" style="height:100%;width:100%;"></div></div>
<script src="https://s3.tradingview.com/tv.js"></script>
<script>new TradingView.widget({json.dumps(cfg)});</script>""", altura)




def _bloco_tendencia(r: dict, titulo: str, preco_txt: str = ""):
    """Card-veredito (mesmo padrão dos cards de valuation) + os sinais calculados, um card por sinal."""
    selo, cls = tendencia.SELO[r["veredito"]]
    cor = {"good": GOOD, "fair": FAIR, "bad": BAD}.get(cls, MUTED)
    linhas = [("Veredito", selo, "Tendência", cor)]
    if preco_txt:
        linhas.append(("Preço", preco_txt, None, None))
    linhas.append(("Candles analisados", str(r["candles"]), None, None))
    if r["placar"] is not None:
        linhas.append(("Placar (−1 a +1)", f"{r['placar']:+.2f}".replace(".", ","), None, cor))
    experiencia_app.mostrar(LT.tendencia(titulo, r["veredito"], r["placar"], r["alta"], r["baixa"], r["neutros"], experiencia_app.modo()))
    _card_resumo(titulo=f"Tendência · {titulo}", icone="📉", status=selo, cls=cls, cor_borda=cor, linhas=linhas,
                 nota=tendencia.resumo_texto(r),
                 aviso="Indicadores técnicos medem o passado e podem errar; não são recomendação." if r["veredito"] else "")
    sinais = r["sinais"]
    for i in range(0, len(sinais), 3):
        for col, x in zip(st.columns(3), sinais[i:i + 3]):
            peso = f" · peso {x['peso']:g}" if x["peso"] else " · informativo"
            col.markdown(tema.card_status(x["nome"], x["valor"], x["status"], x["leitura"] + peso), unsafe_allow_html=True)


EUA_POPULARES = ["AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "TSLA", "JPM", "KO", "XOM"]


@st.cache_data(ttl=900, show_spinner=False)
def _hist_eua(ticker: str, periodo: str, intervalo: str) -> pd.DataFrame:
    """Histórico de ação americana (NYSE/Nasdaq) direto no Yahoo, sem o sufixo .SA da B3. Erros não ficam em cache."""
    import yfinance as yf
    df = yf.Ticker(ticker).history(period=periodo, interval=intervalo, auto_adjust=True)
    if df is None or df.empty:
        raise ValueError("sem dados")
    return df[["Open", "High", "Low", "Close", "Volume"]].dropna(subset=["Close"])


def _tendencia_acao():
    """Ação da B3 ou da NYSE/Nasdaq: histórico do Yahoo/Brapi, veredito e gráfico com médias e IFR."""
    bolsa = st.segmented_control("Bolsa", ["B3 (Brasil)", "NYSE e Nasdaq (EUA)"], default="B3 (Brasil)",
                                 key="tec_bolsa", label_visibility="collapsed") or "B3 (Brasil)"
    eua = bolsa.startswith("NYSE")
    c1, c2 = st.columns([3, 1.4], vertical_alignment="bottom")
    if eua:
        tk = (c1.selectbox("Ação americana", EUA_POPULARES, accept_new_options=True, key="tec_acao_eua",
                           help="Escolha ou digite o código: AAPL, MSFT, NVDA…") or "").strip().upper()
    else:
        base = list(dict.fromkeys(st.session_state.get("sel_ativos", []) + rec.TODOS_TICKERS)) or ["PETR4"]
        padrao = (st.session_state.get("sel_ativos") or [base[0]])[0]
        tk = normaliza(c1.selectbox("Ativo", base, index=base.index(padrao) if padrao in base else 0,
                                    accept_new_options=True, key="tec_acao", format_func=rec.rotulo,
                                    help="Escolha ou digite um ticker da B3 (ex.: PETR4, VALE3).") or "")
    inter = c2.selectbox("Intervalo", ["Diário", "Semanal"], key="tec_acao_tf")
    if not tk:
        st.info("Escolha ou digite um código.")
        return
    periodo, iv = ("2y", "1d") if inter == "Diário" else ("5y", "1wk")
    with st.spinner(f"Lendo o histórico de {tk}…"):
        try:
            df, err = (_hist_eua(tk, periodo, iv), None) if eua else historico(tk, periodo, iv)
        except Exception as e:
            df, err = None, e.__class__.__name__
    if df is None or df.empty or "Close" not in df:
        st.warning(f"Não consegui o histórico de preços de {tk} agora ({err or 'sem dados'}). "
                   + ("Confira o código (ex.: AAPL)." if eua else "Troque a fonte em Ajustes (menu lateral) ou tente de novo em instantes."))
        return
    r = tendencia.analisar(df)
    preco_txt = ("US$ " + f"{r['preco']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") if eua else brl(r["preco"])) if r["preco"] else ""
    _bloco_tendencia(r, tk, preco_txt)
    if r.get("preco"):
        botao_carteira(tk, r["preco"], "_tec")
    st.session_state["_tec_tk"] = tk                      # para o atalho "Comparar" de pagina_tecnica_acoes
    if r["ind"] is not None:
        st.plotly_chart(tendencia.figura(df, r["ind"]), width="stretch", key=f"tec_fig_{tk}_{iv}",
                        config={"displayModeBar": False})
    st.caption(f"Histórico {inter.lower()} via {'Yahoo Finance' if eua else st.session_state.get('fonte_dados', 'Yahoo Finance')}. "
               "Indicadores técnicos servem para estudo, não são recomendação.")


def _tendencia_cripto():
    """Par da Binance: veredito calculado com as velas da Binance; gráfico do TradingView ou painel com sinais."""
    simbolos, binance_ok = list(PARES_POPULARES), False
    if ccxt is not None:
        try:
            with st.spinner("Conectando à Binance…"):
                simbolos = binance_simbolos(binance_exchange())
            binance_ok = True
        except Exception as e:
            st.warning(f"Não consegui conectar à Binance agora ({e.__class__.__name__}): o gráfico do TradingView "
                       "continua disponível, mas o veredito e os sinais não.")
            st.caption("Se a mensagem citar 451 ou 'restricted location', o servidor do app está num país bloqueado "
                       "pela Binance. O TradingView não sofre esse bloqueio, porque carrega no seu navegador.")
    else:
        st.warning("A biblioteca **ccxt** não está instalada: só o gráfico do TradingView está disponível. "
                   "Adicione `ccxt` ao requirements.txt para liberar o veredito e os sinais.")

    c1, c2, c3, c4 = st.columns([2.4, 1, 1, 1.3], vertical_alignment="bottom")
    _pref = st.session_state.get("graf_par")
    entrada = c1.selectbox("Par de criptomoedas", simbolos, index=simbolos.index(_pref) if _pref in simbolos else 0,
                           accept_new_options=True, key="graf_par_in",
                           placeholder="Digite: BTC/USDT, SOL/USDT, RENDER/USDT…",
                           help="Escolha na lista ou digite livremente: btc, BTCUSDT, sol/usdt, render/usdt…")
    tf_lbl = c2.selectbox("Intervalo", list(TIMEFRAMES), index=5, key="graf_tf")
    limite = c3.selectbox("Velas", [200, 300, 500, 1000], index=2, key="graf_n")
    auto = c4.toggle("Atualizar a cada 30 s", value=False, key="graf_auto")

    par = normaliza_par(entrada, set(simbolos))
    if not par:
        st.warning("Digite um par, por exemplo BTC/USDT.")
        return
    if binance_ok and par not in set(simbolos):
        sug = [s for s in simbolos if s.split("/")[0].startswith(par.split("/")[0][:3])][:6]
        st.warning(f"O par **{par}** não existe no mercado à vista da Binance."
                   + (f" Parecidos: {', '.join(sug)}." if sug else ""))
        return
    base, cot = par.split("/")
    st.session_state["graf_par"] = par

    if binance_ok:
        try:
            dfb = binance_ohlcv(par, TIMEFRAMES[tf_lbl], int(limite))
            r = tendencia.analisar(dfb)
            _bloco_tendencia(r, f"{par} ({tf_lbl.lower()})", _fmt_preco(r["preco"]) + f" {cot}" if r["preco"] else "")
            if cot in ("USDT", "USD") and r.get("preco"):
                cripto.botao_carteira_cripto(par.replace("/", "_"), {"simbolo": base, "preco": r["preco"]}, "tec")
        except Exception as e:
            st.error(f"Não consegui buscar {par} na Binance: {e.__class__.__name__}. Tente de novo em instantes.")

    vistas = ["TradingView", "Sinais de candles e setups"] if binance_ok else ["TradingView"]
    vista = st.segmented_control("Gráfico", vistas, default=vistas[0], key="graf_vista",
                                 label_visibility="collapsed") or vistas[0]
    if vista == "TradingView":
        tradingview_cripto(par, TIMEFRAMES[tf_lbl], altura=660)
        st.caption("Gráfico do TradingView (par da Binance). Use o botão de indicadores do próprio gráfico para "
                   "ajustar médias, Bollinger e IFR, e as ferramentas à esquerda para desenhar. "
                   "Indicadores técnicos servem para estudo, não são recomendação.")
    else:
        _painel_binance(par, base, cot, tf_lbl, int(limite), auto)


def pagina_tecnica_acoes():
    cabecalho("📉", "Análise Técnica · Ações",
              "Só preço, sem fundamentos: médias móveis, IFR e MACD de ações da B3 e da NYSE/Nasdaq, com o veredito de "
              "tendência (Alta, Lateral ou Baixa) e cada sinal calculado.")
    md(tema.legenda_tendencia())
    st.session_state.pop("_tec_tk", None)
    _tendencia_acao()
    atalho_comparar([st.session_state.get("_tec_tk")], "tec", "Comparar este ativo com outros")
    evolucao.atalho_evolucao(PG_EVOLUCAO, st.session_state.get("_tec_tk"), "tec", "Evolução e crescimento deste ativo")


def pagina_tecnica_cripto():
    cabecalho("📉", "Análise Técnica · Criptoativos",
              "Só preço, sem fundamentos: o veredito de tendência (Alta, Lateral ou Baixa) e os sinais de qualquer par da "
              "Binance, com o gráfico do TradingView.")
    md(tema.legenda_tendencia())
    _tendencia_cripto()


def _painel_binance(par, base, cot, tf_lbl, limite, auto):
    """Cartões, gráfico com sinais e alertas calculados a partir das velas da Binance (ccxt)."""
    mostrar_sinais = st.toggle("Mostrar sinais dos últimos 3 candles (candles, cruzamentos, setups)", value=True,
                               key="graf_sinais")

    @st.fragment(run_every=30 if auto else None)
    def painel():
        try:
            df = binance_ohlcv(par, TIMEFRAMES[tf_lbl], limite)
        except Exception as e:
            st.error(f"Não consegui buscar {par} na Binance: {e.__class__.__name__}. Tente de novo em instantes.")
            return
        if len(df) < 30:
            st.warning("Poucas velas para esse par e intervalo. Tente um intervalo menor.")
            return
        ind = indicadores_cripto(df)
        sinais, alertas_s, zonas = [], [], []
        if mostrar_sinais:
            try:
                sinais = [s for s in tec.candlesticks(df) if s["sinal"] != "Doji"] + tec.indicadores(df, 20, 50)["sinais"]
                rs = tec.setups(df, tec.SETUP_NOMES)
                sinais += rs["sinais"]
                alertas_s, zonas = rs["alertas"], rs["zonas"]
                sinais = tec.so_atuais(sinais, df, 3)
            except Exception as e:
                st.caption(f"Sinais indisponíveis agora ({e.__class__.__name__}).")
        try:
            st.plotly_chart(figura_cripto(df, ind, sinais=sinais, zonas=zonas), width="stretch", config=tec.CONFIG_GRAFICO)
        except Exception as e:
            st.error(f"Erro ao desenhar o gráfico: {e}")
        if mostrar_sinais and alertas_s:
            cls = {"alta": "pos", "baixa": "neg", "neutro": "neu"}
            for tipo, txt in alertas_s:
                md(f'<div class="ctx {cls.get(tipo, "neu")}"><div class="t">{html.escape(txt)}</div></div>')
        hora = datetime.now().strftime("%H:%M:%S")
        st.caption(f"Dados: Binance (ccxt{', com chave de API' if binance_exchange().options.get('_com_chave') else ''}) · indicadores: {ind.attrs.get('motor', 'pandas')} · atualizado às {hora}. "
                   "Indicadores técnicos servem para estudo, não são recomendação.")

    painel()


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
                   "Streamlit Cloud). Se Fundamentus ou Brapi funcionarem, escolha uma delas em Ajustes (menu lateral) → Fonte de dados.")


# ---------------------------------------------------------------- navegação
# Menu organizado pela jornada de quem está começando:
#   Início -> Analisar separadamente -> Ranking, mais Economia, Carteira e Ajuda.
# Os url_path das páginas de análise são os mesmos de antes.
PG_INICIO = st.Page(pagina_inicio, title="Início", icon="🏠", url_path="inicio", default=True)
PG_PRECO = st.Page(pagina_preco_justo, title="Preço justo", icon=":material/target:", url_path="preco-justo")
PG_DCF = st.Page(pagina_dcf, title="Fluxo de caixa (DCF)", icon=":material/calculate:", url_path="dcf")
PG_VAL = st.Page(pagina_valuation, title="Múltiplos", icon=":material/balance:", url_path="valuation")
PG_DIV = st.Page(pagina_dividendos, title="Dividendos", icon=":material/payments:", url_path="dividendos")
PG_MICRO = st.Page(pagina_micro, title="Saúde financeira", icon=":material/domain:", url_path="micro")
PG_TEC_ACOES = st.Page(pagina_tecnica_acoes, title="Análise Técnica", icon=":material/candlestick_chart:", url_path="tecnica")
PG_TEC_AV = st.Page(pagina_tecnica_avancada_app, title="Análise técnica avançada", icon=":material/query_stats:", url_path="tecnica-avancada")
PG_TEC = st.Page(pagina_tecnica_cripto, title="Análise Técnica", icon=":material/candlestick_chart:", url_path="tecnica-cripto")
PG_PICK = st.Page(pagina_picking, title="Ranking", icon=":material/leaderboard:", url_path="stock-picking")
PG_MACRO = st.Page(pagina_macro, title="Economia", icon=":material/public:", url_path="macro")
PG_CART = st.Page(pagina_carteira_app, title="Carteira", icon=":material/account_balance_wallet:", url_path="carteira")
PG_NOTICIAS = st.Page(pagina_noticias_app, title="Central de notícias e eventos", icon=":material/newspaper:", url_path="noticias")
PG_INTEL = st.Page(pagina_intel_app, title="Central de inteligência", icon=":material/psychology:", url_path="inteligencia")
PG_NOTIF = st.Page(notif_app.pagina_notificacoes, title="Central de notificações", icon=":material/notifications:", url_path="notificacoes")
PG_EDU = st.Page(educacao_app.pagina_educacao, title="Educação financeira", icon=":material/school:", url_path="educacao")
PG_GESTAO = st.Page(pagina_gestao_app, title="Gestão de carteira", icon=":material/pie_chart:", url_path="gestao-carteira")
PG_RISCO = st.Page(pagina_risco_app, title="Gestão de risco", icon=":material/shield:", url_path="risco")
PG_SIM = st.Page(pagina_simulador_app, title="Simulador financeiro", icon=":material/calculate:", url_path="simulador")
PG_REL = st.Page(pagina_relatorios_app, title="Relatórios e dashboard", icon=":material/monitoring:", url_path="relatorios")
PG_CRIPTO = st.Page(cripto.pagina_cripto, title="Visão Geral & Tokenomics", icon=":material/donut_small:", url_path="criptomoedas")
PG_ONCHAIN = st.Page(cripto.pagina_onchain, title="Adoção & On-Chain", icon=":material/lan:", url_path="cripto-onchain")
PG_CRIPTO_AV = st.Page(pagina_cripto_av_app, title="Análise Avançada", icon=":material/psychology:", url_path="cripto-avancada")
PG_RECEITAS = st.Page(cripto.pagina_receitas, title="Receitas & Emissão", icon=":material/payments:", url_path="cripto-receitas")
PG_FUND_CRIPTO = st.Page(fundamentalista_cripto.pagina_fundamentalista, title="Análise Fundamentalista", icon=":material/query_stats:", url_path="cripto-fundamentalista")
PG_TESOURO = st.Page(mercados.pagina_tesouro, title="Tesouro Direto / CDI", icon=":material/savings:", url_path="tesouro-cdi")
PG_ETFS = st.Page(pagina_etfs_app, title="ETFs", icon=":material/stacked_line_chart:", url_path="etfs")
PG_CALC = st.Page(pagina_calculadoras_app, title="Calculadoras", icon=":material/calculate:", url_path="calculadoras")
def pagina_fiis_app():
    """Página de FIIs (fiis_app.py) com atalhos para Comparar e Evolução."""
    fiis_app.pagina_fii(atalho_comparar=atalho_comparar, botao_carteira=botao_carteira,
                        atalho_evolucao=lambda cod, ch, rot: evolucao.atalho_evolucao(PG_EVOLUCAO, cod, ch, rot))
    _bloco_intel(st.session_state.get("fii_tk"))


PG_FIIS = st.Page(pagina_fiis_app, title="FIIs", icon=":material/apartment:", url_path="fiis")
PG_FUNDOS_ACOES = st.Page(pagina_fundos_acoes_app, title="Fundos de Ações", icon=":material/bar_chart:", url_path="fundos-acoes")
PG_MULTI = st.Page(pagina_multimercados_app, title="Multimercados", icon=":material/tune:", url_path="multimercados")
PG_FUNDOS_RF = st.Page(pagina_fundos_rf_app, title="Fundos de Renda Fixa", icon=":material/account_balance:", url_path="fundos-renda-fixa")
PG_RF = st.Page(pagina_renda_fixa_app, title="Análise de títulos", icon=":material/request_quote:", url_path="renda-fixa")
PG_PLANOS = st.Page(planos_app.pagina_planos, title="Planos", icon=":material/workspace_premium:", url_path="planos")
PG_CONTA = st.Page(usuarios.pagina_conta, title="Minha conta", icon=":material/account_circle:", url_path="conta")
PG_ADMIN = st.Page(conta_app.pagina_admin, title="Administração", icon=":material/admin_panel_settings:", url_path="administracao")
PG_AJUDA = st.Page(pagina_ajuda, title="Ajuda", icon=":material/help:", url_path="ajuda")
PG_EVOLUCAO = st.Page(evolucao.pagina_evolucao, title="Evolução e crescimento", icon=":material/timeline:", url_path="evolucao")
PG_COMPARAR = st.Page(pagina_comparar, title="Comparar ativos", icon=":material/compare_arrows:", url_path="comparar")


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


def contexto_grafico() -> str:
    """Contexto da assistente na Análise gráfica: o par que está na tela."""
    par = st.session_state.get("graf_par")
    if pg.url_path == PG_TEC.url_path and par:
        return (f"O usuário está na página Análise Técnica (Tendência), olhando o par {par} na Binance (veredito de "
                "tendência, médias móveis, IFR e MACD). A página não mostra fundamentos.")
    return ("O usuário está na página Análise Técnica (Tendência): veredito de tendência por médias móveis, IFR e "
            f"MACD de {st.session_state.get('tec_acao_eua') if st.session_state.get('tec_bolsa', '').startswith('NYSE') else st.session_state.get('tec_acao') or 'uma ação'}. A página não mostra fundamentos.")


def contexto_cripto() -> str:
    """Contexto da assistente na página Cripto: só as moedas em análise (nada de ações)."""
    ids = st.session_state.get("cripto_ativos", [])
    nomes = st.session_state.get("cripto_nomes", {})
    if not ids:
        return "O usuário está nas páginas de Criptomoedas, ainda sem moedas em análise."
    lista = ", ".join(nomes.get(g) or g.replace("-", " ").title() for g in ids[:6])
    return f"O usuário está nas páginas de Criptomoedas. Moedas em análise: {lista}."


PGS_FUNDAMENTALISTA = [PG_PRECO, PG_VAL, PG_MICRO, PG_DIV, PG_DCF]
paginas = {
    ":material/home: Início": [PG_INICIO],
    ":material/show_chart: Ações": PGS_FUNDAMENTALISTA + [PG_TEC_ACOES, PG_TEC_AV, PG_PICK],   # o Ranking continua no app, só não aparece no menu
    ":material/account_balance: Fundos de investimento": [PG_FIIS, PG_FUNDOS_ACOES, PG_MULTI, PG_FUNDOS_RF],
    ":material/stacked_line_chart: ETFs": [PG_ETFS],
    ":material/currency_bitcoin: Criptoativos": [PG_CRIPTO, PG_ONCHAIN, PG_RECEITAS, PG_FUND_CRIPTO, PG_CRIPTO_AV, PG_TEC],
    ":material/savings: Renda fixa": [PG_RF, PG_TESOURO, PG_CALC],
    ":material/public: Economia": [PG_MACRO],
    ":material/account_balance_wallet: Carteira": [PG_CART, PG_GESTAO, PG_RISCO, PG_REL, PG_SIM],
    ":material/psychology: Inteligência": [PG_INTEL, PG_NOTICIAS, PG_NOTIF],
    ":material/school: Aprender": [PG_EDU],
    ":material/compare_arrows: Comparar": [PG_COMPARAR, PG_EVOLUCAO],
    ":material/help: Ajuda": [PG_AJUDA],
}

# A navegação nativa do Streamlit fica escondida: o menu próprio fica na barra lateral (botão ☰).
try:
    pg = st.navigation({**paginas, ":material/account_circle: Conta": [PG_CONTA, PG_PLANOS, PG_ADMIN]}, position="hidden")
except TypeError:
    st.warning("Esta versão do Streamlit é antiga (`pip install -U streamlit`). Usando o menu lateral.")
    pg = st.navigation({**paginas, ":material/account_circle: Conta": [PG_CONTA, PG_PLANOS, PG_ADMIN]})


def _marca_html(tam: int = 34) -> str:
    """Logotipo em texto: bússola desenhada em SVG + nome com selo B3 (sem imagem, nunca é cortado)."""
    return (
        f'<div class="wm"><svg width="{tam}" height="{tam}" viewBox="0 0 48 48" aria-hidden="true">'
        '<defs><linearGradient id="wmg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#3B6BC4"/>'
        '<stop offset="1" stop-color="#1F7A55"/></linearGradient></defs>'
        '<circle cx="24" cy="24" r="21" fill="none" stroke="url(#wmg)" stroke-width="2.5"/>'
        '<circle cx="24" cy="24" r="16" fill="none" stroke="url(#wmg)" stroke-width="1" stroke-dasharray="2 3.2" opacity=".7"/>'
        '<path d="M24 7 L29.5 24 L24 41 L18.5 24 Z" fill="url(#wmg)" opacity=".18"/>'
        '<path d="M24 7 L29.5 24 L24 24 Z" fill="#C9A227"/><path d="M24 7 L18.5 24 L24 24 Z" fill="url(#wmg)"/>'
        '<path d="M24 41 L29.5 24 L24 24 Z" fill="url(#wmg)" opacity=".55"/>'
        '<path d="M24 41 L18.5 24 L24 24 Z" fill="url(#wmg)" opacity=".8"/>'
        '<circle cx="24" cy="24" r="2.2" fill="#fff" stroke="url(#wmg)" stroke-width="1.2"/></svg>'
        '<span class="wm-t">Bússola<b>B3</b></span></div>')


PGS_CRIPTO_FUND = [PG_CRIPTO, PG_ONCHAIN, PG_RECEITAS, PG_FUND_CRIPTO, PG_CRIPTO_AV]
PGS_MODO_CRIPTO = PGS_CRIPTO_FUND + [PG_TEC]


NAV_CSS = """<style>
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p{white-space:normal !important;overflow:visible !important;text-overflow:clip !important;line-height:1.28 !important}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]{align-items:flex-start;padding-top:6px;padding-bottom:6px}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p{white-space:normal !important;font-weight:700;letter-spacing:.01em;color:#FFFFFF !important}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"],section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg{color:#C5B3FF !important;fill:#C5B3FF !important;opacity:1 !important}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary{gap:10px;align-items:center}
section[data-testid="stSidebar"] details > summary *{color:#EFE9FF !important;-webkit-text-fill-color:#EFE9FF !important;fill:#EFE9FF !important;opacity:1 !important;filter:none !important}
section[data-testid="stSidebar"] details > summary [class*="Icon"], section[data-testid="stSidebar"] details > summary span[role="img"]{color:#C5B3FF !important;-webkit-text-fill-color:#C5B3FF !important;font-size:1.25rem !important}
section[data-testid="stSidebar"] [data-testid="stExpander"] details>div{padding:2px 4px 6px 6px}
section[data-testid="stSidebar"] .nav-sec{margin:18px 0 6px 12px;font-size:.66rem;letter-spacing:.14em;text-transform:uppercase;color:rgba(255,255,255,.62)}
section[data-testid="stSidebar"] .st-key-nav_marca [data-testid="stMarkdownContainer"]{margin-bottom:8px !important}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"]{margin:8px 0 0 10px !important}
section[data-testid="stSidebar"] .nav-sub2{margin:10px 0 2px 10px;font-size:.72rem;font-weight:700;color:rgba(255,255,255,.55);letter-spacing:.03em}
section[data-testid="stSidebar"] [class*="st-key-nav_grp_on_"] [data-testid="stExpander"]{border-color:rgba(197,179,255,.55) !important}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"]{scrollbar-width:thin;scrollbar-color:rgba(255,255,255,.28) transparent}
@media (min-width:992px){section[data-testid="stSidebar"][aria-expanded="true"]{min-width:310px !important}}
</style>"""


def menu_navegacao():
    """Barra lateral ESTÁTICA (botão ☰ no celular): sempre as mesmas opções, qualquer que seja o mercado escolhido
    na página Início. Três blocos separados por divisores: marca, navegação geral e mercados; conta no rodapé."""
    # a página aberta continua sincronizando o modo da página Início (só o estado; o menu não muda)
    if pg.url_path in {p.url_path for p in PGS_MODO_CRIPTO}:
        st.session_state["modo_ativo_v"] = "Criptomoedas"
    elif pg.url_path in {p.url_path for p in PGS_FUNDAMENTALISTA + [PG_PICK, PG_TEC_ACOES]}:
        st.session_state["modo_ativo_v"] = "Ações"

    def item(p, label=None):
        with st.container(key=f"nav_{'on' if pg.url_path == p.url_path else 'off'}_{p.url_path}"):
            st.page_link(p, label=label or p.title, icon=p.icon)

    def sub(nome):
        st.caption(f"**{nome}**")          # caption não tem a margem negativa do markdown (que causava sobreposição)

    def categoria(chave, titulo, icone, blocos, abrir=False):
        """Categoria recolhível. `blocos` = lista de itens (página, rótulo) ou subtítulos (texto). Abre sozinha se a página atual está nela."""
        urls = {x[0].url_path for x in blocos if isinstance(x, tuple)}
        ativo = pg.url_path in urls
        with st.container(key=f"nav_grp_{'on' if ativo else 'off'}_{chave}"):
            with st.expander(titulo, icon=icone, expanded=ativo or abrir):
                for x in blocos:
                    if isinstance(x, tuple):
                        item(*x)
                    else:
                        sub(x)

    st.markdown(NAV_CSS, unsafe_allow_html=True)
    with st.sidebar:
        # marca
        with st.container(key="nav_marca"):
            st.markdown(_marca_html(34) + "<div class='nav-sub'>Terminal de Análise</div>", unsafe_allow_html=True)
        # todas as categorias começam recolhidas; só a da página atual abre sozinha (vale para os três modos)
        ab = lambda k: False

        nivel = experiencia_app.modo()
        ver_todas = bool(st.session_state.get("menu_ver_todas"))
        n_oculto = [0]

        def v(p, rot):
            """Item do menu, ou None se o nível atual o esconde (a página continua acessível por 'Ver todas as páginas')."""
            if PROF.visivel_no_menu(p.url_path, nivel, ver_todas, pg.url_path):
                return (p, rot)
            n_oculto[0] += 1
            return None

        def cat(chave, titulo, icone, blocos):
            """Categoria só com os itens visíveis; subtítulos sem item embaixo e categorias vazias somem."""
            limpos = []
            for x in blocos:
                if x is None:
                    continue
                if isinstance(x, str):
                    if limpos and isinstance(limpos[-1], str):
                        limpos.pop()
                    limpos.append(x)
                else:
                    limpos.append(x)
            if limpos and isinstance(limpos[-1], str):
                limpos.pop()
            if any(isinstance(x, tuple) for x in limpos):
                categoria(chave, titulo, icone, limpos, ab(chave))

        item(PG_INICIO, "Início")
        cat("conta", "Minha conta", ":material/account_circle:", [v(PG_CONTA, "Minha conta"), v(PG_PLANOS, "Planos e assinaturas")])
        cat("acoes", "Análise de ativos", ":material/query_stats:",
            ["Ações", v(PG_PRECO, "Preço justo"), v(PG_VAL, "Múltiplos"), v(PG_DIV, "Dividendos"), v(PG_MICRO, "Saúde financeira"),
             v(PG_DCF, "Fluxo de caixa (DCF)"), v(PG_TEC_ACOES, "Análise técnica"), v(PG_TEC_AV, "Análise técnica avançada"),
             v(PG_INTEL, "Central de inteligência"), v(PG_EVOLUCAO, "Evolução e crescimento"),
             "Fundos e ETFs", v(PG_FIIS, "FIIs"), v(PG_ETFS, "ETFs"), v(PG_FUNDOS_ACOES, "Fundos de ações"), v(PG_MULTI, "Multimercados"),
             v(PG_FUNDOS_RF, "Fundos de renda fixa"),
             "Renda fixa", v(PG_RF, "Análise de títulos"), v(PG_TESOURO, "Tesouro Direto / CDI")])
        cat("cripto", "Criptomoedas", ":material/currency_bitcoin:",
            [v(PG_CRIPTO, "Visão geral e tokenomics"), v(PG_ONCHAIN, "Adoção e on-chain"), v(PG_RECEITAS, "Receitas e emissão"),
             v(PG_FUND_CRIPTO, "Análise fundamentalista"), v(PG_CRIPTO_AV, "Análise avançada"), v(PG_TEC, "Análise técnica")])
        cat("inv", "Minha carteira", ":material/account_balance_wallet:",
            [v(PG_CART, "Minha carteira"), v(PG_GESTAO, "Gestão de carteira"), v(PG_RISCO, "Gestão de risco"),
             v(PG_COMPARAR, "Comparar ativos"), v(PG_REL, "Relatórios e dashboard")])
        cat("mercado", "Mercado e economia", ":material/trending_up:",
            [v(PG_NOTICIAS, "Notícias e eventos"), v(PG_MACRO, "Economia"), v(PG_NOTIF, "Notificações" + notif_app.selo_texto())])
        cat("ferramentas", "Ferramentas", ":material/build:", [v(PG_SIM, "Simulador financeiro"), v(PG_CALC, "Calculadoras")])
        cat("edu", "Educação", ":material/school:", [v(PG_EDU, "Educação financeira"), v(PG_AJUDA, "Ajuda e diagnóstico")])
        if usuarios.pode("admin.resumo"):
            categoria("admin", "Administração", ":material/admin_panel_settings:", [(PG_ADMIN, "Administração")], ab("admin"))
        if n_oculto[0] or ver_todas:
            st.toggle("Ver todas as páginas", key="menu_ver_todas", help="Seu nível mostra só o essencial no menu. Ligue para ver também as páginas avançadas.")

        ajustes_laterais()
        # rodapé · conta (mesmas funções de login de antes)
        with st.container(key="nav_rodape"):
            st.markdown("---")
            if usuarios.usuario():
                st.markdown(f"<div class='nav-user'><i></i>{html.escape(usuarios.primeiro_nome())}</div>",
                            unsafe_allow_html=True)
                st.button("Sair", icon=":material/logout:", on_click=usuarios.sair, key="sair_s", type="tertiary")
            elif usuarios.eh_visitante():
                st.markdown("<div class='nav-user'><i></i>Visitante</div>", unsafe_allow_html=True)
                st.button("Entrar", icon=":material/login:", on_click=usuarios.sair_visitante,
                          key="entrar_s", type="tertiary")
            elif not usuarios.acesso_obrigatorio():
                st.markdown("<div class='nav-user'><i></i>Visitante</div>", unsafe_allow_html=True)
                st.caption("Login desativado: faltam os secrets [auth] (Google) ou [email].")

    # topo da página: marca e conta (o menu fica na barra lateral)
    with st.container(key="nav_mobile"):
        a, b = st.columns([3, 1], vertical_alignment="center")
        a.markdown(_marca_html(32), unsafe_allow_html=True)
        if usuarios.usuario():
            with b.popover(f":material/account_circle: {usuarios.primeiro_nome()}"):
                st.markdown(f"**{usuarios.primeiro_nome()}**")
                st.page_link(PG_CONTA, label="Minha conta", icon=PG_CONTA.icon)
                st.page_link(PG_NOTIF, label="Notificações" + notif_app.selo_texto(), icon=PG_NOTIF.icon)
                st.page_link(PG_CONTA, label="Meu nível de conhecimento", icon=":material/tune:")
                usuarios.menu_conta("m")
        elif usuarios.eh_visitante():
            with b.popover(":material/account_circle: Entrar"):
                usuarios.menu_visitante("m")


def ajustes_laterais():
    """Fonte de dados, atualizar e adicionar empresa por ticker: ficam no menu lateral, não numa barra fixa no topo."""
    with st.expander("Ajustes", icon=":material/tune:"):
        st.selectbox("Fonte de dados", FONTES, key="fonte_dados")
        if st.button("Atualizar dados", icon=":material/refresh:", width="stretch", key="ajuste_atualizar"):
            liberado, info_plano = __import__("planos").usar("atualizar_dados")
            if not liberado:
                st.warning(info_plano.get("mensagem") or "Limite diário atingido.")
            else:
                st.cache_data.clear()
                __import__("cache_central").limpar_tudo()
                st.rerun()
        with st.form("add", clear_on_submit=True):
            st.text_input("Adicionar empresa por ticker", key="novo_ticker", placeholder="Ex.: WEGE3, ABCB4")
            st.form_submit_button("Adicionar", on_click=_adicionar_ticker)
        if st.session_state.get("msg_add"):
            st.caption(st.session_state["msg_add"])
        st.page_link(PG_AJUDA, label="Ajuda e diagnóstico", icon=":material/help:")


conta_app.registrar_paginas(gestao=PG_GESTAO, inteligencia=PG_INTEL, relatorios=PG_REL, noticias=PG_NOTICIAS, admin=PG_ADMIN)
_todas_pg = {p.url_path: p for n_, p in list(globals().items()) if n_.startswith("PG_") and hasattr(p, "url_path")}
notif_app.registrar_paginas(_todas_pg)
educacao_app.registrar_paginas({"renda-fixa": PG_RF, "fiis": PG_FIIS, "criptomoedas": PG_CRIPTO, "simulador": PG_SIM})
usuarios.exigir_login(marca.LOGO_GRANDE, "Bússola B3")   # sem login configurado nos secrets, abre como visitante
usuarios.iniciar()                        # carrega ações, perfil e carteiras do usuário

em_cripto = (pg.url_path in (PG_CRIPTO.url_path, PG_ONCHAIN.url_path, PG_RECEITAS.url_path, PG_FUND_CRIPTO.url_path,
                              PG_CRIPTO_AV.url_path)
             or (pg.url_path == PG_INICIO.url_path and modo_atual() == "Criptomoedas"))

menu_navegacao()   # marca e menu no topo
# O Streamlit apaga o estado de widgets que não aparecem na tela; regravamos a seleção de ações e o perfil
# para não se perderem ao trocar de página (a escolha é feita dentro das páginas que precisam dela).
for _k in ("sel_ativos", "perfil"):
    if _k in st.session_state:
        st.session_state[_k] = st.session_state[_k]
try:
    experiencia_app.faixa(pg.url_path)
    ajuda_app.botao(pg.url_path)
    experiencia_app.glossario_da_pagina(pg.url_path)
    pg.run()
finally:
    usuarios.salvar()   # grava as mudanças do usuário, mesmo se a página chamar st.stop()
if hasattr(assistente, "flutuante"):  # Assistente de Investimentos: botão flutuante em todas as páginas
    try:
        assistente.flutuante(contexto_fn=contexto_grafico if pg.url_path in (PG_TEC.url_path, PG_TEC_ACOES.url_path) else
                             (contexto_cripto if em_cripto else contexto_assistente))
    except Exception as e:
        st.caption(f"Assistente indisponível no momento ({e.__class__.__name__}).")

if not em_cripto:
    st.caption("Ferramenta educacional. Graham, Bazin, DCF e a nota do Ranking são modelos simplificados "
               "e dependem da qualidade das fontes; não constituem recomendação de investimento.")
