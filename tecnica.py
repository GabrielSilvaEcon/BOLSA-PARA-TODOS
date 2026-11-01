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


# ------------------------------------------------------------------ figura (estilo TradingView)
# Paleta do TradingView (tema claro, combinando com o gráfico limpo ao lado)
TV = {
    "claro": dict(bg="#ffffff", texto="#131722", muted="#787b86", grade="#f0f3fa", borda="#e0e3eb",
                  alta="#089981", baixa="#f23645", mm1="#ff9800", mm2="#2962ff", ifr="#7e57c2",
                  faixa="rgba(126,87,194,.08)", vol_a="rgba(8,153,129,.45)", vol_b="rgba(242,54,69,.45)",
                  neutro="#9598a1", zona_a="rgba(8,153,129,.13)", zona_b="rgba(242,54,69,.13)",
                  rotulo="#131722", rotulo_txt="#ffffff"),
    "escuro": dict(bg="#131722", texto="#d1d4dc", muted="#787b86", grade="#1e222d", borda="#2a2e39",
                   alta="#26a69a", baixa="#ef5350", mm1="#ff9800", mm2="#2962ff", ifr="#b39ddb",
                   faixa="rgba(179,157,219,.10)", vol_a="rgba(38,166,154,.45)", vol_b="rgba(239,83,80,.45)",
                   neutro="#868993", zona_a="rgba(38,166,154,.15)", zona_b="rgba(239,83,80,.15)",
                   rotulo="#d1d4dc", rotulo_txt="#131722"),
}


def so_atuais(itens: list[dict], df: pd.DataFrame, ultimos: int = 3) -> list[dict]:
    """Mantém só os sinais/padrões dos últimos `ultimos` candles: sinal que já passou não aparece no gráfico."""
    if not itens or df.empty:
        return []
    corte = df.index[max(0, len(df) - ultimos)]
    return [s for s in itens if s["data"] >= corte]


def padroes_atuais(padroes: list[dict], df: pd.DataFrame, janela: int = 25) -> list[dict]:
    """Padrões gráficos cujo ponto de referência é recente (últimos `janela` candles)."""
    return [p for p in padroes if p["ref"] >= len(df) - janela]


def _fmt(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def figura(df, sinais, padroes, niveis, ind, diario=True, altura=700, mostrar_mm=True, zonas=None,
           tema="claro", candles_visiveis=120, sinais_ultimos=3):
    t = TV.get(tema, TV["claro"])
    n = len(df)
    sinais = so_atuais(sinais, df, sinais_ultimos)
    padroes = padroes_atuais(padroes, df)

    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.66, 0.14, 0.20],
                        vertical_spacing=0.012)
    x = df.index
    # candles cheios: corpo e pavio na mesma cor, como no TradingView
    fig.add_trace(go.Candlestick(
        x=x, open=df["Open"], high=df["High"], low=df["Low"], close=df["Close"],
        increasing=dict(line=dict(color=t["alta"], width=1), fillcolor=t["alta"]),
        decreasing=dict(line=dict(color=t["baixa"], width=1), fillcolor=t["baixa"]),
        whiskerwidth=0, name="Preço", showlegend=False, opacity=1,
        hoverlabel=dict(bgcolor=t["bg"], bordercolor=t["borda"], font=dict(color=t["texto"], size=12)),
    ), row=1, col=1)

    legenda = []
    if mostrar_mm and ind:
        for chave, nome, cor in (("mm_curta", f"MM{ind['n_curta']}", t["mm1"]),
                                 ("mm_longa", f"MM{ind['n_longa']}", t["mm2"])):
            serie = ind[chave]
            fig.add_trace(go.Scatter(x=x, y=serie, mode="lines", name=nome, showlegend=False,
                                     line=dict(color=cor, width=1.3), hoverinfo="skip"), row=1, col=1)
            ult = serie.dropna()
            if len(ult):
                legenda.append(f"<span style='color:{cor}'>● {nome} {_fmt(ult.iloc[-1])}</span>")

    # sinais atuais: marcadores pequenos encostados no candle, com texto só no hover
    ampl = float((df["High"] - df["Low"]).tail(30).mean()) or float(df["Close"].iloc[-1]) * 0.01
    estilos = {ALTA: ("triangle-up", t["alta"], "Sinal de alta", -1),
               BAIXA: ("triangle-down", t["baixa"], "Sinal de baixa", 1),
               NEUTRO: ("diamond", t["neutro"], "Indecisão", 1)}
    for tipo, (simb, cor, rot, sgn) in estilos.items():
        pts = [s for s in sinais if s["tipo"] == tipo]
        if not pts:
            continue
        fig.add_trace(go.Scatter(
            x=[p["data"] for p in pts], y=[p["preco"] + sgn * 0.45 * ampl for p in pts],
            mode="markers", name=rot, showlegend=False, customdata=[p["sinal"] for p in pts],
            marker=dict(symbol=simb, size=10, color=cor, line=dict(width=1, color=t["bg"])),
            hovertemplate="<b>%{customdata}</b><br>%{x|%d/%m/%Y}<extra></extra>"), row=1, col=1)
        legenda.append(f"<span style='color:{cor}'>{'▲' if tipo == ALTA else '▼' if tipo == BAIXA else '◆'} "
                       f"{len(pts)} {rot.lower()}</span>")

    cores = {ALTA: t["alta"], BAIXA: t["baixa"], NEUTRO: t["mm2"]}
    for p in padroes:
        cor = cores[p["tipo"]]
        for x0, y0, x1, y1 in p["linhas"]:
            fig.add_trace(go.Scatter(x=[x[x0], x[x1]], y=[y0, y1], mode="lines",
                                     line=dict(color=cor, width=1.3, dash="dash"),
                                     showlegend=False, hoverinfo="skip"), row=1, col=1)
        if p["pontos"]:
            fig.add_trace(go.Scatter(x=[x[i] for i, _ in p["pontos"]], y=[y for _, y in p["pontos"]],
                                     mode="markers", marker=dict(size=6, color=cor),
                                     showlegend=False, hoverinfo="skip"), row=1, col=1)
        fig.add_annotation(x=x[p["ref"]], y=p["preco"], text=p["nome"], showarrow=True, arrowcolor=cor,
                           arrowwidth=1, arrowhead=0, ax=0, ay=40 if p["tipo"] == ALTA else -40,
                           font=dict(size=11, color=cor), bgcolor=t["bg"], bordercolor=cor, borderwidth=1,
                           borderpad=3, row=1, col=1)

    for z in (zonas or []):
        fig.add_shape(type="rect", x0=z["x0"], x1=z["x1"], y0=z["y0"], y1=z["y1"],
                      fillcolor=t["zona_a"] if z["tipo"] == ALTA else t["zona_b"],
                      line=dict(width=0), layer="below", row=1, col=1)

    for nv in niveis:
        fig.add_hline(y=nv["preco"], row=1, col=1, line=dict(color=t["muted"], width=1, dash="dot"),
                      annotation_text=f"{nv['tipo']} {_fmt(nv['preco'])}", annotation_position="top left",
                      annotation_font=dict(size=10, color=t["muted"]))

    # linha e etiqueta do último preço, no eixo da direita
    ult, ant = float(df["Close"].iloc[-1]), float(df["Open"].iloc[-1])
    cor_ult = t["alta"] if ult >= ant else t["baixa"]
    fig.add_hline(y=ult, row=1, col=1, line=dict(color=cor_ult, width=1, dash="dot"))
    fig.add_annotation(xref="paper", x=1, yref="y", y=ult, text=f"<b>{_fmt(ult)}</b>", showarrow=False,
                       xanchor="left", xshift=2, bgcolor=cor_ult, font=dict(color="#ffffff", size=11),
                       borderpad=3)

    # volume
    sobe = (df["Close"] >= df["Open"]).to_numpy()
    fig.add_trace(go.Bar(x=x, y=df["Volume"], marker=dict(color=[t["vol_a"] if s else t["vol_b"] for s in sobe],
                                                          line=dict(width=0)),
                         showlegend=False, name="Volume",
                         hovertemplate="Vol. %{y:,.0f}<extra></extra>"), row=2, col=1)

    # IFR com faixa 30–70 sombreada
    if ind:
        fig.add_hrect(y0=30, y1=70, fillcolor=t["faixa"], line_width=0, row=3, col=1)
        for nivel in (30, 70):
            fig.add_hline(y=nivel, row=3, col=1, line=dict(color=t["muted"], width=1, dash="dash"))
        fig.add_trace(go.Scatter(x=x, y=ind["ifr"], mode="lines", showlegend=False, name="IFR",
                                 line=dict(color=t["ifr"], width=1.4),
                                 hovertemplate="IFR %{y:.1f}<extra></extra>"), row=3, col=1)
        ifr_ult = ind["ifr"].dropna()
        if len(ifr_ult):
            fig.add_annotation(xref="x domain", yref="y3 domain", x=0.005, y=0.95, showarrow=False,
                               xanchor="left", yanchor="top", font=dict(size=11, color=t["ifr"]),
                               text=f"IFR 14 · {ifr_ult.iloc[-1]:.1f}")
    fig.add_annotation(xref="x domain", yref="y2 domain", x=0.005, y=0.95, showarrow=False, xanchor="left",
                       yanchor="top", font=dict(size=11, color=t["muted"]), text="Volume")

    if legenda:
        fig.add_annotation(xref="x domain", yref="y domain", x=0.005, y=0.995, showarrow=False,
                           xanchor="left", yanchor="top", align="left", font=dict(size=12, color=t["texto"]),
                           text="  ".join(legenda))

    fig.update_layout(
        height=altura, paper_bgcolor=t["bg"], plot_bgcolor=t["bg"],
        font=dict(color=t["texto"], size=12, family="Inter, -apple-system, 'Segoe UI', Roboto, sans-serif"),
        margin=dict(l=8, r=64, t=8, b=8), showlegend=False, xaxis_rangeslider_visible=False,
        bargap=0.15, dragmode="pan", hovermode="x", spikedistance=-1,
        hoverlabel=dict(bgcolor=t["bg"], bordercolor=t["borda"], font=dict(color=t["texto"], size=12)),
    )

    # janela inicial: últimos N candles, com eixo Y ajustado a eles (o resto fica disponível ao arrastar)
    ini = max(0, n - candles_visiveis)
    vis = df.iloc[ini:]
    lo, hi = float(vis["Low"].min()), float(vis["High"].max())
    if mostrar_mm and ind:
        for chave in ("mm_curta", "mm_longa"):
            s = ind[chave].iloc[ini:].dropna()
            if len(s):
                lo, hi = min(lo, float(s.min())), max(hi, float(s.max()))
    folga = (hi - lo) * 0.06
    passo = x.to_series().diff().median() if n > 2 else pd.Timedelta(days=1)
    fig.update_xaxes(range=[x[ini], x[-1] + passo * 6], showgrid=True, gridcolor=t["grade"], gridwidth=1,
                     zeroline=False, showline=True, linecolor=t["borda"], tickfont=dict(color=t["muted"], size=11),
                     showspikes=True, spikemode="across", spikesnap="cursor", spikecolor=t["muted"],
                     spikethickness=1, spikedash="dash")
    fig.update_xaxes(showticklabels=False, row=1, col=1)
    fig.update_xaxes(showticklabels=False, row=2, col=1)
    fig.update_yaxes(side="right", showgrid=True, gridcolor=t["grade"], gridwidth=1, zeroline=False,
                     showline=True, linecolor=t["borda"], tickfont=dict(color=t["muted"], size=11),
                     showspikes=True, spikemode="across", spikecolor=t["muted"], spikethickness=1,
                     spikedash="dash", fixedrange=False)
    fig.update_yaxes(range=[lo - folga, hi + folga], row=1, col=1)
    fig.update_yaxes(range=[0, 100], tickvals=[30, 50, 70], row=3, col=1)
    fig.update_yaxes(tickformat=".2s", row=2, col=1)
    if diario:
        fig.update_xaxes(rangebreaks=[dict(bounds=["sat", "mon"])])
    return fig


# configuração do st.plotly_chart: zoom com a rodinha, arrastar para mover, barra de ferramentas enxuta
CONFIG_GRAFICO = {
    "displaylogo": False, "scrollZoom": True, "doubleClick": "reset",
    "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d", "toImage", "zoomIn2d", "zoomOut2d",
                               "hoverClosestCartesian", "hoverCompareCartesian", "toggleSpikelines"],
}
