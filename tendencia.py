"""
Análise Técnica (Tendência): motor puro, sem Streamlit e sem rede.

Recebe o histórico de preços (DataFrame com coluna "Close"; "High", "Low" e "Volume" são opcionais) de QUALQUER
ativo (ação da B3, ETF, criptomoeda) e devolve um veredito de tendência (Alta, Baixa ou Lateral) mais os sinais
calculados, cada um com a sua leitura. Nada aqui usa fundamentos.

    r = analisar(df)
    r["veredito"]   # "Alta" | "Lateral" | "Baixa" | None (poucos dados)
    r["sinais"]     # [{"chave","nome","valor","leitura","direcao","peso","status"}, ...]
    r["placar"]     # -1 (tudo baixa) a +1 (tudo alta)

Regra do veredito: cada sinal direcional vota +1 (alta), 0 (neutro) ou -1 (baixa), multiplicado pelo seu peso.
O placar é a soma dos votos dividida pela soma dos pesos dos sinais disponíveis. Placar >= +0,35 = Alta;
<= -0,35 = Baixa; entre os dois = Lateral. Sobrecompra/sobrevenda (IFR) e Bollinger só avisam, não votam.
Os limites são regras educacionais, não recomendação de investimento.
"""
from __future__ import annotations

import pandas as pd

LIMITE = 0.35
MIN_CANDLES = 50          # abaixo disso não há veredito
SELO = {"Alta": ("▲ Alta", "good"), "Lateral": ("► Lateral", "fair"), "Baixa": ("▼ Baixa", "bad"), None: ("Sem dados", "na")}


# --------------------------------------------------------------------------- indicadores
def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    """IFR de Wilder."""
    d = c.diff()
    ganho = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    perda = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + ganho / perda.where(perda != 0))


def macd(c: pd.Series, rapida: int = 12, lenta: int = 26, sinal: int = 9) -> pd.DataFrame:
    linha = c.ewm(span=rapida, adjust=False).mean() - c.ewm(span=lenta, adjust=False).mean()
    sig = linha.ewm(span=sinal, adjust=False).mean()
    return pd.DataFrame({"macd": linha, "sinal": sig, "hist": linha - sig})


def indicadores(df: pd.DataFrame) -> pd.DataFrame:
    """SMA 20/50/200, IFR 14, MACD e Bandas de Bollinger (20, 2), alinhados ao índice do histórico."""
    c = df["Close"].astype(float)
    out = pd.DataFrame(index=df.index)
    out["SMA20"], out["SMA50"], out["SMA200"] = c.rolling(20).mean(), c.rolling(50).mean(), c.rolling(200).mean()
    out["RSI14"] = rsi(c)
    m = macd(c)
    out["MACD"], out["MACD_SINAL"], out["MACD_HIST"] = m["macd"], m["sinal"], m["hist"]
    desvio = c.rolling(20).std(ddof=0)
    out["BBM"] = out["SMA20"]
    out["BBU"], out["BBL"] = out["SMA20"] + 2 * desvio, out["SMA20"] - 2 * desvio
    return out


# --------------------------------------------------------------------------- sinais
def _num(v, casas=2) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _s(chave, nome, valor, leitura, direcao, peso):
    """direcao: +1 alta, 0 neutro, -1 baixa, None = só informativo (não vota)."""
    status = {1: "good", 0: "fair", -1: "bad"}.get(direcao, "info")
    return {"chave": chave, "nome": nome, "valor": valor, "leitura": leitura, "direcao": direcao,
            "peso": peso if direcao is not None else 0, "status": status}


def _na(chave, nome, motivo):
    return {"chave": chave, "nome": nome, "valor": "n/d", "leitura": motivo, "direcao": None, "peso": 0, "status": "na"}


def analisar(df: pd.DataFrame | None) -> dict:
    """Calcula os sinais e o veredito. Nunca levanta erro por falta de dados: devolve veredito None."""
    vazio = {"veredito": None, "placar": None, "sinais": [], "ind": None, "candles": 0, "alta": 0, "baixa": 0,
             "neutros": 0, "preco": None}
    if df is None or df.empty or "Close" not in df:
        return vazio
    df = df.dropna(subset=["Close"])
    n = len(df)
    vazio["candles"] = n
    if n < MIN_CANDLES:
        return vazio
    ind = indicadores(df)
    u = ind.iloc[-1]
    c = float(df["Close"].iloc[-1])
    sinais = []

    # 1 · preço × SMA 200 (tendência de longo prazo)
    if pd.notna(u["SMA200"]):
        ac = c > u["SMA200"]
        sinais.append(_s("p200", "Preço × SMA 200", f"{'acima' if ac else 'abaixo'} ({(c / u['SMA200'] - 1) * 100:+.1f}%)".replace(".", ","),
                         "Acima da média de longo prazo: viés de alta." if ac else "Abaixo da média de longo prazo: viés de baixa.",
                         1 if ac else -1, 2))
    else:
        sinais.append(_na("p200", "Preço × SMA 200", "Precisa de 200 candles."))
    # 2 · SMA 50 × SMA 200 (cruz dourada / cruz da morte)
    if pd.notna(u["SMA200"]):
        ac = u["SMA50"] > u["SMA200"]
        sinais.append(_s("c50_200", "SMA 50 × SMA 200", "Cruz dourada" if ac else "Cruz da morte",
                         "Média média acima da longa: tendência primária de alta." if ac else
                         "Média média abaixo da longa: tendência primária de baixa.", 1 if ac else -1, 2))
    else:
        sinais.append(_na("c50_200", "SMA 50 × SMA 200", "Precisa de 200 candles."))
    # 3 · preço e SMA 20 × SMA 50 (médio prazo)
    s20, s50 = u["SMA20"], u["SMA50"]
    if c > s50 and s20 > s50:
        d, leit = 1, "Preço e SMA 20 acima da SMA 50."
    elif c < s50 and s20 < s50:
        d, leit = -1, "Preço e SMA 20 abaixo da SMA 50."
    else:
        d, leit = 0, "Sinais mistos entre preço e médias."
    sinais.append(_s("m20_50", "Preço e SMA 20 × SMA 50", {1: "alta", 0: "misto", -1: "baixa"}[d], leit, d, 1))
    # 4 · inclinação da SMA 50 nos últimos 10 candles
    ref = ind["SMA50"].iloc[-11] if n >= 61 else None
    if ref is not None and pd.notna(ref) and ref > 0:
        incl = (s50 / ref - 1) * 100
        d = 1 if incl > 0.3 else -1 if incl < -0.3 else 0
        sinais.append(_s("incl50", "Inclinação da SMA 50 (10 candles)", f"{incl:+.1f}%".replace(".", ","),
                         {1: "Média subindo.", 0: "Média praticamente plana.", -1: "Média caindo."}[d], d, 1))
    else:
        sinais.append(_na("incl50", "Inclinação da SMA 50 (10 candles)", "Precisa de 60 candles."))
    # 5 · MACD
    if pd.notna(u["MACD"]) and pd.notna(u["MACD_SINAL"]):
        d = 1 if u["MACD"] > u["MACD_SINAL"] and u["MACD"] > 0 else -1 if u["MACD"] < u["MACD_SINAL"] and u["MACD"] < 0 else 0
        sinais.append(_s("macd", "MACD (12, 26, 9)", f"hist. {_num(u['MACD_HIST'], 3)}",
                         {1: "MACD acima da linha de sinal e positivo: momento de alta.",
                          0: "MACD sem alinhamento: momento indefinido.",
                          -1: "MACD abaixo da linha de sinal e negativo: momento de baixa."}[d], d, 1))
    # 6 · IFR: >55 momento de alta, <45 de baixa; extremos só avisam
    r = u["RSI14"]
    if pd.notna(r):
        d = 1 if r >= 55 else -1 if r <= 45 else 0
        ext = " Sobrecompra (≥ 70): pode haver correção." if r >= 70 else " Sobrevenda (≤ 30): possível repique." if r <= 30 else ""
        sinais.append(_s("ifr", "IFR (RSI) 14", _num(r, 1),
                         {1: "Momento comprador (≥ 55).", 0: "Zona neutra (45 a 55).", -1: "Momento vendedor (≤ 45)."}[d] + ext,
                         d, 1))
    # 7 · Bollinger: só informativo
    bl, bu = u["BBL"], u["BBU"]
    if pd.notna(bl) and pd.notna(bu) and bu != bl:
        pb = (c - bl) / (bu - bl)
        txt = ("Acima da banda superior: esticado para cima." if pb > 1 else
               "Abaixo da banda inferior: esticado para baixo." if pb < 0 else "Dentro das bandas (0 = inferior, 1 = superior).")
        sinais.append(_s("bb", "Bollinger (20, 2)", f"%B {_num(pb, 2)}", txt, None, 0))
    # 8 · posição no intervalo do período: só informativo
    alto, baixo = float(df["Close"].max()), float(df["Close"].min())
    if alto > baixo:
        sinais.append(_s("faixa", f"Posição no período ({n} candles)", f"{(c - baixo) / (alto - baixo) * 100:.0f}%".replace(".", ","),
                         f"Máxima {_num(alto)} · mínima {_num(baixo)}.", None, 0))

    votos = [x for x in sinais if x["direcao"] is not None]
    peso = sum(x["peso"] for x in votos)
    placar = sum(x["direcao"] * x["peso"] for x in votos) / peso if peso else None
    ver = None if placar is None else "Alta" if placar >= LIMITE else "Baixa" if placar <= -LIMITE else "Lateral"
    return {"veredito": ver, "placar": placar, "sinais": sinais, "ind": ind, "candles": n, "preco": c,
            "alta": sum(x["direcao"] == 1 for x in votos), "baixa": sum(x["direcao"] == -1 for x in votos),
            "neutros": sum(x["direcao"] == 0 for x in votos)}


def resumo_texto(r: dict) -> str:
    """Frase do card: quantos sinais apontam para cada lado."""
    if r["veredito"] is None:
        return (f"Só {r['candles']} candles: são necessários pelo menos {MIN_CANDLES} para calcular a tendência."
                if r["candles"] else "Sem histórico de preços para calcular a tendência.")
    return (f"{r['alta']} sinal(is) de alta, {r['baixa']} de baixa e {r['neutros']} neutro(s) · "
            f"placar {r['placar']:+.2f}".replace(".", ","))


# --------------------------------------------------------------------------- gráfico simples (preço + médias + IFR)
def figura(df: pd.DataFrame, ind: pd.DataFrame, altura: int = 560, visiveis: int = 180):
    """Candles (ou linha, se não houver OHLC), SMA 20/50/200 e IFR. Plotly é importado aqui para o motor continuar puro."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    df, ind = df.tail(visiveis), ind.tail(visiveis)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.74, 0.26], vertical_spacing=0.04)
    if {"Open", "High", "Low"} <= set(df.columns):
        fig.add_trace(go.Candlestick(x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
                                     name="Preço", increasing_line_color="#26A69A", decreasing_line_color="#EF5350",
                                     showlegend=False), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=df.index, y=df["Close"], name="Preço", line=dict(color="#EDE9FF", width=1.6)), row=1, col=1)
    for col, nome, cor in (("SMA20", "SMA 20", "#DDA735"), ("SMA50", "SMA 50", "#8EA2FF"), ("SMA200", "SMA 200", "#C084FC")):
        if ind[col].notna().any():
            fig.add_trace(go.Scatter(x=ind.index, y=ind[col], name=nome, line=dict(color=cor, width=1.3)), row=1, col=1)
    fig.add_trace(go.Scatter(x=ind.index, y=ind["RSI14"], name="IFR 14", showlegend=False, line=dict(color="#E5C8FF", width=1.4)),
                  row=2, col=1)
    for nivel in (30, 70):
        fig.add_hline(y=nivel, line_dash="dot", line_color="rgba(189,181,230,.5)", row=2, col=1)
    fig.update_layout(height=altura, template="plotly_dark", paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      margin=dict(l=0, r=0, t=10, b=0), xaxis_rangeslider_visible=False, hovermode="x unified",
                      legend=dict(orientation="h", y=1.04, x=0))
    fig.update_yaxes(gridcolor="rgba(189,181,230,.12)")
    fig.update_yaxes(range=[0, 100], row=2, col=1)
    return fig
