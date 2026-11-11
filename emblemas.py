"""Coleção de emblemas (Fase 3). Módulo puro, sem Streamlit e sem gravar nada.

Cada emblema é DERIVADO do que o app já guarda (Jornada, conquistas do Wallet Game, selos de temporada). Não tem recompensa própria:
nenhum emblema paga XP, Ticker Coins ou T$, então nada se duplica nem se converte entre as três economias.
`ctx` = {"licoes": int, "ofensiva": int, "unidades": int, "nivel": int, "wg": {id_conquista: data|None}, "aceite": bool, "selos": [{"selo","temp"}]}
"""
from __future__ import annotations

CATEGORIAS = ("Aprendizado", "Consistência", "Evolução financeira simulada", "Participação", "Desafios", "Temporadas", "Exploração de classes")

# (id, categoria, nome, descrição, emblema, cor, regra)
# regra = ("min", chave, valor) | ("wg", id_conquista) | ("aceite",) | ("selo", tipo)
_CAT = [
    ("a_primeira", "Aprendizado", "Primeira lição", "Concluiu a primeira lição da Jornada.", "📘", "#8B6CFF", ("min", "licoes", 1)),
    ("a_dez", "Aprendizado", "10 lições", "Concluiu 10 lições.", "📚", "#8B6CFF", ("min", "licoes", 10)),
    ("a_unidade", "Aprendizado", "Unidade completa", "Terminou todas as lições de uma unidade.", "🎓", "#8B6CFF", ("min", "unidades", 1)),
    ("a_nivel5", "Aprendizado", "Nível 5", "Chegou ao nível 5 de estudo.", "⭐", "#8B6CFF", ("min", "nivel", 5)),
    ("a_nivel10", "Aprendizado", "Nível 10", "Chegou ao nível 10 de estudo.", "🌟", "#8B6CFF", ("min", "nivel", 10)),
    ("k_3", "Consistência", "3 dias seguidos", "Estudou 3 dias seguidos.", "🔥", "#FF9B3D", ("min", "ofensiva", 3)),
    ("k_7", "Consistência", "7 dias seguidos", "Estudou 7 dias seguidos.", "🔥", "#FF9B3D", ("min", "ofensiva", 7)),
    ("k_30", "Consistência", "30 dias seguidos", "Estudou 30 dias seguidos.", "🏅", "#FF9B3D", ("min", "ofensiva", 30)),
    ("k_bonus7", "Consistência", "Bônus 7 dias", "Resgatou o bônus do Wallet Game 7 dias seguidos.", "📅", "#FF9B3D", ("wg", "c_seq7")),
    ("f_primeiro", "Evolução financeira simulada", "Primeiro investimento", "Fez a primeira compra na carteira virtual.", "🌱", "#3DDC97", ("wg", "c_primeiro")),
    ("f_positiva", "Evolução financeira simulada", "Resultado positivo", "A carteira virtual fechou no positivo.", "📈", "#3DDC97", ("wg", "c_positiva")),
    ("f_val10", "Evolução financeira simulada", "10% de valorização", "Chegou a +10% de resultado simulado.", "🚀", "#3DDC97", ("wg", "c_val10")),
    ("f_prata", "Evolução financeira simulada", "Rank Prata", "Chegou ao rank Prata.", "🥈", "#3DDC97", ("wg", "c_prata")),
    ("f_ouro", "Evolução financeira simulada", "Rank Ouro", "Chegou ao rank Ouro.", "🥇", "#3DDC97", ("wg", "c_ouro")),
    ("p_wallet", "Participação", "Entrou no Wallet Game", "Aceitou participar da competição de carteiras.", "🎮", "#2BA7C9", ("aceite",)),
    ("d_missoes5", "Desafios", "5 missões", "Completou 5 missões do Wallet Game.", "🎯", "#F2B84B", ("wg", "c_missoes5")),
    ("t_ouro", "Temporadas", "Selo Ouro", "1º lugar em uma temporada.", "🥇", "#F2B84B", ("selo", "ouro")),
    ("t_prata", "Temporadas", "Selo Prata", "2º lugar em uma temporada.", "🥈", "#F2B84B", ("selo", "prata")),
    ("t_bronze", "Temporadas", "Selo Bronze", "3º lugar em uma temporada.", "🥉", "#F2B84B", ("selo", "bronze")),
    ("t_top10", "Temporadas", "Top 10", "Ficou entre os 10 melhores de uma temporada.", "🔟", "#F2B84B", ("selo", "top10")),
    ("t_equilibrio", "Temporadas", "Equilíbrio", "Melhor retorno ajustado ao risco em uma temporada.", "⚖️", "#F2B84B", ("selo", "equilibrio")),
    ("x_diversa", "Exploração de classes", "Carteira diversificada", "Montou uma carteira com 4 ativos em 3 classes.", "🧺", "#D23FC8", ("wg", "c_diversa")),
]
EMBLEMAS = [dict(zip(("id", "categoria", "nome", "descricao", "emblema", "cor", "regra"), x)) for x in _CAT]


def _n(ctx: dict, chave: str) -> int:
    try:
        return int(ctx.get(chave) or 0)
    except (TypeError, ValueError):
        return 0


def conquistado(e: dict, ctx: dict) -> bool:
    r = e["regra"]
    if r[0] == "min":
        return _n(ctx, r[1]) >= r[2]
    if r[0] == "wg":
        return bool((ctx.get("wg") or {}).get(r[1]))
    if r[0] == "aceite":
        return bool(ctx.get("aceite"))
    if r[0] == "selo":
        return any(isinstance(s, dict) and s.get("selo") == r[1] for s in (ctx.get("selos") or []))
    return False


def colecao(ctx: dict) -> list[dict]:
    """[{categoria, itens:[{...emblema, ok}], ok, total}] na ordem de CATEGORIAS; categorias sem emblema não aparecem."""
    ctx = ctx or {}
    out = []
    for cat in CATEGORIAS:
        itens = [{**e, "ok": conquistado(e, ctx)} for e in EMBLEMAS if e["categoria"] == cat]
        if itens:
            out.append({"categoria": cat, "itens": itens, "ok": sum(1 for i in itens if i["ok"]), "total": len(itens)})
    return out


def totais(col: list[dict]) -> tuple[int, int]:
    return sum(c["ok"] for c in col), sum(c["total"] for c in col)


def contexto(jornada_resumo: dict, unidades_completas: int, nivel: int, conquistas_wg: list[dict], aceite: bool, selos: list) -> dict:
    """Monta o ctx a partir do que as telas já têm (sem ler banco aqui)."""
    return {"licoes": jornada_resumo.get("licoes_feitas", 0), "ofensiva": jornada_resumo.get("ofensiva", 0), "unidades": unidades_completas,
            "nivel": nivel, "wg": {c["id"]: c.get("desbloqueada_em") for c in (conquistas_wg or []) if isinstance(c, dict) and "id" in c},
            "aceite": bool(aceite), "selos": [s for s in (selos or []) if isinstance(s, dict)]}
