"""Onboarding — Tela 1: Seu Perfil (perfil de investidor + NickName). Só apresentação: as regras estão em onboarding.py.

Aparece uma vez, para conta nova que ainda não concluiu o onboarding. Não marca o onboarding como concluído (as telas 2 e 3 ainda não existem):
guarda perfil e NickName em `onb` (gravado junto com os dados da conta) e reserva o NickName no mesmo cadastro do ranking, sem aceitar o termo.
"""
from __future__ import annotations

import html

import streamlit as st

import arte_onboarding as ART
import banco
import competicao as C
import onboarding as O
import usuarios

_P = "html body .stApp.stApp.stApp"

_CSS = f"""
{_P}{{background:radial-gradient(120% 60% at 50% 0%,#241257 0%,#0B0821 55%,#070516 100%) !important}}
{_P} header[data-testid="stHeader"],{_P} [data-testid="stSidebar"],{_P} [data-testid="stSidebarCollapsedControl"],{_P} [data-testid="stToolbar"]{{display:none !important}}
{_P} [data-testid="stMainBlockContainer"],{_P} .block-container{{max-width:520px !important;padding:26px 14px 28px !important;margin:0 auto !important}}
{_P} .onb-marca{{display:flex;justify-content:center;margin:2px 0 6px}}
{_P} .onb-marca .wm-t{{color:#fff;font-weight:900;letter-spacing:.01em}}{_P} .onb-marca .wm-t em{{color:#A78BFA;font-style:normal}}
/* stepper */
{_P} .onb-steps{{display:grid;grid-template-columns:1fr 1fr 1fr;position:relative;margin:6px 0 4px}}
{_P} .onb-steps:before{{content:"";position:absolute;top:13px;left:16.6%;right:16.6%;height:2px;background:linear-gradient(90deg,#7C3AED,#3B2F7A 40%,#3B2F7A);z-index:0}}
{_P} .onb-st{{position:relative;z-index:1;display:flex;flex-direction:column;align-items:center;gap:5px;font-size:.68rem;font-weight:700;color:#A7A0D6;text-align:center}}
{_P} .onb-st i{{display:grid;place-items:center;width:28px;height:28px;border-radius:50%;font-style:normal;font-weight:800;font-size:.8rem;color:#C9C2F2;background:#150F38;border:2px solid #3B2F7A}}
{_P} .onb-st.on{{color:#fff}}{_P} .onb-st.on i{{color:#fff;border-color:#8B5CF6;background:#1B1050;box-shadow:0 0 12px rgba(139,92,246,.75)}}
/* herói */
{_P} .onb-hero{{position:relative;text-align:center;margin:0 -6px}}
{_P} .onb-hero .onb-lobo{{display:block;width:78%;max-width:340px;margin:0 auto;aspect-ratio:1.5/1;object-fit:cover;object-position:46% 30%;
  -webkit-mask-image:radial-gradient(ellipse closest-side at 50% 48%,#000 60%,transparent 100%);mask-image:radial-gradient(ellipse closest-side at 50% 48%,#000 60%,transparent 100%)}}
{_P} .onb-hero .onb-h{{margin:-16px 0 2px;padding:0;font-size:1.85rem;font-weight:900;font-style:italic;color:#fff !important;-webkit-text-fill-color:#fff !important;text-shadow:0 2px 14px rgba(0,0,0,.7)}}
{_P} .onb-hero .onb-sub{{margin:0 8px 8px;font-size:.86rem;line-height:1.35;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
/* blocos */
{_P} .st-key-onb_perfil,{_P} .st-key-onb_nick{{background:linear-gradient(180deg,rgba(40,26,110,.55),rgba(14,10,46,.75));border:1px solid rgba(124,92,255,.45);border-radius:16px;padding:12px 10px 12px !important;margin:0 0 10px;box-shadow:0 0 0 1px rgba(0,0,0,.3) inset,0 8px 26px rgba(0,0,0,.35)}}
{_P} .onb-tit{{display:flex;align-items:center;gap:8px;margin:0 2px 8px;font-weight:800;font-size:.98rem}}
{_P} .onb-tit .t1{{display:block;color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800;font-size:.98rem}}
{_P} .onb-tit svg{{flex:0 0 auto}}{_P} .onb-tit small{{display:block;font-weight:500;color:#B9B2E6 !important;-webkit-text-fill-color:#B9B2E6 !important;font-size:.72rem}}
/* grade 3+2 dos perfis */
{_P} .st-key-onb_grade[data-testid="stVerticalBlock"],{_P} .st-key-onb_grade>[data-testid="stVerticalBlock"]{{display:grid !important;grid-template-columns:repeat(6,minmax(0,1fr)) !important;gap:8px !important}}
{_P} [class*="st-key-onbc_"]{{position:relative;grid-column:span 2;gap:0 !important;height:100%}}
{_P} [class*="st-key-onbc_"] [data-testid="stMarkdownContainer"],{_P} [class*="st-key-onbc_"] [data-testid="stElementContainer"]:has(.onb-card){{margin:0 !important;height:100%}}
{_P} .st-key-onb_grade{{align-items:stretch}}
{_P} .st-key-onbc_iniciante,{_P} .st-key-onbc_explorador{{grid-column:span 3}}
{_P} .st-key-onb_grade>*:has([class*="st-key-onbc_"]){{grid-column:span 2}}
{_P} .st-key-onb_grade>*:has(.st-key-onbc_iniciante),{_P} .st-key-onb_grade>*:has(.st-key-onbc_explorador){{grid-column:span 3}}
{_P} [class*="st-key-onbc_"] [data-testid="stElementContainer"]:has(button){{position:absolute !important;inset:0;z-index:3;width:100% !important;height:100% !important}}
{_P} [class*="st-key-onbc_"] button{{width:100% !important;height:100% !important;min-height:100% !important;opacity:0;cursor:pointer;padding:0 !important}}
{_P} .onb-card{{position:relative;height:100%;box-sizing:border-box;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:3px;min-height:92px;padding:8px 6px 8px;border-radius:14px;text-align:center;
  background:linear-gradient(160deg,color-mix(in srgb,var(--c) 14%,#140E3A),#0E0A2C 80%);border:1.5px solid color-mix(in srgb,var(--c) 42%,transparent);transition:transform .1s,box-shadow .1s}}
{_P} .onb-card img{{width:38px;height:38px;object-fit:contain;border-radius:8px}}
{_P} .onb-card b{{font-size:.84rem;color:#fff;font-weight:800;line-height:1.1}}
{_P} .onb-card span{{font-size:.62rem;color:#C4BEEA;line-height:1.2}}
{_P} .onb-card.sel{{border:2px solid var(--c);background:linear-gradient(160deg,color-mix(in srgb,var(--c) 30%,#140E3A),color-mix(in srgb,var(--c) 10%,#0E0A2C) 85%);box-shadow:0 0 14px color-mix(in srgb,var(--c) 70%,transparent),0 0 0 1px color-mix(in srgb,var(--c) 40%,transparent) inset;transform:translateY(-1px)}}
{_P} .onb-card .ok{{display:none;position:absolute;top:-8px;right:-6px;width:22px;height:22px;border-radius:50%;background:var(--c);color:#06131f;font-size:.8rem;font-weight:900;line-height:22px;box-shadow:0 0 10px var(--c)}}
{_P} .onb-card.sel .ok{{display:block}}
/* NickName */
{_P} .st-key-onb_caixa{{position:relative}}
{_P} .st-key-onb_caixa iframe{{border-radius:12px;border:1px solid rgba(124,92,255,.6) !important;background:#0A0724}}
{_P} .st-key-onb_caixa [data-testid="stElementContainer"]:has(.onb-cnt){{position:absolute !important;right:14px;top:0;height:46px;display:flex;align-items:center;width:auto !important;z-index:4;pointer-events:none}}
{_P} .onb-cnt{{font-size:.8rem;font-weight:700;color:#B9B2E6}}{_P} .onb-cnt.max{{color:#FBBF24}}
{_P} .onb-msg{{display:flex;align-items:center;gap:6px;margin:6px 4px 0;font-size:.76rem;font-weight:600;line-height:1.25}}
{_P} .onb-msg.dica{{color:#C4BEEA;font-weight:500}}{_P} .onb-msg.ok{{color:#4ADE80}}{_P} .onb-msg.erro{{color:#FB7185}}
/* botão continuar */
{_P} .st-key-onb_continuar button{{width:100% !important;min-height:50px !important;border-radius:14px !important;font-weight:800 !important;border:1px solid #A78BFA !important;
  background:linear-gradient(180deg,#8B5CF6,#5B21B6) !important;box-shadow:0 0 18px rgba(139,92,246,.55),0 4px 0 #3B1480 !important}}
{_P} .st-key-onb_continuar button p{{color:#fff !important;font-size:1rem !important;font-weight:800 !important}}
{_P} .st-key-onb_continuar button:disabled{{opacity:.45 !important;box-shadow:none !important;filter:grayscale(.4)}}
{_P} .onb-nota{{text-align:center;font-size:.7rem;color:#8F88C4;margin:8px 0 0}}
"""

_ICO_USER = "<svg width='22' height='22' viewBox='0 0 24 24' fill='#A78BFA'><circle cx='12' cy='8' r='4.2'/><path d='M4 21c0-4.4 3.6-7 8-7s8 2.6 8 7z'/></svg>"
_ICO_LAPIS = "<svg width='22' height='22' viewBox='0 0 24 24' fill='#C084FC'><path d='M3 17.2V21h3.8L18 9.8 14.2 6 3 17.2zM20.7 7.1a1 1 0 0 0 0-1.4l-2.4-2.4a1 1 0 0 0-1.4 0l-1.9 1.9 3.8 3.8 1.9-1.9z'/></svg>"


def _marca() -> str:
    try:
        import marca
        return f"<div class='onb-marca'>{marca.wordmark_html(30)}</div>"
    except Exception:
        return "<div class='onb-marca'><b style='color:#fff'>TickerHunters</b></div>"


def _stepper(etapa: int) -> str:
    itens = []
    for i, nome in enumerate(O.ETAPAS, 1):
        marca_ = "✓" if i < etapa else str(i)
        itens.append(f"<div class='onb-st{' on' if i == etapa else ''}'><i>{marca_}</i>{html.escape(nome)}</div>")
    return "<div class='onb-steps'>" + "".join(itens) + "</div>"


def _hero() -> str:
    img = ART.uri("mascote")
    lobo = f"<img class='onb-lobo' src='{img}' alt='Mascote TickerHunters'>" if img else ""
    return (f"<div class='onb-hero'>{lobo}<div class='onb-h'>Vamos começar!</div>"
            "<div class='onb-sub'>Conte pra gente um pouco sobre você para personalizar sua experiência.</div></div>")


def _cartao(p: dict, sel: bool) -> str:
    img = ART.uri(p["id"])
    ic = f"<img src='{img}' alt=''>" if img else ""
    return (f"<div class='onb-card{' sel' if sel else ''}' style='--c:{p['cor']}'><div class='ok'>✓</div>{ic}"
            f"<b>{html.escape(p['titulo'])}</b><span>{html.escape(p['desc'])}</span></div>")


def _escolher(pid: str) -> None:
    st.session_state["onb_sel"] = pid


def _livre_fn(a):
    """Função 'este apelido (em minúsculas) está livre?' para a conta de quem está logado (o próprio apelido da pessoa conta como livre)."""
    return lambda k: banco.comp_apelido_livre(a, k)


def _reservar(a, nick: str) -> tuple[bool, str]:
    """Confere de novo (outra pessoa pode ter pegado nesse meio tempo) e reserva o NickName no cadastro do ranking, sem aceitar o termo."""
    estado, msg = O.verificar_nick(nick, _livre_fn(a))
    if estado != "ok":
        return False, msg
    try:
        atual = C.sanear_perfil(banco.comp_ordens_ler(a))
        if atual.get("aceite") and atual.get("apelido"):       # quem já participa do ranking mantém o apelido que tem
            return True, ""
        banco.comp_ordens_gravar(a, {**atual, "apelido": nick, "apelido_k": C.chave_apelido(nick)})
        st.session_state.pop("_comp_cache", None)
        return True, ""
    except Exception as e:
        banco.registrar_erro("onboarding.reservar", e)
        return False, "Não consegui salvar agora. Tente de novo em instantes."


def _campo_nick(inicial: str) -> str:
    try:
        from st_keyup import st_keyup
        return st_keyup("NickName", value=inicial, max_chars=O.MAX_NICK, key="onb_nick_txt", debounce=450,
                        placeholder="Ex.: InvestorX", label_visibility="collapsed") or ""
    except Exception:
        return st.text_input("NickName", value=inicial, max_chars=O.MAX_NICK, key="onb_nick_txt", placeholder="Ex.: InvestorX",
                             label_visibility="collapsed")


def _continuar(a, pid: str, nick: str, previa: bool) -> None:
    if previa:                                  # prévia do administrador: não grava nada
        st.session_state["_onb_adiar"] = True
        return
    ok, msg = _reservar(a, nick)
    if not ok:
        st.session_state["onb_erro"] = msg
        return
    st.session_state.pop("onb_erro", None)
    st.session_state["_onb_pos"] = True
    st.session_state["onb"] = {"v": O.VERSAO, "etapa": 2, "perfil": pid, "nick": nick, "concluido": False}


def _pos_tela1() -> None:
    """Confirmação depois da Tela 1 (substitui a tela inteira antes de abrir o app). As telas 2 e 3 ainda não existem: o onboarding NÃO é marcado como concluído."""
    ss = st.session_state
    onb = O.normalizar(ss.get("onb"))
    p = O.perfil(onb["perfil"]) or {}
    st.markdown(_CSS_MIN + _marca() + _stepper(1) + _hero().replace("Vamos começar!", "Tudo certo!").replace(
        "Conte pra gente um pouco sobre você para personalizar sua experiência.", "Seu perfil e seu NickName foram salvos."), unsafe_allow_html=True)
    st.markdown(f"<div class='onb-msg ok' style='justify-content:center'>✓ {html.escape(onb['nick'])} · {html.escape(p.get('titulo', ''))}</div>", unsafe_allow_html=True)
    with st.container(key="onb_continuar"):
        if st.button("Ir para o app  →", key="onb_ir", type="primary", width="stretch"):
            ss.pop("_onb_pos", None)
            st.rerun()
    st.stop()


_CSS_MIN = f"<style>{_CSS}</style>"


def mostrar(a, previa: bool = False) -> None:
    """Desenha a Tela 1 e interrompe a execução (st.stop). `previa`: modo de teste do administrador, não grava nada."""
    ss = st.session_state
    onb = O.normalizar(ss.get("onb"))
    if ss.get("_onb_pos"):
        _pos_tela1()
    if not onb["nick"] and a and not previa:  # conta antiga que já tem apelido no ranking: sugere o mesmo (o próprio apelido conta como livre)
        try:
            ap = C.sanear_perfil(banco.comp_ordens_ler(a)).get("apelido") or ""
            if ap:
                onb = {**onb, "nick": ap}
        except Exception:
            pass
    if "onb_sel" not in ss:
        ss["onb_sel"] = onb["perfil"]
    pid = ss["onb_sel"] if ss["onb_sel"] in O.IDS else ""
    st.markdown(_CSS_MIN + _marca() + _stepper(1) + _hero(), unsafe_allow_html=True)

    with st.container(key="onb_perfil"):
        st.markdown(f"<div class='onb-tit'>{_ICO_USER}<div><span class='t1'>Seu perfil de investidor</span>"
                    "<small>Isso nos ajuda a personalizar dicas, conteúdos e desafios.</small></div></div>", unsafe_allow_html=True)
        with st.container(key="onb_grade"):
            for p in O.PERFIS:
                with st.container(key=f"onbc_{p['id']}"):
                    st.markdown(_cartao(p, p["id"] == pid), unsafe_allow_html=True)
                    st.button(p["titulo"], key=f"onb_b_{p['id']}", on_click=_escolher, args=(p["id"],), width="stretch")

    if pid:
        st.markdown(f"<div class='onb-msg ok' style='margin:-2px 4px 8px'>✓ Perfil escolhido: {html.escape(O.perfil(pid)['titulo'])}</div>", unsafe_allow_html=True)
    with st.container(key="onb_nick"):
        st.markdown(f"<div class='onb-tit'>{_ICO_LAPIS}<div><span class='t1'>Seu NickName ou apelido</span>"
                    "<small>É como os outros jogadores vão te conhecer, inclusive no ranking.</small></div></div>", unsafe_allow_html=True)
        with st.container(key="onb_caixa"):
            nick = (_campo_nick(onb["nick"]) or "").strip()
            n = len(nick)
            st.markdown(f"<span class='onb-cnt{' max' if n >= O.MAX_NICK else ''}'>{n}/{O.MAX_NICK}</span>", unsafe_allow_html=True)
        livre = _livre_fn(a) if (a and not previa) else None
        chave = (nick, a.email if a else "")
        if ss.get("_onb_ck", (None,))[0] == chave:
            estado, msg = ss["_onb_ck"][1]
        else:
            estado, msg = O.verificar_nick(nick, livre)
            ss["_onb_ck"] = (chave, (estado, msg))
        if estado == "ok":
            st.markdown(f"<div class='onb-msg ok'>✓ {html.escape(msg)}</div>", unsafe_allow_html=True)
        elif estado in ("invalido", "ocupado", "erro"):
            st.markdown(f"<div class='onb-msg erro'>✕ {html.escape(msg)}</div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='onb-msg dica'>💡 Escolha um nome único: de 3 a 20 caracteres, sem espaços. Ele será exibido no ranking.</div>",
                        unsafe_allow_html=True)
    if ss.get("onb_erro"):
        st.error(ss["onb_erro"])
    pode = O.pode_continuar(pid, estado)
    with st.container(key="onb_continuar"):
        st.button("Continuar  →", key="onb_cont_btn", type="primary", disabled=not pode, width="stretch",
                  on_click=_continuar, args=(a, pid, nick, previa))
    if not pid:
        st.markdown("<p class='onb-nota'>Escolha um perfil e um NickName para continuar.</p>", unsafe_allow_html=True)
    elif previa:
        st.markdown("<p class='onb-nota'>Modo de prévia (administrador): nada é salvo.</p>", unsafe_allow_html=True)
    st.stop()


def deve_mostrar() -> tuple[bool, bool]:
    """(mostrar, prévia). Prévia: administrador abrindo o app com ?onb=1 vê a tela sem gravar nada."""
    ss = st.session_state
    u = usuarios.usuario()
    if not u:
        return False, False
    if ss.get("_onb_pos"):
        return True, False
    if ss.get("_onb_adiar"):
        return False, False
    try:
        if u.get("papel") == "admin" and st.query_params.get("onb") == "1":
            return True, True
    except Exception:
        pass
    c = ss.get("_conta") or {}
    return O.precisa(ss.get("onb"), c.get("criado_em", ""), bool(ss.get("_doc_novo"))), False


def rodar() -> None:
    """Chamado pelo app.py logo depois de carregar os dados da pessoa. Não faz nada se não for o caso."""
    mostrar_, previa = deve_mostrar()
    if mostrar_:
        mostrar(usuarios.ator(), previa)
