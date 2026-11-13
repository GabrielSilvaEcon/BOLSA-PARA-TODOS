"""Ticker Battle Online · telas (Streamlit). Regras em battle_online.py, banco/fila/salas em battle_online_dados.py.

Telas (chave `bt_tela`): central (modos) → busca | sala → espera → oarena → oresultado. Reaproveita as cartas, o CSS e o Raio-X do Duelo contra o Sistema (battle_app).
Sincronização: `st.fragment(run_every=2.5)` consulta o banco só enquanto a tela online está aberta; sair da tela para a consulta.
O navegador só envia "qual carta" e "qual atributo"; o servidor valida, grava na hora e calcula tudo. Sem XP, moedas, ranking, chat ou recompensas.
"""
from __future__ import annotations

import html
import math
import time

import streamlit as st

import arte_battle as ART
import arte_cartela as CT
import arte_tickerhunters as AT
import battle as B
import battle_app as BA
import battle_online as O
import battle_online_dados as D
import banco

_e = html.escape
POLL_S = 1.5          # busca, sala e espera: respostas rápidas enquanto se aguarda alguém
POLL_ARENA_S = 2.0
REVELA_AUTO_S = 7     # revelação de rodada avança sozinha (exceto a última); dá para pular
_P = BA._P

_CSS = f"""
{_P} .on-modo{{position:relative;overflow:hidden;box-sizing:border-box;min-height:150px;padding:12px 10px 8px;text-align:center;
  background:radial-gradient(circle at 50% 22%,color-mix(in srgb,var(--c) 45%,transparent),transparent 62%),linear-gradient(170deg,#1A1250,#0B0825 90%);box-shadow:0 0 16px color-mix(in srgb,var(--c) 60%,transparent)}}
{_P} .on-modo .ic{{font-size:3.2rem;line-height:1.1;margin:6px 0 4px;filter:drop-shadow(0 0 12px var(--c))}}
{_P} .on-modo .ic img{{height:62px;width:auto}}
{_P} .on-modo b{{display:block;font-size:1.05rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .on-modo span{{display:block;font-size:.74rem;line-height:1.3;margin:3px 0 10px;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .on-modo i{{display:block;font-style:normal;font-weight:900;font-size:.84rem;padding:8px 4px;border-radius:10px;color:#101024 !important;-webkit-text-fill-color:#101024 !important;background:var(--c)}}
{_P} .on-ti{{text-align:center;font-weight:900;font-size:1.25rem;color:#fff !important;-webkit-text-fill-color:#fff !important;margin:4px 0 2px}}
{_P} .on-su{{text-align:center;font-size:.86rem;line-height:1.35;margin:0 10px 8px;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .on-globo{{display:flex;align-items:center;justify-content:center;gap:0;margin:8px 0}}
{_P} .on-globo .g{{font-size:5rem;line-height:1;filter:drop-shadow(0 0 18px #22d3ee)}}
{_P} .on-av{{display:flex;align-items:center;justify-content:center;width:58px;height:58px;border-radius:50%;background:#0E0A2C;border:2px solid #22d3ee;box-shadow:0 0 14px rgba(34,211,238,.8);overflow:hidden}}
{_P} .on-op-st{{margin:4px 0 2px;padding:6px 10px;border-radius:999px;text-align:center;font-size:.8rem;font-weight:800;border:1px solid rgba(197,179,255,.35);background:rgba(139,108,255,.14);color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .on-op-st.ok{{border-color:#3DDC97;background:rgba(61,220,151,.16);color:#7CF0BE !important;-webkit-text-fill-color:#7CF0BE !important}}
{_P} .st-key-bt_confirma{{position:sticky;bottom:calc(var(--dz-barra-h,64px) + env(safe-area-inset-bottom,0px) + 14px);z-index:60;padding:6px 0;background:linear-gradient(0deg,rgba(10,7,34,.96) 60%,transparent)}}
{_P} .on-av img{{width:100%;height:100%;object-fit:cover;object-position:50% 22%}}
{_P} .on-av.op{{border-color:#D23FC8;box-shadow:0 0 14px rgba(210,63,200,.8)}}
{_P} .on-av.sil img{{filter:brightness(0) opacity(.55)}}
{_P} .on-av.sil{{border-color:#6b6590;box-shadow:none}}
{_P} .on-cod{{margin:8px 0;padding:14px 10px;text-align:center;border-radius:18px;border:2px solid #22d3ee;background:linear-gradient(160deg,#17114A,#0B0825);box-shadow:0 0 16px rgba(34,211,238,.45)}}
{_P} .on-cod small{{display:block;font-size:.8rem;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}}
{_P} .on-cod b{{display:block;font-size:2.2rem;letter-spacing:.14em;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .on-ou{{display:flex;align-items:center;gap:10px;margin:8px 0;font-size:.8rem;color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE !important}}
{_P} .on-ou:before,{_P} .on-ou:after{{content:"";flex:1;height:1px;background:rgba(197,179,255,.35)}}
{_P} .on-jog{{display:flex;align-items:center;gap:12px;margin:8px 0;padding:10px;border-radius:16px;background:linear-gradient(160deg,#17114A,#0B0825);border:2px solid #22d3ee;box-shadow:0 0 12px rgba(34,211,238,.4)}}
{_P} .on-jog.op{{border-color:#6b6590;box-shadow:none}}
{_P} .on-jog.op.on{{border-color:#D23FC8;box-shadow:0 0 12px rgba(210,63,200,.45)}}
{_P} .on-jog b{{display:block;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .on-jog span{{font-size:.8rem;font-weight:800}}
{_P} .on-jog span.ok{{color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important}}
{_P} .on-jog span.es{{color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .on-ampulheta{{margin:8px 0;padding:14px;text-align:center;border-radius:16px;border:1px solid rgba(197,179,255,.3);background:rgba(255,255,255,.05);font-size:.85rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .on-ampulheta .h{{font-size:2rem}}
{_P} .on-placar{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:6px;margin:4px 0 8px;padding:8px;border-radius:16px;background:linear-gradient(160deg,#17114A,#0B0825);border:1px solid rgba(197,179,255,.3)}}
{_P} .on-placar .l{{display:flex;align-items:center;gap:8px}}
{_P} .on-placar .l.op{{flex-direction:row-reverse;text-align:right}}
{_P} .on-placar .n{{font-size:1.7rem;font-weight:900;line-height:1;color:#22d3ee !important;-webkit-text-fill-color:#22d3ee !important}}
{_P} .on-placar .op .n{{color:#FF6BC8 !important;-webkit-text-fill-color:#FF6BC8 !important}}
{_P} .on-placar small{{display:block;font-size:.66rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .on-placar .m{{text-align:center;font-weight:900;font-size:.82rem;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} .on-placar .m b{{display:block;font-size:1.05rem}}
{_P} .on-aviso{{margin:6px 0;padding:8px 10px;border-radius:12px;font-size:.8rem;font-weight:700;background:rgba(242,184,75,.14);border:1px solid #F2B84B;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} .on-trava{{margin:6px 0;padding:10px;border-radius:14px;text-align:center;font-size:.84rem;background:rgba(61,220,151,.12);border:1px solid #3DDC97;color:#CFFFE8 !important;-webkit-text-fill-color:#CFFFE8 !important}}
{_P} .on-vs{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:6px;margin:8px 0}}
{_P} .on-vs .x{{text-align:center;font-size:1.6rem;font-weight:900;font-style:italic;color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} .on-vs .p{{text-align:center;font-weight:900;font-size:1.9rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .on-vs .p small{{display:block;font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .on-cmp{{margin:6px 0;padding:8px 10px;border-radius:12px;font-size:.8rem;line-height:1.4;background:rgba(255,255,255,.06);border:1px solid rgba(197,179,255,.3);color:#EDE9FF !important;-webkit-text-fill-color:#EDE9FF !important}}
{_P} .on-cmp b{{color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important}}
{_P} [data-testid="stStatusWidget"]{{display:none !important}}
{_P} .on-av.sil img{{filter:brightness(0) invert(.38) !important}}
{_P} .on-vs .on-av{{margin:0 auto}}
{_P} .on-vs>div:not(.p){{text-align:center}}
{_P} .on-car{{max-width:250px;margin:0 auto}}
{_P} :is(.st-key-bt_setas,.st-key-bt_atrs)[data-testid="stVerticalBlock"],{_P} :is(.st-key-bt_setas,.st-key-bt_atrs)>[data-testid="stVerticalBlock"]{{display:grid !important;grid-template-columns:repeat(2,minmax(0,1fr)) !important;gap:8px !important}}
{_P} .on-hist .x b{{color:#fff !important;-webkit-text-fill-color:#fff !important}}
"""
CSS = "<style>" + "".join(l.strip() for l in _CSS.splitlines()) + "</style>"


# ------------------------------------------------------------------ estado
def _ss():
    return st.session_state


def _ir(tela: str) -> None:
    BA._ir(tela)


def _limpar() -> None:
    for k in ("on_pid", "on_vis", "on_idx", "on_ind", "on_visto", "on_erro", "on_ficha", "on_aviso"):
        _ss().pop(k, None)


def _erro(msg: str) -> None:
    _ss()["on_erro"] = msg


def _msg_erro() -> None:
    if _ss().get("on_erro"):
        st.markdown(f"<div class='bt-msg er'>{_e(_ss()['on_erro'])}</div>", unsafe_allow_html=True)


def _agir(fn, *a, destino: str | None = None, **kw):
    """Executa uma ação do servidor; erro de regra vira mensagem na tela (nunca derruba o app)."""
    _ss().pop("on_erro", None)
    try:
        r = fn(*a, **kw)
    except O.ErroPartida as e:
        _erro(str(e))
        return None
    except Exception as e:                                           # banco fora do ar / rede: mensagem simples e registro
        _erro("Sem conexão com o servidor agora. Tente de novo em instantes.")
        try:
            banco.registrar_erro("battle_online_app", e)
        except Exception:
            pass
        return None
    if destino:
        _ir(destino)
    return r


def _avatar(op: bool = False, sil: bool = False, pose: str = "rosto") -> str:
    cls = ("op" if op else "") + (" sil" if sil else "")
    fx = {"rosto": "confiante", "celebrando": "vitoriosa", "triste": "derrotada", "pensativo": "pensativa", "animado": "animada", "surpreso": "surpresa"}.get(pose, "confiante")
    nome = {"confiante": "raposa_confiante", "vitoriosa": "raposa_vitoriosa", "derrotada": "raposa_derrotada", "pensativa": "raposa_pensativa", "animada": "raposa_animada", "surpresa": "raposa_surpresa"}[fx]
    return f"<div class='on-av {cls}'>{CT.img(nome, alt='')}</div>"


def _cabecalho(titulo: str, sub: str = "") -> None:
    st.markdown(f"<div class='on-ti'>{_e(titulo)}</div>" + (f"<div class='on-su'>{sub}</div>" if sub else ""), unsafe_allow_html=True)


# ------------------------------------------------------------------ TELA · escolha do modo
def _abrir_partida(pid: str) -> None:
    _ss()["on_pid"] = pid
    _ss().pop("on_vis", None)
    _ss()["on_visto"] = 0
    _ir("espera")


def _entrar_fila() -> None:
    em = BA._email()
    if not em:
        _erro("Entre na sua conta para jogar online.")
        return
    r = _agir(D.entrar_na_fila, em)
    if not r:
        return
    if r["estado"] == "partida":
        _abrir_partida(r["id"])
    else:
        _ir("busca")


def _abrir_sala() -> None:
    em = BA._email()
    if not em:
        _erro("Entre na sua conta para jogar online.")
        return
    r = _agir(D.criar_sala, em)
    if r:
        _ss()["on_pid"] = r["id"]
        _ir("sala")


def _escolher_modo(m: str) -> None:
    _ss()["bt_modo_sel"] = m


def _jogar_modo() -> None:
    """JOGAR: começa o modo escolhido nos cartões (Sistema: preparar o duelo; Online: procurar adversário)."""
    if _ss().get("bt_modo_sel", "sis") == "on":
        _entrar_fila()
    else:
        _ir("preparar")


def cartoes_modo(ok_deck: bool) -> None:
    """Tela de entrada do Battle: dois cartões inteiros clicáveis (arte da referência) e o botão JOGAR que inicia o modo escolhido."""
    sel = _ss().get("bt_modo_sel", "sis")
    if sel not in ("sis", "on"):
        sel = "sis"
    cor = "#5AA8FF" if sel == "sis" else "#C06BFF"
    outro = "on" if sel == "sis" else "sis"
    s = f"{_P} .st-key-bt_modo_"
    st.markdown(f"<style>{s}sis button{{background-image:url({ART.uri('modo_sis')}) !important}}{s}on button{{background-image:url({ART.uri('modo_on')}) !important}}"
                f"{_P} .st-key-bt_jogar button{{background-image:url({ART.uri('modo_jogar')}) !important}}"
                f"{s}{sel} button{{box-shadow:0 0 0 3px #FFC93C,0 0 24px 2px {cor} !important}}"
                f"{s}{sel} button:after{{content:\"✓\";position:absolute;top:6px;left:8px;width:24px;height:24px;border-radius:50%;"
                "background:#FFC93C;color:#1A1030;font-weight:900;font-size:.95rem;line-height:24px;text-align:center;opacity:1;-webkit-text-fill-color:#1A1030}"
                f"{s}{outro} button{{opacity:.72}}</style>", unsafe_allow_html=True)
    with st.container(key="on_modos"):
        st.button("Duelo contra Sistema", key="bt_modo_sis", width="stretch", on_click=_escolher_modo, args=("sis",))
        st.button("Duelo Online", key="bt_modo_on", width="stretch", on_click=_escolher_modo, args=("on",))
    st.button("Jogar", key="bt_jogar", width="stretch", disabled=not ok_deck, on_click=_jogar_modo)
    if not ok_deck:
        st.caption("Monte um baralho válido abaixo para liberar o JOGAR.")
    _msg_erro()


def secao_online() -> None:
    """Sala privada, partida em andamento e histórico online (só para quem está logado e com o banco preparado)."""
    em = BA._email()
    if not em:
        st.markdown("<div class='bt-msg'>Para o Duelo Online é preciso estar logado. O Duelo contra Sistema funciona sem login.</div>", unsafe_allow_html=True)
        return
    if not _online_ok():
        st.markdown("<div class='bt-msg er'>O Duelo Online ainda não está ativado neste banco de dados (falta rodar o script SQL do Battle Online).</div>", unsafe_allow_html=True)
        return
    try:
        pid = D.partida_ativa(em)
        hist = D.historico(em, 5)
    except Exception:
        pid, hist = None, []
    if pid:
        st.markdown("<div class='on-aviso'>Você tem uma partida online em andamento.</div>", unsafe_allow_html=True)
        st.button("Voltar para a partida", key="bt_retomar", icon=":material/play_arrow:", type="primary", width="stretch", on_click=_abrir_partida, args=(pid,))
    st.button("Criar sala privada", key="bt_sala_atalho", icon=":material/lock:", width="stretch", on_click=_abrir_sala)
    rot = {"vitoria": "Vitória", "derrota": "Derrota", "empate": "Empate"}
    linhas = ""
    for h in hist:
        linhas += (f"<div class='bt-lin'><div class='r {h['resultado']}'>{rot[h['resultado']]}</div><div class='x'>{h['placar']['eu']} × {h['placar']['op']} contra <b>{_e(h['op'])}</b>"
                   f"<small>{_e(h['em'][8:10])}/{_e(h['em'][5:7])}/{_e(h['em'][:4])} · {_e(h['em'][11:16])} UTC{' · abandono' if h['motivo'] == 'abandono' else ''}{' · tempo esgotado' if h['motivo'] == 'tempo' else ''}</small></div></div>")
    st.markdown(f"<div class='bt-box on-hist'><div class='t'><span class='m'>{CT.img('ic_online', cls='bt-ico', alt='')}</span>Últimas partidas online</div>{linhas or '<div class=\"bt-vazio\">Você ainda não jogou online.</div>'}</div>", unsafe_allow_html=True)
    for i, h in enumerate(hist):
        st.button(f"Raio-X · {h['placar']['eu']}×{h['placar']['op']} vs {h['op']}", key=f"bt_hx_{i}", icon=":material/search:", width="stretch",
                  on_click=lambda h=h: (_ss().__setitem__("on_ficha", h), _ir("oresultado")))


def _online_ok() -> bool:
    ss = _ss()
    if "on_ok" not in ss:
        try:
            banco._contar("bt_fila")
            banco._contar("bt_partidas")
            ss["on_ok"] = True
        except Exception:
            return False                                             # não guarda a falha: tenta de novo na próxima abertura
    return ss["on_ok"]


# ------------------------------------------------------------------ TELA · buscando jogador
def _cancelar_busca() -> None:
    em = BA._email()
    if em:
        _agir(D.sair_da_fila, em)
    _ir("modo")


@st.fragment(run_every=POLL_S)
def _frag_busca() -> None:
    em = BA._email()
    try:
        r = D.consultar_fila(em) if em else {"estado": "fora"}
    except Exception:
        st.markdown("<div class='on-aviso'>Reconectando ao servidor…</div>", unsafe_allow_html=True)
        return
    if r["estado"] == "partida":
        _abrir_partida(r["id"])
        return st.rerun()
    if r["estado"] in ("expirou", "fora"):
        _ss()["on_erro"] = "Nenhum adversário apareceu agora. Tente de novo ou crie uma sala privada." if r["estado"] == "expirou" else "A busca foi encerrada."
        _ir("modo")
        return st.rerun()
    st.markdown("<div class='on-ti' style='font-size:1.05rem'>Buscando jogador…</div><div class='on-su'>Aguarde enquanto procuramos um adversário disponível.</div>", unsafe_allow_html=True)


def _busca() -> None:
    _cabecalho("Duelo Online", "Encontre um adversário e dispute uma partida épica!")
    st.markdown(f"<div class='on-globo'>{_avatar()}<div class='g'>🌐</div>{_avatar(op=True, sil=True)}</div>", unsafe_allow_html=True)
    _frag_busca()
    st.button("Cancelar Busca", key="bt_cancela", icon=":material/close:", width="stretch", on_click=_cancelar_busca)
    st.markdown("<div class='bt-box'><div class='t'><span class='m'>🔒</span>Ou crie uma sala privada</div><p>Compartilhe um código com um amigo para jogarem juntos.</p></div>", unsafe_allow_html=True)
    st.button("Criar Sala", key="bt_criar_sala", icon=":material/group:", width="stretch", on_click=lambda: (_cancelar_busca(), _abrir_sala()))
    _msg_erro()


# ------------------------------------------------------------------ TELA · sala privada
def _entrar_codigo() -> None:
    em = BA._email()
    r = _agir(D.entrar_na_sala, em, _ss().get("on_cod", ""))
    if r:
        _abrir_partida(r["id"])


def _sair_sala() -> None:
    pid, em = _ss().get("on_pid"), BA._email()
    if pid and em:
        _agir(D.sair, pid, em)
    _limpar()
    _ir("modo")


@st.fragment(run_every=POLL_S)
def _frag_sala() -> None:
    pid, em = _ss().get("on_pid"), BA._email()
    if not pid:
        return
    try:
        v = D.ler(pid, em)
    except Exception:
        st.markdown("<div class='on-aviso'>Reconectando ao servidor…</div>", unsafe_allow_html=True)
        return
    if v["fase"] == "pronta":
        _abrir_partida(pid)
        return st.rerun()
    if v["fase"] in ("cancelada", "finalizada"):
        _limpar()
        _ir("modo")
        return st.rerun()
    st.markdown("<div class='on-aviso'>⏳ Aguardando seu amigo entrar com o código…</div>", unsafe_allow_html=True)


def _sala() -> None:
    pid = _ss().get("on_pid")
    _cabecalho("Sala Privada", "Crie uma sala e compartilhe o código com seu amigo!")
    codigo = ""
    if pid:
        try:
            r = banco._selecionar("bt_partidas", {"id": pid}, ["codigo", "a_email", "status"], limite=1)
            if r and r[0]["a_email"] == BA._email() and r[0]["status"] == "aguardando":
                codigo = r[0].get("codigo") or ""
        except Exception:
            pass
    if codigo:
        st.markdown(f"<div class='on-cod'><small>🔑 Código da Sala</small><b>{_e(codigo)}</b></div>", unsafe_allow_html=True)
        st.code(codigo, language=None)
        st.caption("Toque no ícone de copiar no canto do código e envie ao seu amigo.")
        _frag_sala()
    st.markdown("<div class='on-ou'>Ou</div><div class='on-atr bt-atr'>Já recebeu um código?</div>", unsafe_allow_html=True)
    st.text_input("Código da sala", key="on_cod", placeholder="Digite o código da sala", max_chars=8, label_visibility="collapsed")
    st.button("Entrar na Sala", key="bt_entrar_sala", icon=":material/arrow_forward:", type="primary", width="stretch", on_click=_entrar_codigo)
    _msg_erro()
    st.button("Voltar", key="bt_v_sala", icon=":material/arrow_back:", width="stretch", on_click=_sair_sala)


# ------------------------------------------------------------------ TELA · sala de espera
def _pronto() -> None:
    _agir(D.estou_pronto, _ss().get("on_pid"), BA._email())


def _sair_partida() -> None:
    pid, em = _ss().get("on_pid"), BA._email()
    if pid and em:
        _agir(D.sair, pid, em)
    _limpar()
    _ir("modo")


def _ler(pid: str, em: str):
    """Consulta de sincronização. Falha de rede devolve a última visão conhecida (e avisa), sem derrubar a tela."""
    ss = _ss()
    try:
        v = D.ler(pid, em)
        ss["on_vis"], ss["on_offline"] = v, False
        return v
    except O.ErroPartida as e:
        _erro(str(e))
        return None
    except Exception:
        ss["on_offline"] = True
        return ss.get("on_vis")


def _faixa_conexao(v: dict) -> None:
    if _ss().get("on_offline"):
        st.markdown("<div class='on-aviso'>📡 Sem conexão com o servidor. Tentando reconectar… sua partida continua guardada.</div>", unsafe_allow_html=True)
    op = v.get("op")
    if op and not v["encerrada"] and op["sem_sinal"] is not None and op["sem_sinal"] >= O.SINAL_PERDIDO_S:
        resta = max(0, int(v["prazo_s"] - op["sem_sinal"]))
        st.markdown(f"<div class='on-aviso'>⚠️ O adversário parece desconectado. Aguardando a volta dele: {resta}s. Depois disso você vence por abandono.</div>", unsafe_allow_html=True)


@st.fragment(run_every=POLL_S)
def _frag_espera() -> None:
    pid, em = _ss().get("on_pid"), BA._email()
    v = _ler(pid, em) if pid else None
    if not v:
        if _ss().get("on_erro"):
            _limpar(); _ir("modo"); return st.rerun()
        return
    if v["fase"] == "em_jogo":
        _ir("oarena"); return st.rerun()
    if v["encerrada"]:
        _ir("oresultado"); return st.rerun()
    _faixa_conexao(v)
    op = v["op"]
    eu_ok, op_ok = v["eu"]["pronto"], bool(op and op["pronto"])
    if op:
        st.markdown(f"<div class='bt-fxres' style='max-width:260px'>{CT.img('faixa_prepare', alt='Prepare-se!')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='on-jog'>{_avatar()}<div><b>Você · {_e(v['eu']['nick'])}</b><span class='{'ok' if eu_ok else 'es'}'>{'✔ Pronto' if eu_ok else '⏳ Ainda não confirmou'}</span></div></div>"
                f"<div class='on-jog op{' on' if op_ok else ''}'>{_avatar(op=True, sil=not op)}<div><b>{_e(op['nick']) if op else 'Jogador Oponente'}</b>"
                f"<span class='{'ok' if op_ok else 'es'}'>{'✔ Pronto' if op_ok else '⏳ Aguardando…'}</span></div></div>"
                "<div class='on-ampulheta'><div class='h'>⏳</div>A partida será iniciada quando ambos estiverem prontos.</div>", unsafe_allow_html=True)
    if v["fase"] == "pronta" and not eu_ok:
        st.button("Estou Pronto", key="bt_pronto", icon=":material/check:", type="primary", width="stretch", on_click=_pronto)


def _espera() -> None:
    _cabecalho("Sala de Espera", "Aguardando o outro jogador…")
    _frag_espera()
    _msg_erro()
    st.button("Sair da sala", key="bt_sai_espera", icon=":material/logout:", width="stretch", on_click=_sair_partida)


# ------------------------------------------------------------------ TELA · arena online
def _idx(n: int) -> int:
    return min(max(int(_ss().get("on_idx", 0)), 0), max(n - 1, 0))


def _mover(delta: int, n: int) -> None:
    ss = _ss()
    ss["on_idx"] = (_idx(n) + delta) % max(n, 1)
    ss.pop("on_ind", None)


def _escolher_ind(i: str) -> None:
    _ss()["on_ind"] = i


def _confirmar(tk: str, ind: str) -> None:
    r = _agir(D.jogar, _ss().get("on_pid"), BA._email(), tk, ind)
    if r:
        _ss().pop("on_ind", None)
        _ss()["on_vis"] = r


def _proxima_visto() -> None:
    _ss()["on_visto"] = _ss().get("on_visto", 0) + 1
    _ss().pop("on_idx", None)


def _placar_html(v: dict, rod_txt: str) -> str:
    p = v["placar"]
    return (f"<div class='on-placar'><div class='l'>{_avatar()}<div><small>Você</small><div class='n'>{p['eu']}</div></div></div>"
            f"<div class='m'>{CT.img('rodada_' + rod_txt[0], h=34) if rod_txt[:1] in '123' else ''}Rodada<b>{rod_txt}</b></div>"
            f"<div class='l op'>{_avatar(op=True)}<div><small>{_e(v['op']['nick'])}</small><div class='n'>{p['op']}</div></div></div></div>")


def _persp(c: dict, lado: str) -> tuple[float, float, str]:
    """(meu valor, valor do outro, 'eu'|'op'|'empate') a partir de um item de comparação em termos a/b."""
    eu_v, op_v = (c["va"], c["vb"]) if lado == "a" else (c["vb"], c["va"])
    venc = "empate" if c["venc"] == "empate" else ("eu" if c["venc"] == lado else "op")
    return eu_v, op_v, venc


def _html_rodada(r: dict, cartas: dict, lado: str, nick_op: str, aberta: bool = False) -> str:
    """Revelação/Raio-X de uma rodada com as duas cartas, valores e a explicação dos atributos."""
    ceu, cop = cartas.get(r["eu"]["tk"]), cartas.get(r["op"]["tk"])
    if not ceu or not cop:
        return ""
    cmps = [_persp(c, lado) + (c["ind"], c["de"]) for c in r["cmp"]]
    ganhou = r["venc"]
    g_eu, g_op = ganhou == lado, ganhou == O.outro(lado)
    primeiro = cmps[0] if cmps else None
    big_eu = BA._grande(primeiro[3], primeiro[0]) if primeiro else ""
    big_op = BA._grande(primeiro[3], primeiro[1]) if primeiro else ""
    ca = BA.carta_html(ceu, mostrar=[], extra_cls="venceu" if g_eu else ("perdeu" if g_op else ""), grande=big_eu)
    cb = BA.carta_html(cop, mostrar=[], extra_cls="venceu" if g_op else ("perdeu" if g_eu else ""), grande=big_op)
    if ganhou == "empate":
        rot = ("empate", "Rodada empatada.")
    else:
        rot = ("vitoria", "Você venceu a rodada!") if g_eu else ("derrota", f"{_e(nick_op)} venceu a rodada.")
    linhas = ""
    for ev, ov, venc, ind, de in cmps:
        m = B.INDICADORES[ind]
        dono = "ambos" if de == "ambos" else ("eu" if de == lado else "op")
        titulo = {"ambos": "Atributo disputado (escolhido pelos dois)", "eu": "Atributo escolhido por você", "op": f"Atributo escolhido por {_e(nick_op)}"}[dono]
        res = {"eu": "ponto para você", "op": f"ponto para {_e(nick_op)}", "empate": "valores iguais, sem ponto"}[venc]
        linhas += (f"<div class='on-cmp'><b>{titulo}: {_e(m['nome'])}</b><br>Você {_e(B.formatar(ind, ev))} × {_e(B.formatar(ind, ov))} {_e(nick_op)} · {res}. {_e(m['regra'])}</div>")
    if r.get("motivo"):
        linhas += f"<div class='on-cmp'><b>Rodada empatada:</b> {_e(r['motivo'])}.</div>"
    raio = ""
    for c in r["cmp"][:2]:
        reg = {"ind": c["ind"], "jog": r["a"]["tk"], "adv": r["b"]["tk"], "va": c["va"], "vb": c["vb"],
               "venc": {"a": "jogador", "b": "adversario", "empate": "empate"}[c["venc"]], "melhor": B.INDICADORES[c["ind"]]["melhor"], "n": r["n"]}
        e = B.explicar(reg, {**cartas, r["a"]["tk"]: cartas.get(r["a"]["tk"], ceu), r["b"]["tk"]: cartas.get(r["b"]["tk"], cop)})
        raio += (f"<p><b>{_e(e['nome'])}.</b> {_e(e['significa'])} {_e(e['relevancia'])}</p><p><b>Limitações:</b> {_e(e['limites'])} <b>Não dá para concluir:</b> {_e(e['nao_conclui'])}</p>")
    dados = f"<p>Dados de referência: {_e(ceu['tk'])} em {_e(BA._data(r['eu']['ref']))} · {_e(cop['tk'])} em {_e(BA._data(r['op']['ref']))} (congelados no início da partida).</p>"
    return (f"<div class='bt-arena bt-anim'><div class='fl'></div><div class='bt-duelo'><div class='ca'>{ca}</div><img class='vs' src='{ART.uri('vs')}' alt='VS'><div class='cb'>{cb}</div></div></div>"
            f"<div class='bt-res {rot[0]}'>{rot[1]}</div>{linhas}"
            f"<details class='bt-rx'{' open' if aberta else ''}><summary>🔎 Raio-X da rodada {r['n']}</summary>{raio}{dados}</details>")


@st.fragment(run_every=POLL_ARENA_S)
def _frag_arena() -> None:
    ss = _ss()
    pid, em = ss.get("on_pid"), BA._email()
    v = _ler(pid, em) if pid else None
    if not v:
        if ss.get("on_erro"):
            _limpar(); _ir("modo"); return st.rerun()
        return
    visto = ss.get("on_visto", 0)
    if v["encerrada"] and visto >= len(v["reg"]):
        _ir("oresultado"); return st.rerun()
    if v["fase"] == "pronta":                                         # ainda na sala (ex.: voltou pelo "retomar")
        _ir("espera"); return st.rerun()
    _faixa_conexao(v)
    lado = v["lado"]
    nick_op = v["op"]["nick"]
    n_vis = min(v["rod"], v["rodadas"])
    # ---- revelação pendente: há rodadas resolvidas que ainda não vi
    if visto < len(v["reg"]):
        r = v["reg"][visto]
        st.markdown(_placar_html(v, f"{r['n']}/{v['rodadas']}"), unsafe_allow_html=True)
        st.markdown(_html_rodada(r, v["cartas"], lado, nick_op, aberta=False), unsafe_allow_html=True)
        ultima = r["n"] >= v["rodadas"] or v["encerrada"] and visto + 1 >= len(v["reg"])
        t0 = ss.get("on_rev_t")
        if not t0 or t0[0] != visto:
            t0 = ss["on_rev_t"] = (visto, time.time())
        falta = max(0, REVELA_AUTO_S - (time.time() - t0[1]))
        if not ultima and falta <= 0:
            _proxima_visto(); return st.rerun()
        rot = "Ver resultado final" if ultima else f"Próxima rodada · {math.ceil(falta)} s (toque para pular)"
        st.button(rot, key="bt_prox_on", icon=":material/arrow_forward:", type="primary", width="stretch", on_click=_proxima_visto)
        return
    st.markdown(_placar_html(v, f"{n_vis}/{v['rodadas']}"), unsafe_allow_html=True)
    if n_vis >= v["rodadas"] and v["placar"]["eu"] == v["placar"]["op"] and v["placar"]["eu"] > 0 and not v["encerrada"]:
        st.markdown(f"<div class='bt-fxres'>{CT.img('faixa_decisiva', alt='Rodada Decisiva!')}</div>", unsafe_allow_html=True)
    if v["encerrada"]:                                                # sem rodada nova para ver (abandono/tempo/cancelamento no meio)
        _ir("oresultado"); return st.rerun()
    # ---- minha jogada já confirmada: espera o outro
    esc = v["eu"]["escolha"]
    if esc:
        c = v["cartas"][esc["tk"]]
        st.markdown(BA.carta_html(c, mostrar=[], grande=BA._grande(esc["ind"], c["ind"][esc["ind"]])), unsafe_allow_html=True)
        st.markdown(f"<div class='on-trava'>🔒 Jogada confirmada: <b>{_e(esc['tk'])}</b> em <b>{_e(B.INDICADORES[esc['ind']]['nome'])}</b>.<br>"
                    f"{'O adversário já confirmou. Revelando…' if v['op']['confirmou'] else 'Aguardando o adversário confirmar. Ninguém vê a escolha do outro antes da revelação.'}</div>", unsafe_allow_html=True)
        return
    # ---- escolha secreta: carta (carrossel) → atributo → confirmar
    livres = [t for t in v["eu"]["deck"] if t not in v["eu"]["usadas"]]
    i = _idx(len(livres))
    tk = livres[i]
    carta = v["cartas"][tk]
    atrs = B.indicadores_validos(carta)
    ind = ss.get("on_ind") if ss.get("on_ind") in atrs else None
    _ok = v["op"]["confirmou"]
    st.markdown(f"<div class='on-op-st{' ok' if _ok else ''}'>{'✔ ' + _e(nick_op) + ' já confirmou a jogada' if _ok else '⏳ ' + _e(nick_op) + ' está escolhendo…'}</div>", unsafe_allow_html=True)
    st.markdown("<div class='bt-atr'>Escolha sua carta</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='on-car'>{BA.carta_html(carta, mostrar=atrs[:3])}</div>", unsafe_allow_html=True)
    with st.container(key="bt_setas"):
        st.button("Anterior", key="bt_ant", icon=":material/chevron_left:", on_click=_mover, args=(-1, len(livres)), disabled=len(livres) < 2, width="stretch")
        st.button("Próxima", key="bt_prox_c", icon=":material/chevron_right:", on_click=_mover, args=(1, len(livres)), disabled=len(livres) < 2, width="stretch")
    st.caption(f"Carta {i + 1} de {len(livres)} no seu baralho.")
    st.markdown("<div class='bt-atr'>Escolha o atributo</div>", unsafe_allow_html=True)
    with st.container(key="bt_atrs"):
        for a in atrs:
            m = B.INDICADORES[a]
            st.button(m["nome"], key=f"bt_oi_{a}", icon=f":material/{m['icone']}:", width="stretch", type="primary" if ind == a else "secondary", on_click=_escolher_ind, args=(a,))
    if ind:
        m = B.INDICADORES[ind]
        st.markdown(f"<div class='bt-edu'><b>{_e(m['nome'])}.</b> {_e(m['significa'])} <b>Regra:</b> {_e(m['regra'])}</div>", unsafe_allow_html=True)
    st.button("Confirmar Jogada", key="bt_confirma", icon=":material/check:", type="primary", width="stretch", disabled=ind is None, on_click=_confirmar, args=(tk, ind or ""))
    st.caption("Depois de confirmar, a jogada não pode ser alterada. O adversário só vê a sua escolha na revelação.")


def _desistir() -> None:
    _sair_partida()


def _arena() -> None:
    _cabecalho("Ticker Battle Online")
    _frag_arena()
    _msg_erro()
    with st.expander("Desistir da partida", icon=":material/flag:"):
        st.caption("Desistir encerra a partida e dá a vitória ao adversário.")
        st.button("Confirmar desistência", key="bt_desiste", type="primary", on_click=_desistir)


# ------------------------------------------------------------------ TELA · resultado online
def _ficha() -> dict | None:
    """Ficha da partida para o resultado: a histórica (Raio-X) ou a da partida que acabou de terminar (relida do servidor)."""
    ss = _ss()
    if ss.get("on_ficha"):
        return ss["on_ficha"]
    pid, em = ss.get("on_pid"), BA._email()
    if not (pid and em):
        return None
    try:
        v = D.ler(pid, em)
    except Exception:
        return None
    if not v["final"]:
        return None
    return {"id": v["id"], "resultado": v["final"]["resultado"], "motivo": v["final"]["motivo"], "eu": v["eu"]["nick"], "op": v["op"]["nick"], "placar": v["placar"],
            "ref": v["ref"], "rodadas": v["reg"], "cartas": v["cartas"], "lado": v["lado"]}


def _de_novo() -> None:
    _limpar()
    _entrar_fila()


def _menu() -> None:
    _limpar()
    _ir("modo")


def _resultado() -> None:
    f = _ficha()
    if not f:
        _limpar(); _ir("modo"); return st.rerun()
    lado = f["lado"]
    res = f["resultado"]
    tit = {"vitoria": ("Vitória!", "Você venceu o duelo!", "celebrando"), "derrota": ("Derrota", f"{f['op']} venceu desta vez.", "triste"), "empate": ("Empate", "O duelo terminou igual.", "pensativo")}[res]
    p = f["placar"]
    st.markdown(f"<div class='bt-final {res}'><div class='bt-fxres'>{CT.img({'vitoria': 'faixa_vitoria', 'derrota': 'faixa_derrota', 'empate': 'faixa_empate'}[res], alt=tit[0])}</div><div class='rs'>{_e(tit[1])}</div></div>"
                f"<div class='on-vs'><div>{_avatar(pose=tit[2])}<div class='bt-atr'>Você</div></div><div class='p'>{p['eu']} <span class='x'>VS</span> {p['op']}<small>{p['emp']} empatada(s)</small></div>"
                f"<div>{_avatar(op=True)}<div class='bt-atr' style='color:#FF6BC8'>{_e(f['op'])}</div></div></div>", unsafe_allow_html=True)
    if f["motivo"] == "abandono":
        st.markdown(f"<div class='on-aviso'>Encerrada por abandono: {'o adversário não voltou dentro do prazo' if res == 'vitoria' else 'você ficou desconectado além do prazo (ou desistiu)'}.</div>", unsafe_allow_html=True)
    elif f["motivo"] == "tempo":
        st.markdown(f"<div class='on-aviso'>Encerrada por tempo esgotado: {'o adversário não confirmou a jogada a tempo' if res == 'vitoria' else 'a sua jogada não foi confirmada a tempo'}.</div>", unsafe_allow_html=True)
    elif f["motivo"] == "cancelada":
        st.markdown("<div class='on-aviso'>Partida cancelada: nenhum dos dois voltou. Não conta vitória nem derrota.</div>", unsafe_allow_html=True)
    st.markdown("<div class='bt-atr'>Raio-X da Partida</div>", unsafe_allow_html=True)
    for k, r in enumerate(f["rodadas"]):
        st.markdown(f"<div class='bt-box'><div class='t'>Rodada {r['n']}</div>{_html_rodada(r, f['cartas'], lado, f['op'], aberta=False)}</div>", unsafe_allow_html=True)
    if not f["rodadas"]:
        st.markdown("<div class='bt-vazio'>Nenhuma rodada foi jogada.</div>", unsafe_allow_html=True)
    st.caption("Educacional: indicadores reais, sem recomendação de investimento. Nada aqui paga XP, moedas, ranking ou recompensas.")
    st.button("Jogar Novamente", key="bt_de_novo", icon=":material/replay:", type="primary", width="stretch", on_click=_de_novo)
    _msg_erro()
    st.button("Voltar para o Menu", key="bt_menu", icon=":material/home:", width="stretch", on_click=_menu)


# ------------------------------------------------------------------ roteador
TELAS_ON = {"busca": _busca, "sala": _sala, "espera": _espera, "oarena": _arena, "oresultado": _resultado}


def pagina_online(tela: str) -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    if tela in ("busca", "sala", "espera", "oarena", "oresultado") and not BA._email():
        _ir("central")
        return st.rerun()
    TELAS_ON[tela]()
