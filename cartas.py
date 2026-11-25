"""Regras PURAS das cartas colecionáveis (sem banco, sem rede): coleção, cópias, evolução, escolha de atributo, equipar e baús.

Coleção de uma pessoa (documento salvo em banco.sis_estado, chave cartas_colecao):
    {"v": 1,
     "cartas": {tk: {"rar": raridade FIXADA na 1ª obtenção, "nivel": 1.., "copias": cópias extras guardadas, "total": cópias já obtidas,
                     "escolhas": [indicador escolhido em cada evolução, na ordem], "desde": iso}},
     "equip": [tk, ..]  → o baralho, na ordem escolhida; no máximo BARALHO_EQUIP cartas, com teto por raridade (MAX_POR_RARIDADE),
     "ids": [referências de recompensa já entregues (baú, pacote inicial)]  → nenhuma recompensa entra duas vezes,
     "log": [transações, a mais nova primeiro]}
Dados financeiros reais NUNCA são alterados: `carta_de_jogo` devolve uma CÓPIA da carta do snapshot com os bônus da evolução aplicados
em "ind" e guarda os valores reais em "real".
"""
from __future__ import annotations

import copy
import hashlib
import random

import cartas_catalogo as CAT

LOG_MAX = 300
IDS_MAX = 2000


class ErroCarta(ValueError):
    pass


# ------------------------------------------------------------------ configuração (padrão do catálogo + ajustes do admin)
def config_padrao() -> dict:
    return {"evolucao": copy.deepcopy(CAT.EVOLUCAO), "baus": copy.deepcopy(CAT.BAUS), "bonus": copy.deepcopy(CAT.BONUS),
            "inicial": list(CAT.INICIAL)}


def validar_config(cfg: dict) -> dict:
    """Confere uma configuração (a do admin) e devolve a configuração completa. ErroCarta se algo estiver fora do lugar."""
    base = config_padrao()
    cfg = cfg or {}
    out = copy.deepcopy(base)
    ev = cfg.get("evolucao") or {}
    for r, lista in ev.items():
        if r not in CAT.RARIDADES or not isinstance(lista, list) or not lista or len(lista) > 30:
            raise ErroCarta(f"Tabela de evolução inválida para {r}.")
        if any(not isinstance(x, int) or x < 1 or x > 10_000 for x in lista):
            raise ErroCarta(f"Custos de evolução de {r} precisam ser inteiros de 1 a 10000.")
        out["evolucao"][r] = list(lista)
    for b, conf in (cfg.get("baus") or {}).items():
        if b not in out["baus"]:
            raise ErroCarta(f"Baú desconhecido: {b}.")
        qtd = int(conf.get("qtd", out["baus"][b]["qtd"]))
        ch = {r: int(v) for r, v in (conf.get("chances") or out["baus"][b]["chances"]).items()}
        if not 0 <= qtd <= 20 or set(ch) - set(CAT.RARIDADES) or any(v < 0 for v in ch.values()) or (qtd and sum(ch.values()) <= 0):
            raise ErroCarta(f"Configuração do baú {b} inválida.")
        g = conf.get("garantia", out["baus"][b]["garantia"])
        if g is not None and g not in CAT.RARIDADES:
            raise ErroCarta(f"Garantia do baú {b} inválida.")
        out["baus"][b] = {"qtd": qtd, "chances": ch, "garantia": g, "extra": conf.get("extra")}
    return out


def niveis_max(cfg: dict) -> dict:
    return {r: 1 + len(cfg["evolucao"][r]) for r in CAT.RARIDADES}


# ------------------------------------------------------------------ coleção
BARALHO_EQUIP = 5                                  # cartas no baralho
MAX_POR_RARIDADE = {"epica": 1, "lendaria": 1}     # as fortes não repetem; comum e rara, sem teto


def cabe_no_baralho(doc: dict, tk: str) -> tuple[bool, str]:
    """A carta cabe no baralho como ele está? (tamanho e teto da raridade dela)"""
    if tk in doc["equip"]:
        return True, ""
    if len(doc["equip"]) >= BARALHO_EQUIP:
        return False, f"O baralho já tem {BARALHO_EQUIP} cartas. Tire uma para pôr outra."
    r = (doc["cartas"].get(tk) or {}).get("rar")
    teto = MAX_POR_RARIDADE.get(r)
    if teto is not None and sum(1 for t in doc["equip"] if doc["cartas"][t]["rar"] == r) >= teto:
        return False, f"O baralho aceita no máximo {teto} carta {CAT.ROTULO_RARIDADE[r]}."
    return True, ""


def colecao_vazia() -> dict:
    return {"v": 1, "cartas": {}, "equip": [], "ids": [], "log": []}


def normalizar(doc) -> dict:
    d = colecao_vazia()
    if isinstance(doc, dict) and doc.get("v") == 1:
        d["cartas"] = {t: dict(c) for t, c in (doc.get("cartas") or {}).items() if isinstance(c, dict) and c.get("rar") in CAT.RARIDADES}
        eq = doc.get("equip")
        if isinstance(eq, dict):                   # formato antigo (um espaço por raridade): vira lista, da comum à lendária
            eq = [eq.get(r) for r in CAT.RARIDADES]
        for t in (eq or []):                       # só o que a pessoa tem, sem repetir e respeitando os tetos de hoje
            if t in d["cartas"] and cabe_no_baralho(d, t)[0] and t not in d["equip"]:
                d["equip"].append(t)
        d["ids"] = list(doc.get("ids") or [])[-IDS_MAX:]
        d["log"] = list(doc.get("log") or [])[:LOG_MAX]
    return d


def _registrar(doc: dict, tipo: str, agora_iso: str, **dados) -> None:
    doc["log"] = [{"tipo": tipo, "em": agora_iso, **dados}] + doc["log"][: LOG_MAX - 1]


def adicionar(doc: dict, tk: str, rar_catalogo: str, agora_iso: str) -> dict:
    """Uma cópia de `tk` entra na coleção. Primeira vez: carta nova (nível 1, raridade fixada). Depois: vira cópia extra (para evoluir).
    Devolve {"tk", "rar", "nova", "copias", "nivel"}. Muda `doc`."""
    c = doc["cartas"].get(tk)
    if c is None:
        c = {"rar": rar_catalogo, "nivel": 1, "copias": 0, "total": 1, "escolhas": [], "desde": agora_iso}
        doc["cartas"][tk] = c
        nova = True
    else:
        c["copias"] = int(c.get("copias", 0)) + 1
        c["total"] = int(c.get("total", 1)) + 1
        nova = False
    return {"tk": tk, "rar": c["rar"], "nova": nova, "copias": c["copias"], "nivel": c["nivel"]}


def custo_evolucao(cfg: dict, rar: str, nivel: int) -> int | None:
    """Cópias extras para subir de `nivel` para `nivel+1` (None no nível máximo)."""
    lista = cfg["evolucao"][rar]
    return lista[nivel - 1] if 1 <= nivel <= len(lista) else None


def progresso(cfg: dict, c: dict) -> dict:
    custo = custo_evolucao(cfg, c["rar"], c["nivel"])
    return {"copias": c["copias"], "precisa": custo, "pode": custo is not None and c["copias"] >= custo, "maximo": custo is None,
            "nivel_max": niveis_max(cfg)[c["rar"]]}


def evoluir(doc: dict, cfg: dict, tk: str, ind: str, agora_iso: str) -> dict:
    """Gasta as cópias da MESMA carta, sobe 1 nível e grava a melhoria escolhida (permanente e cumulativa). ErroCarta se não puder."""
    if ind not in CAT.INDICADORES:
        raise ErroCarta("Escolha P/L, DY ou ROE para melhorar.")
    c = doc["cartas"].get(tk)
    if c is None:
        raise ErroCarta("Você ainda não tem essa carta.")
    custo = custo_evolucao(cfg, c["rar"], c["nivel"])
    if custo is None:
        raise ErroCarta("Essa carta já está no nível máximo.")
    if c["copias"] < custo:
        raise ErroCarta(f"Faltam {custo - c['copias']} cópia(s) de {tk} para evoluir.")
    c["copias"] -= custo
    c["nivel"] += 1
    c["escolhas"] = list(c.get("escolhas") or []) + [ind]
    _registrar(doc, "evolucao", agora_iso, tk=tk, nivel=c["nivel"], ind=ind, gasto=custo)
    return {"tk": tk, "nivel": c["nivel"], "ind": ind, "gasto": custo, "copias": c["copias"]}


def equipar(doc: dict, tk: str, agora_iso: str) -> dict:
    """Põe `tk` no baralho. Recusa se já estiver cheio ou se a raridade dela já bateu o teto."""
    c = doc["cartas"].get(tk)
    if c is None:
        raise ErroCarta("Você ainda não tem essa carta.")
    r = c["rar"]
    if tk in doc["equip"]:
        return {"tk": tk, "rar": r, "saiu": None}
    ok, msg = cabe_no_baralho(doc, tk)
    if not ok:
        raise ErroCarta(msg)
    doc["equip"].append(tk)
    _registrar(doc, "equipar", agora_iso, tk=tk, rar=r, saiu=None)
    return {"tk": tk, "rar": r, "saiu": None}


def desequipar(doc: dict, tk: str, agora_iso: str) -> dict:
    """Tira `tk` do baralho."""
    if tk not in doc["equip"]:
        raise ErroCarta("Essa carta não está no baralho.")
    doc["equip"].remove(tk)
    _registrar(doc, "desequipar", agora_iso, tk=tk, rar=(doc["cartas"].get(tk) or {}).get("rar"))
    return {"tk": tk, "saiu": tk}


def equipadas(doc: dict) -> list[str]:
    """O baralho, na ordem em que a pessoa montou."""
    return list(doc["equip"])


# ------------------------------------------------------------------ sorteio (determinístico: mesma conta + mesma recompensa = mesmo resultado)
def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))


def _sortear_raridade(rng: random.Random, chances: dict, disponiveis: dict) -> str:
    itens = [(r, int(chances.get(r, 0))) for r in CAT.RARIDADES if disponiveis.get(r) and int(chances.get(r, 0)) > 0]
    if not itens:
        itens = [(r, 1) for r in CAT.RARIDADES if disponiveis.get(r)]
    n = rng.random() * sum(p for _r, p in itens)
    for r, p in itens:
        if n < p:
            return r
        n -= p
    return itens[-1][0]


def sortear_bau(seed: str, conf: dict, por_raridade: dict) -> list[str]:
    """Cartas de um baú. `por_raridade`: {raridade: [tickers disponíveis no catálogo]}. Duplicatas são permitidas."""
    rng = _rng(seed)
    qtd = int(conf.get("qtd") or 0)
    if qtd <= 0 or not any(por_raridade.values()):
        return []
    rars = [_sortear_raridade(rng, conf["chances"], por_raridade) for _ in range(qtd)]
    g = conf.get("garantia")
    if g and por_raridade.get(g):
        ordem = CAT.RARIDADES.index(g)
        if not any(CAT.RARIDADES.index(r) >= ordem for r in rars):
            rars[-1] = g
    return [rng.choice(sorted(por_raridade[r])) for r in rars]


def sortear_inicial(seed: str, raridades: list[str], por_raridade: dict) -> list[str]:
    rng = _rng("inicial|" + seed)
    return [rng.choice(sorted(por_raridade[r])) for r in raridades if por_raridade.get(r)]


def entregar(doc: dict, ref: str, tks: list[str], raridade_de, origem: str, agora_iso: str) -> dict:
    """Entrega uma recompensa UMA vez (por `ref`). Devolve {"ja": bool, "itens": [...]} com o resultado de cada carta."""
    if ref in doc["ids"]:
        return {"ja": True, "itens": []}
    itens = [adicionar(doc, t, raridade_de(t), agora_iso) for t in tks]
    doc["ids"] = (doc["ids"] + [ref])[-IDS_MAX:]
    _registrar(doc, "recompensa", agora_iso, ref=ref, origem=origem, cartas=list(tks))
    return {"ja": False, "itens": itens}


# ------------------------------------------------------------------ atributos de jogo (cópia com bônus; o dado real fica separado)
def bonus_das_escolhas(escolhas: list[str]) -> dict:
    return {i: sum(1 for e in escolhas or [] if e == i) for i in CAT.INDICADORES}


def aplicar_bonus(ind: str, valor: float, vezes: int, bonus: dict) -> float:
    if not vezes or ind not in bonus:
        return valor
    tipo, passo = bonus[ind]
    if tipo == "rel":
        return valor * (1 + passo) ** vezes
    return valor + passo * vezes


def carta_de_jogo(base: dict, c: dict, cfg: dict, ident: str) -> dict:
    """Cópia da carta do snapshot (`base`) com os atributos de jogo da coleção (`c`). `ident` é o id da carta no duelo."""
    out = copy.deepcopy(base)
    real = dict(base.get("ind") or {})
    vezes = bonus_das_escolhas(c.get("escolhas"))
    out["ind"] = {k: (aplicar_bonus(k, float(v), vezes.get(k, 0), cfg["bonus"]) if k in vezes else v) for k, v in real.items()}
    out.update(id=ident, real=real, nivel=c["nivel"], rar=c["rar"], melhorias=vezes)
    return out
