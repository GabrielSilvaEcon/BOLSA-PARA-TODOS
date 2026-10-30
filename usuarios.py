"""Login com Google e perfil por usuário (Bolsa para Todos).

- Login: st.login / st.user (Streamlit 1.42+, precisa de Authlib e do bloco [auth] nos secrets).
- Dados por usuário: ações em análise, perfil, fonte de dados, carteiras (fictícia e real), moedas cripto etc.
  Ficam em um JSON por e-mail. Com [supabase] nos secrets vão para o Supabase (permanente);
  sem ele vão para um SQLite local (usuarios.db), que na nuvem do Streamlit é apagado a cada novo deploy.
- Sem [auth] nos secrets o app abre como visitante (útil para testar no computador) e nada é salvo.
"""
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
import streamlit as st

# O que é guardado: estas chaves do session_state e qualquer chave que comece com um destes prefixos.
CHAVES = ("sel_ativos", "perfil", "fonte_dados", "universo", "cores_ativos",
          "cripto_ativos", "cripto_nomes", "cart_capital")
PREFIXOS = ("cart_",)

_DB = Path(__file__).with_name("usuarios.db")


# ------------------------------------------------------------------ armazenamento
def _supabase():
    try:
        cfg = st.secrets["supabase"]
        return cfg["url"].rstrip("/"), cfg["key"]
    except Exception:
        return None


def _cab(key: str) -> dict:
    """Cabeçalhos do Supabase. Chaves novas (sb_secret_...) vão só em apikey; a service_role antiga (JWT) também em Authorization."""
    h = {"apikey": key}
    if key.startswith("eyJ"):
        h["Authorization"] = f"Bearer {key}"
    return h


def _ler(email: str) -> dict:
    sb = _supabase()
    try:
        if sb:
            url, key = sb
            r = requests.get(f"{url}/rest/v1/perfis?email=eq.{quote(email)}&select=dados",
                             headers=_cab(key), timeout=10)
            r.raise_for_status()
            linhas = r.json()
            return linhas[0]["dados"] if linhas else {}
        with sqlite3.connect(_DB) as con:
            con.execute("create table if not exists perfis (email text primary key, dados text, atualizado text)")
            lin = con.execute("select dados from perfis where email=?", (email,)).fetchone()
            return json.loads(lin[0]) if lin else {}
    except Exception as e:
        st.toast(f"Não consegui carregar seus dados salvos ({e.__class__.__name__}).", icon="⚠️")
        return {}


def _gravar(email: str, dados: dict) -> bool:
    agora = datetime.now(timezone.utc).isoformat()
    sb = _supabase()
    try:
        if sb:
            url, key = sb
            r = requests.post(f"{url}/rest/v1/perfis?on_conflict=email",
                              headers={**_cab(key), "Content-Type": "application/json",
                                       "Prefer": "resolution=merge-duplicates"},
                              json={"email": email, "dados": dados, "atualizado": agora}, timeout=10)
            r.raise_for_status()
            return True
        with sqlite3.connect(_DB) as con:
            con.execute("create table if not exists perfis (email text primary key, dados text, atualizado text)")
            con.execute("insert into perfis values (?,?,?) on conflict(email) do update set "
                        "dados=excluded.dados, atualizado=excluded.atualizado",
                        (email, json.dumps(dados, ensure_ascii=False), agora))
        return True
    except Exception as e:
        st.toast(f"Não consegui salvar seus dados ({e.__class__.__name__}).", icon="⚠️")
        return False


# ------------------------------------------------------------------ sessão
def _configurado() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def usuario():
    """{'email', 'nome'} do usuário logado, ou None (visitante)."""
    try:
        if _configurado() and st.user.is_logged_in:
            email = (st.user.get("email") or "").strip().lower()
            if email:
                return {"email": email, "nome": st.user.get("name") or email.split("@")[0]}
    except Exception:
        pass
    return None


_ROSA = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='-100 -100 200 200'>"
         "<g fill='none' stroke='%231F7A55' stroke-width='.7'><circle r='92'/><circle r='72'/><circle r='46' stroke-dasharray='2 3'/></g>"
         "<polygon points='0,-92 9,-9 0,0 -9,-9' fill='%231F7A55'/><polygon points='0,92 9,9 0,0 -9,9' fill='%231F7A55'/>"
         "<polygon points='92,0 9,-9 0,0 9,9' fill='%233B6BC4'/><polygon points='-92,0 -9,-9 0,0 -9,9' fill='%233B6BC4'/>"
         "<g fill='%23C9A227'><polygon points='56,-56 7,-3 0,0 3,-7'/><polygon points='-56,-56 -7,-3 0,0 -3,-7'/>"
         "<polygon points='56,56 7,3 0,0 3,7'/><polygon points='-56,56 -7,3 0,0 -3,7'/></g></svg>")


def _css_login() -> str:
    return f"""<style>
.stApp {{background:
  radial-gradient(900px 520px at 85% -10%, rgba(59,107,196,.16), transparent 60%),
  radial-gradient(800px 520px at -10% 105%, rgba(31,122,85,.18), transparent 60%),
  radial-gradient(520px 320px at 100% 100%, rgba(201,162,39,.14), transparent 60%), #EEF0F3;}}
.stApp::before {{content:""; position:fixed; inset:0; z-index:0; pointer-events:none; opacity:.10;
  background-image: url("data:image/svg+xml;utf8,{_ROSA}"),
    repeating-linear-gradient(0deg, rgba(31,122,85,.35) 0 1px, transparent 1px 64px),
    repeating-linear-gradient(90deg, rgba(31,122,85,.35) 0 1px, transparent 1px 64px);
  background-repeat:no-repeat, repeat, repeat; background-position:center 46%, 0 0, 0 0;
  background-size:min(820px,140vw), auto, auto;}}
.block-container {{position:relative; z-index:1; padding-top:3.2rem !important;}}
.st-key-login_card {{max-width:440px; margin:0 auto; background:#F9FAFB; border:1px solid #D5DAE0;
  border-radius:26px; box-shadow:0 22px 60px rgba(14,42,92,.20); overflow:hidden; padding:0 0 22px; gap:0 !important;}}
.st-key-login_card > div {{gap:0 !important;}}
.lg-top {{text-align:center; padding:30px 24px 24px; color:#fff;
  background:linear-gradient(160deg,#0E2A5C 0%,#164A8F 55%,#17604A 130%);}}
.lg-top img {{width:112px; height:112px; border-radius:26px; box-shadow:0 10px 26px rgba(0,0,0,.35);}}
.lg-top .nm {{font-size:1.9rem; font-weight:800; letter-spacing:.3px; margin-top:14px; color:#fff;}}
.lg-top .nm b {{color:#E9C85A; font-weight:800;}}
.lg-top .sb {{font-size:.95rem; color:#D8E4F6; margin-top:4px;}}
.lg-body {{padding:22px 26px 6px;}}
.lg-body h3 {{margin:0 0 6px; font-size:1.2rem; font-weight:800; color:#1F2933;}}
.lg-body p {{margin:0; font-size:.9rem; color:#5B6675; line-height:1.5;}}
.lg-chips {{display:flex; flex-wrap:wrap; gap:7px; margin-top:14px;}}
.lg-chips span {{background:#E3E8EE; border:1px solid #D5DAE0; border-radius:999px; padding:4px 11px;
  font-size:.76rem; font-weight:700; color:#1F2933;}}
.st-key-login_card [data-testid="stButton"] {{padding:14px 26px 0;}}
.st-key-login_card button {{border-radius:14px; font-weight:800; padding:.7rem 1rem; border:0;
  background:linear-gradient(135deg,#1F7A55,#17604A); box-shadow:0 8px 20px rgba(31,122,85,.30);}}
.st-key-login_card button p {{color:#fff !important; font-size:1rem;}}
.lg-foot {{padding:12px 26px 0; font-size:.74rem; color:#5B6675; text-align:center; line-height:1.45;}}
</style>"""


def exigir_login(logo_uri: str = "", nome: str = "Bússola B3"):
    """Mostra a tela de entrada e interrompe o app enquanto não houver login (se o login estiver configurado)."""
    if not _configurado():
        return None
    u = usuario()
    if u:
        return u
    st.markdown(_css_login(), unsafe_allow_html=True)
    topo, resto = nome.rsplit(" ", 1) if " " in nome else (nome, "")
    img = f'<img src="{logo_uri}" alt="{nome}">' if logo_uri else ""
    with st.container(key="login_card"):
        st.markdown(
            f'<div class="lg-top">{img}<div class="nm">{topo} <b>{resto}</b></div>'
            f'<div class="sb">Seu norte no mercado de ações brasileiro</div></div>'
            f'<div class="lg-body"><h3>Entre para continuar</h3>'
            f'<p>Com a sua conta Google, suas empresas em análise, seu perfil de investidor e suas carteiras '
            f'ficam guardados e te esperam em qualquer aparelho.</p>'
            f'<div class="lg-chips"><span>📈 Preço justo</span><span>🧭 Análise técnica</span>'
            f'<span>💼 Carteira</span><span>🪙 Cripto</span></div></div>',
            unsafe_allow_html=True)
        st.button("Entrar com Google", icon=":material/login:", type="primary", width="stretch",
                  on_click=st.login, args=("google",))
        st.markdown('<div class="lg-foot">Usamos só o seu nome e e-mail para identificar você. '
                    'Ferramenta educacional, sem recomendação de investimento.</div>', unsafe_allow_html=True)
    st.stop()


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


def iniciar():
    """Carrega os dados do usuário uma vez por sessão, antes dos widgets serem desenhados."""
    u = usuario()
    if not u:
        return None
    if st.session_state.get("_perfil_de") != u["email"]:
        for k, v in _ler(u["email"]).items():
            st.session_state[k] = v
        st.session_state["_perfil_de"] = u["email"]
        st.session_state["_salvo"] = _chave(_snapshot())
    return u


def salvar():
    """Grava no fim de cada execução, só se algo mudou."""
    u = usuario()
    if not u or st.session_state.get("_perfil_de") != u["email"]:
        return
    snap = _snapshot()
    ch = _chave(snap)
    if ch != st.session_state.get("_salvo") and _gravar(u["email"], snap):
        st.session_state["_salvo"] = ch


def menu_conta(sufixo: str = "d"):
    """Nome, e-mail e botão Sair. Desenhar dentro de um popover ou container."""
    u = usuario()
    if not u:
        return
    st.markdown(f"**{u['nome']}**")
    st.caption(u["email"])
    st.button("Sair", icon="🚪", on_click=st.logout, width="stretch", key=f"sair_{sufixo}")
