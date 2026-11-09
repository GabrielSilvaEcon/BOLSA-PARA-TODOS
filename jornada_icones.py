"""Ícones da jornada, desenhados em SVG (módulo puro, sem Streamlit). Estilo: traço arredondado em viewBox 48x48.

Uso: svg("balanca", cor="#FFFFFF", tamanho=40) devolve o SVG; uri("balanca") devolve um data URI (para usar em CSS ou <img>).
Para criar um ícone novo: adicione uma entrada em ICONES com o miolo do SVG (use currentColor para traço e preenchimento).
Nome desconhecido cai em "estrela", então nunca quebra a tela.
"""
from __future__ import annotations

import base64

# miolo de cada ícone; "tr" = só traço, "pr" = preenchido
_T = 'fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"'
_P = 'fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linejoin="round"'

ICONES: dict[str, tuple[str, str]] = {
    "balanca": (_T, '<path d="M24 8v30M15 40h18M9 15h30"/><circle cx="24" cy="8" r="2" fill="currentColor"/>'
                    '<path d="M9 15 3 28M9 15l6 13M39 15l-6 13M39 15l6 13"/>'
                    '<path d="M3 28h12c0 3.5-2.7 6-6 6s-6-2.5-6-6zM33 28h12c0 3.5-2.7 6-6 6s-6-2.5-6-6z"/>'),
    "grafico": (_T, '<path d="M8 8v32h32"/><path d="M14 32l8-9 6 5 10-13"/><path d="M31 15h7v7"/>'),
    "carrinho": (_T, '<path d="M5 9h6l5 21h21l4-15H13"/><circle cx="19" cy="38" r="2.6"/><circle cx="35" cy="38" r="2.6"/>'),
    "broto": (_T, '<path d="M24 41V24M15 41h18"/><path d="M24 29C15 29 10 24 10 15c9 0 14 5 14 14z"/><path d="M24 23c0-9 5-14 14-14 0 9-5 14-14 14z"/>'),
    "moeda": (_T, '<circle cx="24" cy="24" r="17"/><path d="M24 13v22M29 19c-1.2-2-3-3-5-3-3 0-5 1.6-5 4s2 3.4 5 4 5 1.6 5 4-2 4-5 4c-2 0-3.8-1-5-3"/>'),
    "escudo": (_T, '<path d="M24 6l14 5v11c0 9-6 16-14 20-8-4-14-11-14-20V11z"/><path d="M18 24l5 5 8-10"/>'),
    "alvo": (_T, '<circle cx="24" cy="24" r="17"/><circle cx="24" cy="24" r="10"/><circle cx="24" cy="24" r="3.5" fill="currentColor"/>'),
    "livro": (_T, '<path d="M7 10h12c3 0 5 2 5 5v24c0-2.5-2-4-5-4H7zM41 10H29c-3 0-5 2-5 5v24c0-2.5 2-4 5-4h12z"/>'),
    "predio": (_T, '<path d="M10 41V9h18v32M28 19h10v22M6 41h36M16 16h6M16 23h6M16 30h6"/>'),
    "cofre": (_T, '<rect x="7" y="9" width="34" height="28" rx="4"/><circle cx="24" cy="23" r="7"/><path d="M24 18v10M19 23h10M14 37v4M34 37v4"/>'),
    "lupa": (_T, '<circle cx="21" cy="21" r="12"/><path d="M30 30l11 11M16 19a6 6 0 0 1 6-5'),
    "velas": (_T, '<path d="M14 8v6M14 34v6M24 14v5M24 38v4M34 8v4M34 30v8"/><rect x="10" y="14" width="8" height="20" rx="2"/><rect x="20" y="19" width="8" height="19" rx="2"/><rect x="30" y="12" width="8" height="18" rx="2"/>'),
    "bitcoin": (_T, '<circle cx="24" cy="24" r="17"/><path d="M19 15h8a4.5 4.5 0 0 1 0 9h-8zM19 24h9a4.5 4.5 0 0 1 0 9h-9zM19 15v18M23 11v4M23 33v4M28 11v4M28 33v4"/>'),
    "percent": (_T, '<path d="M12 36L36 12"/><circle cx="15" cy="15" r="5"/><circle cx="33" cy="33" r="5"/>'),
    "estrela": (_P, '<path d="M24 6l5.5 11.5 12.5 1.8-9 8.8 2.1 12.4L24 34.6 12.9 40.5 15 28.1 6 19.3l12.5-1.8z"/>'),
    "check": ('fill="none" stroke="currentColor" stroke-width="5" stroke-linecap="round" stroke-linejoin="round"', '<path d="M10 25l9 9 19-20"/>'),
    "chama": (_P, '<path d="M25 4c1 8 11 12 11 23a12 12 0 0 1-24 0c0-6 3-10 6-12 0 5 2 8 5 8 0-7-1-12 2-19z"/>'),
    "raio": (_P, '<path d="M28 3L9 27h12l-3 18 21-26H26z"/>'),
}


def svg(nome: str, cor: str = "#FFFFFF", tamanho: int = 48) -> str:
    attrs, miolo = ICONES.get(nome) or ICONES["estrela"]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{tamanho}" height="{tamanho}" viewBox="0 0 48 48" '
            f'color="{cor}" {attrs}>{miolo}</svg>')


def uri(nome: str, cor: str = "#FFFFFF") -> str:
    return "data:image/svg+xml;base64," + base64.b64encode(svg(nome, cor).encode("utf-8")).decode("ascii")


def existe(nome: str) -> bool:
    return nome in ICONES
