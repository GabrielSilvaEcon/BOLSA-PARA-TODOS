"""Áreas do app (estilo super app): quais páginas aparecem em cada área.

Módulo puro: não importa o Streamlit e não mexe em nenhuma tela. Identifica as páginas pelo `url_path`
(o mesmo usado em `st.Page(..., url_path=...)` no app.py). Para mudar ou criar uma área, edite só a lista AREAS.
Regras: 3 ou 4 áreas (cabem na barra do celular); cada página em no máximo uma área.
"""

MAX_AREAS = 4

# Páginas sempre acessíveis, em qualquer área (não pertencem a nenhuma).
SEMPRE = ("inicio", "conta", "planos", "administracao", "ajuda")

# `descricao` aparece no cartão da tela Início. A primeira página de cada área é a página padrão (a que abre ao entrar na área pela primeira vez).
# `entrada` = página que SEMPRE abre ao tocar na área (tela própria com cartões); sem `entrada`, abre a última página visitada.
# `grupo_menu` = grupo do menu lateral que abre sozinho quando a área é aberta pela raiz (chave usada em `cat(...)` no app.py).
AREAS = [
    {
        "id": "aprender", "nome": "Aprender", "icone": ":material/school:", "grupo_menu": "edu",
        "descricao": "Jornada, educação financeira e glossário",
        "paginas": ["jornada", "educacao", "glossario"],
    },
    {
        "id": "analisar", "nome": "Analisar", "icone": ":material/query_stats:", "grupo_menu": "acoes", "entrada": "analisar",
        "descricao": "Carteira, ações, fundos, cripto e mais",
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
        "id": "jogar", "nome": "Jogar", "icone": ":material/emoji_events:", "grupo_menu": "competicao",
        "descricao": "Missões, desafios e ranking",
        "paginas": ["jogar", "competicao"],
    },
]

# Cartões da tela-raiz de Analisar (url_path, rótulo). Todo url_path precisa estar nas páginas da mesma área.
HUBS = {
    "analisar": {
        "titulo": "Analisar", "icone": "🔎",
        "subtitulo": "Escolha o tipo de ativo e a análise. Para pesquisar pelo nome ou código, use o Início.",
        "cartoes": [
            {"titulo": "Ações", "descricao": "Preço justo, valor e qualidade da empresa",
             "paginas": [("preco-justo", "Preço justo"), ("valuation", "Múltiplos"), ("dividendos", "Dividendos"),
                         ("micro", "Saúde financeira"), ("dcf", "Fluxo de caixa (DCF)"), ("tecnica", "Análise técnica de ações"),
                         ("stock-picking", "Ranking")]},
            {"titulo": "FIIs, fundos e ETFs", "descricao": "Fundos imobiliários e fundos de investimento",
             "paginas": [("fiis", "FIIs"), ("etfs", "ETFs"), ("fundos-acoes", "Fundos de ações"), ("multimercados", "Multimercados"),
                         ("fundos-renda-fixa", "Fundos de renda fixa")]},
            {"titulo": "Renda fixa", "descricao": "Títulos, Tesouro Direto e CDI",
             "paginas": [("renda-fixa", "Análise de títulos"), ("tesouro-cdi", "Tesouro Direto / CDI")]},
            {"titulo": "Criptomoedas", "descricao": "Tokenomics, on-chain e análise técnica",
             "paginas": [("criptomoedas", "Visão geral e tokenomics"), ("cripto-onchain", "Adoção e on-chain"),
                         ("cripto-receitas", "Receitas e emissão"), ("cripto-fundamentalista", "Análise fundamentalista"),
                         ("cripto-avancada", "Análise avançada"), ("tecnica-cripto", "Análise técnica de cripto")]},
            {"titulo": "Ferramentas", "descricao": "Servem para qualquer tipo de ativo",
             "paginas": [("comparar", "Comparar ativos"), ("evolucao", "Evolução e crescimento"), ("tecnica-avancada", "Análise técnica avançada"),
                         ("inteligencia", "Central de inteligência"), ("calculadoras", "Calculadoras"), ("simulador", "Simulador financeiro"),
                         ("macro", "Economia"), ("noticias", "Notícias e eventos"), ("notificacoes", "Alertas")]},
            {"titulo": "Minha carteira", "descricao": "Acompanhe, gerencie e meça o risco",
             "paginas": [("carteira", "Minha carteira"), ("gestao-carteira", "Gestão de carteira"), ("risco", "Gestão de risco"),
                         ("relatorios", "Relatórios e dashboard")]},
        ],
    },
}


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


def limpar(memoria) -> dict:
    """Memória de últimas páginas só com o que ainda vale: área que existe, página que pertence a ela e não é a tela-raiz.
    Protege contra dados antigos ou corrompidos vindos do perfil salvo (áreas renomeadas, páginas removidas)."""
    out = {}
    for area_id, url in (memoria.items() if isinstance(memoria, dict) else []):
        a = _area(area_id) if isinstance(area_id, str) else None
        if a and isinstance(url, str) and url in a["paginas"] and url != a.get("entrada"):
            out[area_id] = url
    return out


def lembrar(memoria: dict, url_path: str) -> dict:
    """Devolve a memória com `url_path` gravada como a última página da sua área (não altera a original).
    Página fora das áreas não muda nada."""
    nova = limpar(memoria)
    a = area_da_pagina(url_path)
    if a and url_path != (_area(a) or {}).get("entrada"):     # a tela-raiz (Analisar) não apaga a última página visitada
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


def grupo_aberto(url_path: str, area_id: str):
    """Chave do grupo do menu lateral que abre sozinho: o `grupo_menu` da área, quando a página atual é a raiz da área,
    o Início ou outra página sem área. Em páginas de uma área o próprio menu já abre o grupo da página."""
    if area_da_pagina(url_path) and url_path != pagina_inicial(area_id):
        return None
    return (_area(area_id) or {}).get("grupo_menu")


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
    for area_id, hub in HUBS.items():
        na_area = set(paginas_da_area(area_id))
        if (_area(area_id) or {}).get("entrada") not in na_area:
            out.append(f"hub {area_id}: a página de entrada não está na área.")
        for c in hub["cartoes"]:
            for url, _ in c["paginas"]:
                if url not in na_area:
                    out.append(f"cartão {c['titulo']}: {url} não está na área {area_id}.")
    return out
