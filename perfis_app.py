"""Perfil de jogador · serviço e telas (Streamlit). As regras e a validação ficam em `perfis.py`; a segurança, no `banco` (só a própria conta grava).

 · `meu_perfil()`: perfil da conta logada; na primeira vez nasce do NickName do cadastro (com a reserva do nome).
 · `salvar(form)`: valida, reserva o nome novo (atômico), libera o antigo e grava. Nunca recebe XP, pontos ou conquistas.
 · `perfil_publico(usuario)`: o que outra pessoa pode ver (lista fechada de campos + privacidade), montado das fontes reais.
 · Telas: `secao_editar()` (dentro de Minha conta › Perfil) e `pagina_publica()` (/jogador?u=<nome>).
"""
from __future__ import annotations

import html
import importlib
import time
from datetime import datetime, timezone

import streamlit as st

import banco
import perfis as PF
import usuarios

_e = html.escape
_P = "html body .stApp.stApp.stApp"
_CACHE_PUB_S = 60

CSS = "<style>" + "".join(l.strip() for l in f"""
{_P} .pj-card{{display:flex;gap:12px;align-items:center;padding:12px;border-radius:20px;border:2px solid #8B6CFF;
  background:radial-gradient(120% 90% at 0 0,rgba(139,108,255,.28),transparent 60%),linear-gradient(160deg,#241A86,#0E0840);box-shadow:0 0 16px rgba(139,108,255,.4)}}
{_P} .pj-av{{flex:none;width:72px;height:72px;border-radius:50%;overflow:hidden;background:#1B1545;box-shadow:0 0 0 3px #34E85E,0 0 14px rgba(52,232,94,.5)}}
{_P} .pj-av img{{width:100%;height:100%;object-fit:cover}}
{_P} .pj-t{{flex:1;min-width:0}}
{_P} .pj-t b{{display:block;font-size:1.15rem;font-weight:900;color:#fff !important;-webkit-text-fill-color:#fff !important;overflow:hidden;text-overflow:ellipsis}}
{_P} .pj-t span{{display:block;font-size:.82rem;font-weight:700;color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important}}
{_P} .pj-t small{{display:block;margin-top:2px;font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .pj-bio{{margin:8px 0;padding:8px 12px;border-radius:14px;border:1px solid rgba(139,108,255,.4);white-space:pre-line;font-size:.86rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .pj-g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(96px,1fr));gap:6px;margin:6px 0}}
{_P} .pj-g div{{text-align:center;padding:8px 4px;border-radius:14px;border:1.5px solid rgba(139,108,255,.5);background:linear-gradient(160deg,#241A86,#150F55)}}
{_P} .pj-g small{{display:block;font-size:.66rem;font-weight:700;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .pj-g b{{display:block;font-size:1.05rem;font-weight:900;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} .pj-g i{{display:block;font-style:normal;font-size:.66rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .pj-vazio{{text-align:center;padding:16px;border-radius:18px;border:1.5px dashed rgba(139,108,255,.55);color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
""".splitlines()) + "</style>"


# ------------------------------------------------------------------ serviço
def _ator():
    try:
        return usuarios.ator()
    except Exception:
        return None


def _nick_cadastro() -> str:
    try:
        import onboarding as O
        return O.normalizar(st.session_state.get("onb"))["nick"]
    except Exception:
        return ""


def uri_avatar(avatar: str) -> str:
    mod, chave = PF.AVATARES.get(avatar, PF.AVATARES[PF.AVATAR_PADRAO])
    try:
        return importlib.import_module(mod).uri(chave)
    except Exception:
        return ""


def meu_perfil() -> dict:
    """Perfil da conta logada (o mesmo documento, lido uma vez por sessão). Primeira vez: nasce do NickName, com a reserva do nome."""
    ss = st.session_state
    if isinstance(ss.get("_pj_doc"), dict):
        return ss["_pj_doc"]
    a = _ator()
    if not a:
        return PF.vazio()
    doc = PF.sanear(banco.perfil_jogador_ler(a))
    if not doc["usuario"]:
        novo = PF.inicial(_nick_cadastro())
        if novo["usuario"] and not banco.usuario_reservar(a, novo["usuario_k"]):
            novo.update(usuario="", usuario_k="")                      # nome já é de outra conta: a pessoa escolhe outro no formulário
        if novo["usuario"]:
            novo["atualizado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            banco.perfil_jogador_gravar(a, novo)
            doc = novo
    ss["_pj_doc"] = doc
    return doc


def salvar(form: dict) -> tuple[bool, str]:
    """Valida e grava o perfil da conta logada. Só campos editáveis entram; o nome novo é reservado antes de liberar o antigo."""
    a = _ator()
    if not a:
        return False, "Faça login."
    import prefs as PR
    atual = PF.sanear(banco.perfil_jogador_ler(a))
    try:
        novo, mud = PF.editar(atual, form, temas=PR.TEMAS)
    except PF.ErroPerfil as e:
        return False, str(e)
    try:
        if "usuario" in mud or (novo["usuario"] and not atual["usuario"]):
            if not banco.usuario_reservar(a, novo["usuario_k"]):
                return False, "Esse nome de usuário já está em uso. Escolha outro."
            if atual["usuario_k"] and atual["usuario_k"] != novo["usuario_k"]:
                banco.usuario_liberar(a, atual["usuario_k"])
            onb = st.session_state.get("onb")
            if isinstance(onb, dict):                                  # o NickName do cadastro acompanha (é o mesmo nome em todo o app)
                st.session_state["onb"] = {**onb, "nick": novo["usuario"]}
        banco.perfil_jogador_gravar(a, novo)
        if "tema" in mud:
            st.session_state["prefs"] = PR.normalizar({**PR.normalizar(st.session_state.get("prefs")), "tema": mud["tema"]})
        banco.auditar(a.id, "perfil_jogador.salvo", ",".join(sorted(k for k in form if k in PF.EDITAVEIS)))
    except Exception as e:
        banco.registrar_erro("perfis_app.salvar", e)
        return False, "Não consegui salvar agora. Tente de novo em instantes."
    st.session_state["_pj_doc"] = novo
    st.session_state.pop("_pj_pub", None)
    return True, "Perfil atualizado!"


def _ranking_de(email: str) -> tuple[dict | None, dict | None]:
    try:
        import jogos as J
        import jogos_app as JA
        linhas = JA.placares()
        return J.montar_ranking(J.TRADE, linhas, email), J.montar_ranking(J.TICKER, linhas, email)
    except Exception:
        return None, None


def perfil_publico(usuario: str) -> dict | None:
    """Perfil público de `usuario` montado das fontes reais (Jornada, placar dos jogos, data da conta). None se não existir ou for privado.
    Cache curto por nome. O e-mail da pessoa só circula aqui dentro e nunca entra no resultado."""
    try:
        k = PF.chave_usuario(PF.validar_usuario(usuario))
    except PF.ErroPerfil:
        return None
    cache = st.session_state.setdefault("_pj_pub", {})
    if k in cache and time.time() - cache[k][0] < _CACHE_PUB_S:
        return cache[k][1]
    pub = None
    try:
        achado = banco.sis_perfil_por_usuario(k)
        if achado:
            email, doc = achado
            conta = banco.sis_conta_por_email(email) or {}
            prog = PF.progresso((banco.sis_dados_de(email) or {}).get("edu_progresso"))
            rt, rk = _ranking_de(email)
            jg = PF.jogos(banco.sis_estado_ler(email, "jogos_placar"), rt, rk)
            pub = PF.publico(doc, conta.get("criado_em"), prog, jg)
    except Exception as e:
        banco.registrar_erro("perfis_app.publico", e)
    cache[k] = (time.time(), pub)
    return pub


def meu_perfil_completo() -> dict:
    """Visão privada da própria conta (para a tela dela): perfil + ID, e-mail, data de criação, nível, XP, conquistas, jogos e tema."""
    u = usuarios.usuario() or {}
    conta = (banco.sis_conta_por_id(u["id"]) if u.get("id") and not u["id"].startswith("legado:") else None) or {"id": u.get("id"), "email": u.get("email")}
    try:
        import educacao_app as EA
        prog = PF.progresso(EA.prog())
    except Exception:
        prog = PF.progresso({})
    rt, rk = _ranking_de(u.get("email", ""))
    try:
        jg = PF.jogos(banco.jogos_placar_ler(_ator()), rt, rk)
    except Exception:
        jg = None
    import prefs as PR
    return PF.privado(meu_perfil(), conta, prog, jg, PR.normalizar(st.session_state.get("prefs"))["tema"])


# ------------------------------------------------------------------ telas
def _cartao(p: dict, eu: bool = False) -> str:
    sub = f"@{p['usuario']}" if p.get("usuario") else "Escolha seu nome de usuário"
    desde = p.get("desde") or ""
    if len(desde) >= 7:
        desde = f"No TickerHunters desde {desde[5:7]}/{desde[:4]}"
    nivel = f" · Nível {p['nivel']} · {p['titulo']}" if p.get("nivel") else ""
    return (f"<div class='pj-card'><div class='pj-av'><img src='{uri_avatar(p.get('avatar', ''))}' alt=''></div><div class='pj-t'>"
            f"<b>{_e(p.get('nome') or p.get('usuario') or 'Jogador')}</b><span>{_e(sub)}{_e(nivel)}</span><small>{_e(desde)}</small></div></div>"
            + (f"<div class='pj-bio'>{_e(p['bio'])}</div>" if p.get("bio") else ""))


def _estatisticas(p: dict) -> str:
    itens = []
    if p.get("xp") is not None:
        itens.append(("XP", f"{p['xp']}", "de estudo"))
    c = p.get("conquistas")
    if isinstance(c, dict):
        itens.append(("Conquistas", f"{c['ok']}/{c['total']}", "de estudo"))
    elif p.get("conquistas_total"):
        itens.append(("Conquistas", f"{p['conquistas']}/{p['conquistas_total']}", "de estudo"))
    j = p.get("jogos") or {}
    if j.get("trade"):
        t = j["trade"]
        pts = f"{'+' if t['pontos'] > 0 else '−' if t['pontos'] < 0 else ''}{abs(t['pontos']):.1f}".replace(".", ",")
        itens.append(("Trade Battle", f"#{t['posicao']}" if t["posicao"] else "—", f"{pts} pts · {t['partidas']} partidas" if t["partidas"] else "sem partidas"))
    if j.get("ticker"):
        k = j["ticker"]
        n = k["vitorias"] + k["empates"] + k["derrotas"]
        itens.append(("Ticker Battle", f"#{k['posicao']}" if k["posicao"] else "—", f"{k['vitorias']}V · {k['empates']}E · {k['derrotas']}D" if n else "sem partidas"))
    return "<div class='pj-g'>" + "".join(f"<div><small>{_e(a)}</small><b>{_e(b)}</b><i>{_e(c_)}</i></div>" for a, b, c_ in itens) + "</div>" if itens else ""


def secao_editar() -> None:
    """Minha conta › Perfil: o perfil de jogador (público) e o formulário de edição da própria conta."""
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        p = meu_perfil_completo()
    except Exception as e:
        banco.registrar_erro("perfis_app.secao", e)
        st.markdown("<div class='pj-vazio'>Seu perfil de jogador não carregou agora. Tente de novo em instantes.</div>", unsafe_allow_html=True)
        return
    st.markdown("#### Perfil de jogador")
    st.caption("É assim que outras pessoas veem você nos rankings e nas ligas. Pontos, XP e conquistas vêm dos jogos e da Jornada e não são editáveis aqui.")
    st.markdown(_cartao(p, eu=True) + _estatisticas(p), unsafe_allow_html=True)
    msg = st.session_state.pop("_pj_msg", None)
    if msg:
        (st.success if msg[0] else st.error)(msg[1])
    import prefs as PR
    with st.form("f_perfil_jogador"):
        usuario = st.text_input("Nome de usuário (único)", value=p.get("usuario") or "", max_chars=20,
                                help=f"3 a 20 caracteres: letras, números, ponto, hífen ou sublinhado. Dá para trocar a cada {PF.TROCA_USUARIO_DIAS} dias.")
        nome = st.text_input("Nome de exibição", value=p.get("nome") or p.get("usuario") or "", max_chars=PF.NOME_MAX)
        bio = st.text_area("Biografia (opcional)", value=p.get("bio") or "", max_chars=PF.BIO_MAX, placeholder="Conte em uma frase o que você gosta de estudar ou jogar.")
        avs = list(PF.AVATARES)
        avatar = st.selectbox("Avatar", avs, index=avs.index(p.get("avatar")) if p.get("avatar") in avs else 0,
                              format_func=lambda a: a.replace("_", " ").capitalize())
        temas = list(PR.TEMAS)
        tema = st.selectbox("Preferência visual", temas, index=temas.index(p["tema"]) if p.get("tema") in temas else 0, format_func=lambda t: PR.TEMAS[t])
        st.markdown("**Privacidade**")
        pv = p.get("privacidade") or PF.PRIVACIDADE_PADRAO
        publico = st.toggle("Perfil público (outras pessoas podem abrir seu perfil)", value=pv["publico"])
        m_bio = st.toggle("Mostrar a biografia", value=pv["mostrar_bio"])
        m_nivel = st.toggle("Mostrar nível e XP", value=pv["mostrar_nivel"])
        m_conq = st.toggle("Mostrar conquistas", value=pv["mostrar_conquistas"])
        m_jogos = st.toggle("Mostrar desempenho nos jogos", value=pv["mostrar_jogos"])
        enviar = st.form_submit_button("Salvar perfil", type="primary", width="stretch")
    if enviar:
        ok, texto = salvar({"usuario": usuario, "nome": nome, "bio": bio, "avatar": avatar, "tema": tema,
                            "privacidade": {"publico": publico, "mostrar_bio": m_bio, "mostrar_nivel": m_nivel,
                                            "mostrar_conquistas": m_conq, "mostrar_jogos": m_jogos}})
        st.session_state["_pj_msg"] = (ok, texto)
        st.rerun()
    if p.get("usuario") and (p.get("privacidade") or {}).get("publico"):
        st.caption(f"Seu perfil público: /jogador?u={p['usuario']}")
    st.caption("Nunca aparecem no perfil público: e-mail, patrimônio, carteira, saldos de T$ ou Ticker Coins e o ID da conta.")


def pagina_publica() -> None:
    """Perfil público de um jogador (/jogador?u=<nome de usuário>). Só o que a pessoa permitiu; nada financeiro."""
    st.markdown(CSS, unsafe_allow_html=True)
    u = str(st.query_params.get("u") or "")
    p = perfil_publico(u) if u else None
    if not p:
        st.markdown("<div class='pj-vazio'>Perfil não encontrado ou privado.</div>", unsafe_allow_html=True)
        return
    st.markdown(_cartao(p) + _estatisticas(p), unsafe_allow_html=True)
