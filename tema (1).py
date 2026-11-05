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


def legenda_tendencia() -> str:
    """Selos que explicam Alta / Lateral / Baixa, no padrão de cores do app."""
    itens = [("good", "▲", "Alta", "subindo"), ("fair", "►", "Lateral", "de lado"), ("bad", "▼", "Baixa", "caindo")]
    chips = "".join(f"<span class='lg {c}'><i>{ic}</i><b>{n}</b><em>{d}</em></span>" for c, ic, n, d in itens)
    return (f"<div class='legenda'>{chips}<span class='lg-nota'>Sinais são indicadores técnicos e podem errar. "
            "Não são recomendação.</span></div>")


def cartao(conteudo: str, extra: str = "") -> str:
    """Envolve HTML no card padrão (gradiente azul-marinho → azul-petróleo, raio 20px, sombra suave).
    Uso: st.markdown(tema.cartao("<h4>Título</h4><p>Texto</p>"), unsafe_allow_html=True)"""
    return f"<div class='cartao {extra}'>{conteudo}</div>"


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
.stTabs [aria-selected="true"] *, .stTabs [aria-selected="true"] p {color:#17604A !important;}   /* texto legível sobre o fundo branco, também no tema escuro */
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

/* ================= marca em texto (logotipo) ================= */
.wm {display:flex; align-items:center; gap:10px; line-height:1.15; padding:2px 0; overflow:visible;}
.wm svg {flex-shrink:0; filter:drop-shadow(0 4px 8px rgba(31,122,85,.30));}
.wm-t {font-weight:800; font-size:1.3rem; letter-spacing:-.025em; white-space:nowrap;
  background:linear-gradient(95deg,#0E2A5C 10%,#1F7A55 90%); -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color:transparent; color:transparent; display:inline-flex; align-items:center;}
.wm-t b {font-family:var(--mono); font-size:.62em; font-weight:700; letter-spacing:.06em; margin-left:8px; padding:3px 8px;
  border-radius:8px; background:linear-gradient(135deg,#0E2A5C,#1F7A55); -webkit-text-fill-color:#fff; color:#fff;
  box-shadow:0 6px 14px -6px rgba(14,42,92,.6);}
section[data-testid="stSidebar"] .wm-t {background:none; -webkit-text-fill-color:#fff; color:#fff;}
section[data-testid="stSidebar"] .wm-t b {background:linear-gradient(135deg,#C9A227,#E3C55A); -webkit-text-fill-color:#0E2A5C; color:#0E2A5C;}
.st-key-nav_mobile {overflow:visible !important; padding:10px 16px !important;}
.st-key-nav_mobile [data-testid="stColumn"], .st-key-nav_mobile [data-testid="column"] {overflow:visible !important;}

/* legenda Alta / Lateral / Baixa */
.legenda {display:flex; flex-wrap:wrap; align-items:center; gap:10px; margin:-8px 0 var(--s2);}
.lg {display:inline-flex; align-items:center; gap:8px; padding:6px 14px 6px 10px; border-radius:var(--r-pill);
  border:1px solid var(--c-line); background:linear-gradient(135deg,var(--c-bg),#fff 85%); box-shadow:var(--sh1);}
.lg i {font-style:normal; display:inline-flex; align-items:center; justify-content:center; width:22px; height:22px;
  border-radius:50%; background:var(--c); color:#fff; font-size:.7rem;}
.lg b {color:var(--c); font-weight:800; font-size:.92rem;}
.lg em {font-style:normal; color:var(--t2); font-size:.85rem; font-weight:600;}
.lg.good {--c:var(--good); --c-bg:rgba(31,122,85,.13); --c-line:rgba(31,122,85,.30);}
.lg.fair {--c:var(--fair); --c-bg:rgba(183,121,31,.14); --c-line:rgba(183,121,31,.32);}
.lg.bad {--c:var(--bad); --c-bg:rgba(192,57,43,.12); --c-line:rgba(192,57,43,.30);}
.lg-nota {font-size:.8rem; color:var(--t3); font-weight:600; margin-left:4px;}
.nav-user {margin:0 0 4px 12px; color:#fff; font-weight:800; font-size:.95rem;}
section[data-testid="stSidebar"] .stButton > button {background:rgba(255,255,255,.14) !important; border:1px solid rgba(255,255,255,.28) !important;
  box-shadow:none !important;}
section[data-testid="stSidebar"] .stButton > button p, section[data-testid="stSidebar"] .stButton > button [data-testid="stIconMaterial"] {color:#fff !important;}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] {color:rgba(255,255,255,.72) !important;}

/* ================= IDENTIDADE ESCURA · etapa 1: fundo azul-marinho e texto claro ================= */
:root {--bg:#0B1C33; --t1:#FFFFFF; --t2:#A0AEC0; --t3:#A0AEC0;
  --line:rgba(160,174,192,.18); --line-2:rgba(160,174,192,.30);}
html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"], [data-testid="stBottom"] > div {
  background:#0B1C33 !important; background-image:none !important;}
.stApp::before, .stApp::after {display:none !important;}
header[data-testid="stHeader"] {background:rgba(11,28,51,.92) !important; border-bottom:1px solid var(--line) !important;
  box-shadow:none !important;}

/* títulos em branco, texto de apoio em azul-cinza claro */
.stApp :is(h1,h2,h3,h4,h5,h6), .stApp .sec, .stApp .sec-sub, .stApp .tk, .stApp .val {color:#FFFFFF !important;}
.stApp :is(p, li, label) {color:#FFFFFF;}
.stApp [data-testid="stCaptionContainer"], .stApp small, .stApp .pgsub, .stApp .nm, .stApp .lbl, .stApp .lg-nota,
.stApp [data-testid="stCaptionContainer"] p {color:#A0AEC0 !important;}
.pgt, .hero2 h1 {background:none !important; -webkit-text-fill-color:#FFFFFF !important; color:#FFFFFF !important;}
/* títulos escritos com st.markdown("#### ...") e textos dos gráficos Plotly (cartão branco): cor explícita e legível */
.stApp [data-testid="stMarkdownContainer"] :is(h1,h2,h3,h4,h5,h6), .stApp [data-testid="stHeading"] :is(h1,h2,h3,h4,h5,h6),
.stApp [data-testid="stMarkdownContainer"] :is(h1,h2,h3,h4,h5,h6) *, .stApp [data-testid="stHeading"] :is(h1,h2,h3,h4,h5,h6) * {
  color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; opacity:1 !important;}   /* inclui o <span> interno, que o app.py pinta de escuro */
[data-testid="stPlotlyChart"] :is(.xtick, .ytick) text, [data-testid="stPlotlyChart"] :is(.g-xtitle, .g-ytitle, .gtitle) text,
[data-testid="stPlotlyChart"] .legendtext, [data-testid="stPlotlyChart"] .annotation-text, [data-testid="stPlotlyChart"] .textpoint text,
[data-testid="stPlotlyChart"] :is(.xtick, .ytick) tspan {fill:#16202B !important; opacity:1 !important;}
.pghead {background:linear-gradient(135deg,rgba(31,122,85,.20),rgba(59,107,196,.16)) !important; border:1px solid var(--line) !important;}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"], section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  color:#A0AEC0 !important;}

/* ================= etapa 2: CARD reutilizável (.cartao) e aplicação nos blocos de destaque ================= */
:root {--good:#3DDC97; --fair:#F2B84B; --bad:#FF6B6B; --info:#6EA8FF; --na:#A0AEC0;
  --card-bg:linear-gradient(180deg,#11294D 0%,#0D3546 100%); --card-sh:0px 10px 25px rgba(0,0,0,.3);}
.cartao,.card,.kpi,.mini,.ctx,.sc,.lg,.vazio,.pv,[data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stForm"],[class*="st-key-form_"],.st-key-ctx_bar,.st-key-trilha_bar,.st-key-nav_mobile,.st-key-home_busca_box {
  background:var(--card-bg) !important; border:1px solid rgba(160,174,192,.14) !important;
  border-radius:20px !important; box-shadow:var(--card-sh) !important; backdrop-filter:none;}
.card,.kpi,.mini {box-shadow:inset 0 3px 0 rgba(61,220,151,.55), var(--card-sh) !important;}
.mini {box-shadow:inset 0 3px 0 rgba(110,168,255,.55), var(--card-sh) !important;}
:is(.cartao,.card,.kpi,.mini,.ctx,.sc,.lg,.vazio,.pv,[data-testid="stMetric"],[data-testid="stExpander"],[data-testid="stForm"],[class*="st-key-form_"],.st-key-ctx_bar,.st-key-trilha_bar,.st-key-nav_mobile,.st-key-home_busca_box):not(section[data-testid="stSidebar"] *):hover {border-color:rgba(160,174,192,.32) !important;
  box-shadow:0px 14px 32px rgba(0,0,0,.42) !important; transform:translateY(-1px);}
[data-testid="stExpander"] summary:hover {background:rgba(255,255,255,.05) !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] {border-radius:14px !important; box-shadow:none !important;
  background:rgba(255,255,255,.06) !important; border:1px solid rgba(255,255,255,.14) !important;}
/* cartões de status e selos: o tom da cor entra por cima do gradiente */
.sc {background:linear-gradient(135deg,var(--c-bg) 0%,transparent 70%), var(--card-bg) !important; border-color:var(--c-line) !important;}
.lg {background:linear-gradient(135deg,var(--c-bg) 0%,transparent 85%), var(--card-bg) !important; border-radius:999px !important;
  box-shadow:0 4px 12px rgba(0,0,0,.25) !important;}
.sc.good {--c-bg:rgba(61,220,151,.16); --c-line:rgba(61,220,151,.38);}
.sc.fair, .lg.fair {--c-bg:rgba(242,184,75,.16); --c-line:rgba(242,184,75,.38);}
.sc.bad, .lg.bad {--c-bg:rgba(255,107,107,.16); --c-line:rgba(255,107,107,.38);}
.sc.info {--c-bg:rgba(110,168,255,.16); --c-line:rgba(110,168,255,.38);}
.lg.good {--c-bg:rgba(61,220,151,.16); --c-line:rgba(61,220,151,.38);}
.sc.na {--c-bg:rgba(160,174,192,.10); --c-line:rgba(160,174,192,.26);}
[data-testid="stMetric"]::before {opacity:.9;}
[data-testid="stMetricValue"], [data-testid="stMetricValue"] div {color:#FFFFFF !important;}
[class*="st-key-form_"] label p, [class*="st-key-form_"] [data-testid="stWidgetLabel"] p {color:#FFFFFF !important;}
.vazio h4 {color:#FFFFFF !important;} .vazio p {color:#A0AEC0 !important;}
.sec-sub {color:#FFFFFF;}
.wm-t {background:linear-gradient(95deg,#FFFFFF 10%,#9FE3C4 95%) !important; -webkit-background-clip:text !important;
  background-clip:text !important; -webkit-text-fill-color:transparent !important;}
.wm-t b {background:linear-gradient(135deg,#C9A227,#E3C55A) !important; -webkit-text-fill-color:#0B1C33 !important; color:#0B1C33 !important;}
/* gráficos, alertas e tabelas: mesmo raio e sombra (o conteúdo interno continua claro) */
[data-testid="stPlotlyChart"],[data-testid="stAlert"],[data-testid="stDataFrame"],[data-testid="stTable"] {border-radius:20px !important; box-shadow:var(--card-sh) !important; overflow:hidden;}
[data-testid="stAlert"] {border:1px solid rgba(160,174,192,.18) !important;}
[data-baseweb="input"] input, [data-baseweb="textarea"] textarea, [data-baseweb="select"] * {
  color:#16202B !important; -webkit-text-fill-color:#16202B !important;}
/* lista aberta do selectbox: fundo escuro, então o texto das opções precisa ser claro */
html body [data-baseweb="popover"] :is(ul, li, [role="listbox"], [role="option"]),
html body [data-baseweb="popover"] :is(ul, li, [role="listbox"], [role="option"]) *,
html body [data-testid="stSelectboxVirtualDropdown"] *, html body [data-baseweb="menu"] * {
  color:#E8EEF5 !important; -webkit-text-fill-color:#E8EEF5 !important; opacity:1 !important;}
html body [data-baseweb="popover"] [role="option"][aria-selected="true"],
html body [data-baseweb="popover"] [role="option"]:hover {background:#2A4468 !important;}
.cartao {padding:var(--s3); margin-bottom:var(--s2);}
.cartao h1,.cartao h2,.cartao h3,.cartao h4 {margin-top:0;}

/* ================= etapa 3: BOTÕES ================= */
:root {--btn:#125C51; --btn-hover:#DDA735; --btn-ink:#0B1C33;}
/* principais: verde-petróleo, texto branco, pílula; no hover ficam dourados como o selo B3 */
.stApp .stButton > button[data-testid^="stBaseButton-primary"],
.stApp .stFormSubmitButton > button[data-testid^="stBaseButton-primary"] {
  background:var(--btn) !important; color:#FFFFFF !important; border:1px solid rgba(255,255,255,.16) !important;
  border-radius:25px !important; min-height:46px; padding:0 24px; font-weight:800; letter-spacing:.02em;
  box-shadow:0 10px 22px -10px rgba(18,92,81,.9) !important; transition:all .2s ease-in-out;}
.stApp .stButton > button[data-testid^="stBaseButton-primary"] :is(p, span, [data-testid="stIconMaterial"]),
.stApp .stFormSubmitButton > button[data-testid^="stBaseButton-primary"] :is(p, span, [data-testid="stIconMaterial"]) {color:#FFFFFF !important;}
.stApp .stButton > button[data-testid^="stBaseButton-primary"]:hover,
.stApp .stFormSubmitButton > button[data-testid^="stBaseButton-primary"]:hover {
  background:var(--btn-hover) !important; border-color:var(--btn-hover) !important; filter:none; transform:translateY(-1px);
  box-shadow:0 14px 26px -10px rgba(221,167,53,.75) !important;}
.stApp .stButton > button[data-testid^="stBaseButton-primary"]:hover :is(p, span, [data-testid="stIconMaterial"]),
.stApp .stFormSubmitButton > button[data-testid^="stBaseButton-primary"]:hover :is(p, span, [data-testid="stIconMaterial"]) {color:var(--btn-ink) !important;}

/* secundários e atalhos: pílulas flutuantes, fundo escuro translúcido */
.stApp .stButton > button[data-testid^="stBaseButton-secondary"],
.stApp .stFormSubmitButton > button[data-testid^="stBaseButton-secondary"],
.stApp .stDownloadButton > button,
.stApp .stLinkButton > a,
.stApp button[data-testid="stPopoverButton"],
.stApp [data-testid="stMain"] a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]),
.stApp .st-key-trilha_bar a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]),
.stApp button[data-testid="stBaseButton-segmented_control"] {
  background:rgba(17,41,77,.55) !important; color:#FFFFFF !important; border:1px solid rgba(160,174,192,.30) !important;
  border-radius:25px !important; min-height:42px; padding:0 20px; font-weight:700; backdrop-filter:blur(8px);
  box-shadow:0 10px 22px -8px rgba(0,0,0,.45) !important; transition:all .2s ease-in-out;}
.stApp .stButton > button[data-testid^="stBaseButton-secondary"] :is(p, span, [data-testid="stIconMaterial"]),
.stApp .stFormSubmitButton > button[data-testid^="stBaseButton-secondary"] :is(p, span, [data-testid="stIconMaterial"]),
.stApp .stDownloadButton > button :is(p, span, [data-testid="stIconMaterial"]),
.stApp .stLinkButton > a :is(p, span, [data-testid="stIconMaterial"]),
.stApp button[data-testid="stPopoverButton"] :is(p, span, [data-testid="stIconMaterial"]),
.stApp [data-testid="stMain"] a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]) :is(p, span, [data-testid="stIconMaterial"]),
.stApp .st-key-trilha_bar a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]) :is(p, span, [data-testid="stIconMaterial"]),
.stApp button[data-testid="stBaseButton-segmented_control"] :is(p, span, [data-testid="stIconMaterial"]) {color:#FFFFFF !important;}
.stApp .stButton > button[data-testid^="stBaseButton-secondary"]:hover,
.stApp .stFormSubmitButton > button[data-testid^="stBaseButton-secondary"]:hover,
.stApp .stDownloadButton > button:hover,
.stApp .stLinkButton > a:hover,
.stApp button[data-testid="stPopoverButton"]:hover,
.stApp [data-testid="stMain"] a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]):hover,
.stApp .st-key-trilha_bar a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]):hover,
.stApp button[data-testid="stBaseButton-segmented_control"]:hover {
  background:rgba(221,167,53,.14) !important; border-color:var(--btn-hover) !important; transform:translateY(-1px);
  box-shadow:0 14px 26px -8px rgba(0,0,0,.55), 0 0 0 3px rgba(221,167,53,.16) !important;}
.stApp .stButton > button[data-testid^="stBaseButton-secondary"]:hover :is(p, span, [data-testid="stIconMaterial"]),
.stApp .stFormSubmitButton > button[data-testid^="stBaseButton-secondary"]:hover :is(p, span, [data-testid="stIconMaterial"]),
.stApp .stDownloadButton > button:hover :is(p, span, [data-testid="stIconMaterial"]),
.stApp .stLinkButton > a:hover :is(p, span, [data-testid="stIconMaterial"]),
.stApp button[data-testid="stPopoverButton"]:hover :is(p, span, [data-testid="stIconMaterial"]),
.stApp [data-testid="stMain"] a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]):hover :is(p, span, [data-testid="stIconMaterial"]),
.stApp .st-key-trilha_bar a[data-testid="stPageLink-NavLink"]:not([aria-current="page"]):hover :is(p, span, [data-testid="stIconMaterial"]),
.stApp button[data-testid="stBaseButton-segmented_control"]:hover :is(p, span, [data-testid="stIconMaterial"]) {color:var(--btn-hover) !important;}
/* controle segmentado: opção ativa em verde-petróleo */
.stApp button[data-testid="stBaseButton-segmented_controlActive"] {background:var(--btn) !important; color:#FFFFFF !important;
  border:1px solid rgba(255,255,255,.16) !important; border-radius:25px !important; box-shadow:0 10px 22px -10px rgba(18,92,81,.9) !important;}
.stApp button[data-testid="stBaseButton-segmented_controlActive"]:hover {background:var(--btn-hover) !important;}
.stApp button[data-testid="stBaseButton-segmented_controlActive"]:hover p {color:var(--btn-ink) !important;}
.stApp button:disabled, .stApp button[disabled] {opacity:.5 !important; transform:none !important; box-shadow:none !important;}
.stApp button:focus-visible, .stApp a:focus-visible {outline:2px solid var(--btn-hover) !important; outline-offset:2px !important;}
/* menu lateral: botões da conta em pílula translúcida */
section[data-testid="stSidebar"] .stButton > button {background:rgba(255,255,255,.12) !important; border:1px solid rgba(255,255,255,.26) !important;
  border-radius:25px !important; box-shadow:none !important;}

/* menu lateral: item da página aberta em destaque; grupo "Análise fundamentalista" neutro quando fechado */
section[data-testid="stSidebar"] [class*="st-key-nav_on_"] a[data-testid="stPageLink-NavLink"] {
  background:rgba(255,255,255,.20) !important; box-shadow:inset 3px 0 0 #C9A227 !important;}
section[data-testid="stSidebar"] [class*="st-key-nav_on_"] a p {color:#FFFFFF !important;}
section[data-testid="stSidebar"] [class*="st-key-nav_"] {margin:0 !important;}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:.25rem;}
section[data-testid="stSidebar"] .st-key-nav_grp_off [data-testid="stExpander"] {background:transparent !important; border:1px solid transparent !important;}
section[data-testid="stSidebar"] .st-key-nav_grp_on [data-testid="stExpander"] {background:rgba(255,255,255,.07) !important;
  border:1px solid rgba(255,255,255,.18) !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {background:rgba(255,255,255,.10) !important;}

/* ================= Início: abas Ações B3 / Criptomoedas Binance no topo do card principal ================= */
.st-key-home_modo {position:relative; z-index:4; margin:0 0 -26px !important;}
.st-key-home_modo [data-testid="stButtonGroup"], .st-key-home_modo [role="radiogroup"] {
  justify-content:flex-start; width:fit-content; max-width:100%; overflow-x:auto; scrollbar-width:none; margin:0 auto; padding:4px; gap:4px; flex-wrap:nowrap;
  background:rgba(11,28,51,.94); border:1px solid rgba(160,174,192,.28); border-radius:999px;
  box-shadow:0 10px 25px rgba(0,0,0,.35);}
.st-key-home_modo button {border-radius:999px !important; min-height:40px; padding:0 16px; flex-shrink:0; box-shadow:none !important;
  background:transparent !important; border:1px solid transparent !important; font-weight:800;}
.st-key-home_modo button p {color:#A0AEC0 !important; font-weight:800; white-space:nowrap;}
.st-key-home_modo button[data-testid="stBaseButton-segmented_controlActive"] {
  background:#125C51 !important; border:1px solid rgba(61,220,151,.55) !important;}
.st-key-home_modo button[data-testid="stBaseButton-segmented_controlActive"] p {color:#FFFFFF !important;}
.st-key-home_modo button:hover {background:rgba(221,167,53,.14) !important; border-color:#DDA735 !important;}
.hero2.com-abas {padding-top:var(--s5);}
.hero2.com-abas h1 {margin-top:var(--s2);}
@media (max-width:640px) {.st-key-home_modo button {padding:0 12px; min-height:38px;} .st-key-home_modo button p {font-size:.82rem;}}
/* ================= Sidebar estática: navy sólido, hierarquia em 3 blocos, sem badges amarelos nem bordas pesadas ================= */
section[data-testid="stSidebar"] {background:#0B1C33 !important; border-right:1px solid rgba(160,174,192,.14) !important; box-shadow:none !important;}
section[data-testid="stSidebar"] [data-testid="stSidebarContent"] {padding:20px 12px 8px !important;}
section[data-testid="stSidebar"] [data-testid="stVerticalBlock"] {gap:2px !important;}
section[data-testid="stSidebar"] hr {margin:14px 6px !important; border:none !important; border-top:1px solid rgba(160,174,192,.16) !important;}
/* marca + subtítulo */
section[data-testid="stSidebar"] .wm {padding:0 6px;}
section[data-testid="stSidebar"] .wm-t b {background:rgba(18,92,81,.55) !important; -webkit-text-fill-color:#5EEAD4 !important; color:#5EEAD4 !important;
  border:1px solid rgba(94,234,212,.30); box-shadow:none;}
.nav-sub {margin:4px 0 0 52px; font-size:.7rem; letter-spacing:.12em; text-transform:uppercase; color:#718096; font-weight:600;}
/* legendas de seção (caption em caixa alta) */
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"], section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
  color:#5FA8A0 !important; font-size:.66rem !important; letter-spacing:.14em; font-weight:700 !important; margin:12px 0 2px 10px !important;}
/* itens: ícone nítido, padding confortável, sem caixas */
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {background:transparent !important; border:none !important; box-shadow:none !important;
  border-radius:10px !important; padding:.5rem .7rem !important; margin:0 !important; min-height:38px; gap:.7rem;}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p {color:#CBD5E0 !important; font-weight:600 !important; font-size:.92rem !important;}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] [data-testid="stIconMaterial"] {color:#8FA3BF !important; font-size:1.25rem !important;}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover {background:rgba(160,174,192,.10) !important;}
section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"]:hover p {color:#FFFFFF !important;}
/* item ativo: fundo teal suave, sem barra amarela */
section[data-testid="stSidebar"] [class*="st-key-nav_on_"] a[data-testid="stPageLink-NavLink"] {background:rgba(45,212,191,.13) !important; box-shadow:none !important;}
section[data-testid="stSidebar"] [class*="st-key-nav_on_"] a p {color:#FFFFFF !important; font-weight:700 !important;}
section[data-testid="stSidebar"] [class*="st-key-nav_on_"] a [data-testid="stIconMaterial"] {color:#2DD4BF !important;}
/* grupos recolhíveis (sub-itens) */
section[data-testid="stSidebar"] [class*="st-key-nav_grp_"] [data-testid="stExpander"] {background:transparent !important; border:none !important;
  box-shadow:none !important; border-radius:10px !important; margin:0 !important;}
section[data-testid="stSidebar"] [class*="st-key-nav_grp_on"] [data-testid="stExpander"] {background:rgba(160,174,192,.06) !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary {padding:.5rem .7rem !important; min-height:38px;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary p {color:#CBD5E0 !important; font-weight:600 !important; font-size:.92rem !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] summary svg, section[data-testid="stSidebar"] [data-testid="stExpander"] summary [data-testid="stIconMaterial"] {color:#8FA3BF !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] [data-testid="stExpanderDetails"] {padding:0 0 4px 12px !important;}
section[data-testid="stSidebar"] [data-testid="stExpander"] a[data-testid="stPageLink-NavLink"] {min-height:34px;}
section[data-testid="stSidebar"] [data-testid="stExpander"] a[data-testid="stPageLink-NavLink"] p {font-size:.86rem !important; font-weight:500 !important;}
/* rodapé fixo com a conta */
section[data-testid="stSidebar"] .st-key-nav_rodape {position:sticky; bottom:0; z-index:5; background:#0B1C33; padding-bottom:10px; margin-top:8px;}
.nav-user {display:flex; align-items:center; gap:8px; margin:0 0 2px 10px; color:#E2E8F0; font-weight:700; font-size:.88rem;}
.nav-user i {width:8px; height:8px; border-radius:50%; background:#2DD4BF; display:inline-block;}
section[data-testid="stSidebar"] .stButton > button[kind="tertiary"], section[data-testid="stSidebar"] .stButton > button {
  background:transparent !important; border:none !important; box-shadow:none !important; justify-content:flex-start; padding:.35rem .6rem !important; min-height:34px;}
section[data-testid="stSidebar"] .stButton > button p {color:#A0AEC0 !important; font-weight:600 !important; font-size:.85rem !important;}
section[data-testid="stSidebar"] .stButton > button [data-testid="stIconMaterial"] {color:#8FA3BF !important;}
section[data-testid="stSidebar"] .stButton > button:hover {background:rgba(160,174,192,.10) !important;}
section[data-testid="stSidebar"] .stButton > button:hover p {color:#FFFFFF !important;}
/* celular: alvos de toque maiores e sidebar de largura confortável; o ☰ abre a mesma sidebar do computador */
@media (max-width:640px) {
  section[data-testid="stSidebar"] {min-width:min(86vw,320px) !important; max-width:86vw !important;}
  section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] {min-height:44px !important; padding:.6rem .8rem !important;}
  section[data-testid="stSidebar"] a[data-testid="stPageLink-NavLink"] p {font-size:.98rem !important;}
  section[data-testid="stSidebar"] [data-testid="stExpander"] summary {min-height:44px;}
  section[data-testid="stSidebar"] [data-testid="stExpander"] a[data-testid="stPageLink-NavLink"] {min-height:42px !important;}
  section[data-testid="stSidebar"] .stButton > button {min-height:44px;}
}

/* ================= cards de resultado (.rc) e resumo executivo (.rs) ================= */
:is(.rc,.rs-top,.rs-box,.rs-concl) {--c:#6EA8FF; --c-bg:rgba(110,168,255,.14); --c-line:rgba(110,168,255,.34);}
:is(.rc,.rs-top,.rs-box,.rs-concl).good {--c:#3DDC97; --c-bg:rgba(61,220,151,.14); --c-line:rgba(61,220,151,.36);}
:is(.rc,.rs-top,.rs-box,.rs-concl).fair {--c:#F2B84B; --c-bg:rgba(242,184,75,.14); --c-line:rgba(242,184,75,.36);}
:is(.rc,.rs-top,.rs-box,.rs-concl).bad  {--c:#FF6B6B; --c-bg:rgba(255,107,107,.14); --c-line:rgba(255,107,107,.36);}
:is(.rc,.rs-top,.rs-box,.rs-concl).na   {--c:#A0AEC0; --c-bg:rgba(160,174,192,.10); --c-line:rgba(160,174,192,.26);}
.rc, .rs-top, .rs-box {position:relative; border-radius:20px; border:1px solid var(--c-line);
  background:radial-gradient(120% 100% at 0% 0%, var(--c-bg) 0%, transparent 62%), linear-gradient(180deg,#11294D 0%,#0D3546 100%);
  box-shadow:0 10px 25px rgba(0,0,0,.30); transition:all .2s ease-in-out;}
.rc:hover, .rs-box:hover {transform:translateY(-2px); box-shadow:0 16px 34px rgba(0,0,0,.42);}
.rc {padding:18px 20px; margin-bottom:8px; min-height:190px;}
.rc-h {display:flex; align-items:center; gap:10px;}
.rc-ic {flex-shrink:0; width:38px; height:38px; border-radius:12px; display:grid; place-items:center; font-size:1.15rem;
  background:var(--c-bg); border:1px solid var(--c-line);}
.rc-t {flex:1; font-weight:800; font-size:1rem; line-height:1.2; color:#FFFFFF;}
.rc-b {white-space:nowrap; padding:4px 12px; border-radius:999px; font-size:.72rem; font-weight:800; letter-spacing:.02em;
  color:var(--c); background:var(--c-bg); border:1px solid var(--c-line);}
.rc-n {margin:6px 0 0; font-size:.8rem; color:#A0AEC0; line-height:1.4;}
.rc-g {display:grid; grid-template-columns:repeat(auto-fit,minmax(112px,1fr)); gap:10px; margin-top:14px;}
.rc-m {padding:10px 12px; border-radius:14px; background:rgba(255,255,255,.045); border:1px solid rgba(160,174,192,.14);}
.rc-l {font-size:.64rem; letter-spacing:.08em; text-transform:uppercase; font-weight:700; color:#A0AEC0;}
.rc-v {margin-top:3px; font-family:var(--mono,'JetBrains Mono',monospace); font-size:1.12rem; font-weight:700; color:#FFFFFF; line-height:1.25;}
.rc-w {margin-top:12px; font-size:.78rem; color:#F2B84B; line-height:1.4;}

.rs {display:flex; flex-direction:column; gap:12px; margin:6px 0 16px;}
.rs-id {font-size:.76rem; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:#A0AEC0;}
.rs-top {display:flex; align-items:center; gap:18px; padding:18px 20px;}
.rs-seal {flex-shrink:0; min-width:104px; text-align:center; padding:12px 14px; border-radius:16px; font-weight:900;
  font-size:1.3rem; letter-spacing:.04em; color:var(--c); background:var(--c-bg); border:1px solid var(--c-line);}
.rs-seal small {display:block; margin-bottom:2px; font-size:.58rem; letter-spacing:.14em; font-weight:700; color:#A0AEC0;}
.rs-k {font-size:.68rem; letter-spacing:.1em; text-transform:uppercase; font-weight:700; color:#A0AEC0;}
.rs-tx {margin-top:3px; font-size:.98rem; line-height:1.55; color:#FFFFFF;}
.rs-grid {display:grid; grid-template-columns:1fr 1fr; gap:12px;}
.rs-box {padding:16px 18px;}
.rs-h {margin-bottom:8px; font-weight:800; font-size:.95rem; color:var(--c);}
.rs-box ul {margin:0; padding:0; list-style:none;}
.rs-box li {position:relative; margin:7px 0; padding-left:18px; font-size:.9rem; line-height:1.5; color:#E2E8F0;}
.rs-box li::before {content:""; position:absolute; left:2px; top:.62em; width:7px; height:7px; border-radius:50%; background:var(--c);}
.rs-concl {padding:14px 18px; border-radius:16px; border:1px solid var(--c-line); border-left:4px solid var(--c);
  background:rgba(255,255,255,.035); font-size:.92rem; line-height:1.5; color:#FFFFFF;}
.rs-concl b {margin-right:6px; color:var(--c);}
.rs-src {font-size:.72rem; color:#A0AEC0; line-height:1.4;}
@media (max-width:760px) {.rs-grid {grid-template-columns:1fr;} .rs-top {flex-direction:column; align-items:flex-start;}}
/* cartões de status (.sc): barra fina no topo em vez de faixa lateral, números maiores */
.sc {padding:16px 18px !important;}
.sc::before {left:0 !important; right:0 !important; top:0 !important; bottom:auto !important; width:auto !important; height:3px !important;}
.sc-v {font-size:clamp(1.4rem,1.1rem + 1vw,1.9rem) !important;}
"""+_legibilidade()+_responsivo()+"""</style>"""


# ---------------------------------------------------------------------------- legibilidade (texto escuro em fundo escuro)
# Trechos de HTML escritos com as cores do tema claro antigo (texto #16202B, cinza #4B5767, verde/vermelho escuros) ficam
# ilegíveis no fundo azul-marinho. Em vez de mexer em cada página, o CSS troca, dentro do app, cada cor escura por
# uma versão clara equivalente e escurece os cartões claros escritos em linha (fundo #FBFCFD).
_TROCA_COR = {
    "#16202B": "#FFFFFF", "#1F2933": "#FFFFFF", "#0E2A5C": "#DCE6F5", "#4B5767": "#A0AEC0", "#5B6675": "#A0AEC0",
    "#788494": "#A0AEC0", "#2E7D4F": "#3DDC97", "#1F7A55": "#3DDC97", "#17604A": "#3DDC97", "#A8650B": "#F2B84B",
    "#B7791F": "#F2B84B", "#B83A3A": "#FF6B6B", "#C0392B": "#FF6B6B", "#3B6BC4": "#6EA8FF",
}
_FORA = ":not([data-testid=\"stPlotlyChart\"] *):not([data-baseweb=\"input\"] *):not([data-baseweb=\"select\"] *):not(.stTabs [aria-selected=\"true\"] *)"


def _legibilidade() -> str:
    regras = []
    for escuro, claro in _TROCA_COR.items():
        sel = []
        for pre in ('"', ";", " "):
            for esp in ("", " "):
                sel.append(f'.stApp [style*="{pre}color:{esp}{escuro}" i]' if False else
                           f'.stApp [style*="{pre if pre != chr(34) else ""}color:{esp}{escuro}" i]{_FORA}')
        regras.append(",\n".join(sel) + f" {{color:{claro} !important; -webkit-text-fill-color:{claro} !important;}}")
    claro_card = '.stApp [style*="background:#FBFCFD" i], .stApp [style*="background: #FBFCFD" i]'
    return "\n/* ===== legibilidade: cores escuras trocadas por claras ===== */\n" + "\n".join(regras) + f"""
{claro_card} {{background:linear-gradient(180deg,#11294D 0%,#0D3546 100%) !important; border-color:rgba(160,174,192,.30) !important;}}
/* chips, passos e balão de ajuda ⓘ */
.chip, .stp span {{background:#11294D !important; border-color:rgba(160,174,192,.32) !important; color:#E8EEF5 !important;}}
.chip *, .stp span * {{color:#E8EEF5 !important;}}
.stp span.on {{background:#125C51 !important; color:#FFFFFF !important;}}
.tip {{color:#A0AEC0 !important;}}
.tip .tipbox {{background:#16304F !important; color:#FFFFFF !important; border-color:rgba(160,174,192,.35) !important;}}
.tip .tipbox * {{color:#FFFFFF !important;}}
/* texto solto (div e span sem cor própria) dentro de cards e avisos em HTML herda o branco do app, e não o cinza-escuro do tema padrão */
.stApp [data-testid="stMarkdownContainer"] {{color:#FFFFFF;}}
/* avisos (aviso, selos) */
.aviso {{color:#F2B84B !important;}}
.badge.good {{color:#3DDC97 !important;}} .badge.fair {{color:#F2B84B !important;}} .badge.bad {{color:#FF6B6B !important;}}
.badge.na {{color:#C3CEDC !important;}}
/* avisos temporários (st.toast), dicas e etiquetas */
[data-testid="stToast"], [data-testid="stToastContainer"] > div, [data-testid="stToast"] > div {{background:#16304F !important;
  border:1px solid rgba(160,174,192,.35) !important; color:#FFFFFF !important;}}
[data-testid="stToast"] *, [data-testid="stToastContainer"] * {{color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; opacity:1 !important;}}
[data-testid="stTooltipContent"], [data-baseweb="tooltip"], [data-baseweb="tooltip"] * {{background:#16304F !important; color:#FFFFFF !important;
  -webkit-text-fill-color:#FFFFFF !important;}}
[data-baseweb="tag"] {{background:rgba(61,220,151,.22) !important; border:1px solid rgba(61,220,151,.45) !important;}}
[data-baseweb="tag"], [data-baseweb="tag"] * {{color:#F1FFF8 !important; -webkit-text-fill-color:#F1FFF8 !important;}}
/* barra do topo do Streamlit (Stop, Share, estrela, lápis) */
header[data-testid="stHeader"] *, [data-testid="stToolbar"] *, [data-testid="stAppDeployButton"] *, [data-testid="stStatusWidget"] * {{
  color:#E8EEF5 !important; -webkit-text-fill-color:#E8EEF5 !important; opacity:1 !important; fill:#E8EEF5;}}
/* menu de três pontinhos e janelas (popover) */
[data-testid="stMainMenuList"], [data-testid="stMainMenuList"] * {{background:#16304F !important; color:#FFFFFF !important;}}
[data-testid="stPopoverBody"], [data-testid="stPopoverBody"] :is(p, span, label, li, h1, h2, h3, h4, div) {{color:#FFFFFF;}}
[data-testid="stPopoverBody"] [data-testid="stCaptionContainer"] * {{color:#A0AEC0 !important;}}
/* controles com fundo branco: texto sempre escuro */
[data-baseweb="input"] *, [data-baseweb="textarea"] *, [data-baseweb="select"] * {{color:#16202B !important; -webkit-text-fill-color:#16202B !important;}}
[data-baseweb="input"] input::placeholder, [data-baseweb="textarea"] textarea::placeholder {{color:#5B6675 !important; -webkit-text-fill-color:#5B6675 !important; opacity:1 !important;}}
[data-baseweb="select"] [data-baseweb="tag"], [data-baseweb="select"] [data-baseweb="tag"] * {{color:#F1FFF8 !important; -webkit-text-fill-color:#F1FFF8 !important;}}
/* mensagens de erro do Streamlit (traceback) */
[data-testid="stException"], [data-testid="stException"] * {{color:#FFE3E3 !important; -webkit-text-fill-color:#FFE3E3 !important; opacity:1 !important;}}
/* tela de entrada (login) */
.lg-s h2 {{color:#FFFFFF !important;}} .lg-s p {{color:#C3CEDC !important;}}
/* botão ☰ do menu: fundo escuro e ícone branco (antes ficava claro sobre branco e "estourava") */
html body [data-testid="stExpandSidebarButton"], html body [data-testid="stSidebarCollapsedControl"] button,
html body [data-testid="collapsedControl"] button {{background:#16304F !important; border:1px solid rgba(160,174,192,.5) !important;
  box-shadow:0 6px 16px rgba(0,0,0,.35) !important;}}
html body [data-testid="stExpandSidebarButton"]::after, html body [data-testid="stSidebarCollapsedControl"] button::after,
html body [data-testid="collapsedControl"] button::after {{color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; opacity:1 !important;}}
html body [data-testid="stSidebarCollapseButton"] button {{background:rgba(255,255,255,.14) !important; border-radius:10px !important;}}
html body [data-testid="stSidebarCollapseButton"] button, html body [data-testid="stSidebarCollapseButton"] button * {{
  color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; fill:#FFFFFF !important; opacity:1 !important;}}
/* atalhos da trilha (links com fundo branco e texto branco) */
html body .st-key-trilha_bar a[data-testid="stPageLink-NavLink"] {{background:rgba(17,41,77,.65) !important; border:1px solid rgba(160,174,192,.35) !important;}}
html body .st-key-trilha_bar a[data-testid="stPageLink-NavLink"] :is(p, span) {{color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important;}}
/* envio de arquivos: área escura com texto claro */
html body [data-testid="stFileUploaderDropzone"] {{background:#11294D !important; border:1px dashed rgba(160,174,192,.5) !important;}}
html body [data-testid="stFileUploaderDropzone"] :is(span, small, p, div, svg) {{color:#E8EEF5 !important; -webkit-text-fill-color:#E8EEF5 !important; fill:#E8EEF5;}}
/* blocos de código e JSON: fundo escuro e texto claro */
html body [data-testid="stCode"] pre, html body [data-testid="stCode"] code {{background:#0F2340 !important; color:#E8EEF5 !important;}}
/* desativados continuam legíveis */
:disabled, [disabled] {{opacity:.7 !important;}}
"""


def _responsivo() -> str:
    """Ajustes para qualquer tela: celular (iPhone e Android), tablet, notebook e monitor grande; toque e mouse."""
    return """
/* ===== responsivo: todas as telas ===== */
:root {color-scheme:dark;}
html {-webkit-text-size-adjust:100%; text-size-adjust:100%;}
html, body {max-width:100%; overflow-x:hidden;}
a, button, [role="button"], [role="tab"], summary, label {touch-action:manipulation; -webkit-tap-highlight-color:transparent;}
img, video {max-width:100%; height:auto;}
.block-container {max-width:min(1440px,100%) !important;
  padding-left:max(1rem, env(safe-area-inset-left)) !important; padding-right:max(1rem, env(safe-area-inset-right)) !important;}
/* textos longos quebram em vez de empurrar a tela para o lado */
.rc-t, .rc-n, .rc-v, .tk, .nm, .rs-tx, .rs-box li, .ctx .t, .ctx .x, .mini .xx, .pgsub, .sc-v, .sc-l, .vazio p,
[data-testid="stMarkdownContainer"] p, [data-testid="stMarkdownContainer"] li, [data-testid="stCaptionContainer"] {overflow-wrap:anywhere; word-break:normal;}
[data-testid="stMarkdownContainer"] table {display:block; max-width:100%; overflow-x:auto; -webkit-overflow-scrolling:touch;}
[data-testid="stMarkdownContainer"] pre, [data-testid="stCode"] pre {max-width:100%; overflow-x:auto; white-space:pre-wrap; overflow-wrap:anywhere;}
/* abas: rolam para o lado quando não cabem (muitas abas no celular) */
.stTabs [data-baseweb="tab-list"] {max-width:100%; overflow-x:auto; overflow-y:hidden; scrollbar-width:none; -webkit-overflow-scrolling:touch;}
.stTabs [data-baseweb="tab-list"]::-webkit-scrollbar {display:none;}
.stTabs [data-baseweb="tab"] {flex-shrink:0; white-space:nowrap;}
/* o script do cabeçalho (meta tags) não ocupa espaço */
.stElementContainer:has(> iframe[height="0"]), [data-testid="stElementContainer"]:has(iframe[height="0"]) {position:absolute; height:0; width:0; margin:0; overflow:hidden;}

/* celular e tablet pequeno */
@media (max-width:768px) {
  /* 16px nos campos: o iPhone não dá zoom automático ao tocar */
  input, textarea, select, [data-baseweb="input"] input, [data-baseweb="select"] input, [data-baseweb="textarea"] textarea {font-size:16px !important;}
  .block-container {padding-top:4rem !important;}
  .stApp h1 {font-size:1.6rem;} .stApp h2 {font-size:1.35rem;} .stApp h3 {font-size:1.2rem;}
  [data-testid="stMetricValue"] {font-size:1.45rem !important;}
  .pghead {padding:var(--s2) !important;} .pghead::after {width:110px; height:110px;}
  .rc {padding:14px 14px !important; min-height:0 !important;}
  .rc-g {grid-template-columns:repeat(2,minmax(0,1fr)) !important;}
  .rs-top {padding:14px 14px !important;} .rs-seal {min-width:88px;}
  [data-testid="stPopoverBody"] {max-width:calc(100vw - 1.6rem) !important; width:calc(100vw - 1.6rem) !important;}
  [data-testid="stDialog"] [role="dialog"] {max-width:calc(100vw - 1rem) !important;}
  [data-testid="stToast"] {max-width:calc(100vw - 1.5rem) !important;}
}
/* celulares estreitos (iPhone SE, Androids pequenos) */
@media (max-width:400px) {
  .block-container {padding-left:max(.7rem, env(safe-area-inset-left)) !important; padding-right:max(.7rem, env(safe-area-inset-right)) !important;}
  .rc-g {grid-template-columns:1fr !important;}
  .stp span {padding:4px 10px; font-size:.74rem;}
  .st-key-home_modo button {padding:0 10px !important;}
}
/* telas de toque (dedo, não mouse): alvos de 44px e sem "hover" que fica preso */
@media (hover:none) and (pointer:coarse) {
  .stButton > button, .stFormSubmitButton > button, .stDownloadButton > button, .stLinkButton > a, button[data-testid="stPopoverButton"],
  a[data-testid="stPageLink-NavLink"], .stTabs [data-baseweb="tab"], [data-testid="stExpander"] summary {min-height:44px !important;}
  [data-baseweb="select"] > div, [data-baseweb="input"] {min-height:44px !important;}
  [role="radiogroup"] label, [data-testid="stCheckbox"] label {min-height:36px;}
  .card:hover, .kpi:hover, .mini:hover, .rc:hover, .rs-box:hover, .sc:hover, [data-testid="stMetric"]:hover {transform:none !important;}
}
/* celular deitado: pouca altura */
@media (max-height:480px) and (orientation:landscape) {
  .hero2.com-abas {padding-top:var(--s3);} .block-container {padding-top:3.4rem !important;}
}
/* monitores grandes e TVs */
@media (min-width:1900px) {html {font-size:17px;}}
@media (min-width:2500px) {html {font-size:19px;} .block-container {max-width:min(1800px,100%) !important;}}
/* impressão (PC): sem menu e com fundo claro */
@media print {
  header[data-testid="stHeader"], section[data-testid="stSidebar"], [data-testid="stToolbar"], .st-key-nav_mobile {display:none !important;}
  html, body, .stApp, [data-testid="stAppViewContainer"], [data-testid="stMain"] {background:#fff !important;}
  .stApp, .stApp * {color:#16202B !important; -webkit-text-fill-color:#16202B !important; box-shadow:none !important;}
  .rc, .rs-box, .rs-top, .sc, .card, .kpi, .mini, .ctx {background:#fff !important; border:1px solid #ccd3dc !important; break-inside:avoid;}
}
"""


# ============================================================================================================
# Passo 19 · Identidade visual única para gráficos e tabelas
# Um só lugar define fonte, grade, legenda, dica de passagem do mouse, zoom e seletor de período; `instalar_graficos()` aplica isso a
# TODOS os st.plotly_chart do app (sem editar cada página). Gráficos com fundo escuro próprio (análise técnica) são respeitados.
# ============================================================================================================
PALETA = ("#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#64748B", "#EC4899")
COR_GANHO, COR_PERDA, COR_NEUTRO = "#1F7A55", "#B83A3A", "#4B5767"
BOTOES_PERIODO = (dict(count=1, label="1m", step="month", stepmode="backward"), dict(count=6, label="6m", step="month", stepmode="backward"),
                  dict(count=1, label="1a", step="year", stepmode="backward"), dict(step="all", label="Tudo"))


def _fundo_escuro(cor) -> bool:
    if not isinstance(cor, str) or not cor.startswith("#") or len(cor) not in (4, 7):
        return False
    h = cor[1:] if len(cor) == 7 else "".join(c * 2 for c in cor[1:])
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return False
    return (0.299 * r + 0.587 * g + 0.114 * b) < 110


def _eixo_de_datas(fig) -> bool:
    for t in fig.data:
        x = getattr(t, "x", None)
        if x is None or len(x) == 0:
            continue
        a = x[0]
        return hasattr(a, "year") or (isinstance(a, str) and len(a) >= 8 and a[:4].isdigit() and a[4] == "-")
    return False


def padronizar_figura(fig):
    """Aplica a identidade visual do app a uma figura Plotly. Nunca levanta erro; devolve a mesma figura.
    Marca a figura como padronizada (não repete)."""
    try:
        if fig is None or getattr(fig, "_bpt_ok", False):
            return fig
        if _fundo_escuro(getattr(fig.layout, "paper_bgcolor", None)):
            return fig                                  # gráfico com tema escuro próprio (ex.: candlestick)
        tipos = {getattr(t, "type", "") for t in fig.data}
        so_cartesiano = bool(tipos) and not (tipos & {"pie", "sunburst", "treemap", "indicator", "table", "sankey", "scatterpolar"})
        fig.update_layout(font=dict(family="Inter, system-ui, -apple-system, Segoe UI, sans-serif", size=12, color="#16202B"),
                          paper_bgcolor="#ffffff", plot_bgcolor="#ffffff",
                          hoverlabel=dict(bgcolor="#16202B", font=dict(color="#ffffff", size=12), bordercolor="#16202B"),
                          legend=dict(orientation="h", yanchor="top", y=-0.18, x=0, font=dict(color="#16202B", size=11), bgcolor="rgba(255,255,255,0)"),
                          colorway=list(PALETA))
        if so_cartesiano:
            fig.update_xaxes(gridcolor="rgba(22,32,43,0.08)", zerolinecolor="rgba(22,32,43,0.25)", linecolor="rgba(22,32,43,0.25)",
                             tickfont=dict(color="#16202B"), title_font=dict(color="#16202B"), automargin=True)
            fig.update_yaxes(gridcolor="rgba(22,32,43,0.08)", zerolinecolor="rgba(22,32,43,0.25)", linecolor="rgba(22,32,43,0.25)",
                             tickfont=dict(color="#16202B"), title_font=dict(color="#16202B"), automargin=True)
            tem_subplots = sum(1 for k in fig.layout if str(k).startswith("xaxis")) > 1
            if not fig.layout.hovermode and not tem_subplots and tipos <= {"scatter", "scattergl", "bar"}:
                fig.update_layout(hovermode="x unified")
            if not tem_subplots and tipos & {"scatter", "scattergl"} and _eixo_de_datas(fig):
                try:
                    if not fig.layout.xaxis.rangeselector.buttons:
                        fig.update_xaxes(rangeselector=dict(buttons=list(BOTOES_PERIODO), bgcolor="#F2F4F7", activecolor="#CFE3FF", font=dict(color="#16202B", size=11)))
                except Exception:
                    pass
        fig._bpt_ok = True
    except Exception:                                   # aparência nunca derruba a página
        pass
    return fig


CONFIG_GRAFICO = {"displaylogo": False, "displayModeBar": "hover", "scrollZoom": False,
                  "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d", "toggleSpikelines"],
                  "toImageButtonOptions": {"format": "png", "scale": 2, "filename": "grafico_bussola_b3"}}


def instalar_graficos(st_mod) -> None:
    """Faz todo st.plotly_chart do app passar por `padronizar_figura` e usar a barra de zoom padrão. Idempotente."""
    f = getattr(st_mod, "plotly_chart", None)
    if f is None or getattr(f, "_bpt", False):
        return

    def plotly_chart(fig, *a, **k):
        padronizar_figura(fig)
        cfg = dict(k.get("config") or {})
        if cfg.get("displayModeBar") is False and _tem_serie_temporal(fig):
            cfg.pop("displayModeBar")                   # série temporal: deixa o zoom disponível
        k["config"] = {**CONFIG_GRAFICO, **cfg}
        k.setdefault("theme", None)
        return f(fig, *a, **k)
    plotly_chart._bpt = True
    st_mod.plotly_chart = plotly_chart


def _tem_serie_temporal(fig) -> bool:
    try:
        return _eixo_de_datas(fig) and not getattr(fig.layout, "dragmode", None) == "pan"
    except Exception:
        return False


def estilizar_tabela(df, ganho=(), formatos=None):
    """Tabela com cor de ganho (verde) e perda (vermelho) nas colunas de resultado e formatos por coluna. Se o Styler falhar, devolve o DataFrame."""
    try:
        def cor(v):
            try:
                v = float(v)
            except (TypeError, ValueError):
                return ""
            return f"color:{COR_GANHO};font-weight:600" if v > 0 else (f"color:{COR_PERDA};font-weight:600" if v < 0 else "")
        df = df.copy()
        pre = {c for c in (formatos or {}) if c in df.columns and (df[c].dtype == object or df[c].isna().all())}
        for c in pre:                                        # coluna toda vazia (None) vira texto "n/d": o Streamlit não aplica o formato a colunas de objeto
            f = formatos[c]
            if True:
                df[c] = df[c].map(lambda v, f=f: "n/d" if v is None or (isinstance(v, float) and v != v) else (f(v) if callable(f) else f.format(v)))
        sty = df.style
        cols = [c for c in ganho if c in df.columns]
        if cols:
            sty = sty.map(cor, subset=cols)
        if formatos:
            sty = sty.format({c: f for c, f in formatos.items() if c in df.columns and c not in pre}, na_rep="n/d")
        return sty
    except Exception:
        return df
