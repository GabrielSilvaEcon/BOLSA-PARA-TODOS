"""Tela da liga de estudo (opcional), no fim da aba Jornada. A lógica está em jornada_liga.py; o acesso aos dados em banco.edu_liga_*.

- Desligada por padrão. Só quem ligar aparece, e só com apelido da Competição + XP da semana.
- Usa as ligas de amigos que a pessoa já tem na Competição (mesmo código de convite). Sem liga, a tela explica como entrar.
- Qualquer falha (banco fora do ar, sem login) mostra um aviso curto e nunca derruba a Jornada.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st

import banco
import competicao as C
import competicao_ligas as L
import jornada_liga as JL
import usuarios

CACHE = "_jor_liga_cache"
TTL_S = 60


def _ator():
    try:
        return usuarios.ator()
    except Exception:
        return None


def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _contexto(a) -> dict:
    """Apelido da competição, ligas da pessoa (código → nome) e documento da liga de estudo. Tudo da própria conta."""
    perfil = C.sanear_perfil(banco.comp_ordens_ler(a))
    codigos = L.codigos(banco.comp_ligas_ler(a))
    nomes = {}
    for c in codigos:
        try:
            d = banco.comp_liga_definicao(a, c)
        except Exception:
            d = None
        if d:
            nomes[c] = d["nome"]
    return {"apelido": perfil.get("apelido") or "", "ligas": nomes, "doc": JL.sanear(banco.edu_liga_ler(a))}


def _publicar(a, prog, ctx: dict) -> dict:
    """Mantém o documento da pessoa em dia (XP da semana). Só grava quando algo mudou, para não escrever a cada clique."""
    novo = JL.atualizar(ctx["doc"], prog(), ctx["apelido"])
    novo["ligado"] = True
    if novo != ctx["doc"]:
        banco.edu_liga_gravar(a, novo)
        st.session_state.pop(CACHE, None)
    return novo


def _mudar(a, prog, ctx: dict) -> None:
    ligar = bool(st.session_state.get("jor_liga_on"))
    ok, msg = JL.pode_participar(ctx["apelido"])
    if ligar and not ok:
        st.session_state["jor_liga_on"] = False
        st.session_state["jor_liga_aviso"] = msg
        return
    try:
        banco.edu_liga_gravar(a, JL.definir_ligado(ctx["doc"], ligar, prog(), ctx["apelido"]))
        st.session_state.pop(CACHE, None)
    except Exception as e:
        banco.registrar_erro("jornada_liga_app.mudar", e)
        st.session_state["jor_liga_on"] = not ligar
        st.session_state["jor_liga_aviso"] = "Não consegui salvar agora. Tente de novo em instantes."


def _ranking(a, codigo: str) -> list[dict]:
    c = st.session_state.get(CACHE)
    if c and c["email"] == a.email and c["codigo"] == codigo and (_agora() - c["t"]).total_seconds() < TTL_S:
        return c["itens"]
    itens = JL.montar(banco.edu_liga_ranking(a, codigo), JL.semana_atual())
    st.session_state[CACHE] = {"email": a.email, "codigo": codigo, "t": _agora(), "itens": itens}
    return itens


def secao(prog) -> None:
    st.markdown("#### Liga de estudo (opcional)")
    st.caption("Um placar só de estudo entre amigos da sua liga da Competição. Mostra apenas seu apelido e o XP da semana (segunda a domingo). "
               "Não mostra operações, retorno nem risco. Fica desligado até você ativar, e você pode desligar quando quiser.")
    a = _ator()
    if not a:
        st.info("Entre na sua conta para usar a liga de estudo. A Jornada continua funcionando normalmente sem ela.")
        return
    try:
        ctx = _contexto(a)
    except Exception as e:
        banco.registrar_erro("jornada_liga_app.contexto", e)
        st.info("A liga de estudo está indisponível agora. A Jornada continua normal.")
        return
    if not ctx["ligas"]:
        st.info("Você ainda não está em nenhuma liga de amigos. Crie ou entre em uma na página Competição (com o código de convite) e volte aqui.")
        return
    aviso = st.session_state.pop("jor_liga_aviso", None)
    if aviso:
        st.warning(aviso)
    if "jor_liga_on" not in st.session_state or st.session_state.get("jor_liga_dono") != a.email:
        st.session_state["jor_liga_on"] = ctx["doc"]["ligado"]
        st.session_state["jor_liga_dono"] = a.email
    st.toggle("Mostrar meu XP de estudo nas minhas ligas", key="jor_liga_on", on_change=_mudar, args=(a, prog, ctx))
    if not ctx["doc"]["ligado"] and not st.session_state.get("jor_liga_on"):
        return
    if not JL.pode_participar(ctx["apelido"])[0]:
        st.info(JL.pode_participar(ctx["apelido"])[1])
        return
    try:
        _publicar(a, prog, ctx)
        codigos = list(ctx["ligas"])
        cod = codigos[0] if len(codigos) == 1 else st.selectbox("Liga", codigos, format_func=lambda c: ctx["ligas"][c], key="jor_liga_sel")
        itens = _ranking(a, cod)
    except Exception as e:
        banco.registrar_erro("jornada_liga_app.ranking", e)
        st.info("Não consegui carregar o ranking agora. Tente de novo em instantes.")
        return
    st.caption(html.escape(JL.texto_posicao(itens)))
    if itens:
        from design import componentes as DC
        st.markdown(DC.lista_ranking([{"pos": x["pos"], "nome": x["apelido"], "valor": f"{x['xp']} XP", "sub": "na semana", "tom": 1 if x["xp"] else 0,
                                       "voce": bool(x["eu"])} for x in itens], medalhas=True), unsafe_allow_html=True)
    st.caption("Só aparecem membros da liga que também ligaram esta opção. O placar mede estudo, não desempenho de investimento.")
