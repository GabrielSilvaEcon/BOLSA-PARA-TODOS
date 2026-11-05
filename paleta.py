"""Paleta de cores do app, montada com o círculo cromático (módulo puro, sem Streamlit).

Base: índigo-violeta (matiz ~250°), o mesmo azul da marca Bússola B3, escurecido para os fundos.
 - Análogas (vizinhas na roda): violeta 262° e azul-pervinca 228° -> marca, links, destaques de interface.
 - Complementar: ouro 42° (oposto do azul-violeta) -> avisos, selo B3, realces.
 - Magenta 318° (tríade com o violeta) -> o brilho do degradê dos botões e da tela de entrada.
 - Semânticas (só significam resultado): verde-menta 152° = bom/ganho, vermelho-rosado 352° = ruim/perda.
Todo par texto/fundo usado no app passa em `contraste()` com razão mínima 4,5:1 (conferido em tests/test_paleta.py).
"""
from __future__ import annotations

import colorsys

# ---- fundos (índigo escuro, do mais fundo ao mais alto)
BG = "#110C2E"           # fundo do app
BG_2 = "#1B1442"         # cartões e painéis
BG_3 = "#2A1F5E"         # elementos elevados (menus, dicas, avisos)
BG_FUNDO = "#0B0821"     # degradê mais escuro da tela de entrada

# ---- textos
TEXTO = "#FFFFFF"        # títulos e texto principal
TEXTO_2 = "#EDE9FF"      # texto corrido sobre cartões
MUDO = "#BDB5E6"         # legendas e apoio
LINHA = "rgba(189,181,230,.22)"

# ---- marca (análogas)
MARCA = "#8B6CFF"        # violeta: realces, links
MARCA_CLARA = "#C5B3FF"  # violeta claro para texto sobre fundo escuro
MARCA_ESCURA = "#5B3FD6"
MAGENTA = "#D23FC8"      # brilho do degradê
PERVINCA = "#7A8CFF"     # info
OURO = "#F2B84B"         # complementar: avisos / selo

# ---- semânticas
BOM = "#3DDC97"
REGULAR = OURO
RUIM = "#FF6B6B"
INFO = "#8EA2FF"
NEUTRO = MUDO

# ---- gráficos: oito matizes espalhados pela roda, mesmo brilho, distintos entre si
PALETA_GRAFICOS = ("#7A6CF0", "#2FB67C", "#E0A030", "#E0556B", "#2BA7C9", "#C74BB8", "#5A7BE8", "#8FB83A")

# ---- degradê do botão principal e da tela de entrada
BOTAO_A, BOTAO_B = "#6E4BFF", "#B02FC8"


def _lin(c: int) -> float:
    v = c / 255
    return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4


def _rgb(hexa: str) -> tuple[int, int, int]:
    h = hexa.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def luminancia(hexa: str) -> float:
    r, g, b = _rgb(hexa)
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contraste(a: str, b: str) -> float:
    """Razão de contraste WCAG entre duas cores #RRGGBB (de 1 a 21)."""
    la, lb = sorted((luminancia(a), luminancia(b)), reverse=True)
    return (la + 0.05) / (lb + 0.05)


def matiz(hexa: str) -> float:
    r, g, b = (x / 255 for x in _rgb(hexa))
    return colorsys.rgb_to_hls(r, g, b)[0] * 360
