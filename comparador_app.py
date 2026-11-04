"""
Passo 20 — Comparador universal: desempenho, risco, pontuação histórica, IA, carteiras e exportação (tela).

Fica logo abaixo da comparação por indicadores do Passo 6 (app._mostrar_comparacao), sem substituí-la. Os cálculos estão em comparador_calc.py e
comparador_desempenho.py; a coleta, em comparador_dados.py; as fontes, os limites e o cache, em comparador_fontes.py; a IA, em comparador_ia.py.
Só lê e calcula: nada compra, vende ou altera posição. Persistência (usuarios): os "modelos" de carteira ficam em cart_cmp_modelos (prefixo cart_).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd
import streamlit as st

import comparador as cmp
import comparador_calc as K
import comparador_dados as CD
import comparador_desempenho as D
import comparador_fontes as F
import comparador_ia as IA
import relatorios as R
import tema

log = logging.getLogger("comparador_app")

CTX = "_cmp_ctx"
CH_MODELOS = "cart_cmp_modelos"
MAX_MODELOS = 3
MOEDAS = {"R$ (reais)": "BRL", "US$ (dólares)": "USD", "Moeda de cada ativo (sem converter)": "NATIVA"}
MODOS = {"Janela comum a todos os ativos": "comum", "Exatamente o período escolhido (exclui quem não cobre)": "estrito"}
ABAS = ["Desempenho", "Risco", "Pontuação", "Gráfico de indicadores", "Explicação (IA)", "Exportar", "Fontes e qualidade"]


class _Plotly:
    def __getattr__(self, nome):
        import plotly.graph_objects as _go
        return getattr(_go, nome)


go = _Plotly()
_PCT_S = lambda v: R.pct(v, 2, True)          # noqa: E731
_PCT1 = lambda v: R.pct(v, 1)                 # noqa: E731
_PP = lambda v: "n/d" if not R._ok(v) else (f"{v:+.2f}".replace(".", ",") + " p.p.")   # noqa: E731
_NUM = lambda v: "n/d" if not R._ok(v) else f"{float(v):.2f}".replace(".", ",")        # noqa: E731


def _grafico(fig, altura: int = 340):
    fig.update_layout(height=altura, margin=dict(l=10, r=20, t=40, b=10))
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def _tabela(df: pd.DataFrame, chave: str, ganho=(), formatos=None, altura: int | None = None):
    """Tabela padrão do app (relatorios_app.tabela): busca, ordenação, paginação e cores de ganho/perda."""
    import relatorios_app as RA
    df = df.copy()
    for c in df.columns:                                   # None em coluna numérica vira NaN (aparece como n/d, nunca "None")
        if df[c].dtype == object:
            conv = pd.to_numeric(df[c], errors="coerce")
            if conv.notna().sum() == df[c].notna().sum():
                df[c] = conv
    RA.tabela(df, chave, ganho=ganho, formatos=formatos, busca=False, paginar=False, altura=altura)


def _cor(i: int) -> str:
    pal = getattr(tema, "PALETA", ["#2563EB", "#16A34A", "#D97706", "#7C3AED", "#DC2626", "#0891B2", "#DB2777", "#65A30D"])
    return pal[i % len(pal)]


# =============================================================================== linhas coloridas de IA
def _mostrar_ia(r: dict):
    st.markdown(f"**{r['texto']}**")
    for s in r.get("secoes", []):
        st.markdown(f"##### {s['titulo']}")
        for tag, txt in s["linhas"]:
            st.markdown(f"- **{tag}** · {txt}")
    if r.get("gerado_em"):
        st.caption(f"Dados da comparação calculada em {str(r['gerado_em'])[:16].replace('T', ' ')}.")
    if r.get("fontes"):
        st.caption("Fontes: " + ", ".join(r["fontes"]) + ".")
    st.caption(r["limite"])


# =============================================================================== abas
def _aba_desempenho(res: dict, itens: dict):
    p = res["params"]
    moeda_txt = {"BRL": "R$", "USD": "US$", "NATIVA": "moeda de cada ativo"}[p["moeda"]]
    st.caption(f"Período comparado: **{res['ini']:%d/%m/%Y} a {res['fim']:%d/%m/%Y}** ({res['dias']} dias) · moeda: {moeda_txt} · "
               + ("com proventos reinvestidos" if p["proventos"] else "só preço") + ".")
    tr = res["tabela_ret"].drop(columns=["Tipo"], errors="ignore")
    cols = [c for c in tr.columns if c != "Ativo"]
    st.markdown("##### Rentabilidade por janela")
    _tabela(tr, "cmpa_ret", ganho=cols, formatos={c: _PCT_S for c in cols})
    st.caption("Retornos acumulados até a data final. 3 e 5 anos são acumulados (não anualizados); 'Anualizado' vale só para 1 ano ou mais. "
               "n/d = a série não cobre a janela. 'Retorno real' desconta o IPCA (só em reais).")
    if len(res["tabela_vs"]) and res["tabela_vs"].shape[1] > 2:
        st.markdown("##### Diferença para os benchmarks no período")
        vs = res["tabela_vs"]
        _tabela(vs, "cmpa_vs", ganho=[c for c in vs.columns if c != "Ativo"], formatos={"Retorno no período": _PCT_S, **{c: _PP for c in vs.columns if c.startswith("vs ")}})
    b = res["base100"]
    if len(b) > 3:
        fig = go.Figure()
        for i, c in enumerate(b.columns):
            bench = c in res["bench"]
            fig.add_scatter(x=b.index, y=b[c], name=c, mode="lines", line=dict(color=_cor(i), width=1.6 if bench else 2.6, dash="dot" if bench else "solid"),
                            hovertemplate="%{y:.1f}")
        fig.update_layout(title="Evolução de 100 aplicados no início do período", legend=dict(orientation="h", y=-0.2))
        _grafico(fig, 380)
        st.caption("Todos começam em 100 na mesma data e na mesma moeda. Linhas pontilhadas são benchmarks. Dias sem negociação repetem o último valor (até 5 dias).")
    jan = [c for c in ("1 mês", "3 meses", "6 meses", "12 meses") if c in tr.columns]
    if jan and len(tr) >= 2:
        fig = go.Figure()
        for i, c in enumerate(jan):
            fig.add_bar(x=tr["Ativo"], y=[None if not R._ok(v) else v * 100 for v in tr[c]], name=c, marker_color=_cor(i), hovertemplate="%{y:.2f}%")
        fig.update_layout(barmode="group", title="Retorno por janela (%)", legend=dict(orientation="h", y=-0.2))
        _grafico(fig, 320)
    with st.expander("Retorno por ano e por mês"):
        if len(res["cal_anual"]):
            a = res["cal_anual"].reset_index().rename(columns={"index": "Ano"})
            _tabela(a, "cmpa_ano", ganho=[c for c in a.columns if c != "Ano"], formatos={c: _PCT_S for c in a.columns if c != "Ano"})
            st.caption("O primeiro e o último ano podem ser parciais (a série começa ou termina no meio do ano).")
        if len(res["cal_mensal"]):
            m = res["cal_mensal"].reset_index().rename(columns={"index": "Mês"})
            _tabela(m.tail(36), "cmpa_mes", ganho=[c for c in m.columns if c != "Mês"], formatos={c: _PCT_S for c in m.columns if c != "Mês"})
            st.caption("Últimos 36 meses.")
    liq = {k: v for k, v in res["liquido"].items() if v.get("ok")}
    with st.expander("Retorno líquido (impostos)"):
        if liq:
            for k, v in liq.items():
                st.markdown(f"- **{k}**: líquido estimado {R.pct(v['liquido'], 2, True)} (IR {R.pct(v['aliquota'], 1)} sobre o ganho). {v['obs']}.")
        st.caption("Para ações, ETFs, FIIs, fundos e cripto o líquido depende de regras que o app não confirma (isenções, prejuízos compensáveis, come-cotas, "
                   "taxas da corretora): por isso fica n/d em vez de ser estimado.")
    conv = {k: c for k, c in res["conversao"].items() if c.get("convertido")}
    if conv:
        with st.expander("Conversão de moeda: taxa e data usadas"):
            df = pd.DataFrame([{"Ativo": k, "De → Para": f"{c['de']} → {c['para']}", "Taxa inicial": f"{c['taxa_inicio']:.4f}".replace(".", ","), "Data inicial": c["data_inicio"],
                                "Taxa final": f"{c['taxa_fim']:.4f}".replace(".", ","), "Data final": c["data_fim"], "Fonte": c["fonte"]} for k, c in conv.items()])
            st.dataframe(df, hide_index=True, width="stretch")


def _aba_risco(res: dict, itens: dict):
    rt = res["risco_tab"]
    st.markdown("##### Indicadores de risco")
    pct_cols = ["Volatilidade anual", "Queda máxima", "Queda atual", "VaR 95% (1 dia)", "CVaR 95% (1 dia)"]
    _tabela(rt, "cmpa_risco", ganho=[], formatos={**{c: _PCT1 for c in pct_cols}, **{c: _NUM for c in ("Sharpe", "Sortino", "Beta", "Calmar")}})
    st.caption(f"Volatilidade em dias úteis (√252) para todas as classes. Sharpe/Sortino usam {res['rf']} como taxa livre de risco. Beta contra: "
               f"{res['ref_beta'] or 'n/d (sem benchmark)'}. VaR e CVaR históricos de 95% em 1 dia exigem 250 dias úteis. "
               "n/d = amostra pequena demais: o app não calcula com poucos dados.")
    faltam = [(k, c, m) for k, d in res["risco_det"].items() for c, m in d["motivos"].items() if c in ("var95", "sharpe", "vol_anual")]
    if faltam:
        with st.expander("Por que alguns indicadores estão n/d"):
            for k, c, m in faltam[:12]:
                st.markdown(f"- {k} · {c}: {m}.")
    dif = D.diferencas_de_risco(res["risco_det"], {k: itens[k]["classe"] for k in res["series"]})
    if dif:
        st.markdown("##### Por que o risco difere")
        for t in dif:
            st.markdown(f"- {t}")
    pts = [(k, res["risco_det"][k]["vol_anual"], res["tabela_ret"].set_index("Ativo").loc[k, "Período escolhido"]) for k in res["series"]]
    pts = [p for p in pts if R._ok(p[1]) and R._ok(p[2])]
    if len(pts) >= 2:
        fig = go.Figure()
        for i, (k, v, r) in enumerate(pts):
            fig.add_scatter(x=[v * 100], y=[r * 100], mode="markers+text", text=[k], textposition="top center", name=k, marker=dict(size=14, color=_cor(i)))
        fig.update_layout(title="Risco × retorno no período", xaxis_title="Volatilidade anual (%)", yaxis_title="Retorno no período (%)", showlegend=False)
        _grafico(fig, 340)
        st.caption("Mais à esquerda = oscilou menos; mais acima = rendeu mais. Passado não garante futuro.")
    dd = go.Figure()
    algum = False
    for i, (k, s) in enumerate(res["series"].items()):
        x = s[(s.index >= res["ini"]) & (s.index <= res["fim"])]
        if len(x) > 5:
            dd.add_scatter(x=x.index, y=(x / x.cummax() - 1) * 100, name=k, line=dict(color=_cor(i)), hovertemplate="%{y:.1f}%")
            algum = True
    if algum:
        dd.update_layout(title="Queda desde o pico (%)", legend=dict(orientation="h", y=-0.2))
        _grafico(dd, 320)
    c = res["corr"]
    if len(c):
        fig = go.Figure(go.Heatmap(z=c.values, x=list(c.columns), y=list(c.index), zmin=-1, zmax=1, colorscale="RdBu_r", text=np.round(c.values, 2), texttemplate="%{text}"))
        fig.update_layout(title="Correlação dos retornos diários")
        _grafico(fig, 320)
        st.caption("Perto de 1: andam juntos (pouca diversificação). Perto de 0: independentes. Negativa: tendem a andar em sentidos opostos.")
    else:
        st.caption("Correlação: precisa de pelo menos 60 dias úteis em comum entre pelo menos 2 ativos.")
    cons = [{"Ativo": k, "Meses analisados": v.get("meses"), "Meses positivos": v.get("pct_positivos"), "Melhor mês": v.get("melhor"), "Pior mês": v.get("pior"),
             "Meses acima do benchmark": v.get("pct_acima_bench")} for k, v in res["cons"].items() if v.get("ok")]
    if cons:
        st.markdown("##### Consistência mensal")
        _tabela(pd.DataFrame(cons), "cmpa_cons", formatos={"Meses positivos": _PCT1, "Melhor mês": _PCT_S, "Pior mês": _PCT_S, "Meses acima do benchmark": _PCT1})
    else:
        st.caption("Consistência mensal: precisa de pelo menos 6 meses de histórico no período.")
    st.caption("Exposição cambial: ativos em dólar carregam o risco do câmbio quando a comparação é em reais. Concentração e liquidez da CARTEIRA estão em "
               "Gestão de risco; aqui o risco é de cada ativo.")


def _aba_pontuacao(res: dict, itens: dict, ativos: list, comp):
    st.markdown("##### Perfil histórico (complementar à nota da classe)")
    st.caption("A nota da classe (acima, no Comparar) mede fundamentos e características de cada classe. Esta mede só o comportamento no período: retorno por "
               "unidade de risco, oscilação, pior queda e consistência. Cada classe usa âncoras próprias; as notas NÃO são ranqueadas entre classes.")
    cols = st.columns(min(len(res["series"]), 4) or 1)
    for i, (k, pt) in enumerate(res["pont_hist"].items()):
        nota = pt.nota
        cls = "na" if nota is None else ("good" if nota >= 70 else "fair" if nota >= 50 else "bad")
        with cols[i % len(cols)]:
            st.markdown(tema.card_status(k, "indisponível" if nota is None else f"{nota:.0f}/100", cls,
                                         cmp.CLASSES[itens[k]["classe"]].nome + (" · provisória" if pt.provisoria else "")), unsafe_allow_html=True)
    with st.expander("O que influenciou o perfil histórico"):
        for k, pt in res["pont_hist"].items():
            st.markdown(f"**{k}** — {pt.metodo}")
            for t in pt.influencias:
                st.markdown(f"- {t}")
    st.markdown("##### De onde vem cada pilar da avaliação")
    linhas = []
    for a in ativos:
        if a.chave not in res["series"]:
            continue
        ph = res["pont_hist"].get(a.chave)
        cb = D.cobertura_de_pilares(a, tem_historico=bool(ph and ph.nota is not None), tem_consist=res["cons"].get(a.chave, {}).get("ok", False))
        linhas.append({"Ativo": a.chave, **cb})
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        st.caption("'nota da classe' = entra na nota do Comparar; 'perfil histórico' = nota desta aba; 'tabela' = aparece na tabela mas não pesa em nota; "
                   "'sem dado' = a fonte não entrega. Pilar sem dado reduz a confiança, nunca vira zero.")


def _aba_indicador(ativos: list):
    ok = [a for a in ativos if not a.erro]
    classes = sorted({a.classe for a in ok})
    if not ok or not classes:
        st.caption("Sem indicadores para mostrar.")
        return
    cl = st.selectbox("Classe", classes, key="cmpa_ind_classe", format_func=lambda c: cmp.CLASSES[c].nome) if len(classes) > 1 else classes[0]
    membros = [a for a in ok if a.classe == cl]
    specs = [s for s in cmp.CLASSES[cl].specs if any(a.ind.get(s.chave) is not None and a.ind[s.chave].valor is not None for a in membros)]
    if len(membros) < 2 or not specs:
        st.caption("Escolha pelo menos 2 ativos da mesma classe com dados para ver o gráfico.")
        return
    sp = st.selectbox("Indicador", specs, key="cmpa_ind_spec", format_func=lambda s: s.nome)
    vals = [(a.chave, a.ind[sp.chave].valor if a.ind.get(sp.chave) else None) for a in membros]
    fig = go.Figure(go.Bar(x=[v[0] for v in vals], y=[v[1] for v in vals], marker_color=[_cor(i) for i in range(len(vals))],
                           text=[cmp.fmt_valor(v[1], sp.fmt) if v[1] is not None else "n/d" for v in vals], textposition="outside"))
    fig.update_layout(title=sp.nome, showlegend=False)
    _grafico(fig, 320)
    nota = {1: "maior é melhor", -1: "menor é melhor", 0: "só informativo"}[sp.direcao]
    st.caption(f"{sp.nome}: {nota}. " + (sp.dica or "") + " Ativos sem o dado ficam sem barra.")


def _aba_ia(res: dict, itens: dict, ativos: list, comp):
    ctx = K.contexto_ia(ativos, comp, res, itens)
    st.session_state[CTX] = ctx
    st.caption("A IA do comparador só usa os números calculados nesta tela. Cada linha vem marcada: ✔ dado, ≈ estimativa ou 💬 opinião (sempre com justificativa).")
    if st.button("Gerar resumo comparativo", key="cmpa_ia_resumo", type="primary"):
        st.session_state["cmpa_ia_res"] = IA.resumo_comparativo(ctx)
    q = st.text_input("Pergunte sobre esta comparação", key="cmpa_ia_q", placeholder="Ex.: qual oscilou mais? o que está faltando? quem entende cada um?", max_chars=200)
    if st.button("Perguntar", key="cmpa_ia_ask") and q.strip():
        st.session_state["cmpa_ia_res"] = IA.responder_comparacao(q.strip(), ctx)
    r = st.session_state.get("cmpa_ia_res")
    if r:
        _mostrar_ia(r)


def _arquivos(res: dict, itens: dict, ativos: list) -> dict:
    doc, graficos, num = K.preparar_exportacao(res, itens, ativos)
    out = {"csv_tabelas": {}, "disp": R.disponibilidade_exportacao()}
    for nome, df in K.tabelas_formatadas(res, itens):
        out["csv_tabelas"][nome.split(" (")[0]] = R.csv_bytes(df)
    out["csv_tabelas"]["Evolução base 100"] = R.csv_bytes(res["base100"].round(4).reset_index().rename(columns={"index": "Data"}))
    if out["disp"].get("excel"):
        out["excel"] = R.excel_bytes(doc, num)
    if out["disp"].get("pdf"):
        out["pdf"] = R.pdf_bytes(doc, graficos)
    return out


def _aba_exportar(res: dict, itens: dict, ativos: list):
    st.caption("Os arquivos trazem identificação, período, moeda, tabelas, metodologia, fontes e avisos (o PDF também leva os gráficos principais).")
    sig = (tuple(res["series"]), str(res["params"]), res["ini"].isoformat(), res["fim"].isoformat(), tuple(i.get("coletado_em") for i in itens.values()))
    if st.button("Preparar arquivos", key="cmpa_exp_prep", type="primary"):
        with st.spinner("Montando PDF, Excel e CSV..."):
            try:
                st.session_state["cmpa_arq"] = {"sig": sig, **_arquivos(res, itens, ativos)}
            except Exception as e:
                log.warning("exportação falhou: %s", e.__class__.__name__)
                st.error("Não consegui montar os arquivos agora. Tente de novo; se continuar, avise o suporte com a hora do erro.")
    arq = st.session_state.get("cmpa_arq")
    if not arq or arq.get("sig") != sig:
        st.info("Toque em **Preparar arquivos** para gerar PDF, Excel e CSV desta comparação.")
        return
    c1, c2, c3 = st.columns(3)
    if arq.get("pdf"):
        c1.download_button("Baixar PDF", arq["pdf"], "comparacao.pdf", "application/pdf", key="cmpa_dl_pdf")
    else:
        c1.caption("PDF indisponível neste ambiente (falta a biblioteca reportlab).")
    if arq.get("excel"):
        c2.download_button("Baixar Excel", arq["excel"], "comparacao.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="cmpa_dl_xlsx")
    else:
        c2.caption("Excel indisponível neste ambiente (falta a biblioteca openpyxl).")
    nome = c3.selectbox("Tabela do CSV", list(arq["csv_tabelas"]), key="cmpa_csv_nome")
    c3.download_button("Baixar CSV", arq["csv_tabelas"][nome], f"comparacao_{nome.lower().replace(' ', '_')}.csv", "text/csv", key="cmpa_dl_csv")
    st.caption("CSV com ';' e decimal ',', pronto para abrir no Excel brasileiro.")


def _aba_fontes(res: dict, itens: dict):
    st.markdown("##### Rastreabilidade de cada ativo")
    rs = K.rastreio(itens, res)
    st.dataframe(rs, hide_index=True, width="stretch")
    st.caption("Fonte, data de coleta, último dado, início do histórico, moeda, unidade, frequência e confiabilidade (oficial e recente = Alta; rebaixa com atraso, "
               "menos de 1 ano de dados ou divergência entre fontes).")
    with st.expander("Tentativas de coleta por ativo"):
        for k, it in itens.items():
            st.markdown(f"**{k}**")
            for t in it.get("tentativas", []):
                ok = "✔" if t["ok"] else "✖"
                st.markdown(f"- {ok} {F.rotulo_fonte(t['fonte'])}: " + (f"{t['n']} pontos, de {t['inicio']} a {t['fim']}" if t["ok"] else t["motivo"]))
            d = it.get("divergencia")
            if d:
                st.markdown(f"- Conferência entre fontes: " + ("compatíveis" if d.get("ok") else (d.get("motivo") or "não conferido")) + ".")
            for a in it.get("avisos", []):
                st.markdown(f"- ⚠️ {a}")
    st.markdown("##### Fontes do app, limites e termos")
    df = F.tabela_fontes()
    st.dataframe(df[["Fonte", "Tipo", "Situação", "Chave", "Limite do plano gratuito", "Histórico"]], hide_index=True, width="stretch")
    with st.expander("Uso comercial, redistribuição e data da conferência"):
        st.dataframe(df[["Fonte", "Uso comercial", "Redistribuição", "Conferido em"]], hide_index=True, width="stretch")
    st.caption("Nenhuma fonte paga é ativada sem a sua autorização. Chaves só em secrets ou variáveis de ambiente. Fontes 'Desativadas' estão documentadas, mas o app não as consulta.")


# =============================================================================== página (ativos)
def pagina_avancada(ativos: list, sel: list, comp):
    """Seção 'Desempenho, risco e explicação' abaixo da comparação por indicadores. `sel` = [(código, classe)] na mesma ordem de `ativos`."""
    ss = st.session_state
    st.divider()
    st.markdown("### Desempenho, risco e explicação")
    st.caption("Mesmo período e mesma moeda para todos. Retornos passados não garantem retornos futuros.")
    c1, c2, c3 = st.columns(3)
    periodo = c1.selectbox("Período", list(D.PRESETS) + ["Personalizado"], index=4, key="cmpa_periodo")
    moeda_rot = c2.selectbox("Moeda de comparação", list(MOEDAS), key="cmpa_moeda")
    modo_rot = c3.selectbox("Períodos diferentes", list(MODOS), key="cmpa_modo",
                            help="Janela comum: todos usam o intervalo em que todos têm dados. Exato: quem não tem histórico desde o início fica de fora.")
    moeda, modo = MOEDAS[moeda_rot], MODOS[modo_rot]
    ini = fim = None
    if periodo == "Personalizado":
        d1, d2 = st.columns(2)
        ini = d1.date_input("De", value=date.today() - timedelta(days=365), key="cmpa_ini", max_value=date.today())
        fim = d2.date_input("Até", value=date.today(), key="cmpa_fim", max_value=date.today())
        if ini and fim and ini >= fim:
            st.warning("A data inicial precisa ser anterior à final.")
            return
    c4, c5 = st.columns(2)
    proventos = c4.checkbox("Incluir proventos (retorno total)", value=True, key="cmpa_prov",
                            help="Dividendos e rendimentos reinvestidos no dia ex. Disponível para ações, ETFs e FIIs do Yahoo.")
    conferir = c5.checkbox("Conferir com uma segunda fonte (usa mais consultas)", value=False, key="cmpa_conf")
    opcoes_b = {"BRL": ["CDI", "Ibovespa", "S&P 500 (em R$)", "Dólar"], "USD": ["S&P 500 (US$)"], "NATIVA": []}[moeda]
    bench = st.multiselect("Benchmarks", opcoes_b, default=[b for b in ("CDI", "Ibovespa") if b in opcoes_b] or opcoes_b[:1], key=f"cmpa_bench_{moeda}") if opcoes_b else []
    codigos = [(c, cl) for c, cl in sel]
    chave = (tuple(codigos), bool(proventos), bool(conferir))
    if st.button("Carregar desempenho e risco", key="cmpa_carregar", type="primary"):
        with st.spinner("Coletando preços, câmbio e benchmarks (usa o cache quando possível)..."):
            nomes = {a.chave: a.nome for a in ativos}
            ss["cmpa_dados"] = {"chave": chave, "itens": CD.coletar_itens(codigos, proventos, conferir, nomes), "refs": CD.coletar_refs()}
    dados = ss.get("cmpa_dados")
    if not dados or dados["chave"] != chave:
        st.info("Toque em **Carregar desempenho e risco** para buscar os preços e montar a comparação de rentabilidade e risco.")
        return
    itens, refs = dados["itens"], dados["refs"]
    params = {"periodo": periodo, "ini": pd.Timestamp(ini) if ini else None, "fim": pd.Timestamp(fim) if fim else None, "modo": modo, "moeda": moeda,
              "proventos": bool(proventos), "benchmarks": bench}
    res = K.calcular(itens, refs, params)
    avisos = list(dict.fromkeys(refs.get("avisos", []) + [a for it in itens.values() for a in it.get("avisos", [])] + res["avisos"]))
    if not res["ok"]:
        st.warning("Não foi possível montar a comparação de desempenho: " + (" ".join(res["avisos"]) or "sem dados."))
        for k, it in itens.items():
            for a in it.get("avisos", []):
                st.caption(f"{k}: {a}")
        return
    if avisos:
        with st.expander(f"⚠️ Qualidade e confiabilidade ({len(avisos)})", expanded=len(avisos) <= 3):
            for a in avisos:
                st.markdown(f"- {a}")
    abas = st.tabs(ABAS)
    with abas[0]:
        _aba_desempenho(res, itens)
    with abas[1]:
        _aba_risco(res, itens)
    with abas[2]:
        _aba_pontuacao(res, itens, ativos, comp)
    with abas[3]:
        _aba_indicador(ativos)
    with abas[4]:
        _aba_ia(res, itens, ativos, comp)
    with abas[5]:
        _aba_exportar(res, itens, ativos)
    with abas[6]:
        _aba_fontes(res, itens)
    st.caption(D.AVISO)


# =============================================================================== comparação de carteiras
def _lotes(chave: str) -> list:
    return [x for x in st.session_state.get(chave, []) if isinstance(x, dict)]


def _entrada_da_carteira(chave: str, rotulo: str, refs: dict) -> tuple[dict | None, list[str]]:
    """Carteira do app (Passo 12) como entrada do comparador: séries em R$, pesos pelo valor atual, posições e DY dos 12 meses."""
    import gestao_app
    av: list[str] = []
    lido = gestao_app.ler_carteira(chave)
    if lido is None:
        return None, [f"{rotulo}: sem posições."]
    C, Dd = lido
    pos = {p["id"]: {"valor": p["valor"], "classe": p["classe"], "moeda": p["moeda"]} for p in C["posicoes"] if R._ok(p.get("valor")) and p["valor"] > 0}
    series = {k: v for k, v in Dd["series"].items() if k in pos}
    pesos = {k: pos[k]["valor"] for k in series}
    dy = {}
    for p in C["posicoes"]:
        pr = (C.get("prov_papel") or {}).get(p["id"])
        if pr is not None and len(pr) and R._ok(p.get("preco")):
            ser = pd.Series(pr["valor"].values, index=pd.to_datetime(pr["data"]))
            dy[p["id"]] = K.dy_12m(ser, p["preco"])
    sem = [k for k in pos if k not in series]
    if sem:
        av.append(f"{rotulo}: sem série de preços para {', '.join(sem)} (renda fixa e fundos sem histórico entram na alocação, não na rentabilidade).")
    return {"series": series, "pesos": pesos, "posicoes": pos, "dy": dy}, av


def _entrada_do_modelo(m: dict, refs: dict) -> tuple[dict | None, list[str]]:
    pesos, erros = K.parse_modelo(m.get("texto", ""))
    av = [f"{m['nome']}: {e}" for e in erros]
    if not pesos:
        return None, av + [f"{m['nome']}: sem ativos válidos."]
    series, pos, dy = {}, {}, {}
    total = float(m.get("valor") or 100000.0)
    soma = sum(pesos.values())
    nomes = [(c, cmp.identificar_classe(c)[0]) for c in pesos]
    itens = CD.coletar_itens(nomes, True, False)
    for cod, cl in nomes:
        it = itens[cod]
        if len(it["preco"]) < 30:
            av.append(f"{m['nome']}: sem histórico de {cod}.")
            continue
        base, _ = D.retorno_total(it["preco"], it["prov"]) if it["prov"] is not None and len(it["prov"]) else (it["preco"], {})
        if it["moeda"] != "BRL":
            base, info = D.converter(base, refs.get("fx"), it["moeda"], "BRL")
            if base.empty:
                av.append(f"{m['nome']}: não consegui converter {cod} para reais.")
                continue
        series[cod] = base
        pos[cod] = {"valor": total * pesos[cod] / soma, "classe": cl, "moeda": it["moeda"]}
        if it["prov"] is not None and len(it["prov"]):
            dy[cod] = K.dy_12m(it["prov"], float(it["preco"].iloc[-1]))
    if not series:
        return None, av
    return {"series": series, "pesos": {k: pesos[k] for k in series}, "posicoes": pos, "dy": dy}, av


def _formulario_modelo():
    ss = st.session_state
    modelos = ss.setdefault(CH_MODELOS, [])
    with st.expander(f"Carteiras-modelo ({len(modelos)}/{MAX_MODELOS}): simule outras distribuições", expanded=not modelos):
        st.caption("Informe os ativos e os pesos, por exemplo: PETR4:40, BOVA11:30, BTC-USD:30. Os pesos são relativos (somam 100% depois). "
                   "É uma simulação histórica com os pesos fixos: não é recomendação.")
        nome = st.text_input("Nome do modelo", key="cmpa_m_nome", max_chars=30, placeholder="Ex.: Mais conservadora")
        texto = st.text_input("Ativos e pesos", key="cmpa_m_texto", max_chars=300, placeholder="PETR4:40, BOVA11:30, BTC-USD:30")
        valor = st.number_input("Valor total do modelo (R$)", min_value=1000.0, value=100000.0, step=1000.0, key="cmpa_m_valor")
        if st.button("Adicionar modelo", key="cmpa_m_add"):
            pesos, erros = K.parse_modelo(texto)
            if not nome.strip():
                st.warning("Dê um nome ao modelo.")
            elif len(modelos) >= MAX_MODELOS:
                st.warning(f"No máximo {MAX_MODELOS} modelos.")
            elif erros or len(pesos) < 1:
                st.warning(" ".join(erros) or "Informe pelo menos um ativo com peso.")
            elif any(m["nome"] == nome.strip() for m in modelos):
                st.warning("Já existe um modelo com esse nome.")
            else:
                modelos.append({"nome": nome.strip(), "texto": texto.strip(), "valor": float(valor)})
                st.rerun()
        for i, m in enumerate(list(modelos)):
            c1, c2 = st.columns([4, 1])
            c1.markdown(f"**{m['nome']}** · {m['texto']} · {R.brl(m['valor'])}")
            if c2.button("Remover", key=f"cmpa_m_del_{i}"):
                modelos.pop(i)
                st.rerun()
    return modelos


def pagina_carteiras():
    """Compara carteiras (a real, a fictícia e até 3 modelos) no mesmo período: rentabilidade, risco, diversificação, concentração, classes, correlação e renda."""
    ss = st.session_state
    st.markdown("### Comparar carteiras")
    st.caption("Usa a carteira do Passo 12 (valores atuais como pesos fixos sobre o histórico) e modelos simulados. Mostra o passado: não é previsão nem recomendação.")
    modelos = _formulario_modelo()
    opcoes = []
    if _lotes("cart_real") or ss.get("cart_rf") or ss.get("cart_fundos_cvm"):
        opcoes.append("Carteira real")
    if _lotes("cart_ficticia"):
        opcoes.append("Carteira fictícia")
    opcoes += [m["nome"] for m in modelos]
    if len(opcoes) < 2:
        st.info("Para comparar, tenha pelo menos 2 carteiras: a real, a fictícia ou modelos criados acima.")
        return
    esc = st.multiselect("Carteiras a comparar", opcoes, default=opcoes[:2], key="cmpa_c_sel")
    periodo = st.selectbox("Período", list(D.PRESETS), index=4, key="cmpa_c_periodo")
    if len(esc) < 2:
        st.info("Escolha pelo menos 2 carteiras.")
        return
    if st.button("Comparar carteiras", key="cmpa_c_go", type="primary"):
        with st.spinner("Coletando e calculando..."):
            refs = CD.coletar_refs()
            entradas, avisos = {}, []
            for nome in esc:
                if nome == "Carteira real":
                    e, av = _entrada_da_carteira("cart_real", nome, refs)
                elif nome == "Carteira fictícia":
                    e, av = _entrada_da_carteira("cart_ficticia", nome, refs)
                else:
                    e, av = _entrada_do_modelo(next(m for m in modelos if m["nome"] == nome), refs)
                avisos += av
                if e:
                    entradas[nome] = e
            res = K.calcular_carteiras(entradas, refs, periodo) if len(entradas) >= 1 else {"ok": False, "avisos": []}
            res["avisos"] = avisos + res.get("avisos", []) + refs.get("avisos", [])
            ss["cmpa_c_res"] = {"res": res, "sel": list(esc), "periodo": periodo, "quando": R.agora().strftime("%d/%m/%Y %H:%M")}
    out = ss.get("cmpa_c_res")
    if not out or out["sel"] != list(esc) or out["periodo"] != periodo:
        st.info("Toque em **Comparar carteiras** para calcular.")
        return
    res = out["res"]
    if res.get("avisos"):
        with st.expander(f"⚠️ Qualidade e limites ({len(res['avisos'])})", expanded=not res.get("ok")):
            for a in dict.fromkeys(res["avisos"]):
                st.markdown(f"- {a}")
    if not res.get("ok"):
        st.warning("Não foi possível comparar as carteiras com os dados disponíveis.")
        return
    st.caption(f"Período em comum: **{res['ini']:%d/%m/%Y} a {res['fim']:%d/%m/%Y}** ({res['dias']} dias) · calculado em {out['quando']} · taxa livre de risco: {res['rf']}.")
    t = res["tabela"]
    pct = ["Retorno no período", "Anualizado (a.a.)"]
    pct1 = ["Volatilidade anual", "Queda máxima", "VaR 95% (1 dia)", "CVaR 95% (1 dia)", "Maior posição", "DY da carteira"]
    st.markdown("##### Rentabilidade, risco e diversificação")
    _tabela(t, "cmpa_c_tab", ganho=pct, formatos={**{c: _PCT_S for c in pct}, **{c: _PCT1 for c in pct1}, **{c: _NUM for c in ("Sharpe", "Sortino", "Beta", "Nº efetivo de ativos")},
                                                  "Renda estimada (12m)": R.brl})
    st.caption("Nº efetivo de ativos = 1 ÷ Σ(peso²): quantas posições de mesmo tamanho dariam a mesma concentração. Renda estimada = valor × DY dos últimos 12 meses "
               "(estimativa baseada no passado, não promessa).")
    ev = res["evolucao"]
    fig = go.Figure()
    for i, c in enumerate(ev.columns):
        fig.add_scatter(x=ev.index, y=ev[c], name=c, line=dict(color=_cor(i), width=2.6), hovertemplate="%{y:.1f}")
    b = res.get("bench100")
    if b is not None and len(b):
        for j, c in enumerate(b.columns):
            fig.add_scatter(x=b.index, y=b[c], name=c, line=dict(color=_cor(len(ev.columns) + j), width=1.4, dash="dot"), hovertemplate="%{y:.1f}")
    fig.update_layout(title="Evolução de 100 aplicados (pesos fixos)", legend=dict(orientation="h", y=-0.2))
    _grafico(fig, 380)
    cl = []
    for nome, d in res["carteiras"].items():
        for x in d["classes"]:
            cl.append({"Carteira": nome, "Classe": cmp.CLASSES[x["nome"]].nome if x["nome"] in cmp.CLASSES else x["nome"], "Peso": x["pct"] * 100})
    if cl:
        df = pd.DataFrame(cl)
        fig = go.Figure()
        for i, c in enumerate(sorted(df["Classe"].unique())):
            s = df[df["Classe"] == c]
            fig.add_bar(x=s["Carteira"], y=s["Peso"], name=c, marker_color=_cor(i), hovertemplate="%{y:.1f}%")
        fig.update_layout(barmode="stack", title="Exposição por classe (%)", legend=dict(orientation="h", y=-0.2))
        _grafico(fig, 320)
    cor = res.get("correlacao")
    if cor is not None and len(cor):
        fig = go.Figure(go.Heatmap(z=cor.values, x=list(cor.columns), y=list(cor.index), zmin=-1, zmax=1, colorscale="RdBu_r", text=np.round(cor.values, 2), texttemplate="%{text}"))
        fig.update_layout(title="Correlação entre as carteiras (retornos diários)")
        _grafico(fig, 300)
    with st.expander("Renda passiva estimada por carteira"):
        for nome, d in res["carteiras"].items():
            rp = d["renda"]
            if rp.get("ok"):
                st.markdown(f"- **{nome}**: cerca de {R.brl(rp['mensal'])} por mês ({R.brl(rp['anual'])} por ano), DY {R.pct(rp['dy_carteira'], 2)}; "
                            f"cobre {R.pct(rp['cobertura'], 0)} do valor" + (f"; sem DY: {', '.join(rp['sem_dy'])}" if rp["sem_dy"] else "") + ".")
            else:
                st.markdown(f"- **{nome}**: {rp.get('motivo', 'sem dados')}.")
        st.caption("Proventos dos últimos 12 meses ÷ preço atual. Renda fixa e fundos não entram. Proventos passados não garantem os futuros.")
    _exportar_carteiras(res, out)
    st.caption(D.AVISO)


def _exportar_carteiras(res: dict, out: dict):
    t = res["tabela"]
    txt = D.tabela_texto(t, pct_cols=["Retorno no período", "Anualizado (a.a.)", "Volatilidade anual", "Queda máxima", "VaR 95% (1 dia)", "CVaR 95% (1 dia)", "Maior posição", "DY da carteira"],
                         num_cols=["Sharpe", "Sortino", "Beta", "Nº efetivo de ativos"], moeda_cols=["Renda estimada (12m)"])
    doc = R.montar_relatorio("Comparação de carteiras", ", ".join(t["Carteira"]), f"{res['ini']:%d/%m/%Y} a {res['fim']:%d/%m/%Y} ({res['dias']} dias), em R$", {},
                             [{"titulo": "Carteiras comparadas", "tipo": "tabela", "dados": txt}, {"titulo": "Metodologia", "tipo": "texto", "dados": K.METODOLOGIA[:4] + [
                                 "Carteiras: pesos fixos (valores atuais ou do modelo) aplicados ao histórico dos ativos; só os ativos com histórico entram e a cobertura é informada."]}],
                             ["Yahoo Finance", "Banco Central do Brasil", "CVM"], res["avisos"])
    doc["aviso_legal"] = D.AVISO
    ev = res["evolucao"]
    idx = ev.index[:: max(1, len(ev) // 60)]
    graf = [{"titulo": "Evolução (base 100)", "tipo": "linha", "x": [d.strftime("%m/%y") for d in idx], "series": {c: [float(v) for v in ev.loc[idx, c]] for c in ev.columns}}]
    c1, c2, c3 = st.columns(3)
    disp = R.disponibilidade_exportacao()
    if st.button("Preparar arquivos", key="cmpa_c_prep"):
        arq = {"csv": R.csv_bytes(txt)}
        try:
            if disp.get("excel"):
                arq["xlsx"] = R.excel_bytes(doc, {"Carteiras": t, "Evolução base 100": ev.reset_index().rename(columns={"index": "Data"})})
            if disp.get("pdf"):
                arq["pdf"] = R.pdf_bytes(doc, graf)
        except Exception as e:
            log.warning("exportação de carteiras falhou: %s", e.__class__.__name__)
            st.error("Não consegui montar os arquivos agora. Tente de novo.")
        st.session_state["cmpa_c_arq"] = arq
    arq = st.session_state.get("cmpa_c_arq")
    if arq:
        if arq.get("pdf"):
            c1.download_button("Baixar PDF", arq["pdf"], "carteiras.pdf", "application/pdf", key="cmpa_c_dl_pdf")
        if arq.get("xlsx"):
            c2.download_button("Baixar Excel", arq["xlsx"], "carteiras.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="cmpa_c_dl_xlsx")
        c3.download_button("Baixar CSV", arq["csv"], "carteiras.csv", "text/csv", key="cmpa_c_dl_csv")
