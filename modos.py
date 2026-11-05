"""Base para os três modos de experiência (Passo 21): INICIANTE, INTERMEDIÁRIO e AVANÇADO.

Só a estrutura: NENHUMA tela usa isto ainda e não há seletor para a pessoa. Os modos mudarão só a APRESENTAÇÃO
(linguagem, nível de detalhe, quais indicadores aparecem), sempre sobre os mesmos dados e o mesmo motor de cálculo;
não há planos nem preços por modo. Quando for a hora, cada tela escolhe o que mostrar com por_modo(...), sem copiar
módulos nem cálculos.
"""
from __future__ import annotations

MODOS = ("iniciante", "intermediario", "avancado")
PADRAO = "intermediario"
ROTULOS = {"iniciante": "Iniciante", "intermediario": "Intermediário", "avancado": "Avançado"}


def modo_valido(modo) -> str:
    return modo if modo in MODOS else PADRAO


def modo_atual(prefs: dict | None = None) -> str:
    """Modo da pessoa, lido das preferências (chave 'modo'). Sem preferência, usa o padrão."""
    return modo_valido((prefs or {}).get("modo"))


def por_modo(iniciante=None, intermediario=None, avancado=None, modo: str | None = None):
    """Escolhe o conteúdo do modo. Se o modo não tem versão própria, usa a mais próxima:
    iniciante -> intermediário -> avançado; avançado -> intermediário -> iniciante."""
    m = modo_valido(modo)
    ordem = {"iniciante": ("iniciante", "intermediario", "avancado"),
             "intermediario": ("intermediario", "avancado", "iniciante"),
             "avancado": ("avancado", "intermediario", "iniciante")}[m]
    v = {"iniciante": iniciante, "intermediario": intermediario, "avancado": avancado}
    for k in ordem:
        if v[k] is not None:
            return v[k]
    return None
