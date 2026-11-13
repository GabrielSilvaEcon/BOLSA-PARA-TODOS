"""Trader Battle · fonte dos cenários históricos (sem Streamlit).

Cenários reais são PREPARADOS uma vez (a partir do Yahoo Finance, que o app já usa) e guardados no banco do sistema; as partidas só
leem o que já está guardado: nenhuma consulta de API por partida ou por candle. Sem cenários reais suficientes, entra o modo
DEMONSTRAÇÃO, sempre marcado como dados simulados (nunca apresentado como cotação real).

Trocar a fonte depois = trocar `listar()` / `salvar()` (ou chamar `preparar()` com outro `baixar`); o motor de replay não muda.
"""
from __future__ import annotations

import math
import random
from datetime import datetime, timedelta

import trader_battle as TB

CHAVE = "tb_cenarios_{tf}"
MAX_POR_FUSO = 80                      # teto de cenários guardados por timeframe
ATIVOS = ("PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "BBAS3", "B3SA3", "RENT3", "SUZB3", "GGBR4", "PRIO3", "LREN3", "ELET3", "RADL3", "JBSS3")
PERIODO_YAHOO = {"15m": "60d", "1h": "2y"}           # limite gratuito de cada intervalo
FONTE_REAL = "Yahoo Finance (histórico intradiário, preparado previamente)"


# ------------------------------------------------------------------ leitura / gravação (adaptador de banco)
def _banco(banco=None):
    if banco is not None:
        return banco
    import banco as _b
    return _b


def listar(tf: str, banco=None) -> list[dict]:
    """Cenários reais guardados e válidos. Qualquer cenário inconsistente é ignorado (nunca corrigido)."""
    try:
        dados = _banco(banco).cfg_ler(CHAVE.format(tf=tf))
    except Exception:
        return []
    return [c for c in ((dados or {}).get("cenarios") or []) if TB.validar_cenario(c)[0] and not c.get("demo")]


def salvar(tf: str, cenarios: list[dict], banco=None) -> int:
    ok = [c for c in cenarios if TB.validar_cenario(c)[0] and not c.get("demo")]
    ok = sorted(ok, key=lambda c: c["candles"][0]["t"])[-MAX_POR_FUSO:]
    _banco(banco).cfg_gravar(CHAVE.format(tf=tf), {"v": 1, "tf": tf, "cenarios": ok})
    return len(ok)


# ------------------------------------------------------------------ preparação de cenários reais (roda como tarefa, não na partida)
def janelas(df, tf: str, max_n: int = 3) -> list[tuple[int, int]]:
    """Intervalos [i, j) do DataFrame limpo que formam um cenário completo: sem candle faltando dentro do pregão, sem volume zerado em excesso."""
    cfg = TB.TIMEFRAMES[tf]
    n = cfg["n_analise"] + TB.RODADAS * cfg["n_replay"]
    passo = timedelta(minutes=cfg["passo_min"])
    idx = list(df.index)
    if len(idx) < n:
        return []
    bom = [True] * (len(idx) - 1)
    for k in range(len(idx) - 1):
        d = idx[k + 1] - idx[k]
        if idx[k].date() == idx[k + 1].date() and d != passo:
            bom[k] = False
    cand = []
    for i in range(0, len(idx) - n + 1):
        if not all(bom[i:i + n - 1]):
            continue
        if (idx[i + n - 1] - idx[i]) > timedelta(days=16):
            continue
        vol = df["Volume"].iloc[i:i + n]
        if (vol.fillna(0) <= 0).mean() > 0.05:
            continue
        cand.append((i, i + n))
    escolhidas, ult = [], -10 ** 9
    for i, j in cand[::-1]:                                   # do mais recente para trás, sem sobreposição
        if i + n <= ult or ult == -10 ** 9:
            escolhidas.append((i, j))
            ult = i
        if len(escolhidas) >= max_n:
            break
    return escolhidas


def cenario_de_df(df, i: int, j: int, ticker: str, tf: str, agora_iso: str) -> dict:
    cfg = TB.TIMEFRAMES[tf]
    sub = df.iloc[i:j]
    cand = [{"t": t.isoformat(timespec="minutes"), "o": round(float(r.Open), 4), "h": round(float(r.High), 4), "l": round(float(r.Low), 4),
             "c": round(float(r.Close), 4), "v": float(r.Volume)} for t, r in sub.iterrows()]
    return {"id": f"{ticker}-{tf}-{cand[0]['t'].replace('-', '').replace(':', '').replace('T', '')}", "ticker": ticker, "nome": ticker, "tf": tf,
            "fonte": FONTE_REAL, "demo": False, "preparado_em": agora_iso, "n_analise": cfg["n_analise"], "candles": cand}


def preparar(tf: str, baixar, agora_iso: str, ativos=ATIVOS, por_ativo: int = 3, banco=None) -> dict:
    """Baixa o histórico de cada ativo UMA vez, valida candle a candle e guarda os cenários novos. `baixar(codigo, periodo, intervalo)` devolve
    {'df': DataFrame OHLCV} ou {'erro': ...}. Devolve um relatório (quantos entraram, quais ativos falharam e por quê)."""
    import analise_tecnica as AT
    atuais = {c["id"]: c for c in listar(tf, banco)}
    rel = {"novos": 0, "total": 0, "falhas": {}}
    for cod in ativos:
        try:
            r = baixar(cod, PERIODO_YAHOO[tf], tf)
        except Exception as e:
            rel["falhas"][cod] = f"erro de conexão ({e.__class__.__name__})"
            continue
        if not r or r.get("erro") or r.get("df") is None:
            rel["falhas"][cod] = str((r or {}).get("erro") or "sem dados")
            continue
        df, info = AT.limpar_ohlcv(r["df"])
        if not info.get("tem_ohlc") or "Volume" not in df.columns:
            rel["falhas"][cod] = "histórico sem OHLC/volume completos"
            continue
        for i, j in janelas(df, tf, por_ativo):
            c = cenario_de_df(df, i, j, cod, tf, agora_iso)
            if TB.validar_cenario(c)[0] and c["id"] not in atuais:
                atuais[c["id"]] = c
                rel["novos"] += 1
    rel["total"] = salvar(tf, list(atuais.values()), banco)
    return rel


# ------------------------------------------------------------------ modo demonstração (dados SIMULADOS, sempre rotulados)
def demo_cenario(tf: str, semente: int) -> dict:
    cfg = TB.TIMEFRAMES[tf]
    rng = random.Random(semente)
    n = cfg["n_analise"] + TB.RODADAS * cfg["n_replay"]
    p, vol = 30.0 + rng.random() * 20, 0.004
    t = datetime(2024, 3, 4, 10, 0)
    cand = []
    for k in range(n):
        vol = max(0.002, min(0.012, 0.9 * vol + 0.1 * 0.005 + 0.002 * rng.random()))
        drift = 0.0006 * math.sin(k / 9.0 + semente)
        o = p
        c = max(1.0, o * (1 + drift + rng.gauss(0, vol)))
        h = max(o, c) * (1 + abs(rng.gauss(0, vol / 2)))
        l = min(o, c) * (1 - abs(rng.gauss(0, vol / 2)))
        cand.append({"t": t.isoformat(timespec="minutes"), "o": round(o, 2), "h": round(h, 2), "l": round(l, 2), "c": round(c, 2),
                     "v": float(int(80000 + rng.random() * 220000))})
        p = c
        t += timedelta(minutes=cfg["passo_min"])
        if t.hour >= 18 or (cfg["passo_min"] == 60 and t.hour >= 18):
            t = (t + timedelta(days=1)).replace(hour=10, minute=0)
            if t.weekday() >= 5:
                t += timedelta(days=7 - t.weekday())
    return {"id": f"DEMO-{tf}-{semente}", "ticker": "DEMO3", "nome": "Cenário simulado", "tf": tf, "demo": True, "fonte": "Dados SIMULADOS (modo demonstração)",
            "n_analise": cfg["n_analise"], "candles": cand}


def escolher(tf: str, semente: int, banco=None) -> dict:
    """UM cenário contínuo para a partida inteira (as 3 rodadas são trechos consecutivos do mesmo ativo): real, se houver; senão demonstração."""
    reais = listar(tf, banco)
    if reais:
        return random.Random(semente).choice(reais)
    return demo_cenario(tf, semente)


def por_id(lista: list[dict]) -> dict:
    return {c["id"]: c for c in lista}


# ------------------------------------------------------------------ referência compartilhada (multiplayer): guarda só o ID/semente, nunca os candles
_CACHE_CEN: dict = {}


def referencia(c: dict, semente: int) -> dict:
    """O que vai para o banco da partida: identifica o cenário sem copiar candles (nenhum futuro fica gravado na sala)."""
    return {"id": c["id"], "demo": bool(c.get("demo")), "semente": int(semente), "tf": c["tf"]}


def resolver(ref: dict, banco=None) -> dict:
    """Reconstrói o MESMO cenário para qualquer sessão: simulado pela semente; real pelo ID guardado (cenários são imutáveis)."""
    chave = (ref.get("id"), ref.get("tf"))
    if chave in _CACHE_CEN:
        return _CACHE_CEN[chave]
    if ref.get("demo"):
        c = demo_cenario(ref["tf"], int(ref["semente"]))
    else:
        c = por_id(listar(ref["tf"], banco)).get(ref["id"])
        if c is None:
            raise TB.ErroTrader("O cenário desta partida não está mais disponível.")
    if len(_CACHE_CEN) > 64:
        _CACHE_CEN.clear()
    _CACHE_CEN[chave] = c
    return c
