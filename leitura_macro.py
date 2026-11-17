"""
leitura_macro.py - Assistente que resume O QUE OS DADOS ESTAO DIZENDO (nao o que cada indicador e).

Cada funcao ler_* recebe a serie (DataFrame com coluna 'valor', indice de datas) e devolve
{"titulo", "tom", "texto"} ou None se nao houver dados. tom: "pos" | "neg" | "neu".
As regras sao simples e transparentes (limiares comentados), para voce poder ajustar.
"""
from __future__ import annotations

import pandas as pd


# ------------------------------------------------------------------ utilitarios
def _n(v: float, c: int = 2) -> str:
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _sinal(v: float, c: int = 2, suf: str = "") -> str:
    return ("+" if v >= 0 else "−") + _n(abs(v), c) + suf


def _limpa(df) -> pd.Series | None:
    if df is None or len(df) == 0 or "valor" not in df:
        return None
    s = df["valor"].dropna().sort_index()
    s = s[~s.index.duplicated(keep="last")]
    return s if len(s) >= 3 else None


def _janela(s: pd.Series, anos: int) -> pd.Series:
    return s.loc[s.index >= s.index[-1] - pd.DateOffset(years=anos)]


def _posicao(s: pd.Series, anos: int) -> str:
    """Onde o ultimo valor esta dentro do periodo escolhido."""
    j = _janela(s, anos)
    if len(j) < 5:
        return ""
    ult, mn, mx = float(j.iloc[-1]), float(j.min()), float(j.max())
    tag = f"nos últimos {anos} ano{'s' if anos > 1 else ''}"
    if ult >= mx:
        return f"É o maior valor {tag}."
    if ult <= mn:
        return f"É o menor valor {tag}."
    pr = float((j <= ult).mean() * 100)
    return f"Está acima de {_n(pr, 0)}% das leituras {tag} (mín. {_n(mn)}, máx. {_n(mx)})."


# ------------------------------------------------------------------ Ipeadata
# titulo (igual ao de IPEA_CATEGORIAS) -> (tipo, sentido, frase se subir, frase se cair)
#   tipo: "nivel" (variacao em %), "taxa" (variacao em p.p.), "mensal" (taxa mensal em %)
#   sentido: +1 alta e boa | -1 alta e ruim | 0 neutro
SPEC_IPEA = {
    "Risco-País EMBI+ Brasil (pontos)": ("nivel", -1,
        "Risco maior encarece o capital e costuma pesar sobre a bolsa.",
        "Risco menor barateia o capital e costuma ajudar a bolsa."),
    "IPCA mensal (%)": ("mensal", -1,
        "Inflação mensal mais forte repassa custos ao consumidor.",
        "Inflação mensal mais fraca alivia o consumidor."),
    "IGP-M mensal (%)": ("mensal", -1,
        "Mais pressão nos custos de atacado e nos reajustes de aluguéis e contratos de elétricas.",
        "Menos pressão nos reajustes de aluguéis e contratos de elétricas."),
    "INCC mensal (%)": ("mensal", -1,
        "Custo da obra subindo comprime a margem de construtoras e incorporadoras.",
        "Custo da obra mais comportado ajuda as margens de construtoras."),
    "IBC-Br (prévia do PIB)": ("nivel", 1,
        "Atividade em expansão favorece cíclicas, consumo e indústria.",
        "Atividade perdendo fôlego pede cautela com empresas cíclicas."),
    "Produção industrial (geral)": ("nivel", 1,
        "Indústria em alta indica demanda firme para bens de capital e insumos.",
        "Indústria em queda indica demanda mais fraca para bens de capital e insumos."),
    "Vendas no varejo (PMC)": ("nivel", 1,
        "Consumo mais forte favorece o varejo.",
        "Consumo mais fraco pressiona o varejo."),
    "Desemprego PNAD (%)": ("taxa", -1,
        "Desemprego maior enfraquece renda, consumo e crédito.",
        "Desemprego menor sustenta renda, consumo e crédito."),
}


