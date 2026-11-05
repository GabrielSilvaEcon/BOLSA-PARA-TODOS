"""Etapa 15 · Prevenção de abuso (sem punir ninguém sozinho).

 · RAJADA: no máximo N usos de recursos pesados (IA, atualizar dados) por minuto e por pessoa; passou disso, espera um minuto.
 · BLOQUEIOS REPETIDOS: cada vez que alguém bate no limite do plano, o app conta; a pessoa que passa de X bloqueios no dia aparece em
   Administração > Uso e gera um aviso ao administrador. O app NUNCA suspende conta sozinho: quem decide é o administrador (Usuários > Suspender).
Configurável em Administração > Uso. Falhas aqui nunca bloqueiam ninguém.
"""
from __future__ import annotations

import time
from collections import defaultdict, deque

CH = "abuso_cfg"
_janelas: dict = defaultdict(deque)
_c = {"cfg": None, "t": 0.0}


def _padrao() -> dict:
    return {"rajada_por_min": 8, "alerta_negadas_dia": 15}


def _int(v, lo, hi, padrao) -> int:
    try:
        return max(lo, min(hi, int(float(str(v).replace(",", ".")))))
    except (TypeError, ValueError):
        return padrao


def config() -> dict:
    if _c["cfg"] is not None and time.time() - _c["t"] < 60:
        return _c["cfg"]
    cfg = _padrao()
    try:
        import banco
        lido = banco.cfg_ler(CH) or {}
        cfg["rajada_por_min"] = _int(lido.get("rajada_por_min", cfg["rajada_por_min"]), 0, 120, 8)
        cfg["alerta_negadas_dia"] = _int(lido.get("alerta_negadas_dia", cfg["alerta_negadas_dia"]), 0, 1000, 15)
    except Exception:
        pass
    _c["cfg"], _c["t"] = cfg, time.time()
    return cfg


def salvar(cfg: dict) -> dict:
    import banco
    limpo = {"rajada_por_min": _int(cfg.get("rajada_por_min"), 0, 120, 8), "alerta_negadas_dia": _int(cfg.get("alerta_negadas_dia"), 0, 1000, 15)}
    banco.cfg_gravar(CH, limpo)
    _c["cfg"], _c["t"] = limpo, time.time()
    return limpo


def limpar() -> None:
    _janelas.clear()
    _c["cfg"], _c["t"] = None, 0.0


def rajada_excedida(quem: str, recurso: str, agora: float | None = None) -> bool:
    """Registra um uso e diz se passou do limite por minuto (0 = sem limite). Memória do processo: reinicia com o app."""
    lim = config()["rajada_por_min"]
    if not lim:
        return False
    agora = agora if agora is not None else time.time()
    j = _janelas[(quem, recurso)]
    while j and agora - j[0] > 60:
        j.popleft()
    if len(j) >= lim:
        return True
    j.append(agora)
    return False


def suspeitos(dia: str | None = None) -> list[dict]:
    """Contas que bateram no limite mais vezes que o configurado no dia (para o administrador olhar)."""
    import banco
    import planos
    dia = dia or planos.hoje()
    lim = config()["alerta_negadas_dia"]
    if not lim:
        return []
    out = []
    for l in banco._selecionar("config_sistema", {"id": ("comeca", f"uso|{dia}|")}, ["id", "dados"], limite=2000):
        d = banco._de_js(l["dados"]) or {}
        if int(d.get("_neg", 0)) >= lim and d.get("_e"):
            out.append({"email": d["_e"], "negadas": int(d["_neg"]), "rajadas": int(d.get("_raj", 0)),
                        "usos": sum(int(d.get(r, 0)) for r, v in planos.RECURSOS.items() if v["tipo"] == "dia")})
    return sorted(out, key=lambda x: -x["negadas"])


def avisar(agora) -> int:
    """Avisa os administradores (uma vez por conta/dia) sobre contas com bloqueios repetidos. Roda no monitor."""
    import banco
    import planos
    lista = suspeitos()
    if not lista:
        return 0
    admins = [c["email"] for c in banco.sis_contas_monitoraveis(500) if c.get("papel") == "admin"]
    n = 0
    for x in lista[:10]:
        for email in admins:
            ok = banco.sis_notif_inserir(email, {"dedup": f"abuso|{planos._h(x['email'])}|{planos.hoje()}", "categoria": "sistema", "importancia": "media",
                                                 "titulo": f"Uso fora do padrão: {x['email']}"[:200],
                                                 "texto": f"Bateu no limite do plano {x['negadas']} vezes hoje ({x['rajadas']} por rajada). Veja Administração > Uso. "
                                                          "Nada foi bloqueado: você decide se suspende.", "origem": "abuso", "pagina": "administracao"})
            n += 1 if ok else 0
    return n
