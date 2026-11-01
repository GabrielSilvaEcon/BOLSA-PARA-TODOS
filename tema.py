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
    "casa": "<path d='M3 11 12 4l9 7'/><path d='M5 10v9a1 1 0 0 0 1 1h4v-6h4v6h4a1 1 0 0 0 1-1v-9'/>",
    "alvo": "<circle cx='12' cy='12' r='8.5'/><circle cx='12' cy='12' r='4.5'/><circle cx='12' cy='12' r='.8'/>",
    "calc": "<rect x='5' y='3' width='14' height='18' rx='2'/><path d='M8 7h8M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01'/>",
    "balanca": "<path d='M12 4v16M7 20h10M5 7h14'/><path d='m5 7-3 7a3 3 0 0 0 6 0zM19 7l-3 7a3 3 0 0 0 6 0z'/>",
    "dinheiro": "<rect x='3' y='6' width='18' height='12' rx='2'/><circle cx='12' cy='12' r='2.5'/><path d='M6.5 9.5v.01M17.5 14.5v.01'/>",
    "predio": "<path d='M4 21V5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1v16'/><path d='M14 10h5a1 1 0 0 1 1 1v10M3 21h18M8 8h2M8 12h2M8 16h2'/>",
    "trofeu": "<path d='M8 4h8v5a4 4 0 0 1-8 0z'/><path d='M8 6H5a1 1 0 0 0-1 1c0 2 1.5 3.5 4 4M16 6h3a1 1 0 0 1 1 1c0 2-1.5 3.5-4 4M12 13v4M8.5 20h7M10 17h4'/>",
    "globo": "<circle cx='12' cy='12' r='8.5'/><path d='M3.5 12h17M12 3.5c2.5 2.5 3.5 5.5 3.5 8.5s-1 6-3.5 8.5c-2.5-2.5-3.5-5.5-3.5-8.5s1-6 3.5-8.5z'/>",
    "usuario": "<circle cx='12' cy='8' r='3.5'/><path d='M5 20c0-3.5 3-6 7-6s7 2.5 7 6'/>",
    "ajuda": "<circle cx='12' cy='12' r='8.5'/><path d='M9.5 9.5a2.5 2.5 0 1 1 3.5 2.3c-.7.4-1 .9-1 1.7M12 17h.01'/>",
    "robo": "<rect x='5' y='8' width='14' height='11' rx='3'/><path d='M12 4v4M9 13h.01M15 13h.01M9.5 16.5h5'/>",
}
_EMOJI_ICONE = {"🏠": "casa", "🎯": "alvo", "🧮": "calc", "⚖": "balanca", "💰": "dinheiro", "🏢": "predio", "📉": "grafico",
                "📈": "grafico", "🏆": "trofeu", "🌐": "globo", "💼": "carteira", "🪙": "moeda", "👤": "usuario",
                "❓": "ajuda", "🤖": "robo", "🧭": "bussola"}



def icone(nome: str, tam: int = 20) -> str:
    corpo = _ICONES.get(nome, _ICONES["bussola"])
    return (f"<svg class='ico' width='{tam}' height='{tam}' viewBox='0 0 24 24' fill='none' stroke='currentColor' "
            f"stroke-width='1.75' stroke-linecap='round' stroke-linejoin='round' aria-hidden='true'>{corpo}</svg>")


def cabecalho(icone_ou_emoji: str, titulo: str, sub: str = "") -> str:
    """Cabeçalho de página: ícone de linha num bloco com brilho, título em degradê e linha de apoio."""
    chave = (icone_ou_emoji or "").replace("\ufe0f", "")
    nome = _EMOJI_ICONE.get(chave) or (chave if chave in _ICONES else None)
    ico = f"<span class='pgi'>{icone(nome, 22)}</span>" if nome else (html.escape(chave) + " " if chave else "")
    s = f"<div class='pgsub'>{html.escape(sub)}</div>" if sub else ""
    return f"<div class='pghead'><div class='pgt'>{ico}{html.escape(titulo)}</div>{s}</div>"


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


def card_status(label: str, valor: str, cls: str = "info", detalhe: str = "", dica: str = "") -> str:
    """Card com cor de status: cls = good (verde), fair (âmbar), bad (vermelho), info (azul) ou na (cinza)."""
    d = f"<div class='sc-d'>{html.escape(detalhe)}</div>" if detalhe else ""
    tt = f" title='{html.escape(dica, quote=True)}'" if dica else ""
    return (f"<div class='sc {cls}'{tt}><div class='sc-l'>{html.escape(label)}</div>"
            f"<div class='sc-v'>{html.escape(valor)}</div>{d}</div>")


def css() -> str:
    return """<style>
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@500;700&display=swap');
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

/* ================= assinatura visual (mais presença de marca) ================= */
.stApp {background:
  radial-gradient(900px 480px at 100% -8%, rgba(59,107,196,.13), transparent 62%),
  radial-gradient(760px 460px at -8% 12%, rgba(31,122,85,.12), transparent 60%),
  linear-gradient(180deg,#F5F7FA 0%,#EEF2F3 100%) !important;}
header[data-testid="stHeader"] {box-shadow:0 1px 0 var(--line), 0 8px 24px -16px rgba(14,42,92,.25);}
header[data-testid="stHeader"]::after {content:""; position:absolute; left:0; right:0; bottom:-1px; height:3px;
  background:linear-gradient(90deg,#0E2A5C 0%,#1F7A55 55%,#C9A227 100%);}
.pgt, .hero2 h1 {background:linear-gradient(95deg,#0E2A5C 0%,#1F7A55 85%); -webkit-background-clip:text;
  background-clip:text; -webkit-text-fill-color:transparent; color:transparent;}
.pgt {font-size:1.75rem;}
.hero2 {padding:var(--s4) var(--s2) var(--s1);}
.sec {display:flex; align-items:center; gap:var(--s1); font-size:1.1rem; letter-spacing:-.01em;}
.sec::before {content:""; width:4px; height:20px; border-radius:var(--r-pill); background:linear-gradient(180deg,#1F7A55,#3B6BC4);}
.card, .kpi, .mini {background:linear-gradient(180deg,#FFFFFF 0%,var(--surface) 100%) !important;
  box-shadow:inset 0 3px 0 rgba(31,122,85,.55), var(--sh1) !important;}
.mini {box-shadow:inset 0 3px 0 rgba(59,107,196,.45), var(--sh1) !important;}
.card:hover, .kpi:hover, .mini:hover {box-shadow:inset 0 3px 0 var(--brand), var(--sh2) !important;}
.kpi .v, .val {color:var(--t1); font-size:1.4rem;}
.st-key-ctx_bar, .st-key-trilha_bar, .st-key-nav_desktop, .st-key-nav_mobile {
  background:rgba(255,255,255,.78) !important; backdrop-filter:blur(8px); border:1px solid var(--line-2) !important;
  box-shadow:var(--sh1) !important;}
.st-key-nav_desktop a[aria-current="page"], .st-key-trilha_bar a[aria-current="page"] {
  background:linear-gradient(180deg,var(--brand),var(--brand-d)) !important; border-color:var(--brand-d) !important;
  box-shadow:0 6px 14px -6px rgba(31,122,85,.6);}
.st-key-nav_desktop a[aria-current="page"] p, .st-key-nav_desktop a[aria-current="page"] span {color:#fff !important;}
.stButton > button, .stFormSubmitButton > button {min-height:44px !important; background:#fff !important;
  border:1px solid var(--line-2) !important; box-shadow:var(--sh1) !important;}
.stButton > button:hover, .stFormSubmitButton > button:hover {border-color:var(--brand) !important;
  background:var(--brand-soft) !important; transform:translateY(-1px);}
button[data-testid^="stBaseButton-primary"]:hover {background:linear-gradient(180deg,var(--brand),var(--brand-d)) !important;}
[data-baseweb="input"], [data-baseweb="select"] > div {background:#fff !important; min-height:44px;}
.chip, .stp span {background:#fff;}
.stp span.on {background:linear-gradient(180deg,var(--brand),var(--brand-d)); box-shadow:0 6px 14px -6px rgba(31,122,85,.6);}
[data-testid="stExpander"] {background:#fff;}

/* ================= estrutura: cabeçalhos, início, gráficos e navegação ================= */
.pghead {position:relative; overflow:hidden; margin:0 0 var(--s3); padding:var(--s3);
  background:linear-gradient(135deg,rgba(14,42,92,.07),rgba(31,122,85,.10)); border:1px solid var(--line);
  border-radius:20px; box-shadow:var(--sh1);}
.pghead::after {content:""; position:absolute; right:-24px; top:-24px; width:160px; height:160px; opacity:.5; pointer-events:none;
  background:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' viewBox='-100 -100 200 200'><g fill='none' stroke='rgba(31,122,85,.35)' stroke-width='1'><circle r='92'/><circle r='64' stroke-dasharray='3 4'/></g><polygon points='0,-92 10,-10 0,0 -10,-10' fill='rgba(31,122,85,.35)'/><polygon points='0,92 10,10 0,0 -10,10' fill='rgba(31,122,85,.35)'/><polygon points='92,0 10,-10 0,0 10,10' fill='rgba(59,107,196,.35)'/><polygon points='-92,0 -10,-10 0,0 -10,10' fill='rgba(59,107,196,.35)'/></svg>") center/contain no-repeat;}
.pgt {font-size:clamp(1.45rem, 1rem + 1.6vw, 1.95rem); position:relative;}
.pgsub {font-size:clamp(.88rem, .8rem + .3vw, 1rem); position:relative; max-width:640px;}

/* início: banner com a busca flutuando por cima */
.hero2 {position:relative; overflow:hidden; border-radius:24px; padding:var(--s5) var(--s3) 88px;
  background:radial-gradient(520px 260px at 90% 0%,rgba(201,162,39,.28),transparent 70%),
             linear-gradient(135deg,#0E2A5C 0%,#164A8F 55%,#17604A 120%);
  box-shadow:0 24px 48px -24px rgba(14,42,92,.55);}
.hero2 h1 {background:none !important; -webkit-text-fill-color:#fff !important; color:#fff !important;
  font-size:clamp(1.6rem, 1rem + 2.4vw, 2.5rem); margin:0 0 var(--s1);}
.hero2 p {color:rgba(255,255,255,.82) !important; max-width:520px; margin:0 auto;}
.st-key-home_busca_box {position:relative; z-index:2; margin:-56px auto 0 !important; padding:var(--s2) !important;
  background:#fff; border:1px solid var(--line); border-radius:20px; box-shadow:var(--sh2);}

/* gráficos e tabelas viram cartões */
[data-testid="stPlotlyChart"] {background:#fff; border:1px solid var(--line); border-radius:var(--r-card);
  padding:var(--s1); box-shadow:var(--sh1); overflow:hidden;}

/* grade responsiva: 3 ou mais colunas passam a 2 por linha em tablets (menos o que tem layout próprio) */
@media (min-width:641px) and (max-width:1100px) {
  [data-testid="stMain"] [data-testid="stHorizontalBlock"]:not(:is(.st-key-nav_desktop, .st-key-nav_mobile,
    .st-key-nav_bottom, .st-key-ctx_bar, .st-key-trilha_bar, .st-key-login_card) *):has(> [data-testid="stColumn"]:nth-child(3)) {
    flex-wrap:wrap !important; row-gap:var(--s2);}
  [data-testid="stMain"] [data-testid="stHorizontalBlock"]:not(:is(.st-key-nav_desktop, .st-key-nav_mobile,
    .st-key-nav_bottom, .st-key-ctx_bar, .st-key-trilha_bar, .st-key-login_card) *):has(> [data-testid="stColumn"]:nth-child(3))
    > [data-testid="stColumn"] {flex:1 1 calc(50% - var(--s2)) !important; min-width:calc(50% - var(--s2)) !important;}
}

/* barra de abas fixa (celular e tablet) */
.st-key-nav_bottom {display:none;}
@media (max-width:1100px) {
  .st-key-nav_bottom {display:block; position:fixed; left:12px; right:12px; z-index:1000;
    bottom:calc(12px + env(safe-area-inset-bottom, 0px)); padding:6px; border-radius:22px;
    background:rgba(255,255,255,.92); backdrop-filter:saturate(1.4) blur(16px);
    border:1px solid var(--line-2); box-shadow:0 18px 40px -12px rgba(14,42,92,.40);}
  .block-container {padding-bottom:7.5rem !important;}
}
.st-key-nav_bottom [data-testid="stHorizontalBlock"] {flex-wrap:nowrap !important; gap:4px !important;}
.st-key-nav_bottom [data-testid="stColumn"], .st-key-nav_bottom [data-testid="column"] {
  min-width:0 !important; flex:1 1 0 !important; width:auto !important;}
.st-key-nav_bottom button, .st-key-nav_bottom a[data-testid="stPageLink-NavLink"] {
  width:100%; min-height:44px; border:none !important; background:transparent !important; box-shadow:none !important;
  border-radius:16px; justify-content:center; padding:0 2px !important; gap:4px;}
.st-key-nav_bottom p {font-size:.7rem !important; font-weight:700 !important; margin:0; white-space:nowrap;
  overflow:hidden; text-overflow:ellipsis;}
.st-key-nav_bottom a[aria-current="page"] {background:var(--brand-soft) !important;}
.st-key-nav_bottom a[aria-current="page"] p {color:var(--brand-d) !important;}

/* ================= camada tecnológica: vidro, brilho, bordas em degradê, números em mono ================= */
:root {--mono:'JetBrains Mono','IBM Plex Mono',ui-monospace,SFMono-Regular,Menlo,monospace;
  --grad:linear-gradient(135deg,rgba(31,122,85,.65),rgba(59,107,196,.65));}
.stApp {background:
  radial-gradient(rgba(22,32,43,.055) 1px, transparent 1.2px) 0 0/22px 22px,
  radial-gradient(900px 480px at 100% -8%, rgba(59,107,196,.14), transparent 62%),
  radial-gradient(760px 460px at -8% 12%, rgba(31,122,85,.13), transparent 60%),
  linear-gradient(180deg,#F5F7FA 0%,#EEF2F3 100%) !important;}
.kpi .v, .val, [data-testid="stMetricValue"], .tk {font-family:var(--mono); letter-spacing:-.02em; font-weight:700;}
.lbl, [data-testid="stMetricLabel"] p {font-family:var(--mono); font-size:.66rem; letter-spacing:.1em;}

/* botões secundários: fundo branco com borda em degradê e brilho no hover */
.stButton > button[data-testid^="stBaseButton-secondary"], .stFormSubmitButton > button[data-testid^="stBaseButton-secondary"],
.stDownloadButton > button, a[data-testid="stPageLink-NavLink"]:not(.nav-x), button[data-testid="stPopoverButton"] {
  background:linear-gradient(#fff,#fff) padding-box, var(--grad) border-box !important;
  border:1px solid transparent !important; color:var(--t1); font-weight:700; letter-spacing:.01em;
  box-shadow:0 1px 2px rgba(22,32,43,.05), 0 8px 18px -12px rgba(31,122,85,.45) !important;}
.stButton > button[data-testid^="stBaseButton-secondary"]:hover, .stFormSubmitButton > button[data-testid^="stBaseButton-secondary"]:hover,
a[data-testid="stPageLink-NavLink"]:not(.nav-x):hover, button[data-testid="stPopoverButton"]:hover {
  background:linear-gradient(var(--brand-soft),var(--brand-soft)) padding-box, var(--grad) border-box !important;
  box-shadow:0 0 0 4px rgba(31,122,85,.10), 0 14px 28px -12px rgba(31,122,85,.55) !important; transform:translateY(-1px);}
/* menus e barras mantêm o visual limpo (sem borda em degradê) */
.st-key-nav_desktop button, .st-key-nav_mobile button, .st-key-nav_bottom button,
.st-key-nav_desktop a[data-testid="stPageLink-NavLink"], .st-key-nav_bottom a[data-testid="stPageLink-NavLink"],
[data-testid="stPopoverBody"] a[data-testid="stPageLink-NavLink"] {background:transparent !important; border:none !important; box-shadow:none !important;}
.st-key-trilha_bar a[data-testid="stPageLink-NavLink"] {border:1px solid var(--line) !important; background:#fff !important; box-shadow:none !important;}

/* botão principal: degradê com brilho (corrige o texto invisível do "Buscar") */
.stButton > button[data-testid^="stBaseButton-primary"], .stFormSubmitButton > button[data-testid^="stBaseButton-primary"] {
  background:linear-gradient(135deg,#1F7A55 0%,#17604A 55%,#1B5C8F 130%) !important; border:1px solid rgba(255,255,255,.12) !important;
  color:#fff !important; font-weight:800; letter-spacing:.02em;
  box-shadow:inset 0 1px 0 rgba(255,255,255,.28), 0 10px 24px -10px rgba(31,122,85,.75) !important;}
.stButton > button[data-testid^="stBaseButton-primary"] p, .stFormSubmitButton > button[data-testid^="stBaseButton-primary"] p {
  color:#fff !important;}
.stButton > button[data-testid^="stBaseButton-primary"]:hover, .stFormSubmitButton > button[data-testid^="stBaseButton-primary"]:hover {
  filter:brightness(1.08); box-shadow:inset 0 1px 0 rgba(255,255,255,.3), 0 0 0 4px rgba(31,122,85,.14), 0 16px 30px -10px rgba(31,122,85,.8) !important;}

/* campos: fundo em vidro, leve sombra interna e brilho no foco */
[data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
  background:rgba(255,255,255,.9) !important; box-shadow:inset 0 1px 2px rgba(22,32,43,.06) !important;}
[data-baseweb="input"]:focus-within, [data-baseweb="select"] > div:focus-within {
  border-color:var(--brand) !important; box-shadow:0 0 0 4px rgba(31,122,85,.14), 0 10px 24px -14px rgba(31,122,85,.6) !important;}
[data-testid="stForm"] {background:rgba(255,255,255,.72); backdrop-filter:blur(10px); border:1px solid var(--line-2) !important;
  border-radius:var(--r-card); box-shadow:var(--sh1);}

/* abas e controle segmentado em formato de cápsula */
.stTabs [data-baseweb="tab-list"] {background:rgba(22,32,43,.05); padding:4px; border-radius:var(--r-pill); border-bottom:none; gap:4px; width:fit-content;}
.stTabs [data-baseweb="tab-highlight"], .stTabs [data-baseweb="tab-border"] {display:none !important;}
.stTabs [data-baseweb="tab"] {border-radius:var(--r-pill); padding:6px 16px; height:auto;}
.stTabs [aria-selected="true"] {background:#fff; color:var(--brand-d) !important; box-shadow:0 2px 6px rgba(22,32,43,.10), 0 0 0 1px var(--line);}
button[data-testid^="stBaseButton-segmented_control"] {border-radius:var(--r-pill) !important; min-height:40px; font-weight:700;
  border:1px solid var(--line-2) !important; background:rgba(255,255,255,.85) !important; transition:var(--ease);}
button[data-testid="stBaseButton-segmented_controlActive"] {background:linear-gradient(135deg,#1F7A55,#17604A) !important;
  color:#fff !important; border-color:transparent !important; box-shadow:0 8px 18px -8px rgba(31,122,85,.7) !important;}
button[data-testid="stBaseButton-segmented_controlActive"] p {color:#fff !important;}

/* cartões com brilho de borda no hover */
.card:hover, .kpi:hover, .mini:hover, [data-testid="stMetric"]:hover {
  box-shadow:inset 0 3px 0 var(--brand), 0 0 0 1px rgba(31,122,85,.28), var(--sh2) !important;}

/* ================= ícones: bloco do cabeçalho e ícones Material do menu ================= */
.pgi {display:inline-flex; align-items:center; justify-content:center; width:40px; height:40px; margin-right:12px;
  vertical-align:middle; border-radius:12px; background:#fff; border:1px solid var(--line); color:var(--brand-d);
  -webkit-text-fill-color:initial; box-shadow:0 1px 2px rgba(22,32,43,.05), 0 8px 16px -10px rgba(31,122,85,.55);}
.pgi svg {display:block;}
[data-testid="stIconMaterial"] {color:var(--t2); font-size:1.3rem !important; transition:var(--ease);}
a[data-testid="stPageLink-NavLink"]:hover [data-testid="stIconMaterial"], button:hover [data-testid="stIconMaterial"] {color:var(--brand);}
a[aria-current="page"] [data-testid="stIconMaterial"] {color:var(--brand-d);}
.st-key-nav_desktop a[aria-current="page"] [data-testid="stIconMaterial"] {color:#fff;}
.st-key-nav_bottom a[data-testid="stPageLink-NavLink"] {flex-direction:column !important; gap:2px !important; min-height:52px !important;}
.st-key-nav_bottom button p {display:flex !important; flex-direction:column; align-items:center; gap:2px; line-height:1.1; margin:0;}
.st-key-nav_bottom [data-testid="stIconMaterial"] {font-size:1.5rem !important;}
.st-key-nav_bottom a[aria-current="page"] [data-testid="stIconMaterial"], .st-key-nav_bottom a[aria-current="page"] p {color:var(--brand-d) !important;}

/* preço atual ao escolher a ação (carteira) */
.pv {display:flex; align-items:center; gap:12px; margin:8px 0; padding:12px 16px; border-radius:14px;
  border:1px solid var(--line); background:linear-gradient(135deg,rgba(31,122,85,.09),rgba(59,107,196,.09));}
.pv .dot {flex-shrink:0; width:9px; height:9px; border-radius:50%; background:var(--brand); animation:pvpulse 1.8s infinite;}
.pv-t {font-weight:800; color:var(--t1);} .pv-s {color:var(--t2); font-size:.9rem; line-height:1.5;}
.pv-s b {font-family:var(--mono); color:var(--t1);}
@keyframes pvpulse {0% {box-shadow:0 0 0 0 rgba(31,122,85,.55);} 70% {box-shadow:0 0 0 9px rgba(31,122,85,0);} 100% {box-shadow:0 0 0 0 rgba(31,122,85,0);}}

/* ---------- acessibilidade ---------- */
@media (prefers-reduced-motion: reduce) {* {transition:none !important; animation:none !important;}}
@media (max-width:768px) {
  .block-container {padding-left:var(--s2); padding-right:var(--s2);}
  .card, .kpi, .mini {padding:var(--s2);}
  .hero2 h1 {font-size:1.7rem;}
}

/* ================= paleta unificada: verde (positivo), âmbar (atenção), vermelho (negativo), azul (neutro) ================= */
:root {--good:#1F7A55; --fair:#B7791F; --bad:#C0392B; --info:#3B6BC4; --na:#788494; --navy:#0E2A5C;}
.sc {position:relative; overflow:hidden; border-radius:var(--r-card); padding:16px 18px 16px 22px;
  background:linear-gradient(135deg,var(--c-bg) 0%,#fff 72%) !important; border:1px solid var(--c-line);
  box-shadow:var(--sh1); transition:var(--ease); margin-bottom:var(--s1);}
.sc::before {content:""; position:absolute; left:0; top:0; bottom:0; width:5px; background:var(--c);}
.sc:hover {box-shadow:var(--sh2); transform:translateY(-1px);}
.sc.good {--c:var(--good); --c-bg:rgba(31,122,85,.13); --c-line:rgba(31,122,85,.30);}
.sc.fair {--c:var(--fair); --c-bg:rgba(183,121,31,.14); --c-line:rgba(183,121,31,.32);}
.sc.bad  {--c:var(--bad);  --c-bg:rgba(192,57,43,.12);  --c-line:rgba(192,57,43,.30);}
.sc.info {--c:var(--info); --c-bg:rgba(59,107,196,.12); --c-line:rgba(59,107,196,.28);}
.sc.na   {--c:var(--na);   --c-bg:rgba(120,132,148,.10); --c-line:rgba(120,132,148,.26);}
.sc-l {font-family:var(--mono); font-size:.66rem; letter-spacing:.1em; text-transform:uppercase; font-weight:700; color:var(--t2);}
.sc-v {font-family:var(--mono); font-size:clamp(1.3rem,1rem + 1vw,1.8rem); font-weight:700; letter-spacing:-.02em;
  color:var(--c); margin-top:4px; line-height:1.2; -webkit-text-fill-color:var(--c);}
.sc-d {font-size:.84rem; color:var(--t2); margin-top:6px; line-height:1.5;}
.sc.tend .sc-v {font-size:clamp(1.6rem,1.1rem + 1.4vw,2.2rem);}
.sec-sub {display:flex; align-items:center; gap:8px; margin:var(--s2) 0 var(--s1); font-weight:800; color:var(--navy);
  font-size:1rem; letter-spacing:-.01em;}
.sec-sub::before {content:""; width:8px; height:8px; border-radius:50%; background:var(--c-sec,var(--info));
  box-shadow:0 0 0 4px rgba(59,107,196,.14);}
.sec-sub.v {--c-sec:var(--good);} .sec-sub.v::before {box-shadow:0 0 0 4px rgba(31,122,85,.16);}

/* métricas nativas do Streamlit: cartão com faixa colorida e valor em azul-marinho */
[data-testid="stMetric"] {position:relative; overflow:hidden; padding:16px 18px 16px 22px;
  background:linear-gradient(135deg,rgba(59,107,196,.10) 0%,#fff 72%) !important; border:1px solid rgba(59,107,196,.25);}
[data-testid="stMetric"]::before {content:""; position:absolute; left:0; top:0; bottom:0; width:5px;
  background:linear-gradient(180deg,var(--info),var(--brand));}
[data-testid="stMetricValue"] {color:var(--navy);}

/* alertas do Streamlit com cores da paleta */
[data-testid="stAlert"] {border-left-width:5px; border-left-style:solid;}
div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {
  background:linear-gradient(90deg,rgba(31,122,85,.13),rgba(31,122,85,.04)); border-color:rgba(31,122,85,.30); border-left-color:var(--good);}
div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {
  background:linear-gradient(90deg,rgba(183,121,31,.16),rgba(183,121,31,.05)); border-color:rgba(183,121,31,.32); border-left-color:var(--fair);}
div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {
  background:linear-gradient(90deg,rgba(192,57,43,.14),rgba(192,57,43,.04)); border-color:rgba(192,57,43,.30); border-left-color:var(--bad);}
div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {
  background:linear-gradient(90deg,rgba(59,107,196,.13),rgba(59,107,196,.04)); border-color:rgba(59,107,196,.28); border-left-color:var(--info);}

/* formulário de compra da carteira: cartão com topo colorido e rótulos em destaque */
[class*="st-key-form_"] {position:relative; overflow:hidden; background:linear-gradient(135deg,rgba(31,122,85,.09) 0%,#fff 55%,rgba(59,107,196,.08) 100%) !important;
  border:1px solid rgba(31,122,85,.26) !important; border-radius:20px !important; box-shadow:var(--sh1); padding:var(--s1) var(--s1) var(--s2);}
[class*="st-key-form_"]::before {content:""; position:absolute; left:0; right:0; top:0; height:4px;
  background:linear-gradient(90deg,var(--navy),var(--brand) 60%,#C9A227);}
[class*="st-key-form_"] label p, [class*="st-key-form_"] [data-testid="stWidgetLabel"] p {color:var(--navy) !important; font-weight:800; font-size:.86rem;}
[class*="st-key-form_"] [data-baseweb="input"], [class*="st-key-form_"] [data-baseweb="select"] > div {
  border:1px solid rgba(14,42,92,.18) !important; background:#fff !important;}

/* gráfico técnico: cartão branco sem moldura dupla */
[data-testid="stPlotlyChart"] {padding:0; border-color:rgba(14,42,92,.14);}

/* ================= barra lateral (botão ☰) ================= */
.st-key-nav_mobile {display:block !important;}
.st-key-nav_desktop, .st-key-nav_bottom {display:none !important;}
.block-container {padding-bottom:3rem !important;}
[data-testid="stExpandSidebarButton"], [data-testid="stSidebarCollapsedControl"] button, [data-testid="collapsedControl"] button {
  position:relative; width:44px; height:44px; border-radius:12px !important; background:#fff !important;
  border:1px solid var(--line-2) !important; box-shadow:var(--sh1); color:transparent !important; font-size:0 !important;}
[data-testid="stExpandSidebarButton"] > *, [data-testid="stSidebarCollapsedControl"] button > *,
[data-testid="collapsedControl"] button > * {display:none !important;}
[data-testid="stExpandSidebarButton"]::after, [data-testid="stSidebarCollapsedControl"] button::after,
[data-testid="collapsedControl"] button::after {content:"☰"; position:absolute; inset:0; display:flex; align-items:center;
  justify-content:center; font-size:1.5rem; color:var(--navy);}
section[data-testid="stSidebar"] {background:linear-gradient(180deg,#0E2A5C 0%,#123F6E 55%,#17604A 130%) !important;
  border-right:none; box-shadow:12px 0 32px -16px rgba(14,42,92,.5);}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding:var(--s2) var(--s1);}
section[data-testid="stSidebar"] .hero {color:#fff !important; -webkit-text-fill-color:#fff;}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {background:transparent !important; border:none !important;
  box-shadow:none !important; border-radius:12px; padding:.55rem .75rem; margin:2px 0;}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p, section[data-testid="stSidebar"] [data-testid="stIconMaterial"] {
  color:rgba(255,255,255,.88) !important; font-weight:700;}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {background:rgba(255,255,255,.12) !important; transform:none;}
section[data-testid="stSidebar"] a[aria-current="page"] {background:rgba(255,255,255,.20) !important;
  box-shadow:inset 3px 0 0 #C9A227 !important;}
section[data-testid="stSidebar"] a[aria-current="page"] p {color:#fff !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] {background:rgba(255,255,255,.06) !important; border:1px solid rgba(255,255,255,.14) !important;
  box-shadow:none; border-radius:14px !important; margin:2px 0;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {background:rgba(255,255,255,.10);}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p, section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
  color:#fff !important; font-weight:800;}
.nav-sec {margin:var(--s2) 0 4px 12px; font-family:var(--mono); font-size:.66rem; letter-spacing:.14em; text-transform:uppercase;
  font-weight:700; color:#C9A227;}
</style>"""
