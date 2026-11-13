"""Ticker Battle Online · regras puras da partida entre dois jogadores (sem Streamlit e sem banco).

Tudo aqui é função de (estado, jogada, relógio) -> novo estado, para que o servidor valide e calcule sozinho:
o navegador só diz "qual carta" e "qual atributo". As comparações reutilizam battle.resolver (mesmas regras do Duelo contra o Sistema).

Estado `d` (guardado em bt_partidas.dados): lados "a" (quem criou/esperava) e "b" (quem entrou).
Escolhas são secretas: `visao()` nunca devolve a escolha do adversário antes da revelação.
"""
from __future__ import annotations

import copy
import hashlib
import secrets
from datetime import date, datetime, timedelta, timezone

import battle as B

PRAZO_RECONEXAO_S = 60        # sem sinal do jogador por este tempo -> o adversário vence por abandono (configurável)
LIMITE_RODADA_S = 180         # com um dos dois já confirmado, quem não confirma em 180 s perde por tempo esgotado (configurável)
SINAL_PERDIDO_S = 12          # a partir daqui a tela mostra "adversário desconectado" (ainda dentro do prazo)
ALFABETO_CODIGO = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"      # sem 0/O/1/I/L para não confundir
TAM_CODIGO = 6
FASES = ("aguardando", "pronta", "em_jogo", "finalizada", "cancelada")
ATIVAS = ("aguardando", "pronta", "em_jogo")
LADOS = ("a", "b")
BRT = timezone(timedelta(hours=-3))


class ErroPartida(ValueError):
    """Jogada ou ação inválida (mensagem pode ser mostrada à pessoa)."""


def iso(t: datetime) -> str:
    return t.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def de_iso(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None


def hoje_de(agora: datetime) -> date:
    return agora.astimezone(BRT).date()


def outro(lado: str) -> str:
    return "b" if lado == "a" else "a"


def gerar_codigo() -> str:
    return "".join(secrets.choice(ALFABETO_CODIGO) for _ in range(TAM_CODIGO))


def normalizar_codigo(txt: str) -> str:
    c = "".join(ch for ch in str(txt or "").upper() if ch.isalnum())
    return c if len(c) == TAM_CODIGO and all(ch in ALFABETO_CODIGO for ch in c) else ""


# ------------------------------------------------------------------ criação
def novo(partida_id: str, a_email: str, a_nick: str, deck_a: list[str], agora: datetime, prazo_s: int = PRAZO_RECONEXAO_S) -> dict:
    return {
        "v": 1, "id": partida_id, "seed": secrets.token_hex(8), "rodadas": B.RODADAS, "prazo_s": int(prazo_s), "limite_rodada_s": LIMITE_RODADA_S,
        "fase": "aguardando",
        "jog": {"a": {"email": a_email, "nick": a_nick, "deck": list(deck_a)}, "b": None},
        "cartas": {}, "ref": "",
        "pronto": {"a": False, "b": False}, "vis": {"a": iso(agora), "b": None},
        "rod": 1, "usadas": {"a": [], "b": []}, "esc": {"a": None, "b": None}, "esc_em": None,
        "reg": [], "placar": {"a": 0, "b": 0, "emp": 0}, "final": None, "criada": iso(agora),
    }


def lado_de(d: dict, email: str) -> str | None:
    for l in LADOS:
        j = d["jog"].get(l)
        if j and j["email"] == email:
            return l
    return None


def entrar(d: dict, b_email: str, b_nick: str, deck_b: list[str], snapshot: dict, agora: datetime, ref: str = "") -> dict:
    """Segundo jogador entra (sala privada ou fila). Valida os dois baralhos contra o snapshot do servidor e CONGELA as cartas."""
    if d["fase"] != "aguardando" or d["jog"]["b"] is not None:
        raise ErroPartida("Esta sala já está completa ou foi encerrada.")
    if d["jog"]["a"]["email"] == b_email:
        raise ErroPartida("Você não pode entrar na sua própria sala.")
    h = hoje_de(agora)
    for l, deck in (("a", d["jog"]["a"]["deck"]), ("b", deck_b)):
        ok, msg = B.validar_baralho(deck, snapshot, h)
        if not ok:
            raise ErroPartida(("O baralho do adversário não está válido agora." if l == "a" else msg))
    n = copy.deepcopy(d)
    n["jog"]["b"] = {"email": b_email, "nick": b_nick, "deck": list(deck_b)}
    n["cartas"] = {t: copy.deepcopy(snapshot[t]) for t in sorted(set(d["jog"]["a"]["deck"]) | set(deck_b))}
    n["ref"] = ref
    n["fase"] = "pronta"
    n["vis"]["b"] = iso(agora)
    return n


# ------------------------------------------------------------------ presença e prazos (relógio do servidor)
def batida(d: dict, lado: str, agora: datetime) -> dict:
    n = copy.deepcopy(d)
    n["vis"][lado] = iso(agora)
    return n


def segundos_sem_sinal(d: dict, lado: str, agora: datetime) -> float | None:
    t = de_iso(d["vis"].get(lado))
    return None if t is None else max(0.0, (agora - t).total_seconds())


def _encerrar(d: dict, venc: str | None, motivo: str, agora: datetime) -> dict:
    n = copy.deepcopy(d)
    n["final"] = {"venc": venc, "motivo": motivo, "em": iso(agora)}
    n["fase"] = "finalizada" if venc is not None or motivo != "cancelada" else "cancelada"
    n["esc"] = {"a": None, "b": None}
    return n


def avaliar_prazos(d: dict, agora: datetime) -> dict:
    """Aplica as regras de tempo do SERVIDOR: abandono por falta de sinal e rodada parada. Devolve o mesmo estado se nada venceu."""
    if d["fase"] not in ("pronta", "em_jogo"):
        return d
    p = d.get("prazo_s", PRAZO_RECONEXAO_S)
    sa, sb = segundos_sem_sinal(d, "a", agora), segundos_sem_sinal(d, "b", agora)
    ra, rb = (sa or 0) > p, (sb or 0) > p
    if ra and rb:
        return _encerrar(d, None, "cancelada", agora)
    if ra:
        return _encerrar(d, "b", "abandono", agora)
    if rb:
        return _encerrar(d, "a", "abandono", agora)
    if d["fase"] == "pronta":
        t1 = de_iso(d.get("pronto_em"))
        if t1 and sum(d["pronto"].values()) == 1 and (agora - t1).total_seconds() > d.get("limite_rodada_s", LIMITE_RODADA_S):
            return _encerrar(d, None, "cancelada", agora)        # um ficou pronto e o outro não apareceu para confirmar: cancela sem vencedor
    if d["fase"] == "em_jogo":
        t0 = de_iso(d.get("esc_em"))
        feitos = [l for l in LADOS if d["esc"][l]]
        if t0 and len(feitos) == 1 and (agora - t0).total_seconds() > d.get("limite_rodada_s", LIMITE_RODADA_S):
            return _encerrar(d, feitos[0], "tempo", agora)
    return d


# ------------------------------------------------------------------ sala de espera
def marcar_pronto(d: dict, lado: str, agora: datetime) -> dict:
    if d["fase"] != "pronta":
        raise ErroPartida("A partida não está na sala de espera.")
    n = copy.deepcopy(d)
    n["pronto"][lado] = True
    n.setdefault("pronto_em", iso(agora))
    if all(n["pronto"].values()):
        n["fase"] = "em_jogo"
    return n


# ------------------------------------------------------------------ rodada
def cartas_livres(d: dict, lado: str) -> list[str]:
    return [t for t in d["jog"][lado]["deck"] if t not in d["usadas"][lado]]


def atributos_da_carta(d: dict, tk: str) -> list[str]:
    c = d["cartas"].get(tk)
    return B.indicadores_validos(c) if c else []


def escolher(d: dict, lado: str, tk: str, ind: str, agora: datetime) -> dict:
    """Confirma a jogada do lado (imutável depois). Se o outro já confirmou, a rodada é resolvida aqui mesmo, no servidor."""
    if d["fase"] != "em_jogo" or d["final"]:
        raise ErroPartida("A partida não está em andamento.")
    if d["esc"][lado] is not None:
        raise ErroPartida("Sua jogada desta rodada já foi confirmada e não pode ser alterada.")
    if tk not in cartas_livres(d, lado):
        raise ErroPartida("Carta indisponível nesta rodada.")
    if ind not in atributos_da_carta(d, tk):
        raise ErroPartida("Atributo sem dado válido nesta carta.")
    n = copy.deepcopy(d)
    n["esc"][lado] = {"tk": tk, "ind": ind, "em": iso(agora)}
    if n["esc_em"] is None:
        n["esc_em"] = iso(agora)
    if n["esc"]["a"] and n["esc"]["b"]:
        n = resolver_rodada(n, agora)
    return n


def _lado_vencedor(res: dict, quem_e_a: bool) -> str:
    """res vem de B.resolver(x, y, ...): 'jogador' = x. Converte para 'a'/'b'/'empate' sabendo se x é o lado a."""
    if res["venc"] == "empate":
        return "empate"
    x_vence = res["venc"] == "jogador"
    return ("a" if x_vence else "b") if quem_e_a else ("b" if x_vence else "a")


def resolver_rodada(d: dict, agora: datetime) -> dict:
    """Regra do prompt: mesmo atributo -> comparação normal. Atributos diferentes -> cada atributo é avaliado sobre as MESMAS duas cartas;
    cada jogador precisa vencer o que escolheu; se só um vencer, ele leva a rodada; os dois venceram ou os dois perderam = empate.
    Empate numérico num atributo não é vitória. Comparação inválida/incompatível nunca dá ponto: a rodada empata e o motivo fica registrado."""
    ea, eb = d["esc"]["a"], d["esc"]["b"]
    ca, cb = d["cartas"][ea["tk"]], d["cartas"][eb["tk"]]
    h = hoje_de(agora)
    reg = {"n": d["rod"], "a": {"tk": ea["tk"], "ind": ea["ind"], "ref": ca.get("ref")}, "b": {"tk": eb["tk"], "ind": eb["ind"], "ref": cb.get("ref")},
           "cmp": [], "venc": "empate", "motivo": ""}
    try:
        if ea["ind"] == eb["ind"]:
            r = B.resolver(ca, cb, ea["ind"], h)
            reg["cmp"].append({"ind": ea["ind"], "va": r["va"], "vb": r["vb"], "venc": _lado_vencedor(r, True), "barra_a": r["barra_a"], "de": "ambos"})
            reg["venc"] = reg["cmp"][0]["venc"]
        else:
            ra = B.resolver(ca, cb, ea["ind"], h)            # atributo de A sobre as duas cartas (A à esquerda)
            rb = B.resolver(cb, ca, eb["ind"], h)            # atributo de B sobre as duas cartas (B à esquerda)
            va = _lado_vencedor(ra, True)
            vb = _lado_vencedor(rb, False)
            reg["cmp"].append({"ind": ea["ind"], "va": ra["va"], "vb": ra["vb"], "venc": va, "barra_a": ra["barra_a"], "de": "a"})
            reg["cmp"].append({"ind": eb["ind"], "va": rb["vb"], "vb": rb["va"], "venc": vb, "barra_a": 1 - rb["barra_a"], "de": "b"})
            a_ok, b_ok = va == "a", vb == "b"
            reg["venc"] = "a" if (a_ok and not b_ok) else ("b" if (b_ok and not a_ok) else "empate")
            if reg["venc"] == "empate":
                reg["motivo"] = "os dois venceram o próprio atributo" if (a_ok and b_ok) else "nenhum venceu o próprio atributo"
    except ValueError as e:
        reg["cmp"], reg["venc"], reg["motivo"] = [], "empate", f"comparação inválida: {e}"
    n = copy.deepcopy(d)
    n["reg"].append(reg)
    n["usadas"]["a"].append(ea["tk"])
    n["usadas"]["b"].append(eb["tk"])
    n["placar"]["emp" if reg["venc"] == "empate" else reg["venc"]] += 1
    n["esc"], n["esc_em"] = {"a": None, "b": None}, None
    n["rod"] += 1
    if len(n["reg"]) >= n["rodadas"]:
        p = n["placar"]
        venc = "a" if p["a"] > p["b"] else ("b" if p["b"] > p["a"] else None)
        n = _encerrar(n, venc, "normal", agora)
        n["fase"] = "finalizada"
    return n


# ------------------------------------------------------------------ o que cada jogador pode ver
def visao(d: dict, lado: str, agora: datetime) -> dict:
    """Recorte seguro para o jogador `lado`: nunca inclui a escolha pendente do adversário nem as cartas dele que ainda não foram jogadas."""
    o = outro(lado)
    eu, op = d["jog"][lado], d["jog"].get(o)
    jogou_op = set(d["usadas"][o])
    fim = d["fase"] in ("finalizada", "cancelada")
    reg = []
    for r in d["reg"]:
        reg.append({**copy.deepcopy(r), "eu": r[lado], "op": r[o]})
    cartas = {t: c for t, c in d["cartas"].items() if t in eu["deck"] or t in jogou_op}
    return {
        "id": d["id"], "fase": d["fase"], "lado": lado, "rod": min(d["rod"], d["rodadas"]), "rodadas": d["rodadas"], "prazo_s": d.get("prazo_s", PRAZO_RECONEXAO_S),
        "eu": {"nick": eu["nick"], "deck": list(eu["deck"]), "usadas": list(d["usadas"][lado]), "pronto": d["pronto"][lado], "escolha": d["esc"][lado]},
        "op": ({"nick": op["nick"], "usadas": list(d["usadas"][o]), "pronto": d["pronto"][o], "confirmou": bool(d["esc"][o]),
                "sem_sinal": segundos_sem_sinal(d, o, agora), "n_deck": len(op["deck"])} if op else None),
        "placar": {"eu": d["placar"][lado], "op": d["placar"][o], "emp": d["placar"]["emp"]},
        "reg": reg, "cartas": cartas, "ref": d.get("ref", ""),
        "final": ({**d["final"], "resultado": ("empate" if d["final"]["venc"] is None else ("vitoria" if d["final"]["venc"] == lado else "derrota"))} if d["final"] else None),
        "encerrada": fim,
    }


def registro_historico(d: dict, lado: str) -> dict:
    """Linha de histórico/Raio-X para o jogador `lado`, com o snapshot das cartas e dos valores usados (reproduzível depois)."""
    v = visao(d, lado, de_iso(d["final"]["em"]) or datetime.now(timezone.utc))
    o = outro(lado)
    return {"id": d["id"], "em": d["final"]["em"], "resultado": v["final"]["resultado"], "motivo": d["final"]["motivo"],
            "lado": lado, "eu": d["jog"][lado]["nick"], "op": d["jog"][o]["nick"], "placar": v["placar"], "ref": d.get("ref", ""),
            "rodadas": v["reg"], "cartas": {t: d["cartas"][t] for t in d["cartas"] if t in d["usadas"]["a"] + d["usadas"]["b"]}}


def resumo_rodada(r: dict, cartas: dict) -> dict:
    """Texto para o Raio-X: reaproveita B.explicar para cada atributo avaliado."""
    out = []
    for c in r["cmp"]:
        reg = {"ind": c["ind"], "jog": r["a"]["tk"], "adv": r["b"]["tk"], "va": c["va"], "vb": c["vb"], "venc": {"a": "jogador", "b": "adversario", "empate": "empate"}[c["venc"]],
               "melhor": B.INDICADORES[c["ind"]]["melhor"], "n": r["n"]}
        out.append({**B.explicar(reg, cartas), "de": c["de"]})
    return {"itens": out}
