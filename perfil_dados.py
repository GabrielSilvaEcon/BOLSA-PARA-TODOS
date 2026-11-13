"""Meu Perfil: regras de dados (módulo puro, sem Streamlit, sem gravar nada).

Tudo vem da carteira virtual real (`estado` do competicao) e das conquistas do Wallet Game. Sem dado = None/lista vazia
(a tela mostra estado vazio em vez de número inventado). T$ é moeda fictícia.
"""
from __future__ import annotations

from datetime import date, datetime

ORDEM_CLASSES = ("acao", "fii", "etf", "cripto", "fundo", "rf")
CORES = {"acao": "#2BA7FF", "fii": "#8B6CFF", "etf": "#D23FC8", "cripto": "#F2B84B", "fundo": "#2BA7C9", "rf": "#3DDC97"}
NOMES = {"acao": "Ações", "fii": "FIIs", "etf": "ETFs", "cripto": "Cripto", "fundo": "Fundos", "rf": "Renda Fixa"}


def trades(estado: dict | None) -> int:
    """Compras + vendas executadas (bônus e proventos não contam)."""
    return sum(1 for x in (estado or {}).get("ext") or [] if x.get("tipo") in ("compra", "venda"))


def alocacao(estado: dict | None, classe_de) -> list[dict]:
    """Posições por classe, em % do valor investido (sem o caixa). [{chave, nome, cor, pct, valor}] do maior ao menor."""
    tot: dict[str, float] = {}
    for tk, p in ((estado or {}).get("pos") or {}).items():
        px = ((estado or {}).get("ult") or {}).get(tk) or p.get("pm") or 0.0
        v = float(p.get("q") or 0) * float(px)
        c = classe_de(tk)
        if c and v > 0:
            tot[c] = tot.get(c, 0.0) + v
    soma = sum(tot.values())
    if soma <= 0:
        return []
    itens = [{"chave": c, "nome": NOMES.get(c, c), "cor": CORES.get(c, "#8B6CFF"), "pct": v / soma * 100, "valor": v} for c, v in tot.items()]
    return sorted(itens, key=lambda i: -i["pct"])


def pcts_inteiros(itens: list[dict]) -> list[int]:
    """Arredonda para inteiros somando 100 (maior resto)."""
    if not itens:
        return []
    base = [int(i["pct"]) for i in itens]
    falta = 100 - sum(base)
    ordem = sorted(range(len(itens)), key=lambda k: -(itens[k]["pct"] - base[k]))
    for k in ordem[:max(falta, 0)]:
        base[k] += 1
    return base


def _liq(h: dict) -> float:
    return float(h["p"]) - float(h.get("a") or 0.0)


def evolucao(estado: dict | None, max_pontos: int = 8) -> list[dict]:
    """Série do patrimônio (sem bônus) por fechamento: [{d, v}], reduzida a no máximo `max_pontos` pontos."""
    h = [{"d": x["d"], "v": _liq(x)} for x in (estado or {}).get("hist") or [] if "d" in x and "p" in x]
    if len(h) <= max_pontos:
        return h
    passo = (len(h) - 1) / (max_pontos - 1)
    idx = sorted({round(i * passo) for i in range(max_pontos)})
    return [h[i] for i in idx]


def variacao(estado: dict | None, hoje: date, dias: int = 30) -> float | None:
    """Variação % do patrimônio (sem bônus) nos últimos `dias`; None sem histórico suficiente (precisa de pelo menos 2 fechamentos)."""
    h = [x for x in (estado or {}).get("hist") or [] if "d" in x and "p" in x]
    if len(h) < 2:
        return None
    corte = date.fromordinal(hoje.toordinal() - dias).isoformat()
    antes = [x for x in h if x["d"] <= corte]
    ini = _liq(antes[-1]) if antes else _liq(h[0])
    if ini <= 0:
        return None
    return (_liq(h[-1]) / ini - 1) * 100


def _dt(txt: str) -> datetime | None:
    try:
        return datetime.fromisoformat(str(txt)[:19])
    except (TypeError, ValueError):
        return None


def ha(quando: str, agora: datetime) -> str:
    """'hoje', 'há 2 dias', 'há 3 semanas'… a partir de uma data ISO (dia)."""
    d = _dt(quando)
    if not d:
        return ""
    n = (agora.date() - d.date()).days
    if n <= 0:
        return "hoje"
    if n == 1:
        return "há 1 dia"
    if n < 14:
        return f"há {n} dias"
    if n < 60:
        return f"há {n // 7} semanas"
    return f"há {n // 30} meses"


def atividades(estado: dict | None, conquistas: list[dict] | None, agora: datetime, limite: int = 3) -> list[dict]:
    """Últimos eventos reais: trades da carteira virtual e conquistas desbloqueadas, do mais recente ao mais antigo.
    [{tipo: 'trade'|'conquista', titulo, detalhe, quando, quando_txt}]"""
    ev = []
    for x in (estado or {}).get("ext") or []:
        if x.get("tipo") in ("compra", "venda") and x.get("d"):
            ev.append({"tipo": "trade", "titulo": "Compra realizada" if x["tipo"] == "compra" else "Venda realizada",
                       "detalhe": str(x.get("t") or ""), "quando": str(x["d"])[:10]})
    for c in conquistas or []:
        q = c.get("desbloqueada_em")
        if q:
            ev.append({"tipo": "conquista", "titulo": "Conquista desbloqueada", "detalhe": str(c.get("nome") or ""), "quando": str(q)[:10]})
    ev.sort(key=lambda e: e["quando"], reverse=True)
    out = ev[:limite]
    for e in out:
        e["quando_txt"] = ha(e["quando"], agora)
    return out


def dica_trades(n: int) -> str:
    return "Faça sua primeira compra!" if n == 0 else "Explore mais estratégias!"
