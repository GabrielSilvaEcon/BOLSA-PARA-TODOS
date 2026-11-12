"""Página Competição: carteira virtual, ordens a preço de fechamento e ranking entre os usuários (lógica em competicao.py)."""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
import secoes
import estilo_app as ES
import carteira_visual as CV
import arte_tickerhunters as AT

import ativos_jogo as A
import banco
import competicao as C
import cotacoes_jogo as CJ
import diversificacao as D
import diversificar_app as DV
import fundos as fd
import competicao_ligas as L
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
    st.markdown("#### Entrar na Wallet Game")
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


def _aba_ranking(perfil: dict, cart: dict, res: dict | None = None):
    """Classificação única em cartões: retorno, patrimônio, queda máxima, Sharpe e pregões. A pessoa escolhe a ordem (Retorno, Patrimônio ou Risco)
    e, se quiser, filtra por liga (Bronze a Mestre) e período. Perfis de demonstração (ranking_ligas.DEMO) completam a lista e vêm marcados."""
    import ranking_ligas as RL
    rk = _publico("comp_ranking")
    listas = (rk or {}).get("listas") or {}
    base = [(n, m, c) for _i, n, m, c in WG.RANKS]
    cap_ref = 10_000.0
    eu = {"apelido": perfil.get("apelido") or "", "patrimonio": None} if perfil.get("apelido") else None     # destaca você mesmo sem o resumo da carteira
    if res:
        fx = res["rank"]["faixas"]
        cap_ref = 10_000.0 * (fx[1][1] / WG.RANKS[1][2])
        eu = {"apelido": perfil.get("apelido") or "", "patrimonio": res["rank"]["patrimonio"]}
    if not listas.get("geral") and not RL.DEMO:
        st.info("O ranking aparece assim que sai o primeiro fechamento: você entra já com " + C.pregoes(C.MIN_DIAS_RANKING) + " de histórico. "
                "Ele é atualizado nos dias úteis, depois do fechamento do mercado (por volta das 18h30). Ordens enviadas até as 17h valem para o fechamento do mesmo dia.")
        return
    c1, c2 = st.columns(2)
    with c1:
        liga = st.selectbox("Liga", ["Todas as ligas"] + [n for n, _m, _c in base], key="cl_liga")
    with c2:
        per = st.selectbox("Período", list(RL.PERIODOS), key="cl_per")
    st.caption("Ordenar por")
    ordem = ES.abas("cl_ord", RL.ORDENS, colunas=3)
    linhas = RL.montar(listas, RL.PERIODOS[per], base, cap_ref, eu)
    itens = RL.ordenar(linhas, ordem, None if liga == "Todas as ligas" else liga)
    if not itens:
        st.info("Ainda não há participantes nesta liga.")
        return
    st.markdown(RL.html_cartoes(itens, ordem), unsafe_allow_html=True)
    if rk and rk.get("dia"):
        st.caption(f"Atualizado após o fechamento de {_data_br(rk.get('dia'))}. Entra quem tem {C.pregoes(C.MIN_DIAS_RANKING)} ou mais.")
    meu = (cart.get("rank") or {})
    if perfil.get("aceite") and not meu.get("geral") and len(cart.get("hist") or []) < C.MIN_DIAS_RANKING:
        st.info("Você entra no ranking no próximo fechamento (dias úteis, por volta das 18h30).")
    if meu.get("conflito"):
        st.warning("Seu apelido ficou igual ao de outra pessoa e você está fora do ranking. Troque o apelido na aba “Carteira”.")
    if RL.DEMO:
        st.caption("Perfis marcados como demonstração são fictícios, com números inventados só para simular a classificação. "
                   "Carteira virtual: retorno alto com queda máxima grande indica mais risco, e resultados passados não garantem resultados futuros.")
    else:
        st.caption("Carteira virtual: retorno alto com queda máxima grande indica mais risco, e resultados passados não garantem resultados futuros. "
                   "Sharpe sem taxa livre de risco: serve para comparar participantes.")


# ------------------------------------------------------------------ minha carteira
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


def _aba_carteira(a, perfil: dict, cart: dict, res: dict | None = None):
    est = cart if cart.get("v") == 1 else C.novo_estado(perfil.get("entrada") or _agora().date().isoformat())
    CV.mostrar(est, res)                                     # patrimônio, ativos, Comprar/Vender, desempenho e missão (mesmos dados de antes)
    if not cart:
        st.info("Sua carteira aparece depois do primeiro fechamento (dias úteis, por volta das 18h30). Você já pode enviar ordens em Comprar.")
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


def _limpar_sel() -> None:
    st.session_state.pop("cn_sel", None)


def _escolher_ativo(tk: str) -> None:
    st.session_state["cn_sel"] = tk


def _voltar_carteira() -> None:
    st.session_state.pop("cn_sel", None)
    st.session_state["wg_sec"] = "Meu patrimônio"


def _passo(k: str, delta, minimo, maximo) -> None:
    v = st.session_state.get(k, minimo) + delta
    v = min(max(v, minimo), maximo)
    st.session_state[k] = round(v, 4) if isinstance(minimo, float) else int(v)


def _p2(v: float) -> str:
    return f"{v:.2f}".replace(".", ",")


def _dados_ativo(tk: str, p: dict) -> dict:
    c = A.classe(tk)
    cl = A.CLASSES.get(c) or {"cor": "#8B6CFF", "icone": "•", "nome": ""}
    rot_ = A.rotulo(tk)
    return {"cl": cl, "codigo": rot_.split(" · ")[-1] if " · " in rot_ else rot_, "nome": rot_.split(" · ")[0] if " · " in rot_ else cl.get("nome", ""),
            "preco": float(p.get("c") or 0), "var": float(p.get("v") or 0)}


def _html_linha(tk: str, p: dict, est: dict, lado: str) -> str:
    """Linha da lista de escolha: ícone da classe, código, nome, preço e variação (venda: o que você tem e o resultado)."""
    d = _dados_ativo(tk, p)
    pos = (est.get("pos") or {}).get(tk)
    if lado == "Vender" and pos:
        res = (d["preco"] / pos["pm"] - 1) * 100 if pos.get("pm") else 0.0
        sub, v, rot_ = f"{A.texto_qtd(tk, pos['q'])} em carteira", res, "resultado"
    else:
        sub, v, rot_ = d["nome"], d["var"], "no dia"
    seta = "▲" if v >= 0 else "▼"
    return (f"<div class='cn-l'><div class='cn-ic' style='--c:{html.escape(d['cl']['cor'])}'>{html.escape(d['cl']['icone'])}</div>"
            f"<div class='cn-tx'><b>{html.escape(d['codigo'])}</b><span>{html.escape(sub)}</span>"
            f"<em class='{'v' if v >= 0 else 'n'}'><u>{html.escape(moeda(d['preco']))}</u> {seta} {_p2(abs(v))}% <small>{rot_}</small></em></div></div>")


def _html_topo(titulo: str, balao: str, pose: str, texto: str = "") -> str:
    dsc = f"<div class='cn-dsc'>{html.escape(texto)}</div>" if texto else ""
    return (f"<div class='cn-top'><div class='cn-tc'><div class='cn-tl'>{AT.img('grafico_alta', 34)}<b>{html.escape(titulo)}</b></div></div>"
            f"<div class='cn-tr'><div class='cn-bal'>{html.escape(balao)}</div><div class='cn-mas'>{AT.img(AT.pose(pose), 92, alt='Caramelo, o mascote')}</div></div>{dsc}</div>")


def _html_selecionado(tk: str, p: dict, lado: str, spark: list | None) -> str:
    d = _dados_ativo(tk, p)
    v = d["var"]
    cor = "#2EE59D" if v >= 0 else "#FF5B6E"
    seta = "▲" if v >= 0 else "▼"
    graf = CV.spark(spark, cor, "sel", 160, 54) if spark else ""
    return (f"<div class='cn-sel'><div class='cn-sh'><div class='cn-ic g' style='--c:{html.escape(d['cl']['cor'])}'>{html.escape(d['cl']['icone'])}</div>"
            f"<div class='cn-tx'><b class='gr'>{html.escape(d['codigo'])}</b><span>{html.escape(d['nome'])}</span></div></div>"
            f"<div class='cn-px'>{html.escape(moeda(d['preco']))}</div><div class='cn-pv' style='color:{cor}'>{seta} {_p2(abs(v))}% <small>no dia</small></div>"
            f"<div class='cn-gr'>{graf}</div></div>")


def _html_painel(icone: str, titulo: str, corpo: str) -> str:
    return f"<div class='cn-pn'><div class='cn-pt'>{AT.img(icone, 22)}<b>{html.escape(titulo)}</b></div>{corpo}</div>"


def _campo_busca() -> str:
    """Campo de busca. Com o pacote st-keyup a lista atualiza a cada letra digitada (como na referência); sem ele, atualiza ao dar Enter."""
    ph = "Ticker ou nome: PETR4, Petrobras..."
    try:
        from st_keyup import st_keyup
        try:
            v = st_keyup("Buscar ativo", key="cn_q", placeholder=ph, debounce=250, label_visibility="collapsed")
        except TypeError:
            v = st_keyup("Buscar ativo", key="cn_q", debounce=250)
        return v or ""
    except Exception:
        pass
    try:
        return st.text_input("Buscar ativo", key="cn_q", placeholder=ph, max_chars=30, label_visibility="collapsed", icon=":material/search:")
    except TypeError:
        return st.text_input("Buscar ativo", key="cn_q", placeholder=ph, max_chars=30, label_visibility="collapsed")


def _vitrine(est: dict, precos: dict, por_classe: dict, disp: list, rot: dict, lado: str, extras: dict, sel: str | None = None) -> None:
    """Passos 2 e 3 do fluxo: buscar e selecionar o ativo. Comprar: por classe, com busca. Vender: só o que você tem."""
    ss = st.session_state
    st.button("Voltar", key="cn_voltar", icon=":material/arrow_back:", on_click=_voltar_carteira)
    st.markdown(ES.css_voltar("cn_voltar"), unsafe_allow_html=True)
    q = ""
    with st.container(key="cn_hero"):                  # igual à referência: busca ao lado do mascote com balão
        ce, cd = st.columns([1.5, 1])
        with ce:
            st.markdown(f"<div class='cn-tl'>{AT.img('grafico_alta', 34)}<b>{lado} Ativo</b></div>", unsafe_allow_html=True)
            if lado == "Comprar":
                with st.container(key="cn_busca"):
                    q = _campo_busca()
        with cd:
            if sel:
                bal = "Ótima escolha! Agora é só definir quanto comprar!" if lado == "Comprar" else "Vamos realizar o lucro? Defina quanto vender."
            else:
                bal = "Digite o código da ação ou o nome da empresa!" if lado == "Comprar" else "Qual ativo vamos vender?"
            st.markdown(f"<div class='cn-tr'><div class='cn-bal'>{html.escape(bal)}</div><div class='cn-mas'>{AT.img(AT.pose('animado'), 92, alt='Caramelo, o mascote')}</div></div>",
                        unsafe_allow_html=True)
    st.markdown(DC.mensagem("Aqui você compra qualquer ativo da bolsa (ações, FIIs, ETFs, cripto, fundos e renda fixa) e também vende os que já tem na carteira."
                            if lado == "Comprar" else "Aqui você vende os ativos que já tem. Toque em Selecionar no ativo que quer vender.", "info"), unsafe_allow_html=True)
    if lado == "Vender":
        itens = sorted([t for t in (est.get("pos") or {}) if t in precos], key=lambda t: -(est["pos"][t]["q"] * float(precos[t]["c"])))
        if not itens:
            st.markdown(DC.mensagem("Você ainda não tem ativos para vender. Toque em Comprar para montar sua carteira.", "info"), unsafe_allow_html=True)
            return
        _lista(itens, precos, est, "Vender")
        return
    por_classe = A.agrupar_por_classe({**precos, **extras})
    precos.update({k: v for k, v in extras.items() if k not in precos})
    opcoes = sorted({t for c in A.ORDEM for t in por_classe[c]}, key=lambda t: A.rotulo(t).lower())
    if not opcoes:
        st.info("Nenhum ativo com cotação agora. Tente de novo mais tarde.")
        return
    with st.expander("Comprar um fundo de investimento (pelo CNPJ)", icon=":material/account_balance:"):
        _entrada_fundo(extras, bool(por_classe["fundo"]))
    if not q.strip():                                   # sem sugestões: a lista só aparece quando a pessoa busca
        return
    opcoes = [t for t in opcoes if q.strip().lower() in A.rotulo(t).lower()]
    if not opcoes:
        st.info("Nenhum ativo encontrado com essa busca.")
        return
    n = int(ss.get("cn_n", 6))
    _lista(opcoes[:n], precos, est, "Comprar")
    if len(opcoes) > n:
        st.button(f"Mostrar mais ({len(opcoes) - n})", key="cn_mais", icon=":material/expand_more:", width="stretch",
                  on_click=lambda k="cn_n", v=n + 6: ss.__setitem__(k, v))


def _lista(itens: list, precos: dict, est: dict, lado: str) -> None:
    with st.container(key="cn_lista"):
        for tk in itens:
            with st.container(key=f"cn_{lado[0]}_{_chave(tk)}"):
                c1, c2 = st.columns([3.1, 1.5])
                c1.markdown(_html_linha(tk, precos[tk], est, lado), unsafe_allow_html=True)
                c2.button("Selecionar", key=f"cn_b_{lado[0]}_{_chave(tk)}", on_click=_escolher_ativo, args=(tk,), width="stretch")


def _spark_ativo(tk: str) -> list | None:
    if A.classe(tk) not in ("acao", "fii", "etf"):
        return None
    try:
        import carteira as CT
        s = CT._hist(tk, "1mo")
        if s is not None and len(s) >= 2:
            return [float(x) for x in s.values[-30:]]
    except Exception:
        pass
    return None


def _html_comprovante(r: dict) -> str:
    """Comprovante da ordem (vai para o pop-up): ativo, quantidade, preço, total e saldo."""
    compra = r["lado"] == "Comprar"
    total = abs(float(r.get("caixa_depois", 0)) - float(r.get("caixa_antes", 0))) if "caixa_depois" in r else r["total"]
    linhas = [("Ativo", A.rotulo(r["tk"])), ("Quantidade", f"{A.texto_qtd(r['tk'], r['qtd'])} un."), ("Preço", moeda(r["px"])),
              ("Total debitado" if compra else "Total recebido", moeda(total))]
    if "caixa_depois" in r:
        linhas.append(("Saldo agora", moeda(r["caixa_depois"])))
    corpo = "".join(f"<div class='r'><span>{html.escape(k)}</span><b>{html.escape(v)}</b></div>" for k, v in linhas)
    return (f"<div class='wg-comp'><div class='top'>{AT.img(AT.pose('celebrando'), 70)}<div><b>{'Compra' if compra else 'Venda'} realizada!</b>"
            f"<span>Preço: {html.escape(r['fonte'])}</span></div></div>{corpo}</div>")


CSS_VIT = ("<style>"
           "html body .stApp.stApp .cn-top{display:flex;justify-content:space-between;align-items:center;gap:8px;margin:6px 0 10px;background:linear-gradient(160deg,#10204A,#0A1433 78%);"
           "border:1px solid #2B4A8C;border-radius:20px;padding:8px 10px 0 14px;overflow:hidden;flex-wrap:wrap}"
           "html body .stApp.stApp .cn-tc{flex:1;min-width:0;padding-bottom:10px}"
           "html body .stApp.stApp .cn-dsc{flex:0 0 100%;color:#B7C8F2;font-size:.82rem;line-height:1.45;padding:10px 4px 12px 0;border-top:1px solid rgba(80,115,190,.35)}"
           "html body .stApp.stApp .cn-tl{display:flex;align-items:center;gap:8px;color:#fff;font-size:1.1rem;font-weight:900;white-space:nowrap}"
           "html body .stApp.stApp .cn-tr{display:flex;align-items:flex-end;gap:4px;min-width:0}"
           "html body .stApp.stApp .cn-bal{background:#FFE9C2;color:#4A2E08;font-weight:800;font-size:.7rem;line-height:1.2;border-radius:14px 14px 4px 14px;padding:6px 8px;max-width:100px;margin-bottom:26px;box-shadow:0 3px 8px rgba(0,0,0,.35)}"
           "html body .stApp.stApp .st-key-cn_hero{margin:6px 0 10px;background:linear-gradient(160deg,#10204A,#0A1433 78%);border:1px solid #2B4A8C;border-radius:22px;padding:12px 12px 8px;box-shadow:0 8px 22px rgba(2,6,23,.45)}"
           "html body .stApp.stApp .st-key-cn_hero [data-testid='stHorizontalBlock']{flex-wrap:nowrap !important;gap:8px !important;align-items:flex-end !important}"
           "html body .stApp.stApp .st-key-cn_hero [data-testid='stColumn']{min-width:0 !important}"
           "html body .stApp.stApp .st-key-cn_hero .cn-tl{margin:0 0 10px;white-space:normal}"
           "html body .stApp.stApp .st-key-cn_hero .cn-tr{flex-direction:column;align-items:flex-end;gap:4px}"
           "html body .stApp.stApp .st-key-cn_hero .cn-bal{margin-bottom:0;max-width:100%;font-size:.68rem;border-radius:14px 14px 4px 14px}"
           "html body .stApp.stApp .cn-mas{animation:cv-flut 3.6s ease-in-out infinite}"
           "html body .stApp.stApp .cn-mas img{display:block}"
           "html body .stApp.stApp .st-key-cn_busca [data-testid='stTextInputRootElement']{border-radius:999px !important;border:2px solid #36B7E8 !important;background:#0B1433 !important;min-height:50px;box-shadow:0 0 14px rgba(54,183,232,.28);padding-left:6px}"
           "html body .stApp.stApp .st-key-cn_busca :is([data-baseweb='input'],[data-baseweb='base-input'],input){border:0 !important;outline:none !important;box-shadow:none !important;background:transparent !important;color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:700 !important}"
           "html body .stApp.stApp .st-key-cn_lista{background:linear-gradient(160deg,#10204A,#0A1433 78%);border:1px solid #2B4A8C;border-radius:20px;padding:4px 10px;margin:10px 0}"
           "html body .stApp.stApp [class*='st-key-cn_C_'],html body .stApp.stApp [class*='st-key-cn_V_']{border-bottom:1px solid rgba(80,115,190,.28);padding:10px 0 14px}"
           "html body .stApp.stApp .cn-l{display:flex;align-items:center;gap:10px;min-width:0}"
           "html body .stApp.stApp .cn-ic{flex:none;width:42px;height:42px;border-radius:12px;display:grid;place-items:center;font-size:1.3rem;"
           "background:radial-gradient(circle at 30% 20%,color-mix(in srgb,var(--c) 55%,#fff),var(--c) 72%);box-shadow:0 3px 0 color-mix(in srgb,var(--c) 45%,#050B1F)}"
           "html body .stApp.stApp .cn-ic.g{width:60px;height:60px;font-size:1.9rem;border-radius:16px}"
           "html body .stApp.stApp .cn-tx{min-width:0}html body .stApp.stApp .cn-tx b{display:block;color:#fff;font-weight:900;font-size:1.02rem;line-height:1.15}"
           "html body .stApp.stApp .cn-tx b.gr{font-size:1.6rem}"
           "html body .stApp.stApp .cn-tx span{display:block;color:#9FB6EA;font-size:.78rem;font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}"
           "html body .stApp.stApp .cn-tx em{display:block;font-style:normal;font-weight:900;font-size:.82rem;margin-top:1px}"
           "html body .stApp.stApp .cn-tx em u{text-decoration:none;color:#fff}html body .stApp.stApp .cn-tx em.v{color:#2EE59D}html body .stApp.stApp .cn-tx em.n{color:#FF5B6E}"
           "html body .stApp.stApp .cn-tx em small{color:#7F96C9;font-weight:600;font-size:.66rem}"
           "html body .stApp.stApp [class*='st-key-cn_b_'] button{min-height:44px !important;border-radius:14px !important;border:0 !important;background:linear-gradient(180deg,#2F55D8,#1B2F9A) !important;box-shadow:0 4px 0 #101C66 !important}"
           "html body .stApp.stApp [class*='st-key-cn_b_V'] button{background:linear-gradient(180deg,#FF5B5B,#D61F2C) !important;box-shadow:0 4px 0 #A0121D !important}"
           "html body .stApp.stApp [class*='st-key-cn_b_'] button:active{transform:translateY(3px);box-shadow:none !important}"
           "html body .stApp.stApp [class*='st-key-cn_b_'] button :is(p,span){color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:800 !important;font-size:.88rem !important}"
           "html body .stApp.stApp [data-testid='stHorizontalBlock']:has([class*='st-key-cn_b_']),html body .stApp.stApp .st-key-cn_qtd [data-testid='stHorizontalBlock']{flex-wrap:nowrap !important;gap:8px !important;align-items:center}"
           "html body .stApp.stApp [data-testid='stHorizontalBlock']:has([class*='st-key-cn_b_']) [data-testid='stColumn'],html body .stApp.stApp .st-key-cn_qtd [data-testid='stColumn']{min-width:0 !important}"
           "html body .stApp.stApp .cn-sel{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:2px 8px;background:radial-gradient(circle at 85% 30%,rgba(46,229,157,.14),transparent 55%),linear-gradient(160deg,#10204A,#0A1433 78%);"
           "border:1px solid #2B4A8C;border-radius:22px;padding:14px;margin:8px 0}"
           "html body .stApp.stApp .cn-sh{grid-column:1/-1;display:flex;align-items:center;gap:12px;min-width:0}"
           "html body .stApp.stApp .cn-px{color:#fff;font-weight:900;font-size:1.7rem;line-height:1.1}html body .stApp.stApp .cn-pv{font-weight:900;font-size:.9rem;align-self:end;text-align:right}"
           "html body .stApp.stApp .cn-pv small{color:#7F96C9;font-weight:600}html body .stApp.stApp .cn-gr{grid-column:1/-1;height:54px}html body .stApp.stApp .cn-gr svg{width:100%;height:100%;display:block}"
           "html body .stApp.stApp .cn-pn{background:linear-gradient(160deg,#10204A,#0A1433 78%);border:1px solid #2B4A8C;border-radius:20px;padding:12px 14px;margin:10px 0}"
           "html body .stApp.stApp .cn-pt{display:flex;align-items:center;gap:8px;color:#fff;font-size:.95rem}"
           "html body .stApp.stApp .cn-big{text-align:center;color:#fff;font-weight:900;font-size:1.9rem;margin-top:6px}html body .stApp.stApp .cn-sm{text-align:center;color:#9FB6EA;font-size:.8rem;margin-top:2px}"
           "html body .stApp.stApp .cn-sd{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:6px;margin-top:8px;text-align:center}"
           "html body .stApp.stApp .cn-sd b{display:block;color:#FFD66B;font-size:1.05rem;font-weight:900}html body .stApp.stApp .cn-sd span{color:#9FB6EA;font-size:.74rem}html body .stApp.stApp .cn-sd i{font-style:normal;color:#2EE59D;font-size:1.4rem;font-weight:900}"
           "html body .stApp.stApp .st-key-cn_qtd{background:linear-gradient(160deg,#10204A,#0A1433 78%);border:1px solid #2B4A8C;border-radius:20px;padding:10px 12px;margin:10px 0 0}"
           "html body .stApp.stApp .st-key-cn_qtd [data-testid='stNumberInputStepUp'],html body .stApp.stApp .st-key-cn_qtd [data-testid='stNumberInputStepDown']{display:none !important}"
           "html body .stApp.stApp .st-key-cn_qtd input{text-align:center !important;font-size:1.8rem !important;font-weight:900 !important;color:#fff !important;-webkit-text-fill-color:#fff !important;background:#070E26 !important;border-radius:16px !important}"
           "html body .stApp.stApp [class*='st-key-cn_pm_'] button{min-height:52px !important;border-radius:16px !important;border:0 !important;background:linear-gradient(180deg,#2F55D8,#1B2F9A) !important;box-shadow:0 4px 0 #101C66 !important}"
           "html body .stApp.stApp [class*='st-key-cn_pm_'] button :is(p,span){color:#fff !important;-webkit-text-fill-color:#fff !important;font-size:1.6rem !important;font-weight:900 !important}"
           "html body .stApp.stApp [class*='st-key-cn_conf_'] button{min-height:62px !important;border-radius:999px !important;border:0 !important;width:100% !important;transition:transform .1s,filter .2s}"
           "html body .stApp.stApp .st-key-cn_conf_C button{background:linear-gradient(180deg,#38E26B,#12A83C) !important;box-shadow:0 5px 0 #0B7A2B,0 8px 22px rgba(46,229,100,.4) !important}"
           "html body .stApp.stApp .st-key-cn_conf_V button{background:linear-gradient(180deg,#FF5B5B,#D61F2C) !important;box-shadow:0 5px 0 #A0121D,0 8px 22px rgba(255,80,80,.38) !important}"
           "html body .stApp.stApp [class*='st-key-cn_conf_'] button:active{transform:translateY(4px) scale(.985);box-shadow:none !important}"
           "html body .stApp.stApp [class*='st-key-cn_conf_'] button :is(p,span){color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:900 !important;font-size:1.25rem !important}"
           "html body .stApp.stApp.stApp .st-key-ab_comp_lado_0 button,html body .stApp.stApp.stApp .st-key-ab_comp_lado_1 button{border:2px solid transparent !important;transition:transform .1s,filter .2s}"
           "html body .stApp.stApp.stApp .st-key-ab_comp_lado_0 button{background:rgba(46,229,100,.10) !important;border-color:#2EE564 !important;box-shadow:0 4px 0 #0B7A2B !important}"
           "html body .stApp.stApp.stApp .st-key-ab_comp_lado_1 button{background:rgba(255,91,91,.10) !important;border-color:#FF5B5B !important;box-shadow:0 4px 0 #A0121D !important}"
           "html body .stApp.stApp.stApp .st-key-ab_comp_lado_0 button[data-testid^='stBaseButton-primary']{background:linear-gradient(180deg,#38E26B,#12A83C) !important;border-color:#7CFFA3 !important}"
           "html body .stApp.stApp.stApp .st-key-ab_comp_lado_1 button[data-testid^='stBaseButton-primary']{background:linear-gradient(180deg,#FF5B5B,#D61F2C) !important;border-color:#FF9A9A !important}"
           "html body .stApp.stApp.stApp .st-key-ab_comp_lado_0 button :is(p,span),html body .stApp.stApp.stApp .st-key-ab_comp_lado_1 button :is(p,span){color:#fff !important;-webkit-text-fill-color:#fff !important;font-weight:900 !important;font-size:1.05rem !important}"
           "html body .stApp.stApp.stApp .st-key-ab_comp_lado_0 button:active,html body .stApp.stApp.stApp .st-key-ab_comp_lado_1 button:active{transform:translateY(3px);box-shadow:none !important}"
           "</style>")


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
    por_classe = A.agrupar_por_classe(precos)
    disp = [c for c in A.ORDEM if por_classe[c] or c == "fundo"]
    rot = {c: f"{A.CLASSES[c]['icone']} {A.CLASSES[c]['nome']}" for c in disp}
    st.markdown(CSS_NEG + CSS_VIT, unsafe_allow_html=True)
    _abrir_dialogo_ordem(a, perfil, est)
    _resultado_ordem()
    lado = st.session_state.get("comp_lado", "Comprar")
    if lado not in ("Comprar", "Vender"):
        lado = "Comprar"
    tk = st.session_state.get("cn_sel")
    if tk and (tk not in precos or (lado == "Vender" and tk not in (est.get("pos") or {}))):
        tk = None
        st.session_state.pop("cn_sel", None)
    _vitrine(est, precos, por_classe, disp, rot, lado, extras, sel=tk)         # busca, lista e negociação na MESMA tela
    if not tk:
        st.caption(f"Cotações do fechamento de {_data_br(pr.get('dia'))}. As ordens são executadas na hora, à cotação atual do ativo "
                   "(fora do pregão, a última cotação disponível; fundos, Tesouro e CDI usam o último preço divulgado).")
        return
    # ---- negociar o ativo escolhido, logo abaixo da lista (quantidade, valor e saldo restante)
    compra = lado == "Comprar"
    st.markdown(_html_selecionado(tk, precos[tk], lado, _spark_ativo(tk)), unsafe_allow_html=True)
    ES.abas("comp_lado", ["Comprar", "Vender"], colunas=2)             # como na referência: Comprar/Vender dentro do cartão do ativo
    ref = float(precos[tk]["c"])
    pos = (est.get("pos") or {}).get(tk, {"q": 0})
    passo = A.passo(tk)
    fracionado = passo < 1
    if compra:
        maxq = _max_compra(est, pend, ref, tk, precos)
    else:
        maxq = A.norm_qtd(tk, max(0.0, pos["q"] - sum(o["q"] for o in pend if o["l"] == "V" and o["t"] == tk)))
    kq, kv = f"comp_qtd_{_chave(tk)}", f"comp_val_{_chave(tk)}"
    modo = ES.abas("comp_modo", ["Quantidade", "Valor em T$"], rotulo=lambda m: {"Quantidade": "Por quantidade", "Valor em T$": "Por valor (T$)"}[m], colunas=2)
    unid = A.CLASSES[A.classe(tk)].get("nome", "ativos").lower()
    if modo == "Valor em T$":
        valor = st.number_input("Valor em T$", min_value=1.0, max_value=100_000_000.0, value=float(st.session_state.get(kv, 1000.0)), step=100.0, key=kv)
        base = valor / (ref * (1 + A.custo(tk))) if compra else valor / ref
        qtd = A.piso_qtd(tk, base)
    else:
        padrao = (A.piso_qtd(tk, 1000.0 / ref) or passo) if fracionado else 10
        if kq not in st.session_state:
            st.session_state[kq] = float(padrao) if fracionado else int(padrao)
        mn = float(passo) if fracionado else 1
        mx = float(C.MAX_QTD_ORDEM) if fracionado else int(C.MAX_QTD_ORDEM)
        st.markdown(f"<div class='cn-pt' style='margin:10px 4px 4px'>{AT.img('barras_verdes', 22)}<b>Quantidade</b></div>", unsafe_allow_html=True)
        with st.container(key="cn_qtd"):
            cm, cn_, cp = st.columns([1, 2.2, 1])
            cm.button("−", key="cn_pm_menos", on_click=_passo, args=(kq, -(float(passo) if fracionado else 1), mn, mx), width="stretch")
            qin = cn_.number_input("Quantidade", min_value=mn, max_value=mx, step=float(passo) if fracionado else 1, key=kq, label_visibility="collapsed",
                                   format=("%.4f" if passo < 0.01 else "%.2f") if fracionado else "%d")
            cp.button("+", key="cn_pm_mais", on_click=_passo, args=(kq, (float(passo) if fracionado else 1), mn, mx), width="stretch")
        qtd = A.norm_qtd(tk, qin) if fracionado else int(qin)
        st.markdown(f"<div class='cn-sm'>Você {'comprará' if compra else 'venderá'} {html.escape(A.texto_qtd(tk, qtd))} {html.escape(unid)}</div>", unsafe_allow_html=True)
    if st.button(f"Usar o máximo ({A.texto_qtd(tk, maxq)})", key="comp_max", disabled=maxq < passo, icon=":material/bolt:",
                 help="Compra: usa o caixa livre (inclui lucros e proventos) respeitando o limite de concentração. Venda: toda a posição."):
        st.session_state[kq] = max(passo, maxq) if fracionado else int(max(1, maxq))
        st.session_state[kv] = round(max(1.0, float(max(passo, maxq)) * ref), 2)
        st.rerun()
    if qtd < passo:
        st.warning("Valor pequeno demais para esse ativo.")
        return
    custo = qtd * ref * (1 + A.custo(tk)) if compra else qtd * ref * (1 - A.custo(tk))
    pat = max(C.patrimonio(est, {k: v.get("c") for k, v in precos.items()}), 1.0)
    delta = qtd * ref * (1 if compra else -1)
    novo_peso = ((pos["q"] + (qtd if compra else -qtd)) * ref) / pat * 100
    caixa = float(est.get("caixa", 0))
    depois = caixa - custo if compra else caixa + custo
    st.markdown(_html_painel("dinheiro_alta", "Valor Estimado" if compra else "Receita Estimada",
                             f"<div class='cn-big'>{html.escape(moeda(custo))}</div><div class='cn-sm'>({html.escape(moeda(ref))} por unidade · peso na carteira {_p2(novo_peso)}%)</div>"),
                unsafe_allow_html=True)
    st.markdown(_html_painel("saco_dinheiro", "Seu Saldo",
                             f"<div class='cn-sd'><div><b>{html.escape(moeda(caixa))}</b><span>Antes {'da compra' if compra else 'da venda'}</span></div><i>→</i>"
                             f"<div><b>{html.escape(moeda(depois))}</b><span>Após {'a compra' if compra else 'a venda'}</span></div></div>"), unsafe_allow_html=True)
    ef = _efeito_na_classe(est, tk, delta)
    if ef:
        st.markdown(DC.barra_progresso(ef[2] * 100, f"{ef[0]} na carteira", f"{ef[1]:.0%} → {ef[2]:.0%}"), unsafe_allow_html=True)
    st.markdown(DC.mensagem(f"Custo de negociação desta classe: {A.custo(tk):.2%} por operação. O valor final usa a cotação do instante da confirmação e pode diferir um pouco da estimativa.", "info"), unsafe_allow_html=True)
    with st.container(key=f"cn_conf_{'C' if compra else 'V'}"):
        confirmar = st.button("Confirmar Compra" if compra else "Confirmar Venda", key="cn_confirmar", icon=":material/check_circle:", width="stretch")
    if confirmar:
        ok, msg = C.validar_ordem(est, perfil.get("pend") or [], "C" if compra else "V", tk, qtd, precos)
        if not ok:
            st.error(msg)
            return
        st.session_state["comp_res"] = _executar_ordem(a, perfil, {"lado": lado, "tk": tk, "qtd": qtd, "ref": ref, "custo": custo})
        st.rerun()


def _executar_ordem(a, perfil: dict, conf: dict) -> dict:
    """Executa a ordem confirmada: revalida, usa o limite de ordens, pega a cotação atual e grava. Devolve {"ok", "msg", ...} para a tela."""
    lado, tk, qtd, ref = conf["lado"], conf["tk"], conf["qtd"], conf["ref"]
    letra = "C" if lado == "Comprar" else "V"
    liberado, aviso = _usar_limite()
    if not liberado:
        return {"ok": False, "msg": aviso}
    vivo = _cotacao_agora(tk)
    px = vivo or ref
    fonte = "cotação atual" if vivo else "último preço divulgado"
    try:                                                     # lê a carteira de novo: o cache da página pode estar atrasado
        atual = banco.comp_carteira_ler(a) or {}
    except Exception as e:
        banco.registrar_erro("competicao_app.carteira_ler", e)
        return {"ok": False, "msg": "Não consegui ler sua carteira agora. Tente de novo."}
    base = atual if atual.get("v") == 1 else C.novo_estado(perfil.get("entrada") or _agora().date().isoformat())
    ok, msg, novo = C.executar_agora(base, perfil.get("pend") or [], letra, tk, qtd, px, _agora())
    if not ok:
        return {"ok": False, "msg": msg}
    try:
        banco.comp_carteira_gravar(a, novo)
    except Exception as e:
        banco.registrar_erro("competicao_app.carteira_gravar", e)
        return {"ok": False, "msg": "A ordem não pôde ser salva. Tente de novo."}
    st.session_state.pop(CH, None)
    st.session_state.pop("cn_sel", None)           # volta à vitrine de ativos depois da ordem
    WGA.esquecer()                                  # missões e conquistas releem a carteira
    return {"ok": True, "lado": lado, "tk": tk, "qtd": qtd, "px": px, "fonte": fonte, "total": qtd * px,
            "caixa_antes": float(base.get("caixa", 0)), "caixa_depois": float(novo.get("caixa", 0))}


def _resultado_ordem() -> None:
    """Resultado da última ordem: cartão de recompensa animado (fx_arte) se deu certo; aviso se não."""
    r = st.session_state.pop("comp_res", None)
    if not r:
        return
    if not r["ok"]:
        st.error(r["msg"])
        return
    verbo = "Compra" if r["lado"] == "Comprar" else "Venda"
    try:
        import fx_arte as FX
        st.markdown(FX.CSS + FX.html_recompensa(f"{verbo} executada!", [{"sprite": "ts", "valor": moeda(r["total"]), "rotulo": A.rotulo(r["tk"])}],
                                                 f"{A.texto_qtd(r['tk'], r['qtd'])} un. a {moeda(r['px'])} ({r['fonte']})", "comum", animar=FX.animar_padrao(st.session_state)),
                    unsafe_allow_html=True)
    except Exception:
        st.success(f"{verbo} executada: {A.texto_qtd(r['tk'], r['qtd'])} × {A.rotulo(r['tk'])} a {moeda(r['px'])} ({r['fonte']}).")


def _fechar_ordem() -> None:
    st.session_state.pop("comp_conf", None)
    st.rerun()


def _dialogo_ordem(a, perfil: dict, est: dict) -> None:
    """Pop-up pequeno de confirmação da ordem (mesmo padrão do pop-up de compra da Loja). Confirmar executa; Cancelar fecha."""
    import arte_tickerhunters as AT
    import tickercoins_app as TCA
    cf = st.session_state.get("comp_conf")
    if not cf:
        st.rerun()
        return
    tk, lado, qtd = cf["tk"], cf["lado"], cf["qtd"]
    cls = A.CLASSES[A.classe(tk)]
    caixa = float(est.get("caixa", 0))
    depois = caixa - cf["custo"] if lado == "Comprar" else caixa + cf["custo"]
    rot = "Custo estimado" if lado == "Comprar" else "Receita estimada"
    st.markdown(TCA.CSS_COMPRA + CSS_NEG, unsafe_allow_html=True)
    st.markdown(f"<div class='cp-box'><div class='cp-top'>{AT.img(AT.pose('pensativo'), 84)}"
                f"<div class='ng-ic' style='--c:{html.escape(cls['cor'])}'>{html.escape(cls['icone'])}</div></div>"
                f"<div class='cp-n'>{html.escape(A.rotulo(tk))}</div><span class='ng-tag {'v' if lado == 'Vender' else 'c'}'>{html.escape(lado)}</span>"
                f"<div class='cp-r'><span>Quantidade</span><b>{html.escape(A.texto_qtd(tk, qtd))} un.</b></div>"
                f"<div class='cp-r'><span>Preço</span><b>{html.escape(moeda(cf['ref']))}</b></div>"
                f"<div class='cp-r'><span>{rot}</span><b>{html.escape(moeda(cf['custo']))}</b></div>"
                f"<div class='cp-r fim'><span>Caixa depois</span><b>{html.escape(moeda(depois))}</b></div></div>"
                "<div class='ng-aviso'>Executa na hora, à cotação do instante do envio; o valor final pode diferir um pouco da estimativa.</div>", unsafe_allow_html=True)
    if st.button("Confirmar ordem", key="tc_ok_ordem", type="primary", width="stretch"):
        st.session_state["comp_res"] = _executar_ordem(a, perfil, cf)
        st.session_state.pop("comp_conf", None)
        st.rerun()
    if st.button("Cancelar", key="tc_no_ordem", width="stretch"):
        _fechar_ordem()


_dialogo_ordem = (getattr(st, "dialog", None) or (lambda *a, **k: (lambda f: f)))("Confirmar ordem", width="small")(_dialogo_ordem)


def _abrir_dialogo_ordem(a, perfil: dict, est: dict) -> None:
    cf = st.session_state.get("comp_conf")
    if cf and cf.get("abrir"):
        cf["abrir"] = False                   # abre uma vez; se a pessoa fechar no X, não reabre sozinho
        _dialogo_ordem(a, perfil, est)


CSS_NEG = ("<style>html body .stApp.stApp .ng-sec{font-weight:800;color:#CFC8EE;font-size:.82rem;letter-spacing:.04em;text-transform:uppercase;margin:14px 2px 4px}"
           "html body .stApp.stApp [class*=\"st-key-comp_max\"] button{border-radius:999px !important;min-height:42px !important;width:auto !important;padding:0 18px !important;"
           "background:rgba(242,184,75,.12) !important;border:1.5px solid rgba(242,184,75,.6) !important}"
           "html body .stApp.stApp [class*=\"st-key-comp_max\"] button :is(p,span){color:#FFD66B !important;-webkit-text-fill-color:#FFD66B !important;font-weight:800 !important}"
           "html body [data-testid=\"stDialog\"] [role=\"dialog\"] .ng-ic{flex:0 0 84px;width:84px;height:84px;border-radius:22px;display:grid;place-items:center;font-size:2.6rem;"
           "background:radial-gradient(circle at 30% 20%,color-mix(in srgb,var(--c) 55%,#fff),var(--c) 70%);box-shadow:0 6px 0 color-mix(in srgb,var(--c) 45%,#0B0821),0 8px 18px rgba(0,0,0,.45)}"
           "html body [data-testid=\"stDialog\"] [role=\"dialog\"] .ng-tag{display:inline-block;border-radius:999px;padding:2px 12px;font-size:.78rem;font-weight:900;margin-bottom:2px}"
           "html body [data-testid=\"stDialog\"] [role=\"dialog\"] .ng-tag.c{background:rgba(61,220,151,.18);color:#3DDC97 !important;-webkit-text-fill-color:#3DDC97 !important;border:1px solid #3DDC97}"
           "html body [data-testid=\"stDialog\"] [role=\"dialog\"] .ng-tag.v{background:rgba(255,107,138,.18);color:#FF6B8A !important;-webkit-text-fill-color:#FF6B8A !important;border:1px solid #FF6B8A}"
           "html body [data-testid=\"stDialog\"] [role=\"dialog\"] .ng-aviso{color:#B7AEE0 !important;-webkit-text-fill-color:#B7AEE0 !important;font-size:.74rem;text-align:center;margin:2px 6px 0}</style>")


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
- **Privacidade:** o ranking mostra só apelido e retorno %. Valores em reais, posições e ordens são só seus. Você pode trocar o apelido a qualquer momento.
- Contas suspensas e apelidos ofensivos ou repetidos saem do ranking.
- **Ranking ajustado ao risco:** além do retorno, dá para ordenar pelo **Sharpe** (retorno por unidade de risco), com {C.MIN_DIAS_RISCO} pregões ou mais. Evita premiar só quem apostou tudo num papel.
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


_GRUPOS_WG = [  # (grupo, ícone, seções); o grupo só aparece se a seção existir (Wallet Game nova exige resultado)
    ("Carteira", ":material/account_balance_wallet:", ["Meu patrimônio"]),
    ("Progresso", ":material/redeem:", ["Bônus e sequência", "Missões do jogo", "Conquistas"]),
    ("Negociar", ":material/swap_horiz:", ["Negociar"]),
    ("Ranking", ":material/leaderboard:", ["Classificação", "Ligas"]),
]
_COR_WG = ("#8B6CFF", "#3DDC97", "#F2B84B", "#FF6B8A", "#2BA7C9")


def _css_wg(ativo_idx: int, n_grupos: int, n_sub: int) -> str:
    q = "html body .stApp.stApp.stApp"
    n = f"{q} .st-key-wgnav"
    sb = f"{q} .st-key-wgsub"
    r = "".join(f"{q} .st-key-wg_g_{i}{{--ac:{c}}}" for i, c in enumerate(_COR_WG))
    ac = _COR_WG[ativo_idx % len(_COR_WG)]
    return (
        r + f"{sb}{{--ac:{ac}}}"
        # as linhas viram grade CSS (a regra global de 3+ colunas do app não alcança); cada botão é uma célula
        f"{n}[data-testid=\"stVerticalBlock\"],{n}>[data-testid=\"stVerticalBlock\"]{{display:grid !important;grid-template-columns:repeat({n_grupos},minmax(0,1fr)) !important;gap:8px !important}}"
        f"{sb}[data-testid=\"stVerticalBlock\"],{sb}>[data-testid=\"stVerticalBlock\"]{{display:grid !important;grid-template-columns:repeat({max(n_sub, 1)},minmax(0,1fr)) !important;gap:6px !important}}"
        f"{n},{sb}{{margin:0 0 6px}}"
        f"{n} button{{width:100% !important;min-height:62px !important;height:auto !important;border-radius:16px !important;padding:6px 3px !important;gap:3px !important;display:flex !important;flex-direction:column !important;align-items:center !important;justify-content:center !important;"
        "background:linear-gradient(160deg,color-mix(in srgb,var(--ac) 14%,var(--dz-cartao)),var(--dz-cartao) 75%) !important;"
        "border:1px solid color-mix(in srgb,var(--ac) 45%,transparent) !important;box-shadow:0 3px 0 color-mix(in srgb,var(--ac) 28%,#0B0821) !important;transition:transform .08s,box-shadow .08s}"
        f"{n} button:active{{transform:translateY(2px);box-shadow:0 1px 0 color-mix(in srgb,var(--ac) 28%,#0B0821) !important}}"
        f"{n} button>div,{n} button [data-testid=\"stMarkdownContainer\"]{{display:flex !important;flex-direction:column !important;align-items:center !important;justify-content:center !important;gap:3px !important;width:100% !important;margin:0 !important;padding:0 !important}}"
        f"{n} button [data-testid=\"stIconMaterial\"]{{flex:0 0 26px;width:26px !important;height:26px !important;border-radius:50%;display:grid !important;place-items:center;font-size:16px !important;color:#fff !important;margin:0 !important;"
        "background:radial-gradient(circle at 30% 18%,rgba(255,255,255,.45),transparent 52%),var(--ac);box-shadow:0 2px 0 color-mix(in srgb,var(--ac) 55%,#0B0821)}"
        f"{n} button :is(p,span):not([data-testid=\"stIconMaterial\"]){{font-size:.72rem !important;font-weight:800 !important;line-height:1.1 !important;color:var(--dz-texto) !important;text-align:center !important;white-space:nowrap !important}}"
        f"{n} button[data-testid^=\"stBaseButton-primary\"]{{border-color:var(--ac) !important;"
        "background:linear-gradient(160deg,color-mix(in srgb,var(--ac) 34%,var(--dz-cartao)),color-mix(in srgb,var(--ac) 12%,var(--dz-cartao)) 80%) !important;"
        "box-shadow:0 3px 0 color-mix(in srgb,var(--ac) 50%,#0B0821),0 0 0 2px color-mix(in srgb,var(--ac) 22%,transparent) !important}"
        f"{sb} button{{width:100% !important;min-height:36px !important;height:auto !important;border-radius:999px !important;padding:0 6px !important;justify-content:center !important;"
        "background:var(--dz-cartao) !important;border:1px solid color-mix(in srgb,var(--ac) 35%,transparent) !important;box-shadow:0 3px 0 rgba(0,0,0,.35) !important}"
        f"{sb} button :is(p,span){{font-size:.78rem !important;font-weight:800 !important;line-height:1.1 !important;color:var(--dz-texto) !important;text-align:center !important;white-space:nowrap !important}}"
        f"{sb} button[data-testid^=\"stBaseButton-primary\"]{{background:var(--ac) !important;border-color:var(--ac) !important;box-shadow:0 3px 0 color-mix(in srgb,var(--ac) 50%,#000) !important}}"
        f"{sb} button[data-testid^=\"stBaseButton-primary\"] :is(p,span){{color:#10091F !important}}"
    )


def _ir_secao(nome: str) -> None:
    st.session_state["wg_sec"] = nome


def _menu_wallet(nomes: list[str], so_sub: bool = False) -> str:
    """Botões internos da Wallet Game: grupos principais + sub-botões do grupo (sempre uma seção ativa)."""
    atual = st.session_state.get("wg_sec", nomes[0])
    grupos = [(g, ic, [x for x in sec if x in nomes]) for g, ic, sec in _GRUPOS_WG]
    grupos = [x for x in grupos if x[2]]
    idx = next((i for i, g in enumerate(grupos) if atual in g[2]), 0)
    ativo = grupos[idx]
    st.markdown(f"<style>{_css_wg(idx, len(grupos), len(ativo[2]) if len(ativo[2]) > 1 else 1)}</style>", unsafe_allow_html=True)
    if not so_sub:
        with st.container(key="wgnav"):
            for i, (g, ic, sec) in enumerate(grupos):
                st.button(g, key=f"wg_g_{i}", icon=ic, type="primary" if i == idx else "secondary",
                          on_click=_ir_secao, args=(sec[0],), width="stretch")
    if len(ativo[2]) > 1:
        with st.container(key="wgsub"):
            for j, nome in enumerate(ativo[2]):
                st.button(nome, key=f"wg_n_{j}_{idx}", type="primary" if nome == atual else "secondary",
                          on_click=_ir_secao, args=(nome,), width="stretch")
    return atual


def _cab() -> None:
    st.markdown(tema.cabecalho("💼", "Carteira",
                               "Monte uma carteira virtual com ações, FIIs, ETFs, cripto, fundos e renda fixa, aprenda a diversificar e dispute o ranking. Dinheiro de mentira, aprendizado de verdade."),
                unsafe_allow_html=True)


def pagina_competicao():
    _capturar_convite()
    a = usuarios.ator()
    if not a:
        _cab()
        st.info("Entre na sua conta para participar. Você pode ver o ranking sem entrar.")
        _aba_ranking({}, {})
        return
    if not banco.cfg_disponivel():
        _cab()
        st.warning("A Wallet Game precisa do banco de configuração do sistema, que ainda não está disponível. Fale com a administração.")
        return
    c = _pessoa(a)
    perfil, cart = c["perfil"], c["cart"]
    if not perfil.get("aceite"):
        _cab()
        if st.session_state.get("comp_convite"):
            st.info("Você recebeu um convite para uma liga de amigos. Entre na Wallet Game abaixo e aceite o convite na aba **Ligas**.")
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
    if st.session_state.get("comp_convite") and not L.participa(_ligas(a), st.session_state["comp_convite"]):
        st.info("Você tem um convite de liga esperando: abra a aba **Ligas**.")
    nomes = (["Meu patrimônio", "Bônus e sequência", "Missões do jogo", "Conquistas"] if res else []) + \
            ["Classificação", "Negociar", "Ligas"]
    if st.session_state.get("wg_sec") not in nomes:
        st.session_state["wg_sec"] = nomes[0]
    sec = st.session_state["wg_sec"]
    if not res:                                        # sem o jogo novo: cabeçalho e menu completos, como antes
        _cab()
        sec = _menu_wallet(nomes)
    elif sec not in ("Meu patrimônio", "Negociar"):    # a carteira é a tela principal: as outras áreas abrem com Voltar e abas próprias
        st.button("Voltar à carteira", key="wg_voltar", icon=":material/arrow_back:", on_click=_ir_secao, args=("Meu patrimônio",))
        st.markdown(ES.css_voltar("wg_voltar"), unsafe_allow_html=True)
        sec = _menu_wallet(nomes, so_sub=True)
    extra = None
    ordem = st.session_state.get("comp_res")
    if res and ordem and ordem.get("ok"):              # comprovante da ordem vai para o pop-up, junto com as comemorações
        st.session_state.pop("comp_res", None)
        extra = [_html_comprovante(ordem)]
    if res:                                            # cada seção mostra só o que é dela
        WGA.resumo(a, res, perfil.get("apelido") or "", hero=sec == "Classificação",
                   bonus_bloco=sec in ("Meu patrimônio", "Bônus e sequência"), extra=extra)
    with st.container():
        if sec == "Meu patrimônio":
            _aba_carteira(a, perfil, cart, res)
        elif sec == "Bônus e sequência":
            WGA.aba_bonus(a, res)
        elif sec == "Missões do jogo":
            WGA.aba_missoes(res)
        elif sec == "Conquistas":
            WGA.aba_conquistas(res, cart)
        elif sec == "Classificação":
            _aba_ranking(perfil, cart, res)
        elif sec == "Negociar":
            _aba_negociar(a, perfil, cart)
        elif sec == "Diversificar":
            DV.aba_diversificar(cart, C.novo_estado(perfil.get("entrada") or _agora().date().isoformat()))
        elif sec == "Ligas":
            _aba_ligas(a, perfil, cart)
    WGA.aviso()
