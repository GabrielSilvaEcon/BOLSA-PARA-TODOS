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
    return {**s, "desde": doc["itens"][s["id"]]["desde"], "origem": doc["itens"][s["id"]]["origem"], "equipado": s["id"] in doc["equipados"]}


def listar(email: str) -> dict:
    """Só o que ela conquistou. O resto do catálogo não aparece: nem o nome, nem a regra, só quantos faltam."""
    doc = ler(email)
    itens = [_visao(s, doc) for s in SU.catalogo() if s["id"] in doc["itens"]]
    return {"itens": itens, "equipados": doc["equipados"], "limite": SU.MAX_EQUIPADOS, "conquistados": len(itens), "total": len(SU.catalogo())}


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


def recompensa_bau(email: str, ref: str, rar_bau: str) -> dict:
    """Setup de um baú já aberto. Mesmo baú (mesma `ref`) = mesmo resultado, entregue uma vez só. {'ja': bool, 'setup': {...nova: True} | None}"""
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
