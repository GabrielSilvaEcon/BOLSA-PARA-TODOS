"""
Análise fundamentalista de protocolos DeFi / criptoativos (página do Streamlit).

Fontes gratuitas, sem chave:
  - DefiLlama (https://api.llama.fi): TVL, taxas e volume dos protocolos DeFi
  - CoinGecko (https://api.coingecko.com/api/v3): busca de qualquer moeda, preço, histórico, Market Cap, FDV e supply.
    Chave Demo gratuita (recomendada): guarde em st.secrets['COINGECKO_KEY'] ou na variável de ambiente COINGECKO_KEY.

Uso no app.py:
    import cripto
    PG_DEFI = st.Page(cripto.pagina_cripto, title="Cripto / DeFi", icon="🪙", url_path="defi")

Não depende de nenhum outro módulo do projeto (só requests, pandas, plotly e streamlit).
Ferramenta educacional, não é recomendação de investimento.
"""
from __future__ import annotations

import html as _html
import os
import re
import time
import unicodedata
from math import sqrt

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

import tema

LLAMA = "https://api.llama.fi"
GECKO = "https://api.coingecko.com/api/v3"
TIMEOUT = 20
HEADERS = {"User-Agent": "bolsa-para-todos/1.0", "Accept": "application/json"}

# Atalhos de moedas (nome -> id da CoinGecko)
POPULARES = {
    "Bitcoin": "bitcoin", "Ethereum": "ethereum", "Solana": "solana", "XRP": "ripple",
    "BNB": "binancecoin", "Uniswap": "uniswap", "Aave": "aave", "Lido DAO": "lido-dao",
}

# Cores no mesmo tom do app
BRAND, ACCENT, GOOD, FAIR, BAD = "#1F7A55", "#3B6BC4", "#2E7D4F", "#A8650B", "#B83A3A"
TEXT, MUTED, BORDER, SURFACE = "#16202B", "#4B5767", "#DDE2E8", "#FBFCFD"

# classe visual -> (cor do texto/borda, cor de fundo do selo)
COR_CLS = {"good": (GOOD, "rgba(46,125,79,.14)"), "fair": (FAIR, "rgba(168,101,11,.14)"),
           "bad": (BAD, "rgba(184,58,58,.14)"), "na": (MUTED, "rgba(91,102,117,.16)")}
ICONE_STATUS = {"Positivo": "✅", "Neutro": "➖", "Atenção": "⚠️", "Negativo": "❌", "Sem dados": "❔"}


class ErroAPI(Exception):
    """Falha ao consultar uma API externa."""


# ----------------------------------------------------------------- requisições
def _limpa_chave(v) -> str:
    """Tira espaços, aspas e o prefixo NOME= caso a linha tenha sido colada inteira."""
    v = str(v).strip().strip("\"'").strip()
    if "=" in v:
        v = v.rsplit("=", 1)[1].strip().strip("\"'").strip()
    return v


def _chave_gecko() -> str:
    """Chave Demo (gratuita) da CoinGecko. Procura COINGECKO_KEY nos secrets (no topo ou dentro de qualquer
    [bloco], caso tenha sido colada depois de um) e na variável de ambiente. Vazia se não houver."""
    nomes = ("COINGECKO_KEY", "COINGECKO_API_KEY", "coingecko_key", "coingecko_api_key")
    try:
        s = st.secrets
        for n in nomes:
            if s.get(n):
                return _limpa_chave(s[n])
        for bloco in list(s.keys()):
            sub = s[bloco]
            if hasattr(sub, "keys"):
                for n in nomes + ("key", "api_key"):
                    if bloco.lower().startswith("coingecko") or n in nomes:
                        if sub.get(n):
                            return _limpa_chave(sub[n])
    except Exception:  # sem arquivo de secrets
        pass
    return _limpa_chave(os.environ.get("COINGECKO_KEY") or os.environ.get("COINGECKO_API_KEY") or "")


def _get_json(url: str, params: dict | None = None, tentativas: int = 3):
    """GET com timeout, retentativas e tratamento de erros (inclui 429 da CoinGecko)."""
    ultimo = ""
    cab = dict(HEADERS)
    if url.startswith(GECKO) and _chave_gecko():
        cab["x-cg-demo-api-key"] = _chave_gecko()
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, headers=cab, timeout=TIMEOUT)
            if r.status_code == 429:
                ultimo = "limite de requisições atingido (HTTP 429)"
                time.sleep(min(int(r.headers.get("Retry-After", 4 * (i + 1))), 20))
                continue
            if r.status_code == 404:
                raise ErroAPI("não encontrado (HTTP 404)")
            if r.status_code in (401, 403):
                raise ErroAPI(f"acesso negado (HTTP {r.status_code}); confira a chave COINGECKO_KEY")
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
            ultimo = "resposta inválida (não é JSON)"
        time.sleep(1.2 * (i + 1))
    raise ErroAPI(ultimo or "falha desconhecida")


def _tvl_atual(p: dict) -> float | None:
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


def _total_30d(resumo: dict | None) -> float | None:
    if not resumo:
        return None
    v = resumo.get("total30d")
    if v is None:
        graf = resumo.get("totalDataChart") or []
        vals = [x[1] for x in graf[-30:] if isinstance(x, (list, tuple)) and len(x) == 2 and x[1] is not None]
        v = sum(vals) if vals else None
    return float(v) if v is not None else None


def _resumo_llama(tipo: str, slug: str, data_type: str | None = None) -> dict | None:
    try:
        return _get_json(f"{LLAMA}/summary/{tipo}/{slug}", {"dataType": data_type} if data_type else None, 2)
    except ErroAPI:
        return None  # nem todo protocolo tem taxas/volume


def _gecko_id_por_busca(termo: str) -> str | None:
    try:
        moedas = (_get_json(f"{GECKO}/search", {"query": termo}, 2).get("coins") or [])
    except ErroAPI:
        return None
    return moedas[0]["id"] if moedas else None


@st.cache_data(ttl=600, show_spinner=False)
def _gecko_coin_raw(gecko_id: str) -> dict:
    """Ficha da moeda na CoinGecko (uma consulta, compartilhada entre a análise da moeda e a do protocolo)."""
    return _get_json(f"{GECKO}/coins/{gecko_id}", {
        "localization": "false", "tickers": "false", "community_data": "false",
        "developer_data": "false", "sparkline": "false"})


def _gecko_mercado(gecko_id: str) -> dict:
    d = _gecko_coin_raw(gecko_id)
    m = d.get("market_data") or {}
    preco = (m.get("current_price") or {}).get("usd")
    mc = (m.get("market_cap") or {}).get("usd") or None
    fdv = (m.get("fully_diluted_valuation") or {}).get("usd") or None
    circ, total, maximo = m.get("circulating_supply"), m.get("total_supply"), m.get("max_supply")
    if not fdv and preco:
        base = maximo or total
        fdv = preco * base if base else None
    if not mc and preco and circ:
        mc = preco * circ
    return {"simbolo": (d.get("symbol") or "").upper(), "preco": preco, "mcap": mc, "fdv": fdv,
            "circulante": circ, "maximo": maximo}


def _razao(a, b):
    return a / b if a is not None and b not in (None, 0) else None


# --------------------------------------------------------------------- análise
@st.cache_data(ttl=600, show_spinner=False)
def analisar_protocolo(slug: str) -> dict:
    """Busca tudo e calcula as métricas. Levanta ErroAPI se o protocolo não existir no DefiLlama.
    Falhas parciais (CoinGecko fora do ar, sem taxas) vão em 'avisos'; erros não ficam em cache."""
    slug = slug.strip().lower()
    avisos: list[str] = []
    try:
        p = _get_json(f"{LLAMA}/protocol/{slug}")
    except ErroAPI as e:
        raise ErroAPI(f"Não encontrei '{slug}' no DefiLlama ({e}).") from e

    nome = p.get("name") or slug
    gecko_id = p.get("gecko_id") or _gecko_id_por_busca(p.get("symbol") or nome)
    tvl = _tvl_atual(p)
    fees30 = _total_30d(_resumo_llama("fees", slug, "dailyFees"))
    vol30 = _total_30d(_resumo_llama("dex", slug))

    mercado = None
    if gecko_id:
        try:
            mercado = _gecko_mercado(gecko_id)
        except ErroAPI as e:
            avisos.append(f"CoinGecko indisponível agora ({e}). Tokenomics e valuation ficam incompletos; tente de novo em 1 minuto.")
    else:
        avisos.append("Protocolo sem token listado na CoinGecko: tokenomics indisponível.")
    if fees30 is None:
        avisos.append("O DefiLlama não tem dados de taxas para este protocolo: Preço/Taxas indisponível.")

    mc = mercado["mcap"] if mercado else (p.get("mcap") or None)
    fdv = mercado["fdv"] if mercado else None
    fees_anuais = fees30 * 365 / 30 if fees30 is not None else None

    hist = [(pd.to_datetime(x["date"], unit="s"), x["totalLiquidityUSD"])
            for x in (p.get("tvl") or []) if isinstance(x, dict) and x.get("totalLiquidityUSD") is not None]

    return {
        "slug": slug, "nome": nome, "categoria": p.get("category"), "simbolo": mercado["simbolo"] if mercado else "",
        "preco": mercado["preco"] if mercado else None, "mcap": mc, "fdv": fdv,
        "mc_fdv": _razao(mc, fdv),
        "circ_max": _razao(mercado["circulante"], mercado["maximo"]) if mercado else None,
        "tvl": tvl, "fees30": fees30, "vol30": vol30, "fees_anuais": fees_anuais,
        "p_taxas": _razao(mc, fees_anuais), "mc_tvl": _razao(mc, tvl),
        "hist_tvl": hist, "avisos": avisos,
    }


def alertas(a: dict) -> list[tuple[str, str]]:
    """Lista de (nível, texto). Níveis: ok, aviso, ruim, info."""
    out = []
    mt, mf, pt = a["mc_tvl"], a["mc_fdv"], a["p_taxas"]
    if mt is None:
        out.append(("info", "Sem dados suficientes para avaliar Market Cap / TVL."))
    elif mt < 1:
        out.append(("ok", f"**Aparenta estar descontado:** Market Cap / TVL = {mt:.2f} (abaixo de 1). "
                          "O mercado avalia o token por menos do que o capital depositado no protocolo."))
    elif mt <= 3:
        out.append(("info", f"**Valuation razoável:** Market Cap / TVL = {mt:.2f} (entre 1 e 3)."))
    else:
        out.append(("aviso", f"**Negocia com ágio:** Market Cap / TVL = {mt:.2f} (acima de 3). "
                             "O mercado paga bem mais que o TVL, então espera muito crescimento."))
    if mf is not None:
        if mf < 0.5:
            out.append(("ruim", f"**Risco de diluição alto:** só {mf:.0%} do FDV está em circulação. "
                                "Novos tokens ainda vão entrar no mercado e podem pressionar o preço."))
        elif mf < 0.8:
            out.append(("aviso", f"**Diluição moderada:** {mf:.0%} do FDV já circula."))
        else:
            out.append(("ok", f"**Baixo risco de diluição:** {mf:.0%} do FDV já circula."))
    if pt is not None:
        if pt < 15:
            out.append(("ok", f"**Preço/Taxas baixo ({pt:.1f}x):** o protocolo gera muita taxa frente ao valor de mercado."))
        elif pt > 50:
            out.append(("aviso", f"**Preço/Taxas alto ({pt:.1f}x):** o valor de mercado depende de grande crescimento das taxas."))
    return out


# ------------------------------------------------------------------ formatação
def usd(v) -> str:
    if v is None:
        return "n/d"
    for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return f"US$ {v / lim:,.2f}{suf}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"US$ {v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _x(v, casas=2) -> str:
    return "n/d" if v is None else f"{v:,.{casas}f}x".replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v) -> str:
    return "n/d" if v is None else f"{v * 100:.1f}%".replace(".", ",")


# ------------------------------------------------------------ quadrados de resumo
def _md(h: str):
    """Markdown com HTML; o $ é escapado para o Streamlit não tratá-lo como fórmula."""
    st.markdown(h.replace("$", "&#36;"), unsafe_allow_html=True)


def _var_tvl_30d(hist: list) -> float | None:
    """Variação do TVL nos últimos 30 dias (fração: 0.10 = +10%)."""
    if len(hist) < 2:
        return None
    df = pd.DataFrame(hist, columns=["data", "tvl"]).sort_values("data")
    fim = df.iloc[-1]
    antes = df[df["data"] <= fim["data"] - pd.Timedelta(days=30)]
    if antes.empty or not antes.iloc[-1]["tvl"] or antes.iloc[-1]["tvl"] <= 0:
        return None
    return float(fim["tvl"] / antes.iloc[-1]["tvl"] - 1)


def _card(titulo, icone, status, cls, texto, linhas, nota=""):
    return {"titulo": titulo, "icone": icone, "status": status, "cls": cls, "texto": texto,
            "linhas": linhas, "nota": nota}


def indicadores(a: dict) -> list[dict]:
    """Um quadrado por indicador, com selo (Positivo / Neutro / Atenção / Negativo / Sem dados)
    e uma frase em linguagem simples. Os limites são regras educacionais, não recomendação."""
    out = []

    # 1 · diluição (Market Cap / FDV)
    mf = a["mc_fdv"]
    linhas = [("Market Cap", usd(a["mcap"])), ("FDV", usd(a["fdv"])), ("Já em circulação", _pct(mf))]
    nota = "Market Cap ÷ FDV"
    if mf is None:
        out.append(_card("Diluição do token", "🪙", "Sem dados", "na",
                         "Não deu para calcular: o token não está na CoinGecko ou ela está fora do ar.", linhas, nota))
    elif mf >= 0.8:
        out.append(_card("Diluição do token", "🪙", "Positivo", "good",
                         f"{mf:.0%} dos tokens já circulam. Pouco risco de tokens novos derrubarem o preço.", linhas, nota))
    elif mf >= 0.5:
        out.append(_card("Diluição do token", "🪙", "Atenção", "fair",
                         f"Só {mf:.0%} dos tokens circulam. Ainda vão entrar tokens novos no mercado.", linhas, nota))
    else:
        out.append(_card("Diluição do token", "🪙", "Negativo", "bad",
                         f"Apenas {mf:.0%} dos tokens circulam. Muitos tokens ainda serão liberados e podem pressionar o preço.",
                         linhas, nota))

    # 2 · uso do protocolo (TVL e sua variação em 30 dias)
    v = _var_tvl_30d(a["hist_tvl"])
    sinal = "" if v is None else f"{v * 100:+.1f}%".replace(".", ",")
    linhas = [("TVL atual", usd(a["tvl"])), ("Variação 30 dias", sinal or "n/d")]
    nota = "Dinheiro depositado no protocolo"
    if v is None:
        out.append(_card("Uso do protocolo (TVL)", "🏦", "Sem dados", "na",
                         "Não há histórico suficiente para ver se o dinheiro depositado está subindo ou caindo.", linhas, nota))
    elif v >= 0.05:
        out.append(_card("Uso do protocolo (TVL)", "🏦", "Positivo", "good",
                         "Mais dinheiro entrando no protocolo nos últimos 30 dias: sinal de confiança dos usuários.", linhas, nota))
    elif v >= -0.10:
        out.append(_card("Uso do protocolo (TVL)", "🏦", "Neutro", "fair",
                         "O dinheiro depositado ficou praticamente estável no último mês.", linhas, nota))
    else:
        out.append(_card("Uso do protocolo (TVL)", "🏦", "Negativo", "bad",
                         "Saiu bastante dinheiro do protocolo no último mês: usuários estão retirando recursos.", linhas, nota))

    # 3 · receita (taxas pagas pelos usuários)
    f30 = a["fees30"]
    linhas = [("Taxas 30 dias", usd(f30)), ("Taxas anualizadas", usd(a["fees_anuais"])), ("Volume 30 dias", usd(a["vol30"]))]
    nota = "Quanto os usuários pagaram para usar"
    if f30 is None:
        out.append(_card("Receita (taxas)", "💸", "Sem dados", "na",
                         "O DefiLlama não tem dados de taxas deste protocolo. O volume só existe para corretoras descentralizadas.",
                         linhas, nota))
    elif f30 > 0:
        out.append(_card("Receita (taxas)", "💸", "Positivo", "good",
                         "O protocolo gera taxas: há gente pagando para usá-lo, não é só dinheiro parado.", linhas, nota))
    else:
        out.append(_card("Receita (taxas)", "💸", "Negativo", "bad",
                         "Nenhuma taxa registrada nos últimos 30 dias: o protocolo quase não é usado.", linhas, nota))

    # 4 · Preço/Taxas
    pt = a["p_taxas"]
    linhas = [("Preço/Taxas", _x(pt, 1)), ("Market Cap", usd(a["mcap"]))]
    nota = "Market Cap ÷ taxas anuais (parecido com o P/L)"
    if pt is None:
        out.append(_card("Preço/Taxas", "⚖️", "Sem dados", "na",
                         "Sem taxas ou sem valor de mercado para calcular.", linhas, nota))
    elif pt < 15:
        out.append(_card("Preço/Taxas", "⚖️", "Positivo", "good",
                         f"O token vale {pt:.1f}x as taxas de um ano: barato para o quanto o protocolo gera.", linhas, nota))
    elif pt <= 50:
        out.append(_card("Preço/Taxas", "⚖️", "Neutro", "fair",
                         f"O token vale {pt:.1f}x as taxas de um ano: preço intermediário.", linhas, nota))
    else:
        out.append(_card("Preço/Taxas", "⚖️", "Atenção", "fair",
                         f"O token vale {pt:.1f}x as taxas de um ano: caro, depende de muito crescimento.", linhas, nota))

    # 5 · Market Cap / TVL
    mt = a["mc_tvl"]
    linhas = [("Market Cap / TVL", _x(mt, 2)), ("TVL atual", usd(a["tvl"]))]
    nota = "Valor do token ÷ dinheiro depositado"
    if mt is None:
        out.append(_card("Valor × dinheiro depositado", "📊", "Sem dados", "na",
                         "Sem TVL ou sem valor de mercado para calcular.", linhas, nota))
    elif mt < 1:
        out.append(_card("Valor × dinheiro depositado", "📊", "Positivo", "good",
                         "O token vale menos que o dinheiro depositado no protocolo: aparenta estar descontado.", linhas, nota))
    elif mt <= 3:
        out.append(_card("Valor × dinheiro depositado", "📊", "Neutro", "fair",
                         "O token vale entre 1 e 3 vezes o dinheiro depositado: valuation razoável.", linhas, nota))
    else:
        out.append(_card("Valor × dinheiro depositado", "📊", "Atenção", "fair",
                         "O token vale mais de 3 vezes o dinheiro depositado: o mercado já espera muito crescimento.",
                         linhas, nota))
    return out


def _html_card(c: dict) -> str:
    cor, fundo = COR_CLS[c["cls"]]
    esc = _html.escape
    itens = "".join(
        f'<div><div style="font-size:.68rem;color:{MUTED};text-transform:uppercase;letter-spacing:.6px;'
        f'font-weight:700;">{esc(r)}</div><div style="font-size:1.05rem;font-weight:800;color:{TEXT};">{esc(v)}</div></div>'
        for r, v in c["linhas"])
    return (
        f'<div style="background:{SURFACE};border:1px solid {BORDER};border-top:3px solid {cor};border-radius:16px;'
        f'padding:14px 16px;margin-bottom:10px;min-height:235px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;">'
        f'<div style="font-size:1.02rem;font-weight:800;color:{TEXT};">{c["icone"]} {esc(c["titulo"])}</div>'
        f'<span style="background:{fundo};color:{cor};padding:3px 11px;border-radius:999px;font-size:.74rem;'
        f'font-weight:800;white-space:nowrap;">{ICONE_STATUS[c["status"]]} {esc(c["status"])}</span></div>'
        f'<div style="font-size:.78rem;color:{MUTED};margin:2px 0 10px;">{esc(c["nota"])}</div>'
        f'<div style="display:flex;flex-wrap:wrap;gap:8px 22px;">{itens}</div>'
        f'<div style="font-size:.86rem;color:{TEXT};line-height:1.45;margin-top:12px;">{esc(c["texto"])}</div></div>')


def _resumo_geral(cards: list[dict]):
    """Faixa no topo: quantos indicadores são positivos."""
    n = sum(c["status"] != "Sem dados" for c in cards)
    pos = sum(c["status"] == "Positivo" for c in cards)
    neg = sum(c["status"] == "Negativo" for c in cards)
    if n == 0:
        cls, titulo = "na", "Sem dados suficientes para resumir"
    elif neg * 2 >= n:
        cls, titulo = "bad", "Quadro desfavorável"
    elif pos / n >= 0.6 and neg == 0:
        cls, titulo = "good", "Quadro favorável"
    else:
        cls, titulo = "fair", "Quadro misto"
    cor, _ = COR_CLS[cls]
    detalhe = (f"{pos} de {n} indicadores positivos · {neg} negativo(s) · {n - pos - neg} neutro(s) ou de atenção"
               if n else "CoinGecko ou DefiLlama sem resposta para este protocolo.")
    _md(f'<div style="background:{SURFACE};border:1px solid {BORDER};border-left:5px solid {cor};border-radius:12px;'
        f'padding:12px 16px;margin:6px 0 12px;"><div style="font-weight:800;font-size:1.05rem;color:{cor};">{titulo}</div>'
        f'<div style="font-size:.85rem;color:{MUTED};margin-top:3px;">{detalhe}</div></div>')


# ----------------------------------------------------------------------- busca
def _norm(s) -> str:
    """Minúsculas, sem acento e sem pontuação: 'MakerDAO / Sky' -> 'makerdao sky'."""
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


@st.cache_data(ttl=3600, show_spinner=False)
def listar_protocolos() -> list[dict]:
    """Protocolos do DefiLlama (usados para ligar uma moeda ao seu protocolo DeFi), do maior TVL ao menor.
    Levanta ErroAPI se a API não responder (erro não fica em cache)."""
    dados = _get_json(f"{LLAMA}/protocols", tentativas=2)
    if not isinstance(dados, list):
        raise ErroAPI("resposta inesperada do DefiLlama")
    out = []
    for p in dados:
        if not isinstance(p, dict) or not p.get("slug") or p.get("category") == "CEX":
            continue
        tvl = p.get("tvl")
        out.append({"slug": p["slug"], "gecko_id": p.get("gecko_id") or "",
                    "parent": p.get("parentProtocol") or "",
                    "tvl": float(tvl) if isinstance(tvl, (int, float)) else None})
    out.sort(key=lambda x: x["tvl"] or 0, reverse=True)
    return out


def slugs_defi(gecko_id: str, lista: list[dict]) -> list[str]:
    """Protocolos do DefiLlama ligados a essa moeda: primeiro o protocolo-pai (soma as versões), depois os filhos."""
    out: list[str] = []
    for p in lista:
        if p["gecko_id"] != gecko_id:
            continue
        pai = p["parent"][7:] if p["parent"].startswith("parent#") else ""
        for s in (pai, p["slug"]):
            if s and s not in out:
                out.append(s)
        if len(out) >= 4:
            break
    return out


@st.cache_data(ttl=600, show_spinner=False)
def buscar_moedas(termo: str) -> list[dict]:
    """Busca qualquer moeda pelo nome ou símbolo na CoinGecko. Levanta ErroAPI se a busca falhar."""
    q = _norm(termo)
    if len(q) < 2:
        return []
    dados = _get_json(f"{GECKO}/search", {"query": termo.strip()}, 2)
    out = []
    for c in (dados.get("coins") or []):
        if not isinstance(c, dict) or not c.get("id"):
            continue
        out.append({"id": c["id"], "nome": c.get("name") or c["id"], "simbolo": (c.get("symbol") or "").upper(),
                    "rank": c.get("market_cap_rank"), "logo": c.get("large") or c.get("thumb") or ""})

    def ordem(c):  # 1º: bate exato e tem ranking; 2º: tem ranking; 3º: sem ranking (comum em tokens copiados)
        exato = q in (_norm(c["nome"]), _norm(c["simbolo"]))
        grupo = 0 if (exato and c["rank"]) else (1 if c["rank"] else 2)
        return (grupo, c["rank"] or 10 ** 9)

    out.sort(key=ordem)
    return out[:6]


# ------------------------------------------------------------ busca por setor (categorias da CoinGecko)
# (nome em português, id da categoria na CoinGecko, palavras de busca extras)
SETORES = [
    ("DeFi (finanças descentralizadas)", "decentralized-finance-defi", ["defi", "financas"]),
    ("Layer 1 (blockchains principais)", "layer-1", ["l1", "camada 1", "blockchain"]),
    ("Layer 2 (redes de escala)", "layer-2", ["l2", "camada 2", "escala"]),
    ("Stablecoins (moedas estáveis)", "stablecoins", ["estavel", "estaveis", "dolar", "stable"]),
    ("Memecoins", "meme-token", ["meme", "memes"]),
    ("Inteligência artificial", "artificial-intelligence", ["ia", "ai", "inteligencia"]),
    ("Jogos (GameFi)", "gaming", ["jogos", "games", "game", "gamefi"]),
    ("NFT", "non-fungible-tokens-nft", ["nft", "colecionaveis"]),
    ("Exchanges (corretoras)", "exchange-based-tokens", ["exchange", "corretora", "corretoras"]),
    ("Exchanges descentralizadas (DEX)", "decentralized-exchange", ["dex", "swap"]),
    ("Empréstimos (lending)", "lending-borrowing", ["lending", "emprestimo", "emprestimos"]),
    ("Staking líquido", "liquid-staking-governance-tokens", ["staking", "liquid"]),
    ("Oráculos", "oracle", ["oraculo", "oraculos", "oracle"]),
    ("Privacidade", "privacy-coins", ["privacidade", "privacy", "anonimas"]),
    ("Ativos do mundo real (RWA)", "real-world-assets-rwa", ["rwa", "tokenizacao", "mundo real"]),
    ("Metaverso", "metaverse", ["metaverso", "metaverse"]),
    ("Infraestrutura", "infrastructure", ["infra", "infraestrutura"]),
]


@st.cache_data(ttl=3600, show_spinner=False)
def listar_setores() -> dict:
    """{id: nome} de todas as categorias da CoinGecko. Vazio se a consulta falhar."""
    try:
        dados = _get_json(f"{GECKO}/coins/categories/list", None, 2)
    except ErroAPI:
        return {}
    return {d["category_id"]: d.get("name") or d["category_id"] for d in (dados or [])
            if isinstance(d, dict) and d.get("category_id")}


def setores_curados() -> list[tuple[str, str, list]]:
    """Os setores em português; se a lista oficial carregou, tira os que não existem mais lá."""
    todos = listar_setores()
    return [s for s in SETORES if not todos or s[1] in todos]


def buscar_setores(termo: str) -> list[tuple[str, str]]:
    """Setores (id, nome) que combinam com o texto digitado (nome em português, apelidos ou nome em inglês)."""
    q = _norm(termo)
    if len(q) < 2:
        return []
    achados: dict[str, str] = {}
    for nome, cid, apelidos in setores_curados():
        if q in _norm(nome) or any(q == _norm(a) or (len(q) >= 3 and q in _norm(a)) for a in apelidos):
            achados[cid] = nome
    if len(q) >= 3:
        for cid, nome in listar_setores().items():
            if q in _norm(nome) and cid not in achados:
                achados[cid] = nome
    return list(achados.items())[:5]


@st.cache_data(ttl=600, show_spinner=False)
def moedas_do_setor(categoria: str, quantas: int = 10) -> list[dict]:
    """As maiores moedas de um setor por valor de mercado, com preço e variação. Levanta ErroAPI se falhar."""
    dados = _get_json(f"{GECKO}/coins/markets", {
        "vs_currency": "usd", "category": categoria, "order": "market_cap_desc",
        "per_page": int(quantas), "page": 1, "sparkline": "false", "price_change_percentage": "24h,7d"}, 2)
    out = []
    for c in (dados or []):
        if not isinstance(c, dict) or not c.get("id"):
            continue
        out.append({"id": c["id"], "nome": c.get("name") or c["id"], "simbolo": (c.get("symbol") or "").upper(),
                    "rank": c.get("market_cap_rank"), "logo": c.get("image") or "", "preco": c.get("current_price"),
                    "var24": c.get("price_change_percentage_24h_in_currency", c.get("price_change_percentage_24h")),
                    "var7": c.get("price_change_percentage_7d_in_currency"), "mcap": c.get("market_cap")})
    return out


def _escolher_setor(cid: str):
    """Mostra um setor (usado pelos botões de resultado da busca)."""
    st.session_state["cripto_setor_sel"] = "🔎 Outro setor (lista completa)"
    st.session_state["cripto_setor_all"] = cid
    st.session_state["cripto_setor_n"] = 10


def _mais_do_setor():
    st.session_state["cripto_setor_n"] = min(50, st.session_state.get("cripto_setor_n", 10) + 10)


def _zerar_n_setor():
    st.session_state["cripto_setor_n"] = 10


# ------------------------------------------------------------ análise de uma moeda
@st.cache_data(ttl=900, show_spinner=False)
def _gecko_historico(gecko_id: str) -> list[tuple]:
    """Preço diário em USD dos últimos 365 dias: [(data, preço), ...]."""
    d = _get_json(f"{GECKO}/coins/{gecko_id}/market_chart", {"vs_currency": "usd", "days": "365"})
    return [(pd.to_datetime(x[0], unit="ms"), float(x[1])) for x in (d.get("prices") or [])
            if isinstance(x, (list, tuple)) and len(x) == 2 and x[1] is not None]


def _rotular_tendencia(acima: bool, cruz: bool, incl: bool) -> str:
    """Mesma regra das ações: preço acima da média de 200 dias, média de 50 acima da de 200 e média de 200 subindo."""
    pts = int(acima) + int(cruz) + int(incl)
    return "Alta" if pts == 3 else ("Baixa" if pts == 0 else "Lateral")


def _sinais_preco(hist: list) -> dict:
    """Tendência, volatilidade anual, queda desde a máxima e máxima do período, a partir do preço diário."""
    out = {"tendencia": None, "vol": None, "queda": None, "maxima": None}
    if len(hist) < 30:
        return out
    c = pd.Series([p for _, p in hist], index=[t for t, _ in hist]).dropna()
    c = c[c > 0]
    if len(c) < 30:
        return out
    out["maxima"] = float(c.max())
    out["queda"] = float((c.iloc[-1] / c.max() - 1) * 100)
    if len(c) >= 60:
        out["vol"] = float(c.pct_change().dropna().std() * sqrt(365) * 100)  # cripto negocia todos os dias
    if len(c) >= 200:
        mm50, mm200 = c.rolling(50).mean(), c.rolling(200).mean()
        m200 = float(mm200.iloc[-1])
        if m200 > 0:
            ref = mm200.iloc[-21] if len(c) >= 220 else None
            cruz = float(mm50.iloc[-1]) > m200
            incl = (m200 > float(ref)) if ref is not None and pd.notna(ref) else cruz
            out["tendencia"] = _rotular_tendencia(float(c.iloc[-1]) > m200, cruz, incl)
    return out


@st.cache_data(ttl=600, show_spinner=False)
def analisar_moeda(gecko_id: str) -> dict:
    """Dados de mercado e sinais de preço de qualquer moeda. Levanta ErroAPI se a moeda não existir.
    Falhas parciais (sem histórico) vão em 'avisos'; erros não ficam em cache."""
    avisos: list[str] = []
    d = _gecko_coin_raw(gecko_id)
    m = d.get("market_data") or {}

    def usd_(k):
        return (m.get(k) or {}).get("usd")

    preco, mc, fdv = usd_("current_price"), usd_("market_cap") or None, usd_("fully_diluted_valuation") or None
    circ, total, maximo = m.get("circulating_supply"), m.get("total_supply"), m.get("max_supply")
    if not fdv and preco and (maximo or total):
        fdv = preco * (maximo or total)
    if not mc and preco and circ:
        mc = preco * circ
    try:
        hist = _gecko_historico(gecko_id)
    except ErroAPI as e:
        hist = []
        avisos.append(f"Histórico de preços indisponível agora ({e}): tendência, volatilidade e queda ficam sem dados.")
    if hist and len(hist) < 200:
        avisos.append("Moeda com menos de 200 dias de histórico: a tendência não pode ser calculada.")
    return {
        "id": gecko_id, "nome": d.get("name") or gecko_id, "simbolo": (d.get("symbol") or "").upper(),
        "logo": (d.get("image") or {}).get("small") or "", "rank": d.get("market_cap_rank"),
        "categorias": [c for c in (d.get("categories") or []) if c][:3],
        "preco": preco, "mcap": mc, "fdv": fdv, "mc_fdv": _razao(mc, fdv), "maximo": maximo,
        "vol24": usd_("total_volume"),
        "var7": m.get("price_change_percentage_7d"), "var30": m.get("price_change_percentage_30d"),
        "var1a": m.get("price_change_percentage_1y"),
        "hist": hist, **_sinais_preco(hist), "avisos": avisos,
    }


def _preco_usd(v) -> str:
    if v is None:
        return "n/d"
    casas = 2 if abs(v) >= 1 else 4 if abs(v) >= 0.01 else 8
    return f"US$ {v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _var(v) -> str:
    """Variação que já vem em % (5.3 = +5,3%)."""
    return "n/d" if v is None else f"{v:+.1f}%".replace(".", ",")


def indicadores_moeda(m: dict) -> list[dict]:
    """Seis quadrados que valem para qualquer moeda. Limites são regras educacionais, não recomendação."""
    out = []

    # 1 · tendência
    t = m["tendencia"]
    linhas = [("Tendência", {"Alta": "▲ Alta", "Lateral": "► Lateral", "Baixa": "▼ Baixa"}.get(t, "n/d")),
              ("Preço", _preco_usd(m["preco"]))]
    nota = "Médias de 50 e 200 dias, gráfico diário de 1 ano"
    if t is None:
        out.append(_card("Tendência", "📈", "Sem dados", "na",
                         "Não há 200 dias de histórico para calcular a tendência.", linhas, nota))
    elif t == "Alta":
        out.append(_card("Tendência", "📈", "Positivo", "good",
                         "O preço está acima da média de 200 dias e as médias sobem: o movimento dominante é de alta.",
                         linhas, nota))
    elif t == "Lateral":
        out.append(_card("Tendência", "📈", "Neutro", "fair",
                         "Sinais mistos: o preço anda de lado, sem direção clara.", linhas, nota))
    else:
        out.append(_card("Tendência", "📈", "Negativo", "bad",
                         "O preço está abaixo das médias de longo prazo e elas caem: o movimento dominante é de queda.",
                         linhas, nota))

    # 2 · desempenho recente
    v30 = m["var30"]
    linhas = [("7 dias", _var(m["var7"])), ("30 dias", _var(v30)), ("1 ano", _var(m["var1a"]))]
    nota = "Quanto o preço variou"
    if v30 is None:
        out.append(_card("Desempenho", "🚀", "Sem dados", "na", "Sem variação de 30 dias na fonte.", linhas, nota))
    elif v30 >= 10:
        out.append(_card("Desempenho", "🚀", "Positivo", "good",
                         "O preço subiu 10% ou mais no último mês.", linhas, nota))
    elif v30 >= -10:
        out.append(_card("Desempenho", "🚀", "Neutro", "fair",
                         "O preço ficou relativamente parado no último mês (entre −10% e +10%).", linhas, nota))
    else:
        out.append(_card("Desempenho", "🚀", "Negativo", "bad",
                         "O preço caiu mais de 10% no último mês.", linhas, nota))

    # 3 · volatilidade
    v = m["vol"]
    linhas = [("Volatilidade anual", "n/d" if v is None else f"{v:.0f}%")]
    nota = "Quanto o preço oscila (1 ano)"
    if v is None:
        out.append(_card("Volatilidade", "🎢", "Sem dados", "na", "Histórico curto demais para medir.", linhas, nota))
    elif v < 50:
        out.append(_card("Volatilidade", "🎢", "Positivo", "good",
                         "Oscila pouco para os padrões de cripto: risco de sustos menor.", linhas, nota))
    elif v <= 90:
        out.append(_card("Volatilidade", "🎢", "Neutro", "fair",
                         "Oscilação típica de cripto: espere altas e quedas fortes.", linhas, nota))
    elif v <= 130:
        out.append(_card("Volatilidade", "🎢", "Atenção", "fair",
                         "Oscila muito, mais que a maioria das criptomoedas.", linhas, nota))
    else:
        out.append(_card("Volatilidade", "🎢", "Negativo", "bad",
                         "Oscilação extrema: o preço pode mudar muito de um dia para o outro.", linhas, nota))

    # 4 · queda desde a máxima de 1 ano
    q = m["queda"]
    linhas = [("Queda desde a máxima", "n/d" if q is None else f"{q:.0f}%".replace(".", ",")),
              ("Máxima de 1 ano", _preco_usd(m["maxima"]))]
    nota = "Distância do topo dos últimos 12 meses"
    if q is None:
        out.append(_card("Queda desde a máxima", "⛰️", "Sem dados", "na", "Sem histórico suficiente.", linhas, nota))
    elif q >= -20:
        out.append(_card("Queda desde a máxima", "⛰️", "Positivo", "good",
                         "O preço está perto da máxima do ano.", linhas, nota))
    elif q >= -40:
        out.append(_card("Queda desde a máxima", "⛰️", "Neutro", "fair",
                         "O preço recuou uma parte do topo do ano.", linhas, nota))
    elif q >= -60:
        out.append(_card("Queda desde a máxima", "⛰️", "Atenção", "fair",
                         "O preço perdeu boa parte do valor desde o topo do ano.", linhas, nota))
    else:
        out.append(_card("Queda desde a máxima", "⛰️", "Negativo", "bad",
                         "O preço caiu mais de 60% desde o topo do ano.", linhas, nota))

    # 5 · diluição
    mf = m["mc_fdv"]
    linhas = [("Market Cap", usd(m["mcap"])), ("FDV", usd(m["fdv"])), ("Já em circulação", _pct(mf))]
    nota = "Market Cap ÷ FDV"
    if mf is None:
        txt = ("Esta moeda não tem oferta máxima definida: não dá para medir a diluição pelo FDV."
               if not m["maximo"] else "Sem dados de supply na fonte.")
        out.append(_card("Diluição do token", "🪙", "Sem dados", "na", txt, linhas, nota))
    elif mf >= 0.8:
        out.append(_card("Diluição do token", "🪙", "Positivo", "good",
                         f"{mf:.0%} dos tokens já circulam. Pouco risco de tokens novos derrubarem o preço.", linhas, nota))
    elif mf >= 0.5:
        out.append(_card("Diluição do token", "🪙", "Atenção", "fair",
                         f"Só {mf:.0%} dos tokens circulam. Ainda vão entrar tokens novos no mercado.", linhas, nota))
    else:
        out.append(_card("Diluição do token", "🪙", "Negativo", "bad",
                         f"Apenas {mf:.0%} dos tokens circulam. Muitos tokens ainda serão liberados e podem pressionar o preço.",
                         linhas, nota))

    # 6 · porte e liquidez
    r = m["rank"]
    linhas = [("Ranking", f"#{r}" if r else "n/d"), ("Market Cap", usd(m["mcap"])), ("Volume 24h", usd(m["vol24"]))]
    nota = "Tamanho e facilidade de comprar e vender"
    if not r:
        out.append(_card("Porte e liquidez", "🏛️", "Sem dados", "na",
                         "A moeda não tem ranking de valor de mercado na CoinGecko.", linhas, nota))
    elif r <= 30:
        out.append(_card("Porte e liquidez", "🏛️", "Positivo", "good",
                         "Está entre as maiores do mercado: mais liquidez e mais história.", linhas, nota))
    elif r <= 200:
        out.append(_card("Porte e liquidez", "🏛️", "Neutro", "fair",
                         "Moeda de porte médio: liquidez razoável.", linhas, nota))
    elif r <= 1000:
        out.append(_card("Porte e liquidez", "🏛️", "Atenção", "fair",
                         "Moeda pequena: pode ser difícil vender sem mexer no preço.", linhas, nota))
    else:
        out.append(_card("Porte e liquidez", "🏛️", "Negativo", "bad",
                         "Moeda muito pequena: risco alto de baixa liquidez.", linhas, nota))
    return out


# ------------------------------------------------------------------ página
def _grafico_preco(hist: list) -> go.Figure | None:
    if len(hist) < 30:
        return None
    df = pd.DataFrame(hist, columns=["data", "preco"]).set_index("data")
    fig = go.Figure(go.Scatter(x=df.index, y=df["preco"], mode="lines", name="Preço",
                               line=dict(color=ACCENT, width=2),
                               hovertemplate="%{x|%d/%m/%Y}<br>US$ %{y:,.4f}<extra></extra>"))
    for janela, cor in ((50, "#C9A227"), (200, "#7B5EA7")):
        if len(df) >= janela:
            fig.add_scatter(x=df.index, y=df["preco"].rolling(janela).mean(), mode="lines", name=f"Média {janela} dias",
                            line=dict(color=cor, width=1.4, dash="dot"), hoverinfo="skip")
    fig.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", legend=dict(orientation="h", y=-0.12, x=0),
                      yaxis=dict(title="Preço (US$)", gridcolor=BORDER), xaxis=dict(gridcolor=BORDER))
    return fig


def _grafico_tvl(hist: list) -> go.Figure | None:
    if len(hist) < 2:
        return None
    df = pd.DataFrame(hist, columns=["data", "tvl"])
    fig = go.Figure(go.Scatter(x=df["data"], y=df["tvl"], mode="lines", line=dict(color=ACCENT, width=2),
                               fill="tozeroy", fillcolor="rgba(59,107,196,0.10)",
                               hovertemplate="%{x|%d/%m/%Y}<br>TVL: US$ %{y:,.0f}<extra></extra>"))
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=False, yaxis=dict(title="TVL (US$)", gridcolor=BORDER),
                      xaxis=dict(gridcolor=BORDER))
    return fig


def _mostrar_alerta(nivel: str, texto: str):
    {"ok": st.success, "aviso": st.warning, "ruim": st.error, "info": st.info}[nivel](texto)


def _detalhes_defi(a: dict):
    """Números detalhados e alertas do protocolo DeFi ligado à moeda."""
    st.markdown("**Alertas de valuation**")
    for nivel, texto in alertas(a):
        _mostrar_alerta(nivel, texto)
    st.markdown("**On-chain / DeFi**")
    k = st.columns(3)
    k[0].metric("TVL atual", usd(a["tvl"]), help="Total Value Locked: valor depositado no protocolo.")
    k[1].metric("Taxas (30 dias)", usd(a["fees30"]), help="Taxas pagas pelos usuários do protocolo nos últimos 30 dias.")
    k[2].metric("Volume (30 dias)", usd(a["vol30"]), help="Só existe para corretoras descentralizadas (DEX).")
    st.markdown("**Valuation**")
    k = st.columns(3)
    k[0].metric("Taxas anualizadas", usd(a["fees_anuais"]), help="Taxas de 30 dias × 365/30.")
    k[1].metric("Preço/Taxas", _x(a["p_taxas"], 1), help="Market Cap ÷ taxas anuais. Parecido com o P/L das ações: quanto menor, mais barato.")
    k[2].metric("Market Cap / TVL", _x(a["mc_tvl"], 2), help="Abaixo de 1: o token vale menos que o capital depositado.")


def _mostrar_moeda(gid: str):
    """Analisa e exibe uma moeda: quadrados, gráfico de preço e, se for protocolo DeFi, TVL e taxas."""
    try:
        with st.spinner(f"Consultando a CoinGecko para “{gid}”…"):
            m = analisar_moeda(gid)
    except ErroAPI as e:
        st.error(f"Não consegui analisar “{gid}”: {e}. Remova da lista ou tente de novo em instantes.")
        return
    except Exception as e:  # erro inesperado não derruba o app
        st.error(f"Erro inesperado ao analisar “{gid}”: {e.__class__.__name__}.")
        return

    # protocolo DeFi ligado à moeda (se houver)
    a_defi, aviso_defi = None, ""
    try:
        with st.spinner("Procurando dados DeFi (TVL e taxas) no DefiLlama…"):
            lista = listar_protocolos()
            for slug in slugs_defi(gid, lista)[:3]:
                try:
                    a_defi = analisar_protocolo(slug)
                    break
                except Exception:
                    continue
    except Exception:
        aviso_defi = "O DefiLlama não respondeu agora: TVL e taxas não puderam ser consultados."

    gerais = indicadores_moeda(m)
    defi = indicadores(a_defi)[1:] if a_defi else []  # a diluição já está entre os quadrados gerais

    esc = _html.escape
    img = (f'<img src="{esc(m["logo"])}" width="40" height="40" style="border-radius:10px;background:#fff;padding:3px;'
           f'border:1px solid {BORDER};object-fit:contain;flex-shrink:0;">' if m["logo"].startswith("https://") else "")
    sim = f" ({esc(m['simbolo'])})" if m["simbolo"] else ""
    cats = " · ".join(esc(c) for c in m["categorias"])
    _md(f'<div style="display:flex;align-items:center;gap:12px;margin:6px 0 2px;">{img}<div>'
        f'<div style="font-size:1.2rem;font-weight:800;color:{TEXT};">{esc(m["nome"])}{sim} · {_preco_usd(m["preco"])}</div>'
        f'<div style="font-size:.8rem;color:{MUTED};">{"Ranking #" + str(m["rank"]) if m["rank"] else "Sem ranking"}'
        f'{" · " + cats if cats else ""}</div></div></div>')
    for av in m["avisos"]:
        st.warning(av)

    st.markdown("**Resumo dos indicadores**")
    _resumo_geral(gerais + defi)
    for linha in (gerais[:3], gerais[3:]):
        for col, c in zip(st.columns(3), linha):
            with col:
                _md(_html_card(c))

    fig = _grafico_preco(m["hist"])
    if fig:
        st.markdown("**Preço nos últimos 12 meses**")
        st.plotly_chart(fig, width="stretch", key=f"cripto_preco_{gid}", config={"displayModeBar": False})

    if a_defi:
        st.markdown("**Fundamentos DeFi (TVL e taxas)**")
        for av in a_defi["avisos"]:
            if "CoinGecko" not in av:
                st.caption(f"ℹ️ {av}")
        for col, c in zip(st.columns(4), defi):
            with col:
                _md(_html_card(c))
        fig = _grafico_tvl(a_defi["hist_tvl"])
        if fig:
            st.markdown("**Evolução do TVL**")
            st.plotly_chart(fig, width="stretch", key=f"cripto_tvl_{gid}", config={"displayModeBar": False})
        with st.expander("Ver números e alertas detalhados do protocolo"):
            _detalhes_defi(a_defi)
    elif aviso_defi:
        st.caption(f"ℹ️ {aviso_defi}")
    else:
        st.caption("ℹ️ Esta moeda não é um protocolo DeFi no DefiLlama: TVL e taxas não se aplicam.")


def _adicionar_cripto(gid: str, nome: str = ""):
    if nome:
        st.session_state.setdefault("cripto_nomes", {})[gid] = nome
    sel = st.session_state.get("cripto_ativos", [])
    if gid not in sel:
        st.session_state["cripto_ativos"] = sel + [gid]


def _render_resultados(res: list[dict], sel: list[str]):
    """Um cartão por moeda achada, com logo, ranking e botão de adicionar."""
    esc = _html.escape
    for c in res:
        with st.container(border=True):
            a, b = st.columns([5, 1.5], vertical_alignment="center")
            img = (f'<img src="{esc(c["logo"])}" width="38" height="38" style="border-radius:10px;background:#fff;'
                   f'padding:3px;border:1px solid {BORDER};object-fit:contain;flex-shrink:0;">'
                   if c["logo"].startswith("https://") else "")
            rank = f"Ranking #{c['rank']}" if c["rank"] else "Sem ranking"
            with a:
                _md(f'<div style="display:flex;align-items:center;gap:12px;">{img}<div>'
                    f'<div style="font-weight:800;color:{TEXT};">{esc(c["nome"])} ({esc(c["simbolo"])})</div>'
                    f'<div style="font-size:.8rem;color:{MUTED};">{rank}</div></div></div>')
            ja = c["id"] in sel
            b.button("✔ Adicionada" if ja else "➕ Adicionar", key=f"cripto_add_{c['id']}",
                     on_click=_adicionar_cripto, args=(c["id"], c["nome"]), disabled=ja, width="stretch")


def _render_setor(res: list[dict], sel: list[str]):
    """Moedas de um setor: logo, ranking, preço, variações, valor de mercado e botão de adicionar."""
    esc = _html.escape
    for c in res:
        with st.container(border=True):
            a, b = st.columns([5, 1.6], vertical_alignment="center")
            img = (f'<img src="{esc(c["logo"])}" width="38" height="38" style="border-radius:10px;background:#fff;'
                   f'padding:3px;border:1px solid {BORDER};object-fit:contain;flex-shrink:0;">'
                   if str(c["logo"]).startswith("https://") else "")
            rank = f"#{c['rank']} · " if c["rank"] else ""
            cor = GOOD if (c["var24"] or 0) >= 0 else BAD
            with a:
                _md(f'<div style="display:flex;align-items:center;gap:12px;">{img}<div>'
                    f'<div style="font-weight:800;color:{TEXT};">{esc(c["nome"])} ({esc(c["simbolo"])})</div>'
                    f'<div style="font-size:.8rem;color:{MUTED};">{rank}{_preco_usd(c["preco"])} · '
                    f'<span style="color:{cor};font-weight:700;">{_var(c["var24"])} em 24h</span> · '
                    f'7d {_var(c["var7"])} · Valor de mercado {usd(c["mcap"])}</div></div></div>')
            ja = c["id"] in sel
            b.button("✔ Adicionada" if ja else "➕ Adicionar", key=f"cripto_setor_add_{c['id']}",
                     on_click=_adicionar_cripto, args=(c["id"], c["nome"]), disabled=ja, width="stretch")


def _secao_setor(sel: list[str]):
    """Escolha de setor + lista das maiores moedas dele."""
    curados = setores_curados()
    rotulos = {n: cid for n, cid, _ in curados}
    OUTRO = "🔎 Outro setor (lista completa)"
    st.markdown("**Ou explore por setor**")
    escolha = st.selectbox("Setor", list(rotulos) + [OUTRO], index=None, key="cripto_setor_sel",
                           placeholder="Escolha um setor: DeFi, Layer 1, IA, Memecoins…",
                           label_visibility="collapsed", on_change=_zerar_n_setor)
    cid, nome_setor = None, ""
    if escolha == OUTRO:
        todos = listar_setores()
        if todos:
            cid = st.selectbox("Todos os setores", sorted(todos, key=lambda k: todos[k].lower()), index=None,
                               key="cripto_setor_all", format_func=lambda k: todos.get(k, k),
                               placeholder="Digite para procurar entre todos os setores (em inglês)",
                               label_visibility="collapsed", on_change=_zerar_n_setor)
            nome_setor = todos.get(cid, "") if cid else ""
        else:
            st.warning("Não consegui carregar a lista de setores agora. Tente de novo em instantes.")
    elif escolha:
        cid, nome_setor = rotulos[escolha], escolha
    if not cid:
        return
    n = st.session_state.get("cripto_setor_n", 10)
    espera = st.empty()
    espera.markdown(tema.skeleton(3), unsafe_allow_html=True)   # cartões fantasma enquanto carrega
    try:
        res = moedas_do_setor(cid, n)
    except ErroAPI as e:
        espera.empty()
        st.warning(f"Não consegui buscar esse setor agora ({e}). Tente de novo em instantes.")
        return
    espera.empty()
    if not res:
        _md(tema.vazio("caixa", "Nenhuma moeda encontrada neste setor",
                       "Tente outro setor ou use a lista completa."))
        return
    st.caption(f"{nome_setor}: as {len(res)} maiores por valor de mercado (CoinGecko).")
    _render_setor(res, sel)
    if len(res) >= n and n < 50:
        st.button("Ver mais 10", key="cripto_setor_mais", on_click=_mais_do_setor)


def pagina_cripto():
    st.markdown("### 🪙 Cripto / DeFi")
    st.caption("Pesquise qualquer criptomoeda pelo nome, símbolo ou setor (Bitcoin, Solana, DeFi, IA…), adicione quantas quiser e "
               "veja a análise com dados públicos da CoinGecko e do DefiLlama.")
    st.session_state.setdefault("cripto_ativos", [])
    st.session_state.setdefault("cripto_nomes", {})

    if not _chave_gecko():
        with st.expander("⚠️ Sem chave da CoinGecko: as consultas podem falhar com frequência. Como configurar (grátis)"):
            st.markdown(
                "Sem chave, a CoinGecko libera poucas consultas por minuto e o app pode mostrar erro de limite. "
                "A chave **Demo** é gratuita:\n\n"
                "1. Crie a conta e a chave em **coingecko.com/en/api/pricing** (plano Demo).\n"
                "2. Guarde a chave nos *secrets* do Streamlit. No computador, crie o arquivo `.streamlit/secrets.toml`; "
                "no Streamlit Cloud, use **Settings → Secrets**. Conteúdo:")
            st.code('COINGECKO_KEY = "cole-sua-chave-aqui"', language="toml")
            st.caption("Depois reinicie o app. A chave nunca fica no código nem aparece na tela.")

    # ---- busca por nome (igual às ações)
    with st.form("form_cripto_busca"):
        c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
        c1.text_input("Buscar moeda", key="cripto_q", label_visibility="collapsed",
                      placeholder="Nome, símbolo ou setor: Bitcoin, ETH, Uniswap, memecoins…")
        c2.form_submit_button("Buscar", type="primary", width="stretch")
    termo = (st.session_state.get("cripto_q") or "").strip()
    sel = st.session_state["cripto_ativos"]

    if termo:
        try:
            res = buscar_moedas(termo)
        except ErroAPI as e:
            res = None
            st.warning(f"Não consegui buscar agora ({e}). Tente de novo em instantes ou use um dos atalhos abaixo.")
        if res:
            _render_resultados(res, sel)
        elif res is not None:
            st.caption("Digite pelo menos 2 letras.") if len(_norm(termo)) < 2 else st.info(
                "Não encontrei essa moeda. Confira o nome ou tente o símbolo.")

    # ---- setores que combinam com o texto digitado (ex.: "meme", "ia", "layer")
    if termo:
        try:
            setores = buscar_setores(termo)
        except ErroAPI:
            setores = []
        if setores:
            st.caption("Setores com esse nome:")
            for col, (cid_s, nome_s) in zip(st.columns(min(len(setores), 3)), setores[:3]):
                col.button(f"📂 {nome_s}", key=f"cripto_setor_hit_{cid_s}", on_click=_escolher_setor,
                           args=(cid_s,), width="stretch")

    # ---- por setor
    _secao_setor(sel)

    # ---- atalhos populares
    st.caption("Ou comece por uma destas:")
    for linha in (list(POPULARES.items())[:4], list(POPULARES.items())[4:]):
        for col, (nome, gid) in zip(st.columns(4), linha):
            col.button(nome, key=f"cripto_pop_{gid}", on_click=_adicionar_cripto, args=(gid, nome),
                       disabled=gid in sel, width="stretch")

    # ---- moedas em análise (dá para remover pelo x)
    nomes = {**{v: k for k, v in POPULARES.items()}, **st.session_state["cripto_nomes"]}
    opcoes = list(dict.fromkeys(sel + list(POPULARES.values())))
    st.multiselect("Moedas em análise", options=opcoes, key="cripto_ativos",
                   format_func=lambda g: nomes.get(g) or g.replace("-", " ").title(),
                   placeholder="Nenhuma moeda ainda: busque acima ou escolha um atalho")
    sel = st.session_state["cripto_ativos"]
    if not sel:
        _md(tema.vazio("moeda", "Nenhuma moeda em análise",
                       "Busque pelo nome, símbolo ou setor e toque em Adicionar para ver a análise completa."))
        return

    mostrar = sel[:4]
    for gid in mostrar:
        st.divider()
        _mostrar_moeda(gid)
    if len(sel) > len(mostrar):
        st.caption(f"Mostrando {len(mostrar)} de {len(sel)} moedas, para não estourar o limite de consultas da "
                   "CoinGecko. Remova alguma da lista para ver as demais.")

    st.caption("Dados de mercado por [CoinGecko](https://www.coingecko.com) e de TVL e taxas pelo DefiLlama (dados "
               "públicos, cache de 10 minutos). Os limites dos indicadores são regras simples e educacionais; não são "
               "recomendação de investimento. Criptomoedas são muito voláteis e você pode perder todo o valor investido. "
               "Selo verde = positivo; amarelo = neutro ou atenção; vermelho = negativo; cinza = sem dados.")
