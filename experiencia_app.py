"""Interface do "Meu modo de experiência": troca livre com prévia e confirmação, faixa explicativa por tela e personalização.

A troca é gratuita, sem limite e sem justificativa. Mexe só em prefs["modo"] (e no nível de leitura da Educação, que é só apresentação).
Nada de carteira, histórico, alertas, relatórios, cálculos, progresso ou assinatura é lido ou alterado aqui.
"""
from __future__ import annotations

import html

import streamlit as st

import banco
import experiencia as E
import prefs as P
import usuarios

_ICONE = {"iniciante": ":material/school:", "intermediario": ":material/balance:", "avancado": ":material/query_stats:"}


def modo() -> str:
    return E.modo_de(st.session_state.get("prefs"))


def efetivo() -> dict:
    return E.efetivo(st.session_state.get("prefs"))


def aplicar(novo: str) -> bool:
    """Troca o modo, grava na conta na hora (vale em outros aparelhos) e alinha o nível de leitura da Educação. Devolve True se mudou."""
    ss = st.session_state
    antes = modo()
    if novo not in E.MODOS or novo == antes:
        return False
    ss["prefs"] = E.trocar_modo(ss.get("prefs"), novo)
    try:
        if isinstance(ss.get("edu_progresso"), dict):          # só o nível de leitura; trilhas, notas e conclusões ficam como estão
            ss["edu_progresso"]["modo"] = novo
        if "edu_modo_sel" in ss:
            ss["edu_modo_sel"] = novo
    except Exception:
        pass
    try:
        banco.auditar(usuarios.ator().id, "experiencia.modo_trocado", f"{antes}>{novo}")
    except Exception:
        pass
    try:
        usuarios.salvar()
    except Exception:
        pass
    ss["_exp_msg"] = f"Pronto: agora você está no modo {E.ROTULOS[novo]}. Seus dados continuam todos iguais."
    return True


def _confirmar(novo: str, chave: str) -> None:
    aplicar(novo)
    st.session_state.pop(f"exp_sel_{chave}", None)


def previa_md(m: str) -> str:
    i = E.INFO[m]
    return f"**Como ficará no modo {E.ROTULOS[m]}**\n\n{i['resumo']}\n\n" + "\n".join(f"- {x}" for x in i["muda"]) + f"\n\n_{E.NAO_MUDA}_"


def seletor(chave: str) -> None:
    """Escolha do modo com prévia. `chave` distingue as instâncias na mesma tela (menu, conta, celular)."""
    atual = modo()
    if st.session_state.get("_exp_msg"):
        st.success(st.session_state.pop("_exp_msg"))
    sel = st.radio("Escolha o modo", list(E.MODOS), index=list(E.MODOS).index(atual), format_func=lambda m: E.ROTULOS[m] + (" (atual)" if m == atual else ""),
                   key=f"exp_sel_{chave}", horizontal=False, label_visibility="collapsed")
    if sel != atual:
        with st.container(border=True):
            st.markdown(previa_md(sel))
        c1, c2 = st.columns(2)
        c1.button("Confirmar mudança", type="primary", key=f"exp_ok_{chave}", on_click=_confirmar, args=(sel, chave), width="stretch")
        c2.button("Manter o atual", key=f"exp_no_{chave}", on_click=lambda: st.session_state.pop(f"exp_sel_{chave}", None), width="stretch")
    else:
        st.caption(E.INFO[atual]["resumo"])
    st.caption("Grátis, sem limite de trocas e reversível. " + "Não apaga nem altera nenhum dado.")


def personalizacao(chave: str = "p") -> None:
    """Ajustes finos DENTRO do modo (só apresentação)."""
    e = P.normalizar(st.session_state.get("prefs"))["exp"]
    c1, c2, c3 = st.columns(3)
    det = c1.selectbox("Quantidade de informações", list(P.EXP_DETALHE), index=list(P.EXP_DETALHE).index(e["detalhe"]), format_func=P.EXP_DETALHE.get, key=f"exp_det_{chave}")
    expl = c2.selectbox("Explicações educativas", list(P.EXP_TRI), index=list(P.EXP_TRI).index(e["explicacoes"]), format_func=P.EXP_TRI.get, key=f"exp_expl_{chave}")
    dic = c3.selectbox("Dicas e orientações nas telas", list(P.EXP_TRI), index=list(P.EXP_TRI).index(e["dicas"]), format_func=P.EXP_TRI.get, key=f"exp_dic_{chave}")
    novo = {"detalhe": det, "explicacoes": expl, "dicas": dic}
    if novo != e:
        st.session_state["prefs"] = P.normalizar({**P.normalizar(st.session_state.get("prefs")), "exp": novo})
        try:
            usuarios.salvar()
        except Exception:
            pass
    st.caption("Estes ajustes mudam só o que aparece na tela. Painel e indicadores favoritos ficam em Preferências.")


def faixa(url_path: str) -> None:
    """Faixa no topo da tela: guia (Iniciante) ou nota técnica (Avançado). Some se a pessoa desligou as dicas."""
    f = E.faixa_da_pagina(url_path, st.session_state.get("prefs"))
    if not f:
        return
    with st.container(border=True):
        st.markdown(f"**{f['titulo']}**  \n" + "  \n".join(f["linhas"]))


def menu_expander() -> None:
    with st.expander(f"Meu modo: {E.ROTULOS[modo()]}", icon=":material/tune:"):
        seletor("menu")


def pagina_bloco() -> None:
    st.markdown("#### Meu modo de experiência")
    st.write("Escolha como o app se apresenta para você. É só a aparência: mesmo preço, mesmas ferramentas, mesmos ativos e nenhum dado muda.")
    seletor("conta")
    st.markdown("##### Personalizar dentro do modo")
    personalizacao("conta")
