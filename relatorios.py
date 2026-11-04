"""
Passo 19 · Relatórios inteligentes e dashboard executivo — motor de cálculo (sem Streamlit e sem rede).

Evolui o que já existe, sem duplicar: a carteira, o TWR/XIRR, as distribuições e a concentração vêm de gestao.py (Passo 12); os indicadores de cada
classe vêm das especificações do comparador.py (Passo 6), que já separa o que vale para ações, FIIs, cripto, ETFs, fundos e renda fixa.
Aqui ficam: filtros, resumo patrimonial, rentabilidade por período (TWR, MWR, benchmarks, retorno real), qualidade dos dados,
fotografias históricas (snapshots) e a montagem/exportação do relatório (CSV, Excel e PDF).

Regras: nada é preenchido com número inventado; o que não pode ser calculado volta com o MOTIVO; aporte nunca é tratado como rentabilidade.
"""
from __future__ import annotations

import io
import json
import math
from datetime import date, datetime

import numpy as np
import pandas as pd

import comparador as cmp
import gestao as g

VERSAO = 1
AVISO = ("Relatório informativo, calculado com os dados disponíveis no aplicativo na data indicada. Rentabilidade passada não garante rentabilidade futura. "
         "Não é recomendação de investimento.")
PERIODOS = {"1 mês": 1, "3 meses": 3, "6 meses": 6, "12 meses": 12, "No ano": "ytd", "Desde o início": None}
MIN_DIAS_MWR = 90
DIAS_DEFASAGEM = 7
MAX_FOTOS = 60
CAMPOS_FILTRO = ("classes", "setores", "paises", "moedas", "ativos", "instituicoes")


# =============================================================================== utilidades
def _ok(x) -> bool:
    try:
        return x is not None and math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


def _d(x) -> date | None:
    return g._data(x)


def brl(v) -> str:
    if not _ok(v):
        return "n/d"
    s = f"{abs(float(v)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 else "") + "R$ " + s


def pct(v, casas: int = 2, sinal: bool = False) -> str:
    if not _ok(v):
        return "n/d"
    s = f"{float(v) * 100:+.{casas}f}" if sinal else f"{float(v) * 100:.{casas}f}"
    return s.replace(".", ",") + "%"


# =============================================================================== filtros e resumo
def validas(posicoes: list[dict]) -> list[dict]:
    """Posições com valor atual positivo (as únicas que entram em totais e percentuais)."""
    return [p for p in posicoes or [] if _ok(p.get("valor")) and p["valor"] > 0]


def filtrar(posicoes: list[dict], classes=None, setores=None, paises=None, moedas=None, ativos=None, instituicoes=None) -> list[dict]:
    """Aplica os filtros do relatório. Lista vazia/None = sem filtro naquele campo. Instituição vem do campo 'instituicao'/'custodiante' quando cadastrado."""
    def pass_(p, campo, vals):
        return not vals or (p.get(campo) or "Não informado") in vals
    out = []
    for p in posicoes or []:
        inst = p.get("instituicao") or p.get("custodiante") or p.get("corretora") or "Não informado"
        if (pass_(p, "classe", classes) and pass_(p, "setor", setores) and pass_(p, "pais", paises) and pass_(p, "moeda", moedas)
                and (not ativos or p.get("id") in ativos) and (not instituicoes or inst in instituicoes)):
            out.append(p)
    return out


def resumo(posicoes: list[dict], eventos: list[dict] | None = None) -> dict:
    """Patrimônio, investido, ganho não realizado, resultado realizado e proventos da seleção. Posição sem custo informado fica FORA do ganho e é contada."""
    pv = validas(posicoes)
    patr = sum(p["valor"] for p in pv)
    com_custo = [p for p in pv if _ok(p.get("custo")) and p["custo"] > 0]
    inv = sum(p["custo"] for p in com_custo)
    val_cc = sum(p["valor"] for p in com_custo)
    ganho = val_cc - inv
    ids = {p["id"] for p in posicoes or []}
    prov = sum(e["valor"] for e in (eventos or []) if e.get("fonte") in ids and _ok(e.get("valor")) and e.get("efetivo", True))
    realizado = sum(p.get("realizado") or 0.0 for p in posicoes or [] if _ok(p.get("realizado")))
    return {"patrimonio": patr, "investido": inv if com_custo else None, "ganho": ganho if com_custo else None, "ganho_pct": (ganho / inv) if inv > 0 else None,
            "realizado": realizado, "proventos": prov, "resultado_total": (ganho + realizado + prov) if com_custo else None,
            "n_posicoes": len(pv), "sem_custo": [p["id"] for p in pv if p not in com_custo], "saldo": patr}


def distribuicao(posicoes: list[dict], campo: str) -> pd.DataFrame:
    d = g.distribuicao(validas(posicoes), campo)
    return pd.DataFrame(d, columns=["nome", "valor", "pct"]) if d else pd.DataFrame(columns=["nome", "valor", "pct"])


def tabela_posicoes(posicoes: list[dict]) -> pd.DataFrame:
    """Tabela principal: uma linha por posição, ordenada pelo valor, com peso e resultado em R$ e %."""
    pv = validas(posicoes)
    tot = sum(p["valor"] for p in pv)
    linhas = []
    for p in sorted(pv, key=lambda x: -x["valor"]):
        c = p.get("custo")
        gan = p["valor"] - c if _ok(c) and c > 0 else None
        linhas.append({"Ativo": p["id"], "Nome": p.get("nome") or p["id"], "Classe": g.CLASSES.get(p.get("classe"), p.get("classe")), "Setor": p.get("setor") or "Não informado",
                       "País": p.get("pais") or "Não informado", "Moeda": p.get("moeda") or "BRL", "Valor (R$)": p["valor"], "Peso": p["valor"] / tot if tot else None,
                       "Custo (R$)": c if _ok(c) else None, "Resultado (R$)": gan, "Resultado (%)": (gan / c) if gan is not None else None})
    return pd.DataFrame(linhas)


def ranking(posicoes: list[dict], n: int = 5) -> dict:
    """Melhores e piores posições pelo resultado sobre o custo. Só posições com custo informado."""
    base = [(p["id"], p["valor"] / p["custo"] - 1.0, p["valor"] - p["custo"]) for p in validas(posicoes) if _ok(p.get("custo")) and p["custo"] > 0]
    base.sort(key=lambda x: -x[1])
    return {"melhores": base[:n], "piores": [x for x in base[::-1][:n] if x[1] < 0] if base else [], "n_avaliadas": len(base)}


# =============================================================================== desempenho
def _indice_em(s: pd.Series, d: pd.Timestamp, antes: bool = True):
    """Valor da série na data (último pregão em ou antes dela); None se a série ainda não existia."""
    s = s.dropna()
    if s.empty:
        return None
    x = s.loc[:d]
    return float(x.iloc[-1]) if len(x) else None


def _inicio(meses, hoje: pd.Timestamp) -> pd.Timestamp | None:
    if meses is None:
        return None
    if meses == "ytd":
        return pd.Timestamp(year=hoje.year, month=1, day=1) - pd.Timedelta(days=1)
    return hoje - pd.DateOffset(months=int(meses))


def retorno_serie(s: pd.Series | None, ini: pd.Timestamp | None, fim: pd.Timestamp) -> float | None:
    """Retorno de um índice/preço entre `ini` e `fim` (None = desde o primeiro ponto). None se a série não cobre o início do período."""
    if s is None or len(s) < 2:
        return None
    x = s.dropna().copy()
    x.index = pd.DatetimeIndex(x.index).tz_localize(None) if getattr(pd.DatetimeIndex(x.index), "tz", None) is not None else pd.DatetimeIndex(x.index)
    if ini is None:
        a = float(x.iloc[0])
    else:
        if x.index[0] > ini + pd.Timedelta(days=5):
            return None                           # série começa depois do período: não compara
        a = _indice_em(x, ini)
    b = _indice_em(x, fim)
    return (b / a - 1.0) if a and b and a > 0 else None


def desempenho(valor_hist: pd.Series | None, fluxos: list[tuple[date, float]], eventos: list[dict] | None = None, ini=None, fim=None) -> dict:
    """Desempenho da carteira num período.
    TWR: retorno ponderado pelo tempo (gestao.twr, com proventos) fatiado no período — aporte e retirada NÃO contam como lucro.
    MWR: XIRR do dinheiro (valor inicial, aportes/retiradas, proventos e valor final); só com 90+ dias.
    Também separa o crescimento do patrimônio em aportes líquidos e resultado dos investimentos."""
    if valor_hist is None or len(valor_hist) < 2:
        return {"ok": False, "motivo": "sem histórico de preços da carteira"}
    v = valor_hist.astype(float).copy()
    v.index = pd.DatetimeIndex(v.index).normalize()
    fim_ts = pd.Timestamp(fim) if fim is not None else v.index[-1]
    fim_ts = min(fim_ts, v.index[-1])
    ini_ts = pd.Timestamp(ini) if ini is not None else None
    ev = [e for e in (eventos or []) if _d(e.get("data")) and e.get("efetivo", True) and _ok(e.get("valor"))]
    acum = g.acumulado_proventos(ev) if ev else None
    tw = g.twr(v, fluxos, acum)
    if not tw.get("ok"):
        return {"ok": False, "motivo": tw.get("motivo", "TWR indisponível")}
    idx = tw["indice"]
    primeiro = idx.index[0]
    base = 1.0
    if ini_ts is not None and ini_ts > primeiro:
        b = _indice_em(idx, ini_ts)
        base = b if b else 1.0
    elif ini_ts is not None and ini_ts < primeiro - pd.Timedelta(days=5):
        pass                                      # período começa antes dos dados: vale desde o primeiro dia disponível
    ini_efetivo = max(ini_ts, primeiro) if ini_ts is not None else primeiro
    final = _indice_em(idx, fim_ts)
    if final is None:
        return {"ok": False, "motivo": "período sem dados"}
    twr_p = final / base - 1.0
    dias = (fim_ts - ini_efetivo).days
    # valores e fluxos do período
    v_ini = _indice_em(v, ini_efetivo - pd.Timedelta(days=1)) if ini_efetivo > v.index[0] else None
    v_fim = _indice_em(v, fim_ts)
    f_per = [(_d(d), x) for d, x in fluxos if _d(d) and ini_efetivo <= pd.Timestamp(_d(d)) <= fim_ts]
    aportes_liq = sum(x for _, x in f_per)        # + aporte, − retirada
    prov = sum(e["valor"] for e in ev if ini_efetivo <= pd.Timestamp(_d(e["data"])) <= fim_ts)
    cresc = (v_fim - (v_ini or 0.0)) if v_fim is not None else None
    resultado = (cresc - aportes_liq) if cresc is not None else None
    mwr = None
    if dias >= MIN_DIAS_MWR and v_fim is not None:
        fl = []
        if v_ini:
            fl.append((ini_efetivo.date(), -v_ini))
        fl += [(d, -x) for d, x in f_per]                           # aporte sai do bolso (−), retirada entra (+)
        fl += [(_d(e["data"]), e["valor"]) for e in ev if ini_efetivo <= pd.Timestamp(_d(e["data"])) <= fim_ts]
        fl.append((fim_ts.date(), v_fim))
        mwr = g.xirr(fl)
    return {"ok": True, "twr": twr_p, "twr_aa": g.cagr(twr_p, dias), "mwr_aa": mwr, "dias": dias, "inicio": ini_efetivo.date(), "fim": fim_ts.date(),
            "valor_inicial": v_ini, "valor_final": v_fim, "crescimento": cresc, "aportes_liquidos": aportes_liq, "proventos": prov,
            "resultado_investimentos": resultado, "indice": idx, "motivo_mwr": None if mwr is not None else (f"precisa de {MIN_DIAS_MWR}+ dias no período" if dias < MIN_DIAS_MWR else "fluxos sem troca de sinal")}


def retorno_real(nominal: float | None, ipca_idx: pd.Series | None, ini: pd.Timestamp | None, fim: pd.Timestamp) -> float | None:
    """(1 + nominal) ÷ (1 + inflação do período) − 1 (Fisher). None sem IPCA cobrindo o período."""
    if not _ok(nominal) or ipca_idx is None or len(ipca_idx) < 2:
        return None
    infl = retorno_serie(ipca_idx, ini, fim)
    return (1 + nominal) / (1 + infl) - 1 if infl is not None else None


def tabela_periodos(valor_hist, fluxos, eventos, refs: dict | None, ipca_idx=None, hoje: date | None = None) -> pd.DataFrame:
    """Uma linha por período: TWR e MWR da carteira, retorno real, benchmarks compatíveis e a diferença para o CDI. Período sem dado = n/d."""
    if valor_hist is None or len(valor_hist) < 2:
        return pd.DataFrame()
    fim = pd.Timestamp(valor_hist.index[-1]).normalize()
    linhas = []
    for rot, m in PERIODOS.items():
        ini = _inicio(m, fim)
        r = desempenho(valor_hist, fluxos, eventos, ini, fim)
        if not r.get("ok") or (ini is not None and pd.Timestamp(valor_hist.index[0]) > ini + pd.Timedelta(days=5)):
            linhas.append({"Período": rot, "Carteira (TWR)": None, "MWR a.a.": None, "Retorno real": None, **{k: None for k in (refs or {})}, "vs CDI (p.p.)": None})
            continue
        row = {"Período": rot, "Carteira (TWR)": r["twr"], "MWR a.a.": r["mwr_aa"], "Retorno real": retorno_real(r["twr"], ipca_idx, pd.Timestamp(r["inicio"]), fim)}
        for k, s in (refs or {}).items():
            row[k] = retorno_serie(s, pd.Timestamp(r["inicio"]), fim)
        row["vs CDI (p.p.)"] = ((r["twr"] - row["CDI"]) * 100) if _ok(row.get("CDI")) else None
        linhas.append(row)
    return pd.DataFrame(linhas)


def curva_patrimonio(valor_hist: pd.Series | None, fluxos: list[tuple[date, float]], ini=None) -> pd.DataFrame:
    """Patrimônio de mercado × aportes líquidos acumulados, dia a dia. A distância entre as linhas é o resultado dos investimentos."""
    if valor_hist is None or len(valor_hist) < 2:
        return pd.DataFrame(columns=["data", "patrimonio", "aportes_acum", "resultado"])
    v = valor_hist.astype(float).copy()
    v.index = pd.DatetimeIndex(v.index).normalize()
    f = pd.Series(0.0, index=v.index)
    for d, x in fluxos:
        dd = _d(d)
        if dd is None:
            continue
        pos = v.index.searchsorted(pd.Timestamp(dd))
        if pos < len(v):
            f.iloc[pos] += x
    ac = f.cumsum()
    df = pd.DataFrame({"data": v.index, "patrimonio": v.values, "aportes_acum": ac.values})
    df["resultado"] = df["patrimonio"] - df["aportes_acum"]
    if ini is not None:
        df = df[df["data"] >= pd.Timestamp(ini)]
    return df.reset_index(drop=True)


def aportes_retiradas_mensal(fluxos: list[tuple[date, float]]) -> pd.DataFrame:
    linhas: dict = {}
    for d, x in fluxos:
        dd = _d(d)
        if dd is None or not _ok(x):
            continue
        k = pd.Period(dd, "M")
        a = linhas.setdefault(k, {"mes": k.to_timestamp(), "aportes": 0.0, "retiradas": 0.0})
        a["aportes" if x > 0 else "retiradas"] += abs(x)
    return pd.DataFrame(sorted(linhas.values(), key=lambda z: z["mes"])) if linhas else pd.DataFrame(columns=["mes", "aportes", "retiradas"])


def rendimentos_mensal(eventos: list[dict]) -> pd.DataFrame:
    linhas: dict = {}
    for e in eventos or []:
        dd = _d(e.get("data"))
        if dd is None or not _ok(e.get("valor")) or not e.get("efetivo", True):
            continue
        k = (pd.Period(dd, "M"), e.get("tipo") or "provento")
        linhas[k] = linhas.get(k, 0.0) + e["valor"]
    if not linhas:
        return pd.DataFrame(columns=["mes", "tipo", "valor"])
    return pd.DataFrame([{"mes": k[0].to_timestamp(), "tipo": k[1], "valor": v} for k, v in sorted(linhas.items())])


def desempenho_por_ativo(series: dict[str, pd.Series], posicoes: list[dict], ini=None, fim=None) -> pd.DataFrame:
    """Retorno de preço de cada ativo no período (em R$), e por classe (média ponderada pelo valor atual). Só ativos com série cobrindo o período."""
    ids = {p["id"]: p for p in validas(posicoes)}
    fim_ts = pd.Timestamp(fim) if fim is not None else None
    linhas = []
    for k, s in series.items():
        if k not in ids or s is None or len(s) < 2:
            continue
        f = fim_ts or pd.Timestamp(s.index[-1])
        r = retorno_serie(s, pd.Timestamp(ini) if ini is not None else None, f)
        linhas.append({"Ativo": k, "Classe": g.CLASSES.get(ids[k].get("classe"), ids[k].get("classe")), "Retorno": r, "Valor": ids[k]["valor"]})
    return pd.DataFrame(linhas).sort_values("Retorno", ascending=False, na_position="last").reset_index(drop=True) if linhas else pd.DataFrame(columns=["Ativo", "Classe", "Retorno", "Valor"])


def desempenho_por_classe(df_ativos: pd.DataFrame) -> pd.DataFrame:
    if df_ativos.empty:
        return pd.DataFrame(columns=["Classe", "Retorno", "Valor"])
    d = df_ativos.dropna(subset=["Retorno"])
    if d.empty:
        return pd.DataFrame(columns=["Classe", "Retorno", "Valor"])
    out = d.groupby("Classe").apply(lambda x: pd.Series({"Retorno": float(np.average(x["Retorno"], weights=x["Valor"])), "Valor": float(x["Valor"].sum())}), include_groups=False)
    return out.reset_index().sort_values("Retorno", ascending=False).reset_index(drop=True)


def retornos_mensais_carteira(twr_ret: pd.Series | None) -> pd.Series:
    return g.retorno_por_periodo(twr_ret, "M") if twr_ret is not None and len(twr_ret) else pd.Series(dtype=float)


# =============================================================================== qualidade dos dados
def qualidade_dados(C: dict, D: dict | None = None, hoje: date | None = None) -> list[dict]:
    """Problemas que afetam a confiança dos números. Cada item: nivel ('alto'|'medio'|'info'), tipo, texto, ativos. Nunca preenche lacunas."""
    hoje = hoje or C.get("hoje") or date.today()
    D = D or {}
    pos = C.get("posicoes") or []
    out: list[dict] = []

    def add(nivel, tipo, texto, ativos=None):
        out.append({"nivel": nivel, "tipo": tipo, "texto": texto, "ativos": ativos or []})
    sem = [p["id"] for p in pos if not _ok(p.get("valor")) or p["valor"] <= 0]
    if sem:
        add("alto", "Dado ausente", f"Sem cotação atual: {', '.join(sem)}. Ficam fora do patrimônio e dos percentuais.", sem)
    vel = [p["id"] for p in pos if _d(p.get("data_preco")) and (hoje - _d(p["data_preco"])).days > DIAS_DEFASAGEM and p.get("classe") != "renda_fixa"]
    if vel:
        add("medio", "Dado desatualizado", f"Cotação com mais de {DIAS_DEFASAGEM} dias: {', '.join(vel)}.", vel)
    sem_custo = [p["id"] for p in validas(pos) if p.get("classe") != "caixa" and (not _ok(p.get("custo")) or p["custo"] <= 0)]
    if sem_custo:
        add("medio", "Dado ausente", f"Sem custo informado (ganho e rentabilidade não calculados): {', '.join(sem_custo)}.", sem_custo)
    sem_fx = [p["id"] for p in pos if p.get("moeda", "BRL") != "BRL" and not _ok(p.get("cambio"))]
    if sem_fx:
        add("alto", "Dado ausente", f"Ativos em moeda estrangeira sem câmbio: {', '.join(sem_fx)}.", sem_fx)
    ids = [p["id"] for p in pos]
    dup = sorted({i for i in ids if ids.count(i) > 1})
    if dup:
        add("alto", "Duplicidade", f"Ativo repetido na lista (possível dupla contagem): {', '.join(dup)}.", dup)
    movs = C.get("movs") or []
    vistos: dict = {}
    for m in movs:
        k = (m.get("ticker"), str(m.get("data")), round(float(m.get("qtd", 0)), 8), round(float(m.get("preco", 0)), 8), m.get("tipo"))
        vistos[k] = vistos.get(k, 0) + 1
    dl = sorted({k[0] for k, n in vistos.items() if n > 1})
    if dl:
        add("medio", "Duplicidade", f"Lançamentos idênticos (mesma data, quantidade e preço): {', '.join(dl)}. Confira se não foram cadastrados duas vezes.", dl)
    series = D.get("series") or {}
    sem_hist = [p["id"] for p in validas(pos) if p.get("classe") not in ("caixa", "renda_fixa") and (p["id"] not in series or len(series[p["id"]]) < 30)]
    if sem_hist:
        add("medio", "Dado ausente", f"Sem histórico de preços suficiente (risco e rentabilidade por ativo não calculados): {', '.join(sem_hist)}.", sem_hist)
    # diferença entre fontes: preço da cotação × último ponto da série histórica
    dif = []
    for p in validas(pos):
        s = series.get(p["id"])
        if s is not None and len(s) and _ok(p.get("qtd")) and p["qtd"] > 0 and p.get("classe") not in ("renda_fixa", "fundo", "caixa"):
            ult = float(s.dropna().iloc[-1])
            unit = p["valor"] / p["qtd"]
            if ult > 0 and abs(unit / ult - 1) > 0.05:
                dif.append(f"{p['id']} ({pct(unit / ult - 1, 1, True)})")
    if dif:
        add("medio", "Diferença entre fontes", "Cotação atual difere mais de 5% do último ponto do histórico: " + ", ".join(dif) + ".", [x.split(" ")[0] for x in dif])
    for a in C.get("avisos") or []:
        add("info", "Aviso da coleta", str(a))
    for a in D.get("avisos") or []:
        add("info", "Aviso da coleta", str(a))
    refs = (C.get("referencias") or {}).get("series") or {}
    for r in ("CDI", "Ibovespa", "S&P 500 (em R$)"):
        if r not in refs:
            add("info", "Dado ausente", f"Benchmark {r} indisponível agora: comparações com ele ficam como n/d.")
    return out


def nao_calculados(C: dict, D: dict, desemp: dict | None, tem_ipca: bool) -> dict:
    """Indicadores que não puderam ser calculados e o motivo (para a tela e para o relatório)."""
    m = {}
    if not (D.get("twr_total") or {}).get("ok"):
        m["TWR"] = (D.get("twr_total") or {}).get("motivo", "sem histórico")
    if desemp and desemp.get("ok") and desemp.get("mwr_aa") is None:
        m["MWR/XIRR"] = desemp.get("motivo_mwr") or "fluxos insuficientes"
    elif not desemp or not desemp.get("ok"):
        m["MWR/XIRR"] = (desemp or {}).get("motivo", "sem histórico")
    if not tem_ipca:
        m["Retorno real"] = "IPCA indisponível agora"
    m["Retorno líquido de impostos"] = "o app não tem as taxas e o imposto devido de cada lançamento; os retornos são brutos de impostos"
    sem_hist = [p["id"] for p in validas(C.get("posicoes") or []) if p.get("classe") not in ("caixa",) and p["id"] not in (D.get("series") or {})]
    if sem_hist:
        m["Risco por ativo"] = "sem histórico de preços para " + ", ".join(sem_hist)
    return m


# =============================================================================== indicadores por classe (reaproveita o comparador)
def linhas_ativo(a) -> list[dict]:
    """Indicadores do ativo na régua da SUA classe (comparador.CLASSES[...].specs), com origem, período e data. Indicador sem dado mostra o motivo.
    `a` é um comparador.Ativo. Nunca devolve indicador que não pertença à classe."""
    cls = cmp.CLASSES.get(a.classe)
    if cls is None:
        return []
    if a.erro:
        return [{"Indicador": "—", "Valor": "n/d", "Origem": "", "Período": "", "Data": "", "Observação": a.erro}]
    out = []
    for s in cls.specs:
        i = a.ind.get(s.chave)
        if i is None:
            out.append({"Indicador": s.nome, "Valor": "n/d", "Origem": "", "Período": "", "Data": "", "Observação": "a fonte não entregou este dado"})
        elif not i.aplica:
            out.append({"Indicador": s.nome, "Valor": "não se aplica", "Origem": "", "Período": "", "Data": "", "Observação": "não vale para este tipo de ativo"})
        elif i.valor is None:
            out.append({"Indicador": s.nome, "Valor": "n/d", "Origem": i.origem, "Período": i.periodo or "", "Data": i.data_ref or "", "Observação": "dado indisponível na fonte"})
        else:
            out.append({"Indicador": s.nome, "Valor": cmp.fmt_valor(i.valor, s.fmt), "Origem": {"dado": "Dado da fonte", "calculado": "Calculado", "estimado": "Estimativa"}.get(i.origem, i.origem),
                        "Período": i.periodo or "", "Data": i.data_ref or "", "Observação": s.dica or ""})
    return out


# =============================================================================== fotografias (histórico e rastreabilidade)
def fotografia(chave_carteira: str, C: dict, D: dict, quando: datetime | None = None, desemp: dict | None = None, qualidade: list | None = None) -> dict:
    """Foto do estado da carteira (sem dados pessoais além dos números): serve para comparar períodos sem recalcular o passado."""
    quando = quando or datetime.now()
    pos = validas(C.get("posicoes") or [])
    r = resumo(C.get("posicoes") or [], C.get("eventos"))
    return {"data": quando.date().isoformat(), "gerado_em": quando.isoformat(timespec="seconds"), "carteira": chave_carteira, "versao": VERSAO,
            "patrimonio": r["patrimonio"], "investido": r["investido"], "ganho": r["ganho"], "proventos": r["proventos"], "n_posicoes": r["n_posicoes"],
            "twr_total": (desemp or {}).get("twr") if (desemp or {}).get("ok") else None, "mwr_aa": (desemp or {}).get("mwr_aa") if (desemp or {}).get("ok") else None,
            "por_classe": {x["nome"]: x["valor"] for x in g.distribuicao(pos, "classe")},
            "por_ativo": {p["id"]: p["valor"] for p in pos},
            "fontes": sorted({p.get("fonte") for p in pos if p.get("fonte")}),
            "qualidade": {"alto": sum(1 for q in qualidade or [] if q["nivel"] == "alto"), "medio": sum(1 for q in qualidade or [] if q["nivel"] == "medio"),
                          "avisos": [q["texto"] for q in (qualidade or []) if q["nivel"] in ("alto", "medio")][:10]}}


def guardar_fotografia(fotos: list[dict], nova: dict, max_fotos: int = MAX_FOTOS) -> tuple[list[dict], str]:
    """Acrescenta a foto. Uma por dia e carteira: se já existe, a anterior é MANTIDA no histórico de alterações (campo 'substituida_por') e a nova entra.
    Nunca apaga silenciosamente. Devolve (lista, mensagem)."""
    fotos = list(fotos or [])
    msg = "Fotografia salva."
    for f in fotos:
        if f.get("data") == nova["data"] and f.get("carteira") == nova["carteira"] and not f.get("substituida_por"):
            f["substituida_por"] = nova["gerado_em"]
            msg = "Já havia uma fotografia de hoje; a anterior foi mantida como versão substituída."
    fotos.append(nova)
    ativas = [f for f in fotos if not f.get("substituida_por")]
    if len(ativas) > max_fotos:                       # só as mais antigas ATIVAS saem, e avisamos
        corte = sorted(ativas, key=lambda f: f["gerado_em"])[: len(ativas) - max_fotos]
        ids = {f["gerado_em"] for f in corte}
        fotos = [f for f in fotos if f["gerado_em"] not in ids]
        msg += f" Limite de {max_fotos} fotografias: as {len(corte)} mais antigas foram removidas."
    return fotos, msg


def comparar_fotografias(a: dict, b: dict) -> dict:
    """Diferenças entre duas fotografias (a = anterior, b = recente). O resultado por ativo separa o que foi aporte do que foi variação NÃO é possível só com fotos:
    por isso a comparação mostra variação do patrimônio e, se houver, do TWR acumulado, sem chamar a diferença de rentabilidade."""
    def dif(k):
        return (b.get(k) - a.get(k)) if _ok(a.get(k)) and _ok(b.get(k)) else None
    ativos = sorted(set(a.get("por_ativo", {})) | set(b.get("por_ativo", {})))
    novos = [x for x in ativos if x not in a.get("por_ativo", {})]
    saiu = [x for x in ativos if x not in b.get("por_ativo", {})]
    classes = sorted(set(a.get("por_classe", {})) | set(b.get("por_classe", {})))
    return {"dias": (date.fromisoformat(b["data"]) - date.fromisoformat(a["data"])).days, "dif_patrimonio": dif("patrimonio"), "dif_investido": dif("investido"),
            "dif_proventos": dif("proventos"), "dif_twr": dif("twr_total"), "novos": novos, "saiu": saiu,
            "classes": [{"classe": c, "antes": a.get("por_classe", {}).get(c, 0.0), "depois": b.get("por_classe", {}).get(c, 0.0)} for c in classes]}


# =============================================================================== montagem e exportação do relatório
def montar_relatorio(titulo: str, identificacao: str, periodo: str, filtros: dict, secoes: list[dict], fontes: list[str], avisos: list[str],
                     quando: datetime | None = None) -> dict:
    """Documento neutro (usado pelo PDF, Excel e CSV). Seção: {'titulo', 'tipo': 'kpis'|'tabela'|'texto', 'dados'}.
    kpis: lista de (rótulo, valor, detalhe); tabela: DataFrame (valores já formatados em texto); texto: lista de linhas."""
    quando = quando or datetime.now()
    return {"titulo": titulo, "identificacao": identificacao, "periodo": periodo, "filtros": {k: v for k, v in (filtros or {}).items() if v},
            "gerado_em": quando.strftime("%d/%m/%Y %H:%M"), "secoes": secoes, "fontes": sorted(set(fontes)), "avisos": list(dict.fromkeys(avisos)), "versao": VERSAO, "aviso_legal": AVISO}


def formatar_tabela(df: pd.DataFrame, moeda=(), percentual=(), pp=()) -> pd.DataFrame:
    """Converte colunas para texto formatado (R$, %, p.p.), preservando n/d. Usada nas exportações e na tela."""
    out = df.copy()
    for c in moeda:
        if c in out:
            out[c] = out[c].map(brl)
    for c in percentual:
        if c in out:
            out[c] = out[c].map(lambda v: pct(v, 2, True))
    for c in pp:
        if c in out:
            out[c] = out[c].map(lambda v: "n/d" if not _ok(v) else (f"{v:+.2f}".replace(".", ",") + " p.p."))
    return out.fillna("n/d")


def csv_bytes(df: pd.DataFrame) -> bytes:
    """CSV para planilha brasileira: separador ';', decimal ',' e BOM UTF-8 (o Excel abre com os acentos certos)."""
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def _texto_celula(v) -> str:
    return "" if v is None else str(v)


def excel_bytes(doc: dict, tabelas_numericas: dict[str, pd.DataFrame] | None = None) -> bytes:
    """Excel com: aba 'Resumo' (identificação, período, filtros, indicadores, fontes e avisos), uma aba por tabela do relatório e,
    se dadas, abas numéricas (valores crus, para o usuário calcular)."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    wb = Workbook()
    ws = wb.active
    ws.title = "Resumo"
    ws["A1"] = doc["titulo"]
    ws["A1"].font = Font(size=16, bold=True, color="0E2A5C")
    meta = [("Identificação", doc["identificacao"]), ("Período analisado", doc["periodo"]), ("Gerado em", doc["gerado_em"])]
    meta += [(f"Filtro: {k}", ", ".join(v) if isinstance(v, (list, tuple)) else str(v)) for k, v in doc["filtros"].items()]
    r = 3
    for k, v in meta:
        ws.cell(r, 1, k).font = Font(bold=True)
        ws.cell(r, 2, _texto_celula(v))
        r += 1
    for s in doc["secoes"]:
        if s["tipo"] == "kpis":
            r += 1
            ws.cell(r, 1, s["titulo"]).font = Font(bold=True, size=12, color="0E2A5C")
            r += 1
            for rot, val, det in s["dados"]:
                ws.cell(r, 1, rot)
                ws.cell(r, 2, _texto_celula(val)).font = Font(bold=True)
                ws.cell(r, 3, _texto_celula(det))
                r += 1
    r += 1
    ws.cell(r, 1, "Fontes dos dados").font = Font(bold=True)
    for f in doc["fontes"]:
        r += 1
        ws.cell(r, 1, f)
    r += 2
    ws.cell(r, 1, "Avisos sobre dados").font = Font(bold=True, color="B42318")
    for a in doc["avisos"] or ["Nenhum aviso."]:
        r += 1
        ws.cell(r, 1, a)
    r += 2
    ws.cell(r, 1, doc["aviso_legal"]).alignment = Alignment(wrap_text=False)
    ws.column_dimensions["A"].width = 34
    ws.column_dimensions["B"].width = 40
    ws.column_dimensions["C"].width = 60
    cab = PatternFill("solid", fgColor="0E2A5C")

    def escrever(nome: str, df: pd.DataFrame):
        w = wb.create_sheet(nome[:31])
        for j, c in enumerate(df.columns, 1):
            x = w.cell(1, j, str(c))
            x.font = Font(bold=True, color="FFFFFF")
            x.fill = cab
        for i, row in enumerate(df.itertuples(index=False), 2):
            for j, v in enumerate(row, 1):
                if isinstance(v, (np.floating, float)) and not math.isfinite(v):
                    v = None
                elif isinstance(v, np.generic):
                    v = v.item()
                elif isinstance(v, pd.Timestamp):
                    v = v.to_pydatetime()
                w.cell(i, j, v)
        for j, c in enumerate(df.columns, 1):
            w.column_dimensions[get_column_letter(j)].width = min(max(len(str(c)) + 2, 12), 40)
        w.freeze_panes = "A2"
    usados = set()
    for s in doc["secoes"]:
        if s["tipo"] == "tabela" and len(s["dados"]):
            nome = "".join(ch for ch in s["titulo"] if ch not in "[]:*?/\\")[:28] or "Tabela"
            base, k = nome, 2
            while nome in usados:
                nome = f"{base[:25]}_{k}"
                k += 1
            usados.add(nome)
            escrever(nome, s["dados"])
    for nome, df in (tabelas_numericas or {}).items():
        escrever("num_" + nome[:25], df)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def pdf_bytes(doc: dict, graficos: list[dict] | None = None) -> bytes:
    """PDF profissional (A4): capa com identificação, período, filtros e data; indicadores; tabelas; gráficos simples; fontes; avisos; aviso legal.
    `graficos`: [{'titulo','tipo':'linha'|'barras'|'pizza','x':[...],'series':{nome:[...]}}] desenhados com reportlab (sem dependências extras)."""
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.shapes import Drawing, String
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
    azul, cinza = colors.HexColor("#0E2A5C"), colors.HexColor("#5B6B82")
    ss = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=ss["Title"], textColor=azul, fontSize=20, alignment=0, spaceAfter=4)
    h2 = ParagraphStyle("h2", parent=ss["Heading2"], textColor=azul, fontSize=13, spaceBefore=10, spaceAfter=4)
    corpo = ParagraphStyle("c", parent=ss["BodyText"], fontSize=9, leading=12)
    peq = ParagraphStyle("p", parent=corpo, fontSize=7.5, textColor=cinza, leading=10)
    cel = ParagraphStyle("cel", parent=corpo, fontSize=7.5, leading=9)

    def esc(t) -> str:
        return str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    buf = io.BytesIO()

    def rodape(canvas, d):
        canvas.saveState()
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(cinza)
        canvas.drawString(1.5 * cm, 1.0 * cm, f"{doc['titulo']} · gerado em {doc['gerado_em']} · Bolsa para Todos")
        canvas.drawRightString(A4[0] - 1.5 * cm, 1.0 * cm, f"Página {d.page}")
        canvas.restoreState()
    pdf = SimpleDocTemplate(buf, pagesize=A4, leftMargin=1.5 * cm, rightMargin=1.5 * cm, topMargin=1.5 * cm, bottomMargin=1.6 * cm, title=doc["titulo"], author="Bolsa para Todos")
    el = [Paragraph(esc(doc["titulo"]), h1), Paragraph(f"<b>{esc(doc['identificacao'])}</b> · Período: {esc(doc['periodo'])} · Gerado em {esc(doc['gerado_em'])}", corpo)]
    if doc["filtros"]:
        el.append(Paragraph("Filtros: " + "; ".join(f"{esc(k)}: {esc(', '.join(v) if isinstance(v, (list, tuple)) else v)}" for k, v in doc["filtros"].items()), peq))
    if doc["avisos"]:
        el += [Spacer(1, 6), Paragraph("<b>Avisos sobre os dados</b>", corpo)] + [Paragraph("• " + esc(a), peq) for a in doc["avisos"][:12]]
    for s in doc["secoes"]:
        bloco = [Paragraph(esc(s["titulo"]), h2)]
        if s["tipo"] == "kpis":
            dados = [[Paragraph(f"<font size=7 color='#5B6B82'>{esc(r)}</font><br/><b>{esc(v)}</b><br/><font size=6.5 color='#5B6B82'>{esc(dt or '')}</font>", cel) for r, v, dt in s["dados"][k:k + 3]]
                     for k in range(0, len(s["dados"]), 3)]
            for linha in dados:
                linha += [""] * (3 - len(linha))
            t = Table(dados, colWidths=[6 * cm] * 3)
            t.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D3E3")), ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D3E3")),
                                   ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#F4F7FC")), ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
            bloco.append(t)
        elif s["tipo"] == "tabela":
            df = s["dados"]
            if len(df) == 0:
                bloco.append(Paragraph("Sem dados para esta seção.", peq))
            else:
                df = df.head(60)
                n = len(df.columns)
                larg = (A4[0] - 3 * cm) / n
                dados = [[Paragraph(f"<b>{esc(c)}</b>", cel) for c in df.columns]] + [[Paragraph(esc(_texto_celula(v)), cel) for v in row] for row in df.itertuples(index=False)]
                t = Table(dados, colWidths=[larg] * n, repeatRows=1)
                t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCE6F5")), ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C9D3E3")),
                                       ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFD")]), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                       ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]))
                bloco.append(t)
                if len(s["dados"]) > 60:
                    bloco.append(Paragraph(f"Mostradas 60 de {len(s['dados'])} linhas; o Excel e o CSV trazem todas.", peq))
        else:
            bloco += [Paragraph(esc(l), corpo) for l in s["dados"]]
        el.append(KeepTogether(bloco[:2]) if len(bloco) > 1 else bloco[0])
        el += bloco[2:]
    cores = [colors.HexColor(c) for c in ("#2563EB", "#10B981", "#F59E0B", "#EF4444", "#8B5CF6", "#06B6D4", "#64748B", "#EC4899")]
    for gr in graficos or []:
        try:
            d = Drawing(17.5 * cm, 6.2 * cm)
            d.add(String(0, 5.9 * cm, gr["titulo"], fontSize=9, fillColor=azul))
            if gr["tipo"] == "pizza":
                p = Pie()
                p.x, p.y, p.width, p.height = 2 * cm, 0.4 * cm, 4.8 * cm, 4.8 * cm
                p.data = [max(float(v), 0.0) for v in list(gr["series"].values())[0]]
                p.labels = [f"{n} ({v / sum(p.data) * 100:.0f}%)" if sum(p.data) else n for n, v in zip(gr["x"], p.data)]
                p.sideLabels = 1
                p.slices.fontSize = 6
                for k in range(len(p.data)):
                    p.slices[k].fillColor = cores[k % len(cores)]
                d.add(p)
            elif gr["tipo"] == "barras":
                b = VerticalBarChart()
                b.x, b.y, b.width, b.height = 1.8 * cm, 0.9 * cm, 14.5 * cm, 4.4 * cm
                b.data = [[0.0 if not _ok(v) else float(v) for v in vs] for vs in gr["series"].values()]
                b.categoryAxis.categoryNames = [str(x)[:12] for x in gr["x"]]
                b.categoryAxis.labels.fontSize = 6
                b.valueAxis.labels.fontSize = 6
                for k in range(len(b.data)):
                    b.bars[k].fillColor = cores[k % len(cores)]
                d.add(b)
            else:
                lc = HorizontalLineChart()
                lc.x, lc.y, lc.width, lc.height = 1.8 * cm, 0.9 * cm, 14.5 * cm, 4.4 * cm
                passo = max(1, len(gr["x"]) // 120)
                lc.data = [[float(v) if _ok(v) else 0.0 for v in vs[::passo]] for vs in gr["series"].values()]
                lc.categoryAxis.categoryNames = [str(x)[:10] for x in gr["x"][::passo]]
                lc.categoryAxis.labelTextFormat = lambda v: ""
                lc.valueAxis.labels.fontSize = 6
                for k in range(len(lc.data)):
                    lc.lines[k].strokeColor = cores[k % len(cores)]
                    lc.lines[k].strokeWidth = 1.2
                d.add(lc)
                for k, nome in enumerate(gr["series"]):
                    d.add(String(2 * cm + k * 4.5 * cm, 0.25 * cm, nome[:24], fontSize=6.5, fillColor=cores[k % len(cores)]))
            el.append(KeepTogether([d]))
        except Exception:                                   # um gráfico que falha não derruba o relatório
            el.append(Paragraph(f"Gráfico “{esc(gr.get('titulo', ''))}” indisponível neste PDF.", peq))
    el += [Paragraph("Fontes dos dados", h2)] + [Paragraph("• " + esc(f), peq) for f in doc["fontes"]]
    el += [Spacer(1, 8), Paragraph(esc(doc["aviso_legal"]), peq)]
    pdf.build(el, onFirstPage=rodape, onLaterPages=rodape)
    return buf.getvalue()


def disponibilidade_exportacao() -> dict:
    """Quais formatos funcionam neste ambiente (bibliotecas instaladas)."""
    out = {"csv": True}
    for k, mod in (("excel", "openpyxl"), ("pdf", "reportlab")):
        try:
            __import__(mod)
            out[k] = True
        except Exception:
            out[k] = False
    return out


# =============================================================================== histórico e risco da seleção filtrada
def historico_filtrado(C: dict, ids: set[str] | None) -> dict:
    """Valor histórico, aportes/retiradas e proventos SÓ dos ativos escolhidos (ids=None: todos). Usa as mesmas funções do Passo 12.
    Ativos sem série de preço (renda fixa, fundos CVM) entram no patrimônio e na alocação, mas não nesta série; isso volta em 'avisos'."""
    precos = C.get("precos_brl")
    movs = [m for m in (C.get("movs") or []) if ids is None or m["ticker"] in ids]
    if precos is None or getattr(precos, "empty", True) or not movs:
        return {"valor_hist": pd.Series(dtype=float), "fluxos": [], "eventos": [], "avisos": ["Sem histórico de preços para a seleção."]}
    cols = set(precos.columns)
    movs = [m for m in movs if m["ticker"] in cols]
    if not movs:
        return {"valor_hist": pd.Series(dtype=float), "fluxos": [], "eventos": [], "avisos": ["Os ativos selecionados não têm histórico de preços (renda fixa e fundos CVM ficam fora das séries)."]}
    qtd = g.quantidades_no_tempo(movs, precos.index)
    vh, av = g.valor_historico(qtd, precos)
    fl = g.fluxos_externos(movs, C.get("moedas") or {}, C.get("cambio"))
    ev = [e for e in (C.get("eventos") or []) if e.get("fonte") in cols and (ids is None or e["fonte"] in ids)]
    return {"valor_hist": vh, "fluxos": fl, "eventos": ev, "avisos": av}


def risco_basico(retornos: pd.Series | None, indice: pd.Series | None, cdi_diario: pd.Series | None = None) -> dict:
    """Indicadores de risco da seleção a partir do TWR diário (mesmas funções do Passo 12/16). Cada um vem None quando faltam dias,
    com o motivo em 'motivos' — nunca com número estimado."""
    out: dict = {"motivos": {}}
    n = 0 if retornos is None else int(retornos.dropna().shape[0])
    out["n_dias"] = n
    out["vol"] = g.vol_anual(retornos) if n else None
    dd = g.drawdown(indice) if indice is not None and len(indice) > 1 else {"ok": False}
    out["mdd"] = dd.get("maximo") if dd.get("ok") else None
    out["dd_atual"] = dd.get("atual") if dd.get("ok") else None
    out["dd_serie"] = dd.get("serie") if dd.get("ok") else None
    out["sharpe"] = g.sharpe(retornos, cdi_diario) if n else None
    out["sortino"] = g.sortino(retornos, cdi_diario) if n else None
    out["var95"] = g.var_historico(retornos, 0.95) if n else None
    out["cvar95"] = g.cvar_historico(retornos, 0.95) if n else None
    for k, minimo in (("vol", 30), ("sharpe", 60), ("sortino", 60), ("var95", 250), ("cvar95", 250)):
        if out[k] is None:
            out["motivos"][k] = f"precisa de {minimo}+ dias de retorno (há {n})" if n < minimo else "dado insuficiente ou sem variação"
    if out["mdd"] is None:
        out["motivos"]["mdd"] = "sem histórico"
    return out


# =============================================================================== cálculo completo e documento
def calcular(C: dict, D: dict, filtros: dict | None = None, ini=None, fim=None, ipca_idx: pd.Series | None = None, rotulo_periodo: str = "Desde o início",
             identificacao: str = "Carteira", quando: datetime | None = None) -> dict:
    """Tudo o que os dashboards, relatórios e exportações precisam, para a seleção (filtros) e o período. Função pura: não usa Streamlit nem rede.
    Sem histórico de preços, as partes de desempenho e risco voltam vazias com o motivo — o patrimônio e a alocação continuam disponíveis."""
    quando = quando or datetime.now()
    filtros = {k: v for k, v in (filtros or {}).items() if v}
    todas = C.get("posicoes") or []
    pos = filtrar(todas, **{k: filtros.get(k) for k in CAMPOS_FILTRO})
    ids = {p["id"] for p in pos}
    sem_filtro = len(pos) == len(todas)
    if sem_filtro and D.get("valor_hist") is not None and len(D.get("valor_hist", [])):
        hist = {"valor_hist": D["valor_hist"], "fluxos": D.get("fluxos_mercado") or [], "eventos": D.get("eventos_mercado") or [], "avisos": list(D.get("avisos") or [])}
    else:
        hist = historico_filtrado(C, ids)
    vh, fl, ev = hist["valor_hist"], hist["fluxos"], hist["eventos"]
    refs = (C.get("referencias") or {}).get("series") or {}
    fim_ts = pd.Timestamp(fim) if fim is not None else (pd.Timestamp(vh.index[-1]) if len(vh) else None)
    des = desempenho(vh, fl, ev, ini, fim_ts) if len(vh) > 1 else {"ok": False, "motivo": "sem histórico de preços da carteira"}
    tabela = tabela_periodos(vh, fl, ev, refs, ipca_idx)
    curva = curva_patrimonio(vh, fl, ini=des.get("inicio") if des.get("ok") else ini)
    retornos = idx = None
    if len(vh) > 1:
        tw = g.twr(vh, fl, g.acumulado_proventos([e for e in ev if _d(e.get("data"))]) if ev else None)
        if tw.get("ok"):
            ini_r = pd.Timestamp(des["inicio"]) if des.get("ok") else None
            retornos = tw["retornos"] if ini_r is None else tw["retornos"].loc[ini_r:]
            idx = (1 + retornos).cumprod() if len(retornos) else None
    cdi_d = D.get("cdi_diario")
    risco = risco_basico(retornos, idx, cdi_d)
    ev_resumo = [e for e in (C.get("eventos") or []) if e.get("fonte") in ids]
    res = resumo(pos, ev_resumo)
    din = desempenho_por_ativo(D.get("series") or {}, pos, des.get("inicio") if des.get("ok") else ini, fim_ts)
    C_f = {**C, "posicoes": pos}
    qual = qualidade_dados(C_f, D, C.get("hoje"))
    real = retorno_real(des.get("twr") if des.get("ok") else None, ipca_idx, pd.Timestamp(des["inicio"]) if des.get("ok") else None, fim_ts) if fim_ts is not None else None
    nc = nao_calculados(C_f, D, des, ipca_idx is not None and len(ipca_idx) > 1)
    fontes = sorted({p.get("fonte") for p in pos if p.get("fonte")} | ({"Banco Central do Brasil (CDI, IPCA)"} if "CDI" in refs or ipca_idx is not None else set()))
    return {"quando": quando, "identificacao": identificacao, "periodo": rotulo_periodo, "filtros": filtros, "posicoes": pos, "n_total": len(todas),
            "resumo": res, "desemp": des, "tabela_periodos": tabela, "curva": curva, "retornos": retornos, "indice": idx, "risco": risco, "retorno_real": real,
            "tabela_posicoes": tabela_posicoes(pos), "ranking": ranking(pos),
            "dist": {c: distribuicao(pos, c) for c in ("classe", "setor", "pais", "moeda")}, "conc": g.concentracao([p["valor"] for p in validas(pos)]),
            "alertas_conc": g.avaliar_concentracao(validas(pos)) if validas(pos) else [], "por_ativo": din, "por_classe": desempenho_por_classe(din),
            "aportes_mes": aportes_retiradas_mensal([(d, x) for d, x in fl if (not des.get("ok")) or pd.Timestamp(_d(d)) >= pd.Timestamp(des["inicio"])]),
            "rend_mes": rendimentos_mensal(ev), "qualidade": qual, "nao_calc": nc, "fontes": fontes, "avisos_hist": hist["avisos"], "refs": refs}


def documento_da_carteira(X: dict, secoes: list[str] | None = None) -> tuple[dict, list[dict], dict]:
    """(documento, gráficos do PDF, tabelas numéricas do Excel) a partir de `calcular`. `secoes`: subconjunto de
    ('resumo', 'desempenho', 'posicoes', 'alocacao', 'risco', 'qualidade'); None = todas."""
    todas = ("resumo", "desempenho", "posicoes", "alocacao", "risco", "qualidade")
    sel = [s for s in todas if secoes is None or s in secoes]
    r, d, ri = X["resumo"], X["desemp"], X["risco"]
    S: list[dict] = []
    if "resumo" in sel:
        k = [("Patrimônio total", brl(r["patrimonio"]), f"{r['n_posicoes']} posições"), ("Total investido (custo)", brl(r["investido"]), "posições com custo informado" if r["investido"] is not None else "custo não informado"),
             ("Ganho / perda não realizado", brl(r["ganho"]), pct(r["ganho_pct"], 2, True)), ("Resultado realizado (vendas)", brl(r["realizado"]), ""),
             ("Proventos recebidos", brl(r["proventos"]), "dividendos, rendimentos e juros registrados"), ("Resultado total", brl(r["resultado_total"]), "ganho + realizado + proventos")]
        if d.get("ok"):
            k += [("Rentabilidade no período (TWR)", pct(d["twr"], 2, True), f"{d['inicio']:%d/%m/%Y} a {d['fim']:%d/%m/%Y}; aportes não contam como lucro"),
                  ("Rentabilidade do dinheiro (MWR/XIRR)", pct(d["mwr_aa"], 2, True) + " a.a." if d.get("mwr_aa") is not None else "n/d", d.get("motivo_mwr") or "considera quando cada aporte entrou"),
                  ("Aportes líquidos no período", brl(d["aportes_liquidos"]), "aportes − retiradas"), ("Resultado dos investimentos", brl(d["resultado_investimentos"]), "crescimento − aportes líquidos")]
        else:
            k.append(("Rentabilidade no período", "n/d", d.get("motivo", "")))
        S.append({"titulo": "Resumo executivo", "tipo": "kpis", "dados": k})
    if "desempenho" in sel and len(X["tabela_periodos"]):
        t = X["tabela_periodos"]
        S.append({"titulo": "Rentabilidade por período (TWR) e benchmarks", "tipo": "tabela",
                  "dados": formatar_tabela(t, percentual=[c for c in t.columns if c not in ("Período", "vs CDI (p.p.)")], pp=["vs CDI (p.p.)"])})
    if "posicoes" in sel and len(X["tabela_posicoes"]):
        S.append({"titulo": "Posições", "tipo": "tabela", "dados": formatar_tabela(X["tabela_posicoes"], moeda=["Valor (R$)", "Custo (R$)", "Resultado (R$)"], percentual=["Resultado (%)"]).assign(
            **{"Peso": X["tabela_posicoes"]["Peso"].map(lambda v: pct(v, 1))})})
    if "alocacao" in sel:
        for c, rot in (("classe", "classe"), ("setor", "setor"), ("pais", "país"), ("moeda", "moeda")):
            df = X["dist"][c]
            if len(df):
                S.append({"titulo": f"Alocação por {rot}", "tipo": "tabela", "dados": pd.DataFrame({rot.capitalize(): df["nome"].map(lambda z: g.CLASSES.get(z, z)) if c == "classe" else df["nome"],
                                                                                                   "Valor": df["valor"].map(brl), "Peso": df["pct"].map(lambda v: pct(v, 1))})})
    if "risco" in sel:
        k = [("Volatilidade anualizada", pct(ri.get("vol"), 2), ri["motivos"].get("vol", "")), ("Maior queda (drawdown)", pct(ri.get("mdd"), 2), ri["motivos"].get("mdd", "")),
             ("Sharpe", "n/d" if ri.get("sharpe") is None else f"{ri['sharpe']:.2f}".replace(".", ","), ri["motivos"].get("sharpe", "contra o CDI")),
             ("Sortino", "n/d" if ri.get("sortino") is None else f"{ri['sortino']:.2f}".replace(".", ","), ri["motivos"].get("sortino", "")),
             ("VaR 95% (1 dia)", pct(ri.get("var95"), 2), ri["motivos"].get("var95", "histórico")), ("CVaR 95% (1 dia)", pct(ri.get("cvar95"), 2), ri["motivos"].get("cvar95", ""))]
        c = X["conc"]
        if c.get("ok"):
            k += [("Maior posição", pct(c["top1"], 1), ""), ("3 maiores posições", pct(c["top3"], 1), ""), ("Nº efetivo de posições", f"{c['n_efetivo']:.1f}".replace(".", ","), f"HHI {c['hhi']:.3f}".replace(".", ","))]
        S.append({"titulo": "Risco e concentração", "tipo": "kpis", "dados": k})
    if "qualidade" in sel:
        q = X["qualidade"]
        S.append({"titulo": "Qualidade dos dados", "tipo": "tabela", "dados": pd.DataFrame([{"Nível": z["nivel"], "Tipo": z["tipo"], "Descrição": z["texto"]} for z in q]) if q else pd.DataFrame({"Descrição": ["Nenhum problema encontrado."]})})
        if X["nao_calc"]:
            S.append({"titulo": "Indicadores não calculados", "tipo": "tabela", "dados": pd.DataFrame([{"Indicador": k_, "Motivo": v_} for k_, v_ in X["nao_calc"].items()])})
    avisos = [z["texto"] for z in X["qualidade"] if z["nivel"] in ("alto", "medio")] + list(X.get("avisos_hist") or [])
    filtros = {k: v for k, v in X["filtros"].items() if v}
    doc = montar_relatorio("Relatório da carteira", X["identificacao"], X["periodo"], filtros, S, X["fontes"] or ["Dados informados pelo usuário"], avisos, X["quando"])
    graficos = []
    cv = X["curva"]
    if len(cv) > 2:
        graficos.append({"titulo": "Patrimônio × aportes líquidos acumulados", "tipo": "linha", "x": [f"{x:%d/%m/%Y}" for x in cv["data"]],
                         "series": {"Patrimônio": list(cv["patrimonio"]), "Aportes líquidos": list(cv["aportes_acum"])}})
    dc = X["dist"]["classe"]
    if len(dc):
        graficos.append({"titulo": "Alocação por classe", "tipo": "pizza", "x": [g.CLASSES.get(n, n) for n in dc["nome"]], "series": {"Valor": list(dc["valor"])}})
    rm = X["rend_mes"]
    if len(rm):
        pv = rm.groupby("mes")["valor"].sum()
        graficos.append({"titulo": "Proventos recebidos por mês (R$)", "tipo": "barras", "x": [f"{m:%m/%y}" for m in pv.index], "series": {"Proventos": list(pv.values)}})
    numericas = {"posicoes": X["tabela_posicoes"], "periodos": X["tabela_periodos"], "curva": X["curva"]}
    numericas = {k: v for k, v in numericas.items() if len(v)}
    return doc, graficos, numericas
