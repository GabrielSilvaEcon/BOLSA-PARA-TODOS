"""Áreas do app (estilo super app): quais páginas aparecem em cada área.

Módulo puro: não importa o Streamlit e não mexe em nenhuma tela. Identifica as páginas pelo `url_path`
(o mesmo usado em `st.Page(..., url_path=...)` no app.py). Para mudar ou criar uma área, edite só a lista AREAS.
Regras: 3 ou 4 áreas (cabem na barra do celular); cada página em no máximo uma área.
"""

MAX_AREAS = 4

# Páginas sempre acessíveis, em qualquer área (não pertencem a nenhuma).
SEMPRE = ("inicio", "conta", "planos", "administracao", "ajuda")

# `descricao` aparece no cartão da tela Início. A primeira página de cada área é a página padrão (a que abre ao entrar na área pela primeira vez).
AREAS = [
    {
        "id": "aprender", "descricao": "Jornada, educação financeira e glossário", "nome": "Aprender", "icone": ":material/school:",
        "paginas": ["jornada", "educacao", "glossario"],
    },
    {
        "id": "analisar", "descricao": "Carteira, ações, fundos, cripto e mais", "nome": "Analisar", "icone": ":material/query_stats:",
        "paginas": [
            "carteira", "gestao-carteira", "risco", "relatorios", "simulador", "calculadoras",
            "preco-justo", "valuation", "micro", "dividendos", "dcf", "tecnica", "tecnica-avancada", "stock-picking",
            "fiis", "etfs", "fundos-acoes", "multimercados", "fundos-renda-fixa",
            "renda-fixa", "tesouro-cdi",
            "criptomoedas", "cripto-onchain", "cripto-receitas", "cripto-fundamentalista", "cripto-avancada", "tecnica-cripto",
            "macro", "comparar", "evolucao", "noticias", "inteligencia", "notificacoes",
        ],
    },
    {
        "id": "jogar", "descricao": "Missões, desafios e ranking", "nome": "Jogar", "icone": ":material/emoji_events:",
        "paginas": ["competicao"],
    },
]


def ids() -> list:
    """Ids das áreas, na ordem da barra."""
    return [a["id"] for a in AREAS]


def _area(area_id: str):
    return next((a for a in AREAS if a["id"] == area_id), None)


def area_padrao() -> str:
    """Área em que o app abre quando ainda não há nenhuma escolhida."""
    return AREAS[0]["id"]


def paginas_da_area(area_id: str) -> list:
    """url_paths das páginas da área (vazio se a área não existe)."""
    a = _area(area_id)
    return list(a["paginas"]) if a else []


def paginas_visiveis(area_id: str) -> list:
    """O que o menu mostra na área ativa: as páginas sempre acessíveis e as da área."""
    return list(SEMPRE) + paginas_da_area(area_id)


def area_da_pagina(url_path: str):
    """Id da área a que a página pertence, ou None (páginas de SEMPRE e páginas desconhecidas)."""
    for a in AREAS:
        if url_path in a["paginas"]:
            return a["id"]
    return None


def area_ativa(url_path: str, atual: str = None) -> str:
    """Área a mostrar quando a página `url_path` está aberta.
    Página de uma área: essa área. Início, Conta, Ajuda etc. não trocam de área: mantém `atual` (ou a padrão)."""
    a = area_da_pagina(url_path)
    if a:
        return a
    return atual if _area(atual or "") else area_padrao()


def lembrar(memoria: dict, url_path: str) -> dict:
    """Devolve a memória com `url_path` gravada como a última página da sua área (não altera a original).
    Página fora das áreas não muda nada."""
    nova = dict(memoria or {})
    a = area_da_pagina(url_path)
    if a:
        nova[a] = url_path
    return nova


def ultima_pagina(area_id: str, memoria: dict = None) -> str:
    """Última página aberta na área; se não houver (ou deixou de existir na área), a página padrão dela."""
    paginas = paginas_da_area(area_id)
    if not paginas:
        return ""
    lembrada = (memoria or {}).get(area_id)
    return lembrada if lembrada in paginas else paginas[0]


def problemas() -> list:
    """Confere a lista AREAS; devolve textos dos problemas (lista vazia = tudo certo)."""
    out, vistos = [], {}
    if not 1 <= len(AREAS) <= MAX_AREAS:
        out.append(f"{len(AREAS)} áreas (o máximo é {MAX_AREAS}).")
    if len(set(ids())) != len(AREAS):
        out.append("ids de área repetidos.")
    for a in AREAS:
        if not a["paginas"]:
            out.append(f"área {a['id']} sem páginas.")
        for p in a["paginas"]:
            if p in SEMPRE:
                out.append(f"{p} está em SEMPRE e na área {a['id']}.")
            if p in vistos:
                out.append(f"{p} está em {vistos[p]} e em {a['id']}.")
            vistos[p] = a["id"]
    return out
