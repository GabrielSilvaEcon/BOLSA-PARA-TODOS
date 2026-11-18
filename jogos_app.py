"""Central de Jogos · telas (Streamlit). Reúne o Trade Battle e o Ticker Battle sem recriar nenhum dos dois.

O que é de cada lugar (nada duplicado):
 · Os jogos continuam nas próprias páginas (trader_battle_app, battle_app/battle_online_app), com as mesmas regras.
 · Placar e rankings: `jogos.py` (lógica pura) + documento `jogos_placar` de cada conta (banco.jogos_placar_*). Leitura de todos
   numa consulta (banco.sis_comp_todos) com cache de 60 s; nunca uma consulta por participante.
 · Amigos: as ligas de amigos por convite que o app já tem (competicao_ligas + banco.comp_liga_*), com os limites do plano.
 · Eventos e recompensas: só LEEM o que já existe (desafio da semana e missões de `jogar`, missões do Wallet Game, baú diário,
   campanhas e extrato das TickerCoins, XP dos jogos). Resgates e compras continuam nas telas de origem (Central de missões e Loja).
 · Navegação: o botão Jogar da barra de baixo abre esta Central; os botões daqui usam o mesmo `_nav_pend` do app.
"""
from __future__ import annotations

import html
import time
from datetime import datetime, timedelta, timezone

import streamlit as st

import arte_battle as ARTB
import arte_conta as AC
import arte_trader as ART
import banco
import competicao_ligas as L
import jogos as J
import usuarios

_P = "html body .stApp.stApp.stApp"
_e = html.escape
BRT = timezone(timedelta(hours=-3))
VERDE, ROXO, OURO = "#34E85E", "#8B6CFF", "#F2B84B"
SECOES = (("jogos", "Central", ":material/sports_esports:"), ("trader", "Trade", ":material/show_chart:"), ("battle", "Ticker", ":material/style:"),
          ("jogos-ranking", "Ranking", ":material/emoji_events:"), ("jogos-amigos", "Amigos", ":material/group:"),
          ("jogos-eventos", "Eventos", ":material/redeem:"))
PAGINAS_DA_CENTRAL = ("jogos", "jogos-ranking", "jogos-amigos", "jogos-eventos")
_AV_COR = ("", "hue-rotate(185deg) saturate(1.2)", "hue-rotate(95deg)", "hue-rotate(260deg)", "hue-rotate(320deg) saturate(1.3)")

CSS = "<style>" + "".join(l.strip() for l in f"""
{_P} .jg-cab{{display:flex;align-items:center;gap:10px;margin:-4px 0 6px;padding:10px 12px;border-radius:20px;border:2px solid rgba(242,184,75,.55);
  background:radial-gradient(120% 90% at 0 0,rgba(242,184,75,.22),transparent 60%),linear-gradient(160deg,#241A86,#0E0840);box-shadow:0 0 18px rgba(139,108,255,.35)}}
{_P} .jg-cab img{{width:78px;height:auto;filter:drop-shadow(0 0 10px rgba(255,201,60,.5))}}
{_P} .jg-cab .t{{flex:1;min-width:0}}
{_P} .jg-cab b{{display:block;font-weight:900;font-style:italic;font-size:1.35rem;line-height:1.05;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important;text-shadow:0 0 12px rgba(255,201,60,.45)}}
{_P} .jg-cab small{{display:block;font-size:.76rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .jg-tc{{flex:none;display:flex;align-items:center;gap:5px;padding:5px 10px;border-radius:999px;border:1.5px solid {OURO};background:rgba(242,184,75,.14);font-weight:900;font-size:.9rem;color:#FFE3A3 !important;-webkit-text-fill-color:#FFE3A3 !important}}
{_P} .st-key-jg_nav,{_P} .st-key-jg_nav > div:only-child{{display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;overflow-x:auto;gap:6px !important;scrollbar-width:none;padding-bottom:2px}}
{_P} .st-key-jg_nav::-webkit-scrollbar{{display:none}}
{_P} .st-key-jg_nav [data-testid="stElementContainer"],{_P} .st-key-jg_nav .stButton{{flex:0 0 auto !important;width:auto !important}}
{_P} .st-key-jg_nav button{{min-height:34px !important;padding:0 12px !important;border-radius:999px !important;white-space:nowrap;font-size:.8rem !important;font-weight:800 !important}}
{_P} .st-key-jg_nav button[data-testid="stBaseButton-primary"]{{background:linear-gradient(90deg,#7C5CFF,#B06BFF) !important;border-color:#B9A8FF !important;box-shadow:0 0 12px rgba(139,108,255,.6) !important}}
{_P} .jg-sec{{display:flex;align-items:center;gap:8px;margin:12px 0 4px;font-weight:900;font-size:1rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .jg-sec small{{margin-left:auto;font-weight:600;font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .jg-card{{padding:10px 12px;border-radius:18px;border:2px solid #5B4BD6;background:linear-gradient(160deg,#1B1470,#0E0840);box-shadow:0 0 12px rgba(91,75,214,.4);margin:4px 0}}
{_P} .jg-card b{{color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .jg-card p{{margin:2px 0 0;font-size:.8rem;line-height:1.35;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .jg-vazio{{text-align:center;padding:16px 12px;border-radius:18px;border:1.5px dashed rgba(139,108,255,.55);font-size:.86rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .st-key-jg_jogos [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap !important;gap:.5rem !important}}
{_P} .st-key-jg_jogos [data-testid="stColumn"]{{flex:1 1 0 !important;width:auto !important;min-width:0 !important}}
{_P} .st-key-jg_atalhos,{_P} .st-key-jg_atalhos > div:only-child{{display:flex !important;flex-direction:row !important;flex-wrap:nowrap !important;gap:.5rem !important}}
{_P} .st-key-jg_atalhos [data-testid="stElementContainer"]{{flex:1 1 0 !important;width:auto !important;min-width:0 !important}}
{_P} .jg-jogo{{position:relative;border-radius:20px 20px 0 0;overflow:hidden;border:2px solid var(--c);border-bottom:0;background:#0A0630}}
{_P} .jg-jogo img{{display:block;width:100%;aspect-ratio:2/1;object-fit:cover}}
{_P} .jg-jogo span{{display:block;padding:6px 8px 8px;font-size:.7rem;line-height:1.3;font-weight:700;background:linear-gradient(160deg,#1B1470,#0E0840);color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .st-key-jg_jogos [data-testid="stColumn"] > div{{gap:0 !important}}
{_P} .st-key-jg_jogos :is([data-testid="stMarkdown"],[data-testid="stMarkdownContainer"],[data-testid="stElementContainer"]){{margin-bottom:0 !important}}
{_P} :is(.st-key-jg_ir_trade,.st-key-jg_ir_ticker) button{{border-radius:0 0 20px 20px !important;min-height:44px !important;font-weight:900 !important;border:2px solid var(--c) !important;border-top:0 !important}}
{_P} .st-key-jg_ir_trade{{--c:{VERDE}}}{_P} .st-key-jg_ir_ticker{{--c:{ROXO}}}
{_P} .st-key-jg_ir_trade button{{background:linear-gradient(90deg,#2EE86B,#14C9B5) !important;box-shadow:0 0 14px rgba(46,232,107,.45) !important}}
{_P} .st-key-jg_ir_trade button :is(p,span){{color:#06240F !important;-webkit-text-fill-color:#06240F !important}}
{_P} .st-key-jg_ir_ticker button{{background:linear-gradient(90deg,#7C5CFF,#B06BFF) !important;box-shadow:0 0 14px rgba(139,108,255,.55) !important}}
{_P} .st-key-jg_ir_ticker button :is(p,span){{color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .jg-dest{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:6px}}
{_P} .jg-dest div{{text-align:center;padding:8px 4px;border-radius:14px;border:1.5px solid rgba(139,108,255,.5);background:linear-gradient(160deg,#241A86,#150F55)}}
{_P} .jg-dest small{{display:block;font-size:.66rem;font-weight:700;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .jg-dest b{{display:block;font-size:1.15rem;font-weight:900;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} .jg-dest i{{display:block;font-style:normal;font-size:.66rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .jg-bar{{height:8px;border-radius:99px;background:rgba(255,255,255,.12);overflow:hidden;margin-top:6px}}
{_P} .jg-bar i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#2EE86B,#14C9B5)}}
{_P} .jg-des{{display:flex;align-items:center;gap:10px;padding:10px 12px;border-radius:18px;border:2px solid {OURO};
  background:radial-gradient(120% 90% at 100% 0,rgba(242,184,75,.25),transparent 60%),linear-gradient(160deg,#2A1F8E,#120C48);box-shadow:0 0 14px rgba(242,184,75,.3)}}
{_P} .jg-des .ic{{font-size:1.8rem}}
{_P} .jg-des .t{{flex:1;min-width:0}}
{_P} .jg-des b{{display:block;font-weight:900;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
{_P} .jg-des small{{display:block;font-size:.76rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .jg-des em{{font-style:normal;font-weight:900;font-size:.85rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .st-key-jg_atalhos button{{min-height:52px !important;border-radius:16px !important;font-weight:800 !important;font-size:.8rem !important}}
{_P} .st-key-jg_atalhos button > div > span{{flex-direction:column !important;gap:2px !important}}
{_P} .st-key-jg_atalhos button [data-testid="stIconMaterial"]{{font-size:1.4rem !important;color:#C9A8FF !important}}
{_P} .jg-podio{{display:grid;grid-template-columns:1fr 1.15fr 1fr;align-items:end;gap:6px;margin:6px 0 4px}}
{_P} .jg-podio > div{{text-align:center;min-width:0}}
{_P} .jg-podio .av{{width:52px;height:52px;margin:0 auto 4px;border-radius:50%;overflow:hidden;background:#1B1545;box-shadow:0 0 0 3px var(--c),0 0 14px var(--c)}}
{_P} .jg-podio .p1 .av{{width:64px;height:64px}}
{_P} .jg-podio .av img{{width:100%;height:100%;object-fit:cover}}
{_P} .jg-podio .nm{{font-size:.76rem;font-weight:800;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .jg-podio .vl{{font-size:.72rem;font-weight:800;color:#FFE3A3 !important;-webkit-text-fill-color:#FFE3A3 !important}}
{_P} .jg-podio .base{{margin-top:4px;border-radius:12px 12px 0 0;font-weight:900;font-size:1.6rem;color:#fff !important;-webkit-text-fill-color:#fff !important;
  background:linear-gradient(180deg,var(--c),rgba(20,12,64,.9));box-shadow:0 0 14px var(--c)}}
{_P} .jg-podio .p1{{--c:#E0A21A}}{_P} .jg-podio .p2{{--c:#9EA3C6}}{_P} .jg-podio .p3{{--c:#B0612A}}
{_P} .jg-podio .p1 .base{{height:74px;line-height:74px}}{_P} .jg-podio .p2 .base{{height:54px;line-height:54px}}{_P} .jg-podio .p3 .base{{height:42px;line-height:42px}}
{_P} .jg-lin{{display:grid;grid-template-columns:30px 30px minmax(0,1fr) auto 34px;gap:8px;align-items:center;padding:7px 8px;border-top:1px solid rgba(255,255,255,.08);font-size:.88rem;font-weight:700;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .jg-lin .ps{{font-weight:900;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .jg-lin .av{{width:30px;height:30px;border-radius:50%;overflow:hidden;background:#1B1545;box-shadow:0 0 0 1.5px #6C5CFF}}
{_P} .jg-lin .av img{{width:100%;height:100%;object-fit:cover}}
{_P} .jg-lin .nm{{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
{_P} .jg-lin .nm small{{display:block;font-size:.66rem;font-weight:600;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .jg-lin b{{font-variant-numeric:tabular-nums;color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}
{_P} .jg-lin b.neg{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
{_P} .jg-lin .vr{{font-size:.72rem;font-weight:900;text-align:right}}
{_P} .jg-lin .vr.up{{color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}{_P} .jg-lin .vr.dn{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
{_P} .jg-lin .vr.eq{{color:#8E87D8 !important;-webkit-text-fill-color:#8E87D8 !important}}
{_P} .jg-lin.eu{{border:2px solid {OURO};border-radius:12px;background:linear-gradient(90deg,rgba(242,184,75,.28),rgba(242,184,75,.06));box-shadow:0 0 12px rgba(242,184,75,.35)}}
{_P} .jg-lista{{padding:4px 6px;border-radius:18px;border:2px solid #5B4BD6;background:linear-gradient(160deg,#17114A,#0A0720 90%)}}
{_P} .jg-lista .jg-lin:first-child{{border-top:0}}
{_P} .jg-faixa{{display:flex;align-items:center;gap:10px;padding:8px 12px;border-radius:16px;border:2px solid #5B4BD6;background:linear-gradient(160deg,#241A86,#150F55);box-shadow:0 0 10px rgba(91,75,214,.4)}}
{_P} .jg-faixa .av{{flex:none;width:34px;height:34px;border-radius:50%;overflow:hidden;box-shadow:0 0 0 2px {VERDE}}}
{_P} .jg-faixa .av img{{width:100%;height:100%;object-fit:cover}}
{_P} :is(.jg-podio,.jg-lin,.jg-faixa) .av:has(.thav){{overflow:visible;box-shadow:none;background:none}}

{_P} .jg-faixa .ps{{font-weight:900;font-size:1rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .jg-faixa .nm{{flex:1;min-width:0;font-weight:700;font-size:.86rem;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .jg-faixa b{{font-weight:900;color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}
{_P} .jg-hist{{display:flex;justify-content:space-between;gap:8px;padding:6px 4px;border-top:1px solid rgba(255,255,255,.08);font-size:.8rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .jg-hist b.up{{color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}{_P} .jg-hist b.dn{{color:#FF6B87 !important;-webkit-text-fill-color:#FF6B87 !important}}
{_P} .jg-hist b.eq{{color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .jg-rec{{display:flex;align-items:center;gap:10px;padding:8px 10px;border-top:1px solid rgba(255,255,255,.08);font-size:.82rem;color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .jg-rec:first-child{{border-top:0}}
{_P} .jg-rec .ic{{font-size:1.25rem}}
{_P} .jg-rec .t{{flex:1;min-width:0}}
{_P} .jg-rec small{{display:block;font-size:.68rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .jg-rec b{{font-weight:900;white-space:nowrap;color:#6BFF8A !important;-webkit-text-fill-color:#6BFF8A !important}}
{_P} .jg-rec b.xp{{color:#C9A8FF !important;-webkit-text-fill-color:#C9A8FF !important}}
{_P} .jg-cod{{font-family:ui-monospace,monospace;font-weight:900;font-size:1.25rem;letter-spacing:2px;color:#FFC93C !important;-webkit-text-fill-color:#FFC93C !important}}
""".splitlines()) + "</style>"


# ------------------------------------------------------------------ navegação e identidade
def _ir(url_path: str, **estado) -> None:
    """Callback dos botões: guarda o estado pedido e navega pelo mesmo `_nav_pend` do app (resolvido logo depois do menu)."""
    for k, v in estado.items():
        st.session_state[k] = v
    st.session_state["_nav_pend"] = url_path


def navegacao(atual: str) -> None:
    """Navegação interna da Central (Central · Trade · Ticker · Ranking · Amigos · Eventos), também usada nas telas iniciais dos jogos."""
    st.markdown(CSS, unsafe_allow_html=True)
    with st.container(key="jg_nav"):                      # faixa rolável de lado (sem colunas: a regra global quebraria em várias linhas)
        for url, rot, ic in SECOES:
            st.button(rot, key=f"jg_nav_{url}", icon=ic, type="primary" if url == atual else "secondary", on_click=_ir, args=(url,))


def _ator():
    try:
        return usuarios.ator()
    except Exception:
        return None


def _email() -> str | None:
    try:
        return (usuarios.usuario() or {}).get("email")
    except Exception:
        return None


def _apelido() -> str:
    """Nome público nos rankings: o NickName do cadastro (único e já público). Nunca e-mail."""
    try:
        import onboarding as O
        return O.normalizar(st.session_state.get("onb"))["nick"] or "Jogador"
    except Exception:
        return "Jogador"


def _agora() -> datetime:
    return datetime.now(BRT)


def _hoje() -> str:
    return _agora().strftime("%Y-%m-%d")


def _avatar(h: str = "", eu: bool = False, tamanho: int = 52) -> str:
    """Avatar equipado do jogador (Coleção de Avatares, com a moldura da raridade). O e-mail só é usado aqui no servidor."""
    try:
        import perfis_app as PA
        if eu:
            m = PA.meu_avatar()
            return PA.avatar_html(m["id"], m["foto"], tamanho)
        email = _emails_por_hash().get(h)
        if email:
            return PA.avatar_html_email(email, tamanho)
        return PA.avatar_html("raposa", "", tamanho)
    except Exception:
        return f"<img src='{AC.uri('avatar')}' alt=''>"


@st.cache_data(ttl=60, show_spinner=False)
def _emails_por_hash() -> dict[str, str]:
    """{hash do placar: e-mail} (só no servidor; nunca vai para a tela)."""
    return {J.hash_conta(r["email"]): r["email"] for r in _placares()}


def _fmt_valor(jogo: str, v) -> str:
    if jogo == J.TRADE:
        s = f"{abs(v):,.1f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return ("+" if v > 0 else "−" if v < 0 else "") + s + " pts"
    n = int(v)
    return f"{n} vitória{'s' if n != 1 else ''}"


def _cabecalho(titulo: str, sub: str) -> None:
    try:
        import tickercoins_app as TCA
        tc = TCA.saldo_atual()
    except Exception:
        tc = None
    chip = f"<div class='jg-tc'>🪙 {tc:,}</div>".replace(",", ".") if tc is not None else ""
    largura = f"<style>{_P} [data-testid='stMainBlockContainer'],{_P} .block-container{{max-width:720px !important}}</style>"   # telas da Central: coluna confortável também no computador
    st.markdown(CSS + largura + f"<div class='jg-cab'><img src='{ART.uri('trofeu')}' alt=''><div class='t'><b>{_e(titulo)}</b><small>{_e(sub)}</small></div>{chip}</div>",
                unsafe_allow_html=True)


# ------------------------------------------------------------------ placar: leitura (uma consulta, cache) e gravação (só o servidor)
@st.cache_data(ttl=60, show_spinner=False)
def _placares() -> list[dict]:
    return banco.sis_comp_todos(J.CH_PLACAR)


@st.cache_data(ttl=60, show_spinner=False)
def _ligas_todas() -> list[dict]:
    return banco.sis_comp_todos(L.CH_LIGAS)


@st.cache_data(ttl=60, show_spinner=False)
def _usuarios_por_hash() -> dict[str, str]:
    """{hash do placar: nome de usuário atual} para levar do ranking ao perfil (o apelido do placar pode estar desatualizado)."""
    import perfis as PF
    out, com_perfil = {}, set()
    for r in banco.sis_comp_todos("perfil_jogador"):
        p = PF.sanear(r["dados"])
        if p["usuario"]:
            com_perfil.add(r["email"])
            if p["privacidade"]["visivel"] != "ninguem":
                out[J.hash_conta(r["email"])] = p["usuario"]
    criados = 0
    for r in _placares():                     # quem joga mas ainda não abriu o perfil: ganha o perfil básico do próprio NickName público
        ap = J.sanear(r["dados"])["apelido"]
        if r["email"] in com_perfil or not ap or ap.lower() == "jogador" or criados >= 50:
            continue
        try:
            if banco.sis_perfil_padrao(r["email"], ap):
                criados += 1
                out[J.hash_conta(r["email"])] = PF.inicial(ap)["usuario"]
        except Exception as e:
            banco.registrar_erro("jogos_app.perfil_padrao", e)
    return out


def _lista_clicavel(chave: str, linhas: list[dict], jogo: str) -> None:
    """Linhas do ranking; tocar em alguém abre o perfil público (quem esconde o perfil continua no ranking, sem link)."""
    import amigos_app as AMA
    try:
        nomes = _usuarios_por_hash()
    except Exception:
        nomes = {}
    st.markdown(AMA.CSS, unsafe_allow_html=True)
    with st.container(key=f"{chave}_lista"):
        for x in linhas:
            u = None if x["eu"] else nomes.get(x["h"])
            AMA.linha_clicavel(f"{chave}_{x['pos']}", "<div class='jg-lista'>" + _linha_rank(x, jogo) + "</div>", u, f"Ver perfil de {x['apelido']}")


def placares() -> list[dict]:
    """Placar de todas as contas (uma consulta, cache de 60 s). Também usado pelo perfil público."""
    return _placares()


def _limpar_cache() -> None:
    _placares.clear()
    _emails_por_hash.clear()
    _ligas_todas.clear()
    _usuarios_por_hash.clear()


def ranking(jogo: str) -> dict | None:
    """Ranking de um jogo com a variação desde o início do dia. None se o banco não responder."""
    try:
        linhas = _placares()
    except Exception as e:
        banco.registrar_erro("jogos_app.ranking", e)
        return None
    eu = _email()
    rk = J.montar_ranking(jogo, linhas, eu)
    try:
        chave = f"jogos_rk|{jogo}"
        cache = st.session_state.get(f"_jg_base_{jogo}")
        if cache and cache[0] == _hoje():
            base = cache[1]
        else:
            base, novo = J.base_do_dia(banco.cfg_ler(chave), _hoje(), rk)
            if novo:
                banco.cfg_gravar(chave, novo)
            st.session_state[f"_jg_base_{jogo}"] = (_hoje(), base)
        rk = J.montar_ranking(jogo, linhas, eu, base)
    except Exception as e:
        banco.registrar_erro("jogos_app.base_do_dia", e)
    return rk


def _meu_doc() -> dict:
    a = _ator()
    if not a:
        return J.vazio()
    try:
        return J.sanear(banco.jogos_placar_ler(a))
    except Exception:
        return J.vazio()


def _gravar(fn, *args, **kw) -> bool:
    """Lê o documento da própria conta, aplica `fn` (pura, idempotente) e grava só se mudou. Nunca derruba a tela do jogo."""
    a = _ator()
    if not a:
        return False
    try:
        doc, mudou = fn(banco.jogos_placar_ler(a), *args, apelido=_apelido(), **kw)
        if mudou:
            banco.jogos_placar_gravar(a, doc)
            _limpar_cache()
        return mudou
    except Exception as e:
        try:
            banco.registrar_erro("jogos_app.gravar", e)
        except Exception:
            pass
        return False


def registrar_trade(pid: str, pontos: float, rodadas: int, formato: str, pos: int | None, n_jog: int) -> None:
    """Fim de partida do Trade Battle (pontos já calculados pelo servidor). Uma vez por partida e por sessão (o placar também é idempotente)."""
    ss = st.session_state
    feitos = ss.setdefault("_jg_trade_ok", set())
    if pid in feitos:
        return
    _gravar(J.registrar_trade, pid, pontos, rodadas, formato, pos, n_jog, _agora().strftime("%Y-%m-%d %H:%M"))
    feitos.add(pid)


def registrar_ticker(did: str, resultado: str, modo: str) -> None:
    """Fim de duelo do Ticker Battle (resultado decidido pelo servidor)."""
    _gravar(J.registrar_ticker, did, resultado, modo, _agora().strftime("%Y-%m-%d %H:%M"))


def sincronizar_ticker(forcar: bool = False) -> None:
    """Confere os duelos já terminados (contra o sistema e online) e soma ao placar os que ainda não entraram. Uma leitura de cada
    histórico, no máximo a cada 60 s por sessão. Cobre quem fechou o app antes de ver o resultado."""
    ss = st.session_state
    em, a = _email(), _ator()
    if not (em and a) or (not forcar and time.time() - ss.get("_jg_sync", 0) < 60):
        return
    ss["_jg_sync"] = time.time()
    try:
        import battle_dados as BD
        novos = [(h.get("id"), h.get("final"), "sistema", str(h.get("ts") or "")[:16].replace("T", " ")) for h in BD.ler_pessoa(banco, em)["hist"]]
        try:
            import battle_online_dados as BOD
            novos += [(h.get("id"), h.get("resultado"), "online", str(h.get("em") or "")[:16].replace("T", " ")) for h in BOD.historico(em)]
        except Exception:
            pass
        doc = J.sanear(banco.jogos_placar_ler(a))
        mudou = False
        for did, res, modo, em_ in reversed(novos):
            doc, m = J.registrar_ticker(doc, did, res, modo, em_, apelido=_apelido())
            mudou = mudou or m
        if mudou:
            banco.jogos_placar_gravar(a, doc)
            _limpar_cache()
    except Exception as e:
        banco.registrar_erro("jogos_app.sincronizar_ticker", e)


# ------------------------------------------------------------------ peças reaproveitadas pelas telas dos jogos
def faixa_jogo(jogo: str) -> None:
    """Faixa 'Ranking do <jogo>' com a posição e a pontuação da pessoa + atalho para o ranking. Usada nas telas iniciais dos dois jogos."""
    if jogo == J.TICKER:
        sincronizar_ticker()
    rk = ranking(jogo)
    st.markdown(CSS + f"<div class='jg-sec'>📊 Ranking do {_e(J.NOME[jogo])}</div>", unsafe_allow_html=True)
    if rk is None:
        st.markdown("<div class='jg-vazio'>O ranking não carregou agora. Tente de novo em instantes.</div>", unsafe_allow_html=True)
        return
    eu = rk["eu"]
    if eu:
        st.markdown(f"<div class='jg-faixa'><div class='av'>{_avatar(eu=True, tamanho=34)}</div><span class='ps'>#{eu['pos']}</span>"
                    f"<span class='nm'>{_e(eu['apelido'])} · de {rk['total']}</span><b>{_e(_fmt_valor(jogo, eu['valor']))}</b></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='jg-vazio'>Termine uma partida para entrar no ranking do {_e(J.NOME[jogo])}.</div>", unsafe_allow_html=True)
    st.button("Ver ranking completo", key=f"jg_fx_{jogo}", icon=":material/emoji_events:", width="stretch", on_click=_ir, args=("jogos-ranking",),
              kwargs={"jg_rk_jogo": jogo, "jg_rk_jogo_w": jogo})
    hist = _meu_doc()[jogo]["hist"]
    if hist:
        with st.expander("Suas últimas partidas", icon=":material/history:"):
            st.markdown("".join(_linha_hist(jogo, h) for h in hist[:10]), unsafe_allow_html=True)


def _linha_hist(jogo: str, h: dict) -> str:
    if jogo == J.TRADE:
        p = float(h.get("pts") or 0)
        cls = "up" if p > 0 else "dn" if p < 0 else "eq"
        onde = f" · {h['pos']}º de {h['n']}" if h.get("pos") and int(h.get("n") or 1) > 1 else ""
        return f"<div class='jg-hist'><span>{_e(h.get('em', ''))} · {_e(str(h.get('formato') or '').capitalize())}{_e(onde)}</span><b class='{cls}'>{_e(_fmt_valor(J.TRADE, p))}</b></div>"
    r = {"v": ("Vitória", "up"), "e": ("Empate", "eq"), "d": ("Derrota", "dn")}.get(h.get("r"), ("—", "eq"))
    return f"<div class='jg-hist'><span>{_e(h.get('em', ''))} · {'Online' if h.get('modo') == 'online' else 'Contra o sistema'}</span><b class='{r[1]}'>{r[0]}</b></div>"


# ------------------------------------------------------------------ TELA · Central de Jogos
def pagina_central() -> None:
    _cabecalho("Central de Jogos", "Aprenda. Compita. Evolua.")
    navegacao("jogos")
    sincronizar_ticker()
    with st.container(key="jg_jogos"):
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"<div class='jg-jogo' style='--c:{VERDE}'><img src='{ART.uri('hero')}' alt='{_e(J.NOME[J.TRADE])}'>"
                        "<span>Análise e replay</span></div>", unsafe_allow_html=True)
            st.button("Jogar agora", key="jg_ir_trade", icon=":material/play_arrow:", width="stretch", on_click=_ir, args=("trader",))
        with c2:
            st.markdown(f"<div class='jg-jogo' style='--c:{ROXO}'><img src='{ARTB.uri('modo_hero')}' alt='{_e(J.NOME[J.TICKER])}'>"
                        "<span>Duelo de cartas</span></div>", unsafe_allow_html=True)
            st.button("Jogar agora", key="jg_ir_ticker", icon=":material/play_arrow:", width="stretch", on_click=_ir, args=("battle",),
                      kwargs={"bt_tela": "central"})
    rt, rk = ranking(J.TRADE), ranking(J.TICKER)
    meu = J.resumo(_meu_doc())
    pos = lambda r: f"#{r['eu']['pos']}" if r and r["eu"] else "—"
    st.markdown("<div class='jg-sec'>🏅 Seus destaques</div>"
                f"<div class='jg-dest'><div><small>{_e(J.NOME[J.TRADE])}</small><b>{pos(rt)}</b><i>{_e(_fmt_valor(J.TRADE, meu['trade_pts']))}</i></div>"
                f"<div><small>{_e(J.NOME[J.TICKER])}</small><b>{pos(rk)}</b><i>{meu['ticker_v']}V · {meu['ticker_e']}E · {meu['ticker_d']}D</i></div>"
                f"<div><small>Vitórias</small><b>{meu['vitorias']}</b><i>nos dois jogos</i></div></div>", unsafe_allow_html=True)
    _card_desafio()
    with st.container(key="jg_atalhos"):
        st.button("Ranking", key="jg_at_rk", icon=":material/emoji_events:", width="stretch", on_click=_ir, args=("jogos-ranking",))
        st.button("Amigos", key="jg_at_am", icon=":material/group:", width="stretch", on_click=_ir, args=("jogos-amigos",))
        st.button("Eventos", key="jg_at_ev", icon=":material/redeem:", width="stretch", on_click=_ir, args=("jogos-eventos",))


def _desafio() -> dict | None:
    try:
        import educacao_app as EA
        import jogar as JG
        return JG.desafio_semana(EA.prog())
    except Exception:
        return None


def _card_desafio() -> None:
    d = _desafio()
    if not d:
        return
    pct = 0 if not d["alvo"] else min(100.0, d["atual"] / d["alvo"] * 100)
    st.markdown(f"<div class='jg-des'><span class='ic'>📅</span><div class='t'><b>Desafio da semana</b><small>{_e(d['titulo'])} · {_e(d['texto'])}</small>"
                f"<div class='jg-bar'><i style='width:{pct:.0f}%'></i></div></div><em>{d['atual']}/{d['alvo']}</em></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ TELA · Ranking Geral
def _podio(rk: dict, jogo: str) -> str:
    top = rk["linhas"][:3]
    ordem = [top[i] if i < len(top) else None for i in (1, 0, 2)]
    out = []
    for x, cls in zip(ordem, ("p2", "p1", "p3")):
        if not x:
            out.append("<div></div>")
            continue
        out.append(f"<div class='{cls}'><div class='av'>{_avatar(x['h'], x['eu'], 64 if cls == 'p1' else 52)}</div><div class='nm'>{_e(x['apelido'])}</div>"
                   f"<div class='vl'>{_e(_fmt_valor(jogo, x['valor']))}</div><div class='base'>{x['pos']}</div></div>")
    return "<div class='jg-podio'>" + "".join(out) + "</div>"


def _podio_clicavel(rk: dict, jogo: str) -> None:
    """Pódio com um botão invisível sobre cada jogador (2º, 1º, 3º, na ordem do desenho) que abre o perfil público."""
    import amigos_app as AMA
    try:
        nomes = _usuarios_por_hash()
    except Exception:
        nomes = {}
    top = rk["linhas"][:3]
    ordem = [top[i] if i < len(top) else None for i in (1, 0, 2)]
    st.markdown(f"<style>{_P} .st-key-jg_pod{{position:relative;gap:0 !important}}"
                f"{_P} .st-key-jg_pod_b{{position:absolute !important;inset:0;z-index:3;display:grid !important;grid-template-columns:1fr 1.15fr 1fr;gap:6px !important}}"
                f"{_P} .st-key-jg_pod_b > div{{width:auto !important;height:100%}}"
                f"{_P} .st-key-jg_pod_b .stButton,{_P} [data-testid='stMain'] .st-key-jg_pod_b .stButton > button[data-testid]{{width:100% !important;height:100% !important;"
                f"opacity:0 !important;min-height:0 !important;background:transparent !important;border:0 !important;box-shadow:none !important}}</style>",
                unsafe_allow_html=True)
    with st.container(key="jg_pod"):
        st.markdown(_podio(rk, jogo), unsafe_allow_html=True)
        with st.container(key="jg_pod_b"):
            for i, x in enumerate(ordem):
                u = nomes.get(x["h"]) if x and not x["eu"] else None
                if u:
                    st.button(f"Ver perfil de {x['apelido']}", key=f"jg_pod_{i}", on_click=AMA.ir_jogador, args=(u,))
                else:
                    st.markdown("&nbsp;")


def _var(v) -> str:
    if v is None:
        return "<span class='vr eq'>—</span>"
    if v > 0:
        return f"<span class='vr up'>▲{v}</span>"
    if v < 0:
        return f"<span class='vr dn'>▼{-v}</span>"
    return "<span class='vr eq'>=</span>"


def _linha_rank(x: dict, jogo: str) -> str:
    v = x["valor"]
    sub = f"{x['partidas']} partida{'s' if x['partidas'] != 1 else ''}"
    return (f"<div class='jg-lin{' eu' if x['eu'] else ''}'><span class='ps'>{x['pos']}</span><span class='av'>{_avatar(x['h'], x['eu'], 30)}</span>"
            f"<span class='nm'>{_e(x['apelido'])}{' (você)' if x['eu'] else ''}<small>{_e(sub)}</small></span>"
            f"<b class='{'neg' if v < 0 else ''}'>{_e(_fmt_valor(jogo, v))}</b>{_var(x['var'])}</div>")


def _seletor_jogo(chave: str) -> str:
    padrao = st.session_state.get(chave) if st.session_state.get(chave) in J.JOGOS else J.TRADE
    sel = st.segmented_control("Jogo", list(J.JOGOS), default=padrao, key=f"{chave}_w", format_func=lambda j: J.NOME[j], label_visibility="collapsed")
    sel = sel if sel in J.JOGOS else padrao
    st.session_state[chave] = sel
    return sel


def pagina_ranking() -> None:
    _cabecalho("Ranking Geral", "Cada jogo com a sua classificação.")
    navegacao("jogos-ranking")
    jogo = _seletor_jogo("jg_rk_jogo")
    if jogo == J.TICKER:
        sincronizar_ticker()
    rk = ranking(jogo)
    if rk is None:
        st.markdown("<div class='jg-vazio'>O ranking não carregou agora. Tente de novo em instantes.</div>", unsafe_allow_html=True)
        return
    if not rk["total"]:
        st.markdown(f"<div class='jg-vazio'>Ainda ninguém terminou uma partida do {_e(J.NOME[jogo])}. Seja o primeiro!</div>", unsafe_allow_html=True)
        st.button(f"Jogar {J.NOME[jogo]}", key="jg_rk_jogar", icon=":material/play_arrow:", width="stretch", on_click=_ir,
                  args=("trader" if jogo == J.TRADE else "battle",))
        return
    crit = "pontos acumulados nas partidas terminadas" if jogo == J.TRADE else "vitórias nos duelos (contra o sistema e online)"
    st.markdown(f"<div class='jg-card'><p>Classificação por {crit}. Variação ▲▼ desde o início do dia. Toque em um jogador para ver o perfil.</p></div>",
                unsafe_allow_html=True)
    _podio_clicavel(rk, jogo)
    eu = rk["eu"]
    resto = rk["linhas"][3:50]
    if eu and eu["pos"] > 3 + len(resto):                       # fora do pódio e da lista mostrada: aparece à parte (senão já está destacado)
        st.markdown("<div class='jg-sec'>Sua posição</div><div class='jg-lista'>" + _linha_rank(eu, jogo) + "</div>", unsafe_allow_html=True)
    if resto:
        st.markdown("<div class='jg-sec'>Classificação<small>" + f"{rk['total']} jogador{'es' if rk['total'] != 1 else ''}" + "</small></div>",
                    unsafe_allow_html=True)
        _lista_clicavel("jg_rk", resto, jogo)
    st.caption(f"Atualizado às {_agora():%H:%M} · atualiza sozinho a cada minuto.")
    if st.button("Atualizar agora", key="jg_rk_atual", icon=":material/refresh:"):
        _limpar_cache()
        st.rerun()


# ------------------------------------------------------------------ TELA · Meus Amigos (ligas de amigos por convite)
def _minhas_ligas(a) -> list[dict]:
    doc = L.sanear_ligas(banco.comp_ligas_ler(a))
    out = []
    for x in doc["ligas"]:
        try:
            d = banco.comp_liga_definicao(a, x["c"])
        except Exception:
            d = None
        if d:
            out.append({**d, "dono": x["dono"]})
    return out


def _criar_liga(a) -> None:
    ss = st.session_state
    nome = str(ss.get("jg_am_nome") or "")
    ok, msg = L.nome_valido(nome)
    if not ok:
        ss["jg_am_msg"] = ("er", msg)
        return
    try:
        import planos
        doc = L.sanear_ligas(banco.comp_ligas_ler(a))
        pode, aviso = planos.permitido_max("comp_ligas_criar", sum(1 for x in doc["ligas"] if x["dono"]))
        if not pode:
            ss["jg_am_msg"] = ("er", aviso)
            return
        pode, aviso = planos.permitido_max("comp_ligas_entrar", len(doc["ligas"]))
        if not pode:
            ss["jg_am_msg"] = ("er", aviso)
            return
        lim, _ = planos.limite_atual("comp_liga_membros")
        cod = banco.comp_liga_criar(a, L.nova_definicao(nome, min(lim, L.MAX_MEMBROS_TETO)))
        banco.comp_ligas_gravar(a, L.adicionar(doc, cod, _agora().date(), dono=True))
        _limpar_cache()
        ss["jg_am_liga"], ss["jg_am_nome"] = cod, ""
        ss["jg_am_msg"] = ("ok", f"Liga criada! Passe o código {L.formatar_codigo(cod)} para seus amigos.")
    except Exception as e:
        banco.registrar_erro("jogos_app.criar_liga", e)
        ss["jg_am_msg"] = ("er", "Não consegui criar a liga agora. Tente de novo em instantes.")


def _entrar_liga(a) -> None:
    ss = st.session_state
    cod = L.codigo_valido(ss.get("jg_am_cod"))
    if not cod:
        ss["jg_am_msg"] = ("er", "Código inválido. Ele tem 8 letras/números (ex.: ABCD-2345).")
        return
    try:
        import planos
        d = banco.comp_liga_definicao(a, cod)
        if not d:
            ss["jg_am_msg"] = ("er", "Não existe liga com esse código.")
            return
        doc = L.sanear_ligas(banco.comp_ligas_ler(a))
        if L.participa(doc, cod):
            ss["jg_am_liga"] = cod
            ss["jg_am_msg"] = ("ok", f"Você já está na liga {d['nome']}.")
            return
        pode, aviso = planos.permitido_max("comp_ligas_entrar", len(doc["ligas"]))
        if not pode:
            ss["jg_am_msg"] = ("er", aviso)
            return
        if banco.comp_liga_contagem(a, cod) >= d["max"]:
            ss["jg_am_msg"] = ("er", "Essa liga já está cheia.")
            return
        banco.comp_ligas_gravar(a, L.adicionar(doc, cod, _agora().date()))
        _limpar_cache()
        ss["jg_am_liga"], ss["jg_am_cod"] = cod, ""
        ss["jg_am_msg"] = ("ok", f"Você entrou na liga {d['nome']}!")
    except Exception as e:
        banco.registrar_erro("jogos_app.entrar_liga", e)
        ss["jg_am_msg"] = ("er", "Não consegui entrar na liga agora. Tente de novo em instantes.")


def _sair_liga(a, cod: str, dono: bool) -> None:
    ss = st.session_state
    try:
        if dono:
            banco.comp_liga_encerrar(a, cod)
        banco.comp_ligas_gravar(a, L.remover(banco.comp_ligas_ler(a), cod))
        _limpar_cache()
        ss.pop("jg_am_liga", None)
        ss["jg_am_msg"] = ("ok", "Liga encerrada." if dono else "Você saiu da liga.")
    except Exception as e:
        banco.registrar_erro("jogos_app.sair_liga", e)
        ss["jg_am_msg"] = ("er", "Não consegui concluir agora. Tente de novo em instantes.")


def _msg_amigos() -> None:
    m = st.session_state.pop("jg_am_msg", None)
    if m:
        (st.success if m[0] == "ok" else st.error)(m[1])


def pagina_amigos() -> None:
    _cabecalho("Meus Amigos", "Seus amigos, solicitações, convites e comparação de resultados.")
    navegacao("jogos-amigos")
    a = _ator()
    if not a:
        return
    conv = L.extrair_convite(st.query_params.get("liga"))
    aba = st.segmented_control("Seção", ["Amigos", "Ligas"], default="Ligas" if conv else "Amigos", key="jg_am_aba", label_visibility="collapsed") or "Amigos"
    if aba == "Amigos":
        import amigos_app as AMA
        AMA.secao_amigos()
        return
    _secao_ligas(a)


def _secao_ligas(a) -> None:
    conv = L.extrair_convite(st.query_params.get("liga"))
    if conv and not st.session_state.get("jg_am_cod"):
        st.session_state["jg_am_cod"] = L.formatar_codigo(conv)
    _msg_amigos()
    try:
        ligas = _minhas_ligas(a)
    except Exception as e:
        banco.registrar_erro("jogos_app.amigos", e)
        st.markdown("<div class='jg-vazio'>Suas ligas não carregaram agora. Tente de novo em instantes.</div>", unsafe_allow_html=True)
        return
    if ligas:
        cods = [x["codigo"] for x in ligas]
        por = {x["codigo"]: x for x in ligas}
        atual = st.session_state.get("jg_am_liga") if st.session_state.get("jg_am_liga") in por else cods[0]
        if len(ligas) > 1:
            atual = st.selectbox("Liga", cods, index=cods.index(atual), format_func=lambda c: por[c]["nome"], key="jg_am_sel")
        st.session_state["jg_am_liga"] = atual
        lg = por[atual]
        jogo = _seletor_jogo("jg_am_jogo")
        try:
            membros = {r["email"] for r in _ligas_todas()
                       if any(isinstance(x, dict) and x.get("c") == atual for x in (r["dados"] or {}).get("ligas") or [])}
            rk = J.ranking_entre(jogo, _placares(), membros, _email())
        except Exception as e:
            banco.registrar_erro("jogos_app.ranking_liga", e)
            rk = None
        st.markdown(f"<div class='jg-sec'>👥 {_e(lg['nome'])}<small>{len(membros) if rk else '—'} de {lg['max']} membros</small></div>", unsafe_allow_html=True)
        if rk is None:
            st.markdown("<div class='jg-vazio'>O placar da liga não carregou agora.</div>", unsafe_allow_html=True)
        elif not rk["total"]:
            st.markdown(f"<div class='jg-vazio'>Ninguém desta liga terminou uma partida do {_e(J.NOME[jogo])} ainda.</div>", unsafe_allow_html=True)
        else:
            _lista_clicavel("jg_lg", rk["linhas"], jogo)
        try:
            import email_envio
            link = L.link_convite(email_envio.url_base(), atual)
        except Exception:
            link = ""
        st.markdown(f"<div class='jg-card'><b>Convide seus amigos</b><p>Código da liga: <span class='jg-cod'>{_e(L.formatar_codigo(atual))}</span></p>"
                    + (f"<p>Ou envie o link: {_e(link)}</p>" if link.startswith("http") else "") + "</div>", unsafe_allow_html=True)
        st.button("Encerrar a liga" if lg["dono"] else "Sair da liga", key="jg_am_sair", icon=":material/logout:", on_click=_sair_liga, args=(a, atual, lg["dono"]))
    else:
        st.markdown("<div class='jg-vazio'>Você ainda não está em nenhuma liga de amigos. Crie uma e passe o código, ou entre com o código que recebeu.</div>",
                    unsafe_allow_html=True)
    with st.expander("Entrar em uma liga com código", icon=":material/vpn_key:", expanded=bool(conv) or not ligas):
        st.text_input("Código da liga", key="jg_am_cod", max_chars=40, placeholder="ABCD-2345 ou o link do convite", label_visibility="collapsed")
        st.button("Entrar na liga", key="jg_am_entrar", icon=":material/login:", width="stretch", on_click=_entrar_liga, args=(a,))
    try:
        import planos
        pode_criar, plano = planos.limite_atual("comp_ligas_criar")
    except Exception:
        pode_criar, plano = 1, ""
    if pode_criar > 0:
        with st.expander("Criar uma liga de amigos", icon=":material/group_add:", expanded=not ligas and not conv):
            st.text_input("Nome da liga", key="jg_am_nome", max_chars=30, placeholder="Ex.: Turma da faculdade", label_visibility="collapsed")
            st.button("Criar liga", key="jg_am_criar", icon=":material/add:", width="stretch", on_click=_criar_liga, args=(a,))
    else:                                                       # regra do plano (Planos e limites): no Gratuito só se entra em ligas
        st.markdown(f"<div class='jg-card'><b>Criar ligas</b><p>No plano {_e(plano)} você entra nas ligas dos seus amigos com o código. "
                    "Criar a sua própria liga faz parte dos planos Investidor Plus e Premium.</p></div>", unsafe_allow_html=True)
    st.caption("As ligas são as mesmas da Competição e da liga de estudo: um código, vários placares. Ninguém vê seu e-mail, só o seu NickName.")


# ------------------------------------------------------------------ TELA · Eventos e Recompensas (só leitura dos sistemas existentes)
def _rec(ic: str, titulo: str, sub: str, valor: str = "", cls: str = "") -> str:
    return (f"<div class='jg-rec'><span class='ic'>{ic}</span><div class='t'>{_e(titulo)}<small>{_e(sub)}</small></div>"
            + (f"<b class='{cls}'>{_e(valor)}</b>" if valor else "") + "</div>")


def pagina_eventos() -> None:
    _cabecalho("Eventos e Recompensas", "Desafios, missões e o que você já ganhou.")
    navegacao("jogos-eventos")
    u = usuarios.usuario() or {}
    cid = u.get("id")
    _card_desafio()
    try:
        import educacao_app as EA
        import jogar as JG
        p = EA.prog()
        md = JG.missoes_do_dia(p)
        feitas = sum(1 for m in md if m.get("ok"))
        st.markdown("<div class='jg-sec'>🎯 Missões de hoje</div><div class='jg-card'>"
                    + _rec("✅" if feitas == len(md) else "🎯", f"{feitas} de {len(md)} missões do dia concluídas", "Estudo na Jornada (Central de missões)")
                    + "</div>", unsafe_allow_html=True)
    except Exception:
        pass
    try:
        import jogar_app as JGA
        res = JGA._res_wallet()
        if res:
            sem = [m for m in res["missoes"] if m["periodo"] == "semana"]
            if sem:
                linhas = []
                for m in sem:
                    rec = m.get("recompensa") or {}
                    premio = " · ".join(x for x in (f"+{int(rec['xp'])} XP" if rec.get("xp") else "", f"+{int(rec['tc'])} TC" if rec.get("tc") else "") if x)
                    linhas.append(_rec("✅" if m["feita"] else "🪙", m["nome"], m["objetivo"], premio))
                st.markdown("<div class='jg-sec'>🪙 Missões da semana · Carteira</div><div class='jg-card'>" + "".join(linhas) + "</div>", unsafe_allow_html=True)
    except Exception:
        pass
    eventos = []
    try:
        import tickercoins as TC
        agora = datetime.now(timezone.utc)
        for c in TC.config().get("campanhas") or []:
            ini, fim = TC._de_iso(c.get("inicio")), TC._de_iso(c.get("fim"))
            if ini and fim and ini <= agora < fim:
                eventos.append(_rec("🚀", str(c.get("rotulo") or "Campanha"), f"Até {fim.astimezone(BRT):%d/%m %H:%M}", f"{int(c.get('multiplicador', 1))}× TC"))
        if cid:
            b = TC.bau_diario(cid)
            if b.get("ativo"):
                eventos.append(_rec("🎁", "Baú diário", "Já aberto hoje" if b["aberto"] else "Disponível na Loja Ticker",
                                    f"+{b['valor']} TC" if b["aberto"] else "abrir"))
    except Exception:
        pass
    st.markdown("<div class='jg-sec'>✨ Eventos ativos</div><div class='jg-card'>"
                + ("".join(eventos) if eventos else "<p>Nenhum evento especial agora. Fique de olho: campanhas aparecem aqui.</p>") + "</div>", unsafe_allow_html=True)
    rec = []
    try:
        import tickercoins as TC
        for r in TC.historico(cid, 40) if cid else []:
            if int(r.get("delta") or 0) > 0:
                rec.append(_rec("🪙", str(r.get("descricao") or "Ticker Coins"), str(r.get("criado_em") or "")[:10], f"+{int(r['delta'])} TC"))
            if len(rec) >= 8:
                break
    except Exception:
        pass
    try:
        import educacao_app as EA
        for pid, v in reversed(list((EA.prog().get("trader_xp") or {}).items())[-5:]):
            if int(v.get("xp") or 0) > 0:
                rec.append(_rec("⭐", f"{J.NOME[J.TRADE]} · XP da partida", str(v.get("d") or ""), f"+{int(v['xp'])} XP", "xp"))
    except Exception:
        pass
    st.markdown("<div class='jg-sec'>🏆 Suas recompensas</div><div class='jg-card'>"
                + ("".join(rec) if rec else "<p>Você ainda não recebeu recompensas. Complete missões e desafios para começar.</p>") + "</div>",
                unsafe_allow_html=True)
    with st.container(key="jg_atalhos"):
        st.button("Central de missões", key="jg_ev_mis", icon=":material/flag:", width="stretch", on_click=_ir, args=("missoes",))
        st.button("Loja Ticker", key="jg_ev_loja", icon=":material/storefront:", width="stretch", on_click=_ir, args=("economia",))
    st.caption("Recompensas vêm só das regras que já existem no app (missões, desafios, baús e campanhas). "
               f"Os jogos dão XP pela colocação; o {J.NOME[J.TRADE]} não dá Ticker Coins.")
