"""
Passo 20 · Orquestração dos cálculos do comparador (sem Streamlit e sem rede).

Recebe os ativos já coletados e padronizados (`itens`) e as referências (`refs`: câmbio, benchmarks, IPCA) e devolve tudo o que a tela e as
exportações mostram. Separa assim: coleta (comparador_dados) → padronização e cálculo (aqui e comparador_desempenho) → pontuação → IA → tela.

itens[chave] = {"classe", "moeda", "nome", "preco": Series, "prov": Series|None, "fonte": id, "tentativas": [...], "avisos": [...], "coletado_em": "AAAA-MM-DD HH:MM",
                "divergencia": dict|None}
refs = {"series": {"CDI", "Ibovespa", "S&P 500 (em R$)", "Dólar"}, "sp_usd": Series|None, "fx": Series|None, "ipca": Series|None, "avisos": [...]}
params = {"periodo": rótulo de D.PRESETS ou "Personalizado", "ini", "fim", "modo": "comum"|"estrito", "moeda": "BRL"|"USD"|"NATIVA",
          "proventos": bool, "benchmarks": [nomes]}
"""
from __future__ import annotations

import re
from datetime import date

import pandas as pd

import comparador as cmp
import comparador_desempenho as D
import comparador_fontes as F
import relatorios as R

DIAS_DESATUALIZADO = 7
OFICIAIS = {"cvm", "tesouro", "bcb"}
PADRAO = {"periodo": "12 meses", "ini": None, "fim": None, "modo": "comum", "moeda": "BRL", "proventos": True, "benchmarks": ["CDI", "Ibovespa"]}


def benchmarks_disponiveis(moeda: str, refs: dict) -> dict[str, pd.Series]:
    """Benchmarks que fazem sentido na moeda escolhida. Em reais: CDI, Ibovespa, S&P 500 (em R$) e Dólar. Em dólar: S&P 500 (US$).
    Sem converter (moeda de cada ativo) não há benchmark: cada ativo estaria numa moeda."""
    if moeda == "BRL":
        return {k: D.limpar(v) for k, v in (refs.get("series") or {}).items() if v is not None and len(v) > 5}
    if moeda == "USD" and refs.get("sp_usd") is not None and len(refs["sp_usd"]) > 5:
        return {"S&P 500 (US$)": D.limpar(refs["sp_usd"])}
    return {}


def _padronizar(itens: dict, refs: dict, p: dict) -> tuple[dict, dict, list, list]:
    """Série de cada ativo na moeda de comparação (retorno total, se pedido) → (séries, informações de conversão, avisos, excluídos)."""
    series, conv, avisos, excl = {}, {}, [], []
    alvo = p.get("moeda", "BRL")
    for k, it in itens.items():
        preco = D.limpar(it.get("preco"))
        if len(preco) < 30:
            excl.append((k, "histórico de preços insuficiente"))
            continue
        base, info = preco, {"proventos": 0}
        if p.get("proventos", True) and it.get("prov") is not None and len(it["prov"]):
            base, info = D.retorno_total(preco, it["prov"])
        moeda = (it.get("moeda") or "BRL").upper()
        if alvo in ("BRL", "USD") and moeda != alvo:
            base, c = D.converter(base, refs.get("fx"), moeda, alvo)
            conv[k] = c
            if base.empty:
                excl.append((k, c.get("erro", "não foi possível converter a moeda")))
                continue
        series[k] = base
        if info.get("proventos"):
            conv.setdefault(k, {})["proventos"] = info["proventos"]
    return series, conv, avisos, excl


def calcular(itens: dict, refs: dict, params: dict | None = None, hoje: date | None = None) -> dict:
    """Desempenho, risco, consistência e nota histórica de todos os ativos no MESMO período e na MESMA moeda."""
    p = {**PADRAO, **(params or {})}
    hoje = hoje or R.agora().date()
    out: dict = {"ok": False, "avisos": [], "params": p}
    series, conv, avisos, excl = _padronizar(itens, refs, p)
    out["avisos"] += avisos
    if p["moeda"] == "NATIVA" and len({(itens[k].get("moeda") or "BRL").upper() for k in series}) > 1:
        out["avisos"].append("Os ativos estão em moedas diferentes e a moeda não foi convertida: os retornos NÃO são diretamente comparáveis. Escolha R$ ou US$.")
    if len(series) < 1:
        out["excluidos"] = excl
        out["avisos"].append("Nenhum ativo tem histórico suficiente para comparar o desempenho.")
        return out
    rot = p["periodo"]
    fim_ref = min(s.index[-1] for s in series.values())
    ini = None
    if rot == "Personalizado":
        ini, fim_p = p.get("ini"), p.get("fim")
        if fim_p is not None:
            fim_ref = min(fim_ref, pd.Timestamp(fim_p))
    elif rot in D.PRESETS and D.PRESETS[rot][0] != "max":
        ini = D.inicio_janela(rot, fim_ref)
    per = D.periodo_comum(series, ini, fim_ref, p["modo"])
    out["excluidos"] = excl + per.get("excluidos", [])
    if not per["ok"]:
        out["avisos"].append("Período: " + per["motivo"] + ".")
        return out
    ini_c, fim_c = per["ini"], per["fim"]
    S = {k: series[k] for k in per["validos"]}
    out.update({"ok": True, "ini": ini_c, "fim": fim_c, "dias": per["dias"], "series": S, "conversao": conv, "periodo_info": per})
    if p["modo"] == "comum" and ini is not None and ini_c > pd.Timestamp(ini) + pd.Timedelta(days=D.TOLERANCIA_DIAS):
        out["avisos"].append(f"O período escolhido foi encurtado para {ini_c:%d/%m/%Y} a {fim_c:%d/%m/%Y}, a janela em que todos os ativos têm dados. "
                             "Retornos de períodos diferentes não são comparáveis; por isso todos usam a mesma janela.")
    for k, why in out["excluidos"]:
        out["avisos"].append(f"{k} ficou de fora: {why}.")
    bench = {n: b for n, b in benchmarks_disponiveis(p["moeda"], refs).items() if n in p.get("benchmarks", [])}
    faltando = [n for n in p.get("benchmarks", []) if n not in bench and p["moeda"] in ("BRL", "USD")]
    if faltando:
        out["avisos"].append("Benchmark indisponível agora: " + ", ".join(faltando) + ".")
    if p["moeda"] == "NATIVA" and p.get("benchmarks"):
        out["avisos"].append("Benchmarks só aparecem com a moeda convertida (R$ ou US$).")
    out["bench"] = bench
    ipca = refs.get("ipca")
    out["tabela_ret"] = D.tabela_retornos(S, fim_c, ini_c, ipca, p["moeda"], bench)
    if p["moeda"] == "BRL" and ipca is None:
        out["avisos"].append("IPCA indisponível agora: retorno real não calculado.")
    if p["moeda"] != "BRL":
        out["avisos"].append("Retorno real (descontada a inflação) só é calculado em reais, com o IPCA.")
    rb = out["tabela_ret"].set_index("Ativo")["Período escolhido"] if len(out["tabela_ret"]) else pd.Series(dtype=float)
    out["bench_ret"] = {n: float(rb[n]) for n in bench if n in rb.index and R._ok(rb[n])}
    linhas = []
    for k in S:
        row = {"Ativo": k, "Retorno no período": rb.get(k)}
        for n, v in out["bench_ret"].items():
            row[f"vs {n} (p.p.)"] = D.vs_benchmark(rb.get(k), v)
        linhas.append(row)
    out["tabela_vs"] = pd.DataFrame(linhas)
    out["base100"] = D.base100({**S, **bench}, ini_c, fim_c)
    out["cal_anual"] = D.tabela_calendario({k: v[(v.index >= ini_c) & (v.index <= fim_c)] for k, v in S.items()}, "Y")
    out["cal_mensal"] = D.tabela_calendario({k: v[(v.index >= ini_c) & (v.index <= fim_c)] for k, v in S.items()}, "M")
    ref_beta = next((n for n in ("Ibovespa", "S&P 500 (US$)", "S&P 500 (em R$)") if n in bench), None)
    if ref_beta is None and p["moeda"] in ("BRL", "USD"):
        out["avisos"].append("Beta indisponível: selecione o Ibovespa (em reais) ou o S&P 500 (em dólar) como benchmark.")
    cdi = refs.get("series", {}).get("CDI") if p["moeda"] == "BRL" else None
    rf = None
    if cdi is not None and len(cdi) > 60:
        rf = D.retornos_uteis(cdi)
        out["rf"] = "CDI"
    else:
        out["rf"] = "0% (sem taxa livre de risco)"
        out["avisos"].append("Sharpe e Sortino sem taxa livre de risco (CDI indisponível ou moeda diferente de R$): usam 0%.")
    out["risco_tab"], out["risco_det"] = D.tabela_risco(S, bench.get(ref_beta) if ref_beta else None, rf, ini_c, fim_c)
    out["ref_beta"] = ref_beta
    out["corr"] = D.correlacoes(S, ini_c, fim_c)
    out["cons"] = {k: D.consistencia(v[(v.index >= ini_c) & (v.index <= fim_c)], bench.get(ref_beta) if ref_beta else None) for k, v in S.items()}
    out["pont_hist"] = {k: D.pontuar_historico(itens[k]["classe"], out["risco_det"][k], out["cons"][k]) for k in S}
    out["liquido"] = {}
    for k in S:
        if itens[k]["classe"] == "renda_fixa":
            out["liquido"][k] = D.liquido_renda_fixa(rb.get(k), per["dias"])
    for k in S:
        n = out["risco_det"][k]["n_dias"]
        if n < 250:
            out["avisos"].append(f"{k}: só {n} dias úteis no período (VaR, CVaR e Calmar pedem 250); volatilidade, Sharpe e notas ficam provisórios ou indisponíveis.")
        if (pd.Timestamp(hoje) - S[k].index[-1]).days > DIAS_DESATUALIZADO:
            out["avisos"].append(f"{k}: último preço em {S[k].index[-1]:%d/%m/%Y}, com mais de {DIAS_DESATUALIZADO} dias de atraso.")
    classes_cripto = [k for k in S if itens[k]["classe"] == "cripto"]
    if classes_cripto and len(classes_cripto) < len(S):
        out["avisos"].append("Cripto negocia todos os dias e a bolsa só em dias úteis: volatilidade e correlação usam apenas dias úteis, para ficarem comparáveis.")
    for k, c in conv.items():
        if c.get("convertido"):
            tx = lambda v: f"{v:.4f}".replace(".", ",")
            out["avisos"].append(f"{k}: convertido de {c['de']} para {c['para']} pelo dólar (BCB): {tx(c['taxa_inicio'])} em {c['data_inicio']} e {tx(c['taxa_fim'])} em {c['data_fim']}.")
    return out


# =============================================================================== rastreabilidade
def confiabilidade(fonte: str, dias_atraso: int | None, pontos: int, divergencia: dict | None = None) -> str:
    """Alta / Média / Baixa. Parte da natureza da fonte (oficial = Alta) e rebaixa por atraso (> 7 dias), histórico curto (< 1 ano) e divergência entre fontes."""
    nivel = 2 if fonte in OFICIAIS else 1
    if dias_atraso is not None and dias_atraso > DIAS_DESATUALIZADO:
        nivel -= 1
    if pontos < 252:
        nivel -= 1
    if divergencia and divergencia.get("ok") is False:
        nivel -= 1
    return ("Baixa", "Média", "Alta")[max(0, min(2, nivel))]


def rastreio(itens: dict, res: dict | None = None, hoje: date | None = None) -> pd.DataFrame:
    """Tabela de rastreabilidade: fonte, data de coleta, data de referência, moeda, frequência e confiabilidade de cada ativo."""
    hoje = pd.Timestamp(hoje or R.agora().date())
    linhas = []
    for k, it in itens.items():
        s = D.limpar(it.get("preco"))
        ult = s.index[-1] if len(s) else None
        atraso = int((hoje - ult).days) if ult is not None else None
        linhas.append({"Ativo": k, "Classe": cmp.CLASSES[it["classe"]].nome if it["classe"] in cmp.CLASSES else it["classe"],
                       "Fonte": F.rotulo_fonte(it.get("fonte", "")) if it.get("fonte") else "n/d", "Coletado em": it.get("coletado_em") or "n/d",
                       "Dados até": ult.strftime("%d/%m/%Y") if ult is not None else "n/d", "Início do histórico": s.index[0].strftime("%d/%m/%Y") if len(s) else "n/d",
                       "Pontos": int(len(s)), "Moeda": (it.get("moeda") or "n/d"), "Unidade": "preço de fechamento por unidade/cota", "Frequência": "diária",
                       "Confiabilidade": confiabilidade(it.get("fonte", ""), atraso, len(s), it.get("divergencia")) if len(s) else "Baixa"})
    return pd.DataFrame(linhas)


# =============================================================================== carteiras
def parse_modelo(texto: str) -> tuple[dict[str, float], list[str]]:
    """Lê 'PETR4:40, VALE3 30; BTC-USD=30%' → ({'PETR4': 40, ...}, erros). Aceita ':', '=' ou espaço entre o código e o peso; pesos repetidos somam."""
    pesos: dict[str, float] = {}
    erros: list[str] = []
    for parte in re.split(r"[,;\n]+", texto or ""):
        parte = parte.strip()
        if not parte:
            continue
        m = re.fullmatch(r"([A-Za-z0-9./\-]+)\s*[:=\s]\s*([0-9]+(?:[.,][0-9]+)?)\s*%?", parte)
        if not m:
            erros.append(f"“{parte}” não é 'CÓDIGO:PESO'.")
            continue
        peso = float(m.group(2).replace(",", "."))
        if peso <= 0:
            erros.append(f"{m.group(1).upper()}: o peso precisa ser maior que zero.")
            continue
        k = m.group(1).upper()
        pesos[k] = pesos.get(k, 0.0) + peso
    return pesos, erros


def dy_12m(prov: pd.Series | None, ultimo_preco: float | None, fim=None) -> float | None:
    """Dividend yield dos 12 meses até `fim`: soma dos proventos por cota ÷ último preço. None sem proventos ou sem preço."""
    if prov is None or len(prov) == 0 or not R._ok(ultimo_preco) or ultimo_preco <= 0:
        return None
    p = pd.Series(prov)
    p.index = pd.DatetimeIndex(p.index)
    fim = pd.Timestamp(fim) if fim is not None else p.index.max()
    j = p[(p.index > fim - pd.Timedelta(days=365)) & (p.index <= fim)]
    return float(j.sum() / ultimo_preco) if len(j) else 0.0


def calcular_carteiras(entradas: dict, refs: dict, janela: str = "12 meses") -> dict:
    """Compara as carteiras de `entradas[nome]` = {'series': {ativo: Series em R$}, 'pesos': {ativo: valor}, 'posicoes': {ativo: {valor, classe, moeda}}, 'dy': {ativo: dy}}.
    Usa o Ibovespa como referência de beta e o CDI como taxa livre de risco (em reais)."""
    series = refs.get("series") or {}
    ibov = D.limpar(series.get("Ibovespa")) if series.get("Ibovespa") is not None else None
    cdi = series.get("CDI")
    rf = D.retornos_uteis(cdi) if cdi is not None and len(cdi) > 60 else None
    res = D.comparar_carteiras(entradas, bench=ibov, rf=rf, janela=janela)
    res["rf"] = "CDI" if rf is not None else "0%"
    res["ref_beta"] = "Ibovespa" if ibov is not None and len(ibov) > 60 else None
    if res.get("ok"):
        if rf is None:
            res["avisos"].append("CDI indisponível: Sharpe e Sortino usam taxa livre de risco de 0%.")
        if res["ref_beta"] is None:
            res["avisos"].append("Ibovespa indisponível: beta não calculado.")
        ini, fim = res["ini"], res["fim"]
        res["bench100"] = D.base100({n: series[n] for n in ("CDI", "Ibovespa") if series.get(n) is not None}, ini, fim)
    return res


# =============================================================================== IA e exportação
def contexto_ia(ativos: list, comp, res: dict, itens: dict, refs: dict | None = None) -> dict:
    """Monta o contexto da IA do comparador só com o que já foi calculado."""
    per = {"ini": f"{res['ini']:%d/%m/%Y}", "fim": f"{res['fim']:%d/%m/%Y}", "moeda": {"BRL": "R$", "USD": "US$", "NATIVA": "moeda de cada ativo"}[res["params"]["moeda"]],
           "modo": res["params"]["modo"]}
    tr = res["tabela_ret"].set_index("Ativo") if len(res["tabela_ret"]) else pd.DataFrame()
    ret = {k: {c: (None if not R._ok(tr.loc[k, c]) else float(tr.loc[k, c])) for c in ("Período escolhido", "Anualizado (a.a.)", "Retorno real")}
           for k in res["series"] if k in tr.index}
    risco = {k: {c: m.get(c) for c in ("vol_anual", "mdd", "sharpe", "var95", "n_dias")} for k, m in res["risco_det"].items()}
    cor = []
    c = res.get("corr")
    if c is not None and len(c):
        ks = list(c.columns)
        cor = [(a, b, float(c.loc[a, b])) for i, a in enumerate(ks) for b in ks[i + 1:]]
    lista = []
    for a in ativos:
        if a.erro or a.chave not in res["series"]:
            continue
        dd = (comp.destaques or {}).get(a.chave, {}) if comp is not None else {}
        ph = res["pont_hist"].get(a.chave)
        lista.append({"chave": a.chave, "nome": a.nome, "classe": a.classe, "classe_nome": cmp.CLASSES[a.classe].nome if a.classe in cmp.CLASSES else a.classe,
                      "nota": a.pontuacao.nota if a.pontuacao else None, "faixa": a.pontuacao.faixa if a.pontuacao else None,
                      "provisoria": bool(a.pontuacao and a.pontuacao.provisoria), "fonte": a.fonte, "data_ref": a.data_ref,
                      "vantagens": dd.get("vantagens", []), "desvantagens": dd.get("desvantagens", []),
                      "ausentes": (comp.indisponiveis or {}).get(a.chave, []) if comp is not None else [], "nota_hist": ph.nota if ph else None})
    alertas = [x for x in res["avisos"]][:8]
    fontes = sorted({F.rotulo_fonte(it.get("fonte", "")) for it in itens.values() if it.get("fonte")})
    return {"gerado_em": R.agora().isoformat(timespec="minutes"), "periodo": per, "ativos": lista, "retornos": ret, "bench": res.get("bench_ret", {}), "risco": risco,
            "correlacao": cor, "alertas": alertas, "fontes": fontes}


def tabelas_formatadas(res: dict, itens: dict) -> list[tuple[str, pd.DataFrame]]:
    """Tabelas já em texto (pt-BR) para tela, PDF, Excel e CSV."""
    T: list[tuple[str, pd.DataFrame]] = []
    tr = res["tabela_ret"].drop(columns=["Tipo"], errors="ignore")
    pct_cols = [c for c in tr.columns if c != "Ativo"]
    T.append(("Retornos (acumulados até a data final; 3 e 5 anos acumulados)", D.tabela_texto(tr, pct_cols=pct_cols)))
    if len(res.get("tabela_vs", [])) and res["tabela_vs"].shape[1] > 2:
        vs = res["tabela_vs"]
        T.append(("Diferença para os benchmarks no período", D.tabela_texto(vs, pct_cols=["Retorno no período"], pp_cols=[c for c in vs.columns if c.startswith("vs ")])))
    rt = res["risco_tab"]
    T.append(("Risco", D.tabela_texto(rt, pct_cols=["Volatilidade anual", "Queda máxima", "Queda atual", "VaR 95% (1 dia)", "CVaR 95% (1 dia)"],
                                      num_cols=["Sharpe", "Sortino", "Beta", "Calmar"]).astype({"Dias úteis": str})))
    ph = [{"Ativo": k, "Classe": cmp.CLASSES[itens[k]["classe"]].nome, "Perfil histórico": "n/d" if v.nota is None else f"{v.nota:.0f}/100" + (" (provisória)" if v.provisoria else "")}
          for k, v in res["pont_hist"].items()]
    T.append(("Perfil histórico (nota complementar)", pd.DataFrame(ph)))
    if len(res.get("cal_anual", [])):
        T.append(("Retorno por ano calendário (primeiro e último anos podem ser parciais)", D.tabela_texto(res["cal_anual"].reset_index().rename(columns={"index": "Ano"}),
                                                                                                        pct_cols=list(res["cal_anual"].columns))))
    T.append(("Rastreabilidade", rastreio(itens, res)))
    return T


def graficos_pdf(res: dict, max_pontos: int = 60) -> list[dict]:
    """Gráficos simples para o PDF: evolução base 100 e retorno no período."""
    G = []
    b = res.get("base100")
    if b is not None and len(b) > 3:
        idx = b.index[:: max(1, len(b) // max_pontos)]
        x = [d.strftime("%m/%y") for d in idx]
        G.append({"titulo": "Evolução (base 100 no início do período)", "tipo": "linha", "x": x,
                  "series": {c: [None if not R._ok(v) else float(v) for v in b.loc[idx, c]] for c in b.columns}})
    rb = res["tabela_ret"].set_index("Ativo")["Período escolhido"] if len(res["tabela_ret"]) else None
    if rb is not None and len(rb):
        G.append({"titulo": "Retorno no período (%)", "tipo": "barras", "x": list(rb.index), "series": {"Retorno (%)": [None if not R._ok(v) else float(v) * 100 for v in rb.values]}})
    return G


METODOLOGIA = [
    "Retornos: variação do preço de fechamento entre as datas; com 'incluir proventos', cada provento é reinvestido no dia ex (retorno total). Janelas de 3 e 5 anos são acumuladas; só períodos de 1 ano ou mais são anualizados.",
    "Mesmo período para todos: no modo 'janela comum' todos usam o intervalo em que todos têm dados; no modo estrito, quem não cobre o início fica de fora.",
    "Moeda: ativos em outra moeda são convertidos pelo dólar do Banco Central do dia (taxa e datas informadas). Retorno real = (1 + nominal) ÷ (1 + IPCA do período) − 1, só em reais.",
    "Risco: volatilidade anualizada (√252, só dias úteis), queda máxima, Sharpe e Sortino (CDI como taxa livre de risco em reais), beta contra o benchmark, VaR e CVaR históricos de 95% em 1 dia (mínimo 250 dias). Sem amostra suficiente, o indicador fica n/d.",
    "Nota da classe: calculada pelo Comparar (Passo 6), com critérios próprios de cada classe; notas de classes diferentes nunca são ranqueadas entre si.",
    "Perfil histórico (complementar): Sharpe, volatilidade, queda máxima e consistência mensal, com âncoras da própria classe; com menos de 1 ano de dados a nota é provisória.",
    "Retorno líquido: estimado só para renda fixa (IR regressivo, sem IOF); nas demais classes depende de regras que o app não confirma e fica n/d.",
    "Desempenho passado não garante desempenho futuro. Nada aqui é recomendação de investimento.",
]


def _fontes_do_documento(res: dict, itens: dict) -> list[str]:
    """Fontes dos ativos + as dos auxiliares realmente usados (câmbio, CDI, IPCA pelo BCB; índices pelo Yahoo)."""
    f = {F.rotulo_fonte(it.get("fonte", "")) for it in itens.values() if it.get("fonte")}
    if any(c.get("convertido") for c in res.get("conversao", {}).values()) or "CDI" in res.get("bench", {}) or res.get("tabela_ret") is not None and "Retorno real" in res["tabela_ret"] and res["tabela_ret"]["Retorno real"].notna().any():
        f.add("Banco Central do Brasil (câmbio, CDI e IPCA)")
    if any(b in res.get("bench", {}) for b in ("Ibovespa", "S&P 500 (em R$)", "S&P 500 (US$)")):
        f.add("Yahoo Finance (índices)")
    return sorted(f)


def preparar_exportacao(res: dict, itens: dict, ativos: list | None = None) -> tuple[dict, list[dict], dict]:
    """(documento, gráficos do PDF, tabelas numéricas do Excel) da comparação."""
    per = f"{res['ini']:%d/%m/%Y} a {res['fim']:%d/%m/%Y} ({res['dias']} dias), moeda: {({'BRL': 'R$', 'USD': 'US$', 'NATIVA': 'de cada ativo'})[res['params']['moeda']]}"
    its = [{"chave": k, "nome": itens[k].get("nome", ""), "classe": cmp.CLASSES[itens[k]["classe"]].nome, "fonte": F.rotulo_fonte(itens[k].get("fonte", "")),
            "data_ref": res["series"][k].index[-1].strftime("%d/%m/%Y")} for k in res["series"]]
    conv = [f"{k}: {c['taxa_inicio']:.4f} em {c['data_inicio']} → {c['taxa_fim']:.4f} em {c['data_fim']} (dólar BCB)".replace(".", ",") for k, c in res.get("conversao", {}).items() if c.get("convertido")]
    doc = D.documento("Comparação de investimentos", per, its, tabelas_formatadas(res, itens), METODOLOGIA,
                      _fontes_do_documento(res, itens), res["avisos"], "; ".join(conv))
    num = {"Retornos": res["tabela_ret"], "Risco": res["risco_tab"], "Evolução base 100": res["base100"].reset_index().rename(columns={"index": "Data"})}
    if len(res.get("corr", [])):
        num["Correlação"] = res["corr"].reset_index().rename(columns={"index": "Ativo"})
    return doc, graficos_pdf(res), num
