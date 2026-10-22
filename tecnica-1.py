"""
Análise técnica: sinais de candlestick, padrões gráficos clássicos e indicadores.

Tudo é calculado a partir do histórico OHLCV (Yahoo Finance) com regras simples e
transparentes. São heurísticas educacionais, não recomendação de investimento.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ALTA, BAIXA, NEUTRO = "alta", "baixa", "neutro"

# Paleta neutra (tons suaves, sem branco puro nem cores saturadas)
UP = "#6f9c85"
DOWN = "#b0706b"
MUTED = "#8b919c"
ACCENT = "#8aa0b8"
GOLD = "#c2ad7e"
TEXT = "#cfd3da"
GRID = "#262a33"

CANDLE_NOMES = [
    "Doji", "Martelo", "Enforcado", "Martelo invertido", "Estrela cadente",
    "Engolfo de alta", "Engolfo de baixa", "Estrela da manhã", "Estrela da noite",
    "Três soldados", "Três corvos", "Marubozu de alta", "Marubozu de baixa",
]


def _sinal(data, nome, tipo, preco, categoria):
    return {"data": data, "sinal": nome, "tipo": tipo, "preco": float(preco), "categoria": categoria}


# ------------------------------------------------------------------ candlestick
def candlesticks(df: pd.DataFrame) -> list[dict]:
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    rng = (h - l).replace(0, np.nan)
    corpo = (c - o).abs()
    sup = h - np.maximum(o, c)
    inf = np.minimum(o, c) - l
    media = corpo.rolling(10, min_periods=3).mean()

    queda = c.shift(1) < c.shift(6)   # tendência prévia de baixa
    subida = c.shift(1) > c.shift(6)  # tendência prévia de alta
    verde, verm = c > o, c < o

    doji = corpo <= 0.1 * rng
    forma_martelo = (inf >= 2 * corpo) & (sup <= 0.15 * rng) & ~doji
    forma_invertido = (sup >= 2 * corpo) & (inf <= 0.15 * rng) & ~doji

    po, pc, pcorpo = o.shift(1), c.shift(1), corpo.shift(1)
    engolfo_alta = (pc < po) & verde & (c >= po) & (o <= pc) & (corpo > pcorpo) & queda
    engolfo_baixa = (pc > po) & verm & (o >= pc) & (c <= po) & (corpo > pcorpo) & subida

    c2, o2, corpo2 = c.shift(2), o.shift(2), corpo.shift(2)
    pequeno1 = pcorpo <= 0.3 * corpo2
    manha = (c2 < o2) & (corpo2 > media.shift(2)) & pequeno1 & verde & (c > (o2 + c2) / 2)
    noite = (c2 > o2) & (corpo2 > media.shift(2)) & pequeno1 & verm & (c < (o2 + c2) / 2)

    v1, v2 = verde.shift(1, fill_value=False), verde.shift(2, fill_value=False)
    r1, r2 = verm.shift(1, fill_value=False), verm.shift(2, fill_value=False)
    fortes = (corpo > media) & (corpo.shift(1) > media.shift(1)) & (corpo.shift(2) > media.shift(2))
    soldados = verde & v1 & v2 & (c > pc) & (pc > c2) & fortes
    corvos = verm & r1 & r2 & (c < pc) & (pc < c2) & fortes

    maru = (corpo >= 0.9 * rng) & (corpo > media)

    regras = [
        ("Doji", NEUTRO, doji),
        ("Martelo", ALTA, forma_martelo & queda),
        ("Enforcado", BAIXA, forma_martelo & subida),
        ("Martelo invertido", ALTA, forma_invertido & queda),
        ("Estrela cadente", BAIXA, forma_invertido & subida),
        ("Engolfo de alta", ALTA, engolfo_alta),
        ("Engolfo de baixa", BAIXA, engolfo_baixa),
        ("Estrela da manhã", ALTA, manha),
        ("Estrela da noite", BAIXA, noite),
        ("Três soldados", ALTA, soldados),
        ("Três corvos", BAIXA, corvos),
        ("Marubozu de alta", ALTA, maru & verde),
        ("Marubozu de baixa", BAIXA, maru & verm),
    ]
    sinais = []
    for nome, tipo, mask in regras:
        for i in np.flatnonzero(mask.to_numpy(dtype=bool)):
            preco = l.iloc[i] if tipo == ALTA else h.iloc[i]
            sinais.append(_sinal(df.index[i], nome, tipo, preco, "Candlestick"))
    return sinais


# ------------------------------------------------------------------ pivôs e padrões gráficos
def _limpa(piv, maior, w):
    out = []
    for i, p in piv:
        if out and i - out[-1][0] <= w:
            if (maior and p > out[-1][1]) or (not maior and p < out[-1][1]):
                out[-1] = (i, p)
        else:
            out.append((i, p))
    return out


def pivots(df: pd.DataFrame, w: int = 5):
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    topos, fundos = [], []
    for i in range(w, len(df) - w):
        if h[i] == h[i - w:i + w + 1].max():
            topos.append((i, float(h[i])))
        if l[i] == l[i - w:i + w + 1].min():
            fundos.append((i, float(l[i])))
    return _limpa(topos, True, w), _limpa(fundos, False, w)


def _reta(x0, y0, x1, y1, x):
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def padroes_graficos(df: pd.DataFrame, w: int = 5):
    """Duplo topo/fundo, OCO/OCOI, triângulos e níveis de suporte/resistência."""
    c, h, l = df["Close"].to_numpy(), df["High"].to_numpy(), df["Low"].to_numpy()
    n = len(df)
    topos, fundos = pivots(df, w)
    pats: list[dict] = []

    def add(nome, tipo, pontos, linhas, ref):
        pats.append({
            "nome": nome, "tipo": tipo, "pontos": pontos, "linhas": linhas, "ref": ref,
            "data": df.index[ref], "preco": float(c[ref]), "categoria": "Padrão gráfico",
        })

    # Duplo topo
    for (i1, p1), (i2, p2) in zip(topos, topos[1:]):
        if i2 - i1 < 8 or abs(p1 - p2) / max(p1, p2) > 0.03:
            continue
        seg = l[i1:i2 + 1]
        vale = float(seg.min())
        if (min(p1, p2) - vale) / min(p1, p2) < 0.04:
            continue
        conf = bool((c[i2 + 1:] < vale).any())
        add(f"Duplo topo ({'confirmado' if conf else 'em formação'})", BAIXA,
            [(i1, p1), (i2, p2)], [(i1, p1, i2, p2), (i1, vale, i2, vale)], i2)

    # Duplo fundo
    for (i1, p1), (i2, p2) in zip(fundos, fundos[1:]):
        if i2 - i1 < 8 or abs(p1 - p2) / max(p1, p2) > 0.03:
            continue
        seg = h[i1:i2 + 1]
        pico = float(seg.max())
        if (pico - max(p1, p2)) / max(p1, p2) < 0.04:
            continue
        conf = bool((c[i2 + 1:] > pico).any())
        add(f"Duplo fundo ({'confirmado' if conf else 'em formação'})", ALTA,
            [(i1, p1), (i2, p2)], [(i1, p1, i2, p2), (i1, pico, i2, pico)], i2)

    # Ombro-cabeça-ombro (OCO) – baixa
    for (ia, pa), (ib, pb), (ic, pc_) in zip(topos, topos[1:], topos[2:]):
        if not (pb > pa * 1.03 and pb > pc_ * 1.03) or abs(pa - pc_) / max(pa, pc_) > 0.05:
            continue
        s1, s2 = l[ia:ib + 1], l[ib:ic + 1]
        v1i, v2i = ia + int(s1.argmin()), ib + int(s2.argmin())
        v1, v2 = float(s1.min()), float(s2.min())
        if v1i == v2i:
            continue
        xs = np.arange(ic + 1, n)
        conf = bool((c[ic + 1:] < v1 + (v2 - v1) * (xs - v1i) / (v2i - v1i)).any()) if len(xs) else False
        xe = min(n - 1, v2i + 5)
        add(f"OCO ({'confirmado' if conf else 'em formação'})", BAIXA,
            [(ia, pa), (ib, pb), (ic, pc_)], [(v1i, v1, xe, _reta(v1i, v1, v2i, v2, xe))], ic)

    # OCO invertido – alta
    for (ia, pa), (ib, pb), (ic, pc_) in zip(fundos, fundos[1:], fundos[2:]):
        if not (pb < pa * 0.97 and pb < pc_ * 0.97) or abs(pa - pc_) / max(pa, pc_) > 0.05:
            continue
        s1, s2 = h[ia:ib + 1], h[ib:ic + 1]
        v1i, v2i = ia + int(s1.argmax()), ib + int(s2.argmax())
        v1, v2 = float(s1.max()), float(s2.max())
        if v1i == v2i:
            continue
        xs = np.arange(ic + 1, n)
        conf = bool((c[ic + 1:] > v1 + (v2 - v1) * (xs - v1i) / (v2i - v1i)).any()) if len(xs) else False
        xe = min(n - 1, v2i + 5)
        add(f"OCO invertido ({'confirmado' if conf else 'em formação'})", ALTA,
            [(ia, pa), (ib, pb), (ic, pc_)], [(v1i, v1, xe, _reta(v1i, v1, v2i, v2, xe))], ic)

    # mantém só os 2 mais recentes de cada tipo
    por_tipo: dict[str, list[dict]] = {}
    for p in pats:
        por_tipo.setdefault(p["nome"].split(" (")[0], []).append(p)
    pats = [p for lst in por_tipo.values() for p in lst[-2:]]

    # Triângulos (últimos 3 topos e 3 fundos dentro de ~150 candles)
    rt = [p for p in topos if p[0] >= n - 150][-3:]
    rf = [p for p in fundos if p[0] >= n - 150][-3:]
    if len(rt) == 3 and len(rf) == 3:
        x0 = min(rt[0][0], rf[0][0])
        at, bt = np.polyfit([p[0] for p in rt], [p[1] for p in rt], 1)
        af, bf = np.polyfit([p[0] for p in rf], [p[1] for p in rf], 1)
        span = n - 1 - x0
        pm = float(np.mean(c[x0:]))
        s_t, s_f = at * span / pm, af * span / pm
        gap0 = (at * x0 + bt) - (af * x0 + bf)
        gap1 = (at * (n - 1) + bt) - (af * (n - 1) + bf)
        if gap0 > 0 and 0 < gap1 < gap0 * 0.8:
            plano = 0.03
            nome = tipo = None
            if abs(s_t) < plano and s_f > plano:
                nome, tipo = "Triângulo ascendente", ALTA
            elif abs(s_f) < plano and s_t < -plano:
                nome, tipo = "Triângulo descendente", BAIXA
            elif s_t < -plano and s_f > plano:
                nome, tipo = "Triângulo simétrico", NEUTRO
            if nome:
                add(nome, tipo, [], [
                    (x0, at * x0 + bt, n - 1, at * (n - 1) + bt),
                    (x0, af * x0 + bf, n - 1, af * (n - 1) + bf),
                ], n - 1)

    # Suporte / resistência por agrupamento de pivôs (>= 3 toques)
    todos = sorted(p for _, p in topos + fundos)
    clusters: list[list[float]] = []
    for p in todos:
        if clusters and abs(p - np.mean(clusters[-1])) / np.mean(clusters[-1]) <= 0.015:
            clusters[-1].append(p)
        else:
            clusters.append([p])
    niveis_all = [(float(np.mean(cl)), len(cl)) for cl in clusters if len(cl) >= 3]
    ultimo = float(c[-1])
    abaixo = sorted([x for x in niveis_all if x[0] <= ultimo], reverse=True)[:2]
    acima = sorted([x for x in niveis_all if x[0] > ultimo])[:2]
    niveis = ([{"tipo": "Suporte", "preco": p, "toques": t} for p, t in abaixo]
              + [{"tipo": "Resistência", "preco": p, "toques": t} for p, t in acima])
    return pats, niveis


# ------------------------------------------------------------------ indicadores
def rsi(c: pd.Series, n: int = 14) -> pd.Series:
    d = c.diff()
    ganho = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    perda = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + ganho / perda.replace(0, np.nan))


def indicadores(df: pd.DataFrame, mm_curta: int = 21, mm_longa: int = 50, ifr_n: int = 14) -> dict:
    c, o, h, l, v = df["Close"], df["Open"], df["High"], df["Low"], df["Volume"]
    mc, ml = c.rolling(mm_curta).mean(), c.rolling(mm_longa).mean()
    r = rsi(c, ifr_n)
    vm = v.rolling(20).mean()

    regras = [
        (f"Cruzamento MM{mm_curta}/{mm_longa} (alta)", ALTA, (mc > ml) & (mc.shift(1) <= ml.shift(1))),
        (f"Cruzamento MM{mm_curta}/{mm_longa} (baixa)", BAIXA, (mc < ml) & (mc.shift(1) >= ml.shift(1))),
        ("IFR saindo de sobrevenda", ALTA, (r > 30) & (r.shift(1) <= 30)),
        ("IFR saindo de sobrecompra", BAIXA, (r < 70) & (r.shift(1) >= 70)),
        ("Volume forte + candle de alta", ALTA, (v > 2 * vm) & (c > o)),
        ("Volume forte + candle de baixa", BAIXA, (v > 2 * vm) & (c < o)),
    ]
    sinais = []
    for nome, tipo, mask in regras:
        for i in np.flatnonzero(mask.to_numpy(dtype=bool)):
            preco = l.iloc[i] if tipo == ALTA else h.iloc[i]
            sinais.append(_sinal(df.index[i], nome, tipo, preco, "Indicador"))
    return {"sinais": sinais, "mm_curta": mc, "mm_longa": ml, "ifr": r,
            "n_curta": mm_curta, "n_longa": mm_longa}


# ------------------------------------------------------------------ figura
def figura(df, sinais, padroes, niveis, ind, diario=True, altura=700, mostrar_mm=True):
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.62, 0.15, 0.23],
                        vertical_spacing=0.025)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing_line_color=UP, increasing_fillcolor=UP,
        decreasing_line_color=DOWN, decreasing_fillcolor=DOWN,
        name="Preço", showlegend=False), row=1, col=1)

    if mostrar_mm and ind:
        fig.add_trace(go.Scatter(x=df.index, y=ind["mm_curta"], mode="lines", name=f"MM{ind['n_curta']}",
                                 line=dict(color=GOLD, width=1.2)), row=1, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=ind["mm_longa"], mode="lines", name=f"MM{ind['n_longa']}",
                                 line=dict(color=ACCENT, width=1.2)), row=1, col=1)

    estilos = {
        ALTA: ("triangle-up", UP, "Sinal de alta", -1),
        BAIXA: ("triangle-down", DOWN, "Sinal de baixa", 1),
        NEUTRO: ("diamond", MUTED, "Indecisão", 1),
    }
    for tipo, (simb, cor, rot, sgn) in estilos.items():
        pts = [s for s in sinais if s["tipo"] == tipo]
        if not pts:
            continue
        fig.add_trace(go.Scatter(
            x=[p["data"] for p in pts], y=[p["preco"] * (1 + 0.012 * sgn) for p in pts],
            mode="markers", name=rot, text=[p["sinal"] for p in pts],
            marker=dict(symbol=simb, size=9, color=cor, line=dict(width=0)),
            hovertemplate="%{text}<br>%{x|%d/%m/%Y}<extra></extra>"), row=1, col=1)

    cores = {ALTA: UP, BAIXA: DOWN, NEUTRO: ACCENT}
    for p in padroes:
        cor = cores[p["tipo"]]
        for x0, y0, x1, y1 in p["linhas"]:
            fig.add_trace(go.Scatter(x=[df.index[x0], df.index[x1]], y=[y0, y1], mode="lines",
                                     line=dict(color=cor, width=1.4, dash="dash"),
                                     showlegend=False, hoverinfo="skip"), row=1, col=1)
        if p["pontos"]:
            fig.add_trace(go.Scatter(x=[df.index[i] for i, _ in p["pontos"]], y=[y for _, y in p["pontos"]],
                                     mode="markers", marker=dict(size=6, color=cor),
                                     showlegend=False, hoverinfo="skip"), row=1, col=1)
        fig.add_annotation(x=df.index[p["ref"]], y=p["preco"], text=p["nome"], showarrow=True,
                           arrowcolor=cor, arrowwidth=1, ax=0, ay=36 if p["tipo"] == ALTA else -36,
                           font=dict(size=10, color=cor), row=1, col=1)

    for nv in niveis:
        fig.add_hline(y=nv["preco"], row=1, col=1, line=dict(color=ACCENT, width=1, dash="dot"),
                      annotation_text=f"{nv['tipo']} {nv['preco']:.2f} ({nv['toques']}x)",
                      annotation_position="top left", annotation_font=dict(size=10, color=MUTED))

    cores_vol = ["rgba(111,156,133,.55)" if cl >= op else "rgba(176,112,107,.55)"
                 for cl, op in zip(df["Close"], df["Open"])]
    fig.add_trace(go.Bar(x=df.index, y=df["Volume"], marker_color=cores_vol, showlegend=False,
                         name="Volume"), row=2, col=1)

    if ind:
        fig.add_trace(go.Scatter(x=df.index, y=ind["ifr"], mode="lines", showlegend=False, name="IFR",
                                 line=dict(color=ACCENT, width=1.2)), row=3, col=1)
        for nivel in (30, 70):
            fig.add_hline(y=nivel, row=3, col=1, line=dict(color=MUTED, width=1, dash="dot"))
    fig.update_yaxes(range=[0, 100], title_text="IFR", row=3, col=1)
    fig.update_yaxes(title_text="Vol.", row=2, col=1)

    fig.update_layout(
        height=altura, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(color=TEXT, size=12), margin=dict(l=10, r=10, t=30, b=10),
        legend=dict(orientation="h", y=1.05, x=0), xaxis_rangeslider_visible=False,
        bargap=0.1,
    )
    fig.update_xaxes(gridcolor=GRID, showgrid=True, zeroline=False)
    fig.update_yaxes(gridcolor=GRID, zeroline=False)
    if diario:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig
