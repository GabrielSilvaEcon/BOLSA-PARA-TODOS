"""Gráficos e tabelas no padrão visual escuro do app (módulo puro, sem Streamlit).
 - `tema_escuro(fig)`: tema único para qualquer figura Plotly (fundo transparente, texto claro, grade suave, paleta legível, dica escura).
   Só estilo: nunca altera dados.
 - `fundo_grafico()` / `fundo_tabela()`: ilustração própria de fundo (data URI de SVG) para os cartões de gráfico e de tabela.
 - `css()`: aplica cartão arredondado com ilustração a todo st.plotly_chart e aos cartões de tabela (.dz-tc).
"""
from __future__ import annotations

from urllib.parse import quote

TEXTO = "#EDE9FF"
APOIO = "#BDB5E6"
GRADE = "rgba(255,255,255,.08)"
ZERO = "rgba(255,255,255,.28)"
PALETA = ("#8B6CFF", "#2EE59D", "#FFD76A", "#FF6B9A", "#4CC9F0", "#FF9F5A", "#C5B3FF", "#7BE0C3")
GANHO, PERDA = "#2EE59D", "#FF6B6B"
TIPOS_SEM_EIXO = {"pie", "sunburst", "treemap", "indicator", "table", "sankey", "scatterpolar", "funnelarea"}


def _uri(svg: str) -> str:
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;'()")


def fundo_grafico() -> str:
    """Brilho violeta no canto, linha de alta suave e pontos de luz."""
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 260' preserveAspectRatio='xMaxYMax slice'><defs>"
           "<radialGradient id='o' cx='.9' cy='.05' r='.7'><stop offset='0' stop-color='#8B6CFF' stop-opacity='.28'/><stop offset='1' stop-color='#8B6CFF' stop-opacity='0'/></radialGradient>"
           "<linearGradient id='l' x1='0' y1='0' x2='1' y2='0'><stop offset='0' stop-color='#2EE59D' stop-opacity='0'/><stop offset='1' stop-color='#2EE59D' stop-opacity='.35'/></linearGradient></defs>"
           "<rect width='400' height='260' fill='url(#o)'/>"
           "<polyline points='0,230 60,210 120,222 190,170 250,180 320,120 400,70' fill='none' stroke='url(#l)' stroke-width='3' stroke-linecap='round'/>"
           "<circle cx='400' cy='70' r='5' fill='#2EE59D' opacity='.5'/><circle cx='40' cy='40' r='2.5' fill='#fff' opacity='.35'/>"
           "<circle cx='330' cy='235' r='9' fill='none' stroke='#FFD76A' stroke-width='2' opacity='.25'/></svg>")
    return _uri(svg)


def fundo_tabela() -> str:
    """Degraus translúcidos e moedas no canto direito."""
    barras = "".join(f"<rect x='{x}' y='{y}' width='22' height='{120 - y}' rx='4' fill='#8B6CFF' opacity='.12'/>" for x, y in ((250, 90), (278, 70), (306, 48), (334, 26)))
    svg = ("<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 120' preserveAspectRatio='xMaxYMid slice'><defs>"
           "<radialGradient id='o' cx='.95' cy='.2' r='.6'><stop offset='0' stop-color='#8B6CFF' stop-opacity='.22'/><stop offset='1' stop-color='#8B6CFF' stop-opacity='0'/></radialGradient></defs>"
           "<rect width='400' height='120' fill='url(#o)'/>" + barras +
           "<circle cx='372' cy='98' r='9' fill='none' stroke='#FFD76A' stroke-width='2' opacity='.3'/>"
           "<circle cx='372' cy='98' r='4.5' fill='#FFD76A' opacity='.12'/></svg>")
    return _uri(svg)


def tema_escuro(fig):
    """Aplica o tema escuro único. Nunca levanta erro; devolve a mesma figura."""
    try:
        if fig is None or not hasattr(fig, "update_layout"):
            return fig
        tipos = {getattr(t, "type", "") for t in fig.data}
        cartesiano = bool(tipos) and not (tipos & TIPOS_SEM_EIXO)
        fig.update_layout(font=dict(family="Inter, system-ui, -apple-system, Segoe UI, sans-serif", size=12, color=TEXTO),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", colorway=list(PALETA),
                          hoverlabel=dict(bgcolor="#2A1F5E", bordercolor="#8B6CFF", font=dict(color="#FFFFFF", size=12)),
                          legend=dict(font=dict(color=TEXTO, size=11), bgcolor="rgba(0,0,0,0)"))
        if cartesiano:
            ax = dict(gridcolor=GRADE, zerolinecolor=ZERO, linecolor=ZERO, tickfont=dict(color=TEXTO), title_font=dict(color=APOIO), automargin=True)
            fig.update_xaxes(**ax)
            fig.update_yaxes(**ax)
        if "bar" in tipos and not fig.layout.bargap:
            fig.update_layout(bargap=0.3)
        if "bar" in tipos:
            try:
                fig.update_traces(marker_cornerradius=6, selector=dict(type="bar"))   # exige Plotly recente; sem ele, barras retas
            except Exception:
                pass
        if "pie" in tipos:
            fig.update_traces(marker=dict(line=dict(color="#1B1442", width=2)), selector=dict(type="pie"))
    except Exception:
        pass
    return fig


def css() -> str:
    q = "html body .stApp.stApp.stApp"
    g, t = fundo_grafico(), fundo_tabela()
    return ("<style>"
            f"{q} [data-testid='stPlotlyChart']{{background-color:#1B1442 !important;background-image:url(\"{g}\") !important;background-repeat:no-repeat !important;"
            "background-position:right bottom !important;background-size:cover !important;border:1px solid rgba(189,181,230,.22) !important;"
            "border-radius:20px !important;padding:10px 8px 4px !important;overflow:hidden;box-shadow:0 8px 24px rgba(8,5,30,.35) !important}}"
            f"{q} [data-testid='stPlotlyChart'] .modebar{{background:transparent !important}}"
            f"{q} [data-testid='stPlotlyChart'] .modebar-btn path{{fill:#BDB5E6 !important}}"
            f"{q} .dz-tc{{background-color:#1B1442 !important;background-image:url(\"{t}\") !important;background-repeat:no-repeat !important;"
            "background-position:right center !important;background-size:cover !important;border:1px solid rgba(189,181,230,.22) !important;"
            "border-radius:18px !important;padding:12px 14px !important;box-shadow:0 6px 18px rgba(8,5,30,.3)}"
            f"{q} .dz-tc-t{{font-size:.95rem}}"
            f"{q} [data-testid='stDataFrame'],{q} [data-testid='stTable']{{background-color:#1B1442 !important;background-image:url(\"{t}\") !important;"
            "background-repeat:no-repeat !important;background-position:right top !important;background-size:cover !important;"
            "border:1px solid rgba(189,181,230,.22) !important;border-radius:18px !important}"
            "</style>")
