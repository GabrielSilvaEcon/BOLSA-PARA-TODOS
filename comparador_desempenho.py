"""
Passo 20 · Motor de DESEMPENHO e RISCO do comparador universal (sem Streamlit e sem rede; recebe séries já coletadas).

Reaproveita, sem duplicar: gestao.py (volatilidade, drawdown, Sharpe, Sortino, beta, VaR/CVaR, correlação, consistência, concentração),
risco.py (dias úteis para todas as classes, Calmar), relatorios.py (retorno real por Fisher, formatação, documento de exportação) e
comparador.py (Pontuacao, _pontuar, escala).

Regras
 · Cada série é um PREÇO (ou índice) diário na moeda do ativo. Com `retorno_total` os proventos entram reinvestidos no dia ex.
 · Moedas diferentes só são comparadas depois de convertidas, informando a taxa e a data usadas (`converter`).
 · Períodos diferentes não são comparados direto: `periodo_comum` recorta todos na mesma janela (ou exclui quem não cobre o período).
 · Dado insuficiente = None com o motivo; nada é estimado para "preencher". Passado não garante futuro.
 · A nota "perfil histórico" é COMPLEMENTAR e usa âncoras por classe; ela nunca ranqueia classes entre si.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

import comparador as cmp
import gestao as g
import relatorios as R
import risco as rk

AVISO = ("Comparação informativa feita com os dados disponíveis na data indicada. Rentabilidade passada não garante rentabilidade futura. "
         "Notas e destaques não são recomendação de investimento.")
TOLERANCIA_DIAS = 5
MIN_PONTOS = 20
JANELAS = {"1 dia": ("d", 1), "1 semana": ("d", 7), "1 mês": ("m", 1), "3 meses": ("m", 3), "6 meses": ("m", 6), "No ano": ("ytd", 0),
           "12 meses": ("m", 12), "3 anos": ("m", 36), "5 anos": ("m", 60)}
PRESETS = {"1 mês": ("m", 1), "3 meses": ("m", 3), "6 meses": ("m", 6), "No ano": ("ytd", 0), "12 meses": ("m", 12), "3 anos": ("m", 36),
           "5 anos": ("m", 60), "Máximo disponível": ("max", 0)}


def _ok(x) -> bool:
    return R._ok(x)


# =============================================================================== séries
def limpar(s) -> pd.Series:
    """Série diária limpa: números, índice sem fuso e sem horas, sem duplicatas, ordenada, só valores positivos."""
    if s is None or len(s) == 0:
        return pd.Series(dtype=float)
    s = pd.Series(s)
    x = pd.Series(pd.to_numeric(s.values, errors="coerce"), index=pd.DatetimeIndex(s.index))
    if x.index.tz is not None:
        x.index = x.index.tz_localize(None)
    x.index = x.index.normalize()
    x = x[~x.index.duplicated(keep="last")].sort_index().dropna()
    return x[x > 0]


def retorno_total(preco: pd.Series, proventos: pd.Series | None) -> tuple[pd.Series, dict]:
    """Índice de RETORNO TOTAL: cada provento (valor por cota, indexado pela data ex) é reinvestido no mesmo dia pelo preço de fechamento.
    Devolve (índice, info). Sem proventos, o índice é o próprio preço. Proventos fora do intervalo do preço são ignorados."""
    p = limpar(preco)
    info = {"proventos": 0, "reinvestidos": 0.0}
    if len(p) < 2 or proventos is None or len(proventos) == 0:
        return p, info
    d = pd.Series(pd.to_numeric(pd.Series(proventos).values, errors="coerce"), index=pd.DatetimeIndex(pd.Series(proventos).index))
    if d.index.tz is not None:
        d.index = d.index.tz_localize(None)
    d.index = d.index.normalize()
    d = d[(d > 0) & d.notna()].groupby(level=0).sum()
    d = d[(d.index > p.index[0]) & (d.index <= p.index[-1])]
    if d.empty:
        return p, info
    ant = p.shift(1)
    fator = pd.Series(1.0, index=p.index)
    for dt, v in d.items():
        pos = p.index.searchsorted(dt)             # primeiro pregão em ou depois da data ex
        if pos <= 0 or pos >= len(p):
            continue
        dia = p.index[pos]
        fator[dia] *= (p.iloc[pos] + v) / p.iloc[pos]
        info["proventos"] += 1
        info["reinvestidos"] += float(v)
    r = (p / ant) * fator - 1.0
    r.iloc[0] = 0.0
    return float(p.iloc[0]) * (1 + r).cumprod(), info


def converter(s: pd.Series, fx: pd.Series | None, de: str, para: str) -> tuple[pd.Series, dict]:
    """Converte uma série de preços entre BRL e USD pela taxa do dia (`fx` = reais por dólar, ex.: PTAX do BCB).
    Devolve (série, info) com a taxa e a data da primeira e da última conversão. Sem câmbio, devolve série vazia e o motivo."""
    de, para = str(de or "").upper(), str(para or "").upper()
    x = limpar(s)
    if de == para or not de or not para:
        return x, {"convertido": False}
    if {de, para} != {"BRL", "USD"}:
        return pd.Series(dtype=float), {"convertido": False, "erro": f"conversão {de}→{para} não disponível (só BRL e USD)"}
    f = limpar(fx)
    if f.empty:
        return pd.Series(dtype=float), {"convertido": False, "erro": "sem série de câmbio para converter"}
    f = f.reindex(f.index.union(x.index)).ffill().reindex(x.index)
    y = (x * f) if (de == "USD" and para == "BRL") else (x / f)
    y = y.dropna()
    if y.empty:
        return y, {"convertido": False, "erro": "o câmbio não cobre o período da série"}
    return y, {"convertido": True, "par": "USD/BRL", "de": de, "para": para, "taxa_inicio": float(f[y.index[0]]), "data_inicio": y.index[0].date().isoformat(),
               "taxa_fim": float(f[y.index[-1]]), "data_fim": y.index[-1].date().isoformat(),
               "fonte": "Banco Central (PTAX, venda)"}


def valor_em(s: pd.Series, d, tol: int = TOLERANCIA_DIAS) -> float | None:
    """Último valor em ou antes de `d`. Se `d` for anterior ao início da série por até `tol` dias, usa o primeiro valor; senão None."""
    if s is None or len(s) == 0:
        return None
    d = pd.Timestamp(d).normalize()
    if d < s.index[0]:
        return float(s.iloc[0]) if (s.index[0] - d).days <= tol else None
    return float(s.loc[:d].iloc[-1])


def ret_entre(s: pd.Series, ini, fim, tol: int = TOLERANCIA_DIAS) -> float | None:
    """Retorno simples entre as datas; None se a série não cobre o início (ou o fim) do período."""
    if s is None or len(s) < 2 or ini is None or fim is None:
        return None
    ini, fim = pd.Timestamp(ini).normalize(), pd.Timestamp(fim).normalize()
    if fim <= ini or fim > s.index[-1] + pd.Timedelta(days=tol):
        return None
    a, b = valor_em(s, ini, tol), valor_em(s, fim, tol)
    return b / a - 1.0 if a and b and a > 0 else None


def anualizar(ret: float | None, dias: float | None) -> float | None:
    """Taxa anual equivalente, só para períodos de pelo menos 1 ano (abaixo disso extrapolaria demais)."""
    if not _ok(ret) or not dias or dias < 365 or ret <= -1:
        return None
    return float((1 + ret) ** (365.25 / dias) - 1)


def inicio_janela(rotulo: str, fim, menor_data=None):
    """Data de início da janela `rotulo` (de PRESETS ou JANELAS) terminando em `fim`. 'Máximo disponível' = `menor_data`."""
    tipo, n = {**JANELAS, **PRESETS}[rotulo]
    fim = pd.Timestamp(fim).normalize()
    if tipo == "d":
        return fim - pd.Timedelta(days=n)
    if tipo == "m":
        return fim - pd.DateOffset(months=n)
    if tipo == "ytd":
        return pd.Timestamp(year=fim.year - 1, month=12, day=31)
    return pd.Timestamp(menor_data) if menor_data is not None else None


def periodo_comum(series: dict[str, pd.Series], ini=None, fim=None, modo: str = "comum", tol: int = TOLERANCIA_DIAS) -> dict:
    """Janela única para todos. modo='comum': recorta no começo mais tardio e no fim mais cedo (e respeita `ini`/`fim` se dados).
    modo='estrito': usa exatamente [ini, fim] e EXCLUI quem não cobre o início. Devolve {ok, ini, fim, validos, excluidos[(chave, motivo)]}."""
    limpas = {k: limpar(v) for k, v in series.items()}
    excl = [(k, "sem dados") for k, v in limpas.items() if len(v) < 2]
    uteis = {k: v for k, v in limpas.items() if len(v) >= 2}
    if not uteis:
        return {"ok": False, "motivo": "nenhuma série com dados", "validos": [], "excluidos": excl}
    fim_c = min(v.index[-1] for v in uteis.values())
    if fim is not None:
        fim_c = min(fim_c, pd.Timestamp(fim).normalize())
    if modo == "estrito" and ini is not None:
        ini_c = pd.Timestamp(ini).normalize()
        for k, v in list(uteis.items()):
            if v.index[0] > ini_c + pd.Timedelta(days=tol):
                excl.append((k, f"histórico começa em {v.index[0]:%d/%m/%Y}, depois do início do período"))
                del uteis[k]
        if not uteis:
            return {"ok": False, "motivo": "nenhum ativo cobre o período escolhido", "validos": [], "excluidos": excl}
    else:
        ini_c = max(v.index[0] for v in uteis.values())
        if ini is not None:
            ini_c = max(ini_c, pd.Timestamp(ini).normalize())
    if (fim_c - ini_c).days < 7:
        return {"ok": False, "motivo": "o período em comum tem menos de 7 dias", "validos": list(uteis), "excluidos": excl, "ini": ini_c, "fim": fim_c}
    validos = []
    for k, v in uteis.items():
        n = int(((v.index >= ini_c) & (v.index <= fim_c)).sum())
        if n < 5:
            excl.append((k, f"só {n} pontos no período"))
        else:
            validos.append(k)
    if len(validos) < 1:
        return {"ok": False, "motivo": "nenhuma série tem pontos suficientes no período", "validos": [], "excluidos": excl, "ini": ini_c, "fim": fim_c}
    return {"ok": True, "ini": ini_c, "fim": fim_c, "validos": validos, "excluidos": excl, "modo": modo,
            "dias": int((fim_c - ini_c).days), "limitado_por": min(uteis, key=lambda k: uteis[k].index[-1]) if modo == "comum" else None}


def base100(series: dict[str, pd.Series], ini, fim) -> pd.DataFrame:
    """Evolução de R$/US$ 100 aplicados em `ini` (valor do último pregão em ou antes de `ini`). Dias sem negociação repetem o último valor
    (no máximo 5 dias seguidos), para ativos de calendários diferentes ficarem no mesmo eixo."""
    ini, fim = pd.Timestamp(ini).normalize(), pd.Timestamp(fim).normalize()
    cols = {}
    for k, v in series.items():
        x = limpar(v)
        a = valor_em(x, ini)
        if len(x) < 2 or a is None:
            continue
        j = x[(x.index >= ini) & (x.index <= fim)]
        if j.empty:
            continue
        base = pd.concat([pd.Series([a], index=[ini]), j[j.index > ini]]) if j.index[0] > ini else j
        cols[k] = base / a * 100.0
    if not cols:
        return pd.DataFrame()
    df = pd.concat(cols, axis=1).sort_index()
    return df.ffill(limit=5)


# =============================================================================== rentabilidade
def tabela_retornos(series: dict[str, pd.Series], fim, ini_escolhido=None, ipca_idx: pd.Series | None = None, moeda: str = "BRL",
                    benchmarks: dict[str, pd.Series] | None = None) -> pd.DataFrame:
    """Uma linha por ativo/benchmark: retorno nominal em 1 dia, 1 semana, 1/3/6 meses, no ano, 12 meses, 3 e 5 anos (acumulado), mais o
    período escolhido, a taxa anual equivalente (≥ 1 ano) e, em reais, o retorno REAL (Fisher com o IPCA). Todos terminam em `fim`.
    Valores são frações (0,05 = 5%); janela que a série não cobre = NaN."""
    fim = pd.Timestamp(fim).normalize()
    linhas = []
    todas = [(k, v, "ativo") for k, v in series.items()] + [(k, v, "benchmark") for k, v in (benchmarks or {}).items()]
    for k, v, tipo in todas:
        x = limpar(v)
        row = {"Ativo": k, "Tipo": tipo}
        for rot in JANELAS:
            row[rot] = ret_entre(x, inicio_janela(rot, fim), fim) if len(x) > 1 else None
        esc = ret_entre(x, ini_escolhido, fim) if ini_escolhido is not None and len(x) > 1 else None
        row["Período escolhido"] = esc
        dias = (fim - pd.Timestamp(ini_escolhido).normalize()).days if ini_escolhido is not None else None
        row["Anualizado (a.a.)"] = anualizar(esc, dias)
        row["Retorno real"] = (R.retorno_real(esc, ipca_idx, pd.Timestamp(ini_escolhido), fim)
                               if moeda == "BRL" and esc is not None and ipca_idx is not None else None)
        linhas.append(row)
    df = pd.DataFrame(linhas)
    for c in df.columns:
        if c not in ("Ativo", "Tipo"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def retornos_calendario(s: pd.Series, freq: str = "M") -> pd.Series:
    """Retorno por mês ('M') ou ano ('Y') calendário (compostos dos retornos diários)."""
    x = limpar(s)
    if len(x) < 5:
        return pd.Series(dtype=float)
    return g.retorno_por_periodo(x.pct_change().dropna(), freq)


def tabela_calendario(series: dict[str, pd.Series], freq: str = "Y") -> pd.DataFrame:
    """Períodos nas linhas e ativos nas colunas. O primeiro e o último período podem ser parciais (a série começa ou termina no meio)."""
    cols = {k: retornos_calendario(v, freq) for k, v in series.items()}
    cols = {k: v for k, v in cols.items() if len(v)}
    if not cols:
        return pd.DataFrame()
    df = pd.concat(cols, axis=1).sort_index()
    df.index = [str(i) for i in df.index]
    return df


def liquido_renda_fixa(ret_bruto: float | None, dias: int | None) -> dict:
    """Retorno líquido ESTIMADO de renda fixa pelo IR regressivo (sobre o ganho), supondo resgate no fim do período. Não inclui IOF, custódia nem
    come-cotas. Só se aplica a renda fixa; para as outras classes o líquido depende de regras que o app não tem como confirmar."""
    if not _ok(ret_bruto) or not dias or dias <= 0:
        return {"ok": False, "motivo": "sem retorno ou prazo"}
    import renda_fixa as rf
    aliq = rf.aliquota_ir(int(dias))
    liq = ret_bruto - aliq * max(ret_bruto, 0.0)
    return {"ok": True, "liquido": float(liq), "aliquota": float(aliq), "obs": "estimativa: IR regressivo sobre o ganho; sem IOF, custódia e come-cotas"}


def vs_benchmark(ret: float | None, bench: float | None) -> float | None:
    """Diferença em pontos percentuais (positiva = acima do benchmark)."""
    return (ret - bench) * 100.0 if _ok(ret) and _ok(bench) else None


# =============================================================================== risco
LIMITES_MIN = {"vol": 30, "sharpe": 60, "sortino": 60, "beta": 60, "var": 250, "cvar": 250, "calmar": 250}


def retornos_uteis(s: pd.Series) -> pd.Series:
    """Retornos diários em DIAS ÚTEIS (a mesma base do módulo de risco do app, para cripto e bolsa ficarem comparáveis)."""
    return rk.padronizar_dias_uteis(s).pct_change().dropna()


def metricas_risco(s: pd.Series, bench: pd.Series | None = None, rf: pd.Series | float | None = None) -> dict:
    """Indicadores de risco de UM ativo (série na moeda de comparação). Cada um fica None, com o motivo em `motivos`, quando faltam dados:
    nada é calculado com amostra curta. `bench`: série de preços do benchmark (beta e correlação); `rf`: retornos diários do CDI (ou número)."""
    r = retornos_uteis(s)
    out: dict = {"n_dias": int(len(r)), "motivos": {}}

    def pedir(chave, valor, minimo):
        if len(r) < minimo:
            out[chave] = None
            out["motivos"][chave] = f"precisa de {minimo} dias úteis; há {len(r)}"
        else:
            out[chave] = valor() if callable(valor) else valor
            if out[chave] is None:
                out["motivos"][chave] = "sem variação suficiente para calcular"
    pedir("vol_anual", lambda: g.vol_anual(r, 30), LIMITES_MIN["vol"])
    if len(r) >= 2:
        dd = g.drawdown((1 + r).cumprod())
        out["mdd"] = dd.get("maximo")
        out["dd_atual"] = dd.get("atual")
        out["dd_data_pico"] = dd.get("pico")
        out["dd_data_vale"] = dd.get("vale")
        out["dd_recuperado"] = dd.get("recuperacao") is not None
    else:
        out["mdd"] = out["dd_atual"] = None
    pedir("sharpe", lambda: g.sharpe(r, rf, 60), LIMITES_MIN["sharpe"])
    pedir("sortino", lambda: g.sortino(r, rf, 60), LIMITES_MIN["sortino"])
    pedir("var95", lambda: g.var_historico(r, 0.95, 1, 250), LIMITES_MIN["var"])
    pedir("cvar95", lambda: g.cvar_historico(r, 0.95, 1, 250), LIMITES_MIN["cvar"])
    pedir("calmar", lambda: rk.calmar(r, 250), LIMITES_MIN["calmar"])
    out["beta"] = out["correlacao_bench"] = None
    if bench is not None and len(bench) > 60:
        rb = retornos_uteis(bench)
        j = pd.concat([r, rb], axis=1, join="inner").dropna()
        if len(j) >= LIMITES_MIN["beta"]:
            out["beta"] = g.beta(j.iloc[:, 0], j.iloc[:, 1], 60)
            out["correlacao_bench"] = float(j.corr().iloc[0, 1])
        else:
            out["motivos"]["beta"] = f"só {len(j)} dias em comum com o benchmark (mínimo 60)"
    else:
        out["motivos"]["beta"] = "sem benchmark com histórico suficiente"
    return out


def tabela_risco(series: dict[str, pd.Series], bench: pd.Series | None, rf=None, ini=None, fim=None) -> tuple[pd.DataFrame, dict]:
    """Tabela de risco (uma linha por ativo) e o dicionário de métricas completo. Recorta todos no mesmo período antes de calcular."""
    linhas, dets = [], {}
    for k, s in series.items():
        x = limpar(s)
        if ini is not None:
            x = x[x.index >= pd.Timestamp(ini)]
        if fim is not None:
            x = x[x.index <= pd.Timestamp(fim)]
        m = metricas_risco(x, bench, rf)
        dets[k] = m
        linhas.append({"Ativo": k, "Dias úteis": m["n_dias"], "Volatilidade anual": m["vol_anual"], "Queda máxima": m["mdd"], "Queda atual": m["dd_atual"],
                       "Sharpe": m["sharpe"], "Sortino": m["sortino"], "Beta": m["beta"], "VaR 95% (1 dia)": m["var95"], "CVaR 95% (1 dia)": m["cvar95"],
                       "Calmar": m["calmar"]})
    return pd.DataFrame(linhas), dets


def correlacoes(series: dict[str, pd.Series], ini=None, fim=None, minimo: int = 60) -> pd.DataFrame:
    """Matriz de correlação dos retornos diários (dias úteis) no período. Vazia se houver menos de `minimo` dias em comum."""
    cols = {}
    for k, s in series.items():
        x = rk.padronizar_dias_uteis(s)
        if ini is not None:
            x = x[x.index >= pd.Timestamp(ini)]
        if fim is not None:
            x = x[x.index <= pd.Timestamp(fim)]
        if len(x) > 2:
            cols[k] = x.pct_change()
    if len(cols) < 2:
        return pd.DataFrame()
    df = pd.concat(cols, axis=1, join="inner").dropna()
    return df.corr() if len(df) >= minimo else pd.DataFrame()


def consistencia(s: pd.Series, bench: pd.Series | None = None) -> dict:
    """% de meses positivos, melhor e pior mês e, com benchmark, % de meses acima dele (mínimo 6 meses)."""
    r = limpar(s).pct_change().dropna()
    b = limpar(bench).pct_change().dropna() if bench is not None and len(bench) > 5 else None
    return g.consistencia(r, b)


def diferencas_de_risco(metricas: dict[str, dict], classes: dict[str, str]) -> list[str]:
    """Frases que explicam, com os números do próprio ativo, de onde vem a diferença de risco entre os comparados."""
    L = []
    vol = {k: m["vol_anual"] for k, m in metricas.items() if _ok(m.get("vol_anual"))}
    if len(vol) >= 2:
        mx, mn = max(vol, key=vol.get), min(vol, key=vol.get)
        if mx != mn:
            razao = vol[mx] / vol[mn] if vol[mn] > 0 else None
            L.append(f"{mx} oscilou mais ({R.pct(vol[mx], 1)} ao ano) que {mn} ({R.pct(vol[mn], 1)})" + (f", cerca de {razao:.1f} vezes".replace(".", ",") if razao else "") + ".")
    dd = {k: m["mdd"] for k, m in metricas.items() if _ok(m.get("mdd"))}
    if len(dd) >= 2:
        pior, melhor = min(dd, key=dd.get), max(dd, key=dd.get)
        if pior != melhor:
            L.append(f"A maior queda do período foi de {pior} ({R.pct(dd[pior], 1)}); {melhor} caiu no máximo {R.pct(dd[melhor], 1)}.")
    for k, m in metricas.items():
        c = classes.get(k)
        if c == "cripto":
            L.append(f"{k} é cripto: negocia 24 horas, sem garantia e com risco de custódia e regulação; a volatilidade tende a ser bem maior que a de bolsa.")
        elif c == "fii":
            L.append(f"{k} é FII: o preço da cota varia com juros, vacância e (nos de papel) crédito dos devedores; o app não mede o risco de crédito dos CRIs.")
        elif c == "renda_fixa":
            L.append(f"{k} é renda fixa: o risco depende do emissor (crédito) e, antes do vencimento, da taxa de juros; o preço de mercado pode cair mesmo sendo 'fixa'.")
        elif c == "fundo":
            L.append(f"{k} é fundo: o risco vem da carteira do gestor, de taxas e das regras de resgate; o informe da CVM mostra a cota, não a composição.")
        elif c == "etf":
            L.append(f"{k} é ETF: acompanha um índice, então carrega o risco do índice (e do câmbio, se for do exterior).")
    return L


# =============================================================================== pontuação histórica (complementar)
ANCORAS = {  # (ruim, bom) para a volatilidade anual e a queda máxima, por classe: o que é 'muito' numa classe não é em outra
    "acao": {"vol": (0.55, 0.15), "mdd": (-0.50, -0.10)}, "etf": {"vol": (0.35, 0.08), "mdd": (-0.40, -0.08)},
    "fii": {"vol": (0.30, 0.08), "mdd": (-0.35, -0.08)}, "cripto": {"vol": (1.20, 0.40), "mdd": (-0.85, -0.30)},
    "fundo": {"vol": (0.20, 0.01), "mdd": (-0.30, -0.02)}, "renda_fixa": {"vol": (0.12, 0.01), "mdd": (-0.25, -0.02)},
}
PESOS_HISTORICO = {"Retorno ajustado ao risco": 30, "Volatilidade": 25, "Queda máxima": 25, "Consistência": 20}


def pontuar_historico(classe: str, m: dict, cons: dict | None = None) -> cmp.Pontuacao:
    """Nota 0–100 do PERFIL HISTÓRICO (complementar à nota da classe): retorno por unidade de risco (Sharpe), volatilidade, pior queda e consistência
    mensal, com âncoras da própria classe. Menos de 1 ano de dados deixa a nota provisória. Não ranqueia classes entre si."""
    a = ANCORAS.get(classe, ANCORAS["acao"])
    p = {"Retorno ajustado ao risco": cmp.escala(m.get("sharpe"), -0.5, 1.5), "Volatilidade": cmp.escala(m.get("vol_anual"), *a["vol"]),
         "Queda máxima": cmp.escala(m.get("mdd"), *a["mdd"]),
         "Consistência": cmp.escala((cons or {}).get("pct_positivos") if (cons or {}).get("ok") else None, 0.40, 0.75)}
    t = {"Retorno ajustado ao risco": f"Sharpe {m['sharpe']:.2f} (0 vale nota 25; 1,5 vale 100)." if _ok(m.get("sharpe")) else "",
         "Volatilidade": f"{R.pct(m.get('vol_anual'), 1)} ao ano; âncoras da classe: {R.pct(a['vol'][1], 0)} (100) a {R.pct(a['vol'][0], 0)} (0)." if _ok(m.get("vol_anual")) else "",
         "Queda máxima": f"{R.pct(m.get('mdd'), 1)}; âncoras da classe: {R.pct(a['mdd'][1], 0)} (100) a {R.pct(a['mdd'][0], 0)} (0)." if _ok(m.get("mdd")) else "",
         "Consistência": f"{R.pct((cons or {}).get('pct_positivos'), 0)} dos meses positivos (40% vale 0; 75% vale 100)." if (cons or {}).get("ok") else ""}
    pt = cmp._pontuar(p, PESOS_HISTORICO, t, "Perfil histórico (complementar): Sharpe, volatilidade, queda máxima e consistência mensal, com âncoras da classe.")
    if m.get("n_dias", 0) < 250 and pt.nota is not None:
        pt.provisoria = True
        pt.influencias.append(f"Histórico curto ({m.get('n_dias', 0)} dias úteis, menos de 1 ano): nota provisória.")
    return pt


PILARES_PEDIDOS = ["Fundamentos", "Rentabilidade", "Valuation", "Risco", "Liquidez", "Crescimento", "Consistência histórica", "Características da classe"]


# =============================================================================== liquidez e crescimento composto
# Réguas educacionais em R$ por dia (média de preço × volume, 90 dias): abaixo da primeira = Baixa; até a segunda = Média; acima = Alta.
FAIXAS_LIQUIDEZ = {"acao": (500_000, 5_000_000), "etf": (500_000, 5_000_000), "fii": (200_000, 3_000_000), "cripto": (5_000_000, 200_000_000)}


def liquidez(preco: pd.Series, volume, fim, em_moeda: bool = False, dias: int = 90, minimo: int = 10) -> dict:
    """Liquidez média diária dos últimos `dias` dias corridos: preço × volume (ou o volume direto, se já vier em dinheiro, como na cripto).
    Devolve {ok, media, pct_dias, n}. Sem volume ou com menos de `minimo` dias com dado: ok=False e o motivo (nunca inventa)."""
    if volume is None or len(volume) == 0 or preco is None or len(preco) == 0:
        return {"ok": False, "motivo": "a fonte não entregou o volume negociado"}
    fim = pd.Timestamp(fim).normalize()
    v = limpar_volume(volume)
    v = v[(v.index > fim - pd.Timedelta(days=dias)) & (v.index <= fim)]
    if len(v) < minimo:
        return {"ok": False, "motivo": f"só {len(v)} dias com volume nos últimos {dias} dias (mínimo {minimo})"}
    if em_moeda:
        fin = v
    else:
        p = preco.reindex(v.index).ffill()
        fin = (p * v).dropna()
    if len(fin) < minimo or fin.sum() <= 0:
        return {"ok": False, "motivo": "volume financeiro zerado ou sem preço correspondente"}
    return {"ok": True, "media": float(fin.mean()), "pct_dias": float((v > 0).mean()), "n": int(len(v))}


def limpar_volume(v) -> pd.Series:
    x = pd.Series(pd.to_numeric(pd.Series(v).values, errors="coerce"), index=pd.DatetimeIndex(pd.Series(v).index))
    if x.index.tz is not None:
        x.index = x.index.tz_localize(None)
    x.index = x.index.normalize()
    x = x[~x.index.duplicated(keep="last")].sort_index()
    return x[x >= 0].dropna()


def faixa_liquidez(classe: str, media_brl: float | None) -> str:
    cortes = FAIXAS_LIQUIDEZ.get(classe)
    if cortes is None or not _ok(media_brl):
        return "n/d"
    return "Baixa" if media_brl < cortes[0] else ("Média" if media_brl < cortes[1] else "Alta")


def cagr(s: pd.Series, fim, anos: int) -> float | None:
    """Crescimento composto anual do último `anos` (preço ou retorno total já na moeda de comparação). None se a série não cobre o período."""
    if s is None or len(s) < 2:
        return None
    fim = pd.Timestamp(fim).normalize()
    ini = fim - pd.DateOffset(years=anos)
    r = ret_entre(s, ini, fim)
    return None if r is None or r <= -1 else float((1 + r) ** (1 / anos) - 1)


def cobertura_de_pilares(ativo, tem_historico: bool, tem_consist: bool, tem_liquidez: bool = False, tem_cagr: bool = False) -> dict[str, str]:
    """Para cada um dos 8 pilares pedidos, de onde vem a informação do ativo: 'nota da classe', 'perfil histórico', 'tabela' ou 'sem dado'."""
    pil = (ativo.pontuacao.pilares if ativo.pontuacao else {}) or {}
    ind = ativo.ind or {}

    def tem(*ks):
        return any(ind.get(k) is not None and ind[k].valor is not None for k in ks)
    nomes = " ".join(pil.keys()).lower()
    out = {}
    out["Fundamentos"] = "nota da classe" if any(w in nomes for w in ("qualidade", "solidez", "fundament", "utilidade", "saúde", "token", "segur")) else (
        "tabela" if tem("roe", "margem_liq", "vacancia", "pl_total") else "sem dado")
    out["Rentabilidade"] = "perfil histórico" if tem_historico else ("nota da classe" if "retorno" in nomes or "renda" in nomes else ("tabela" if tem("ret12m") else "sem dado"))
    out["Valuation"] = "nota da classe" if any(w in nomes for w in ("valor", "valuation", "p/vp")) else ("tabela" if tem("pl", "pvp", "ev_ebitda", "mc_tvl") else "sem dado")
    out["Risco"] = "perfil histórico" if tem_historico else ("nota da classe" if "risco" in nomes else ("tabela" if tem("vol") else "sem dado"))
    out["Liquidez"] = "nota da classe" if "liquidez" in nomes else ("tabela" if tem_liquidez or tem("liquidez", "liq_media", "vol24", "liquidez_dias") else "sem dado")
    out["Crescimento"] = "tabela" if tem_cagr or any(k.startswith("cagr") or k.startswith("cresc") for k in ind) else "sem dado"
    out["Consistência histórica"] = "perfil histórico" if tem_consist else "sem dado"
    out["Características da classe"] = "nota da classe" if ativo.pontuacao else ("tabela" if ind else "sem dado")
    return out


# =============================================================================== carteiras
def carteira_de_pesos(series: dict[str, pd.Series], pesos: dict[str, float], minimo: int = 60) -> dict:
    """Série diária de uma carteira com pesos CONSTANTES (rebalanceada todo dia) a partir dos preços já na mesma moeda. Os pesos são renormalizados entre
    os ativos com histórico; `cobertura` diz que fração do peso original eles representam. Sem dado suficiente: ok=False."""
    pesos = {k: float(v) for k, v in pesos.items() if _ok(v) and float(v) > 0}
    if not pesos:
        return {"ok": False, "motivo": "sem pesos"}
    rets = g.matriz_retornos({k: rk.padronizar_dias_uteis(series[k]) for k in pesos if k in series and len(series[k]) > minimo}, minimo)
    if rets.empty:
        return {"ok": False, "motivo": f"menos de {minimo} dias de histórico em comum entre os ativos"}
    r, info = g.retornos_da_carteira(rets, pesos)
    if r.empty:
        return {"ok": False, "motivo": "nenhum ativo da carteira tem histórico"}
    sem = [k for k in pesos if k not in info["usados"]]
    return {"ok": True, "retornos": r, "indice": 100 * (1 + r).cumprod(), "cobertura": info["cobertura"], "usados": info["usados"], "sem_historico": sem,
            "inicio": r.index[0], "fim": r.index[-1], "dias": int(len(r))}


def exposicao(posicoes: dict[str, dict], campo: str) -> list[dict]:
    """Distribuição % por `campo` ('classe', 'moeda', 'pais'...) de {ativo: {'valor', campo}}."""
    return g.distribuicao([{"valor": v.get("valor"), campo: v.get(campo)} for v in posicoes.values()], campo)


def renda_passiva(posicoes: dict[str, dict], dy: dict[str, float | None]) -> dict:
    """Estimativa de renda dos próximos 12 meses = Σ valor × DY dos últimos 12 meses. É ESTIMATIVA baseada no passado, não promessa.
    Só entram ativos com DY conhecido; `cobertura` é a fração do valor com DY."""
    tot = sum(v["valor"] for v in posicoes.values() if _ok(v.get("valor")))
    if tot <= 0:
        return {"ok": False, "motivo": "carteira sem valor"}
    com = {k: v for k, v in posicoes.items() if _ok(dy.get(k)) and _ok(v.get("valor"))}
    if not com:
        return {"ok": False, "motivo": "nenhum ativo com histórico de proventos"}
    est = sum(v["valor"] * dy[k] for k, v in com.items())
    cob = sum(v["valor"] for v in com.values()) / tot
    return {"ok": True, "anual": float(est), "mensal": float(est / 12), "dy_carteira": float(est / tot), "cobertura": float(cob),
            "sem_dy": [k for k in posicoes if k not in com]}


def comparar_carteiras(cart: dict[str, dict], ini=None, fim=None, bench: pd.Series | None = None, rf=None, janela: str | None = None) -> dict:
    """Compara duas ou mais carteiras no MESMO período (o comum a todas, limitado por `janela`: um dos PRESETS). `cart[nome]` = {'series', 'pesos', 'posicoes': {ativo: {valor, classe, moeda}}, 'dy'}.
    Devolve tabela de métricas, evolução base 100, correlação entre as carteiras, exposição por classe e concentração; cada falta de dado vem em `avisos`."""
    out: dict = {"ok": False, "avisos": [], "carteiras": {}}
    calc = {}
    for nome, c in cart.items():
        r = carteira_de_pesos(c["series"], c["pesos"])
        if not r.get("ok"):
            out["avisos"].append(f"{nome}: {r['motivo']}.")
            continue
        if r["cobertura"] < 0.8:
            out["avisos"].append(f"{nome}: só {R.pct(r['cobertura'], 0)} do valor tem histórico; o resultado representa essa parte.")
        if r["sem_historico"]:
            out["avisos"].append(f"{nome}: sem histórico para {', '.join(r['sem_historico'])}.")
        calc[nome] = r
    if len(calc) < 1:
        return out
    ini_c = max(r["inicio"] for r in calc.values())
    fim_c = min(r["fim"] for r in calc.values())
    if fim is not None:
        fim_c = min(fim_c, pd.Timestamp(fim))
    if janela and janela in PRESETS and PRESETS[janela][0] != "max":
        ini = inicio_janela(janela, fim_c)
    if ini is not None:
        ini_c = max(ini_c, pd.Timestamp(ini))
    if (fim_c - ini_c).days < 30:
        out["avisos"].append("O período em comum entre as carteiras tem menos de 30 dias: não há base para comparar.")
        return out
    out.update({"ok": True, "ini": ini_c, "fim": fim_c, "dias": int((fim_c - ini_c).days)})
    linhas, idx, rets = [], {}, {}
    for nome, r in calc.items():
        x = r["retornos"][(r["retornos"].index >= ini_c) & (r["retornos"].index <= fim_c)]
        rets[nome] = x
        ind = 100 * (1 + x).cumprod()
        idx[nome] = ind
        total = float(ind.iloc[-1] / 100 - 1)
        met = metricas_risco(pd.concat([pd.Series([1.0], index=[x.index[0] - pd.Timedelta(days=1)]), (1 + x).cumprod()]), bench, rf)
        pos = cart[nome].get("posicoes") or {}
        conc = g.concentracao([v.get("valor") for v in pos.values()]) if pos else {"ok": False}
        rp = renda_passiva(pos, cart[nome].get("dy") or {}) if pos else {"ok": False}
        linhas.append({"Carteira": nome, "Ativos": len(r["usados"]), "Retorno no período": total, "Anualizado (a.a.)": anualizar(total, out["dias"]),
                       "Volatilidade anual": met["vol_anual"], "Queda máxima": met["mdd"], "Sharpe": met["sharpe"], "Sortino": met["sortino"],
                       "VaR 95% (1 dia)": met["var95"], "CVaR 95% (1 dia)": met["cvar95"], "Beta": met["beta"],
                       "Nº efetivo de ativos": conc.get("n_efetivo") if conc.get("ok") else None,
                       "Maior posição": conc.get("top1") if conc.get("ok") else None,
                       "Renda estimada (12m)": rp.get("anual") if rp.get("ok") else None,
                       "DY da carteira": rp.get("dy_carteira") if rp.get("ok") else None})
        out["carteiras"][nome] = {"risco": met, "concentracao": conc, "renda": rp, "cobertura": r["cobertura"], "dias": r["dias"],
                                  "classes": exposicao(pos, "classe") if pos else [], "moedas": exposicao(pos, "moeda") if pos else []}
    out["tabela"] = pd.DataFrame(linhas)
    out["evolucao"] = pd.DataFrame(idx)
    if len(rets) >= 2:
        j = pd.concat(rets, axis=1, join="inner").dropna()
        out["correlacao"] = j.corr() if len(j) >= 60 else pd.DataFrame()
    else:
        out["correlacao"] = pd.DataFrame()
    return out


# =============================================================================== exportação
def documento(titulo: str, periodo: str, itens: list[dict], tabelas: list[tuple[str, pd.DataFrame]], metodologia: list[str], fontes: list[str],
              avisos: list[str], moeda_info: str = "") -> dict:
    """Documento neutro para PDF, Excel e CSV do Passo 19 (relatorios.pdf_bytes / excel_bytes): identificação, período, tabelas (já em texto),
    metodologia, fontes e avisos. `itens`: [{'chave','nome','classe','fonte','data_ref'}]."""
    S = [{"titulo": "Ativos comparados", "tipo": "tabela", "dados": pd.DataFrame([{"Código": i["chave"], "Nome": i.get("nome", ""), "Classe": i.get("classe", ""),
                                                                               "Fonte": i.get("fonte", ""), "Dados até": i.get("data_ref") or "n/d"} for i in itens])}]
    for nome, df in tabelas:
        if df is not None and len(df):
            S.append({"titulo": nome, "tipo": "tabela", "dados": df})
    S.append({"titulo": "Metodologia", "tipo": "texto", "dados": list(metodologia) + ([f"Conversão de moeda: {moeda_info}"] if moeda_info else [])})
    doc = R.montar_relatorio(titulo, ", ".join(i["chave"] for i in itens), periodo, {}, S, fontes, avisos)
    doc["aviso_legal"] = AVISO
    return doc


def tabela_texto(df: pd.DataFrame, pct_cols=(), num_cols=(), pp_cols=(), moeda_cols=()) -> pd.DataFrame:
    """Converte para texto formatado em português (n/d para vazio). Usada na tela, no PDF, no Excel e no CSV."""
    out = df.copy()
    for c in pct_cols:
        if c in out:
            out[c] = out[c].map(lambda v: R.pct(v, 2, True))
    for c in num_cols:
        if c in out:
            out[c] = out[c].map(lambda v: "n/d" if not _ok(v) else f"{float(v):.2f}".replace(".", ","))
    for c in pp_cols:
        if c in out:
            out[c] = out[c].map(lambda v: "n/d" if not _ok(v) else f"{float(v):+.2f}".replace(".", ",") + " p.p.")
    for c in moeda_cols:
        if c in out:
            out[c] = out[c].map(R.brl)
    return out.fillna("n/d")
