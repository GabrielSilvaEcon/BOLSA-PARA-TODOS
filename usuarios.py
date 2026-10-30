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


def exigir_login(marca_html: str = ""):
    """Mostra a tela de entrada e interrompe o app enquanto não houver login (se o login estiver configurado)."""
    if not _configurado():
        return None
    u = usuario()
    if u:
        return u
    _, meio, _ = st.columns([1, 1.6, 1])
    with meio:
        if marca_html:
            st.markdown(marca_html, unsafe_allow_html=True)
        st.markdown("### Entre para continuar")
        st.write("Entre com sua conta Google para guardar suas empresas em análise, seu perfil de investidor "
                 "e suas carteiras. Usamos só o seu e-mail e nome para identificar você.")
        st.button("Entrar com Google", icon="🔐", type="primary", width="stretch",
                  on_click=st.login, args=("google",))
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
