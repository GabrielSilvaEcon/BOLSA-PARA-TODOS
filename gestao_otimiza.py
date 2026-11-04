"""
Passo 12, segunda parte do motor (sem Streamlit e sem rede): otimização, rebalanceamento, renda passiva, cenários e relatório.

Tudo é SIMULAÇÃO sobre dados históricos e premissas explícitas. Nada compra, vende ou altera posição, e nenhuma estatística
histórica é apresentada como previsão: retornos e correlações do passado podem não se repetir.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

import gestao as g

_ok = g._ok


def _br(v: float, d: int = 2) -> str:
    """Número no padrão brasileiro (milhar com ponto, decimal com vírgula)."""
    return f"{v:,.{d}f}".replace(",", "X").replace(".", ",").replace("X", ".")


# =============================================================================== otimização
def covariancia(rets: pd.DataFrame, encolher: bool = True) -> pd.DataFrame:
    """Covariância ANUAL dos retornos. Com `encolher`, aplica o encolhimento de Ledoit-Wolf (alvo = variância média na
    diagonal), que estabiliza a matriz quando há poucos dias para muitos ativos."""
    x = rets.dropna().values
    n, p = x.shape
    xc = x - x.mean(axis=0)
    s = xc.T @ xc / (n - 1)
    if encolher and p > 1 and n > 3:
        mu = np.trace(s) / p
        f = mu * np.eye(p)
        d2 = ((s - f) ** 2).sum() / p
        b2 = sum(((np.outer(r, r) - s) ** 2).sum() for r in xc) / (n * n) / p if n * p <= 400_000 else d2
        delta = min(b2 / d2, 1.0) if d2 > 0 else 0.0
        s = delta * f + (1 - delta) * s
    return pd.DataFrame(s * g.DIAS_ANO, index=rets.columns, columns=rets.columns)


def _projetar(v: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Projeção euclidiana no conjunto {Σw = 1, lo ≤ w ≤ hi} (bissecção no multiplicador)."""
    a, b = float((v - hi).min()) - 1.0, float((v - lo).max()) + 1.0
    for _ in range(100):
        m = (a + b) / 2
        if np.clip(v - m, lo, hi).sum() > 1.0:
            a = m
        else:
            b = m
    return np.clip(v - (a + b) / 2, lo, hi)


def _limites(cols: list[str], lim_ativo) -> tuple[np.ndarray, np.ndarray]:
    lo = np.zeros(len(cols))
    hi = np.ones(len(cols))
    for i, c in enumerate(cols):
        a = lim_ativo.get(c, lim_ativo.get("*", (0.0, 1.0))) if isinstance(lim_ativo, dict) else lim_ativo
        lo[i], hi[i] = a
    return lo, hi


def _com_classes(v, lo, hi, classes: list[str | None], cap: dict | None):
    """Projeta no simplex com limites por ativo e, se houver, tetos por classe (reduz o teto dos membros da classe que
    estourou e projeta de novo, até 40 vezes). Devolve (pesos, ok)."""
    w = _projetar(v, lo, hi)
    if not cap:
        return w, True
    hi2 = hi.copy()
    for _ in range(40):
        viol = False
        for c, teto in cap.items():
            idx = [i for i, k in enumerate(classes) if k == c]
            s = w[idx].sum() if idx else 0.0
            if idx and s > teto + 1e-9:
                viol = True
                f = teto / s
                hi2[idx] = np.minimum(hi2[idx], np.maximum(w[idx] * f, lo[idx]))
        if not viol:
            return w, True
        w = _projetar(w, lo, hi2)
    ok = all(w[[i for i, k in enumerate(classes) if k == c]].sum() <= t + 1e-6 for c, t in cap.items())
    return w, ok


def _quadratico(S: np.ndarray, mu: np.ndarray, gamma: float, lo, hi, classes, cap, w0=None, iters: int = 3000):
    """min ½γ wᵀΣw − μᵀw sob as restrições (gradiente projetado acelerado)."""
    p = len(mu)
    L = gamma * float(np.linalg.eigvalsh(S).max()) + 1e-12
    w = _com_classes(np.full(p, 1.0 / p) if w0 is None else w0, lo, hi, classes, cap)[0]
    y, t = w.copy(), 1.0
    for _ in range(iters):
        wn = _com_classes(y - (gamma * S @ y - mu) / L, lo, hi, classes, cap)[0]
        tn = (1 + math.sqrt(1 + 4 * t * t)) / 2
        y = wn + (t - 1) / tn * (wn - w)
        if np.abs(wn - w).max() < 1e-11:
            w = wn
            break
        w, t = wn, tn
    return w


def _paridade(S: np.ndarray, lo, hi, classes, cap, iters: int = 2000):
    p = S.shape[0]
    w = np.full(p, 1.0 / p)
    for _ in range(iters):
        rc = w * (S @ w)
        tot = rc.sum()
        if tot <= 0:
            break
        nw = w * np.sqrt((tot / p) / np.maximum(rc, 1e-18))
        nw = _com_classes(nw / nw.sum(), lo, hi, classes, cap)[0]
        if np.abs(nw - w).max() < 1e-12:
            w = nw
            break
        w = nw
    return w


def estatisticas_anuais(rets: pd.DataFrame, w: np.ndarray, rf_aa: float = 0.0) -> dict:
    """Retorno (média aritmética diária × 252), volatilidade e Sharpe HISTÓRICOS de uma carteira de pesos constantes."""
    r = rets.values @ w
    ret = float(r.mean() * g.DIAS_ANO)
    vol = float(r.std(ddof=1) * math.sqrt(g.DIAS_ANO))
    return {"retorno": ret, "vol": vol, "sharpe": (ret - rf_aa) / vol if vol > 1e-12 else None}


def otimizar(rets: pd.DataFrame, metodo: str = "min_var", rf_aa: float = 0.0, lim_ativo=(0.0, 1.0), classe_de: dict | None = None,
             lim_classe: dict | None = None, mu_aa: pd.Series | None = None, encolher: bool = True, minimo_dias: int = 120) -> dict:
    """Pesos ótimos (apenas compra, sem alavancagem) pelo método: 'min_var' (variância mínima), 'max_sharpe' (máximo Sharpe)
    ou 'paridade' (paridade de risco: cada ativo contribui igualmente à variância). Limites por ativo (min, max) e tetos por
    classe. Retorno esperado = média histórica (ou `mu_aa`), que é a parte MENOS confiável: use como exploração, não promessa."""
    rets = rets.dropna()
    cols = list(rets.columns)
    if len(cols) < 2 or len(rets) < minimo_dias:
        return {"ok": False, "motivo": f"são necessários ≥ 2 ativos com ≥ {minimo_dias} dias em comum (há {len(cols)} ativos, {len(rets)} dias)"}
    S = covariancia(rets, encolher).values
    mu = (mu_aa.reindex(cols).values if mu_aa is not None else rets.mean().values * g.DIAS_ANO) - rf_aa
    lo, hi = _limites(cols, lim_ativo)
    if lo.sum() > 1 + 1e-9 or hi.sum() < 1 - 1e-9:
        return {"ok": False, "motivo": "limites por ativo impossíveis (a soma dos mínimos passa de 100% ou a dos máximos não chega a 100%)"}
    classes = [(classe_de or {}).get(c) for c in cols]
    if metodo == "min_var":
        w = _quadratico(S, np.zeros(len(cols)), 1.0, lo, hi, classes, lim_classe)
        ok_cl = True
    elif metodo == "paridade":
        w = _paridade(S, lo, hi, classes, lim_classe)
    elif metodo == "max_sharpe":
        g0 = float(np.abs(mu).mean() / max(np.diag(S).mean(), 1e-12)) or 1.0
        melhor, melhor_s = None, -1e18
        for k in np.logspace(-2, 3, 40):
            w_ = _quadratico(S, mu, g0 * k, lo, hi, classes, lim_classe, w0=None if melhor is None else melhor, iters=800)
            vol = math.sqrt(float(w_ @ S @ w_))
            s = float(mu @ w_) / vol if vol > 1e-12 else -1e18
            if s > melhor_s:
                melhor, melhor_s = w_, s
        w = melhor
    else:
        return {"ok": False, "motivo": f"método desconhecido: {metodo}"}
    ok_cl = True
    if lim_classe:
        ok_cl = all(w[[i for i, k in enumerate(classes) if k == c]].sum() <= t + 1e-6 for c, t in lim_classe.items())
    vol = math.sqrt(float(w @ S @ w))
    return {"ok": True, "pesos": pd.Series(w, index=cols), "metodo": metodo, "limites_ok": ok_cl,
            "retorno": float(mu @ w + rf_aa), "vol": vol, "sharpe": float(mu @ w) / vol if vol > 1e-12 else None,
            "contribuicao": g.contribuicao_risco(pd.Series(w, index=cols), pd.DataFrame(S, index=cols, columns=cols)),
            "dias": int(len(rets)),
            "avisos": ["Retorno e correlação do passado podem não se repetir: o resultado mostra o que teria funcionado, não o que vai funcionar.",
                       "Retorno esperado = média histórica dos últimos dias em comum: é a estimativa menos estável do modelo."] +
                      ([] if ok_cl else ["Os tetos por classe não puderam ser cumpridos totalmente com esses limites por ativo."])}


def fronteira_eficiente(rets: pd.DataFrame, pontos: int = 12, rf_aa: float = 0.0, lim_ativo=(0.0, 1.0)) -> pd.DataFrame:
    """Carteiras de menor variância para vários níveis de aversão a risco: pares (vol, retorno histórico) para o gráfico."""
    rets = rets.dropna()
    if rets.shape[1] < 2 or len(rets) < 120:
        return pd.DataFrame()
    cols = list(rets.columns)
    S = covariancia(rets).values
    mu = rets.mean().values * g.DIAS_ANO - rf_aa
    lo, hi = _limites(cols, lim_ativo)
    g0 = float(np.abs(mu).mean() / max(np.diag(S).mean(), 1e-12)) or 1.0
    out, w = [], None
    for k in np.logspace(-2, 3, pontos):
        w = _quadratico(S, mu, g0 * k, lo, hi, [None] * len(cols), None, w0=w, iters=800)
        out.append({"vol": math.sqrt(float(w @ S @ w)), "retorno": float(mu @ w) + rf_aa, **{c: float(x) for c, x in zip(cols, w)}})
    return pd.DataFrame(out).drop_duplicates(subset=["vol"]).sort_values("vol").reset_index(drop=True)


def comparar_carteiras(rets: pd.DataFrame, carteiras: dict[str, dict[str, float]], rf_diario=None) -> pd.DataFrame:
    """Métricas históricas (pesos constantes) de várias carteiras sobre o MESMO período: retorno ao ano composto, volatilidade,
    Sharpe, queda máxima e VaR 95% diário. Ativos fora dos pesos valem zero."""
    linhas = []
    for nome, pesos in carteiras.items():
        r, info = g.retornos_da_carteira(rets, pesos)
        if r.empty:
            continue
        idx = (1 + r).cumprod()
        n = len(r)
        linhas.append({"Carteira": nome, "Retorno a.a.": float(idx.iloc[-1] ** (g.DIAS_ANO / n) - 1), "Volatilidade a.a.": g.vol_anual(r, 30),
                       "Sharpe": g.sharpe(r, rf_diario, 60), "Queda máxima": g.drawdown(idx).get("maximo"),
                       "VaR 95% (1 dia)": g.var_historico(r, 0.95, 1, 100), "Dias": n})
    return pd.DataFrame(linhas)


def impacto_marginal(rets: pd.DataFrame, pesos: dict[str, float], passo: float = 0.05) -> pd.DataFrame:
    """O que acontece se `passo` (5%) do patrimônio for movido, proporcionalmente, para cada ativo: variação da volatilidade e do
    HHI. Negativo = reduz risco/concentração. Mostra quais ativos ajudam a diversificar e quais concentram."""
    rets = rets.dropna()
    cols = [c for c in rets.columns if pesos.get(c, 0) > 0] if len(rets) else []
    if len(cols) < 2:
        return pd.DataFrame()
    w0 = pd.Series({c: pesos[c] for c in cols})
    w0 = w0 / w0.sum()
    S = covariancia(rets[cols], False)

    def vol(w):
        return math.sqrt(float(w.values @ S.values @ w.values))
    v0, h0 = vol(w0), float((w0 ** 2).sum())
    linhas = []
    for c in cols:
        w1 = w0 * (1 - passo)
        w1[c] += passo
        linhas.append({"Ativo": c, "Peso atual": float(w0[c]), "Δ volatilidade (p.p.)": (vol(w1) - v0) * 100,
                       "Δ concentração (HHI)": float((w1 ** 2).sum()) - h0})
    return pd.DataFrame(linhas).sort_values("Δ volatilidade (p.p.)").reset_index(drop=True)


# =============================================================================== rebalanceamento
ALIQUOTAS_VENDA = {   # (alíquota sobre o ganho, isenção mensal de vendas em R$ ou None). Estimativa; confira a regra vigente.
    "acao": (0.15, 20_000.0), "bdr": (0.15, None), "fii": (0.20, None), "etf": (0.15, None), "cripto": (0.15, 35_000.0),
    "fundo": (0.15, None), "renda_fixa": (0.15, None), "caixa": (0.0, None), "outro": (0.15, None)}


def rebalancear_com_aporte(valores: dict[str, float], alvos: dict[str, float], aporte: float) -> dict:
    """Divide um aporte só entre as classes ABAIXO do alvo, de modo que fiquem o mais perto possível dele (preenchimento por
    nível), sem vender nada. Exato: se o aporte chega, todas atingem o alvo; se não, só as mais defasadas recebem."""
    if aporte < 0 or abs(sum(alvos.values()) - 100.0) > 0.01:
        return {"ok": False, "motivo": "alvos precisam somar 100% e o aporte não pode ser negativo"}
    v = {c: max(float(valores.get(c, 0.0)), 0.0) for c in dict.fromkeys(list(alvos) + list(valores))}
    w = {c: alvos.get(c, 0.0) / 100 for c in v}
    ativo = [c for c in v if w[c] > 0]
    comprar: dict[str, float] = {c: 0.0 for c in v}
    while ativo:
        sw = sum(w[c] for c in ativo)
        base = sum(v[c] for c in ativo) + aporte
        alvo_v = {c: w[c] / sw * base for c in ativo}
        sai = [c for c in ativo if alvo_v[c] < v[c] - 1e-9]
        if not sai:
            comprar = {c: (alvo_v[c] - v[c] if c in ativo else 0.0) for c in v}
            break
        ativo = [c for c in ativo if c not in sai]
    total = sum(v.values()) + aporte
    final = {c: v[c] + comprar[c] for c in v}
    return {"ok": True, "comprar": {c: x for c, x in comprar.items() if x > 1e-6}, "final": final,
            "pct_final": {c: final[c] / total * 100 if total > 0 else 0.0 for c in v},
            "atinge_alvo": all(abs(final[c] / total * 100 - alvos.get(c, 0.0)) < 0.01 for c in v) if total > 0 else False}


def aporte_para_rebalancear(valores: dict[str, float], alvos: dict[str, float]) -> float | None:
    """Aporte mínimo para trazer todas as classes ao alvo SEM vender: V_final = max(valor_i / alvo_i); aporte = V_final − V."""
    tot = sum(valores.values())
    razoes = [valores.get(c, 0.0) / (a / 100) for c, a in alvos.items() if a > 0]
    if not razoes or abs(sum(alvos.values()) - 100.0) > 0.01:
        return None
    if any(valores.get(c, 0.0) > 0 and alvos.get(c, 0.0) <= 0 for c in valores):
        return None            # classe com saldo e alvo zero: só vendendo
    return max(max(razoes) - tot, 0.0)


def rebalancear_com_vendas(valores: dict[str, float], custos: dict[str, float], alvos: dict[str, float], tolerancia: dict | float = 5.0,
                           corretagem_pct: float = 0.0, aliquotas: dict | None = None, vendas_mes_ja_feitas: float = 0.0) -> dict:
    """Plano de rebalanceamento por vendas: vende o excesso das classes fora da tolerância, desconta imposto estimado (alíquota
    sobre a fração de ganho da classe, com a isenção mensal de ações e cripto) e corretagem, e compra as classes defasadas com o
    que sobrou. Estimativa simplificada: não considera prejuízos a compensar, lotes específicos nem come-cotas."""
    if abs(sum(alvos.values()) - 100.0) > 0.01:
        return {"ok": False, "motivo": "alvos precisam somar 100%"}
    al = {**ALIQUOTAS_VENDA, **(aliquotas or {})}
    classes = list(dict.fromkeys(list(alvos) + list(valores)))
    v = {c: max(float(valores.get(c, 0.0)), 0.0) for c in classes}
    total = sum(v.values())
    if total <= 0:
        return {"ok": False, "motivo": "carteira sem valor"}
    des = {d["classe"]: d for d in g.desvios_do_alvo(v, alvos, tolerancia)}
    vender, falta = {}, {}
    for c in classes:
        d = des[c]
        if d["status"] == "acima":
            vender[c] = v[c] - alvos.get(c, 0.0) / 100 * total
        elif d["status"] == "abaixo":
            falta[c] = alvos.get(c, 0.0) / 100 * total - v[c]
    bruto = sum(vender.values())
    imposto: dict[str, float] = {}
    isento_usado = {}
    for c, s in vender.items():
        custo = max(float(custos.get(c, v[c])), 0.0)
        frac_ganho = max(0.0, (v[c] - custo) / v[c]) if v[c] > 0 else 0.0
        taxa, iso = al.get(c, (0.15, None))
        if iso is not None and s + (vendas_mes_ja_feitas if c == "acao" else 0.0) <= iso:
            imposto[c] = 0.0
            isento_usado[c] = True
        else:
            imposto[c] = taxa * frac_ganho * s
    total_imp = sum(imposto.values())
    taxas = corretagem_pct / 100 * bruto
    liquido = max(bruto - total_imp - taxas, 0.0)
    comprar = {}
    if falta:
        df = sum(falta.values())
        k = min(1.0, liquido / df) if df > 0 else 0.0
        comprar = {c: x * k for c, x in falta.items()}
        taxas += corretagem_pct / 100 * sum(comprar.values())
    final = {c: v[c] - vender.get(c, 0.0) + comprar.get(c, 0.0) for c in classes}
    sobra = liquido - sum(comprar.values())
    tf = sum(final.values()) + max(sobra, 0.0)
    return {"ok": True, "vender": vender, "comprar": comprar, "imposto": imposto, "imposto_total": total_imp, "corretagem_total": taxas,
            "caixa_sobra": max(sobra, 0.0), "final": final, "pct_final": {c: final[c] / tf * 100 if tf > 0 else 0.0 for c in classes},
            "isentos": sorted(isento_usado), "perda_pelo_custo": total_imp + taxas,
            "avisos": ["Imposto estimado por alíquota fixa sobre a fração de ganho da classe; prejuízos anteriores, lotes e regras "
                       "específicas (come-cotas, IR regressivo da renda fixa) não entram. Confira com seu contador ou corretora."]}


# =============================================================================== renda passiva
TIPOS_PROVENTO = {"dividendo": "Dividendos", "jcp": "Juros sobre capital próprio", "rendimento_fii": "Rendimentos de FIIs",
                  "juros": "Juros", "cupom": "Cupons", "distribuicao_fundo": "Distribuições de fundos", "amortizacao": "Amortizações"}


def renda_passiva(eventos: list[dict], hoje: date | None = None) -> dict:
    """Resume o que FOI recebido (eventos com data ≤ hoje e `efetivo`): por mês, por ano, média de 12 meses, regularidade,
    crescimento e concentração por fonte pagadora. Cada evento: {data, fonte, valor (R$), tipo, efetivo}. Projeções ficam
    à parte (veja projetar_repetindo_12m e projetar_contratual): não se misturam com o recebido."""
    hoje = hoje or date.today()
    ef = [e for e in eventos if e.get("efetivo", True) and g._data(e.get("data")) and g._data(e["data"]) <= hoje and _ok(e.get("valor"))]
    if not ef:
        return {"ok": False, "motivo": "nenhum provento recebido registrado/encontrado"}
    df = pd.DataFrame([{"data": pd.Timestamp(g._data(e["data"])), "fonte": e.get("fonte", "?"), "valor": float(e["valor"]),
                        "tipo": e.get("tipo", "dividendo")} for e in ef])
    df["mes"] = df["data"].dt.to_period("M")
    fim = pd.Period(hoje, "M")
    meses = pd.period_range(df["mes"].min(), fim, freq="M")
    mensal = df.groupby("mes")["valor"].sum().reindex(meses, fill_value=0.0)
    anual = df.groupby(df["data"].dt.year)["valor"].sum()
    u12 = mensal.iloc[-12:]
    a12, p12 = float(u12.sum()), float(mensal.iloc[-24:-12].sum()) if len(mensal) > 12 else None
    por_fonte = df.groupby("fonte")["valor"].sum().sort_values(ascending=False)
    pf = por_fonte / por_fonte.sum()
    por_tipo = df.groupby("tipo")["valor"].sum().sort_values(ascending=False)
    janela = mensal.iloc[-12:]
    cv = float(janela.std(ddof=1) / janela.mean()) if janela.mean() > 0 and len(janela) > 1 else None
    return {"ok": True, "total": float(df["valor"].sum()), "mensal": mensal, "anual": anual,
            "rolante_12m": mensal.rolling(12, min_periods=12).sum().dropna(), "ultimos_12m": a12,
            "media_mensal_12m": a12 / min(12, len(mensal)), "anterior_12m": p12,
            "crescimento_12m": (a12 / p12 - 1) if p12 and p12 > 0 else None,
            "meses_com_pagamento_12m": int((janela > 0).sum()), "meses_janela": int(len(janela)), "cv_12m": cv,
            "por_fonte": por_fonte, "por_fonte_pct": pf, "hhi_fontes": float((pf ** 2).sum()), "top_fonte": (pf.index[0], float(pf.iloc[0])),
            "por_tipo": por_tipo}


def projetar_repetindo_12m(eventos_12m: list[dict], hoje: date | None = None) -> pd.Series:
    """REFERÊNCIA, não promessa: repete, mês a mês, o que foi recebido nos últimos 12 meses (já com a quantidade ATUAL de cada
    ativo, se o chamador ajustou). Devolve R$ por mês dos próximos 12 meses."""
    hoje = hoje or date.today()
    base = {}
    for e in eventos_12m:
        d = g._data(e.get("data"))
        if d and _ok(e.get("valor")):
            base[d.month] = base.get(d.month, 0.0) + float(e["valor"])
    meses = pd.period_range(pd.Period(hoje, "M") + 1, periods=12, freq="M")
    return pd.Series([base.get(m.month, 0.0) for m in meses], index=meses)


def projetar_contratual(fluxos: list[dict], hoje: date | None = None, meses: int = 12) -> pd.Series:
    """Projeção SUPORTADA por contrato: fluxos futuros de renda fixa (cupons, juros, amortizações) — cada item {data, valor}."""
    hoje = hoje or date.today()
    idx = pd.period_range(pd.Period(hoje, "M") + 1, periods=meses, freq="M")
    out = pd.Series(0.0, index=idx)
    for f in fluxos:
        d = g._data(f.get("data"))
        if d and d > hoje and _ok(f.get("valor")) and pd.Period(d, "M") in out.index:
            out[pd.Period(d, "M")] += float(f["valor"])
    return out


# =============================================================================== cenários
PREMISSAS = {
    "beta": {"acao": 1.0, "bdr": 1.0, "etf": 1.0, "fii": 0.6, "fundo": 0.4, "cripto": 1.0},
    "juros_pct_por_pp": {"fii": -3.0, "acao": 0.0, "bdr": 0.0, "etf": 0.0, "fundo": 0.0, "cripto": 0.0},   # % de variação por +1 p.p.
    "duracao_padrao_rf": 3.0,
}

CENARIOS_PRONTOS = {
    "Bolsa em queda forte": {"bolsa_br": -30.0, "bolsa_ext": -25.0, "cripto": -50.0},
    "Juros sobem 3 p.p.": {"juros_pp": 3.0},
    "Juros caem 3 p.p.": {"juros_pp": -3.0},
    "Inflação surpreende (+3 p.p.)": {"inflacao_pp": 3.0},
    "Dólar sobe 20%": {"usd": 20.0},
    "Dólar cai 15%": {"usd": -15.0},
    "Estresse geral": {"bolsa_br": -25.0, "bolsa_ext": -20.0, "cripto": -45.0, "juros_pp": 2.0, "inflacao_pp": 2.0, "usd": 15.0},
}


def impacto_posicao(p: dict, ch: dict, prem: dict | None = None) -> dict:
    """Variação estimada (em %) de uma posição para os choques `ch` (bolsa_br, bolsa_ext, cripto, juros_pp, inflacao_pp, usd — em
    %, exceto juros_pp e inflacao_pp, em pontos percentuais). Usa betas e sensibilidades de PREMISSAS (editáveis) ou o beta
    histórico da própria posição quando informado em p['beta']. Devolve {pct, partes, premissa}."""
    pr = {**PREMISSAS, **(prem or {})}
    c = p.get("classe", "outro")
    bolsa_br, bolsa_ext, cr_, jp = ch.get("bolsa_br", 0.0), ch.get("bolsa_ext", 0.0), ch.get("cripto", 0.0), ch.get("juros_pp", 0.0)
    infl, usd = ch.get("inflacao_pp", 0.0), ch.get("usd", 0.0)
    exterior = p.get("moeda", "BRL") != "BRL"
    partes: dict[str, float] = {}
    usa_beta_hist = _ok(p.get("beta")) and c in ("acao", "etf", "bdr", "fundo")
    if c == "renda_fixa":
        ind = p.get("indexador", "")
        dur = p.get("duracao") if _ok(p.get("duracao")) else pr["duracao_padrao_rf"]
        if ind in ("pre", "ipca"):
            partes["juros (marcação a mercado)"] = -dur * jp
        if ind == "ipca":
            partes["inflação (correção do ano)"] = infl
        premissa = "duração do título" if _ok(p.get("duracao")) else f"duração padrão de {pr['duracao_padrao_rf']:g} anos (título sem duração calculada)"
        return {"pct": sum(partes.values()), "partes": partes, "premissa": premissa}
    if c == "caixa":
        return {"pct": 0.0, "partes": {}, "premissa": "caixa sem variação de preço"}
    if c == "cripto":
        local = cr_
        partes["mercado cripto"] = local
        total = (1 + local / 100) * (1 + usd / 100) - 1
        partes["dólar"] = total * 100 - local
        return {"pct": total * 100, "partes": partes, "premissa": "cripto cotada em dólar: mercado cripto × câmbio"}
    base_beta = p["beta"] if usa_beta_hist else pr["beta"].get(c, 1.0)
    mercado = bolsa_ext if (exterior or c == "bdr") else bolsa_br
    local = base_beta * mercado + pr["juros_pct_por_pp"].get(c, 0.0) * jp
    partes["mercado"] = base_beta * mercado
    if pr["juros_pct_por_pp"].get(c, 0.0) and jp:
        partes["juros"] = pr["juros_pct_por_pp"][c] * jp
    if exterior or c == "bdr":
        total = (1 + local / 100) * (1 + usd / 100) - 1
        partes["dólar"] = total * 100 - local
        local = total * 100
    prem_txt = (f"beta histórico {p['beta']:.2f}" if usa_beta_hist else f"beta assumido {pr['beta'].get(c, 1.0):g} para {g.CLASSES.get(c, c)}")
    return {"pct": local, "partes": partes, "premissa": prem_txt}


def simular_cenario(posicoes: list[dict], ch: dict, prem: dict | None = None) -> dict:
    """Aplica os choques a todas as posições e soma: patrimônio depois, variação em R$ e %, por classe e por posição."""
    linhas, por_classe = [], {}
    tot0 = 0.0
    for p in posicoes:
        v = p.get("valor")
        if not _ok(v) or v <= 0:
            continue
        i = impacto_posicao(p, ch, prem)
        delta = v * i["pct"] / 100
        tot0 += v
        linhas.append({"id": p["id"], "classe": p.get("classe"), "valor": v, "pct": i["pct"], "delta": delta, "premissa": i["premissa"]})
        por_classe[p.get("classe")] = por_classe.get(p.get("classe"), 0.0) + delta
    dt = sum(l["delta"] for l in linhas)
    depois = [{**l, "valor_depois": l["valor"] + l["delta"]} for l in linhas]
    pesos_depois = {l["id"]: l["valor_depois"] / (tot0 + dt) for l in depois} if tot0 + dt > 0 else {}
    return {"antes": tot0, "depois": tot0 + dt, "delta": dt, "pct": dt / tot0 * 100 if tot0 > 0 else 0.0, "posicoes": sorted(linhas, key=lambda x: x["delta"]),
            "por_classe": por_classe, "pesos_depois": pesos_depois, "choques": ch}


def vol_com_correlacao(pesos: pd.Series, vols: pd.Series, corr: pd.DataFrame, k: float) -> float | None:
    """Volatilidade da carteira quando as correlações são empurradas para 1: R' = (1−k)·R + k·1, com k de 0 (histórico) a 1 (todos
    se movem juntos, sem diversificação). Mostra quanto da proteção depende de a correlação do passado se manter."""
    cols = [c for c in pesos.index if c in corr.columns and c in vols.index]
    if len(cols) < 2:
        return None
    w = pesos[cols].values / pesos[cols].sum()
    s = vols[cols].values
    R = (1 - k) * corr.loc[cols, cols].values + k * np.ones((len(cols), len(cols)))
    cov = np.outer(s, s) * R
    return float(math.sqrt(max(w @ cov @ w, 0.0)))


def piores_periodos(r: pd.Series) -> dict:
    """Pior dia, pior mês e pior ano do histórico da carteira (com pesos atuais)."""
    if r is None or len(r) < 20:
        return {}
    m = g.retorno_por_periodo(r, "M")
    a = g.retorno_por_periodo(r, "Y")
    out = {"pior_dia": (r.idxmin().date(), float(r.min()))}
    if len(m):
        out["pior_mes"] = (str(m.idxmin()), float(m.min()))
    if len(a) >= 1:
        out["pior_ano"] = (str(a.idxmin()), float(a.min()))
    return out


def simular_fluxo(valores: dict[str, float], aporte: float = 0.0, retirada: float = 0.0, alvos: dict[str, float] | None = None,
                  retirar_de: str | None = None) -> dict:
    """Efeito de um aporte e/ou uma retirada na distribuição por classe. Aporte: vai para `alvos` (ou proporcional ao atual).
    Retirada: sai de `retirar_de` (uma classe) ou, sem isso, proporcionalmente. Retirada maior que o patrimônio é recusada."""
    tot = sum(valores.values())
    if retirada > tot + 1e-9:
        return {"ok": False, "motivo": "a retirada é maior que o patrimônio"}
    if retirar_de and valores.get(retirar_de, 0.0) < retirada - 1e-9:
        return {"ok": False, "motivo": f"{retirar_de} tem menos que o valor da retirada"}
    novo = dict(valores)
    if retirada > 0:
        if retirar_de:
            novo[retirar_de] -= retirada
        else:
            for c in novo:
                novo[c] -= retirada * valores[c] / tot
    if aporte > 0:
        if alvos and abs(sum(alvos.values()) - 100) < 0.01:
            r = rebalancear_com_aporte(novo, alvos, aporte)
            for c, x in r.get("comprar", {}).items():
                novo[c] = novo.get(c, 0.0) + x
        else:
            base = sum(novo.values())
            for c in list(novo):
                novo[c] += aporte * (novo[c] / base if base > 0 else 1 / len(novo))
    t2 = sum(novo.values())
    return {"ok": True, "antes": valores, "depois": novo, "total_antes": tot, "total_depois": t2,
            "pct_antes": {c: v / tot * 100 if tot else 0 for c, v in valores.items()}, "pct_depois": {c: v / t2 * 100 if t2 else 0 for c, v in novo.items()}}


# =============================================================================== relatório
def diagnostico(ctx: dict) -> dict:
    """Relatório automático. Cada frase traz o número que a justifica (ctx vem de gestao_app). Seções: resumo, pontos_fortes,
    fragilidades, concentracoes, riscos, diversificacao, evolucao, consistencia, classes, melhorias, atencao. Níveis: ok, atencao, info.
    Não é recomendação de investimento: aponta o que os dados mostram."""
    R = {k: [] for k in ("pontos_fortes", "fragilidades", "concentracoes", "riscos", "diversificacao", "evolucao", "consistencia",
                         "classes", "melhorias", "atencao")}

    def add(sec, nivel, texto):
        R[sec].append({"nivel": nivel, "texto": texto})
    pct = lambda x, d=1: f"{x * 100:.{d}f}%".replace(".", ",")      # noqa: E731
    pat = ctx.get("patrimonio", 0.0)
    c = ctx.get("conc") or {}
    if c.get("ok"):
        if c["n_efetivo"] >= 8 and c["top1"] <= 0.15:
            add("pontos_fortes", "ok", f"Posições bem distribuídas: ≈ {c['n_efetivo']:.0f} ativos efetivos e maior posição com {pct(c['top1'], 0)}.")
        elif c["top1"] > 0.30 or c["n_efetivo"] < 3:
            add("fragilidades", "atencao", f"Carteira concentrada: apenas ≈ {c['n_efetivo']:.1f} ativos efetivos e a maior posição pesa {pct(c['top1'], 0)}.")
    for a in ctx.get("alertas_conc") or []:
        add("concentracoes", "atencao", a["texto"])
    if not R["concentracoes"] and c.get("ok"):
        add("concentracoes", "ok", "Nenhum limite de concentração (ativo, setor, classe, emissor, país, moeda) foi ultrapassado.")
    k = ctx.get("risco") or {}
    if k.get("vol") is not None:
        add("riscos", "info", f"Volatilidade histórica de {pct(k['vol'])} ao ano (carteira atual sobre {k.get('dias', '?')} dias, cobrindo {pct(k.get('cobertura', 0), 0)} do patrimônio).")
        if k["vol"] > 0.25:
            add("fragilidades", "atencao", f"Volatilidade alta ({pct(k['vol'])} ao ano): oscilações fortes são esperadas.")
        elif k["vol"] < 0.12:
            add("pontos_fortes", "ok", f"Volatilidade baixa ({pct(k['vol'])} ao ano) no histórico.")
    if k.get("mdd") is not None:
        add("riscos", "atencao" if k["mdd"] < -0.25 else "info", f"Maior queda histórica (pico ao vale): {pct(k['mdd'])}. Quedas futuras podem ser maiores.")
    if k.get("var95") is not None:
        add("riscos", "info", f"VaR histórico de 95% em 1 dia: {pct(k['var95'], 2)} — em 5% dos dias do passado a perda foi maior que isso"
                               + (f" (CVaR: perda média de {pct(k['cvar95'], 2)} nesses dias)." if k.get("cvar95") is not None else "."))
    if k.get("sharpe") is not None:
        add("riscos", "ok" if k["sharpe"] >= 1 else "info", f"Sharpe de {_br(k['sharpe'], 2)} sobre o CDI: retorno por unidade de risco no período.")
        if k["sharpe"] >= 1:
            add("pontos_fortes", "ok", "Boa relação retorno/risco no período (Sharpe ≥ 1), mas é histórico.")
        elif k["sharpe"] < 0:
            add("fragilidades", "atencao", "O retorno no período ficou abaixo do CDI para o risco assumido (Sharpe negativo).")
    if ctx.get("exposicao_cambial", 0) > 0.3:
        add("riscos", "atencao", f"{pct(ctx['exposicao_cambial'], 0)} do patrimônio varia com o dólar.")
    if ctx.get("liquidez_baixa_pct", 0) > 0.3:
        add("riscos", "atencao", f"{pct(ctx['liquidez_baixa_pct'], 0)} do patrimônio leva mais de 30 dias para virar dinheiro (renda fixa com carência/vencimento).")
    if ctx.get("credito_privado_pct", 0) > 0.3:
        add("riscos", "atencao", f"{pct(ctx['credito_privado_pct'], 0)} do patrimônio está em crédito privado (sem garantia soberana).")
    d = ctx.get("diversificacao") or {}
    if d.get("enb") is not None and d.get("n_ativos"):
        add("diversificacao", "info", f"Número efetivo de apostas independentes: {_br(d['enb'], 1)} (de {d['n_ativos']} ativos com histórico).")
        if d["enb"] < max(2.0, d["n_ativos"] * 0.4):
            add("fragilidades", "atencao", f"A diversificação é menor do que parece: {d['n_ativos']} ativos, mas só ≈ {_br(d['enb'], 1)} apostas independentes.")
    if d.get("corr_media") is not None:
        add("diversificacao", "atencao" if d["corr_media"] > 0.6 else "info", f"Correlação média entre os ativos: {_br(d['corr_media'], 2)}.")
    for a, b, v in (d.get("pares") or [])[:3]:
        add("diversificacao", "atencao", f"{a} e {b} andam muito juntos (correlação {_br(v, 2)}): contam como quase a mesma aposta.")
    if d.get("fator_dominante"):
        f, p = d["fator_dominante"]
        if p > 0.6:
            add("diversificacao", "atencao", f"{pct(p, 0)} da carteira depende de um mesmo fator: {f}.")
    for s in d.get("indiretas") or []:
        add("diversificacao", "atencao", s)
    dsp = ctx.get("desempenho") or {}
    if dsp.get("twr") is not None:
        t = f"Retorno ponderado pelo tempo (TWR): {pct(dsp['twr'])} no período"
        if dsp.get("xirr") is not None:
            t += f"; retorno ponderado pelo dinheiro (XIRR): {pct(dsp['xirr'])} ao ano"
        add("evolucao", "info", t + ".")
        if dsp.get("bench_nome") and dsp.get("bench") is not None:
            dif = dsp["twr"] - dsp["bench"]
            add("evolucao", "ok" if dif >= 0 else "atencao", f"{'Acima' if dif >= 0 else 'Abaixo'} do {dsp['bench_nome']} em {_br(abs(dif) * 100, 1)} p.p. no mesmo período (o {dsp['bench_nome']} fez {pct(dsp['bench'])}).")
            if dif >= 0:
                add("pontos_fortes", "ok", f"Desempenho acima do {dsp['bench_nome']} no período.")
            else:
                add("fragilidades", "atencao", f"Desempenho abaixo do {dsp['bench_nome']} no período.")
    if pat > 0 and ctx.get("resultado") is not None:
        add("evolucao", "info", f"Resultado acumulado das posições: {'+' if ctx['resultado'] >= 0 else '−'}R$ {_br(abs(ctx['resultado']))} sobre o valor investido.")
    cs = ctx.get("consistencia") or {}
    if cs.get("ok"):
        add("consistencia", "ok" if cs["pct_positivos"] >= 0.6 else "info", f"{pct(cs['pct_positivos'], 0)} dos {cs['meses']} meses tiveram retorno positivo (melhor {pct(cs['melhor'])}, pior {pct(cs['pior'])}).")
        if cs.get("pct_acima_bench") is not None:
            add("consistencia", "info", f"Em {pct(cs['pct_acima_bench'], 0)} dos {cs['meses_bench']} meses a carteira superou o benchmark.")
    for cl, r in (ctx.get("retorno_por_classe") or {}).items():
        add("classes", "ok" if r >= 0 else "atencao", f"{g.CLASSES.get(cl, cl)}: {pct(r)} sobre o custo (só preço, sem proventos).")
    ref = ctx.get("renda_passiva") or {}
    if ref.get("ok"):
        add("evolucao", "info", f"Renda passiva dos últimos 12 meses: R$ {_br(ref['ultimos_12m'])} (média mensal R$ {_br(ref['media_mensal_12m'])}).")
        if ref.get("meses_com_pagamento_12m", 0) >= 10:
            add("pontos_fortes", "ok", f"Renda recorrente: recebimentos em {ref['meses_com_pagamento_12m']} dos últimos 12 meses.")
    for dv in ctx.get("desvios") or []:
        if dv["status"] != "dentro":
            add("melhorias", "atencao", f"{g.CLASSES.get(dv['classe'], dv['classe'])} está {dv['status']} do alvo: {_br(dv['atual'], 1)}% contra {_br(dv['alvo'], 1)}% (tolerância ±{_br(dv['tolerancia'], 0)} p.p.).")
    if ctx.get("desvios") is not None and not any(x["status"] != "dentro" for x in ctx["desvios"]):
        add("melhorias", "ok", "Alocação dentro das tolerâncias do alvo definido.")
    if ctx.get("desvios") is None:
        add("melhorias", "info", "Defina percentuais-alvo por classe (aba Alocação) para receber sugestões de rebalanceamento.")
    for a in R["concentracoes"]:
        if a["nivel"] == "atencao":
            add("melhorias", "info", "Para reduzir uma concentração, direcione os próximos aportes para classes/ativos abaixo do alvo antes de pensar em vender (evita imposto).")
            break
    for q in ctx.get("qualidade") or []:
        add("melhorias", "atencao", "Dados: " + q)
    for p in ctx.get("ativos") or []:
        mot = []
        if _ok(p.get("peso")) and p["peso"] > 0.20:
            mot.append(f"pesa {pct(p['peso'], 0)} da carteira")
        if _ok(p.get("ret12m")) and p["ret12m"] < -0.20:
            mot.append(f"caiu {pct(abs(p['ret12m']), 0)} em 12 meses")
        if _ok(p.get("dd_atual")) and p["dd_atual"] < -0.30:
            mot.append(f"está {pct(abs(p['dd_atual']), 0)} abaixo do pico")
        if p.get("sem_cotacao"):
            mot.append("está sem cotação atual")
        if mot:
            add("atencao", "atencao", f"{p['id']}: " + ", ".join(mot) + ".")
    ok = [x for sec in ("fragilidades", "concentracoes", "riscos", "diversificacao") for x in R[sec] if x["nivel"] == "atencao"]
    n = len(ok)
    R["resumo"] = ("Carteira sem pontos de atenção relevantes nos critérios usados." if n == 0 else
                   f"{n} ponto(s) de atenção nos critérios usados (concentração, risco e diversificação). Veja os detalhes abaixo.")
    R["n_atencao"] = n
    return R
