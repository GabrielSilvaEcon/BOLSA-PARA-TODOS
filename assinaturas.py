"""Etapas 11, 12 e 13 · Ciclo de vida da assinatura: carência/inadimplência, cancelamento, avisos de renovação, cupons e teste grátis.

O pagamento online (Mercado Pago) está em pagamentos.py e libera o plano sozinho; o administrador também pode ativar/renovar à mão (planos.definir_plano / renovar). Este módulo cuida do resto:
 · CARÊNCIA: depois do vencimento o plano continua valendo por N dias (padrão 3) — é a "inadimplência tolerada"; passado o prazo volta ao Gratuito.
 · CANCELAR RENOVAÇÃO: a pessoa mantém o plano até a data de validade e depois volta ao Gratuito; pode reativar antes disso.
 · AVISOS: notificação ao usuário N dias antes do vencimento (padrão 7, 3 e 1), no dia, durante a carência e quando o plano acaba.
 · CUPONS: código que dá dias de um plano pago (uma vez por conta; limite de usos e de validade; 5 tentativas por dia por conta).
 · TESTE GRÁTIS: opcional (desligado até o administrador ligar), uma vez por conta, só para quem nunca teve plano pago.
Tudo configurável em Administração > Assinaturas. Falha de banco nunca bloqueia o app.
"""
from __future__ import annotations

import re
import threading
import time
from datetime import date, datetime, timedelta

import planos

CH = "assin_cfg"
TENTATIVAS_CUPOM_DIA = 5
_c = {"cfg": None, "t": 0.0}
_lock = threading.Lock()                      # cupom e teste são raros: um trinco só basta e evita uso duplo no mesmo instante


def _padrao() -> dict:
    return {"carencia_dias": 3, "avisos_dias": [7, 3, 1], "teste": {"ligado": False, "plano": "plus", "dias": 7}}


def _int(v, lo, hi, padrao) -> int:
    try:
        return max(lo, min(hi, int(float(str(v).replace(",", ".")))))
    except (TypeError, ValueError):
        return padrao


def _aviso(v) -> int:
    """Dia de aviso válido (1 a 30) ou 0 se o valor não serve (zero, negativo ou texto)."""
    try:
        return 0 if float(str(v).replace(",", ".")) < 1 else _int(v, 1, 30, 0)
    except (TypeError, ValueError):
        return 0


def config() -> dict:
    agora = time.time()
    if _c["cfg"] is not None and agora - _c["t"] < 60:
        return _c["cfg"]
    cfg = _padrao()
    try:
        import banco
        lido = banco.cfg_ler(CH) or {}
        cfg["carencia_dias"] = _int(lido.get("carencia_dias", cfg["carencia_dias"]), 0, 30, 3)
        av = [_aviso(x) for x in (lido.get("avisos_dias") or cfg["avisos_dias"])]
        cfg["avisos_dias"] = sorted({x for x in av if x}, reverse=True)[:5]
        t = lido.get("teste") or {}
        cfg["teste"] = {"ligado": bool(t.get("ligado", False)), "plano": t.get("plano") if t.get("plano") in ("plus", "premium") else "plus",
                        "dias": _int(t.get("dias", 7), 1, 30, 7)}
    except Exception:
        pass
    _c["cfg"], _c["t"] = cfg, agora
    return cfg


def salvar(cfg: dict) -> dict:
    import banco
    t = cfg.get("teste") or {}
    av = sorted({_aviso(x) for x in (cfg.get("avisos_dias") or [])} - {0}, reverse=True)[:5]
    limpo = {"carencia_dias": _int(cfg.get("carencia_dias"), 0, 30, 3), "avisos_dias": av,
             "teste": {"ligado": bool(t.get("ligado")), "plano": t.get("plano") if t.get("plano") in ("plus", "premium") else "plus",
                       "dias": _int(t.get("dias"), 1, 30, 7)}}
    banco.cfg_gravar(CH, limpo)
    _c["cfg"], _c["t"] = limpo, time.time()
    return limpo


def limpar_cache() -> None:
    _c["cfg"], _c["t"] = None, 0.0


def parse_dias(txt: str) -> list[int]:
    return sorted({_aviso(x) for x in re.split(r"[,\s;]+", str(txt or "")) if x} - {0}, reverse=True)[:5]


# ---------------------------------------------------------------- cancelamento
def cancelar_renovacao(email: str) -> str:
    """Devolve 'fim_da_validade' (mantém até a data) ou 'agora' (plano sem validade volta ao Gratuito na hora)."""
    a = planos.assinatura_de(email)
    if a["contratado"] in ("gratuito", "visitante") or a["vencida"]:
        raise ValueError("Você não tem uma assinatura paga ativa para cancelar.")
    if a["ate"] is None:
        planos.definir_plano(email, "gratuito", origem="cancelado")
        return "agora"
    planos.marcar_cancelado(email, True)
    return "fim_da_validade"


def reativar_renovacao(email: str) -> None:
    a = planos.assinatura_de(email)
    if not a.get("cancelado") or a["vencida"]:
        raise ValueError("Não há cancelamento para desfazer.")
    planos.marcar_cancelado(email, False)


# ---------------------------------------------------------------- avisos de vencimento (rodam no monitor)
def avisar_vencimentos(agora: datetime) -> int:
    """Notifica quem está perto de vencer, venceu (carência) ou acabou de voltar ao Gratuito. Uma notificação por data/situação."""
    import banco
    cfg = config()
    car = cfg["carencia_dias"]
    n = 0
    for x in planos.listar_assinaturas():
        email, dias = x["email"], x["dias"]
        if dias is None or "@" not in email:
            continue
        nome = planos.ROTULO[x["plano"]]
        fim = _br(x["ate"])
        if dias in cfg["avisos_dias"] or dias == 0:
            t = (f"Seu plano {nome} vence hoje" if dias == 0 else f"Seu plano {nome} vence em {dias} dia" + ("s" if dias > 1 else ""))
            tx = (f"Validade até {fim}. " + ("Você cancelou a renovação: depois dessa data volta ao plano Gratuito."
                                            if x.get("cancelado") else "Para continuar, peça a renovação ao administrador."))
            grave = dias <= 1
        elif -car <= dias < 0:
            t, tx, grave = f"Seu plano {nome} venceu", f"Venceu em {fim}. Você ainda tem {car + dias} dia(s) de carência com os limites do plano; depois volta ao Gratuito.", True
        elif dias == -car - 1:
            t, tx, grave = "Você voltou ao plano Gratuito", f"O plano {nome} acabou em {fim}. Seus dados continuam guardados; peça a renovação quando quiser.", True
        else:
            continue
        ok = banco.sis_notif_inserir(email, {"dedup": f"venc|{x['ate']}|{dias}", "categoria": "sistema", "importancia": "alta" if grave else "media",
                                             "titulo": t, "texto": tx, "origem": "assinatura", "pagina": "conta"})
        n += 1 if ok else 0
    return n


def _br(iso) -> str:
    try:
        a, m, d = str(iso).split("-")
        return f"{int(d):02d}/{int(m):02d}/{a}"
    except Exception:
        return "—"


# ---------------------------------------------------------------- cupons
_COD = re.compile(r"^[A-Z0-9_-]{3,20}$")


def _cod(c) -> str:
    return str(c or "").strip().upper()


def criar_cupom(codigo: str, plano: str, dias: int, validade_ate: str | None = None, max_usos: int = 0, nota: str = "") -> dict:
    import banco
    c = _cod(codigo)
    if not _COD.match(c):
        raise ValueError("Código inválido: use 3 a 20 letras, números, - ou _.")
    if plano not in ("plus", "premium"):
        raise ValueError("O cupom precisa dar um plano pago (Plus ou Premium).")
    if validade_ate:
        try:
            date.fromisoformat(validade_ate)
        except ValueError:
            raise ValueError("Data de validade inválida.")
    doc = {"codigo": c, "plano": plano, "dias": _int(dias, 1, 365, 30), "validade_ate": validade_ate or None,
           "max_usos": _int(max_usos, 0, 100000, 0), "usos": 0, "ativo": True, "nota": str(nota)[:80], "criado": planos.hoje()}
    antigo = banco.cfg_ler("cupom|" + c)
    if antigo:
        doc["usos"] = int(antigo.get("usos", 0))
    banco.cfg_gravar("cupom|" + c, doc)
    return doc


def definir_ativo(codigo: str, ativo: bool) -> None:
    import banco
    c = _cod(codigo)
    d = banco.cfg_ler("cupom|" + c)
    if not d:
        raise ValueError("Cupom não encontrado.")
    d["ativo"] = bool(ativo)
    banco.cfg_gravar("cupom|" + c, d)


def listar_cupons() -> list[dict]:
    import banco
    out = []
    for l in banco._selecionar("config_sistema", {"id": ("comeca", "cupom|")}, ["id", "dados"], limite=1000):
        if str(l["id"]).startswith("cupom|"):
            d = banco._de_js(l["dados"]) or {}
            if d.get("codigo"):
                out.append(d)
    return sorted(out, key=lambda d: d["codigo"])


def resgatar_cupom(email: str, codigo: str, papel: str | None = None) -> tuple[bool, str]:
    with _lock:
        return _resgatar_cupom(email, codigo, papel)


def _resgatar_cupom(email: str, codigo: str, papel: str | None = None) -> tuple[bool, str]:
    """Aplica o cupom à conta. (ok, mensagem). Nunca levanta erro por falha de banco: devolve mensagem."""
    import banco
    try:
        if papel in ("admin", "suporte"):
            return False, "Contas da equipe já têm acesso total."
        h = planos._h(email)
        chave_t = f"cupom_tent|{planos.hoje()}|{h}"
        t = banco.cfg_ler(chave_t) or {}
        if int(t.get("n", 0)) >= TENTATIVAS_CUPOM_DIA:
            return False, "Muitas tentativas hoje. Tente de novo amanhã."
        banco.cfg_gravar(chave_t, {"n": int(t.get("n", 0)) + 1})
        c = _cod(codigo)
        d = banco.cfg_ler("cupom|" + c) if _COD.match(c) else None
        if not d or not d.get("ativo"):
            return False, "Cupom inválido ou desativado."
        if d.get("validade_ate") and planos.hoje() > d["validade_ate"]:
            return False, "Este cupom já expirou."
        if d.get("max_usos") and int(d.get("usos", 0)) >= int(d["max_usos"]):
            return False, "Este cupom já atingiu o limite de usos."
        if banco.cfg_ler(f"resgate|{c}|{h}"):
            return False, "Você já usou este cupom."
        a = planos.assinatura_de(email)
        ordem = {"gratuito": 0, "plus": 1, "premium": 2}
        if not a["vencida"] and ordem.get(a["plano"], 0) > ordem[d["plano"]]:
            return False, f"Seu plano atual ({planos.ROTULO[a['plano']]}) já é superior ao do cupom."
        if not a["vencida"] and a["plano"] == d["plano"] and a["ate"]:
            novo = planos.renovar(email, d["dias"], origem="cupom")
        else:
            novo = planos.definir_plano(email, d["plano"], dias=d["dias"], origem="cupom")
        d["usos"] = int(d.get("usos", 0)) + 1
        banco.cfg_gravar("cupom|" + c, d)
        banco.cfg_gravar(f"resgate|{c}|{h}", {"quando": planos.hoje()})
        return True, f"Cupom aplicado: {planos.ROTULO[d['plano']]} até {_br(novo['ate'])}."
    except Exception as e:
        try:
            banco.registrar_erro("assinaturas.cupom", e)
        except Exception:
            pass
        return False, "Não consegui aplicar o cupom agora. Tente de novo em instantes."


# ---------------------------------------------------------------- teste grátis
def teste_disponivel(email: str | None, papel: str | None = None) -> tuple[bool, str]:
    cfg = config()["teste"]
    if not email or papel in ("admin", "suporte") or not cfg["ligado"]:
        return False, ""
    try:
        import banco
        if banco.cfg_ler("teste|" + planos._h(email)):
            return False, "Você já usou o teste grátis."
        a = planos.assinatura_de(email)
        if a["contratado"] != "gratuito":
            return False, ""
        return True, f"Teste grátis do {planos.ROTULO[cfg['plano']]} por {cfg['dias']} dias"
    except Exception:
        return False, ""


def iniciar_teste(email: str, papel: str | None = None) -> str:
    with _lock:
        return _iniciar_teste(email, papel)


def _iniciar_teste(email: str, papel: str | None = None) -> str:
    import banco
    ok, _ = teste_disponivel(email, papel)
    if not ok:
        raise ValueError("O teste grátis não está disponível para esta conta.")
    cfg = config()["teste"]
    d = planos.definir_plano(email, cfg["plano"], dias=cfg["dias"], origem="teste")
    banco.cfg_gravar("teste|" + planos._h(email), {"quando": planos.hoje(), "plano": cfg["plano"]})
    return f"Teste iniciado: {planos.ROTULO[cfg['plano']]} até {_br(d['ate'])}."
