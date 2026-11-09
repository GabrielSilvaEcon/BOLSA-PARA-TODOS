"""Paletas dos três ambientes + a concha (barra inferior) que é igual nos três. Só cores; nada de lógica de negócio."""
from __future__ import annotations

TEMAS = {
    "aprender": {
        "nome": "Aprender", "escuro": False,
        "fundo": "#F7F5FF", "cartao": "#FFFFFF", "elevado": "#EDE8FF", "borda": "#E6E1F5",
        "texto": "#1E1B2E", "apoio": "#5F5A75", "destaque": "#6C47FF", "sobre_destaque": "#FFFFFF",
        "secundaria": "#B9A8FF", "positivo": "#157F55", "negativo": "#C93A47",
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

# Concha compartilhada: a barra inferior é a mesma nos três ambientes; só a cor de destaque acompanha o ambiente ativo.
CONCHA = {"fundo": "#0F1020", "borda": "#262A40", "inativo": "#A7ABC4", "texto_ativo": "#FFFFFF"}
DESTAQUE_NA_CONCHA = {"aprender": "#9B84FF", "analise": "#9C84FF", "wallet": "#D7B25E"}

# Pares (texto, fundo, mínimo) conferidos em test_design.py (WCAG).
def pares_de_contraste(tema_id: str) -> list:
    t = TEMAS[tema_id]
    return [(t["texto"], t["fundo"], 4.5), (t["texto"], t["cartao"], 4.5), (t["apoio"], t["fundo"], 4.5),
            (t["apoio"], t["cartao"], 4.5), (t["sobre_destaque"], t["destaque"], 4.5),
            (t["positivo"], t["cartao"], 3.0), (t["negativo"], t["cartao"], 3.0)]


def tema_da_area(area_id) -> str:
    """Área (id de areas.py) -> tema. Início, Conta, Planos e Ajuda (sem área) usam o tema da Análise."""
    return {"aprender": "aprender", "wallet": "wallet"}.get(area_id, "analise")


def tema_da_pagina(url_path: str, area_fn) -> str:
    """`area_fn` é areas.area_da_pagina (recebida por parâmetro para este módulo continuar puro)."""
    a = area_fn(url_path)
    return tema_da_area(a["id"] if isinstance(a, dict) else a)
