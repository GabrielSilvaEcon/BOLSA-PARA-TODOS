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
SUFIXO_B24 = "-b24"                    # cenários de 24 candles por bloco no 1h: id próprio, para nunca colidir com os antigos (16 por bloco)
MAX_DIAS_B24 = {"1h": 90}              # 340 candles de 1h passam de 60 dias corridos: o limite de 70 do formato antigo reprovaria quase tudo
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


def _grupo(c: dict) -> str:
    return "b24" if str(c.get("id", "")).endswith(SUFIXO_B24) else "legado"


def salvar(tf: str, cenarios: list[dict], banco=None) -> int:
    """Teto de MAX_POR_FUSO aplicado SEPARADAMENTE por grupo: cenários novos (-b24) nunca expulsam os antigos (partidas antigas dependem deles)."""
    ok = [c for c in cenarios if TB.validar_cenario(c)[0] and not c.get("demo")]
    ok = sorted(ok, key=lambda c: c["candles"][0]["t"])
    ok = [c for g in ("legado", "b24") for c in [x for x in ok if _grupo(x) == g][-MAX_POR_FUSO:]]
    _banco(banco).cfg_gravar(CHAVE.format(tf=tf), {"v": 1, "tf": tf, "cenarios": ok})
    return len(ok)


# ------------------------------------------------------------------ preparação de cenários reais (roda como tarefa, não na partida)
def janelas(df, tf: str, max_n: int = 3, b24: bool = False) -> list[tuple[int, int]]:
    """Intervalos [i, j) do DataFrame limpo que formam um cenário completo: sem candle faltando dentro do pregão, sem volume zerado em excesso.
    b24=True: blocos de 24 candles (mesa), com o limite de dias próprio do formato."""
    cfg = TB.TIMEFRAMES[tf]
    n = cfg["n_analise"] + TB.RODADAS * (TB.N_REPLAY_MESA if b24 else cfg["n_replay"])
    max_dias = MAX_DIAS_B24.get(tf, cfg["max_dias"]) if b24 else cfg["max_dias"]
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
        if (idx[i + n - 1] - idx[i]) > timedelta(days=max_dias):
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


def cenario_de_df(df, i: int, j: int, ticker: str, tf: str, agora_iso: str, b24: bool = False) -> dict:
    cfg = TB.TIMEFRAMES[tf]
    suf = SUFIXO_B24 if b24 and TB.N_REPLAY_MESA != cfg["n_replay"] else ""      # no 15m o bloco já é de 24: o cenário é o mesmo, com o mesmo id
    sub = df.iloc[i:j]
    cand = [{"t": t.isoformat(timespec="minutes"), "o": round(float(r.Open), 4), "h": round(float(r.High), 4), "l": round(float(r.Low), 4),
             "c": round(float(r.Close), 4), "v": float(r.Volume)} for t, r in sub.iterrows()]
    return {"id": f"{ticker}-{tf}-{cand[0]['t'].replace('-', '').replace(':', '').replace('T', '')}-a{cfg['n_analise']}{suf}", "ticker": ticker, "nome": ticker, "tf": tf,
            "fonte": FONTE_REAL, "demo": False, "preparado_em": agora_iso, "n_analise": cfg["n_analise"], "candles": cand}


def preparar(tf: str, baixar, agora_iso: str, ativos=ATIVOS, por_ativo: int = 3, banco=None, b24: bool = False) -> dict:
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
        for i, j in janelas(df, tf, por_ativo, b24):
            c = cenario_de_df(df, i, j, cod, tf, agora_iso, b24)
            if TB.validar_cenario(c)[0] and c["id"] not in atuais:
                atuais[c["id"]] = c
                rel["novos"] += 1
    rel["total"] = salvar(tf, list(atuais.values()), banco)
    return rel


# ------------------------------------------------------------------ modo demonstração (dados SIMULADOS, sempre rotulados)
def demo_cenario(tf: str, semente: int, b24: bool = False) -> dict:
    cfg = TB.TIMEFRAMES[tf]
    rng = random.Random(semente)
    n = cfg["n_analise"] + TB.RODADAS * (TB.N_REPLAY_MESA if b24 else cfg["n_replay"])
    suf = SUFIXO_B24 if b24 and TB.N_REPLAY_MESA != cfg["n_replay"] else ""
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
    return {"id": f"DEMO-{tf}-{semente}{suf}", "ticker": "DEMO3", "nome": "Cenário simulado", "tf": tf, "demo": True, "fonte": "Dados SIMULADOS (modo demonstração)",
            "n_analise": cfg["n_analise"], "candles": cand}


def formatos_disponiveis(tf: str, banco=None) -> list[str]:
    """Formatos (rapida/normal/longa) que a sala pode oferecer agora: há cenário real que comporte as rodadas, ou nenhum real (então vale a demonstração)."""
    reais = listar(tf, banco)
    return [f for f, n in TB.FORMATOS.items() if not reais or any(TB.capacidade_rodadas(c) >= n for c in reais)]


def escolher(tf: str, semente: int, banco=None, rodadas: int | None = None) -> dict:
    """UM cenário contínuo para a partida inteira (todas as rodadas são trechos consecutivos do mesmo ativo): real, se houver; senão demonstração.
    `rodadas` (mesa): só serve cenário que comporte esse nº de rodadas de 24 candles; sem `rodadas` vale o comportamento antigo."""
    reais = listar(tf, banco)
    if rodadas is not None:
        if reais:
            reais = [c for c in reais if TB.capacidade_rodadas(c) >= rodadas]
            if not reais:
                raise TB.ErroTrader("Ainda não há cenários reais deste timeframe para esse formato de partida. Escolha um formato menor ou outro timeframe.")
        else:
            return demo_cenario(tf, semente, b24=True)
    novos = [c for c in reais if c["n_analise"] == TB.TIMEFRAMES[tf]["n_analise"]]   # prefere os de histórico longo; os antigos só entram se ainda não há nenhum novo
    if novos or reais:
        return random.Random(semente).choice(novos or reais)
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
    if ref.get("corrida"):                                    # partida corrida: cenários próprios por duração
        c = demo_corrida(ref["corrida"], int(ref["semente"])) if ref.get("demo") else por_id(listar_corrida(ref["corrida"], banco)).get(ref["id"])
        if c is None:
            raise TB.ErroTrader("O cenário desta partida não está mais disponível.")
    elif ref.get("demo"):
        c = demo_cenario(ref["tf"], int(ref["semente"]), b24=str(ref.get("id", "")).endswith(SUFIXO_B24))
    else:
        c = por_id(listar(ref["tf"], banco)).get(ref["id"])
        if c is None:
            raise TB.ErroTrader("O cenário desta partida não está mais disponível.")
    if len(_CACHE_CEN) > 64:
        _CACHE_CEN.clear()
    _CACHE_CEN[chave] = c
    return c


# ------------------------------------------------------------------ PARTIDA CORRIDA (rápida = 5 min · intermediária = 1 h · longa = 1 dia)
CHAVE_CORRIDA = "tb_corrida_{formato}"
PERIODO_CORRIDA = {"5m": "60d", "1h": "2y", "1d": "10y"}          # o máximo gratuito de cada intervalo
INTERVALO_YAHOO = {"5m": "5m", "1h": "60m", "1d": "1d"}
MAX_DIAS_CORRIDA = {"rapida": 14, "intermediaria": 120, "longa": 900}   # dias corridos máximos do cenário inteiro (feriados e fins de semana inclusos)


def _spec(formato: str) -> dict:
    sp = TB.CORRIDAS.get(formato)
    if not sp:
        raise TB.ErroTrader("formato de partida inválido")
    return sp


def listar_corrida(formato: str, banco=None) -> list[dict]:
    try:
        dados = _banco(banco).cfg_ler(CHAVE_CORRIDA.format(formato=formato))
    except Exception:
        return []
    return [c for c in ((dados or {}).get("cenarios") or []) if TB.validar_cenario(c)[0] and not c.get("demo") and c.get("corrida") == formato]


def salvar_corrida(formato: str, cenarios: list[dict], banco=None) -> int:
    ok = [c for c in cenarios if TB.validar_cenario(c)[0] and not c.get("demo") and c.get("corrida") == formato]
    ok = sorted(ok, key=lambda c: c["candles"][0]["t"])[-MAX_POR_FUSO:]
    _banco(banco).cfg_gravar(CHAVE_CORRIDA.format(formato=formato), {"v": 1, "formato": formato, "cenarios": ok})
    return len(ok)


def janelas_corrida(df, formato: str, max_n: int = 3) -> list[tuple[int, int]]:
    """Trechos [i, j) completos para a partida corrida: no intraday, sem candle faltando dentro do pregão; volume quase sempre presente."""
    sp = _spec(formato)
    cfg = TB.TIMEFRAMES[sp["tf"]]
    n = sp["n_analise"] + sp["n_replay"]
    passo = timedelta(minutes=cfg["passo_min"])
    idx = list(df.index)
    if len(idx) < n:
        return []
    intraday = cfg["passo_min"] < 1440
    bom = [not (intraday and idx[k].date() == idx[k + 1].date() and idx[k + 1] - idx[k] != passo) for k in range(len(idx) - 1)]
    cand = []
    for i in range(0, len(idx) - n + 1):
        if not all(bom[i:i + n - 1]):
            continue
        if (idx[i + n - 1] - idx[i]) > timedelta(days=MAX_DIAS_CORRIDA[formato]):
            continue
        vol = df["Volume"].iloc[i:i + n]
        if (vol.fillna(0) <= 0).mean() > 0.05:
            continue
        cand.append((i, i + n))
    escolhidas, ult = [], None
    for i, j in cand[::-1]:                                   # do mais recente para trás, sem sobreposição
        if ult is None or i + n <= ult:
            escolhidas.append((i, j))
            ult = i
        if len(escolhidas) >= max_n:
            break
    return escolhidas


def cenario_corrida_de_df(df, i: int, j: int, ticker: str, formato: str, agora_iso: str) -> dict:
    sp = _spec(formato)
    sub = df.iloc[i:j]
    cand = [{"t": t.isoformat(timespec="minutes"), "o": round(float(r.Open), 4), "h": round(float(r.High), 4), "l": round(float(r.Low), 4),
             "c": round(float(r.Close), 4), "v": float(r.Volume)} for t, r in sub.iterrows()]
    return {"id": f"{ticker}-{sp['tf']}-{cand[0]['t'].replace('-', '').replace(':', '').replace('T', '')}-c{formato}", "ticker": ticker, "nome": ticker,
            "tf": sp["tf"], "corrida": formato, "fonte": FONTE_REAL, "demo": False, "preparado_em": agora_iso, "n_analise": sp["n_analise"], "candles": cand}


def preparar_corrida(formato: str, baixar, agora_iso: str, ativos=ATIVOS, por_ativo: int = 3, banco=None) -> dict:
    """Baixa o histórico de cada ativo UMA vez no tempo gráfico do formato, valida e guarda os cenários novos. `baixar(codigo, periodo, intervalo_yahoo)`."""
    import analise_tecnica as AT
    sp = _spec(formato)
    tf = sp["tf"]
    atuais = {c["id"]: c for c in listar_corrida(formato, banco)}
    rel = {"novos": 0, "total": 0, "falhas": {}}
    for cod in ativos:
        try:
            r = baixar(cod, PERIODO_CORRIDA[tf], INTERVALO_YAHOO[tf])
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
        achou = 0
        for i, j in janelas_corrida(df, formato, por_ativo):
            c = cenario_corrida_de_df(df, i, j, cod, formato, agora_iso)
            if TB.validar_cenario(c)[0] and c["id"] not in atuais:
                atuais[c["id"]] = c
                rel["novos"] += 1
            achou += 1
        if not achou:
            rel["falhas"][cod] = "nenhum trecho completo (faltam candles no período gratuito)"
    rel["total"] = salvar_corrida(formato, list(atuais.values()), banco)
    return rel


def demo_corrida(formato: str, semente: int) -> dict:
    """Cenário SIMULADO da partida corrida (sempre rotulado como demonstração)."""
    sp = _spec(formato)
    cfg = TB.TIMEFRAMES[sp["tf"]]
    rng = random.Random(semente)
    n = sp["n_analise"] + sp["n_replay"]
    p = 20.0 + rng.random() * 30
    base_vol = {"5m": 0.0018, "1h": 0.004, "1d": 0.014}[sp["tf"]]
    vol = base_vol
    t = datetime(2024, 3, 4, 10, 0)
    cand = []
    for k in range(n):
        vol = max(base_vol / 2, min(base_vol * 2.5, 0.9 * vol + 0.1 * base_vol + 0.3 * base_vol * rng.random()))
        drift = 0.15 * base_vol * math.sin(k / 23.0 + semente)
        o = p
        c = max(1.0, o * (1 + drift + rng.gauss(0, vol)))
        h = max(o, c) * (1 + abs(rng.gauss(0, vol / 2)))
        l = min(o, c) * (1 - abs(rng.gauss(0, vol / 2)))
        cand.append({"t": t.isoformat(timespec="minutes"), "o": round(o, 2), "h": round(h, 2), "l": round(l, 2), "c": round(c, 2),
                     "v": float(int(80000 + rng.random() * 220000))})
        p = c
        if cfg["passo_min"] >= 1440:
            t += timedelta(days=1)
            while t.weekday() >= 5:
                t += timedelta(days=1)
        else:
            t += timedelta(minutes=cfg["passo_min"])
            if t.hour >= 17 and (t.hour > 17 or t.minute > 55):
                t = (t + timedelta(days=1)).replace(hour=10, minute=0)
                while t.weekday() >= 5:
                    t += timedelta(days=1)
    return {"id": f"DEMO-{sp['tf']}-{semente}-c{formato}", "ticker": "DEMO3", "nome": "Cenário simulado", "tf": sp["tf"], "corrida": formato, "demo": True,
            "fonte": "Dados SIMULADOS (modo demonstração)", "n_analise": sp["n_analise"], "candles": cand}


def escolher_corrida(formato: str, semente: int, banco=None) -> dict:
    reais = listar_corrida(formato, banco)
    return random.Random(semente).choice(reais) if reais else demo_corrida(formato, semente)


def referencia_corrida(c: dict, semente: int) -> dict:
    return {**referencia(c, semente), "corrida": c.get("corrida")}
