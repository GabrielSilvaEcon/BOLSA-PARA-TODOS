"""Etapa 2 · Controle central de consumo das APIs (contador, limites configuráveis e proteção contra esgotamento).

Como funciona
 · Todo pedido feito com `requests` já passa pela proteção de rede (http_seguro). Ali ele chama `antes(url)`, que descobre o
   provedor pelo domínio, CONTA o pedido e, se o administrador mandou bloquear aquele provedor e o limite estourou (ou ele está
   suspenso), recusa o pedido ANTES de gastar a cota.
 · Yahoo (yfinance) não usa `requests`: os pontos de chamada em dados.py chamam `contar("yahoo")`.
 · Padrão seguro: modo "avisar" (só conta). Bloquear é uma escolha do administrador, por provedor.
 · Contagem por dia no banco (tabela config_sistema; sem ela, segue só em memória). O app e o monitor (GitHub Actions) somam na mesma
   contagem. Gravação a cada 20 pedidos ou 60 s; se o banco falhar, segue só em memória.
Etapa 6 (proteção contra esgotamento):
 · Modo "proteger" (padrão para fontes com limite): chamadas de BAIXA prioridade (aquecimento do monitor) param ao chegar na
   reserva (padrão 70% do limite), guardando o resto para quem está usando o app; todas param ao chegar em 100%.
 · Disjuntor: se uma fonte falha muitas vezes seguidas (ou devolve 429), é pausada por alguns minutos para todos; o app usa a fonte
   reserva ou o último dado guardado (cache central) em vez de insistir e ser bloqueado.
 · Suspender vale em qualquer modo. O administrador é avisado (notificação na Central) quando uma fonte passa de 80% e de 100%.
Limites conhecidos: a soma entre processos não é atômica (dois processos gravando juntos podem perder poucos pedidos); a contagem
é de PEDIDOS, enquanto alguns provedores medem em "créditos" (ex.: CoinGecko); limites de uso por minuto valem por processo.
"""
from __future__ import annotations

import contextlib
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

_lock = threading.RLock()                 # reentrante: a checagem de limite e o incremento acontecem juntos, sem corrida
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
RESERVA_PADRAO = 70            # % do limite a partir do qual só o uso normal passa (o aquecimento para)
CIRCUITO_PADRAO = {"falhas": 6, "janela_s": 300, "pausa_min": 10}
_cfg_chaves = ("limites", "modo", "suspenso", "reserva_pct", "circuito")


def _cfg_padrao() -> dict:
    return {"limites": {}, "modo": {}, "suspenso": [], "reserva_pct": RESERVA_PADRAO, "circuito": dict(CIRCUITO_PADRAO)}


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
        cfg["circuito"] = {**CIRCUITO_PADRAO, **(cfg["circuito"] or {})}
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
        if pid in PROVEDORES and m in ("avisar", "proteger", "bloquear"):
            limpo["modo"][pid] = m
    limpo["suspenso"] = [p for p in (cfg.get("suspenso") or []) if p in PROVEDORES]
    limpo["reserva_pct"] = max(10, min(100, int(cfg.get("reserva_pct", RESERVA_PADRAO) or RESERVA_PADRAO)))
    c = cfg.get("circuito") or {}
    limpo["circuito"] = {"falhas": max(2, min(50, int(c.get("falhas", CIRCUITO_PADRAO["falhas"])))),
                         "janela_s": CIRCUITO_PADRAO["janela_s"],
                         "pausa_min": max(1, min(240, int(c.get("pausa_min", CIRCUITO_PADRAO["pausa_min"]))))}
    import banco
    banco.cfg_gravar(CH_CFG, limpo)
    _est["cfg"], _est["cfg_t"] = limpo, time.time()


def limites(pid: str) -> dict:
    """Limite efetivo: o do administrador, senão o padrão do catálogo."""
    base = dict(PROVEDORES[pid][3])
    base.update(config()["limites"].get(pid) or {})
    return base


def modo(pid: str) -> str:
    """Modo do provedor: o escolhido pelo administrador; senão 'proteger' se há limite conhecido, 'avisar' se não há."""
    m = config()["modo"].get(pid)
    if m in ("avisar", "proteger", "bloquear"):
        return m
    return "proteger" if limites(pid) else "avisar"


# ---------------------------------------------------------------- prioridade da chamada e disjuntor
_ctx = threading.local()


@contextlib.contextmanager
def baixa_prioridade():
    """Dentro deste bloco, o pedido é 'não essencial' (ex.: aquecimento do cache): para antes, na reserva."""
    antes_ = getattr(_ctx, "baixa", False)
    _ctx.baixa = True
    try:
        yield
    finally:
        _ctx.baixa = antes_


def _eh_baixa() -> bool:
    return bool(getattr(_ctx, "baixa", False))


_circ: dict[str, dict] = {}


def falha(pid: str, peso: int = 1) -> None:
    """Registra falha da fonte (erro de rede, 429, bloqueio). Muitas seguidas abrem o disjuntor (pausa para todos)."""
    try:
        if pid not in PROVEDORES:
            return
        c = config()["circuito"]
        agora = time.time()
        with _lock:
            e = _circ.setdefault(pid, {"falhas": [], "aberto_ate": 0.0, "vezes": 0})
            e["falhas"] = [t for t in e["falhas"] if agora - t < c["janela_s"]] + [agora] * max(1, peso)
            if len(e["falhas"]) >= c["falhas"] and agora >= e["aberto_ate"]:
                e["aberto_ate"] = agora + c["pausa_min"] * 60
                e["vezes"] += 1
                e["falhas"] = []
    except Exception:
        pass


def sucesso(pid: str) -> None:
    with _lock:
        e = _circ.get(pid)
        if e:
            e["falhas"] = []


def circuito_aberto_ate(pid: str) -> float:
    e = _circ.get(pid)
    return e["aberto_ate"] if e and e["aberto_ate"] > time.time() else 0.0


def fechar_circuito(pid: str) -> None:
    with _lock:
        _circ.pop(pid, None)


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
        por_mes: dict[str, dict[str, int]] = {}
        for dia, mudancas in por_dia.items():
            for pid, n in mudancas.items():
                por_mes.setdefault(dia[:7], {})[pid] = por_mes.get(dia[:7], {}).get(pid, 0) + n
        for mes, mudancas in por_mes.items():          # total do mês num único registro (leitura barata)
            mdoc = banco.cfg_ler(f"uso_mes|{mes}")
            if not mdoc:
                mdoc = _soma_dias(mes)
            else:
                for pid, n in mudancas.items():
                    mdoc[pid] = int(mdoc.get(pid, 0)) + n
            banco.cfg_gravar(f"uso_mes|{mes}", mdoc)
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


def _soma_dias(mes: str) -> dict:
    tot: dict[str, int] = {}
    for d in range(1, 32):
        for pid, n in _carregar_dia(f"{mes}-{d:02d}").items():
            tot[pid] = tot.get(pid, 0) + int(n)
    return tot


def usos_do_mes(mes: str | None = None) -> dict:
    """Total do mês 'AAAA-MM': um registro só (mais o que este processo ainda não gravou). Meses antigos sem registro somam os dias."""
    mes = mes or _hoje()[:7]
    try:
        import banco
        tot = {k: int(v) for k, v in (banco.cfg_ler(f"uso_mes|{mes}") or {}).items()}
    except Exception:
        tot = {}
    if not tot:
        tot = _soma_dias(mes)
    with _lock:
        for (pid, d), n in _delta.items():
            if d.startswith(mes):
                tot[pid] = tot.get(pid, 0) + n
    return tot


def _sabido(pid: str, dia: str) -> int:
    """Contagem do dia que este processo conhece (lê o banco uma vez por dia e provedor)."""
    k = (pid, dia)
    if k not in _est["carregado"]:
        _est["carregado"].add(k)
        _total[k] = int(_carregar_dia(dia).get(pid, 0))
    return _total.get(k, 0)


def _razao(pid: str, dia: str) -> tuple[float, str]:
    """Maior fração usada entre os limites do provedor (1.0 = 100%) e qual limite é."""
    lim = limites(pid)
    melhor, qual = 0.0, ""
    if lim.get("min"):
        j = _janela.setdefault(pid, deque())
        agora = time.time()
        while j and agora - j[0] > 60:
            j.popleft()
        r = len(j) / lim["min"]
        if r > melhor:
            melhor, qual = r, "limite por minuto"
    if lim.get("dia"):
        r = _sabido(pid, dia) / lim["dia"]
        if r > melhor:
            melhor, qual = r, "limite diário"
    if lim.get("mes"):
        if time.time() - _est.get("mes_t_" + pid, 0.0) > 300:      # soma do mês: relida a cada 5 min
            _est["mes_t_" + pid] = time.time()
            _est["mes_v_" + pid] = usos_do_mes().get(pid, 0)
        r = _est.get("mes_v_" + pid, 0) / lim["mes"]
        if r > melhor:
            melhor, qual = r, "limite mensal"
    return melhor, qual


def _estourou(pid: str, dia: str) -> str:
    r, q = _razao(pid, dia)
    return q if r >= 1 else ""


def contar(pid: str, n: int = 1) -> bool:
    """Conta `n` pedidos do provedor. True = pode seguir; False = barrado (suspenso, disjuntor, limite ou reserva). Nunca levanta erro."""
    try:
        if pid not in PROVEDORES:
            return True
        dia = _hoje()
        cfg = config()
        if pid in cfg["suspenso"] or circuito_aberto_ate(pid):
            return False
        m = modo(pid)
        with _lock:                                    # checar e contar juntos: sem isso, pedidos simultâneos passam do teto
            if m != "avisar" and limites(pid):
                r, _q = _razao(pid, dia)
                if r >= 1 or (m == "proteger" and _eh_baixa() and r >= cfg["reserva_pct"] / 100):
                    return False
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
    ate = circuito_aberto_ate(pid)
    if ate:
        return f"fonte pausada após falhas seguidas (volta em {max(1, int((ate - time.time()) // 60) + 1)} min)"
    r, q = _razao(pid, _hoje())
    if r >= 1:
        return q
    return f"reservado ao uso normal ({int(r * 100)}% do limite usado)" if _eh_baixa() else "limite atingido"


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


def depois(url: str, status: int | None = None, erro: bool = False) -> None:
    """Chamado após cada pedido: 429 pesa 3 falhas; 5xx/erro de rede pesa 1; resposta boa zera a contagem."""
    try:
        from urllib.parse import urlsplit
        pid = provedor_de(urlsplit(str(url)).hostname or "")
        if pid is None:
            return
        if status == 429:
            falha(pid, 3)
        elif erro or (status is not None and status >= 500):
            falha(pid)
        elif status is not None and status < 400:
            sucesso(pid)
    except Exception:
        pass


def avisos_de_cota(niveis=(0.8, 1.0)) -> list[dict]:
    """Provedores com limite que passaram de 80% / 100% (maior nível atingido). Para avisar o administrador."""
    dia, mes = usos_do_dia(), usos_do_mes()
    out = []
    for pid in PROVEDORES:
        lim = limites(pid)
        pct = max([dia.get(pid, 0) / lim[k] for k in ("dia",) if lim.get(k)] + [mes.get(pid, 0) / lim[k] for k in ("mes",) if lim.get(k)] + [0.0])
        nivel = max([n for n in niveis if pct >= n] or [0])
        if nivel:
            out.append({"id": pid, "nome": PROVEDORES[pid][0], "pct": round(pct * 100), "nivel": int(nivel * 100)})
    return out


def historico(dias: int = 14) -> dict:
    """{'AAAA-MM-DD': {provedor: pedidos}} dos últimos `dias` dias (um registro por dia; só para o painel)."""
    from datetime import datetime, timedelta, timezone
    base = datetime.now(timezone.utc)
    out = {}
    for i in range(dias - 1, -1, -1):
        d = (base - timedelta(days=i)).strftime("%Y-%m-%d")
        out[d] = usos_do_dia(d)
    return out


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
        pausa = circuito_aberto_ate(pid)
        sit = "suspenso" if suspenso else "pausado" if pausa else "erro" if pct >= 1 else "aviso" if pct >= 0.8 else "ok" if lim else "na"
        out.append({"id": pid, "nome": nome, "classes": classes, "dia": dia.get(pid, 0), "mes": mes.get(pid, 0), "limites": lim,
                    "modo": modo(pid), "pct": pct, "situacao": sit, "pausa_min": int(max(0, pausa - time.time()) // 60) + 1 if pausa else 0})
    return out
