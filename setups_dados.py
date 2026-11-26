"""Setups colecionáveis · leitura e gravação no banco e ligação com os baús e com a partida X1.

- Coleção de cada pessoa: banco.sis_estado (chave CH_COLECAO), separada da coleção de cartas. Toda mudança passa pelas regras de setups.py.
- O que foi conquistado fica para sempre; só se equipa o setup cuja carta a pessoa tem. Os setups equipados (até 2) valem sozinhos nas partidas X1 (congelados no começo).
- Baús: a roleta do setup é uma rolagem à parte (setups.sortear_do_bau), pelo mesmo ponto onde as cartas do baú já são entregues.
"""
from __future__ import annotations

import banco
import cartas_dados as CD
import setups as SU

CH_COLECAO = "setups_colecao"
PRESENTE_ID = "setup_classico"        # o setup de boas-vindas: o mais simples, para todo mundo começar com um
PRESENTE_REF = "presente:inicial"


def ler(email: str) -> dict:
    try:
        return SU.normalizar(banco.sis_estado_ler(email, CH_COLECAO))
    except Exception:
        return SU.colecao_vazia()


def gravar(email: str, doc: dict) -> None:
    banco.sis_estado_gravar(email, CH_COLECAO, doc)


def equipados(email: str) -> list[str]:
    """Os setups equipados (até 2), já conferidos contra as cartas que a pessoa realmente tem (a conferência é de `normalizar`)."""
    return ler(email)["equipados"]


def _visao(s: dict, doc: dict) -> dict:
    meu = doc["itens"].get(s["id"]) or {}
    return {**s, "desde": meu.get("desde"), "origem": meu.get("origem") or "liberado", "equipado": s["id"] in doc["equipados"]}


def listar(email: str) -> dict:
    """Tudo liberado: o catálogo inteiro. Com a liberação desligada: só o que ela conquistou (o resto não aparece: nem o nome, nem a regra, só quantos faltam)."""
    doc = ler(email)
    itens = [_visao(s, doc) for s in SU.catalogo() if SU.tem(doc, s["id"])]
    return {"itens": itens, "equipados": doc["equipados"], "limite": SU.MAX_EQUIPADOS, "conquistados": len(itens), "total": len(SU.catalogo()),
            "todos_liberados": SU.LIBERAR_TODOS}


def equipar(email: str, setup_id: str) -> dict:
    doc = ler(email)
    r = SU.equipar(doc, setup_id, CD._agora_iso())
    gravar(email, doc)
    return r


def desequipar(email: str, setup_id: str) -> dict:
    doc = ler(email)
    r = SU.desequipar(doc, setup_id, CD._agora_iso())
    gravar(email, doc)
    return r


def presente_inicial(email: str) -> dict | None:
    """Presente de boas-vindas: a carta do setup básico, uma vez só por conta (contas antigas e novas). Já entra equipada se houver espaço.
    Devolve o setup (com nova=True) quando entregou agora, ou None se já tinha sido entregue (ou a pessoa já tinha o setup)."""
    if SU.LIBERAR_TODOS:                                     # tudo liberado: não há brinde nem aviso de "carta ganha"
        return None
    doc = ler(email)
    if PRESENTE_REF in doc["ids"]:
        return None
    agora = CD._agora_iso()
    doc["ids"] = (doc["ids"] + [PRESENTE_REF])[-SU.IDS_MAX:]
    novo = SU.conquistar(doc, PRESENTE_ID, "presente_inicial", agora)
    if novo and len(doc["equipados"]) < SU.MAX_EQUIPADOS:
        SU.equipar(doc, PRESENTE_ID, agora)
    gravar(email, doc)
    if not novo:
        return None
    s = SU.info(PRESENTE_ID)
    try:                                                     # o aviso no sino; se falhar, o presente continua valendo
        banco.sis_notif_inserir(email, {"dedup": "setup_presente|" + PRESENTE_ID, "categoria": "sistema", "importancia": "media",
                                        "titulo": f"🎁 Presente: carta do {s['nome']}",
                                        "texto": f"Você ganhou a carta do {s['nome']}. Com ela, o setup já vale nas suas partidas X1 (ele foi equipado em Meus Setups; "
                                                 f"você pode usar até {SU.MAX_EQUIPADOS} ao mesmo tempo).",
                                        "origem": "presente", "pagina": "setups"})
    except Exception as e:
        banco.registrar_erro("setups.presente_aviso", e)
    return {**_visao(s, doc), "nova": True}


def recompensa_bau(email: str, ref: str, rar_bau: str) -> dict:
    """Setup de um baú já aberto. Mesmo baú (mesma `ref`) = mesmo resultado, entregue uma vez só. {'ja': bool, 'setup': {...nova: True} | None}"""
    if SU.LIBERAR_TODOS:                                     # tudo liberado: o baú não sorteia setup (não há o que ganhar)
        return {"ja": True, "setup": None}
    doc = ler(email)
    chave = "bau:" + ref
    if chave in doc["ids"]:
        return {"ja": True, "setup": None}
    sid = SU.sortear_do_bau(f"{banco._h_conta(email)}|{ref}", rar_bau, doc, CD.regras()["baus"])
    doc["ids"] = (doc["ids"] + [chave])[-SU.IDS_MAX:]
    if sid:
        SU.conquistar(doc, sid, "bau_" + rar_bau, CD._agora_iso())
    gravar(email, doc)
    return {"ja": False, "setup": {**_visao(SU.info(sid), doc), "nova": True} if sid else None}
