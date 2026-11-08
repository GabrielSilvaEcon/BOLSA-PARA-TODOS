"""Página Competição: carteira virtual, ordens a preço de fechamento e ranking entre os usuários (lógica em competicao.py)."""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import banco
import competicao as C
import tema
import usuarios
from dados import brl, pct

CH = "_comp_cache"
BRT = timezone(timedelta(hours=-3))


def _agora() -> datetime:
    return datetime.now(BRT).replace(tzinfo=None)


def _pc(r) -> str:
    return "—" if r is None else ("+" if r > 0 else "") + pct(r * 100, 2)


def _data_br(iso: str | None) -> str:
    try:
        return date.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except Exception:
        return "—"


@st.cache_data(ttl=120, show_spinner=False)
def _publico(chave: str) -> dict:
    return banco.comp_publico_ler(chave)


def _pessoa(a, forcar: bool = False) -> dict:
    """Documento da pessoa e carteira, lidos do banco (no máximo a cada 30 s, ou na hora quando algo foi gravado)."""
    c = st.session_state.get(CH)
    if forcar or not c or c.get("email") != a.email or (_agora() - c["t"]).total_seconds() > 30:
        try:
            perfil = C.sanear_perfil(banco.comp_ordens_ler(a))
            cart = banco.comp_carteira_ler(a) or {}
        except Exception as e:
            banco.registrar_erro("competicao_app", e)
            perfil, cart = C.sanear_perfil({}), {}
        c = {"email": a.email, "t": _agora(), "perfil": perfil, "cart": cart}
        st.session_state[CH] = c
    return c


def _gravar_perfil(a, perfil: dict):
    banco.comp_ordens_gravar(a, C.sanear_perfil(perfil))
    st.session_state.pop(CH, None)


# ------------------------------------------------------------------ participar
def _participar(a, perfil: dict):
    st.markdown("#### Entrar na competição")
    st.write("Você recebe **R$ 100.000 virtuais** e monta sua carteira com ativos da bolsa. O lucro aumenta o seu capital e pode ser "
             "reinvestido. O ranking compara apenas o **retorno em %**, então todos competem em pé de igualdade.")
    with st.form("comp_entrar"):
        ap = st.text_input("Escolha um apelido público", max_chars=20, placeholder="ex.: investidor_sp",
                           help="É o único dado seu que aparece no ranking. Não use seu nome ou e-mail.")
        ok = st.checkbox("Entendo que meu apelido e meu retorno em % aparecem no ranking para todos os usuários. Valores em reais nunca aparecem. "
                         "É uma simulação educacional, sem dinheiro real e sem recomendação de investimento.")
        enviar = st.form_submit_button("Participar", type="primary")
    if not enviar:
        return
    valido, msg = C.apelido_valido(ap)
    if not valido:
        st.error(msg)
    elif not ok:
        st.error("Para participar, marque a confirmação.")
    elif not banco.comp_apelido_livre(a, C.chave_apelido(ap)):
        st.error("Esse apelido já está em uso. Escolha outro.")
    else:
        _gravar_perfil(a, {"apelido": ap.strip(), "aceite": True, "entrada": _agora().date().isoformat(), "drip": False, "pend": []})
        try:
            banco.auditar(a.id, "competicao_entrar", a.id, {})
        except Exception:
            pass
        st.rerun()


# ------------------------------------------------------------------ ranking
def _aba_ranking(perfil: dict, cart: dict):
    rk = _publico("comp_ranking")
    if not rk or not rk.get("listas"):
        st.info(f"O ranking aparece depois dos primeiros fechamentos: para entrar nele é preciso ter pelo menos {C.MIN_DIAS_RANKING} pregões de histórico. "
                "Ele é atualizado nos dias úteis, depois do fechamento do mercado.")
        return
    per = st.segmented_control("Período", ["Geral", "Mês", "Semana"], default="Geral", key="comp_per") or "Geral"
    chave = {"Geral": "geral", "Mês": "mes", "Semana": "semana"}[per]
    linhas = rk["listas"].get(chave) or []
    n = rk["listas"].get(chave + "_n", len(linhas))
    st.caption(f"Atualizado após o fechamento de {_data_br(rk.get('dia'))} · {n} participante(s) no ranking {per.lower()}. "
               f"Só entra quem tem {C.MIN_DIAS_RANKING} pregões ou mais.")
    meu = (cart.get("rank") or {})
    if perfil.get("aceite") and meu.get(chave):
        st.success(f"Você está em **{meu[chave]}º** de {n} no ranking {per.lower()}.")
    elif perfil.get("aceite") and len(cart.get("hist") or []) < C.MIN_DIAS_RANKING:
        st.info(f"Você entra no ranking depois de {C.MIN_DIAS_RANKING} pregões (faltam {max(0, C.MIN_DIAS_RANKING - len(cart.get('hist') or []))}).")
    if meu.get("conflito"):
        st.warning("Seu apelido ficou igual ao de outra pessoa e você está fora do ranking. Troque o apelido em “Minha carteira”.")
    if not linhas:
        st.info("Ainda não há participantes neste período.")
        return
    eu = (perfil.get("apelido") or "").lower()
    df = pd.DataFrame([{"Posição": x["pos"], "Apelido": x["apelido"] + (" (você)" if x["apelido"].lower() == eu else ""),
                        "Retorno": x["ret"] * 100, "Queda máxima": x["dd"] * 100, "Pregões": x["dias"]} for x in linhas])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Retorno": st.column_config.NumberColumn(format="%+.2f%%"),
        "Queda máxima": st.column_config.NumberColumn(format="%.2f%%", help="Maior queda do patrimônio desde um pico. Quanto menor, mais estável.")})
    st.caption("Retorno alto com queda máxima grande indica mais risco. Carteira virtual: resultados passados não garantem resultados futuros.")


# ------------------------------------------------------------------ minha carteira
def _tabela_posicoes(est: dict) -> pd.DataFrame:
    pat = max(C.patrimonio(est), 1.0)
    linhas = []
    for tk, p in sorted((est.get("pos") or {}).items()):
        px = (est.get("ult") or {}).get(tk) or p["pm"]
        v = p["q"] * px
        linhas.append({"Ativo": tk, "Qtd": p["q"], "Preço médio": p["pm"], "Último preço": px, "Valor": v, "Peso": v / pat * 100,
                       "Resultado": (px / p["pm"] - 1) * 100 if p["pm"] else 0.0})
    return pd.DataFrame(linhas)


def _aba_carteira(a, perfil: dict, cart: dict):
    est = cart if cart.get("v") == 1 else C.novo_estado(perfil.get("entrada") or _agora().date().isoformat())
    pat = C.patrimonio(est)
    ret = pat / C.CAPITAL_INICIAL - 1
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Patrimônio", brl(pat))
    c2.metric("Retorno", _pc(ret))
    c3.metric("Lucro / prejuízo", brl(pat - C.CAPITAL_INICIAL))
    c4.metric("Caixa disponível", brl(est.get("caixa", 0)), help="Inclui lucros das vendas e proventos. Use para comprar mais (reinvestir).")
    if not cart:
        st.info("Sua carteira aparece depois do primeiro fechamento (dias úteis, por volta das 18h30). Você já pode enviar ordens na aba Negociar.")
    elif est.get("ult_dia"):
        st.caption(f"Valores do fechamento de {_data_br(est['ult_dia'])}.")
    hist = est.get("hist") or []
    if hist:
        xs = [est.get("inicio") or hist[0]["d"]] + [x["d"] for x in hist]
        ys = [0.0] + [(x["p"] / C.CAPITAL_INICIAL - 1) * 100 for x in hist]
        fig = go.Figure(go.Scatter(x=xs, y=ys, mode="lines+markers", name="Retorno %", hovertemplate="%{x}: %{y:+.2f}%<extra></extra>"))
        fig.update_layout(height=260, margin=dict(l=10, r=10, t=30, b=10), yaxis_title="Retorno (%)", title="Evolução do retorno")
        try:
            tema.padronizar_figura(fig)
        except Exception:
            pass
        st.plotly_chart(fig, width="stretch")
    df = _tabela_posicoes(est)
    if df.empty:
        st.info("Nenhuma posição ainda. Todo o capital está em caixa.")
    else:
        st.markdown("##### Posições")
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Preço médio": st.column_config.NumberColumn(format="R$ %.2f"), "Último preço": st.column_config.NumberColumn(format="R$ %.2f"),
            "Valor": st.column_config.NumberColumn(format="R$ %.2f"), "Peso": st.column_config.NumberColumn(format="%.1f%%"),
            "Resultado": st.column_config.NumberColumn(format="%+.1f%%")})
    pend = C.pendentes_validas(est, perfil.get("pend") or [])
    if pend:
        st.markdown("##### Ordens aguardando o fechamento")
        for o in pend:
            c1, c2 = st.columns([5, 1])
            c1.write(f"{'Compra' if o['l'] == 'C' else 'Venda'} de **{o['q']}** × {o['t']} · executa no fechamento de {_data_br(o['x'])}")
            if c2.button("Cancelar", key=f"comp_canc_{o['id']}"):
                perfil["pend"] = [x for x in perfil["pend"] if x["id"] != o["id"]]
                _gravar_perfil(a, perfil)
                st.rerun()
    st.markdown("##### Preferências")
    drip = st.toggle("Reinvestir proventos automaticamente no mesmo ativo", value=perfil.get("drip", False), key="comp_drip",
                     help="Dividendos e rendimentos de FIIs viram novas cotas do mesmo ativo no fechamento do dia (com o custo de negociação).")
    if drip != perfil.get("drip", False):
        perfil["drip"] = drip
        _gravar_perfil(a, perfil)
        st.rerun()
    with st.expander("Extrato (últimas movimentações)"):
        ext = list(reversed(est.get("ext") or []))[:40]
        if not ext:
            st.caption("Sem movimentações ainda.")
        for x in ext:
            nome = {"compra": "Compra", "venda": "Venda", "provento": "Provento", "recusada": "Ordem recusada",
                    "reinvestimento": "Reinvestimento", "desdobramento": "Desdobramento"}.get(x["tipo"], x["tipo"])
            extra = f" · {x['m']}" if x.get("m") else (f" · {brl(x['v'])}" if x.get("v") is not None else "")
            st.write(f"{_data_br(x['d'])} · {nome} · {x.get('t', '')} {x.get('q', '')}{extra}")
    with st.expander("Mudar meu apelido"):
        novo = st.text_input("Novo apelido", value=perfil.get("apelido", ""), max_chars=20, key="comp_novo_ap")
        if st.button("Salvar apelido", key="comp_salvar_ap"):
            ok, msg = C.apelido_valido(novo)
            if not ok:
                st.error(msg)
            elif C.chave_apelido(novo) != C.chave_apelido(perfil["apelido"]) and not banco.comp_apelido_livre(a, C.chave_apelido(novo)):
                st.error("Esse apelido já está em uso.")
            else:
                perfil["apelido"] = novo.strip()
                _gravar_perfil(a, perfil)
                st.rerun()


# ------------------------------------------------------------------ negociar
def _rotulo(tk: str) -> str:
    try:
        import recursos
        return recursos.rotulo(tk)
    except Exception:
        return tk


def _max_compra(est: dict, pend: list, ref: float, tk: str, precos: dict) -> int:
    reservado = sum(o["q"] * float((precos.get(o["t"]) or {}).get("c") or 0) * (1 + C.CUSTO_OPERACAO) for o in pend if o["l"] == "C")
    livre = max(0.0, float(est.get("caixa", 0)) - reservado)
    pat = max(C.patrimonio(est, {k: v.get("c") for k, v in precos.items()}), 1.0)
    atual = (est.get("pos") or {}).get(tk, {"q": 0})["q"]
    por_caixa = livre / (ref * (1 + C.CUSTO_OPERACAO))
    por_peso = (C.MAX_PESO * pat) / ref - atual
    return max(0, int(min(por_caixa, por_peso)))


def _usar_limite() -> tuple[bool, str]:
    try:
        import planos
        ok, info = planos.usar("comp_ordens_dia")
        return ok, info.get("mensagem") or "Limite diário de ordens atingido."
    except Exception:
        return True, ""


def _aba_negociar(a, perfil: dict, cart: dict):
    pr = _publico("comp_precos")
    precos = (pr or {}).get("precos") or {}
    if not precos:
        st.info("A lista de ativos da competição é publicada no primeiro fechamento (dias úteis, por volta das 18h30). Volte depois disso.")
        return
    est = cart if cart.get("v") == 1 else C.novo_estado(perfil.get("entrada") or _agora().date().isoformat())
    pend = C.pendentes_validas(est, perfil.get("pend") or [])
    st.caption(f"Cotações do fechamento de {_data_br(pr.get('dia'))}. As ordens são executadas no **preço de fechamento** do pregão "
               f"(ordens até as {C.HORA_CORTE}h valem para hoje; depois, para o próximo pregão).")
    tk = st.selectbox("Ativo", sorted(precos), format_func=_rotulo, key="comp_tk")
    lado = st.segmented_control("Operação", ["Comprar", "Vender"], default="Comprar", key="comp_lado") or "Comprar"
    ref = float(precos[tk]["c"])
    pos = (est.get("pos") or {}).get(tk, {"q": 0})
    if lado == "Comprar":
        maxq = _max_compra(est, pend, ref, tk, precos)
    else:
        maxq = max(0, pos["q"] - sum(o["q"] for o in pend if o["l"] == "V" and o["t"] == tk))
    c1, c2 = st.columns([3, 2])
    with c2:
        st.write("")
        if st.button(f"Máximo permitido ({maxq})", key="comp_max", disabled=maxq < 1,
                     help="Compra: usa o caixa livre (inclui lucros e proventos) respeitando o limite de concentração. Venda: toda a posição."):
            st.session_state["comp_qtd"] = max(1, maxq)
    with c1:
        qtd = st.number_input("Quantidade (cotas inteiras)", min_value=1, max_value=C.MAX_QTD_ORDEM, value=st.session_state.get("comp_qtd", 100),
                              step=1, key="comp_qtd")
    custo = qtd * ref * (1 + C.CUSTO_OPERACAO) if lado == "Comprar" else qtd * ref * (1 - C.CUSTO_OPERACAO)
    pat = max(C.patrimonio(est, {k: v.get("c") for k, v in precos.items()}), 1.0)
    st.write(f"Último fechamento: **{brl(ref)}** ({_pc(precos[tk].get('v', 0) / 100)} no dia) · "
             f"{'custo' if lado == 'Comprar' else 'receita'} estimado: **{brl(custo)}** · "
             f"no seu patrimônio: **{pct(((pos['q'] + (qtd if lado == 'Comprar' else -qtd)) * ref) / pat * 100, 1)}**")
    st.caption(f"Caixa disponível: {brl(est.get('caixa', 0))} · Custo de negociação: {C.CUSTO_OPERACAO:.2%} por operação. "
               "O valor final usa o preço de fechamento do dia da execução e pode diferir da estimativa.")
    if st.button("Enviar ordem", type="primary", key="comp_enviar"):
        ok, msg = C.validar_ordem(est, perfil.get("pend") or [], "C" if lado == "Comprar" else "V", tk, int(qtd), precos)
        if not ok:
            st.error(msg)
            return
        liberado, aviso = _usar_limite()
        if not liberado:
            st.warning(aviso)
            return
        o = C.nova_ordem(_agora(), "C" if lado == "Comprar" else "V", tk, int(qtd))
        perfil["pend"] = (perfil.get("pend") or []) + [o]
        _gravar_perfil(a, perfil)
        st.session_state["comp_ok"] = f"Ordem enviada: {lado.lower()} {int(qtd)} × {tk}. Execução no fechamento de {_data_br(o['x'])}."
        st.rerun()
    if st.session_state.get("comp_ok"):
        st.success(st.session_state.pop("comp_ok"))


# ------------------------------------------------------------------ regras
def _aba_regras():
    st.markdown(f"""
**Como funciona**
- Todos começam com **{brl(C.CAPITAL_INICIAL, 0)} virtuais**. Não há aportes nem retiradas: o patrimônio só muda por resultado das ordens, proventos e variação de preço.
- **O lucro vira capital.** O caixa inclui lucros de vendas e proventos, e você pode **reinvesti-lo** comprando mais. Há também o reinvestimento automático de proventos.
- O ranking usa o **retorno em %** (patrimônio atual ÷ capital inicial − 1), não valores em reais. Entra quem tem {C.MIN_DIAS_RANKING} pregões ou mais.
- **Ordens a preço de fechamento.** Ordens até as {C.HORA_CORTE}h valem para o fechamento do mesmo dia; depois disso, ou em fim de semana e feriado, para o próximo pregão.
  Ninguém escolhe o preço olhando o movimento do dia.
- **Universo:** ações do catálogo do app e FIIs/ETFs muito líquidos, os que tiverem cotação no fechamento.
- **Limite de concentração:** no máximo {C.MAX_PESO:.0%} do patrimônio em um único ativo. Cotas inteiras apenas.
- **Custos:** {C.CUSTO_OPERACAO:.2%} em cada compra e venda. Proventos entram no caixa na data ex; desdobramentos ajustam a quantidade.
- **Privacidade:** o ranking mostra só apelido e retorno %. Valores em reais, posições e ordens são só seus. Você pode trocar o apelido a qualquer momento.
- Contas suspensas e apelidos ofensivos ou repetidos saem do ranking.

**Aviso:** competição educacional com dinheiro virtual. Não é recomendação de investimento, não há prêmios em dinheiro e resultados passados não garantem resultados futuros.
Cotações vêm de fontes gratuitas e podem ter atrasos ou falhas.
""")


# ------------------------------------------------------------------ página
def pagina_competicao():
    st.markdown(tema.cabecalho("🏆", "Competição de carteiras",
                               "Monte uma carteira virtual, dispute o ranking e acompanhe sua evolução. Dinheiro de mentira, aprendizado de verdade."),
                unsafe_allow_html=True)
    a = usuarios.ator()
    if not a:
        st.info("Entre na sua conta para participar. Você pode ver o ranking sem entrar.")
        _aba_ranking({}, {})
        return
    if not banco.cfg_disponivel():
        st.warning("A competição precisa do banco de configuração do sistema, que ainda não está disponível. Fale com a administração.")
        return
    c = _pessoa(a)
    perfil, cart = c["perfil"], c["cart"]
    if not perfil.get("aceite"):
        _participar(a, perfil)
        st.divider()
        _aba_ranking(perfil, cart)
        return
    st.caption(f"Você compete como **{html.escape(perfil['apelido'])}**.")
    abas = st.tabs(["Ranking", "Minha carteira", "Negociar", "Regras"])
    with abas[0]:
        _aba_ranking(perfil, cart)
    with abas[1]:
        _aba_carteira(a, perfil, cart)
    with abas[2]:
        _aba_negociar(a, perfil, cart)
    with abas[3]:
        _aba_regras()
