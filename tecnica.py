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


# ------------------------------------------------------------------ setups operacionais
SETUP_NOMES = ["Inside Bar", "Setup 9.1 (Larry Williams)", "Cruzamento MME 9/21",
               "Rompimento com volume", "Fair Value Gap", "Pin Bar"]


def _brl(v) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _setup_sinal(df, i, nome, tipo, preco=None):
    """Sinal de setup no formato do gráfico: alta marca a mínima, baixa e indecisão marcam a máxima."""
    if preco is None:
        preco = df["Low"].iloc[i] if tipo == ALTA else df["High"].iloc[i]
    return _sinal(df.index[i], nome, tipo, preco, "Setup")


def setup_inside_bar(df: pd.DataFrame):
    """Inside Bar: candle totalmente dentro da faixa (máxima e mínima) do candle anterior, a barra mãe.
    Compra se um candle seguinte romper a máxima da barra mãe; venda se romper a mínima.
    Rompendo os dois lados no mesmo candle o sinal é ambíguo e não é emitido."""
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    sinais, alertas = [], []
    mae = None  # (índice, máxima, mínima) da barra mãe ainda sem rompimento
    for i in range(1, len(df)):
        if mae is not None:
            _, mh, ml = mae
            if h[i] <= mh and l[i] >= ml:
                sinais.append(_setup_sinal(df, i, "Inside Bar", NEUTRO))
                continue
            rompe_alta, rompe_baixa = h[i] > mh, l[i] < ml
            if rompe_alta and not rompe_baixa:
                sinais.append(_setup_sinal(df, i, "Inside Bar: rompeu a máxima da barra mãe (compra)", ALTA))
            elif rompe_baixa and not rompe_alta:
                sinais.append(_setup_sinal(df, i, "Inside Bar: rompeu a mínima da barra mãe (venda)", BAIXA))
            mae = None
            continue
        if h[i] < h[i - 1] and l[i] > l[i - 1]:
            mae = (i - 1, float(h[i - 1]), float(l[i - 1]))
            sinais.append(_setup_sinal(df, i, "Inside Bar", NEUTRO))
    if mae is not None:
        alertas.append((NEUTRO, f"Inside Bar ativa: compra se o preço romper a máxima da barra mãe ({_brl(mae[1])}); "
                                f"venda se romper a mínima ({_brl(mae[2])})."))
    return {"sinais": sinais, "zonas": [], "alertas": alertas}


def setup_91(df: pd.DataFrame, periodo: int = 9):
    """Setup 9.1 de Larry Williams. A MME de 9 períodos muda de inclinação: o candle da virada arma o setup e
    o gatilho é a máxima (compra) ou a mínima (venda) desse candle. O sinal sai quando um candle seguinte
    rompe o gatilho; o setup é cancelado se a média virar de novo antes disso."""
    ema = df["Close"].ewm(span=periodo, adjust=False).mean().to_numpy()
    h, l = df["High"].to_numpy(), df["Low"].to_numpy()
    sinais, alertas = [], []
    armado = None  # (direção, gatilho)
    for i in range(2, len(df)):
        sobe, desce = ema[i] > ema[i - 1], ema[i] < ema[i - 1]
        virou_alta = sobe and ema[i - 1] <= ema[i - 2]
        virou_baixa = desce and ema[i - 1] >= ema[i - 2]
        if armado is not None:
            dire, gat = armado
            if (dire == ALTA and desce) or (dire == BAIXA and sobe):
                armado = None  # inclinação virou contra o setup: cancelado
            elif (dire == ALTA and h[i] > gat) or (dire == BAIXA and l[i] < gat):
                nome = "Setup 9.1 compra (gatilho acionado)" if dire == ALTA else "Setup 9.1 venda (gatilho acionado)"
                sinais.append(_setup_sinal(df, i, nome, dire))
                armado = None
        if virou_alta:
            armado = (ALTA, float(h[i]))
        elif virou_baixa:
            armado = (BAIXA, float(l[i]))
    if armado is not None:
        dire, gat = armado
        if dire == ALTA:
            alertas.append((ALTA, f"Setup 9.1 armado (compra): a MME {periodo} virou para cima. "
                                  f"Gatilho: preço acima de {_brl(gat)}."))
        else:
            alertas.append((BAIXA, f"Setup 9.1 armado (venda): a MME {periodo} virou para baixo. "
                                   f"Gatilho: preço abaixo de {_brl(gat)}."))
    return {"sinais": sinais, "zonas": [], "alertas": alertas}


def setup_cruzamento_mme(df: pd.DataFrame, curta: int = 9, longa: int = 21):
    """Golden Cross (MME 9 cruza para cima a MME 21) e Death Cross (cruza para baixo)."""
    c = df["Close"]
    mc, ml = c.ewm(span=curta, adjust=False).mean(), c.ewm(span=longa, adjust=False).mean()
    golden = ((mc > ml) & (mc.shift(1) <= ml.shift(1))).to_numpy(dtype=bool)
    death = ((mc < ml) & (mc.shift(1) >= ml.shift(1))).to_numpy(dtype=bool)
    sinais = ([_setup_sinal(df, i, f"Golden Cross MME{curta}/{longa} (compra)", ALTA) for i in np.flatnonzero(golden)]
              + [_setup_sinal(df, i, f"Death Cross MME{curta}/{longa} (venda)", BAIXA) for i in np.flatnonzero(death)])
    return {"sinais": sinais, "zonas": [], "alertas": []}


def setup_rompimento_volume(df: pd.DataFrame, janela: int = 20):
    """Rompimento da máxima (resistência) ou da mínima (suporte) dos últimos `janela` candles, validado só se o
    volume do candle estiver acima da média de volume desses mesmos candles anteriores."""
    c, v = df["Close"], df["Volume"]
    resist = df["High"].rolling(janela).max().shift(1)
    suporte = df["Low"].rolling(janela).min().shift(1)
    vol_med = v.rolling(janela).mean().shift(1)
    forte = v > vol_med
    alta = ((c > resist) & forte).to_numpy(dtype=bool)
    baixa = ((c < suporte) & forte).to_numpy(dtype=bool)
    sinais = ([_setup_sinal(df, i, f"Rompimento de resistência de {janela} candles com volume (compra)", ALTA)
               for i in np.flatnonzero(alta)]
              + [_setup_sinal(df, i, f"Rompimento de suporte de {janela} candles com volume (venda)", BAIXA)
                 for i in np.flatnonzero(baixa)])
    return {"sinais": sinais, "zonas": [], "alertas": []}


def setup_fvg(df: pd.DataFrame, tamanho_min_pct: float = 0.3, max_zonas: int = 6):
    """Fair Value Gap (desequilíbrio) em três candles. Alta: a mínima do 3º candle fica acima da máxima do 1º.
    Baixa: a máxima do 3º fica abaixo da mínima do 1º. A zona é o espaço entre os dois e continua aberta
    enquanto nenhum candle posterior voltar a tocá-la. Gaps menores que `tamanho_min_pct` % do preço são ignorados."""
    h, l, c = df["High"].to_numpy(), df["Low"].to_numpy(), df["Close"].to_numpy()
    n = len(df)
    sinais, zonas = [], []
    for i in range(2, n):
        if l[i] > h[i - 2]:
            topo, base, tipo = float(l[i]), float(h[i - 2]), ALTA
        elif h[i] < l[i - 2]:
            topo, base, tipo = float(l[i - 2]), float(h[i]), BAIXA
        else:
            continue
        if c[i - 1] <= 0 or (topo - base) / c[i - 1] * 100 < tamanho_min_pct:
            continue
        nome = "FVG de alta (desequilíbrio)" if tipo == ALTA else "FVG de baixa (desequilíbrio)"
        sinais.append(_setup_sinal(df, i, nome, tipo))
        depois_l, depois_h = l[i + 1:], h[i + 1:]
        tocou = bool((depois_l <= topo).any()) if tipo == ALTA else bool((depois_h >= base).any())
        if not tocou:
            zonas.append({"x0": df.index[i - 2], "x1": df.index[-1], "y0": base, "y1": topo, "tipo": tipo})
    zonas = zonas[-max_zonas:]
    alertas = []
    ultimo = df.index[-1]
    for s in sinais:
        if s["data"] == ultimo:
            alertas.append((s["tipo"], f"{s['sinal']} formado no último candle."))
    for z in zonas[-2:]:
        lado = "alta" if z["tipo"] == ALTA else "baixa"
        alertas.append((NEUTRO, f"FVG de {lado} ainda aberto entre {_brl(z['y0'])} e {_brl(z['y1'])}."))
    return {"sinais": sinais, "zonas": zonas, "alertas": alertas}


def setup_pin_bar(df: pd.DataFrame, pavio_pct: float = 60.0):
    """Pin Bar (rejeição): o pavio inferior (compra) ou superior (venda) ocupa pelo menos `pavio_pct` % do
    tamanho total do candle (máxima menos mínima)."""
    o, h, l, c = df["Open"], df["High"], df["Low"], df["Close"]
    rng = (h - l).replace(0, np.nan)
    inf = (np.minimum(o, c) - l) / rng
    sup = (h - np.maximum(o, c)) / rng
    lim = pavio_pct / 100
    alta = (inf >= lim).to_numpy(dtype=bool)
    baixa = (sup >= lim).to_numpy(dtype=bool)
    sinais = []
    for i in range(len(df)):
        if alta[i] and baixa[i]:
            continue  # pavio dos dois lados ≥ limite só ocorre com limite baixo: sem direção clara
        if alta[i]:
            sinais.append(_setup_sinal(df, i, f"Pin Bar de alta (pavio inferior ≥ {pavio_pct:.0f}%)", ALTA))
        elif baixa[i]:
            sinais.append(_setup_sinal(df, i, f"Pin Bar de baixa (pavio superior ≥ {pavio_pct:.0f}%)", BAIXA))
    return {"sinais": sinais, "zonas": [], "alertas": []}


def setups(df: pd.DataFrame, escolhidos: list[str], janela: int = 20, pavio_pct: float = 60.0,
           fvg_min_pct: float = 0.3) -> dict:
    """Roda os setups escolhidos. Devolve {'sinais', 'zonas', 'alertas'}; os alertas são os do último candle
    (setups armados ou sinais acionados nele), na ordem em que foram pedidos."""
    funcoes = {
        "Inside Bar": setup_inside_bar,
        "Setup 9.1 (Larry Williams)": setup_91,
        "Cruzamento MME 9/21": setup_cruzamento_mme,
        "Rompimento com volume": lambda d: setup_rompimento_volume(d, janela),
        "Fair Value Gap": lambda d: setup_fvg(d, fvg_min_pct),
        "Pin Bar": lambda d: setup_pin_bar(d, pavio_pct),
    }
    out = {"sinais": [], "zonas": [], "alertas": []}
    if len(df) < 3:
        return out
    ultimo = df.index[-1]
    for nome in SETUP_NOMES:
        if nome not in escolhidos:
            continue
        r = funcoes[nome](df)
        out["sinais"] += r["sinais"]
        out["zonas"] += r["zonas"]
        out["alertas"] += r["alertas"]
        ja = {t for _, t in r["alertas"]}
        for s in r["sinais"]:  # sinal que saiu exatamente no último candle
            txt = f"{s['sinal']} no último candle."
            if s["data"] == ultimo and s["tipo"] != NEUTRO and txt not in ja and not nome == "Fair Value Gap":
                out["alertas"].append((s["tipo"], txt))
    return out


# ------------------------------------------------------------------ figura
def figura(df, sinais, padroes, niveis, ind, diario=True, altura=700, mostrar_mm=True, zonas=None):
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

    for z in (zonas or []):
        cor_z = "rgba(111,156,133,.22)" if z["tipo"] == ALTA else "rgba(176,112,107,.22)"
        fig.add_shape(type="rect", x0=z["x0"], x1=z["x1"], y0=z["y0"], y1=z["y1"], fillcolor=cor_z,
                      line=dict(width=0), layer="below", row=1, col=1)

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
