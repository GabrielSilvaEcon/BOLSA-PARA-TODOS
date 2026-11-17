"""Central de Jogos · placar e rankings do Trade Battle e do Ticker Battle. Lógica pura: sem Streamlit, sem banco e sem rede.

Como se encaixa no que já existe (sem tabela nova e sem segunda infraestrutura):
 · Cada conta tem UM documento `jogos_placar` em monitor_estado (o mesmo lugar dos documentos da Competição e da liga de estudo).
   Só o servidor grava, e só o da própria conta, no fim de cada partida: o navegador nunca envia pontos nem resultado.
 · O ranking de cada jogo é montado na hora a partir de TODOS os documentos, lidos numa única consulta (banco.sis_comp_todos),
   com cache curto na tela. Nunca há consulta por participante.
 · Cada jogo tem o seu ranking e a sua métrica (nada de misturar escalas):
     Trade Battle  → pontos acumulados nas partidas terminadas (a mesma pontuação que o jogo já calcula por rodada).
     Ticker Battle → vitórias (o jogo não cria pontuação própria: o que decide o duelo é o valor real do indicador).
 · Idempotência: cada partida/duelo entra uma vez só (lista dos ids já contados). Repetir a gravação não soma de novo.
 · Sanidade: tudo o que é lido é saneado (tipos, limites); um documento adulterado não distorce o ranking.
 · Identificação pública: só o apelido (o NickName do cadastro, único e já público). Nunca e-mail.
 · Ranking dos Campeões (combinado): estrutura preparada em `JOGOS`/`ranking_campeoes`, DESLIGADO. Sem fórmula arbitrária.
"""
from __future__ import annotations

import hashlib
import math

CH_PLACAR = "jogos_placar"
TRADE, TICKER = "trade", "ticker"
NOME = {TRADE: "Trade Battle", TICKER: "Ticker Battle"}
IDS_GUARDADOS = 300            # ids de partidas já contadas (idempotência); acima disso os mais antigos saem
HIST_MAX = 20                  # linhas de histórico por jogo
TOPO = 100                     # linhas do ranking entregues à tela
PTS_RODADA_MAX = 100.0         # teto do Trade Battle por rodada (o mesmo do motor); usado na sanidade
RODADAS_MAX = 10

# Registro dos jogos. `metrica` é o que ordena o ranking individual. `campeoes` reservado para o ranking combinado futuro:
# quando existir uma regra de normalização aprovada, ela entra aqui (por jogo) e `ranking_campeoes` passa a usá-la.
JOGOS = {
    TRADE: {"nome": NOME[TRADE], "metrica": "pts", "rotulo": "pontos", "campeoes": None},
    TICKER: {"nome": NOME[TICKER], "metrica": "v", "rotulo": "vitórias", "campeoes": None},
}


def _num(v, padrao=0.0) -> float:
    try:
        x = float(v)
        return x if math.isfinite(x) else padrao
    except (TypeError, ValueError):
        return padrao


def _int(v, minimo=0, maximo=10**7) -> int:
    try:
        return max(minimo, min(int(v), maximo))
    except (TypeError, ValueError):
        return minimo


def hash_conta(email: str) -> str:
    """Identificador estável e não reversível da conta (para comparar posições entre dias sem guardar e-mail)."""
    return hashlib.sha256(str(email or "").strip().lower().encode()).hexdigest()[:16]


# ------------------------------------------------------------------ documento da conta
def vazio() -> dict:
    return {"v": 1, "apelido": "", TRADE: {"pts": 0.0, "partidas": 0, "vitorias": 0, "melhor": None, "ids": [], "hist": []},
            TICKER: {"v": 0, "e": 0, "d": 0, "ids": [], "hist": []}}


def sanear(doc) -> dict:
    """Documento com tipos e limites conferidos (vale para o que vem do banco, inclusive se alguém adulterar)."""
    d = doc if isinstance(doc, dict) else {}
    out = vazio()
    out["apelido"] = str(d.get("apelido") or "")[:20]
    t = d.get(TRADE) if isinstance(d.get(TRADE), dict) else {}
    part = _int(t.get("partidas"), 0, 10**6)
    lim = part * RODADAS_MAX * PTS_RODADA_MAX
    out[TRADE].update(pts=round(max(-lim, min(lim, _num(t.get("pts")))), 1), partidas=part, vitorias=_int(t.get("vitorias"), 0, part),
                      melhor=None if t.get("melhor") is None else round(_num(t.get("melhor")), 1),
                      ids=[str(x)[:40] for x in (t.get("ids") or []) if x][-IDS_GUARDADOS:],
                      hist=[h for h in (t.get("hist") or []) if isinstance(h, dict)][:HIST_MAX])
    k = d.get(TICKER) if isinstance(d.get(TICKER), dict) else {}
    out[TICKER].update(v=_int(k.get("v")), e=_int(k.get("e")), d=_int(k.get("d")),
                       ids=[str(x)[:40] for x in (k.get("ids") or []) if x][-IDS_GUARDADOS:],
                       hist=[h for h in (k.get("hist") or []) if isinstance(h, dict)][:HIST_MAX])
    return out


def registrar_trade(doc, pid: str, pontos: float, rodadas: int, formato: str, pos: int | None, n_jog: int, em: str, apelido: str = "") -> tuple[dict, bool]:
    """Soma uma partida TERMINADA do Trade Battle (pontos já calculados pelo servidor). Devolve (doc, mudou). Repetir o mesmo `pid` não soma."""
    d = sanear(doc)
    if apelido:
        d["apelido"] = str(apelido)[:20]
    t = d[TRADE]
    pid = str(pid)[:40]
    if not pid or pid in t["ids"]:
        return d, False
    teto = max(1, min(int(rodadas or 1), RODADAS_MAX)) * PTS_RODADA_MAX
    p = round(max(-teto, min(teto, _num(pontos))), 1)
    venceu = bool(pos == 1 and n_jog >= 2)
    t["pts"] = round(t["pts"] + p, 1)
    t["partidas"] += 1
    t["vitorias"] += int(venceu)
    t["melhor"] = p if t["melhor"] is None else max(t["melhor"], p)
    t["ids"] = (t["ids"] + [pid])[-IDS_GUARDADOS:]
    t["hist"] = ([{"id": pid, "em": str(em)[:16], "pts": p, "formato": str(formato or "")[:10], "pos": pos, "n": int(n_jog)}] + t["hist"])[:HIST_MAX]
    return d, True


def registrar_ticker(doc, did: str, resultado: str, modo: str, em: str, apelido: str = "") -> tuple[dict, bool]:
    """Soma um duelo TERMINADO do Ticker Battle (vitoria | empate | derrota, decidido pelo servidor). Repetir o mesmo `did` não soma."""
    d = sanear(doc)
    if apelido:
        d["apelido"] = str(apelido)[:20]
    k = d[TICKER]
    did = str(did)[:40]
    r = {"vitoria": "v", "empate": "e", "derrota": "d"}.get(str(resultado))
    if not did or not r or did in k["ids"]:
        return d, False
    k[r] += 1
    k["ids"] = (k["ids"] + [did])[-IDS_GUARDADOS:]
    k["hist"] = ([{"id": did, "em": str(em)[:16], "r": r, "modo": str(modo or "")[:10]}] + k["hist"])[:HIST_MAX]
    return d, True


# ------------------------------------------------------------------ rankings
def _linha(jogo: str, email: str, d: dict) -> dict | None:
    if jogo == TRADE:
        t = d[TRADE]
        if not t["partidas"]:
            return None
        return {"valor": t["pts"], "partidas": t["partidas"], "vitorias": t["vitorias"], "desempate": t["melhor"] or 0.0}
    k = d[TICKER]
    n = k["v"] + k["e"] + k["d"]
    if not n:
        return None
    return {"valor": k["v"], "partidas": n, "vitorias": k["v"], "desempate": k["v"] - k["d"]}


def montar_ranking(jogo: str, linhas: list[dict], eu_email: str | None = None, base_pos: dict | None = None) -> dict:
    """Ranking de UM jogo a partir de [{email, dados}] (uma consulta). Ordena pela métrica do jogo; desempate pelo critério do jogo e
    depois pelo apelido. `base_pos` ({hash: posição}) dá a variação desde o início do dia. Entrega só apelido (nunca e-mail)."""
    if jogo not in JOGOS:
        raise ValueError("jogo desconhecido")
    rows = []
    for r in linhas or []:
        d = sanear(r.get("dados"))
        ln = _linha(jogo, r.get("email", ""), d)
        if ln:
            rows.append({**ln, "apelido": d["apelido"] or "Jogador", "h": hash_conta(r.get("email", "")), "eu": bool(eu_email and r.get("email") == eu_email)})
    rows.sort(key=lambda x: (-x["valor"], -x["desempate"], x["apelido"].lower()))
    meu = None
    for i, x in enumerate(rows, 1):
        x["pos"] = i
        ant = (base_pos or {}).get(x["h"])
        x["var"] = (ant - i) if isinstance(ant, int) else None
        if x["eu"]:
            meu = x
    return {"jogo": jogo, "total": len(rows), "linhas": rows[:TOPO], "eu": meu}


def posicoes(ranking: dict) -> dict:
    """{hash: posição} para guardar como base do dia (variação de posição)."""
    return {x["h"]: x["pos"] for x in ranking.get("linhas") or []}


def base_do_dia(snap, hoje: str, ranking: dict) -> tuple[dict, dict | None]:
    """Base das variações: posições da primeira montagem do dia. Devolve (base, snap_novo_para_gravar_ou_None)."""
    s = snap if isinstance(snap, dict) else {}
    if s.get("dia") == hoje and isinstance(s.get("pos"), dict):
        return {k: v for k, v in s["pos"].items() if isinstance(v, int)}, None
    novo = {"dia": hoje, "pos": posicoes(ranking)}
    return novo["pos"], novo


def ranking_entre(jogo: str, linhas: list[dict], emails: set[str], eu_email: str | None = None) -> dict:
    """Ranking de um jogo só entre as contas de `emails` (membros de uma liga de amigos)."""
    return montar_ranking(jogo, [r for r in linhas or [] if r.get("email") in emails], eu_email)


def ranking_campeoes(*_rankings) -> None:
    """Ranking dos Campeões (combinado). Reservado: só será ativado com uma regra de normalização aprovada, cadastrada em
    JOGOS[jogo]["campeoes"]. Enquanto nenhuma regra existir, não há ranking combinado (devolve None) e os rankings individuais
    não são afetados."""
    if any(JOGOS[j]["campeoes"] is None for j in JOGOS):
        return None
    raise NotImplementedError("regra de normalização ainda não definida")


def resumo(d: dict) -> dict:
    """Destaques da conta: pontos e vitórias de cada jogo."""
    d = sanear(d)
    t, k = d[TRADE], d[TICKER]
    return {"trade_pts": t["pts"], "trade_partidas": t["partidas"], "trade_vitorias": t["vitorias"],
            "ticker_v": k["v"], "ticker_e": k["e"], "ticker_d": k["d"], "vitorias": t["vitorias"] + k["v"]}
