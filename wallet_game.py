"""Wallet Game: ranks, bônus diário, missões e conquistas. Módulo sem Streamlit (as telas ficam em wallet_game_app.py).

Três economias que NUNCA se misturam
 · Dinheiro virtual (T$): só dentro da Wallet Game. Bônus e recompensas em T$ entram no caixa da carteira virtual.
 · TickerCoins (TC): a moeda do app (tickercoins.py). Aqui só se chama `tickercoins.creditar`; não existe segunda moeda.
 · XP: experiência da Jornada. Aqui só se calcula quanto pagar; quem grava é a tela (perfil de estudo).

Segurança (tudo no servidor)
 · Livro `wg_creditos`: cada crédito em T$ é uma linha com `chave` ÚNICA (ex.: "bonus:<conta>:2026-11-11"). Repetir o pedido, clicar duas vezes
   ou abrir em dois aparelhos não credita de novo. O dia vem do relógio do servidor em Brasília; a tela não envia data nem valor.
 · A carteira (documento `comp_cart`) recebe os créditos de forma idempotente (`competicao.aplicar_creditos`): cada chave entra uma vez só,
   mesmo que o app e o fechamento diário regravem a carteira ao mesmo tempo.
 · Bônus não infla o ranking: o retorno % descarta o que veio de bônus (`apt` na carteira).
 · O rank é calculado aqui a partir da carteira; o maior rank fica guardado e só sobe.
Valores configuráveis: `CFG_PADRAO` (bônus, ranks, recompensas) mesclado com o que o administrador gravar em config_sistema (`wg_config`).
"""
from __future__ import annotations

import copy
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import banco
import competicao as C

CH_CART = "comp_cart"
CH_PERFIL = "comp_ordens"
CH_WG = "wg_estado"
MAX_VISITAS = 60

# ------------------------------------------------------------------ configuração
RANKS = [  # (id, nome, patrimônio mínimo para o capital de T$ 10.000; carteiras de outro capital usam múltiplos equivalentes)
    ("bronze", "Bronze", 0.0, "#CD7F32"),
    ("prata", "Prata", 20_000.0, "#C0C7D4"),
    ("ouro", "Ouro", 35_000.0, "#F2B84B"),
    ("platina", "Platina", 55_000.0, "#5FD6E6"),
    ("diamante", "Diamante", 80_000.0, "#7AA7FF"),
    ("mestre", "Mestre", 120_000.0, "#C46BFF"),
]

CFG_PADRAO = {
    "bonus": {"diario": 25.0, "extra_7": 100.0,
              "ciclos": {"14": {"capital": 150.0, "tc": 10}, "30": {"capital": 500.0, "tc": 30}}},
    "missoes": {},          # {id_da_missao: {"xp": n, "tc": n, "capital": n}}: sobrescreve a recompensa padrão
}
_CFG = {"v": None, "t": 0.0}


def _mesclar(base: dict, extra: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (extra or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _mesclar(out[k], v)
        else:
            out[k] = v
    return out


def config(forcar: bool = False) -> dict:
    import time
    if not forcar and _CFG["v"] is not None and time.time() - _CFG["t"] < 30:
        return _CFG["v"]
    salvo = {}
    try:
        salvo = banco.cfg_ler("wg_config") or {}
    except Exception:
        pass
    _CFG["v"], _CFG["t"] = _mesclar(CFG_PADRAO, salvo), time.time()
    return _CFG["v"]


# ------------------------------------------------------------------ tempo (Brasília)
def agora_utc(agora: datetime | None = None) -> datetime:
    return (agora or datetime.now(timezone.utc)).astimezone(timezone.utc)


def hoje_brt(agora: datetime | None = None) -> date:
    return (agora_utc(agora) - timedelta(hours=3)).date()


def inicio_semana(d: date) -> str:
    return (d - timedelta(days=d.weekday())).isoformat()


def _iso(agora: datetime) -> str:
    return agora_utc(agora).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


# ------------------------------------------------------------------ ranks
def patrimonio_rank(estado: dict) -> float:
    """Patrimônio total (caixa + posições) na escala do capital de T$ 10.000. Quem começou com T$ 100.000 é comparado em múltiplos equivalentes,
    então ninguém vira 'Diamante' só por ter entrado com o capital antigo."""
    return C.patrimonio(estado) * C.CAPITAL_NOVO / C.capital_de(estado)


def indice_rank(pat_norm: float) -> int:
    idx = 0
    for i, (_, _, minimo, _) in enumerate(RANKS):
        if pat_norm >= minimo:
            idx = i
    return idx


def info_rank(estado: dict, rank_max_idx: int | None = None) -> dict:
    """Rank atual, próximo rank, barra de progresso e quanto falta (em T$ da escala da própria carteira)."""
    esc = C.capital_de(estado) / C.CAPITAL_NOVO
    pn = patrimonio_rank(estado)
    i = indice_rank(pn)
    atual = RANKS[i]
    prox = RANKS[i + 1] if i + 1 < len(RANKS) else None
    if prox:
        piso = max(atual[2], C.CAPITAL_NOVO)               # a barra do Bronze começa no capital inicial
        prog = (pn - piso) / (prox[2] - piso) if prox[2] > piso else 1.0
        faltam = max(0.0, (prox[2] - pn) * esc)
    else:
        prog, faltam = 1.0, 0.0
    mx = max(i, rank_max_idx if rank_max_idx is not None else i)
    return {"idx": i, "id": atual[0], "nome": atual[1], "cor": atual[3], "progresso": max(0.0, min(1.0, prog)),
            "proximo": prox[1] if prox else None, "proximo_em": round(prox[2] * esc, 2) if prox else None, "faltam": round(faltam, 2),
            "patrimonio": round(C.patrimonio(estado), 2), "max_idx": mx, "max_nome": RANKS[mx][1], "max_cor": RANKS[mx][3],
            "faixas": [(n, round(m * esc, 2), cor) for _, n, m, cor in RANKS]}


# ------------------------------------------------------------------ livro de créditos em T$
def _por_chave(chave: str) -> dict | None:
    r = banco._selecionar("wg_creditos", {"chave": chave}, None, limite=1)
    return r[0] if r else None


def _inserir_credito(email: str, conta_id: str, chave: str, tipo: str, valor: float, dia: str, descricao: str,
                     dados: dict | None, agora: datetime) -> bool:
    """True se gravou agora; False se a chave já existia (nada é creditado duas vezes)."""
    if _por_chave(chave):
        return False
    try:
        banco._inserir("wg_creditos", {"id": uuid.uuid4().hex, "email": email, "conta_id": conta_id, "chave": chave[:140], "tipo": tipo,
                                       "valor": round(float(valor), 2), "dia": dia, "descricao": descricao[:120], "criado_em": _iso(agora),
                                       "dados": banco._js(dados or {})})
        return True
    except banco.Duplicado:
        return False


def creditos_do_email(email: str) -> list[dict]:
    rows = banco._selecionar("wg_creditos", {"email": email}, ["chave", "valor", "dia", "descricao", "criado_em", "tipo"], limite=5000)
    return [r for r in rows if r["tipo"] != "xp"]


def creditos_todos() -> dict[str, list[dict]]:
    """{email: [créditos em T$]} para o fechamento diário aplicar de uma vez às carteiras."""
    out: dict[str, list[dict]] = {}
    for r in banco._selecionar("wg_creditos", None, ["email", "chave", "valor", "dia", "descricao", "criado_em", "tipo"], limite=100_000):
        if r["tipo"] != "xp":
            out.setdefault(r["email"], []).append(r)
    return out


def sincronizar(email: str, hoje: str | None = None) -> dict:
    """Garante que a carteira da conta contém todos os créditos do livro. Devolve a carteira (criando-a em memória se ainda não existe)."""
    cart = banco.sis_estado_ler(email, CH_CART) or {}
    perfil = banco.sis_estado_ler(email, CH_PERFIL) or {}
    entrada = perfil.get("entrada") or hoje or hoje_brt().isoformat()
    base = cart if cart.get("v") == 1 else C.novo_estado(entrada)
    novo, n = C.aplicar_creditos(base, creditos_do_email(email))
    if n:
        banco.sis_estado_gravar(email, CH_CART, novo)
    return novo


# ------------------------------------------------------------------ bônus diário e sequência
def _linhas_bonus(email: str) -> list[dict]:
    rows = banco._selecionar("wg_creditos", {"email": email, "tipo": "bonus"}, ["dia", "valor", "descricao", "criado_em", "dados"], ordem="dia", limite=800)
    for r in rows:
        r["dados"] = banco._de_js(r.get("dados")) if r.get("dados") is not None else {}
    return rows


def sequencia(email: str, hoje: date) -> dict:
    """Estado da sequência a partir do livro (não de dados da tela): dias seguidos, melhor sequência, se já resgatou hoje e o próximo marco."""
    rows = _linhas_bonus(email)
    dias = [date.fromisoformat(r["dia"]) for r in rows]
    resgatou = bool(dias) and dias[-1] == hoje
    atual = 0
    if dias and dias[-1] >= hoje - timedelta(days=1):
        atual, d = 1, dias[-1]
        for x in reversed(dias[:-1]):
            if x == d - timedelta(days=1):
                atual += 1
                d = x
            else:
                break
    melhor, cor = 0, 0
    for i, d in enumerate(dias):
        cor = cor + 1 if i and d - dias[i - 1] == timedelta(days=1) else 1
        melhor = max(melhor, cor)
    proximo = atual + 1                                   # número do próximo resgate (hoje, se ainda não resgatou; senão amanhã)
    marco = next((m for m in (7, 14, 30) if m >= proximo), None)
    return {"atual": atual, "melhor": melhor, "resgatou_hoje": resgatou, "proximo_numero": proximo, "proximo_marco": marco, "total": len(dias),
            "pode_em": (hoje + timedelta(days=1)).isoformat() if resgatou else hoje.isoformat()}


def historico_bonus(email: str, limite: int = 20) -> list[dict]:
    rows = _linhas_bonus(email)
    return list(reversed(rows))[:limite]


def _participa(email: str) -> bool:
    return bool((banco.sis_estado_ler(email, CH_PERFIL) or {}).get("aceite"))


def resgatar_bonus(email: str, conta_id: str, agora: datetime | None = None) -> dict:
    """Resgata o bônus do dia. Tudo é decidido aqui: dia pelo relógio do servidor (Brasília), valor pela configuração, duplicidade pela chave única.
    Devolve {"ok", "erro", "valor", "seq", "extras", "tc"}."""
    agora = agora_utc(agora)
    hoje = hoje_brt(agora)
    if not email or not conta_id:
        return {"ok": False, "erro": "Faça login para resgatar."}
    if not _participa(email):
        return {"ok": False, "erro": "Entre na competição da Wallet Game (escolha um apelido) para resgatar o bônus."}
    chave = f"bonus:{conta_id}:{hoje.isoformat()}"
    if _por_chave(chave):
        return {"ok": False, "erro": "Você já resgatou o bônus de hoje.", "duplicado": True}
    rows = _linhas_bonus(email)
    ultimo = date.fromisoformat(rows[-1]["dia"]) if rows else None
    seq = (int(rows[-1]["dados"].get("seq", 1)) + 1) if ultimo == hoje - timedelta(days=1) else 1
    cfg = config()["bonus"]
    valor = float(cfg["diario"])
    extras: list[str] = []
    tc = 0
    if seq % 7 == 0:
        valor += float(cfg["extra_7"])
        extras.append(f"{seq}º dia seguido: bônus extra")
    ciclo = cfg["ciclos"].get(str(seq))
    if ciclo:
        valor += float(ciclo.get("capital", 0))
        tc = int(ciclo.get("tc", 0))
        extras.append(f"ciclo de {seq} dias")
    desc = f"Bônus diário (dia {seq})" + (f" + {', '.join(extras)}" if extras else "")
    if not _inserir_credito(email, conta_id, chave, "bonus", valor, hoje.isoformat(), desc, {"seq": seq, "tc": tc}, agora):
        return {"ok": False, "erro": "Você já resgatou o bônus de hoje.", "duplicado": True}
    sincronizar(email, hoje.isoformat())
    if tc > 0:
        try:
            import tickercoins as TC
            TC.creditar(conta_id, tc, "wallet_game", f"Wallet Game: ciclo de {seq} dias", f"wg:ciclo:{conta_id}:{hoje.isoformat()}", str(seq))
        except Exception as e:
            banco.registrar_erro("wallet_game.tc_ciclo", e)
            tc = 0
    return {"ok": True, "valor": valor, "seq": seq, "extras": extras, "tc": tc}


# ------------------------------------------------------------------ missões e conquistas (definições)
# periodo: dia | semana | especial. meta é o número a atingir; a recompensa pode ter xp, tc (TickerCoins) e capital (T$).
MISSOES = [
    {"id": "d_bonus", "periodo": "dia", "nome": "Resgatar o bônus do dia", "descricao": "Abra a Wallet Game e resgate o bônus de hoje.",
     "objetivo": "1 resgate", "meta": 1, "recompensa": {"xp": 5}},
    {"id": "d_conferir", "periodo": "dia", "nome": "Conferir sua carteira", "descricao": "Veja como está seu patrimônio hoje.",
     "objetivo": "1 visita", "meta": 1, "recompensa": {"xp": 3}},
    {"id": "s_bonus5", "periodo": "semana", "nome": "Constância na semana", "descricao": "Resgate o bônus diário em 5 dias da semana.",
     "objetivo": "5 resgates", "meta": 5, "recompensa": {"xp": 30, "tc": 5}},
    {"id": "s_operacao", "periodo": "semana", "nome": "Uma compra e uma venda", "descricao": "Faça uma compra e uma venda na semana (sem pressa: uma de cada basta).",
     "objetivo": "1 compra + 1 venda", "meta": 2, "recompensa": {"xp": 20}},
    {"id": "e_primeiro", "periodo": "especial", "nome": "Primeiro investimento", "descricao": "Compre seu primeiro ativo na carteira virtual.",
     "objetivo": "1 ativo", "meta": 1, "recompensa": {"xp": 20, "tc": 5, "capital": 100.0}},
    {"id": "e_tres", "periodo": "especial", "nome": "Três ativos diferentes", "descricao": "Tenha três ativos diferentes na carteira.",
     "objetivo": "3 ativos", "meta": 3, "recompensa": {"xp": 30, "tc": 5}},
    {"id": "e_diversa", "periodo": "especial", "nome": "Carteira diversificada", "descricao": "Tenha pelo menos 4 ativos de pelo menos 3 classes diferentes (ações, FIIs, ETFs, cripto, fundos ou renda fixa).",
     "objetivo": "4 ativos em 3 classes", "meta": 4, "recompensa": {"xp": 50, "tc": 10, "capital": 250.0}},
    {"id": "e_acompanhar", "periodo": "especial", "nome": "Acompanhar por 7 dias", "descricao": "Confira a evolução da carteira em 7 dias diferentes.",
     "objetivo": "7 dias", "meta": 7, "recompensa": {"xp": 40, "tc": 5}},
    {"id": "e_rent5", "periodo": "especial", "nome": "Rentabilidade de 5%", "descricao": "Alcance +5% de resultado simulado (sem contar bônus).",
     "objetivo": "+5%", "meta": 5, "recompensa": {"xp": 60, "tc": 10, "capital": 300.0}},
    {"id": "e_seq7", "periodo": "especial", "nome": "Sequência de 7 dias", "descricao": "Resgate o bônus 7 dias seguidos.",
     "objetivo": "7 dias seguidos", "meta": 7, "recompensa": {"xp": 50, "tc": 10}},
]
CONQUISTAS = [
    {"id": "c_primeiro", "nome": "Primeiro investimento", "descricao": "Fez a primeira compra na carteira virtual.", "emblema": "🌱", "cor": "#3DDC97", "recompensa": {"tc": 3}},
    {"id": "c_diversa", "nome": "Carteira diversificada", "descricao": "Montou uma carteira com 4 ativos em 3 classes.", "emblema": "🧺", "cor": "#2BA7C9", "recompensa": {"tc": 5}},
    {"id": "c_seq7", "nome": "7 dias seguidos", "descricao": "Resgatou o bônus por 7 dias seguidos.", "emblema": "🔥", "cor": "#FF9B3D", "recompensa": {"tc": 5}},
    {"id": "c_prata", "nome": "Rank Prata", "descricao": "Chegou ao rank Prata.", "emblema": "🥈", "cor": "#C0C7D4", "recompensa": {"tc": 5}},
    {"id": "c_ouro", "nome": "Rank Ouro", "descricao": "Chegou ao rank Ouro.", "emblema": "🥇", "cor": "#F2B84B", "recompensa": {"tc": 10}},
    {"id": "c_positiva", "nome": "Primeira rentabilidade positiva", "descricao": "Seus investimentos fecharam no positivo (sem contar bônus).", "emblema": "📈", "cor": "#8BE04E", "recompensa": {"tc": 3}},
    {"id": "c_val10", "nome": "10% de valorização", "descricao": "Chegou a +10% de resultado simulado (sem contar bônus).", "emblema": "🚀", "cor": "#B02FC8", "recompensa": {"tc": 10}},
    {"id": "c_missoes5", "nome": "5 missões concluídas", "descricao": "Completou 5 missões.", "emblema": "🎯", "cor": "#8B6CFF", "recompensa": {"tc": 5}},
]
_M_POR_ID = {m["id"]: m for m in MISSOES}


def recompensa_da_missao(mid: str) -> dict:
    base = dict(_M_POR_ID[mid]["recompensa"])
    base.update((config().get("missoes") or {}).get(mid) or {})
    return base


# ------------------------------------------------------------------ medidas
def _classes(estado: dict) -> set:
    import ativos_jogo as A
    return {A.classe(tk) for tk in (estado.get("pos") or {}) if A.classe(tk)}


def resultado_liquido(estado: dict) -> float:
    """Resultado simulado em %, sem contar os bônus: (patrimônio - bônus) / capital inicial - 1."""
    return ((C.patrimonio(estado) - C.aportes(estado)) / C.capital_de(estado) - 1) * 100


def _compras_vendas(estado: dict, desde: str) -> tuple[int, int]:
    ext = estado.get("ext") or []
    return (sum(1 for x in ext if x.get("tipo") == "compra" and x.get("d", "") >= desde),
            sum(1 for x in ext if x.get("tipo") == "venda" and x.get("d", "") >= desde))


def progresso_da_missao(m: dict, ctx: dict) -> int:
    est, hoje = ctx["estado"], ctx["hoje"]
    mid = m["id"]
    if mid == "d_bonus":
        return 1 if ctx["seq"]["resgatou_hoje"] else 0
    if mid == "d_conferir":
        return 1 if hoje.isoformat() in ctx["visitas"] else 0
    if mid == "s_bonus5":
        ini = inicio_semana(hoje)
        return sum(1 for r in ctx["bonus"] if r["dia"] >= ini)
    if mid == "s_operacao":
        c, v = _compras_vendas(est, inicio_semana(hoje))
        return min(c, 1) + min(v, 1)
    if mid == "e_primeiro":
        c, _ = _compras_vendas(est, "0000")
        return 1 if (c or est.get("pos")) else 0
    if mid == "e_tres":
        return len(est.get("pos") or {})
    if mid == "e_diversa":
        return len(est.get("pos") or {}) if len(_classes(est)) >= 3 else min(len(est.get("pos") or {}), 3)
    if mid == "e_acompanhar":
        return len(ctx["visitas"])
    if mid == "e_rent5":
        return max(0, int(resultado_liquido(est) * 100) / 100) if est.get("pos") or est.get("hist") else 0
    if mid == "e_seq7":
        return max(ctx["seq"]["atual"], ctx["seq"]["melhor"])
    return 0


def _ref_periodo(m: dict, hoje: date) -> str:
    return hoje.isoformat() if m["periodo"] == "dia" else inicio_semana(hoje) if m["periodo"] == "semana" else "unica"


def conquista_ok(cid: str, ctx: dict) -> bool:
    est, rk = ctx["estado"], ctx["rank"]
    if cid == "c_primeiro":
        return progresso_da_missao(_M_POR_ID["e_primeiro"], ctx) >= 1
    if cid == "c_diversa":
        return progresso_da_missao(_M_POR_ID["e_diversa"], ctx) >= 4
    if cid == "c_seq7":
        return ctx["seq"]["melhor"] >= 7
    if cid == "c_prata":
        return rk["max_idx"] >= 1
    if cid == "c_ouro":
        return rk["max_idx"] >= 2
    if cid == "c_positiva":
        return bool(est.get("pos") or est.get("hist")) and resultado_liquido(est) > 0
    if cid == "c_val10":
        return resultado_liquido(est) >= 10
    if cid == "c_missoes5":
        return len(ctx["doc"].get("conc") or {}) >= 5
    return False


# ------------------------------------------------------------------ avaliação (missões, conquistas, rank, visita)
def _doc(email: str) -> dict:
    d = banco.sis_estado_ler(email, CH_WG) or {}
    return {"v": 1, "visitas": list(d.get("visitas") or []), "conq": dict(d.get("conq") or {}), "conc": dict(d.get("conc") or {}),
            "rank_max": int(d.get("rank_max") or 0), "rank_max_em": d.get("rank_max_em")}


def _pagar_tc(conta_id: str, valor: int, descricao: str, chave: str) -> int:
    if valor <= 0:
        return 0
    try:
        import tickercoins as TC
        r = TC.creditar(conta_id, int(valor), "wallet_game", descricao, chave, chave)
        return 0 if r.get("duplicado") else int(valor)
    except Exception as e:
        banco.registrar_erro("wallet_game.tc", e)
        return 0


def avaliar(email: str, conta_id: str, agora: datetime | None = None, registrar_visita: bool = True) -> dict:
    """Atualiza e devolve tudo da tela: carteira, rank, sequência, missões, conquistas e eventos novos (subiu de rank, missão ou conquista).
    Pagamentos são idempotentes (chaves únicas); repetir a chamada não paga de novo."""
    agora = agora_utc(agora)
    hoje = hoje_brt(agora)
    estado = sincronizar(email, hoje.isoformat())
    doc = _doc(email)
    antes = json.dumps(doc, sort_keys=True)
    if registrar_visita and hoje.isoformat() not in doc["visitas"]:
        doc["visitas"] = (doc["visitas"] + [hoje.isoformat()])[-MAX_VISITAS:]
    seq = sequencia(email, hoje)
    bonus = _linhas_bonus(email)
    rank = info_rank(estado, doc["rank_max"])
    eventos: list[dict] = []
    xp_novo = 0
    if rank["idx"] > doc["rank_max"]:
        doc["rank_max"], doc["rank_max_em"] = rank["idx"], _iso(agora)
        eventos.append({"tipo": "rank", "nome": rank["nome"], "cor": rank["cor"]})
        rank = info_rank(estado, doc["rank_max"])
    ctx = {"estado": estado, "hoje": hoje, "seq": seq, "bonus": bonus, "visitas": doc["visitas"], "rank": rank, "doc": doc}
    missoes = []
    creditou_capital = False
    for m in MISSOES:
        ref = _ref_periodo(m, hoje)
        k = f"{m['id']}|{ref}"
        prog = progresso_da_missao(m, ctx)
        feita = k in doc["conc"]
        if not feita and prog >= m["meta"]:
            rec = recompensa_da_missao(m["id"])
            doc["conc"][k] = _iso(agora)
            tc = _pagar_tc(conta_id, int(rec.get("tc", 0)), f"Missão: {m['nome']}", f"wg:missao:{conta_id}:{k}")
            cap = float(rec.get("capital", 0) or 0)
            if cap > 0 and _inserir_credito(email, conta_id, f"missao:{conta_id}:{k}", "missao", cap, hoje.isoformat(), f"Missão: {m['nome']}", {"m": m["id"]}, agora):
                creditou_capital = True
            xp = int(rec.get("xp", 0))
            if xp > 0 and _inserir_credito(email, conta_id, f"xp:{conta_id}:{k}", "xp", xp, hoje.isoformat(), f"Missão: {m['nome']}", {"m": m["id"]}, agora):
                xp_novo += xp
            eventos.append({"tipo": "missao", "nome": m["nome"], "xp": xp, "tc": tc, "capital": cap})
            feita = True
        missoes.append({**m, "ref": ref, "progresso": min(prog, m["meta"]) if m["id"] != "e_rent5" else min(prog, m["meta"]), "feita": feita,
                        "status": "concluida" if feita else ("andamento" if prog > 0 else "disponivel"), "recompensa": recompensa_da_missao(m["id"]),
                        "concluida_em": doc["conc"].get(k)})
    conquistas = []
    for c in CONQUISTAS:
        quando = doc["conq"].get(c["id"])
        if not quando and conquista_ok(c["id"], ctx):
            quando = doc["conq"][c["id"]] = _iso(agora)
            tc = _pagar_tc(conta_id, int(c["recompensa"].get("tc", 0)), f"Conquista: {c['nome']}", f"wg:conquista:{conta_id}:{c['id']}")
            eventos.append({"tipo": "conquista", "nome": c["nome"], "emblema": c["emblema"], "tc": tc})
        conquistas.append({**c, "desbloqueada_em": quando})
    if creditou_capital:
        estado = sincronizar(email, hoje.isoformat())
        rank = info_rank(estado, doc["rank_max"])
    if json.dumps(doc, sort_keys=True) != antes:
        try:
            banco.sis_estado_gravar(email, CH_WG, doc)
        except Exception as e:
            banco.registrar_erro("wallet_game.doc", e)
    return {"estado": estado, "rank": rank, "seq": seq, "missoes": missoes, "conquistas": conquistas, "eventos": eventos, "xp_novo": xp_novo,
            "resultado": resultado_liquido(estado), "hoje": hoje.isoformat(), "bonus_hist": list(reversed(bonus))[:10]}


SIMBOLO = "T$"  # moeda fictícia da Wallet Game (não é real e não se mistura com TickerCoins)


def moeda(v, casas=2):
    """Formata dinheiro virtual: 'T$ 1.234,56'. Separado de dados.brl (R$ real)."""
    if v is None or v != v:
        return "—"
    s = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{SIMBOLO} {s}"


def moeda_curta(v) -> str:
    """T$ compacto para o topo do app: 'T$ 950', 'T$ 100,1 mil', 'T$ 1,2 mi'."""
    if v is None or v != v:
        return "—"
    n = abs(float(v))
    if n >= 1_000_000:
        t = f"{v / 1_000_000:.1f}".replace(".", ",") + " mi"
    elif n >= 1_000:
        t = f"{v / 1_000:.1f}".replace(".", ",") + " mil"
    else:
        t = f"{v:.0f}"
    return f"{SIMBOLO} {t}"
