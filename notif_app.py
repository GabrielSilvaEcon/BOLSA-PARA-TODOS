"""Passo 23 — Página "Central de notificações": caixa de entrada, histórico, alertas, canais e painel do monitoramento.

Regras desta tela:
- Só a conta logada vê e altera as próprias notificações: a posse é conferida em banco.py (não aqui).
- As regras do monitor ficam em st.session_state["mon_regras"] e as preferências em ["notif_prefs"]; usuarios.salvar() grava as duas no
  perfil. É isso que o monitor automático (monitor.py) lê quando o app está fechado.
- Nada aqui compra, vende ou altera posições.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st

import banco
import canais
import conta_app as C
import monitor
import notif as N
import paleta as PL
import seguranca as seg
import tema
import usuarios

_PAGINAS: dict = {}
POR_PAGINA = 25
_COR = {"alta": PL.RUIM, "media": PL.OURO, "baixa": PL.INFO}

CSS = f"""<style>
.nt-c{{--c:{PL.INFO};background:linear-gradient(145deg,#1E1650,#160F36);border:1px solid #3D3182;border-left:5px solid var(--c);border-radius:16px;
  padding:12px 14px 10px;margin:10px 0 4px;color:#EDE9FF !important;}}
.nt-c.alta{{--c:{PL.RUIM};}} .nt-c.media{{--c:{PL.OURO};}} .nt-c.baixa{{--c:{PL.INFO};}}
.nt-c.lida{{opacity:.72;}} .nt-c.nova{{box-shadow:0 0 0 1px var(--c),0 10px 24px -12px var(--c);}}
.nt-t{{font-weight:800;font-size:1.02rem;color:#F6F3FF !important;line-height:1.35;word-break:break-word;}}
.nt-p{{display:inline-block;width:9px;height:9px;border-radius:50%;background:var(--c);margin-right:8px;vertical-align:middle;}}
.nt-c.lida .nt-p{{background:transparent;border:1px solid var(--c);}}
.nt-x{{margin-top:6px;color:#DCD6F5 !important;line-height:1.5;font-size:.93rem;word-break:break-word;}}
.nt-m{{margin-top:6px;}} .nt-c *, .nt-c .nt-x {{-webkit-text-fill-color:currentColor;}}
.nt-ex{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:8px;margin:4px 0 8px;}}
.nt-ex div{{background:#1A1342;border:1px solid #382C78;border-radius:12px;padding:9px 11px;color:#EDE9FF !important;font-size:.88rem;line-height:1.45;}}
.nt-ex b{{display:block;color:#C5B3FF !important;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px;}}
</style>"""


def registrar_paginas(paginas: dict) -> None:
    _PAGINAS.update({k: v for k, v in paginas.items() if v is not None})


# ------------------------------------------------------------------ utilidades
def _ator():
    return usuarios.ator()


def _ss():
    return st.session_state


def contagem_nao_lidas(forcar: bool = False) -> int:
    """Nº de não lidas (para o selo do menu). Guardado por 60 s na sessão para não consultar o banco a cada clique."""
    a = _ator()
    if not a:
        return 0
    c = _ss().get("_nt_cont")
    agora = datetime.now(timezone.utc).timestamp()
    if c and not forcar and agora - c[0] < 60:
        return c[1]
    try:
        n = banco.notif_contar(a, lida=False)
    except Exception:
        n = 0
    _ss()["_nt_cont"] = (agora, n)
    return n


def selo_texto() -> str:
    n = contagem_nao_lidas()
    return f" ({n if n < 100 else '99+'})" if n else ""


def _pesos_carteira() -> dict:
    """Peso de cada ativo pelo CUSTO registrado (sem consultar preços): serve só para explicar o aviso e priorizar."""
    tot, por = 0.0, {}
    for l in _ss().get("cart_real") or []:
        try:
            v = float(l["qtd"]) * float(l["preco_medio"])
            por[str(l["ticker"]).upper()] = por.get(str(l["ticker"]).upper(), 0.0) + v
            tot += v
        except (KeyError, TypeError, ValueError):
            continue
    return {k: v / tot * 100 for k, v in por.items()} if tot > 0 else {}


def prefs() -> dict:
    p = N.normalizar_prefs(_ss().get("notif_prefs"))
    _ss()["notif_prefs"] = p
    return p


def registrar_disparos(disparos: list[dict], origem: str) -> int:
    """Ponte dos motores que já existem (Inteligência, Notícias, Técnica, Risco): guarda os alertas que eles geram na Central, com
    deduplicação e respeitando as preferências. Nunca interrompe a página que chamou: qualquer falha é registrada e ignorada."""
    a = _ator()
    if not a or not disparos:
        return 0
    try:
        p, novas = prefs(), 0
        peso = _pesos_carteira()
        notifs = [N.de_disparo(d, origem) for d in disparos]
        notifs = [n for n in notifs if N.passa_prefs(n, p)]
        for n in notifs:
            n["importancia"], mot = N.pontuar(n, peso)
            if mot:
                n["dados"]["prioridade_motivo"] = mot
        notifs, _ = N.suprimir(notifs, [], p)
        if p["agrupar"]:
            notifs, _ = N.agrupar(notifs)
        for n in notifs:
            if banco.notif_inserir(a, n):
                novas += 1
        if novas:
            contagem_nao_lidas(True)
        return novas
    except Exception as e:
        banco.registrar_erro("notif_app.registrar", e)
        return 0


def _fmt(iso) -> str:
    return C._fmt(iso)


def _e(x) -> str:
    return html.escape(str(x if x is not None else ""))


# ------------------------------------------------------------------ ações (callbacks)
def _acao(fn, *args):
    try:
        fn(_ator(), *args)
    except Exception as e:
        banco.registrar_erro("notif_app.acao", e)
        st.toast("Não consegui concluir agora. Tente de novo.", icon="⚠️")
    contagem_nao_lidas(True)


def _marcar_todas(ids, lida=True):
    _acao(banco.notif_marcar, ids, lida)


# ------------------------------------------------------------------ cartão de notificação
def _cartao(n: dict, sufixo: str, pesos: dict) -> None:
    cls = f"nt-c {n['importancia']} {'lida' if n['lida'] else 'nova'}"
    chips = (C._chip(N.CATEGORIAS.get(n["categoria"], n["categoria"]), "") + (C._chip(n["ativo"], "ok") if n["ativo"] else "")
             + C._chip("Importância " + N.ROTULO_IMPORT.get(n["importancia"], "").lower(), {"alta": "erro", "media": "aviso"}.get(n["importancia"], "na"))
             + C._chip(_fmt(n["quando"]), "na") + (C._chip("Não lida", "aviso") if not n["lida"] else ""))
    ent = (n["dados"] or {}).get("entregas") or {}
    for c, r in ent.items():
        chips += C._chip(f"{N.CANAIS.get(c, c)}: {'enviado' if r.get('ok') else 'falhou'}", "ok" if r.get("ok") else "erro")
    st.markdown(f"<div class='{cls}'><div class='nt-t'><span class='nt-p'></span>{_e(n['titulo'])}</div><div class='nt-m'>{chips}</div>"
                f"<div class='nt-x'>{_e(n['texto'])}</div></div>", unsafe_allow_html=True)
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1.4])
    id_ = n["id"]
    if n["arquivada"]:
        c1.button("Restaurar", key=f"nt_rest_{sufixo}_{id_}", icon=":material/unarchive:", on_click=_acao, args=(banco.notif_arquivar, [id_], False), width="stretch")
    else:
        c1.button("Marcar não lida" if n["lida"] else "Marcar lida", key=f"nt_lida_{sufixo}_{id_}", icon=":material/mark_email_read:",
                  on_click=_acao, args=(banco.notif_marcar, [id_], not n["lida"]), width="stretch")
        c2.button("Arquivar", key=f"nt_arq_{sufixo}_{id_}", icon=":material/archive:", on_click=_acao, args=(banco.notif_arquivar, [id_], True), width="stretch")
    c3.button("Excluir", key=f"nt_del_{sufixo}_{id_}", icon=":material/delete:", on_click=_acao, args=(banco.notif_excluir, [id_]), width="stretch")
    pg = _PAGINAS.get(n.get("pagina") or "")
    if pg is not None:
        try:
            c4.page_link(pg, label="Abrir análise", icon=":material/open_in_new:")
        except Exception:
            pass
    import experiencia as _EX
    _ef = _EX.efetivo(st.session_state.get("prefs"))
    with st.expander("Por que isso importa", icon=":material/psychology:", expanded=bool(_ef["explicar_alertas"] and not n["lida"])):
        if _ef["explicar_alertas"] and _ef["modo"] == "iniciante":
            st.caption("Em palavras simples: este aviso mostra algo que mudou em um ativo seu. Não é ordem de compra ou venda.")
        ex = N.explicar(n, pesos or None, "(pelo custo registrado)")
        blocos = [("Fato", ex["fato"] + (f" Fonte: {ex['fonte']}." if ex["fonte"] else "")), ("Interpretação do app", ex["interpretacao"])]
        if ex["carteira"]:
            blocos.append(("Na sua carteira", ex["carteira"]))
        if ex["consequencias"]:
            blocos.append(("Possíveis consequências", ex["consequencias"]))
        if (n["dados"] or {}).get("prioridade_motivo"):
            blocos.append(("Prioridade", n["dados"]["prioridade_motivo"]))
        blocos.append(("Incertezas e limites", ex["incerteza"]))
        if _ef["alertas_tecnicos"]:
            blocos.append(("Detalhes técnicos", f"id {n['id']} · categoria {n['categoria']} · importância {n['importancia']} · regra {(n['dados'] or {}).get('regra', 'n/d')}"))
        st.markdown("<div class='nt-ex'>" + "".join(f"<div><b>{_e(t)}</b>{_e(v)}</div>" for t, v in blocos) + "</div>", unsafe_allow_html=True)
        for it in (n["dados"] or {}).get("itens") or []:
            st.markdown(C._linha(it.get("titulo", ""), it.get("texto", "")), unsafe_allow_html=True)
        if (n["dados"] or {}).get("url"):
            st.link_button("Abrir fonte", n["dados"]["url"], icon=":material/link:")


# ------------------------------------------------------------------ abas
def _filtros(prefixo: str, ativos: list[str], com_estado: bool):
    c1, c2, c3, c4 = st.columns(4)
    cat = c1.selectbox("Categoria", ["todas"] + list(N.CATEGORIAS), format_func=lambda x: "Todas" if x == "todas" else N.CATEGORIAS[x], key=f"{prefixo}_cat")
    imp = c2.selectbox("Importância", ["todas"] + list(N.IMPORTANCIAS), format_func=lambda x: "Todas" if x == "todas" else N.ROTULO_IMPORT[x], key=f"{prefixo}_imp")
    ativo = c3.selectbox("Ativo", ["todos"] + ativos, format_func=lambda x: "Todos" if x == "todos" else x, key=f"{prefixo}_ativo")
    est = c4.selectbox("Mostrar", ["nao_lidas", "todas", "lidas"], format_func={"nao_lidas": "Não lidas", "todas": "Todas", "lidas": "Lidas"}.get,
                       key=f"{prefixo}_est") if com_estado else "todas"
    return (cat if cat != "todas" else None, imp if imp != "todas" else None, ativo if ativo != "todos" else None,
            {"nao_lidas": False, "lidas": True, "todas": None}[est])


def _aba_caixa(a) -> None:
    pesos = _pesos_carteira()
    try:
        nao = banco.notif_contar(a, lida=False)
        todas = banco.notif_listar(a, None, False, limite=500)
        arq = banco.notif_contar(a, lida=None, arquivada=True)
    except Exception as e:
        banco.registrar_erro("notif_app.caixa", e)
        st.markdown(C._msg("Não consegui carregar as notificações agora. Tente recarregar a página.", "erro"), unsafe_allow_html=True)
        return
    hoje = N.hora_local(seg.agora()).date()
    altas = sum(1 for n in todas if not n["lida"] and n["importancia"] == "alta")
    st.markdown(C._grade([C._kpi("Não lidas", nao, "aviso" if nao else "ok", "esperando você"), C._kpi("Importância alta", altas, "erro" if altas else "na", "não lidas"),
                          C._kpi("Hoje", sum(1 for n in todas if (d := seg.de_iso(n["quando"])) and N.hora_local(d).date() == hoje), "info", "horário de Brasília"), C._kpi("Arquivadas", arq, "na", "no histórico")]),
                unsafe_allow_html=True)
    cat, imp, ativo, lida = _filtros("nt_f", sorted({n["ativo"] for n in todas if n["ativo"]}), True)
    lista = [n for n in todas if (cat is None or n["categoria"] == cat) and (imp is None or n["importancia"] == imp)
             and (ativo is None or n["ativo"] == ativo) and (lida is None or n["lida"] == lida)]
    b1, b2, _ = st.columns([1.3, 1.3, 2])
    b1.button("Marcar tudo como lido", icon=":material/done_all:", key="nt_todas", disabled=not any(not n["lida"] for n in lista),
              on_click=_marcar_todas, args=([n["id"] for n in lista if not n["lida"]],), width="stretch")
    b2.button("Arquivar lidas", icon=":material/archive:", key="nt_arq_lidas", disabled=not any(n["lida"] for n in lista),
              on_click=_acao, args=(banco.notif_arquivar, [n["id"] for n in lista if n["lida"]], True), width="stretch")
    if not lista:
        st.markdown(C._msg("Nenhuma notificação com esses filtros. Crie alertas na aba **Meus alertas**; os avisos aparecem aqui quando acontecerem.", "info"),
                    unsafe_allow_html=True)
        return
    lim = _ss().get("_nt_lim", POR_PAGINA)
    for n in lista[:lim]:
        _cartao(n, "cx", pesos)
    if len(lista) > lim:
        st.button(f"Mostrar mais ({len(lista) - lim})", key="nt_mais", on_click=lambda: _ss().__setitem__("_nt_lim", lim + POR_PAGINA))


def _aba_historico(a) -> None:
    pesos = _pesos_carteira()
    ver = st.radio("Histórico de", ["Arquivadas", "Tudo que já chegou"], horizontal=True, key="nt_h_ver")
    try:
        lista = banco.notif_listar(a, None, True, limite=500) if ver == "Arquivadas" else \
            sorted(banco.notif_listar(a, None, False, limite=500) + banco.notif_listar(a, None, True, limite=500), key=lambda n: n["quando"], reverse=True)
    except Exception as e:
        banco.registrar_erro("notif_app.hist", e)
        st.markdown(C._msg("Não consegui carregar o histórico agora.", "erro"), unsafe_allow_html=True)
        return
    cat, imp, ativo, _ = _filtros("nt_h", sorted({n["ativo"] for n in lista if n["ativo"]}), False)
    lista = [n for n in lista if (cat is None or n["categoria"] == cat) and (imp is None or n["importancia"] == imp) and (ativo is None or n["ativo"] == ativo)]
    st.caption(f"{len(lista)} notificação(ões). O histórico é guardado por {banco.RETENCAO_NOTIF_DIAS} dias e depois apagado sozinho.")
    if ver == "Arquivadas" and lista:
        c1, c2 = st.columns([2, 1])
        ok = c1.checkbox("Confirmo que quero apagar TODAS as arquivadas", key="nt_h_conf")
        c2.button("Apagar arquivadas", icon=":material/delete_forever:", key="nt_h_apagar", disabled=not ok,
                  on_click=_acao, args=(banco.notif_excluir, [n["id"] for n in lista]), width="stretch")
    if not lista:
        st.markdown(C._msg("Nada por aqui ainda.", "info"), unsafe_allow_html=True)
    for n in lista[:POR_PAGINA * 2]:
        _cartao(n, "hist", pesos)


# ---- alertas
def _ativo_valido(ativo: str, classe: str) -> bool:
    a = (ativo or "").strip().upper()
    if not a:
        return False
    if classe == "cripto":
        return a.isalnum() and 2 <= len(a) <= 10
    return seg.validar_ticker(a) is not None


def _aba_alertas() -> None:
    regras = _ss().get("mon_regras") or []
    st.markdown(C._titulo("Criar alerta", "Escolha a classe: só aparecem os alertas que fazem sentido para ela."), unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    classe = c1.selectbox("Classe do ativo", list(N.CLASSES), format_func=N.CLASSES.get, key="nt_a_classe")
    tipos = N.tipos_para_classe(classe)
    if not tipos:
        st.markdown(C._msg(N.ALTERNATIVAS.get(classe, "Sem alertas de mercado para esta classe."), "aviso"), unsafe_allow_html=True)
    else:
        tipo = c2.selectbox("Tipo de alerta", list(tipos), format_func=tipos.get, key="nt_a_tipo")
        with st.form("nt_a_form", clear_on_submit=False):
            ativo = st.text_input("Ativo", placeholder="BTC" if classe == "cripto" else "PETR4, HGLG11, IVVB11", key="nt_a_ativo")
            p: dict = {}
            if tipo in ("preco_acima", "preco_abaixo"):
                p["nivel"] = st.number_input("Valor do preço", min_value=0.0, value=0.0, step=0.01, format="%.4f", key="nt_a_nivel")
            elif tipo in ("alta_pct", "queda_pct"):
                x1, x2 = st.columns(2)
                p["limite_pct"] = x1.number_input("Variação mínima (%)", min_value=0.1, value=5.0, step=0.5, key="nt_a_lim")
                p["janela"] = x2.selectbox("Em quanto tempo", ["1d", "5d", "30d"], format_func={"1d": "1 pregão", "5d": "5 pregões", "30d": "1 mês"}.get, key="nt_a_jan")
            elif tipo == "extremo":
                x1, x2 = st.columns(2)
                p["sentido"] = x1.selectbox("Aviso de", ["max", "min"], format_func={"max": "Máxima", "min": "Mínima"}.get, key="nt_a_sent")
                p["periodo"] = x2.selectbox("Período", ["52s", "6m", "3m"], format_func={"52s": "52 semanas", "6m": "6 meses", "3m": "3 meses"}.get, key="nt_a_per")
            elif tipo == "variacao_incomum":
                p["desvios"] = st.number_input("Quantos desvios-padrão (3 = bem raro)", min_value=2.0, max_value=10.0, value=3.0, step=0.5, key="nt_a_desv")
            elif tipo == "fund_mudanca":
                x1, x2 = st.columns(2)
                ind = N.INDICADORES.get(classe, {})
                p["campo"] = x1.selectbox("Indicador", list(ind), format_func=ind.get, key="nt_a_campo")
                p["limite_pct"] = x2.number_input("Mudança mínima (%)", min_value=1.0, value=15.0, step=1.0, key="nt_a_lim2")
            imp = st.selectbox("Importância", list(N.IMPORTANCIAS), index=1, format_func=N.ROTULO_IMPORT.get, key="nt_a_imp")
            ok = C._enviar("Criar alerta", type="primary")
        if ok:
            try:
                if not _ativo_valido(ativo, classe):
                    raise ValueError("Esse código de ativo não parece válido.")
                r = N.nova_regra_mon(tipo, ativo, classe, p, imp)
                if any(x["id"] == r["id"] for x in regras):
                    raise ValueError("Você já tem exatamente esse alerta.")
                if len(regras) >= 60:
                    raise ValueError("Limite de 60 alertas atingido. Apague algum para criar outro.")
                import planos                                   # Etapa 5: limite de alertas do plano
                pode_mais, msg_plano = planos.permitido_max("alertas_max", len([x for x in regras if x.get("ativa", True)]))
                if not pode_mais:
                    raise ValueError(msg_plano)
                _ss()["mon_regras"] = regras + [r]
                st.markdown(C._msg("Alerta criado. Ele passa a ser verificado pelo monitor automático (se estiver ativo) e quando você tocar em Verificar agora.", "ok"), unsafe_allow_html=True)
                regras = _ss()["mon_regras"]
            except ValueError as e:
                st.markdown(C._msg(str(e), "erro"), unsafe_allow_html=True)
    st.markdown(C._titulo(f"Seus alertas de mercado ({len(regras)})", "Avisam quando a condição passa de não atendida para atendida; depois só voltam se ela deixar de valer e valer de novo."), unsafe_allow_html=True)
    if not regras:
        st.markdown(C._msg("Você ainda não criou alertas de mercado.", "info"), unsafe_allow_html=True)
    for r in regras:
        a, b, c = st.columns([4, 1.2, 1.2], vertical_alignment="center")
        a.markdown(C._linha(f"{r['ativo']} · {N.descrever_regra_mon(r)}", f"{N.CLASSES.get(r['classe'], '')} · importância {N.ROTULO_IMPORT[r['importancia']].lower()}",
                            C._chip("ativo" if r.get("ativa", True) else "pausado", "ok" if r.get("ativa", True) else "na")), unsafe_allow_html=True)
        b.button("Pausar" if r.get("ativa", True) else "Ativar", key=f"nt_r_pa_{r['id']}", width="stretch",
                 on_click=lambda i=r["id"]: _ss().__setitem__("mon_regras", [dict(x, ativa=not x.get("ativa", True)) if x["id"] == i else x for x in _ss().get("mon_regras") or []]))
        c.button("Remover", key=f"nt_r_rm_{r['id']}", width="stretch", icon=":material/delete:",
                 on_click=lambda i=r["id"]: _ss().__setitem__("mon_regras", [x for x in _ss().get("mon_regras") or [] if x["id"] != i]))
    st.markdown(C._titulo("Outros alertas que você já criou", "Continuam funcionando nas páginas deles; os que o monitor consegue avaliar com o app fechado estão indicados."), unsafe_allow_html=True)
    itens = [("intel_regras", "Central de inteligência", "inteligencia", "preço, volatilidade, liquidez e carteira são avaliados pelo monitor"),
             ("tec_av_regras", "Análise técnica avançada", "tecnica-avancada", "avaliados pelo monitor (RSI, médias, MACD, rompimentos, volume, tendência)"),
             ("ne_regras", "Notícias e eventos", "noticias", "avaliados quando você atualiza a página (dependem de leitura de notícias)"),
             ("risco_regras", "Gestão de risco", "risco", "avaliados quando você atualiza a página; os limites de carteira também entram no monitor")]
    for chave, nome, pag, nota in itens:
        n = len(_ss().get(chave) or [])
        pg = _PAGINAS.get(pag)
        x, y = st.columns([4, 1.4], vertical_alignment="center")
        x.markdown(C._linha(f"{nome}: {n} alerta(s)", nota), unsafe_allow_html=True)
        if pg is not None:
            y.page_link(pg, label="Gerenciar", icon=":material/open_in_new:")


# ---- preferências e canais
def _teste(canal: str, destino: str, nome: str) -> None:
    r = canais.enviar_com_retentativa(canal, destino, "[Bússola B3] Teste de notificação",
                                      f"Olá, {nome}! Este é um teste real do canal {N.CANAIS[canal]}. Se você recebeu, o canal está funcionando.", "baixa", tentativas=2)
    _ss()["_nt_teste"] = (canal, r)


def _aba_prefs(u: dict) -> None:
    p = prefs()
    disp = canais.disponiveis()
    st.markdown(C._titulo("Canais de entrega", "O aviso no app sempre existe. Os outros só enviam se estiverem configurados e se você ligar."), unsafe_allow_html=True)
    st.markdown(C._grade([C._kpi(N.CANAIS[c], "Pronto" if ok else "Indisponível", "ok" if ok else "na", txt) for c, (ok, txt) in disp.items()]), unsafe_allow_html=True)
    teste = _ss().pop("_nt_teste", None)
    if teste:
        c, r = teste
        st.markdown(C._msg(f"Teste de {N.CANAIS[c]}: " + ("enviado de verdade (confira o aparelho/caixa de entrada)." if r["ok"] else f"não foi enviado. {r['detalhe']}"),
                           "ok" if r["ok"] else "erro"), unsafe_allow_html=True)
    # Telegram: vínculo
    if disp["telegram"][0]:
        with st.expander("Vincular o Telegram", icon=":material/send:", expanded=not p["telegram_chat"]):
            if p["telegram_chat"]:
                st.markdown(C._msg("Telegram vinculado.", "ok"), unsafe_allow_html=True)
            cod = _ss().get("_nt_tg")
            bot = canais.telegram_bot().get("usuario", "o bot do app")
            if not cod:
                st.button("Gerar código", key="nt_tg_gerar", on_click=lambda: _ss().__setitem__("_nt_tg", canais.novo_codigo_vinculo()))
            else:
                st.markdown(C._msg(f"Abra o Telegram, procure {bot} e envie exatamente este código: {cod}. Depois toque em Verificar.", "info"), unsafe_allow_html=True)
                if st.button("Verificar vínculo", key="nt_tg_ver"):
                    chat, msg = canais.telegram_vincular(cod)
                    if chat:
                        _ss()["notif_prefs"] = N.normalizar_prefs({**p, "telegram_chat": chat, "canais": {**p["canais"], "telegram": True}})
                        _ss().pop("_nt_tg", None)
                        st.rerun()
                    st.markdown(C._msg(msg, "aviso"), unsafe_allow_html=True)
    # ntfy: tópico secreto
    with st.expander("Push no celular (ntfy)", icon=":material/phone_iphone:", expanded=False):
        if not p["ntfy_topico"]:
            st.markdown(C._msg("Gere seu tópico secreto, instale o app gratuito ntfy (Android ou iPhone), toque em + e digite o tópico. Guarde-o como uma senha.", "info"), unsafe_allow_html=True)
            st.button("Gerar tópico secreto", key="nt_ntfy_gerar",
                      on_click=lambda: _ss().__setitem__("notif_prefs", N.normalizar_prefs({**p, "ntfy_topico": N.novo_topico_ntfy(), "canais": {**p["canais"], "ntfy": True}})))
        else:
            st.markdown(C._msg("No app ntfy, assine este tópico (servidor " + canais._servidor_ntfy().removeprefix("https://") + "):", "info"), unsafe_allow_html=True)
            st.code(p["ntfy_topico"], language=None)
            st.button("Trocar tópico (invalida o anterior)", key="nt_ntfy_novo",
                      on_click=lambda: _ss().__setitem__("notif_prefs", N.normalizar_prefs({**p, "ntfy_topico": N.novo_topico_ntfy()})))
    with st.form("nt_prefs"):
        st.markdown(C._titulo("Quando e o que receber"), unsafe_allow_html=True)
        g1, g2 = st.columns(2)
        ativo = g1.checkbox("Receber notificações", value=p["ativo"])
        agr = g2.checkbox("Agrupar avisos relacionados", value=p["agrupar"], help="Vários avisos do mesmo ativo e categoria viram um só.")
        m1, m2 = st.columns(2)
        imin = m1.selectbox("Importância mínima (no app)", list(N.IMPORTANCIAS)[::-1], index=list(N.IMPORTANCIAS)[::-1].index(p["importancia_min"]), format_func=N.ROTULO_IMPORT.get)
        iext = m2.selectbox("Importância mínima (e-mail, Telegram, push)", list(N.IMPORTANCIAS)[::-1], index=list(N.IMPORTANCIAS)[::-1].index(p["importancia_min_externo"]), format_func=N.ROTULO_IMPORT.get)
        off = st.multiselect("Desativar categorias", [c for c in N.CATEGORIAS if c != "sistema"], default=p["categorias_off"], format_func=N.CATEGORIAS.get)
        st.markdown(C._titulo("Alertas do cenário econômico", "Avisam quando a economia muda de um jeito relevante para os ativos da sua carteira real. Nunca usam ativos pesquisados, exemplos ou a carteira fictícia."), unsafe_allow_html=True)
        pm = p["macro"]
        q1, q2, q3 = st.columns(3)
        mm_mud = q1.checkbox("Mudança de cenário", value=pm["mudanca"], help="O cenário de um setor seu passou de neutro para bom ou ruim, ou de bom para ruim (e o contrário).")
        mm_int = q2.checkbox("Piora ou melhora forte", value=pm["intensidade"], help="O cenário não mudou de classificação, mas a nota se moveu muito desde o último aviso.")
        mm_ris = q3.checkbox("Novo risco econômico forte", value=pm["risco"], help="Um fator da economia passou a pesar forte contra um ativo seu. Não repete o mesmo risco em menos de 14 dias.")
        q4, q5 = st.columns(2)
        mm_neu = q4.checkbox("Avisar também quando voltar a neutro", value=pm["neutro"])
        mm_ruim = q5.checkbox("Só avisar quando for desfavorável", value=pm["somente_ruim"])
        st.markdown(C._titulo("Canais externos"), unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)
        ce = k1.checkbox("E-mail", value=p["canais"]["email"], disabled=not disp["email"][0])
        ct = k2.checkbox("Telegram", value=p["canais"]["telegram"], disabled=not (disp["telegram"][0] and p["telegram_chat"]))
        cn = k3.checkbox("Push (ntfy)", value=p["canais"]["ntfy"], disabled=not p["ntfy_topico"])
        st.markdown(C._titulo("Horários permitidos", "Vale para os canais externos (o aviso no app sempre entra). Horário de Brasília."), unsafe_allow_html=True)
        h1, h2, h3 = st.columns([1, 1, 2])
        ini = h1.text_input("Início (HH:MM)", value=p["horario"]["inicio"])
        fim = h2.text_input("Fim (HH:MM)", value=p["horario"]["fim"])
        dias = h3.multiselect("Dias", list(range(7)), default=p["horario"]["dias"], format_func=lambda d: ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"][d])
        st.markdown(C._titulo("Frequência e limites"), unsafe_allow_html=True)
        f1, f2, f3 = st.columns(3)
        try:
            import planos
            _min_plano = planos.intervalo_minimo(*(lambda c: (c["email"], c["papel"]) if c else (None, None))(st.session_state.get("_conta")))
            if _min_plano > 15:
                st.caption(f"Seu plano verifica no mínimo a cada {_min_plano} min, mesmo que você escolha um intervalo menor.")
        except Exception:
            pass
        ver = f1.selectbox("Verificar a cada", list(N.FREQUENCIAS_MIN), index=list(N.FREQUENCIAS_MIN).index(p["verificar_a_cada_min"]), format_func=N.FREQUENCIAS_MIN.get)
        gap = f2.number_input("Intervalo mínimo entre avisos parecidos (horas)", min_value=0, max_value=168, value=p["intervalo_min_h"])
        mx = f3.number_input("Máximo de avisos externos por dia", min_value=1, max_value=50, value=p["max_externas_dia"])
        st.markdown(C._titulo("Alocação-alvo (opcional)", "Para o aviso de rebalanceamento. Deixe 0 para não usar."), unsafe_allow_html=True)
        cols = st.columns(len(N.CLASSES))
        alvo = {cl: cols[i].number_input(N.CLASSES[cl], min_value=0.0, max_value=100.0, value=float(p["alvo_classes"].get(cl, 0.0)), step=5.0, key=f"nt_alvo_{cl}") for i, cl in enumerate(N.CLASSES)}
        salvar = C._enviar("Salvar preferências", type="primary")
    if salvar:
        novas = N.normalizar_prefs({**p, "ativo": ativo, "agrupar": agr, "importancia_min": imin, "importancia_min_externo": iext, "categorias_off": off,
                                    "canais": {"app": True, "email": ce, "telegram": ct, "ntfy": cn}, "horario": {"inicio": ini.strip(), "fim": fim.strip(), "dias": dias},
                                    "verificar_a_cada_min": ver, "intervalo_min_h": gap, "max_externas_dia": mx, "alvo_classes": {k: v for k, v in alvo.items() if v > 0},
                                    "macro": {"ativo": True, "mudanca": mm_mud, "intensidade": mm_int, "risco": mm_ris, "neutro": mm_neu, "somente_ruim": mm_ruim}})
        if sum(novas["alvo_classes"].values()) > 100.5:
            st.markdown(C._msg("A alocação-alvo passa de 100%. Ajuste os valores.", "erro"), unsafe_allow_html=True)
        else:
            _ss()["notif_prefs"] = novas
            st.markdown(C._msg("Preferências salvas." + (" Horário inválido foi trocado pelo padrão." if (ini.strip(), fim.strip()) != (novas["horario"]["inicio"], novas["horario"]["fim"]) else ""), "ok"), unsafe_allow_html=True)
    st.markdown(C._titulo("Enviar um teste real", "Só envia se o canal estiver pronto e com destino definido."), unsafe_allow_html=True)
    t1, t2, t3 = st.columns(3)
    t1.button("Testar e-mail", key="nt_t_em", disabled=not disp["email"][0], on_click=_teste, args=("email", u["email"], usuarios.primeiro_nome()), width="stretch")
    t2.button("Testar Telegram", key="nt_t_tg", disabled=not (disp["telegram"][0] and p["telegram_chat"]), on_click=_teste, args=("telegram", p["telegram_chat"], usuarios.primeiro_nome()), width="stretch")
    t3.button("Testar push", key="nt_t_nt", disabled=not p["ntfy_topico"], on_click=_teste, args=("ntfy", p["ntfy_topico"], usuarios.primeiro_nome()), width="stretch")


# ---- monitoramento
def _quando_relativo(iso) -> tuple[str, str]:
    d = seg.de_iso(iso)
    if not d:
        return "Nunca", "na"
    mins = int((seg.agora() - d).total_seconds() // 60)
    txt = f"há {mins} min" if mins < 120 else f"há {mins // 60} h" if mins < 2880 else f"há {mins // 1440} dias"
    return txt, "ok" if mins <= 45 else "aviso" if mins <= 360 else "erro"


def _aba_monitor(a) -> None:
    p = prefs()
    ult = banco.monitor_ultima(1)
    rel, cls = _quando_relativo(ult[0]["inicio"] if ult else None)
    st.markdown(C._grade([C._kpi("Última verificação automática", rel, cls, "do monitor fora do app" if ult else "o monitor ainda não rodou"),
                          C._kpi("Frequência escolhida", N.FREQUENCIAS_MIN[p["verificar_a_cada_min"]], "info", "por conta, no mínimo"),
                          C._kpi("Banco de dados", "Supabase" if banco.backend() == "supabase" else "Local (SQLite)", "ok" if banco.backend() == "supabase" else "aviso",
                                 "necessário para o monitor" if banco.backend() != "supabase" else "compartilhado com o monitor"),
                          C._kpi("Seus alertas", len(_ss().get("mon_regras") or []), "info", "de mercado")]), unsafe_allow_html=True)
    if banco.backend() != "supabase":
        st.markdown(C._msg("O monitor automático só funciona com o Supabase ligado: com o banco local não há onde o monitor e o app dividirem seus alertas.", "aviso"), unsafe_allow_html=True)
    elif not ult:
        st.markdown(C._msg("O monitor ainda não executou. Ele precisa ser ligado no GitHub (veja o passo a passo em NOTIFICACOES.md). Enquanto isso, use Verificar agora.", "aviso"), unsafe_allow_html=True)
    st.markdown(C._titulo("Verificar agora", "Roda a mesma checagem do monitor para a sua conta, usando esta sessão. Grava só no app (não envia e-mail/Telegram/push)."), unsafe_allow_html=True)
    if st.button("Verificar agora", key="nt_vagora", icon=":material/refresh:", type="primary"):
        with st.spinner("Consultando as fontes (até 25 ativos)..."):
            try:
                dados = {k: _ss().get(k) for k in ("mon_regras", "notif_prefs", "cart_real", "risco_limites", "intel_regras", "tec_av_regras")}
                r = monitor.verificar_agora(a, {k: v for k, v in dados.items() if v is not None})
                contagem_nao_lidas(True)
                if r.get("aviso"):
                    st.markdown(C._msg(r["aviso"], "aviso"), unsafe_allow_html=True)
                else:
                    st.markdown(C._msg(f"Verificados {r['lidos']} de {r['ativos']} ativos: {r['novas']} nova(s) notificação(ões), {r['suprimidas']} repetida(s) ignorada(s), {r['agrupadas']} agrupada(s).", "ok" if not r["erros"] else "aviso"), unsafe_allow_html=True)
                for e in r.get("erros", [])[:5]:
                    st.caption("Fonte indisponível: " + e)
            except Exception as e:
                banco.registrar_erro("notif_app.verificar", e)
                st.markdown(C._msg("A verificação falhou agora. Tente de novo em alguns minutos.", "erro"), unsafe_allow_html=True)
    st.markdown(C._titulo("Como o monitoramento automático funciona"), unsafe_allow_html=True)
    st.markdown(C._grade([
        C._kpi("Quem executa", "GitHub Actions", "info", "gratuito, fora do Streamlit; pode atrasar alguns minutos"),
        C._kpi("Proteções", "Sem duplicar", "ok", "trava por janela, retentativas, cache e limite de consultas por execução"),
        C._kpi("Cobre", "Preço, técnica, carteira", "info", "notícias e eventos só quando você atualiza a página"),
        C._kpi("Limite", "Dias úteis, 15 min", "aviso", "fim de semana: a cada 4 horas")]), unsafe_allow_html=True)
    st.markdown(C._msg("Isto não é um sistema de tempo real nem de execução de ordens: serve para avisar, e as decisões continuam sendo suas. Fontes gratuitas podem atrasar ou falhar.", "info"), unsafe_allow_html=True)


# ------------------------------------------------------------------ página
def pagina_notificacoes() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    C._css()
    st.markdown(tema.cabecalho("🔔", "Central de notificações", "Avisos dos seus ativos e da sua carteira, com histórico, filtros e canais."), unsafe_allow_html=True)
    u = usuarios.usuario()
    a = _ator()
    if not u or not a:
        st.markdown(C._msg("Entre na sua conta para criar alertas e receber notificações. Elas são individuais: só você vê as suas.", "aviso"), unsafe_allow_html=True)
        return
    if not banco.notif_disponivel():
        st.markdown(C._msg("As tabelas de notificações ainda não existem no banco. No Supabase, abra o SQL Editor e execute de novo o script "
                           "(Administração > Sistema > Script SQL). Ele é seguro de repetir.", "aviso"), unsafe_allow_html=True)
        return
    abas = st.tabs(["Caixa de entrada", "Histórico", "Meus alertas", "Preferências e canais", "Monitoramento"])
    with abas[0]:
        _aba_caixa(a)
    with abas[1]:
        _aba_historico(a)
    with abas[2]:
        _aba_alertas()
    with abas[3]:
        _aba_prefs(u)
    with abas[4]:
        _aba_monitor(a)
