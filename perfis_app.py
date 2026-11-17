"""Perfil de jogador · serviço e telas (Streamlit). Regras e validação em `perfis.py`; imagem em `perfil_foto.py`; segurança no `banco`
(cada conta só lê e grava o próprio perfil e a própria foto).

Telas:
 · Meu Perfil (/perfil): avatar ou foto com a moldura da Loja, nomes, bio, nível e barra de XP, partidas, vitórias, derrotas, taxa de
   vitórias, conquistas e medalhas, desempenho e posição nos dois jogos, botões Editar Perfil, Privacidade e Configurações da conta.
 · Editar Perfil (/perfil-editar): foto (galeria com recorte e prévia, ou avatar do app), nome de exibição, nome de usuário, bio,
   moldura e tema da Loja (só itens que a conta possui), preferência visual e privacidade. Tudo em RASCUNHO: só "Salvar" grava;
   "Cancelar" descarta o rascunho e nada do que já estava salvo se perde.
 · Perfil público (/jogador?u=<nome>) e o cartão em Minha conta › Perfil.
Estatísticas competitivas vêm só do placar real dos jogos e da Jornada: nenhuma tela de edição recebe pontos, XP ou conquistas.
"""
from __future__ import annotations

import html
import importlib
import time
from datetime import datetime, timezone

import streamlit as st

import banco
import perfil_foto as FT
import perfis as PF
import usuarios

_e = html.escape
_P = "html body .stApp.stApp.stApp"
_CACHE_PUB_S = 60
VERDE, OURO, ROXO = "#34E85E", "#F2B84B", "#8B6CFF"

CSS = "<style>" + "".join(l.strip() for l in f"""
{_P} [data-testid='stMainBlockContainer'],{_P} .block-container{{max-width:720px !important}}
{_P} .pj-hero{{position:relative;text-align:center;padding:16px 12px 14px;border-radius:24px;border:2px solid {ROXO};
  background:radial-gradient(120% 70% at 50% 0,rgba(139,108,255,.38),transparent 65%),linear-gradient(170deg,#241A86,#0E0840);box-shadow:0 0 22px rgba(139,108,255,.45)}}
{_P} .pj-hero .mo,{_P} .pj-hero .pj-av{{margin:0 auto}}
{_P} .pj-av{{display:inline-block;width:104px;height:104px;border-radius:50%;overflow:hidden;background:#1B1545;box-shadow:0 0 0 3px {VERDE},0 0 18px rgba(52,232,94,.5)}}
{_P} .mo .pj-av{{box-shadow:none}}
{_P} .pj-av img{{width:100%;height:100%;object-fit:cover;display:block}}
{_P} .pj-nv{{position:absolute;top:12px;right:12px;padding:4px 10px;border-radius:999px;background:linear-gradient(160deg,#FFE08A,#E0A21A);font-weight:900;font-size:.78rem;color:#3A2400 !important;-webkit-text-fill-color:#3A2400 !important;box-shadow:0 0 12px rgba(255,201,60,.55)}}
{_P} .pj-nome{{margin-top:8px;font-size:1.35rem;font-weight:900;line-height:1.15;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .pj-user{{font-size:.86rem;font-weight:700;color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important}}
{_P} .pj-bio{{margin:8px auto 0;max-width:460px;white-space:pre-line;font-size:.86rem;line-height:1.4;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .pj-desde{{margin-top:6px;font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .pj-xp{{margin:10px 0 4px;padding:10px 12px;border-radius:18px;border:2px solid rgba(242,184,75,.6);background:linear-gradient(160deg,rgba(242,184,75,.14),rgba(14,8,64,.92))}}
{_P} .pj-xp .l{{display:flex;justify-content:space-between;font-size:.8rem;font-weight:800;color:#FFE3A3 !important;-webkit-text-fill-color:#FFE3A3 !important}}
{_P} .pj-xp .l span{{color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;font-weight:700}}
{_P} .pj-bar{{height:10px;margin-top:6px;border-radius:99px;background:rgba(255,255,255,.12);overflow:hidden}}
{_P} .pj-bar i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#F2B84B,#FFE08A);box-shadow:0 0 10px rgba(255,201,60,.6)}}
{_P} .pj-sec{{margin:14px 0 6px;font-weight:900;font-size:1rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .pj-sec small{{float:right;font-weight:700;font-size:.74rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .pj-g{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px}}
{_P} .pj-g div{{text-align:center;padding:9px 4px;border-radius:16px;border:1.5px solid rgba(139,108,255,.5);background:linear-gradient(160deg,#241A86,#150F55)}}
{_P} .pj-g small{{display:block;font-size:.66rem;font-weight:700;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .pj-g b{{display:block;font-size:1.2rem;font-weight:900;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .pj-g .ok b{{color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}{_P} .pj-g .no b{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
{_P} .pj-g .ou b{{color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} .pj-jg{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}}
{_P} .pj-jg > div{{padding:10px 12px;border-radius:18px;border:2px solid var(--c);background:linear-gradient(160deg,var(--f),#0E0840 80%);box-shadow:0 0 14px color-mix(in srgb,var(--c) 45%,transparent)}}
{_P} .pj-jg .t{{display:flex;justify-content:space-between;align-items:center;font-weight:900;font-size:.9rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .pj-jg .t em{{font-style:normal;padding:1px 8px;border-radius:999px;background:var(--c);font-size:.78rem;color:#0B0830 !important;-webkit-text-fill-color:#0B0830 !important}}
{_P} .pj-jg p{{margin:6px 0 0;display:flex;justify-content:space-between;font-size:.78rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .pj-jg p b{{color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .pj-md{{display:grid;grid-template-columns:repeat(auto-fill,minmax(76px,1fr));gap:6px}}
{_P} .pj-md div{{text-align:center;padding:8px 4px;border-radius:16px;border:1.5px solid rgba(139,108,255,.35);background:rgba(20,14,70,.7);opacity:.45;filter:grayscale(.9)}}
{_P} .pj-md div.ok{{opacity:1;filter:none;border-color:{OURO};background:linear-gradient(160deg,rgba(242,184,75,.22),rgba(20,14,70,.9));box-shadow:0 0 12px rgba(242,184,75,.35)}}
{_P} .pj-md i{{display:block;font-style:normal;font-size:1.5rem}}
{_P} .pj-md span{{display:block;margin-top:2px;font-size:.62rem;line-height:1.2;font-weight:700;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .pj-vazio{{text-align:center;padding:14px;border-radius:18px;border:1.5px dashed rgba(139,108,255,.55);font-size:.86rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .pj-cab{{display:flex;align-items:center;gap:10px;margin:0 0 8px;font-weight:900;font-style:italic;font-size:1.3rem;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} .pj-prev{{text-align:center;margin:6px 0}}
{_P} .pj-prev small{{display:block;margin-top:4px;font-size:.74rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .st-key-pe_av{{display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr)) !important;gap:8px !important}}
{_P} .st-key-pe_av > div{{width:auto !important;min-width:0 !important}}
{_P} [class*="st-key-pe_avc_"]{{gap:4px !important;padding:6px 4px;border-radius:16px;background:rgba(20,14,70,.6);border:1.5px solid rgba(139,108,255,.35)}}
{_P} [class*="st-key-pe_avc_"] button{{min-height:32px !important;padding:2px 6px !important}}
@media (min-width:600px){{{_P} .st-key-pe_av{{grid-template-columns:repeat(6,minmax(0,1fr)) !important}}}}
{_P} :is(.st-key-pj_editar,.st-key-pe_salvar) button{{min-height:48px !important;border:0 !important;border-radius:16px !important;font-weight:900 !important;
  background:linear-gradient(90deg,#2EE86B,#14C9B5) !important;box-shadow:0 0 16px rgba(46,232,107,.45) !important}}
{_P} :is(.st-key-pj_editar,.st-key-pe_salvar) button :is(p,span){{color:#06240F !important;-webkit-text-fill-color:#06240F !important}}
@media (max-width:420px){{{_P} .pj-g{{grid-template-columns:repeat(2,minmax(0,1fr))}}{_P} .pj-jg{{grid-template-columns:1fr}}}}
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


def uri_avatar(avatar: str, foto_uri: str = "") -> str:
    if avatar == PF.FOTO and foto_uri:
        return foto_uri
    mod, chave = PF.AVATARES.get(avatar, PF.AVATARES[PF.AVATAR_PADRAO])
    try:
        return importlib.import_module(mod).uri(chave)
    except Exception:
        return ""


def meu_perfil() -> dict:
    """Perfil da conta logada (lido uma vez por sessão). Primeira vez: nasce do NickName do cadastro, com a reserva do nome."""
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
            novo.update(usuario="", usuario_k="")                      # nome já é de outra conta: a pessoa escolhe outro em Editar Perfil
        if novo["usuario"]:
            novo["atualizado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
            banco.perfil_jogador_gravar(a, novo)
            doc = novo
    ss["_pj_doc"] = doc
    return doc


def minha_foto_uri() -> str:
    ss = st.session_state
    if "_pj_foto" not in ss:
        a = _ator()
        try:
            ss["_pj_foto"] = FT.uri(banco.perfil_foto_ler(a)) if a else ""
        except Exception:
            ss["_pj_foto"] = ""
    return ss["_pj_foto"]


def salvar(form: dict, foto_webp: bytes | None = None, remover_foto: bool = False) -> tuple[bool, str]:
    """Valida e grava o perfil da conta logada (e a foto nova, se houver). Só campos editáveis entram; o nome novo é reservado antes de
    liberar o antigo; a foto já chega reprocessada. Em qualquer falha nada fica pela metade do lado do perfil."""
    a = _ator()
    if not a:
        return False, "Faça login."
    import prefs as PR
    atual = PF.sanear(banco.perfil_jogador_ler(a))
    form = dict(form)
    if form.get("avatar") == PF.FOTO and not foto_webp and (remover_foto or not minha_foto_uri()):
        form["avatar"] = PF.AVATAR_PADRAO                              # escolheu foto mas não há foto: volta ao avatar padrão
    try:
        novo, mud = PF.editar(atual, form, temas=PR.TEMAS)
        foto_doc = FT.documento(foto_webp, datetime.now(timezone.utc).isoformat(timespec="seconds")) if foto_webp else None
    except (PF.ErroPerfil, FT.ErroFoto) as e:
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
        if foto_doc:
            banco.perfil_foto_gravar(a, foto_doc)
            novo["avatar"] = PF.FOTO
        elif remover_foto:
            banco.perfil_foto_apagar(a)
            if novo["avatar"] == PF.FOTO:
                novo["avatar"] = PF.AVATAR_PADRAO
        banco.perfil_jogador_gravar(a, novo)
        if "tema" in mud:
            st.session_state["prefs"] = PR.normalizar({**PR.normalizar(st.session_state.get("prefs")), "tema": mud["tema"]})
        banco.auditar(a.id, "perfil_jogador.salvo", ",".join(sorted(k for k in form if k in PF.EDITAVEIS)) + (",foto" if foto_doc else ""))
    except Exception as e:
        banco.registrar_erro("perfis_app.salvar", e)
        return False, "Não consegui salvar agora. Tente de novo em instantes."
    st.session_state["_pj_doc"] = novo
    for k in ("_pj_pub", "_pj_foto"):
        st.session_state.pop(k, None)
    return True, "Perfil atualizado!"


def itens_loja(tipo: str) -> tuple[list[tuple[str, str]], str | None]:
    """Itens de `tipo` (moldura ou tema) que a conta POSSUI na Loja Ticker e o equipado agora. Nada é vendido aqui."""
    u = usuarios.usuario() or {}
    try:
        import tickercoins as TC
        donos = {c["produto_id"] for c in TC.beneficios_ativos(u["id"])}
        itens = [(p["id"], p["nome"]) for p in TC._POR_ID.values() if p["efeito"].get("kind") == tipo and p["id"] in donos]
        return itens, TC.equipado(u["email"]).get(tipo)
    except Exception:
        return [], None


def equipar(tipo: str, pid: str | None) -> tuple[bool, str]:
    """Equipa a moldura/tema com o mesmo serviço da Loja (só aceita item que a conta possui)."""
    u = usuarios.usuario() or {}
    try:
        import loja_aparencia as LA
        import tickercoins as TC
        TC.equipar(u["id"], u["email"], pid, tipo)
        LA.invalidar()
        return True, ""
    except Exception as e:
        return False, str(e) or "Não foi possível aplicar o item agora."


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
            foto = FT.uri(banco.sis_estado_ler(email, "perfil_foto")) if PF.sanear(doc)["avatar"] == PF.FOTO else ""
            pub = PF.publico(doc, conta.get("criado_em"), prog, jg, foto)
    except Exception as e:
        banco.registrar_erro("perfis_app.publico", e)
    cache[k] = (time.time(), pub)
    return pub


def _dados_meus() -> dict:
    """Tudo o que a tela Meu Perfil mostra, das fontes reais (sem gravar nada)."""
    import jogos as J
    import nivel as NV
    import prefs as PR
    u = usuarios.usuario() or {}
    conta = (banco.sis_conta_por_id(u["id"]) if u.get("id") and not u["id"].startswith("legado:") else None) or {"id": u.get("id"), "email": u.get("email")}
    try:
        import educacao_app as EA
        prog = PF.progresso(EA.prog())
    except Exception:
        prog = PF.progresso({})
    rt, rk = _ranking_de(u.get("email", ""))
    try:
        placar = banco.jogos_placar_ler(_ator())
    except Exception:
        placar = {}
    medalhas = []
    try:
        import emblemas as EM
        import emblemas_app as EMA
        import perfil_app as PA
        res, cart = PA._wallet()
        for cat in EM.colecao(EMA.contexto_da_tela(res, cart)):
            medalhas += cat["itens"]
    except Exception:
        pass
    priv = PF.privado(meu_perfil(), conta, prog, PF.jogos(placar, rt, rk), PR.normalizar(st.session_state.get("prefs"))["tema"])
    return {**priv, "est": J.estatisticas(placar), "nivel_est": NV.estado(prog["xp"]), "medalhas": medalhas, "placar": J.sanear(placar)}


# ------------------------------------------------------------------ peças visuais
def _moldura() -> dict | None:
    try:
        import loja_aparencia as LA
        return LA.efeito("moldura")
    except Exception:
        return None


def _avatar_html(avatar: str, foto: str, moldura: dict | None = None) -> str:
    import visual_loja as VL
    av = f"<div class='pj-av'><img src='{uri_avatar(avatar, foto)}' alt='Foto de perfil'></div>"
    return VL.CSS_MOLDURA + VL.html_moldura(av, moldura) if moldura else av


def _fmt_pts(v: float) -> str:
    return f"{'+' if v > 0 else '−' if v < 0 else ''}{abs(v):.1f}".replace(".", ",")


def _ir(url: str, **estado) -> None:
    for k, v in estado.items():
        st.session_state[k] = v
    st.session_state["_nav_pend"] = url


def _msg() -> None:
    m = st.session_state.pop("_pj_msg", None)
    if m:
        (st.success if m[0] else st.error)(m[1], icon=":material/check_circle:" if m[0] else ":material/error:")


# ------------------------------------------------------------------ TELA · Meu Perfil
def pagina_meu_perfil() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if not _ator():
        return
    _msg()
    try:
        d = _dados_meus()
    except Exception as e:
        banco.registrar_erro("perfis_app.meu_perfil", e)
        st.markdown("<div class='pj-vazio'>Seu perfil não carregou agora. Tente de novo em instantes.</div>", unsafe_allow_html=True)
        return
    desde = d.get("desde") or ""
    desde = f"No TickerHunters desde {desde[8:10]}/{desde[5:7]}/{desde[:4]}" if len(desde) >= 10 else ""
    st.markdown(
        f"<div class='pj-hero'><span class='pj-nv'>Nível {d['nivel']}</span>{_avatar_html(d['avatar'], minha_foto_uri(), _moldura())}"
        f"<div class='pj-nome'>{_e(d.get('nome') or d.get('usuario') or 'Jogador')}</div>"
        f"<div class='pj-user'>{'@' + _e(d['usuario']) if d.get('usuario') else 'Escolha seu nome de usuário em Editar Perfil'} · {_e(d['titulo'])}</div>"
        + (f"<div class='pj-bio'>{_e(d['bio'])}</div>" if d.get("bio") else "")
        + f"<div class='pj-desde'>{_e(desde)}</div></div>", unsafe_allow_html=True)
    ne = d["nivel_est"]
    falta = "Nível máximo!" if ne["maximo"] else f"faltam {ne['falta']} XP para o nível {ne['nivel'] + 1}"
    st.markdown(f"<div class='pj-xp'><div class='l'>⭐ {d['xp']} XP<span>{_e(falta)}</span></div><div class='pj-bar'><i style='width:{ne['pct'] * 100:.0f}%'></i></div></div>",
                unsafe_allow_html=True)
    c1, c2 = st.columns([1.4, 1])
    c1.button("Editar perfil", key="pj_editar", icon=":material/edit:", width="stretch", on_click=_ir, args=("perfil-editar",), kwargs={"pe_novo": True, "pe_foco": None})
    c2.button("Privacidade", key="pj_priv", icon=":material/lock:", width="stretch", on_click=_ir, args=("perfil-editar",), kwargs={"pe_novo": True, "pe_foco": "privacidade"})
    es = d["est"]
    taxa = f"{es['taxa']:.0f}%".replace(".", ",") if es["taxa"] is not None else "—"
    st.markdown("<div class='pj-sec'>📊 Desempenho<small>só partidas terminadas</small></div><div class='pj-g'>"
                f"<div><small>Partidas</small><b>{es['partidas']}</b></div><div class='ok'><small>Vitórias</small><b>{es['vitorias']}</b></div>"
                f"<div class='no'><small>Derrotas</small><b>{es['derrotas']}</b></div><div class='ou'><small>Taxa de vitórias</small><b>{taxa}</b></div></div>",
                unsafe_allow_html=True)
    t, k = d["jogos"]["trade"], d["jogos"]["ticker"]
    pos = lambda x: f"#{x}" if x else "—"
    st.markdown("<div class='pj-sec'>🎮 Jogos e rankings</div><div class='pj-jg'>"
                f"<div style='--c:{VERDE};--f:rgba(20,110,80,.6)'><div class='t'>Trade Battle<em>{pos(t['posicao'])}</em></div>"
                f"<p>Pontos<b>{_fmt_pts(t['pontos'])}</b></p><p>Partidas<b>{t['partidas']}</b></p><p>1º lugar em sala<b>{t['vitorias']}</b></p>"
                f"<p>Melhor partida<b>{_fmt_pts(d['placar']['trade']['melhor']) if d['placar']['trade']['melhor'] is not None else '—'}</b></p></div>"
                f"<div style='--c:{ROXO};--f:rgba(110,70,230,.55)'><div class='t'>Ticker Battle<em>{pos(k['posicao'])}</em></div>"
                f"<p>Vitórias<b>{k['vitorias']}</b></p><p>Empates<b>{k['empates']}</b></p><p>Derrotas<b>{k['derrotas']}</b></p>"
                f"<p>Duelos<b>{k['vitorias'] + k['empates'] + k['derrotas']}</b></p></div></div>", unsafe_allow_html=True)
    md = sorted(d["medalhas"], key=lambda m: not m.get("ok"))
    ok = sum(1 for m in md if m.get("ok"))
    if md:
        st.markdown(f"<div class='pj-sec'>🏅 Conquistas e medalhas<small>{ok} de {len(md)}</small></div><div class='pj-md'>"
                    + "".join(f"<div class='{'ok' if m.get('ok') else ''}' title='{_e(m.get('descricao', ''))}'><i>{_e(m.get('emblema', '🏅'))}</i><span>{_e(m.get('nome', ''))}</span></div>"
                              for m in md[:12]) + "</div>", unsafe_allow_html=True)
    st.button("Configurações da conta", key="pj_conta", icon=":material/settings:", width="stretch", on_click=_ir, args=("conta",))
    st.caption("Pontos, vitórias, XP e conquistas vêm dos jogos e da Jornada e não podem ser editados.")


# ------------------------------------------------------------------ TELA · Editar Perfil (rascunho até salvar)
_CAMPOS = ("pe_nome", "pe_usuario", "pe_bio", "pe_avatar", "pe_tema", "pe_moldura", "pe_tema_loja", "pe_pub", "pe_mbio", "pe_mnivel", "pe_mconq", "pe_mjogos",
           "pe_foto", "pe_remover", "pe_zoom", "pe_x", "pe_y", "pe_up", "pe_foco")


def _iniciar_rascunho() -> None:
    """Copia o perfil salvo para os campos do rascunho (ao entrar na tela). Nada é gravado até 'Salvar'."""
    import prefs as PR
    ss = st.session_state
    for k in _CAMPOS:
        if k != "pe_foco":
            ss.pop(k, None)
    p, pv = meu_perfil(), meu_perfil()["privacidade"]
    ss.update(pe_nome=p["nome"] or p["usuario"], pe_usuario=p["usuario"], pe_bio=p["bio"], pe_avatar=p["avatar"],
              pe_tema=PR.normalizar(ss.get("prefs"))["tema"], pe_pub=pv["publico"], pe_mbio=pv["mostrar_bio"], pe_mnivel=pv["mostrar_nivel"],
              pe_mconq=pv["mostrar_conquistas"], pe_mjogos=pv["mostrar_jogos"], pe_zoom=1.0, pe_x=0.0, pe_y=0.0)
    ss["pe_moldura"] = itens_loja("moldura")[1] or ""
    ss["pe_tema_loja"] = itens_loja("tema")[1] or ""


def _cancelar() -> None:
    for k in _CAMPOS:
        st.session_state.pop(k, None)
    st.session_state["_pj_msg"] = (True, "Edição cancelada. Nada foi alterado.")
    st.session_state["_nav_pend"] = "perfil"


def _escolher_avatar(a: str) -> None:
    ss = st.session_state
    ss["pe_avatar"] = a
    ss.pop("pe_foto", None)
    ss["pe_remover"] = False


def _usar_foto() -> None:
    """Processa a foto enviada com o recorte escolhido e guarda no rascunho (ainda não grava)."""
    ss = st.session_state
    arq = ss.get("pe_up")
    try:
        if arq is None:
            raise FT.ErroFoto("Escolha uma imagem da galeria primeiro.")
        ss["pe_foto"] = FT.processar(arq.getvalue(), ss.get("pe_zoom", 1.0), ss.get("pe_x", 0.0), ss.get("pe_y", 0.0))
        ss["pe_avatar"], ss["pe_remover"] = PF.FOTO, False
        ss["_pe_aviso"] = (True, "Foto pronta! Toque em Salvar para usar no seu perfil.")
    except FT.ErroFoto as e:
        ss["_pe_aviso"] = (False, str(e))
    except Exception as e:
        banco.registrar_erro("perfis_app.usar_foto", e)
        ss["_pe_aviso"] = (False, "Não consegui processar essa imagem. Tente outra foto.")


def _remover_foto() -> None:
    ss = st.session_state
    ss.pop("pe_foto", None)
    ss["pe_remover"], ss["pe_avatar"] = True, PF.AVATAR_PADRAO


def _salvar_edicao() -> None:
    ss = st.session_state
    form = {"nome": ss.get("pe_nome", ""), "usuario": ss.get("pe_usuario", ""), "bio": ss.get("pe_bio", ""), "avatar": ss.get("pe_avatar", PF.AVATAR_PADRAO),
            "tema": ss.get("pe_tema"), "privacidade": {"publico": bool(ss.get("pe_pub")), "mostrar_bio": bool(ss.get("pe_mbio")),
                                                        "mostrar_nivel": bool(ss.get("pe_mnivel")), "mostrar_conquistas": bool(ss.get("pe_mconq")),
                                                        "mostrar_jogos": bool(ss.get("pe_mjogos"))}}
    ok, msg = salvar(form, ss.get("pe_foto"), bool(ss.get("pe_remover")))
    if not ok:
        ss["_pe_aviso"] = (False, msg)
        return
    erros = []
    for tipo, chave in (("moldura", "pe_moldura"), ("tema", "pe_tema_loja")):
        atual = itens_loja(tipo)[1] or ""
        if (ss.get(chave) or "") != atual:
            ok_i, msg_i = equipar(tipo, ss.get(chave) or None)
            if not ok_i:
                erros.append(msg_i)
    for k in _CAMPOS:
        ss.pop(k, None)
    ss["_pj_msg"] = (not erros, "Perfil atualizado!" if not erros else "Perfil salvo, mas a moldura/tema não foi aplicado: " + "; ".join(erros))
    ss["_nav_pend"] = "perfil"


def pagina_editar() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    ss = st.session_state
    if not _ator():
        return
    if ss.pop("pe_novo", False) or "pe_nome" not in ss:
        foco = ss.get("pe_foco")
        _iniciar_rascunho()
        if foco:
            ss["pe_foco"] = foco
    st.markdown("<div class='pj-cab'>✏️ Editar Perfil</div>", unsafe_allow_html=True)
    av = ss.pop("_pe_aviso", None)
    if av:
        (st.success if av[0] else st.error)(av[1], icon=":material/check_circle:" if av[0] else ":material/error:")
    import prefs as PR
    # ---- foto ou avatar
    foto_atual = "" if ss.get("pe_remover") else minha_foto_uri()
    if ss.get("pe_foto"):
        import base64
        foto_prev = "data:image/webp;base64," + base64.b64encode(ss["pe_foto"]).decode()
    else:
        foto_prev = foto_atual
    st.markdown("<div class='pj-sec'>📷 Foto de perfil</div><div class='pj-prev'>" + _avatar_html(ss.get("pe_avatar", PF.AVATAR_PADRAO), foto_prev)
                + f"<small>{'Prévia: ainda não foi salvo.' if ss.get('pe_foto') or ss.get('pe_remover') else 'Como está agora.'}</small></div>",
                unsafe_allow_html=True)
    aba = st.segmented_control("Origem da foto", ["Avatares do app", "Enviar da galeria"], default="Avatares do app", key="pe_aba", label_visibility="collapsed")
    if aba == "Enviar da galeria":
        st.file_uploader(f"Foto (JPG, PNG ou WebP, até {FT.TAM_MAX_MB} MB)", type=["jpg", "jpeg", "png", "webp"], key="pe_up")
        if ss.get("pe_up") is not None:
            try:
                prev = FT.processar(ss["pe_up"].getvalue(), ss.get("pe_zoom", 1.0), ss.get("pe_x", 0.0), ss.get("pe_y", 0.0), FT.LADO_PREVIA)
                import base64
                st.markdown(f"<div class='pj-prev'><div class='pj-av'><img src='data:image/webp;base64,{base64.b64encode(prev).decode()}' alt='Recorte'></div>"
                            "<small>Ajuste o recorte abaixo.</small></div>", unsafe_allow_html=True)
                st.slider("Zoom", 1.0, FT.ZOOM_MAX, step=0.1, key="pe_zoom")
                st.slider("Posição horizontal", -1.0, 1.0, step=0.05, key="pe_x")
                st.slider("Posição vertical", -1.0, 1.0, step=0.05, key="pe_y")
                st.button("Usar esta foto", key="pe_usar", icon=":material/check:", width="stretch", on_click=_usar_foto)
            except FT.ErroFoto as e:
                st.error(str(e), icon=":material/error:")
    else:
        with st.container(key="pe_av"):
            for a in PF.AVATARES:
                with st.container(key=f"pe_avc_{a}"):
                    st.markdown(f"<div class='pj-prev'><div class='pj-av' style='width:52px;height:52px{';box-shadow:0 0 0 3px ' + OURO + ',0 0 14px ' + OURO if ss.get('pe_avatar') == a else ''}'>"
                                f"<img src='{uri_avatar(a)}' alt=''></div></div>", unsafe_allow_html=True)
                    st.button("✓" if ss.get("pe_avatar") == a else "Usar", key=f"pe_av_{a}", width="stretch", on_click=_escolher_avatar, args=(a,))
    if foto_atual or ss.get("pe_foto"):
        st.button("Remover foto", key="pe_rem", icon=":material/delete:", on_click=_remover_foto)
    # ---- dados
    st.markdown("<div class='pj-sec'>👤 Seus dados</div>", unsafe_allow_html=True)
    st.text_input("Nome de exibição", key="pe_nome", max_chars=PF.NOME_MAX)
    st.text_input("Nome de usuário (único)", key="pe_usuario", max_chars=20,
                  help=f"3 a 20 caracteres: letras, números, ponto, hífen ou sublinhado. Dá para trocar a cada {PF.TROCA_USUARIO_DIAS} dias.")
    st.text_area("Biografia (opcional)", key="pe_bio", max_chars=PF.BIO_MAX, placeholder="Conte em uma frase o que você gosta de estudar ou jogar.")
    # ---- aparência
    st.markdown("<div class='pj-sec'>🎨 Aparência</div>", unsafe_allow_html=True)
    molds, _ = itens_loja("moldura")
    temas_loja, _ = itens_loja("tema")
    if molds:
        op = [""] + [i for i, _ in molds]
        nomes = dict(molds)
        st.selectbox("Moldura do avatar", op, key="pe_moldura", format_func=lambda i: nomes.get(i, "Sem moldura"))
    if temas_loja:
        op = [""] + [i for i, _ in temas_loja]
        nomes_t = dict(temas_loja)
        st.selectbox("Tema do app (Loja Ticker)", op, key="pe_tema_loja", format_func=lambda i: nomes_t.get(i, "Tema padrão"))
    if not molds and not temas_loja:
        st.caption("Molduras e temas aparecem aqui quando você desbloqueia na Loja Ticker.")
    st.selectbox("Preferência visual", list(PR.TEMAS), key="pe_tema", format_func=lambda t: PR.TEMAS[t])
    # ---- privacidade
    with st.expander("🔒 Privacidade", expanded=ss.get("pe_foco") == "privacidade"):
        st.toggle("Perfil público (outras pessoas podem abrir seu perfil)", key="pe_pub")
        st.toggle("Mostrar a biografia", key="pe_mbio")
        st.toggle("Mostrar nível e XP", key="pe_mnivel")
        st.toggle("Mostrar conquistas", key="pe_mconq")
        st.toggle("Mostrar desempenho nos jogos", key="pe_mjogos")
        st.caption("Nunca aparecem para outras pessoas: e-mail, patrimônio, carteira, saldos de T$ ou Ticker Coins e o ID da conta.")
    c1, c2 = st.columns([1.4, 1])
    c1.button("Salvar", key="pe_salvar", icon=":material/save:", width="stretch", on_click=_salvar_edicao)
    c2.button("Cancelar", key="pe_cancelar", icon=":material/close:", width="stretch", on_click=_cancelar)


# ------------------------------------------------------------------ Minha conta › Perfil (atalho) e perfil público
def secao_conta() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    try:
        p = meu_perfil()
    except Exception:
        return
    st.markdown("#### Perfil de jogador")
    st.markdown(f"<div class='pj-prev'>{_avatar_html(p['avatar'], minha_foto_uri(), _moldura())}<small>{_e(p.get('nome') or '')} · @{_e(p.get('usuario') or '—')}</small></div>",
                unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.button("Ver meu perfil", key="ct_pj_ver", icon=":material/person:", width="stretch", on_click=_ir, args=("perfil",))
    c2.button("Editar perfil", key="ct_pj_edit", icon=":material/edit:", width="stretch", on_click=_ir, args=("perfil-editar",), kwargs={"pe_novo": True, "pe_foco": None})


def pagina_publica() -> None:
    """Perfil público de um jogador (/jogador?u=<nome de usuário>). Só o que a pessoa permitiu; nada financeiro."""
    st.markdown(CSS, unsafe_allow_html=True)
    u = str(st.query_params.get("u") or "")
    p = perfil_publico(u) if u else None
    if not p:
        st.markdown("<div class='pj-vazio'>Perfil não encontrado ou privado.</div>", unsafe_allow_html=True)
        return
    desde = p.get("desde") or ""
    nivel = f" · Nível {p['nivel']} · {p['titulo']}" if p.get("nivel") else ""
    st.markdown(f"<div class='pj-hero'>{_avatar_html(p['avatar'], p.get('foto', ''))}<div class='pj-nome'>{_e(p['nome'])}</div>"
                f"<div class='pj-user'>@{_e(p['usuario'])}{_e(nivel)}</div>" + (f"<div class='pj-bio'>{_e(p['bio'])}</div>" if p.get("bio") else "")
                + (f"<div class='pj-desde'>No TickerHunters desde {desde[5:7]}/{desde[:4]}</div>" if len(desde) >= 7 else "") + "</div>", unsafe_allow_html=True)
    itens = []
    if isinstance(p.get("conquistas"), dict):
        itens.append(f"<div class='ou'><small>Conquistas</small><b>{p['conquistas']['ok']}/{p['conquistas']['total']}</b></div>")
    j = p.get("jogos") or {}
    if j.get("trade"):
        itens.append(f"<div><small>Trade Battle</small><b>{'#' + str(j['trade']['posicao']) if j['trade']['posicao'] else '—'}</b></div>")
    if j.get("ticker"):
        itens.append(f"<div><small>Ticker Battle</small><b>{'#' + str(j['ticker']['posicao']) if j['ticker']['posicao'] else '—'}</b></div>")
    if p.get("xp") is not None:
        itens.append(f"<div class='ok'><small>XP</small><b>{p['xp']}</b></div>")
    if itens:
        st.markdown("<div class='pj-g'>" + "".join(itens) + "</div>", unsafe_allow_html=True)
