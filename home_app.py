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
        corpo = HV.html_ranking_corpo(r, logado, participa)
        if r.get("vazio") or not r.get("top"):
            st.markdown(corpo, unsafe_allow_html=True)
            return
        import amigos_app as AMA                     # cada líder é clicável: abre o perfil público
        q = "html body .stApp.stApp.stApp"
        st.markdown(f"<style>{q} .st-key-hm_rk > :is(.st-key-hm_rk_c,div:has(> .st-key-hm_rk_c)){{grid-column:1 / -1;grid-row:2;min-width:0}}"
                    f"{q} .st-key-hm_rk_c{{display:grid !important;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:8px !important}}"
                    f"{q} .st-key-hm_rk_c > :last-child{{grid-column:1 / -1}}{q} .st-key-hm_rk_c .hm-rk-grid{{display:block}}"
                    f"{q} .hm-av2{{flex:0 0 auto;display:inline-flex}}</style>", unsafe_allow_html=True)
        with st.container(key="hm_rk_c"):
            chips = ""
            for x in r["top"]:
                ch = HV._chip_top(x)
                chips += ch
                av = AMA.avatar_por_apelido(x.get("apelido", ""), 30)            # avatar equipado no lugar da inicial
                if av:
                    import re as _re
                    ch = _re.sub(r"<span class='hm-av'>.*?</span>", f"<span class='hm-av2'>{av}</span>", ch, count=1)
                AMA.linha_clicavel(f"hm_{x['pos']}", f"<div class='hm-rk-grid'>{ch}</div>",
                                   None if participa and x.get("apelido") == apelido else AMA.usuario_de_apelido(x.get("apelido", "")))
            st.markdown(corpo.replace(chips, "", 1), unsafe_allow_html=True)


def desempenho(ir=None, est_carteira: dict | None = None) -> None:
    """Maiores altas, maiores quedas e mais rentável da carteira do jogo (resultado desde a compra, pelo preço médio).
    Mostrado na carteira (Wallet Game › Meu patrimônio), que passa a carteira já carregada em `est_carteira`."""
    if est_carteira is not None:
        logado, participa, est = True, True, est_carteira
    else:
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
            st.caption("Comece a sua carteira para acompanhar o desempenho.")


def nivel_xp(xp) -> str:
    try:
        import nivel
        return HV.html_nivel(nivel.estado(xp))
    except Exception:
        return ""
