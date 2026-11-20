"""Avaliação dos desenhos da estratégia (Trade Battle, partida corrida): no fim, cada desenho é conferido contra o gráfico REAL
que andou depois da análise. Módulo puro e determinístico (sem banco, sem rede): só recebe candles e desenhos.

Tolerância: `tol` = 25% do ATR14 do histórico (o "ruído" típico de um candle daquele ativo), com piso de 0,2% do preço.
Cada desenho vira um item com `ok` = True (acertou), False (errou) ou None (o preço nem chegou lá: não conta, nem a favor nem contra).

  suporte      o preço desceu até a linha (mínima ≤ P + tol) e voltou: fechou acima de P + tol antes de fechar abaixo de P − 2·tol.
  resistência  o espelho: subiu até a linha e voltou para baixo antes de romper.
  rompimento   o preço fechou além da linha (do lado oposto de onde estava no fim da análise), com folga de tol.
  alvo         o preço tocou o alvo (máxima ou mínima, conforme o lado).
  tendência    a linha projetada no futuro: nos primeiros candles do replay, o preço ficou do lado certo dela em ≥ 70% dos fechamentos
               (linha de alta = suporte inclinado: fechamento ≥ linha − tol; linha de baixa = o contrário). Nota parcial = fração.
  zona ↑/↓     o preço entrou na área e reagiu na direção apostada: fechou além da borda certa antes de atravessar a borda oposta.
  notas        não são avaliadas (são só anotações).

`nota` (0 a 100) = média dos itens avaliados (acerto = 1, erro = 0, tendência = fração); None se nenhum desenho pôde ser avaliado.
"""
from __future__ import annotations

JANELA_REACAO = 5          # candles para o preço reagir depois de tocar a linha ou entrar na zona
JANELA_TENDENCIA = 20      # candles do replay usados para conferir uma linha de tendência
MIN_TENDENCIA = 0.7        # fração mínima de fechamentos do lado certo da linha para a tendência valer


def _fmt(p: float) -> str:
    return f"R$ {p:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tolerancia(atr: float, ref: float) -> float:
    return max(0.25 * float(atr or 0), 0.002 * float(ref or 0), 0.01)


def _reacao(rep: list[dict], toque, volta, rompe) -> bool | None:
    """Procura o 1º candle que toca; depois (incluindo ele) espera `volta` antes de `rompe`, em até JANELA_REACAO candles."""
    for i, c in enumerate(rep):
        if not toque(c):
            continue
        for k in rep[i:i + JANELA_REACAO + 1]:
            if rompe(k):
                return False
            if volta(k):
                return True
        return False
    return None


def _nivel(papel: str, p: float, rep: list[dict], ref: float, tol: float) -> tuple[bool | None, str]:
    if papel == "suporte":
        ok = _reacao(rep, lambda c: c["l"] <= p + tol, lambda c: c["c"] > p + tol, lambda c: c["c"] < p - 2 * tol)
        txt = {True: f"Suporte em {_fmt(p)} segurou: o preço tocou e voltou a subir.",
               False: f"Suporte em {_fmt(p)} não segurou: o preço passou para baixo.",
               None: f"Suporte em {_fmt(p)}: o preço não chegou até lá."}[ok]
    elif papel == "resistencia":
        ok = _reacao(rep, lambda c: c["h"] >= p - tol, lambda c: c["c"] < p - tol, lambda c: c["c"] > p + 2 * tol)
        txt = {True: f"Resistência em {_fmt(p)} segurou: o preço tocou e voltou a cair.",
               False: f"Resistência em {_fmt(p)} não segurou: o preço passou para cima.",
               None: f"Resistência em {_fmt(p)}: o preço não chegou até lá."}[ok]
    elif papel == "rompimento":
        acima = p >= ref
        ok = any((c["c"] > p + tol) if acima else (c["c"] < p - tol) for c in rep)
        txt = f"Rompimento em {_fmt(p)}: " + ("o preço rompeu, como você previu." if ok else "o preço não rompeu.")
    else:                                                   # alvo
        acima = p >= ref
        ok = any((c["h"] >= p) if acima else (c["l"] <= p) for c in rep)
        txt = f"Alvo em {_fmt(p)}: " + ("alcançado!" if ok else "não foi alcançado.")
    return ok, txt


def _tendencia(t: dict, n_ini: int, rep: list[dict], tol: float) -> tuple[float | None, str]:
    i1, p1, i2, p2 = t["i1"], t["p1"], t["i2"], t["p2"]
    if i2 == i1 or not rep:
        return None, "Tendência: não deu para avaliar."
    k = (p2 - p1) / (i2 - i1)
    alta = k >= 0
    janela = rep[:JANELA_TENDENCIA]
    certos = 0
    for j, c in enumerate(janela):
        linha = p1 + k * (n_ini + j - i1)
        certos += (c["c"] >= linha - tol) if alta else (c["c"] <= linha + tol)
    frac = certos / len(janela)
    nome = "Tendência de alta" if alta else "Tendência de baixa"
    if frac >= MIN_TENDENCIA:
        return frac, f"{nome} respeitada em {frac:.0%} dos candles."
    return frac * 0.5, f"{nome} não foi respeitada (só {frac:.0%} dos candles do lado certo)."


def _zona(z: dict, rep: list[dict], tol: float) -> tuple[bool | None, str]:
    p1, p2, alta = z["p1"], z["p2"], z["reacao"] == "alta"
    entra = lambda c: c["l"] <= p2 and c["h"] >= p1                      # noqa: E731
    if alta:
        ok = _reacao(rep, entra, lambda c: c["c"] > p2 + tol, lambda c: c["c"] < p1 - tol)
    else:
        ok = _reacao(rep, entra, lambda c: c["c"] < p1 - tol, lambda c: c["c"] > p2 + tol)
    faixa = f"{_fmt(p1)}–{_fmt(p2)}"
    sentido = "para cima" if alta else "para baixo"
    txt = {True: f"Zona {faixa}: o preço entrou e reagiu {sentido}, como você previu.",
           False: f"Zona {faixa}: o preço entrou mas não reagiu {sentido}.",
           None: f"Zona {faixa}: o preço não chegou até a zona."}[ok]
    return ok, txt


def avaliar_desenhos(marcas: dict | None, n_ini: int, rep: list[dict], ref: float, atr: float) -> dict:
    """Confere os desenhos (`marcas` validadas por trader_battle.validar_marcas) contra os candles do replay `rep`.
    `n_ini` = índice do 1º candle do replay (os índices dos desenhos usam o mesmo eixo); `ref` = preço no fim da análise."""
    m = marcas or {}
    tol = tolerancia(atr, ref)
    itens = []
    for n in m.get("niveis") or []:
        papel = n.get("papel")
        if papel not in ("suporte", "resistencia", "rompimento", "alvo"):
            continue
        ok, txt = _nivel(papel, float(n["preco"]), rep, ref, tol)
        itens.append({"tipo": "nivel", "papel": papel, "preco": n["preco"], "ok": ok, "valor": None if ok is None else float(ok), "texto": txt})
    for t in m.get("tendencias") or []:
        v, txt = _tendencia(t, n_ini, rep, tol)
        itens.append({"tipo": "tendencia", **{k: t[k] for k in ("i1", "p1", "i2", "p2")}, "ok": None if v is None else v >= MIN_TENDENCIA,
                      "valor": v, "texto": txt})
    for z in m.get("zonas") or []:
        ok, txt = _zona(z, rep, tol)
        itens.append({"tipo": "zona", **{k: z[k] for k in ("i1", "i2", "p1", "p2", "reacao")}, "ok": ok, "valor": None if ok is None else float(ok), "texto": txt})
    contam = [x["valor"] for x in itens if x["valor"] is not None]
    nota = round(100 * sum(contam) / len(contam), 1) if contam else None
    return {"itens": itens, "nota": nota, "avaliados": len(contam), "acertos": sum(1 for x in itens if x["ok"]), "tol": round(tol, 4)}
