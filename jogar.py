"""Jogar: a Competição como jogo educativo. Lógica pura: sem Streamlit, sem banco e sem rede.

Formato (PLANO_AREAS.md, J1 a J4):
 · Missões do dia (3) e desafio da semana (1, gira entre três modelos): tudo calculado a partir do que a Jornada já grava
   (XP por dia e lições concluídas). Não há documento novo, nem tabela nova, nem nada para sincronizar.
 · Pontos do jogo: premiam ESTUDO e BOAS DECISÕES de processo. Nunca lucro, retorno, risco assumido, volume de ordens ou valor da carteira.
   (Mesma regra da Educação: ver `jornada.py` e `EDUCACAO.md`.)
 · Desafios temáticos: concluir todas as lições de uma unidade da Jornada DESBLOQUEIA o desafio dela (5 perguntas da unidade).
   O desbloqueio vale só para o desafio: nenhuma lição, aula ou página da Jornada é bloqueada por causa do jogo.
 · Ranking da liga: reaproveita a liga de estudo (`jornada_liga.py`), que já mostra só apelido e XP da semana.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta

import jornada as JO
import jornada_conteudo as J
import jornada_liga as JL

PTS_MISSAO = 5            # por missão do dia concluída
PTS_SEMANAL = 30          # desafio da semana concluído
PTS_DECISAO = 20          # boa decisão de processo (carteira diversificada), uma vez por semana
TAM_DESAFIO = 5           # perguntas de um desafio temático

# Boa decisão de processo (não olha lucro, retorno nem risco medido): 5 ou mais ativos com peso relevante e nenhum concentrando a carteira.
MIN_ATIVOS = 5
PESO_RELEVANTE = 0.05     # uma posição só conta como "ativo da carteira" se tiver pelo menos 5% do patrimônio
PESO_MAXIMO = 0.25

REGRA = ("Os pontos premiam estudo e boas decisões de processo. Lucro, retorno, risco assumido e quantidade de ordens "
         "nunca valem pontos. Nada é bloqueado: os desafios só se abrem depois de você concluir a unidade da Jornada.")

# id, título, texto, quanto XP no dia vale como cumprida (função da meta diária)
MISSOES = (
    dict(id="estudar", titulo="Estude hoje", texto="Conclua uma lição ou uma revisão.", alvo=lambda meta: 1),
    dict(id="meta", titulo="Bata a meta do dia", texto="Chegue à sua meta diária de XP.", alvo=lambda meta: meta),
    dict(id="dourado", titulo="Dia dourado", texto="Dobre a meta diária de XP.", alvo=lambda meta: meta * 2),
)

SEMANAIS = ("dias", "metas", "xp")


# ------------------------------------------------------------------ datas
def _hoje(agora: datetime | None) -> date:
    return JO.hoje(agora)


def dias_da_semana(agora: datetime | None = None) -> list[date]:
    """De segunda-feira até hoje (horário de Brasília)."""
    h = _hoje(agora)
    ini = JL.inicio_semana(h)
    return [ini + timedelta(days=i) for i in range((h - ini).days + 1)]


def _xp_por_dia(p: dict) -> tuple[dict, int]:
    j = JO._jor(p)
    return j["xp_dia"], j["meta_dia"]


# ------------------------------------------------------------------ missões do dia
def _missao_ok(m: dict, xp: int, meta: int) -> bool:
    return xp >= m["alvo"](meta)


def missoes_do_dia(p: dict, agora: datetime | None = None) -> list[dict]:
    xp_dia, meta = _xp_por_dia(p)
    xp = xp_dia.get(_hoje(agora).isoformat(), 0)
    out = []
    for m in MISSOES:
        alvo = m["alvo"](meta)
        out.append({"id": m["id"], "titulo": m["titulo"], "texto": m["texto"], "atual": min(xp, alvo), "alvo": alvo,
                    "ok": _missao_ok(m, xp, meta), "pontos": PTS_MISSAO})
    return out


# ------------------------------------------------------------------ desafio da semana
def _modelo_da_semana(agora: datetime | None) -> str:
    ano, sem, _ = _hoje(agora).isocalendar()
    return SEMANAIS[(ano * 53 + sem) % len(SEMANAIS)]


def desafio_semana(p: dict, agora: datetime | None = None) -> dict:
    xp_dia, meta = _xp_por_dia(p)
    dias = [d.isoformat() for d in dias_da_semana(agora)]
    xps = [xp_dia.get(d, 0) for d in dias]
    modelo = _modelo_da_semana(agora)
    if modelo == "dias":
        atual, alvo = sum(1 for x in xps if x > 0), 5
        titulo, texto = "Estude em 5 dias", "Estude em 5 dias diferentes até domingo. Pode ser uma lição curta por dia."
    elif modelo == "metas":
        atual, alvo = sum(1 for x in xps if x >= meta), 3
        titulo, texto = "Meta batida 3 vezes", "Bata a meta diária de XP em 3 dias desta semana."
    else:
        atual, alvo = sum(xps), 150
        titulo, texto = "150 XP de estudo", "Junte 150 XP de estudo de segunda a domingo."
    return {"id": modelo, "titulo": titulo, "texto": texto, "atual": min(atual, alvo), "alvo": alvo, "ok": atual >= alvo,
            "pontos": PTS_SEMANAL, "semana": JL.semana_atual(agora)}


# ------------------------------------------------------------------ boa decisão de processo (Competição)
def diversificada(estado) -> dict:
    """Olha só COMO a carteira virtual foi montada: quantos ativos têm peso relevante e qual o maior peso.
    Não usa retorno, lucro, risco medido nem número de ordens. `ok` exige 5+ ativos relevantes e nenhum acima de 25%."""
    vazio = {"ok": False, "ativos": 0, "maior_peso": 0.0}
    if not isinstance(estado, dict) or estado.get("v") != 1:
        return vazio
    try:
        import competicao as C
        pat = C.patrimonio(estado)
        if pat <= 0:
            return vazio
        pesos = []
        for tk, pos in (estado.get("pos") or {}).items():
            px = (estado.get("ult") or {}).get(tk) or pos.get("pm") or 0.0
            pesos.append(pos["q"] * px / pat)
    except Exception:
        return vazio
    relevantes = [w for w in pesos if w >= PESO_RELEVANTE]
    maior = max(pesos) if pesos else 0.0
    return {"ok": len(relevantes) >= MIN_ATIVOS and maior <= PESO_MAXIMO, "ativos": len(relevantes), "maior_peso": maior}


# ------------------------------------------------------------------ pontos (J2)
def pontos_semana(p: dict, agora: datetime | None = None, boa_decisao: bool = False) -> dict:
    """Pontos da semana = XP de estudo + 5 por missão do dia cumprida + 30 do desafio da semana + 20 da boa decisão.
    Só recebe o progresso de ESTUDO e um sim/não de processo: não há como retorno, lucro ou risco entrarem na conta."""
    xp_dia, meta = _xp_por_dia(p)
    estudo = missoes = 0
    for d in dias_da_semana(agora):
        xp = xp_dia.get(d.isoformat(), 0)
        estudo += xp
        missoes += sum(1 for m in MISSOES if _missao_ok(m, xp, meta)) * PTS_MISSAO
    desafio = PTS_SEMANAL if desafio_semana(p, agora)["ok"] else 0
    decisao = PTS_DECISAO if boa_decisao else 0
    return {"estudo": estudo, "missoes": missoes, "desafio": desafio, "decisao": decisao,
            "total": estudo + missoes + desafio + decisao}


# ------------------------------------------------------------------ desafios temáticos ligados à Jornada (J4)
def desafios_tematicos(p: dict) -> list[dict]:
    """Um desafio por unidade da Jornada. Abre quando todas as lições da unidade foram concluídas. Nada na Jornada depende disso."""
    out = []
    for u in JO.mapa(p):
        perguntas = sum(l["exercicios"] for l in u["licoes"])
        out.append({"id": u["id"], "titulo": u["titulo"], "svg": u["svg"], "cor": u["cor"], "descricao": u["descricao"],
                    "liberado": bool(u["completa"]), "falta": u["total"] - u["feitas"], "total": u["total"], "perguntas": perguntas})
    return out


def iniciar_desafio(unidade_id: str, p: dict, agora: datetime | None = None) -> dict | None:
    """Sessão do desafio: 5 perguntas sorteadas (estável no mesmo dia) entre as lições da unidade, no formato que o player da Jornada já usa
    (sessão de revisão: vale o XP de revisão, só estudo). None se a unidade não existe ou ainda não foi concluída."""
    d = next((x for x in desafios_tematicos(p) if x["id"] == unidade_id), None)
    if not d or not d["liberado"]:
        return None
    un = next(u for u in J.UNIDADES if u["id"] == unidade_id)
    ids = [e["id"] for lid in un["licoes"] for e in J.LICAO_POR_ID[lid]["exercicios"]]
    if not ids:
        return None
    rng = random.Random(f"{unidade_id}|{_hoje(agora).isoformat()}")
    escolhidos = rng.sample(ids, min(TAM_DESAFIO, len(ids)))
    return {"licao": None, "fila": list(escolhidos), "total": len(escolhidos), "feitos": 0, "erros_ids": [], "revisao": True,
            "ids": list(escolhidos), "nome": f"Desafio: {d['titulo']}"}


# ------------------------------------------------------------------ resumo para a tela
def resumo(p: dict, agora: datetime | None = None, boa_decisao: bool = False) -> dict:
    ms = missoes_do_dia(p, agora)
    return {"missoes": ms, "feitas": sum(1 for m in ms if m["ok"]), "semanal": desafio_semana(p, agora),
            "pontos": pontos_semana(p, agora, boa_decisao), "ofensiva": JO.ofensiva(p, agora), "xp_hoje": JO.xp_hoje(p, agora)}
