"""
Passo 18 · Simulação de carteira (integra o Passo 12) e simulação com dados históricos reais.

Sem Streamlit e sem rede. A carteira entra como a lista de posições que a Gestão (Passo 12) já calcula
({'id','classe','valor','custo','setor','moeda',...}); nada é comprado, vendido ou alterado.

Carteira: cada classe é um "balde" projetado com as premissas do cenário (simulador.premissas_classe). Rebalanceamento, novos aportes e
inclusão/retirada de ativos mexem nos baldes; impostos de rebalanceamento não são modelados (avisado no resultado).

Histórico: usa SÓ preços reais passados. Todas as decisões de uma estratégia no dia t usam dados até t−1 (sem olhar o futuro).
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np
import pandas as pd

import gestao as g
import renda_fixa as rf
import simulador as S

AVISO_CARTEIRA = ("Projeção hipotética com premissas por classe, não resultado garantido. Rebalanceamento não considera o imposto sobre o ganho "
                  "realizado nas vendas; classes 'caixa' e 'outros' rendem o que você informar. A volatilidade usa uma correlação média única entre as classes.")

CLASSE_PARA_SIM = {"acao": "acao", "bdr": "acao", "fii": "fii", "etf": "etf", "fundo": "fundo", "cripto": "cripto", "renda_fixa": "renda_fixa",
                   "caixa": "caixa", "outro": "outros", "outros": "outros"}
ROTULO_SIM = {**S.CLASSES_SIM, "caixa": "Caixa"}
CORRELACAO_MEDIA_PADRAO = 0.5


# =============================================================================== carteira
def baldes_da_carteira(posicoes: list[dict], dy_por_ativo: dict | None = None) -> dict:
    """Agrupa as posições por classe de simulação: {classe: {'valor','custo','ativos':[ids],'dy' (média ponderada, se houver dado)}}."""
    out: dict = {}
    for p in posicoes or []:
        v = p.get("valor")
        if v is None or not math.isfinite(float(v)) or float(v) <= 0:
            continue
        c = CLASSE_PARA_SIM.get(p.get("classe"), "outros")
        b = out.setdefault(c, {"valor": 0.0, "custo": 0.0, "ativos": [], "_dyw": 0.0, "_dyv": 0.0})
        b["valor"] += float(v)
        b["custo"] += float(p.get("custo") if p.get("custo") not in (None, 0) and math.isfinite(float(p.get("custo"))) else v)
        b["ativos"].append(p["id"])
        dy = (dy_por_ativo or {}).get(p["id"])
        if dy is not None and math.isfinite(dy):
            b["_dyw"] += float(v) * dy
            b["_dyv"] += float(v)
    for b in out.values():
        b["dy"] = (b["_dyw"] / b["_dyv"]) if b["_dyv"] > 0 else None
        b["cobertura_dy"] = (b["_dyv"] / b["valor"]) if b["valor"] > 0 else 0.0
        del b["_dyw"], b["_dyv"]
    return out


def pesos(baldes: dict) -> dict:
    tot = sum(b["valor"] for b in baldes.values())
    return {c: b["valor"] / tot for c, b in baldes.items()} if tot > 0 else {}


def vol_carteira(pesos_: dict, vols: dict, rho: float = CORRELACAO_MEDIA_PADRAO) -> float | None:
    """Volatilidade anual estimada: √(Σ wᵢ²σᵢ² + ρ Σᵢ≠ⱼ wᵢwⱼσᵢσⱼ) com correlação média ρ única. Referência de planejamento, não medida de mercado."""
    cs = [c for c in pesos_ if c in vols and pesos_[c] > 0]
    if not cs:
        return None
    var = sum((pesos_[c] * vols[c]) ** 2 for c in cs)
    var += rho * sum(pesos_[a] * pesos_[b] * vols[a] * vols[b] for a in cs for b in cs if a != b)
    return math.sqrt(max(var, 0.0))


def _premissas_balde(classe: str, cenario: str, macro: dict, rf_cfg: dict | None, ajustes: dict | None, dy: float | None) -> dict:
    if classe == "caixa":
        taxa = (ajustes or {}).get("caixa", {}).get("taxa_aa", 0.0)
        return {"taxa_aa": taxa, "dy_aa": 0.0, "cresc_dist_aa": None, "custo_aa": 0.0, "ir": "isento", "tipo_rf": "cdb", "vol": 0.01, "inflacao": macro[cenario]["ipca"],
                "nome": "Caixa", "rotulos": {"taxa": f"Caixa rende {taxa:.2%} a.a. (informado)"}}
    pr = S.premissas_classe(classe, cenario, macro, rf_cfg, (ajustes or {}).get(classe))
    if dy is not None and classe in ("acao", "fii", "etf") and not (ajustes or {}).get(classe, {}).get("dy_aa"):
        pr["dy_aa"] = float(dy)
        pr["rotulos"]["dy"] = f"Yield de {dy:.1%} ao ano calculado dos proventos reais dos últimos 12 meses da sua carteira (não é garantia de repetição)"
    return pr


def _imposto_balde(classe: str, pr: dict, valor: float, base: float, meses: int) -> float:
    ganho = max(valor - base, 0.0)
    if classe == "renda_fixa":
        if pr.get("ir") == "rf_isento":
            return 0.0
        return ganho * rf.aliquota_ir(int(meses * S.DIAS_NO_MES))
    tipo = pr.get("ir", "isento")
    a = pr.get("aliquota")
    if a is None:
        a = S.ALIQUOTA_PADRAO.get(tipo, 0.0)
    return ganho * a


def simular_carteira(baldes: dict, macro: dict, cenario: str = "moderado", aporte_mensal: float = 0.0, meses: int = 120, alocacao_aporte: dict | None = None,
                     rebalancear: str | None = None, pesos_alvo: dict | None = None, rf_cfg: dict | None = None, ajustes: dict | None = None,
                     custo_rebal: float = 0.001, reinvestir: bool = True, rho: float = CORRELACAO_MEDIA_PADRAO, nome: str = "Carteira") -> dict:
    """Projeta a carteira por classe.
    - alocacao_aporte: {classe: fração} (soma 1); padrão = pesos atuais. Aporte mensal no fim de cada mês.
    - rebalancear: None | 'trimestral' | 'semestral' | 'anual': nesses meses volta aos pesos_alvo (padrão = pesos iniciais) pagando custo_rebal sobre o volume negociado.
    - distribuições (yield) reinvestidas no próprio balde (ou acumuladas como renda se reinvestir=False).
    Devolve df mensal por classe e total, resumo (patrimônio, aportes, TIR, renda passiva, vol estimada, concentração) e as premissas usadas."""
    if not baldes:
        return {"ok": False, "motivo": "carteira sem posições com valor"}
    classes = list(baldes)
    w0 = pesos(baldes)
    alvo = pesos_alvo or w0
    soma_alvo = sum(alvo.get(c, 0.0) for c in classes)
    alvo = {c: alvo.get(c, 0.0) / soma_alvo for c in classes} if soma_alvo > 0 else w0
    aloc = alocacao_aporte or w0
    sa = sum(aloc.get(c, 0.0) for c in classes)
    aloc = {c: aloc.get(c, 0.0) / sa for c in classes} if sa > 0 else w0
    pr = {c: _premissas_balde(c, cenario, macro, rf_cfg, ajustes, baldes[c].get("dy")) for c in classes}
    F = S.fatores_inflacao(macro[cenario]["ipca"], meses)
    V = {c: baldes[c]["valor"] for c in classes}
    base = {c: min(baldes[c]["custo"], baldes[c]["valor"]) if baldes[c]["custo"] > 0 else baldes[c]["valor"] for c in classes}
    renda_cx = {c: 0.0 for c in classes}
    dist_12 = []
    freq_reb = {"trimestral": 3, "semestral": 6, "anual": 12}.get(rebalancear or "", 0)
    invest = sum(V.values())
    fluxos = [(0, -invest)]
    linhas = []
    tot_dist_mes = []
    custo_total_reb = 0.0
    for t in range(1, meses + 1):
        dist_mes = 0.0
        for c in classes:
            p = pr[c]
            taxa = S.liquida_de_custo(p["taxa_aa"], p.get("custo_aa", 0.0)) if p.get("custo_aa") else p["taxa_aa"]
            V[c] *= 1.0 + S.mensal(taxa)
            if p.get("dy_aa"):
                gd = p.get("cresc_dist_aa")
                gd = p["taxa_aa"] if gd is None else gd
                fator = ((1.0 + gd) / (1.0 + p["taxa_aa"])) ** (t / 12.0)
                d = V[c] * p["dy_aa"] / 12.0 * fator * (1.0 - p.get("ir_dist", 0.0))
                dist_mes += d
                if reinvestir:
                    V[c] += d
                    base[c] += d
                else:
                    renda_cx[c] += d
                    fluxos.append((t, d))
        tot_dist_mes.append(dist_mes)
        if aporte_mensal:
            for c in classes:
                a = aporte_mensal * aloc[c]
                V[c] += a
                base[c] += a
            invest += aporte_mensal
            fluxos.append((t, -aporte_mensal))
        if freq_reb and t % freq_reb == 0:
            tot = sum(V.values())
            giro = 0.0
            for c in classes:
                novo = tot * alvo[c]
                dif = novo - V[c]
                giro += abs(dif)
                if dif < 0 and V[c] > 0:                      # venda: reduz o custo fiscal na mesma proporção
                    base[c] *= novo / V[c]
                else:
                    base[c] += max(dif, 0.0)
                V[c] = novo
            custo = giro / 2.0 * custo_rebal
            custo_total_reb += custo
            for c in classes:
                V[c] -= custo * (V[c] / tot) if tot > 0 else 0.0
        total = sum(V.values())
        linha = {"mes": t, "ano": t / 12.0, "investido": invest, "patrimonio": total, "renda_acum": sum(renda_cx.values()), "indice_precos": F[t], "patrimonio_real": total / F[t]}
        for c in classes:
            linha[c] = V[c]
        linhas.append(linha)
    df = pd.DataFrame(linhas)
    imposto = sum(_imposto_balde(c, pr[c], V[c], base[c], meses) for c in classes)
    bruto = sum(V.values())
    renda = sum(renda_cx.values())
    liq = bruto - imposto
    fluxos.append((meses, liq))
    irr = S.tir_mensal(fluxos)
    anualizada = S.anual(irr) if irr is not None else None
    infl_media = S.inflacao_media_anual(macro[cenario]["ipca"], meses)
    w_fim = {c: V[c] / bruto for c in classes} if bruto > 0 else {}
    vols = {c: pr[c]["vol"] for c in classes}
    ult12 = tot_dist_mes[-12:] if tot_dist_mes else []
    renda_12m = float(sum(ult12)) if len(ult12) == 12 else (float(sum(ult12)) * 12.0 / len(ult12) if ult12 else 0.0)
    dist_ini = sum(baldes[c]["valor"] * (pr[c].get("dy_aa") or 0.0) * (1 - pr[c].get("ir_dist", 0.0)) for c in classes)
    return {"ok": True, "nome": nome, "cenario": cenario, "df": df, "premissas": pr, "pesos_iniciais": w0, "pesos_finais": w_fim, "pesos_alvo": alvo, "alocacao_aporte": aloc,
            "resumo": {"patrimonio_inicial": sum(b["valor"] for b in baldes.values()), "meses": meses, "total_investido": invest, "patrimonio_bruto": bruto, "imposto": imposto,
                       "patrimonio_liquido": liq, "renda_recebida": renda, "total_liquido": liq + renda, "valor_real": (liq + renda) / F[meses] if meses else liq + renda,
                       "rentabilidade_acumulada": ((liq + renda) / invest - 1.0) if invest > 0 else None, "rentabilidade_anualizada": anualizada,
                       "rentabilidade_real_anualizada": S.fisher(anualizada, infl_media) if anualizada is not None else None,
                       "renda_passiva_anual_inicial": dist_ini, "renda_passiva_mensal_final": float(tot_dist_mes[-1]) if tot_dist_mes else 0.0, "renda_passiva_anual_final": renda_12m,
                       "vol_estimada_inicial": vol_carteira(w0, vols, rho), "vol_estimada_final": vol_carteira(w_fim, vols, rho), "rho": rho,
                       "custo_rebalanceamento": custo_total_reb},
            "avisos": [AVISO_CARTEIRA] + ([f"Rebalanceamento {rebalancear}: o imposto sobre ganhos realizados nas vendas não foi descontado."] if freq_reb else [])}


def adicionar_ativo(baldes: dict, classe: str, valor: float, dy: float | None = None, nome: str = "novo ativo") -> dict:
    """Cópia dos baldes com um ativo a mais (valor à vista; custo = valor)."""
    novo = {c: {**b, "ativos": list(b["ativos"])} for c, b in baldes.items()}
    b = novo.setdefault(classe, {"valor": 0.0, "custo": 0.0, "ativos": [], "dy": None, "cobertura_dy": 0.0})
    dy_ant, v_ant = b.get("dy"), b["valor"]
    b["valor"] += valor
    b["custo"] += valor
    b["ativos"].append(nome)
    if dy is not None:
        b["dy"] = ((dy_ant or 0.0) * v_ant + dy * valor) / b["valor"] if v_ant > 0 and dy_ant is not None else dy
    return novo


def retirar_ativo(posicoes: list[dict], ids: list[str], dy_por_ativo: dict | None = None) -> dict:
    """Baldes da carteira SEM os ativos `ids` (simula vender; o dinheiro some do balde — use o aporte para reaplicar)."""
    return baldes_da_carteira([p for p in posicoes if p.get("id") not in set(ids)], dy_por_ativo)


def comparar_carteiras(a: dict, b: dict) -> dict:
    """Original × simulada: diferenças nos indicadores-chave e exposição por classe."""
    if not (a.get("ok") and b.get("ok")):
        return {"ok": False}
    ra, rb = a["resumo"], b["resumo"]

    def d(k):
        x, y = ra.get(k), rb.get(k)
        return (y - x) if (x is not None and y is not None) else None
    classes = sorted(set(a["pesos_finais"]) | set(b["pesos_finais"]) | set(a["pesos_iniciais"]) | set(b["pesos_iniciais"]))
    expo = [{"classe": c, "ini_a": a["pesos_iniciais"].get(c, 0.0), "ini_b": b["pesos_iniciais"].get(c, 0.0), "fim_a": a["pesos_finais"].get(c, 0.0), "fim_b": b["pesos_finais"].get(c, 0.0)} for c in classes]
    return {"ok": True, "dif_patrimonio": d("total_liquido"), "dif_real": d("valor_real"), "dif_rent_aa": d("rentabilidade_anualizada"), "dif_vol": d("vol_estimada_final"),
            "dif_renda_anual": d("renda_passiva_anual_final"), "dif_aportado": d("total_investido"), "exposicao": expo}


def indicadores_estrutura(posicoes: list[dict]) -> dict:
    """Concentração e diversificação da lista de posições (HHI por ativo e por classe, número efetivo de posições, maiores pesos)."""
    vals = [float(p["valor"]) for p in posicoes if p.get("valor") and p["valor"] > 0]
    por_ativo = g.concentracao(vals)
    por_classe: dict = {}
    for p in posicoes:
        if p.get("valor") and p["valor"] > 0:
            c = CLASSE_PARA_SIM.get(p.get("classe"), "outros")
            por_classe[c] = por_classe.get(c, 0.0) + float(p["valor"])
    return {"ativo": por_ativo, "classe": g.concentracao(list(por_classe.values())), "n_classes": len(por_classe)}


def yield_12m(proventos: pd.DataFrame | None, preco_atual: float | None, hoje: date | None = None) -> float | None:
    """Yield dos últimos 12 meses = proventos por unidade pagos nos 12 meses / preço atual. None sem dado. (Histórico, não garantia de repetição.)"""
    if proventos is None or len(proventos) == 0 or not preco_atual or preco_atual <= 0:
        return None
    hoje = pd.Timestamp(hoje or date.today())
    d = pd.to_datetime(proventos["data"]).dt.tz_localize(None) if getattr(pd.to_datetime(proventos["data"]).dt, "tz", None) is not None else pd.to_datetime(proventos["data"])
    soma = float(proventos.loc[(d > hoje - pd.Timedelta(days=365)) & (d <= hoje), "valor"].sum())
    return soma / preco_atual if soma > 0 else None


# =============================================================================== histórico
EPISODIOS = {
    "Crise financeira global (2008–2009)": (date(2007, 12, 31), date(2009, 12, 31)),
    "Recessão brasileira (2014–2016)": (date(2014, 1, 2), date(2016, 12, 30)),
    "Pandemia (2020)": (date(2020, 1, 2), date(2020, 12, 30)),
    "Alta de juros e inflação (2021–2022)": (date(2021, 1, 4), date(2022, 12, 30)),
    "Últimos 5 anos": (None, None),
}
AVISO_HISTORICO = ("Resultados do passado, com preços ajustados por proventos quando a fonte os traz. Não incluem todos os custos nem eventos corporativos que "
                   "a fonte não registra, e não indicam o que acontecerá. As janelas das crises são convenções de agrupamento, não datas oficiais.")
ESTRATEGIAS = {"unico": "Compra única no início (e mantém)", "dca": "Aportes mensais iguais", "dca_tendencia": "Aportes mensais só com preço acima da média de 200 dias",
               "tendencia": "Compra única, sai do ativo abaixo da média de 200 dias (caixa a 0%)", "rebalanceada": "Carteira com pesos fixos, rebalanceada"}


def _serie_limpa(s: pd.Series) -> pd.Series:
    s = s.dropna().astype(float)
    s.index = pd.to_datetime(s.index).tz_localize(None) if getattr(pd.to_datetime(s.index), "tz", None) is not None else pd.to_datetime(s.index)
    s = s[~s.index.duplicated(keep="last")].sort_index()
    return s[s > 0]


def _primeiros_dias_do_mes(idx: pd.DatetimeIndex) -> list[pd.Timestamp]:
    df = pd.Series(idx, index=idx)
    return list(df.groupby([idx.year, idx.month]).first().values)


def metricas_caminho(valor: pd.Series) -> dict:
    """Queda máxima e volatilidade anual (dias úteis) de uma série de valores."""
    v = valor.dropna()
    if len(v) < 3:
        return {"mdd": None, "vol_aa": None}
    pico = v.cummax()
    mdd = float((v / pico - 1.0).min())
    r = v.pct_change().dropna()
    r = r[np.isfinite(r)]
    return {"mdd": mdd, "vol_aa": float(r.std() * math.sqrt(252)) if len(r) > 2 else None}


def _tributo(ganho: float, tipo: str, aliquota: float | None) -> float:
    a = aliquota if aliquota is not None else S.ALIQUOTA_PADRAO.get(tipo, 0.0)
    return max(ganho, 0.0) * a


def simular_historico(series: dict[str, pd.Series], estrategia: str, inicio: date | None = None, fim: date | None = None, capital: float = 10000.0,
                      aporte_mensal: float = 1000.0, pesos_alvo: dict | None = None, rebalancar: str = "anual", corretagem: float = 0.0, ir: str = "isento",
                      aliquota: float | None = None, ipca_mensal: pd.Series | None = None, cdi_diario: pd.Series | None = None, janela_tendencia: int = 200) -> dict:
    """Simula uma estratégia com preços reais (série de preço ajustado, em R$, de cada ativo).
    unico: compra tudo no 1º dia. dca: `aporte_mensal` no 1º pregão de cada mês (o capital inicial entra no 1º dia). dca_tendencia: só aporta se o
    fechamento de ontem estava acima da média de `janela_tendencia` dias de ontem (sem olhar o futuro); o que não foi aportado fica em caixa a 0%.
    tendencia: compra única; fica no ativo se o fechamento anterior estava acima da média móvel anterior, senão em caixa (0%). rebalanceada: vários ativos com
    pesos fixos, volta aos pesos a cada 'mensal'/'trimestral'/'anual'.
    Corretagem: % sobre cada compra/venda. IR: sobre o ganho no fim (liquidação hipotética). Real = deflacionado por ipca_mensal (se dado)."""
    if estrategia not in ESTRATEGIAS:
        raise ValueError(f"estratégia desconhecida: {estrategia}")
    ss = {k: _serie_limpa(v) for k, v in series.items() if v is not None and len(v) > 5}
    if not ss:
        return {"ok": False, "motivo": "sem séries de preço"}
    idx = None
    for s in ss.values():
        idx = s.index if idx is None else idx.intersection(s.index)
    if inicio:
        idx = idx[idx >= pd.Timestamp(inicio)]
    if fim:
        idx = idx[idx <= pd.Timestamp(fim)]
    if len(idx) < 30:
        return {"ok": False, "motivo": "poucos pregões em comum no período escolhido"}
    P = pd.DataFrame({k: s.reindex(idx) for k, s in ss.items()}).ffill().dropna()
    idx = P.index
    nomes = list(P.columns)
    if estrategia == "rebalanceada":
        w = pesos_alvo or {n: 1.0 / len(nomes) for n in nomes}
        sw = sum(w.get(n, 0.0) for n in nomes)
        w = {n: w.get(n, 0.0) / sw for n in nomes}
    else:
        base = nomes[0]
        w = {base: 1.0}
    mm = {n: P[n].rolling(janela_tendencia, min_periods=janela_tendencia).mean().shift(1) for n in nomes}
    ant = P.shift(1)
    meses_ini = set(_primeiros_dias_do_mes(idx))
    freq = {"mensal": 1, "trimestral": 3, "anual": 12}.get(rebalancar, 12)
    qtd = {n: 0.0 for n in nomes}
    caixa = 0.0
    investido = 0.0
    base_custo = 0.0
    fluxos = []
    hist_valor = []
    mes_idx = 0
    t0 = idx[0]

    def comprar(n, valor, dia):
        nonlocal base_custo
        liquido = valor * (1.0 - corretagem)
        qtd[n] += liquido / P.at[dia, n]
        base_custo += valor

    for k, dia in enumerate(idx):
        if k == 0:
            investido += capital
            fluxos.append((dia, -capital))
            if estrategia in ("unico", "dca", "dca_tendencia", "tendencia", "rebalanceada"):
                if estrategia == "dca_tendencia":
                    caixa += capital
                else:
                    for n in nomes:
                        comprar(n, capital * w[n], dia)
        elif dia in meses_ini and estrategia in ("dca", "dca_tendencia", "rebalanceada") and aporte_mensal > 0:
            mes_idx += 1
            investido += aporte_mensal
            fluxos.append((dia, -aporte_mensal))
            if estrategia == "dca":
                comprar(nomes[0], aporte_mensal, dia)
            elif estrategia == "dca_tendencia":
                caixa += aporte_mensal
            else:
                tot = sum(qtd[n] * P.at[dia, n] for n in nomes) + aporte_mensal
                for n in nomes:
                    comprar(n, aporte_mensal * w[n], dia)
        elif dia in meses_ini and k > 0:
            mes_idx += 1
        if estrategia == "dca_tendencia" and dia in meses_ini and caixa > 0:
            ok = (not np.isnan(mm[nomes[0]].at[dia])) and ant.at[dia, nomes[0]] > mm[nomes[0]].at[dia]
            if ok:
                comprar(nomes[0], caixa, dia)
                caixa = 0.0
        if estrategia == "tendencia" and k > 0:
            n = nomes[0]
            tem = qtd[n] > 0
            sinal = (not np.isnan(mm[n].at[dia])) and ant.at[dia, n] > mm[n].at[dia]
            if tem and not sinal:
                caixa += qtd[n] * P.at[dia, n] * (1.0 - corretagem)
                qtd[n] = 0.0
            elif (not tem) and sinal and caixa > 0:
                comprar(n, caixa, dia)
                base_custo = base_custo   # o custo fiscal acumulado segue o total aportado
                caixa = 0.0
        if estrategia == "rebalanceada" and k > 0 and dia in meses_ini and mes_idx % freq == 0:
            tot = sum(qtd[n] * P.at[dia, n] for n in nomes)
            for n in nomes:
                alvo = tot * w[n]
                atual = qtd[n] * P.at[dia, n]
                dif = alvo - atual
                qtd[n] += dif / P.at[dia, n] - abs(dif) * corretagem / P.at[dia, n]
        valor = sum(qtd[n] * P.at[dia, n] for n in nomes) + caixa
        hist_valor.append(valor)
    serie_valor = pd.Series(hist_valor, index=idx)
    final = float(serie_valor.iloc[-1])
    custo_fiscal = investido
    imposto = _tributo(final - custo_fiscal, ir, aliquota)
    liquido = final - imposto
    fluxos2 = [(((d - t0).days / 30.4375), v) for d, v in fluxos] + [((idx[-1] - t0).days / 30.4375, liquido)]
    irr = S.tir_mensal(fluxos2)
    anualizada = S.anual(irr) if irr is not None else None
    anos = (idx[-1] - t0).days / 365.25
    m = metricas_caminho(serie_valor)
    real = None
    infl_periodo = None
    if ipca_mensal is not None and len(ipca_mensal):
        ip = ipca_mensal.copy()
        ip.index = pd.to_datetime(ip.index)
        sel = ip[(ip.index > t0 - pd.Timedelta(days=31)) & (ip.index <= idx[-1])]
        if len(sel):
            infl_periodo = float((1.0 + sel / 100.0).prod() - 1.0) if sel.abs().max() > 1.0 or True else None
            real = liquido / (1.0 + infl_periodo)
    cdi_ref = None
    if cdi_diario is not None and len(cdi_diario):
        c = cdi_diario.copy()
        c.index = pd.to_datetime(c.index)
        sel = c[(c.index > t0) & (c.index <= idx[-1])]
        if len(sel):
            fator = float((1.0 + sel / 100.0).prod())
            cdi_ref = {"fator": fator, "valor_equivalente_unico": capital * fator}
    return {"ok": True, "estrategia": estrategia, "rotulo": ESTRATEGIAS[estrategia], "inicio": idx[0].date(), "fim": idx[-1].date(), "anos": anos, "pregoes": len(idx),
            "serie": serie_valor, "investido": investido, "valor_final": final, "imposto": imposto, "valor_liquido": liquido, "ganho_liquido": liquido - investido,
            "rentabilidade_acumulada": liquido / investido - 1.0 if investido > 0 else None, "tir_aa": anualizada, "mdd": m["mdd"], "vol_aa": m["vol_aa"],
            "inflacao_periodo": infl_periodo, "valor_real": real, "cdi": cdi_ref, "ativos": nomes, "avisos": [AVISO_HISTORICO]}


def comparar_estrategias(series: dict[str, pd.Series], estrategias: list[str], **kw) -> list[dict]:
    """Mesmo período, mesmo capital e mesmos aportes para todas as estratégias; ordena pelo valor líquido final."""
    out = [simular_historico(series, e, **kw) for e in estrategias]
    ok = [r for r in out if r.get("ok")]
    return sorted(ok, key=lambda r: -r["valor_liquido"]) + [r for r in out if not r.get("ok")]


def periodo_do_episodio(nome: str, hoje: date | None = None) -> tuple[date, date]:
    ini, fim = EPISODIOS[nome]
    if ini is None:
        hoje = hoje or date.today()
        return date(hoje.year - 5, hoje.month, min(hoje.day, 28)), hoje
    return ini, fim
