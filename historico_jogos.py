"""Histórico de partidas do app novo (botão "Ver detalhes" de Sua Evolução, na aba Jogos).

O placar dos jogos (jogos.py) só guarda partidas ONLINE, porque é ele que alimenta o ranking. Para o jogador ver também as partidas
contra o sistema, o Trade Battle ganha um histórico pessoal (todas as partidas, solo e online), guardado à parte e sem efeito em
ranking ou pontos. O Ticker Battle já tinha o seu (battle_dados: duelos contra o sistema) e os duelos online vêm do placar.
Funções puras; quem lê e grava no banco é a API.
"""
from __future__ import annotations

CHAVE_TRADE = "trade_hist"
MAX = 30


def _num(v):
    try:
        x = float(v)
    except (TypeError, ValueError):
        return None
    return x if x == x else None


def anotar_trade(doc: dict | None, pid: str, em: str, n_jog: int, pontos, pos=None, formato: str = "", lucro=None, retorno=None,
                 qualidade=None) -> tuple[dict, bool]:
    """Acrescenta UMA partida terminada do Trade Battle ao histórico pessoal. Repetir o mesmo `pid` não duplica. Devolve (doc, mudou)."""
    d = {"itens": [h for h in ((doc or {}).get("itens") or []) if isinstance(h, dict)][:MAX]}
    pid = str(pid or "")[:40]
    if not pid or any(h.get("id") == pid for h in d["itens"]):
        return d, False
    n = int(n_jog or 1)
    h = {"id": pid, "em": str(em or "")[:16], "modo": "online" if n >= 2 else "solo", "n": n, "pos": pos if n >= 2 else None,
         "pontos": round(_num(pontos) or 0.0, 1), "formato": str(formato or "")[:14]}
    for k, v in (("lucro", lucro), ("ret", retorno), ("qual", qualidade)):
        if _num(v) is not None:
            h[k] = round(_num(v), 3)
    d["itens"] = ([h] + d["itens"])[:MAX]
    return d, True


_RES_TICKER = {"v": "vitoria", "e": "empate", "d": "derrota"}


def montar(trade_pessoal: dict | None, placar: dict | None, ticker_hist: list | None) -> dict:
    """Resposta de GET /jogos/historico: as partidas dos dois jogos, da mais nova para a mais antiga, e o resumo de cada um."""
    trade = [dict(h) for h in ((trade_pessoal or {}).get("itens") or []) if isinstance(h, dict)]
    vistos = {h["id"] for h in trade}
    for h in (((placar or {}).get("trade") or {}).get("hist") or []):        # partidas online antigas, de antes do histórico pessoal
        if isinstance(h, dict) and h.get("id") and h["id"] not in vistos:
            trade.append({"id": h["id"], "em": h.get("em"), "modo": "online", "n": h.get("n"), "pos": h.get("pos"), "pontos": h.get("pts"),
                          "formato": h.get("formato"), **({"lucro": h["lucro"], "ret": h["ret"]} if "lucro" in h else {}),
                          **({"qual": h["qual"]} if "qual" in h else {})})
    for h in trade:
        h["resultado"] = ("vitoria" if h.get("pos") == 1 else "derrota") if h.get("modo") == "online" and h.get("pos") else None
    trade.sort(key=lambda h: str(h.get("em") or ""), reverse=True)

    ticker = []
    for h in (ticker_hist or []):
        if isinstance(h, dict) and h.get("id"):
            ticker.append({"id": h["id"], "em": str(h.get("ts") or "")[:16].replace("T", " "), "modo": h.get("modo") or "solo",
                           "resultado": h.get("final"), "placar": h.get("placar"),
                           "rodadas": [{"jog": r.get("nome_jog") or r.get("jog"), "adv": r.get("nome_adv") or r.get("adv"), "ind": r.get("ind"),
                                        "venc": r.get("venc") or r.get("vencedor")} for r in (h.get("rodadas") or []) if isinstance(r, dict)]})
    vistos = {h["id"] for h in ticker}
    for h in (((placar or {}).get("ticker") or {}).get("hist") or []):
        if isinstance(h, dict) and h.get("id") and h["id"] not in vistos:
            ticker.append({"id": h["id"], "em": h.get("em"), "modo": h.get("modo") or "online", "resultado": _RES_TICKER.get(h.get("r")),
                           "placar": None, "rodadas": []})
    ticker.sort(key=lambda h: str(h.get("em") or ""), reverse=True)

    def resumo(itens, chave="resultado"):
        r = {"total": len(itens), "vitoria": 0, "empate": 0, "derrota": 0}
        for h in itens:
            if h.get(chave) in r:
                r[h[chave]] += 1
        return r
    rt = resumo(trade)
    pts = [h["pontos"] for h in trade if isinstance(h.get("pontos"), (int, float))]
    rt["melhor"] = max(pts) if pts else None
    return {"trade": trade[:MAX], "ticker": ticker[:MAX], "resumo": {"trade": rt, "ticker": resumo(ticker)}}
