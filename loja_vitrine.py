"""Vitrine da Loja Ticker (Fase 5). Módulo puro, sem Streamlit, sem banco e sem rede: só organiza o catálogo de `tickercoins.py` em categorias
e decide o estado de cada item para a tela. Não cria produto, não muda preço, não cobra e não entrega nada: a compra continua toda em
`tickercoins.comprar` (débito seguro, pedido idempotente, extrato e estorno). Ticker Coins, XP e T$ seguem independentes.

Regra de honestidade: categoria sem item REAL para entregar aparece como "em preparação", sem preço nem botão de compra.
"""
from __future__ import annotations

# (id, rótulo, tipos de efeito do catálogo que pertencem à categoria, texto de "em preparação" ou None quando há itens)
VITRINE = (
    ("emblemas", "Emblemas", ("distintivo",), None),
    ("molduras", "Molduras", ("moldura",), None),
    ("temas", "Temas", ("tema",), "Temas de cor para o app: ainda não existe nenhum tema pronto para desbloquear."),
    ("especiais", "Itens especiais", ("especial",), "Itens especiais: ainda não existe nenhum item extra que possa ser liberado sem afetar o jogo."),
    ("beneficios", "Benefícios", ("bonus_limite",), None),
)
ROTULOS = {c[0]: c[1] for c in VITRINE}
IDS = tuple(c[0] for c in VITRINE)
_EQUIPAVEIS = ("distintivo", "moldura")


def categoria_de(produto: dict) -> str | None:
    kind = (produto.get("efeito") or {}).get("kind")
    return next((c[0] for c in VITRINE if kind in c[2]), None)


def itens_da_categoria(catalogo: list[dict], cat: str) -> list[dict]:
    return [p for p in catalogo if categoria_de(p) == cat]


def texto_preparacao(cat: str) -> str | None:
    return next((c[3] for c in VITRINE if c[0] == cat), None)


def equipavel(produto: dict) -> bool:
    return (produto.get("efeito") or {}).get("kind") in _EQUIPAVEIS


def status(produto: dict, possui: set, equipado: dict, saldo: int | None) -> dict:
    """Estado do item para a tela. `possui` = ids com benefício em vigor; `equipado` = {"distintivo": id, "moldura": id}.
    rotulo: texto da etiqueta; cls: ok | uso | falta | livre."""
    pid, kind = produto["id"], (produto.get("efeito") or {}).get("kind")
    if pid in possui:
        if kind in _EQUIPAVEIS and (equipado or {}).get(kind) == pid:
            return {"rotulo": "Em uso", "cls": "uso", "tem": True}
        return {"rotulo": "Ativo hoje" if produto.get("validade_h") == "meia_noite" else "Você tem", "cls": "ok", "tem": True}
    if saldo is not None and saldo < int(produto["preco"]):
        return {"rotulo": f"Faltam {int(produto['preco']) - int(saldo)} TC", "cls": "falta", "tem": False}
    return {"rotulo": "Disponível", "cls": "livre", "tem": False}


def previa(produto: dict) -> dict:
    """O que desenhar no círculo do item: {"tipo": "emoji"|"anel"|"texto", "valor": str, "cor": str}."""
    ef, cor = produto.get("efeito") or {}, produto.get("cor") or "#8B6CFF"
    if ef.get("kind") == "distintivo":
        return {"tipo": "emoji", "valor": str(ef.get("emoji") or "⭐"), "cor": cor}
    if ef.get("kind") == "moldura":
        return {"tipo": "anel", "valor": "", "cor": str(ef.get("cor") or cor)}
    return {"tipo": "texto", "valor": f"+{int(ef.get('extra', 0))}" if ef.get("extra") else "★", "cor": cor}
