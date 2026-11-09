"""Arte da jornada (módulo puro, sem Streamlit): mascote Tico, cenário de cada unidade e cores derivadas.

Tico é um touro (símbolo do mercado em alta) com uma moeda de ouro no lugar do anel do nariz.
Para mudar a cara dele, mexa só em mascote(). Para mudar o cenário, mexa em tile().
"""
from __future__ import annotations

import base64
import html

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


def mascote(festa: bool = False, tamanho: int = 92) -> str:
    """Tico, o touro. `festa=True`: olhos felizes e estrelinhas (meta do dia batida)."""
    olhos = (f'<path d="M38 57q6-9 12 0M70 57q6-9 12 0" fill="none" stroke="#1B1442" stroke-width="3.5" stroke-linecap="round"/>' if festa else
             '<circle cx="44" cy="55" r="6.5" fill="#1B1442"/><circle cx="76" cy="55" r="6.5" fill="#1B1442"/>'
             '<circle cx="46.2" cy="52.8" r="2.2" fill="#fff"/><circle cx="78.2" cy="52.8" r="2.2" fill="#fff"/>')
    brilho = ('<path d="M104 30l2.5 6 6 2.5-6 2.5-2.5 6-2.5-6-6-2.5 6-2.5zM12 62l2 4.5 4.5 2-4.5 2-2 4.5-2-4.5-4.5-2 4.5-2z" fill="#FFC94D"/>' if festa else "")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{tamanho}" height="{tamanho}" viewBox="0 0 120 120" role="img" aria-label="Tico, o touro mascote">'
            f'<ellipse cx="60" cy="112" rx="30" ry="5" fill="#000" opacity=".25"/>'
            f'<path d="M31 42C14 40 9 22 15 11c6 11 18 16 28 22zM89 42c17-2 22-20 16-31-6 11-18 16-28 22z" fill="{OURO}" stroke="{OURO_ESC}" stroke-width="3" stroke-linejoin="round"/>'
            f'<ellipse cx="20" cy="56" rx="11" ry="7" transform="rotate(-25 20 56)" fill="#B8A4FF" stroke="{ROXO}" stroke-width="3"/>'
            f'<ellipse cx="100" cy="56" rx="11" ry="7" transform="rotate(25 100 56)" fill="#B8A4FF" stroke="{ROXO}" stroke-width="3"/>'
            f'<ellipse cx="60" cy="60" rx="40" ry="37" fill="#D9CCFF" stroke="{ROXO}" stroke-width="3.5"/>'
            f'<path d="M50 26q10-14 20 0q-10-5-20 0z" fill="{ROXO}"/>'
            f'<ellipse cx="60" cy="82" rx="25" ry="17" fill="#F4EEFF" stroke="{ROXO}" stroke-width="3"/>'
            f'<ellipse cx="51" cy="78" rx="3.2" ry="4.5" fill="{ROXO}"/><ellipse cx="69" cy="78" rx="3.2" ry="4.5" fill="{ROXO}"/>'
            f'<circle cx="35" cy="70" r="5.5" fill="#FF8FB8" opacity=".6"/><circle cx="85" cy="70" r="5.5" fill="#FF8FB8" opacity=".6"/>'
            f'{olhos}'
            f'<path d="M52 88q8 6 16 0" fill="none" stroke="{ROXO}" stroke-width="3" stroke-linecap="round"/>'
            f'<circle cx="60" cy="101" r="9" fill="{OURO}" stroke="{OURO_ESC}" stroke-width="3"/><circle cx="60" cy="101" r="4.5" fill="none" stroke="{OURO_ESC}" stroke-width="2"/>'
            f'{brilho}</svg>')


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
