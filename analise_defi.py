#!/usr/bin/env python3
"""
Análise fundamentalista automatizada de protocolos DeFi / criptoativos.

Fontes (gratuitas, sem chave):
  - DefiLlama  (https://api.llama.fi): TVL, taxas e volume
  - CoinGecko  (https://api.coingecko.com/api/v3): Market Cap, FDV e supply

Uso:
    python analise_defi.py uniswap
    python analise_defi.py aave lido
    python analise_defi.py            # pergunta o slug no terminal

Requisitos:  pip install requests

Heurísticas educacionais, não recomendação de investimento.
"""
from __future__ import annotations

import sys
import time

import requests

LLAMA = "https://api.llama.fi"
GECKO = "https://api.coingecko.com/api/v3"
TIMEOUT = 20
HEADERS = {"User-Agent": "analise-defi/1.0", "Accept": "application/json"}


class ErroAPI(Exception):
    """Falha ao consultar uma API externa."""


# ----------------------------------------------------------------- requisições
def get_json(url: str, params: dict | None = None, tentativas: int = 3) -> dict | list:
    """GET com timeout, retentativas e tratamento de erros (inclui 429 da CoinGecko)."""
    ultimo = ""
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:  # rate limit
                espera = int(r.headers.get("Retry-After", 5 * (i + 1)))
                ultimo = "limite de requisições atingido (HTTP 429)"
                time.sleep(min(espera, 30))
                continue
            if r.status_code == 404:
                raise ErroAPI(f"não encontrado (HTTP 404): {url}")
            r.raise_for_status()
            return r.json()
        except ErroAPI:
            raise
        except requests.exceptions.Timeout:
            ultimo = "tempo de resposta esgotado"
        except requests.exceptions.ConnectionError:
            ultimo = "falha de conexão"
        except requests.exceptions.HTTPError as e:
            ultimo = f"erro HTTP {e.response.status_code}"
        except ValueError:
            ultimo = "resposta não é um JSON válido"
        time.sleep(1.5 * (i + 1))
    raise ErroAPI(f"{ultimo} ao acessar {url}")


# ------------------------------------------------------------------- DefiLlama
def llama_protocolo(slug: str) -> dict:
    return get_json(f"{LLAMA}/protocol/{slug}")


def tvl_atual(p: dict) -> float | None:
    """TVL atual em USD: soma das cadeias (sem staking/borrowed/pool2) ou último ponto do histórico."""
    cadeias = p.get("currentChainTvls") or {}
    soma = sum(
        v for k, v in cadeias.items()
        if isinstance(v, (int, float)) and not any(t in k for t in ("staking", "borrowed", "pool2", "vesting", "treasury"))
    )
    if soma > 0:
        return float(soma)
    hist = p.get("tvl") or []
    if hist and isinstance(hist[-1], dict):
        return float(hist[-1].get("totalLiquidityUSD") or 0) or None
    return None


def llama_resumo(tipo: str, slug: str, data_type: str | None = None) -> dict | None:
    """Resumo de taxas/volume. Retorna None se o protocolo não tem esse dado (ex.: volume de um não-DEX)."""
    params = {"dataType": data_type} if data_type else None
    try:
        return get_json(f"{LLAMA}/summary/{tipo}/{slug}", params=params, tentativas=2)
    except ErroAPI:
        return None


def total_30d(resumo: dict | None) -> float | None:
    if not resumo:
        return None
    v = resumo.get("total30d")
    if v is None:  # fallback: soma dos últimos 30 dias do gráfico diário
        graf = resumo.get("totalDataChart") or []
        valores = [x[1] for x in graf[-30:] if isinstance(x, (list, tuple)) and len(x) == 2 and x[1] is not None]
        v = sum(valores) if valores else None
    return float(v) if v is not None else None


# ------------------------------------------------------------------- CoinGecko
def gecko_buscar_id(termo: str) -> str | None:
    """Procura o id CoinGecko pelo nome/símbolo (usado se o DefiLlama não informar gecko_id)."""
    try:
        res = get_json(f"{GECKO}/search", params={"query": termo}, tentativas=2)
    except ErroAPI:
        return None
    moedas = res.get("coins") or []
    return moedas[0]["id"] if moedas else None


def gecko_mercado(gecko_id: str) -> dict:
    d = get_json(
        f"{GECKO}/coins/{gecko_id}",
        params={
            "localization": "false", "tickers": "false", "community_data": "false",
            "developer_data": "false", "sparkline": "false",
        },
    )
    m = d.get("market_data") or {}
    preco = (m.get("current_price") or {}).get("usd")
    mc = (m.get("market_cap") or {}).get("usd") or None
    fdv = (m.get("fully_diluted_valuation") or {}).get("usd") or None
    circ, total, maximo = m.get("circulating_supply"), m.get("total_supply"), m.get("max_supply")
    if not fdv and preco:  # estima FDV pelo supply máximo (ou total)
        base = maximo or total
        fdv = preco * base if base else None
    if not mc and preco and circ:
        mc = preco * circ
    return {
        "nome": d.get("name"), "simbolo": (d.get("symbol") or "").upper(), "preco": preco,
        "mcap": mc, "fdv": fdv, "circulante": circ, "total": total, "maximo": maximo,
    }


# ------------------------------------------------------------------ formatação
def usd(v: float | None) -> str:
    if v is None:
        return "n/d"
    a = abs(v)
    for lim, suf in ((1e12, "T"), (1e9, "B"), (1e6, "M"), (1e3, "K")):
        if a >= lim:
            return f"US$ {v / lim:,.2f}{suf}"
    return f"US$ {v:,.2f}"


def razao(a: float | None, b: float | None) -> float | None:
    return a / b if a is not None and b not in (None, 0) else None


def fmt_x(v: float | None, casas: int = 2) -> str:
    return "n/d" if v is None else f"{v:,.{casas}f}x"


def linha(rotulo: str, valor: str, largura: int = 34) -> None:
    print(f"  {rotulo:<{largura}} {valor}")


def titulo(txt: str) -> None:
    print(f"\n{txt}\n" + "-" * len(txt))


# --------------------------------------------------------------------- análise
def analisar(slug: str) -> bool:
    slug = slug.strip().lower()
    print("=" * 60)
    print(f" ANÁLISE FUNDAMENTALISTA: {slug.upper()}")
    print("=" * 60)

    # 1) DefiLlama: dados do protocolo
    try:
        p = llama_protocolo(slug)
    except ErroAPI as e:
        print(f"\n[ERRO] Não consegui carregar o protocolo '{slug}' no DefiLlama: {e}")
        print("       Confira o slug em https://defillama.com/protocols (ex.: uniswap, aave, lido).")
        return False

    nome = p.get("name") or slug
    gecko_id = p.get("gecko_id") or gecko_buscar_id(p.get("symbol") or nome)
    tvl = tvl_atual(p)
    fees30 = total_30d(llama_resumo("fees", slug, "dailyFees"))
    vol30 = total_30d(llama_resumo("dex", slug))  # só existe para DEXs

    # 2) CoinGecko: tokenomics
    mercado = None
    if gecko_id:
        try:
            mercado = gecko_mercado(gecko_id)
        except ErroAPI as e:
            print(f"\n[AVISO] CoinGecko indisponível para '{gecko_id}': {e}")
    else:
        print("\n[AVISO] Protocolo sem token listado na CoinGecko; métricas de tokenomics indisponíveis.")

    mc = mercado["mcap"] if mercado else (p.get("mcap") or None)
    fdv = mercado["fdv"] if mercado else None

    print(f" {nome}" + (f" ({mercado['simbolo']})" if mercado and mercado["simbolo"] else "")
          + f" | Categoria: {p.get('category') or 'n/d'}")

    # Métricas
    mc_fdv = razao(mc, fdv)
    fees_anuais = fees30 * 365 / 30 if fees30 is not None else None
    p_taxas = razao(mc, fees_anuais)
    mc_tvl = razao(mc, tvl)

    titulo("1. TOKENOMICS")
    if mercado and mercado["preco"] is not None:
        linha("Preço do token:", f"US$ {mercado['preco']:,.4f}")
    linha("Market Cap:", usd(mc))
    linha("FDV (Fully Diluted Valuation):", usd(fdv))
    linha("Market Cap / FDV:", f"{mc_fdv:.1%}" if mc_fdv is not None else "n/d")
    if mercado and mercado["circulante"] and mercado["maximo"]:
        linha("Supply circulante / máximo:", f"{mercado['circulante'] / mercado['maximo']:.1%}")

    titulo("2. ON-CHAIN / DEFI")
    linha("TVL atual:", usd(tvl))
    linha("Taxas geradas (30 dias):", usd(fees30))
    linha("Volume (30 dias):", usd(vol30) + ("" if vol30 is not None else "  (não aplicável / indisponível)"))

    titulo("3. VALUATION")
    linha("Taxas anualizadas (30d x 365/30):", usd(fees_anuais))
    linha("Preço/Taxas (MC / taxas anuais):", fmt_x(p_taxas, 1))
    linha("Market Cap / TVL:", fmt_x(mc_tvl, 2))

    titulo("4. ALERTAS")
    alertas = []
    if mc_tvl is None:
        alertas.append("[?] Sem dados suficientes para avaliar MC/TVL.")
    elif mc_tvl < 1:
        alertas.append(f"[OK] DESCONTADO: MC/TVL = {mc_tvl:.2f} (< 1): o mercado avalia o token abaixo do capital depositado.")
    elif mc_tvl <= 3:
        alertas.append(f"[~] VALUATION RAZOÁVEL: MC/TVL = {mc_tvl:.2f} (entre 1 e 3).")
    else:
        alertas.append(f"[!] PREMIUM: MC/TVL = {mc_tvl:.2f} (> 3): token negocia com ágio sobre o TVL.")

    if mc_fdv is not None:
        if mc_fdv < 0.5:
            alertas.append(f"[!] RISCO DE DILUIÇÃO ALTO: só {mc_fdv:.0%} do FDV está em circulação.")
        elif mc_fdv < 0.8:
            alertas.append(f"[~] Diluição moderada: {mc_fdv:.0%} do FDV em circulação.")
        else:
            alertas.append(f"[OK] Baixo risco de diluição: {mc_fdv:.0%} do FDV em circulação.")

    if p_taxas is not None:
        if p_taxas < 15:
            alertas.append(f"[OK] Preço/Taxas baixo ({p_taxas:.1f}x): geração de taxas forte frente ao valor de mercado.")
        elif p_taxas > 50:
            alertas.append(f"[!] Preço/Taxas alto ({p_taxas:.1f}x): valor de mercado exige muito crescimento de taxas.")
    elif fees30 is None:
        alertas.append("[?] Protocolo sem dados de taxas no DefiLlama; Preço/Taxas indisponível.")

    for a in alertas:
        print(f"  {a}")

    print("\n  Obs.: dados públicos e heurísticas simples; não é recomendação de investimento.")
    print("=" * 60)
    return True


def main() -> int:
    slugs = sys.argv[1:] or [input("Slug do protocolo (ex.: uniswap, aave): ").strip()]
    slugs = [s for s in slugs if s]
    if not slugs:
        print("Nenhum protocolo informado.")
        return 1
    ok = True
    for i, s in enumerate(slugs):
        if i:
            time.sleep(2)  # respeita o rate limit gratuito da CoinGecko
        ok = analisar(s) and ok
    return 0 if ok else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\nInterrompido.")
        sys.exit(130)
