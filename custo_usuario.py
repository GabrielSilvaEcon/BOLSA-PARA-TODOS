"""Etapa 14 · Custo por usuário, por plano e por recurso (estimativa).

Soma, dos últimos N dias, o uso de cada recurso diário por conta (documentos `uso|dia|hash`) e multiplica pelo custo por uso que o administrador
informa (padrão: IA = preço por 1.000 pedidos da fonte "ia" ÷ 1.000; o resto R$ 0). Projeta para 30 dias e compara com a receita líquida de
uma assinatura de cada plano (precificacao). Só enxerga uso de recursos limitados por plano: o custo de leitura de dados (cache) é compartilhado
e aparece em Custos, não aqui.
"""
from __future__ import annotations

from datetime import date, timedelta

import custos
import planos
import precificacao


def custo_por_uso(cfg: dict | None = None) -> dict:
    """R$ por uso de cada recurso diário: o informado pelo administrador, ou (IA) o preço por 1.000 pedidos ÷ 1.000."""
    cfg = cfg or custos.config()
    ia = custos._num((cfg.get("preco_por_mil") or {}).get("ia")) / 1000
    out = {}
    for r, v in planos.RECURSOS.items():
        if v["tipo"] != "dia":
            continue
        inf = custos._num((cfg.get("custo_recurso") or {}).get(r))
        out[r] = inf if inf > 0 else (ia if r.startswith("ia_") else 0.0)
    return out


def coletar(dias: int = 7, plano_de=None) -> dict:
    import banco
    plano_de = plano_de or planos.plano_de
    unit = custo_por_uso()
    hoje = date.fromisoformat(planos.hoje())
    contas: dict[str, dict] = {}
    for i in range(dias):
        dia = (hoje - timedelta(days=i)).isoformat()
        for l in banco._selecionar("config_sistema", {"id": ("comeca", f"uso|{dia}|")}, ["id", "dados"], limite=2000):
            if not str(l["id"]).startswith(f"uso|{dia}|"):
                continue
            d = banco._de_js(l["dados"]) or {}
            chave = str(l["id"]).split("|")[-1]
            c = contas.setdefault(chave, {"email": d.get("_e") or "(conta sem e-mail registrado)", "usos": {}, "negadas": 0, "dias": set()})
            if d.get("_e"):
                c["email"] = d["_e"]
            for r in unit:
                n = int(d.get(r, 0))
                if n:
                    c["usos"][r] = c["usos"].get(r, 0) + n
                    c["dias"].add(dia)
            c["negadas"] += int(d.get("_neg", 0))
    usuarios = []
    for c in contas.values():
        custo = round(sum(n * unit[r] for r, n in c["usos"].items()), 4)
        plano = plano_de(c["email"]) if "@" in c["email"] else "gratuito"
        usuarios.append({"email": c["email"], "plano": plano if plano in planos.PLANOS else "gratuito", "usos": c["usos"], "custo": custo,
                         "negadas": c["negadas"], "dias_ativos": len(c["dias"]), "total_usos": sum(c["usos"].values())})
    usuarios = [u for u in usuarios if u["total_usos"] or u["negadas"]]
    usuarios.sort(key=lambda u: (-u["custo"], -u["total_usos"]))
    por_recurso = {r: {"usos": sum(u["usos"].get(r, 0) for u in usuarios), "custo": round(sum(u["usos"].get(r, 0) for u in usuarios) * unit[r], 4),
                       "unit": unit[r]} for r in unit}
    por_plano = {}
    cfg_p = precificacao.config()
    for p in planos.PLANOS:
        us = [u for u in usuarios if u["plano"] == p]
        custo = sum(u["custo"] for u in us)
        mensal_por_usuario = round(custo * 30 / max(1, dias) / len(us), 4) if us else 0.0
        receita = precificacao.liquido_por_assinatura(cfg_p["preco"].get(p, 0.0), cfg_p) if p in precificacao.PAGOS else 0.0
        por_plano[p] = {"usuarios": len(us), "usos": sum(u["total_usos"] for u in us), "custo": round(custo, 4), "custo_mensal_por_usuario": mensal_por_usuario,
                        "receita_liquida": receita, "margem_por_usuario": round(receita - mensal_por_usuario, 2) if p in precificacao.PAGOS else None}
    return {"dias": dias, "usuarios": usuarios, "por_recurso": por_recurso, "por_plano": por_plano,
            "custo_total": round(sum(u["custo"] for u in usuarios), 4), "unit": unit}
