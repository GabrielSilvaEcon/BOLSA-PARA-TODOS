"""
Fonte reserva de dados (fallback) para ações AMERICANAS: Financial Modeling Prep (FMP), plano gratuito.

Por que só ações dos EUA: o plano gratuito do FMP cobre apenas bolsas americanas. Para a B3 o app já tem
três fontes (Yahoo, Fundamentus e Brapi) com troca automática, então este módulo não é usado nelas.

Quando é usada (a ligação fica em dados.py, funções buscar_yahoo e buscar_caixa_yahoo):
  1. Yahoo Finance falhou e não trouxe preço -> os dados vêm do FMP (e o app avisa isso ao usuário);
  2. Yahoo trouxe o preço mas sem LPA e VPA (resumo bloqueado) -> o FMP completa só o que faltou;
  3. Yahoo sem fluxo de caixa -> fluxo de caixa anual do FMP (usado no DCF).
  Se as duas fontes falharem, o app mostra uma mensagem amigável (nunca números inventados).

Regras de dados:
  - O dado que o FMP não entrega fica None (indisponível). Nunca vira zero e nunca é estimado.
  - O dicionário devolvido segue o mesmo formato do restante do app (dados.dict_base), mais campos de apoio:
      fonte, data_referencia, valor_mercado_usd, indisponiveis, erros_consulta, erro_tipo.
  - Diferença entre os estados de um dado: disponível (valor), indisponível (None + aviso), desatualizado
    (aviso com a data de referência) e erro de consulta (aviso com o motivo, sem dados sensíveis).

Chave da API: somente em st.secrets["FMP_API_KEY"] (ou variável de ambiente FMP_API_KEY). Nunca no código.
A chave nunca aparece em mensagens de erro nem em logs: os erros são traduzidos para textos fixos.

Cache (st.cache_data), respeitando os 250 pedidos/dia do plano gratuito:
  cotação 15 min | indicadores, razões e resultado 6 h | dividendos 12 h | fluxo de caixa 24 h.
Por ativo americano são até 5 pedidos (cotação, resultado, razões, indicadores, dividendos) + 1 do fluxo de caixa.
"""

from __future__ import annotations

import math
import os
import time
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests
import streamlit as st

NOME_FONTE = "Financial Modeling Prep"
BASE_URL = "https://financialmodelingprep.com/stable"
TIMEOUT_S = 12
PAUSA_TICKER_S = 45          # depois de uma falha, não repete o pedido do mesmo ativo por alguns segundos
PAUSA_LIMITE_S = 600         # depois do limite de pedidos, não insiste por 10 minutos
COTACAO_VELHA_DIAS = 7       # cotação mais antiga que isso é avisada como desatualizada
BALANCO_VELHO_DIAS = 550     # demonstrativo anual mais antigo que ~18 meses é avisado
BOLSAS_EUA = {"NASDAQ", "NYSE", "AMEX", "NYSEARCA", "NYSE ARCA", "BATS", "CBOE"}

MSG_INDISPONIVEL = ("Dados temporariamente indisponíveis: o Yahoo Finance e a fonte reserva não responderam. "
                    "Tente novamente em alguns minutos.")
MSG_SEM_RESERVA = ("Dados temporariamente indisponíveis: o Yahoo Finance não respondeu e a fonte reserva "
                   "não está configurada.")
MSG_LIMITE = ("Dados temporariamente indisponíveis: o Yahoo Finance não respondeu e o limite diário de consultas "
              "da fonte reserva foi atingido. Tente novamente mais tarde.")
MSG_NAO_ENCONTRADO = ("Não foi possível obter dados deste ativo. Confira o código; se estiver correto, as fontes "
                      "estão temporariamente indisponíveis.")

_MENSAGENS = {
    "sem_chave": "chave da fonte reserva (FMP_API_KEY) não configurada",
    "chave_invalida": "chave da fonte reserva recusada",
    "limite": "limite de consultas da fonte reserva atingido",
    "plano": "dado não disponível no plano gratuito da fonte reserva",
    "nao_encontrado": "ativo não encontrado na fonte reserva",
    "timeout": "tempo esgotado ao consultar a fonte reserva",
    "conexao": "falha de conexão com a fonte reserva",
    "indisponivel": "fonte reserva fora do ar",
    "http": "resposta inesperada da fonte reserva",
    "resposta_invalida": "resposta inválida da fonte reserva",
}
_FATAIS = {"sem_chave", "chave_invalida", "limite"}   # com esses erros, não adianta tentar os demais pedidos


class FMPErro(Exception):
    """Erro de consulta ao FMP. O texto é sempre fixo (nunca contém URL, chave ou resposta bruta)."""

    def __init__(self, tipo: str):
        self.tipo = tipo
        self.msg = _MENSAGENS.get(tipo, _MENSAGENS["http"])
        super().__init__(self.msg)


# ---------------------------------------------------------------- utilidades
def _agora() -> datetime:
    return datetime.now(timezone.utc)


def _chave() -> str:
    """Lê a chave de st.secrets (ou da variável de ambiente). Devolve '' se não houver."""
    try:
        v = st.secrets.get("FMP_API_KEY")
    except Exception:
        v = None
    return str(v or os.environ.get("FMP_API_KEY") or "").strip()


def _num(x):
    """Número finito ou None. Texto, bool, NaN e infinito viram None (indisponível, nunca zero)."""
    if x is None or isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _data_br(iso: str | None) -> str:
    try:
        return pd.to_datetime(iso).strftime("%d/%m/%Y")
    except Exception:
        return "data desconhecida"


def _idade(iso) -> timedelta | None:
    """Tempo decorrido desde uma data ISO (None se a data for inválida)."""
    t = pd.to_datetime(iso, errors="coerce")
    if pd.isna(t):
        return None
    t = t.tz_localize(timezone.utc) if t.tzinfo is None else t.tz_convert(timezone.utc)
    return _agora() - t.to_pydatetime()


_LIMITE_ATE = 0.0            # instante (time.time) até o qual não se consulta, depois de atingir o limite
_FALHAS_TICKER: dict = {}    # símbolo -> (instante, tipo do erro)


def _resetar_estado():
    """Zera as pausas (usado nos testes)."""
    global _LIMITE_ATE
    _LIMITE_ATE = 0.0
    _FALHAS_TICKER.clear()


def _marcar_limite():
    global _LIMITE_ATE
    _LIMITE_ATE = time.time() + PAUSA_LIMITE_S


def _erro_por_status(status: int) -> str:
    if status == 429:
        return "limite"
    if status in (401, 403):
        return "chave_invalida"
    if status == 402:
        return "plano"
    if status == 404:
        return "nao_encontrado"
    if status >= 500:
        return "indisponivel"
    return "http"


def _erro_por_texto(msg: str) -> str:
    t = msg.lower()
    if "limit" in t:
        return "limite"
    if "restricted" in t or "premium" in t or "subscription" in t or "upgrade" in t:
        return "plano"
    if "api key" in t or "apikey" in t or "invalid key" in t:
        return "chave_invalida"
    if "not found" in t or "no data" in t:
        return "nao_encontrado"
    return "resposta_invalida"


def _get_json(endpoint: str, params: dict):
    """Pedido HTTP ao FMP. Levanta FMPErro (texto fixo) em qualquer falha; nunca expõe a chave."""
    chave = _chave()
    if not chave:
        raise FMPErro("sem_chave")
    if time.time() < _LIMITE_ATE:
        raise FMPErro("limite")
    try:
        r = requests.get(f"{BASE_URL}/{endpoint}", params={**params, "apikey": chave}, timeout=TIMEOUT_S)
    except requests.exceptions.Timeout:
        raise FMPErro("timeout") from None
    except requests.exceptions.RequestException:
        raise FMPErro("conexao") from None     # a exceção original traz a URL (com a chave): descartada
    if r.status_code != 200:
        tipo = _erro_por_status(r.status_code)
        if tipo == "limite":
            _marcar_limite()
        raise FMPErro(tipo)
    try:
        dados = r.json()
    except ValueError:
        raise FMPErro("resposta_invalida") from None
    if isinstance(dados, dict):
        msg = dados.get("Error Message") or dados.get("error") or dados.get("message")
        if msg:
            tipo = _erro_por_texto(str(msg))
            if tipo == "limite":
                _marcar_limite()
            raise FMPErro(tipo)
    return dados


def _lista(dados, permitir_vazia: bool = False) -> list:
    """Valida que a resposta é uma lista de objetos. Lista vazia = ativo/dado não encontrado."""
    if isinstance(dados, dict):
        dados = [dados]
    if not isinstance(dados, list) or any(not isinstance(x, dict) for x in dados):
        raise FMPErro("resposta_invalida")
    if not dados and not permitir_vazia:
        raise FMPErro("nao_encontrado")
    return dados


# ---------------------------------------------------------------- consultas com cache
_FUNCOES_COM_CACHE: list = []


def _cache(ttl: int):
    def deco(func):
        try:
            f = st.cache_data(ttl=ttl, show_spinner=False)(func)
        except Exception:
            f = func
        _FUNCOES_COM_CACHE.append(f)
        return f
    return deco


def _limpar_cache():
    for f in _FUNCOES_COM_CACHE:
        try:
            f.clear()
        except Exception:
            pass


# Erros não são guardados em cache (a função levanta exceção): só leituras bem-sucedidas.
@_cache(900)
def _cotacao(sym: str) -> list:
    return _lista(_get_json("quote", {"symbol": sym}))


@_cache(21600)
def _resultado(sym: str) -> list:
    return _lista(_get_json("income-statement", {"symbol": sym}))


@_cache(21600)
def _razoes(sym: str) -> list:
    return _lista(_get_json("ratios-ttm", {"symbol": sym}))


@_cache(21600)
def _indicadores(sym: str) -> list:
    return _lista(_get_json("key-metrics-ttm", {"symbol": sym}))


@_cache(43200)
def _dividendos(sym: str) -> list:
    return _lista(_get_json("dividends", {"symbol": sym}), permitir_vazia=True)


@_cache(86400)
def _fluxo_caixa(sym: str) -> list:
    return _lista(_get_json("cash-flow-statement", {"symbol": sym}))


def _simbolo(tk: str) -> str:
    import dados
    return dados.sym_yf(tk)


def _ordenar_por_data(lista: list) -> list:
    def chave(x):
        t = pd.to_datetime(x.get("date"), errors="coerce")
        return t if pd.notna(t) else pd.Timestamp.min
    return sorted(lista, key=chave, reverse=True)


# ---------------------------------------------------------------- dados do ativo
def buscar_fmp(ticker: str) -> dict:
    """Dados fundamentalistas de uma ação americana, no formato padrão do app. Nunca levanta exceção de rede.

    Sem preço = falha total (campo 'erro' preenchido, 'erro_tipo' com o motivo). Com preço, o que o FMP não
    entregar fica None e é listado em 'indisponiveis'; falhas parciais ficam em 'erros_consulta'."""
    import dados

    tk = dados.normaliza(ticker)
    d = dados.dict_base(tk)
    d.update({"fonte": NOME_FONTE, "erro_tipo": None, "indisponiveis": [], "erros_consulta": {},
              "data_referencia": None, "valor_mercado_usd": None})

    if dados.eh_b3(tk):
        d["erro"] = "A fonte reserva cobre apenas ações americanas (a B3 já tem Yahoo, Fundamentus e Brapi)."
        d["erro_tipo"] = "fora_da_cobertura"
        return d

    sym = _simbolo(tk)
    anterior = _FALHAS_TICKER.get(sym)
    if anterior and time.time() - anterior[0] < PAUSA_TICKER_S:
        d["erro_tipo"] = anterior[1]
        d["erro"] = f"Fonte reserva: {_MENSAGENS.get(anterior[1], _MENSAGENS['http'])}."
        return d

    def falha_total(tipo: str, texto: str | None = None):
        _FALHAS_TICKER[sym] = (time.time(), tipo)
        d["erro_tipo"] = tipo
        d["erro"] = texto or f"Fonte reserva: {_MENSAGENS.get(tipo, _MENSAGENS['http'])}."
        return d

    # 1) cotação (essencial)
    try:
        q = _cotacao(sym)[0]
    except FMPErro as e:
        return falha_total(e.tipo)
    preco = _num(q.get("price"))
    if not preco or preco <= 0:
        return falha_total("nao_encontrado", "Fonte reserva: a cotação veio sem preço.")
    bolsa = str(q.get("exchange") or "").upper()
    if bolsa not in BOLSAS_EUA:
        return falha_total("fora_da_cobertura",
                           "Fonte reserva: ativo fora das bolsas americanas cobertas pelo plano gratuito.")
    d["preco"] = preco
    d["nome"] = q.get("name") or tk
    d["moeda"] = "USD"
    d["valor_mercado_usd"] = _num(q.get("marketCap"))
    alertas = d["alertas"]

    ts = _num(q.get("timestamp"))
    if ts:
        try:
            quando = datetime.fromtimestamp(ts, tz=timezone.utc)
            d["data_referencia"] = quando.strftime("%Y-%m-%d")
            if _agora() - quando > timedelta(days=COTACAO_VELHA_DIAS):
                alertas.append(f"Dado desatualizado: a cotação do {NOME_FONTE} é de {_data_br(d['data_referencia'])}.")
        except (OverflowError, OSError, ValueError):
            ts = None
    if not ts:
        alertas.append(f"O {NOME_FONTE} não informou a data da cotação.")

    # 2) demais consultas (cada falha vira dado indisponível + aviso; limite/chave encerram as tentativas)
    erros, fatal = d["erros_consulta"], [None]

    def consultar(rotulo, funcao):
        if fatal[0]:
            erros[rotulo] = fatal[0]
            return None
        try:
            return funcao(sym)
        except FMPErro as e:
            erros[rotulo] = e.tipo
            if e.tipo in _FATAIS:
                fatal[0] = e.tipo
            return None

    resultado = consultar("resultado anual", _resultado)
    razoes = consultar("razões", _razoes)
    indicadores = consultar("indicadores", _indicadores)
    dividendos = consultar("dividendos", _dividendos)

    moeda_bal = None
    if resultado:
        r0 = _ordenar_por_data(resultado)[0]
        moeda_bal = r0.get("reportedCurrency") or None
        acoes = _num(r0.get("weightedAverageShsOut"))
        if acoes and acoes > 0:
            d["acoes"] = acoes
            alertas.append("Número de ações = média ponderada do último exercício anual "
                           f"({_data_br(r0.get('date'))}), não a contagem de hoje.")
        if r0.get("date"):
            d["data_balanco"] = str(r0["date"])[:10]
            idade = _idade(r0["date"])
            if idade is not None and idade > timedelta(days=BALANCO_VELHO_DIAS):
                alertas.append(f"Dado desatualizado: o demonstrativo anual do {NOME_FONTE} é de "
                               f"{_data_br(r0['date'])}.")
    d["moeda_balanco"] = moeda_bal or "USD"

    ttm_div = None
    if razoes:
        z = razoes[0]
        lpa, vpa = _num(z.get("netIncomePerShareTTM")), _num(z.get("bookValuePerShareTTM"))
        if moeda_bal:
            d["lpa"], d["vpa"] = lpa, vpa
        elif lpa is not None or vpa is not None:
            alertas.append("Moeda do balanço não confirmada pela fonte reserva: LPA e VPA descartados "
                           "para não gerar preço justo incorreto.")
        d["margem_liq"] = _num(z.get("netProfitMarginTTM"))
        ttm_div = _num(z.get("dividendPerShareTTM"))

    if indicadores:
        m = indicadores[0]
        d["ev_ebitda"] = _num(m.get("evToEBITDATTM"))
        d["roe"] = _num(m.get("returnOnEquityTTM"))

    if dividendos:
        linhas = []
        for x in dividendos:
            dt = pd.to_datetime(x.get("date"), errors="coerce")
            v = _num(x.get("adjDividend"))
            if v is None:
                v = _num(x.get("dividend"))
            if pd.notna(dt) and v is not None and v >= 0:
                linhas.append((dt.tz_localize(None) if dt.tzinfo else dt, v))
        if linhas:
            ano, med, d12 = dados._proventos_series(pd.DataFrame(linhas, columns=["data", "rate"]), "data", "rate")
            d["div_ano"], d["div_medio"], d["div_12m"] = ano, med, d12
    if d["div_12m"] is None and ttm_div is not None:
        d["div_12m"] = ttm_div
    if dividendos is not None and not d["div_ano"].size:
        alertas.append(f"O {NOME_FONTE} não retornou proventos (empresa sem dividendos ou dado indisponível).")

    # 3) o que não veio: indisponível (None) e avisado; falhas de consulta com o motivo
    rotulos = {"lpa": "LPA", "vpa": "VPA", "acoes": "nº de ações", "roe": "ROE", "margem_liq": "margem líquida",
               "ev_ebitda": "EV/EBITDA"}
    d["indisponiveis"] = [rot for k, rot in rotulos.items() if d.get(k) is None]
    d["indisponiveis"] += ["dívida/patrimônio", "dívida líquida", "setor"]   # o FMP gratuito não entrega (sem estimar)
    if d["indisponiveis"]:
        alertas.append("Indisponíveis na fonte reserva (ficam sem valor, não zerados): "
                       + ", ".join(d["indisponiveis"]) + ".")
    for rotulo, tipo in sorted(erros.items()):
        alertas.append(f"{NOME_FONTE}, {rotulo}: consulta falhou ({_MENSAGENS.get(tipo, _MENSAGENS['http'])}).")
    return d


# ---------------------------------------------------------------- fluxo de caixa anual (DCF)
def buscar_caixa_fmp(ticker: str) -> pd.DataFrame:
    """Fluxo de caixa anual no mesmo formato do Yahoo (índice = ano, colunas em português). Vazio se indisponível.

    Só aceita demonstrativos em dólar: o app converte o fluxo de caixa de ações americanas pelo dólar de cada ano,
    e misturar outra moeda geraria números errados."""
    import dados

    tk = dados.normaliza(ticker)
    if dados.eh_b3(tk):
        return pd.DataFrame()
    try:
        lista = _fluxo_caixa(_simbolo(tk))
    except FMPErro:
        return pd.DataFrame()
    linhas = [x for x in lista if x.get("period") in (None, "FY")]
    if not linhas or any((x.get("reportedCurrency") or "") != "USD" for x in linhas):
        return pd.DataFrame()
    out = {}
    for x in linhas:
        dt = pd.to_datetime(x.get("date"), errors="coerce")
        if pd.isna(dt) or int(dt.year) in out:
            continue
        out[int(dt.year)] = {
            "Caixa operacional": _num(x.get("netCashProvidedByOperatingActivities")),
            "Caixa de investimento": _num(x.get("netCashProvidedByInvestingActivities")),
            "Fluxo de caixa livre": _num(x.get("freeCashFlow")),
        }
    if not out:
        return pd.DataFrame()
    df = pd.DataFrame.from_dict(out, orient="index").sort_index().astype(float)
    df.index = df.index.astype(int)
    df = df.dropna(how="all")
    if df.empty:
        return pd.DataFrame()
    df.attrs["fonte"] = NOME_FONTE
    return df


# ---------------------------------------------------------------- ligação com o Yahoo (usada por dados.buscar_yahoo)
def recorrer(d: dict, ticker: str, falhou: bool) -> dict:
    """Aplica a reserva a uma ação americana.

    falhou=True : o Yahoo não trouxe preço -> troca pelos dados do FMP (ou devolve erro amigável);
    falhou=False: o Yahoo trouxe preço; se faltarem LPA e VPA, o FMP completa só o que está ausente."""
    import dados

    tk = dados.normaliza(ticker)
    if falhou:
        r = buscar_fmp(tk)
        if r.get("preco"):
            r["alertas"].insert(0, f"Yahoo Finance indisponível agora: dados vindos de {NOME_FONTE} (fonte reserva).")
            return r
        saida = dict(d)
        saida["alertas"] = list(d.get("alertas", []))
        tipo = r.get("erro_tipo")
        saida["erro"] = {"sem_chave": MSG_SEM_RESERVA, "limite": MSG_LIMITE,
                         "nao_encontrado": MSG_NAO_ENCONTRADO}.get(tipo, MSG_INDISPONIVEL)
        saida["alertas"].append(r.get("erro") or MSG_INDISPONIVEL)
        saida["erro_tipo"] = tipo
        return saida

    if not d.get("preco") or d.get("lpa") is not None or d.get("vpa") is not None:
        return d                                       # dados essenciais presentes: nada a fazer
    r = buscar_fmp(tk)
    saida = dict(d)
    saida["alertas"] = list(d.get("alertas", []))
    if not r.get("preco"):
        saida["alertas"].append("LPA e VPA indisponíveis no Yahoo e a fonte reserva também não respondeu "
                                f"({r.get('erro') or 'sem detalhe'}).")
        return saida
    completou = []
    for k in ("lpa", "vpa", "ev_ebitda", "roe", "margem_liq", "acoes", "valor_mercado_usd", "data_balanco"):
        if saida.get(k) is None and r.get(k) is not None:
            saida[k] = r[k]
            completou.append(k)
    if "lpa" in completou or "vpa" in completou:
        saida["moeda_balanco"] = r["moeda_balanco"]
    div = saida.get("div_ano")
    if (div is None or len(div) == 0) and len(r["div_ano"]):
        saida["div_ano"], saida["div_medio"], saida["div_12m"] = r["div_ano"], r["div_medio"], r["div_12m"]
        completou.append("proventos")
    if completou:
        saida["fonte"] = f"Yahoo Finance + {NOME_FONTE}"
        saida["alertas"].append(f"Indicadores (LPA, VPA, ROE...) completados pelo {NOME_FONTE} (fonte reserva), "
                                "porque o Yahoo não os entregou.")
        if "acoes" in completou:
            saida["alertas"] += [a for a in r["alertas"] if a.startswith("Número de ações")]
    return saida
