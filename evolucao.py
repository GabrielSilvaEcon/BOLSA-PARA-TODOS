"""
Evolução e crescimento dos ativos: coleta de dados reais (Yahoo Finance e CoinGecko/DefiLlama, já usados no app)
e a página "Evolução e crescimento". Os cálculos ficam em crescimento.py (puro e testado); aqui só há coleta,
montagem de séries e tela. Nada é estimado: dado que a fonte não entrega fica indisponível e a tela diz isso.
"""
from __future__ import annotations

import re
from datetime import date

import pandas as pd
import streamlit as st

import comparador
import crescimento as cr
import tema

try:                                     # no teste, estes módulos podem ser substituídos
    import dados
except Exception:                        # pragma: no cover
    dados = None

NOTA_FONTE_BALANCO = ("Yahoo Finance: costuma trazer cerca de 4 exercícios anuais e 5 trimestres. Por isso CAGR de 5 e 10 "
                      "anos de receita e lucro só aparece quando a fonte entrega esse histórico; o de preço e dividendos "
                      "usa todo o histórico de cotações.")
SEM_FONTE = {
    "fii": "Patrimônio líquido, valor patrimonial por cota, vacância, ocupação, imóveis e inquilinos não têm fonte de dados "
           "integrada ao app (não são oferecidos pelo Yahoo). Aqui entram preço, dividendos por cota e retorno total.",
    "etf": "Patrimônio sob gestão histórico e evolução da composição da carteira não têm fonte integrada. Aqui entram "
           "preço, distribuições e retorno total.",
    "fundo": "Fundos de investimento ainda não têm fonte de dados integrada ao app: nenhum número é inventado.",
    "renda_fixa": "Renda fixa ainda não tem série histórica integrada ao app: use a calculadora e o Tesouro Direto.",
}


# =============================================================================== funções puras (testáveis)
def dividendos_por_ano(div: pd.Series, inicio_hist=None, hoje: date | None = None) -> pd.Series:
    """Soma dos proventos por ano-calendário. Só entram anos COMPLETOS: o ano corrente e o primeiro ano do histórico
    (se o histórico começa depois de janeiro) ficam de fora, para não comparar ano parcial com ano cheio."""
    hoje = hoje or date.today()
    s = cr.serie_limpa(div)
    s = s[s > 0]
    if s.empty:
        return pd.Series(dtype=float)
    ini = pd.Timestamp(inicio_hist) if inicio_hist is not None else s.index[0]
    por_ano = s.groupby(s.index.year).sum()
    anos = [a for a in por_ano.index if a < hoje.year and (a > ini.year or (a == ini.year and ini <= pd.Timestamp(a, 1, 31)))]
    out = por_ano.loc[anos]
    out.index = pd.to_datetime([f"{a}-12-31" for a in out.index])
    return out


def series_cripto(chart: dict) -> dict[str, pd.Series]:
    """Séries diárias da CoinGecko (market_chart): preço, valor de mercado, volume e oferta circulante.
    Oferta circulante = valor de mercado ÷ preço (CALCULADA; a CoinGecko não entrega o histórico da oferta)."""
    def serie(chave):
        pts = [(pd.to_datetime(x[0], unit="ms"), float(x[1])) for x in (chart.get(chave) or [])
               if isinstance(x, (list, tuple)) and len(x) == 2 and x[1] is not None]
        if not pts:
            return pd.Series(dtype=float)
        s = pd.Series([v for _, v in pts], index=[d for d, _ in pts])
        s.index = s.index.normalize()
        return s[~s.index.duplicated(keep="last")]
    preco, mc, vol = serie("prices"), serie("market_caps"), serie("total_volumes")
    oferta = (mc / preco.where(preco > 0)).dropna() if len(mc) and len(preco) else pd.Series(dtype=float)
    return {"Preço (USD)": preco, "Valor de mercado (USD)": mc.where(mc > 0).dropna(),
            "Volume diário (USD)": vol.where(vol >= 0).dropna(), "Oferta circulante (calculada)": oferta}


def media_movel(s: pd.Series, dias: int = 7) -> pd.Series:
    return cr.serie_limpa(s).rolling(f"{dias}D").mean().dropna() if len(s) else s


def cagr_de_serie(s: pd.Series, periodos=(1, 3, 5, 10), tol: int | None = None) -> dict:
    return cr.cagr_periodos(s, periodos, tol)


def resumo_crescimento(df_anual: pd.DataFrame, preco: pd.Series | None = None, retorno_total: pd.Series | None = None,
                       dividendos_ano: pd.Series | None = None, periodo: int = 3) -> dict:
    """Números de crescimento de um ativo para o motor de comparação: chave → valor em % (ou None)."""
    out: dict = {}

    def pega(chave, serie):
        if serie is None or len(serie) == 0:
            out[chave] = None
            return
        c = cr.cagr_periodos(serie, (periodo,))[periodo]
        out[chave] = c.valor * 100 if c.ok else None
    pega("cagr_preco3", preco)
    pega("cagr_retorno3", retorno_total)
    pega("cagr_div3", dividendos_ano)
    for chave, col in (("cagr_receita3", "Receita líquida"), ("cagr_lucro3", "Lucro líquido"),
                       ("cagr_fcl3", "Fluxo de caixa livre")):
        pega(chave, df_anual[col] if df_anual is not None and col in df_anual else None)
    if df_anual is not None and "Receita líquida" in df_anual:
        c = cr.consistencia(df_anual["Receita líquida"])
        out["consist_receita"] = c["taxa"]
    else:
        out["consist_receita"] = None
    return out


def inds_comparador(resumo: dict, fonte: str, data_ref: str | None, periodo: str = "3 anos") -> dict:
    """Converte o resumo em indicadores do motor do passo 6 (sem alterar nota alguma)."""
    I = comparador.Ind
    return {k: I(v, "calculado", periodo if k != "consist_receita" else "exercícios anuais", data_ref)
            for k, v in resumo.items() if v is not None}


def quem_cresceu_mais(linhas: dict[str, dict]) -> list[dict]:
    """Linhas {ativo: resumo}. Devolve destaques: maior crescimento (receita, depois preço), maior consistência
    e melhor retorno total. Só compara ativos que têm o indicador."""
    def melhor(chave, titulo):
        v = {k: r[chave] for k, r in linhas.items() if r.get(chave) is not None}
        if len(v) < 2:
            return None
        top = max(v, key=v.get)
        return {"titulo": titulo, "ativo": top, "valor": v[top], "chave": chave, "n": len(v)}
    cand = [melhor("cagr_receita3", "Maior crescimento de receita (3 anos)"),
            melhor("cagr_lucro3", "Maior crescimento de lucro (3 anos)"),
            melhor("cagr_preco3", "Maior valorização do preço (3 anos)"),
            melhor("cagr_retorno3", "Maior retorno total (3 anos)"),
            melhor("consist_receita", "Receita mais consistente")]
    return [c for c in cand if c]


# =============================================================================== coleta
def _yf():
    import yfinance as yf
    return yf


def _sym(tk: str) -> str:
    tk = str(tk).upper().strip().replace(" ", "")
    if dados is not None and hasattr(dados, "sym_yf"):
        return dados.sym_yf(tk)
    return tk + ".SA" if re.fullmatch(r"[A-Z]{4}\d{1,2}", tk) else tk


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def coletar_demonstrativos(tk: str) -> dict:
    """Demonstrativos anuais e trimestrais do Yahoo, já padronizados. Falhas viram aviso, nunca número inventado."""
    out = {"anual": pd.DataFrame(), "trim": pd.DataFrame(), "fonte": "Yahoo Finance", "data": date.today().isoformat(),
           "avisos": [], "moeda": None}
    try:
        t = _yf().Ticker(_sym(tk))
        out["anual"] = cr.padronizar_yahoo(t.income_stmt, t.balance_sheet, t.cashflow)
        out["trim"] = cr.padronizar_yahoo(t.quarterly_income_stmt, t.quarterly_balance_sheet, t.quarterly_cashflow)
        try:
            out["moeda"] = (t.fast_info or {}).get("currency")
        except Exception:
            out["moeda"] = None
    except Exception as e:
        out["avisos"].append(f"Yahoo Finance não entregou os demonstrativos ({e.__class__.__name__}).")
    if out["anual"].empty and not out["avisos"]:
        out["avisos"].append("O Yahoo Finance não traz demonstrativos para este código.")
    if len(out["anual"]) and out["anual"].attrs.get("derivados"):
        out["avisos"].append("Calculados a partir de outros itens: " + ", ".join(out["anual"].attrs["derivados"]) + ".")
    return out


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def coletar_precos(tk: str) -> dict:
    """Todo o histórico diário: Close sem ajuste (preço), Close ajustado (retorno total) e proventos."""
    out = {"preco": pd.Series(dtype=float), "ajustado": pd.Series(dtype=float), "div": pd.Series(dtype=float),
           "fonte": "Yahoo Finance", "avisos": []}
    try:
        h = _yf().Ticker(_sym(tk)).history(period="max", auto_adjust=False)
        if h is not None and not h.empty:
            idx = pd.to_datetime(h.index)
            if getattr(idx, "tz", None) is not None:
                idx = idx.tz_localize(None)
            h.index = idx.normalize()
            out["preco"] = h["Close"].dropna()
            out["ajustado"] = (h["Adj Close"] if "Adj Close" in h else h["Close"]).dropna()
            if "Dividends" in h:
                out["div"] = h["Dividends"][h["Dividends"] > 0]
    except Exception as e:
        out["avisos"].append(f"Yahoo Finance não entregou o histórico de preços ({e.__class__.__name__}).")
    if out["preco"].empty and not out["avisos"]:
        out["avisos"].append("Sem histórico de preços para este código.")
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def coletar_cripto(gid: str) -> dict:
    """Preço, valor de mercado, volume, oferta (calculada) e TVL (quando existir) dos últimos 365 dias."""
    import cripto
    out = {"series": {}, "tvl": pd.Series(dtype=float), "fonte": "CoinGecko / DefiLlama", "avisos": [],
           "data": date.today().isoformat()}
    try:
        chart = cripto._get_json(f"{cripto.GECKO}/coins/{gid}/market_chart", {"vs_currency": "usd", "days": "365"})
        out["series"] = series_cripto(chart)
    except Exception as e:
        out["avisos"].append(f"CoinGecko não respondeu ({e}).")
        return out
    try:
        cad = cripto._cadeia_da_moeda(gid)
        if cad:
            h = cripto._tvl_hist_cadeia(cad["name"])
            if h:
                s = pd.Series([v for _, v in h], index=[pd.to_datetime(d).normalize() for d, _ in h], dtype=float)
                out["tvl"] = s[~s.index.duplicated(keep="last")].sort_index().tail(365)
    except Exception:
        out["avisos"].append("TVL indisponível para esta moeda agora.")
    out["avisos"].append("A CoinGecko gratuita entrega 365 dias: CAGR de 3, 5 e 10 anos não existe para criptomoedas aqui. "
                         "Usuários e transações on-chain não têm fonte integrada.")
    return out


def coletar_resumo(tk: str, classe_id: str) -> dict:
    """Resumo de crescimento de um ativo (para tabela, ranking e Comparar). Sempre devolve um dict, nunca levanta."""
    p = coletar_precos(tk)
    r = {"resumo": {}, "fonte": p["fonte"], "data_ref": None, "avisos": list(p["avisos"])}
    if len(p["preco"]):
        r["data_ref"] = p["preco"].index[-1].date().isoformat()
    div_ano = dividendos_por_ano(p["div"], p["preco"].index[0] if len(p["preco"]) else None)
    df = pd.DataFrame()
    if classe_id == "acao":
        d = coletar_demonstrativos(tk)
        df = d["anual"]
        r["avisos"].extend(d["avisos"])
    r["resumo"] = resumo_crescimento(df, p["preco"], p["ajustado"], div_ano)
    return r


# =============================================================================== gráficos
def _fig():
    import plotly.graph_objects as go
    return go


PLOT_BASE = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=40, b=40),
                 legend=dict(orientation="h", y=-0.2), height=380)


def grafico_barras(df: pd.DataFrame, colunas: list[str], titulo: str, pct: bool = False):
    go = _fig()
    f = go.Figure()
    x = [pd.Timestamp(d).strftime("%m/%Y") if len(df) > 0 and pd.Timestamp(d).month != 12 else str(pd.Timestamp(d).year)
         for d in df.index]
    for c in colunas:
        if c in df:
            f.add_bar(x=x, y=df[c], name=c)
    f.update_layout(title=titulo, barmode="group", **PLOT_BASE)
    if pct:
        f.update_yaxes(ticksuffix="%")
    return f


def grafico_linhas(series: dict[str, pd.Series], titulo: str, ysufixo: str = ""):
    go = _fig()
    f = go.Figure()
    for nome, s in series.items():
        if len(s):
            f.add_scatter(x=s.index, y=s.values, name=nome, mode="lines")
    f.update_layout(title=titulo, **PLOT_BASE)
    if ysufixo:
        f.update_yaxes(ticksuffix=ysufixo)
    return f


def grafico_cagr(tabela_num: pd.DataFrame, titulo: str):
    """Barras do CAGR por indicador e período (linhas = indicador, colunas = período; valores em %)."""
    go = _fig()
    f = go.Figure()
    for c in tabela_num.columns:
        f.add_bar(x=tabela_num.index, y=tabela_num[c], name=c)
    f.update_layout(title=titulo, barmode="group", **PLOT_BASE)
    f.update_yaxes(ticksuffix="%")
    return f


def cagr_numerico(df_anual: pd.DataFrame, colunas, periodos=cr.PERIODOS) -> pd.DataFrame:
    """Tabela numérica (em %) para o gráfico; período sem CAGR válido fica vazio."""
    linhas = {}
    for c in colunas:
        if c in df_anual:
            r = cr.cagr_periodos(df_anual[c], periodos)
            linhas[c] = {f"{n} ano" + ("s" if n > 1 else ""): (r[n].valor * 100 if r[n].ok else None) for n in periodos}
    return pd.DataFrame(linhas).T


# =============================================================================== apresentação
def _fmt_num(v, moeda: str = "") -> str:
    if v is None or pd.isna(v):
        return "n/d"
    a = abs(v)
    for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if a >= lim:
            return f"{v / lim:,.2f}{suf}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tabela_formatada(df: pd.DataFrame, anual: bool = True) -> pd.DataFrame:
    """Para exibição: datas como ano (ou mês/ano), valores grandes abreviados, margens em %."""
    if df is None or df.empty:
        return pd.DataFrame()
    t = df.copy()
    pcts = [c for c in t.columns if c.startswith("Margem") or c in ("ROE", "ROIC")]
    for c in t.columns:
        if c in pcts:
            t[c] = t[c].map(lambda v: "n/d" if pd.isna(v) else f"{v:.1f}%".replace(".", ","))
        elif c == "Dívida líquida/EBITDA":
            t[c] = t[c].map(lambda v: "n/d" if pd.isna(v) else f"{v:.1f}×".replace(".", ","))
        else:
            t[c] = t[c].map(_fmt_num)
    t.index = [str(pd.Timestamp(d).year) if anual else pd.Timestamp(d).strftime("%m/%Y") for d in t.index]
    return t.T


def _alternar(chave: str) -> bool:
    """True = gráfico, False = tabela."""
    return st.radio("Visualização", ["Gráfico", "Tabela"], horizontal=True, key=chave, label_visibility="collapsed") == "Gráfico"


GRUPOS = {
    "Resultado": ["Receita líquida", "Lucro bruto", "EBITDA", "EBIT", "Lucro líquido"],
    "Margens (%)": ["Margem bruta", "Margem EBITDA", "Margem líquida"],
    "Balanço": ["Ativo total", "Passivo total", "Patrimônio líquido"],
    "Dívida e caixa": ["Dívida bruta", "Dívida líquida", "Caixa"],
    "Fluxo de caixa": ["Caixa operacional", "Capex", "Fluxo de caixa livre"],
    "Rentabilidade (%)": ["ROE", "ROIC"],
}


def _mostrar_demonstrativo(df: pd.DataFrame, anual: bool, chave: str):
    d = cr.derivar_indicadores(df)
    if d.empty:
        st.info("Sem dados para este recorte.")
        return
    if not anual:
        st.caption("Trimestres: ROE e ROIC usam o lucro de UM trimestre sobre o capital do fim dele (não anualizado); "
                   "compare só com o mesmo trimestre do ano anterior. Não misture com os números anuais.")
    mostrar_graf = _alternar(f"{chave}_vis")
    for nome, cols in GRUPOS.items():
        cols = [c for c in cols if c in d and d[c].notna().any()]
        if not cols:
            continue
        with st.expander(nome, expanded=nome in ("Resultado", "Margens (%)")):
            if mostrar_graf:
                st.plotly_chart(grafico_barras(d, cols, nome, pct="%" in nome), use_container_width=True,
                                key=f"{chave}_{nome}")
            else:
                st.dataframe(tabela_formatada(d[cols], anual), use_container_width=True)
    if anual and len(d) >= 2:
        yoy = {c: cr.variacao_anual(d[c]) for c in ("Receita líquida", "Lucro líquido", "Fluxo de caixa livre") if c in d}
        yoy = pd.DataFrame({k: v * 100 for k, v in yoy.items() if len(v)})
        if len(yoy):
            with st.expander("Crescimento de um ano para o outro"):
                if mostrar_graf:
                    st.plotly_chart(grafico_barras(yoy, list(yoy.columns), "Variação anual", pct=True),
                                    use_container_width=True, key=f"{chave}_yoy")
                else:
                    st.dataframe(yoy.round(1).astype(str).radd("").T, use_container_width=True)
    if not anual and len(d):
        yq = {c: cr.variacao_trimestral_yoy(d[c]) * 100 for c in ("Receita líquida", "Lucro líquido") if c in d}
        yq = pd.DataFrame({k: v for k, v in yq.items() if len(v)})
        if len(yq):
            with st.expander("Variação sobre o mesmo trimestre do ano anterior"):
                if mostrar_graf:
                    st.plotly_chart(grafico_barras(yq, list(yq.columns), "Trimestre contra o mesmo trimestre do ano anterior",
                                                   pct=True), use_container_width=True, key=f"{chave}_yoyq")
                else:
                    st.dataframe(yq.round(1), use_container_width=True)
        ttm = {c: cr.soma_12m(d[c]) for c in ("Receita líquida", "Lucro líquido", "Caixa operacional") if c in d}
        ttm = pd.DataFrame({k: v for k, v in ttm.items() if len(v)})
        if len(ttm):
            with st.expander("Últimos 12 meses (soma de 4 trimestres)"):
                st.dataframe(tabela_formatada(ttm, anual=False), use_container_width=True)


def _mostrar_cagr_serie(nome: str, s: pd.Series, unidade: str = ""):
    r = cr.cagr_periodos(s)
    cols = st.columns(len(r))
    for col, (n, c) in zip(cols, r.items()):
        col.metric(f"{nome} · {n} ano" + ("s" if n > 1 else ""), c.texto if c.ok else "—",
                   help=None if c.ok else c.texto)
        if not c.ok:
            col.caption(c.texto)
        else:
            col.caption(f"{c.inicio[0]} → {c.fim[0]} ({c.anos:.1f} anos)")


_TOM = {"positivo": "✅", "atencao": "⚠️", "neutro": "ℹ️"}


def _mostrar_achados(achados: list):
    for a in achados:
        st.markdown(f"{_TOM.get(a.tom, 'ℹ️')} **{a.titulo}.** {a.texto}")
        if a.evidencias:
            st.caption("Indicadores que justificam: " + " · ".join(a.evidencias))


def _tab_preco(tk: str, classe_id: str, p: dict):
    if p["preco"].empty:
        st.warning("Sem histórico de preços para este código.")
        return
    st.caption(f"Fonte: {p['fonte']} · último preço em {p['preco'].index[-1].strftime('%d/%m/%Y')} · "
               f"histórico desde {p['preco'].index[0].strftime('%d/%m/%Y')}")
    st.markdown("**Preço (sem proventos)**")
    _mostrar_cagr_serie("Preço", p["preco"])
    st.markdown("**Retorno total (preço + proventos reinvestidos)**")
    _mostrar_cagr_serie("Retorno total", p["ajustado"])
    st.caption("O preço mostra só a valorização da cota/ação; o retorno total inclui proventos. Em ativos que pagam muito "
               "dividendo (FIIs, por exemplo) a diferença é grande.")
    div_ano = dividendos_por_ano(p["div"], p["preco"].index[0])
    st.markdown("**Dividendos por ano (somente anos-calendário completos)**")
    if len(div_ano) >= 2:
        st.caption("Valores por ação/cota, na moeda do ativo.")
        _mostrar_cagr_serie("Dividendos", div_ano)
        if _alternar(f"ev_{tk}_div_vis"):
            st.plotly_chart(grafico_barras(pd.DataFrame({"Dividendos por ano": div_ano}), ["Dividendos por ano"],
                                           "Dividendos por ano"), use_container_width=True, key=f"ev_{tk}_divg")
        else:
            st.dataframe(pd.DataFrame({"Ano": div_ano.index.year, "Dividendos": div_ano.round(4).values}).set_index("Ano").T)
    else:
        st.info("Menos de 2 anos completos de proventos no histórico: CAGR dos dividendos não se aplica.")
    st.markdown("**Crescimento acumulado (base 100)**")
    ac = {"Preço": cr.acumulado(p["preco"]), "Retorno total": cr.acumulado(p["ajustado"])}
    if _alternar(f"ev_{tk}_ac_vis"):
        st.plotly_chart(grafico_linhas(ac, "Crescimento acumulado (base 100 no início do histórico)"),
                        use_container_width=True, key=f"ev_{tk}_acg")
    else:
        st.dataframe(pd.DataFrame(ac).resample("YE").last().round(1).T)


def _pagina_acao_fii_etf(tk: str, classe_id: str):
    with st.spinner("Coletando balanços e cotações..."):
        p = coletar_precos(tk)
        d = coletar_demonstrativos(tk) if classe_id == "acao" else None
    for av in p["avisos"] + (d["avisos"] if d else []):
        st.caption("⚠️ " + av)
    if classe_id != "acao":
        st.info(SEM_FONTE.get(classe_id, ""))
        _tab_preco(tk, classe_id, p)
        return
    anual, trim = d["anual"], d["trim"]
    abas = st.tabs(["Resumo e análise", "CAGR", "Anual", "Trimestral", "Preço e dividendos"])
    with abas[0]:
        if anual.empty:
            st.warning("Sem demonstrativos anuais para esta ação na fonte.")
        else:
            st.caption(f"Fonte: {d['fonte']} · {len(anual)} exercícios anuais ({anual.index[0].year}–{anual.index[-1].year})"
                       f"{' · moeda: ' + d['moeda'] if d.get('moeda') else ''} · consultado em "
                       f"{date.fromisoformat(d['data']).strftime('%d/%m/%Y')}")
            _mostrar_achados(cr.diagnosticar(anual))
            st.caption("Regras automáticas e educacionais, baseadas apenas nos números acima; não são recomendação. "
                       "Mudanças contábeis (ex.: adoção de nova norma, reapresentação de balanços) não são detectadas "
                       "pela fonte: confira as notas explicativas da empresa.")
    with abas[1]:
        if anual.empty:
            st.info("Sem demonstrativos para calcular CAGR.")
        else:
            st.caption("CAGR = (valor final ÷ valor inicial)^(1 ÷ anos) − 1, com anos medidos pelas datas reais. "
                       "Sem ponto de partida no período pedido, aparece \"histórico insuficiente\" (não é trocado por outro período).")
            st.dataframe(cr.tabela_cagr(anual).set_index("Indicador"), use_container_width=True)
            num = cagr_numerico(anual, ["Receita líquida", "EBITDA", "Lucro líquido", "Fluxo de caixa livre",
                                        "Patrimônio líquido"])
            if num.notna().any().any() and _alternar(f"ev_{tk}_cagr_vis"):
                st.plotly_chart(grafico_cagr(num, "CAGR por indicador"), use_container_width=True, key=f"ev_{tk}_cagrg")
            st.caption(NOTA_FONTE_BALANCO)
        if len(p["div"]):
            div_ano = dividendos_por_ano(p["div"], p["preco"].index[0] if len(p["preco"]) else None)
            _mostrar_cagr_serie("Dividendos", div_ano)
        _mostrar_cagr_serie("Preço", p["preco"])
    with abas[2]:
        if anual.empty:
            st.info("Sem dados anuais.")
        else:
            _mostrar_demonstrativo(anual, True, f"ev_{tk}_a")
    with abas[3]:
        if trim.empty:
            st.info("Sem dados trimestrais na fonte.")
        else:
            _mostrar_demonstrativo(trim, False, f"ev_{tk}_t")
    with abas[4]:
        _tab_preco(tk, classe_id, p)


def _pagina_cripto(gid: str):
    with st.spinner("Coletando a série da CoinGecko..."):
        c = coletar_cripto(gid)
    for av in c["avisos"]:
        st.caption("⚠️ " + av)
    s = c["series"]
    if not s or all(len(v) == 0 for v in s.values()):
        st.warning("Sem dados de mercado agora. Tente novamente em instantes.")
        return
    st.caption(f"Fonte: {c['fonte']} · janela de 365 dias · consultado em {date.fromisoformat(c['data']).strftime('%d/%m/%Y')}")
    mostrar_graf = _alternar(f"ev_{gid}_vis")
    st.markdown("**Variação em 12 meses**")
    cols = st.columns(4)
    rot = [("Preço (USD)", s["Preço (USD)"], 1), ("Valor de mercado (USD)", s["Valor de mercado (USD)"], 1),
           ("Volume diário (USD)", media_movel(s["Volume diário (USD)"], 7), 10),
           ("Oferta circulante (calculada)", s["Oferta circulante (calculada)"], 1)]
    for col, (nome, ser, tol) in zip(cols, rot):
        r = cr.cagr_periodos(ser, (1,), tol_dias=max(tol, cr.TOL_DIARIA_DIAS))[1] if len(ser) else None
        col.metric(nome.split(" (")[0] + (" (média 7d)" if "Volume" in nome else ""),
                   (cr._pct(r.variacao_total * 100) if r and r.ok else "—"))
        col.caption("" if r and r.ok else (r.texto if r else "dado indisponível"))
    st.caption("Em 12 meses o CAGR é igual à variação do período. Para 3, 5 e 10 anos a fonte gratuita não entrega histórico.")
    for nome, ser in s.items():
        if len(ser) == 0:
            continue
        if mostrar_graf:
            st.plotly_chart(grafico_linhas({nome: ser}, nome), use_container_width=True, key=f"ev_{gid}_{nome}")
        else:
            st.dataframe(ser.resample("ME").last().round(2).rename(nome).to_frame().T, use_container_width=True)
    if len(c["tvl"]):
        st.markdown("**TVL (valor bloqueado) da rede**")
        if mostrar_graf:
            st.plotly_chart(grafico_linhas({"TVL (USD)": c["tvl"]}, "TVL (USD)"), use_container_width=True, key=f"ev_{gid}_tvl")
        r = cr.cagr_periodos(c["tvl"], (1,), tol_dias=10)[1]
        st.caption("Variação em 12 meses do TVL: " + (cr._pct(r.variacao_total * 100) if r.ok else r.texto))
    else:
        st.caption("TVL não se aplica ou não está disponível para esta moeda.")


def _pagina_comparacao(base_tk: str, classe_base: str):
    st.caption("Compare o crescimento histórico de vários ativos. Os mesmos indicadores entram na página **Comparar ativos**.")
    extra = st.text_input("Outros códigos (separe por vírgula)", key="ev_cmp_extra",
                          placeholder="Ex.: ITUB4, BBDC4, SANB11")
    codigos = list(dict.fromkeys([base_tk] + [re.sub(r"[^A-Z0-9.\-]", "", x.upper()) for x in re.split(r"[,\s;]+", extra or "") if x]))[:6]
    if len(codigos) < 2:
        st.info("Informe pelo menos 1 código além do ativo atual.")
        return
    if not st.button("Comparar crescimento", type="primary", key="ev_cmp_go"):
        return
    linhas, series_ac = {}, {}
    with st.spinner("Coletando..."):
        for tk in codigos:
            cls, _ = comparador.identificar_classe(tk)
            cls = "acao" if cls not in ("acao", "etf", "fii") else cls
            r = coletar_resumo(tk, cls)
            linhas[tk] = r["resumo"]
            series_ac[tk] = cr.acumulado(coletar_precos(tk)["preco"])
    rotulos = {s.chave: s.nome for s in comparador.SPECS_CRESCIMENTO}
    tab = pd.DataFrame({tk: {rotulos[k]: (None if v is None else float(v)) for k, v in r.items() if k in rotulos}
                        for tk, r in linhas.items()})
    if _alternar("ev_cmp_vis"):
        pct = tab.drop(index=[rotulos["consist_receita"]], errors="ignore").dropna(how="all")
        if len(pct):
            go = _fig()
            f = go.Figure()
            for tk in pct.columns:
                f.add_bar(x=pct.index, y=pct[tk], name=tk)
            f.update_layout(title="Crescimento anual composto (3 anos), %", barmode="group", **PLOT_BASE)
            st.plotly_chart(f, use_container_width=True, key="ev_cmp_barras")
        st.plotly_chart(grafico_linhas(series_ac, "Crescimento acumulado do preço (base 100 no início de cada histórico)"),
                        use_container_width=True, key="ev_cmp_lin")
        st.caption("As linhas começam em datas diferentes (início do histórico de cada ativo): olhe a inclinação, não a altura.")
    else:
        st.dataframe(tab.round(1), use_container_width=True)
    for d in quem_cresceu_mais(linhas):
        st.markdown(f"🏆 **{d['titulo']}:** {d['ativo']} ({d['valor']:+.1f}%)".replace(".", ",") if "consist" not in d["chave"]
                    else f"🏆 **{d['titulo']}:** {d['ativo']} ({d['valor']:.0f}% dos anos em alta)")
    st.caption("Ativos sem o indicador (histórico insuficiente, lucro negativo ou fonte sem o dado) ficam de fora do destaque.")


# =============================================================================== página
def pagina_evolucao():
    st.markdown(tema.cabecalho("📈", "Evolução e crescimento",
                               "Balanços, margens, CAGR de 1, 3, 5 e 10 anos, preço, dividendos e análise automática. "
                               "Só dados reais das fontes do app."), unsafe_allow_html=True)
    modo = st.radio("Classe", ["Ação, FII ou ETF", "Criptomoeda"], horizontal=True, key="ev_modo", label_visibility="collapsed")
    if modo == "Criptomoeda":
        import cripto
        ops = list(dict.fromkeys(st.session_state.get("cripto_ativos", []) + list(cripto.POPULARES.values())))
        nomes = {**{v: k for k, v in cripto.POPULARES.items()}, **st.session_state.get("cripto_nomes", {})}
        gid = st.selectbox("Criptomoeda", ops, key="ev_gid", format_func=lambda g: nomes.get(g) or g.replace("-", " ").title())
        if gid:
            _pagina_cripto(gid)
        return
    pre = st.session_state.pop("ev_pre", None)
    if pre:
        st.session_state["ev_tk"] = pre
    tk = st.text_input("Código", key="ev_tk", placeholder="Ex.: ITUB4, WEGE3, AAPL, HGLG11, BOVA11, VOO").upper().strip()
    tk = re.sub(r"[^A-Z0-9.\-]", "", tk)
    if not tk:
        st.info("Digite um código para ver a evolução. Fundos de investimento e renda fixa ainda não têm fonte integrada.")
        return
    cls, conf = comparador.identificar_classe(tk)
    if cls == "cripto":
        st.info("Para criptomoedas, escolha **Criptomoeda** acima.")
        return
    if cls == "fii" and conf != "alta":
        st.caption("Código parecido com FII (XXXX11): tratado como FII. Se for outro tipo de papel, os números de balanço não valem.")
    st.caption("Classe: " + comparador.classe(cls).nome)
    _pagina_acao_fii_etf(tk, cls)
    with st.expander("Comparar o crescimento com outros ativos"):
        _pagina_comparacao(tk, cls)


def atalho_evolucao(destino, codigo: str, chave: str, rotulo: str = "Ver evolução e crescimento"):
    """Botão que leva um código de outra tela para esta página (`destino` = st.Page da evolução)."""
    if codigo and destino is not None and st.button(rotulo, key=f"ev_atalho_{chave}", icon=":material/timeline:"):
        st.session_state["ev_pre"] = codigo
        st.session_state["ev_modo"] = "Ação, FII ou ETF"
        st.switch_page(destino)
