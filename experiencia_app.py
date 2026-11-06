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


def _cartao_nivel(m: str) -> str:
    """Cartão ilustrado de um nível: o mesmo resultado escrito de três jeitos, o quanto de texto/número/detalhe e o que muda no app."""
    import paleta as PL
    nome, sub, itens = E.BOAS_VINDAS[m]
    il = E.ILUSTRACAO[m]
    cor = {"bom": PL.BOM, "marca": PL.MARCA_CLARA, "ouro": PL.OURO}[il["cor"]]
    forte = "color:#FFFFFF !important;-webkit-text-fill-color:#FFFFFF"
    claro = f"color:{PL.TEXTO_2} !important;-webkit-text-fill-color:{PL.TEXTO_2}"
    mudo = f"color:{PL.MUDO} !important;-webkit-text-fill-color:{PL.MUDO}"
    meds = ""
    for rot, n in zip(E.MEDIDORES, il["medidores"]):
        bolas = "".join(f"<i style='display:inline-block;width:11px;height:11px;border-radius:50%;margin-right:4px;background:{cor if k < n else 'rgba(189,181,230,.22)'}'></i>" for k in range(3))
        meds += (f"<div style='display:flex;justify-content:space-between;align-items:center;gap:8px;margin:5px 0'>"
                 f"<span style='{claro};font-size:.86rem'>{html.escape(rot)}</span><span>{bolas}</span></div>")
    itens_html = "".join(f"<li style='{claro};margin:2px 0;font-size:.88rem'>{html.escape(x)}</li>" for x in itens[:4])
    chip = lambda t: (f"<span style='display:inline-block;margin:3px 6px 0 0;padding:3px 10px;border-radius:99px;border:1px solid {cor};{claro};font-size:.78rem'>{html.escape(t)}</span>")
    return (f"<div style='border:2px solid {cor};border-radius:18px;padding:16px 16px 14px;background:{PL.BG_2}'>"
            f"<div style='display:flex;align-items:center;gap:12px'>"
            f"<div style='width:46px;height:46px;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:1.5rem;background:{cor}26;border:1px solid {cor}'>{il['icone']}</div>"
            f"<div><div style='{forte};font-weight:800;font-size:1.2rem'>{html.escape(nome)}</div><div style='{mudo};font-size:.84rem'>{html.escape(sub)}</div></div></div>"
            f"<div style='margin-top:12px;{mudo};font-size:.76rem'>O mesmo resultado, escrito neste nível:</div>"
            f"<div style='margin-top:4px;padding:10px 12px;border-radius:12px;border-left:4px solid {cor};background:{PL.BG_3};{forte};font-size:.9rem;line-height:1.45'>“{html.escape(il['exemplo'])}”</div>"
            f"<div style='margin-top:12px'>{meds}</div>"
            f"<ul style='margin:10px 0 6px;padding-left:18px'>{itens_html}</ul>"
            f"<div style='margin-top:6px'>{chip(il['menu'])}{chip(il['analise'])}</div>"
            f"<div style='margin-top:10px;{claro};font-size:.86rem'><b style='{forte}'>Na prática:</b> {html.escape(il['ideal'])}</div></div>")


def boas_vindas() -> bool:
    """Tela de escolha do nível de conhecimento na página Início. É a primeira coisa que a pessoa vê; só some depois que ela escolher."""
    if E.ja_escolheu(st.session_state.get("prefs")):
        return False
    st.markdown("## Bem-vindo ao Bússola B3")
    st.write("Antes de começar, escolha como você prefere ver as informações. Compare os três jeitos abaixo: "
             "o resultado é o mesmo, muda só a linguagem, a quantidade de números e o tamanho do menu.")
    for col, m in zip(st.columns(3), E.MODOS):
        with col:
            st.markdown(_cartao_nivel(m), unsafe_allow_html=True)
            st.button(f"Escolher {E.ROTULOS[m]}", key=f"bv_{m}", type="primary", on_click=escolher_inicial, args=(m,), width="stretch")
    st.caption(E.AVISO_EXEMPLO)
    st.caption("Grátis, sem limite de trocas e sem apagar nada. Para mudar depois: Minha conta, em Meu nível de conhecimento. "
               "Depois de escolher, você segue para a busca e a análise de ações.")
    return True


def nivel_discreto() -> None:
    """Linha discreta no Início: mostra o nível atual e abre a troca sem ocupar espaço fixo."""
    c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
    c1.caption(f"Seu nível de conhecimento: **{E.ROTULOS[modo()]}**")
    with c2.popover("Alterar", icon=":material/tune:", width="stretch"):
        seletor("inicio", compacto=True)


def inicio() -> bool:
    """Topo da página Início: boas-vindas na primeira vez (devolve True: a página para aí, sem busca nem análise); depois, só a linha discreta do nível."""
    if boas_vindas():
        return True
    msg = st.session_state.pop("_exp_msg", None)
    if msg:
        st.toast(msg, icon=":material/check_circle:")
    try:
        import ajuda_app                                       # introdução curta: só no primeiro acesso, depois do nível escolhido
        ajuda_app.introducao()
    except Exception:
        pass
    return False


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
