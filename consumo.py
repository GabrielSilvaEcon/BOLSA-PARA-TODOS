"""Etapa 2 · Controle central de consumo das APIs (contador, limites configuráveis e proteção contra esgotamento).

Como funciona
 · Todo pedido feito com `requests` já passa pela proteção de rede (http_seguro). Ali ele chama `antes(url)`, que descobre o
   provedor pelo domínio, CONTA o pedido e, se o administrador mandou bloquear aquele provedor e o limite estourou (ou ele está
   suspenso), recusa o pedido ANTES de gastar a cota.
 · Yahoo (yfinance) não usa `requests`: os pontos de chamada em dados.py chamam `contar("yahoo")`.
 · Padrão seguro: modo "avisar" (só conta). Bloquear é uma escolha do administrador, por provedor.
 · Contagem por dia no banco (tabela config_sistema; sem ela, segue só em memória). O app e o monitor (GitHub Actions) somam na mesma
   contagem. Gravação a cada 20 pedidos ou 60 s; se o banco falhar, segue só em memória.
Limites conhecidos: a soma entre processos não é atômica (dois processos gravando juntos podem perder poucos pedidos); a contagem
é de PEDIDOS, enquanto alguns provedores medem em "créditos" (ex.: CoinGecko); limites de uso por minuto valem por processo.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from datetime import datetime, timezone

CH_USO, CH_CFG = "consumo", "consumo_cfg"
FLUSH_N, FLUSH_S = 20, 60

# id: (nome, domínios, classes, limites padrão {min, dia, mes} conforme o catálogo conferido em 2026-11-04; None = desconhecido)
PROVEDORES = {
    "yahoo": ("Yahoo Finance", ("yahoo.com",), "ações, ETFs, FIIs, câmbio", {}),
    "brapi": ("Brapi", ("brapi.dev",), "ações, FIIs, ETFs BR", {"mes": 15000}),
    "fundamentus": ("Fundamentus", ("fundamentus.com.br",), "ações e FIIs BR", {}),
    "fmp": ("Financial Modeling Prep", ("financialmodelingprep.com",), "ações EUA", {"dia": 250}),
    "coingecko": ("CoinGecko", ("coingecko.com",), "cripto", {"min": 100, "mes": 10000}),
    "coinmarketcap": ("CoinMarketCap", ("coinmarketcap.com",), "cripto", {"min": 50, "mes": 15000}),
    "binance": ("Binance (dados públicos)", ("binance.com", "binance.vision"), "cripto", {}),
    "defillama": ("DefiLlama", ("llama.fi", "defillama.com"), "cripto/DeFi", {}),
    "onchain": ("On-chain (mempool, Blockchair, Snapshot, Dune)", ("mempool.space", "blockchair.com", "blockchain.info", "snapshot.org", "dune.com"), "cripto", {}),
    "bcb": ("Banco Central", ("bcb.gov.br",), "macro, renda fixa", {}),
    "ibge_ipea": ("IBGE / Ipeadata", ("ibge.gov.br", "ipeadata.gov.br"), "macro", {}),
    "cvm": ("CVM", ("cvm.gov.br",), "fundos, FIIs", {}),
    "tesouro": ("Tesouro", ("tesourotransparente.gov.br", "tesouro.gov.br", "tesourodireto.com.br"), "renda fixa", {}),
    "noticias": ("Notícias (Google, Fed, BLS, SEC, BCE)", ("news.google.com", "federalreserve.gov", "bls.gov", "sec.gov", "ecb.europa.eu"), "todas", {}),
    "ia": ("IA (Gemini / Anthropic)", ("googleapis.com", "anthropic.com"), "todas", {}),
}

_lock = threading.Lock()
_delta: dict[tuple[str, str], int] = {}          # (provedor, dia) -> pedidos ainda não gravados
_total: dict[tuple[str, str], int] = {}          # conhecido neste processo (banco + novos)
_janela: dict[str, deque] = {}
_est = {"ultimo_flush": 0.0, "pendentes": 0, "cfg": None, "cfg_t": 0.0, "carregado": set()}


def _hoje() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def provedor_de(host: str) -> str | None:
    h = (host or "").lower().rstrip(".")
    for pid, (_n, doms, _c, _l) in PROVEDORES.items():
        if any(h == d or h.endswith("." + d) for d in doms):
            return pid
    return None


# ---------------------------------------------------------------- configuração do administrador
def _cfg_padrao() -> dict:
    return {"limites": {}, "modo": {}, "suspenso": []}


def config() -> dict:
    """{'limites': {id: {min, dia, mes}}, 'modo': {id: 'avisar'|'bloquear'}, 'suspenso': [ids]} (cache de 60 s)."""
    agora = time.time()
    if _est["cfg"] is not None and agora - _est["cfg_t"] < 60:
        return _est["cfg"]
    cfg = _cfg_padrao()
    try:
        import banco
        lido = banco.cfg_ler(CH_CFG) or {}
        for k in cfg:
            if k in lido:
                cfg[k] = lido[k]
    except Exception:
        pass
    _est["cfg"], _est["cfg_t"] = cfg, agora
    return cfg


def salvar_config(cfg: dict) -> None:
    limpo = _cfg_padrao()
    for pid, lim in (cfg.get("limites") or {}).items():
        if pid in PROVEDORES:
            limpo["limites"][pid] = {k: int(v) for k, v in (lim or {}).items() if k in ("min", "dia", "mes") and v not in (None, "", 0)}
    for pid, m in (cfg.get("modo") or {}).items():
        if pid in PROVEDORES and m in ("avisar", "bloquear"):
            limpo["modo"][pid] = m
    limpo["suspenso"] = [p for p in (cfg.get("suspenso") or []) if p in PROVEDORES]
    import banco
    banco.cfg_gravar(CH_CFG, limpo)
    _est["cfg"], _est["cfg_t"] = limpo, time.time()


def limites(pid: str) -> dict:
    """Limite efetivo: o do administrador, senão o padrão do catálogo."""
    base = dict(PROVEDORES[pid][3])
    base.update(config()["limites"].get(pid) or {})
    return base


def modo(pid: str) -> str:
    return config()["modo"].get(pid, "avisar")


# ---------------------------------------------------------------- contagem
def _carregar_dia(dia: str) -> dict:
    try:
        import banco
        return banco.cfg_ler(f"{CH_USO}|{dia}") or {}
    except Exception:
        return {}


def _flush(forcar: bool = False) -> None:
    with _lock:
        if not _delta:
            return
        if not forcar and _est["pendentes"] < FLUSH_N and time.time() - _est["ultimo_flush"] < FLUSH_S:
            return
        pend = dict(_delta)
        _delta.clear()
        _est["pendentes"] = 0
        _est["ultimo_flush"] = time.time()
    try:
        import banco
        por_dia: dict[str, dict[str, int]] = {}
        for (pid, dia), n in pend.items():
            por_dia.setdefault(dia, {})[pid] = n
        for dia, mudancas in por_dia.items():
            atual = _carregar_dia(dia)
            for pid, n in mudancas.items():
                atual[pid] = int(atual.get(pid, 0)) + n
            banco.cfg_gravar(f"{CH_USO}|{dia}", atual)
    except Exception:
        with _lock:                      # não perde a contagem: tenta de novo no próximo ciclo
            for k, n in pend.items():
                _delta[k] = _delta.get(k, 0) + n


def usos_do_dia(dia: str | None = None) -> dict:
    """{provedor: pedidos} do dia (banco + o que este processo ainda não gravou)."""
    dia = dia or _hoje()
    base = {k: int(v) for k, v in _carregar_dia(dia).items()}
    with _lock:
        for (pid, d), n in _delta.items():
            if d == dia:
                base[pid] = base.get(pid, 0) + n
    return base


def usos_do_mes(mes: str | None = None) -> dict:
    """Soma dos dias do mês 'AAAA-MM' (lê no máximo 31 chaves; use só no painel, não a cada pedido)."""
    mes = mes or _hoje()[:7]
    tot: dict[str, int] = {}
    hoje = int(_hoje()[8:10]) if mes == _hoje()[:7] else 31
    for d in range(1, hoje + 1):
        for pid, n in usos_do_dia(f"{mes}-{d:02d}").items():
            tot[pid] = tot.get(pid, 0) + int(n)
    return tot


def _sabido(pid: str, dia: str) -> int:
    """Contagem do dia que este processo conhece (lê o banco uma vez por dia e provedor)."""
    k = (pid, dia)
    if k not in _est["carregado"]:
        _est["carregado"].add(k)
        _total[k] = int(_carregar_dia(dia).get(pid, 0))
    return _total.get(k, 0)


def _estourou(pid: str, dia: str) -> str:
    lim = limites(pid)
    if lim.get("min"):
        j = _janela.setdefault(pid, deque())
        agora = time.time()
        while j and agora - j[0] > 60:
            j.popleft()
        if len(j) >= lim["min"]:
            return "limite por minuto"
    if lim.get("dia") and _sabido(pid, dia) >= lim["dia"]:
        return "limite diário"
    if lim.get("mes"):
        # o mês só é somado quando há limite mensal e o provedor está em modo bloquear (evita ler o banco a cada pedido)
        if modo(pid) == "bloquear":
            if time.time() - _est.get("mes_t_" + pid, 0.0) > 300:
                _est["mes_t_" + pid] = time.time()
                _est["mes_v_" + pid] = usos_do_mes().get(pid, 0)
            if _est.get("mes_v_" + pid, 0) >= lim["mes"]:
                return "limite mensal"
    return ""


def contar(pid: str, n: int = 1) -> bool:
    """Conta `n` pedidos do provedor. True = pode seguir; False = bloqueado pelo administrador. Nunca levanta erro."""
    try:
        if pid not in PROVEDORES:
            return True
        dia = _hoje()
        cfg = config()
        bloqueia = modo(pid) == "bloquear"
        if bloqueia:
            if pid in cfg["suspenso"] or _estourou(pid, dia):
                return False
        with _lock:
            _delta[(pid, dia)] = _delta.get((pid, dia), 0) + n
            _total[(pid, dia)] = _total.get((pid, dia), 0) + n
            _est["pendentes"] += n
            if "mes_v_" + pid in _est:                # mantém o total do mês em dia entre as releituras do banco
                _est["mes_v_" + pid] += n
            _janela.setdefault(pid, deque()).extend([time.time()] * n)
        _flush()
    except Exception:
        return True
    return True


def motivo_bloqueio(pid: str) -> str:
    if pid in config()["suspenso"]:
        return "provedor suspenso pelo administrador"
    return _estourou(pid, _hoje()) or "limite atingido"


def antes(url: str) -> tuple[bool, str]:
    """Chamado pela proteção de rede antes de cada pedido. (ok, motivo)."""
    try:
        from urllib.parse import urlsplit
        pid = provedor_de(urlsplit(str(url)).hostname or "")
        if pid is None:
            return True, ""
        if contar(pid):
            return True, ""
        return False, f"{PROVEDORES[pid][0]}: {motivo_bloqueio(pid)}"
    except Exception:
        return True, ""


def gravar_agora() -> None:
    _flush(True)


def resumo() -> list[dict]:
    """Para o painel: um item por provedor, com uso do dia/mês, limites e situação."""
    dia, mes = usos_do_dia(), usos_do_mes()
    out = []
    for pid, (nome, _d, classes, _l) in PROVEDORES.items():
        lim = limites(pid)
        pct = 0.0
        for chave, usado in (("dia", dia.get(pid, 0)), ("mes", mes.get(pid, 0))):
            if lim.get(chave):
                pct = max(pct, usado / lim[chave])
        suspenso = pid in config()["suspenso"]
        sit = "suspenso" if suspenso else "erro" if pct >= 1 else "aviso" if pct >= 0.8 else "ok" if lim else "na"
        out.append({"id": pid, "nome": nome, "classes": classes, "dia": dia.get(pid, 0), "mes": mes.get(pid, 0), "limites": lim,
                    "modo": modo(pid), "pct": pct, "situacao": sit})
    return out
