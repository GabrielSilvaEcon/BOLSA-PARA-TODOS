"""Filtros e categoria das notícias (Fase 6). Módulo puro, sem Streamlit, sem rede e sem banco.

Só reorganiza o que a Central de notícias JÁ coletou (fontes gratuitas: Google Notícias, Federal Reserve, SEC e IBGE). Não busca nada, não inventa
notícia e não cria resumo: o resumo é o texto que a própria fonte publicou (nunca o título repetido). Sem resumo distinto, o cartão não mostra resumo.
Educacional: notícia não é recomendação de investimento.
"""
from __future__ import annotations

import re

FILTROS = ("todas", "brasil", "eua", "cripto", "empresas", "economia")
ROTULOS = {"todas": "Todas", "brasil": "Brasil", "eua": "Estados Unidos", "cripto": "Criptomoedas", "empresas": "Empresas", "economia": "Economia"}

# temas da coleta (noticias_app.TEMAS) e fontes oficiais, agrupados por categoria
_ECONOMIA = {"Política monetária e juros", "Inflação", "Câmbio", "Economia dos EUA", "Economia global", "Renda fixa", "Geopolítica",
             "Federal Reserve", "IBGE"}
_EMPRESAS = {"Mercado de ações", "Bancos e instituições financeiras", "Commodities e setores", "SEC"}
_CRIPTO = {"Criptomoedas e blockchain"}
_FUNDOS = {"FIIs e mercado imobiliário", "ETFs e fundos"}


def categoria(g: dict) -> str:
    """Uma categoria por notícia: Criptomoedas, Empresas, Economia, Fundos ou Mercado (padrão quando nada se aplica)."""
    origem = str(g.get("origem") or "")
    classes = set(g.get("classes") or [])
    if origem in _CRIPTO or (origem.startswith("ativo:") and "cripto" in classes) or classes == {"cripto"}:
        return "Criptomoedas"
    if origem in _FUNDOS:
        return "Fundos"
    if origem in _ECONOMIA:
        return "Economia"
    if origem in _EMPRESAS or origem.startswith("ativo:"):
        return "Empresas"
    return "Mercado"


def pertence(g: dict, filtro: str) -> bool:
    if filtro in (None, "", "todas"):
        return True
    if filtro == "brasil":
        return "Brasil" in (g.get("paises") or [])
    if filtro == "eua":
        return "Estados Unidos" in (g.get("paises") or [])
    if filtro == "cripto":
        return categoria(g) == "Criptomoedas" or "cripto" in (g.get("classes") or [])
    if filtro == "empresas":
        return categoria(g) == "Empresas"
    if filtro == "economia":
        return categoria(g) == "Economia"
    return False


def filtrar(grupos: list[dict], filtro: str) -> list[dict]:
    return [g for g in grupos if pertence(g, filtro)]


def contagens(grupos: list[dict]) -> dict[str, int]:
    return {f: sum(1 for g in grupos if pertence(g, f)) for f in FILTROS}


_TAG = re.compile(r"<[^>]+>")
_ESP = re.compile(r"\s+")


def _limpo(t) -> str:
    return _ESP.sub(" ", _TAG.sub(" ", str(t or ""))).strip()


def _chave(t: str) -> str:
    return re.sub(r"[\W_]+", "", t.lower())


def resumo(g: dict, limite: int = 170) -> str | None:
    """Resumo que a fonte publicou, em texto puro e curto. None se não houver ou se for só o título repetido (ou o título + nome do veículo)."""
    titulo = _chave(_limpo(g.get("titulo")))
    for m in g.get("membros") or [g]:
        txt = _limpo(m.get("resumo"))
        if len(txt) < 25:
            continue
        k = _chave(txt)
        if titulo and (k.startswith(titulo) or titulo.startswith(k) or titulo in k and len(k) - len(titulo) < 40):
            continue
        return txt if len(txt) <= limite else txt[:limite].rsplit(" ", 1)[0].rstrip(",.;:") + "…"
    return None
