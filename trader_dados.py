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
ATIVOS = ("PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "BBAS3", "ITSA4", "RENT3", "SUZB3", "GGBR4", "PRIO3", "LREN3", "AXIA3", "RADL3", "EQTL3")
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
        c = demo_corrida(ref["corrida"], int(ref["semente"])) if ref.get("demo") else carregar_corrida(ref["corrida"], ref["id"], banco)
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


# ------------------------------------------------------------------ PARTIDA CORRIDA (rápida = 15 min · intermediária = 1 h · longa = 1 dia)
# Cada cenário guarda: o histórico (n_analise candles do tempo gráfico da partida) + o replay em candles MENORES reais (5 min ou 1 h), com
# `grupo` (a que candle do gráfico cada passo pertence) e `velas_t` (horário de início de cada candle do gráfico). Nada é inventado: trecho com
# qualquer candle menor faltando fica de fora.
# Armazenamento: um registro por cenário (`tb_cc|<formato>|<id>`) e um índice pequeno por formato (`tb_corrida_<formato>`), para a biblioteca
# crescer todo dia (o workflow trader_cenarios_job.py prepara depois do pregão) sem um registro gigante.
CHAVE_CORRIDA = "tb_corrida_{formato}"
CHAVE_CEN_CORRIDA = "tb_cc|{formato}|{id}"
MAX_CORRIDA = 1500                                                  # teto de cenários guardados por duração (os mais antigos saem)
PERIODO_CORRIDA = {"5m": "60d", "15m": "60d", "1h": "2y", "1d": "10y"}   # o máximo gratuito de cada intervalo no Yahoo
INTERVALO_YAHOO = {"5m": "5m", "15m": "15m", "1h": "60m", "1d": "1d"}
PASSO_MIN = {"5m": 5, "15m": 15, "1h": 60, "1d": 1440}
MAX_DIAS_HIST = {"rapida": 40, "intermediaria": 150, "longa": 900}   # dias corridos máximos do histórico (feriados e fins de semana inclusos)


def _spec(formato: str) -> dict:
    sp = TB.CORRIDAS.get(formato)
    if not sp:
        raise TB.ErroTrader("formato de partida inválido")
    return sp


def _indice(formato: str, banco=None) -> list[dict]:
    try:
        dados = _banco(banco).cfg_ler(CHAVE_CORRIDA.format(formato=formato))
    except Exception:
        return []
    if (dados or {}).get("v") != 2:                                  # índice antigo (cenários sem passos): não serve mais
        return []
    return list(dados.get("itens") or [])


def listar_corrida(formato: str, banco=None) -> list[dict]:
    """Índice dos cenários reais guardados (id, ativo e período do replay). O cenário inteiro só é lido na hora de jogar (`carregar_corrida`)."""
    return [x for x in _indice(formato, banco) if x.get("id")]


def carregar_corrida(formato: str, cid: str, banco=None) -> dict | None:
    try:
        c = _banco(banco).cfg_ler(CHAVE_CEN_CORRIDA.format(formato=formato, id=cid))
    except Exception:
        return None
    if not c or not TB.validar_cenario(c)[0] or c.get("demo") or c.get("corrida") != formato:
        return None
    return c


def _item(c: dict) -> dict:
    vt = c["velas_t"]
    return {"id": c["id"], "ticker": c["ticker"], "de": vt[0], "ate": vt[-1]}


def salvar_corrida(formato: str, cenarios: list[dict], banco=None) -> int:
    """Grava os cenários novos (cada um no seu registro) e atualiza o índice. Devolve o total guardado."""
    b = _banco(banco)
    itens = {x["id"]: x for x in _indice(formato, b)}
    for c in cenarios:
        if not TB.validar_cenario(c)[0] or c.get("demo") or c.get("corrida") != formato or c["id"] in itens:
            continue
        b.cfg_gravar(CHAVE_CEN_CORRIDA.format(formato=formato, id=c["id"]), c)
        itens[c["id"]] = _item(c)
    ordem = sorted(itens.values(), key=lambda x: x["de"])
    for velho in ordem[:-MAX_CORRIDA]:
        try:
            b.cfg_apagar(CHAVE_CEN_CORRIDA.format(formato=formato, id=velho["id"]))
        except Exception:
            pass
    ordem = ordem[-MAX_CORRIDA:]
    b.cfg_gravar(CHAVE_CORRIDA.format(formato=formato), {"v": 2, "formato": formato, "itens": ordem})
    return len(ordem)


def _chave_vela(t, tf: str):
    """Início do candle do gráfico a que o candle menor de horário `t` pertence."""
    if tf == "1d":
        return t.normalize()
    m = PASSO_MIN[tf]
    return t.floor(f"{m}min")


def _velas_completas(sub, tf: str, sub_tf: str, vela=None) -> list[tuple]:
    """Agrupa os candles menores (DataFrame) por candle do gráfico. Devolve [(início, posições dos menores)] só com grupos sem buraco: dentro de cada
    pregão os menores vêm em sequência exata (5 min a 5 min, ou 1 h a 1 h), e no intraday o grupo não pode pular um horário do candle do gráfico."""
    from datetime import timedelta as _td
    idx = list(sub.index)
    passo = _td(minutes=PASSO_MIN[sub_tf])
    grupos, atual, chave_ant = [], None, None
    for pos, t in enumerate(idx):
        ch = _chave_vela(t, tf)
        if ch != chave_ant:
            atual = [ch, [pos], True]
            grupos.append(atual)
            chave_ant = ch
        else:
            if t - idx[atual[1][-1]] != passo:
                atual[2] = False                                  # buraco dentro do candle: o grupo inteiro fica de fora
            atual[1].append(pos)
    out = []
    for ch, poss, ok in grupos:
        if tf != "1d" and idx[poss[0]] != ch and (idx[poss[0]] - ch) >= passo:   # o 1º menor tem que abrir o candle do gráfico
            ok = False
        if not ok and not _igual_ao_real(sub, poss, vela, ch):
            out.append(None)
            continue
        out.append((ch, poss))
    return out


TOL_REAL = 0.0005          # 0,05% (≈ 1 centavo numa ação de R$ 20-30): diferença de arredondamento entre as séries do Yahoo


def _igual_ao_real(sub, poss: list[int], vela, ch) -> bool:
    """Grupo com candle menor faltando só vale se a soma dos menores que vieram for IGUAL ao candle real do gráfico (abertura, máxima, mínima e
    fechamento do Yahoo): aí o candle mostrado é exatamente o real e só a formação pula aqueles minutos. Nada é inventado."""
    if vela is None or ch not in vela.index:
        return False
    r = vela.loc[ch]
    if hasattr(r, "ndim") and r.ndim > 1:
        r = r.iloc[-1]
    g = sub.iloc[poss]
    agg = (float(g["Open"].iloc[0]), float(g["High"].max()), float(g["Low"].min()), float(g["Close"].iloc[-1]))
    real = (float(r["Open"]), float(r["High"]), float(r["Low"]), float(r["Close"]))
    return all(abs(a - b) <= TOL_REAL * b for a, b in zip(agg, real))


def _hist_ok(hist, tf: str) -> bool:
    """Histórico do tempo gráfico da partida: sem buraco dentro do pregão (intraday) e volume quase sempre presente."""
    from datetime import timedelta as _td
    idx = list(hist.index)
    if tf != "1d":
        passo = _td(minutes=PASSO_MIN[tf])
        for a, b in zip(idx, idx[1:]):
            if a.date() == b.date() and b - a != passo:
                return False
    vol = hist["Volume"]
    return (vol.fillna(0) <= 0).mean() <= 0.05


def montar_corridas(df_vela, df_sub, formato: str, ticker: str, agora_iso: str, max_n: int = 3, ocupados: list[tuple[str, str]] | None = None,
                    motivos: dict | None = None) -> list[dict]:
    """Cenários completos de um ativo: replay de n_replay candles do gráfico formados pelos candles menores reais (cada pregão começa um trecho),
    com os n_analise candles do gráfico imediatamente anteriores como histórico. Do mais recente para trás, sem sobrepor os já guardados."""
    from datetime import timedelta as _td
    sp = _spec(formato)
    tf, sub_tf, nr, na = sp["tf"], sp["sub"], sp["n_replay"], sp["n_analise"]
    grupos = _velas_completas(df_sub, tf, sub_tf, df_vela)
    ocup = [(a, b) for a, b in (ocupados or [])]
    out = []
    mot = motivos if motivos is not None else {}

    def _n(m):
        mot[m] = mot.get(m, 0) + 1
    mot["candles_menores_incompletos"] = sum(1 for g in grupos if g is None)
    mot["candles_do_grafico"] = len(grupos)
    inicios = [k for k, g in enumerate(grupos) if g and (k == 0 or not grupos[k - 1] or grupos[k - 1][0].date() != g[0].date())]
    for k in reversed(inicios):                                     # cada trecho começa na abertura de um pregão
        bloco = grupos[k:k + nr]
        if len(bloco) < nr:
            _n("pouco_replay")
            continue
        if any(g is None for g in bloco):
            _n("candle_menor_faltando")
            continue
        if tf != "1d" and any((b[0] - a[0]) != _td(minutes=PASSO_MIN[tf]) and a[0].date() == b[0].date() for a, b in zip(bloco, bloco[1:])):
            _n("pulou_hora_no_pregao")
            continue                                                # pulou um candle do gráfico dentro do pregão
        de, ate = bloco[0][0].isoformat(timespec="minutes"), bloco[-1][0].isoformat(timespec="minutes")
        if any(not (ate < a or de > b) for a, b in ocup):
            _n("sobrepoe")
            continue                                                # sobrepõe um trecho já guardado (ou já escolhido agora)
        hist = df_vela[df_vela.index < bloco[0][0]].tail(na)
        if len(hist) < na:
            _n("historico_curto")
            continue
        if not _hist_ok(hist, tf):
            _n("historico_sem_volume" if _hist_ok(hist.assign(Volume=1.0), tf) else "historico_com_buraco")
            continue
        if (bloco[0][0] - hist.index[0]) > _td(days=MAX_DIAS_HIST[formato] + nr * (1 if tf == "1d" else 0)):
            _n("historico_longo_demais")
            continue
        if (bloco[0][0] - hist.index[-1]) > _td(days=5):            # histórico encostado no replay (no máximo um feriado prolongado)
            _n("historico_longe_do_replay")
            continue
        poss = [p for _ch, ps in bloco for p in ps]
        rep = df_sub.iloc[poss]
        if (rep["Volume"].fillna(0) <= 0).mean() > 0.05:
            _n("replay_sem_volume")
            continue
        def _k(t, r):
            return {"t": t.isoformat(timespec="minutes"), "o": round(float(r.Open), 4), "h": round(float(r.High), 4), "l": round(float(r.Low), 4),
                    "c": round(float(r.Close), 4), "v": float(r.Volume if r.Volume == r.Volume else 0.0)}
        cand = [_k(t, r) for t, r in hist.iterrows()] + [_k(t, r) for t, r in rep.iterrows()]
        grupo = [n for n, (_ch, ps) in enumerate(bloco) for _ in ps]
        c = {"id": f"{ticker}-{tf}-{de.replace('-', '').replace(':', '').replace('T', '')}-d{formato}", "ticker": ticker, "nome": ticker, "tf": tf,
             "corrida": formato, "sub": sub_tf, "fonte": FONTE_REAL, "demo": False, "preparado_em": agora_iso, "n_analise": na, "candles": cand,
             "grupo": grupo, "velas_t": [g[0].isoformat(timespec="minutes") for g in bloco]}
        ok, why = TB.validar_cenario(c)
        if not ok:
            _n("invalido: " + why)
            continue
        out.append(c)
        ocup.append((de, ate))
        if len(out) >= max_n:
            break
    return out


def preparar_corrida(formato: str, baixar, agora_iso: str, ativos=ATIVOS, por_ativo: int = 3, banco=None) -> dict:
    """Baixa, de cada ativo, o tempo gráfico da partida (histórico) e os candles menores (replay), monta os trechos completos e guarda os novos.
    `baixar(codigo, periodo, intervalo_yahoo)` devolve {'df'} ou {'erro'}. Rodar todo dia faz a biblioteca crescer (os dados antigos ficam guardados)."""
    import analise_tecnica as AT
    sp = _spec(formato)
    tf, sub_tf = sp["tf"], sp["sub"]
    guardados = listar_corrida(formato, banco)
    rel = {"novos": 0, "total": len(guardados), "falhas": {}}
    novos = []

    def _df(cod, t):
        r = baixar(cod, PERIODO_CORRIDA[t], INTERVALO_YAHOO[t])
        if not r or r.get("erro") or r.get("df") is None:
            raise ValueError(str((r or {}).get("erro") or "sem dados"))
        df, info = AT.limpar_ohlcv(r["df"])
        if not info.get("tem_ohlc") or "Volume" not in df.columns:
            raise ValueError("histórico sem OHLC/volume completos")
        return df
    for cod in ativos:
        try:
            dv, ds = _df(cod, tf), _df(cod, sub_tf)
        except Exception as e:
            rel["falhas"][cod] = str(e)[:120] or e.__class__.__name__
            continue
        ocup = [(x["de"], x["ate"]) for x in guardados if x.get("ticker") == cod]
        cs = montar_corridas(dv, ds, formato, cod, agora_iso, por_ativo, ocup)
        if not cs:
            rel["falhas"][cod] = "nenhum trecho novo completo (faltam candles menores no período gratuito)"
        novos += cs
    rel["novos"] = len(novos)
    rel["total"] = salvar_corrida(formato, novos, banco) if novos else len(guardados)
    return rel


def demo_corrida(formato: str, semente: int) -> dict:
    """Cenário SIMULADO da partida corrida (sempre rotulado como demonstração). Só para testes e para o administrador: partida de verdade
    nunca usa gráfico simulado. Mesmo formato dos reais: histórico + passos menores agrupados nos candles do gráfico."""
    sp = _spec(formato)
    tf, k = sp["tf"], sp["k"]
    rng = random.Random(semente)
    p = 20.0 + rng.random() * 30
    base_vol = {"15m": 0.003, "1h": 0.004, "1d": 0.014}[tf]

    def vela(o, vol):
        c = max(1.0, o * (1 + rng.gauss(0, vol)))
        h = max(o, c) * (1 + abs(rng.gauss(0, vol / 2)))
        l = min(o, c) * (1 - abs(rng.gauss(0, vol / 2)))
        return round(o, 2), round(h, 2), round(l, 2), round(c, 2)
    t = datetime(2024, 3, 4, 10, 0)
    passo = timedelta(minutes=TB.TIMEFRAMES[tf]["passo_min"]) if tf != "1d" else timedelta(days=1)

    def prox(t):
        if tf == "1d":
            t += timedelta(days=1)
        else:
            t += passo
            if t.hour >= 17:
                t = (t + timedelta(days=1)).replace(hour=10, minute=0)
        while t.weekday() >= 5:
            t += timedelta(days=1)
        return t
    cand = []
    for _ in range(sp["n_analise"]):
        o, h, l, c = vela(p, base_vol)
        cand.append({"t": t.isoformat(timespec="minutes"), "o": o, "h": h, "l": l, "c": c, "v": float(int(80000 + rng.random() * 220000))})
        p, t = c, prox(t)
    grupo, velas_t = [], []
    sub_min = TB.TIMEFRAMES.get(sp["sub"], {}).get("passo_min", 5 if sp["sub"] == "5m" else 60)
    for g in range(sp["n_replay"]):
        velas_t.append(t.isoformat(timespec="minutes"))
        ts = t.replace(hour=10) if tf == "1d" else t
        for _ in range(k):
            o, h, l, c = vela(p, base_vol / math.sqrt(k))
            cand.append({"t": ts.isoformat(timespec="minutes"), "o": o, "h": h, "l": l, "c": c, "v": float(int(8000 + rng.random() * 22000))})
            grupo.append(g)
            p, ts = c, ts + timedelta(minutes=sub_min)
        t = prox(t)
    return {"id": f"DEMO-{tf}-{semente}-d{formato}", "ticker": "DEMO3", "nome": "Cenário simulado", "tf": tf, "corrida": formato, "sub": sp["sub"], "demo": True,
            "fonte": "Dados SIMULADOS (modo demonstração)", "n_analise": sp["n_analise"], "candles": cand, "grupo": grupo, "velas_t": velas_t}


def escolher_corrida(formato: str, semente: int, banco=None, permitir_demo: bool = False) -> dict:
    """Sorteia um cenário REAL guardado. Sem nenhum, a partida não começa (só testes/administração pedem o simulado com `permitir_demo`)."""
    itens = listar_corrida(formato, banco)
    rng = random.Random(semente)
    for x in rng.sample(itens, len(itens)):
        c = carregar_corrida(formato, x["id"], banco)
        if c:
            return c
    if permitir_demo:
        return demo_corrida(formato, semente)
    raise SemCenarios("Os gráficos reais desta duração ainda estão sendo preparados. Tente outra duração ou volte mais tarde.")


class SemCenarios(TB.ErroTrader):
    """Nenhum gráfico real guardado para a duração escolhida."""


def referencia_corrida(c: dict, semente: int) -> dict:
    return {**referencia(c, semente), "corrida": c.get("corrida")}
