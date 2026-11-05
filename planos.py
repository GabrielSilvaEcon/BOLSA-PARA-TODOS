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


def _carencia() -> int:
    """Dias de tolerância depois do vencimento (assinaturas.config; 0 se não der para ler)."""
    try:
        import assinaturas
        return int(assinaturas.config()["carencia_dias"])
    except Exception:
        return 0


def _dias_restantes(ate: str | None) -> int | None:
    """Dias até o fim da validade (0 = vence hoje; negativo = já venceu). None = sem validade (vale até alguém mudar)."""
    if not ate:
        return None
    from datetime import date
    try:
        return (date.fromisoformat(ate) - _hoje_data()).days
    except ValueError:
        return None


def _efetivo(d: dict, carencia: int | None = None) -> str:
    """Plano que vale hoje para um documento de assinatura (vencida além da carência = gratuito)."""
    v = d.get("plano")
    p = v if v in PLANOS else "gratuito"
    dr = _dias_restantes(d.get("ate"))
    car = _carencia() if carencia is None else carencia
    return "gratuito" if dr is not None and dr < -car else p


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
        p = _efetivo(_ler_assinatura(email))
    except Exception:
        pass
    _cache["planos"][email] = (p, agora)
    return p


def assinatura_de(email: str | None, papel: str | None = None) -> dict:
    """Situação da assinatura: plano em vigor, plano contratado, validade, dias, carência, cancelamento e histórico."""
    if not email:
        return {"plano": "visitante", "contratado": "visitante", "ate": None, "dias": None, "vencida": False, "carencia": False,
                "cancelado": False, "origem": "", "historico": []}
    if papel in ("admin", "suporte"):
        return {"plano": "premium", "contratado": "premium", "ate": None, "dias": None, "vencida": False, "carencia": False,
                "cancelado": False, "origem": "equipe", "historico": []}
    try:
        d = _ler_assinatura(email)
    except Exception:
        d = {}
    contratado = d.get("plano") if d.get("plano") in PLANOS else "gratuito"
    dias = _dias_restantes(d.get("ate"))
    car = _carencia()
    vencida = contratado != "gratuito" and dias is not None and dias < -car
    return {"plano": "gratuito" if vencida else contratado, "contratado": contratado, "ate": d.get("ate"), "dias": dias, "vencida": vencida,
            "carencia": contratado != "gratuito" and dias is not None and -car <= dias < 0, "carencia_dias": car,
            "cancelado": bool(d.get("cancelado")), "origem": d.get("origem") or "", "historico": list(d.get("historico") or [])}


def _com_historico(antigo: dict, doc: dict, evento: str, detalhe: str = "") -> dict:
    h = list(antigo.get("historico") or [])
    h.append([hoje(), evento, str(detalhe)[:60]])
    doc["historico"] = h[-20:]
    return doc


def definir_plano(email: str, plano: str, dias: int | None = None, origem: str = "manual") -> dict:
    """Define o plano da conta. `dias` = validade a partir de hoje (None = sem validade). Devolve a assinatura gravada."""
    if plano not in PLANOS:
        raise ValueError("plano desconhecido")
    import banco
    from datetime import timedelta
    ate = None
    if dias is not None and plano != "gratuito":
        ate = (_hoje_data() + timedelta(days=max(1, min(int(dias), 3650)))).isoformat()
    antigo = _ler_assinatura(email)
    doc = _com_historico(antigo, {"plano": plano, "ate": ate, "desde": hoje(), "origem": str(origem)[:20], "email": email, "cancelado": False},
                         "plano", f"{plano} até {ate or 'sem validade'} ({origem})")
    banco.cfg_gravar("plano|" + _h(email), doc)
    _cache["planos"].pop(email, None)
    return doc


def renovar(email: str, dias: int, origem: str = "manual") -> dict:
    """Soma `dias` à validade: a partir do vencimento, se ainda vale (ou está na carência); a partir de hoje, se já acabou. Mantém o plano."""
    import banco
    from datetime import date, timedelta
    d = _ler_assinatura(email)
    plano = d.get("plano") if d.get("plano") in PLANOS else "gratuito"
    if plano == "gratuito":
        raise ValueError("A conta está no plano gratuito: escolha um plano pago primeiro.")
    base = _hoje_data()
    try:
        if d.get("ate") and _efetivo(d) != "gratuito":          # ainda vale (ou está na carência): continua do vencimento
            base = date.fromisoformat(d["ate"])
    except ValueError:
        pass
    ate = (base + timedelta(days=max(1, min(int(dias), 3650)))).isoformat()
    doc = _com_historico(d, {**d, "plano": plano, "ate": ate, "origem": str(origem)[:20], "email": email, "cancelado": False},
                         "renovou", f"+{int(dias)} dias, até {ate} ({origem})")
    banco.cfg_gravar("plano|" + _h(email), doc)
    _cache["planos"].pop(email, None)
    return doc


def marcar_cancelado(email: str, cancelado: bool) -> dict:
    import banco
    d = _ler_assinatura(email)
    doc = _com_historico(d, {**d, "cancelado": bool(cancelado), "email": email}, "cancelou a renovação" if cancelado else "reativou a renovação")
    banco.cfg_gravar("plano|" + _h(email), doc)
    _cache["planos"].pop(email, None)
    return doc


def listar_assinaturas() -> list[dict]:
    """Contas com plano pago definido (para o administrador): e-mail, plano, validade, dias restantes e situação."""
    import banco
    car = _carencia()
    out = []
    for l in banco._selecionar("config_sistema", {"id": ("comeca", "plano|")}, ["id", "dados"], limite=5000):
        if not str(l["id"]).startswith("plano|"):
            continue
        d = banco._de_js(l["dados"]) or {}
        if d.get("plano") not in PLANOS or d.get("plano") == "gratuito":
            continue
        dias = _dias_restantes(d.get("ate"))
        sit = ("sem_validade" if dias is None else "vencida" if dias < -car else "carencia" if dias < 0 else "vencendo" if dias <= 7 else "ativa")
        out.append({"email": d.get("email") or "(conta antiga, sem e-mail registrado)", "plano": d["plano"], "ate": d.get("ate"),
                    "dias": dias, "situacao": sit, "origem": d.get("origem") or "", "desde": d.get("desde") or "", "cancelado": bool(d.get("cancelado"))})
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


import threading
_LOCKS = [threading.Lock() for _ in range(64)]          # um trinco por "faixa" de contas: leitura-e-gravação do uso é atômica por conta


def _trinco(email: str | None):
    return _LOCKS[int(hashlib.sha1(str(email or "visitante").encode()).hexdigest()[:6], 16) % 64]


def usar(recurso: str, unico: str | None = None, email: str | None = "?", papel: str | None = None) -> tuple[bool, dict]:
    """Veja `_usar`. O trinco evita que dois pedidos simultâneos da mesma conta passem do limite (corrida de leitura-e-gravação)."""
    if email == "?":
        email, papel = _ator()
    with _trinco(email):
        return _usar(recurso, unico, email, papel)


def _usar(recurso: str, unico: str | None = None, email: str | None = "?", papel: str | None = None) -> tuple[bool, dict]:
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
            _registrar_negada(email, doc)
            return False, info
        if RECURSOS[recurso]["tipo"] == "dia":                # Etapa 15: rajada (muitas ações em pouco tempo)
            try:
                import abuso
                if abuso.rajada_excedida(email or f"visitante{id(_estado_visitante())}", recurso):   # visitante: por sessão, não compartilhado
                    info["mensagem"] = "Muitas ações em pouco tempo. Aguarde um minuto e tente de novo."
                    _registrar_negada(email, doc, rajada=True)
                    return False, info
            except Exception:
                pass
        if email:
            doc["_e"] = email                              # só o administrador vê (painel Uso por usuário)
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


def _registrar_negada(email, doc: dict, rajada: bool = False) -> None:
    """Conta quantas vezes a pessoa bateu no limite hoje (sinal de abuso ou de plano pequeno demais). Só contas logadas."""
    if not email:
        return
    try:
        doc["_neg"] = int(doc.get("_neg", 0)) + 1
        if rajada:
            doc["_raj"] = int(doc.get("_raj", 0)) + 1
        doc["_e"] = email
        _gravar_uso(email, doc)
    except Exception:
        pass


def uso_agregado_hoje() -> dict:
    """Painel do administrador: quantas contas usaram recursos limitados hoje e o total por recurso (sem identificar ninguém)."""
    import banco
    linhas = banco._selecionar("config_sistema", {"id": ("comeca", f"uso|{hoje()}|")}, ["id", "dados"], limite=1000)
    tot = {r: 0 for r, v in RECURSOS.items() if v["tipo"] == "dia"}
    for l in linhas:
        d = banco._de_js(l["dados"]) or {}
        for r in tot:
            tot[r] += int(d.get(r, 0))
    return {"contas": len(linhas), "total": tot}


def apagar_conta(email: str, dias: int = 45) -> None:
    """LGPD: apaga o plano/assinatura e o uso diário recente da conta (guardam o e-mail). Ficam só marcas sem e-mail (hash) que impedem
    reusar teste grátis e cupom já usados: `teste|hash` e `resgate|código|hash`."""
    import banco
    from datetime import timedelta
    h = _h(email)
    banco.cfg_apagar("plano|" + h)
    for i in range(dias):
        banco.cfg_apagar(f"uso|{(_hoje_data() - timedelta(days=i)).isoformat()}|{h}")
    _cache["planos"].pop(email, None)


def contagem_por_plano() -> dict:
    """Quantas contas têm cada plano em vigor (vencidas além da carência contam como gratuito). Não identifica ninguém."""
    import banco
    out = {p: 0 for p in PLANOS}
    car = _carencia()
    for l in banco._selecionar("config_sistema", {"id": ("comeca", "plano|")}, ["id", "dados"], limite=5000):
        if str(l["id"]).startswith("plano|"):
            d = banco._de_js(l["dados"]) or {}
            if d.get("plano") in out:
                out[_efetivo(d, car)] += 1
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
