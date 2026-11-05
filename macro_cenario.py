"""Motor do cenário econômico: lê os indicadores em conjunto e classifica o ambiente em BOM, NEUTRO ou RUIM, por setor e por classe de ativo.

Puro: sem Streamlit, sem rede, sem IA e sem custo. Regras transparentes, todas escritas aqui.

Como funciona, em quatro camadas:
  1. INDICADORES (macro_fontes) -> cada um com nível, direção (variação recente), velocidade (aceleração) e posição no histórico.
  2. FATORES: 12 forças da economia (juros reais, tendência dos juros, inflação, atividade, emprego, estresse de crédito, risco fiscal,
     câmbio, juros dos EUA, petróleo, minério, aversão a risco). Cada fator vira um número de -1 a +1 que combina VÁRIOS indicadores
     (nível + direção). +1 significa "intenso" na direção do nome do fator (ex.: juros reais muito altos, inflação muito pressionada).
  3. SENSIBILIDADES: cada setor/classe tem pesos por fator (ex.: construção civil sofre com juros reais altos; petroleiras ganham com
     petróleo e dólar altos). O mesmo fator ajuda um setor e prejudica outro. Os pesos são educacionais e estão em SETORES.
  4. VEREDITO: nota = média ponderada (de -1 a +1) só com os fatores que têm dado ATUAL. >= +0,18 BOM, <= -0,18 RUIM, entre os dois NEUTRO.
     Há histerese (para sair de BOM/RUIM a nota precisa recuar mais), sinais contraditórios viram NEUTRO, e cobertura baixa de dados
     força NEUTRO com confiança baixa. Indicador desatualizado não entra na nota.
Nada aqui é recomendação: descreve condições econômicas, não prevê o preço de nenhum ativo.
"""
from __future__ import annotations

import math

import macro_fontes as MF

LIM_BOM, LIM_RUIM = 0.18, -0.18
HISTERESE = 0.08
VEREDITOS = ("BOM", "NEUTRO", "RUIM")
META_IPCA, TETO_IPCA = 3.0, 4.5


def _n(v, c=1) -> str:
    return f"{v:,.{c}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _pp(v, c=1) -> str:
    return ("+" if v >= 0 else "−") + _n(abs(v), c)


def _clip(x, lo=-1.0, hi=1.0) -> float:
    return max(lo, min(hi, float(x)))


def _ok(R: dict, i: str):
    """Indicador utilizável AGORA: existe e não está desatualizado nem indisponível."""
    r = (R or {}).get(i)
    return r if r and r.get("status") in ("atualizado", "provisorio", "revisado") and r.get("valor") is not None else None


def _comb(partes: list):
    """[(peso, valor -1..1, texto)] -> (valor, texto) ou None."""
    partes = [p for p in partes if p is not None]
    if not partes:
        return None
    pt = sum(p[0] for p in partes)
    return sum(p[0] * p[1] for p in partes) / pt, " ".join(p[2] for p in partes if p[2])


# ------------------------------------------------------------------ fatores
FATORES = {
    "juro_real": {"nome": "Juros reais", "alto": "juros reais mais altos", "baixo": "juros reais mais baixos", "ind": ["selic_meta", "focus_ipca", "ipca_12m"]},
    "juro_tendencia": {"nome": "Tendência dos juros", "alto": "juros em alta", "baixo": "juros em queda", "ind": ["selic_meta", "focus_selic"]},
    "inflacao": {"nome": "Pressão inflacionária", "alto": "inflação mais alta", "baixo": "inflação mais baixa", "ind": ["ipca_12m", "focus_ipca", "ipca15", "nucleo_ipca", "incc", "igpm"]},
    "atividade": {"nome": "Atividade econômica", "alto": "atividade mais forte", "baixo": "atividade mais fraca", "ind": ["ibcbr", "pib", "pmc", "pim", "pms", "confianca_consumidor"]},
    "emprego": {"nome": "Mercado de trabalho", "alto": "mercado de trabalho mais forte", "baixo": "mercado de trabalho mais fraco", "ind": ["desemprego", "rendimento", "massa_salarial"]},
    "credito_estresse": {"nome": "Estresse de crédito", "alto": "mais estresse no crédito", "baixo": "menos estresse no crédito", "ind": ["inadimplencia", "endividamento", "juros_credito", "concessoes"]},
    "fiscal_risco": {"nome": "Risco fiscal e país", "alto": "risco fiscal maior", "baixo": "risco fiscal menor", "ind": ["divida_bruta", "primario_12m", "embi"]},
    "cambio": {"nome": "Dólar", "alto": "dólar mais alto", "baixo": "dólar mais baixo", "ind": ["dolar"]},
    "juros_eua": {"nome": "Juros dos Estados Unidos", "alto": "juros americanos mais altos", "baixo": "juros americanos mais baixos", "ind": ["fed_funds", "us10y"]},
    "petroleo": {"nome": "Petróleo", "alto": "petróleo mais caro", "baixo": "petróleo mais barato", "ind": ["brent"]},
    "minerio": {"nome": "Minério de ferro", "alto": "minério mais caro", "baixo": "minério mais barato", "ind": ["minerio"]},
    "aversao_risco": {"nome": "Aversão a risco global", "alto": "mais aversão a risco no mundo", "baixo": "menos aversão a risco no mundo", "ind": ["vix", "dxy"]},
}


def _f_juro_real(R):
    s = _ok(R, "selic_meta")
    if not s:
        return None
    foc, i12 = _ok(R, "focus_ipca"), _ok(R, "ipca_12m")
    if foc:
        exp, rot = foc["valor"], "esperada pelo mercado para o ano"
    elif i12:
        exp, rot = i12["valor"], "dos últimos 12 meses"
    else:
        return None
    jr = ((1 + s["valor"] / 100) / (1 + exp / 100) - 1) * 100
    nivel = "muito altos" if jr >= 8 else "altos" if jr >= 6 else "moderados" if jr >= 3.5 else "baixos"
    return {"valor": _clip((jr - 5) / 3.5), "texto": f"Os juros reais estão {nivel}: cerca de {_n(jr)}% ao ano (Selic de {_n(s['valor'], 2)}% e inflação {rot} de {_n(exp)}%).",
            "numeros": {"juro_real": jr}, "usa": ["selic_meta", "focus_ipca" if foc else "ipca_12m"]}


def _f_juro_tend(R):
    s = _ok(R, "selic_meta")
    partes, usa, txt = [], [], []
    if s and s.get("d_curto") is not None:
        serie = MF.para_serie(s)
        d6 = float(serie.iloc[-1] - serie.iloc[-7]) if len(serie) > 7 else None
        if d6 is not None:
            partes.append((0.6, _clip(d6 / 2.0), ""))
            txt.append(f"A Selic {'subiu' if d6 > 0.05 else 'caiu' if d6 < -0.05 else 'ficou estável'}"
                       + (f" {_n(abs(d6), 2)} ponto percentual em 6 meses" if abs(d6) > 0.05 else " nos últimos 6 meses") + ".")
            usa.append("selic_meta")
    fs = _ok(R, "focus_selic")
    if s and fs:
        dif = fs["valor"] - s["valor"]
        partes.append((0.4, _clip(dif / 1.5), ""))
        txt.append(f"O mercado espera Selic de {_n(fs['valor'], 2)}% no fim do ano ({_n(abs(dif), 2)} ponto percentual {'acima' if dif > 0 else 'abaixo'} da atual).")
        usa.append("focus_selic")
    c = _comb(partes)
    return {"valor": c[0], "texto": " ".join(txt), "usa": usa, "numeros": {}} if c else None


def _f_inflacao(R):
    i12 = _ok(R, "ipca_12m")
    if not i12:
        return None
    partes, txt, usa = [], [], ["ipca_12m"]
    ref = i12["valor"]
    foc = _ok(R, "focus_ipca")
    if foc:
        ref = (i12["valor"] + foc["valor"]) / 2
        usa.append("focus_ipca")
    partes.append((0.7, _clip((ref - META_IPCA) / 3.0), ""))
    posicao = "acima do teto da meta" if i12["valor"] > TETO_IPCA else "acima do centro da meta" if i12["valor"] > META_IPCA + 0.25 else "dentro da meta"
    txt.append(f"O IPCA acumulado em 12 meses está em {_n(i12['valor'], 2)}%, {posicao} (centro de {_n(META_IPCA)}% e teto de {_n(TETO_IPCA)}%).")
    if i12.get("d_curto") is not None:
        partes.append((0.3, _clip(i12["d_curto"] / 1.0), ""))
        txt.append(f"Em 3 meses, o acumulado {'subiu' if i12['d_curto'] > 0.05 else 'caiu' if i12['d_curto'] < -0.05 else 'ficou estável'}.")
    nuc = _ok(R, "nucleo_ipca")
    if nuc:
        usa.append("nucleo_ipca")
    c = _comb(partes)
    return {"valor": c[0], "texto": " ".join(txt), "usa": usa, "numeros": {"ipca_12m": i12["valor"]}}


def _f_atividade(R):
    def yoy(i, centro, escala, rot):
        r = _ok(R, i)
        if not r or r.get("v12") is None:
            return None
        return (_PESOS_ATIV[i], _clip((r["v12"] - centro) / escala), f"{rot} {_pp(r['v12'])}% em 12 meses;")
    _PESOS_ATIV = {"ibcbr": .35, "pmc": .15, "pim": .10, "pms": .10}
    partes = [yoy("ibcbr", 1.5, 3.0, "IBC-Br"), yoy("pmc", 1.5, 4.0, "varejo"), yoy("pim", 0.5, 4.0, "indústria"), yoy("pms", 2.0, 4.0, "serviços")]
    pib = _ok(R, "pib")
    if pib:
        partes.append((.20, _clip((pib["valor"] - 2.0) / 2.5), f"PIB {_pp(pib['valor'])}% frente ao mesmo trimestre do ano anterior;"))
    icc = _ok(R, "confianca_consumidor")
    if icc:
        partes.append((.10, _clip((icc["valor"] - 90) / 15), f"confiança do consumidor em {_n(icc['valor'], 0)} pontos;"))
    c = _comb(partes)
    if not c:
        return None
    usa = [i for i in FATORES["atividade"]["ind"] if _ok(R, i)]
    txt = c[1].rstrip(";")
    return {"valor": c[0], "texto": "Atividade: " + txt + ".", "usa": usa, "numeros": {}}


def _f_emprego(R):
    partes, usa = [], []
    d = _ok(R, "desemprego")
    txt = []
    if d:
        partes.append((0.5, _clip((7.0 - d["valor"]) / 2.5), ""))
        txt.append(f"A taxa de desocupação está em {_n(d['valor'])}%" + (f", {'abaixo' if d['d12'] < 0 else 'acima'} dos {_n(d['valor'] - d['d12'])}% de 12 meses atrás" if d.get("d12") is not None and abs(d["d12"]) >= 0.1 else "") + ".")
        usa.append("desemprego")
        if d.get("d12") is not None:
            partes.append((0.25, _clip(-d["d12"] / 1.5), ""))
    r = _ok(R, "rendimento")
    if r and r.get("v12") is not None:
        partes.append((0.25, _clip((r["v12"] - 2.0) / 4.0), ""))
        txt.append(f"O rendimento médio real variou {_pp(r['v12'])}% em 12 meses.")
        usa.append("rendimento")
    c = _comb(partes)
    return {"valor": c[0], "texto": " ".join(txt), "usa": usa, "numeros": {}} if c else None


def _f_credito(R):
    partes, txt, usa = [], [], []
    a = _ok(R, "inadimplencia")
    if a:
        partes.append((.40, _clip((a["valor"] - 3.0) / 1.5), ""))
        txt.append(f"A inadimplência está em {_n(a['valor'])}% da carteira de crédito.")
        usa.append("inadimplencia")
    e = _ok(R, "endividamento")
    if e:
        partes.append((.25, _clip((e["valor"] - 45) / 10), ""))
        txt.append(f"As famílias devem {_n(e['valor'], 0)}% da renda de 12 meses.")
        usa.append("endividamento")
    j = _ok(R, "juros_credito")
    if j:
        partes.append((.20, _clip((j.get("d12") or 0) / 5.0 + (j["valor"] - 40) / 25), ""))
        txt.append(f"O juro médio do crédito está em {_n(j['valor'])}% ao ano.")
        usa.append("juros_credito")
    k = _ok(R, "concessoes")
    if k and k.get("v12") is not None:
        partes.append((.15, _clip(-(k["v12"] - 5) / 10), ""))
        txt.append(f"As concessões de crédito variaram {_pp(k['v12'])}% em 12 meses.")
        usa.append("concessoes")
    c = _comb(partes)
    return {"valor": c[0], "texto": " ".join(txt), "usa": usa, "numeros": {}} if c else None


def _f_fiscal(R):
    partes, txt, usa = [], [], []
    d = _ok(R, "divida_bruta")
    if d:
        partes.append((.4, _clip((d["valor"] - 75) / 10), ""))
        txt.append(f"A dívida bruta é de {_n(d['valor'])}% do PIB.")
        usa.append("divida_bruta")
    p = _ok(R, "primario_12m")
    if p:
        partes.append((.3, _clip((-0.5 - p["valor"]) / 1.5), ""))
        txt.append(f"O resultado primário em 12 meses é {_pp(p['valor'])}% do PIB.")
        usa.append("primario_12m")
    e = _ok(R, "embi")
    if e:
        partes.append((.3, _clip((e["valor"] - 200) / 150), ""))
        txt.append(f"O risco-país está em {_n(e['valor'], 0)} pontos-base.")
        usa.append("embi")
    c = _comb(partes)
    return {"valor": c[0], "texto": " ".join(txt), "usa": usa, "numeros": {}} if c else None


def _f_cambio(R):
    d = _ok(R, "dolar")
    if not d:
        return None
    partes, txt = [], [f"O dólar está em R$ {_n(d['valor'], 2)}"]
    if d.get("media_5a"):
        rel = (d["valor"] / d["media_5a"] - 1) * 100
        partes.append((.5, _clip(rel / 20), ""))
        txt[0] += f", {_n(abs(rel), 0)}% {'acima' if rel > 0 else 'abaixo'} da média de 5 anos"
    if d.get("v_curto") is not None:
        partes.append((.5, _clip(d["v_curto"] / 8), ""))
        txt.append(f"{'subiu' if d['v_curto'] > 0 else 'caiu'} {_n(abs(d['v_curto']))}% no último mês")
    c = _comb(partes)
    return {"valor": c[0], "texto": (" e ".join(txt) if len(txt) < 2 else txt[0] + " e " + txt[1]) + ".", "usa": ["dolar"], "numeros": {"dolar": d["valor"]}} if c else None


def _f_juros_eua(R):
    f, t = _ok(R, "fed_funds"), _ok(R, "us10y")
    partes, txt, usa = [], [], []
    if f:
        partes.append((.5, _clip((f["valor"] - 3.0) / 2.0), ""))
        txt.append(f"Os juros básicos dos EUA (Fed Funds) estão em {_n(f['valor'], 2)}%")
        usa.append("fed_funds")
    if t:
        partes.append((.5, _clip((t["valor"] - 3.5) / 1.2), ""))
        txt.append(("e o " if f else "O ") + f"Treasury de 10 anos {'em ' if f else 'está em '}{_n(t['valor'], 2)}%")
        usa.append("us10y")
    c = _comb(partes)
    return {"valor": c[0], "texto": " ".join(txt) + ".", "usa": usa, "numeros": {}} if c else None


def _f_commod(R, ind, nome):
    r = _ok(R, ind)
    if not r or r.get("v12") is None:
        return None
    unid = r["unidade"].replace("US$ ", "")
    return {"valor": _clip(r["v12"] / 30), "texto": f"{nome} está a US$ {_n(r['valor'], 0)} {unid}, com variação de {_pp(r['v12'], 0)}% em 12 meses.",
            "usa": [ind], "numeros": {}}


def _f_aversao(R):
    v, d = _ok(R, "vix"), _ok(R, "dxy")
    partes, txt, usa = [], [], []
    if v:
        partes.append((.7, _clip((v["valor"] - 18) / 10), ""))
        txt.append(f"O VIX (medo do mercado americano) está em {_n(v['valor'], 1)} pontos")
        usa.append("vix")
    if d and d.get("v12") is not None:
        partes.append((.3, _clip(d["v12"] / 8), ""))
        txt.append(("e o " if v else "O ") + f"dólar global variou {_pp(d['v12'])}% em 12 meses")
        usa.append("dxy")
    c = _comb(partes)
    return {"valor": c[0], "texto": " ".join(txt) + ".", "usa": usa, "numeros": {}} if c else None


_CALC = {"juro_real": _f_juro_real, "juro_tendencia": _f_juro_tend, "inflacao": _f_inflacao, "atividade": _f_atividade, "emprego": _f_emprego,
         "credito_estresse": _f_credito, "fiscal_risco": _f_fiscal, "cambio": _f_cambio, "juros_eua": _f_juros_eua,
         "petroleo": lambda R: _f_commod(R, "brent", "O Brent"), "minerio": lambda R: _f_commod(R, "minerio", "O minério de ferro"), "aversao_risco": _f_aversao}


def calcular_fatores(R: dict) -> dict:
    """{fator: {id, nome, valor (-1..1) ou None, texto, usa, qualidade (0..1), motivo_ausencia}}"""
    out = {}
    for fid, meta in FATORES.items():
        try:
            r = _CALC[fid](R)
        except (KeyError, TypeError, ValueError, IndexError, ZeroDivisionError):
            r = None
        if r is None:
            faltam = [i for i in meta["ind"] if not _ok(R, i)]
            desat = [i for i in faltam if (R.get(i) or {}).get("status") == "desatualizado"]
            out[fid] = {"id": fid, "nome": meta["nome"], "valor": None, "texto": "", "usa": [], "qualidade": 0.0,
                        "motivo": ("indicadores desatualizados: " + ", ".join(MF.CATALOGO[i]["nome"] for i in desat) + ". ") if desat else "sem dado confiável nas fontes."}
            continue
        q = [1.0 if (R.get(i) or {}).get("status") != "provisorio" else 0.85 for i in r["usa"]]
        out[fid] = {"id": fid, "nome": meta["nome"], "valor": round(r["valor"], 4), "texto": r["texto"], "usa": r["usa"],
                    "qualidade": round(sum(q) / len(q), 3) if q else 0.0, "numeros": r.get("numeros", {}), "motivo": ""}
    return out


# ------------------------------------------------------------------ setores e classes (pesos educacionais)
# pesos > 0: o fator ALTO ajuda; < 0: o fator ALTO prejudica. O mecanismo é a frase mostrada ao usuário: (quando alto, quando baixo).
SETORES: dict[str, dict] = {}


def _s(chave, nome, classe, pesos, mec, resumo=""):
    SETORES[chave] = {"chave": chave, "nome": nome, "classe": classe, "pesos": pesos, "mec": mec, "resumo": resumo}


_s("geral", "Brasil (cenário geral)", "geral",
   {"atividade": .30, "emprego": .15, "inflacao": -.20, "juro_real": -.20, "fiscal_risco": -.15, "credito_estresse": -.15, "aversao_risco": -.15, "juros_eua": -.10},
   {"atividade": ("a economia crescendo sustenta lucros, renda e arrecadação", "a economia fraca reduz lucros e renda"),
    "emprego": ("emprego forte sustenta o consumo", "emprego fraco reduz o consumo"),
    "inflacao": ("inflação alta corrói a renda e obriga juros altos por mais tempo", "inflação baixa abre espaço para juros menores"),
    "juro_real": ("juros reais altos encarecem o crédito e o investimento", "juros reais menores estimulam crédito e investimento"),
    "fiscal_risco": ("risco fiscal alto eleva os juros longos e o dólar", "risco fiscal menor reduz o prêmio de risco"),
    "credito_estresse": ("inadimplência e endividamento altos travam o consumo", "crédito saudável sustenta o consumo"),
    "aversao_risco": ("aversão a risco no mundo tira dinheiro de emergentes", "apetite a risco global favorece emergentes"),
    "juros_eua": ("juros americanos altos atraem capital para fora", "juros americanos menores favorecem emergentes")})
_s("mercado_acoes", "Ações em geral (bolsa)", "acao",
   {"juro_real": -.35, "atividade": .30, "fiscal_risco": -.25, "aversao_risco": -.25, "juros_eua": -.15, "emprego": .10, "inflacao": -.15, "cambio": -.10},
   {"juro_real": ("renda fixa competitiva e crédito caro reduzem o valor das ações", "juros reais menores tornam as ações mais atraentes frente à renda fixa"),
    "atividade": ("lucros crescem com a economia aquecida", "lucros sofrem com a economia fraca"),
    "fiscal_risco": ("risco fiscal alto pesa nos preços da bolsa", "risco fiscal menor melhora o apetite por ações"),
    "aversao_risco": ("aversão a risco global pressiona a bolsa", "apetite a risco global favorece a bolsa"),
    "juros_eua": ("juros americanos altos reduzem o apetite por ações", "juros americanos menores ajudam"),
    "emprego": ("emprego forte sustenta o consumo", "emprego fraco pesa no consumo"),
    "inflacao": ("inflação alta mantém os juros altos", "inflação baixa permite juros menores"),
    "cambio": ("dólar alto encarece insumos e dívidas em dólar", "dólar baixo alivia custos")})
_s("bancos", "Bancos", "acao",
   {"credito_estresse": -.45, "atividade": .30, "emprego": .20, "juro_real": .15, "inflacao": -.10},
   {"credito_estresse": ("inadimplência alta eleva as provisões e reduz o lucro", "crédito saudável reduz provisões"),
    "atividade": ("economia forte aumenta a demanda por crédito", "economia fraca reduz a demanda por crédito"),
    "emprego": ("emprego forte melhora a capacidade de pagamento", "emprego fraco aumenta atrasos"),
    "juro_real": ("juros altos ampliam a margem dos empréstimos, mas pesam no risco", "juros menores reduzem a margem"),
    "inflacao": ("inflação alta corrói a renda do tomador", "inflação baixa preserva a renda do tomador")})
_s("construcao", "Construção civil e incorporadoras", "acao",
   {"juro_real": -.35, "juro_tendencia": -.25, "inflacao": -.20, "emprego": .20, "credito_estresse": -.20, "atividade": .15},
   {"juro_real": ("financiamento imobiliário caro reduz as vendas", "financiamento mais barato aquece as vendas"),
    "juro_tendencia": ("juros em alta pioram o crédito imobiliário", "juros em queda melhoram o crédito imobiliário"),
    "inflacao": ("o INCC e a inflação elevam os custos de obra", "custos de obra mais comportados protegem a margem"),
    "emprego": ("emprego forte sustenta a compra de imóveis", "emprego fraco reduz a compra de imóveis"),
    "credito_estresse": ("crédito com estresse restringe financiamentos", "crédito saudável amplia financiamentos"),
    "atividade": ("economia forte aumenta a demanda", "economia fraca reduz a demanda")})
_s("fii_tijolo", "FIIs de tijolo (imóveis físicos)", "fii",
   {"juro_real": -.40, "juro_tendencia": -.25, "atividade": .25, "inflacao": .10, "credito_estresse": -.10},
   {"juro_real": ("juros reais altos deixam a renda fixa mais atraente e pressionam as cotas", "juros reais menores valorizam fundos de imóveis"),
    "juro_tendencia": ("juros em alta pressionam o valor das cotas", "juros em queda tendem a valorizar as cotas"),
    "atividade": ("economia forte sustenta aluguéis e ocupação", "economia fraca aumenta vacância"),
    "inflacao": ("contratos indexados ao IPCA/IGP-M repassam parte da inflação", "menos inflação reduz reajustes de aluguel"),
    "credito_estresse": ("estresse de crédito pesa sobre inquilinos", "crédito saudável ajuda os inquilinos")})
_s("fii_papel", "FIIs de papel (recebíveis e CRIs)", "fii",
   {"juro_real": .30, "juro_tendencia": .20, "inflacao": .25, "credito_estresse": -.35, "fiscal_risco": -.10},
   {"juro_real": ("CRIs pós-fixados rendem mais com juros altos", "juros menores reduzem o rendimento dos novos recebíveis"),
    "juro_tendencia": ("juros em alta elevam o CDI e a renda do fundo", "juros em queda reduzem a renda futura"),
    "inflacao": ("CRIs indexados ao IPCA rendem mais com inflação alta", "inflação menor reduz a correção dos CRIs"),
    "credito_estresse": ("inadimplência alta aumenta o risco de calote dos devedores", "crédito saudável reduz o risco de calote"),
    "fiscal_risco": ("risco fiscal eleva a volatilidade das cotas", "risco fiscal menor reduz a volatilidade")})
_s("fii", "FIIs (geral e híbridos)", "fii",
   {"juro_real": -.15, "juro_tendencia": -.10, "atividade": .20, "credito_estresse": -.20, "inflacao": .10},
   {"juro_real": ("juros reais altos competem com os rendimentos dos fundos", "juros reais menores favorecem os fundos"),
    "juro_tendencia": ("juros em alta pressionam as cotas", "juros em queda favorecem as cotas"),
    "atividade": ("economia forte sustenta ocupação e aluguéis", "economia fraca pressiona ocupação"),
    "credito_estresse": ("estresse de crédito afeta inquilinos e devedores", "crédito saudável ajuda"),
    "inflacao": ("parte dos contratos acompanha a inflação", "menos inflação reduz reajustes")})
_s("varejo", "Varejo", "acao",
   {"juro_real": -.30, "inflacao": -.25, "emprego": .30, "atividade": .25, "credito_estresse": -.20},
   {"juro_real": ("vendas a prazo ficam mais caras e a dívida da empresa pesa", "crédito mais barato impulsiona as vendas"),
    "inflacao": ("inflação alta reduz o poder de compra", "inflação baixa preserva o poder de compra"),
    "emprego": ("emprego e renda fortes sustentam as vendas", "emprego fraco reduz as vendas"),
    "atividade": ("economia forte aquece o consumo", "economia fraca esfria o consumo"),
    "credito_estresse": ("famílias endividadas compram menos", "famílias com crédito saudável compram mais")})
_s("consumo", "Consumo e alimentos", "acao",
   {"emprego": .35, "inflacao": -.30, "atividade": .20, "cambio": -.10, "juro_real": -.10},
   {"emprego": ("emprego forte sustenta o consumo", "emprego fraco reduz o consumo"),
    "inflacao": ("inflação alta corrói a renda e comprime margens", "inflação baixa ajuda renda e margens"),
    "atividade": ("economia forte aumenta o consumo", "economia fraca reduz o consumo"),
    "cambio": ("dólar alto encarece insumos importados", "dólar baixo reduz custos"),
    "juro_real": ("juros altos encarecem o crédito do consumidor", "juros menores ajudam o consumidor")})
_s("energia", "Energia elétrica", "acao",
   {"juro_real": -.30, "inflacao": .20, "atividade": .15, "fiscal_risco": -.15, "juro_tendencia": -.10},
   {"juro_real": ("empresas endividadas e de receita estável perdem valor quando a renda fixa paga mais", "juros menores valorizam receitas estáveis"),
    "inflacao": ("tarifas reajustadas por IPCA/IGP-M repassam a inflação", "menos inflação reduz reajustes"),
    "atividade": ("economia forte aumenta o consumo de energia", "economia fraca reduz o consumo de energia"),
    "fiscal_risco": ("risco fiscal alto pressiona o valor de ativos regulados", "risco fiscal menor ajuda"),
    "juro_tendencia": ("juros em alta pesam na dívida", "juros em queda aliviam a dívida")})
_s("saneamento", "Saneamento", "acao",
   {"juro_real": -.35, "inflacao": .15, "fiscal_risco": -.15, "juro_tendencia": -.15, "atividade": .05},
   {"juro_real": ("investimentos pesados e dívida longa sofrem com juros altos", "juros menores aliviam o custo do investimento"),
    "inflacao": ("tarifas são corrigidas por inflação", "menos inflação reduz reajustes"),
    "fiscal_risco": ("risco fiscal pressiona ativos regulados", "risco fiscal menor ajuda"),
    "juro_tendencia": ("juros em alta pesam na dívida", "juros em queda aliviam a dívida"),
    "atividade": ("economia forte aumenta o consumo", "economia fraca reduz o consumo")})
_s("petroleo", "Petróleo e gás", "acao",
   {"petroleo": .50, "cambio": .30, "aversao_risco": -.10, "atividade": .10},
   {"petroleo": ("petróleo caro eleva a receita do setor", "petróleo barato reduz a receita"),
    "cambio": ("receita em dólar rende mais reais com o dólar alto", "dólar baixo reduz a receita em reais"),
    "aversao_risco": ("aversão a risco pressiona commodities", "apetite a risco favorece commodities"),
    "atividade": ("economia forte aumenta a demanda por combustíveis", "economia fraca reduz a demanda")})
_s("mineracao", "Mineração", "acao",
   {"minerio": .50, "cambio": .30, "aversao_risco": -.10, "atividade": .10},
   {"minerio": ("minério caro eleva a receita", "minério barato reduz a receita"),
    "cambio": ("receita em dólar rende mais reais com o dólar alto", "dólar baixo reduz a receita em reais"),
    "aversao_risco": ("aversão a risco pressiona commodities", "apetite a risco favorece commodities"),
    "atividade": ("economia forte aumenta a demanda por aço", "economia fraca reduz a demanda")})
_s("siderurgia", "Siderurgia", "acao",
   {"atividade": .35, "juro_real": -.20, "cambio": .15, "minerio": -.10, "inflacao": -.10},
   {"atividade": ("construção e indústria aquecidas aumentam a demanda por aço", "economia fraca reduz a demanda por aço"),
    "juro_real": ("juros altos desaceleram obras e investimentos", "juros menores estimulam obras"),
    "cambio": ("dólar alto ajuda exportações e encarece o aço importado", "dólar baixo atrai aço importado"),
    "minerio": ("minério caro eleva o custo de produção", "minério barato reduz o custo"),
    "inflacao": ("inflação eleva custos", "inflação baixa protege margens")})
_s("agro", "Agronegócio", "acao",
   {"cambio": .35, "juro_real": -.25, "atividade": .10, "petroleo": -.10},
   {"cambio": ("receita em dólar rende mais reais", "dólar baixo reduz a receita em reais"),
    "juro_real": ("crédito rural e capital de giro mais caros", "crédito mais barato ajuda"),
    "atividade": ("economia forte sustenta a demanda interna", "economia fraca reduz a demanda interna"),
    "petroleo": ("diesel e fertilizantes mais caros elevam o custo", "custos de insumos menores")})
_s("tecnologia", "Tecnologia e software", "acao",
   {"juro_real": -.35, "juros_eua": -.25, "aversao_risco": -.20, "atividade": .20},
   {"juro_real": ("lucros distantes valem menos com juros altos", "juros menores valorizam lucros futuros"),
    "juros_eua": ("juros americanos altos reduzem o valor de empresas de crescimento", "juros americanos menores ajudam"),
    "aversao_risco": ("aversão a risco castiga empresas de crescimento", "apetite a risco ajuda"),
    "atividade": ("economia forte aumenta gastos de empresas em tecnologia", "economia fraca reduz esses gastos")})
_s("industria", "Indústria e bens de capital", "acao",
   {"atividade": .40, "juro_real": -.25, "credito_estresse": -.15, "inflacao": -.10, "petroleo": -.10},
   {"atividade": ("pedidos e investimentos crescem com a economia aquecida", "pedidos caem com a economia fraca"),
    "juro_real": ("financiamento de máquinas e investimentos fica caro", "financiamento mais barato estimula investimentos"),
    "credito_estresse": ("estresse de crédito reduz encomendas", "crédito saudável sustenta encomendas"),
    "inflacao": ("inflação eleva custos de insumos", "inflação baixa protege margens"),
    "petroleo": ("energia e frete mais caros", "energia e frete mais baratos")})
_s("transporte", "Transporte e logística", "acao",
   {"atividade": .40, "juro_real": -.25, "petroleo": -.20, "credito_estresse": -.10, "cambio": -.05},
   {"atividade": ("mais carga e mais passageiros com a economia aquecida", "menos carga com a economia fraca"),
    "juro_real": ("concessões e frotas financiadas ficam caras", "financiamento mais barato ajuda"),
    "petroleo": ("combustível caro eleva o custo", "combustível barato reduz o custo"),
    "credito_estresse": ("estresse de crédito reduz a demanda", "crédito saudável ajuda"),
    "cambio": ("dólar alto encarece veículos e peças importados", "dólar baixo reduz o custo")})
_s("seguros", "Seguros e serviços financeiros", "acao",
   {"juro_real": .35, "atividade": .25, "credito_estresse": -.20, "inflacao": -.10, "emprego": .10},
   {"juro_real": ("o dinheiro das reservas rende mais com juros altos", "juros menores reduzem o rendimento das reservas"),
    "atividade": ("economia forte aumenta prêmios e negócios", "economia fraca reduz prêmios"),
    "credito_estresse": ("estresse de crédito afeta a carteira", "crédito saudável ajuda"),
    "inflacao": ("inflação encarece sinistros", "inflação baixa reduz sinistros"),
    "emprego": ("emprego forte sustenta a procura por seguros", "emprego fraco reduz a procura")})
_s("telecom", "Telecomunicações", "acao",
   {"juro_real": -.20, "inflacao": .15, "cambio": -.20, "atividade": .15, "emprego": .10},
   {"juro_real": ("dívida e investimentos mais caros", "juros menores aliviam o custo"),
    "inflacao": ("contratos corrigidos por inflação repassam o aumento", "menos inflação reduz reajustes"),
    "cambio": ("equipamentos importados ficam mais caros", "equipamentos mais baratos"),
    "atividade": ("economia forte sustenta consumo de dados e serviços", "economia fraca reduz serviços"),
    "emprego": ("emprego forte sustenta assinaturas", "emprego fraco reduz assinaturas")})
_s("exportadoras", "Exportadoras (papel, celulose, proteínas)", "acao",
   {"cambio": .55, "aversao_risco": -.15, "juros_eua": -.10, "juro_real": -.10},
   {"cambio": ("a receita em dólar rende mais reais", "dólar baixo reduz a receita em reais"),
    "aversao_risco": ("aversão a risco pressiona preços de commodities", "apetite a risco ajuda"),
    "juros_eua": ("juros americanos altos reduzem a demanda global", "juros menores ajudam a demanda global"),
    "juro_real": ("dívida local mais cara", "dívida local mais barata")})
_s("importadoras", "Empresas dependentes de importações", "acao",
   {"cambio": -.50, "inflacao": -.20, "juro_real": -.15, "atividade": .15},
   {"cambio": ("insumos e produtos importados ficam mais caros", "insumos importados mais baratos"),
    "inflacao": ("custos sobem e o repasse é difícil", "custos mais comportados"),
    "juro_real": ("capital de giro mais caro", "capital de giro mais barato"),
    "atividade": ("economia forte aumenta a demanda", "economia fraca reduz a demanda")})
_s("saude", "Saúde", "acao",
   {"emprego": .25, "inflacao": -.25, "atividade": .15, "juro_real": -.15, "cambio": -.15},
   {"emprego": ("emprego formal sustenta planos de saúde", "emprego fraco reduz beneficiários"),
    "inflacao": ("a inflação médica eleva custos", "inflação menor protege margens"),
    "atividade": ("economia forte sustenta a demanda", "economia fraca reduz a demanda"),
    "juro_real": ("expansão e dívida mais caras", "juros menores ajudam"),
    "cambio": ("insumos e equipamentos importados mais caros", "insumos mais baratos")})
_s("educacao", "Educação", "acao",
   {"emprego": .30, "juro_real": -.25, "atividade": .20, "inflacao": -.15, "credito_estresse": -.10},
   {"emprego": ("emprego forte sustenta matrículas", "emprego fraco reduz matrículas"),
    "juro_real": ("financiamento estudantil e dívidas mais caros", "financiamento mais barato"),
    "atividade": ("economia forte aumenta a procura", "economia fraca reduz a procura"),
    "inflacao": ("inflação reduz a renda disponível", "inflação baixa preserva a renda"),
    "credito_estresse": ("estresse de crédito aumenta a inadimplência de mensalidades", "crédito saudável ajuda")})
_s("quimica", "Química", "acao",
   {"atividade": .30, "petroleo": -.25, "cambio": -.15, "juro_real": -.15},
   {"atividade": ("demanda industrial aquecida", "demanda industrial fraca"),
    "petroleo": ("matérias-primas derivadas do petróleo mais caras", "matérias-primas mais baratas"),
    "cambio": ("insumos importados mais caros", "insumos mais baratos"),
    "juro_real": ("investimentos e dívida mais caros", "juros menores ajudam")})
_s("acoes_eua", "Ações dos EUA", "acao",
   {"juros_eua": -.40, "aversao_risco": -.30, "cambio": .20},
   {"juros_eua": ("juros americanos altos reduzem o valor das ações", "juros americanos menores favorecem as ações"),
    "aversao_risco": ("aversão a risco derruba ações", "apetite a risco favorece ações"),
    "cambio": ("com o dólar alto, o retorno em reais de ativos dolarizados aumenta", "com o dólar baixo, o retorno em reais diminui")})
_s("cripto", "Criptomoedas", "cripto",
   {"aversao_risco": -.35, "juros_eua": -.35, "cambio": .10, "juro_real": -.05},
   {"aversao_risco": ("aversão a risco derruba ativos voláteis", "apetite a risco favorece ativos voláteis"),
    "juros_eua": ("juros americanos altos reduzem a liquidez e o apetite por cripto", "juros americanos menores favorecem cripto"),
    "cambio": ("para quem compra em reais, dólar alto aumenta o valor da posição", "dólar baixo reduz o valor em reais"),
    "juro_real": ("renda fixa brasileira competitiva", "renda fixa menos atraente")})
_s("renda_fixa_pos", "Renda fixa pós-fixada (Selic/CDI)", "renda_fixa",
   {"juro_real": .45, "juro_tendencia": .30, "inflacao": .10, "fiscal_risco": -.15},
   {"juro_real": ("o rendimento descontada a inflação é alto", "o ganho acima da inflação diminui"),
    "juro_tendencia": ("juros em alta elevam o rendimento futuro", "juros em queda reduzem o rendimento futuro"),
    "inflacao": ("inflação alta mantém juros altos", "inflação baixa reduz o rendimento"),
    "fiscal_risco": ("risco fiscal aumenta a incerteza sobre os juros", "risco fiscal menor reduz a incerteza")})
_s("renda_fixa_longa", "Renda fixa longa (prefixados e IPCA+)", "renda_fixa",
   {"juro_tendencia": -.40, "juro_real": .30, "fiscal_risco": -.25, "inflacao": -.05},
   {"juro_tendencia": ("juros em alta desvalorizam o título antes do vencimento", "juros em queda valorizam o título antes do vencimento"),
    "juro_real": ("taxas reais altas garantem bom ganho a quem carrega até o vencimento", "taxas reais menores reduzem o ganho de novas compras"),
    "fiscal_risco": ("risco fiscal alto desvaloriza títulos longos", "risco fiscal menor valoriza títulos longos"),
    "inflacao": ("inflação inesperada pesa nos prefixados", "inflação baixa ajuda os prefixados")})

# apelidos dos fatores para o texto "o que poderia mudar"
_MUDA = {"juro_real": "os juros reais", "juro_tendencia": "a trajetória dos juros", "inflacao": "a inflação", "atividade": "o ritmo da economia",
         "emprego": "o mercado de trabalho", "credito_estresse": "o crédito e a inadimplência", "fiscal_risco": "o risco fiscal",
         "cambio": "o dólar", "juros_eua": "os juros dos EUA", "petroleo": "o preço do petróleo", "minerio": "o preço do minério",
         "aversao_risco": "a aversão a risco global"}


# ------------------------------------------------------------------ veredito
def classificar(nota: float, anterior: str | None = None) -> str:
    """BOM/NEUTRO/RUIM com histerese: quem já está em BOM ou RUIM só sai quando a nota recua uma margem além do limite."""
    if anterior == "BOM" and nota >= LIM_BOM - HISTERESE:
        return "BOM"
    if anterior == "RUIM" and nota <= LIM_RUIM + HISTERESE:
        return "RUIM"
    return "BOM" if nota >= LIM_BOM else "RUIM" if nota <= LIM_RUIM else "NEUTRO"


def nivel_confianca(pontos: float) -> str:
    return "Alta" if pontos >= 70 else "Média" if pontos >= 45 else "Baixa"


def _frase_driver(fator: dict, sinal_efeito: float, setor: dict) -> str:
    alto, baixo = setor["mec"].get(fator["id"], ("", ""))
    return alto if fator["valor"] > 0 else baixo


def avaliar(chave: str, fatores: dict, anterior: str | None = None, ajuste: dict | None = None, indicadores: dict | None = None) -> dict:
    """Cenário de UM setor/classe. `ajuste` altera pesos para um ativo específico (ex.: exportadora dentro da indústria)."""
    setor = SETORES[chave]
    pesos = dict(setor["pesos"])
    for k, v in (ajuste or {}).items():
        pesos[k] = pesos.get(k, 0.0) + v
    total = sum(abs(w) for w in pesos.values()) or 1.0
    contrib, usados, faltando = [], 0.0, []
    for fid, w in pesos.items():
        f = fatores.get(fid)
        if not f or f["valor"] is None:
            faltando.append((fid, abs(w)))
            continue
        usados += abs(w)
        contrib.append({"fator": fid, "nome": f["nome"], "peso": round(w, 3), "valor": f["valor"], "efeito": round(w * f["valor"], 4),
                        "texto": f["texto"], "mecanismo": _frase_driver(f, w * f["valor"], {"mec": setor["mec"]})})
    cobertura = usados / total
    if usados == 0:
        return {"chave": chave, "nome": setor["nome"], "classe": setor["classe"], "veredito": "NEUTRO", "nota": 0.0, "confianca": "Baixa", "confianca_pontos": 0,
                "cobertura": 0.0, "mistos": False, "motivo_neutro": "dados insuficientes", "contribuicoes": [], "faltando": [x[0] for x in faltando],
                "favor": [], "contra": [], "riscos": [], "muda": [], "limitacoes": ["Nenhum fator tem dado atual para este setor."]}
    nota = sum(c["efeito"] for c in contrib) / usados
    pos = sum(c["efeito"] for c in contrib if c["efeito"] > 0)
    neg = -sum(c["efeito"] for c in contrib if c["efeito"] < 0)
    consist = 1.0 - (2 * min(pos, neg) / (pos + neg)) if (pos + neg) > 0 else 1.0
    mistos = consist < 0.35 and abs(nota) < 0.35
    ver = classificar(nota, anterior)
    motivo_neutro = ""
    if cobertura < 0.5:
        ver, motivo_neutro = "NEUTRO", "dados insuficientes: menos da metade dos fatores relevantes tem dado atual"
    elif mistos and ver != "NEUTRO":
        ver, motivo_neutro = "NEUTRO", "sinais contraditórios"
    elif ver == "NEUTRO":
        motivo_neutro = "sinais contraditórios" if mistos else "nenhuma direção suficientemente forte"
    qual = sum(fatores[c["fator"]]["qualidade"] * abs(c["peso"]) for c in contrib) / usados
    pontos = 100 * (0.5 * cobertura + 0.2 * qual + 0.3 * consist)
    if cobertura < 0.5:
        pontos = min(pontos, 35)
    contrib.sort(key=lambda c: -abs(c["efeito"]))
    favor = [c for c in contrib if c["efeito"] > 0.02][:4]
    contra = [c for c in contrib if c["efeito"] < -0.02][:4]
    riscos = [c for c in contra if abs(c["valor"]) >= 0.5][:3]
    muda = []
    for c in contrib[:2]:
        f = FATORES[c["fator"]]
        direcao = "recuar" if c["efeito"] > 0 else "melhorar" if c["efeito"] < 0 else "mudar"
        muda.append(f"Uma virada em {_MUDA[c['fator']]} (hoje {'um fator a favor' if c['efeito'] > 0 else 'um fator contra'}) pode {direcao} o quadro deste setor.")
    lim = []
    if faltando:
        nomes = ", ".join(FATORES[f]["nome"].lower() for f, _ in sorted(faltando, key=lambda x: -x[1])[:4])
        lim.append(f"Sem dado atual para: {nomes}.")
    if mistos:
        lim.append("Os sinais se compensam: o resultado é pouco conclusivo.")
    datas = sorted({(indicadores or {})[i]["data"] for c in contrib for i in fatores[c["fator"]]["usa"] if (indicadores or {}).get(i) and (indicadores or {})[i].get("data")})
    return {"chave": chave, "nome": setor["nome"], "classe": setor["classe"], "veredito": ver, "nota": round(nota, 3), "confianca": nivel_confianca(pontos),
            "confianca_pontos": round(pontos), "cobertura": round(cobertura, 2), "consistencia": round(consist, 2), "mistos": mistos, "motivo_neutro": motivo_neutro,
            "contribuicoes": contrib, "faltando": [x[0] for x in faltando], "favor": favor, "contra": contra, "riscos": riscos, "muda": muda,
            "limitacoes": lim, "dados_de": datas[0] if datas else None, "dados_ate": datas[-1] if datas else None}


def calcular(R: dict, anteriores: dict | None = None) -> dict:
    """Foto completa do cenário a partir dos indicadores já resolvidos. `anteriores` = {chave: veredito} para a histerese."""
    anteriores = anteriores or {}
    fatores = calcular_fatores(R)
    cen = {k: avaliar(k, fatores, anteriores.get(k), indicadores=R) for k in SETORES}
    cob = MF.cobertura(R)
    datas = [r["data"] for r in R.values() if r.get("data") and r["status"] != "indisponivel"]
    return {"fatores": fatores, "cenarios": cen, "cobertura": cob, "dados_ate": max(datas) if datas else None,
            "dados_desde": min(datas) if datas else None}


def beneficiados_e_pressionados(cen: dict) -> tuple[list, list]:
    """Setores com cenário BOM / RUIM, do mais forte ao mais fraco (ignora 'geral' e classes sem dado suficiente)."""
    itens = [c for k, c in cen.items() if k != "geral" and not (c["veredito"] == "NEUTRO" and c.get("motivo_neutro", "").startswith("dados insuf"))]
    bons = sorted([c for c in itens if c["veredito"] == "BOM"], key=lambda c: -c["nota"])
    ruins = sorted([c for c in itens if c["veredito"] == "RUIM"], key=lambda c: c["nota"])
    return bons, ruins


def snapshot_vereditos(cen: dict) -> dict:
    """Parte pequena do cenário, para guardar entre execuções (histerese e detecção de mudança)."""
    return {k: {"v": c["veredito"], "nota": c["nota"], "conf": c["confianca"]} for k, c in cen.items()}


def texto_geral(c: dict, modo: str = "intermediario") -> str:
    """Frase-resumo do cenário geral, no nível de profundidade do usuário."""
    v = c["veredito"]
    base = {"BOM": "O conjunto dos indicadores mostra condições relativamente favoráveis para a economia brasileira.",
            "NEUTRO": "Os indicadores dão sinais mistos, sem uma direção forte para a economia brasileira.",
            "RUIM": "O conjunto dos indicadores mostra condições relativamente desfavoráveis para a economia brasileira."}[v]
    if c.get("motivo_neutro", "").startswith("dados insuf"):
        base = "Faltam dados atuais para uma leitura segura da economia brasileira."
    if modo == "iniciante":
        return base + " Isso descreve o ambiente, não diz se uma ação vai subir ou cair."
    extra = f" Nota {_pp(c['nota'], 2)} (de −1 a +1); confiança {c['confianca'].lower()} ({c['confianca_pontos']}/100)."
    return base + (extra if modo == "avancado" else f" Confiança da análise: {c['confianca'].lower()}.")
