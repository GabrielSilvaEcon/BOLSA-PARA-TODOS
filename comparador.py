"""
Motor universal de comparação de ativos (puro: sem Streamlit e sem rede; recebe dados já coletados).

Estrutura (cada classe de ativo tem as suas métricas e regras; a infraestrutura de normalização, validação,
comparação e apresentação é compartilhada):

  Ind        um indicador normalizado: valor, origem ("dado" | "calculado" | "estimado"), período e data de referência.
  Ativo      um ativo já normalizado: classe, moeda, data de referência, indicadores, pontuação, avisos.
  Classe     o que cada classe mede (Spec de cada indicador) e se há fonte de dados para ela.
  Pontuacao  nota 0-100 DA CLASSE (nunca comparável com a de outra classe), pilares, pesos, cobertura e influências.
  comparar() compara dois ou mais Ativo e devolve linhas, ranking por classe, vantagens/desvantagens e alertas.

Para incluir uma nova classe: registrar_classe(Classe(...)) e criar um coletor que devolva Ativo. Nada mais muda.

Regras de honestidade (as mesmas do restante do app):
  - dado ausente = None: não vira zero, não entra na nota e é listado como indisponível;
  - indicador que não faz sentido para o ativo (ex.: dívida/patrimônio de banco) é "não se aplica": não penaliza;
  - notas de classes diferentes usam critérios diferentes e NUNCA são ranqueadas entre si;
  - classes sem fonte de dados (FIIs, fundos, renda fixa) aparecem como indisponíveis; nada é simulado;
  - "melhor indicador" não significa "melhor investimento". A pontuação é educacional, não garante rentabilidade.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime

AVISO_LEGAL = ("Pontuação educacional, calculada com os dados disponíveis e critérios simples de cada classe. Não é "
               "recomendação de investimento e não garante rentabilidade futura.")
DIAS_DESATUALIZADO = 7        # dado de mercado mais velho que isso é sinalizado
DIAS_DATAS_DISTANTES = 5      # datas de referência muito afastadas entre os ativos comparados
COBERTURA_MIN_NOTA = 0.5      # a nota só aparece com pelo menos 50% do peso com dados
COBERTURA_CONFIAVEL = 0.7     # abaixo disso a nota é marcada como provisória


# =============================================================================== modelos
@dataclass
class Ind:
    """Um indicador. valor None = indisponível. aplica=False = não se aplica a este ativo (não penaliza)."""
    valor: float | None
    origem: str = "dado"                 # "dado" (fonte), "calculado" (derivado de dados) ou "estimado"
    periodo: str | None = None           # ex.: "12m", "TTM"
    data_ref: str | None = None          # ISO (AAAA-MM-DD)
    aplica: bool = True


@dataclass
class Spec:
    chave: str
    nome: str
    fmt: str = "num"                     # num | x | pct | pct_s (com sinal) | brl | usd | tend
    direcao: int = 0                     # +1 maior é melhor, -1 menor é melhor, 0 só informativo
    comum: bool = False                  # critério comum a todas as classes (risco, desempenho)
    dica: str = ""


@dataclass
class Pontuacao:
    nota: float | None
    pilares: dict                        # nome do pilar -> nota 0-100 ou None
    pesos: dict                          # nome do pilar -> peso usado
    cobertura: float                     # fração do peso total com dado
    influencias: list = field(default_factory=list)
    metodo: str = ""
    provisoria: bool = False

    @property
    def faixa(self) -> str:
        if self.nota is None:
            return "Dados insuficientes"
        return "Alta" if self.nota >= 70 else ("Média" if self.nota >= 50 else "Baixa")


@dataclass
class Ativo:
    chave: str                           # código (PETR4, AAPL, VOO) ou id da moeda (bitcoin)
    nome: str
    classe: str
    moeda: str | None = None
    data_ref: str | None = None
    fonte: str = ""
    ind: dict = field(default_factory=dict)
    pontuacao: Pontuacao | None = None
    avisos: list = field(default_factory=list)
    erro: str | None = None


@dataclass
class Classe:
    id: str
    nome: str
    specs: list
    suportada: bool = True
    motivo: str = ""                     # por que não é suportada (ou o que falta)
    sem_fonte: list = field(default_factory=list)   # métricas pedidas que o projeto ainda não tem como obter
    criterios: str = ""                  # texto curto sobre como a pontuação é feita
    parcial: str = ""                    # suporte parcial: o que a análise NÃO cobre (a classe tem nota, mas provisória)


# =============================================================================== catálogo de classes
_COMUNS = [
    Spec("ret12m", "Retorno em 12 meses", "pct_s", +1, True, "Variação do preço ajustado nos últimos 12 meses, na moeda do ativo."),
    Spec("vol", "Volatilidade anual", "pct", -1, True, "Desvio-padrão dos retornos diários, anualizado (12 meses)."),
    Spec("dd_max", "Pior queda em 12 meses", "pct_s", +1, True, "Maior queda do pico ao fundo nos últimos 12 meses."),
]

CLASSES: dict[str, Classe] = {}


def registrar_classe(c: Classe) -> Classe:
    CLASSES[c.id] = c
    return c


registrar_classe(Classe(
    "acao", "Ações", [
        Spec("pl", "P/L", "x", -1), Spec("pvp", "P/VP", "x", -1), Spec("ev_ebitda", "EV/EBITDA", "x", -1),
        Spec("roe", "ROE", "pct", +1), Spec("margem_liq", "Margem líquida", "pct", +1),
        Spec("dy", "Dividend Yield (12m)", "pct", +1), Spec("div_pl", "Dívida/Patrimônio", "pct", -1),
        Spec("margem_graham", "Margem de segurança (Graham)", "pct_s", +1,
             dica="(preço justo − preço) ÷ preço justo. Modelo simplificado: empresas de crescimento ficam muito negativas."),
        *_COMUNS],
    sem_fonte=["ROIC", "Dívida líquida/EBITDA", "Crescimento de receita e de lucro"],
    criterios="Nota do Ranking do app (valor, qualidade, dividendos, solidez, tendência e risco), com os pesos do perfil escolhido."))

registrar_classe(Classe(
    "etf", "ETFs", [
        Spec("ret1m", "Retorno em 1 mês", "pct_s", 0), Spec("ret6m", "Retorno em 6 meses", "pct_s", +1),
        Spec("queda_pico", "Distância do pico (12m)", "pct_s", +1), Spec("tend", "Tendência (SMA 50/200)", "tend", 0),
        *_COMUNS],
    sem_fonte=["Taxa de administração", "Patrimônio sob gestão", "Tracking error", "Composição da carteira",
               "Exposição geográfica e setorial"],
    criterios="Retorno (35%), risco (35%), tendência (15%) e custos/porte (15%, hoje sem fonte: fica fora da nota)."))

registrar_classe(Classe(
    "cripto", "Criptomoedas", [
        Spec("mcap", "Valor de mercado", "usd", +1, dica="Quanto maior, em geral mais liquidez e maturidade."),
        Spec("vol24", "Volume em 24h", "usd", +1),
        Spec("liquidez", "Volume ÷ valor de mercado", "pct", +1, dica="Calculado: giro diário em relação ao tamanho."),
        Spec("ret30", "Variação em 30 dias", "pct_s", 0),
        Spec("circ_pct", "Oferta circulante ÷ máxima", "pct", 0, dica="Calculado. Só existe para moedas com oferta máxima."),
        *_COMUNS],
    sem_fonte=["Segurança e descentralização (só Bitcoin, via blockchain.com)", "Dominância"],
    criterios="Nota da Análise Fundamentalista de cripto (7 pilares, régua própria por tipo: Bitcoin, stablecoin, blockchain, DeFi)."))

registrar_classe(Classe(
    "fii", "Fundos imobiliários (FIIs)", [
        Spec("dy12m", "Dividend Yield (12m)", "pct", +1, dica="Calculado: rendimentos pagos nos últimos 12 meses ÷ preço atual. "
             "DY muito alto pode indicar queda forte do preço ou rendimento extraordinário."),
        Spec("meses_pagos", "Meses com distribuição (12m)", "int", +1, dica="Quantos dos últimos 12 meses tiveram rendimento pago."),
        Spec("liq", "Liquidez média diária (90d)", "brl_g", +1, dica="Média de preço × volume negociado por dia, últimos 90 dias."),
        Spec("pvp", "P/VP", "x", -1, dica="Exige o valor patrimonial da cota (informe mensal da CVM): ainda sem fonte no app."),
        *_COMUNS],
    parcial="sem P/VP, valor patrimonial, vacância, contratos e concentração de imóveis (sem fonte de dados no app). "
            "Indicadores calculados a partir do Yahoo Finance (preço, volume e rendimentos).",
    sem_fonte=["P/VP e valor patrimonial por cota", "Vacância física e financeira", "Prazo dos contratos",
               "Diversificação de imóveis e inquilinos", "Qualidade dos ativos", "Riscos de concentração"],
    criterios="Renda (25%), liquidez (10%), risco (20%), retorno (10%); P/VP (20%) e qualidade dos ativos (15%) sem fonte: "
              "a nota é sempre provisória."))
registrar_classe(Classe(
    "fundo", "Fundos de investimento", list(_COMUNS), suportada=False,
    motivo="Os dados de fundos viriam da CVM (cadastro e informe diário), que ainda não está integrada.",
    sem_fonte=["Rentabilidade", "Taxas", "Patrimônio", "Prazo de resgate", "Benchmark"],
    criterios="Sem nota própria."))
registrar_classe(Classe(
    "renda_fixa", "Renda fixa", [], suportada=False,
    motivo="O app tem calculadoras de renda fixa, mas não uma base de títulos para comparar (taxa, vencimento, risco de crédito).",
    sem_fonte=["Taxa contratada", "Vencimento", "Duration", "Risco de crédito", "Garantias"],
    criterios="Sem nota própria."))

# códigos que o app trata como ETF (o usuário pode digitar outros; o coletor confirma pelo tipo do Yahoo, quando houver)
ETFS_CONHECIDOS = {
    "BOVA11", "IVVB11", "SMAL11", "BOVV11", "HASH11", "GOLD11", "DIVO11", "FIND11", "MATB11", "ECOO11", "NASD11",
    "SPXI11", "XINA11", "QBTC11", "ETHE11", "BOVX11", "PIBB11", "ISUS11", "TECK11",
    "VOO", "QQQ", "SCHD", "VT", "SPY", "VTI", "IVV", "VEA", "VWO", "BND", "AGG", "GLD", "IWM", "DIA", "VNQ", "ARKK", "XLK",
    "XLF", "XLE", "VIG", "VYM", "JEPI", "SOXX", "SMH"}
_B3 = re.compile(r"[A-Z]{4}\d{1,2}")
_FII = re.compile(r"[A-Z]{4}11")


def identificar_classe(codigo: str, catalogo_acoes=(), tipo_externo: str | None = None) -> tuple[str, str]:
    """(classe, confiança). Confiança "alta" quando vem de um tipo explícito ou de lista conhecida; "provável" quando
    é só pelo formato do código (ex.: XXXX11 que não está no catálogo de ações é provavelmente um FII)."""
    c = str(codigo or "").upper().strip().replace(".SA", "")
    t = (tipo_externo or "").upper()
    if t == "ETF":
        return "etf", "alta"
    if t in ("CRYPTOCURRENCY", "CRIPTO"):
        return "cripto", "alta"
    if t == "MUTUALFUND":
        return "fundo", "alta"
    if "/" in c or c.endswith("-USD") or c.endswith("-BRL"):
        return "cripto", "provável"
    if c in ETFS_CONHECIDOS:
        return "etf", "alta"
    if c in set(catalogo_acoes) or t == "EQUITY":
        return "acao", "alta"
    if _FII.fullmatch(c):
        return "fii", "provável"
    return "acao", "provável"


def classe(id_: str) -> Classe:
    return CLASSES[id_]


# =============================================================================== números e formatação
def _ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def escala(x, ruim, bom):
    """0-100 linear entre 'ruim' (0) e 'bom' (100); funciona nos dois sentidos. None se x não for número."""
    if not _ok(x):
        return None
    if bom == ruim:
        return None
    return max(0.0, min(100.0, (x - ruim) / (bom - ruim) * 100.0))


def _media(valores):
    v = [x for x in valores if x is not None]
    return sum(v) / len(v) if v else None


def _virg(txt: str) -> str:
    return txt.replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_valor(v, fmt: str) -> str:
    """Texto no padrão brasileiro; indisponível nunca vira zero."""
    if not _ok(v):
        return "indisponível"
    if fmt == "pct":
        return _virg(f"{v:,.1f}") + "%"
    if fmt == "pct_s":
        return _virg(f"{v:+,.1f}") + "%"
    if fmt == "x":
        return _virg(f"{v:,.2f}")
    if fmt == "brl":
        return "R$ " + _virg(f"{v:,.2f}")
    if fmt == "usd":
        return "US$ " + _grande(v)
    if fmt == "tend":
        return {2: "▲ Alta", 1: "► Lateral", 0: "▼ Baixa"}.get(int(v), "indisponível")
    if fmt == "int":
        return f"{v:.0f}"
    if fmt == "brl_g":
        return "R$ " + _grande(v)
    return _virg(f"{v:,.2f}")


def _grande(v: float) -> str:
    for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi")):
        if abs(v) >= lim:
            return _virg(f"{v / lim:,.2f}") + suf
    return _virg(f"{v:,.2f}")


# =============================================================================== métricas de preço (períodos equivalentes)
def metricas_preco(close, dias: int = 365) -> dict:
    """Retorno, volatilidade e queda em uma MESMA janela de calendário (12 meses), para qualquer classe.
    `close`: pandas.Series de fechamento com índice de datas. Ações (≈252 pregões) e cripto (365 dias) ficam
    comparáveis porque a janela é por dias corridos e a anualização usa o nº real de observações por ano.
    Devolve só o que dá para calcular; o resto fica None. Nada é estimado fora da janela."""
    out = {"ret1m": None, "ret6m": None, "ret12m": None, "vol": None, "dd_max": None, "queda_pico": None,
           "tend": None, "data_ref": None, "n": 0, "janela_dias": None}
    try:
        c = close.dropna()
        c = c[c > 0]
    except Exception:
        return out
    if len(c) < 30:
        return out
    fim = c.index.max()
    out["data_ref"] = _iso(fim)
    import pandas as pd
    j = c[c.index >= fim - pd.Timedelta(days=dias)]
    out["n"] = len(j)
    out["janela_dias"] = int((j.index.max() - j.index.min()).days)
    if len(j) < 30 or out["janela_dias"] < dias * 0.9:
        return out                                    # histórico curto: não comparar 12m com menos de ~11 meses
    ult = float(j.iloc[-1])
    out["ret12m"] = (ult / float(j.iloc[0]) - 1) * 100
    for chave, d in (("ret1m", 30), ("ret6m", 182)):
        ant = j[j.index <= fim - pd.Timedelta(days=d)]
        if len(ant):
            out[chave] = (ult / float(ant.iloc[-1]) - 1) * 100
    por_ano = len(j) / (out["janela_dias"] / 365.25)
    r = j.pct_change().dropna()
    if len(r) >= 20:
        out["vol"] = float(r.std() * math.sqrt(por_ano) * 100)
    pico = j.cummax()
    out["dd_max"] = float((j / pico - 1).min() * 100)
    out["queda_pico"] = float((ult / float(pico.iloc[-1]) - 1) * 100)
    if len(c) >= 200:
        mm50, mm200 = c.rolling(50).mean().iloc[-1], c.rolling(200).mean().iloc[-1]
        if _ok(float(mm50)) and _ok(float(mm200)) and mm200 > 0:
            out["tend"] = int(float(c.iloc[-1]) > mm200) + int(mm50 > mm200)
    return out


def _iso(x) -> str | None:
    try:
        return x.date().isoformat()
    except Exception:
        try:
            return str(x)[:10]
        except Exception:
            return None


def inds_de_preco(m: dict, origem: str = "calculado") -> dict:
    """Converte o dicionário de metricas_preco em indicadores normalizados (calculados a partir do preço)."""
    out = {}
    for k in ("ret1m", "ret6m", "ret12m", "vol", "dd_max", "queda_pico", "tend"):
        per = "12m" if k in ("ret12m", "vol", "dd_max", "queda_pico") else None
        out[k] = Ind(m.get(k), origem, per, m.get("data_ref"))
    return out


# =============================================================================== pontuação por classe
def _pontuar(pilares: dict, pesos: dict, textos: dict, metodo: str) -> Pontuacao:
    """Média ponderada só dos pilares com dado; calcula a cobertura e marca nota provisória/insuficiente."""
    total = sum(p for p in pesos.values() if p > 0)
    usados = {k: v for k, v in pilares.items() if v is not None and pesos.get(k, 0) > 0}
    w = sum(pesos[k] for k in usados)
    cob = w / total if total else 0.0
    nota = sum(pilares[k] * pesos[k] for k in usados) / w if w else None
    if cob < COBERTURA_MIN_NOTA:
        nota = None
    infl = []
    for k, v in pilares.items():
        if pesos.get(k, 0) <= 0:
            continue
        if v is None:
            infl.append(f"{k}: sem dados, ficou fora da nota (peso {pesos[k]:.0f}).")
        else:
            infl.append(f"{k}: {v:.0f}/100 (peso {pesos[k]:.0f}). {textos.get(k, '')}".strip())
    return Pontuacao(nota, dict(pilares), {k: pesos[k] for k in pilares if k in pesos}, cob, infl, metodo,
                     provisoria=nota is not None and cob < COBERTURA_CONFIAVEL)


ETF_PESOS = {"Retorno": 35, "Risco": 35, "Tendência": 15, "Custos e porte": 15}


def pontuar_etf(ind: dict) -> Pontuacao:
    """ETF: desempenho e risco de preço. Custos e porte (taxa, patrimônio) ainda não têm fonte: ficam fora da nota,
    sem penalizar o ETF. Os limites são regras educacionais."""
    v = {k: (i.valor if isinstance(i, Ind) else i) for k, i in ind.items()}
    pil = {
        "Retorno": _media([escala(v.get("ret12m"), 0, 25), escala(v.get("ret6m"), 0, 12)]),
        "Risco": _media([escala(v.get("vol"), 30, 10), escala(v.get("dd_max"), -40, -8)]),
        "Tendência": None if v.get("tend") is None else {0: 0.0, 1: 50.0, 2: 100.0}.get(int(v["tend"])),
        "Custos e porte": _media([escala(v.get("taxa_adm"), 1.0, 0.1)]),
    }
    txt = {"Retorno": "Retornos de 12 e 6 meses (passado não garante futuro).",
           "Risco": "Volatilidade e pior queda em 12 meses.",
           "Tendência": "Preço e médias de 50/200 dias.",
           "Custos e porte": "Taxa de administração."}
    return _pontuar(pil, ETF_PESOS, txt, "ETF: retorno, risco, tendência e custos")


def de_avaliacao_acao(av: dict, perfil: str) -> Pontuacao:
    """Converte o resultado de app.avaliar (o MESMO cálculo do Ranking) em Pontuacao. Não recalcula nada."""
    pil = dict(av.get("pil") or {})
    pesos = {k: float(w) for k, w in (av.get("pesos") or {}).items() if k in pil}
    if not pesos:
        pesos = {k: 1.0 for k in pil}
    txt = {"Valor": "Margem de segurança, P/L, P/VP, EV/EBITDA e DCF.", "Qualidade": "ROE e margem líquida.",
           "Dividendos": "Dividend yield e regularidade.", "Solidez": "Dívida/patrimônio (não vale para financeiras).",
           "Tendência": "Preço contra a média de 200 dias.", "Risco": "Volatilidade frente à tolerância do perfil."}
    p = _pontuar(pil, pesos, txt, f"Ações (Ranking do app), perfil {perfil}")
    if av.get("nota") is not None and p.nota is not None:
        p.nota = float(av["nota"])
    return p


def de_resultado_cripto(res: dict) -> Pontuacao:
    """Converte o resultado do motor fundamentalista de cripto em Pontuacao. Não recalcula nada."""
    pil, pesos = {}, {}
    for p in res.get("pilares", []):
        pil[p["nome"]] = p.get("nota")
        pesos[p["nome"]] = float(p.get("peso") or 0)
    out = _pontuar(pil, pesos, {}, f"Cripto: {res.get('tipo_rotulo', '')}")
    out.nota = res.get("nota")
    out.cobertura = float(res.get("cobertura") or 0.0)
    out.provisoria = bool(res.get("provisoria")) and out.nota is not None
    return out


def metricas_distribuicao(dividendos, close, dias: int = 365) -> dict:
    """Rendimentos de um fundo/ação nos últimos 12 meses, a partir da série de proventos (índice = data de pagamento).
    DY = soma dos 12 meses ÷ último preço. Sem série de proventos, ou com histórico de preço < 12 meses, o DY fica None
    (indisponível, nunca zero). Fundo que já pagou antes mas não pagou nos últimos 12 meses tem DY 0 de verdade."""
    out = {"dy12m": None, "meses_pagos": None, "soma12m": None, "data_ref": None}
    try:
        import pandas as pd
        c = close.dropna()
        c = c[c > 0]
        d = dividendos.dropna() if dividendos is not None else None
        d = d[d > 0] if d is not None else None
    except Exception:
        return out
    if d is None or len(d) == 0 or len(c) < 30:
        return out
    fim = c.index.max()
    if (fim - c.index.min()).days < dias * 0.95:
        return out                                    # preço com menos de ~12 meses: não comparar o DY de 12 meses
    j = d[d.index > fim - pd.Timedelta(days=dias)]
    out["soma12m"] = float(j.sum())
    out["dy12m"] = float(j.sum()) / float(c.iloc[-1]) * 100
    out["meses_pagos"] = int(len({(x.year, x.month) for x in j.index}))
    out["data_ref"] = _iso(d.index.max())
    return out


def liquidez_diaria(close, volume, dias: int = 90) -> float | None:
    """Média diária de preço × volume (na moeda do ativo) nos últimos `dias` dias corridos. None sem volume."""
    try:
        import pandas as pd
        v = (close * volume).dropna()
        v = v[v.index > v.index.max() - pd.Timedelta(days=dias)]
        return float(v.mean()) if len(v) >= 10 and v.sum() > 0 else None
    except Exception:
        return None


FII_PESOS = {"Renda": 25, "Liquidez": 10, "Risco": 20, "Retorno": 10, "Valuation (P/VP)": 20, "Qualidade dos ativos": 15}


def pontuar_fii(ind: dict) -> Pontuacao:
    """FII: renda, liquidez, risco e retorno (calculados do preço/rendimentos). P/VP e qualidade dos ativos ainda não têm
    fonte: ficam fora da nota (sem penalizar) e a nota fica PROVISÓRIA, porque falta metade do que importa num FII.
    Se um dia o P/VP chegar em ind["pvp"], ele entra na nota sem mudar mais nada. Limites são regras educacionais."""
    v = {k: (i.valor if isinstance(i, Ind) else i) for k, i in ind.items()}
    pil = {
        "Renda": _media([escala(v.get("dy12m"), 4, 12), escala(v.get("meses_pagos"), 6, 12)]),
        "Liquidez": escala(v.get("liq"), 200_000, 3_000_000),
        "Risco": _media([escala(v.get("vol"), 25, 8), escala(v.get("dd_max"), -30, -5)]),
        "Retorno": escala(v.get("ret12m"), 0, 20),
        "Valuation (P/VP)": escala(v.get("pvp"), 1.3, 0.9),
        "Qualidade dos ativos": None,
    }
    txt = {"Renda": "DY de 12 meses e regularidade das distribuições (DY muito alto pode ser sinal de queda do preço).",
           "Liquidez": "Volume financeiro médio negociado por dia.", "Risco": "Volatilidade e pior queda em 12 meses.",
           "Retorno": "Retorno em 12 meses com proventos reinvestidos (preço ajustado).",
           "Valuation (P/VP)": "Preço contra o valor patrimonial da cota.", "Qualidade dos ativos": "Vacância, contratos e concentração."}
    return _pontuar(pil, FII_PESOS, txt, "FII: renda, liquidez, risco e retorno (parcial)")


# =============================================================================== comparação
@dataclass
class Linha:
    spec: Spec
    valores: dict            # chave do ativo -> Ind | None
    melhores: list
    piores: list
    nota: str = ""           # observação (ex.: períodos distintos)


@dataclass
class Comparacao:
    ativos: list
    modo: str                # "vazio" | "ativo_unico" | "mesma_classe" | "classes_diferentes"
    classes: list
    linhas: list
    ranking: dict            # classe -> [(chave, nota, posição)]
    destaques: dict          # chave -> {"vantagens": [...], "desvantagens": [...]}
    alertas: list
    indisponiveis: dict      # chave -> [nomes dos indicadores sem dado]
    excluidos: dict          # chave -> motivo (erro)


def _dias(a: str | None, b: date) -> int | None:
    try:
        return (b - datetime.fromisoformat(str(a)[:10]).date()).days
    except Exception:
        return None


def comparar(ativos: list, hoje: date | None = None) -> Comparacao:
    hoje = hoje or date.today()
    validos = [a for a in ativos if not a.erro]
    excluidos = {a.chave: a.erro for a in ativos if a.erro}
    alertas: list[str] = []
    if len(validos) != len({a.chave for a in validos}):
        vistos, unicos = set(), []
        for a in validos:
            if a.chave not in vistos:
                vistos.add(a.chave)
                unicos.append(a)
        validos = unicos
    classes = list(dict.fromkeys(a.classe for a in validos))
    if not validos:
        motivos = [f"{k}: fora da comparação ({m})." for k, m in excluidos.items()]
        return Comparacao([], "vazio", [], [], {}, {}, ["Nenhum ativo com dados para comparar."] + motivos, {}, excluidos)
    modo = "ativo_unico" if len(validos) == 1 else ("mesma_classe" if len(classes) == 1 else "classes_diferentes")

    # --- quais indicadores entram
    if modo == "classes_diferentes":
        specs = [s for s in _COMUNS]
        alertas.append("Classes diferentes: só entram os critérios comuns (retorno, volatilidade e queda em 12 meses). "
                       "Múltiplos, dividendos e demais indicadores específicos não são comparáveis entre classes.")
        alertas.append("As notas de cada classe usam critérios diferentes e não são ranqueadas entre si.")
    else:
        specs = list(classe(classes[0]).specs)
    for c in classes:
        cl = classe(c)
        if not cl.suportada:
            alertas.append(f"{cl.nome}: {cl.motivo} Só os indicadores de preço (comuns) são mostrados.")
        elif cl.parcial:
            alertas.append(f"{cl.nome}: análise parcial, {cl.parcial}")
    if modo == "mesma_classe" and not classe(classes[0]).suportada:
        specs = list(_COMUNS)

    # --- linhas, melhores e piores
    linhas: list[Linha] = []
    indisp: dict[str, list] = {a.chave: [] for a in validos}
    for s in specs:
        vals = {a.chave: a.ind.get(s.chave) for a in validos}
        tem = {k: i for k, i in vals.items() if i is not None and i.aplica and _ok(i.valor)}
        for a in validos:
            if s.chave not in {x.chave for x in classe(a.classe).specs}:
                continue                                  # a classe do ativo nem mede este indicador
            i = vals[a.chave]
            if i is not None and not i.aplica:
                continue                                  # "não se aplica" não conta como falta
            if i is None or not _ok(i.valor):
                indisp[a.chave].append(s.nome)
        if not tem:
            continue
        obs = ""
        periodos = {i.periodo for i in tem.values() if i.periodo}
        if len(periodos) > 1:
            obs = "Períodos diferentes (" + ", ".join(sorted(periodos)) + "): sem destaque de melhor/pior."
        melhores, piores = [], []
        if s.direcao != 0 and len(tem) >= 2 and not obs:
            vs = [i.valor for i in tem.values()]
            if max(vs) != min(vs):
                alvo_m = max(vs) if s.direcao > 0 else min(vs)
                alvo_p = min(vs) if s.direcao > 0 else max(vs)
                melhores = [k for k, i in tem.items() if i.valor == alvo_m]
                piores = [k for k, i in tem.items() if i.valor == alvo_p]
        linhas.append(Linha(s, vals, melhores, piores, obs))

    # --- qualidade e confiabilidade dos dados
    moedas = {a.moeda for a in validos if a.moeda}
    if len(moedas) > 1:
        alertas.append("Moedas diferentes (" + ", ".join(sorted(moedas)) + "): retornos e volatilidade são percentuais na "
                       "moeda de cada ativo; valores absolutos não são somados nem comparados sem conversão.")
    datas = [(a.chave, a.data_ref) for a in validos]
    sem_data = [k for k, d in datas if not d]
    if sem_data:
        alertas.append("Data de referência não informada para: " + ", ".join(sem_data) + ".")
    ds = []
    for k, d in datas:
        try:
            ds.append((k, datetime.fromisoformat(str(d)[:10]).date()))
        except Exception:
            pass
    if len(ds) >= 2 and (max(x for _, x in ds) - min(x for _, x in ds)).days > DIAS_DATAS_DISTANTES:
        alertas.append("Datas de referência distantes entre os ativos (" + ", ".join(
            f"{k}: {x.strftime('%d/%m/%Y')}" for k, x in ds) + "): a comparação pode não ser do mesmo período.")
    velhos = [f"{k} ({x.strftime('%d/%m/%Y')})" for k, x in ds if (hoje - x).days > DIAS_DESATUALIZADO]
    if velhos:
        alertas.append("Dados desatualizados (mais de 7 dias): " + ", ".join(velhos) + ".")
    for a in validos:
        for av in a.avisos:
            alertas.append(f"{a.chave}: {av}")
        if indisp[a.chave]:
            alertas.append(f"{a.chave}: indicadores indisponíveis (não entram na pontuação): "
                           + ", ".join(indisp[a.chave]) + ".")
    for k, motivo in excluidos.items():
        alertas.append(f"{k}: fora da comparação ({motivo}).")

    # --- ranking só dentro de cada classe
    ranking: dict[str, list] = {}
    for c in classes:
        itens = [(a.chave, a.pontuacao.nota) for a in validos
                 if a.classe == c and a.pontuacao is not None and a.pontuacao.nota is not None]
        itens.sort(key=lambda x: -x[1])
        pos, out = 0, []
        for n, (k, nota) in enumerate(itens):
            if n == 0 or abs(nota - itens[n - 1][1]) > 1e-9:
                pos = n + 1
            out.append((k, nota, pos))
        if out:
            ranking[c] = out
    for c in classes:
        sem = [a.chave for a in validos if a.classe == c and classe(c).suportada
               and (a.pontuacao is None or a.pontuacao.nota is None)]
        if sem:
            alertas.append("Sem pontuação por dados insuficientes: " + ", ".join(sem) + ".")
        if any(a.pontuacao and a.pontuacao.provisoria for a in validos if a.classe == c):
            alertas.append(f"{classe(c).nome}: há pontuação provisória (menos de 70% dos critérios com dado).")

    # --- vantagens e desvantagens (sem dizer qual é "melhor investimento")
    dest = {a.chave: {"vantagens": [], "desvantagens": []} for a in validos}
    for ln in linhas:
        for k in ln.melhores:
            dest[k]["vantagens"].append(f"{ln.spec.nome}: {fmt_valor(ln.valores[k].valor, ln.spec.fmt)} "
                                        f"({'menor' if ln.spec.direcao < 0 else 'maior'} entre os comparados)")
        for k in ln.piores:
            dest[k]["desvantagens"].append(f"{ln.spec.nome}: {fmt_valor(ln.valores[k].valor, ln.spec.fmt)} "
                                           f"({'maior' if ln.spec.direcao < 0 else 'menor'} entre os comparados)")
    for c, itens in ranking.items():
        if len(itens) >= 2:
            topo, base = itens[0], itens[-1]
            if topo[2] != base[2]:
                dest[topo[0]]["vantagens"].append(f"Maior pontuação de {classe(c).nome.lower()} entre os comparados "
                                                  f"({topo[1]:.0f}/100)")
                dest[base[0]]["desvantagens"].append(f"Menor pontuação de {classe(c).nome.lower()} entre os comparados "
                                                     f"({base[1]:.0f}/100)")
    alertas.append(AVISO_LEGAL)
    return Comparacao(validos, modo, classes, linhas, ranking, dest, list(dict.fromkeys(alertas)), indisp, excluidos)


def posicionamento(c: Comparacao, chave: str) -> str:
    """Frase de posição relativa dentro da classe, entre os ativos comparados (nunca 'entre todos do mercado')."""
    a = next((x for x in c.ativos if x.chave == chave), None)
    if a is None or a.classe not in c.ranking:
        return "Sem posição: pontuação indisponível ou ativo único na classe."
    itens = c.ranking[a.classe]
    for k, nota, pos in itens:
        if k == chave:
            return f"{pos}º de {len(itens)} em {classe(a.classe).nome.lower()} entre os comparados (nota {nota:.0f}/100)."
    return "Sem posição: pontuação indisponível."


def tabela(c: Comparacao) -> list[dict]:
    """Linhas prontas para exibição: {"Indicador": ..., "<ativo>": texto, ...}. Marca ✅ melhor e ⚠️ pior."""
    out = []
    for ln in c.linhas:
        row = {"Indicador": ln.spec.nome}
        for a in c.ativos:
            i = ln.valores.get(a.chave)
            if i is not None and not i.aplica:
                txt = "não se aplica"
            else:
                txt = fmt_valor(i.valor if i else None, ln.spec.fmt)
                if i is not None and _ok(i.valor) and i.origem != "dado":
                    txt += " ᶜ" if i.origem == "calculado" else " ᵉ"
            if a.chave in ln.melhores:
                txt += " ✅"
            elif a.chave in ln.piores:
                txt += " ⚠️"
            row[a.chave] = txt
        if ln.nota:
            row["Indicador"] += " (*)"
        out.append(row)
    return out
