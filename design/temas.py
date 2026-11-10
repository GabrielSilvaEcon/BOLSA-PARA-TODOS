"""Paletas dos três ambientes + a concha (barra inferior) que é igual nos três. Só cores; nada de lógica de negócio."""
from __future__ import annotations

TEMAS = {
    "aprender": {
        "nome": "Aprender", "escuro": True,
        "fundo": "#120D33", "cartao": "#1D1752", "elevado": "#2A2270", "borda": "#3A3190",
        "texto": "#F3F1FF", "apoio": "#C3BDF0", "destaque": "#B6F23E", "sobre_destaque": "#10240A",
        "secundaria": "#8B6CFF", "positivo": "#4BE3A0", "negativo": "#FF7A93",
    },
    "analise": {
        "nome": "Análise", "escuro": True,
        "fundo": "#0B0E17", "cartao": "#131826", "elevado": "#1B2133", "borda": "#252C42",
        "texto": "#E8EAF2", "apoio": "#9AA2BB", "destaque": "#7A55FA", "sobre_destaque": "#FFFFFF",
        "secundaria": "#5B3FD6", "positivo": "#26D07C", "negativo": "#FF5C6C",
    },
    "wallet": {
        "nome": "Wallet Game", "escuro": True,
        "fundo": "#0A0A0C", "cartao": "#141318", "elevado": "#1C1A22", "borda": "#2A2630",
        "texto": "#F2EFE8", "apoio": "#A39FAE", "destaque": "#C9A24B", "sobre_destaque": "#14110A",
        "secundaria": "#4B2E83", "positivo": "#4CC38A", "negativo": "#E5646E",
    },
}

# Cor de marca (verde-limão do alvo): só para detalhes e conquistas sobre fundo escuro; texto sobre ela é sempre escuro.
MARCA = {"cor": "#B6F23E", "sobre": "#10240A", "fundo_logo": "#150F3A"}

# Concha compartilhada: a barra inferior é a mesma nos três ambientes; só a cor de destaque acompanha o ambiente ativo.
CONCHA = {"fundo": "#0F1020", "borda": "#262A40", "inativo": "#A7ABC4", "texto_ativo": "#FFFFFF"}
DESTAQUE_NA_CONCHA = {"aprender": "#B6F23E", "analise": "#9C84FF", "wallet": "#D7B25E"}

# Pares (texto, fundo, mínimo) conferidos em test_design.py (WCAG).
def pares_de_contraste(tema_id: str) -> list:
    t = TEMAS[tema_id]
    return [(t["texto"], t["fundo"], 4.5), (t["texto"], t["cartao"], 4.5), (t["apoio"], t["fundo"], 4.5),
            (t["apoio"], t["cartao"], 4.5), (t["sobre_destaque"], t["destaque"], 4.5),
            (t["positivo"], t["cartao"], 3.0), (t["negativo"], t["cartao"], 3.0)]


def pares_da_marca() -> list:
    """Marca sobre os fundos escuros e texto escuro sobre a marca."""
    escuros = [t for t in TEMAS.values() if t["escuro"]]
    return [(MARCA["cor"], t["cartao"], 4.5) for t in escuros] + [(MARCA["sobre"], MARCA["cor"], 4.5)]


def tema_da_area(area_id) -> str:
    """Área (id de areas.py) -> tema. Início, Conta, Planos e Ajuda (sem área) usam o tema da Análise."""
    return {"aprender": "aprender", "wallet": "wallet"}.get(area_id, "analise")


def tema_da_pagina(url_path: str, area_fn) -> str:
    """`area_fn` é areas.area_da_pagina (recebida por parâmetro para este módulo continuar puro)."""
    a = area_fn(url_path)
    return tema_da_area(a["id"] if isinstance(a, dict) else a)
