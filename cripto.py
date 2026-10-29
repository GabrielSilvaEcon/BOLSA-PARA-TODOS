"""
Análise fundamentalista de protocolos DeFi / criptoativos (página do Streamlit).

Fontes gratuitas, sem chave:
  - DefiLlama (https://api.llama.fi): lista de protocolos (busca por nome), TVL, taxas e volume
  - CoinGecko (https://api.coingecko.com/api/v3): Market Cap, FDV e supply

Uso no app.py:
    import cripto
    PG_DEFI = st.Page(cripto.pagina_cripto, title="Cripto / DeFi", icon="🪙", url_path="defi")

Não depende de nenhum outro módulo do projeto (só requests, pandas, plotly e streamlit).
Ferramenta educacional, não é recomendação de investimento.
"""
from __future__ import annotations

import html as _html
import re
import time
import unicodedata

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
TEXT, MUTED, BORDER, SURFACE = "#1F2933", "#5B6675", "#D5DAE0", "#F9FAFB"

# classe visual -> (cor do texto/borda, cor de fundo do selo)
COR_CLS = {"good": (GOOD, "rgba(46,125,79,.14)"), "fair": (FAIR, "rgba(168,101,11,.14)"),
           "bad": (BAD, "rgba(184,58,58,.14)"), "na": (MUTED, "rgba(91,102,117,.16)")}
ICONE_STATUS = {"Positivo": "✅", "Neutro": "➖", "Atenção": "⚠️", "Negativo": "❌", "Sem dados": "❔"}


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
    """Todos os protocolos do DefiLlama (nome, slug, símbolo, categoria, TVL, logo), do maior TVL ao menor.
    Levanta ErroAPI se a API não responder (erro não fica em cache)."""
    dados = _get_json(f"{LLAMA}/protocols", tentativas=2)
    if not isinstance(dados, list):
        raise ErroAPI("resposta inesperada do DefiLlama")
    out = []
    for p in dados:
        if not isinstance(p, dict) or not p.get("slug") or p.get("category") == "CEX":
            continue
        tvl = p.get("tvl")
        out.append({
            "slug": p["slug"], "nome": p.get("name") or p["slug"], "simbolo": p.get("symbol") or "",
            "categoria": p.get("category") or "", "tvl": float(tvl) if isinstance(tvl, (int, float)) else None,
            "logo": p.get("logo") or "",
            "_n": _norm(p.get("name")), "_s": _norm(p["slug"]), "_y": _norm(p.get("symbol")),
        })
    out.sort(key=lambda x: x["tvl"] or 0, reverse=True)
    return out


def buscar_protocolos(termo: str, lista: list[dict], limite: int = 6) -> list[dict]:
    """Procura por nome, slug ou símbolo. Primeiro o que bate exato, depois o que começa com o termo,
    depois o que contém; em empate, o de maior TVL aparece antes."""
    q = _norm(termo)
    if len(q) < 2:
        return []
    achados = []
    for p in lista:
        nome, slug, sim = p["_n"], p["_s"], p["_y"]
        if q in (nome, slug, sim):
            pts = 0
        elif nome.startswith(q) or slug.startswith(q) or sim.startswith(q):
            pts = 1
        elif q in nome or q in slug:
            pts = 2
        elif all(w in nome for w in q.split()):
            pts = 3
        else:
            continue
        achados.append((pts, -(p["tvl"] or 0), p))
    achados.sort(key=lambda x: (x[0], x[1]))
    return [p for _, _, p in achados[:limite]]


def _adicionar_defi(slug: str):
    sel = st.session_state.get("defi_ativos", [])
    if slug not in sel:
        st.session_state["defi_ativos"] = sel + [slug]


def _render_resultados(res: list[dict], sel: list[str]):
    """Um cartão por protocolo achado, com logo, categoria, TVL e botão de adicionar."""
    esc = _html.escape
    for p in res:
        with st.container(border=True):
            a, b = st.columns([5, 1.5], vertical_alignment="center")
            logo = p.get("logo") or ""
            img = (f'<img src="{esc(logo)}" width="38" height="38" style="border-radius:10px;background:#fff;'
                   f'padding:3px;border:1px solid {BORDER};object-fit:contain;flex-shrink:0;">'
                   if logo.startswith("https://") else "")
            sim = f" ({esc(p['simbolo'])})" if p["simbolo"] and p["simbolo"] != "-" else ""
            cat = esc(p["categoria"] or "n/d")
            with a:
                _md(f'<div style="display:flex;align-items:center;gap:12px;">{img}<div>'
                    f'<div style="font-weight:800;color:{TEXT};">{esc(p["nome"])}{sim}</div>'
                    f'<div style="font-size:.8rem;color:{MUTED};">{cat} · TVL {usd(p["tvl"])}</div></div></div>')
            ja = p["slug"] in sel
            b.button("✔ Adicionado" if ja else "➕ Adicionar", key=f"defi_add_{p['slug']}",
                     on_click=_adicionar_defi, args=(p["slug"],), disabled=ja, width="stretch")


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


def _mostrar_protocolo(slug: str):
    """Analisa e exibe um protocolo (quadrados, números detalhados e gráfico do TVL)."""
    try:
        with st.spinner(f"Consultando DefiLlama e CoinGecko para “{slug}”…"):
            a = analisar_protocolo(slug)
    except ErroAPI as e:
        st.error(f"{e} Confira o nome em defillama.com/protocols ou remova da lista.")
        return
    except Exception as e:  # erro inesperado não derruba o app
        st.error(f"Erro inesperado ao analisar “{slug}”: {e.__class__.__name__}.")
        return

    titulo = a["nome"] + (f" ({a['simbolo']})" if a["simbolo"] else "")
    st.markdown(f"#### {titulo}")
    st.caption(f"Categoria: {a['categoria'] or 'n/d'}" + (f" · Preço do token: US$ {a['preco']:,.4f}" if a["preco"] else ""))
    for av in a["avisos"]:
        st.warning(av)

    cards = indicadores(a)
    st.markdown("**Resumo dos indicadores**")
    _resumo_geral(cards)
    for linha in (cards[:3], cards[3:]):
        for col, c in zip(st.columns(3), linha):
            with col:
                _md(_html_card(c))

    with st.expander("Ver todos os números e alertas detalhados"):
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
        st.plotly_chart(fig, width="stretch", key=f"defi_tvl_{slug}", config={"displayModeBar": False})


def pagina_cripto():
    st.markdown("### 🪙 Cripto / DeFi")
    st.caption("Pesquise o protocolo pelo nome (ex.: Uniswap, Aave, Lido), adicione quantos quiser e veja a análise "
               "fundamentalista com dados públicos do DefiLlama e da CoinGecko.")
    st.session_state.setdefault("defi_ativos", [])

    try:
        with st.spinner("Carregando a lista de protocolos…"):
            lista = listar_protocolos()
    except Exception:
        lista = []
    nomes = {p["slug"]: p["nome"] for p in lista}

    # ---- busca por nome (igual às ações)
    with st.form("form_defi_busca"):
        c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
        c1.text_input("Buscar protocolo", key="defi_q", label_visibility="collapsed",
                      placeholder="Digite o nome ou o símbolo: Uniswap, Aave, Lido, Pendle…")
        c2.form_submit_button("Buscar", type="primary", width="stretch")
    termo = (st.session_state.get("defi_q") or "").strip()
    sel = st.session_state["defi_ativos"]

    if termo:
        if not lista:
            st.warning("Não consegui carregar a lista do DefiLlama agora, então a busca por nome está indisponível. "
                       "Você ainda pode tentar o nome exato do protocolo abaixo.")
            res = []
        else:
            res = buscar_protocolos(termo, lista)
            if res:
                _render_resultados(res, sel)
            elif len(_norm(termo)) < 2:
                st.caption("Digite pelo menos 2 letras.")
            else:
                st.info("Não encontrei esse protocolo. Confira o nome ou tente o símbolo. Aqui entram protocolos DeFi "
                        "(DefiLlama); moedas como Bitcoin, que não têm TVL, em geral não aparecem.")
        slug_tentativa = re.sub(r"[^a-z0-9.\-]+", "-", termo.lower()).strip("-")
        if slug_tentativa and slug_tentativa not in sel:
            st.button(f"Tentar “{slug_tentativa}” como nome exato do DefiLlama", key="defi_tentar",
                      on_click=_adicionar_defi, args=(slug_tentativa,))

    # ---- atalhos populares
    st.caption("Ou comece por um destes:")
    for linha in (list(POPULARES.items())[:4], list(POPULARES.items())[4:]):
        for col, (nome, slug) in zip(st.columns(4), linha):
            col.button(nome, key=f"defi_pop_{slug}", on_click=_adicionar_defi, args=(slug,),
                       disabled=slug in sel, width="stretch")

    # ---- protocolos em análise (dá para remover pelo x)
    opcoes = list(dict.fromkeys(sel + list(POPULARES.values())))
    st.multiselect("Protocolos em análise", options=opcoes, key="defi_ativos",
                   format_func=lambda s: nomes.get(s) or s,
                   placeholder="Nenhum protocolo ainda: busque acima ou escolha um atalho")
    sel = st.session_state["defi_ativos"]
    if not sel:
        st.info("Busque um protocolo pelo nome e clique em **➕ Adicionar** para ver a análise.")
        return

    mostrar = sel[:4]
    for slug in mostrar:
        st.divider()
        _mostrar_protocolo(slug)
    if len(sel) > len(mostrar):
        st.caption(f"Mostrando {len(mostrar)} de {len(sel)} protocolos, para não estourar o limite de consultas da "
                   "CoinGecko. Remova algum da lista para ver os demais.")

    st.caption("Fontes: DefiLlama e CoinGecko (dados públicos, cache de 10 minutos). Os limites dos alertas são regras "
               "simples e educacionais (Market Cap/TVL, diluição e Preço/Taxas); não são recomendação de investimento. "
               "Market Cap/TVL pode enganar em protocolos de liquid staking. Selo verde = positivo; "
               "amarelo = neutro ou atenção; vermelho = negativo; cinza = sem dados.")