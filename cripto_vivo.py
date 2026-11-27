"""Candles de cripto AO VIVO (Binance, endereço público de dados de mercado, sem chave nem conta).

Uma consulta por moeda/duração serve todos os jogadores: o resultado fica guardado alguns segundos (TTL curto) e consultas simultâneas esperam a mesma
resposta (nada de cada jogador bater na Binance). Se a Binance falhar, devolve o último gráfico guardado marcado como `atrasado` (e só falha de vez se
nunca houve resposta). Módulo sem banco: o `buscar` é injetável nos testes.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

BASE = "https://data-api.binance.vision/api/v3/klines"
SIMBOLOS = {"BTC": "BTCUSDT", "ETH": "ETHUSDT", "SOL": "SOLUSDT", "BNB": "BNBUSDT", "XRP": "XRPUSDT", "DOGE": "DOGEUSDT"}
NOMES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "BNB": "BNB", "XRP": "XRP", "DOGE": "Dogecoin"}
INTERVALOS = {"1m": 60, "5m": 300}                       # duração do candle em segundos
TTL = {"1m": 4.0, "5m": 8.0}                             # quanto tempo o gráfico guardado vale antes de nova consulta
N_MIN, N_MAX = 30, 500
TIMEOUT_S = 6.0


class SemDados(Exception):
    """A Binance não respondeu e não há gráfico guardado."""


_lock = threading.Lock()
_cache: dict[tuple[str, str], dict] = {}                 # (moeda, tf) -> {"t": quando, "velas": [...]}
_locks: dict[tuple[str, str], threading.Lock] = {}
_sessao = None


def _buscar_binance(simbolo: str, tf: str, n: int) -> list:
    global _sessao
    import requests
    if _sessao is None:
        _sessao = requests.Session()
    r = _sessao.get(BASE, params={"symbol": simbolo, "interval": tf, "limit": n}, timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def normalizar(brutas: list, tf: str, agora: float) -> list[dict]:
    """Linhas da Binance -> candles do jogo ({t, o, h, l, c, v}); `fechado` diz se o candle já terminou (o último costuma estar em formação)."""
    saida = []
    for k in brutas or []:
        try:
            ini_ms, o, h, l, c, v, fim_ms = int(k[0]), float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5]), int(k[6])
        except (IndexError, TypeError, ValueError):
            continue
        if min(o, h, l, c) <= 0 or h < l:
            continue
        saida.append({"t": datetime.fromtimestamp(ini_ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%M"), "o": o, "h": h, "l": l, "c": c, "v": v,
                      "fechado": fim_ms / 1000 < agora})
    return saida


def candles(moeda: str, tf: str, n: int = 300, buscar=None, agora=time.time) -> dict:
    """Gráfico atual de `moeda` (BTC, ETH...) em `tf` (1m ou 5m): {moeda, tf, candles, atualizado_em, atrasado}."""
    moeda = str(moeda or "").upper()
    if moeda not in SIMBOLOS:
        raise ValueError("moeda inválida")
    if tf not in INTERVALOS:
        raise ValueError("duração inválida")
    n = max(N_MIN, min(N_MAX, int(n)))
    chave = (moeda, tf)
    fonte = buscar or _buscar_binance
    with _lock:
        trava = _locks.setdefault(chave, threading.Lock())
    with trava:                                           # quem chega junto espera a mesma consulta
        agora_s = agora()
        c = _cache.get(chave)
        if c and agora_s - c["t"] < TTL[tf] and len(c["velas"]) >= n:
            return _resposta(moeda, tf, c, n, False)
        try:
            velas = normalizar(fonte(SIMBOLOS[moeda], tf, N_MAX), tf, agora_s)
            if len(velas) < N_MIN:
                raise SemDados("resposta curta demais")
            c = {"t": agora_s, "velas": velas}
            _cache[chave] = c
            return _resposta(moeda, tf, c, n, False)
        except Exception as e:
            if c and c["velas"]:
                return _resposta(moeda, tf, c, n, True)      # a Binance falhou: mostra o último gráfico, avisando que está atrasado
            raise SemDados(f"sem dados de {moeda} agora") from e


def _resposta(moeda: str, tf: str, c: dict, n: int, atrasado: bool) -> dict:
    return {"moeda": moeda, "nome": NOMES[moeda], "tf": tf, "candles": c["velas"][-n:], "atualizado_em": int(c["t"]), "atrasado": atrasado}


# ------------------------------------------------------------------ segundos (candles de 1 s): o candle do jogo se forma junto com o mercado
SEG_MAX = 4000                 # segundos guardados por moeda
SEG_TTL = 1.0                  # no máximo 1 consulta por segundo por moeda (todos os jogadores da moeda dividem)
_seg: dict[str, dict] = {}     # moeda -> {"t": última consulta, "linhas": {epoch_s: (o, h, l, c, v)}}


def _buscar_binance_seg(simbolo: str, fim_ms: int | None, n: int) -> list:
    global _sessao
    import requests
    if _sessao is None:
        _sessao = requests.Session()
    par = {"symbol": simbolo, "interval": "1s", "limit": min(1000, n)}
    if fim_ms is not None:
        par["endTime"] = fim_ms
    r = _sessao.get(BASE, params=par, timeout=TIMEOUT_S)
    r.raise_for_status()
    return r.json()


def _guardar(est: dict, brutas: list) -> None:
    for k in brutas or []:
        try:
            s = int(k[0]) // 1000
            o, h, l, c, v = float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])
        except (IndexError, TypeError, ValueError):
            continue
        if min(o, h, l, c) > 0 and h >= l:
            est["linhas"][s] = (o, h, l, c, v)
    if len(est["linhas"]) > SEG_MAX:
        for s in sorted(est["linhas"])[:len(est["linhas"]) - SEG_MAX]:
            del est["linhas"][s]


def segundos(moeda: str, ini: int, fim: int, buscar=None, agora=time.time) -> list[dict]:
    """Candles de 1 s já FECHADOS com início em [ini, fim) (epoch, s), em ordem e sem buracos (segundo sem negócio repete o fechamento anterior).
    Para no primeiro segundo que ainda não existe. Levanta SemDados se a Binance falhar e não houver nada guardado para o trecho."""
    moeda = str(moeda or "").upper()
    if moeda not in SIMBOLOS:
        raise ValueError("moeda inválida")
    fonte = buscar or _buscar_binance_seg
    with _lock:
        trava = _locks.setdefault((moeda, "1s"), threading.Lock())
    with trava:
        est = _seg.setdefault(moeda, {"t": 0.0, "linhas": {}})
        agora_s = agora()
        precisa_novo = agora_s - est["t"] >= SEG_TTL
        antigo = min(est["linhas"]) if est["linhas"] else None
        try:
            if precisa_novo or antigo is None:
                _guardar(est, fonte(SIMBOLOS[moeda], None, 1000))             # os últimos 1000 s
                est["t"] = agora_s
            while ini < (min(est["linhas"]) if est["linhas"] else ini + 1) and len(est["linhas"]) < SEG_MAX:   # trecho mais antigo que o guardado
                mais_velho = min(est["linhas"])
                antes = len(est["linhas"])
                _guardar(est, fonte(SIMBOLOS[moeda], mais_velho * 1000 - 1, 1000))
                if len(est["linhas"]) == antes:
                    break
        except Exception as e:
            if not est["linhas"]:
                raise SemDados(f"sem dados de {moeda} agora") from e
    linhas, fechado_ate = est["linhas"], int(agora_s) - 1                 # o segundo corrente ainda está em formação
    if not linhas:
        raise SemDados(f"sem dados de {moeda} agora")
    limite = min(fechado_ate, max(linhas))                                 # nunca inventa segundo depois do último que a Binance entregou (só tapa buraco no meio)
    saida, ant = [], None
    for s in range(int(ini), int(fim)):
        if s > limite:
            break
        if s in linhas:
            o, h, l, c, v = linhas[s]
        elif ant is not None:
            o = h = l = c = ant
            v = 0.0
        else:
            achou = [x for x in linhas if x < s]                              # primeiro segundo do trecho sem negócio: parte do último fechamento conhecido
            if not achou:
                break
            o = h = l = c = linhas[max(achou)][3]
            v = 0.0
        saida.append({"s": s, "o": o, "h": h, "l": l, "c": c, "v": v})
        ant = c
    return saida
