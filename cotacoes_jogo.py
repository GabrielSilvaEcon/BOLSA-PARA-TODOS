"""Cotações da carteira virtual (Wallet Game): uma fonte gratuita por classe de ativo. Toda a rede passa por funções que dá para trocar nos
testes (`get`, `baixar`, `yahoo`), então a lógica roda sem internet.

 · Ações, FIIs e ETFs da B3 ............ Yahoo Finance (fechamento, proventos e desdobramentos)
 · ETFs dos EUA ........................ Yahoo Finance em dólar × dólar do dia, em reais (Yahoo "BRL=X")
 · Criptomoedas ........................ Binance (par em USDT × USDTBRL), pelo endereço público de dados de mercado
 · Fundos .............................. CVM, informe diário (cota). Sai com atraso de 1 a 2 dias úteis
 · Tesouro Direto ...................... Tesouro Transparente (preço unitário). Só títulos sem cupom: Selic, Prefixado e IPCA+
 · Renda fixa pós-fixada (RF:CDI) ...... Banco Central, série 12 (CDI diário), acumulada em uma cota virtual que começa em R$ 100

Resultado de todo coletor: {"fech": {"AAAA-MM-DD": preço em R$}, "div": {data: provento por cota}, "spl": {data: fator}}.
Ativos fora do calendário da B3 (todos menos ação/FII/ETF da B3) são avaliados no último preço disponível até o pregão (ver `valor_no_dia`).
"""
from __future__ import annotations

import io
import threading
import time
from datetime import date, datetime, timedelta, timezone

import ativos_jogo as A

BINANCE_HOSTS = ("https://data-api.binance.vision", "https://api.binance.com")
URL_CDI = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.12/dados"
CDI_DATA_BASE = date(2024, 1, 2)
CDI_COTA_BASE = 100.0
JANELA_DIAS = 40                  # histórico baixado de cada ativo
IDADE_MAXIMA_DIAS = 12            # preço de ativo fora da B3 mais velho que isso não vale (fundo parado, título vencido)
UA = {"User-Agent": "Mozilla/5.0 (Bolsa para Todos)"}


# ------------------------------------------------------------------ rede
def get_json(url: str, params: dict | None = None, timeout: int = 20):
    import requests
    r = requests.get(url, params=params, headers=UA, timeout=timeout)
    r.raise_for_status()
    return r.json()


def _asof(serie: dict, dia: str, limite_dias: int = IDADE_MAXIMA_DIAS) -> float | None:
    """Último valor da série em `dia` ou antes (até `limite_dias` para trás)."""
    if not serie:
        return None
    if dia in serie:
        return serie[dia]
    ant = [d for d in serie if d <= dia]
    if not ant:
        return None
    d = max(ant)
    try:
        if (date.fromisoformat(dia) - date.fromisoformat(d)).days > limite_dias:
            return None
    except Exception:
        return None
    return serie[d]


def valor_no_dia(ativo: str, serie: dict, dia: str) -> float | None:
    """Preço do ativo no pregão `dia`. B3: o fechamento exato (sem fechamento = feriado do ativo = sem preço). Demais classes: o último
    preço disponível até o dia (cripto fecha todo dia, fundo e Tesouro saem com atraso)."""
    if A.eh_b3(ativo):
        return (serie or {}).get(dia)
    return _asof(serie, dia)


# ------------------------------------------------------------------ Yahoo (B3 e EUA)
def yahoo_historico(simbolo: str, periodo: str = "1mo") -> tuple[dict, dict, dict]:
    """(fechamentos, proventos, desdobramentos) por data ISO, sem ajuste por proventos."""
    import pandas as pd
    import yfinance as yf
    h = yf.Ticker(simbolo).history(period=periodo, interval="1d", auto_adjust=False, actions=True)
    if h is None or h.empty:
        raise RuntimeError("sem dados")
    idx = pd.to_datetime(h.index)
    idx = idx.tz_localize(None) if getattr(idx, "tz", None) is not None else idx
    fech, div, spl = {}, {}, {}
    for d, c in zip(idx, h["Close"]):
        if c == c and c > 0:
            fech[d.date().isoformat()] = float(c)
    if "Dividends" in h:
        for d, x in zip(idx, h["Dividends"]):
            if x == x and x > 0:
                div[d.date().isoformat()] = float(x)
    if "Stock Splits" in h:
        for d, x in zip(idx, h["Stock Splits"]):
            if x == x and x > 0 and abs(x - 1) > 1e-9:
                spl[d.date().isoformat()] = float(x)
    return fech, div, spl


def coletor_yahoo_b3(ativo: str, yahoo=yahoo_historico) -> dict:
    fech, div, spl = yahoo(A.simbolo_yahoo(ativo))
    return {"fech": fech, "div": div, "spl": spl}


def coletor_eua(ativo: str, yahoo=yahoo_historico, fx: dict | None = None) -> dict:
    """ETF americano em reais: preço em dólar × dólar do dia (último disponível)."""
    fech, div, _ = yahoo(A.simbolo_yahoo(ativo))
    fx = fx if fx is not None else dolar_yahoo(yahoo)
    f2, d2 = {}, {}
    for d, c in fech.items():
        t = _asof(fx, d)
        if t:
            f2[d] = round(c * t, 6)
    for d, v in div.items():
        t = _asof(fx, d)
        if t:
            d2[d] = round(v * t, 6)
    return {"fech": f2, "div": d2, "spl": {}}


_cache_fx: dict = {}
_trava = threading.Lock()


def _memo(chave: str, ttl: int, fazer):
    with _trava:
        v = _cache_fx.get(chave)
        if v and time.time() - v[0] < ttl:
            return v[1]
    r = fazer()
    with _trava:
        _cache_fx[chave] = (time.time(), r)
    return r


def dolar_yahoo(yahoo=yahoo_historico) -> dict:
    return _memo("brl=x", 600, lambda: yahoo("BRL=X")[0])


# ------------------------------------------------------------------ Binance (cripto)
def _klines(par: str, get=get_json, limite: int = JANELA_DIAS) -> dict:
    """{data ISO (UTC): fechamento} do par diário à vista."""
    erro = None
    for host in BINANCE_HOSTS:
        try:
            linhas = get(f"{host}/api/v3/klines", {"symbol": par, "interval": "1d", "limit": limite})
            out = {}
            for k in linhas:
                d = datetime.fromtimestamp(int(k[0]) / 1000, tz=timezone.utc).date().isoformat()
                c = float(k[4])
                if c > 0:
                    out[d] = c
            if out:
                return out
        except Exception as e:                          # tenta o próximo endereço
            erro = e
    raise RuntimeError(f"Binance sem resposta para {par}: {erro.__class__.__name__ if erro else 'vazio'}")


def dolar_binance(get=get_json) -> dict:
    return _memo("usdtbrl", 600, lambda: _klines("USDTBRL", get))


def coletor_cripto(ativo: str, get=get_json, fx: dict | None = None) -> dict:
    simbolo = ativo.split(":", 1)[1]
    usd = _klines(simbolo + "USDT", get)
    fx = fx if fx is not None else dolar_binance(get)
    fech = {}
    for d, c in usd.items():
        t = _asof(fx, d, 5)
        if t:
            fech[d] = round(c * t, 6)
    return {"fech": fech, "div": {}, "spl": {}}


# ------------------------------------------------------------------ Banco Central (CDI)
def serie_cdi(get=get_json, ate: date | None = None) -> dict:
    """Cota virtual da renda fixa 100% do CDI: R$ 100,00 em 02/01/2024, acumulando o CDI diário (série 12 do BC)."""
    ate = ate or date.today()
    linhas = get(URL_CDI, {"formato": "json", "dataInicial": CDI_DATA_BASE.strftime("%d/%m/%Y"), "dataFinal": ate.strftime("%d/%m/%Y")})
    cota, out = CDI_COTA_BASE, {}
    for r in sorted(linhas, key=lambda x: datetime.strptime(x["data"], "%d/%m/%Y")):
        v = float(str(r["valor"]).replace(",", "."))
        cota *= 1 + v / 100.0
        out[datetime.strptime(r["data"], "%d/%m/%Y").date().isoformat()] = round(cota, 6)
    if not out:
        raise RuntimeError("série do CDI vazia")
    return out


def coletor_cdi(get=get_json, hoje: date | None = None) -> dict:
    s = _memo("cdi", 3600, lambda: serie_cdi(get, hoje))
    corte = (hoje or date.today()) - timedelta(days=JANELA_DIAS)
    return {"fech": {d: v for d, v in s.items() if d >= corte.isoformat()}, "div": {}, "spl": {}}


# ------------------------------------------------------------------ Tesouro Direto
def ler_tesouro(baixar=None):
    """Tabela padronizada do Tesouro Transparente (colunas titulo, venc, data, pu). Vazia se o arquivo não vier."""
    import pandas as pd
    import fundos as fd
    baixar = baixar or fd.baixar
    conteudo = baixar(fd.URL_TESOURO, 90)
    if conteudo is None:
        return pd.DataFrame()
    return fd.padronizar_tesouro(pd.read_csv(io.BytesIO(conteudo), sep=";", encoding="latin1", dtype=str))


def ids_tesouro(tab, hoje: date | None = None) -> list[str]:
    """Títulos sem cupom ainda não vencidos e com preço recente."""
    hoje = hoje or date.today()
    if tab is None or tab.empty:
        return []
    import pandas as pd
    recentes = tab[tab["data"] >= pd.Timestamp(hoje - timedelta(days=IDADE_MAXIMA_DIAS))]
    out = set()
    for t, v in zip(recentes["titulo"], recentes["venc"]):
        if v.date() > hoje:
            i = A.id_td(t, v)
            if i:
                out.add(i)
    return sorted(out)


def coletor_tesouro(ativo: str, tab) -> dict:
    import pandas as pd
    nome, venc = A.partes_td(ativo)
    s = tab[(tab["titulo"].str.strip().str.lower() == nome.lower()) & (tab["venc"] == pd.Timestamp(venc))]
    s = s.sort_values("data").drop_duplicates("data", keep="last")
    s = s[s["data"] >= pd.Timestamp(date.today() - timedelta(days=JANELA_DIAS * 2))]
    fech = {d.date().isoformat(): float(p) for d, p in zip(s["data"], s["pu"])}
    if not fech:
        raise RuntimeError("título sem preço")
    return {"fech": fech, "div": {}, "spl": {}}


# ------------------------------------------------------------------ fundos (CVM)
def _ler_zip_fundos(conteudo: bytes, cnpjs: set):
    import pandas as pd
    import zipfile
    import fundos as fd
    partes = []
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        for nome in z.namelist():
            if not nome.lower().endswith(".csv"):
                continue
            with z.open(nome) as f:
                cab = pd.read_csv(f, sep=";", encoding="latin1", dtype=str, nrows=0)
            usar = [c for c in cab.columns if c in fd.colunas_desejadas()]
            with z.open(nome) as f:
                for pedaco in pd.read_csv(f, sep=";", encoding="latin1", dtype=str, usecols=usar, chunksize=250_000):
                    col = fd._achar(pedaco.columns, *fd.CAMPOS_INFORME["cnpj"])
                    if col is None:
                        raise fd.LayoutInesperado("coluna de CNPJ ausente")
                    partes.append(pedaco[pedaco[col].map(fd.so_digitos).isin(cnpjs)])
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def ler_fundos(cnpjs, hoje: date | None = None, baixar=None) -> dict:
    """{cnpj (14 dígitos): {data ISO: cota}} do mês corrente e do anterior, numa única leitura dos arquivos da CVM."""
    import fundos as fd
    baixar = baixar or fd.baixar
    hoje = hoje or date.today()
    alvo = {fd.so_digitos(c) for c in cnpjs}
    out: dict = {c: {} for c in alvo}
    if not alvo:
        return out
    for ym in fd.meses_necessarios(hoje, 2):
        conteudo = baixar(fd.URL_INF_DIARIO.format(ym=ym))
        if conteudo is None:
            continue
        bruto = _ler_zip_fundos(conteudo, alvo)
        for c in alvo:
            try:
                p = fd.padronizar_informe(bruto, c)
            except fd.LayoutInesperado:
                raise
            for d, cota in zip(p.index, p["cota"]):
                out[c][d.date().isoformat()] = float(cota)
    return out


def coletor_fundo(ativo: str, tabela: dict) -> dict:
    s = (tabela or {}).get(ativo.split(":", 1)[1]) or {}
    if not s:
        raise RuntimeError("fundo sem cota recente")
    return {"fech": dict(s), "div": {}, "spl": {}}


# ------------------------------------------------------------------ coletor universal (usado pelo fechamento diário)
class Coletor:
    """Chame `preparar(ativos)` uma vez (baixa os arquivos do Tesouro e dos fundos) e depois use a instância como `coletor(ativo)`.
    Cada classe usa a sua fonte; falha de uma fonte só derruba os ativos dela."""

    def __init__(self, hoje: date | None = None, get=get_json, baixar=None, yahoo=yahoo_historico):
        self.hoje, self.get, self.baixar, self.yahoo = hoje or date.today(), get, baixar, yahoo
        self.tesouro = None
        self.fundos: dict = {}
        self.avisos: list[str] = []

    def preparar(self, ativos) -> list[str]:
        """Baixa Tesouro e fundos. Devolve os ids dos títulos do Tesouro disponíveis (para entrarem no universo)."""
        ids = []
        try:
            self.tesouro = ler_tesouro(self.baixar)
            ids = ids_tesouro(self.tesouro, self.hoje)
        except Exception as e:
            self.avisos.append(f"Tesouro: {e.__class__.__name__}")
        cnpjs = [a.split(":", 1)[1] for a in ativos if A.classe(a) == "fundo"]
        if cnpjs:
            try:
                self.fundos = ler_fundos(cnpjs, self.hoje, self.baixar)
            except Exception as e:
                self.avisos.append(f"Fundos: {e.__class__.__name__}")
        return ids

    def __call__(self, ativo: str) -> dict:
        if A.eh_b3(ativo):
            return coletor_yahoo_b3(ativo, self.yahoo)
        c = A.classe(ativo)
        if ativo.startswith("US:"):
            return coletor_eua(ativo, self.yahoo)
        if c == "cripto":
            return coletor_cripto(ativo, self.get)
        if ativo == A.RF_CDI:
            return coletor_cdi(self.get, self.hoje)
        if c == "fundo":
            return coletor_fundo(ativo, self.fundos)
        if ativo.startswith("TD:"):
            if self.tesouro is None or self.tesouro.empty:
                raise RuntimeError("Tesouro indisponível")
            return coletor_tesouro(ativo, self.tesouro)
        raise RuntimeError("ativo desconhecido")


# ------------------------------------------------------------------ cotação do momento (tela de ordens)
def preco_agora(ativo: str, get=get_json, yahoo_rapido=None) -> float | None:
    """Cotação atual em reais, só para os ativos que têm preço durante o dia (B3, EUA e cripto). Os demais devolvem None
    (a tela usa o último preço publicado: cota do fundo, preço unitário do Tesouro, cota do CDI)."""
    try:
        if A.classe(ativo) == "cripto":
            simbolo = ativo.split(":", 1)[1]
            usd = float(get(f"{BINANCE_HOSTS[0]}/api/v3/ticker/price", {"symbol": simbolo + "USDT"})["price"])
            brl = float(get(f"{BINANCE_HOSTS[0]}/api/v3/ticker/price", {"symbol": "USDTBRL"})["price"])
            return usd * brl if usd > 0 and brl > 0 else None
        sim = A.simbolo_yahoo(ativo)
        if not sim:
            return None
        rapido = yahoo_rapido or _yahoo_rapido
        px = rapido(sim)
        if not px:
            return None
        if ativo.startswith("US:"):
            fx = rapido("BRL=X")
            return px * fx if fx else None
        return px
    except Exception:
        return None


def _yahoo_rapido(simbolo: str) -> float | None:
    import yfinance as yf
    t = yf.Ticker(simbolo)
    try:
        px = float(t.fast_info["last_price"])
        if px > 0:
            return px
    except Exception:
        pass
    col = t.history(period="5d", interval="1d", auto_adjust=False)["Close"].dropna()
    return float(col.iloc[-1]) if len(col) and float(col.iloc[-1]) > 0 else None
