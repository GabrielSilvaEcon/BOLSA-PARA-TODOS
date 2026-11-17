"""Amizades, bloqueios, denúncias e convites para jogar · regras puras (sem Streamlit, sem banco e sem rede).

Como fica guardado (no banco, em config_sistema; ver banco.py, seção "Amigos"):
 · Cada conta é identificada por um hash do e-mail (nunca o e-mail). Toda operação parte da conta LOGADA (ator); a outra
   ponta vem do nome de usuário, resolvido no servidor.
 · Amizade: duas linhas espelhadas `amz|<eu>|<outro>` com o estado visto por cada lado:
     enviada (eu pedi) · recebida (ele pediu) · amigos.
   A linha de quem RECEBE é inserida primeiro e de forma atômica: dois pedidos cruzados viram amizade, nunca duplicam.
 · Bloqueio: `blq|<quem bloqueou>|<bloqueado>`. Desfaz a amizade e os pedidos, e esconde os perfis nos dois sentidos.
 · Denúncia: `den|<quem>|<alvo>|<dia>` (uma por pessoa, por alvo, por dia). Vai para a administração.
 · Convite para jogar: `cvj|<convidado>|<quem convidou>` com o jogo e o código da sala privada criada pelo fluxo normal do jogo.
"""
from __future__ import annotations

from datetime import datetime, timedelta

ENVIADA, RECEBIDA, AMIGOS = "enviada", "recebida", "amigos"
ESTADOS = (ENVIADA, RECEBIDA, AMIGOS)
MAX_AMIGOS = 200
MAX_PEDIDOS_ENVIADOS = 50
CONVITE_VALIDO_MIN = 30                  # a sala privada espera por pouco tempo: convite mais velho que isso some da lista
TEXTO_DENUNCIA_MAX = 300
MOTIVOS = {
    "nome": "Nome ou foto ofensivos",
    "bio": "Biografia ofensiva",
    "golpe": "Golpe, spam ou divulgação",
    "trapaca": "Trapaça nos jogos",
    "outro": "Outro motivo",
}
JOGOS_CONVITE = {"trade": "Trade Battle", "ticker": "Ticker Battle"}


class ErroAmigos(ValueError):
    """Ação recusada (mensagem pronta para a tela)."""


def estado_valido(e) -> str | None:
    return e if e in ESTADOS else None


def relacoes(linhas: list[dict], prefixo: str) -> dict[str, dict]:
    """{hash do outro: {"estado", "em"}} a partir das linhas `amz|<eu>|<outro>` (uma consulta por prefixo)."""
    out = {}
    for r in linhas or []:
        rid, d = str(r.get("id") or ""), r.get("dados") if isinstance(r.get("dados"), dict) else {}
        if not rid.startswith(prefixo):
            continue
        outro = rid[len(prefixo):]
        est = estado_valido(d.get("estado"))
        if outro and est:
            out[outro] = {"estado": est, "em": str(d.get("em") or "")[:25]}
    return out


def conferir_pedido(eu_h: str, alvo_h: str, rel_atual: str | None, bloqueado: bool, alvo_aceita: bool, n_amigos: int, n_enviados: int) -> str:
    """Decide o que um pedido de amizade faz. Devolve "aceitar" (o outro já tinha pedido), "enviar", ou levanta ErroAmigos."""
    if not alvo_h or eu_h == alvo_h:
        raise ErroAmigos("Você não pode adicionar a si mesmo.")
    if bloqueado:
        raise ErroAmigos("Não é possível adicionar este jogador.")
    if rel_atual == AMIGOS:
        raise ErroAmigos("Vocês já são amigos.")
    if rel_atual == ENVIADA:
        raise ErroAmigos("Você já enviou uma solicitação. Aguarde a resposta.")
    if n_amigos >= MAX_AMIGOS:
        raise ErroAmigos(f"Você chegou ao limite de {MAX_AMIGOS} amigos.")
    if rel_atual == RECEBIDA:
        return "aceitar"
    if not alvo_aceita:
        raise ErroAmigos("Este jogador não está recebendo solicitações de amizade.")
    if n_enviados >= MAX_PEDIDOS_ENVIADOS:
        raise ErroAmigos(f"Você tem {MAX_PEDIDOS_ENVIADOS} solicitações esperando resposta. Cancele algumas antes de enviar outras.")
    return "enviar"


def validar_denuncia(motivo, texto) -> tuple[str, str]:
    if motivo not in MOTIVOS:
        raise ErroAmigos("Escolha o motivo da denúncia.")
    t = " ".join(str(texto or "").split())[:TEXTO_DENUNCIA_MAX]
    if motivo == "outro" and len(t) < 5:
        raise ErroAmigos("Conte em poucas palavras o que aconteceu.")
    return motivo, t


def convite_valido(d: dict, agora: datetime) -> bool:
    try:
        em = datetime.fromisoformat(str(d.get("em")))
    except (TypeError, ValueError):
        return False
    if em.tzinfo is None and agora.tzinfo is not None:
        em = em.replace(tzinfo=agora.tzinfo)
    return d.get("jogo") in JOGOS_CONVITE and bool(d.get("codigo")) and agora - em <= timedelta(minutes=CONVITE_VALIDO_MIN)


def atividade(ultimo_login: str | None, agora: datetime) -> str | None:
    """Indicador grosso de atividade (só para amigos): 'hoje', 'semana' ou None. Nunca a hora exata."""
    try:
        t = datetime.fromisoformat(str(ultimo_login).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if t.tzinfo is None and agora.tzinfo is not None:
        t = t.replace(tzinfo=agora.tzinfo)
    dt = agora - t
    if dt <= timedelta(hours=24):
        return "hoje"
    if dt <= timedelta(days=7):
        return "semana"
    return None


def buscar(itens: list[dict], termo: str, campos=("usuario", "nome")) -> list[dict]:
    """Filtro por nome de exibição ou nome de usuário (sem acento e sem diferença de maiúsculas)."""
    import unicodedata

    def n(s):
        return "".join(c for c in unicodedata.normalize("NFD", str(s or "").lower()) if unicodedata.category(c) != "Mn")
    t = n(termo).strip().lstrip("@")
    if not t:
        return list(itens)
    return [x for x in itens if any(t in n(x.get(c)) for c in campos)]


def comparar(eu: dict, amigos: list[dict], jogo: str) -> list[dict]:
    """Linhas da comparação de desempenho (eu + amigos que mostram estatísticas), ordenadas pela métrica do jogo.
    Cada item de entrada: {"usuario", "nome", "eu", "placar" (doc saneado ou None se oculto)}."""
    import jogos as J
    out = []
    for x in [eu] + list(amigos):
        d = x.get("placar")
        if d is None:
            continue
        d = J.sanear(d)
        if jogo == J.TRADE:
            t = d[J.TRADE]
            row = {"valor": t["pts"], "partidas": t["partidas"], "vitorias": t["vitorias"], "melhor": t["melhor"],
                   "taxa": round(t["vitorias"] / t["salas"] * 100) if t["salas"] else None}
        else:
            k = d[J.TICKER]
            n = k["v"] + k["e"] + k["d"]
            row = {"valor": k["v"], "partidas": n, "vitorias": k["v"], "empates": k["e"], "derrotas": k["d"],
                   "taxa": round(k["v"] / n * 100) if n else None}
        out.append({"usuario": x.get("usuario", ""), "nome": x.get("nome", ""), "eu": bool(x.get("eu")), **row})
    out.sort(key=lambda r: (-r["valor"], -r["partidas"], str(r["usuario"]).lower()))
    for i, r in enumerate(out, 1):
        r["pos"] = i
    return out
