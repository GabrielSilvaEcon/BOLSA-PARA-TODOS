"""Vitrine da Loja Ticker (Fases 5 e 8). Módulo puro, sem Streamlit, sem banco e sem rede: organiza o catálogo de `tickercoins.py`
em grupos e subcategorias (tudo definido em `loja_catalogo.py`) e decide o estado de cada item para a tela.
Não cria produto, não muda preço, não cobra e não entrega nada: a compra continua toda em `tickercoins.comprar`
(débito seguro, pedido idempotente, extrato e estorno). Ticker Coins, XP e T$ seguem independentes.

Regra de honestidade: subcategoria sem item REAL para entregar aparece como "em preparação", sem preço nem botão de compra.
"""
from __future__ import annotations

from datetime import date

import loja_catalogo as LC

GRUPOS = LC.GRUPOS
GRUPO_IDS = tuple(g[0] for g in GRUPOS)
GRUPO_ROTULOS = {g[0]: g[1] for g in GRUPOS}
SUBGRUPOS = LC.SUBGRUPOS
ROTULOS = {s[0]: s[1] for s in SUBGRUPOS}
IDS = tuple(s[0] for s in SUBGRUPOS)


def subs_do_grupo(grupo: str) -> tuple:
    return tuple(s[0] for s in SUBGRUPOS if s[2] == grupo)


def categoria_de(produto: dict) -> str | None:
    """Subcategoria do item ('temas', 'molduras', 'fundos', 'efeitos', 'selos', 'beneficios')."""
    return LC.subgrupo_de((produto.get("efeito") or {}).get("kind"))


def itens_da_categoria(catalogo: list[dict], cat: str) -> list[dict]:
    """Itens da subcategoria, dos mais comuns para os mais raros e, dentro da raridade, do mais barato ao mais caro."""
    itens = [p for p in catalogo if categoria_de(p) == cat]
    return sorted(itens, key=lambda p: (LC.RARIDADES.get(p.get("raridade"), LC.RARIDADES["comum"])["ordem"], p["preco"]))


def texto_preparacao(cat: str) -> str | None:
    return next((s[3] for s in SUBGRUPOS if s[0] == cat), None)


def equipavel(produto: dict) -> bool:
    return bool(LC.FAMILIAS.get((produto.get("efeito") or {}).get("kind"), {}).get("equipavel"))


def raridade(produto: dict) -> dict:
    r = LC.RARIDADES.get(produto.get("raridade") or "comum", LC.RARIDADES["comum"])
    return {"id": produto.get("raridade") or "comum", "rotulo": r["rotulo"], "cor": r["cor"]}


def status(produto: dict, possui: set, equipado: dict, saldo: int | None, hoje: date | None = None) -> dict:
    """Estado do item para a tela. `possui` = ids com benefício em vigor; `equipado` = {tipo: id}.
    rotulo: texto da etiqueta; cls: ok | uso | falta | livre | fora."""
    pid, kind = produto["id"], (produto.get("efeito") or {}).get("kind")
    if pid in possui:
        if equipavel(produto) and (equipado or {}).get(kind) == pid:
            return {"rotulo": "Em uso", "cls": "uso", "tem": True}
        return {"rotulo": "Ativo hoje" if produto.get("validade_h") == "meia_noite" else "Você tem", "cls": "ok", "tem": True}
    if hoje is not None and not LC.na_janela(produto, hoje):
        return {"rotulo": "Fora de temporada", "cls": "fora", "tem": False}
    if saldo is not None and saldo < int(produto["preco"]):
        return {"rotulo": f"Faltam {int(produto['preco']) - int(saldo)} TC", "cls": "falta", "tem": False}
    return {"rotulo": "Disponível", "cls": "livre", "tem": False}


def previa(produto: dict) -> dict:
    """O que desenhar na prévia do item. tipo: emoji | anel | texto | tema | fundo | efeito."""
    ef, cor = produto.get("efeito") or {}, produto.get("cor") or "#8B6CFF"
    k = ef.get("kind")
    if k in ("distintivo", "selo"):
        return {"tipo": "emoji", "valor": str(ef.get("emoji") or "⭐"), "cor": cor}
    if k == "moldura":
        return {"tipo": "anel", "valor": "", "cor": str(ef.get("cor") or cor), "estilo": ef.get("estilo", "solido"), "cores": list(ef.get("cores") or [])}
    if k == "tema":
        return {"tipo": "tema", "valor": "", "cor": cor, "paleta": LC.PALETAS.get(ef.get("paleta")) or {}}
    if k == "fundo":
        return {"tipo": "fundo", "valor": "", "cor": cor, "de": ef.get("de", "#3A2C86"), "para": ef.get("para", "#1B1545"), "luz": ef.get("luz")}
    if k in ("efeito_nivel", "efeito_conquista", "efeito_bau"):
        return {"tipo": "efeito", "valor": "", "cor": cor, "cores": list(ef.get("cores") or [cor]), "formas": ef.get("formas", "bolha")}
    return {"tipo": "texto", "valor": f"+{int(ef.get('extra', 0))}" if ef.get("extra") else "★", "cor": cor}
