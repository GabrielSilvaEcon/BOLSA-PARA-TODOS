"""Três profundidades de análise (Rápida · Mediana · Completa) e menu por nível de conhecimento. Módulo puro (sem Streamlit).

Só muda QUANTO aparece: nenhum cálculo, dado, carteira ou alerta é alterado. A profundidade padrão acompanha o nível da pessoa
(Iniciante → Rápida, Intermediário → Mediana, Avançado → Completa) e ela troca quando quiser.
"""
from __future__ import annotations

PROFUNDIDADES = ("rapida", "mediana", "completa")
ROTULOS = {"rapida": "Rápida", "mediana": "Mediana", "completa": "Completa"}
DESCRICAO = {
    "rapida": "O essencial em poucos segundos: veredito em texto, preço e preço justo.",
    "mediana": "A rápida mais os cartões de cada análise (preço justo, múltiplos, saúde e dividendos).",
    "completa": "Tudo que o app calcula: todas as análises, sinais, notícias e as abas completas.",
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
