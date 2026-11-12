"""Acesso das páginas por plano (módulo puro, sem Streamlit).

Divisão sugerida (PADRAO_MINIMOS): o Gratuito abre a análise fundamentalista básica, carteira, notícias e educação; o Plus soma saúde financeira,
fundos, renda fixa, cripto, comparador e relatórios; o Premium soma DCF, análise técnica avançada, risco, gestão, inteligência e evolução.
Vale enquanto o administrador não salvar a sua própria configuração (Administração > Consumo > Páginas por plano); depois, vale a dele. O que está aqui vale para o menu (cadeado) e para o servidor (bloqueio por URL):
as duas checagens usam as mesmas funções.
 · Páginas essenciais nunca podem ser trancadas (início, alertas, planos, conta, ajuda): a pessoa sempre consegue sair do bloqueio.
 · Administração é controlada por permissão de papel, não por plano.
 · Falha ao ler a configuração NUNCA bloqueia: sem como conferir, a página é liberada.
"""
from __future__ import annotations

PLANOS_ORDEM = ("visitante", "gratuito", "plus", "premium")
ROTULO = {"visitante": "Visitante", "gratuito": "Gratuito", "plus": "Investidor Plus", "premium": "Investidor Premium"}
NUNCA_TRANCAR = frozenset({"inicio", "notificacoes", "planos", "conta", "ajuda", "administracao"})
CH_CFG = "paginas_plano_cfg"
PADRAO_MINIMOS = {
    # Investidor Plus
    "micro": "plus", "tecnica": "plus", "tecnica-cripto": "plus", "fiis": "plus", "fundos-acoes": "plus", "multimercados": "plus",
    "fundos-renda-fixa": "plus", "renda-fixa": "plus", "etfs": "plus", "criptomoedas": "plus", "cripto-onchain": "plus",
    "cripto-receitas": "plus", "cripto-fundamentalista": "plus", "comparar": "plus", "relatorios": "plus",
    # Investidor Premium
    "dcf": "premium", "tecnica-avancada": "premium", "cripto-avancada": "premium", "risco": "premium", "gestao-carteira": "premium",
    "inteligencia": "premium", "evolucao": "premium", "stock-picking": "premium",
}


def normalizar(cfg) -> dict:
    """{url_path: plano_minimo}. Descarta planos desconhecidos, páginas essenciais e o plano 'visitante' (todos o têm)."""
    out = {}
    if isinstance(cfg, dict):
        for url, pl in (cfg.get("minimos", cfg) if isinstance(cfg.get("minimos", cfg), dict) else {}).items():
            if isinstance(url, str) and url not in NUNCA_TRANCAR and pl in PLANOS_ORDEM and pl != "visitante":
                out[url] = pl
    return out


def plano_minimo(url_path: str, cfg: dict | None) -> str | None:
    return normalizar(cfg).get(url_path)


def liberada(url_path: str, plano: str | None, cfg: dict | None) -> bool:
    """A página abre para este plano? Plano desconhecido conta como visitante (o mais baixo)."""
    minimo = plano_minimo(url_path, cfg)
    if minimo is None:
        return True
    p = plano if plano in PLANOS_ORDEM else "visitante"
    return PLANOS_ORDEM.index(p) >= PLANOS_ORDEM.index(minimo)


def paginas_do_plano(minimos: dict | None, plano: str) -> list[str]:
    """url_path das páginas cujo plano mínimo é exatamente este (o que o plano acrescenta ao anterior)."""
    return sorted(u for u, p in normalizar(minimos).items() if p == plano)


def explicacao(titulo: str, minimo: str, plano: str | None) -> dict:
    """Texto claro do bloqueio: o que é, qual plano libera e qual é o plano atual."""
    atual = ROTULO.get(plano if plano in ROTULO else "visitante")
    return {"titulo": f"{titulo}: disponível no plano {ROTULO[minimo]}",
            "texto": f"Seu plano atual é {atual}. Esta ferramenta pede o plano {ROTULO[minimo]} ou superior. "
                     "Nada do que você já cadastrou foi perdido; o resto do app continua liberado.",
            "minimo": minimo}


_cache = {"v": None, "t": 0.0}


def ler() -> dict:
    """Configuração atual, com cache de 60 s (o menu e o bloqueio consultam a cada interação)."""
    import time
    agora = time.time()
    if _cache["v"] is not None and agora - _cache["t"] < 60:
        return _cache["v"]
    try:
        import banco
        bruto = banco.cfg_ler(CH_CFG)
        v = normalizar(bruto) if isinstance(bruto, dict) and "minimos" in bruto else normalizar({"minimos": PADRAO_MINIMOS})
    except Exception:
        v = {}
    _cache["v"], _cache["t"] = v, agora
    return v


def salvar(minimos: dict) -> dict:
    import banco
    limpo = normalizar({"minimos": minimos})
    banco.cfg_gravar(CH_CFG, {"minimos": limpo})
    _cache["v"], _cache["t"] = limpo, __import__("time").time()
    return limpo
