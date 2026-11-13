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
/* ---- Tela 2 ---- */
{_P} .onb-st.ok{{color:#9DEBFA}}{_P} .onb-st.ok i{{color:#22d3ee;border-color:#22d3ee;background:#0A2A3F;box-shadow:0 0 8px rgba(34,211,238,.45)}}
{_P} .onb-hero2{{text-align:center;margin:0 -6px}}
{_P} .onb-hero2 .onb-jor{{display:block;width:92%;max-width:420px;margin:0 auto;aspect-ratio:2.4/1;object-fit:cover;
  -webkit-mask-image:radial-gradient(ellipse closest-side at 50% 50%,#000 60%,transparent 100%);mask-image:radial-gradient(ellipse closest-side at 50% 50%,#000 60%,transparent 100%)}}
{_P} .onb-hero2 .onb-h{{margin:-10px 0 2px;font-size:1.85rem;font-weight:900;font-style:italic;color:#fff !important;-webkit-text-fill-color:#fff !important;text-shadow:0 2px 14px rgba(0,0,0,.7)}}
{_P} .onb-hero2 .onb-sub{{margin:0 8px 10px;font-size:.86rem;line-height:1.35;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .st-key-onb_int,{_P} .st-key-onb_niv{{background:linear-gradient(180deg,rgba(40,26,110,.55),rgba(14,10,46,.75));border:1px solid rgba(124,92,255,.45);border-radius:16px;padding:12px 10px !important;margin:0 0 10px;box-shadow:0 0 0 1px rgba(0,0,0,.3) inset,0 8px 26px rgba(0,0,0,.35)}}
{_P} .onb-tit img{{width:24px;height:24px;object-fit:contain}}
{_P} .st-key-onb_gi[data-testid="stVerticalBlock"],{_P} .st-key-onb_gi>[data-testid="stVerticalBlock"]{{display:grid !important;grid-template-columns:repeat(3,minmax(0,1fr)) !important;gap:8px !important}}
{_P} .st-key-onb_gn[data-testid="stVerticalBlock"],{_P} .st-key-onb_gn>[data-testid="stVerticalBlock"]{{gap:8px !important}}
{_P} [class*="st-key-onbi_"],{_P} [class*="st-key-onbn_"]{{position:relative;gap:0 !important;height:100%}}
{_P} [class*="st-key-onbi_"] [data-testid="stMarkdownContainer"],{_P} [class*="st-key-onbn_"] [data-testid="stMarkdownContainer"],
{_P} [class*="st-key-onbi_"] [data-testid="stElementContainer"]:has(.onb-ic),{_P} [class*="st-key-onbn_"] [data-testid="stElementContainer"]:has(.onb-nv){{margin:0 !important;height:100%}}
{_P} [class*="st-key-onbi_"] [data-testid="stElementContainer"]:has(button),{_P} [class*="st-key-onbn_"] [data-testid="stElementContainer"]:has(button){{position:absolute !important;inset:0;z-index:3;width:100% !important;height:100% !important}}
{_P} [class*="st-key-onbi_"] button,{_P} [class*="st-key-onbn_"] button{{width:100% !important;height:100% !important;min-height:100% !important;opacity:0;cursor:pointer;padding:0 !important}}
{_P} .onb-ic{{position:relative;height:100%;box-sizing:border-box;display:flex;align-items:center;gap:7px;min-height:50px;padding:6px 8px;border-radius:14px;
  background:linear-gradient(160deg,#17114A,#0E0A2C 85%);border:1.5px solid rgba(124,92,255,.42);transition:transform .1s,box-shadow .1s}}
{_P} .onb-ic img{{width:28px;height:28px;object-fit:contain;flex:0 0 auto;border-radius:7px}}
{_P} .onb-ic b{{font-size:.74rem;color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800;line-height:1.1;min-width:0;overflow-wrap:anywhere}}
{_P} .onb-ic.sel,{_P} .onb-nv.sel{{border:2px solid #22d3ee;background:linear-gradient(160deg,#103A66,#0E1E4A 85%);box-shadow:0 0 14px rgba(34,211,238,.6),0 0 0 1px rgba(34,211,238,.35) inset;transform:translateY(-1px)}}
{_P} .onb-ic .ok,{_P} .onb-nv .ok{{display:none;position:absolute;top:-8px;right:-6px;width:20px;height:20px;border-radius:50%;background:#22d3ee;color:#06131f;font-size:.74rem;font-weight:900;line-height:20px;text-align:center;box-shadow:0 0 10px #22d3ee}}
{_P} .onb-ic.sel .ok,{_P} .onb-nv.sel .ok{{display:block}}
{_P} .onb-nv{{position:relative;display:flex;align-items:center;gap:12px;box-sizing:border-box;min-height:64px;padding:8px 12px;border-radius:14px;
  background:linear-gradient(160deg,#17114A,#0E0A2C 85%);border:1.5px solid rgba(124,92,255,.42);transition:transform .1s,box-shadow .1s}}
{_P} .onb-nv img{{width:40px;height:40px;object-fit:contain;flex:0 0 auto;border-radius:9px}}
{_P} .onb-nv b{{display:block;font-size:.92rem;color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800;line-height:1.15}}
{_P} .onb-nv span{{display:block;font-size:.74rem;color:#C4BEEA !important;-webkit-text-fill-color:#C4BEEA !important;line-height:1.25}}
@media (max-width:380px){{{_P} .onb-ic{{flex-direction:column;justify-content:center;text-align:center;gap:3px;min-height:64px}}}}
/* boas-vindas */
@keyframes onbpop{{0%{{opacity:0;transform:scale(.86) translateY(10px)}}60%{{opacity:1;transform:scale(1.03)}}100%{{opacity:1;transform:none}}}}
{_P} .onb-anim .onb-lobo,{_P} .onb-anim .onb-h{{animation:onbpop .7s ease-out both}}{_P} .onb-anim .onb-sub{{animation:onbpop .9s ease-out both}}
@media (prefers-reduced-motion:reduce){{{_P} .onb-anim *{{animation:none !important}}}}
{_P} .onb-resumo{{background:linear-gradient(180deg,rgba(40,26,110,.55),rgba(14,10,46,.75));border:1px solid rgba(124,92,255,.45);border-radius:16px;padding:8px 14px;margin:4px 0 12px}}
{_P} .onb-res{{display:flex;justify-content:space-between;gap:10px;padding:7px 0;border-bottom:1px solid rgba(124,92,255,.18);font-size:.84rem}}
{_P} .onb-res:last-child{{border-bottom:0}}{_P} .onb-res span{{color:#B9B2E6 !important;-webkit-text-fill-color:#B9B2E6 !important}}
{_P} .onb-res b{{color:#fff !important;-webkit-text-fill-color:#fff !important;text-align:right}}
/* navegação fixa embaixo */
{_P} .st-key-onb_nav2{{position:sticky;bottom:0;z-index:20;padding:12px 0 6px;margin-top:6px;background:linear-gradient(180deg,rgba(7,5,22,0),#070516 38%)}}
{_P} .st-key-onb_nav2[data-testid="stVerticalBlock"],{_P} .st-key-onb_nav2>[data-testid="stVerticalBlock"]{{display:grid !important;grid-template-columns:1fr 1.6fr !important;gap:10px !important}}
{_P} .st-key-onb_nav2 button{{width:100% !important;min-height:50px !important;border-radius:14px !important;font-weight:800 !important}}
{_P} .st-key-onb_nav2 button[data-testid^="stBaseButton-secondary"]{{background:#120C36 !important;border:1.5px solid rgba(167,139,250,.7) !important}}
{_P} .st-key-onb_nav2 button[data-testid^="stBaseButton-secondary"] p{{color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important;font-size:.98rem !important;font-weight:800 !important}}
{_P} .st-key-onb_nav2 button[data-testid^="stBaseButton-primary"]{{border:1px solid #A78BFA !important;background:linear-gradient(180deg,#8B5CF6,#5B21B6) !important;box-shadow:0 0 18px rgba(139,92,246,.55),0 4px 0 #3B1480 !important}}
{_P} .st-key-onb_nav2 button[data-testid^="stBaseButton-primary"] p{{color:#fff !important;-webkit-text-fill-color:#fff !important;font-size:1rem !important;font-weight:800 !important}}
{_P} .st-key-onb_nav2 button:disabled{{opacity:.45 !important;box-shadow:none !important;filter:grayscale(.4)}}
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
        cls = " on" if i == etapa else (" ok" if i < etapa else "")
        itens.append(f"<div class='onb-st{cls}'><i>{marca_}</i>{html.escape(nome)}</div>")
    return "<div class='onb-steps'>" + "".join(itens) + "</div>"


def _hero(titulo: str = "Vamos começar!", sub: str = "Conte pra gente um pouco sobre você para personalizar sua experiência.", anim: bool = False) -> str:
    img = ART.uri("mascote")
    lobo = f"<img class='onb-lobo' src='{img}' alt='Mascote TickerHunters'>" if img else ""
    return (f"<div class='onb-hero{' onb-anim' if anim else ''}'>{lobo}<div class='onb-h'>{html.escape(titulo)}</div>"
            f"<div class='onb-sub'>{html.escape(sub)}</div></div>")


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


def _estado(previa: bool) -> dict:
    return O.normalizar(st.session_state.get("onb_prev" if previa else "onb"))


def _gravar(previa: bool, novo: dict, concluido: bool = False) -> None:
    """Prévia do administrador guarda só na sessão (`onb_prev` não é salvo); o fluxo real grava em `onb`, que vai junto com os dados da conta."""
    st.session_state["onb_prev" if previa else "onb"] = {**novo, "v": O.VERSAO, "concluido": concluido}


def _continuar(a, pid: str, nick: str, previa: bool) -> None:
    if not previa:
        ok, msg = _reservar(a, nick)
        if not ok:
            st.session_state["onb_erro"] = msg
            return
    st.session_state.pop("onb_erro", None)
    _gravar(previa, {**_estado(previa), "etapa": 2, "perfil": pid, "nick": nick})      # mantém interesses e nível já escolhidos


def _pos(previa: bool) -> None:
    """Boas-vindas depois de concluir o onboarding (tela cheia, com uma animação discreta); o botão leva à tela inicial."""
    ss = st.session_state
    onb = _estado(previa)
    p = O.perfil(onb["perfil"]) or {}
    nv = next((n["titulo"] for n in O.NIVEIS if n["id"] == onb["nivel"]), "")
    ob = next((o["titulo"] for o in O.OBJETIVOS if o["id"] == onb["objetivo"]), "")
    st.markdown(_CSS_MIN + _marca() + _stepper(4) + _hero(f"Pronto para caçar, {onb['nick'] or 'jogador'}!", "Seu perfil foi configurado com sucesso. "
                "Agora você faz parte do universo TickerHunters!", anim=True), unsafe_allow_html=True)
    linhas = "".join(f"<div class='onb-res'><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>" for k, v in
                     (("NickName", onb["nick"]), ("Perfil", p.get("titulo", "")), ("Nível", nv), ("Objetivo", ob),
                      ("Interesses", f"{len(onb['interesses'])} escolhido(s)")) if v)
    st.markdown(f"<div class='onb-resumo'>{linhas}</div>", unsafe_allow_html=True)
    with st.container(key="onb_continuar"):
        if st.button("Ir para a tela inicial  →", key="onb_ir", type="primary", width="stretch"):
            ss.pop("_onb_pos", None)
            if previa:
                ss["_onb_adiar"] = True
            ss["_nav_pend"] = "inicio"
            st.rerun()
    st.stop()


# ------------------------------------------------------------------ Tela 2 — Sua Jornada
def _alt_interesse(iid: str) -> None:
    st.session_state["onb_int"] = O.alternar_interesse(st.session_state.get("onb_int"), iid)


def _set_nivel(nid: str) -> None:
    st.session_state["onb_niv"] = nid


def _salvar2(previa: bool, etapa: int) -> None:
    ss = st.session_state
    _gravar(previa, {**_estado(previa), "etapa": etapa, "interesses": list(ss.get("onb_int") or []), "nivel": ss.get("onb_niv") or ""})


def _voltar2(previa: bool) -> None:
    _salvar2(previa, 1)                         # volta à Tela 1 guardando o que já foi marcado


def _continuar2(previa: bool) -> None:
    ss = st.session_state
    if not O.pode_continuar_2(ss.get("onb_int"), ss.get("onb_niv")):
        return
    _salvar2(previa, 3)


def _img(nome: str) -> str:
    u = ART.uri(nome)
    return f"<img src='{u}' alt=''>" if u else ""


def _tela2(previa: bool) -> None:
    ss = st.session_state
    onb = _estado(previa)
    if "onb_int" not in ss:
        ss["onb_int"] = onb["interesses"]
    if "onb_niv" not in ss:
        ss["onb_niv"] = onb["nivel"]
    ints = [i for i in (ss.get("onb_int") or []) if i in O.IDS_INT]
    niv = ss.get("onb_niv") if ss.get("onb_niv") in O.IDS_NIV else ""
    jor = ART.uri("jornada")
    img_j = f"<img class='onb-jor' src='{jor}' alt=''>" if jor else ""
    topo = (f"<div class='onb-hero2'>{img_j}<div class='onb-h'>Sua Jornada</div>"
            "<div class='onb-sub'>Vamos descobrir o que você gosta de explorar no mercado.</div></div>")
    st.markdown(_CSS_MIN + _marca() + _stepper(2) + topo, unsafe_allow_html=True)

    with st.container(key="onb_int"):
        st.markdown(f"<div class='onb-tit'>{_img('estrela')}<div><span class='t1'>O que desperta seu interesse?</span>"
                    "<small>Escolha uma ou mais opções.</small></div></div>", unsafe_allow_html=True)
        with st.container(key="onb_gi"):
            for it in O.INTERESSES:
                with st.container(key=f"onbi_{it['id']}"):
                    sel = it["id"] in ints
                    st.markdown(f"<div class='onb-ic{' sel' if sel else ''}'><div class='ok'>✓</div>{_img(it['id'])}<b>{html.escape(it['titulo'])}</b></div>",
                                unsafe_allow_html=True)
                    st.button(it["titulo"], key=f"onb_i_{it['id']}", on_click=_alt_interesse, args=(it["id"],), width="stretch")
        if ints:
            st.markdown(f"<div class='onb-msg ok' style='margin-top:8px'>✓ {len(ints)} selecionado(s)</div>", unsafe_allow_html=True)

    with st.container(key="onb_niv"):
        st.markdown(f"<div class='onb-tit'>{_img('chapeu')}<div><span class='t1'>Como você se considera no mercado financeiro?</span>"
                    "<small>Escolha apenas uma opção.</small></div></div>", unsafe_allow_html=True)
        with st.container(key="onb_gn"):
            for n in O.NIVEIS:
                with st.container(key=f"onbn_{n['id']}"):
                    st.markdown(f"<div class='onb-nv{' sel' if n['id'] == niv else ''}'><div class='ok'>✓</div>{_img('niv_' + n['id'])}"
                                f"<div><b>{html.escape(n['titulo'])}</b><span>{html.escape(n['desc'])}</span></div></div>", unsafe_allow_html=True)
                    st.button(n["titulo"], key=f"onb_n_{n['id']}", on_click=_set_nivel, args=(n["id"],), width="stretch")

    pode = O.pode_continuar_2(ints, niv)
    with st.container(key="onb_nav2"):
        st.button("←  Voltar", key="onb_voltar", on_click=_voltar2, args=(previa,), width="stretch")
        st.button("Continuar  →", key="onb_cont2", type="primary", disabled=not pode, on_click=_continuar2, args=(previa,), width="stretch")
    if not pode:
        st.markdown("<p class='onb-nota'>Escolha pelo menos um interesse e seu nível para continuar.</p>", unsafe_allow_html=True)
    elif previa:
        st.markdown("<p class='onb-nota'>Modo de prévia (administrador): nada é salvo.</p>", unsafe_allow_html=True)
    st.stop()


# ------------------------------------------------------------------ Tela 3 — Seu objetivo
def _set_obj(oid: str) -> None:
    st.session_state["onb_obj"] = oid


def _voltar3(previa: bool) -> None:
    _gravar(previa, {**_estado(previa), "etapa": 2, "objetivo": st.session_state.get("onb_obj") or ""})


def _concluir(previa: bool) -> None:
    ss = st.session_state
    if not O.pode_concluir(ss.get("onb_obj")):
        return
    _gravar(previa, {**_estado(previa), "etapa": 3, "objetivo": ss["onb_obj"]}, concluido=True)     # só registra preferências: sem moedas, XP ou missões
    ss["_onb_pos"] = "prev" if previa else "real"


def _tela3(previa: bool) -> None:
    ss = st.session_state
    onb = _estado(previa)
    if "onb_obj" not in ss:
        ss["onb_obj"] = onb["objetivo"]
    obj = ss.get("onb_obj") if ss.get("onb_obj") in O.IDS_OBJ else ""
    st.markdown(_CSS_MIN + _marca() + _stepper(3) + _hero("Qual é o seu objetivo?", "Queremos ajudar você a evoluir no mercado financeiro. Qual caminho deseja seguir?"),
                unsafe_allow_html=True)
    with st.container(key="onb_niv"):
        st.markdown(f"<div class='onb-tit'>{_img('estrela')}<div><span class='t1'>O que você quer conquistar no TickerHunters?</span>"
                    "<small>Escolha apenas um objetivo principal.</small></div></div>", unsafe_allow_html=True)
        with st.container(key="onb_gn"):
            for o in O.OBJETIVOS:
                with st.container(key=f"onbn_{o['id']}"):
                    st.markdown(f"<div class='onb-nv{' sel' if o['id'] == obj else ''}'><div class='ok'>✓</div>{_img(o['icone'])}"
                                f"<div><b>{html.escape(o['titulo'])}</b><span>{html.escape(o['desc'])}</span></div></div>", unsafe_allow_html=True)
                    st.button(o["titulo"], key=f"onb_o_{o['id']}", on_click=_set_obj, args=(o["id"],), width="stretch")
    with st.container(key="onb_nav2"):
        st.button("←  Voltar", key="onb_voltar3", on_click=_voltar3, args=(previa,), width="stretch")
        st.button("Concluir e entrar  →", key="onb_cont3", type="primary", disabled=not O.pode_concluir(obj), on_click=_concluir, args=(previa,), width="stretch")
    if not obj:
        st.markdown("<p class='onb-nota'>Escolha seu objetivo para concluir.</p>", unsafe_allow_html=True)
    elif previa:
        st.markdown("<p class='onb-nota'>Modo de prévia (administrador): nada é salvo.</p>", unsafe_allow_html=True)
    st.stop()


_CSS_MIN = f"<style>{_CSS}</style>"


def mostrar(a, previa: bool = False) -> None:
    """Desenha a Tela 1 e interrompe a execução (st.stop). `previa`: modo de teste do administrador, não grava nada."""
    ss = st.session_state
    if ss.get("_onb_pos"):
        _pos(previa)
    onb = _estado(previa)
    if onb["etapa"] == 3:
        _tela3(previa)
    if onb["etapa"] == 2:
        _tela2(previa)
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
        return True, ss.get("_onb_pos") == "prev"
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
