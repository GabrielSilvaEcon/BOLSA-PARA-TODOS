"""Ilustrações de fundo do cabeçalho de cada página, de acordo com o que o ativo representa (prédios para FIIs, velas para ações...).
Módulo puro: devolve o nome do motivo pelo título e o CSS com os desenhos (SVG feitos aqui, sem imagens externas)."""
from __future__ import annotations

import unicodedata
from urllib.parse import quote


def _sem_acento(t: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", (t or "").lower()) if unicodedata.category(c) != "Mn")


# (palavras do título, motivo); vale a primeira regra que casar
_REGRAS = (
    (("cripto", "token", "on-chain", "bitcoin"), "hex"),
    (("fii", "imobili"), "predios"),
    (("etf",), "pizza"),
    (("fundo", "multimercado"), "camadas"),
    (("renda fixa", "titulo", "tesouro", "cdi"), "banco"),
    (("acoes", "acao", "preco justo", "multiplo", "dividend", "saude", "fluxo", "tecnica", "ranking", "valuation"), "velas"),
    (("carteira", "gestao", "risco", "relatorio"), "pizza"),
    (("economia", "macro", "noticia"), "velas"),
)


def motivo(titulo: str) -> str:
    t = _sem_acento(titulo)
    for palavras, m in _REGRAS:
        if any(p in t for p in palavras):
            return m
    return ""


_W = "%23FFFFFF"
_SVG = {
    "predios": "<rect x='20' y='50' width='34' height='70' rx='3' fill='{c}' fill-opacity='.28'/><rect x='62' y='20' width='42' height='100' rx='3' fill='{c}' fill-opacity='.38'/>"
               "<rect x='112' y='62' width='30' height='58' rx='3' fill='{c}' fill-opacity='.26'/><rect x='150' y='34' width='38' height='86' rx='3' fill='{c}' fill-opacity='.34'/>"
               "<rect x='196' y='70' width='30' height='50' rx='3' fill='{c}' fill-opacity='.22'/>"
               + "".join(f"<rect x='{x}' y='{y}' width='6' height='6' rx='1' fill='{{w}}' fill-opacity='.45'/>" for x in (70, 84, 96) for y in (32, 50, 68, 86))
               + "".join(f"<rect x='{x}' y='{y}' width='6' height='6' rx='1' fill='{{w}}' fill-opacity='.4'/>" for x in (158, 172) for y in (46, 64, 82)),
    "velas": "".join(f"<line x1='{x + 7}' y1='{a}' x2='{x + 7}' y2='{b}' stroke='{{col}}' stroke-width='2' stroke-opacity='.6'/>"
                      f"<rect x='{x}' y='{c1}' width='14' height='{h}' rx='2' fill='{{col}}' fill-opacity='.55'/>"
                      for x, a, b, c1, h, col in ((24, 60, 110, 70, 30, "%23FF6B8A"), (52, 40, 100, 52, 36, "%233DDC97"), (80, 50, 108, 66, 30, "%23FF6B8A"),
                                                  (108, 30, 90, 40, 38, "%233DDC97"), (136, 20, 80, 30, 34, "%233DDC97"), (164, 36, 96, 52, 28, "%23FF6B8A"),
                                                  (192, 16, 74, 24, 36, "%233DDC97"))),
    "banco": "<polygon points='120,12 214,48 26,48' fill='{c}' fill-opacity='.34'/>"
             + "".join(f"<rect x='{x}' y='56' width='16' height='48' rx='2' fill='{{c}}' fill-opacity='.30'/>" for x in (42, 76, 110, 144, 178))
             + "<rect x='26' y='108' width='188' height='10' rx='3' fill='{c}' fill-opacity='.4'/>",
    "hex": "<polygon points='60,28 84,14 108,28 108,56 84,70 60,56' fill='{c}' fill-opacity='.30'/><polygon points='128,64 152,50 176,64 176,92 152,106 128,92' fill='{c}' fill-opacity='.34'/>"
           "<polygon points='168,14 188,2 208,14 208,38 188,50 168,38' fill='{c}' fill-opacity='.24'/><line x1='108' y1='42' x2='128' y2='70' stroke='{w}' stroke-opacity='.4' stroke-width='2'/>"
           "<line x1='176' y1='70' x2='190' y2='48' stroke='{w}' stroke-opacity='.4' stroke-width='2'/><circle cx='84' cy='42' r='5' fill='{w}' fill-opacity='.6'/><circle cx='152' cy='78' r='5' fill='{w}' fill-opacity='.6'/>",
    "pizza": "<circle cx='120' cy='64' r='48' fill='{c}' fill-opacity='.26'/><path d='M120 64 L120 16 A48 48 0 0 1 164 82 Z' fill='{c}' fill-opacity='.5'/>"
             "<path d='M120 64 L164 82 A48 48 0 0 1 96 108 Z' fill='{w}' fill-opacity='.22'/><circle cx='120' cy='64' r='18' fill='%230E0A26' fill-opacity='.5'/>",
    "camadas": "<polygon points='120,16 214,52 120,88 26,52' fill='{c}' fill-opacity='.42'/><polygon points='26,66 120,102 214,66 214,80 120,116 26,80' fill='{c}' fill-opacity='.28'/>",
}
_COR = {"predios": "%232BA7C9", "banco": "%233DDC97", "hex": "%23F2B84B", "pizza": "%238B6CFF", "camadas": "%232BA7C9", "velas": "%23FFFFFF"}


def _uri(m: str) -> str:
    corpo = _SVG[m].replace("{c}", _COR[m]).replace("{w}", _W).replace("{col}", "%23FFFFFF")
    svg = f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 240 124'>{corpo}</svg>"
    return "data:image/svg+xml;utf8," + quote(svg, safe="/:='<>,;%#() .-")


def css() -> str:
    """Desenha o motivo atrás do lado direito do cabeçalho (.pghead[data-bg]); fica discreto e não captura toques."""
    q = "html body .stApp.stApp .pghead[data-bg]"
    regras = [f"{q}{{position:relative}}",
              f"{q}>*:not(.pgmais){{position:relative;z-index:1}}",
              f"{q}>.pgmais{{z-index:2}}",
              f"{q}::before{{content:\"\";position:absolute;right:0;top:0;bottom:0;width:58%;opacity:.55;pointer-events:none;z-index:0;"
              f"background-repeat:no-repeat;background-position:right center;background-size:auto 92%;border-radius:inherit;"
              f"-webkit-mask-image:linear-gradient(90deg,transparent,#000 40%);mask-image:linear-gradient(90deg,transparent,#000 40%)}}"]
    for m in _SVG:
        regras.append(f"{q}[data-bg=\"{m}\"]::before{{background-image:url(\"{_uri(m)}\")}}")
    return "".join(regras)
