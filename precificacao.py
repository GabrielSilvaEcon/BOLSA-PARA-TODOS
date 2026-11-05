"""Etapa 8 · Preços, receita e margem dos planos (somente cálculo e simulação; NÃO cobra ninguém).

O administrador define: preço mensal de cada plano pago, taxa do meio de pagamento (% + valor fixo por cobrança; começa em 0 até
ele escolher o provedor) e a margem alvo. O app cruza isso com o número real de contas por plano e com os custos do mês
(custos.py) e mostra receita bruta, taxas, receita líquida, custo, lucro, margem, ponto de equilíbrio e o preço mínimo para a margem alvo.
Tudo é ESTIMATIVA: pagamentos reais só entram quando houver cobrança (Etapa 9).
"""
from __future__ import annotations

import math

CH = "precos_cfg"
PAGOS = ("plus", "premium")


def _padrao() -> dict:
    return {"preco": {"plus": 0.0, "premium": 0.0}, "taxa_pct": 0.0, "taxa_fixa": 0.0, "margem_alvo": 30.0}


def _num(v, padrao=0.0) -> float:
    try:
        x = float(str(v).replace(",", "."))
        return x if x == x and x != float("inf") and x >= 0 else padrao
    except (TypeError, ValueError):
        return padrao


def config() -> dict:
    cfg = _padrao()
    try:
        import banco
        lido = banco.cfg_ler(CH) or {}
        cfg["preco"].update({k: _num(v) for k, v in (lido.get("preco") or {}).items() if k in PAGOS})
        for k in ("taxa_pct", "taxa_fixa", "margem_alvo"):
            if k in lido:
                cfg[k] = _num(lido[k], cfg[k])
    except Exception:
        pass
    return cfg


def salvar(cfg: dict) -> dict:
    limpo = {"preco": {p: round(_num((cfg.get("preco") or {}).get(p)), 2) for p in PAGOS},
             "taxa_pct": min(30.0, round(_num(cfg.get("taxa_pct")), 2)), "taxa_fixa": min(10.0, round(_num(cfg.get("taxa_fixa")), 2)),
             "margem_alvo": min(90.0, round(_num(cfg.get("margem_alvo"), 30.0), 1))}
    import banco
    banco.cfg_gravar(CH, limpo)
    return limpo


def liquido_por_assinatura(preco: float, cfg: dict) -> float:
    """O que sobra de uma cobrança depois da taxa do meio de pagamento."""
    if preco <= 0:
        return 0.0
    return round(preco * (1 - cfg["taxa_pct"] / 100) - cfg["taxa_fixa"], 2)


def calcular(assinantes: dict, custo_mensal: float, cfg: dict | None = None) -> dict:
    """assinantes: {'plus': n, 'premium': n}. custo_mensal: custos do mês cheio (fixos + variáveis projetados)."""
    cfg = cfg or config()
    custo = round(_num(custo_mensal), 2)
    linhas, bruta, taxas = {}, 0.0, 0.0
    for p in PAGOS:
        n, preco = max(0, int(assinantes.get(p, 0))), cfg["preco"].get(p, 0.0)
        b = round(n * preco, 2)
        liq_u = liquido_por_assinatura(preco, cfg)
        t = round(b - n * liq_u, 2) if preco > 0 else 0.0
        linhas[p] = {"assinantes": n, "preco": preco, "bruta": b, "taxas": t, "liquida_unit": liq_u}
        bruta += b
        taxas += t
    bruta, taxas = round(bruta, 2), round(taxas, 2)
    liquida = round(bruta - taxas, 2)
    lucro = round(liquida - custo, 2)
    margem = round(100 * lucro / liquida, 1) if liquida > 0 else None
    precos_ok = [p for p in PAGOS if linhas[p]["liquida_unit"] > 0]
    if not precos_ok:
        sit = "sem_preco"
    elif liquida <= 0:
        sit = "sem_assinantes"
    elif lucro < 0:
        sit = "erro"
    elif margem is not None and margem < cfg["margem_alvo"]:
        sit = "aviso"
    else:
        sit = "ok"
    return {"linhas": linhas, "bruta": bruta, "taxas": taxas, "liquida": liquida, "custo": custo, "lucro": lucro, "margem": margem,
            "margem_alvo": cfg["margem_alvo"], "situacao": sit, "equilibrio": equilibrio(custo, cfg)}


def equilibrio(custo: float, cfg: dict) -> dict:
    """Quantos assinantes de UM plano pago (sozinho) cobrem o custo do mês. None = plano sem preço (ou preço que não cobre a taxa)."""
    out = {}
    for p in PAGOS:
        liq = liquido_por_assinatura(cfg["preco"].get(p, 0.0), cfg)
        out[p] = None if liq <= 0 else (0 if custo <= 0 else math.ceil(custo / liq))
    return out


def preco_minimo(custo: float, assinantes: int, cfg: dict | None = None) -> float | None:
    """Menor preço mensal que, com `assinantes` pagantes, dá a margem alvo: p = (custo/(N·(1−m)) + fixa) / (1 − pct)."""
    cfg = cfg or config()
    m, pct = cfg["margem_alvo"] / 100, cfg["taxa_pct"] / 100
    if assinantes <= 0 or m >= 1 or pct >= 1:
        return None
    return round((_num(custo) / (assinantes * (1 - m)) + cfg["taxa_fixa"]) / (1 - pct), 2)
