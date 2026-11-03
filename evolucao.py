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
    "fii": "A evolução (histórico) de patrimônio líquido, valor patrimonial por cota, vacância e imóveis não tem fonte "
           "integrada. Os valores de hoje vêm do Fundamentus; o histórico traz preço, dividendos por cota e retorno total.",
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


def validar_historico(longo: pd.Series, ref: pd.Series, tol: float = 0.05, tol_meio: float = 0.10) -> tuple[bool, str]:
    """O histórico longo (Yahoo) é do MESMO ativo da CoinGecko? Compara o último preço e o de ~180 dias atrás com a
    série de referência. Símbolos repetidos entre moedas diferentes são comuns: sem esta conferência, não se usa."""
    a, b = cr.serie_limpa(longo), cr.serie_limpa(ref)
    if a.empty or b.empty:
        return False, "sem série para conferir"
    a, b = a.copy(), b.copy()
    a.index, b.index = a.index.normalize(), b.index.normalize()
    pares = []
    for d in (b.index[-1], b.index[len(b) // 2]):
        i = a.index.get_indexer([d], method="nearest")[0]
        if abs((a.index[i] - d).days) > 3:
            return False, "datas não batem"
        pares.append((float(a.iloc[i]), float(b.loc[d])))
    lim = (tol, tol_meio)
    for (x, y), l in zip(pares, lim):
        if y <= 0 or abs(x / y - 1) > l:
            return False, f"preço diferente da CoinGecko ({x:.4g} contra {y:.4g})"
    return True, ""


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
def coletar_historico_longo_cripto(simbolo: str, ref_preco: pd.Series) -> dict:
    """Preço e volume diários desde o início da série no Yahoo (SÍMBOLO-USD). Só vale se bater com a CoinGecko."""
    out = {"preco": pd.Series(dtype=float), "volume": pd.Series(dtype=float), "fonte": "Yahoo Finance", "avisos": []}
    if not simbolo or ref_preco is None or len(ref_preco) == 0:
        return out
    try:
        h = _yf().Ticker(f"{str(simbolo).upper().strip()}-USD").history(period="max", auto_adjust=False)
        if h is None or h.empty:
            out["avisos"].append("O Yahoo não tem histórico longo para este símbolo.")
            return out
        idx = pd.to_datetime(h.index)
        if getattr(idx, "tz", None) is not None:
            idx = idx.tz_localize(None)
        h.index = idx.normalize()
        preco = h["Close"].where(h["Close"] > 0).dropna()
        ok, motivo = validar_historico(preco, ref_preco)
        if not ok:
            out["avisos"].append(f"Histórico longo descartado: {motivo}. Pode ser outro ativo com o mesmo símbolo.")
            return out
        out["preco"] = preco
        if "Volume" in h:
            out["volume"] = h["Volume"].where(h["Volume"] >= 0).dropna()
    except Exception as e:
        out["avisos"].append(f"Histórico longo indisponível ({e.__class__.__name__}).")
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def coletar_cripto(gid: str) -> dict:
    """Preço, valor de mercado, volume, oferta (calculada) e TVL (quando existir) dos últimos 365 dias."""
    import cripto
    out = {"series": {}, "tvl": pd.Series(dtype=float), "fonte": "CoinGecko / DefiLlama", "avisos": [],
           "data": date.today().isoformat(), "longo": {"preco": pd.Series(dtype=float), "volume": pd.Series(dtype=float),
                                                       "fonte": "Yahoo Finance", "avisos": []}}
    try:
        chart = cripto._get_json(f"{cripto.GECKO}/coins/{gid}/market_chart", {"vs_currency": "usd", "days": "365"})
        out["series"] = series_cripto(chart)
    except Exception as e:
        out["avisos"].append(f"CoinGecko não respondeu ({e}).")
        return out
    try:
        simbolo = (cripto.analisar_moeda(gid) or {}).get("simbolo")
        out["longo"] = coletar_historico_longo_cripto(simbolo, out["series"].get("Preço (USD)"))
    except Exception:
        out["longo"]["avisos"].append("Histórico longo indisponível agora.")
    try:
        cad = cripto._cadeia_da_moeda(gid)
        if cad:
            h = cripto._tvl_hist_cadeia(cad["name"])
            if h:
                s = pd.Series([v for _, v in h], index=[pd.to_datetime(d).normalize() for d, _ in h], dtype=float)
                out["tvl"] = s[~s.index.duplicated(keep="last")].sort_index().tail(365)
    except Exception:
        out["avisos"].append("TVL indisponível para esta moeda agora.")
    out["avisos"].append("Valor de mercado, volume e oferta: a CoinGecko gratuita entrega 365 dias. Usuários e transações "
                         "on-chain não têm fonte integrada.")
    return out


# campos do FII na página do Fundamentus: chave → (rótulos aceitos, tipo)
CAMPOS_FII = {
    "segmento": (("Segmento",), "txt"), "mandato": (("Mandato",), "txt"),
    "vacancia": (("Vacância Média", "Vacancia Media"), "pct"), "imoveis": (("Qtd imóveis", "Qtd imoveis"), "int"),
    "vp_cota": (("VP/Cota",), "num"), "pvp": (("P/VP",), "num"), "pl": (("Patrimônio Líquido", "Patrimonio Liquido"), "num"),
    "dy": (("Dividend Yield",), "pct"), "ffo": (("FFO Yield",), "pct"), "cotas": (("Nº de cotas", "N de cotas", "Num de cotas"), "int"),
    "valor_mercado": (("Valor de mercado",), "num"),
}


def _num_br(txt):
    """'1.234,56' → 1234.56; '8,5%' → 8.5; '-' ou vazio → None. Formato brasileiro (ponto = milhar, vírgula = decimal)."""
    if txt is None:
        return None
    s = re.sub(r"[^0-9,.\-]", "", str(txt))
    if s in ("", "-", ".", ","):
        return None
    try:
        return float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None


def ler_fii_fundamentus(campos: dict) -> dict:
    """Extrai de {rótulo: texto} (página do Fundamentus) os campos de FII. O que não for encontrado fica None: a tela
    mostra 'não encontrado' em vez de preencher. Quem chama decide o que fazer com a lista `faltando`."""
    def achar(*nomes):
        for n in nomes:
            k = dados._chave_txt(n) if dados is not None and hasattr(dados, "_chave_txt") else n.lower()
            if k in campos:
                return campos[k]
        return None
    out, faltando = {}, []
    for chave, (nomes, tipo) in CAMPOS_FII.items():
        bruto = achar(*nomes)
        if bruto is None or str(bruto).strip() in ("", "-"):
            out[chave] = None
            faltando.append(chave)
        else:
            out[chave] = str(bruto).strip() if tipo == "txt" else _num_br(bruto)
            if out[chave] is None:
                faltando.append(chave)
    out["faltando"] = faltando
    return out


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def coletar_fii_fundamentus(tk: str) -> dict:
    """Dados ATUAIS do FII no Fundamentus (não é histórico). Falhou = dict com aviso, nunca número inventado."""
    out = {"dados": {}, "fonte": "Fundamentus", "data": date.today().isoformat(), "avisos": []}
    try:
        campos = dados._fundamentus_pagina(str(tk).upper().strip())
        if not campos:
            out["avisos"].append("O Fundamentus não devolveu a página deste FII.")
            return out
        out["dados"] = ler_fii_fundamentus(campos)
        if len(out["dados"]["faltando"]) == len(CAMPOS_FII):
            out["avisos"].append("A página não trouxe nenhum dos campos esperados (o layout do site pode ter mudado).")
    except Exception as e:
        out["avisos"].append(f"Fundamentus indisponível ({e.__class__.__name__}).")
    return out


@st.cache_data(ttl=3600, show_spinner=False)
def coletar_bcb() -> dict:
    """IPCA mensal (SGS 433) e CDI diário (SGS 12) do Banco Central, já como índices acumulados. Reaproveita o
    buscar_macro_bcb do app. Se a API não responder, os índices vêm vazios e a tela explica."""
    out = {"ipca": pd.Series(dtype=float), "ipca_idx": pd.Series(dtype=float), "cdi_idx": pd.Series(dtype=float),
           "fonte": "Banco Central (SGS 433 e 12)", "avisos": []}
    if dados is None:
        out["avisos"].append("Fonte do Banco Central indisponível.")
        return out
    try:
        i = dados.buscar_macro_bcb(433, 10)
        c = dados.buscar_macro_bcb(12, 9)
        if not i.empty:
            out["ipca"] = i["valor"]
            out["ipca_idx"] = cr.indice_de_taxas(i["valor"])
        if not c.empty:
            out["cdi_idx"] = cr.indice_de_taxas(c["valor"])
    except Exception as e:
        out["avisos"].append(f"Banco Central não respondeu ({e.__class__.__name__}).")
    if out["ipca_idx"].empty:
        out["avisos"].append("IPCA indisponível agora: valor real não calculado.")
    if out["cdi_idx"].empty:
        out["avisos"].append("CDI indisponível agora: comparação com o CDI não calculada.")
    return out


def em_reais(tk: str) -> bool:
    """Ativo negociado em reais (código da B3). Só esses são comparados com IPCA e CDI brasileiros."""
    try:
        return bool(dados.eh_b3(tk))
    except Exception:
        return bool(re.fullmatch(r"[A-Z]{4}\d{1,2}", str(tk).upper()))


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
    r["resumo"]["ganho_real3"] = r["resumo"]["pct_cdi3"] = None
    if em_reais(tk) and len(p["ajustado"]):
        b = coletar_bcb()
        x = cr.contra_benchmarks(p["ajustado"], b["cdi_idx"], b["ipca_idx"], 3)
        if x["ok"]:
            r["resumo"]["ganho_real3"] = x["real_anual"] * 100 if x["real_anual"] is not None else None
            r["resumo"]["pct_cdi3"] = x["pct_cdi"]
        r["avisos"].extend(b["avisos"])
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


def _secao_real(tk: str, p: dict):
    """Valor real (descontado o IPCA) e comparação com CDI e inflação, para ativos em reais."""
    st.markdown("**Contra a inflação e o CDI**")
    if not em_reais(tk):
        st.info("Ativo em moeda estrangeira: o IPCA e o CDI brasileiros não se aplicam, e o app ainda não converte "
                "moedas. Os números acima estão na moeda do ativo.")
        return
    if p["ajustado"].empty:
        st.info("Sem histórico de preços.")
        return
    b = coletar_bcb()
    for av in b["avisos"]:
        st.caption("⚠️ " + av)
    linhas = []
    for n in (1, 3, 5):
        x = cr.contra_benchmarks(p["ajustado"], b["cdi_idx"], b["ipca_idx"], n)
        nome = f"{n} ano" + ("s" if n > 1 else "")
        if not x["ok"]:
            linhas.append({"Período": nome, "Retorno total": x["motivo"], "CDI": "—", "% do CDI": "—", "IPCA": "—",
                           "Ganho real a.a.": "—"})
            continue
        f = lambda v: "n/d" if v is None else cr._pct(v * 100)
        linhas.append({"Período": nome, "Retorno total": f(x["ativo"]), "CDI": f(x["cdi"]), "IPCA": f(x["ipca"]),
                       "% do CDI": "n/d" if x["pct_cdi"] is None else f"{x['pct_cdi']:.0f}%",
                       "Ganho real a.a.": f(x["real_anual"])})
    st.dataframe(pd.DataFrame(linhas).set_index("Período"), use_container_width=True)
    st.caption("Retorno total = preço + proventos, acumulado na mesma janela do CDI e do IPCA. Ganho real = "
               "(1 + retorno) ÷ (1 + IPCA) − 1, em base anual. Fonte da inflação e do CDI: Banco Central.")
    real, aviso = cr.valor_real(p["preco"], b["ipca"])
    if aviso:
        st.caption(aviso)
    if len(real):
        st.markdown("**Preço a valores de hoje (descontado o IPCA)**")
        _mostrar_cagr_serie("Preço real", real)
        ac = {"Preço (nominal)": cr.acumulado(p["preco"][p["preco"].index >= real.index[0]]), "Preço (real)": cr.acumulado(real)}
        if len(b["cdi_idx"]):
            cdi = b["cdi_idx"][b["cdi_idx"].index >= real.index[0]]
            ac["CDI"] = cr.acumulado(cdi)
        if _alternar(f"ev_{tk}_real_vis"):
            st.plotly_chart(grafico_linhas(ac, "Nominal, real e CDI (base 100 no início)"), use_container_width=True,
                            key=f"ev_{tk}_realg")
        else:
            st.dataframe(pd.DataFrame(ac).resample("YE").last().round(1).T)


ROT_FII = {"segmento": "Segmento", "mandato": "Mandato", "vacancia": "Vacância média (%)", "imoveis": "Nº de imóveis",
           "vp_cota": "Valor patrimonial por cota (R$)", "pvp": "P/VP", "pl": "Patrimônio líquido (R$)",
           "dy": "Dividend yield (%)", "ffo": "FFO yield (%)", "cotas": "Nº de cotas", "valor_mercado": "Valor de mercado (R$)"}


def _secao_fii(tk: str):
    """Fotografia atual do FII (Fundamentus): vacância, imóveis, VP/cota e PL. Não é série histórica."""
    st.markdown("**Fotografia atual do FII**")
    f = coletar_fii_fundamentus(tk)
    for av in f["avisos"]:
        st.caption("⚠️ " + av)
    d = f["dados"]
    if not d:
        return
    linhas = {ROT_FII[k]: ("não encontrado" if d.get(k) is None else
                           (d[k] if isinstance(d[k], str) else _fmt_num(d[k]))) for k in ROT_FII}
    st.dataframe(pd.DataFrame({"Valor": linhas}), use_container_width=True)
    st.caption(f"Fonte: {f['fonte']} · lido em {date.fromisoformat(f['data']).strftime('%d/%m/%Y')} · valores de HOJE: "
               "o app ainda não guarda o histórico de vacância, patrimônio e VP/cota, então não há CAGR deles.")


def _pagina_acao_fii_etf(tk: str, classe_id: str):
    with st.spinner("Coletando balanços e cotações..."):
        p = coletar_precos(tk)
        d = coletar_demonstrativos(tk) if classe_id == "acao" else None
    for av in p["avisos"] + (d["avisos"] if d else []):
        st.caption("⚠️ " + av)
    if classe_id != "acao":
        st.info(SEM_FONTE.get(classe_id, ""))
        if classe_id == "fii":
            _secao_fii(tk)
        _tab_preco(tk, classe_id, p)
        _secao_real(tk, p)
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
        _secao_real(tk, p)


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
    st.caption("Em 12 meses o CAGR é igual à variação do período. Valor de mercado, volume e oferta só têm 365 dias de histórico.")
    lg = c.get("longo") or {}
    for av in lg.get("avisos", []):
        st.caption("⚠️ " + av)
    if len(lg.get("preco", [])):
        st.markdown("**Preço: CAGR de longo prazo**")
        st.caption(f"Fonte: {lg['fonte']} (SÍMBOLO-USD), conferido com a CoinGecko · histórico desde "
                   f"{lg['preco'].index[0].strftime('%d/%m/%Y')}. Cripto é muito volátil: o CAGR depende do ponto de partida.")
        _mostrar_cagr_serie("Preço", lg["preco"])
        if len(lg.get("volume", [])):
            vol = media_movel(lg["volume"], 30)
            r = cr.cagr_periodos(vol, (1, 3, 5), tol_dias=20)
            st.markdown("**Volume diário (média de 30 dias)**")
            cols = st.columns(len(r))
            for col, (n, x) in zip(cols, r.items()):
                col.metric(f"{n} ano" + ("s" if n > 1 else ""), x.texto if x.ok else "—")
                if not x.ok:
                    col.caption(x.texto)
        if mostrar_graf:
            st.plotly_chart(grafico_linhas({"Preço (USD)": lg["preco"]}, "Preço desde o início do histórico (USD)"),
                            use_container_width=True, key=f"ev_{gid}_longo")
            st.caption("O gráfico está em escala linear: variações antigas parecem pequenas perto das recentes.")
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
