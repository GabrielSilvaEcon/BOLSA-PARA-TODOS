"""
Passo 18 — Simulador de investimentos e planejamento financeiro (tela). Os cálculos estão em simulador.py, simulador_carteira.py e
simulador_ia.py (sem Streamlit nem rede); aqui ficam as 12 abas, os gráficos e a leitura da carteira (Passo 12) e do mercado (Banco Central).

Tudo é hipótese de planejamento: o app não promete rentabilidade, não compra, não vende e não altera posições.
Persistência (usuarios.CHAVES): sim_metas (painel de metas) e sim_premissas (premissas por classe editadas por você).
Cada widget usa chave própria 'sim_*'; os resultados mudam na hora em que você altera uma premissa.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as _st

import simulador as S
import simulador_carteira as SC
import simulador_ia as SI
import tema
from renda_fixa_app import _p, _r as _brl

log = logging.getLogger("simulador_app")


class _St:
    """Streamlit com o cifrão escapado nos textos em Markdown: sem isso, dois 'R$' na mesma frase viram fórmula matemática."""
    _MD = {"markdown", "caption", "write", "success", "info", "warning", "error"}

    def __getattr__(self, nome):
        f = getattr(_st, nome)
        if nome not in self._MD:
            return f

        def envolto(t="", *a, **k):
            if isinstance(t, str) and not k.get("unsafe_allow_html"):
                t = t.replace("\\$", "$").replace("$", "\\$")
            return f(t, *a, **k)
        return envolto


st = _St()

CH_METAS, CH_PREM = "sim_metas", "sim_premissas"
CTX = "_sim_ctx"
ABAS = ["Juros compostos", "Aposentadoria", "Renda passiva", "Aportes e metas", "Por classe", "Cenários", "Crises", "Carteira", "Histórico", "Inflação", "Assistente", "Fórmulas"]
TRANSP = dict(paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", margin=dict(l=10, r=10, t=40, b=10))
COR = {"investido": "#8b9bb4", "liquido": "#38bdf8", "real": "#34d399", "renda": "#fbbf24", "ruim": "#f87171", "alt": "#a78bfa"}
FREQ_ROT = {"semanal": "Semanal", "quinzenal": "Quinzenal", "mensal": "Mensal", "bimestral": "Bimestral", "trimestral": "Trimestral", "semestral": "Semestral", "anual": "Anual"}
MOMENTO_ROT = {"fim": "No fim do período", "inicio": "No início do período"}
CLASSES_ROT = {**S.CLASSES_SIM}
CLASSES_CARTEIRA = {**S.CLASSES_SIM, "caixa": "Caixa"}


class _Plotly:
    def __getattr__(self, nome):
        import plotly.graph_objects as _go
        return getattr(_go, nome)


go = _Plotly()


def _ss():
    return st.session_state


def _opt(chave: str, nome: str, valor) -> dict:
    """Valor inicial só na primeira vez (evita o aviso do Streamlit de widget com valor padrão e session_state ao mesmo tempo)."""
    return {} if chave in st.session_state else {nome: valor}


def _cartoes(itens: list, por_linha: int = 4):
    for k in range(0, len(itens), por_linha):
        for col, (rot, val, cls, *det) in zip(st.columns(por_linha), itens[k:k + por_linha]):
            col.markdown(tema.card_status(rot, val, cls, det[0] if det else "", det[1] if len(det) > 1 else ""), unsafe_allow_html=True)


def _grafico(fig, altura: int = 340):
    fig.update_layout(height=altura, template="plotly_white", font=dict(color="#16202B"), legend=dict(orientation="h", y=-0.2), **TRANSP)
    fig.update_xaxes(gridcolor="rgba(22,32,43,0.10)", zerolinecolor="rgba(22,32,43,0.25)")
    fig.update_yaxes(gridcolor="rgba(22,32,43,0.10)", zerolinecolor="rgba(22,32,43,0.25)")
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def _agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _guardar(chave: str, valor):
    c = _ss().setdefault(CTX, {})
    c[chave] = valor
    c["gerado_em"] = _agora()


# ------------------------------------------------------------------ entradas
def _pct_in(rotulo: str, padrao: float, chave: str, minimo: float = -50.0, maximo: float = 200.0, passo: float = 0.5, ajuda: str | None = None) -> float:
    """Campo em % que devolve fração (10 → 0,10)."""
    v = st.number_input(rotulo, min_value=minimo, max_value=maximo, step=passo, format="%.2f", key=chave, help=ajuda, **_opt(chave, "value", float(padrao * 100)))
    return float(v) / 100.0


def _valor_in(rotulo: str, padrao: float, chave: str, minimo: float = 0.0, passo: float = 100.0, ajuda: str | None = None) -> float:
    return float(st.number_input(rotulo, min_value=minimo, step=passo, format="%.2f", key=chave, help=ajuda, **_opt(chave, "value", float(padrao))))


def _taxa_in(pref: str, padrao: float = 0.10) -> float:
    """Taxa de rentabilidade com a convenção explícita (efetiva a.a., nominal capitalizada ou efetiva a.m.). Devolve efetiva a.a."""
    c1, c2 = st.columns([2, 3])
    tipo = c1.selectbox("Tipo de taxa", ["Efetiva ao ano", "Nominal ao ano (capitalização mensal)", "Efetiva ao mês"], key=f"{pref}_tt",
                        help="Efetiva: juros sobre juros (padrão do app). Nominal: o banco divide por 12 e capitaliza. Escolha a que consta no seu produto.")
    if tipo == "Efetiva ao mês":
        with c2:
            m = _pct_in("Taxa ao mês (%)", S.mensal(padrao), f"{pref}_tm", -20.0, 30.0, 0.05)
        return S.anual(m)
    with c2:
        v = _pct_in("Taxa ao ano (%)", padrao, f"{pref}_ta", -50.0, 300.0, 0.25)
    return S.nominal_para_efetiva(v, 12) if tipo.startswith("Nominal") else v


def _aliquota_in(pref: str, tipo: str) -> float | None:
    if tipo == "personalizado":
        return _pct_in("Alíquota sobre o ganho (%)", 0.15, f"{pref}_aliq", 0.0, 100.0, 0.5)
    return None


def _extras_in(pref: str, meses_max: int) -> list[dict]:
    st.caption("Aportes extraordinários (13º, bônus, venda de bem...): mês da projeção e valor. Saque: valor negativo.")
    df0 = pd.DataFrame({"mes": pd.Series(dtype="int64"), "valor": pd.Series(dtype="float64")})
    ed = st.data_editor(df0, num_rows="dynamic", key=f"{pref}_ex", width="stretch",
                        column_config={"mes": st.column_config.NumberColumn("Mês", min_value=1, max_value=max(meses_max, 1), step=1),
                                       "valor": st.column_config.NumberColumn("Valor (R$)", step=100.0, format="%.2f")})
    out = []
    for _, r in (ed if ed is not None else df0).iterrows():
        if pd.notna(r.get("mes")) and pd.notna(r.get("valor")) and int(r["mes"]) >= 1 and float(r["valor"]) != 0:
            out.append({"mes": int(r["mes"]), "valor": float(r["valor"])})
    return out


def _bloco_basico(pref: str, titulo_taxa: bool = True, avancado: bool = True, padrao: dict | None = None, so_taxa_e_frequencia: bool = False) -> dict:
    """Premissas comuns de uma projeção. Devolve os parâmetros de S.projetar()."""
    d = {"inicial": 10000.0, "aporte": 1000.0, "anos": 10, "taxa": 0.10, "infl": 0.045, **(padrao or {})}
    if so_taxa_e_frequencia:
        # capital inicial, prazo e valor do aporte já foram pedidos acima pela aba (o aporte é o resultado)
        c1, c2, c3 = st.columns(3)
        inicial, aporte, anos = float(d["inicial"]), 0.0, float(d["anos"])
        with c1:
            freq = st.selectbox("Frequência do aporte", list(FREQ_ROT), index=2, format_func=FREQ_ROT.get, key=f"{pref}_fq")
        with c2:
            momento = st.radio("Momento do aporte", list(MOMENTO_ROT), format_func=MOMENTO_ROT.get, horizontal=True, key=f"{pref}_mom",
                               help="Início do período rende um período a mais que o fim.")
        with c3:
            infl = _pct_in("Inflação estimada (% a.a.)", d["infl"], f"{pref}_inf", -5.0, 100.0, 0.25)
    else:
        c1, c2, c3 = st.columns(3)
        with c1:
            inicial = _valor_in("Capital inicial (R$)", d["inicial"], f"{pref}_ini", 0.0, 1000.0)
        with c2:
            aporte = _valor_in("Valor do aporte (R$)", d["aporte"], f"{pref}_ap", 0.0, 50.0)
        with c3:
            freq = st.selectbox("Frequência do aporte", list(FREQ_ROT), index=2, format_func=FREQ_ROT.get, key=f"{pref}_fq")
        c1, c2, c3 = st.columns(3)
        with c1:
            anos = st.number_input("Prazo (anos)", min_value=0.0, max_value=80.0, step=0.5, key=f"{pref}_anos", **_opt(f"{pref}_anos", "value", float(d["anos"])))
        with c2:
            momento = st.radio("Momento do aporte", list(MOMENTO_ROT), format_func=MOMENTO_ROT.get, horizontal=True, key=f"{pref}_mom",
                               help="Início do período rende um período a mais que o fim.")
        with c3:
            infl = _pct_in("Inflação estimada (% a.a.)", d["infl"], f"{pref}_inf", -5.0, 100.0, 0.25)
    taxa = _taxa_in(pref, d["taxa"]) if titulo_taxa else d["taxa"]
    p = {"inicial": inicial, "aporte": aporte, "freq": freq, "momento": momento, "meses": int(round(anos * 12)), "taxa_aa": taxa, "inflacao": infl}
    if avancado:
        with st.expander("Impostos, custos, rendimentos e aportes extraordinários"):
            e1, e2 = st.columns(2)
            with e1:
                ir = st.selectbox("Imposto de renda", list(S.TIPOS_IR), format_func=S.TIPOS_IR.get, index=list(S.TIPOS_IR).index("isento"), key=f"{pref}_ir")
                p["ir"] = ir
                p["aliquota"] = _aliquota_in(pref, ir)
                if ir == "rf":
                    p["tipo_rf"] = "cdb"
                p["custo_aa"] = _pct_in("Taxa de administração/custódia (% a.a.)", 0.0, f"{pref}_cu", 0.0, 10.0, 0.05)
            with e2:
                p["custo_aporte"] = _pct_in("Custo por aporte (corretagem, % do aporte)", 0.0, f"{pref}_ca", 0.0, 10.0, 0.05)
                ra = st.selectbox("Reajuste do aporte", ["Sem reajuste", "Pela inflação", "Percentual fixo ao ano"], key=f"{pref}_ra")
                p["reajuste_aporte"] = "inflacao" if ra == "Pela inflação" else (_pct_in("Reajuste anual do aporte (%)", 0.05, f"{pref}_rf", 0.0, 50.0, 0.5) if ra.startswith("Perc") else None)
            f1, f2 = st.columns(2)
            with f1:
                p["dy_aa"] = _pct_in("Rendimentos distribuídos (% do patrimônio a.a.)", 0.0, f"{pref}_dy", 0.0, 50.0, 0.25,
                                     "Dividendos/aluguéis/proventos pagos à parte do preço. A taxa acima é a variação do preço.")
            with f2:
                p["reinvestir"] = st.checkbox("Reinvestir os rendimentos", value=True, key=f"{pref}_re")
            p["extras"] = _extras_in(pref, p["meses"])
    return p


def _mercado() -> dict:
    """CDI, IPCA e Selic do Banco Central (com cache da própria coleta). Nunca levanta: sem dado, devolve None e a tela avisa."""
    ss = _ss()
    if "_sim_mercado" not in ss:
        try:
            import renda_fixa_app as rfa
            m = rfa.mercado()
            ss["_sim_mercado"] = {"cdi": m.get("cdi_aa"), "ipca": m.get("ipca_12m"), "selic": m.get("selic"), "avisos": m.get("avisos", []),
                                  "cdi_idx": m.get("cdi_idx"), "ipca_serie": m.get("ipca")}
        except Exception as e:
            log.warning("mercado indisponível: %s", e)
            ss["_sim_mercado"] = {"cdi": None, "ipca": None, "selic": None, "avisos": ["Banco Central indisponível agora: usei pontos de partida editáveis."],
                                  "cdi_idx": None, "ipca_serie": None}
    return ss["_sim_mercado"]


def _macro_editavel(pref: str) -> dict:
    """Cenários macro (CDI/IPCA) com a possibilidade de editar cada um."""
    m = _mercado()
    macro = S.macro_cenarios(m["cdi"], m["ipca"])
    st.caption(f"Cenários macroeconômicos: {macro['origem']}.")
    with st.expander("Editar CDI e inflação de cada cenário"):
        for c in S.CENARIOS:
            a, b = st.columns(2)
            with a:
                macro[c]["cdi"] = _pct_in(f"CDI · {S.NOMES_CENARIO[c]} (% a.a.)", macro[c]["cdi"], f"{pref}_cdi_{c}", 0.0, 60.0, 0.25)
            with b:
                macro[c]["ipca"] = _pct_in(f"IPCA · {S.NOMES_CENARIO[c]} (% a.a.)", macro[c]["ipca"], f"{pref}_ipca_{c}", -5.0, 60.0, 0.25)
    for a in m["avisos"][:2]:
        st.caption(a)
    return macro


def _avisos(res: dict | None = None):
    st.caption(S.AVISO)


# ------------------------------------------------------------------ saídas comuns
def _resumo_cartoes(r: dict):
    _cartoes([("Patrimônio líquido", _brl(r["total_liquido"]), "info", f"bruto {_brl(r['patrimonio_bruto'])} · imposto {_brl(r['imposto'])}"),
              ("Total investido", _brl(r["total_investido"]), "na"),
              ("Rendimentos líquidos", _brl(r["rendimentos_liquidos"]), "good" if r["rendimentos_liquidos"] >= 0 else "bad"),
              ("Valor de hoje (real)", _brl(r["valor_real"]), "fair", f"inflação média {_p(r.get('inflacao_media_aa'))} a.a.")])
    _cartoes([("Rentabilidade acumulada", _p(r.get("rentabilidade_acumulada")), "info", "líquida, sobre o investido"),
              ("Rentabilidade anualizada", _p(r.get("rentabilidade_anualizada")), "info", "TIR, considera quando cada aporte entrou"),
              ("Anualizada real", _p(r.get("rentabilidade_real_anualizada")), "fair", "acima da inflação (Fisher)"),
              ("Renda recebida", _brl(r.get("renda_recebida", 0.0)), "na", "rendimentos não reinvestidos")])


def _grafico_evolucao(df: pd.DataFrame, real: bool = True, titulo: str = "Evolução do patrimônio"):
    fig = go.Figure()
    x = df["mes"] / 12.0
    fig.add_scatter(x=x, y=df["investido"], name="Total investido", line=dict(color=COR["investido"], dash="dot"))
    fig.add_scatter(x=x, y=df["total_liquido"], name="Patrimônio líquido", line=dict(color=COR["liquido"], width=3))
    if real:
        fig.add_scatter(x=x, y=df["total_real"], name="Em valores de hoje", line=dict(color=COR["real"]))
    fig.update_layout(title=titulo, xaxis_title="Anos", yaxis_title="R$")
    _grafico(fig)


def _tabela_anual(df: pd.DataFrame):
    t = S.tabela_anual(df)
    if t.empty:
        return
    v = pd.DataFrame({"Ano": t["ano"], "Investido": t["investido"].map(_brl), "Rendimentos acumulados": (t["total_liquido"] - t["investido"]).map(_brl),
                      "Patrimônio líquido": t["total_liquido"].map(_brl), "Em valores de hoje": t["total_real"].map(_brl)})
    st.dataframe(v, hide_index=True, width="stretch")
    with st.expander("Evolução mensal"):
        m = df[["mes", "investido", "total_liquido", "total_real"]].copy()
        m.columns = ["Mês", "Investido", "Patrimônio líquido", "Em valores de hoje"]
        for c in m.columns[1:]:
            m[c] = m[c].map(_brl)
        st.dataframe(m, hide_index=True, width="stretch")


# ------------------------------------------------------------------ 1 · juros compostos
def _aba_juros():
    st.markdown("##### Calculadora de juros compostos")
    p = _bloco_basico("sj")
    res = S.projetar(p)
    r = res["resumo"]
    _resumo_cartoes(r)
    _grafico_evolucao(res["df"])
    df = res["df"]
    fig = go.Figure()
    x = df["mes"] / 12.0
    fig.add_bar(x=x, y=df["investido"], name="Aportes", marker_color=COR["investido"])
    fig.add_bar(x=x, y=(df["total_liquido"] - df["investido"]).clip(lower=0), name="Rendimentos acumulados", marker_color=COR["renda"])
    fig.update_layout(barmode="stack", title="Aportes × rendimentos acumulados", xaxis_title="Anos", yaxis_title="R$")
    _grafico(fig, 300)
    _tabela_anual(df)
    ref = S.valor_futuro_formula(p["inicial"], p["aporte"], p["meses"], p["taxa_aa"], p["momento"]) if (p["freq"] == "mensal" and not p.get("extras") and not p.get("custo_aa")
                                                                                                           and not p.get("dy_aa") and not p.get("reajuste_aporte") and not p.get("custo_aporte")) else None
    if ref is not None:
        st.caption(f"Conferência pela fórmula fechada (sem impostos): {_brl(ref)} · patrimônio bruto da projeção: {_brl(r['patrimonio_bruto'])}.")
    with st.expander("Risco: faixa de resultados (Monte Carlo)"):
        vol = _pct_in("Volatilidade anual estimada (%)", 0.15, "sj_vol", 0.0, 200.0, 1.0, "Hipótese; use a da classe na aba Por classe.")
        if vol > 0 and p["meses"] > 0:
            mc = S.monte_carlo(p, vol, 2000, meta=None, aliquota=0.0)
            if mc.get("ok"):
                _cartoes([("Pior caso comum (P10)", _brl(mc["p10"]), "bad", "10% dos caminhos ficam abaixo"), ("Mediana (P50)", _brl(mc["p50"]), "info"),
                          ("Melhor caso comum (P90)", _brl(mc["p90"]), "good", "10% ficam acima"), ("Chance de terminar abaixo do investido", _p(mc["prob_abaixo_investido"], 1), "fair")], 4)
                st.caption("2.000 caminhos aleatórios com semente fixa; antes de impostos. É uma faixa de possibilidades, não uma previsão.")
    _guardar("juros", {"p": p, "resumo": r})
    _avisos()


# ------------------------------------------------------------------ 2 · aposentadoria
def _aba_aposentadoria():
    st.markdown("##### Planejamento de aposentadoria")
    c1, c2, c3 = st.columns(3)
    with c1:
        pat = _valor_in("Patrimônio atual (R$)", 50000.0, "sa_pat", 0.0, 1000.0)
        idade = st.number_input("Idade atual", 15, 90, key="sa_id", **_opt("sa_id", "value", 30))
    with c2:
        apos = st.number_input("Idade para se aposentar", 20, 100, key="sa_ap", **_opt("sa_ap", "value", 60))
        fim = st.number_input("Patrimônio deve durar até (idade)", 30, 120, key="sa_fim", **_opt("sa_fim", "value", 90),
                              help="Expectativa de duração do patrimônio.")
    with c3:
        aporte = _valor_in("Aporte periódico (R$)", 1500.0, "sa_aporte", 0.0, 50.0)
        freq = st.selectbox("Frequência do aporte", list(FREQ_ROT), index=2, format_func=FREQ_ROT.get, key="sa_fq")
    c1, c2, c3 = st.columns(3)
    with c1:
        renda = _valor_in("Renda mensal desejada (R$ de hoje)", 8000.0, "sa_renda", 0.0, 500.0, "Líquida, em poder de compra de hoje.")
    with c2:
        infl = _pct_in("Inflação estimada (% a.a.)", 0.045, "sa_inf", 0.0, 50.0, 0.25)
    with c3:
        custo = _pct_in("Custos (% a.a.)", 0.0, "sa_cu", 0.0, 10.0, 0.05)
    c1, c2, c3 = st.columns(3)
    with c1:
        t1 = _pct_in("Rentabilidade até aposentar (% a.a., nominal)", 0.10, "sa_t1", -20.0, 100.0, 0.25)
    with c2:
        t2 = _pct_in("Rentabilidade depois (% a.a., nominal)", 0.08, "sa_t2", -20.0, 100.0, 0.25)
    with c3:
        aliq = _pct_in("Imposto sobre os saques (%)", 0.0, "sa_aliq", 0.0, 50.0, 0.5)
    if apos <= idade:
        st.warning("A idade de aposentadoria precisa ser maior que a idade atual.")
        return
    if fim <= apos:
        st.warning("A idade-limite do patrimônio precisa ser maior que a de aposentadoria.")
        return
    p = {"patrimonio_atual": pat, "idade_atual": idade, "idade_apos": apos, "idade_fim": fim, "aporte": aporte, "freq": freq, "renda_desejada": renda, "inflacao": infl,
         "taxa_acum_aa": t1, "taxa_apos_aa": t2, "custo_aa": custo, "aliquota_saque": aliq}
    r = S.aposentadoria(p)
    ok = r["suficiente"]
    _cartoes([("Patrimônio necessário", _brl(r["necessario_real"]), "info", f"nominal na aposentadoria: {_brl(r['necessario_nominal'])}"),
              ("Patrimônio projetado", _brl(r["patrimonio_real"]), "good" if ok else "bad", f"nominal: {_brl(r['patrimonio_nominal'])}"),
              ("Falta (valores de hoje)" if not ok else "Sobra (valores de hoje)", _brl(abs(r["lacuna_real"])), "bad" if not ok else "good"),
              ("Renda mensal possível", _brl(r["renda_possivel_real"]), "info", f"nominal: {_brl(r['renda_possivel_nominal'])}")])
    ap = r["aporte_necessario"]
    _cartoes([("Aporte necessário", "já suficiente" if ap.get("ja_atinge") else (_brl(ap["aporte"]) if ap.get("aporte") is not None else "inviável"), "info", f"{FREQ_ROT[freq].lower()}, corrigido pela inflação"),
              ("Idade estimada de alcance", f"{r['idade_alcance']:.1f} anos" if r["idade_alcance"] else "não atinge", "fair", "mantendo o aporte atual"),
              ("Taxa de retirada inicial", _p(r["taxa_retirada_inicial"], 1), "fair", f"retorno real: {_p(r['retorno_real_aposentadoria'])}"),
              ("Sustentabilidade", "dura até a idade-limite" if r["dura_ate_idade_fim"] else f"esgota aos {r['idade_esgotamento']:.1f} anos", "good" if r["dura_ate_idade_fim"] else "bad",
               "retirada perpétua" if r["retirada_perpetua"] else "consome o capital")])
    dec = r["decumulacao"]
    pr = r["projecao"]["df"]
    fig = go.Figure()
    fig.add_scatter(x=idade + pr["mes"] / 12.0, y=pr["total_real"], name="Acumulação (valores de hoje)", line=dict(color=COR["real"], width=3))
    if isinstance(dec.get("df"), pd.DataFrame) and len(dec["df"]):
        d = dec["df"]
        # em valores de hoje: deflaciona pelo índice de preços desde HOJE (acumulação + meses de saque), não só desde a aposentadoria
        F = S.fatores_inflacao(infl, r["meses_acumulacao"] + r["meses_saque"])
        real_saque = d["patrimonio"].to_numpy() / F[r["meses_acumulacao"] + d["mes"].to_numpy().astype(int)]
        fig.add_scatter(x=apos + d["mes"] / 12.0, y=real_saque, name="Saques (valores de hoje)", line=dict(color=COR["renda"], width=3))
    fig.add_hline(y=r["necessario_real"], line_dash="dash", line_color=COR["alt"], annotation_text="necessário")
    fig.update_layout(title="Patrimônio da acumulação à aposentadoria", xaxis_title="Idade", yaxis_title="R$ de hoje")
    _grafico(fig)
    st.markdown("**E se der errado? Cenários de insuficiência**")
    cen = S.cenarios_aposentadoria(p, (-3.0, 0.0, 2.0), (infl, infl + 0.02))
    tb = pd.DataFrame([{"Cenário": c["rotulo"], "Suficiente?": "sim" if c["suficiente"] else "não",
                        "Patrimônio dura até": "idade-limite" if c["idade_esgotamento"] is None else f"{c['idade_esgotamento']:.1f} anos",
                        "Lacuna (valores de hoje)": _brl(c["lacuna_real"]), "Renda possível": _brl(c["renda_possivel_real"])} for c in cen])
    st.dataframe(tb, hide_index=True, width="stretch")
    _guardar("aposentadoria", r)
    _avisos()


# ------------------------------------------------------------------ 3 · renda passiva
def _aba_renda():
    st.markdown("##### Simulador de renda passiva")
    st.caption("Informe o patrimônio de cada fonte e o yield recorrente. Distribuições NÃO são constantes: elas crescem na taxa informada e você pode simular um corte.")
    padrao = pd.DataFrame([
        {"Fonte": "Dividendos de ações", "Classe": "acao", "Patrimônio (R$)": 50000.0, "Yield a.a. (%)": 5.0, "Cresc. dos proventos a.a. (%)": 4.5, "Valorização a.a. (%)": 6.0, "Aporte mensal (R$)": 500.0, "IR sobre proventos (%)": 0.0},
        {"Fonte": "Rendimentos de FIIs", "Classe": "fii", "Patrimônio (R$)": 50000.0, "Yield a.a. (%)": 9.0, "Cresc. dos proventos a.a. (%)": 4.0, "Valorização a.a. (%)": 3.0, "Aporte mensal (R$)": 500.0, "IR sobre proventos (%)": 0.0},
    ])
    ed = st.data_editor(padrao, num_rows="dynamic", key="sr_fontes", width="stretch", column_config={
        "Classe": st.column_config.SelectboxColumn("Classe", options=list(S.FONTES_RENDA), required=True)})
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        anos = st.number_input("Prazo (anos)", 1, 60, key="sr_anos", **_opt("sr_anos", "value", 10))
    with c2:
        infl = _pct_in("Inflação (% a.a.)", 0.045, "sr_inf", 0.0, 50.0, 0.25)
    with c3:
        desejada = _valor_in("Renda mensal desejada (R$)", 5000.0, "sr_des", 0.0, 100.0)
    with c4:
        reinv = st.checkbox("Reinvestir os rendimentos", value=True, key="sr_re")
    c1, c2 = st.columns(2)
    with c1:
        corte = st.slider("Corte nas distribuições (%)", 0, 100, 0, key="sr_corte", help="Simula queda de dividendos/aluguéis.")
    with c2:
        corte_ano = st.number_input("Corte a partir do ano", 1, 60, key="sr_cano", **_opt("sr_cano", "value", 2))
    with st.expander("Pagamentos extraordinários (não entram no yield)"):
        ex = _extras_in("sr", anos * 12)
    fontes = []
    for _, l in ed.iterrows():
        if pd.isna(l.get("Patrimônio (R$)")) or float(l["Patrimônio (R$)"]) <= 0:
            continue
        fontes.append({"nome": l.get("Fonte") or "Fonte", "classe": l.get("Classe") or "outros", "patrimonio": float(l["Patrimônio (R$)"]),
                       "yield_aa": float(l.get("Yield a.a. (%)") or 0) / 100.0, "cresc_dist_aa": float(l.get("Cresc. dos proventos a.a. (%)") or 0) / 100.0,
                       "valorizacao_aa": float(l.get("Valorização a.a. (%)") or 0) / 100.0, "aporte_mensal": float(l.get("Aporte mensal (R$)") or 0),
                       "ir_dist": float(l.get("IR sobre proventos (%)") or 0) / 100.0, "extras": ex if not fontes else []})
    if not fontes:
        st.info("Adicione ao menos uma fonte com patrimônio maior que zero.")
        return
    r = S.renda_passiva(fontes, anos, infl, reinv, corte, corte_ano, desejada or None)
    sem_corte = S.renda_passiva(fontes, anos, infl, reinv, 0.0, 1, desejada or None) if corte else None
    _cartoes([("Renda mensal hoje", _brl(r["renda_mensal_inicial"]), "info", f"anual {_brl(r['renda_anual_inicial'])}"),
              ("Yield médio", _p(r["yield_medio"]), "info", "líquido de IR sobre proventos"),
              ("Renda mensal no fim", _brl(r["renda_mensal_final"]), "good", f"em valores de hoje: {_brl(r['renda_mensal_final_real'])}"),
              ("Patrimônio no fim", _brl(r["patrimonio_final"]), "fair")])
    if r["patrimonio_necessario"]:
        st.markdown(f"Para **{_brl(desejada)}/mês** com o yield médio atual ({_p(r['yield_medio'])}) seria preciso **{_brl(r['patrimonio_necessario'])}** investidos. "
                    f"Patrimônio projetado no fim: {_brl(r['patrimonio_final'])}.")
    pa = r["por_ano"]
    fig = go.Figure()
    fig.add_bar(x=pa["ano"], y=pa["renda_recorrente"] / 12.0, name="Renda recorrente média/mês", marker_color=COR["renda"])
    if r["extraordinario_total"]:
        fig.add_bar(x=pa["ano"], y=pa["renda_extraordinaria"] / 12.0, name="Extraordinária média/mês", marker_color=COR["alt"])
    fig.add_scatter(x=pa["ano"], y=pa["renda_real"] / 12.0, name="Recorrente em valores de hoje", line=dict(color=COR["real"]))
    if sem_corte is not None:
        fig.add_scatter(x=sem_corte["por_ano"]["ano"], y=sem_corte["por_ano"]["renda_recorrente"] / 12.0, name="Sem corte", line=dict(color=COR["investido"], dash="dot"))
    fig.update_layout(title="Evolução da renda mensal", xaxis_title="Ano", yaxis_title="R$/mês", barmode="stack")
    _grafico(fig)
    st.dataframe(pd.DataFrame([{"Fonte": f["nome"], "Patrimônio": _brl(f["patrimonio"]), "Yield": _p(f["yield_aa"]), "Renda mensal hoje": _brl(f["renda_mensal"])} for f in r["por_fonte"]]),
                 hide_index=True, width="stretch")
    _guardar("renda", {"mensal_inicial": r["renda_mensal_inicial"], "mensal_final": r["renda_mensal_final"], "anual_final": r["renda_mensal_final"] * 12.0,
                       "yield_inicial": r["yield_medio"], "patrimonio_necessario": r["patrimonio_necessario"]})
    _avisos()


# ------------------------------------------------------------------ 4 · aportes e metas
def _metas() -> list:
    return _ss().setdefault(CH_METAS, [])


def _aba_metas():
    st.markdown("##### Quanto preciso investir para chegar lá?")
    c1, c2, c3 = st.columns(3)
    with c1:
        tipo_meta = st.selectbox("Objetivo", ["Valor-alvo", "Renda mensal desejada", "Independência financeira (cobrir despesas)", "Reserva de emergência"], key="sm_tipo")
    with c2:
        inicial = _valor_in("Patrimônio inicial (R$)", 20000.0, "sm_ini", 0.0, 1000.0)
    with c3:
        anos = st.number_input("Prazo (anos)", 0.5, 60.0, step=0.5, key="sm_anos", **_opt("sm_anos", "value", 10.0))
    if tipo_meta == "Valor-alvo":
        meta_hoje = _valor_in("Meta (R$ de hoje)", 500000.0, "sm_meta", 0.0, 10000.0)
        st.caption("Exemplos de meta: 100 mil, 500 mil ou 1 milhão de reais. Edite o campo acima.")
    elif tipo_meta == "Renda mensal desejada":
        renda = _valor_in("Renda mensal desejada (R$)", 5000.0, "sm_renda", 0.0, 100.0)
        y = _pct_in("Yield esperado do patrimônio (% a.a.)", 0.08, "sm_y", 0.5, 30.0, 0.25)
        meta_hoje = S.patrimonio_para_renda(renda, y) or 0.0
        st.caption(f"Patrimônio para gerar {_brl(renda)}/mês com yield {_p(y)}: {_brl(meta_hoje)}.")
    elif tipo_meta.startswith("Independ"):
        desp = _valor_in("Despesa mensal (R$)", 6000.0, "sm_desp", 0.0, 100.0)
        tr = _pct_in("Taxa de retirada anual (%)", 0.04, "sm_tr", 1.0, 15.0, 0.25, "Regra dos 4%: patrimônio = despesa anual ÷ taxa de retirada.")
        meta_hoje = S.valor_independencia(desp, tr)
        st.caption(f"Patrimônio de independência: {_brl(meta_hoje)} (despesa anual {_brl(desp * 12)} ÷ {_p(tr)}).")
    else:
        desp = _valor_in("Despesa mensal essencial (R$)", 4000.0, "sm_desp2", 0.0, 100.0)
        n = st.slider("Meses de cobertura", 3, 24, 6, key="sm_mc")
        meta_hoje = S.valor_reserva(desp, n)
        st.caption(f"Reserva de {n} meses: {_brl(meta_hoje)}.")
    p = _bloco_basico("smb", avancado=True, padrao={"inicial": inicial, "aporte": 0.0, "anos": anos}, so_taxa_e_frequencia=True)
    p.pop("aporte", None)
    p["meses"] = int(round(anos * 12))
    p["inicial"] = inicial
    corrigir = st.checkbox("Corrigir a meta pela inflação até o prazo", value=True, key="sm_corr")
    n = p["meses"]
    meta_nom = meta_hoje * S.fatores_inflacao(p["inflacao"], n)[n] if corrigir and n > 0 else meta_hoje
    ap = S.aporte_necessario(meta_nom, {**p, "aporte": 0.0, "freq": p["freq"]}, real=False)
    if ap["ja_atinge"]:
        st.success(f"Com as premissas atuais, o capital inicial sozinho chega a {_brl(ap['total'])} no prazo: nenhum aporte é necessário.")
    elif not ap["viavel"]:
        st.error("Não há aporte viável (acima de R$ 1 bilhão) com essas premissas.")
    else:
        fc = S.aporte_formula_fechada(meta_nom, inicial, n, p["taxa_aa"], p["momento"]) if (p["freq"] == "mensal" and not p.get("extras") and not p.get("custo_aa") and not p.get("custo_aporte")
                                                                                         and not p.get("dy_aa") and p.get("ir", "isento") == "isento" and not p.get("reajuste_aporte")) else None
        _cartoes([("Aporte necessário", _brl(ap["aporte"]), "info", f"{FREQ_ROT[p['freq']].lower()} · fim do prazo: {_brl(ap['total'])}"),
                  ("Meta no prazo", _brl(meta_nom), "fair", f"hoje: {_brl(meta_hoje)}" + (" · corrigida pela inflação" if corrigir else "")),
                  ("Total aportado", _brl(S.projetar({**p, "aporte": ap["aporte"]}, detalhado=False)["resumo"]["total_investido"]), "na"),
                  ("Conferência (fórmula fechada)", _brl(fc) if fc is not None else "n/d", "na", "só no caso simples: mensal, sem impostos/custos")])
        st.markdown("**Mude as premissas e veja o efeito no aporte:**")
        linhas = []
        for dpp in (-3.0, -1.0, 0.0, 1.0, 3.0):
            q = {**p, "taxa_aa": p["taxa_aa"] + dpp / 100.0}
            a = S.aporte_necessario(meta_nom, {**q, "aporte": 0.0}, real=False)
            linhas.append({"Rentabilidade": _p(q["taxa_aa"]), "Variação": f"{dpp:+.0f} p.p.", "Aporte necessário": _brl(a["aporte"]) if a["aporte"] is not None else "inviável"})
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    st.divider()
    _painel_metas()
    _avisos()


def _painel_metas():
    st.markdown("##### Painel de metas")
    metas = _metas()
    with st.expander("Cadastrar nova meta", expanded=not metas):
        c1, c2 = st.columns(2)
        with c1:
            nome = st.text_input("Nome", key="sp_nome", max_chars=60, placeholder="Ex.: Reserva de emergência")
            tipo = st.selectbox("Tipo", list(S.TIPOS_META), format_func=S.TIPOS_META.get, key="sp_tipo")
            alvo = _valor_in("Valor necessário (R$ de hoje)", 30000.0, "sp_alvo", 0.0, 1000.0)
        with c2:
            prazo = st.date_input("Prazo", value=date.today() + timedelta(days=365 * 3), min_value=date.today() + timedelta(days=1), key="sp_prazo")
            acum = _valor_in("Já acumulado (R$)", 0.0, "sp_acum", 0.0, 100.0)
            aporte = _valor_in("Aporte mensal planejado (R$)", 500.0, "sp_aporte", 0.0, 50.0)
        c1, c2, c3 = st.columns(3)
        with c1:
            taxa = _pct_in("Rentabilidade líquida estimada (% a.a.)", 0.08, "sp_taxa", -20.0, 100.0, 0.25)
        with c2:
            infl = _pct_in("Inflação (% a.a.)", 0.045, "sp_inf", 0.0, 50.0, 0.25)
        with c3:
            corr = st.checkbox("Corrigir pela inflação", value=True, key="sp_corr")
        if st.button("Adicionar meta", key="sp_add", type="primary", icon=":material/add:"):
            if not nome.strip():
                st.warning("Dê um nome à meta.")
            elif alvo <= 0:
                st.warning("O valor necessário precisa ser maior que zero.")
            else:
                metas.append(S.nova_meta(nome.strip(), tipo, alvo, prazo, acum, aporte, taxa, infl, corr))
                st.rerun()
    if not metas:
        st.markdown(tema.vazio("alvo", "Nenhuma meta cadastrada", "Cadastre reserva de emergência, imóvel, aposentadoria... e acompanhe várias metas ao mesmo tempo."), unsafe_allow_html=True)
        return
    ava = [S.avaliar_meta(m) for m in metas]
    st.dataframe(pd.DataFrame([{"Meta": a["nome"], "Tipo": S.TIPOS_META.get(a["tipo"], a["tipo"]), "Necessário (hoje)": _brl(a["alvo_hoje"]), "Acumulado": _brl(a["acumulado"]),
                                "Atingido": _p(a["pct"], 1), "Prazo": a["prazo"], "Meses": a["meses_restantes"], "Aporte necessário": _brl(a["aporte_necessario"]),
                                "Aporte planejado": _brl(a["aporte_planejado"]), "Situação": a["status"]} for a in ava]), hide_index=True, width="stretch")
    fig = go.Figure()
    fig.add_bar(y=[a["nome"] for a in ava], x=[min((a["pct"] or 0) * 100, 100) for a in ava], orientation="h", marker_color=COR["liquido"], name="% atingido")
    fig.update_layout(title="Progresso das metas", xaxis=dict(range=[0, 100], title="%"))
    _grafico(fig, 120 + 45 * len(ava))
    esc = st.selectbox("Atualizar ou ver a evolução de uma meta", range(len(metas)), format_func=lambda i: metas[i]["nome"], key="sp_esc")
    m = metas[esc]
    a1, a2, a3 = st.columns([2, 1, 1])
    with a1:
        novo = _valor_in("Novo valor acumulado (R$)", float(m.get("acumulado") or 0.0), f"sp_novo_{m['id']}", 0.0, 100.0)
    with a2:
        if st.button("Registrar progresso", key="sp_reg", icon=":material/check:"):
            metas[esc] = S.registrar_progresso(m, novo)
            st.rerun()
    with a3:
        if st.button("Remover meta", key="sp_del", icon=":material/delete:"):
            metas.pop(esc)
            st.rerun()
    h = pd.DataFrame(m.get("historico", []))
    if len(h) > 1:
        fig = go.Figure()
        fig.add_scatter(x=h["data"], y=h["valor"], mode="lines+markers", name="Acumulado", line=dict(color=COR["real"]))
        fig.add_hline(y=m["alvo"], line_dash="dash", line_color=COR["alt"], annotation_text="meta")
        fig.update_layout(title=f"Evolução: {m['nome']}", yaxis_title="R$")
        _grafico(fig, 260)
    _guardar("metas", ava)


# ------------------------------------------------------------------ 5 · por classe
def _prem_salvas() -> dict:
    return _ss().setdefault(CH_PREM, {})


def _editor_classe(classe: str, cenario: str, macro: dict, rf_cfg: dict | None, pref: str):
    """Mostra as premissas da classe no cenário e deixa editar; devolve os ajustes (ou None)."""
    pr = S.premissas_classe(classe, cenario, macro, rf_cfg)
    salvo = _prem_salvas().get(f"{classe}|{cenario}") or {}
    with st.expander(f"Premissas de {pr['nome']} no cenário {S.NOMES_CENARIO[cenario]} (hipóteses — edite)"):
        st.caption("; ".join(v for v in pr["rotulos"].values()))
        c1, c2, c3 = st.columns(3)
        with c1:
            taxa = _pct_in("Variação do preço/índice (% a.a. nominal)", salvo.get("taxa_aa", pr["taxa_aa"]), f"{pref}_t_{classe}_{cenario}", -80.0, 300.0, 0.25)
        with c2:
            dy = _pct_in("Yield das distribuições (% a.a.)", salvo.get("dy_aa", pr.get("dy_aa", 0.0)), f"{pref}_y_{classe}_{cenario}", 0.0, 50.0, 0.25) if classe != "renda_fixa" else 0.0
        with c3:
            custo = _pct_in("Custos (% a.a.)", salvo.get("custo_aa", pr.get("custo_aa", 0.0)), f"{pref}_c_{classe}_{cenario}", 0.0, 10.0, 0.05)
        aj = {"taxa_aa": taxa, "dy_aa": dy, "custo_aa": custo}
        if classe != "renda_fixa" and dy:
            aj["cresc_dist_aa"] = _pct_in("Crescimento dos proventos (% a.a. nominal)", salvo.get("cresc_dist_aa", pr.get("cresc_dist_aa") or taxa), f"{pref}_g_{classe}_{cenario}", -50.0, 100.0, 0.25)
        alter = any(abs(aj[k] - pr.get(k, 0.0)) > 1e-9 for k in ("taxa_aa", "dy_aa", "custo_aa"))
        if st.button("Guardar estas premissas", key=f"{pref}_sv_{classe}_{cenario}"):
            _prem_salvas()[f"{classe}|{cenario}"] = aj
            st.success("Premissas guardadas.")
        st.markdown(f"**Riscos relevantes:** {pr['riscos']}")
        st.caption(pr["notas"])
    return aj if (alter or salvo) else None


def _rf_cfg_in(pref: str) -> dict:
    c1, c2, c3 = st.columns(3)
    with c1:
        ind = st.selectbox("Indexador", list(S.INDEXADORES_RF), format_func=S.INDEXADORES_RF.get, key=f"{pref}_ind")
    with c2:
        if ind == "cdi_pct":
            taxa = _pct_in("% do CDI", 1.0, f"{pref}_pcdi", 10.0, 300.0, 1.0)
        elif ind == "selic":
            taxa = 0.0
        else:
            taxa = _pct_in("Taxa (% a.a.)", 0.06, f"{pref}_tx", -10.0, 60.0, 0.1)
    with c3:
        tp = st.selectbox("Tipo", list(S.TIPOS_RF), format_func=S.TIPOS_RF.get, key=f"{pref}_tprf")
    return {"indexador": ind, "taxa": taxa, "tipo_rf": tp}


def _aba_classe():
    st.markdown("##### Simulação por classe de ativo")
    classe = st.selectbox("Classe", list(S.CLASSES_SIM), format_func=S.CLASSES_SIM.get, key="sc_classe")
    macro = _macro_editavel("sc")
    rf_cfg = _rf_cfg_in("sc") if classe == "renda_fixa" else None
    c1, c2, c3 = st.columns(3)
    with c1:
        inicial = _valor_in("Capital inicial (R$)", 10000.0, "sc_ini", 0.0, 1000.0)
    with c2:
        aporte = _valor_in("Aporte (R$)", 1000.0, "sc_ap", 0.0, 50.0)
    with c3:
        freq = st.selectbox("Frequência", list(FREQ_ROT), index=2, format_func=FREQ_ROT.get, key="sc_fq")
    c1, c2, c3 = st.columns(3)
    with c1:
        anos = st.number_input("Prazo (anos)", 0.5, 60.0, step=0.5, key="sc_anos", **_opt("sc_anos", "value", 10.0))
    with c2:
        mom = st.radio("Aporte", list(MOMENTO_ROT), format_func=MOMENTO_ROT.get, horizontal=True, key="sc_mom")
    with c3:
        reinv = st.checkbox("Reinvestir distribuições", value=True, key="sc_re")
    base = {"inicial": inicial, "aporte": aporte, "freq": freq, "momento": mom, "meses": int(round(anos * 12)), "reinvestir": reinv}
    ajustes = {c: _editor_classe(classe, c, macro, rf_cfg, "sc") for c in S.CENARIOS}
    if classe in ("cripto", "fundo", "etf", "acao", "fii", "outros", "renda_fixa"):
        base["inflacao"] = macro["moderado"]["ipca"]
    ress = {}
    for c in S.CENARIOS:
        b = {**base, "inflacao": macro[c]["ipca"]}
        ress[c] = S.simular_classe(classe, c, macro, b, rf_cfg, ajustes[c])
    _guardar("classe", {"classe": classe})
    ref = ress["moderado"]
    _resumo_cartoes(ref["resumo"])
    fig = go.Figure()
    cores = {"conservador": COR["ruim"], "moderado": COR["liquido"], "otimista": COR["real"]}
    for c in S.CENARIOS:
        d = ress[c]["df"]
        fig.add_scatter(x=d["mes"] / 12.0, y=d["total_liquido"], name=S.NOMES_CENARIO[c], line=dict(color=cores[c], width=3 if c == "moderado" else 2))
    fig.add_scatter(x=ref["df"]["mes"] / 12.0, y=ref["df"]["investido"], name="Total investido", line=dict(color=COR["investido"], dash="dot"))
    fig.update_layout(title=f"{S.CLASSES_SIM[classe]}: três cenários (hipóteses)", xaxis_title="Anos", yaxis_title="R$")
    _grafico(fig)
    st.dataframe(pd.DataFrame([{"Cenário": S.NOMES_CENARIO[c], "Retorno do preço (a.a.)": _p(ress[c]["premissas"]["taxa_aa"]), "Yield": _p(ress[c]["premissas"].get("dy_aa", 0.0)),
                                "Patrimônio líquido": _brl(ress[c]["resumo"]["total_liquido"]), "Em valores de hoje": _brl(ress[c]["resumo"]["valor_real"]),
                                "Rent. anualizada": _p(ress[c]["resumo"]["rentabilidade_anualizada"])} for c in S.CENARIOS]), hide_index=True, width="stretch")
    pr = ref["premissas"]
    vol = pr.get("vol", 0.15)
    with st.expander("Volatilidade e risco de perda (Monte Carlo)"):
        vol = _pct_in("Volatilidade anual (%)", vol, "sc_vol", 0.0, 300.0, 1.0)
        mc = S.monte_carlo({**base, "taxa_aa": pr["taxa_aa"], "dy_aa": 0.0, "custo_aa": pr.get("custo_aa", 0.0), "inflacao": macro["moderado"]["ipca"]}, vol, 2000)
        if mc.get("ok"):
            _cartoes([("P10", _brl(mc["p10"]), "bad"), ("Mediana", _brl(mc["p50"]), "info"), ("P90", _brl(mc["p90"]), "good"),
                      ("Chance de perder metade", _p(mc["prob_perda_metade"], 1), "fair", "terminar abaixo de 50% do investido")])
            st.caption(f"Queda máxima típica no caminho: {_p(mc['queda_maxima_mediana'], 0)}; em 10% dos caminhos, pior que {_p(mc['queda_maxima_p10'], 0)}.")
    if classe == "renda_fixa":
        r = ref["resumo"]
        st.caption(f"Rentabilidade bruta anual do cenário moderado: {_p(pr['taxa_aa'])}; imposto de renda total no resgate: {_brl(r['imposto'])} (tabela regressiva lote a lote).")
    st.warning(pr["riscos"])
    _avisos()


# ------------------------------------------------------------------ 6 · cenários
def _aba_cenarios():
    st.markdown("##### Cenários: conservador, moderado e otimista")
    st.caption("Todos os cenários são hipóteses suas ou pontos de partida editáveis. Nenhum é previsão.")
    p = _bloco_basico("sn", titulo_taxa=False, padrao={"taxa": 0.10})
    st.markdown("**Retorno nominal de cada cenário**")
    c1, c2, c3 = st.columns(3)
    padrao = {"conservador": 0.07, "moderado": 0.10, "otimista": 0.13}
    taxas = {}
    for col, c in zip((c1, c2, c3), S.CENARIOS):
        with col:
            taxas[c] = _pct_in(f"{S.NOMES_CENARIO[c]} (% a.a.)", padrao[c], f"sn_t_{c}", -50.0, 300.0, 0.25)
    infls = {}
    for col, c in zip((c1, c2, c3), S.CENARIOS):
        with col:
            infls[c] = _pct_in(f"Inflação {S.NOMES_CENARIO[c]} (%)", {"conservador": p["inflacao"] + 0.015, "moderado": p["inflacao"], "otimista": max(p["inflacao"] - 0.01, 0.0)}[c], f"sn_i_{c}", 0.0, 60.0, 0.25)
    ress = {c: S.projetar({**p, "taxa_aa": taxas[c], "inflacao": infls[c]}) for c in S.CENARIOS}
    cores = {"conservador": COR["ruim"], "moderado": COR["liquido"], "otimista": COR["real"]}
    fig = go.Figure()
    for c in S.CENARIOS:
        d = ress[c]["df"]
        fig.add_scatter(x=d["mes"] / 12.0, y=d["total_liquido"], name=S.NOMES_CENARIO[c], line=dict(color=cores[c], width=3 if c == "moderado" else 2))
    fig.add_scatter(x=d["mes"] / 12.0, y=d["investido"], name="Total investido", line=dict(color=COR["investido"], dash="dot"))
    fig.update_layout(title="Patrimônio projetado por cenário", xaxis_title="Anos", yaxis_title="R$")
    _grafico(fig)
    mod = ress["moderado"]["resumo"]["total_liquido"]
    tb = []
    for c in S.CENARIOS:
        r = ress[c]["resumo"]
        tb.append({"Cenário": S.NOMES_CENARIO[c], "Retorno": _p(taxas[c]), "Inflação": _p(infls[c]), "Total de aportes": _brl(r["total_investido"]), "Rendimentos": _brl(r["rendimentos_liquidos"]),
                   "Patrimônio líquido": _brl(r["total_liquido"]), "Efeito da inflação": _brl(r["total_liquido"] - r["valor_real"]), "Valor de hoje": _brl(r["valor_real"]),
                   "Diferença p/ moderado": _brl(r["total_liquido"] - mod)})
    st.dataframe(pd.DataFrame(tb), hide_index=True, width="stretch")
    vol = _pct_in("Volatilidade para estimar perdas possíveis (% a.a.)", 0.15, "sn_vol", 0.0, 200.0, 1.0)
    if vol > 0 and p["meses"] > 0:
        mc = S.monte_carlo({**p, "taxa_aa": taxas["moderado"], "inflacao": infls["moderado"]}, vol, 2000)
        if mc.get("ok"):
            st.markdown(f"**Possíveis perdas (cenário moderado, volatilidade {_p(vol, 0)}):** em 10% dos caminhos o patrimônio fica abaixo de {_brl(mc['p10'])}; "
                        f"a chance de terminar abaixo do total investido é {_p(mc['prob_abaixo_investido'], 1)}.")
    _guardar("cenarios", {c: {"p": {**p, "taxa_aa": taxas[c], "inflacao": infls[c]}, "resumo": ress[c]["resumo"]} for c in S.CENARIOS})
    _avisos()


# ------------------------------------------------------------------ 7 · crises
def _aba_crises():
    st.markdown("##### Crises e perdas")
    st.caption("Mostra como choques afetariam a projeção e o prazo da meta. Não há rebote automático: a recuperação depende da rentabilidade informada.")
    p = _bloco_basico("sk", padrao={"taxa": 0.10})
    c1, c2, c3 = st.columns(3)
    with c1:
        escolhidas = st.multiselect("Crises", list(S.CRISES), default=["queda_30"], format_func=lambda k: S.CRISES[k]["nome"], key="sk_crises")
    with c2:
        mes = st.number_input("Mês em que ocorre", 1, max(p["meses"], 1), key="sk_mes", **_opt("sk_mes", "value", min(24, max(p["meses"], 1))))
    with c3:
        dolar = st.slider("Parcela em dólar do patrimônio (%)", 0, 100, 0, key="sk_usd", help="Só para a crise cambial.") / 100.0
    with st.expander("Crise personalizada"):
        a, b, c_, d, e = st.columns(5)
        with a:
            q = st.number_input("Queda (%)", 0.0, 100.0, 0.0, 1.0, key="sk_q")
        with b:
            j = st.number_input("Juros (+p.p.)", 0.0, 30.0, 0.0, 0.5, key="sk_j")
        with c_:
            i = st.number_input("Inflação (+p.p.)", 0.0, 50.0, 0.0, 0.5, key="sk_i")
        with d:
            dv = st.number_input("Dividendos (−%)", 0.0, 100.0, 0.0, 5.0, key="sk_d")
        with e:
            lq = st.number_input("Deságio de saída (%)", 0.0, 80.0, 0.0, 1.0, key="sk_l")
    meta = None
    if st.checkbox("Medir o atraso para atingir uma meta", key="sk_usar_meta"):
        meta = _valor_in("Meta (R$ nominais)", 500000.0, "sk_meta", 0.0, 10000.0)
    itens = [(S.CRISES[k]["nome"], S.CRISES[k]) for k in escolhidas]
    pers = S.crise_personalizada("Crise personalizada", q, j, i, dv, lq)
    if pers:
        itens.append(("Crise personalizada", pers))
    if not itens:
        st.info("Escolha ao menos uma crise.")
        return
    fig = go.Figure()
    tb = []
    guardado = []
    for k, (nome, cr) in enumerate(itens):
        imp = S.impacto_crise(p, cr, mes, meta, False, dolar)
        if k == 0:
            fig.add_scatter(x=imp["df_sem"]["mes"] / 12.0, y=imp["df_sem"]["total_liquido"], name="Sem crise", line=dict(color=COR["liquido"], width=3))
        fig.add_scatter(x=imp["df_com"]["mes"] / 12.0, y=imp["df_com"]["total_liquido"], name=nome, line=dict(width=2))
        at = imp["atraso_meta"] or {}
        tb.append({"Crise": nome, "Sem crise": _brl(imp["sem_crise"]["total_liquido"]), "Com crise": _brl(imp["com_crise"]["total_liquido"]), "Diferença": _brl(imp["delta"]),
                   "Diferença %": _p(imp["delta_pct"], 1), "Queda máxima": _p(imp["queda_maxima"], 1), "Meses p/ recuperar": imp["meses_para_recuperar"] if imp["meses_para_recuperar"] is not None else "não recupera",
                   **({"Atraso na meta (meses)": at.get("atraso_meses") if at.get("atraso_meses") is not None else "não atinge"} if meta else {})})
        guardado.append({"nome": nome, "resumo_base": imp["sem_crise"], "resumo_crise": imp["com_crise"]})
    fig.add_vline(x=mes / 12.0, line_dash="dash", line_color=COR["ruim"], annotation_text="crise")
    fig.update_layout(title="Efeito das crises sobre o patrimônio", xaxis_title="Anos", yaxis_title="R$")
    _grafico(fig)
    st.dataframe(pd.DataFrame(tb), hide_index=True, width="stretch")
    _guardar("crise", guardado)
    # integração com o Passo 16 (motor de estresse da gestão de risco)
    st.divider()
    st.markdown("**Choque na carteira real (motor de estresse do Passo 16)**")
    _crise_na_carteira()
    _avisos()


def _posicoes_carteira(chave_radio: str = "scart_esc"):
    """(posições, aviso) da carteira escolhida na Gestão (Passo 12). Sem posições → ([], motivo)."""
    ss = _ss()
    reais = [l for l in ss.get("cart_real", []) if isinstance(l, dict)]
    fict = [l for l in ss.get("cart_ficticia", []) if isinstance(l, dict)]
    ops = ["Carteira real", "Carteira fictícia"]
    esc = st.radio("Carteira", ops, horizontal=True, key=chave_radio, **_opt(chave_radio, "index", 0 if (reais or ss.get("cart_rf") or not fict) else 1))
    chave = "cart_real" if esc == ops[0] else "cart_ficticia"
    try:
        import gestao_app as ga
        lido = ga.ler_carteira(chave)
    except Exception as e:
        log.warning("carteira indisponível: %s", e)
        return [], f"Não consegui ler a carteira agora ({e.__class__.__name__})."
    if lido is None:
        return [], "Sua carteira está vazia. Cadastre posições na página Carteira para simular com elas."
    C = lido[0]
    pos = [p for p in C["posicoes"] if p.get("valor") and p["valor"] > 0]
    return pos, ""


def _crise_na_carteira():
    pos, aviso = _posicoes_carteira("scart_esc_crise")
    if not pos:
        st.caption(aviso)
        return
    q = st.select_slider("Queda dos mercados (%)", [10, 20, 30, 50], value=30, key="sk_cq")
    try:
        r = S.crise_na_carteira(pos, S.choques_risco_de_queda(q), None, f"Queda de {q}%")
    except Exception as e:
        st.caption(f"O motor de estresse não respondeu ({e.__class__.__name__}).")
        return
    st.markdown(f"Patrimônio atual {_brl(r['antes'])} → {_brl(r['depois'])} depois de uma queda de {q}% nos mercados: **{_brl(r['delta'])}** ({_p(r['pct'] / 100.0, 1)}). "
                "Hipotético, calculado pelo módulo de risco; renda fixa e caixa não caem por padrão.")
    for k, v in list(r.get("por_classe", {}).items())[:6]:
        st.caption(f"{CLASSES_CARTEIRA.get(k, k)}: {_brl(v)}")


# ------------------------------------------------------------------ 8 · carteira
def _dy_por_ativo(pos: list[dict]) -> dict:
    """Yield dos proventos reais dos últimos 12 meses por ativo, quando a Gestão já os trouxe. Sem dado, não inventa."""
    out = {}
    for p in pos:
        dy = p.get("dy") if p.get("dy") is not None else p.get("yield_12m")
        if isinstance(dy, (int, float)) and np.isfinite(dy) and dy > 0:
            out[p["id"]] = float(dy) / (100.0 if dy > 1.5 else 1.0)
    return out


def _aba_carteira():
    st.markdown("##### Simulador de carteira")
    pos, aviso = _posicoes_carteira()
    if not pos:
        st.markdown(tema.vazio("carteira", "Sem posições para simular", aviso), unsafe_allow_html=True)
        return
    macro = _macro_editavel("scar")
    dyp = _dy_por_ativo(pos)
    baldes = SC.baldes_da_carteira(pos, dyp)
    w0 = SC.pesos(baldes)
    c1, c2, c3 = st.columns(3)
    with c1:
        cen = st.selectbox("Cenário", list(S.CENARIOS), index=1, format_func=S.NOMES_CENARIO.get, key="scar_cen")
    with c2:
        anos = st.number_input("Prazo (anos)", 1, 50, key="scar_anos", **_opt("scar_anos", "value", 10))
    with c3:
        aporte = _valor_in("Novo aporte mensal (R$)", 0.0, "scar_ap", 0.0, 100.0)
    st.markdown("**Alocação dos novos aportes e peso-alvo (%)**")
    cls = list(baldes)
    cols = st.columns(min(len(cls), 4))
    aloc, alvo = {}, {}
    for k, c in enumerate(cls):
        with cols[k % len(cols)]:
            aloc[c] = st.number_input(f"Aporte → {CLASSES_CARTEIRA.get(c, c)}", 0.0, 100.0, step=5.0, key=f"scar_al_{c}", **_opt(f"scar_al_{c}", "value", round(w0[c] * 100, 1)))
            alvo[c] = st.number_input(f"Alvo · {CLASSES_CARTEIRA.get(c, c)}", 0.0, 100.0, step=5.0, key=f"scar_av_{c}", **_opt(f"scar_av_{c}", "value", round(w0[c] * 100, 1)))
    c1, c2, c3 = st.columns(3)
    with c1:
        reb = st.selectbox("Rebalanceamento", ["Nenhum", "Trimestral", "Semestral", "Anual"], key="scar_reb")
    with c2:
        cr = _pct_in("Custo do rebalanceamento (% do volume)", 0.001, "scar_cr", 0.0, 5.0, 0.05)
    with c3:
        reinv = st.checkbox("Reinvestir proventos", value=True, key="scar_re")
    rho = st.slider("Correlação média entre classes (hipótese)", 0.0, 1.0, 0.5, 0.05, key="scar_rho")
    with st.expander("Incluir ou retirar ativos"):
        a, b, c_ = st.columns(3)
        with a:
            nc = st.selectbox("Incluir ativo da classe", ["—"] + [k for k in CLASSES_CARTEIRA], format_func=lambda k: "—" if k == "—" else CLASSES_CARTEIRA[k], key="scar_ic")
        with b:
            nv = _valor_in("Valor a incluir (R$)", 0.0, "scar_iv", 0.0, 1000.0)
        with c_:
            ret = st.multiselect("Retirar ativos", [p["id"] for p in pos], key="scar_ret")
    rf_nada = {}
    tabs_prem = st.expander("Premissas de caixa")
    with tabs_prem:
        cx = _pct_in("Rendimento do caixa (% a.a.)", 0.0, "scar_cx", 0.0, 50.0, 0.25)
    ajustes = {"caixa": {"taxa_aa": cx}}
    for c in cls:
        sv = _prem_salvas().get(f"{c}|{cen}")
        if sv:
            ajustes[c] = sv
    fr = {"Nenhum": None, "Trimestral": "trimestral", "Semestral": "semestral", "Anual": "anual"}[reb]
    pa = {c: v / 100.0 for c, v in alvo.items()}
    paa = {c: v / 100.0 for c, v in aloc.items()}
    orig = SC.simular_carteira(baldes, macro, cen, 0.0, int(anos * 12), None, None, None, None, ajustes, cr, reinv, rho, "Carteira atual")
    b2 = SC.retirar_ativo(pos, ret, dyp) if ret else baldes
    if nc != "—" and nv > 0:
        b2 = SC.adicionar_ativo(b2, nc, nv)
    sim = SC.simular_carteira(b2, macro, cen, aporte, int(anos * 12), paa if sum(paa.values()) > 0 else None, fr, pa if sum(pa.values()) > 0 else None, None, ajustes, cr, reinv, rho, "Carteira simulada")
    if not (orig.get("ok") and sim.get("ok")):
        st.warning("Não foi possível simular: a carteira ficou sem posições.")
        return
    cmp_ = SC.comparar_carteiras(orig, sim)
    ro, rs = orig["resumo"], sim["resumo"]
    tb = pd.DataFrame([
        ("Patrimônio projetado (líquido)", _brl(ro["total_liquido"]), _brl(rs["total_liquido"]), _brl(cmp_["dif_patrimonio"])),
        ("Em valores de hoje", _brl(ro["valor_real"]), _brl(rs["valor_real"]), _brl(cmp_["dif_real"])),
        ("Total aportado", _brl(ro["total_investido"]), _brl(rs["total_investido"]), _brl(cmp_["dif_aportado"])),
        ("Rentabilidade hipotética (a.a.)", _p(ro["rentabilidade_anualizada"]), _p(rs["rentabilidade_anualizada"]), _p(cmp_["dif_rent_aa"], 2)),
        ("Risco estimado (volatilidade a.a.)", _p(ro["vol_estimada_final"]), _p(rs["vol_estimada_final"]), _p(cmp_["dif_vol"], 2)),
        ("Renda passiva anual no fim", _brl(ro["renda_passiva_anual_final"]), _brl(rs["renda_passiva_anual_final"]), _brl(cmp_["dif_renda_anual"])),
    ], columns=["Indicador", "Original", "Simulada", "Diferença"])
    st.dataframe(tb, hide_index=True, width="stretch")
    fig = go.Figure()
    fig.add_scatter(x=orig["df"]["mes"] / 12.0, y=orig["df"]["patrimonio"], name="Original", line=dict(color=COR["investido"], width=3))
    fig.add_scatter(x=sim["df"]["mes"] / 12.0, y=sim["df"]["patrimonio"], name="Simulada", line=dict(color=COR["liquido"], width=3))
    fig.update_layout(title="Patrimônio projetado (bruto, antes do imposto)", xaxis_title="Anos", yaxis_title="R$")
    _grafico(fig)
    ex = pd.DataFrame(cmp_["exposicao"])
    fig = go.Figure()
    rot = [CLASSES_CARTEIRA.get(c, c) for c in ex["classe"]]
    fig.add_bar(x=rot, y=ex["ini_a"] * 100, name="Hoje", marker_color=COR["investido"])
    fig.add_bar(x=rot, y=ex["fim_a"] * 100, name="Original no fim", marker_color=COR["alt"])
    fig.add_bar(x=rot, y=ex["fim_b"] * 100, name="Simulada no fim", marker_color=COR["liquido"])
    fig.update_layout(barmode="group", title="Exposição por classe (%)", yaxis_title="%")
    _grafico(fig, 300)
    est = SC.indicadores_estrutura(pos)
    ea, ec = est["ativo"], est["classe"]
    if ea.get("ok"):
        _cartoes([("Concentração por ativo (HHI)", f"{ea['hhi']:.2f}", "fair", f"maior posição {_p(ea['top1'], 0)}"), ("Nº efetivo de ativos", f"{ea['n_efetivo']:.1f}", "info", f"{ea['n']} {'posição' if ea['n'] == 1 else 'posições'}"),
                  ("Concentração por classe (HHI)", f"{ec['hhi']:.2f}" if ec.get("ok") else "n/d", "fair", f"{est['n_classes']} {'classe' if est['n_classes'] == 1 else 'classes'}"), ("Maiores 3 posições", _p(ea["top3"], 0), "na")])
    cob = [f"{CLASSES_CARTEIRA.get(c, c)}: {_p(b['cobertura_dy'], 0)} do valor com yield real" for c, b in baldes.items() if b.get("dy") is not None]
    st.caption("Yield usado: " + ("; ".join(cob) if cob else "nenhum dado real de proventos disponível, então uso a hipótese de cada classe") + ".")
    for a in sim["avisos"]:
        st.caption(a)
    comp = {"dif_patrimonio": cmp_["dif_patrimonio"], "dif_vol": cmp_["dif_vol"], "dif_renda_anual": cmp_["dif_renda_anual"]}
    _guardar("carteira", {"resumo": rs, "comparacao": comp})


# ------------------------------------------------------------------ 9 · histórico
def _preco_ativo(tk: str) -> tuple[pd.Series, str]:
    try:
        import evolucao
        p = evolucao.coletar_precos(tk)
        s = p["ajustado"] if len(p["ajustado"]) else p["preco"]
        return s, ("; ".join(p["avisos"]) if p["avisos"] else "")
    except Exception as e:
        return pd.Series(dtype=float), f"Sem histórico para {tk} ({e.__class__.__name__})."


def _aba_historico():
    st.markdown("##### Simulação com dados históricos reais")
    st.caption("Usa preços ajustados por proventos do Yahoo Finance. Em cada dia a estratégia só enxerga o passado (sem olhar o futuro).")
    c1, c2 = st.columns(2)
    with c1:
        tks = st.text_input("Ativo(s) (códigos separados por vírgula)", "BOVA11", key="sh_tk", max_chars=60, help="Para carteira rebalanceada use 2 ou mais.")
        ep = st.selectbox("Período", list(SC.EPISODIOS) + ["Datas livres"], index=len(SC.EPISODIOS) - 1, key="sh_ep")
    with c2:
        capital = _valor_in("Capital inicial (R$)", 10000.0, "sh_cap", 0.0, 1000.0)
        aporte = _valor_in("Aporte mensal (R$)", 1000.0, "sh_ap", 0.0, 100.0)
    if ep == "Datas livres":
        a, b = st.columns(2)
        with a:
            ini = st.date_input("De", value=date.today() - timedelta(days=365 * 5), key="sh_ini")
        with b:
            fim = st.date_input("Até", value=date.today(), key="sh_fim")
    else:
        ini, fim = SC.periodo_do_episodio(ep)
    c1, c2, c3 = st.columns(3)
    with c1:
        corr = _pct_in("Corretagem (% por operação)", 0.0, "sh_cor", 0.0, 5.0, 0.05)
    with c2:
        ir = st.selectbox("Imposto sobre o ganho final", list(S.TIPOS_IR), index=list(S.TIPOS_IR).index("ganho_15"), format_func=S.TIPOS_IR.get, key="sh_ir")
    with c3:
        reb = st.selectbox("Rebalanceamento", ["anual", "trimestral", "mensal"], key="sh_reb")
    aliq = _aliquota_in("sh", ir)
    codigos = [t.strip().upper() for t in tks.split(",") if t.strip()][:6]
    if not codigos:
        st.info("Digite ao menos um código.")
        return
    estr = st.multiselect("Estratégias para comparar", [e for e in SC.ESTRATEGIAS if e != "rebalanceada" or len(codigos) > 1], default=["unico", "dca"], format_func=SC.ESTRATEGIAS.get, key="sh_estr")
    if not st.button("Simular com dados históricos", key="sh_go", type="primary", icon=":material/history:"):
        res_ant = _ss().get("_sim_hist")
        if not res_ant:
            return
        res = res_ant
    else:
        series, avs = {}, []
        for t in codigos:
            s, av = _preco_ativo(t)
            if len(s) > 30:
                series[t] = s
            elif av:
                avs.append(av)
        if not series:
            st.error("Não consegui o histórico de preços. " + " ".join(avs))
            return
        mk = _mercado()
        ipca = mk.get("ipca_serie")
        cdi_d = None
        if mk.get("cdi_idx") is not None and len(mk["cdi_idx"]):
            cdi_d = mk["cdi_idx"].astype(float).pct_change().dropna() * 100.0
        kw = dict(inicio=ini, fim=fim, capital=capital, aporte_mensal=aporte, rebalancar=reb, corretagem=corr, ir=ir, aliquota=aliq, ipca_mensal=ipca, cdi_diario=cdi_d)
        base_ser = {k: v for k, v in series.items()}
        out = []
        for e in estr:
            usa = base_ser if e == "rebalanceada" else {list(base_ser)[0]: list(base_ser.values())[0]}
            out.append(SC.simular_historico(usa, e, **kw))
        res = {"itens": out, "avisos": avs, "ativos": list(series), "periodo": (ini, fim)}
        _ss()["_sim_hist"] = res
    ok = [r for r in res["itens"] if r.get("ok")]
    for r in res["itens"]:
        if not r.get("ok"):
            st.warning(r.get("motivo", "Sem dados no período."))
    if not ok:
        return
    ok = sorted(ok, key=lambda r: -r["valor_liquido"])
    st.caption(f"Período efetivo: {ok[0]['inicio']} a {ok[0]['fim']} ({ok[0]['anos']:.1f} anos, {ok[0]['pregoes']} pregões) · ativos: {', '.join(res['ativos'])}.")
    st.dataframe(pd.DataFrame([{"Estratégia": r["rotulo"], "Investido": _brl(r["investido"]), "Valor líquido": _brl(r["valor_liquido"]), "Resultado": _brl(r["ganho_liquido"]),
                                "TIR a.a.": _p(r["tir_aa"], 2), "Queda máxima": _p(r["mdd"], 1), "Volatilidade a.a.": _p(r["vol_aa"], 1),
                                "Valor real (IPCA)": _brl(r["valor_real"]) if r.get("valor_real") else "n/d", "Imposto": _brl(r["imposto"])} for r in ok]), hide_index=True, width="stretch")
    fig = go.Figure()
    for r in ok:
        fig.add_scatter(x=r["serie"].index, y=r["serie"].values, name=r["rotulo"][:40])
    fig.update_layout(title="Valor da estratégia ao longo do tempo (bruto)", yaxis_title="R$")
    _grafico(fig)
    r0 = ok[0]
    if r0.get("cdi"):
        st.caption(f"Referência: o capital inicial no CDI do período teria virado {_brl(r0['cdi']['valor_equivalente_unico'])} (sem aportes, antes de imposto).")
    for a in r0["avisos"] + res.get("avisos", []):
        st.caption(a)
    _guardar("historico", [{"rotulo": r["rotulo"], "valor_liquido": r["valor_liquido"], "investido": r["investido"], "tir_aa": r["tir_aa"], "mdd": r["mdd"]} for r in ok])


# ------------------------------------------------------------------ 10 · inflação
def _aba_inflacao():
    st.markdown("##### Inflação e poder de compra")
    c1, c2, c3 = st.columns(3)
    with c1:
        valor = _valor_in("Valor de hoje (R$)", 100000.0, "si_val", 0.0, 1000.0)
    with c2:
        anos = st.number_input("Anos", 1, 60, key="si_anos", **_opt("si_anos", "value", 20))
    with c3:
        modo = st.radio("Inflação", ["Constante", "Varia ano a ano"], horizontal=True, key="si_modo")
    if modo == "Constante":
        infl = _pct_in("Inflação (% a.a.)", 0.045, "si_inf", -5.0, 100.0, 0.25)
    else:
        st.caption("Informe a inflação de cada ano (o último valor se repete nos anos seguintes).")
        base = pd.DataFrame({"Ano": list(range(1, 11)), "Inflação (%)": [6.0, 5.0, 4.5, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0, 4.0]})
        ed = st.data_editor(base, key="si_tab", hide_index=True, width="stretch", disabled=["Ano"])
        v = [float(x) / 100.0 for x in ed["Inflação (%)"].fillna(0).tolist()]
        infl = (v + [v[-1]] * max(int(anos) - len(v), 0))[:max(int(anos), 1)]
    t = S.serie_poder_de_compra(valor, infl, int(anos))
    fim = t.iloc[-1]
    _cartoes([("Valor parado compra só", _brl(fim["valor_parado_real"]), "bad", f"perda de poder de compra: {_p(fim['perda_poder_compra'], 1)}"),
              ("Para manter o poder de compra", _brl(fim["nominal_para_manter"]), "info", f"em {int(anos)} anos"),
              ("Inflação média", _p(S.inflacao_media_anual(infl, int(anos) * 12), 2), "fair", "ao ano")])
    fig = go.Figure()
    fig.add_scatter(x=t["ano"], y=t["valor_parado_real"], name="O que o valor parado compra (R$ de hoje)", line=dict(color=COR["ruim"], width=3))
    fig.add_scatter(x=t["ano"], y=t["nominal_para_manter"], name="Valor nominal para manter o poder de compra", line=dict(color=COR["liquido"], width=3))
    fig.update_layout(title="Poder de compra ao longo do tempo", xaxis_title="Anos", yaxis_title="R$")
    _grafico(fig)
    st.markdown("**Rentabilidade real de um investimento**")
    c1, c2 = st.columns(2)
    with c1:
        nom = _pct_in("Rentabilidade nominal (% a.a.)", 0.10, "si_nom", -50.0, 300.0, 0.25)
    with c2:
        im = S.inflacao_media_anual(infl, int(anos) * 12)
    real = S.fisher(nom, im)
    st.markdown(f"Rentabilidade nominal de **{_p(nom)}** com inflação média de **{_p(im, 2)}** dá **{_p(real, 2)} ao ano em termos reais** "
                f"(Fisher: (1 + nominal) ÷ (1 + inflação) − 1; não é a subtração simples, que daria {_p(nom - im, 2)}). "
                f"{_brl(valor)} investidos viram {_brl(valor * (1 + nom) ** int(anos))} nominais, que valem {_brl(valor * (1 + real) ** int(anos))} em poder de compra de hoje.")
    st.dataframe(pd.DataFrame({"Ano": t["ano"], "Índice de preços": t["indice"].round(4), "Valor parado compra": t["valor_parado_real"].map(_brl),
                               "Nominal p/ manter": t["nominal_para_manter"].map(_brl), "Perda": t["perda_poder_compra"].map(lambda x: _p(x, 1))}), hide_index=True, width="stretch")
    _avisos()


# ------------------------------------------------------------------ 11 · assistente
def contexto_ia() -> dict | None:
    c = _ss().get(CTX)
    if not c:
        return None
    m = _mercado() if "_sim_mercado" in _ss() else {}
    return {**c, "cdi": m.get("cdi"), "ipca": m.get("ipca")}


def _aba_assistente():
    st.markdown("##### Assistente do simulador")
    st.caption("Explica os números que o simulador calculou nas outras abas. Não indica compra ou venda e não promete rentabilidade.")
    ctx = contexto_ia()
    if not ctx:
        st.info("Calcule alguma simulação nas outras abas e volte aqui.")
    exemplos = ["Explique o resultado da simulação", "Minhas premissas estão otimistas?", "E se eu aportar 25% a mais?", "Qual o efeito da inflação?", "Compare os cenários", "Que simulações devo testar?"]
    cols = st.columns(3)
    for k, e in enumerate(exemplos):
        if cols[k % 3].button(e, key=f"sas_ex_{k}"):
            _ss()["sas_q"] = e
    q = st.text_input("Pergunte sobre sua simulação", key="sas_q", max_chars=300, placeholder="Ex.: minhas premissas estão otimistas?")
    if q and q.strip():
        r = SI.responder_simulador(q.strip(), ctx)
        st.markdown(f"**{r['texto']}**")
        for l in r["linhas"]:
            st.markdown(f"- {l}")
        st.caption(f"{r['referencia']} · {r['consultado']}")
        st.caption(r["limite"])


# ------------------------------------------------------------------ 12 · fórmulas
def _aba_formulas():
    st.markdown("##### Fórmulas e metodologia")
    for titulo, f, nota in SI.FORMULAS:
        st.markdown(f"**{titulo}**")
        st.code(f, language=None)
        st.caption(nota)
    st.markdown("**Convenções**")
    st.markdown("- Periodicidade: o cálculo é mensal; taxas anuais são convertidas por equivalência.\n"
                "- Aporte no início do mês rende o mês; no fim, não.\n"
                "- Frequência semanal = 52/12 aportes por mês; quinzenal = 2.\n"
                "- Rentabilidade bruta é antes de custos e impostos; líquida, depois. Real desconta a inflação.\n"
                "- Arredondamento só na exibição; os cálculos usam ponto flutuante de dupla precisão.\n"
                "- Premissas por classe são hipóteses editáveis, não dados de mercado. Dados reais usados: CDI, IPCA e Selic (Banco Central), preços e proventos (Yahoo Finance) e sua carteira.")
    st.caption(S.AVISO)


# ------------------------------------------------------------------ página
def pagina_simulador():
    st.markdown(tema.cabecalho("calc", "Simulador financeiro",
                               "Juros compostos, aposentadoria, renda passiva, metas, cenários, crises, carteira e histórico, todos com premissas editáveis."), unsafe_allow_html=True)
    st.caption(S.AVISO)
    tabs = st.tabs(ABAS)
    fs = [_aba_juros, _aba_aposentadoria, _aba_renda, _aba_metas, _aba_classe, _aba_cenarios, _aba_crises, _aba_carteira, _aba_historico, _aba_inflacao, _aba_assistente, _aba_formulas]
    for t, f in zip(tabs, fs):
        with t:
            try:
                f()
            except Exception as e:
                log.exception("falha na aba do simulador")
                st.error(f"Esta aba falhou ({e.__class__.__name__}). Confira as premissas e tente de novo; o problema foi registrado.")
