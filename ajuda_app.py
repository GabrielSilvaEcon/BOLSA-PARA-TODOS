"""Sistema de aprendizado na tela: introdução do primeiro acesso, tutorial de cada página e Central de Ajuda.

O conteúdo vem de tutoriais.py e os termos, do glossário central (mesma base do resto do app). Nada consulta API.
O progresso fica na conta (prefs["ajuda"]), por pessoa, e permite retomar de onde parou. Nada abre sozinho
depois da introdução do primeiro acesso, e nenhum tutorial altera carteira, dados ou configurações.
"""
from __future__ import annotations

import streamlit as st

import experiencia_app as EA
import glossario_app
import prefs as P
import tutoriais as T
import usuarios

ROT_BOTAO = "Como utilizar esta página?"


# ------------------------------------------------------------------ progresso (na conta)
def _ajuda() -> dict:
    return P.normalizar(st.session_state.get("prefs"))["ajuda"]


def _gravar(novo: dict, agora: bool = True) -> None:
    st.session_state["prefs"] = P.normalizar({**P.normalizar(st.session_state.get("prefs")), "ajuda": novo})
    if not agora:
        return
    try:
        usuarios.salvar()
    except Exception:
        pass


def progresso(url: str) -> dict:
    return _ajuda()["tuts"].get(url, {"passo": 0, "feito": False})


def registrar(url: str, passo: int, feito: bool | None = None, gravar_agora: bool = True) -> None:
    """Atualiza o progresso. Em cliques de Avançar/Voltar só a sessão muda (rápido); a conta é gravada no fim da próxima execução da página."""
    a = _ajuda()
    atual = a["tuts"].get(url, {"passo": 0, "feito": False})
    a["tuts"][url] = {"passo": max(0, passo), "feito": atual["feito"] if feito is None else feito}
    _gravar(a, gravar_agora)


def reiniciar(url: str) -> None:
    a = _ajuda()
    a["tuts"].pop(url, None)
    _gravar(a)
    st.session_state.pop(f"aj_passo_{url}", None)


def definir_intro(estado: str) -> None:
    a = _ajuda()
    a["intro"] = estado
    _gravar(a)
    st.session_state["aj_intro_i"] = 0


def status(url: str) -> str:
    p = progresso(url)
    n = len(T.get(url)["etapas"]) if T.get(url) else 0
    if p["feito"]:
        return "Concluído"
    if p["passo"] > 0:
        return f"Em andamento · etapa {min(p['passo'] + 1, n)} de {n}"
    return "Não iniciado"


# ------------------------------------------------------------------ uma etapa (mesmo visual na introdução e nos tutoriais)
def mapa_html(regiao: str, onde: str = "") -> str:
    """Mini-mapa da tela com a parte da etapa em destaque (brilho e contorno): mostra ONDE olhar sem depender da janela cobrir a página."""
    cor, base, linha = "#8B6CFF", "#1B1442", "rgba(189,181,230,.28)"

    def bloco(chave: str, rotulo: str, extra: str = "") -> str:
        on = chave == regiao
        est = (f"background:{cor};border:2px solid #FFFFFF;box-shadow:0 0 0 3px {cor}66,0 0 18px {cor};" if on
               else f"background:{base};border:1px dashed {linha};")
        return (f"<div style='{est}border-radius:8px;display:flex;align-items:center;justify-content:center;text-align:center;{extra}'>"
                f"<span style='color:#FFFFFF !important;-webkit-text-fill-color:#FFFFFF;font-size:.78rem;font-weight:{800 if on else 500};opacity:{1 if on else .75}'>{rotulo}</span></div>")
    grade = (f"<div style='display:grid;grid-template-columns:22% 1fr;grid-template-rows:34px 30px 54px 54px;gap:6px;height:190px'>"
             + bloco("menu", "Menu lateral", "grid-row:1 / span 4;")
             + bloco("topo", "Topo da página")
             + bloco("abas", "Abas")
             + bloco("busca", "Busca")
             + bloco("cartoes", "Cartões e resultados")
             + "</div>")
    dica = "" if regiao != "conteudo" else "<div style='color:#BDB5E6 !important;-webkit-text-fill-color:#BDB5E6;font-size:.78rem;margin-top:4px'>Esta etapa fala da tela como um todo.</div>"
    return (f"<div style='margin:8px 0;padding:10px 12px;border-radius:14px;border:1px solid {linha};background:#110C2E'>"
            f"<div style='color:#C5B3FF !important;-webkit-text-fill-color:#C5B3FF;font-weight:800;font-size:.84rem;margin-bottom:6px'>Onde olhar na tela</div>{grade}{dica}</div>")


def render_etapa(e: dict, i: int, n: int, modo: str, chave: str) -> None:
    st.progress((i + 1) / n, text=f"Etapa {i + 1} de {n}")
    st.markdown(f"### {e['titulo']}")
    with st.container(border=True):
        st.markdown(f"**O que é**\n\n{e['o_que']}")
    with st.container(border=True):
        st.markdown(f"**Como usar**\n\n{e['como']}")
        if e.get("onde"):
            st.caption(f":material/near_me: Onde fica: {e['onde']}")
    if e.get("onde"):
        st.markdown(mapa_html(T.regiao(e["onde"]), e["onde"]), unsafe_allow_html=True)
    extra = e["ini"] if modo == "iniciante" else (e["avanc"] if modo == "avancado" else "")
    if extra:
        st.info(extra, icon=":material/lightbulb:")
    if e.get("exemplo"):
        st.caption("Exemplo ilustrativo (números inventados, não são dados do mercado): " + e["exemplo"])
    if e.get("cuidado"):
        st.warning(e["cuidado"], icon=":material/warning:")
    if e.get("termos"):
        with st.expander("Termos desta etapa", icon=":material/help:"):
            for t in e["termos"]:
                with st.container(border=True):
                    glossario_app.mostrar_termo(t, modo)
    outros = [(r, e[c]) for nv, r, c in (("iniciante", "Iniciante", "ini"), ("avancado", "Avançado", "avanc")) if nv != modo and e.get(c)]
    if outros:
        with st.expander("Ver em outro nível", icon=":material/layers:"):
            for r, t in outros:
                st.markdown(f"**{r}:** {t}")


# ------------------------------------------------------------------ tutorial de uma página (janela)
def _ir(url: str, delta: int, n: int) -> None:
    i = max(0, min(n - 1, st.session_state.get(f"aj_passo_{url}", 0) + delta))
    st.session_state[f"aj_passo_{url}"] = i
    registrar(url, i, gravar_agora=False)


def _concluir(url: str, n: int) -> None:
    registrar(url, 0, True)
    st.session_state.pop(f"aj_passo_{url}", None)
    st.session_state["aj_fechar"] = True


_dialog = getattr(st, "dialog", None) or (lambda *a, **k: (lambda f: f))     # st.dialog existe no Streamlit real (>= 1.34)


@_dialog("Como utilizar esta página", width="large")
def _dialogo(url: str) -> None:
    t = T.get(url)
    if not t:
        st.write("Esta página ainda não tem tutorial.")
        return
    n = len(t["etapas"])
    if f"aj_passo_{url}" not in st.session_state:
        p = progresso(url)
        st.session_state[f"aj_passo_{url}"] = 0 if p["feito"] else min(p["passo"], n - 1)
    i = min(st.session_state[f"aj_passo_{url}"], n - 1)
    st.caption(t["titulo"])
    render_etapa(t["etapas"][i], i, n, EA.modo(), f"d_{url}")
    c1, c2, c3 = st.columns(3)
    c1.button("Voltar", key=f"aj_v_{url}", icon=":material/arrow_back:", disabled=i == 0, on_click=_ir, args=(url, -1, n), width="stretch")
    if i < n - 1:
        c2.button("Avançar", key=f"aj_a_{url}", icon=":material/arrow_forward:", type="primary", on_click=_ir, args=(url, 1, n), width="stretch")
    else:
        c2.button("Concluir", key=f"aj_c_{url}", icon=":material/check:", type="primary", on_click=_concluir, args=(url, n), width="stretch")
    if c3.button("Fechar", key=f"aj_f_{url}", icon=":material/close:", width="stretch"):
        st.rerun()
    if st.session_state.pop("aj_fechar", False):
        st.rerun()


def botao(url: str) -> None:
    """Botão padrão no topo de toda página com tutorial. Só abre quando a pessoa toca; nunca sozinho."""
    if not T.existe(url):
        return
    _, c = st.columns([3, 2], vertical_alignment="center")
    p = progresso(url)
    rot = ROT_BOTAO + (" ✓" if p["feito"] else "")
    if c.button(rot, key=f"aj_btn_{url}", icon=":material/help:", width="stretch"):
        _dialogo(url)


# ------------------------------------------------------------------ introdução do primeiro acesso (no Início, depois de escolher o nível)
def _intro_ir(delta: int) -> None:
    n = len(T.INTRO)
    st.session_state["aj_intro_i"] = max(0, min(n - 1, st.session_state.get("aj_intro_i", 0) + delta))


def _intro_fim(estado: str) -> None:
    definir_intro(estado)
    st.rerun()


@_dialog("Introdução rápida ao Bússola B3", width="large")
def _dialogo_intro() -> None:
    n = len(T.INTRO)
    i = min(st.session_state.get("aj_intro_i", 0), n - 1)
    render_etapa(T.INTRO[i], i, n, EA.modo(), "intro")
    c1, c2, c3 = st.columns(3)
    c1.button("Voltar", key="aj_intro_v", icon=":material/arrow_back:", disabled=i == 0, on_click=_intro_ir, args=(-1,), width="stretch")
    if i < n - 1:
        c2.button("Avançar", key="aj_intro_a", icon=":material/arrow_forward:", type="primary", on_click=_intro_ir, args=(1,), width="stretch")
    else:
        if c2.button("Concluir", key="aj_intro_c", icon=":material/check:", type="primary", width="stretch"):
            _intro_fim("feita")
    if c3.button("Pular", key="aj_intro_p", icon=":material/close:", width="stretch"):
        _intro_fim("pulada")
    st.caption("Você pode rever esta introdução quando quiser em Ajuda > Meu aprendizado.")


def introducao(forcar: bool = False) -> bool:
    """Introdução rápida em JANELA própria, aberta uma única vez (depois da escolha do nível). Fechar no X também conta como vista:
    ela não volta sozinha. Para rever: Ajuda > Meu aprendizado. Devolve True se a janela foi aberta agora."""
    if not forcar and _ajuda()["intro"] != "pendente":
        return False
    st.session_state.setdefault("aj_intro_i", 0)
    try:
        a = _ajuda()
        a["intro"] = "vista"                       # marcada ANTES de abrir: se a pessoa fechar no X, não reabre no próximo Início
        _gravar(a)
    except Exception:
        pass
    _dialogo_intro()
    return True


# ------------------------------------------------------------------ Central de Ajuda
def _linha(url: str, chave: str) -> None:
    t = T.get(url)
    c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
    c1.markdown(f"**{t['titulo']}**  \n{status(url)}")
    if c2.button("Abrir" if not progresso(url)["feito"] and progresso(url)["passo"] == 0 else ("Rever" if progresso(url)["feito"] else "Continuar"),
                 key=f"aj_{chave}_{url}", width="stretch"):
        if progresso(url)["feito"]:
            reiniciar(url)
        _dialogo(url)


def tutoriais_da_central() -> None:
    q = st.text_input("Buscar tutorial", key="aj_busca", placeholder="Ex.: dividendos, FII, carteira, risco", max_chars=60)
    achados = set(T.buscar(q))
    if not achados:
        st.info("Nenhum tutorial encontrado. Tente outra palavra.")
        return
    for cat, urls in T.por_categoria().items():
        urls = [u for u in urls if u in achados]
        if not urls:
            continue
        with st.expander(f"{cat} ({len(urls)})", expanded=bool(q)):
            for u in urls:
                _linha(u, "t")


def meu_aprendizado(pagina_inicio=None) -> None:
    a = _ajuda()
    total = len(T.TUTORIAIS)
    feitos = [u for u in T.TUTORIAIS if a["tuts"].get(u, {}).get("feito")]
    andamento = [u for u in T.TUTORIAIS if u in a["tuts"] and not a["tuts"][u]["feito"] and a["tuts"][u]["passo"] > 0]
    st.progress(len(feitos) / total if total else 0, text=f"{len(feitos)} de {total} tutoriais concluídos")
    st.caption("Concluir tutoriais é opcional. Seu progresso fica salvo na sua conta.")
    if andamento:
        st.markdown("**Continue de onde parou**")
        for u in andamento:
            _linha(u, "and")
    if feitos:
        with st.expander(f"Concluídos ({len(feitos)})"):
            for u in feitos:
                _linha(u, "ok")
    if not andamento and not feitos:
        st.info("Você ainda não abriu nenhum tutorial. Em qualquer página, toque em 'Como utilizar esta página?'.")
    st.markdown("**Introdução ao Bússola B3**")
    st.caption({"pendente": "Ainda não vista.", "vista": "Já foi aberta uma vez.", "feita": "Concluída.", "pulada": "Foi pulada."}[a["intro"]])
    if st.button("Rever a introdução", key="aj_rever_intro", icon=":material/replay:"):
        definir_intro("pendente")
        if pagina_inicio is not None:
            st.switch_page(pagina_inicio)
        else:
            st.info("Abra o Início para rever a introdução.")
