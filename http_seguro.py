"""Camada central de rede do app (Passo 22): vale para TODO pedido feito com a biblioteca `requests` (e, por ela, o ccxt,
o fundamentus e o sidrapy), sem precisar mexer em cada módulo.

O que ela garante em cada pedido, inclusive nos redirecionamentos:
  - só http/https, nas portas 80 e 443, sem usuário/senha embutidos na URL;
  - nunca chega a endereços internos (localhost, redes privadas, link-local/metadados de nuvem, 100.64/10), mesmo que o
    nome de domínio aponte para eles (proteção contra SSRF);
  - nunca desliga a verificação de certificado;
  - todo pedido tem tempo limite (30 s se o código não definiu) e respostas gigantes são recusadas;
  - lista de domínios conhecidos: domínio fora da lista é registrado (modo "avisar", padrão) ou recusado (modo "bloquear").
Limites conhecidos: a checagem de DNS acontece antes do pedido (um DNS malicioso poderia mudar de resposta no meio); pedidos
feitos por `httpx` (login Google) e `curl_cffi` (yfinance) não passam por aqui.
"""
from __future__ import annotations

import ipaddress
import socket
import threading
import time
from urllib.parse import urlsplit

DOMINIOS = (
    "yahoo.com", "finance.yahoo.com", "brapi.dev", "fundamentus.com.br", "financialmodelingprep.com",
    "cvm.gov.br", "bcb.gov.br", "ibge.gov.br", "ipeadata.gov.br", "tesourotransparente.gov.br", "tesouro.gov.br", "gov.br",
    "b3.com.br", "federalreserve.gov", "bls.gov", "sec.gov", "stlouisfed.org", "ecb.europa.eu",
    "llama.fi", "defillama.com", "binance.com", "binance.vision", "coinmarketcap.com", "coingecko.com", "mempool.space",
    "blockchair.com", "blockchain.info", "solana.com", "snapshot.org", "dune.com", "github.com", "githubusercontent.com",
    "googleapis.com", "google.com", "anthropic.com", "tradingview.com", "supabase.co",
)
PORTAS = {None, 80, 443}
LIMITE_BYTES = 60 * 1024 * 1024
TIMEOUT_PADRAO = 30

_lock = threading.Lock()
_estado = {"modo": "avisar", "extras": set(), "bloqueios": [], "hosts": {}, "instalado": False}
_dns: dict[str, tuple[float, tuple[str, ...]]] = {}
_DNS_TTL = 300


def configurar(modo: str | None = None, extras=()) -> None:
    """modo: 'avisar' (registra domínios desconhecidos) ou 'bloquear'. extras: domínios a mais permitidos (ex.: o do Supabase)."""
    with _lock:
        if modo in ("avisar", "bloquear"):
            _estado["modo"] = modo
        for d in extras or ():
            d = str(d or "").strip().lower().lstrip(".")
            if d:
                _estado["extras"].add(d)


def modo() -> str:
    return _estado["modo"]


def ip_proibido(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(ip.split("%")[0])
    except ValueError:
        return True
    if getattr(a, "ipv4_mapped", None):
        a = a.ipv4_mapped
    if (a.is_private or a.is_loopback or a.is_link_local or a.is_multicast or a.is_reserved or a.is_unspecified):
        return True
    return a in ipaddress.ip_network("100.64.0.0/10")


def _ips(host: str) -> tuple[str, ...]:
    agora = time.monotonic()
    c = _dns.get(host)
    if c and agora - c[0] < _DNS_TTL:
        return c[1]
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
        ips = tuple(sorted({i[4][0] for i in infos}))
    except OSError:
        ips = ()
    _dns[host] = (agora, ips)
    return ips


def dominio_permitido(host: str) -> bool:
    h = (host or "").lower().rstrip(".")
    base = DOMINIOS + tuple(_estado["extras"])
    return any(h == d or h.endswith("." + d) for d in base)


def verificar(url: str) -> tuple[bool, str]:
    """(ok, motivo). Rejeita o que é inseguro sempre; domínio desconhecido só rejeita no modo 'bloquear'."""
    try:
        p = urlsplit(str(url))
        host = (p.hostname or "").lower()
        porta = p.port
    except ValueError:
        return False, "endereço inválido"
    if p.scheme not in ("http", "https"):
        return False, "protocolo não permitido"
    if not host:
        return False, "endereço sem domínio"
    if p.username or p.password:
        return False, "endereço com usuário/senha embutidos"
    if porta not in PORTAS:
        return False, "porta não permitida"
    if host == "localhost" or host.endswith((".localhost", ".local", ".internal")):
        return False, "endereço interno"
    try:
        ipaddress.ip_address(host)
        if ip_proibido(host):
            return False, "endereço interno"
    except ValueError:
        ips = _ips(host)
        if ips and any(ip_proibido(i) for i in ips):
            return False, "o domínio aponta para um endereço interno"
    if not dominio_permitido(host):
        with _lock:
            _estado["hosts"][host] = _estado["hosts"].get(host, 0) + 1
        if _estado["modo"] == "bloquear":
            return False, "domínio fora da lista permitida"
    return True, ""


def _anotar(url: str, motivo: str) -> None:
    host = ""
    try:
        host = urlsplit(str(url)).hostname or ""
    except ValueError:
        pass
    with _lock:
        _estado["bloqueios"].append({"quando": time.time(), "host": host[:80], "motivo": motivo})
        del _estado["bloqueios"][:-200]


def bloqueios() -> list[dict]:
    with _lock:
        return list(_estado["bloqueios"])


def hosts_desconhecidos() -> dict[str, int]:
    with _lock:
        return dict(_estado["hosts"])


def instalar(requests_mod=None) -> bool:
    """Liga a proteção em todo pedido do `requests`. Seguro chamar várias vezes."""
    if _estado["instalado"]:
        return True
    try:
        import requests as rq
    except Exception:
        return False
    rq = requests_mod or rq
    original = rq.sessions.Session.send

    def send(self, request, **kw):
        ok, motivo = verificar(getattr(request, "url", ""))
        if not ok:
            _anotar(request.url, motivo)
            raise rq.exceptions.ConnectionError(f"Pedido bloqueado pela proteção de rede: {motivo}")
        if kw.get("timeout") is None:
            kw["timeout"] = TIMEOUT_PADRAO
        if kw.get("verify") is False:
            kw["verify"] = True
        resp = original(self, request, **kw)
        try:
            tam = int(resp.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            tam = 0
        if tam > LIMITE_BYTES:
            resp.close()
            _anotar(request.url, "resposta grande demais")
            raise rq.exceptions.ConnectionError("Resposta grande demais; pedido descartado")
        return resp
    send._bpt_seguro = True
    if not getattr(original, "_bpt_seguro", False):
        rq.sessions.Session.send = send
    _estado["instalado"] = True
    return True
