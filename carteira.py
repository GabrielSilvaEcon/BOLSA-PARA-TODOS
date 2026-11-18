"""Histórico de preços de um ativo (fechamento diário, sem fuso, sem datas repetidas), com cache de 1 h.

Era o módulo da antiga tela de carteira virtual (removida: a carteira do app agora é uma só, a Minha Carteira).
Ficou só a leitura de histórico, usada pelo gráfico dos ativos da carteira e pela Gestão de carteira.
"""
import pandas as pd
import streamlit as st

from dados import historico_yahoo


@st.cache_data(ttl=3600, show_spinner=False)
def _hist(tk: str, periodo: str) -> pd.Series:
    try:
        df, _ = historico_yahoo(tk, periodo, "1d")
    except Exception:
        return pd.Series(dtype=float)
    if df is None or df.empty or "Close" not in df:
        return pd.Series(dtype=float)
    s = df["Close"].dropna()
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")]
