"""Competição · Etapa 3, parte 2 — temporadas mensais e trimestrais e selos. Lógica pura (sem Streamlit, sem rede e sem banco), testável isoladamente.

Temporada = janela de calendário (mês ou trimestre). O retorno é medido só dentro da janela: patrimônio do último pregão da janela dividido pelo
patrimônio do último fechamento antes dela (quem entrou no meio parte do capital inicial). Como a carteira não recebe aportes, a razão é o retorno puro.
Temporada encerrada é congelada: o resultado depende só do histórico até o último dia da janela, então recalcular dá sempre o mesmo número.

Selos são honrarias simbólicas (sem prêmio em dinheiro): ouro, prata e bronze (pódio), Top 10 e "equilíbrio" (melhor retorno ajustado ao risco).
Para evitar "ouro" ganho sozinho, o pódio exige um mínimo de participantes qualificados na temporada.
Educacional: carteira virtual, sem dinheiro real, sem recomendação de investimento.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone

import competicao as C

TIPOS = ("mensal", "trimestral")
MIN_DIAS_TEMPORADA = {"mensal": 5, "trimestral": 10}    # pregões dentro da janela para entrar no ranking da temporada
MIN_PARTICIPANTES_SELO = 5                              # abaixo disso não há pódio nem selo de equilíbrio
MIN_PARTICIPANTES_TOP10 = 11                            # "Top 10" só faz sentido se alguém ficou de fora
TOPO = 100
CFG_TEMPORADA = "comp_temp|"                            # ranking congelado da temporada encerrada (só o fechamento grava) — prefixo + id

SELOS = {
    "ouro": "Ouro · 1º lugar",
    "prata": "Prata · 2º lugar",
    "bronze": "Bronze · 3º lugar",
    "top10": "Top 10",
    "equilibrio": "Equilíbrio · melhor retorno ajustado ao risco",
}

_ID_MES = re.compile(r"(\d{4})-(0[1-9]|1[0-2])")
_ID_TRI = re.compile(r"(\d{4})-T([1-4])")


# ------------------------------------------------------------------ janelas
def id_temporada(tipo: str, dia: date) -> str:
    if tipo == "mensal":
        return f"{dia.year:04d}-{dia.month:02d}"
    if tipo == "trimestral":
        return f"{dia.year:04d}-T{(dia.month - 1) // 3 + 1}"
    raise ValueError(f"tipo inválido: {tipo}")


def tipo_de(tid: str) -> str:
    if _ID_MES.fullmatch(tid or ""):
        return "mensal"
    if _ID_TRI.fullmatch(tid or ""):
        return "trimestral"
    raise ValueError(f"id de temporada inválido: {tid}")


def limites(tid: str) -> tuple[date, date]:
    """(primeiro dia, último dia) da temporada, inclusive."""
    if tipo_de(tid) == "mensal":
        a, m = (int(x) for x in tid.split("-"))
        ini = date(a, m, 1)
        fim = (date(a + (m == 12), m % 12 + 1, 1)) - timedelta(days=1)
    else:
        a, t = int(tid[:4]), int(tid[-1])
        ini = date(a, 3 * t - 2, 1)
        fim = date(a + (t == 4), (3 * t) % 12 + 1, 1) - timedelta(days=1)
    return ini, fim


def encerrada(tid: str, hoje: date) -> bool:
    return hoje > limites(tid)[1]


def anterior(tid: str) -> str:
    """Temporada imediatamente anterior, do mesmo tipo."""
    return id_temporada(tipo_de(tid), limites(tid)[0] - timedelta(days=1))


# ------------------------------------------------------------------ desempenho e ranking
def desempenho(estado: dict, tid: str) -> dict | None:
    """Retorno, queda máxima e risco do participante dentro da temporada. None se não houve pregão na janela."""
    ini, fim = (d.isoformat() for d in limites(tid))
    h = (estado or {}).get("hist") or []
    dentro = [x for x in h if ini <= x["d"] <= fim]
    if not dentro:
        return None
    antes = [x["p"] for x in h if x["d"] < ini]
    base = antes[-1] if antes else C.CAPITAL_INICIAL
    if base <= 0:
        return None
    pats = [base] + [x["p"] for x in dentro]
    pico, pior = base, 0.0
    for p in pats:
        pico = max(pico, p)
        pior = min(pior, p / pico - 1)
    return {"ret": pats[-1] / base - 1, "dd": pior, "dias": len(dentro), "risco": C.metricas_serie(pats)}


def montar_temporada(participantes: list[dict], tid: str, hoje: date, topo: int = TOPO) -> dict:
    """participantes: [{'apelido', 'email', 'estado'}]. Devolve o ranking da temporada (público: só apelido e %) e, à parte,
    as posições por e-mail (`posicoes`, `posicoes_risco`), que o job usa para avisos e selos e NÃO publica."""
    tipo = tipo_de(tid)
    ini, fim = limites(tid)
    minimo = MIN_DIAS_TEMPORADA[tipo]
    linhas = []
    for p in participantes:
        d = desempenho(p["estado"], tid)
        if d and d["dias"] >= minimo:
            linhas.append({"apelido": p["apelido"], "email": p["email"], **d})
    linhas.sort(key=lambda x: (-round(x["ret"], 8), -x["dias"], x["apelido"].lower()))
    risco = [x for x in linhas if x["risco"]]
    risco.sort(key=lambda x: (-round(x["risco"]["sharpe"], 8), -x["dias"], x["apelido"].lower()))
    return {
        "id": tid, "tipo": tipo, "inicio": ini.isoformat(), "fim": fim.isoformat(), "encerrada": hoje > fim, "gerado": hoje.isoformat(),
        "n": len(linhas), "risco_n": len(risco), "min_dias": minimo,
        "lista": [{"pos": i, "apelido": x["apelido"], "ret": round(x["ret"], 6), "dd": round(x["dd"], 6), "dias": x["dias"]}
                  for i, x in enumerate(linhas[:topo], 1)],
        "risco": [{"pos": i, "apelido": x["apelido"], "sh": round(x["risco"]["sharpe"], 3), "vol": round(x["risco"]["vol"], 4),
                   "ret": round(x["ret"], 6), "dd": round(x["dd"], 6), "dias": x["dias"]} for i, x in enumerate(risco[:topo], 1)],
        "posicoes": {x["email"]: i for i, x in enumerate(linhas, 1)},
        "posicoes_risco": {x["email"]: i for i, x in enumerate(risco, 1)},
    }


def publico(res: dict) -> dict:
    """Versão publicável: sem e-mails."""
    return {k: v for k, v in res.items() if k not in ("posicoes", "posicoes_risco")}


# ------------------------------------------------------------------ selos
def _selo(tipo_selo: str, tid: str, pos: int) -> dict:
    return {"id": f"{tipo_selo}|{tid}", "selo": tipo_selo, "temp": tid, "tipo": tipo_de(tid), "pos": pos}


def conceder_selos(res: dict) -> dict[str, list[dict]]:
    """Selos de uma temporada ENCERRADA, por e-mail. Temporada em andamento não concede nada (o resultado ainda muda)."""
    if not res.get("encerrada"):
        return {}
    tid, n = res["id"], res["n"]
    out: dict[str, list[dict]] = {}
    for email, pos in res["posicoes"].items():
        if n >= MIN_PARTICIPANTES_SELO and pos <= 3:
            out.setdefault(email, []).append(_selo(("ouro", "prata", "bronze")[pos - 1], tid, pos))
        elif n >= MIN_PARTICIPANTES_TOP10 and pos <= 10:
            out.setdefault(email, []).append(_selo("top10", tid, pos))
    if res["risco_n"] >= MIN_PARTICIPANTES_SELO:
        for email, pos in res["posicoes_risco"].items():
            if pos == 1:
                out.setdefault(email, []).append(_selo("equilibrio", tid, 1))
    return out


def juntar_selos(atuais: list[dict], novos: list[dict]) -> list[dict]:
    """Acrescenta selos novos sem duplicar (o id é selo|temporada, então reprocessar o mesmo fechamento é seguro)."""
    ja = {s["id"] for s in atuais or []}
    return list(atuais or []) + [s for s in novos if s["id"] not in ja]


# ------------------------------------------------------------------ plano do fechamento diário
def planejar(participantes: list[dict], dia: date, ja_encerrada=lambda tid: False) -> dict:
    """O que o fechamento diário de `dia` (o último pregão) deve fazer com as temporadas:
     · publicar a temporada ATUAL de cada tipo (muda todo dia);
     · congelar a temporada que acabou de ENCERRAR (a anterior de cada tipo), uma única vez: se `ja_encerrada(id)` diz que o documento final já
       existe, nada é recalculado e nenhum selo é concedido de novo;
     · conceder os selos dessa temporada encerrada.
    Devolve {'publicar': {id: documento sem e-mails}, 'selos': {email: [selo]}, 'posicoes': {email: {id: {'pos', 'n'}}}, 'encerradas': [id]}."""
    out: dict = {"publicar": {}, "selos": {}, "posicoes": {}, "encerradas": []}
    atuais = [id_temporada(t, dia) for t in TIPOS]
    for tid in atuais:
        res = montar_temporada(participantes, tid, dia)
        out["publicar"][tid] = publico(res)
        for email, pos in res["posicoes"].items():
            out["posicoes"].setdefault(email, {})[tid] = {"pos": pos, "n": res["n"]}
    for tid in (anterior(a) for a in atuais):
        try:
            final = bool(ja_encerrada(tid))
        except Exception:
            final = False                                   # sem conseguir conferir, recalcula (os selos são idempotentes)
        if final:
            continue
        res = montar_temporada(participantes, tid, dia)
        out["publicar"][tid] = publico(res)
        out["encerradas"].append(tid)
        for email, lista in conceder_selos(res).items():
            out["selos"].setdefault(email, []).extend(lista)
    return out


# ------------------------------------------------------------------ apresentação e avisos (sem Streamlit)
ICONES = {"ouro": "🥇", "prata": "🥈", "bronze": "🥉", "top10": "🔟", "equilibrio": "⚖️"}
_MESES = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")


def rotulo(tid: str) -> str:
    """'2026-11' -> 'Novembro de 2026'; '2026-T4' -> '4º trimestre de 2026'."""
    ini, _ = limites(tid)
    if tipo_de(tid) == "mensal":
        return f"{_MESES[ini.month - 1].capitalize()} de {ini.year}"
    return f"{(ini.month - 1) // 3 + 1}º trimestre de {ini.year}"


def recentes(tipo: str, hoje: date, quantas: int) -> list[str]:
    """A temporada atual e as anteriores do mesmo tipo (da mais nova para a mais antiga)."""
    tid = id_temporada(tipo, hoje)
    out = [tid]
    while len(out) < quantas:
        tid = anterior(tid)
        out.append(tid)
    return out


def descricao_selo(s: dict) -> str | None:
    """'Ouro · 1º lugar · Outubro de 2026'. None se o selo for desconhecido ou estiver malformado (a tela ignora)."""
    try:
        return f"{SELOS[s['selo']]} · {rotulo(s['temp'])}"
    except Exception:
        return None


def avisos_de_selos(selos: list[dict] | None, quando: datetime, preferencias: dict | None = None) -> list[dict]:
    """Notificações de selos recém-conquistados. O `dedup` é o id do selo, então reprocessar o fechamento não avisa duas vezes.
    Usa a mesma preferência dos avisos do ranking geral (`global`): quem desligou esses avisos também não recebe os de selo."""
    if not (preferencias or {}).get("global", True):
        return []
    out = []
    for s in selos or []:
        desc = descricao_selo(s)
        if not desc:
            continue
        nome = SELOS[s["selo"]].split(" · ")[0]
        texto = (f"Seu retorno ajustado ao risco foi o melhor da temporada de {rotulo(s['temp']).lower()}." if s["selo"] == "equilibrio"
                 else f"Você terminou em {s['pos']}º lugar na temporada de {rotulo(s['temp']).lower()}.")
        q = quando.astimezone(timezone.utc) if quando.tzinfo else quando
        out.append({"dedup": f"comp|selo|{s['id']}", "categoria": "carteira", "ativo": "", "importancia": "baixa" if s["selo"] == "top10" else "media",
                    "titulo": f"Você ganhou o selo {nome}", "texto": texto + " Veja seus selos na aba Temporadas.",
                    "origem": "competicao", "regra_id": "competicao", "grupo": "competicao", "pagina": "competicao",
                    "quando": q.strftime("%Y-%m-%dT%H:%M:%S.000Z"), "dados": {"competicao": True}})
    return out
