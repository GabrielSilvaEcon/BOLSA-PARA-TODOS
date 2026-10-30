"""Camada de acabamento visual (SaaS/dashboard) do Bússola B3.

Injeta CSS por cima do tema base: tokens em múltiplos de 8px, tipografia com hierarquia, cores suavizadas,
bordas sutis, sombras macias, estados hover/active/focus-visible, transições, skeleton e empty state.
Uso: st.markdown(tema.css(), unsafe_allow_html=True)
"""
import html

# Ícones de linha (mesmo traço 1.75, cantos arredondados), tamanho proporcional ao texto.
_ICONES = {
    "busca": "<circle cx='11' cy='11' r='7'/><path d='m20 20-3.5-3.5'/>",
    "grafico": "<path d='M4 19V5'/><path d='M4 19h16'/><path d='m8 15 3-4 3 2 4-6'/>",
    "carteira": "<path d='M4 7a2 2 0 0 1 2-2h12v4'/><path d='M4 7v10a2 2 0 0 0 2 2h14V9H6a2 2 0 0 1-2-2z'/><circle cx='16' cy='14' r='1'/>",
    "moeda": "<circle cx='12' cy='12' r='8'/><path d='M14.5 9.5c-.6-.8-1.5-1.2-2.5-1.2-1.4 0-2.5.8-2.5 1.9 0 2.6 5 1.2 5 3.8 0 1.1-1.1 1.9-2.5 1.9-1 0-2-.4-2.6-1.2M12 6.5v1.8m0 7.4v1.8'/>",
    "bussola": "<circle cx='12' cy='12' r='8.5'/><path d='m15.5 8.5-2 5-5 2 2-5z'/>",
    "alerta": "<path d='M12 4 3 19h18z'/><path d='M12 10v4m0 3h.01'/>",
    "caixa": "<path d='M4 13 6.5 6h11L20 13v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1z'/><path d='M4 13h4.5l1 2h5l1-2H20'/>",
}


def icone(nome: str, tam: int = 20) -> str:
    corpo = _ICONES.get(nome, _ICONES["bussola"])
    return (f"<svg class='ico' width='{tam}' height='{tam}' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
            f"stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>{corpo}</svg>")


def vazio(icone_nome: str, titulo: str, texto: str = "") -> str:
    """Estado vazio: ícone num círculo suave, título em destaque e texto de apoio."""
    sub = f"<p>{html.escape(texto)}</p>" if texto else ""
    return (f"<div class='vazio'><div class='vazio-ico'>{icone(icone_nome, 24)}</div>"
            f"<h4>{html.escape(titulo)}</h4>{sub}</div>")


def skeleton(linhas: int = 3) -> str:
    """Cartões fantasma com brilho passando, para mostrar enquanto os dados carregam."""
    um = ("<div class='sk-card'><div class='sk sk-av'></div><div class='sk-col'>"
          "<div class='sk sk-l1'></div><div class='sk sk-l2'></div></div><div class='sk sk-btn'></div></div>")
    return "<div class='sk-wrap'>" + um * linhas + "</div>"


def css() -> str:
    return """<style>
:root {
  /* espaçamento: múltiplos de 8px */
  --s1:8px; --s2:16px; --s3:24px; --s4:32px; --s5:40px;
  /* raios: controles 12, cartões 16, pílulas 999 */
  --r-c:12px; --r-card:16px; --r-pill:999px;
  /* cores suavizadas (sem preto nem branco puros) */
  --bg:#F2F4F7; --surface:#FBFCFD; --surface-2:#F5F7FA;
  --t1:#16202B; --t2:#4B5767; --t3:#788494;
  --line:rgba(22,32,43,.09); --line-2:rgba(22,32,43,.14);
  --brand:#1F7A55; --brand-d:#17604A; --brand-soft:rgba(31,122,85,.10); --ring:rgba(31,122,85,.35);
  /* sombras macias */
  --sh1:0 1px 2px rgba(22,32,43,.04), 0 6px 16px -10px rgba(22,32,43,.10);
  --sh2:0 2px 4px rgba(22,32,43,.05), 0 18px 32px -18px rgba(22,32,43,.20);
  --ease:all .2s ease-in-out;
}

/* ---------- tipografia e hierarquia ---------- */
.stApp {background:var(--bg); -webkit-font-smoothing:antialiased; text-rendering:optimizeLegibility;}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span {line-height:1.55; letter-spacing:.005em;}
.stApp p, .stApp li {font-weight:500; color:var(--t1);}
.stApp h1, .stApp h2, .stApp h3, .stApp h4 {color:var(--t1); line-height:1.2; letter-spacing:-.015em; font-weight:800;}
.stApp h3 {font-size:1.45rem; margin-bottom:var(--s1);}
.stApp h4 {font-size:1.1rem;}
.stApp [data-testid="stCaptionContainer"], .stApp small {color:var(--t2); font-weight:500; line-height:1.5;}
.pgt {letter-spacing:-.02em; color:var(--t1);}
.pgsub, .nm, .kpi .d, .ctx .x, .mini .xx {color:var(--t2); font-weight:500; line-height:1.5;}
.lbl {color:var(--t3); font-weight:700; letter-spacing:.08em; font-size:.68rem;}
.val, .kpi .v, .tk, .stMetric [data-testid="stMetricValue"] {font-variant-numeric:tabular-nums; letter-spacing:-.01em;}
.tk {font-size:1.15rem; color:var(--t1);}
.hero2 h1 {letter-spacing:-.025em; font-size:2.25rem;}
.hero2 p {color:var(--t2); font-weight:500; line-height:1.6; font-size:1.05rem;}
.ico {flex-shrink:0; vertical-align:-.2em;}

/* ---------- cabeçalho e área principal ---------- */
header[data-testid="stHeader"] {background:rgba(251,252,253,.82); backdrop-filter:saturate(1.4) blur(10px);
  border-bottom:1px solid var(--line);}
.block-container {padding-top:4.5rem;}

/* ---------- cartões ---------- */
.card, .kpi, .mini, .ctx, .st-key-ctx_bar, .st-key-trilha_bar, .st-key-nav_desktop, .st-key-nav_mobile {
  background:var(--surface); border:1px solid var(--line); box-shadow:var(--sh1); transition:var(--ease);}
.card {border-radius:var(--r-card); padding:var(--s2) var(--s3) var(--s2); margin-bottom:var(--s2);}
.kpi {border-radius:var(--r-card); padding:var(--s2);}
.mini {border-radius:var(--r-card); padding:var(--s2);}
.ctx {border-radius:var(--r-c); padding:var(--s2); margin-bottom:var(--s1); border-left-width:4px;}
.st-key-ctx_bar, .st-key-trilha_bar {border-radius:var(--r-card); padding:var(--s1) var(--s2); margin-bottom:var(--s2);}
.st-key-nav_desktop, .st-key-nav_mobile {border-radius:var(--r-card); padding:var(--s1);}
.card:hover, .kpi:hover, .mini:hover {border-color:var(--line-2); box-shadow:var(--sh2); transform:translateY(-1px);}
[data-testid="stVerticalBlockBorderWrapper"] {border-radius:var(--r-card); transition:var(--ease);}
[data-testid="stMetric"] {background:var(--surface); border:1px solid var(--line); border-radius:var(--r-card);
  padding:var(--s2); box-shadow:var(--sh1); transition:var(--ease);}
[data-testid="stMetric"]:hover {box-shadow:var(--sh2); transform:translateY(-1px);}
[data-testid="stMetricLabel"] p {color:var(--t3); font-weight:700; letter-spacing:.06em; text-transform:uppercase; font-size:.72rem;}

/* ---------- selos ---------- */
.badge {padding:4px 12px; letter-spacing:.02em; font-weight:700;}
.chip, .stp span {border:1px solid var(--line); background:var(--surface); transition:var(--ease);}
.chip:hover, .stp span:hover {border-color:var(--line-2); box-shadow:var(--sh1);}

/* ---------- botões e links clicáveis ---------- */
.stButton > button, .stFormSubmitButton > button, .stDownloadButton > button, .stLinkButton > a {
  border-radius:var(--r-pill); font-weight:700; min-height:40px; padding:0 var(--s2);
  border:1px solid var(--line-2); background:var(--surface); color:var(--t1); box-shadow:var(--sh1); transition:var(--ease);}
.stButton > button:hover, .stFormSubmitButton > button:hover, .stDownloadButton > button:hover {
  border-color:var(--brand); color:var(--brand-d); background:var(--surface); transform:translateY(-1px); box-shadow:var(--sh2);}
.stButton > button:active, .stFormSubmitButton > button:active {transform:translateY(0) scale(.98); box-shadow:var(--sh1);}
button[data-testid^="stBaseButton-primary"] {background:linear-gradient(180deg,var(--brand) 0%,var(--brand-d) 100%) !important;
  border:1px solid var(--brand-d) !important; box-shadow:0 1px 2px rgba(23,96,74,.30), 0 8px 18px -8px rgba(31,122,85,.55);}
button[data-testid^="stBaseButton-primary"]:hover {filter:brightness(1.06); transform:translateY(-1px);}
button[data-testid^="stBaseButton-primary"] p {color:#FBFCFD !important;}
button:disabled, button[disabled] {opacity:.55; cursor:not-allowed; transform:none !important; box-shadow:none !important;}
a[data-testid="stPageLink-NavLink"] {border-radius:var(--r-pill); transition:var(--ease); border-color:var(--line);}
a[data-testid="stPageLink-NavLink"]:hover {background:var(--brand-soft); border-color:var(--line-2);}
.st-key-nav_desktop a[aria-current="page"], [data-testid="stPopoverBody"] a[aria-current="page"] {background:var(--brand-soft);}
.st-key-nav_desktop button:hover, .st-key-nav_mobile button:hover {background:var(--brand-soft) !important; transform:none; box-shadow:none !important;}

/* foco visível para teclado */
button:focus-visible, a:focus-visible, [role="button"]:focus-visible, [tabindex]:focus-visible, summary:focus-visible {
  outline:2px solid var(--ring) !important; outline-offset:2px !important; border-radius:var(--r-c);}

/* ---------- campos ---------- */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"], .stNumberInput [data-baseweb="input"] {
  border-radius:var(--r-c) !important; background:var(--surface) !important;
  border:1px solid var(--line-2) !important; transition:var(--ease);}
[data-baseweb="input"]:hover, [data-baseweb="select"] > div:hover {border-color:var(--t3) !important;}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within, [data-baseweb="textarea"]:focus-within {
  border-color:var(--brand) !important; box-shadow:0 0 0 3px var(--brand-soft) !important;}
[data-baseweb="tag"] {border-radius:var(--r-pill) !important; background:var(--brand-soft) !important;}
[data-baseweb="tag"] span {color:var(--brand-d) !important; font-weight:700;}
[data-baseweb="popover"] > div {border-radius:var(--r-card) !important; border:1px solid var(--line); box-shadow:var(--sh2) !important;}
[data-testid="stPopoverBody"] {border-radius:var(--r-card) !important; border:1px solid var(--line); box-shadow:var(--sh2) !important;}

/* ---------- expansores, abas, alertas, tabelas ---------- */
[data-testid="stExpander"] {border:1px solid var(--line) !important; border-radius:var(--r-card) !important;
  background:var(--surface); box-shadow:var(--sh1); overflow:hidden; transition:var(--ease);}
[data-testid="stExpander"] summary {padding:var(--s1) var(--s2); transition:var(--ease);}
[data-testid="stExpander"] summary:hover {background:var(--surface-2);}
.stTabs [data-baseweb="tab-list"] {gap:var(--s1); border-bottom:1px solid var(--line);}
.stTabs [data-baseweb="tab"] {border-radius:var(--r-c) var(--r-c) 0 0; padding:var(--s1) var(--s2); font-weight:700;
  color:var(--t2); transition:var(--ease);}
.stTabs [data-baseweb="tab"]:hover {background:var(--surface-2); color:var(--t1);}
.stTabs [aria-selected="true"] {color:var(--brand-d);}
[data-testid="stAlert"] {border-radius:var(--r-card); border:1px solid var(--line); box-shadow:var(--sh1);}
[data-testid="stDataFrame"], [data-testid="stTable"] {border-radius:var(--r-card); overflow:hidden; border:1px solid var(--line);
  box-shadow:var(--sh1);}
[data-testid="stToast"] {border-radius:var(--r-card) !important; box-shadow:var(--sh2) !important; border:1px solid var(--line);}
hr {border-color:var(--line) !important; margin:var(--s3) 0 !important;}

/* ---------- carregamento: spinner discreto e skeleton ---------- */
[data-testid="stSpinner"] {padding:var(--s1) 0; color:var(--t2); font-weight:600;}
[data-testid="stSpinner"] i, [data-testid="stSpinner"] svg {border-top-color:var(--brand) !important; color:var(--brand) !important;}
.sk-wrap {display:flex; flex-direction:column; gap:var(--s1);}
.sk-card {display:flex; align-items:center; gap:var(--s2); padding:var(--s2); background:var(--surface);
  border:1px solid var(--line); border-radius:var(--r-card); box-shadow:var(--sh1);}
.sk-col {flex:1; display:flex; flex-direction:column; gap:var(--s1);}
.sk {border-radius:8px; background:linear-gradient(90deg,#E6EAEF 25%,#F3F5F8 45%,#E6EAEF 65%);
  background-size:200% 100%; animation:shimmer 1.4s ease-in-out infinite;}
.sk-av {width:40px; height:40px; border-radius:12px;} .sk-l1 {height:16px; width:48%;} .sk-l2 {height:8px; width:74%;}
.sk-btn {width:96px; height:40px; border-radius:var(--r-pill);}
@keyframes shimmer {0% {background-position:200% 0;} 100% {background-position:-200% 0;}}

/* ---------- estado vazio ---------- */
.vazio {text-align:center; padding:var(--s4) var(--s3); background:var(--surface); border:1px dashed var(--line-2);
  border-radius:var(--r-card);}
.vazio-ico {width:48px; height:48px; margin:0 auto var(--s2); border-radius:50%; display:flex; align-items:center;
  justify-content:center; background:var(--brand-soft); color:var(--brand-d);}
.vazio h4 {margin:0 0 4px; font-size:1.05rem;}
.vazio p {margin:0 auto; max-width:420px; color:var(--t2); font-size:.92rem;}

/* ---------- acessibilidade ---------- */
@media (prefers-reduced-motion: reduce) {* {transition:none !important; animation:none !important;}}
@media (max-width:768px) {
  .block-container {padding-left:var(--s2); padding-right:var(--s2);}
  .card, .kpi, .mini {padding:var(--s2);}
  .hero2 h1 {font-size:1.7rem;}
}
</style>"""