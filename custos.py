"""Etapa 7 · Custos e orçamento (somente o que o administrador informa; o app não vê faturas).

Hoje todas as fontes de dados são gratuitas, então o custo variável é R$ 0. Este módulo existe para o dia em que alguma fonte
passar a ser paga (ou houver custo fixo de hospedagem, domínio etc.):
 · custos fixos mensais: lista de {nome, valor em R$} digitada pelo administrador;
 · preço por 1.000 pedidos de cada fonte (0 = gratuita): o custo variável é pedidos do mês ÷ 1.000 × preço;
 · orçamento mensal: com ele, o painel mostra % usado e a PROJEÇÃO até o fim do mês (ritmo médio dos dias já passados);
 · avisos ao administrador quando a projeção passa de 80% do orçamento e quando o orçamento é ultrapassado.
Limite: é uma ESTIMATIVA a partir da contagem de pedidos do próprio app (que pode perder poucos pedidos e conta pedidos, não créditos).
"""
from __future__ import annotations

import calendar
from datetime import date

CH = "custos_cfg"
MAX_FIXOS = 20


def _padrao() -> dict:
    return {"orcamento_mensal": 0.0, "fixos": [], "preco_por_mil": {}, "custo_recurso": {}}


def config() -> dict:
    cfg = _padrao()
    try:
        import banco
        lido = banco.cfg_ler(CH) or {}
        for k in cfg:
            if k in lido:
                cfg[k] = lido[k]
    except Exception:
        pass
    return cfg


def _num(v, padrao=0.0) -> float:
    try:
        x = float(str(v).replace(",", "."))
        return x if x == x and x >= 0 else padrao
    except (TypeError, ValueError):
        return padrao


def salvar(cfg: dict) -> dict:
    import consumo
    antigo = config()
    limpo = {"orcamento_mensal": round(_num(cfg.get("orcamento_mensal")), 2), "fixos": [], "preco_por_mil": {},
             "custo_recurso": dict(cfg["custo_recurso"]) if "custo_recurso" in cfg else dict(antigo.get("custo_recurso") or {})}
    import planos
    limpo["custo_recurso"] = {r: round(_num(v), 4) for r, v in limpo["custo_recurso"].items()
                              if r in planos.RECURSOS and planos.RECURSOS[r]["tipo"] == "dia" and _num(v) > 0}
    for f in (cfg.get("fixos") or [])[:MAX_FIXOS]:
        nome = str((f or {}).get("nome") or "").strip()[:60]
        valor = round(_num((f or {}).get("valor")), 2)
        if nome and valor > 0:
            limpo["fixos"].append({"nome": nome, "valor": valor})
    for pid, v in (cfg.get("preco_por_mil") or {}).items():
        if pid in consumo.PROVEDORES and _num(v) > 0:
            limpo["preco_por_mil"][pid] = round(_num(v), 4)
    import banco
    banco.cfg_gravar(CH, limpo)
    return limpo


def calcular(usos_mes: dict, hoje: date, cfg: dict | None = None) -> dict:
    """Custos do mês até hoje, projeção até o fim do mês e situação frente ao orçamento."""
    cfg = cfg or config()
    precos = cfg.get("preco_por_mil") or {}
    var = {pid: round(int(usos_mes.get(pid, 0)) / 1000 * _num(p), 2) for pid, p in precos.items() if _num(p) > 0}
    fixo = round(sum(_num(f.get("valor")) for f in cfg.get("fixos") or []), 2)
    var_total = round(sum(var.values()), 2)
    total = round(fixo + var_total, 2)
    dias_mes = calendar.monthrange(hoje.year, hoje.month)[1]
    proj_var = round(var_total * dias_mes / max(1, hoje.day), 2)
    projecao = round(fixo + proj_var, 2)
    orc = _num(cfg.get("orcamento_mensal"))
    if not orc:
        sit = "sem_orcamento"
    elif total > orc or projecao > orc:
        sit = "erro"
    elif projecao >= 0.8 * orc:
        sit = "aviso"
    else:
        sit = "ok"
    return {"fixo": fixo, "variavel_por_fonte": var, "variavel": var_total, "total": total, "projecao": projecao, "orcamento": orc,
            "pct_usado": round(100 * total / orc, 1) if orc else None, "pct_projetado": round(100 * projecao / orc, 1) if orc else None,
            "situacao": sit, "fontes_pagas": sorted(precos_pagos(precos)), "pedidos_mes": sum(int(v) for v in usos_mes.values())}


def precos_pagos(precos: dict) -> list[str]:
    return [p for p, v in precos.items() if _num(v) > 0]


def alertas(calc: dict) -> list[dict]:
    """Avisos para o administrador (um por situação): projeção ≥ 80% do orçamento ou orçamento ultrapassado."""
    if calc["situacao"] == "erro":
        return [{"nivel": "erro", "titulo": "Custos acima do orçamento do mês" if calc["total"] > calc["orcamento"] else "Custos devem passar do orçamento do mês",
                 "texto": f"Gasto estimado {brl(calc['total'])}, projeção {brl(calc['projecao'])}, orçamento {brl(calc['orcamento'])}. Veja Administração > Custos."}]
    if calc["situacao"] == "aviso":
        return [{"nivel": "aviso", "titulo": "Custos perto do orçamento do mês",
                 "texto": f"Projeção {brl(calc['projecao'])} de {brl(calc['orcamento'])} ({calc['pct_projetado']:.0f}%). Veja Administração > Custos."}]
    return []


def brl(v: float) -> str:
    s = f"{float(v):,.2f}"
    return "R$ " + s.replace(",", "X").replace(".", ",").replace("X", ".")


def parse_fixos(txt: str) -> list[dict]:
    """Uma linha por custo: 'Nome = 25,90' (ou 'Nome: 25,90'). Linhas inválidas são ignoradas."""
    import re
    out = []
    for linha in str(txt or "").splitlines():
        m = re.match(r"^\s*(.+?)\s*[=:]\s*(?:R\$\s*)?([\d.,]+)\s*$", linha)
        if m:
            v = m.group(2)
            v = v.replace(".", "").replace(",", ".") if "," in v else v
            if _num(v) > 0:
                out.append({"nome": m.group(1)[:60], "valor": _num(v)})
    return out[:MAX_FIXOS]


def fixos_txt(fixos: list[dict]) -> str:
    return "\n".join(f"{f['nome']} = {f['valor']:.2f}".replace(".", ",") for f in fixos or [])
