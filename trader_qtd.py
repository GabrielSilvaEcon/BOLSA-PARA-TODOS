"""Trade Battle · partida corrida com quantidade livre (regras puras: sem Streamlit, sem rede, sem banco).

Regras (combinadas com o dono do app, nov/2026):
 · o capital da partida é 5% do saldo disponível (caixa livre) da Carteira no início da partida;
 · a quantidade é livre (ações inteiras): o valor aplicado AO MESMO TEMPO (posição aberta + ordens que ainda vão executar) não passa do
   capital da partida mais o resultado já realizado. Dá para aumentar a posição várias vezes até o teto; encerrar ou reduzir libera o capital;
 · vender com posição comprada reduz ou zera a posição (não inverte: para virar vendido, encerre e venda de novo). Sem posição, vender abre
   uma venda a descoberto com o mesmo teto (1x, sem alavancagem);
 · execução honesta: a ordem a mercado executa na ABERTURA do próximo candle (nunca num preço que já passou); stop e alvo executam no nível
   ou, se o candle abrir além dele (gap), na abertura; a ordem limite só executa se o preço chegar nela;
 · taxa da B3 sobre cada execução (compra e venda);
 · a perda da partida nunca passa do capital: se o prejuízo (realizado + aberto) chegar a ele, a posição é encerrada e não há mais entradas.

O estado é recalculado do zero a partir das ações gravadas (`simular`), como na mesa antiga. `trades` usa os mesmos campos da mesa antiga
(entrada, saida, i_exc, i_saida, ret, com_stop...) para a pontuação e o desenho continuarem iguais; `ret` = resultado ÷ capital da partida.
"""
from __future__ import annotations

import math

PCT_CAPITAL = 0.05             # capital da partida = 5% do caixa livre da Carteira
TAXA_B3 = 0.0003               # ≈0,03% do valor de cada execução (emolumentos e liquidação)
Q_MAX = 10_000_000             # teto técnico de ações por ordem (protege contra número absurdo)
EPS = 1e-9
TIPOS_ENTRADA = ("mercado", "limite", "stop_entrada")


class ErroQtd(ValueError):
    """Ordem que não cabe nas regras (o registro recusa antes de gravar)."""


def _lado(direcao: str) -> int:
    return 1 if direcao == "alta" else -1


def _lado_ok(direcao: str, campo: str, preco: float, ref: float) -> bool:
    if campo == "stop":
        return preco < ref if _lado(direcao) == 1 else preco > ref
    return preco > ref if _lado(direcao) == 1 else preco < ref


def capital_da_partida(caixa_livre: float) -> float:
    return round(max(0.0, float(caixa_livre)) * PCT_CAPITAL, 2)


# ------------------------------------------------------------------ estado
def _novo(cap: float, taxa: float) -> dict:
    return {"cap": float(cap), "taxa": float(taxa), "pos": None, "pend": None, "mkt": [], "trades": [], "ignoradas": 0, "bloq": False,
            "taxas": 0.0, "limite_x": 1.0}


def realizado(st: dict) -> float:
    return sum(t["pnl"] for t in st["trades"])


def aberto(st: dict, px: float) -> float:
    """Resultado da posição aberta no preço `px`, já descontada a taxa paga na entrada (a da saída só entra quando ela acontece)."""
    p = st["pos"]
    if not p:
        return 0.0
    return _lado(p["direcao"]) * (px - p["entrada"]) * p["q"] - p["taxa_ent"]


def poder(st: dict) -> float:
    """Quanto a partida pode ter aplicado ao mesmo tempo: o capital mais o resultado já realizado (prejuízo reduz, lucro aumenta)."""
    return max(0.0, st["cap"] + realizado(st))


def comprometido(st: dict, px: float, direcao: str | None = None) -> float:
    """Valor já aplicado ou reservado: posição aberta (no preço `px`), ordens a mercado que vão abrir/aumentar e a ordem de entrada pendente."""
    tot = 0.0
    p = st["pos"]
    if p:
        tot += p["q"] * px
    for o in st["mkt"]:
        if o["kind"] == "abre":
            tot += o["q"] * px
    pe = st["pend"]
    if pe:
        tot += pe["q"] * pe["preco"]
    return tot


def max_qtd(st: dict, px: float) -> int:
    """Quantas ações ainda cabem numa nova compra/venda a mercado no preço `px` (com a taxa)."""
    livre = poder(st) - comprometido(st, px)
    if px <= 0 or livre <= 0:
        return 0
    return max(0, int(math.floor(livre / (px * (1 + st["taxa"])) + EPS)))


def _checa_limite(st: dict) -> None:
    if realizado(st) <= -st["cap"] + EPS:
        st["bloq"] = True
        st["pend"] = None
        st["mkt"] = [o for o in st["mkt"] if o["kind"] == "fecha"]


def _abrir(st: dict, direcao: str, q: int, px: float, i: int, tipo: str, stop, alvo) -> None:
    taxa = st["taxa"] * q * px
    st["taxas"] += taxa
    p = st["pos"]
    if p is None:
        st["pos"] = {"direcao": direcao, "q": int(q), "entrada": float(px), "i_entrada": i, "i_exc": i, "tipo_entrada": tipo, "stop": stop, "alvo": alvo,
                     "com_stop": stop is not None, "taxa_ent": taxa}
        return
    tot = p["q"] + q                                           # aumentar a posição: novo preço médio
    p["entrada"] = (p["entrada"] * p["q"] + px * q) / tot
    p["q"] = int(tot)
    p["taxa_ent"] += taxa
    if stop is not None:
        p["stop"], p["com_stop"] = stop, True
    if alvo is not None:
        p["alvo"] = alvo


def _fechar(st: dict, q: int, px: float, i: int, motivo: str) -> None:
    p = st["pos"]
    q = int(min(q, p["q"]))
    if q <= 0:
        return
    taxa_sai = st["taxa"] * q * px
    parte_ent = p["taxa_ent"] * q / p["q"]
    bruto = _lado(p["direcao"]) * (px - p["entrada"]) * q
    pnl = bruto - taxa_sai - parte_ent
    st["taxas"] += taxa_sai
    st["trades"].append({"n": len(st["trades"]) + 1, "direcao": p["direcao"], "q": q, "entrada": p["entrada"], "i_entrada": p["i_entrada"], "i_exc": p["i_exc"],
                         "tipo_entrada": p["tipo_entrada"], "saida": float(px), "i_saida": i, "motivo": motivo, "pnl": round(pnl, 2),
                         "ret": pnl / st["cap"] if st["cap"] > 0 else 0.0, "com_stop": p["com_stop"], "taxas": round(taxa_sai + parte_ent, 2)})
    p["q"] -= q
    p["taxa_ent"] -= parte_ent
    if p["q"] <= 0:
        st["pos"] = None
    _checa_limite(st)


def nivel_limite(st: dict) -> float | None:
    """Preço em que a perda da partida (realizada + aberta) chega ao capital: age como um stop implícito."""
    p = st["pos"]
    if not p or p["q"] <= 0:
        return None
    folga = st["cap"] + realizado(st) - p["taxa_ent"]
    nivel = p["entrada"] - folga / p["q"] if _lado(p["direcao"]) == 1 else p["entrada"] + folga / p["q"]
    return nivel if nivel > 0 else None


# ------------------------------------------------------------------ ações e candles
def _aplicar(st: dict, a: dict, px: float, i: int) -> None:
    """Ação tomada com i candles revelados (px = último fechamento). Ordens a mercado ficam na fila e executam na abertura do candle i."""
    t = a["tipo"]
    p = st["pos"]
    if t in TIPOS_ENTRADA:
        q = int(a.get("q") or 0)
        reduz = p is not None and a["direcao"] != p["direcao"]
        if q <= 0 or (st["bloq"] and not reduz):
            st["ignoradas"] += 1
            return
        if t == "mercado":
            st["mkt"].append({"kind": "fecha" if reduz else "abre", "direcao": a["direcao"], "q": q, "stop": a.get("stop"), "alvo": a.get("alvo"), "i_env": i})
        else:
            if st["pend"] or reduz:
                st["ignoradas"] += 1
                return
            st["pend"] = {"tipo": t, "direcao": a["direcao"], "preco": a["preco"], "q": q, "stop": a.get("stop"), "alvo": a.get("alvo"), "ordem": a["ordem"]}
    elif t in ("definir_stop", "mover_stop", "definir_alvo", "mover_alvo"):
        campo = "stop" if t.endswith("stop") else "alvo"
        o = p or st["pend"]
        if o is None or not _lado_ok(o["direcao"], campo, a["preco"], px if p else o["preco"]):
            st["ignoradas"] += 1
            return
        o[campo] = a["preco"]
        if campo == "stop" and p:
            p["com_stop"] = True
    elif t == "cancelar":
        o = a.get("qual")
        if o in ("entrada", "todas"):
            st["pend"] = None
        alvo_o = p or st["pend"]
        if alvo_o is not None:
            if o in ("stop", "todas"):
                alvo_o["stop"] = None
            if o in ("alvo", "todas"):
                alvo_o["alvo"] = None
    elif t == "encerrar":
        if p:
            st["mkt"].append({"kind": "fecha", "direcao": "baixa" if p["direcao"] == "alta" else "alta", "q": p["q"], "stop": None, "alvo": None, "i_env": i, "tudo": True})
        else:
            st["ignoradas"] += 1


def _executar_mercado(st: dict, k: dict, i: int) -> None:
    fila, st["mkt"] = st["mkt"], []
    for o in fila:
        p = st["pos"]
        px = k["o"]
        if o["kind"] == "fecha":
            if p is None:
                continue
            _fechar(st, p["q"] if o.get("tudo") else o["q"], px, i, "manual")
            continue
        if st["bloq"]:
            continue
        if p is not None and p["direcao"] != o["direcao"]:      # a posição virou entre o envio e a execução: não inverte
            st["ignoradas"] += 1
            continue
        # o teto é conferido de novo na execução (a abertura pode ter saltado): o que não couber é reduzido ao que cabe
        livre = poder(st) - comprometido(st, px)
        q = min(int(o["q"]), max(0, int(math.floor(livre / (px * (1 + st["taxa"])) + EPS))))
        if q <= 0:
            st["ignoradas"] += 1
            continue
        _abrir(st, o["direcao"], q, px, i, "mercado", o.get("stop"), o.get("alvo"))


def _candle(st: dict, k: dict, i: int) -> None:
    if st["mkt"]:
        _executar_mercado(st, k, i)
    pe = st["pend"]
    if pe and not st["bloq"]:
        lado, nivel, fill = _lado(pe["direcao"]), pe["preco"], None
        if pe["tipo"] == "limite":
            if lado == 1 and k["l"] <= nivel:
                fill = min(k["o"], nivel)
            elif lado == -1 and k["h"] >= nivel:
                fill = max(k["o"], nivel)
        else:
            if lado == 1 and k["h"] >= nivel:
                fill = max(k["o"], nivel)
            elif lado == -1 and k["l"] <= nivel:
                fill = min(k["o"], nivel)
        if fill is not None:
            st["pend"] = None
            p = st["pos"]
            if p is None or p["direcao"] == pe["direcao"]:
                _abrir(st, pe["direcao"], pe["q"], fill, i, pe["tipo"], pe.get("stop"), pe.get("alvo"))
    p = st["pos"]
    if p is None:
        return
    lado, stop, alvo, motivo = _lado(p["direcao"]), p["stop"], p["alvo"], "stop"
    lim = nivel_limite(st)
    if lim is not None and (stop is None or (lim > stop if lado == 1 else lim < stop)):
        stop, motivo = lim, "limite"
    bateu_stop = stop is not None and (k["l"] <= stop if lado == 1 else k["h"] >= stop)
    bateu_alvo = alvo is not None and (k["h"] >= alvo if lado == 1 else k["l"] <= alvo)
    if bateu_stop:                                             # stop e alvo no mesmo candle: vale o stop
        gap = k["o"] <= stop if lado == 1 else k["o"] >= stop
        _fechar(st, p["q"], k["o"] if gap else stop, i, motivo)
    elif bateu_alvo:
        gap = k["o"] >= alvo if lado == 1 else k["o"] <= alvo
        _fechar(st, p["q"], k["o"] if gap else alvo, i, "alvo")


def simular(candles: list[dict], acoes: list[dict], preco_ref: float, cap: float, final: bool = False, taxa: float = TAXA_B3) -> dict:
    """Estado de UM jogador a partir dos candles existentes (na visão, só os revelados) e das ações dele, na ordem de processamento.
    final=True: fim da partida (a posição aberta sai no último fechamento; ordens que não executaram expiram)."""
    n = len(candles)
    st = _novo(cap, taxa)
    por_i: dict[int, list] = {}
    for a in sorted(acoes, key=lambda x: x["ordem"]):
        por_i.setdefault(min(max(int(a["n_rev"]), 0), n), []).append(a)
    px = float(preco_ref)
    for i in range(n + 1):
        for a in por_i.get(i, ()):
            _aplicar(st, a, px, i)
        if i == n:
            break
        _candle(st, candles[i], i)
        px = candles[i]["c"]
    if final:
        if st["pos"]:
            _fechar(st, st["pos"]["q"], px, n - 1, "fim")
        st["pend"], st["mkt"] = None, []
    st["preco_atual"] = px
    return st


# ------------------------------------------------------------------ validação (antes de gravar)
def _q(d: dict) -> int:
    try:
        q = int(d.get("q"))
    except (TypeError, ValueError):
        raise ErroQtd("informe a quantidade de ações")
    if isinstance(d.get("q"), float) and d["q"] != q:
        raise ErroQtd("a quantidade é um número inteiro de ações")
    if not 1 <= q <= Q_MAX:
        raise ErroQtd("informe a quantidade de ações")
    return q


def validar(d: dict, st: dict, px: float, n: int, nr: int, preco_obrig) -> dict | None:
    """Valida as ordens de entrada/redução (quantidade, teto e lado). Para os outros tipos devolve None (a mesa antiga valida igual)."""
    t = d.get("tipo") if isinstance(d, dict) else None
    if t not in TIPOS_ENTRADA:
        return None
    dirc = d.get("direcao")
    if dirc not in ("alta", "baixa"):
        raise ErroQtd("escolha comprar ou vender")
    if n >= nr:
        raise ErroQtd("a partida acabou: não dá mais para operar")
    q = _q(d)
    p = st["pos"]
    if p is not None and dirc != p["direcao"]:                     # vender comprado / comprar vendido = reduzir ou zerar
        if t != "mercado":
            raise ErroQtd("para reduzir a posição use a ordem a mercado (limite e stop servem para abrir ou aumentar)")
        ja = sum(o["q"] for o in st["mkt"] if o["kind"] == "fecha")
        resta = p["q"] - ja
        if q > resta:
            acao = "vender" if p["direcao"] == "alta" else "comprar"
            raise ErroQtd(f"você tem {resta} ações para {acao}: para inverter a posição, encerre e abra de novo")
        return {"tipo": "mercado", "direcao": dirc, "q": q}
    if st["bloq"]:
        raise ErroQtd("a perda da partida chegou ao capital: não dá mais para abrir posição")
    out = {"tipo": t, "direcao": dirc, "q": q}
    ref = px
    if t != "mercado":
        if st["pend"]:
            raise ErroQtd("você já tem uma ordem de entrada pendente: cancele-a antes")
        ref = out["preco"] = preco_obrig(d)
        if t == "limite":
            ok, msg = (ref < px, "a compra limite precisa ficar abaixo do preço atual") if dirc == "alta" else (ref > px, "a venda limite precisa ficar acima do preço atual")
        else:
            ok, msg = (ref > px, "a compra stop precisa ficar acima do preço atual") if dirc == "alta" else (ref < px, "a venda stop precisa ficar abaixo do preço atual")
        if not ok:
            raise ErroQtd(msg)
    livre = poder(st) - comprometido(st, px)
    if q * ref * (1 + st["taxa"]) > livre + EPS:
        mx = max(0, int(math.floor(livre / (ref * (1 + st["taxa"])) + EPS)))
        raise ErroQtd(f"passa do capital da partida: cabem no máximo {mx} ações agora" if mx else "o capital da partida já está todo aplicado: encerre ou reduza a posição para entrar de novo")
    for campo in ("stop", "alvo"):
        if d.get(campo) in (None, ""):
            continue
        v = preco_obrig(d, campo)
        if not _lado_ok(dirc, campo, v, ref):
            raise ErroQtd(f"o {campo} está do lado errado da entrada" + (" (stop abaixo e alvo acima)" if dirc == "alta" else " (alvo abaixo e stop acima)"))
        out[campo] = v
    return out


# ------------------------------------------------------------------ financeiro e visão
def financeiro(trades: list[dict], ap: dict | None) -> dict | None:
    """Efeito em dinheiro da partida (vai para a Carteira): soma de todas as operações, com as taxas."""
    if not ap:
        return None
    cap, pat = float(ap["stake"]), float(ap["pat"])
    pnl = round(sum(t["pnl"] for t in trades), 2)
    return {"aposta": cap, "pnl": pnl, "pct_aposta": round(pnl / cap * 100, 3) if cap > 0 else 0.0, "pct_pat": round(pnl / pat * 100, 4) if pat > 0 else 0.0,
            "pat_ini": pat, "operou": bool(trades), "n_ops": len(trades), "taxas": round(sum(t.get("taxas", 0.0) for t in trades), 2),
            "ops": [{"n": t["n"], "pnl": t["pnl"], "pct": round(t["ret"] * 100, 3), "q": t["q"]} for t in trades]}


def _cor(v: float) -> str:
    return "zero" if abs(v) < 0.005 else ("up" if v > 0 else "down")


def _txt_val(v: float) -> str:
    s = f"{abs(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("+" if v > 0.004 else "−" if v < -0.004 else "") + "T$ " + s


def visao(st: dict, ini: int, ativo: bool, n: int, nr: int, n_acoes: int, max_acoes: int, pat: float | None) -> dict:
    """Mesa privada do jogador no formato que a tela já entende, mais os campos da quantidade."""
    cap, px, pos, pend = st["cap"], st["preco_atual"], st["pos"], st["pend"]
    real, ab = realizado(st), aberto(st, px)
    ordens = []
    if pend:
        ordens.append({"id": "entrada", "tipo": pend["tipo"], "direcao": pend["direcao"], "preco": pend["preco"], "q": pend["q"]})
    base = pos or pend
    if base:
        for c in ("stop", "alvo"):
            if base.get(c) is not None:
                ordens.append({"id": c, "preco": base[c]})
    fila = [{"direcao": o["direcao"], "q": o["q"], "reduz": o["kind"] == "fecha"} for o in st["mkt"]]
    expo = pos["q"] * px if pos else 0.0
    usado = max(0.0, -(real + ab))
    mq = max_qtd(st, px)
    pode = ativo and n < nr and n_acoes < max_acoes
    return {"qtd": True, "preco_atual": px, "stake": cap, "capital": cap, "pat_ini": pat,
            "posicao": None if not pos else {"direcao": pos["direcao"], "preco_entrada": pos["entrada"], "indice_entrada": ini + pos["i_entrada"],
                                             "stop": pos["stop"], "alvo": pos["alvo"], "q": pos["q"]},
            "ordens": ordens, "fila": fila,
            "operacoes": [{"n": t["n"], "direcao": t["direcao"], "q": t["q"], "preco_entrada": t["entrada"], "indice_entrada": ini + t["i_entrada"],
                           "preco_saida": t["saida"], "indice_saida": ini + t["i_saida"], "motivo": t["motivo"], "pct": round(t["ret"] * 100, 3), "val": t["pnl"]}
                          for t in st["trades"]],
            "n_encerradas": len(st["trades"]),
            "realizado_val": round(real, 2), "realizado_pct": round(real / cap * 100, 3) if cap else 0.0,
            "aberto_val": round(ab, 2), "aberto_pct": round(ab / cap * 100, 3) if cap else 0.0,
            "total_val": round(real + ab, 2), "total_pct": round((real + ab) / cap * 100, 3) if cap else 0.0,
            "aberto_txt": _txt_val(ab), "acum_txt": _txt_val(real + ab), "cor_aberto": _cor(ab), "cor_acum": _cor(real + ab),
            "poder": round(max(0.0, poder(st) - comprometido(st, px)), 2), "max_q": mq, "exposicao": round(expo, 2),
            "exposicao_pct": round(expo / cap * 100, 1) if cap else 0.0, "taxas": round(st["taxas"], 2), "taxa": st["taxa"],
            "limite": {"pct_pat": round(cap / pat * 100, 2) if pat else None, "usado_pct_pat": round(usado / pat * 100, 3) if pat else 0.0,
                       "usado_pct_cap": round(usado / cap * 100, 1) if cap else 0.0, "bloqueado": bool(st["bloq"]), "preco": nivel_limite(st)},
            "pode_abrir": bool(pode and not st["bloq"] and mq > 0),
            "pode_reduzir": bool(pode and pos is not None),
            "pode_encerrar": bool(pode and pos is not None),
            "pode_cancelar": bool(ativo and (pend or (pos and (pos["stop"] is not None or pos["alvo"] is not None)))),
            "pode_gerir": bool(ativo and (pos or pend))}
