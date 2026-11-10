"""Ícones próprios do TickerHunters: traço único (2 px, pontas arredondadas) em SVG inline, na cor do texto (currentColor).

Puro e sem dependências. Nome desconhecido devolve o ícone 'ponto' (nunca quebra a tela).
"""
from __future__ import annotations

_TRACOS = {
    "inicio": '<path d="M4 11l8-7 8 7v8a1 1 0 0 1-1 1h-4v-6h-6v6H5a1 1 0 0 1-1-1z"/>',
    "aprender": '<path d="M3 8l9-4 9 4-9 4z"/><path d="M7 10.5V15c0 1.5 2.2 3 5 3s5-1.5 5-3v-4.5"/><path d="M21 8v6"/>',
    "analisar": '<path d="M4 20V10M10 20V4M16 20v-7M22 20H2"/>',
    "wallet": '<rect x="3" y="6" width="18" height="13" rx="3"/><path d="M3 10h18"/><circle cx="16.5" cy="14.5" r="1.2"/>',
    "alvo": '<circle cx="12" cy="12" r="8"/><circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3"/>',
    "trofeu": '<path d="M8 4h8v5a4 4 0 0 1-8 0z"/><path d="M8 6H4v1a4 4 0 0 0 4 4M16 6h4v1a4 4 0 0 1-4 4"/><path d="M12 13v4M8 20h8"/>',
    "escudo": '<path d="M12 3l7 3v5c0 5-3 8-7 10-4-2-7-5-7-10V6z"/><path d="M9 12l2 2 4-4"/>',
    "moeda": '<circle cx="12" cy="12" r="8"/><path d="M14.5 9.5c-.5-.8-1.4-1.2-2.5-1.2-1.4 0-2.5.7-2.5 1.8 0 2.6 5.2 1.2 5.2 3.8 0 1.1-1.1 1.8-2.7 1.8-1.2 0-2.2-.5-2.7-1.4M12 6.5v1.8M12 15.7v1.8"/>',
    "livro": '<path d="M4 5a2 2 0 0 1 2-2h13v16H6a2 2 0 0 0-2 2z"/><path d="M4 19a2 2 0 0 1 2-2h13"/>',
    "estrela": '<path d="M12 3l2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1L3.2 9.5l6.1-.9z"/>',
    "fogo": '<path d="M12 3c1 3 5 5 5 10a5 5 0 0 1-10 0c0-2 1-3 2-4 .2 1.5 1 2 1.5 2C10 8 11 5 12 3z"/>',
    "cadeado": '<rect x="5" y="11" width="14" height="9" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "alerta": '<path d="M12 3l10 18H2z"/><path d="M12 10v5M12 18v.5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v6M12 7.5v.5"/>',
    "perfil": '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
    "ajustes": '<path d="M4 7h10M18 7h2M4 17h2M10 17h10"/><circle cx="16" cy="7" r="2"/><circle cx="8" cy="17" r="2"/>',
    "sino": '<path d="M6 17V11a6 6 0 0 1 12 0v6l1.5 2h-15z"/><path d="M10 21h4"/>',
    "busca": '<circle cx="11" cy="11" r="7"/><path d="M20 20l-4-4"/>',
    "seta_cima": '<path d="M12 19V5M6 11l6-6 6 6"/>',
    "seta_baixo": '<path d="M12 5v14M6 13l6 6 6-6"/>',
    "voltar": '<path d="M15 5l-7 7 7 7"/>',
    "ponto": '<circle cx="12" cy="12" r="2"/>',
}

NOMES = tuple(_TRACOS)


def icone(nome: str, tam: int = 24, cor: str = "currentColor", espessura: float = 2.0) -> str:
    """SVG inline. A cor padrão é a do texto ao redor, então o ícone acompanha o tema sozinho."""
    corpo = _TRACOS.get(nome, _TRACOS["ponto"])
    t = max(12, min(int(tam), 96))
    return (f'<svg class="dz-ico" width="{t}" height="{t}" viewBox="0 0 24 24" fill="none" stroke="{cor}" '
            f'stroke-width="{espessura}" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">{corpo}</svg>')
