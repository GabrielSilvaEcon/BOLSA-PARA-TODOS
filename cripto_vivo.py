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
