"""
Passo 18 · Simulador de investimentos, projeções, juros compostos e planejamento financeiro (motor de cálculo).

Sem Streamlit e sem rede: só números. Tudo o que a tela mostra vem daqui, e as fórmulas estão documentadas em FORMULAS
(simulador_ia.py) e nos comentários de cada função.

Princípios
- Nada é previsão. Cada taxa é uma HIPÓTESE escolhida (ou editada) pela pessoa; os valores iniciais por classe são pontos de partida
  declarados como premissa (PREMISSAS_CLASSE), não dados de mercado. CDI, Selic e IPCA de hoje entram quando a camada de dados os fornece.
- Mês é a unidade de cálculo. Taxa anual efetiva vira mensal por (1 + a)^(1/12) − 1 (juros compostos equivalentes, não a/12).
- Aporte no fim ou no início do mês, à escolha. Semanal vale 52/12 aportes por mês (aproximação declarada).
- Valores nominais e reais (poder de compra de hoje) sempre lado a lado.
- Imposto: aplicado na liquidação hipotética (resgate no mês observado), lote a lote na renda fixa (tabela regressiva), sobre o ganho nas
  demais classes. Regras simplificadas e documentadas; a pessoa pode trocar a alíquota.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

import renda_fixa as rf

VERSAO = 1
DIAS_NO_MES = 30.4375

AVISO = ("Simulações são hipóteses de planejamento, não previsões nem promessas de rentabilidade. Os resultados mudam com cada premissa; "
         "rentabilidade passada não garante rentabilidade futura. Impostos e custos aqui seguem regras simplificadas.")


# =============================================================================== taxas e inflação
def mensal(taxa_aa: float) -> float:
    """Taxa anual efetiva → mensal equivalente: (1 + a)^(1/12) − 1."""
    return (1.0 + taxa_aa) ** (1.0 / 12.0) - 1.0


def anual(taxa_am: float) -> float:
    """Taxa mensal → anual efetiva: (1 + m)^12 − 1."""
    return (1.0 + taxa_am) ** 12 - 1.0


def nominal_para_efetiva(nominal_aa: float, capitalizacoes: int = 12) -> float:
    """Taxa nominal (ex.: '12% a.a. capitalizada mensalmente') → efetiva anual: (1 + i/n)^n − 1."""
    return (1.0 + nominal_aa / capitalizacoes) ** capitalizacoes - 1.0


def efetiva_para_nominal(efetiva_aa: float, capitalizacoes: int = 12) -> float:
    """Efetiva anual → nominal com n capitalizações por ano: n · ((1 + e)^(1/n) − 1)."""
    return capitalizacoes * ((1.0 + efetiva_aa) ** (1.0 / capitalizacoes) - 1.0)


def fisher(nominal: float, inflacao: float) -> float:
    """Rentabilidade real (Fisher): (1 + nominal) / (1 + inflação) − 1."""
    return (1.0 + nominal) / (1.0 + inflacao) - 1.0


def nominal_de_real(real: float, inflacao: float) -> float:
    return (1.0 + real) * (1.0 + inflacao) - 1.0


def liquida_de_custo(bruta_aa: float, custo_aa: float) -> float:
    """Taxa líquida de custo anual (taxa de administração etc.): (1 + bruta) / (1 + custo) − 1."""
    return (1.0 + bruta_aa) / (1.0 + custo_aa) - 1.0


def fatores_inflacao(inflacao, meses: int) -> np.ndarray:
    """Índice de preços acumulado F[0..meses] (F[0] = 1). `inflacao`: número (% a.a. como fração) ou lista por ano (o último valor se repete).
    Dentro de cada ano a inflação mensal é a equivalente composta, então F[12] = Π (1 + inflação do ano)."""
    anos = [float(inflacao)] if np.isscalar(inflacao) else [float(x) for x in (inflacao or [0.0])]
    f = np.ones(meses + 1)
    for t in range(1, meses + 1):
        a = anos[min((t - 1) // 12, len(anos) - 1)]
        f[t] = f[t - 1] * (1.0 + mensal(a))
    return f


def poder_de_compra(valor_hoje: float, inflacao, anos: float) -> float:
    """Quanto R$ valor_hoje compraria daqui a `anos` em termos de hoje (valor / índice de preços)."""
    f = fatores_inflacao(inflacao, int(round(anos * 12)))
    return valor_hoje / f[-1]


def corrigir_pela_inflacao(valor_hoje: float, inflacao, anos: float) -> float:
    """Valor nominal futuro necessário para manter o poder de compra de `valor_hoje`."""
    return valor_hoje * fatores_inflacao(inflacao, int(round(anos * 12)))[-1]


def inflacao_media_anual(inflacao, meses: int) -> float:
    if meses <= 0:
        return 0.0
    f = fatores_inflacao(inflacao, meses)
    return float(f[-1] ** (12.0 / meses) - 1.0)


def tir_mensal(fluxos: list[tuple[float, float]]) -> float | None:
    """Taxa interna de retorno mensal de fluxos (mês, valor) — saídas negativas, entradas positivas. Bissecção; None se não houver sinal trocado."""
    if not fluxos or not any(v < 0 for _, v in fluxos) or not any(v > 0 for _, v in fluxos):
        return None
    t = np.array([a for a, _ in fluxos], dtype=float)
    v = np.array([b for _, b in fluxos], dtype=float)

    def f(r):
        with np.errstate(over="ignore"):
            return float(np.sum(v * np.exp(-t * np.log1p(r))))
    tmax = max(float(t.max()), 1.0)
    lo, hi = max(-0.5, math.exp(-500.0 / tmax) - 1.0), 1.0     # evita estouro numérico: cobre de ≈ −44% a +100% ao mês
    flo, fhi = f(lo), f(hi)
    if flo * fhi > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        fm = f(mid)
        if flo * fm <= 0:
            hi, fhi = mid, fm
        else:
            lo, flo = mid, fm
        if hi - lo < 1e-13:
            break
    return (lo + hi) / 2


# =============================================================================== aportes
FREQUENCIAS = {"semanal": ("n", 52.0 / 12.0), "quinzenal": ("n", 2.0), "mensal": ("n", 1.0),
               "bimestral": ("k", 2), "trimestral": ("k", 3), "semestral": ("k", 6), "anual": ("k", 12)}


def aporte_no_mes(valor: float, freq: str, mes: int, momento: str = "fim") -> float:
    """Aporte devido no mês `mes` (1, 2, ...). Frequências ≥ mensal: valor × aportes por mês, todo mês. Menores: no mês 1 (início) ou
    no último mês de cada período (fim)."""
    tipo, x = FREQUENCIAS[freq]
    if tipo == "n":
        return valor * x
    if momento == "inicio":
        return valor if (mes - 1) % x == 0 else 0.0
    return valor if mes % x == 0 else 0.0


# =============================================================================== impostos
TIPOS_IR = {
    "rf": "Renda fixa tributável (tabela regressiva 22,5% a 15%, IOF até 30 dias)",
    "rf_isento": "Renda fixa isenta para pessoa física (LCI, LCA etc.)",
    "ganho_15": "Ganho de capital a 15% (ações em swing trade, ETFs de renda variável)",
    "ganho_20": "Ganho de capital a 20% (cotas de FIIs vendidas em bolsa)",
    "fundo_lp": "Fundo de longo prazo (15% sobre o rendimento; come-cotas aproximado pelo resgate)",
    "cripto": "Criptoativos (15% sobre o ganho; faixas maiores e isenções não modeladas)",
    "isento": "Sem imposto (ou imposto fora do modelo)",
    "personalizado": "Alíquota informada por você sobre o ganho",
}
ALIQUOTA_PADRAO = {"ganho_15": 0.15, "ganho_20": 0.20, "fundo_lp": 0.15, "cripto": 0.15, "isento": 0.0, "rf_isento": 0.0}


def _ir_rf_vetor(valor_in: np.ndarray, valor_atual: np.ndarray, dias: np.ndarray, tipo_chave: str) -> tuple[float, float]:
    """(IR, IOF) de cada lote da renda fixa, vetorizado, com as mesmas regras de renda_fixa.tributar. Perda de um lote não abate ganho de outro."""
    tp = rf.tipo(tipo_chave)
    rend = np.maximum(valor_atual - valor_in, 0.0)
    if tp.iof:
        iof_tab = np.where(dias >= 30, 0.0, np.where(dias <= 0, 1.0, np.array(rf.IOF_TABELA + [0.0])[np.clip(dias.astype(int) - 1, 0, 29)] / 100.0))
        iof = rend * iof_tab
    else:
        iof = np.zeros_like(rend)
    base = rend - iof
    aliq = np.where(dias <= 180, 0.225, np.where(dias <= 360, 0.20, np.where(dias <= 720, 0.175, 0.15)))
    ir = np.zeros_like(rend) if tp.isento_ir_pf else base * aliq
    return float(ir.sum()), float(iof.sum())


def imposto_na_saida(tipo: str, valor_in: np.ndarray, indice_in: np.ndarray, mes_in: np.ndarray, indice_atual: float, mes_atual: int,
                     valor_atual: float, base_total: float, tipo_rf: str = "cdb", aliquota: float | None = None) -> dict:
    """Imposto devido se tudo fosse resgatado agora. Renda fixa: lote a lote pela idade de cada aporte. Demais: aliquota × ganho total
    (valor atual − base). Retorna {'ir', 'iof', 'total'}."""
    if tipo in ("rf", "rf_isento"):
        va = valor_in * indice_atual / indice_in
        dias = np.floor((mes_atual - mes_in) * DIAS_NO_MES)
        chave = tipo_rf if tipo == "rf" else (tipo_rf if rf.tipo(tipo_rf).isento_ir_pf else "lci")
        ir, iof = _ir_rf_vetor(valor_in, va, dias, chave)
        return {"ir": ir, "iof": iof, "total": ir + iof}
    a = aliquota if aliquota is not None else ALIQUOTA_PADRAO.get(tipo, 0.0)
    ir = max(valor_atual - base_total, 0.0) * a
    return {"ir": ir, "iof": 0.0, "total": ir}


# =============================================================================== projeção principal
def _normalizar(p: dict) -> dict:
    q = {
        "inicial": 0.0, "aporte": 0.0, "freq": "mensal", "momento": "fim", "meses": 120,
        "taxa_aa": 0.10,               # retorno nominal bruto do preço/índice (a.a. efetiva); distribuições à parte em dy_aa
        "dy_aa": 0.0, "cresc_dist_aa": None,   # yield das distribuições (% do valor, a.a.) e crescimento delas (nominal a.a.); None = igual ao do preço
        "reinvestir": True, "ir_dist": 0.0,    # reinvestir distribuições; imposto sobre elas
        "custo_aa": 0.0, "custo_aporte": 0.0,  # taxa de administração/custódia a.a.; custo por aporte (fração)
        "inflacao": 0.045, "reajuste_aporte": None,   # 'inflacao' | fração a.a. | None
        "extras": [], "choques": [], "mudancas_taxa": [], "cortes_dist": [],
        "ir": "isento", "tipo_rf": "cdb", "aliquota": None, "haircut_saida": 0.0,
    }
    q.update({k: v for k, v in (p or {}).items() if v is not None or k in ("cresc_dist_aa", "reajuste_aporte", "aliquota")})
    q["meses"] = int(max(0, round(q["meses"])))
    if q["freq"] not in FREQUENCIAS:
        raise ValueError(f"frequência desconhecida: {q['freq']}")
    if q["ir"] not in TIPOS_IR:
        raise ValueError(f"tipo de imposto desconhecido: {q['ir']}")
    return q


def projetar(p: dict, detalhado: bool = True) -> dict:
    """Projeção mês a mês de um investimento com aportes. Devolve {'df', 'resumo', 'params'}.

    Modelo: índice I (cresce a cada mês pela taxa líquida de custo e sofre choques) × unidades U. Cada aporte compra U += a / I.
    Valor = I · U. Distribuições (yield): valor × yield/12, reinvestidas (compram unidades) ou acumuladas como renda recebida.
    A taxa pode mudar ao longo do tempo (mudancas_taxa), as distribuições podem ser cortadas (cortes_dist) e o preço pode sofrer choques.
    Imposto na saída: ver imposto_na_saida. Real = líquido / índice de preços."""
    q = _normalizar(p)
    N = q["meses"]
    F = fatores_inflacao(q["inflacao"], N)
    I = 1.0
    U = 0.0
    renda_acum = 0.0
    investido = 0.0
    base = 0.0                      # custo fiscal (aportes + distribuições reinvestidas)
    lotes_v, lotes_i, lotes_m = [], [], []
    fluxos = []                     # (mês, valor) do ponto de vista do investidor
    linhas = []
    ajuste_taxa = 0.0
    corte = 1.0
    extras = {}
    for e in q["extras"]:
        extras[int(e["mes"])] = extras.get(int(e["mes"]), 0.0) + float(e["valor"])
    choques = {}
    for c in q["choques"]:
        choques.setdefault(int(c["mes"]), []).append(float(c["pct"]) / 100.0)
    custo_aa = q["custo_aa"]
    taxa0 = q["taxa_aa"]
    gd = q["cresc_dist_aa"] if q["cresc_dist_aa"] is not None else taxa0
    reajuste = q["reajuste_aporte"]

    def comprar(valor_bruto: float, mes: int, momento_indice: float, custo_pct: float = 0.0):
        nonlocal U, base
        liquido_comprado = valor_bruto * (1.0 - custo_pct)
        if liquido_comprado <= 0:
            return
        U += liquido_comprado / momento_indice
        base += liquido_comprado
        lotes_v.append(liquido_comprado)
        lotes_i.append(momento_indice)
        lotes_m.append(mes)

    # capital inicial no mês 0
    if q["inicial"] > 0:
        investido += q["inicial"]
        fluxos.append((0, -q["inicial"]))
        comprar(q["inicial"], 0, I)

    def valor_aporte(mes: int) -> float:
        v = aporte_no_mes(q["aporte"], q["freq"], mes, q["momento"])
        if v and reajuste is not None:
            if isinstance(reajuste, str) and reajuste == "inflacao":
                v *= F[mes - 1]
            else:
                v *= (1.0 + float(reajuste)) ** ((mes - 1) / 12.0)
        return v

    for t in range(1, N + 1):
        for m in q["mudancas_taxa"]:
            if int(m["mes"]) == t:
                ajuste_taxa += float(m["delta_pp"]) / 100.0
        for c in q["cortes_dist"]:
            if int(c["mes"]) == t:
                corte *= 1.0 - float(c["pct"]) / 100.0
        a_t = valor_aporte(t) + extras.get(t, 0.0) if q["momento"] == "inicio" else 0.0
        if a_t > 0:
            investido += a_t
            fluxos.append((t - 1, -a_t))
            comprar(a_t, t - 1, I, q["custo_aporte"])
        taxa_t = liquida_de_custo(taxa0 + ajuste_taxa, custo_aa) if custo_aa else taxa0 + ajuste_taxa
        I *= 1.0 + mensal(taxa_t)
        for pct in choques.get(t, []):
            I *= 1.0 + pct
        V = I * U
        dist = 0.0
        if q["dy_aa"] > 0 and V > 0:
            fator = ((1.0 + gd) / (1.0 + taxa0)) ** (t / 12.0) if taxa0 > -1 else 1.0
            dist = V * q["dy_aa"] / 12.0 * fator * corte
            dist *= (1.0 - q["ir_dist"])
        if dist > 0:
            if q["reinvestir"]:
                comprar(dist, t, I)
            else:
                renda_acum += dist
                fluxos.append((t, dist))
        if q["momento"] == "fim":
            a_t = valor_aporte(t) + extras.get(t, 0.0)
            if a_t > 0:
                investido += a_t
                fluxos.append((t, -a_t))
                comprar(a_t, t, I, q["custo_aporte"])
        if detalhado or t == N:
            V = I * U
            imp = imposto_na_saida(q["ir"], np.array(lotes_v), np.array(lotes_i), np.array(lotes_m), I, t, V, base, q["tipo_rf"], q["aliquota"])
            liq = V * (1.0 - q["haircut_saida"]) - imp["total"]
            linhas.append({"mes": t, "ano": t / 12.0, "investido": investido, "patrimonio_bruto": V, "imposto": imp["total"],
                           "patrimonio_liquido": liq, "renda_recebida": renda_acum, "total_liquido": liq + renda_acum,
                           "indice_precos": F[t], "total_real": (liq + renda_acum) / F[t]})
    if N == 0:
        V = I * U
        linhas.append({"mes": 0, "ano": 0.0, "investido": investido, "patrimonio_bruto": V, "imposto": 0.0, "patrimonio_liquido": V,
                       "renda_recebida": 0.0, "total_liquido": V, "indice_precos": 1.0, "total_real": V})
    df = pd.DataFrame(linhas)
    fim = df.iloc[-1]
    flx = fluxos + [(N, float(fim["patrimonio_liquido"]))]
    irr = tir_mensal(flx)
    anualizada = anual(irr) if irr is not None else None
    infl_media = inflacao_media_anual(q["inflacao"], N)
    rend_liq = float(fim["total_liquido"] - investido)
    rend_bruto = float(fim["patrimonio_bruto"] + fim["renda_recebida"] - investido)
    resumo = {
        "meses": N, "total_investido": float(investido), "patrimonio_bruto": float(fim["patrimonio_bruto"]), "imposto": float(fim["imposto"]),
        "patrimonio_liquido": float(fim["patrimonio_liquido"]), "renda_recebida": float(fim["renda_recebida"]),
        "total_liquido": float(fim["total_liquido"]), "rendimentos_brutos": rend_bruto, "rendimentos_liquidos": rend_liq,
        "rentabilidade_acumulada": (float(fim["total_liquido"]) / investido - 1.0) if investido > 0 else None,
        "rentabilidade_anualizada": anualizada,
        "valor_real": float(fim["total_real"]), "inflacao_media_aa": infl_media,
        "rentabilidade_real_anualizada": fisher(anualizada, infl_media) if anualizada is not None else None,
        "indice_final": float(I), "unidades": float(U),
    }
    return {"df": df, "resumo": resumo, "params": q}


def tabela_anual(df: pd.DataFrame) -> pd.DataFrame:
    """Evolução anual: o último mês de cada ano (e o mês final, se o prazo não for múltiplo de 12)."""
    if df.empty:
        return df
    m = df["mes"]
    sel = df[(m % 12 == 0) | (m == m.max())].copy()
    sel["ano"] = (sel["mes"] / 12.0).round(2)
    return sel.reset_index(drop=True)


# =============================================================================== resolver aporte, prazo e simulações de objetivo
def _valor_alvo(res: dict, real: bool) -> float:
    r = res["resumo"]
    return r["valor_real"] if real else r["total_liquido"]


def aporte_necessario(meta: float, p: dict, real: bool = False, maximo: float = 1e9) -> dict:
    """Menor aporte (na frequência de p) que leva o total líquido (ou real) à meta no prazo. Bissecção sobre projetar().
    Devolve {'aporte', 'ja_atinge', 'viavel', 'total'}; 'ja_atinge' quando o aporte zero já basta."""
    base = dict(p)
    base["aporte"] = 0.0
    sem = projetar(base, detalhado=False)
    if _valor_alvo(sem, real) >= meta:
        return {"aporte": 0.0, "ja_atinge": True, "viavel": True, "total": _valor_alvo(sem, real)}
    lo, hi = 0.0, max(float(p.get("aporte") or 0) * 2, 100.0)
    while _valor_alvo(projetar({**base, "aporte": hi}, detalhado=False), real) < meta:
        hi *= 2
        if hi > maximo:
            return {"aporte": None, "ja_atinge": False, "viavel": False, "total": None}
    for _ in range(60):
        mid = (lo + hi) / 2
        if _valor_alvo(projetar({**base, "aporte": mid}, detalhado=False), real) >= meta:
            hi = mid
        else:
            lo = mid
        if hi - lo < 0.0005:
            break
    tot = _valor_alvo(projetar({**base, "aporte": hi}, detalhado=False), real)
    return {"aporte": hi, "ja_atinge": False, "viavel": True, "total": tot}


def prazo_para_meta(meta: float, p: dict, real: bool = False, max_meses: int = 1200) -> dict:
    """Primeiro mês em que o total líquido (ou real) atinge a meta com as premissas dadas; None se não atingir em `max_meses`."""
    res = projetar({**p, "meses": max_meses})
    col = "total_real" if real else "total_liquido"
    ok = res["df"][res["df"][col] >= meta]
    if ok.empty:
        return {"meses": None, "anos": None, "atinge": False, "valor_final": float(res["df"][col].iloc[-1])}
    m = int(ok.iloc[0]["mes"])
    return {"meses": m, "anos": m / 12.0, "atinge": True, "valor_final": float(ok.iloc[0][col])}


def aporte_formula_fechada(meta: float, inicial: float, meses: int, taxa_aa: float, momento: str = "fim") -> float:
    """Aporte mensal sem imposto nem inflação (anuidade): PMT = (meta − inicial·(1+i)^n) · i / ((1+i)^n − 1); início do mês divide por (1+i)."""
    i = mensal(taxa_aa)
    if meses <= 0:
        return float("nan")
    if abs(i) < 1e-15:
        return (meta - inicial) / meses
    pmt = (meta - inicial * (1 + i) ** meses) * i / ((1 + i) ** meses - 1)
    return pmt / (1 + i) if momento == "inicio" else pmt


def valor_futuro_formula(inicial: float, aporte: float, meses: int, taxa_aa: float, momento: str = "fim") -> float:
    """Valor futuro de referência (anuidade): inicial·(1+i)^n + aporte·((1+i)^n − 1)/i, ×(1+i) se o aporte for no início do mês."""
    i = mensal(taxa_aa)
    if abs(i) < 1e-15:
        return inicial + aporte * meses
    a = aporte * ((1 + i) ** meses - 1) / i
    return inicial * (1 + i) ** meses + (a * (1 + i) if momento == "inicio" else a)


# =============================================================================== Monte Carlo (classes voláteis)
def monte_carlo(p: dict, vol_aa: float, n: int = 2000, semente: int = 42, meta: float | None = None, aliquota: float = 0.0) -> dict:
    """Distribuição do patrimônio final com retornos mensais lognormais e volatilidade `vol_aa`; o retorno esperado de cada mês é o da taxa de p
    (o valor médio dos caminhos acompanha a projeção determinística). Semente fixa: mesmo resultado a cada execução. Imposto: `aliquota` sobre o ganho.
    Devolve percentis (P10, P50, P90), probabilidade de terminar abaixo do investido e abaixo de metade dele, queda máxima típica e (opcional) de bater a meta."""
    q = _normalizar(p)
    N = q["meses"]
    if N <= 0 or n <= 0:
        return {"ok": False, "motivo": "prazo ou número de simulações inválidos"}
    rng = np.random.default_rng(semente)
    taxa = liquida_de_custo(q["taxa_aa"], q["custo_aa"]) if q["custo_aa"] else q["taxa_aa"]
    m_esp = mensal(taxa)
    sig = vol_aa / math.sqrt(12.0)
    mu = math.log(1.0 + m_esp) - sig ** 2 / 2.0
    z = rng.standard_normal((n, N))
    ret = np.exp(mu + sig * z)
    V = np.full(n, float(q["inicial"]))
    investido = float(q["inicial"])
    pico = V.copy()
    mdd = np.zeros(n)
    for t in range(1, N + 1):
        a_ini = aporte_no_mes(q["aporte"], q["freq"], t, "inicio") if q["momento"] == "inicio" else 0.0
        V = (V + a_ini) * ret[:, t - 1]
        investido += a_ini
        if q["momento"] == "fim":
            a_fim = aporte_no_mes(q["aporte"], q["freq"], t, "fim")
            V = V + a_fim
            investido += a_fim
        pico = np.maximum(pico, V)
        mdd = np.minimum(mdd, np.where(pico > 0, V / pico - 1.0, 0.0))
    final = V - np.maximum(V - investido, 0.0) * aliquota
    pct = np.percentile(final, [10, 50, 90])
    out = {"ok": True, "n": n, "semente": semente, "vol_aa": vol_aa, "investido": investido, "p10": float(pct[0]), "p50": float(pct[1]), "p90": float(pct[2]),
           "media": float(final.mean()), "prob_abaixo_investido": float((final < investido).mean()),
           "prob_perda_metade": float((final < investido * 0.5).mean()), "queda_maxima_mediana": float(np.median(mdd)),
           "queda_maxima_p10": float(np.percentile(mdd, 10))}
    if meta is not None:
        out["prob_meta"] = float((final >= meta).mean())
    return out


# =============================================================================== premissas por classe
CENARIOS = ("conservador", "moderado", "otimista")
NOMES_CENARIO = {"conservador": "Conservador", "moderado": "Moderado", "otimista": "Otimista"}

# Pontos de partida por classe. SÃO HIPÓTESES de planejamento (retorno real = acima da inflação do cenário; yield = % do valor distribuído
# por ano), editáveis na tela; não são dados de mercado nem previsão. Ordem: conservador, moderado, otimista.
PREMISSAS_CLASSE = {
    "acao": {"nome": "Ações", "val_real": (-0.02, 0.03, 0.07), "dy": (0.04, 0.05, 0.06), "cresc_dist_real": (-0.03, 0.0, 0.02), "vol": 0.25,
             "ir": "ganho_15", "custo_aa": 0.0, "ir_dist": 0.0,
             "notas": "Valorização (acima da inflação) e dividendos separados. Dividendos variam com o lucro: o cenário conservador os reduz em termos reais.",
             "riscos": "Quedas fortes de preço, cortes de dividendos e prejuízo de empresas específicas."},
    "fii": {"nome": "FIIs", "val_real": (-0.03, 0.0, 0.02), "dy": (0.08, 0.09, 0.10), "cresc_dist_real": (-0.03, 0.0, 0.01), "vol": 0.15,
            "ir": "ganho_20", "custo_aa": 0.0, "ir_dist": 0.0,
            "notas": "Cotas tendem a acompanhar o valor patrimonial; o grosso do retorno vem das distribuições mensais (isentas para pessoa física que cumpre as regras), que podem cair com vacância e inadimplência.",
            "riscos": "Vacância, inadimplência, juros altos pressionando as cotas e fundos de papel com risco de crédito."},
    "etf": {"nome": "ETFs", "val_real": (-0.01, 0.03, 0.06), "dy": (0.0, 0.01, 0.02), "cresc_dist_real": (-0.02, 0.0, 0.01), "vol": 0.20,
            "ir": "ganho_15", "custo_aa": 0.003, "ir_dist": 0.0,
            "notas": "Acompanha um índice; a taxa de administração (padrão 0,30% a.a., edite) já sai do retorno. A maioria dos ETFs acumula os proventos no preço.",
            "riscos": "Risco do índice acompanhado, erro de rastreamento e, em ETFs do exterior, câmbio."},
    "cripto": {"nome": "Criptoativos", "val_real": (-0.30, 0.05, 0.35), "dy": (0.0, 0.0, 0.0), "cresc_dist_real": (0.0, 0.0, 0.0), "vol": 0.70,
               "ir": "cripto", "custo_aa": 0.0, "ir_dist": 0.0,
               "notas": "Cenários muito abertos (retorno real de −30% a +35% ao ano). A volatilidade alta é parte do resultado: veja o Monte Carlo.",
               "riscos": "Perda de 50% ou mais em poucos meses, falha de exchange, regulação e golpes. Pode perder todo o valor."},
    "fundo": {"nome": "Fundos de investimento", "val_real": (0.0, 0.03, 0.06), "dy": (0.0, 0.0, 0.0), "cresc_dist_real": (0.0, 0.0, 0.0), "vol": 0.12,
              "ir": "fundo_lp", "custo_aa": 0.015, "ir_dist": 0.0,
              "notas": "Retorno bruto antes da taxa de administração (padrão 1,50% a.a., edite). O IR do longo prazo (15%) é aproximado pelo resgate.",
              "riscos": "Gestão abaixo do benchmark, taxas de performance, resgate com prazo e risco de crédito do portfólio."},
    "outros": {"nome": "Outros", "val_real": (-0.02, 0.02, 0.05), "dy": (0.0, 0.0, 0.0), "cresc_dist_real": (0.0, 0.0, 0.0), "vol": 0.15,
               "ir": "ganho_15", "custo_aa": 0.0, "ir_dist": 0.0, "notas": "Classe genérica: edite todas as premissas.", "riscos": "Depende do ativo."},
}
CLASSES_SIM = {**{k: v["nome"] for k, v in PREMISSAS_CLASSE.items()}, "renda_fixa": "Renda fixa"}

INDEXADORES_RF = {
    "cdi_pct": "% do CDI", "selic": "Tesouro Selic (Selic + custódia)", "ipca_mais": "IPCA + taxa fixa", "pre": "Prefixado (taxa fixa)",
    "cdi_mais": "CDI + taxa",
}
TIPOS_RF = {"cdb": "CDB / LC / LF (IR regressivo)", "lci": "LCI / LCA (isento)", "tesouro": "Tesouro Direto (IR regressivo, custódia 0,20%)"}
CUSTODIA_TESOURO = 0.0020
DIFERENCA_CDI_SELIC = 0.0010


def macro_cenarios(cdi: float | None = None, ipca: float | None = None) -> dict:
    """CDI e IPCA (a.a., fração) de cada cenário. O moderado usa os valores de hoje (Banco Central) quando informados; o conservador tem juros
    2,0 p.p. menores e inflação 1,5 p.p. maior; o otimista, juros 1,0 p.p. maiores e inflação 1,0 p.p. menor. Sem dado, usa pontos de partida editáveis
    (CDI 10,5%, IPCA 4,5%) e sinaliza em 'origem'."""
    origem = "valores de hoje do Banco Central" if (cdi is not None and ipca is not None) else "pontos de partida editáveis (sem consulta ao Banco Central)"
    c = cdi if cdi is not None else 0.105
    i = ipca if ipca is not None else 0.045
    return {"conservador": {"cdi": max(c - 0.02, 0.0), "ipca": i + 0.015}, "moderado": {"cdi": c, "ipca": i}, "otimista": {"cdi": c + 0.01, "ipca": max(i - 0.01, 0.0)},
            "origem": origem}


def premissas_classe(classe: str, cenario: str, macro: dict, rf_cfg: dict | None = None, ajustes: dict | None = None) -> dict:
    """Parâmetros de projetar() para uma classe e um cenário. Renda fixa: `rf_cfg` = {'indexador', 'taxa' (fração ou % do CDI como fração, ex. 1.10),
    'tipo_rf' ('cdb' | 'lci' | 'tesouro')}. `ajustes` sobrescreve qualquer campo (premissas personalizadas). Devolve também 'rotulos' com a origem de cada premissa."""
    if cenario not in CENARIOS:
        raise ValueError(f"cenário desconhecido: {cenario}")
    k = CENARIOS.index(cenario)
    m = macro[cenario]
    infl = m["ipca"]
    out: dict = {"inflacao": infl, "cenario": cenario, "classe": classe}
    if classe == "renda_fixa":
        cfg = {"indexador": "cdi_pct", "taxa": 1.0, "tipo_rf": "cdb", **(rf_cfg or {})}
        ind, taxa, tp = cfg["indexador"], float(cfg["taxa"]), cfg["tipo_rf"]
        cdi = m["cdi"]
        if ind == "cdi_pct":
            bruta = cdi * taxa
        elif ind == "cdi_mais":
            bruta = cdi + taxa
        elif ind == "selic":
            bruta = cdi + DIFERENCA_CDI_SELIC
        elif ind == "ipca_mais":
            bruta = nominal_de_real(taxa, infl)
        elif ind == "pre":
            bruta = taxa
        else:
            raise ValueError(f"indexador desconhecido: {ind}")
        custo = CUSTODIA_TESOURO if (tp == "tesouro" or ind == "selic") else 0.0
        tipo_chave = {"cdb": "cdb", "lci": "lci", "tesouro": "tesouro_selic" if ind == "selic" else "tesouro_ipca"}[tp]
        out.update({"taxa_aa": bruta, "dy_aa": 0.0, "custo_aa": custo, "ir": "rf" if tp != "lci" else "rf_isento", "tipo_rf": tipo_chave, "vol": 0.02,
                    "nome": CLASSES_SIM["renda_fixa"], "indexador": ind, "reinvestir": True,
                    "rotulos": {"taxa": f"{INDEXADORES_RF[ind]} no cenário {NOMES_CENARIO[cenario]}: CDI {cdi:.2%}, IPCA {infl:.2%} ({macro.get('origem', '')})"},
                    "notas": "Rendimento bruto pela taxa contratada e pelo cenário de CDI/IPCA; IR regressivo lote a lote. Marcação a mercado antes do vencimento não é modelada.",
                    "riscos": "Crédito do emissor (acima do limite do FGC), liquidez e, em prefixados e IPCA+, oscilação de preço se vender antes do vencimento."})
    else:
        if classe not in PREMISSAS_CLASSE:
            raise ValueError(f"classe sem premissas: {classe}")
        P = PREMISSAS_CLASSE[classe]
        gp = nominal_de_real(P["val_real"][k], infl)
        out.update({"taxa_aa": gp, "dy_aa": P["dy"][k], "cresc_dist_aa": nominal_de_real(P["cresc_dist_real"][k], infl), "custo_aa": P["custo_aa"],
                    "ir": P["ir"], "ir_dist": P["ir_dist"], "vol": P["vol"], "nome": P["nome"], "reinvestir": True, "notas": P["notas"], "riscos": P["riscos"],
                    "rotulos": {"taxa": f"Valorização real de {P['val_real'][k]:+.1%} ao ano sobre a inflação do cenário ({infl:.2%}) — hipótese",
                                "dy": f"Yield de distribuições de {P['dy'][k]:.1%} ao ano — hipótese"}})
    if ajustes:
        out.update({a: b for a, b in ajustes.items() if b is not None})
    return out


def simular_classe(classe: str, cenario: str, macro: dict, base: dict, rf_cfg: dict | None = None, ajustes: dict | None = None, detalhado: bool = True) -> dict:
    """projetar() com as premissas da classe no cenário; `base` traz inicial, aporte, freq, momento, meses etc."""
    pr = premissas_classe(classe, cenario, macro, rf_cfg, ajustes)
    params = {**base, **{k: v for k, v in pr.items() if k in ("taxa_aa", "dy_aa", "cresc_dist_aa", "custo_aa", "ir", "ir_dist", "tipo_rf", "inflacao", "reinvestir")}}
    if ajustes:
        params.update({k: v for k, v in ajustes.items() if v is not None and k in ("reinvestir", "aliquota", "custo_aporte", "haircut_saida")})
    res = projetar(params, detalhado=detalhado)
    res["premissas"] = pr
    return res


def comparar_cenarios_classe(classe: str, macro: dict, base: dict, rf_cfg: dict | None = None, ajustes_por_cenario: dict | None = None) -> dict:
    """Roda os três cenários da classe. Devolve {cenario: resultado} e as diferenças contra o moderado."""
    out = {}
    for c in CENARIOS:
        out[c] = simular_classe(classe, c, macro, base, rf_cfg, (ajustes_por_cenario or {}).get(c))
    mod = out["moderado"]["resumo"]["total_liquido"]
    for c in CENARIOS:
        r = out[c]["resumo"]
        r["dif_vs_moderado"] = r["total_liquido"] - mod
        r["dif_vs_moderado_pct"] = (r["total_liquido"] / mod - 1.0) if mod else None
    return out


# =============================================================================== aposentadoria
def valor_presente_anuidade_real(saque_real: float, meses: int, taxa_real_aa: float, momento: str = "inicio") -> float:
    """Patrimônio (em termos reais) para sustentar `meses` saques reais mensais de `saque_real` com retorno real `taxa_real_aa`:
    PV = saque · (1 − (1 + r)^−n)/r (fim do mês) × (1 + r) se o saque for no início do mês."""
    r = mensal(taxa_real_aa)
    if meses <= 0:
        return 0.0
    if abs(r) < 1e-15:
        return saque_real * meses
    pv = saque_real * (1 - (1 + r) ** (-meses)) / r
    return pv * (1 + r) if momento == "inicio" else pv


def saque_sustentavel_real(patrimonio_real: float, meses: int, taxa_real_aa: float, momento: str = "inicio") -> float:
    """Inverso de valor_presente_anuidade_real: saque real mensal que esgota o patrimônio em `meses`."""
    fator = valor_presente_anuidade_real(1.0, meses, taxa_real_aa, momento)
    return patrimonio_real / fator if fator > 0 else 0.0


def decumular(patrimonio: float, saque0: float, taxa_aa: float, inflacao, meses: int, momento: str = "inicio", aliquota_saque: float = 0.0) -> dict:
    """Fase de saques: a cada mês retira `saque0` corrigido pela inflação (líquido desejado; o bruto é saque/(1 − aliquota_saque)) e o saldo rende a taxa
    mensal. Devolve a tabela e o mês em que o patrimônio acaba (None se durar todo o prazo)."""
    F = fatores_inflacao(inflacao, meses)
    i = mensal(taxa_aa)
    W = patrimonio
    linhas = [{"mes": 0, "patrimonio": W, "saque_liquido": 0.0, "patrimonio_real": W}]
    esgotou = None
    for t in range(1, meses + 1):
        s = saque0 * F[t - 1] / (1.0 - aliquota_saque)
        if momento == "inicio":
            if W < s:
                esgotou = t
                retirado = max(W, 0.0)
                W = 0.0
                linhas.append({"mes": t, "patrimonio": 0.0, "saque_liquido": retirado * (1 - aliquota_saque), "patrimonio_real": 0.0})
                break
            W -= s
            W *= 1.0 + i
        else:
            W *= 1.0 + i
            if W < s:
                esgotou = t
                retirado = max(W, 0.0)
                W = 0.0
                linhas.append({"mes": t, "patrimonio": 0.0, "saque_liquido": retirado * (1 - aliquota_saque), "patrimonio_real": 0.0})
                break
            W -= s
        linhas.append({"mes": t, "patrimonio": W, "saque_liquido": s * (1 - aliquota_saque), "patrimonio_real": W / F[t]})
    return {"df": pd.DataFrame(linhas), "esgotou_no_mes": esgotou, "patrimonio_final": W}


def aposentadoria(p: dict) -> dict:
    """Planejamento de aposentadoria.
    Entradas (frações a.a. e valores de hoje): patrimonio_atual, idade_atual, idade_apos, idade_fim (expectativa de duração: até que idade o
    patrimônio precisa durar), aporte, freq, renda_desejada (líquida mensal em R$ de hoje), inflacao, taxa_acum_aa e taxa_apos_aa (nominais brutas),
    custo_aa, ir/tipo_rf (fase de acúmulo), aliquota_saque, reajuste_aporte, extras.
    Saídas: patrimônio necessário (real e nominal), projeção na aposentadoria, lacuna, aporte necessário, idade estimada de alcance, renda possível,
    sustentabilidade dos saques (idade de esgotamento) e cenários de insuficiência."""
    q = {"patrimonio_atual": 0.0, "idade_atual": 30, "idade_apos": 60, "idade_fim": 90, "aporte": 0.0, "freq": "mensal", "momento": "fim",
         "renda_desejada": 0.0, "inflacao": 0.045, "taxa_acum_aa": 0.10, "taxa_apos_aa": 0.08, "custo_aa": 0.0, "ir": "isento", "tipo_rf": "cdb",
         "aliquota": None, "aliquota_saque": 0.0, "reajuste_aporte": "inflacao", "extras": [], "dy_aa": 0.0, "momento_saque": "inicio"}
    q.update({k: v for k, v in p.items() if v is not None or k in ("aliquota",)})
    anos_acum = max(q["idade_apos"] - q["idade_atual"], 0)
    meses_acum = int(round(anos_acum * 12))
    meses_saque = int(round(max(q["idade_fim"] - q["idade_apos"], 0) * 12))
    base = {"inicial": q["patrimonio_atual"], "aporte": q["aporte"], "freq": q["freq"], "momento": q["momento"], "meses": meses_acum, "taxa_aa": q["taxa_acum_aa"],
            "dy_aa": q["dy_aa"], "custo_aa": q["custo_aa"], "inflacao": q["inflacao"], "reajuste_aporte": q["reajuste_aporte"], "extras": q["extras"], "ir": q["ir"],
            "tipo_rf": q["tipo_rf"], "aliquota": q["aliquota"]}
    proj = projetar(base)
    F = fatores_inflacao(q["inflacao"], meses_acum + meses_saque)
    taxa_ret_liq = liquida_de_custo(q["taxa_apos_aa"], q["custo_aa"]) if q["custo_aa"] else q["taxa_apos_aa"]
    r_real_ret = fisher(taxa_ret_liq, q["inflacao"] if np.isscalar(q["inflacao"]) else float(np.mean(q["inflacao"])))
    saque_bruto_real = q["renda_desejada"] / (1.0 - q["aliquota_saque"])
    necessario_real = valor_presente_anuidade_real(saque_bruto_real, meses_saque, r_real_ret, q["momento_saque"])
    necessario_nominal = necessario_real * F[meses_acum]
    pat_nom = proj["resumo"]["total_liquido"]
    pat_real = proj["resumo"]["valor_real"]
    lacuna_real = necessario_real - pat_real
    # aporte necessário para fechar o gap (em termos reais, mesmo critério do necessário)
    ap = aporte_necessario(necessario_real, base, real=True) if q["renda_desejada"] > 0 and meses_acum > 0 else {"aporte": None, "ja_atinge": pat_real >= necessario_real, "viavel": True}
    alvo = prazo_para_meta(necessario_real, {**base, "meses": 1200}, real=True) if q["renda_desejada"] > 0 else {"meses": None, "atinge": False, "anos": None}
    renda_possivel_real = saque_sustentavel_real(pat_real, meses_saque, r_real_ret, q["momento_saque"]) * (1.0 - q["aliquota_saque"])
    # sustentabilidade: saques desejados (corrigidos) contra o patrimônio projetado
    dec = decumular(pat_nom, q["renda_desejada"] * F[meses_acum], taxa_ret_liq, [float(q["inflacao"])] * 1 if np.isscalar(q["inflacao"]) else q["inflacao"],
                    meses_saque, q["momento_saque"], q["aliquota_saque"]) if q["renda_desejada"] > 0 else {"df": pd.DataFrame(), "esgotou_no_mes": None, "patrimonio_final": pat_nom}
    idade_esgota = (q["idade_apos"] + dec["esgotou_no_mes"] / 12.0) if dec["esgotou_no_mes"] else None
    retirada_inicial = (q["renda_desejada"] * 12.0 / (1.0 - q["aliquota_saque"])) / pat_real if pat_real > 0 else None
    perpetuo = r_real_ret > 0 and retirada_inicial is not None and retirada_inicial <= r_real_ret
    return {"projecao": proj, "necessario_real": necessario_real, "necessario_nominal": necessario_nominal, "patrimonio_real": pat_real, "patrimonio_nominal": pat_nom,
            "lacuna_real": lacuna_real, "suficiente": lacuna_real <= 0, "aporte_necessario": ap, "alcance": alvo, "idade_alcance": (q["idade_atual"] + alvo["anos"]) if alvo.get("anos") is not None else None,
            "renda_possivel_real": renda_possivel_real, "renda_possivel_nominal": renda_possivel_real * F[meses_acum], "decumulacao": dec, "idade_esgotamento": idade_esgota,
            "dura_ate_idade_fim": dec["esgotou_no_mes"] is None, "taxa_retirada_inicial": retirada_inicial, "retorno_real_aposentadoria": r_real_ret, "retirada_perpetua": perpetuo,
            "meses_acumulacao": meses_acum, "meses_saque": meses_saque, "premissas": q}


def cenarios_aposentadoria(p: dict, deltas_pp: tuple = (-3.0, 0.0, 2.0), inflacoes: tuple | None = None) -> list[dict]:
    """Insuficiência de patrimônio: repete a aposentadoria com retorno menor/igual/maior (em p.p. nas duas fases) e, opcionalmente, outras inflações.
    Cada item: rótulo, idade de esgotamento, suficiente, lacuna real."""
    out = []
    infl_lista = inflacoes or (p.get("inflacao", 0.045),)
    for infl in infl_lista:
        for d in deltas_pp:
            pp = dict(p)
            pp["taxa_acum_aa"] = float(p.get("taxa_acum_aa", 0.10)) + d / 100.0
            pp["taxa_apos_aa"] = float(p.get("taxa_apos_aa", 0.08)) + d / 100.0
            pp["inflacao"] = infl
            r = aposentadoria(pp)
            out.append({"rotulo": f"retorno {d:+.0f} p.p. · inflação {infl:.1%}", "delta_pp": d, "inflacao": infl, "suficiente": r["suficiente"], "idade_esgotamento": r["idade_esgotamento"],
                        "lacuna_real": r["lacuna_real"], "necessario_real": r["necessario_real"], "patrimonio_real": r["patrimonio_real"], "renda_possivel_real": r["renda_possivel_real"]})
    return out


# =============================================================================== renda passiva
FONTES_RENDA = {"acao": "Dividendos de ações", "fii": "Rendimentos de FIIs", "fundo": "Distribuições de fundos", "renda_fixa": "Juros de renda fixa",
                "etf": "ETFs distribuidores", "outros": "Outras fontes"}


def renda_passiva(fontes: list[dict], anos: int = 10, inflacao: float = 0.045, reinvestir: bool = True, corte_dist_pct: float = 0.0, corte_a_partir_ano: int = 1,
                  renda_desejada: float | None = None) -> dict:
    """Projeta a renda de várias fontes. Cada fonte: {'nome','classe','patrimonio','yield_aa' (recorrente, % do valor/ano),'cresc_dist_aa' (nominal; None = inflação),
    'valorizacao_aa' (nominal do preço; 0 = só distribuições),'aporte_mensal','ir_dist' (fração),'reinvestir' (opcional),'extras' [{'mes','valor'}] (pagamentos extraordinários)}.
    Renda recorrente = yield sobre o valor atual (cresce com cresc_dist_aa, nunca constante por suposição); extraordinários entram só no mês informado
    e não contam para yield nem para patrimônio necessário. `corte_dist_pct` reduz as distribuições a partir do ano `corte_a_partir_ano` (cenário de queda)."""
    N = int(anos * 12)
    F = fatores_inflacao(inflacao, N)
    estado = []
    for f in fontes:
        gd = f.get("cresc_dist_aa")
        estado.append({"f": f, "V": float(f.get("patrimonio") or 0.0), "y": float(f.get("yield_aa") or 0.0), "gd": float(inflacao if gd is None else gd),
                       "gp": float(f.get("valorizacao_aa") or 0.0), "ap": float(f.get("aporte_mensal") or 0.0), "ir": float(f.get("ir_dist") or 0.0),
                       "re": bool(f.get("reinvestir", reinvestir)), "caixa": 0.0, "extras": {int(e["mes"]): float(e["valor"]) for e in f.get("extras", [])}})
    linhas = []
    for t in range(1, N + 1):
        rec = ext = 0.0
        cortes = (1.0 - corte_dist_pct / 100.0) if (corte_dist_pct and (t - 1) // 12 + 1 >= corte_a_partir_ano) else 1.0
        for s in estado:
            s["V"] *= 1.0 + mensal(s["gp"])
            # yield cresce (ou cai) em relação ao preço: distribuições crescem a gd, o valor a gp
            fator = ((1.0 + s["gd"]) / (1.0 + s["gp"])) ** (t / 12.0)
            d = s["V"] * s["y"] / 12.0 * fator * cortes * (1.0 - s["ir"])
            rec += d
            if s["re"]:
                s["V"] += d
            else:
                s["caixa"] += d
            s["V"] += s["ap"]
            e = s["extras"].get(t, 0.0)
            ext += e
        patr = sum(s["V"] for s in estado)
        linhas.append({"mes": t, "ano": t / 12.0, "renda_recorrente": rec, "renda_extraordinaria": ext, "patrimonio": patr, "renda_recebida_acum": sum(s["caixa"] for s in estado),
                       "renda_recorrente_real": rec / F[t]})
    df = pd.DataFrame(linhas)
    por_ano = df.groupby(np.ceil(df["mes"] / 12).astype(int)).agg(renda_recorrente=("renda_recorrente", "sum"), renda_extraordinaria=("renda_extraordinaria", "sum"),
                                                                  patrimonio=("patrimonio", "last"), renda_real=("renda_recorrente_real", "sum")).reset_index(names="ano")
    pat0 = sum(float(f.get("patrimonio") or 0.0) for f in fontes)
    ren0 = sum(float(f.get("patrimonio") or 0.0) * float(f.get("yield_aa") or 0.0) * (1.0 - float(f.get("ir_dist") or 0.0)) for f in fontes)
    yield_medio = ren0 / pat0 if pat0 > 0 else None
    necessario = None
    if renda_desejada and yield_medio and yield_medio > 0:
        necessario = renda_desejada * 12.0 / yield_medio
    por_fonte = [{"nome": f.get("nome") or FONTES_RENDA.get(f.get("classe"), "Fonte"), "classe": f.get("classe"), "patrimonio": float(f.get("patrimonio") or 0.0),
                  "yield_aa": float(f.get("yield_aa") or 0.0), "renda_mensal": float(f.get("patrimonio") or 0.0) * float(f.get("yield_aa") or 0.0) * (1 - float(f.get("ir_dist") or 0)) / 12.0}
                 for f in fontes]
    return {"df": df, "por_ano": por_ano, "renda_mensal_inicial": ren0 / 12.0, "renda_anual_inicial": ren0, "patrimonio_inicial": pat0, "yield_medio": yield_medio,
            "patrimonio_necessario": necessario, "renda_mensal_final": float(df["renda_recorrente"].iloc[-1]) if len(df) else 0.0,
            "renda_mensal_final_real": float(df["renda_recorrente_real"].iloc[-1]) if len(df) else 0.0, "patrimonio_final": float(df["patrimonio"].iloc[-1]) if len(df) else pat0,
            "extraordinario_total": float(df["renda_extraordinaria"].sum()) if len(df) else 0.0, "por_fonte": por_fonte, "reinvestir": reinvestir}


def patrimonio_para_renda(renda_mensal: float, yield_aa: float, ir_dist: float = 0.0) -> float | None:
    """Patrimônio necessário para uma renda mensal líquida com yield recorrente informado: renda·12 / (yield·(1 − ir))."""
    y = yield_aa * (1.0 - ir_dist)
    return renda_mensal * 12.0 / y if y > 0 else None


# =============================================================================== metas
TIPOS_META = {"reserva": "Reserva de emergência", "imovel": "Compra de imóvel", "veiculo": "Compra de veículo", "aposentadoria": "Aposentadoria",
              "independencia": "Independência financeira", "educacao": "Educação", "viagem": "Viagem", "outra": "Outra meta"}


def valor_reserva(despesa_mensal: float, meses: float = 6.0) -> float:
    """Reserva de emergência de referência: despesa mensal × número de meses (convenção usual de 3 a 12; escolha conforme a estabilidade da renda)."""
    return despesa_mensal * meses


def valor_independencia(despesa_mensal: float, taxa_retirada: float = 0.04) -> float:
    """Patrimônio de independência financeira: despesa anual / taxa de retirada. A 'regra dos 4%' (25×) é uma convenção histórica dos EUA, não uma garantia."""
    return despesa_mensal * 12.0 / taxa_retirada if taxa_retirada > 0 else float("nan")


def meses_entre(d0: date, d1: date) -> int:
    return max((d1.year - d0.year) * 12 + (d1.month - d0.month) - (1 if d1.day < d0.day else 0), 0)


def nova_meta(nome: str, tipo: str, alvo: float, prazo: date, acumulado: float = 0.0, aporte_mensal: float = 0.0, taxa_aa: float = 0.08,
              inflacao: float = 0.045, corrigir_inflacao: bool = True, criada: date | None = None, id_: str | None = None) -> dict:
    """Registro de meta (serializável em JSON). `alvo` em reais de hoje; `taxa_aa` = rentabilidade líquida estimada do dinheiro da meta."""
    criada = criada or date.today()
    return {"id": id_ or f"m{criada.strftime('%Y%m%d')}{abs(hash((nome, alvo, prazo.isoformat()))) % 10_000:04d}", "nome": nome, "tipo": tipo if tipo in TIPOS_META else "outra",
            "alvo": float(alvo), "prazo": prazo.isoformat(), "acumulado": float(acumulado), "aporte_mensal": float(aporte_mensal), "taxa_aa": float(taxa_aa),
            "inflacao": float(inflacao), "corrigir_inflacao": bool(corrigir_inflacao), "criada": criada.isoformat(),
            "historico": [{"data": criada.isoformat(), "valor": float(acumulado)}]}


def registrar_progresso(meta: dict, valor: float, quando: date | None = None) -> dict:
    """Atualiza o valor acumulado e guarda o ponto no histórico (um por dia: o último valor do dia vale)."""
    quando = quando or date.today()
    h = [x for x in meta.get("historico", []) if x["data"] != quando.isoformat()]
    h.append({"data": quando.isoformat(), "valor": float(valor)})
    h.sort(key=lambda x: x["data"])
    return {**meta, "acumulado": float(valor), "historico": h}


def avaliar_meta(meta: dict, hoje: date | None = None) -> dict:
    """Situação da meta: percentual atingido, meses restantes, valor nominal a atingir (corrigido pela inflação até o prazo, se marcado),
    projeção do acumulado com o aporte planejado, aporte mensal necessário e status."""
    hoje = hoje or date.today()
    prazo = date.fromisoformat(meta["prazo"])
    n = meses_entre(hoje, prazo)
    alvo_hoje = float(meta["alvo"])
    alvo_nom = alvo_hoje * (1.0 + meta["inflacao"]) ** (n / 12.0) if meta.get("corrigir_inflacao") else alvo_hoje
    acum = float(meta.get("acumulado") or 0.0)
    pct = acum / alvo_hoje if alvo_hoje > 0 else None
    i = mensal(meta["taxa_aa"])
    proj = valor_futuro_formula(acum, float(meta.get("aporte_mensal") or 0.0), n, meta["taxa_aa"])
    necessario = max(aporte_formula_fechada(alvo_nom, acum, n, meta["taxa_aa"]), 0.0) if n > 0 else max(alvo_nom - acum, 0.0)
    if acum >= alvo_hoje and not meta.get("corrigir_inflacao"):
        status = "atingida"
    elif acum >= alvo_nom:
        status = "atingida"
    elif n <= 0:
        status = "prazo vencido"
    elif proj >= alvo_nom:
        status = "no ritmo"
    elif proj >= 0.9 * alvo_nom:
        status = "quase no ritmo"
    else:
        status = "atrás do ritmo"
    return {"id": meta["id"], "nome": meta["nome"], "tipo": meta["tipo"], "alvo_hoje": alvo_hoje, "alvo_nominal": alvo_nom, "acumulado": acum, "pct": pct,
            "meses_restantes": n, "prazo": meta["prazo"], "aporte_planejado": float(meta.get("aporte_mensal") or 0.0), "aporte_necessario": necessario,
            "projetado_no_prazo": proj, "falta": max(alvo_nom - acum, 0.0), "status": status, "taxa_mensal": i, "historico": meta.get("historico", [])}


# =============================================================================== crises e perdas
CRISES = {
    "queda_10": {"nome": "Queda de 10%", "tipo": "queda", "valor": 10.0},
    "queda_20": {"nome": "Queda de 20%", "tipo": "queda", "valor": 20.0},
    "queda_30": {"nome": "Queda de 30%", "tipo": "queda", "valor": 30.0},
    "queda_50": {"nome": "Queda de 50%", "tipo": "queda", "valor": 50.0},
    "juros": {"nome": "Alta dos juros (+4 p.p.)", "tipo": "juros", "valor": 4.0},
    "inflacao": {"nome": "Inflação elevada (+4 p.p.)", "tipo": "inflacao", "valor": 4.0},
    "cambio": {"nome": "Desvalorização cambial (real −25% frente ao dólar)", "tipo": "cambio", "valor": 25.0},
    "dividendos": {"nome": "Redução de dividendos (−40%)", "tipo": "dividendos", "valor": 40.0},
    "liquidez": {"nome": "Perda de liquidez (deságio de 15% na saída)", "tipo": "liquidez", "valor": 15.0},
}
CLASSES_QUEDA = ("acao", "fii", "etf", "cripto", "fundo", "outros")   # onde "queda de X%" bate; renda fixa não cai por padrão


def aplicar_crise(p: dict, crise: dict, mes: int = 24, parcela_dolar: float = 0.0) -> dict:
    """Devolve novos parâmetros de projetar() com a crise embutida no mês `mes`.
    queda: choque de preço de −valor% (a recuperação, se vier, depende da taxa do cenário — nada de rebote automático);
    juros: a taxa sobe `valor` p.p. daí em diante (renda fixa pós-fixada ganha; marcação a mercado não é modelada);
    inflacao: a inflação passa a ser maior por 12 meses (reduz o valor real e, nos aportes reajustados, aumenta o esforço);
    cambio: ativos em dólar (parcela_dolar do patrimônio) sobem na moeda local; o choque é de +valor% sobre essa parcela (via choque de preço equivalente);
    dividendos: corta as distribuições em valor%; liquidez: deságio de valor% na saída (haircut)."""
    q = {**p}
    t = crise["tipo"]
    v = float(crise["valor"])
    if t == "queda":
        q["choques"] = list(q.get("choques", [])) + [{"mes": mes, "pct": -v}]
    elif t == "juros":
        q["mudancas_taxa"] = list(q.get("mudancas_taxa", [])) + [{"mes": mes, "delta_pp": v}]
    elif t == "inflacao":
        base_inf = q.get("inflacao", 0.045)
        anos = [float(base_inf)] if np.isscalar(base_inf) else [float(x) for x in base_inf]
        n_anos = max(int(math.ceil(q.get("meses", 120) / 12)), len(anos))
        anos = (anos + [anos[-1]] * n_anos)[:n_anos]
        a0 = (mes - 1) // 12
        for k in range(a0, min(a0 + 1, n_anos)):
            anos[k] = anos[k] + v / 100.0
        q["inflacao"] = anos
    elif t == "cambio":
        q["choques"] = list(q.get("choques", [])) + [{"mes": mes, "pct": v * parcela_dolar}]
    elif t == "dividendos":
        q["cortes_dist"] = list(q.get("cortes_dist", [])) + [{"mes": mes, "pct": v}]
    elif t == "liquidez":
        q["haircut_saida"] = max(q.get("haircut_saida", 0.0), v / 100.0)
    else:
        raise ValueError(f"tipo de crise desconhecido: {t}")
    return q


def crise_personalizada(nome: str, queda_pct: float = 0.0, juros_pp: float = 0.0, inflacao_pp: float = 0.0, dividendos_pct: float = 0.0,
                        liquidez_pct: float = 0.0) -> list[dict]:
    """Combina vários efeitos numa crise só (lista de crises simples aplicadas em sequência)."""
    out = []
    if queda_pct:
        out.append({"nome": nome, "tipo": "queda", "valor": float(queda_pct)})
    if juros_pp:
        out.append({"nome": nome, "tipo": "juros", "valor": float(juros_pp)})
    if inflacao_pp:
        out.append({"nome": nome, "tipo": "inflacao", "valor": float(inflacao_pp)})
    if dividendos_pct:
        out.append({"nome": nome, "tipo": "dividendos", "valor": float(dividendos_pct)})
    if liquidez_pct:
        out.append({"nome": nome, "tipo": "liquidez", "valor": float(liquidez_pct)})
    return out


def impacto_crise(p: dict, crises: dict | list, mes: int = 24, meta: float | None = None, real: bool = False, parcela_dolar: float = 0.0) -> dict:
    """Compara a projeção sem crise com a projeção com a(s) crise(s) no mês `mes`: patrimônio final, perda, queda máxima, mês de recuperação do nível
    anterior e atraso para atingir a meta (se informada)."""
    lista = [crises] if isinstance(crises, dict) else list(crises)
    base = projetar(p)
    q = dict(p)
    for c in lista:
        q = aplicar_crise(q, c, mes, parcela_dolar)
    com = projetar(q)
    b, c_ = base["resumo"], com["resumo"]
    col = "total_real" if real else "total_liquido"
    db, dc = base["df"], com["df"]
    ref_mes = max(mes - 1, 0)
    nivel_antes = float(dc[dc["mes"] == ref_mes][col].iloc[0]) if ref_mes in set(dc["mes"]) else None
    pos = dc[dc["mes"] >= mes]
    pior = float(pos[col].min()) if len(pos) else None
    queda_max = (pior / nivel_antes - 1.0) if (nivel_antes and pior is not None and nivel_antes > 0) else None
    recuperou = None
    if nivel_antes is not None:
        rec = pos[pos[col] >= nivel_antes]
        # recuperação só vale depois de ter caído abaixo do nível anterior
        abaixo = pos[pos[col] < nivel_antes]
        if not abaixo.empty:
            rec = rec[rec["mes"] > abaixo.iloc[0]["mes"]]
            recuperou = int(rec.iloc[0]["mes"]) - mes if not rec.empty else None
    atraso = None
    if meta is not None:
        a = prazo_para_meta(meta, p, real)
        b2 = prazo_para_meta(meta, q, real)
        atraso = {"sem_crise_meses": a["meses"], "com_crise_meses": b2["meses"], "atraso_meses": (b2["meses"] - a["meses"]) if (a["meses"] is not None and b2["meses"] is not None) else None}
    return {"sem_crise": b, "com_crise": c_, "df_sem": db, "df_com": dc, "delta": c_["total_liquido"] - b["total_liquido"],
            "delta_pct": (c_["total_liquido"] / b["total_liquido"] - 1.0) if b["total_liquido"] else None, "delta_real": c_["valor_real"] - b["valor_real"],
            "queda_maxima": queda_max, "meses_para_recuperar": recuperou, "atraso_meta": atraso, "mes_crise": mes, "crises": lista}


def choques_risco_de_queda(pct: float) -> dict:
    """Traduz 'queda de X%' para os choques do módulo de risco (Passo 16): bolsas e criptoativos caem X%; FIIs seguem a bolsa."""
    return {"bolsa_br": -pct, "bolsa_ext": -pct, "cripto": -pct}


def crise_na_carteira(posicoes: list[dict], choques: dict, liq: dict | None = None, nome: str = "Cenário") -> dict:
    """Aplica os choques às posições com o motor de estresse do Passo 16 (risco.simular_estresse). Devolve o resultado dele, sem alterá-lo."""
    import risco as R
    return R.simular_estresse(posicoes, choques, liq, None, nome)


# =============================================================================== inflação e poder de compra
def serie_poder_de_compra(valor_nominal: float, inflacao, anos: int) -> pd.DataFrame:
    """Ano a ano: o que um valor nominal parado compra (em R$ de hoje) e o valor nominal necessário para manter o poder de compra."""
    n = anos * 12
    F = fatores_inflacao(inflacao, n)
    linhas = [{"ano": a, "indice": F[a * 12], "valor_parado_real": valor_nominal / F[a * 12], "nominal_para_manter": valor_nominal * F[a * 12],
               "perda_poder_compra": 1.0 - 1.0 / F[a * 12]} for a in range(anos + 1)]
    return pd.DataFrame(linhas)


def rentabilidade_real_projecao(res: dict) -> dict:
    """Resumo nominal × real de uma projeção já calculada."""
    r = res["resumo"]
    return {"nominal": r["total_liquido"], "real": r["valor_real"], "perda_inflacao": r["total_liquido"] - r["valor_real"],
            "rent_nominal_aa": r["rentabilidade_anualizada"], "rent_real_aa": r["rentabilidade_real_anualizada"], "inflacao_media_aa": r["inflacao_media_aa"]}
