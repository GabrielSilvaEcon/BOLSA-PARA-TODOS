"""Regras da Home (módulo PURO: sem Streamlit, sem rede, sem banco). Só transforma dados que o app já tem em estruturas simples.

Reutilizável pela futura API Python: a tela (Streamlit hoje, Flutter depois) só desenha o que sai daqui.
Nada é inventado: sem dado, o resultado diz `vazio` e a tela mostra um estado vazio explicando o motivo.

 · ranking_resumo: três primeiros do ranking REAL já publicado (o mesmo da Wallet Game) + a posição da própria pessoa, esteja onde estiver.
 · desempenho: melhores e piores ativos da carteira do jogo e o que mais contribuiu no total. Um critério só para os três cartões:
   resultado ACUMULADO desde a compra (preço atual contra preço médio). Não mistura com variação do dia.
"""
from __future__ import annotations

import ativos_jogo as A

CRITERIO = "Resultado acumulado desde a compra"
MEDALHAS = {1: "ouro", 2: "prata", 3: "bronze"}


def _f(v, padrao: float = 0.0) -> float:
    try:
        x = float(v)
        return x if x == x else padrao
    except (TypeError, ValueError):
        return padrao


def sigla(ativo) -> str:
    """Código curto para mostrar: 'PETR4' fica 'PETR4', 'US:VOO' vira 'VOO', 'CRIPTO:BTC' vira 'BTC'. Outros ids usam o fim do rótulo."""
    a = str(ativo or "")
    if ":" in a and a.split(":")[0] in ("US", "CRIPTO"):
        return a.split(":", 1)[1]
    rot = A.rotulo(a)
    return rot.split(" · ")[-1] if " · " in rot else rot


def nome_curto(ativo) -> str:
    rot = A.rotulo(ativo)
    return rot.split(" · ")[0] if " · " in rot else rot


# ------------------------------------------------------------------ ranking
def retorno_atual(est: dict | None) -> float | None:
    """Retorno da carteira AGORA (patrimônio com os últimos preços, sem contar bônus, sobre o capital inicial). Não é o critério do ranking
    (que usa o fechamento do dia): serve para a pessoa ver o que já mudou desde o último fechamento."""
    if not isinstance(est, dict) or est.get("v") != 1:
        return None
    try:
        import competicao as C
        cap = C.capital_de(est)
        return (C.patrimonio(est) - C.aportes(est)) / cap - 1 if cap > 0 else None
    except Exception:
        return None


def data_br(iso) -> str | None:
    """'2026-11-12' vira '12/11'. Qualquer outra coisa vira None."""
    t = str(iso or "")[:10]
    return f"{t[8:10]}/{t[5:7]}" if len(t) == 10 and t[4] == "-" and t[7] == "-" else None


def ranking_resumo(geral: list | None, total: int | None = None, minha_pos: int | None = None, meu_apelido: str | None = None,
                   meu_ret: float | None = None, topo: int = 3, dia=None, meu_ao_vivo: float | None = None, parcial: str | None = None) -> dict:
    """geral = lista pública do ranking geral [{'pos','apelido','ret',...}] (já ordenada). minha_pos/total vêm da própria carteira (valem
    mesmo se a pessoa estiver fora da lista publicada). Devolve {'top': [...], 'eu': {...}|None, 'total': n, 'vazio': bool}."""
    linhas = [x for x in (geral or []) if isinstance(x, dict) and x.get("apelido") is not None]
    top = [{"pos": int(x.get("pos") or i), "apelido": str(x["apelido"]), "ret": x.get("ret")} for i, x in enumerate(linhas[:max(0, topo)], 1)]
    eu = None
    ap = (meu_apelido or "").strip()
    if ap or minha_pos:
        achado = next((x for x in linhas if ap and str(x.get("apelido", "")).lower() == ap.lower()), None)
        pos = minha_pos or (int(achado.get("pos") or 0) if achado else 0) or None
        ret = meu_ret if meu_ret is not None else (achado.get("ret") if achado else None)
        if pos:
            eu = {"pos": int(pos), "apelido": ap or "Você", "ret": ret, "no_topo": int(pos) <= len(top)}
    n = int(total) if total else (len(linhas) or None)
    return {"top": top, "eu": eu, "total": n, "vazio": not top, "dia": data_br(dia), "ao_vivo": meu_ao_vivo, "parcial": parcial}


# ------------------------------------------------------------------ desempenho
def realizado_por_ativo(ext: list | None) -> dict:
    """Resultado já realizado em vendas, por ativo (do extrato do jogo). Bônus e proventos ficam de fora: não são resultado de preço."""
    out: dict = {}
    for x in ext or []:
        if isinstance(x, dict) and x.get("tipo") == "venda" and x.get("t"):
            out[x["t"]] = out.get(x["t"], 0.0) + _f(x.get("r"))
    return out


def _linha(p: dict) -> dict:
    return {"id": p["id"], "sigla": sigla(p["id"]), "nome": nome_curto(p["id"]), "classe": p.get("classe"),
            "pct": _f(p.get("pct")) * 100.0, "resultado": _f(p.get("lucro_nao_realizado"))}


def desempenho(posicoes: list | None, realizado: dict | None = None, n: int = 3, minimo: float = 0.0001) -> dict:
    """posicoes = linhas de carteira_unica.resumo(est)['posicoes']. Devolve:
    altas   = até n ativos com maior retorno % (só os positivos);  quedas = até n com menor retorno % (só os negativos);
    mais_rentavel = quem mais somou no total (resultado em aberto + vendas já realizadas dele), se for positivo.
    Ativo com variação ~0 não entra em altas nem quedas. `vazio` = não há nenhuma posição com custo."""
    pos = [p for p in (posicoes or []) if isinstance(p, dict) and p.get("id") and _f(p.get("custo")) > 0]
    realizado = realizado or {}
    linhas = [_linha(p) for p in pos]
    altas = sorted((x for x in linhas if x["pct"] > minimo), key=lambda x: (-x["pct"], x["sigla"]))[:n]
    quedas = sorted((x for x in linhas if x["pct"] < -minimo), key=lambda x: (x["pct"], x["sigla"]))[:n]
    contrib = {x["id"]: x["resultado"] + _f(realizado.get(x["id"])) for x in linhas}
    for tk, r in realizado.items():                          # ativo já vendido por inteiro também conta no total
        contrib.setdefault(tk, _f(r))
    mais = None
    if contrib:
        tk, val = max(contrib.items(), key=lambda kv: (kv[1], kv[0]))
        if val > 0:
            base = next((x for x in linhas if x["id"] == tk), None)
            mais = {"id": tk, "sigla": sigla(tk), "nome": nome_curto(tk), "classe": A.classe(tk),
                    "resultado": round(val, 2), "pct": base["pct"] if base else None, "aberto": base is not None}
    return {"altas": altas, "quedas": quedas, "mais_rentavel": mais, "vazio": not linhas, "criterio": CRITERIO}
