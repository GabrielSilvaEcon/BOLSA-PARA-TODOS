"""Cartas colecionáveis · leitura/gravação no banco e ligação com os baús e o Ticker Battle.

- Catálogo global: cartas_catalogo.EMPRESAS + o que o admin cadastrar/ajustar (config_sistema, chave CFG_CATALOGO).
- Configuração (evolução, baús): padrão do catálogo + ajustes do admin (config_sistema, chave CFG_REGRAS), sempre validada.
- Coleção de cada pessoa: banco.sis_estado (chave CH_COLECAO), separada do catálogo. Toda mudança passa pelas regras de cartas.py.
- No Ticker Battle, as cartas EQUIPADAS viram o baralho; cada uma entra no duelo como CÓPIA com os atributos de jogo (id "TK-xxxx").
"""
from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import banco
import cartas as C
import cartas_catalogo as CAT

CH_COLECAO = "cartas_colecao"
CFG_CATALOGO = "cartas_catalogo"
CFG_REGRAS = "cartas_regras"
CAMPOS_EMPRESA = ("nome", "setor", "icone", "atividade", "fato", "arte")


def _agora_iso() -> str:
    return datetime.now(timezone(timedelta(hours=-3))).strftime("%Y-%m-%dT%H:%M:%S")


# ------------------------------------------------------------------ catálogo e regras
def _cfg(chave: str) -> dict:
    try:
        return banco.cfg_ler(chave) or {}
    except Exception:
        return {}


def validar_empresa(tk: str, e: dict, base: dict | None) -> dict:
    """Confere um cadastro do admin. Empresa nova precisa de todos os textos e dos 3 pontos; a raridade sai da pontuação."""
    tk = str(tk or "").strip().upper()
    if not (4 <= len(tk) <= 7 and tk.isalnum()):
        raise C.ErroCarta("Ticker inválido.")
    out = dict(base or {"tk": tk, "arte": None, "desde": CAT.REVISAO})
    for k in CAMPOS_EMPRESA:
        if k in e and e[k] is not None:
            v = str(e[k]).strip()
            if len(v) > (40 if k in ("nome", "setor", "arte") else 8 if k == "icone" else 160):
                raise C.ErroCarta(f"Texto grande demais em {k}.")
            out[k] = v or None
    for k in ("nome", "setor", "icone", "atividade", "fato"):
        if not out.get(k):
            raise C.ErroCarta(f"Falta {k} da empresa {tk}.")
    if "pontos" in e or not base:
        p = e.get("pontos") or {}
        try:
            m, l, r = float(p["mercado"]), float(p["liquidez"]), float(p["relevancia"])
        except (KeyError, TypeError, ValueError):
            raise C.ErroCarta("Informe os pontos de mercado (0–50), liquidez (0–30) e relevância (0–20).")
        if not (0 <= m <= 50 and 0 <= l <= 30 and 0 <= r <= 20):
            raise C.ErroCarta("Pontos fora da faixa: mercado 0–50, liquidez 0–30, relevância 0–20.")
        tot = CAT.pontuacao(m, l, r)
        out["pontos"] = {"mercado": m, "liquidez": l, "relevancia": r, "total": tot}
        out["raridade_fixa"] = CAT.raridade_da_pontuacao(tot)
    out["ativo"] = bool(e.get("ativo", out.get("ativo", True)))
    return out


def catalogo() -> dict:
    """{tk: empresa} = cadastro fixo + cadastro/ajustes do admin (só os ativos). Atualiza a lista de tickers jogáveis do Battle."""
    cat = {e["tk"]: {**e, "ativo": True} for e in CAT.EMPRESAS}
    for tk, e in (_cfg(CFG_CATALOGO).get("empresas") or {}).items():
        try:
            cat[tk] = validar_empresa(tk, e, cat.get(tk))
        except C.ErroCarta:
            continue
    ativos = {t: e for t, e in cat.items() if e.get("ativo", True)}
    CAT.EXTRAS.clear()
    CAT.EXTRAS.update({t: e["nome"] for t, e in ativos.items() if t not in CAT.POR_TK})
    return ativos


def regras() -> dict:
    try:
        return C.validar_config(_cfg(CFG_REGRAS))
    except C.ErroCarta:
        return C.config_padrao()


def por_raridade(cat: dict) -> dict:
    return {r: sorted(t for t, e in cat.items() if e["raridade_fixa"] == r) for r in CAT.RARIDADES}


def admin_salvar_empresa(tk: str, dados: dict) -> dict:
    tk = str(tk or "").strip().upper()
    atual = catalogo()
    todas = {e["tk"]: e for e in CAT.EMPRESAS}
    e = validar_empresa(tk, dados, atual.get(tk) or todas.get(tk))
    doc = _cfg(CFG_CATALOGO)
    emp = dict(doc.get("empresas") or {})
    emp[tk] = {k: e.get(k) for k in (*CAMPOS_EMPRESA, "pontos", "ativo")}
    banco.cfg_gravar(CFG_CATALOGO, {**doc, "empresas": emp, "atualizado": _agora_iso()})
    return e


def admin_salvar_regras(dados: dict) -> dict:
    cfg = C.validar_config(dados)
    banco.cfg_gravar(CFG_REGRAS, {"evolucao": cfg["evolucao"], "baus": cfg["baus"], "atualizado": _agora_iso()})
    return cfg


# ------------------------------------------------------------------ coleção da pessoa
def ler(email: str) -> dict:
    try:
        return C.normalizar(banco.sis_estado_ler(email, CH_COLECAO))
    except Exception:
        return C.colecao_vazia()


def gravar(email: str, doc: dict) -> None:
    banco.sis_estado_gravar(email, CH_COLECAO, doc)


def garantir_inicial(email: str, doc: dict | None = None) -> tuple[dict, dict | None]:
    """Primeiro acesso: entrega o pacote inicial (1 carta de cada raridade de INICIAL) e já equipa. Uma vez só por conta."""
    doc = doc if doc is not None else ler(email)
    if "inicial" in doc["ids"]:
        return doc, None
    cat, cfg = catalogo(), regras()
    tks = C.sortear_inicial(banco._h_conta(email), cfg["inicial"], por_raridade(cat))
    agora = _agora_iso()
    res = C.entregar(doc, "inicial", tks, lambda t: cat[t]["raridade_fixa"], "inicial", agora)
    for t in tks:                                          # monta o baralho com o que couber (teto por raridade em cartas.py)
        try:
            C.equipar(doc, t, agora)
        except C.ErroCarta:
            pass
    gravar(email, doc)
    return doc, res


def recompensa_bau(email: str, ref: str, rar_bau: str) -> dict:
    """Cartas de um baú já aberto (o crédito de moedas é do tickercoins). Mesmo baú = mesmo resultado, entregue uma vez só."""
    doc, _ = garantir_inicial(email)
    cat, cfg = catalogo(), regras()
    conf = cfg["baus"].get(rar_bau) or cfg["baus"]["comum"]
    seed = f"{banco._h_conta(email)}|{ref}"
    tks = C.sortear_bau(seed, conf, por_raridade(cat))
    res = C.entregar(doc, "bau:" + ref, tks, lambda t: cat[t]["raridade_fixa"], "bau_" + rar_bau, _agora_iso())
    if not res["ja"]:
        gravar(email, doc)
    return {**res, "itens": [{**i, **visao_empresa(cat.get(i["tk"]))} for i in res["itens"]], "extra": conf.get("extra")}


def visao_empresa(e: dict | None) -> dict:
    if not e:
        return {}
    return {"nome": e["nome"], "setor": e["setor"], "icone": e["icone"], "atividade": e["atividade"], "fato": e["fato"], "arte": e.get("arte"),
            "raridade": e["raridade_fixa"]}


# ------------------------------------------------------------------ Ticker Battle
def sufixo(email: str) -> str:
    return banco._h_conta(email)[:6]


def id_jogo(email: str, tk: str) -> str:
    return f"{tk}-{sufixo(email)}"


def base_do_id(ident: str) -> str:
    return str(ident).split("-")[0]


def deck(email: str, doc: dict | None = None) -> list[str]:
    """Baralho do Battle = cartas equipadas (ids de jogo, da comum à lendária)."""
    doc = doc if doc is not None else garantir_inicial(email)[0]
    return [id_jogo(email, t) for t in C.equipadas(doc)]


def cartas_de_jogo(email: str, snap: dict, doc: dict | None = None) -> dict:
    """{id: cópia da carta do snapshot com os atributos de jogo} das equipadas que têm dados no snapshot."""
    doc = doc if doc is not None else garantir_inicial(email)[0]
    cfg = regras()
    equip = [t for t in C.equipadas(doc) if t in snap]
    cat = catalogo()
    sin = {s["setor"]: s for s in C.sinergias(equip, lambda t: (cat.get(t) or {}).get("setor"))}   # sinergia de setor, vista pelo baralho inteiro
    out = {}
    for t in equip:
        carta = C.carta_de_jogo(snap[t], doc["cartas"][t], cfg, id_jogo(email, t))
        s = sin.get((cat.get(t) or {}).get("setor"))
        if s:
            C.aplicar_sinergia(carta, s["passos"], cfg)
            carta["sinergia"] = {"setor": s["setor"], "n": s["n"], "passos": s["passos"]}
        out[id_jogo(email, t)] = carta
    return out


def snapshot_com(snap: dict, emails: list[str]) -> dict:
    """Snapshot + as cópias de jogo das cartas equipadas de cada pessoa (para validar e congelar o baralho no duelo)."""
    out = dict(snap)
    for e in emails:
        if e:
            out.update(cartas_de_jogo(e, snap))
    return out


def cartas_do_solo(email: str, snap: dict) -> tuple[list[str], dict]:
    """(baralho, cartas do duelo contra o sistema): as cópias de jogo + o snapshot SEM as empresas equipadas (o sistema não joga a mesma)."""
    doc = garantir_inicial(email)[0]
    minhas = cartas_de_jogo(email, snap, doc)
    eq = set(C.equipadas(doc))
    return list(minhas), {**{t: copy.deepcopy(c) for t, c in snap.items() if t not in eq}, **minhas}
