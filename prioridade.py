"""Etapa 4 · Ativos prioritários e aquecimento do cache.

O monitor automático (GitHub Actions) já roda a cada 15 min. Depois de cuidar dos alertas dos usuários, ele usa uma pequena parte do
orçamento para ler os ativos PRIORITÁRIOS, em rodízio, e o cache central grava o resultado no Supabase. Assim, quem abre o app
encontra o dado pronto e a fonte (Yahoo etc.) recebe poucos pedidos.
 · A lista é editada pelo administrador (Administração > Consumo). Padrão: ativos muito conhecidos da B3 e algumas criptos.
 · Por execução lê no máximo `por_execucao` ativos (padrão 15), continuando de onde parou (cursor); para após 3 falhas seguidas;
   respeita suspensão e bloqueio de consumo (a leitura simplesmente falha e conta como falha).
 · Ativos que o monitor já leu para os alertas nesta execução são pulados (não repete pedido).
Não cria dado: só antecipa leituras reais; quando a fonte falha, nada é gravado.
"""
from __future__ import annotations

import re
import time

CH = "prioridade"
LIMITE_LISTA = 60
PADRAO = (
    [(t, "acao") for t in ("PETR4", "VALE3", "ITUB4", "BBDC4", "BBAS3", "ABEV3", "WEGE3", "B3SA3", "RENT3", "SUZB3", "ELET3",
                           "PRIO3", "MGLU3", "LREN3", "JBSS3", "GGBR4")]
    + [(t, "fii") for t in ("HGLG11", "KNRI11", "XPML11", "MXRF11", "VISC11", "BTLG11")]
    + [(t, "cripto") for t in ("BTC", "ETH", "SOL")]
)
_B3 = re.compile(r"^[A-Z]{4}\d{1,2}$")


def classe_de(tk: str) -> str:
    if _B3.match(tk):
        return "fii" if tk.endswith("11") else "acao"
    return "cripto"


def parse(txt: str) -> list[tuple[str, str]]:
    """'PETR4, VALE3 BTC HGLG11:fii' -> [(id, classe)]. Ignora itens inválidos e repetidos."""
    import seguranca as seg
    out, vistos = [], set()
    for tok in re.split(r"[,\s;]+", str(txt or "")):
        if not tok:
            continue
        tk, _, cl = tok.partition(":")
        tk = seg.validar_ticker(tk)
        if not tk or tk in vistos:
            continue
        cl = cl.lower() if cl.lower() in ("acao", "fii", "etf", "cripto") else classe_de(tk)
        vistos.add(tk)
        out.append((tk, cl))
    return out[:LIMITE_LISTA]


def config() -> dict:
    cfg = {"ativos": [list(x) for x in PADRAO], "por_execucao": 15, "cursor": 0, "ligado": True}
    try:
        import banco
        lido = banco.cfg_ler(CH) or {}
        for k in cfg:
            if k in lido:
                cfg[k] = lido[k]
    except Exception:
        pass
    cfg["por_execucao"] = max(0, min(int(cfg["por_execucao"] or 0), 40))
    return cfg


def salvar(ativos, por_execucao: int, ligado: bool = True) -> None:
    import banco
    cfg = config()
    cfg.update({"ativos": [list(x) for x in ativos][:LIMITE_LISTA], "por_execucao": max(0, min(int(por_execucao), 40)),
                "ligado": bool(ligado), "cursor": 0})
    banco.cfg_gravar(CH, cfg)


def proximos(cfg: dict, n: int, pular=()) -> tuple[list[tuple[str, str]], int]:
    """Próximos `n` itens em rodízio (sem os de `pular`) e o novo cursor."""
    lista = [tuple(x) for x in cfg["ativos"]]
    if not lista or n <= 0:
        return [], cfg.get("cursor", 0)
    i = int(cfg.get("cursor", 0)) % len(lista)
    out, passos = [], 0
    while len(out) < n and passos < len(lista):
        item = lista[(i + passos) % len(lista)]
        passos += 1
        if item[0] not in pular:
            out.append(item)
    return out, (i + passos) % len(lista)


def aquecer(coletor, dormir=time.sleep, ja_lidos=(), orcamento: int | None = None, falhas_max: int = 3) -> dict:
    """Lê os próximos prioritários. Devolve {'lidos','falhas','pulados'}. `orcamento` limita o total (além de por_execucao)."""
    cfg = config()
    res = {"lidos": 0, "falhas": 0, "pulados": 0}
    if not cfg["ligado"]:
        return {**res, "desligado": True}
    n = cfg["por_execucao"] if orcamento is None else min(cfg["por_execucao"], max(0, orcamento))
    pular = set(ja_lidos)
    itens, cursor = proximos(cfg, n, pular)
    res["pulados"] = len(pular & {x[0] for x in cfg["ativos"]})
    seguidas = 0
    for ativo, classe in itens:
        if seguidas >= falhas_max:
            break
        try:
            d = coletor(ativo, classe, classe != "cripto")
            res["lidos"] += 1 if d else 0
            res["falhas"] += 0 if d else 1
            seguidas = 0 if d else seguidas + 1
        except Exception:
            res["falhas"] += 1
            seguidas += 1
            dormir(1)
    try:
        import banco
        cfg["cursor"] = cursor
        banco.cfg_gravar(CH, cfg)
    except Exception:
        pass
    return res
