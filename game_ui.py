"""Kit visual "mobile game" do TickerHunters: peças reutilizáveis (HTML/CSS puros, sem Streamlit e sem dados).

Serve a Home agora e as próximas telas (Jogos, Carteira, Aprender, Ranking, Loja) depois, para o app inteiro ter a mesma cara.
Tudo o que é desenhado aqui é decoração ou estrutura: nenhum número, nome ou resultado é inventado neste arquivo.

Peças:
 · cores e `fundo(tema)`: ilustração própria de fundo para cada cartão (regra do app: todo cartão tem a sua);
 · `css_base()`: cartão com borda luminosa e relevo, ficha (chip), barra de progresso e barra em segmentos;
 · `css_cartao_botao(chave)`: transforma um cartão HTML em botão inteiro (o st.button fica por cima, invisível, e leva o toque);
 · ícones desenhados em SVG (`icone`) e pequenos construtores de HTML (`barra`, `segmentos`, `ficha`).
"""
from __future__ import annotations

import html
from urllib.parse import quote

ROXO, AZUL, NOITE = "#8B6CFF", "#2E5BFF", "#0B0828"
OURO, VERDE, VERMELHO, CIANO = "#F2B84B", "#3DDC97", "#FF5B6E", "#2BA7C9"
Q = "html body .stApp.stApp.stApp"


def _e(x) -> str:
    return html.escape(str(x), quote=True)


def svg_uri(svg: str) -> str:
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:=,;")      # aspas e parênteses codificados: o URI cabe em url('...') dentro de style="..."


# ------------------------------------------------------------------ ilustrações de fundo (decoração, sem texto e sem números)
def _velas(xs, centros, altos, cor, mecha=9) -> str:
    out = ""
    for x, c, h in zip(xs, centros, altos):
        out += (f"<rect x='{x + 5}' y='{c - h / 2 - mecha}' width='2' height='{h + 2 * mecha}' fill='{cor}' opacity='.55'/>"
                f"<rect x='{x}' y='{c - h / 2}' width='12' height='{h}' rx='2.5' fill='{cor}' opacity='.8'/>")
    return out


def _faiscas(pontos, cor="#FFE08A") -> str:
    return "".join(f"<circle cx='{x}' cy='{y}' r='{r}' fill='{cor}' opacity='{o}'/>" for x, y, r, o in pontos)


def fundo(tema: str) -> str:
    """Ilustração de fundo (data URI de SVG) para um cartão. Temas: arena, jogador, marca, missoes, jogar, carteira, mercado."""
    glow = lambda cx, cy, r, cor, o: (f"<radialGradient id='g' cx='{cx}' cy='{cy}' r='{r}'><stop offset='0' stop-color='{cor}' stop-opacity='{o}'/>"
                                      f"<stop offset='1' stop-color='{cor}' stop-opacity='0'/></radialGradient>")
    if tema == "arena":      # compradores (velas verdes subindo) de um lado, vendedores (velas vermelhas caindo) do outro
        grade = "".join(f"<line x1='0' y1='{y}' x2='400' y2='{y}' stroke='#8B6CFF' stroke-opacity='.10'/>" for y in (30, 60, 90))
        corpo = (f"<defs>{glow('.5', '.5', '.55', '#6E4BFF', '.35')}</defs><rect width='400' height='120' fill='url(#g)'/>" + grade
                 + _velas([14 + i * 27 for i in range(6)], [98, 88, 92, 72, 62, 46], [14, 16, 10, 18, 14, 20], VERDE)
                 + _velas([240 + i * 27 for i in range(6)], [42, 54, 50, 70, 80, 96], [14, 16, 10, 18, 14, 20], VERMELHO)
                 + "<path d='M206 4 L194 58 L206 58 L194 116' fill='none' stroke='#FFD76A' stroke-width='3' stroke-linejoin='round' opacity='.8'/>"
                 + "<path d='M206 4 L194 58 L206 58 L194 116' fill='none' stroke='#FFD76A' stroke-width='9' stroke-linejoin='round' opacity='.14'/>")
        return svg_uri(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 120' preserveAspectRatio='xMidYMid slice'>{corpo}</svg>")
    if tema == "jogador":
        corpo = (f"<defs>{glow('.12', '.5', '.7', '#8B6CFF', '.5')}</defs><rect width='400' height='80' fill='url(#g)'/>"
                 + _faiscas([(340, 14, 2, .7), (372, 40, 1.6, .6), (300, 64, 1.4, .5), (386, 66, 2.2, .5)])
                 + "<path d='M250 80 L400 20' stroke='#8B6CFF' stroke-opacity='.18' stroke-width='22'/>")
        return svg_uri(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 80' preserveAspectRatio='xMidYMid slice'>{corpo}</svg>")
    if tema == "marca":
        raios = "".join(f"<polygon points='70,40 {70 + 330 * __import__('math').cos(a):.0f},{40 + 330 * __import__('math').sin(a):.0f} "
                        f"{70 + 330 * __import__('math').cos(a + .1):.0f},{40 + 330 * __import__('math').sin(a + .1):.0f}' fill='#7AA2FF' opacity='.07'/>"
                        for a in [-1.3 + i * .22 for i in range(12)])
        corpo = (f"<defs>{glow('.17', '.5', '.6', '#3C6EFF', '.55')}</defs><rect width='400' height='80' fill='url(#g)'/>" + raios
                 + _faiscas([(160, 16, 2, .8), (330, 22, 1.6, .7), (380, 60, 2.2, .6), (250, 66, 1.4, .6)], "#fff"))
        return svg_uri(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 80' preserveAspectRatio='xMidYMid slice'>{corpo}</svg>")
    if tema == "missoes":    # alvo com anéis à direita e faíscas douradas
        aneis = "".join(f"<circle cx='350' cy='46' r='{r}' fill='none' stroke='{OURO}' stroke-opacity='{o}' stroke-width='3'/>" for r, o in ((16, .35), (30, .22), (46, .14)))
        corpo = (f"<defs>{glow('.9', '.4', '.55', OURO, '.28')}</defs><rect width='400' height='96' fill='url(#g)'/>" + aneis
                 + f"<circle cx='350' cy='46' r='6' fill='{OURO}' opacity='.5'/>" + _faiscas([(300, 12, 2, .7), (390, 84, 2, .6), (250, 80, 1.4, .5)]))
        return svg_uri(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 400 96' preserveAspectRatio='xMaxYMid slice'>{corpo}</svg>")
    if tema == "jogar":     # explosão dourada atrás do botão principal
        raios = "".join(f"<polygon points='100,60 {100 + 260 * __import__('math').cos(a):.0f},{60 + 260 * __import__('math').sin(a):.0f} "
                        f"{100 + 260 * __import__('math').cos(a + .16):.0f},{60 + 260 * __import__('math').sin(a + .16):.0f}' fill='#FFE08A' opacity='.16'/>"
                        for a in [i * .45 for i in range(14)])
        corpo = (f"<defs>{glow('.5', '.4', '.7', '#FFC23D', '.55')}</defs><rect width='200' height='120' fill='url(#g)'/>" + raios
                 + _faiscas([(24, 22, 2, .9), (176, 30, 2.4, .9), (160, 100, 1.8, .8), (30, 96, 1.6, .7)], "#fff"))
        return svg_uri(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 120' preserveAspectRatio='xMidYMid slice'>{corpo}</svg>")
    if tema == "carteira":
        moedas = "".join(f"<circle cx='{x}' cy='{y}' r='{r}' fill='none' stroke='#FFD76A' stroke-width='2' opacity='{o}'/>" for x, y, r, o in ((20, 100, 16, .28), (170, 24, 11, .3), (150, 104, 8, .22)))
        corpo = (f"<defs>{glow('.2', '.2', '.7', '#6E4BFF', '.55')}</defs><rect width='200' height='120' fill='url(#g)'/>" + moedas
                 + "<polyline points='0,100 50,86 90,92 140,64 200,44' fill='none' stroke='#8B6CFF' stroke-opacity='.45' stroke-width='3' stroke-linecap='round'/>")
        return svg_uri(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 120' preserveAspectRatio='xMidYMid slice'>{corpo}</svg>")
    if tema == "mercado":
        corpo = (f"<defs>{glow('.8', '.2', '.7', CIANO, '.45')}</defs><rect width='200' height='120' fill='url(#g)'/>"
                 + _velas([20, 46, 72, 98, 124, 150], [88, 78, 82, 62, 52, 36], [12, 14, 10, 16, 12, 18], VERDE, 7).replace("opacity='.8'", "opacity='.35'").replace("opacity='.55'", "opacity='.25'")
                 + "<polyline points='0,96 40,84 80,88 120,60 160,48 200,26' fill='none' stroke='#2EE59D' stroke-opacity='.5' stroke-width='3' stroke-linecap='round'/>")
        return svg_uri(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 200 120' preserveAspectRatio='xMidYMid slice'>{corpo}</svg>")
    raise ValueError(f"tema de fundo desconhecido: {tema}")


# ------------------------------------------------------------------ ícones (SVG próprio, 3D leve com degradê)
_ICONES = {
    "carteira": ("<defs><linearGradient id='a' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#B7A2FF'/><stop offset='1' stop-color='#5B3FD6'/></linearGradient></defs>"
                 "<rect x='6' y='16' width='52' height='38' rx='9' fill='#2A1B78'/><rect x='6' y='12' width='52' height='38' rx='9' fill='url(#a)'/>"
                 "<path d='M10 22h44' stroke='#fff' stroke-opacity='.35' stroke-width='3' stroke-linecap='round'/>"
                 "<rect x='38' y='26' width='22' height='14' rx='6' fill='#2A1B78'/><circle cx='46' cy='33' r='3.4' fill='#FFD76A'/>"),
    "jogar": ("<defs><linearGradient id='b' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#FFF0A8'/><stop offset='1' stop-color='#F29A1F'/></linearGradient></defs>"
              "<circle cx='32' cy='36' r='25' fill='#9A5A00'/><circle cx='32' cy='32' r='25' fill='url(#b)'/>"
              "<circle cx='32' cy='32' r='19' fill='none' stroke='#fff' stroke-opacity='.5' stroke-width='2'/>"
              "<path d='M26 21 L45 32 L26 43 Z' fill='#4A2A00' stroke='#4A2A00' stroke-width='3' stroke-linejoin='round'/>"),
    "mercado": ("<defs><linearGradient id='c' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#7FF0C4'/><stop offset='1' stop-color='#14A56E'/></linearGradient>"
                "<linearGradient id='d' x1='0' y1='0' x2='0' y2='1'><stop offset='0' stop-color='#FF9AA8'/><stop offset='1' stop-color='#D62F4B'/></linearGradient></defs>"
                "<rect x='11' y='6' width='3' height='46' rx='1.5' fill='#7FF0C4'/><rect x='5' y='16' width='15' height='24' rx='4' fill='url(#c)'/>"
                "<rect x='31' y='12' width='3' height='46' rx='1.5' fill='#FF9AA8'/><rect x='25' y='20' width='15' height='26' rx='4' fill='url(#d)'/>"
                "<rect x='51' y='4' width='3' height='40' rx='1.5' fill='#7FF0C4'/><rect x='45' y='10' width='15' height='22' rx='4' fill='url(#c)'/>"),
    "alvo": ("<circle cx='32' cy='32' r='26' fill='#3B1F8E'/><circle cx='32' cy='32' r='26' fill='none' stroke='#F2B84B' stroke-width='4'/>"
             "<circle cx='32' cy='32' r='16' fill='none' stroke='#fff' stroke-width='4' stroke-opacity='.85'/><circle cx='32' cy='32' r='6' fill='#F2B84B'/>"
             "<path d='M34 30 L56 8' stroke='#fff' stroke-width='4' stroke-linecap='round'/><path d='M50 6 L58 6 L58 14' fill='none' stroke='#fff' stroke-width='4' stroke-linecap='round' stroke-linejoin='round'/>"),
    "trofeu": ("<path d='M20 8h24v16c0 10-6 17-12 17S20 34 20 24z' fill='#F2B84B'/><path d='M20 12H9c0 10 4 15 12 16M44 12h11c0 10-4 15-12 16' fill='none' stroke='#F2B84B' stroke-width='4' stroke-linecap='round'/>"
               "<rect x='28' y='40' width='8' height='9' fill='#D99A2B'/><rect x='19' y='49' width='26' height='7' rx='3' fill='#F2B84B'/><path d='M25 13v11' stroke='#fff' stroke-opacity='.5' stroke-width='3' stroke-linecap='round'/>"),
    "estrela": ("<path d='M32 6l7.6 16 17.4 2.2-12.8 12 3.4 17.3L32 45l-15.6 8.5 3.4-17.3L7 24.2 24.4 22z' fill='#F2B84B' stroke='#B97A00' stroke-width='3' stroke-linejoin='round'/>"),
    "check": ("<circle cx='32' cy='32' r='26' fill='#14A56E'/><path d='M19 33l9 9 17-19' fill='none' stroke='#fff' stroke-width='6' stroke-linecap='round' stroke-linejoin='round'/>"),
}


def icone(nome: str, tamanho: int = 32, classe: str = "") -> str:
    corpo = _ICONES[nome].replace("id='a'", f"id='{nome}a'").replace("url(#a)", f"url(#{nome}a)")
    for k in ("b", "c", "d"):      # ids únicos por ícone: vários SVGs na mesma página não podem repetir id
        corpo = corpo.replace(f"id='{k}'", f"id='{nome}{k}'").replace(f"url(#{k})", f"url(#{nome}{k})")
    cls = f" class='{_e(classe)}'" if classe else ""
    return (f"<svg{cls} xmlns='http://www.w3.org/2000/svg' width='{tamanho}' height='{tamanho}' viewBox='0 0 64 64' aria-hidden='true' "
            f"focusable='false'>{corpo}</svg>")


# ------------------------------------------------------------------ peças de HTML
def barra(pct: float, classe: str = "") -> str:
    p = max(0, min(100, int(round(float(pct or 0)))))
    return f"<div class='gu-bar {_e(classe)}'><i style='width:{p}%'></i></div>"


def segmentos(feitos: int, total: int) -> str:
    """Barra em fatias, uma por tarefa (ex.: missões do dia). Sem total, não desenha nada."""
    total = max(0, int(total or 0))
    feitos = max(0, min(int(feitos or 0), total))
    if not total:
        return ""
    return "<div class='gu-seg'>" + "".join(f"<i class='{'on' if k < feitos else ''}'></i>" for k in range(total)) + "</div>"


def ficha(conteudo_html: str, cor: str = ROXO, titulo: str = "") -> str:
    t = f" title='{_e(titulo)}'" if titulo else ""
    return f"<span class='gu-chip' style='--c:{_e(cor)}'{t}>{conteudo_html}</span>"


# ------------------------------------------------------------------ CSS
def css_base() -> str:
    """Estilos das peças acima. Vale para qualquer tela que use o kit."""
    return ("<style>"
            f"{Q} .gu-card{{position:relative;box-sizing:border-box;border-radius:20px;overflow:hidden;color:#fff;"
            "border:1.5px solid color-mix(in srgb,var(--ac,#8B6CFF) 60%,transparent);"
            "background:var(--bg) center/cover no-repeat,linear-gradient(160deg,#241C5A,#110C32 85%);"
            "box-shadow:0 4px 0 color-mix(in srgb,var(--ac,#8B6CFF) 26%,#06031A),0 0 18px -8px var(--ac,#8B6CFF),inset 0 1px 0 rgba(255,255,255,.08)}"
            f"{Q} .gu-card :is(b,span,small,div,em,i){{-webkit-text-fill-color:currentColor}}"
            f"{Q} .gu-bar{{height:8px;border-radius:99px;background:rgba(255,255,255,.16);overflow:hidden;box-shadow:inset 0 1px 2px rgba(0,0,0,.4)}}"
            f"{Q} .gu-bar i{{display:block;height:100%;border-radius:99px;background:linear-gradient(90deg,#8B6CFF,#3DDC97);box-shadow:0 0 8px rgba(61,220,151,.6)}}"
            f"{Q} .gu-seg{{display:flex;gap:4px;flex:1 1 auto;min-width:0}}"
            f"{Q} .gu-seg i{{flex:1 1 0;height:8px;border-radius:99px;background:rgba(255,255,255,.16);box-shadow:inset 0 1px 2px rgba(0,0,0,.4)}}"
            f"{Q} .gu-seg i.on{{background:linear-gradient(90deg,#FFD76A,#F2B84B);box-shadow:0 0 8px rgba(242,184,75,.7)}}"
            f"{Q} .gu-chip{{display:inline-flex;align-items:center;gap:4px;padding:2px 8px 2px 4px;border-radius:99px;border:1.5px solid var(--c);"
            "background:rgba(8,6,30,.7);color:#fff;font-weight:900;line-height:1.2;white-space:nowrap}"
            "</style>")


def css_cartao_botao(chave: str) -> str:
    """O cartão HTML vira botão inteiro: o st.button (key=`chave`, dentro de st.container(key=`chave`)) fica por cima, invisível, e leva o toque.
    Afundar ao tocar dá a sensação de botão de jogo. O texto do st.button continua lá para leitores de tela."""
    c = f"{Q} .st-key-{chave}"
    return ("<style>"
            f"{c}{{position:relative;gap:0 !important;min-width:0;transition:transform .08s}}"
            f"{c}:has(button:active){{transform:translateY(3px) scale(.985)}}"
            f"{c} [data-testid='stElementContainer']:has(.stButton){{position:absolute !important;inset:0;width:100% !important;height:100% !important;margin:0 !important;z-index:5}}"
            f"{c} .stButton,{c} .stButton>button{{width:100% !important;height:100% !important;min-height:0 !important;padding:0 !important;margin:0 !important;"
            "opacity:0 !important;border-radius:20px !important;cursor:pointer}"
            f"{c} [data-testid='stElementContainer']:not(:has(.stButton)){{margin:0 !important;width:100% !important}}"
            "</style>")
