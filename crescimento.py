"""
Crescimento, CAGR e análise histórica (puro: sem Streamlit e sem rede; recebe séries/tabelas já coletadas).

O que este módulo garante (as regras de precisão do Passo 7):
  - CAGR = (valor final ÷ valor inicial)^(1 ÷ anos) − 1, com anos medidos pelas datas REAIS dos dois pontos. Só existe
    quando início e fim são positivos; base zero/negativa, resultado não positivo e mudança de sinal devolvem um status
    explicado, nunca um número inventado.
  - Períodos de 1, 3, 5 e 10 anos exigem um ponto de partida real a esse tempo do fim (com uma tolerância curta). Se não
    houver, o status é "período insuficiente": o app NÃO troca por um período menor sem avisar.
  - Séries anuais, trimestrais e diárias não se misturam: CAGR só em séries anuais ou diárias; trimestre usa a variação
    sobre o MESMO trimestre do ano anterior e a soma dos últimos 4 trimestres (TTM).
  - Dado ausente fica ausente (NaN/None): não vira zero.
  - Preço (sem proventos) e retorno total (com proventos) são calculados separadamente por quem chama; este módulo só
    recebe a série certa para cada conta.

Os limites usados na análise automática são regras educacionais (constantes LIM_*), não recomendação de investimento.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import pandas as pd

PERIODOS = (1, 3, 5, 10)
TOL_ANUAL_DIAS = 45          # demonstrativos: o exercício fiscal pode fechar em datas diferentes de um ano para o outro
TOL_DIARIA_DIAS = 7          # preços: fins de semana e feriados

OK = "ok"
DADO_AUSENTE = "dado_ausente"
PERIODO_INSUFICIENTE = "periodo_insuficiente"
PERIODO_INVALIDO = "periodo_invalido"
BASE_NAO_POSITIVA = "base_nao_positiva"
RESULTADO_NAO_POSITIVO = "resultado_nao_positivo"
MUDANCA_DE_SINAL = "mudanca_de_sinal"
AMBOS_NEGATIVOS = "ambos_negativos"
SERIE_TRIMESTRAL = "serie_trimestral"

MENSAGENS = {
    OK: "",
    DADO_AUSENTE: "dado indisponível",
    PERIODO_INSUFICIENTE: "histórico insuficiente para este período",
    PERIODO_INVALIDO: "período inválido",
    BASE_NAO_POSITIVA: "valor inicial zero: CAGR não se aplica",
    RESULTADO_NAO_POSITIVO: "resultado final zero: CAGR não se aplica",
    MUDANCA_DE_SINAL: "mudou de sinal (prejuízo ↔ lucro): CAGR não se aplica",
    AMBOS_NEGATIVOS: "negativo no início e no fim: CAGR não se aplica",
    SERIE_TRIMESTRAL: "série trimestral: use a variação sobre o mesmo trimestre",
}

# limites educacionais da análise automática
LIM_ACELERACAO_PP = 0.10      # crescimento do último ano ≥ média anterior + 10 p.p.
LIM_DESACELERACAO_PP = 0.10   # crescimento do último ano ≤ média anterior − 10 p.p.
LIM_QUEDA = -0.05             # variação do último ano abaixo de −5% = queda
LIM_MARGEM_PP = 2.0           # variação de margem de pelo menos 2 p.p. entre o primeiro e o último ano
LIM_ALAVANCAGEM = 3.0         # dívida líquida / EBITDA a partir de 3× chama atenção
LIM_ALAV_ALTA = 4.0           # a partir de 4× é alavancagem alta
LIM_ALAV_AUMENTO = 0.5        # aumento de 0,5× na alavancagem entre o primeiro e o último ano
LIM_FCL_QUEDA = -0.30         # queda de 30% no fluxo de caixa livre
LIM_DIVERGENCIA = 0.10        # lucro e caixa operacional andando em sentidos opostos em mais de 10%
LIM_QUEDA_LUCRO = -0.20       # queda de 20% no lucro com receita crescendo


def _ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


# =============================================================================== CAGR
@dataclass
class Cagr:
    periodo: int                         # anos pedidos (1, 3, 5, 10)
    valor: float | None                  # fração ao ano (0,12 = 12% a.a.); None quando não se aplica
    status: str
    anos: float | None = None            # tempo real entre os dois pontos
    inicio: tuple | None = None          # (data ISO, valor)
    fim: tuple | None = None
    variacao_total: float | None = None  # fim ÷ início − 1, só com início positivo

    @property
    def ok(self) -> bool:
        return self.status == OK and self.valor is not None

    @property
    def texto(self) -> str:
        if self.ok:
            return _pct(self.valor * 100) + " a.a."
        return MENSAGENS.get(self.status, "indisponível")


def _pct(v: float) -> str:
    return f"{v:+,.1f}".replace(",", "X").replace(".", ",").replace("X", ".") + "%"


def cagr(v0, v1, anos) -> tuple[float | None, str]:
    """(taxa, status). Só calcula com início e fim positivos; o resto vira um status explicado."""
    if not (_ok(v0) and _ok(v1)):
        return None, DADO_AUSENTE
    if not _ok(anos) or anos <= 0:
        return None, PERIODO_INVALIDO
    if v0 == 0:
        return None, BASE_NAO_POSITIVA
    if v0 > 0 and v1 > 0:
        return (v1 / v0) ** (1.0 / anos) - 1.0, OK
    if (v0 > 0 > v1) or (v0 < 0 < v1):
        return None, MUDANCA_DE_SINAL
    if v0 > 0 and v1 == 0:
        return None, RESULTADO_NAO_POSITIVO
    return None, AMBOS_NEGATIVOS


def serie_limpa(serie) -> pd.Series:
    """Série numérica com índice de datas ordenado, sem NaN e sem fuso. Índice inteiro (ano) vira 31/12 do ano."""
    if serie is None:
        return pd.Series(dtype=float)
    s = pd.Series(serie).copy()
    s = pd.to_numeric(s, errors="coerce")
    if len(s) and pd.api.types.is_integer_dtype(s.index):
        s.index = pd.to_datetime([f"{int(a)}-12-31" for a in s.index])
    else:
        s.index = pd.to_datetime(s.index, errors="coerce")
    s = s[s.index.notna()].dropna()
    s = s[[math.isfinite(x) for x in s.values]] if len(s) else s
    if getattr(s.index, "tz", None) is not None:
        s.index = s.index.tz_localize(None)
    s = s[~s.index.duplicated(keep="last")]
    return s.sort_index()


def frequencia(s: pd.Series) -> str:
    """"diaria", "trimestral" ou "anual", pela mediana do espaçamento entre as datas ("indefinida" com < 2 pontos)."""
    if len(s) < 2:
        return "indefinida"
    mediana = s.index.to_series().diff().dropna().dt.days.median()
    if mediana <= 20:
        return "diaria"
    if mediana <= 150:
        return "trimestral"
    return "anual"


def _ponto_a(s: pd.Series, alvo, tol: int):
    """Ponto da série mais próximo de `alvo` (dentro de `tol` dias), anterior ao último ponto. None se não houver."""
    anteriores = s.iloc[:-1]
    if anteriores.empty:
        return None
    dist = abs((anteriores.index - alvo).days)
    k = int(dist.argmin())
    return (anteriores.index[k], float(anteriores.iloc[k])) if dist[k] <= tol else None


def cagr_periodos(serie, periodos=PERIODOS, tol_dias: int | None = None) -> dict[int, Cagr]:
    """CAGR do último ponto contra o ponto de N anos atrás, para cada N. Aceita série anual ou diária (não trimestral).
    Sem ponto de partida a ~N anos (tolerância curta), o status é 'período insuficiente': nada é estimado."""
    s = serie_limpa(serie)
    if s.empty:
        return {n: Cagr(n, None, DADO_AUSENTE) for n in periodos}
    freq = frequencia(s)
    if freq == "trimestral":
        return {n: Cagr(n, None, SERIE_TRIMESTRAL) for n in periodos}
    tol = tol_dias if tol_dias is not None else (TOL_DIARIA_DIAS if freq == "diaria" else TOL_ANUAL_DIAS)
    fim_d, fim_v = s.index[-1], float(s.iloc[-1])
    out = {}
    for n in periodos:
        p = _ponto_a(s, fim_d - pd.DateOffset(years=n), tol)
        if p is None:
            out[n] = Cagr(n, None, PERIODO_INSUFICIENTE)
            continue
        ini_d, ini_v = p
        anos = (fim_d - ini_d).days / 365.25
        v, st = cagr(ini_v, fim_v, anos)
        if st == OK and (s.loc[ini_d:fim_d] <= 0).any():      # passou por zero/prejuízo no meio do caminho
            v, st = None, MUDANCA_DE_SINAL
        out[n] = Cagr(n, v, st, round(anos, 2), (ini_d.date().isoformat(), ini_v), (fim_d.date().isoformat(), fim_v),
                      (fim_v / ini_v - 1) if ini_v > 0 else None)
    return out


def anos_ate(serie, anos: int) -> bool:
    """A série tem história suficiente para o período pedido?"""
    return cagr_periodos(serie, (anos,))[anos].status != PERIODO_INSUFICIENTE


# =============================================================================== variações
def variacao_anual(serie) -> pd.Series:
    """Variação de um ano para o outro (fração). Só existe quando o ano anterior é positivo e o atual é número."""
    s = serie_limpa(serie)
    if frequencia(s) == "trimestral":
        return pd.Series(dtype=float)
    ant = s.shift(1)
    g = (s / ant - 1).where(ant > 0)
    return g.dropna()


def variacao_trimestral_yoy(serie, tol_dias: int = 20) -> pd.Series:
    """Cada trimestre contra o MESMO trimestre do ano anterior (fração). Nunca compara trimestre com ano."""
    s = serie_limpa(serie)
    out = {}
    for d, v in s.items():
        alvo = d - pd.DateOffset(years=1)
        dist = abs((s.index - alvo).days)
        k = int(dist.argmin())
        i = s.index[k]
        if i < d and dist[k] <= tol_dias and s.iloc[k] > 0:
            out[d] = v / s.iloc[k] - 1
    return pd.Series(out, dtype=float)


def soma_12m(serie_trimestral) -> pd.Series:
    """Soma móvel de 4 trimestres consecutivos (TTM), só para valores de fluxo (receita, lucro, caixa operacional).
    Só soma quando os 4 trimestres são de fato consecutivos (espaçados ~3 meses)."""
    s = serie_limpa(serie_trimestral)
    out = {}
    for k in range(3, len(s)):
        j = s.iloc[k - 3:k + 1]
        d = j.index.to_series().diff().dropna().dt.days
        if len(j) == 4 and ((d >= 70) & (d <= 110)).all():
            out[s.index[k]] = float(j.sum())
    return pd.Series(out, dtype=float)


def consistencia(serie) -> dict:
    """Em quantos dos intervalos anuais o valor cresceu (entre os que têm base positiva) e a oscilação do crescimento."""
    g = variacao_anual(serie)
    if g.empty:
        return {"intervalos": 0, "com_crescimento": 0, "taxa": None, "desvio_pp": None}
    return {"intervalos": int(len(g)), "com_crescimento": int((g > 0).sum()),
            "taxa": float((g > 0).mean() * 100), "desvio_pp": float(g.std() * 100) if len(g) >= 2 else None}


def acumulado(serie, base: float = 100.0) -> pd.Series:
    """Crescimento acumulado indexado (início = base) para comparar ativos de tamanhos diferentes."""
    s = serie_limpa(serie)
    s = s[s > 0]
    return s / s.iloc[0] * base if len(s) else s


# =============================================================================== demonstrativos padronizados
COLUNAS = ["Receita líquida", "Lucro bruto", "EBITDA", "EBIT", "Lucro líquido", "Lucro antes do IR", "Imposto",
           "Ativo total", "Passivo total", "Patrimônio líquido", "Dívida bruta", "Dívida líquida", "Caixa",
           "Caixa operacional", "Capex", "Fluxo de caixa livre"]

# nomes das linhas nos demonstrativos do Yahoo Finance (yfinance); vale o primeiro com dado
ALIAS_YAHOO = {
    "Receita líquida": ["Total Revenue", "Operating Revenue", "Revenue"],
    "Lucro bruto": ["Gross Profit"],
    "EBITDA": ["EBITDA", "Normalized EBITDA"],
    "EBIT": ["EBIT", "Operating Income"],
    "Lucro líquido": ["Net Income", "Net Income Common Stockholders"],
    "Lucro antes do IR": ["Pretax Income"],
    "Imposto": ["Tax Provision"],
    "Ativo total": ["Total Assets"],
    "Passivo total": ["Total Liabilities Net Minority Interest", "Total Liabilities"],
    "Patrimônio líquido": ["Stockholders Equity", "Common Stock Equity", "Total Equity Gross Minority Interest"],
    "Dívida bruta": ["Total Debt"],
    "Dívida líquida": ["Net Debt"],
    "Caixa": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "Caixa operacional": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "Capex": ["Capital Expenditure"],
    "Fluxo de caixa livre": ["Free Cash Flow"],
}


def _linha(df: pd.DataFrame | None, nomes: list[str]) -> pd.Series | None:
    if df is None or getattr(df, "empty", True):
        return None
    por_nome = {str(i).strip().lower(): i for i in df.index}
    for n in nomes:
        i = por_nome.get(n.lower())
        if i is not None:
            s = pd.to_numeric(df.loc[i], errors="coerce")
            if s.notna().any():
                return s
    return None


def padronizar_yahoo(*tabelas) -> pd.DataFrame:
    """Junta DRE, balanço e fluxo de caixa do Yahoo (linhas = itens, colunas = datas) em uma tabela padrão
    (linhas = datas dos exercícios/trimestres, colunas = COLUNAS). Item que o Yahoo não traz fica fora (NaN):
    nunca vira zero. Dívida líquida e FCL só são derivados quando todos os insumos existem (marcados em .attrs)."""
    cols = {}
    for nome in COLUNAS:
        for t in tabelas:
            s = _linha(t, ALIAS_YAHOO.get(nome, []))
            if s is not None:
                cols[nome] = s
                break
    if not cols:
        return pd.DataFrame()
    df = pd.DataFrame(cols)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df[df.index.notna()]
    if getattr(df.index, "tz", None) is not None:
        df.index = df.index.tz_localize(None)
    df = df[~df.index.duplicated(keep="first")].sort_index().dropna(how="all")
    derivados = []
    if "Dívida líquida" not in df and {"Dívida bruta", "Caixa"} <= set(df):
        df["Dívida líquida"] = df["Dívida bruta"] - df["Caixa"]
        derivados.append("Dívida líquida")
    if "Fluxo de caixa livre" not in df and {"Caixa operacional", "Capex"} <= set(df):
        df["Fluxo de caixa livre"] = df["Caixa operacional"] - df["Capex"].abs()
        derivados.append("Fluxo de caixa livre")
    df.attrs["derivados"] = derivados
    return df


def derivar_indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """Margens, ROE e ROIC a partir da tabela padrão (todos CALCULADOS, em %). Falta de insumo = NaN.
    ROE = lucro líquido ÷ patrimônio líquido do fim do período (anual; no trimestre use o TTM antes de comparar).
    ROIC = EBIT × (1 − alíquota efetiva) ÷ (dívida bruta + patrimônio líquido − caixa), com a alíquota efetiva
    = imposto ÷ lucro antes do IR (entre 0 e 50%). Sem esses dados o ROIC fica indisponível (não se assume alíquota)."""
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()

    def col(n):
        return out[n] if n in out else pd.Series(float("nan"), index=out.index)
    rec = col("Receita líquida").where(col("Receita líquida") > 0)
    out["Margem bruta"] = col("Lucro bruto") / rec * 100
    out["Margem EBITDA"] = col("EBITDA") / rec * 100
    out["Margem líquida"] = col("Lucro líquido") / rec * 100
    pl = col("Patrimônio líquido").where(col("Patrimônio líquido") > 0)
    out["ROE"] = col("Lucro líquido") / pl * 100
    aliq = (col("Imposto") / col("Lucro antes do IR").where(col("Lucro antes do IR") > 0)).clip(0, 0.5)
    capital = (col("Dívida bruta") + col("Patrimônio líquido") - col("Caixa")).where(lambda x: x > 0)
    out["ROIC"] = col("EBIT") * (1 - aliq) / capital * 100
    out["Dívida líquida/EBITDA"] = col("Dívida líquida") / col("EBITDA").where(col("EBITDA") > 0)
    return out


FLUXOS = ["Receita líquida", "Lucro bruto", "EBITDA", "EBIT", "Lucro líquido", "Caixa operacional", "Fluxo de caixa livre"]


def tabela_cagr(df_anual: pd.DataFrame, colunas=None, periodos=PERIODOS) -> pd.DataFrame:
    """Linhas = indicadores, colunas = períodos (1a, 3a, 5a, 10a). Cada célula: texto do CAGR ou o motivo."""
    colunas = [c for c in (colunas or ["Receita líquida", "EBITDA", "Lucro líquido", "Fluxo de caixa livre",
                                       "Patrimônio líquido"]) if df_anual is not None and c in df_anual]
    linhas = []
    for c in colunas:
        r = cagr_periodos(df_anual[c], periodos)
        linhas.append({"Indicador": c, **{f"{n} ano" + ("s" if n > 1 else ""): r[n].texto for n in periodos}})
    return pd.DataFrame(linhas)


# =============================================================================== análise automática
@dataclass
class Achado:
    chave: str
    tom: str                 # "positivo" | "atencao" | "neutro"
    titulo: str
    texto: str
    evidencias: list = field(default_factory=list)


def _fmt(v, kind="pct") -> str:
    if not _ok(v):
        return "n/d"
    if kind == "pct":
        return _pct(v * 100)
    if kind == "pp":
        return f"{v:+.1f}".replace(".", ",") + " p.p."
    if kind == "x":
        return f"{v:.1f}×".replace(".", ",")
    a = abs(v)
    for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if a >= lim:
            return f"{v / lim:,.1f}{suf}".replace(".", ",")
    return f"{v:,.0f}".replace(",", ".")


def _ano(d) -> str:
    return str(pd.Timestamp(d).year)


def diagnosticar(df_anual: pd.DataFrame, financeira: bool = False) -> list[Achado]:
    """Explica, com números, o que aconteceu nos últimos exercícios anuais. Exige pelo menos 3 exercícios; sem isso
    devolve um único achado dizendo que o histórico é insuficiente (nada é estimado). Para bancos e seguradoras
    (`financeira=True`), EBITDA, margem bruta, dívida líquida e fluxo de caixa livre não são medidas significativas
    (dívida e caixa são a matéria-prima do negócio), então essas regras não rodam."""
    if df_anual is None or df_anual.empty or len(df_anual) < 3:
        n = 0 if df_anual is None else len(df_anual)
        return [Achado("historico", "neutro", "Histórico insuficiente",
                       f"Só há {n} exercício(s) anual(is) com dados; a análise automática pede pelo menos 3.")]
    df = derivar_indicadores(df_anual)
    if financeira:
        df = df.drop(columns=[c for c in ("EBITDA", "Lucro bruto", "Margem bruta", "Margem EBITDA", "Dívida bruta", "Dívida líquida",
                                          "Dívida líquida/EBITDA", "Fluxo de caixa livre", "Capex", "Caixa operacional")
                              if c in df.columns])
    ach: list[Achado] = []

    # --- receita
    g = variacao_anual(df["Receita líquida"]) if "Receita líquida" in df else pd.Series(dtype=float)
    if len(g) >= 2:
        ult, ant = g.iloc[-1], g.iloc[:-1].mean()
        ev = [f"{_ano(d)}: {_fmt(v)}" for d, v in g.items()]
        if ult <= LIM_QUEDA:
            ach.append(Achado("receita_queda", "atencao", "Queda da receita",
                              f"A receita caiu {_fmt(ult)} no último exercício.", ev))
        elif (g > 0).all():
            ach.append(Achado("receita_consistente", "positivo", "Crescimento consistente da receita",
                              f"A receita cresceu em todos os {len(g)} últimos anos (último: {_fmt(ult)}).", ev))
        if ult - ant >= LIM_ACELERACAO_PP and ult > 0.05:
            ach.append(Achado("receita_acelera", "positivo", "Crescimento acelerado",
                              f"O crescimento da receita subiu para {_fmt(ult)}, contra média de {_fmt(ant)} antes.", ev))
        elif ant > 0 and ult >= LIM_QUEDA and ult <= ant - LIM_DESACELERACAO_PP:
            ach.append(Achado("receita_desacelera", "atencao", "Desaceleração",
                              f"O crescimento da receita caiu para {_fmt(ult)}, contra média de {_fmt(ant)} antes.", ev))

    # --- lucro
    if "Lucro líquido" in df:
        ln = df["Lucro líquido"].dropna()
        if len(ln) >= 2:
            a, b = float(ln.iloc[-2]), float(ln.iloc[-1])
            ev = [f"{_ano(d)}: {_fmt(v, 'n')}" for d, v in ln.items()]
            if a > 0 > b:
                ach.append(Achado("lucro_prejuizo", "atencao", "Prejuízo no último exercício",
                                  f"O lucro líquido virou prejuízo ({_fmt(a, 'n')} → {_fmt(b, 'n')}).", ev))
            elif a < 0 < b:
                ach.append(Achado("lucro_retomada", "positivo", "Retomada do lucro",
                                  f"O resultado voltou a ser positivo ({_fmt(a, 'n')} → {_fmt(b, 'n')}).", ev))
            elif a > 0 and b / a - 1 <= LIM_QUEDA:
                ach.append(Achado("lucro_queda", "atencao", "Queda dos resultados",
                                  f"O lucro líquido caiu {_fmt(b / a - 1)} no último exercício.", ev))
            elif a > 0 and b > a:
                ach.append(Achado("lucro_alta", "positivo", "Lucro em alta",
                                  f"O lucro líquido subiu {_fmt(b / a - 1)} no último exercício.", ev))
            sinais = (ln > 0).astype(int).diff().abs().sum()
            if sinais >= 2:
                ach.append(Achado("lucro_oscila", "atencao", "Resultado instável",
                                  f"O lucro líquido mudou de sinal {int(sinais)} vezes no período.", ev))
        if len(g) and "Lucro líquido" in df:
            gl = variacao_anual(df["Lucro líquido"])
            if len(g) and len(gl) and g.iloc[-1] > 0 and gl.iloc[-1] <= LIM_QUEDA_LUCRO:
                ach.append(Achado("receita_sobe_lucro_cai", "atencao", "Receita cresce, lucro cai",
                                  f"A receita subiu {_fmt(g.iloc[-1])}, mas o lucro caiu {_fmt(gl.iloc[-1])}: "
                                  "a empresa está convertendo menos receita em lucro.",
                                  [f"Receita: {_fmt(g.iloc[-1])}", f"Lucro líquido: {_fmt(gl.iloc[-1])}"]))

    # --- margens
    for nome in ("Margem bruta", "Margem EBITDA", "Margem líquida"):
        m = df[nome].dropna() if nome in df else pd.Series(dtype=float)
        if len(m) >= 2:
            dif = float(m.iloc[-1] - m.iloc[0])
            ev = [f"{_ano(d)}: {v:.1f}%".replace(".", ",") for d, v in m.items()]
            if dif >= LIM_MARGEM_PP:
                ach.append(Achado(f"{nome}_melhora", "positivo", f"{nome} em melhora",
                                  f"{nome} subiu {_fmt(dif, 'pp')} entre {_ano(m.index[0])} e {_ano(m.index[-1])}.", ev))
            elif dif <= -LIM_MARGEM_PP:
                ach.append(Achado(f"{nome}_piora", "atencao", f"{nome} em deterioração",
                                  f"{nome} caiu {_fmt(dif, 'pp')} entre {_ano(m.index[0])} e {_ano(m.index[-1])}.", ev))

    # --- endividamento
    alav = df["Dívida líquida/EBITDA"].dropna() if "Dívida líquida/EBITDA" in df else pd.Series(dtype=float)
    if len(alav):
        a1 = float(alav.iloc[-1])
        ev = [f"{_ano(d)}: {v:.1f}×".replace(".", ",") for d, v in alav.items()]
        subiu = len(alav) >= 2 and a1 - float(alav.iloc[0]) >= LIM_ALAV_AUMENTO
        if a1 >= LIM_ALAV_ALTA or (a1 >= LIM_ALAVANCAGEM and subiu):
            ach.append(Achado("alavancagem", "atencao", "Endividamento elevado",
                              f"A dívida líquida equivale a {_fmt(a1, 'x')} o EBITDA"
                              + (" e vem subindo" if subiu else "") + ".", ev))
        elif subiu and a1 > 0:
            ach.append(Achado("alavancagem_sobe", "atencao", "Endividamento em alta",
                              f"A dívida líquida/EBITDA subiu para {_fmt(a1, 'x')}.", ev))
    elif {"EBITDA", "Dívida bruta"} <= set(df):
        u = df.dropna(subset=["EBITDA", "Dívida bruta"]).tail(1)
        if len(u) and float(u["EBITDA"].iloc[0]) <= 0 < float(u["Dívida bruta"].iloc[0]):
            ach.append(Achado("alavancagem_ebitda", "atencao", "Dívida sem geração operacional",
                              "A empresa tem dívida e EBITDA zero ou negativo no último exercício.", []))

    # --- caixa
    fcl = df["Fluxo de caixa livre"].dropna() if "Fluxo de caixa livre" in df else pd.Series(dtype=float)
    if len(fcl) >= 2:
        a, b = float(fcl.iloc[0]), float(fcl.iloc[-1])
        ev = [f"{_ano(d)}: {_fmt(v, 'n')}" for d, v in fcl.items()]
        if b < 0:
            ach.append(Achado("fcl_negativo", "atencao", "Fluxo de caixa livre negativo",
                              f"O fluxo de caixa livre do último exercício foi negativo ({_fmt(b, 'n')}).", ev))
        elif a > 0 and b > a:
            ach.append(Achado("fcl_melhora", "positivo", "Melhora na geração de caixa",
                              f"O fluxo de caixa livre subiu de {_fmt(a, 'n')} para {_fmt(b, 'n')}.", ev))
        elif a > 0 and b / a - 1 <= LIM_FCL_QUEDA:
            ach.append(Achado("fcl_queda", "atencao", "Geração de caixa em queda",
                              f"O fluxo de caixa livre caiu {_fmt(b / a - 1)} desde {_ano(fcl.index[0])}.", ev))

    # --- inconsistências entre lucro e caixa
    if {"Lucro líquido", "Caixa operacional"} <= set(df):
        j = df[["Lucro líquido", "Caixa operacional"]].dropna()
        if len(j):
            ll, co = float(j["Lucro líquido"].iloc[-1]), float(j["Caixa operacional"].iloc[-1])
            if ll > 0 > co:
                ach.append(Achado("lucro_sem_caixa", "atencao", "Lucro sem geração de caixa",
                                  "A empresa registrou lucro, mas o caixa operacional foi negativo no último exercício.",
                                  [f"Lucro líquido: {_fmt(ll, 'n')}", f"Caixa operacional: {_fmt(co, 'n')}"]))
        if len(j) >= 2:
            gl, gc = variacao_anual(j["Lucro líquido"]), variacao_anual(j["Caixa operacional"])
            if len(gl) and len(gc) and gl.index[-1] == gc.index[-1] and gl.iloc[-1] >= LIM_DIVERGENCIA \
                    and gc.iloc[-1] <= -LIM_DIVERGENCIA:
                ach.append(Achado("lucro_caixa_divergem", "atencao", "Lucro sobe, caixa operacional cai",
                                  f"O lucro subiu {_fmt(gl.iloc[-1])}, mas o caixa operacional caiu {_fmt(gc.iloc[-1])}: "
                                  "vale conferir a qualidade do lucro.",
                                  [f"Lucro líquido: {_fmt(gl.iloc[-1])}", f"Caixa operacional: {_fmt(gc.iloc[-1])}"]))

    # --- crescimento com mais risco
    cr = cagr_periodos(df["Receita líquida"], (3, 1)) if "Receita líquida" in df else {}
    base = next((c for c in (cr.get(3), cr.get(1)) if c is not None and c.ok), None)
    mais_risco = [a.titulo for a in ach if a.chave in ("alavancagem", "alavancagem_sobe", "Margem líquida_piora",
                                                       "Margem EBITDA_piora", "fcl_negativo")]
    if base is not None and base.valor > 0 and mais_risco:
        ach.append(Achado("crescimento_com_risco", "atencao", "Crescimento acompanhado de mais risco",
                          f"A receita cresce {_fmt(base.valor)} a.a., mas o risco financeiro aumentou ("
                          + "; ".join(mais_risco).lower() + ").", [f"CAGR da receita ({base.periodo}a): {base.texto}"]))
    if financeira:
        ach.append(Achado("financeira", "neutro", "Instituição financeira",
                          "Em bancos e seguradoras, EBITDA, dívida líquida e fluxo de caixa livre não medem a saúde do negócio "
                          "(dívida e caixa são a matéria-prima). Por isso a análise usa receita, lucro, margem líquida e ROE.", []))
    if not ach:
        ach.append(Achado("estavel", "neutro", "Sem sinais marcantes",
                          "Nenhuma das regras de alerta ou melhora foi acionada nos últimos exercícios.", []))
    return ach


# =============================================================================== valor real e benchmarks (IPCA, CDI)
def indice_de_taxas(taxas_pct, base: float = 100.0) -> pd.Series:
    """Índice acumulado a partir de taxas em % por período (IPCA mensal, CDI diário). O primeiro ponto vale `base`
    ANTES da primeira taxa: o índice na data t já inclui a taxa de t."""
    s = serie_limpa(taxas_pct)
    return (1 + s / 100).cumprod() * base if len(s) else s


def valor_real(nominal, ipca_mensal_pct) -> tuple[pd.Series, str | None]:
    """Série a preços de HOJE (último índice disponível): real_t = nominal_t × índice_final ÷ índice_t.
    O IPCA do SGS é mensal e datado no dia 1; o valor de um dia usa o índice do último mês já fechado. Só devolve o
    trecho coberto pelo IPCA; o aviso diz se houve corte. Sem IPCA, devolve série vazia."""
    s = serie_limpa(nominal)
    idx = indice_de_taxas(ipca_mensal_pct)
    if s.empty or idx.empty:
        return pd.Series(dtype=float), "IPCA indisponível: valor real não calculado."
    s = s[s.index >= idx.index[0]]
    if s.empty:
        return pd.Series(dtype=float), "Sem sobreposição entre o ativo e a série de IPCA."
    ref = idx.reindex(s.index, method="ffill")
    ok = ref.notna()
    s, ref = s[ok], ref[ok]
    real = s * float(idx.iloc[-1]) / ref
    aviso = None
    if serie_limpa(nominal).index[0] < idx.index[0]:
        aviso = f"Valor real a partir de {idx.index[0].strftime('%m/%Y')} (início da série de IPCA usada)."
    return real, aviso


def retorno_no_periodo(serie, anos: int) -> dict:
    """Retorno acumulado e anualizado do último ponto contra o de `anos` atrás (mesma regra de datas do CAGR)."""
    c = cagr_periodos(serie, (anos,))[anos]
    return {"anos": anos, "ok": c.ok, "acumulado": c.variacao_total if c.ok else None,
            "anual": c.valor if c.ok else None, "inicio": c.inicio[0] if c.inicio else None,
            "fim": c.fim[0] if c.fim else None, "status": c.status}


def contra_benchmarks(retorno_total, cdi_idx, ipca_idx, anos: int = 3) -> dict:
    """Retorno total do ativo na MESMA janela (datas reais) do CDI e do IPCA: % do CDI e ganho real sobre a inflação.
    Se alguma ponta não existir, devolve motivo em vez de número. Fisher: real = (1+nominal)/(1+inflação) − 1."""
    a = retorno_no_periodo(retorno_total, anos)
    if not a["ok"]:
        return {"ok": False, "motivo": MENSAGENS.get(a["status"], "indisponível"), "anos": anos}
    ini, fim = pd.Timestamp(a["inicio"]), pd.Timestamp(a["fim"])

    def acc(idx):
        s = serie_limpa(idx)
        if s.empty or s.index[0] > ini or s.index[-1] < fim - pd.Timedelta(days=45):
            return None
        return float(s.asof(fim) / s.asof(ini) - 1)
    cdi, ipca = acc(cdi_idx), acc(ipca_idx)
    nom = a["acumulado"]
    out = {"ok": True, "anos": anos, "inicio": a["inicio"], "fim": a["fim"], "ativo": nom, "cdi": cdi, "ipca": ipca,
           "pct_cdi": (nom / cdi * 100) if cdi and cdi > 0 and nom is not None else None,
           "real": ((1 + nom) / (1 + ipca) - 1) if ipca is not None and nom is not None else None}
    out["real_anual"] = ((1 + out["real"]) ** (365.25 / (fim - ini).days) - 1) if out["real"] is not None and 1 + out["real"] > 0 else None
    return out
