"""Leitura AO VIVO de cripto (modo "Ao Vivo"): o jogador lê o gráfico de agora, desenha e escolhe Subir, Cair ou Aguardar. O futuro ainda não aconteceu, então
ninguém pode saber a resposta. A leitura vale por HORIZONTE candles fechados depois do último que o jogador viu; então o servidor confere (direção e desenhos).

Módulo puro (sem banco e sem rede): recebe e devolve dicionários; o servidor (api/main.py) guarda as previsões do jogador.

Nota final (0 a 100, 50 = acaso): média entre a DIREÇÃO (100 se acertou, 0 se errou; "Aguardar" não aposta e fica fora) e a nota dos DESENHOS
(trader_leitura, já descontado o acaso). Sem nada avaliável, a previsão fecha sem nota.
"""
from __future__ import annotations

import trader_battle as TB
import trader_leitura as TL

HORIZONTE = {"1m": 15, "5m": 12}        # candles fechados até conferir (15 min no 1m, 1 hora no 5m)
MAX_PENDENTES = 4                        # previsões em aberto por jogador
MAX_GUARDADAS = 30                       # histórico guardado por jogador
EXPIRA_S = 6 * 3600                      # previsão sem conferência possível (candles saíram da janela) é encerrada sem nota
DIRECOES = ("alta", "baixa")


class ErroVivo(Exception):
    pass


def fechados(velas: list[dict]) -> list[dict]:
    return [c for c in velas if c.get("fechado")]


def criar(moeda: str, tf: str, direcao, marcas, n_vistos: int, velas: list[dict], agora: float, pid: str) -> dict:
    """Registra a previsão. `n_vistos` = quantos candles fechados o jogador tinha na tela (o último deles é o preço de referência)."""
    if tf not in HORIZONTE:
        raise ErroVivo("duração inválida")
    if direcao is not None and direcao not in DIRECOES:
        raise ErroVivo("direção inválida")
    fe = fechados(velas)
    if not (30 <= n_vistos <= len(fe)):
        raise ErroVivo("O gráfico mudou. Abra a leitura de novo.")
    ult = fe[n_vistos - 1]
    return {"id": pid, "moeda": moeda, "tf": tf, "direcao": direcao, "marcas": TB.validar_marcas(marcas), "n": n_vistos, "t_ref": ult["t"], "ref": ult["c"],
            "criada": float(agora), "estado": "aberta", "horizonte": HORIZONTE[tf]}


def _indice(velas: list[dict], t_ref: str) -> int | None:
    for i, c in enumerate(velas):
        if c["t"] == t_ref:
            return i
    return None


def conferir(prev: dict, velas: list[dict], agora: float) -> dict:
    """Devolve a previsão atualizada: ainda `aberta`, `conferida` (com resultado) ou `expirada`. Não muda a entrada."""
    if prev.get("estado") != "aberta":
        return prev
    fe = fechados(velas)
    i = _indice(fe, prev["t_ref"])
    if i is None:                                           # o candle de referência já saiu da janela guardada
        return {**prev, "estado": "expirada"} if agora - prev["criada"] > EXPIRA_S else prev
    futuros = fe[i + 1:i + 1 + prev["horizonte"]]
    if len(futuros) < prev["horizonte"]:
        return {**prev, "faltam": prev["horizonte"] - len(futuros)}
    hist = fe[:i + 1]
    atr = TB._atr(hist)
    ref = prev["ref"]
    mov = futuros[-1]["c"] - ref
    real = "lateral" if atr <= 0 or abs(mov) < atr else ("alta" if mov > 0 else "baixa")
    ok_dir = None if prev["direcao"] is None else prev["direcao"] == real
    desenhos = TL.avaliar_desenhos(prev["marcas"], prev["n"], futuros, ref, atr)
    partes = []
    if ok_dir is not None:
        partes.append(100.0 if ok_dir else 0.0)
    if desenhos["nota"] is not None:
        partes.append(desenhos["nota"])
    nota = round(sum(partes) / len(partes), 1) if partes else None
    resultado = {"real": real, "mov_pct": round(mov / ref * 100, 3), "direcao_ok": ok_dir, "desenhos": desenhos, "nota": nota, "preco_fim": futuros[-1]["c"]}
    return {**prev, "estado": "conferida", "resultado": resultado, "faltam": 0}
