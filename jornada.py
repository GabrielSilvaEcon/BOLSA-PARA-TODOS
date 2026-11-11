"""Jornada de educação financeira (estilo Duolingo) — lógica pura, sem Streamlit.

Princípios (herdados de educacao.py):
- XP só por ESTUDAR (lição, revisão). Nunca por operar ou assumir risco.
- Nada é bloqueado: não há vidas que travam nem lições trancadas. Erro volta ao fim da fila e vai para "revisar".
- O estado é um dicionário pequeno em progresso["jornada"], gravado junto com edu_progresso no perfil da conta.
- Datas em horário de Brasília (UTC-3, sem horário de verão desde 2019).
"""
from __future__ import annotations

import random
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
    return {"xp": 0, "xp_dia": {}, "licoes": {}, "erros": [], "meta_dia": META_DIA_PADRAO, "som": True, "vistos": None, "escudos": []}


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
    base["som"] = j["som"] if isinstance(j.get("som"), bool) else True      # só um booleano de verdade vale; qualquer outra coisa volta ao padrão (ligado)
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
    vv = j.get("vistos")
    if isinstance(vv, dict):
        base["vistos"] = {k: sorted({str(x) for x in (vv.get(k) or []) if isinstance(x, str)})[-400:] for k in ("emb", "passe")}
    esc = []
    for e in (j.get("escudos") or [])[-10:] if isinstance(j.get("escudos"), list) else []:
        try:
            ini, fim = date.fromisoformat(str(e["ini"])), date.fromisoformat(str(e["fim"]))
        except (TypeError, ValueError, KeyError):
            continue
        if ini <= fim <= ini + timedelta(days=ESCUDO_DIAS) and not any(x["ini"] == ini.isoformat() for x in esc):
            esc.append({"ini": ini.isoformat(), "fim": fim.isoformat()})
    base["escudos"] = esc
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


# ------------------------------------------------------------------ apoio à tela (puro)
def _embaralhar(itens: list, semente: str) -> list:
    """Embaralha de forma estável (mesma ordem a cada rerun) e nunca devolve a ordem original."""
    base = list(itens)
    r = list(base)
    rng = random.Random(semente)
    for _ in range(10):
        rng.shuffle(r)
        if r != base:
            return r
    return base[1:] + base[:1]


def embaralhar_itens(ex: dict) -> list:
    """Itens de um exercício 'ordenar' na ordem em que aparecem para a pessoa montar."""
    return _embaralhar(ex["itens"], ex["id"])


def embaralhar_pares(ex: dict) -> list:
    """Lado direito de um exercício 'pares', embaralhado."""
    return _embaralhar([b for _, b in ex["pares"]], ex["id"])


def resposta_certa_texto(ex: dict) -> str:
    t = ex["tipo"]
    if t in ("escolha", "completar"):
        return str(ex["opcoes"][ex["correta"]])
    if t == "vf":
        return "Verdadeiro" if ex["correta"] else "Falso"
    if t == "ordenar":
        return " → ".join(ex["itens"])
    return "; ".join(f"{a} = {b}" for a, b in ex["pares"])


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
    xp_antes = j["xp"]
    j["xp"] += xp
    d = hoje(agora).isoformat()
    antes_hoje = j["xp_dia"].get(d, 0)
    j["xp_dia"][d] = antes_hoje + xp
    for eid in s["ids"]:                      # errou agora → entra na fila de revisão; acertou de primeira → sai dela
        if eid in s["erros_ids"]:
            if eid not in j["erros"]:
                j["erros"].append(eid)
        elif eid in j["erros"]:
            j["erros"].remove(eid)
    p = {**p, "jornada": normalizar_jornada(j)}
    meta_ok = meta_atingida(p, agora)
    return p, {"ok": True, "xp": xp, "perfeita": perfeita, "acertos_primeira": total - len(s["erros_ids"]), "total": total,
               "revisao": s["revisao"], "ofensiva": ofensiva(p, agora), "meta_atingida": meta_ok,
               "meta_nova": meta_ok and antes_hoje < j["meta_dia"],          # a meta foi batida NESTA sessão (e não antes, no mesmo dia)
               "primeiro_do_dia": antes_hoje == 0, "licao": s["licao"],
               "xp_antes": xp_antes, "xp_depois": j["xp"]}


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


ESCUDO_DIAS = 7            # um Escudo de ofensiva (Loja) vale 7 dias a partir da compra e perdoa UM dia sem estudo nesse período


def registrar_escudo(p: dict, agora: datetime | None = None) -> dict:
    """Registra um Escudo de ofensiva comprado agora (janela de 7 dias). Comprar de novo no mesmo dia não duplica."""
    j = _jor(p)
    d = hoje(agora)
    ini = d.isoformat()
    if not any(e["ini"] == ini for e in j["escudos"]):
        j["escudos"] = (j["escudos"] + [{"ini": ini, "fim": (d + timedelta(days=ESCUDO_DIAS)).isoformat()}])[-10:]
    return {**p, "jornada": j}


def escudos_vigentes(p: dict, agora: datetime | None = None) -> int:
    """Quantos Escudos ainda estão na janela de validade e não foram gastos para salvar a sequência."""
    d = hoje(agora)
    return sum(1 for e in _escudos_livres(p, agora) if date.fromisoformat(e["fim"]) >= d)


def _escudos_livres(p: dict, agora: datetime | None = None) -> list[dict]:
    return [e for e in _jor(p)["escudos"] if e["fim"] >= hoje(agora).isoformat() and not _escudo_usado(p, e, agora)]


def _escudo_usado(p: dict, e: dict, agora: datetime | None = None) -> bool:
    _n, usados = _ofensiva_e_usados(p, agora)
    return e["ini"] in usados


def _ofensiva_e_usados(p: dict, agora: datetime | None = None) -> tuple[int, set]:
    j = _jor(p)
    dias = {k for k, v in j["xp_dia"].items() if v > 0}
    hj = hoje(agora)
    esc = [dict(e, usado=False) for e in j["escudos"]]
    d = hj
    if d.isoformat() not in dias:
        d -= timedelta(days=1)
    n = 0
    while True:
        if d.isoformat() in dias:
            n += 1
            d -= timedelta(days=1)
            continue
        ant = (d - timedelta(days=1)).isoformat()
        e = next((x for x in esc if not x["usado"] and x["ini"] <= d.isoformat() <= x["fim"] and d < hj), None) if ant in dias else None
        if not e:
            break
        e["usado"] = True                    # o dia sem estudo é perdoado: não soma, mas não quebra a sequência
        d -= timedelta(days=1)
    return n, {x["ini"] for x in esc if x["usado"]}


def ofensiva(p: dict, agora: datetime | None = None) -> int:
    """Dias seguidos com estudo. Conta a partir de hoje; se hoje ainda não estudou, a sequência de ontem segue viva.
    Um Escudo de ofensiva comprado na Loja perdoa um dia sem estudo dentro dos 7 dias da compra (o dia perdoado não conta como estudado)."""
    return _ofensiva_e_usados(p, agora)[0]


def melhor_ofensiva(p: dict) -> int:
    """Maior sequência de dias seguidos com estudo já registrada (não zera quando a ofensiva atual se perde). Base das conquistas de ofensiva."""
    dias = sorted(date.fromisoformat(k) for k, v in _jor(p)["xp_dia"].items() if v > 0)
    melhor = atual = 0
    anterior = None
    for d in dias:
        atual = atual + 1 if anterior is not None and (d - anterior).days == 1 else 1
        melhor = max(melhor, atual)
        anterior = d
    return melhor


def teve_licao_perfeita(p: dict) -> bool:
    return any(r.get("melhor", 0) >= 1.0 for r in _jor(p)["licoes"].values())


# ------------------------------------------------------------------ preferência de som
def som_ligado(p: dict) -> bool:
    return _jor(p)["som"]


def definir_som(p: dict, ligado: bool) -> dict:
    j = _jor(p)
    j["som"] = bool(ligado)
    return {**p, "jornada": j}


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
            "ofensiva": ofensiva(p, agora), "erros": len(j["erros"]), "licoes_feitas": len(j["licoes"]), "som": j["som"]}


# ------------------------------------------------------------------ estudo com dados reais no fim da unidade (etapa 6b)
# Cada unidade concluída pode abrir um estudo guiado com um ativo REAL (dados com fonte e data, ou "indisponível"; nada é estimado).
# Só liga indicadores que existem em edu_conteudo.INDICADORES; `risco` mostra retorno, volatilidade e queda máxima do último ano.
# Unidades sem dado real útil (renda fixa e impostos) ficam de fora: o app não tem fonte de preço para elas nesta tela.
ESTUDO_REAL = {
    "u_inicio": dict(titulo="Risco e retorno de um ativo de verdade", indicadores=(), risco=True,
                     dica="Veja quanto um ativo oscilou no último ano e compare com o retorno do período."),
    "u_onde": dict(titulo="Conheça um ativo por dentro", indicadores=("Dividend yield",), risco=True,
                   dica="Ação, FII ou ETF: veja os proventos dos últimos 12 meses e o risco observado."),
    "u_carteira": dict(titulo="Compare o risco de dois ativos", indicadores=(), risco=True,
                       dica="Escolha dois ativos e veja como oscilaram na mesma janela. Diversificar é combinar oscilações diferentes."),
    "u_analise": dict(titulo="Leia os indicadores de uma empresa real", indicadores=("P/L", "P/VP", "ROE", "Margem líquida"), risco=False,
                      dica="Digite o código de uma ação e veja o que cada número significa, em palavras."),
    "u_riscos": dict(titulo="Volatilidade e queda máxima na prática", indicadores=(), risco=True,
                     dica="Veja a pior queda que o ativo teve no último ano e quanto ele oscila."),
}


def estudo_real(unidade_id: str) -> dict | None:
    """Roteiro de estudo com dado real para a unidade (ou None se a unidade não tem)."""
    return ESTUDO_REAL.get(unidade_id)


def estudo_real_liberado(p: dict, unidade_id: str) -> bool:
    """Só aparece no fim da unidade: todas as lições feitas. (Não tranca nada: a tela só oferece o estudo, que é opcional.)"""
    if unidade_id not in ESTUDO_REAL:
        return False
    u = J.UNIDADE_POR_ID.get(unidade_id)
    j = _jor(p)
    return bool(u) and all(l in j["licoes"] for l in u["licoes"])


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
    for uid, e in ESTUDO_REAL.items():
        if uid not in J.UNIDADE_POR_ID:
            erros.append(f"estudo real: unidade {uid} não existe")
        for sig in e["indicadores"]:
            if sig not in E.INDICADORES:
                erros.append(f"estudo real {uid}: indicador {sig} não existe")
        if not e["indicadores"] and not e["risco"]:
            erros.append(f"estudo real {uid}: sem indicador nem risco")
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
