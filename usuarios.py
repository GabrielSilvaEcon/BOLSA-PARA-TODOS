"""Identidade e dados por usuário (Bolsa para Todos) — Passo 21.

Duas formas de entrar, uma só conta (identificada pelo e-mail):
- Google (st.login / st.user, como antes);
- e-mail e senha (contas.py: cadastro com confirmação por e-mail, sessões com expiração, recuperação de senha).

Este módulo liga a identidade à sessão do Streamlit e guarda/carrega os dados da pessoa (ações em análise, perfil,
carteiras, preferências...) em UM JSON por conta, pelo banco.py, que confere na própria camada de dados que o dono
é quem está logado. Sem [auth] e sem e-mail configurados nos secrets o app abre como visitante e nada é salvo.

Isolamento entre usuários: ao sair, ou ao trocar de conta na mesma sessão do navegador, TODO o session_state é apagado
(só o código do navegador permanece), para que nada da conta anterior apareça na seguinte.
"""
import json
import time
import uuid
from html import escape as _esc

import streamlit as st

import banco
import contas
import email_envio as mail
import permissoes as perm
import prefs as P
import seguranca as seg

# O que é guardado: estas chaves do session_state e qualquer chave que comece com um destes prefixos.
CHAVES = ("sel_ativos", "perfil", "fonte_dados", "universo", "cores_ativos",
          "cripto_ativos", "cripto_nomes", "cart_capital",
          # Central de inteligência (Passo 13): só os dados da pessoa (preferências, regras, histórico e fotografias sem valores);
          # as chaves de widgets (intel_f_*, intel_p_*...) e o cache de leitura (_intel_cache) não são gravados.
          "intel_prefs", "intel_regras", "intel_hist", "intel_fotos", "intel_fotos_carteira",
          # Análise técnica avançada (Passo 14): configuração do gráfico, regras de alerta, histórico de alertas e de sinais
          "tec_av_config", "tec_av_regras", "tec_av_hist", "tec_av_sinais",
          # Central de notícias e eventos (Passo 15): regras de alerta, histórico, eventos informados pela pessoa e registro de atualizações
          "ne_regras", "ne_hist", "ne_eventos", "ne_log",
          # Gestão de risco (Passo 16): limites, regras de alerta, histórico de alertas e de notas, dados complementares e cenários personalizados
          "risco_limites", "risco_regras", "risco_hist", "risco_notas", "risco_cfg",
          # Simulador financeiro (Passo 18): painel de metas e premissas por classe editadas pela pessoa
          "sim_metas", "sim_premissas",
          # Relatórios (Passo 19): fotografias do histórico da carteira e gráficos escolhidos
          "rel_fotos", "rel_cfg",
          # Preferências da conta (Passo 21): moeda, tema, favoritos, período, notificações, ordem do painel, modo
          "prefs",
          # Notificações e monitoramento (Passo 23): preferências de entrega e regras de alerta do monitor automático
          "notif_prefs", "mon_regras", "edu_progresso")
PREFIXOS = ("cart_",)

COOKIE = "bpt_sess"
REVALIDAR_S = 60          # a cada quanto tempo conferimos se a sessão/conta continua válida


# ------------------------------------------------------------------ configuração
def _configurado() -> bool:
    """Login com Google configurado nos secrets ([auth])."""
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def senha_disponivel() -> bool:
    """Cadastro, login e recuperação por e-mail e senha: precisam do envio de e-mail configurado e do banco pronto."""
    return mail.configurado() and bool(mail.url_base()) and banco.pronto()[0]


def acesso_obrigatorio() -> bool:
    """Se o app deve mostrar a tela de entrada (em vez de abrir direto como visitante)."""
    return _configurado() or senha_disponivel()


def cliente_id() -> str:
    """Código aleatório deste navegador/sessão (para limitar tentativas sem guardar dados pessoais)."""
    ss = st.session_state
    if "_cid" not in ss:
        ss["_cid"] = uuid.uuid4().hex
    return ss["_cid"]


# ------------------------------------------------------------------ identidade da sessão
_G = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'><path fill='%23EA4335' d='M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z'/><path fill='%234285F4' d='M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z'/><path fill='%23FBBC05' d='M10.5 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.9-6.1C.9 16.4 0 20.1 0 24s.9 7.6 2.6 10.8l7.9-6.1z'/><path fill='%2334A853' d='M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z'/></svg>")

_ICO_EMAIL = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FFFFFF' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>"
              "<rect x='3' y='5' width='18' height='14' rx='3'/><path d='M3.5 7.5l8.5 6 8.5-6'/></svg>")
_ICO_SENHA = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FFFFFF' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>"
              "<rect x='4.5' y='10.5' width='15' height='10' rx='3'/><path d='M8 10.5V8a4 4 0 018 0v2.5'/></svg>")
_ICO_NOME = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='%23FFFFFF' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'>"
             "<circle cx='12' cy='8' r='4'/><path d='M4.5 20.5c1-4 4-5.5 7.5-5.5s6.5 1.5 7.5 5.5'/></svg>")


def _css_login() -> str:
    """Tela de entrada em vidro (glassmorphism): fundo índigo com brilho magenta no alto e pervinca no canto, cartão translúcido,
    campos só com linha embaixo e ícone, botão largo em degradê. Texto branco sobre vidro escuro (contraste > 9:1)."""
    return f"""<style>
html body .stApp[class], html body [data-testid="stAppViewContainer"][class], html body [data-testid="stMain"][class] {{
  background:radial-gradient(760px 520px at 50% -8%, rgba(240,70,120,.48), rgba(210,63,200,.26) 40%, transparent 72%),
             radial-gradient(900px 640px at 108% 106%, rgba(122,140,255,.52), transparent 62%),
             linear-gradient(160deg,#1A1050 0%,#120B3A 48%,#0B0821 100%) !important; background-attachment:fixed !important;}}
html body .block-container {{padding-top:2rem !important;}}
html body .st-key-login_card {{max-width:440px; margin:.6rem auto 0; padding:34px 30px 20px !important; border-radius:38px;
  background:linear-gradient(160deg,rgba(255,255,255,.17),rgba(255,255,255,.05)) !important; border:1px solid rgba(255,255,255,.28) !important;
  backdrop-filter:blur(22px) saturate(1.3); -webkit-backdrop-filter:blur(22px) saturate(1.3);
  box-shadow:0 30px 60px -22px rgba(0,0,0,.6), inset 0 1px 0 rgba(255,255,255,.35) !important; gap:1rem !important;}}
html body .st-key-login_card > div {{margin:0 !important;}}
html body .st-key-login_card [data-testid="stMarkdownContainer"] {{margin:0 !important;}}
html body .st-key-login_card [data-testid="stElementContainer"], html body .st-key-login_card [data-testid="stExpander"] {{position:relative; z-index:1;}}
.lg-hero {{display:flex; justify-content:center; margin:2px 0 4px;}}
.lg-ringav {{width:118px; height:118px; border-radius:50%; padding:4px; background:linear-gradient(135deg,#8B6CFF,#D23FC8 55%,#F2B84B);
  box-shadow:0 0 44px rgba(210,63,200,.55), 0 14px 30px rgba(0,0,0,.4);}}
.lg-av {{width:100%; height:100%; border-radius:50%; background:#1B1442; display:flex; align-items:center; justify-content:center;}}
.lg-av img {{width:84px; height:84px; border-radius:22px; object-fit:contain;}}
.lg-marca {{text-align:center; font-weight:800; font-size:1.05rem; letter-spacing:.34em; text-transform:uppercase; color:#FFFFFF; margin:4px 0 0; padding-left:.34em;}}
.lg-slides {{position:relative; min-height:136px; text-align:center; margin:0 0 4px;}}
.lg-s {{position:absolute; inset:0; opacity:0; animation:lgslide 12s infinite;}}
.lg-s.s2 {{animation-delay:4s;}} .lg-s.s3 {{animation-delay:8s;}}
.lg-s h2 {{margin:6px 0 6px !important; padding:0 !important; font-size:1.3rem !important; font-weight:800; color:#FFFFFF !important; line-height:1.2 !important;}}
.lg-s h2 a, .lg-s h2 [data-testid="stHeaderActionElements"], .lg-s h2 svg {{display:none !important;}}
.lg-s p {{margin:0 auto !important; padding:0 !important; max-width:330px; font-size:.93rem; color:#E3DDFA !important; line-height:1.45;}}
@keyframes lgslide {{0% {{opacity:0; transform:translateY(8px);}} 4%,30% {{opacity:1; transform:none;}} 34%,100% {{opacity:0;}}}}
.lg-dots {{display:flex; gap:6px; justify-content:center; margin:0 0 26px;}}
.lg-dots i {{display:block; height:7px; width:7px; border-radius:99px; background:rgba(255,255,255,.35); animation:lgdot 12s infinite;}}
.lg-dots i:nth-child(2) {{animation-delay:4s;}} .lg-dots i:nth-child(3) {{animation-delay:8s;}}
@keyframes lgdot {{0%,30% {{width:24px; background:#FFFFFF;}} 34%,100% {{width:7px; background:rgba(255,255,255,.35);}}}}
.lg-ou {{display:flex; align-items:center; gap:12px; font-size:.8rem; font-weight:600; margin:10px 0 6px;}}
.lg-ou, .lg-ou span {{color:#E3DDFA !important; -webkit-text-fill-color:#E3DDFA !important;}}
.lg-ou::before, .lg-ou::after {{content:""; flex:1; height:1px; background:rgba(255,255,255,.30);}}
/* botões: largos, em pílula; o principal é o degradê violeta -> magenta */
html body .stApp .st-key-login_card button {{border-radius:999px !important; min-height:3.3rem; font-weight:800; position:relative; width:100% !important;}}
html body .stApp .st-key-login_card .stButton, html body .stApp .st-key-login_card [data-testid="stFormSubmitButton"] {{width:100% !important;}}
html body .stApp .st-key-login_card button[data-testid^="stBaseButton-primary"] {{background:linear-gradient(90deg,#6E4BFF 0%,#B02FC8 100%) !important;
  border:1px solid rgba(255,255,255,.25) !important; box-shadow:0 14px 30px -10px rgba(176,47,200,.75) !important;}}
html body .stApp .st-key-login_card button[data-testid^="stBaseButton-primary"] :is(p, span) {{color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important;
  letter-spacing:.12em; text-transform:uppercase; font-size:.88rem;}}
html body .stApp .st-key-login_card [data-testid="stFormSubmitButton"] button {{min-height:3.4rem; margin-top:.35rem;}}
/* botão do Google no padrão dos outros apps: branco, texto escuro, "G" colorido à esquerda */
html body .stApp .st-key-login_card .stButton.st-key-login_google button[data-testid^="stBaseButton-primary"] {{background:#FFFFFF !important; border:1px solid #DADCE0 !important; box-shadow:0 2px 6px rgba(0,0,0,.25) !important;}}
html body .stApp .st-key-login_card .stButton.st-key-login_google button[data-testid^="stBaseButton-primary"]:is(button, :hover) :is(p, span, [data-testid="stIconMaterial"]) {{color:#1F1F1F !important; -webkit-text-fill-color:#1F1F1F !important; letter-spacing:0 !important;
  text-transform:none !important; font-size:1rem !important; font-weight:700; padding-left:1.6rem;}}
html body .stApp .st-key-login_card .stButton.st-key-login_google button[data-testid^="stBaseButton-primary"]:hover {{background:#F3F0FF !important;}}
html body .st-key-login_google button::before {{content:""; position:absolute; left:16px; top:50%; transform:translateY(-50%);
  width:1.5rem; height:1.5rem; background:url("data:image/svg+xml;utf8,{_G}") center/contain no-repeat;}}
html body .stApp .st-key-login_visit button {{background:transparent !important; border:1px solid rgba(255,255,255,.30) !important; box-shadow:none !important;}}
html body .stApp .st-key-login_visit button :is(p, span) {{color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; font-size:.98rem;}}
html body .stApp .st-key-login_visit button:hover {{background:rgba(255,255,255,.12) !important; border-color:#FFFFFF !important;}}
/* bloco de e-mail e senha: sem caixa própria, abas só sublinhadas */
html body .st-key-login_card .st-key-acesso_card {{background:transparent !important; border:0 !important; box-shadow:none !important; padding:0 !important;}}
html body .stApp .st-key-login_card .stTabs [data-baseweb="tab-list"] {{background:transparent !important; border:0 !important; border-bottom:1px solid rgba(255,255,255,.28) !important;
  border-radius:0 !important; padding:0 !important; width:100%; gap:0; justify-content:space-between;}}
html body .stApp .st-key-login_card .stTabs [data-baseweb="tab"] {{background:transparent !important; border-radius:0 !important; padding:8px 4px; flex:1; justify-content:center;
  color:#E3DDFA !important; box-shadow:none !important;}}
html body .stApp .st-key-login_card .stTabs [data-baseweb="tab"] p {{color:#E3DDFA !important; -webkit-text-fill-color:#E3DDFA !important; font-weight:700; font-size:.9rem;}}
html body .stApp .st-key-login_card .stTabs [data-baseweb="tab"][aria-selected="true"] {{background:transparent !important; box-shadow:none !important;
  border:0 !important; border-bottom:3px solid #F06AD8 !important;}}
html body .stApp .st-key-login_card .stTabs [data-baseweb="tab"][aria-selected="true"] p {{color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important;}}
html body .stApp .st-key-login_card [data-testid="stForm"] {{background:transparent !important; border:0 !important; box-shadow:none !important; padding:.4rem 0 0 !important;}}
/* campos: só uma linha embaixo, ícone à esquerda, texto branco */
html body .st-key-login_card [data-baseweb="input"] {{background:transparent !important; border:0 !important; border-bottom:1.5px solid rgba(255,255,255,.6) !important;
  border-radius:0 !important; box-shadow:none !important; position:relative;}}
html body .st-key-login_card [data-baseweb="input"]:focus-within {{border-bottom:2px solid #FFFFFF !important; box-shadow:0 8px 14px -10px rgba(240,106,216,.9) !important;}}
html body .st-key-login_card [data-baseweb="input"] * {{background:transparent !important; color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important; caret-color:#FFFFFF;}}
html body .st-key-login_card [data-baseweb="input"] input {{padding-left:38px !important; font-size:1rem;}}
html body .st-key-login_card [data-baseweb="input"] input::placeholder {{color:rgba(255,255,255,.78) !important; -webkit-text-fill-color:rgba(255,255,255,.78) !important; opacity:1 !important;}}
html body .st-key-login_card [data-baseweb="input"] input:-webkit-autofill {{-webkit-box-shadow:0 0 0 1000px #2B2066 inset !important; -webkit-text-fill-color:#FFFFFF !important;}}
html body .st-key-login_card [data-baseweb="input"]::before {{content:""; position:absolute; left:6px; top:50%; transform:translateY(-50%); width:20px; height:20px;
  background:center/contain no-repeat; opacity:.9; pointer-events:none; z-index:2;}}
html body .st-key-in_email [data-baseweb="input"]::before, html body .st-key-cr_email [data-baseweb="input"]::before,
html body .st-key-es_email [data-baseweb="input"]::before, html body .st-key-reenv_email [data-baseweb="input"]::before {{background-image:url("data:image/svg+xml;utf8,{_ICO_EMAIL}");}}
html body .st-key-in_senha [data-baseweb="input"]::before, html body .st-key-cr_senha [data-baseweb="input"]::before, html body .st-key-cr_senha2 [data-baseweb="input"]::before,
html body .st-key-nova_senha [data-baseweb="input"]::before, html body .st-key-nova_senha2 [data-baseweb="input"]::before {{background-image:url("data:image/svg+xml;utf8,{_ICO_SENHA}");}}
html body .st-key-cr_nome [data-baseweb="input"]::before {{background-image:url("data:image/svg+xml;utf8,{_ICO_NOME}");}}
html body .st-key-login_card [data-testid="stWidgetLabel"] p, html body .st-key-login_card label p {{color:#EDE9FF !important; -webkit-text-fill-color:#EDE9FF !important;
  font-size:.82rem; font-weight:700; letter-spacing:.04em;}}
html body .st-key-login_card [data-testid="stCheckbox"] label p {{font-size:.86rem; font-weight:600; letter-spacing:0;}}
html body .st-key-login_card [data-testid="stExpander"] {{margin-top:6px !important; background:rgba(255,255,255,.06) !important; border:1px solid rgba(255,255,255,.22) !important;
  border-radius:18px !important; box-shadow:none !important;}}
html body .st-key-login_card [data-testid="stExpander"] summary p {{color:#FFFFFF !important;}}
/* reforço: abas e campos (a estrutura interna do Streamlit varia entre versões) */
html body .stApp .st-key-login_card .stTabs :is([aria-selected="true"], [aria-selected="false"], [data-baseweb="tab-highlight"], [data-baseweb="tab-border"]) {{
  background:none !important; background-color:transparent !important; box-shadow:none !important;}}
html body .stApp .st-key-login_card .stTabs [data-baseweb="tab-highlight"], html body .stApp .st-key-login_card .stTabs [data-baseweb="tab-border"] {{display:none !important;}}
html body .stApp .st-key-login_card .stTabs [aria-selected="true"] {{box-shadow:inset 0 -3px 0 #F06AD8 !important; border:0 !important; border-radius:0 !important;}}
html body .st-key-login_card :is([data-baseweb="input"], [data-baseweb="base-input"], [data-testid="stTextInputRootElement"], [data-testid="stTextInput"] > div > div) {{
  background:none !important; background-color:transparent !important; border-radius:0 !important; box-shadow:none !important;}}
html body .st-key-login_card :is([data-baseweb="base-input"], [data-baseweb="base-input"] input, input) {{background-color:transparent !important; border:0 !important; color:#FFFFFF !important; -webkit-text-fill-color:#FFFFFF !important;}}
html body .st-key-login_card [data-testid="stTextInputRootElement"], html body .st-key-login_card [data-baseweb="input"] {{border:0 !important; border-bottom:1.5px solid rgba(255,255,255,.65) !important;}}
html body .st-key-login_card [data-baseweb="base-input"] {{border:0 !important;}}
.lg-foot {{display:block; padding:8px 6px 0; margin-bottom:16px; font-size:.76rem; color:#E3DDFA; text-align:center; line-height:1.55;}}
.lg-foot b {{color:#FFFFFF;}}
@media (min-width:900px) {{html body .st-key-login_card {{zoom:1.3; margin-top:4vh;}}}}
@media (min-width:1300px) {{html body .st-key-login_card {{zoom:1.5; margin-top:5vh;}}}}
@media (max-width:520px) {{.lg-slides {{min-height:168px;}} html body .st-key-login_card {{padding:26px 18px 16px !important; border-radius:30px; margin-top:0;}} .lg-s h2 {{font-size:1.15rem;}}}}
</style>"""


def _diagnostico() -> dict:
    """Informações sem dados pessoais para descobrir por que o login não conclui."""
    from urllib.parse import urlparse
    d = {}
    for rot, fn in (
        ("conectado", lambda: bool(st.user.is_logged_in)),
        ("campos do usuário", lambda: list(st.user.to_dict().keys())),
        ("cookies recebidos", lambda: list(st.context.cookies.keys())),
        ("endereço acessado", lambda: st.context.headers.get("Host")),
        ("endereço do redirect_uri", lambda: urlparse(st.secrets["auth"]["redirect_uri"]).netloc),
        ("redirect_uri termina em /oauth2callback", lambda: st.secrets["auth"]["redirect_uri"].endswith("/oauth2callback")),
        ("tem cookie_secret", lambda: bool(st.secrets["auth"].get("cookie_secret"))),
        ("tem [auth.google]", lambda: all(k in st.secrets["auth"]["google"] for k in ("client_id", "client_secret", "server_metadata_url"))),
        ("versão do streamlit", lambda: st.__version__),
    ):
        try:
            d[rot] = fn()
        except Exception as e:
            d[rot] = f"erro: {e.__class__.__name__}"
    return d


def _google_dados():
    try:
        if _configurado() and st.user.is_logged_in:
            email = (st.user.get("email") or "").strip().lower()
            if not email and st.user.get("sub"):
                email = f"sub:{st.user.get('sub')}"
            if email:
                return {"email": email, "nome": st.user.get("name") or email.split("@")[0]}
    except Exception:
        pass
    return None


def _purgar() -> None:
    """Apaga tudo da sessão (dados pessoais, widgets, caches de sessão). Só o código do navegador fica."""
    ss = st.session_state
    cid = ss.get("_cid")
    ss.clear()
    if cid:
        ss["_cid"] = cid


def _definir_conta(conta: dict, via: str, token: str | None = None, legado: bool = False) -> None:
    ss = st.session_state
    antigo = ss.get("_perfil_de")
    if antigo and antigo != conta["email"]:
        _purgar()          # outra conta no mesmo navegador: nada da anterior pode sobrar
        ss = st.session_state
    ss["_conta"] = {"id": conta.get("id") or "legado:" + conta["email"], "email": conta["email"],
                    "nome": conta.get("nome") or conta["email"].split("@")[0],
                    "papel": contas.papel_da_conta(conta) if not legado else "usuario",
                    "provedor": conta.get("provedor") or via, "via": via, "legado": legado}
    ss["_tok"] = token
    ss["_val_em"] = time.monotonic()
    ss.pop("_negado", None)


def _cookie_lido() -> str | None:
    try:
        return st.context.cookies.get(COOKIE)
    except Exception:
        return None


def _resolver_identidade() -> None:
    """Descobre quem está na sessão (conta já carregada, Google ou cookie de sessão) e revalida de tempos em tempos."""
    ss = st.session_state
    g = _google_dados()
    c = ss.get("_conta")
    if c and c["via"] == "google" and (not g or g["email"] != c["email"]):
        _purgar()
        c = None
    if c and time.monotonic() - ss.get("_val_em", 0) >= REVALIDAR_S:
        if c["via"] == "senha":
            conta = contas.validar_sessao(ss.get("_tok"))
            if not conta:
                tok_aviso = "Sua sessão terminou por segurança. Entre novamente."
                _purgar()
                ss = st.session_state
                ss["_aviso"], ss["_cookie_pend"] = tok_aviso, ("limpar", "")
                c = None
            else:
                _definir_conta(conta, "senha", ss.get("_tok"))
        elif not c.get("legado"):
            conta = contas.conta_ativa_por_email(c["email"])
            if not conta:
                _purgar()
                st.session_state["_negado"] = "Esta conta está suspensa ou indisponível. Fale com o suporte."
                c = None
            else:
                _definir_conta(conta, "google")
    if c:
        return
    if g and not ss.get("_negado"):
        r = contas.login_google(g["email"], g["nome"])
        if r.ok:
            _definir_conta(r.dado, "google")
            return
        if not banco.pronto()[0]:      # banco ainda sem as tabelas novas: continua como antes (só o perfil)
            _definir_conta({"email": g["email"], "nome": g["nome"], "provedor": "google"}, "google", legado=True)
            return
        ss["_negado"] = r.msg
        return
    tok = _cookie_lido()
    if tok and not g and senha_disponivel():
        conta = contas.validar_sessao(tok)
        if conta:
            _definir_conta(conta, "senha", tok)


def iniciar_sessao_senha(res) -> None:
    """Chamado pela tela de login quando contas.entrar deu certo."""
    _definir_conta(res.dado["conta"], "senha", res.dado["token"])
    st.session_state["_cookie_pend"] = ("definir", res.dado["token"], res.dado.get("lembrar", False))


def _aplicar_cookie_pendente() -> None:
    """Grava/apaga o cookie de sessão no navegador (um pequeno script numa moldura invisível)."""
    pend = st.session_state.pop("_cookie_pend", None)
    if not pend:
        return
    try:
        import incorporar
        if pend[0] == "definir":
            ma = contas.SESSAO_LEMBRAR["absoluto"] if (len(pend) > 2 and pend[2]) else contas.SESSAO_PADRAO["absoluto"]
            corpo = f"{COOKIE}={pend[1]}; path=/; max-age={ma}; SameSite=Lax"
        else:
            corpo = f"{COOKIE}=; path=/; max-age=0; SameSite=Lax"
        js = ("<script>(function(){var c=%s+(location.protocol==='https:'?'; Secure':'');"
              "try{document.cookie=c;}catch(e){}"
              "try{window.parent.document.cookie=c;}catch(e){}})();</script>" % json.dumps(corpo))
        incorporar.html(st, js, 0)
    except Exception as e:
        banco.registrar_erro("usuarios.cookie", e)


def usuario():
    """{'email', 'nome', 'id', 'papel', 'provedor'} de quem está logado, ou None (visitante)."""
    c = st.session_state.get("_conta")
    if not c:
        return None
    return {k: c[k] for k in ("email", "nome", "id", "papel", "provedor")}


def ator():
    """Quem age, no formato que a camada de dados exige. None se for visitante."""
    c = st.session_state.get("_conta")
    return banco.Ator(id=c["id"], email=c["email"], papel=c["papel"]) if c else None


def token_sessao() -> str | None:
    return st.session_state.get("_tok")


def pode(permissao: str) -> bool:
    c = st.session_state.get("_conta")
    return bool(c) and perm.tem(c["papel"], permissao)


def preferencias() -> dict:
    return P.normalizar(st.session_state.get("prefs"))


def eh_visitante() -> bool:
    return bool(st.session_state.get("_visitante")) and not usuario()


def _virar_visitante():
    st.session_state["_visitante"] = True


def sair_visitante():
    """Volta para a tela de login."""
    st.session_state.pop("_visitante", None)


def sair():
    """Encerra a sessão (no banco, no navegador e na memória) e, se veio do Google, também o login do Google."""
    ss = st.session_state
    c, tok = ss.get("_conta"), ss.get("_tok")
    via = c["via"] if c else None
    if c and via == "senha":
        contas.encerrar_sessao(tok, c["id"])
    elif c and not c.get("legado"):
        contas.encerrar_sessao(None, c["id"])
    _purgar()
    st.session_state["_cookie_pend"] = ("limpar", "")
    if via == "google" or (_google_dados() is not None):
        st.logout()


def menu_visitante(sufixo: str = "d"):
    st.markdown("**Visitante**")
    st.caption("Você está sem conta: nada fica salvo.")
    st.button("Entrar", icon=":material/login:", on_click=sair_visitante, width="stretch", key=f"entrar_{sufixo}")


def exigir_login(logo_uri: str = "", nome: str = "Bússola B3"):
    """Resolve quem está na sessão. Sem login e com acesso configurado, mostra a tela de entrada e interrompe o app."""
    _aplicar_cookie_pendente()
    if acesso_obrigatorio() or _google_dados():
        _resolver_identidade()
    u = usuario()
    if u:
        return u
    if not acesso_obrigatorio():
        return None
    if st.session_state.get("_visitante"):
        return None
    import conta_app
    conta_app.tela_acesso(logo_uri, nome)
    st.stop()


# ------------------------------------------------------------------ dados da pessoa
def _snapshot() -> dict:
    d = {}
    for k, v in st.session_state.items():
        if isinstance(k, str) and (k in CHAVES or k.startswith(PREFIXOS)):
            try:
                json.dumps(v)
                d[k] = v
            except TypeError:
                pass
    return d


def _chave(d: dict) -> str:
    return json.dumps(d, sort_keys=True, default=str)


def _ler(a, email: str) -> dict:
    try:
        return banco.ler_dados(a, email)
    except Exception as e:
        banco.registrar_erro("usuarios.ler", e)
        st.toast("Não consegui carregar seus dados salvos agora. Tente recarregar a página.", icon="⚠️")
        return {}


def _gravar(a, email: str, dados: dict) -> bool:
    try:
        banco.gravar_dados(a, email, dados)
        return True
    except Exception as e:
        banco.registrar_erro("usuarios.gravar", e)
        st.toast("Não consegui salvar seus dados agora.", icon="⚠️")
        return False


def iniciar():
    """Carrega os dados do usuário uma vez por sessão, antes dos widgets serem desenhados."""
    u = usuario()
    if not u:
        return None
    ss = st.session_state
    if ss.get("_perfil_de") != u["email"]:
        for k, v in _ler(ator(), u["email"]).items():
            if isinstance(k, str) and (k in CHAVES or k.startswith(PREFIXOS)):   # só chaves conhecidas voltam para a sessão
                ss[k] = v
        ss["prefs"] = P.normalizar(ss.get("prefs"))
        ss["_perfil_de"] = u["email"]
        ss["_salvo"] = _chave(_snapshot())
        st.toast(f"Bem-vindo, {u['nome'].split()[0]}! Seus dados estão carregados.", icon="👋")
    return u


def salvar():
    """Grava no fim de cada execução, só se algo mudou."""
    u = usuario()
    if not u or st.session_state.get("_perfil_de") != u["email"]:
        return
    snap = _snapshot()
    ch = _chave(snap)
    if ch != st.session_state.get("_salvo") and _gravar(ator(), u["email"], snap):
        st.session_state["_salvo"] = ch


def primeiro_nome() -> str:
    u = usuario()
    return (u["nome"].split()[0][:12]) if u else ""


def menu_conta(sufixo: str = "d"):
    """Nome, e-mail e botão Sair. Desenhar dentro de um popover ou container."""
    u = usuario()
    if not u:
        return
    st.markdown(f"**{_esc(u['nome'])}**")
    st.caption(u["email"])
    st.button("Sair", icon=":material/logout:", on_click=sair, width="stretch", key=f"sair_{sufixo}")


def apagar_dados_salvos() -> bool:
    """Apaga só os dados guardados (carteiras, perfil...) mantendo a conta. Usado em Privacidade."""
    u = usuario()
    if not u:
        return False
    try:
        banco.apagar_dados(ator(), u["email"])
    except Exception as e:
        banco.registrar_erro("usuarios.apagar", e)
        return False
    ss = st.session_state
    for k in list(ss.keys()):
        if isinstance(k, str) and (k in CHAVES or k.startswith(PREFIXOS)):
            del ss[k]
    ss["_salvo"] = _chave(_snapshot())
    return True


def pagina_conta():
    import conta_app
    conta_app.pagina_conta()
