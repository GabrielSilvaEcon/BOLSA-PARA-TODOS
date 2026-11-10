"""Classes de ativos da carteira virtual (Wallet Game). Lógica pura: sem Streamlit, sem banco e sem rede.

Todo ativo da carteira tem um identificador de texto. Os da B3 continuam como sempre (PETR4, HGLG11, BOVA11), então as carteiras
antigas seguem valendo. Os demais ganham um prefixo:

    PETR4 / HGLG11 / BOVA11   B3 (ação, FII ou ETF; a classe vem do catálogo do app)
    US:VOO                    ETF americano (preço em dólar convertido para reais)
    CRIPTO:BTC                criptomoeda (Binance, par em dólar convertido para reais)
    FUNDO:12345678000190      fundo de investimento (cota da CVM, informe diário)
    TD:SELIC-20310301         título do Tesouro Direto sem cupom (preço unitário do Tesouro Transparente)
    RF:CDI                    renda fixa pós-fixada que rende 100% do CDI (cota virtual que acompanha o CDI diário)

Cada classe tem custo de negociação e passo de quantidade próprios (cripto e fundos aceitam frações; B3 só cotas inteiras).
"""
from __future__ import annotations

import re

# ------------------------------------------------------------------ classes
# custo: por compra e por venda. passo: menor fração negociável. cor/icone: só apresentação.
CLASSES = {
    "acao":   {"nome": "Ações", "singular": "ação", "cor": "#8B6CFF", "icone": "📈", "custo": 0.0005, "passo": 1.0,
               "resumo": "Pedaços de empresas. Podem render com valorização e dividendos, mas oscilam bastante."},
    "fii":    {"nome": "FIIs", "singular": "FII", "cor": "#2BA7C9", "icone": "🏢", "custo": 0.0005, "passo": 1.0,
               "resumo": "Fundos imobiliários. Costumam pagar renda todo mês (aluguéis ou juros de recebíveis)."},
    "etf":    {"nome": "ETFs", "singular": "ETF", "cor": "#D23FC8", "icone": "🧺", "custo": 0.0005, "passo": 1.0,
               "resumo": "Cestas prontas de ativos (índices). Uma cota já traz dezenas de empresas ou mercados."},
    "cripto": {"nome": "Criptomoedas", "singular": "criptomoeda", "cor": "#F2B84B", "icone": "🪙", "custo": 0.002, "passo": 0.0001,
               "resumo": "Ativos digitais. Muito voláteis: poucos pontos percentuais já bastam para somar diversificação."},
    "fundo":  {"nome": "Fundos", "singular": "fundo", "cor": "#7A8CFF", "icone": "🗂️", "custo": 0.0, "passo": 0.01,
               "resumo": "Dinheiro de muita gente reunido e gerido por um profissional. Você compra cotas."},
    "rf":     {"nome": "Renda fixa", "singular": "título de renda fixa", "cor": "#3DDC97", "icone": "🏦", "custo": 0.0, "passo": 0.01,
               "resumo": "Empréstimos ao governo ou a bancos. Variam menos e ajudam a segurar a carteira nas quedas."},
}
CAIXA = {"nome": "Caixa (parado)", "cor": "#9AA3B2", "icone": "💵"}
ORDEM = ("acao", "fii", "etf", "cripto", "fundo", "rf")

# ------------------------------------------------------------------ universo fixo
ETFS_B3 = ("BOVA11", "IVVB11", "SMAL11", "DIVO11", "IMAB11", "HASH11", "GOLD11", "NASD11")
ETFS_EUA = ("VOO", "QQQ", "SCHD", "VT")
CRIPTOS = ("BTC", "ETH", "BNB", "SOL", "XRP", "ADA", "DOGE", "AVAX", "LINK", "DOT", "LTC", "TRX")
FIIS_LIQUIDOS = ("HGLG11", "KNRI11", "XPML11", "MXRF11", "VISC11", "XPLG11", "BTLG11", "KNCR11", "HGRU11", "TRXF11", "KNIP11", "RBRR11")
NOMES_CRIPTO = {"BTC": "Bitcoin", "ETH": "Ethereum", "BNB": "BNB", "SOL": "Solana", "XRP": "XRP", "ADA": "Cardano", "DOGE": "Dogecoin",
                "AVAX": "Avalanche", "LINK": "Chainlink", "DOT": "Polkadot", "LTC": "Litecoin", "TRX": "TRON"}
NOMES_EUA = {"VOO": "ETF S&P 500 (EUA)", "QQQ": "ETF Nasdaq 100 (EUA)", "SCHD": "ETF de dividendos (EUA)", "VT": "ETF mundo todo"}
RF_CDI = "RF:CDI"

# ------------------------------------------------------------------ identificadores
_B3 = re.compile(r"[A-Z]{4}\d{1,2}")
_US = re.compile(r"US:[A-Z]{1,5}")
_CRIPTO = re.compile(r"CRIPTO:[A-Z0-9]{2,10}")
_FUNDO = re.compile(r"FUNDO:\d{14}")
_TD = re.compile(r"TD:(SELIC|PRE|IPCA)-(\d{4})(\d{2})(\d{2})")

TD_TIPOS = {"SELIC": "Tesouro Selic", "PRE": "Tesouro Prefixado", "IPCA": "Tesouro IPCA+"}
TD_NOME_CSV = {"tesouro selic": "SELIC", "tesouro prefixado": "PRE", "tesouro ipca+": "IPCA"}   # só os sem cupom (os com juros semestrais ficam de fora)


def valido(ativo) -> bool:
    a = str(ativo or "")
    return bool(_B3.fullmatch(a) or _US.fullmatch(a) or _CRIPTO.fullmatch(a) or _FUNDO.fullmatch(a) or _TD.fullmatch(a) or a == RF_CDI)


def eh_b3(ativo) -> bool:
    """Negociado no calendário de pregões da B3 (ação, FII ou ETF da B3). Só esses definem os dias de fechamento da competição."""
    return bool(_B3.fullmatch(str(ativo or "")))


def _catalogo_acao(tk: str) -> bool:
    try:
        import recursos
        return tk in recursos.POR_TICKER
    except Exception:
        return False


def classe(ativo) -> str | None:
    """'acao', 'fii', 'etf', 'cripto', 'fundo' ou 'rf' (None se o identificador não é válido)."""
    a = str(ativo or "")
    if _B3.fullmatch(a):
        if a in ETFS_B3:
            return "etf"
        if _catalogo_acao(a):
            return "acao"                       # units (KLBN11, TAEE11...) estão no catálogo de ações
        if a in FIIS_LIQUIDOS or a.endswith("11"):
            return "fii"
        return "acao"
    if _US.fullmatch(a):
        return "etf"
    if _CRIPTO.fullmatch(a):
        return "cripto"
    if _FUNDO.fullmatch(a):
        return "fundo"
    if _TD.fullmatch(a) or a == RF_CDI:
        return "rf"
    return None


def passo(ativo) -> float:
    c = classe(ativo)
    return CLASSES[c]["passo"] if c else 1.0


def custo(ativo) -> float:
    """Custo de negociação (fração do valor) em cada compra e em cada venda."""
    c = classe(ativo)
    return CLASSES[c]["custo"] if c else 0.0005


def isento_peso(ativo) -> bool:
    """Caixa rendendo (CDI e Tesouro Selic) não entra no limite de concentração por ativo: é onde se guarda a reserva."""
    a = str(ativo or "")
    return a == RF_CDI or a.startswith("TD:SELIC-")


def norm_qtd(ativo, q) -> int | float:
    """Quantidade arredondada para o passo da classe. Inteiro (int) quando o passo é 1; senão float com até 8 casas."""
    p = passo(ativo)
    n = round(float(q) / p)
    if p >= 1:
        return int(n * p)
    return round(n * p, 8)


def qtd_valida(ativo, q) -> bool:
    try:
        x = float(q)
    except Exception:
        return False
    if not (x > 0) or x != x or x in (float("inf"),):
        return False
    p = passo(ativo)
    return abs(x / p - round(x / p)) < 1e-6 and round(x / p) >= 1


def piso_qtd(ativo, q: float) -> int | float:
    """Maior quantidade permitida (múltipla do passo) que não passa de q."""
    p = passo(ativo)
    n = int((float(q) / p) + 1e-9)
    return int(n * p) if p >= 1 else round(n * p, 8)


def texto_qtd(ativo, q) -> str:
    """Quantidade para mostrar na tela: sem casas desnecessárias."""
    p = passo(ativo)
    if p >= 1:
        return f"{int(round(float(q))):,}".replace(",", ".")
    casas = 4 if p <= 0.0001 else 2
    s = f"{float(q):.{casas}f}".rstrip("0").rstrip(".")
    return s.replace(".", ",") or "0"


# ------------------------------------------------------------------ montagem de identificadores
def id_cripto(simbolo: str) -> str:
    return "CRIPTO:" + re.sub(r"[^A-Z0-9]", "", str(simbolo).upper())


def id_fundo(cnpj: str) -> str:
    return "FUNDO:" + re.sub(r"\D", "", str(cnpj))


def id_us(simbolo: str) -> str:
    return "US:" + re.sub(r"[^A-Z]", "", str(simbolo).upper())


def id_td(tipo_csv: str, vencimento) -> str | None:
    """'Tesouro Selic' + data de vencimento → 'TD:SELIC-20310301' (None se for um título com cupom ou desconhecido)."""
    t = TD_NOME_CSV.get(str(tipo_csv or "").strip().lower())
    if not t:
        return None
    try:
        d = vencimento.strftime("%Y%m%d")
    except Exception:
        d = re.sub(r"\D", "", str(vencimento))[:8]
        if len(d) != 8:
            return None
    return f"TD:{t}-{d}"


def partes_td(ativo: str) -> tuple[str, str] | None:
    """('Tesouro Selic', '2031-03-01') de um id TD."""
    m = _TD.fullmatch(str(ativo or ""))
    if not m:
        return None
    return TD_TIPOS[m.group(1)], f"{m.group(2)}-{m.group(3)}-{m.group(4)}"


def simbolo_yahoo(ativo: str) -> str | None:
    """Símbolo no Yahoo Finance de ativos que o Yahoo cota (B3 com .SA; ETFs americanos como estão). None para os demais."""
    a = str(ativo or "")
    if _B3.fullmatch(a):
        return a + ".SA"
    if _US.fullmatch(a):
        return a[3:]
    return None


# ------------------------------------------------------------------ nomes e setores
def rotulo(ativo) -> str:
    """Texto dos seletores e tabelas: 'Bitcoin · BTC', 'Tesouro Selic 2031', 'Petrobras · PETR4'."""
    a = str(ativo or "")
    if _CRIPTO.fullmatch(a):
        s = a[7:]
        return f"{NOMES_CRIPTO.get(s, s)} · {s}"
    if _US.fullmatch(a):
        s = a[3:]
        return f"{NOMES_EUA.get(s, 'ETF dos EUA')} · {s}"
    if _FUNDO.fullmatch(a):
        c = a[6:]
        return f"Fundo {c[:2]}.{c[2:5]}.{c[5:8]}/{c[8:12]}-{c[12:]}"
    if a == RF_CDI:
        return "Renda fixa 100% do CDI"
    p = partes_td(a)
    if p:
        return f"{p[0]} {p[1][:4]}"
    try:
        import recursos
        return recursos.rotulo(a)
    except Exception:
        return a


def setor(ativo) -> str | None:
    """Setor da empresa (só ações do catálogo). Os demais devolvem None."""
    if classe(ativo) != "acao":
        return None
    try:
        import recursos
        e = recursos.info(str(ativo))
        return e["setor"] if e else None
    except Exception:
        return None


# ------------------------------------------------------------------ universo
def universo_fixo() -> list[str]:
    """Tudo que o fechamento diário sempre tenta cotar, além do catálogo de ações: FIIs e ETFs líquidos, ETFs dos EUA, cripto e CDI.
    (Títulos do Tesouro vêm do arquivo do Tesouro e fundos entram quando alguém compra: ver competicao_job.)"""
    return (list(FIIS_LIQUIDOS) + list(ETFS_B3) + [id_us(s) for s in ETFS_EUA] + [id_cripto(s) for s in CRIPTOS] + [RF_CDI])


def agrupar_por_classe(ativos) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {c: [] for c in ORDEM}
    for a in ativos:
        c = classe(a)
        if c:
            out[c].append(a)
    return out


def peso_por_classe(pos: dict, ult: dict, caixa: float) -> tuple[dict, float]:
    """({classe: valor em R$}, patrimônio). A chave 'caixa' guarda o dinheiro parado."""
    vals: dict[str, float] = {}
    for tk, p in (pos or {}).items():
        c = classe(tk)
        if not c:
            continue
        px = (ult or {}).get(tk) or p.get("pm") or 0.0
        vals[c] = vals.get(c, 0.0) + p["q"] * px
    cx = max(0.0, float(caixa or 0.0))
    if cx:
        vals["caixa"] = cx
    return vals, sum(vals.values())
