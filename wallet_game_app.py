"""Telas novas da Wallet Game: resumo (rank, bônus e sequência), missões e conquistas. A lógica e os pagamentos ficam em wallet_game.py (servidor);
aqui só se desenha e se chama. A tela nunca envia valor, data ou rank: tudo é decidido no servidor."""
from __future__ import annotations

import html
import time
from datetime import date, datetime, timezone

import streamlit as st

import banco
import estilo_app as ES
import jornada_arte as ART
import moedas_arte as MA
import wallet_game as W
from wallet_game import moeda
from design import componentes as DC

CH = "wg_res"
CSS = """<style>
html body .stApp.stApp .wg-hero{background:linear-gradient(135deg,#34286F,#1B1545);border:1px solid #F2B84B44;border-radius:18px;padding:10px 12px;margin:4px 0 8px;}
html body .stApp.stApp .wg-top svg{width:54px;height:54px;flex:none;}
html body .stApp.stApp .wg-top{display:flex;align-items:center;gap:12px;}
html body .stApp.stApp .wg-top .tx{flex:1;min-width:0;}
html body .stApp.stApp .wg-top .rk{font-size:1.1rem;font-weight:900;color:#F6F3FF;line-height:1.1;}
html body .stApp.stApp .wg-top .pt{color:#FFD66B;font-weight:800;font-size:1.05rem;}
html body .stApp.stApp .wg-top .sub{color:#CFC8EE;font-size:.82rem;margin-top:2px;}
html body .stApp.stApp .wg-bar{height:12px;border-radius:999px;background:#2A2058;overflow:hidden;margin:10px 0 4px;}
html body .stApp.stApp .wg-bar i{display:block;height:100%;border-radius:999px;background:linear-gradient(90deg,#8BE04E,#3DDC97);}
html body .stApp.stApp .wg-leg{display:flex;justify-content:space-between;color:#CFC8EE;font-size:.78rem;gap:8px;}
html body .stApp.stApp .wg-fala{display:flex;align-items:center;gap:10px;background:#241C4D;border:1px solid #3B3170;border-radius:16px;padding:8px 12px;margin:8px 0;}
html body .stApp.stApp .wg-fala .b{background:#fff;color:#1B1545;border-radius:14px;padding:8px 12px;font-weight:700;font-size:.9rem;}
html body .stApp.stApp .wg-fala.festa{border-color:#F2B84B;background:linear-gradient(135deg,#3A2A75,#241C4D);}
html body .stApp.stApp .wg-card{background:#241C4D;border:1px solid #3B3170;border-radius:16px;padding:12px 14px;margin:8px 0;box-sizing:border-box;max-width:100%;}
html body .stApp.stApp .wg-card .t{font-weight:800;color:#F6F3FF;}
html body .stApp.stApp .wg-card .d{color:#CFC8EE;font-size:.84rem;margin-top:2px;}
html body .stApp.stApp .wg-card .m{color:#9C94C9;font-size:.78rem;margin-top:6px;}
html body .stApp.stApp .wg-card.ok{border-color:#3DDC9788;}
html body .stApp.stApp .wg-card.off{opacity:.55;}
html body .stApp.stApp .wg-chip{display:inline-block;border-radius:999px;padding:2px 9px;font-size:.74rem;font-weight:800;margin:4px 4px 0 0;background:#2A2058;color:#FFD66B;border:1px solid #F2B84B55;}
html body .stApp.stApp .wg-chip.v{color:#8BE04E;border-color:#8BE04E66;}
html body .stApp.stApp .wg-chip.c{color:#B9B2E3;border-color:#5B5190;}
html body .stApp.stApp .wg-dias{display:flex;gap:6px;margin:10px 0 4px;}
html body .stApp.stApp .wg-dias i{flex:1;height:34px;border-radius:10px;background:#2A2058;border:1px solid #3B3170;display:flex;align-items:center;justify-content:center;font-style:normal;color:#9C94C9;font-weight:800;font-size:.8rem;}
html body .stApp.stApp .wg-dias i.on{background:linear-gradient(135deg,#FF9B3D,#FFD66B);color:#3A2300;border-color:#FFD66B;}
html body .stApp.stApp .wg-dias i.hj{outline:2px solid #8BE04E;}
html body .stApp.stApp .wg-emb{display:flex;align-items:center;gap:12px;}
html body .stApp.stApp .wg-emb .e{width:46px;height:46px;border-radius:14px;display:flex;align-items:center;justify-content:center;font-size:1.6rem;flex:none;background:#2A2058;border:2px solid var(--c,#8B6CFF);}
html body .stApp.stApp .wg-sec{font-weight:800;color:#F6F3FF;margin:14px 2px 4px;}
html body .stApp.stApp .wg-aviso{color:#B7AEE0;font-size:.78rem;line-height:1.45;margin:10px 0 8px;padding:10px 12px;background:#1B1545;border:1px solid #3B3170;border-left:3px solid #F2B84B;border-radius:12px;box-sizing:border-box;max-width:100%;}
html body .stApp.stApp .wg-leg span{color:#CFC8EE !important;-webkit-text-fill-color:#CFC8EE;}
</style>"""
AVISO = ("Dinheiro virtual, TickerCoins e XP são coisas separadas. O dinheiro virtual vale só dentro da Wallet Game, sem conversão em dinheiro real. "
         "Simulação educacional, sem recomendação de investimento.")


def _e(x) -> str:
    return html.escape(str(x))


def _data(iso) -> str:
    try:
        return datetime.fromisoformat(str(iso).replace("Z", "+00:00")).astimezone(timezone(W.timedelta(hours=-3))).strftime("%d/%m/%Y")
    except Exception:
        return str(iso)[:10]


def _dia_br(d: str) -> str:
    try:
        return date.fromisoformat(d).strftime("%d/%m")
    except Exception:
        return d


# ------------------------------------------------------------------ dados (cache curto na sessão; ações limpam)
def resultado(a, forcar: bool = False) -> dict:
    """Resultado de `W.avaliar` para a conta logada, guardado 30 s na sessão. Eventos (rank, missão, conquista) são mostrados uma vez só."""
    c = st.session_state.get(CH)
    if forcar or not c or c["email"] != a.email or time.time() - c["t"] > 30:
        res = W.avaliar(a.email, a.id)
        _pagar_xp(res.get("xp_novo", 0))
        c = {"email": a.email, "t": time.time(), "res": res, "festa": list(res["eventos"])}
        st.session_state[CH] = c
    return c["res"]


def esquecer() -> None:
    st.session_state.pop(CH, None)


def _pagar_xp(n: int) -> None:
    """Soma XP ao progresso de estudo da pessoa (separado do dinheiro virtual e das TickerCoins). Falha aqui nunca derruba a tela."""
    if n <= 0:
        return
    try:
        import educacao_app as EA
        import jornada as JO
        p = dict(EA.prog())
        j = JO.normalizar_jornada(p.get("jornada"))
        hoje = W.hoje_brt().isoformat()
        j["xp"] += int(n)
        j["xp_dia"][hoje] = int(j["xp_dia"].get(hoje, 0)) + int(n)
        p["jornada"] = j
        EA._set(p)
    except Exception as e:
        banco.registrar_erro("wallet_game_app.xp", e)


# ------------------------------------------------------------------ peças visuais
def emblema_rank(cor: str, nome: str, tam: int = 64) -> str:
    """Emblema do rank (escudo com a cor do nível e a inicial)."""
    ini = _e(nome[:1])
    return (f"<svg width='{tam}' height='{tam}' viewBox='0 0 64 64' role='img' aria-label='Rank {_e(nome)}'>"
            f"<defs><linearGradient id='g{ini}{cor[1:]}' x1='0' y1='0' x2='1' y2='1'><stop offset='0' stop-color='{cor}'/><stop offset='1' stop-color='#1B1545'/></linearGradient></defs>"
            f"<path d='M32 3 L57 12 V32 C57 46 46 56 32 61 C18 56 7 46 7 32 V12 Z' fill='url(#g{ini}{cor[1:]})' stroke='{cor}' stroke-width='2.5'/>"
            f"<text x='32' y='41' text-anchor='middle' font-family='sans-serif' font-weight='900' font-size='26' fill='#fff'>{ini}</text></svg>")


def _fala(texto: str, festa: bool = False, pose: str | None = None) -> str:
    return (f"<div class='wg-fala{' festa' if festa else ''}'><div>{ART.mascote(festa=festa, tamanho=88, humor=pose or ('festa' if festa else None))}</div>"
            f"<div class='b'>{_e(texto)}</div></div>")


def _chips(rec: dict) -> str:
    out = ""
    if rec.get("xp"):
        out += f"<span class='wg-chip v'>+{int(rec['xp'])} XP</span>"
    if rec.get("tc"):
        out += f"<span class='wg-chip'>{MA.img('tc', 16)} +{int(rec['tc'])} TC</span>"
    if rec.get("capital"):
        out += f"<span class='wg-chip c'>+{moeda(rec['capital'])}</span>"
    return out


def _animar() -> bool:
    try:
        import fx_arte as FX
        return FX.animar_padrao(st.session_state)
    except Exception:
        return True


def _festa_rank(x: dict) -> str:
    """Promoção de rank com a animação do fx_arte (some se animações desligadas: fica só o resultado). Cai no balão simples se algo falhar."""
    try:
        import fx_arte as FX
        ids = [r[0] for r in W.RANKS]
        novo = str(x.get("nome", "")).lower()
        if novo not in ids:
            raise ValueError(novo)
        ant = ids[ids.index(novo) - 1] if ids.index(novo) > 0 else None
        return FX.CSS + FX.html_rank(novo, ant, animar=_animar())
    except Exception:
        return _fala(f"Subiu de rank! Você agora é {x.get('nome', '')}. Muito bem!", True, "conquistas")


def _festa_missao(x: dict) -> str:
    """Prêmios da missão (XP, TC, T$) em fichas animadas. Vazio se a missão não pagou nada ou se o componente falhar."""
    try:
        import fx_arte as FX
        itens = []
        if x.get("xp"):
            itens.append({"sprite": "xp", "valor": f"+{int(x['xp'])}", "rotulo": "XP"})
        if x.get("tc"):
            itens.append({"sprite": "tc", "valor": f"+{int(x['tc'])}", "rotulo": "TickerCoins"})
        if x.get("capital"):
            itens.append({"sprite": "ts", "valor": f"+{moeda(x['capital'])}", "rotulo": "Dinheiro virtual"})
        if not itens:
            return ""
        return FX.CSS + FX.html_recompensa("Missão concluída!", itens, str(x.get("nome", "")), "comum", animar=_animar())
    except Exception:
        return ""


def festas() -> None:
    """Mensagens de comemoração (subiu de rank, missão ou conquista) logo depois da avaliação. Aparecem uma única vez."""
    c = st.session_state.get(CH)
    if not c or not c.get("festa"):
        return
    ev, c["festa"] = c["festa"], []
    for x in ev:
        if x["tipo"] == "rank":
            st.markdown(_festa_rank(x), unsafe_allow_html=True)
            st.toast(f"Novo rank: {x['nome']}", icon="🏆")
        elif x["tipo"] == "conquista":
            extra = f" (+{x['tc']} TC)" if x.get("tc") else ""
            st.markdown(_fala(f"Conquista desbloqueada: {x['nome']}{extra}", True, "conquistas"), unsafe_allow_html=True)
            st.toast(f"Conquista: {x['nome']}", icon=x.get("emblema") or "🏅")
        elif x["tipo"] == "missao":
            partes = [f"+{x['xp']} XP"] if x.get("xp") else []
            if x.get("tc"):
                partes.append(f"+{x['tc']} TC")
            if x.get("capital"):
                partes.append(f"+{moeda(x['capital'])}")
            st.markdown(_fala(f"Missão concluída: {x['nome']}. " + " · ".join(partes), False, "wallet") + _festa_missao(x), unsafe_allow_html=True)


# ------------------------------------------------------------------ resumo (sempre no topo)
def _resgatar(a) -> None:
    r = W.resgatar_bonus(a.email, a.id)
    st.session_state["wg_bonus_res"] = r
    esquecer()
    try:
        import tickercoins_app
        tickercoins_app.esquecer_saldo()
    except Exception:
        pass


def aviso() -> None:
    """Aviso legal da Wallet Game, no fim da página (continua visível em todas as seções)."""
    st.markdown(f"<div class='wg-aviso'>{_e(AVISO)}</div>", unsafe_allow_html=True)


def resumo(a, res: dict, apelido: str = "", hero: bool = True, bonus_bloco: bool = True) -> None:
    """Topo da Wallet Game. `hero`: cartão de rank; `bonus_bloco`: botão e mensagem do bônus. Cada seção pede só o que é dela."""
    st.markdown(CSS, unsafe_allow_html=True)
    festas()
    rk, seq = res["rank"], res["seq"]
    est = res["estado"]
    barra = ""
    if rk["proximo"]:
        barra = (f"<div class='wg-bar'><i style='width:{rk['progresso'] * 100:.1f}%'></i></div>"
                 f"<div class='wg-leg'><span>{_e(rk['nome'])}</span><span>faltam {moeda(rk['faltam'])} para {_e(rk['proximo'])}</span></div>")
    else:
        barra = "<div class='wg-bar'><i style='width:100%'></i></div><div class='wg-leg'><span>Rank máximo alcançado</span></div>"
    if hero:
      st.markdown(
        f"<div class='wg-hero'><div class='wg-top'>{emblema_rank(rk['cor'], rk['nome'])}<div class='tx'><div class='rk'>Rank {_e(rk['nome'])}</div>"
        f"<div class='pt'>{MA.img('ts', 24)} {moeda(rk['patrimonio'])}</div><div class='sub'>{_e(apelido) + ' · ' if apelido else ''}maior rank: {_e(rk['max_nome'])}</div></div></div>{barra}</div>",
        unsafe_allow_html=True)
    if not bonus_bloco:
        return
    bonus = st.session_state.pop("wg_bonus_res", None)
    if bonus:
        if bonus.get("ok"):
            extra = (" " + " · ".join(bonus["extras"])) if bonus.get("extras") else ""
            tc = f" +{bonus['tc']} TC!" if bonus.get("tc") else ""
            st.markdown(_fala(f"Bônus resgatado: {moeda(bonus['valor'])} (dia {bonus['seq']}).{extra}{tc} Volte amanhã!", True), unsafe_allow_html=True)
        else:
            st.warning(bonus.get("erro", "Não foi possível resgatar agora."))
    if not seq["resgatou_hoje"]:                       # já resgatado: o aviso some da tela (a data do próximo fica na aba Bônus)
        st.button(f"Resgatar bônus de hoje ({moeda(W.config()['bonus']['diario'])})", key="wg_resgatar", type="primary", width="stretch",
                  on_click=_resgatar, args=(a,))


# ------------------------------------------------------------------ seções
def _ranking_liga(res: dict) -> None:
    """Ranking de cada liga (Bronze a Mestre) por patrimônio. Hoje com participantes de DEMONSTRAÇÃO, avisados na tela."""
    import ranking_ligas as RL
    rk = res["rank"]
    st.markdown("<div class='wg-sec'>Ranking por liga</div>", unsafe_allow_html=True)
    nomes = [n for n, _m, _c in rk["faixas"]]
    sel = ES.abas("wg_liga_sel", nomes, default=nomes[rk["idx"]], colunas=3)
    i = nomes.index(sel)
    mn = rk["faixas"][i][1]
    pr = rk["faixas"][i + 1][1] if i + 1 < len(rk["faixas"]) else None
    st.caption(f"Liga {sel}: " + (f"{moeda(mn)} ou mais" if pr is None else (f"até {moeda(pr - 1)}" if i == 0 else f"{moeda(mn)} a {moeda(pr - 1)}")) + " de patrimônio.")
    try:
        apelido = (res.get("apelido") or "")
    except Exception:
        apelido = ""
    itens = RL.montar(rk["faixas"], i, {"apelido": apelido, "patrimonio": rk["patrimonio"]})
    if not itens:
        st.info("Ainda não há participantes nesta liga.")
        return
    st.markdown(DC.lista_ranking([{"pos": x["pos"], "nome": x["apelido"] + (" · demonstração" if x["demo"] else ""), "valor": moeda(x["patrimonio"]),
                                   "sub": "patrimônio na carteira virtual", "tom": 1, "voce": bool(x.get("eu"))} for x in itens], medalhas=True),
                unsafe_allow_html=True)
    if RL.DEMO:
        st.caption("Participantes marcados como demonstração são fictícios, com valores inventados só para simular o ranking. Carteira virtual, sem dinheiro real.")


def aba_rank(res: dict) -> None:
    rk = res["rank"]
    st.markdown(DC.grade([DC.indicador("Rank atual", rk["nome"]), DC.indicador("Maior rank", rk["max_nome"]),
                          DC.indicador("Patrimônio", moeda(rk["patrimonio"])),
                          DC.indicador("Resultado simulado", f"{res['resultado']:+.2f}%".replace(".", ","), res["resultado"],
                                       detalhe="Sem contar bônus")], 2), unsafe_allow_html=True)
    _ranking_liga(res)
    st.markdown("<div class='wg-aviso'>O rank acompanha seu patrimônio (caixa + valor de mercado dos ativos). Se o patrimônio cair, o rank atual cai, "
                "mas o maior rank que você alcançou fica registrado. Quem começou com T$ 100.000 é medido em faixas proporcionais.</div>", unsafe_allow_html=True)


def aba_bonus(a, res: dict) -> None:
    seq, cfg = res["seq"], W.config()["bonus"]
    atual = seq["atual"]
    marcados = atual if seq["resgatou_hoje"] else atual
    pos7 = (atual - 1) % 7 + 1 if atual else 0
    caixas = ""
    for d in range(1, 8):
        on = atual > 0 and d <= pos7
        caixas += f"<i class='{'on' if on else ''}{' hj' if (d == pos7 + 1 and not seq['resgatou_hoje']) or (seq['resgatou_hoje'] and d == pos7) else ''}'>{d}</i>"
    st.markdown(f"<div class='wg-card'><div class='t'>🔥 Sequência: {atual} {'dia' if atual == 1 else 'dias'}</div>"
                f"<div class='d'>Melhor sequência: {seq['melhor']} · total de resgates: {seq['total']}</div><div class='wg-dias'>{caixas}</div>"
                f"<div class='m'>Perdeu um dia? A sequência volta ao dia 1. Resgate todo dia (a virada é à meia-noite de Brasília).</div></div>", unsafe_allow_html=True)
    ciclos = cfg["ciclos"]
    st.markdown(f"<div class='wg-card'><div class='t'>{MA.img('ts', 22)} Como funciona o bônus</div><div class='d'>{moeda(cfg['diario'])} por dia. No 7º dia seguido, mais {moeda(cfg['extra_7'])}. "
                f"No 14º dia: +{moeda(ciclos['14']['capital'])} e {ciclos['14']['tc']} TC. No 30º: +{moeda(ciclos['30']['capital'])} e {ciclos['30']['tc']} TC.</div>"
                f"<div class='m'>O valor entra no saldo disponível da carteira virtual. Não vale como resultado de investimento e não conta no ranking por %.</div></div>",
                unsafe_allow_html=True)
    st.markdown("<div class='wg-sec'>Histórico de bônus</div>", unsafe_allow_html=True)
    hist = W.historico_bonus(a.email, 15)
    if not hist:
        st.markdown("<div class='wg-card'><div class='d'>Nenhum bônus resgatado ainda.</div></div>", unsafe_allow_html=True)
    for r in hist:
        st.markdown(f"<div class='wg-card ok'><div class='t'>{_e(r['descricao'])} <span style='float:right;color:#8BE04E'>+{_e(moeda(r['valor']))}</span></div>"
                    f"<div class='m'>{_e(_dia_br(r['dia']))}</div></div>", unsafe_allow_html=True)


_GRUPOS = (("dia", "Diárias"), ("semana", "Semanais"), ("especial", "Especiais"))
_STATUS = {"disponivel": "Disponível", "andamento": "Em andamento", "concluida": "Concluída"}


def aba_missoes(res: dict) -> None:
    for per, titulo in _GRUPOS:
        st.markdown(f"<div class='wg-sec'>{titulo}</div>", unsafe_allow_html=True)
        for m in [x for x in res["missoes"] if x["periodo"] == per]:
            pct = 100 if m["feita"] else min(100.0, m["progresso"] / m["meta"] * 100)
            prog = "Concluída" if m["feita"] else (f"{m['progresso']:.0f} de {m['meta']}" if m["id"] != "e_rent5" else f"{res['resultado']:+.1f}% de +{m['meta']}%")
            st.markdown(f"<div class='wg-card{' ok' if m['feita'] else ''}'><div class='t'>{_e(m['nome'])} <span class='wg-chip{' v' if m['feita'] else ' c'}' style='float:right'>{_STATUS[m['status']]}</span></div>"
                        f"<div class='d'>{_e(m['descricao'])}</div><div class='m'>Objetivo: {_e(m['objetivo'])} · {_e(prog)}</div>"
                        f"<div class='wg-bar'><i style='width:{pct:.0f}%'></i></div>{_chips(m['recompensa'])}</div>", unsafe_allow_html=True)
    st.markdown("<div class='wg-aviso'>As missões premiam hábito e diversificação, não volume de operações. Diárias e semanais renovam sozinhas.</div>", unsafe_allow_html=True)


def aba_conquistas(res: dict, cart: dict | None = None) -> None:
    """Só as conquistas do Wallet Game, com as recompensas de cada uma. A coleção geral de emblemas fica no Perfil (Minha conta)."""
    ok = [c for c in res["conquistas"] if c["desbloqueada_em"]]
    st.markdown(f"<div class='wg-sec'>{len(ok)} de {len(res['conquistas'])} desbloqueadas</div>", unsafe_allow_html=True)
    for c in res["conquistas"]:
        quando = f"Desbloqueada em {_data(c['desbloqueada_em'])}" if c["desbloqueada_em"] else "Ainda bloqueada"
        st.markdown(f"<div class='wg-card{'' if c['desbloqueada_em'] else ' off'}'><div class='wg-emb' style='--c:{c['cor']}'><div class='e'>{c['emblema']}</div>"
                    f"<div><div class='t'>{_e(c['nome'])}</div><div class='d'>{_e(c['descricao'])}</div><div class='m'>{_e(quando)}</div>{_chips(c['recompensa'])}</div></div></div>",
                    unsafe_allow_html=True)
