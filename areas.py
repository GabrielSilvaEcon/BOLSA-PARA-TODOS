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
        # Ao tocar em Analisar o app abre sempre a tela própria da área (cartões por tipo de ativo); a Carteira fica dentro da área.
        "entrada": "analisar",
        "paginas": [
            "analisar", "carteira", "gestao-carteira", "risco", "relatorios", "simulador", "calculadoras",
            "preco-justo", "valuation", "micro", "dividendos", "dcf", "tecnica", "tecnica-avancada", "stock-picking",
            "fiis", "etfs", "fundos-acoes", "multimercados", "fundos-renda-fixa",
            "renda-fixa", "tesouro-cdi",
            "criptomoedas", "cripto-onchain", "cripto-receitas", "cripto-fundamentalista", "cripto-avancada", "tecnica-cripto",
            "macro", "comparar", "evolucao", "noticias", "inteligencia", "notificacoes",
        ],
    },
    {
        "id": "jogar", "descricao": "Missões, desafios e ranking", "nome": "Jogar", "icone": ":material/emoji_events:",
        "paginas": ["jogar", "competicao"],
    },
]

# Cartões da tela "Analisar" (url_path, rótulo). Cada url_path precisa estar na lista de páginas da área Analisar.
HUB_ANALISAR = [
    {"titulo": "Ações", "icone": ":material/show_chart:", "descricao": "Preço justo, valor e qualidade da empresa",
     "paginas": [("preco-justo", "Preço justo"), ("valuation", "Múltiplos"), ("dividendos", "Dividendos"),
                 ("micro", "Saúde financeira"), ("dcf", "Fluxo de caixa (DCF)"), ("tecnica", "Análise técnica de ações")]},
    {"titulo": "FIIs, fundos e ETFs", "icone": ":material/account_balance:", "descricao": "Fundos imobiliários e fundos de investimento",
     "paginas": [("fiis", "FIIs"), ("etfs", "ETFs"), ("fundos-acoes", "Fundos de ações"), ("multimercados", "Multimercados"),
                 ("fundos-renda-fixa", "Fundos de renda fixa")]},
    {"titulo": "Renda fixa", "icone": ":material/savings:", "descricao": "Títulos, Tesouro Direto e CDI",
     "paginas": [("renda-fixa", "Análise de títulos"), ("tesouro-cdi", "Tesouro Direto / CDI")]},
    {"titulo": "Criptomoedas", "icone": ":material/currency_bitcoin:", "descricao": "Tokenomics, on-chain e análise técnica",
     "paginas": [("criptomoedas", "Visão geral e tokenomics"), ("cripto-onchain", "Adoção e on-chain"),
                 ("cripto-receitas", "Receitas e emissão"), ("cripto-fundamentalista", "Análise fundamentalista"),
                 ("cripto-avancada", "Análise avançada"), ("tecnica-cripto", "Análise técnica de cripto")]},
    {"titulo": "Ferramentas", "icone": ":material/hub:", "descricao": "Servem para qualquer tipo de ativo",
     "paginas": [("comparar", "Comparar ativos"), ("evolucao", "Evolução e crescimento"), ("tecnica-avancada", "Análise técnica avançada"),
                 ("inteligencia", "Central de inteligência"), ("calculadoras", "Calculadoras"), ("simulador", "Simulador financeiro"),
                 ("macro", "Economia"), ("noticias", "Notícias e eventos")]},
    {"titulo": "Minha carteira", "icone": ":material/account_balance_wallet:", "descricao": "Acompanhe, gerencie e meça o risco",
     "paginas": [("carteira", "Minha carteira"), ("gestao-carteira", "Gestão de carteira"), ("risco", "Gestão de risco"),
                 ("relatorios", "Relatórios e dashboard")]},
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
    """Página que abre ao tocar na área. Área com `entrada` (Analisar -> tela da área) abre sempre nela;
    as demais abrem a última página visitada; se não houver (ou deixou de existir), a página padrão."""
    paginas = paginas_da_area(area_id)
    if not paginas:
        return ""
    entrada = (_area(area_id) or {}).get("entrada")
    if entrada:
        return entrada
    lembrada = (memoria or {}).get(area_id)
    return lembrada if lembrada in paginas else paginas[0]


def pagina_inicial(area_id: str) -> str:
    """Página-raiz da área (a `entrada`, ou a primeira da lista): é o primeiro item da trilha no topo das páginas."""
    a = _area(area_id)
    return (a.get("entrada") or a["paginas"][0]) if a and a["paginas"] else ""


def trilha(url_path: str):
    """(área, url da página-raiz) para a trilha 'Analisar › Preço justo'; None se a página não tem trilha
    (fora das áreas, ou é a própria página-raiz da área)."""
    area = area_da_pagina(url_path)
    if not area:
        return None
    raiz = pagina_inicial(area)
    return None if raiz == url_path else (_area(area), raiz)


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
    na_area = set(paginas_da_area("analisar"))
    for c in HUB_ANALISAR:
        for url, _ in c["paginas"]:
            if url not in na_area:
                out.append(f"cartão {c['titulo']}: {url} não está na área analisar.")
    return out
