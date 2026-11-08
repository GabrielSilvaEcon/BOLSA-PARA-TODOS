"""Jornada de educação financeira (estilo Duolingo) — lógica pura, sem Streamlit.

Princípios (herdados de educacao.py):
- XP só por ESTUDAR (lição, revisão). Nunca por operar ou assumir risco.
- Nada é bloqueado: não há vidas que travam nem lições trancadas. Erro volta ao fim da fila e vai para "revisar".
- O estado é um dicionário pequeno em progresso["jornada"], gravado junto com edu_progresso no perfil da conta.
- Datas em horário de Brasília (UTC-3, sem horário de verão desde 2019).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import jornada_conteudo as J

XP_LICAO, XP_BONUS_PERFEITA, XP_REVISAO = 10, 5, 5
META_DIA_PADRAO = 20
LIMITE_ERROS, LIMITE_DIAS = 50, 400
TAM_REVISAO = 5
BRT = timezone(timedelta(hours=-3))


# ------------------------------------------------------------------ datas
def _agora(agora: datetime | None = None) -> datetime:
    return (agora or datetime.now(timezone.utc)).astimezone(BRT)


def hoje(agora: datetime | None = None) -> date:
    return _agora(agora).date()


# ------------------------------------------------------------------ estado
def nova_jornada() -> dict:
    return {"xp": 0, "xp_dia": {}, "licoes": {}, "erros": [], "meta_dia": META_DIA_PADRAO}


def _int(v, minimo: int, maximo: int, padrao: int) -> int:
    try:
        return min(maximo, max(minimo, int(v)))
    except (TypeError, ValueError):
        return padrao


def normalizar_jornada(j) -> dict:
    """Aceita lixo/ausente e devolve sempre um estado válido (descarta ids que não existem mais)."""
    base = nova_jornada()
    if not isinstance(j, dict):
        return base
    base["xp"] = _int(j.get("xp"), 0, 10**9, 0)
    base["meta_dia"] = _int(j.get("meta_dia"), 5, 200, META_DIA_PADRAO)
    dias = {}
    for k, v in (j.get("xp_dia") or {}).items():
        try:
            date.fromisoformat(str(k))
        except ValueError:
            continue
        dias[str(k)] = _int(v, 0, 10**6, 0)
    base["xp_dia"] = dict(sorted(dias.items())[-LIMITE_DIAS:])
    for lid, r in (j.get("licoes") or {}).items():
        if lid in J.LICAO_POR_ID and isinstance(r, dict):
            try:
                melhor = min(1.0, max(0.0, float(r.get("melhor", 0))))
            except (TypeError, ValueError):
                melhor = 0.0
            base["licoes"][lid] = {"n": _int(r.get("n"), 1, 10**6, 1), "melhor": melhor, "ultima": str(r.get("ultima", ""))}
    vistos: list[str] = []
    for eid in j.get("erros") or []:
        if eid in J.EX_POR_ID and eid not in vistos:
            vistos.append(eid)
    base["erros"] = vistos[-LIMITE_ERROS:]
    return base


def _jor(p: dict) -> dict:
    return normalizar_jornada((p or {}).get("jornada"))


# ------------------------------------------------------------------ correção
def corrigir(ex: dict, resposta) -> bool:
    """True se a resposta está certa. Resposta de formato errado conta como erro, nunca gera exceção.
    escolha/completar: índice · vf: bool · ordenar: lista na ordem · pares: dict {esquerda: direita}."""
    try:
        t = ex["tipo"]
        if t in ("escolha", "completar"):
            return isinstance(resposta, int) and not isinstance(resposta, bool) and resposta == ex["correta"]
        if t == "vf":
            return isinstance(resposta, bool) and resposta is ex["correta"]
        if t == "ordenar":
            return list(resposta) == list(ex["itens"])
        if t == "pares":
            return dict(resposta) == {a: b for a, b in ex["pares"]}
    except (TypeError, ValueError, KeyError):
        return False
    return False


# ------------------------------------------------------------------ sessão (uma lição em andamento)
def iniciar_sessao(licao_id: str) -> dict | None:
    l = J.LICAO_POR_ID.get(licao_id)
    if not l:
        return None
    ids = [e["id"] for e in l["exercicios"]]
    return {"licao": licao_id, "fila": ids, "total": len(ids), "feitos": 0, "erros_ids": [], "revisao": False, "ids": list(ids)}


def iniciar_revisao(p: dict, n: int = TAM_REVISAO) -> dict | None:
    """Sessão com os exercícios errados antes. None se não houver nada para revisar."""
    ids = _jor(p)["erros"][:n]
    if not ids:
        return None
    return {"licao": None, "fila": list(ids), "total": len(ids), "feitos": 0, "erros_ids": [], "revisao": True, "ids": list(ids)}


def exercicio_atual(s: dict) -> dict | None:
    return J.EX_POR_ID[s["fila"][0]] if s and s.get("fila") else None


def terminada(s: dict) -> bool:
    return not s.get("fila")


def progresso_sessao(s: dict) -> float:
    return (s["feitos"] / s["total"]) if s.get("total") else 0.0


def responder(s: dict, resposta) -> tuple[bool, dict]:
    """Corrige o exercício atual. Acerto avança; erro vai para o fim da fila (sem perder vida) e fica marcado para revisão."""
    ex = exercicio_atual(s)
    if ex is None:
        return False, s
    s = {**s, "fila": list(s["fila"]), "erros_ids": list(s["erros_ids"])}
    ok = corrigir(ex, resposta)
    eid = s["fila"].pop(0)
    if ok:
        s["feitos"] += 1
    else:
        s["fila"].append(eid)
        if eid not in s["erros_ids"]:
            s["erros_ids"].append(eid)
    return ok, s


def concluir_sessao(p: dict, s: dict, agora: datetime | None = None) -> tuple[dict, dict]:
    """Aplica o resultado de uma sessão terminada ao progresso. Devolve (progresso, resultado). Sessão não terminada não muda nada."""
    if not terminada(s):
        return p, {"ok": False}
    j = _jor(p)
    total = s["total"]
    perfeita = not s["erros_ids"]
    if s["revisao"]:
        xp = XP_REVISAO
    else:
        xp = XP_LICAO + (XP_BONUS_PERFEITA if perfeita else 0)
        r = j["licoes"].setdefault(s["licao"], {"n": 0, "melhor": 0.0, "ultima": ""})
        r["n"] += 1
        r["melhor"] = max(r["melhor"], 1 - len(s["erros_ids"]) / total)
        r["ultima"] = _agora(agora).isoformat(timespec="seconds")
    j["xp"] += xp
    d = hoje(agora).isoformat()
    j["xp_dia"][d] = j["xp_dia"].get(d, 0) + xp
    for eid in s["ids"]:                      # errou agora → entra na fila de revisão; acertou de primeira → sai dela
        if eid in s["erros_ids"]:
            if eid not in j["erros"]:
                j["erros"].append(eid)
        elif eid in j["erros"]:
            j["erros"].remove(eid)
    p = {**p, "jornada": normalizar_jornada(j)}
    return p, {"ok": True, "xp": xp, "perfeita": perfeita, "acertos_primeira": total - len(s["erros_ids"]), "total": total,
               "revisao": s["revisao"], "ofensiva": ofensiva(p, agora), "meta_atingida": meta_atingida(p, agora)}


# ------------------------------------------------------------------ XP, meta e ofensiva
def xp_total(p: dict) -> int:
    return _jor(p)["xp"]


def xp_hoje(p: dict, agora: datetime | None = None) -> int:
    return _jor(p)["xp_dia"].get(hoje(agora).isoformat(), 0)


def meta_atingida(p: dict, agora: datetime | None = None) -> bool:
    return xp_hoje(p, agora) >= _jor(p)["meta_dia"]


def definir_meta(p: dict, xp_por_dia: int) -> dict:
    j = _jor(p)
    j["meta_dia"] = _int(xp_por_dia, 5, 200, META_DIA_PADRAO)
    return {**p, "jornada": j}


def ofensiva(p: dict, agora: datetime | None = None) -> int:
    """Dias seguidos com estudo. Conta a partir de hoje; se hoje ainda não estudou, a sequência de ontem segue viva."""
    dias = {k for k, v in _jor(p)["xp_dia"].items() if v > 0}
    d = hoje(agora)
    if d.isoformat() not in dias:
        d -= timedelta(days=1)
    n = 0
    while d.isoformat() in dias:
        n += 1
        d -= timedelta(days=1)
    return n


# ------------------------------------------------------------------ mapa da trilha
def mapa(p: dict) -> list[dict]:
    """Unidades com o estado de cada lição: concluida | proxima (a primeira não feita) | livre. Nada fica trancado."""
    j = _jor(p)
    achou_proxima = False
    out = []
    for u in J.UNIDADES:
        ls = []
        for lid in u["licoes"]:
            l = J.LICAO_POR_ID[lid]
            feita = lid in j["licoes"]
            estado = "concluida" if feita else ("livre" if achou_proxima else "proxima")
            achou_proxima = achou_proxima or not feita
            ls.append({"id": lid, "titulo": l["titulo"], "icone": l["icone"], "svg": l.get("icone_svg", "estrela"), "estado": estado, "aula": l.get("aula"),
                       "melhor": j["licoes"].get(lid, {}).get("melhor", 0.0), "exercicios": len(l["exercicios"])})
        feitas = sum(1 for x in ls if x["estado"] == "concluida")
        out.append({**{k: u[k] for k in ("id", "titulo", "icone", "cor", "descricao")}, "svg": u.get("icone_svg", "estrela"), "licoes": ls, "feitas": feitas, "total": len(ls),
                    "completa": feitas == len(ls)})
    return out


def erros_para_revisar(p: dict) -> int:
    return len(_jor(p)["erros"])


def resumo(p: dict, agora: datetime | None = None) -> dict:
    j = _jor(p)
    return {"xp": j["xp"], "xp_hoje": xp_hoje(p, agora), "meta_dia": j["meta_dia"], "meta_atingida": meta_atingida(p, agora),
            "ofensiva": ofensiva(p, agora), "erros": len(j["erros"]), "licoes_feitas": len(j["licoes"])}


# ------------------------------------------------------------------ validação do conteúdo
def validar_conteudo() -> list[str]:
    """Lista de problemas encontrados nos dados (vazia = tudo certo). Usada nos testes ao adicionar conteúdo novo."""
    import edu_conteudo as E
    erros: list[str] = []
    for u in J.UNIDADES:
        for lid in u["licoes"]:
            if lid not in J.LICAO_POR_ID:
                erros.append(f"{u['id']}: lição {lid} não existe")
    import jornada_icones as IC
    for u in J.UNIDADES:
        if not IC.existe(u.get("icone_svg", "")):
            erros.append(f"{u['id']}: icone_svg inexistente")
    for l in J.LICOES:
        if not IC.existe(l.get("icone_svg", "")):
            erros.append(f"{l['id']}: icone_svg inexistente")
        if l["unidade"] not in J.UNIDADE_POR_ID:
            erros.append(f"{l['id']}: unidade inválida")
        if l.get("aula") and l["aula"] not in E.POR_ID:
            erros.append(f"{l['id']}: aula {l['aula']} não existe em edu_conteudo")
        if not 3 <= len(l["exercicios"]) <= 8:
            erros.append(f"{l['id']}: use de 3 a 8 exercícios")
        for e in l["exercicios"]:
            t = e.get("tipo")
            if t not in J.TIPOS:
                erros.append(f"{e['id']}: tipo inválido")
            elif not e.get("pergunta") or not e.get("explicacao"):
                erros.append(f"{e['id']}: falta pergunta ou explicação")
            elif t in ("escolha", "completar") and not (isinstance(e.get("correta"), int) and 0 <= e["correta"] < len(e.get("opcoes", []))):
                erros.append(f"{e['id']}: índice da resposta correta inválido")
            elif t == "completar" and "___" not in e["pergunta"]:
                erros.append(f"{e['id']}: falta '___' na frase")
            elif t == "vf" and not isinstance(e.get("correta"), bool):
                erros.append(f"{e['id']}: vf precisa de True/False")
            elif t == "ordenar" and len(set(e.get("itens", []))) < 3:
                erros.append(f"{e['id']}: ordenar precisa de 3+ itens distintos")
            elif t == "pares" and len(e.get("pares", [])) < 3:
                erros.append(f"{e['id']}: pares precisa de 3+ pares")
    return erros
