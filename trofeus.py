"""Troféus, divisões e temporadas dos jogos online (Trade Battle e Ticker Battle) · regras puras, sem banco e sem rede.

Cada jogo tem os seus troféus. Só partida ONLINE vale troféus (contra o sistema é treino). A conta segue a ideia do Elo:
vencer quem tem mais troféus vale mais; perder para quem tem menos custa mais. Nunca fica abaixo de zero.
Temporada = mês do calendário (horário de Brasília). Na virada, quem passou do Ouro volta metade do caminho até ele (todo
mundo recomeça a disputa, sem perder tudo), e recebe uma vez o prêmio da MAIOR divisão alcançada na temporada que acabou.
Documento por conta: {"temp": "2026-11", "trade": {"t", "max"}, "ticker": {...}, "ids": [...], "premios": {temp: {...}}}
"""
from __future__ import annotations

JOGOS = ("trade", "ticker")
K = 40                         # tamanho máximo de um ganho ou perda numa partida entre iguais é K/2
MIN_GANHO = 8                  # vencer sempre dá pelo menos isso; perder tira pelo menos isso (quando há troféus)
IDS_MAX = 300

# (id, nome, troféus mínimos, cor, prêmio em TC no fim da temporada)
DIVISOES = (
    ("bronze", "Bronze", 0, "#E0803A", 10),
    ("prata", "Prata", 200, "#C0C7D4", 25),
    ("ouro", "Ouro", 500, "#F2B84B", 50),
    ("platina", "Platina", 1000, "#9FC3E6", 80),
    ("diamante", "Diamante", 2000, "#3D8BFF", 120),
    ("lenda", "Lenda", 3000, "#FFC93C", 200),
)
PISO_RESET = 500               # na virada da temporada, quem passou daqui volta metade do excedente


def divisao(t: int) -> dict:
    """A divisão de quem tem `t` troféus, com a próxima e quanto falta."""
    t = max(0, int(t or 0))
    i = max(k for k, d in enumerate(DIVISOES) if t >= d[2])
    d = DIVISOES[i]
    prox = DIVISOES[i + 1] if i + 1 < len(DIVISOES) else None
    pct = 1.0 if not prox else (t - d[2]) / (prox[2] - d[2])
    return {"id": d[0], "nome": d[1], "min": d[2], "cor": d[3], "premio": d[4], "nivel": i,
            "prox": ({"id": prox[0], "nome": prox[1], "min": prox[2]} if prox else None),
            "falta": (prox[2] - t) if prox else 0, "pct": round(max(0.0, min(1.0, pct)), 4)}


def tabela() -> list[dict]:
    return [{"id": i, "nome": n, "min": m, "cor": c, "premio": p} for i, n, m, c, p in DIVISOES]


def delta(meus: int, deles: float, placar: float) -> int:
    """Troféus ganhos (positivo) ou perdidos (negativo). `placar`: 1 venceu, 0.5 empatou, 0 perdeu (ou fração da posição)."""
    esperado = 1 / (1 + 10 ** ((float(deles) - float(meus)) / 400))
    d = K * (float(placar) - esperado)
    if placar > 0.5:
        d = max(d, MIN_GANHO)
    elif placar < 0.5:
        d = min(d, -MIN_GANHO)
    return int(round(d))


def placar_por_posicao(pos: int, n: int) -> float:
    """Partida com vários jogadores (Trade Battle): 1º = 1, último = 0, os do meio em proporção."""
    n = max(2, int(n))
    return max(0.0, min(1.0, (n - int(pos)) / (n - 1)))


def vazio(temp: str) -> dict:
    return {"temp": temp, "trade": {"t": 0, "max": 0}, "ticker": {"t": 0, "max": 0}, "ids": [], "premios": {}}


def sanear(doc: dict | None, temp: str) -> tuple[dict, dict | None]:
    """Documento válido para a temporada `temp`. Se ele era de uma temporada anterior, aplica a virada e devolve também o
    resumo dela ({temp, jogos: {jogo: {max, divisao}}, premio}) para o servidor pagar uma vez. Sem virada: (doc, None)."""
    d = dict(doc or {})
    if not d.get("temp"):
        return vazio(temp), None
    out = {"temp": d["temp"], "ids": [str(x) for x in (d.get("ids") or [])][-IDS_MAX:], "premios": dict(d.get("premios") or {})}
    for j in JOGOS:
        g = d.get(j) or {}
        out[j] = {"t": max(0, int(g.get("t") or 0)), "max": max(0, int(g.get("max") or 0))}
    if out["temp"] == temp:
        return out, None
    fim = {"temp": out["temp"], "jogos": {}}
    melhor = 0
    for j in JOGOS:
        dv = divisao(out[j]["max"])
        fim["jogos"][j] = {"max": out[j]["max"], "divisao": dv["nome"], "id": dv["id"]}
        melhor = max(melhor, dv["premio"]) if out[j]["max"] > 0 else melhor
        t = out[j]["t"]
        novo = PISO_RESET + (t - PISO_RESET) // 2 if t > PISO_RESET else t
        out[j] = {"t": novo, "max": novo}
    fim["premio"] = melhor
    out["premios"][fim["temp"]] = fim
    out["temp"] = temp
    return out, (fim if melhor > 0 else None)


def registrar(doc: dict, jogo: str, pid: str, meus_deles: float, placar: float) -> tuple[dict, int | None]:
    """Soma o resultado de UMA partida online (repetir o mesmo `pid` não soma). Devolve (doc, troféus ganhos/perdidos ou None)."""
    if jogo not in JOGOS:
        raise ValueError("jogo inválido")
    pid = f"{jogo}:{str(pid)[:40]}"
    if pid in doc["ids"]:
        return doc, None
    g = doc[jogo]
    d = delta(g["t"], meus_deles, placar)
    g["t"] = max(0, g["t"] + d)
    g["max"] = max(g["max"], g["t"])
    doc["ids"] = (doc["ids"] + [pid])[-IDS_MAX:]
    return doc, d
