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

`nota` (0 a 100) = média dos itens avaliados; None se nenhum desenho pôde ser avaliado. Em níveis e zonas cada item vale pelo quanto supera o ACASO
naquele gráfico (ver `taxa_acaso`): acertar onde o acaso também acerta quase sempre vale ~50 (neutro); errar onde o acaso quase sempre acerta vale muito
pouco; acertar onde o acaso raramente acerta vale muito. Assim desenhar às cegas rende ~50 em média, e só leitura de verdade passa disso.
"""
from __future__ import annotations

JANELA_REACAO = 5          # candles para o preço reagir depois de tocar a linha ou entrar na zona
JANELA_TENDENCIA = 20      # candles do replay usados para conferir uma linha de tendência
MIN_TENDENCIA = 0.7        # fração mínima de fechamentos do lado certo da linha para a tendência valer
DIST_PLENA = 2.0           # em ATR: a partir desta distância do preço de partida o acerto vale 100%; mais perto, vale proporcionalmente

ROTULO_NIVEL = {"suporte": "Suporte", "resistencia": "Resistência", "rompimento": "Rompimento", "alvo": "Alvo"}


def _fmt(p: float) -> str:
    return f"R$ {p:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def tolerancia(atr: float, ref: float) -> float:
    return max(0.25 * float(atr or 0), 0.002 * float(ref or 0), 0.01)


def distancia_plena(atr: float, ref: float) -> float:
    """Distância do preço de partida a partir da qual um acerto vale tudo. Mais perto, o acerto vale a fração dessa distância.

    Um desenho colado no preço acerta quase sempre (o preço já está lá), então o acerto dele não diz nada. Medido em 4000 mercados: a 1 ATR o alvo
    acertava 70% das vezes; a 2 ATR, 45%, abaixo de um cara-ou-coroa, que é onde acertar volta a ser previsão. Daí a distância cheia de 2 ATR.
    O piso (1,6% do preço) cobre o caso de ATR muito pequeno."""
    return max(DIST_PLENA * float(atr or 0), 0.016 * float(ref or 0), 0.02)


def peso_distancia(dist: float, plena: float) -> float:
    """Quanto vale o acerto de um desenho que está a `dist` do preço de partida: 0 em cima do preço, 1 a partir da distância plena."""
    return 0.0 if plena <= 0 else max(0.0, min(1.0, dist / plena))


FATORES_ACASO = (0.6, 0.8, 1.2, 1.4)     # distâncias (em fração da distância do desenho ao preço) onde se testa o que o acaso faria no MESMO gráfico


def taxa_acaso(avalia, d: float) -> float:
    """Chance de acerto de um desenho do mesmo tipo em outras distâncias do preço, no mesmo replay (usa o caminho real do preço: vale para qualquer
    mercado). `avalia(f)` devolve True/False/None para o desenho trazido para `f` × a distância original. Só contam os que o preço alcançou; se nenhum foi
    alcançado (ou o desenho está em cima do preço, d = 0), assume 50%."""
    if d <= 0:
        return 0.5
    oks = [r for r in (avalia(f) for f in FATORES_ACASO) if r is not None]
    return sum(1 for r in oks if r) / len(oks) if oks else 0.5


def valor_sobre_acaso(ok, acaso: float, peso: float) -> float | None:
    """0 a 1: 0,5 + peso × (acerto − acaso)/2. Sem peso (colado no preço) ou acertando só o que o acaso acerta, fica neutro (0,5)."""
    if ok is None:
        return None
    return max(0.0, min(1.0, 0.5 + peso * (float(bool(ok)) - acaso) / 2))


def _com_peso(texto: str, peso: float) -> str:
    return texto if peso >= 1 else f"{texto} Vale {peso:.0%} dos pontos por estar perto do preço de partida."


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
    `n_ini` = índice do 1º candle do replay (os índices dos desenhos usam o mesmo eixo); `ref` = preço no fim da análise.

    Pode-se desenhar em qualquer lugar. Em níveis e zonas o acerto é multiplicado pelo peso da distância (`peso_distancia`), que mede o caminho que o
    preço precisou percorrer até o desenho. Um acerto colado no preço vale quase nada, e como a nota é a MÉDIA dos desenhos avaliados, um desenho
    assim ainda puxa a nota para baixo em vez de ajudar. Linha de tendência fica fora do peso (ver abaixo)."""
    m = marcas or {}
    tol = tolerancia(atr, ref)
    plena = distancia_plena(atr, ref)
    itens = []
    for n in m.get("niveis") or []:
        papel = n.get("papel")
        if papel not in ("suporte", "resistencia", "rompimento", "alvo"):
            continue
        p = float(n["preco"])
        w = peso_distancia(abs(p - ref), plena)
        ok, txt = _nivel(papel, p, rep, ref, tol)
        d, lado = abs(p - ref), (1 if p >= ref else -1)
        acaso = taxa_acaso(lambda f: _nivel(papel, ref + lado * d * f, rep, ref, tol)[0], d)
        itens.append({"tipo": "nivel", "papel": papel, "preco": n["preco"], "ok": ok, "peso": round(w, 3), "acaso": round(acaso, 3),
                      "valor": valor_sobre_acaso(ok, acaso, w), "texto": txt if ok is None else _com_peso(txt, w)})
    for t in m.get("tendencias") or []:
        v, txt = _tendencia(t, n_ini, rep, tol)
        # Sem peso de distância: uma linha de tendência nasce encostada no preço (passa pelos fundos ou topos recentes), então o peso a zeraria.
        # E o acerto dela não depende do preço CHEGAR a algum lugar, que é o que o peso mede.
        itens.append({"tipo": "tendencia", **{k: t[k] for k in ("i1", "p1", "i2", "p2")}, "ok": None if v is None else v >= MIN_TENDENCIA,
                      "peso": 1.0, "valor": v, "texto": txt})
    for z in m.get("zonas") or []:
        d = 0.0 if z["p1"] <= ref <= z["p2"] else min(abs(z["p1"] - ref), abs(z["p2"] - ref))     # a borda mais próxima: o caminho até entrar nela
        w = peso_distancia(d, plena)
        ok, txt = _zona(z, rep, tol)
        lado = 1 if z["p2"] > ref and z["p1"] >= ref else -1
        acaso = taxa_acaso(lambda f: _zona({**z, "p1": z["p1"] + lado * d * (f - 1), "p2": z["p2"] + lado * d * (f - 1)}, rep, tol)[0], d)
        itens.append({"tipo": "zona", **{k: z[k] for k in ("i1", "i2", "p1", "p2", "reacao")}, "ok": ok, "peso": round(w, 3), "acaso": round(acaso, 3),
                      "valor": valor_sobre_acaso(ok, acaso, w), "texto": txt if ok is None else _com_peso(txt, w)})
    contam = [x["valor"] for x in itens if x["valor"] is not None]
    nota = round(100 * sum(contam) / len(contam), 1) if contam else None
    return {"itens": itens, "nota": nota, "avaliados": len(contam), "acertos": sum(1 for x in itens if x["ok"]), "tol": round(tol, 4)}
