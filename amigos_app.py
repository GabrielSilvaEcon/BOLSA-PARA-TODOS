"""Meus Amigos · telas e ações (Streamlit). Regras em `amigos.py`; permissões no `banco` (cada ação parte da conta logada).

 · Lista de amigos (avatar, nome, @usuário, nível se a pessoa mostra, atividade "hoje/esta semana" quando há registro de login).
 · Busca por nome ou usuário: filtra os amigos e encontra outros jogadores (só quem deixa o perfil visível e sem bloqueio).
 · Solicitações recebidas (aceitar/recusar) e enviadas (cancelar); convites para jogar recebidos (entrar na sala do amigo).
 · Comparação de desempenho entre amigos, por jogo (Trade Battle ou Ticker Battle), só com quem mostra as estatísticas.
Nada de chat, feed ou curtidas. Nada financeiro sai daqui.
"""
from __future__ import annotations

import html
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

import amigos as AM
import banco
import jogos as J
import perfis as PF
import usuarios

_e = html.escape
_P = "html body .stApp.stApp.stApp"
_TTL = 60

CSS_LINK = "<style>" + "".join(l.strip() for l in f"""
{_P} [class*="st-key-lk_"]{{position:relative;gap:0 !important}}
{_P} [class*="st-key-lk_"] [data-testid="stElementContainer"]:has(.stButton){{position:absolute !important;inset:0;z-index:3;margin:0 !important;width:100% !important}}
{_P} [class*="st-key-lk_"] .stButton,{_P} [class*="st-key-lk_"] .stButton > button[data-testid]{{width:100% !important;height:100% !important;min-height:0 !important}}
{_P} [data-testid="stMain"] [class*="st-key-lk_"] .stButton > button[data-testid]{{opacity:0 !important;cursor:pointer;background:transparent !important;border:0 !important;box-shadow:none !important}}
{_P} [class*="st-key-lk_"]:hover .am-lin,{_P} [class*="st-key-lk_"]:hover .jg-lin{{filter:brightness(1.15)}}
""".splitlines()) + "</style>"   # linhas e grades clicáveis (vai no CSS global do app)

CSS = CSS_LINK + "<style>" + "".join(l.strip() for l in f"""
{_P} .am-lin{{display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:16px;border:1.5px solid rgba(139,108,255,.45);
  background:linear-gradient(160deg,#241A86,#150F55)}}
{_P} .am-lin .av{{flex:0 0 42px;width:42px;height:42px;border-radius:50%;overflow:hidden;background:#1B1545;box-shadow:0 0 0 2px #34E85E}}
{_P} .am-lin .av img{{width:100%;height:100%;object-fit:cover;display:block}}
{_P} .am-lin .nm{{flex:1;min-width:0;font-weight:800;font-size:.92rem;line-height:1.2;color:#fff !important;-webkit-text-fill-color:#fff !important;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
{_P} .am-lin .nm small{{display:block;font-weight:600;font-size:.74rem;color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important}}
{_P} .am-lin .nv{{flex:0 0 auto;padding:2px 8px;border-radius:999px;background:linear-gradient(160deg,#FFE08A,#E0A21A);font-weight:900;font-size:.7rem;
  color:#3A2400 !important;-webkit-text-fill-color:#3A2400 !important}}
{_P} .am-on{{display:inline-block;width:8px;height:8px;margin-right:4px;border-radius:50%;background:#34E85E;box-shadow:0 0 6px #34E85E}}
{_P} .am-on.sem{{background:#F2B84B;box-shadow:none}}
{_P} .am-sec{{margin:14px 0 6px;font-weight:900;font-size:1rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .am-sec small{{float:right;font-weight:700;font-size:.74rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .am-vazio{{text-align:center;padding:12px;border-radius:16px;border:1.5px dashed rgba(139,108,255,.55);font-size:.84rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .am-cv{{padding:10px 12px;border-radius:18px;border:2px solid #F2B84B;background:linear-gradient(160deg,rgba(242,184,75,.2),#150F55);
  font-size:.86rem;color:#fff !important;-webkit-text-fill-color:#fff !important;box-shadow:0 0 14px rgba(242,184,75,.35)}}
{_P} .am-cv b{{color:#FFE3A3 !important;-webkit-text-fill-color:#FFE3A3 !important}}
{_P} .am-cmp{{display:grid;grid-template-columns:22px 1fr auto;align-items:center;gap:8px;padding:7px 10px;margin-bottom:5px;border-radius:14px;
  background:rgba(20,14,70,.75);border:1.5px solid rgba(139,108,255,.35)}}
{_P} .am-cmp.eu{{border-color:#34E85E;box-shadow:0 0 12px rgba(52,232,94,.35)}}
{_P} .am-cmp .p{{font-weight:900;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} .am-cmp .n{{min-width:0;font-weight:800;font-size:.86rem;color:#fff !important;-webkit-text-fill-color:#fff !important;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
{_P} .am-cmp .n small{{display:block;font-weight:600;font-size:.7rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .am-cmp .b{{grid-column:2 / 4;height:7px;border-radius:99px;background:rgba(255,255,255,.1);overflow:hidden}}
{_P} .am-cmp .b i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#8B6CFF,#34E85E)}}
{_P} .am-cmp .b i.neg{{background:linear-gradient(90deg,#FF6B87,#FF9AAE)}}
{_P} .am-cmp .v{{font-weight:900;font-size:.9rem;color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}
{_P} .am-cmp .v.neg{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
""".splitlines()) + "</style>"


# ------------------------------------------------------------------ serviço (leituras com cache curto; toda gravação passa pelo banco)
def _ss():
    return st.session_state


def _ator():
    try:
        return usuarios.ator()
    except Exception:
        return None


def _cache(chave: str, ttl: float, fn):
    c = _ss().get(chave)
    if c and time.time() - c[0] < ttl:
        return c[1]
    v = fn()
    _ss()[chave] = (time.time(), v)
    return v


def limpar() -> None:
    """Depois de qualquer ação: relê relações, perfis e listas na próxima tela."""
    for k in [k for k in _ss().keys() if str(k).startswith("_am_")] + ["_pj_pub"]:
        _ss().pop(k, None)


def mapa() -> dict[str, tuple[str, dict]]:
    return _cache("_am_mapa", _TTL, banco.sis_perfis_por_hash)


def relacoes() -> dict[str, dict]:
    a = _ator()
    return _cache("_am_rel", 20, lambda: banco.social_relacoes(a)) if a else {}


def bloqueios() -> tuple[set[str], set[str]]:
    """(quem eu bloqueei, quem me bloqueou)."""
    a = _ator()
    if not a:
        return set(), set()
    return _cache("_am_blq", 30, lambda: (set(banco.social_bloqueados(a)), banco.social_bloqueado_por(a)))


def _ativos() -> dict[str, str]:
    desde = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat(timespec="seconds")
    try:
        return _cache("_am_ativos", 120, lambda: banco.sis_ativos_desde(desde))
    except Exception:
        return {}


def info(h: str) -> dict | None:
    """Cartão de um jogador para listas: nome, usuário, avatar/foto e nível (se ele mostra). Sem e-mail; cache por sessão."""
    par = mapa().get(h)
    if not par:
        return None
    email, doc = par
    p = PF.sanear(doc)
    if not p["usuario"]:
        return None
    cache = _ss().setdefault("_am_info", {})
    if h in cache and time.time() - cache[h][0] < 300:
        return cache[h][1]
    nivel = None
    if p["privacidade"]["mostrar_nivel"]:
        try:
            nivel = PF.progresso((banco.sis_dados_de(email) or {}).get("edu_progresso"))["nivel"]
        except Exception:
            nivel = None
    foto = ""
    if p["avatar"] == PF.FOTO:
        try:
            import perfil_foto as FT
            foto = FT.uri(banco.sis_estado_ler(email, "perfil_foto"))
        except Exception:
            foto = ""
    x = {"h": h, "usuario": p["usuario"], "nome": p["nome"] or p["usuario"], "avatar": p["avatar"], "foto": foto, "nivel": nivel,
         "mostra_jogos": p["privacidade"]["mostrar_jogos"], "_email": email}
    cache[h] = (time.time(), x)
    return x


def _publico(x: dict) -> dict:
    return {k: v for k, v in x.items() if not k.startswith("_")}


# ------------------------------------------------------------------ navegação para o perfil de alguém
def ir_jogador(usuario: str) -> None:
    """Callback: abre /jogador?u=<usuário> pelo mesmo `_nav_pend` do app (com o parâmetro)."""
    _ss()["_nav_pend"] = "jogador"
    _ss()["_nav_qp"] = {"u": usuario}
    try:
        st.query_params["u"] = usuario
    except Exception:
        pass


def linha_clicavel(chave: str, html_linha: str, usuario: str | None, rotulo: str = "") -> None:
    """Uma linha (HTML) inteira clicável: um botão invisível por cima leva ao perfil público."""
    with st.container(key=f"lk_{chave}"):
        st.markdown(html_linha, unsafe_allow_html=True)
        if usuario:
            st.button(rotulo or f"Ver perfil de {usuario}", key=f"lkb_{chave}", on_click=ir_jogador, args=(usuario,))


def _indice() -> dict:
    """Índices para levar de qualquer nome público (NickName da Competição, da liga de estudo, das salas) ao perfil. Só no servidor."""
    def montar():
        por_email, por_k = {}, {}
        for r in banco.sis_comp_todos("perfil_jogador"):
            p = PF.sanear(r["dados"])
            if p["usuario"]:
                vis = p["privacidade"]["visivel"] != "ninguem"
                por_email[r["email"]] = p["usuario"] if vis else ""
                if vis:
                    por_k[p["usuario_k"]] = p["usuario"]
        comp = {}
        try:
            for r in banco.sis_comp_todos("comp_ordens"):
                k = str((r["dados"] or {}).get("apelido_k") or "")
                if k:
                    comp[k] = r["email"]
        except Exception:
            pass
        return {"por_email": por_email, "por_k": por_k, "comp": comp}
    return _cache("_am_idx", _TTL, montar)


def usuario_de_email(email: str, apelido: str = "") -> str | None:
    """Nome de usuário (para o link) da conta `email`. Quem joga mas ainda não tem perfil ganha o perfil básico do NickName público.
    None se a pessoa esconde o perfil de todos."""
    idx = _indice()
    if email in idx["por_email"]:
        return idx["por_email"][email] or None
    if apelido:
        try:
            if banco.sis_perfil_padrao(email, apelido):
                u = PF.inicial(apelido)["usuario"]
                idx["por_email"][email] = u
                idx["por_k"][PF.chave_usuario(u)] = u
                return u
        except Exception as e:
            banco.registrar_erro("amigos_app.usuario_de_email", e)
    return None


def usuario_de_apelido(apelido: str) -> str | None:
    """Do NickName mostrado em um ranking (Competição/Wallet Game, liga de estudo, salas) ao nome de usuário do perfil."""
    k = str(apelido or "").strip().lower()
    if not k or k == "jogador":
        return None
    try:
        idx = _indice()
        email = idx["comp"].get(k)
        if email:
            return usuario_de_email(email, apelido)
        return idx["por_k"].get(k)
    except Exception as e:
        banco.registrar_erro("amigos_app.usuario_de_apelido", e)
        return None


def avatar_por_apelido(apelido: str, tamanho: int = 42) -> str | None:
    """Avatar equipado (com moldura da raridade) de quem aparece num ranking pelo NickName público. None se não achar a conta."""
    import perfis_app as PA
    k = str(apelido or "").strip().lower()
    if not k:
        return None
    try:
        idx = _indice()
        email = idx["comp"].get(k)
        if not email:
            u = idx["por_k"].get(k)
            email = next((e for e, us in idx["por_email"].items() if us and us.lower() == k), None) if u else None
        a = _ator()
        if not email and a and k == str((PA.meu_perfil() or {}).get("usuario_k") or ""):
            email = a.email
        return PA.avatar_html_email(email, tamanho) if email else None
    except Exception:
        return None


def lista_clicavel(chave: str, linhas: list[tuple[str, str | None]], abre: str = "", fecha: str = "") -> None:
    """Várias linhas HTML, cada uma clicável (abre o perfil de quem está nela). `abre`/`fecha` envolvem cada linha com a classe da lista
    original, para manter o visual."""
    st.markdown(CSS, unsafe_allow_html=True)
    for i, (h, u) in enumerate(linhas):
        linha_clicavel(f"{chave}_{i}", abre + h + fecha, u)


def grade_clicavel(chave: str, html_bloco: str, usuarios: list[str | None], colunas: str) -> None:
    """Bloco em colunas (pódio, chips) com um botão invisível sobre cada coluna. `colunas` = grid-template-columns do bloco original."""
    st.markdown(f"<style>{_P} .st-key-gk_{chave}{{position:relative;gap:0 !important}}"
                f"{_P} .st-key-gk_{chave}_b{{position:absolute !important;inset:0;z-index:3;display:grid !important;grid-template-columns:{colunas};gap:8px !important}}"
                f"{_P} .st-key-gk_{chave}_b > div{{width:auto !important;height:100%;min-width:0}}"
                f"{_P} .st-key-gk_{chave}_b .stButton,{_P} [data-testid='stMain'] .st-key-gk_{chave}_b .stButton > button[data-testid]{{width:100% !important;height:100% !important;"
                f"opacity:0 !important;min-height:0 !important;background:transparent !important;border:0 !important;box-shadow:none !important;cursor:pointer}}</style>",
                unsafe_allow_html=True)
    with st.container(key=f"gk_{chave}"):
        st.markdown(html_bloco, unsafe_allow_html=True)
        with st.container(key=f"gk_{chave}_b"):
            for i, u in enumerate(usuarios):
                if u:
                    st.button(f"Ver perfil de {u}", key=f"gk_{chave}_{i}", on_click=ir_jogador, args=(u,))
                else:
                    st.markdown("&nbsp;")


def botao_perfil(chave: str, nick: str, rotulo: str | None = None) -> None:
    """Botão visível "Ver perfil" para telas em que o nome não está numa lista (adversário do duelo, jogadores da sala)."""
    u = usuario_de_apelido(nick)
    if u and st.button(rotulo or f"Ver perfil de {nick}", key=f"bp_{chave}", icon=":material/person:"):
        ir_jogador(u)
        st.rerun(scope="app")                       # também funciona dentro de telas que se atualizam sozinhas (fragmentos)


def _av(x: dict) -> str:
    import perfis_app as PA
    return PA.avatar_html(x["avatar"], x.get("foto", ""), 42)


def html_linha(x: dict, extra: str = "", atividade: str | None = None) -> str:
    at = {"hoje": "<span class='am-on'></span>Ativo hoje", "semana": "<span class='am-on sem'></span>Ativo esta semana"}.get(atividade or "", "")
    sub = "@" + _e(x["usuario"]) + (f" · {at}" if at else "") + (f" · {_e(extra)}" if extra else "")
    nv = f"<span class='nv'>Nível {x['nivel']}</span>" if x.get("nivel") else ""
    return f"<div class='am-lin'>{_av(x)}<span class='nm'>{_e(x['nome'])}<small>{sub}</small></span>{nv}</div>"


# ------------------------------------------------------------------ ações (callbacks): mensagem clara de sucesso ou erro
def _msg(ok: bool, texto: str) -> None:
    _ss()["_amsg_tela"] = (ok, texto)


def _acao(fn, sucesso: str, *a, **kw) -> bool:
    try:
        r = fn(_ator(), *a, **kw)
    except AM.ErroAmigos as e:
        _msg(False, str(e))
        return False
    except banco.SemPermissao:
        _msg(False, "Faça login para continuar.")
        return False
    except Exception as e:
        banco.registrar_erro(f"amigos_app.{getattr(fn, '__name__', 'acao')}", e)
        _msg(False, "Não consegui concluir agora. Tente de novo em instantes.")
        return False
    finally:
        limpar()
    if r is False:
        _msg(False, "Essa solicitação não existe mais.")
        return False
    _msg(True, sucesso if not callable(sucesso) else sucesso(r))
    return True


def pedir(usuario: str) -> None:
    _acao(lambda a, u: banco.amigo_pedir(a, PF.chave_usuario(u)), lambda r: "Vocês agora são amigos!" if r == "aceito" else "Solicitação enviada!", usuario)


def aceitar(h: str) -> None:
    _acao(banco.amigo_responder, "Solicitação aceita! Agora vocês são amigos.", h, True)


def recusar(h: str) -> None:
    _acao(banco.amigo_responder, "Solicitação recusada.", h, False)


def cancelar(h: str) -> None:
    _acao(banco.amigo_remover, "Solicitação cancelada.", h)


def remover(h: str) -> None:
    _acao(banco.amigo_remover, "Amizade desfeita.", h)


def bloquear(h: str) -> None:
    if _acao(banco.bloquear, "Jogador bloqueado. Vocês não verão mais o perfil um do outro.", h):
        _ss()["_nav_pend"] = "jogos-amigos"


def desbloquear(h: str) -> None:
    _acao(banco.desbloquear, "Jogador desbloqueado.", h)


def denunciar(h: str) -> None:
    motivo, texto = _ss().get(f"pp_den_mot_{h}"), _ss().get(f"pp_den_txt_{h}", "")

    def enviar(a, hh):
        if not banco.denunciar(a, hh, motivo, texto):
            raise AM.ErroAmigos("Você já denunciou este perfil hoje.")
        return True
    if _acao(enviar, "Denúncia enviada. A equipe do TickerHunters vai analisar. Obrigado!", h):
        _ss().pop(f"pp_den_txt_{h}", None)


def convidar(h: str, jogo: str) -> None:
    """Cria a sala privada pelo fluxo normal do jogo (como o botão "Criar sala") e avisa o amigo com o código."""
    a = _ator()
    if not a:
        return _msg(False, "Faça login para convidar.")
    ss = _ss()
    try:
        if jogo == "trade":
            import trader_battle_app as TBA
            import trader_online_dados as TOD
            tf = ss.get("tb_tf") or "15m"
            r = TOD.criar_sala(a.email, tf, None, TBA._formato(tf))
            cod = r.get("codigo") or ((TOD._row(r["id"]) or {}).get("dados") or {}).get("sala", {}).get("codigo", "")
            ss["tb_on_pid"], destino = r["id"], "trader"
        else:
            import battle_online_dados as D
            r = D.criar_sala(a.email)
            cod = r.get("codigo") or ""
            ss["on_pid"], ss["bt_tela"], destino = r["id"], "sala", "battle"
        if not cod:
            return _msg(False, "Você já está em uma partida em andamento. Termine ou saia dela para convidar.")
        banco.convite_jogo_enviar(a, h, jogo, cod)
    except AM.ErroAmigos as e:
        return _msg(False, str(e))
    except Exception as e:
        msg = str(e) if type(e).__name__ in ("ErroPartida", "ErroSala", "ErroTrader") else "Não consegui criar a sala agora. Tente de novo em instantes."
        if msg.startswith("Não consegui"):
            banco.registrar_erro("amigos_app.convidar", e)
        return _msg(False, msg)
    finally:
        limpar()
    _msg(True, f"Convite enviado! Sala {cod} criada: seu amigo recebe o aviso e entra por Meus Amigos.")
    try:
        st.toast(f"Convite enviado! Sala {cod}: seu amigo recebe o aviso.", icon="🎮")
    except Exception:
        pass
    ss["_nav_pend"] = destino


def entrar_convite(h: str, jogo: str, codigo: str) -> None:
    """Entra na sala do amigo pelo fluxo normal de "entrar com código" do jogo."""
    a = _ator()
    if not a:
        return
    ss = _ss()
    try:
        if jogo == "trade":
            import trader_online_dados as TOD
            ss["tb_on_pid"] = TOD.entrar_na_sala(a.email, codigo, None)["id"]
            destino = "trader"
        else:
            import battle_online_dados as D
            pid = D.entrar_na_sala(a.email, codigo)["id"]
            ss.update(on_pid=pid, on_visto=0, bt_tela="espera")
            ss.pop("on_vis", None)
            destino = "battle"
        banco.convite_apagar(a, h)
    except Exception as e:
        if type(e).__name__ not in ("ErroPartida", "ErroSala", "ErroTrader"):
            banco.registrar_erro("amigos_app.entrar_convite", e)
            return _msg(False, "Não consegui entrar na sala agora. Tente de novo em instantes.")
        try:
            banco.convite_apagar(a, h)
        except Exception:
            pass
        return _msg(False, f"{e} O convite foi removido.")
    finally:
        limpar()
    ss["_nav_pend"] = destino


def recusar_convite(h: str) -> None:
    _acao(lambda a, hh: banco.convite_apagar(a, hh) or True, "Convite recusado.", h)


def mostrar_msg() -> None:
    m = _ss().pop("_amsg_tela", None)
    if m:
        (st.success if m[0] else st.error)(m[1], icon=":material/check_circle:" if m[0] else ":material/error:")


# ------------------------------------------------------------------ TELA · Meus Amigos (aba Amigos)
def secao_amigos() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    a = _ator()
    if not a:
        return
    mostrar_msg()
    try:
        rel = relacoes()
        meus_blq, me_blq = bloqueios()
        eu_h = banco._h_conta(a.email)
    except Exception as e:
        banco.registrar_erro("amigos_app.secao", e)
        st.markdown("<div class='am-vazio'>Seus amigos não carregaram agora. Tente de novo em instantes.</div>", unsafe_allow_html=True)
        return
    por_estado = {k: [h for h, r in rel.items() if r["estado"] == k and h not in me_blq] for k in AM.ESTADOS}
    # ---- convites para jogar
    try:
        convites = _cache("_am_conv", 15, lambda: banco.convites_recebidos(a))
    except Exception:
        convites = []
    for i, cv in enumerate(convites):
        x = info(cv["h"])
        if not x:
            continue
        st.markdown(f"<div class='am-cv'>🎮 <b>@{_e(x['usuario'])}</b> convidou você para o <b>{_e(AM.JOGOS_CONVITE[cv['jogo']])}</b> · sala {_e(cv['codigo'])}</div>",
                    unsafe_allow_html=True)
        c1, c2 = st.columns([1.4, 1])
        c1.button("Entrar na sala", key=f"am_cv_ok_{i}", icon=":material/login:", type="primary", width="stretch", on_click=entrar_convite,
                  args=(cv["h"], cv["jogo"], cv["codigo"]))
        c2.button("Recusar", key=f"am_cv_no_{i}", width="stretch", on_click=recusar_convite, args=(cv["h"],))
    # ---- solicitações recebidas
    if por_estado[AM.RECEBIDA]:
        st.markdown(f"<div class='am-sec'>📨 Solicitações recebidas<small>{len(por_estado[AM.RECEBIDA])}</small></div>", unsafe_allow_html=True)
        for h in por_estado[AM.RECEBIDA]:
            x = info(h)
            if not x:
                continue
            linha_clicavel(f"rec_{h}", html_linha(x), x["usuario"])
            c1, c2 = st.columns(2)
            c1.button("Aceitar", key=f"am_ac_{h}", icon=":material/check:", type="primary", width="stretch", on_click=aceitar, args=(h,))
            c2.button("Recusar", key=f"am_rc_{h}", icon=":material/close:", width="stretch", on_click=recusar, args=(h,))
    # ---- busca
    termo = st.text_input("Buscar por nome ou usuário", key="am_busca", placeholder="Buscar amigos ou jogadores por nome ou @usuário", max_chars=30,
                          label_visibility="collapsed")
    amigos_inf = [x for x in (info(h) for h in por_estado[AM.AMIGOS]) if x]
    lista = AM.buscar(amigos_inf, termo)
    ativos = _ativos()
    st.markdown(f"<div class='am-sec'>👥 Amigos<small>{len(amigos_inf)}</small></div>", unsafe_allow_html=True)
    if not amigos_inf:
        st.markdown("<div class='am-vazio'>Você ainda não tem amigos no TickerHunters. Busque um jogador pelo nome ou toque em alguém no ranking "
                    "para abrir o perfil e adicionar.</div>", unsafe_allow_html=True)
    elif not lista:
        st.markdown("<div class='am-vazio'>Nenhum amigo com esse nome.</div>", unsafe_allow_html=True)
    for x in sorted(lista, key=lambda x: x["nome"].lower()):
        linha_clicavel(f"am_{x['h']}", html_linha(x, atividade=AM.atividade(ativos.get(x["_email"]), datetime.now(timezone.utc))), x["usuario"])
    if termo and len(termo.strip().lstrip("@")) >= 2:
        ja = set(rel) | meus_blq | me_blq | {eu_h}
        outros = []
        for h, (email, doc) in mapa().items():
            p = PF.sanear(doc)
            if h in ja or not p["usuario"] or p["privacidade"]["visivel"] == "ninguem":
                continue
            outros.append({"h": h, "usuario": p["usuario"], "nome": p["nome"] or p["usuario"]})
        achados = AM.buscar(outros, termo)[:8]
        st.markdown("<div class='am-sec'>🔎 Outros jogadores</div>", unsafe_allow_html=True)
        if not achados:
            st.markdown("<div class='am-vazio'>Nenhum jogador encontrado com esse nome.</div>", unsafe_allow_html=True)
        for o in achados:
            x = info(o["h"])
            if x:
                linha_clicavel(f"bu_{o['h']}", html_linha(x, "toque para ver o perfil"), x["usuario"])
    # ---- solicitações enviadas
    if por_estado[AM.ENVIADA]:
        with st.expander(f"Solicitações enviadas ({len(por_estado[AM.ENVIADA])})", icon=":material/outgoing_mail:"):
            for h in por_estado[AM.ENVIADA]:
                x = info(h)
                if not x:
                    continue
                linha_clicavel(f"env_{h}", html_linha(x, "aguardando resposta"), x["usuario"])
                st.button("Cancelar solicitação", key=f"am_cn_{h}", icon=":material/close:", on_click=cancelar, args=(h,))
    # ---- comparação
    if amigos_inf:
        _comparacao(a, amigos_inf)


def _comparacao(a, amigos_inf: list[dict]) -> None:
    st.markdown("<div class='am-sec'>📊 Comparar desempenho</div>", unsafe_allow_html=True)
    jogo = st.segmented_control("Jogo da comparação", list(J.JOGOS), default=J.TRADE, key="am_cmp_jogo", format_func=lambda j: J.NOME[j],
                                label_visibility="collapsed") or J.TRADE
    try:
        import jogos_app as JA
        por_email = {r["email"]: r["dados"] for r in JA.placares()}
    except Exception as e:
        banco.registrar_erro("amigos_app.comparacao", e)
        st.markdown("<div class='am-vazio'>A comparação não carregou agora.</div>", unsafe_allow_html=True)
        return
    import perfis_app as PA
    eu_p = PA.meu_perfil()
    eu = {"usuario": eu_p.get("usuario") or "você", "nome": eu_p.get("nome") or "Você", "eu": True, "placar": por_email.get(a.email) or {}}
    outros = [{"usuario": x["usuario"], "nome": x["nome"], "placar": (por_email.get(x["_email"]) or {}) if x["mostra_jogos"] else None} for x in amigos_inf]
    linhas = AM.comparar(eu, outros, jogo)
    ocultos = sum(1 for o in outros if o["placar"] is None)
    if all(r["partidas"] == 0 for r in linhas):
        st.markdown(f"<div class='am-vazio'>Ninguém aqui terminou uma partida do {_e(J.NOME[jogo])} ainda.</div>", unsafe_allow_html=True)
    else:
        teto = max(abs(r["valor"]) for r in linhas) or 1
        for r in linhas:
            v = r["valor"]
            if jogo == J.TRADE:
                val = f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f} pts".replace(".", ",")
                sub = f"{r['partidas']} partidas · {r['vitorias']} vitórias em sala" + (f" · {r['taxa']}%" if r["taxa"] is not None else "")
            else:
                val = f"{int(v)} vitória{'s' if v != 1 else ''}"
                sub = f"{r['partidas']} duelos · {r['empates']} empates · {r['derrotas']} derrotas" + (f" · {r['taxa']}%" if r["taxa"] is not None else "")
            linha_clicavel(f"cmp_{jogo}_{r['pos']}",
                           f"<div class='am-cmp{' eu' if r['eu'] else ''}'><span class='p'>{r['pos']}</span><span class='n'>{_e(r['nome'])}{' (você)' if r['eu'] else ''}"
                           f"<small>{_e(sub)}</small></span><span class='v{' neg' if v < 0 else ''}'>{_e(val)}</span>"
                           f"<div class='b'><i class='{'neg' if v < 0 else ''}' style='width:{abs(v) / teto * 100:.0f}%'></i></div></div>",
                           None if r["eu"] else r["usuario"])
    if ocultos:
        st.caption(f"{ocultos} amigo{'s' if ocultos > 1 else ''} esconde{'m' if ocultos > 1 else ''} as estatísticas e não aparece{'m' if ocultos > 1 else ''} na comparação.")


def secao_bloqueados() -> None:
    """Lista de quem a conta bloqueou, com Desbloquear (em Editar Perfil › Privacidade). Ação imediata."""
    try:
        meus, _ = bloqueios()
    except Exception:
        return
    if not meus:
        st.caption("Você não bloqueou ninguém.")
        return
    st.markdown(CSS, unsafe_allow_html=True)
    for h in sorted(meus):
        x = info(h)
        nome = f"@{x['usuario']}" if x else "Jogador"
        c1, c2 = st.columns([2, 1])
        c1.markdown(f"🚫 {_e(nome)}")
        c2.button("Desbloquear", key=f"am_db_{h}", width="stretch", on_click=desbloquear, args=(h,))
