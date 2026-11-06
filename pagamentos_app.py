"""Telas do pagamento online: botões "Assinar" na página Planos e o aviso de pagamento em análise.

Toda a regra (valores, cobrança, confirmação, liberação do plano) fica em pagamentos.py; aqui só há tela.
Sem chave do Mercado Pago nos secrets, nada disto aparece e o app segue como antes.
"""
from __future__ import annotations

import html

import streamlit as st

import pagamentos as PG
import planos

E = html.escape


def _msg(txt: str, tipo: str = "info") -> None:
    {"ok": st.success, "erro": st.error, "aviso": st.warning}.get(tipo, st.info)(txt)


def _data_br(iso: str | None) -> str:
    try:
        a, m, d = str(iso)[:10].split("-")
        return f"{d}/{m}/{a}"
    except ValueError:
        return "—"


def avisar_liberacao(liberadas: list[dict]) -> None:
    for d in liberadas:
        _msg(f"Pagamento confirmado. Seu plano {planos.ROTULO.get(d['plano'], d['plano'])} está ativo até {_data_br(d.get('ate'))}.", "ok")


def bloco_pendente(email: str, chave: str = "pg") -> None:
    """Mostra cobranças aguardando pagamento e o botão para conferir. Some quando não há nada pendente."""
    if not PG.ligado():
        return
    flash = st.session_state.pop("_pagto_ok", None)
    if flash:
        avisar_liberacao(flash)
    try:
        pend = PG.pendentes(email)
    except Exception:
        return
    if not pend:
        return
    d = pend[0]
    nome = f"{planos.ROTULO.get(d['plano'], d['plano'])} · {PG.PERIODOS[d['periodo']]['rotulo']}"
    with st.container(border=True):
        st.markdown(f"**Pagamento em análise: {E(nome)}** · {PG.brl(float(d['valor']))}")
        st.caption("Pix costuma confirmar em segundos; cartão, em poucos minutos. Assim que o Mercado Pago aprovar, o plano é liberado aqui.")
        c1, c2 = st.columns(2)
        if d.get("link"):
            c1.link_button("Ir para o pagamento", d["link"], icon=":material/lock:")
        if c2.button("Já paguei, verificar", key=f"{chave}_verif", icon=":material/refresh:"):
            lib = PG.verificar_automatico(email, forcar=True)
            if lib:
                st.session_state["_pagto_ok"] = lib
                st.rerun()
            _msg("Ainda não encontrei o pagamento aprovado. Se acabou de pagar, aguarde um minuto e tente de novo.", "aviso")


def secao_assinar() -> None:
    """Escolha de período e botões de assinatura para Plus e Premium (Planos)."""
    if not PG.ligado():
        return
    import usuarios
    u = usuarios.usuario()
    st.markdown("#### Assinar um plano")
    if not u:
        _msg("Entre na sua conta para assinar. É rápido e seus dados ficam guardados nela.")
        return
    if u.get("papel") in ("admin", "suporte"):
        st.caption("Contas da equipe não precisam de plano.")
        return
    bloco_pendente(u["email"], "pgp")
    cfg = PG.config()
    desc = cfg["desconto_anual_pct"]
    ops = {"mensal": "1 mês"}
    if desc > 0:
        ops["anual"] = f"12 meses (economize {desc:g}%)"
    else:
        ops["anual"] = "12 meses"
    per = st.radio("Período", list(ops), format_func=ops.get, horizontal=True, key="pg_per")
    ass = planos.assinatura_de(u["email"], u.get("papel"))
    cols = st.columns(2)
    for col, pl in zip(cols, PG.PAGOS):
        v = PG.valor(pl, per, desconto_anual=desc)
        with col.container(border=True):
            st.markdown(f"**{E(planos.ROTULO.get(pl, pl))}**")
            if v <= 0:
                st.caption("Em breve")
                continue
            dias = PG.PERIODOS[per]["dias"]
            st.markdown(f"### {PG.brl(v)}")
            extra = f" ({PG.brl(v / 12)} por mês)" if per == "anual" else ""
            st.caption(f"{PG.PERIODOS[per]['rotulo']} de acesso, pago uma vez{extra}. Sem renovação automática.")
            bloqueado = pl == "plus" and ass["contratado"] == "premium" and not ass["vencida"]
            if ass["contratado"] == pl and not ass["vencida"]:
                st.caption(f"Você já tem este plano até {_data_br(ass['ate'])}. Pagar agora soma {dias} dias ao vencimento.")
            elif ass["contratado"] == "plus" and pl == "premium" and not ass["vencida"]:
                st.caption("Ao passar para o Premium, os dias que restam do Plus não são somados.")
            if st.button(f"Assinar {planos.ROTULO.get(pl, pl)}", key=f"pg_ass_{pl}", type="primary", disabled=bloqueado,
                         help="Disponível quando o Premium vencer." if bloqueado else None, width="stretch"):
                try:
                    st.session_state["_pagto_link"] = PG.criar_cobranca(u["email"], pl, per)
                except PG.ErroPagamento as e:
                    _msg(str(e), "erro")
    d = st.session_state.get("_pagto_link")
    if d and d.get("link") and d.get("email") == u["email"]:
        with st.container(border=True):
            st.markdown(f"**Tudo pronto: {PG.brl(float(d['valor']))}** · {E(planos.ROTULO.get(d['plano'], d['plano']))} · {PG.PERIODOS[d['periodo']]['rotulo']}")
            st.caption("Você paga na página segura do Mercado Pago, com Pix ou cartão. Depois volte aqui: o plano é liberado sozinho.")
            st.link_button("Pagar no Mercado Pago", d["link"], type="primary", icon=":material/lock:")
            if d.get("teste"):
                st.caption("Modo de teste: nenhum dinheiro real é cobrado.")
    st.caption("Pagamento processado pelo Mercado Pago. O app não guarda dados de cartão.")
