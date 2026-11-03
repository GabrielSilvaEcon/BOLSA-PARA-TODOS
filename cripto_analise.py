"""Inteligência avançada para criptomoedas (Passo 9) — funções PURAS (sem Streamlit e sem rede).

Recebem dados já coletados (CoinGecko, DefiLlama, blockchain.com, GitHub) e devolvem classificação, indicadores,
tokenomics, valuation, riscos, histórico, alertas, relatório e análise de carteira.

Regras de honestidade (as mesmas do Passo 8):
- nada é inventado: o que não tem fonte integrada aparece como "sem fonte", nunca como zero ou "ok";
- cada indicador carrega origem, tipo (provedor / calculado / registrado na blockchain) e data;
- alerta só nasce de dado verificável; evento de desbloqueio só entra com fonte informada;
- "tem auditoria" nunca vira "é seguro"; múltiplo baixo nunca vira "barato".
"""
from __future__ import annotations

import math
import re
from datetime import date, datetime, timezone

import pandas as pd

# --------------------------------------------------------------------------------------- classificação
CATEGORIAS = {
    "layer1": "Layer 1", "layer2": "Layer 2", "defi": "DeFi", "stablecoin": "Stablecoin", "oraculo": "Oráculo",
    "infra": "Infraestrutura", "ia": "Inteligência artificial", "gaming": "Gaming", "metaverso": "Metaverso",
    "rwa": "RWA (ativos do mundo real)", "meme": "Memecoin", "exchange": "Token de exchange",
    "staking": "Protocolo de staking", "governanca": "Token de governança", "outros": "Outros segmentos",
}

# termos (em minúsculas) procurados em cada rótulo de categoria da CoinGecko / DefiLlama
_TERMOS = {
    "layer1": ("layer 1", "smart contract platform"),
    "layer2": ("layer 2", "rollup", "zero knowledge", "zk rollup", "optimistic rollup"),
    "defi": ("decentralized finance", "defi", "decentralized exchange", "dex", "lending", "borrowing", "yield",
             "derivatives", "automated market maker", "amm", "perpetual", "yield aggregator", "stablecoin protocol",
             "liquidity"),
    "stablecoin": ("stablecoins", "usd stablecoin", "eur stablecoin", "fiat-backed stablecoin",
                   "crypto-backed stablecoin", "algorithmic stablecoin", "gold stablecoin", "yield-bearing stablecoin"),
    "oraculo": ("oracle",),
    "infra": ("infrastructure", "layer 0", "interoperability", "data availability", "depin", "storage",
              "cross-chain communication", "identity"),
    "ia": ("artificial intelligence", "ai agent", "ai framework", "ai applications", "ai big data"),
    "gaming": ("gaming", "play to earn", "gamefi"),
    "metaverso": ("metaverse",),
    "rwa": ("real world assets", "rwa", "tokenized"),
    "meme": ("meme",),
    "exchange": ("exchange-based", "cex token", "centralized exchange"),
    "staking": ("liquid staking", "staking"),
    "governanca": ("governance",),
}

# lista curada (id da CoinGecko): vale mesmo se a CoinGecko não rotular a moeda
_CURADO = {
    "layer1": {"bitcoin", "ethereum", "solana", "cardano", "avalanche-2", "polkadot", "near", "cosmos", "tron",
               "aptos", "sui", "the-open-network", "algorand", "binancecoin", "litecoin", "ripple", "stellar",
               "dogecoin", "bitcoin-cash", "monero", "internet-computer", "hedera-hashgraph", "kaspa"},
    "layer2": {"arbitrum", "optimism", "matic-network", "polygon-ecosystem-token", "starknet", "mantle",
               "immutable-x", "loopring", "blast", "zksync", "base"},
    "stablecoin": {"tether", "usd-coin", "dai", "first-digital-usd", "usds", "ethena-usde", "true-usd",
                   "paypal-usd", "frax", "usdd", "paxos-standard", "gemini-dollar", "stasis-eurs", "euro-coin"},
    "oraculo": {"chainlink", "band-protocol", "pyth-network", "api3", "uma"},
    "meme": {"dogecoin", "shiba-inu", "pepe", "dogwifcoin", "bonk", "floki"},
    "exchange": {"binancecoin", "crypto-com-chain", "okb", "leo-token", "kucoin-shares", "gate", "bitget-token"},
    "staking": {"lido-dao", "rocket-pool", "frax-share"},
    "governanca": {"uniswap", "aave", "maker", "compound-governance-token", "curve-dao-token", "lido-dao"},
    "defi": {"uniswap", "aave", "maker", "compound-governance-token", "curve-dao-token", "lido-dao", "pancakeswap-token"},
}

# ordem para escolher a categoria "principal" (a que define com quem comparar)
PRIORIDADE = ("stablecoin", "layer2", "layer1", "staking", "defi", "oraculo", "rwa", "ia", "gaming", "metaverso",
              "exchange", "meme", "infra", "governanca", "outros")

# família = modelo econômico. Valuation e comparação só fazem sentido dentro da mesma família.
FAMILIAS = {
    "stablecoin": "Moeda estável (valor ancorado)",
    "layer1": "Rede / infraestrutura", "layer2": "Rede / infraestrutura", "infra": "Rede / infraestrutura",
    "defi": "Protocolo com receita", "staking": "Protocolo com receita", "oraculo": "Protocolo com receita",
    "exchange": "Protocolo com receita", "governanca": "Protocolo com receita", "rwa": "Ativo tokenizado",
    "meme": "Narrativa / especulativo", "ia": "Narrativa / especulativo", "gaming": "Narrativa / especulativo",
    "metaverso": "Narrativa / especulativo", "outros": "Outros",
}

UTILIDADE = {
    "layer1": "Paga as taxas da rede, remunera quem a protege (mineração/staking) e, em geral, é a moeda base do ecossistema.",
    "layer2": "Usado para taxas, segurança ou governança de uma rede que roda sobre outra blockchain (Layer 1).",
    "defi": "Participa de um protocolo financeiro (troca, empréstimo, derivativos): pode dar voto, desconto, incentivo ou direito a receita.",
    "stablecoin": "Busca manter valor estável (geralmente US$ 1) para pagamentos, reserva e negociação. Não é feita para valorizar.",
    "oraculo": "Remunera quem leva dados do mundo externo para contratos inteligentes; a demanda depende de quanto o serviço é usado.",
    "infra": "Paga por serviços de rede (armazenamento, dados, conexão entre blockchains); a utilidade depende do uso do serviço.",
    "ia": "Ligado a projetos de inteligência artificial; a utilidade varia muito e costuma depender da narrativa.",
    "gaming": "Moeda ou ativo dentro de jogos; a demanda depende de haver jogadores ativos.",
    "metaverso": "Moeda ou ativo de mundos virtuais; a demanda depende da base de usuários.",
    "rwa": "Representa ativos fora da blockchain (títulos, imóveis, ouro); o risco inclui o emissor e a custódia.",
    "meme": "Sem utilidade econômica própria definida: o preço depende de atenção, comunidade e especulação.",
    "exchange": "Dá descontos e benefícios numa exchange; depende da saúde e da regulação dessa empresa.",
    "staking": "Representa ou governa ativos em staking; o risco inclui contratos, validadores e desvio de preço do ativo base.",
    "governanca": "Dá direito de voto sobre o protocolo; só tem valor econômico se o protocolo devolver receita ao token.",
    "outros": "Categoria não identificada pelas fontes: a utilidade do token precisa ser verificada na documentação do projeto.",
}


def _casa(item: str, termo: str) -> bool:
    return re.search(r"(?<![a-z0-9])" + re.escape(termo) + r"s?(?![a-z0-9])", item) is not None


def classificar(gecko_id: str, categorias: list[str] | None = None, categoria_llama: str | None = None) -> list[dict]:
    """Todas as categorias do projeto (multi-rótulo): [{chave, rotulo, motivo}]. Sem nenhuma pista → 'outros'."""
    gid = (gecko_id or "").lower()
    itens = [str(c).lower().replace("decentralized", "dec_") for c in (categorias or []) if c]
    if categoria_llama:
        itens.append(str(categoria_llama).lower())
    achadas: dict[str, str] = {}
    for chave, termos in _TERMOS.items():
        for it in itens:
            t = next((t for t in termos if _casa(it, t.replace("decentralized", "dec_"))), None)
            if t:
                achadas.setdefault(chave, f"rótulo “{it.replace('dec_', 'decentralized')}” (CoinGecko/DefiLlama)")
                break
    # "dec_ exchange" deve virar DeFi (DEX), não token de exchange: o termo foi mascarado acima
    for chave, ids in _CURADO.items():
        if gid in ids:
            achadas.setdefault(chave, "lista curada do app")
    if "dec_ exchange" in " ".join(itens):
        achadas.setdefault("defi", "rótulo “decentralized exchange” (CoinGecko)")
    # stablecoin não é DeFi nem rede só por ter "yield"/"liquidity" no rótulo
    if "stablecoin" in achadas and achadas.get("defi", "").startswith("rótulo") and gid in _CURADO["stablecoin"]:
        achadas.pop("defi", None)
    if not achadas:
        achadas["outros"] = "nenhum rótulo reconhecido nas fontes"
    ordem = [c for c in PRIORIDADE if c in achadas]
    return [{"chave": c, "rotulo": CATEGORIAS[c], "motivo": achadas[c]} for c in ordem]


def principal(classes: list[dict] | list[str]) -> str:
    chaves = [c["chave"] if isinstance(c, dict) else c for c in classes]
    return next((p for p in PRIORIDADE if p in chaves), "outros")


def categoria_para_pares(categorias: list[str] | None, princ: str) -> str | None:
    """Rótulo da CoinGecko mais específico que define a categoria principal (para buscar concorrentes). None se não há."""
    termos = _TERMOS.get(princ, ())
    for c in categorias or []:
        it = str(c).lower().replace("decentralized", "dec_")
        if any(_casa(it, t.replace("decentralized", "dec_")) for t in termos):
            return c
    return None


def familia(chave: str) -> str:
    return FAMILIAS.get(chave, "Outros")


def compatibilidade(principais: dict[str, str]) -> list[str]:
    """{nome: categoria principal} → avisos sobre misturar modelos econômicos incompatíveis. [] = comparação coerente."""
    avisos = []
    fams = {n: familia(p) for n, p in principais.items()}
    distintas = set(fams.values())
    if len(distintas) <= 1:
        return avisos
    if "Moeda estável (valor ancorado)" in distintas:
        avisos.append("Há stablecoin na comparação: ela busca manter o preço fixo, então retorno, volatilidade e "
                      "valuation não são comparáveis com os dos demais. Compare stablecoins entre si (lastro, liquidez, desvio do preço-alvo).")
    if "Narrativa / especulativo" in distintas and len(distintas) > 1:
        avisos.append("Há ativo de narrativa (memecoin, IA, gaming ou metaverso) junto de projetos com atividade econômica "
                      "mensurável: múltiplos como Preço/Taxas e Valor de mercado/TVL não valem para o primeiro.")
    if {"Rede / infraestrutura", "Protocolo com receita"} <= distintas:
        avisos.append("Rede (Layer 1/2) e protocolo de aplicação têm modelos de receita diferentes: use os múltiplos "
                      "com cautela e prefira compará-los dentro do mesmo grupo.")
    if not avisos:
        avisos.append("Os projetos pertencem a famílias econômicas diferentes: a comparação é só indicativa.")
    avisos.append("Categorias: " + "; ".join(f"{n} → {CATEGORIAS.get(p, p)} ({fams[n]})" for n, p in principais.items()))
    return avisos


# --------------------------------------------------------------------------------------- utilidades numéricas
def _num(v) -> float | None:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def _razao(a, b) -> float | None:
    a, b = _num(a), _num(b)
    return a / b if a is not None and b not in (None, 0) else None


def _md(raw: dict | None, chave: str, moeda: str = "usd"):
    d = ((raw or {}).get("market_data") or {}).get(chave)
    return _num(d.get(moeda)) if isinstance(d, dict) else _num(d)


def _data_iso(v) -> str | None:
    if not v:
        return None
    try:
        return str(v)[:10]
    except Exception:
        return None


def _linha(chave, rotulo, valor, fmt, fonte, tipo, data=None, nota=""):
    return {"chave": chave, "rotulo": rotulo, "valor": valor, "fmt": fmt, "fonte": fonte, "tipo": tipo,
            "data": data, "nota": nota}


TIPOS = {"provedor": "dado do provedor", "calculado": "calculado pelo app", "blockchain": "registrado na blockchain",
         "estimativa": "estimativa de provedor", "sem_fonte": "sem fonte"}


# --------------------------------------------------------------------------------------- mercado
def mercado(raw: dict | None, glob: dict | None = None, hist: list | None = None) -> dict:
    """Indicadores de mercado de uma moeda. raw = JSON de /coins/{id} (CoinGecko); glob = {total_mcap, data};
    hist = [(timestamp, preço)] diário (365 dias). Devolve {linhas, calc, avisos, fonte, data}."""
    avisos: list[str] = []
    fonte = "CoinGecko"
    data = _data_iso((raw or {}).get("last_updated") or ((raw or {}).get("market_data") or {}).get("last_updated"))
    preco, mc = _md(raw, "current_price"), _md(raw, "market_cap")
    fdv_prov = _md(raw, "fully_diluted_valuation")
    vol = _md(raw, "total_volume")
    md = (raw or {}).get("market_data") or {}
    circ, total, maximo = _num(md.get("circulating_supply")), _num(md.get("total_supply")), _num(md.get("max_supply"))
    if maximo is not None and maximo <= 0:
        maximo = None
    if total is not None and total <= 0:
        total = None

    if not mc and preco and circ:
        mc, nota_mc = preco * circ, "calculado: preço × oferta circulante"
    else:
        nota_mc = ""
    fdv, nota_fdv = fdv_prov or None, ""
    if not fdv and preco and (maximo or total):
        fdv = preco * (maximo or total)
        nota_fdv = "calculado: preço × " + ("oferta máxima" if maximo else "oferta total")
    if mc and preco and circ and abs(preco * circ / mc - 1) > 0.15:
        avisos.append("O valor de mercado do provedor difere mais de 15% de preço × oferta circulante: "
                      "o provedor pode usar uma oferta circulante diferente da informada.")
    if circ and total and circ > total * 1.001:
        avisos.append("A oferta circulante informada é maior que a oferta total: dado inconsistente na fonte.")
    if circ and maximo and circ > maximo * 1.001:
        avisos.append("A oferta circulante informada é maior que a oferta máxima: dado inconsistente na fonte.")

    calc = {
        "preco": preco, "mcap": mc, "fdv": fdv, "vol24": vol, "circ": circ, "total": total, "maximo": maximo,
        "mc_fdv": _razao(mc, fdv), "fdv_mc": _razao(fdv, mc),
        "giro": _razao(vol, mc),                                   # volume ÷ valor de mercado
        "circ_max": _razao(circ, maximo), "circ_total": _razao(circ, total),
        "teto_definido": maximo is not None,
        "ath": _md(raw, "ath"), "atl": _md(raw, "atl"),
        "ath_data": _data_iso(((md.get("ath_date") or {}) if isinstance(md.get("ath_date"), dict) else {}).get("usd")),
        "atl_data": _data_iso(((md.get("atl_date") or {}) if isinstance(md.get("atl_date"), dict) else {}).get("usd")),
        "var24": _num(md.get("price_change_percentage_24h")), "var7": _num(md.get("price_change_percentage_7d")),
        "var30": _num(md.get("price_change_percentage_30d")), "var1a": _num(md.get("price_change_percentage_1y")),
        "rank": (raw or {}).get("market_cap_rank"),
    }
    calc["queda_ath"] = ((preco / calc["ath"] - 1) * 100) if preco and calc["ath"] else None
    calc["alta_atl"] = ((preco / calc["atl"] - 1) * 100) if preco and calc["atl"] else None
    tot = _num((glob or {}).get("total_mcap"))
    calc["dominancia"] = (mc / tot * 100) if mc and tot else None
    if hist:
        s = serie_de_pares(hist)
        calc["vol_anual"] = volatilidade(s)
        calc["dd_max"] = drawdown_maximo(s)
        calc["dd_atual"] = drawdown_atual(s)
    else:
        calc["vol_anual"] = calc["dd_max"] = calc["dd_atual"] = None

    L = []
    L.append(_linha("preco", "Preço atual", preco, "usd_p", fonte, "provedor", data))
    L.append(_linha("mcap", "Capitalização de mercado", mc, "usd", fonte, "calculado" if nota_mc else "provedor", data, nota_mc))
    L.append(_linha("fdv", "FDV (valor totalmente diluído)", fdv, "usd", fonte, "calculado" if nota_fdv else "provedor", data,
                    nota_fdv or ("Sem oferta máxima nem total informada: FDV indisponível." if not fdv else "")))
    L.append(_linha("mc_fdv", "Valor de mercado ÷ FDV", calc["mc_fdv"], "ratio", fonte, "calculado", data,
                    "Quanto mais perto de 1, menor a parte da oferta ainda por entrar em circulação."))
    L.append(_linha("vol24", "Volume negociado (24 h)", vol, "usd", fonte, "provedor", data,
                    "Soma das exchanges que a CoinGecko monitora; pode incluir volume inflado em exchanges pouco confiáveis."))
    L.append(_linha("giro", "Liquidez: volume ÷ valor de mercado", calc["giro"], "pct_f", fonte, "calculado", data,
                    "Giro diário. Profundidade do livro de ofertas e spread não têm fonte integrada."))
    L.append(_linha("circ", "Oferta circulante", circ, "qtd", fonte, "provedor", data))
    L.append(_linha("total", "Oferta total", total, "qtd", fonte, "provedor", data,
                    "" if total else "O provedor não informa a oferta total."))
    L.append(_linha("maximo", "Oferta máxima", maximo, "qtd", fonte, "provedor", data,
                    "" if maximo else "Sem teto informado: pode ser oferta ilimitada ou dado ausente na fonte."))
    for ch, rot in (("var24", "Variação 24 h"), ("var7", "Variação 7 dias"), ("var30", "Variação 30 dias"),
                    ("var1a", "Variação 1 ano")):
        L.append(_linha(ch, rot, calc[ch], "pct_s", fonte, "provedor", data))
    L.append(_linha("vol_anual", "Volatilidade anualizada (365 d)", calc["vol_anual"], "pct_f", fonte, "calculado", data,
                    "Desvio-padrão dos retornos diários × √365 (cripto negocia todos os dias)."))
    L.append(_linha("ath", "Máxima histórica", calc["ath"], "usd_p", fonte, "provedor", calc["ath_data"]))
    L.append(_linha("atl", "Mínima histórica", calc["atl"], "usd_p", fonte, "provedor", calc["atl_data"]))
    L.append(_linha("queda_ath", "Distância da máxima histórica", calc["queda_ath"], "pct_s", fonte, "calculado", data))
    L.append(_linha("dd_max", "Drawdown máximo (365 d)", calc["dd_max"], "pct_s", fonte, "calculado", data,
                    "Maior queda de um pico até o vale dentro dos últimos 365 dias."))
    L.append(_linha("dd_atual", "Drawdown atual (365 d)", calc["dd_atual"], "pct_s", fonte, "calculado", data))
    L.append(_linha("dominancia", "Dominância de mercado", calc["dominancia"], "pct_f", "CoinGecko (/global)", "calculado",
                    _data_iso((glob or {}).get("data")),
                    "" if tot else "Valor de mercado total indisponível agora: dominância não calculada."))
    return {"linhas": L, "calc": calc, "avisos": avisos, "fonte": fonte, "data": data}


# --------------------------------------------------------------------------------------- séries
def serie_de_pares(hist, permitir_zero: bool = False) -> pd.Series:
    """[(timestamp ou data, valor)] → Series diária ordenada, sem duplicatas e sem valores não positivos
    (permitir_zero=True mantém dias com valor 0, como taxas de um dia sem atividade)."""
    pts = []
    for t, v in (hist or []):
        v = _num(v)
        if v is None or v < 0 or (v == 0 and not permitir_zero):
            continue
        try:
            tn = _num(t) if not isinstance(t, (pd.Timestamp, datetime, date, str)) else None
            if tn is not None:
                idx = pd.to_datetime(tn, unit="ms" if tn > 1e11 else "s")
            else:
                idx = pd.to_datetime(t)
        except Exception:
            continue
        pts.append((idx, v))
    if not pts:
        return pd.Series(dtype=float)
    s = pd.Series([v for _, v in pts], index=[i for i, _ in pts]).sort_index()
    s.index = pd.DatetimeIndex(s.index).tz_localize(None) if pd.DatetimeIndex(s.index).tz is not None else s.index
    s.index = s.index.normalize()
    return s[~s.index.duplicated(keep="last")]


def _limpa(s) -> pd.Series:
    if s is None or len(s) == 0:
        return pd.Series(dtype=float)
    s = pd.Series(s).astype(float).dropna()
    return s[s > 0].sort_index()


def volatilidade(s, minimo: int = 60) -> float | None:
    """Volatilidade anualizada em % (retornos diários × √365). None com menos de `minimo` pontos."""
    s = _limpa(s)
    if len(s) < minimo:
        return None
    r = s.pct_change().dropna()
    v = r.std()
    return float(v * math.sqrt(365) * 100) if pd.notna(v) else None


def drawdown_maximo(s, minimo: int = 30) -> float | None:
    s = _limpa(s)
    if len(s) < minimo:
        return None
    return float(((s / s.cummax()) - 1).min() * 100)


def drawdown_atual(s, minimo: int = 30) -> float | None:
    s = _limpa(s)
    if len(s) < minimo:
        return None
    return float((s.iloc[-1] / s.max() - 1) * 100)


def variacao(s, dias: int, tol: int = 5) -> float | None:
    """Variação % entre o último ponto e o ponto mais recente que tenha pelo menos `dias` dias de idade.
    Aceita até `tol` dias a menos (séries diárias de "365 dias" têm 364 dias de extensão)."""
    s = _limpa(s)
    if len(s) < 2:
        return None
    alvo = s.index[-1] - pd.Timedelta(days=dias)
    ant = s[s.index <= alvo]
    if ant.empty and (s.index[0] - alvo).days <= tol:
        ant = s.iloc[:1]
    if ant.empty:
        return None
    return float((s.iloc[-1] / ant.iloc[-1] - 1) * 100)


def cagr(s, minimo_dias: int = 360) -> dict:
    """CAGR com datas reais: (v1/v0)^(1/anos) − 1, anos = dias/365,25. Exige início > 0 e ≥ `minimo_dias` de dados.
    Com ~1 ano de dados o CAGR é igual ao retorno do período (isso é dito em 'nota')."""
    s = _limpa(s)
    vazio = {"cagr": None, "anos": None, "inicio": None, "fim": None, "nota": "Histórico insuficiente para o CAGR."}
    if len(s) < 2:
        return vazio
    dias = (s.index[-1] - s.index[0]).days
    if dias < minimo_dias:
        return {**vazio, "nota": f"Só {dias} dias de histórico: o CAGR exige pelo menos {minimo_dias}."}
    anos = dias / 365.25
    v0, v1 = float(s.iloc[0]), float(s.iloc[-1])
    c = ((v1 / v0) ** (1 / anos) - 1) * 100
    nota = "Com cerca de 1 ano de dados, o CAGR equivale ao retorno do período." if anos < 1.5 else ""
    return {"cagr": float(c), "anos": float(anos), "inicio": s.index[0].date().isoformat(),
            "fim": s.index[-1].date().isoformat(), "nota": nota}


def _media_janela(s: pd.Series, ini_dias: int, fim_dias: int) -> float | None:
    if s.empty:
        return None
    ref = s.index[-1]
    j = s[(s.index > ref - pd.Timedelta(days=ini_dias)) & (s.index <= ref - pd.Timedelta(days=fim_dias))]
    return float(j.mean()) if len(j) else None


def soma_movel_30d(s) -> pd.Series:
    """Taxas/receita diárias → soma móvel de 30 dias (tira o ruído do dia a dia). Exige dias seguidos: com falhas na
    série, a janela que as contém é descartada (não preenchemos dias sem dado com zero)."""
    if s is not None and not isinstance(s, pd.Series):
        s = serie_de_pares(s, permitir_zero=True)
    s = pd.Series(s).astype(float).dropna() if s is not None else pd.Series(dtype=float)
    if len(s) < 30:
        return pd.Series(dtype=float)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    cheio = s.reindex(pd.date_range(s.index[0], s.index[-1], freq="D"))
    soma = cheio.rolling(30, min_periods=30).sum().dropna()
    return soma[soma > 0]


def historico(series: dict[str, pd.Series], longo_preco: pd.Series | None = None) -> dict:
    """Resumo histórico (Passo 7 aplicado a cripto). series: 'Preço (USD)', 'Valor de mercado (USD)',
    'Volume diário (USD)', 'Oferta circulante (calculada)', 'TVL (USD)', 'Taxas (USD)'… (as que existirem).
    longo_preco = histórico longo validado (Yahoo) — só usado se vier."""
    out: dict = {"linhas": [], "avisos": []}
    preco = _limpa((series or {}).get("Preço (USD)"))
    base_cagr = _limpa(longo_preco) if longo_preco is not None and len(_limpa(longo_preco)) > len(preco) else preco
    out["preco"] = {
        "ret": {d: variacao(preco, d) for d in (30, 90, 180, 365)},
        "vol": volatilidade(preco), "dd_max": drawdown_maximo(preco), "dd_atual": drawdown_atual(preco),
        "cagr": cagr(base_cagr), "inicio": preco.index[0].date().isoformat() if len(preco) else None,
        "fim": preco.index[-1].date().isoformat() if len(preco) else None,
        "usou_longo": base_cagr is not preco,
    }
    if len(preco) == 0:
        out["avisos"].append("Sem série de preços agora (CoinGecko não respondeu).")
    out["retorno_nota"] = ("Retorno de PREÇO. Recompensas de staking, airdrops e emissão não entram: não há metodologia "
                           "confiável integrada para o retorno total de criptomoedas.")
    mc, vol, oferta, tvl = (_limpa((series or {}).get(k)) for k in
                            ("Valor de mercado (USD)", "Volume diário (USD)", "Oferta circulante (calculada)", "TVL (USD)"))
    out["mcap"] = {"var_365": variacao(mc, 360), "var_30": variacao(mc, 30), "cagr": cagr(mc)} if len(mc) else None
    if len(vol) >= 60:
        atual, ant = _media_janela(vol, 30, 0), _media_janela(vol, 60, 30)
        out["volume"] = {"media30": atual, "media30_ant": ant, "var": (atual / ant - 1) * 100 if atual and ant else None}
    else:
        out["volume"] = None
    if len(oferta) >= 60:
        out["oferta"] = {"var_30": variacao(oferta, 30), "var_365": variacao(oferta, 360),
                         "nota": "Oferta calculada (valor de mercado ÷ preço); a CoinGecko não entrega o histórico da oferta."}
    else:
        out["oferta"] = None
    out["tvl"] = ({"var_30": variacao(tvl, 30), "var_90": variacao(tvl, 90), "var_365": variacao(tvl, 360),
                   "cagr": cagr(tvl), "atual": float(tvl.iloc[-1])} if len(tvl) >= 30 else None)
    for chave, nome in (("taxas", "Taxas (USD)"), ("receita", "Receita (USD)")):
        sr = _limpa((series or {}).get(nome))
        out[chave] = ({"atual": float(sr.iloc[-1]), "var_30": variacao(sr, 30), "var_90": variacao(sr, 90),
                       "var_365": variacao(sr, 360), "cagr": cagr(sr)} if len(sr) >= 30 else None)
    out["atividade"] = None if not (series or {}).get("Atividade (endereços ativos)") else {
        "var_30": variacao(_limpa(series["Atividade (endereços ativos)"]), 30)}
    return out


# --------------------------------------------------------------------------------------- tokenomics
def faixa_diluicao(pct_a_entrar: float | None) -> str:
    """% da oferta final que ainda não circula. Faixas educacionais, não previsão de preço."""
    if pct_a_entrar is None:
        return "indefinida"
    return "baixa" if pct_a_entrar < 10 else "moderada" if pct_a_entrar < 40 else "alta"


def faixa_inflacao(infl: float | None) -> str:
    if infl is None:
        return "indefinida"
    if infl < 0:
        return "deflacionária"
    return "baixa" if infl < 2 else "moderada" if infl < 8 else "alta"


LACUNAS_TOKENOMICS = [
    ("Distribuição inicial entre equipe, investidores, tesouraria e comunidade",
     "Nenhuma API gratuita integrada entrega a alocação. Consulte o whitepaper e a documentação oficial do projeto."),
    ("Concentração entre carteiras (maiores detentores)",
     "Precisa de explorador de blocos com API própria (Etherscan etc.); não há fonte gratuita integrada."),
    ("Calendário de desbloqueios e vesting",
     "O DefiLlama só entrega calendários na API paga. Você pode informar um evento com o link da fonte abaixo."),
    ("Queimas de tokens (separadas da emissão)",
     "A fonte entrega só a oferta circulante líquida; não separa emissão de queima."),
    ("Incentivos e recompensas distribuídos",
     "Sem fonte integrada (o DefiLlama detalha emissões apenas na API paga)."),
]


def tokenomics(calc: dict, inflacao_12m: float | None = None, receita_ao_detentor_30d: float | None = None) -> dict:
    """Tokenomics que dá para calcular com dados reais. `calc` é mercado()['calc']."""
    circ, total, maximo = calc.get("circ"), calc.get("total"), calc.get("maximo")
    teto = maximo or total
    a_entrar = (teto - circ) if teto and circ is not None and teto >= circ else None
    pct_entrar = (a_entrar / teto * 100) if a_entrar is not None and teto else None
    dil = faixa_diluicao(pct_entrar)
    fdv_mc = calc.get("fdv_mc")
    avisos = []
    if not maximo and not total:
        avisos.append("Sem oferta máxima nem total: não dá para saber quanto ainda pode entrar em circulação.")
    elif not maximo:
        avisos.append("Sem oferta máxima definida: a oferta total pode crescer (emissão contínua) e o FDV usa a oferta total atual.")
    if inflacao_12m is not None and inflacao_12m < 0:
        avisos.append("A oferta circulante encolheu em 12 meses; é compatível com queimas ou recompras, "
                      "mas a fonte não separa o motivo.")
    return {
        "circ": circ, "total": total, "maximo": maximo, "teto_definido": maximo is not None,
        "circ_max": calc.get("circ_max"), "circ_total": calc.get("circ_total"),
        "a_entrar": a_entrar, "pct_a_entrar": pct_entrar, "diluicao": dil, "fdv_mc": fdv_mc,
        "inflacao_12m": inflacao_12m, "faixa_inflacao": faixa_inflacao(inflacao_12m),
        "receita_ao_detentor_30d": receita_ao_detentor_30d,
        "avisos": avisos, "lacunas": LACUNAS_TOKENOMICS,
        "nota_inflacao": "Inflação = crescimento da oferta circulante em 12 meses (valor de mercado ÷ preço, mediana de 7 dias "
                         "nas pontas). É estimativa calculada, não emissão oficial do protocolo.",
    }


def desbloqueios(eventos: list[dict] | None, circ: float | None, preco: float | None, hoje: date | None = None,
                 horizonte_dias: int = 90) -> dict:
    """Eventos de desbloqueio INFORMADOS (data, quantidade, fonte). Sem fonte (link) o evento é recusado.
    Calcula % da oferta circulante e valor em US$. É pressão vendedora POSSÍVEL, nunca previsão de queda."""
    hoje = hoje or date.today()
    aceitos, recusados = [], []
    for e in (eventos or []):
        try:
            d = e["data"] if isinstance(e["data"], date) else date.fromisoformat(str(e["data"])[:10])
            q = float(e["quantidade"])
        except Exception:
            recusados.append({**e, "motivo": "data ou quantidade inválida"})
            continue
        fonte = str(e.get("fonte") or "").strip()
        if not re.match(r"^https?://", fonte):
            recusados.append({**e, "motivo": "sem link de fonte verificável"})
            continue
        if q <= 0:
            recusados.append({**e, "motivo": "quantidade deve ser positiva"})
            continue
        dias = (d - hoje).days
        pct = q / circ * 100 if circ else None
        val = q * preco if preco else None
        nivel = None if pct is None else "relevante" if pct >= 2 else "moderado" if pct >= 0.5 else "pequeno"
        aceitos.append({"data": d.isoformat(), "dias": dias, "quantidade": q, "pct_circulante": pct, "valor_usd": val,
                        "nivel": nivel, "fonte": fonte, "descricao": str(e.get("descricao") or ""),
                        "no_horizonte": 0 <= dias <= horizonte_dias, "passado": dias < 0})
    aceitos.sort(key=lambda x: x["data"])
    prox = [a for a in aceitos if a["no_horizonte"]]
    return {"eventos": aceitos, "recusados": recusados, "proximos": prox,
            "pct_proximos": sum(a["pct_circulante"] or 0 for a in prox) if prox else 0.0,
            "aviso": "Desbloqueio aumenta a oferta que pode ser vendida, mas não garante queda de preço: "
                     "depende de quem recebe os tokens, da demanda e do que já estava precificado."}


# --------------------------------------------------------------------------------------- on-chain
# quais fontes realmente leem a blockchain e quais são agregações/estimativas de provedores
# gecko_id → rede no Blockchair (API pública, sem chave). Só entram redes que o Blockchair indexa.
BLOCKCHAIR = {"bitcoin": "bitcoin", "ethereum": "ethereum", "litecoin": "litecoin", "dogecoin": "dogecoin",
              "bitcoin-cash": "bitcoin-cash", "dash": "dash", "zcash": "zcash", "ripple": "ripple", "stellar": "stellar",
              "cardano": "cardano", "monero": "monero"}


def ler_blockchair(resp, data: str | None = None) -> dict | None:
    """Resposta de /{rede}/stats do Blockchair → {'valor': transações em 24 h, 'data': ...} ou None (nunca zero inventado)."""
    dados = (resp or {}).get("data") if isinstance(resp, dict) else None
    if isinstance(dados, list):
        dados = dados[0] if dados else None
    v = _num((dados or {}).get("transactions_24h")) if isinstance(dados, dict) else None
    if v is None or v <= 0:
        return None
    return {"valor": v, "data": data}


ORIGEM_ONCHAIN = {
    "hash_rate": ("blockchain", "blockchain.com (dado da rede Bitcoin)"),
    "enderecos_ativos": ("blockchain", "blockchain.com (endereços únicos da rede Bitcoin)"),
    "tps": ("blockchain", "RPC público da própria rede (Solana)"),
    "transacoes_24h": ("blockchain", "Blockchair (explorador de blocos; contagem de transações registradas na rede)"),
    "tvl": ("estimativa", "DefiLlama (soma de contratos monitorados; metodologia do provedor)"),
    "taxas_30d": ("estimativa", "DefiLlama (taxas pagas pelos usuários, agregadas pelo provedor)"),
    "receita_30d": ("estimativa", "DefiLlama (parte das taxas que fica com o protocolo)"),
    "volume_dex_30d": ("estimativa", "DefiLlama (volume de DEXs monitoradas)"),
    "usuarios_ativos": ("estimativa", "Dune (consulta própria do usuário via chave configurada)"),
    "commits_4w": ("provedor", "CoinGecko/GitHub (atividade de desenvolvimento)"),
}

LACUNAS_ONCHAIN = [
    "Endereços ativos (exceto Bitcoin) e transações das redes fora do Blockchair: precisa de API de explorador de blocos ou Dune com chave.",
    "Participação de validadores / taxa de staking: sem fonte gratuita integrada.",
    "Distribuição de grandes carteiras (baleias): sem fonte gratuita integrada.",
    "Volume transferido na rede: sem fonte gratuita integrada.",
]


def onchain(dados: dict | None) -> dict:
    """dados: {chave: valor ou {valor, data, var_90d, ...}} com as chaves de ORIGEM_ONCHAIN que existirem.
    Cada item sai com a origem rotulada; o que faltou vai em 'ausentes' (nunca como zero)."""
    itens, ausentes = [], []
    rotulos = {
        "hash_rate": "Poder de mineração (hash rate)", "enderecos_ativos": "Endereços ativos",
        "tps": "Transações por segundo", "transacoes_24h": "Transações nas últimas 24 h", "tvl": "TVL (valor depositado)", "taxas_30d": "Taxas geradas (30 dias)",
        "receita_30d": "Receita do protocolo (30 dias)", "volume_dex_30d": "Volume em DEXs (30 dias)",
        "usuarios_ativos": "Usuários ativos diários", "commits_4w": "Commits de código (4 semanas)",
    }
    for ch, rot in rotulos.items():
        v = (dados or {}).get(ch)
        val = v.get("valor") if isinstance(v, dict) else v
        val = _num(val)
        tipo, fonte = ORIGEM_ONCHAIN[ch]
        if val is None:
            ausentes.append({"chave": ch, "rotulo": rot, "fonte_possivel": fonte})
            continue
        det = v if isinstance(v, dict) else {}
        itens.append({"chave": ch, "rotulo": rot, "valor": val, "tipo": tipo, "fonte": fonte,
                      "data": det.get("data"), "var_90d": _num(det.get("var_90d")), "var_30d": _num(det.get("var_30d")),
                      "fmt": "usd" if ch in ("tvl", "taxas_30d", "receita_30d", "volume_dex_30d") else "qtd"})
    reg = [i for i in itens if i["tipo"] == "blockchain"]
    est = [i for i in itens if i["tipo"] != "blockchain"]
    return {"itens": itens, "registrados": reg, "estimativas": est, "ausentes": ausentes, "lacunas": LACUNAS_ONCHAIN}


# --------------------------------------------------------------------------------------- governança (Snapshot)
# gecko_id → espaço no Snapshot (votações off-chain). Se um espaço mudar de nome, o app avisa "espaço não encontrado"
# em vez de mostrar dado errado. Fora desta lista, o usuário pode informar o espaço (ele vira "informado por você").
SNAPSHOT_ESPACOS = {
    "uniswap": "uniswapgovernance.eth", "aave": "aave.eth", "compound-governance-token": "comp-vote.eth",
    "curve-dao-token": "curve.eth", "maker": "makerdao.eth", "lido-dao": "lido-snap.eth",
    "ethereum-name-service": "ens.eth", "balancer": "balancer.eth", "1inch": "1inch.eth", "sushi": "sushigov.eth",
    "pancakeswap-token": "cakevote.eth", "gnosis": "gnosis.eth", "arbitrum": "arbitrumfoundation.eth",
    "dydx": "dydxgov.eth", "yearn-finance": "ybaby.eth",
}
GOV_RECENTE_DIAS = 30


def espaco_valido(txt) -> str | None:
    """Aceita só o formato de id do Snapshot (letras, números, ponto, hífen); devolve em minúsculas ou None."""
    t = str(txt or "").strip().lower()
    return t if re.fullmatch(r"[a-z0-9][a-z0-9.\-]{2,60}", t) else None


def governanca(resp, espaco: str, hoje: date | None = None) -> dict:
    """Resposta GraphQL do Snapshot ({'data': {'space': {...}, 'proposals': [...]}}) → resumo das votações.
    Sem resposta ou espaço inexistente: disponivel=False com o motivo (nada é inventado)."""
    hoje = hoje or date.today()
    base = {"disponivel": False, "espaco": espaco, "motivo": "", "ativas": [], "recentes": [], "n_90d": 0,
            "nome": None, "seguidores": None, "fonte": "Snapshot (hub.snapshot.org)"}
    dados = (resp or {}).get("data") if isinstance(resp, dict) else None
    if not isinstance(dados, dict):
        return {**base, "motivo": "O Snapshot não respondeu agora."}
    sp = dados.get("space")
    if not isinstance(sp, dict):
        return {**base, "motivo": f"Espaço '{espaco}' não encontrado no Snapshot."}
    propostas = []
    for p in dados.get("proposals") or []:
        if not isinstance(p, dict) or not p.get("id"):
            continue
        ini, fim = _num(p.get("start")), _num(p.get("end"))
        d_ini = datetime.fromtimestamp(ini, tz=timezone.utc).date() if ini else None
        d_fim = datetime.fromtimestamp(fim, tz=timezone.utc).date() if fim else None
        propostas.append({
            "titulo": _sem_html(p.get("title") or "(sem título)")[:140], "estado": str(p.get("state") or "").lower(),
            "inicio": d_ini.isoformat() if d_ini else None, "fim": d_fim.isoformat() if d_fim else None,
            "dias_ate_fim": (d_fim - hoje).days if d_fim else None,
            "dias_desde_inicio": (hoje - d_ini).days if d_ini else None,
            "votos_total": _num(p.get("scores_total")), "url": f"https://snapshot.org/#/{espaco}/proposal/{p['id']}"})
    ativas = [p for p in propostas if p["estado"] == "active"]
    recentes = [p for p in propostas if p["estado"] != "active"][:5]
    n90 = len([p for p in propostas if p["dias_desde_inicio"] is not None and 0 <= p["dias_desde_inicio"] <= 90])
    return {**base, "disponivel": True, "nome": sp.get("name"), "seguidores": _num(sp.get("followersCount")),
            "ativas": ativas, "recentes": recentes, "n_90d": n90}


# --------------------------------------------------------------------------------------- valuation
_COM_TVL = {"defi", "staking", "layer1", "layer2", "rwa"}
_COM_TAXAS = {"defi", "staking", "layer1", "layer2", "exchange", "oraculo", "infra", "governanca"}
FATOR_ANUAL = 365 / 30


def _mediana(vs):
    vs = sorted(v for v in (_num(x) for x in vs) if v is not None and v > 0)
    n = len(vs)
    if n < 3:
        return None
    return vs[n // 2] if n % 2 else (vs[n // 2 - 1] + vs[n // 2]) / 2


def _posicao(valor, mediana):
    if valor is None or mediana is None:
        return None
    r = valor / mediana
    return "abaixo da mediana dos pares" if r < 0.8 else "acima da mediana dos pares" if r > 1.2 else "em linha com a mediana dos pares"


def valuation(princ: str, mcap, fdv, tvl=None, taxas_30d=None, receita_30d=None, vol24=None,
              pares: list[dict] | None = None) -> dict:
    """Múltiplos só onde fazem sentido tecnicamente. pares = [{mc_tvl, p_taxas, p_receita}] da MESMA categoria."""
    mcap, fdv, tvl, t30, r30 = _num(mcap), _num(fdv), _num(tvl), _num(taxas_30d), _num(receita_30d)
    itens, nao = [], []
    pares = pares or []

    def add(ch, rot, val, fmt, nota, med=None):
        itens.append({"chave": ch, "rotulo": rot, "valor": val, "fmt": fmt, "nota": nota, "mediana_pares": med,
                      "posicao": _posicao(val, med), "n_pares": sum(1 for p in pares if _num(p.get(ch)))})

    fam = familia(princ)
    add("mcap", "Capitalização de mercado", mcap, "usd", "Preço × oferta circulante.")
    add("fdv", "FDV", fdv, "usd", "Preço × oferta máxima (ou total). Mostra o tamanho do projeto se toda a oferta circulasse.")
    if princ == "stablecoin":
        nao.append("Múltiplos de valuation não se aplicam a stablecoins: o preço é ancorado; avalie lastro, liquidez e desvio do preço-alvo.")
    elif princ in ("meme", "ia", "gaming", "metaverso") and not (t30 or tvl):
        nao.append("Sem atividade econômica mensurável (taxas ou TVL) nas fontes: Preço/Taxas e Valor/TVL não se aplicam. "
                   "O preço depende de narrativa e demanda especulativa.")
    else:
        if tvl and tvl > 0 and mcap and princ in _COM_TVL:
            add("mc_tvl", "Valor de mercado ÷ TVL", mcap / tvl, "ratio",
                "Quanto o mercado paga por cada dólar depositado. Compare só com a mesma categoria.",
                _mediana(p.get("mc_tvl") for p in pares))
        elif princ in _COM_TVL:
            nao.append("Valor de mercado ÷ TVL: sem TVL para este projeto nas fontes.")
        else:
            nao.append("Valor de mercado ÷ TVL não se aplica a esta categoria.")
        if t30 and t30 > 0 and mcap and princ in _COM_TAXAS:
            anual = t30 * FATOR_ANUAL
            add("p_taxas", "Preço ÷ Taxas (P/F)", mcap / anual, "ratio",
                "Valor de mercado ÷ taxas dos últimos 30 dias anualizadas. As taxas são pagas pelos usuários, não são lucro do token.",
                _mediana(p.get("p_taxas") for p in pares))
            add("taxas_anuais", "Taxas anualizadas", anual, "usd", "Taxas de 30 dias × 365/30.")
            add("rend_taxas", "Taxas anualizadas ÷ valor de mercado", anual / mcap * 100, "pct_f",
                "Não é dividend yield: o token pode não receber essas taxas.")
        else:
            nao.append("Preço ÷ Taxas: sem taxas medidas para este projeto (ou categoria sem taxas próprias).")
        if r30 and r30 > 0 and mcap and princ in _COM_TAXAS:
            anual_r = r30 * FATOR_ANUAL
            add("p_receita", "Preço ÷ Receita (P/S)", mcap / anual_r, "ratio",
                "Valor de mercado ÷ receita do protocolo anualizada (parte das taxas que fica com o protocolo).",
                _mediana(p.get("p_receita") for p in pares))
        else:
            nao.append("Preço ÷ Receita (P/S): sem receita comparável do protocolo nas fontes.")
    if vol24 and mcap:
        add("giro", "Valor de mercado vs. atividade de negociação", vol24 / mcap * 100, "pct_f",
            "Volume de 24 h ÷ valor de mercado; mede negociação, não atividade econômica do projeto.")
    return {"familia": fam, "itens": itens, "nao_aplicaveis": nao,
            "aviso": "Múltiplo baixo não significa barato: pode refletir risco, diluição ou receita que não chega ao token. "
                     "Os múltiplos tradicionais só são calculados quando há fluxo medido."}


# --------------------------------------------------------------------------------------- exploits e auditorias
def _norm(n) -> str:
    return re.sub(r"[^a-z0-9]", "", str(n or "").lower())


def exploits_do_projeto(hacks: list[dict] | None, nome: str, defillama_id=None, hoje: date | None = None) -> dict:
    """Filtra a lista do DefiLlama (/hacks) para o projeto. hacks=None → fonte indisponível (≠ 'nenhum')."""
    hoje = hoje or date.today()
    if hacks is None:
        return {"disponivel": False, "itens": [], "total_usd": 0.0, "recentes": []}
    alvo = _norm(nome)
    itens = []
    for h in hacks:
        if not isinstance(h, dict):
            continue
        casa = False
        if defillama_id is not None and str(h.get("defillamaId") or "") == str(defillama_id):
            casa = True
        elif alvo and _norm(h.get("name")) == alvo:
            casa = True
        if not casa:
            continue
        try:
            d = datetime.fromtimestamp(int(h.get("date")), tz=timezone.utc).date()
        except Exception:
            d = None
        itens.append({"data": d.isoformat() if d else None, "dias": (hoje - d).days if d else None,
                      "valor_usd": _num(h.get("amount")), "tecnica": h.get("technique") or h.get("classification"),
                      "ponte": bool(h.get("bridgeHack")), "devolvido_usd": _num(h.get("returnedFunds")),
                      "fonte": h.get("source")})
    itens.sort(key=lambda x: x["data"] or "", reverse=True)
    return {"disponivel": True, "itens": itens, "total_usd": sum(i["valor_usd"] or 0 for i in itens),
            "recentes": [i for i in itens if i["dias"] is not None and i["dias"] <= HACK_DIAS]}


_TVL_FORA = ("staking", "borrowed", "pool2", "vesting", "treasury")


def tvl_historico_do_protocolo(raws: list[dict] | None) -> pd.Series:
    """Série diária de TVL a partir da resposta /protocol/{slug} do DefiLlama: soma das redes (sem staking, empréstimos
    tomados, pool2, vesting e tesouraria — a mesma regra do TVL atual) ou, se não houver por rede, a série total.
    Vários protocolos na lista = soma deles (usado para as versões de um mesmo projeto)."""
    total: dict = {}

    def somar(lista):
        for x in lista or []:
            if not isinstance(x, dict):
                continue
            v, d = _num(x.get("totalLiquidityUSD")), _num(x.get("date"))
            if v is None or d is None or v < 0:
                continue
            dia = pd.to_datetime(d, unit="s").normalize()
            total[dia] = total.get(dia, 0.0) + v

    for raw in raws or []:
        if not isinstance(raw, dict):
            continue
        cadeias = raw.get("chainTvls") if isinstance(raw.get("chainTvls"), dict) else {}
        usou = False
        for nome, dados in cadeias.items():
            if any(t in str(nome).lower() for t in _TVL_FORA) or not isinstance(dados, dict):
                continue
            somar(dados.get("tvl"))
            usou = True
        if not usou:
            somar(raw.get("tvl"))
    if not total:
        return pd.Series(dtype=float)
    s = pd.Series(total).sort_index()
    return s[s > 0]


def mesclar_protocolo(base: dict | None, outros: list[dict] | None) -> dict | None:
    """O protocolo-pai do DefiLlama soma o TVL das versões, mas pode vir sem categoria, redes e auditorias. Completa só o
    que falta com os dados das versões (categoria: a primeira que existir; redes e auditorias: união). Não inventa nada."""
    if not isinstance(base, dict):
        return base
    out = dict(base)
    vers = [o for o in (outros or []) if isinstance(o, dict)]
    if not out.get("category"):
        cat = next((o["category"] for o in vers if o.get("category")), None)
        if cat:
            out["category"] = cat
    redes = list(out.get("chains") or [])
    links = list(out.get("audit_links") or [])
    n = out.get("audits") or 0
    for o in vers:
        redes += [c for c in (o.get("chains") or []) if c not in redes]
        links += [l for l in (o.get("audit_links") or []) if l not in links]
        try:
            n = max(int(n or 0), int(o.get("audits") or 0))
        except (TypeError, ValueError):
            pass
    if redes:
        out["chains"] = redes
    if links:
        out["audit_links"] = links
    if n:
        out["audits"] = n
    return out


def auditorias(proto: dict | None) -> dict:
    """Auditorias listadas no DefiLlama (/protocol/{slug}). Lista ≠ garantia de segurança."""
    if not proto:
        return {"disponivel": False, "n": None, "links": []}
    links = [l for l in (proto.get("audit_links") or []) if isinstance(l, str) and l.startswith("http")]
    try:
        n = int(proto.get("audits") or 0)
    except (TypeError, ValueError):
        n = 0
    n = max(n, len(links))
    return {"disponivel": True, "n": n, "links": links[:10],
            "aviso": "Auditoria reduz risco de falhas conhecidas, mas não o elimina: o código pode mudar depois, "
                     "a auditoria pode ter limites de escopo e existem exploits em projetos auditados."}


# --------------------------------------------------------------------------------------- riscos
def avaliar_riscos(ctx: dict) -> dict:
    """ctx: classes(list de chaves), princ, mcap, giro, fdv_mc, eh_stable, tipo_stable, peg_desvio (%), exploits
    (de exploits_do_projeto), auditorias (de auditorias), plataforma (rede do contrato), ponte (bool), gid, governanca.
    Cada risco: nível alto/médio/baixo/indeterminado + base. 'baixo' = sem evidência nas fontes, não 'seguro'."""
    cl = set(ctx.get("classes") or [])
    princ = ctx.get("princ") or "outros"
    mcap, giro = _num(ctx.get("mcap")), _num(ctx.get("giro"))
    R = []

    def add(ch, rot, nivel, texto, base):
        R.append({"chave": ch, "rotulo": rot, "nivel": nivel, "texto": texto, "base": base})

    # contratos inteligentes
    aud = ctx.get("auditorias") or {}
    nativa = princ in ("layer1",) and not ctx.get("plataforma")
    if nativa:
        add("contratos", "Contratos inteligentes", "indeterminado",
            "Moeda nativa de uma rede: o risco está no código do protocolo base e no consenso, que esta análise não audita.",
            "categoria")
    elif aud.get("disponivel"):
        if aud.get("n"):
            add("contratos", "Contratos inteligentes", "medio",
                f"{aud['n']} auditoria(s) listada(s). Isso reduz, mas não elimina, o risco de falhas no código.",
                "DefiLlama (audit_links)")
        else:
            add("contratos", "Contratos inteligentes", "medio",
                "Nenhuma auditoria listada no DefiLlama (a base pode estar incompleta): confira a documentação do projeto.",
                "DefiLlama")
    else:
        add("contratos", "Contratos inteligentes", "indeterminado",
            "Sem dados de auditoria para este projeto nas fontes.", "sem fonte")

    # exploits
    ex = ctx.get("exploits") or {}
    if not ex.get("disponivel"):
        add("exploits", "Histórico de exploits", "indeterminado", "A base de incidentes do DefiLlama não respondeu agora.", "sem fonte")
    elif ex.get("itens"):
        n, tot = len(ex["itens"]), ex.get("total_usd") or 0
        nivel = "alto" if (ex.get("recentes") or tot >= 50e6) else "medio"
        add("exploits", "Histórico de exploits", nivel,
            f"{n} incidente(s) registrado(s) no DefiLlama, somando US$ {tot:,.0f} em perdas." .replace(",", "."),
            "DefiLlama (/hacks)")
    else:
        add("exploits", "Histórico de exploits", "baixo",
            "Nenhum incidente encontrado na base do DefiLlama. Ausência na base não prova ausência de falhas.",
            "DefiLlama (/hacks)")

    # concentração de tokens
    fdv_mc = _num(ctx.get("fdv_mc"))
    extra = (f" Há indício indireto: o FDV é {fdv_mc:.1f}× o valor de mercado, ou seja, parte grande da oferta ainda não circula "
             "e pode estar concentrada em equipe/investidores.") if fdv_mc and fdv_mc >= 1.5 else ""
    add("concentracao", "Concentração de tokens", "indeterminado",
        "A distribuição entre carteiras não tem fonte gratuita integrada." + extra, "sem fonte")

    # administradores / centralização
    if ctx.get("gid") == "bitcoin":
        add("centralizacao", "Centralização e dependência de administradores", "baixo",
            "Rede sem emissor ou administrador. A concentração de mineração é um risco próprio, acompanhado em outras fontes.", "categoria")
    elif ctx.get("eh_stable") and ctx.get("tipo_stable") != "cripto":
        add("centralizacao", "Centralização e dependência de administradores", "alto",
            "Stablecoin com emissor central: pode congelar endereços e depende da reserva e da gestão da empresa.", "categoria")
    elif "exchange" in cl:
        add("centralizacao", "Centralização e dependência de administradores", "alto",
            "O token depende de uma empresa (a exchange): problemas de solvência, regulação ou de política afetam o token.", "categoria")
    else:
        add("centralizacao", "Centralização e dependência de administradores", "indeterminado",
            "Chaves de administrador, multisig e poder de atualização dos contratos não têm fonte integrada.", "sem fonte")

    # vulnerabilidades conhecidas
    add("vulnerabilidades", "Vulnerabilidades conhecidas", "indeterminado",
        "Não há feed de vulnerabilidades integrado; os incidentes acima são o indicador disponível.", "sem fonte")

    # liquidez
    if mcap is None and giro is None:
        add("liquidez", "Liquidez", "indeterminado", "Sem valor de mercado ou volume nas fontes.", "sem fonte")
    else:
        if (giro is not None and giro < 0.005) or (mcap is not None and mcap < 50e6):
            nv = "alto"
        elif (giro is not None and giro < 0.02) or (mcap is not None and mcap < 500e6):
            nv = "medio"
        else:
            nv = "baixo"
        g = f"giro diário {giro * 100:.1f}%" if giro is not None else "giro indisponível"
        add("liquidez", "Liquidez", nv,
            f"Valor de mercado e volume sugerem liquidez {'baixa' if nv == 'alto' else 'moderada' if nv == 'medio' else 'adequada'} ({g}). "
            "Profundidade do livro de ofertas e spread não têm fonte integrada.", "CoinGecko (volume ÷ mcap)")

    # regulatório
    if cl & {"stablecoin", "exchange", "staking", "rwa"}:
        add("regulatorio", "Regulatório", "medio",
            "Categoria sob escrutínio regulatório em várias jurisdições (contexto geral da categoria, não um evento verificado).",
            "categoria")
    else:
        add("regulatorio", "Regulatório", "indeterminado",
            "Sem evento regulatório verificável nas fontes integradas.", "sem fonte")

    # stablecoin
    if ctx.get("eh_stable"):
        d = _num(ctx.get("peg_desvio"))
        tipo = ctx.get("tipo_stable")
        if tipo == "algoritmica":
            add("stablecoin", "Risco de stablecoin", "alto",
                "Stablecoin algorítmica: sem lastro integral, o preço-alvo depende do mecanismo e da confiança.", "categoria")
        elif d is None:
            add("stablecoin", "Risco de stablecoin", "indeterminado", "Preço atual indisponível para medir o desvio.", "sem fonte")
        else:
            nv = "alto" if abs(d) >= 2 else "medio" if abs(d) >= 0.5 else "baixo"
            add("stablecoin", "Risco de stablecoin", nv,
                f"Desvio do preço-alvo (US$ 1): {d:+.2f}%. Composição e auditoria das reservas não têm fonte integrada.",
                "CoinGecko (preço)")

    # bridges
    if ctx.get("ponte"):
        add("bridges", "Dependência de bridges", "alto",
            "O ativo é um token representado/“encapsulado” ou ligado a uma ponte entre blockchains: se a ponte falhar, o token perde lastro.",
            "categoria/DefiLlama")
    elif ctx.get("plataforma"):
        add("bridges", "Dependência de bridges", "indeterminado",
            f"O token roda em outra rede ({ctx['plataforma']}); se circula em outras blockchains, depende de pontes que não foram avaliadas.",
            "CoinGecko (plataforma)")

    # governança
    if "governanca" in cl:
        add("governanca", "Governança", "medio",
            "Decisões são votadas por detentores do token: risco de concentração de votos e de propostas que favoreçam grandes detentores.",
            "categoria")
    else:
        add("governanca", "Governança", "indeterminado", "Modelo de governança não identificado nas fontes.", "sem fonte")

    # manipulação
    meme = "meme" in cl
    if mcap is not None and giro is not None:
        if mcap < 100e6 and giro > 1:
            nv = "alto"
        elif meme or mcap < 1e9 or giro > 0.5:
            nv = "medio"
        else:
            nv = "baixo"
        add("manipulacao", "Manipulação de mercado", nv,
            "Valor de mercado pequeno, giro muito alto e ativos de narrativa são mais fáceis de manipular."
            if nv != "baixo" else "Porte e liquidez altos dificultam a manipulação, mas não a eliminam.", "CoinGecko (mcap e volume)")
    else:
        add("manipulacao", "Manipulação de mercado", "indeterminado", "Sem dados de porte e volume.", "sem fonte")

    # diluição
    if fdv_mc is None:
        add("diluicao", "Diluição", "indeterminado", "FDV indisponível: não dá para medir a oferta ainda por entrar.", "sem fonte")
    else:
        nv = "alto" if fdv_mc > 2 else "medio" if fdv_mc > 1.3 else "baixo"
        add("diluicao", "Diluição", nv,
            f"O FDV equivale a {fdv_mc:.2f}× o valor de mercado. Tokens a liberar podem aumentar a pressão vendedora; não é previsão de queda.",
            "CoinGecko (FDV)")

    det = [r for r in R if r["nivel"] != "indeterminado"]
    geral = ("alto" if any(r["nivel"] == "alto" for r in det) else "medio" if any(r["nivel"] == "medio" for r in det)
             else "baixo" if det else "indeterminado")
    return {"riscos": R, "geral": geral, "cobertura": len(det) / len(R) if R else 0.0,
            "aviso": "“Baixo” significa que não há evidência de problema nas fontes integradas — não que o projeto seja seguro. "
                     "Itens “indeterminado” não foram medidos por falta de fonte."}


# --------------------------------------------------------------------------------------- fundamentos
def _sem_html(t) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", str(t or ""))).strip()


def fundamentos(raw: dict | None, dev: dict | None = None, github: dict | None = None, protocolo: dict | None = None,
                classes: list[str] | None = None) -> dict:
    """Fundamentos do projeto com o que as fontes entregam. O que não é verificável vai em 'lacunas'."""
    raw = raw or {}
    desc = _sem_html((raw.get("description") or {}).get("en") if isinstance(raw.get("description"), dict) else raw.get("description"))
    sent = re.split(r"(?<=[.!?])\s+", desc)
    objetivo = " ".join(sent[:2])[:500] if desc else None
    links = raw.get("links") or {}
    home = next((h for h in (links.get("homepage") or []) if h), None)
    repos = [r for r in ((links.get("repos_url") or {}).get("github") or []) if r]
    princ = principal(classes or ["outros"])
    itens = {
        "objetivo": objetivo,
        "tecnologia": ", ".join(x for x in [raw.get("hashing_algorithm"),
                                           f"contrato na rede {raw['asset_platform_id']}" if raw.get("asset_platform_id") else None,
                                           "rede própria" if not raw.get("asset_platform_id") else None] if x) or None,
        "inicio": _data_iso(raw.get("genesis_date")),
        "site": home, "repositorios": repos[:3],
        "utilidade_token": UTILIDADE.get(princ, UTILIDADE["outros"]),
        "ecossistema": ((protocolo or {}).get("chains") or [])[:12] or None,
        "categoria_defillama": (protocolo or {}).get("category"),
        "dev": dev or None, "github": github or None,
    }
    lacunas = [
        "Equipe e histórico verificável: não há fonte estruturada integrada. Verifique no site oficial e em fontes independentes.",
        "Parcerias verificáveis: não há fonte integrada; anúncios de parceria precisam ser confirmados com o outro lado.",
        "Roadmap: sem fonte integrada. Governança: só votações do Snapshot, quando o espaço do projeto é conhecido.",
    ]
    aviso = ("O texto do objetivo é a descrição que o projeto fornece à CoinGecko; não foi verificado. "
             "Popularidade (ranking, comunidade) não é qualidade fundamental.")
    return {"itens": itens, "lacunas": lacunas, "aviso": aviso,
            "utilidade_nota": "Descrição geral da categoria: confirme a utilidade real do token na documentação do projeto."}


# --------------------------------------------------------------------------------------- ranking e pares
CRITERIOS_RANKING = {
    "mcap": ("Capitalização de mercado", True), "giro": ("Liquidez (volume ÷ mcap)", True),
    "var30": ("Desempenho 30 dias", True), "var1a": ("Desempenho 1 ano", True),
    "vol_anual": ("Menor volatilidade", False), "dd_max": ("Menor drawdown máximo", True),
    "mc_fdv": ("Menor diluição (mcap ÷ FDV)", True), "mc_tvl": ("Menor Valor/TVL", False),
    "p_taxas": ("Menor Preço/Taxas", False), "tvl": ("Adoção: maior TVL", True),
    "nota": ("Nota fundamentalista", True),
}


def ranking(linhas: list[dict], chave: str) -> list[dict]:
    """linhas: [{nome, <chave>: valor}]. Ordena pelo critério; quem não tem o dado vai para o fim, sem posição."""
    if chave not in CRITERIOS_RANKING:
        raise KeyError(chave)
    _, maior = CRITERIOS_RANKING[chave]
    com = [(l, _num(l.get(chave))) for l in linhas]
    ok = sorted([(l, v) for l, v in com if v is not None], key=lambda x: x[1], reverse=maior)
    sem = [l for l, v in com if v is None]
    out = [{**l, "posicao": i + 1, "valor": v} for i, (l, v) in enumerate(ok)]
    out += [{**l, "posicao": None, "valor": None} for l in sem]
    return out


# --------------------------------------------------------------------------------------- monitoramento
HACK_DIAS = 180
LIM_OFERTA_30D = 5.0      # % de crescimento da oferta circulante calculada em 30 dias
LIM_TVL_30D = 25.0        # % de variação do TVL em 30 dias
LIM_PEG = 1.0             # % de desvio do preço-alvo de uma stablecoin
LIM_VOLUME_X = 3.0        # volume 24 h vs. média de 30 dias
LIM_VAR24 = 15.0          # % de variação do preço em 24 h
RELEASE_DIAS = 30
LIM_TAXAS_30D = 40.0      # % de variação das taxas (soma de 30 dias vs. 30 dias antes)


def _decimal_br(t) -> str:
    """'-50.0%' → '-50,0%'. Não mexe em versões como 'v32.1' nem em endereços (o ponto precisa vir depois de um número solto)."""
    return re.sub(r"(?<![\w.])(\d+)\.(\d+)", r"\1,\2", str(t))


def monitorar(ctx: dict) -> list[dict]:
    """Alertas SOMENTE a partir de dados verificáveis presentes em ctx (cada alerta traz fonte e data).
    ctx: var24, vol24, vol_media30, oferta_var30, tvl_var30, eh_stable, peg_desvio, exploits (exploits_do_projeto),
    desbloqueios (desbloqueios()), release ({tag,data,dias,url}), data, fonte."""
    A = []
    data = ctx.get("data")

    def add(nivel, tipo, titulo, texto, fonte, texto_externo=False):
        # texto_externo: título de proposta etc. vem de fora e fica exatamente como veio (ex.: "Version 2.0")
        A.append({"nivel": nivel, "tipo": tipo, "titulo": _decimal_br(titulo),
                  "texto": texto if texto_externo else _decimal_br(texto), "fonte": fonte, "data": data})

    v24 = _num(ctx.get("var24"))
    if v24 is not None and abs(v24) >= LIM_VAR24:
        add("atencao", "mercado", f"Variação de preço de {v24:+.1f}% em 24 h",
            "Movimento forte em um dia; verifique a causa antes de tirar conclusões.", "CoinGecko")
    vol, vm = _num(ctx.get("vol24")), _num(ctx.get("vol_media30"))
    if vol and vm and vm > 0 and vol / vm >= LIM_VOLUME_X:
        add("atencao", "liquidez", f"Volume {vol / vm:.1f}× a média de 30 dias",
            "Mudança relevante de liquidez/negociação (pode vir de notícia, listagem ou manipulação).", "CoinGecko")
    o30 = _num(ctx.get("oferta_var30"))
    if o30 is not None and o30 >= LIM_OFERTA_30D:
        add("atencao", "tokenomics", f"Oferta circulante calculada subiu {o30:.1f}% em 30 dias",
            "Compatível com desbloqueio ou emissão, mas a fonte não identifica o motivo.", "CoinGecko (valor de mercado ÷ preço)")
    t30 = _num(ctx.get("tvl_var30"))
    if t30 is not None and abs(t30) >= LIM_TVL_30D:
        add("atencao", "rede", f"TVL variou {t30:+.1f}% em 30 dias",
            "Mudança relevante na utilização do protocolo/rede (o TVL também oscila com o preço dos ativos depositados).", "DefiLlama")
    d = _num(ctx.get("peg_desvio"))
    if ctx.get("eh_stable") and d is not None and abs(d) >= LIM_PEG:
        add("alto" if abs(d) >= 2 else "atencao", "stablecoin", f"Stablecoin {d:+.2f}% fora de US$ 1",
            "Desvio do preço-alvo; verifique reservas e liquidez de resgate.", "CoinGecko")
    for e in (ctx.get("exploits") or {}).get("recentes", []):
        add("alto", "exploit", f"Exploit em {e['data']} (há {e['dias']} dias)",
            f"Perda registrada: US$ {e['valor_usd']:,.0f}.".replace(",", ".") if e.get("valor_usd") else "Valor não informado.",
            "DefiLlama (/hacks)")
    for ev in (ctx.get("desbloqueios") or {}).get("proximos", []):
        add("atencao", "desbloqueio", f"Desbloqueio em {ev['dias']} dias ({ev['data']})",
            (f"Equivale a {ev['pct_circulante']:.2f}% da oferta circulante. " if ev.get("pct_circulante") is not None else "")
            + "Possível pressão vendedora; não é previsão de queda. Fonte informada por você.", ev["fonte"])
    gov = ctx.get("governanca") or {}
    for p in gov.get("ativas", []):
        fim = f" (termina em {p['dias_ate_fim']} dias)" if p.get("dias_ate_fim") is not None and p["dias_ate_fim"] >= 0 else ""
        add("info", "governanca", f"Votação aberta na governança{fim}", p["titulo"], p.get("url") or "Snapshot", texto_externo=True)
    for p in gov.get("recentes", []):
        if p.get("dias_desde_inicio") is not None and p["dias_desde_inicio"] <= GOV_RECENTE_DIAS:
            add("info", "governanca", f"Proposta recente ({p['estado'] or 'encerrada'})", p["titulo"], p.get("url") or "Snapshot", texto_externo=True)
    tx30 = _num((ctx.get("taxas_var30")))
    if tx30 is not None and abs(tx30) >= LIM_TAXAS_30D:
        add("atencao", "rede", f"Taxas (30 dias) variaram {tx30:+.1f}% frente aos 30 dias anteriores",
            "Mudança relevante na atividade econômica medida pelo DefiLlama (também oscila com o preço do ativo).", "DefiLlama")
    rel = ctx.get("release") or {}
    if rel.get("dias") is not None and rel["dias"] <= RELEASE_DIAS:
        add("info", "atualizacao", f"Nova versão publicada: {rel.get('tag')}",
            f"Publicada há {rel['dias']} dias no GitHub oficial do projeto.", rel.get("url") or "GitHub")
    ordem = {"alto": 0, "atencao": 1, "info": 2}
    A.sort(key=lambda a: ordem.get(a["nivel"], 3))
    return A


SEM_FONTE_MONITOR = [
    "Mudanças de tokenomics: sem feed integrado (acompanhe o fórum e a documentação do projeto).",
    "Governança: só votações do Snapshot (espaços cadastrados ou informados por você); votações on-chain (Tally, Governor) não estão integradas.",
    "Desbloqueios: só aparecem os que você informar com link de fonte.",
]


# --------------------------------------------------------------------------------------- relatório
def _f_usd(v):
    v = _num(v)
    if v is None:
        return "n/d"
    for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return f"US$ {v / lim:.2f}{suf}".replace(".", ",")
    return f"US$ {v:.2f}".replace(".", ",")


def relatorio(ctx: dict) -> dict:
    """Relatório automático. ctx: nome, simbolo, classes (dicts), mercado (calc), tokenomics, onchain, valuation,
    riscos, historico, pares (lista de nomes), nota (fundamentalista, opcional), alertas, fundamentos."""
    nome = ctx.get("nome") or "o ativo"
    cl = [c["rotulo"] for c in ctx.get("classes") or []]
    mc = ctx.get("mercado") or {}
    tk = ctx.get("tokenomics") or {}
    rk = ctx.get("riscos") or {}
    hs = ctx.get("historico") or {}
    val = ctx.get("valuation") or {}
    oc = ctx.get("onchain") or {}
    pos, neg, atencao = [], [], []

    resumo = (f"{nome} ({ctx.get('simbolo') or '?'}) é classificado como {', '.join(cl) or 'sem categoria definida'}. "
              f"Valor de mercado {_f_usd(mc.get('mcap'))}"
              + (f", posição #{mc['rank']} no ranking" if mc.get("rank") else "") + ".")
    sec = [{"titulo": "Resumo do projeto", "itens": [resumo]}]
    fu = (ctx.get("fundamentos") or {}).get("itens") or {}
    fund_it = []
    if fu.get("objetivo"):
        fund_it.append("Objetivo (texto do projeto, não verificado): " + fu["objetivo"])
    if fu.get("dev") and fu["dev"].get("commits_4w") is not None:
        c4 = fu["dev"]["commits_4w"]
        fund_it.append(f"Desenvolvimento: {c4} commits nas últimas 4 semanas (repositórios públicos).")
        (pos if c4 >= 20 else atencao if c4 == 0 else []).append(
            "Desenvolvimento ativo (20+ commits em 4 semanas)." if c4 >= 20 else "Nenhum commit nas últimas 4 semanas.")
    gv = ctx.get("governanca") or {}
    if gv.get("disponivel"):
        fund_it.append(f"Governança (Snapshot, {gv.get('nome') or gv.get('espaco')}): {len(gv['ativas'])} votação(ões) aberta(s) e "
                       f"{gv['n_90d']} proposta(s) nos últimos 90 dias.")
    fund_it.append("Equipe, parcerias e roadmap: sem fonte verificável integrada.")
    sec.append({"titulo": "Qualidade dos fundamentos", "itens": fund_it})
    sec.append({"titulo": "Utilidade do token", "itens": [fu.get("utilidade_token") or UTILIDADE["outros"]]})

    t_it = []
    if tk.get("pct_a_entrar") is not None:
        t_it.append(f"Ainda não circula {tk['pct_a_entrar']:.1f}% da oferta final (diluição potencial {tk['diluicao']}).")
        if tk["diluicao"] == "alta":
            neg.append(f"Diluição potencial alta: {tk['pct_a_entrar']:.0f}% da oferta ainda por circular.")
        elif tk["diluicao"] == "baixa":
            pos.append("Quase toda a oferta final já circula (baixa diluição potencial).")
    else:
        t_it.append("Sem oferta máxima/total: o potencial de diluição não pode ser medido.")
        atencao.append("Oferta máxima indefinida.")
    if tk.get("inflacao_12m") is not None:
        t_it.append(f"Inflação da oferta em 12 meses: {tk['inflacao_12m']:+.1f}% ({tk['faixa_inflacao']}).")
        if tk["faixa_inflacao"] == "alta":
            neg.append(f"Oferta cresceu {tk['inflacao_12m']:.1f}% em 12 meses.")
        elif tk["faixa_inflacao"] in ("baixa", "deflacionária"):
            pos.append("Oferta circulante estável ou em queda em 12 meses.")
    t_it.append("Distribuição, vesting e concentração de carteiras: sem fonte integrada.")
    sec.append({"titulo": "Tokenomics", "itens": t_it})

    a_it = []
    for i in oc.get("itens", []):
        if i["chave"] == "tvl":
            a_it.append(f"TVL: {_f_usd(i['valor'])} ({i['fonte']}).")
        elif i["chave"] in ("taxas_30d", "receita_30d"):
            a_it.append(f"{i['rotulo']}: {_f_usd(i['valor'])}.")
    if not a_it:
        a_it.append("Sem métricas de adoção medidas nas fontes integradas para este ativo.")
    sec.append({"titulo": "Adoção", "itens": a_it})

    s_it = []
    for r in rk.get("riscos", []):
        if r["nivel"] in ("alto", "medio"):
            nv = "médio" if r["nivel"] == "medio" else r["nivel"]
            s_it.append(f"{r['rotulo']} — {nv}: {r['texto']}")
            (neg if r["nivel"] == "alto" else atencao).append(f"{r['rotulo']}: {nv}.")
    s_it.append(rk.get("aviso") or "")
    sec.append({"titulo": "Segurança", "itens": [x for x in s_it if x]})

    v_it = [f"{i['rotulo']}: {i['valor']:.2f}" + (f" ({i['posicao']})" if i.get("posicao") else "")
            for i in val.get("itens", []) if i["fmt"] == "ratio" and i.get("valor") is not None]
    v_it += val.get("nao_aplicaveis", [])[:2]
    sec.append({"titulo": "Valuation", "itens": v_it or ["Valuation por múltiplos não se aplica ou não há dados."]})

    p = hs.get("preco") or {}
    h_it = []
    ret = p.get("ret") or {}
    if ret.get(365) is not None:
        h_it.append(f"Retorno de preço em 1 ano: {ret[365]:+.1f}%.")
    if p.get("vol") is not None:
        h_it.append(f"Volatilidade anualizada: {p['vol']:.0f}%; drawdown máximo no período: {p['dd_max']:.0f}%."
                    if p.get("dd_max") is not None else f"Volatilidade anualizada: {p['vol']:.0f}%.")
        if p["vol"] > 100:
            atencao.append(f"Volatilidade muito alta ({p['vol']:.0f}% a.a.).")
    if mc.get("queda_ath") is not None and mc["queda_ath"] <= -50:
        neg.append(f"Preço {abs(mc['queda_ath']):.0f}% abaixo da máxima histórica.")
    tx = hs.get("taxas")
    if tx and tx.get("var_90") is not None:
        h_it.append(f"Taxas geradas (soma de 30 dias): {_f_usd(tx['atual'])}; {tx['var_90']:+.0f}% em 90 dias (DefiLlama).")
    h_it.append(hs.get("retorno_nota") or "")
    sec.append({"titulo": "Desempenho histórico", "itens": [x for x in h_it if x]})

    r_alto = [r for r in rk.get("riscos", []) if r["nivel"] == "alto"]
    sec.append({"titulo": "Principais riscos", "itens": [f"{r['rotulo']}: {r['texto']}" for r in r_alto]
                or ["Nenhum risco alto identificado nas fontes integradas (isso não significa ausência de risco)."]})
    if mc.get("giro") is not None and mc["giro"] >= 0.05:
        pos.append("Boa liquidez de negociação (volume diário ≥ 5% do valor de mercado).")
    if (mc.get("mcap") or 0) >= 10e9:
        pos.append("Porte grande (valor de mercado acima de US$ 10 bi).")
    if ctx.get("nota") is not None:
        sec.append({"titulo": "Nota da análise fundamentalista", "itens": [f"{ctx['nota']:.0f} de 100 (7 pilares do motor de cripto)"]})
    sec.append({"titulo": "Pontos positivos", "itens": pos or ["Nenhum ponto positivo objetivo identificado nos dados disponíveis."]})
    sec.append({"titulo": "Pontos negativos", "itens": neg or ["Nenhum ponto negativo objetivo identificado nos dados disponíveis."]})
    pares = ctx.get("pares") or []
    sec.append({"titulo": "Concorrentes", "itens": [("Maiores da mesma categoria: " + ", ".join(pares[:6]) + ". Use a aba Comparação.")
                                                    if pares else "Concorrentes não identificados agora (CoinGecko não respondeu)."]})
    for a in ctx.get("alertas") or []:
        atencao.append(a["titulo"])
    sec.append({"titulo": "Indicadores que merecem atenção", "itens": list(dict.fromkeys(atencao)) or ["Nenhum no momento."]})
    def _virgula(t):                      # números do relatório no padrão brasileiro (o texto do projeto fica como veio)
        return t if t.startswith("Objetivo") else re.sub(r"(?<![\w.])(\d+)\.(\d+)", r"\1,\2", t)
    for s_ in sec:
        s_["itens"] = [_virgula(i) for i in s_["itens"]]
    pos, neg = [_virgula(x) for x in pos], [_virgula(x) for x in neg]
    atencao = [_virgula(x) for x in atencao]
    return {"secoes": sec, "positivos": pos, "negativos": neg, "atencao": list(dict.fromkeys(atencao)),
            "aviso": "Relatório gerado por regras sobre dados públicos. É informação educacional, não recomendação de compra ou venda."}


# --------------------------------------------------------------------------------------- carteira
LIM_ATIVO = 40.0          # % da parte cripto num único ativo
LIM_CATEGORIA = 60.0      # % numa categoria principal
LIM_STABLE = 50.0         # % em stablecoins
LIM_REDE = 60.0           # % numa mesma rede


def analisar_carteira(posicoes: list[dict]) -> dict:
    """posicoes: [{gid, simbolo, qtd, preco (USD atual), classes (chaves), princ, rede, serie (Series de preço USD)}].
    Concentração por ativo/categoria/rede, exposição a stablecoins, volatilidade e drawdown da carteira cripto atual
    (quantidades de hoje aplicadas ao histórico comum). Não executa nada."""
    agg: dict[str, dict] = {}
    for p in posicoes or []:
        q, pr = _num(p.get("qtd")), _num(p.get("preco"))
        if not p.get("gid") or q is None or q <= 0:
            continue
        a = agg.setdefault(p["gid"], {**p, "qtd": 0.0})
        a["qtd"] += q
        if pr is not None:
            a["preco"] = pr
    linhas, sem_preco = [], []
    for g, a in agg.items():
        pr = _num(a.get("preco"))
        if pr is None:
            sem_preco.append(a.get("simbolo") or g)
            continue
        linhas.append({"gid": g, "simbolo": a.get("simbolo") or g, "valor": a["qtd"] * pr, "qtd": a["qtd"],
                       "classes": a.get("classes") or ["outros"], "princ": a.get("princ") or "outros",
                       "rede": a.get("rede") or g, "serie": a.get("serie")})
    total = sum(l["valor"] for l in linhas)
    out = {"total_usd": total, "linhas": [], "por_categoria": {}, "exposicao_rotulos": {}, "redes": {}, "stable_pct": 0.0,
           "alertas": [], "vol_anual": None, "dd_max": None, "dd_atual": None, "dias_hist": 0, "sem_preco": sem_preco,
           "avisos": []}
    if total <= 0:
        out["avisos"].append("Nenhuma criptomoeda com preço atual na carteira.")
        return out
    for l in sorted(linhas, key=lambda x: -x["valor"]):
        l["peso"] = l["valor"] / total * 100
        out["linhas"].append({k: l[k] for k in ("gid", "simbolo", "valor", "qtd", "peso", "princ", "rede")} |
                             {"classes": l["classes"]})
        out["por_categoria"][l["princ"]] = out["por_categoria"].get(l["princ"], 0.0) + l["peso"]
        for c in l["classes"]:
            out["exposicao_rotulos"][c] = out["exposicao_rotulos"].get(c, 0.0) + l["peso"]
        out["redes"][l["rede"]] = out["redes"].get(l["rede"], 0.0) + l["peso"]
    out["stable_pct"] = out["exposicao_rotulos"].get("stablecoin", 0.0)
    out["hhi"] = sum((l["peso"] / 100) ** 2 for l in out["linhas"])

    top = out["linhas"][0]
    if len(out["linhas"]) > 1 and top["peso"] >= LIM_ATIVO:
        out["alertas"].append(f"Concentração: {top['simbolo']} é {top['peso']:.0f}% da parte cripto da carteira.")
    if len(out["linhas"]) == 1:
        out["alertas"].append(f"Só há um ativo cripto ({top['simbolo']}): sem diversificação dentro da classe.")
    for c, w in out["por_categoria"].items():
        if w >= LIM_CATEGORIA and len(out["linhas"]) > 1 and c != "stablecoin":
            out["alertas"].append(f"Concentração por categoria: {w:.0f}% em {CATEGORIAS.get(c, c)}.")
    if out["stable_pct"] >= LIM_STABLE:
        out["alertas"].append(f"{out['stable_pct']:.0f}% em stablecoins: baixa volatilidade, mas com risco de emissor e de "
                              "desvio do preço-alvo (não é caixa livre de risco).")
    for r, w in out["redes"].items():
        if w >= LIM_REDE and len(out["redes"]) > 1:
            out["alertas"].append(f"Exposição a uma rede: {w:.0f}% dependem da rede {r} (moeda nativa e tokens que rodam nela).")

    # volatilidade e drawdown: quantidades atuais aplicadas ao histórico comum (não é a carteira real no passado)
    series = {l["gid"]: _limpa(l["serie"]) for l in linhas if l.get("serie") is not None and len(_limpa(l["serie"])) > 1}
    cobertos = [l for l in linhas if l["gid"] in series]
    if cobertos:
        cobertura_valor = sum(l["valor"] for l in cobertos) / total
        df = pd.concat({l["gid"]: series[l["gid"]] * l["qtd"] for l in cobertos}, axis=1).dropna()
        out["dias_hist"] = len(df)
        if len(df) >= 60 and cobertura_valor >= 0.8:
            v = df.sum(axis=1)
            out["vol_anual"], out["dd_max"], out["dd_atual"] = volatilidade(v), drawdown_maximo(v), drawdown_atual(v)
            out["avisos"].append("Volatilidade e drawdown usam as quantidades de hoje sobre o histórico de preços: "
                                 "mostram o risco da composição atual, não o que a carteira rendeu no passado.")
            if cobertura_valor < 1:
                out["avisos"].append(f"Histórico cobre {cobertura_valor * 100:.0f}% do valor; o restante ficou fora do cálculo.")
        else:
            out["avisos"].append("Histórico comum insuficiente (menos de 60 dias ou cobertura < 80% do valor): "
                                 "volatilidade e drawdown da carteira não foram calculados.")
    else:
        out["avisos"].append("Sem histórico de preços das moedas da carteira agora: volatilidade e drawdown não calculados.")
    return out
