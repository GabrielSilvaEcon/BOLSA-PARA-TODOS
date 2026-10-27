"""
Camada de dados do Painel B3: leitura e formatação de números, Banco Central (SGS) e IPEADATA,
e os clientes das fontes (Brapi, Yahoo Finance e Fundamentus).

Mantido em arquivo separado para o app.py ficar abaixo de 100 mil caracteres
(o editor do GitHub corta textos colados acima desse limite).
"""

import os
import re
from datetime import date, timedelta
from numbers import Number

import fundamentus
import pandas as pd
import requests
import streamlit as st
import yfinance as yf


def normaliza(t: str) -> str:
    return str(t).upper().strip().replace(".SA", "")


# ---------------------------------------------------------------- parsing numérico e formatação
def _num(x):
    try:
        if x is None or pd.isna(x):
            return None
        val = float(x)
        return None if pd.isna(val) else val
    except (TypeError, ValueError):
        return None


def parse_num(val):
    """Converte número ou texto (formato BR ou US, com R$, %, parênteses) em float."""
    if val is None:
        return None
    if isinstance(val, Number) and not isinstance(val, bool):
        return _num(val)
    s = str(val).strip().replace("R$", "").replace("%", "").replace("\xa0", "").replace(" ", "")
    if s in ("", "-", "—", "nan", "None", "N/A"):
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif re.fullmatch(r"-?\d{1,3}(\.\d{3})+", s):
        s = s.replace(".", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def parse_pct(val):
    """Devolve SEMPRE fração (0.15 = 15%). Texto com '%' é dividido por 100;
    número puro com |v| <= 1 já é tratado como fração, acima disso como pontos percentuais."""
    if val is None:
        return None
    tem_pct = isinstance(val, str) and "%" in val
    v = parse_num(val)
    if v is None:
        return None
    if tem_pct:
        return v / 100.0
    return v if abs(v) <= 1.0 else v / 100.0


def _sep(s: str) -> str:
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v, casas=2):
    return "—" if v is None or pd.isna(v) else _sep(f"R$ {v:,.{casas}f}")


def pct(v, casas=1):
    return "—" if v is None or pd.isna(v) else _sep(f"{v:,.{casas}f}%")


def num(v, casas=2):
    return "—" if v is None or pd.isna(v) else _sep(f"{v:,.{casas}f}")


def mi(v):
    return "—" if v is None or pd.isna(v) else _sep(f"{v / 1e6:,.0f}")


def estilizar(df: pd.DataFrame, fmts: dict):
    return df.style.format(fmts, na_rep="—")


# ---------------------------------------------------------------- Banco Central (macro + câmbio)
@st.cache_data(ttl=3600, show_spinner=False)
def buscar_macro_bcb(codigo_serie: int, anos: int = 10) -> pd.DataFrame:
    """
    432   Selic meta (% a.a.)            433   IPCA mensal (%)
    13522 IPCA acumulado 12m (%)        1     Dólar comercial venda (R$)
    24369 Taxa de desocupação PNAD (%)
    A API do SGS exige janela de datas em séries diárias, por isso sempre filtramos.
    """
    fim = date.today()
    ini = fim - timedelta(days=int(365.25 * anos))
    url = (f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{codigo_serie}/dados"
           f"?formato=json&dataInicial={ini:%d/%m/%Y}&dataFinal={fim:%d/%m/%Y}")
    for _ in range(2):
        try:
            r = requests.get(url, timeout=12)
            if r.status_code == 200:
                df = pd.DataFrame(r.json())
                if not df.empty and {"data", "valor"} <= set(df.columns):
                    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
                    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
                    return df.dropna(subset=["data", "valor"]).set_index("data").sort_index()
        except Exception:
            continue
    return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def serie_cambio() -> pd.Series:
    """USD/BRL diário (BCB; Yahoo como reserva)."""
    df = buscar_macro_bcb(1, anos=8)
    if not df.empty:
        return df["valor"]
    try:
        h = yf.Ticker("BRL=X").history(period="8y")["Close"]
        h.index = pd.to_datetime(h.index).tz_localize(None)
        return h.dropna()
    except Exception:
        return pd.Series(dtype=float)


def fx_atual():
    s = serie_cambio()
    return float(s.iloc[-1]) if not s.empty else None


def fx_anual() -> dict:
    s = serie_cambio()
    if s.empty:
        return {}
    return {int(a): float(v) for a, v in s.groupby(s.index.year).mean().items()}


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_macro_ipea(codigo_serie: str) -> pd.DataFrame:
    urls = [
        f"https://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo_serie}')",
        f"http://www.ipeadata.gov.br/api/odata4/ValoresSerie(SERCODIGO='{codigo_serie}')",
    ]
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for url in urls:
        try:
            r = requests.get(url, headers=headers, timeout=12)
            if r.status_code != 200:
                continue
            dados = r.json().get("value", [])
            if not dados:
                continue
            df = pd.DataFrame(dados)
            cd = "VALDATA" if "VALDATA" in df.columns else ("Data" if "Data" in df.columns else None)
            cv = "VALVALOR" if "VALVALOR" in df.columns else ("Valor" if "Valor" in df.columns else None)
            if cd and cv:
                df[cd] = pd.to_datetime(df[cd], errors="coerce", utc=True).dt.tz_localize(None)
                df[cv] = pd.to_numeric(df[cv], errors="coerce")
                df = df.dropna(subset=[cd, cv]).set_index(cd).sort_index()
                return df[[cv]].rename(columns={cv: "valor"})
        except Exception:
            continue
    return pd.DataFrame()


# ---------------------------------------------------------------- clientes de dados
def dict_base(tk: str) -> dict:
    return {
        "ticker": tk, "nome": tk, "preco": None, "lpa": None, "vpa": None,
        "div_ano": pd.Series(dtype=float), "div_medio": None, "div_12m": None,
        "ev_ebitda": None, "roe": None, "margem_liq": None, "div_pl": None,
        "acoes": None, "moeda": "BRL", "moeda_balanco": "BRL", "divida_liq": None,
        "setor": None, "data_balanco": None,
        "erro": None, "alertas": [],
    }


def _proventos_series(df: pd.DataFrame, col_data: str, col_valor: str):
    """Série anual de proventos + média dos últimos 5 anos completos + últimos 12 meses."""
    por_ano = df.groupby(df[col_data].dt.year)[col_valor].sum()
    por_ano.index = por_ano.index.astype(int)
    por_ano.index.name = "ano"
    hoje = pd.Timestamp.now(tz=df[col_data].dt.tz) if df[col_data].dt.tz is not None else pd.Timestamp.now()
    mask12 = (df[col_data] >= hoje - pd.Timedelta(days=365)) & (df[col_data] <= hoje)
    div_12m = float(df.loc[mask12, col_valor].sum())
    completos = por_ano[por_ano.index < hoje.year].tail(5)
    base = completos if len(completos) else por_ano
    return por_ano, (float(base.mean()) if not base.empty else 0.0), div_12m


# --- 1. Brapi
BRAPI = "https://brapi.dev/api"


def _token() -> str:
    try:
        t = st.secrets.get("BRAPI_TOKEN")
    except Exception:
        t = None
    return str(t or os.environ.get("BRAPI_TOKEN") or "").strip()


def _get(path: str, params: dict | None = None):
    tok = _token()
    headers = {"Authorization": f"Bearer {tok}"} if tok else {}
    try:
        r = requests.get(f"{BRAPI}{path}", params=params, headers=headers, timeout=15)
    except requests.RequestException as e:
        return None, f"falha de conexão ({e.__class__.__name__})"
    if r.status_code != 200:
        try:
            msg = r.json().get("message")
        except ValueError:
            msg = None
        return None, f"HTTP {r.status_code}" + (f": {msg}" if msg else "")
    try:
        return r.json(), None
    except ValueError:
        return None, "resposta inválida"


def _primeiro(js):
    if isinstance(js, dict):
        res = js.get("results")
        if isinstance(res, list) and res:
            return res[0]
    return None


def _proventos_brapi(lista):
    vazio = pd.Series(dtype=float)
    if not lista:
        return vazio, None, None
    try:
        df = pd.DataFrame(lista)
        if "rate" not in df:
            return vazio, None, None
        df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
        data = pd.Series(pd.NaT, index=df.index, dtype="datetime64[ns, UTC]")
        for col in ("paymentDate", "exDate", "lastDatePrior"):
            if col in df:
                data = data.fillna(pd.to_datetime(df[col], errors="coerce", utc=True))
        df["data"] = data
        df = df.dropna(subset=["rate", "data"])
        if df.empty:
            return vazio, None, None
        return _proventos_series(df, "data", "rate")
    except Exception:
        return vazio, None, None


@st.cache_data(ttl=900, show_spinner=False)
def buscar_brapi(ticker: str) -> dict:
    tk = normaliza(ticker)
    d = dict_base(tk)
    erros = []
    try:
        js, err = _get(f"/quote/{tk}", {"dividends": "true"})
        if err:
            erros.append(f"cotação: {err}")
        q = _primeiro(js)
        lista_div = None
        if q:
            d["nome"] = q.get("longName") or q.get("shortName") or tk
            d["preco"] = _num(q.get("regularMarketPrice"))
            d["lpa"] = _num(q.get("earningsPerShare"))
            d["moeda"] = q.get("currency") or "BRL"
            lista_div = (q.get("dividendsData") or {}).get("cashDividends")

        if lista_div is None:
            js, err = _get("/v2/stocks/dividends", {"symbols": tk})
            if err:
                erros.append(f"dividendos: {err}")
            item = _primeiro(js)
            if item:
                lista_div = (item.get("data") or {}).get("cashDividends")
        d["div_ano"], d["div_medio"], d["div_12m"] = _proventos_brapi(lista_div)

        js, err = _get("/v2/stocks/statistics", {"symbols": tk})
        if err:
            erros.append(f"múltiplos: {err}")
        est = (_primeiro(js) or {}).get("data") or {}
        if isinstance(est, dict):
            d["vpa"] = _num(est.get("bookValue"))
            d["lpa"] = _num(est.get("trailingEps")) or d["lpa"]
            d["ev_ebitda"] = _num(est.get("enterpriseToEbitda"))
            d["acoes"] = _num(est.get("sharesOutstanding"))
            d["margem_liq"] = _num(est.get("profitMargins"))

        js, err = _get("/v2/stocks/financial-data", {"symbols": tk})
        if err:
            erros.append(f"dados financeiros: {err}")
        fin = (_primeiro(js) or {}).get("data") or {}
        if isinstance(fin, dict):
            d["roe"] = _num(fin.get("returnOnEquity"))
            ml = _num(fin.get("profitMargins"))
            d["margem_liq"] = ml if ml is not None else d["margem_liq"]
            # debtToEquity já vem em percentual (padrão Yahoo): não multiplicar
            d["div_pl"] = _num(fin.get("debtToEquity"))
            if fin.get("financialCurrency"):
                d["moeda_balanco"] = fin["financialCurrency"]
            td, tc = _num(fin.get("totalDebt")), _num(fin.get("totalCash"))
            if td is not None and tc is not None:
                d["divida_liq"] = td - tc
    except Exception as e:
        erros.append(f"exceção brapi: {e}")
    d["erro"] = "; ".join(erros) or None
    return d


@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa_brapi(ticker: str) -> pd.DataFrame:
    try:
        js, _ = _get("/v2/stocks/cash-flow", {"symbols": normaliza(ticker), "period": "annual"})
        linhas = (_primeiro(js) or {}).get("data")
        if not linhas:
            return pd.DataFrame()
        df = pd.DataFrame(linhas)
        if "endDate" not in df:
            return pd.DataFrame()
        nomes = {"operatingCashFlow": "Caixa operacional",
                 "investmentCashFlow": "Caixa de investimento",
                 "freeCashFlow": "Fluxo de caixa livre"}
        cols = [k for k in nomes if k in df]
        if not cols:
            return pd.DataFrame()
        out = df[cols].apply(pd.to_numeric, errors="coerce").rename(columns=nomes)
        out.index = pd.to_datetime(df["endDate"], errors="coerce").dt.year
        out = out[out.index.notna()]
        out.index = out.index.astype(int)
        out = out[~out.index.duplicated(keep="last")]
        return out.dropna(how="all").sort_index()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def historico_brapi(ticker: str, periodo: str, intervalo: str):
    try:
        js, err = _get(f"/quote/{normaliza(ticker)}", {"range": periodo, "interval": intervalo})
        dados = (_primeiro(js) or {}).get("historicalDataPrice")
        if not dados:
            return pd.DataFrame(), err or "a API não devolveu histórico para esse ativo/período"
        df = pd.DataFrame(dados).rename(columns={
            "date": "Date", "open": "Open", "high": "High",
            "low": "Low", "close": "Close", "volume": "Volume"})
        df["Date"] = (pd.to_datetime(df["Date"], unit="s", utc=True)
                      .dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None).dt.normalize())
        df = df.drop_duplicates("Date").set_index("Date").sort_index()
        df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
        return df.dropna(subset=["Open", "High", "Low", "Close"]), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# --- 2. Yahoo Finance
@st.cache_data(ttl=900, show_spinner=False)
def buscar_yahoo(ticker: str) -> dict:
    d = dict_base(normaliza(ticker))
    try:
        t = yf.Ticker(d["ticker"] + ".SA")
        info = t.info or {}
        d["nome"] = info.get("longName") or info.get("shortName") or d["ticker"]
        d["preco"] = _num(info.get("currentPrice") or info.get("regularMarketPrice"))
        d["lpa"] = _num(info.get("trailingEps"))
        d["vpa"] = _num(info.get("bookValue"))
        d["ev_ebitda"] = _num(info.get("enterpriseToEbitda"))
        d["roe"] = _num(info.get("returnOnEquity"))
        d["margem_liq"] = _num(info.get("profitMargins"))
        d["div_pl"] = _num(info.get("debtToEquity"))  # já em %
        d["acoes"] = _num(info.get("sharesOutstanding"))
        d["moeda"] = info.get("currency") or "BRL"
        d["moeda_balanco"] = info.get("financialCurrency") or d["moeda"]
        td, tc = _num(info.get("totalDebt")), _num(info.get("totalCash"))
        if td is not None and tc is not None:
            d["divida_liq"] = td - tc
        d["setor"] = info.get("sector")
        try:
            mrq = info.get("mostRecentQuarter")
            if mrq:
                d["data_balanco"] = pd.to_datetime(mrq, unit="s").strftime("%Y-%m-%d")
        except Exception:
            pass

        divs = t.dividends
        if divs is not None and not divs.empty:
            df = divs.rename("rate").to_frame()
            df["data"] = pd.to_datetime(df.index).tz_localize(None)
            d["div_ano"], d["div_medio"], d["div_12m"] = _proventos_series(df, "data", "rate")
    except Exception as e:
        d["erro"] = f"Erro Yahoo Finance: {e}"
    return d


@st.cache_data(ttl=900, show_spinner=False)
def buscar_caixa_yahoo(ticker: str) -> pd.DataFrame:
    try:
        cf = yf.Ticker(normaliza(ticker) + ".SA").cashflow
        if cf is None or cf.empty:
            return pd.DataFrame()
        cf = cf.T.apply(pd.to_numeric, errors="coerce")
        out = pd.DataFrame(index=cf.index)
        if "Operating Cash Flow" in cf:
            out["Caixa operacional"] = cf["Operating Cash Flow"]
        if "Investing Cash Flow" in cf:
            out["Caixa de investimento"] = cf["Investing Cash Flow"]
        if "Free Cash Flow" in cf:
            out["Fluxo de caixa livre"] = cf["Free Cash Flow"]
        elif "Operating Cash Flow" in cf and "Capital Expenditure" in cf:
            out["Fluxo de caixa livre"] = cf["Operating Cash Flow"] + cf["Capital Expenditure"]
        if out.empty:
            return pd.DataFrame()
        out.index = pd.to_datetime(out.index).year
        out = out[out.index.notna()]
        out.index = out.index.astype(int)
        out = out[~out.index.duplicated(keep="first")]
        return out.dropna(how="all").sort_index()
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def historico_yahoo(ticker: str, periodo: str, intervalo: str):
    tk = normaliza(ticker) + ".SA"
    p = {"6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y"}.get(periodo, "1y")
    try:
        df = yf.download(tk, period=p, interval=intervalo, progress=False)
        if df.empty:
            return pd.DataFrame(), "Sem dados históricos do Yahoo."
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
        df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
        return df.dropna(subset=["Open", "High", "Low", "Close"]), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# --- 3. Fundamentus
@st.cache_data(ttl=900, show_spinner=False)
def buscar_fundamentus(ticker: str) -> dict:
    tk = normaliza(ticker)
    d = dict_base(tk)
    try:
        df = fundamentus.get_detalhes_papel(tk)
        if df is None or df.empty:
            d["erro"] = "Ativo não encontrado no Fundamentus."
            return d
        row = df.loc[tk] if tk in df.index else df.iloc[0]
        d["preco"] = parse_num(row.get("Cotacao"))
        d["lpa"] = parse_num(row.get("LPA"))
        d["vpa"] = parse_num(row.get("VPA"))
        d["ev_ebitda"] = parse_num(row.get("EV_EBITDA"))
        d["roe"] = parse_pct(row.get("ROE"))
        d["margem_liq"] = parse_pct(row.get("Marg_Liquida"))
        dbp = parse_num(row.get("Div_Br_Patrim"))  # razão (1,5 = 150%)
        d["div_pl"] = dbp * 100 if dbp is not None else None
        d["acoes"] = parse_num(row.get("Nro_Acoes"))
        dy = parse_pct(row.get("Div_Yield"))
        if dy is not None and d["preco"]:
            d["div_12m"] = dy * d["preco"]
            d["div_medio"] = d["div_12m"]
            d["alertas"].append("Fundamentus não traz histórico de proventos: a média de 5 anos "
                                "foi aproximada pelo dividend yield atual.")
    except Exception as e:
        d["erro"] = f"Erro Fundamentus: {e}"
    return d
