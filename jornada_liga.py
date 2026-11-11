"""Liga de estudo (opcional) da Jornada. Lógica pura: sem Streamlit, sem banco e sem rede.

Como se encaixa, sem tabela nova e sem mexer no fechamento diário da competição:
 · Reaproveita as ligas de amigos de `competicao_ligas.py` (o mesmo código de convite): quem já está numa liga pode, se quiser,
   mostrar nela o **XP de estudo da semana**. Quem não ligar a opção não aparece em nenhum ranking (padrão: desligado).
 · Cada pessoa grava só o próprio documento `edu_liga` (monitor_estado): {ligado, semana, xp, apelido}. O apelido é o mesmo da competição
   (já é público nos rankings); nunca vai e-mail, nem XP total, nem erros, nem nada do conteúdo estudado.
 · O ranking é montado na hora, a partir dos documentos dos membros da liga (banco.edu_liga_ranking confere que quem pede é membro).
Regras do projeto: o placar só mede **estudo** (XP de lição e revisão); nunca operação, retorno ou risco. Sem prêmio, sem bloqueio.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import jornada as JO

CH_EDU_LIGA = "edu_liga"
TOPO = 50                      # linhas mostradas no ranking da liga
XP_SEMANA_MAX = 10_000         # teto de sanidade (um documento adulterado não distorce o placar)


# ------------------------------------------------------------------ semana (segunda a domingo, horário de Brasília)
def inicio_semana(d: date) -> date:
    return d - timedelta(days=d.weekday())


def semana_id(d: date) -> str:
    """'2026-W45': ano e semana ISO da data."""
    ano, sem, _ = d.isocalendar()
    return f"{ano}-W{sem:02d}"


def semana_atual(agora: datetime | None = None) -> str:
    return semana_id(JO.hoje(agora))


def xp_semana(p: dict, agora: datetime | None = None) -> int:
    """XP ganho de segunda-feira até hoje (soma de xp_dia). Só estudo: lição, bônus de lição perfeita e revisão."""
    j = JO._jor(p)
    h = JO.hoje(agora)
    ini = inicio_semana(h).isoformat()
    fim = h.isoformat()
    return sum(int(v) for d, v in j["xp_dia"].items() if ini <= d <= fim)


# ------------------------------------------------------------------ documento da pessoa
def _int(v, minimo: int, maximo: int) -> int:
    try:
        return max(minimo, min(maximo, int(v)))
    except (TypeError, ValueError):
        return minimo


def _apelido(v) -> str:
    """Apelido da competição (3 a 20 caracteres: letras, números, ponto, hífen ou sublinhado; sem espaços). Qualquer outra coisa vira vazio."""
    import competicao as C
    s = str(v or "").strip()
    return s if C.apelido_valido(s)[0] else ""


def sanear(doc) -> dict:
    d = doc if isinstance(doc, dict) else {}
    sem = str(d.get("semana") or "")
    ok_sem = len(sem) == 8 and sem[4:6] == "-W" and sem[:4].isdigit() and sem[6:].isdigit()
    return {"v": 1, "ligado": bool(d.get("ligado")), "semana": sem if ok_sem else "", "xp": _int(d.get("xp"), 0, XP_SEMANA_MAX),
            "apelido": _apelido(d.get("apelido"))}


def atualizar(doc, p: dict, apelido: str, agora: datetime | None = None) -> dict:
    """Documento novo com o XP da semana atual e o apelido. Não muda a opção ligado/desligado."""
    d = sanear(doc)
    d.update({"semana": semana_atual(agora), "xp": _int(xp_semana(p, agora), 0, XP_SEMANA_MAX), "apelido": _apelido(apelido)})
    return d


def definir_ligado(doc, ligado: bool, p: dict | None = None, apelido: str = "", agora: datetime | None = None) -> dict:
    """Liga ou desliga a participação. Ao desligar, zera o XP publicado (nada fica visível para a liga)."""
    d = sanear(doc)
    if not ligado:
        return {**d, "ligado": False, "xp": 0, "semana": ""}
    d = atualizar({**d, "ligado": True}, p or {}, apelido, agora)
    return {**d, "ligado": True}


def pode_participar(apelido: str) -> tuple[bool, str]:
    if not _apelido(apelido):
        return False, "Para aparecer na liga de estudo você precisa de um apelido da Wallet Game (é o mesmo que já aparece nos rankings)."
    return True, ""


# ------------------------------------------------------------------ ranking da liga
def montar(linhas: list[dict], semana: str) -> list[dict]:
    """linhas: [{'apelido','ligado','semana','xp','eu'}] de membros da liga. Devolve o ranking da `semana`: só quem ligou e tem apelido.
    Documento de semana antiga conta como 0 XP (a pessoa não estudou nesta semana). Empate divide a posição (1, 2, 2, 4)."""
    itens = []
    for x in linhas or []:
        d = sanear(x)
        if not d["ligado"] or not d["apelido"]:
            continue
        itens.append({"apelido": d["apelido"], "xp": d["xp"] if d["semana"] == semana else 0, "eu": bool(x.get("eu"))})
    vistos, unicos = set(), []
    for it in sorted(itens, key=lambda i: (-i["xp"], i["apelido"].lower())):     # apelido repetido: fica um só
        k = it["apelido"].lower()
        if k not in vistos:
            vistos.add(k)
            unicos.append(it)
    for i, it in enumerate(unicos):
        it["pos"] = 1 if i == 0 else (unicos[i - 1]["pos"] if it["xp"] == unicos[i - 1]["xp"] else i + 1)
    return unicos[:TOPO]


def minha_posicao(ranking: list[dict]) -> dict | None:
    return next((x for x in ranking if x.get("eu")), None)


def texto_posicao(ranking: list[dict]) -> str:
    eu = minha_posicao(ranking)
    n = len(ranking)
    if not eu:
        return "Você ainda não aparece neste ranking."
    if eu["xp"] == 0:
        return f"Você está na liga de estudo com {n} pessoa{'s' if n != 1 else ''}. Estude hoje para pontuar nesta semana."
    return f"Você está em {eu['pos']}º lugar entre {n} nesta semana, com {eu['xp']} XP."
