"""Trader Battle · interface (Streamlit). Mobile primeiro, no padrão visual do TickerHunters.

Toda regra mora em `trader_battle.py` e toda leitura de cenário em `trader_dados.py`. Aqui só se desenha o que `TB.visao()` entrega
(candles já revelados pelo relógio do servidor) e se coleta o que a pessoa registra. Independente do Ticker Battle.
"""
from __future__ import annotations

import html
import time

import streamlit as st

import arte_cartela as CT
import arte_trader as ART
import trader_battle as TB
import trader_dados as TD
import trader_grafico as TG
import trader_online_dados as TOD

_e = html.escape
_P = "html body .stApp.stApp.stApp"
VERDE, VERM, ROXO, OURO, AZUL = "#26D07C", "#FF4D6D", "#8B6CFF", "#F2B84B", "#4B8BFF"
POLL_S = 1.0

_CSS = f"""
{_P} [data-testid="stMainBlockContainer"],{_P} .block-container{{max-width:560px !important}}
{_P} .tb-hero{{margin:-8px -6px 0;text-align:center}}
{_P} .tb-hero img{{display:block;width:100%;max-width:420px;margin:0 auto;-webkit-mask-image:linear-gradient(to bottom,transparent 0,#000 8%,#000 90%,transparent 100%);mask-image:linear-gradient(to bottom,transparent 0,#000 8%,#000 90%,transparent 100%)}}
{_P} .tb-demo{{margin:4px 0;padding:8px 12px;border-radius:14px;border:1.5px solid {OURO};background:rgba(242,184,75,.12);font-size:.8rem;font-weight:700;color:#FFE3A3 !important;-webkit-text-fill-color:#FFE3A3 !important}}
{_P} .tb-chips{{display:grid;grid-template-columns:repeat(3,1fr);gap:6px;margin:6px 0}}
{_P} .tb-chips div{{text-align:center;padding:8px 4px;border-radius:14px;border:1px solid rgba(139,108,255,.45);background:linear-gradient(160deg,rgba(60,44,150,.5),rgba(18,12,56,.9));font-size:.68rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-chips b{{display:block;font-size:.92rem;white-space:nowrap;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-top{{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:8px;padding:6px 10px;border-radius:14px;border:1px solid rgba(139,108,255,.45);background:linear-gradient(160deg,rgba(60,44,150,.5),rgba(18,12,56,.92))}}
{_P} .tb-top .tk{{font-weight:900;font-size:.95rem;color:#fff !important;-webkit-text-fill-color:#fff !important;line-height:1.1}}
{_P} .tb-top .tk small{{display:block;font-weight:600;font-size:.68rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-rod{{display:flex;align-items:center;gap:4px;padding:3px 10px 3px 4px;border-radius:999px;border:1px solid {ROXO};font-size:.74rem;font-weight:800;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-rod img{{width:20px;height:20px}}
{_P} .tb-rel{{font-weight:900;font-size:1.25rem;font-variant-numeric:tabular-nums;color:{VERDE} !important;-webkit-text-fill-color:{VERDE} !important}}
{_P} .tb-rel.fim{{color:{VERM} !important;-webkit-text-fill-color:{VERM} !important}}
{_P} .tb-pill{{display:inline-block;margin-left:4px;padding:1px 7px;border-radius:999px;font-size:.6rem;font-weight:900;background:{OURO};color:#1A1030 !important;-webkit-text-fill-color:#1A1030 !important}}
{_P} .tb-h{{font-weight:900;font-size:.9rem;color:#fff !important;-webkit-text-fill-color:#fff !important;margin:2px 0}}
{_P} .tb-cap{{font-size:.72rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-ok{{padding:6px 10px;border-radius:12px;border:1px solid {VERDE};background:rgba(38,208,124,.12);font-size:.78rem;font-weight:800;color:#8DF5C1 !important;-webkit-text-fill-color:#8DF5C1 !important}}
{_P} .tb-er{{padding:6px 10px;border-radius:12px;border:1px solid {VERM};background:rgba(255,77,109,.12);font-size:.78rem;font-weight:800;color:#FFB0BD !important;-webkit-text-fill-color:#FFB0BD !important}}
{_P} .tb-aviso{{padding:6px 10px;border-radius:12px;border:1px solid rgba(139,108,255,.5);background:rgba(139,108,255,.12);font-size:.76rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .tb-card{{padding:10px 12px;border-radius:16px;border:1.5px solid rgba(139,108,255,.5);background:radial-gradient(circle at 100% 0,rgba(139,108,255,.25),transparent 60%),linear-gradient(160deg,#17114A,#0A0720 90%);margin:4px 0}}
{_P} .tb-card b{{color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-card p{{margin:3px 0 0;font-size:.8rem;color:#D9D4F7 !important;-webkit-text-fill-color:#D9D4F7 !important}}
{_P} .tb-pts{{text-align:center;padding:12px;border-radius:18px;border:2px solid {VERDE};background:radial-gradient(circle at 50% 0,rgba(38,208,124,.3),transparent 65%),linear-gradient(160deg,#0E2A2A,#0A0720 90%);margin:4px 0}}
{_P} .tb-pts .n{{font-size:2.3rem;font-weight:900;line-height:1;color:{VERDE} !important;-webkit-text-fill-color:{VERDE} !important}}
{_P} .tb-pts small{{display:block;margin-top:2px;font-size:.76rem;color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6 !important}}
{_P} .tb-troph{{text-align:center}}{_P} .tb-troph img{{width:60%;max-width:240px}}
{_P} .tb-lin{{display:flex;justify-content:space-between;align-items:center;padding:7px 0;border-top:1px solid rgba(255,255,255,.1);font-size:.85rem;color:#fff !important;-webkit-text-fill-color:#fff !important}}
{_P} .tb-lin span{{font-weight:900;color:{VERDE} !important;-webkit-text-fill-color:{VERDE} !important}}
{_P} .st-key-tb_jogar button,{_P} .st-key-tb_salvar button,{_P} .st-key-tb_prox button,{_P} .st-key-tb_de_novo button{{height:48px !important;border:0 !important;border-radius:14px !important;font-weight:900 !important;
  background:linear-gradient(90deg,#2EE86B,#14C9B5) !important;box-shadow:0 0 16px rgba(46,232,107,.4) !important}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_salvar,.st-key-tb_prox,.st-key-tb_de_novo) button :is(p,span){{color:#06240F !important;-webkit-text-fill-color:#06240F !important;font-weight:900 !important}}
{_P} :is(.st-key-tb_jogar,.st-key-tb_salvar,.st-key-tb_prox,.st-key-tb_de_novo) button:disabled{{filter:grayscale(.8) brightness(.6)}}
{_P} .st-key-tb_sala button,{_P} .st-key-tb_voltar button,{_P} .st-key-tb_replay_ja button{{border-radius:14px !important;border:1.5px solid rgba(139,108,255,.6) !important}}
{_P} .st-key-tb_estr{{gap:.4rem !important;padding:8px 10px;border-radius:16px;border:1.5px solid rgba(139,108,255,.5);background:linear-gradient(160deg,#17114A,#0A0720 90%)}}
{_P} .st-key-tb_conf_l [data-testid="stHorizontalBlock"]{{align-items:center;flex-wrap:nowrap !important;gap:.4rem !important}}
{_P} .st-key-tb_ferr [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap !important;gap:.4rem !important}}
{_P} .st-key-tb_ferr button{{min-height:38px !important;border-radius:12px !important;padding:0 8px !important;font-size:.78rem !important;width:100% !important}}
{_P} .st-key-tb_ferr [data-testid="stPopover"]{{width:100%}}
{_P} .st-key-tb_estr [data-testid="stNumberInputStepUp"],{_P} .st-key-tb_estr [data-testid="stNumberInputStepDown"]{{display:none !important}}
{_P} .tb-faixa img{{display:block;width:100%;max-width:420px;margin:2px auto}}
{_P} [class*="st-key-tb_estr"] [data-testid="stHorizontalBlock"]{{flex-wrap:nowrap !important;gap:.4rem !important}}
{_P} [class*="st-key-tb_estr"] [data-testid="stNumberInput"] input{{min-height:38px}}
{_P} .tb-graf [data-testid="stPlotlyChart"]{{border-radius:14px;overflow:hidden}}
"""
CSS = "<style>" + "".join(l.strip() for l in _CSS.splitlines()) + "</style>"


# ------------------------------------------------------------------ estado da sessão
def _ss():
    return st.session_state


def _agora() -> float:
    return time.time()


def _jogador() -> str:
    try:
        import usuarios
        u = usuarios.usuario()
        return (u or {}).get("email") or "visitante"
    except Exception:
        return "visitante"


def _partida() -> dict | None:
    return _ss().get("tb_p")


def _cen() -> dict:
    return _ss().get("tb_cen") or {}


def _cenario_atual(p: dict) -> dict:
    return _cen()[p["cenarios"][p["rodada"] - 1]]


def _zerar_rascunho() -> None:
    for k in [k for k in _ss() if k.startswith("tb_") and not k.startswith("tb_i_") and k not in ("tb_p", "tb_cen", "tb_tf")]:
        _ss().pop(k, None)


def _iniciar() -> None:
    tf = _ss().get("tb_tf") or "15m"
    try:
        cen = TD.escolher(tf, int(_agora()) % 100000)
        _ss()["tb_cen"] = TD.por_id([cen])
        _ss()["tb_p"] = TB.nova_partida(cen, tf, [_jogador()], _agora())
        _zerar_rascunho()
    except TB.ErroTrader as e:
        _ss()["tb_erro"] = str(e)
    except Exception:
        _ss()["tb_erro"] = "Não consegui carregar os cenários agora. Tente de novo em instantes."


def _sair() -> None:
    for k in ("tb_p", "tb_cen"):
        _ss().pop(k, None)
    _zerar_rascunho()


def _fmt_t(seg: int) -> str:
    return f"{seg // 60:02d}:{seg % 60:02d}"


# ------------------------------------------------------------------ gráfico (plotly; só recebe candles já revelados)
def _ind_cfg() -> dict:
    """Lê as escolhas direto das chaves dos widgets (valores padrão constantes: o widget não é recriado a cada clique)."""
    g = _ss().get
    return {"vol": bool(g("tb_i_vol", True)), "sma": int(g("tb_i_nsma", 20)) if g("tb_i_sma", True) else 0,
            "ema": int(g("tb_i_nema", 9)) if g("tb_i_ema", False) else 0, "rsi": 14 if g("tb_i_rsi", False) else 0, "sr": bool(g("tb_i_sr", False))}


def _rotulo(t: str) -> str:
    return f"{t[8:10]}/{t[5:7]} {t[11:16]}"


def _figura(v: dict, marcas: dict, linhas: dict | None = None, divisor: bool = False):
    """Figura do gráfico com só o que está em `v` (candles revelados). `linhas`: entrada/stop/alvo (aparecem só depois de travada a estratégia)."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    cand = v["candles"]
    n = len(cand)
    cfg = _ind_cfg()
    ind = TB.indicadores(cand, cfg)
    lab = [_rotulo(k["t"]) for k in cand]
    na, total = v["n_analise"], v["total_replay"]
    linhas_h = [1.0] + ([0.22] if cfg["vol"] else []) + ([0.26] if cfg["rsi"] else [])
    fig = make_subplots(rows=len(linhas_h), cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[h / sum(linhas_h) for h in linhas_h])
    fig.add_trace(go.Candlestick(x=lab, open=[k["o"] for k in cand], high=[k["h"] for k in cand], low=[k["l"] for k in cand], close=[k["c"] for k in cand],
                                 increasing_line_color=VERDE, increasing_fillcolor=VERDE, decreasing_line_color=VERM, decreasing_fillcolor=VERM,
                                 showlegend=False, name=v["ticker"]), row=1, col=1)
    if ind["sma"]:
        fig.add_trace(go.Scatter(x=lab, y=ind["sma"], mode="lines", line=dict(color=OURO, width=1.6), name=f"SMA {cfg['sma']}", showlegend=False, hoverinfo="skip"), row=1, col=1)
    if ind["ema"]:
        fig.add_trace(go.Scatter(x=lab, y=ind["ema"], mode="lines", line=dict(color="#4DD0E1", width=1.6), name=f"EMA {cfg['ema']}", showlegend=False, hoverinfo="skip"), row=1, col=1)
    r = 2
    if cfg["vol"]:
        fig.add_trace(go.Bar(x=lab, y=[k["v"] for k in cand], marker_color=[VERDE if k["c"] >= k["o"] else VERM for k in cand], opacity=.6, showlegend=False,
                             name="Volume", hoverinfo="skip"), row=r, col=1)
        r += 1
    if cfg["rsi"] and ind["rsi"]:
        fig.add_trace(go.Scatter(x=lab, y=ind["rsi"], mode="lines", line=dict(color="#C4B5FF", width=1.5), name="RSI", showlegend=False, hoverinfo="skip"), row=r, col=1)
        for nivel in (30, 70):
            fig.add_hline(y=nivel, line=dict(color="rgba(255,255,255,.25)", width=1, dash="dot"), row=r, col=1)
        fig.update_yaxes(range=[0, 100], row=r, col=1)
    # suporte/resistência automáticos e marcações da pessoa
    for z in ind["sr"]["suportes"][:3]:
        fig.add_hline(y=z["preco"], line=dict(color="rgba(38,208,124,.7)", width=1.2, dash="dash"), row=1, col=1)
    for z in ind["sr"]["resistencias"][:3]:
        fig.add_hline(y=z["preco"], line=dict(color="rgba(255,77,109,.7)", width=1.2, dash="dash"), row=1, col=1)
    for m in marcas.get("niveis", []):
        fig.add_hline(y=m["preco"], line=dict(color="#C4B5FF", width=1.3, dash="dot"), annotation_text=m.get("rotulo") or None, annotation_position="top left",
                      annotation_font_size=10, row=1, col=1)
    x_fim = (n + 3) if v["fase"] == "analise" else (na + total + 1)        # análise: foco nos candles; replay: janela fixa que comporta todo o replay
    for t in marcas.get("tendencias", []):
        if t["i1"] < n and t["i2"] < n:
            incl = (t["p2"] - t["p1"]) / (t["i2"] - t["i1"])
            fig.add_shape(type="line", x0=t["i1"], y0=t["p1"], x1=x_fim, y1=t["p1"] + incl * (x_fim - t["i1"]), line=dict(color=OURO, width=1.5), row=1, col=1)
    for a in marcas.get("notas", []):
        if 0 <= a["i"] < n:
            fig.add_annotation(x=lab[a["i"]], y=a["preco"], text=a["texto"], showarrow=True, arrowhead=2, arrowcolor="#C4B5FF", font=dict(size=10, color="#fff"),
                               bgcolor="rgba(60,44,150,.85)", row=1, col=1)
    for nome, cor in (("entrada", AZUL), ("stop", VERM), ("alvo", VERDE)):
        if linhas and linhas.get(nome):
            fig.add_hline(y=linhas[nome], line=dict(color=cor, width=1.6), annotation_text=nome.capitalize(), annotation_position="bottom right",
                          annotation_font_size=10, row=1, col=1)
    if divisor and na - 1 < n:
        fig.add_vline(x=lab[na - 1], line=dict(color="rgba(255,255,255,.4)", width=1, dash="dot"), row="all", col=1)
    fig.update_xaxes(type="category", rangeslider_visible=False, showgrid=False, tickfont=dict(size=9, color="#9E96CE"), nticks=5, categoryorder="trace",
                     range=[max(-0.5, na - 45), x_fim], showspikes=False)
    fig.update_yaxes(side="right", gridcolor="rgba(255,255,255,.06)", tickfont=dict(size=10, color="#CFC8EE"), zeroline=False)
    fig.update_layout(margin=dict(l=2, r=2, t=4, b=2), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(10,7,32,.85)", dragmode="pan", hovermode="x",
                      font=dict(color="#CFC8EE"), uirevision=f"tb-{v['rodada']}-{v['tf']}", height=300 + (50 if cfg["vol"] else 0) + (70 if cfg["rsi"] else 0), showlegend=False)
    return fig


def _grafico(v: dict, marcas: dict, linhas: dict | None = None, divisor: bool = False, chave: str = "tb_graf") -> None:
    try:
        fig = _figura(v, marcas, linhas, divisor)
    except Exception as e:
        st.markdown(f"<div class='tb-er'>Não consegui montar o gráfico agora ({_e(e.__class__.__name__)}).</div>", unsafe_allow_html=True)
        return
    st.markdown("<div class='tb-graf'>", unsafe_allow_html=True)
    mexe = bool(_ss().get("tb_i_mov", True))
    st.plotly_chart(fig, width="stretch", theme=None, key=chave,
                    config={"scrollZoom": mexe, "staticPlot": not mexe, "displaylogo": False, "responsive": True,
                            "modeBarButtonsToAdd": ["drawline", "drawrect", "eraseshape"], "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"]})
    st.markdown("</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ partes comuns
def _topo(v: dict, seg: int | None = None, rotulo: str = "") -> str:
    preco = v["candles"][-1]["c"]
    medalha = CT.img(f"rodada_{min(max(v['rodada'], 1), 3)}", alt="")
    demo = "<span class='tb-pill'>SIMULADO</span>" if v["demo"] else ""
    rel = f"<div class='tb-rel{' fim' if (seg is not None and seg <= 10) else ''}'>{_fmt_t(seg)}</div>" if seg is not None else "<div></div>"
    return (f"<div class='tb-top'><div class='tk'>{_e(v['ticker'])}{demo}<small>R$ {preco:.2f} · {_e(TB.TIMEFRAMES[v['tf']]['nome'])}{(' · ' + _e(rotulo)) if rotulo else ''}</small></div>"
            f"<div class='tb-rod'>{medalha}Rodada {v['rodada']}/{v['rodadas']}</div>{rel}</div>")


def _voltar() -> None:
    st.button("Voltar", key="tb_voltar", icon=":material/arrow_back:", on_click=_sair)


# ------------------------------------------------------------------ MULTIPLAYER · salas (o estado da partida vive no banco, não na sessão)
def _email_online() -> str | None:
    """Identidade validada pelo servidor (sessão de login). Sem login não há sala."""
    try:
        import usuarios
        return (usuarios.usuario() or {}).get("email") or None
    except Exception:
        return None


def _msg_online(e: Exception) -> str:
    return str(e) if isinstance(e, (TOD.ErroSala, TB.ErroTrader)) else "Servidor de salas indisponível agora. Confira se as tabelas do Trader Battle foram criadas no banco."


def _on_criar() -> None:
    em = _email_online()
    try:
        _ss()["tb_on_pid"] = TOD.criar_sala(em, _ss().get("tb_tf") or "15m", _agora())["id"]
    except Exception as e:
        _ss()["tb_erro"] = _msg_online(e)


def _on_entrar() -> None:
    em = _email_online()
    try:
        _ss()["tb_on_pid"] = TOD.entrar_na_sala(em, _ss().get("tb_on_cod") or "", _agora())["id"]
    except Exception as e:
        _ss()["tb_erro"] = _msg_online(e)


def _on_voltar_partida(pid: str) -> None:
    _ss()["tb_on_pid"] = pid


def _on_desanexar() -> None:
    _ss().pop("tb_on_pid", None)


def _on_sair_sala(pid: str) -> None:
    try:
        TOD.sair(pid, _email_online(), _agora())
    except Exception:
        pass
    _ss().pop("tb_on_pid", None)


def _on_iniciar(pid: str) -> None:
    try:
        TOD.iniciar(pid, _email_online(), _agora())
    except Exception as e:
        _ss()["tb_erro"] = _msg_online(e)


def _central_online() -> None:
    em = _email_online()
    st.markdown("<div class='tb-card'><b>Jogar com amigos</b><p>Crie uma sala e passe o código (2 a 4 jogadores). Todos veem o mesmo gráfico, "
                "o mesmo relógio e a mesma rodada.</p></div>", unsafe_allow_html=True)
    if not em:
        st.markdown("<div class='tb-aviso'>Entre na sua conta para criar ou entrar em uma sala.</div>", unsafe_allow_html=True)
        return
    try:
        ativa = TOD.partida_ativa(em)
    except Exception:
        ativa = None
    if ativa:
        st.button("Voltar para minha sala/partida", key="tb_on_volta", icon=":material/login:", width="stretch", on_click=_on_voltar_partida, args=(ativa,))
        return
    st.button("Criar sala", key="tb_on_criar", icon=":material/group_add:", width="stretch", on_click=_on_criar)
    st.text_input("Código da sala", key="tb_on_cod", max_chars=8, placeholder="Código de 6 letras/números", label_visibility="collapsed")
    st.button("Entrar com código", key="tb_on_entrar", icon=":material/vpn_key:", width="stretch", on_click=_on_entrar)


@st.fragment(run_every=2)
def _frag_sala(pid: str) -> None:
    em = _email_online()
    try:
        b = TOD.ler(pid, em, _agora())
    except Exception as e:
        _ss().pop("tb_on_pid", None)
        _ss()["tb_erro"] = _msg_online(e)
        return st.rerun()
    if b["estado"] != "sala":
        return st.rerun()                                        # a partida começou (ou a sala foi cancelada): tela inteira muda
    sa = b["sala"]
    cards = "".join(f"<div class='tb-lin'>{_e(j['nick'])}{' (você)' if j['voce'] else ''}<span>{'criador' if j['criador'] else 'jogador'}</span></div>" for j in sa["jogadores"])
    st.markdown(f"<div class='tb-pts'><div class='n'>{_e(sa['codigo'])}</div><small>código da sala · {_e(TB.TIMEFRAMES[sa['tf']]['nome'])}</small></div>"
                f"<div class='tb-card'><b>Jogadores {sa['n']}/{sa['max']}</b>{cards}</div>", unsafe_allow_html=True)
    if sa["criador"]:
        st.button("Iniciar partida", key="tb_on_iniciar", icon=":material/play_arrow:", width="stretch", disabled=sa["n"] < sa["min"], on_click=_on_iniciar, args=(pid,))
        if sa["n"] < sa["min"]:
            st.markdown("<div class='tb-cap'>Aguardando pelo menos mais 1 jogador para começar.</div>", unsafe_allow_html=True)
    else:
        st.markdown("<div class='tb-cap'>Aguardando o criador iniciar a partida…</div>", unsafe_allow_html=True)


@st.fragment(run_every=1)
def _frag_mesa_online(pid: str) -> None:
    """Mesmo gráfico contínuo do modo individual, mas o estado vem do banco: cada segundo o servidor entrega a esta sessão só o que ela pode ver."""
    em, ag = _email_online(), _agora()
    try:
        b = TOD.ler(pid, em, ag)
    except Exception as e:
        _ss().pop("tb_on_pid", None)
        _ss()["tb_erro"] = _msg_online(e)
        return st.rerun()
    if b["estado"] != "jogo" or b["p"]["fase"] == "fim":
        return st.rerun()
    v, p = b["v"], b["p"]
    est = _ss().setdefault(f"tb_ev_{pid}", {})
    try:
        val = TG.mesa(f"tb_mesa_{pid}", **TG.args_mesa(v, p, est, ag))
    except Exception:
        _ss()["tb_erro"] = "O gráfico não carregou neste navegador."
        _ss().pop("tb_on_pid", None)
        return st.rerun()
    if TG.processar(p, val, est, em, v["candles"][-1]["c"], ag, TOD.Ops(pid, em)):
        return st.rerun(scope="fragment")


def _fim_online(b: dict) -> None:
    v = b["v"]
    linhas = "".join(f"<div class='tb-lin'>Rodada {k + 1} · {_e(v['ticker'])}<span>{x:.1f}</span></div>" for k, x in enumerate(v["pontos_rodadas"]))
    st.markdown(f"<div class='tb-troph'><img src='{ART.uri('trofeu')}' alt=''></div>"
                f"<div class='tb-pts'><div class='n'>{v['pontos']:.1f}</div><small>pontos em {TB.RODADAS} rodadas{' · cenário simulado' if v['demo'] else ''}</small></div>"
                f"<div class='tb-card'>{linhas}</div>", unsafe_allow_html=True)
    st.button("Voltar ao início do Trader Battle", key="tb_voltar", icon=":material/home:", width="stretch", on_click=_on_desanexar)


def _pagina_online(pid: str) -> None:
    em = _email_online()
    try:
        b = TOD.ler(pid, em, _agora())
    except Exception as e:
        _ss().pop("tb_on_pid", None)
        _ss()["tb_erro"] = _msg_online(e)
        return st.rerun()
    if b["estado"] == "cancelada":
        _ss().pop("tb_on_pid", None)
        _ss()["tb_erro"] = "A sala foi cancelada."
        return st.rerun()
    if b["estado"] == "sala":
        st.markdown(f"<div class='tb-hero'><img src='{ART.uri('hero')}' alt='Trader Battle'></div>", unsafe_allow_html=True)
        _frag_sala(pid)
        st.button("Sair da sala", key="tb_voltar", icon=":material/logout:", width="stretch", on_click=_on_sair_sala, args=(pid,))
        return
    if b["p"]["fase"] == "fim":
        return _fim_online(b)
    st.markdown(_CSS_MESA, unsafe_allow_html=True)
    st.button("Voltar", key="tb_voltar", icon=":material/arrow_back:", on_click=_on_desanexar)
    _frag_mesa_online(pid)


# ------------------------------------------------------------------ TELA 1 · Central
def _n_reais(tf: str) -> int:
    k = f"tb_nreais_{tf}"
    if k not in _ss():
        try:
            _ss()[k] = len(TD.listar(tf))
        except Exception:
            _ss()[k] = 0
    return _ss()[k]


def _preparar_reais(tf: str) -> None:
    import analise_tecnica_app as ATA
    from datetime import datetime
    try:
        rel = TD.preparar(tf, lambda cod, per, iv: ATA._baixar(cod, per, "60m" if iv == "1h" else iv), datetime.now().isoformat(timespec="minutes"))
        _ss()["tb_prep"] = rel
        _ss().pop(f"tb_nreais_{tf}", None)
    except Exception as e:
        _ss()["tb_prep"] = {"erro": f"{e.__class__.__name__}"}


def _central() -> None:
    st.markdown(f"<div class='tb-hero'><img src='{ART.uri('hero')}' alt='Trader Battle'></div>", unsafe_allow_html=True)
    tf = st.segmented_control("Timeframe", list(TB.TIMEFRAMES), default="15m", key="tb_tf",
                              format_func=lambda k: TB.TIMEFRAMES[k]["nome"], label_visibility="collapsed") or "15m"
    if _n_reais(tf) < TB.RODADAS:
        st.markdown("<div class='tb-demo'>MODO DEMONSTRAÇÃO: ainda não há cenários históricos reais preparados para este timeframe. "
                    "Os gráficos desta partida são SIMULADOS e não são cotações reais.</div>", unsafe_allow_html=True)
    st.button("Jogar agora", key="tb_jogar", icon=":material/play_arrow:", width="stretch", on_click=_iniciar)
    _central_online()
    st.markdown(f"<div class='tb-chips'><div><b>2-4</b>jogadores (sala)</div><div><b>3</b>rodadas</div><div><b>{TB.T_ANALISE_S}s/{TB.T_REPLAY_S}s</b>análise e replay</div></div>", unsafe_allow_html=True)
    if _ss().get("tb_erro"):
        st.markdown(f"<div class='tb-er'>{_e(_ss().pop('tb_erro'))}</div>", unsafe_allow_html=True)
    with st.expander("Como funciona", icon=":material/help:"):
        st.markdown("<div class='tb-aviso'>Você recebe o gráfico de uma ação da B3 parado num ponto do passado e tem 120 s para analisar e registrar a estratégia "
                    "(direção, entrada, stop, alvo e confiança; aguardar também vale). Depois o servidor revela os candles seguintes em poucos segundos, e você vê se a leitura "
                    "se confirmou. Jogo educativo: nenhuma ordem real, nada de recomendação de investimento. "
                    "No modo individual a partida fica só neste navegador; se você atualizar a página, ela é perdida. Em sala com amigos (2 a 4 jogadores) a partida fica "
                    "guardada no servidor: dá para voltar a ela depois de atualizar a página.</div>", unsafe_allow_html=True)
    try:
        import usuarios
        admin = usuarios.pode("sistema.dados")
    except Exception:
        admin = False
    if admin:
        with st.expander("Preparar cenários reais (administração)", icon=":material/database:"):
            st.caption("Baixa o histórico gratuito UMA vez, valida candle a candle e guarda no banco. As partidas só leem o que já está guardado.")
            if st.button("Preparar agora", key="tb_preparar", on_click=_preparar_reais, args=(tf,)):
                pass
            rel = _ss().get("tb_prep")
            if rel:
                if rel.get("erro"):
                    st.markdown(f"<div class='tb-er'>Falhou ({_e(str(rel['erro']))}).</div>", unsafe_allow_html=True)
                else:
                    falhas = rel.get("falhas") or {}
                    st.markdown(f"<div class='tb-ok'>{rel.get('novos', 0)} cenário(s) novo(s) · {rel.get('total', 0)} guardado(s) · {len(falhas)} ativo(s) com falha</div>", unsafe_allow_html=True)
                    for cod, why in list(falhas.items())[:6]:
                        st.markdown(f"<div class='tb-cap'>{_e(cod)}: {_e(str(why))}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ TELA 2 · Análise
def _ferr_indicadores(v: dict) -> None:
    with st.popover("Indicadores", icon=":material/show_chart:"):
        st.toggle("Volume", value=True, key="tb_i_vol")
        if st.toggle("Média móvel simples", value=True, key="tb_i_sma"):
            st.number_input("Período da média simples", 2, 100, 20, key="tb_i_nsma")
        if st.toggle("Média móvel exponencial", value=False, key="tb_i_ema"):
            st.number_input("Período da média exponencial", 2, 100, 9, key="tb_i_nema")
        st.toggle("RSI (14)", value=False, key="tb_i_rsi")
        st.toggle("Suporte e resistência automáticos", value=False, key="tb_i_sr")
        st.toggle("Mexer no gráfico com o dedo", value=True, key="tb_i_mov", help="Desligue para rolar a página passando o dedo sobre o gráfico.")


def _marcas() -> dict:
    return _ss().setdefault("tb_marcas", {"niveis": [], "tendencias": [], "notas": []})


def _add_nivel() -> None:
    v = _ss().get("tb_mk_preco")
    if v:
        _marcas()["niveis"].append({"preco": float(v), "rotulo": (_ss().get("tb_mk_rot") or "")[:20]})


def _add_tend(cand: list[dict]) -> None:
    n = len(cand)
    a, b = int(_ss().get("tb_mk_a", 20)), int(_ss().get("tb_mk_b", 3))
    i1, i2 = n - 1 - a, n - 1 - b
    if 0 <= i1 < i2 < n:
        col = "l" if _ss().get("tb_mk_ap", "Fundos") == "Fundos" else "h"
        _marcas()["tendencias"].append({"i1": i1, "p1": cand[i1][col], "i2": i2, "p2": cand[i2][col]})
    else:
        _ss()["tb_erro"] = "Na linha de tendência, o candle A precisa vir antes do B (A com número maior de candles atrás)."


def _add_nota(cand: list[dict]) -> None:
    n = len(cand)
    a = int(_ss().get("tb_mk_na", 3))
    txt = (_ss().get("tb_mk_nt") or "").strip()
    if txt and 0 <= n - 1 - a < n:
        _marcas()["notas"].append({"i": n - 1 - a, "preco": cand[n - 1 - a]["c"], "texto": txt[:40]})


def _limpar_marcas() -> None:
    _ss()["tb_marcas"] = {"niveis": [], "tendencias": [], "notas": []}


def _ferr_marcar(v: dict) -> None:
    cand = v["candles"]
    m = _marcas()
    with st.popover("Marcar", icon=":material/draw:"):
        st.caption("Níveis, tendências e notas ficam registrados junto com a estratégia. (Os desenhos livres da barra do gráfico servem de rascunho e não são salvos.)")
        st.markdown("<div class='tb-h'>Nível de preço</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([1.2, 1])
        c1.number_input("Preço", min_value=0.0, value=None, step=0.01, format="%.2f", key="tb_mk_preco", label_visibility="collapsed", placeholder="Preço")
        c2.text_input("Nome", key="tb_mk_rot", label_visibility="collapsed", placeholder="Nome (opcional)", max_chars=20)
        st.button("Adicionar nível", key="tb_add_n", on_click=_add_nivel, width="stretch", disabled=len(m["niveis"]) >= TB.MAX_MARCAS["niveis"])
        st.markdown("<div class='tb-h'>Linha de tendência</div>", unsafe_allow_html=True)
        c1, c2, c3 = st.columns(3)
        c1.number_input("A (candles atrás)", 1, len(cand) - 1, 20, key="tb_mk_a")
        c2.number_input("B (candles atrás)", 0, len(cand) - 2, 3, key="tb_mk_b")
        c3.selectbox("Apoiar em", ["Fundos", "Topos"], key="tb_mk_ap")
        st.button("Adicionar tendência", key="tb_add_t", on_click=_add_tend, args=(cand,), width="stretch", disabled=len(m["tendencias"]) >= TB.MAX_MARCAS["tendencias"])
        st.markdown("<div class='tb-h'>Anotação</div>", unsafe_allow_html=True)
        c1, c2 = st.columns([2, 1])
        c1.text_input("Texto", key="tb_mk_nt", label_visibility="collapsed", placeholder="Texto curto", max_chars=40)
        c2.number_input("Candles atrás", 0, len(cand) - 1, 3, key="tb_mk_na", label_visibility="collapsed")
        st.button("Adicionar anotação", key="tb_add_a", on_click=_add_nota, args=(cand,), width="stretch", disabled=len(m["notas"]) >= TB.MAX_MARCAS["notas"])
        st.caption(f"{len(m['niveis'])} nível(is) · {len(m['tendencias'])} tendência(s) · {len(m['notas'])} nota(s)")
        st.button("Limpar marcações", key="tb_lim_m", on_click=_limpar_marcas, width="stretch")


def _mudar_conf(d: int) -> None:
    _ss()["tb_conf"] = max(1, min(5, int(_ss().get("tb_conf", 3)) + d))


def _montar_est(ref: float) -> dict:
    s = _ss()
    return {"direcao": s.get("tb_dir"), "tipo": s.get("tb_tipo"), "confianca": int(s.get("tb_conf", 3)),
            "entrada": s.get("tb_ent"), "stop": s.get("tb_stop"), "alvo": s.get("tb_alvo")}


def _salvar(p: dict, ref: float) -> None:
    try:
        TB.salvar_estrategia(p, _jogador(), _montar_est(ref), _marcas(), ref, _agora())
        _ss()["tb_salva"] = True
        _ss().pop("tb_erro", None)
    except TB.ErroTrader as e:
        _ss()["tb_erro"] = str(e)


def _replay_ja(p: dict) -> None:
    try:
        TB.iniciar_replay(p, _jogador(), _agora())
    except TB.ErroTrader as e:
        _ss()["tb_erro"] = str(e)


@st.fragment(run_every=POLL_S)
def _frag_relogio_analise() -> None:
    p = _partida()
    if not p:
        return
    TB.avancar(p, _agora(), _cen())
    if p["fase"] != "analise":
        return st.rerun()
    v = TB.visao(p, _cenario_atual(p), _agora(), _jogador())
    st.markdown(_topo(v, v["segundos"], "análise"), unsafe_allow_html=True)
    if v["segundos"] <= 15 and not v["estrategia"]:
        st.markdown("<div class='tb-er'>⏱ Poucos segundos! Salve a estratégia ou a rodada conta como Aguardar.</div>", unsafe_allow_html=True)


def _analise_classica(p: dict) -> None:
    """Montagem por formulário (plano B: usada se a mesa de operações não estiver disponível)."""
    v = TB.visao(p, _cenario_atual(p), _agora(), _jogador())
    ref = v["candles"][-1]["c"]
    _voltar()
    _frag_relogio_analise()
    if v["demo"]:
        st.markdown("<div class='tb-demo'>DADOS SIMULADOS (modo demonstração)</div>", unsafe_allow_html=True)
    _grafico(v, _marcas(), None, chave="tb_graf_a")
    st.markdown("<div class='tb-cap'>Não atualize a página: a partida em andamento não é salva.</div>", unsafe_allow_html=True)
    with st.container(key="tb_ferr"):
        c1, c2, c3 = st.columns([0.7, 1.2, 1])
        c1.markdown(f"<div class='tb-rod' style='justify-content:center;height:38px'>{_e(v['tf'])}</div>", unsafe_allow_html=True)
        with c2:
            _ferr_indicadores(v)
        with c3:
            _ferr_marcar(v)
    with st.container(key="tb_estr"):
        st.markdown("<div class='tb-h'>Sua Estratégia</div>", unsafe_allow_html=True)
        st.segmented_control("Direção", ["alta", "baixa", "lateral"], key="tb_dir", label_visibility="collapsed",
                             format_func=lambda k: {"alta": "▲ Alta", "baixa": "▼ Baixa", "lateral": "↔ Lateral"}[k])
        st.segmented_control("Estratégia", list(TB.ESTRATEGIAS), key="tb_tipo", label_visibility="collapsed", format_func=lambda k: TB.ROTULO_ESTRATEGIA[k])
        operar = _ss().get("tb_tipo") not in (None, "aguardar") and _ss().get("tb_dir") in ("alta", "baixa")
        if operar:
            c1, c2, c3 = st.columns(3)
            c1.number_input("Entrada", min_value=0.0, value=None, step=0.01, format="%.2f", key="tb_ent", placeholder=f"{ref:.2f}")
            c2.number_input("Stop", min_value=0.0, value=None, step=0.01, format="%.2f", key="tb_stop")
            c3.number_input("Alvo", min_value=0.0, value=None, step=0.01, format="%.2f", key="tb_alvo")
        elif _ss().get("tb_tipo") == "aguardar":
            st.markdown("<div class='tb-cap'>Aguardar é uma decisão válida: você fica de fora desta rodada.</div>", unsafe_allow_html=True)
        with st.container(key="tb_conf_l"):
            c1, c2, c3 = st.columns([2, 1, 1])
            c1.markdown(f"<div class='tb-h' style='margin-top:6px'>Confiança: {int(_ss().get('tb_conf', 3))}/5</div>", unsafe_allow_html=True)
            c2.button("−", key="tb_conf_m", on_click=_mudar_conf, args=(-1,), width="stretch")
            c3.button("+", key="tb_conf_p", on_click=_mudar_conf, args=(1,), width="stretch")
        st.button("Salvar Estratégia", key="tb_salvar", icon=":material/check:", width="stretch", on_click=_salvar, args=(p, ref))
        if _ss().get("tb_erro"):
            st.markdown(f"<div class='tb-er'>{_e(_ss().pop('tb_erro'))}</div>", unsafe_allow_html=True)
        elif p["estrategias"].get(f"{p['rodada']}:{_jogador()}"):
            st.markdown("<div class='tb-ok'>✔ Estratégia salva. Você pode ajustar até o tempo acabar.</div>", unsafe_allow_html=True)
            st.button("Iniciar replay agora", key="tb_replay_ja", icon=":material/fast_forward:", width="stretch", on_click=_replay_ja, args=(p,))


_CSS_MESA = ("<style>" + "".join(l.strip() for l in f"""
{_P} .block-container,{_P} [data-testid="stMainBlockContainer"]{{padding-top:.5rem !important;padding-bottom:.2rem !important}}
{_P} [data-testid="stMainBlockContainer"] [data-testid="stVerticalBlock"]{{gap:.3rem !important}}
{_P} .st-key-tb_voltar button{{min-height:32px !important;height:32px !important;padding:0 12px !important}}
{_P} iframe[data-testid="stCustomComponentV1"]{{border:0 !important;display:block;width:100%}}
{_P} .st-key-tb_fragsil{{display:none !important}}
""".splitlines()) + "</style>")


@st.fragment(run_every=2)
def _frag_fase_silencioso() -> None:
    """Sem desenho: só garante que, quando o relógio do servidor encerrar a análise, a tela passe para o replay."""
    p = _partida()
    if not p:
        return
    TB.avancar(p, _agora(), _cen())
    if p["fase"] != "analise":
        return st.rerun()


def _analise(p: dict) -> None:
    """Análise em tela útil inteira: gráfico com as marcações de Entrada, Stop e Alvo feitas direto nele (componente trader_front)."""
    if _ss().get("tb_sem_mesa") or not TG.disponivel():
        return _analise_classica(p)
    v = TB.visao(p, _cenario_atual(p), _agora(), _jogador())
    ref = v["candles"][-1]["c"]
    chave = f"tb_mesa_{p['id']}_{p['rodada']}"
    est = _ss().setdefault(f"tb_ev_{chave}", {})
    st.markdown(_CSS_MESA, unsafe_allow_html=True)
    _voltar()
    try:
        val = TG.mesa(chave, **TG.args_mesa(v, p, est, _agora()))
    except Exception:
        _ss()["tb_sem_mesa"] = True                       # componente indisponível neste ambiente: cai para o formulário
        return st.rerun()
    if TG.processar(p, val, est, _jogador(), ref, _agora()):
        return st.rerun()
    with st.container(key="tb_fragsil"):
        _frag_fase_silencioso()


# ------------------------------------------------------------------ MESA CONTÍNUA · análise, replay e resultado no MESMO gráfico
@st.fragment(run_every=1)
def _frag_mesa() -> None:
    """Um único componente por partida (chave estável): as 3 rodadas seguem em sequência cronológica no mesmo gráfico, sem fechar nem reabrir.
    O servidor decide o que aparece (candles revelados e entradas de adversários autorizadas); o componente só desenha."""
    p = _partida()
    if not p:
        return
    ag, jog = _agora(), _jogador()
    TB.avancar(p, ag, _cen())
    if p["fase"] == "fim":
        return st.rerun()
    cen = _cenario_atual(p)
    if p["fase"] == "resultado" and f"{p['rodada']}:{jog}" not in p["resultados"]:
        TB.fechar_rodada(p, cen)
    est = _ss().setdefault(f"tb_ev_{p['id']}", {})
    v = TB.visao(p, cen, ag, jog)
    ref = v["candles"][-1]["c"]
    try:
        val = TG.mesa(f"tb_mesa_{p['id']}", **TG.args_mesa(v, p, est, ag))
    except Exception:
        _ss()["tb_sem_mesa"] = True                       # componente indisponível neste ambiente: cai para as telas clássicas
        return st.rerun()
    if TG.processar(p, val, est, jog, ref, ag):
        return st.rerun(scope="app" if p["fase"] == "fim" else "fragment")


def _mesa_continua(p: dict) -> None:
    st.markdown(_CSS_MESA, unsafe_allow_html=True)
    _voltar()
    _frag_mesa()


# ------------------------------------------------------------------ TELA 3 · Replay
@st.fragment(run_every=POLL_S)
def _frag_replay() -> None:
    p = _partida()
    if not p:
        return
    TB.avancar(p, _agora(), _cen())
    if p["fase"] != "replay":
        return st.rerun()
    cen = _cenario_atual(p)
    v = TB.visao(p, cen, _agora(), _jogador())
    est = v["estrategia"] or {}
    st.markdown(_topo(v, v["segundos"], "replay"), unsafe_allow_html=True)
    _grafico(v, est.get("marcas") or {"niveis": [], "tendencias": [], "notas": []}, est if est.get("entrada") else None, chave="tb_graf_r")
    nd = {"alta": "Alta", "baixa": "Baixa", "lateral": "Lateral"}
    if est.get("sem_registro"):
        st.markdown("<div class='tb-aviso'>🔒 Estratégia travada: você não registrou nada, então esta rodada conta como Aguardar.</div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='tb-ok'>🔒 Estratégia travada · {_e(nd.get(est.get('direcao'), ''))} · {_e(TB.ROTULO_ESTRATEGIA.get(est.get('tipo'), ''))} · confiança {est.get('confianca')}/5</div>",
                    unsafe_allow_html=True)
    frac = min(1.0, (TB.T_REPLAY_S - v["segundos"]) / TB.T_REPLAY_S)
    st.progress(frac, text=f"Replay em andamento · {v['revelados']}/{v['total_replay']} candles revelados")
    st.markdown("<div class='tb-card'><b>Acompanhe o movimento</b><p>Os candles aparecem na ordem em que aconteceram. Veja se a sua estratégia se confirma!</p></div>", unsafe_allow_html=True)


@st.fragment(run_every=1)
def _frag_replay_mesa() -> None:
    """Replay na mesa (canvas): a tela continua montada e só recebe os candles que o servidor já liberou; a animação é local e suave."""
    p = _partida()
    if not p:
        return
    TB.avancar(p, _agora(), _cen())
    if p["fase"] != "replay":
        return st.rerun()
    v = TB.visao(p, _cenario_atual(p), _agora(), _jogador())
    try:
        TG.mesa(f"tb_mesa_r_{p['id']}_{p['rodada']}", **TG.args_mesa(v, p, {}, _agora()))
    except Exception:
        _ss()["tb_sem_mesa"] = True
        return st.rerun()


def _replay(p: dict) -> None:
    if _ss().get("tb_sem_mesa") or not TG.disponivel():
        _voltar()
        return _frag_replay()
    st.markdown(_CSS_MESA, unsafe_allow_html=True)
    _voltar()
    _frag_replay_mesa()


# ------------------------------------------------------------------ TELA 4 · Resultado da rodada
def _proxima(p: dict) -> None:
    TB.proxima_rodada(p, _agora())
    _zerar_rascunho_rodada()


def _zerar_rascunho_rodada() -> None:
    for k in [k for k in _ss() if k.startswith("tb_") and not k.startswith("tb_i_") and k not in ("tb_p", "tb_cen", "tb_tf")]:
        _ss().pop(k, None)


def _resultado(p: dict) -> None:
    cen = _cenario_atual(p)
    if f"{p['rodada']}:{_jogador()}" not in p["resultados"]:
        TB.fechar_rodada(p, cen)
    v = TB.visao(p, cen, _agora(), _jogador())
    r = v["resultado"]
    st.markdown(_topo(v, None, "resultado"), unsafe_allow_html=True)
    est = r["estrategia"]
    _grafico(v, est.get("marcas") or {"niveis": [], "tendencias": [], "notas": []}, est if est.get("entrada") else None, divisor=True, chave="tb_graf_x")
    fx = {True: "faixa_vitoria", False: "faixa_derrota"}.get(r.get("acertou_direcao"), "faixa_empate")
    st.markdown(f"<div class='tb-faixa'>{CT.img(fx, alt='')}</div>", unsafe_allow_html=True)
    st.markdown(f"<div class='tb-pts'><div class='n'>{r['pontos']:.1f}</div><small>pontos nesta rodada · total {p['pontos'][_jogador()]:.1f}</small></div>", unsafe_allow_html=True)
    with st.expander("Raio-X da rodada", icon=":material/search:", expanded=False):
        for titulo, txt in TB.explicar(r):
            st.markdown(f"<div class='tb-card'><b>{_e(titulo)}</b><p>{_e(txt)}</p></div>", unsafe_allow_html=True)
        st.markdown(f"<div class='tb-cap'>{'Dados simulados (modo demonstração).' if v['demo'] else 'Fonte: ' + _e(v['fonte']) + '.'} Pontuação educativa; não mede lucro real nem é recomendação.</div>",
                    unsafe_allow_html=True)
    ultima = p["rodada"] >= TB.RODADAS
    st.button("Ver resultado final" if ultima else "Próxima rodada", key="tb_prox", icon=":material/arrow_forward:", width="stretch", on_click=_proxima, args=(p,))


# ------------------------------------------------------------------ TELA 5 · Fim da partida
def _de_novo() -> None:
    _sair()
    _iniciar()


def _fim(p: dict) -> None:
    j = _jogador()
    linhas = "".join(f"<div class='tb-lin'>Rodada {k + 1} · {_e(_cen()[cid]['ticker'])}<span>{p['resultados'].get(f'{k + 1}:{j}', {}).get('pontos', 0):.1f}</span></div>"
                     for k, cid in enumerate(p["cenarios"]))
    st.markdown(f"<div class='tb-troph'><img src='{ART.uri('trofeu')}' alt=''></div>"
                f"<div class='tb-pts'><div class='n'>{p['pontos'][j]:.1f}</div><small>pontos em {TB.RODADAS} rodadas{' · cenários simulados' if p['demo'] else ''}</small></div>"
                f"<div class='tb-card'>{linhas}</div>", unsafe_allow_html=True)
    st.button("Jogar novamente", key="tb_de_novo", icon=":material/replay:", width="stretch", on_click=_de_novo)
    st.button("Voltar ao início do Trader Battle", key="tb_voltar", icon=":material/home:", width="stretch", on_click=_sair)


# ------------------------------------------------------------------ página
def pagina_trader() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    p = _partida()
    em = _email_online()
    if em and not p and not _ss().get("tb_on_visto"):
        _ss()["tb_on_visto"] = True                              # voltou à página (ou atualizou): retoma a partida em sala/andamento, se houver
        try:
            ativa = TOD.partida_ativa(em)
            if ativa:
                _ss()["tb_on_pid"] = ativa
        except Exception:
            pass
    if em and not p and _ss().get("tb_on_pid"):
        return _pagina_online(_ss()["tb_on_pid"])
    if not p:
        _central()
        return
    try:
        TB.avancar(p, _agora(), _cen())
        if p["fase"] != "fim" and not _ss().get("tb_sem_mesa") and TG.disponivel():
            _mesa_continua(p)
        else:
            {"analise": _analise, "replay": _replay, "resultado": _resultado, "fim": _fim}[p["fase"]](p)
    except KeyError:                                           # cenário sumiu da sessão: volta ao início sem derrubar a página
        _sair()
        return st.rerun()
