"""Preferências do usuário (Passo 21). Módulo puro.

Ficam dentro do JSON de dados da própria pessoa (chave "prefs", gravada em perfis só para o dono). Tudo que vem do
banco passa por normalizar(): valores fora da lista permitida viram o padrão, listas são limpas e limitadas, e chaves
desconhecidas são descartadas. Assim nada digitado ou corrompido chega às telas.
"""
from __future__ import annotations

import re

MOEDAS = {"BRL": "Real (R$)", "USD": "Dólar (US$)", "EUR": "Euro (€)"}
PAISES = {"BR": "Brasil", "US": "Estados Unidos", "PT": "Portugal"}
IDIOMAS = {"pt-BR": "Português (Brasil)"}          # outros idiomas entram aqui quando existirem
TEMAS = {"sistema": "Automático", "claro": "Claro", "escuro": "Escuro"}
PERIODOS = {"1m": "1 mês", "3m": "3 meses", "6m": "6 meses", "12m": "12 meses", "24m": "24 meses", "5a": "5 anos", "max": "Máximo"}
GRAFICO_TIPOS = {"linha": "Linha", "area": "Área", "candle": "Candles"}
GRAFICO_ALTURAS = {"normal": "Normal", "alta": "Alta"}
INDICADORES = ("P/L", "P/VP", "Dividend Yield", "ROE", "ROIC", "Margem líquida", "Dívida/PL", "Payout", "CAGR",
               "Volatilidade", "Sharpe", "Drawdown máximo", "Beta")
BLOCOS = {"resumo": "Resumo", "carteira": "Minha carteira", "favoritos": "Ativos favoritos", "alertas": "Alertas",
          "relatorios": "Relatórios", "noticias": "Notícias"}
MODOS = ("iniciante", "intermediario", "avancado")   # só preparado: a divisão dos modos vem depois dos 25 passos

EXP_DETALHE = {"auto": "Automático (do meu modo)", "menos": "Menos informações", "mais": "Mais informações"}
EXP_TRI = {"auto": "Automático (do meu modo)", "sim": "Sempre", "nao": "Nunca"}

PADRAO = {
    "moeda": "BRL", "pais": "BR", "idioma": "pt-BR", "tema": "sistema", "periodo": "12m",
    "grafico": {"tipo": "linha", "altura": "normal", "grade": True},
    "indicadores": ["P/L", "P/VP", "Dividend Yield", "ROE"],
    "ativos_favoritos": [], "carteiras_favoritas": [],
    "notificacoes": {"alertas": True, "relatorios": False, "email": False},
    "dashboard": {"ordem": list(BLOCOS), "ocultos": []},
    "modo": "intermediario",
    "exp": {"detalhe": "auto", "explicacoes": "auto", "dicas": "auto"},     # personalização DENTRO do modo (só apresentação)
}
_TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,14}$")
_MAX_FAV = 50


def _em(v, permitidos, padrao):
    return v if isinstance(v, str) and v in permitidos else padrao


def _bool(v, padrao):
    return v if isinstance(v, bool) else padrao


def _lista_texto(v, valido, limite):
    out = []
    for x in v if isinstance(v, (list, tuple)) else []:
        x = str(x).strip()
        if valido(x) and x not in out:
            out.append(x)
        if len(out) >= limite:
            break
    return out


def normalizar_ticker(t) -> str:
    return str(t or "").strip().upper()


def normalizar(p) -> dict:
    """Devolve sempre um dict completo e válido, mesmo com entrada vazia, de tipo errado ou adulterada."""
    p = p if isinstance(p, dict) else {}
    g = p.get("grafico") if isinstance(p.get("grafico"), dict) else {}
    n = p.get("notificacoes") if isinstance(p.get("notificacoes"), dict) else {}
    d = p.get("dashboard") if isinstance(p.get("dashboard"), dict) else {}
    ordem = _lista_texto(d.get("ordem"), lambda x: x in BLOCOS, len(BLOCOS))
    ordem += [b for b in BLOCOS if b not in ordem]
    ocultos = _lista_texto(d.get("ocultos"), lambda x: x in BLOCOS, len(BLOCOS))
    pd_ = PADRAO
    e = p.get("exp") if isinstance(p.get("exp"), dict) else {}
    return {
        "moeda": _em(p.get("moeda"), MOEDAS, pd_["moeda"]),
        "pais": _em(p.get("pais"), PAISES, pd_["pais"]),
        "idioma": _em(p.get("idioma"), IDIOMAS, pd_["idioma"]),
        "tema": _em(p.get("tema"), TEMAS, pd_["tema"]),
        "periodo": _em(p.get("periodo"), PERIODOS, pd_["periodo"]),
        "grafico": {"tipo": _em(g.get("tipo"), GRAFICO_TIPOS, "linha"), "altura": _em(g.get("altura"), GRAFICO_ALTURAS, "normal"),
                    "grade": _bool(g.get("grade"), True)},
        "indicadores": _lista_texto(p.get("indicadores", pd_["indicadores"]), lambda x: x in INDICADORES, 20),
        "ativos_favoritos": _lista_texto([normalizar_ticker(x) for x in (p.get("ativos_favoritos") or [])
                                          if isinstance(x, (str, int))], lambda x: bool(_TICKER.match(x)), _MAX_FAV),
        "carteiras_favoritas": _lista_texto(p.get("carteiras_favoritas"), lambda x: 0 < len(x) <= 60 and "<" not in x and ">" not in x, 20),
        "notificacoes": {"alertas": _bool(n.get("alertas"), True), "relatorios": _bool(n.get("relatorios"), False),
                         "email": _bool(n.get("email"), False)},
        "dashboard": {"ordem": ordem, "ocultos": ocultos},
        "modo": _em(p.get("modo"), MODOS, pd_["modo"]),
        "exp": {"detalhe": _em(e.get("detalhe"), EXP_DETALHE, "auto"), "explicacoes": _em(e.get("explicacoes"), EXP_TRI, "auto"),
                "dicas": _em(e.get("dicas"), EXP_TRI, "auto")},
    }


def alternar_favorito(prefs: dict, ticker: str) -> dict:
    p = normalizar(prefs)
    t = normalizar_ticker(ticker)
    if not _TICKER.match(t):
        return p
    fav = list(p["ativos_favoritos"])
    fav.remove(t) if t in fav else fav.append(t)
    p["ativos_favoritos"] = fav[:_MAX_FAV]
    return normalizar(p)
