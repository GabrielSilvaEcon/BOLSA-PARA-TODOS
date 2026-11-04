"""
Ativos em dólar na carteira.

Regra: ticker da B3 (e pares ...-BRL) = reais; qualquer outro (AAPL, VOO, BTC-USD) = dólar (mesma regra de gestao.moeda_do_ticker).
O lote de um ativo em dólar guarda o PREÇO PAGO EM US$. Para somar com o resto da carteira, converte-se para reais:
 - custo (o que saiu do caixa) = qtd × preço × dólar do dia da compra;
 - valor atual = qtd × preço atual × dólar de hoje.
Sem cotação do dólar, não se inventa: o cálculo devolve None.
"""
from __future__ import annotations

import pandas as pd

import gestao as g


def eh_dolar(ticker: str) -> bool:
    return g.moeda_do_ticker(ticker) != "BRL"


def simbolo(ticker: str) -> str:
    return "US$" if eh_dolar(ticker) else "R$"


def cambio_em(fx: pd.Series | None, d=None) -> float | None:
    """Dólar (R$ por US$) no dia d (ou o último antes dele); sem data, o mais recente."""
    if fx is None or len(fx) == 0:
        return None
    if d is None:
        return float(fx.iloc[-1])
    f = fx.loc[:pd.Timestamp(d)]
    return float(f.iloc[-1]) if len(f) else float(fx.iloc[0])


def cambio_serie() -> pd.Series:
    try:
        import dados
        return dados.serie_cambio()
    except Exception:
        return pd.Series(dtype=float)


def custo_lote_brl(lote: dict, fx: pd.Series | None) -> float | None:
    custo = float(lote.get("qtd") or 0) * float(lote.get("preco_medio") or 0)
    if not eh_dolar(lote.get("ticker", "")):
        return custo
    f = cambio_em(fx, lote.get("data"))
    return custo * f if f else None


def custo_total_brl(lotes: list, fx: pd.Series | None = None) -> float | None:
    """Soma do custo de todos os lotes em reais; None se faltar o dólar para algum lote em US$."""
    lotes = [l for l in (lotes or []) if isinstance(l, dict)]
    if fx is None and any(eh_dolar(l.get("ticker", "")) for l in lotes):
        fx = cambio_serie()
    total = 0.0
    for l in lotes:
        c = custo_lote_brl(l, fx)
        if c is None:
            return None
        total += c
    return total
