"""Perfil macroeconômico de cada ativo: em qual setor/classe ele se encaixa e a que fatores da economia ele é sensível.

Puro (sem Streamlit e sem rede). O perfil complementa a análise individual do ativo e NUNCA a substitui: um cenário favorável não torna
uma ação barata, e um cenário desfavorável não manda vender. Quando o ativo não tem perfil próprio, usa-se o do setor e isso é dito
("perfil estimado do setor"). Quando não se sabe o setor, o ativo fica sem classificação em vez de receber uma sensibilidade inventada.
"""
from __future__ import annotations

import re

import macro_cenario as MC

# setor do catálogo do app (recursos.py) -> chave de setor macro
SETOR_RECURSOS = {
    "Agronegócio": "agro", "Alimentos e Bebidas": "consumo", "Bancos": "bancos", "Construção e Imobiliário": "construcao", "Consumo": "consumo",
    "Educação": "educacao", "Energia Elétrica": "energia", "Indústria e Bens de Capital": "industria", "Mineração e Siderurgia": "mineracao",
    "Papel e Celulose": "exportadoras", "Petróleo e Gás": "petroleo", "Química": "quimica", "Saneamento": "saneamento", "Saúde": "saude",
    "Seguros e Serviços Financeiros": "seguros", "Telecom e Tecnologia": "telecom", "Transporte e Logística": "transporte", "Varejo": "varejo",
    "Ações dos EUA": "acoes_eua",
}

# Perfis próprios (empresas conhecidas). `ajuste` soma/subtrai pesos do setor; `why` explica em linguagem simples, com fatos gerais e estáveis.
PERFIS: dict[str, dict] = {}


def _p(tickers: str, setor: str, why: str, ajuste: dict | None = None):
    for t in tickers.split():
        PERFIS[t] = {"setor": setor, "why": why, "ajuste": ajuste or {}}


_p("PETR4 PETR3", "petroleo", "Receita ligada ao petróleo e ao dólar; a política de preços dos combustíveis e a dívida também pesam.")
_p("PRIO3 BRAV3", "petroleo", "Produtora de petróleo: a receita acompanha o preço do barril e o dólar.", {"petroleo": .15})
_p("VBBR3 UGPA3", "petroleo", "Distribuidora de combustíveis: ganha com volume e margem, e é menos exposta ao preço do barril do que as produtoras.", {"petroleo": -.35, "cambio": -.20, "atividade": .30})
_p("VALE3 CMIN3", "mineracao", "Receita principalmente em dólar, com exportação de minério de ferro.")
_p("CSNA3 GGBR4 USIM5 GOAU4", "siderurgia", "Siderúrgica: demanda de construção e indústria e custo de matérias-primas.")
_p("SUZB3 KLBN11", "exportadoras", "Celulose e papel: grande parte da receita vem das exportações, em dólar.")
_p("JBSS3 MRFG3 BRFS3 BEEF3", "exportadoras", "Proteínas: parte relevante das vendas é exportada, em dólar; o milho e a soja entram como custo.", {"juro_real": -.05, "inflacao": -.10})
_p("ITUB4 BBDC4 BBDC3 BBAS3 SANB11 BPAC11 ABCB4 BRSR6 BMGB4", "bancos", "Banco: o lucro depende de crédito concedido, inadimplência e atividade.")
_p("BBSE3 CXSE3 PSSA3 IRBR3 B3SA3", "seguros", "Seguros e mercado financeiro: renda sobre reservas e volume de negócios.")
_p("WEGE3", "industria", "Indústria de bens de capital com forte presença no exterior: o dólar costuma ajudar a receita.", {"cambio": .30})
_p("MGLU3 LREN3 AMER3 CASH3 ARZZ3 PETZ3 SOMA3 GUAR3 CEAB3", "varejo", "Varejo de bens de consumo, muitas vezes vendidos a prazo: sensível à renda, ao emprego e ao custo do crédito.")
_p("MGLU3 AMER3 CASH3 CVCB3", "varejo", "Varejo de bens duráveis ou serviços financiados: muito sensível a juros e crédito.", {"juro_real": -.15, "credito_estresse": -.10})
_p("ABEV3 NTCO3 MDIA3 CAML3", "consumo", "Consumo básico: depende da renda das famílias e dos custos de insumos.")
_p("CYRE3 MRVE3 EZTC3 DIRR3 TEND3 CURY3 PLPL3 JHSF3 EVEN3", "construcao", "Incorporadora: vendas dependem de crédito imobiliário e emprego; custos acompanham o INCC.")
_p("MRVE3 TEND3 CURY3 PLPL3 DIRR3", "construcao", "Incorporadora focada em imóveis econômicos: muito ligada ao crédito e à renda das famílias de menor renda.", {"juro_real": -.05, "emprego": .10})
_p("EQTL3 CPFE3 TAEE11 CMIG4 CMIG3 ENGI11 NEOE3 CPLE6 AURE3 AXIA3 AXIA6 ELET3 ELET6 EGIE3 ENEV3 ALUP11 TRPL4 CPLE3", "energia",
   "Energia elétrica: receitas reguladas e reajustadas por inflação, com dívida longa e investimentos pesados.")
_p("SBSP3 SAPR11 CSMG3 SAPR4", "saneamento", "Saneamento: concessões reguladas, investimentos elevados e dívida longa.")
_p("RADL3 RDOR3 HAPV3 FLRY3 HYPE3 ONCO3 QUAL3 MATD3", "saude", "Saúde: custos médicos e emprego formal (planos) pesam no resultado.")
_p("VIVT3 TIMS3", "telecom", "Telecomunicações: receita recorrente reajustada por inflação e investimento em equipamentos.")
_p("TOTS3 LWSA3 INTB3", "tecnologia", "Tecnologia: empresas de crescimento, cujo valor reage mais aos juros.")
_p("RAIL3 CCRO3 ECOR3 RENT3 MOVI3 LCAM3 STBP3 AZUL4 GOLL4 HBSA3 PORT3", "transporte", "Transporte e logística: ligado à atividade, ao combustível e ao custo do capital.")
_p("AZUL4 GOLL4", "transporte", "Aéreas: combustível e dívida em dólar pesam no resultado.", {"cambio": -.30, "petroleo": -.20})
_p("SLCE3 AGRO3 SMTO3 RAIZ4 CSAN3", "agro", "Agronegócio e açúcar/etanol: receita ligada a commodities e ao dólar.")
_p("DXCO3 UNIP6 BRKM5 VITT3", "quimica", "Química e materiais: demanda industrial e matérias-primas ligadas ao petróleo.")
_p("COGN3 YDUQ3 ANIM3 SEER3", "educacao", "Educação: renda das famílias, emprego e crédito estudantil.")

CLASSES_ROTULO = {"acao": "Ação", "fii": "FII", "etf": "ETF", "cripto": "Criptomoeda", "renda_fixa": "Renda fixa", "fundo": "Fundo"}

_RE_FII = re.compile(r"^[A-Z]{4}1[1-3]$")
_PAPEL = {"KNCR11", "KNIP11", "KNHY11", "MXRF11", "CPTS11", "RBRR11", "HABT11", "VGIR11", "RECR11", "IRDM11", "VCRI11", "BCRI11", "RZAK11", "JSAF11", "PORD11", "KFOF11"}
_ETF_BR = {"BOVA11", "IVVB11", "SMAL11", "DIVO11", "FIND11", "MATB11", "GOLD11", "HASH11", "BOVV11", "BOVB11", "ECOO11", "XFIX11", "IMAB11", "IB5M11", "FIXA11"}
_ETF_EUA = {"SPY", "QQQ", "VOO", "VTI", "IVV", "DIA", "IWM", "VT", "VEA", "VWO", "EWZ", "SCHD", "VNQ", "ARKK", "XLK", "XLF", "XLE"}


def classe_do_ativo(tk: str, info: dict | None = None) -> str:
    """'acao' | 'fii' | 'etf' | 'cripto'. Não adivinha 'renda_fixa' nem 'fundo' (têm carteiras próprias)."""
    tk = str(tk or "").upper().replace(".SA", "").strip()
    if tk.endswith("-USD") or tk.endswith("-USDT"):
        return "cripto"
    if tk in _ETF_BR or tk in _ETF_EUA:
        return "etf"
    setor = str((info or {}).get("setor") or "").lower()
    if "etf" in setor:
        return "etf"
    if "imobili" in setor and "constru" not in setor or tk in _PAPEL:
        return "fii"
    if _RE_FII.match(tk) and tk not in PERFIS and not info:
        return "fii"
    return "acao"


def setor_macro(tk: str, classe: str, info: dict | None = None) -> tuple[str | None, str, str]:
    """(chave do setor macro, justificativa, origem: 'perfil próprio' | 'setor' | 'classe' | 'sem classificação')."""
    tk = str(tk or "").upper().replace(".SA", "").strip()
    if classe == "cripto":
        return "cripto", "Criptomoedas reagem sobretudo à liquidez global, aos juros americanos e ao apetite a risco.", "classe"
    if classe == "fii":
        if tk in _PAPEL:
            return "fii_papel", "Fundo de papel: investe em recebíveis (CRIs), pós-fixados ou indexados à inflação.", "classe"
        return "fii", "FII sem segmento identificado: usa-se o perfil geral de fundos imobiliários (tijolo e papel misturados).", "classe"
    if classe == "etf":
        if tk in _ETF_EUA or tk in {"IVVB11"}:
            return "acoes_eua", "ETF que replica ações dos EUA: segue os juros americanos e o apetite a risco global.", "classe"
        if tk in {"IMAB11", "IB5M11", "FIXA11", "XFIX11"}:
            return "renda_fixa_longa", "ETF de renda fixa: o preço das cotas reage a juros e inflação.", "classe"
        return "mercado_acoes", "ETF de ações brasileiras: reage ao ambiente geral da bolsa.", "classe"
    p = PERFIS.get(tk)
    if p:
        return p["setor"], p["why"], "perfil próprio"
    setor = SETOR_RECURSOS.get(str((info or {}).get("setor") or ""))
    if setor:
        return setor, f"Perfil estimado a partir do setor ({SETORES_ROT.get(setor, setor)}); a empresa pode fugir do padrão do setor.", "setor"
    return None, "Setor não identificado: sem classificação macroeconômica para este ativo.", "sem classificação"


SETORES_ROT = {k: v["nome"] for k, v in MC.SETORES.items()}


def ajuste_do_ativo(tk: str) -> dict:
    p = PERFIS.get(str(tk or "").upper().replace(".SA", "").strip())
    return dict(p["ajuste"]) if p else {}


def _faixa(x: float) -> str:
    x = abs(x)
    return "Alta" if x >= 0.40 else "Média" if x >= 0.20 else "Baixa"


def sensibilidades(chave: str, ajuste: dict | None = None, div_pl: float | None = None) -> dict:
    """Tabela de sensibilidades (juros, inflação, câmbio, crédito, consumo, commodities, endividamento) derivada dos pesos do setor."""
    pesos = dict(MC.SETORES[chave]["pesos"])
    for k, v in (ajuste or {}).items():
        pesos[k] = pesos.get(k, 0.0) + v
    g = lambda *ks: sum(pesos.get(k, 0.0) for k in ks)
    def linha(x, pior_quando_alto, melhor_quando_alto):
        if abs(x) < 0.05:
            return {"nivel": "Baixa", "sentido": "pouco afetado"}
        return {"nivel": _faixa(x), "sentido": melhor_quando_alto if x > 0 else pior_quando_alto}
    consumo = g("emprego", "atividade")
    comm = g("petroleo", "minerio")
    s = {
        "Juros": linha(g("juro_real", "juro_tendencia"), "prejudicado por juros altos", "favorecido por juros altos"),
        "Inflação": linha(g("inflacao"), "prejudicado por inflação alta", "protegido pela inflação (reajustes)"),
        "Câmbio": linha(g("cambio"), "prejudicado por dólar alto", "favorecido por dólar alto"),
        "Crédito": linha(g("credito_estresse"), "prejudicado por estresse de crédito", "favorecido por estresse de crédito"),
        "Consumo e atividade": linha(consumo, "prejudicado por economia forte", "favorecido por economia e consumo fortes"),
        "Commodities": linha(comm, "prejudicado por commodities caras", "favorecido por commodities caras"),
    }
    if div_pl is None:
        s["Endividamento"] = {"nivel": "n/d", "sentido": "dado da empresa não carregado"}
    else:
        s["Endividamento"] = {"nivel": "Alta" if div_pl >= 2 else "Média" if div_pl >= 1 else "Baixa", "sentido": f"dívida líquida de {div_pl:.1f}x o patrimônio".replace(".", ",")}
    return s


def perfil(tk: str, info: dict | None = None, classe: str | None = None, div_pl: float | None = None) -> dict:
    tk = str(tk or "").upper().replace(".SA", "").strip()
    cl = classe or classe_do_ativo(tk, info)
    chave, why, origem = setor_macro(tk, cl, info)
    out = {"ticker": tk, "classe": cl, "classe_rotulo": CLASSES_ROTULO.get(cl, cl), "setor_chave": chave, "setor": SETORES_ROT.get(chave, "Sem classificação"),
           "origem": origem, "justificativa": why, "ajuste": ajuste_do_ativo(tk) if origem == "perfil próprio" else {}}
    if chave:
        ajuste = dict(out["ajuste"])
        if div_pl is not None and div_pl >= 2.0:
            ajuste["juro_real"] = ajuste.get("juro_real", 0.0) - 0.10        # dívida alta: mais sensível a juros (regra explícita e informada ao usuário)
            out["justificativa"] += f" A dívida líquida alta ({div_pl:.1f}x o patrimônio) aumenta a sensibilidade a juros.".replace(".", ",")
        out["ajuste"] = ajuste
        out["sens"] = sensibilidades(chave, ajuste, div_pl)
    return out


def posicoes_reais(dados: dict) -> list[dict]:
    """Posições da carteira REAL de uma conta (nunca a fictícia). `dados` = dados salvos da conta (chaves cart_real e cart_rf).
    Devolve [{ativo, classe, qtd}] para ações/FIIs/ETFs/cripto e [{ativo, classe:'renda_fixa', setor_chave}] para renda fixa."""
    dados = dados or {}
    soma: dict = {}
    for l in dados.get("cart_real") or []:
        try:
            tk, q = str(l["ticker"]).upper().replace(".SA", ""), float(l["qtd"])
        except (KeyError, TypeError, ValueError):
            continue
        if q > 0:
            soma[tk] = soma.get(tk, 0.0) + q
    out = [{"ativo": tk, "classe": classe_do_ativo(tk), "qtd": q} for tk, q in soma.items()]
    vistos = set()
    for d in dados.get("cart_rf") or []:
        if not isinstance(d, dict):
            continue
        idx = str(d.get("indexador") or "")
        chave = "renda_fixa_pos" if idx in ("cdi_pct", "cdi_mais", "selic") else "renda_fixa_longa" if idx in ("pre", "ipca") else None
        nome = str(d.get("emissor") or d.get("nome") or d.get("tipo") or "Título")[:40]
        if chave and (nome, chave) not in vistos:
            vistos.add((nome, chave))
            out.append({"ativo": f"RF·{nome}".upper(), "classe": "renda_fixa", "qtd": 1.0, "setor_chave": chave})
    return out
