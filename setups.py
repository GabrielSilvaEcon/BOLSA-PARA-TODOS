"""Setups de trading colecionáveis do Trade Game: catálogo, detecção, coleção e sorteio nos baús (módulo PURO: sem rede, sem banco).

Cada setup mora numa pasta própria, `app/assets/setups/<id>/`, com um `setup.json` e as artes dele:

    setup.json   id, nome, raridade, resumo, caracteristicas[], indicadores[], regra{compra, venda}, cores{principal, brilho},
                 assets{carta, ativacao, moldura, icone, efeitos[]}      (nomes de arquivo DENTRO da pasta; null = ainda provisório)
    carta.webp, ativacao.webp, moldura.webp, icone.webp, efeitos/...     as artes, quando forem enviadas

Trocar uma arte provisória pela definitiva = copiar o arquivo para a pasta do setup e preencher o nome no setup.json. Nenhum código muda.
O arquivo só vale se existir de fato na pasta: um nome digitado errado não vira link quebrado no app, o setup continua provisório.
Setup novo = pasta nova + uma função em DETECTORES + uma linha no pubspec.yaml (o Flutter só empacota as pastas que estão listadas lá).

DETECÇÃO. Cada detector recebe os candles FECHADOS, do mais antigo ao mais novo, e avalia somente o último deles. Não existe parâmetro por onde o
futuro possa entrar, e o histórico entra só como insumo das médias e dos canais (nunca como lugar onde procurar sinal). Quem decide QUAL candle avaliar,
e quando, é setups_vivo.py.
"""
from __future__ import annotations

import functools
import json
import os

import cartas as C
import cartas_catalogo as CAT

PASTA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app", "assets", "setups")
SLOTS = ("carta", "ativacao", "moldura", "icone")        # artes únicas por setup; `efeitos` é uma lista
CAMPOS_TEXTO = ("resumo",)


class ErroSetup(ValueError):
    pass


# ------------------------------------------------------------------ indicadores (só o que os detectores usam)
def _sma(v: list[float], n: int, fim: int | None = None) -> float | None:
    """Média simples dos `n` valores que terminam em `fim` (exclusivo; padrão: o último)."""
    fim = len(v) if fim is None else fim
    if n <= 0 or fim < n or fim > len(v):
        return None
    return sum(v[fim - n:fim]) / n


def _ema(v: list[float], n: int) -> list[float | None]:
    """Média exponencial, semeada pela média simples dos `n` primeiros valores. Alinhada a `v`: None antes de existir."""
    out: list[float | None] = [None] * len(v)
    if len(v) < n:
        return out
    e = sum(v[:n]) / n
    out[n - 1] = e
    k = 2 / (n + 1)
    for i in range(n, len(v)):
        e = v[i] * k + e * (1 - k)
        out[i] = e
    return out


# ------------------------------------------------------------------ detectores
# Parâmetros nomeados: cada setup segue o método do CRIADOR (o texto da carta é só ilustrativo por enquanto; o Clássico não tem criador e segue a carta).
# Cada ativação pausa os DOIS jogadores por alguns segundos, então a frequência é parte do jogo: o motor limita a 2 ativações por jogador e 8 candles de carência.
# Sinais a cada 100 candles em 120 mercados simulados (lateral · tendência): Turtle ≈ 13 · 14, Larry Williams (gatilhos armados) ≈ 24 · 20, Minervini ≈ 0 · 0,2,
# Clássico ≈ 0,9 · 1,5. O Minervini quase não dispara porque o VCP real é raro: é seletivo de propósito. São mercados sorteados, não dado real.
# --- Setup Clássico (sem criador: a regra é a da carta): rompimento de pivô de alta com volume
CL_K, CL_JANELA, CL_VOLUME, CL_TENDENCIA, CL_ALVO_R = 3, 30, 1.2, 21, 2.0   # pivô = topo com 3 candles menores de cada lado, dos últimos 30; volume > 1,2x a média de 20; acima da média de 21; alvo 2:1
# --- Turtle Trading (Richard Dennis e William Eckhardt, o "Sistema 1" e o "Sistema 2" das regras dos Turtles)
TURTLE_S1, TURTLE_S1_SAIDA, TURTLE_S2, TURTLE_N, TURTLE_STOP_N = 20, 10, 55, 20, 2.0     # entrada em 20 dias (saída em 10) e 55 dias; N = ATR de 20; stop de 2N
TURTLE_OLHAR = 400                                                                       # até onde se procura o rompimento anterior (filtro do Sistema 1)
# --- Larry Williams (setup "9.1": a média exponencial de 9 vira e a máxima/mínima do candle vira o gatilho; stop no outro extremo)
LW_MEDIA, LW_VALIDADE, LW_MIN_CANDLES = 9, 1, 40                      # o gatilho vale só para o candle seguinte e é reposicionado enquanto a média seguir na mesma direção
# --- Mark Minervini (Trend Template + VCP): tendência de alta, contrações sucessivas menores com o volume secando e rompimento do pivô com volume
MM_TOPO, MM_ACIMA_FUNDO, MM_JANELA = 0.75, 1.30, 250                  # a no máximo 25% do topo e pelo menos 30% acima do fundo de 52 semanas
MM_K, MM_BASE_MAX, MM_CONTRACOES, MM_PROF_ULT = 3, 65, 2, 0.12        # swings de 3 candles; base de até 65 candles; ao menos 2 contrações; a última com no máximo 12% de profundidade
MM_VOLUME, MM_STOP_MAX, MM_ALVO_R = 1.4, 0.08, 3.0                    # rompimento com volume 40% acima da média de 50; stop no fundo da última contração, no máximo 8%; alvo 3:1


def _classico(v: list[dict]) -> dict | None:
    """Setup Clássico (só compra, como na carta): o candle fecha PELA PRIMEIRA VEZ acima do último pivô de alta (topo local confirmado por `CL_K` candles
    menores à direita e não maiores à esquerda), com volume acima da média e acima da média de `CL_TENDENCIA` (confirmação de tendência). Stop no fundo do pivô (a mínima desde o
    topo até agora); alvo `CL_ALVO_R` vezes o risco. Só usa candles já fechados."""
    n = len(v)
    if n < max(CL_JANELA, 21) + CL_K + 2:
        return None
    h, c, lo, vol = ([x[k] for x in v] for k in ("h", "c", "l", "v"))
    ult = n - 1
    pivo = next((p for p in range(ult - CL_K - 1, max(CL_K, ult - CL_JANELA) - 1, -1)
                 if all(h[p] >= h[p - k] and h[p] > h[p + k] for k in range(1, CL_K + 1))), None)
    if pivo is None or max(c[pivo + 1:ult], default=0.0) > h[pivo] or c[ult] <= h[pivo]:
        return None                                                  # sem pivô, ou o pivô já tinha sido rompido antes, ou ainda não rompeu
    media_vol = _sma(vol[:-1], 20)
    media = _sma(c, CL_TENDENCIA)
    if not media_vol or vol[ult] <= CL_VOLUME * media_vol or media is None or c[ult] <= media:
        return None
    stop = min(lo[pivo:ult + 1])
    if stop >= c[ult]:
        return None
    return {"direcao": "alta", "stop": round(stop, 4), "alvo": round(c[ult] + CL_ALVO_R * (c[ult] - stop), 4),
            "motivo": "Rompimento do pivô de alta com volume acima da média."}


def _atr(v: list[dict], n: int) -> float | None:
    """Média do intervalo verdadeiro dos últimos `n` candles (o candle atual entra). None se não há candles suficientes."""
    if len(v) < n + 1:
        return None
    tr = [max(v[i]["h"] - v[i]["l"], abs(v[i]["h"] - v[i - 1]["c"]), abs(v[i]["l"] - v[i - 1]["c"])) for i in range(len(v) - n, len(v))]
    return sum(tr) / n


def _n_turtle(v: list[dict]) -> list[float | None]:
    """N dos Turtles: média do intervalo verdadeiro de `TURTLE_N` candles, atualizada de forma exponencial (N = ((n-1)·N anterior + TR) / n)."""
    tr = [v[0]["h"] - v[0]["l"]] + [max(x["h"] - x["l"], abs(x["h"] - v[k]["c"]), abs(x["l"] - v[k]["c"])) for k, x in enumerate(v[1:])]
    out: list[float | None] = [None] * len(v)
    if len(v) < TURTLE_N:
        return out
    n = sum(tr[:TURTLE_N]) / TURTLE_N
    out[TURTLE_N - 1] = n
    for i in range(TURTLE_N, len(v)):
        n = ((TURTLE_N - 1) * n + tr[i]) / TURTLE_N
        out[i] = n
    return out


def _rompe(v: list[dict], i: int, d: int, alta: bool) -> bool:
    """O candle `i` é o PRIMEIRO a superar (alta) ou perder (baixa) o canal dos `d` candles anteriores?"""
    if i - d - 1 < 0:
        return False
    h, lo = v[i]["h"], v[i]["l"]
    ant_h, ant_l = v[i - 1]["h"], v[i - 1]["l"]
    if alta:
        return h > max(x["h"] for x in v[i - d:i]) and not ant_h > max(x["h"] for x in v[i - d - 1:i - 1])
    return lo < min(x["l"] for x in v[i - d:i]) and not ant_l < min(x["l"] for x in v[i - d - 1:i - 1])


def _s1_anterior_deu_lucro(v: list[dict], t: int, alta: bool, n: list[float | None]) -> bool | None:
    """Filtro do Sistema 1: o rompimento de 20 dias ANTERIOR (no mesmo sentido) teria dado lucro? Simula a operação dos Turtles (entrada no canal, stop de 2N,
    saída na mínima/máxima de 10 dias). None se não houve rompimento anterior ou se aquela operação ainda estaria aberta."""
    p = next((i for i in range(t - 1, max(TURTLE_S1 + 1, t - TURTLE_OLHAR), -1) if _rompe(v, i, TURTLE_S1, alta)), None)
    if p is None or n[p] is None:
        return None
    nivel = max(x["h"] for x in v[p - TURTLE_S1:p]) if alta else min(x["l"] for x in v[p - TURTLE_S1:p])
    stop = nivel - TURTLE_STOP_N * n[p] if alta else nivel + TURTLE_STOP_N * n[p]
    for k in range(p + 1, t):
        saida = min(x["l"] for x in v[k - TURTLE_S1_SAIDA:k]) if alta else max(x["h"] for x in v[k - TURTLE_S1_SAIDA:k])
        if alta and v[k]["l"] <= stop:
            return False
        if not alta and v[k]["h"] >= stop:
            return False
        if (alta and v[k]["l"] < saida) or (not alta and v[k]["h"] > saida):
            return (saida > nivel) if alta else (saida < nivel)
    return None


def _turtle(v: list[dict]) -> dict | None:
    """Turtle Trading, como os Turtles operavam (compra e venda). Sistema 1: rompimento do canal de 20 dias, só se o rompimento anterior (no mesmo sentido)
    teria dado prejuízo (se teria dado lucro, pula). Sistema 2: rompimento de 55 dias, sempre (a rede de segurança). Só vale o primeiro candle do rompimento.
    Stop de 2N (N = ATR de 20). A saída dos Turtles é na mínima (máxima) de 10 dias: é regra de saída, não de entrada, então fica a cargo do jogador."""
    t = len(v) - 1
    if t < TURTLE_S2 + 1:
        return None
    n = _n_turtle(v)
    if n[t] is None:
        return None
    for alta in (True, False):
        s2 = _rompe(v, t, TURTLE_S2, alta)
        s1 = _rompe(v, t, TURTLE_S1, alta) and _s1_anterior_deu_lucro(v, t, alta, n) is not True
        if not (s1 or s2):
            continue
        c = v[t]["c"]
        stop = c - TURTLE_STOP_N * n[t] if alta else c + TURTLE_STOP_N * n[t]
        lado = ("acima da máxima" if alta else "abaixo da mínima")
        return {"direcao": "alta" if alta else "baixa", "stop": round(stop, 4),
                "motivo": f"Rompimento de {TURTLE_S2 if s2 else TURTLE_S1} dias: fechamento {lado} dos últimos {TURTLE_S2 if s2 else TURTLE_S1} candles."}
    return None


def _larry(v: list[dict]) -> dict | None:
    """Larry Williams, setup 9.1: quando a média exponencial de 9 VIRA (para cima, ou para baixo), a máxima (mínima) desse candle vira o gatilho de compra
    (venda) e a mínima (máxima) dele, o stop. Se o candle seguinte não acionar, o gatilho é reposicionado para o novo candle enquanto a média continuar na mesma
    direção; depois de acionado, não se entra de novo na mesma virada. Sem alvo fixo: a saída é a média virar contra. Setup ARMADO: aqui só se prepara o gatilho."""
    n = len(v)
    if n < LW_MIN_CANDLES:
        return None
    e = _ema([x["c"] for x in v], LW_MEDIA)
    if None in (e[-1], e[-2]) or e[-1] == e[-2]:
        return None
    alta = e[-1] > e[-2]
    r = n - 1                                                           # a virada: o primeiro candle desta corrida da média
    while r - 2 >= 0 and e[r - 2] is not None and ((e[r - 1] > e[r - 2]) if alta else (e[r - 1] < e[r - 2])):
        r -= 1
    if any((v[k]["h"] > v[k - 1]["h"]) if alta else (v[k]["l"] < v[k - 1]["l"]) for k in range(r + 1, n)):
        return None                                                     # o gatilho já foi acionado nesta virada: não se entra de novo
    a = v[-1]
    if a["h"] - a["l"] <= 0:
        return None
    if alta:
        return {"direcao": "alta", "gatilho": a["h"], "stop": a["l"], "validade": LW_VALIDADE,
                "motivo": f"A média de {LW_MEDIA} está para cima: compra na superação da máxima do candle."}
    return {"direcao": "baixa", "gatilho": a["l"], "stop": a["h"], "validade": LW_VALIDADE,
            "motivo": f"A média de {LW_MEDIA} está para baixo: venda na perda da mínima do candle."}


def _swings(v: list[dict], ini: int, fim: int) -> list[tuple[int, str, float]]:
    """Topos e fundos locais (`MM_K` candles de cada lado) em [ini, fim), alternados: dois do mesmo tipo seguidos ficam só com o mais extremo."""
    h, lo, brutos = [x["h"] for x in v], [x["l"] for x in v], []
    for i in range(max(ini, MM_K), fim - MM_K):
        if all(h[i] >= h[i - k] and h[i] >= h[i + k] for k in range(1, MM_K + 1)):
            brutos.append((i, "H", h[i]))
        if all(lo[i] <= lo[i - k] and lo[i] <= lo[i + k] for k in range(1, MM_K + 1)):
            brutos.append((i, "L", lo[i]))
    out: list[tuple[int, str, float]] = []
    for i, tp, pr in sorted(brutos, key=lambda x: (x[0], x[1])):
        if out and out[-1][1] == tp:
            if (tp == "H" and pr >= out[-1][2]) or (tp == "L" and pr <= out[-1][2]):
                out[-1] = (i, tp, pr)
        else:
            out.append((i, tp, pr))
    return out


def _minervini(v: list[dict]) -> dict | None:
    """Mark Minervini (só compra). Trend Template: fechamento > médias de 50, 150 e 200, com 50 > 150 > 200 e a de 200 subindo; a no máximo 25% do topo e pelo menos
    30% acima do fundo de 52 semanas. (A força relativa contra o mercado não entra: o jogo não tem o índice.) VCP: contrações sucessivas, cada uma mais rasa que a
    anterior, a última curta, com o volume secando; compra no rompimento do pivô (o topo onde começou a última contração) com volume 40% acima da média de 50.
    Stop no fundo da última contração (no máximo 8% abaixo); alvo de 3 vezes o risco."""
    n = len(v)
    if n < 221:
        return None
    c, h, lo, vol = ([x[k] for x in v] for k in ("c", "h", "l", "v"))
    m50, m150, m200, m200_antes = _sma(c, 50), _sma(c, 150), _sma(c, 200), _sma(c, 200, n - 20)
    if None in (m50, m150, m200, m200_antes) or not (c[-1] > m50 > m150 > m200 and m200 > m200_antes):
        return None
    janela = v[-MM_JANELA:]
    if c[-1] < MM_TOPO * max(x["h"] for x in janela) or c[-1] < MM_ACIMA_FUNDO * min(x["l"] for x in janela):
        return None
    sw = _swings(v, n - 1 - MM_BASE_MAX, n - 1)
    pares = [(sw[i], sw[i + 1]) for i in range(len(sw) - 1) if sw[i][1] == "H" and sw[i + 1][1] == "L"]
    pares = pares[-4:]
    if len(pares) < MM_CONTRACOES:
        return None
    prof = [(a[2] - b[2]) / a[2] for a, b in pares]
    if any(prof[i] >= prof[i - 1] for i in range(1, len(prof))) or prof[-1] > MM_PROF_ULT:
        return None                                                     # as contrações precisam ir diminuindo, e a última ser curta
    topo_i, fundo = pares[-1][0][0], pares[-1][1][2]
    pivo = max(h[topo_i:n - 1])
    media_vol = _sma(vol[:-1], 50)
    seca = _sma(vol[topo_i:n - 1], len(vol[topo_i:n - 1]))
    if not media_vol or seca is None or seca >= media_vol or vol[-1] < MM_VOLUME * media_vol:
        return None                                                     # o volume tem que ter secado na contração e explodir no rompimento
    if c[-1] <= pivo or max(c[topo_i:n - 1]) > pivo:
        return None
    stop = max(fundo, c[-1] * (1 - MM_STOP_MAX))
    if stop >= c[-1]:
        return None
    return {"direcao": "alta", "stop": round(stop, 4), "alvo": round(c[-1] + MM_ALVO_R * (c[-1] - stop), 4),
            "motivo": "Contrações sucessivas com volume secando e rompimento do pivô com volume."}


# ------------------------------------------------------------------ padrões de candle (Martelo, Engolfo de Alta, Estrela Cadente)
# Regra de ouro: o padrão NUNCA ativa só pela aparência do candle. Precisa, ao mesmo tempo, de (1) o padrão medido por regras matemáticas fixas,
# (2) uma região de interesse que o jogador marcou ANTES da partida (suporte/zona de alta para comprar; resistência/zona de baixa para vender),
# (3) o candle FECHADO (o motor só entrega candles fechados) e (4) todas as proporções da carta. Sem região marcada, nada ativa.
PAD_CORPO_MAX = 0.35            # corpo relativamente pequeno: no máximo 35% da amplitude do candle
PAD_SOMBRA_X = 2.0              # sombra principal pelo menos 2 vezes o corpo
PAD_SOMBRA_OPOSTA_MAX = 0.15    # a sombra do outro lado é pequena: no máximo 15% da amplitude
PAD_STOP_FOLGA = 0.05           # o stop fica além do extremo do padrão por 5% da amplitude do padrão
PAD_ALVO_R = 2.0                # alvo inicial: risco/retorno de 2:1
REGIAO_TOL_ATR = 0.5            # tolerância da região: meio ATR (da análise) para cada lado, para o candle não precisar tocar a linha exata
REGIAO_TOL_PCT = 0.002          # ...e nunca menos que 0,2% do preço
ROTULO_REGIAO = {"suporte": "suporte", "resistencia": "resistência", "zona_alta": "zona de alta", "zona_baixa": "zona de baixa"}


def _partes(x: dict) -> tuple[float, float, float, float]:
    """(corpo, amplitude, sombra inferior, sombra superior) de um candle."""
    corpo, amp = abs(x["c"] - x["o"]), x["h"] - x["l"]
    return corpo, amp, min(x["o"], x["c"]) - x["l"], x["h"] - max(x["o"], x["c"])


def _martelo(v: list[dict]) -> dict | None:
    x = v[-1]
    corpo, amp, inf, sup = _partes(x)
    if amp <= 0 or corpo > PAD_CORPO_MAX * amp or inf < PAD_SOMBRA_X * corpo or sup > PAD_SOMBRA_OPOSTA_MAX * amp:
        return None
    if x["c"] < x["l"] + 0.5 * amp:                                  # fechamento na metade superior do candle
        return None
    return {"extremo": x["l"], "stop": x["l"] - PAD_STOP_FOLGA * amp}


def _engolfo_alta(v: list[dict]) -> dict | None:
    if len(v) < 2:
        return None
    a, b = v[-2], v[-1]
    if not (a["c"] < a["o"] and b["c"] > b["o"]):                    # anterior de baixa, atual de alta
        return None
    if not (b["o"] <= a["c"] and b["c"] >= a["o"]):                  # o corpo atual envolve por completo o corpo anterior
        return None
    extremo, topo = min(a["l"], b["l"]), max(a["h"], b["h"])
    return {"extremo": extremo, "stop": extremo - PAD_STOP_FOLGA * (topo - extremo)}


def _estrela_cadente(v: list[dict]) -> dict | None:
    x = v[-1]
    corpo, amp, inf, sup = _partes(x)
    if amp <= 0 or corpo > PAD_CORPO_MAX * amp or sup < PAD_SOMBRA_X * corpo or inf > PAD_SOMBRA_OPOSTA_MAX * amp:
        return None
    if x["c"] > x["l"] + 0.5 * amp:                                  # fechamento na metade inferior do candle
        return None
    return {"extremo": x["h"], "stop": x["h"] + PAD_STOP_FOLGA * amp}


# Um motor só: cada carta é só uma linha aqui (direção, onde pode ativar e o critério do candle).
PADROES = {
    "martelo": {"nome": "Martelo", "direcao": "alta", "regioes": ("suporte", "zona_alta"), "criterio": _martelo},
    "engolfo_alta": {"nome": "Engolfo de Alta", "direcao": "alta", "regioes": ("suporte", "zona_alta"), "criterio": _engolfo_alta},
    "estrela_cadente": {"nome": "Estrela Cadente", "direcao": "baixa", "regioes": ("resistencia", "zona_baixa"), "criterio": _estrela_cadente},
}


def regioes_das_marcas(marcas: dict | None, atr: float | None, ref: float, partida: str, jog_n: int, rodada: int, criada_em: float) -> list[dict]:
    """As regiões de interesse que o jogador marcou na estratégia, já com a tolerância, prontas para serem CONGELADAS no começo do replay.
    Suporte e resistência (linhas de preço) viram uma faixa em volta da linha; zonas ficam com os limites que o jogador desenhou, também com a tolerância."""
    tol = max(REGIAO_TOL_ATR * atr if atr else 0.0, REGIAO_TOL_PCT * ref)
    out = []
    for k, n in enumerate((marcas or {}).get("niveis") or []):
        papel, pr = n.get("papel"), n.get("preco")
        if papel in ("suporte", "resistencia") and isinstance(pr, (int, float)):
            out.append({"id": f"{partida}:{jog_n}:{rodada}:n{k}", "tipo": papel, "min": round(pr - tol, 4), "max": round(pr + tol, 4),
                        "partida": partida, "criada_em": float(criada_em)})
    for k, z in enumerate((marcas or {}).get("zonas") or []):
        try:
            lo, hi = sorted((float(z["p1"]), float(z["p2"])))
        except (KeyError, TypeError, ValueError):
            continue
        out.append({"id": f"{partida}:{jog_n}:{rodada}:z{k}", "tipo": "zona_alta" if z.get("reacao") == "alta" else "zona_baixa",
                    "min": round(lo - tol, 4), "max": round(hi + tol, 4), "partida": partida, "criada_em": float(criada_em)})
    return out


def _detectar_padrao(setup_id: str, v: list[dict], regioes: list[dict] | None) -> dict | None:
    spec = PADROES[setup_id]
    pad = spec["criterio"](v)
    if not pad:
        return None
    reg = next((r for r in regioes or [] if r["tipo"] in spec["regioes"] and r["min"] <= pad["extremo"] <= r["max"]), None)
    if reg is None:                                                  # padrão perfeito, mas fora de uma região marcada (ou numa região do tipo errado): nunca ativa
        return None
    entrada, stop = v[-1]["c"], pad["stop"]
    sinal = 1 if spec["direcao"] == "alta" else -1
    risco = (entrada - stop) * sinal
    if risco <= 0:
        return None
    return {"direcao": spec["direcao"], "stop": round(stop, 4), "alvo": round(entrada + sinal * PAD_ALVO_R * risco, 4),
            "regiao": {k: reg[k] for k in ("id", "tipo", "min", "max")},
            "motivo": f"{spec['nome']} fechado na {ROTULO_REGIAO[reg['tipo']]} que você marcou."}


DETECTORES = {"setup_classico": _classico, "turtle_trading": _turtle, "larry_williams": _larry, "mark_minervini": _minervini}


def detectar(setup_id: str, fechados: list[dict], regioes: list[dict] | None = None) -> dict | None:
    """Sinal do ÚLTIMO candle fechado da lista ({'direcao', 'motivo'}) ou None. Só olha para trás: não há como enxergar o futuro daqui.
    `regioes`: as regiões de interesse congeladas do jogador (só os padrões de candle usam; sem elas, esses nunca ativam)."""
    if not fechados:
        return None
    if setup_id in PADROES:
        return _detectar_padrao(setup_id, fechados, regioes)
    fn = DETECTORES.get(setup_id)
    return fn(fechados) if fn else None


# ------------------------------------------------------------------ catálogo (uma pasta por setup)
def _ler_um(pasta: str) -> dict:
    id_ = os.path.basename(pasta)
    with open(os.path.join(pasta, "setup.json"), encoding="utf-8") as f:
        d = json.load(f)
    if d.get("id") != id_:
        raise ErroSetup(f"{id_}/setup.json: o id precisa ser igual ao nome da pasta.")
    if id_ not in DETECTORES and id_ not in PADROES:
        raise ErroSetup(f"{id_}: não há detector para este setup.")
    if d.get("raridade") not in CAT.RARIDADES:
        raise ErroSetup(f"{id_}: raridade inválida.")
    if not str(d.get("nome") or "").strip():
        raise ErroSetup(f"{id_}: falta o nome.")
    a = d.get("assets") or {}

    def existe(nome):
        return bool(nome) and os.path.isfile(os.path.join(pasta, str(nome)))
    assets = {s: (f"assets/setups/{id_}/{a[s]}" if existe(a.get(s)) else None) for s in SLOTS}
    assets["efeitos"] = [f"assets/setups/{id_}/{n}" for n in (a.get("efeitos") or []) if existe(n)]
    cores = {"principal": "#8FB4F0", "brilho": "#FFFFFF", **(d.get("cores") or {})}
    return {"id": id_, "nome": str(d["nome"]).strip(), "raridade": d["raridade"], "resumo": str(d.get("resumo") or ""),
            "caracteristicas": [str(x) for x in d.get("caracteristicas") or []], "indicadores": [str(x) for x in d.get("indicadores") or []],
            "regra": {"compra": str((d.get("regra") or {}).get("compra") or ""), "venda": str((d.get("regra") or {}).get("venda") or "")},
            "fonte_regra": str(d.get("fonte_regra") or ""), "saida": str(d.get("saida") or ""), "cores": cores, "assets": assets, "provisorio": not (assets["carta"] and assets["ativacao"])}


@functools.lru_cache(maxsize=1)
def catalogo() -> tuple[dict, ...]:
    """Todos os setups do jogo, na ordem da raridade e do nome. Lê as pastas uma vez; `recarregar()` lê de novo."""
    if not os.path.isdir(PASTA):
        return ()
    itens = [_ler_um(os.path.join(PASTA, n)) for n in sorted(os.listdir(PASTA)) if os.path.isfile(os.path.join(PASTA, n, "setup.json"))]
    ordem = {r: i for i, r in enumerate(CAT.RARIDADES)}
    return tuple(sorted(itens, key=lambda s: (ordem[s["raridade"]], s["nome"])))


def recarregar() -> None:
    catalogo.cache_clear()


def info(setup_id: str) -> dict | None:
    return next((s for s in catalogo() if s["id"] == setup_id), None)


# ------------------------------------------------------------------ coleção de uma pessoa
def colecao_vazia() -> dict:
    return {"v": 1, "itens": {}, "equipados": [], "ids": [], "log": []}


IDS_MAX, LOG_MAX = 500, 100

# Por enquanto TODOS os setups estão liberados: o jogador só escolhe quais usar (até MAX_EQUIPADOS). A coleção por cartas continua intacta (o que alguém já
# conquistou fica registrado) e volta a valer, sem mexer em mais nada, trocando esta chave para False.
LIBERAR_TODOS = True


def tem(doc: dict, setup_id: str) -> bool:
    """O jogador pode usar este setup? (liberado para todos, ou a carta dele está na coleção.)"""
    return bool(info(setup_id)) and (LIBERAR_TODOS or setup_id in doc["itens"])
MAX_EQUIPADOS = 2      # cada jogador usa até 2 setups ao mesmo tempo, desde que tenha a carta de cada um


def normalizar(doc) -> dict:
    d = colecao_vazia()
    if isinstance(doc, dict) and doc.get("v") == 1:
        d["itens"] = {str(k): dict(v) for k, v in (doc.get("itens") or {}).items() if isinstance(v, dict)}      # o que foi conquistado nunca sai
        bruto = doc.get("equipados")
        if bruto is None:
            bruto = [doc.get("equipado")]                                                                          # formato antigo (um só)
        eqs = []
        for x in bruto if isinstance(bruto, list) else []:
            if tem(d, x) and x not in eqs:                                                                           # só se equipa o que existe e o jogador pode usar
                eqs.append(x)
        d["equipados"] = eqs[:MAX_EQUIPADOS]
        d["ids"] = list(doc.get("ids") or [])[-IDS_MAX:]
        d["log"] = list(doc.get("log") or [])[:LOG_MAX]
    return d


def _registrar(doc: dict, tipo: str, agora_iso: str, **kw) -> None:
    doc["log"] = ([{"t": agora_iso, "tipo": tipo, **kw}] + doc["log"])[:LOG_MAX]


def conquistar(doc: dict, setup_id: str, origem: str, agora_iso: str) -> bool:
    """Registra o setup como conquistado. Devolve False se já era dela (nada muda): conquista é permanente e não duplica."""
    if not info(setup_id):
        raise ErroSetup("Setup desconhecido.")
    if setup_id in doc["itens"]:
        return False
    doc["itens"][setup_id] = {"desde": agora_iso, "origem": origem}
    _registrar(doc, "conquista", agora_iso, setup=setup_id, origem=origem)
    return True


def equipar(doc: dict, setup_id: str, agora_iso: str) -> dict:
    """Equipa um setup cuja carta a pessoa tem. Até MAX_EQUIPADOS ao mesmo tempo; com todos os espaços ocupados, é preciso desequipar um antes."""
    if not info(setup_id):
        raise ErroSetup("Setup desconhecido.")
    if not tem(doc, setup_id):
        raise ErroSetup("Você ainda não tem a carta deste setup.")
    if setup_id not in doc["equipados"]:
        if len(doc["equipados"]) >= MAX_EQUIPADOS:
            raise ErroSetup(f"Você já está usando {MAX_EQUIPADOS} setups. Desequipe um para equipar outro.")
        doc["equipados"].append(setup_id)
        _registrar(doc, "equipar", agora_iso, setup=setup_id)
    return {"equipados": list(doc["equipados"])}


def desequipar(doc: dict, setup_id: str, agora_iso: str) -> dict:
    if setup_id in doc["equipados"]:
        doc["equipados"].remove(setup_id)
        _registrar(doc, "desequipar", agora_iso, setup=setup_id)
    return {"equipados": list(doc["equipados"])}


# ------------------------------------------------------------------ baús
# Chance de um baú de cada tier trazer UM setup, além do que ele já traz. É uma rolagem à parte: as cartas e as moedas do baú não mudam.
# A raridade do setup sai da MESMA tabela de pesos do baú (cartas_catalogo.BAUS[...]["chances"]), então baú melhor favorece setup mais raro.
CHANCE_BAU = {"comum": 0.04, "raro": 0.08, "epico": 0.15, "lendario": 0.30}


def sortear_do_bau(seed: str, rar_bau: str, doc: dict, baus: dict, chance: dict | None = None) -> str | None:
    """Setup que veio neste baú, ou None. Determinístico: mesma semente, mesmo resultado. Só sai o que ela ainda NÃO conquistou."""
    rng = C._rng("setup|" + seed)
    if rng.random() >= float((chance or CHANCE_BAU).get(rar_bau, 0.0)):
        return None
    livres = {r: sorted(s["id"] for s in catalogo() if s["raridade"] == r and s["id"] not in doc["itens"]) for r in CAT.RARIDADES}
    if not any(livres.values()):
        return None
    conf = baus.get(rar_bau) or baus["comum"]
    return rng.choice(livres[C._sortear_raridade(rng, conf["chances"], livres)])
