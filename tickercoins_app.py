"""Telas do TickerCoins: Minha Carteira de Moedas, Central de Recompensas, Loja Ticker, faixa de acesso e seção do painel admin.
Toda regra e todo saldo ficam em tickercoins.py (servidor); aqui só se desenha e se chama. O cliente nunca envia quantidades."""
from __future__ import annotations

import html
import uuid

import streamlit as st

import banco
import planos
import tickercoins as TC
import usuarios

_PAGS: dict = {}
CSS = """<style>
html body .stApp.stApp .tc-saldo{background:linear-gradient(135deg,#3A2A75,#1E1747);border:1px solid #F2B84B55;border-radius:20px;padding:18px;text-align:center;margin:6px 0 12px;}
html body .stApp.stApp .tc-saldo .v{font-size:2.4rem;font-weight:900;color:#FFD66B;line-height:1.1;}
html body .stApp.stApp .tc-saldo .l{color:#CFC8EE;font-size:.85rem;margin-top:2px;}
html body .stApp.stApp .tc-chip{display:inline-flex;align-items:center;gap:6px;background:#2A2058;border:1px solid #F2B84B66;border-radius:999px;padding:4px 12px;color:#FFD66B;font-weight:800;font-size:.9rem;}
html body .stApp.stApp .tc-card{background:#241C4D;border:1px solid #3B3170;border-radius:16px;padding:12px 14px;margin:6px 0;}
html body .stApp.stApp .tc-card .t{font-weight:800;color:#F6F3FF;}
html body .stApp.stApp .tc-card .d{color:#CFC8EE;font-size:.85rem;margin-top:2px;}
html body .stApp.stApp .tc-card .m{color:#9C94C9;font-size:.78rem;margin-top:4px;}
html body .stApp.stApp .tc-pos{color:#3DDC97;font-weight:800;}
html body .stApp.stApp .tc-neg{color:#FF6B8A;font-weight:800;}
html body .stApp.stApp .tc-pre{border-style:dashed;opacity:.9;}
html body .stApp.stApp .tc-aviso{color:#9C94C9;font-size:.78rem;margin-top:10px;}
html body .stApp.stApp .st-key-tc_faixa [data-testid="stHorizontalBlock"]{flex-wrap:nowrap !important;gap:6px !important;align-items:center !important;}
html body .stApp.stApp .st-key-tc_faixa [data-testid="stColumn"]{min-width:0 !important;flex:1 1 0 !important;width:auto !important;}
html body .stApp.stApp .st-key-tc_faixa [data-testid="stColumn"]:first-child{flex:0 0 auto !important;}
html body .stApp.stApp .st-key-tc_faixa a{padding:6px 8px !important;min-height:0 !important;font-size:.8rem !important;justify-content:center;white-space:nowrap;}
html body .stApp.stApp .st-key-tc_faixa a p{font-size:.8rem !important;white-space:nowrap;}
</style>"""


def registrar_paginas(paginas: dict) -> None:
    _PAGS.update(paginas)


def _e(x) -> str:
    return html.escape(str(x))


def _conta() -> dict | None:
    return usuarios.usuario()


def _plano() -> str:
    c = _conta()
    return planos.plano_de(c["email"], c["papel"]) if c else "visitante"


def _fmt(iso) -> str:
    d = TC._de_iso(iso)
    return d.astimezone(TC.timezone(TC.timedelta(hours=-3))).strftime("%d/%m %H:%M") if d else ""


def _sinal(n: int) -> str:
    return f"+{n}" if n > 0 else str(n)


def saldo_atual() -> int | None:
    """Saldo da conta logada (None se visitante ou sem banco). Nunca levanta erro."""
    try:
        c = _conta()
        return TC.saldo(c["id"]) if c else None
    except Exception:
        return None


def faixa(atual: str) -> None:
    """Linha compacta: saldo + Carteira / Recompensas / Loja. `atual` = url_path da página onde está (não vira link para si mesma)."""
    if not _PAGS:
        return
    st.markdown(CSS, unsafe_allow_html=True)
    with st.container(key="tc_faixa"):
        s = saldo_atual()
        cols = st.columns([1.3, 1, 1, 1])
        cols[0].markdown(f"<span class='tc-chip'>🪙 {'—' if s is None else s} TC</span>", unsafe_allow_html=True)
        for col, (url, rot, ic) in zip(cols[1:], (("moedas", "Moedas", ":material/account_balance_wallet:"),
                                                  ("recompensas", "Prêmios", ":material/redeem:"),
                                                  ("loja", "Loja", ":material/storefront:"))):
            if url != atual and url in _PAGS:
                col.page_link(_PAGS[url], label=rot, icon=ic)


def _precisa_login() -> bool:
    if _conta():
        return False
    st.markdown("<div class='tc-card'><div class='t'>Entre na sua conta</div><div class='d'>Seu saldo de TickerCoins fica salvo na sua conta. "
                "Entre ou crie uma conta gratuita para ganhar e usar moedas.</div></div>", unsafe_allow_html=True)
    return True


def _banco_ok() -> bool:
    ok, motivo = TC.disponivel()
    if not ok:
        st.markdown(f"<div class='tc-card'><div class='t'>TickerCoins em preparação</div><div class='d'>{_e(motivo)}</div></div>", unsafe_allow_html=True)
    return ok


def _rodape() -> None:
    st.markdown(f"<div class='tc-aviso'>{_e(TC.AVISO)}</div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ Minha Carteira de Moedas
def _linha_hist(x: dict) -> str:
    d = int(x["delta"])
    pend = x["estado"] == "pendente"
    cor = "tc-pos" if d > 0 else "tc-neg" if d < 0 else ""
    val = "aguardando" if pend else _sinal(d)
    return (f"<div class='tc-card{' tc-pre' if pend else ''}'><div class='t'>{_e(x['descricao'] or x['origem'])} "
            f"<span class='{cor}' style='float:right'>{_e(val)} TC</span></div>"
            f"<div class='m'>{_e(_fmt(x['criado_em']))} · {_e(TC.ROTULO_ESTADO.get(x['estado'], x['estado']))} · saldo depois: {int(x['saldo_apos'])} TC</div></div>")


def pagina_carteira() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🪙 Minha carteira de moedas")
    faixa("moedas")
    if _precisa_login() or not _banco_ok():
        _rodape()
        return
    c = _conta()
    s, t = TC.saldo(c["id"]), TC.totais(c["id"])
    st.markdown(f"<div class='tc-saldo'><div class='v'>{s} TC</div><div class='l'>Saldo disponível de TickerCoins</div></div>", unsafe_allow_html=True)
    a, b = st.columns(2)
    a.markdown(f"<div class='tc-card'><div class='d'>Total recebido</div><div class='t tc-pos'>{t['recebido']} TC</div></div>", unsafe_allow_html=True)
    b.markdown(f"<div class='tc-card'><div class='d'>Total usado</div><div class='t'>{t['usado']} TC</div></div>", unsafe_allow_html=True)
    ativos = TC.beneficios_ativos(c["id"])
    if ativos:
        st.markdown("**Benefícios ativos**")
        for x in ativos:
            p = TC.produto(x["produto_id"]) or {}
            val = "Permanente" if not x.get("expira_em") else f"até {_fmt(x['expira_em'])}"
            st.markdown(f"<div class='tc-card'><div class='t'>{_e(p.get('nome', x['produto_id']))}</div><div class='m'>{_e(val)}</div></div>", unsafe_allow_html=True)
    st.markdown("**Histórico**")
    hist = TC.historico(c["id"], 60)
    if not hist:
        st.markdown("<div class='tc-card'><div class='d'>Nenhuma movimentação ainda. Conclua uma lição na Jornada para ganhar suas primeiras moedas.</div></div>", unsafe_allow_html=True)
    for x in hist:
        st.markdown(_linha_hist(x), unsafe_allow_html=True)
    _rodape()


# ------------------------------------------------------------------ Central de Recompensas
def pagina_recompensas() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🎁 Central de recompensas")
    faixa("recompensas")
    if _precisa_login() or not _banco_ok():
        _rodape()
        return
    c = _conta()
    cfg = TC.config()
    ganho, teto = TC.ganhos_hoje(c["id"]), int(cfg["limite_diario_ganhos"])
    mult, camp = TC._multiplicador(TC._agora())
    st.markdown(f"<div class='tc-card'><div class='t'>Hoje: {ganho} de {teto} TC por estudo</div>"
                f"<div class='d'>O limite diário renova à meia-noite (horário de Brasília).</div></div>", unsafe_allow_html=True)
    if camp:
        st.markdown(f"<div class='tc-card'><div class='t'>🎉 {_e(camp)}: recompensas x{mult}</div></div>", unsafe_allow_html=True)
    st.markdown("**Como ganhar moedas**")
    for k, r in cfg["recompensas"].items():
        if r.get("ativo") and int(r["valor"]) > 0:
            st.markdown(f"<div class='tc-card'><div class='t'>{_e(r['rotulo'])} <span class='tc-pos' style='float:right'>+{int(r['valor'])} TC</span></div></div>", unsafe_allow_html=True)
    st.markdown("<div class='tc-card'><div class='d'>As moedas de estudo entram sozinhas quando você conclui a atividade. O XP da Jornada continua separado.</div></div>", unsafe_allow_html=True)
    st.markdown("**Anúncios recompensados**")
    stt = TC.anuncios_status()
    a = cfg["anuncios"]
    if stt["disponivel"]:
        st.markdown(f"<div class='tc-card'><div class='t'>Assista e ganhe {int(a['valor'])} TC</div><div class='d'>Até {int(a['limite_dia'])} por dia, com {int(a['intervalo_min'])} min de intervalo.</div></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div class='tc-card tc-pre'><div class='t'>Indisponível por enquanto</div><div class='d'>{_e(stt['motivo'])}</div></div>", unsafe_allow_html=True)
    _rodape()


# ------------------------------------------------------------------ Loja Ticker
def _pedir(pid: str) -> None:
    st.session_state["tc_conf"] = {"pid": pid, "req": uuid.uuid4().hex}


def _cancelar() -> None:
    st.session_state.pop("tc_conf", None)


def _confirmar() -> None:
    cf = st.session_state.pop("tc_conf", None)
    c = _conta()
    if not cf or not c:
        return
    r = TC.comprar(c["id"], cf["pid"], cf["req"], _plano())
    TC.esquecer_cache(c["id"])
    st.session_state["tc_res"] = r


def _card_produto(p: dict, c: dict, s: int) -> None:
    ok, motivo = TC.pode_comprar(c["id"], p["id"], _plano())
    st.markdown(f"<div class='tc-card'><div class='t'>{_e(p['nome'])} <span class='tc-chip' style='float:right'>🪙 {p['preco']} TC</span></div>"
                f"<div class='d'>{_e(p['descricao'])}</div><div class='m'>Validade: {_e(TC.rotulo_validade(p['validade_h']))}</div></div>", unsafe_allow_html=True)
    cf = st.session_state.get("tc_conf")
    if cf and cf["pid"] == p["id"]:
        st.markdown(f"Confirmar a compra de **{_e(p['nome'])}** por **{p['preco']} TC**? Saldo depois: {s - p['preco']} TC.")
        x, y = st.columns(2)
        x.button("Confirmar compra", key=f"tc_ok_{p['id']}", type="primary", width="stretch", on_click=_confirmar)
        y.button("Cancelar", key=f"tc_no_{p['id']}", width="stretch", on_click=_cancelar)
    elif not ok:
        st.caption(motivo)
    elif s < p["preco"]:
        st.caption(f"Faltam {p['preco'] - s} TC.")
    else:
        st.button("Comprar", key=f"tc_c_{p['id']}", width="stretch", on_click=_pedir, args=(p["id"],))


def _equipar_ui(c: dict, u: dict) -> None:
    """Escolha do distintivo e da moldura entre os itens que a conta possui."""
    possui = {b["produto_id"] for b in TC.beneficios_ativos(c["id"])}
    atual = TC.equipado(u["email"])
    for tipo, rot in (("distintivo", "Distintivo"), ("moldura", "Moldura")):
        ops = [p for p in TC.CATALOGO if p["efeito"]["kind"] == tipo and p["id"] in possui]
        if not ops:
            continue
        nomes = {p["id"]: p["nome"] for p in ops}
        escolha = st.selectbox(f"{rot} em uso", [None, *nomes], format_func=lambda i: "Nenhum" if i is None else nomes[i],
                               index=([None, *nomes].index(atual.get(tipo)) if atual.get(tipo) in nomes else 0), key=f"tc_eq_{tipo}")
        if escolha != atual.get(tipo):
            try:
                TC.equipar(c["id"], u["email"], escolha, tipo)
                st.rerun()
            except TC.ErroTC as e:
                st.error(str(e))


def pagina_loja() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    st.title("🛍️ Loja Ticker")
    faixa("loja")
    if _precisa_login() or not _banco_ok():
        _rodape()
        return
    u = _conta()
    c = {"id": u["id"]}
    r = st.session_state.pop("tc_res", None)
    if r:
        if r.get("ok"):
            st.success("Compra feita! O benefício já está ativo." if not r.get("duplicada") else "Esta compra já tinha sido feita (nada foi cobrado de novo).")
        else:
            st.error(r.get("erro", "Não foi possível concluir a compra."))
    s = TC.saldo(c["id"])
    st.markdown(f"<span class='tc-chip'>🪙 Seu saldo: {s} TC</span>", unsafe_allow_html=True)
    nomes = list(TC.CATEGORIAS)
    for cat in nomes:
        st.markdown(f"**{TC.CATEGORIAS[cat]}**")
        itens = TC.produtos(cat)
        if not itens:
            st.markdown(f"<div class='tc-card tc-pre'><div class='t'>Em preparação</div><div class='d'>{_e(TC.EM_PREPARACAO.get(cat, 'Nenhum item disponível agora.'))}</div></div>", unsafe_allow_html=True)
        for p in itens:
            _card_produto(p, c, s)
    _equipar_ui(c, u)
    st.markdown("**Minhas compras**")
    cs = TC.compras(c["id"], 20)
    if not cs:
        st.caption("Você ainda não comprou nada.")
    for x in cs:
        p = TC.produto(x["produto_id"]) or {}
        est = TC.ROTULO_ESTADO.get(x["estado"], x["estado"])
        st.markdown(f"<div class='tc-card'><div class='t'>{_e(p.get('nome', x['produto_id']))} <span class='tc-neg' style='float:right'>-{int(x['preco'])} TC</span></div>"
                    f"<div class='m'>{_e(_fmt(x['criado_em']))} · {_e(est)}</div></div>", unsafe_allow_html=True)
    _rodape()


# ------------------------------------------------------------------ painel administrativo (seção "TickerCoins")
def admin(a) -> None:
    """Visão geral, conta, preços/recompensas, compras e tentativas suspeitas. Cada operação confere a permissão e é auditada em tickercoins.py."""
    TC.exigir(a, "admin.tickercoins.ver")
    pode = TC.permissoes.tem(a.papel, "admin.tickercoins")
    est = TC.admin_estatisticas(a)
    st.markdown(f"**Contas com moedas:** {est['contas_com_moedas']} · **Recebido:** {est['recebido']} TC · **Usado:** {est['usado']} TC · "
                f"**Compras:** {est['compras']} · **Tentativas suspeitas:** {est['fraudes']}")
    st.caption(f"Base: {est['amostra']}.")
    ok, motivo = TC.disponivel()
    if not ok:
        st.warning(motivo)
        return
    st.markdown("**Conta**")
    email = st.text_input("E-mail da conta", key="tc_adm_email")
    d = TC.admin_conta(a, email) if email.strip() else None
    if email.strip() and not d:
        st.info("Conta não encontrada.")
    if d:
        st.markdown(f"Saldo: **{d['saldo']} TC** · recebido {d['totais']['recebido']} · usado {d['totais']['usado']} · "
                    f"integridade do livro: {'ok' if d['integridade']['ok'] else 'INCONSISTENTE'}")
        for x in d["historico"][:15]:
            st.markdown(_linha_hist(x), unsafe_allow_html=True)
        if pode:
            v = st.number_input("Quantidade (negativa remove)", value=0, step=1, key="tc_adm_val")
            j = st.text_input("Justificativa (obrigatória)", key="tc_adm_just")
            if st.button("Aplicar ajuste", key="tc_adm_go"):
                try:
                    TC.admin_ajustar(a, d["conta"]["id"], int(v), j)
                    st.success("Ajuste feito e auditado.")
                    st.rerun()
                except (TC.ErroTC, banco.ErroBanco, banco.SemPermissao) as e:
                    st.error(str(e))
    if pode:
        _admin_config(a)
    st.markdown("**Compras recentes**")
    for x in TC.admin_compras_recentes(a, 15):
        st.markdown(f"<div class='tc-card'><div class='t'>{_e(x['produto_id'])} · {int(x['preco'])} TC · {_e(x['estado'])}</div>"
                    f"<div class='m'>{_e(_fmt(x['criado_em']))} · conta {_e(x['conta_id'][:8])}</div></div>", unsafe_allow_html=True)
        if pode and x["estado"] == "confirmada":
            if st.button("Estornar", key=f"tc_est_{x['id']}"):
                try:
                    TC.estornar_compra(a, x["id"], "estorno pelo painel")
                    st.rerun()
                except (TC.ErroTC, banco.ErroBanco) as e:
                    st.error(str(e))
    st.markdown("**Tentativas inválidas (anúncios)**")
    fr = TC.admin_fraudes(a, 15)
    if not fr:
        st.caption("Nenhuma.")
    for x in fr:
        st.caption(f"{_fmt(x['quando'])} · {x['detalhes']}")


def _admin_config(a) -> None:
    cfg = TC.config(True)
    st.markdown("**Economia (valores em TC)**")
    novo = {"recompensas": {}, "anuncios": {}, "produtos": {}}
    for k, r in cfg["recompensas"].items():
        c1, c2 = st.columns([3, 1])
        v = c1.number_input(r["rotulo"], 0, 1000, int(r["valor"]), key=f"tc_cf_r_{k}")
        on = c2.checkbox("Ativa", bool(r["ativo"]), key=f"tc_cf_ra_{k}")
        novo["recompensas"][k] = {"valor": int(v), "ativo": on}
    novo["limite_diario_ganhos"] = int(st.number_input("Limite diário de ganhos por estudo", 0, 10000, int(cfg["limite_diario_ganhos"]), key="tc_cf_lim"))
    an = cfg["anuncios"]
    novo["anuncios"] = {"ativo": st.checkbox("Anúncios recompensados ligados (exige provedor configurado)", bool(an["ativo"]), key="tc_cf_an"),
                        "valor": int(st.number_input("Valor por anúncio", 0, 1000, int(an["valor"]), key="tc_cf_anv")),
                        "limite_dia": int(st.number_input("Anúncios por dia", 0, 100, int(an["limite_dia"]), key="tc_cf_and")),
                        "intervalo_min": int(st.number_input("Intervalo entre anúncios (min)", 0, 1440, int(an["intervalo_min"]), key="tc_cf_ani"))}
    st.markdown("**Produtos**")
    for p in TC.produtos(None, so_ativos=False):
        c1, c2 = st.columns([2, 1])
        preco = c1.number_input(p["nome"], 0, TC.MAX_VALOR, int(p["preco"]), key=f"tc_cf_p_{p['id']}")
        on = c2.checkbox("À venda", bool(p["ativo"]), key=f"tc_cf_pa_{p['id']}")
        novo["produtos"][p["id"]] = {"preco": int(preco), "ativo": on}
    j = st.text_input("Justificativa da alteração", key="tc_cf_just")
    if st.button("Salvar configuração", key="tc_cf_go", type="primary"):
        if len(j.strip()) < 5:
            st.error("Informe a justificativa (mínimo 5 caracteres).")
            return
        try:
            TC.salvar_config(a, novo, j)
            st.success("Configuração salva e auditada.")
        except (TC.ErroTC, banco.ErroBanco, banco.SemPermissao) as e:
            st.error(str(e))
