"""Três profundidades de análise (Essencial · Detalhada · Aprofundada) e menu por nível de conhecimento. Módulo puro (sem Streamlit).

Só muda QUANTO aparece: nenhum cálculo, dado, carteira ou alerta é alterado. A profundidade padrão acompanha o nível da pessoa
(Iniciante → Essencial, Intermediário → Detalhada, Avançado → Aprofundada) e ela troca quando quiser.
"""
from __future__ import annotations

PROFUNDIDADES = ("rapida", "mediana", "completa")
ROTULOS = {"rapida": "Essencial", "mediana": "Detalhada", "completa": "Aprofundada"}   # só os nomes mudaram; os códigos internos seguem iguais
DESCRICAO = {
    "rapida": "Veredito, preço atual, preço justo e principais informações.",
    "mediana": "Fundamentos, indicadores, riscos e comparações relevantes.",
    "completa": "Análise completa, histórico, gráficos, cálculos e indicadores avançados.",
}
_PADRAO = {"iniciante": "rapida", "intermediario": "mediana", "avancado": "completa"}


def padrao_do_modo(modo: str) -> str:
    return _PADRAO.get(modo, "mediana")


def normalizar(escolha, modo: str) -> str:
    """Profundidade válida: a escolhida, ou a padrão do nível quando não há escolha (ou ela é inválida)."""
    return escolha if isinstance(escolha, str) and escolha in PROFUNDIDADES else padrao_do_modo(modo)


def blocos_inicio(prof: str) -> dict:
    """O que o Início das ações mostra em cada profundidade."""
    p = prof if prof in PROFUNDIDADES else "mediana"
    return {
        "leitura": True,                                   # veredito em texto de cada empresa
        "resumo_ia": p != "rapida",                        # resumo executivo
        "cartoes": p != "rapida",                          # cartões de preço justo, múltiplos, saúde, dividendos, DCF
        "atalhos": p != "rapida",                          # comparar, evolução, central de inteligência
        "intel": p == "completa",                          # sinais e notícias da empresa
        "abas": p == "completa",                           # as 5 análises completas, em abas
        "dcf": p == "completa",                            # cartão do fluxo de caixa só na completa
        "max_empresas": 3 if p == "rapida" else 4,
    }


# ---------------------------------------------------------------- leitura rápida de uma empresa
def _margem(justo, preco):
    return None if not justo or not preco or justo <= 0 else (justo - preco) / justo * 100


def leitura_rapida(nome: str, preco, graham, bazin, margem_alvo: float, roe=None, margem_liq=None, div_pl=None, financeira: bool = False,
                   dy=None, modo: str = "iniciante") -> dict:
    """Veredito curto de uma empresa, só com o que o app já calcula (preço justo por Graham e Bazin + saúde).
    Devolve: nivel (bom/ok/ruim/na), selo, frase, preco, justo, motivo, risco, confianca. Nunca recomenda compra ou venda."""
    modo = modo if modo in _PADRAO else "intermediario"
    justos = [j for j in (graham, bazin) if j is not None and j > 0]
    margens = [m for m in (_margem(j, preco) for j in justos) if m is not None]
    # saúde: mesma regra dos cartões do Início
    ind = [roe is not None and roe >= 10, margem_liq is not None and margem_liq >= 8, financeira or div_pl is None or div_pl <= 100]
    tem_saude = roe is not None or margem_liq is not None
    saude = None if not tem_saude else {3: "sólida", 2: "moderada"}.get(sum(ind), "frágil")
    # risco principal (o mais relevante, em palavras)
    if not financeira and div_pl is not None and div_pl > 150:
        risco = "A dívida da empresa é alta perto do patrimônio dela."
    elif margem_liq is not None and margem_liq < 0:
        risco = "A empresa está dando prejuízo."
    elif roe is not None and roe < 5:
        risco = "O lucro é baixo perto do patrimônio da empresa."
    elif saude == "frágil":
        risco = "Os números de saúde financeira estão fracos."
    elif not dy and bazin is None:
        risco = "A empresa paga pouco ou nenhum dividendo, então só uma das contas se aplica."
    else:
        risco = "Nenhum sinal forte de risco nos dados usados, mas dados passados não garantem o futuro."
    if not margens or preco is None:
        return {"nivel": "na", "selo": "Sem veredito", "preco": preco, "justo": None, "saude": saude, "risco": risco, "confianca": "Baixa",
                "motivo": "Não foi possível calcular um preço justo (a empresa pode ter prejuízo ou não pagar dividendos).",
                "frase": f"Não deu para calcular um preço justo para {nome} com os dados disponíveis. Veja a saúde financeira e as outras análises."}
    media = sum(margens) / len(margens)
    nivel = "bom" if media >= margem_alvo else ("ok" if media >= 0 else "ruim")
    justo = sum(justos) / len(justos)
    selo = {"bom": "Abaixo do preço justo", "ok": "Perto do preço justo", "ruim": "Acima do preço justo"}[nivel]
    conf = "Alta" if len(margens) == 2 and saude else ("Média" if len(margens) == 2 or saude else "Baixa")
    metodos = "as duas contas (Graham e Bazin)" if len(margens) == 2 else "uma conta (Graham ou Bazin; a outra não se aplica)"
    if modo == "iniciante":
        frase = {"bom": f"Pelas nossas contas, a ação de {nome} está mais barata do que parece valer. É um motivo para estudar melhor a empresa, não uma ordem de compra.",
                 "ok": f"Pelas nossas contas, o preço de {nome} está perto do que a ação parece valer: nem barata, nem cara.",
                 "ruim": f"Pelas nossas contas, a ação de {nome} está mais cara do que parece valer. Pagar mais que o valor justo deixa você mais exposto a perdas."}[nivel]
        motivo = f"Comparamos o preço de hoje com o que a empresa ganha, tem e distribui, usando {metodos}."
    elif modo == "intermediario":
        frase = (f"{nome}: preço {selo.lower()} (margem média {media:.0f}% contra alvo de {margem_alvo:.0f}%)."
                 + (f" Saúde financeira {saude}." if saude else ""))
        motivo = f"Margem média entre {len(margens)} método(s) de preço justo; saúde pelo ROE, margem líquida e dívida."
    else:
        frase = (f"{nome}: margem média {media:.1f}% ({len(margens)} método(s)), alvo do perfil {margem_alvo:.0f}%"
                 + (f"; ROE {roe:.1f}%" if roe is not None else "") + (f"; margem líq. {margem_liq:.1f}%" if margem_liq is not None else "")
                 + (f"; Dív./PL {div_pl:.0f}%" if div_pl is not None and not financeira else "") + ".")
        motivo = "Margem = (justo − preço) ÷ justo, média dos métodos aplicáveis; Graham e Bazin usam dados passados e ignoram o setor."
    return {"nivel": nivel, "selo": selo, "frase": frase, "preco": preco, "justo": justo, "saude": saude, "risco": risco,
            "confianca": conf, "motivo": motivo, "margem": media}


# ---------------------------------------------------------------- menu por nível
# nível mínimo para a página aparecer no menu (a página continua existindo e funcionando em qualquer nível)
MENU_MIN = {
    "inicio": "iniciante", "carteira": "iniciante", "comparar": "iniciante", "preco-justo": "iniciante", "valuation": "iniciante",
    "dividendos": "iniciante", "micro": "iniciante", "fiis": "iniciante", "etfs": "iniciante", "renda-fixa": "iniciante",
    "tesouro-cdi": "iniciante", "criptomoedas": "iniciante", "macro": "iniciante", "noticias": "iniciante", "notificacoes": "iniciante",
    "simulador": "iniciante", "calculadoras": "iniciante", "educacao": "iniciante", "ajuda": "iniciante", "conta": "iniciante", "planos": "iniciante",
    "administracao": "iniciante",
    "dcf": "intermediario", "tecnica": "intermediario", "gestao-carteira": "intermediario", "relatorios": "intermediario",
    "fundos-acoes": "intermediario", "multimercados": "intermediario", "fundos-renda-fixa": "intermediario", "cripto-onchain": "intermediario",
    "tecnica-cripto": "intermediario", "inteligencia": "intermediario",
    "tecnica-avancada": "avancado", "risco": "avancado", "evolucao": "avancado", "cripto-receitas": "avancado",
    "cripto-fundamentalista": "avancado", "cripto-avancada": "avancado",
}
# Páginas sugeridas para COMEÇAR em cada nível (só destaque no menu; nenhuma página é escondida).
SUGERIDAS = {
    "iniciante": ("preco-justo", "carteira", "macro", "educacao"),
    "intermediario": ("valuation", "comparar", "gestao-carteira", "noticias"),
    "avancado": ("tecnica-avancada", "risco", "inteligencia", "evolucao"),
}


def sugeridas(modo: str) -> frozenset:
    return frozenset(SUGERIDAS.get(modo, ()))


_ORDEM = {"iniciante": 0, "intermediario": 1, "avancado": 2}


def visivel_no_menu(url_path: str, modo: str, ver_todas: bool = False, pagina_atual: str = "") -> bool:
    """A página aparece no menu? Sempre aparece quando é a página aberta, quando a pessoa pediu 'ver todas' ou quando não é classificada."""
    if ver_todas or url_path == pagina_atual:
        return True
    minimo = MENU_MIN.get(url_path)
    if minimo is None:
        return True
    return _ORDEM.get(modo, 1) >= _ORDEM[minimo]


def escondidas(modo: str, urls) -> list[str]:
    """Páginas (da lista) que o nível atual esconde do menu."""
    return [u for u in urls if not visivel_no_menu(u, modo)]


# ---------------------------------------------------------------- abas por profundidade nas páginas de cada classe
# Em cada classe, a análise Essencial mostra só as abas do essencial; a Detalhada soma as principais; a Aprofundada mostra todas.
_R, _M, _C = "rapida", "mediana", "completa"
_OCULTA = "oculta"   # abas de outro assunto: ficam fora das páginas de cada tipo (o código segue guardado); o assunto tem página própria
ABAS_MIN = {
    "fii": {"Visão geral": _R, "Indicadores": _M, "Dividendos": _M, "Histórico": _C, "Imóveis ou recebíveis": _M, "Riscos": _R,
            "Comparação": _OCULTA, "Análise inteligente": _OCULTA},
    "fundo": {"Visão geral": _R, "Indicadores": _M, "Estratégia": _M, "Composição": _M, "Rentabilidade": _M, "Risco": _R, "Custos": _R,
              "Histórico": _C, "Comparação": _OCULTA, "Análise inteligente": _OCULTA},
    "renda_fixa": {"Visão geral": _R, "Características": _R, "Rentabilidade": _M, "Tributação": _M, "Riscos": _R, "Liquidez": _M,
                   "Marcação a mercado": _C, "Simulador": _M, "Comparação": _OCULTA, "Histórico": _C, "Análise inteligente": _OCULTA},
    "cripto": {"Visão geral": _R, "Mercado": _M, "Fundamentos": _M, "Tokenomics": _M, "On-chain": _C, "Segurança": _R, "Valuation": _C,
               "Histórico": _C, "Comparação": _OCULTA, "Análise inteligente": _OCULTA},
}
_NIV = {_R: 0, _M: 1, _C: 2, _OCULTA: 99}


def abas_visiveis(classe: str, nomes: list[str], prof: str) -> list[bool]:
    """Para cada aba da classe: aparece nesta profundidade? Aba desconhecida sempre aparece; a primeira nunca some."""
    regra = ABAS_MIN.get(classe, {})
    p = _NIV.get(prof if prof in _NIV else _M)
    vis = [_NIV[regra.get(n, _R)] <= p for n in nomes]
    if nomes and not any(vis):
        vis[0] = True
    return vis


# ---------------------------------------------------------------- checklist de decisão (4 perguntas, sem recomendar compra ou venda)
_COR = {"verde": "good", "amarelo": "fair", "vermelho": "bad", "cinza": "na"}


def checklist(leitura: dict, margem_alvo: float, perfil: str, dy=None, paga_dividendos=None) -> list[dict]:
    """Quatro perguntas simples sobre a empresa, cada uma com resposta verde, amarela, vermelha ou cinza (sem dado).
    É um roteiro de leitura: não diz para comprar nem vender."""
    margem = leitura.get("margem")
    saude = leitura.get("saude")
    if margem is None:
        p1 = ("cinza", "Não deu para calcular o preço justo.")
    elif margem >= margem_alvo:
        p1 = ("verde", "Sim: o preço está abaixo do valor justo estimado, com a folga que o seu perfil pede.")
    elif margem >= 0:
        p1 = ("amarelo", "Mais ou menos: está perto do valor justo, mas sem a folga que o seu perfil pede.")
    else:
        p1 = ("vermelho", "Não: o preço está acima do valor justo estimado.")
    p2 = ("cinza", "Faltam dados para avaliar a saúde da empresa.") if saude is None else {
        "sólida": ("verde", "Sim: lucro, rentabilidade e dívida estão em níveis confortáveis."),
        "moderada": ("amarelo", "Em parte: alguns números de saúde estão no limite."),
        "frágil": ("vermelho", "Pouco: os números de saúde financeira estão fracos.")}[saude]
    if paga_dividendos is None and dy is None:
        p3 = ("cinza", "Sem dados de dividendos.")
    elif (dy or 0) >= 6:
        p3 = ("verde", "Sim: paga uma parte relevante do lucro em dividendos.")
    elif (dy or 0) >= 3 or paga_dividendos:
        p3 = ("amarelo", "Um pouco: paga dividendos, mas não são o forte da empresa.")
    else:
        p3 = ("vermelho", "Quase nada: paga pouco ou nenhum dividendo.")
    if margem is None:
        p4 = ("cinza", "Sem preço justo, não dá para comparar com o seu perfil.")
    elif margem >= margem_alvo and saude != "frágil":
        p4 = ("verde", f"Sim: passa na régua do perfil {perfil}.")
    elif margem >= 0 and saude != "frágil":
        p4 = ("amarelo", f"Quase: ainda não passa na régua do perfil {perfil}.")
    else:
        p4 = ("vermelho", f"Não: não passa na régua do perfil {perfil} hoje.")
    perguntas = ["O preço está abaixo do valor justo?", "A empresa é saudável?", "Ela paga dividendos?", f"Combina com o perfil {perfil}?"]
    return [{"pergunta": q, "cor": c, "cls": _COR[c], "texto": t} for q, (c, t) in zip(perguntas, (p1, p2, p3, p4))]


# ---------------------------------------------------------------- selo de atualização dos dados
def selo_dados(data_balanco, hoje=None, fonte: str | None = None) -> dict:
    """Quão atuais estão os números do balanço usados na análise: verde até ~5 meses, amarelo até ~10, vermelho acima."""
    import pandas as pd
    hoje = pd.Timestamp(hoje) if hoje is not None else pd.Timestamp.now()
    try:
        d = pd.to_datetime(data_balanco, errors="coerce")
    except Exception:
        d = None
    pre = f"Fonte: {fonte}. " if fonte else ""
    if d is None or pd.isna(d):
        return {"nivel": "cinza", "texto": pre + "Data do último balanço não informada pela fonte."}
    d = d.tz_localize(None) if getattr(d, "tzinfo", None) else d
    dias = max(0, (hoje.normalize() - d.normalize()).days)
    nivel = "verde" if dias <= 150 else "amarelo" if dias <= 300 else "vermelho"
    quando = d.strftime("%d/%m/%Y")
    ha = "hoje" if dias == 0 else f"há {dias} dias" if dias < 60 else f"há {round(dias / 30)} meses"
    extra = "" if nivel == "verde" else " Os números de lucro e patrimônio podem estar defasados."
    return {"nivel": nivel, "texto": f"{pre}Último balanço usado: {quando} ({ha}).{extra}", "dias": dias}


# ---------------------------------------------------------------- primeiros passos (iniciante) e resumo do dia
PRIMEIROS_PASSOS = (
    {"titulo": "1. Entenda o preço justo", "texto": "Veja, em palavras simples, como o app estima quanto uma ação parece valer.", "pagina": "educacao", "rotulo": "Abrir Educação financeira"},
    {"titulo": "2. Analise a sua primeira empresa", "texto": "Digite o nome de uma empresa na busca acima. Você recebe uma leitura curta e um roteiro de 4 perguntas.", "pagina": None, "rotulo": ""},
    {"titulo": "3. Olhe antes de decidir", "texto": "Confira preço justo, saúde e dividendos, e leia o risco principal. A decisão é sua.", "pagina": "preco-justo", "rotulo": "Abrir Preço justo"},
)

_FRASE_GERAL = {"BOM": "As condições gerais da economia estão relativamente favoráveis.",
                "NEUTRO": "A economia dá sinais mistos, sem uma direção forte.",
                "RUIM": "As condições gerais da economia estão relativamente desfavoráveis."}
_ROT_SETOR = {"BOM": "ambiente favorável", "NEUTRO": "ambiente neutro", "RUIM": "ambiente desfavorável"}


def resumo_do_dia(snapshot: dict | None, posicoes: list[dict] | None, nomes_setor: dict | None = None, modo: str = "iniciante") -> dict | None:
    """Frase curta do cenário da economia e o que ele significa para os setores da carteira REAL. Usa só a última leitura guardada (sem rede).
    Devolve None se não há leitura guardada. Nunca prevê preço nem recomenda."""
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("geral"), dict) or snapshot["geral"].get("v") not in _FRASE_GERAL:
        return None
    g = snapshot["geral"]
    nomes_setor = nomes_setor or {}
    setores: dict[str, list[str]] = {}
    for p in posicoes or []:
        k = p.get("setor_chave")
        s = snapshot.get(k) if k else None
        if isinstance(s, dict) and s.get("v") in _ROT_SETOR:
            setores.setdefault(k, []).append(p.get("ativo") or "")
    linhas = []
    for k, ativos in setores.items():
        v = snapshot[k]["v"]
        linhas.append({"setor": nomes_setor.get(k, k), "veredito": v, "ativos": sorted(a for a in ativos if a), "rotulo": _ROT_SETOR[v]})
    ordem = {"RUIM": 0, "BOM": 1, "NEUTRO": 2}
    linhas.sort(key=lambda x: (ordem[x["veredito"]], x["setor"]))
    frase = _FRASE_GERAL[g["v"]]
    if modo != "iniciante" and g.get("nota") is not None:
        frase += f" (nota {g['nota']:+.2f}, confiança {str(g.get('conf', '')).lower()})"
    return {"geral": g["v"], "frase": frase, "setores": linhas,
            "aviso": "Leitura educativa do ambiente econômico. Não prevê o preço de nenhum ativo e não é recomendação."}
