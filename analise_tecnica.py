"""
Passo 14 — Análise técnica avançada (motor puro: sem Streamlit e sem rede).

CAMADAS (separadas de propósito):
  dados      → `limpar_ohlcv` (valida candles, NUNCA inventa nem "conserta" preço), `reamostrar` (semanal/mensal/anual),
               `detectar_lacunas`, `meta_fonte` (fonte, fuso, moeda, frequência, atraso), `avaliar_liquidez`;
  cálculo    → indicadores (`INDICADORES`, `calcular`), tendência (`classificar_tendencia`), suportes/resistências,
               padrões gráficos, sinais, análise multitemporal;
  simulação  → `backtest` (execução no candle SEGUINTE ao sinal, sem informação futura), custos, métricas;
  alertas    → regras técnicas, avaliação e detecção por candle (o app filtra repetidos com `intel.filtrar_repetidos`);
  leitura    → resumo técnico, visão da carteira, respostas do assistente (só com dados presentes no contexto).

Reaproveita: `tecnica.pivots` (topos/fundos do Passo existente), `intel.tendencia` (regressão do log-preço) e as regras de
alerta/histórico do Passo 13. Cada classe de ativo só recebe os indicadores adequados a ela (`perfil_classe`).
Tudo aqui são regras educacionais explicáveis; nada é recomendação de compra ou venda.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

import intel as I

AVISO_LEGAL = ("Ferramenta educacional. Indicadores, padrões e sinais técnicos descrevem o passado do preço e podem falhar; "
               "não são recomendação de compra ou venda e não garantem resultado futuro.")
AVISO_BACKTEST = ("Desempenho passado não garante desempenho futuro. Um teste histórico é uma simulação: custos, impostos, liquidez "
                  "e comportamento reais podem diferir, e ajustar parâmetros ao próprio histórico gera resultados otimistas (sobreajuste).")
CLASSES = ("acao", "etf", "fii", "cripto", "fundo", "renda_fixa")
ROTULO_CLASSE = {"acao": "Ação", "etf": "ETF", "fii": "FII", "cripto": "Criptomoeda", "fundo": "Fundo", "renda_fixa": "Renda fixa"}
COLUNAS = ["Open", "High", "Low", "Close", "Volume"]


class IndicadorIndisponivel(Exception):
    """Dado ausente ou inadequado para o indicador pedido (nunca se preenche com valor inventado)."""


def _ok(v) -> bool:
    try:
        return v is not None and not (isinstance(v, float) and math.isnan(v)) and not pd.isna(v)
    except Exception:
        return False


def fmt_num(v, casas: int = 2) -> str:
    if not _ok(v):
        return "n/d"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_preco(v, moeda: str = "BRL") -> str:
    if not _ok(v):
        return "n/d"
    v = float(v)
    casas = 2 if abs(v) >= 1 else 4 if abs(v) >= 0.01 else 8
    pre = {"BRL": "R$ ", "USD": "US$ ", "USDT": "", "": ""}.get(moeda, f"{moeda} ")
    return pre + fmt_num(v, casas)


def _dia(x) -> str:
    try:
        t = pd.Timestamp(x)
        return t.strftime("%Y-%m-%d %H:%M") if (t.hour or t.minute) else t.strftime("%Y-%m-%d")
    except Exception:
        return str(x)


# =============================================================================== dados
def limpar_ohlcv(df) -> tuple[pd.DataFrame, dict]:
    """Valida o histórico. Remove (e conta) linhas sem fechamento, duplicadas ou com candle impossível (máxima < mínima, abertura/
    fechamento fora do intervalo). NÃO preenche, interpola nem corrige valores. Colunas ausentes ficam ausentes (sem candle falso).
    Devolve (df limpo, relatório)."""
    rel = {"n_original": 0, "n": 0, "removidas_sem_preco": 0, "duplicadas": 0, "removidas_inconsistentes": 0, "tem_ohlc": False,
           "tem_volume": False, "volume_zero_pct": None, "primeira": None, "ultima": None, "problemas": []}
    if df is None or len(df) == 0:
        rel["problemas"].append("Sem dados de preço.")
        return pd.DataFrame(columns=COLUNAS), rel
    d = df.copy()
    d.columns = [str(c).strip().capitalize() if str(c).strip().lower() in ("open", "high", "low", "close", "volume") else c for c in d.columns]
    if "Close" not in d.columns:
        rel["problemas"].append("Coluna de fechamento ausente.")
        return pd.DataFrame(columns=COLUNAS), rel
    rel["n_original"] = len(d)
    if not isinstance(d.index, pd.DatetimeIndex):
        d.index = pd.to_datetime(d.index, errors="coerce")
        d = d[~d.index.isna()]
    if d.index.tz is not None:
        d.index = d.index.tz_convert("America/Sao_Paulo").tz_localize(None)
    cols = [c for c in COLUNAS if c in d.columns]
    d = d[cols].apply(pd.to_numeric, errors="coerce")
    n0 = len(d)
    d = d[d["Close"].notna() & (d["Close"] > 0)]
    rel["removidas_sem_preco"] = n0 - len(d)
    n1 = len(d)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    rel["duplicadas"] = n1 - len(d)
    if {"Open", "High", "Low"}.issubset(d.columns):
        tem = d[["Open", "High", "Low"]].notna().all(axis=1)
        ruim = tem & ((d["High"] < d["Low"]) | (d["High"] < d[["Open", "Close"]].max(axis=1) - 1e-9)
                      | (d["Low"] > d[["Open", "Close"]].min(axis=1) + 1e-9) | (d[["Open", "High", "Low"]] <= 0).any(axis=1))
        rel["removidas_inconsistentes"] = int(ruim.sum())
        d = d[~ruim]
        rel["tem_ohlc"] = bool(len(d)) and bool(d[["Open", "High", "Low"]].notna().all(axis=1).mean() >= 0.95)
        if not rel["tem_ohlc"]:
            d = d.drop(columns=["Open", "High", "Low"])
    if "Volume" in d.columns:
        d.loc[d["Volume"] < 0, "Volume"] = np.nan
        nn = d["Volume"].notna().mean() if len(d) else 0
        rel["tem_volume"] = bool(nn >= 0.8 and (d["Volume"].fillna(0) > 0).mean() >= 0.5)
        rel["volume_zero_pct"] = float((d["Volume"].fillna(0) <= 0).mean() * 100) if len(d) else None
        if not rel["tem_volume"]:
            d = d.drop(columns=["Volume"])
            rel["problemas"].append("Volume ausente ou insuficiente: indicadores de volume ficam indisponíveis.")
    rel["n"] = len(d)
    if len(d):
        rel["primeira"], rel["ultima"] = _dia(d.index[0]), _dia(d.index[-1])
    if rel["removidas_inconsistentes"]:
        rel["problemas"].append(f"{rel['removidas_inconsistentes']} candle(s) inconsistente(s) removido(s) (sem correção).")
    if rel["removidas_sem_preco"]:
        rel["problemas"].append(f"{rel['removidas_sem_preco']} linha(s) sem preço removida(s).")
    if rel["duplicadas"]:
        rel["problemas"].append(f"{rel['duplicadas']} data(s) duplicada(s) removida(s).")
    return d, rel


def inferir_frequencia(idx) -> str:
    """'intra' (menos de 1 dia entre candles), 'D', 'W' ou 'M' pela mediana do espaçamento."""
    if len(idx) < 3:
        return "D"
    dif = pd.Series(pd.DatetimeIndex(idx)).diff().dropna().median()
    if dif < timedelta(hours=20):
        return "intra"
    if dif <= timedelta(days=4):
        return "D"
    if dif <= timedelta(days=12):
        return "W"
    return "M"


def _alias(regra: str) -> str:
    try:
        novo = tuple(int(x) for x in pd.__version__.split(".")[:2]) >= (2, 2)
    except Exception:
        novo = True
    return {"W": "W-FRI", "M": "ME" if novo else "M", "Y": "YE" if novo else "A", "D": "D"}[regra]


def reamostrar(df: pd.DataFrame, regra: str) -> pd.DataFrame:
    """Agrega para semanal ('W'), mensal ('M'), anual ('Y') ou diário ('D', a partir de intraday): abertura do 1º candle, máxima,
    mínima, fechamento do último, volume somado. Períodos sem negócio são descartados (sem candle inventado). `attrs['ultimo_parcial']`
    avisa quando o último período ainda não terminou."""
    if df is None or df.empty:
        return pd.DataFrame(columns=COLUNAS)
    ag = {}
    for c, f in (("Open", "first"), ("High", "max"), ("Low", "min"), ("Close", "last"), ("Volume", "sum")):
        if c in df.columns:
            ag[c] = f
    if not ag:
        return pd.DataFrame(columns=COLUNAS)
    g = df.resample(_alias(regra), label="right", closed="right") if regra in ("W", "M", "Y") else df.resample("D")
    out = g.agg(ag)
    out = out[out["Close"].notna()]
    if "Volume" in out.columns and "Volume" in df.columns:
        n_ok = df["Volume"].resample(_alias(regra)).count() if regra in ("W", "M", "Y") else df["Volume"].resample("D").count()
        out.loc[n_ok.reindex(out.index).fillna(0) == 0, "Volume"] = np.nan
    # rótulo = data do último pregão real do período (não o fim do calendário)
    ult = df.index.to_series().resample(_alias(regra), label="right", closed="right").max() if regra in ("W", "M", "Y") else None
    if ult is not None:
        out.index = pd.DatetimeIndex(ult.reindex(out.index).values)
    out = out[~out.index.duplicated(keep="last")]
    try:
        fim = {"W": pd.Timestamp(df.index[-1]) + pd.offsets.Week(weekday=4), "M": pd.Timestamp(df.index[-1]) + pd.offsets.MonthEnd(0),
               "Y": pd.Timestamp(df.index[-1]) + pd.offsets.YearEnd(0)}.get(regra)
        out.attrs["ultimo_parcial"] = bool(fim is not None and pd.Timestamp(df.index[-1]).normalize() < fim.normalize()
                                           and fim.normalize() >= pd.Timestamp.now().normalize())
    except Exception:
        out.attrs["ultimo_parcial"] = False
    return out


def detectar_lacunas(idx, freq: str | None = None, cripto: bool = False) -> list[dict]:
    """Buracos no histórico acima do esperado (feriados e fins de semana não contam). Só informa; nunca preenche."""
    idx = pd.DatetimeIndex(idx)
    if len(idx) < 3:
        return []
    freq = freq or inferir_frequencia(idx)
    lim = {"D": timedelta(days=2 if cripto else 5), "W": timedelta(days=15), "M": timedelta(days=45)}.get(freq)
    out = []
    if freq == "intra":
        base = pd.Series(idx).diff().dropna().median()
        s = pd.Series(idx)
        for i in range(1, len(s)):
            if s[i].date() == s[i - 1].date() and (s[i] - s[i - 1]) > base * 4:
                out.append({"de": _dia(s[i - 1]), "ate": _dia(s[i]), "dias": round((s[i] - s[i - 1]).total_seconds() / 86400, 2)})
        return out[:20]
    s = pd.Series(idx)
    dif = s.diff()
    for i in np.flatnonzero((dif > lim).to_numpy()):
        out.append({"de": _dia(s[i - 1]), "ate": _dia(s[i]), "dias": int(dif[i].days)})
    return out[:20]


def meta_fonte(fonte: str, frequencia: str = "diario", moeda: str = "BRL", atrasado: bool | None = True, ajustado: bool | None = None,
               fuso: str = "America/Sao_Paulo", atualizado_em: str | None = None, observacao: str = "") -> dict:
    """Registro da procedência dos dados (exigido pelo Passo 14). `atrasado=None` = não informado."""
    return {"fonte": fonte, "frequencia": frequencia, "moeda": moeda, "atrasado": atrasado, "ajustado": ajustado, "fuso": fuso,
            "atualizado_em": atualizado_em or datetime.now().isoformat(timespec="minutes"), "observacao": observacao}


def descrever_fonte(meta: dict, rel: dict | None = None, lacunas: list | None = None) -> str:
    p = [f"Fonte: {meta.get('fonte', 'n/d')}", f"frequência: {meta.get('frequencia', 'n/d')}", f"moeda: {meta.get('moeda', 'n/d')}",
         f"fuso: {meta.get('fuso', 'n/d')}", f"atualizado em {str(meta.get('atualizado_em', 'n/d'))[:16].replace('T', ' ')}"]
    a = meta.get("atrasado")
    p.append("dados atrasados (não é tempo real)" if a else "dados quase em tempo real" if a is False else "atraso não informado")
    aj = meta.get("ajustado")
    if aj is True:
        p.append("preços ajustados por proventos/eventos")
    elif aj is False:
        p.append("preços sem ajuste por proventos")
    txt = " · ".join(p) + "."
    if rel and rel.get("n"):
        txt += f" {rel['n']} candles de {rel.get('primeira')} a {rel.get('ultima')}."
    if lacunas:
        txt += f" {len(lacunas)} lacuna(s) no histórico (nada foi preenchido)."
    if meta.get("observacao"):
        txt += " " + meta["observacao"]
    return txt


def avaliar_liquidez(df: pd.DataFrame, classe: str = "acao", janela: int = 60) -> dict:
    """Liquidez pelo volume financeiro mediano (preço × volume) e pela fração de dias sem negócio na janela."""
    out = {"nivel": "indisponivel", "mediana_financeira": None, "dias_sem_negocio_pct": None, "aviso": None}
    if df is None or "Volume" not in df.columns or len(df) < 20:
        out["aviso"] = "Sem volume confiável: a liquidez não pôde ser avaliada."
        return out
    j = df.iloc[-janela:]
    fin = (j["Close"] * j["Volume"]).dropna()
    if not len(fin):
        out["aviso"] = "Sem volume confiável: a liquidez não pôde ser avaliada."
        return out
    sem = float((j["Volume"].fillna(0) <= 0).mean() * 100)
    med = float(fin.median())
    out.update({"mediana_financeira": med, "dias_sem_negocio_pct": sem})
    if classe == "cripto":
        out["nivel"] = "adequada"
        return out
    minimo = {"fii": 500_000.0, "acao": 1_000_000.0, "etf": 500_000.0}.get(classe, 500_000.0)
    if sem > 20 or med < minimo * 0.2:
        out["nivel"] = "muito_baixa"
        out["aviso"] = (f"Liquidez muito baixa (mediana de {fmt_preco(med)} por dia, {fmt_num(sem, 0)}% dos dias sem negócio): "
                        "o preço pode se mover por poucas ordens e os indicadores perdem confiabilidade.")
    elif med < minimo or sem > 5:
        out["nivel"] = "baixa"
        out["aviso"] = (f"Liquidez baixa (mediana de {fmt_preco(med)} por dia): negociações irregulares podem distorcer sinais e "
                        "dificultar a execução ao preço do gráfico.")
    else:
        out["nivel"] = "adequada"
    return out


def separar_proventos(df: pd.DataFrame, proventos: pd.Series | None, ajustado: bool | None = None) -> dict:
    """FIIs/ações: retorno de PREÇO e retorno de PROVENTOS separados na janela do gráfico. Com preços já ajustados por proventos a
    separação não é possível (o ajuste mistura os dois) e a função avisa em vez de calcular."""
    out = {"disponivel": False, "retorno_preco_pct": None, "proventos_pct": None, "total_pct": None, "soma_proventos": None, "n": 0, "aviso": None}
    if df is None or len(df) < 2:
        out["aviso"] = "Sem histórico."
        return out
    if ajustado:
        out["aviso"] = "Os preços já estão ajustados por proventos: o retorno de preço e o de proventos aparecem misturados nesta série."
        return out
    c0, c1 = float(df["Close"].iloc[0]), float(df["Close"].iloc[-1])
    out["retorno_preco_pct"] = (c1 / c0 - 1) * 100
    if proventos is None or len(proventos) == 0:
        out["aviso"] = "Sem dados de proventos na fonte para este período."
        out["disponivel"] = True
        return out
    pv = pd.Series(proventos).dropna()
    pv.index = pd.DatetimeIndex(pv.index).tz_localize(None) if getattr(pv.index, "tz", None) else pd.DatetimeIndex(pv.index)
    pv = pv[(pv.index >= df.index[0]) & (pv.index <= df.index[-1])]
    out.update({"disponivel": True, "soma_proventos": float(pv.sum()), "n": int(len(pv)), "proventos_pct": float(pv.sum() / c0 * 100)})
    out["total_pct"] = out["retorno_preco_pct"] + out["proventos_pct"]
    return out


# =============================================================================== indicadores
def _wilder(x: np.ndarray, n: int) -> np.ndarray:
    """Suavização de Wilder: o 1º valor é a média simples dos n primeiros valores válidos; depois (anterior·(n−1)+atual)/n."""
    x = np.asarray(x, dtype=float)
    out = np.full(len(x), np.nan)
    val = np.flatnonzero(~np.isnan(x))
    if len(val) < n:
        return out
    s = val[0]
    i0 = s + n - 1
    out[i0] = x[s:s + n].mean()
    for i in range(i0 + 1, len(x)):
        out[i] = (out[i - 1] * (n - 1) + x[i]) / n if not np.isnan(x[i]) else np.nan
    return out


def _ema(x: pd.Series, n: int) -> pd.Series:
    """Média móvel exponencial semeada pela média simples dos n primeiros valores (padrão das plataformas)."""
    v = x.to_numpy(dtype=float)
    out = np.full(len(v), np.nan)
    val = np.flatnonzero(~np.isnan(v))
    if len(val) < n:
        return pd.Series(out, index=x.index)
    s = val[0]
    i0 = s + n - 1
    out[i0] = v[s:s + n].mean()
    a = 2.0 / (n + 1)
    for i in range(i0 + 1, len(v)):
        out[i] = out[i - 1] + a * (v[i] - out[i - 1]) if not np.isnan(v[i]) else np.nan
    return pd.Series(out, index=x.index)


def _tr(df: pd.DataFrame) -> pd.Series:
    pc = df["Close"].shift(1)
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - pc).abs(), (df["Low"] - pc).abs()], axis=1).max(axis=1)
    tr.iloc[0] = float(df["High"].iloc[0] - df["Low"].iloc[0])
    return tr


def _sma(df, n=20, col="Close"):
    return pd.DataFrame({"SMA": df[col].rolling(n).mean()})


def _ema_i(df, n=20, col="Close"):
    return pd.DataFrame({"EMA": _ema(df[col], n)})


def _wma(df, n=20, col="Close"):
    w = np.arange(1, n + 1, dtype=float)
    return pd.DataFrame({"WMA": df[col].rolling(n).apply(lambda a: float(np.dot(a, w) / w.sum()), raw=True)})


def _macd(df, rapida=12, lenta=26, sinal=9):
    if rapida >= lenta:
        raise ValueError("No MACD a média rápida deve ser menor que a lenta.")
    m = _ema(df["Close"], rapida) - _ema(df["Close"], lenta)
    s = _ema(m.dropna(), sinal).reindex(m.index)
    return pd.DataFrame({"MACD": m, "MACD_SINAL": s, "MACD_HIST": m - s})


def _rsi(df, n=14):
    c = df["Close"].to_numpy(dtype=float)
    d = np.diff(c, prepend=np.nan)
    g, p = np.where(d > 0, d, 0.0), np.where(d < 0, -d, 0.0)
    g[0] = p[0] = np.nan
    ag, ap = _wilder(g, n), _wilder(p, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        rs = ag / ap
        r = 100 - 100 / (1 + rs)
    r = np.where(np.isnan(ag), np.nan, np.where(ap == 0, np.where(ag == 0, 50.0, 100.0), r))
    return pd.DataFrame({"RSI": r}, index=df.index)


def _adx(df, n=14):
    h, l = df["High"].to_numpy(float), df["Low"].to_numpy(float)
    up, dn = np.diff(h, prepend=np.nan), -np.diff(l, prepend=np.nan)
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    pdm[0] = mdm[0] = np.nan
    tr = np.array(_tr(df).to_numpy(float))
    tr[0] = np.nan
    atr, sp, sm = _wilder(tr, n), _wilder(pdm, n), _wilder(mdm, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi, mdi = 100 * sp / atr, 100 * sm / atr
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    dx = np.where(np.isnan(dx) & ~np.isnan(pdi), 0.0, dx)
    return pd.DataFrame({"ADX": _wilder(dx, n), "DI_MAIS": pdi, "DI_MENOS": mdi}, index=df.index)


def _ichimoku(df, tenkan=9, kijun=26, senkou_b=52):
    def meio(n):
        return (df["High"].rolling(n).max() + df["Low"].rolling(n).min()) / 2
    t, k = meio(tenkan), meio(kijun)
    return pd.DataFrame({"TENKAN": t, "KIJUN": k, "SENKOU_A": ((t + k) / 2).shift(kijun), "SENKOU_B": meio(senkou_b).shift(kijun),
                         "CHIKOU": df["Close"].shift(-kijun)})


def _estocastico(df, n=14, suav_k=3, d=3):
    ll, hh = df["Low"].rolling(n).min(), df["High"].rolling(n).max()
    with np.errstate(divide="ignore", invalid="ignore"):
        rapido = 100 * (df["Close"] - ll) / (hh - ll)
    k = rapido.rolling(suav_k).mean() if suav_k > 1 else rapido
    return pd.DataFrame({"STOCH_K": k, "STOCH_D": k.rolling(d).mean()})


def _cci(df, n=20):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    sma = tp.rolling(n).mean()
    dm = tp.rolling(n).apply(lambda a: float(np.abs(a - a.mean()).mean()), raw=True)
    with np.errstate(divide="ignore", invalid="ignore"):
        return pd.DataFrame({"CCI": (tp - sma) / (0.015 * dm)})


def _roc(df, n=12):
    return pd.DataFrame({"ROC": (df["Close"] / df["Close"].shift(n) - 1) * 100})


def _williams(df, n=14):
    hh, ll = df["High"].rolling(n).max(), df["Low"].rolling(n).min()
    with np.errstate(divide="ignore", invalid="ignore"):
        return pd.DataFrame({"WILLIAMS_R": -100 * (hh - df["Close"]) / (hh - ll)})


def _bollinger(df, n=20, k=2.0):
    m = df["Close"].rolling(n).mean()
    s = df["Close"].rolling(n).std(ddof=0)
    sup, inf = m + k * s, m - k * s
    with np.errstate(divide="ignore", invalid="ignore"):
        return pd.DataFrame({"BOLL_SUP": sup, "BOLL_MEDIA": m, "BOLL_INF": inf, "BOLL_LARG": (sup - inf) / m * 100,
                             "BOLL_B": (df["Close"] - inf) / (sup - inf)})


def _atr(df, n=14):
    a = pd.Series(_wilder(_tr(df).to_numpy(float), n), index=df.index)
    return pd.DataFrame({"ATR": a, "ATR_PCT": a / df["Close"] * 100})


def _desvio(df, n=20):
    s = df["Close"].rolling(n).std(ddof=1)
    return pd.DataFrame({"DESVIO": s, "DESVIO_PCT": s / df["Close"].rolling(n).mean() * 100})


def _keltner(df, n=20, n_atr=10, mult=2.0):
    m = _ema(df["Close"], n)
    a = pd.Series(_wilder(_tr(df).to_numpy(float), n_atr), index=df.index)
    return pd.DataFrame({"KELT_SUP": m + mult * a, "KELT_MEDIA": m, "KELT_INF": m - mult * a})


def _obv(df):
    sinal = np.sign(df["Close"].diff().fillna(0.0))
    return pd.DataFrame({"OBV": (sinal * df["Volume"].fillna(0.0)).cumsum()})


def _vwap(df, n=20):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    pv = tp * df["Volume"]
    if inferir_frequencia(df.index) == "intra":
        dia = df.index.normalize()
        return pd.DataFrame({"VWAP": pv.groupby(dia).cumsum() / df["Volume"].groupby(dia).cumsum()})
    return pd.DataFrame({"VWAP": pv.rolling(n).sum() / df["Volume"].rolling(n).sum()})


def _vol_medio(df, n=20):
    m = df["Volume"].rolling(n).mean()
    return pd.DataFrame({"VOL_MEDIO": m, "VOL_RAZAO": df["Volume"] / m})


def _mfi(df, n=14):
    tp = (df["High"] + df["Low"] + df["Close"]) / 3
    fluxo = tp * df["Volume"]
    pos = fluxo.where(tp > tp.shift(1), 0.0).rolling(n).sum()
    neg = fluxo.where(tp < tp.shift(1), 0.0).rolling(n).sum()
    with np.errstate(divide="ignore", invalid="ignore"):
        mfi = 100 - 100 / (1 + pos / neg)
    mfi = mfi.where(neg != 0, 100.0).where(pos.notna() & neg.notna())
    return pd.DataFrame({"MFI": mfi})


def _acum_dist(df):
    amp = (df["High"] - df["Low"]).replace(0, np.nan)
    clv = (((df["Close"] - df["Low"]) - (df["High"] - df["Close"])) / amp).fillna(0.0)
    return pd.DataFrame({"AD": (clv * df["Volume"].fillna(0.0)).cumsum()})


def _donchian(df, n=20):
    return pd.DataFrame({"DON_ALTO": df["High"].shift(1).rolling(n).max(), "DON_BAIXO": df["Low"].shift(1).rolling(n).min()})


_P = lambda padrao, mn, mx, rot: {"padrao": padrao, "min": mn, "max": mx, "rotulo": rot}  # noqa: E731
_FONTE = {"padrao": "Close", "opcoes": ["Close", "Open", "High", "Low"], "rotulo": "Preço usado"}

INDICADORES: dict[str, dict] = {
    "SMA": {"nome": "Média móvel simples (SMA)", "grupo": "Tendência", "painel": "preco", "fn": _sma, "req": "c", "colunas": ["SMA"],
            "params": {"n": _P(20, 2, 400, "Períodos")},
            "explicacao": "Média aritmética dos últimos n fechamentos. Suaviza o ruído e mostra a direção: preço acima da média costuma indicar viés de alta, abaixo, de baixa. Reage com atraso e engana em mercado lateral."},
    "EMA": {"nome": "Média móvel exponencial (EMA)", "grupo": "Tendência", "painel": "preco", "fn": _ema_i, "req": "c", "colunas": ["EMA"],
            "params": {"n": _P(21, 2, 400, "Períodos")},
            "explicacao": "Média que dá mais peso aos preços recentes, reagindo mais rápido que a SMA. Também atrasa e gera falsos sinais em mercado sem direção."},
    "WMA": {"nome": "Média móvel ponderada (WMA)", "grupo": "Tendência", "painel": "preco", "fn": _wma, "req": "c", "colunas": ["WMA"],
            "params": {"n": _P(20, 2, 400, "Períodos")},
            "explicacao": "Média com pesos lineares crescentes (o preço mais recente pesa mais). Meio-termo entre a SMA e a EMA."},
    "MACD": {"nome": "MACD", "grupo": "Tendência", "painel": "sub", "fn": _macd, "req": "c", "colunas": ["MACD", "MACD_SINAL", "MACD_HIST"],
             "params": {"rapida": _P(12, 2, 100, "Média rápida"), "lenta": _P(26, 3, 200, "Média lenta"), "sinal": _P(9, 2, 100, "Sinal")},
             "explicacao": "Diferença entre duas EMAs (rápida − lenta) e sua média de sinal. MACD acima do sinal indica momento de alta; abaixo, de baixa. O histograma mostra a distância entre eles. Cruzamentos isolados geram muitos falsos sinais."},
    "ADX": {"nome": "ADX / DMI", "grupo": "Tendência", "painel": "sub", "fn": _adx, "req": "hlc", "colunas": ["ADX", "DI_MAIS", "DI_MENOS"],
            "params": {"n": _P(14, 2, 100, "Períodos")},
            "explicacao": "Mede a FORÇA da tendência, não a direção: ADX abaixo de 20 sugere mercado sem tendência; acima de 25, tendência definida. +DI acima de −DI indica pressão compradora, o inverso, vendedora."},
    "ICHIMOKU": {"nome": "Ichimoku Kinko Hyo", "grupo": "Tendência", "painel": "preco", "fn": _ichimoku, "req": "hlc",
                 "colunas": ["TENKAN", "KIJUN", "SENKOU_A", "SENKOU_B", "CHIKOU"],
                 "params": {"tenkan": _P(9, 2, 100, "Tenkan"), "kijun": _P(26, 3, 200, "Kijun"), "senkou_b": _P(52, 5, 300, "Senkou B")},
                 "explicacao": "Sistema japonês com linhas de equilíbrio (Tenkan/Kijun) e uma nuvem (Senkou A/B). Preço acima da nuvem sugere alta, abaixo sugere baixa, dentro dela indefinição. A linha Chikou usa preços passados e NÃO entra em simulações."},
    "RSI": {"nome": "Índice de Força Relativa (RSI/IFR)", "grupo": "Momentum", "painel": "sub", "fn": _rsi, "req": "c", "colunas": ["RSI"],
            "params": {"n": _P(14, 2, 100, "Períodos")}, "faixa": (0, 100), "linhas": (30, 70),
            "explicacao": "Oscilador de 0 a 100 que compara altas e baixas recentes. Acima de 70 costuma indicar sobrecompra, abaixo de 30, sobrevenda. Em tendências fortes pode ficar muito tempo em sobrecompra/sobrevenda sem reverter."},
    "ESTOCASTICO": {"nome": "Estocástico", "grupo": "Momentum", "painel": "sub", "fn": _estocastico, "req": "hlc", "colunas": ["STOCH_K", "STOCH_D"],
                    "params": {"n": _P(14, 2, 100, "Períodos"), "suav_k": _P(3, 1, 20, "Suavização %K"), "d": _P(3, 1, 20, "Média %D")},
                    "faixa": (0, 100), "linhas": (20, 80),
                    "explicacao": "Posição do fechamento dentro da faixa de máximas e mínimas recentes (0 a 100). Acima de 80, sobrecompra; abaixo de 20, sobrevenda. Cruzamento de %K sobre %D mostra mudança de momento."},
    "CCI": {"nome": "Índice de Canal de Commodities (CCI)", "grupo": "Momentum", "painel": "sub", "fn": _cci, "req": "hlc", "colunas": ["CCI"],
            "params": {"n": _P(20, 2, 200, "Períodos")}, "linhas": (-100, 100),
            "explicacao": "Mede o desvio do preço típico (máx+mín+fech)/3 em relação à sua média. Acima de +100 indica força compradora/esticamento; abaixo de −100, o oposto."},
    "ROC": {"nome": "Taxa de variação (ROC)", "grupo": "Momentum", "painel": "sub", "fn": _roc, "req": "c", "colunas": ["ROC"],
            "params": {"n": _P(12, 1, 200, "Períodos")}, "linhas": (0,),
            "explicacao": "Variação percentual do preço em n períodos. Acima de zero, o preço subiu no intervalo; abaixo, caiu. Mede velocidade, não valor."},
    "WILLIAMS": {"nome": "Williams %R", "grupo": "Momentum", "painel": "sub", "fn": _williams, "req": "hlc", "colunas": ["WILLIAMS_R"],
                 "params": {"n": _P(14, 2, 100, "Períodos")}, "faixa": (-100, 0), "linhas": (-80, -20),
                 "explicacao": "Como o estocástico, de −100 a 0. Acima de −20, sobrecompra; abaixo de −80, sobrevenda."},
    "BOLLINGER": {"nome": "Bandas de Bollinger", "grupo": "Volatilidade", "painel": "preco", "fn": _bollinger, "req": "c",
                  "colunas": ["BOLL_SUP", "BOLL_MEDIA", "BOLL_INF", "BOLL_LARG", "BOLL_B"],
                  "params": {"n": _P(20, 2, 200, "Períodos"), "k": _P(2.0, 0.5, 5.0, "Desvios")},
                  "explicacao": "Média móvel com bandas a k desvios-padrão. Bandas apertadas indicam baixa volatilidade (possível expansão depois); preço fora da banda indica esticamento, não reversão garantida."},
    "ATR": {"nome": "Faixa média verdadeira (ATR)", "grupo": "Volatilidade", "painel": "sub", "fn": _atr, "req": "hlc", "colunas": ["ATR", "ATR_PCT"],
            "params": {"n": _P(14, 2, 100, "Períodos")},
            "explicacao": "Amplitude média diária dos candles (incluindo gaps). Mede o tamanho normal do movimento, não a direção; útil para dimensionar risco e stops."},
    "DESVIO": {"nome": "Desvio padrão", "grupo": "Volatilidade", "painel": "sub", "fn": _desvio, "req": "c", "colunas": ["DESVIO", "DESVIO_PCT"],
               "params": {"n": _P(20, 2, 200, "Períodos")},
               "explicacao": "Dispersão dos fechamentos em torno da média nos últimos n períodos (amostral). Em % da média (DESVIO_PCT) permite comparar ativos."},
    "KELTNER": {"nome": "Canais de Keltner", "grupo": "Volatilidade", "painel": "preco", "fn": _keltner, "req": "hlc", "colunas": ["KELT_SUP", "KELT_MEDIA", "KELT_INF"],
                "params": {"n": _P(20, 2, 200, "Média (EMA)"), "n_atr": _P(10, 2, 100, "ATR"), "mult": _P(2.0, 0.5, 5.0, "Múltiplo do ATR")},
                "explicacao": "Canal formado por uma EMA ± múltiplo do ATR. Menos sensível a picos que Bollinger. Fechamentos fora do canal sugerem movimento forte."},
    "OBV": {"nome": "Volume em balanço (OBV)", "grupo": "Volume e fluxo", "painel": "sub", "fn": _obv, "req": "cv", "colunas": ["OBV"], "params": {},
            "explicacao": "Soma o volume dos dias de alta e subtrai o dos dias de baixa. OBV subindo com o preço confirma o movimento; divergência entre os dois é um aviso."},
    "VWAP": {"nome": "Preço médio ponderado por volume (VWAP)", "grupo": "Volume e fluxo", "painel": "preco", "fn": _vwap, "req": "hlcv", "colunas": ["VWAP"],
             "params": {"n": _P(20, 2, 200, "Períodos (gráfico diário)")},
             "explicacao": "Preço médio do período ponderado pelo volume. Em gráficos intraday reinicia a cada dia; em diário/semanal é calculado numa janela móvel de n candles."},
    "VOL_MEDIO": {"nome": "Volume médio", "grupo": "Volume e fluxo", "painel": "sub", "fn": _vol_medio, "req": "v", "colunas": ["VOL_MEDIO", "VOL_RAZAO"],
                  "params": {"n": _P(20, 2, 200, "Períodos")},
                  "explicacao": "Média do volume e razão do volume atual sobre ela. Razão alta confirma movimentos (rompimentos); volume seco enfraquece."},
    "MFI": {"nome": "Índice de Fluxo de Dinheiro (MFI)", "grupo": "Volume e fluxo", "painel": "sub", "fn": _mfi, "req": "hlcv", "colunas": ["MFI"],
            "params": {"n": _P(14, 2, 100, "Períodos")}, "faixa": (0, 100), "linhas": (20, 80),
            "explicacao": "Um 'RSI com volume': acima de 80 sugere sobrecompra, abaixo de 20, sobrevenda, ponderando o dinheiro negociado."},
    "AD": {"nome": "Acumulação/Distribuição", "grupo": "Volume e fluxo", "painel": "sub", "fn": _acum_dist, "req": "hlcv", "colunas": ["AD"], "params": {},
           "explicacao": "Acumula o volume ponderado pela posição do fechamento no candle. Linha subindo sugere acumulação (compra); caindo, distribuição (venda)."},
    "DONCHIAN": {"nome": "Canal de Donchian", "grupo": "Tendência", "painel": "preco", "fn": _donchian, "req": "hl", "colunas": ["DON_ALTO", "DON_BAIXO"],
                 "params": {"n": _P(20, 2, 400, "Períodos")},
                 "explicacao": "Máxima e mínima dos n candles ANTERIORES (sem o atual). Fechar acima da máxima é um rompimento clássico; usada em estratégias de seguimento de tendência."},
}
GRUPOS = ["Tendência", "Momentum", "Volatilidade", "Volume e fluxo"]
COLUNAS_PROIBIDAS_BACKTEST = {"CHIKOU"}            # usa preços FUTUROS (deslocada para trás): proibida em simulações

_REQ_COLS = {"c": ["Close"], "hl": ["High", "Low"], "hlc": ["High", "Low", "Close"], "v": ["Close", "Volume"], "cv": ["Close", "Volume"],
             "hlcv": ["High", "Low", "Close", "Volume"]}


def _parametros(nome: str, params: dict | None) -> dict:
    spec = INDICADORES[nome]["params"]
    out = {}
    for k, s in spec.items():
        v = (params or {}).get(k, s["padrao"])
        try:
            v = float(v) if isinstance(s["padrao"], float) else int(v)
        except Exception:
            raise ValueError(f"Parâmetro '{k}' de {nome} inválido.")
        if not (s["min"] <= v <= s["max"]):
            raise ValueError(f"Parâmetro '{s['rotulo']}' de {nome} deve ficar entre {s['min']} e {s['max']}.")
        out[k] = v
    extra = set(params or {}) - set(spec) - {"col"}
    if extra:
        raise ValueError(f"Parâmetro desconhecido em {nome}: {', '.join(sorted(extra))}.")
    return out


def minimo_candles(nome: str, params: dict | None = None) -> int:
    p = _parametros(nome, params)
    base = max([v for k, v in p.items() if k != "mult" and k != "k"] or [1])
    extra = {"MACD": p.get("lenta", 26) + p.get("sinal", 9), "ADX": 3 * p.get("n", 14), "ICHIMOKU": p.get("senkou_b", 52) + p.get("kijun", 26),
             "ESTOCASTICO": p.get("n", 14) + p.get("suav_k", 3) + p.get("d", 3), "KELTNER": base + 5}.get(nome)
    return int(extra or base + 2)


def disponibilidade(nome: str, df: pd.DataFrame, params: dict | None = None) -> tuple[bool, str]:
    """(ok, motivo). Indicador só é calculado com as colunas necessárias, candles suficientes e dados sem lacuna de volume."""
    if nome not in INDICADORES:
        return False, "Indicador desconhecido."
    if df is None or df.empty:
        return False, "Sem dados de preço."
    falta = [c for c in _REQ_COLS[INDICADORES[nome]["req"]] if c not in df.columns]
    if falta:
        nomes = {"High": "máxima", "Low": "mínima", "Volume": "volume", "Close": "fechamento"}
        return False, "Faltam dados de " + ", ".join(nomes.get(c, c) for c in falta) + " nesta série."
    try:
        mn = minimo_candles(nome, params)
    except ValueError as e:
        return False, str(e)
    if len(df) < mn:
        return False, f"Precisa de pelo menos {mn} candles (há {len(df)})."
    return True, ""


def calcular(nome: str, df: pd.DataFrame, **params) -> pd.DataFrame:
    """Calcula o indicador alinhado ao índice de `df`. Levanta IndicadorIndisponivel se faltar dado (nunca preenche)."""
    ok, motivo = disponibilidade(nome, df, params)
    if not ok:
        raise IndicadorIndisponivel(motivo)
    spec = INDICADORES[nome]
    p = _parametros(nome, params)
    col = (params or {}).get("col")
    if "n" in spec["params"] and nome in ("SMA", "EMA", "WMA"):
        p["col"] = col if col in ("Close", "Open", "High", "Low") and col in df.columns else "Close"
    out = spec["fn"](df, **p)
    out.index = df.index
    return out


def tentar(nome: str, df: pd.DataFrame, **params) -> tuple[pd.DataFrame | None, str]:
    try:
        return calcular(nome, df, **params), ""
    except IndicadorIndisponivel as e:
        return None, str(e)
    except ValueError as e:
        return None, str(e)


# =============================================================================== adequação por classe
_TODOS = set(INDICADORES)
_SO_PRECO = {"SMA", "EMA", "WMA", "MACD", "RSI", "ROC", "BOLLINGER", "DESVIO"}


def perfil_classe(classe: str, df: pd.DataFrame | None = None, freq: str | None = None, serie_adequada: bool = False) -> dict:
    """Quais indicadores a classe aceita e por quê. Não força indicador de ação em ativo para o qual ele não faz sentido.
    {'liberada', 'permitidos', 'bloqueados': {nome: motivo}, 'avisos': [...]}"""
    classe = classe if classe in CLASSES else "acao"
    freq = freq or (inferir_frequencia(df.index) if df is not None and len(df) > 2 else "D")
    avisos: list[str] = []
    bloqueados: dict[str, str] = {}
    if classe == "renda_fixa":
        if not serie_adequada:
            return {"liberada": False, "permitidos": [], "avisos": [], "classe": classe,
                    "bloqueados": {n: "Indicadores de ações não se aplicam a títulos de renda fixa." for n in INDICADORES},
                    "motivo": "Renda fixa não recebe indicadores de ações automaticamente. Use a análise de títulos (taxas, curva de juros e "
                              "marcação a mercado, Passo 11) ou informe uma série adequada de preço/taxa com histórico suficiente."}
        perm = {"SMA", "EMA", "ROC", "DESVIO", "BOLLINGER"}
        avisos.append("Série de preço/taxa de renda fixa: só indicadores simples de tendência e dispersão; não há volume nem candles.")
    elif classe == "fundo":
        if freq == "intra" or df is None or len(df) < 120:
            return {"liberada": False, "permitidos": [], "avisos": [], "classe": classe,
                    "bloqueados": {n: "Série de cotas curta ou irregular." for n in INDICADORES},
                    "motivo": "Fundos só recebem análise técnica com cotas diárias e histórico suficiente (120+ cotas). Cotas atualizadas "
                              "esporadicamente não são tratadas como cotações intraday."}
        perm = set(_SO_PRECO)
        avisos.append("Cota de fundo não tem volume nem máxima/mínima de pregão: só indicadores calculados sobre o valor da cota.")
    else:
        perm = set(_TODOS)
    if classe == "fii":
        avisos.append("Proventos devem ser analisados separadamente do preço da cota; FIIs de baixa liquidez geram sinais pouco confiáveis.")
    if classe == "cripto":
        avisos.append("Preços e volumes variam entre exchanges e pares de negociação; a análise vale para o par e a fonte indicados.")
    for n in list(perm):
        if INDICADORES[n]["req"] in ("hlcv", "hl", "hlc") and df is not None and not all(c in df.columns for c in ("High", "Low")):
            perm.discard(n)
            bloqueados[n] = "Sem máxima e mínima nesta série."
        elif INDICADORES[n]["req"] in ("cv", "v", "hlcv") and df is not None and "Volume" not in df.columns:
            perm.discard(n)
            bloqueados[n] = "Sem volume confiável nesta série."
    for n in _TODOS - perm:
        bloqueados.setdefault(n, f"Não se aplica a {ROTULO_CLASSE.get(classe, classe).lower()}.")
    return {"liberada": True, "permitidos": sorted(perm), "bloqueados": bloqueados, "avisos": avisos, "classe": classe, "motivo": ""}


# =============================================================================== tendência, níveis, extremos
LIM_VOL_RAZAO = 1.8          # volatilidade de 20 dias sobre a de 120 (mesmo limiar da Central de inteligência, Passo 13)
LIM_VOLUME_ALTO = 2.0        # volume ≥ 2× a mediana dos 20 candles anteriores
ZONAS = {"RSI": (30, 70), "STOCH_K": (20, 80), "WILLIAMS_R": (-80, -20), "CCI": (-100, 100), "MFI": (20, 80)}


def _tem_hl(df) -> bool:
    return "High" in df.columns and "Low" in df.columns


def _hl(df) -> pd.DataFrame:
    """Para localizar topos/fundos em séries sem máxima/mínima usa-se o fechamento (só no cálculo; nada é exibido como candle)."""
    return df if _tem_hl(df) else df.assign(High=df["Close"], Low=df["Close"])


def _pivos(df: pd.DataFrame, w: int = 5):
    import tecnica                                  # reaproveita a detecção de topos e fundos já existente no app
    return tecnica.pivots(_hl(df), w)


def _w_padrao(n: int) -> int:
    return 5 if n >= 120 else 3


def classificar_tendencia(df: pd.DataFrame, min_candles: int = 40) -> dict:
    """Alta, baixa ou lateral por VÁRIOS critérios independentes (nenhum cruzamento sozinho decide):
    1 preço × média longa · 2 alinhamento e inclinação das médias · 3 regressão do log-preço (t ≥ 2) · 4 topos e fundos
    (estrutura) · 5 ADX/DMI (só com máxima e mínima). Precisa de 3+ critérios com dado; sem isso devolve None."""
    out = {"tendencia": None, "confianca": None, "criterios": [], "candles": 0, "motivo": None, "placar": None, "adx": None, "divergentes": False}
    if df is None or "Close" not in df.columns:
        out["motivo"] = "Sem dados de preço."
        return out
    c = df["Close"].astype(float).dropna()
    n = len(c)
    out["candles"] = n
    if n < min_candles:
        out["motivo"] = f"Histórico curto: {n} candles (mínimo {min_candles})."
        return out
    longa = min(50, max(10, n // 2))
    curta = max(5, longa // 2)
    ml, mc = c.rolling(longa).mean(), c.rolling(curta).mean()
    crit = []

    def add(nome, voto, texto):
        crit.append({"nome": nome, "voto": voto, "texto": texto})

    dist = (c.iloc[-1] / ml.iloc[-1] - 1) * 100
    add(f"Preço × média de {longa}", 1 if dist > 0.5 else -1 if dist < -0.5 else 0,
        f"Preço {'acima' if dist > 0 else 'abaixo'} da média de {longa} candles ({fmt_num(dist, 1)}%).")
    k = max(3, longa // 5)
    incl = (ml.iloc[-1] / ml.iloc[-1 - k] - 1) * 100 if n > longa + k and _ok(ml.iloc[-1 - k]) else None
    if incl is not None:
        sub = mc.iloc[-1] > ml.iloc[-1]
        v = 1 if (sub and incl > 0.2) else -1 if ((not sub) and incl < -0.2) else 0
        add(f"Médias {curta}/{longa}", v, f"Média curta {'acima' if sub else 'abaixo'} da longa; longa {'subindo' if incl > 0 else 'caindo'} ({fmt_num(incl, 1)}% em {k} candles).")
    reg = I.tendencia(c, min(120, n)) if n >= 40 else {"rotulo": None}
    if reg.get("rotulo"):
        v = {"alta": 1, "baixa": -1}.get(reg["rotulo"], 0)
        add("Regressão do preço", v, f"Inclinação do log-preço em {reg['n']} candles: t = {fmt_num(reg['t'], 1)} (|t| ≥ 2 = estatisticamente relevante).")
    topos, fundos = _pivos(df.loc[c.index], _w_padrao(n))
    if len(topos) >= 2 and len(fundos) >= 2:
        ht, hf = topos[-1][1] > topos[-2][1], fundos[-1][1] > fundos[-2][1]
        v = 1 if (ht and hf) else -1 if (not ht and not hf) else 0
        add("Topos e fundos", v, ("Topos e fundos mais altos." if v == 1 else "Topos e fundos mais baixos." if v == -1 else "Topos e fundos sem sequência clara."))
    if {"High", "Low"}.issubset(df.columns) and n >= 45:
        a, _ = tentar("ADX", df.loc[c.index])
        if a is not None and _ok(a["ADX"].iloc[-1]):
            adx, mais, menos = float(a["ADX"].iloc[-1]), float(a["DI_MAIS"].iloc[-1]), float(a["DI_MENOS"].iloc[-1])
            out["adx"] = adx
            if adx >= 20:
                add("ADX / DMI", 1 if mais > menos else -1, f"ADX {fmt_num(adx, 1)} (tendência definida) com {'+DI' if mais > menos else '−DI'} dominante.")
            else:
                add("ADX / DMI", 0, f"ADX {fmt_num(adx, 1)} (< 20): pouca força direcional.")
    out["criterios"] = crit
    tot = len(crit)
    if tot < 3:
        out["motivo"] = "Poucos critérios com dado suficiente."
        return out
    pos, neg = sum(x["voto"] == 1 for x in crit), sum(x["voto"] == -1 for x in crit)
    out["placar"] = (pos - neg) / tot
    # alta/baixa exigem 60%+ dos critérios a favor E nenhum contra: um critério forte em sentido oposto (ex.: regressão de 120
    # candles) impede o rótulo e a leitura fica "lateral" com `divergentes=True`.
    out["divergentes"] = bool(pos and neg)
    if pos / tot >= 0.6 and neg == 0:
        t, frac = "alta", pos / tot
    elif neg / tot >= 0.6 and pos == 0:
        t, frac = "baixa", neg / tot
    else:
        t, frac = "lateral", 0.0
    out["tendencia"] = t
    if t == "lateral":
        out["confianca"] = "média" if (out["adx"] is not None and out["adx"] < 20 and not out["divergentes"]) else "baixa"
    else:
        out["confianca"] = "alta" if (frac >= 0.8 and tot >= 4) else "média" if frac >= 0.6 else "baixa"
    return out


def consolidacao(df: pd.DataFrame, janela: int = 20) -> dict:
    """Consolidação = bandas de Bollinger entre as 20% mais estreitas dos últimos 120 candles (e ADX < 20, se houver)."""
    out = {"ativa": False, "percentil_largura": None, "faixa": None, "motivo": None}
    if df is None or len(df) < 60:
        out["motivo"] = "Histórico curto."
        return out
    b, _ = tentar("BOLLINGER", df)
    if b is None:
        out["motivo"] = "Indisponível."
        return out
    larg = b["BOLL_LARG"].dropna().iloc[-120:]
    if len(larg) < 40:
        out["motivo"] = "Histórico curto."
        return out
    pct = float((larg <= larg.iloc[-1]).mean())
    out["percentil_largura"] = pct
    a, _ = tentar("ADX", df) if _tem_hl(df) else (None, "")
    adx_ok = a is None or not _ok(a["ADX"].iloc[-1]) or float(a["ADX"].iloc[-1]) < 20
    j = _hl(df).iloc[-janela:]
    out["faixa"] = (float(j["Low"].min()), float(j["High"].max()))
    out["ativa"] = bool(pct <= 0.2 and adx_ok)
    return out


def suportes_resistencias(df: pd.DataFrame, w: int | None = None, tol: float = 0.015, min_toques: int = 2, max_n: int = 3) -> dict:
    """Zonas de preço tocadas várias vezes por topos/fundos (pivôs). Suporte = zona abaixo do preço atual; resistência = acima.
    Cada zona traz preço médio, faixa, nº de toques, último toque e distância ao preço atual."""
    out = {"suportes": [], "resistencias": [], "dentro": [], "w": None}
    if df is None or len(df) < 40:
        return out
    n = len(df)
    w = w or _w_padrao(n)
    out["w"] = w
    topos, fundos = _pivos(df, w)
    pts = sorted([(p, i) for i, p in topos + fundos])
    grupos: list[list[tuple]] = []
    for p, i in pts:
        if grupos and abs(p - np.mean([x[0] for x in grupos[-1]])) / np.mean([x[0] for x in grupos[-1]]) <= tol:
            grupos[-1].append((p, i))
        else:
            grupos.append([(p, i)])
    ultimo = float(df["Close"].iloc[-1])
    zonas = []
    for g in grupos:
        if len(g) < min_toques:
            continue
        ps = [x[0] for x in g]
        pm = float(np.mean(ps))
        lt = max(x[1] for x in g)
        zonas.append({"preco": pm, "zona": (float(min(ps)), float(max(ps))), "toques": len(g), "ultimo_toque": _dia(df.index[lt]),
                      "idx_ultimo": int(lt), "distancia_pct": (pm / ultimo - 1) * 100,
                      "forca": len(g) + 2.0 * (lt / n)})
    for z in zonas:
        lo, hi = z["zona"]
        if ultimo > hi * 1.0:
            z["tipo"] = "Suporte"
        elif ultimo < lo:
            z["tipo"] = "Resistência"
        else:
            z["tipo"] = "Zona atual"
    sup = sorted([z for z in zonas if z["tipo"] == "Suporte"], key=lambda z: -z["preco"])[:max_n]
    res = sorted([z for z in zonas if z["tipo"] == "Resistência"], key=lambda z: z["preco"])[:max_n]
    out.update({"suportes": sup, "resistencias": res, "dentro": [z for z in zonas if z["tipo"] == "Zona atual"]})
    return out


def extremos(df: pd.DataFrame, janela_ano: int = 252) -> dict:
    """Máxima e mínima do período exibido e dos últimos ~12 meses (usa máxima/mínima do candle quando existem)."""
    if df is None or df.empty:
        return {}
    h = df["High"] if "High" in df.columns else df["Close"]
    l = df["Low"] if "Low" in df.columns else df["Close"]
    ult = float(df["Close"].iloc[-1])

    def par(hh, ll):
        return {"max": {"data": _dia(hh.idxmax()), "preco": float(hh.max())}, "min": {"data": _dia(ll.idxmin()), "preco": float(ll.min())}}

    out = {"periodo": par(h, l)}
    out["periodo"]["dist_max_pct"] = (ult / out["periodo"]["max"]["preco"] - 1) * 100
    out["periodo"]["dist_min_pct"] = (ult / out["periodo"]["min"]["preco"] - 1) * 100
    if len(df) >= janela_ano and inferir_frequencia(df.index) == "D":
        out["ano"] = par(h.iloc[-janela_ano:], l.iloc[-janela_ano:])
    return out


# =============================================================================== osciladores, volatilidade, volume, divergências
def leitura_osciladores(df: pd.DataFrame) -> dict:
    """Valor atual e zona (sobrecompra/sobrevenda) de cada oscilador disponível. Em tendência forte as zonas podem persistir."""
    itens = []
    for nome, col in (("RSI", "RSI"), ("ESTOCASTICO", "STOCH_K"), ("WILLIAMS", "WILLIAMS_R"), ("CCI", "CCI"), ("MFI", "MFI")):
        o, _ = tentar(nome, df)
        if o is None or not _ok(o[col].iloc[-1]):
            continue
        v = float(o[col].iloc[-1])
        lo, hi = ZONAS[col]
        zona = "sobrecompra" if v >= hi else "sobrevenda" if v <= lo else "neutra"
        itens.append({"indicador": nome, "coluna": col, "valor": v, "zona": zona, "limites": (lo, hi)})
    sc = [x for x in itens if x["zona"] == "sobrecompra"]
    sv = [x for x in itens if x["zona"] == "sobrevenda"]
    geral = "sobrecompra" if sc and len(sc) >= len(sv) else "sobrevenda" if sv else "neutra"
    return {"itens": itens, "geral": geral, "n_sobrecompra": len(sc), "n_sobrevenda": len(sv)}


def volatilidade_atual(df: pd.DataFrame) -> dict:
    out = {"razao_20_120": None, "atr_pct": None, "atr_percentil": None, "elevada": False, "motivos": []}
    r = df["Close"].pct_change().dropna()
    if len(r) >= 140 and float(r.iloc[-120:].std()) > 0:
        out["razao_20_120"] = float(r.iloc[-20:].std() / r.iloc[-120:].std())
        if out["razao_20_120"] >= LIM_VOL_RAZAO:
            out["elevada"] = True
            out["motivos"].append(f"Volatilidade dos últimos 20 candles é {fmt_num(out['razao_20_120'], 1)}× a dos últimos 120.")
    a, _ = tentar("ATR", df) if _tem_hl(df) else (None, "")
    if a is not None:
        s = a["ATR_PCT"].dropna()
        if len(s) >= 60:
            out["atr_pct"] = float(s.iloc[-1])
            out["atr_percentil"] = float((s.iloc[-250:] <= s.iloc[-1]).mean())
            if out["atr_percentil"] >= 0.9 and not out["elevada"]:
                out["elevada"] = True
                out["motivos"].append(f"ATR de {fmt_num(out['atr_pct'], 2)}% do preço está entre os 10% mais altos do último período.")
    return out


def volume_atual(df: pd.DataFrame) -> dict:
    out = {"disponivel": False, "razao": None, "media5_sobre_20": None, "estado": None}
    if "Volume" not in df.columns or len(df) < 25:
        return out
    v = df["Volume"].astype(float)
    mediana = float(v.iloc[-21:-1].median())
    if not mediana > 0:
        return out
    out["disponivel"] = True
    out["razao"] = float(v.iloc[-1] / mediana)
    out["media5_sobre_20"] = float(v.iloc[-5:].mean() / v.iloc[-20:].mean()) if float(v.iloc[-20:].mean()) > 0 else None
    out["estado"] = "alto" if out["razao"] >= LIM_VOLUME_ALTO else "baixo" if out["razao"] <= 0.5 else "normal"
    return out


def divergencias(df: pd.DataFrame, janela: int = 90) -> list[dict]:
    """Divergência entre preço e RSI nos dois últimos fundos (altista) ou topos (baixista), dentro da janela. É um aviso, não um gatilho."""
    r, _ = tentar("RSI", df)
    if r is None or len(df) < 50:
        return []
    n = len(df)
    topos, fundos = _pivos(df, _w_padrao(n))
    rsi = r["RSI"]
    out = []
    ini = n - janela
    fs = [(i, p) for i, p in fundos if i >= ini and _ok(rsi.iloc[i])]
    ts = [(i, p) for i, p in topos if i >= ini and _ok(rsi.iloc[i])]
    if len(fs) >= 2:
        (i1, p1), (i2, p2) = fs[-2], fs[-1]
        if p2 < p1 * 0.999 and rsi.iloc[i2] > rsi.iloc[i1] + 2:
            out.append({"tipo": "altista", "texto": f"Preço fez fundo mais baixo ({fmt_num(p1)} → {fmt_num(p2)}) enquanto o RSI fez fundo mais alto "
                        f"({fmt_num(rsi.iloc[i1], 1)} → {fmt_num(rsi.iloc[i2], 1)}).", "de": _dia(df.index[i1]), "ate": _dia(df.index[i2])})
    if len(ts) >= 2:
        (i1, p1), (i2, p2) = ts[-2], ts[-1]
        if p2 > p1 * 1.001 and rsi.iloc[i2] < rsi.iloc[i1] - 2:
            out.append({"tipo": "baixista", "texto": f"Preço fez topo mais alto ({fmt_num(p1)} → {fmt_num(p2)}) enquanto o RSI fez topo mais baixo "
                        f"({fmt_num(rsi.iloc[i1], 1)} → {fmt_num(rsi.iloc[i2], 1)}).", "de": _dia(df.index[i1]), "ate": _dia(df.index[i2])})
    if "Volume" in df.columns and len(df) >= 60:
        o, _ = tentar("OBV", df)
        if o is not None:
            j = 20
            dp = df["Close"].iloc[-1] / df["Close"].iloc[-1 - j] - 1
            do = o["OBV"].iloc[-1] - o["OBV"].iloc[-1 - j]
            esc = float(df["Volume"].iloc[-j:].sum())
            if esc > 0:
                if dp > 0.03 and do / esc < -0.1:
                    out.append({"tipo": "baixista", "texto": "Preço subiu em 20 candles, mas o OBV (fluxo de volume) caiu: o avanço tem pouca adesão do volume.",
                                "de": _dia(df.index[-1 - j]), "ate": _dia(df.index[-1])})
                elif dp < -0.03 and do / esc > 0.1:
                    out.append({"tipo": "altista", "texto": "Preço caiu em 20 candles, mas o OBV subiu: a queda tem pouca adesão do volume vendedor.",
                                "de": _dia(df.index[-1 - j]), "ate": _dia(df.index[-1])})
    return out


# =============================================================================== padrões gráficos
def _conf_rotulo(v: float) -> str:
    return "alta" if v >= 70 else "média" if v >= 45 else "baixa"


def _vol_contrai(df, a: int, b: int) -> bool | None:
    if "Volume" not in df.columns or b - a < 9:
        return None
    v = df["Volume"].iloc[a:b + 1].astype(float)
    t = len(v) // 3
    return bool(v.iloc[-t:].mean() < v.iloc[:t].mean() * 0.8) if v.iloc[:t].mean() > 0 else None


def detectar_padroes(df: pd.DataFrame, w: int | None = None, recencia: int = 90, janela_linhas: int = 120) -> list[dict]:
    """Padrões gráficos com critérios explícitos. Cada item traz: nome, direção (viés), estado (em formação / confirmado /
    invalidado), período, região (datas e preços), pontos e linhas para o gráfico, critérios usados, confiança (0–100 e rótulo),
    cenários e condições de invalidação. Padrão incerto NUNCA aparece como confirmado. Sem dados suficientes → lista vazia."""
    if df is None or len(df) < 60 or "Close" not in df.columns:
        return []
    n = len(df)
    w = w or _w_padrao(n)
    d = _hl(df)
    c, h, l = d["Close"].to_numpy(float), d["High"].to_numpy(float), d["Low"].to_numpy(float)
    idx = d.index
    topos, fundos = _pivos(df, w)
    pats: list[dict] = []

    def reg(nome, direcao, estado, i0, i1, criterios, conf, cenarios, invalida, pontos=None, linhas=None, y0=None, y1=None, alvo=None):
        conf = int(max(0, min(100, round(conf))))
        pats.append({"nome": nome, "direcao": direcao, "estado": estado, "inicio": _dia(idx[i0]), "fim": _dia(idx[i1]),
                     "candles": int(i1 - i0 + 1), "idx_ini": int(i0), "idx_fim": int(i1),
                     "regiao": {"x0": _dia(idx[i0]), "x1": _dia(idx[min(n - 1, i1)]), "y0": float(y0 if y0 is not None else l[i0:i1 + 1].min()),
                                "y1": float(y1 if y1 is not None else h[i0:i1 + 1].max())},
                     "pontos": [(_dia(idx[i]), float(p)) for i, p in (pontos or [])],
                     "linhas": [(_dia(idx[a]), float(pa), _dia(idx[b]), float(pb)) for a, pa, b, pb in (linhas or [])],
                     "criterios": criterios, "confianca": conf, "confianca_rotulo": _conf_rotulo(conf), "cenarios": cenarios,
                     "invalidacao": invalida, "alvo": None if alvo is None else float(alvo)})

    # ---- duplo topo / duplo fundo
    for topo, serie_ext, serie_vale, ext in ((True, h, l, topos), (False, l, h, fundos)):
        for (i1, p1), (i2, p2) in zip(ext, ext[1:]):
            if not (8 <= i2 - i1 <= 80) or abs(p1 - p2) / max(p1, p2) > 0.03 or i2 < n - recencia:
                continue
            vale = float(serie_vale[i1:i2 + 1].min() if topo else serie_vale[i1:i2 + 1].max())
            prof = abs(min(p1, p2) - vale) / min(p1, p2) if topo else abs(vale - max(p1, p2)) / max(p1, p2)
            if prof < 0.04:
                continue
            apos = c[i2 + 1:]
            conf_ = bool((apos < vale).any()) if topo else bool((apos > vale).any())
            inval = bool((c[i2 + 1:] > max(p1, p2) * 1.01).any()) if topo else bool((c[i2 + 1:] < min(p1, p2) * 0.99).any())
            estado = "confirmado" if conf_ else "invalidado" if inval else "em formação"
            c_ = 40 + (15 if abs(p1 - p2) / max(p1, p2) < 0.015 else 0) + (15 if prof >= 0.08 else 0) + (20 if conf_ else 0) - (30 if inval else 0)
            vc = _vol_contrai(df, i1, i2)
            if vc:
                c_ += 10
            alvo = vale - (max(p1, p2) - vale) if topo else vale + (vale - min(p1, p2))
            crit = [f"Dois {'topos' if topo else 'fundos'} em {fmt_num(p1)} e {fmt_num(p2)} (diferença de {fmt_num(abs(p1 - p2) / max(p1, p2) * 100, 1)}%).",
                    f"Separados por {i2 - i1} candles, com {'vale' if topo else 'pico'} intermediário em {fmt_num(vale)} (profundidade de {fmt_num(prof * 100, 1)}%)."]
            if vc:
                crit.append("Volume menor no segundo extremo.")
            ext_lado = max(p1, p2) if topo else min(p1, p2)
            reg("Topo duplo" if topo else "Fundo duplo", "baixa" if topo else "alta", estado, i1, i2, crit, c_,
                [f"Confirma com fechamento {'abaixo' if topo else 'acima'} de {fmt_num(vale)} (linha de pescoço); a projeção da altura do padrão aponta para {fmt_num(alvo)} (referência, não previsão).",
                 f"Se o preço ultrapassar {fmt_num(ext_lado)}, o padrão perde validade."],
                f"Fechamento {'acima' if topo else 'abaixo'} de {fmt_num(ext_lado * (1.01 if topo else 0.99))}.",
                pontos=[(i1, p1), (i2, p2)], linhas=[(i1, p1, i2, p2), (i1, vale, min(n - 1, i2 + 10), vale)], alvo=alvo)

    # ---- ombro-cabeça-ombro e invertido
    for topo, ext, serie_vale in ((True, topos, l), (False, fundos, h)):
        for (ia, pa), (ib, pb), (ic, pc_) in zip(ext, ext[1:], ext[2:]):
            if ic < n - recencia or ic - ia > 120:
                continue
            cabeca = pb > max(pa, pc_) * 1.03 if topo else pb < min(pa, pc_) * 0.97
            if not cabeca or abs(pa - pc_) / max(pa, pc_) > 0.07:
                continue
            f = (lambda s: (int(s.argmin()), float(s.min()))) if topo else (lambda s: (int(s.argmax()), float(s.max())))
            ja, va = f(serie_vale[ia:ib + 1]); ja += ia
            jb, vb = f(serie_vale[ib:ic + 1]); jb += ib
            if ja == jb:
                continue
            m = (vb - va) / (jb - ja)
            pescoco = lambda x: va + m * (x - ja)  # noqa: E731
            xs = np.arange(ic + 1, n)
            conf_ = bool(len(xs) and ((c[ic + 1:] < np.array([pescoco(x) for x in xs])).any() if topo else (c[ic + 1:] > np.array([pescoco(x) for x in xs])).any()))
            inval = bool((c[ic + 1:] > pb).any()) if topo else bool((c[ic + 1:] < pb).any())
            estado = "confirmado" if conf_ else "invalidado" if inval else "em formação"
            altura = abs(pb - pescoco(jb))
            alvo = pescoco(ic) - altura if topo else pescoco(ic) + altura
            c_ = 40 + (15 if abs(pa - pc_) / max(pa, pc_) < 0.03 else 0) + (10 if abs(pb - max(pa, pc_)) / pb > 0.06 else 0) + (20 if conf_ else 0) - (30 if inval else 0)
            crit = [f"Cabeça em {fmt_num(pb)} {'acima' if topo else 'abaixo'} dos ombros ({fmt_num(pa)} e {fmt_num(pc_)}).",
                    f"Ombros com diferença de {fmt_num(abs(pa - pc_) / max(pa, pc_) * 100, 1)}%.",
                    f"Linha de pescoço entre {fmt_num(va)} e {fmt_num(vb)}."]
            xe = min(n - 1, jb + 8)
            reg("Ombro-cabeça-ombro" if topo else "Ombro-cabeça-ombro invertido", "baixa" if topo else "alta", estado, ia, ic, crit, c_,
                [f"Confirma com fechamento {'abaixo' if topo else 'acima'} da linha de pescoço; a altura da cabeça projeta {fmt_num(alvo)} (referência, não previsão).",
                 f"Se o preço {'superar' if topo else 'perder'} {fmt_num(pb)} (cabeça), o padrão é invalidado."],
                f"Fechamento {'acima' if topo else 'abaixo'} de {fmt_num(pb)}.",
                pontos=[(ia, pa), (ib, pb), (ic, pc_)], linhas=[(ja, va, xe, pescoco(xe))], alvo=alvo)

    # ---- triângulos, cunhas, canais, retângulos (linhas ajustadas aos topos e fundos recentes)
    ini = max(0, n - janela_linhas)
    rt, rf = [p for p in topos if p[0] >= ini][-4:], [p for p in fundos if p[0] >= ini][-4:]
    if len(rt) >= 2 and len(rf) >= 2 and len(rt) + len(rf) >= 4:
        x0, x1 = min(rt[0][0], rf[0][0]), n - 1
        at, bt = np.polyfit([p[0] for p in rt], [p[1] for p in rt], 1)
        af, bf = np.polyfit([p[0] for p in rf], [p[1] for p in rf], 1)
        up, lo = lambda x: at * x + bt, lambda x: af * x + bf  # noqa: E731
        span = x1 - x0
        pm = float(np.mean(c[x0:]))
        st_, sf = at * span / pm, af * span / pm
        g0, g1 = up(x0) - lo(x0), up(x1) - lo(x1)
        xs = np.arange(x0, x1 + 1)
        dentro = float(np.mean((c[x0:] <= up(xs) * 1.01) & (c[x0:] >= lo(xs) * 0.99)))
        if g0 > 0 and g1 > 0 and span >= 20 and dentro >= 0.85:
            plano, conv = 0.025, g1 < g0 * 0.75
            paralelo = abs(st_ - sf) < 0.03 and 0.8 <= g1 / g0 <= 1.25
            nome = direcao = None
            if conv:
                if abs(st_) < plano and sf > plano:
                    nome, direcao = "Triângulo ascendente", "alta"
                elif abs(sf) < plano and st_ < -plano:
                    nome, direcao = "Triângulo descendente", "baixa"
                elif st_ < -plano and sf > plano:
                    nome, direcao = "Triângulo simétrico", "neutro"
                elif st_ > plano and sf > plano:
                    nome, direcao = "Cunha ascendente", "baixa"
                elif st_ < -plano and sf < -plano:
                    nome, direcao = "Cunha descendente", "alta"
            elif paralelo:
                if abs(st_) < plano and abs(sf) < plano and g1 / pm >= 0.03:
                    nome, direcao = "Retângulo", "neutro"
                elif st_ > plano and sf > plano:
                    nome, direcao = "Canal de alta", "alta"
                elif st_ < -plano and sf < -plano:
                    nome, direcao = "Canal de baixa", "baixa"
            if nome:
                u_, l_ = up(x1), lo(x1)
                ult = float(c[-1])
                rompe_cima, rompe_baixo = ult > u_ * 1.01, ult < l_ * 0.99
                viés = {"alta": "cima", "baixa": "baixo", "neutro": None}[direcao]
                if rompe_cima or rompe_baixo:
                    lado = "cima" if rompe_cima else "baixo"
                    estado = "confirmado" if (viés is None or viés == lado) else "invalidado"
                else:
                    estado = "em formação"
                toques = len(rt) + len(rf)
                c_ = 30 + 8 * min(4, toques - 4) + (10 if dentro >= 0.95 else 0) + (10 if span >= 30 else 0) - (15 if toques < 5 else 0)
                vc = _vol_contrai(df, x0, x1) if nome.startswith(("Triângulo", "Cunha")) else None
                if vc:
                    c_ += 10
                if estado == "confirmado":
                    vr = volume_atual(df)
                    c_ += 15 if (vr["disponivel"] and (vr["razao"] or 0) >= 1.5) else 5
                crit = [f"{len(rt)} topos e {len(rf)} fundos ajustados por duas linhas ao longo de {span} candles.",
                        f"{fmt_num(dentro * 100, 0)}% dos fechamentos ficaram dentro das linhas.",
                        f"Inclinação da linha superior {fmt_num(st_ * 100, 1)}% e da inferior {fmt_num(sf * 100, 1)}% no período; "
                        f"{'linhas convergindo' if conv else 'linhas paralelas'}."]
                if vc:
                    crit.append("Volume diminuindo dentro do padrão.")
                cen = []
                if direcao == "alta":
                    cen = [f"O padrão tem viés de alta: rompimento acima de {fmt_num(u_)} com volume o confirmaria.", f"Perder {fmt_num(l_)} contraria o viés."]
                elif direcao == "baixa":
                    cen = [f"O padrão tem viés de baixa: rompimento abaixo de {fmt_num(l_)} o confirmaria.", f"Superar {fmt_num(u_)} contraria o viés."]
                else:
                    cen = [f"Sem viés definido: o rompimento acima de {fmt_num(u_)} ou abaixo de {fmt_num(l_)} indicaria a direção."]
                inv = (f"Fechamento {'abaixo de ' + fmt_num(l_ * 0.99) if viés == 'cima' else 'acima de ' + fmt_num(u_ * 1.01)} contra o viés."
                       if viés else "Retorno do preço para dentro da faixa após o rompimento.")
                reg(nome, direcao, estado, x0, x1, crit, c_, cen, inv, pontos=rt + rf, linhas=[(x0, up(x0), x1, u_), (x0, lo(x0), x1, l_)],
                    y0=min(lo(x0), l_), y1=max(up(x0), u_))

    # ---- bandeiras (mastro forte + consolidação curta contra a tendência)
    melhor = None
    for k in range(6, 21):
        if n < k + 25:
            break
        for pl in range(5, 16):
            a, b = n - 1 - k, n - 1 - k - pl
            if b < 0:
                continue
            mov = c[a] / c[b] - 1
            if abs(mov) < 0.10:
                continue
            seg_h, seg_l = h[a:].max(), l[a:].min()
            retr = (c[a] - seg_l) / (c[a] - c[b]) if mov > 0 else (seg_h - c[a]) / (c[b] - c[a])
            amplitude = (seg_h - seg_l) / abs(c[a] - c[b])
            deriva = c[-1] / c[a] - 1
            contra = (mov > 0 and deriva <= 0.01) or (mov < 0 and deriva >= -0.01)
            if retr <= 0.5 and amplitude <= 0.6 and contra:
                if melhor is None or abs(mov) > abs(melhor[0]):
                    melhor = (mov, k, pl, retr, seg_h, seg_l, a, b)
    if melhor:
        mov, k, pl, retr, seg_h, seg_l, a, b = melhor
        alta = mov > 0
        ult = float(c[-1])
        rompe = (ult > seg_h * 1.0 and alta) or (ult < seg_l * 1.0 and not alta)
        estado = "confirmado" if rompe and ((alta and ult > h[a:n - 1].max()) or (not alta and ult < l[a:n - 1].min())) else "em formação"
        vr = (df["Volume"].iloc[a:].mean() < df["Volume"].iloc[b:a].mean()) if "Volume" in df.columns and df["Volume"].iloc[b:a].mean() > 0 else None
        c_ = 35 + (15 if abs(mov) >= 0.15 else 0) + (10 if retr <= 0.38 else 0) + (10 if vr else 0) + (15 if estado == "confirmado" else 0)
        reg("Bandeira de alta" if alta else "Bandeira de baixa", "alta" if alta else "baixa", estado, b, n - 1,
            [f"Mastro de {fmt_num(abs(mov) * 100, 1)}% em {pl} candles ({'alta' if alta else 'queda'}).",
             f"Consolidação de {k} candles contra o movimento, devolvendo {fmt_num(retr * 100, 0)}% do mastro."] + (["Volume menor na consolidação."] if vr else []),
            c_, [f"Bandeira tem viés de {'alta' if alta else 'baixa'}: confirma ao fechar {'acima de ' + fmt_num(seg_h) if alta else 'abaixo de ' + fmt_num(seg_l)}.",
                 "Padrões de continuação falham com frequência; confirme com volume."],
            f"Fechamento {'abaixo de ' + fmt_num(seg_l) if alta else 'acima de ' + fmt_num(seg_h)}.",
            linhas=[(a, seg_h, n - 1, seg_h), (a, seg_l, n - 1, seg_l)], y0=seg_l, y1=seg_h)

    # ---- rompimento de consolidação (faixa estreita e saída com fechamento fora dela)
    if n >= 60:
        for k in (1, 2, 3):
            ref = slice(n - 1 - k - 20, n - 1 - k)
            if ref.start < 0:
                continue
            fh, fl = h[ref].max(), l[ref].min()
            amp = (fh - fl) / ((fh + fl) / 2)
            if amp > 0.12:
                continue
            ult = float(c[-1])
            lado = "alta" if ult > fh * 1.005 else "baixa" if ult < fl * 0.995 else None
            if lado and (c[n - 1 - k] <= fh * 1.005 if lado == "alta" else c[n - 1 - k] >= fl * 0.995):
                vr = volume_atual(df)
                forte = vr["disponivel"] and (vr["razao"] or 0) >= 1.5
                reg("Rompimento de consolidação", lado, "confirmado" if forte else "em formação", n - 21 - k, n - 1,
                    [f"Faixa de {fmt_num(amp * 100, 1)}% de amplitude por 20 candles ({fmt_num(fl)} a {fmt_num(fh)}).",
                     f"Fechamento em {fmt_num(ult)} fora da faixa, {'para cima' if lado == 'alta' else 'para baixo'}.",
                     "Com volume acima da média." if forte else "Sem confirmação de volume." if vr["disponivel"] else "Sem dado de volume para confirmar."],
                    45 + (25 if forte else 0) + (10 if k >= 2 else 0),
                    ["Rompimentos sem volume costumam falhar; observe se o preço se mantém fora da faixa nos próximos candles.",
                     f"Retorno ao interior da faixa ({fmt_num(fl)} a {fmt_num(fh)}) invalida."],
                    f"Fechamento de volta {'abaixo de ' + fmt_num(fh) if lado == 'alta' else 'acima de ' + fmt_num(fl)}.",
                    linhas=[(n - 21 - k, fh, n - 1, fh), (n - 21 - k, fl, n - 1, fl)], y0=fl, y1=fh)
                break

    # mantém no máximo 2 do mesmo nome, ordena por (confirmado primeiro, confiança)
    por: dict[str, list] = {}
    for p in sorted(pats, key=lambda p: -p["idx_fim"]):
        por.setdefault(p["nome"], []).append(p)
    pats = [p for lst in por.values() for p in lst[:2]]
    ordem = {"confirmado": 0, "em formação": 1, "invalidado": 2}
    return sorted(pats, key=lambda p: (ordem[p["estado"]], -p["confianca"]))[:8]


# =============================================================================== sinais
TIPOS_SINAL = {"tendencia_positiva": "Tendência positiva", "tendencia_negativa": "Tendência negativa", "possivel_rompimento": "Possível rompimento",
               "possivel_reversao": "Possível reversão", "sobrecompra": "Sobrecompra", "sobrevenda": "Sobrevenda",
               "volatilidade_elevada": "Volatilidade elevada", "sem_sinal": "Ausência de sinal claro"}


def _evid(n: int) -> str:
    return "alta" if n >= 4 else "média" if n == 3 else "baixa"


def rompimento_atual(df: pd.DataFrame, niveis: dict | None = None) -> dict | None:
    """Fechamento recente (últimos 3 candles) além de uma zona de resistência (alta) ou suporte (baixa) que antes continha o preço."""
    if df is None or len(df) < 40:
        return None
    niveis = niveis or suportes_resistencias(df)
    c = df["Close"].astype(float)
    ult = float(c.iloc[-1])
    vr = volume_atual(df)
    adx = None
    if _tem_hl(df):
        a, _ = tentar("ADX", df)
        adx = float(a["ADX"].iloc[-1]) if a is not None and _ok(a["ADX"].iloc[-1]) else None
    # zonas que o preço acabou de cruzar: olhamos as zonas calculadas ANTES dos últimos 3 candles
    ant = suportes_resistencias(df.iloc[:-3]) if len(df) >= 43 else {"suportes": [], "resistencias": []}
    for z in ant["resistencias"]:
        topo = z["zona"][1]
        if ult > topo * 1.003 and float(c.iloc[-4]) <= topo * 1.003:
            ev = [f"Fechamento em {fmt_num(ult)} acima da resistência de {fmt_num(topo)} ({z['toques']} toques)."]
            n = 1
            if vr["disponivel"] and (vr["razao"] or 0) >= 1.5:
                ev.append(f"Volume {fmt_num(vr['razao'], 1)}× a mediana recente."); n += 1
            if (c.iloc[-2:] > topo).all():
                ev.append("Dois fechamentos seguidos acima da zona."); n += 1
            if adx is not None and adx >= 20:
                ev.append(f"ADX de {fmt_num(adx, 1)} indica força direcional."); n += 1
            return {"direcao": 1, "zona": z, "nivel": topo, "evidencias": ev, "n": n, "volume": vr, "adx": adx}
    for z in ant["suportes"]:
        piso = z["zona"][0]
        if ult < piso * 0.997 and float(c.iloc[-4]) >= piso * 0.997:
            ev = [f"Fechamento em {fmt_num(ult)} abaixo do suporte de {fmt_num(piso)} ({z['toques']} toques)."]
            n = 1
            if vr["disponivel"] and (vr["razao"] or 0) >= 1.5:
                ev.append(f"Volume {fmt_num(vr['razao'], 1)}× a mediana recente."); n += 1
            if (c.iloc[-2:] < piso).all():
                ev.append("Dois fechamentos seguidos abaixo da zona."); n += 1
            if adx is not None and adx >= 20:
                ev.append(f"ADX de {fmt_num(adx, 1)} indica força direcional."); n += 1
            return {"direcao": -1, "zona": z, "nivel": piso, "evidencias": ev, "n": n, "volume": vr, "adx": adx}
    return None


def gerar_sinais(df: pd.DataFrame, ativo: str = "", classe: str = "acao", rotulo_periodo: str = "diário", moeda: str = "BRL",
                 trend: dict | None = None, niveis: dict | None = None, padroes: list | None = None) -> list[dict]:
    """Sinais técnicos explicados: ativo, indicadores, período, justificativa, dados, nível de evidência e o que os invalida.
    NUNCA emite 'compre' ou 'venda'. Sem dados suficientes devolve lista vazia."""
    if df is None or len(df) < 40:
        return []
    perfil = perfil_classe(classe, df)
    if not perfil["liberada"]:
        return []
    ult = float(df["Close"].iloc[-1])
    data = _dia(df.index[-1])
    periodo = f"{rotulo_periodo}, {len(df)} candles ({_dia(df.index[0])} a {data})"
    tr = trend or classificar_tendencia(df)
    niveis = niveis or suportes_resistencias(df)
    sinais: list[dict] = []

    def novo(tipo, direcao, indicadores, just, dados, conf, evid, total, invalida):
        sinais.append({"tipo": tipo, "titulo": TIPOS_SINAL[tipo], "ativo": ativo, "indicadores": indicadores, "periodo": periodo, "justificativa": just,
                       "dados": dados, "confianca": conf, "evidencia": evid, "total_criterios": total, "invalida": invalida, "direcao": direcao,
                       "data": data, "assinatura": f"{tipo}:{data}"})

    adx_v = tr.get("adx")
    if tr["tendencia"] in ("alta", "baixa"):
        up = tr["tendencia"] == "alta"
        pro = [x for x in tr["criterios"] if x["voto"] == (1 if up else -1)]
        longa = next((x["nome"] for x in tr["criterios"] if x["nome"].startswith("Preço ×")), "")
        m = re.search(r"média de (\d+)", longa)
        ml = float(df["Close"].rolling(int(m.group(1))).mean().iloc[-1]) if m else None
        topos, fundos = _pivos(df, _w_padrao(len(df)))
        ref = fundos[-1][1] if up and fundos else topos[-1][1] if (not up) and topos else None
        inv = []
        if ml is not None:
            inv.append(f"Fechamento {'abaixo' if up else 'acima'} da média de {m.group(1)} candles ({fmt_preco(ml, moeda)}).")
        if ref is not None:
            inv.append(f"{'Perda' if up else 'Superação'} do último {'fundo' if up else 'topo'} em {fmt_preco(ref, moeda)}.")
        novo("tendencia_positiva" if up else "tendencia_negativa", 1 if up else -1, [x["nome"] for x in pro],
             f"{len(pro)} de {len(tr['criterios'])} critérios independentes apontam {'alta' if up else 'baixa'}: " + " ".join(x["texto"] for x in pro),
             {"placar": tr["placar"], "adx": adx_v, "preco": ult}, tr["confianca"], len(pro), len(tr["criterios"]), inv)
    rp = rompimento_atual(df, niveis)
    if rp:
        up = rp["direcao"] == 1
        novo("possivel_rompimento", rp["direcao"], ["Suporte/resistência (pivôs)"] + (["Volume"] if rp["volume"]["disponivel"] else []) + (["ADX"] if rp["adx"] is not None else []),
             " ".join(rp["evidencias"]) + " Rompimentos podem ser falsos: observe se o preço se sustenta fora da zona.",
             {"nivel": rp["nivel"], "toques": rp["zona"]["toques"], "preco": ult}, _evid(rp["n"]), rp["n"], 4,
             [f"Fechamento de volta {'abaixo' if up else 'acima'} de {fmt_preco(rp['nivel'], moeda)}."])
    osc = leitura_osciladores(df)
    dv = divergencias(df)
    ext = osc["geral"] != "neutra"
    ev_rev, txt_rev = 0, []
    dire_rev = 0
    for d_ in dv[:2]:
        ev_rev += 1
        txt_rev.append(d_["texto"])
        dire_rev = 1 if d_["tipo"] == "altista" else -1
    if dv and ext and ((dire_rev == 1 and osc["geral"] == "sobrevenda") or (dire_rev == -1 and osc["geral"] == "sobrecompra")):
        ev_rev += 1
        txt_rev.append(f"Osciladores em {osc['geral']} ({osc['n_sobrecompra'] + osc['n_sobrevenda']} indicador(es)).")
    prox = [z for z in (niveis["suportes"][:1] if dire_rev == 1 else niveis["resistencias"][:1] if dire_rev == -1 else []) if abs(z["distancia_pct"]) <= 2.0]
    if dv and prox:
        ev_rev += 1
        txt_rev.append(f"Preço perto de {prox[0]['tipo'].lower()} de {fmt_preco(prox[0]['preco'], moeda)}.")
    if dv and ev_rev >= 2:
        novo("possivel_reversao", dire_rev, ["RSI" if any("RSI" in t for t in txt_rev) else "OBV"] + (["Osciladores"] if ext else []) + (["Suporte/resistência"] if prox else []),
             " ".join(txt_rev) + " Divergências avisam de perda de força; não determinam reversão.", {"divergencias": [d_["tipo"] for d_ in dv], "preco": ult},
             _evid(ev_rev + 1), ev_rev, 4,
             [f"Novo fundo/topo na mesma direção da tendência anterior (preço {'abaixo' if dire_rev == 1 else 'acima'} do último pivô).",
              "Tendência anterior se reestabelecendo com ADX subindo."])
    forte = adx_v is not None and adx_v >= 25
    if osc["n_sobrecompra"] or osc["n_sobrevenda"]:
        sobre = osc["n_sobrecompra"] >= osc["n_sobrevenda"]
        nome_z = "sobrecompra" if sobre else "sobrevenda"
        lista = [x for x in osc["itens"] if x["zona"] == nome_z]
        n_ = len(lista)
        txt = "; ".join(f"{x['indicador']} em {fmt_num(x['valor'], 1)}" for x in lista)
        extra = " Em tendência forte, a zona pode persistir por muito tempo." if (forte and ((sobre and tr["tendencia"] == "alta") or (not sobre and tr["tendencia"] == "baixa"))) else ""
        novo(nome_z, -1 if sobre else 1, [x["indicador"] for x in lista], f"{n_} oscilador(es) em {nome_z}: {txt}.{extra}",
             {x["indicador"]: x["valor"] for x in lista}, "alta" if n_ >= 3 else "média" if n_ == 2 else "baixa", n_, len(osc["itens"]),
             [f"Oscilador(es) voltando à zona neutra ({'abaixo' if sobre else 'acima'} do limite)." if True else ""])
    vol = volatilidade_atual(df)
    if vol["elevada"]:
        novo("volatilidade_elevada", 0, ["Desvio dos retornos"] + (["ATR"] if vol["atr_pct"] is not None else []), " ".join(vol["motivos"]),
             {k: v for k, v in vol.items() if k != "motivos"}, "média" if len(vol["motivos"]) == 1 else "alta", len(vol["motivos"]), 2,
             ["Razão de volatilidade voltando abaixo de 1,3 por vários candles."])
    if not any(s["tipo"] in ("tendencia_positiva", "tendencia_negativa", "possivel_rompimento", "possivel_reversao", "sobrecompra", "sobrevenda") for s in sinais):
        mot = tr.get("motivo") or "Tendência lateral ou critérios divergentes, sem rompimento, divergência ou extremo nos osciladores."
        novo("sem_sinal", 0, [x["nome"] for x in tr["criterios"]], mot, {"tendencia": tr["tendencia"], "placar": tr["placar"]}, "média", 0, len(tr["criterios"]),
             ["Um rompimento de zona, extremo de oscilador ou nova tendência alteraria a leitura."])
    return sinais


# =============================================================================== análise multitemporal
def analise_multitemporal(df: pd.DataFrame, freq: str | None = None) -> dict:
    """Mesmo ativo em curto (diário), médio (semanal) e longo prazo (mensal), a partir do histórico base. Diz se os períodos
    concordam ou divergem e o que isso significa e NÃO significa."""
    out = {"periodos": [], "concordancia": "insuficiente", "conclusao": "", "limites": []}
    if df is None or df.empty:
        out["conclusao"] = "Sem dados de preço."
        return out
    freq = freq or inferir_frequencia(df.index)
    quadros = []
    if freq == "intra":
        quadros = [("Curto prazo", "intraday", df, 60), ("Médio prazo", "diário", reamostrar(df, "D"), 40), ("Longo prazo", "semanal", None, 30)]
        dd = quadros[1][2]
        quadros[2] = ("Longo prazo", "semanal", reamostrar(dd, "W") if len(dd) else None, 30)
    elif freq == "D":
        quadros = [("Curto prazo", "diário", df, 60), ("Médio prazo", "semanal", reamostrar(df, "W"), 30), ("Longo prazo", "mensal", reamostrar(df, "M"), 24)]
    elif freq == "W":
        quadros = [("Médio prazo", "semanal", df, 30), ("Longo prazo", "mensal", reamostrar(df, "M"), 24)]
    else:
        quadros = [("Longo prazo", "mensal", df, 24)]
    for horizonte, rotulo, q, minimo in quadros:
        if q is None or len(q) == 0:
            out["periodos"].append({"horizonte": horizonte, "rotulo": rotulo, "tendencia": None, "motivo": "Sem candles neste período.", "candles": 0, "criterios": []})
            continue
        r = classificar_tendencia(q, min_candles=minimo)
        out["periodos"].append({"horizonte": horizonte, "rotulo": rotulo, "tendencia": r["tendencia"], "confianca": r["confianca"], "motivo": r["motivo"],
                                "candles": len(q), "criterios": r["criterios"], "placar": r["placar"], "parcial": bool(q.attrs.get("ultimo_parcial"))})
    val = [p for p in out["periodos"] if p["tendencia"]]
    ts = [p["tendencia"] for p in val]
    if len(val) < 2:
        out["conclusao"] = "Histórico insuficiente para comparar períodos: precisa de ao menos dois horizontes com dados."
        out["concordancia"] = "insuficiente"
    elif len(set(ts)) == 1:
        out["concordancia"] = {"alta": "concordam_alta", "baixa": "concordam_baixa", "lateral": "concordam_lateral"}[ts[0]]
        out["conclusao"] = (f"Os {len(val)} horizontes analisados concordam: tendência de {ts[0]}. Concordância entre períodos aumenta a robustez da leitura, "
                            "mas não garante continuidade.")
    else:
        out["concordancia"] = "divergem" if ("alta" in ts and "baixa" in ts) else "parcial"
        ordem = [(p["horizonte"].split()[0].lower(), p["rotulo"], p["tendencia"]) for p in val]
        desc = "; ".join(f"{h} ({r}): {t}" for h, r, t in ordem)
        if out["concordancia"] == "divergem":
            curto, longo = val[0], val[-1]
            if curto["tendencia"] == "baixa" and longo["tendencia"] == "alta":
                sig = "Pode ser correção dentro de uma tendência maior de alta, ou o início de uma reversão; só os próximos candles esclarecem."
            elif curto["tendencia"] == "alta" and longo["tendencia"] == "baixa":
                sig = "Pode ser repique dentro de uma tendência maior de baixa, ou o início de uma reversão; só os próximos candles esclarecem."
            else:
                sig = "Os horizontes apontam direções opostas: o cenário é de baixa clareza."
            out["conclusao"] = f"Períodos divergentes: {desc}. {sig}"
        else:
            out["conclusao"] = f"Períodos parcialmente alinhados: {desc}. Algum horizonte está lateral ou indefinido."
    out["limites"] = ["Semanal e mensal são derivados do histórico diário; períodos curtos de histórico reduzem a confiabilidade.",
                      "Tendência descreve o passado do preço e não prevê o futuro."]
    if any(p.get("parcial") for p in out["periodos"]):
        out["limites"].append("O último candle de algum período ainda não terminou.")
    return out


# =============================================================================== regras (backtest e alertas personalizados)
OPERADORES = {">": lambda a, b: a > b, "<": lambda a, b: a < b, ">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b}
OPS_ROTULO = {">": "maior que", "<": "menor que", ">=": "maior ou igual a", "<=": "menor ou igual a", "cruza_acima": "cruza para cima", "cruza_abaixo": "cruza para baixo"}


def operando(ind: str = "PRECO", params: dict | None = None, col: str | None = None, valor: float | None = None) -> dict:
    """Um lado de uma condição: número fixo, preço (Open/High/Low/Close) ou coluna de um indicador."""
    if valor is not None:
        return {"valor": float(valor)}
    return {"ind": ind, "params": dict(params or {}), "col": col}


def condicao(esq: dict, op: str, dir_: dict) -> dict:
    if op not in OPS_ROTULO:
        raise ValueError(f"Operador desconhecido: {op}")
    return {"esq": esq, "op": op, "dir": dir_}


def _serie_operando(df: pd.DataFrame, spec: dict, cache: dict) -> pd.Series:
    if "valor" in spec:
        return pd.Series(float(spec["valor"]), index=df.index)
    ind = spec.get("ind", "PRECO")
    if ind == "PRECO":
        col = spec.get("col") or "Close"
        if col not in df.columns:
            raise IndicadorIndisponivel(f"Sem a coluna {col}.")
        return df[col].astype(float)
    col = spec.get("col") or (INDICADORES[ind]["colunas"][0] if ind in INDICADORES else None)
    if ind not in INDICADORES or col not in INDICADORES[ind]["colunas"]:
        raise ValueError(f"Indicador/coluna inválido: {ind}/{col}")
    if col in COLUNAS_PROIBIDAS_BACKTEST:
        raise ValueError(f"{col} usa preços futuros e não pode ser usada em regras de simulação ou alerta.")
    chave = (ind, tuple(sorted((spec.get("params") or {}).items())))
    if chave not in cache:
        cache[chave] = calcular(ind, df, **(spec.get("params") or {}))
    return cache[chave][col].astype(float)


def avaliar_condicao(df: pd.DataFrame, cond: dict, cache: dict | None = None) -> pd.Series:
    """Série booleana (True onde a condição vale no FECHAMENTO do candle). Só usa dados até o próprio candle."""
    cache = {} if cache is None else cache
    a, b = _serie_operando(df, cond["esq"], cache), _serie_operando(df, cond["dir"], cache)
    op = cond["op"]
    if op in OPERADORES:
        r = OPERADORES[op](a, b)
    elif op == "cruza_acima":
        r = (a.shift(1) <= b.shift(1)) & (a > b)
    else:
        r = (a.shift(1) >= b.shift(1)) & (a < b)
    return (r & a.notna() & b.notna()).fillna(False).astype(bool)


def avaliar_regras(df: pd.DataFrame, regras: list[dict], cache: dict | None = None) -> pd.Series:
    """Todas as condições ao mesmo tempo (E lógico). Lista vazia = nunca."""
    if not regras:
        return pd.Series(False, index=df.index)
    cache = {} if cache is None else cache
    out = pd.Series(True, index=df.index)
    for r in regras:
        out &= avaliar_condicao(df, r, cache)
    return out


def descrever_condicao(c: dict) -> str:
    def lado(s):
        if "valor" in s:
            return fmt_num(s["valor"], 2)
        ind = s.get("ind", "PRECO")
        if ind == "PRECO":
            return {"Close": "Fechamento", "Open": "Abertura", "High": "Máxima", "Low": "Mínima"}.get(s.get("col") or "Close", "Fechamento")
        ps = ",".join(str(v) for v in (s.get("params") or {}).values())
        col = s.get("col") or INDICADORES[ind]["colunas"][0]
        return f"{col}({ps})" if ps else col
    return f"{lado(c['esq'])} {OPS_ROTULO[c['op']]} {lado(c['dir'])}"


def sinais_sem_futuro(df: pd.DataFrame, regras: list[dict], pontos: int = 6) -> list[str]:
    """Auditoria anti look-ahead: o sinal calculado com a série COMPLETA tem de ser igual ao calculado só com os dados até aquele
    candle. Devolve a lista de divergências (vazia = nenhum uso de informação futura detectado)."""
    cheio = avaliar_regras(df, regras)
    n = len(df)
    erros = []
    cortes = sorted({int(x) for x in np.linspace(max(60, n // 3), n - 2, pontos)}) if n > 70 else []
    for k in cortes:
        parcial = avaliar_regras(df.iloc[:k + 1], regras)
        if bool(parcial.iloc[-1]) != bool(cheio.iloc[k]):
            erros.append(f"Sinal em {_dia(df.index[k])} muda quando os dados futuros são removidos.")
    return erros


ESTRATEGIAS_PADRAO = {
    "cruz_sma": {"nome": "Cruzamento de médias (SMA 20/50)", "descricao": "Entra quando a SMA 20 cruza para cima da SMA 50 e sai quando cruza para baixo.",
                 "entrada": [condicao(operando("SMA", {"n": 20}), "cruza_acima", operando("SMA", {"n": 50}))],
                 "saida": [condicao(operando("SMA", {"n": 20}), "cruza_abaixo", operando("SMA", {"n": 50}))]},
    "rsi_rev": {"nome": "RSI de reversão (compra < 30, sai > 55)", "descricao": "Entra com RSI(14) abaixo de 30 e sai quando passa de 55.",
                "entrada": [condicao(operando("RSI", {"n": 14}), "<", operando(valor=30))], "saida": [condicao(operando("RSI", {"n": 14}), ">", operando(valor=55))]},
    "macd": {"nome": "MACD cruza a linha de sinal", "descricao": "Entra quando o MACD cruza para cima do sinal e sai no cruzamento para baixo.",
             "entrada": [condicao(operando("MACD", col="MACD"), "cruza_acima", operando("MACD", col="MACD_SINAL"))],
             "saida": [condicao(operando("MACD", col="MACD"), "cruza_abaixo", operando("MACD", col="MACD_SINAL"))]},
    "donchian": {"nome": "Rompimento de máxima de 20 (Donchian)", "descricao": "Entra ao fechar acima da máxima dos 20 candles anteriores e sai ao fechar abaixo da mínima dos 10 anteriores.",
                 "entrada": [condicao(operando("PRECO", col="Close"), ">", operando("DONCHIAN", {"n": 20}, col="DON_ALTO"))],
                 "saida": [condicao(operando("PRECO", col="Close"), "<", operando("DONCHIAN", {"n": 10}, col="DON_BAIXO"))]},
    "boll_rev": {"nome": "Bollinger de reversão", "descricao": "Entra quando o fechamento fica abaixo da banda inferior e sai ao voltar à média.",
                 "entrada": [condicao(operando("PRECO", col="Close"), "<", operando("BOLLINGER", col="BOLL_INF"))],
                 "saida": [condicao(operando("PRECO", col="Close"), ">", operando("BOLLINGER", col="BOLL_MEDIA"))]},
}


# =============================================================================== backtest
def custos_padrao(classe: str) -> dict:
    """Custos iniciais EDITÁVEIS (estimativas; confira na sua corretora/exchange). Imposto de renda NÃO é simulado."""
    if classe == "cripto":
        return {"corretagem_fixa": 0.0, "corretagem_pct": 0.10, "emolumentos_pct": 0.0, "slippage_pct": 0.05, "max_participacao_pct": 10.0}
    return {"corretagem_fixa": 0.0, "corretagem_pct": 0.0, "emolumentos_pct": 0.033, "slippage_pct": 0.05, "max_participacao_pct": 10.0}


def _anualizar(ret_total: float, dias: float):
    if dias <= 0 or ret_total <= -1:
        return None
    return (1 + ret_total) ** (365.25 / dias) - 1


def _max_dd(eq: pd.Series) -> float:
    if len(eq) == 0:
        return 0.0
    return float(((eq / eq.cummax()) - 1).min())


def _periodos_ano(freq: str, classe: str):
    return {"D": 365 if classe == "cripto" else 252, "W": 52, "M": 12}.get(freq)


def _metricas(eq: pd.Series, trades: list[dict], freq: str, classe: str, rf_anual: float) -> dict:
    out = {"retorno_pct": None, "anualizado_pct": None, "anualizacao_curta": False, "drawdown_max_pct": None, "n_operacoes": len(trades),
           "taxa_acerto_pct": None, "payoff": None, "fator_lucro": None, "sharpe": None, "retorno_dd": None, "tempo_no_mercado_pct": None,
           "expectativa_pct": None}
    if len(eq) < 2:
        return out
    r_tot = float(eq.iloc[-1] / eq.iloc[0] - 1)
    dias = (eq.index[-1] - eq.index[0]).days
    out["retorno_pct"] = r_tot * 100
    an = _anualizar(r_tot, dias)
    out["anualizado_pct"] = None if an is None else an * 100
    out["anualizacao_curta"] = dias < 365
    dd = _max_dd(eq)
    out["drawdown_max_pct"] = dd * 100
    if an is not None and dd < 0:
        out["retorno_dd"] = an / abs(dd)
    if trades:
        gan = [t["pnl"] for t in trades if t["pnl"] > 0]
        per = [-t["pnl"] for t in trades if t["pnl"] < 0]
        out["taxa_acerto_pct"] = len(gan) / len(trades) * 100
        if gan and per:
            out["payoff"] = (np.mean(gan)) / (np.mean(per))
        out["fator_lucro"] = (sum(gan) / sum(per)) if per else (None if not gan else float("inf"))
        out["expectativa_pct"] = float(np.mean([t["retorno_pct"] for t in trades]))
    ppy = _periodos_ano(freq, classe)
    rets = eq.pct_change().dropna()
    if ppy and len(rets) >= 30 and float(rets.std()) > 0:
        rf_p = (1 + rf_anual) ** (1 / ppy) - 1
        out["sharpe"] = float((rets.mean() - rf_p) / rets.std() * math.sqrt(ppy))
    return out


def backtest(df: pd.DataFrame, estrategia: dict, capital: float = 10_000.0, custos: dict | None = None, classe: str = "acao",
             proventos: pd.Series | None = None, ajustado: bool | None = None, de=None, ate=None, benchmark: pd.Series | None = None,
             rf_anual: float = 0.0, dividir: float | None = None, fracionario: bool | None = None, exposicao: float = 1.0) -> dict:
    """Simulação histórica de uma estratégia comprada (long-only) em UM ativo.

    Sem informação futura: o sinal é calculado no FECHAMENTO do candle t (só com dados até t) e a ordem é executada na ABERTURA do
    candle t+1 (sem abertura na série, no fechamento de t+1). Indicadores são causais (verificado por `sinais_sem_futuro`).
    Considera corretagem, emolumentos, slippage, limite de participação no volume do candle e proventos (quando os preços NÃO
    estão ajustados). Stop e alvo, se definidos, usam máxima/mínima e abertura do candle (gap respeitado; stop vence se ambos).
    NÃO simula imposto de renda e só testa o ativo atual (viés de sobrevivência: ativos que deixaram de existir não aparecem)."""
    avisos = [AVISO_BACKTEST,
              "Viés de sobrevivência: só o ativo atual foi testado; ativos que deixaram de existir, mudaram de nome ou foram excluídos não entram.",
              "Imposto de renda não foi considerado."]
    res = {"ok": False, "motivo": None, "metricas": None, "trades": [], "equity": None, "benchmark": None, "amostras": None, "avisos": avisos,
           "custos": None, "execucao": None, "liquidez": {"reduzidas": 0, "bloqueadas": 0}, "posicao_aberta": None, "estrategia": estrategia.get("nome")}
    if df is None or len(df) < 60:
        res["motivo"] = "Histórico insuficiente (mínimo de 60 candles)."
        return res
    perfil = perfil_classe(classe, df)
    if not perfil["liberada"]:
        res["motivo"] = perfil["motivo"]
        return res
    try:
        cache: dict = {}
        ent = avaliar_regras(df, estrategia.get("entrada") or [], cache)
        sai = avaliar_regras(df, estrategia.get("saida") or [], cache)
    except (IndicadorIndisponivel, ValueError) as e:
        res["motivo"] = str(e)
        return res
    if not estrategia.get("entrada"):
        res["motivo"] = "Defina ao menos uma condição de entrada."
        return res
    cs = {**custos_padrao(classe), **(custos or {})}
    res["custos"] = cs
    tem_open = "Open" in df.columns
    tem_hl = _tem_hl(df)
    stop_pct, alvo_pct = estrategia.get("stop_pct"), estrategia.get("alvo_pct")
    max_c = estrategia.get("max_candles")
    if (stop_pct or alvo_pct) and not tem_hl:
        avisos.append("Sem máxima/mínima nesta série: stop e alvo foram ignorados.")
        stop_pct = alvo_pct = None
    res["execucao"] = "abertura do candle seguinte ao sinal" if tem_open else "fechamento do candle seguinte ao sinal (série sem abertura)"
    if ajustado:
        avisos.append("Preços ajustados por proventos: o retorno de preço já embute os proventos reinvestidos (não são creditados à parte).")
    fracionario = (classe == "cripto") if fracionario is None else fracionario
    n = len(df)
    i0 = 0
    if de is not None:
        i0 = int(df.index.searchsorted(pd.Timestamp(de)))
    i1 = n - 1 if ate is None else int(df.index.searchsorted(pd.Timestamp(ate), side="right")) - 1
    if i1 - i0 < 40:
        res["motivo"] = "Período de teste muito curto (menos de 40 candles)."
        return res
    O = df["Open"].to_numpy(float) if tem_open else df["Close"].to_numpy(float)
    H = df["High"].to_numpy(float) if tem_hl else None
    L = df["Low"].to_numpy(float) if tem_hl else None
    C = df["Close"].to_numpy(float)
    V = df["Volume"].to_numpy(float) if "Volume" in df.columns else None
    prov = None
    if proventos is not None and len(proventos) and not ajustado:
        pv = pd.Series(proventos).dropna()
        pv.index = pd.DatetimeIndex(pv.index).tz_localize(None) if getattr(pv.index, "tz", None) else pd.DatetimeIndex(pv.index)
        prov = pv.groupby(pv.index.normalize()).sum()
    slip, fixa = cs["slippage_pct"] / 100, cs["corretagem_fixa"]
    taxa = (cs["corretagem_pct"] + cs["emolumentos_pct"]) / 100
    lim = cs["max_participacao_pct"] / 100

    def cap_vol(i):
        if V is None or not _ok(V[i]) or lim <= 0:
            return None
        return lim * V[i]

    caixa, qtd = float(capital), 0.0
    pend = None
    trade = None
    trades: list[dict] = []
    eq = np.full(n, np.nan)
    em_mercado = 0
    bloq = reduz = 0

    def comprar(i, preco_base):
        nonlocal caixa, qtd, trade, bloq, reduz
        p = preco_base * (1 + slip)
        orcamento = caixa * exposicao
        q = (orcamento - fixa) / (p * (1 + taxa)) if orcamento > fixa else 0.0
        if not fracionario:
            q = math.floor(q)
        cap = cap_vol(i)
        if cap is not None and q > cap:
            q = cap if fracionario else math.floor(cap)
            reduz += 1
        if q <= 0:
            bloq += 1
            return False
        custo = fixa + q * p * taxa
        caixa -= q * p + custo
        qtd = q
        trade = {"entrada_data": _dia(df.index[i]), "entrada_idx": i, "entrada_preco": p, "qtd": q, "custo": custo, "recebido": 0.0, "qtd_saida": 0.0,
                 "motivo_saida": None, "proventos": 0.0, "stop": p * (1 - stop_pct / 100) if stop_pct else None,
                 "alvo": p * (1 + alvo_pct / 100) if alvo_pct else None}
        return True

    def vender(i, preco_base, motivo):
        nonlocal caixa, qtd, trade, pend, reduz
        p = preco_base * (1 - slip)
        q = qtd
        cap = cap_vol(i)
        if cap is not None and q > cap:
            q = cap
            reduz += 1
        custo = fixa + q * p * taxa
        caixa += q * p - custo
        qtd -= q
        trade["custo"] += custo
        trade["recebido"] += q * p
        trade["qtd_saida"] += q
        trade["motivo_saida"] = trade["motivo_saida"] or motivo
        if qtd <= 1e-12:
            qtd = 0.0
            base = trade["entrada_preco"] * trade["qtd"]
            pnl = trade["recebido"] - base - trade["custo"] + trade["proventos"]
            trades.append({"entrada_data": trade["entrada_data"], "entrada_preco": float(trade["entrada_preco"]), "saida_data": _dia(df.index[i]),
                           "saida_preco": float(trade["recebido"] / trade["qtd_saida"]), "qtd": float(trade["qtd"]), "custos": float(trade["custo"]),
                           "proventos": float(trade["proventos"]), "pnl": float(pnl), "retorno_pct": float(pnl / base * 100),
                           "dias": int((df.index[i] - pd.Timestamp(trade["entrada_data"])).days), "motivo_saida": trade["motivo_saida"]})
            trade = None
            pend = None
        else:
            pend = "saida"          # sobrou posição por limite de liquidez: continua saindo nos candles seguintes

    for i in range(i0, i1 + 1):
        if pend == "entrada" and qtd == 0 and i > i0:
            comprar(i, O[i])
            pend = None
        elif pend == "saida" and qtd > 0 and i > i0:
            vender(i, O[i], trade["motivo_saida"] or "regra de saída")
        if qtd > 0 and prov is not None and df.index[i].normalize() in prov.index and trade is not None and trade["entrada_idx"] < i:
            val = float(prov.loc[df.index[i].normalize()]) * qtd
            caixa += val
            trade["proventos"] += val
        if qtd > 0 and tem_hl and trade is not None and (trade["stop"] or trade["alvo"]):
            st_, al_ = trade["stop"], trade["alvo"]
            if al_ and O[i] >= al_:
                vender(i, O[i], "alvo")
            elif st_ and O[i] <= st_:
                vender(i, O[i], "stop")
            elif st_ and L[i] <= st_:
                vender(i, st_, "stop")
            elif al_ and H[i] >= al_:
                vender(i, al_, "alvo")
        if qtd > 0 and max_c and trade is not None and (i - trade["entrada_idx"]) >= int(max_c) and pend is None:
            pend = "saida"
            trade["motivo_saida"] = "prazo máximo"
        eq[i] = caixa + qtd * C[i]
        if qtd > 0:
            em_mercado += 1
        if i < i1:                                     # decisão no fechamento de i → ordem para o candle i+1
            if qtd == 0 and pend is None and bool(ent.iloc[i]):
                pend = "entrada"
            elif qtd > 0 and pend is None and bool(sai.iloc[i]) and (estrategia.get("saida")):
                pend = "saida"
                trade["motivo_saida"] = "regra de saída"
    serie = pd.Series(eq[i0:i1 + 1], index=df.index[i0:i1 + 1]).dropna()
    freq = inferir_frequencia(serie.index)
    res["equity"] = serie
    res["trades"] = trades
    res["liquidez"] = {"reduzidas": int(reduz), "bloqueadas": int(bloq)}
    if bloq or reduz:
        avisos.append(f"Liquidez: {reduz} ordem(ns) reduzida(s) e {bloq} não executada(s) por exceder {fmt_num(cs['max_participacao_pct'], 0)}% do volume do candle.")
    if qtd > 0 and trade is not None:
        mtm = qtd * C[i1] - trade["entrada_preco"] * trade["qtd"]
        res["posicao_aberta"] = {"entrada_data": trade["entrada_data"], "entrada_preco": trade["entrada_preco"], "qtd": qtd, "resultado_aberto": mtm}
    m = _metricas(serie, trades, freq, classe, rf_anual)
    m["tempo_no_mercado_pct"] = em_mercado / max(1, len(serie)) * 100
    res["metricas"] = m
    # comprar e manter (mesmos custos de uma entrada e uma saída) e benchmark externo
    try:
        p0 = O[i0 + 1] * (1 + slip) if i0 + 1 <= i1 else C[i0]
        q0 = (capital - fixa) / (p0 * (1 + taxa))
        q0 = q0 if fracionario else math.floor(q0)
        bh = pd.Series(capital - q0 * p0 - (fixa + q0 * p0 * taxa) + q0 * C[i0:i1 + 1], index=df.index[i0:i1 + 1])
        bh.iloc[0] = capital
        bh_m = _metricas(bh, [], freq, classe, rf_anual)
        res["benchmark"] = {"comprar_e_manter": {"retorno_pct": bh_m["retorno_pct"], "anualizado_pct": bh_m["anualizado_pct"], "drawdown_max_pct": bh_m["drawdown_max_pct"],
                                                  "sharpe": bh_m["sharpe"], "serie": bh}}
        if benchmark is not None and len(benchmark):
            b = pd.Series(benchmark).dropna()
            b.index = pd.DatetimeIndex(b.index).tz_localize(None) if getattr(b.index, "tz", None) else pd.DatetimeIndex(b.index)
            b = b[(b.index >= serie.index[0]) & (b.index <= serie.index[-1])]
            if len(b) >= 2:
                bm = _metricas(b / b.iloc[0] * capital, [], inferir_frequencia(b.index), classe, rf_anual)
                res["benchmark"]["referencia"] = {"retorno_pct": bm["retorno_pct"], "anualizado_pct": bm["anualizado_pct"], "drawdown_max_pct": bm["drawdown_max_pct"]}
    except Exception:
        pass
    if dividir and 0.4 <= dividir <= 0.9 and len(serie) >= 80:
        k = int(len(serie) * dividir)
        corte = serie.index[k]
        dentro, fora = serie.iloc[:k + 1], serie.iloc[k:]
        t_in = [t for t in trades if pd.Timestamp(t["entrada_data"]) < corte]
        t_out = [t for t in trades if pd.Timestamp(t["entrada_data"]) >= corte]
        res["amostras"] = {"corte": _dia(corte), "dentro": _metricas(dentro, t_in, freq, classe, rf_anual), "fora": _metricas(fora, t_out, freq, classe, rf_anual),
                           "aviso": "Se os parâmetros foram escolhidos olhando o período inteiro, a 'amostra de fora' também já foi vista e não é um teste independente."}
    if len(trades) < 10:
        avisos.append(f"Poucas operações ({len(trades)}): as métricas têm pouco valor estatístico.")
    res["ok"] = True
    return res


def comparar_estrategias(df: pd.DataFrame, estrategias: list[dict], **kw) -> dict:
    """Roda várias estratégias com os mesmos dados e custos. Devolve {'linhas': [...], 'resultados': [...]}; não elege 'melhor'."""
    resultados = [backtest(df, e, **kw) for e in estrategias]
    linhas = []
    for e, r in zip(estrategias, resultados):
        m = r["metricas"] or {}
        linhas.append({"estrategia": e.get("nome"), "ok": r["ok"], "motivo": r["motivo"], "retorno_pct": m.get("retorno_pct"), "anualizado_pct": m.get("anualizado_pct"),
                       "drawdown_max_pct": m.get("drawdown_max_pct"), "n_operacoes": m.get("n_operacoes"), "taxa_acerto_pct": m.get("taxa_acerto_pct"),
                       "sharpe": m.get("sharpe"), "retorno_dd": m.get("retorno_dd")})
    return {"linhas": linhas, "resultados": resultados}


# =============================================================================== alertas técnicos
TIPOS_ALERTA_TEC = {"cruz_medias": "Cruzamento de médias", "rsi_zona": "RSI em região configurada", "macd_cruz": "Cruzamento do MACD",
                    "rompe_sr": "Rompimento de suporte ou resistência", "volume_alto": "Aumento de volume", "mudanca_tendencia": "Mudança de tendência",
                    "volatilidade": "Aumento de volatilidade", "padrao": "Formação de padrão", "personalizada": "Condição personalizada"}
PERIODOS_ALERTA = {"D": "Diário", "W": "Semanal", "M": "Mensal"}
CANAIS = {"app": "No aplicativo"}          # e-mail e push dependem de um serviço externo (não existe neste app)
PADROES_PARAMS = {
    "cruz_medias": {"tipo_media": "SMA", "rapida": 9, "lenta": 21, "direcao": "ambas"},
    "rsi_zona": {"n": 14, "sobrecompra": 70, "sobrevenda": 30, "zona": "ambas"},
    "macd_cruz": {"rapida": 12, "lenta": 26, "sinal": 9, "direcao": "ambas"},
    "rompe_sr": {},
    "volume_alto": {"razao": 2.0},
    "mudanca_tendencia": {"candles_atras": 3},
    "volatilidade": {"razao": 1.8},
    "padrao": {"min_confianca": 60, "confirmados": False},
    "personalizada": {"nome": "Condição personalizada", "condicao": None},
}


def nova_regra_tec(tipo: str, ativo: str = "*", params: dict | None = None, periodo: str = "D", frequencia: str = "diaria", canal: str = "app",
                   prioridade: str = "media", ativa: bool = True, id_: str | None = None) -> dict:
    """Valida e normaliza uma regra de alerta técnico. Levanta ValueError com mensagem clara para parâmetros inválidos."""
    if tipo not in TIPOS_ALERTA_TEC:
        raise ValueError(f"Tipo de alerta desconhecido: {tipo}")
    if periodo not in PERIODOS_ALERTA:
        raise ValueError("Período deve ser diário, semanal ou mensal.")
    if frequencia not in I.FREQUENCIAS:
        raise ValueError("Frequência inválida.")
    if canal not in CANAIS:
        raise ValueError("Canal indisponível: hoje só há avisos dentro do aplicativo.")
    p = {**PADROES_PARAMS[tipo], **(params or {})}
    if tipo in ("cruz_medias", "macd_cruz"):
        if int(p["rapida"]) >= int(p["lenta"]):
            raise ValueError("A média rápida deve ser menor que a lenta.")
        if p["direcao"] not in ("ambas", "alta", "baixa"):
            raise ValueError("Direção inválida.")
    if tipo == "cruz_medias" and p["tipo_media"] not in ("SMA", "EMA"):
        raise ValueError("Tipo de média deve ser SMA ou EMA.")
    if tipo == "rsi_zona":
        if not (0 < float(p["sobrevenda"]) < float(p["sobrecompra"]) < 100):
            raise ValueError("No RSI, sobrevenda deve ser menor que sobrecompra, entre 0 e 100.")
        if p["zona"] not in ("ambas", "sobrecompra", "sobrevenda"):
            raise ValueError("Zona inválida.")
    if tipo in ("volume_alto", "volatilidade") and not float(p["razao"]) > 1:
        raise ValueError("A razão deve ser maior que 1.")
    if tipo == "mudanca_tendencia" and not 1 <= int(p["candles_atras"]) <= 20:
        raise ValueError("Compare com 1 a 20 candles atrás.")
    if tipo == "padrao" and not 0 <= float(p["min_confianca"]) <= 100:
        raise ValueError("Confiança mínima entre 0 e 100.")
    if tipo == "personalizada":
        c = p.get("condicao")
        if not isinstance(c, dict) or "esq" not in c or "dir" not in c or c.get("op") not in OPS_ROTULO:
            raise ValueError("Informe a condição (indicador, operador e valor).")
    a = re.sub(r"[^A-Za-z0-9.*\-/]", "", str(ativo or "*")).upper()[:24] or "*"
    base = f"{tipo}:{a}:{periodo}:" + ",".join(f"{k}={v}" for k, v in sorted(p.items()) if k != "nome")
    rid = id_ or re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:90]
    return {"id": rid, "tipo": tipo, "ativo": a, "params": p, "periodo": periodo, "frequencia": frequencia, "canal": canal,
            "prioridade": prioridade if prioridade in I.PRIORIDADES else "media", "ativa": bool(ativa)}


def descrever_regra_tec(r: dict) -> str:
    p, t = r["params"], r["tipo"]
    per = PERIODOS_ALERTA[r["periodo"]].lower()
    det = {"cruz_medias": lambda: f"{p['tipo_media']} {p['rapida']} × {p['lenta']} ({p['direcao']})", "rsi_zona": lambda: f"RSI({p['n']}) ≥ {p['sobrecompra']} ou ≤ {p['sobrevenda']} ({p['zona']})",
           "macd_cruz": lambda: f"MACD({p['rapida']},{p['lenta']},{p['sinal']}) cruza o sinal ({p['direcao']})", "rompe_sr": lambda: "fechamento além de suporte/resistência",
           "volume_alto": lambda: f"volume ≥ {fmt_num(p['razao'], 1)}× a mediana", "mudanca_tendencia": lambda: f"tendência diferente de {p['candles_atras']} candles atrás",
           "volatilidade": lambda: f"volatilidade 20/120 ≥ {fmt_num(p['razao'], 1)}", "padrao": lambda: f"padrão com confiança ≥ {p['min_confianca']}" + (" (só confirmados)" if p.get("confirmados") else ""),
           "personalizada": lambda: (p.get("nome") or "") + ": " + (descrever_condicao(p["condicao"]) if p.get("condicao") else "")}[t]()
    return f"{TIPOS_ALERTA_TEC[t]} · {det} · {per}"


def _ultimo_evento(ev: pd.Series, recentes: int):
    """Data do evento mais recente nos últimos `recentes` candles (ou None)."""
    j = ev.iloc[-recentes:]
    return j[j].index[-1] if bool(j.any()) else None


def avaliar_alertas_tec(regras: list[dict], series: dict, agora: datetime | None = None, recentes: int = 3) -> tuple[list[dict], list[str]]:
    """Avalia as regras ativas. `series` = {ativo: {'df': OHLCV diário, 'classe': 'acao'|...}}. Cada disparo registra QUANDO a condição
    foi detectada (data do candle) e usa uma assinatura por candle, então o mesmo evento não vira dois alertas. Devolve (disparos, avisos).
    Os disparos têm o formato dos alertas da Central (Passo 13): o app aplica `intel.filtrar_repetidos` para a frequência."""
    agora = agora or datetime.now()
    out, avisos = [], []
    cache_per: dict = {}

    def quadro(ativo, per):
        k = (ativo, per)
        if k not in cache_per:
            d = series[ativo]["df"]
            cache_per[k] = d if per == "D" else reamostrar(d, per)
        return cache_per[k]

    for r in regras or []:
        if not r.get("ativa", True):
            continue
        alvos = [a for a in series if r["ativo"] == "*" or str(a).upper() == r["ativo"]]
        for a in alvos:
            try:
                d = quadro(a, r["periodo"])
                cl = series[a].get("classe", "acao")
                perfil = perfil_classe(cl, d)
                if not perfil["liberada"] or len(d) < 40:
                    avisos.append(f"{a}: sem dados suficientes ou análise técnica não aplicável ({ROTULO_CLASSE.get(cl, cl)}).")
                    continue
                for dsp in _avaliar_uma(r, a, d, cl, agora, recentes):
                    out.append(dsp)
            except (IndicadorIndisponivel, ValueError) as e:
                avisos.append(f"{a}: {e}")
    return sorted(out, key=lambda x: (I.PRIORIDADES.get(x["prioridade"], 3), x["ativo"])), avisos


def _avaliar_uma(r: dict, a: str, d: pd.DataFrame, cl: str, agora: datetime, recentes: int) -> list[dict]:
    t, P, per = r["tipo"], r["params"], PERIODOS_ALERTA[r["periodo"]].lower()
    res = []

    def disp(candle, titulo, texto, valor, chave, dados=None):
        res.append({"regra_id": r["id"], "ativo": a, "tipo": r["tipo"], "prioridade": r["prioridade"], "titulo": titulo, "texto": texto, "valor": valor,
                    "assinatura": f"{chave}:{_dia(candle)}", "data": agora.isoformat(timespec="minutes"), "detectado_em": _dia(candle),
                    "periodo": per, "canal": r["canal"], "dados": dados or {}})

    if t == "cruz_medias":
        k = "EMA" if P["tipo_media"] == "EMA" else "SMA"
        f, s = calcular(k, d, n=int(P["rapida"]))[k], calcular(k, d, n=int(P["lenta"]))[k]
        up = (f.shift(1) <= s.shift(1)) & (f > s)
        dn = (f.shift(1) >= s.shift(1)) & (f < s)
        for nome, ev, ok_ in (("alta", up, P["direcao"] in ("ambas", "alta")), ("baixa", dn, P["direcao"] in ("ambas", "baixa"))):
            c = _ultimo_evento(ev, recentes) if ok_ else None
            if c is not None:
                disp(c, f"{a}: {k} {P['rapida']} cruzou {'para cima' if nome == 'alta' else 'para baixo'} da {k} {P['lenta']} ({per})",
                     f"Em {_dia(c)}, a {k} de {P['rapida']} candles cruzou {'acima' if nome == 'alta' else 'abaixo'} da de {P['lenta']}. Cruzamento isolado não confirma tendência.",
                     float(f.loc[c]), f"cruz:{nome}")
    elif t == "rsi_zona":
        rsi = calcular("RSI", d, n=int(P["n"]))["RSI"]
        sc, sv = float(P["sobrecompra"]), float(P["sobrevenda"])
        for nome, ev, ok_ in (("sobrecompra", (rsi >= sc) & (rsi.shift(1) < sc), P["zona"] in ("ambas", "sobrecompra")),
                              ("sobrevenda", (rsi <= sv) & (rsi.shift(1) > sv), P["zona"] in ("ambas", "sobrevenda"))):
            c = _ultimo_evento(ev.fillna(False), recentes) if ok_ else None
            if c is not None:
                disp(c, f"{a}: RSI entrou em {nome} ({per})", f"O RSI({P['n']}) ficou em {fmt_num(rsi.loc[c], 1)} em {_dia(c)}, "
                     f"{'acima' if nome == 'sobrecompra' else 'abaixo'} de {fmt_num(sc if nome == 'sobrecompra' else sv, 0)}. Em tendência forte, a zona pode persistir.", float(rsi.loc[c]), f"rsi:{nome}")
    elif t == "macd_cruz":
        m = calcular("MACD", d, rapida=int(P["rapida"]), lenta=int(P["lenta"]), sinal=int(P["sinal"]))
        up = (m["MACD"].shift(1) <= m["MACD_SINAL"].shift(1)) & (m["MACD"] > m["MACD_SINAL"])
        dn = (m["MACD"].shift(1) >= m["MACD_SINAL"].shift(1)) & (m["MACD"] < m["MACD_SINAL"])
        for nome, ev, ok_ in (("alta", up, P["direcao"] in ("ambas", "alta")), ("baixa", dn, P["direcao"] in ("ambas", "baixa"))):
            c = _ultimo_evento(ev.fillna(False), recentes) if ok_ else None
            if c is not None:
                disp(c, f"{a}: MACD cruzou {'para cima' if nome == 'alta' else 'para baixo'} da linha de sinal ({per})",
                     f"Em {_dia(c)} o MACD cruzou {'acima' if nome == 'alta' else 'abaixo'} do sinal. É um indício de mudança de momento, não de tendência.", float(m["MACD"].loc[c]), f"macd:{nome}")
    elif t == "rompe_sr":
        rp = rompimento_atual(d)
        if rp:
            lado = "resistência" if rp["direcao"] == 1 else "suporte"
            disp(d.index[-1], f"{a}: possível rompimento de {lado} ({per})", " ".join(rp["evidencias"]), float(rp["nivel"]), f"sr:{rp['direcao']}:{round(rp['nivel'], 2)}")
    elif t == "volume_alto":
        if "Volume" not in d.columns:
            raise IndicadorIndisponivel("sem volume confiável nesta série.")
        med = d["Volume"].rolling(20).median().shift(1)
        raz = d["Volume"] / med
        c = _ultimo_evento((raz >= float(P["razao"])).fillna(False), recentes)
        if c is not None:
            disp(c, f"{a}: volume {fmt_num(raz.loc[c], 1)}× a mediana ({per})", f"Em {_dia(c)} o volume foi {fmt_num(raz.loc[c], 1)}× a mediana dos 20 candles anteriores.", float(raz.loc[c]), "vol")
    elif t == "mudanca_tendencia":
        k = int(P["candles_atras"])
        agora_t, antes_t = classificar_tendencia(d), classificar_tendencia(d.iloc[:-k])
        if agora_t["tendencia"] and antes_t["tendencia"] and agora_t["tendencia"] != antes_t["tendencia"]:
            disp(d.index[-1], f"{a}: tendência passou de {antes_t['tendencia']} para {agora_t['tendencia']} ({per})",
                 f"Há {k} candles a leitura era de {antes_t['tendencia']}; agora é {agora_t['tendencia']} (confiança {agora_t['confianca']}). "
                 "A leitura usa vários critérios, mas pode oscilar perto dos limites.", float(agora_t["placar"] or 0), f"tend:{antes_t['tendencia']}>{agora_t['tendencia']}")
    elif t == "volatilidade":
        v = volatilidade_atual(d)
        if v["razao_20_120"] is not None and v["razao_20_120"] >= float(P["razao"]):
            disp(d.index[-1], f"{a}: volatilidade {fmt_num(v['razao_20_120'], 1)}× a normal ({per})", " ".join(v["motivos"]), float(v["razao_20_120"]), "volat")
    elif t == "padrao":
        n = len(d)
        for pt in detectar_padroes(d):
            if pt["idx_fim"] >= n - 1 - max(recentes, 5) and pt["confianca"] >= float(P["min_confianca"]) and pt["estado"] != "invalidado" \
                    and (not P.get("confirmados") or pt["estado"] == "confirmado"):
                disp(d.index[pt["idx_fim"]], f"{a}: {pt['nome']} {pt['estado']} ({per})", f"{pt['nome']} ({pt['estado']}, confiança {pt['confianca_rotulo']}): " + " ".join(pt["criterios"][:2]),
                     float(pt["confianca"]), f"pad:{pt['nome']}:{pt['estado']}")
    elif t == "personalizada":
        c = P["condicao"]
        ev = avaliar_condicao(d, c)
        cc = _ultimo_evento(ev, recentes)
        if cc is not None:
            disp(cc, f"{a}: {P.get('nome') or 'condição personalizada'} ({per})", f"Condição atendida em {_dia(cc)}: {descrever_condicao(c)}.", float(d['Close'].loc[cc]), "pers")
    return res


# =============================================================================== resumo técnico (base da IA, da carteira e do relatório)
def _classe_tec(classe: str) -> str:
    return "acao" if classe in ("bdr", "acao") else classe if classe in CLASSES else "acao"


def _lim(x):
    if isinstance(x, (np.floating, np.integer)):
        return x.item()
    if isinstance(x, dict):
        return {k: _lim(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_lim(v) for v in x]
    return x


def resumo_tecnico(df: pd.DataFrame, classe: str = "acao", ativo: str = "", meta: dict | None = None, moeda: str = "BRL", rotulo_periodo: str = "diário") -> dict:
    """Leitura técnica completa e serializável de um ativo: é o que o assistente do Passo 13, a carteira e o relatório consomem.
    Só usa dados reais passados em `df`; campos sem dado ficam None e há `avisos` dizendo por quê."""
    classe = _classe_tec(classe)
    d, rel = limpar_ohlcv(df)
    out = {"ativo": ativo, "classe": classe, "moeda": moeda, "disponivel": False, "avisos": [], "qualidade": rel, "meta": meta or {}, "ate": rel.get("ultima"),
           "preco": None, "tendencia": None, "multitemporal": None, "niveis": None, "extremos": None, "osciladores": None, "volatilidade": None,
           "volume": None, "divergencias": [], "padroes": [], "sinais": [], "liquidez": None, "lacunas": [], "proventos": None, "consolidacao": None}
    out["avisos"] += rel["problemas"]
    if len(d) < 40:
        out["avisos"].append(f"Histórico insuficiente para análise técnica ({len(d)} candles; mínimo 40).")
        return out
    perfil = perfil_classe(classe, d)
    out["perfil"] = {k: perfil[k] for k in ("liberada", "permitidos", "avisos", "motivo")}
    out["avisos"] += perfil["avisos"]
    if not perfil["liberada"]:
        out["avisos"].append(perfil["motivo"])
        return out
    freq = inferir_frequencia(d.index)
    out["frequencia"] = freq
    out["lacunas"] = detectar_lacunas(d.index, freq, cripto=classe == "cripto")
    if out["lacunas"]:
        out["avisos"].append(f"{len(out['lacunas'])} lacuna(s) no histórico: nada foi preenchido.")
    out["preco"] = float(d["Close"].iloc[-1])
    tr = classificar_tendencia(d)
    niv = suportes_resistencias(d)
    pad = detectar_padroes(d)
    out.update({"disponivel": True, "tendencia": tr, "niveis": niv, "multitemporal": analise_multitemporal(d, freq), "extremos": extremos(d),
                "osciladores": leitura_osciladores(d), "volatilidade": volatilidade_atual(d), "volume": volume_atual(d), "divergencias": divergencias(d),
                "padroes": pad, "consolidacao": consolidacao(d), "liquidez": avaliar_liquidez(d, classe),
                "sinais": gerar_sinais(d, ativo, classe, rotulo_periodo, moeda, trend=tr, niveis=niv, padroes=pad)})
    if out["liquidez"] and out["liquidez"].get("aviso"):
        out["avisos"].append(out["liquidez"]["aviso"])
    if len(d) >= 200:
        m200 = float(d["Close"].rolling(200).mean().iloc[-1])
        out["dist_sma200_pct"] = (out["preco"] / m200 - 1) * 100
    return _lim(out)


# =============================================================================== carteira
def visao_carteira(itens: list[dict], limite_corr: float = 0.7, peso_alerta: float = 10.0) -> dict:
    """Visão técnica consolidada. `itens` = [{'id','peso' (%),'classe','df'}] com as posições da carteira (Passo 12). Mostra a leitura de
    cada posição, o peso por tendência, grupos de ativos com tendência E comportamento parecidos (correlação) e riscos técnicos.
    Não faz operações; ativos sem dado suficiente aparecem como 'sem leitura'."""
    linhas, retornos = [], {}
    for it in itens:
        r = resumo_tecnico(it.get("df"), it.get("classe", "acao"), it["id"])
        linha = {"id": it["id"], "classe": r["classe"], "peso": float(it.get("peso") or 0), "disponivel": r["disponivel"], "tendencia": None, "confianca": None,
                 "osciladores": None, "volatilidade_elevada": False, "dist_sma200_pct": r.get("dist_sma200_pct"), "liquidez": None,
                 "multitemporal": None, "sinais": [], "avisos": r["avisos"]}
        if r["disponivel"]:
            linha.update({"tendencia": r["tendencia"]["tendencia"], "confianca": r["tendencia"]["confianca"], "osciladores": r["osciladores"]["geral"],
                          "volatilidade_elevada": r["volatilidade"]["elevada"], "liquidez": (r["liquidez"] or {}).get("nivel"),
                          "multitemporal": r["multitemporal"]["concordancia"], "sinais": [s["titulo"] for s in r["sinais"]]})
            c = it["df"]["Close"].astype(float)
            c.index = pd.DatetimeIndex(c.index)
            retornos[it["id"]] = c.pct_change().dropna().iloc[-120:]
        linhas.append(linha)
    total = sum(x["peso"] for x in linhas) or 1.0
    com = [x for x in linhas if x["tendencia"]]
    peso_ok = sum(x["peso"] for x in com)
    por_tend = {t: sum(x["peso"] for x in com if x["tendencia"] == t) / total * 100 for t in ("alta", "baixa", "lateral")}
    placar = (sum(x["peso"] * {"alta": 1, "baixa": -1, "lateral": 0}[x["tendencia"]] for x in com) / peso_ok) if peso_ok else None
    grupos, riscos = [], []
    for t in ("alta", "baixa", "lateral"):
        ids = [x["id"] for x in com if x["tendencia"] == t]
        if len(ids) >= 2:
            m = pd.concat([retornos[i].rename(i) for i in ids], axis=1, join="inner").dropna()
            cm = m.corr().to_numpy()
            corr = float(cm[~np.eye(len(ids), dtype=bool)].mean()) if len(m) >= 30 else None
            peso = sum(x["peso"] for x in com if x["id"] in ids) / total * 100
            grupos.append({"tendencia": t, "ativos": ids, "peso_pct": peso, "correlacao_media": corr,
                           "concentrada": bool(corr is not None and corr >= limite_corr and peso >= 40)})
    for x in com:
        pct = x["peso"] / total * 100
        if pct < peso_alerta:
            continue
        if x["tendencia"] == "baixa":
            riscos.append(f"{x['id']} ({fmt_num(pct, 0)}% da carteira) está em tendência de baixa (confiança {x['confianca']}).")
        if x["volatilidade_elevada"]:
            riscos.append(f"{x['id']} ({fmt_num(pct, 0)}%) com volatilidade acima do normal.")
        if x["osciladores"] == "sobrecompra":
            riscos.append(f"{x['id']} ({fmt_num(pct, 0)}%) com osciladores em sobrecompra: risco de correção de curto prazo.")
        if x["liquidez"] in ("baixa", "muito_baixa"):
            riscos.append(f"{x['id']} ({fmt_num(pct, 0)}%) com liquidez {x['liquidez'].replace('_', ' ')}: preço de saída pode diferir do gráfico.")
        if x["dist_sma200_pct"] is not None and x["dist_sma200_pct"] < -10:
            riscos.append(f"{x['id']} ({fmt_num(pct, 0)}%) está {fmt_num(abs(x['dist_sma200_pct']), 0)}% abaixo da média de 200 candles.")
    for g in grupos:
        if g["concentrada"]:
            riscos.append(f"{', '.join(g['ativos'])} somam {fmt_num(g['peso_pct'], 0)}% da carteira, estão em tendência de {g['tendencia']} e se movem juntos "
                          f"(correlação média {fmt_num(g['correlacao_media'], 2)}): a diversificação real é menor que a aparente.")
    sem = [x["id"] for x in linhas if not x["disponivel"]]
    return {"linhas": linhas, "peso_por_tendencia_pct": por_tend, "placar_ponderado": placar, "cobertura_pct": peso_ok / total * 100, "grupos": grupos,
            "riscos": riscos, "sem_leitura": sem,
            "resumo": (f"{fmt_num(por_tend['alta'], 0)}% do patrimônio analisado em tendência de alta, {fmt_num(por_tend['lateral'], 0)}% lateral e "
                       f"{fmt_num(por_tend['baixa'], 0)}% em baixa; cobertura técnica de {fmt_num(peso_ok / total * 100, 0)}% dos pesos." if peso_ok else
                       "Nenhuma posição tem histórico suficiente para leitura técnica.")}


# =============================================================================== assistente (interpreta o que está nos dados)
GLOSSARIO_ALIAS = {"rsi": "RSI", "ifr": "RSI", "macd": "MACD", "adx": "ADX", "dmi": "ADX", "ichimoku": "ICHIMOKU", "estocastico": "ESTOCASTICO",
                   "cci": "CCI", "roc": "ROC", "williams": "WILLIAMS", "bollinger": "BOLLINGER", "bandas de bollinger": "BOLLINGER", "atr": "ATR",
                   "desvio padrao": "DESVIO", "keltner": "KELTNER", "obv": "OBV", "vwap": "VWAP", "volume medio": "VOL_MEDIO", "mfi": "MFI",
                   "acumulacao": "AD", "distribuicao": "AD", "donchian": "DONCHIAN", "media movel simples": "SMA", "sma": "SMA", "ema": "EMA",
                   "media movel exponencial": "EMA", "wma": "WMA", "media movel ponderada": "WMA", "media movel": "SMA"}
CONCEITOS = {
    "suporte": "Suporte é uma região de preço onde as quedas anteriores foram contidas (compradores apareceram). Quanto mais toques e mais recente, mais relevante; um suporte rompido tende a virar resistência. Nada garante que segure de novo.",
    "resistencia": "Resistência é uma região de preço onde as altas anteriores foram barradas (vendedores apareceram). Quando o preço fecha acima dela com volume, fala-se em rompimento, que pode ser falso.",
    "rompimento": "Rompimento é o fechamento do preço além de uma zona de suporte ou resistência. Ganha credibilidade com volume acima da média, fechamentos seguidos fora da zona e ADX alto; mesmo assim pode ser falso (volta para dentro da zona).",
    "tendencia": "Tendência é a direção predominante do preço. Aqui ela é lida por vários critérios independentes (preço × médias, inclinação, regressão, topos e fundos, ADX); um cruzamento isolado não define tendência.",
    "divergencia": "Divergência é quando o preço faz um novo topo/fundo e um indicador (como o RSI) não acompanha. Avisa de perda de força, mas não determina reversão.",
    "sobrecompra": "Sobrecompra significa que o preço subiu rápido e osciladores (RSI, estocástico...) estão em zona alta. Pode indicar risco de correção, mas em tendência forte a zona pode durar muito tempo. Sobrevenda é o oposto.",
    "sobrevenda": "Sobrevenda significa que o preço caiu rápido e osciladores estão em zona baixa. Pode anteceder repique, mas em tendência de baixa forte pode persistir.",
    "backtest": "Backtest simula uma regra no histórico. Aqui o sinal usa só dados até o fechamento e a ordem é executada no candle seguinte, com custos e slippage. Desempenho passado não garante o futuro e o ajuste de parâmetros ao próprio histórico gera resultados otimistas.",
}
_KW_TEC = ("tecnic", "grafico", "indicador", "rsi", "ifr", "macd", "adx", "ichimoku", "estocast", "bollinger", "suporte", "resistencia", "rompimento", "tendencia",
           "sobrecompr", "sobrevend", "candle", "padrao", "padroes", "media movel", "volatil", "divergen", "atr", "obv", "vwap", "mfi", "cci", "momentum", "backtest",
           "keltner", "williams", "donchian", "sma", "ema")


def eh_pergunta_tecnica(pergunta: str) -> bool:
    q = " " + I._norm(pergunta) + " "
    return any((" " + k) in q for k in _KW_TEC)


def _achar_ativo(q: str, tec: dict, foco: str | None) -> str | None:
    toks = set(q.upper().split())
    for k in tec:
        if str(k).upper() in toks or I._norm(str(k)) in q.split():
            return k
    return foco if foco in tec else (next(iter(tec)) if len(tec) == 1 else None)


def _linhas_tec(r: dict) -> list[str]:
    L = []
    t = r.get("tendencia") or {}
    if t.get("tendencia"):
        L.append(f"Tendência ({r.get('frequencia', 'D')}): {t['tendencia']} (confiança {t['confianca']}); critérios: " + "; ".join(f"{c['nome']} {'+' if c['voto'] > 0 else '−' if c['voto'] < 0 else '0'}" for c in t["criterios"]))
    return L


def responder_tecnica(pergunta: str, ctx: dict | None) -> dict:
    """Responde SÓ com o que está em `ctx`: {'tecnica': {ativo: resumo_tecnico}, 'foco': ativo, 'ativos': [leituras do Passo 13],
    'carteira_tecnica': visao_carteira, 'gerado_em': iso}. Explica indicadores com o glossário; sobre ativos, cita valores, datas e
    limites. Sem dado, diz que não tem. Recusa pedidos de compra/venda."""
    ctx = ctx or {}
    q = I._norm(pergunta)
    tec = ctx.get("tecnica") or {}
    gerado = ctx.get("gerado_em")
    cab = f"Leitura técnica de {gerado[:16].replace('T', ' ')}" if gerado else "Sem leitura técnica carregada"
    base = {"sem_dados": False, "limite": "Leitura de dados e modelos simples, não recomendação."}

    def resp(texto, linhas=None, consultado=None, falta=False):
        c = consultado if consultado is not None else (f"Consultei a leitura técnica de {len(tec)} ativo(s)." if tec else "Não consultei dados de mercado.")
        return {**base, "texto": texto, "linhas": linhas or [], "referencia": cab, "consultado": c, "sem_dados": falta}

    if not q:
        return resp("Escreva uma pergunta sobre o gráfico ou sobre um indicador.", falta=True)
    if I._PEDIDO_INDICACAO.search(q):
        return resp("Eu não indico compra ou venda. Posso explicar o que os indicadores, a tendência, os níveis e os padrões mostram, com os dados e as condições que os invalidam.")
    # 1) explicações de indicadores e conceitos (não dependem de mercado)
    if re.search(r"\b(o que e|o que sao|significa|explique|explica|como funciona|como ler|para que serve|como interpretar|interpreta)\b", q):
        for alias in sorted(GLOSSARIO_ALIAS, key=len, reverse=True):
            if re.search(rf"\b{re.escape(alias)}\b", q):
                nome = GLOSSARIO_ALIAS[alias]
                esp = INDICADORES[nome]
                ps = ", ".join(f"{s['rotulo']} {s['padrao']}" for s in esp["params"].values()) or "sem parâmetros"
                return resp(f"{esp['nome']} ({esp['grupo']}). {esp['explicacao']}", [f"Parâmetros padrão: {ps}."], "Glossário de indicadores do app (sem dados de mercado).")
        for k, txt in CONCEITOS.items():
            if k in q:
                return resp(txt, [], "Glossário de conceitos do app (sem dados de mercado).")
    if not tec:
        return resp("Ainda não há leitura técnica carregada. Abra a página Análise técnica avançada, escolha um ativo e volte aqui (ou atualize a Central).", falta=True)
    if "carteira" in q:
        v = ctx.get("carteira_tecnica")
        if not v:
            return resp("A visão técnica da carteira ainda não foi calculada: abra Análise técnica avançada → Carteira.", falta=True)
        L = [f"{x['id']}: {x['tendencia'] or 'sem leitura'}" + (f" ({x['peso']:.0f}%)" if x.get("peso") else "") for x in v["linhas"]][:10]
        return resp(v["resumo"], L + v["riscos"][:6], f"Consultei a visão técnica de {len(v['linhas'])} posição(ões).")
    ativo = _achar_ativo(q, tec, ctx.get("foco"))
    if ativo is None:
        return resp("Diga de qual ativo está falando. Tenho leitura técnica de: " + ", ".join(list(tec)[:12]) + ".", falta=True)
    r = tec[ativo]
    if not r.get("disponivel"):
        return resp(f"Não tenho leitura técnica utilizável de {ativo}: " + (" ".join(r.get("avisos") or []) or "sem histórico suficiente.") + " Não vou estimar.", falta=True)
    t, mt, niv = r["tendencia"], r["multitemporal"], r["niveis"]
    moeda = r.get("moeda", "BRL")
    ate = r.get("ate")
    cons = f"Consultei a leitura técnica de {ativo} (dados até {ate})."
    if re.search(r"fundament|valuation|balanc|preco justo", q):
        fund = next((a for a in (ctx.get("ativos") or []) if str(a.get("id")).upper() == str(ativo).upper()), None)
        L = _linhas_tec(r)
        if not fund:
            return resp(f"Tenho a leitura técnica de {ativo}, mas não a leitura fundamentalista na Central (atualize a Central de inteligência para comparar).", L, cons, falta=True)
        pos = [x["titulo"] for x in fund.get("achados") or [] if x.get("tom") == "positivo"]
        neg = [x["titulo"] for x in fund.get("achados") or [] if x.get("tom") == "atencao"] + list(fund.get("bandeiras") or [])
        fav = fund.get("status") in ("merece_estudo", "sinais_parciais") and not neg
        tend = t["tendencia"]
        if fav and tend == "alta":
            txt = f"{ativo}: fundamentos e preço apontam na mesma direção (fundamentos favoráveis e tendência de alta)."
        elif fav and tend == "baixa":
            txt = f"{ativo}: divergência. Fundamentos favoráveis nos dados do app, mas o preço está em tendência de baixa; o mercado pode estar vendo algo que os dados do app não mostram, ou o preço pode estar defasado em relação aos fundamentos. Nenhum dos dois é conclusivo."
        elif neg and tend == "alta":
            txt = f"{ativo}: divergência. O preço sobe, mas há pontos de atenção nos fundamentos ({'; '.join(neg[:2])}). Tendência de alta com fundamentos frágeis costuma ser menos sustentável."
        elif neg and tend == "baixa":
            txt = f"{ativo}: preço em baixa e pontos de atenção nos fundamentos: os dois sinais apontam cautela."
        else:
            txt = f"{ativo}: leituras sem alinhamento claro (fundamentos: {fund.get('status') or 'n/d'}; tendência técnica: {tend})."
        return resp(txt, L + ([f"Pontos positivos: {'; '.join(pos[:3])}"] if pos else []) + ([f"Pontos de atenção: {'; '.join(neg[:3])}"] if neg else []),
                    cons + " Fundamentos: Central de inteligência (Passos 7 a 13).")
    if re.search(r"divergen", q) and re.search(r"period|prazo|semanal|mensal|diario|tempo|multi", q) or "multitempor" in q or "prazo" in q:
        if not mt or mt["concordancia"] == "insuficiente":
            return resp(f"Histórico de {ativo} insuficiente para comparar períodos.", [mt["conclusao"]] if mt else [], cons, falta=True)
        L = [f"{p['horizonte']} ({p['rotulo']}): {p['tendencia'] or 'sem leitura (' + (p['motivo'] or '') + ')'}" for p in mt["periodos"]]
        return resp(mt["conclusao"], L + mt["limites"][:1], cons)
    if re.search(r"rompiment|romper|rompe", q):
        rp = [s for s in r["sinais"] if s["tipo"] == "possivel_rompimento"]
        if rp:
            s = rp[0]
            return resp(f"{ativo}: {s['titulo'].lower()} detectado (evidência {s['confianca']}).", [s["justificativa"]] + [f"Invalida: {x}" for x in s["invalida"]], cons)
        L = [f"Resistência próxima: {fmt_preco(z['preco'], moeda)} ({z['toques']} toques, {fmt_num(z['distancia_pct'], 1)}% acima)" for z in niv["resistencias"][:2]]
        L += [f"Suporte próximo: {fmt_preco(z['preco'], moeda)} ({z['toques']} toques, {fmt_num(abs(z['distancia_pct']), 1)}% abaixo)" for z in niv["suportes"][:2]]
        return resp(f"Nenhum rompimento recente de suporte/resistência em {ativo}. Os níveis a observar:" if L else f"Sem zonas de suporte/resistência relevantes identificadas em {ativo}.", L, cons)
    if re.search(r"suporte|resistencia", q):
        L = [f"Resistência: {fmt_preco(z['preco'], moeda)} (faixa {fmt_preco(z['zona'][0], moeda)}–{fmt_preco(z['zona'][1], moeda)}; {z['toques']} toques; último em {z['ultimo_toque']})" for z in niv["resistencias"]]
        L += [f"Suporte: {fmt_preco(z['preco'], moeda)} (faixa {fmt_preco(z['zona'][0], moeda)}–{fmt_preco(z['zona'][1], moeda)}; {z['toques']} toques; último em {z['ultimo_toque']})" for z in niv["suportes"]]
        return resp(f"Zonas de {ativo} calculadas pelos topos e fundos do histórico (preço atual {fmt_preco(r['preco'], moeda)})." if L else f"Não identifiquei zonas com toques suficientes em {ativo}.", L, cons, falta=not L)
    if re.search(r"sobrecompr|sobrevend|rsi|ifr|estocast|oscilador", q):
        o = r["osciladores"]
        L = [f"{x['indicador']}: {fmt_num(x['valor'], 1)} ({x['zona']})" for x in o["itens"]]
        return resp(f"Osciladores de {ativo}: leitura geral {o['geral']}." + (" Em tendência forte, zonas extremas podem persistir." if o["geral"] != "neutra" else ""), L, cons, falta=not L)
    if re.search(r"padra|padroes|figura|triangulo|bandeira|cunha|canal|topo duplo|fundo duplo|ombro", q):
        p = r["padroes"]
        if not p:
            return resp(f"Nenhum padrão gráfico identificado em {ativo} com os critérios do app (ou histórico curto).", [], cons)
        L = [f"{x['nome']} — {x['estado']}, confiança {x['confianca_rotulo']} ({x['inicio']} a {x['fim']}). Invalida: {x['invalidacao']}" for x in p[:5]]
        return resp(f"{len(p)} padrão(ões) em {ativo}. Padrão 'em formação' NÃO está confirmado.", L, cons)
    if re.search(r"risco|volatil|perigo|cuidado|liquidez", q):
        L = []
        if r["volatilidade"]["elevada"]:
            L += r["volatilidade"]["motivos"]
        if r["osciladores"]["geral"] != "neutra":
            L.append(f"Osciladores em {r['osciladores']['geral']}.")
        if t["tendencia"] == "baixa":
            L.append(f"Tendência de baixa (confiança {t['confianca']}).")
        L += [d["texto"] for d in r["divergencias"][:2]]
        if r["liquidez"] and r["liquidez"].get("aviso"):
            L.append(r["liquidez"]["aviso"])
        L += [a for a in r["avisos"] if "lacuna" in a]
        return resp(f"Riscos técnicos de {ativo}." if L else f"Não há riscos técnicos relevantes sinalizados para {ativo} pelos critérios do app.", L, cons)
    if re.search(r"sinal|sinais", q):
        L = [f"{s['titulo']} (evidência {s['confianca']}, {s['evidencia']}/{s['total_criterios']} critérios): {s['justificativa']}" for s in r["sinais"]]
        return resp(f"Sinais técnicos de {ativo} em {ate}.", L, cons)
    # padrão: leitura geral do gráfico
    L = _linhas_tec(r)
    if mt and mt["concordancia"] != "insuficiente":
        L.append(mt["conclusao"])
    if niv["suportes"]:
        L.append(f"Suporte mais próximo: {fmt_preco(niv['suportes'][0]['preco'], moeda)}")
    if niv["resistencias"]:
        L.append(f"Resistência mais próxima: {fmt_preco(niv['resistencias'][0]['preco'], moeda)}")
    L += [f"Sinal: {s['titulo']} ({s['confianca']})" for s in r["sinais"][:3]]
    tend = t["tendencia"]
    return resp(f"{ativo} em {ate}: " + (f"tendência de {tend} (confiança {t['confianca']})." if tend else "sem tendência classificável com o histórico disponível."), L, cons)


def relatorio_tecnico_md(r: dict, titulo: str | None = None) -> str:
    """Relatório em Markdown de UM ativo, só com o que está no resumo técnico (sem inventar). Texto escapado para exibição."""
    esc = I.escapar_md
    L = [f"# {esc(titulo or 'Análise técnica · ' + str(r.get('ativo') or ''))}", "", f"_{AVISO_LEGAL}_", ""]
    if not r.get("disponivel"):
        L += ["Sem leitura técnica utilizável: " + esc(" ".join(r.get("avisos") or ["histórico insuficiente."]))]
        return "\n".join(L)
    moeda = r.get("moeda", "BRL")
    t = r["tendencia"]
    L += [f"**Dados até {esc(str(r.get('ate')))}** · preço {fmt_preco(r['preco'], moeda)}", "", "## Tendência",
          f"{t['tendencia'] or 'indefinida'} (confiança {t['confianca']})"] + [f"- {esc(c['nome'])}: {esc(c['texto'])}" for c in t["criterios"]]
    mt = r["multitemporal"]
    if mt:
        L += ["", "## Multitemporal", esc(mt["conclusao"])] + [f"- {p['horizonte']} ({p['rotulo']}): {p['tendencia'] or 'sem leitura'}" for p in mt["periodos"]]
    n = r["niveis"]
    L += ["", "## Suportes e resistências"] + [f"- {z['tipo']} {fmt_preco(z['preco'], moeda)} ({z['toques']} toques)" for z in n["resistencias"] + n["suportes"]]
    L += ["", "## Sinais"] + [f"- **{s['titulo']}** (evidência {s['confianca']}): {esc(s['justificativa'])} Invalida: {esc(' '.join(s['invalida']))}" for s in r["sinais"]]
    if r["padroes"]:
        L += ["", "## Padrões"] + [f"- {p['nome']} — {p['estado']}, confiança {p['confianca_rotulo']}. Invalida: {esc(p['invalidacao'])}" for p in r["padroes"]]
    L += ["", "## Dados", esc(descrever_fonte(r.get("meta") or {}, r.get("qualidade"), r.get("lacunas")))]
    return "\n".join(L)


# =============================================================================== linhas de tendência e histórico de sinais
def linhas_de_tendencia(df: pd.DataFrame, w: int | None = None, janela: int = 150) -> list[dict]:
    """Retas ligando os DOIS ÚLTIMOS fundos e os DOIS ÚLTIMOS topos (pivôs) da janela, estendidas até o último candle. São auxílios
    visuais: o rótulo diz a inclinação; uma reta só vale como suporte/resistência se o preço a respeitar."""
    if df is None or len(df) < 40:
        return []
    n = len(df)
    topos, fundos = _pivos(df, w or _w_padrao(n))
    out = []
    for nome, ps in (("fundos", [p for p in fundos if p[0] >= n - janela]), ("topos", [p for p in topos if p[0] >= n - janela])):
        if len(ps) < 2:
            continue
        (i1, p1), (i2, p2) = ps[-2], ps[-1]
        if i2 == i1:
            continue
        m = (p2 - p1) / (i2 - i1)
        fim = p2 + m * (n - 1 - i2)
        if fim <= 0:
            continue
        sent = "ascendente" if (fim / p2 - 1) > 0.002 else "descendente" if (fim / p2 - 1) < -0.002 else "horizontal"
        out.append({"tipo": f"Linha dos {nome} ({sent})", "pontos": [(_dia(df.index[i1]), float(p1)), (_dia(df.index[i2]), float(p2))],
                    "linha": (_dia(df.index[i1]), float(p1), _dia(df.index[n - 1]), float(fim)), "sentido": sent, "base": nome})
    return out


def filtrar_por_frequencia(disparos: list[dict], historico: list[dict], regras: list[dict], agora: datetime | None = None) -> tuple[list[dict], list[dict], int]:
    """Aplica `intel.filtrar_repetidos` respeitando a frequência de CADA regra e mantém um único histórico (reaproveitado pela Central).
    Devolve (alertas novos, histórico atualizado, nº suprimidos como repetidos)."""
    agora = agora or datetime.now()
    freq = {r["id"]: r.get("frequencia", "diaria") for r in regras}
    novos, hist, supr = [], list(historico or []), 0
    for f in sorted(set(freq.get(d["regra_id"], "diaria") for d in disparos)):
        sub = [d for d in disparos if freq.get(d["regra_id"], "diaria") == f]
        n, hist, s = I.filtrar_repetidos(sub, hist, agora, f)
        novos += n
        supr += s
    return sorted(novos, key=lambda x: (I.PRIORIDADES.get(x["prioridade"], 3), x["ativo"])), hist, supr


def registrar_sinais(historico: list[dict], sinais: list[dict], limite: int = 300) -> tuple[list[dict], int]:
    """Histórico de sinais: cada (ativo, tipo, data do candle) entra uma única vez. Devolve (histórico, quantos novos)."""
    hist = list(historico or [])
    vistos = {(h.get("ativo"), h.get("tipo"), h.get("data")) for h in hist}
    novos = 0
    for s in sinais:
        if s["tipo"] == "sem_sinal":
            continue
        k = (s["ativo"], s["tipo"], s["data"])
        if k in vistos:
            continue
        vistos.add(k)
        hist.append({"ativo": s["ativo"], "tipo": s["tipo"], "titulo": s["titulo"], "data": s["data"], "confianca": s["confianca"],
                     "direcao": s["direcao"], "periodo": s["periodo"], "registrado_em": datetime.now().isoformat(timespec="minutes")})
        novos += 1
    return hist[-limite:], novos
