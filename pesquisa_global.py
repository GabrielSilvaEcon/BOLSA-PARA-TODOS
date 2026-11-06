"""Pesquisa global do menu lateral (módulo puro, sem Streamlit).

Procura em TRÊS grupos que nunca se misturam na mesma lista:
 · Páginas e ferramentas: título da página e palavras parecidas (SINONIMOS); mostra o grupo do menu onde ela fica.
 · Ajuda e termos: termos do glossário (sigla, nome, apelidos) e tutoriais de página.
 · Ativos: se o texto parece um ativo (ticker, CNPJ, código de título, ou uma palavra só), oferece UM botão que leva à busca universal do Início.
Só usa páginas e textos que já existem no app.
"""
from __future__ import annotations

import re
import unicodedata

import busca_universal as BU

# url_path -> grupo do menu onde a página mora (precisa bater com menu_navegacao; um teste confere)
GRUPO = {
    "inicio": "Início", "notificacoes": "Alertas",
    "preco-justo": "Analisar › Ações", "valuation": "Analisar › Ações", "dividendos": "Analisar › Ações", "micro": "Analisar › Ações",
    "dcf": "Analisar › Ações", "tecnica": "Analisar › Ações", "stock-picking": "Analisar › Ações",
    "fiis": "Analisar › FIIs", "etfs": "Analisar › Fundos e ETFs", "fundos-acoes": "Analisar › Fundos e ETFs",
    "multimercados": "Analisar › Fundos e ETFs", "fundos-renda-fixa": "Analisar › Fundos e ETFs", "renda-fixa": "Analisar › Renda fixa",
    "criptomoedas": "Analisar › Criptomoedas", "cripto-onchain": "Analisar › Criptomoedas", "cripto-receitas": "Analisar › Criptomoedas",
    "cripto-fundamentalista": "Analisar › Criptomoedas", "cripto-avancada": "Analisar › Criptomoedas", "tecnica-cripto": "Analisar › Criptomoedas",
    "comparar": "Ferramentas de análise", "evolucao": "Ferramentas de análise", "tecnica-avancada": "Ferramentas de análise",
    "inteligencia": "Ferramentas de análise",
    "carteira": "Minha carteira", "gestao-carteira": "Minha carteira", "risco": "Minha carteira", "relatorios": "Minha carteira",
    "macro": "Mercado e economia", "noticias": "Mercado e economia",
    "simulador": "Calculadoras e simuladores", "calculadoras": "Calculadoras e simuladores", "tesouro-cdi": "Calculadoras e simuladores",
    "educacao": "Aprender e ajuda", "ajuda": "Aprender e ajuda",
    "conta": "Configurações", "planos": "Configurações", "administracao": "Administração",
}

# palavras que as pessoas usam e que não estão no título
SINONIMOS = {
    "preco-justo": "graham bazin valor justo barato caro margem de seguranca",
    "valuation": "multiplos p/l p/vp pl pvp ev ebitda",
    "dividendos": "proventos yield renda passiva",
    "micro": "balanco divida lucro roe margem endividamento",
    "dcf": "fluxo de caixa descontado valor intrinseco",
    "tecnica": "grafico candle media movel rsi macd tendencia",
    "tecnica-avancada": "indicadores bandas bollinger suporte resistencia",
    "fiis": "fundos imobiliarios aluguel tijolo papel",
    "etfs": "indice bova11 ivvb11 fundo de indice",
    "fundos-acoes": "fundo de acoes cvm cnpj",
    "multimercados": "fundo multimercado cvm cnpj",
    "fundos-renda-fixa": "fundo de renda fixa cvm cnpj di",
    "renda-fixa": "cdb lci lca debenture titulos tesouro direto cri cra",
    "tesouro-cdi": "simulacao aportes ir regressivo cdi selic",
    "criptomoedas": "bitcoin ethereum cripto tokenomics token moeda digital",
    "cripto-onchain": "on-chain adocao enderecos",
    "comparar": "comparacao lado a lado versus",
    "evolucao": "crescimento cagr balancos historico",
    "inteligencia": "oportunidades riscos sinais assistente ia",
    "notificacoes": "alertas avisos notificacoes preco indicadores",
    "carteira": "posicoes patrimonio meus investimentos",
    "gestao-carteira": "alocacao rebalanceamento diversificacao",
    "risco": "volatilidade drawdown var concentracao",
    "relatorios": "dashboard relatorio exportar",
    "macro": "economia selic ipca juros inflacao pib dolar cambio",
    "noticias": "eventos noticia manchetes",
    "simulador": "simular aposentadoria juros compostos",
    "calculadoras": "calculadora conta",
    "educacao": "aprender curso trilha",
    "ajuda": "tutorial diagnostico fontes termos glossario",
    "conta": "perfil senha cadastro nivel conhecimento sair",
    "planos": "assinatura plano pagar premium plus gratuito",
}


def norm(s) -> str:
    s = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9/]+", " ", s).strip()


def _pontos(consulta: str, titulo: str, extra: str = "") -> int:
    """0 = não combina. Maior = mais relevante (título exato > começa com > contém > todas as palavras > só nos sinônimos)."""
    q, t, e = norm(consulta), norm(titulo), norm(extra)
    if not q:
        return 0
    if t == q:
        return 100
    if t.startswith(q):
        return 80
    if q in t:
        return 60
    palavras = [p for p in q.split() if len(p) >= 2]
    if not palavras:
        return 0
    if all(p in t or p in e.split() or p in e for p in palavras):
        return 40 if all(p in t for p in palavras) else 20
    return 0


def buscar_paginas(consulta: str, paginas: dict, limite: int = 6) -> list[dict]:
    """paginas: {url_path: título}. Devolve [{'url','titulo','grupo'}] da mais para a menos relevante."""
    achados = []
    for url, titulo in paginas.items():
        p = _pontos(consulta, titulo, SINONIMOS.get(url, ""))
        if p:
            achados.append((p, titulo, {"url": url, "titulo": titulo, "grupo": GRUPO.get(url, "")}))
    achados.sort(key=lambda x: (-x[0], x[1]))
    return [a[2] for a in achados[:limite]]


def buscar_ajuda(consulta: str, termos: list[dict], tutoriais: dict, limite: int = 5) -> list[dict]:
    """Termos do glossário (tipo 'termo') e tutoriais de página (tipo 'tutorial', com url da página)."""
    achados = []
    for t in termos or []:
        nomes = " ".join([t.get("sigla", ""), t.get("pt", ""), t.get("en", ""), *(t.get("alias") or [])])
        p = _pontos(consulta, t.get("sigla", "") + " " + t.get("pt", ""), nomes)
        if p:
            achados.append((p, {"tipo": "termo", "titulo": f"{t.get('sigla', '')} · {t.get('pt', '')}".strip(" ·"),
                                "texto": t.get("iniciante") or t.get("definicao") or ""}))
    for url, tu in (tutoriais or {}).items():
        p = _pontos(consulta, "tutorial " + tu.get("titulo", ""), tu.get("busca", ""))
        if p and norm(consulta) not in ("tutorial",):
            achados.append((p - 5, {"tipo": "tutorial", "titulo": f"Tutorial: {tu.get('titulo', '')}", "url": url, "texto": ""}))
    achados.sort(key=lambda x: (-x[0], x[1]["titulo"]))
    return [a[1] for a in achados[:limite]]


def buscar_ativo(consulta: str, catalogo=(), eh_fii=None, ha_resultado: bool = False) -> dict | None:
    """Um único botão 'Analisar …' quando o texto parece ativo. Texto livre (nome de empresa, ticker dos EUA) só vira botão se nada mais foi encontrado
    (evita oferecer 'Buscar risco como empresa')."""
    q = (consulta or "").strip()
    if len(q) < 2:
        return None
    r = BU.interpretar(q, catalogo, eh_fii)
    if r["classe"] is None:
        return {"texto": q, "rotulo": r.get("aviso") or "", "reconhecido": False, "aviso": r.get("aviso")}
    if r["classe"] == "texto":
        if ha_resultado:
            return None
        return {"texto": q, "rotulo": f"Buscar “{q}” como empresa", "reconhecido": False, "aviso": None}
    return {"texto": q, "rotulo": f"Analisar {r['codigo']} ({BU.ROTULO_CLASSE[r['classe']]})", "reconhecido": True, "aviso": None}


def pesquisar(consulta: str, paginas: dict, termos: list[dict], tutoriais: dict, catalogo=(), eh_fii=None) -> dict:
    """{'paginas': [...], 'ajuda': [...], 'ativo': {...}|None}. Consulta vazia ou de 1 letra → tudo vazio."""
    q = (consulta or "").strip()
    if len(q) < 2:
        return {"paginas": [], "ajuda": [], "ativo": None}
    pgs = buscar_paginas(q, paginas)
    aj = buscar_ajuda(q, termos, tutoriais)
    return {"paginas": pgs, "ajuda": aj, "ativo": buscar_ativo(q, catalogo, eh_fii, ha_resultado=bool(pgs or aj))}
