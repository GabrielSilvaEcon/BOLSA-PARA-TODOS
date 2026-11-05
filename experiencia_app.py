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


def escolher_inicial(novo: str) -> None:
    """Primeira escolha (caixa de boas-vindas): grava o nível e marca que a pessoa já escolheu, mesmo se for o padrão."""
    ss = st.session_state
    antes = modo()
    if novo not in E.MODOS:
        return
    ss["prefs"] = E.trocar_modo(ss.get("prefs"), novo)
    try:
        if isinstance(ss.get("edu_progresso"), dict):
            ss["edu_progresso"]["modo"] = novo
        if "edu_modo_sel" in ss:
            ss["edu_modo_sel"] = novo
    except Exception:
        pass
    try:
        banco.auditar(usuarios.ator().id, "experiencia.modo_escolhido", f"{antes}>{novo}")
    except Exception:
        pass
    try:
        usuarios.salvar()
    except Exception:
        pass
    ss["_exp_msg"] = f"Pronto: agora você está no nível {E.ROTULOS[novo]}. Seus dados continuam todos iguais."


def boas_vindas() -> bool:
    """Caixa de escolha do nível de conhecimento na página Início. Só aparece até a pessoa escolher; depois nunca mais sozinha."""
    if E.ja_escolheu(st.session_state.get("prefs")):
        return False
    with st.container(border=True):
        st.markdown("### Bem-vindo ao Bússola B3")
        st.write("Como você prefere ver as informações? Escolha o nível que combina com você. "
                 "Isso muda só a linguagem e a profundidade das explicações, e você pode trocar quando quiser.")
        for col, m in zip(st.columns(3), E.MODOS):
            nome, sub, itens = E.BOAS_VINDAS[m]
            with col.container(border=True):
                st.markdown(f"**{nome}**")
                st.caption(sub)
                st.markdown("\n".join(f"- {x}" for x in itens))
                st.button(f"Escolher {nome}", key=f"bv_{m}", type="primary", on_click=escolher_inicial, args=(m,), width="stretch")
        st.caption("Grátis, sem limite de trocas e sem apagar nada. Para mudar depois: Minha conta, em Meu nível de conhecimento.")
    return True


def nivel_discreto() -> None:
    """Linha discreta no Início: mostra o nível atual e abre a troca sem ocupar espaço fixo."""
    c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
    c1.caption(f"Seu nível de conhecimento: **{E.ROTULOS[modo()]}**")
    with c2.popover("Alterar", icon=":material/tune:", width="stretch"):
        seletor("inicio", compacto=True)


def inicio() -> None:
    """Topo da página Início: boas-vindas na primeira vez; depois, só a linha discreta do nível."""
    if not boas_vindas():
        msg = st.session_state.pop("_exp_msg", None)
        if msg:
            st.toast(msg, icon=":material/check_circle:")
        try:
            import ajuda_app                                   # introdução curta: só no primeiro acesso, depois do nível escolhido
            ajuda_app.introducao()
        except Exception:
            pass
        nivel_discreto()


def _confirmar(novo: str, chave: str) -> None:
    aplicar(novo)
    st.session_state.pop(f"exp_sel_{chave}", None)


def previa_md(m: str) -> str:
    i = E.INFO[m]
    return f"**Como ficará no modo {E.ROTULOS[m]}**\n\n{i['resumo']}\n\n" + "\n".join(f"- {x}" for x in i["muda"]) + f"\n\n_{E.NAO_MUDA}_"


def seletor(chave: str, compacto: bool = False) -> None:
    """Escolha do modo com prévia. `chave` distingue as instâncias na mesma tela (menu, conta, celular)."""
    atual = modo()
    if st.session_state.get("_exp_msg"):
        _msg = st.session_state.pop("_exp_msg")
        if compacto:
            st.caption("✅ " + _msg.split(".")[0] + ".")
        else:
            st.success(_msg)
    sel = st.radio("Escolha o modo", list(E.MODOS), index=list(E.MODOS).index(atual), format_func=lambda m: E.ROTULOS[m] + (" (atual)" if m == atual else ""),
                   key=f"exp_sel_{chave}", horizontal=False, label_visibility="collapsed")
    if sel != atual:
        with st.container(border=True):
            if compacto:
                st.markdown(f"**Modo {E.ROTULOS[sel]}**\n\n{E.INFO[sel]['resumo']}\n\n_Seus dados não mudam, só a apresentação._")
            else:
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


def glossario_da_pagina(url_path: str) -> None:
    """Quadro recolhido com os termos da tela, no nível escolhido. Falha nunca derruba a página."""
    try:
        import glossario_app
        glossario_app.painel(E.TERMOS_DA_PAGINA.get(url_path, ()))
    except Exception:
        pass


def menu_expander() -> None:
    with st.expander("Meu modo", icon=":material/tune:"):
        st.caption(f"Agora: {E.ROTULOS[modo()]}")
        seletor("menu", compacto=True)


def pagina_bloco() -> None:
    st.markdown("#### Meu nível de conhecimento")
    st.write("Escolha como o app se apresenta para você. É só a apresentação: mesmo preço, mesmas ferramentas, mesmos ativos e nenhum dado muda.")
    seletor("conta")
    st.markdown("##### Personalizar dentro do modo")
    personalizacao("conta")


def mostrar(card: dict) -> None:
    """Mostra a leitura em palavras de um resultado (cartão de leitura.py), na linguagem do modo escolhido."""
    if not card:
        return
    with st.container(border=True):
        st.markdown(f"**{card['titulo']}**")
        {"bom": st.success, "ok": st.info, "ruim": st.warning}.get(card["nivel"], st.info)(card["resumo"])
        for p in card["pontos"]:
            st.markdown(f"- {p}")
        if card.get("rodape"):
            st.caption(card["rodape"])


def mostrar_varios(cartoes: list, titulo: str = "Leitura do resultado") -> None:
    cartoes = [c for c in cartoes if c]
    if not cartoes:
        return
    with st.expander(titulo + f" · modo {E.ROTULOS[modo()]}", icon=":material/menu_book:", expanded=True):
        for c in cartoes:
            mostrar(c)


def rotular_df(df, fmts=None):
    """Iniciante: troca siglas dos cabeçalhos por nomes por extenso (só na exibição; o df original não muda)."""
    import leitura
    mapa = leitura.rotular(list(df.columns), modo())
    novo = df.rename(columns=mapa)
    return (novo, {mapa.get(k, k): v for k, v in fmts.items()}) if fmts is not None else novo
