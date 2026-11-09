"""Competição de carteiras virtuais — lógica pura (sem Streamlit e sem rede), testável isoladamente.

Regras (resumo; a tela "Competição" mostra o texto completo):
 · Todos começam com o mesmo capital virtual (CAPITAL_INICIAL). Não há aportes nem retiradas: o patrimônio só muda por resultado das
   ordens, proventos e variação de preço. Por isso o retorno % de cada pessoa é exatamente o patrimônio atual dividido pelo capital inicial.
 · O lucro faz o patrimônio crescer e pode ser reinvestido: o caixa (que inclui lucros realizados e proventos) compra mais ativos.
   Opcionalmente, os proventos são reinvestidos sozinhos no mesmo ativo (reinvestimento automático).
 · Ordens são executadas no PREÇO DE FECHAMENTO do dia (ordens feitas até HORA_CORTE valem para o fechamento de hoje; depois dessa hora ou em
   fim de semana, valem para o próximo pregão). Assim ninguém escolhe o preço olhando o movimento do pregão.
 · Só ativos do universo líquido (o fechamento diário publica a lista). Máximo de MAX_PESO do patrimônio em um único ativo.
 · Custo de negociação de CUSTO_OPERACAO em cada compra e venda. Proventos entram no caixa na data "ex"; desdobramentos ajustam a quantidade.
 · O ranking mostra apelido e retorno %. Valores em reais nunca saem da carteira da própria pessoa.
Educacional: carteira virtual, sem dinheiro real, sem recomendação de investimento.
"""
from __future__ import annotations

import copy
import math
import re
import uuid
from datetime import date, datetime, timedelta

CAPITAL_INICIAL = 100_000.0
CUSTO_OPERACAO = 0.0005          # 0,05% por compra e por venda
MAX_PESO = 0.40                  # no máximo 40% do patrimônio em um ativo
MIN_DIAS_RANKING = 1             # pregões de histórico para aparecer no ranking: entra já no primeiro fechamento (subir este número exige mais histórico)
HORA_MEIO_DIA = 12               # ordens enviadas antes das 12h (dias úteis) executam ao preço do meio-dia; de 12h às 17h, no fechamento
HORA_CORTE = 17                  # ordens até as 17h (Brasília) valem para o fechamento do mesmo dia
MIN_DIAS_RISCO = 10              # pregões para calcular Sharpe/volatilidade (com menos, o número é ruído)
RF_ANUAL = 0.0                   # taxa livre de risco usada no Sharpe (0 = Sharpe simples; troque por uma taxa fixa se quiser descontar o CDI)
MAX_PENDENTES = 30
MAX_QTD_ORDEM = 1_000_000
MAX_EXTRATO = 300
MAX_PROCESSADAS = 600
DIAS_ESPERA_SEM_PRECO = 5        # ordem sem preço por tantos dias é recusada

CH_ORDENS = "comp_ordens"        # documento da pessoa (o app grava): apelido, aceite, reinvestimento e ordens pendentes
CH_CARTEIRA = "comp_cart"        # documento da carteira (só o fechamento diário grava): caixa, posições, histórico, extrato
CFG_RANKING = "comp_ranking"     # ranking público (apelido e retorno %) gerado no fechamento
CFG_PRECOS = "comp_precos"       # fechamentos do universo líquido (também gerado no fechamento)

# Fundos imobiliários e ETFs muito líquidos além do catálogo de ações (o fechamento descarta o que não tiver preço).
EXTRAS_LIQUIDOS = ("BOVA11", "IVVB11", "SMAL11", "DIVO11", "HGLG11", "KNRI11", "XPML11", "MXRF11", "VISC11", "XPLG11",
                   "BTLG11", "KNCR11", "HGRU11", "TRXF11", "KNIP11", "RBRR11")

_TICKER = re.compile(r"[A-Z]{4}\d{1,2}")
_APELIDO = re.compile(r"[A-Za-z0-9_.\-]{3,20}")
_RESERVADOS = ("admin", "suporte", "bussola", "moderador", "staff", "oficial")
_BLOQUEADOS = ("caralho", "buceta", "filhadaputa", "merda", "porra", "nazista")


# ------------------------------------------------------------------ identidade
def pregoes(n: int) -> str:
    """'1 pregão' / '5 pregões' (para os textos da tela)."""
    return f"{n} pregão" if n == 1 else f"{n} pregões"


def apelido_valido(apelido: str) -> tuple[bool, str]:
    a = str(apelido or "").strip()
    if not _APELIDO.fullmatch(a):
        return False, "Use de 3 a 20 caracteres: letras, números, ponto, hífen ou sublinhado (sem espaços)."
    base = re.sub(r"[\d_.\-]", "", a.lower())
    if any(r in base for r in _RESERVADOS):
        return False, "Esse apelido é reservado. Escolha outro."
    if any(b in base for b in _BLOQUEADOS):
        return False, "Esse apelido não é permitido. Escolha outro."
    return True, ""


def chave_apelido(apelido: str) -> str:
    """Forma usada para conferir duplicidade (maiúsculas e minúsculas contam como o mesmo apelido)."""
    return str(apelido or "").strip().lower()


def universo_base() -> list[str]:
    """Tickers que o fechamento tenta cotar: catálogo de ações do app mais os extras líquidos."""
    out: list[str] = []
    try:
        import recursos
        out += [t for t in recursos.TODOS_TICKERS]
    except Exception:
        pass
    out += list(EXTRAS_LIQUIDOS)
    vistos, res = set(), []
    for t in out:
        t = str(t).upper().strip()
        if _TICKER.fullmatch(t) and t not in vistos:
            vistos.add(t)
            res.append(t)
    return res


# ------------------------------------------------------------------ estado da carteira
def novo_estado(entrada: str) -> dict:
    return {"v": 1, "inicio": entrada, "caixa": CAPITAL_INICIAL, "pos": {}, "ult": {}, "hist": [], "proc": [], "ext": [],
            "ult_dia": None, "rank": {}}


def patrimonio(estado: dict, precos: dict | None = None) -> float:
    """Caixa mais posições. precos: {ticker: fechamento}; sem preço novo usa o último conhecido (ou o preço médio)."""
    total = float(estado.get("caixa", 0.0))
    for tk, p in (estado.get("pos") or {}).items():
        px = (precos or {}).get(tk) or (estado.get("ult") or {}).get(tk) or p.get("pm") or 0.0
        total += p["q"] * px
    return total


def dia_execucao(agora: datetime) -> str:
    """Data do fechamento em que uma ordem feita agora será executada."""
    d = agora.date()
    if d.weekday() < 5 and agora.hour < HORA_CORTE:
        return d.isoformat()
    d += timedelta(days=1)
    while d.weekday() >= 5:
        d += timedelta(days=1)
    return d.isoformat()


def fase_execucao(agora: datetime) -> str:
    """"M" = preço do meio-dia (ordem feita antes das 12h, ou depois do corte/fim de semana para o próximo pregão); "F" = fechamento (12h às 17h)."""
    return "F" if agora.date().weekday() < 5 and HORA_MEIO_DIA <= agora.hour < HORA_CORTE else "M"


def rotulo_execucao(o: dict) -> str:
    return "no preço do meio-dia" if o.get("f") == "M" else "no fechamento"


def nova_ordem(agora: datetime, lado: str, ticker: str, qtd: int) -> dict:
    return {"id": uuid.uuid4().hex[:12], "ts": agora.strftime("%Y-%m-%dT%H:%M:%S"), "l": lado, "t": str(ticker).upper().strip(),
            "q": int(qtd), "x": dia_execucao(agora), "f": fase_execucao(agora)}


def pendentes_validas(estado: dict, pendentes: list[dict]) -> list[dict]:
    feitas = set((estado or {}).get("proc") or [])
    return [o for o in (pendentes or []) if o.get("id") not in feitas]


def validar_ordem(estado: dict, pendentes: list[dict], lado: str, ticker: str, qtd, precos: dict) -> tuple[bool, str]:
    """Confere a ordem na hora de enviar (o fechamento confere de novo, com o preço real de fechamento). precos: {ticker: {'c': preço}}"""
    tk = str(ticker or "").upper().strip()
    if lado not in ("C", "V"):
        return False, "Escolha comprar ou vender."
    if tk not in (precos or {}) or not (precos[tk] or {}).get("c"):
        return False, "Esse ativo não está no universo da competição (ou está sem cotação hoje)."
    try:
        q = int(qtd)
    except Exception:
        return False, "Informe a quantidade em número inteiro."
    if q < 1 or q > MAX_QTD_ORDEM or q != qtd:
        return False, "A quantidade deve ser um número inteiro maior que zero."
    pend = pendentes_validas(estado, pendentes)
    if len(pend) >= MAX_PENDENTES:
        return False, f"Você já tem {MAX_PENDENTES} ordens aguardando o fechamento. Cancele alguma ou espere."
    ref = float(precos[tk]["c"])
    pos = (estado.get("pos") or {}).get(tk, {"q": 0})
    if lado == "C":
        reservado = sum(o["q"] * float(precos.get(o["t"], {}).get("c") or 0) * (1 + CUSTO_OPERACAO) for o in pend if o["l"] == "C")
        custo = q * ref * (1 + CUSTO_OPERACAO)
        if custo > float(estado.get("caixa", 0)) - reservado + 1e-9:
            livre = max(0.0, float(estado.get("caixa", 0)) - reservado)
            return False, f"Caixa insuficiente: a compra custa cerca de R$ {custo:,.2f} e o caixa livre é R$ {livre:,.2f}.".replace(",", "X").replace(".", ",").replace("X", ".")
        pat = max(patrimonio(estado, {k: v.get("c") for k, v in precos.items()}), 1.0)
        if (pos["q"] + q) * ref / pat > MAX_PESO + 1e-9:
            return False, f"Limite de concentração: no máximo {MAX_PESO:.0%} do patrimônio em um único ativo."
    else:
        em_venda = sum(o["q"] for o in pend if o["l"] == "V" and o["t"] == tk)
        if q > pos["q"] - em_venda:
            return False, f"Você tem {pos['q'] - em_venda} cota(s) disponível(is) para vender desse ativo."
    return True, ""


def sanear_perfil(doc) -> dict:
    """Documento da pessoa (o que o app grava): só campos conhecidos, com tipos e tamanhos conferidos."""
    d = doc if isinstance(doc, dict) else {}
    ap = str(d.get("apelido") or "").strip()
    pend = []
    for o in (d.get("pend") or [])[:MAX_PENDENTES]:
        try:
            if o["l"] in ("C", "V") and _TICKER.fullmatch(str(o["t"])) and 1 <= int(o["q"]) <= MAX_QTD_ORDEM:
                pend.append({"id": str(o["id"])[:24], "ts": str(o.get("ts", ""))[:19], "l": o["l"], "t": str(o["t"]), "q": int(o["q"]),
                             "x": date.fromisoformat(str(o["x"])).isoformat(), "f": "M" if o.get("f") == "M" else "F"})
        except Exception:
            continue
    return {"apelido": ap if apelido_valido(ap)[0] else "", "apelido_k": chave_apelido(ap) if apelido_valido(ap)[0] else "",
            "aceite": bool(d.get("aceite")), "entrada": str(d.get("entrada") or "")[:10], "drip": bool(d.get("drip")), "pend": pend}


# ------------------------------------------------------------------ fechamento do dia
def _comprar(e: dict, tk: str, q: int, px: float, dia: str, ext: list, tipo: str = "compra"):
    custo = q * px * (1 + CUSTO_OPERACAO)
    p = e["pos"].get(tk, {"q": 0, "pm": 0.0})
    novo_q = p["q"] + q
    e["pos"][tk] = {"q": novo_q, "pm": (p["q"] * p["pm"] + custo) / novo_q}
    e["caixa"] -= custo
    ext.append({"d": dia, "tipo": tipo, "t": tk, "q": q, "p": round(px, 4), "v": round(custo, 2)})


def _aplicar_ordem(e: dict, o: dict, px: float, dia: str, ext: list) -> None:
    """Executa uma ordem ao preço `px` (recusa se faltar caixa ou posição, ou se estourar o limite de concentração)."""
    tk, q = o["t"], int(o["q"])
    px = float(px)
    pos = e["pos"].get(tk, {"q": 0, "pm": 0.0})
    if o["l"] == "C":
        custo = q * px * (1 + CUSTO_OPERACAO)
        pat = patrimonio(e)
        if custo > e["caixa"] + 1e-9:
            ext.append({"d": dia, "tipo": "recusada", "t": tk, "q": q, "p": round(px, 4), "m": "caixa insuficiente no fechamento"})
        elif (pos["q"] + q) * px > MAX_PESO * pat + 1e-6:
            ext.append({"d": dia, "tipo": "recusada", "t": tk, "q": q, "p": round(px, 4), "m": f"passaria de {MAX_PESO:.0%} do patrimônio"})
        else:
            _comprar(e, tk, q, px, dia, ext)
    else:
        if q > pos["q"]:
            ext.append({"d": dia, "tipo": "recusada", "t": tk, "q": q, "p": round(px, 4), "m": "quantidade maior que a posição"})
        else:
            receita = q * px * (1 - CUSTO_OPERACAO)
            resultado = receita - q * pos["pm"]
            e["caixa"] += receita
            if q == pos["q"]:
                del e["pos"][tk]
            else:
                e["pos"][tk] = {"q": pos["q"] - q, "pm": pos["pm"]}
            ext.append({"d": dia, "tipo": "venda", "t": tk, "q": q, "p": round(px, 4), "v": round(receita, 2), "r": round(resultado, 2)})


def processar_dia(estado: dict, pendentes: list[dict], dia: str, dados_dia: dict, reinvestir: bool = False) -> dict:
    """Aplica um pregão à carteira: desdobramentos, proventos, ordens (no fechamento), reinvestimento e valorização.
    dados_dia: {ticker: {'c': fechamento ou None, 'div': provento por cota (data ex), 'split': fator}}. Devolve o novo estado."""
    e = copy.deepcopy(estado)
    ext: list[dict] = []
    # 1) desdobramentos/grupamentos: a quantidade acompanha o fator, o valor da posição não muda
    for tk, p in list(e["pos"].items()):
        f = float((dados_dia.get(tk) or {}).get("split") or 1.0)
        if f > 0 and abs(f - 1.0) > 1e-9:
            p["q"] = int(round(p["q"] * f))
            p["pm"] = p["pm"] / f
            if tk in e["ult"]:
                e["ult"][tk] = e["ult"][tk] / f
            ext.append({"d": dia, "tipo": "desdobramento", "t": tk, "q": p["q"], "m": f"fator {f:g}"})
            if p["q"] <= 0:
                del e["pos"][tk]
    # 2) proventos sobre a posição que existia ANTES das ordens de hoje
    creditos: dict[str, float] = {}
    meio = e.get("meio") or {}
    base = meio.get("q") if meio.get("d") == dia else None      # posição do fechamento anterior: ordens do meio-dia não recebem o provento do dia
    if base is None:
        qtds = {tk: p["q"] for tk, p in e["pos"].items()}
    else:
        qtds = {tk: int(round(q * float((dados_dia.get(tk) or {}).get("split") or 1.0))) for tk, q in base.items()}
    for tk, q in qtds.items():
        dv = float((dados_dia.get(tk) or {}).get("div") or 0.0)
        if dv > 0 and q > 0:
            v = round(q * dv, 2)
            e["caixa"] += v
            creditos[tk] = v
            ext.append({"d": dia, "tipo": "provento", "t": tk, "q": q, "p": round(dv, 4), "v": v})
    # 3) fechamentos do dia
    for tk, dd in dados_dia.items():
        if (dd or {}).get("c"):
            e["ult"][tk] = float(dd["c"])
    # 4) ordens que valem para hoje (ou atrasadas por falta de preço), na ordem em que foram feitas
    feitas = set(e["proc"])
    fila = sorted((o for o in (pendentes or []) if o.get("id") not in feitas and o.get("x", dia) <= dia), key=lambda o: o.get("ts", ""))
    for o in fila:
        tk, q = o["t"], int(o["q"])
        px = (dados_dia.get(tk) or {}).get("c")
        if not px:
            atraso = (date.fromisoformat(dia) - date.fromisoformat(o["x"])).days
            if atraso > DIAS_ESPERA_SEM_PRECO:
                ext.append({"d": dia, "tipo": "recusada", "t": tk, "q": q, "m": "sem cotação por vários dias"})
                e["proc"].append(o["id"])
            continue                                       # sem preço hoje: tenta no próximo pregão
        _aplicar_ordem(e, o, px, dia, ext)
        e["proc"].append(o["id"])
    # 5) reinvestimento automático dos proventos no mesmo ativo
    if reinvestir:
        for tk, v in creditos.items():
            px = e["ult"].get(tk)
            if not px:
                continue
            n = int(min(v, e["caixa"]) // (px * (1 + CUSTO_OPERACAO)))
            if n >= 1:
                _comprar(e, tk, n, float(px), dia, ext, tipo="reinvestimento")
    e.pop("meio", None)
    # 6) valorização e histórico
    pat = round(patrimonio(e), 2)
    if e["hist"] and e["hist"][-1]["d"] == dia:
        e["hist"][-1]["p"] = pat
    else:
        e["hist"].append({"d": dia, "p": pat})
    e["ult_dia"] = dia
    e["proc"] = e["proc"][-MAX_PROCESSADAS:]
    e["ext"] = (e["ext"] + ext)[-MAX_EXTRATO:]
    e["caixa"] = round(e["caixa"], 2)
    return e


def processar_meio_dia(estado: dict, pendentes: list[dict], dia: str, precos: dict) -> dict:
    """Executa ao preço atual (meio-dia) as ordens com f="M" e x=dia. Só mexe em caixa, posições e extrato: não valoriza nem fecha o dia.
    precos: {ticker: preço atual}. Ordem sem preço fica para o fechamento (que executa qualquer ordem ainda pendente)."""
    e = copy.deepcopy(estado)
    if e.get("ult_dia") is not None and e["ult_dia"] >= dia:
        return e                                               # o dia já fechou
    feitas = set(e["proc"])
    fila = sorted((o for o in (pendentes or []) if o.get("id") not in feitas and o.get("f") == "M" and o.get("x") == dia), key=lambda o: o.get("ts", ""))
    if not fila:
        return e
    e["meio"] = {"d": dia, "q": {tk: p["q"] for tk, p in e["pos"].items()}}
    ext: list[dict] = []
    for o in fila:
        px = (precos or {}).get(o["t"])
        if not px:
            continue
        _aplicar_ordem(e, o, float(px), dia, ext)
        e["proc"].append(o["id"])
    e["proc"] = e["proc"][-MAX_PROCESSADAS:]
    e["ext"] = (e["ext"] + ext)[-MAX_EXTRATO:]
    e["caixa"] = round(e["caixa"], 2)
    return e


# ------------------------------------------------------------------ desempenho e ranking
def retorno_total(estado: dict) -> float | None:
    h = (estado or {}).get("hist") or []
    return h[-1]["p"] / CAPITAL_INICIAL - 1 if h else None


def retorno_periodo(estado: dict, desde: str | None) -> float | None:
    """Retorno desde o início do período (data ISO). Sem aportes, é a razão entre o patrimônio final e o do último fechamento antes do período."""
    h = (estado or {}).get("hist") or []
    if not h:
        return None
    if desde is None:
        base = CAPITAL_INICIAL
    else:
        antes = [x["p"] for x in h if x["d"] < desde]
        base = antes[-1] if antes else CAPITAL_INICIAL      # quem entrou no meio do período parte do capital inicial
        if not [x for x in h if x["d"] >= desde]:
            return None                                     # sem pregão no período: fora do ranking do período
    return h[-1]["p"] / base - 1


def queda_maxima(estado: dict) -> float:
    pico, pior = CAPITAL_INICIAL, 0.0
    for x in (estado or {}).get("hist") or []:
        pico = max(pico, x["p"])
        pior = min(pior, x["p"] / pico - 1)
    return pior


def metricas_serie(pats: list[float]) -> dict | None:
    """Volatilidade e Sharpe anualizados (252 pregões) de uma série de patrimônios (o primeiro valor é a base). None com poucos pregões ou sem variação."""
    rets = [b / a - 1 for a, b in zip(pats, pats[1:]) if a > 0]
    if len(rets) < MIN_DIAS_RISCO:
        return None
    rf_d = (1 + RF_ANUAL) ** (1 / 252) - 1
    ex = [r - rf_d for r in rets]
    media = sum(ex) / len(ex)
    var = sum((x - media) ** 2 for x in ex) / (len(ex) - 1)
    dp = math.sqrt(var)
    if dp < 1e-9:
        return None                                     # tudo em caixa: desvio zero, não é "Sharpe infinito"
    return {"vol": dp * math.sqrt(252), "sharpe": media / dp * math.sqrt(252)}


def metricas_risco(estado: dict) -> dict | None:
    """Volatilidade e Sharpe desde o início. None com menos de MIN_DIAS_RISCO pregões ou sem variação."""
    h = (estado or {}).get("hist") or []
    if len(h) < MIN_DIAS_RISCO:
        return None
    return metricas_serie([CAPITAL_INICIAL] + [x["p"] for x in h])


def inicio_semana(hoje: date) -> str:
    return (hoje - timedelta(days=hoje.weekday())).isoformat()


def inicio_mes(hoje: date) -> str:
    return hoje.replace(day=1).isoformat()


def montar_ranking(participantes: list[dict], hoje: date, topo: int = 100) -> dict:
    """participantes: [{'apelido': str, 'email': str, 'estado': dict}]. Devolve o ranking público e a posição de cada pessoa.
    Só entra quem tem MIN_DIAS_RANKING pregões. Empate: mais pregões e depois apelido (ordem estável)."""
    periodos = {"geral": None, "mes": inicio_mes(hoje), "semana": inicio_semana(hoje)}
    listas: dict[str, list[dict]] = {}
    posicoes: dict[str, dict] = {}                          # email -> {periodo: posição}
    for nome, desde in periodos.items():
        linhas = []
        for p in participantes:
            est = p["estado"]
            hist = est.get("hist") or []
            if len(hist) < MIN_DIAS_RANKING:
                continue
            r = retorno_periodo(est, desde)
            if r is None:
                continue
            linhas.append({"apelido": p["apelido"], "email": p["email"], "ret": r, "dd": queda_maxima(est), "dias": len(hist)})
        linhas.sort(key=lambda x: (-round(x["ret"], 8), -x["dias"], x["apelido"].lower()))
        for i, x in enumerate(linhas, 1):
            posicoes.setdefault(x["email"], {})[nome] = i
        listas[nome] = [{"pos": i, "apelido": x["apelido"], "ret": round(x["ret"], 6), "dd": round(x["dd"], 6), "dias": x["dias"]}
                        for i, x in enumerate(linhas[:topo], 1)]
        listas[nome + "_n"] = len(linhas)
    # ranking ajustado ao risco (Sharpe desde o início): premia retorno por unidade de risco, não só quem apostou tudo num papel
    risco = []
    for p in participantes:
        est = p["estado"]
        m = metricas_risco(est) if len(est.get("hist") or []) >= MIN_DIAS_RANKING else None
        if m:
            risco.append({"apelido": p["apelido"], "ret": retorno_total(est), "dd": queda_maxima(est), "dias": len(est["hist"]), **m})
    risco.sort(key=lambda x: (-round(x["sharpe"], 8), -x["dias"], x["apelido"].lower()))
    listas["risco"] = [{"pos": i, "apelido": x["apelido"], "sh": round(x["sharpe"], 3), "vol": round(x["vol"], 4), "ret": round(x["ret"], 6),
                        "dd": round(x["dd"], 6), "dias": x["dias"]} for i, x in enumerate(risco[:topo], 1)]
    listas["risco_n"] = len(risco)
    return {"gerado": hoje.isoformat(), "listas": listas, "posicoes": posicoes}
