"""Página Competição: carteira virtual, ordens a preço de fechamento e ranking entre os usuários (lógica em competicao.py)."""
from __future__ import annotations

import html
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import banco
import competicao as C
import competicao_ligas as L
import competicao_temporadas as T
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


@st.cache_data(ttl=120, show_spinner=False)
def _temp(tid: str) -> dict:
    try:
        return banco.comp_temp_ler(tid)
    except Exception:                                   # banco.py desatualizado ou leitura falhou: a aba mostra "sem resultado" em vez de derrubar a página
        return {}


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
def _tabela_risco(linhas: list, eu: str, periodo: str = "Desde o início"):
    """Ranking ajustado ao risco: Sharpe (retorno por unidade de risco), volatilidade anual, retorno e queda máxima."""
    if not linhas:
        st.info(f"Ainda não há participantes com {C.MIN_DIAS_RISCO} pregões ou mais para calcular o risco.")
        return
    df = pd.DataFrame([{"Posição": x["pos"], "Apelido": x["apelido"] + (" (você)" if x["apelido"].lower() == eu else ""), "Sharpe": x["sh"],
                        "Volatilidade": x["vol"] * 100, "Retorno": x["ret"] * 100, "Queda máxima": x["dd"] * 100, "Pregões": x["dias"]} for x in linhas])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Sharpe": st.column_config.NumberColumn(format="%.2f", help="Retorno diário médio ÷ oscilação diária, anualizado. Quanto maior, mais retorno por unidade de risco."),
        "Volatilidade": st.column_config.NumberColumn(format="%.1f%%", help="Oscilação anualizada do patrimônio."),
        "Retorno": st.column_config.NumberColumn(format="%+.2f%%"), "Queda máxima": st.column_config.NumberColumn(format="%.2f%%")})
    st.caption(f"{periodo}, com {C.MIN_DIAS_RISCO} pregões ou mais. Sharpe sem taxa livre de risco: serve para comparar participantes, não como promessa de retorno.")


def _aba_ranking(perfil: dict, cart: dict):
    rk = _publico("comp_ranking")
    if not rk or not rk.get("listas"):
        st.info("O ranking aparece assim que sai o primeiro fechamento: você entra já com " + C.pregoes(C.MIN_DIAS_RANKING) + " de histórico. "
                "Ele é atualizado nos dias úteis, depois do fechamento do mercado (por volta das 18h30). Ordens enviadas até as 17h valem para o fechamento do mesmo dia.")
        return
    ordem = st.segmented_control("Ordenar por", ["Retorno", "Ajustado ao risco"], default="Retorno", key="comp_ord") or "Retorno"
    if ordem == "Ajustado ao risco":
        _tabela_risco(rk["listas"].get("risco") or [], (perfil.get("apelido") or "").lower())
        return
    per = st.segmented_control("Período", ["Geral", "Mês", "Semana"], default="Geral", key="comp_per") or "Geral"
    chave = {"Geral": "geral", "Mês": "mes", "Semana": "semana"}[per]
    linhas = rk["listas"].get(chave) or []
    n = rk["listas"].get(chave + "_n", len(linhas))
    st.caption(f"Atualizado após o fechamento de {_data_br(rk.get('dia'))} · {n} participante(s) no ranking {per.lower()}. "
               f"Entra quem tem {C.pregoes(C.MIN_DIAS_RANKING)} ou mais.")
    meu = (cart.get("rank") or {})
    if perfil.get("aceite") and meu.get(chave):
        st.success(f"Você está em **{meu[chave]}º** de {n} no ranking {per.lower()}.")
    elif perfil.get("aceite") and len(cart.get("hist") or []) < C.MIN_DIAS_RANKING:
        st.info("Você entra no ranking no próximo fechamento (dias úteis, por volta das 18h30)." if C.MIN_DIAS_RANKING <= 1 else
                f"Você entra no ranking depois de {C.pregoes(C.MIN_DIAS_RANKING)} (faltam {max(0, C.MIN_DIAS_RANKING - len(cart.get('hist') or []))}).")
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
# ------------------------------------------------------------------ temporadas e selos
def _vitrine_selos(cart: dict):
    selos = [s for s in (cart.get("selos") or []) if isinstance(s, dict) and T.descricao_selo(s)]
    st.markdown("**Meus selos**")
    if not selos:
        st.caption("Você ainda não tem selos. Eles saem quando uma temporada termina: Ouro, Prata e Bronze para o pódio, Top 10 e Equilíbrio "
                   "(melhor retorno ajustado ao risco). São honrarias simbólicas, sem prêmio em dinheiro.")
        return
    for s in sorted(selos, key=lambda x: (x["temp"], x["selo"]), reverse=True):
        st.markdown(f"{T.ICONES.get(s['selo'], '🏅')} **{html.escape(T.descricao_selo(s))}**")


def _aba_temporadas(perfil: dict, cart: dict):
    if perfil.get("aceite"):
        _vitrine_selos(cart)
        st.divider()
    tipo_rot = st.segmented_control("Tipo de temporada", ["Mensal", "Trimestral"], default="Mensal", key="comp_ttipo") or "Mensal"
    tipo = tipo_rot.lower()
    ids = T.recentes(tipo, _agora().date(), 6 if tipo == "mensal" else 4)
    tid = st.selectbox("Temporada", ids, format_func=lambda x: T.rotulo(x) + (" (em andamento)" if x == ids[0] else ""), key=f"comp_tid_{tipo}")
    doc = _temp(tid)
    if not doc or doc.get("id") != tid:
        st.info("Esta temporada ainda não tem resultado. O ranking da temporada é atualizado nos dias úteis, depois do fechamento do mercado.")
        return
    n, minimo = doc.get("n", 0), doc.get("min_dias", T.MIN_DIAS_TEMPORADA[tipo])
    if doc.get("encerrada"):
        st.caption(f"Temporada **encerrada** · resultado final · {n} participante(s). Entra quem teve {minimo} pregões ou mais dentro do período.")
    else:
        st.caption(f"Temporada **em andamento** · atualizada após o fechamento de {_data_br(doc.get('gerado'))} · {n} participante(s). "
                   f"Entra quem tem {minimo} pregões ou mais dentro do período. Os selos só saem quando ela terminar.")
    eu = (perfil.get("apelido") or "").lower()
    if perfil.get("aceite"):
        pos = ((cart.get("rank") or {}).get("temp") or {}).get(tid, {}).get("pos") if not doc.get("encerrada") else \
            next((x["pos"] for x in doc.get("lista") or [] if x["apelido"].lower() == eu), None)
        if pos:
            st.success(f"Você {'terminou' if doc.get('encerrada') else 'está'} em **{pos}º** de {n} nesta temporada.")
        elif n:
            st.info(f"Você ainda não aparece nesta temporada (precisa de {minimo} pregões dentro do período).")
    ordem = st.segmented_control("Ordenar por", ["Retorno", "Ajustado ao risco"], default="Retorno", key=f"comp_tord_{tid}") or "Retorno"
    if ordem == "Ajustado ao risco":
        _tabela_risco(doc.get("risco") or [], eu, periodo="Dentro da temporada")
        return
    linhas = doc.get("lista") or []
    if not linhas:
        st.info("Ainda não há participantes nesta temporada.")
        return
    medalha = {1: "🥇 ", 2: "🥈 ", 3: "🥉 "} if doc.get("encerrada") and n >= T.MIN_PARTICIPANTES_SELO else {}
    df = pd.DataFrame([{"Posição": x["pos"], "Apelido": medalha.get(x["pos"], "") + x["apelido"] + (" (você)" if x["apelido"].lower() == eu else ""),
                        "Retorno": x["ret"] * 100, "Queda máxima": x["dd"] * 100, "Pregões": x["dias"]} for x in linhas])
    st.dataframe(df, hide_index=True, width="stretch", column_config={
        "Retorno": st.column_config.NumberColumn(format="%+.2f%%", help="Retorno só dentro do período da temporada."),
        "Queda máxima": st.column_config.NumberColumn(format="%.2f%%", help="Maior queda do patrimônio desde um pico, dentro da temporada.")})
    st.caption("Carteira virtual: resultados passados não garantem resultados futuros.")



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


# ------------------------------------------------------------------ ligas de amigos (etapa 2)
CHL = "_comp_ligas_cache"
MAX_ERROS_CODIGO = 6            # códigos errados por sessão antes de pedir uma pausa (impede adivinhar códigos)


def _ligas(a, forcar: bool = False) -> dict:
    c = st.session_state.get(CHL)
    if forcar or not c or c.get("email") != a.email or (_agora() - c["t"]).total_seconds() > 30:
        try:
            doc = L.sanear_ligas(banco.comp_ligas_ler(a))
        except Exception as e:
            banco.registrar_erro("competicao_app.ligas", e)
            doc = L.sanear_ligas({})
        c = {"email": a.email, "t": _agora(), "doc": doc}
        st.session_state[CHL] = c
    return c["doc"]


def _gravar_ligas(a, doc: dict):
    banco.comp_ligas_gravar(a, L.sanear_ligas(doc))
    st.session_state.pop(CHL, None)


@st.cache_data(ttl=120, show_spinner=False)
def _rank_liga(email: str, codigo: str, _a) -> dict:
    """Ranking publicado da liga (o banco só entrega a quem é membro). A chave do cache inclui o e-mail: ninguém lê o cache de outro."""
    return banco.comp_liga_ranking_ler(_a, codigo)


@st.cache_data(ttl=120, show_spinner=False)
def _def_liga(email: str, codigo: str, _a) -> dict | None:
    return banco.comp_liga_definicao(_a, codigo)


def _url_app() -> str:
    try:
        import email_envio
        return email_envio.url_base()
    except Exception:
        return ""


def _limite_plano(recurso: str) -> tuple[int, str]:
    try:
        import planos
        return planos.limite_atual(recurso)
    except Exception:
        return 10 ** 6, "Gratuito"


def _pode_mais(recurso: str, atual: int) -> tuple[bool, str]:
    try:
        import planos
        lim, plano = planos.limite_atual(recurso)
        if lim <= 0:
            return False, f"Criar ligas privadas é um recurso do plano Investidor Plus ou superior (seu plano: {plano})."
        return planos.permitido_max(recurso, atual)
    except Exception:
        return True, ""


def _erro_codigo() -> bool:
    """True se a sessão errou códigos demais nos últimos 5 minutos (a contagem zera sozinha depois da pausa)."""
    t = st.session_state.get("comp_cod_t")
    if t and (_agora() - t).total_seconds() > 300:
        st.session_state["comp_cod_erros"], st.session_state["comp_cod_t"] = 0, None
    return st.session_state.get("comp_cod_erros", 0) >= MAX_ERROS_CODIGO


def _errou_codigo():
    st.session_state["comp_cod_erros"] = st.session_state.get("comp_cod_erros", 0) + 1
    st.session_state["comp_cod_t"] = _agora()


def _entrar_na_liga(a, codigo_txt: str) -> tuple[bool, str]:
    codigo = L.codigo_valido(codigo_txt)
    if not codigo:
        _errou_codigo()
        return False, "Código inválido. Ele tem 8 letras e números (ex.: K7QM-2XPA)."
    if _erro_codigo():
        return False, "Muitos códigos errados. Aguarde alguns minutos e tente de novo."
    try:
        import abuso
        if abuso.rajada_excedida(a.email, "comp_liga_entrar"):
            return False, "Muitas tentativas em pouco tempo. Aguarde um minuto."
    except Exception:
        pass
    doc = _ligas(a, forcar=True)
    if L.participa(doc, codigo):
        return True, "Você já participa dessa liga."
    de_amigos = [x for x in doc["ligas"] if not x["dono"]]
    ok, msg = _pode_mais("comp_ligas_entrar", len(de_amigos))
    if not ok:
        return False, msg
    try:
        d = banco.comp_liga_definicao(a, codigo)
    except Exception as e:
        banco.registrar_erro("competicao_app.liga_def", e)
        return False, "Não consegui consultar a liga agora. Tente de novo em instantes."
    if not d:
        _errou_codigo()
        return False, "Não encontrei nenhuma liga com esse código. Confira com quem convidou."
    try:
        if banco.comp_liga_contagem(a, codigo) >= d["max"]:
            return False, f"A liga “{d['nome']}” já está cheia ({d['max']} membros)."
    except Exception as e:
        banco.registrar_erro("competicao_app.liga_contagem", e)
    _gravar_ligas(a, L.adicionar(doc, codigo, _agora().date()))
    try:
        banco.auditar(a.id, "competicao_liga_entrar", a.id, {"liga": codigo})
    except Exception:
        pass
    return True, f"Você entrou na liga “{d['nome']}”. Ela aparece no ranking depois do próximo fechamento."


def _criar_liga(a, nome: str) -> tuple[bool, str]:
    ok, msg = L.nome_valido(nome)
    if not ok:
        return False, msg
    doc = _ligas(a, forcar=True)
    ok, msg = _pode_mais("comp_ligas_criar", len(L.donas(doc)))
    if not ok:
        return False, msg
    maxm = max(2, min(_limite_plano("comp_liga_membros")[0], L.MAX_MEMBROS_TETO))
    try:
        codigo = banco.comp_liga_criar(a, L.nova_definicao(nome, a.email, maxm, _agora()))
    except Exception as e:
        banco.registrar_erro("competicao_app.liga_criar", e)
        return False, "Não consegui criar a liga agora. Tente de novo em instantes."
    _gravar_ligas(a, L.adicionar(doc, codigo, _agora().date(), dono=True))
    try:
        banco.auditar(a.id, "competicao_liga_criar", a.id, {"liga": codigo})
    except Exception:
        pass
    return True, codigo


def _tabela_liga(rk: dict, perfil: dict, codigo: str):
    if (st.segmented_control("Ordenar por", ["Retorno", "Ajustado ao risco"], default="Retorno", key=f"comp_lord_{codigo}") or "Retorno") != "Retorno":
        _tabela_risco((rk.get("listas") or {}).get("risco") or [], (perfil.get("apelido") or "").lower())
        return
    per = st.segmented_control("Período", ["Geral", "Mês", "Semana"], default="Geral", key=f"comp_lper_{codigo}") or "Geral"
    chave = {"Geral": "geral", "Mês": "mes", "Semana": "semana"}[per]
    linhas = (rk.get("listas") or {}).get(chave) or []
    eu = (perfil.get("apelido") or "").lower()
    if linhas:
        df = pd.DataFrame([{"Posição": x["pos"], "Apelido": x["apelido"] + (" (você)" if x["apelido"].lower() == eu else ""),
                            "Retorno": x["ret"] * 100, "Queda máxima": x["dd"] * 100, "Pregões": x["dias"]} for x in linhas])
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Retorno": st.column_config.NumberColumn(format="%+.2f%%"), "Queda máxima": st.column_config.NumberColumn(format="%.2f%%")})
    else:
        st.info("Ainda não há participantes qualificados neste período.")
    if rk.get("aguardando"):
        st.caption(f"Aguardando o primeiro fechamento para entrar no ranking: " + ", ".join(html.escape(x) for x in rk["aguardando"]) + ".")


def _cartao_liga(a, perfil: dict, cart: dict, x: dict):
    codigo = x["c"]
    meu = ((cart.get("rank") or {}).get("ligas") or {}).get(codigo) or {}
    try:
        rk = _rank_liga(a.email, codigo, a)
    except Exception:
        rk = {}
    nome = (rk or {}).get("nome") or meu.get("nome")
    if not nome:
        try:
            d = _def_liga(a.email, codigo, a)
        except Exception:
            d = None
        nome = d["nome"] if d else None
    if nome is None and not rk:
        rotulo = f"Liga {L.formatar_codigo(codigo)}"
    else:
        rotulo = f"{nome or 'Liga'}"
    sufixo = f" · você em {meu['geral']}º" if meu.get("geral") else ""
    with st.expander(f"{rotulo}{sufixo}", expanded=False):
        if meu.get("cheia"):
            st.warning("A liga lotou antes de você ser contado e você está fora do ranking dela. Fale com quem criou a liga.")
        if not rk:
            d = None
            try:
                d = _def_liga(a.email, codigo, a)
            except Exception:
                pass
            if d is None:
                st.warning("Essa liga foi encerrada por quem a criou (ou o código não existe mais).")
            else:
                st.info("O ranking da liga aparece depois do próximo fechamento (dias úteis, por volta das 18h30).")
        else:
            dono = f" · criada por **{html.escape(rk['dono'])}**" if rk.get("dono") else ""
            st.caption(f"Atualizado após o fechamento de {_data_br(rk.get('dia'))} · {rk.get('membros', 0)} de {rk.get('max', '—')} membros{dono}")
            _tabela_liga(rk, perfil, codigo)
        st.markdown("**Convidar amigos**")
        st.code(L.formatar_codigo(codigo), language=None)
        link = L.link_convite(_url_app(), codigo)
        st.caption("Envie o código ou este link. Quem abrir o link já cai na tela de entrada da liga.")
        st.code(link, language=None)
        c1, c2 = st.columns(2)
        if x["dono"]:
            if c1.button("Encerrar liga", key=f"comp_enc_{codigo}", help="Apaga a liga para todos. Os participantes continuam na competição geral."):
                st.session_state["comp_enc_confirma"] = codigo
            if st.session_state.get("comp_enc_confirma") == codigo:
                st.warning("Encerrar apaga a liga e o ranking dela para todos os membros. Não dá para desfazer.")
                if st.button("Sim, encerrar agora", key=f"comp_enc2_{codigo}", type="primary"):
                    try:
                        banco.comp_liga_encerrar(a, codigo)
                    except Exception as e:
                        st.error(str(e) if isinstance(e, PermissionError) else "Não consegui encerrar agora.")
                    else:
                        _gravar_ligas(a, L.remover(_ligas(a, forcar=True), codigo))
                        st.session_state.pop("comp_enc_confirma", None)
                        st.cache_data.clear()
                        st.rerun()
        else:
            if c1.button("Sair da liga", key=f"comp_sair_{codigo}"):
                _gravar_ligas(a, L.remover(_ligas(a, forcar=True), codigo))
                st.rerun()


def _aba_ligas(a, perfil: dict, cart: dict):
    st.write("Dispute o ranking só com os seus amigos: crie uma liga, compartilhe o código ou o link e acompanhem quem rende mais em **%**. "
             "Só aparecem apelidos e retornos, nunca valores em reais.")
    doc = _ligas(a)
    # convite recebido por link (?liga=CÓDIGO)
    conv = st.session_state.get("comp_convite")
    if conv and not L.participa(doc, conv):
        try:
            d = _def_liga(a.email, conv, a)
        except Exception:
            d = None
        if d:
            st.info(f"Você foi convidado para a liga **{html.escape(d['nome'])}** (até {d['max']} membros).")
            if st.button("Entrar nessa liga", type="primary", key="comp_aceitar_convite"):
                ok, msg = _entrar_na_liga(a, conv)
                st.session_state["comp_liga_msg"] = (ok, msg)
                st.session_state.pop("comp_convite", None)
                st.rerun()
        else:
            st.warning("Esse convite não é mais válido (a liga foi encerrada ou o código está errado).")
            st.session_state.pop("comp_convite", None)
    elif conv:
        st.session_state.pop("comp_convite", None)
    if st.session_state.get("comp_liga_msg"):
        ok, msg = st.session_state.pop("comp_liga_msg")
        (st.success if ok else st.error)(msg)
    st.markdown("##### Minhas ligas")
    if not doc["ligas"]:
        st.info("Você ainda não participa de nenhuma liga. Crie a sua ou entre com o código de um amigo.")
    for x in doc["ligas"]:
        _cartao_liga(a, perfil, cart, x)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("##### Entrar com um código")
        with st.form("comp_entrar_liga", clear_on_submit=True):
            cod = st.text_input("Código ou link do convite", placeholder="ex.: K7QM-2XPA", max_chars=200)
            if st.form_submit_button("Entrar na liga"):
                ok, msg = _entrar_na_liga(a, cod)
                st.session_state["comp_liga_msg"] = (ok, msg)
                st.rerun()
    with c2:
        st.markdown("##### Criar uma liga")
        lim, plano = _limite_plano("comp_ligas_criar")
        if lim <= 0:
            st.info(f"Criar ligas privadas está no plano **Investidor Plus** (seu plano: {plano}). Entrar em ligas de amigos continua liberado.")
        else:
            st.caption(f"Você criou {len(L.donas(doc))} de {lim} ligas permitidas no plano {plano}. "
                       f"Cada liga aceita até {_limite_plano('comp_liga_membros')[0]} membros.")
            with st.form("comp_criar_liga", clear_on_submit=True):
                nome = st.text_input("Nome da liga", max_chars=30, placeholder="ex.: Turma da faculdade")
                if st.form_submit_button("Criar liga", type="primary"):
                    ok, msg = _criar_liga(a, nome)
                    st.session_state["comp_liga_msg"] = (ok, f"Liga criada! Código: {L.formatar_codigo(msg)}. Compartilhe com seus amigos." if ok else msg)
                    st.rerun()
    st.markdown("##### Avisos de posição")
    st.caption("Receba uma notificação (e, se você ligou e-mail, Telegram ou push, também por lá) quando você mudar de posição. "
               "Os canais e horários seguem as suas preferências em Alertas.")
    av = doc["avisos"]
    t1 = st.toggle("Avisar mudanças de posição nas minhas ligas", value=av["liga"], key="comp_av_liga")
    t2 = st.toggle("Avisar marcos no ranking geral (entrada, Top 100, Top 10, Top 3 e 1º lugar)", value=av["global"], key="comp_av_glob")
    if t1 != av["liga"] or t2 != av["global"]:
        _gravar_ligas(a, {**doc, "avisos": {"liga": t1, "global": t2}})
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
- O ranking usa o **retorno em %** (patrimônio atual ÷ capital inicial − 1), não valores em reais. Entra já no primeiro fechamento ({C.pregoes(C.MIN_DIAS_RANKING)} ou mais).
- **Ordens a preço de fechamento.** Ordens até as {C.HORA_CORTE}h valem para o fechamento do mesmo dia; depois disso, ou em fim de semana e feriado, para o próximo pregão.
  Ninguém escolhe o preço olhando o movimento do dia.
- **Universo:** ações do catálogo do app e FIIs/ETFs muito líquidos, os que tiverem cotação no fechamento.
- **Limite de concentração:** no máximo {C.MAX_PESO:.0%} do patrimônio em um único ativo. Cotas inteiras apenas.
- **Custos:** {C.CUSTO_OPERACAO:.2%} em cada compra e venda. Proventos entram no caixa na data ex; desdobramentos ajustam a quantidade.
- **Privacidade:** o ranking mostra só apelido e retorno %. Valores em reais, posições e ordens são só seus. Você pode trocar o apelido a qualquer momento.
- Contas suspensas e apelidos ofensivos ou repetidos saem do ranking.
- **Ranking ajustado ao risco:** além do retorno, dá para ordenar pelo **Sharpe** (retorno por unidade de risco), com {C.MIN_DIAS_RISCO} pregões ou mais. Evita premiar só quem apostou tudo num papel.
- **Temporadas:** o ranking também é fechado por **mês** e por **trimestre**, medindo só o retorno dentro do período (mínimo de {T.MIN_DIAS_TEMPORADA['mensal']} pregões no mês e {T.MIN_DIAS_TEMPORADA['trimestral']} no trimestre).
  Quando a temporada termina, o resultado é congelado e saem os **selos**: Ouro, Prata e Bronze (pódio, com pelo menos {T.MIN_PARTICIPANTES_SELO} participantes), Top 10 e Equilíbrio (melhor retorno ajustado ao risco).
  Selos são simbólicos, sem prêmio em dinheiro.
- **Ligas de amigos:** qualquer pessoa entra em ligas por código ou link de convite; criar ligas privadas é do plano Investidor Plus em diante. O ranking da liga usa as
  mesmas regras do geral (retorno em %, entrada no primeiro fechamento) e só os membros o veem. Quem criou pode encerrar a liga; quem entrou pode sair quando quiser.
- **Avisos:** você pode receber uma notificação quando subir de posição (ou entrar no Top 100, Top 10, Top 3 e 1º lugar) e quando mudar de posição nas suas ligas.

**Aviso:** competição educacional com dinheiro virtual. Não é recomendação de investimento, não há prêmios em dinheiro e resultados passados não garantem resultados futuros.
Cotações vêm de fontes gratuitas e podem ter atrasos ou falhas.
""")


# ------------------------------------------------------------------ página
def _capturar_convite():
    """Convite por link (…/competicao?liga=CÓDIGO): guarda na sessão para sobreviver ao login e à tela de entrada na competição."""
    try:
        v = st.query_params.get("liga")
        v = v[0] if isinstance(v, list) else v
    except Exception:
        v = None
    cod = L.extrair_convite(v) if v else None
    if cod:
        st.session_state["comp_convite"] = cod


def pagina_competicao():
    _capturar_convite()
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
        if st.session_state.get("comp_convite"):
            st.info("Você recebeu um convite para uma liga de amigos. Entre na competição abaixo e aceite o convite na aba **Ligas**.")
        _participar(a, perfil)
        st.divider()
        _aba_ranking(perfil, cart)
        return
    st.caption(f"Você compete como **{html.escape(perfil['apelido'])}**.")
    if st.session_state.get("comp_convite") and not L.participa(_ligas(a), st.session_state["comp_convite"]):
        st.info("Você tem um convite de liga esperando: abra a aba **Ligas**.")
    abas = st.tabs(["Ranking", "Temporadas", "Ligas", "Minha carteira", "Negociar", "Regras"])
    with abas[0]:
        _aba_ranking(perfil, cart)
    with abas[1]:
        _aba_temporadas(perfil, cart)
    with abas[2]:
        _aba_ligas(a, perfil, cart)
    with abas[3]:
        _aba_carteira(a, perfil, cart)
    with abas[4]:
        _aba_negociar(a, perfil, cart)
    with abas[5]:
        _aba_regras()
