"""Adaptador do Streamlit para a Home nova: lê os dados que o app já tem (ranking publicado, carteira do Wallet Game, XP) e desenha os cartões.
As regras ficam em home_dados.py e o HTML em home_visual.py (sem Streamlit), para a futura API reaproveitar. Nada aqui grava dados."""
from __future__ import annotations

import streamlit as st

import home_dados as HD
import home_visual as HV


def _jogo():
    """(logado, participa, carteira_do_jogo|None, apelido, ranking_publicado). Falha de leitura nunca derruba a Home."""
    import usuarios
    a = usuarios.ator()
    if not a:
        return False, False, None, "", {}
    try:
        import competicao_app as CA
        c = CA._pessoa(a)
        perfil = c.get("perfil") or {}
        cart = c.get("cart") or {}
        est = cart if cart.get("v") == 1 else None
        rk = CA._publico("comp_ranking") or {}
        return True, bool(perfil.get("aceite")), est, str(perfil.get("apelido") or ""), rk
    except Exception:
        return True, False, None, "", {}


def ranking(ir) -> None:
    import ranking_parcial as RP
    logado, participa, est, apelido, rk = _jogo()
    listas, rotulo = RP.escolher(rk)
    geral = listas.get("geral") or []
    mr = (est or {}).get("rank") or {}
    n = mr.get("n")
    total = listas.get("geral_n") if rotulo else ((n.get("geral") if isinstance(n, dict) else n) or listas.get("geral_n"))
    try:
        import competicao as C
        meu_ret = C.retorno_total(est) if est and (est.get("hist") or []) else None
    except Exception:
        meu_ret = None
    if rotulo:                                  # parcial: posição e retorno saem da própria lista parcial, não do último fechamento
        r = HD.ranking_resumo(geral, total, None, apelido if participa else None, None, dia=rk.get("dia"), parcial=rotulo)
    else:
        r = HD.ranking_resumo(geral, total, mr.get("geral"), apelido if participa else None, meu_ret,
                              dia=rk.get("dia"), meu_ao_vivo=HD.retorno_atual(est))
    with st.container(key="hm_rk"):
        st.markdown(HV.html_ranking_cab(), unsafe_allow_html=True)
        st.button("Ver ranking completo", key="hm_rk_ver", icon=":material/chevron_right:", on_click=ir,
                  args=("competicao", {"wg_sec": "Classificação"}))
        st.markdown(HV.html_ranking_corpo(r, logado, participa), unsafe_allow_html=True)


def desempenho(ir) -> None:
    logado, participa, est, _ap, _rk = _jogo()
    d = {"altas": [], "quedas": [], "mais_rentavel": None, "vazio": True, "criterio": HD.CRITERIO}
    if est:
        try:
            import carteira_unica as CU
            d = HD.desempenho(CU.resumo(est)["posicoes"], HD.realizado_por_ativo(est.get("ext")))
        except Exception:
            pass
    with st.container(key="hm_perf"):
        st.markdown(HV.html_titulo_desempenho(d["criterio"]), unsafe_allow_html=True)
        st.markdown(HV.html_altas(d), unsafe_allow_html=True)
        st.markdown(HV.html_quedas(d), unsafe_allow_html=True)
        st.markdown(HV.html_mais_rentavel(d), unsafe_allow_html=True)
        if not logado:
            st.caption("Entre na sua conta para acompanhar o desempenho da sua carteira.")
        elif not participa:
            st.caption("Entre na Wallet Game para montar uma carteira e acompanhar o desempenho.")
        st.button("Ver todos", key="hm_perf_ver", icon=":material/chevron_right:", on_click=ir, args=("carteira", {}), width="stretch")


def nivel_xp(xp) -> str:
    try:
        import nivel
        return HV.html_nivel(nivel.estado(xp))
    except Exception:
        return ""
