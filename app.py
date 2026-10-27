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
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
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
PLOT_LEG = {**PLOT, "margin": dict(l=10, r=10, t=40, b=60)}  # margem extra p/ legenda abaixo do gráfico

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
       '<b>Ativos em análise</b>, lá em cima, ou use <b>Encontrar → Buscar empresa</b>.</div></div>')
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
                                 "(Comparar → Perfis e cenários)."),
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
        c2.markdown("**📊 Analise**  \nPreço justo, DCF, múltiplos e tendência.")
        c3.markdown("**🏆 Compare**  \nRanking e os mesmos ativos em cada perfil.")
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
                st.info("Não encontrei no catálogo. Depois use **Encontrar → Buscar empresa** para procurar na internet.")
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
        md("Cada cartão também mostra a **tendência do gráfico diário** nos últimos 5 anos: Alta, Lateral ou Baixa.")
        st.caption("Passe o mouse no ⓘ de qualquer indicador para ver o que ele significa.")

    elif i == 4:
        st.markdown("### Descubra oportunidades")
        md("- **🧪 Buscador de oportunidades** (Encontrar): marque critérios de uma boa empresa (ROE, dívida, "
           "dividendos, margem de segurança...) e veja quais do catálogo passam no filtro.\n"
           "- **🏆 Ranking (Stock picking)** (Comparar): nota de 0 a 100 em seis pilares, com pesos do seu perfil.\n"
           "- **🧭 Perfis e cenários** (Comparar): a mesma empresa avaliada nos três perfis, com cenários de DCF "
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
    st.caption("Leitura completa, época dos dados e impacto por ação e setor em Início → Macroeconomia.")
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
               "Ajuste em Analisar → Preço justo.")


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
    with st.spinner("Lendo o gráfico diário dos últimos 5 anos..."):
        tend = {r["ticker"]: tendencia_5a(r["ticker"]) for r in resultados}
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
</div>{linha_tendencia(tend.get(r['ticker']))}{aviso_moeda}{aviso_lpa}</div>""",
                        unsafe_allow_html=True)
                    st.plotly_chart(gauge(r["margem"], cor_ativo(r["ticker"])), width="stretch",
                                    key=f"g_{r['ticker']}", config={"displayModeBar": False})
                    st.caption(f"Margem de segurança · Graham {brl(r['graham'])} · Bazin {brl(r['bazin'])}")
        st.caption("Tendência no gráfico diário (até 5 anos): ▲ Alta (verde) = preço acima da média de 200 dias, média de "
                   "50 acima da de 200 e média de 200 subindo; ▼ Baixa (vermelho) = os três sinais contrários; "
                   "► Lateral (amarelo) = sinais mistos. Indicador técnico, não recomendação.")

    with t_comp:
        df = pd.DataFrame([{"Ticker": r["ticker"], "Preço": r["preco"], "Preço justo": r["justo"],
                            "Margem (%)": r["margem"], "Status": r["status"],
                            "Tendência 5a": tend.get(r["ticker"]) or "—"}
                           for r in resultados])
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
    fig.update_layout(barmode="group", height=300, title="Fluxo de caixa histórico (R$ milhões)",
                      legend=dict(orientation="h", y=-0.15, x=0), **PLOT_LEG)
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
               "ou veja os três lado a lado em Comparar → Perfis e cenários.")

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
            fig.update_layout(barmode="group", title="Nota por perfil", height=330,
                              legend=dict(orientation="h", y=-0.15, x=0), **PLOT_LEG)
            fig.update_yaxes(range=[0, 100], **GRID)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        with g2:
            fig = go.Figure()
            for pf in PERFIS:
                fig.add_bar(x=tks, y=[aval[(t, pf)]["pot"] for t in tks], name=pf, marker_color=COR_PERFIL[pf])
            fig.add_hline(y=0, line_color=MUTED)
            fig.update_layout(barmode="group", title="Potencial do DCF por perfil (%)", height=330,
                              legend=dict(orientation="h", y=-0.15, x=0), **PLOT_LEG)
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
                fig.update_layout(barmode="group", title=f"Valor justo por DCF · {rec.nome_curto(tk)}", height=350,
                                  legend=dict(orientation="h", y=-0.15, x=0), **PLOT_LEG)
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


# ---------------------------------------------------------------- páginas: encontrar (busca por nome e buscador de oportunidades)
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


IPEA_CATEGORIAS = {
    "💹 Macro e valuation": [
        ("Selic acumulada no mês (%)", [("BM12_SELC12", "valor"), ("BM12_TJOVER12", "valor")],
         lambda v: pct(v, 2), GOOD, "p.p.", "Custo de capital e taxa de desconto das empresas (WACC)."),
        ("Câmbio R$/US$ (média)", [("BM12_ERC12", "valor"), ("BM12_ERV12", "valor")],
         brl, ACCENT, "R$", "Impacto em exportadoras (Vale, Suzano) e importadoras."),
        ("Risco-País EMBI+ (pontos)", [("BM12_EMBI12", "valor"), ("JPM366_EMBI366", "valor")],
         lambda v: f"{num(v, 0)} pts", "#7C3AED", "pts", "Prêmio de risco exigido para investir no Brasil."),
    ],
    "🏷️ Preços e contratos": [
        ("IPCA mensal (%)", [("PRECOS12_IPCA12", "preco"), ("PRECOS12_IPCAG12", "valor")],
         lambda v: pct(v, 2), FAIR, "p.p.", "Reajuste de contratos e inflação repassada ao consumidor."),
        ("IGP-M mensal (%)", [("PRECOS12_IGPM12", "preco"), ("IGP12_IGPMG12", "valor"), ("IGP12_IGPM12", "preco")],
         lambda v: pct(v, 2), "#0D9488", "p.p.", "Indexador de aluguéis (shoppings, galpões) e contratos de elétricas."),
        ("INCC mensal (%)", [("PRECOS12_INCC12", "preco")],
         lambda v: pct(v, 2), "#CA8A04", "p.p.", "Pressão de custos em construtoras e incorporadoras."),
    ],
    "🏭 Atividade econômica": [
        ("IBC-Br (prévia do PIB)", [("SGS12_IBCBR12", "indice")],
         lambda v: num(v, 1), "#0284C7", "pts", "Termômetro mensal: o país está crescendo?"),
        ("Produção industrial (geral)", [("PIMPF12_INDG12", "indice")],
         lambda v: num(v, 1), "#4D7C0F", "pts", "Demanda e desempenho de indústrias e bens de capital."),
    ],
    "🛒 Varejo, consumo e crédito": [
        ("Vendas no varejo (PMC)", [("PMC12_RVT12", "indice")],
         lambda v: num(v, 1), "#DB2777", "pts", "Força do consumo (Assaí, Carrefour, Magazine Luiza)."),
        ("Desemprego PNAD (%)", [("PNADC12_TDES12", "valor")],
         lambda v: pct(v, 1), BAD, "p.p.", "Capacidade de endividamento da população e inadimplência."),
    ],
}


def _serie_ipea(codigos):
    """Tenta cada código na ordem. Devolve (código usado, modo, DataFrame com 'valor')."""
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
        if modo == "preco" and s.abs().median() > 30:  # veio como índice: vira % mensal
            s = (s.pct_change() * 100).dropna()
        if not s.empty:
            return cod, modo, s.to_frame("valor")
    return None, None, pd.DataFrame()


def pagina_macro():
    intro("🌐", "O cenário econômico do Brasil",
          "Juros (Selic), inflação (IPCA), dólar, atividade e desemprego influenciam o preço das ações. "
          "Aqui você acompanha esses números e vê <b>o que observar</b> em cada um.")
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
        for categoria, itens in IPEA_CATEGORIAS.items():
            st.markdown(f"#### {categoria}")
            for i in range(0, len(itens), 2):
                cols = st.columns(2)
                for col, (titulo, codigos, fmt, cor, unid, monitorar) in zip(cols, itens[i:i + 2]):
                    with col:
                        cod, modo, df = _serie_ipea(codigos)
                        if df.empty:
                            st.warning(f"{titulo}: sem dados agora (código {codigos[0][0]}).")
                            st.caption(f"👀 {monitorar}")
                            continue
                        cartao_serie(titulo, df, anos, fmt, cor, unid, barra=(modo == "preco"))
                        extra = ""
                        if modo == "indice" and len(df) > 12:
                            v12 = (df["valor"].iloc[-1] / df["valor"].iloc[-13] - 1) * 100
                            extra = f" · 12 meses: {pct(v12, 1)}"
                        reserva = "" if cod == codigos[0][0] else " (código reserva)"
                        st.caption(f"👀 {monitorar}{extra}  \nIpeadata: {cod}{reserva}")
        st.caption("Séries do Ipeadata. Se o código pedido não devolver dados, o app tenta um reserva da mesma série. "
                   "Alguns indicadores saem com 1 a 2 meses de defasagem.")


def pagina_micro():
    dados = dados_ativos()
    if not dados:
        return
    st.markdown("#### Matriz de indicadores das empresas")
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
        estado_vazio()
        return
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.4])
    ticker = c1.selectbox("Ativo", ativos, key="tec_ativo", format_func=rec.rotulo)
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


# ---------------------------------------------------------------- barra superior (substitui a sidebar)
def _adicionar_ticker():
    """Aceita tickers ou nomes de empresa, separados por vírgula."""
    termos = []
    for p in re.split(r"[,;]+", st.session_state.get("novo_ticker", "")):
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
        partes.append("Não encontrei: " + ", ".join(falhas) + ". Tente em Encontrar → Buscar empresa.")
    st.session_state["msg_add"] = " · ".join(partes)


def barra_superior():
    c1, c2, c3, c4, c5, c6 = st.columns([1.7, 4.6, 1.0, 1.8, 0.55, 0.55], vertical_alignment="center")
    c1.markdown(f'<div class="hero">Painel B3</div>'
                f'<div class="sub">Atualizado em {datetime.now():%d/%m/%Y %H:%M}</div>',
                unsafe_allow_html=True)
    opcoes = list(dict.fromkeys(st.session_state.universo + rec.TODOS_TICKERS))
    c2.multiselect("Ativos em análise", options=opcoes, key="sel_ativos", format_func=rec.rotulo,
                   label_visibility="collapsed",
                   placeholder="Digite o nome da empresa (ex.: Petrobras) ou o ticker")
    for t in st.session_state.sel_ativos:
        if t not in st.session_state.universo:
            st.session_state.universo.append(t)
    with c3.popover("➕ Ativo"):
        with st.form("add", clear_on_submit=True):
            st.text_input("Nome ou ticker", key="novo_ticker", placeholder="Ex.: Petrobras, WEGE3, ABCB4")
            st.form_submit_button("Adicionar", on_click=_adicionar_ticker)
        if st.session_state.get("msg_add"):
            st.caption(st.session_state["msg_add"])
        st.caption("Para explorar por setor ou ver logos, use Encontrar → Buscar empresa.")
    c4.selectbox("Fonte de dados", FONTES, key="fonte_dados", label_visibility="collapsed",
                 format_func=lambda f: f"Fonte: {f}")
    if c5.button("🔄", help="Limpar cache e atualizar dados", width="stretch"):
        st.cache_data.clear()
        st.rerun()
    if c6.button("❓", help="Abrir o tutorial", width="stretch"):
        st.session_state.tour_passo = 0
        tutorial()

    p1, p2 = st.columns([3.4, 5], vertical_alignment="center")
    p1.radio("Perfil do investidor", list(PERFIS), key="perfil", horizontal=True,
             format_func=lambda x: f"{PERFIS[x]['icone']} {x}", help=ajuda_txt("Perfil"))
    p2.caption(PERFIS[perfil_atual()]["resumo"])
    if st.session_state.fonte_dados == "Brapi" and not _token():
        st.warning("Token da Brapi não configurado (BRAPI_TOKEN). Os dados virão do Yahoo Finance quando faltarem.")


# ---------------------------------------------------------------- navegação
# Menu organizado pelo que a pessoa quer fazer:
#   Início    -> ver o panorama e o cenário econômico
#   Encontrar -> achar empresas para estudar
#   Analisar  -> olhar a fundo as empresas escolhidas (valor, caixa, múltiplos, dividendos, gráfico, indicadores)
#   Comparar  -> ranquear e comparar as empresas entre si e entre perfis
PG_INICIO = st.Page(pagina_inicio, title="Visão geral", icon="🏠", url_path="inicio", default=True)
PG_MACRO = st.Page(pagina_macro, title="Economia (Macro)", icon="🌐", url_path="macro")
PG_BUSCA = st.Page(pagina_busca, title="Buscar empresa", icon="🔎", url_path="buscar")
PG_SCREENER = st.Page(pagina_screener, title="Buscador de oportunidades", icon="🧪", url_path="oportunidades")
PG_PRECO = st.Page(pagina_preco_justo, title="Preço justo e tendência", icon="🎯", url_path="preco-justo")
PG_DCF = st.Page(pagina_dcf, title="Fluxo de caixa descontado (DCF)", icon="🧮", url_path="dcf")
PG_VAL = st.Page(pagina_valuation, title="Múltiplos (P/L, P/VP...)", icon="⚖️", url_path="valuation")
PG_DIV = st.Page(pagina_dividendos, title="Dividendos", icon="💰", url_path="dividendos")
PG_TEC = st.Page(pagina_tecnica, title="Gráfico e análise técnica", icon="📉", url_path="tecnica")
PG_MICRO = st.Page(pagina_micro, title="Indicadores das empresas", icon="🏢", url_path="micro")
PG_PICK = st.Page(pagina_picking, title="Ranking (Stock picking)", icon="🏆", url_path="stock-picking")
PG_PERFIS = st.Page(pagina_perfis, title="Perfis e cenários", icon="🧭", url_path="perfis")

paginas = {
    "🏠 Início": [PG_INICIO, PG_MACRO],
    "🔎 Encontrar": [PG_BUSCA, PG_SCREENER],
    "📊 Analisar": [PG_PRECO, PG_DCF, PG_VAL, PG_DIV, PG_TEC, PG_MICRO],
    "🏆 Comparar": [PG_PICK, PG_PERFIS],
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
if not st.session_state.tour_visto:  # tutorial abre sozinho na primeira visita
    st.session_state.tour_visto = True
    try:
        tutorial()
    except Exception as e:  # o tutorial é um extra: não pode impedir o app de abrir
        st.caption(f"Tutorial indisponível no momento ({e.__class__.__name__}). Use o botão ❓ para tentar de novo.")
pg.run()

st.caption("Ferramenta educacional. Graham, Bazin, DCF e a nota de Stock Picking são modelos simplificados "
           "e dependem da qualidade das fontes; não constituem recomendação de investimento.")
