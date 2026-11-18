"""Cabeçalho global do TickerHunters (única fonte de estilo).

Linha 1 (container `topo_perfil`, criado em app._topo_acoes): logo + nome à esquerda; busca, sino e perfil à direita. Fica sobre o cabeçalho
nativo do Streamlit (o menu ⋮ dele continua livre à direita).
A antiga linha 2 (faixa de indicadores) saiu: sequência, XP, Ticker Coins e patrimônio ficam no Meu Perfil e na Minha Carteira.
`css_topo` é o estilo (cabeçalho escuro com linha verde neon e traço diagonal, sino com contador). O design/css.py cuida da posição base.
"""
from __future__ import annotations

Q = "html body .stApp.stApp.stApp"
LARGURA = 1100            # largura útil no computador: a faixa e a linha 1 se alinham com o conteúdo



def css_topo(n_alertas: int = 0) -> str:
    """Cabeçalho no padrão de referência: fundo escuro em degradê, linha verde neon embaixo, traço diagonal de luz; sino com contador.
    Sem a faixa de indicadores (o conteúdo começa logo abaixo do cabeçalho)."""
    sino = (f'{Q} .st-key-topo_perfil [data-testid="stPageLink"] a::after{{content:"{n_alertas if n_alertas < 100 else "99+"}";position:absolute;top:3px;right:2px;'
            "min-width:18px;height:18px;padding:0 4px;box-sizing:border-box;border-radius:9px;background:#FF3B30;color:#fff;font-size:.62rem;font-weight:800;"
            "display:grid;place-items:center;line-height:1}") if n_alertas > 0 else ""
    return "<style>" + (
        f'{Q} .st-key-topo_perfil [data-testid="stPageLink"]{{width:auto !important}}'
        f'{Q} .st-key-topo_perfil [data-testid="stPageLink"] a[data-testid="stPageLink-NavLink"]{{position:relative;overflow:visible;width:44px !important;min-width:44px !important;'
        "height:44px !important;min-height:44px !important;padding:0 !important;justify-content:center !important;background:transparent !important;border:0 !important;box-shadow:none !important}"
        f'{Q} .st-key-topo_perfil a [data-testid="stIconMaterial"]{{font-size:26px !important;color:var(--dz-texto) !important}}'
        + sino +
        f"@media (min-width:{LARGURA}px){{{Q} .st-key-topo_perfil{{padding-left:max(10px,calc((100vw - {LARGURA}px)/2)) !important;"
        f"right:max(44px,calc((100vw - {LARGURA}px)/2 + 44px)) !important}}}}"
        # ---- fundo do cabeçalho (o header nativo ocupa a largura toda, inclusive atrás do menu ⋮)
        f'{Q} header[data-testid="stHeader"]{{background:linear-gradient(100deg,#05130E 0%,#0A0B26 38%,#0D0930 62%,#07170F 100%) !important;'
        "border-bottom:2px solid #34E85E !important;box-shadow:0 1px 0 rgba(52,232,94,.35),0 6px 18px -6px rgba(52,232,94,.45) !important;overflow:hidden}"
        f'{Q} header[data-testid="stHeader"]::before{{content:"";position:absolute;top:-10px;bottom:-10px;left:56%;width:3px;transform:skewX(-38deg);'
        "background:linear-gradient(180deg,rgba(52,232,94,.85),rgba(52,232,94,0));box-shadow:0 0 10px rgba(52,232,94,.6);pointer-events:none}"
        f'{Q} header[data-testid="stHeader"]::after{{content:"";position:absolute;top:0;bottom:0;left:calc(56% + 18px);width:90px;transform:skewX(-38deg);'
        "background:linear-gradient(90deg,rgba(52,232,94,.10),rgba(52,232,94,0));pointer-events:none}"
        # blocos que só carregam <style> não ocupam espaço
        f'{Q} [data-testid="stMain"] [data-testid="stElementContainer"]:has(>[data-testid="stMarkdown"] style):not(:has(>[data-testid="stMarkdown"] :is(p,div,h1,h2,h3,h4,ul,ol,table,img,svg,a,span))){{display:none !important}}'
        f'{Q} [data-testid="stMain"] .block-container{{padding-top:calc(var(--dz-cab-h,48px) + 8px) !important}}'
        # sem vão no topo: blocos que só levam <style> e os invólucros do cabeçalho e da barra (que são fixos) não ocupam lugar na coluna
        f'{Q} [data-testid="stMain"] [data-testid="stElementContainer"]:has([data-testid="stMarkdownContainer"] > style)'
        ':not(:has([data-testid="stMarkdownContainer"] > :not(style))){display:none !important}'
        f'{Q} [data-testid="stLayoutWrapper"]:has(> :is(.st-key-topo_perfil,.st-key-barra_areas)){{display:contents !important}}'
        # iframes auxiliares de 1 px (scripts): continuam rodando, mas não aparecem nem ocupam espaço (antes era uma linha branca no topo)
        f'{Q} [data-testid="stElementContainer"][height="1px"]:has(iframe){{position:absolute !important;width:1px !important;height:1px !important;'
        "opacity:0 !important;pointer-events:none !important;overflow:hidden !important;margin:0 !important}"
    ) + "</style>"
