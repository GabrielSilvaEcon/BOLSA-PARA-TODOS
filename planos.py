"""Etapa 5 · Planos e limites de utilização.

Três planos (Gratuito, Investidor Plus, Investidor Premium) mais o "visitante" (sem conta). Os modos Iniciante, Intermediário e
Avançado NÃO são planos: valem para todos. Aqui não há preço nem pagamento (isso é a Fase 2); só quanto cada plano pode usar dos
recursos que consomem fontes externas ou processamento.
 · Os limites abaixo são PONTOS DE PARTIDA, escolhidos para proteger as cotas gratuitas; o administrador muda todos no painel
   (Administração > Consumo > Planos e limites). Nenhum deles vem de custo medido.
 · Plano de cada conta fica na tabela config_sistema (sem mudar o esquema). Sem registro = Gratuito. Administrador e suporte usam
   os limites do Premium. Mudar o plano é feito pelo administrador (não existe compra ainda).
 · Uso diário conta por dia de Brasília (UTC-3). Recurso do tipo "máximo" (ex.: nº de alertas) não é diário.
 · Falha do banco NUNCA bloqueia a pessoa: sem como conferir, o recurso é liberado (e o erro é registrado).
"""
from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone

PLANOS = ("gratuito", "plus", "premium")
ROTULO = {"visitante": "Visitante", "gratuito": "Gratuito", "plus": "Investidor Plus", "premium": "Investidor Premium"}
ORDEM = ("visitante",) + PLANOS

# id: rotulo, tipo ("dia" = por dia; "max" = quantidade máxima; "min" = intervalo mínimo em minutos), aplicado, padrão por plano
RECURSOS = {
    "ia_mensagens": {"rotulo": "Mensagens ao assistente de IA", "tipo": "dia", "aplicado": True,
                     "padrao": {"visitante": 3, "gratuito": 5, "plus": 30, "premium": 100}},
    "ia_resumos": {"rotulo": "Resumos com IA (ativos distintos)", "tipo": "dia", "aplicado": True,
                   "padrao": {"visitante": 5, "gratuito": 10, "plus": 40, "premium": 120}},
    "atualizar_dados": {"rotulo": "Botão Atualizar dados (limpa o cache de todos)", "tipo": "dia", "aplicado": True,
                        "padrao": {"visitante": 2, "gratuito": 3, "plus": 10, "premium": 30}},
    "alertas_max": {"rotulo": "Alertas de mercado ativos", "tipo": "max", "aplicado": True,
                    "padrao": {"visitante": 3, "gratuito": 3, "plus": 15, "premium": 50}},
    "verificacao_min": {"rotulo": "Intervalo mínimo do monitor (minutos)", "tipo": "min", "aplicado": True,
                        "padrao": {"visitante": 60, "gratuito": 60, "plus": 30, "premium": 15}},
    "carteira_posicoes": {"rotulo": "Posições na carteira", "tipo": "max", "aplicado": True,
                          "padrao": {"visitante": 10, "gratuito": 15, "plus": 60, "premium": 300}},
    "comparador_ativos": {"rotulo": "Ativos no comparador", "tipo": "max", "aplicado": True,
                          "padrao": {"visitante": 3, "gratuito": 4, "plus": 6, "premium": 8}},
}
CH_CFG = "planos_cfg"
_cache = {"cfg": None, "t": 0.0, "planos": {}}


def hoje() -> str:
    return (datetime.now(timezone.utc) - timedelta(hours=3)).strftime("%Y-%m-%d")


def _h(email: str) -> str:
    return hashlib.sha256(str(email or "").strip().lower().encode()).hexdigest()[:24]


# ---------------------------------------------------------------- limites (configuráveis)
def config() -> dict:
    agora = time.time()
    if _cache["cfg"] is not None and agora - _cache["t"] < 60:
        return _cache["cfg"]
    cfg = {}
    try:
        import banco
        cfg = (banco.cfg_ler(CH_CFG) or {}).get("limites") or {}
    except Exception:
        pass
    _cache["cfg"], _cache["t"] = cfg, agora
    return cfg


def salvar_limites(limites: dict) -> None:
    """limites: {plano: {recurso: n}} — só valores inteiros ≥ 0 de recursos e planos conhecidos."""
    limpo: dict = {}
    for pl, rs in (limites or {}).items():
        if pl not in ORDEM:
            continue
        for r, v in (rs or {}).items():
            if r in RECURSOS:
                limpo.setdefault(pl, {})[r] = max(0, int(v))
    import banco
    banco.cfg_gravar(CH_CFG, {"limites": limpo})
    _cache["cfg"], _cache["t"] = limpo, time.time()


def limite(plano: str, recurso: str) -> int:
    plano = plano if plano in ORDEM else "gratuito"
    return int((config().get(plano) or {}).get(recurso, RECURSOS[recurso]["padrao"][plano]))


# ---------------------------------------------------------------- plano de cada conta
def _hoje_data():
    from datetime import date
    return date.fromisoformat(hoje())


def _ler_assinatura(email: str) -> dict:
    import banco
    return banco.cfg_ler("plano|" + _h(email)) or {}


def _dias_restantes(ate: str | None) -> int | None:
    """Dias até o fim da validade (0 = vence hoje; negativo = vencida). None = sem validade (vale até alguém mudar)."""
    if not ate:
        return None
    from datetime import date
    try:
        return (date.fromisoformat(ate) - _hoje_data()).days
    except ValueError:
        return None


def plano_de(email: str | None, papel: str | None = None) -> str:
    if not email:
        return "visitante"
    if papel in ("admin", "suporte"):
        return "premium"
    agora = time.time()
    c = _cache["planos"].get(email)
    if c and agora - c[1] < 60:
        return c[0]
    p = "gratuito"
    try:
        d = _ler_assinatura(email)
        v = d.get("plano")
        p = v if v in PLANOS else "gratuito"
        dr = _dias_restantes(d.get("ate"))
        if dr is not None and dr < 0:                       # assinatura vencida volta ao gratuito (nada é apagado)
            p = "gratuito"
    except Exception:
        pass
    _cache["planos"][email] = (p, agora)
    return p


def assinatura_de(email: str | None, papel: str | None = None) -> dict:
    """Situação da assinatura da conta: plano contratado, validade, dias restantes e se está vencida."""
    if not email:
        return {"plano": "visitante", "contratado": "visitante", "ate": None, "dias": None, "vencida": False, "origem": ""}
    if papel in ("admin", "suporte"):
        return {"plano": "premium", "contratado": "premium", "ate": None, "dias": None, "vencida": False, "origem": "equipe"}
    try:
        d = _ler_assinatura(email)
    except Exception:
        d = {}
    contratado = d.get("plano") if d.get("plano") in PLANOS else "gratuito"
    dias = _dias_restantes(d.get("ate"))
    vencida = dias is not None and dias < 0 and contratado != "gratuito"
    return {"plano": "gratuito" if vencida else contratado, "contratado": contratado, "ate": d.get("ate"), "dias": dias,
            "vencida": vencida, "origem": d.get("origem") or ""}


def definir_plano(email: str, plano: str, dias: int | None = None, origem: str = "manual") -> dict:
    """Define o plano da conta. `dias` = validade a partir de hoje (None = sem validade). Devolve a assinatura gravada."""
    if plano not in PLANOS:
        raise ValueError("plano desconhecido")
    import banco
    from datetime import timedelta
    ate = None
    if dias is not None and plano != "gratuito":
        ate = (_hoje_data() + timedelta(days=max(1, min(int(dias), 3650)))).isoformat()
    doc = {"plano": plano, "ate": ate, "desde": hoje(), "origem": str(origem)[:20], "email": email}
    banco.cfg_gravar("plano|" + _h(email), doc)
    _cache["planos"].pop(email, None)
    return doc


def renovar(email: str, dias: int, origem: str = "manual") -> dict:
    """Soma `dias` à validade: a partir do vencimento, se ainda vale; a partir de hoje, se já venceu. Mantém o plano contratado."""
    import banco
    from datetime import date, timedelta
    d = _ler_assinatura(email)
    plano = d.get("plano") if d.get("plano") in PLANOS else "gratuito"
    if plano == "gratuito":
        raise ValueError("A conta está no plano gratuito: escolha um plano pago primeiro.")
    base = _hoje_data()
    try:
        if d.get("ate") and date.fromisoformat(d["ate"]) > base:
            base = date.fromisoformat(d["ate"])
    except ValueError:
        pass
    ate = (base + timedelta(days=max(1, min(int(dias), 3650)))).isoformat()
    doc = {**d, "plano": plano, "ate": ate, "origem": str(origem)[:20], "email": email}
    banco.cfg_gravar("plano|" + _h(email), doc)
    _cache["planos"].pop(email, None)
    return doc


def listar_assinaturas() -> list[dict]:
    """Contas com plano pago definido (para o administrador): e-mail, plano, validade, dias restantes e situação."""
    import banco
    out = []
    for l in banco._selecionar("config_sistema", {"id": ("contem", "plano|")}, ["id", "dados"], limite=5000):
        if not str(l["id"]).startswith("plano|"):
            continue
        d = banco._de_js(l["dados"]) or {}
        if d.get("plano") not in PLANOS or d.get("plano") == "gratuito":
            continue
        dias = _dias_restantes(d.get("ate"))
        sit = "sem_validade" if dias is None else "vencida" if dias < 0 else "vencendo" if dias <= 7 else "ativa"
        out.append({"email": d.get("email") or "(conta antiga, sem e-mail registrado)", "plano": d["plano"], "ate": d.get("ate"),
                    "dias": dias, "situacao": sit, "origem": d.get("origem") or "", "desde": d.get("desde") or ""})
    return sorted(out, key=lambda x: (x["dias"] is None, x["dias"] if x["dias"] is not None else 0))


# ---------------------------------------------------------------- uso diário
def _estado_visitante() -> dict:
    import streamlit as st
    return st.session_state.setdefault("_uso_visitante", {})


def _ator() -> tuple[str | None, str | None]:
    try:
        import streamlit as st
        c = st.session_state.get("_conta")
        return (c["email"], c["papel"]) if c else (None, None)
    except Exception:
        return None, None


def _doc_uso(email: str | None) -> dict:
    if not email:
        return _estado_visitante().setdefault(hoje(), {})
    import banco
    return banco.cfg_ler(f"uso|{hoje()}|{_h(email)}") or {}


def _gravar_uso(email: str | None, doc: dict) -> None:
    if not email:
        _estado_visitante()[hoje()] = doc
        return
    import banco
    banco.cfg_gravar(f"uso|{hoje()}|{_h(email)}", doc)


def usado_hoje(recurso: str, email: str | None = None) -> int:
    try:
        return int((_doc_uso(email) or {}).get(recurso, 0))
    except Exception:
        return 0


def usar(recurso: str, unico: str | None = None, email: str | None = "?", papel: str | None = None) -> tuple[bool, dict]:
    """Tenta gastar 1 unidade do recurso diário. `unico` = chave de repetição (mesmo item no mesmo dia conta uma vez só).
    Devolve (liberado, info{plano, usado, limite, mensagem}). Falha do banco libera."""
    if email == "?":
        email, papel = _ator()
    plano = plano_de(email, papel)
    lim = limite(plano, recurso)
    info = {"plano": plano, "limite": lim, "usado": 0, "mensagem": ""}
    try:
        doc = _doc_uso(email)
        vistos = list(doc.get("vistos") or [])
        chave = f"{recurso}:{hashlib.sha1(str(unico).encode()).hexdigest()[:12]}" if unico is not None else None
        usado = int(doc.get(recurso, 0))
        info["usado"] = usado
        if chave and chave in vistos:
            return True, info                              # já contado hoje: não gasta de novo
        if usado >= lim:
            info["mensagem"] = mensagem_limite(recurso, plano, lim)
            return False, info
        doc[recurso] = usado + 1
        if chave:
            doc["vistos"] = (vistos + [chave])[-60:]
        _gravar_uso(email, doc)
        info["usado"] = usado + 1
        return True, info
    except Exception as e:
        try:
            import banco
            banco.registrar_erro("planos.usar", e)
        except Exception:
            pass
        return True, info


def uso_agregado_hoje() -> dict:
    """Painel do administrador: quantas contas usaram recursos limitados hoje e o total por recurso (sem identificar ninguém)."""
    import banco
    linhas = banco._selecionar("config_sistema", {"id": ("contem", f"uso|{hoje()}|")}, ["id", "dados"], limite=1000)
    tot = {r: 0 for r, v in RECURSOS.items() if v["tipo"] == "dia"}
    for l in linhas:
        d = banco._de_js(l["dados"]) or {}
        for r in tot:
            tot[r] += int(d.get(r, 0))
    return {"contas": len(linhas), "total": tot}


def contagem_por_plano() -> dict:
    """Quantas contas têm cada plano (assinaturas vencidas não contam: voltaram ao gratuito). Não identifica ninguém."""
    import banco
    out = {p: 0 for p in PLANOS}
    for l in banco._selecionar("config_sistema", {"id": ("contem", "plano|")}, ["id", "dados"], limite=5000):
        if str(l["id"]).startswith("plano|"):
            d = banco._de_js(l["dados"]) or {}
            v = d.get("plano")
            dr = _dias_restantes(d.get("ate"))
            if v in out:
                out["gratuito" if dr is not None and dr < 0 else v] += 1
    return out


def mensagem_limite(recurso: str, plano: str, lim: int) -> str:
    r = RECURSOS[recurso]
    quem = ROTULO.get(plano, plano)
    if lim <= 0:
        return f"{r['rotulo']}: indisponível no plano {quem}."
    return f"Você usou todo o limite diário de “{r['rotulo']}” do plano {quem} ({lim}). Ele renova à meia-noite (horário de Brasília)."


def permitido_max(recurso: str, quantidade_atual: int, email: str | None = "?", papel: str | None = None) -> tuple[bool, str]:
    """Para recursos do tipo 'max': pode criar mais um? (ok, mensagem)."""
    if email == "?":
        email, papel = _ator()
    plano = plano_de(email, papel)
    lim = limite(plano, recurso)
    if quantidade_atual < lim:
        return True, ""
    return False, f"O plano {ROTULO[plano]} permite até {lim} em “{RECURSOS[recurso]['rotulo']}”. Apague algum ou peça ao administrador para mudar seu plano."


def limite_atual(recurso: str, email: str | None = "?", papel: str | None = None) -> tuple[int, str]:
    """Limite do plano da pessoa logada (ou visitante) para um recurso e o nome do plano. Nunca levanta erro."""
    try:
        if email == "?":
            email, papel = _ator()
        plano = plano_de(email, papel)
        return limite(plano, recurso), ROTULO[plano]
    except Exception:
        return 10 ** 6, ROTULO["gratuito"]


def intervalo_minimo(email: str, papel: str | None = None) -> int:
    """Menor intervalo (min) entre verificações do monitor para esta conta."""
    return limite(plano_de(email, papel), "verificacao_min")


def resumo_do_usuario(email: str | None, papel: str | None = None) -> dict:
    plano = plano_de(email, papel)
    linhas = []
    for rid, r in RECURSOS.items():
        lim = limite(plano, rid)
        linha = {"id": rid, "rotulo": r["rotulo"], "tipo": r["tipo"], "limite": lim, "aplicado": r["aplicado"], "usado": None}
        if r["tipo"] == "dia" and r["aplicado"]:
            linha["usado"] = usado_hoje(rid, email)
        linhas.append(linha)
    return {"plano": plano, "rotulo": ROTULO[plano], "linhas": linhas, "assinatura": assinatura_de(email, papel)}
