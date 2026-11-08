"""Jogar: pontuação do jogo educativo. Lógica pura (sem Streamlit, banco ou rede). Etapa J2 do PLANO_AREAS.md.

Regra de ouro (a mesma da Educação): a pontuação premia ESTUDO e BOA DECISÃO, nunca lucro nem risco.
 · Estudo: o XP da Jornada de cada dia, com teto diário (repetir lições à toa não leva ao topo).
 · Missões do dia: 3 tarefas curtas de estudo, com bônus por fazer as três.
 · Desafio da semana: nota de 0 a 100 da QUALIDADE da carteira virtual (quantos ativos, quanto pesa o maior, quantas classes).
   A nota usa só o que a pessoa escolheu comprar (quantidade e preço médio de compra). Preço atual, lucro, prejuízo, volatilidade
   e retorno nunca entram na conta: duas carteiras com as mesmas compras têm a mesma nota, rendam o que rendessem.
O ranking por retorno da Competição segue à parte e não soma pontos aqui.
"""
from __future__ import annotations

from datetime import date, timedelta

import jornada_liga as JL

MISSOES = {
    "licao": "Conclua 1 lição",
    "revisao": "Revise seus erros",
    "termo": "Leia 1 termo do glossário",
}
PONTOS_MISSAO = 10
BONUS_TODAS = 10               # fazer as 3 missões do dia
TETO_XP_DIA = 60               # XP de estudo que conta por dia (a meta padrão da Jornada é 20)
PONTOS_DESAFIO = 50            # pontos do desafio da semana com nota 100
DIAS_GUARDADOS = 14            # histórico de missões que fica no documento da pessoa

# nota da carteira: pontos por critério (somam 100 com as classes; sem informação de classes, vale proporcional)
_PTS_ATIVOS = {1: 0, 2: 10, 3: 20, 4: 30}      # 5 ou mais = 40
_PTS_ATIVOS_MAX = 40
_FAIXAS_PESO = ((0.25, 40), (0.30, 30), (0.35, 20), (0.40, 10))   # maior peso (pelo valor comprado) até X = tantos pontos
_PTS_CLASSES = {1: 0, 2: 10}                   # 3 ou mais = 20
_PTS_CLASSES_MAX = 20


# ------------------------------------------------------------------ missões do dia
def _dia(d) -> str:
    return d.isoformat() if isinstance(d, date) else str(d)


def normalizar_missoes(doc) -> dict:
    """Aceita lixo/ausente e devolve {'dias': {'AAAA-MM-DD': [tipos válidos sem repetição]}} (só os últimos dias)."""
    dias = {}
    bruto = doc.get("dias") if isinstance(doc, dict) else None
    for k, v in (bruto or {}).items():
        try:
            date.fromisoformat(str(k))
        except ValueError:
            continue
        if isinstance(v, (list, tuple)):
            vistos = []
            for t in v:
                if t in MISSOES and t not in vistos:
                    vistos.append(t)
            dias[str(k)] = vistos
    return {"dias": dict(sorted(dias.items())[-DIAS_GUARDADOS:])}


def concluir_missao(doc, dia, tipo: str) -> dict:
    """Marca a missão do dia como feita. Repetir não faz nada; tipo desconhecido é ignorado. Não altera o original."""
    novo = normalizar_missoes(doc)
    if tipo not in MISSOES:
        return novo
    d = _dia(dia)
    feitas = novo["dias"].setdefault(d, [])
    if tipo not in feitas:
        feitas.append(tipo)
    return normalizar_missoes(novo)


def missoes_do_dia(doc, dia) -> list:
    """Tipos de missão já feitos no dia."""
    return list(normalizar_missoes(doc)["dias"].get(_dia(dia), []))


def pontos_missoes_dia(doc, dia) -> int:
    feitas = missoes_do_dia(doc, dia)
    return len(feitas) * PONTOS_MISSAO + (BONUS_TODAS if len(feitas) == len(MISSOES) else 0)


def pontos_missoes_semana(doc, hoje: date) -> int:
    ini = JL.inicio_semana(hoje)
    return sum(pontos_missoes_dia(doc, ini + timedelta(days=i)) for i in range((hoje - ini).days + 1))


# ------------------------------------------------------------------ estudo
def pontos_estudo_semana(xp_dia: dict, hoje: date) -> int:
    """XP da Jornada de segunda até hoje, com teto por dia (TETO_XP_DIA)."""
    ini, fim = JL.inicio_semana(hoje).isoformat(), hoje.isoformat()
    total = 0
    for d, v in (xp_dia or {}).items():
        try:
            n = int(v)
        except (TypeError, ValueError):
            continue
        if ini <= str(d) <= fim:
            total += min(max(n, 0), TETO_XP_DIA)
    return total


# ------------------------------------------------------------------ desafio da semana: qualidade da carteira
def nota_carteira(pos: dict, classes: dict | None = None) -> int:
    """Nota de 0 a 100 pela qualidade das ESCOLHAS: nº de ativos, peso do maior (pelo valor comprado) e nº de classes.
    `pos` = {ticker: {'q': quantidade, 'pm': preço médio de compra}}; qualquer outro campo é ignorado, e é de propósito:
    preço atual, lucro e retorno não entram. `classes` = {ticker: classe} (opcional; sem ele a nota usa só os dois primeiros critérios)."""
    custos = {}
    for tk, p in (pos or {}).items():
        try:
            c = float(p["q"]) * float(p["pm"])
        except (KeyError, TypeError, ValueError):
            continue
        if c > 0:
            custos[tk] = c
    if not custos:
        return 0
    total = sum(custos.values())
    n = len(custos)
    pts = _PTS_ATIVOS_MAX if n >= 5 else _PTS_ATIVOS.get(n, 0)
    maior = max(custos.values()) / total
    pts += next((p for lim, p in _FAIXAS_PESO if maior <= lim + 1e-9), 0)
    maximo = _PTS_ATIVOS_MAX + 40
    if classes:
        nc = len({classes[tk] for tk in custos if classes.get(tk)})
        pts += _PTS_CLASSES_MAX if nc >= 3 else _PTS_CLASSES.get(nc, 0)
        maximo += _PTS_CLASSES_MAX
    return round(100 * pts / maximo)


def pontos_desafio(nota: int | None) -> int:
    """Pontos do desafio da semana (0 a PONTOS_DESAFIO), proporcionais à nota."""
    if nota is None:
        return 0
    return round(PONTOS_DESAFIO * min(100, max(0, int(nota))) / 100)


# ------------------------------------------------------------------ placar da semana
def pontos_semana(xp_dia: dict, missoes_doc, nota: int | None, hoje: date) -> dict:
    """Pontos da semana por fonte e o total (é o que o ranking da liga mostra)."""
    estudo = pontos_estudo_semana(xp_dia, hoje)
    missoes = pontos_missoes_semana(missoes_doc, hoje)
    desafio = pontos_desafio(nota)
    return {"estudo": estudo, "missoes": missoes, "desafio": desafio, "total": estudo + missoes + desafio}
