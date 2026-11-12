"""Carteira única do TickerHunters: a carteira do Wallet Game é a ÚNICA carteira oficial do app.

Esta camada não guarda nada. Ela lê o estado do Wallet Game (caixa, posições, extrato) e:
 - calcula o resumo financeiro (disponível, investido, preço médio, lucro realizado, não realizado);
 - monta a visão "legada" (lotes, fundos, capital, vendas) que Gestão, Risco, Simulador, Relatórios e Comparador já sabiam ler;
 - leva toda compra/venda feita fora do Wallet Game para o mesmo motor de ordens do jogo (sem saldo, posição ou histórico duplicados).

Dados antigos: lotes que a pessoa tinha só na sessão (cart_ficticia/cart_fundos_virtual) vão para uma cópia de segurança
(`cart_ficticia_legado`, `cart_fundos_legado`) antes de a visão do jogo assumir; nada é apagado.
T$ (capital virtual), Ticker Coins e XP continuam separados: nenhuma função daqui mexe em Ticker Coins nem em XP.
"""
from __future__ import annotations

import re
from datetime import date

import ativos_jogo as A

# ---------------------------------------------------------------- tradução legado ↔ jogo
SEM_CONTA = "Entre na sua conta e participe do Wallet Game: a carteira dele é a única carteira do TickerHunters."
FORA_DO_JOGO = ("Esse ativo ainda não está no universo do Wallet Game (ações, FIIs, ETFs e BDRs da B3, ETFs VOO, QQQ, SCHD e VT, "
                "criptomoedas, fundos por CNPJ e renda fixa). Por isso ele não entra na carteira.")


def id_jogo(ticker) -> str | None:
    """Ticker do app (PETR4, VOO, BTC-USD) → identificador do jogo (PETR4, US:VOO, CRIPTO:BTC). None se o jogo não negocia."""
    t = str(ticker or "").upper().strip()
    if not t:
        return None
    if t.startswith("US:"):
        return t if t[3:] in A.ETFS_EUA else None
    if A.valido(t):
        return t
    if t.endswith(".SA") and A.valido(t[:-3]):
        return t[:-3]
    if t.endswith("-USD") and re.fullmatch(r"[A-Z0-9]{2,10}", t[:-4]):
        return A.id_cripto(t[:-4])
    if t.endswith("-BRL") and re.fullmatch(r"[A-Z0-9]{2,10}", t[:-4]):
        return A.id_cripto(t[:-4])
    if t in A.ETFS_EUA:
        return A.id_us(t)
    return None


def ticker_legado(ativo: str) -> str | None:
    """Identificador do jogo → ticker que as telas antigas entendem. None para fundo, Tesouro e CDI (têm lista própria)."""
    a = str(ativo or "")
    if A.eh_b3(a):
        return a
    if a.startswith("US:"):
        return a[3:]
    if a.startswith("CRIPTO:"):
        return a[7:] + "-USD"
    return None


# ---------------------------------------------------------------- resumo financeiro
def _f(x, d=0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def resumo(est: dict | None) -> dict:
    """Números da carteira, cada um com um significado só:
    disponivel    = caixa livre para comprar (T$);
    investido     = custo das posições abertas (quantidade × preço médio, já com custos de negociação);
    valor_atual   = posições ao último preço conhecido;
    nao_realizado = valor_atual − investido (só vira resultado ao vender); rent_nao_realizada = isso sobre o investido;
    realizado     = soma dos resultados das vendas já feitas (vem do extrato);
    patrimonio    = disponível + valor_atual.
    Bônus do jogo (aportes) ficam fora dos resultados: não são lucro de investimento."""
    e = est if isinstance(est, dict) and est.get("v") == 1 else {}
    pos = e.get("pos") or {}
    ult = e.get("ult") or {}
    linhas = []
    investido = valor = 0.0
    for tk, p in pos.items():
        q, pm = _f(p.get("q")), _f(p.get("pm"))
        px = _f(ult.get(tk)) or pm
        custo, val = q * pm, q * px
        investido += custo
        valor += val
        linhas.append({"id": tk, "classe": A.classe(tk), "qtd": q, "pm": pm, "preco": px, "custo": custo, "valor": val,
                       "lucro_nao_realizado": val - custo, "pct": (val / custo - 1) if custo > 0 else 0.0})
    realizado = sum(_f(x.get("r")) for x in (e.get("ext") or []) if x.get("tipo") == "venda")
    proventos = sum(_f(x.get("v")) for x in (e.get("ext") or []) if x.get("tipo") == "provento")
    disp = _f(e.get("caixa"))
    return {"existe": bool(e), "disponivel": disp, "investido": investido, "valor_atual": valor,
            "nao_realizado": valor - investido, "rent_nao_realizada": (valor / investido - 1) if investido > 0 else 0.0,
            "realizado": realizado, "proventos": proventos, "patrimonio": disp + valor, "posicoes": linhas,
            "capital_inicial": _f(e.get("cap0")), "aportes": _f(e.get("apt"))}


# ---------------------------------------------------------------- visão legada (derivada: nunca é fonte)
def _datas_compra(e: dict) -> dict:
    d: dict = {}
    for x in e.get("ext") or []:
        if x.get("tipo") == "compra" and x.get("t") and x["t"] not in d:
            d[x["t"]] = str(x.get("d") or "")[:10]
    return d


def visao_legada(est: dict | None, fx=None, hoje: date | None = None) -> dict:
    """{'lotes','fundos','capital','vendas','sem_dolar'} a partir do estado do jogo. fx: série do dólar (None = não precisa)."""
    import moeda
    e = est if isinstance(est, dict) and est.get("v") == 1 else {}
    hoje = hoje or date.today()
    datas = _datas_compra(e)
    lotes, fundos, sem_dolar = [], [], []
    gasto_rf = 0.0
    for tk, p in (e.get("pos") or {}).items():
        q, pm = _f(p.get("q")), _f(p.get("pm"))
        if q <= 0:
            continue
        leg = ticker_legado(tk)
        if leg:
            dt = (datas.get(tk) or str(e.get("inicio") or hoje.isoformat()))[:10]
            preco = pm
            if moeda.eh_dolar(leg):
                f = moeda.cambio_em(fx, dt) if fx is not None else None
                if not f:
                    sem_dolar.append(leg)
                    continue
                preco = pm / f                      # o legado reconverte por qtd × preço × dólar da mesma data: volta ao custo exato em R$
            lotes.append({"ticker": leg, "qtd": int(q) if float(q).is_integer() else q, "preco_medio": float(preco), "data": dt})
        elif tk.startswith("FUNDO:"):
            try:
                cn = fd_formatar(tk[6:])
            except Exception:
                cn = tk[6:]
            fundos.append({"cnpj": cn, "valor": q * pm})
        else:
            gasto_rf += q * pm                      # Tesouro e CDI: contam no resumo único, não nas telas antigas de ações
    vendas = [{"ticker": ticker_legado(x["t"]) or x["t"], "qtd": _f(x.get("q")), "preco_medio": _f(x.get("p")), "data": str(x.get("d") or "")[:10]}
              for x in (e.get("ext") or []) if x.get("tipo") == "venda" and ticker_legado(x.get("t", ""))]
    gasto_lotes = 0.0
    try:
        gasto_lotes = moeda.custo_total_brl(lotes, fx) or 0.0
    except Exception:
        pass
    # capital = caixa + o que está nos lotes e fundos: a conta antiga (capital − gasto − fundos) devolve exatamente o caixa do jogo
    capital = _f(e.get("caixa")) + gasto_lotes + sum(f["valor"] for f in fundos)
    return {"lotes": lotes, "fundos": fundos, "capital": capital, "vendas": vendas, "sem_dolar": sem_dolar, "renda_fixa": gasto_rf}


def fd_formatar(cnpj: str) -> str:
    import fundos as fd
    return fd.formatar_cnpj(cnpj)


# ---------------------------------------------------------------- sessão do Streamlit
def _ss():
    import streamlit as st
    return st.session_state


def _estado_do_jogo(a, forcar: bool = False) -> dict | None:
    """Carteira do jogo da pessoa logada (None se ela ainda não entrou no jogo). Usa o mesmo cache da página do jogo."""
    try:
        import competicao_app as CA
        c = CA._pessoa(a, forcar)
        if not (c.get("perfil") or {}).get("aceite"):
            return None
        cart = c.get("cart") or {}
        return cart if cart.get("v") == 1 else None
    except Exception:
        return None


def sincronizar_sessao(forcar: bool = False) -> bool:
    """Preenche as chaves de sessão que as telas antigas leem (cart_ficticia, cart_fundos_virtual, cart_capital, cart_vendas_ficticia)
    com o que está na carteira do jogo. Chamada a cada execução do app; só refaz quando o estado mudou. Devolve True se a visão é a do jogo."""
    try:
        import usuarios
        a = usuarios.ator()
    except Exception:
        a = None
    ss = _ss()
    if not a:
        ss["cu_ativa"] = False
        return False
    est = _estado_do_jogo(a, forcar)
    if est is None:
        ss["cu_ativa"] = False
        return False
    # cópia de segurança do que existia só na sessão (uma vez): nada se perde
    if not ss.get("cu_ativa") and not ss.get("cu_copiado"):
        if ss.get("cart_ficticia"):
            ss["cart_ficticia_legado"] = list(ss["cart_ficticia"])
        if ss.get("cart_fundos_virtual"):
            ss["cart_fundos_legado"] = list(ss["cart_fundos_virtual"])
        if ss.get("cart_fundos_cvm"):
            ss["cart_fundos_cvm_legado"] = list(ss["cart_fundos_cvm"])
        ss["cu_copiado"] = True
    assinatura = (len(est.get("ext") or []), round(_f(est.get("caixa")), 2), tuple(sorted((k, _f(v.get("q"))) for k, v in (est.get("pos") or {}).items())))
    if not forcar and ss.get("cu_ativa") and ss.get("cu_sig") == assinatura:
        return True
    fx = None
    if any(ticker_legado(k) and not A.eh_b3(k) for k in (est.get("pos") or {})):
        import moeda
        fx = moeda.cambio_serie()
    v = visao_legada(est, fx)
    ss["cart_ficticia"] = v["lotes"]
    ss["cart_fundos_virtual"] = v["fundos"]
    ss["cart_vendas_ficticia"] = v["vendas"]
    ss["cart_capital"] = max(v["capital"], 0.0)
    ss["cart_fundos_cvm"] = []                      # lista paralela antiga: o fundo agora mora só na carteira do jogo (cópia em cart_fundos_cvm_legado)
    ss["cu_sem_dolar"] = v["sem_dolar"]
    ss["cu_sig"] = assinatura
    ss["cu_ativa"] = True
    return True


def ss_get(chave: str, padrao=None):
    return _ss().get(chave, padrao)


def ativa() -> bool:
    return bool(_ss().get("cu_ativa"))


# ---------------------------------------------------------------- ordens (sempre pelo motor do jogo)
def _ordem(lado: str, ativo: str, qtd, ref_brl: float | None) -> tuple[bool, str]:
    try:
        import usuarios
        a = usuarios.ator()
    except Exception:
        a = None
    if not a:
        return False, SEM_CONTA
    try:
        import competicao_app as CA
        c = CA._pessoa(a, True)
    except Exception:
        return False, "Não consegui abrir a carteira do Wallet Game agora. Tente de novo em instantes."
    perfil = c["perfil"]
    if not perfil.get("aceite"):
        return False, "Participe do Wallet Game primeiro: a carteira dele é a única carteira do TickerHunters."
    q = A.norm_qtd(ativo, qtd)
    if not A.qtd_valida(ativo, q):
        return False, f"Quantidade inválida para {A.rotulo(ativo)}. Esse tipo de ativo aceita múltiplos de {A.texto_qtd(ativo, A.passo(ativo))}."
    r = CA._executar_ordem(a, perfil, {"lado": lado, "tk": ativo, "qtd": q, "ref": ref_brl or 0.0})
    if not r.get("ok"):
        return False, r.get("msg") or "Ordem não executada."
    sincronizar_sessao(True)
    verbo = "Compra" if lado == "Comprar" else "Venda"
    return True, f"{verbo} executada: {A.texto_qtd(ativo, q)} × {A.rotulo(ativo)} a R$ {r['px']:,.2f} ({r['fonte']}).".replace(",", "X").replace(".", ",").replace("X", ".")


def _preco_ref_brl(ticker: str, preco, dt) -> float | None:
    """Preço informado na tela (US$ para ativo do exterior) em reais, só como referência quando não há cotação ao vivo."""
    try:
        p = float(preco)
    except (TypeError, ValueError):
        return None
    if p <= 0:
        return None
    import moeda
    if moeda.eh_dolar(ticker):
        f = moeda.cambio_em(moeda.cambio_serie(), dt)
        return p * f if f else None
    return p


def comprar(ticker: str, qtd, preco=None, dt=None) -> str | None:
    """Compra pelo motor do jogo ao preço de agora. Devolve mensagem de erro, ou None se deu certo (compatível com _adicionar_carteira)."""
    ativo = id_jogo(ticker)
    if not ativo:
        return FORA_DO_JOGO
    ok, msg = _ordem("Comprar", ativo, qtd, _preco_ref_brl(ticker, preco, dt))
    if ok:
        _ss()["cu_aviso"] = msg
        return None
    return msg


def vender(ticker: str, qtd) -> str | None:
    ativo = id_jogo(ticker)
    if not ativo:
        return FORA_DO_JOGO
    ok, msg = _ordem("Vender", ativo, qtd, None)
    if ok:
        _ss()["cu_aviso"] = msg
        return None
    return msg


# ---------------------------------------------------------------- simulação de compra (regra pura + leitura do caixa)
def simulacao_compra(ativo: str, qtd, ref_brl: float, caixa: float | None) -> dict:
    """Quanto custa comprar `qtd` do ativo ao preço `ref_brl` (com a taxa de negociação da classe) e como fica o caixa.
    Devolve: qtd (já no passo do ativo), taxa, custo, caixa, depois, max_qtd (o que o caixa paga) e ok (cabe no caixa e a quantidade é válida)."""
    taxa = A.custo(ativo)
    q = A.norm_qtd(ativo, qtd) if qtd else 0
    unit = float(ref_brl) * (1 + taxa)
    custo = q * unit
    maxq = A.piso_qtd(ativo, caixa / unit) if (caixa is not None and unit > 0) else 0
    depois = (caixa - custo) if caixa is not None else None
    ok = bool(q) and A.qtd_valida(ativo, q) and caixa is not None and custo <= caixa + 1e-9
    return {"qtd": q, "taxa": taxa, "custo": custo, "caixa": caixa, "depois": depois, "max_qtd": maxq, "ok": ok}


def caixa_disponivel() -> float | None:
    """Caixa livre da carteira do Wallet Game da pessoa logada (None se ela não entrou no jogo)."""
    try:
        import usuarios
        a = usuarios.ator()
    except Exception:
        a = None
    est = _estado_do_jogo(a) if a else None
    return _f(est.get("caixa")) if est else None


def simular_compra(ticker: str, qtd, preco=None, dt=None) -> dict | None:
    """Simulação para a tela: None se o ativo está fora do jogo ou sem cotação."""
    ativo = id_jogo(ticker)
    ref = _preco_ref_brl(ticker, preco, dt) if ativo else None
    if not ativo or not ref:
        return None
    return {**simulacao_compra(ativo, qtd, ref, caixa_disponivel()), "ref": ref, "ativo": ativo}


def comprar_fundo(cnpj: str, valor: float) -> str | None:
    """Fundo por CNPJ: converte o valor aplicado em cotas pela última cota da CVM e compra pelo motor do jogo."""
    import fundos as fd
    dig = fd.so_digitos(cnpj)
    if len(dig) != 14:
        return "CNPJ inválido."
    try:
        import competicao_app as CA
        cota = CA._cota_fundo(dig)
    except Exception:
        cota = None
    if not cota or not cota.get("c"):
        return "Não encontrei cota recente desse fundo na CVM. Confira o CNPJ ou tente outro fundo."
    ativo = A.id_fundo(dig)
    q = A.norm_qtd(ativo, float(valor) / float(cota["c"]))
    ok, msg = _ordem("Comprar", ativo, q, float(cota["c"]))
    if ok:
        _ss()["cu_aviso"] = msg
        return None
    return msg


def aviso() -> str | None:
    """Mensagem da última operação (uma vez só)."""
    return _ss().pop("cu_aviso", None)


# ---------------------------------------------------------------- cartão do resumo (HTML puro)
def _brl(v: float) -> str:
    return ("R$ " + f"{v:,.2f}").replace(",", "X").replace(".", ",").replace("X", ".")


def _pct(v: float) -> str:
    return (f"{v * 100:+.2f}%").replace(".", ",")


def html_resumo(r: dict) -> str:
    """Seis números, cada um com seu nome: disponível, investido, valor atual, não realizado, realizado, patrimônio."""
    def cor(v):
        return "#1F9D55" if v > 0.005 else ("#D64545" if v < -0.005 else "#6B7280")
    itens = [("Capital disponível", _brl(r["disponivel"]), "#1F2937", "caixa livre para comprar"),
             ("Capital investido", _brl(r["investido"]), "#1F2937", "custo das posições abertas"),
             ("Valor atual", _brl(r["valor_atual"]), "#1F2937", "posições ao último preço"),
             ("Não realizado", f"{_brl(r['nao_realizado'])} · {_pct(r['rent_nao_realizada'])}", cor(r["nao_realizado"]), "só vira resultado ao vender"),
             ("Lucro realizado", _brl(r["realizado"]), cor(r["realizado"]), "soma das vendas já feitas"),
             ("Patrimônio", _brl(r["patrimonio"]), "#1F2937", "disponível + valor atual")]
    cels = "".join(f"<div style='flex:1 1 46%;min-width:140px;background:#fff;border:1px solid #E5E7EB;border-radius:12px;padding:8px 10px'>"
                   f"<div style='font-size:.72rem;color:#6B7280'>{t}</div><div style='font-weight:800;color:{c};font-size:.95rem'>{v}</div>"
                   f"<div style='font-size:.66rem;color:#9AA3B2'>{s}</div></div>" for t, v, c, s in itens)
    return (f"<div style='display:flex;flex-wrap:wrap;gap:8px;margin:6px 0 10px'>{cels}</div>"
            "<div style='font-size:.7rem;color:#6B7280'>Valores em T$ (capital virtual do jogo, sem dinheiro de verdade). "
            "Ticker Coins e XP ficam à parte e não entram aqui.</div>")
