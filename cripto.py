"""
Análise fundamentalista de protocolos DeFi / criptoativos (página do Streamlit).

Fontes gratuitas, sem chave:
  - DefiLlama (https://api.llama.fi): TVL, taxas e volume
  - CoinGecko (https://api.coingecko.com/api/v3): Market Cap, FDV e supply

Uso no app.py:
    import cripto
    PG_DEFI = st.Page(cripto.pagina_cripto, title="Cripto / DeFi", icon="🪙", url_path="defi")

Não depende de nenhum outro módulo do projeto (só requests, pandas, plotly e streamlit).
Ferramenta educacional, não é recomendação de investimento.
"""
from __future__ import annotations

import time

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

LLAMA = "https://api.llama.fi"
GECKO = "https://api.coingecko.com/api/v3"
TIMEOUT = 20
HEADERS = {"User-Agent": "bolsa-para-todos/1.0", "Accept": "application/json"}

# Atalhos para quem não sabe o slug (slug do DefiLlama)
POPULARES = {
    "Uniswap": "uniswap", "Aave": "aave", "Lido": "lido", "MakerDAO / Sky": "sky-lending",
    "Curve": "curve-dex", "Compound": "compound-finance", "Pendle": "pendle", "Hyperliquid": "hyperliquid",
}

# Cores no mesmo tom do app
BRAND, ACCENT, GOOD, FAIR, BAD = "#1F7A55", "#3B6BC4", "#2E7D4F", "#A8650B", "#B83A3A"


class ErroAPI(Exception):
    """Falha ao consultar uma API externa."""


# ----------------------------------------------------------------- requisições
def _get_json(url: str, params: dict | None = None, tentativas: int = 3):
    """GET com timeout, retentativas e tratamento de erros (inclui 429 da CoinGecko)."""
    ultimo = ""
    for i in range(tentativas):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=TIMEOUT)
            if r.status_code == 429:
                ultimo = "limite de requisições atingido (HTTP 429)"
                time.sleep(min(int(r.headers.get("Retry-After", 4 * (i + 1))), 20))
                continue
            if r.status_code == 404:
                raise ErroAPI("não encontrado (HTTP 404)")
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


def _gecko_mercado(gecko_id: str) -> dict:
    d = _get_json(f"{GECKO}/coins/{gecko_id}", {
        "localization": "false", "tickers": "false", "community_data": "false",
        "developer_data": "false", "sparkline": "false"})
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


# ---------------------------------------------------------------------- página
def _grafico_tvl(hist: list) -> go.Figure | None:
    if len(hist) < 2:
        return None
    df = pd.DataFrame(hist, columns=["data", "tvl"])
    fig = go.Figure(go.Scatter(x=df["data"], y=df["tvl"], mode="lines", line=dict(color=ACCENT, width=2),
                               fill="tozeroy", fillcolor="rgba(59,107,196,0.10)",
                               hovertemplate="%{x|%d/%m/%Y}<br>TVL: US$ %{y:,.0f}<extra></extra>"))
    fig.update_layout(height=300, margin=dict(l=0, r=0, t=10, b=0), paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)", showlegend=False, yaxis=dict(title="TVL (US$)", gridcolor="#D5DAE0"),
                      xaxis=dict(gridcolor="#D5DAE0"))
    return fig


def _mostrar_alerta(nivel: str, texto: str):
    {"ok": st.success, "aviso": st.warning, "ruim": st.error, "info": st.info}[nivel](texto)


def pagina_cripto():
    st.markdown("### 🪙 Cripto / DeFi")
    st.caption("Análise fundamentalista de protocolos DeFi com dados públicos do DefiLlama e da CoinGecko. "
               "Informe o nome do protocolo como aparece no DefiLlama (ex.: uniswap, aave, lido).")

    with st.form("form_defi"):
        c1, c2, c3 = st.columns([2, 2, 1], vertical_alignment="bottom")
        escolha = c1.selectbox("Protocolos populares", ["(digitar outro)"] + list(POPULARES), key="defi_pop")
        livre = c2.text_input("Ou digite o slug", key="defi_slug", placeholder="ex.: uniswap")
        enviar = c3.form_submit_button("Analisar", type="primary", width="stretch")

    if enviar:
        slug = (livre or "").strip().lower() or POPULARES.get(escolha, "")
        st.session_state["defi_ativo"] = slug
    slug = st.session_state.get("defi_ativo", "")
    if not slug:
        st.info("Escolha um protocolo da lista ou digite o slug e clique em **Analisar**.")
        return

    try:
        with st.spinner(f"Consultando DefiLlama e CoinGecko para “{slug}”…"):
            a = analisar_protocolo(slug)
    except ErroAPI as e:
        st.error(f"{e} Confira o slug em defillama.com/protocols (ex.: uniswap, aave, lido).")
        return
    except Exception as e:  # erro inesperado não derruba o app
        st.error(f"Erro inesperado ao analisar “{slug}”: {e.__class__.__name__}.")
        return

    titulo = a["nome"] + (f" ({a['simbolo']})" if a["simbolo"] else "")
    st.markdown(f"#### {titulo}")
    st.caption(f"Categoria: {a['categoria'] or 'n/d'}" + (f" · Preço do token: US$ {a['preco']:,.4f}" if a["preco"] else ""))
    for av in a["avisos"]:
        st.warning(av)

    st.markdown("**Alertas de valuation**")
    for nivel, texto in alertas(a):
        _mostrar_alerta(nivel, texto)

    st.markdown("**1. Tokenomics**")
    k = st.columns(3)
    k[0].metric("Market Cap", usd(a["mcap"]), help="Valor de mercado dos tokens em circulação.")
    k[1].metric("FDV", usd(a["fdv"]), help="Valor se todos os tokens (inclusive os ainda não liberados) já circulassem.")
    k[2].metric("Market Cap / FDV", _pct(a["mc_fdv"]),
                help="Quanto do FDV já circula. Quanto menor, maior o risco de diluição por novos tokens.")

    st.markdown("**2. On-chain / DeFi**")
    k = st.columns(3)
    k[0].metric("TVL atual", usd(a["tvl"]), help="Total Value Locked: valor depositado no protocolo.")
    k[1].metric("Taxas (30 dias)", usd(a["fees30"]), help="Taxas pagas pelos usuários do protocolo nos últimos 30 dias.")
    k[2].metric("Volume (30 dias)", usd(a["vol30"]), help="Só existe para corretoras descentralizadas (DEX).")

    st.markdown("**3. Valuation**")
    k = st.columns(3)
    k[0].metric("Taxas anualizadas", usd(a["fees_anuais"]), help="Taxas de 30 dias × 365/30.")
    k[1].metric("Preço/Taxas", _x(a["p_taxas"], 1), help="Market Cap ÷ taxas anuais. Parecido com o P/L das ações: quanto menor, mais barato.")
    k[2].metric("Market Cap / TVL", _x(a["mc_tvl"], 2), help="Abaixo de 1: o token vale menos que o capital depositado.")

    fig = _grafico_tvl(a["hist_tvl"])
    if fig:
        st.markdown("**Evolução do TVL**")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.caption("Fontes: DefiLlama e CoinGecko (dados públicos, cache de 10 minutos). Os limites dos alertas são regras "
               "simples e educacionais (Market Cap/TVL, diluição e Preço/Taxas); não são recomendação de investimento. "
               "Market Cap/TVL pode enganar em protocolos de liquid staking.")
