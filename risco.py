"""
Passo 16 — Gestão de risco avançada (motor de cálculo, SEM Streamlit e SEM rede).

Recebe dados já coletados (posições, séries de preço, OHLCV, referências) e devolve números e classificações explicáveis. Quem coleta é risco_app.py.
Reaproveita o motor do Passo 12 (gestao.py: volatilidade anual, drawdown, Sharpe, Sortino, beta, VaR/CVaR, covariância, contribuição ao risco,
distribuições) e as premissas de cenário (gestao_otimiza.py). Nada aqui compra, vende ou altera posição.

Princípios
- Cada classe tem METODOLOGIA PRÓPRIA (METODOLOGIA): componentes medidos, âncoras (valor que vale nota 0 e valor que vale nota 100) e pesos documentados.
- Nota 0–100 (maior = mais risco) → nível: Muito baixo (<20), Baixo (<40), Moderado (<60), Alto (<80), Muito alto (≥80).
- RISCO ≠ INCERTEZA: o que falta de dado não vira nota; reduz a CONFIANÇA. Com menos de 40% do peso medido a classificação é "provisória" e com menos
  de 25% fica "indeterminada" (sem nota).
- Estimativas históricas (volatilidade, VaR, correlação, drawdown) descrevem o passado e não são limite de perda futura. Cenários são hipóteses, não previsões.
- Volatilidades usam fechamentos de DIAS ÚTEIS e √252 para todas as classes, para serem comparáveis (cripto negocia 24/7: ver nota na metodologia).
"""
from __future__ import annotations

import hashlib
import math
import re
from datetime import date, datetime, timedelta
from statistics import NormalDist

import numpy as np
import pandas as pd

import gestao as g
import gestao_otimiza as O
import intel as I

DIAS_ANO = g.DIAS_ANO
VERSAO_METODOLOGIA = "1.0"
AVISO_LEGAL = ("Ferramenta educacional. Notas e indicadores de risco descrevem o passado e usam premissas explícitas: não preveem perdas, não as limitam e não "
               "são recomendação. Nada é comprado, vendido ou alterado automaticamente.")
NIVEIS = ["Muito baixo", "Baixo", "Moderado", "Alto", "Muito alto"]
CORTES_NIVEL = (20, 40, 60, 80)
_ok = g._ok


def _r(x) -> str:
    """Reais inteiros com ponto de milhar (1.234.567)."""
    return f"{x:,.0f}".replace(",", ".")


def nivel_de_nota(nota: float | None) -> str:
    if nota is None or not _ok(nota):
        return "Indeterminado"
    return NIVEIS[sum(1 for c in CORTES_NIVEL if nota >= c)]


def interpolar(valor, ancora_baixa, ancora_alta) -> float | None:
    """Nota 0–100 por interpolação linear: `ancora_baixa` vale 0 e `ancora_alta` vale 100 (vale também para âncoras decrescentes). Fora do intervalo,
    trava em 0 ou 100. Sem valor → None (falta de dado não vira risco nem segurança)."""
    if valor is None or not _ok(valor) or ancora_baixa == ancora_alta:
        return None
    t = (float(valor) - ancora_baixa) / (ancora_alta - ancora_baixa)
    return float(min(100.0, max(0.0, t * 100.0)))


# =============================================================================== séries e volatilidade
def padronizar_dias_uteis(s: pd.Series | None) -> pd.Series:
    """Série diária limpa (índice sem fuso, sem duplicatas, só dias úteis). Cripto (7 dias) perde sábados e domingos: o retorno de segunda inclui o fim de
    semana. Assim todas as classes usam a mesma base (√252) e a volatilidade fica comparável."""
    if s is None or len(s) == 0:
        return pd.Series(dtype=float)
    x = pd.Series(pd.to_numeric(s.values, errors="coerce"), index=pd.DatetimeIndex(s.index))
    if x.index.tz is not None:
        x.index = x.index.tz_localize(None)
    x.index = x.index.normalize()
    x = x[~x.index.duplicated(keep="last")].sort_index().dropna()
    x = x[x > 0]
    return x[x.index.dayofweek < 5]


def frequencia_dias(s: pd.Series | None) -> float | None:
    """Mediana de dias entre observações (1 = diária; ~7 = semanal; ~30 = mensal). Serve para recusar comparação entre frequências diferentes."""
    if s is None or len(s) < 5:
        return None
    d = np.diff(pd.DatetimeIndex(s.index).values).astype("timedelta64[D]").astype(float)
    return float(np.median(d)) if len(d) else None


def retornos(s: pd.Series | None) -> pd.Series:
    x = padronizar_dias_uteis(s)
    return x.pct_change().dropna() if len(x) > 1 else pd.Series(dtype=float)


def retornos_comparaveis(a: pd.Series, b: pd.Series, tolerancia_dias: float = 3.0) -> tuple[bool, str]:
    """True se as duas séries têm frequência compatível (ambas diárias). Série mensal contra diária dá volatilidade incomparável e é recusada."""
    fa, fb = frequencia_dias(a), frequencia_dias(b)
    if fa is None or fb is None:
        return False, "histórico curto demais para saber a frequência"
    if abs(fa - fb) > 0.5 and max(fa, fb) > tolerancia_dias:
        return False, f"frequências diferentes (a cada {fa:g} e {fb:g} dias): volatilidades não são comparáveis diretamente"
    return True, ""


JANELAS_VOL = {"1 mês": 21, "3 meses": 63, "6 meses": 126, "12 meses": 252, "2 anos": 504}


def vol_janelas(r: pd.Series, janelas: dict | None = None, minimo_frac: float = 0.8) -> dict:
    """Volatilidade anualizada (desvio-padrão diário × √252) em várias janelas. Janela só vale se houver ≥ 80% das observações previstas."""
    out = {}
    for nome, n in (janelas or JANELAS_VOL).items():
        x = r.dropna().iloc[-n:] if r is not None else pd.Series(dtype=float)
        ok = len(x) >= max(10, int(n * minimo_frac))
        out[nome] = {"dias": n, "n": int(len(x)), "desvio_diario": float(x.std(ddof=1)) if ok else None,
                     "vol_anual": float(x.std(ddof=1) * math.sqrt(DIAS_ANO)) if ok else None}
    return out


def vol_realizada(r: pd.Series, janela: int = 21) -> float | None:
    """Volatilidade realizada anualizada: √(Σ r² × 252 / n) nos últimos `janela` dias (não subtrai a média; é a medida usada em derivativos)."""
    x = r.dropna().iloc[-janela:] if r is not None else pd.Series(dtype=float)
    if len(x) < max(10, int(janela * 0.8)):
        return None
    return float(math.sqrt(float((x ** 2).sum()) * DIAS_ANO / len(x)))


def vol_rolante(r: pd.Series, janela: int = 63) -> pd.Series:
    return (r.rolling(janela).std(ddof=1) * math.sqrt(DIAS_ANO)).dropna() if r is not None and len(r) > janela else pd.Series(dtype=float)


def atr(df: pd.DataFrame | None, n: int = 14) -> dict:
    """ATR de Wilder: média móvel exponencial (α = 1/n) do verdadeiro intervalo = máx(H−L, |H−C₋₁|, |L−C₋₁|). Precisa de High, Low e Close.
    Só se aplica a ativos com preços de máxima e mínima (ações, FIIs, ETFs, cripto); renda fixa e fundos não têm."""
    if df is None or not {"High", "Low", "Close"} <= set(df.columns) or len(df) < n + 2:
        return {"ok": False, "motivo": "sem preços de máxima e mínima (ATR não se aplica)"}
    h, l_, c = df["High"].astype(float), df["Low"].astype(float), df["Close"].astype(float)
    tr = pd.concat([h - l_, (h - c.shift()).abs(), (l_ - c.shift()).abs()], axis=1).max(axis=1).dropna()
    a = tr.ewm(alpha=1.0 / n, adjust=False).mean()
    v = float(a.iloc[-1])
    return {"ok": True, "atr": v, "pct_preco": v / float(c.iloc[-1]) if float(c.iloc[-1]) > 0 else None, "n": n, "serie": a}


def vol_relativa(r: pd.Series, rb: pd.Series, janela: int = 252, minimo: int = 60) -> dict:
    """Volatilidade do ativo ÷ volatilidade do benchmark no MESMO período (datas em comum). >1 = oscila mais que a referência."""
    j = pd.concat([r, rb], axis=1, join="inner").dropna().iloc[-janela:]
    if len(j) < minimo:
        return {"ok": False, "motivo": f"só {len(j)} dias em comum com a referência (mínimo {minimo})"}
    va, vb = float(j.iloc[:, 0].std(ddof=1)), float(j.iloc[:, 1].std(ddof=1))
    return {"ok": vb > 0, "razao": va / vb if vb > 0 else None, "vol_ativo": va * math.sqrt(DIAS_ANO), "vol_ref": vb * math.sqrt(DIAS_ANO), "dias": int(len(j))}


def mudanca_volatilidade(r: pd.Series, curta: int = 21, longa: int = 252, razao_alerta: float = 1.5) -> dict:
    """Compara a volatilidade recente com a de longo prazo (mesma metodologia nas duas). Razão ≥ 1,5 = risco subindo; ≤ 1/1,5 = acalmando."""
    x = r.dropna() if r is not None else pd.Series(dtype=float)
    if len(x) < longa * 0.8:
        return {"ok": False, "motivo": "histórico curto para comparar com a volatilidade de 12 meses"}
    vc, vl = float(x.iloc[-curta:].std(ddof=1)), float(x.iloc[-longa:].std(ddof=1))
    if vl <= 0:
        return {"ok": False, "motivo": "volatilidade de longo prazo nula"}
    k = vc / vl
    return {"ok": True, "razao": k, "vol_curta": vc * math.sqrt(DIAS_ANO), "vol_longa": vl * math.sqrt(DIAS_ANO),
            "sinal": "subindo" if k >= razao_alerta else "caindo" if k <= 1 / razao_alerta else "estável",
            "texto": f"Volatilidade dos últimos {curta} dias ({vc * math.sqrt(DIAS_ANO) * 100:.0f}% a.a.) é {k:.1f}× a de {longa} dias ({vl * math.sqrt(DIAS_ANO) * 100:.0f}% a.a.)."}


# =============================================================================== indicadores avançados
def covariancia_anual(rets: pd.DataFrame) -> pd.DataFrame:
    return rets.cov() * DIAS_ANO if rets is not None and rets.shape[1] >= 1 and len(rets) > 1 else pd.DataFrame()


def cagr_da_serie(r: pd.Series) -> float | None:
    x = r.dropna() if r is not None else pd.Series(dtype=float)
    if len(x) < 60:
        return None
    total = float((1 + x).prod())
    return float(total ** (DIAS_ANO / len(x)) - 1) if total > 0 else None


def calmar(r: pd.Series, minimo: int = 250) -> float | None:
    """Calmar = retorno anualizado (geométrico) ÷ |queda máxima| no mesmo período. Sensível ao período: um único vale domina o denominador."""
    x = r.dropna() if r is not None else pd.Series(dtype=float)
    if len(x) < minimo:
        return None
    dd = g.drawdown((1 + x).cumprod())
    c = cagr_da_serie(x)
    return float(c / abs(dd["maximo"])) if dd.get("ok") and c is not None and dd["maximo"] < -1e-9 else None


def tracking_error(r: pd.Series, rb: pd.Series, minimo: int = 60) -> float | None:
    """Tracking error anualizado = desvio-padrão da diferença diária de retorno (ativo − referência) × √252."""
    j = pd.concat([r, rb], axis=1, join="inner").dropna()
    if len(j) < minimo:
        return None
    return float((j.iloc[:, 0] - j.iloc[:, 1]).std(ddof=1) * math.sqrt(DIAS_ANO))


def information_ratio(r: pd.Series, rb: pd.Series, minimo: int = 60) -> float | None:
    """Information ratio = (retorno ativo médio − referência) anualizado ÷ tracking error. Referência inadequada produz número sem sentido."""
    j = pd.concat([r, rb], axis=1, join="inner").dropna()
    if len(j) < minimo:
        return None
    d = j.iloc[:, 0] - j.iloc[:, 1]
    sd = d.std(ddof=1)
    return float(d.mean() * DIAS_ANO / (sd * math.sqrt(DIAS_ANO))) if sd > 1e-12 else None


def var_ewma(r: pd.Series, nivel: float = 0.95, dias: int = 1, lam: float = 0.94, minimo: int = 250) -> float | None:
    """VaR paramétrico com volatilidade EWMA (RiskMetrics, λ=0,94): dá mais peso aos dias recentes, reage mais rápido que o histórico."""
    x = r.dropna() if r is not None else pd.Series(dtype=float)
    if len(x) < minimo:
        return None
    var = float(x.iloc[:30].var(ddof=1))
    for v in x.iloc[30:].values:
        var = lam * var + (1 - lam) * float(v) ** 2
    return float(NormalDist().inv_cdf(nivel) * math.sqrt(var) * math.sqrt(dias))


LIMITES_INDICADORES = {
    "vol": "Desvio-padrão dos retornos: trata subidas e quedas como risco e supõe que a dispersão passada vale para o futuro.",
    "var": "Perda que não foi excedida em N% dos dias do histórico. Em (100−N)% dos dias a perda foi MAIOR; não é a perda máxima.",
    "cvar": "Média das perdas dos dias piores que o VaR. Precisa de cauda com ≥ 10 observações e só conhece o que aconteceu na amostra.",
    "drawdown": "Queda do pico ao vale no período analisado. Depende da janela: períodos sem crise subestimam.",
    "beta": "Sensibilidade ao benchmark escolhido; muda com a referência, a janela e a frequência. Não mede risco próprio da empresa.",
    "correlacao": "Mede o movimento conjunto no passado. Em crises costuma subir; não é constante.",
    "sharpe": "Retorno excedente ÷ volatilidade. Penaliza igualmente altas e quedas e assume retornos em forma de sino.",
    "sortino": "Como o Sharpe, mas só a volatilidade negativa conta. Poucos dias negativos deixam o número instável.",
    "calmar": "Retorno anualizado ÷ queda máxima. Um único vale domina o resultado.",
    "tracking_error": "Dispersão da diferença para a referência: só faz sentido com referência adequada ao ativo.",
    "information_ratio": "Retorno ativo ÷ tracking error: instável com amostras curtas.",
}


def indicadores(r: pd.Series, rb: pd.Series | None = None, rf: pd.Series | float | None = None, horizontes: tuple = (1, 10)) -> dict:
    """Painel de indicadores de UM ativo ou carteira. Cada indicador sem dado suficiente fica None (nunca zero) e traz seu limite em LIMITES_INDICADORES."""
    x = r.dropna() if r is not None else pd.Series(dtype=float)
    out: dict = {"n_dias": int(len(x)), "limites": LIMITES_INDICADORES}
    if len(x) < 30:
        return {**out, "ok": False, "motivo": f"só {len(x)} dias de histórico (mínimo 30)"}
    dd = g.drawdown((1 + x).cumprod())
    out.update({"ok": True, "vol_anual": g.vol_anual(x), "mdd": dd.get("maximo"), "dd_atual": dd.get("atual"), "dd": dd, "calmar": calmar(x),
                "sharpe": g.sharpe(x, rf), "sortino": g.sortino(x, rf), "cagr": cagr_da_serie(x)})
    for h in horizontes:
        for nv in (0.95, 0.99):
            k = f"{int(nv * 100)}_{h}d"
            out["var_hist_" + k], out["var_param_" + k], out["cvar_" + k], out["var_ewma_" + k] = (
                g.var_historico(x, nv, h), g.var_parametrico(x, nv, h), g.cvar_historico(x, nv, h), var_ewma(x, nv, h))
    if rb is not None and len(rb):
        out.update({"beta": g.beta(x, rb), "correlacao_ref": float(pd.concat([x, rb], axis=1, join="inner").dropna().corr().iloc[0, 1])
                    if len(pd.concat([x, rb], axis=1, join="inner").dropna()) >= 60 else None,
                    "tracking_error": tracking_error(x, rb), "information_ratio": information_ratio(x, rb), "vol_relativa": vol_relativa(x, rb)})
    return out


# =============================================================================== concentração (11 eixos)
REDES = {"BTC": "Bitcoin", "ETH": "Ethereum", "SOL": "Solana", "ADA": "Cardano", "XRP": "XRP Ledger", "DOGE": "Dogecoin", "LTC": "Litecoin", "BNB": "BNB Chain",
         "AVAX": "Avalanche", "DOT": "Polkadot", "TRX": "Tron", "MATIC": "Polygon", "POL": "Polygon", "LINK": "Ethereum (token ERC-20)", "UNI": "Ethereum (token ERC-20)",
         "AAVE": "Ethereum (token ERC-20)", "USDT": "Tokens estáveis (emissor centralizado)", "USDC": "Tokens estáveis (emissor centralizado)"}
EIXOS = {"ativo": "Ativo", "classe": "Classe", "setor": "Setor", "empresa": "Empresa", "emissor": "Emissor", "pais": "País", "moeda": "Moeda", "custodiante": "Corretora ou custodiante",
         "protocolo": "Protocolo ou rede", "indexador": "Indexador", "vencimento": "Vencimento"}
NI = "Não informado"
LIMITES_PADRAO_RISCO = {"ativo": 20.0, "classe": 80.0, "setor": 40.0, "empresa": 25.0, "emissor": 25.0, "pais": 70.0, "moeda": 60.0, "custodiante": 70.0, "protocolo": 50.0,
                        "indexador": 70.0, "vencimento": 50.0, "perda_drawdown_pct": -20.0, "perda_sobre_custo_pct": -25.0, "por_ativo": {}, "por_classe": {}, "por_setor": {}}
SEM_LIMITE = {"Caixa", "Tesouro Nacional"}
INDEXADORES = {"pre": "Prefixado", "ipca": "IPCA+", "cdi_pct": "% do CDI", "cdi_mais": "CDI+", "selic": "Selic", "selic_mais": "Selic+"}


def faixa_vencimento(venc, hoje: date | None = None) -> str:
    if venc is None:
        return "Sem vencimento"
    hoje = hoje or date.today()
    try:
        d = pd.Timestamp(venc).date()
    except Exception:
        return NI
    anos = (d - hoje).days / 365.25
    return "Vencido" if anos < 0 else "até 1 ano" if anos <= 1 else "1 a 3 anos" if anos <= 3 else "3 a 5 anos" if anos <= 5 else "5 a 10 anos" if anos <= 10 else "mais de 10 anos"


def rede_do_ativo(ticker: str) -> str:
    base = re.split(r"[-/]", str(ticker).upper())[0]
    return REDES.get(base, NI)


def eixos_da_posicao(p: dict, hoje: date | None = None) -> dict:
    """Valor de cada eixo de concentração para UMA posição. O que o app não sabe vira 'Não informado' (e a tela diz que o eixo não é avaliável)."""
    c = p.get("classe")
    empresa = p.get("nome") if c in ("acao", "bdr") else (p.get("gestor") if c in ("fii", "etf", "fundo") and p.get("gestor") not in (None, NI) else None)
    return {"ativo": p["id"], "classe": g.CLASSES.get(c, c), "setor": p.get("setor") or NI, "empresa": empresa or NI,
            "emissor": p.get("emissor") or (p.get("nome") if c in ("acao", "bdr") else NI), "pais": p.get("pais") or NI, "moeda": p.get("moeda") or NI,
            "custodiante": p.get("custodiante") or p.get("corretora") or NI, "protocolo": rede_do_ativo(p["id"]) if c == "cripto" else "Não se aplica",
            "indexador": INDEXADORES.get(p.get("indexador"), NI) if c == "renda_fixa" else "Não se aplica",
            "vencimento": faixa_vencimento(p.get("vencimento"), hoje) if c == "renda_fixa" else "Sem vencimento"}


def _validos(posicoes: list[dict]) -> list[dict]:
    return [p for p in posicoes if _ok(p.get("valor")) and p["valor"] > 0]


def distribuicao_eixo(posicoes: list[dict], eixo: str, hoje: date | None = None) -> list[dict]:
    pos = _validos(posicoes)
    tot = sum(p["valor"] for p in pos)
    acc: dict[str, dict] = {}
    for p in pos:
        k = eixos_da_posicao(p, hoje)[eixo]
        d = acc.setdefault(k, {"nome": k, "valor": 0.0, "ativos": []})
        d["valor"] += p["valor"]
        d["ativos"].append(p["id"])
    return sorted([{**d, "pct": d["valor"] / tot * 100 if tot else 0.0} for d in acc.values()], key=lambda x: -x["pct"])


def concentracao_completa(posicoes: list[dict], hoje: date | None = None) -> dict:
    """Distribuição nos 11 eixos + HHI do eixo 'ativo'. Eixo com mais de 50% 'Não informado' é marcado como não avaliável (dado ausente ≠ concentração)."""
    out = {"eixos": {}, "hhi": g.concentracao([p["valor"] for p in _validos(posicoes)])}
    for e in EIXOS:
        d = distribuicao_eixo(posicoes, e, hoje)
        ni = sum(x["pct"] for x in d if x["nome"] == NI)
        out["eixos"][e] = {"rotulo": EIXOS[e], "dist": d, "pct_nao_informado": ni, "avaliavel": ni <= 50.0}
    return out


def avaliar_limites(posicoes: list[dict], limites: dict | None = None, hoje: date | None = None) -> list[dict]:
    """Excessos em relação aos limites (em % do patrimônio) escolhidos pela pessoa. Cada item traz o dado, o limite, o excesso em R$ e a gravidade.
    Limites são referências pessoais, não regras do mercado. Eixo sem dado ('Não informado' > 50%) não gera alerta; aparece em dados ausentes."""
    lim = {**LIMITES_PADRAO_RISCO, **{k: v for k, v in (limites or {}).items() if v is not None}}
    pos = _validos(posicoes)
    tot = sum(p["valor"] for p in pos)
    out = []
    if tot <= 0:
        return out

    def add(eixo, nome, pct, ref, valor):
        exc = pct - ref
        out.append({"eixo": eixo, "rotulo": EIXOS.get(eixo, eixo), "nome": nome, "pct": pct, "limite": ref, "excesso_pct": exc, "excesso_brl": exc / 100 * tot,
                    "gravidade": "alta" if exc >= ref * 0.5 else "media" if exc >= ref * 0.2 else "baixa",
                    "texto": f"{nome} = {pct:.1f}% do patrimônio; seu limite para {EIXOS.get(eixo, eixo).lower()} é {ref:g}% (excesso ≈ R$ {_r(exc / 100 * tot)})."})
    for e in EIXOS:
        if e == "ativo":
            continue
        dist = distribuicao_eixo(posicoes, e, hoje)
        if sum(x["pct"] for x in dist if x["nome"] == NI) > 50:
            continue
        espec = {"classe": lim["por_classe"], "setor": lim["por_setor"]}.get(e, {})
        for d in dist:
            if d["nome"] in SEM_LIMITE or d["nome"] in (NI, "Não se aplica", "Sem vencimento"):
                continue
            if e == "moeda" and d["nome"] == "BRL":
                continue   # a moeda de casa não é risco de concentração cambial
            if e == "classe" and len(dist) == 1:
                continue
            ref = espec.get(d["nome"], lim.get(e))
            if ref is not None and d["pct"] > ref + 1e-9:
                add(e, d["nome"], d["pct"], float(ref), d["valor"])
    for p in pos:
        if p.get("classe") == "caixa":
            continue
        ref = lim["por_ativo"].get(p["id"], lim["ativo"])
        if p["valor"] / tot * 100 > ref + 1e-9:
            add("ativo", p["id"], p["valor"] / tot * 100, float(ref), p["valor"])
    return sorted(out, key=lambda x: -x["excesso_pct"])


def exposicoes_indiretas(posicoes: list[dict], minimo_ativos: int = 2) -> list[dict]:
    """Ativos DIFERENTES que dependem do mesmo fator econômico (juros, commodities e dólar, bolsa do exterior, cripto...). Mostra o risco que a lista de tickers esconde."""
    pos = _validos(posicoes)
    tot = sum(p["valor"] for p in pos)
    grupos: dict[str, list[dict]] = {}
    for p in pos:
        if p.get("classe") == "caixa":
            continue
        fs = {g.fator_de_risco(p)}
        if p.get("classe") in ("acao", "bdr") and g.FATOR_DO_SETOR.get(p.get("setor")):
            fs.add(g.FATOR_DO_SETOR[p["setor"]])
        for f in fs:
            grupos.setdefault(f, []).append(p)
    out = []
    for f, lst in grupos.items():
        if len(lst) >= minimo_ativos:
            v = sum(x["valor"] for x in lst)
            out.append({"fator": f, "n": len(lst), "pct": v / tot * 100 if tot else 0.0, "ativos": [x["id"] for x in lst],
                        "classes": sorted({g.CLASSES.get(x.get("classe"), x.get("classe")) for x in lst}),
                        "texto": f"{len(lst)} ativos ({', '.join(x['id'] for x in lst[:6])}) dependem de “{f}”: {v / tot * 100:.0f}% do patrimônio pode reagir junto."})
    return sorted(out, key=lambda x: -x["pct"])


# =============================================================================== correlação
def matriz_corr(series: dict[str, pd.Series], janela: int | None = None, minimo: int = 60) -> pd.DataFrame:
    """Correlação de retornos diários (dias úteis, datas em comum). `janela` = últimos N dias úteis; None = todo o histórico comum. Ativos com poucos dados ficam fora."""
    pad = {k: padronizar_dias_uteis(s) for k, s in series.items()}
    rets = g.matriz_retornos(pad, minimo)
    if rets.empty:
        return pd.DataFrame()
    if janela:
        rets = rets.iloc[-janela:]
        if len(rets) < min(minimo, janela):
            return pd.DataFrame()
    return rets.corr() if rets.shape[1] >= 2 else pd.DataFrame()


def correlacoes_em_janelas(series: dict[str, pd.Series], janelas: dict | None = None) -> dict:
    return {nome: matriz_corr(series, n) for nome, n in (janelas or {"3 meses": 63, "6 meses": 126, "12 meses": 252, "Todo o histórico": None}).items()}


def mudancas_de_correlacao(series: dict[str, pd.Series], curta: int = 63, longa: int = 252, limite: float = 0.30) -> list[dict]:
    """Pares cuja correlação recente (curta) difere da de longo prazo em ≥ `limite`. Subida de correlação = menos diversificação do que o histórico longo sugere."""
    c, l_ = matriz_corr(series, curta), matriz_corr(series, longa)
    if c.empty or l_.empty:
        return []
    cols = [x for x in c.columns if x in l_.columns]
    out = []
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            d = float(c.loc[a, b] - l_.loc[a, b])
            if abs(d) >= limite:
                out.append({"a": a, "b": b, "recente": float(c.loc[a, b]), "longa": float(l_.loc[a, b]), "mudanca": d,
                            "texto": f"{a} × {b}: correlação {l_.loc[a, b]:+.2f} (12 meses) → {c.loc[a, b]:+.2f} (3 meses)."})
    return sorted(out, key=lambda x: -abs(x["mudanca"]))


def grupos_semelhantes(corr: pd.DataFrame, limite: float = 0.70) -> list[list[str]]:
    """Grupos de ativos ligados por correlação ≥ limite (componentes conectados). Só grupos com 2 ou mais ativos."""
    if corr is None or corr.empty:
        return []
    cols, pai = list(corr.columns), {}

    def raiz(x):
        while pai.setdefault(x, x) != x:
            pai[x] = pai[pai[x]]
            x = pai[x]
        return x
    for i, a in enumerate(cols):
        for b in cols[i + 1:]:
            if _ok(corr.loc[a, b]) and corr.loc[a, b] >= limite:
                pai[raiz(a)] = raiz(b)
    g_: dict[str, list[str]] = {}
    for c in cols:
        g_.setdefault(raiz(c), []).append(c)
    return sorted([sorted(v) for v in g_.values() if len(v) >= 2], key=lambda x: -len(x))


def correlacao_nos_piores_dias(series: dict[str, pd.Series], pesos: dict[str, float], quantil: float = 0.10, minimo: int = 120) -> dict:
    """Correlação média entre pares apenas nos 10% piores dias da carteira, comparada com a de todos os dias. Mostra o quanto a diversificação encolhe
    quando mais importa. Poucos dias na cauda (< 12) tornam o número instável."""
    pad = {k: padronizar_dias_uteis(s) for k, s in series.items() if k in pesos}
    rets = g.matriz_retornos(pad, 60)
    if rets.shape[1] < 2 or len(rets) < minimo:
        return {"ok": False, "motivo": "histórico comum curto demais (≥ 120 dias e 2 ativos)"}
    w = pd.Series({k: pesos[k] for k in rets.columns})
    w = w / w.sum()
    cart = (rets * w).sum(axis=1)
    cauda = rets[cart <= cart.quantile(quantil)]
    if len(cauda) < 12:
        return {"ok": False, "motivo": f"só {len(cauda)} dias na cauda"}

    def media(c):
        m = c.values[np.triu_indices_from(c.values, 1)]
        m = m[np.isfinite(m)]
        return float(m.mean()) if len(m) else None
    todos, pior = media(rets.corr()), media(cauda.corr())
    return {"ok": todos is not None and pior is not None, "todos": todos, "piores_dias": pior, "n_cauda": int(len(cauda)),
            "aumento": None if todos is None or pior is None else pior - todos}


AVISO_CORRELACAO = "Correlações do passado não ficam constantes: em crises costumam subir e a diversificação encolhe. Use-as como referência, não como garantia."


# =============================================================================== liquidez
PARTICIPACAO_PADRAO = 0.10        # fatia do volume diário que uma pessoa consegue negociar sem dominar o mercado (premissa editável)
HAIRCUT_VOLUME_ESTRESSE = 0.50    # em estresse, o volume negociado cai à metade (premissa editável)


def liquidez_negociavel(df: pd.DataFrame | None, valor_posicao: float, participacao: float = PARTICIPACAO_PADRAO, janela: int = 20, fator_cambio: float = 1.0,
                        moeda_volume: str = "BRL") -> dict:
    """Liquidez de ação, FII, ETF ou cripto a partir de OHLCV diário.
    - Liquidez média diária (ADV) = média de (fechamento × volume) dos últimos `janela` pregões, em R$.
    - Frequência de negociação = % dos últimos 60 pregões com volume > 0.
    - Dias para liquidar = valor da posição ÷ (ADV × participação).
    - Impacto potencial (ESTIMATIVA): σ diária × √(valor ÷ ADV) (regra da raiz quadrada, coeficiente 1). Spread e profundidade do livro: indisponíveis."""
    if df is None or not {"Close", "Volume"} <= set(df.columns) or len(df) < 25:
        return {"ok": False, "motivo": "sem histórico de volume"}
    c, v = df["Close"].astype(float), df["Volume"].astype(float)
    fin = (c * v * fator_cambio).iloc[-janela:]
    adv = float(fin.mean())
    freq = float((v.iloc[-60:] > 0).mean())
    sd = float(c.pct_change().iloc[-60:].std(ddof=1))
    if adv <= 0 or not valor_posicao or valor_posicao <= 0:
        return {"ok": False, "motivo": "volume financeiro nulo no período", "adv": adv, "freq": freq}
    dias = valor_posicao / (adv * participacao)
    return {"ok": True, "adv": adv, "freq": freq, "dias_liquidar": float(dias), "participacao": participacao, "valor": float(valor_posicao),
            "impacto_pct": float(sd * math.sqrt(valor_posicao / adv) * 100) if sd == sd else None, "spread": None, "profundidade": None,
            "dias_liquidar_estresse": float(dias / (1 - HAIRCUT_VOLUME_ESTRESSE)), "janela": janela,
            "metodo": f"ADV de {janela} pregões; participação de {participacao * 100:.0f}% do volume; impacto = σ√(valor/ADV) (estimativa)"}


def liquidez_renda_fixa(p: dict) -> dict:
    d = p.get("liquidez_dias")
    if d is None:
        return {"ok": False, "motivo": "prazo de liquidez do título não informado"}
    return {"ok": True, "dias_liquidar": float(d), "dias_liquidar_estresse": float(d), "metodo": "prazo contratual (carência ou vencimento); marcação a mercado pode gerar perda na venda antecipada",
            "adv": None, "freq": None, "impacto_pct": None, "spread": None, "profundidade": None}


def liquidez_fundo(p: dict) -> dict:
    d = p.get("dias_resgate")
    if d is None:
        return {"ok": False, "motivo": "prazo de resgate (cotização + liquidação) do fundo não está nos dados; consulte o regulamento"}
    return {"ok": True, "dias_liquidar": float(d), "dias_liquidar_estresse": float(d), "metodo": "prazo de resgate informado", "adv": None, "freq": None, "impacto_pct": None,
            "spread": None, "profundidade": None}


def nota_liquidez(dias: float | None) -> float | None:
    """Nota 0–100: até 1 dia = 0; 60 dias ou mais = 100 (interpolação linear)."""
    return interpolar(dias, 1.0, 60.0)


def liquidez_da_carteira(posicoes: list[dict], liq: dict[str, dict]) -> dict:
    """% do patrimônio liquidável em até 1, 5 e 30 dias (normal e em estresse), mais a lista de posições problemáticas e das sem dado."""
    pos = _validos(posicoes)
    tot = sum(p["valor"] for p in pos)
    faixas = {"em_1d": 0.0, "em_5d": 0.0, "em_30d": 0.0, "mais_30d": 0.0, "sem_dado": 0.0}
    estresse = dict(faixas)
    difíceis, sem = [], []
    for p in pos:
        if p.get("classe") == "caixa":
            for f in (faixas, estresse):
                f["em_1d"] += p["valor"]
            continue
        L = liq.get(p["id"]) or {"ok": False}
        for f, chave in ((faixas, "dias_liquidar"), (estresse, "dias_liquidar_estresse")):
            if not L.get("ok"):
                f["sem_dado"] += p["valor"]
                continue
            d = L[chave]
            f["em_1d" if d <= 1 else "em_5d" if d <= 5 else "em_30d" if d <= 30 else "mais_30d"] += p["valor"]
        if not L.get("ok"):
            sem.append(p["id"])
        elif L["dias_liquidar"] > 5:
            difíceis.append({"id": p["id"], "dias": L["dias_liquidar"], "pct": p["valor"] / tot * 100})
    pct = lambda f: {k: (v / tot * 100 if tot else 0.0) for k, v in f.items()}
    return {"normal": pct(faixas), "estresse": pct(estresse), "dificeis": sorted(difíceis, key=lambda x: -x["dias"]), "sem_dado": sem,
            "aviso": "Estresse = volume negociado cai à metade (premissa). Spread e profundidade do livro de ofertas não estão disponíveis."}


# =============================================================================== metodologia por classe (nota 0–100)
# Cada componente: id, rótulo, peso, âncoras (valor que vale 0, valor que vale 100), tipo e fórmula/fonte em texto.
# tipo: "calculado" (série de preços ou campo medido) | "estimado" (premissa de modelo) | "proxy" (regra qualitativa fixa, mostrada como tal; nunca número inventado).
def _c(i, rot, peso, anc, tipo, formula):
    return {"id": i, "rotulo": rot, "peso": peso, "ancoras": anc, "tipo": tipo, "formula": formula}


_VOL = lambda a, b, p=0.30: _c("vol", "Volatilidade anualizada (12m)", p, (a, b), "calculado", f"σ dos retornos diários × √252; {a:g}% = nota 0, {b:g}% = nota 100")
_DD = lambda a, b, p=0.20: _c("dd", "Pior queda do pico (12m)", p, (a, b), "calculado", f"maior queda do pico ao fundo em 12 meses; {a:g}% = nota 0, {b:g}% = nota 100")
_LIQ = lambda a, b, p=0.15: _c("liq", "Dias para liquidar a posição", p, (a, b), "estimado", f"valor ÷ (liquidez média diária × 10% de participação); {a:g} dia = 0, {b:g} dias = 100")
_CAMBIO = lambda p=0.05: _c("cambio", "Exposição cambial direta", p, (0, 1), "calculado", "1 se a moeda do ativo não é o real, 0 se é; nota = valor × 100")

METODOLOGIA = {
    "acao": [_VOL(15, 70, 0.30), _DD(-10, -60, 0.20), _LIQ(0.1, 10, 0.15),
             _c("div_pl", "Endividamento (dívida ÷ patrimônio)", 0.15, (0, 300), "calculado", "Yahoo Finance; 0% = nota 0, 300% = nota 100. Bancos e seguradoras não têm esse indicador comparável: ficam sem o componente"),
             _c("reg", "Risco regulatório e operacional do setor", 0.10, (0, 100), "proxy", "regra fixa: setor regulado (utilidade pública, financeiro, saúde, petróleo e energia) = 60; demais = 30. É um proxy qualitativo, não uma medida"),
             _CAMBIO(0.10)],
    "bdr": [_VOL(15, 70, 0.30), _DD(-10, -60, 0.20), _LIQ(0.1, 10, 0.15),
            _c("div_pl", "Endividamento (dívida ÷ patrimônio)", 0.15, (0, 300), "calculado", "Yahoo Finance; 0% = nota 0, 300% = nota 100"),
            _c("reg", "Risco regulatório e operacional do setor", 0.10, (0, 100), "proxy", "regra fixa: setor regulado = 60; demais = 30"),
            _c("cambio", "Exposição cambial (ativo no exterior)", 0.10, (0, 1), "calculado", "BDR replica ativo em dólar: sempre 1")],
    "fii": [_VOL(8, 35, 0.20), _DD(-5, -35, 0.15), _LIQ(0.1, 10, 0.15),
            _c("vacancia", "Vacância média", 0.20, (0, 25), "calculado", "Fundamentus (fundos de tijolo); 0% = nota 0, 25% = nota 100"),
            _c("inadimplencia", "Inadimplência / qualidade dos CRIs", 0.10, (0, 10), "calculado", "só se o dado existir na base; 0% = 0, 10% = 100"),
            _c("conc_imoveis", "Concentração de imóveis", 0.10, (10, 1), "calculado", "nº de imóveis: 1 imóvel = nota 100, 10 ou mais = nota 0"),
            _c("juros", "Sensibilidade aos juros", 0.10, (0, 100), "proxy", "FIIs perdem valor quando os juros sobem (premissa do app: −3% por +1 p.p.); proxy fixo = 50")],
    "cripto": [_VOL(40, 120, 0.30), _DD(-30, -85, 0.20), _LIQ(0.005, 1, 0.10),
               _c("desbloqueio", "Desbloqueio de tokens (próximos 90 dias)", 0.10, (0, 10), "calculado", "% da oferta circulante a liberar em eventos com fonte; 0% = 0, 10% = 100"),
               _c("contrato", "Risco de smart contract / protocolo", 0.10, (0, 100), "proxy", "rede principal própria (Bitcoin, Ethereum, Solana...) = 30; token em outra rede ou stablecoin = 60; rede desconhecida = sem dado"),
               _c("custodia", "Risco de custódia e exchange", 0.10, (0, 100), "proxy", "custódia própria = 40; exchange ou corretora = 60 (risco de contraparte); não informado = sem dado"),
               _c("reg", "Risco regulatório", 0.10, (0, 100), "proxy", "regra fixa = 60 para todo o mercado cripto (regras ainda em evolução)")],
    "etf": [_VOL(10, 60, 0.25), _DD(-8, -50, 0.15), _LIQ(0.1, 10, 0.15),
            _c("te", "Tracking error vs. benchmark", 0.15, (0, 10), "calculado", "σ(retorno − benchmark) × √252, 12m; 0% = 0, 10% = 100"),
            _c("taxa", "Taxa de administração", 0.10, (0, 2), "calculado", "% a.a.; 0 = nota 0, 2% = nota 100"),
            _c("conc_etf", "Concentração da carteira do ETF", 0.10, (10, 80), "calculado", "% das 10 maiores posições; só se o dado existir"),
            _CAMBIO(0.10)],
    "fundo": [_VOL(2, 30, 0.25), _DD(-3, -35, 0.20),
              _c("liq_fundo", "Prazo de resgate", 0.15, (1, 60), "calculado", "dias para ter o dinheiro (cotização + liquidação); 1 dia = 0, 60 dias = 100"),
              _c("taxa", "Taxa de administração", 0.10, (0, 3), "calculado", "% a.a.; 0 = nota 0, 3% = nota 100"),
              _c("te", "Tracking error vs. benchmark", 0.10, (0, 10), "calculado", "σ(retorno − benchmark) × √252, 12m"),
              _c("gestao", "Risco de gestão", 0.10, (0, 100), "proxy", "fundo ativo = 50 (desempenho depende do gestor); passivo/indexado = 20; não informado = sem dado"),
              _CAMBIO(0.10)],
    "renda_fixa": [_c("credito", "Risco de crédito do emissor", 0.30, (1, 5), "calculado", "classe de crédito cadastrada (1 = soberano ou muito forte, 5 = fraco); 1 = nota 0, 5 = nota 100"),
                   _c("duracao", "Duration (sensibilidade aos juros)", 0.20, (0, 8), "calculado", "anos; 0 = nota 0, 8 anos = nota 100. Perda aproximada = duration × alta dos juros (p.p.)"),
                   _c("liq_rf", "Prazo para resgatar", 0.15, (0, 720), "calculado", "dias de carência ou até o vencimento; 0 = nota 0, 720 dias = 100"),
                   _c("fgc", "Proteção do FGC", 0.15, (0, 100), "proxy", "emissor soberano = 0; coberto pelo FGC (até o limite por CPF e instituição) = 25; sem cobertura = 70. A regra tem limites e não elimina o risco"),
                   _c("reinv", "Risco de reinvestimento", 0.10, (3, 0), "estimado", "anos até o vencimento: 3 anos ou mais = nota 0 (taxa travada), vencimento próximo = nota 100"),
                   _c("indexador", "Risco de indexador", 0.10, (0, 100), "proxy", "pós-fixado = 20; IPCA+ = 40; prefixado = 55 (maior risco de marcação a mercado)")],
    "caixa": [_c("caixa", "Caixa", 1.0, (0, 100), "proxy", "sem risco de preço; perde poder de compra se render menos que a inflação. Nota fixa = 5")],
}
METODOLOGIA["outro"] = [_VOL(15, 70, 0.5), _DD(-10, -60, 0.5)]
LIMITE_PROVISORIA, LIMITE_INDETERMINADA = 0.40, 0.25
DIAS_DADO_VELHO = 7
SETORES_REGULADOS = {"Utilidade pública", "Financeiro", "Saúde", "Petróleo e energia"}


def _anos_ate(venc, hoje: date) -> float | None:
    try:
        return (pd.Timestamp(venc).date() - hoje).days / 365.25
    except Exception:
        return None


def _valores_do_ativo(p: dict, dados: dict, hoje: date) -> dict:
    """{id_componente: (valor, fonte)}. Só coloca o que está realmente disponível; o resto fica de fora (ausente)."""
    c, ind = p.get("classe", "outro"), dados.get("ind") or {}
    v: dict[str, tuple] = {}
    ser = padronizar_dias_uteis(dados.get("serie")) if dados.get("serie") is not None else pd.Series(dtype=float)
    if len(ser) >= 120:
        r = ser.pct_change().dropna()
        vj = vol_janelas(r, {"12 meses": 252}).get("12 meses", {})
        if _ok(vj.get("vol_anual")):
            v["vol"] = (vj["vol_anual"] * 100, "série de preços (dias úteis)")
        j = ser.iloc[-252:]
        v["dd"] = (float((j / j.cummax() - 1).min() * 100), "série de preços (12m)")
    else:
        if _ok(ind.get("vol")):
            v["vol"] = (float(ind["vol"]), "Comparador (12m)")
        if _ok(ind.get("dd_max")):
            v["dd"] = (float(ind["dd_max"]), "Comparador (12m)")
    L = dados.get("liq") or {}
    if L.get("ok"):
        v["liq"] = (L["dias_liquidar"], "OHLCV (liquidez média × 10%)")
    elif c in ("acao", "bdr", "fii", "etf", "cripto") and _ok(ind.get("liq")) and ind["liq"] > 0 and _ok(p.get("valor")):
        v["liq"] = (p["valor"] / (ind["liq"] * PARTICIPACAO_PADRAO), "Comparador (liquidez 90d × 10%)")
    cambio = 1.0 if (p.get("moeda", "BRL") != "BRL" or c == "bdr") else 0.0
    if c in ("acao", "bdr", "etf", "fundo"):
        v["cambio"] = (cambio, "cadastro da posição")
    if c in ("acao", "bdr"):
        if _ok(ind.get("div_pl")) and p.get("setor") not in ("Financeiro",):
            v["div_pl"] = (float(ind["div_pl"]), "Yahoo Finance")
        v["reg"] = (60.0 if p.get("setor") in SETORES_REGULADOS else 30.0, "regra por setor")
    if c == "fii":
        for k, ik in (("vacancia", "vacancia"), ("inadimplencia", "inadimplencia"), ("conc_imoveis", "qtd_imoveis")):
            if _ok(ind.get(ik)):
                v[k] = (float(ind[ik]), "Fundamentus")
        v["juros"] = (50.0, "premissa do app")
    if c in ("etf", "fundo"):
        if _ok(dados.get("te")):
            v["te"] = (dados["te"], "série vs. benchmark")
        if _ok(ind.get("taxa_adm")):
            v["taxa"] = (float(ind["taxa_adm"]), "CVM / Yahoo")
        if c == "etf" and _ok(ind.get("conc_top10")):
            v["conc_etf"] = (float(ind["conc_top10"]), "carteira do ETF")
    if c == "fundo":
        d = p.get("dias_resgate") if _ok(p.get("dias_resgate")) else ind.get("liquidez_dias")
        if _ok(d):
            v["liq_fundo"] = (float(d), "cadastro")
        if p.get("gestao_tipo") in ("ativo", "passivo"):
            v["gestao"] = (50.0 if p["gestao_tipo"] == "ativo" else 20.0, "cadastro")
    if c == "cripto":
        if _ok(dados.get("desbloqueio_pct")):
            v["desbloqueio"] = (float(dados["desbloqueio_pct"]), "eventos de desbloqueio informados")
        rede = rede_do_ativo(p["id"])
        if rede != NI:
            v["contrato"] = (30.0 if rede == re.split(r"[-/]", p["id"].upper())[0].title() or rede in ("Bitcoin", "Ethereum", "Solana", "Cardano", "XRP Ledger", "Litecoin", "Dogecoin", "BNB Chain", "Avalanche", "Polkadot", "Tron", "Polygon")
                             else 60.0, "rede do ativo")
        cust = str(p.get("custodiante") or p.get("corretora") or "").lower()
        if cust:
            v["custodia"] = (40.0 if any(x in cust for x in ("própria", "propria", "ledger", "trezor", "cold", "self")) else 60.0, "cadastro de custódia")
        v["reg"] = (60.0, "regra fixa")
    if c == "renda_fixa":
        if _ok(p.get("credito")):
            v["credito"] = (float(p["credito"]), "cadastro")
        if _ok(p.get("duracao")):
            v["duracao"] = (float(p["duracao"]), "cadastro")
        if _ok(p.get("liquidez_dias")):
            v["liq_rf"] = (float(p["liquidez_dias"]), "cadastro")
        emissor = str(p.get("emissor") or "")
        if emissor == "Tesouro Nacional":
            v["fgc"] = (0.0, "emissor soberano")
        elif p.get("fgc") is not None:
            v["fgc"] = (25.0 if p["fgc"] else 70.0, "cadastro (FGC)")
        a = _anos_ate(p.get("vencimento"), hoje)
        if a is not None:
            v["reinv"] = (max(a, 0.0), "vencimento")
        v["indexador"] = ({"cdi_pct": 20.0, "cdi_mais": 20.0, "selic": 20.0, "selic_mais": 20.0, "ipca": 40.0, "pre": 55.0}.get(p.get("indexador"), None) or 0.0, "indexador")
        if p.get("indexador") not in ("cdi_pct", "cdi_mais", "selic", "selic_mais", "ipca", "pre"):
            v.pop("indexador")
    if c == "caixa":
        v["caixa"] = (5.0, "regra fixa")
    return v


def confianca_rotulo(x: float) -> str:
    return "Alta" if x >= 0.75 else "Média" if x >= 0.5 else "Baixa"


def avaliar_ativo(p: dict, dados: dict | None = None, hoje: date | None = None) -> dict:
    """Classificação de risco de UMA posição, com metodologia da própria classe. Devolve nota, nível, status, confiança, componentes (valor, nota, peso, fonte, tipo),
    principais fatores, dados ausentes e uma impressão digital (hash) da entrada para auditoria.
    Falta de dado NÃO vira nota: o peso dos componentes ausentes sai do cálculo (renormaliza) e a confiança cai. Peso medido < 40% = provisória; < 25% = indeterminada."""
    dados = dados or {}
    hoje = hoje or date.today()
    c = p.get("classe", "outro")
    espec = METODOLOGIA.get(c, METODOLOGIA["outro"])
    vals = _valores_do_ativo(p, dados, hoje)
    comps, ausentes = [], []
    for e in espec:
        if e["id"] in vals:
            val, fonte = vals[e["id"]]
            a, b = e["ancoras"]
            nota = float(val) if e["tipo"] == "proxy" else interpolar(val if e["id"] not in ("cambio",) else val, a, b)
            if e["id"] in ("dd", "reinv"):
                pass
            comps.append({**e, "valor": val, "nota": nota, "fonte": fonte, "contribuicao": None})
        else:
            ausentes.append({"id": e["id"], "rotulo": e["rotulo"], "peso": e["peso"], "tipo": e["tipo"]})
    total = sum(e["peso"] for e in espec)
    medido = sum(x["peso"] for x in comps if x["nota"] is not None)
    conf = medido / total if total else 0.0
    nota = None
    if medido > 0:
        nota = sum(x["nota"] * x["peso"] for x in comps if x["nota"] is not None) / medido
        for x in comps:
            x["contribuicao"] = x["nota"] * x["peso"] / medido if x["nota"] is not None else None
    # dado velho derruba a confiança (não a nota)
    dp = g._data(p.get("data_preco"))
    velho = dp is not None and (hoje - dp).days > DIAS_DADO_VELHO and p.get("classe") not in ("renda_fixa", "caixa", "fundo")
    if velho:
        conf *= 0.7
    status = "indeterminada" if conf < LIMITE_INDETERMINADA else "provisória" if conf < LIMITE_PROVISORIA else "definitiva"
    if status == "indeterminada":
        nota = None
    cc = sum(x["peso"] for x in comps if x["nota"] is not None and x["tipo"] == "calculado") / medido if medido else 0.0
    fatores = [{"id": x["id"], "rotulo": x["rotulo"], "valor": x["valor"], "nota": x["nota"], "contribuicao": x["contribuicao"], "tipo": x["tipo"]}
               for x in sorted([y for y in comps if y["nota"] is not None], key=lambda y: -(y["contribuicao"] or 0))[:3] if x["nota"] >= 40]
    impressao = hashlib.sha1(repr([(x["id"], round(float(x["valor"]), 4)) for x in comps] + [VERSAO_METODOLOGIA, c]).encode()).hexdigest()[:10]
    return {"id": p["id"], "nome": p.get("nome", p["id"]), "classe": c, "nota": nota, "nivel": nivel_de_nota(nota), "status": status, "confianca": conf,
            "confianca_rotulo": confianca_rotulo(conf), "parte_calculada": cc, "componentes": comps, "ausentes": ausentes, "fatores": fatores, "dado_velho": velho,
            "atualizado_em": hoje.isoformat(), "versao_metodologia": VERSAO_METODOLOGIA, "impressao": impressao,
            "texto": explicar_nota_simples(p["id"], c, nota, status, conf, fatores, ausentes)}


def explicar_nota_simples(ident, classe, nota, status, conf, fatores, ausentes) -> str:
    if nota is None:
        return (f"{ident}: risco INDETERMINADO — só {conf * 100:.0f}% da metodologia de {g.CLASSES.get(classe, classe)} pôde ser medida. "
                "Isso é falta de dado, não sinal de segurança.")
    t = f"{ident}: nota {nota:.0f}/100 ({nivel_de_nota(nota)}), confiança {confianca_rotulo(conf).lower()} ({conf * 100:.0f}% da metodologia medida)."
    if status == "provisória":
        t += " Classificação PROVISÓRIA: faltam muitos dados."
    if fatores:
        t += " Pesa mais: " + "; ".join(f"{f['rotulo']} (nota {f['nota']:.0f})" for f in fatores) + "."
    if ausentes:
        t += " Sem dado: " + ", ".join(a["rotulo"].lower() for a in ausentes[:4]) + "."
    return t


def comparar_classificacoes(a: dict, b: dict) -> dict | None:
    """Mudança entre duas classificações do mesmo ativo (para histórico e alertas). None se nada relevante mudou (≥ 5 pontos ou troca de nível)."""
    if a.get("nota") is None or b.get("nota") is None:
        return None
    d = b["nota"] - a["nota"]
    if abs(d) < 5 and a["nivel"] == b["nivel"]:
        return None
    return {"de": a["nota"], "para": b["nota"], "variacao": d, "nivel_de": a["nivel"], "nivel_para": b["nivel"], "subiu": d > 0}


def registrar_nota(historico: dict | None, res: dict, maximo: int = 60) -> tuple[dict, dict | None]:
    """Acrescenta a classificação ao histórico {id: [{data, nota, nivel, confianca, status, versao, impressao}]} quando mudou ≥ 5 pontos, trocou de nível, trocou
    a versão da metodologia ou é a primeira. Devolve (histórico novo, mudança ou None). Um registro por dia no máximo."""
    h = {k: list(v) for k, v in (historico or {}).items()}
    lst = h.setdefault(res["id"], [])
    nova = {"data": res["atualizado_em"], "nota": res["nota"], "nivel": res["nivel"], "confianca": round(res["confianca"], 3), "status": res["status"],
            "versao": res["versao_metodologia"], "impressao": res["impressao"]}
    if lst and lst[-1]["data"] == nova["data"]:
        lst[-1] = nova
        return h, None
    ant = lst[-1] if lst else None
    mud = comparar_classificacoes(ant, nova) if ant else None
    if ant is None or mud or ant["versao"] != nova["versao"] or ant["status"] != nova["status"]:
        lst.append(nova)
    h[res["id"]] = lst[-maximo:]
    return h, mud


# =============================================================================== exposições (câmbio, juros, crédito)
def exposicao_cambial(posicoes: list[dict]) -> dict:
    """Quanto do patrimônio reage ao dólar. 'Direta' = ativo cotado em outra moeda. 'Indireta' = BDR e cripto (cotados em R$ ou em dólar, mas que seguem ativos em dólar)."""
    pos = _validos(posicoes)
    tot = sum(p["valor"] for p in pos)
    if tot <= 0:
        return {"ok": False}
    direta = sum(p["valor"] for p in pos if p.get("moeda", "BRL") != "BRL")
    indireta = sum(p["valor"] for p in pos if p.get("moeda", "BRL") == "BRL" and p.get("classe") in ("bdr", "cripto"))
    return {"ok": True, "por_moeda": distribuicao_eixo(posicoes, "moeda"), "direta_pct": direta / tot * 100, "indireta_pct": indireta / tot * 100,
            "total_pct": (direta + indireta) / tot * 100, "texto": "Direta: ativos em moeda estrangeira. Indireta: BDRs e criptomoedas."}


def exposicao_juros(posicoes: list[dict], prem: dict | None = None) -> dict:
    """Perda estimada para +1 p.p. nos juros (duration dos títulos prefixados e IPCA+, sensibilidade assumida dos FIIs; ver gestao_otimiza.PREMISSAS)."""
    pos = _validos(posicoes)
    tot = sum(p["valor"] for p in pos)
    if tot <= 0:
        return {"ok": False}
    s = O.simular_cenario(pos, {"juros_pp": 1.0}, prem)
    sens = [l for l in s["posicoes"] if abs(l["delta"]) > 1e-9]
    rf = [p for p in pos if p.get("classe") == "renda_fixa" and p.get("indexador") in ("pre", "ipca")]
    v_rf = sum(p["valor"] for p in rf)
    dur = (sum(p["valor"] * (p["duracao"] if _ok(p.get("duracao")) else O.PREMISSAS["duracao_padrao_rf"]) for p in rf) / v_rf) if v_rf else None
    return {"ok": True, "delta_1pp": s["delta"], "pct_1pp": s["pct"], "sensiveis": sens, "duration_media": dur, "pct_prefixado_ipca": v_rf / tot * 100,
            "pct_pos_fixado": sum(p["valor"] for p in pos if p.get("classe") == "renda_fixa" and p.get("indexador") not in ("pre", "ipca")) / tot * 100,
            "premissa": "marcação a mercado: perda ≈ −duration × alta dos juros; FIIs: −3% por +1 p.p. (editável). Pós-fixados não têm perda de marcação relevante."}


def exposicao_credito(posicoes: list[dict]) -> dict:
    pos = _validos(posicoes)
    tot = sum(p["valor"] for p in pos)
    rf = [p for p in pos if p.get("classe") == "renda_fixa"]
    if tot <= 0:
        return {"ok": False}
    v_rf = sum(p["valor"] for p in rf)
    priv = [p for p in rf if p.get("emissor") != "Tesouro Nacional"]
    por_nota: dict = {}
    for p in rf:
        k = int(p["credito"]) if _ok(p.get("credito")) else None
        por_nota[k] = por_nota.get(k, 0.0) + p["valor"]
    sem_fgc = [p for p in priv if not p.get("fgc")]
    return {"ok": True, "renda_fixa_pct": v_rf / tot * 100, "privado_pct": sum(p["valor"] for p in priv) / tot * 100,
            "privado_sem_fgc_pct": sum(p["valor"] for p in sem_fgc) / tot * 100, "por_nota": {("sem classe" if k is None else k): v / tot * 100 for k, v in sorted(por_nota.items(), key=lambda x: (x[0] is None, x[0]))},
            "credito_medio": (sum(p["valor"] * p["credito"] for p in rf if _ok(p.get("credito"))) / sum(p["valor"] for p in rf if _ok(p.get("credito")))) if any(_ok(p.get("credito")) for p in rf) else None,
            "texto": "FGC cobre até R$ 250 mil por CPF e instituição (limite global de R$ 1 milhão a cada 4 anos) e não cobre todos os produtos; confira as regras vigentes."}


# =============================================================================== risco da carteira
PESOS_NOTA_CARTEIRA = {"ativos": 0.40, "vol": 0.20, "dd": 0.15, "conc": 0.15, "liq": 0.10}
ANCORAS_CARTEIRA = {"vol": (5.0, 40.0), "dd": (3.0, 35.0), "conc": (10.0, 1.0), "liq": (0.0, 50.0)}


def risco_carteira(posicoes: list[dict], series: dict[str, pd.Series] | None = None, avaliacoes: dict[str, dict] | None = None, liq: dict[str, dict] | None = None,
                   refs: dict[str, pd.Series] | None = None, cdi_diario=None, limites: dict | None = None, hoje: date | None = None, prem: dict | None = None) -> dict:
    """Visão consolidada: nota da carteira (média ponderada das notas dos ativos + volatilidade, drawdown, concentração e liquidez da CARTEIRA) sem esconder
    os ativos: devolve também a nota de cada um, por classe, e a contribuição de cada ativo e fator para a variância. Confiança = peso medido × cobertura."""
    hoje = hoje or date.today()
    series, avaliacoes, liq, refs = series or {}, avaliacoes or {}, liq or {}, refs or {}
    pos = _validos(posicoes)
    tot = sum(p["valor"] for p in pos)
    if tot <= 0:
        return {"ok": False, "motivo": "carteira sem posições com valor"}
    pesos = {p["id"]: p["valor"] / tot for p in pos}
    pad = {k: padronizar_dias_uteis(s) for k, s in series.items() if k in pesos}
    rets = g.matriz_retornos(pad, 120)
    rc, cob = (g.retornos_da_carteira(rets, pesos) if not rets.empty else (pd.Series(dtype=float), {"cobertura": 0.0, "usados": []}))
    rb = retornos(refs.get("Ibovespa")) if refs.get("Ibovespa") is not None else None
    ind = indicadores(rc, rb, cdi_diario) if len(rc) >= 30 else {"ok": False, "motivo": "histórico comum curto demais (< 30 dias)"}
    # contribuição ao risco
    contrib = []
    if not rets.empty and rets.shape[1] >= 1 and cob.get("usados"):
        cols = cob["usados"]
        w = pd.Series({c: pesos[c] for c in cols})
        w = w / w.sum()
        cov = covariancia_anual(rets[cols].dropna())
        cr = g.contribuicao_risco(w, cov)
        vols = pd.Series(np.sqrt(np.diag(cov.values)), index=cov.index)
        by = {p["id"]: p for p in pos}
        for c in cols:
            contrib.append({"id": c, "classe": by[c].get("classe"), "peso_pct": pesos[c] * 100, "vol_anual": float(vols[c]), "contribuicao_pct": float(cr[c] * 100),
                            "fator": g.fator_de_risco(by[c])})
        contrib.sort(key=lambda x: -x["contribuicao_pct"])
    por_fator: dict = {}
    por_classe_risco: dict = {}
    for c in contrib:
        por_fator[c["fator"]] = por_fator.get(c["fator"], 0.0) + c["contribuicao_pct"]
        k = g.CLASSES.get(c["classe"], c["classe"])
        por_classe_risco[k] = por_classe_risco.get(k, 0.0) + c["contribuicao_pct"]
    # nota
    com_nota = [(p, avaliacoes.get(p["id"])) for p in pos]
    com_nota = [(p, a) for p, a in com_nota if a and a.get("nota") is not None]
    cobertura_nota = sum(p["valor"] for p, _ in com_nota) / tot
    comp: list[dict] = []
    if com_nota:
        vt = sum(p["valor"] for p, _ in com_nota)
        comp.append({"id": "ativos", "rotulo": "Média ponderada das notas dos ativos", "valor": sum(p["valor"] * a["nota"] for p, a in com_nota) / vt, "nota": sum(p["valor"] * a["nota"] for p, a in com_nota) / vt, "tipo": "calculado"})
    if ind.get("ok") and _ok(ind.get("vol_anual")):
        comp.append({"id": "vol", "rotulo": "Volatilidade da carteira (anualizada)", "valor": ind["vol_anual"] * 100, "nota": interpolar(ind["vol_anual"] * 100, *ANCORAS_CARTEIRA["vol"]), "tipo": "calculado"})
        if _ok(ind.get("mdd")):
            comp.append({"id": "dd", "rotulo": "Maior queda da carteira (histórico disponível)", "valor": abs(ind["mdd"]) * 100, "nota": interpolar(abs(ind["mdd"]) * 100, *ANCORAS_CARTEIRA["dd"]), "tipo": "calculado"})
    hh = g.concentracao([p["valor"] for p in pos])
    if hh and _ok(hh.get("n_efetivo")):
        comp.append({"id": "conc", "rotulo": "Nº efetivo de ativos (1 ÷ HHI)", "valor": hh["n_efetivo"], "nota": interpolar(hh["n_efetivo"], *ANCORAS_CARTEIRA["conc"]), "tipo": "calculado"})
    lq = liquidez_da_carteira(posicoes, liq)
    medido_liq = 100 - lq["normal"]["sem_dado"]
    if medido_liq >= 50:
        lento = lq["estresse"]["em_30d"] + lq["estresse"]["mais_30d"] + lq["estresse"]["em_5d"]
        comp.append({"id": "liq", "rotulo": "% que leva mais de 1 dia para liquidar (estresse)", "valor": lento, "nota": interpolar(lento, *ANCORAS_CARTEIRA["liq"]), "tipo": "estimado"})
    pesos_n = {e["id"]: PESOS_NOTA_CARTEIRA[e["id"]] for e in comp}
    medido = sum(pesos_n.values())
    nota = sum(e["nota"] * pesos_n[e["id"]] for e in comp) / medido if medido else None
    for e in comp:
        e["peso"] = pesos_n[e["id"]] / medido if medido else 0
        e["contribuicao"] = e["nota"] * e["peso"]
    conf = medido / sum(PESOS_NOTA_CARTEIRA.values()) * (0.5 + 0.5 * cobertura_nota)
    status = "indeterminada" if conf < LIMITE_INDETERMINADA else "provisória" if conf < LIMITE_PROVISORIA else "definitiva"
    if status == "indeterminada":
        nota = None
    ava = sorted([a for a in avaliacoes.values() if a["id"] in pesos], key=lambda a: -(a["nota"] if a["nota"] is not None else -1))
    sem_nota = [a["id"] for a in avaliacoes.values() if a["id"] in pesos and a["nota"] is None]
    est = simular_estresse(posicoes, CENARIOS_RISCO["Estresse geral"], liq, prem)
    ej = exposicao_juros(posicoes, prem)
    ex_cam, ex_cred = exposicao_cambial(posicoes), exposicao_credito(posicoes)
    perfil = perfil_de_risco(posicoes, ind, comp, lq, ej, ex_cam, ex_cred, est, avaliacoes, hh)
    pior = [e for e in comp if e["nota"] is not None]
    return {"ok": True, "nota": nota, "nivel": nivel_de_nota(nota), "status": status, "confianca": conf, "confianca_rotulo": confianca_rotulo(conf), "componentes": comp,
            "cobertura_nota_pct": cobertura_nota * 100, "cobertura_retornos_pct": cob.get("cobertura", 0.0) * 100, "dias_historico": cob.get("dias", 0),
            "indicadores": ind, "contribuicoes": contrib, "por_fator": dict(sorted(por_fator.items(), key=lambda x: -x[1])),
            "por_classe_risco": dict(sorted(por_classe_risco.items(), key=lambda x: -x[1])), "concentracao": concentracao_completa(posicoes, hoje), "hhi": hh,
            "liquidez": lq, "estresse_geral": est, "juros": ej, "cambio": ex_cam, "credito": ex_cred, "perfil": perfil, "ativos_ordenados": ava, "sem_nota": sem_nota,
            "principais_fatores": sorted(pior, key=lambda e: -e["contribuicao"])[:3], "atualizado_em": hoje.isoformat(), "versao_metodologia": VERSAO_METODOLOGIA, "patrimonio": tot,
            "texto": _texto_carteira(nota, status, conf, sorted(pior, key=lambda e: -e["contribuicao"])[:2], sem_nota)}


def _texto_carteira(nota, status, conf, fatores, sem_nota) -> str:
    if nota is None:
        return f"Risco da carteira INDETERMINADO: só {conf * 100:.0f}% da metodologia pôde ser medida (falta de dado, não segurança)."
    t = f"Nota de risco da carteira {nota:.0f}/100 ({nivel_de_nota(nota)}), confiança {confianca_rotulo(conf).lower()}."
    if status == "provisória":
        t += " Classificação provisória."
    if fatores:
        t += " Pesam mais: " + "; ".join(f"{f['rotulo']} (nota {f['nota']:.0f})" for f in fatores) + "."
    if sem_nota:
        t += f" {len(sem_nota)} ativo(s) sem nota por falta de dado: {', '.join(sem_nota[:5])}."
    return t


def perfil_de_risco(posicoes, ind, comp, lq, ej, ex_cam, ex_cred, est, avaliacoes, hh) -> list[dict]:
    """Os 14 riscos pedidos, cada um com seu valor, sua nota (quando há como medir) e o TIPO do número: calculado, estimado ou proxy qualitativo.
    Risco sem como medir com dados reais aparece como 'sem medida' — nunca como zero."""
    def nota_de(i):
        return next((e["nota"] for e in comp if e["id"] == i), None)
    tot = sum(p["valor"] for p in _validos(posicoes))

    def media_comp(cid):
        xs = [(p["valor"], c["nota"]) for p in _validos(posicoes) for c in (avaliacoes.get(p["id"]) or {}).get("componentes", []) if c["id"] == cid and c["nota"] is not None]
        return sum(v * n for v, n in xs) / sum(v for v, _ in xs) if xs else None
    cripto = sum(p["valor"] for p in _validos(posicoes) if p.get("classe") == "cripto") / tot * 100 if tot else 0
    cred_n = interpolar(ex_cred.get("credito_medio"), 1, 5) if ex_cred.get("ok") and ex_cred.get("credito_medio") else None
    if cred_n is not None and ex_cred["renda_fixa_pct"] < 100:
        cred_n *= ex_cred["renda_fixa_pct"] / 100
    P = [
        ("individual", "Risco individual dos ativos", nota_de("ativos"), "calculado", "média ponderada das notas por classe"),
        ("mercado", "Risco de mercado", nota_de("vol"), "calculado", "volatilidade anualizada da carteira"),
        ("volatilidade", "Volatilidade", nota_de("vol"), "calculado", "σ diária × √252"),
        ("concentracao", "Concentração", nota_de("conc"), "calculado", "nº efetivo de ativos (1 ÷ HHI)"),
        ("liquidez", "Liquidez", nota_de("liq"), "estimado", "% que leva mais de 1 dia para liquidar em estresse"),
        ("credito", "Crédito", cred_n, "calculado", "crédito médio da renda fixa × peso da renda fixa"),
        ("cambial", "Cambial", interpolar(ex_cam.get("total_pct"), 0, 100) if ex_cam.get("ok") else None, "calculado", "% do patrimônio exposto ao dólar (direta + indireta)"),
        ("juros", "Juros (marcação a mercado)", interpolar(-ej.get("pct_1pp"), 0, 5) if ej.get("ok") else None, "estimado", "perda estimada para +1 p.p. nos juros; 5% de perda = nota 100"),
        ("extremos", "Eventos extremos", interpolar(-est["pct"], 0, 40) if est.get("antes") else None, "estimado", "perda no cenário hipotético “Estresse geral”; 40% de perda = nota 100"),
        ("regulatorio", "Regulatório (proxy)", media_comp("reg"), "proxy", "regra por setor/classe, sem medida de mercado"),
        ("operacional", "Operacional (proxy)", media_comp("contrato"), "proxy", "smart contract e protocolo (cripto); demais classes sem medida"),
        ("contraparte", "Contraparte e custódia (proxy)", media_comp("custodia"), "proxy", "custódia/exchange (cripto); emissor bancário em renda fixa aparece em Crédito"),
        ("setor", "Setor", None, "calculado", "ver Concentração por setor"),
        ("emissor", "Emissor", None, "calculado", "ver Concentração por emissor"),
    ]
    out = []
    for i, r, n, t, f in P:
        out.append({"id": i, "rotulo": r, "nota": n, "nivel": nivel_de_nota(n) if n is not None else "Sem medida", "tipo": t, "formula": f})
    # setor e emissor: maior fatia (%), nota por interpolação 10→90
    for i, eixo in (("setor", "setor"), ("emissor", "emissor")):
        dist = [d for d in distribuicao_eixo(posicoes, eixo) if d["nome"] not in (NI, "Tesouro Nacional", "Caixa", "Renda fixa")]
        item = next(x for x in out if x["id"] == i)
        if dist:
            item["nota"] = interpolar(dist[0]["pct"], 10, 90)
            item["nivel"] = nivel_de_nota(item["nota"])
            item["formula"] = f"maior {eixo}: {dist[0]['nome']} ({dist[0]['pct']:.0f}% do patrimônio); 10% = nota 0, 90% = nota 100"
    if cripto and not any(x["id"] == "operacional" and x["nota"] is not None for x in out):
        pass
    return out


# =============================================================================== testes de estresse
CENARIOS_RISCO = {
    "Queda generalizada da bolsa": {"bolsa_br": -30.0, "bolsa_ext": -25.0, "cripto": -50.0},
    "Alta abrupta dos juros": {"juros_pp": 4.0},
    "Aumento da inflação": {"inflacao_pp": 3.0, "juros_pp": 2.0},
    "Desvalorização cambial (dólar +25%)": {"usd": 25.0},
    "Crise de crédito": {"spread_pp": 3.0, "bolsa_br": -15.0, "bolsa_ext": -10.0, "fii_pct": -10.0},
    "Queda acentuada do Bitcoin": {"cripto": -60.0},
    "Problemas em exchanges": {"cripto": -25.0, "exchange_pct": -30.0},
    "Crise imobiliária": {"fii_pct": -30.0, "spread_pp": 2.0},
    "Aumento de spreads de crédito": {"spread_pp": 2.0},
    "Redução da liquidez": {"liquidez_haircut_pct": 10.0, "bolsa_br": -10.0},
    "Estresse geral": {"bolsa_br": -25.0, "bolsa_ext": -20.0, "cripto": -45.0, "juros_pp": 2.0, "inflacao_pp": 2.0, "usd": 15.0, "spread_pp": 1.5, "fii_pct": -10.0},
}
CHOQUES_ROTULO = {"bolsa_br": "Bolsa brasileira (%)", "bolsa_ext": "Bolsa do exterior (%)", "cripto": "Criptomoedas (%)", "juros_pp": "Juros (p.p.)", "inflacao_pp": "Inflação (p.p.)",
                  "usd": "Dólar (%)", "spread_pp": "Spread de crédito privado (p.p.)", "fii_pct": "FIIs, choque adicional (%)", "exchange_pct": "Perda em cripto custodiada em exchange (%)",
                  "liquidez_haircut_pct": "Desconto para vender posições ilíquidas (%)"}
AVISO_ESTRESSE = ("Cenários são HIPÓTESES para testar a fragilidade da carteira — não são previsões. As sensibilidades são premissas simples (betas, duration, "
                  "choques); a perda real pode ser maior ou menor, e correlações costumam subir em crises.")


def _extras(p: dict, ch: dict, liq: dict | None) -> dict:
    """Efeitos que gestao_otimiza.impacto_posicao não cobre: spread de crédito, choque direto em FIIs, falha de exchange e desconto por iliquidez."""
    ex: dict[str, float] = {}
    c = p.get("classe")
    if c == "renda_fixa" and ch.get("spread_pp") and p.get("emissor") != "Tesouro Nacional":
        dur = p["duracao"] if _ok(p.get("duracao")) else O.PREMISSAS["duracao_padrao_rf"]
        mult = 1.0 + max(0.0, (p["credito"] - 2) * 0.25) if _ok(p.get("credito")) else 1.0   # crédito pior sofre mais (premissa)
        ex["spread de crédito"] = -dur * ch["spread_pp"] * mult
    if c == "fii" and ch.get("fii_pct"):
        ex["choque direto em FIIs"] = ch["fii_pct"]
    if c == "cripto" and ch.get("exchange_pct"):
        cust = str(p.get("custodiante") or p.get("corretora") or "").lower()
        if not any(x in cust for x in ("própria", "propria", "ledger", "trezor", "cold", "self")):
            ex["falha de exchange"] = ch["exchange_pct"]
    if ch.get("liquidez_haircut_pct") and c not in ("caixa", "renda_fixa", "fundo"):
        L = (liq or {}).get(p["id"]) or {}
        d = L.get("dias_liquidar_estresse")
        if d is not None and d > 1:
            ex["desconto por iliquidez"] = -ch["liquidez_haircut_pct"] * min(1.0, d / 30.0)
    return ex


def simular_estresse(posicoes: list[dict], choques: dict, liq: dict | None = None, prem: dict | None = None, nome: str = "Cenário") -> dict:
    """Aplica `choques` a cada posição: impacto por ativo (com as partes de cada causa), por classe, total e as principais fontes de perda.
    Combina gestao_otimiza.impacto_posicao (mercado, juros, inflação, dólar) com spread de crédito, FIIs, exchange e iliquidez."""
    linhas, por_classe, por_fonte = [], {}, {}
    tot0 = 0.0
    for p in _validos(posicoes):
        base = O.impacto_posicao(p, choques, prem)
        ex = _extras(p, choques, liq)
        partes = {**base["partes"], **ex}
        pct = ((1 + base["pct"] / 100) * np.prod([1 + v / 100 for v in ex.values()]) - 1) * 100 if ex else base["pct"]
        # as partes de cada causa somam ao total (diferença de composição vai para 'interação')
        soma = sum(partes.values())
        if abs(soma - pct) > 1e-9:
            partes["interação entre efeitos"] = pct - soma
        d = p["valor"] * pct / 100
        tot0 += p["valor"]
        linhas.append({"id": p["id"], "classe": p.get("classe"), "valor": p["valor"], "pct": float(pct), "delta": float(d), "partes": partes, "premissa": base["premissa"]})
        por_classe[p.get("classe")] = por_classe.get(p.get("classe"), 0.0) + d
        for k, v in partes.items():
            por_fonte[k] = por_fonte.get(k, 0.0) + p["valor"] * v / 100
    dt = sum(l["delta"] for l in linhas)
    ativos = {k: v for k, v in choques.items() if v}
    return {"nome": nome, "choques": ativos, "antes": tot0, "depois": tot0 + dt, "delta": dt, "pct": dt / tot0 * 100 if tot0 > 0 else 0.0,
            "posicoes": sorted(linhas, key=lambda x: x["delta"]), "por_classe": dict(sorted(por_classe.items(), key=lambda x: x[1])),
            "fontes": dict(sorted(por_fonte.items(), key=lambda x: x[1])), "hipotetico": True, "aviso": AVISO_ESTRESSE,
            "premissas": [f"{CHOQUES_ROTULO.get(k, k)}: {v:+g}" for k, v in ativos.items()] + [f"{l['id']}: {l['premissa']}" for l in linhas[:0]]
            + [f"Beta por classe: {O.PREMISSAS['beta']}", f"Duration padrão da renda fixa sem duration: {O.PREMISSAS['duracao_padrao_rf']:g} anos", "Spread: perda = −duration × alta do spread × (1 + 0,25 por nota de crédito acima de 2)",
               f"Iliquidez: desconto × min(1, dias para liquidar em estresse ÷ 30)"]}


def comparar_cenarios(posicoes: list[dict], cenarios: dict[str, dict], liq: dict | None = None, prem: dict | None = None) -> list[dict]:
    """Roda vários cenários e ordena do pior para o melhor. Cada item: nome, delta, pct, pior ativo, maior fonte de perda."""
    out = []
    for n, ch in cenarios.items():
        s = simular_estresse(posicoes, ch, liq, prem, n)
        out.append({"nome": n, "delta": s["delta"], "pct": s["pct"], "depois": s["depois"], "pior_ativo": s["posicoes"][0]["id"] if s["posicoes"] else None,
                    "maior_fonte": next(iter(s["fontes"]), None), "detalhe": s})
    return sorted(out, key=lambda x: x["delta"])


def resumo_comparacao(lista: list[dict]) -> str:
    if not lista:
        return "Sem cenários para comparar."
    p, m = lista[0], lista[-1]
    return (f"Pior cenário: “{p['nome']}” ({p['pct']:+.1f}%, R$ {_r(p['delta'])}), puxado por {p['maior_fonte'] or 'n/d'}. "
            f"Menos severo: “{m['nome']}” ({m['pct']:+.1f}%). São hipóteses, não previsões.")


# =============================================================================== proteção de capital: drawdown, perda, redução simulada
def monitorar_drawdown(serie_valor: pd.Series | None, limite_pct: float = -20.0, aviso_frac: float = 0.75) -> dict:
    """Queda atual e máxima de uma série de VALOR (carteira ou ativo) contra o limite escolhido (negativo, em %). Situação: dentro (queda menor que 75% do limite),
    atenção (entre 75% do limite e o limite) ou excedido. Com série curta o resultado é 'sem dado'."""
    s = padronizar_dias_uteis(serie_valor) if serie_valor is not None else pd.Series(dtype=float)
    if len(s) < 20:
        return {"ok": False, "motivo": "histórico curto demais (< 20 dias úteis)"}
    d = g.drawdown(s)
    atual, mx = d["atual"] * 100, d["maximo"] * 100
    sit = "excedido" if atual <= limite_pct else "atenção" if atual <= limite_pct * aviso_frac else "dentro"
    return {"ok": True, "atual": atual, "maximo": mx, "limite": limite_pct, "situacao": sit, "pico": d["pico"], "vale": d["vale"], "recuperacao": d["recuperacao"],
            "dias": int(len(s)), "texto": f"Queda atual {atual:.1f}% (limite {limite_pct:g}%): {sit}. Maior queda no período: {mx:.1f}%."}


def perdas_sobre_custo(posicoes: list[dict], limite_pct: float = -25.0) -> list[dict]:
    """Posições cuja variação sobre o custo (valor ÷ custo − 1) está no limite de perda ou abaixo. Só com custo informado."""
    out = []
    for p in _validos(posicoes):
        c = p.get("custo")
        if not _ok(c) or c <= 0 or p.get("classe") == "caixa":
            continue
        v = (p["valor"] / c - 1) * 100
        if v <= limite_pct:
            out.append({"id": p["id"], "variacao_pct": v, "perda_brl": p["valor"] - c, "limite": limite_pct,
                        "texto": f"{p['id']}: {v:.1f}% sobre o custo (limite {limite_pct:g}%)."})
    return sorted(out, key=lambda x: x["variacao_pct"])


def sugerir_reducoes(posicoes: list[dict], limites: dict | None = None, hoje: date | None = None) -> dict[str, float]:
    """R$ a reduzir por ativo para voltar aos limites. Excesso de ativo = corte direto; excesso de grupo (setor, classe, emissor...) é dividido
    proporcionalmente entre os ativos do grupo. Para cada ativo vale o MAIOR corte pedido (não a soma), evitando cortar duas vezes pelo mesmo motivo."""
    corte: dict[str, float] = {}
    pos = {p["id"]: p for p in _validos(posicoes)}
    for ex in avaliar_limites(posicoes, limites, hoje):
        if ex["eixo"] == "ativo":
            ids = [ex["nome"]]
        else:
            ids = [i for i, p in pos.items() if eixos_da_posicao(p, hoje)[ex["eixo"]] == ex["nome"] and p.get("classe") != "caixa"]
        base = sum(pos[i]["valor"] for i in ids)
        for i in ids:
            parte = ex["excesso_brl"] * pos[i]["valor"] / base if base else 0.0
            corte[i] = max(corte.get(i, 0.0), min(parte, pos[i]["valor"]))
    return {k: v for k, v in corte.items() if v > 0.005}


def simular_reducao(posicoes: list[dict], reducoes: dict[str, float], limites: dict | None = None, choques: dict | None = None, liq: dict | None = None,
                    destino: str = "caixa", hoje: date | None = None) -> dict:
    """Simula (sem executar nada) vender `reducoes` {id: R$}. O dinheiro vai para o caixa (destino='caixa') ou sai da conta (destino='fora').
    Compara limites excedidos, maior posição, nº efetivo de ativos e perda no cenário `choques` (padrão: Estresse geral), antes e depois.
    Não considera impostos, custos, spread nem preço de execução: é uma simulação de exposição, não uma ordem."""
    choques = choques or CENARIOS_RISCO["Estresse geral"]
    pos = [dict(p) for p in _validos(posicoes)]
    tot = sum(p["valor"] for p in pos)
    novos, retirado = [], 0.0
    for p in pos:
        r = min(max(float(reducoes.get(p["id"], 0.0) or 0.0), 0.0), p["valor"])
        q = dict(p)
        if r > 0:
            f = (p["valor"] - r) / p["valor"]
            q["valor"] = p["valor"] - r
            for k in ("qtd", "custo"):
                if _ok(q.get(k)):
                    q[k] = q[k] * f
            retirado += r
        if q["valor"] > 0.005:
            novos.append(q)
    if destino == "caixa" and retirado > 0:
        cx = next((q for q in novos if q.get("classe") == "caixa"), None)
        if cx:
            cx["valor"] += retirado
        else:
            novos.append({"id": "CAIXA (simulado)", "nome": "Caixa (simulado)", "classe": "caixa", "moeda": "BRL", "pais": "Brasil", "valor": retirado, "setor": "Caixa", "emissor": "Caixa"})

    def foto(ps):
        tt = sum(p["valor"] for p in ps)
        ex = avaliar_limites(ps, limites, hoje)
        h = g.concentracao([p["valor"] for p in ps]) or {}
        mx = max(ps, key=lambda p: p["valor"]) if ps else None
        e = simular_estresse(ps, choques, liq)
        return {"total": tt, "excessos": ex, "n_excessos": len(ex), "soma_excesso_pct": sum(x["excesso_pct"] for x in ex), "n_efetivo": h.get("n_efetivo"),
                "maior": (mx["id"], mx["valor"] / tt * 100) if mx and tt else None, "perda_estresse": e["delta"], "perda_estresse_pct": e["pct"]}
    a, d = foto(pos), foto(novos)
    return {"antes": a, "depois": d, "vendido": retirado, "destino": destino, "posicoes_depois": novos,
            "melhora_excessos": a["n_excessos"] - d["n_excessos"],
            "texto": (f"Reduzir R$ {_r(retirado)} → limites excedidos: {a['n_excessos']} → {d['n_excessos']}; perda no estresse: R$ {_r(a['perda_estresse'])} → R$ {_r(d['perda_estresse'])}. "
                      "Simulação sem impostos, custos ou spread; nenhuma ordem é enviada."),
            "aviso": "Simulação de exposição. Não considera impostos, custos de corretagem, spread nem o preço real de execução. O app nunca executa vendas."}


# =============================================================================== dimensionamento de posição
Z95 = NormalDist().inv_cdf(0.95)


def dimensionar_posicao(patrimonio: float, disponivel: float, risco_max_pct: float, preco_entrada: float | None = None, stop: float | None = None,
                        vol_anual: float | None = None, exposicao_atual: float = 0.0, limite_ativo_pct: float = 20.0, atr_valor: float | None = None,
                        perda_estresse_pct: float | None = None, horizonte_dias: int = 21, multiplo_atr: float = 2.0, lote: int = 1) -> dict:
    """Quanto comprar para que a PERDA ESTIMADA no cenário adverso escolhido não passe de `risco_max_pct` do patrimônio. Métodos (todos mostram o cálculo):
    1. Stop: perda por unidade = entrada − stop; quantidade = risco em R$ ÷ perda por unidade.
    2. Volatilidade: perda adversa = 1,645 × σ anual × √(horizonte ÷ 252) (95%); valor = risco em R$ ÷ essa perda.
    3. ATR: stop implícito = entrada − múltiplo × ATR; igual ao método 1.
    4. Sem stop (fundos, renda fixa): valor = risco em R$ ÷ perda de estresse informada.
    O resultado final é o MENOR entre os métodos aplicáveis e os tetos: dinheiro disponível e limite por ativo (menos o que já se tem). Quantidade em lotes inteiros.
    Não é recomendação: depende das premissas listadas, e o stop pode ser executado a preço pior (gap)."""
    prem = [f"Patrimônio R$ {_r(patrimonio)}; risco máximo {risco_max_pct:g}% = R$ {_r(patrimonio * risco_max_pct / 100)}",
            f"Teto por ativo {limite_ativo_pct:g}% do patrimônio; já exposto R$ {_r(exposicao_atual)}; disponível R$ {_r(disponivel)}"]
    if not (_ok(patrimonio) and patrimonio > 0) or not _ok(risco_max_pct) or risco_max_pct <= 0 or not _ok(disponivel) or disponivel < 0:
        return {"ok": False, "erro": "Informe patrimônio e risco máximo maiores que zero e valor disponível não negativo.", "premissas": prem}
    risco_brl = patrimonio * risco_max_pct / 100
    teto_ativo = max(0.0, patrimonio * limite_ativo_pct / 100 - max(exposicao_atual, 0.0))
    metodos = []

    def add(nome, valor, formula, perda_pct):
        if valor is not None and valor >= 0:
            metodos.append({"metodo": nome, "valor_max": float(valor), "formula": formula, "perda_pct_adversa": perda_pct})
    if _ok(preco_entrada) and preco_entrada > 0 and _ok(stop):
        if stop >= preco_entrada:
            return {"ok": False, "erro": "O stop precisa ser menor que o preço de entrada (posição comprada).", "premissas": prem}
        perda_un = preco_entrada - stop
        add("Stop informado", risco_brl / perda_un * preco_entrada, f"R$ {_r(risco_brl)} ÷ ({preco_entrada:g} − {stop:g}) × {preco_entrada:g}", perda_un / preco_entrada * 100)
        prem.append("Stop executado ao preço do stop (gaps e baixa liquidez podem gerar perda maior).")
    if _ok(preco_entrada) and preco_entrada > 0 and _ok(atr_valor) and atr_valor > 0:
        perda_un = multiplo_atr * atr_valor
        if perda_un < preco_entrada:
            add(f"ATR ({multiplo_atr:g}×)", risco_brl / perda_un * preco_entrada, f"stop implícito = entrada − {multiplo_atr:g}×ATR ({atr_valor:g})", perda_un / preco_entrada * 100)
    if _ok(vol_anual) and vol_anual > 0:
        perda = Z95 * vol_anual * math.sqrt(horizonte_dias / DIAS_ANO)
        add(f"Volatilidade ({horizonte_dias} dias, 95%)", risco_brl / perda, f"perda adversa = 1,645 × {vol_anual * 100:.1f}% × √({horizonte_dias}/252) = {perda * 100:.1f}%", perda * 100)
        prem.append("Volatilidade do passado como medida do risco futuro; perdas maiores que o 95% ocorrem em 1 de cada 20 períodos.")
    if _ok(perda_estresse_pct) and perda_estresse_pct > 0:
        add("Perda de estresse informada", risco_brl / (perda_estresse_pct / 100), f"R$ {_r(risco_brl)} ÷ {perda_estresse_pct:g}%", perda_estresse_pct)
        prem.append("Para ativos sem stop (fundos, renda fixa): a perda de estresse é uma hipótese informada por você, não uma previsão.")
    if not metodos:
        return {"ok": False, "erro": "Informe pelo menos um destes: stop (com preço de entrada), ATR, volatilidade anual ou perda de estresse.", "premissas": prem}
    teto_risco = min(m["valor_max"] for m in metodos)
    limites_ = {"risco máximo (método mais conservador)": teto_risco, "dinheiro disponível": disponivel, "limite por ativo": teto_ativo}
    final = min(limites_.values())
    restricao = min(limites_, key=limites_.get)
    qtd = None
    if _ok(preco_entrada) and preco_entrada > 0:
        qtd = int(final // (preco_entrada * lote)) * lote
        valor = qtd * preco_entrada
    else:
        valor = final
    perda_final = valor * (min(m["perda_pct_adversa"] for m in metodos if m["valor_max"] == teto_risco) / 100) if valor else 0.0
    return {"ok": True, "valor_max": float(valor), "quantidade": qtd, "restricao": restricao, "metodos": metodos, "tetos": limites_, "risco_brl_alvo": risco_brl,
            "perda_estimada": float(perda_final), "perda_estimada_pct_patrimonio": float(perda_final / patrimonio * 100), "pct_patrimonio": float(valor / patrimonio * 100),
            "premissas": prem, "aviso": "Cálculo de tamanho máximo compatível com as premissas acima; não é recomendação de compra e não executa nada."}


# =============================================================================== alertas de risco
TIPOS_ALERTA_RISCO = {
    "nota_ativo_alta": "Nota de risco do ativo alta", "nota_subiu": "Nota de risco do ativo subiu", "nota_carteira_alta": "Nota de risco da carteira alta",
    "limite_excedido": "Limite de exposição excedido", "drawdown_carteira": "Queda da carteira além do limite", "perda_sobre_custo": "Perda sobre o custo além do limite",
    "volatilidade_subiu": "Volatilidade subiu", "correlacao_subiu": "Correlação entre ativos subiu", "liquidez_baixa": "Liquidez baixa", "estresse_perda": "Perda alta no estresse geral",
    "dado_insuficiente": "Risco indeterminado por falta de dado", "noticia_risco": "Notícia com risco para ativo da carteira",
}
PADROES_RISCO = {"nota_ativo_alta": {"nota_min": 70}, "nota_subiu": {"pontos": 10}, "nota_carteira_alta": {"nota_min": 60}, "limite_excedido": {"gravidade_min": "baixa"},
                 "drawdown_carteira": {"limite_pct": -15.0}, "perda_sobre_custo": {"limite_pct": -25.0}, "volatilidade_subiu": {"razao": 1.5}, "correlacao_subiu": {"mudanca": 0.30},
                 "liquidez_baixa": {"dias": 5.0}, "estresse_perda": {"perda_pct": 20.0}, "dado_insuficiente": {"pct_min": 10.0}, "noticia_risco": {}}


def nova_regra_risco(tipo: str, ativo: str = "*", params: dict | None = None, prioridade: str = "media", frequencia: str = "diaria", ativa: bool = True, id_: str | None = None) -> dict:
    if tipo not in TIPOS_ALERTA_RISCO:
        raise ValueError(f"Tipo de alerta de risco desconhecido: {tipo}")
    if frequencia not in I.FREQUENCIAS:
        raise ValueError("Frequência inválida.")
    p = {**PADROES_RISCO[tipo], **(params or {})}
    try:
        if tipo in ("nota_ativo_alta", "nota_carteira_alta") and not 0 < float(p["nota_min"]) <= 100:
            raise ValueError("A nota mínima deve estar entre 0 e 100.")
        if tipo == "nota_subiu" and float(p["pontos"]) <= 0:
            raise ValueError("A variação mínima deve ser maior que zero.")
        if tipo in ("drawdown_carteira", "perda_sobre_custo") and not -100 < float(p["limite_pct"]) < 0:
            raise ValueError("O limite de perda deve ser negativo (ex.: −15).")
        if tipo == "volatilidade_subiu" and float(p["razao"]) <= 1:
            raise ValueError("A razão deve ser maior que 1.")
        if tipo == "correlacao_subiu" and not 0 < float(p["mudanca"]) < 2:
            raise ValueError("A mudança de correlação deve estar entre 0 e 2.")
        if tipo == "liquidez_baixa" and float(p["dias"]) <= 0:
            raise ValueError("Os dias devem ser maiores que zero.")
        if tipo == "estresse_perda" and not 0 < float(p["perda_pct"]) <= 100:
            raise ValueError("A perda deve estar entre 0 e 100.")
        if tipo == "limite_excedido" and p["gravidade_min"] not in ("baixa", "media", "alta"):
            raise ValueError("Gravidade inválida.")
    except (TypeError, KeyError):
        raise ValueError("Parâmetros inválidos.")
    a = re.sub(r"[^A-Za-z0-9.*\-/]", "", str(ativo or "*")).upper()[:24] or "*"
    base = f"risco:{tipo}:{a}:" + ",".join(f"{k}={v}" for k, v in sorted(p.items()))
    return {"id": id_ or re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:90], "tipo": tipo, "ativo": a, "params": p, "frequencia": frequencia,
            "prioridade": prioridade if prioridade in I.PRIORIDADES else "media", "ativa": bool(ativa)}


def descrever_regra_risco(r: dict) -> str:
    p = r["params"]
    det = {"nota_ativo_alta": f"nota ≥ {p.get('nota_min')}", "nota_subiu": f"nota subiu ≥ {p.get('pontos')} pontos", "nota_carteira_alta": f"nota da carteira ≥ {p.get('nota_min')}",
           "limite_excedido": f"gravidade ≥ {p.get('gravidade_min')}", "drawdown_carteira": f"queda atual ≤ {p.get('limite_pct')}%", "perda_sobre_custo": f"≤ {p.get('limite_pct')}% sobre o custo",
           "volatilidade_subiu": f"vol. 21d ÷ 252d ≥ {p.get('razao')}", "correlacao_subiu": f"correlação subiu ≥ {p.get('mudanca')}", "liquidez_baixa": f"mais de {p.get('dias')} dias para liquidar",
           "estresse_perda": f"perda ≥ {p.get('perda_pct')}% no estresse geral", "dado_insuficiente": f"≥ {p.get('pct_min')}% do patrimônio sem classificação", "noticia_risco": "notícia de risco"}[r["tipo"]]
    return f"{TIPOS_ALERTA_RISCO[r['tipo']]} · {r['ativo']} · {det}"


def _alerta(regra, ativo, titulo, texto, valor, assinatura, dados, agora, prioridade=None):
    return {"regra_id": regra["id"], "ativo": ativo, "tipo": regra["tipo"], "prioridade": prioridade or regra["prioridade"], "titulo": titulo, "texto": texto, "valor": valor,
            "assinatura": assinatura, "data": agora.isoformat(timespec="minutes"), "dados": dados, "causa": texto,
            "detectado_em": agora.date().isoformat()}


def avaliar_alertas_risco(regras: list[dict], ctx: dict, agora: datetime | None = None) -> list[dict]:
    """Avalia as regras ativas sobre `ctx`: {'carteira': risco_carteira, 'avaliacoes': {id: avaliar_ativo}, 'mudancas_nota': {id: comparar_classificacoes},
    'limites': avaliar_limites, 'drawdown': monitorar_drawdown, 'perdas': perdas_sobre_custo(…), 'vol': {id: mudanca_volatilidade}, 'corr': mudancas_de_correlacao,
    'liq': {id: liquidez}, 'noticias': [{ativo, titulo, fonte, url, data}], 'posicoes'}. Só dispara com dado presente; cada alerta traz causa, dados usados e data da
    detecção. Formato igual ao da Central (Passo 13): passa por `filtrar_por_frequencia` para não repetir."""
    agora = agora or datetime.now()
    out = []
    ordem_g = {"baixa": 0, "media": 1, "alta": 2}
    ava, car = ctx.get("avaliacoes") or {}, ctx.get("carteira") or {}

    def alvo(r, ident):
        return r["ativo"] == "*" or r["ativo"].upper() == str(ident).upper()
    for r in regras:
        if not r.get("ativa", True):
            continue
        t, p = r["tipo"], r["params"]
        if t == "nota_ativo_alta":
            for i, a in ava.items():
                if alvo(r, i) and a.get("nota") is not None and a["nota"] >= float(p["nota_min"]):
                    out.append(_alerta(r, i, f"{i}: risco {a['nivel'].lower()} (nota {a['nota']:.0f})", a["texto"], a["nota"], f"{t}:{int(a['nota'] // 10)}",
                                       {"nota": a["nota"], "confianca": a["confianca"], "fatores": [f["rotulo"] for f in a["fatores"]], "fonte": "metodologia por classe v" + VERSAO_METODOLOGIA}, agora))
        elif t == "nota_subiu":
            for i, m in (ctx.get("mudancas_nota") or {}).items():
                if alvo(r, i) and m and m["variacao"] >= float(p["pontos"]):
                    out.append(_alerta(r, i, f"{i}: nota de risco subiu {m['variacao']:.0f} pontos", f"A nota foi de {m['de']:.0f} ({m['nivel_de']}) para {m['para']:.0f} ({m['nivel_para']}).",
                                       m["variacao"], f"{t}:{int(m['para'] // 5)}", {**m, "fonte": "histórico de classificações"}, agora))
        elif t == "nota_carteira_alta" and r["ativo"] == "*" and car.get("nota") is not None and car["nota"] >= float(p["nota_min"]):
            out.append(_alerta(r, "_carteira", f"Risco da carteira {car['nivel'].lower()} (nota {car['nota']:.0f})", car["texto"], car["nota"], f"{t}:{int(car['nota'] // 5)}",
                               {"nota": car["nota"], "confianca": car["confianca"], "componentes": {c["id"]: round(c["nota"], 1) for c in car["componentes"]}}, agora))
        elif t == "limite_excedido":
            for ex in ctx.get("limites") or []:
                if alvo(r, ex["nome"]) or (r["ativo"] == "*"):
                    if ordem_g[ex["gravidade"]] >= ordem_g[p["gravidade_min"]]:
                        out.append(_alerta(r, ex["nome"] if ex["eixo"] == "ativo" else f"{ex['rotulo']}: {ex['nome']}", f"Limite de {ex['rotulo'].lower()} excedido: {ex['nome']}", ex["texto"], ex["pct"],
                                           f"{t}:{ex['eixo']}:{ex['nome']}:{int(ex['pct'] // 5)}", {k: ex[k] for k in ("eixo", "pct", "limite", "excesso_pct", "excesso_brl")}, agora,
                                           {"alta": "alta", "media": "media", "baixa": "baixa"}[ex["gravidade"]]))
        elif t == "drawdown_carteira" and r["ativo"] == "*":
            d = ctx.get("drawdown") or {}
            if d.get("ok") and d["atual"] <= float(p["limite_pct"]):
                out.append(_alerta(r, "_carteira", f"Carteira {d['atual']:.1f}% abaixo do pico", d["texto"], d["atual"], f"{t}:{int(d['atual'] // 5)}", {k: d[k] for k in ("atual", "maximo", "limite", "dias")}, agora))
        elif t == "perda_sobre_custo":
            for x in perdas_sobre_custo(ctx.get("posicoes") or [], float(p["limite_pct"])):
                if alvo(r, x["id"]):
                    out.append(_alerta(r, x["id"], f"{x['id']}: {x['variacao_pct']:.1f}% sobre o custo", x["texto"], x["variacao_pct"], f"{t}:{int(x['variacao_pct'] // 5)}", x, agora))
        elif t == "volatilidade_subiu":
            for i, m in (ctx.get("vol") or {}).items():
                if alvo(r, i) and m and m.get("ok") and _ok(m.get("razao")) and m["razao"] >= float(p["razao"]):
                    out.append(_alerta(r, i, f"{i}: volatilidade {m['razao']:.1f}× a de longo prazo", m.get("texto", ""), m["razao"], f"{t}:{int(m['razao'] * 2)}", dict(m), agora))
        elif t == "correlacao_subiu" and r["ativo"] == "*":
            for m in ctx.get("corr") or []:
                if m["mudanca"] >= float(p["mudanca"]):
                    out.append(_alerta(r, f"{m['a']}×{m['b']}", f"Correlação {m['a']} × {m['b']} subiu", m["texto"], m["mudanca"], f"{t}:{m['a']}:{m['b']}:{int(m['mudanca'] * 10)}", dict(m), agora))
        elif t == "liquidez_baixa":
            for i, L in (ctx.get("liq") or {}).items():
                if alvo(r, i) and L.get("ok") and L["dias_liquidar"] >= float(p["dias"]):
                    out.append(_alerta(r, i, f"{i}: ~{L['dias_liquidar']:.1f} dias para liquidar", f"{L['metodo']}.", L["dias_liquidar"], f"{t}:{int(L['dias_liquidar'])}", {k: L.get(k) for k in ("dias_liquidar", "dias_liquidar_estresse", "adv", "metodo")}, agora))
        elif t == "estresse_perda" and r["ativo"] == "*":
            e = car.get("estresse_geral") or {}
            if e.get("antes") and -e["pct"] >= float(p["perda_pct"]):
                out.append(_alerta(r, "_carteira", f"Estresse geral: perda de {-e['pct']:.0f}%", f"No cenário hipotético “Estresse geral” a carteira perderia ≈ R$ {_r(-e['delta'])} ({e['pct']:.1f}%). Hipótese, não previsão.",
                                   -e["pct"], f"{t}:{int(-e['pct'] // 5)}", {"pct": e["pct"], "delta": e["delta"], "choques": e["choques"]}, agora))
        elif t == "dado_insuficiente" and r["ativo"] == "*":
            tot = sum(p_["valor"] for p_ in _validos(ctx.get("posicoes") or []))
            sem = [i for i, a in ava.items() if a.get("nota") is None]
            v = sum(p_["valor"] for p_ in _validos(ctx.get("posicoes") or []) if p_["id"] in sem)
            if tot and v / tot * 100 >= float(p["pct_min"]):
                out.append(_alerta(r, "_carteira", f"{v / tot * 100:.0f}% do patrimônio sem classificação de risco", f"Sem dado suficiente para classificar: {', '.join(sem[:6])}. Isso é incerteza, não segurança.", v / tot * 100,
                                   f"{t}:{int(v / tot * 10)}", {"ativos": sem, "pct": v / tot * 100}, agora))
        elif t == "noticia_risco":
            for n in ctx.get("noticias") or []:
                if alvo(r, n.get("ativo", "")):
                    out.append(_alerta(r, n["ativo"], f"{n['ativo']}: {I.escapar_md(n['titulo'])[:90]}", f"Notícia de risco ({n.get('fonte', 'fonte n/d')}). Notícia não confirma efeito no preço.", None,
                                       f"{t}:{n['titulo'][:40]}", {"fonte": n.get("fonte"), "url": n.get("url"), "data_noticia": n.get("data")}, agora))
    return sorted(out, key=lambda x: (I.PRIORIDADES.get(x["prioridade"], 3), x["ativo"]))


# =============================================================================== IA: explicações e respostas
def explicar_nota(a: dict) -> list[str]:
    """Passo a passo auditável da nota: cada componente com valor, âncoras, nota, peso efetivo e origem do número (calculado, estimado ou proxy)."""
    if not a:
        return ["Sem classificação para este ativo."]
    esp = {e["id"]: e for e in METODOLOGIA.get(a["classe"], METODOLOGIA["outro"])}
    L = [a["texto"], f"Metodologia de {g.CLASSES.get(a['classe'], a['classe'])} v{a['versao_metodologia']} · atualizada em {a['atualizado_em']} · impressão {a['impressao']}."]
    for c in sorted(a["componentes"], key=lambda x: -(x.get("contribuicao") or 0)):
        L.append(f"• {c['rotulo']}: {c['valor']:.2f} → nota {c['nota']:.0f} (peso efetivo {c['peso'] / max(sum(x['peso'] for x in a['componentes'] if x['nota'] is not None), 1e-9) * 100:.0f}%, {c['tipo']}; fonte: {c['fonte']}). Regra: {esp[c['id']]['formula']}.")
    for x in a["ausentes"]:
        L.append(f"• Sem dado: {x['rotulo']} (peso {x['peso'] * 100:.0f}%). Fica fora da nota e reduz a confiança; não significa baixo risco.")
    if a["dado_velho"]:
        L.append("• Preço desatualizado: a confiança foi reduzida.")
    return L


def fragilidades(c: dict, limite: int = 8) -> list[dict]:
    """Pontos fracos da carteira, do mais grave ao menos: cada um com a evidência numérica. Só inclui o que os dados sustentam."""
    if not c or not c.get("ok"):
        return []
    F = []

    def add(sev, titulo, texto):
        F.append({"gravidade": sev, "titulo": titulo, "texto": texto})
    for e in c["concentracao"]["eixos"].values():
        if e["avaliavel"] and e["dist"] and e["rotulo"] not in ("Ativo", "Vencimento", "Protocolo ou rede") and e["dist"][0]["nome"] not in (NI, "Não se aplica", "Sem vencimento", "Tesouro Nacional") and e["dist"][0]["pct"] >= 60 and len(e["dist"]) > 1:
            add(2, f"{e['rotulo']} concentrado", f"{e['dist'][0]['nome']} = {e['dist'][0]['pct']:.0f}% do patrimônio.")
    if c["hhi"] and c["hhi"].get("top1", 0) >= 0.30 and len(c["ativos_ordenados"]) >= 2:
        add(3, "Uma posição domina", f"A maior posição tem {c['hhi']['top1'] * 100:.0f}% do patrimônio.")
    if c["contribuicoes"] and c["contribuicoes"][0]["contribuicao_pct"] >= 40:
        x = c["contribuicoes"][0]
        add(3, "Um ativo responde por boa parte do risco", f"{x['id']} tem {x['peso_pct']:.0f}% do patrimônio e {x['contribuicao_pct']:.0f}% da variância da carteira.")
    for f, pct in list(c["por_fator"].items())[:1]:
        if pct >= 50:
            add(2, "Risco concentrado em um fator", f"“{f}” explica {pct:.0f}% da variância da carteira.")
    L = c["liquidez"]
    if L["estresse"]["em_30d"] + L["estresse"]["mais_30d"] >= 15:
        add(2, "Liquidez baixa em estresse", f"{L['estresse']['em_30d'] + L['estresse']['mais_30d']:.0f}% do patrimônio levaria mais de 5 dias para liquidar se o volume caísse à metade.")
    if L["normal"]["sem_dado"] >= 25:
        add(1, "Liquidez sem dado", f"{L['normal']['sem_dado']:.0f}% do patrimônio não tem como medir a liquidez (prazo de resgate ou volume n/d).")
    e = c["estresse_geral"]
    if e.get("antes") and e["pct"] <= -20:
        add(3 if e["pct"] <= -30 else 2, "Perda alta no estresse geral", f"No cenário hipotético, perda de {-e['pct']:.0f}% (≈ R$ {_r(-e['delta'])}).")
    cam = c["cambio"]
    if cam.get("ok") and cam["total_pct"] >= 50:
        add(1, "Exposição ao dólar alta", f"{cam['total_pct']:.0f}% do patrimônio reage ao dólar (direta {cam['direta_pct']:.0f}%, indireta {cam['indireta_pct']:.0f}%).")
    cr = c["credito"]
    if cr.get("ok") and cr["privado_sem_fgc_pct"] >= 15:
        add(2, "Crédito privado sem FGC", f"{cr['privado_sem_fgc_pct']:.0f}% do patrimônio em renda fixa privada sem cobertura do FGC.")
    if c["sem_nota"]:
        add(1, "Ativos sem classificação", f"Sem dado para classificar: {', '.join(c['sem_nota'][:6])}. É incerteza, não segurança.")
    ind = c["indicadores"]
    if ind.get("ok") and _ok(ind.get("mdd")) and ind["mdd"] <= -0.25:
        add(2, "Queda histórica profunda", f"A carteira atual teria caído {abs(ind['mdd']) * 100:.0f}% do pico ao vale no histórico disponível ({ind['n_dias']} dias).")
    return sorted(F, key=lambda x: -x["gravidade"])[:limite]


_GATILHO_RISCO = re.compile(r"risco d[ao]s? (minha )?carteira|nota de risco|classificacao de risco|\bvar\b|\bcvar\b|value at risk|drawdown|estresse|stress|fragilidade|ponto fraco|"
                            r"concentra|exposicao|volatilidade d[ao]|dimension|tamanho d[ae] posicao|quanto (posso )?(comprar|investir) .*risco|liquidez d[ao]|correlacao|protecao de capital|"
                            r"perda maxima|quanto posso perder|por que .*(nota|classificacao|risco)|maior risco|risco total|cenarios?|sharpe|sortino|calmar|\bbeta\b|tracking error")


def eh_pergunta_risco(pergunta: str) -> bool:
    return bool(_GATILHO_RISCO.search(I._norm(pergunta)))


def _achar_id(q: str, ctx: dict) -> str | None:
    ids = set((ctx.get("avaliacoes") or {}).keys())
    for i in sorted(ids, key=len, reverse=True):
        if re.search(r"(?<![a-z0-9])" + re.escape(I._norm(i)) + r"(?![a-z0-9])", q):
            return i
    return None


def responder_risco(pergunta: str, ctx: dict | None) -> dict:
    """Responde SÓ com o que está em `ctx` (resultados dos módulos de risco). Cita números, premissas e limites; recusa compra/venda; diz quando não há dado."""
    ctx = ctx or {}
    q = I._norm(pergunta)
    car = ctx.get("carteira") or {}
    gerado = ctx.get("gerado_em")
    base = {"limite": "Métricas históricas e cenários hipotéticos, não previsões nem recomendação. Nada é comprado ou vendido pelo app.",
            "referencia": f"Risco calculado em {gerado[:16].replace('T', ' ')}" if gerado else "Sem cálculo de risco carregado",
            "consultado": "Consultei: " + (f"carteira com {len(ctx.get('avaliacoes') or {})} ativo(s), cenários e alertas." if car.get("ok") else "nada (abra a aba Risco para calcular).")}

    def resp(texto, linhas=None, falta=False):
        return {**base, "texto": texto, "linhas": linhas or [], "sem_dados": falta}
    if not q:
        return resp("Escreva uma pergunta sobre o risco da carteira ou de um ativo.", falta=True)
    if I._PEDIDO_INDICACAO.search(q):
        return resp("Eu não indico compra ou venda. Posso explicar o risco da carteira e dos ativos, mostrar concentrações, fragilidades e cenários de estresse, e simular a redução de uma exposição sem executar nada.")
    if not car.get("ok"):
        return resp("Ainda não há cálculo de risco carregado. Abra a página Risco e atualize os dados para eu consultar.", falta=True)
    ident = _achar_id(q, ctx)
    ava = ctx.get("avaliacoes") or {}
    if ident and re.search(r"por que|porque|nota|classific|explic|risco d", q):
        return resp(ava[ident]["texto"], explicar_nota(ava[ident]))
    if re.search(r"fragil|ponto fraco|vulnerab", q):
        f = fragilidades(car)
        return resp("Principais fragilidades encontradas nos dados." if f else "Não encontrei fragilidades acima dos limites usados, com os dados disponíveis.", [f"{x['titulo']}: {x['texto']}" for x in f])
    if re.search(r"cenario|estresse|stress|compar", q):
        cmp_ = ctx.get("cenarios") or []
        return resp(resumo_comparacao(cmp_) + " Hipóteses, não previsões.", [f"{x['nome']}: {x['pct']:+.1f}% (R$ {_r(x['delta'])}); maior fonte: {x['maior_fonte']}" for x in cmp_[:8]], falta=not cmp_)
    if re.search(r"concentra|exposicao|limite", q):
        lim = ctx.get("limites") or []
        ind = exposicoes_indiretas(ctx.get("posicoes") or [])
        return resp(f"{len(lim)} limite(s) excedido(s)." if lim else "Nenhum limite configurado foi excedido.", [x["texto"] for x in lim[:6]] + [x["texto"] for x in ind[:3]])
    if re.search(r"volatil", q):
        vol = ctx.get("vol") or {}
        mud = [(i, m) for i, m in vol.items() if m and m.get("ok") and _ok(m.get("razao")) and m["razao"] >= 1.5]
        ind = car["indicadores"]
        t = f"Volatilidade anualizada da carteira: {ind['vol_anual'] * 100:.1f}% (histórico comum de {ind['n_dias']} dias úteis)." if ind.get("ok") and _ok(ind.get("vol_anual")) else "Sem histórico suficiente para medir a volatilidade da carteira."
        return resp(t, [f"{i}: volatilidade recente {m['razao']:.1f}× a de longo prazo." for i, m in mud[:8]] or ["Nenhuma mudança relevante de volatilidade nos ativos com dado."])
    if re.search(r"liquidez", q):
        L = car["liquidez"]
        return resp(f"{L['normal']['em_1d']:.0f}% do patrimônio sai em até 1 dia; em estresse (volume à metade), {L['estresse']['em_1d']:.0f}%.",
                    [f"{x['id']}: ~{x['dias']:.1f} dias ({x['pct']:.0f}% do patrimônio)" for x in L["dificeis"][:6]] + ([f"Sem dado de liquidez: {', '.join(L['sem_dado'][:6])}"] if L["sem_dado"] else []))
    if re.search(r"correlac", q):
        m = ctx.get("corr") or []
        return resp((f"{len(m)} par(es) com correlação mudando." if m else "Sem mudança relevante de correlação nos dados.") + " " + AVISO_CORRELACAO, [x["texto"] for x in m[:6]])
    if re.search(r"var\b|cvar|drawdown|sharpe|sortino|calmar|beta|tracking", q):
        i = car["indicadores"]
        if not i.get("ok"):
            return resp(f"Sem indicadores: {i.get('motivo', 'dados insuficientes')}.", falta=True)
        L = []
        if _ok(i.get("var_hist_95_1d")):
            L.append(f"VaR 95% 1 dia (histórico): {i['var_hist_95_1d'] * 100:.2f}% do patrimônio; CVaR: {i['cvar_95_1d'] * 100:.2f}%." if _ok(i.get("cvar_95_1d")) else f"VaR 95% 1 dia: {i['var_hist_95_1d'] * 100:.2f}%.")
        L.append(f"Maior queda: {i['mdd'] * 100:.1f}%; queda atual: {i['dd_atual'] * 100:.1f}%.")
        for k, n in (("sharpe", "Sharpe"), ("sortino", "Sortino"), ("calmar", "Calmar"), ("beta", "Beta vs. Ibovespa")):
            if _ok(i.get(k)):
                L.append(f"{n}: {i[k]:.2f}")
        return resp("Indicadores calculados sobre o histórico disponível: descrevem o passado, não limitam perdas futuras.", L)
    if re.search(r"noticia", q):
        n = ctx.get("noticias") or []
        return resp(f"{len(n)} notícia(s) de risco ligada(s) a ativos da carteira." if n else "Nenhuma notícia de risco ligada à carteira nos dados carregados.", [f"{x['ativo']}: {x['titulo']} ({x.get('fonte', 'fonte n/d')})" for x in n[:6]], falta=not n)
    if re.search(r"maior risco|contribu|risco total|mais pesa", q):
        c = car["contribuicoes"][:5]
        return resp(car["texto"], [f"{x['id']}: {x['peso_pct']:.0f}% do patrimônio, {x['contribuicao_pct']:.0f}% da variância" for x in c] + [f"Fator “{k}”: {v:.0f}% da variância" for k, v in list(car["por_fator"].items())[:3]])
    f = fragilidades(car, 3)
    return resp(car["texto"], [f"{x['titulo']}: {x['texto']}" for x in f] + [f"Confiança {car['confianca_rotulo'].lower()}: {car['cobertura_nota_pct']:.0f}% do patrimônio classificado."])


def relatorio_md(car: dict, ava: dict[str, dict], cenarios: list[dict] | None = None, limites: list[dict] | None = None, alertas: list[dict] | None = None) -> str:
    """Relatório em Markdown (para baixar): nota, ativos, fragilidades, estresse, limites, alertas, metodologia e avisos. Só números do cálculo."""
    if not car or not car.get("ok"):
        return "# Relatório de risco\n\nSem dados para calcular.\n"
    L = ["# Relatório de risco da carteira", f"_Gerado em {car['atualizado_em']} · metodologia v{car['versao_metodologia']}_", "", f"**{car['texto']}**", "", "## Ativos", "",
         "| Ativo | Classe | Nota | Nível | Confiança |", "|---|---|---|---|---|"]
    for a in sorted(ava.values(), key=lambda a: -(a["nota"] if a["nota"] is not None else -1)):
        nt = "n/d" if a["nota"] is None else "%.0f" % a["nota"]
        L.append(f"| {a['id']} | {g.CLASSES.get(a['classe'], a['classe'])} | {nt} | {a['nivel']} | {a['confianca_rotulo']} |")
    f = fragilidades(car)
    if f:
        L += ["", "## Fragilidades"] + [f"- **{x['titulo']}**: {x['texto']}" for x in f]
    if cenarios:
        L += ["", "## Cenários de estresse (hipóteses, não previsões)"] + [f"- {x['nome']}: {x['pct']:+.1f}% (R$ {_r(x['delta'])})" for x in cenarios]
    if limites:
        L += ["", "## Limites excedidos"] + [f"- {x['texto']}" for x in limites]
    if alertas:
        L += ["", "## Alertas"] + [f"- [{x['prioridade']}] {x['titulo']} — {x['texto']} (detectado em {x['detectado_em']})" for x in alertas]
    L += ["", "## Avisos", f"- {AVISO_LEGAL}", f"- {AVISO_CORRELACAO}", f"- {AVISO_ESTRESSE}"]
    return "\n".join(L) + "\n"
