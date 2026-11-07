"""Foto das notícias. O feed do Google Notícias não traz imagem; por isso, para os cartões que vão aparecer, o app abre a matéria original
e lê a imagem de capa (meta og:image), que é o que os próprios sites oferecem para pré-visualização.

Regras de segurança: só https, só sites públicos (nunca endereço interno), páginas limitadas a 400 KB, tempo curto, e o resultado fica em
memória (6 h quando acha, 30 min quando não acha) para não repetir pedidos. Falha nunca derruba a página: o cartão fica sem foto.
Sem Streamlit neste módulo; a busca de rede pode ser trocada nos testes.
"""
from __future__ import annotations

import base64
import concurrent.futures as cf
import ipaddress
import re
import socket
import threading
import time
from urllib.parse import urljoin, urlparse

TTL_ACHOU = 6 * 3600
TTL_FALHOU = 30 * 60
MAX_BYTES = 400_000
MAX_CACHE = 600
UA = {"User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Mobile Safari/537.36",
      "Accept": "text/html,application/xhtml+xml", "Accept-Language": "pt-BR,pt;q=0.9"}

_LOCK = threading.Lock()
_CACHE: dict[str, tuple[float, str | None]] = {}

_ID_GOOGLE = re.compile(r"news\.google\.com/(?:rss/)?(?:articles|read)/([A-Za-z0-9_-]+)")
_META = re.compile(r"<meta\b[^>]*>", re.I)
_ATTR = re.compile(r"""([a-zA-Z:_-]+)\s*=\s*(?:"([^"]*)"|'([^']*)')""")
_PRIORIDADE = ("og:image:secure_url", "og:image", "og:image:url", "twitter:image", "twitter:image:src")


def id_google(link: str) -> str | None:
    m = _ID_GOOGLE.search(link or "")
    return m.group(1) if m else None


def decodificar_legado(id_: str) -> str | None:
    """Links antigos do Google Notícias levam o endereço da matéria dentro do próprio código (base64). Os novos (AU_yqL…) não: devolve None."""
    try:
        bruto = base64.urlsafe_b64decode(id_ + "=" * (-len(id_) % 4))
    except Exception:
        return None
    if bruto.startswith(b"\x08\x13\x22"):
        bruto = bruto[3:]
    if bruto.endswith(b"\xd2\x01\x00"):
        bruto = bruto[:-3]
    if not bruto:
        return None
    if bruto[0] & 0x80 and len(bruto) > 1:
        tam, ini = (bruto[0] & 0x7F) | (bruto[1] << 7), 2
    else:
        tam, ini = bruto[0], 1
    txt = bruto[ini:ini + tam].decode("utf-8", "ignore")
    return txt if txt.startswith("http") else None


def url_da_materia(link: str) -> str | None:
    """Endereço real da matéria a partir do link do feed (que pode ser um redirecionamento do Google Notícias)."""
    if not link:
        return None
    gid = id_google(link)
    if not gid:
        return link
    leg = decodificar_legado(gid)
    if leg:
        return leg
    try:                                                   # links novos: o pacote googlenewsdecoder pergunta ao Google (gratuito)
        from googlenewsdecoder import gnewsdecoder
        r = gnewsdecoder(link, interval=0)
        if r and str(r.get("decoded_url", "")).startswith("http"):   # versões antigas usam "status", as novas "success": basta checar o endereço
            return r["decoded_url"]
    except Exception:
        pass
    return None


def host_publico(url: str) -> bool:
    """Só sites da internet pública: recusa localhost, IP interno, endereço inválido e porta fora do padrão."""
    try:
        p = urlparse(url)
        if p.scheme != "https" or not p.hostname or p.port not in (None, 443):
            return False
        for info in socket.getaddrinfo(p.hostname, 443, proto=socket.IPPROTO_TCP):
            ip = ipaddress.ip_address(info[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
                return False
        return True
    except Exception:
        return False


def imagem_de_html(html: str, base: str) -> str | None:
    """Imagem de capa declarada pela página (og:image / twitter:image), como endereço https absoluto."""
    achados: dict[str, str] = {}
    for tag in _META.findall((html or "")[:MAX_BYTES]):
        a = {k.lower(): (v1 or v2) for k, v1, v2 in _ATTR.findall(tag)}
        chave = (a.get("property") or a.get("name") or "").lower()
        if chave in _PRIORIDADE and a.get("content") and chave not in achados:
            achados[chave] = a["content"].strip().replace("&amp;", "&")
    for chave in _PRIORIDADE:
        u = achados.get(chave)
        if not u:
            continue
        u = urljoin(base, u)
        if u.startswith("http://"):
            u = "https://" + u[7:]
        if re.match(r"^https://[^\s<>\"']+$", u) and len(u) <= 600:
            return u
    return None


def _baixar(url: str) -> tuple[str, str] | None:
    """(html, endereço final) da página, ou None. Segue poucos redirecionamentos, sempre conferindo o destino."""
    import requests
    atual = url
    for _ in range(4):
        if not host_publico(atual):
            return None
        r = requests.get(atual, headers=UA, timeout=(3, 5), stream=True, allow_redirects=False)
        try:
            if r.status_code in (301, 302, 303, 307, 308) and r.headers.get("location"):
                atual = urljoin(atual, r.headers["location"])
                continue
            if r.status_code != 200 or "html" not in r.headers.get("content-type", "html").lower():
                return None
            dados = b""
            for parte in r.iter_content(16384):
                dados += parte
                if len(dados) >= MAX_BYTES:
                    break
            return dados[:MAX_BYTES].decode(r.encoding or "utf-8", "ignore"), atual
        finally:
            r.close()
    return None


def _foto_da_url(link: str, baixar=_baixar) -> str | None:
    real = url_da_materia(link)
    if not real or real.startswith("http://"):
        real = ("https://" + real[7:]) if real and real.startswith("http://") else real
    if not real:
        return None
    pag = baixar(real)
    if not pag:
        return None
    html, final = pag
    host = (urlparse(final).hostname or "").lower()
    if host.endswith("google.com"):                        # página de redirecionamento do Google: a imagem seria genérica
        return None
    return imagem_de_html(html, final)


def foto_da_noticia(link: str, baixar=_baixar, agora=None) -> str | None:
    """Foto de UMA matéria, com memória (6 h se achou, 30 min se não)."""
    if not link:
        return None
    t = agora if agora is not None else time.time()
    with _LOCK:
        c = _CACHE.get(link)
        if c and t - c[0] < (TTL_ACHOU if c[1] else TTL_FALHOU):
            return c[1]
    try:
        img = _foto_da_url(link, baixar)
    except Exception:
        img = None
    with _LOCK:
        _CACHE[link] = (t, img)
        if len(_CACHE) > MAX_CACHE:
            for k in sorted(_CACHE, key=lambda k: _CACHE[k][0])[:150]:
                _CACHE.pop(k, None)
    return img


def so_cache(link: str) -> str | None:
    with _LOCK:
        c = _CACHE.get(link)
    return c[1] if c else None


def _links_do_grupo(g: dict, max_links: int = 2) -> list[str]:
    ordem = {"oficial": 0, "veiculo": 1, "nao_verificada": 2}
    ms = sorted(g.get("membros") or [], key=lambda m: ordem.get(m.get("fonte_nivel"), 3))
    return [m["url"] for m in ms if m.get("url")][:max_links]


def pre_carregar(grupos: list[dict], limite: int = 14, tempo: float = 12.0, baixar=_baixar) -> int:
    """Busca em paralelo a foto dos primeiros grupos que ainda não têm (respeita um tempo total) e grava em g['imagem']. Devolve quantas achou."""
    alvo = [g for g in grupos[:limite] if not g.get("imagem") and _links_do_grupo(g)]
    if not alvo:
        return 0
    achou = 0

    def trabalho(g):
        for link in _links_do_grupo(g):
            img = foto_da_noticia(link, baixar)
            if img:
                return g, img
        return g, None

    ex = cf.ThreadPoolExecutor(max_workers=6)
    futuros = [ex.submit(trabalho, g) for g in alvo]
    try:
        for f in cf.as_completed(futuros, timeout=tempo):
            try:
                g, img = f.result()
            except Exception:
                continue
            if img:
                g["imagem"] = img
                achou += 1
    except cf.TimeoutError:
        pass
    finally:
        ex.shutdown(wait=False, cancel_futures=True)
    return achou


def foto_do_grupo(g: dict) -> dict:
    """Usa só o que já está na memória (sem rede): se algum link do grupo já teve foto achada, coloca em g['imagem']."""
    if not g.get("imagem"):
        for link in _links_do_grupo(g, 4):
            img = so_cache(link)
            if img:
                g["imagem"] = img
                break
    return g
