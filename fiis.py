"""
FIIs: classificação, leitura da lista do Fundamentus, qualidade dos dividendos, riscos, pares, relatório e carteira.

Módulo PURO (sem Streamlit e sem rede): recebe dados já coletados. Regras do passo 8:
  - só usa dado que existe; o que a fonte não entrega aparece como "indisponível", nunca como estimativa;
  - Dividend Yield alto NÃO é tratado como positivo: ele só pontua dentro de uma faixa e é confrontado com os pares;
  - fundos de estratégias diferentes (tijolo, papel, FOF...) não são ranqueados entre si;
  - os limites abaixo (LIM_*) são regras educacionais para chamar atenção, não recomendação.
"""
from __future__ import annotations

import html as _html
import math
import re
import unicodedata
from dataclasses import dataclass, field

import pandas as pd

import crescimento as cr

# --------------------------------------------------------------------------- limites educacionais
LIM_VACANCIA_ALTA = 15.0       # % — acima disso, vacância alta
LIM_VACANCIA_MEDIA = 8.0
LIM_LIQ_ALTA = 300_000         # R$/dia — abaixo disso, risco de liquidez alto
LIM_LIQ_MEDIA = 1_000_000
LIM_IMOVEIS_ALTO = 2           # fundos de tijolo com até 2 imóveis: concentração alta
LIM_IMOVEIS_MEDIO = 5
LIM_PVP_AGIO = 1.15
LIM_PVP_DESCONTO = 0.70        # desconto muito grande: o mercado pode estar enxergando um problema
LIM_DY_ALTO = 14.0             # % ao ano
LIM_DY_VS_PARES = 1.5          # DY acima de 1,5× a mediana dos pares chama atenção
LIM_EXTRA = 1.5                # pagamento acima de 1,5× a mediana recente = candidato a extraordinário
LIM_REGULARIDADE = 10          # meses pagos em 12 abaixo disso = distribuição irregular
LIM_QUEDA_DIV = -0.15
LIM_PESO_ATIVO = 25.0          # % da carteira num único FII
LIM_PESO_SEGMENTO = 50.0       # % da carteira num segmento


def _ok(v) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def _chave(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


# =============================================================================== classificação
ESTRATEGIAS = {"tijolo": "Tijolo (imóveis físicos)", "papel": "Papel (recebíveis/CRIs)", "hibrido": "Híbrido",
               "fof": "Fundo de fundos (FOF)", "desenvolvimento": "Desenvolvimento", "outros": "Outros / não classificado"}

# (palavra-chave no segmento normalizado, estratégia, segmento exibido). Vale a primeira que bater.
REGRAS_SEGMENTO = [
    ("fundodefundos", "fof", "Fundo de fundos"), ("fof", "fof", "Fundo de fundos"),
    ("titulos", "papel", "Papel (CRI/LCI)"), ("valoresmob", "papel", "Papel (CRI/LCI)"), ("recebiv", "papel", "Papel (CRI/LCI)"),
    ("papel", "papel", "Papel (CRI/LCI)"), ("hibrido", "hibrido", "Híbrido"), ("misto", "hibrido", "Híbrido"),
    ("desenvolv", "desenvolvimento", "Desenvolvimento"),
    ("shopping", "tijolo", "Shopping centers"), ("logist", "tijolo", "Logística"), ("industrial", "tijolo", "Logística"),
    ("laje", "tijolo", "Lajes corporativas"), ("corporativ", "tijolo", "Lajes corporativas"),
    ("escritorio", "tijolo", "Lajes corporativas"), ("hotel", "tijolo", "Hotéis"), ("agencia", "tijolo", "Agências bancárias"),
    ("urbana", "tijolo", "Renda urbana"), ("varejo", "tijolo", "Renda urbana"), ("hospital", "tijolo", "Hospitais"),
    ("educacion", "tijolo", "Educacional"), ("residenc", "tijolo", "Residencial"), ("terras", "tijolo", "Terras e fazendas"),
    ("fazenda", "tijolo", "Terras e fazendas"),
]


@dataclass
class ClasseFii:
    estrategia: str                # chave de ESTRATEGIAS
    segmento: str                  # nome exibido
    confianca: str                 # "alta" (segmento reconhecido) | "baixa" (não reconhecido)
    origem: str

    @property
    def rotulo(self) -> str:
        return f"{ESTRATEGIAS[self.estrategia]} · {self.segmento}"


def classificar(segmento_fonte: str | None, nome: str | None = None, origem: str = "Fundamentus") -> ClasseFii:
    """Classifica pelo segmento informado pela fonte. Segmento desconhecido ou 'Outros' fica "outros" com confiança
    baixa: não se adivinha. (O nome do fundo só serve para o caso de agências/renda urbana, quando traz a palavra.)"""
    seg = _chave(segmento_fonte or "")
    for chave, est, nome_seg in REGRAS_SEGMENTO:
        if chave in seg:
            return ClasseFii(est, nome_seg, "alta", origem)
    n = _chave(nome or "")
    for chave, est, nome_seg in (("agencia", "tijolo", "Agências bancárias"), ("urbana", "tijolo", "Renda urbana")):
        if chave in n:
            return ClasseFii(est, nome_seg, "baixa", "nome do fundo")
    return ClasseFii("outros", (segmento_fonte or "Não informado").strip() or "Não informado", "baixa", origem)


def comparaveis(a: ClasseFii, b: ClasseFii) -> tuple[bool, str]:
    """Dois FIIs podem ser comparados indiscriminadamente? Mesma estratégia é o mínimo; tijolo de segmentos diferentes
    (shopping × logística) só compara critérios gerais."""
    if "outros" in (a.estrategia, b.estrategia):
        return False, "Um dos fundos não tem segmento identificado: a comparação direta pode enganar."
    if a.estrategia != b.estrategia:
        return False, (f"Estratégias diferentes ({ESTRATEGIAS[a.estrategia]} × {ESTRATEGIAS[b.estrategia]}): risco, renda e "
                       "valuation seguem lógicas distintas. Compare só liquidez, retorno e volatilidade.")
    if a.estrategia == "tijolo" and a.segmento != b.segmento:
        return True, (f"Segmentos de tijolo diferentes ({a.segmento} × {b.segmento}): vacância e P/VP não têm o mesmo patamar "
                      "normal em cada segmento.")
    return True, ""


# =============================================================================== lista do Fundamentus
CAMPOS_LISTA = {
    "papel": ("papel",), "segmento": ("segmento",), "cotacao": ("cotacao",), "ffo_yield": ("ffoyield",),
    "dy": ("dividendyield", "divyield"), "pvp": ("pvp",), "valor_mercado": ("valordemercado",), "liquidez": ("liquidez",),
    "qtd_imoveis": ("qtddeimoveis", "qtdimoveis"), "preco_m2": ("precodom2", "precom2"),
    "aluguel_m2": ("aluguelporm2", "aluguelm2"), "cap_rate": ("caprate",), "vacancia": ("vacanciamedia",),
}


class LayoutInesperado(Exception):
    pass


def num_br(txt) -> float | None:
    """'1.234,56' → 1234.56 ; '8,9%' → 8.9 ; vazio, '-' ou texto → None. Padrão brasileiro."""
    if txt is None:
        return None
    s = re.sub(r"[^0-9,.\-]", "", str(txt))
    if s in ("", "-", ".", ","):
        return None
    try:
        v = float(s.replace(".", "").replace(",", "."))
    except ValueError:
        return None
    return v if math.isfinite(v) else None


_TR = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TC = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def _texto(h: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def ler_lista_fundamentus(conteudo: str) -> pd.DataFrame:
    """Tabela de todos os FIIs (fii_resultado.php). Índice = código. Colunas numéricas em float (None quando a fonte
    traz '-' ou texto). Levanta LayoutInesperado se não achar a coluna do código (o site pode ter mudado)."""
    linhas = [[_texto(c) for c in _TC.findall(tr)] for tr in _TR.findall(conteudo)]
    linhas = [l for l in linhas if len(l) >= 3]
    cab_i = next((i for i, l in enumerate(linhas) if any(_chave(c) == "papel" for c in l)), None)
    if cab_i is None:
        raise LayoutInesperado("coluna 'Papel' não encontrada na tabela de FIIs")
    cab = [_chave(c) for c in linhas[cab_i]]
    pos = {}
    for campo, nomes in CAMPOS_LISTA.items():
        for n in nomes:
            if n in cab:
                pos[campo] = cab.index(n)
                break
    if "papel" not in pos:
        raise LayoutInesperado("coluna 'Papel' não encontrada")
    registros = []
    for l in linhas[cab_i + 1:]:
        if len(l) <= pos["papel"]:
            continue
        tk = l[pos["papel"]].strip().upper()
        if not re.fullmatch(r"[A-Z]{4}\d{1,2}", tk):
            continue
        reg = {"papel": tk}
        for campo, i in pos.items():
            if campo == "papel" or i >= len(l):
                continue
            reg[campo] = l[i].strip() if campo == "segmento" else num_br(l[i])
        registros.append(reg)
    if not registros:
        raise LayoutInesperado("nenhum FII encontrado na tabela")
    df = pd.DataFrame(registros).drop_duplicates("papel").set_index("papel")
    return df


def classificar_lista(df: pd.DataFrame) -> pd.DataFrame:
    """Acrescenta estrategia/segmento_nome/confianca à lista."""
    if df is None or df.empty:
        return df
    out = df.copy()
    cls = [classificar(out["segmento"].get(tk) if "segmento" in out else None) for tk in out.index]
    out["estrategia"] = [c.estrategia for c in cls]
    out["segmento_nome"] = [c.segmento for c in cls]
    out["confianca"] = [c.confianca for c in cls]
    return out


# =============================================================================== dividendos
@dataclass
class Extraordinario:
    mes: str
    valor: float
    razao: float                   # valor ÷ mediana recente


def analisar_dividendos(div, preco: float | None = None) -> dict:
    """Qualidade dos rendimentos a partir da série de proventos por cota (índice = data). Mede regularidade, estabilidade,
    tendência e candidatos a rendimento extraordinário. NÃO sabe se o fundo usou reserva ou se o resultado cobre a
    distribuição (isso exige o informe trimestral/relatório gerencial): esses campos vêm como None e a tela explica."""
    s = cr.serie_limpa(div)
    s = s[s > 0]
    out = {"ok": False, "n_pagamentos": int(len(s)), "motivo": None}
    if len(s) < 6:
        out["motivo"] = "menos de 6 pagamentos no histórico: análise de regularidade não se aplica"
        return out
    mensal = s.groupby(s.index.to_period("M")).sum()
    meses = pd.period_range(mensal.index.min(), mensal.index.max(), freq="M")
    mensal = mensal.reindex(meses, fill_value=0.0)
    ult12, ant12 = mensal.iloc[-12:], mensal.iloc[-24:-12] if len(mensal) >= 24 else None
    pagos12 = int((ult12 > 0).sum())
    base = ult12[ult12 > 0]
    med = float(base.median()) if len(base) else None
    out.update({"ok": True, "primeiro": str(mensal.index[0]), "ultimo": str(mensal.index[-1]), "meses_historico": len(mensal),
                "meses_pagos_12": pagos12 if len(mensal) >= 12 else None,
                "regularidade": pagos12 / 12 * 100 if len(mensal) >= 12 else None,
                "soma_12m": float(ult12.sum()) if len(mensal) >= 12 else None,
                "mediana_12m": med, "ultimo_valor": float(mensal.iloc[-1]),
                "cv": float(base.std() / base.mean() * 100) if len(base) >= 3 and base.mean() > 0 else None})
    # candidatos a extraordinário: acima de 1,5× a mediana dos 12 meses anteriores ao pagamento, isolados
    extras = []
    for i in range(len(mensal)):
        v = float(mensal.iloc[i])
        if v <= 0 or i < 6:
            continue
        ref = mensal.iloc[max(0, i - 12):i]
        ref = ref[ref > 0]
        if len(ref) < 4:
            continue
        m = float(ref.median())
        prox = float(mensal.iloc[i + 1]) if i + 1 < len(mensal) else None
        if m > 0 and v > LIM_EXTRA * m and (prox is None or prox <= LIM_EXTRA * m):
            extras.append(Extraordinario(str(mensal.index[i]), v, v / m))
    recentes = [e for e in extras if pd.Period(e.mes) >= mensal.index[-1] - 11]
    out["extraordinarios"] = extras
    out["extraordinarios_12m"] = recentes
    soma_extra = sum(e.valor - (med or 0) for e in recentes) if med else 0.0
    out["soma_recorrente_12m"] = (out["soma_12m"] - soma_extra) if out["soma_12m"] is not None else None
    out["peso_extra_12m"] = (soma_extra / out["soma_12m"] * 100) if out["soma_12m"] and soma_extra > 0 else 0.0
    if ant12 is not None and ant12.sum() > 0:
        out["var_12m"] = float(ult12.sum() / ant12.sum() - 1)
    else:
        out["var_12m"] = None
    out["queda_ultimo"] = (float(mensal.iloc[-1] / med - 1) if med and mensal.iloc[-1] > 0 else (-1.0 if med else None))
    ultimo_mes_pago = mensal.iloc[-1] > 0
    out["ultimo_mes_sem_pagar"] = not bool(ultimo_mes_pago)
    if preco and _ok(preco) and preco > 0 and out["soma_12m"] is not None:
        out["dy_12m"] = out["soma_12m"] / preco * 100
        out["dy_recorrente"] = out["soma_recorrente_12m"] / preco * 100
    else:
        out["dy_12m"] = out["dy_recorrente"] = None
    out["anuais"] = cr.serie_limpa(mensal.groupby(mensal.index.year).sum().rename(lambda a: pd.Timestamp(f"{a}-12-31")))
    # sem dado na fonte (Yahoo só traz data do pagamento e valor)
    out["indisponivel"] = ["Resultado recorrente × distribuição", "Uso de reservas para distribuir",
                           "Dividendo anunciado × efetivamente pago"]
    return out


def classe_dividendo(d: dict) -> tuple[str, list[str]]:
    """Resumo qualitativo da distribuição: ('boa' | 'atencao' | 'fraca' | 'insuficiente', motivos)."""
    if not d.get("ok") or d.get("regularidade") is None:
        return "insuficiente", [d.get("motivo") or "histórico curto"]
    motivos, pontos = [], 0
    if d["meses_pagos_12"] >= LIM_REGULARIDADE:
        motivos.append(f"pagou em {d['meses_pagos_12']} dos últimos 12 meses")
    else:
        pontos += 2
        motivos.append(f"pagou só em {d['meses_pagos_12']} dos últimos 12 meses (irregular)")
    if d["cv"] is not None and d["cv"] > 25:
        pontos += 1
        motivos.append(f"valores oscilam muito (variação de {d['cv']:.0f}% em torno da média)")
    if d["peso_extra_12m"] and d["peso_extra_12m"] >= 15:
        pontos += 1
        motivos.append(f"cerca de {d['peso_extra_12m']:.0f}% do total de 12 meses veio de pagamento acima do normal")
    if d.get("var_12m") is not None and d["var_12m"] <= LIM_QUEDA_DIV:
        pontos += 1
        motivos.append(f"total de 12 meses caiu {abs(d['var_12m']) * 100:.0f}% contra os 12 meses anteriores")
    if d["ultimo_mes_sem_pagar"]:
        pontos += 1
        motivos.append("o mês mais recente não teve pagamento")
    return ("boa" if pontos == 0 else "atencao" if pontos <= 2 else "fraca"), motivos


# =============================================================================== riscos
@dataclass
class Risco:
    chave: str
    nome: str
    nivel: str                      # "alto" | "medio" | "baixo" | "indisponivel"
    texto: str
    evidencias: list = field(default_factory=list)


def _niv(v, alto, medio, maior_e_pior=True):
    if not _ok(v):
        return "indisponivel"
    if maior_e_pior:
        return "alto" if v >= alto else "medio" if v >= medio else "baixo"
    return "alto" if v <= alto else "medio" if v <= medio else "baixo"


def avaliar_riscos(c: ClasseFii, ind: dict, div: dict | None = None, pares: dict | None = None) -> list[Risco]:
    """Riscos do fundo com base só no que há de dado. `ind`: vacancia, qtd_imoveis, liquidez, pvp, dy, vol, dd_max,
    alavancagem. Risco sem dado aparece como 'indisponível' com a explicação do que faltaria (nunca vira 'baixo')."""
    r: list[Risco] = []
    tijolo = c.estrategia in ("tijolo", "hibrido")
    papel = c.estrategia in ("papel", "hibrido")
    div = div or {}
    pares = pares or {}

    vac = ind.get("vacancia")
    if tijolo or c.estrategia == "outros":
        n = _niv(vac, LIM_VACANCIA_ALTA, LIM_VACANCIA_MEDIA)
        r.append(Risco("vacancia", "Risco de vacância", n,
                       {"alto": "Vacância alta: imóveis vazios não pagam aluguel e reduzem o rendimento.",
                        "medio": "Vacância moderada: acompanhe se sobe de um mês para o outro.",
                        "baixo": "Vacância baixa para o padrão geral (cada segmento tem seu normal).",
                        "indisponivel": "Vacância não informada pela fonte para este fundo."}[n],
                       [f"Vacância média: {vac:.1f}%".replace(".", ",")] if _ok(vac) else []))
    nim = ind.get("qtd_imoveis")
    if tijolo:
        n = _niv(nim, LIM_IMOVEIS_ALTO, LIM_IMOVEIS_MEDIO, maior_e_pior=False)
        r.append(Risco("concentracao_imoveis", "Risco de concentração em imóveis", n,
                       {"alto": "Poucos imóveis: a perda de um inquilino pesa muito no resultado.",
                        "medio": "Carteira pequena: a diversificação é limitada.",
                        "baixo": "Número de imóveis razoável (isso não mede a concentração por inquilino).",
                        "indisponivel": "Número de imóveis não informado."}[n],
                       [f"{nim:.0f} imóvel(is)"] if _ok(nim) else []))
        r.append(Risco("concentracao_inquilinos", "Concentração de inquilinos", "indisponivel",
                       "O app ainda não lê a lista de inquilinos (está nos relatórios gerenciais). Verifique no relatório do "
                       "fundo quanto da receita vem do maior inquilino.", []))
    if papel:
        r.append(Risco("credito", "Risco de crédito (devedores dos CRIs)", "indisponivel",
                       "Fundos de papel dependem de os devedores pagarem. O app ainda não lê a carteira de CRIs "
                       "(devedores, garantias, LTV, inadimplência): consulte o relatório gerencial.", []))
        r.append(Risco("inadimplencia", "Inadimplência", "indisponivel",
                       "Sem fonte integrada para inadimplência da carteira.", []))
        r.append(Risco("juros_inflacao", "Sensibilidade a juros e inflação", "indisponivel",
                       "Em fundos de papel o rendimento acompanha o indexador (CDI, IPCA ou prefixado). Juros altos "
                       "costumam elevar o rendimento de CRIs em CDI e derrubar o preço de CRIs prefixados. Os indexadores "
                       "do fundo não estão disponíveis ao app.", []))
    elif tijolo:
        r.append(Risco("juros_inflacao", "Sensibilidade a juros e inflação", "indisponivel",
                       "Em fundos de tijolo os contratos costumam ser reajustados por IPCA/IGP-M, o que protege da inflação, "
                       "mas juros altos reduzem o preço das cotas. O app não lê os índices de reajuste dos contratos.", []))
    aval = ind.get("alavancagem")
    n = _niv(aval, 0.3, 0.1)
    r.append(Risco("alavancagem", "Risco de alavancagem e refinanciamento", n,
                   {"alto": "Passivo relevante frente ao patrimônio: dívida aumenta o risco e depende de refinanciamento.",
                    "medio": "Algum endividamento: vale conferir prazos e custo da dívida.",
                    "baixo": "Passivo baixo frente ao patrimônio.",
                    "indisponivel": "Alavancagem não calculada: o informe da CVM não foi lido para este fundo."}[n],
                   [f"Passivo ÷ patrimônio líquido: {aval * 100:.0f}%"] if _ok(aval) else []))
    liq = ind.get("liquidez")
    n = _niv(liq, LIM_LIQ_ALTA, LIM_LIQ_MEDIA, maior_e_pior=False)
    r.append(Risco("liquidez", "Risco de liquidez", n,
                   {"alto": "Pouco volume negociado: vender rápido pode exigir aceitar preço menor.",
                    "medio": "Liquidez moderada.", "baixo": "Boa liquidez diária.",
                    "indisponivel": "Liquidez não informada."}[n],
                   [f"Volume médio diário: R$ {liq:,.0f}".replace(",", ".")] if _ok(liq) else []))
    # sustentabilidade e valuation entram como riscos de preço/renda
    dy, med = ind.get("dy"), pares.get("dy_mediana")
    if _ok(dy):
        alto = dy >= LIM_DY_ALTO or (_ok(med) and med > 0 and dy >= LIM_DY_VS_PARES * med)
        r.append(Risco("dy_elevado", "Dividend Yield acima do normal", "medio" if alto else "baixo",
                       ("DY muito acima do padrão: pode ser preço depreciado, pagamento extraordinário ou distribuição que "
                        "a carteira não sustenta. DY alto, sozinho, não é sinal de qualidade.") if alto
                       else "DY dentro do que os pares praticam.",
                       [f"DY: {dy:.1f}%".replace(".", ",")] + ([f"Mediana dos pares: {med:.1f}%".replace(".", ",")] if _ok(med) else [])))
    if div.get("ok"):
        k, mot = classe_dividendo(div)
        r.append(Risco("distribuicao", "Regularidade dos rendimentos",
                       {"boa": "baixo", "atencao": "medio", "fraca": "alto", "insuficiente": "indisponivel"}[k],
                       "; ".join(mot).capitalize() + ".", []))
    pvp = ind.get("pvp")
    if _ok(pvp):
        if pvp >= LIM_PVP_AGIO:
            r.append(Risco("pvp", "Preço acima do valor patrimonial", "medio",
                           "A cota custa mais que o patrimônio por cota: o ágio só se justifica por gestão ou renda diferenciada.",
                           [f"P/VP: {pvp:.2f}".replace(".", ",")]))
        elif pvp <= LIM_PVP_DESCONTO:
            r.append(Risco("pvp", "Desconto muito grande sobre o patrimônio", "medio",
                           "O mercado paga bem menos que o patrimônio declarado: pode ser oportunidade ou sinal de que o valor "
                           "contábil dos imóveis/recebíveis não é confiável.", [f"P/VP: {pvp:.2f}".replace(".", ",")]))
    vol, dd = ind.get("vol"), ind.get("dd_max")
    if _ok(dd):
        n = _niv(dd, -25, -12, maior_e_pior=False)
        r.append(Risco("preco", "Oscilação do preço (12 meses)", n,
                       {"alto": "Queda forte nos últimos 12 meses.", "medio": "Queda moderada.", "baixo": "Oscilação contida.",
                        "indisponivel": ""}[n],
                       [f"Maior queda: {dd:.0f}%"] + ([f"Volatilidade anual: {vol:.0f}%"] if _ok(vol) else [])))
    return r


# =============================================================================== pares e rankings
def pares(lista: pd.DataFrame, tk: str, minimo: int = 3) -> tuple[pd.DataFrame, str]:
    """Pares do fundo na lista: mesmo segmento (tijolo) ou mesma estratégia. Devolve (df sem o próprio fundo, descrição).
    Se houver menos de `minimo` pares no segmento, usa a estratégia toda e avisa."""
    if lista is None or lista.empty or tk not in lista.index or "estrategia" not in lista:
        return pd.DataFrame(), "sem lista de FIIs"
    row = lista.loc[tk]
    mesma = lista[(lista["estrategia"] == row["estrategia"]) & (lista.index != tk)]
    if row["estrategia"] == "outros":
        return pd.DataFrame(), "fundo sem segmento identificado"
    seg = mesma[mesma["segmento_nome"] == row["segmento_nome"]]
    if row["estrategia"] == "tijolo" and len(seg) >= minimo:
        return seg, f"{row['segmento_nome']} ({len(seg)} fundos)"
    return mesma, f"{ESTRATEGIAS[row['estrategia']]} ({len(mesma)} fundos)" + (
        " — poucos pares no mesmo segmento" if row["estrategia"] == "tijolo" else "")


def mediana_pares(df: pd.DataFrame, coluna: str, liq_min: float = 100_000) -> float | None:
    if df is None or df.empty or coluna not in df:
        return None
    d = df[df["liquidez"] >= liq_min] if "liquidez" in df else df
    s = pd.to_numeric(d[coluna], errors="coerce").dropna()
    return float(s.median()) if len(s) >= 3 else None


CRITERIOS_RANKING = {
    "valuation": ("pvp", True, "P/VP (menor = mais barato frente ao patrimônio)"),
    "renda": ("dy", False, "Dividend Yield (dentro de uma faixa saudável: veja a nota)"),
    "liquidez": ("liquidez", False, "Liquidez diária"),
    "vacancia": ("vacancia", True, "Vacância (menor = melhor)"),
    "tamanho": ("valor_mercado", False, "Valor de mercado (porte)"),
}


def ranking(df: pd.DataFrame, criterio: str, liq_min: float = 100_000, topo: int = 10) -> pd.DataFrame:
    """Ranking SÓ dentro do df recebido (deve ser de uma mesma estratégia/segmento). Fundos com liquidez abaixo do mínimo
    ficam fora (preço de fundo ilíquido engana). No critério 'renda' o DY acima do limite ou de 1,5× a mediana não
    sobe no ranking: é movido para o fim, porque DY muito alto costuma ser sinal de problema, não de qualidade."""
    col, crescente, _ = CRITERIOS_RANKING[criterio]
    if df is None or df.empty or col not in df:
        return pd.DataFrame()
    d = df[df.get("liquidez", pd.Series(dtype=float)) >= liq_min] if "liquidez" in df else df
    d = d.dropna(subset=[col])
    if criterio == "valuation":
        d = d[d[col] > 0]
    if criterio == "renda" and len(d) >= 3:
        med = float(d[col].median())
        suspeito = (d[col] >= LIM_DY_ALTO) | (d[col] >= LIM_DY_VS_PARES * med)
        d = pd.concat([d[~suspeito].sort_values(col, ascending=False), d[suspeito].sort_values(col)])
        return d.head(topo)
    return d.sort_values(col, ascending=crescente).head(topo)


# =============================================================================== relatório automático
def montar_relatorio(tk: str, c: ClasseFii, ind: dict, div: dict | None, riscos: list[Risco], pares_info: dict | None = None,
                     datas: dict | None = None) -> dict:
    """Relatório em seções {titulo: [linhas]} só com o que há de dado. 'indisponivel' lista o que falta."""
    div = div or {}
    pares_info = pares_info or {}
    secoes: dict[str, list] = {}
    pos, neg, atencao, indisp = [], [], [], []

    def f(v, casas=2, suf=""):
        return "n/d" if not _ok(v) else f"{v:,.{casas}f}{suf}".replace(",", "X").replace(".", ",").replace("X", ".")
    pvp, dy, vac = ind.get("pvp"), ind.get("dy"), ind.get("vacancia")
    secoes["Resumo"] = [f"{tk}: {c.rotulo}." + ("" if c.confianca == "alta" else " (classificação de baixa confiança)"),
                        f"Cota: R$ {f(ind.get('cotacao'))} · P/VP {f(pvp)} · DY {f(dy, 1, '%')} · liquidez R$ {f(ind.get('liquidez'), 0)}/dia."]
    # carteira
    carteira = []
    if c.estrategia in ("tijolo", "hibrido"):
        carteira.append(f"Imóveis: {f(ind.get('qtd_imoveis'), 0)} · vacância média {f(vac, 1, '%')}.")
        if _ok(ind.get("cap_rate")):
            carteira.append(f"Cap rate informado: {f(ind['cap_rate'], 1, '%')}.")
        if _ok(vac):
            (neg if vac >= LIM_VACANCIA_ALTA else pos if vac < LIM_VACANCIA_MEDIA else atencao).append(f"Vacância de {f(vac, 1, '%')}.")
    if c.estrategia in ("papel", "hibrido"):
        carteira.append("Carteira de CRIs, indexadores, LTV e inadimplência: sem fonte integrada (consulte o relatório gerencial).")
        indisp.append("Carteira de CRIs (devedores, indexadores, garantias, LTV)")
    if c.estrategia == "fof":
        carteira.append("Fundo de fundos: a qualidade depende dos fundos em que investe (composição não integrada ao app).")
        indisp.append("Composição de um FOF")
    secoes["Qualidade da carteira"] = carteira or ["Sem dados da carteira para este tipo de fundo."]
    # dividendos
    if div.get("ok"):
        k, mot = classe_dividendo(div)
        sus = [f"Avaliação geral: {k}. " + "; ".join(mot) + "."]
        if div.get("dy_recorrente") is not None and div.get("dy_12m") is not None and abs(div["dy_12m"] - div["dy_recorrente"]) > 0.3:
            sus.append(f"DY de 12 meses {f(div['dy_12m'], 1, '%')}; sem pagamentos acima do normal, {f(div['dy_recorrente'], 1, '%')}.")
        if div["extraordinarios_12m"]:
            sus.append("Pagamentos acima do normal: " + ", ".join(
                f"{e.mes} (×{e.razao:.1f})".replace(".", ",") for e in div["extraordinarios_12m"]) + ". Podem ser extraordinários.")
        sus.append("Não é possível dizer se o resultado cobre a distribuição nem se há uso de reservas: "
                   "isso exige o relatório gerencial.")
        secoes["Sustentabilidade dos rendimentos"] = sus
        (pos if k == "boa" else neg if k == "fraca" else atencao).append("Distribuição: " + "; ".join(mot) + ".")
        indisp += div["indisponivel"]
    else:
        secoes["Sustentabilidade dos rendimentos"] = [div.get("motivo") or "Sem histórico de rendimentos."]
    # patrimonial
    pat = []
    if _ok(pvp):
        txt = ("com ágio sobre o patrimônio" if pvp >= LIM_PVP_AGIO else "com desconto expressivo" if pvp <= LIM_PVP_DESCONTO
               else "abaixo do patrimônio" if pvp < 0.98 else "próximo do patrimônio")
        pat.append(f"P/VP {f(pvp)}: cota negociada {txt}.")
        (atencao if pvp >= LIM_PVP_AGIO or pvp <= LIM_PVP_DESCONTO else pos).append(f"P/VP {f(pvp)}.")
    else:
        pat.append("P/VP indisponível.")
        indisp.append("P/VP")
    if _ok(ind.get("vp_cota")):
        pat.append(f"Valor patrimonial por cota: R$ {f(ind['vp_cota'])}.")
    if _ok(ind.get("patrimonio")):
        pat.append(f"Patrimônio líquido: R$ {f(ind['patrimonio'] / 1e9, 2)} bi.")
    secoes["Avaliação patrimonial"] = pat
    # desempenho
    des = []
    if _ok(ind.get("ret12m")):
        des.append(f"Retorno total em 12 meses (com rendimentos): {f(ind['ret12m'], 1, '%')}.")
    if _ok(ind.get("dd_max")):
        des.append(f"Maior queda em 12 meses: {f(ind['dd_max'], 1, '%')}.")
    secoes["Histórico de desempenho"] = des or ["Sem histórico de preços."]
    # riscos
    secoes["Principais riscos"] = [f"{r.nome} — {r.nivel.upper()}: {r.texto}" for r in riscos if r.nivel in ("alto", "medio")] \
        or ["Nenhum risco acima do baixo foi identificado com os dados disponíveis (isso não significa ausência de risco)."]
    for r in riscos:
        if r.nivel == "alto":
            neg.append(r.nome + ".")
        elif r.nivel == "indisponivel":
            indisp.append(r.nome)
    # pares
    if pares_info.get("descricao"):
        linhas = [f"Comparado com {pares_info['descricao']}."]
        for k, rot in (("dy", "DY"), ("pvp", "P/VP"), ("vacancia", "vacância")):
            m = pares_info.get(f"{k}_mediana")
            v = ind.get(k)
            if _ok(m) and _ok(v):
                linhas.append(f"{rot}: {f(v, 2)} contra mediana {f(m, 2)}.")
        secoes["Comparação com fundos semelhantes"] = linhas
    secoes["Pontos positivos"] = pos or ["Nenhum ponto positivo claro nos dados disponíveis."]
    secoes["Pontos negativos"] = neg or ["Nenhum ponto negativo claro nos dados disponíveis."]
    secoes["Indicadores que merecem atenção"] = atencao or ["Nenhum."]
    secoes["Não disponível (sem fonte)"] = list(dict.fromkeys(indisp + ["Qualidade da gestão (não há dado verificável integrado)"]))
    if datas:
        secoes["Fontes e datas"] = [f"{k}: {v}" for k, v in datas.items()]
    return secoes


# =============================================================================== carteira
def analisar_carteira(lotes: list[dict], lista: pd.DataFrame, precos: dict | None = None) -> dict:
    """FIIs presentes na carteira: peso por fundo, estratégia e segmento, alertas de concentração e renda estimada pelo
    DY de 12 meses (estimativa de referência, não garantia). `lotes` = [{ticker, qtd, preco_medio}]. Não altera nada."""
    precos = precos or {}
    por: dict[str, dict] = {}
    for l in lotes or []:
        tk = str(l.get("ticker", "")).upper().strip()
        if not tk or tk not in (lista.index if lista is not None and not lista.empty else []):
            continue
        qtd = float(l.get("qtd") or 0)
        p = precos.get(tk) or (lista.loc[tk].get("cotacao") if "cotacao" in lista else None) or l.get("preco_medio")
        e = por.setdefault(tk, {"qtd": 0.0, "valor": 0.0, "custo": 0.0})
        e["qtd"] += qtd
        e["valor"] += qtd * float(p or 0)
        e["custo"] += qtd * float(l.get("preco_medio") or 0)
    out = {"fiis": [], "total": 0.0, "alertas": [], "por_estrategia": {}, "por_segmento": {}, "renda_mensal_estimada": None,
           "indisponivel": ["Concentração por gestor", "Concentração por imóvel e por devedor", "Distribuição de rendimentos já paga"]}
    total = sum(e["valor"] for e in por.values())
    if total <= 0:
        out["alertas"].append("Nenhum FII com preço encontrado na carteira.")
        return out
    out["total"] = total
    renda = 0.0
    tem_renda = False
    for tk, e in sorted(por.items(), key=lambda x: -x[1]["valor"]):
        row = lista.loc[tk]
        peso = e["valor"] / total * 100
        dy = row.get("dy") if "dy" in lista else None
        item = {"ticker": tk, "qtd": e["qtd"], "valor": e["valor"], "peso": peso, "estrategia": row.get("estrategia"),
                "segmento": row.get("segmento_nome"), "dy": dy, "pvp": row.get("pvp") if "pvp" in lista else None}
        out["fiis"].append(item)
        out["por_estrategia"][item["estrategia"]] = out["por_estrategia"].get(item["estrategia"], 0) + peso
        out["por_segmento"][item["segmento"]] = out["por_segmento"].get(item["segmento"], 0) + peso
        if _ok(dy):
            renda += e["valor"] * dy / 100 / 12
            tem_renda = True
        if peso >= LIM_PESO_ATIVO and len(por) > 1:
            out["alertas"].append(f"{tk} representa {peso:.0f}% dos seus FIIs: concentração em um único fundo.")
    for seg, p in out["por_segmento"].items():
        if p >= LIM_PESO_SEGMENTO and len(por) > 1:
            out["alertas"].append(f"{p:.0f}% dos seus FIIs estão em {seg}: concentração em um segmento.")
    if len(por) == 1:
        out["alertas"].append("Só um FII na carteira: toda a renda depende de um único fundo.")
    if "outros" in out["por_estrategia"]:
        out["alertas"].append("Há fundos sem segmento identificado: a distribuição por segmento está incompleta.")
    out["hhi"] = sum((i["peso"] / 100) ** 2 for i in out["fiis"])
    out["renda_mensal_estimada"] = renda if tem_renda else None
    return out


# =============================================================================== indicadores consolidados
def montar_indicadores(row: dict | None, snap: dict | None = None, pm: dict | None = None, dist: dict | None = None,
                       cvm: pd.DataFrame | None = None, hoje: str | None = None) -> tuple[dict, dict]:
    """Junta as fontes em um único dicionário de indicadores e devolve também `fontes[chave] = (fonte, data de referência)`.
    Prioridade: CVM (oficial, tem data do informe) > Fundamentus (valor de hoje) > Yahoo (preço/rendimentos).
    Nunca preenche com estimativa; o que nenhuma fonte tem fica ausente."""
    ind: dict = {}
    fontes: dict = {}

    def put(k, v, fonte, data=None):
        if _ok(v):
            ind[k] = float(v)
            fontes[k] = (fonte, data)

    row = row or {}
    snap = snap or {}
    pm = pm or {}
    dist = dist or {}
    F = "Fundamentus"
    # Fundamentus mostra 0 imóveis para fundos sem imóveis (papel, FOF) ou sem dado: 0 não é número de imóveis
    if _ok(row.get("qtd_imoveis")) and row["qtd_imoveis"] <= 0:
        row = {**row, "qtd_imoveis": None}
    if _ok(snap.get("imoveis")) and snap["imoveis"] <= 0:
        snap = {**snap, "imoveis": None}
    for k_ind, k_row in (("cotacao", "cotacao"), ("pvp", "pvp"), ("dy", "dy"), ("liquidez", "liquidez"),
                         ("valor_mercado", "valor_mercado"), ("vacancia", "vacancia"), ("qtd_imoveis", "qtd_imoveis"),
                         ("cap_rate", "cap_rate"), ("preco_m2", "preco_m2"), ("aluguel_m2", "aluguel_m2"), ("ffo_yield", "ffo_yield")):
        put(k_ind, row.get(k_row), F, hoje)
    # a página de detalhe do Fundamentus completa o que a lista não tem
    put("vp_cota", snap.get("vp_cota"), F, hoje)
    put("patrimonio", snap.get("pl"), F, hoje)
    put("cotas", snap.get("cotas"), F, hoje)
    for k in ("pvp", "dy", "vacancia", "valor_mercado", "qtd_imoveis"):
        if k not in ind:
            put(k, snap.get(k if k != "qtd_imoveis" else "imoveis"), F, hoje)
    for k in ("ret12m", "vol", "dd_max", "ret6m", "ret1m"):
        put(k, pm.get(k), "Yahoo Finance", hoje)
    if _ok(dist.get("dy12m")):
        put("dy12m", dist["dy12m"], "Yahoo Finance (proventos ÷ preço)", dist.get("data_ref"))
    if _ok(dist.get("meses_pagos")):
        put("meses_pagos", dist["meses_pagos"], "Yahoo Finance", dist.get("data_ref"))
    # CVM: último informe mensal sobrepõe o que for do mesmo assunto
    if cvm is not None and not cvm.empty:
        ult = cvm.index[-1].date().isoformat()
        for k_cvm, k_ind in (("pl", "patrimonio"), ("vp_cota", "vp_cota"), ("cotas", "cotas"), ("cotistas", "cotistas"),
                             ("alavancagem", "alavancagem"), ("dy_mes", "dy_mes")):
            if k_cvm in cvm.columns and _ok(cvm[k_cvm].iloc[-1]):
                put(k_ind, cvm[k_cvm].iloc[-1], "CVM (informe mensal)", ult)
    # P/VP coerente com a cota e o VP mais atual
    if _ok(ind.get("cotacao")) and _ok(ind.get("vp_cota")) and ind["vp_cota"] > 0:
        calc = ind["cotacao"] / ind["vp_cota"]
        if "pvp" in ind and abs(calc / ind["pvp"] - 1) > 0.10:
            fontes["pvp_aviso"] = (f"P/VP da fonte ({ind['pvp']:.2f}) difere do calculado com o VP da fonte mais recente "
                                   f"({calc:.2f}): os valores são de datas diferentes.", None)
        elif "pvp" not in ind:
            put("pvp", calc, "calculado (cotação ÷ VP por cota)", fontes["vp_cota"][1])
    return ind, fontes


# =============================================================================== monitoramento
LIM_MUDANCA = {"pvp": 0.10, "vacancia": 2.0, "dy": 1.5, "liquidez": 0.5}   # relativo (pvp, liquidez) ou pontos (vacancia, dy)


def detectar_mudancas(antes: dict | None, depois: dict | None) -> list[str]:
    """Compara duas fotografias de indicadores do mesmo FII e descreve só as mudanças acima do limite. Não age sobre nada."""
    out = []
    if not antes or not depois:
        return out
    for k, lim in LIM_MUDANCA.items():
        a, d = antes.get(k), depois.get(k)
        if not (_ok(a) and _ok(d)):
            continue
        if k in ("pvp", "liquidez"):
            if a > 0 and abs(d / a - 1) >= lim:
                out.append(f"{'P/VP' if k == 'pvp' else 'Liquidez'} mudou {((d / a - 1) * 100):+.0f}% (de {a:.2f} para {d:.2f}).".replace(".", ","))
        elif abs(d - a) >= lim:
            out.append(f"{'Vacância' if k == 'vacancia' else 'DY'} mudou {d - a:+.1f} ponto(s) percentual(is) (de {a:.1f}% para {d:.1f}%).".replace(".", ","))
    return out
