"""Mercado no app novo: Mercado hoje, busca de empresas do catálogo e a leitura de uma ação (preço justo, indicadores e
um resumo em palavras simples). As contas são as mesmas do app antigo (app.py: graham_calc, bazin_calc, multiplos,
resumo_simples), aqui sem Streamlit para a API poder usar. Tudo educativo: nada aqui é recomendação de compra ou venda.

As funções de cálculo (`indicadores`, `preco_justo`, `resumo`, `montar_acao`) são puras e testadas sem rede; `dados_acao`
e `historico` falam com as fontes (Yahoo e Fundamentus, pelo dados.py, que já tem cache e pausa depois de falha).
"""
from __future__ import annotations

import re
from datetime import datetime
from math import sqrt

# mesmo perfil padrão do app antigo (recursos.PERFIS["Moderado"])
YIELD_ALVO = 6.0
MARGEM_ALVO = 20

FINANCEIRAS = ("ITSA", "ITUB", "BBDC", "BBAS", "BPAC", "SANB", "BBSE", "CXSE", "SULA",
               "INBR", "BRSR", "BPAN", "XPBR", "PSSA", "ROXO", "ABCB")

AVISO = "Leitura educativa com dados públicos. Não é recomendação de compra ou venda."

# Cartões da tela Mercado: (id, título, descrição, pronto no app novo?)
TIPOS = (
    ("acoes", "Ações", "Preço justo, valor e saúde da empresa", True),
    ("cripto", "Criptomoedas", "Tendência, risco e diluição do token", True),
)

# Criptomoedas da tela Mercado: (id na CoinGecko, nome, símbolo). Logos em app/assets/logos/cripto/.
CRIPTOS = (
    ("bitcoin", "Bitcoin", "BTC"), ("ethereum", "Ethereum", "ETH"), ("solana", "Solana", "SOL"), ("ripple", "XRP", "XRP"),
    ("binancecoin", "BNB", "BNB"), ("cardano", "Cardano", "ADA"), ("dogecoin", "Dogecoin", "DOGE"), ("chainlink", "Chainlink", "LINK"),
    ("avalanche-2", "Avalanche", "AVAX"), ("polkadot", "Polkadot", "DOT"), ("litecoin", "Litecoin", "LTC"), ("uniswap", "Uniswap", "UNI"),
)
_LOGOS_CRIPTO = {"btc", "eth", "xrp", "bnb", "sol", "ada", "avax", "doge", "usdt", "usdc", "trx", "dot", "shib", "link", "matic", "ltc",
                 "bch", "dai", "uni", "cro"}
ID_CRIPTO = re.compile(r"^[a-z0-9][a-z0-9-]{1,60}$")


def logo_cripto(simbolo: str | None):
    s = str(simbolo or "").lower()
    return f"cripto/{s}.webp" if s in _LOGOS_CRIPTO else None


def cripto_item(gid: str, nome: str, simbolo: str) -> dict:
    return {"tipo": "cripto", "id": gid, "ticker": simbolo, "nome": nome, "setor": "Criptomoeda", "logo": logo_cripto(simbolo)}


def criptos_populares() -> list[dict]:
    return [cripto_item(*c) for c in CRIPTOS]


def buscar_criptos(texto: str) -> list[dict]:
    """Criptos da lista pelo nome ou símbolo (sem rede)."""
    t = (texto or "").strip().lower()
    return [cripto_item(*c) for c in CRIPTOS if t and (t in c[1].lower() or t in c[2].lower() or t == c[0])]


_STATUS_CRIPTO = {"good": "bom", "fair": "medio", "bad": "ruim", "na": "na"}


def montar_cripto(m: dict) -> dict:
    """Resposta de GET /mercado/cripto/{id} a partir de cripto.analisar_moeda (puro, sem rede). Os seis quadros são os do
    app antigo (cripto.indicadores_moeda): tendência, desempenho, volatilidade, queda desde a máxima, diluição e porte."""
    import cripto as CR
    cards = []
    for c in CR.indicadores_moeda(m):
        cards.append({"titulo": c["titulo"], "icone": c["icone"], "status": _STATUS_CRIPTO.get(c["cls"], "na"), "selo": c["status"],
                      "texto": c["texto"], "linhas": [[str(a), str(b)] for a, b in c["linhas"]], "nota": c.get("nota", "")})
    hist = m.get("hist") or []
    passo = max(1, len(hist) // 260)
    hist = hist[::-1][::passo][::-1]
    serie = [{"t": t.strftime("%Y-%m-%d"), "c": round(float(v), 8)} for t, v in hist]
    return {"tipo": "cripto", "id": m.get("id"), "nome": m.get("nome"), "simbolo": m.get("simbolo"), "rank": m.get("rank"),
            "logo": logo_cripto(m.get("simbolo")), "preco": _f(m.get("preco")), "var7": _f(m.get("var7")), "var30": _f(m.get("var30")),
            "var1a": _f(m.get("var1a")), "mcap": _f(m.get("mcap")), "categorias": list(m.get("categorias") or [])[:3],
            "indicadores": cards, "serie": serie, "alertas": [a for a in (m.get("avisos") or []) if isinstance(a, str)][:3],
            "aviso": "Leitura educativa com dados públicos (CoinGecko). Cripto oscila muito. Não é recomendação de compra ou venda."}

PERIODOS = {"6m": ("6mo", "1d"), "1a": ("1y", "1d"), "5a": ("5y", "1wk")}


def eh_financeiro(tk: str) -> bool:
    return str(tk).upper().startswith(FINANCEIRAS)


def _f(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x and abs(x) != float("inf") else None


def _margem(justo, preco):
    """Margem de segurança = (justo − preço) ÷ justo, em %."""
    return (justo - preco) / justo * 100 if justo and justo > 0 and preco else None


def _status(margem, alvo=MARGEM_ALVO) -> str:
    if margem is None:
        return "na"
    if margem >= alvo:
        return "bom"
    return "medio" if margem >= 0 else "ruim"


def base_bazin(div_ano: dict | None, div_medio=None, ano: int | None = None):
    """Dividendo anual médio dos últimos 5 anos completos (o ano em curso fica de fora; anos sem pagamento contam zero).
    Devolve (média, nº de anos, ano atípico?). Sem série por ano, usa o dividendo médio da fonte."""
    ano = ano or datetime.now().year
    try:
        serie = {int(a): float(v) for a, v in (div_ano or {}).items() if v is not None}
        serie = {a: v for a, v in serie.items() if a < ano}
        if serie:
            ini = max(min(serie), ano - 5)
            vals = [serie.get(a, 0.0) for a in range(ini, ano)]
            if len(vals) >= 2:
                s = sorted(vals)
                med = (s[len(s) // 2] + s[(len(s) - 1) // 2]) / 2
                return sum(vals) / len(vals), len(vals), med > 0 and max(vals) > 2 * med
    except (TypeError, ValueError):
        pass
    dm = _f(div_medio)
    return dm, None, False


def indicadores(d: dict) -> dict:
    """P/L, P/VP, dividend yield (12 meses), ROE, margem líquida (em %) e dívida/patrimônio, como no app antigo."""
    p, lpa, vpa = _f(d.get("preco")), _f(d.get("lpa")), _f(d.get("vpa"))
    d12, roe, ml = _f(d.get("div_12m")), _f(d.get("roe")), _f(d.get("margem_liq"))
    return {
        "pl": p / lpa if p and lpa and lpa > 0 else None,
        "pvp": p / vpa if p and vpa and vpa > 0 else None,
        "dy": d12 / p * 100 if p and p > 0 and d12 is not None else None,
        "roe": roe * 100 if roe is not None else None,
        "margem": ml * 100 if ml is not None else None,
        "div_pl": _f(d.get("div_pl")),
    }


def preco_justo(d: dict, ano: int | None = None) -> dict:
    """Graham (√(22,5 × LPA × VPA), só com LPA e VPA positivos) e Bazin (dividendo médio ÷ yield desejado), cada um por si."""
    preco, lpa, vpa = _f(d.get("preco")), _f(d.get("lpa")), _f(d.get("vpa"))
    if lpa is None or vpa is None:
        g = {"justo": None, "aviso": "Faltam lucro por ação ou patrimônio por ação na fonte."}
    elif lpa <= 0 or vpa <= 0:
        g = {"justo": None, "aviso": "A empresa teve prejuízo ou patrimônio negativo: Graham não se aplica."}
    else:
        g = {"justo": sqrt(22.5 * lpa * vpa), "aviso": None}
    base, anos, atipico = base_bazin(d.get("div_ano"), d.get("div_medio"), ano)
    if base is None or base <= 0:
        b = {"justo": None, "aviso": "Sem dividendos nos últimos anos: Bazin não se aplica."}
    else:
        b = {"justo": base / (YIELD_ALVO / 100),
             "aviso": "Um dos anos pagou bem mais que os outros: a média pode estar inflada." if atipico else None}
    for m in (g, b):
        m["margem"] = _margem(m["justo"], preco)
        m["status"] = _status(m["margem"])
    g["como"] = "Usa o lucro e o patrimônio da empresa por ação."
    b["como"] = f"Quanto pagar para receber {YIELD_ALVO:.0f}% ao ano em dividendos (média dos últimos anos)."
    return {"graham": g, "bazin": b, "margem_alvo": MARGEM_ALVO, "yield_alvo": YIELD_ALVO}


def _faixa(chave: str, v, fin: bool) -> str:
    """Faixa de referência geral (bom, medio, ruim ou na). Cada setor tem seus patamares; é só um norte para iniciante."""
    if v is None:
        return "na"
    if chave == "pl":
        return "bom" if 0 < v <= 10 else "medio" if v <= 20 else "ruim"
    if chave == "pvp":
        return "bom" if v <= 1.5 else "medio" if v <= 3 else "ruim"
    if chave == "dy":
        return "bom" if v >= 6 else "medio" if v >= 3 else "ruim"
    if chave == "roe":
        return "bom" if v >= 15 else "medio" if v >= 8 else "ruim"
    if chave == "margem":
        return "bom" if v >= 15 else "medio" if v >= 5 else "ruim"
    if chave == "div_pl":
        return "na" if fin else ("bom" if v <= 50 else "medio" if v <= 100 else "ruim")
    return "na"


EXPLICA = {
    "pl": ("P/L", "Em quantos anos o lucro de hoje paga o preço da ação."),
    "pvp": ("P/VP", "Quanto o mercado paga por cada R$ 1 de patrimônio da empresa."),
    "dy": ("Dividendos (12m)", "Quanto a empresa pagou em dividendos no último ano, para cada R$ 100 na ação."),
    "roe": ("ROE", "Lucro a cada R$ 100 que os donos colocaram na empresa."),
    "margem": ("Margem líquida", "Lucro a cada R$ 100 vendidos."),
    "div_pl": ("Dívida/Patrimônio", "Quanto a empresa deve em relação ao que ela tem. Em bancos, dívida faz parte do negócio."),
}


def lista_indicadores(d: dict) -> list[dict]:
    fin = eh_financeiro(d.get("ticker", ""))
    ind = indicadores(d)
    out = []
    for k, (nome, explica) in EXPLICA.items():
        v = ind.get(k)
        if k == "div_pl" and fin:
            continue
        pct = k in ("dy", "roe", "margem", "div_pl")
        out.append({"id": k, "nome": nome, "valor": v, "pct": pct, "faixa": _faixa(k, v, fin), "explica": explica})
    return out


def resumo(d: dict, pj: dict) -> list[dict]:
    """Os três cartões em palavras simples do app antigo: o preço está bom, a empresa é saudável, ela paga dividendos."""
    preco = _f(d.get("preco"))
    ind = indicadores(d)
    fin = eh_financeiro(d.get("ticker", ""))
    justos = [m["justo"] for m in (pj["graham"], pj["bazin"]) if m["justo"]]
    if justos and preco:
        v = sum(justos) / len(justos)
        dif = (v - preco) / v * 100
        st = "bom" if dif >= MARGEM_ALVO else "medio" if dif >= 0 else "ruim"
        txt = {"bom": "Mais barata que o valor estimado", "medio": "Perto do valor estimado", "ruim": "Mais cara que o valor estimado"}[st]
        c1 = {"id": "preco", "titulo": "O preço está bom?", "status": st, "texto": txt, "linhas": [["Preço hoje", preco], ["Quanto parece valer", v]],
              "nota": "Comparamos o preço de hoje com uma estimativa do valor, feita com o lucro e os dividendos da empresa."}
    else:
        c1 = {"id": "preco", "titulo": "O preço está bom?", "status": "na", "texto": "Sem dados", "linhas": [["Preço hoje", preco]],
              "nota": "Não deu para estimar quanto a empresa vale: faltam dados de lucro ou de dividendos."}
    roe, ml, dpl = ind["roe"], ind["margem"], ind["div_pl"]
    if roe is None and ml is None:
        c2 = {"id": "saude", "titulo": "A empresa é saudável?", "status": "na", "texto": "Sem dados suficientes", "linhas": [], "nota": ""}
    else:
        ok = int(roe is not None and roe >= 10) + int(ml is not None and ml >= 8) + int(fin or dpl is None or dpl <= 100)
        st = {3: "bom", 2: "medio"}.get(ok, "ruim")
        linhas = [["Lucro a cada R$ 100 dos donos", roe], ["Lucro a cada R$ 100 vendidos", ml]]
        c2 = {"id": "saude", "titulo": "A empresa é saudável?", "status": st, "texto": {"bom": "Saudável", "medio": "Meio a meio", "ruim": "Atenção"}[st],
              "linhas": linhas, "nota": "Quanto a empresa lucra e quanto ela deve. Lucrar bem e dever pouco é bom sinal."}
        if not fin and dpl is not None:
            c2["nivel_divida"] = "Baixo" if dpl <= 50 else "Médio" if dpl <= 100 else "Alto"
    dy = ind["dy"]
    if dy is None:
        c3 = {"id": "dividendos", "titulo": "Ela paga dividendos?", "status": "na", "texto": "Sem dados", "linhas": [], "nota": ""}
    else:
        st = "bom" if dy >= 6 else "medio" if dy >= 3 else "na"
        c3 = {"id": "dividendos", "titulo": "Ela paga dividendos?", "status": st,
              "texto": {"bom": "Paga bem", "medio": "Paga um pouco", "na": "Paga pouco"}[st],
              "linhas": [["A cada R$ 100 investidos, pagou", dy]],
              "nota": "Dividendo é a parte do lucro que a empresa divide com quem tem ações dela."}
    return [c1, c2, c3]


def montar_acao(tk: str, d: dict, info: dict | None = None, ano: int | None = None) -> dict:
    """Resposta de GET /mercado/acao/{tk} a partir dos dados da fonte (puro, sem rede)."""
    info = info or {}
    pj = preco_justo(d, ano)
    return {
        "ticker": tk, "nome": info.get("nome") or d.get("nome") or tk, "setor": info.get("setor") or d.get("setor"),
        "preco": _f(d.get("preco")), "var_dia": _f(d.get("var_dia")),
        "indicadores": lista_indicadores(d), "preco_justo": pj, "resumo": resumo(d, pj),
        "alertas": [a for a in (d.get("alertas") or []) if isinstance(a, str)][:4], "fonte": d.get("fonte"), "aviso": AVISO,
    }


# ------------------------------------------------------------------ fontes (rede)
def dados_acao(tk: str) -> dict:
    """Yahoo primeiro; sem preço ou sem lucro e patrimônio por ação, completa com o Fundamentus (como o app antigo)."""
    import dados as DA
    d = dict(DA.buscar_yahoo(tk))
    d["alertas"] = [a for a in d.get("alertas", []) if not str(a).startswith("Yahoo parcial")]
    if not d.get("preco") or (d.get("lpa") is None and d.get("vpa") is None):
        try:
            f = DA.buscar_fundamentus(tk)
            if f.get("preco"):
                if not d.get("preco"):
                    d = {**f, "alertas": list(f.get("alertas", []))}
                else:
                    for k in ("lpa", "vpa", "roe", "margem_liq", "div_pl", "div_12m", "div_ano", "div_medio"):
                        if d.get(k) is None and f.get(k) is not None:
                            d[k] = f[k]
        except Exception:
            pass
    if (d.get("moeda_balanco") or "BRL") == "USD" and (d.get("moeda") or "BRL") == "BRL":
        d["lpa"] = d["vpa"] = None             # balanço em dólar: sem câmbio confiável aqui, não arrisca preço justo errado
        d.setdefault("alertas", []).append("Balanço em dólar: preço justo por Graham fica de fora.")
    d["div_ano"] = _serie_dict(d.get("div_ano"))
    d["ticker"] = tk
    return d


def _serie_dict(s) -> dict:
    try:
        return {int(k): float(v) for k, v in dict(s).items()} if s is not None else {}
    except Exception:
        return {}


def historico(tk: str, periodo: str = "1a") -> list[dict]:
    """Fechamentos para o gráfico: [{t: 'AAAA-MM-DD', c: preço}], no máximo ~260 pontos."""
    import dados as DA
    per, intv = PERIODOS.get(periodo, PERIODOS["1a"])
    df, _err = DA.historico_yahoo(tk, per, intv)
    if df is None or df.empty or "Close" not in df:
        return []
    s = df["Close"].dropna()
    passo = max(1, len(s) // 260)
    s = s.iloc[::-1].iloc[::passo].iloc[::-1]      # mantém sempre o último fechamento
    return [{"t": i.strftime("%Y-%m-%d"), "c": round(float(v), 4)} for i, v in s.items()]


def var_dia(serie: list[dict]):
    if len(serie) >= 2 and serie[-2]["c"]:
        return (serie[-1]["c"] / serie[-2]["c"] - 1) * 100
    return None
