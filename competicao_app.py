"""Página Competição: carteira virtual, ordens a preço de fechamento e ranking entre os usuários (lógica em competicao.py)."""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import secoes

import ativos_jogo as A
import banco
import competicao as C
import cotacoes_jogo as CJ
import diversificacao as D
import diversificar_app as DV
import fundos as fd
import competicao_ligas as L
import competicao_temporadas as T
import tema
import usuarios
import wallet_game as WG
import wallet_game_app as WGA
from design import componentes as DC
from dados import pct
from wallet_game import moeda

CH = "_comp_cache"
BRT = timezone(timedelta(hours=-3))


def _agora() -> datetime:
    return datetime.now(BRT).replace(tzinfo=None)


def _pc(r) -> str:
    return "—" if r is None else ("+" if r > 0 else "") + pct(r * 100, 2)


def _n(v, casas: int = 1) -> str:
    return DC.numero_br(v, casas)


def _itens_ranking(linhas: list, eu: str, medalha: dict | None = None, risco: bool = False) -> list:
    """Linhas do ranking -> itens do componente de cartões (sem tabela crua)."""
    out = []
    for x in linhas:
        x = dict(x, ret=0.0 if abs(x["ret"]) < 0.00005 else x["ret"], dd=0.0 if abs(x["dd"]) < 0.00005 else x["dd"])   # evita "-0,00%"
        if risco:
            valor = f"Sharpe {_n(x['sh'], 2)}"
            sub = f"Volatilidade {_n(x['vol'] * 100)}% · retorno {_pc(x['ret'])} · queda máx. {_n(x['dd'] * 100)}% · {x['dias']} pregões"
        else:
            valor = _pc(x["ret"])
            sub = f"Queda máxima {_n(x['dd'] * 100)}% · {x['dias']} pregões"
        out.append({"pos": x["pos"], "nome": x["apelido"], "valor": valor, "tom": x["ret"], "sub": sub,
                    "voce": x["apelido"].lower() == eu})
    return out


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
    st.write(f"Você recebe **{moeda(C.CAPITAL_NOVO, 0)} ** e monta sua carteira com ativos da bolsa. O lucro aumenta o seu capital e pode ser "
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
    st.markdown(DC.lista_ranking(_itens_ranking(linhas, eu, risco=True)), unsafe_allow_html=True)
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
        st.markdown(DC.mensagem(f"Você está em {meu[chave]}º de {n} no ranking {per.lower()}.", "sucesso"), unsafe_allow_html=True)
    elif perfil.get("aceite") and len(cart.get("hist") or []) < C.MIN_DIAS_RANKING:
        st.info("Você entra no ranking no próximo fechamento (dias úteis, por volta das 18h30)." if C.MIN_DIAS_RANKING <= 1 else
                f"Você entra no ranking depois de {C.pregoes(C.MIN_DIAS_RANKING)} (faltam {max(0, C.MIN_DIAS_RANKING - len(cart.get('hist') or []))}).")
    if meu.get("conflito"):
        st.warning("Seu apelido ficou igual ao de outra pessoa e você está fora do ranking. Troque o apelido na aba “Carteira”.")
    if not linhas:
        st.info("Ainda não há participantes neste período.")
        return
    eu = (perfil.get("apelido") or "").lower()
    st.markdown(DC.lista_ranking(_itens_ranking(linhas, eu), medalhas=True), unsafe_allow_html=True)
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
            st.markdown(DC.mensagem(f"Você {'terminou' if doc.get('encerrada') else 'está'} em {pos}º de {n} nesta temporada.", "sucesso"), unsafe_allow_html=True)
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
    medalhas = bool(doc.get("encerrada") and n >= T.MIN_PARTICIPANTES_SELO)
    st.markdown(DC.lista_ranking(_itens_ranking(linhas, eu), medalhas=medalhas), unsafe_allow_html=True)
    st.caption("Carteira virtual: resultados passados não garantem resultados futuros.")



def _tabela_posicoes(est: dict) -> pd.DataFrame:
    pat = max(C.patrimonio(est), 1.0)
    linhas = []
    for tk, p in sorted((est.get("pos") or {}).items()):
        px = (est.get("ult") or {}).get(tk) or p["pm"]
        v = p["q"] * px
        c = A.classe(tk)
        linhas.append({"Cor": A.CLASSES[c]["cor"] if c else "", "Classe": A.CLASSES[c]["icone"] + " " + A.CLASSES[c]["nome"] if c else "—", "Ativo": A.rotulo(tk), "Qtd": A.texto_qtd(tk, p["q"]),
                       "Preço médio": p["pm"], "Último preço": px, "Valor": v, "Peso": v / pat * 100,
                       "Resultado": (px / p["pm"] - 1) * 100 if p["pm"] else 0.0})
    return pd.DataFrame(linhas)


def _aba_carteira(a, perfil: dict, cart: dict):
    est = cart if cart.get("v") == 1 else C.novo_estado(perfil.get("entrada") or _agora().date().isoformat())
    pat = C.patrimonio(est)
    cap, apt = C.capital_de(est), C.aportes(est)
    ret = (pat - apt) / cap - 1                              # bônus da Wallet Game não contam como resultado de investimento
    st.markdown(DC.grade([
        DC.indicador("Patrimônio", moeda(pat)),
        DC.indicador("Retorno", _pc(ret), ret * 100),
        DC.indicador("Lucro / prejuízo", moeda(pat - apt - cap), detalhe="Sem contar bônus" if apt else ""),
        DC.indicador("Caixa disponível", moeda(est.get("caixa", 0)), detalhe="Inclui vendas, proventos e bônus; use para reinvestir."),
    ], 4), unsafe_allow_html=True)
    if not cart:
        st.info("Sua carteira aparece depois do primeiro fechamento (dias úteis, por volta das 18h30). Você já pode enviar ordens na aba Negociar.")
    elif est.get("ult_dia"):
        st.caption(f"Valores do fechamento de {_data_br(est['ult_dia'])}.")
    hist = est.get("hist") or []
    if hist:
        xs = [est.get("inicio") or hist[0]["d"]] + [x["d"] for x in hist]
        ys = [0.0] + [(C._liq(x) / C.capital_de(est) - 1) * 100 for x in hist]
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
        cartoes = [DC.cartao_posicao(r["Ativo"], r["Classe"], moeda(r["Valor"]), r["Resultado"], r["Peso"],
                                     f"{r['Qtd']} · preço médio {moeda(r['Preço médio'])} · último {moeda(r['Último preço'])}", r["Cor"])
                   for r in df.to_dict("records")]
        st.markdown(DC.grade(cartoes, 2), unsafe_allow_html=True)
    pend = C.pendentes_validas(est, perfil.get("pend") or [])
    if pend:
        st.markdown("##### Ordens antigas aguardando execução")
        for o in pend:
            c1, c2 = st.columns([5, 1])
            c1.write(f"{'Compra' if o['l'] == 'C' else 'Venda'} de **{A.texto_qtd(o['t'], o['q'])}** × {A.rotulo(o['t'])} · executa {C.rotulo_execucao(o)} de {_data_br(o['x'])}")
            if c2.button("Cancelar", key=f"comp_canc_{o['id']}"):
                perfil["pend"] = [x for x in perfil["pend"] if x["id"] != o["id"]]
                _gravar_perfil(a, perfil)
                st.rerun()
    with st.expander("Preferências", icon=":material/tune:"):
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
        icones = {"compra": "🛒", "venda": "💸", "provento": "💰", "recusada": "⛔", "reinvestimento": "🔁", "desdobramento": "✂️", "bonus": "🎁"}
        itens = []
        for x in ext:
            nome = {"compra": "Compra", "venda": "Venda", "provento": "Provento", "recusada": "Ordem recusada",
                    "reinvestimento": "Reinvestimento", "desdobramento": "Desdobramento", "bonus": "Bônus"}.get(x["tipo"], x["tipo"])
            extra = f"{x['m']}" if x.get("m") else (moeda(x["v"]) if x.get("v") is not None else "")
            qtxt = A.texto_qtd(x["t"], x["q"]) if x.get("t") and A.valido(x["t"]) and x.get("q") is not None else x.get("q", "")
            itens.append({"pos": icones.get(x["tipo"], "•"), "nome": f"{nome} {A.rotulo(x['t']) if x.get('t') else ''} {qtxt}".strip(),
                          "valor": _data_br(x["d"]), "sub": extra})
        if itens:
            st.markdown(DC.lista_ranking(itens), unsafe_allow_html=True)
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
        st.markdown(DC.lista_ranking(_itens_ranking(linhas, eu), medalhas=True), unsafe_allow_html=True)
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
    with st.expander("Entrar com um código", icon=":material/login:"):
        with st.form("comp_entrar_liga", clear_on_submit=True):
            cod = st.text_input("Código ou link do convite", placeholder="ex.: K7QM-2XPA", max_chars=200)
            if st.form_submit_button("Entrar na liga", type="primary"):
                ok, msg = _entrar_na_liga(a, cod)
                st.session_state["comp_liga_msg"] = (ok, msg)
                st.rerun()
    lim, plano = _limite_plano("comp_ligas_criar")
    with st.expander("Criar uma liga", icon=":material/group_add:"):
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
    av = doc["avisos"]
    with st.expander("Avisos de posição", icon=":material/notifications:"):
        t1 = st.toggle("Avisar mudanças de posição nas minhas ligas", value=av["liga"], key="comp_av_liga")
        t2 = st.toggle("Avisar marcos no ranking geral (entrada, Top 100, Top 10, Top 3 e 1º lugar)", value=av["global"], key="comp_av_glob")
    if t1 != av["liga"] or t2 != av["global"]:
        _gravar_ligas(a, {**doc, "avisos": {"liga": t1, "global": t2}})
        st.rerun()


# ------------------------------------------------------------------ negociar
def _rotulo(tk: str) -> str:
    return A.rotulo(tk)


def _max_compra(est: dict, pend: list, ref: float, tk: str, precos: dict) -> int | float:
    reservado = sum(o["q"] * float((precos.get(o["t"]) or {}).get("c") or 0) * (1 + A.custo(o["t"])) for o in pend if o["l"] == "C")
    livre = max(0.0, float(est.get("caixa", 0)) - reservado)
    pat = max(C.patrimonio(est, {k: v.get("c") for k, v in precos.items()}), 1.0)
    atual = (est.get("pos") or {}).get(tk, {"q": 0})["q"]
    por_caixa = livre / (ref * (1 + A.custo(tk)))
    limite = por_caixa if A.isento_peso(tk) else min(por_caixa, (C.MAX_PESO * pat) / ref - atual)
    return A.piso_qtd(tk, max(0.0, limite))


def _usar_limite() -> tuple[bool, str]:
    try:
        import planos
        ok, info = planos.usar("comp_ordens_dia")
        return ok, info.get("mensagem") or "Limite diário de ordens atingido."
    except Exception:
        return True, ""


@st.cache_data(ttl=900, show_spinner=False)
def _precos_reserva() -> dict:
    """Reserva para o início da competição: enquanto o fechamento diário não publicou `comp_precos` (primeiro dia, job parado ou falhando),
    busca o último fechamento do universo direto no Yahoo, em uma única chamada em lote. Só serve para a tela de ordens; a execução usa
    sempre o preço do fechamento/meio-dia do job."""
    try:
        import yfinance as yf
        import dados
        base = C.universo_b3()
        mapa = {dados.sym_yf(tk): tk for tk in base}
        h = yf.download(list(mapa), period="7d", interval="1d", auto_adjust=False, group_by="ticker", progress=False, threads=True)
        precos, dia = {}, None
        for sym, tk in mapa.items():
            try:
                col = h[sym]["Close"].dropna()
                if len(col) < 1 or float(col.iloc[-1]) <= 0:
                    continue
                c = float(col.iloc[-1])
                v = (c / float(col.iloc[-2]) - 1) * 100 if len(col) > 1 and float(col.iloc[-2]) > 0 else 0.0
                precos[tk] = {"c": round(c, 4), "v": round(v, 2)}
                dia = dia or col.index[-1].date().isoformat()
            except Exception:
                continue
        return {"dia": dia, "precos": precos, "reserva": True} if precos else {}
    except Exception as e:
        try:
            banco.registrar_erro("competicao_app.precos_reserva", e)
        except Exception:
            pass
        return {}


@st.cache_data(ttl=15, show_spinner=False)
def _cotacao_agora(tk: str) -> float | None:
    """Cotação atual em reais (B3 e EUA pelo Yahoo, cripto pela Binance). Fundo, Tesouro e CDI não têm preço durante o dia: devolve None
    e a ordem usa o último preço publicado."""
    return CJ.preco_agora(tk)


@st.cache_data(ttl=3600, show_spinner=False)
def _cota_fundo(cnpj: str) -> dict | None:
    """Última cota do fundo na CVM (informe diário), para quem quer comprar um fundo que ainda não está na lista do fechamento."""
    try:
        s = (CJ.ler_fundos([cnpj]).get(cnpj) or {})
        if not s:
            return None
        datas = sorted(s)
        c = float(s[datas[-1]])
        ant = float(s[datas[-2]]) if len(datas) > 1 else c
        return {"c": c, "v": round((c / ant - 1) * 100, 2) if ant else 0.0, "d": datas[-1]}
    except Exception as e:
        try:
            banco.registrar_erro("competicao_app.cota_fundo", e)
        except Exception:
            pass
        return None


def _chave(tk: str) -> str:
    return re.sub(r"\W", "_", tk)


def _entrada_fundo(extras: dict, tem_fundos: bool) -> None:
    """Fundos são milhares: em vez de uma lista fixa, a pessoa digita o CNPJ e o jogo busca a última cota na CVM."""
    with st.expander("Adicionar um fundo pelo CNPJ", expanded=not tem_fundos):
        st.caption("Informe o CNPJ do fundo (está no site do gestor ou na página Fundos do app). O jogo usa a cota divulgada pela CVM, que sai com 1 a 2 dias úteis de atraso.")
        txt = st.text_input("CNPJ do fundo", key="comp_cnpj", placeholder="00.000.000/0000-00", max_chars=20)
        if st.button("Buscar cota", key="comp_cnpj_ok", icon=":material/search:"):
            dig = fd.so_digitos(txt)
            if not fd.cnpj_valido(dig):
                st.error("CNPJ inválido. Confira os 14 números.")
            else:
                cota = _cota_fundo(dig)
                if not cota:
                    st.error("Não encontrei cota recente desse fundo na CVM. Confira o CNPJ ou tente outro fundo.")
                else:
                    extras[A.id_fundo(dig)] = {"c": cota["c"], "v": cota["v"]}
                    st.rerun()


def _efeito_na_classe(est: dict, tk: str, delta: float):
    """Como a ordem muda o peso da classe na carteira (ensino de diversificação): (nome, antes, depois) ou None."""
    try:
        f = D.pesos(est)
        g = D._grupo(A.classe(tk))
        if not g or f["pat"] <= 0:
            return None
        antes = f["grupos"].get(g, 0.0)
        return D.NOME_GRUPO[g].split(" (")[0], antes, max(0.0, antes + delta / f["pat"])
    except Exception:
        return None


def _aba_negociar(a, perfil: dict, cart: dict):
    pr = _publico("comp_precos")
    precos = dict((pr or {}).get("precos") or {})
    if not precos:
        pr = _precos_reserva()
        precos = dict((pr or {}).get("precos") or {})
        if precos:
            st.caption("Lista de ativos provisória (o fechamento diário ainda não foi publicado). Só ações, FIIs e ETFs da B3 aparecem até lá. Suas ordens executam na hora, à cotação atual.")
    if not precos:
        st.info("Não consegui carregar as cotações agora. Tente de novo em alguns minutos; se persistir, avise a administração.")
        return
    est = cart if cart.get("v") == 1 else C.novo_estado(perfil.get("entrada") or _agora().date().isoformat())
    pend = C.pendentes_validas(est, perfil.get("pend") or [])
    for tk0 in (est.get("pos") or {}):                                   # o que você já tem sempre pode ser vendido, mesmo sem cotação nova hoje
        if tk0 not in precos and (est.get("ult") or {}).get(tk0):
            precos[tk0] = {"c": float(est["ult"][tk0]), "v": 0.0}
    extras = st.session_state.setdefault("comp_fundos_extra", {})
    precos.update({k: v for k, v in extras.items() if k not in precos})
    st.caption(f"Cotações do fechamento de {_data_br(pr.get('dia'))}. As ordens são **executadas na hora**, à cotação atual do ativo "
               "(fora do pregão, a última cotação disponível; fundos, Tesouro e CDI usam o último preço divulgado).")

    por_classe = A.agrupar_por_classe(precos)
    disp = [c for c in A.ORDEM if por_classe[c] or c == "fundo"]
    rot = {c: f"{A.CLASSES[c]['icone']} {A.CLASSES[c]['nome']}" for c in disp}
    cl = st.segmented_control("Classe de ativo", disp, default=disp[0], format_func=lambda c: rot[c], key="comp_classe") or disp[0]
    st.caption(A.CLASSES[cl]["resumo"] + (" Quantidades fracionadas são aceitas." if A.CLASSES[cl]["passo"] < 1 else ""))
    if cl == "fundo":
        _entrada_fundo(extras, bool(por_classe["fundo"]))
        por_classe = A.agrupar_por_classe({**precos, **extras})
        precos.update({k: v for k, v in extras.items() if k not in precos})
    opcoes = sorted(por_classe[cl], key=lambda t: A.rotulo(t).lower())
    if not opcoes:
        st.info("Nenhum ativo dessa classe com cotação agora. Tente outra classe ou volte mais tarde.")
        return
    tk = st.selectbox("Ativo", opcoes, format_func=_rotulo, key=f"comp_tk_{cl}")
    lado = st.segmented_control("Operação", ["Comprar", "Vender"], default="Comprar", key="comp_lado") or "Comprar"
    ref = float(precos[tk]["c"])
    pos = (est.get("pos") or {}).get(tk, {"q": 0})
    passo = A.passo(tk)
    fracionado = passo < 1
    if lado == "Comprar":
        maxq = _max_compra(est, pend, ref, tk, precos)
    else:
        maxq = A.norm_qtd(tk, max(0.0, pos["q"] - sum(o["q"] for o in pend if o["l"] == "V" and o["t"] == tk)))
    kq, kv = f"comp_qtd_{_chave(tk)}", f"comp_val_{_chave(tk)}"
    c1, c2 = st.columns([3, 2])
    with c2:
        st.write("")
        if st.button(f"Máximo permitido ({A.texto_qtd(tk, maxq)})", key="comp_max", disabled=maxq < passo,
                     help="Compra: usa o caixa livre (inclui lucros e proventos) respeitando o limite de concentração. Venda: toda a posição."):
            st.session_state[kq] = max(passo, maxq) if fracionado else int(max(1, maxq))
            st.session_state[kv] = round(max(1.0, float(max(passo, maxq)) * ref), 2)
    with c1:
        if fracionado:
            modo = st.segmented_control("Informar por", ["Valor em T$", "Quantidade"], default="Valor em T$", key="comp_modo") or "Valor em T$"
        else:
            modo = "Quantidade"
        if modo == "Valor em T$":
            valor = st.number_input("Valor em T$", min_value=1.0, max_value=100_000_000.0, value=float(st.session_state.get(kv, 1000.0)), step=100.0, key=kv)
            base = valor / (ref * (1 + A.custo(tk))) if lado == "Comprar" else valor / ref
            qtd = A.piso_qtd(tk, base)
        elif fracionado:
            padrao = A.piso_qtd(tk, 1000.0 / ref) or passo
            qtd = A.norm_qtd(tk, st.number_input(f"Quantidade (múltiplos de {A.texto_qtd(tk, passo)})", min_value=float(passo), max_value=float(C.MAX_QTD_ORDEM),
                                                 value=float(st.session_state.get(kq, padrao)), step=float(passo), format="%.4f" if passo < 0.01 else "%.2f", key=kq))
        else:
            qtd = int(st.number_input("Quantidade (cotas inteiras)", min_value=1, max_value=C.MAX_QTD_ORDEM, value=int(st.session_state.get(kq, 100)), step=1, key=kq))
    if qtd < passo:
        st.warning("Valor pequeno demais para esse ativo.")
        return
    custo = qtd * ref * (1 + A.custo(tk)) if lado == "Comprar" else qtd * ref * (1 - A.custo(tk))
    pat = max(C.patrimonio(est, {k: v.get("c") for k, v in precos.items()}), 1.0)
    delta = qtd * ref * (1 if lado == "Comprar" else -1)
    cor = A.CLASSES[A.classe(tk)]["cor"]
    novo_peso = ((pos["q"] + (qtd if lado == "Comprar" else -qtd)) * ref) / pat * 100
    st.markdown(f"<div class='dz-posc-n' style='margin:6px 0'><span style='display:inline-block;width:10px;height:10px;border-radius:50%;"
                f"background:{html.escape(cor)};margin-right:8px'></span>{html.escape(A.rotulo(tk))}</div>", unsafe_allow_html=True)
    st.markdown(DC.grade([
        DC.indicador("Último preço", moeda(ref), precos[tk].get("v", 0)),
        DC.indicador("Custo estimado" if lado == "Comprar" else "Receita estimada", moeda(custo), detalhe=f"{A.texto_qtd(tk, qtd)} un."),
        DC.indicador("Peso no patrimônio", pct(novo_peso, 1)),
    ], 3), unsafe_allow_html=True)
    ef = _efeito_na_classe(est, tk, delta)
    if ef:
        st.markdown(DC.barra_progresso(ef[2] * 100, f"{ef[0]} na carteira", f"{ef[1]:.0%} → {ef[2]:.0%}"), unsafe_allow_html=True)
    st.markdown(DC.mensagem(f"Caixa disponível: {moeda(est.get('caixa', 0))}. Custo de negociação desta classe: {A.custo(tk):.2%} por operação. "
                            "O valor final usa a cotação do instante do envio e pode diferir da estimativa.", "info"), unsafe_allow_html=True)
    if st.button("Enviar ordem", type="primary", key="comp_enviar"):
        ok, msg = C.validar_ordem(est, perfil.get("pend") or [], "C" if lado == "Comprar" else "V", tk, qtd, precos)
        if not ok:
            st.error(msg)
            return
        liberado, aviso = _usar_limite()
        if not liberado:
            st.warning(aviso)
            return
        vivo = _cotacao_agora(tk)
        px = vivo or ref
        fonte = "cotação atual" if vivo else "último preço divulgado"
        try:                                                     # lê a carteira de novo: o cache da página pode estar atrasado
            atual = banco.comp_carteira_ler(a) or {}
        except Exception as e:
            banco.registrar_erro("competicao_app.carteira_ler", e)
            st.error("Não consegui ler sua carteira agora. Tente de novo.")
            return
        base = atual if atual.get("v") == 1 else C.novo_estado(perfil.get("entrada") or _agora().date().isoformat())
        ok, msg, novo = C.executar_agora(base, perfil.get("pend") or [], "C" if lado == "Comprar" else "V", tk, qtd, px, _agora())
        if not ok:
            st.error(msg)
            return
        try:
            banco.comp_carteira_gravar(a, novo)
        except Exception as e:
            banco.registrar_erro("competicao_app.carteira_gravar", e)
            st.error("A ordem não pôde ser salva. Tente de novo.")
            return
        st.session_state.pop(CH, None)
        WGA.esquecer()                                  # missões e conquistas releem a carteira
        st.session_state["comp_ok"] = f"Ordem executada: {lado.lower()} de {A.texto_qtd(tk, qtd)} × {A.rotulo(tk)} a {moeda(px)} ({fonte})."
        st.rerun()
    if st.session_state.get("comp_ok"):
        st.success(st.session_state.pop("comp_ok"))


# ------------------------------------------------------------------ regras
def _aba_regras():
    st.markdown(f"""
**Como funciona**
- Quem entra agora começa com **{moeda(C.CAPITAL_NOVO, 0)} ** (carteiras criadas antes continuam com o capital que já tinham). Não há retiradas nem aportes em dinheiro: o patrimônio muda por resultado das ordens, proventos, variação de preço e pelos **bônus e recompensas da Wallet Game**, que entram no caixa mas **não contam como retorno** no ranking.
- **O lucro vira capital.** O caixa inclui lucros de vendas e proventos, e você pode **reinvesti-lo** comprando mais. Há também o reinvestimento automático de proventos.
- O ranking usa o **retorno em %** ((patrimônio − bônus recebidos) ÷ capital inicial − 1), não valores em reais. Entra já no primeiro fechamento ({C.pregoes(C.MIN_DIAS_RANKING)} ou mais).
- **Execução imediata.** Ao enviar, a ordem é executada na hora, à cotação atual do ativo (fora do pregão, a última cotação disponível), e aparece na carteira e no extrato.
- **Universo:** todas as classes do app, as que tiverem cotação no fechamento. **Ações, FIIs e ETFs** da B3; **ETFs dos EUA** (VOO, QQQ, SCHD, VT, convertidos para reais); **criptomoedas** (Binance, em reais); **renda fixa** (Tesouro Selic, Prefixado e IPCA+ sem cupom, e uma renda fixa que rende 100% do CDI);
  **fundos**, que você adiciona pelo CNPJ (cota da CVM, com 1 a 2 dias úteis de atraso).
- **Limite de concentração:** no máximo {C.MAX_PESO:.0%} do patrimônio em um único ativo. CDI e Tesouro Selic, onde se guarda a reserva, ficam de fora do limite. B3: cotas inteiras. Cripto, fundos e renda fixa aceitam frações.
- **Custos:** {C.CUSTO_OPERACAO:.2%} em cada compra e venda na B3 e nos ETFs dos EUA, {A.CLASSES['cripto']['custo']:.2%} em cripto (taxa e diferença entre compra e venda) e zero em fundos e renda fixa. Proventos entram no caixa na data ex; desdobramentos ajustam a quantidade.
  O jogo simplifica: não desconta imposto de renda, IOF nem taxas de administração além do que já está embutido na cota.
- **Diversificação:** a aba **Diversificar** dá uma nota à sua carteira (classes, número de ativos, peso do maior e reserva) e propõe um desafio. A nota ensina o processo e **não entra no ranking**; a boa decisão da semana (5 ativos, 3 classes, nenhum acima de 25%) vale pontos na área Aprender.
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


_ICONES_WG = {"Meu patrimônio": ":material/account_balance_wallet:", "Rank e evolução": ":material/military_tech:", "Bônus e sequência": ":material/redeem:",
              "Missões": ":material/flag:", "Conquistas": ":material/emoji_events:", "Ranking": ":material/leaderboard:", "Negociar": ":material/swap_horiz:",
              "Diversificar": ":material/donut_small:", "Temporadas": ":material/calendar_month:", "Ligas": ":material/groups:", "Regras": ":material/menu_book:"}
_CSS_WG = (
    'html body .stApp.stApp .st-key-wgnav{margin:4px 0 14px;}'
    'html body .stApp.stApp .st-key-wgnav [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important;gap:8px !important;margin-bottom:8px;}'
    'html body .stApp.stApp .st-key-wgnav [data-testid="stColumn"]{flex:1 1 0 !important;min-width:0 !important;width:auto !important;}'
    'html body .stApp.stApp .st-key-wgnav button{width:100% !important;min-height:50px;border-radius:14px !important;padding:6px 8px !important;gap:6px !important;justify-content:center !important;}'
    'html body .stApp.stApp .st-key-wgnav button :is(p,span){font-size:.84rem !important;font-weight:800 !important;line-height:1.15 !important;white-space:normal !important;text-align:center !important;}'
)


def _ir_secao(nome: str) -> None:
    st.session_state["wg_sec"] = nome


def _menu_wallet(nomes: list[str]) -> str:
    """Botões internos da Wallet Game (duas colunas, sempre uma seção ativa). Substitui o menu expansivo."""
    st.markdown(f"<style>{_CSS_WG}</style>", unsafe_allow_html=True)
    atual = st.session_state.get("wg_sec", nomes[0])
    with st.container(key="wgnav"):
        for i in range(0, len(nomes), 2):
            cols = st.columns(2)
            for col, nome in zip(cols, nomes[i:i + 2]):
                with col:
                    st.button(nome, key=f"wg_n_{nome}", icon=_ICONES_WG.get(nome), type="primary" if nome == atual else "secondary",
                              on_click=_ir_secao, args=(nome,), width="stretch")
    return atual



def pagina_competicao():
    _capturar_convite()
    st.markdown(tema.cabecalho("🏆", "Competição de carteiras",
                               "Monte uma carteira virtual com ações, FIIs, ETFs, cripto, fundos e renda fixa, aprenda a diversificar e dispute o ranking. Dinheiro de mentira, aprendizado de verdade."),
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
    try:                                               # rank, bônus, missões e conquistas (também aplica créditos pendentes à carteira)
        res = WGA.resultado(a)
        if res["estado"].get("v") == 1 and (cart.get("apt") or 0) != (res["estado"].get("apt") or 0):
            c = _pessoa(a, True)
            perfil, cart = c["perfil"], c["cart"]
    except Exception as e:
        banco.registrar_erro("competicao_app.wallet_game", e)
        res = None
    if res:
        WGA.resumo(a, res)
    st.markdown(f"<div style='margin:14px 0 8px;font-size:.85rem;color:#B7AEE0'>Você compete como <b>{html.escape(perfil['apelido'])}</b>.</div>", unsafe_allow_html=True)
    if st.session_state.get("comp_convite") and not L.participa(_ligas(a), st.session_state["comp_convite"]):
        st.info("Você tem um convite de liga esperando: abra a aba **Ligas**.")
    nomes = (["Meu patrimônio", "Rank e evolução", "Bônus e sequência", "Missões", "Conquistas"] if res else []) + \
            ["Ranking", "Negociar", "Diversificar", "Temporadas", "Ligas", "Regras"]
    if st.session_state.get("wg_sec") not in nomes:
        st.session_state["wg_sec"] = nomes[0]
    sec = _menu_wallet(nomes)                          # botões fixos; só a seção escolhida é calculada
    with st.container():
        if sec == "Meu patrimônio":
            _aba_carteira(a, perfil, cart)
        elif sec == "Rank e evolução":
            WGA.aba_rank(res)
        elif sec == "Bônus e sequência":
            WGA.aba_bonus(a, res)
        elif sec == "Missões":
            WGA.aba_missoes(res)
        elif sec == "Conquistas":
            WGA.aba_conquistas(res)
        elif sec == "Ranking":
            _aba_ranking(perfil, cart)
        elif sec == "Negociar":
            _aba_negociar(a, perfil, cart)
        elif sec == "Diversificar":
            DV.aba_diversificar(cart, C.novo_estado(perfil.get("entrada") or _agora().date().isoformat()))
        elif sec == "Temporadas":
            _aba_temporadas(perfil, cart)
        elif sec == "Ligas":
            _aba_ligas(a, perfil, cart)
        else:
            _aba_regras()
