"""
Motor de inteligência do BÚSSOLA B3 (Passo 13). Sem Streamlit: só cálculo, regras e texto, para poder ser testado.

O que este módulo FAZ (e só com dado que alguém lhe entregou; nada é inventado):
  - anomalias estatísticas de preço/volume e tendência (com a diferença entre "anomalia estatística" e "evento com fonte");
  - projeção probabilística de preço (bootstrap em blocos) e projeção linear de indicadores, sempre com intervalo e limites;
  - avaliação de oportunidades por EVIDÊNCIAS EM VÁRIOS PILARES (um indicador isolado nunca basta) + bandeiras de risco;
  - notícias: leitura de RSS, limpeza, categorias, tom aproximado, relevância e remoção de repetidas;
  - alertas configuráveis, com prioridade, controle de frequência e histórico;
  - rankings dentro de UMA classe (nunca mistura classes), com critério, pontuação, riscos e justificativa;
  - comparação entre fotografias (o que mudou), assistente baseado em regras sobre os dados carregados e relatórios.

O que NÃO faz: recomendar compra ou venda, prometer retorno, tratar notícia como instrução, executar operação.
Tudo que vem de fora (notícias, nomes de ativos) é DADO: é limpo, truncado e nunca interpretado como comando.
As notas por classe vêm dos motores dos Passos 6 a 12 (comparador, crescimento, fiis, fundos, renda fixa, cripto, gestão);
aqui elas só são lidas, combinadas e monitoradas.
"""

from __future__ import annotations

import html
import math
import re
import unicodedata
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

import numpy as np
import pandas as pd

AVISO_LEGAL = ("Ferramenta educacional. Sinais, notas, tom de notícias e cenários são leituras de dados e modelos simples, não "
               "recomendação de compra ou venda, e não garantem resultado futuro. Confira sempre a fonte original.")


def _ok(v) -> bool:
    try:
        return v is not None and not isinstance(v, bool) and math.isfinite(float(v))
    except (TypeError, ValueError):
        return False


def _br(v, casas: int = 1) -> str:
    if not _ok(v):
        return "n/d"
    return f"{float(v):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _iso(d) -> str | None:
    try:
        return pd.Timestamp(d).date().isoformat()
    except Exception:
        return None


def _sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(s)) if unicodedata.category(c) != "Mn")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", _sem_acento(s).lower())).strip()


def escapar_md(t: str) -> str:
    """Texto vindo de fora, seguro para st.markdown (sem links, imagens, títulos, HTML ou ênfase injetados)."""
    t = html.unescape(str(t or ""))
    return re.sub(r"([\\`*_{}\[\]()#+!<>|~$])", r"\\\1", t)


# =============================================================================== preços: anomalias e tendência
LIM_ANOMALIA = {"z": 3.0, "queda_min_pct": 4.0, "z_acumulado": 3.5, "razao_vol": 1.8, "volume_x": 3.0, "dd_atual": -30.0,
                "base": 60, "min_obs": 80}


def _serie(s) -> pd.Series:
    if s is None:
        return pd.Series(dtype=float)
    try:
        x = pd.Series(s).astype(float)
    except Exception:
        return pd.Series(dtype=float)
    x = x[np.isfinite(x) & (x > 0)]
    if not isinstance(x.index, pd.DatetimeIndex):
        return x
    return x[~x.index.duplicated(keep="last")].sort_index()


def anomalias_preco(preco, volume=None, limites: dict | None = None) -> list[dict]:
    """Anomalias ESTATÍSTICAS (não confirmadas) no último pregão, comparadas ao comportamento dos 60 pregões anteriores:
    queda/alta fora do padrão (z-score do retorno), queda acumulada em 5 pregões, aumento da volatilidade (20 d ÷ 120 d),
    salto de volume (último ÷ mediana de 20) e queda acumulada desde a máxima de 12 meses."""
    L = {**LIM_ANOMALIA, **(limites or {})}
    p = _serie(preco)
    if len(p) < L["min_obs"]:
        return []
    r = p.pct_change().dropna()
    data = _iso(p.index[-1])
    out: list[dict] = []

    def add(tipo, sentido, grav, valor, limiar, texto):
        out.append({"tipo": tipo, "sentido": sentido, "gravidade": grav, "valor": float(valor), "limiar": limiar, "texto": texto,
                    "natureza": "estimativa estatística (não confirmada por fonte)", "data": data})

    base = r.iloc[-(L["base"] + 1):-1]
    sig, mu = float(base.std()), float(base.mean())
    ult = float(r.iloc[-1])
    if sig > 0:
        z = (ult - mu) / sig
        if z <= -L["z"] and ult * 100 <= -L["queda_min_pct"]:
            add("queda_anormal", "negativo", "alta" if z <= -4.5 else "media", z, -L["z"],
                f"Queda de {_br(ult * 100)}% no último pregão, {_br(abs(z))} desvios-padrão fora do normal dos últimos {L['base']} pregões.")
        elif z >= L["z"] and ult * 100 >= L["queda_min_pct"]:
            add("alta_anormal", "positivo", "baixa", z, L["z"],
                f"Alta de {_br(ult * 100)}% no último pregão, {_br(z)} desvios-padrão fora do normal dos últimos {L['base']} pregões.")
        if len(r) >= 5 + L["base"]:
            acum = float(np.log1p(r.iloc[-5:]).sum())
            base5 = r.iloc[-(L["base"] + 5):-5]
            s5 = float(base5.std()) * math.sqrt(5)
            if s5 > 0 and acum / s5 <= -L["z_acumulado"] and (math.exp(acum) - 1) * 100 <= -L["queda_min_pct"] * 1.5 \
                    and not any(a["tipo"] == "queda_anormal" for a in out):
                add("queda_acumulada", "negativo", "media", acum / s5, -L["z_acumulado"],
                    f"Queda acumulada de {_br((math.exp(acum) - 1) * 100)}% em 5 pregões, bem acima do ritmo normal.")
    if len(r) >= 140:
        v20, v120 = float(r.iloc[-20:].std()), float(r.iloc[-120:].std())
        if v120 > 0 and v20 / v120 >= L["razao_vol"]:
            add("volatilidade", "negativo", "media", v20 / v120, L["razao_vol"],
                f"Volatilidade dos últimos 20 pregões é {_br(v20 / v120)}× a dos últimos 120.")
    vol = _serie(volume)
    if len(vol) >= 25:
        v_ult = float(vol.iloc[-1])
        med = float(vol.iloc[-21:-1].median())
        if med > 0 and v_ult / med >= L["volume_x"]:
            add("volume", "neutro", "baixa", v_ult / med, L["volume_x"],
                f"Volume do último pregão foi {_br(v_ult / med)}× a mediana dos 20 anteriores.")
        elif med > 0 and v_ult / med <= 0.2:
            add("volume_baixo", "neutro", "baixa", v_ult / med, 0.2,
                f"Volume do último pregão foi só {_br(v_ult / med * 100, 0)}% da mediana dos 20 anteriores (liquidez menor).")
    j = p.iloc[-252:]
    dd = (float(j.iloc[-1]) / float(j.max()) - 1) * 100
    if dd <= L["dd_atual"]:
        add("queda_do_pico", "negativo", "alta" if dd <= -50 else "media", dd, L["dd_atual"],
            f"O preço está {_br(abs(dd))}% abaixo da máxima dos últimos 12 meses.")
    return out


def _dt(x):
    try:
        d = pd.Timestamp(x)
        return d.tz_localize(None) if d.tzinfo is not None else d
    except Exception:
        return None


def cruzar_anomalias_noticias(anomalias: list[dict], noticias: list[dict], dias: int = 3) -> list[dict]:
    """Liga anomalias a notícias do mesmo período. A coincidência NÃO prova causa; sem notícia, a anomalia segue só estatística."""
    out = []
    for a in anomalias or []:
        d = _dt(a.get("data")) if a.get("data") else None
        rel = []
        for n in noticias or []:
            dn = _dt(n.get("data")) if n.get("data") else None
            if d is not None and dn is not None and abs((d - dn).total_seconds()) <= dias * 86400 + 86399:
                rel.append(n)
        b = dict(a)
        b["noticias_proximas"] = [{"titulo": n.get("titulo"), "fonte": n.get("fonte"), "url": n.get("url")} for n in rel[:3]]
        b["status"] = ("coincide com notícia do período (a coincidência não prova a causa)" if rel
                       else "anomalia estatística sem notícia associada nas fontes consultadas")
        out.append(b)
    return out


def tendencia(preco, janela: int = 120) -> dict:
    """Tendência pela inclinação do log do preço (regressão linear) nos últimos `janela` pregões, com R² e estatística t,
    mais a posição frente às médias de 50 e 200 pregões. Rótulo: alta/baixa só se |t| ≥ 2; caso contrário, lateral."""
    p = _serie(preco)
    out = {"rotulo": None, "inclinacao_aa": None, "r2": None, "t": None, "acima_mm200": None, "mm50_sobre_mm200": None,
           "n": 0, "data": None}
    if len(p) < max(40, janela // 2):
        return out
    j = p.iloc[-janela:]
    y = np.log(j.values.astype(float))
    x = np.arange(len(y), dtype=float)
    xm, ym = x.mean(), y.mean()
    sxx = float(((x - xm) ** 2).sum())
    b = float(((x - xm) * (y - ym)).sum() / sxx)
    a = ym - b * xm
    res = y - (a + b * x)
    sst = float(((y - ym) ** 2).sum())
    r2 = 1.0 - float((res ** 2).sum()) / sst if sst > 0 else 1.0
    if len(y) > 2 and float((res ** 2).sum()) > 1e-18:
        se = math.sqrt(float((res ** 2).sum()) / (len(y) - 2) / sxx)
        t = b / se if se > 0 else None
    else:
        t = float("inf") if b > 0 else float("-inf") if b < 0 else 0.0
    out.update({"inclinacao_aa": (math.exp(b * 252) - 1) * 100, "r2": r2, "t": t, "n": len(j), "data": _iso(p.index[-1])
                if isinstance(p.index, pd.DatetimeIndex) else None})
    out["rotulo"] = "alta" if (t is not None and t >= 2 and b > 0) else "baixa" if (t is not None and t <= -2 and b < 0) else "lateral"
    if len(p) >= 200:
        m50, m200 = float(p.iloc[-50:].mean()), float(p.iloc[-200:].mean())
        out["acima_mm200"] = bool(float(p.iloc[-1]) > m200)
        out["mm50_sobre_mm200"] = bool(m50 > m200)
    return out


# =============================================================================== projeções com incerteza
def projecao_preco(preco, horizonte: int = 63, n_sim: int = 2000, janela: int = 756, bloco: int = 5, seed: int = 7,
                   usar_media_historica: bool = False, escala_vol: float = 1.0) -> dict:
    """Cenários probabilísticos por BOOTSTRAP EM BLOCOS dos retornos diários (log) da janela observada. Por padrão a média
    histórica é retirada (deriva zero): o resultado mostra a INCERTEZA, não uma aposta de alta ou de queda. Devolve percentis
    5/25/50/75/95 do preço no horizonte, probabilidade de ficar abaixo do preço atual, premissas, período e limitações."""
    p = _serie(preco)
    base = {"ok": False, "motivo": None, "percentis": None, "prob_abaixo": None, "premissas": [], "limitacoes": LIMITACOES_PROJECAO,
            "periodo": None, "metodo": "bootstrap em blocos de retornos diários"}
    if len(p) < 250:
        base["motivo"] = f"histórico de {len(p)} pregões; a projeção exige pelo menos 250."
        return base
    p = p.iloc[-(janela + 1):]
    r = np.log(p.values[1:] / p.values[:-1])
    mu = float(r.mean())
    if not usar_media_historica:
        r = r - mu
    if escala_vol != 1.0:                      # cenário de mercado: volatilidade multiplicada (ex.: 1,5 = estresse, 0,7 = calmaria)
        r = (r - r.mean()) * escala_vol + r.mean()
    rng = np.random.default_rng(seed)
    n_blocos = int(math.ceil(horizonte / bloco))
    inicios = rng.integers(0, len(r) - bloco + 1, size=(n_sim, n_blocos))
    idx = (inicios[:, :, None] + np.arange(bloco)[None, None, :]).reshape(n_sim, -1)[:, :horizonte]
    soma = r[idx].sum(axis=1)
    p0 = float(p.iloc[-1])
    finais = p0 * np.exp(soma)
    q = {k: float(np.percentile(finais, k)) for k in (5, 25, 50, 75, 95)}
    base.update({
        "ok": True, "p0": p0, "horizonte": horizonte, "percentis": q, "prob_abaixo": float((finais < p0).mean()),
        "vol_diaria": float(r.std()), "n_sim": n_sim, "escala_vol": escala_vol,
        "periodo": (_iso(p.index[0]) if isinstance(p.index, pd.DatetimeIndex) else None,
                    _iso(p.index[-1]) if isinstance(p.index, pd.DatetimeIndex) else None, len(p)),
        "premissas": [f"Retornos diários sorteados em blocos de {bloco} pregões do período observado ({len(p)} pregões).",
                      "Média histórica retirada (deriva zero): o cenário central fica perto do preço de hoje." if not usar_media_historica
                      else "Média histórica mantida: o cenário repete o ritmo do passado, que raramente se mantém.",
                      f"Volatilidade multiplicada por {escala_vol:g} em relação ao histórico." if escala_vol != 1.0 else "Volatilidade igual à do histórico.",
                      f"{n_sim} simulações para {horizonte} pregões à frente; sem dividendos, custos ou eventos futuros."]})
    return base


LIMITACOES_PROJECAO = [
    "O passado não garante o futuro: crises, mudanças de regime e notícias novas não estão no histórico.",
    "O modelo supõe que a distribuição dos retornos passados continua valendo; caudas extremas tendem a ser subestimadas.",
    "Intervalos mostram incerteza, não probabilidade de acerto do modelo. Não é previsão.",
]


def projetar_indicador(serie, passos: int = 2, nivel_z: float = 1.96) -> dict:
    """Projeção LINEAR de um indicador anual (ex.: receita, lucro), com intervalo de ±z·erro de previsão da regressão.
    Exige pelo menos 4 pontos; com menos, devolve o motivo e nenhuma projeção."""
    s = pd.Series(serie).astype(float).dropna() if serie is not None else pd.Series(dtype=float)
    if len(s) < 4:
        return {"ok": False, "motivo": f"apenas {len(s)} ponto(s); a projeção exige pelo menos 4.", "projecao": []}
    x = np.arange(len(s), dtype=float)
    y = s.values
    xm, ym = x.mean(), y.mean()
    sxx = float(((x - xm) ** 2).sum())
    b = float(((x - xm) * (y - ym)).sum() / sxx)
    a = ym - b * xm
    res = y - (a + b * x)
    s_res = math.sqrt(float((res ** 2).sum()) / (len(y) - 2))
    out = []
    for k in range(1, passos + 1):
        x0 = len(s) - 1 + k
        pred = a + b * x0
        erro = s_res * math.sqrt(1 + 1 / len(y) + (x0 - xm) ** 2 / sxx)
        out.append({"passo": k, "estimativa": float(pred), "inferior": float(pred - nivel_z * erro), "superior": float(pred + nivel_z * erro)})
    return {"ok": True, "inclinacao": b, "erro_padrao": s_res, "n": len(s), "projecao": out,
            "premissas": ["Tendência linear dos últimos exercícios anuais.", "Intervalo de ~95% do erro de previsão da regressão."],
            "limitacoes": ["Poucos pontos: o intervalo é largo e instável.", "Não considera mudanças de negócio, ciclo ou eventos futuros."]}


# =============================================================================== oportunidades (evidências em vários pilares)
LIM_FAVORAVEL = 65.0     # pilar com nota ≥ 65 conta como evidência favorável
LIM_BANDEIRA = 30.0      # pilar com nota ≤ 30 vira bandeira de atenção
MIN_EVIDENCIAS = 3       # nº mínimo de pilares favoráveis para "merece estudo"

ROTULO_STATUS = {
    "merece_estudo": "Merece estudo",
    "sinais_parciais": "Sinais parciais",
    "sem_sinais": "Sem sinais claros",
    "atencao_riscos": "Atenção: riscos",
    "dados_insuficientes": "Dados insuficientes",
}

# pilares que cada classe usa nos motores existentes (para filtros por classe e para o texto)
FILTROS_CLASSE = {
    "acao": "Valor, Qualidade, Dividendos, Solidez, Tendência e Risco (Ranking do app) + diagnóstico de crescimento (Passo 7).",
    "bdr": "Mesmos pilares das ações, com os dados disponíveis.",
    "fii": "Renda, Liquidez, Risco, Retorno, Valuation (P/VP) e Qualidade dos ativos (Passo 8), comparando só FIIs da mesma estratégia.",
    "cripto": "Pilares do motor fundamentalista de cripto (Passo 9): adoção, tokenomics, risco e mercado.",
    "etf": "Retorno, Risco, Tendência e Custos e porte (Passo 10).",
    "fundo": "Retorno, Risco, Consistência, Custos e Porte e liquidez (Passo 10, dados da CVM).",
    "renda_fixa": "Retorno real esperado, Crédito, Liquidez e Risco de mercado (Passo 11).",
}


def avaliar_oportunidade(classe: str, pilares: dict, bandeiras: list | tuple = (), extras: dict | None = None,
                         minimo: int = MIN_EVIDENCIAS, prioritarios: list | tuple = ()) -> dict:
    """Combina evidências de PILARES diferentes. Nunca conclui por um indicador isolado.
    `pilares`: nome → nota 0-100 (None = sem dado). `extras`: nome → True/False/None (evidências qualitativas, ex.: "Fundamentos
    em melhora"). `bandeiras`: riscos graves; com qualquer bandeira o status vira "atencao_riscos" mesmo com evidências favoráveis.
    `prioritarios`: pilares que o usuário prioriza; se informados, "merece estudo" exige ao menos um deles favorável."""
    fav, desf, sem = [], [], []
    for nome, v in (pilares or {}).items():
        if not _ok(v):
            sem.append(nome)
        elif v >= LIM_FAVORAVEL:
            fav.append((nome, float(v)))
        elif v <= LIM_BANDEIRA:
            desf.append((nome, float(v)))
    for nome, v in (extras or {}).items():
        if v is None:
            sem.append(nome)
        elif v:
            fav.append((nome, 100.0))
        else:
            desf.append((nome, 0.0))
    com_dado = len(fav) + len(desf) + sum(1 for n, v in (pilares or {}).items() if _ok(v) and LIM_BANDEIRA < v < LIM_FAVORAVEL)
    band = list(bandeiras or [])
    if com_dado < 3:
        status = "dados_insuficientes"
    elif band:
        status = "atencao_riscos"
    elif len(fav) >= minimo and len(fav) / max(com_dado, 1) >= 0.5:
        status = "merece_estudo"
        if prioritarios and not any(n in {x for x, _ in fav} for n in prioritarios):
            status = "sinais_parciais"
    elif len(fav) >= 2:
        status = "sinais_parciais"
    else:
        status = "sem_sinais"
    nomes_fav = ", ".join(f"{n} ({v:.0f})" for n, v in sorted(fav, key=lambda x: -x[1])[:4])
    texto = {
        "merece_estudo": f"Evidências favoráveis em {len(fav)} de {com_dado} critérios ({nomes_fav}). É um ponto de partida para estudar, não uma recomendação.",
        "sinais_parciais": f"Há {len(fav)} critério(s) favorável(is) ({nomes_fav or 'nenhum'}), mas não o suficiente para destacar.",
        "sem_sinais": "Os critérios avaliados não mostram evidências favoráveis em número suficiente.",
        "atencao_riscos": "Há bandeiras de risco que pedem atenção antes de qualquer outra conclusão: " + "; ".join(band[:3]) + ".",
        "dados_insuficientes": f"Só {com_dado} critério(s) com dado; a leitura exige pelo menos 3.",
    }[status]
    return {"status": status, "rotulo": ROTULO_STATUS[status], "classe": classe,
            "favoraveis": [n for n, _ in sorted(fav, key=lambda x: -x[1])], "desfavoraveis": [n for n, _ in desf],
            "sem_dado": sem, "bandeiras": band, "n_criterios": com_dado, "texto": texto,
            "forca": len(fav) / com_dado if com_dado else None}


def extras_de_achados(achados: list[dict]) -> dict:
    """Do diagnóstico de crescimento (Passo 7) para evidências qualitativas. Só avalia o que o diagnóstico cobre."""
    if not achados or all(a.get("chave") in ("historico", "financeira") for a in achados):
        return {}
    chaves = {a.get("chave"): a.get("tom") for a in achados}
    pos = [k for k, t in chaves.items() if t == "positivo"]
    neg = [k for k, t in chaves.items() if t == "atencao"]
    ex = {"Fundamentos em melhora": True if pos and len(pos) > len(neg) else (False if neg and not pos else None)}
    if any(k in chaves for k in ("receita_queda", "receita_consistente", "receita_acelera", "receita_desacelera")):
        ex["Receita"] = (False if "receita_queda" in chaves or "receita_desacelera" in chaves
                         else True if "receita_consistente" in chaves or "receita_acelera" in chaves else None)
    if any(k in chaves for k in ("fcl_negativo", "fcl_melhora", "fcl_queda")):
        ex["Geração de caixa"] = False if ("fcl_negativo" in chaves or "fcl_queda" in chaves) else True if "fcl_melhora" in chaves else None
    return {k: v for k, v in ex.items() if v is not None}


BANDEIRAS_GRAVES_ACHADO = {"lucro_prejuizo": "prejuízo no último exercício", "alavancagem_ebitda": "dívida líquida muito alta frente ao EBITDA",
                           "alavancagem": "alavancagem elevada", "fcl_negativo": "fluxo de caixa livre negativo",
                           "lucro_sem_caixa": "lucro sem geração de caixa"}


def bandeiras_de(achados: list[dict] | None = None, anomalias: list[dict] | None = None, ind: dict | None = None,
                 risco: str = "moderado", classe: str = "acao") -> list[str]:
    """Bandeiras de risco (texto) a partir de diagnóstico, anomalias e do perfil de risco escolhido pelo usuário."""
    out = []
    for a in achados or []:
        if a.get("chave") in BANDEIRAS_GRAVES_ACHADO and a.get("tom") == "atencao":
            out.append(BANDEIRAS_GRAVES_ACHADO[a["chave"]].capitalize())
    for a in anomalias or []:
        if a.get("sentido") == "negativo" and a.get("gravidade") == "alta":
            out.append(a["texto"])
    lim = LIMITES_RISCO.get(risco, LIMITES_RISCO["moderado"])
    ind = ind or {}
    if _ok(ind.get("vol")) and ind["vol"] > lim["vol_max"] and classe not in ("renda_fixa",):
        out.append(f"Volatilidade de {_br(ind['vol'])}% a.a. acima do limite do seu perfil {risco} ({lim['vol_max']}%)")
    if _ok(ind.get("dd_max")) and ind["dd_max"] < lim["dd_max"] and classe not in ("renda_fixa",):
        out.append(f"Queda máxima de {_br(ind['dd_max'])}% em 12 meses, pior que o limite do perfil {risco} ({lim['dd_max']}%)")
    return list(dict.fromkeys(out))


# =============================================================================== preferências do usuário
CLASSES_TODAS = ["acao", "bdr", "fii", "cripto", "etf", "fundo", "renda_fixa"]
ROTULO_CLASSE = {"acao": "Ações", "bdr": "BDRs", "fii": "FIIs", "cripto": "Criptomoedas", "etf": "ETFs", "fundo": "Fundos", "renda_fixa": "Renda fixa"}
LIMITES_RISCO = {"conservador": {"vol_max": 20.0, "dd_max": -25.0}, "moderado": {"vol_max": 35.0, "dd_max": -40.0},
                 "arrojado": {"vol_max": 70.0, "dd_max": -65.0}}
HORIZONTES = {"curto (até 1 ano)": 63, "médio (1 a 5 anos)": 126, "longo (mais de 5 anos)": 252}
FREQUENCIAS = {"cada_atualizacao": 1, "diaria": 24, "semanal": 168}
ROTULO_FREQ = {"cada_atualizacao": "A cada atualização", "diaria": "No máximo 1 vez por dia", "semanal": "No máximo 1 vez por semana"}

PREFS_PADRAO = {"classes": list(CLASSES_TODAS), "favoritos": [], "risco": "moderado", "horizonte": "médio (1 a 5 anos)",
                "pilares_prioritarios": [], "tipos_alerta": [], "frequencia": "diaria", "benchmarks": ["CDI", "Ibovespa"]}


def normalizar_prefs(p: dict | None) -> dict:
    """Completa e valida as preferências (valores desconhecidos voltam ao padrão)."""
    p = dict(p or {})
    out = dict(PREFS_PADRAO)
    cl = [c for c in (p.get("classes") or []) if c in CLASSES_TODAS]
    out["classes"] = cl or list(CLASSES_TODAS)
    fav = []
    for t in p.get("favoritos") or []:
        t = re.sub(r"[^A-Za-z0-9.\-]", "", str(t)).upper()[:24]
        if t and t not in fav:
            fav.append(t)
    out["favoritos"] = fav[:40]
    out["risco"] = p.get("risco") if p.get("risco") in LIMITES_RISCO else "moderado"
    out["horizonte"] = p.get("horizonte") if p.get("horizonte") in HORIZONTES else PREFS_PADRAO["horizonte"]
    out["pilares_prioritarios"] = [str(x)[:40] for x in (p.get("pilares_prioritarios") or [])][:6]
    out["tipos_alerta"] = [t for t in (p.get("tipos_alerta") or []) if t in TIPOS_ALERTA]
    out["frequencia"] = p.get("frequencia") if p.get("frequencia") in FREQUENCIAS else "diaria"
    out["benchmarks"] = [str(b)[:24] for b in (p.get("benchmarks") or PREFS_PADRAO["benchmarks"])][:6]
    return out


def nota_personalizada(pilares: dict, pesos: dict | None, prioritarios: list | tuple, fator: float = 1.5) -> float | None:
    """Reponderação pela prioridade do usuário (peso × 1,5 nos pilares escolhidos). Só pilares com dado; None se nenhum."""
    pesos = pesos or {}
    num = den = 0.0
    for k, v in (pilares or {}).items():
        if not _ok(v):
            continue
        w = float(pesos.get(k, 1.0) or 1.0) * (fator if k in (prioritarios or ()) else 1.0)
        num += w * float(v)
        den += w
    return num / den if den else None


# =============================================================================== notícias
CATEGORIAS_NOTICIA = {
    "Resultados financeiros": ["resultado", "balanco", "lucro", "prejuizo", "receita", "ebitda", "trimestre", "guidance", "earnings", "revenue"],
    "Fusões e aquisições": ["fusao", "aquisicao", "incorpora", "oferta publica", "opa ", "compra a ", "vende participacao", "merger", "acquisition", "acquires"],
    "Dividendos": ["dividendo", "jcp", "juros sobre capital", "proventos", "rendimento", "bonificacao", "dividend", "buyback", "recompra"],
    "Mudanças regulatórias": ["regulat", "cvm", "anbima", "banco central regula", "resolucao", "norma", "sec ", "licenca", "regulation"],
    "Decisões governamentais": ["governo", "ministerio", "congresso", "senado", "camara", "imposto", "tributa", "reforma", "decreto", "medida provisoria", "tarifa"],
    "Política monetária": ["copom", "selic", "politica monetaria", "fed ", "fomc", "banco central", "bce", "meta de inflacao"],
    "Inflação": ["inflacao", "ipca", "igpm", "igp-m", "cpi", "precos ao consumidor", "deflacao"],
    "Juros": ["juros", "taxa de juros", "curva de juros", "di futuro", "treasury", "yield"],
    "Crises": ["crise", "calote", "recuperacao judicial", "falencia", "default", "inadimpl", "colapso", "rombo", "quebra"],
    "Problemas operacionais": ["greve", "acidente", "paralisa", "interrompe", "vazamento", "recall", "incendio", "suspende producao", "apagao", "falha operacional"],
    "Atualizações tecnológicas": ["lanca", "lancamento", "atualizacao", "upgrade", "hard fork", "mainnet", "inteligencia artificial", "tecnologia", "plataforma", "etf de bitcoin"],
    "Segurança em cripto": ["hack", "hacker", "exploit", "invasao", "roubo de", "rug pull", "ataque", "vulnerabilidade", "stolen", "drained"],
    "Mudanças na gestão": ["ceo", "presidente", "diretor", "conselho de administracao", "renuncia", "demite", "nomeia", "novo gestor", "troca de comando", "gestora"],
}
PESO_CATEGORIA = {"Crises": 35, "Segurança em cripto": 35, "Resultados financeiros": 30, "Fusões e aquisições": 30, "Dividendos": 25,
                  "Mudanças regulatórias": 25, "Problemas operacionais": 25, "Mudanças na gestão": 20, "Decisões governamentais": 15,
                  "Política monetária": 15, "Inflação": 10, "Juros": 10, "Atualizações tecnológicas": 10}
ALTERA_FUNDAMENTOS = {"Resultados financeiros", "Fusões e aquisições", "Mudanças regulatórias", "Crises", "Problemas operacionais",
                      "Mudanças na gestão", "Segurança em cripto", "Dividendos"}
PALAVRAS_POSITIVAS = ["lucro sobe", "lucra", "lucro cresce", "recorde", "cresce", "crescimento", "supera", "aprova", "aprovado", "eleva", "aumenta", "melhora",
                      "expansao", "valoriza", "dispara", "sobe", "alta de", "acordo", "reajusta", "paga dividendo", "distribui", "upgrade",
                      "beats", "surges", "record", "gains", "approves"]
PALAVRAS_NEGATIVAS = ["queda", "cai", "despenca", "prejuizo", "perda", "rombo", "calote", "fraude", "hack", "hacker", "ataque", "investigacao", "multa", "rebaixa",
                      "downgrade", "recuperacao judicial", "falencia", "demite", "greve", "acidente", "vazamento", "suspende", "corte de",
                      "inadimpl*", "colapso", "reduz", "recua", "desaba", "plunges", "falls", "drops", "lawsuit", "stolen", "exploit"]
NEGACOES = {"nao", "sem", "nunca", "evita", "descarta"}
PADROES_INJECAO = [r"ignore (todas |as )?(as )?(instru|regras)", r"ignore (all |previous )?instructions", r"system prompt", r"prompt do sistema",
                   r"voce (agora )?e ", r"you are now", r"finja ", r"revele (o )?(prompt|suas instru)", r"\bact as\b", r"<\s*script", r"javascript:"]
MAX_TITULO, MAX_RESUMO = 220, 400


def _limpar_texto(t, limite: int) -> str:
    t = html.unescape(str(t or ""))
    t = re.sub(r"<[^>]*>", " ", t)
    t = "".join(c for c in t if c in "\n\t" or unicodedata.category(c)[0] != "C")
    t = re.sub(r"\s+", " ", t).strip()
    return t[:limite]


def url_segura(u) -> str | None:
    u = str(u or "").strip()
    return u if re.match(r"^https?://[^\s<>\"']+$", u, flags=re.I) and len(u) <= 600 else None


def _data_noticia(txt) -> str | None:
    if not txt:
        return None
    try:
        d = parsedate_to_datetime(str(txt))
        if d.tzinfo is not None:
            d = d.astimezone(timezone.utc).replace(tzinfo=None)
        return d.isoformat(timespec="minutes")
    except Exception:
        try:
            return pd.Timestamp(str(txt)).tz_localize(None).isoformat(timespec="minutes")
        except Exception:
            return None


def parse_rss(xml_texto: str, max_itens: int = 40) -> list[dict]:
    """RSS → [{titulo, fonte, url, data, resumo}]. Tudo que vem de fora é limpo e truncado; entrada inválida → []."""
    if not xml_texto or len(xml_texto) > 3_000_000 or "<!ENTITY" in xml_texto:
        return []
    try:
        raiz = ET.fromstring(xml_texto)
    except ET.ParseError:
        return []
    itens = []
    for it in raiz.iter("item"):
        titulo = _limpar_texto(it.findtext("title"), MAX_TITULO)
        if not titulo:
            continue
        fonte_el = it.find("source")
        fonte = _limpar_texto(fonte_el.text if fonte_el is not None else "", 60)
        if fonte and titulo.endswith(" - " + fonte):
            titulo = titulo[: -len(fonte) - 3].strip()
        elif not fonte and " - " in titulo:
            titulo, _, fonte = titulo.rpartition(" - ")
            fonte = fonte[:60]
        itens.append({"titulo": titulo, "fonte": fonte or "fonte não informada", "url": url_segura(it.findtext("link")),
                      "data": _data_noticia(it.findtext("pubDate")), "resumo": _limpar_texto(it.findtext("description"), MAX_RESUMO)})
        if len(itens) >= max_itens:
            break
    return itens


def _tokens(t: str) -> list[str]:
    return [w for w in _norm(t).split() if len(w) > 2]


def _casa_termo(t: str, termo: str) -> list[int]:
    """Posições de `termo` em `t` (já normalizado). Termo terminado em * casa como início de palavra (radical); os demais, como
    palavra inteira (com plural simples), para "cai" não casar com "caixa" nem "sobe" com "soberano"."""
    stem = termo.endswith("*")
    tn = _norm(termo.rstrip("*"))
    if not tn:
        return []
    padrao = r"(?<![a-z0-9])" + re.escape(tn) + (r"" if stem else r"s?(?![a-z0-9])")
    return [m.start() for m in re.finditer(padrao, t)]


def tom_noticia(texto: str) -> tuple[str, int]:
    """Tom APROXIMADO por léxico (positivo/negativo/neutro) com inversão por negação nas 2 palavras anteriores.
    É interpretação, não fato, e não prevê preço."""
    t = _norm(texto)
    pos = neg = 0
    for lista, sinal in ((PALAVRAS_POSITIVAS, 1), (PALAVRAS_NEGATIVAS, -1)):
        for termo in lista:
            for ini in _casa_termo(t, termo):
                inv = any(a in NEGACOES for a in t[:ini].split()[-2:])
                if (sinal > 0) != inv:
                    pos += 1
                else:
                    neg += 1
    score = pos - neg
    return ("positivo" if score > 0 else "negativo" if score < 0 else "neutro"), score


NOME_GENERICO = {"sa", "ltda", "holding", "participacoes", "brasil", "brasileiro", "brasileira", "banco", "companhia", "cia", "fundo", "investimento",
                 "imobiliario", "etf", "unit", "units", "grupo", "fii", "the", "inc", "corp", "corporation", "company", "token", "coin", "network", "protocol"}


def _tokens_nome(nome: str | None) -> list[str]:
    """Palavras que identificam a empresa/ativo (sem termos genéricos). 'Petróleo Brasileiro S.A. - Petrobras' → petroleo, petrobras."""
    return [w for w in _norm(nome or "").split() if len(w) >= 4 and w not in NOME_GENERICO and not w.isdigit()]


def classificar_noticia(n: dict, ticker: str | None = None, nome: str | None = None, agora: datetime | None = None) -> dict:
    """Acrescenta categorias, tom, relevância (0-100), se pode alterar fundamentos e a marca de conteúdo suspeito."""
    agora = agora or datetime.now()
    titulo = _limpar_texto(n.get("titulo"), MAX_TITULO)
    resumo = _limpar_texto(n.get("resumo"), MAX_RESUMO)
    bruto = _norm(titulo + " " + resumo)
    cats = [c for c, kws in CATEGORIAS_NOTICIA.items() if any(_norm(k) and re.search(r"(?<![a-z0-9])" + re.escape(_norm(k)), bruto) for k in kws)]
    tom, score = tom_noticia(titulo + " " + resumo)
    cit = []
    tn = _norm(titulo)
    for alvo in [ticker] + _tokens_nome(nome):
        a = _norm(alvo or "")
        if a and len(a) >= 3 and re.search(r"(?<![a-z0-9])" + re.escape(a) + r"(?![a-z0-9])", tn):
            cit.append(alvo)
    rel = max([PESO_CATEGORIA.get(c, 10) for c in cats], default=5) + (25 if cit else 0) + (8 if len(cats) >= 2 else 0)
    dias = None
    if n.get("data"):
        try:
            dias = (agora - pd.Timestamp(n["data"]).to_pydatetime().replace(tzinfo=None)).total_seconds() / 86400
        except Exception:
            dias = None
    if dias is not None:
        rel += 20 if dias <= 1 else 12 if dias <= 3 else 5 if dias <= 7 else (-20 if dias > 30 else 0)
    rel = max(0, min(100, int(rel)))
    suspeita = any(re.search(p, _sem_acento(titulo + " " + resumo).lower()) for p in PADROES_INJECAO)
    return {**n, "titulo": titulo, "resumo": resumo, "url": url_segura(n.get("url")), "categorias": cats, "tom": tom, "tom_score": score,
            "relevancia": rel, "nivel": "alta" if rel >= 60 else "media" if rel >= 35 else "baixa",
            "pode_alterar_fundamentos": bool(set(cats) & ALTERA_FUNDAMENTOS), "ativo": ticker, "dias": dias,
            "conteudo_suspeito": suspeita, "natureza": "fato: a publicação existe (fonte e data acima) · tom: interpretação aproximada"}


def deduplicar(noticias: list[dict], limiar: float = 0.7) -> list[dict]:
    """Agrupa títulos quase iguais (Jaccard de palavras ≥ limiar). Mantém o mais relevante/antigo e registra as fontes repetidas."""
    grupos: list[dict] = []
    for n in sorted(noticias, key=lambda x: (-x.get("relevancia", 0), x.get("data") or "")):
        tk = set(_tokens(n.get("titulo", "")))
        achou = None
        for g in grupos:
            u = tk | g["_tk"]
            if u and len(tk & g["_tk"]) / len(u) >= limiar:
                achou = g
                break
        if achou:
            achou["repetidas"] += 1
            if n.get("fonte") and n["fonte"] not in achou["fontes"]:
                achou["fontes"].append(n["fonte"])
        else:
            grupos.append({**n, "_tk": tk, "repetidas": 0, "fontes": [n["fonte"]] if n.get("fonte") else []})
    for g in grupos:
        g.pop("_tk", None)
    return grupos


def processar_noticias(brutas: list[dict], ticker: str | None = None, nome: str | None = None, agora: datetime | None = None) -> list[dict]:
    return sorted(deduplicar([classificar_noticia(n, ticker, nome, agora) for n in brutas or []]),
                  key=lambda x: (-x["relevancia"], x.get("data") or ""), reverse=False)


def resumo_noticia(n: dict) -> str:
    """Resumo objetivo (extrativo): título, fonte e data, categorias e tom. Nada é gerado além do que a fonte publicou."""
    cats = ", ".join(n.get("categorias") or []) or "sem categoria definida"
    rep = f" · {n['repetidas']} repetida(s) agrupada(s)" if n.get("repetidas") else ""
    return f"{n.get('titulo', '')} — {n.get('fonte', '')}, {(n.get('data') or 'data n/d')[:10]} · {cats} · tom {n.get('tom', 'neutro')} (aproximado){rep}"


# =============================================================================== alertas
TIPOS_ALERTA = {
    "variacao_preco": "Variação de preço",
    "nivel_preco": "Rompimento de nível de preço",
    "indicador": "Indicador fundamentalista",
    "dividendo": "Mudança de dividendos",
    "resultado": "Novo resultado financeiro",
    "volatilidade": "Aumento de volatilidade",
    "noticia": "Notícia relevante",
    "risco": "Mudança de risco",
    "liquidez": "Alteração de liquidez",
    "desbloqueio": "Desbloqueio de tokens",
    "vencimento_rf": "Vencimento de renda fixa",
    "carteira": "Alteração na carteira",
}
PRIORIDADES = {"alta": 0, "media": 1, "baixa": 2}
OPERADORES = {">=": lambda a, b: a >= b, "<=": lambda a, b: a <= b, ">": lambda a, b: a > b, "<": lambda a, b: a < b}


def nova_regra(tipo: str, ativo: str = "*", params: dict | None = None, prioridade: str = "media", id_: str | None = None) -> dict:
    if tipo not in TIPOS_ALERTA:
        raise ValueError(f"tipo de alerta desconhecido: {tipo}")
    a = re.sub(r"[^A-Za-z0-9.*\-]", "", str(ativo or "*")).upper()[:24] or "*"
    base = f"{tipo}:{a}:" + ",".join(f"{k}={v}" for k, v in sorted((params or {}).items()))
    return {"id": id_ or re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:80], "tipo": tipo, "ativo": a, "params": dict(params or {}),
            "prioridade": prioridade if prioridade in PRIORIDADES else "media", "ativa": True}


def _alvos(regra: dict, estado: dict) -> list[str]:
    """Ativos da regra no estado. Código sem diferenciar maiúsculas (ids de cripto como 'bitcoin' são minúsculos)."""
    a = regra.get("ativo", "*")
    if a == "*":
        return [k for k in estado if k != "_carteira"]
    return [k for k in estado if k != "_carteira" and str(k).upper() == str(a).upper()]


def avaliar_alertas(regras: list[dict], estado: dict, agora: datetime | None = None) -> list[dict]:
    """Avalia cada regra ativa contra o estado atual {ativo: {...}, '_carteira': {...}}. Só dispara com dado presente.
    Campos lidos do estado de um ativo: preco, var_1d, var_5d, ind{}, div_var_pct, resultado_novo, vol_razao, noticias[],
    anomalias[], bandeiras[], volume_x, desbloqueios[], dias_vencimento. De '_carteira': maior_peso, pesos_classe{}."""
    agora = agora or datetime.now()
    out = []

    def disparo(r, ativo, titulo, texto, valor, dados=None):
        a = ativo if ativo else "carteira"
        out.append({"regra_id": r["id"], "ativo": a, "tipo": r["tipo"], "prioridade": r["prioridade"], "titulo": titulo, "texto": texto,
                    "valor": valor, "assinatura": f"{round(valor, 0) if _ok(valor) else valor}", "data": agora.isoformat(timespec="minutes"),
                    "dados": dados or {}})

    for r in regras or []:
        if not r.get("ativa", True):
            continue
        t, P = r["tipo"], r.get("params", {})
        if t == "carteira":
            c = estado.get("_carteira") or {}
            if P.get("tipo") == "concentracao_max" and _ok(c.get("maior_peso")) and c["maior_peso"] >= float(P.get("limite", 25)):
                disparo(r, None, "Concentração na carteira", f"A maior posição pesa {_br(c['maior_peso'])}% (limite escolhido: {_br(float(P.get('limite', 25)))}%).", c["maior_peso"])
            if P.get("tipo") == "classe_acima":
                pc = c.get("pesos_classe") or {}
                cl = P.get("classe")
                if cl in pc and pc[cl] >= float(P.get("limite", 50)):
                    disparo(r, None, f"{ROTULO_CLASSE.get(cl, cl)} acima do limite", f"{ROTULO_CLASSE.get(cl, cl)} pesam {_br(pc[cl])}% da carteira (limite {_br(float(P.get('limite', 50)))}%).", pc[cl])
            continue
        for tk in _alvos(r, estado):
            e = estado[tk] or {}
            if t == "variacao_preco":
                v = e.get("var_5d") if P.get("janela") == "5d" else e.get("var_1d")
                lim = float(P.get("limite_pct", 5))
                dire = P.get("direcao", "ambas")
                if _ok(v) and ((dire in ("queda", "ambas") and v <= -lim) or (dire in ("alta", "ambas") and v >= lim)):
                    disparo(r, tk, f"{tk}: variação de {_br(v)}%", f"Variação de {_br(v)}% ({'5 pregões' if P.get('janela') == '5d' else '1 pregão'}), limite de {_br(lim)}%.", v)
            elif t == "nivel_preco":
                p, nv = e.get("preco"), P.get("nivel")
                if _ok(p) and _ok(nv):
                    if (P.get("sentido", "acima") == "acima" and p >= nv) or (P.get("sentido") == "abaixo" and p <= nv):
                        disparo(r, tk, f"{tk}: preço {'acima' if P.get('sentido', 'acima') == 'acima' else 'abaixo'} de {_br(nv, 2)}",
                                f"Preço de {_br(p, 2)} cruzou o nível {_br(nv, 2)}.", p)
            elif t == "indicador":
                v = (e.get("ind") or {}).get(P.get("campo"))
                op = OPERADORES.get(P.get("op", ">="))
                if _ok(v) and op and _ok(P.get("valor")) and op(float(v), float(P["valor"])):
                    disparo(r, tk, f"{tk}: {P.get('campo')} {P.get('op')} {_br(float(P['valor']), 2)}", f"{P.get('campo')} está em {_br(v, 2)}.", float(v))
            elif t == "dividendo":
                v = e.get("div_var_pct")
                if _ok(v) and abs(v) >= float(P.get("limite_pct", 20)):
                    disparo(r, tk, f"{tk}: dividendos {'subiram' if v > 0 else 'caíram'} {_br(abs(v))}%", "Proventos dos últimos 12 meses frente aos 12 meses anteriores.", v)
            elif t == "resultado":
                if e.get("resultado_novo"):
                    disparo(r, tk, f"{tk}: novo resultado financeiro", f"Novo exercício disponível ({e['resultado_novo']}).", str(e["resultado_novo"]))
            elif t == "volatilidade":
                v = e.get("vol_razao")
                if _ok(v) and v >= float(P.get("razao", 1.8)):
                    disparo(r, tk, f"{tk}: volatilidade {_br(v)}× a normal", "Volatilidade de 20 pregões contra a de 120.", v)
            elif t == "noticia":
                mini = float(P.get("relevancia_min", 60))
                for n in e.get("noticias") or []:
                    if n.get("relevancia", 0) >= mini and (not P.get("categoria") or P["categoria"] in (n.get("categorias") or [])) and not n.get("conteudo_suspeito"):
                        disparo(r, tk, f"{tk}: {n['titulo'][:90]}", resumo_noticia(n), n["relevancia"], {"url": n.get("url"), "fonte": n.get("fonte")})
                        break
            elif t == "risco":
                graves = [a for a in (e.get("anomalias") or []) if a.get("sentido") == "negativo" and PRIORIDADES.get(a.get("gravidade"), 3) <= PRIORIDADES.get(P.get("gravidade_min", "media"), 1)]
                if graves or (e.get("bandeiras") and P.get("incluir_bandeiras", True)):
                    txt = graves[0]["texto"] if graves else e["bandeiras"][0]
                    disparo(r, tk, f"{tk}: mudança de risco", txt, len(graves) + len(e.get("bandeiras") or []))
            elif t == "liquidez":
                v = e.get("volume_x")
                if _ok(v) and (v >= float(P.get("alta_x", 3)) or v <= float(P.get("baixa_x", 0.2))):
                    disparo(r, tk, f"{tk}: volume {_br(v)}× a mediana", "Salto ou queda forte do volume negociado.", v)
            elif t == "desbloqueio":
                for d in e.get("desbloqueios") or []:
                    if _ok(d.get("dias")) and 0 <= d["dias"] <= float(P.get("dias", 14)):
                        disparo(r, tk, f"{tk}: desbloqueio em {int(d['dias'])} dia(s)", f"Evento informado com fonte: {d.get('fonte', 'fonte n/d')}.", d["dias"])
                        break
            elif t == "vencimento_rf":
                v = e.get("dias_vencimento")
                if _ok(v) and 0 <= v <= float(P.get("dias", 30)):
                    disparo(r, tk, f"{tk}: vence em {int(v)} dia(s)", "Planeje o reinvestimento ou a necessidade de caixa.", v)
    return sorted(out, key=lambda x: (PRIORIDADES.get(x["prioridade"], 3), x["ativo"]))


def filtrar_repetidos(disparos: list[dict], historico: list[dict], agora: datetime | None = None, frequencia: str = "diaria",
                      max_historico: int = 300, tipos_permitidos: list | None = None) -> tuple[list[dict], list[dict], int]:
    """Evita alertas repetidos: o mesmo (regra, ativo, assinatura) só volta depois do período da frequência escolhida.
    Se o valor mudar de faixa (assinatura diferente), o alerta passa de novo. Devolve (novos, histórico atualizado, suprimidos)."""
    agora = agora or datetime.now()
    horas = FREQUENCIAS.get(frequencia, 24)
    vistos: dict = {}
    for h in historico or []:
        try:
            quando = datetime.fromisoformat(h["quando"])
        except Exception:
            continue
        chave = (h.get("regra_id"), h.get("ativo"), h.get("assinatura"))
        if chave not in vistos or quando > vistos[chave]:
            vistos[chave] = quando
    novos, supr = [], 0
    for d in disparos:
        if tipos_permitidos and d["tipo"] not in tipos_permitidos:
            continue
        chave = (d["regra_id"], d["ativo"], d["assinatura"])
        ult = vistos.get(chave)
        if ult is not None and (agora - ult) < timedelta(hours=horas):
            supr += 1
            continue
        vistos[chave] = agora
        novos.append(d)
    hist = list(historico or []) + [{"regra_id": d["regra_id"], "ativo": d["ativo"], "assinatura": d["assinatura"], "tipo": d["tipo"],
                                     "prioridade": d["prioridade"], "titulo": d["titulo"], "texto": d["texto"],
                                     "quando": agora.isoformat(timespec="seconds")} for d in novos]
    return novos, hist[-max_historico:], supr


# =============================================================================== rankings (uma classe por vez)
def justificativa(item: dict) -> str:
    pil = {k: v for k, v in (item.get("pilares") or {}).items() if _ok(v)}
    if not pil:
        return "Sem pilares com dado suficiente para justificar a posição."
    ordem = sorted(pil.items(), key=lambda x: -x[1])
    fortes = ", ".join(f"{k} ({v:.0f})" for k, v in ordem[:2])
    fraco = ordem[-1]
    txt = f"Pontos fortes: {fortes}."
    if len(ordem) > 1 and fraco[1] < 50:
        txt += f" Ponto mais fraco: {fraco[0]} ({fraco[1]:.0f})."
    if item.get("cobertura") is not None and item["cobertura"] < 0.7:
        txt += f" Cobertura de dados de {item['cobertura'] * 100:.0f}%: nota provisória."
    return txt


def montar_ranking(itens: list[dict], classe: str, titulo: str | None = None, prefs: dict | None = None) -> dict:
    """Ranking SÓ de uma classe (ValueError se houver mistura). itens: {id, nome, classe, nota, pilares, pesos, cobertura,
    provisoria, data_ref, fonte, riscos[], subgrupo}. Com prioridades do usuário, a nota é reponderada (e a original é mantida)."""
    mistura = {i.get("classe") for i in itens if i.get("classe")} - {classe}
    if mistura:
        raise ValueError(f"Ranking de {classe} não pode misturar classes: {sorted(mistura)}")
    prefs = normalizar_prefs(prefs)
    pri = prefs["pilares_prioritarios"]
    linhas = []
    for i in itens:
        nota = i.get("nota")
        nota_p = nota_personalizada(i.get("pilares"), i.get("pesos"), pri) if pri and _ok(nota) else nota
        linhas.append({**i, "nota_base": nota, "nota": nota_p, "justificativa": justificativa(i)})
    com = sorted([l for l in linhas if _ok(l["nota"])], key=lambda l: -l["nota"])
    sem = [l for l in linhas if not _ok(l["nota"])]
    ranking = [{**l, "posicao": n + 1} for n, l in enumerate(com)] + [{**l, "posicao": None} for l in sem]
    datas = [i.get("data_ref") for i in itens if i.get("data_ref")]
    return {"classe": classe, "titulo": titulo or f"{ROTULO_CLASSE.get(classe, classe)}: nota composta", "itens": ranking,
            "criterios": FILTROS_CLASSE.get(classe, ""), "indicadores": sorted({k for i in itens for k in (i.get("pilares") or {})}),
            "atualizacao": max(datas) if datas else None, "prioridades_aplicadas": pri,
            "aviso": "Ranking dentro da classe. Nota é triagem educacional; não é ordem de compra."}


def ranking_por_valor(itens: list[dict], classe: str, chave: str, rotulo: str, crescente: bool, ind_rotulo: str, unidade: str = "") -> dict:
    """Rankings temáticos (custo, consistência de renda, utilização...) por um único indicador, só com quem tem o dado."""
    mistura = {i.get("classe") for i in itens if i.get("classe")} - {classe}
    if mistura:
        raise ValueError(f"Ranking de {classe} não pode misturar classes: {sorted(mistura)}")
    com = [(i, (i.get("ind") or {}).get(chave)) for i in itens]
    ok = sorted([(i, v) for i, v in com if _ok(v)], key=lambda x: x[1], reverse=not crescente)
    sem = [i for i, v in com if not _ok(v)]
    linhas = [{"posicao": n + 1, "id": i["id"], "nome": i.get("nome"), "valor": float(v), "unidade": unidade, "data_ref": i.get("data_ref"),
               "fonte": i.get("fonte"), "riscos": i.get("riscos") or [], "justificativa": f"{ind_rotulo}: {_br(v, 2)}{unidade}."}
              for n, (i, v) in enumerate(ok)]
    return {"classe": classe, "titulo": rotulo, "itens": linhas, "sem_dado": [i["id"] for i in sem], "criterios": ind_rotulo,
            "atualizacao": max([i.get("data_ref") for i in itens if i.get("data_ref")], default=None),
            "aviso": "Um único indicador não define qualidade: use junto com a nota composta."}


# =============================================================================== monitoramento: o que mudou
LIM_MUDANCA = {"nota": 10.0, "preco_pct": 10.0, "concentracao_pp": 3.0, "correlacao": 0.10, "dy_pct": 25.0}


def fotografia(ativo: dict, agora: datetime | None = None) -> dict:
    """Parte mínima de um ativo que vale guardar para comparar depois (sem posição, quantidade ou patrimônio)."""
    agora = agora or datetime.now()
    return {"data": agora.date().isoformat(), "nota": ativo.get("nota"), "preco": ativo.get("preco"), "status": ativo.get("status"),
            "bandeiras": list(ativo.get("bandeiras") or [])[:8],
            "achados_neg": sorted(a["chave"] for a in ativo.get("achados") or [] if a.get("tom") == "atencao" and a.get("chave"))[:12],
            "achados_pos": sorted(a["chave"] for a in ativo.get("achados") or [] if a.get("tom") == "positivo" and a.get("chave"))[:12],
            "dy": (ativo.get("ind") or {}).get("dy"), "classe": ativo.get("classe")}


def comparar_fotografias(antes: dict | None, depois: dict | None, limites: dict | None = None) -> list[dict]:
    """Diferenças relevantes entre duas fotografias {ativo: foto}. Ativo novo ou sem fotografia anterior não gera 'mudança'."""
    L = {**LIM_MUDANCA, **(limites or {})}
    out = []
    for tk, d in (depois or {}).items():
        a = (antes or {}).get(tk)
        if not a:
            continue
        ref = f"desde {a.get('data', 'a leitura anterior')}"
        if _ok(a.get("nota")) and _ok(d.get("nota")) and abs(d["nota"] - a["nota"]) >= L["nota"]:
            up = d["nota"] > a["nota"]
            out.append({"ativo": tk, "tipo": "nota", "sentido": "positivo" if up else "negativo",
                        "texto": f"Nota {'subiu' if up else 'caiu'} de {a['nota']:.0f} para {d['nota']:.0f} {ref}."})
        novas = [b for b in d.get("bandeiras") or [] if b not in (a.get("bandeiras") or [])]
        for b in novas[:2]:
            out.append({"ativo": tk, "tipo": "risco_novo", "sentido": "negativo", "texto": f"Nova bandeira de risco {ref}: {b}."})
        for b in [x for x in a.get("bandeiras") or [] if x not in (d.get("bandeiras") or [])][:2]:
            out.append({"ativo": tk, "tipo": "risco_resolvido", "sentido": "positivo", "texto": f"Bandeira deixou de aparecer {ref}: {b}."})
        for k in [x for x in d.get("achados_neg") or [] if x not in (a.get("achados_neg") or [])][:2]:
            out.append({"ativo": tk, "tipo": "deterioracao", "sentido": "negativo", "texto": f"Novo sinal de deterioração nos fundamentos {ref}: {k.replace('_', ' ')}."})
        for k in [x for x in d.get("achados_pos") or [] if x not in (a.get("achados_pos") or [])][:2]:
            out.append({"ativo": tk, "tipo": "melhora", "sentido": "positivo", "texto": f"Novo sinal de melhora nos fundamentos {ref}: {k.replace('_', ' ')}."})
        if _ok(a.get("preco")) and _ok(d.get("preco")) and a["preco"] > 0:
            v = (d["preco"] / a["preco"] - 1) * 100
            if abs(v) >= L["preco_pct"]:
                out.append({"ativo": tk, "tipo": "preco", "sentido": "positivo" if v > 0 else "negativo", "texto": f"Preço variou {_br(v)}% {ref}."})
        if _ok(a.get("dy")) and _ok(d.get("dy")) and a["dy"] > 0:
            v = (d["dy"] / a["dy"] - 1) * 100
            if abs(v) >= L["dy_pct"]:
                out.append({"ativo": tk, "tipo": "dividendos", "sentido": "positivo" if v > 0 else "negativo", "texto": f"Dividend yield variou {_br(v)}% {ref}."})
    return out


def comparar_carteira(antes: dict | None, depois: dict | None, limites: dict | None = None) -> list[dict]:
    """Concentração crescente e correlação em alta entre duas leituras da carteira
    ({maior_peso (%), n_efetivo, corr_media, data})."""
    L = {**LIM_MUDANCA, **(limites or {})}
    out = []
    if not antes or not depois:
        return out
    ref = f"desde {antes.get('data', 'a leitura anterior')}"
    if _ok(antes.get("maior_peso")) and _ok(depois.get("maior_peso")) and depois["maior_peso"] - antes["maior_peso"] >= L["concentracao_pp"]:
        out.append({"ativo": "carteira", "tipo": "concentracao", "sentido": "negativo",
                    "texto": f"A maior posição passou de {_br(antes['maior_peso'])}% para {_br(depois['maior_peso'])}% {ref}."})
    if _ok(antes.get("corr_media")) and _ok(depois.get("corr_media")) and depois["corr_media"] - antes["corr_media"] >= L["correlacao"]:
        out.append({"ativo": "carteira", "tipo": "correlacao", "sentido": "negativo",
                    "texto": f"A correlação média entre os ativos subiu de {_br(antes['corr_media'], 2)} para {_br(depois['corr_media'], 2)} {ref}: menos diversificação."})
    if _ok(antes.get("n_efetivo")) and _ok(depois.get("n_efetivo")) and depois["n_efetivo"] <= antes["n_efetivo"] - 0.5:
        out.append({"ativo": "carteira", "tipo": "diversificacao", "sentido": "negativo",
                    "texto": f"O número efetivo de posições caiu de {_br(antes['n_efetivo'])} para {_br(depois['n_efetivo'])} {ref}."})
    return out


# =============================================================================== assistente (regras sobre dados carregados)
_PEDIDO_INDICACAO = re.compile(r"\b(comprar|compro|vender|vendo|devo (comprar|vender|manter)|vale a pena|qual (a )?melhor (acao|ativo|fii|investimento)|onde invest\w*|me indica|indique|recomend\w*)", re.I)


def _linhas(lista, n=6):
    return [f"- {x}" for x in lista[:n]]


def responder(pergunta: str, ctx: dict | None) -> dict:
    """Responde SÓ com o que está em `ctx` (ativos analisados, carteira, notícias, alertas, mudanças). Cada resposta diz o que
    foi consultado, a data da leitura e o que faltou. Pedido de compra/venda é recusado com gentileza e redirecionado aos dados."""
    ctx = ctx or {}
    q = _norm(pergunta)
    ativos = ctx.get("ativos") or []
    gerado = ctx.get("gerado_em")
    cab = f"Dados do app lidos em {gerado[:16].replace('T', ' ')}" if gerado else "Sem leitura de dados carregada"
    consultado = [f"{len(ativos)} ativo(s) analisado(s)"] if ativos else []
    if ctx.get("carteira"):
        consultado.append("carteira (Passo 12)")
    if ctx.get("noticias"):
        consultado.append(f"{len(ctx['noticias'])} notícia(s)")
    if ctx.get("mudancas"):
        consultado.append(f"{len(ctx['mudancas'])} mudança(s) detectada(s)")
    rodape = f"Consultei: {', '.join(consultado)}." if consultado else "Não consultei nenhum dado: a central ainda não foi atualizada."

    def resp(texto, linhas=None, falta=False):
        return {"texto": texto, "linhas": linhas or [], "referencia": cab, "consultado": rodape, "sem_dados": falta,
                "limite": "Leitura de dados, não recomendação."}

    if not q:
        return resp("Escreva uma pergunta sobre os ativos que você acompanha.", falta=True)
    if _PEDIDO_INDICACAO.search(q):
        return resp("Eu não indico compra ou venda. Posso mostrar o que os dados do app dizem: ativos com sinais favoráveis em vários "
                    "critérios, os riscos de cada um, o que mudou e o que merece atenção. Experimente: “quais ativos apresentaram melhora "
                    "nos fundamentos?” ou “onde existe concentração excessiva?”.")

    def tem(*pals):
        return any(p in q for p in pals)

    def nome(a):
        return f"{a['id']} ({ROTULO_CLASSE.get(a.get('classe'), a.get('classe'))})"

    if tem("melhora") and tem("fundament"):
        sel = [a for a in ativos if any(x.get("tom") == "positivo" for x in a.get("achados") or []) and not any(x.get("tom") == "atencao" for x in a.get("achados") or [])]
        if not any(a.get("achados") for a in ativos):
            return resp("Não tenho diagnóstico de fundamentos carregado (ele existe só para ações com balanço disponível).", falta=True)
        L = [f"{nome(a)}: " + "; ".join(x["titulo"] for x in a["achados"] if x.get("tom") == "positivo")[:160] for a in sel]
        return resp(f"{len(sel)} ativo(s) com sinais de melhora e sem alertas nos fundamentos." if sel else "Nenhum ativo carregado combina melhora e ausência de alertas nos fundamentos.", _linhas(L, 8))
    if tem("risco") and tem("crescent", "aument", "piora", "maior"):
        L = []
        for a in ativos:
            sinais = list(a.get("bandeiras") or []) + [x["texto"] for x in a.get("anomalias") or [] if x.get("sentido") == "negativo"]
            if sinais:
                L.append((len(sinais), f"{nome(a)}: {sinais[0][:150]}"))
        L = [t for _, t in sorted(L, reverse=True)]
        for m in ctx.get("mudancas") or []:
            if m.get("sentido") == "negativo":
                L.append(f"{m['ativo']}: {m['texto']}")
        return resp(f"{len(L)} ponto(s) de risco encontrado(s)." if L else "Nenhuma bandeira de risco ou anomalia negativa nos ativos carregados.", _linhas(L, 8), falta=not ativos)
    if tem("fii") and tem("consist", "rendiment", "renda"):
        fiis = [a for a in ativos if a.get("classe") == "fii"]
        com = sorted([a for a in fiis if _ok((a.get("pilares") or {}).get("Renda"))], key=lambda a: -a["pilares"]["Renda"])
        if not fiis:
            return resp("Não há FIIs entre os ativos carregados. Adicione FIIs aos favoritos ou à carteira.", falta=True)
        return resp("FIIs ordenados pela nota do pilar Renda (Passo 8). Compare só FIIs da mesma estratégia.",
                    _linhas([f"{a['id']}: Renda {a['pilares']['Renda']:.0f}/100 · DY {_br((a.get('ind') or {}).get('dy'))}%" for a in com], 8))
    if tem("cripto") and tem("utiliza", "adoc", "uso", "crescimento"):
        c = [a for a in ativos if a.get("classe") == "cripto"]
        com = sorted([a for a in c if _ok((a.get("ind") or {}).get("tvl"))], key=lambda a: -a["ind"]["tvl"])
        if not c:
            return resp("Não há criptomoedas entre os ativos carregados.", falta=True)
        if not com:
            return resp("As criptomoedas carregadas não têm dado de utilização (TVL) nas fontes integradas; não vou estimar.", falta=True)
        return resp("Utilização medida pelo TVL (DefiLlama) onde existe. Não mede toda forma de uso de uma rede.",
                    _linhas([f"{a['id']}: TVL US$ {_br(a['ind']['tvl'] / 1e9, 2)} bi" for a in com], 8))
    if tem("etf") and tem("custo", "taxa", "barato"):
        e = [a for a in ativos if a.get("classe") == "etf"]
        com = sorted([a for a in e if _ok((a.get("ind") or {}).get("taxa_adm"))], key=lambda a: a["ind"]["taxa_adm"])
        if not e:
            return resp("Não há ETFs entre os ativos carregados.", falta=True)
        if not com:
            return resp("Os ETFs carregados não trazem a taxa de administração nas fontes integradas; não vou inventar o custo.", falta=True)
        return resp("ETFs ordenados pela taxa de administração (menor primeiro).", _linhas([f"{a['id']}: {_br(a['ind']['taxa_adm'], 2)}% a.a." for a in com], 8))
    if tem("renda fixa", "titulo", "tesouro"):
        r = sorted([a for a in ativos if a.get("classe") == "renda_fixa" and _ok(a.get("nota"))], key=lambda a: -a["nota"])
        if not r:
            return resp("Não há títulos de renda fixa analisados entre os ativos carregados.", falta=True)
        return resp("Títulos ordenados pela nota educacional do Passo 11 (retorno real esperado, crédito, liquidez e risco de mercado).",
                    _linhas([f"{a['id']}: nota {a['nota']:.0f}/100. {justificativa(a)}" for a in r], 8))
    if tem("minha carteira", "como esta minha", "carteira atual"):
        c = ctx.get("carteira")
        if not c:
            return resp("A carteira ainda não foi lida: abra a página Gestão de carteira e volte à central.", falta=True)
        return resp(c.get("resumo") or "Resumo da carteira indisponível.", _linhas(c.get("pontos") or [], 8))
    if tem("concentra"):
        c = ctx.get("carteira") or {}
        L = c.get("concentracoes") or []
        if not c:
            return resp("A carteira ainda não foi lida: abra a página Gestão de carteira e volte à central.", falta=True)
        return resp("Concentrações identificadas na carteira (Passo 12)." if L else "Nenhuma concentração acima dos limites foi identificada.", _linhas(L, 8))
    if tem("mudou", "mudanca", "novidade", "acompanho"):
        L = [f"{m['ativo']}: {m['texto']}" for m in ctx.get("mudancas") or []]
        return resp("Mudanças desde a leitura anterior." if L else "Nenhuma mudança relevante desde a leitura anterior (ou ainda não há leitura anterior para comparar).", _linhas(L, 10), falta=not ativos)
    if tem("acontecimento", "atencao", "noticia", "merecem"):
        n = sorted(ctx.get("noticias") or [], key=lambda x: -x.get("relevancia", 0))
        L = [f"{x.get('ativo') or 'geral'}: {resumo_noticia(x)}" for x in n if x.get("relevancia", 0) >= 35 and not x.get("conteudo_suspeito")]
        for al in ctx.get("alertas") or []:
            L.append(f"Alerta {al['prioridade']}: {al['titulo']}")
        return resp("Itens que mais pedem atenção agora (notícias por relevância e alertas ativos)." if L else "Sem notícias relevantes ou alertas nas fontes consultadas.", _linhas(L, 10), falta=not L)
    return resp("Posso responder sobre: melhora nos fundamentos, riscos crescentes, FIIs com renda consistente, utilização de criptomoedas, "
                "custos de ETFs, títulos de renda fixa, a situação e a concentração da sua carteira, o que mudou e o que merece atenção.")


# =============================================================================== relatório
def relatorio_markdown(ctx: dict, titulo: str = "Relatório de inteligência") -> str:
    """Relatório em Markdown, só com o que há em `ctx` (cada item com fonte/data). Itens externos são escapados."""
    gerado = (ctx.get("gerado_em") or "")[:16].replace("T", " ") or "data n/d"
    ativos = ctx.get("ativos") or []
    L = [f"# {titulo}", "", f"*Gerado em {gerado}. Fontes: as já integradas ao app (Yahoo Finance, CVM, Tesouro, CoinGecko/DefiLlama, Fundamentus, Google Notícias).*", ""]
    est = [a for a in ativos if a.get("status") == "merece_estudo"]
    L += ["## Sinais para estudar", "(Evidências em vários critérios; não é recomendação.)", ""]
    L += [f"- **{a['id']}** ({ROTULO_CLASSE.get(a.get('classe'), '')}): {a.get('texto_oportunidade', '')}" for a in est] or ["- Nenhum ativo atingiu o mínimo de evidências."]
    L += ["", "## Riscos e anomalias", ""]
    riscos = []
    for a in ativos:
        for b in a.get("bandeiras") or []:
            riscos.append(f"- **{a['id']}**: {b} *(bandeira)*")
        for x in a.get("anomalias") or []:
            if x.get("sentido") == "negativo":
                riscos.append(f"- **{a['id']}**: {x['texto']} *({x.get('natureza', '')}; {x.get('data', '')})*")
    L += riscos or ["- Nenhuma bandeira ou anomalia negativa nos ativos analisados."]
    L += ["", "## O que mudou", ""]
    L += [f"- **{m['ativo']}**: {m['texto']}" for m in ctx.get("mudancas") or []] or ["- Sem mudanças relevantes desde a leitura anterior."]
    L += ["", "## Notícias relevantes", ""]
    for n in sorted(ctx.get("noticias") or [], key=lambda x: -x.get("relevancia", 0))[:8]:
        if n.get("relevancia", 0) < 35 or n.get("conteudo_suspeito"):
            continue
        L.append(f"- {escapar_md(resumo_noticia(n))}" + (f" [fonte]({n['url']})" if n.get("url") else ""))
    if L[-1] == "":
        L.append("- Sem notícias relevantes nas fontes consultadas.")
    L += ["", "## Alertas", ""]
    L += [f"- **{a['prioridade'].upper()}** · {a['titulo']}: {a['texto']}" for a in ctx.get("alertas") or []] or ["- Nenhum alerta novo."]
    c = ctx.get("carteira")
    if c:
        L += ["", "## Carteira", "", c.get("resumo") or ""]
        L += [f"- {p}" for p in (c.get("pontos") or [])[:8]]
    L += ["", "## Limitações", ""]
    L += [f"- {x}" for x in LIMITACOES_PROJECAO] + [f"- {AVISO_LEGAL}"]
    return "\n".join(L).replace("\n\n\n", "\n\n")
