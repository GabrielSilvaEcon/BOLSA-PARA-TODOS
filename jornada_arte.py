"""Arte da jornada (módulo puro, sem Streamlit): mascote Tico, cenário de cada unidade e cores derivadas.

Tico é uma moeda de ouro com carinha (dinheiro é o assunto do app).
Para mudar a cara dele, mexa só em mascote(). Para mudar o cenário, mexa em tile().
"""
from __future__ import annotations

import base64
import functools
import html
import os

OURO, OURO_ESC = "#F2B84B", "#B9811F"
ROXO = "#5B3FD6"


def _rgb(h: str) -> tuple[int, int, int]:
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def misturar(h: str, outro: str, t: float) -> str:
    """Mistura a cor `h` com `outro` (t=0 fica em h, t=1 vira `outro`)."""
    a, b = _rgb(h), _rgb(outro)
    return "#%02X%02X%02X" % tuple(round(x + (y - x) * t) for x, y in zip(a, b))


def escurecer(h: str, t: float = .45) -> str:
    return misturar(h, "#0B0821", t)


def clarear(h: str, t: float = .55) -> str:
    return misturar(h, "#FFFFFF", t)


def uri(svg: str) -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode("utf-8")).decode("ascii")


def _mascote_svg(festa: bool = False, tamanho: int = 92, humor: str | None = None) -> str:
    """Tico, a moeda de ouro com carinha. `festa=True`: olhos felizes, boca aberta e estrelinhas (meta do dia batida).
    `humor`: "normal", "festa", "pensa" (pergunta na tela) ou "triste" (errou)."""
    h = humor or ("festa" if festa else "normal")
    T = "#3A2A00"
    tr = f'fill="none" stroke="{T}" stroke-width="4" stroke-linecap="round"'
    olhos = ('<ellipse cx="47" cy="50" rx="5.5" ry="7.5" fill="%s"/><ellipse cx="73" cy="50" rx="5.5" ry="7.5" fill="%s"/>'
             '<circle cx="48.8" cy="47" r="2" fill="#fff"/><circle cx="74.8" cy="47" r="2" fill="#fff"/>' % (T, T))
    boca = f'<path d="M46 70q14 14 28 0" {tr}/>'
    extra = ""
    if h == "festa":
        olhos = f'<path d="M40 53q7-10 14 0M66 53q7-10 14 0" {tr}/>'
        boca = '<path d="M44 68q16 26 32 0z" fill="#5A2B00"/><path d="M52 78q8 6 16 0q-8-5-16 0z" fill="#FF7A8A"/>'
        extra = ('<path d="M104 26l2.5 6 6 2.5-6 2.5-2.5 6-2.5-6-6-2.5 6-2.5zM13 56l2 4.5 4.5 2-4.5 2-2 4.5-2-4.5-4.5-2 4.5-2z" fill="#FFF3B0"/>')
    elif h == "triste":
        olhos += f'<path d="M39 38l15 5M81 38l-15 5" {tr}/><path d="M40 60q-5 8 0 10q5-2 0-10z" fill="#8EC5FF"/>'
        boca = f'<path d="M48 80q12-10 24 0" {tr}/>'
    elif h == "pensa":
        olhos += f'<path d="M66 36q7-5 14 0" {tr}/>'
        boca = f'<path d="M52 75h14" {tr}/>'
        extra = '<circle cx="100" cy="26" r="2.5" fill="#fff" opacity=".85"/><circle cx="108" cy="17" r="3.5" fill="#fff" opacity=".85"/><circle cx="116" cy="6" r="4.5" fill="#fff" opacity=".85"/>'
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{tamanho}" height="{tamanho}" viewBox="0 0 120 120" role="img" aria-label="Tico, a moeda mascote">'
            f'<ellipse cx="60" cy="114" rx="30" ry="5" fill="#000" opacity=".25"/>'
            f'<circle cx="60" cy="66" r="46" fill="{OURO_ESC}"/>'
            f'<circle cx="60" cy="58" r="46" fill="{OURO}" stroke="{OURO_ESC}" stroke-width="4"/>'
            f'<circle cx="60" cy="58" r="37" fill="none" stroke="#D99A2B" stroke-width="3"/>'
            f'<path d="M30 40Q38 24 56 20" fill="none" stroke="#fff" stroke-width="5" stroke-linecap="round" opacity=".55"/>'
            f'<circle cx="35" cy="67" r="6" fill="#FF8F6B" opacity=".45"/><circle cx="85" cy="67" r="6" fill="#FF8F6B" opacity=".45"/>'
            f'{olhos}{boca}{extra}</svg>')

PASTA_MASCOTE = os.path.dirname(os.path.abspath(__file__))
# humor/pose -> arquivo mascote_<pose>.webp na raiz do repositório. Poses extras: analise, aprender, conquistas, loja, perfil.
POSES = {"normal": "inicio", "festa": "wallet", "pensa": "ajuda", "triste": "carteira", "inicio": "inicio", "wallet": "wallet", "ajuda": "ajuda",
         "carteira": "carteira", "analise": "analise", "aprender": "aprender", "conquistas": "conquistas", "loja": "loja", "perfil": "perfil", "capa": "capa"}


@functools.lru_cache(maxsize=16)
def _uri_pose(arquivo: str) -> str | None:
    """Imagem do mascote em data URI (None se o arquivo não estiver no repositório: aí vale a moeda Tico desenhada)."""
    try:
        with open(os.path.join(PASTA_MASCOTE, f"mascote_{arquivo}.webp"), "rb") as f:
            return "data:image/webp;base64," + base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return None


def mascote(festa: bool = False, tamanho: int = 92, humor: str | None = None) -> str:
    """Mascote cachorro do TickerHunters. `humor`/pose: normal, festa, pensa, triste, analise, aprender, conquistas, loja, perfil.
    Sem os arquivos mascote_*.webp, cai na moeda Tico desenhada (mesmo contrato de antes)."""
    h = humor or ("festa" if festa else "normal")
    uri = _uri_pose(POSES.get(h, "inicio"))
    if not uri:
        return _mascote_svg(festa, tamanho, humor)
    return (f'<img src="{uri}" alt="Mascote do TickerHunters" width="{tamanho}" height="{tamanho}" loading="lazy" '
            f'style="width:{tamanho}px;height:{tamanho}px;object-fit:contain;display:block;flex:none">')




def hero(texto: str, festa: bool = False) -> str:
    return (f"<div class='jor-hero'><div class='jor-tico'>{mascote(festa)}</div>"
            f"<div class='jor-fala'>{html.escape(texto)}</div></div>")


def _moeda(x, y, r, o=.9):
    return (f'<g opacity="{o}"><circle cx="{x}" cy="{y}" r="{r}" fill="{OURO}" stroke="{OURO_ESC}" stroke-width="2"/>'
            f'<circle cx="{x}" cy="{y}" r="{r * .62:.1f}" fill="none" stroke="{OURO_ESC}" stroke-width="1.6"/></g>')


def _brilho(x, y, s, cor, o=.8):
    return f'<path d="M{x} {y - s}Q{x} {y} {x + s} {y}Q{x} {y} {x} {y + s}Q{x} {y} {x - s} {y}Q{x} {y} {x} {y - s}z" fill="{cor}" opacity="{o}"/>'


def tile(cor: str) -> str:
    """Cenário que se repete na vertical atrás dos nós de uma unidade: brilho da cor da unidade, moedas e estrelinhas nas laterais."""
    c = clarear(cor, .45)
    s = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 380 560" preserveAspectRatio="none">'
         f'<defs><radialGradient id="g1"><stop offset="0" stop-color="{cor}" stop-opacity=".30"/><stop offset="1" stop-color="{cor}" stop-opacity="0"/></radialGradient></defs>'
         f'<circle cx="40" cy="120" r="130" fill="url(#g1)"/><circle cx="350" cy="400" r="150" fill="url(#g1)"/>'
         f'{_moeda(26, 70, 11)}{_moeda(352, 250, 9, .7)}{_moeda(34, 440, 8, .6)}{_moeda(340, 520, 12)}'
         f'{_brilho(348, 80, 11, c)}{_brilho(24, 250, 9, c, .6)}{_brilho(350, 400, 8, c, .7)}{_brilho(40, 520, 10, c)}'
         f'<circle cx="70" cy="330" r="3" fill="{c}" opacity=".5"/><circle cx="318" cy="170" r="3" fill="{c}" opacity=".5"/><circle cx="300" cy="470" r="2.5" fill="{c}" opacity=".5"/>'
         f'</svg>')
    return uri(s)


# palavra do título (sem acento, minúscula) -> pose; vale a primeira que aparecer
_POSE_AREA = (("conquista", "conquistas"), ("ranking", "conquistas"), ("wallet", "wallet"), ("competi", "wallet"), ("jogar", "wallet"), ("jogo", "wallet"),
              ("aprend", "aprender"), ("jornada", "aprender"), ("educ", "aprender"), ("licao", "aprender"), ("curso", "aprender"), ("glossario", "aprender"),
              ("loja", "loja"), ("plano", "loja"), ("pagament", "loja"), ("economia", "loja"), ("assin", "loja"),
              ("perfil", "perfil"), ("conta", "perfil"), ("usuario", "perfil"), ("preferenc", "perfil"), ("config", "perfil"),
              ("ajuda", "ajuda"), ("suporte", "ajuda"), ("duvida", "ajuda"), ("sobre", "ajuda"),
              ("carteira", "carteira"), ("patrimonio", "carteira"), ("gestao", "carteira"), ("risco", "carteira"), ("renda", "carteira"),
              ("proventos", "carteira"), ("simulad", "carteira"), ("relatorio", "carteira"), ("diversific", "carteira"),
              ("analise", "analise"), ("tecnica", "analise"), ("fundament", "analise"), ("preco", "analise"), ("fundos", "analise"), ("fii", "analise"),
              ("acoes", "analise"), ("cripto", "analise"), ("mercado", "analise"), ("macro", "analise"), ("noticia", "analise"), ("compar", "analise"),
              ("inicio", "inicio"), ("painel", "inicio"))


def pose_da_area(titulo: str) -> str:
    """Pose do mascote para o cabeçalho de uma área, pelo título (padrão: acenando)."""
    import unicodedata
    t = unicodedata.normalize("NFD", str(titulo or "").lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return next((pose for chave, pose in _POSE_AREA if chave in t), "inicio")
