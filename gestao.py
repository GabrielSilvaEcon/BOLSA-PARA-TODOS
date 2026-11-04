"""
Gestão inteligente de carteiras (Passo 12) — motor de cálculo, SEM Streamlit e SEM rede.

Recebe dados já coletados (lotes, preços, câmbio, proventos) e devolve números. Quem coleta é gestao_app.py, que reaproveita
os coletores dos outros passos (carteira.py, fiis_app, fundos_app, renda_fixa_app). Nada aqui compra, vende ou altera posição.

Convenções
- Retornos são simples e diários (fração: 0,01 = 1%). Anualização com 252 pregões.
- Valores em R$. Ativo em moeda estrangeira: o preço nativo é multiplicado pelo dólar (BCB) da mesma data.
- Preço pago nos lançamentos está na moeda do ativo (como a página Carteira já faz). Custo médio nas vendas.
- Estatísticas de risco usam a carteira ATUAL com pesos constantes sobre o histórico dos ativos ("e se eu tivesse essa
  carteira"): descrevem o passado e não garantem o futuro. O desempenho (TWR e XIRR) usa as compras reais, nas datas reais.
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime
from statistics import NormalDist

import numpy as np
import pandas as pd

DIAS_ANO = 252

CLASSES = {"acao": "Ações", "bdr": "BDRs", "fii": "FIIs", "etf": "ETFs", "fundo": "Fundos", "cripto": "Criptomoedas",
           "renda_fixa": "Renda fixa", "caixa": "Caixa", "outro": "Outros"}

_BDR = re.compile(r"[A-Z]{4}(3[2-5]|39)")
_B3 = re.compile(r"[A-Z]{4}\d{1,2}")

SETORES_PT = {
    "Financial Services": "Financeiro", "Energy": "Petróleo e energia", "Basic Materials": "Materiais básicos",
    "Utilities": "Utilidade pública", "Consumer Cyclical": "Consumo cíclico", "Consumer Defensive": "Consumo defensivo",
    "Industrials": "Indústria", "Technology": "Tecnologia", "Healthcare": "Saúde", "Real Estate": "Imobiliário",
    "Communication Services": "Comunicação",
}

# O que move cada setor (dependência econômica). Só o que é consenso; setor desconhecido fica em "Outros fatores".
FATOR_DO_SETOR = {
    "Financeiro": "Juros e crédito", "Imobiliário": "Juros e crédito", "Petróleo e energia": "Commodities e dólar",
    "Materiais básicos": "Commodities e dólar", "Consumo cíclico": "Consumo doméstico", "Consumo defensivo": "Consumo doméstico",
    "Utilidade pública": "Setores regulados", "Tecnologia": "Tecnologia global", "Saúde": "Saúde",
}


# =============================================================================== utilidades
def _ok(x) -> bool:
    return isinstance(x, (int, float, np.floating, np.integer)) and not isinstance(x, bool) and math.isfinite(float(x))


def _tk(t) -> str:
    return str(t or "").upper().strip().replace(".SA", "")


def _data(d) -> date | None:
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    try:
        t = pd.to_datetime(d)
        return None if pd.isna(t) else t.date()
    except Exception:
        return None


def eh_bdr(tk: str) -> bool:
    return bool(_BDR.fullmatch(_tk(tk)))


def moeda_do_ticker(tk: str) -> str:
    """Moeda em que o Yahoo cota o código. B3 = BRL; ...-BRL = BRL; ...-USD e demais códigos = USD. É uma regra de formato:
    quando o Yahoo informar a moeda de verdade, a camada de coleta a usa no lugar."""
    t = _tk(tk)
    if _B3.fullmatch(t) or t.endswith("-BRL"):
        return "BRL"
    return "USD"


def pais_do_ticker(tk: str, classe: str) -> str:
    if classe == "renda_fixa" or classe == "caixa":
        return "Brasil"
    if classe == "cripto":
        return "Global (cripto)"
    return "Brasil" if moeda_do_ticker(tk) == "BRL" else "Exterior (EUA e outros)"


# =============================================================================== lançamentos → posições
def normalizar_movs(lotes: list, vendas: list | tuple = ()) -> tuple[list[dict], list[str]]:
    """Junta compras (lotes da carteira) e vendas/retiradas num só livro, em ordem de data. Descarta linhas inválidas e vendas
    maiores que a posição, sempre com aviso (nada some em silêncio)."""
    avisos: list[str] = []
    movs: list[dict] = []
    for tipo, fonte in (("compra", lotes or []), ("venda", vendas or [])):
        for l in fonte:
            if not isinstance(l, dict):
                continue
            tk, d = _tk(l.get("ticker")), _data(l.get("data"))
            try:
                q, p = float(l.get("qtd")), float(l.get("preco_medio", l.get("preco")))
            except (TypeError, ValueError):
                q, p = float("nan"), float("nan")
            if not tk or d is None or not (math.isfinite(q) and q > 0) or not (math.isfinite(p) and p >= 0):
                avisos.append(f"Lançamento ignorado (dados inválidos): {tk or '?'} {l.get('data', '')}.")
                continue
            movs.append({"ticker": tk, "tipo": tipo, "qtd": q, "preco": p, "data": d})
    movs.sort(key=lambda m: (m["data"], 0 if m["tipo"] == "compra" else 1))
    pos: dict[str, float] = {}
    ok = []
    for m in movs:
        atual = pos.get(m["ticker"], 0.0)
        if m["tipo"] == "venda":
            if m["qtd"] > atual + 1e-9:
                avisos.append(f"Venda de {m['qtd']:g} {m['ticker']} em {m['data']:%d/%m/%Y} ignorada: a posição na data era {atual:g}.")
                continue
            pos[m["ticker"]] = atual - m["qtd"]
        else:
            pos[m["ticker"]] = atual + m["qtd"]
        ok.append(m)
    return ok, avisos


def posicoes_de_movs(movs: list[dict]) -> dict[str, dict]:
    """Posição atual por ativo pelo custo médio: {qtd, custo, preco_medio, realizado, aportado, retirado}. Valores na moeda do ativo."""
    out: dict[str, dict] = {}
    for m in movs:
        e = out.setdefault(m["ticker"], {"qtd": 0.0, "custo": 0.0, "realizado": 0.0, "aportado": 0.0, "retirado": 0.0})
        if m["tipo"] == "compra":
            e["qtd"] += m["qtd"]
            e["custo"] += m["qtd"] * m["preco"]
            e["aportado"] += m["qtd"] * m["preco"]
        else:
            pm = e["custo"] / e["qtd"] if e["qtd"] > 0 else 0.0
            e["realizado"] += m["qtd"] * (m["preco"] - pm)
            e["custo"] -= m["qtd"] * pm
            e["qtd"] -= m["qtd"]
            e["retirado"] += m["qtd"] * m["preco"]
        if e["qtd"] < 1e-9:
            e["qtd"], e["custo"] = 0.0, 0.0
    for e in out.values():
        e["preco_medio"] = e["custo"] / e["qtd"] if e["qtd"] > 0 else None
    return out


def quantidades_no_tempo(movs: list[dict], datas: pd.DatetimeIndex) -> pd.DataFrame:
    """Quantidade de cada ativo em cada data (compras somam, vendas subtraem). Datas sem pregão herdam a anterior."""
    if not movs:
        return pd.DataFrame(index=datas)
    df = pd.DataFrame([{"data": pd.Timestamp(m["data"]), "ticker": m["ticker"],
                        "q": m["qtd"] if m["tipo"] == "compra" else -m["qtd"]} for m in movs])
    piv = df.pivot_table(index="data", columns="ticker", values="q", aggfunc="sum").fillna(0.0).sort_index().cumsum()
    todas = piv.index.union(pd.DatetimeIndex(datas))
    return piv.reindex(todas).ffill().fillna(0.0).reindex(pd.DatetimeIndex(datas)).fillna(0.0)


def precos_em_brl(precos: dict[str, pd.Series], moedas: dict[str, str], cambio: pd.Series | None) -> tuple[pd.DataFrame, list[str]]:
    """Série de preços de cada ativo em R$. Ativo em dólar sem série de câmbio fica de fora (aviso): nunca mistura moedas."""
    cols, avisos = {}, []
    fx = None
    if cambio is not None and len(cambio):
        fx = cambio.copy()
        fx.index = pd.DatetimeIndex(fx.index).tz_localize(None) if pd.DatetimeIndex(fx.index).tz is not None else pd.DatetimeIndex(fx.index)
        fx = fx[~fx.index.duplicated(keep="last")].sort_index()
    for tk, s in precos.items():
        if s is None or len(s) == 0:
            continue
        s = s.copy().dropna()
        s.index = pd.DatetimeIndex(s.index).normalize()
        s = s[~s.index.duplicated(keep="last")].sort_index()
        if moedas.get(tk, "BRL") == "BRL":
            cols[tk] = s
        elif fx is None or fx.empty:
            avisos.append(f"{tk} cotado em {moedas.get(tk)} sem série de câmbio: ficou fora das séries históricas.")
        else:
            cols[tk] = s * fx.reindex(s.index.union(fx.index)).ffill().reindex(s.index)
    df = pd.DataFrame(cols).sort_index() if cols else pd.DataFrame()
    return df, avisos


def valor_historico(qtd: pd.DataFrame, precos: pd.DataFrame) -> tuple[pd.Series, list[str]]:
    """Valor da carteira por data = Σ quantidade × preço em R$ (preço do último pregão conhecido). Ativo sem preço na data
    com posição aberta fica fora e é listado: o valor é um MÍNIMO nesse caso."""
    if qtd.empty or precos.empty:
        return pd.Series(dtype=float), []
    idx = precos.index
    p = precos.reindex(idx.union(qtd.index)).ffill().reindex(qtd.index)
    cols = [c for c in qtd.columns if c in p.columns]
    faltam = sorted(c for c in qtd.columns if c not in p.columns and (qtd[c] > 0).any())
    v = (qtd[cols] * p[cols]).sum(axis=1, min_count=1)
    avisos = [f"Sem histórico de preço: {', '.join(faltam)}. Esses ativos não entram nas séries de desempenho e risco."] if faltam else []
    return v.dropna(), avisos


def fluxos_externos(movs: list[dict], moedas: dict[str, str], cambio: pd.Series | None) -> list[tuple[date, float]]:
    """Aportes (+) e retiradas (−) em R$, na data de cada lançamento (câmbio da data para ativos em dólar)."""
    fx = None
    if cambio is not None and len(cambio):
        fx = pd.Series(cambio.values, index=pd.DatetimeIndex(cambio.index).normalize()).sort_index()
        fx = fx[~fx.index.duplicated(keep="last")]
    out = []
    for m in movs:
        v = m["qtd"] * m["preco"]
        if moedas.get(m["ticker"], "BRL") != "BRL":
            if fx is None or fx.empty:
                continue
            ts = pd.Timestamp(m["data"])
            f = fx.loc[:ts]
            v *= float(f.iloc[-1]) if len(f) else float(fx.iloc[0])
        out.append((m["data"], v if m["tipo"] == "compra" else -v))
    return out


# =============================================================================== desempenho
def twr(valor: pd.Series, fluxos: list[tuple[date, float]], proventos_acum: pd.Series | None = None) -> dict:
    """Retorno ponderado pelo tempo (TWR), encadeado dia a dia: r_t = (W_t − F_t) / W_{t−1} − 1, com W = valor + proventos
    acumulados e F = aportes líquidos do dia. Aporte não conta como lucro. Sem `proventos_acum` é o retorno de PREÇO."""
    if valor is None or len(valor) < 2:
        return {"ok": False, "motivo": "histórico insuficiente"}
    v = valor.astype(float).copy()
    v.index = pd.DatetimeIndex(v.index).normalize()
    f = pd.Series(0.0, index=v.index)
    for d, x in fluxos:
        ts = pd.Timestamp(d)
        pos = v.index.searchsorted(ts)                    # primeiro pregão em ou depois da data
        if pos < len(v):
            f.iloc[pos] += x
    w = v.copy()
    if proventos_acum is not None and len(proventos_acum):
        pa = proventos_acum.copy()
        pa.index = pd.DatetimeIndex(pa.index).normalize()
        w = w + pa.reindex(pa.index.union(v.index)).ffill().fillna(0.0).reindex(v.index)
    ant = w.shift(1)
    r = (w - f) / ant - 1
    r[(ant <= 0) | ~np.isfinite(r)] = np.nan
    r = r.dropna()
    if r.empty:
        return {"ok": False, "motivo": "sem dias com patrimônio anterior"}
    idx = (1 + r).cumprod()
    return {"ok": True, "retornos": r, "indice": idx, "total": float(idx.iloc[-1] - 1),
            "inicio": r.index[0].date(), "fim": r.index[-1].date()}


def cagr(total: float, dias: float) -> float | None:
    if not _ok(total) or not _ok(dias) or dias < 30 or total <= -1:
        return None
    return float((1 + total) ** (365.25 / dias) - 1)


def xirr(fluxos: list[tuple[date, float]]) -> float | None:
    """Retorno ponderado pelo dinheiro (MWR) ao ano. Fluxos do ponto de vista do investidor: aporte negativo, retirada,
    provento e valor final positivos. Bissecção sobre a taxa (robusta quando Newton diverge). None se não houver sinal troca."""
    fl = [(_data(d), float(v)) for d, v in fluxos if _ok(v) and abs(v) > 1e-12 and _data(d)]
    if len(fl) < 2 or not any(v < 0 for _, v in fl) or not any(v > 0 for _, v in fl):
        return None
    t0 = min(d for d, _ in fl)

    def f(r):
        return sum(v / (1 + r) ** ((d - t0).days / 365.0) for d, v in fl)
    lo, hi = -0.9999, 10.0
    flo, fhi = f(lo), f(hi)
    if not (math.isfinite(flo) and math.isfinite(fhi)) or flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if abs(fm) < 1e-9:
            return mid
        if flo * fm < 0:
            hi = mid
        else:
            lo, flo = mid, fm
    return (lo + hi) / 2


def retorno_por_periodo(retornos: pd.Series, freq: str) -> pd.Series:
    """Retorno composto por mês ('M') ou ano ('Y') calendário."""
    if retornos is None or retornos.empty:
        return pd.Series(dtype=float)
    r = retornos.copy()
    r.index = pd.DatetimeIndex(r.index)
    grupo = r.groupby(r.index.to_period("M" if freq == "M" else "Y"))
    return grupo.apply(lambda x: float((1 + x).prod() - 1))


def janelas(indice: pd.Series, hoje: date | None = None) -> dict:
    """Retorno acumulado em 1, 3, 6, 12 meses, no ano e desde o início, a partir de um índice (base qualquer)."""
    if indice is None or len(indice) < 2:
        return {}
    idx = indice.copy()
    idx.index = pd.DatetimeIndex(idx.index)
    fim = idx.index[-1]
    out = {}
    for rot, meses in (("1 mês", 1), ("3 meses", 3), ("6 meses", 6), ("12 meses", 12)):
        ini = fim - pd.DateOffset(months=meses)
        if idx.index[0] <= ini:
            base = idx.loc[:ini].iloc[-1]
            out[rot] = float(idx.iloc[-1] / base - 1)
    ano0 = pd.Timestamp(year=fim.year, month=1, day=1)
    if idx.index[0] < ano0:
        out["No ano"] = float(idx.iloc[-1] / idx.loc[:ano0 - pd.Timedelta(days=1)].iloc[-1] - 1)
    out["Desde o início"] = float(idx.iloc[-1] / idx.iloc[0] - 1)
    return out


def consistencia(retornos: pd.Series, bench: pd.Series | None = None) -> dict:
    """% de meses positivos, melhor/pior mês e (com benchmark) % de meses acima dele. Precisa de ≥ 6 meses."""
    m = retorno_por_periodo(retornos, "M")
    if len(m) < 6:
        return {"ok": False, "motivo": "menos de 6 meses de histórico"}
    out = {"ok": True, "meses": int(len(m)), "pct_positivos": float((m > 0).mean()), "melhor": float(m.max()),
           "pior": float(m.min()), "desvio_mensal": float(m.std(ddof=1))}
    if bench is not None and len(bench):
        b = retorno_por_periodo(bench, "M")
        j = pd.concat([m, b], axis=1, join="inner").dropna()
        if len(j) >= 6:
            out["pct_acima_bench"] = float((j.iloc[:, 0] > j.iloc[:, 1]).mean())
            out["meses_bench"] = int(len(j))
    return out


# =============================================================================== risco
def vol_anual(r: pd.Series, minimo: int = 30) -> float | None:
    r = r.dropna() if r is not None else r
    return float(r.std(ddof=1) * math.sqrt(DIAS_ANO)) if r is not None and len(r) >= minimo else None


def drawdown(indice: pd.Series) -> dict:
    """Queda máxima do pico ao vale e a queda atual. Datas do pico, do vale e (se houve) da recuperação."""
    if indice is None or len(indice) < 2:
        return {"ok": False}
    s = indice.astype(float)
    pico = s.cummax()
    dd = s / pico - 1
    vale = dd.idxmin()
    pico_data = s.loc[:vale].idxmax()
    rec = s.loc[vale:][s.loc[vale:] >= s.loc[pico_data]]
    return {"ok": True, "maximo": float(dd.min()), "atual": float(dd.iloc[-1]), "serie": dd,
            "pico": pico_data, "vale": vale, "recuperacao": rec.index[0] if len(rec) else None}


def _alinhar(r: pd.Series, rf) -> tuple[pd.Series, pd.Series]:
    if rf is None:
        return r.dropna(), pd.Series(0.0, index=r.dropna().index)
    if _ok(rf):
        x = r.dropna()
        return x, pd.Series(float(rf), index=x.index)
    j = pd.concat([r, rf], axis=1, join="inner").dropna()
    return j.iloc[:, 0], j.iloc[:, 1]


def sharpe(r: pd.Series, rf=None, minimo: int = 60) -> float | None:
    """Sharpe anualizado: média do excesso diário sobre a taxa livre de risco ÷ desvio do excesso. `rf`: série de retornos
    diários (ex.: CDI) ou número diário. None se houver menos de `minimo` dias ou variância zero."""
    x, f = _alinhar(r, rf)
    if len(x) < minimo:
        return None
    e = x - f
    sd = e.std(ddof=1)
    return float(e.mean() * DIAS_ANO / (sd * math.sqrt(DIAS_ANO))) if sd > 1e-12 else None


def sortino(r: pd.Series, rf=None, minimo: int = 60) -> float | None:
    """Sortino: igual ao Sharpe, mas só os desvios abaixo da taxa livre de risco contam como risco."""
    x, f = _alinhar(r, rf)
    if len(x) < minimo:
        return None
    e = x - f
    dd = math.sqrt(float((np.minimum(e, 0.0) ** 2).mean()))
    return float(e.mean() * DIAS_ANO / (dd * math.sqrt(DIAS_ANO))) if dd > 1e-12 else None


def beta(r: pd.Series, bench: pd.Series, minimo: int = 60) -> float | None:
    j = pd.concat([r, bench], axis=1, join="inner").dropna()
    if len(j) < minimo:
        return None
    v = j.iloc[:, 1].var(ddof=1)
    return float(j.iloc[:, 0].cov(j.iloc[:, 1]) / v) if v > 1e-14 else None


def var_historico(r: pd.Series, nivel: float = 0.95, dias: int = 1, minimo: int = 250) -> float | None:
    """VaR histórico: perda (positiva) que não foi excedida em `nivel` dos dias do passado, escalada por √dias.
    Não é a perda máxima possível: em 1−nivel dos dias a perda foi maior."""
    x = r.dropna() if r is not None else r
    if x is None or len(x) < minimo:
        return None
    return float(max(0.0, -np.quantile(x, 1 - nivel)) * math.sqrt(dias))


def var_parametrico(r: pd.Series, nivel: float = 0.95, dias: int = 1, minimo: int = 250) -> float | None:
    """VaR paramétrico (normal): z·σ − μ, escalado por √dias. Subestima caudas gordas; serve de comparação."""
    x = r.dropna() if r is not None else r
    if x is None or len(x) < minimo:
        return None
    z = NormalDist().inv_cdf(nivel)
    return float(max(0.0, z * x.std(ddof=1) - x.mean()) * math.sqrt(dias))


def cvar_historico(r: pd.Series, nivel: float = 0.95, dias: int = 1, minimo: int = 250) -> float | None:
    """CVaR (perda esperada na cauda): média das perdas nos dias piores que o VaR. Precisa de cauda com ≥ 10 observações."""
    x = r.dropna() if r is not None else r
    if x is None or len(x) < minimo:
        return None
    lim = np.quantile(x, 1 - nivel)
    cauda = x[x <= lim]
    if len(cauda) < 10:
        return None
    return float(max(0.0, -cauda.mean()) * math.sqrt(dias))


def retornos_da_carteira(rets: pd.DataFrame, pesos: dict[str, float], minimo_ativos_pct: float = 0.0) -> tuple[pd.Series, dict]:
    """Retorno diário da carteira com pesos CONSTANTES (rebalanceada todo dia) sobre os ativos que têm histórico comum.
    Os pesos são renormalizados entre os ativos usados; `cobertura` diz quanto do patrimônio eles representam."""
    cols = [c for c in rets.columns if c in pesos and pesos[c] > 0]
    if not cols:
        return pd.Series(dtype=float), {"cobertura": 0.0, "usados": []}
    tot = sum(pesos.values())
    w = pd.Series({c: pesos[c] for c in cols})
    cob = float(w.sum() / tot) if tot > 0 else 0.0
    w = w / w.sum()
    r = (rets[cols].dropna() * w).sum(axis=1)
    return r, {"cobertura": cob, "usados": cols, "inicio": r.index[0] if len(r) else None, "dias": int(len(r))}


def matriz_retornos(series: dict[str, pd.Series], minimo: int = 60) -> pd.DataFrame:
    """Retornos diários de vários ativos alinhados (interseção de datas). Ativos com poucos dados ficam de fora."""
    cols = {}
    for k, s in series.items():
        if s is None or len(s) < minimo + 1:
            continue
        x = s.astype(float).copy()
        x.index = pd.DatetimeIndex(x.index).normalize()
        x = x[~x.index.duplicated(keep="last")].sort_index()
        cols[k] = x.pct_change()
    if not cols:
        return pd.DataFrame()
    df = pd.concat(cols, axis=1, join="inner").dropna()
    return df if len(df) >= minimo else pd.DataFrame()


def correlacao(rets: pd.DataFrame) -> pd.DataFrame:
    return rets.corr() if rets is not None and rets.shape[1] >= 2 else pd.DataFrame()


def contribuicao_risco(pesos: pd.Series, cov: pd.DataFrame) -> pd.Series:
    """Parcela (soma 1) de cada ativo na variância da carteira: w_i·(Σw)_i / wᵀΣw."""
    w = pesos.reindex(cov.index).fillna(0.0).values
    marg = cov.values @ w
    tot = float(w @ marg)
    return pd.Series(w * marg / tot if tot > 0 else np.zeros_like(w), index=cov.index)


def pares_correlacionados(corr: pd.DataFrame, limite: float = 0.8) -> list[tuple[str, str, float]]:
    out = []
    cols = list(corr.columns)
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            c = corr.loc[a, b]
            if _ok(c) and c >= limite:
                out.append((a, b, float(c)))
    return sorted(out, key=lambda x: -x[2])


def n_efetivo_de_apostas(pesos: pd.Series, cov: pd.DataFrame) -> float | None:
    """Número efetivo de apostas independentes: razão de participação dos autovalores da covariância das posições ponderadas
    (matriz D·Σ·D, D = pesos na diagonal): (Σλ)² / Σλ². N ativos independentes, de mesmo peso e mesma volatilidade → N;
    ativos perfeitamente correlacionados → 1. Não depende da base escolhida e também cai quando o peso é concentrado."""
    w = pesos.reindex(cov.index).fillna(0.0).values
    if len(w) < 2:
        return None
    m = (w[:, None] * cov.values) * w[None, :]
    lam = np.clip(np.linalg.eigvalsh(m), 0.0, None)
    s2 = float((lam ** 2).sum())
    return float(lam.sum() ** 2 / s2) if s2 > 0 else None


def correlacao_media(corr: pd.DataFrame, pesos: pd.Series) -> float | None:
    """Correlação média entre pares, ponderada por w_i·w_j."""
    cols = [c for c in corr.columns if c in pesos.index]
    if len(cols) < 2:
        return None
    num = den = 0.0
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            wij = pesos[a] * pesos[b]
            if _ok(corr.loc[a, b]):
                num += wij * corr.loc[a, b]
                den += wij
    return float(num / den) if den > 0 else None


# =============================================================================== alocação
def distribuicao(posicoes: list[dict], campo: str) -> list[dict]:
    """Valor e % por categoria de `campo` (classe, setor, pais, moeda, emissor, gestor), só posições com valor."""
    tot = sum(p["valor"] for p in posicoes if _ok(p.get("valor")) and p["valor"] > 0)
    g: dict[str, float] = {}
    for p in posicoes:
        if _ok(p.get("valor")) and p["valor"] > 0:
            k = p.get(campo) or "Não informado"
            g[k] = g.get(k, 0.0) + p["valor"]
    return [{"nome": k, "valor": v, "pct": v / tot if tot > 0 else 0.0} for k, v in sorted(g.items(), key=lambda x: -x[1])]


def concentracao(valores: list[float]) -> dict:
    """HHI (Σ pesos²), número efetivo de posições (1/HHI) e peso das maiores."""
    v = sorted((float(x) for x in valores if _ok(x) and x > 0), reverse=True)
    tot = sum(v)
    if tot <= 0:
        return {"ok": False}
    p = [x / tot for x in v]
    hhi = sum(x * x for x in p)
    return {"ok": True, "n": len(v), "hhi": hhi, "n_efetivo": 1 / hhi, "top1": p[0], "top3": sum(p[:3]), "top5": sum(p[:5])}


LIMITES_PADRAO = {"ativo": 0.20, "setor": 0.40, "classe": 0.80, "emissor": 0.25, "exterior": 0.60, "moeda_estrangeira": 0.60,
                  "fator": 0.60}


def avaliar_concentracao(posicoes: list[dict], limites: dict | None = None) -> list[dict]:
    """Pontos de atenção: ativo, setor, classe, país, moeda, emissor e fator de risco acima dos limites (editáveis).
    Cada alerta traz o dado que o justifica. Limites são referências, não regras do mercado."""
    lim = {**LIMITES_PADRAO, **(limites or {})}
    tot = sum(p["valor"] for p in posicoes if _ok(p.get("valor")) and p["valor"] > 0)
    if tot <= 0:
        return []
    a: list[dict] = []

    def add(tipo, nome, pct, ref, texto):
        a.append({"tipo": tipo, "nome": nome, "pct": pct, "limite": ref, "texto": texto})
    for p in posicoes:
        if _ok(p.get("valor")) and p["valor"] / tot > lim["ativo"] and p.get("classe") != "caixa":
            add("ativo", p["id"], p["valor"] / tot, lim["ativo"],
                f"{p['id']} é {p['valor'] / tot * 100:.0f}% do patrimônio (referência: até {lim['ativo'] * 100:.0f}% por ativo).")
    rotulos = {"setor": "setor", "classe": "classe", "emissor": "emissor", "fator": "fator de risco"}
    for campo, ref in (("setor", lim["setor"]), ("classe", lim["classe"]), ("emissor", lim["emissor"]), ("fator", lim["fator"])):
        for d in distribuicao(posicoes, campo):
            if d["nome"] in ("Não informado", "Tesouro Nacional", "Renda fixa") and campo in ("setor", "emissor"):
                continue
            if campo == "classe" and len(distribuicao(posicoes, "classe")) == 1:
                add("classe", CLASSES.get(d["nome"], d["nome"]), d["pct"], ref,
                    f"100% da carteira está em {CLASSES.get(d['nome'], d['nome'])}: uma só classe de ativo.")
                break
            if d["pct"] > ref:
                nome = CLASSES.get(d["nome"], d["nome"]) if campo == "classe" else d["nome"]
                add(campo, nome, d["pct"], ref, f"{nome} = {d['pct'] * 100:.0f}% do patrimônio "
                                               f"(referência: até {ref * 100:.0f}% por {rotulos[campo]}).")
    ext = [d for d in distribuicao(posicoes, "pais") if d["nome"].startswith("Exterior")]
    if ext and ext[0]["pct"] > lim["exterior"]:
        add("pais", ext[0]["nome"], ext[0]["pct"], lim["exterior"], f"{ext[0]['pct'] * 100:.0f}% do patrimônio está no exterior.")
    me = sum(d["pct"] for d in distribuicao(posicoes, "moeda") if d["nome"] != "BRL")
    if me > lim["moeda_estrangeira"]:
        add("moeda", "Moeda estrangeira", me, lim["moeda_estrangeira"],
            f"{me * 100:.0f}% do patrimônio depende do dólar: a carteira oscila com o câmbio.")
    return a


def fator_de_risco(p: dict) -> str:
    """Fonte de retorno dominante de uma posição. Duas posições no mesmo fator tendem a cair juntas."""
    c = p.get("classe")
    if c == "renda_fixa":
        return "Juros pós-fixados (CDI)" if p.get("indexador") in ("cdi_pct", "cdi_mais", "selic", "selic_mais") else "Juros longos (prefixado e IPCA)"
    if c == "cripto":
        return "Criptomoedas"
    if c == "fii":
        return "Imóveis e juros (FIIs)"
    if c == "caixa":
        return "Juros pós-fixados (CDI)"
    exterior = p.get("moeda", "BRL") != "BRL" or p.get("pais", "").startswith("Exterior")
    if c in ("acao", "etf", "bdr", "fundo"):
        if exterior or c == "bdr":
            return "Bolsa do exterior e dólar"
        return "Bolsa brasileira"
    return "Outros fatores"


def desvios_do_alvo(valores: dict[str, float], alvos: dict[str, float], tolerancia: dict[str, float] | float = 5.0) -> list[dict]:
    """Compara % atual e % alvo por classe. `alvos` e `tolerancia` em pontos percentuais; alvos devem somar 100.
    `ajuste` = R$ para comprar (+) ou vender (−) e chegar ao alvo sem mexer no total."""
    total = sum(v for v in valores.values() if _ok(v) and v > 0)
    soma_alvo = sum(alvos.values())
    if total <= 0 or abs(soma_alvo - 100.0) > 0.01:
        return []
    out = []
    for c in dict.fromkeys(list(alvos) + list(valores)):
        atual = valores.get(c, 0.0) / total * 100
        alvo = alvos.get(c, 0.0)
        tol = tolerancia.get(c, 5.0) if isinstance(tolerancia, dict) else float(tolerancia)
        desvio = atual - alvo
        st = "dentro" if abs(desvio) <= tol else ("acima" if desvio > 0 else "abaixo")
        out.append({"classe": c, "atual": atual, "alvo": alvo, "desvio": desvio, "tolerancia": tol, "status": st,
                    "valor": valores.get(c, 0.0), "ajuste": alvo / 100 * total - valores.get(c, 0.0)})
    return sorted(out, key=lambda x: -abs(x["desvio"]))


# =============================================================================== qualidade dos dados
def avaliar_qualidade(posicoes: list[dict], hoje: date | None = None, dias_defasagem: int = 7) -> list[str]:
    """Problemas que afetam a confiança dos números: sem cotação, cotação antiga, moeda sem câmbio, ativo duplicado."""
    hoje = hoje or date.today()
    av = []
    sem = [p["id"] for p in posicoes if not _ok(p.get("valor")) or p["valor"] <= 0]
    if sem:
        av.append(f"Sem cotação atual (ficam fora do valor da carteira): {', '.join(sem)}.")
    vel = []
    for p in posicoes:
        d = _data(p.get("data_preco"))
        if d is not None and (hoje - d).days > dias_defasagem and p.get("classe") != "renda_fixa":
            vel.append(f"{p['id']} ({d:%d/%m/%Y})")
    if vel:
        av.append("Cotação desatualizada (mais de 7 dias): " + ", ".join(vel) + ".")
    sem_fx = [p["id"] for p in posicoes if p.get("moeda", "BRL") != "BRL" and not _ok(p.get("cambio"))]
    if sem_fx:
        av.append("Ativos em moeda estrangeira sem câmbio disponível: " + ", ".join(sem_fx) + ".")
    ids = [p["id"] for p in posicoes]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        av.append("Ativo repetido na lista (possível dupla contagem): " + ", ".join(dup) + ".")
    return av


# =============================================================================== proventos recebidos
def quantidade_em(movs: list[dict], ticker: str, data: date) -> float:
    """Quantidade do ativo na data (inclui lançamentos DA data: quem comprou no dia da data-com ainda não tem direito, então use
    a véspera quando for o caso — aqui a regra é: compras e vendas com data < `data`)."""
    q = 0.0
    for m in movs:
        if m["ticker"] == ticker and m["data"] < data:
            q += m["qtd"] if m["tipo"] == "compra" else -m["qtd"]
    return max(q, 0.0)


def proventos_recebidos(movs: list[dict], por_papel: dict[str, pd.DataFrame], moedas: dict[str, str], classes: dict[str, str],
                        cambio: pd.Series | None, hoje: date | None = None) -> list[dict]:
    """Proventos (R$ brutos) por ativo = valor por papel na data-com × quantidade que a pessoa tinha na véspera. `por_papel[ticker]`:
    DataFrame com colunas data (data-com/ex) e valor (na moeda do ativo). A fonte (Yahoo) traz a data-com, não a data do crédito:
    o mês pode adiantar em relação ao recebimento."""
    hoje = hoje or date.today()
    fx = None
    if cambio is not None and len(cambio):
        fx = pd.Series(cambio.values, index=pd.DatetimeIndex(cambio.index).normalize()).sort_index()
        fx = fx[~fx.index.duplicated(keep="last")]
    out = []
    for tk, df in por_papel.items():
        if df is None or df.empty:
            continue
        primeiro = min((m["data"] for m in movs if m["ticker"] == tk), default=None)
        if primeiro is None:
            continue
        for r in df.itertuples():
            d = _data(r.data)
            if d is None or d <= primeiro or d > hoje or not _ok(r.valor) or r.valor <= 0:
                continue
            q = quantidade_em(movs, tk, d)
            if q <= 0:
                continue
            v = q * float(r.valor)
            if moedas.get(tk, "BRL") != "BRL":
                if fx is None or fx.empty:
                    continue
                f = fx.loc[:pd.Timestamp(d)]
                v *= float(f.iloc[-1]) if len(f) else float(fx.iloc[0])
            out.append({"data": d, "fonte": tk, "valor": v, "tipo": "rendimento_fii" if classes.get(tk) == "fii" else
                        ("distribuicao_fundo" if classes.get(tk) in ("etf", "fundo") else "dividendo"), "efetivo": True})
    return sorted(out, key=lambda e: e["data"])


def acumulado_proventos(eventos: list[dict]) -> pd.Series:
    """Proventos acumulados em R$ por data (para somar ao valor da carteira no retorno TOTAL)."""
    if not eventos:
        return pd.Series(dtype=float)
    s = pd.Series({pd.Timestamp(e["data"]): 0.0 for e in eventos})
    s = pd.Series([e["valor"] for e in eventos], index=pd.DatetimeIndex([pd.Timestamp(e["data"]) for e in eventos])).groupby(level=0).sum()
    return s.sort_index().cumsum()


def parse_proventos_chart(res: dict | None) -> pd.DataFrame:
    """Dividendos de uma resposta da API de gráfico do Yahoo (events.dividends) → DataFrame(data, valor)."""
    ev = ((res or {}).get("events") or {}).get("dividends") or {}
    linhas = []
    for v in ev.values():
        try:
            valor, ts = float(v.get("amount")), int(v.get("date"))
        except (TypeError, ValueError):
            continue
        if math.isfinite(valor) and valor > 0:
            linhas.append({"data": pd.to_datetime(ts, unit="s").date(), "valor": valor})
    return pd.DataFrame(linhas, columns=["data", "valor"]).sort_values("data").reset_index(drop=True)
