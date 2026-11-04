"""
Renda fixa: cálculos puros (Passo 11). Nada aqui acessa rede ou Streamlit.

Convenções (as do mercado brasileiro):
  - Prazo em dias úteis (DU) e base 252 para taxas: fator = (1 + taxa) ** (DU / 252).
  - Calendário de feriados nacionais (o da ANBIMA): fixos, Carnaval (segunda e terça), Sexta-feira Santa, Corpus Christi
    e Consciência Negra (20/11, nacional desde 2024).
  - IR regressivo pelos dias CORRIDOS desde a aplicação; IOF regressivo nos primeiros 29 dias, sobre o rendimento.
  - Taxas em fração (0,12 = 12% a.a.). Percentual do CDI em fração (1,10 = 110% do CDI).

Separação obrigatória dos conceitos:
  - CONTRATADA: a taxa do título (só é garantida até o vencimento, se o emissor pagar).
  - REALIZADA: o que o título rendeu até hoje pelos dados reais (CDI e IPCA do Banco Central, PU do Tesouro).
  - ESPERADA: projeção até o vencimento sob um CENÁRIO de CDI/IPCA (premissa, não promessa).
  - MARCAÇÃO A MERCADO: preço ESTIMADO se vendesse hoje; não é preço executável.
Ferramenta educacional, não é recomendação de investimento.
"""
from __future__ import annotations

import math
import re
import unicodedata
import uuid
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from functools import lru_cache

import numpy as np
import pandas as pd

# =============================================================================== calendário (DU/252)
CONSCIENCIA_NEGRA_DESDE = 2024


def _pascoa(ano: int) -> date:
    """Domingo de Páscoa (algoritmo de Meeus/Jones/Butcher, calendário gregoriano)."""
    a, b, c = ano % 19, ano // 100, ano % 100
    d, e = b // 4, b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = c // 4, c % 4
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    mes = (h + l_ - 7 * m + 114) // 31
    dia = ((h + l_ - 7 * m + 114) % 31) + 1
    return date(ano, mes, dia)


def feriados(ano: int) -> list[date]:
    p = _pascoa(ano)
    fixos = [(1, 1), (4, 21), (5, 1), (9, 7), (10, 12), (11, 2), (11, 15), (12, 25)]
    if ano >= CONSCIENCIA_NEGRA_DESDE:
        fixos.append((11, 20))
    moveis = [p - timedelta(days=48), p - timedelta(days=47), p - timedelta(days=2), p + timedelta(days=60)]
    return sorted({date(ano, m, d) for m, d in fixos} | set(moveis))


@lru_cache(maxsize=1)
def _feriados_np() -> np.ndarray:
    return np.array([np.datetime64(d) for a in range(1990, 2101) for d in feriados(a)], dtype="datetime64[D]")


def _d(x) -> date:
    if isinstance(x, pd.Timestamp):
        return x.date()
    if isinstance(x, date):
        return x
    return pd.Timestamp(x).date()


def du(d0, d1) -> int:
    """Dias úteis de d0 (inclusive) até d1 (exclusive). Negativo se d1 < d0."""
    a, b = _d(d0), _d(d1)
    if b < a:
        return -_du(b, a)
    return _du(a, b)


@lru_cache(maxsize=500_000)
def _du(a: date, b: date) -> int:
    return int(np.busday_count(np.datetime64(a), np.datetime64(b), holidays=_feriados_np()))


def dc(d0, d1) -> int:
    """Dias corridos."""
    return (_d(d1) - _d(d0)).days


def eh_dia_util(d) -> bool:
    return bool(np.is_busday(np.datetime64(_d(d)), holidays=_feriados_np()))


def somar_meses(d: date, meses: int) -> date:
    t = pd.Timestamp(d) + pd.DateOffset(months=meses)
    return t.date()


# =============================================================================== tipos de título
@dataclass(frozen=True)
class Tipo:
    chave: str
    nome: str
    grupo: str                      # "tesouro" | "bancario" | "credito_privado"
    isento_ir_pf: bool
    fgc: bool
    iof: bool                       # IOF regressivo se resgatar antes de 30 dias
    risco_credito: int              # 1 soberano · 2 bancário com FGC · 3 bancário sem FGC · 4 empresa/securitização
    liquidez_tipica: str
    descricao: str
    indexadores: tuple = ("pre", "cdi_pct", "cdi_mais", "ipca")
    emissor_fixo: str = ""
    pagamento_padrao: str = "vencimento"


_LIQ_TESOURO = "Diária: o Tesouro recompra em D+1, pelo preço do dia (marcado a mercado)."
_LIQ_SECUNDARIO = "Sem recompra garantida: venda antes do vencimento depende de comprador no mercado secundário (pode ter deságio)."
TIPOS: dict[str, Tipo] = {t.chave: t for t in [
    Tipo("tesouro_selic", "Tesouro Selic", "tesouro", False, False, True, 1, _LIQ_TESOURO,
         "Pós-fixado: acompanha a Selic. Oscila pouco de preço; o menor risco de mercado do Tesouro.",
         ("selic",), "Tesouro Nacional"),
    Tipo("tesouro_prefixado", "Tesouro Prefixado", "tesouro", False, False, True, 1, _LIQ_TESOURO,
         "Taxa fixa definida na compra; paga tudo no vencimento. O preço cai quando os juros sobem.", ("pre",), "Tesouro Nacional"),
    Tipo("tesouro_prefixado_juros", "Tesouro Prefixado com Juros Semestrais", "tesouro", False, False, True, 1, _LIQ_TESOURO,
         "Taxa fixa com cupom de 10% a.a. pago a cada seis meses (há IR em cada cupom).", ("pre",), "Tesouro Nacional", "semestral"),
    Tipo("tesouro_ipca", "Tesouro IPCA+", "tesouro", False, False, True, 1, _LIQ_TESOURO,
         "IPCA + taxa fixa, tudo no vencimento. Protege da inflação se levado até o fim; o preço oscila muito antes.",
         ("ipca",), "Tesouro Nacional"),
    Tipo("tesouro_ipca_juros", "Tesouro IPCA+ com Juros Semestrais", "tesouro", False, False, True, 1, _LIQ_TESOURO,
         "IPCA + taxa fixa, com cupom real de 6% a.a. pago a cada seis meses.", ("ipca",), "Tesouro Nacional", "semestral"),
    Tipo("tesouro_renda", "Tesouro Renda+ Aposentadoria Extra", "tesouro", False, False, True, 1, _LIQ_TESOURO,
         "IPCA + taxa, pago em 240 parcelas mensais (20 anos) a partir do ano do título.", ("ipca",), "Tesouro Nacional", "mensal"),
    Tipo("tesouro_educa", "Tesouro Educa+", "tesouro", False, False, True, 1, _LIQ_TESOURO,
         "IPCA + taxa, pago em 60 parcelas mensais (5 anos) a partir do ano do título.", ("ipca",), "Tesouro Nacional", "mensal"),
    Tipo("cdb", "CDB", "bancario", False, True, True, 2, "Depende do título: liquidez diária ou só no vencimento (veja o contrato).",
         "Certificado de Depósito Bancário: empréstimo ao banco, coberto pelo FGC até o limite."),
    Tipo("lci", "LCI", "bancario", True, True, False, 2, "Só depois da carência (mínimo legal de 6 meses; 36 meses se atrelada à inflação).",
         "Letra de Crédito Imobiliário: isenta de IR para pessoa física, coberta pelo FGC até o limite."),
    Tipo("lca", "LCA", "bancario", True, True, False, 2, "Só depois da carência (mínimo legal de 6 meses; 12 meses se atrelada à inflação).",
         "Letra de Crédito do Agronegócio: isenta de IR para pessoa física, coberta pelo FGC até o limite."),
    Tipo("lc", "LC (Letra de Câmbio)", "bancario", False, True, True, 2, "Em geral só no vencimento.",
         "Emitida por financeiras; coberta pelo FGC até o limite."),
    Tipo("lf", "Letra Financeira", "bancario", False, False, True, 3, "Prazo mínimo de 24 meses e sem resgate antecipado.",
         "Título de banco SEM cobertura do FGC; o risco é o do banco."),
    Tipo("debenture", "Debênture", "credito_privado", False, False, True, 4, _LIQ_SECUNDARIO,
         "Dívida de empresa. Sem FGC: o risco é o da empresa (e das garantias, se houver)."),
    Tipo("debenture_incentivada", "Debênture incentivada (Lei 12.431)", "credito_privado", True, False, False, 4, _LIQ_SECUNDARIO,
         "Dívida de empresa para infraestrutura, isenta de IR para pessoa física. Sem FGC."),
    Tipo("cri", "CRI", "credito_privado", True, False, False, 4, _LIQ_SECUNDARIO,
         "Certificado de Recebíveis Imobiliários: isento de IR para PF, sem FGC; o risco é dos devedores e das garantias."),
    Tipo("cra", "CRA", "credito_privado", True, False, False, 4, _LIQ_SECUNDARIO,
         "Certificado de Recebíveis do Agronegócio: isento de IR para PF, sem FGC; o risco é dos devedores e das garantias."),
    Tipo("outro", "Outro título", "credito_privado", False, False, True, 4, "Confira no contrato.",
         "Título não identificado: o app assume tributação normal e sem FGC."),
]}

INDEXADORES = {"pre": "Prefixado (% a.a.)", "cdi_pct": "% do CDI", "cdi_mais": "CDI + taxa (% a.a.)",
               "ipca": "IPCA + taxa (% a.a.)", "selic": "Selic + taxa (% a.a.)"}
PAGAMENTOS = {"vencimento": "Tudo no vencimento", "mensal": "Juros mensais", "semestral": "Juros semestrais", "anual": "Juros anuais"}
MESES_PAGAMENTO = {"mensal": 1, "semestral": 6, "anual": 12}
LIQUIDEZ = {"diaria": "Liquidez diária", "carencia": "Liquidez após carência", "vencimento": "Só no vencimento"}
NOMES_TESOURO = {   # nome do Tesouro Transparente -> tipo
    "tesouro selic": "tesouro_selic", "tesouro prefixado": "tesouro_prefixado",
    "tesouro prefixado com juros semestrais": "tesouro_prefixado_juros", "tesouro ipca+": "tesouro_ipca",
    "tesouro ipca+ com juros semestrais": "tesouro_ipca_juros", "tesouro renda+ aposentadoria extra": "tesouro_renda",
    "tesouro educa+": "tesouro_educa"}
CUPOM_NTNF = 0.10          # 10% a.a. (cupom semestral (1,10^0,5 − 1) × 1000 = 48,8088)
CUPOM_NTNB = 0.06          # 6% a.a. real
PARCELAS_RENDA, PARCELAS_EDUCA = 240, 60
FGC_LIMITE = 250_000.0     # por CPF/CNPJ, por instituição ou conglomerado
FGC_TETO_4ANOS = 1_000_000.0
CUSTODIA_TESOURO = 0.0020  # 0,20% a.a. (B3)
ISENCAO_CUSTODIA_SELIC = 10_000.0
DIFERENCA_CDI_SELIC = 0.0010   # o CDI costuma ficar ~0,10 p.p. abaixo da Selic


def tipo(chave: str) -> Tipo:
    return TIPOS.get(chave) or TIPOS["outro"]


def tipo_do_tesouro(nome: str) -> str | None:
    """Nome do Tesouro Transparente → tipo. Nome exato primeiro; se a fonte mudar a grafia, lê pelas palavras do nome.
    IGP-M+ (fora de venda) e nomes desconhecidos: None."""
    n = re.sub(r"\s+", " ", (nome or "").strip().lower())
    if n in NOMES_TESOURO:
        return NOMES_TESOURO[n]
    if "tesouro" not in n or "igp" in n:
        return None
    k = interpretar(n).get("tipo")
    return k if k in NOMES_TESOURO.values() else None


# =============================================================================== título (o que o usuário tem ou quer analisar)
@dataclass
class Titulo:
    tipo: str
    indexador: str
    taxa: float                     # pre/ipca/cdi_mais/selic: fração a.a.; cdi_pct: fração do CDI (1,10 = 110%)
    aplicacao: date
    vencimento: date
    valor: float = 1000.0           # valor aplicado (R$)
    emissor: str = ""
    nome: str = ""
    liquidez: str = "vencimento"    # diaria | carencia | vencimento
    carencia: date | None = None
    pagamento: str = "vencimento"   # vencimento | mensal | semestral | anual
    garantia: str = ""              # texto livre (ex.: alienação fiduciária de imóveis)
    rating: str = ""                # ex.: "AA+ (Fitch)"
    emissor_ticker: str = ""        # empresa listada que emite (saúde financeira pelo app)
    td_titulo: str = ""             # Tesouro: nome no Tesouro Transparente (preço oficial)
    td_venc: date | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:6])

    def para_dict(self) -> dict:
        d = asdict(self)
        for k in ("aplicacao", "vencimento", "carencia", "td_venc"):
            d[k] = d[k].isoformat() if d[k] else None
        return d

    @staticmethod
    def de_dict(d: dict) -> "Titulo":
        x = dict(d)
        for k in ("aplicacao", "vencimento", "carencia", "td_venc"):
            x[k] = _d(x[k]) if x.get(k) else None
        campos = Titulo.__dataclass_fields__
        return Titulo(**{k: v for k, v in x.items() if k in campos})

    @property
    def t(self) -> Tipo:
        return tipo(self.tipo)

    def rotulo(self) -> str:
        base = self.nome or f"{self.t.nome} {self.emissor}".strip()
        return f"{base} · {texto_taxa(self)} · vence {self.vencimento.strftime('%d/%m/%Y')}"


def texto_taxa(t: Titulo) -> str:
    if t.indexador == "cdi_pct":
        return f"{_br(t.taxa * 100, 1)}% do CDI"
    if t.indexador == "pre":
        return f"{_br(t.taxa * 100)}% a.a."
    nome = {"cdi_mais": "CDI", "ipca": "IPCA", "selic": "Selic"}[t.indexador]
    return f"{nome} + {_br(t.taxa * 100)}% a.a."


def _br(v: float, casas: int = 2) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def validar(t: Titulo) -> list[str]:
    """Erros que impedem a análise (lista vazia = ok)."""
    e = []
    if t.indexador not in INDEXADORES:
        e.append("indexador desconhecido")
    elif t.indexador not in t.t.indexadores:
        e.append(f"{t.t.nome} não usa o indexador {INDEXADORES[t.indexador]}")
    if t.vencimento <= t.aplicacao:
        e.append("o vencimento precisa ser depois da aplicação")
    if not (t.valor and t.valor > 0):
        e.append("valor aplicado precisa ser maior que zero")
    if t.indexador == "cdi_pct" and not (0 < t.taxa <= 3):
        e.append("% do CDI fora do razoável (use, por exemplo, 110 para 110% do CDI)")
    if t.indexador != "cdi_pct" and not (-0.05 < t.taxa < 0.5):
        e.append("taxa fora do razoável (use % ao ano, por exemplo 6,5)")
    if t.liquidez == "carencia" and not t.carencia:
        e.append("informe a data de fim da carência")
    return e


# =============================================================================== classificação automática (texto livre)
def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", s).strip()


def _num(txt: str) -> float | None:
    try:
        return float(txt.replace(".", "").replace(",", ".")) if re.search(r",\d", txt) else float(txt)
    except ValueError:
        return None


_MESES = {"jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6, "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12}


def interpretar(texto: str) -> dict:
    """Lê a descrição de um título como aparece na corretora ("CDB Banco X 110% CDI venc. 15/03/2028", "Tesouro IPCA+ 2035",
    "LCA 95% do CDI 2027", "Debênture incentivada XPTO IPCA + 7,2% 2032"). Devolve só o que conseguiu identificar, com
    a origem de cada campo; o resto fica para o usuário. Nada é inventado."""
    t = _norm(texto)
    out: dict = {"achados": []}
    if not t:
        return out
    tes = None
    if "tesouro" in t or re.search(r"\b(ltn|lft|ntn-?b|ntn-?f)\b", t):
        juros = bool(re.search(r"juros|semestra|ntn-?b\b(?! princ)|ntn-?f", t))
        if "selic" in t or "lft" in t:
            tes = "tesouro_selic"
        elif "renda" in t:
            tes = "tesouro_renda"
        elif "educa" in t:
            tes = "tesouro_educa"
        elif "ipca" in t or "ntn-b" in t or "ntnb" in t:
            tes = "tesouro_ipca_juros" if juros and "principal" not in t else "tesouro_ipca"
        elif "pre" in t or "ltn" in t or "ntn-f" in t or "ntnf" in t:
            tes = "tesouro_prefixado_juros" if juros else "tesouro_prefixado"
    if tes:
        out["tipo"] = tes
    else:
        for chave, padrao in (("debenture_incentivada", r"debenture[s]? incentivad|12\.?431|incentivad"),
                              ("debenture", r"\bdebenture|\bdeb\b"), ("cri", r"\bcri\b"), ("cra", r"\bcra\b"),
                              ("lci", r"\blci\b"), ("lca", r"\blca\b"), ("lf", r"\blf\b|letra financeira"),
                              ("lc", r"\blc\b|letra de cambio"), ("cdb", r"\bcdb\b|\brdb\b")):
            if re.search(padrao, t):
                out["tipo"] = chave
                break
    if "tipo" in out:
        out["achados"].append("tipo")
    # indexador e taxa
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*%\s*(?:do\s+)?(?:cdi|di)\b", t)
    if m:
        out.update(indexador="cdi_pct", taxa=(_num(m.group(1)) or 0) / 100)
    elif re.search(r"\b(?:cdi|di)\s*\+\s*(\d+(?:[.,]\d+)?)", t):
        m = re.search(r"\b(?:cdi|di)\s*\+\s*(\d+(?:[.,]\d+)?)", t)
        out.update(indexador="cdi_mais", taxa=(_num(m.group(1)) or 0) / 100)
    elif re.search(r"ipca\s*\+?\s*(\d+(?:[.,]\d+)?)\s*%", t):
        m = re.search(r"ipca\s*\+?\s*(\d+(?:[.,]\d+)?)\s*%", t)
        out.update(indexador="ipca", taxa=(_num(m.group(1)) or 0) / 100)
    elif re.search(r"selic\s*\+\s*(\d+(?:[.,]\d+)?)", t):
        m = re.search(r"selic\s*\+\s*(\d+(?:[.,]\d+)?)", t)
        out.update(indexador="selic", taxa=(_num(m.group(1)) or 0) / 100)
    elif re.search(r"(?:pre|prefixad\w*)\D{0,12}(\d+(?:[.,]\d+)?)\s*%|(\d+(?:[.,]\d+)?)\s*%\s*(?:a\.?a\.?|ao ano)", t):
        m = re.search(r"(?:pre|prefixad\w*)\D{0,12}(\d+(?:[.,]\d+)?)\s*%|(\d+(?:[.,]\d+)?)\s*%\s*(?:a\.?a\.?|ao ano)", t)
        out.update(indexador="pre", taxa=(_num(m.group(1) or m.group(2)) or 0) / 100)
    if "indexador" in out:
        out["achados"] += ["indexador", "taxa"]
    elif "tipo" in out and len(TIPOS[out["tipo"]].indexadores) == 1:
        out["indexador"] = TIPOS[out["tipo"]].indexadores[0]
        out["achados"].append("indexador")
    # vencimento: dd/mm/aaaa, mm/aaaa, mes/aaaa ou só o ano
    m = re.search(r"(\d{1,2})/(\d{1,2})/(\d{4})", t)
    if m:
        try:
            out["vencimento"] = date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        except ValueError:
            pass
    if "vencimento" not in out:
        m = re.search(r"\b(jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)\w*[/ -]*(\d{4})\b", t)
        if m:
            out["vencimento"] = date(int(m.group(2)), _MESES[m.group(1)], 15)
            out["venc_aproximado"] = True
    if "vencimento" not in out:
        anos = [int(a) for a in re.findall(r"\b(20[2-9]\d)\b", t)]
        if anos:
            out["ano_vencimento"] = max(anos)
    if "vencimento" in out or "ano_vencimento" in out:
        out["achados"].append("vencimento")
    if out.get("tipo") in ("tesouro_selic", "tesouro_prefixado", "tesouro_prefixado_juros", "tesouro_ipca",
                           "tesouro_ipca_juros", "tesouro_renda", "tesouro_educa"):
        out["emissor"] = "Tesouro Nacional"
        out["pagamento"] = TIPOS[out["tipo"]].pagamento_padrao
    if out.get("tipo") in ("lci", "lca") and "liquidez" not in out:
        out["liquidez"] = "carencia"
    if re.search(r"liquidez diaria|liq\.? diaria|\bd\+0\b|\bd\+1\b", t):
        out["liquidez"] = "diaria"
    if re.search(r"juros (mensais|mensal)", t):
        out["pagamento"] = "mensal"
    elif re.search(r"juros semestra", t):
        out["pagamento"] = "semestral"
    return out


# =============================================================================== tributação
IOF_TABELA = [96, 93, 90, 86, 83, 80, 76, 73, 70, 66, 63, 60, 56, 53, 50, 46, 43, 40, 36, 33, 30, 26, 23, 20, 16, 13, 10, 6, 3]


def aliquota_ir(dias: int) -> float:
    """Tabela regressiva (Lei 11.033/2004), pelos dias corridos da aplicação."""
    return 0.225 if dias <= 180 else 0.20 if dias <= 360 else 0.175 if dias <= 720 else 0.15


def aliquota_iof(dias: int) -> float:
    """IOF regressivo sobre o rendimento, para resgates em menos de 30 dias (Decreto 6.306/2007, anexo)."""
    if dias >= 30:
        return 0.0
    if dias <= 0:
        return 1.0
    return IOF_TABELA[dias - 1] / 100


def custodia_tesouro(tipo_chave: str, valor_medio: float, anos: float, ate_vencimento: bool = True) -> float:
    """Taxa de custódia da B3 (0,20% a.a. sobre o valor). Tesouro Selic: isento até R$ 10 mil. Renda+ e Educa+: sem taxa
    se levados até o vencimento; na venda antecipada há taxa sobre o excedente da isenção (aqui estimada em 0,10% a.a.
    sobre todo o valor, como teto)."""
    if tipo(tipo_chave).grupo != "tesouro" or anos <= 0 or valor_medio <= 0:
        return 0.0
    if tipo_chave in ("tesouro_renda", "tesouro_educa"):
        return 0.0 if ate_vencimento else 0.0010 * valor_medio * anos
    base = max(valor_medio - ISENCAO_CUSTODIA_SELIC, 0.0) if tipo_chave == "tesouro_selic" else valor_medio
    return CUSTODIA_TESOURO * base * anos


def tributar(aplicado: float, bruto: float, dias: int, tipo_chave: str, custodia: float = 0.0) -> dict:
    """Do valor bruto ao líquido: IOF (se < 30 dias) sobre o rendimento; IR regressivo sobre o rendimento menos IOF e
    custódia. Isentos (LCI, LCA, CRI, CRA, debênture incentivada) não pagam IR para pessoa física."""
    tp = tipo(tipo_chave)
    rend = bruto - aplicado
    iof = rend * aliquota_iof(dias) if tp.iof and rend > 0 else 0.0
    base = rend - iof - custodia
    aliq = 0.0 if tp.isento_ir_pf else aliquota_ir(dias)
    ir = base * aliq if base > 0 else 0.0
    liquido = bruto - iof - ir - custodia
    return {"bruto": bruto, "rendimento": rend, "iof": iof, "ir": ir, "custodia": custodia, "liquido": liquido,
            "aliquota_ir": aliq, "aliquota_iof": aliquota_iof(dias) if tp.iof else 0.0, "isento": tp.isento_ir_pf}


def taxa_equivalente_tributavel(taxa_isenta: float, dias: int) -> float:
    """Quanto um título tributável precisa render (bruto) para empatar com um isento no mesmo prazo."""
    return taxa_isenta / (1 - aliquota_ir(dias))


# =============================================================================== cenários (premissas de CDI, IPCA e Selic)
@dataclass
class Cenario:
    nome: str
    cdi: dict                 # ano -> taxa a.a. (fração); a chave 0 vale para anos sem valor próprio
    ipca: dict
    origem: str = ""

    def cdi_de(self, ano: int) -> float:
        return _por_ano(self.cdi, ano)

    def ipca_de(self, ano: int) -> float:
        return _por_ano(self.ipca, ano)

    def selic_de(self, ano: int) -> float:
        return self.cdi_de(ano) + DIFERENCA_CDI_SELIC


def _por_ano(d: dict, ano: int) -> float:
    if ano in d:
        return d[ano]
    anos = sorted(k for k in d if k)
    if anos and ano > anos[-1]:
        return d[anos[-1]]
    if anos and ano < anos[0]:
        return d[anos[0]]
    return d.get(0, 0.0)


def cenario_fixo(cdi: float, ipca: float, nome: str = "Juros e inflação de hoje", origem: str = "") -> Cenario:
    return Cenario(nome, {0: cdi}, {0: ipca}, origem)


def cenario_focus(focus: dict, cdi_hoje: float, ipca_hoje: float) -> Cenario | None:
    """Focus (mediana do mercado por ano). Selic do Focus é a do FIM de cada ano: usamos a média entre o fim do ano anterior
    e o fim do ano (aproximação da média do ano) e CDI = Selic − 0,10 p.p. Sem Focus, None."""
    sel, ipc = focus.get("selic") or {}, focus.get("ipca") or {}
    if not sel and not ipc:
        return None
    cdi, ant = {}, cdi_hoje + DIFERENCA_CDI_SELIC
    for ano in sorted(sel):
        fim = sel[ano]
        cdi[ano] = (ant + fim) / 2 - DIFERENCA_CDI_SELIC
        ant = fim
    ip = {a: v for a, v in ipc.items()}
    if not cdi:
        cdi = {0: cdi_hoje}
    if not ip:
        ip = {0: ipca_hoje}
    return Cenario("Expectativas do mercado (Focus)", cdi, ip, focus.get("data", ""))


def cenario_deslocado(c: Cenario, d_cdi: float = 0.0, d_ipca: float = 0.0, nome: str = "") -> Cenario:
    return Cenario(nome or c.nome, {k: max(v + d_cdi, 0.0) for k, v in c.cdi.items()},
                   {k: v + d_ipca for k, v in c.ipca.items()}, c.origem)


# =============================================================================== fatores (projetado e realizado)
def _trechos_por_ano(d0: date, d1: date):
    a = d0
    while a < d1:
        fim = min(date(a.year + 1, 1, 1), d1)
        yield a.year, du(a, fim), a, fim
        a = fim


def fator_projetado(indexador: str, taxa: float, d0, d1, cen: Cenario) -> float:
    """Fator bruto de d0 a d1 só com o CENÁRIO (sem dado realizado). IPCA projetado por dias úteis (aproximação)."""
    d0, d1 = _d(d0), _d(d1)
    if d1 <= d0:
        return 1.0
    f = 1.0
    for ano, n, _, _ in _trechos_por_ano(d0, d1):
        if indexador == "pre":
            f *= (1 + taxa) ** (n / 252)
        elif indexador == "cdi_pct":
            f *= (((1 + cen.cdi_de(ano)) ** (1 / 252) - 1) * taxa + 1) ** n
        elif indexador == "cdi_mais":
            f *= ((1 + cen.cdi_de(ano)) * (1 + taxa)) ** (n / 252)
        elif indexador == "selic":
            f *= ((1 + cen.selic_de(ano)) * (1 + taxa)) ** (n / 252)
        elif indexador == "ipca":
            f *= ((1 + cen.ipca_de(ano)) * (1 + taxa)) ** (n / 252)
        else:
            raise ValueError(indexador)
    return f


def fator_inflacao_projetado(d0, d1, cen: Cenario) -> float:
    return math.prod((1 + cen.ipca_de(a)) ** (n / 252) for a, n, _, _ in _trechos_por_ano(_d(d0), _d(d1)))


def _taxas_diarias(cdi_idx: pd.Series) -> pd.Series:
    """Taxa diária (fração) a partir do índice acumulado do CDI (o índice em t já inclui a taxa de t)."""
    s = cdi_idx.dropna().sort_index()
    if s.empty:
        return s
    r = s.pct_change()
    r.iloc[0] = s.iloc[0] / 100 - 1
    r.index = pd.DatetimeIndex(r.index).normalize()
    return r


def fator_cdi_realizado(indexador: str, taxa: float, d0, d1, cdi_idx: pd.Series) -> tuple[float | None, date | None]:
    """Fator realizado com o CDI diário do Banco Central (dias em [d0, d1)). Devolve (fator, último dia coberto) ou (None,
    None) sem dado. Selic ≈ CDI + 0,10 p.p. (aproximação)."""
    if cdi_idx is None or len(cdi_idx) == 0:
        return None, None
    r = _taxas_diarias(cdi_idx)
    r = r[(r.index >= pd.Timestamp(_d(d0))) & (r.index < pd.Timestamp(_d(d1)))]
    if r.empty:
        return None, None
    if indexador == "cdi_pct":
        f = float((1 + taxa * r).prod())
    elif indexador == "cdi_mais":
        f = float(((1 + r) * (1 + taxa) ** (1 / 252)).prod())
    elif indexador == "selic":
        f = float(((1 + r) * (1 + DIFERENCA_CDI_SELIC) ** (1 / 252) * (1 + taxa) ** (1 / 252)).prod())
    else:
        raise ValueError(indexador)
    return f, (r.index[-1] + pd.Timedelta(days=1)).date()


def fator_ipca_realizado(d0, d1, ipca_mensal: pd.Series) -> tuple[float, date | None]:
    """IPCA realizado entre d0 e d1, mês a mês, proporcional aos dias corridos dentro de cada mês. ipca_mensal: % ao mês,
    datada no FIM do mês. Devolve (fator, último dia coberto por dado); depois disso, o chamador projeta."""
    d0, d1 = _d(d0), _d(d1)
    if ipca_mensal is None or len(ipca_mensal) == 0 or d1 <= d0:
        return 1.0, None
    s = ipca_mensal.dropna()
    meses = {(t.year, t.month): float(v) / 100 for t, v in s.items()}
    f, ate, a = 1.0, None, d0
    while a < d1:
        ini_mes = date(a.year, a.month, 1)
        prox = somar_meses(ini_mes, 1)
        fim = min(prox, d1)
        taxa = meses.get((a.year, a.month))
        if taxa is None:
            break
        dias_mes = (prox - ini_mes).days
        f *= (1 + taxa) ** ((fim - a).days / dias_mes)
        ate = fim
        a = fim
    return f, ate


def fator_inflacao(d0, d1, mercado: dict | None, cen: Cenario) -> tuple[float, date | None]:
    """IPCA de d0 a d1: realizado (Banco Central) até onde há dado; depois, o cenário. Devolve (fator, último dia real)."""
    d0, d1 = _d(d0), _d(d1)
    if d1 <= d0:
        return 1.0, d0
    fr, ate = fator_ipca_realizado(d0, d1, (mercado or {}).get("ipca"))
    ini = ate or d0
    return fr * (fator_inflacao_projetado(ini, d1, cen) if ini < d1 else 1.0), ate


def fator_realizado(t: Titulo, d1, mercado: dict, cen: Cenario) -> dict:
    """Fator bruto de t.aplicacao a d1 usando dado REAL até onde existe e o cenário depois. Diz quanto foi realizado."""
    d0, d1 = t.aplicacao, _d(d1)
    if d1 <= d0:
        return {"fator": 1.0, "real_ate": d0, "parcial": False}
    if t.indexador == "pre":
        return {"fator": (1 + t.taxa) ** (du(d0, d1) / 252), "real_ate": d1, "parcial": False}
    if t.indexador in ("cdi_pct", "cdi_mais", "selic"):
        f, ate = fator_cdi_realizado(t.indexador, t.taxa, d0, d1, mercado.get("cdi_idx"))
        if f is None:
            return {"fator": fator_projetado(t.indexador, t.taxa, d0, d1, cen), "real_ate": None, "parcial": True}
        parcial = ate < d1
        inicio = pd.DatetimeIndex(mercado["cdi_idx"].dropna().index).normalize().min().date()
        if inicio > d0 + timedelta(days=7):                 # dado do CDI começa depois da aplicação: projeta o começo
            f *= fator_projetado(t.indexador, t.taxa, d0, inicio, cen)
            parcial = True
        if ate < d1:
            f *= fator_projetado(t.indexador, t.taxa, ate, d1, cen)
        return {"fator": f, "real_ate": ate, "parcial": parcial}
    fi, ate = fator_inflacao(d0, d1, mercado, cen)
    return {"fator": fi * (1 + t.taxa) ** (du(d0, d1) / 252), "fator_ipca": fi, "real_ate": ate, "parcial": (ate or d0) < d1}


# =============================================================================== fluxos de pagamento
def datas_de_pagamento(t: Titulo) -> list[date]:
    """Datas de pagamento (juros periódicos contados para trás a partir do vencimento; o último é o vencimento)."""
    if t.tipo in ("tesouro_renda", "tesouro_educa"):
        n = PARCELAS_RENDA if t.tipo == "tesouro_renda" else PARCELAS_EDUCA
        return [somar_meses(t.vencimento, -k) for k in range(n - 1, -1, -1) if somar_meses(t.vencimento, -k) > t.aplicacao]
    pag = t.t.pagamento_padrao if t.t.grupo == "tesouro" else t.pagamento      # Tesouro: o fluxo é definido em lei
    if pag == "vencimento":
        return [t.vencimento]
    passo = MESES_PAGAMENTO[pag]
    out, k = [], 0
    while True:
        d = somar_meses(t.vencimento, -passo * k)
        if d <= t.aplicacao:
            break
        out.append(d)
        k += 1
    out = sorted(out)
    # privados: a aplicação costuma ser a emissão; um primeiro período curto (menos da metade) junta-se ao seguinte.
    # Tesouro: o calendário é legal e o comprador recebe o cupom cheio (o preço já embute os juros corridos).
    if t.t.grupo != "tesouro" and len(out) > 1 and (out[0] - t.aplicacao).days < passo * 15:
        out = out[1:]
    return out


def _pagamento(t: Titulo) -> str:
    return t.t.pagamento_padrao if t.t.grupo == "tesouro" else t.pagamento


def _cupom_contrato(t: Titulo, ini: date, fim: date) -> float:
    """Taxa do período pelo contrato (Tesouro com cupom fixo em lei; os demais pela taxa contratada)."""
    if t.tipo == "tesouro_prefixado_juros":
        return (1 + CUPOM_NTNF) ** 0.5 - 1
    if t.tipo == "tesouro_ipca_juros":
        return (1 + CUPOM_NTNB) ** 0.5 - 1
    return (1 + t.taxa) ** (du(ini, fim) / 252) - 1


def fluxos(t: Titulo, cen: Cenario, mercado: dict | None = None, hoje: date | None = None) -> pd.DataFrame:
    """Fluxo de caixa nominal BRUTO do título: data, juros, amortização, total, se já passou (realizado) e o fator de
    inflação acumulado (para títulos IPCA). Para datas passadas usa dado real quando há; depois, o cenário.

    Regras por tipo:
      - Tudo no vencimento: um fluxo = valor × fator(aplicação → vencimento).
      - Juros periódicos (CDB/debêntures/CRI…): o principal fica parado e cada período paga o rendimento do período.
      - Tesouro Prefixado com juros: cupom de 10% a.a.; o preço pago embute a taxa de compra (TIR = taxa contratada).
      - Tesouro IPCA+ com juros: cupom real de 6% a.a. sobre o valor corrigido pelo IPCA.
      - Renda+/Educa+: parcelas mensais reais iguais que, descontadas à taxa contratada, valem o aplicado."""
    mercado = mercado or {}
    hoje = _d(hoje or date.today())
    datas = datas_de_pagamento(t)
    linhas = []

    def fator_ate(d):
        if d <= hoje:
            return fator_realizado(t, d, mercado, cen)["fator"]
        if t.aplicacao >= hoje:
            return fator_projetado(t.indexador, t.taxa, t.aplicacao, d, cen)
        base = fator_realizado(t, hoje, mercado, cen)["fator"]
        return base * fator_projetado(t.indexador, t.taxa, hoje, d, cen)

    def inflacao_ate(d):
        if t.indexador != "ipca":
            return 1.0
        if t.aplicacao >= hoje:
            return fator_inflacao_projetado(t.aplicacao, d, cen)
        return fator_inflacao(t.aplicacao, d, mercado, cen)[0]

    if t.tipo in ("tesouro_renda", "tesouro_educa"):
        # parcela real constante P tal que Σ P/(1+taxa)^(du/252) = valor (na data de aplicação)
        desc = sum((1 + t.taxa) ** (-du(t.aplicacao, d) / 252) for d in datas)
        p_real = t.valor / desc if desc > 0 else 0.0
        for d in datas:
            fi = inflacao_ate(d)
            principal = p_real * (1 + t.taxa) ** (-du(t.aplicacao, d) / 252)   # quanto do aplicado "comprou" esta parcela
            linhas.append({"data": d, "juros": p_real * fi - principal, "amortizacao": principal, "total": p_real * fi,
                           "fator_ipca": fi})
    elif _pagamento(t) == "vencimento":
        f = fator_ate(t.vencimento)
        linhas.append({"data": t.vencimento, "juros": t.valor * (f - 1), "amortizacao": t.valor, "total": t.valor * f,
                       "fator_ipca": inflacao_ate(t.vencimento)})
    elif t.tipo in ("tesouro_prefixado_juros", "tesouro_ipca_juros"):
        # face (em unidades do valor aplicado) que faz a TIR com cupom fixo = taxa contratada
        ant = t.aplicacao
        cps = []
        for d in datas:
            cps.append((d, _cupom_contrato(t, ant, d)))
            ant = d
        pv = sum(c * (1 + t.taxa) ** (-du(t.aplicacao, d) / 252) for d, c in cps) + (1 + t.taxa) ** (-du(t.aplicacao, datas[-1]) / 252)
        face = t.valor / pv
        for i, (d, c) in enumerate(cps):
            fi = inflacao_ate(d)
            j = face * c * fi
            am = face * fi if i == len(cps) - 1 else 0.0
            linhas.append({"data": d, "juros": j, "amortizacao": am, "total": j + am, "fator_ipca": fi})
    else:
        ant = t.aplicacao
        for i, d in enumerate(datas):
            fi = inflacao_ate(d)
            if t.indexador == "ipca":
                j = t.valor * fi * ((1 + t.taxa) ** (du(ant, d) / 252) - 1)
                am = t.valor * fi if i == len(datas) - 1 else 0.0
            else:
                j = t.valor * (fator_ate(d) / fator_ate(ant) - 1)
                am = t.valor if i == len(datas) - 1 else 0.0
            linhas.append({"data": d, "juros": j, "amortizacao": am, "total": j + am, "fator_ipca": fi})
            ant = d
    df = pd.DataFrame(linhas)
    if not df.empty:
        df["passado"] = df["data"].map(lambda d: d <= hoje)
    return df


def tir(fluxos_: list[tuple[date, float]], d0: date, valor: float) -> float | None:
    """Taxa anual (base 252 DU) que iguala o valor presente dos fluxos ao valor aplicado. Bisseção (robusta)."""
    fl = [(du(d0, d), v) for d, v in fluxos_ if v and du(d0, d) > 0]
    if not fl or valor <= 0:
        return None

    def vp(r):
        return sum(v * (1 + r) ** (-n / 252) for n, v in fl) - valor
    lo, hi = -0.99, 5.0
    if vp(lo) * vp(hi) > 0:
        return None
    for _ in range(200):
        mid = (lo + hi) / 2
        if vp(lo) * vp(mid) <= 0:
            hi = mid
        else:
            lo = mid
        if hi - lo < 1e-10:
            break
    return (lo + hi) / 2


# =============================================================================== resultado até o vencimento (bruto, líquido, real)
def resultado_ate_vencimento(t: Titulo, cen: Cenario, mercado: dict | None = None, hoje: date | None = None) -> dict:
    """Retorno esperado se levar até o vencimento, sob o cenário. Bruto, líquido de IR/IOF/custódia (cada pagamento com a
    alíquota do seu prazo) e real (descontando a inflação do cenário/realizada)."""
    fl = fluxos(t, cen, mercado, hoje)
    if fl.empty:
        return {"ok": False}
    bruto_total = float(fl["total"].sum())
    liq = []
    anos = du(t.aplicacao, t.vencimento) / 252
    custodia = custodia_tesouro(t.tipo, (t.valor + bruto_total) / 2, anos, ate_vencimento=True)
    n = len(fl)
    imposto = 0.0
    for i, r in enumerate(fl.itertuples()):
        dias = dc(t.aplicacao, r.data)
        if t.tipo in ("tesouro_renda", "tesouro_educa"):
            principal = r.amortizacao                      # cada parcela: principal = o que ela custou na aplicação
        elif i == n - 1:
            principal = t.valor
        else:
            principal = 0.0                                # juros periódicos: o pagamento todo é rendimento
        cust = custodia if i == n - 1 else 0.0
        tx = tributar(principal, r.total, dias, t.tipo, cust)
        imposto += tx["ir"] + tx["iof"] + tx["custodia"]
        liq.append((r.data, tx["liquido"]))
    inflacao_fim = fl["fator_ipca"].iloc[-1] if t.indexador == "ipca" else None
    hoje_ = _d(hoje or date.today())
    real_fl = []
    for d, v in liq:
        fi = (fator_inflacao_projetado(t.aplicacao, d, cen) if t.aplicacao >= hoje_
              else fator_inflacao(t.aplicacao, d, mercado, cen)[0])
        real_fl.append((d, v / fi))
    tb = tir([(r.data, r.total) for r in fl.itertuples()], t.aplicacao, t.valor)
    tl = tir(liq, t.aplicacao, t.valor)
    tr = tir(real_fl, t.aplicacao, t.valor)
    return {"ok": True, "fluxos": fl, "bruto_total": bruto_total, "liquido_total": sum(v for _, v in liq),
            "imposto_total": imposto, "custodia": custodia, "taxa_bruta_aa": tb, "taxa_liquida_aa": tl, "taxa_real_aa": tr,
            "anos": anos, "inflacao_fim": inflacao_fim, "cenario": cen.nome}


# =============================================================================== situação hoje (curva) e marcação a mercado
def valor_na_curva(t: Titulo, mercado: dict, cen: Cenario, hoje: date | None = None) -> dict:
    """Quanto o título vale hoje PELA TAXA CONTRATADA (o que se recebe com liquidez diária pela curva), já descontados os
    pagamentos recebidos. Rendimento acumulado e anualizado REALIZADOS (até onde há dado real)."""
    hoje = _d(hoje or date.today())
    ref = min(hoje, t.vencimento)
    if ref < t.aplicacao:
        return {"ok": False, "motivo": "título ainda não aplicado (data de aplicação no futuro)"}
    if ref == t.aplicacao:
        return {"ok": True, "valor_atual": t.valor, "recebido": 0.0, "acumulado": 0.0, "anualizado": None, "dias": 0,
                "real_ate": None, "parcial": False, "fator_ipca": 1.0}
    fr = fator_realizado(t, ref, mercado, cen)
    fl = fluxos(t, cen, mercado, hoje)
    recebido = float(fl.loc[fl["passado"], "total"].sum()) if not fl.empty else 0.0
    if _pagamento(t) == "vencimento":
        atual = t.valor * fr["fator"] if hoje < t.vencimento else 0.0
    else:
        futuros = fl[~fl["passado"]] if not fl.empty else fl
        if futuros.empty:
            atual = 0.0
        else:
            taxa_desc = t.taxa
            fi_hoje = fr.get("fator_ipca", 1.0) if t.indexador == "ipca" else 1.0
            if t.indexador in ("pre", "ipca"):
                atual = sum((r.total / (r.fator_ipca if t.indexador == "ipca" else 1.0)) * fi_hoje
                            * (1 + taxa_desc) ** (-du(hoje, r.data) / 252) for r in futuros.itertuples())
            else:
                atual = t.valor * (fr["fator"] / max(fator_realizado(t, _ultimo_pagamento(fl, hoje) or t.aplicacao, mercado, cen)["fator"], 1e-12))
    total = atual + recebido
    dias = dc(t.aplicacao, ref)
    anos = du(t.aplicacao, ref) / 252
    acum = total / t.valor - 1
    return {"ok": True, "valor_atual": atual, "recebido": recebido, "acumulado": acum,
            "anualizado": (1 + acum) ** (1 / anos) - 1 if anos >= 0.25 and acum > -1 else None,
            "dias": dias, "real_ate": fr.get("real_ate"), "parcial": fr.get("parcial", False),
            "fator_ipca": fr.get("fator_ipca")}


def _ultimo_pagamento(fl: pd.DataFrame, hoje: date) -> date | None:
    p = fl[fl["passado"]] if not fl.empty else fl
    return p["data"].iloc[-1] if len(p) else None


def preco_pela_taxa(t: Titulo, taxa_mercado: float, mercado: dict, cen: Cenario, hoje: date | None = None) -> dict:
    """Preço ESTIMADO hoje descontando os fluxos futuros à taxa de mercado (prefixados e IPCA+, em termos reais). Pós-fixados
    (CDI/Selic): o preço varia com o PRÊMIO (spread) do emissor, não com o CDI: taxa_mercado é o novo spread/percentual.
    Devolve preço, duration (Macaulay e modificada) e o valor na curva para comparar."""
    hoje = _d(hoje or date.today())
    if hoje >= t.vencimento:
        return {"ok": False, "motivo": "título vencido"}
    fl = fluxos(t, cen, mercado, hoje)
    fut = fl[~fl["passado"]]
    if fut.empty:
        return {"ok": False, "motivo": "sem pagamentos futuros"}
    curva = valor_na_curva(t, mercado, cen, hoje)
    if t.indexador in ("pre", "ipca"):
        fi_hoje = (curva.get("fator_ipca") or 1.0) if t.indexador == "ipca" else 1.0
        reais = [(r.data, r.total / (r.fator_ipca if t.indexador == "ipca" else 1.0)) for r in fut.itertuples()]

        def p(taxa):
            return sum(v * (1 + taxa) ** (-du(hoje, d) / 252) for d, v in reais) * fi_hoje
        preco = p(taxa_mercado)
        if preco <= 0:
            return {"ok": False, "motivo": "preço indefinido"}
        mac = sum((du(hoje, d) / 252) * v * fi_hoje * (1 + taxa_mercado) ** (-du(hoje, d) / 252) for d, v in reais) / preco
        mod = mac / (1 + taxa_mercado)
        sens = {dlt: p(taxa_mercado + dlt) / preco - 1 for dlt in (-0.02, -0.01, 0.01, 0.02)}
        return {"ok": True, "preco": preco, "curva": curva.get("valor_atual"), "mac": mac, "mod": mod, "sens": sens,
                "taxa_mercado": taxa_mercado, "tipo_risco": "juros"}
    # pós-fixados: duration de juros ≈ 0; o que mexe no preço é o spread
    prazo = du(hoje, t.vencimento) / 252
    if t.indexador == "cdi_pct":
        cdi = cen.cdi_de(hoje.year)
        s_c, s_m = (t.taxa - 1) * cdi, (taxa_mercado - 1) * cdi
    else:
        s_c, s_m = t.taxa, taxa_mercado
    base = curva.get("valor_atual") or 0.0
    preco = base * ((1 + s_c) / (1 + s_m)) ** prazo
    sens = {dlt: ((1 + s_c) / (1 + s_m + dlt)) ** prazo * ((1 + s_m) / (1 + s_c)) ** prazo - 1 for dlt in (-0.01, -0.005, 0.005, 0.01)}
    return {"ok": True, "preco": preco, "curva": base, "mac": 0.0, "mod": 0.0, "duration_spread": prazo, "sens": sens,
            "taxa_mercado": taxa_mercado, "tipo_risco": "spread"}


# =============================================================================== curva do Tesouro (referência de mercado)
CURVA_PRE = ("tesouro_prefixado", "tesouro_prefixado_juros")
CURVA_REAL = ("tesouro_ipca", "tesouro_ipca_juros")


def curva_tesouro(td: pd.DataFrame, data_ref, indexador: str, campo: str = "taxa_compra", tolerancia: int = 7) -> pd.Series:
    """Taxas (% a.a., fração) do Tesouro numa data, por prazo em anos (DU/252), para usar como referência: prefixados
    (LTN/NTN-F) ou IPCA+ (NTN-B). Usa a última data disponível até `data_ref` (tolerância em dias)."""
    if td is None or td.empty or campo not in td:
        return pd.Series(dtype=float)
    tipos = CURVA_PRE if indexador == "pre" else CURVA_REAL if indexador == "ipca" else ()
    if not tipos:
        return pd.Series(dtype=float)
    x = td[td["titulo"].map(lambda n: tipo_do_tesouro(n) in tipos)]
    dref = pd.Timestamp(_d(data_ref))
    x = x[(x["data"] <= dref) & (x["data"] >= dref - pd.Timedelta(days=tolerancia))]
    if x.empty:
        return pd.Series(dtype=float)
    ult = x["data"].max()
    x = x[(x["data"] == ult) & x[campo].notna()]
    prazos = x["venc"].map(lambda v: du(ult, v) / 252)
    s = pd.Series((x[campo] / 100).values, index=prazos.values).sort_index()
    s = s[s.index > 0]
    return s[~s.index.duplicated(keep="first")]


def interpolar(curva: pd.Series, prazo: float) -> float | None:
    if curva is None or curva.empty:
        return None
    xs, ys = curva.index.to_numpy(float), curva.to_numpy(float)
    return float(np.interp(prazo, xs, ys))


def taxa_de_mercado_estimada(t: Titulo, td: pd.DataFrame, hoje: date | None = None) -> dict:
    """Taxa de mercado para marcar um título privado prefixado ou IPCA+: curva do Tesouro de hoje no prazo restante MAIS
    o prêmio que o título pagava sobre o Tesouro na data da aplicação (premissa: o prêmio de crédito não mudou)."""
    hoje = _d(hoje or date.today())
    if t.indexador not in ("pre", "ipca"):
        return {"ok": False, "motivo": "pós-fixado: o preço depende do prêmio do emissor, não da curva de juros"}
    c0 = curva_tesouro(td, t.aplicacao, t.indexador)
    c1 = curva_tesouro(td, hoje, t.indexador)
    if c0.empty or c1.empty:
        return {"ok": False, "motivo": "sem taxas do Tesouro na data da aplicação ou hoje"}
    r0 = interpolar(c0, du(t.aplicacao, t.vencimento) / 252)
    r1 = interpolar(c1, du(hoje, t.vencimento) / 252)
    premio = t.taxa - r0
    return {"ok": True, "taxa": r1 + premio, "premio": premio, "tesouro_aplicacao": r0, "tesouro_hoje": r1}


# =============================================================================== riscos
def risco_credito(t: Titulo) -> dict:
    """1 (soberano) a 5 (alto), pela classe do título, cobertura do FGC e rating informado. Rating abaixo de BBB (grau
    especulativo) sobe um nível. Não é rating: é uma régua educacional."""
    nivel = t.t.risco_credito
    motivo = {1: "risco soberano (Tesouro Nacional)", 2: "banco, com cobertura do FGC até o limite",
              3: "banco, sem cobertura do FGC", 4: "empresa ou securitização, sem FGC"}[nivel]
    r = (t.rating or "").upper().replace(" ", "")
    m = re.match(r"(AAA|AA|A|BBB|BB|B|CCC|CC|C|D)", re.sub(r"^BR|\(.*", "", r))
    grau = m.group(1) if m else None
    if grau in ("BB", "B", "CCC", "CC", "C", "D") and nivel > 1:
        nivel = min(nivel + 1, 5)
        motivo += f"; rating {grau} (grau especulativo)"
    elif grau and nivel > 1:
        motivo += f"; rating {grau} informado"
    elif nivel >= 3:
        motivo += "; sem rating informado"
    return {"nivel": nivel, "texto": ["", "muito baixo", "baixo", "moderado", "alto", "muito alto"][nivel], "motivo": motivo,
            "grau": grau}


def dias_ate_liquidez(t: Titulo, hoje: date | None = None) -> int:
    hoje = _d(hoje or date.today())
    if t.t.grupo == "tesouro" or t.liquidez == "diaria":
        return 1
    if t.liquidez == "carencia" and t.carencia:
        return max(dc(hoje, t.carencia), 1)
    return max(dc(hoje, t.vencimento), 0)


def riscos(t: Titulo, mam: dict | None, hoje: date | None = None, carteira_emissor_pct: float | None = None) -> list[dict]:
    """Os 10 riscos pedidos, cada um com nível (baixo/médio/alto/n.a.) e explicação baseada no próprio título."""
    hoje = _d(hoje or date.today())
    tp = t.t
    prazo = max(du(hoje, t.vencimento) / 252, 0)
    rc = risco_credito(t)
    mod = (mam or {}).get("mod")
    out = []

    def add(nome, nivel, txt):
        out.append({"risco": nome, "nivel": nivel, "explicacao": txt})
    add("Crédito", "baixo" if rc["nivel"] <= 2 else "médio" if rc["nivel"] == 3 else "alto",
        f"Nível {rc['nivel']}/5 ({rc['texto']}): {rc['motivo']}.")
    if t.indexador in ("cdi_pct", "cdi_mais", "selic"):
        add("Mercado (juros)", "baixo", "Pós-fixado: acompanha os juros do dia; o preço quase não reage à Selic, só ao prêmio do emissor.")
    elif mod is not None:
        add("Mercado (juros)", "alto" if mod >= 5 else "médio" if mod >= 2 else "baixo",
            f"Duration modificada de {_br(mod, 1)}: se as taxas subirem 1 p.p., o preço cai cerca de {_br(mod, 1)}%.")
    else:
        add("Mercado (juros)", "médio" if prazo > 2 else "baixo", f"Prefixado/IPCA+ com {_br(prazo, 1)} anos até o vencimento.")
    d_liq = dias_ate_liquidez(t, hoje)
    add("Liquidez", "baixo" if d_liq <= 1 else "médio" if d_liq <= 365 else "alto",
        tp.liquidez_tipica if tp.grupo == "tesouro" else
        (f"{LIQUIDEZ.get(t.liquidez, t.liquidez)}: dinheiro disponível em {d_liq} dia(s)." +
         (" " + _LIQ_SECUNDARIO if tp.grupo == "credito_privado" else "")))
    add("Reinvestimento", "médio" if _pagamento(t) != "vencimento" or prazo < 1 else "baixo",
        "Recebe juros periódicos (ou vence logo): o dinheiro precisa ser reaplicado, talvez a taxas menores."
        if _pagamento(t) != "vencimento" or prazo < 1 else "Paga tudo no vencimento: os juros rendem pela taxa contratada até o fim.")
    add("Inflação", "alto" if t.indexador == "pre" and prazo > 3 else "médio" if t.indexador == "pre" else "baixo",
        "Prefixado: se a inflação subir, o ganho real cai." if t.indexador == "pre" else
        "Atrelado ao IPCA: protegido da inflação até o vencimento." if t.indexador == "ipca" else
        "Pós-fixado: o CDI tende a subir com a inflação, protegendo em parte.")
    add("Duration", "n.a." if mod is None else ("alto" if mod >= 5 else "médio" if mod >= 2 else "baixo"),
        "Não se aplica a pós-fixados (a duration de juros é quase zero)." if mod is None else
        f"Prazo médio ponderado dos pagamentos (Macaulay) de {_br(mam['mac'], 1)} anos.")
    add("Marcação a mercado", "baixo" if t.indexador in ("cdi_pct", "cdi_mais", "selic") else
        ("alto" if prazo > 5 else "médio"),
        "Só importa se vender antes do vencimento: o preço do dia pode estar acima ou abaixo da curva.")
    if carteira_emissor_pct is None:
        add("Concentração por emissor", "n.a.", "Veja na Carteira (precisa dos outros títulos para medir).")
    else:
        add("Concentração por emissor", "alto" if carteira_emissor_pct > 25 else "médio" if carteira_emissor_pct > 10 else "baixo",
            f"Este emissor é {_br(carteira_emissor_pct, 0)}% da renda fixa da carteira.")
    add("Vencimento", "médio" if prazo > 10 else "baixo",
        f"Vence em {_br(prazo, 1)} anos ({t.vencimento.strftime('%d/%m/%Y')}). Prazos longos aumentam a incerteza.")
    if tp.grupo == "tesouro":
        add("Garantias", "baixo", "Garantia do Tesouro Nacional (risco soberano). Não há FGC: não é necessário.")
    elif tp.fgc:
        add("Garantias", "médio" if t.valor > FGC_LIMITE else "baixo",
            f"FGC cobre até R$ 250 mil por CPF por instituição/conglomerado (teto de R$ 1 milhão a cada 4 anos)"
            + (": este título passa do limite." if t.valor > FGC_LIMITE else "."))
    else:
        add("Garantias", "alto" if not t.garantia else "médio",
            ("Sem FGC. Garantia informada: " + t.garantia + " (o app não avalia se é suficiente).") if t.garantia else
            "Sem FGC e sem garantia informada: em caso de calote, o investidor vira credor comum.")
    return out


# =============================================================================== simulador
def simular(inicial: float, aporte: float, meses: int, indexador: str, taxa: float, cen: Cenario, tipo_chave: str = "cdb",
            inicio: date | None = None, resgate_mes: int | None = None, choque_juros: float = 0.0,
            reinvestir: bool = True) -> dict:
    """Aplicação inicial + aportes mensais (no fim de cada mês), juros compostos pelo indexador sob o cenário.
      - IR por aporte (cada parcela com a sua idade) e IOF se a parcela tiver menos de 30 dias.
      - reinvestir=False: os juros de cada mês são sacados (pagos ao investidor, com IR na hora) e não rendem mais.
      - resgate_mes < meses: resgate antecipado. Prefixados e IPCA+ sofrem a marcação a mercado de um choque nas taxas
        (`choque_juros`, fração; +0,01 = juros 1 p.p. maiores). Pós-fixados: sem choque (o preço quase não reage).
    Valores bruto, líquido e real (deflacionado pelo IPCA do cenário)."""
    inicio = _d(inicio or date.today())
    fim_m = meses if resgate_mes is None else max(min(resgate_mes, meses), 1)
    parcelas = [(0, inicial)] + [(m, aporte) for m in range(1, fim_m + 1) if aporte > 0]
    datas = [somar_meses(inicio, m) for m in range(fim_m + 1)]
    sacado_liq = {k: 0.0 for k in range(len(parcelas))}
    sacado_bruto = {k: 0.0 for k in range(len(parcelas))}
    linhas = []
    for mes in range(fim_m + 1):
        d_mes = datas[mes]
        bruto = liquido = investido = 0.0
        for k, (m0, v) in enumerate(parcelas):
            if m0 > mes:
                continue
            investido += v
            d0 = datas[m0]
            if reinvestir:
                valor = v * fator_projetado(indexador, taxa, d0, d_mes, cen)
                bruto += valor
                liquido += tributar(v, valor, dc(d0, d_mes), tipo_chave)["liquido"]
            else:
                if mes > m0:
                    juros = v * (fator_projetado(indexador, taxa, datas[mes - 1], d_mes, cen) - 1)
                    sacado_liq[k] += tributar(0.0, juros, dc(d0, d_mes), tipo_chave)["liquido"]
                    sacado_bruto[k] += juros
                bruto += v
                liquido += v
        if not reinvestir:
            liquido += sum(sacado_liq.values())
            bruto += sum(sacado_bruto.values())
        infl = fator_inflacao_projetado(inicio, d_mes, cen)
        linhas.append({"mes": mes, "investido": investido, "bruto": bruto, "liquido": liquido, "real": liquido / infl})
    ult = dict(linhas[-1])
    ajuste_mam = 0.0
    antecipado = resgate_mes is not None and resgate_mes < meses
    if antecipado and indexador in ("pre", "ipca") and choque_juros:
        restante = du(datas[fim_m], somar_meses(inicio, meses)) / 252
        ajuste_mam = ((1 + taxa) / (1 + taxa + choque_juros)) ** restante - 1
        bruto = liquido = 0.0
        for m0, v in parcelas:
            valor = v * fator_projetado(indexador, taxa, datas[m0], datas[fim_m], cen) * (1 + ajuste_mam)
            bruto += valor
            liquido += tributar(v, valor, dc(datas[m0], datas[fim_m]), tipo_chave)["liquido"]
        ult.update(bruto=bruto, liquido=liquido, real=liquido / fator_inflacao_projetado(inicio, datas[fim_m], cen))
        linhas[-1] = ult
    return {"linhas": linhas, "investido": ult["investido"], "bruto": ult["bruto"], "liquido": ult["liquido"],
            "real": ult["real"], "imposto": ult["bruto"] - ult["liquido"], "ajuste_mam": ajuste_mam,
            "meses": fim_m, "antecipado": antecipado}


def tabela_cenarios(t: Titulo, base: Cenario, mercado: dict | None = None, hoje: date | None = None,
                    d_cdi=(-0.02, 0.0, 0.02), d_ipca=(-0.015, 0.0, 0.015)) -> pd.DataFrame:
    """Retorno líquido e real até o vencimento em cenários de CDI e IPCA diferentes do base (premissas, não previsões)."""
    linhas = []
    for dc_ in d_cdi:
        for di in d_ipca:
            c = cenario_deslocado(base, dc_, di)
            r = resultado_ate_vencimento(t, c, mercado, hoje)
            if not r["ok"]:
                continue
            linhas.append({"CDI": dc_, "IPCA": di, "liquido_total": r["liquido_total"], "taxa_liquida_aa": r["taxa_liquida_aa"],
                           "taxa_real_aa": r["taxa_real_aa"]})
    return pd.DataFrame(linhas)


# =============================================================================== carteira de renda fixa
_PALAVRAS_EMISSOR = {"s", "a", "sa", "banco", "bco", "financeira", "ltda", "cia", "companhia", "de", "do", "da", "dos", "das"}


def emissor_chave(t: Titulo) -> str:
    """Nome do emissor sem pontuação, 'S.A.', 'Banco' e afins, para agrupar 'Banco X S.A.' e 'banco x'."""
    e = _norm(t.emissor) or ("tesouro nacional" if t.t.grupo == "tesouro" else "(emissor não informado)")
    tokens = [w for w in re.sub(r"[^\w\s]", " ", e).split() if w not in _PALAVRAS_EMISSOR]
    return " ".join(tokens) or e


def analisar_carteira(titulos: list[Titulo], valores: dict, fluxos_futuros: dict | None = None,
                      hoje: date | None = None) -> dict:
    """valores: id -> valor atual (curva) de cada título. Exposição por emissor, indexador e tipo; FGC por emissor; escada
    de vencimentos; liquidez por prazo; fluxo de recebimentos (se fluxos_futuros: id -> DataFrame de fluxos); alertas."""
    hoje = _d(hoje or date.today())
    ativos = [t for t in titulos if t.vencimento > hoje and (valores.get(t.id) or 0) > 0]
    total = sum(valores[t.id] for t in ativos)
    out = {"total": total, "n": len(ativos), "alertas": []}
    if not ativos or total <= 0:
        out["alertas"].append("Nenhum título vigente com valor para analisar.")
        return out

    def agrupa(f):
        g: dict = {}
        for t in ativos:
            g[f(t)] = g.get(f(t), 0.0) + valores[t.id]
        return dict(sorted(g.items(), key=lambda x: -x[1]))
    nomes_emissor = {}
    for t in ativos:
        nomes_emissor.setdefault(emissor_chave(t), t.emissor or ("Tesouro Nacional" if t.t.grupo == "tesouro" else "(não informado)"))
    por_em = agrupa(emissor_chave)
    out["por_emissor"] = {nomes_emissor[k]: v for k, v in por_em.items()}
    out["por_indexador"] = {INDEXADORES[k].split(" (")[0]: v for k, v in agrupa(lambda t: t.indexador).items()}
    out["por_tipo"] = {TIPOS[k].nome: v for k, v in agrupa(lambda t: t.tipo).items()}
    out["por_credito"] = agrupa(lambda t: f"{risco_credito(t)['nivel']} · {risco_credito(t)['texto']}")
    privado = {k: v for k, v in por_em.items() if k != "tesouro nacional"}
    pesos = [v / total for v in privado.values()]
    out["hhi_privado"] = sum(p * p for p in pesos) if pesos else None
    for k, v in privado.items():
        if v / total > 0.25:
            out["alertas"].append(f"{nomes_emissor[k]} concentra {_br(v / total * 100, 0)}% da renda fixa (acima de 25% em um só emissor privado).")
    fgc_em: dict = {}
    for t in ativos:
        if t.t.fgc:
            fgc_em[emissor_chave(t)] = fgc_em.get(emissor_chave(t), 0.0) + valores[t.id]
    out["fgc"] = []
    for k, v in sorted(fgc_em.items(), key=lambda x: -x[1]):
        exc = max(v - FGC_LIMITE, 0.0)
        out["fgc"].append({"emissor": nomes_emissor[k], "coberto_pelo_fgc": min(v, FGC_LIMITE), "valor": v, "excedente": exc})
        if exc > 0:
            out["alertas"].append(f"{nomes_emissor[k]}: R$ {_br(v)} em títulos com FGC; R$ {_br(exc)} passam do limite de "
                                  "R$ 250 mil por CPF e instituição (o limite é por conglomerado: confira se outros bancos são do mesmo grupo).")
    if sum(fgc_em.values()) > FGC_TETO_4ANOS:
        out["alertas"].append("Mais de R$ 1 milhão em títulos com FGC: o teto global de garantia é R$ 1 milhão a cada 4 anos por CPF.")
    sem_fgc = [t for t in ativos if not t.t.fgc and t.t.grupo != "tesouro"]
    if sem_fgc:
        out["alertas"].append(f"{len(sem_fgc)} título(s) sem FGC (LF, debêntures, CRI, CRA ou outros): o risco é só do emissor.")
    venc: dict = {}
    for t in ativos:
        venc[t.vencimento.year] = venc.get(t.vencimento.year, 0.0) + valores[t.id]
    out["vencimentos_por_ano"] = dict(sorted(venc.items()))
    out["proximos"] = sorted([(t.vencimento, t.rotulo(), valores[t.id]) for t in ativos if dc(hoje, t.vencimento) <= 365])
    faixas = {"Em até 1 dia": 0.0, "Até 30 dias": 0.0, "Até 90 dias": 0.0, "Até 1 ano": 0.0, "Mais de 1 ano": 0.0}
    for t in ativos:
        d = dias_ate_liquidez(t, hoje)
        k = ("Em até 1 dia" if d <= 1 else "Até 30 dias" if d <= 30 else "Até 90 dias" if d <= 90 else
             "Até 1 ano" if d <= 365 else "Mais de 1 ano")
        faixas[k] += valores[t.id]
    out["liquidez"] = faixas
    if faixas["Em até 1 dia"] / total < 0.10:
        out["alertas"].append("Menos de 10% da renda fixa tem liquidez diária: confira se há reserva de emergência fora daqui.")
    prazo_medio = sum(valores[t.id] * du(hoje, t.vencimento) / 252 for t in ativos) / total
    out["prazo_medio_anos"] = prazo_medio
    if fluxos_futuros:
        meses: dict = {}
        lim = somar_meses(hoje, 24)
        for t in ativos:
            fl = fluxos_futuros.get(t.id)
            if fl is None or fl.empty:
                continue
            for r in fl[~fl["passado"]].itertuples():
                if r.data <= lim:
                    k = date(r.data.year, r.data.month, 1)
                    meses[k] = meses.get(k, 0.0) + float(r.total)
        out["fluxo_24m"] = dict(sorted(meses.items()))
    altos = [t for t in ativos if risco_credito(t)["nivel"] >= 4]
    if altos and sum(valores[t.id] for t in altos) / total > 0.30:
        out["alertas"].append("Mais de 30% da renda fixa em crédito de risco alto (empresas, securitização ou rating especulativo).")
    return out


# =============================================================================== nota educacional (para o comparador)
def pontuar(ind: dict) -> dict:
    """Pilares 0-100: retorno real líquido esperado (35%), crédito (25%), liquidez (20%) e risco de mercado (20%).
    Sem dado, o pilar sai da nota. Retorno ESPERADO (premissa), nunca garantido."""
    def esc(x, ruim, bom):
        if x is None or not math.isfinite(x):
            return None
        return max(0.0, min(100.0, (x - ruim) / (bom - ruim) * 100))
    pil = {"Retorno real esperado": esc(ind.get("taxa_real_aa"), 0.0, 0.08),
           "Crédito": esc(ind.get("risco_credito"), 5, 1),
           "Liquidez": esc(math.log10(max(ind["liquidez_dias"], 1)) if ind.get("liquidez_dias") is not None else None, math.log10(3650), 0),
           "Risco de mercado": esc(ind.get("duration"), 10, 0)}
    pesos = {"Retorno real esperado": 35, "Crédito": 25, "Liquidez": 20, "Risco de mercado": 20}
    com = {k: v for k, v in pil.items() if v is not None}
    cob = sum(pesos[k] for k in com) / sum(pesos.values())
    nota = sum(pil[k] * pesos[k] for k in com) / sum(pesos[k] for k in com) if com and cob >= 0.5 else None
    return {"nota": nota, "pilares": pil, "pesos": pesos, "cobertura": cob, "provisoria": cob < 0.7}


# =============================================================================== análise inteligente (texto)
def relatorio(t: Titulo, curva: dict, venc: dict, mam: dict | None, rs: list[dict], cdi_ref: float | None,
              ipca_ref: float | None, hoje: date | None = None) -> dict:
    """Pontos positivos, de atenção e conclusão, só com números calculados. Nunca diz para comprar ou vender."""
    hoje = _d(hoje or date.today())
    pos, neg = [], []
    tp = t.t
    if venc.get("ok") and venc.get("taxa_real_aa") is not None:
        r = venc["taxa_real_aa"]
        (pos if r >= 0.04 else neg if r < 0.02 else pos).append(
            f"Retorno real líquido esperado de {_br(r * 100)}% a.a. até o vencimento ({venc['cenario']}).")
    if venc.get("ok") and cdi_ref and venc.get("taxa_liquida_aa") is not None:
        cdi_liq = cdi_ref * (1 - aliquota_ir(dc(t.aplicacao, t.vencimento)))
        if venc["taxa_liquida_aa"] >= cdi_liq:
            pos.append(f"Rende líquido {_br(venc['taxa_liquida_aa'] * 100)}% a.a., acima do CDI líquido de hoje ({_br(cdi_liq * 100)}% a.a.).")
        else:
            neg.append(f"Rende líquido {_br(venc['taxa_liquida_aa'] * 100)}% a.a., abaixo do CDI líquido de hoje ({_br(cdi_liq * 100)}% a.a.).")
    if tp.isento_ir_pf:
        pos.append("Isento de IR para pessoa física.")
    if tp.grupo == "tesouro":
        pos.append("Risco de crédito soberano (Tesouro Nacional).")
    elif tp.fgc:
        (pos if t.valor <= FGC_LIMITE else neg).append(
            "Coberto pelo FGC até R$ 250 mil por instituição." + ("" if t.valor <= FGC_LIMITE else " O valor aplicado passa do limite."))
    else:
        neg.append("Sem cobertura do FGC: o risco de crédito é todo do investidor.")
    for r in rs:
        if r["nivel"] == "alto" and r["risco"] not in ("Crédito",):
            neg.append(f"Risco de {r['risco'].lower()} alto: {r['explicacao']}")
    if mam and mam.get("ok") and mam.get("curva"):
        dif = mam["preco"] / mam["curva"] - 1
        if abs(dif) >= 0.005:
            (pos if dif > 0 else neg).append(
                f"Pela taxa de mercado estimada, venderia hoje {'acima' if dif > 0 else 'abaixo'} da curva ({_br(dif * 100, 1)}%). "
                "Estimativa, não preço executável.")
    if curva.get("ok") and curva.get("parcial"):
        neg.append("Parte do rendimento até hoje é projeção: o dado real do indexador ainda não cobre todo o período.")
    conc = ("Título com retorno e riscos descritos acima. A taxa contratada só é garantida até o vencimento e depende do "
            "emissor pagar; vender antes expõe ao preço do dia. Ferramenta educacional, não é recomendação.")
    return {"Pontos positivos": pos, "Pontos de atenção": neg, "Conclusão": [conc]}
