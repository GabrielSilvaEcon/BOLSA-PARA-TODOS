"""
Passo 20 · COLETA de séries do comparador (a única parte que fala com a internet).

Cada classe tem a sua cadeia de fontes, da mais confiável para a reserva, e TODAS as chamadas passam pelo cache (validade por tipo de dado, ver
comparador_fontes.TTL), pelo limitador de consultas e pela cadeia de fontes autorizadas. Falha nunca fica em cache e nunca vira dado inventado.

  ações, ETFs, FIIs, BDRs : Yahoo Finance (até 5 anos, com proventos)  → Brapi (reserva, só 3 meses e só com chave)
  criptomoedas            : Yahoo SÍMBOLO-USD (histórico longo, validado contra a CoinGecko) → Binance (público, em USDT) → CoinGecko (365 dias) → CoinMarketCap (só com chave)
  fundos (CNPJ)           : CVM, informe diário (cota)
  renda fixa TD-…         : Tesouro Nacional, PU histórico (os cupons não entram no PU; a tela avisa)
  renda fixa RF-…         : sem série de mercado (título da carteira): só indicadores
  câmbio, CDI, IPCA       : Banco Central
  Ibovespa, S&P 500       : Yahoo Finance (índices)

O retorno de cada série vem do módulo de cálculo (comparador_desempenho); aqui só se busca e se padroniza.
"""
from __future__ import annotations

import logging

import pandas as pd
import streamlit as st

import comparador_desempenho as D
import comparador_fontes as F
import gestao as g
import relatorios as R

log = logging.getLogger("comparador_dados")
MESES_FUNDO = 37


# =============================================================================== coletores unitários (cache)
@st.cache_data(ttl=F.ttl("historico"), show_spinner=False)
def _yahoo_preco(tk: str) -> pd.Series:
    import dados
    df, err = dados.historico_yahoo(tk, "5y", "1d")
    if df is None or df.empty or "Close" not in df:
        raise ValueError(err or "sem histórico")
    return D.limpar(df["Close"])


@st.cache_data(ttl=F.ttl("historico"), show_spinner=False)
def _yahoo_volume(tk: str) -> pd.Series:
    """Volume negociado por dia (mesma consulta do preço, já em cache). Vazio se a fonte não trouxer."""
    import dados
    df, _ = dados.historico_yahoo(tk, "5y", "1d")
    if df is None or df.empty or "Volume" not in df:
        return pd.Series(dtype=float)
    return D.limpar_volume(df["Volume"])


@st.cache_data(ttl=F.ttl("historico"), show_spinner=False)
def _yahoo_prov(tk: str) -> pd.Series:
    import dados
    try:
        res, _ = dados._chart_yahoo(tk, "5y", "1d", "div")
        df = g.parse_proventos_chart(res)
    except Exception:
        return pd.Series(dtype=float)
    if df is None or df.empty:
        return pd.Series(dtype=float)
    return pd.Series(df["valor"].values, index=pd.to_datetime(df["data"]), dtype=float)


@st.cache_data(ttl=F.ttl("historico"), show_spinner=False)
def _brapi_preco(tk: str) -> pd.Series:
    import dados
    F.LIMITADORES["brapi"].esperar()
    df, err = dados.historico_brapi(tk, "3mo", "1d")
    if df is None or df.empty:
        raise ValueError(err or "sem histórico")
    return D.limpar(df["Close"])


@st.cache_data(ttl=F.ttl("historico"), show_spinner=False)
def _cripto(gid: str) -> dict:
    import evolucao
    F.LIMITADORES["coingecko"].esperar()
    c = evolucao.coletar_cripto(gid)
    vol = (c.get("longo") or {}).get("volume")
    return {"longo": D.limpar((c.get("longo") or {}).get("preco")), "volume": D.limpar_volume(vol) if vol is not None and len(vol) else pd.Series(dtype=float), "gecko": D.limpar((c.get("series") or {}).get("Preço (USD)")),
            "avisos": list(c.get("avisos", [])) + list((c.get("longo") or {}).get("avisos", []))}


@st.cache_data(ttl=F.ttl("cadastro"), show_spinner=False)
def _simbolo_cripto(gid: str) -> str:
    import cripto
    try:
        return str((cripto.analisar_moeda(gid) or {}).get("simbolo") or "").upper()
    except Exception:
        return ""


def parse_klines(linhas) -> pd.Series:
    """Velas diárias da Binance ([abertura_ms, o, h, l, fechamento, ...]) → série de fechamento por dia (UTC)."""
    if not linhas:
        return pd.Series(dtype=float)
    idx = pd.to_datetime([int(x[0]) for x in linhas], unit="ms").normalize()
    s = pd.Series([float(x[4]) for x in linhas], index=idx)
    return D.limpar(s[~s.index.duplicated(keep="last")])


@st.cache_data(ttl=F.ttl("historico"), show_spinner=False)
def _binance(simbolo: str) -> pd.Series:
    """Fechamento diário contra USDT (≈ dólar), até 5 anos, por paginação de 1000 velas. Sem chave."""
    import time as _t
    import requests
    if not simbolo:
        raise ValueError("símbolo desconhecido")
    ini = int((_t.time() - 5 * 365 * 86400) * 1000)
    linhas = []
    for _ in range(4):
        F.LIMITADORES["binance"].esperar()
        r = requests.get("https://data-api.binance.vision/api/v3/klines", params={"symbol": f"{simbolo}USDT", "interval": "1d", "limit": 1000, "startTime": ini}, timeout=15)
        r.raise_for_status()
        lote = r.json()
        if not lote:
            break
        linhas += lote
        if len(lote) < 1000:
            break
        ini = int(lote[-1][0]) + 1
    return parse_klines(linhas)


def parse_cmc(js) -> pd.Series:
    """Resposta de quotes/historical da CoinMarketCap (formatos com lista ou dicionário por símbolo) → série de preço em USD."""
    def achar(x):
        if isinstance(x, dict):
            if isinstance(x.get("quotes"), list):
                return x["quotes"]
            for v in x.values():
                r = achar(v)
                if r:
                    return r
        elif isinstance(x, list):
            for v in x:
                r = achar(v)
                if r:
                    return r
        return None
    qs = achar(js) or []
    pts = {}
    for q in qs:
        try:
            ts = pd.Timestamp(q["timestamp"])
            ts = ts.tz_convert(None) if ts.tzinfo is not None else ts
            pts[ts.normalize()] = float(q["quote"]["USD"]["price"])
        except Exception:
            continue
    return D.limpar(pd.Series(pts, dtype=float).sort_index()) if pts else pd.Series(dtype=float)


@st.cache_data(ttl=F.ttl("historico"), show_spinner=False)
def _cmc(simbolo: str) -> pd.Series:
    """CoinMarketCap (plano Basic): preço diário de até 1 ano. Precisa da chave CMC_API_KEY (secrets); a chave nunca é registrada."""
    import requests
    chave = F.chave_da_fonte("coinmarketcap")
    if not chave or not simbolo:
        raise ValueError("sem chave ou símbolo")
    F.LIMITADORES["coinmarketcap"].esperar()
    r = requests.get("https://pro-api.coinmarketcap.com/v3/cryptocurrency/quotes/historical",
                     params={"symbol": simbolo, "interval": "daily", "count": 365, "convert": "USD"},
                     headers={"X-CMC_PRO_API_KEY": chave, "Accept": "application/json"}, timeout=20)
    r.raise_for_status()
    return parse_cmc(r.json())


@st.cache_data(ttl=F.ttl("cadastro"), show_spinner=False)
def _fundo(cnpj: str) -> dict:
    import fundos_app
    f = fundos_app.preparar_fundo(cnpj, MESES_FUNDO)
    if f.get("erro") or f.get("serie") is None:
        raise ValueError(f.get("erro") or "sem cota")
    return {"serie": D.limpar(f["serie"]), "nome": f.get("nome"), "avisos": list(f.get("avisos", []))}


@st.cache_data(ttl=F.ttl("cadastro"), show_spinner=False)
def _tesouro(cod: str) -> pd.Series:
    import renda_fixa_app as rfa
    m = rfa.mercado()
    linha = rfa.resolver_td(cod, m["td"])
    if linha is None:
        raise ValueError("título não encontrado")
    t = rfa.titulo_do_tesouro(linha, 1000.0)
    s = rfa.precos_oficiais(t, m["td"]).get("serie")
    if s is None:
        raise ValueError("sem histórico de PU")
    return D.limpar(s["pu"])


@st.cache_data(ttl=F.ttl("cambio"), show_spinner=False)
def _cambio() -> pd.Series:
    import dados
    try:
        return D.limpar(dados.serie_cambio())
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=F.ttl("macro"), show_spinner=False)
def _ipca() -> pd.Series | None:
    try:
        import evolucao
        s = evolucao.coletar_bcb().get("ipca_idx")
        return s if s is not None and len(s) > 1 else None
    except Exception:
        return None


@st.cache_data(ttl=F.ttl("macro"), show_spinner=False)
def _sp_usd() -> pd.Series | None:
    try:
        import fundos_app
        s = fundos_app._serie_yahoo("^GSPC")
        return D.limpar(s) if s is not None and len(s) > 5 else None
    except Exception:
        return None


@st.cache_data(ttl=F.ttl("macro"), show_spinner=False)
def _referencias_reais() -> dict:
    try:
        import gestao_app
        r = gestao_app._referencias()
        return {"series": {k: D.limpar(v) for k, v in (r.get("series") or {}).items() if v is not None and len(v) > 5}, "avisos": list(r.get("avisos", []))}
    except Exception as e:
        return {"series": {}, "avisos": [f"Benchmarks indisponíveis agora ({e.__class__.__name__})."]}


def coletar_refs() -> dict:
    """Câmbio, benchmarks, IPCA e S&P 500 em dólar. O que faltar vem vazio (a tela avisa)."""
    r = _referencias_reais()
    fx = _cambio()
    refs = {"series": r["series"], "sp_usd": _sp_usd(), "fx": fx if len(fx) else None, "ipca": _ipca(), "avisos": list(r["avisos"])}
    if refs["fx"] is None:
        refs["avisos"].append("Câmbio (BCB) indisponível: não dá para converter moedas.")
    return refs


# =============================================================================== por ativo
def moeda_de(codigo: str, classe: str) -> str:
    if classe == "cripto":
        return "USD"
    if classe in ("fundo", "renda_fixa"):
        return "BRL"
    return g.moeda_do_ticker(codigo)


def _cadeia(codigo: str, classe: str) -> list[tuple[str, object]]:
    if classe == "cripto":
        cad = [("yahoo", lambda: _cripto(codigo)["longo"]), ("binance", lambda: _binance(_simbolo_cripto(codigo))), ("coingecko", lambda: _cripto(codigo)["gecko"])]
        if F.chave_da_fonte("coinmarketcap"):
            cad.append(("coinmarketcap", lambda: _cmc(_simbolo_cripto(codigo))))
        return cad
    if classe == "fundo":
        return [("cvm", lambda: _fundo(codigo)["serie"])]
    if classe == "renda_fixa":
        if codigo.upper().startswith("TD-"):
            return [("tesouro", lambda: _tesouro(codigo.upper()))]
        return []
    cad = [("yahoo", lambda: _yahoo_preco(codigo))]
    try:
        import dados
        if g.moeda_do_ticker(codigo) == "BRL" and dados._token():
            cad.append(("brapi", lambda: _brapi_preco(codigo)))
    except Exception:
        pass
    return cad


def coletar_item(codigo: str, classe: str, proventos: bool = True, conferir: bool = False, nome: str | None = None) -> dict:
    """Série padronizada de UM ativo: preço diário, proventos (quando existirem), fonte usada, tentativas e avisos. Sem dado: preço vazio e o motivo."""
    item = {"classe": classe, "moeda": moeda_de(codigo, classe), "nome": nome or codigo, "preco": pd.Series(dtype=float), "prov": None, "volume": None, "fonte": "",
            "tentativas": [], "avisos": [], "coletado_em": R.agora().strftime("%Y-%m-%d %H:%M"), "divergencia": None}
    cad = _cadeia(codigo, classe)
    if not cad:
        item["avisos"].append("Sem série de mercado para este título (renda fixa da carteira): use os indicadores da tabela; o retorno depende da taxa contratada.")
        return item
    res = F.buscar_serie(cad, 30, conferir)
    item["tentativas"] = [t.__dict__ for t in res.tentativas]
    item["avisos"] += res.avisos
    item["divergencia"] = res.divergencia
    if res.serie.empty:
        return item
    item["preco"], item["fonte"] = res.serie, res.fonte
    if res.fonte == "brapi":
        item["avisos"].append("A reserva (Brapi gratuito) só entrega 3 meses de histórico: períodos longos ficam indisponíveis.")
    if classe == "renda_fixa":
        item["avisos"].append("PU do Tesouro: o preço não inclui cupons pagos; o retorno de títulos com cupom aparece menor que o real.")
    if classe == "cripto" and res.fonte == "coingecko":
        item["avisos"].append("CoinGecko gratuito: só 365 dias de histórico.")
    if classe == "cripto" and res.fonte == "binance":
        item["avisos"].append("Binance: preço em USDT (stablecoin quase igual ao dólar); pode diferir ligeiramente da cotação em US$.")
    if classe == "cripto" and res.fonte == "coinmarketcap":
        item["avisos"].append("CoinMarketCap gratuito: só 1 ano de histórico diário.")
    if classe == "fundo":
        item["avisos"] += _fundo(codigo).get("avisos", [])[:2]
    try:
        if classe in ("acao", "etf", "fii") and res.fonte == "yahoo":
            item["volume"] = _yahoo_volume(codigo)
        elif classe == "cripto" and res.fonte == "yahoo":
            item["volume"] = _cripto(codigo)["volume"]
    except Exception:
        item["volume"] = None
    if proventos and classe in ("acao", "etf", "fii") and res.fonte == "yahoo":
        p = _yahoo_prov(codigo)
        if len(p):
            item["prov"] = p
        else:
            item["avisos"].append("Sem proventos no histórico do Yahoo: o retorno é só de preço.")
    return item


def coletar_itens(sel: list[tuple[str, str]], proventos: bool = True, conferir: bool = False, nomes: dict | None = None) -> dict:
    """Coleta sequencial (respeita os limites das fontes) de [(código, classe)] → {código: item}."""
    out = {}
    for cod, cl in sel:
        try:
            out[cod] = coletar_item(cod, cl, proventos, conferir, (nomes or {}).get(cod))
        except Exception as e:
            log.warning("coleta de %s falhou: %s", cod, e.__class__.__name__)
            out[cod] = {"classe": cl, "moeda": moeda_de(cod, cl), "nome": cod, "preco": pd.Series(dtype=float), "prov": None, "fonte": "", "tentativas": [],
                        "avisos": [f"Falha inesperada na coleta ({e.__class__.__name__})."], "coletado_em": R.agora().strftime("%Y-%m-%d %H:%M"), "divergencia": None}
    return out
