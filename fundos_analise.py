"""
Motor de análise de ETFs e fundos de investimento (PURO: sem Streamlit e sem rede; recebe séries e dicionários).

Regras de honestidade (as mesmas do restante do app):
  - dado que a fonte não entrega fica None / "sem fonte": nada é inventado nem preenchido com zero;
  - rentabilidade passada não é expectativa de retorno futuro;
  - benchmark só entra quando é o índice correto do fundo; sem série gratuita, a métrica fica "n/d";
  - risco "baixo" NÃO significa seguro; as notas são educacionais e explicam de onde vêm.

Séries são pandas.Series com índice de datas (cota do fundo, preço do ETF, índice de referência).
"""
from __future__ import annotations

import math
import re
from datetime import date

import pandas as pd

import crescimento as cr

AVISO_PASSADO = "Rentabilidade passada não garante resultado futuro."
DIAS_ANO = 252


# =============================================================================== utilidades
def _ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _tem(texto: str, termos) -> bool:
    """Palavra inteira (aceita plural): 'bond' não casa com 'bondade', nem 'ouro' com 'touro'."""
    return any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?:s|es)?(?![a-z0-9])", texto) for t in termos)


def _br(txt: str) -> str:
    """Vírgula decimal: troca o ponto entre dígitos ('12.3%' → '12,3%'), sem mexer em pontos finais de frase."""
    return re.sub(r"(?<=\d)\.(?=\d)", ",", txt)


def _norm(txt) -> str:
    import unicodedata
    s = unicodedata.normalize("NFKD", str(txt or "")).encode("ascii", "ignore").decode()
    return s.lower()


def serie(s) -> pd.Series:
    """Série numérica positiva, ordenada, sem fuso e sem datas repetidas (usa a mesma limpeza do CAGR)."""
    x = cr.serie_limpa(s)
    return x[x > 0] if len(x) else x


def retornos(s: pd.Series) -> pd.Series:
    s = serie(s)
    return s.pct_change().dropna() if len(s) > 1 else pd.Series(dtype=float)


def _por_ano(s: pd.Series) -> float:
    """Observações por ano da própria série (ETF de pregão ≈ 252; cota de fundo ≈ 252; cripto 365)."""
    if len(s) < 3:
        return float(DIAS_ANO)
    dias = (s.index[-1] - s.index[0]).days
    return len(s) / (dias / 365.25) if dias > 0 else float(DIAS_ANO)


def _ponto_antes(s: pd.Series, alvo: pd.Timestamp, tol_dias: int = 10):
    """Último ponto em ou antes de `alvo` (até `tol_dias` antes). None se a série não começa a tempo."""
    ate = s[s.index <= alvo]
    if ate.empty or (alvo - ate.index[-1]).days > tol_dias:
        return None
    return ate.index[-1], float(ate.iloc[-1])


# =============================================================================== classificação de ETFs
ROTULOS_ETF = {
    "indice_amplo": "ETF de índice amplo", "acoes": "ETF de ações", "renda_fixa": "ETF de renda fixa",
    "internacional": "ETF internacional", "setorial": "ETF setorial", "commodities": "ETF de commodities",
    "cripto": "ETF de criptomoedas", "dividendos": "ETF de dividendos", "fatores": "ETF de fatores",
    "imobiliario": "ETF imobiliário",
}
# Lista curada (código → rótulos, índice de referência e como obter a série do índice). Não é exaustiva: o que não está
# aqui é classificado pelo nome e pela categoria do Yahoo, e o índice de referência fica "sem fonte".
#   indice: símbolo do Yahoo (índice de PREÇO); em_reais: o índice é em dólar e o ETF negocia em reais (converte).
ETFS_CURADOS = {
    "BOVA11": {"r": ["indice_amplo", "acoes"], "idx": "Ibovespa", "yh": "^BVSP"},
    "BOVV11": {"r": ["indice_amplo", "acoes"], "idx": "Ibovespa", "yh": "^BVSP"},
    "PIBB11": {"r": ["indice_amplo", "acoes"], "idx": "IBrX-50"},
    "BOVX11": {"r": ["indice_amplo", "acoes"], "idx": "Ibovespa"},
    "SMAL11": {"r": ["acoes"], "idx": "Índice Small Cap (SMLL)"},
    "DIVO11": {"r": ["acoes", "dividendos"], "idx": "Índice Dividendos (IDIV)"},
    "FIND11": {"r": ["acoes", "setorial"], "idx": "Índice Financeiro (IFNC)"},
    "MATB11": {"r": ["acoes", "setorial"], "idx": "Índice Materiais Básicos (IMAT)"},
    "ECOO11": {"r": ["acoes", "fatores"], "idx": "Índice Carbono Eficiente (ICO2)"},
    "ISUS11": {"r": ["acoes", "fatores"], "idx": "Índice de Sustentabilidade (ISE)"},
    "IVVB11": {"r": ["internacional", "indice_amplo", "acoes"], "idx": "S&P 500", "yh": "^GSPC", "em_reais": True},
    "SPXI11": {"r": ["internacional", "indice_amplo", "acoes"], "idx": "S&P 500", "yh": "^GSPC", "em_reais": True},
    "NASD11": {"r": ["internacional", "acoes"], "idx": "Nasdaq-100", "yh": "^NDX", "em_reais": True},
    "TECK11": {"r": ["internacional", "setorial", "acoes"], "idx": "Global Technology"},
    "XINA11": {"r": ["internacional", "acoes"], "idx": "MSCI China"},
    "GOLD11": {"r": ["commodities"], "idx": "Ouro"},
    "HASH11": {"r": ["cripto"], "idx": "Nasdaq Crypto Index (NCI)"},
    "QBTC11": {"r": ["cripto"], "idx": "Bitcoin"},
    "ETHE11": {"r": ["cripto"], "idx": "Ether"},
    "IMAB11": {"r": ["renda_fixa"], "idx": "IMA-B (títulos públicos atrelados ao IPCA)"},
    "IRFM11": {"r": ["renda_fixa"], "idx": "IRF-M (títulos prefixados)"},
    "B5P211": {"r": ["renda_fixa"], "idx": "IMA-B 5 (IPCA, até 5 anos)"},
    "FIXA11": {"r": ["renda_fixa"], "idx": "IMA-B 5+"},
    "VOO": {"r": ["indice_amplo", "acoes"], "idx": "S&P 500", "yh": "^GSPC"},
    "SPY": {"r": ["indice_amplo", "acoes"], "idx": "S&P 500", "yh": "^GSPC"},
    "IVV": {"r": ["indice_amplo", "acoes"], "idx": "S&P 500", "yh": "^GSPC"},
    "QQQ": {"r": ["indice_amplo", "acoes"], "idx": "Nasdaq-100", "yh": "^NDX"},
    "DIA": {"r": ["indice_amplo", "acoes"], "idx": "Dow Jones Industrial", "yh": "^DJI"},
    "IWM": {"r": ["indice_amplo", "acoes"], "idx": "Russell 2000", "yh": "^RUT"},
    "VTI": {"r": ["indice_amplo", "acoes"], "idx": "CRSP US Total Market"},
    "VT": {"r": ["internacional", "indice_amplo", "acoes"], "idx": "FTSE Global All Cap"},
    "VEA": {"r": ["internacional", "acoes"], "idx": "FTSE Developed All Cap ex US"},
    "VWO": {"r": ["internacional", "acoes"], "idx": "FTSE Emerging Markets All Cap"},
    "SCHD": {"r": ["acoes", "dividendos"], "idx": "Dow Jones U.S. Dividend 100"},
    "VIG": {"r": ["acoes", "dividendos"], "idx": "S&P U.S. Dividend Growers"},
    "VYM": {"r": ["acoes", "dividendos"], "idx": "FTSE High Dividend Yield"},
    "JEPI": {"r": ["acoes", "dividendos"], "idx": "Sem índice (gestão ativa com opções)"},
    "MTUM": {"r": ["acoes", "fatores"], "idx": "MSCI USA Momentum"},
    "QUAL": {"r": ["acoes", "fatores"], "idx": "MSCI USA Sector Neutral Quality"},
    "USMV": {"r": ["acoes", "fatores"], "idx": "MSCI USA Minimum Volatility"},
    "XLK": {"r": ["acoes", "setorial"], "idx": "Technology Select Sector"},
    "XLF": {"r": ["acoes", "setorial"], "idx": "Financial Select Sector"},
    "XLE": {"r": ["acoes", "setorial"], "idx": "Energy Select Sector"},
    "SOXX": {"r": ["acoes", "setorial"], "idx": "NYSE Semiconductor"},
    "SMH": {"r": ["acoes", "setorial"], "idx": "MVIS US Listed Semiconductor 25"},
    "ARKK": {"r": ["acoes", "setorial"], "idx": "Sem índice (gestão ativa)"},
    "BND": {"r": ["renda_fixa"], "idx": "Bloomberg US Aggregate Float Adjusted"},
    "AGG": {"r": ["renda_fixa"], "idx": "Bloomberg US Aggregate"},
    "GLD": {"r": ["commodities"], "idx": "Ouro (LBMA)"},
    "SLV": {"r": ["commodities"], "idx": "Prata (LBMA)"},
    "VNQ": {"r": ["imobiliario", "acoes"], "idx": "MSCI US IMI Real Estate 25/50"},
}
_TERMOS_ETF = {
    "renda_fixa": ("bond", "treasury", "fixed income", "renda fixa", "ima-b", "imab", "irf-m", "debenture", "aggregate", "tips"),
    "commodities": ("gold", "ouro", "silver", "prata", "oil", "petroleo", "commodity", "commodities", "agro"),
    "cripto": ("bitcoin", "crypto", "cripto", "ether", "ethereum", "blockchain"),
    "dividendos": ("dividend", "dividendo", "dividendos", "high yield equity", "income equity"),
    "fatores": ("momentum", "quality", "low volatility", "minimum volatility", "value factor", "factor", "esg", "smart beta"),
    "imobiliario": ("real estate", "reit", "imobiliario"),
    "setorial": ("technology", "tecnologia", "financial", "financeiro", "health", "saude", "energy", "energia",
                 "semiconductor", "utilities", "consumer", "industrial", "materials", "materiais", "mineracao"),
    "internacional": ("global", "world", "international", "emerging", "europe", "china", "japan", "msci", "ex-us", "ex us"),
    "indice_amplo": ("s&p 500", "ibovespa", "total market", "nasdaq-100", "nasdaq 100", "large blend", "large cap", "ibrx"),
}


def classificar_etf(ticker: str, nome: str = "", categoria: str = "") -> list[dict]:
    """Rótulos do ETF (um ETF pode ter vários: ex.: S&P 500 no Brasil é internacional + índice amplo + ações).
    Lista curada primeiro; depois, palavras do nome e da categoria do Yahoo. Cada rótulo diz de onde veio."""
    tk = (ticker or "").upper().replace(".SA", "").strip()
    achados: dict[str, str] = {}
    cur = ETFS_CURADOS.get(tk)
    if cur:
        for r in cur["r"]:
            achados[r] = "lista curada do app"
    texto = _norm(f"{nome} | {categoria}")
    for r, termos in _TERMOS_ETF.items():
        if not cur and r not in achados and _tem(texto, termos):       # ETF da lista curada: só os rótulos curados (sem contradição)
            achados[r] = "palavras do nome/categoria na fonte"
    if achados and not (set(achados) & {"renda_fixa", "commodities", "cripto", "imobiliario", "acoes"}):
        if set(achados) & {"indice_amplo", "dividendos", "fatores", "setorial", "internacional"}:
            achados["acoes"] = "inferido: índice/estratégia de ações"
    ordem = list(ROTULOS_ETF)
    return [{"chave": k, "rotulo": ROTULOS_ETF[k], "motivo": achados[k]} for k in ordem if k in achados]


def indice_de_referencia(ticker: str) -> dict:
    """Índice de referência conhecido (nome e símbolo Yahoo da série, se houver). Sem lista: sem fonte."""
    tk = (ticker or "").upper().replace(".SA", "").strip()
    c = ETFS_CURADOS.get(tk)
    if not c:
        return {"nome": None, "yahoo": None, "em_reais": False, "fonte": "sem fonte (ETF fora da lista curada)"}
    return {"nome": c.get("idx"), "yahoo": c.get("yh"), "em_reais": bool(c.get("em_reais")),
            "fonte": "lista curada do app (confira no regulamento do ETF)"}


def politica_distribuicao(dividendos, hoje: date | None = None) -> dict:
    """Distribuição × acumulação, pelo que o Yahoo MOSTRA: houve proventos nos últimos 12 meses? Sem proventos observados
    não prova acumulação (o dado pode faltar): o texto diz isso."""
    hoje = hoje or date.today()
    d = serie_proventos(dividendos)
    if d.empty:
        return {"tipo": "sem_proventos", "rotulo": "Sem proventos observados (possível acumulação)", "n_12m": 0,
                "total_12m": None, "nota": "A fonte não mostra proventos. Pode ser ETF de acumulação (reinveste) ou falta de "
                                           "dado: confira o regulamento."}
    ini = pd.Timestamp(hoje) - pd.DateOffset(years=1)
    ult = d[d.index > ini]
    if ult.empty:
        return {"tipo": "sem_proventos", "rotulo": "Sem proventos nos últimos 12 meses", "n_12m": 0, "total_12m": None,
                "nota": "Houve proventos no passado, mas nenhum nos últimos 12 meses."}
    return {"tipo": "distribuicao", "rotulo": "Distribui rendimentos", "n_12m": int(len(ult)), "total_12m": float(ult.sum()),
            "nota": f"{len(ult)} pagamento(s) nos últimos 12 meses."}


def serie_proventos(d) -> pd.Series:
    if d is None:
        return pd.Series(dtype=float)
    s = cr.serie_limpa(d)
    return s[s > 0] if len(s) else s


# =============================================================================== classificação de fundos (CVM)
ROTULOS_FUNDO = {
    "renda_fixa": "Fundo de renda fixa", "acoes": "Fundo de ações", "multimercado": "Fundo multimercado",
    "cambial": "Fundo cambial", "imobiliario": "Fundo imobiliário", "previdencia": "Fundo de previdência",
    "cotas": "Fundo de cotas (FIC)", "etf": "ETF (fundo de índice)", "credito_privado": "Crédito privado",
    "referenciado_di": "Referenciado DI", "indexado": "Indexado/índice", "exclusivo": "Fundo exclusivo/restrito",
}


def classificar_fundo(cad: dict | None) -> list[dict]:
    """Rótulos do fundo pelo cadastro da CVM (classe, classificação ANBIMA, nome e condições). Vários rótulos possíveis."""
    cad = cad or {}
    classe = _norm(cad.get("classe"))
    anbima = _norm(cad.get("classe_anbima"))
    nome = _norm(cad.get("nome"))
    achados: dict[str, str] = {}

    def add(k, m):
        achados.setdefault(k, m)
    base = f"{classe} | {anbima}"
    if _tem(base, ("renda fixa",)) or "referenciado" in base or "duration" in base:
        add("renda_fixa", "classe CVM/ANBIMA")
    if _tem(base, ("acoes", "acao")):
        add("acoes", "classe CVM/ANBIMA")
    if _tem(base, ("multimercado", "multimercados")):
        add("multimercado", "classe CVM/ANBIMA")
    if _tem(base, ("cambial",)):
        add("cambial", "classe CVM/ANBIMA")
    if "previd" in base or "previd" in nome:
        add("previdencia", "classe/nome")
    if "referenciado di" in base or _tem(nome, ("referenciado di", "ref di", "di")) and "renda fixa" in base:
        add("referenciado_di", "classe/nome")
    if _tem(nome, ("fii", "imobiliario", "imobiliarios")) or "imobili" in base:
        add("imobiliario", "classe/nome")
    if _tem(nome, ("fic", "fif", "fundo de cotas", "fundo de investimento em cotas")) or "cotas" in classe:
        add("cotas", "nome/classe (investe em outros fundos)")
    if _tem(nome, ("etf", "indice", "index")) or "indexado" in base:
        add("indexado", "nome/classe")
    if _tem(nome, ("credito privado", "cred priv", "credito")):
        add("credito_privado", "nome")
    if _norm(cad.get("exclusivo")) in ("s", "sim") or _tem(nome, ("exclusivo", "exclusiva")):
        add("exclusivo", "cadastro")
    ordem = list(ROTULOS_FUNDO)
    return [{"chave": k, "rotulo": ROTULOS_FUNDO[k], "motivo": achados[k]} for k in ordem if k in achados]


def categoria_principal(rotulos: list[dict]) -> str:
    """Rótulo usado para agrupar comparações: o primeiro de uma ordem de especificidade."""
    chaves = [r["chave"] for r in rotulos]
    for k in ("referenciado_di", "renda_fixa", "cripto", "commodities", "imobiliario", "internacional", "setorial", "dividendos",
              "fatores", "indice_amplo", "acoes", "multimercado", "cambial", "previdencia", "credito_privado"):
        if k in chaves:
            return k
    return chaves[0] if chaves else "outros"


# =============================================================================== qualidade dos dados
MIN_PARADA = 15            # pregões seguidos com o MESMO preço = série parada (dado faltando na fonte), não mercado calmo
LIM_PONTO_FORA = 0.20      # salto diário acima disso, com preço de volta ao nível anterior no dia seguinte = ponto fora do padrão
MAX_EXCURSAO = 30          # pregões: sobe/desce de forma anormal e VOLTA ao nível de antes dentro desse prazo = excursão falsa
RAMPA = 3                  # a subida e a volta anormais acontecem em até 3 pregões cada
VERSAO = "10.4"
MULT_SIGMA = 10            # "anormal" = salto diário > 10x a oscilação diária típica da própria série (piso de 3%)
MIN_RESTANTE = 60          # depois do corte, o histórico precisa ter ao menos isso; senão a série é mantida, com aviso


def limpar_serie(s: pd.Series, excursoes: bool = False) -> tuple[pd.Series, dict]:
    """Detecta defeitos comuns de dados gratuitos: (1) pontos isolados que sobem/descem e voltam no dia seguinte;
    (1b) com excursoes=True (renda fixa): trechos de até 30 pregões que disparam e voltam rápido ao nível de antes;
    (2) trechos PARADOS (≥ 15 pregões com o mesmo preço), onde a fonte deixou de atualizar. Pontos fora do padrão são
    removidos; com trecho parado, a série começa DEPOIS do último trecho (nada é interpolado). Se sobrar menos de 60
    pontos, mantém a série original e só avisa. Devolve (série, info)."""
    x = serie(s)
    info = {"alterada": False, "removidos": [], "paradas": [], "inicio": None, "cortada": False, "aviso": None}
    if len(x) < 30:
        return x, info
    r = x.pct_change()
    ruins = []
    for i in range(1, len(x) - 1):
        if abs(r.iloc[i]) > LIM_PONTO_FORA and abs(x.iloc[i + 1] / x.iloc[i - 1] - 1) < 0.05:   # sobe/desce e volta ao nível de antes
            ruins.append(x.index[i])
    y = x.drop(ruins) if ruins else x
    # (1b) excursões de vários dias: o preço dispara (ou despenca) de forma anormal para a própria série em até 3 pregões,
    # fica lá um tempo e volta RÁPIDO ao nível de antes. Em renda fixa isso é erro de cotação da fonte, não mercado.
    ry0 = y.pct_change().dropna()
    nz = ry0[ry0 != 0].abs()
    sigma = float(nz.median()) * 1.4826 if len(nz) >= 20 else None
    if excursoes and sigma is not None:                     # só para séries de renda fixa (ações têm quedas e voltas reais)
        lim = max(0.03, MULT_SIGMA * sigma)
        idx, v, n0, extra, k = list(y.index), y.to_numpy(dtype=float), len(y), [], 1
        while k < n0 - 1:
            base, achou = v[k - 1], None
            for w in range(RAMPA):                          # a subida/descida anormal acontece em até 3 pregões
                if k + w < n0 and abs(v[k + w] / base - 1) > lim:
                    sinal = 1 if v[k + w] > base else -1
                    if all((v[m] / base - 1) * sinal > 0 for m in range(k, k + w + 1)):
                        achou = (w, sinal)
                    break
            if achou:
                w, sinal = achou
                fim = None
                for j in range(k + w + 1, min(k + MAX_EXCURSAO + 1, n0)):
                    d = (v[j] / base - 1) * sinal
                    if abs(v[j] / base - 1) < lim / 2:
                        fim = j
                        break
                    if d <= 0:                              # atravessou para o outro lado: não é excursão
                        break
                if fim is not None:
                    meio_ok = all((v[m] / base - 1) * sinal > lim / 2 for m in range(k + w, fim))
                    volta_rapida = any(abs(v[m] / base - 1) > lim for m in range(max(k + w, fim - RAMPA), fim))
                    if meio_ok and volta_rapida:
                        extra.extend(idx[k:fim])
                        k = fim
                        continue
            k += 1
        if extra:
            ruins = sorted(set(ruins) | set(extra))
            y = x.drop(ruins)
    info["removidos"] = ruins
    ry = y.pct_change().fillna(1.0)
    zero = (ry == 0).to_numpy()
    paradas, i, n = [], 0, len(y)
    while i < n:
        if zero[i]:
            j = i
            while j + 1 < n and zero[j + 1]:
                j += 1
            if j - i + 1 >= MIN_PARADA:
                paradas.append((i - 1, j))             # i-1 = último preço "bom" antes da parada
            i = j + 1
        else:
            i += 1
    info["paradas"] = [(y.index[max(a, 0)], y.index[b]) for a, b in paradas]
    if paradas:
        corte = paradas[-1][1] + 1                      # primeiro preço novo depois da última parada
        if corte < n and n - corte >= MIN_RESTANTE:
            y = y.iloc[corte:]
            info["cortada"], info["inicio"] = True, y.index[0]
    info["alterada"] = bool(ruins or paradas)
    if info["alterada"]:
        partes = []
        if paradas:
            d = sum(b - a for a, b in paradas)
            partes.append(f"preço parado por {d} pregões ({_d(info['paradas'][0][0])} a {_d(info['paradas'][-1][1])})")
        if ruins:
            partes.append(f"{len(ruins)} pregão(ões) com preço fora do padrão (subida ou queda anormal que desfez logo depois) removido(s)")
        info["aviso"] = ("Dados suspeitos na fonte: " + " e ".join(partes) + ". "
                         + (f"Usei só o histórico a partir de {_d(info['inicio'])}." if info["cortada"] else
                            "O histórico restante é curto demais para cortar: os números abaixo podem estar distorcidos."
                            if paradas else "Esses pregões ficaram de fora dos cálculos; nada foi inventado no lugar."))
    return y, info


def _d(ts) -> str:
    return pd.Timestamp(ts).strftime("%d/%m/%Y")


# =============================================================================== rentabilidade
JANELAS_MESES = {"1 mês": 1, "3 meses": 3, "6 meses": 6, "12 meses": 12, "36 meses": 36, "60 meses": 60}


def rentabilidade(s: pd.Series) -> dict:
    """Retorno acumulado por janela (datas reais, tolerância de 10 dias), no ano (YTD), no mês e desde o início;
    CAGR de 1, 3 e 5 anos. Sem ponto de partida a tempo, a janela fica None (nada é estimado)."""
    s = serie(s)
    out = {"ok": False, "janelas": {}, "cagr": {}, "ytd": None, "mes": None, "dia": None, "inicio": None, "fim": None,
           "acumulado": None, "anos": None}
    if len(s) < 2:
        return out
    fim_d, fim_v = s.index[-1], float(s.iloc[-1])
    out.update(ok=True, inicio=s.index[0], fim=fim_d, acumulado=fim_v / float(s.iloc[0]) - 1,
               anos=(fim_d - s.index[0]).days / 365.25, dia=fim_v / float(s.iloc[-2]) - 1)
    for rot, m in JANELAS_MESES.items():
        p = _ponto_antes(s.iloc[:-1], fim_d - pd.DateOffset(months=m))
        out["janelas"][rot] = None if p is None else fim_v / p[1] - 1
    p_ano = _ponto_antes(s.iloc[:-1], pd.Timestamp(year=fim_d.year - 1, month=12, day=31), tol_dias=10)
    out["ytd"] = None if p_ano is None else fim_v / p_ano[1] - 1
    p_mes = _ponto_antes(s.iloc[:-1], fim_d.replace(day=1) - pd.Timedelta(days=1), tol_dias=10)
    out["mes"] = None if p_mes is None else fim_v / p_mes[1] - 1
    for n, c in cr.cagr_periodos(s, (1, 3, 5), tol_dias=10).items():
        out["cagr"][n] = c.valor if c.ok else None
    return out


def retornos_calendario(s: pd.Series) -> dict:
    """Retornos por mês e por ano-calendário. O primeiro período só existe se a série começar no fechamento anterior:
    períodos parciais são marcados (parcial=True) e não entram nas estatísticas de consistência."""
    s = serie(s)
    if len(s) < 2:
        return {"mensal": pd.Series(dtype=float), "anual": pd.DataFrame(columns=["retorno", "parcial"])}
    mes = s.resample("ME").last()
    mensal = mes.pct_change().dropna()
    ano = s.resample("YE").last()
    anual = []
    for i, (d, v) in enumerate(ano.items()):
        if i == 0:
            ini = float(s.iloc[0])
            parcial = s.index[0] > pd.Timestamp(year=d.year, month=1, day=10)
        else:
            ini, parcial = float(ano.iloc[i - 1]), False
        if d.year == s.index[-1].year and s.index[-1] < pd.Timestamp(year=d.year, month=12, day=20):
            parcial = True
        anual.append({"ano": d.year, "retorno": float(v) / ini - 1, "parcial": parcial})
    return {"mensal": mensal, "anual": pd.DataFrame(anual).set_index("ano") if anual else
            pd.DataFrame(columns=["retorno", "parcial"])}


def retorno_real(s: pd.Series, ipca_idx: pd.Series, anos: int = 3) -> dict:
    """Retorno acumulado e ganho real (Fisher) na mesma janela do IPCA. Sem IPCA cobrindo a janela: motivo, sem número."""
    x = cr.contra_benchmarks(s, pd.Series(dtype=float), ipca_idx, anos)
    if not x["ok"]:
        return {"ok": False, "motivo": x["motivo"], "anos": anos}
    if x["ipca"] is None:
        return {"ok": False, "motivo": "IPCA não cobre a janela do fundo", "anos": anos}
    return {"ok": True, "anos": anos, "nominal": x["ativo"], "ipca": x["ipca"], "real": x["real"],
            "real_anual": x["real_anual"], "inicio": x["inicio"], "fim": x["fim"]}


def contra_referencia(s: pd.Series, ref_idx: pd.Series, anos: int = 3, nome: str = "referência") -> dict:
    """Retorno do ativo contra um índice (CDI, IPCA, Ibovespa...) na MESMA janela, com % da referência e diferença."""
    a = cr.retorno_no_periodo(s, anos)
    if not a["ok"]:
        return {"ok": False, "motivo": cr.MENSAGENS.get(a["status"], "indisponível"), "anos": anos, "nome": nome}
    r = serie(ref_idx)
    ini, fim = pd.Timestamp(a["inicio"]), pd.Timestamp(a["fim"])
    if r.empty or r.index[0] > ini + pd.Timedelta(days=10) or r.index[-1] < fim - pd.Timedelta(days=45):
        return {"ok": False, "motivo": f"série de {nome} não cobre a janela", "anos": anos, "nome": nome}
    ref = float(r.asof(fim) / r.asof(ini) - 1)
    nom = a["acumulado"]
    return {"ok": True, "anos": anos, "nome": nome, "ativo": nom, "ref": ref, "dif_pp": (nom - ref) * 100,
            "pct_ref": (nom / ref * 100) if ref > 0 else None, "inicio": a["inicio"], "fim": a["fim"]}


# =============================================================================== risco
def drawdown(s: pd.Series) -> dict:
    s = serie(s)
    if len(s) < 2:
        return {"max": None, "pico": None, "fundo": None, "recuperado": None, "atual": None}
    pico = s.cummax()
    dd = s / pico - 1
    fundo = dd.idxmin()
    p = s.loc[:fundo].idxmax()
    depois = s.loc[fundo:]
    rec = depois[depois >= float(s.loc[p])]
    return {"max": float(dd.min()), "pico": p, "fundo": fundo, "recuperado": None if rec.empty else rec.index[0],
            "atual": float(dd.iloc[-1])}


def _alinhar(a: pd.Series, b: pd.Series, freq: str = "D") -> pd.DataFrame:
    """Retornos de duas séries nas mesmas datas. freq 'W' usa fechamentos semanais (mercados com horários diferentes)."""
    a, b = serie(a), serie(b)
    if a.empty or b.empty:
        return pd.DataFrame()
    if freq == "W":
        a, b = a.resample("W-FRI").last().dropna(), b.resample("W-FRI").last().dropna()
        df = pd.concat([a, b], axis=1, join="inner")
    else:
        b2 = b.reindex(a.index.union(b.index)).ffill(limit=3).reindex(a.index)
        df = pd.concat([a, b2], axis=1).dropna()
    df.columns = ["a", "b"]
    return df.pct_change().dropna()


def retorno_diario_do_indice(idx: pd.Series, datas) -> pd.Series:
    """Retorno do índice acumulado (CDI/IPCA) entre datas consecutivas da série do ativo (composto, sem buracos)."""
    i = serie(idx)
    if i.empty or len(datas) < 2:
        return pd.Series(dtype=float)
    v = i.reindex(i.index.union(datas)).ffill().reindex(datas)
    return v.pct_change().dropna()


def risco(s: pd.Series, ref: pd.Series | None = None, rf_idx: pd.Series | None = None, freq_ref: str = "D") -> dict:
    """Volatilidade, drawdown, Sharpe, Sortino e, com índice de referência, beta, correlação e tracking error/difference.
    Sharpe e Sortino só existem com taxa livre de risco real (rf_idx = índice acumulado do CDI, por exemplo): sem ela,
    ficam None (não se assume taxa zero). Poucas observações = None."""
    s = serie(s)
    out = {"ok": False, "vol": None, "dd": drawdown(s), "sharpe": None, "sortino": None, "beta": None, "corr": None,
           "te": None, "td": None, "td_anual": None, "n": int(len(s)), "motivos": {}}
    r = retornos(s)
    if len(r) < 30:
        out["motivos"]["geral"] = "menos de 30 retornos: indicadores de risco não calculados"
        return out
    k = _por_ano(s)
    out["ok"] = True
    out["vol"] = float(r.std() * math.sqrt(k))
    if rf_idx is not None and len(serie(rf_idx)):
        rf = retorno_diario_do_indice(rf_idx, list(s.index))
        j = pd.concat([r, rf], axis=1, join="inner").dropna()
        j.columns = ["r", "rf"]
        if len(j) >= 30 and j["r"].std() > 0:
            ex = j["r"] - j["rf"]
            out["sharpe"] = float(ex.mean() * k / (j["r"].std() * math.sqrt(k)))
            down = ex.clip(upper=0)
            dd = math.sqrt(float((down ** 2).mean())) * math.sqrt(k)
            out["sortino"] = float(ex.mean() * k / dd) if dd > 0 else None
            if dd == 0:
                out["motivos"]["sortino"] = "sem retornos abaixo da taxa livre de risco no período"
        else:
            out["motivos"]["sharpe"] = "taxa livre de risco não cobre o período"
    else:
        out["motivos"]["sharpe"] = "sem taxa livre de risco: Sharpe e Sortino não calculados"
    if ref is not None and len(serie(ref)):
        j = _alinhar(s, ref, freq_ref)
        if len(j) >= 30 and j["b"].var() > 0:
            kk = 52.0 if freq_ref == "W" else k
            out["beta"] = float(j["a"].cov(j["b"]) / j["b"].var())
            out["corr"] = float(j["a"].corr(j["b"]))
            ativo = j["a"] - j["b"]
            out["te"] = float(ativo.std() * math.sqrt(kk))
            acum_a, acum_b = float((1 + j["a"]).prod() - 1), float((1 + j["b"]).prod() - 1)
            anos = (j.index[-1] - j.index[0]).days / 365.25
            out["td"] = acum_a - acum_b
            out["td_anual"] = ((1 + acum_a) / (1 + acum_b)) ** (1 / anos) - 1 if anos >= 1 and acum_b > -1 else None
            out["janela_ref"] = (j.index[0], j.index[-1])
        else:
            out["motivos"]["ref"] = "poucos pontos em comum com o índice de referência"
    else:
        out["motivos"]["ref"] = "sem série do índice de referência: beta, correlação e tracking não calculados"
    return out


def consistencia(s: pd.Series, ref_idx: pd.Series | None = None) -> dict:
    """Meses positivos, meses acima da referência e janelas móveis de 12 meses (pior/melhor). Sem 12 meses, None."""
    cal = retornos_calendario(s)
    m = cal["mensal"]
    out = {"n_meses": int(len(m)), "meses_positivos": None, "meses_acima_ref": None, "pior_12m": None, "melhor_12m": None,
           "janelas_12m": 0, "pct_12m_positivas": None}
    if len(m) >= 6:
        out["meses_positivos"] = float((m > 0).mean())
    sm = serie(s).resample("ME").last()
    if len(sm) >= 13:
        j12 = (sm / sm.shift(12) - 1).dropna()
        out.update(pior_12m=float(j12.min()), melhor_12m=float(j12.max()), janelas_12m=int(len(j12)),
                   pct_12m_positivas=float((j12 > 0).mean()))
    if ref_idx is not None and len(serie(ref_idx)) and len(m) >= 6:
        rm = serie(ref_idx).resample("ME").last().pct_change().dropna()
        j = pd.concat([m, rm], axis=1, join="inner").dropna()
        if len(j) >= 6:
            out["meses_acima_ref"] = float((j.iloc[:, 0] > j.iloc[:, 1]).mean())
    return out


# =============================================================================== liquidez, porte e custos
def liquidez_financeira(preco: pd.Series, volume: pd.Series, dias: int = 90) -> float | None:
    """Média de preço × volume nos últimos `dias` dias corridos. Sem volume: None (fundos abertos não negociam em bolsa)."""
    p, v = serie(preco), cr.serie_limpa(volume)
    if p.empty or v.empty:
        return None
    j = pd.concat([p, v], axis=1, join="inner").dropna()
    j = j[j.index >= j.index[-1] - pd.Timedelta(days=dias)]
    if len(j) < 10:
        return None
    x = (j.iloc[:, 0] * j.iloc[:, 1])
    return float(x.mean())


def faixa_liquidez_etf(fin_diaria_brl_ou_usd: float | None, moeda: str = "BRL") -> tuple[str, str]:
    """(classe, texto) pela média diária negociada. Limites educacionais por moeda."""
    if fin_diaria_brl_ou_usd is None:
        return "na", "sem dado de volume"
    v = fin_diaria_brl_ou_usd
    lim = (5e6, 1e6) if moeda == "USD" else (2e6, 3e5)
    if v >= lim[0]:
        return "good", "liquidez alta"
    if v >= lim[1]:
        return "fair", "liquidez média"
    return "bad", "liquidez baixa: o spread pode custar caro"


def custo_acumulado(taxa_aa_pct: float | None, anos: int) -> float | None:
    """Quanto da rentabilidade bruta a taxa consome em `anos`: 1 − (1 − t)^anos (em fração do patrimônio)."""
    if not _ok(taxa_aa_pct) or taxa_aa_pct < 0 or anos <= 0:
        return None
    return 1 - (1 - taxa_aa_pct / 100) ** anos


def retorno_bruto_aprox(retorno_liquido_aa: float | None, taxa_aa_pct: float | None) -> float | None:
    """Aproximação: o preço do ETF/cota já é LÍQUIDO da taxa. Bruto ≈ (1 + líquido) ÷ (1 − taxa) − 1. Não inclui custos
    de negociação nem impostos."""
    if not (_ok(retorno_liquido_aa) and _ok(taxa_aa_pct)) or taxa_aa_pct >= 100:
        return None
    return (1 + retorno_liquido_aa) / (1 - taxa_aa_pct / 100) - 1


def faixa_taxa(taxa_aa_pct: float | None, categoria: str) -> tuple[str, str]:
    """Taxa de administração contra faixas educacionais por categoria (não é recomendação)."""
    if not _ok(taxa_aa_pct):
        return "na", "sem dado de taxa"
    lim = {"indice_amplo": (0.30, 0.70), "acoes": (0.50, 1.50), "renda_fixa": (0.30, 1.00),
           "referenciado_di": (0.30, 1.00), "multimercado": (1.00, 2.00), "cambial": (0.50, 1.50)}.get(
        categoria, (0.50, 1.50))
    if taxa_aa_pct <= lim[0]:
        return "good", _br(f"baixa para a categoria (até {lim[0]:.2f}% a.a.)")
    if taxa_aa_pct <= lim[1]:
        return "fair", _br(f"intermediária ({lim[0]:.2f}% a {lim[1]:.2f}% a.a.)")
    return "bad", _br(f"alta para a categoria (acima de {lim[1]:.2f}% a.a.)")


# =============================================================================== composição, concentração e sobreposição
def pesos_pct(itens) -> pd.Series:
    """{ativo: peso} ou Series em % do patrimônio. Descarta ausentes/negativos. Só reduz a escala se a soma passar de
    100,5% (dado inconsistente); composições PARCIAIS (ex.: 10 maiores posições) ficam com o peso real, sem inflar."""
    if itens is None:
        return pd.Series(dtype=float)
    s = pd.Series(itens, dtype=float).dropna()
    s = s[s > 0]
    if len(s) and s.sum() > 100.5:
        s = s / s.sum() * 100
    return s


pesos_normalizados = pesos_pct          # nome antigo mantido (usado por outros módulos e testes)


def concentracao(pesos) -> dict:
    """Top 1/3/5/10 (% do patrimônio), HHI e número efetivo de ativos (1/HHI). Se só parte da carteira foi divulgada
    (soma < 95%), `parcial` = True, `cobertura` = soma, e HHI/número efetivo não são calculados (seriam enganosos)."""
    p = pesos_pct(pesos).sort_values(ascending=False)
    if p.empty:
        return {"ok": False}
    cob = float(p.sum())
    parcial = cob < 95.0
    out = {"ok": True, "n": int(len(p)), "top1": float(p.iloc[0]), "top3": float(p.iloc[:3].sum()),
           "top5": float(p.iloc[:5].sum()), "top10": float(p.iloc[:10].sum()), "parcial": parcial, "cobertura": cob,
           "hhi": None, "n_efetivo": None}
    if not parcial:
        f = p / p.sum()
        hhi = float((f ** 2).sum())
        out["hhi"], out["n_efetivo"] = hhi, (1 / hhi if hhi > 0 else None)
    return out


def qualidade_diversificacao(c: dict) -> tuple[str, str, str]:
    """(classe, rótulo, texto). Carteira completa: pelo número EFETIVO de ativos e maior peso. Só as maiores posições
    (parcial): pelo peso das 10 maiores e da maior, dizendo a cobertura. Nunca pela quantidade de linhas."""
    if not c.get("ok"):
        return "na", "Sem dados", "A composição não foi divulgada pela fonte."
    t1 = c["top1"]
    if c.get("parcial"):
        t10 = c["top10"]
        base = _br(f"As {min(c['n'], 10)} maiores posições somam {t10:.0f}% do patrimônio (maior: {t1:.1f}%); "
                f"a fonte só divulga {c['cobertura']:.0f}% da carteira.")
        if t10 <= 40 and t1 < 10:
            return "good", "Diversificação alta (pelas maiores posições)", base
        if t10 <= 65 and t1 < 25:
            return "fair", "Diversificação média (pelas maiores posições)", base
        return "bad", "Diversificação baixa (pelas maiores posições)", base
    ne = c["n_efetivo"]
    txt = _br(f"≈ {0 if ne is None else ne:.0f} ativos efetivos; maior posição {t1:.1f}%.")
    if ne is not None and ne >= 30 and t1 < 10:
        return "good", "Diversificação alta", txt
    if ne is not None and ne >= 10 and t1 < 25:
        return "fair", "Diversificação média", txt
    return "bad", "Diversificação baixa", txt


def sobreposicao(a, b) -> dict:
    """Sobreposição entre duas composições: soma dos MENORES pesos (% do patrimônio) nos ativos em comum. Com composição
    parcial é um MÍNIMO (o real pode ser maior); `parcial` avisa."""
    pa, pb = pesos_pct(a), pesos_pct(b)
    if pa.empty or pb.empty:
        return {"ok": False, "motivo": "composição não divulgada em um dos dois"}
    comum = pa.index.intersection(pb.index)
    v = float(sum(min(pa[k], pb[k]) for k in comum))
    return {"ok": True, "valor": v, "comuns": sorted(comum, key=lambda k: -min(pa[k], pb[k])), "n_comuns": int(len(comum)),
            "parcial": bool(pa.sum() < 95 or pb.sum() < 95)}


def exposicao_total(posicoes: list[dict]) -> dict:
    """Olha através dos fundos/ETFs: cada posição = {"nome", "valor" (R$), "pesos" {ativo: % do patrimônio} ou None}. Devolve o
    peso de cada ativo subjacente na carteira e a parcela do valor SEM composição conhecida (nunca distribuída por palpite)."""
    total = sum(p["valor"] for p in posicoes if _ok(p.get("valor")) and p["valor"] > 0)
    if total <= 0:
        return {"ok": False}
    expo: dict[str, float] = {}
    sem = 0.0
    for p in posicoes:
        v = p.get("valor")
        if not (_ok(v) and v > 0):
            continue
        w = pesos_pct(p.get("pesos"))
        if w.empty:
            sem += v
            continue
        for k, pct in w.items():
            expo[k] = expo.get(k, 0.0) + v * pct / 100
        sem += v * max(0.0, 1 - float(w.sum()) / 100)
    s = pd.Series(expo, dtype=float).sort_values(ascending=False)
    return {"ok": True, "total": total, "sem_composicao_pct": sem / total * 100, "ativos": (s / total * 100)}


def correlacao_carteira(series: dict[str, pd.Series], freq: str = "W") -> pd.DataFrame:
    """Matriz de correlação dos retornos (semanais por padrão, para alinhar bolsas e fundos). Mínimo de 20 observações."""
    cols = {}
    for k, s in series.items():
        s = serie(s)
        if len(s) > 20:
            cols[k] = (s.resample("W-FRI").last() if freq == "W" else s).pct_change()
    if len(cols) < 2:
        return pd.DataFrame()
    df = pd.concat(cols, axis=1, join="inner").dropna()
    return df.corr() if len(df) >= 20 else pd.DataFrame()


# =============================================================================== monitoramento e relatório
LIM_QUEDA_PL = -20.0          # queda do patrimônio em 12 meses (%) que merece atenção
LIM_RESGATE_LIQ = 0.0         # captação líquida negativa em 12 meses
LIM_DD = -20.0                # drawdown atual (%)
LIM_TE = 0.03                 # tracking error anual acima de 3% (índice amplo) merece atenção
LIM_TOP1 = 25.0               # uma posição acima disso (%) = concentração
LIM_TAXA_ALTA = 2.0


def monitorar(ctx: dict) -> list[dict]:
    """Alertas só sobre o que dá para VERIFICAR nos dados. Chaves de ctx (todas opcionais): pl_var12m (fração), captacao_12m,
    cotistas_var12m (fração), dd_atual (fração), vol, te, top1, taxa_adm (%), taxa_perf (%), liq_baixa (bool), retorno_12m,
    ref_12m (mesma janela), categoria."""
    a: list[dict] = []

    def add(n, t, x):
        a.append({"nivel": n, "titulo": t, "texto": x})
    v = ctx.get("pl_var12m")
    if _ok(v) and v * 100 <= LIM_QUEDA_PL:
        add("atencao", "Patrimônio em queda", f"O patrimônio caiu {abs(v) * 100:.0f}% em 12 meses.")
    c = ctx.get("captacao_12m")
    if _ok(c) and c < LIM_RESGATE_LIQ:
        add("atencao", "Resgates maiores que aplicações", "A captação líquida dos últimos 12 meses é negativa.")
    cv = ctx.get("cotistas_var12m")
    if _ok(cv) and cv * 100 <= -15:
        add("atencao", "Menos cotistas", f"O número de cotistas caiu {abs(cv) * 100:.0f}% em 12 meses.")
    d = ctx.get("dd_atual")
    if _ok(d) and d * 100 <= LIM_DD:
        add("atencao", "Longe do pico", f"A cota está {abs(d) * 100:.0f}% abaixo do último pico.")
    te = ctx.get("te")
    if _ok(te) and te >= LIM_TE and ctx.get("categoria") in ("indice_amplo", "indexado", None):
        add("atencao", "Tracking error elevado", f"A réplica do índice desvia {te * 100:.1f}% ao ano (volatilidade da diferença).")
    t1 = ctx.get("top1")
    if _ok(t1) and t1 >= LIM_TOP1:
        add("atencao", "Posição concentrada", f"A maior posição da carteira divulgada pesa {t1:.0f}%.")
    tx = ctx.get("taxa_adm")
    if _ok(tx) and tx >= LIM_TAXA_ALTA:
        add("atencao", "Taxa de administração alta", f"{tx:.2f}% ao ano consome retorno todos os anos.")
    tp = ctx.get("taxa_perf")
    if _ok(tp) and tp > 0:
        add("info", "Taxa de performance", f"Cobra {tp:.0f}% sobre o que exceder o benchmark: confira a regra no regulamento.")
    if ctx.get("liq_baixa"):
        add("atencao", "Liquidez baixa na bolsa", "O volume médio negociado é baixo: o preço de compra e venda pode se afastar do valor da cota.")
    r, f = ctx.get("retorno_12m"), ctx.get("ref_12m")
    if _ok(r) and _ok(f) and r < f:
        add("info", "Abaixo da referência", f"Em 12 meses: {r * 100:.1f}% contra {f * 100:.1f}% da referência.")
    return [{**x, "titulo": _br(x["titulo"]), "texto": _br(x["texto"])} for x in a]


def relatorio(d: dict) -> dict:
    """Resumo automático em seções, só com fatos presentes em `d`. Chaves: nome, rotulos (lista de rótulos), estrategia,
    rent (rentabilidade()), risco (risco()), custos {taxa_adm,taxa_perf}, conc (concentracao()), consist (consistencia()),
    vs_ref (contra_referencia()), pares (texto), pl, alertas. Cada seção é uma lista de frases."""
    sec: dict[str, list[str]] = {"Resumo": [], "Estratégia": [], "Diversificação": [], "Custos": [], "Desempenho": [],
                                 "Risco": [], "Consistência": [], "Pontos positivos": [], "Pontos negativos": [],
                                 "Principais riscos": [], "Merecem atenção": []}
    pos, neg = sec["Pontos positivos"], sec["Pontos negativos"]
    rot = ", ".join(r["rotulo"] for r in d.get("rotulos") or []) or "categoria não identificada"
    sec["Resumo"].append(f"{d.get('nome') or 'Fundo'}: {rot}.")
    if d.get("pl") is not None:
        sec["Resumo"].append(f"Patrimônio: {d['pl']}.")
    if d.get("estrategia"):
        sec["Estratégia"].append(d["estrategia"])
    else:
        sec["Estratégia"].append("Estratégia não descrita na fonte: confira o regulamento e a lâmina do fundo.")
    c = d.get("conc") or {}
    cl, rotc, txt = qualidade_diversificacao(c)
    sec["Diversificação"].append(f"{rotc}: {txt}" if c.get("ok") else txt)
    if cl == "good":
        pos.append("Carteira diversificada na parte divulgada.")
    elif cl == "bad":
        neg.append("Carteira concentrada em poucos ativos.")
    k = d.get("custos") or {}
    if _ok(k.get("taxa_adm")):
        cat = d.get("categoria") or "outros"
        fc, ft = faixa_taxa(k["taxa_adm"], cat)
        sec["Custos"].append(f"Taxa de administração {k['taxa_adm']:.2f}% a.a.: {ft}.")
        if fc == "good":
            pos.append("Taxa de administração baixa para a categoria.")
        elif fc == "bad":
            neg.append("Taxa de administração alta para a categoria.")
        cum = custo_acumulado(k["taxa_adm"], 10)
        if cum is not None:
            sec["Custos"].append(f"Em 10 anos a taxa consome ≈ {cum * 100:.1f}% do patrimônio (efeito composto).")
    else:
        sec["Custos"].append("Taxa de administração sem dado na fonte.")
    if _ok(k.get("taxa_perf")) and k["taxa_perf"] > 0:
        sec["Custos"].append(f"Taxa de performance de {k['taxa_perf']:.0f}% sobre o que superar o benchmark.")
    r = d.get("rent") or {}
    if r.get("ok"):
        j = r["janelas"]
        partes = [f"{n}: {v * 100:+.1f}%" for n, v in j.items() if v is not None and n in ("12 meses", "36 meses", "60 meses")]
        if partes:
            sec["Desempenho"].append("Retorno acumulado — " + "; ".join(partes) + ".")
        else:
            sec["Desempenho"].append("Histórico menor que 12 meses: retornos por janela indisponíveis.")
        sec["Desempenho"].append(AVISO_PASSADO)
    ref = d.get("vs_ref") or {}
    if ref.get("ok"):
        sec["Desempenho"].append(f"Contra {ref['nome']} em {ref['anos']} ano(s): {ref['ativo'] * 100:.1f}% contra {ref['ref'] * 100:.1f}% "
                                 f"({ref['dif_pp']:+.1f} p.p.).")
        (pos if ref["dif_pp"] > 0 else neg).append(
            f"{'Superou' if ref['dif_pp'] > 0 else 'Ficou abaixo de'} {ref['nome']} em {ref['anos']} ano(s).")
    rk = d.get("risco") or {}
    if rk.get("ok"):
        sec["Risco"].append(f"Volatilidade anual {rk['vol'] * 100:.1f}%; pior queda {abs(rk['dd']['max']) * 100:.1f}%.")
        if rk.get("sharpe") is not None:
            sec["Risco"].append(f"Sharpe {rk['sharpe']:.2f}" + (f" e Sortino {rk['sortino']:.2f}." if rk.get("sortino") is not None else "."))
        if rk.get("te") is not None:
            sec["Risco"].append(f"Tracking error {rk['te'] * 100:.2f}% a.a.; diferença acumulada contra o índice {rk['td'] * 100:+.2f}%.")
        if rk["dd"]["max"] <= -0.30:
            neg.append("Já sofreu queda superior a 30% do pico.")
        elif rk["vol"] <= 0.08:
            pos.append("Volatilidade baixa no período (isso não elimina risco).")
    cs = d.get("consist") or {}
    if cs.get("meses_positivos") is not None:
        sec["Consistência"].append(f"{cs['meses_positivos'] * 100:.0f}% dos meses fecharam positivos ({cs['n_meses']} meses).")
        if cs.get("meses_acima_ref") is not None:
            sec["Consistência"].append(f"{cs['meses_acima_ref'] * 100:.0f}% dos meses acima da referência.")
        if cs.get("pior_12m") is not None:
            sec["Consistência"].append(f"Pior janela de 12 meses: {cs['pior_12m'] * 100:.1f}%; melhor: {cs['melhor_12m'] * 100:.1f}%.")
    else:
        sec["Consistência"].append("Histórico curto demais para medir consistência (mínimo ~6 meses).")
    if d.get("pares"):
        sec["Desempenho"].append(d["pares"])
    for r_ in d.get("riscos_estrategia") or []:
        sec["Principais riscos"].append(r_)
    for al in d.get("alertas") or []:
        sec["Merecem atenção"].append(f"{al['titulo']}: {al['texto']}")
    if not sec["Merecem atenção"]:
        sec["Merecem atenção"].append("Nenhum alerta verificável nos dados disponíveis (isso não significa ausência de risco).")
    if not pos:
        pos.append("Nenhum ponto positivo objetivo identificado nos dados disponíveis.")
    if not neg:
        neg.append("Nenhum ponto negativo objetivo identificado nos dados disponíveis.")
    return {k: [_br(x) for x in v] for k, v in sec.items() if v}


RISCOS_ESTRATEGIA = {
    "renda_fixa": ["Risco de crédito dos emissores e de marcação a mercado (a cota pode cair quando os juros sobem).",
                   "Come-cotas semestral reduz o rendimento em fundos de longo prazo."],
    "referenciado_di": ["Risco de crédito baixo, mas não nulo; a cota acompanha o CDI menos a taxa."],
    "acoes": ["Risco de mercado: o fundo acompanha a bolsa e pode ter quedas longas.",
              "Risco de concentração em poucos setores ou empresas."],
    "multimercado": ["Risco de estratégia: o gestor pode mudar posições, alavancar e usar derivativos.",
                     "Resultados dependem da gestão; compare só com multimercados da mesma estratégia."],
    "cambial": ["Risco cambial: a cota oscila com o dólar e outras moedas."],
    "imobiliario": ["Risco de vacância, de crédito (papel) e de liquidez da cota."],
    "internacional": ["Risco cambial e de mercados estrangeiros; tributação própria."],
    "cripto": ["Risco de volatilidade extrema e de custódia dos ativos subjacentes."],
    "commodities": ["Risco de preço da commodity (sem fluxo de caixa que sustente o valor)."],
    "setorial": ["Risco setorial: poucos setores concentram o resultado."],
    "dividendos": ["Dividendos não são garantidos e podem ser cortados."],
    "fatores": ["Fatores (momentum, qualidade, baixa volatilidade) podem ficar anos fora de moda."],
    "indice_amplo": ["Risco de mercado: o ETF cai junto com o índice."],
    "credito_privado": ["Risco de crédito: inadimplência de emissores; o FGC não cobre fundos."],
    "previdencia": ["Regras de tributação e de resgate próprias (regressiva/progressiva); confira o plano."],
}


def riscos_da_estrategia(rotulos: list[dict]) -> list[str]:
    out: list[str] = []
    for r in rotulos:
        for t in RISCOS_ESTRATEGIA.get(r["chave"], []):
            if t not in out:
                out.append(t)
    return out


# =============================================================================== comparação inteligente
def comparavel(a: dict, b: dict) -> tuple[bool, str]:
    """Dois ativos {categoria, benchmark, tipo} podem ser comparados como tendo o mesmo objetivo? Categoria principal
    diferente = não; mesma categoria com benchmarks diferentes = sim, com aviso."""
    if a.get("categoria") != b.get("categoria"):
        return False, (f"Objetivos diferentes ({a.get('categoria')} × {b.get('categoria')}): comparar retorno e risco "
                       "entre eles engana.")
    ba, bb = _norm(a.get("benchmark")), _norm(b.get("benchmark"))
    if ba and bb and ba != bb:
        return True, "Benchmarks diferentes: a diferença de retorno pode ser só do índice."
    return True, ""


def ranking(itens: list[dict], chave: str, melhor_alto: bool = True) -> list[dict]:
    """Ordena só quem tem o dado; quem não tem vai ao fim com posição None. Não preenche faltas."""
    com = sorted([i for i in itens if _ok(i.get(chave))], key=lambda i: i[chave], reverse=melhor_alto)
    sem = [i for i in itens if not _ok(i.get(chave))]
    return [{**i, "pos": n + 1} for n, i in enumerate(com)] + [{**i, "pos": None} for i in sem]


def pontuar(ind: dict, categoria: str) -> dict:
    """Nota educacional (0–100) por pilares com dado. ind: ret12m, ret36a (a.a.), vol, dd_max (negativo), sharpe, taxa_adm,
    liq_pct (pontos), meses_pos, pl. Pilares sem dado saem da média e reduzem a cobertura; nota só com ≥ 50% de cobertura."""
    def esc(x, ruim, bom):
        if not _ok(x):
            return None
        t = (x - ruim) / (bom - ruim)
        return max(0.0, min(1.0, t)) * 100
    taxa_ref = {"indice_amplo": (1.0, 0.1), "renda_fixa": (1.5, 0.2), "referenciado_di": (1.5, 0.2), "acoes": (2.5, 0.5),
                "multimercado": (3.0, 0.8)}.get(categoria, (2.0, 0.3))
    pil = {
        "Retorno": _media([esc(ind.get("ret12m"), 0, 25), esc(ind.get("cagr3"), 0, 15)]),
        "Risco": _media([esc(ind.get("vol"), 30, 5), esc(ind.get("dd_max"), -40, -3), esc(ind.get("sharpe"), 0, 1.5)]),
        "Consistência": _media([esc(ind.get("meses_pos"), 40, 80)]),
        "Custos": _media([esc(ind.get("taxa_adm"), *taxa_ref)]),
        "Porte e liquidez": _media([esc(None if not _ok(ind.get("pl")) else math.log10(max(ind["pl"], 1)), 6, 9.5)]),
    }
    pesos = {"Retorno": 30, "Risco": 30, "Consistência": 15, "Custos": 15, "Porte e liquidez": 10}
    cob = sum(pesos[k] for k, v in pil.items() if v is not None) / sum(pesos.values())
    com = {k: v for k, v in pil.items() if v is not None}
    nota = sum(pesos[k] * v for k, v in com.items()) / sum(pesos[k] for k in com) if com and cob >= 0.5 else None
    return {"nota": nota, "pilares": pil, "pesos": pesos, "cobertura": cob, "provisoria": nota is not None and cob < 0.7}


def _media(vals):
    v = [x for x in vals if x is not None]
    return sum(v) / len(v) if v else None


# =============================================================================== cadastro e informe da CVM (parte pura)
def cadastro_para_dict(linha: dict) -> dict:
    """Linha do cadastro da CVM → campos padronizados. Aceita o layout antigo (cad_fi: TAXA_ADM, RENTAB_FUNDO...) e o novo
    (registro_classe). O que não existe vira None, nunca zero."""
    def pega(*nomes):
        mapa = {_norm(k).replace("_", "").replace(" ", ""): v for k, v in linha.items()}
        for n in nomes:
            v = mapa.get(_norm(n).replace("_", "").replace(" ", ""))
            if v is not None and not (isinstance(v, float) and math.isnan(v)) and str(v).strip() not in ("", "nan", "None"):
                return v
        return None

    def num(v):
        if v is None:
            return None
        try:
            return float(str(v).replace(",", "."))
        except ValueError:
            return None
    return {
        "cnpj": pega("CNPJ_FUNDO", "CNPJ_Classe", "CNPJ_FUNDO_CLASSE"),
        "nome": pega("DENOM_SOCIAL", "Denominacao_Social", "Denominacao_Social_Classe"),
        "classe": pega("CLASSE", "Tipo_Classe", "Classificacao"),
        "classe_anbima": pega("CLASSE_ANBIMA", "Classificacao_Anbima"),
        "situacao": pega("SIT", "Situacao"),
        "benchmark": pega("RENTAB_FUNDO", "Indicador_Desempenho", "Benchmark"),
        "taxa_adm": num(pega("TAXA_ADM", "Taxa_Administracao")),
        "taxa_perf": num(pega("TAXA_PERFM", "Taxa_Performance")),
        "publico": pega("PUBLICO_ALVO", "Publico_Alvo"),
        "condominio": pega("CONDOM", "Forma_Condominio"),
        "exclusivo": pega("FUNDO_EXCLUSIVO", "Exclusivo"),
        "fundo_cotas": pega("FUNDO_COTAS"),
        "gestor": pega("GESTOR", "Gestor"),
        "administrador": pega("ADMIN", "Administrador"),
        "pl_cadastro": num(pega("VL_PATRIM_LIQ", "Patrimonio_Liquido")),
        "data_pl": pega("DT_PATRIM_LIQ", "Data_Patrimonio_Liquido"),
    }


def prazos_do_extrato(linha: dict) -> dict:
    """Do extrato da CVM, devolve QUALQUER campo cujo nome contenha 'prazo' ou 'carencia' (nome do campo → valor), sem supor
    o layout. Vazio = a fonte não informa."""
    out = {}
    for k, v in (linha or {}).items():
        n = _norm(k)
        if ("prazo" in n or "carenc" in n or "cotiz" in n) and v is not None and str(v).strip() not in ("", "nan", "None"):
            out[str(k)] = str(v).strip()
    return out


def padronizar_composicao(df: pd.DataFrame) -> pd.DataFrame:
    """Blocos da CDA (carteira) → colunas tipo, ativo, valor. Descobre colunas por nome; sem valor de mercado, devolve vazio
    (não estima). Várias linhas do mesmo ativo são somadas."""
    if df is None or df.empty:
        return pd.DataFrame(columns=["tipo", "ativo", "valor"])
    mapa = {_norm(c).replace("_", ""): c for c in df.columns}

    def col(*n):
        for x in n:
            if _norm(x).replace("_", "") in mapa:
                return mapa[_norm(x).replace("_", "")]
        return None
    c_val = col("VL_MERC_POS_FINAL", "VL_POSICAO_FINAL", "VL_MERC_POS")
    c_tipo = col("TP_APLIC", "TP_ATIVO", "TP_APLIC_ATIVO")
    c_ativo = col("CD_ATIVO", "DS_ATIVO", "EMISSOR", "CD_ISIN", "CPF_CNPJ_EMISSOR", "TP_TITPUB", "TP_ATIVO", "CD_SELIC")
    if c_val is None:
        return pd.DataFrame(columns=["tipo", "ativo", "valor"])
    out = pd.DataFrame({"tipo": df[c_tipo].astype(str).str.strip() if c_tipo else "Não informado",
                        "ativo": df[c_ativo].astype(str).str.strip() if c_ativo else "Não informado",
                        "valor": pd.to_numeric(df[c_val].astype(str).str.replace(",", "."), errors="coerce")})
    out = out.dropna(subset=["valor"])
    out = out[out["valor"] > 0]
    return out.groupby(["tipo", "ativo"], as_index=False)["valor"].sum().sort_values("valor", ascending=False)


def composicao_por_tipo(comp: pd.DataFrame) -> pd.Series:
    if comp is None or comp.empty:
        return pd.Series(dtype=float)
    s = comp.groupby("tipo")["valor"].sum().sort_values(ascending=False)
    return s / s.sum() * 100


# =============================================================================== ligação com o comparador (Passo 6)
def inds_para_comparador(rent: dict, rk: dict, cons: dict, custos: dict, pl: float | None, data_ref: str | None,
                         origem: str = "calculado") -> dict:
    """Indicadores no formato do comparador (Ind). Importa o comparador só aqui para manter o módulo independente."""
    from comparador import Ind
    j = rent.get("janelas", {}) if rent else {}
    ind = {
        "ret1m": Ind(None if j.get("1 mês") is None else j["1 mês"] * 100, origem, None, data_ref),
        "ret6m": Ind(None if j.get("6 meses") is None else j["6 meses"] * 100, origem, None, data_ref),
        "ret12m": Ind(None if j.get("12 meses") is None else j["12 meses"] * 100, origem, "12m", data_ref),
        "vol": Ind(None if not rk.get("vol") else rk["vol"] * 100, origem, "período", data_ref),
        "dd_max": Ind(None if rk.get("dd", {}).get("max") is None else rk["dd"]["max"] * 100, origem, "período", data_ref),
        "queda_pico": Ind(None if rk.get("dd", {}).get("atual") is None else rk["dd"]["atual"] * 100, origem, "período", data_ref),
        "taxa_adm": Ind(custos.get("taxa_adm"), "dado", None, data_ref),
        "pl": Ind(pl, "dado", None, data_ref),
        "sharpe": Ind(rk.get("sharpe"), origem, "período", data_ref),
        "tracking_error": Ind(None if rk.get("te") is None else rk["te"] * 100, origem, "período", data_ref),
        "meses_pos": Ind(None if cons.get("meses_positivos") is None else cons["meses_positivos"] * 100, origem, None, data_ref),
        "cagr3": Ind(None if not rent or rent["cagr"].get(3) is None else rent["cagr"][3] * 100, origem, "3 anos", data_ref),
    }
    return ind


# =============================================================================== benchmark, classe de ativo e análise completa
BENCH_TEXTOS = (("cdi", "CDI", ("cdi", "di", "selic", "referenciado di")), ("ibov", "Ibovespa", ("ibovespa", "ibov", "ibrx", "ibr-x")),
                ("ipca", "IPCA", ("ipca", "ima-b", "imab", "inflacao")), ("dolar", "Dólar (PTAX)", ("dolar", "ptax", "usd")),
                ("sp500", "S&P 500", ("s&p", "sp500", "sp 500")))


def benchmark_do_texto(texto: str | None, categoria: str = "") -> dict:
    """Benchmark de um FUNDO: primeiro o que o cadastro da CVM declara; sem declaração, só categorias com benchmark
    inequívoco (renda fixa/referenciado DI/multimercado → CDI; ações → Ibovespa). Caso contrário: sem benchmark."""
    t = _norm(texto)
    for chave, nome, termos in BENCH_TEXTOS:
        if _tem(t, termos):
            return {"chave": chave, "nome": nome, "origem": "declarado no cadastro da CVM"}
    if categoria in ("renda_fixa", "referenciado_di", "multimercado", "credito_privado"):
        return {"chave": "cdi", "nome": "CDI", "origem": "padrão da categoria (o cadastro não declara benchmark)"}
    if categoria == "acoes":
        return {"chave": "ibov", "nome": "Ibovespa", "origem": "padrão da categoria (o cadastro não declara benchmark)"}
    return {"chave": None, "nome": None, "origem": "sem benchmark claro: não comparamos com índice"}


CLASSE_DE_ATIVO = {"renda_fixa": "Renda fixa", "referenciado_di": "Renda fixa", "credito_privado": "Renda fixa",
                   "acoes": "Ações", "indice_amplo": "Ações", "dividendos": "Ações", "setorial": "Ações", "fatores": "Ações",
                   "multimercado": "Multimercado", "cambial": "Câmbio", "commodities": "Commodities", "cripto": "Criptoativos",
                   "imobiliario": "Imobiliário", "previdencia": "Previdência"}


def classe_de_ativo(rotulos: list[dict]) -> str:
    """Classe de ativo para exposição da carteira, pelo rótulo mais específico. Sem rótulo: 'Não classificado'."""
    chaves = [r["chave"] for r in rotulos]
    for k in ("renda_fixa", "referenciado_di", "credito_privado", "commodities", "cripto", "imobiliario", "cambial",
              "multimercado", "previdencia", "acoes", "indice_amplo", "dividendos", "setorial", "fatores"):
        if k in chaves:
            return CLASSE_DE_ATIVO[k]
    return "Não classificado"


def analisar_tudo(fx: dict, hoje: date | None = None) -> dict:
    """Roda todas as análises sobre o dicionário preparado pela camada de dados. Chaves usadas de `fx`: serie (retorno total),
    nome, rotulos, categoria, ref (série do índice de referência) e ref_nome, ref_freq, rf_idx, ipca_idx, custos, pl,
    pl_var12m, captacao_12m, cotistas_var12m, pesos, volume, preco, moeda, estrategia."""
    s = serie(fx.get("serie"))
    rk = risco(s, fx.get("ref"), fx.get("rf_idx"), fx.get("ref_freq", "D"))
    s_px = serie(fx.get("serie_tracking")) if fx.get("serie_tracking") is not None else s     # ETF: preço contra índice de PREÇO
    if len(s_px) and fx.get("ref") is not None and len(serie(fx["ref"])) and fx.get("serie_tracking") is not None:
        rk2 = risco(s_px, fx["ref"], None, fx.get("ref_freq", "D"))
        for k in ("te", "td", "td_anual", "janela_ref", "beta", "corr"):
            if k in rk2:
                rk[k] = rk2[k]
        if "ref" in rk2["motivos"]:
            rk["motivos"]["ref"] = rk2["motivos"]["ref"]
    out = {"rent": rentabilidade(s), "risco": rk,
           "consist": consistencia(s, fx.get("ref")), "conc": concentracao(fx.get("pesos")) if fx.get("pesos") is not None else {"ok": False}}
    out["cal"] = retornos_calendario(s)
    out["vs_ref"] = contra_referencia(s_px, fx["ref"], 3, fx.get("ref_nome") or "referência") if fx.get("ref") is not None and len(serie(fx["ref"])) else {
        "ok": False, "motivo": "sem série do índice de referência", "anos": 3, "nome": fx.get("ref_nome")}
    if not out["vs_ref"]["ok"] and fx.get("ref") is not None and len(serie(fx["ref"])):
        out["vs_ref"] = contra_referencia(s_px, fx["ref"], 1, fx.get("ref_nome") or "referência")
    out["vs_cdi"] = {n: contra_referencia(s, fx["cdi_idx"], n, "CDI") for n in (1, 3)} if fx.get("cdi_idx") is not None and len(serie(fx["cdi_idx"])) else {}
    out["real"] = {n: retorno_real(s, fx["ipca_idx"], n) for n in (1, 3)} if fx.get("ipca_idx") is not None and len(serie(fx["ipca_idx"])) else {}
    liq = liquidez_financeira(fx["preco"], fx["volume"]) if fx.get("preco") is not None and fx.get("volume") is not None else None
    out["liquidez"] = liq
    classe_liq, txt_liq = faixa_liquidez_etf(liq, fx.get("moeda") or "BRL") if fx.get("tipo") == "etf" else ("na", "fundo aberto: sem negociação em bolsa")
    out["liq_classe"], out["liq_texto"] = classe_liq, txt_liq
    j = out["rent"].get("janelas", {})
    cat = fx.get("categoria") or "outros"
    ctx = {"pl_var12m": fx.get("pl_var12m"), "captacao_12m": fx.get("captacao_12m"), "cotistas_var12m": fx.get("cotistas_var12m"),
           "dd_atual": out["risco"]["dd"]["atual"], "te": out["risco"].get("te"), "top1": out["conc"].get("top1"),
           "taxa_adm": (fx.get("custos") or {}).get("taxa_adm"), "taxa_perf": (fx.get("custos") or {}).get("taxa_perf"),
           "liq_baixa": classe_liq == "bad", "retorno_12m": j.get("12 meses"), "categoria": cat,
           "ref_12m": (out["vs_ref"]["ref"] if out["vs_ref"].get("ok") and out["vs_ref"]["anos"] == 1 else None)}
    out["alertas"] = monitorar(ctx)
    out["riscos_estrategia"] = riscos_da_estrategia(fx.get("rotulos") or [])
    out["relatorio"] = relatorio({"nome": fx.get("nome"), "rotulos": fx.get("rotulos"), "estrategia": fx.get("estrategia"),
                                  "rent": out["rent"], "risco": out["risco"], "custos": fx.get("custos"), "conc": out["conc"],
                                  "consist": out["consist"], "vs_ref": out["vs_ref"], "categoria": cat, "alertas": out["alertas"],
                                  "riscos_estrategia": out["riscos_estrategia"], "pl": fx.get("pl_texto")})
    ind = {"ret12m": None if j.get("12 meses") is None else j["12 meses"] * 100,
           "cagr3": None if out["rent"]["cagr"].get(3) is None else out["rent"]["cagr"][3] * 100,
           "vol": None if out["risco"]["vol"] is None else out["risco"]["vol"] * 100,
           "dd_max": None if out["risco"]["dd"]["max"] is None else out["risco"]["dd"]["max"] * 100,
           "sharpe": out["risco"].get("sharpe"), "taxa_adm": (fx.get("custos") or {}).get("taxa_adm"),
           "meses_pos": None if out["consist"]["meses_positivos"] is None else out["consist"]["meses_positivos"] * 100,
           "pl": fx.get("pl")}
    out["nota"] = pontuar(ind, cat)
    out["ind"] = ind
    return out
