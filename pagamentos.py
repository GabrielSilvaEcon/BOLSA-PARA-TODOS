"""Pagamento online dos planos pelo Mercado Pago (Pix e cartão), pago à vista por período (1 mês ou 12 meses).

Como funciona (o Streamlit não recebe avisos automáticos do provedor, então a confirmação é feita consultando a API):
 1. A pessoa escolhe plano e período. `criar_cobranca` cria no Mercado Pago uma "preferência de pagamento" com o valor lido de
    precificacao.py (o usuário nunca informa valor) e guarda um registro `pagto|<ref>` com o que foi pedido.
 2. A pessoa paga na página segura do Mercado Pago e volta ao app.
 3. `verificar` consulta `/v1/payments/search` pela referência. Se houver pagamento APROVADO, de valor igual ou maior que o pedido,
    libera o plano (planos.definir_plano / renovar). O registro é marcado como pago e o id do pagamento é gravado, então o mesmo
    pagamento nunca libera dias duas vezes.
Segredos: `[mercadopago] access_token` (obrigatório) e `app_url` (endereço do app, para o botão "voltar ao app") nos secrets.
O token nunca é gravado em banco, log ou tela. Falha de rede ou do provedor nunca derruba o app.
"""
from __future__ import annotations

import re
import threading
import time
import uuid
from datetime import datetime, timedelta, timezone

import planos

API = "https://api.mercadopago.com"
PERIODOS = {"mensal": {"rotulo": "1 mês", "dias": 30, "meses": 1}, "anual": {"rotulo": "12 meses", "dias": 365, "meses": 12}}
PAGOS = ("plus", "premium")
CH_CFG = "pagto_cfg"
REUSO_MIN = 30                      # reaproveita o mesmo link por 30 min (evita criar dezenas de cobranças por clique repetido)
VALIDADE_H = 48                     # o link de pagamento vale 48 h
PEND_DIAS = 7                       # só procura pagamento de cobranças criadas nos últimos 7 dias
_lock = threading.Lock()


# ------------------------------------------------------------------ configuração
def _segredos() -> dict:
    try:
        import banco
        return banco.secrets_secao("mercadopago") or {}
    except Exception:
        return {}


def _token() -> str:
    t = str(_segredos().get("access_token") or "").strip().strip("\"'")
    return t if len(t) >= 20 else ""


def _app_url() -> str:
    u = str(_segredos().get("app_url") or "").strip().strip("\"'").rstrip("/")
    return u if re.match(r"^https://[\w.\-:]+(/[\w.\-/]*)?$", u) else ""


def ligado() -> bool:
    """Há chave do Mercado Pago configurada? Sem ela, a tela não mostra botões de compra."""
    return bool(_token())


def modo_teste() -> bool:
    return _token().startswith("TEST-")


def config() -> dict:
    cfg = {"desconto_anual_pct": 15.0}
    try:
        import banco
        lido = banco.cfg_ler(CH_CFG) or {}
        d = float(str(lido.get("desconto_anual_pct", cfg["desconto_anual_pct"])).replace(",", "."))
        cfg["desconto_anual_pct"] = max(0.0, min(50.0, d)) if d == d else 15.0
    except Exception:
        pass
    return cfg


def salvar(cfg: dict) -> dict:
    import banco
    try:
        d = float(str(cfg.get("desconto_anual_pct", 15)).replace(",", "."))
    except (TypeError, ValueError):
        d = 15.0
    limpo = {"desconto_anual_pct": round(max(0.0, min(50.0, d if d == d else 15.0)), 1)}
    banco.cfg_gravar(CH_CFG, limpo)
    return limpo


def valor(plano: str, periodo: str, precos: dict | None = None, desconto_anual: float | None = None) -> float:
    """Preço do plano no período, em reais. 0 = não está à venda (preço não definido)."""
    if plano not in PAGOS or periodo not in PERIODOS:
        return 0.0
    if precos is None:
        import precificacao
        precos = precificacao.config().get("preco") or {}
    mensal = float(precos.get(plano) or 0)
    if mensal <= 0:
        return 0.0
    if periodo == "mensal":
        return round(mensal, 2)
    if desconto_anual is None:
        desconto_anual = config()["desconto_anual_pct"]
    return round(mensal * 12 * (1 - desconto_anual / 100), 2)


def brl(v: float) -> str:
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# ------------------------------------------------------------------ registros
def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _agora()).strftime("%Y-%m-%dT%H:%M:%SZ")


def _ler(ref: str) -> dict:
    import banco
    return banco.cfg_ler("pagto|" + ref) or {}


def _gravar(ref: str, doc: dict) -> None:
    import banco
    banco.cfg_gravar("pagto|" + ref, doc)


def _refs_do_usuario(email: str) -> list[str]:
    import banco
    return list((banco.cfg_ler("pagto_u|" + planos._h(email)) or {}).get("refs") or [])


def _lembrar_ref(email: str, ref: str) -> None:
    import banco
    refs = [r for r in _refs_do_usuario(email) if r != ref] + [ref]
    banco.cfg_gravar("pagto_u|" + planos._h(email), {"refs": refs[-8:]})


def _idade_min(iso: str) -> float:
    try:
        return (_agora() - datetime.strptime(iso, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)).total_seconds() / 60
    except (TypeError, ValueError):
        return 1e9


def pendentes(email: str) -> list[dict]:
    """Cobranças recentes da pessoa que ainda não viraram plano (status 'pendente')."""
    out = []
    for ref in reversed(_refs_do_usuario(email)):
        d = _ler(ref)
        if d.get("status") == "pendente" and d.get("email") == email and _idade_min(d.get("criado", "")) < PEND_DIAS * 1440:
            out.append(d)
    return out


# ------------------------------------------------------------------ chamadas ao Mercado Pago
class ErroPagamento(Exception):
    """Mensagem já pronta para mostrar à pessoa. `status` = código HTTP do Mercado Pago, quando houve."""

    def __init__(self, msg: str = "", status: int = 0):
        super().__init__(msg)
        self.status = status


def _chamar(metodo: str, caminho: str, corpo: dict | None = None, params: dict | None = None) -> dict:
    tk = _token()
    if not tk:
        raise ErroPagamento("O pagamento online ainda não está ativado neste app.")
    import requests
    try:
        r = requests.request(metodo, API + caminho, json=corpo, params=params, timeout=15,
                             headers={"Authorization": f"Bearer {tk}", "Content-Type": "application/json",
                                      "X-Idempotency-Key": str(uuid.uuid4())})
    except requests.RequestException:
        raise ErroPagamento("Não consegui falar com o Mercado Pago agora. Tente de novo em instantes.")
    if r.status_code in (401, 403):
        _registrar(f"{r.status_code} {caminho.split('/')[-2] if caminho.endswith('/search') else caminho.split('/')[-1]}: {_resumo(r)}")
        raise ErroPagamento("O pagamento está indisponível no momento. Avise o suporte.", r.status_code)
    if r.status_code >= 400:
        _registrar(f"{r.status_code} {caminho.split('/')[-2] if caminho.endswith('/search') else caminho.split('/')[-1]}: {_resumo(r)}")
        raise ErroPagamento("O Mercado Pago recusou o pedido. Tente de novo ou fale com o suporte.", r.status_code)
    try:
        return r.json()
    except ValueError:
        raise ErroPagamento("Resposta inesperada do Mercado Pago. Tente de novo.")


def _resumo(r) -> str:
    """Motivo curto de uma recusa do Mercado Pago (só mensagem, código e quem bloqueou; nunca o token)."""
    try:
        j = r.json()
        partes = [str(j.get(k)) for k in ("message", "error", "code", "blocked_by", "description") if j.get(k)]
        causa = j.get("cause")
        if isinstance(causa, list) and causa and isinstance(causa[0], dict):
            partes.append(str(causa[0].get("description") or causa[0].get("code") or ""))
        txt = " | ".join(dict.fromkeys(p for p in partes if p))
    except Exception:
        txt = str(getattr(r, "text", ""))
    return txt[:230] or "sem detalhe"


def _registrar(msg: str) -> None:
    try:
        import banco
        banco.registrar_erro("pagamentos", msg)
    except Exception:
        pass


def criar_cobranca(email: str, plano: str, periodo: str) -> dict:
    """Cria (ou reaproveita) a cobrança e devolve o registro, com `link` para a página de pagamento. Levanta ErroPagamento."""
    if plano not in PAGOS or periodo not in PERIODOS:
        raise ErroPagamento("Plano ou período inválido.")
    v = valor(plano, periodo)
    if v <= 0:
        raise ErroPagamento("Este plano ainda não está à venda.")
    for d in pendentes(email):                                    # mesmo pedido há pouco tempo: reaproveita o link
        if d.get("plano") == plano and d.get("periodo") == periodo and abs(float(d.get("valor", 0)) - v) < 0.005 \
                and d.get("link") and _idade_min(d.get("criado", "")) < REUSO_MIN:
            return d
    ref = "bb" + uuid.uuid4().hex[:20]
    p = PERIODOS[periodo]
    nome = f"{planos.ROTULO.get(plano, plano)} · {p['rotulo']}"
    corpo = {
        "items": [{"id": f"{plano}-{periodo}", "title": f"Bússola B3 · {nome}", "description": "Assinatura pré-paga, sem renovação automática",
                   "quantity": 1, "currency_id": "BRL", "unit_price": v}],
        "external_reference": ref,
        "statement_descriptor": "BUSSOLA B3",
        "payer": {"email": email},
        "payment_methods": {"excluded_payment_types": [{"id": "ticket"}], "installments": 12 if periodo == "anual" else 3},
        "expires": True,
        "expiration_date_to": (_agora() + timedelta(hours=VALIDADE_H)).strftime("%Y-%m-%dT%H:%M:%S.000-00:00"),
    }
    url = _app_url()
    if url:
        corpo["back_urls"] = {"success": f"{url}/?pagto={ref}", "pending": f"{url}/?pagto={ref}", "failure": f"{url}/?pagto={ref}"}
        corpo["auto_return"] = "approved"
    r = _chamar("POST", "/checkout/preferences", corpo)
    link = (r.get("sandbox_init_point") if modo_teste() else None) or r.get("init_point") or ""
    if not str(link).startswith("https://"):
        _registrar("preferência sem init_point")
        raise ErroPagamento("O Mercado Pago não devolveu o link de pagamento. Tente de novo.")
    doc = {"ref": ref, "email": email, "plano": plano, "periodo": periodo, "valor": v, "dias": p["dias"],
           "status": "pendente", "criado": _iso(), "link": link, "teste": modo_teste()}
    _gravar(ref, doc)
    _lembrar_ref(email, ref)
    return doc


def _serve(p: dict, esperado: float) -> bool:
    if p.get("status") != "approved" or str(p.get("currency_id") or "BRL") != "BRL":
        return False
    try:
        return float(p.get("transaction_amount") or 0) + 0.005 >= esperado
    except (TypeError, ValueError):
        return False


def _aprovado(ref: str, esperado: float) -> dict | None:
    """Primeiro pagamento aprovado dessa referência com valor suficiente, ou None.
    Consulta primeiro a busca de pagamentos; se a chave não tiver essa permissão (401/403), usa os pedidos do Checkout Pro."""
    try:
        r = _chamar("GET", "/v1/payments/search", params={"external_reference": ref, "sort": "date_created", "criteria": "desc", "limit": 10})
        achados = [p for p in r.get("results") or [] if str(p.get("external_reference")) == ref]
    except ErroPagamento as e:
        if e.status not in (401, 403, 404):
            raise
        r = _chamar("GET", "/merchant_orders/search", params={"external_reference": ref})
        achados = [p for o in r.get("elements") or [] if str(o.get("external_reference")) == ref for p in o.get("payments") or []]
    for p in achados:
        if _serve(p, esperado):
            return p
    return None


def _liberar(d: dict, pid: str) -> dict:
    """Aplica os dias ao plano da conta. Compra do mesmo plano soma ao vencimento; troca de plano começa hoje."""
    email, plano, dias = d["email"], d["plano"], int(d["dias"])
    atual = planos.assinatura_de(email)
    ativo = atual["contratado"] == plano and not atual["vencida"] and atual["ate"]
    if ativo:
        return planos.renovar(email, dias, origem="mercadopago")
    return planos.definir_plano(email, plano, dias, origem="mercadopago")


def verificar(email: str) -> list[dict]:
    """Confere as cobranças pendentes da pessoa. Devolve as que acabaram de ser pagas e liberadas. Não levanta erro de rede."""
    liberadas = []
    for d in pendentes(email):
        try:
            p = _aprovado(d["ref"], float(d["valor"]))
        except ErroPagamento:
            continue
        if not p:
            continue
        with _lock:
            atual = _ler(d["ref"])                                # outro acesso pode ter liberado neste instante
            if atual.get("status") != "pendente":
                continue
            pid = str(p.get("id"))
            import banco
            if banco.cfg_ler("pagto_id|" + pid):
                continue
            banco.cfg_gravar("pagto_id|" + pid, {"ref": d["ref"], "email": email, "em": _iso()})
            try:
                ass = _liberar(atual, pid)
            except Exception as e:                                 # não liberou: desfaz a marca para tentar de novo na próxima
                try:
                    banco.cfg_apagar("pagto_id|" + pid)
                except Exception:
                    pass
                _registrar(f"liberar: {e.__class__.__name__}")
                continue
            atual.update({"status": "pago", "pago_em": _iso(), "pagamento_id": pid, "ate": ass.get("ate")})
            atual.pop("link", None)
            _gravar(d["ref"], atual)
        liberadas.append(atual)
    return liberadas


def verificar_automatico(email: str | None, forcar: bool = False) -> list[dict]:
    """Chamada leve a cada carregamento do app: no máximo uma consulta a cada 90 s por sessão, e só se a pessoa tiver cobrança pendente."""
    if not email or not ligado():
        return []
    try:
        import streamlit as st
        ss = st.session_state
        if not forcar and time.time() - ss.get("_pagto_t", 0) < 90:
            return []
        ss["_pagto_t"] = time.time()
    except Exception:
        pass
    try:
        return verificar(email)
    except Exception as e:
        _registrar(f"verificar: {e.__class__.__name__}")
        return []


def listar(limite: int = 40) -> list[dict]:
    """Últimas cobranças (para o administrador)."""
    import banco
    out = []
    for l in banco._selecionar("config_sistema", {"id": ("comeca", "pagto|")}, ["id", "dados"], limite=500):
        if not str(l["id"]).startswith("pagto|"):
            continue
        d = banco._de_js(l["dados"]) or {}
        if d.get("ref"):
            out.append({k: d.get(k) for k in ("ref", "email", "plano", "periodo", "valor", "status", "criado", "pago_em", "teste")})
    return sorted(out, key=lambda x: x.get("criado") or "", reverse=True)[:limite]
