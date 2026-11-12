"""Passo 24 — Página "Educação financeira": painel, trilhas, biblioteca, prática (quiz), estudo com ativos reais, simulações, professor com IA e glossário.

Regras desta tela:
- Todo o conteúdo é aberto a todos; os três modos (iniciante/intermediário/avançado) mudam só a apresentação (modos.py), não há planos nem preços.
- O progresso fica em st.session_state["edu_progresso"] e é gravado no perfil da conta (usuarios.CHAVES): individual e isolado. Visitante estuda, mas nada é salvo.
- Dados reais vêm das fontes do app, com fonte e data; o que não existe aparece como "indisponível". Exemplos numéricos fora disso são sempre marcados como HIPOTÉTICOS.
- Nada aqui recomenda compra ou venda, nem usa pontos para incentivar operações.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

import streamlit as st
import secoes
import estilo_app as ES

import conta_app as C
import edu_conteudo as E
import educacao as ED
import jornada_app
import modos
import paleta as PL
import tema
import usuarios

_PAGINAS: dict = {}
_COR_NIVEL = {"iniciante": "ok", "intermediario": "info", "avancado": "aviso"}

CSS = f"""<style>
.ed-card{{background:linear-gradient(145deg,#1E1650,#160F36);border:1px solid #3D3182;border-left:5px solid {PL.INFO};border-radius:16px;padding:12px 14px;margin:8px 0;color:#EDE9FF !important;}}
.ed-card.ok{{border-left-color:{PL.BOM};}} .ed-card.aviso{{border-left-color:{PL.OURO};}} .ed-card.feita{{opacity:.85;}}
.ed-t{{font-weight:800;font-size:1.02rem;color:#F6F3FF !important;line-height:1.35;word-break:break-word;}}
.ed-s{{margin-top:4px;color:#CFC8EE !important;font-size:.9rem;line-height:1.45;word-break:break-word;}}
.ed-barra{{height:9px;background:#2A2060;border-radius:99px;overflow:hidden;margin-top:8px;}} .ed-barra i{{display:block;height:100%;background:linear-gradient(90deg,#7C5CFF,#2DD4A0);}}
.ed-ind{{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:8px;margin:6px 0 10px;}}
.ed-ind div{{background:#1A1342;border:1px solid #382C78;border-radius:12px;padding:9px 11px;color:#EDE9FF !important;font-size:.9rem;line-height:1.45;}}
.ed-ind b{{display:block;color:#C5B3FF !important;font-size:.72rem;text-transform:uppercase;letter-spacing:.05em;margin-bottom:2px;}}
.ed-cert{{border:2px solid {PL.OURO};border-radius:16px;padding:14px;margin:8px 0;background:linear-gradient(145deg,#2B2150,#1A1342);color:#F6F3FF !important;}}
</style>"""


def registrar_paginas(paginas: dict) -> None:
    _PAGINAS.update({k: v for k, v in paginas.items() if v is not None})



def _br(v: float, casas: int = 1, sinal: bool = False) -> str:
    """Número no padrão brasileiro: milhar com ponto e decimal com vírgula."""
    t = f"{v:{'+' if sinal else ''},.{casas}f}"
    return t.replace(",", "§").replace(".", ",").replace("§", ".")


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def _ss():
    return st.session_state


# ------------------------------------------------------------------ progresso (sessão ⇄ perfil)
def prog() -> dict:
    p = ED.normalizar(_ss().get("edu_progresso"))
    _ss()["edu_progresso"] = p
    return p


def _set(p: dict) -> None:
    _ss()["edu_progresso"] = p


def modo() -> str:
    return prog()["modo"]


def _salvo() -> bool:
    return bool(usuarios.usuario())


def _barra(pct: float) -> str:
    return f"<div class='ed-barra'><i style='width:{max(0.0, min(1.0, pct)) * 100:.0f}%'></i></div>"


def _card(titulo: str, sub: str = "", cls: str = "", extra: str = "") -> str:
    s = f"<div class='ed-s'>{_e(sub)}</div>" if sub else ""
    return f"<div class='ed-card {cls}'><div class='ed-t'>{_e(titulo)}</div>{s}{extra}</div>"


# ------------------------------------------------------------------ ações (callbacks)
def _ler_aula(aula_id: str) -> None:
    p = ED.registrar_aula(prog(), aula_id)
    p, novos = ED.atualizar_certificados(p)
    _set(p)
    if novos:
        _ss()["_edu_cert_novo"] = novos


def _abrir_aula(aula_id: str) -> None:
    _ss()["edu_aula"] = aula_id


def _fechar_aula() -> None:
    _ss().pop("edu_aula", None)


def _iniciar_trilha(tid: str) -> None:
    _set(ED.iniciar_trilha(prog(), tid))


def _mudar_modo() -> None:
    p = prog()
    p["modo"] = modos.modo_valido(_ss().get("edu_modo_sel"))
    _set(p)
    try:                                   # o nível de leitura é o mesmo modo de experiência do app inteiro
        import experiencia_app
        experiencia_app.aplicar(p["modo"])
    except Exception:
        pass


def _responder(qid: str, chave_radio: str) -> None:
    q = E.QUIZ_POR_ID[qid]
    esc = _ss().get(chave_radio)
    if esc is None:
        return
    ok, p = ED.responder(prog(), qid, q["opcoes"].index(esc))
    p, novos = ED.atualizar_certificados(p)
    _set(p)
    _ss().setdefault("_edu_res", {})[qid] = ok
    if novos:
        _ss()["_edu_cert_novo"] = novos


# ------------------------------------------------------------------ componentes
def _fontes_html(aula: dict) -> str:
    fs = ED.fontes_da_aula(aula)
    if not fs:
        return ""
    return " · ".join(f"<a href='{_e(u)}' target='_blank' rel='noopener noreferrer'>{_e(n)}</a>" for n, u in fs)


def _quiz(qs: list[dict], prefixo: str) -> None:
    if not qs:
        st.markdown(C._msg("Esta aula ainda não tem perguntas.", "info"), unsafe_allow_html=True)
        return
    p = prog()
    for q in qs:
        ch = f"{prefixo}_{q['id']}"
        feito = p["quiz"].get(q["id"])
        selo = ""
        if feito:
            selo = C._chip("Acertou" if feito.get("ok") else "Revisar", "ok" if feito.get("ok") else "aviso")
        with st.container(border=True):
            st.markdown(f"**{q['pergunta']}**  \n{selo}", unsafe_allow_html=True)
            st.radio("Escolha uma resposta", q["opcoes"], index=None, key=ch, label_visibility="collapsed")
            st.button("Responder", key=f"{ch}_b", on_click=_responder, args=(q["id"], ch))
            res = _ss().get("_edu_res", {}).get(q["id"])
            if res is not None:
                st.markdown(C._msg(("Correto! " if res else "Ainda não. ") + q["explicacao"], "ok" if res else "aviso"), unsafe_allow_html=True)


def _aula_card(a: dict, p: dict, chave: str) -> None:
    lida = a["id"] in p["aulas"]
    c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
    c1.markdown(_card(("✔ " if lida else "") + a["titulo"], f"{E.ROTULO_ASSUNTO[a['assunto']]} · {modos.ROTULOS[a['dificuldade']]} · {a['min']} min",
                      "ok feita" if lida else ""), unsafe_allow_html=True)
    c2.button("Reler" if lida else "Abrir", key=f"{chave}_{a['id']}", on_click=_abrir_aula, args=(a["id"],), width="stretch")


def _ver_aula(aula_id: str) -> None:
    a = E.POR_ID[aula_id]
    p = prog()
    st.button("← Voltar", key="edu_voltar", on_click=_fechar_aula)
    st.markdown(C._titulo(a["titulo"], f"{E.ROTULO_ASSUNTO[a['assunto']]} · {modos.ROTULOS[a['dificuldade']]} · leitura de {a['min']} min · exibindo o modo {modos.ROTULOS[p['modo']]}"),
                unsafe_allow_html=True)
    with st.container(border=True):
        st.markdown(ED.texto_aula(a, p["modo"]))
        f = _fontes_html(a)
        if f:
            st.markdown(f"<div class='ed-s'>Fontes: {f}<br>Revisão do conteúdo: {E.REVISAO}.</div>", unsafe_allow_html=True)
    if a["id"] in p["aulas"]:
        st.markdown(C._msg("Aula marcada como lida.", "ok"), unsafe_allow_html=True)
    else:
        st.button("Marquei como lida", key="edu_lida", type="primary", on_click=_ler_aula, args=(a["id"],))
    rel = [E.POR_ID[r] for r in a.get("relacionadas", []) if r in E.POR_ID]
    if rel:
        st.markdown(C._titulo("Conteúdos relacionados"), unsafe_allow_html=True)
        for r in rel:
            _aula_card(r, p, "edu_rel")
    st.markdown(C._titulo("Pratique esta aula"), unsafe_allow_html=True)
    _quiz([q for q in E.QUIZ if q["aula"] == a["id"]], "edu_qa")
    _certificado_novo()


def _certificado_novo() -> None:
    novos = _ss().pop("_edu_cert_novo", None)
    for tid in novos or []:
        t = E.TRILHA_POR_ID[tid]
        st.markdown(f"<div class='ed-cert'><div class='ed-t'>🏅 Trilha concluída: {_e(t['titulo'])}</div><div class='ed-s'>Certificado interno de conclusão, de caráter educacional. "
                    "Não é certificação profissional e não mede sua capacidade de investir.</div></div>", unsafe_allow_html=True)


# ------------------------------------------------------------------ abas
def _aba_painel() -> None:
    p = prog()
    pts = ED.pontos(p)
    lidas = len(p["aulas"])
    certas = sum(1 for r in p["quiz"].values() if r.get("acertos", 0) > 0)
    sem = ED.aulas_na_semana(p)
    st.markdown(C._grade([
        C._kpi("Pontos de estudo", pts, "info", "só por estudar"),
        C._kpi("Aulas lidas", f"{lidas}/{len(E.AULAS)}", "ok"),
        C._kpi("Perguntas acertadas", f"{certas}/{len(E.QUIZ)}", "ok"),
        C._kpi("Trilhas concluídas", f"{len(p['certificados'])}/{len(E.TRILHAS)}", "info"),
        C._kpi("Meta da semana", f"{sem}/{p['meta_semana']} aulas", "ok" if sem >= p["meta_semana"] else "aviso"),
    ]), unsafe_allow_html=True)
    if not _salvo():
        st.markdown(C._msg("Você está navegando como visitante: o progresso vale só nesta sessão. Entre na sua conta para salvá-lo.", "aviso"), unsafe_allow_html=True)
    st.number_input("Meta de aulas por semana", min_value=1, max_value=21, value=int(p["meta_semana"]), key="edu_meta_in",
                    on_change=lambda: _set({**prog(), "meta_semana": int(_ss().get("edu_meta_in", 3))}))
    st.markdown(C._titulo("Sugestões para você", "Com base no que você já estudou, nas perguntas que errou e no nível escolhido."), unsafe_allow_html=True)
    for s in ED.sugerir(p, 3):
        a = E.POR_ID[s["aula"]]
        c1, c2 = st.columns([4, 1.4], vertical_alignment="center")
        c1.markdown(_card(a["titulo"], s["motivo"] + f" · {a['min']} min"), unsafe_allow_html=True)
        c2.button("Abrir", key=f"edu_sug_{a['id']}", on_click=_abrir_aula, args=(a["id"],), width="stretch")
    dif = ED.dificuldades(p)
    if dif:
        st.markdown(C._titulo("Assuntos para reforçar", "Onde as respostas mais recentes indicam dúvida. Isso orienta o estudo e não é uma nota."), unsafe_allow_html=True)
        st.markdown(C._grade([C._kpi(d["rotulo"], f"{d['acerto'] * 100:.0f}%", "aviso", f"{d['n']} perguntas") for d in dif]), unsafe_allow_html=True)
    st.markdown(C._titulo("Conquistas", "Reconhecem estudo e constância. Não há conquistas por operar nem por assumir risco."), unsafe_allow_html=True)
    st.markdown(C._grade([C._kpi(c["titulo"], "Conquistada" if c["ok"] else "A conquistar", "ok" if c["ok"] else "na", c["descricao"]) for c in ED.conquistas(p)]), unsafe_allow_html=True)
    if p["certificados"]:
        st.markdown(C._titulo("Certificados internos", "De caráter educacional, não são certificações profissionais."), unsafe_allow_html=True)
        for tid, quando in p["certificados"].items():
            t = E.TRILHA_POR_ID[tid]
            st.markdown(f"<div class='ed-cert'><div class='ed-t'>🏅 {_e(t['titulo'])}</div><div class='ed-s'>Concluída em {_e(C._fmt(quando))}. Certificado educacional interno.</div></div>", unsafe_allow_html=True)
    with st.expander("Histórico de atividades", expanded=False):
        ativ = list(reversed(p["atividade"]))[:40]
        if not ativ:
            st.markdown(C._msg("Nada por aqui ainda. Abra uma aula para começar.", "info"), unsafe_allow_html=True)
        rot = {"aula": "Aula lida", "quiz": "Pergunta respondida", "trilha": "Trilha", "ativo": "Estudo com dado real"}
        for a in ativ:
            ref = a.get("ref", "")
            nome = (E.POR_ID.get(ref) or {}).get("titulo") or (E.TRILHA_POR_ID.get(ref) or {}).get("titulo") or (
                E.POR_ID[E.QUIZ_POR_ID[ref]["aula"]]["titulo"] if ref in E.QUIZ_POR_ID else ref)
            st.markdown(C._linha(f"{rot.get(a.get('tipo'), 'Atividade')} · {nome}", C._fmt(a.get("t")), C._chip(a.get("x"), "ok" if a.get("x") in ("acerto", "concluída") else "") if a.get("x") else ""),
                        unsafe_allow_html=True)
    st.caption(E.AVISO)


def _aba_trilhas() -> None:
    p = prog()
    st.markdown(C._titulo("Trilhas de aprendizado", "Cada trilha tem aulas, perguntas e acompanhamento. Conclua todas as aulas e acerte pelo menos 70% das perguntas para o certificado interno."), unsafe_allow_html=True)
    for t in E.TRILHAS:
        pr = ED.progresso_trilha(p, t["id"])
        selo = C._chip("Concluída", "ok") if pr["concluida"] else (C._chip("Em andamento", "info") if pr["iniciada"] else C._chip("Não iniciada"))
        extra = f"<div class='ed-s'>{pr['lidas']}/{pr['aulas']} aulas · {pr['respondidas']}/{pr['perguntas']} perguntas respondidas" + (f" · acerto {pr['acerto'] * 100:.0f}%" if pr["respondidas"] else "") + f"</div>{_barra(pr['pct'])}"
        with st.expander(f"{t['icone']} {t['titulo']}  ·  {pr['pct'] * 100:.0f}%", expanded=False):
            st.markdown(selo + _card(t["titulo"], t["descricao"] + f" · nível {modos.ROTULOS[t['dificuldade']].lower()}", "ok" if pr["concluida"] else "", extra), unsafe_allow_html=True)
            if t["id"] not in p["trilhas"]:
                st.button("Iniciar trilha", key=f"edu_ini_{t['id']}", on_click=_iniciar_trilha, args=(t["id"],))
            for i, aid in enumerate(t["aulas"], 1):
                _aula_card(E.POR_ID[aid], p, f"edu_t{t['id']}_{i}")
            if pr["perguntas"]:
                st.markdown("**Perguntas da trilha**")
                _quiz(ED.perguntas_da_trilha(t), f"edu_tq_{t['id']}")


def _aba_biblioteca() -> None:
    p = prog()
    c1, c2 = st.columns(2)
    assunto = c1.selectbox("Assunto", ["Todos"] + [a[1] for a in E.ASSUNTOS], key="edu_f_ass")
    dif = c2.selectbox("Dificuldade", ["Todas"] + [modos.ROTULOS[d] for d in E.DIFICULDADES], key="edu_f_dif")
    chave_ass = next((a[0] for a in E.ASSUNTOS if a[1] == assunto), None)
    chave_dif = next((d for d in E.DIFICULDADES if modos.ROTULOS[d] == dif), None)
    aulas = ED.aulas_do_assunto(chave_ass, chave_dif)
    sem = [a for a in E.ASSUNTOS if (not chave_ass or a[0] == chave_ass) and not any(x["assunto"] == a[0] for x in E.AULAS)]
    if not aulas:
        st.markdown(C._msg("Nenhuma aula com esses filtros ainda.", "info"), unsafe_allow_html=True)
    for a in aulas:
        _aula_card(a, p, "edu_bib")
    if sem and not chave_dif:
        st.caption("Assuntos em preparação: " + ", ".join(a[1] for a in sem))


def _aba_praticar() -> None:
    st.markdown(C._titulo("Perguntas e exercícios", "Correção automática com explicação. O resultado orienta seu estudo e não mede capacidade de investir."), unsafe_allow_html=True)
    assunto = st.selectbox("Assunto", ["Todos"] + [a[1] for a in E.ASSUNTOS if any(x["assunto"] == a[0] for x in E.AULAS)], key="edu_pq_ass")
    chave = next((a[0] for a in E.ASSUNTOS if a[1] == assunto), None)
    qs = [q for q in E.QUIZ if not chave or E.POR_ID[q["aula"]]["assunto"] == chave]
    _quiz(qs, "edu_pq")
    _certificado_novo()
    st.markdown(C._titulo("Estudo de caso", "Perdas pesam mais que ganhos iguais: quanto é preciso ganhar para recuperar uma queda?"), unsafe_allow_html=True)
    q = st.slider("Queda sofrida (%)", 5, 90, value=30, key="edu_caso_q")
    need = ED.queda_e_recuperacao(q / 100) * 100
    st.markdown(C._grade([C._kpi("Queda", f"-{q}%", "aviso"), C._kpi("Ganho necessário", f"+{_br(need)}%", "info", "para voltar ao ponto de partida")]), unsafe_allow_html=True)
    st.markdown(C._msg("Exercício matemático (hipotético): por isso limitar perdas e dimensionar posições importa mais do que parece.", "info"), unsafe_allow_html=True)


# ------------------------------------------------------------------ estudo com dados reais
@st.cache_data(ttl=900, show_spinner=False)
def _fechamentos(ticker: str):
    import dados
    df, err = dados.historico_yahoo(ticker, "1y", "1d")
    if df is None or df.empty or "Close" not in df:
        return None, None, err or "Sem histórico."
    s = df["Close"].dropna()
    return [float(x) for x in s.tolist()], str(s.index[-1])[:10], None


def _indicadores_reais(tk: str) -> tuple[dict, dict | None]:
    import dados
    d = dados.buscar_yahoo(tk)
    preco = d.get("preco")
    out: dict = {}
    try:
        out["P/L"] = preco / d["lpa"] if preco and d.get("lpa") and d["lpa"] > 0 else None
        out["P/VP"] = preco / d["vpa"] if preco and d.get("vpa") and d["vpa"] > 0 else None
        out["Dividend yield"] = d["div_12m"] / preco * 100 if preco and d.get("div_12m") else None
    except Exception:
        pass
    for sig, chave in (("ROE", "roe"), ("Margem líquida", "margem_liq")):       # dados.py guarda estes dois como fração (0,30 = 30%)
        v = d.get(chave)
        out[sig] = v * 100 if isinstance(v, (int, float)) and v == v else None
    out["EBITDA"] = d.get("ev_ebitda")
    return out, d


def _bloco_indicador(sig: str, valor) -> None:
    e = ED.explicar_indicador(sig)
    if not e:
        return
    st.markdown(f"<div class='ed-card'><div class='ed-t'>{_e(sig) if e['nome'] == sig else _e(sig) + ' · ' + _e(e['nome'])}</div><div class='ed-s'><b>Neste ativo:</b> {_e(ED.ler_indicador(sig, valor))}</div></div>", unsafe_allow_html=True)
    with st.expander(f"Entenda: {sig}", expanded=False):
        _explicacao(sig, marcar=True)


def _explicacao(sig: str, marcar: bool = False) -> None:
    e = ED.explicar_indicador(sig)
    if not e:
        st.markdown(C._msg("Não encontrei esse indicador.", "info"), unsafe_allow_html=True)
        return
    if marcar:
        _set(ED.registrar_indicador_visto(prog(), e["sigla"]))
    campos = [("O que significa", "significa"), ("Como é calculado", "calculo"), ("Para que serve", "serve"), ("Como interpretar", "interpretar"),
              ("Limitações", "limites"), ("Quando é útil", "quando"), ("Erros a evitar", "erros")]
    cls = ", ".join({"acao": "ações", "fii": "FIIs", "etf": "ETFs", "cripto": "criptomoedas", "renda_fixa": "renda fixa"}.get(c, c) for c in e["classes"]) or "qualquer ativo com histórico de preços"
    st.markdown("<div class='ed-ind'>" + "".join(f"<div><b>{_e(r)}</b>{_e(e[k])}</div>" for r, k in campos) + f"<div><b>Aplica-se a</b>{_e(cls)}</div></div>", unsafe_allow_html=True)


def _aba_ativo() -> None:
    st.markdown(C._titulo("Aprender com um ativo real", "Escolha um ativo e veja o que cada número significa, com dados reais do app, fonte e data. O que faltar aparece como indisponível."), unsafe_allow_html=True)
    c1, c2 = st.columns([2, 1.4])
    tk = c1.text_input("Código do ativo", value=_ss().get("edu_tk", ""), placeholder="PETR4, HGLG11, BOVA11, BTC-USD...", key="edu_tk_in", max_chars=14).strip().upper()
    classes = {"Ação": "acao", "FII": "fii", "ETF": "etf", "Criptomoeda": "cripto"}
    padrao = "Ação"
    if tk:
        try:
            import monitor
            padrao = next((k for k, v in classes.items() if v == ("cripto" if "-" in tk and tk.endswith(("USD", "USDT", "BRL")) else monitor.classe_do_ticker(tk))), "Ação")
        except Exception:
            pass
    classe_rot = c2.selectbox("Classe", list(classes), index=list(classes).index(padrao), key=f"edu_cl_{tk}")
    classe = classes[classe_rot]
    if not tk:
        st.markdown(C._msg("Digite um código para começar. Para renda fixa, use a página de Análise de títulos (botão abaixo).", "info"), unsafe_allow_html=True)
    elif st.button("Estudar este ativo", type="primary", key="edu_estudar"):
        _ss()["edu_tk"] = tk
        _set(ED.registrar_ativo_estudado(prog()))
        _ss()["edu_estudo"] = tk
    alvo = _ss().get("edu_estudo")
    if alvo and alvo == tk:
        hoje = datetime.now(timezone.utc).strftime("%d/%m/%Y")
        if classe in ("acao", "fii", "etf"):
            with st.spinner("Buscando dados reais..."):
                ind, d = _indicadores_reais(alvo)
            if d and d.get("erro") and all(v is None for v in ind.values()):
                st.markdown(C._msg(f"Não consegui dados fundamentalistas agora ({d['erro']}). Nada foi estimado.", "aviso"), unsafe_allow_html=True)
            else:
                st.markdown(C._msg(f"Fonte: fontes de dados do app (Yahoo Finance, com fonte reserva) · consulta em {hoje}" + (f" · balanço de {d['data_balanco']}" if d and d.get("data_balanco") else ""), "info"), unsafe_allow_html=True)
                for sig in ED.indicadores_da_classe(classe):
                    if sig in ind:
                        _bloco_indicador(sig, ind[sig])
                if classe == "fii":
                    st.markdown(C._msg("Vacância e outros indicadores específicos de FIIs vêm dos relatórios gerenciais; veja a página FIIs do app. Aqui não estimamos esse número.", "info"), unsafe_allow_html=True)
        st.markdown(C._titulo("Risco observado no último ano", "Volatilidade, queda máxima e retorno do período, calculados com o histórico real."), unsafe_allow_html=True)
        precos, ultima, erro = _fechamentos(alvo)
        m = ED.metricas_risco(precos) if precos else None
        if not m:
            st.markdown(C._msg(f"Histórico indisponível ({erro or 'poucos dados'}). Nada foi estimado.", "aviso"), unsafe_allow_html=True)
        else:
            st.markdown(C._msg(f"Fonte: Yahoo Finance · último fechamento de {ultima} · {m['pontos']} dias de dados. Resultado histórico: não indica o futuro.", "info"), unsafe_allow_html=True)
            st.markdown(C._grade([C._kpi("Retorno no período", f"{_br(m['retorno'] * 100, 1, True)}%", "ok" if m["retorno"] >= 0 else "aviso"),
                                  C._kpi("Volatilidade anual", f"{_br(m['volatilidade'] * 100)}%", "info"),
                                  C._kpi("Queda máxima", f"{_br(m['drawdown'] * 100)}%", "aviso")]), unsafe_allow_html=True)
            for sig, val in (("Volatilidade", m["volatilidade"] * 100), ("Drawdown", m["drawdown"] * 100)):
                st.markdown(_card(sig, ("Oscilação anualizada de " if sig == "Volatilidade" else "Maior queda desde um topo: ") + f"{_br(abs(val))}%. Compare com outros ativos na mesma janela."), unsafe_allow_html=True)
                with st.expander(f"Entenda: {sig}", expanded=False):
                    _explicacao(sig, marcar=True)
            outro = st.text_input("Comparar o risco com outro ativo (opcional)", key="edu_tk2", max_chars=14).strip().upper()
            if outro:
                p2, u2, e2 = _fechamentos(outro)
                m2 = ED.metricas_risco(p2) if p2 else None
                if not m2:
                    st.markdown(C._msg(f"Sem histórico para {outro} ({e2 or 'poucos dados'}).", "aviso"), unsafe_allow_html=True)
                else:
                    st.markdown(C._grade([C._kpi(f"{alvo} · volatilidade", f"{_br(m['volatilidade'] * 100)}%", "info"), C._kpi(f"{outro} · volatilidade", f"{_br(m2['volatilidade'] * 100)}%", "info"),
                                          C._kpi(f"{alvo} · queda máx.", f"{_br(m['drawdown'] * 100)}%", "aviso"), C._kpi(f"{outro} · queda máx.", f"{_br(m2['drawdown'] * 100)}%", "aviso")]), unsafe_allow_html=True)
                    st.caption("Dois ativos podem render parecido e oscilar de formas muito diferentes. Fonte: Yahoo Finance, último ano.")
    st.markdown(C._titulo("Outras classes no app"), unsafe_allow_html=True)
    b1, b2, b3 = st.columns(3)
    for col, (chave, rot) in zip((b1, b2, b3), (("renda-fixa", "Renda fixa: análise de títulos"), ("fiis", "FIIs"), ("criptomoedas", "Criptomoedas"))):
        pg = _PAGINAS.get(chave)
        if pg is not None:
            col.page_link(pg, label=rot, icon=":material/open_in_new:")


def _estudo_unidade(uid: str, roteiro: dict) -> None:
    """Estudo com dado real no fim de uma unidade da Jornada (chamado por jornada_app). Mesmas fontes e regras da aba "Com ativos reais":
    dado com fonte e data, ou "indisponível"; nada é estimado. Não dá XP (XP é só por estudar lições e revisões)."""
    st.markdown(f"**{_e(roteiro['titulo'])}**")
    tk = st.text_input("Código do ativo", key=f"edu_ru_tk_{uid}", placeholder="PETR4, HGLG11, BOVA11, BTC-USD...", max_chars=14).strip().upper()
    if st.button("Estudar este ativo", key=f"edu_ru_go_{uid}", type="primary", disabled=not tk):
        _ss()[f"edu_ru_{uid}"] = tk
        _set(ED.registrar_ativo_estudado(prog()))
    alvo = _ss().get(f"edu_ru_{uid}")
    if not alvo or alvo != tk:
        st.caption(roteiro["dica"])
        return
    hoje = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    cripto = "-" in alvo and alvo.endswith(("USD", "USDT", "BRL"))
    classe = "cripto" if cripto else None
    if not cripto:
        try:
            import monitor
            classe = monitor.classe_do_ticker(alvo)
        except Exception:
            classe = "acao"
    if roteiro["indicadores"] and classe in ("acao", "fii", "etf"):
        with st.spinner("Buscando dados reais..."):
            ind, d = _indicadores_reais(alvo)
        if d and d.get("erro") and all(v is None for v in ind.values()):
            st.markdown(C._msg(f"Não consegui dados fundamentalistas agora ({d['erro']}). Nada foi estimado.", "aviso"), unsafe_allow_html=True)
        else:
            st.markdown(C._msg(f"Fonte: fontes de dados do app (Yahoo Finance, com fonte reserva) · consulta em {hoje}" + (f" · balanço de {d['data_balanco']}" if d and d.get("data_balanco") else ""), "info"), unsafe_allow_html=True)
            for sig in roteiro["indicadores"]:
                if sig in ind:
                    e = ED.explicar_indicador(sig)
                    if e:
                        st.markdown(_card(sig if e["nome"] == sig else f"{sig} · {e['nome']}", "Neste ativo: " + ED.ler_indicador(sig, ind[sig])), unsafe_allow_html=True)
    elif roteiro["indicadores"]:
        st.markdown(C._msg("Indicadores de balanço valem para ações, FIIs e ETFs. Para este ativo, veja o risco observado abaixo.", "info"), unsafe_allow_html=True)
    if not roteiro["risco"]:
        return
    precos, ultima, erro = _fechamentos(alvo)
    m = ED.metricas_risco(precos) if precos else None
    if not m:
        st.markdown(C._msg(f"Histórico indisponível ({erro or 'poucos dados'}). Nada foi estimado.", "aviso"), unsafe_allow_html=True)
        return
    st.markdown(C._msg(f"Fonte: Yahoo Finance · último fechamento de {ultima} · {m['pontos']} dias de dados. Resultado histórico: não indica o futuro.", "info"), unsafe_allow_html=True)
    st.markdown(C._grade([C._kpi("Retorno no período", f"{_br(m['retorno'] * 100, 1, True)}%", "ok" if m["retorno"] >= 0 else "aviso"),
                          C._kpi("Volatilidade anual", f"{_br(m['volatilidade'] * 100)}%", "info"),
                          C._kpi("Queda máxima", f"{_br(m['drawdown'] * 100)}%", "aviso")]), unsafe_allow_html=True)
    outro = st.text_input("Comparar o risco com outro ativo (opcional)", key=f"edu_ru_tk2_{uid}", max_chars=14).strip().upper()
    if outro:
        p2, _u2, e2 = _fechamentos(outro)
        m2 = ED.metricas_risco(p2) if p2 else None
        if not m2:
            st.markdown(C._msg(f"Sem histórico para {outro} ({e2 or 'poucos dados'}).", "aviso"), unsafe_allow_html=True)
        else:
            st.markdown(C._grade([C._kpi(f"{alvo} · volatilidade", f"{_br(m['volatilidade'] * 100)}%", "info"), C._kpi(f"{outro} · volatilidade", f"{_br(m2['volatilidade'] * 100)}%", "info"),
                                  C._kpi(f"{alvo} · queda máx.", f"{_br(m['drawdown'] * 100)}%", "aviso"), C._kpi(f"{outro} · queda máx.", f"{_br(m2['drawdown'] * 100)}%", "aviso")]), unsafe_allow_html=True)
            st.caption("Dois ativos podem render parecido e oscilar de formas muito diferentes. Fonte: Yahoo Finance, último ano.")
    st.caption("Quer a explicação completa de cada indicador? Use a aba Com ativos reais. Conteúdo educacional, não é recomendação.")


# ------------------------------------------------------------------ simulações
def _aba_simulacoes() -> None:
    st.markdown(C._titulo("Simulações educativas", "Resultados HIPOTÉTICOS com as fórmulas do Simulador (Passo 18). Não são previsões nem retornos garantidos."), unsafe_allow_html=True)
    c1, c2, c3, c4, c5 = st.columns(5)
    ini = c1.number_input("Valor inicial (R$)", min_value=0.0, max_value=1e9, value=1000.0, step=100.0, key="edu_s_ini")
    apt = c2.number_input("Aporte mensal (R$)", min_value=0.0, max_value=1e8, value=300.0, step=50.0, key="edu_s_apt")
    tx = c3.number_input("Taxa ao ano (%)", min_value=0.0, max_value=60.0, value=10.0, step=0.5, key="edu_s_tx")
    inf = c4.number_input("Inflação ao ano (%)", min_value=0.0, max_value=30.0, value=4.5, step=0.5, key="edu_s_inf")
    anos = c5.number_input("Anos", min_value=1, max_value=50, value=10, step=1, key="edu_s_anos")
    r = ED.juros_compostos(ini, apt, tx / 100, int(anos), inf / 100)
    st.markdown(C._grade([C._kpi("Total aportado", f"R$ {_br(r['aportado'], 0)}", "info"),
                          C._kpi("Juros acumulados", f"R$ {_br(r['juros'], 0)}", "ok"),
                          C._kpi("Saldo final (nominal)", f"R$ {_br(r['final'], 0)}", "ok"),
                          C._kpi("Saldo em poder de compra de hoje", f"R$ {_br(r['final_real'], 0)}", "aviso", f"taxa real ≈ {_br(r['taxa_real_aa'] * 100, 2)}% ao ano")]), unsafe_allow_html=True)
    try:
        import plotly.graph_objects as go
        anos = list(range(len(r["serie"])))
        fig = go.Figure()
        for nome, chave, cor, trc in (("Saldo", "saldo", "#8B6CFF", "solid"), ("Aportado", "aportado", "#BDB5E6", "dot"),
                                      ("Saldo corrigido pela inflação", "saldo_real", "#3DDC97", "solid")):
            fig.add_scatter(x=anos, y=[x[chave] for x in r["serie"]], name=nome, mode="lines", line={"color": cor, "width": 3, "dash": trc})
        fig.update_layout(height=300, margin={"l": 10, "r": 10, "t": 30, "b": 10}, xaxis_title="Anos", yaxis_title="R$")
        st.plotly_chart(fig, width="stretch", key="edu_juros_graf", config={"displayModeBar": False})
    except Exception:
        st.line_chart({"Saldo": [s["saldo"] for s in r["serie"]], "Aportado": [s["aportado"] for s in r["serie"]], "Saldo corrigido pela inflação": [s["saldo_real"] for s in r["serie"]]},
                      x_label="Anos", y_label="R$")
    st.markdown(C._msg("Hipotético: usa taxa constante, sem impostos nem custos. A realidade oscila. Para cenários, impostos e carteiras, abra o Simulador financeiro.", "aviso"), unsafe_allow_html=True)
    st.caption("Resultados históricos (como a queda máxima na aba \"Com ativos reais\") mostram o que já aconteceu; simulações hipotéticas mostram o que aconteceria se as premissas se confirmassem.")


# ------------------------------------------------------------------ professor
def _aba_professor() -> None:
    import assistente as AS
    st.markdown(C._titulo("Professor de investimentos", "Tira dúvidas e ensina no seu nível. Ele educa: não recomenda compra, venda nem carteira."), unsafe_allow_html=True)
    p = prog()
    chave_g, chave_a = AS._segredo("GEMINI_API_KEY"), AS._segredo("ANTHROPIC_API_KEY")
    if chave_g:
        chave, mod, chamar = chave_g, AS._segredo("GEMINI_MODEL") or AS.GEMINI_MODELO_PADRAO, AS._chamar_gemini
    else:
        chave, mod, chamar = chave_a, AS._segredo("ANTHROPIC_MODEL") or AS.MODELO_PADRAO, AS._chamar_ia
    if not chave:
        st.markdown(C._msg("A IA ainda não está ativada neste app. Enquanto isso, o professor responde com o glossário e os indicadores do app.", "aviso"), unsafe_allow_html=True)
    hist = _ss().setdefault("edu_chat", [])
    aulas_opc = {a["titulo"]: a["id"] for a in E.AULAS}
    foco = st.selectbox("Aula de apoio (opcional)", ["Nenhuma"] + list(aulas_opc), key="edu_prof_aula")
    if st.button("Nova conversa", key="edu_prof_novo"):
        _ss()["edu_chat"] = []
        st.rerun()
    if not hist:
        for i, s in enumerate(["O que é P/L e como interpretar?", "Qual a diferença entre ação e FII?", "Como a inflação afeta a renda fixa?", "O que é drawdown?"]):
            st.button(s, key=f"edu_sug_p{i}", on_click=lambda t=s: _ss().__setitem__("edu_pend", t))
    for m in hist:
        with st.chat_message("user" if m["role"] == "user" else "assistant"):
            st.markdown(m["content"])
    pergunta = st.chat_input("Pergunte sobre um conceito, indicador ou gráfico...", max_chars=AS.MAX_CHARS_PERGUNTA, key="edu_chat_in") or _ss().pop("edu_pend", None)
    if not pergunta:
        st.caption("Conteúdo educacional gerado por IA, que pode errar: confira nas fontes oficiais. Nada aqui é recomendação.")
        return
    if sum(1 for m in hist if m["role"] == "user") >= AS.MAX_PERGUNTAS:
        st.warning("Limite de perguntas da conversa atingido. Toque em Nova conversa.")
        return
    hist.append({"role": "user", "content": pergunta.strip()[:AS.MAX_CHARS_PERGUNTA]})
    with st.chat_message("user"):
        st.markdown(hist[-1]["content"])
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            if chave:
                sistema = AS.SYSTEM_PROMPT + "\n\n" + ED.contexto_professor(p["modo"], aulas_opc.get(foco))
                try:
                    resp = chamar(hist, sistema, chave, mod)
                    if AS.passou_do_limite(resp):
                        resp = AS.MSG_FILTRO
                except RuntimeError as e:
                    resp = f"⚠️ {e}"
            else:
                resp = AS.resposta_sem_ia(pergunta)
        st.markdown(resp)
    if resp.startswith("⚠️"):
        hist.pop()
    else:
        hist.append({"role": "assistant", "content": resp})
        rel = [t for t in E.AULAS if any(w in pergunta.lower() for w in t["titulo"].lower().split() if len(w) > 5)][:2]
        if rel:
            st.markdown(C._msg("Para estudar mais: " + "; ".join(t["titulo"] for t in rel) + ". Veja na aba Biblioteca.", "info"), unsafe_allow_html=True)


# ------------------------------------------------------------------ glossário
def _aba_glossario() -> None:
    from glossario import GLOSSARIO
    st.markdown(C._titulo("Glossário financeiro", "Pesquise qualquer termo do app, com definição, exemplo, fórmula e conteúdos relacionados."), unsafe_allow_html=True)
    q = st.text_input("Buscar termo", key="edu_g_q", placeholder="Ex.: P/L, duration, inflação, come-cotas", max_chars=60)
    itens = ED.buscar_glossario(q, GLOSSARIO)
    st.caption(f"{len(itens)} termos")
    for it in itens[:40]:
        with st.expander(it["termo"], expanded=bool(q) and len(itens) == 1):
            if it.get("central"):
                import glossario_app
                glossario_app.mostrar_termo(it["central"], _st=st)
                if it.get("indicador"):
                    _explicacao(it["indicador"], marcar=True)
                for aid in it.get("aulas", []):
                    if aid in E.POR_ID:
                        st.button(f"Aula: {E.POR_ID[aid]['titulo']}", key=f"edu_g_{it['termo']}_{aid}", on_click=_abrir_aula, args=(aid,))
                continue
            st.markdown(f"**O que é:** {it['definicao']}")
            if it.get("uso"):
                st.markdown(f"**Exemplo / uso:** {it['uso']}")
            if it.get("formula"):
                st.markdown(f"**Fórmula:** `{it['formula']}`")
            if it.get("indicador"):
                _explicacao(it["indicador"], marcar=True)
                rel = ", ".join(it.get("relacionados", []))
                if rel:
                    st.markdown(f"**Indicadores relacionados:** {rel}")
            for aid in it.get("aulas", []):
                if aid in E.POR_ID:
                    st.button(f"Aula: {E.POR_ID[aid]['titulo']}", key=f"edu_g_{it['termo']}_{aid}", on_click=_abrir_aula, args=(aid,))
    if len(itens) > 40:
        st.caption("Refine a busca para ver os demais.")


# ------------------------------------------------------------------ explicador reutilizável por outros módulos
def explicador(sigla: str, chave: str) -> None:
    """Botão compacto ("O que é isso?") que abre a explicação completa de um indicador onde ele aparece.
    Só mostra indicadores compatíveis: sigla desconhecida não gera nada. `chave` precisa ser única na tela."""
    if not ED.chave_indicador(sigla):
        return
    with st.popover(f"O que é {sigla}?", icon=":material/school:"):
        _explicacao(ED.chave_indicador(sigla), marcar=True)
        st.caption("Conteúdo educacional. Veja a página Educação financeira para aprender mais.")


# ------------------------------------------------------------------ página
# 4 botões no topo; dentro de cada um, no máximo um seletor compacto (antes eram 9 botões)
GRUPOS = {"Painel": ("Painel",), "Aulas": ("Trilhas", "Biblioteca"), "Praticar": ("Praticar", "Com ativos reais", "Simulações"), "Mais": ("Professor", "Glossário")}


def pagina_educacao() -> None:
    st.markdown(CSS, unsafe_allow_html=True)
    C._css()
    st.markdown(tema.cabecalho("🎓", "Educação financeira", "Aprenda no seu ritmo, com trilhas, exercícios e dados reais do app."), unsafe_allow_html=True)
    p = prog()
    _ss().setdefault("edu_modo_sel", p["modo"])
    if _ss().get("edu_aula") in E.POR_ID:
        st.segmented_control("Seu nível de leitura", list(modos.MODOS), format_func=lambda m: modos.ROTULOS[m], key="edu_modo_sel", on_change=_mudar_modo)
        _ver_aula(_ss()["edu_aula"])
        st.caption(E.AVISO)
        return
    with st.expander("Seu nível de leitura", icon=":material/tune:"):
        st.segmented_control("Nível", list(modos.MODOS), format_func=lambda m: modos.ROTULOS[m], key="edu_modo_sel", on_change=_mudar_modo, label_visibility="collapsed",
                             help="Muda só a forma de explicar (linguagem e profundidade). Todo o conteúdo fica aberto para todos e não há planos nem preços.")
    fns = {"Painel": _aba_painel, "Trilhas": _aba_trilhas, "Biblioteca": _aba_biblioteca, "Praticar": _aba_praticar, "Com ativos reais": _aba_ativo,
           "Simulações": _aba_simulacoes, "Professor": _aba_professor, "Glossário": _aba_glossario}
    grupo = ES.abas("edu_grupo", list(GRUPOS), colunas=4)
    subs = GRUPOS[grupo]
    sub = subs[0]
    if len(subs) > 1:
        sub = st.selectbox("Seção", subs, key=f"edu_sub_{grupo}", label_visibility="collapsed")
    fns[sub]()
    st.caption(E.AVISO)


# ---- Páginas próprias para o menu das áreas (etapa A6): reaproveitam o que já existe nas abas, sem duplicar lógica ----
def _topo_pagina(emoji: str, titulo: str, sub: str, mostrar_titulo: bool = True) -> bool:
    """CSS e título da página. Devolve True se uma aula da Biblioteca está aberta (mesma regra da página Educação)."""
    st.markdown(CSS, unsafe_allow_html=True)
    C._css()
    if mostrar_titulo:
        st.markdown(tema.cabecalho(emoji, titulo, sub), unsafe_allow_html=True)
    if _ss().get("edu_aula") in E.POR_ID:
        _ver_aula(_ss()["edu_aula"])
        st.caption(E.AVISO)
        return True
    return False


def pagina_jornada() -> None:
    if _topo_pagina("🎓", "Jornada", "Lições curtas, uma de cada vez, no seu ritmo.", mostrar_titulo=False):          # o cartão da Jornada (jornada_app) já é o cabeçalho
        return
    jornada_app.aba(prog, _set, _estudo_unidade)
    st.caption(E.AVISO)


def pagina_glossario() -> None:
    if _topo_pagina("📖", "Glossário", "Pesquise qualquer termo do app."):
        return
    _aba_glossario()
    st.caption(E.AVISO)
