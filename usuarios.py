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
    """(url, chave) do Supabase nos secrets, com a URL corrigida se vier sem https:// ou com /rest/v1 no fim."""
    try:
        cfg = st.secrets["supabase"]
        url = str(cfg["url"]).strip().strip("\"'").rstrip("/")
        key = str(cfg["key"]).strip().strip("\"'")
    except Exception:
        return None
    # aceita a linha colada inteira, como NEXT_PUBLIC_SUPABASE_URL=https://xxxx.supabase.co
    if "=" in url:
        url = url.rsplit("=", 1)[1].strip().strip("\"'")
    if "=" in key and not key.startswith(("sb_", "eyJ")):
        key = key.rsplit("=", 1)[1].strip().strip("\"'")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if "." not in url.split("//", 1)[1]:  # só o código do projeto
        url += ".supabase.co"
    return url, key


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
        st.toast(f"Não consegui carregar seus dados salvos ({e.__class__.__name__}: {str(e)[:110]}).", icon="⚠️")
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
        st.toast(f"Não consegui salvar seus dados ({e.__class__.__name__}: {str(e)[:110]}).", icon="⚠️")
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
            if not email and st.user.get("sub"):
                email = f"sub:{st.user.get('sub')}"
            if email:
                return {"email": email, "nome": st.user.get("name") or email.split("@")[0]}
    except Exception:
        pass
    return None


_G = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 48 48'><path fill='%23EA4335' d='M24 9.5c3.5 0 6.6 1.2 9.1 3.6l6.8-6.8C35.8 2.4 30.3 0 24 0 14.6 0 6.5 5.4 2.6 13.2l7.9 6.1C12.4 13.6 17.7 9.5 24 9.5z'/><path fill='%234285F4' d='M46.5 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.7c-.6 3-2.3 5.5-4.8 7.2l7.5 5.8c4.4-4.1 7.1-10.1 7.1-17.5z'/><path fill='%23FBBC05' d='M10.5 28.7c-.5-1.5-.8-3-.8-4.7s.3-3.2.8-4.7l-7.9-6.1C.9 16.4 0 20.1 0 24s.9 7.6 2.6 10.8l7.9-6.1z'/><path fill='%2334A853' d='M24 48c6.5 0 11.9-2.1 15.9-5.8l-7.5-5.8c-2.1 1.4-4.8 2.3-8.4 2.3-6.3 0-11.6-4.1-13.5-9.8l-7.9 6.1C6.5 42.6 14.6 48 24 48z'/></svg>")

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
.stApp::before {{content:""; position:fixed; inset:0; z-index:0; pointer-events:none; opacity:.09;
  background-image: url("data:image/svg+xml;utf8,{_ROSA}"),
    repeating-linear-gradient(0deg, rgba(31,122,85,.35) 0 1px, transparent 1px 64px),
    repeating-linear-gradient(90deg, rgba(31,122,85,.35) 0 1px, transparent 1px 64px);
  background-repeat:no-repeat, repeat, repeat; background-position:center 30%, 0 0, 0 0;
  background-size:min(820px,150vw), auto, auto;}}
.block-container {{position:relative; z-index:1; padding-top:2.4rem !important;}}
.st-key-login_card {{max-width:420px; margin:0 auto; gap:0 !important;}}
.st-key-login_card > div {{gap:.7rem !important;}}
.lg-hero {{position:relative; height:240px; display:flex; align-items:center; justify-content:center; margin-top:.4rem;}}
.lg-halo {{position:absolute; width:236px; height:236px; border-radius:50%;
  background:radial-gradient(circle, rgba(59,107,196,.20), rgba(31,122,85,.10) 55%, transparent 72%);}}
.lg-ring {{position:absolute; border-radius:50%; border:1.5px dashed rgba(31,122,85,.40);}}
.lg-ring.a {{width:212px; height:212px; animation:lgspin 48s linear infinite;}}
.lg-ring.b {{width:176px; height:176px; border-color:rgba(201,162,39,.55); animation:lgspin 36s linear infinite reverse;}}
.lg-hero img {{position:relative; width:128px; height:128px; border-radius:30px; box-shadow:0 16px 36px rgba(14,42,92,.35);}}
@keyframes lgspin {{to {{transform:rotate(360deg);}}}}
.lg-slides {{position:relative; min-height:112px; text-align:center;}}
.lg-s {{position:absolute; inset:0; opacity:0; animation:lgslide 12s infinite;}}
.lg-s.s2 {{animation-delay:4s;}} .lg-s.s3 {{animation-delay:8s;}}
.lg-s h2 {{margin:0 0 6px; font-size:1.55rem; font-weight:800; color:#0E2A5C; line-height:1.15;}}
.lg-s p {{margin:0 auto; max-width:340px; font-size:.95rem; color:#5B6675; line-height:1.45;}}
@keyframes lgslide {{0% {{opacity:0; transform:translateY(8px);}} 4%,30% {{opacity:1; transform:none;}} 34%,100% {{opacity:0;}}}}
.lg-dots {{display:flex; gap:6px; justify-content:center; margin:2px 0 10px;}}
.lg-dots i {{display:block; height:7px; width:7px; border-radius:99px; background:#C8CED6; animation:lgdot 12s infinite;}}
.lg-dots i:nth-child(2) {{animation-delay:4s;}} .lg-dots i:nth-child(3) {{animation-delay:8s;}}
@keyframes lgdot {{0%,30% {{width:24px; background:#1F7A55;}} 34%,100% {{width:7px; background:#C8CED6;}}}}
.st-key-login_card button {{border-radius:999px; min-height:3.2rem; font-weight:800; position:relative;}}
.st-key-login_google button {{border:0; background:linear-gradient(135deg,#1F7A55,#17604A);
  box-shadow:0 10px 22px rgba(31,122,85,.32);}}
.st-key-login_google button p {{color:#fff !important; font-size:1.02rem;}}
.st-key-login_google button::before {{content:""; position:absolute; left:10px; top:50%; transform:translateY(-50%);
  width:2.2rem; height:2.2rem; border-radius:50%; background:#fff url("data:image/svg+xml;utf8,{_G}") center/1.25rem no-repeat;}}
.st-key-login_visit button {{background:#fff; border:1px solid #C8CED6 !important; box-shadow:none;}}
.st-key-login_visit button p {{color:#1F2933 !important; font-size:1rem;}}
.lg-foot {{padding:6px 10px 0; font-size:.74rem; color:#5B6675; text-align:center; line-height:1.5;}}
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


def eh_visitante() -> bool:
    return bool(st.session_state.get("_visitante")) and not usuario()


def _virar_visitante():
    st.session_state["_visitante"] = True


def sair_visitante():
    """Volta para a tela de login."""
    st.session_state.pop("_visitante", None)


def menu_visitante(sufixo: str = "d"):
    st.markdown("**Visitante**")
    st.caption("Você está sem conta: nada fica salvo.")
    st.button("Entrar com Google", icon=":material/login:", on_click=sair_visitante, width="stretch",
              key=f"entrar_{sufixo}")


def exigir_login(logo_uri: str = "", nome: str = "Bússola B3"):
    """Tela de entrada (Google ou visitante). Interrompe o app enquanto não houver login, se ele estiver configurado."""
    if not _configurado():
        return None
    u = usuario()
    if u:
        return u
    if st.session_state.get("_visitante"):
        return None
    st.markdown(_css_login(), unsafe_allow_html=True)
    img = f'<img src="{logo_uri}" alt="{nome}">' if logo_uri else ""
    with st.container(key="login_card"):
        st.markdown(
            f'<div class="lg-hero"><div class="lg-halo"></div><div class="lg-ring a"></div>'
            f'<div class="lg-ring b"></div>{img}</div>'
            '<div class="lg-slides">'
            '<div class="lg-s s1"><h2>Seu norte no mercado brasileiro</h2>'
            '<p>Entenda, em linguagem simples, se o preço de uma ação está justo.</p></div>'
            '<div class="lg-s s2"><h2>Análise técnica sem mistério</h2>'
            '<p>Setups, médias e sinais marcados direto no gráfico.</p></div>'
            '<div class="lg-s s3"><h2>Sua carteira em qualquer aparelho</h2>'
            '<p>Entre com o Google e suas empresas, perfil e compras ficam guardados.</p></div></div>'
            '<div class="lg-dots"><i></i><i></i><i></i></div>',
            unsafe_allow_html=True)
        if st.button("Continuar com o Google", key="login_google", type="primary", width="stretch"):
            try:
                st.login("google")
            except Exception as e:  # mostra o motivo real (o Streamlit esconde a mensagem quando o erro não é tratado)
                st.error(f"Não foi possível iniciar o login: {e}")
        st.button("Continuar como visitante", icon=":material/person:", key="login_visit", width="stretch",
                  on_click=_virar_visitante)
        st.markdown('<div class="lg-foot">Como visitante você usa tudo, mas nada fica salvo. Com a conta Google, '
                    'usamos só o seu nome e e-mail para identificar você. Ferramenta educacional, '
                    'sem recomendação de investimento.</div>', unsafe_allow_html=True)
        with st.expander("Problemas para entrar?"):
            st.write("Abra o app direto no Chrome ou no Safari (não pelo navegador de dentro de outro app) "
                     "e deixe os cookies liberados.")
            st.json(_diagnostico())
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
        st.toast(f"Bem-vindo, {u['nome'].split()[0]}! Seus dados estão carregados.", icon="👋")
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


def primeiro_nome() -> str:
    u = usuario()
    return (u["nome"].split()[0][:12]) if u else ""


def menu_conta(sufixo: str = "d"):
    """Nome, e-mail e botão Sair. Desenhar dentro de um popover ou container."""
    u = usuario()
    if not u:
        return
    st.markdown(f"**{u['nome']}**")
    st.caption(u["email"])
    st.button("Sair", icon=":material/logout:", on_click=st.logout, width="stretch", key=f"sair_{sufixo}")


def _apagar(email: str) -> bool:
    sb = _supabase()
    try:
        if sb:
            url, key = sb
            r = requests.delete(f"{url}/rest/v1/perfis?email=eq.{quote(email)}", headers=_cab(key), timeout=10)
            r.raise_for_status()
            return True
        with sqlite3.connect(_DB) as con:
            con.execute("create table if not exists perfis (email text primary key, dados text, atualizado text)")
            con.execute("delete from perfis where email=?", (email,))
        return True
    except Exception as e:
        st.error(f"Não consegui apagar seus dados ({e.__class__.__name__}).")
        return False


def pagina_conta():
    """Página 'Minha conta': dados do perfil, o que está salvo, sair e apagar dados."""
    st.markdown('<div class="pghead"><div class="pgt">Minha conta</div>'
                '<div class="pgsub">Seus dados, o que fica guardado e como sair.</div></div>', unsafe_allow_html=True)
    u = usuario()
    if not u:
        st.info("Você está como visitante e nada fica salvo. Entre com o Google para guardar suas empresas, "
                "seu perfil e suas carteiras.")
        if _configurado():
            st.button("Entrar com Google", icon=":material/login:", type="primary", on_click=sair_visitante,
                      key="entrar_conta")
        return
    foto = ""
    try:
        foto = st.user.get("picture") or ""
    except Exception:
        pass
    avatar = (f'<img src="{foto}" width="64" height="64" referrerpolicy="no-referrer" '
              f'style="border-radius:50%;flex-shrink:0;">' if foto else
              '<div style="width:64px;height:64px;border-radius:50%;background:#1F7A55;color:#fff;display:flex;'
              'align-items:center;justify-content:center;font-size:1.6rem;font-weight:800;flex-shrink:0;">'
              f'{u["nome"][:1].upper()}</div>')
    st.markdown(f'<div class="card" style="display:flex;gap:14px;align-items:center;">{avatar}'
                f'<div><div class="tk">{u["nome"]}</div><div class="nm" style="margin:0;">{u["email"]}</div></div></div>',
                unsafe_allow_html=True)

    ss = st.session_state
    lotes = len(ss.get("cart_ficticia", [])) + len(ss.get("cart_real", []))
    c1, c2, c3, c4 = st.columns(4)
    for col, rot, val in ((c1, "Empresas em análise", len(ss.get("sel_ativos", []))),
                          (c2, "Perfil", ss.get("perfil", "—")),
                          (c3, "Moedas cripto", len(ss.get("cripto_ativos", []))),
                          (c4, "Compras na carteira", lotes)):
        col.markdown(f'<div class="kpi"><div class="lbl">{rot}</div><div class="v">{val}</div></div>',
                     unsafe_allow_html=True)

    if _supabase():
        st.caption("☁️ Seus dados ficam guardados na nuvem e acompanham você em qualquer aparelho. "
                   "Tudo é salvo automaticamente.")
    else:
        st.warning("Seus dados estão sendo guardados só neste servidor e podem se perder quando o app for atualizado.")

    st.markdown("#### Sessão")
    st.button("Sair da conta", icon=":material/logout:", on_click=st.logout, type="primary", key="sair_conta")

    with st.expander("Apagar meus dados salvos"):
        st.write("Remove do banco as empresas em análise, o perfil, as moedas e as carteiras guardadas. "
                 "Isso não pode ser desfeito.")
        ok = st.checkbox("Entendi, quero apagar tudo", key="conf_apagar")
        if st.button("Apagar agora", disabled=not ok, key="btn_apagar"):
            if _apagar(u["email"]):
                for k in list(ss.keys()):
                    if isinstance(k, str) and (k in CHAVES or k.startswith(PREFIXOS)):
                        del ss[k]
                ss["_salvo"] = _chave(_snapshot())
                st.success("Dados apagados. Recarregue a página para começar do zero.")
