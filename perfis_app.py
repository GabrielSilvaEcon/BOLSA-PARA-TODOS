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
{_P} .pj-rar{{margin-top:6px;display:flex;gap:6px;justify-content:center;align-items:center;font-size:.76rem;font-weight:700;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .pj-col-h{{display:flex;flex-wrap:wrap;gap:6px 10px;align-items:center;margin:4px 0 8px;font-size:.78rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .pj-col-h b{{color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .st-key-pe_col{{display:grid !important;grid-template-columns:repeat(auto-fill,minmax(96px,1fr));gap:8px !important}}
{_P} .st-key-pe_col > div{{width:auto !important;min-width:0}}
{_P} .pe-t{{position:relative;text-align:center;padding:9px 4px 8px;border-radius:16px;background:rgba(20,14,70,.75);border:1.5px solid rgba(139,108,255,.3);min-height:126px}}
{_P} .pe-t.eq{{border-color:#34E85E;box-shadow:0 0 14px rgba(52,232,94,.45)}}
{_P} .pe-t.ver{{border-color:#FFC93C}}
{_P} .pe-t .n{{display:block;margin-top:6px;font-size:.7rem;font-weight:800;line-height:1.15;color:#fff !important;-webkit-text-fill-color:#fff !important;
  overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
{_P} .pe-t .thrar{{margin-top:3px;font-size:.56rem}}
{_P} .pe-t.bloq .thav{{filter:grayscale(.85) brightness(.45)}}
{_P} .pe-t .cad{{position:absolute;top:30px;left:50%;transform:translateX(-50%);font-size:1.25rem}}
{_P} .pe-t .lv{{display:block;margin-top:2px;font-size:.6rem;font-weight:700;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .pe-t .eqk{{position:absolute;top:5px;right:6px;font-size:.62rem;font-weight:900;color:#34E85E !important;-webkit-text-fill-color:#34E85E !important}}
{_P} .pe-prevc{{display:flex;gap:14px;align-items:center;padding:12px;border-radius:18px;border:1.5px solid rgba(139,108,255,.5);background:linear-gradient(160deg,#241A86,#120C4A);margin:6px 0 8px}}
{_P} .pe-prevc .t{{min-width:0}}
{_P} .pe-prevc b{{display:block;font-size:1.02rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .pe-prevc small{{display:block;margin-top:3px;font-size:.78rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
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
{_P} .pj-rel{{display:flex;align-items:center;justify-content:center;min-height:42px;padding:6px 10px;border-radius:16px;border:1.5px solid {VERDE};
  font-weight:800;font-size:.86rem;color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important;background:rgba(52,232,94,.1);text-align:center}}
{_P} .pj-hl{{display:flex;flex-direction:column;gap:5px}}
{_P} .pj-h{{display:flex;justify-content:space-between;align-items:center;padding:7px 12px;border-radius:14px;background:rgba(20,14,70,.75);border:1.5px solid rgba(139,108,255,.35)}}
{_P} .pj-h span{{font-weight:800;font-size:.84rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .pj-h small{{margin-left:6px;font-weight:600;font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .pj-h b{{font-size:.84rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .pj-h b.ok{{color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}{_P} .pj-h b.no{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
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


def avatar_html(avatar: str, foto: str = "", tamanho: int = 48) -> str:
    """Avatar com a moldura da raridade (ou da foto). Use em qualquer lugar: listas, rankings, salas, perfis."""
    import avatares as AV
    return AV.html(None if avatar == PF.FOTO and foto else avatar, tamanho, foto if avatar == PF.FOTO else "")


def meu_avatar() -> dict:
    """Avatar equipado da conta logada: {id, foto, src, src_p, rar}. Usado no cabeçalho e nas telas de jogo."""
    import avatares as AV
    try:
        p = meu_perfil()
        av, foto = p.get("avatar") or PF.AVATAR_PADRAO, minha_foto_uri() if p.get("avatar") == PF.FOTO else ""
    except Exception:
        av, foto = PF.AVATAR_PADRAO, ""
    if av == PF.FOTO and foto:
        return {"id": av, "foto": foto, "src": foto, "src_p": foto, "rar": "foto"}
    av = av if AV.existe(av) else PF.AVATAR_PADRAO
    return {"id": av, "foto": "", "src": AV.url(av), "src_p": AV.url(av, True), "rar": AV.raridade_de(av)}


def avatar_de_email(email: str) -> tuple[str, str]:
    """(avatar equipado, foto) de outra conta, lidos no servidor com cache de 5 min na sessão. O e-mail nunca vai para a tela."""
    if not email:
        return PF.AVATAR_PADRAO, ""
    a = _ator()
    if a and a.email == email:
        m = meu_avatar()
        return m["id"], m["foto"]
    cache = st.session_state.setdefault("_pj_avs", {})
    if email in cache and time.time() - cache[email][0] < 300:
        return cache[email][1]
    av, foto = PF.AVATAR_PADRAO, ""
    try:
        p = PF.sanear(banco.sis_estado_ler(email, "perfil_jogador"))
        av = p["avatar"]
        if av == PF.FOTO:
            foto = FT.uri(banco.sis_estado_ler(email, "perfil_foto"))
            av = PF.FOTO if foto else PF.AVATAR_PADRAO
    except Exception:
        pass
    cache[email] = (time.time(), (av, foto))
    return av, foto


def avatar_html_email(email: str, tamanho: int = 40) -> str:
    av, foto = avatar_de_email(email)
    return avatar_html(av, foto, tamanho)


def _ctx_colecao() -> dict:
    """Nível real (Jornada) e conquistas reais da conta, para a regra de desbloqueio. Nada vem da tela."""
    ctx = {"nivel": 1, "emblemas": set()}
    try:
        import educacao_app as EA
        ctx["nivel"] = PF.progresso(EA.prog())["nivel"]
    except Exception:
        pass
    try:
        import emblemas as EM
        import emblemas_app as EMA
        import perfil_app as PA
        ctx["emblemas"] = {i["id"] for c in EM.colecao(EMA.contexto_da_tela(*PA._wallet())) for i in c["itens"] if i["ok"]}
    except Exception:
        pass
    return ctx


def minha_colecao() -> set[str]:
    """Avatares liberados para a conta logada. Guarda na coleção (banco) o que acabou de liberar. Cache de 60 s na sessão."""
    import avatares as AV
    ss = st.session_state
    c = ss.get("_pj_col")
    if c and time.time() - c[0] < 60:
        return c[1]
    a = _ator()
    lib = AV.liberados({"nivel": 1})
    if a:
        try:
            ctx = _ctx_colecao()
            doc, novos = AV.sincronizar(banco.avatares_colecao_ler(a), ctx, datetime.now(timezone.utc).date().isoformat())
            if novos:
                banco.avatares_colecao_gravar(a, doc)
            lib = AV.liberados({**ctx, "concedidos": doc["concedidos"]}, doc["ids"])
        except Exception as e:
            banco.registrar_erro("perfis_app.minha_colecao", e)
    ss["_pj_col"] = (time.time(), lib)
    return lib


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


def garantir_perfil() -> None:
    """Ao entrar no app: cria o perfil de jogador (do NickName do cadastro) uma vez por sessão, para a pessoa já aparecer com link nos
    rankings e na busca de amigos sem precisar abrir Meu Perfil antes."""
    if "_pj_doc" in st.session_state or not _nick_cadastro() or not _ator():
        return
    try:
        meu_perfil()
    except Exception as e:
        banco.registrar_erro("perfis_app.garantir_perfil", e)


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
    if form.get("avatar") not in (None, PF.FOTO, atual["avatar"]):
        import avatares as AV
        if not AV.pode_equipar(form["avatar"], minha_colecao()):       # conferido no servidor: avatar bloqueado não é equipado
            return False, "Esse avatar ainda está bloqueado. " + AV.como_liberar(AV.POR_ID.get(form["avatar"]) or {"desbloqueio": {}}) + "."
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
    for k in ("_pj_pub", "_pj_foto", "_pj_avs"):
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
    """O que a conta logada pode ver do perfil de `usuario`, montado das fontes reais (Jornada, placar dos jogos, data da conta).
    A permissão é decidida no banco (`perfil_alvo`: bloqueio e privacidade); aqui só se projeta o permitido por `perfis.publico`.
    None = não existe, bloqueado ou privado. Devolve {"pub", "h", "rel", "completo", "dono", "aceita"}. O e-mail nunca sai daqui."""
    try:
        k = PF.chave_usuario(PF.validar_usuario(usuario))
    except PF.ErroPerfil:
        return None
    cache = st.session_state.setdefault("_pj_pub", {})
    if k in cache and time.time() - cache[k][0] < _CACHE_PUB_S:
        return cache[k][1]
    out = None
    try:
        import amigos as AM
        import jogos as J
        alvo = banco.perfil_alvo(_ator(), k)
        if alvo:
            email, doc = alvo["email"], alvo["doc"]
            pv = PF.sanear(doc)["privacidade"]
            if alvo["completo"]:
                conta = banco.sis_conta_por_email(email) or {}
                prog = PF.progresso((banco.sis_dados_de(email) or {}).get("edu_progresso"))
                rt, rk = _ranking_de(email)
                placar = banco.sis_estado_ler(email, "jogos_placar")
                foto = FT.uri(banco.sis_estado_ler(email, "perfil_foto")) if PF.sanear(doc)["avatar"] == PF.FOTO else ""
                pub = PF.publico(doc, conta.get("criado_em"), prog, PF.jogos(placar, rt, rk), foto,
                                 amigo=alvo["rel"] == AM.AMIGOS, estat=J.estatisticas(placar), historico=PF.historico_publico(placar))
            else:
                pub = PF.restrito(doc)
            out = {"pub": pub, "h": alvo["h"], "rel": alvo["rel"], "completo": alvo["completo"], "dono": alvo["dono"], "aceita": PF.aceita_pedidos(pv)}
    except Exception as e:
        banco.registrar_erro("perfis_app.publico", e)
    cache[k] = (time.time(), out)
    return out


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


def _avatar_html(avatar: str, foto: str, moldura: dict | None = None, tamanho: int = 104) -> str:
    """Avatar grande (perfil) com a moldura da raridade; a moldura comprada na Loja, se houver, fica por fora."""
    import visual_loja as VL
    av = avatar_html(avatar, foto, tamanho)
    return VL.CSS_MOLDURA + VL.html_moldura(av, moldura) if moldura else av


def _rar_chip(avatar: str) -> str:
    import avatares as AV
    if avatar == PF.FOTO or not AV.existe(avatar):
        return ""
    a = AV.POR_ID[avatar]
    return f"<div class='pj-rar'>{AV.chip(a['raridade'])} <span>{_e(a['nome'])}</span></div>"


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
_CSS_MP = "<style>" + "".join(l.strip() for l in f"""
{_P} .st-key-mp_tela{{max-width:500px !important;margin:0 auto !important;gap:8px !important}}
{_P} .st-key-mp_tela [data-testid="stElementContainer"]{{margin-bottom:0 !important}}
{_P} .st-key-mp_tela [data-testid="stMarkdownContainer"]{{margin-bottom:0 !important}}
{_P} .mp-hero{{position:relative;display:flex;align-items:center;gap:10px;padding:8px 10px;border-radius:18px;border:1.5px solid rgba(52,232,94,.5);
  background:radial-gradient(120% 90% at 0 0,rgba(52,232,94,.16),transparent 55%),linear-gradient(160deg,#1C1570,#0B0738);box-shadow:0 0 16px rgba(52,232,94,.16)}}
{_P} .mp-hero>:first-child:not(.mp-nv),{_P} .mp-hero .mp-nv+*{{flex:0 0 auto}}
{_P} .mp-hero .t{{min-width:0;flex:1;padding-right:64px}}
{_P} .mp-nome{{font-size:1.12rem;font-weight:900;line-height:1.1;color:#fff !important;-webkit-text-fill-color:#fff !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
{_P} .mp-user{{font-size:.74rem;font-weight:700;line-height:1.2;color:#C9C2FF !important;-webkit-text-fill-color:#C9C2FF !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
{_P} .mp-hero .pj-rar{{margin-top:3px;justify-content:flex-start;font-size:.68rem;flex-wrap:wrap}}
{_P} .mp-desde{{display:flex;align-items:center;gap:4px;margin-top:3px;font-size:.66rem;line-height:1.2;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .mp-desde i{{font-style:normal;font-size:.85rem}}
{_P} .mp-nv{{position:absolute;top:8px;right:8px;padding:2px 9px;border-radius:999px;border:1.5px solid #FFC93C;background:rgba(40,24,0,.55);
  font-weight:900;font-size:.72rem;line-height:1.4;color:#FFE08A !important;-webkit-text-fill-color:#FFE08A !important;box-shadow:0 0 10px rgba(255,201,60,.45)}}
{_P} .mp-slogan{{margin-top:2px;font-size:.64rem;line-height:1.2;font-style:italic;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .mp-xpc{{margin:0 !important;padding:5px 10px 6px !important;border-radius:14px !important;border-width:1.5px !important}}
{_P} .mp-xpc .l{{font-size:.72rem !important;line-height:1.2}}
{_P} .mp-xpc .pj-bar{{height:7px;margin-top:4px}}
{_P} .mp-stats{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin:0}}
{_P} .mp-stats div{{text-align:center;padding:5px 2px 4px;border-radius:12px;border:1.5px solid rgba(43,74,140,.9);background:linear-gradient(160deg,#10204A,#0A1433 78%)}}
{_P} .mp-stats div:last-child{{border-color:rgba(139,108,255,.7);background:linear-gradient(160deg,#241A86,#120C4A)}}
{_P} .mp-stats i{{display:block;font-style:normal;font-size:1.05rem;line-height:1.15}}
{_P} .mp-stats b{{display:block;font-size:.82rem;line-height:1.2;font-weight:900;color:#fff !important;-webkit-text-fill-color:#fff !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
{_P} .mp-stats small{{display:block;font-size:.58rem;line-height:1.2;color:#C9C2F2 !important;-webkit-text-fill-color:#C9C2F2 !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
{_P} :is(.st-key-mp_des,.st-key-mp_conq,.st-key-mp_sobre,.st-key-mp_cfg){{height:100%;box-sizing:border-box;padding:7px 8px;border-radius:14px;gap:5px !important;
  background:linear-gradient(160deg,#10204A,#0A1433 78%);border:1.5px solid #2B4A8C;box-shadow:inset 0 1px 0 rgba(120,160,255,.14)}}
{_P} .st-key-mp_des{{border-color:rgba(52,232,94,.55) !important}}
{_P} :is(.st-key-mp_des,.st-key-mp_conq,.st-key-mp_sobre,.st-key-mp_cfg) :is([data-testid="stMarkdownContainer"],[data-testid="stMarkdown"],.stMarkdown){{margin-bottom:0 !important}}
{_P} :is(.st-key-mp_des,.st-key-mp_conq,.st-key-mp_sobre,.st-key-mp_cfg) [data-testid="stElementContainer"]{{margin-bottom:0 !important}}
/* as duas colunas continuam lado a lado no celular (o Streamlit empilha abaixo de 640 px) */
{_P} :is(.st-key-mp_duo,.st-key-mp_duo2) [data-testid="stHorizontalBlock"]{{display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;gap:6px !important;align-items:stretch !important}}
{_P} :is(.st-key-mp_duo,.st-key-mp_duo2) [data-testid="stColumn"]{{flex:1 1 0 !important;width:auto !important;min-width:0 !important}}
{_P} .mp-ct{{display:flex;align-items:center;justify-content:space-between;gap:4px;font-weight:900;font-size:.84rem;line-height:1.2;color:#fff !important;-webkit-text-fill-color:#fff !important;white-space:nowrap}}
{_P} .mp-ct small{{font-weight:700;font-size:.64rem;color:#C9C2F2 !important;-webkit-text-fill-color:#C9C2F2 !important}}
{_P} .mp-des{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr)) auto;align-items:center;gap:2px}}
{_P} .mp-des div{{text-align:center;min-width:0}}
{_P} .mp-des i{{display:block;font-style:normal;font-size:.9rem;line-height:1.2}}
{_P} .mp-des small{{display:block;font-size:.54rem;line-height:1.2;color:#C9C2F2 !important;-webkit-text-fill-color:#C9C2F2 !important;overflow:hidden;text-overflow:ellipsis}}
{_P} .mp-des b{{display:block;font-size:.98rem;line-height:1.15;font-weight:900;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .mp-anel{{width:46px;height:46px;margin:0 auto;border-radius:50%;display:grid;place-items:center;background:conic-gradient(#34E85E var(--p),rgba(255,255,255,.12) 0)}}
{_P} .mp-anel span{{width:36px;height:36px;border-radius:50%;display:grid;place-items:center;background:#0B1736;font-weight:900;font-size:.72rem;color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}
{_P} .mp-anel-r{{text-align:center;font-size:.5rem;line-height:1.1;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;margin-top:2px}}
{_P} .mp-med{{display:flex;gap:4px;justify-content:space-between;margin:2px 0}}
{_P} .mp-med span{{flex:1;aspect-ratio:1;max-width:40px;display:grid;place-items:center;font-size:1rem;clip-path:polygon(50% 0,93% 25%,93% 75%,50% 100%,7% 75%,7% 25%);
  background:linear-gradient(160deg,var(--c),#120C4A)}}
{_P} .mp-med span.no{{--c:#3A3F5C;filter:grayscale(1);opacity:.7}}
{_P} .mp-bio{{font-size:.7rem;line-height:1.3;white-space:pre-line;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .mp-foco{{margin-top:5px;padding-top:5px;border-top:1px solid rgba(255,255,255,.1);font-size:.64rem;color:#C9C2F2 !important;-webkit-text-fill-color:#C9C2F2 !important}}
{_P} .mp-tags{{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}}
{_P} .mp-tags span{{padding:1px 8px;border-radius:999px;border:1px solid rgba(139,108,255,.6);background:rgba(139,108,255,.18);font-size:.64rem;font-weight:700;
  color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} :is(.st-key-mp_des,.st-key-mp_conq,.st-key-mp_cfg) button{{min-height:28px !important;height:28px !important;padding:0 6px !important;border-radius:10px !important}}
{_P} :is(.st-key-mp_des,.st-key-mp_conq,.st-key-mp_cfg) button :is(p,span){{font-size:.7rem !important;line-height:1 !important}}
{_P} .st-key-mp_cfg [data-testid="stIconMaterial"]{{font-size:.95rem !important}}
{_P} .st-key-mp_cfg{{gap:4px !important}}
{_P} :is(.st-key-mp_cfg_ed) button{{border:0 !important;background:linear-gradient(90deg,#8B5CF6,#6D28D9) !important;box-shadow:0 0 12px rgba(139,92,246,.55) !important}}
{_P} :is(.st-key-mp_cfg_ed) button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .mp-jg{{display:flex;gap:6px;margin:0}}
{_P} .mp-jg div{{flex:1;min-width:0;display:flex;justify-content:space-between;align-items:center;gap:4px;padding:5px 9px;border-radius:12px;border:1.5px solid var(--c);
  background:linear-gradient(160deg,var(--f),#0A1433 80%);font-weight:800;font-size:.72rem;line-height:1.2;white-space:nowrap;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .mp-jg em{{font-style:normal;font-weight:900;overflow:hidden;text-overflow:ellipsis;color:var(--c) !important;-webkit-text-fill-color:var(--c) !important}}
{_P} .mp-sec{{margin:2px 2px 0;font-weight:900;font-size:.86rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .st-key-mp_ops{{display:grid !important;grid-template-columns:repeat(auto-fit,minmax(48px,1fr));gap:5px !important}}
{_P} .st-key-mp_ops > div{{width:auto !important;min-width:0}}
{_P} .mp-op{{display:flex;flex-direction:column;align-items:center;gap:2px;padding:5px 2px 4px;border-radius:12px;text-align:center;
  background:linear-gradient(160deg,#10204A,#0A1433 78%);border:1px solid #2B4A8C}}
{_P} .mp-op i{{font-style:normal;font-size:1.05rem;line-height:1.1}}
{_P} .mp-op span{{font-size:.54rem;font-weight:800;line-height:1.1;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}}
{_P} .mp-op.sair{{border-color:rgba(255,107,135,.55)}}
{_P} .st-key-mp_sair_conf{{padding:8px;border-radius:14px;border:1.5px solid rgba(255,107,135,.6);background:#1A0F2E;gap:6px !important}}
{_P} .mp-sair-t{{font-size:.8rem;font-weight:800;color:#fff !important;-webkit-text-fill-color:#fff !important}}
@media (max-width:370px){{{_P} .mp-des{{grid-template-columns:repeat(3,minmax(0,1fr))}}{_P} .mp-des>div:last-child{{grid-column:1 / -1;display:flex;align-items:center;justify-content:center;gap:6px}}
  {_P} .mp-anel{{margin:0}}{_P} .mp-anel-r{{margin:0;text-align:left}}
  {_P} .mp-ct{{font-size:.74rem;white-space:normal}}
  {_P} .mp-stats b{{font-size:.72rem}}{_P} .mp-jg div{{font-size:.64rem;padding:5px 7px}}}}
""".splitlines()) + "</style>"


def _extras_meus() -> dict:
    """Sequência, Ticker Coins, patrimônio (T$) e interesses do cadastro: só leitura, das fontes que o app já usa."""
    out = {"ofensiva": 0, "tc": None, "pat": None, "foco": [], "rank": "—"}
    try:                       # a mesma posição no ranking geral que a Home mostra
        import home_game_app as HGA
        pos = HGA._posicao()[0]
        out["rank"] = f"#{int(pos)}" if pos else "—"
    except Exception:
        pass
    try:
        import educacao_app as EA
        import jornada as JO
        out["ofensiva"] = int(JO.resumo(EA.prog()).get("ofensiva") or 0)
    except Exception:
        pass
    try:
        import tickercoins_app as TCA
        out["tc"] = TCA.saldo_atual()
    except Exception:
        pass
    try:
        import wallet_game as WG
        import wallet_game_app as WGA
        out["pat"] = WG.moeda_curta(WGA.resultado(_ator())["rank"]["patrimonio"])
    except Exception:
        pass
    try:
        import onboarding as O
        o = O.normalizar(st.session_state.get("onb"))
        nomes = {i["id"]: i["titulo"] for i in O.INTERESSES}
        out["foco"] = [nomes[i] for i in (o.get("interesses") or []) if i in nomes][:4]
    except Exception:
        pass
    return out


def _sair() -> None:
    usuarios.sair()


def _sair_confirmado() -> None:
    st.session_state.pop("mp_sair_conf", None)
    _sair()


_OPCOES = (   # (chave, rótulo, ícone, destino) — o que antes ficava na janela "Minha Conta" do avatar
    ("conta", "Minha conta", "🏠", "conta"), ("loja", "Loja Ticker", "🛍️", "economia"), ("planos", "Planos", "💎", "planos"),
    ("ajuda", "Ajuda", "❔", "ajuda"), ("admin", "Administração", "🛡️", "administracao"),
)


def pagina_meu_perfil() -> None:
    st.markdown(CSS + _CSS_MP, unsafe_allow_html=True)
    if not _ator():
        return
    _msg()
    with st.container(key="mp_tela"):
        _meu_perfil_corpo()


def _meu_perfil_corpo() -> None:
    try:
        d = _dados_meus()
        x = _extras_meus()
    except Exception as e:
        banco.registrar_erro("perfis_app.meu_perfil", e)
        st.markdown("<div class='pj-vazio'>Seu perfil não carregou agora. Tente de novo em instantes.</div>", unsafe_allow_html=True)
        return
    desde = d.get("desde") or ""
    desde = f"No TickerHunters desde {desde[8:10]}/{desde[5:7]}/{desde[:4]}" if len(desde) >= 10 else ""
    st.markdown(
        f"<div class='mp-hero'><span class='mp-nv'>⭐ Nível {d['nivel']}</span>{_avatar_html(d['avatar'], minha_foto_uri(), _moldura(), 74)}"
        f"<div class='t'><div class='mp-nome'>{_e(d.get('nome') or d.get('usuario') or 'Jogador')}</div>"
        f"<div class='mp-user'>{'@' + _e(d['usuario']) if d.get('usuario') else 'Escolha seu nome de usuário em Editar perfil'}</div>"
        f"{_rar_chip(d['avatar'])}"
        + (f"<div class='mp-desde'><i>🏆</i>{_e(desde)}</div>" if desde else "")
        + f"<div class='mp-slogan'>{_e(d['titulo'])} · Aprender. Jogar. Evoluir.</div></div></div>", unsafe_allow_html=True)
    ne = d["nivel_est"]
    falta = "Nível máximo!" if ne["maximo"] else f"faltam {ne['falta']} XP para o nível {ne['nivel'] + 1}"
    st.markdown(f"<div class='pj-xp mp-xpc'><div class='l'>⭐ {d['xp']} XP<span>{_e(falta)}</span></div><div class='pj-bar'><i style='width:{ne['pct'] * 100:.0f}%'></i></div></div>",
                unsafe_allow_html=True)
    tc = f"{x['tc']:,}".replace(",", ".") if x["tc"] is not None else "—"
    st.markdown("<div class='mp-stats'>"
                f"<div><i>🔥</i><b>{x['ofensiva']} {'dia' if x['ofensiva'] == 1 else 'dias'}</b><small>Sequência</small></div>"
                f"<div><i>🏆</i><b>{_e(x['rank'])}</b><small>Ranking</small></div>"
                f"<div><i>🪙</i><b>{tc}</b><small>Ticker Coins</small></div>"
                f"<div><i>💰</i><b>{_e(x['pat'] or '—')}</b><small>Patrimônio</small></div></div>", unsafe_allow_html=True)
    # ---- Desempenho + Conquistas
    es = d["est"]
    taxa = es["taxa"] if es["taxa"] is not None else 0
    md = sorted(d["medalhas"], key=lambda m: not m.get("ok"))
    ok = sum(1 for m in md if m.get("ok"))
    cores = ("#F2B84B", "#34E85E", "#FF5A6B", "#8B6CFF")
    with st.container(key="mp_duo"):
        c1, c2 = st.columns(2)
        with c1:
            with st.container(key="mp_des"):
                st.markdown("<div class='mp-ct'>📊 Desempenho</div><div class='mp-des'>"
                            f"<div><i>▶️</i><small>Partidas</small><b>{es['partidas']}</b></div><div><i>🏆</i><small>Vitórias</small><b>{es['vitorias']}</b></div>"
                            f"<div><i>💀</i><small>Derrotas</small><b>{es['derrotas']}</b></div>"
                            f"<div><div class='mp-anel' style='--p:{taxa:.0f}%'><span>{(str(round(taxa)) + '%') if es['taxa'] is not None else '—'}</span></div>"
                            "<div class='mp-anel-r'>Taxa de vitórias</div></div></div>", unsafe_allow_html=True)
                st.button("Ver detalhes →", key="mp_des_ver", width="stretch", on_click=_ir, args=("jogos-ranking",))
        with c2:
            with st.container(key="mp_conq"):
                med = [m for m in md if m.get("ok")][:3]
                fig = "".join(f"<span style='--c:{cores[i % 4]}'>{_e(m.get('emblema', '🏅'))}</span>" for i, m in enumerate(med))
                fig += "<span class='no'>🔒</span>" * max(1, 4 - len(med)) if ok < len(md) else ""
                st.markdown(f"<div class='mp-ct'>🏅 Conquistas<small>{ok} de {len(md)}</small></div><div class='mp-med'>{fig}</div>", unsafe_allow_html=True)
                st.button("Ver menos ↑" if st.session_state.get("mp_conq_todas") else "Ver todas →", key="mp_conq_ver", width="stretch",
                          on_click=lambda: st.session_state.update(mp_conq_todas=not st.session_state.get("mp_conq_todas")))
    if st.session_state.get("mp_conq_todas") and md:
        st.markdown("<div class='pj-md'>" + "".join(
            f"<div class='{'ok' if m.get('ok') else ''}' title='{_e(m.get('descricao', ''))}'><i>{_e(m.get('emblema', '🏅'))}</i><span>{_e(m.get('nome', ''))}</span></div>"
            for m in md) + "</div>", unsafe_allow_html=True)
    # ---- Sobre mim + Configurações rápidas
    with st.container(key="mp_duo2"):
        c1, c2 = st.columns(2)
        with c1:
            with st.container(key="mp_sobre"):
                foco = "".join(f"<span>{_e(t)}</span>" for t in x["foco"])
                st.markdown("<div class='mp-ct'>👤 Sobre mim</div>"
                            + f"<div class='mp-bio'>{_e(d['bio']) if d.get('bio') else 'Conte um pouco sobre você em Editar perfil.'}</div>"
                            + (f"<div class='mp-foco'>Meu foco:<div class='mp-tags'>{foco}</div></div>" if foco else ""), unsafe_allow_html=True)
        with c2:
            with st.container(key="mp_cfg"):
                st.markdown("<div class='mp-ct'>⚙️ Configurações rápidas</div>", unsafe_allow_html=True)
                with st.container(key="mp_cfg_ed"):
                    st.button("Editar perfil", key="pj_editar", icon=":material/edit:", width="stretch", on_click=_ir, args=("perfil-editar",),
                              kwargs={"pe_novo": True, "pe_foco": None})
                st.button("Privacidade", key="pj_priv", icon=":material/lock:", width="stretch", on_click=_ir, args=("perfil-editar",),
                          kwargs={"pe_novo": True, "pe_foco": "privacidade"})
                st.button("Tema do app", key="pj_tema", icon=":material/palette:", width="stretch", on_click=_ir, args=("perfil-editar",),
                          kwargs={"pe_novo": True, "pe_foco": None})
    # ---- Jogos (posição em cada ranking)
    t, k = d["jogos"]["trade"], d["jogos"]["ticker"]
    pos = lambda v: f"#{v}" if v else "—"
    st.markdown("<div class='mp-jg'>"
                f"<div style='--c:{VERDE};--f:rgba(20,110,80,.55)'>Trade Battle<em>{pos(t['posicao'])} · {_fmt_pts(t['pontos'])} pts</em></div>"
                f"<div style='--c:{ROXO};--f:rgba(110,70,230,.5)'>Ticker Battle<em>{pos(k['posicao'])} · {k['vitorias']} vit.</em></div></div>", unsafe_allow_html=True)
    # ---- Opções da conta (o que ficava na janela do avatar)
    st.markdown("<div class='mp-sec'>Conta</div>", unsafe_allow_html=True)
    with st.container(key="mp_ops"):
        for ch, rot, ic, dest in _OPCOES:
            if ch == "admin" and not usuarios.pode("admin.resumo"):
                continue
            with st.container(key=f"lk_mpo_{ch}"):
                st.markdown(f"<div class='mp-op'><i>{ic}</i><span>{_e(rot)}</span></div>", unsafe_allow_html=True)
                st.button(f"Abrir {rot}", key=f"mpo_b_{ch}", on_click=_ir, args=(dest,))
        with st.container(key="lk_mpo_sair"):
            st.markdown("<div class='mp-op sair'><i>🚪</i><span>Sair</span></div>", unsafe_allow_html=True)
            st.button("Sair da conta", key="mpo_b_sair", on_click=lambda: st.session_state.update(mp_sair_conf=True))
    if st.session_state.get("mp_sair_conf"):          # sair pede confirmação: um toque sem querer não desloga
        with st.container(key="mp_sair_conf"):
            st.markdown("<div class='mp-sair-t'>Sair da sua conta neste aparelho?</div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            c1.button("Cancelar", key="mp_sair_nao", width="stretch", on_click=lambda: st.session_state.pop("mp_sair_conf", None))
            c2.button("Sim, sair", key="mp_sair_sim", type="primary", width="stretch", on_click=_sair_confirmado)
    st.caption("Pontos, vitórias, XP e conquistas vêm dos jogos e da Jornada e não podem ser editados.")


# ------------------------------------------------------------------ TELA · Editar Perfil (rascunho até salvar)
_CAMPOS = ("pe_nome", "pe_usuario", "pe_bio", "pe_avatar", "pe_tema", "pe_moldura", "pe_tema_loja", "pe_vis", "pe_ped", "pe_mbio", "pe_mnivel", "pe_mconq", "pe_mjogos", "pe_mhist",
           "pe_foto", "pe_remover", "pe_zoom", "pe_x", "pe_y", "pe_up", "pe_foco", "pe_ver")


def _iniciar_rascunho() -> None:
    """Copia o perfil salvo para os campos do rascunho (ao entrar na tela). Nada é gravado até 'Salvar'."""
    import prefs as PR
    ss = st.session_state
    for k in _CAMPOS:
        if k != "pe_foco":
            ss.pop(k, None)
    p, pv = meu_perfil(), meu_perfil()["privacidade"]
    ss.update(pe_nome=p["nome"] or p["usuario"], pe_usuario=p["usuario"], pe_bio=p["bio"], pe_avatar=p["avatar"],
              pe_tema=PR.normalizar(ss.get("prefs"))["tema"], pe_vis=pv["visivel"], pe_ped=pv["pedidos"], pe_mbio=pv["mostrar_bio"],
              pe_mnivel=pv["mostrar_nivel"], pe_mconq=pv["mostrar_conquistas"], pe_mjogos=pv["mostrar_jogos"], pe_mhist=pv["mostrar_historico"], pe_zoom=1.0, pe_x=0.0, pe_y=0.0)
    ss["pe_moldura"] = itens_loja("moldura")[1] or ""
    ss["pe_tema_loja"] = itens_loja("tema")[1] or ""


def _cancelar() -> None:
    for k in _CAMPOS:
        st.session_state.pop(k, None)
    st.session_state["_pj_msg"] = (True, "Edição cancelada. Nada foi alterado.")
    st.session_state["_nav_pend"] = "perfil"


def _ver_avatar(a: str) -> None:
    st.session_state["pe_ver"] = a


def _usar_avatar(a: str) -> None:
    """Equipa o avatar e JÁ GRAVA no perfil (só se estiver liberado; o servidor confere de novo em salvar)."""
    import avatares as AV
    if AV.pode_equipar(a, minha_colecao()):
        ok, msg = salvar({"avatar": a})
        if not ok:
            st.session_state["_pe_aviso"] = (False, msg)
            return
        _escolher_avatar(a)
        st.session_state["_pe_aviso"] = (True, f"Pronto! {AV.POR_ID[a]['nome']} é o seu avatar agora.")
    else:
        st.session_state["_pe_aviso"] = (False, "Esse avatar ainda está bloqueado. " + AV.como_liberar(AV.POR_ID[a]) + ".")


def _colecao_avatares() -> None:
    """Coleção de Avatares: filtros por raridade, grade com liberados e bloqueados, prévia e "Usar este avatar"."""
    import avatares as AV
    ss = st.session_state
    lib = minha_colecao()
    tot = AV.totais(lib)
    ops = ["todos"] + list(AV.RARIDADES)
    fil = st.segmented_control("Raridade", ops, default="todos", key="pe_fil", label_visibility="collapsed",
                               format_func=lambda r: "Todos" if r == "todos" else AV.RARIDADES[r]["plural"]) or "todos"
    n_ok, n = sum(v["ok"] for v in tot.values()), sum(v["total"] for v in tot.values())
    st.markdown("<div class='pj-col-h'><span><b>" + str(n_ok) + "</b> de " + str(n) + " liberados</span>"
                + "".join(f"<span>{AV.chip(r)} {tot[r]['ok']}/{tot[r]['total']}</span>" for r in AV.RARIDADES) + "</div>", unsafe_allow_html=True)
    ver = ss.get("pe_ver") if AV.existe(ss.get("pe_ver")) else (ss.get("pe_avatar") if AV.existe(ss.get("pe_avatar")) else None)
    if ver:
        a = AV.POR_ID[ver]
        livre = ver in lib
        estado = "Equipado no rascunho" if ver == ss.get("pe_avatar") else ("Liberado" if livre else "🔒 " + AV.como_liberar(a))
        st.markdown(f"<div class='pe-prevc'>{AV.html(ver, 84)}<div class='t'><b>{_e(a['nome'])}</b>{AV.chip(a['raridade'])}"
                    f"<small>{_e(AV.RARIDADES[a['raridade']]['dica'])} · {_e(estado)}</small></div></div>", unsafe_allow_html=True)
        if ver != ss.get("pe_avatar"):
            st.button("Usar este avatar" if livre else "Bloqueado", key="pe_usar_av", icon=":material/check:" if livre else ":material/lock:",
                      width="stretch", disabled=not livre, on_click=_usar_avatar, args=(ver,))
    with st.container(key="pe_col"):
        for it in AV.colecao(lib, ss.get("pe_avatar"), None if fil == "todos" else fil):
            cls = ("eq " if it["equipado"] else "") + ("ver " if it["id"] == ver and not it["equipado"] else "") + ("" if it["liberado"] else "bloq")
            extra = ("<span class='eqk'>✓</span>" if it["equipado"] else "") + ("" if it["liberado"] else "<span class='cad'>🔒</span>")
            lv = "" if it["liberado"] else f"<span class='lv'>{_e(it['como'])}</span>"
            with st.container(key=f"lk_pec_{it['id']}"):
                st.markdown(f"<div class='pe-t {cls}'>{extra}{AV.html(it['id'], 58, pequeno=True)}<span class='n'>{_e(it['nome'])}</span>"
                            f"{AV.chip(it['raridade'])}{lv}</div>", unsafe_allow_html=True)
                st.button(f"Ver {it['nome']}", key=f"pec_b_{it['id']}", on_click=_ver_avatar, args=(it["id"],))


def _escolher_avatar(a: str) -> None:
    ss = st.session_state
    ss["pe_avatar"] = a
    ss.pop("pe_foto", None)
    ss["pe_remover"] = False


def _usar_foto() -> None:
    """Processa a foto enviada com o recorte escolhido e JÁ GRAVA no perfil (é o que a pessoa espera ao tocar em "Usar esta foto").
    Os outros campos do rascunho (nome, bio, privacidade...) continuam esperando o Salvar."""
    ss = st.session_state
    arq = ss.get("pe_up")
    try:
        if arq is None:
            raise FT.ErroFoto("Escolha uma imagem da galeria primeiro.")
        webp = FT.processar(arq.getvalue(), ss.get("pe_zoom", 1.0), ss.get("pe_x", 0.0), ss.get("pe_y", 0.0))
        ok, msg = salvar({"avatar": PF.FOTO}, foto_webp=webp)
        if not ok:
            ss["_pe_aviso"] = (False, msg)
            return
        ss.pop("pe_foto", None)
        ss["pe_avatar"], ss["pe_remover"] = PF.FOTO, False
        ss.pop("pe_up", None)
        ss["_pe_aviso"] = (True, "Foto atualizada no seu perfil!")
    except FT.ErroFoto as e:
        ss["_pe_aviso"] = (False, str(e))
    except Exception as e:
        banco.registrar_erro("perfis_app.usar_foto", e)
        ss["_pe_aviso"] = (False, "Não consegui processar essa imagem. Tente outra foto.")


def _remover_foto() -> None:
    """Tira a foto enviada e volta ao avatar padrão, já gravando no perfil."""
    ss = st.session_state
    ok, msg = salvar({"avatar": PF.AVATAR_PADRAO}, remover_foto=True)
    if not ok:
        ss["_pe_aviso"] = (False, msg)
        return
    ss.pop("pe_foto", None)
    ss["pe_remover"], ss["pe_avatar"] = False, PF.AVATAR_PADRAO
    ss["_pe_aviso"] = (True, "Foto removida. Você voltou ao avatar padrão.")


def _salvar_edicao() -> None:
    ss = st.session_state
    form = {"nome": ss.get("pe_nome", ""), "usuario": ss.get("pe_usuario", ""), "bio": ss.get("pe_bio", ""), "avatar": ss.get("pe_avatar", PF.AVATAR_PADRAO),
            "tema": ss.get("pe_tema"), "privacidade": {"visivel": ss.get("pe_vis"), "pedidos": ss.get("pe_ped"),
                                                        "mostrar_bio": bool(ss.get("pe_mbio")), "mostrar_nivel": bool(ss.get("pe_mnivel")),
                                                        "mostrar_conquistas": bool(ss.get("pe_mconq")), "mostrar_jogos": bool(ss.get("pe_mjogos")),
                                                        "mostrar_historico": bool(ss.get("pe_mhist"))}}
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
    try:
        import amigos_app as AMA
        AMA.mostrar_msg()
    except Exception:
        pass
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
    st.markdown("<div class='pj-sec'>📷 Foto de perfil</div><div class='pj-prev'>" + _avatar_html(ss.get("pe_avatar", PF.AVATAR_PADRAO), foto_prev) + _rar_chip(ss.get("pe_avatar", PF.AVATAR_PADRAO))
                + f"<small>{'Prévia: ainda não foi salvo.' if ss.get('pe_foto') or ss.get('pe_remover') else 'Como está agora.'}</small></div>",
                unsafe_allow_html=True)
    aba = st.segmented_control("Origem da foto", ["Coleção de avatares", "Enviar da galeria"], default="Coleção de avatares", key="pe_aba", label_visibility="collapsed")
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
        _colecao_avatares()
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
        st.radio("Quem pode ver meu perfil", list(PF.VISIVEL), key="pe_vis", format_func=lambda v: PF.VISIVEL[v])
        st.caption("Com \"Só meus amigos\", quem não é seu amigo vê apenas seu nome e avatar, para poder pedir amizade.")
        st.toggle("Mostrar estatísticas competitivas (vitórias, derrotas, pontos e posições)", key="pe_mjogos")
        st.toggle("Mostrar histórico de partidas", key="pe_mhist")
        st.toggle("Mostrar conquistas e medalhas", key="pe_mconq")
        st.toggle("Mostrar nível e XP", key="pe_mnivel")
        st.toggle("Mostrar a biografia", key="pe_mbio")
        st.radio("Quem pode me enviar solicitações de amizade", list(PF.PEDIDOS), key="pe_ped", format_func=lambda v: PF.PEDIDOS[v], horizontal=True)
        st.caption("Nunca aparecem para outras pessoas: e-mail, patrimônio, carteira, saldos de T$ ou Ticker Coins e o ID da conta.")
        st.markdown("**Jogadores bloqueados**")
        try:
            import amigos_app as AMA
            AMA.secao_bloqueados()
        except Exception as e:
            banco.registrar_erro("perfis_app.bloqueados", e)
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


def _hist_html(h: dict) -> str:
    import jogos as J
    quando = f"{h['em'][8:10]}/{h['em'][5:7]}" if len(h.get("em", "")) >= 10 else ""
    if h["jogo"] == J.TRADE:
        v = h.get("pts", 0)
        res = (f"{h['pos']}º de {h['n']} · " if h.get("pos") and h.get("n", 1) >= 2 else "Solo · ") + _fmt_pts(v) + " pts"
        cls = "ok" if v > 0 else "no" if v < 0 else ""
    else:
        res, cls = {"v": ("Vitória", "ok"), "e": ("Empate", ""), "d": ("Derrota", "no")}.get(h.get("r"), ("—", ""))
    return f"<div class='pj-h'><span>{_e(J.NOME[h['jogo']])}<small>{_e(quando)}</small></span><b class='{cls}'>{_e(res)}</b></div>"


def _acoes_publicas(usuario: str, v: dict) -> None:
    """Botões do perfil de outra pessoa conforme a relação. Cada um chama o banco, que confere a permissão de novo."""
    import amigos as AM
    import amigos_app as AMA
    h, rel = v["h"], v["rel"]
    if rel == AM.AMIGOS:
        c1, c2 = st.columns([1.4, 1])
        with c1.popover("Convidar para jogar", icon=":material/sports_esports:", width="stretch"):
            st.caption("Cria uma sala privada e avisa seu amigo com o código.")
            st.button("Trade Battle", key="pp_cv_trade", icon=":material/candlestick_chart:", width="stretch", on_click=AMA.convidar, args=(h, "trade"))
            st.button("Ticker Battle", key="pp_cv_ticker", icon=":material/style:", width="stretch", on_click=AMA.convidar, args=(h, "ticker"))
        c2.markdown("<div class='pj-rel'>✓ Amigos</div>", unsafe_allow_html=True)
    elif rel == AM.ENVIADA:
        st.button("Cancelar solicitação", key="pp_cancelar", icon=":material/close:", width="stretch", on_click=AMA.cancelar, args=(h,))
    elif rel == AM.RECEBIDA:
        st.markdown(f"<div class='pj-rel'>@{_e(usuario)} quer ser seu amigo</div>", unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        c1.button("Aceitar", key="pp_aceitar", icon=":material/check:", type="primary", width="stretch", on_click=AMA.aceitar, args=(h,))
        c2.button("Recusar", key="pp_recusar", icon=":material/close:", width="stretch", on_click=AMA.recusar, args=(h,))
    elif v["aceita"]:
        st.button("Adicionar amigo", key="pp_add", icon=":material/person_add:", width="stretch", on_click=AMA.pedir, args=(usuario,))
    else:
        st.caption("Este jogador não está recebendo solicitações de amizade.")
    with st.expander("Mais opções", icon=":material/more_horiz:"):
        if rel == AM.AMIGOS:
            st.button("Remover amigo", key="pp_remover", icon=":material/person_remove:", width="stretch", on_click=AMA.remover, args=(h,))
        st.markdown("**Denunciar perfil**")
        st.selectbox("Motivo", list(AM.MOTIVOS), key=f"pp_den_mot_{h}", format_func=lambda m: AM.MOTIVOS[m], index=None, placeholder="Escolha o motivo")
        st.text_area("Detalhes (opcional)", key=f"pp_den_txt_{h}", max_chars=AM.TEXTO_DENUNCIA_MAX, height=80)
        st.button("Enviar denúncia", key="pp_den", icon=":material/flag:", width="stretch", on_click=AMA.denunciar, args=(h,))
        st.markdown("**Bloquear**")
        st.caption("Desfaz a amizade e os pedidos, e vocês deixam de ver o perfil um do outro. Dá para desbloquear em Editar Perfil › Privacidade.")
        conf = st.checkbox(f"Quero bloquear @{usuario}", key=f"pp_blq_ok_{h}")
        st.button("Bloquear usuário", key="pp_blq", icon=":material/block:", width="stretch", disabled=not conf, on_click=AMA.bloquear, args=(h,))


def pagina_publica() -> None:
    """Perfil público de outro jogador (/jogador?u=<nome de usuário>): só o que a pessoa permitiu; nada financeiro. Ações de amizade,
    convite para jogar, denúncia e bloqueio."""
    st.markdown(CSS, unsafe_allow_html=True)
    import amigos_app as AMA
    st.markdown(AMA.CSS, unsafe_allow_html=True)
    AMA.mostrar_msg()
    u = str(st.query_params.get("u") or "")
    v = perfil_publico(u) if u and _ator() else None
    if not v:
        st.markdown("<div class='pj-vazio'>Perfil não encontrado ou indisponível.</div>", unsafe_allow_html=True)
        st.button("Voltar para Meus Amigos", key="pp_voltar", icon=":material/group:", on_click=_ir, args=("jogos-amigos",))
        return
    p = v["pub"]
    if v["dono"]:
        st.markdown("<div class='pj-vazio'>Este é o seu perfil.</div>", unsafe_allow_html=True)
        st.button("Abrir Meu Perfil", key="pp_meu", icon=":material/person:", width="stretch", on_click=_ir, args=("perfil",))
        return
    desde = p.get("desde") or ""
    nivel = f"<span class='pj-nv'>Nível {p['nivel']}</span>" if p.get("nivel") else ""
    st.markdown(f"<div class='pj-hero'>{nivel}{_avatar_html(p['avatar'], p.get('foto', ''))}{_rar_chip(p['avatar'])}<div class='pj-nome'>{_e(p['nome'])}</div>"
                f"<div class='pj-user'>@{_e(p['usuario'])}{' · ' + _e(p['titulo']) if p.get('titulo') else ''}</div>"
                + (f"<div class='pj-bio'>{_e(p['bio'])}</div>" if p.get("bio") else "")
                + (f"<div class='pj-desde'>No TickerHunters desde {desde[5:7]}/{desde[:4]}</div>" if len(desde) >= 7 else "") + "</div>", unsafe_allow_html=True)
    if p.get("xp") is not None:
        import nivel as NV
        ne = NV.estado(p["xp"])
        st.markdown(f"<div class='pj-xp'><div class='l'>⭐ {p['xp']} XP<span>{'Nível máximo' if ne['maximo'] else 'Nível ' + str(ne['nivel'])}</span></div>"
                    f"<div class='pj-bar'><i style='width:{ne['pct'] * 100:.0f}%'></i></div></div>", unsafe_allow_html=True)
    _acoes_publicas(p["usuario"], v)
    if not v["completo"]:
        st.markdown("<div class='pj-vazio'>🔒 Este perfil é visível só para amigos. Adicione para ver as conquistas e o desempenho.</div>", unsafe_allow_html=True)
        return
    es = p.get("estat")
    if es:
        taxa = f"{es['taxa']:.0f}%" if es.get("taxa") is not None else "—"
        st.markdown("<div class='pj-sec'>📊 Desempenho</div><div class='pj-g'>"
                    f"<div><small>Partidas</small><b>{es['partidas']}</b></div><div class='ok'><small>Vitórias</small><b>{es['vitorias']}</b></div>"
                    f"<div class='no'><small>Derrotas</small><b>{es['derrotas']}</b></div><div class='ou'><small>Taxa de vitórias</small><b>{taxa}</b></div></div>",
                    unsafe_allow_html=True)
    j = p.get("jogos")
    if j:
        t, k = j["trade"], j["ticker"]
        pos = lambda x: f"#{x}" if x else "—"
        st.markdown("<div class='pj-sec'>🎮 Jogos e rankings</div><div class='pj-jg'>"
                    f"<div style='--c:{VERDE};--f:rgba(20,110,80,.6)'><div class='t'>Trade Battle<em>{pos(t['posicao'])}</em></div>"
                    f"<p>Pontos<b>{_fmt_pts(t['pontos'])}</b></p><p>Partidas<b>{t['partidas']}</b></p><p>1º lugar em sala<b>{t['vitorias']}</b></p></div>"
                    f"<div style='--c:{ROXO};--f:rgba(110,70,230,.55)'><div class='t'>Ticker Battle<em>{pos(k['posicao'])}</em></div>"
                    f"<p>Vitórias<b>{k['vitorias']}</b></p><p>Empates<b>{k['empates']}</b></p><p>Derrotas<b>{k['derrotas']}</b></p></div></div>",
                    unsafe_allow_html=True)
    if isinstance(p.get("conquistas"), dict):
        md = p.get("medalhas") or []
        st.markdown(f"<div class='pj-sec'>🏅 Conquistas e medalhas<small>{p['conquistas']['ok']} de {p['conquistas']['total']}</small></div>"
                    + ("<div class='pj-md'>" + "".join(f"<div class='ok'><i>{_e(m['emblema'])}</i><span>{_e(m['nome'])}</span></div>" for m in md[:12]) + "</div>"
                       if md else "<div class='pj-vazio'>Nenhuma conquista ainda.</div>"), unsafe_allow_html=True)
    if p.get("historico"):
        st.markdown("<div class='pj-sec'>🕑 Últimas partidas</div><div class='pj-hl'>" + "".join(_hist_html(h) for h in p["historico"]) + "</div>",
                    unsafe_allow_html=True)
    if not (es or j or p.get("historico")):
        st.caption("Este jogador escolheu não mostrar as estatísticas.")
