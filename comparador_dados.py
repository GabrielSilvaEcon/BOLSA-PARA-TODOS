"""
Passo 20 · COLETA de séries do comparador (a única parte que fala com a internet).

Cada classe tem a sua cadeia de fontes, da mais confiável para a reserva, e TODAS as chamadas passam pelo cache (validade por tipo de dado, ver
comparador_fontes.TTL), pelo limitador de consultas e pela cadeia de fontes autorizadas. Falha nunca fica em cache e nunca vira dado inventado.

  ações, ETFs, FIIs, BDRs : Yahoo Finance (até 5 anos, com proventos)  → Brapi (reserva, só 3 meses e só com chave)
  criptomoedas            : Yahoo SÍMBOLO-USD (histórico longo, validado contra a CoinGecko) → CoinGecko (365 dias)
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
    return {"longo": D.limpar((c.get("longo") or {}).get("preco")), "gecko": D.limpar((c.get("series") or {}).get("Preço (USD)")),
            "avisos": list(c.get("avisos", [])) + list((c.get("longo") or {}).get("avisos", []))}


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
        return [("yahoo", lambda: _cripto(codigo)["longo"]), ("coingecko", lambda: _cripto(codigo)["gecko"])]
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
    item = {"classe": classe, "moeda": moeda_de(codigo, classe), "nome": nome or codigo, "preco": pd.Series(dtype=float), "prov": None, "fonte": "",
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
    if classe == "fundo":
        item["avisos"] += _fundo(codigo).get("avisos", [])[:2]
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
