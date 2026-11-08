"""Etapa 3 — Player da lição (estilo Duolingo): um exercício por vez, verificação, feedback e tela final com XP.

Fluxo (st.session_state):
  jor_sessao   sessão em andamento (jornada.iniciar_sessao)
  jor_fase     "pergunta" -> "feedback" -> (próxima pergunta ... ) -> "fim"
  jor_ultimo   {"ex": id, "ok": bool} do exercício que acabou de ser respondido
  jor_n        contador que muda a cada pergunta (renova os widgets: ninguém herda a resposta anterior)
  jor_ord      itens já escolhidos no exercício "ordenar"
  jor_resultado  resultado da sessão, mostrado na tela final

Regras: nada bloqueia nem tira vidas. Erro volta para o fim da fila e a explicação aparece na hora. A lógica fica em jornada.py;
aqui só existe tela e o encadeamento dos passos. O progresso só é gravado ao terminar a lição (jornada.concluir_sessao).
"""
from __future__ import annotations

import html

import streamlit as st

import jornada as JO
import jornada_conteudo as J
import jornada_icones as IC

DICA = {"escolha": "Escolha a resposta certa", "completar": "Complete a frase", "vf": "Verdadeiro ou falso?",
        "ordenar": "Toque nos itens na ordem certa", "pares": "Ligue cada item ao seu par"}
CHAVES = ("jor_sessao", "jor_fase", "jor_ultimo", "jor_n", "jor_ord", "jor_resultado")

CSS = """<style>
div[class*="st-key-jor_player"]{max-width:560px;margin:0 auto;}
.jor-top{display:flex;align-items:center;gap:10px;margin:2px 0 14px;}
.jor-top .nome{flex:0 0 auto;max-width:42%;font-weight:800;font-size:.82rem;color:#CFC8EE !important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;}
.jor-trilho{flex:1;height:14px;background:#2A2060;border-radius:99px;overflow:hidden;}
.jor-trilho i{display:block;height:100%;background:linear-gradient(90deg,#2DD4A0,#6CF0C8);border-radius:99px;transition:width .35s;}
.jor-dica{font-size:.78rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#C5B3FF !important;margin:4px 0 6px;}
.jor-q{font-weight:900;font-size:1.28rem;line-height:1.35;color:#F6F3FF !important;margin:0 0 14px;word-break:break-word;}
.jor-q .lacuna{display:inline-block;min-width:64px;border-bottom:3px solid #C5B3FF;margin:0 4px;}
.jor-chips{display:flex;flex-wrap:wrap;gap:8px;min-height:50px;padding:10px;border:2px dashed #3D3182;border-radius:14px;margin:0 0 12px;}
.jor-chip{background:#8B6CFF;color:#fff !important;font-weight:800;font-size:.9rem;border-radius:12px;padding:8px 12px;box-shadow:0 3px 0 #5B3FD6;}
.jor-chip b{opacity:.75;margin-right:6px;}
.jor-vazio{color:#8F86C7 !important;font-size:.9rem;align-self:center;}
.jor-par{font-weight:800;color:#F6F3FF !important;margin:10px 0 4px;}
.jor-fb{border-radius:16px;padding:14px 16px;margin:10px 0 14px;}
.jor-fb.ok{background:#0F3329;border:2px solid #2DD4A0;} .jor-fb.err{background:#3A1630;border:2px solid #FF6B8A;}
.jor-fb .t{font-weight:900;font-size:1.1rem;} .jor-fb.ok .t{color:#5FF0C0 !important;} .jor-fb.err .t{color:#FF9DB3 !important;}
.jor-fb .c{margin-top:6px;color:#EDE9FF !important;font-size:.95rem;line-height:1.45;}
.jor-fb .d{margin-top:8px;color:#CFC8EE !important;font-size:.85rem;}
.jor-fim{text-align:center;padding:10px 0 4px;}
.jor-fim .medalha{width:96px;height:96px;border-radius:50%;margin:8px auto 12px;display:flex;align-items:center;justify-content:center;background:#FFC94D;box-shadow:0 7px 0 #B98A00;}
.jor-fim .medalha img{width:52px;height:52px;display:block;}
.jor-fim h2{margin:0 0 4px;color:#F6F3FF !important;font-size:1.5rem;font-weight:900;}
.jor-fim p{margin:0;color:#CFC8EE !important;}
.jor-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:16px 0;}
.jor-kpi{border-radius:14px;padding:10px 6px;background:#1B1442;border:2px solid #3D3182;}
.jor-kpi .v{font-weight:900;font-size:1.25rem;color:#F6F3FF !important;} .jor-kpi .l{font-size:.72rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:#BDB5E6 !important;}
.jor-kpi.xp{border-color:#FFC94D;} .jor-kpi.xp .v{color:#FFC94D !important;} .jor-kpi.ac{border-color:#2DD4A0;} .jor-kpi.ac .v{color:#2DD4A0 !important;}
.jor-kpi.of{border-color:#FF9B3D;} .jor-kpi.of .v{color:#FF9B3D !important;}
.jor-meta{margin:0 0 12px;padding:9px 12px;border-radius:12px;background:#0F3329;border:1px solid #2DD4A0;color:#5FF0C0 !important;font-weight:800;font-size:.9rem;}
/* opções como cartões */
div[class*="st-key-jor_r_"] label{width:100%;background:#1B1442;border:2px solid #3D3182;border-radius:14px;padding:12px 14px;margin:0 0 8px;cursor:pointer;}
div[class*="st-key-jor_r_"] label:hover{border-color:#8B6CFF;}
div[class*="st-key-jor_r_"] label:has(input:checked){border-color:#8B6CFF;background:#2A2060;}
div[class*="st-key-jor_oi_"] button{width:100%;border-radius:14px;border:2px solid #3D3182;background:#1B1442;padding:12px 14px;}
div[class*="st-key-jor_oi_"] button:hover{border-color:#8B6CFF;}
</style>"""


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _ss():
    return st.session_state


# ------------------------------------------------------------------ pedaços de HTML (puros, testáveis sem Streamlit)
def html_barra(pct: float, nome: str = "") -> str:
    pct = max(0.0, min(1.0, float(pct)))
    return f"<div class='jor-top'><div class='nome'>{_e(nome)}</div><div class='jor-trilho'><i style='width:{pct * 100:.0f}%'></i></div></div>"


def html_pergunta(ex: dict) -> str:
    texto = _e(ex["pergunta"])
    if ex["tipo"] == "completar":
        texto = texto.replace("___", "<span class='lacuna'></span>")
    return f"<div class='jor-dica'>{_e(DICA[ex['tipo']])}</div><div class='jor-q'>{texto}</div>"


def html_chips(escolhidos: list[str], total: int) -> str:
    if not escolhidos:
        return f"<div class='jor-chips'><span class='jor-vazio'>Toque nos itens abaixo, do primeiro ao último ({total}).</span></div>"
    return "<div class='jor-chips'>" + "".join(f"<span class='jor-chip'><b>{i}</b>{_e(x)}</span>" for i, x in enumerate(escolhidos, 1)) + "</div>"


def html_feedback(ok: bool, ex: dict) -> str:
    if ok:
        return f"<div class='jor-fb ok'><div class='t'>Correto!</div><div class='c'>{_e(ex['explicacao'])}</div></div>"
    return (f"<div class='jor-fb err'><div class='t'>Não foi dessa vez</div>"
            f"<div class='c'><b>Resposta certa:</b> {_e(JO.resposta_certa_texto(ex))}<br>{_e(ex['explicacao'])}</div>"
            f"<div class='d'>Esta pergunta volta no fim da lição para você tentar de novo.</div></div>")


def html_fim(r: dict) -> str:
    if r.get("revisao"):
        titulo, sub = "Revisão concluída!", "Você revisou o que tinha errado antes."
    elif r.get("perfeita"):
        titulo, sub = "Lição perfeita!", "Nenhum erro de primeira. Bônus de XP garantido."
    else:
        titulo, sub = "Lição concluída!", "Os erros ficam na sua lista de revisão."
    of = int(r.get("ofensiva", 0))
    meta = "<div class='jor-meta'>Meta de hoje batida!</div>" if r.get("meta_atingida") else ""
    return (f"<div class='jor-fim'><div class='medalha'><img src='{IC.uri('estrela', '#5A3B00')}' alt=''></div><h2>{_e(titulo)}</h2><p>{_e(sub)}</p></div>"
            f"<div class='jor-kpis'><div class='jor-kpi xp'><div class='v'>+{int(r['xp'])}</div><div class='l'>XP</div></div>"
            f"<div class='jor-kpi ac'><div class='v'>{int(r['acertos_primeira'])}/{int(r['total'])}</div><div class='l'>De primeira</div></div>"
            f"<div class='jor-kpi of'><div class='v'>{of}</div><div class='l'>{'Dia seguido' if of == 1 else 'Dias seguidos'}</div></div></div>{meta}")


# ------------------------------------------------------------------ ações (callbacks)
def iniciar(licao_id: str) -> None:
    """Começa uma lição: zera o estado do player e guarda a sessão. Id inexistente não faz nada."""
    s = JO.iniciar_sessao(licao_id)
    if s:
        sair()
        _ss().update({"jor_sessao": s, "jor_fase": "pergunta", "jor_n": 0, "jor_ord": []})


def iniciar_revisao(p: dict) -> None:
    """Começa uma revisão com os exercícios errados antes. Sem erros, não faz nada."""
    s = JO.iniciar_revisao(p)
    if s:
        sair()
        _ss().update({"jor_sessao": s, "jor_fase": "pergunta", "jor_n": 0, "jor_ord": []})


def sair() -> None:
    for k in CHAVES:
        _ss().pop(k, None)


def _verificar(eid: str, resposta) -> None:
    s = _ss().get("jor_sessao")
    if not s or JO.exercicio_atual(s) is None or JO.exercicio_atual(s)["id"] != eid:      # clique atrasado/duplo: ignora
        return
    ok, s2 = JO.responder(s, resposta)
    _ss().update({"jor_sessao": s2, "jor_fase": "feedback", "jor_ultimo": {"ex": eid, "ok": ok}})


def _continuar(prog, set_prog) -> None:
    s = _ss().get("jor_sessao")
    if not s:
        return
    if JO.terminada(s):
        p, r = JO.concluir_sessao(prog(), s)
        set_prog(p)
        _ss().update({"jor_resultado": r, "jor_fase": "fim"})
    else:
        _ss().update({"jor_fase": "pergunta", "jor_n": _ss().get("jor_n", 0) + 1, "jor_ord": []})


def _add_item(item: str) -> None:
    ordem = list(_ss().get("jor_ord") or [])
    if item not in ordem:
        ordem.append(item)
    _ss()["jor_ord"] = ordem


def _desfazer() -> None:
    _ss()["jor_ord"] = list(_ss().get("jor_ord") or [])[:-1]


# ------------------------------------------------------------------ entradas por tipo (devolvem a resposta pronta ou None se incompleta)
def _entrada(ex: dict, n: int):
    t, eid = ex["tipo"], ex["id"]
    if t in ("escolha", "completar"):
        esc = st.radio("Resposta", ex["opcoes"], index=None, key=f"jor_r_{eid}_{n}", label_visibility="collapsed")
        return None if esc is None else ex["opcoes"].index(esc)
    if t == "vf":
        esc = st.radio("Resposta", ["Verdadeiro", "Falso"], index=None, key=f"jor_r_{eid}_{n}", label_visibility="collapsed")
        return None if esc is None else esc == "Verdadeiro"
    if t == "ordenar":
        return _entrada_ordenar(ex, n)
    return _entrada_pares(ex, n)


def _entrada_ordenar(ex: dict, n: int):
    ordem = list(_ss().get("jor_ord") or [])
    todos = JO.embaralhar_itens(ex)
    st.markdown(html_chips(ordem, len(todos)), unsafe_allow_html=True)
    for i, item in enumerate(todos):
        if item not in ordem:
            st.button(item, key=f"jor_oi_{n}_{i}", on_click=_add_item, args=(item,), width="stretch")
    if ordem:
        st.button("Desfazer último", key=f"jor_od_{n}", on_click=_desfazer, icon=":material/undo:")
    return ordem if len(ordem) == len(todos) else None


def _entrada_pares(ex: dict, n: int):
    direitas = JO.embaralhar_pares(ex)
    escolhas = []
    for i, (a, _b) in enumerate(ex["pares"]):
        st.markdown(f"<div class='jor-par'>{_e(a)}</div>", unsafe_allow_html=True)
        escolhas.append(st.selectbox(a, direitas, index=None, placeholder="Escolha o par", key=f"jor_pa_{ex['id']}_{n}_{i}", label_visibility="collapsed"))
    if any(e is None for e in escolhas):
        return None
    return {a: e for (a, _b), e in zip(ex["pares"], escolhas)}


# ------------------------------------------------------------------ telas
def _nome_sessao(s: dict) -> str:
    return J.LICAO_POR_ID[s["licao"]]["titulo"] if s.get("licao") in J.LICAO_POR_ID else "Revisão"


def tela(prog, set_prog) -> None:
    """Desenha a fase atual. `prog` devolve o progresso; `set_prog` grava (só chamado ao terminar a lição)."""
    st.markdown(CSS, unsafe_allow_html=True)
    s, fase = _ss().get("jor_sessao"), _ss().get("jor_fase", "pergunta")
    if not s:
        return
    with st.container(key="jor_player"):
        if fase == "fim":
            r = _ss().get("jor_resultado")
            if not r:
                sair()
                st.rerun()
                return
            st.markdown(html_fim(r), unsafe_allow_html=True)
            st.button("Continuar", key="jor_sf", type="primary", width="stretch", on_click=sair)
            return
        st.markdown(html_barra(JO.progresso_sessao(s), _nome_sessao(s)), unsafe_allow_html=True)
        if fase == "feedback":
            ult = _ss().get("jor_ultimo") or {}
            ex = J.EX_POR_ID.get(ult.get("ex"))
            if ex is None:
                sair()
                st.rerun()
                return
            st.markdown(html_pergunta(ex), unsafe_allow_html=True)
            st.markdown(html_feedback(bool(ult.get("ok")), ex), unsafe_allow_html=True)
            st.button("Continuar", key="jor_sc", type="primary", width="stretch", on_click=_continuar, args=(prog, set_prog))
            return
        ex = JO.exercicio_atual(s)
        if ex is None:                                       # sessão sem exercício restante: fecha direto
            _continuar(prog, set_prog)
            st.rerun()
            return
        n = _ss().get("jor_n", 0)
        st.markdown(html_pergunta(ex), unsafe_allow_html=True)
        resposta = _entrada(ex, n)
        st.button("Verificar", key="jor_sv", type="primary", width="stretch", disabled=resposta is None, on_click=_verificar, args=(ex["id"], resposta))
        st.button("Sair da lição", key="jor_ss", on_click=sair, icon=":material/close:")
