"""
Camada de dados do Painel B3: leitura e formatação de números, Banco Central (SGS) e IPEADATA,
e os clientes das fontes (Brapi, Yahoo Finance e Fundamentus).

Mantido em arquivo separado para o app.py ficar abaixo de 100 mil caracteres
(o editor do GitHub corta textos colados acima desse limite).

Resiliência (importante no Streamlit Cloud, onde o Yahoo costuma bloquear o servidor):
  - falhas NUNCA ficam guardadas em cache (só leituras bem-sucedidas), e uma fonte que acabou de falhar
    ganha uma pausa curta para não ser bombardeada;
  - Yahoo: preço e proventos vêm da API de gráfico (menos bloqueada que o resumo de fundamentos);
    se o resumo falhar, os indicadores são completados pelo Fundamentus;
  - Fundamentus: usa a biblioteca e, se ela falhar, lê a página direto; os proventos vêm do gráfico do Yahoo;
  - Brapi: usa o endpoint documentado /quote com dividends=true e modules=defaultKeyStatistics,financialData.
"""

import html as _html
import os
import re
import time
import unicodedata
from datetime import date, timedelta
from numbers import Number

import pandas as pd
import requests
import streamlit as st
import yfinance as yf

try:
    import fundamentus
except Exception:  # biblioteca ausente ou quebrada: o app segue com a leitura direta da página
    fundamentus = None


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


# ---------------------------------------------------------------- controle de falhas (nada de falha em cache)
_FALHAS: dict = {}
_ESPERA_S = 45  # pausa curta depois de uma falha, para não sobrecarregar a fonte


def _barrar(chave):
    t0 = _FALHAS.get(chave)
    if t0 and time.time() - t0 < _ESPERA_S:
        raise RuntimeError("a fonte falhou há instantes; nova tentativa automática em alguns segundos")


def _falhou(chave):
    _FALHAS[chave] = time.time()


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


# --- API de gráfico do Yahoo (preço, histórico e proventos; não exige o "crumb" que o Yahoo bloqueia)
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
       "Chrome/124.0 Safari/537.36")


def _chart_yahoo(tk: str, periodo: str, intervalo: str, eventos: str = ""):
    """Devolve (resultado do gráfico, erro). Tenta dois servidores do Yahoo."""
    params = {"range": periodo, "interval": intervalo}
    if eventos:
        params["events"] = eventos
    erro = "sem resposta"
    for host in ("query1", "query2"):
        try:
            r = requests.get(f"https://{host}.finance.yahoo.com/v8/finance/chart/{normaliza(tk)}.SA",
                             params=params, headers={"User-Agent": _UA, "Accept": "application/json"}, timeout=15)
            if r.status_code == 200:
                ch = r.json().get("chart") or {}
                res = ch.get("result")
                if res:
                    return res[0], None
                erro = str((ch.get("error") or {}).get("description") or "sem dados para o ativo")
            else:
                erro = f"HTTP {r.status_code}"
        except Exception as e:
            erro = f"falha de conexão ({e.__class__.__name__})"
    return None, erro


def _proventos_chart(res):
    vazio = pd.Series(dtype=float)
    ev = ((res or {}).get("events") or {}).get("dividends") or {}
    if not ev:
        return vazio, None, None
    linhas = []
    for v in ev.values():
        valor, ts = _num(v.get("amount")), v.get("date")
        if valor is not None and ts is not None:
            linhas.append({"data": pd.to_datetime(int(ts), unit="s"), "rate": valor})
    if not linhas:
        return vazio, None, None
    return _proventos_series(pd.DataFrame(linhas), "data", "rate")


def _meta(res) -> dict:
    return (res or {}).get("meta") or {}


def _historico_chart(tk: str, periodo: str, intervalo: str):
    res, err = _chart_yahoo(tk, periodo, intervalo)
    if not res:
        return pd.DataFrame(), err
    try:
        ts = res.get("timestamp") or []
        q = ((res.get("indicators") or {}).get("quote") or [{}])[0]
        df = pd.DataFrame({"Open": q.get("open"), "High": q.get("high"), "Low": q.get("low"),
                           "Close": q.get("close"), "Volume": q.get("volume")},
                          index=pd.to_datetime(ts, unit="s", utc=True)
                          .tz_convert("America/Sao_Paulo").tz_localize(None).normalize())
        df = df[~df.index.duplicated(keep="last")].sort_index()
        df = df.apply(pd.to_numeric, errors="coerce")
        return df.dropna(subset=["Open", "High", "Low", "Close"]), None
    except Exception as e:
        return pd.DataFrame(), f"histórico do gráfico em formato inesperado ({e.__class__.__name__})"


# --- 1. Brapi (endpoint documentado: /quote/{ticker}?dividends=true&modules=...)
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


def _brapi_bruto(tk: str) -> dict:
    d = dict_base(tk)
    erros = []
    # 1) cotação + proventos (disponível mesmo sem token para os tickers de teste da Brapi)
    js, err = _get(f"/quote/{tk}", {"dividends": "true"})
    if err:
        erros.append(f"cotação: {err}")
    q = _primeiro(js)
    if q:
        d["nome"] = q.get("longName") or q.get("shortName") or tk
        d["preco"] = _num(q.get("regularMarketPrice"))
        d["lpa"] = _num(q.get("earningsPerShare"))
        d["moeda"] = q.get("currency") or "BRL"
        lista = (q.get("dividendsData") or {}).get("cashDividends")
        d["div_ano"], d["div_medio"], d["div_12m"] = _proventos_brapi(lista)
    # 2) indicadores fundamentalistas (módulos)
    js2, err2 = _get(f"/quote/{tk}", {"modules": "defaultKeyStatistics,financialData"})
    if err2:
        erros.append(f"indicadores: {err2}")
    q2 = _primeiro(js2) or {}
    est = q2.get("defaultKeyStatistics") or {}
    fin = q2.get("financialData") or {}
    if isinstance(est, dict):
        d["vpa"] = _num(est.get("bookValue"))
        d["lpa"] = _num(est.get("trailingEps")) or d["lpa"]
        d["ev_ebitda"] = _num(est.get("enterpriseToEbitda"))
        d["acoes"] = _num(est.get("sharesOutstanding"))
        d["margem_liq"] = _num(est.get("profitMargins"))
    if isinstance(fin, dict):
        d["roe"] = _num(fin.get("returnOnEquity"))
        ml = _num(fin.get("profitMargins"))
        d["margem_liq"] = ml if ml is not None else d["margem_liq"]
        d["div_pl"] = _num(fin.get("debtToEquity"))  # já vem em percentual (padrão Yahoo)
        if fin.get("financialCurrency"):
            d["moeda_balanco"] = fin["financialCurrency"]
        td, tc = _num(fin.get("totalDebt")), _num(fin.get("totalCash"))
        if td is not None and tc is not None:
            d["divida_liq"] = td - tc
    if d["preco"]:
        if erros:
            d["alertas"].append("Brapi parcial: " + "; ".join(erros))
    else:
        d["erro"] = "; ".join(erros) or "Brapi sem preço"
    return d


@st.cache_data(ttl=900, show_spinner=False)
def _brapi_ok(tk: str) -> dict:
    _barrar(("brapi", tk))
    d = _brapi_bruto(tk)
    if not d.get("preco"):
        _falhou(("brapi", tk))
        raise ValueError(d.get("erro") or "sem preço")
    return d


def buscar_brapi(ticker: str) -> dict:
    tk = normaliza(ticker)
    try:
        return _brapi_ok(tk)
    except Exception as e:
        d = dict_base(tk)
        d["erro"] = f"Brapi: {e}"
        return d


def _linha_caixa(item: dict) -> dict | None:
    """Lê uma linha de fluxo de caixa com nomes de campos alternativos (Brapi/Yahoo)."""
    def pega(*nomes):
        for n in nomes:
            v = _num(item.get(n))
            if v is not None:
                return v
        return None
    op = pega("operatingCashFlow", "totalCashFromOperatingActivities", "cashFlowFromOperatingActivities")
    inv = pega("investmentCashFlow", "totalCashflowsFromInvestingActivities", "investingCashFlow")
    capex = pega("capitalExpenditures", "capitalExpenditure")
    fcl = pega("freeCashFlow")
    if fcl is None and op is not None and capex is not None:
        fcl = op - abs(capex)
    data = item.get("endDate") or item.get("date")
    if isinstance(data, dict):
        data = data.get("fmt") or data.get("raw")
    ano = pd.to_datetime(data, errors="coerce")
    if pd.isna(ano) or (op is None and fcl is None):
        return None
    return {"ano": int(ano.year), "Caixa operacional": op, "Caixa de investimento": inv,
            "Fluxo de caixa livre": fcl}


@st.cache_data(ttl=900, show_spinner=False)
def _caixa_brapi_ok(tk: str) -> pd.DataFrame:
    js, err = _get(f"/quote/{tk}", {"modules": "cashflowHistory"})
    q = _primeiro(js) or {}
    bruto = q.get("cashflowHistory") or q.get("cashflowStatementHistory") or []
    if isinstance(bruto, dict):
        bruto = bruto.get("cashflowStatements") or []
    linhas = [x for x in (_linha_caixa(i) for i in bruto if isinstance(i, dict)) if x]
    if not linhas:
        raise ValueError(err or "sem fluxo de caixa")
    out = pd.DataFrame(linhas).drop_duplicates("ano", keep="first").set_index("ano").sort_index()
    return out.dropna(how="all")


def buscar_caixa_brapi(ticker: str) -> pd.DataFrame:
    try:
        return _caixa_brapi_ok(normaliza(ticker))
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def _hist_brapi_ok(tk: str, periodo: str, intervalo: str) -> pd.DataFrame:
    js, err = _get(f"/quote/{tk}", {"range": periodo, "interval": intervalo})
    dados = (_primeiro(js) or {}).get("historicalDataPrice")
    if not dados:
        raise ValueError(err or "a API não devolveu histórico para esse ativo/período")
    df = pd.DataFrame(dados).rename(columns={
        "date": "Date", "open": "Open", "high": "High",
        "low": "Low", "close": "Close", "volume": "Volume"})
    df["Date"] = (pd.to_datetime(df["Date"], unit="s", utc=True)
                  .dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None).dt.normalize())
    df = df.drop_duplicates("Date").set_index("Date").sort_index()
    df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
    return df.dropna(subset=["Open", "High", "Low", "Close"])


def historico_brapi(ticker: str, periodo: str, intervalo: str):
    try:
        return _hist_brapi_ok(normaliza(ticker), periodo, intervalo), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# --- 3. Fundamentus (biblioteca + leitura direta da página como reserva)
def _chave_txt(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


_TR_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.S | re.I)
_TD_RE = re.compile(r"<t[dh][^>]*>(.*?)</t[dh]>", re.S | re.I)


def _texto_html(h: str) -> str:
    return _html.unescape(re.sub(r"<[^>]+>", "", h)).strip()


def _fundamentus_pagina(tk: str) -> dict:
    """Lê a página de detalhes do Fundamentus direto e devolve {rótulo normalizado: texto}.
    Lê o HTML como texto (sem o pandas converter números), pois o formato é brasileiro."""
    r = requests.get("https://www.fundamentus.com.br/detalhes.php", params={"papel": tk},
                     headers={"User-Agent": _UA, "Referer": "https://www.fundamentus.com.br/"}, timeout=20)
    r.raise_for_status()
    campos = {}
    for tr in _TR_RE.findall(r.text):
        cel = [_texto_html(c) for c in _TD_RE.findall(tr)]
        for i in range(0, len(cel) - 1, 2):
            rot, val = cel[i], cel[i + 1]
            if rot and val:
                campos.setdefault(_chave_txt(rot), val)
    return campos


def _campo(campos: dict, *nomes):
    for n in nomes:
        v = campos.get(_chave_txt(n))
        if v is not None:
            return v
    return None


def _fundamentus_bruto(tk: str) -> dict:
    d = dict_base(tk)
    erros = []
    row = None
    if fundamentus is not None:
        try:
            df = fundamentus.get_detalhes_papel(tk)
            if df is not None and not df.empty:
                row = df.loc[tk] if tk in df.index else df.iloc[0]
        except Exception as e:
            erros.append(f"biblioteca ({e.__class__.__name__})")
    if row is not None:
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
    else:
        try:  # reserva: lê a página direto
            c = _fundamentus_pagina(tk)
            d["preco"] = parse_num(_campo(c, "Cotação"))
            d["lpa"] = parse_num(_campo(c, "LPA"))
            d["vpa"] = parse_num(_campo(c, "VPA"))
            d["ev_ebitda"] = parse_num(_campo(c, "EV / EBITDA", "EV/EBITDA"))
            d["roe"] = parse_pct(_campo(c, "ROE"))
            d["margem_liq"] = parse_pct(_campo(c, "Marg. Líquida", "Marg Liquida"))
            dbp = next((parse_num(v) for k, v in c.items() if "div" in k and "patrim" in k), None)
            d["div_pl"] = dbp * 100 if dbp is not None else None
            d["acoes"] = parse_num(_campo(c, "Nro. Ações", "Nro Acoes"))
            dy = parse_pct(_campo(c, "Div. Yield", "Dividend Yield"))
            if d["preco"]:
                d["alertas"].append("Fundamentus lido direto da página (a biblioteca falhou).")
        except Exception as e:
            erros.append(f"página ({e.__class__.__name__})")
            dy = None

    # Proventos: o Fundamentus não traz histórico, então usa o gráfico do Yahoo (leve e pouco bloqueado)
    try:
        res, err = _chart_yahoo(tk, "10y", "1mo", "div")
        if res:
            if not d["preco"]:
                d["preco"] = _num(_meta(res).get("regularMarketPrice"))
            ano, med, d12 = _proventos_chart(res)
            if len(ano):
                d["div_ano"], d["div_medio"], d["div_12m"] = ano, med, d12
    except Exception:
        pass
    if d["div_medio"] is None and dy is not None and d["preco"]:
        d["div_12m"] = dy * d["preco"]
        d["div_medio"] = d["div_12m"]
        d["alertas"].append("Sem histórico de proventos: a média de 5 anos foi aproximada pelo "
                            "dividend yield atual.")
    if not d["preco"]:
        d["erro"] = "Fundamentus: " + ("; ".join(erros) or "ativo não encontrado")
    return d


@st.cache_data(ttl=900, show_spinner=False)
def _fundamentus_ok(tk: str) -> dict:
    _barrar(("fundamentus", tk))
    d = _fundamentus_bruto(tk)
    if not d.get("preco"):
        _falhou(("fundamentus", tk))
        raise ValueError(d.get("erro") or "sem preço")
    return d


def buscar_fundamentus(ticker: str) -> dict:
    tk = normaliza(ticker)
    try:
        return _fundamentus_ok(tk)
    except Exception as e:
        d = dict_base(tk)
        d["erro"] = str(e) if str(e).startswith("Fundamentus") else f"Fundamentus: {e}"
        return d


# --- 2. Yahoo Finance
def _yahoo_bruto(tk: str) -> dict:
    d = dict_base(tk)
    erros = []
    t = None
    # 1) resumo de fundamentos pelo yfinance (é a parte que o Yahoo mais bloqueia)
    try:
        t = yf.Ticker(tk + ".SA")
        info = t.info or {}
        d["nome"] = info.get("longName") or info.get("shortName") or tk
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
    except Exception as e:
        erros.append(f"resumo de fundamentos indisponível ({e.__class__.__name__})")

    # 2) preço e proventos pela API de gráfico
    res, err = _chart_yahoo(tk, "10y", "1mo", "div")
    if res:
        meta = _meta(res)
        if not d["preco"]:
            d["preco"] = _num(meta.get("regularMarketPrice"))
            if meta.get("currency"):
                d["moeda"] = meta["currency"]
                if d["lpa"] is None and d["vpa"] is None:
                    d["moeda_balanco"] = meta["currency"]
        ano, med, d12 = _proventos_chart(res)
        if len(ano):
            d["div_ano"], d["div_medio"], d["div_12m"] = ano, med, d12
    elif err:
        erros.append(f"gráfico: {err}")

    # 3) proventos pelo yfinance, se o gráfico não trouxe
    if len(d["div_ano"]) == 0 and t is not None:
        try:
            divs = t.dividends
            if divs is not None and not divs.empty:
                df = divs.rename("rate").to_frame()
                df["data"] = pd.to_datetime(df.index).tz_localize(None)
                d["div_ano"], d["div_medio"], d["div_12m"] = _proventos_series(df, "data", "rate")
        except Exception:
            pass

    # 4) sem LPA e VPA (resumo bloqueado): completa com o Fundamentus
    if d["preco"] and d["lpa"] is None and d["vpa"] is None:
        try:
            f = _fundamentus_bruto(tk)
            if f.get("preco"):
                for k in ("lpa", "vpa", "ev_ebitda", "roe", "margem_liq", "div_pl", "acoes"):
                    if d.get(k) is None and f.get(k) is not None:
                        d[k] = f[k]
                d["alertas"].append("Indicadores (LPA, VPA, ROE...) completados pelo Fundamentus, "
                                    "porque o resumo do Yahoo ficou indisponível.")
        except Exception:
            pass

    if d["preco"]:
        if erros:
            d["alertas"].append("Yahoo parcial: " + "; ".join(erros))
    else:
        d["erro"] = "Erro Yahoo Finance: " + ("; ".join(erros) or "sem preço")
    return d


@st.cache_data(ttl=900, show_spinner=False)
def _yahoo_ok(tk: str) -> dict:
    _barrar(("yahoo", tk))
    d = _yahoo_bruto(tk)
    if not d.get("preco"):
        _falhou(("yahoo", tk))
        raise ValueError(d.get("erro") or "sem preço")
    return d


def buscar_yahoo(ticker: str) -> dict:
    tk = normaliza(ticker)
    try:
        return _yahoo_ok(tk)
    except Exception as e:
        d = dict_base(tk)
        d["erro"] = str(e) if str(e).startswith("Erro Yahoo") else f"Yahoo Finance: {e}"
        return d


@st.cache_data(ttl=900, show_spinner=False)
def _caixa_yahoo_ok(tk: str) -> pd.DataFrame:
    _barrar(("caixa", tk))
    try:
        cf = yf.Ticker(tk + ".SA").cashflow
    except Exception:
        _falhou(("caixa", tk))
        raise
    if cf is None or cf.empty:
        _falhou(("caixa", tk))
        raise ValueError("sem fluxo de caixa")
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
        raise ValueError("sem fluxo de caixa")
    out.index = pd.to_datetime(out.index).year
    out = out[out.index.notna()]
    out.index = out.index.astype(int)
    out = out[~out.index.duplicated(keep="first")]
    return out.dropna(how="all").sort_index()


def buscar_caixa_yahoo(ticker: str) -> pd.DataFrame:
    try:
        return _caixa_yahoo_ok(normaliza(ticker))
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def _hist_yahoo_ok(tk: str, periodo: str, intervalo: str) -> pd.DataFrame:
    _barrar(("hist", tk, periodo, intervalo))
    erro = "Sem dados históricos do Yahoo."
    try:  # 1) API de gráfico direta (menos bloqueada)
        df, err = _historico_chart(tk, periodo, intervalo)
        if not df.empty:
            return df
        erro = err or erro
    except Exception as e:
        erro = str(e)
    try:  # 2) yfinance
        df = yf.download(tk + ".SA", period=periodo, interval=intervalo, progress=False)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.index = pd.to_datetime(df.index).tz_localize(None).normalize()
            df = df[["Open", "High", "Low", "Close", "Volume"]].apply(pd.to_numeric, errors="coerce")
            df = df.dropna(subset=["Open", "High", "Low", "Close"])
            if not df.empty:
                return df
    except Exception as e:
        erro = f"{erro} | yfinance: {e}"
    _falhou(("hist", tk, periodo, intervalo))
    raise ValueError(erro)


def historico_yahoo(ticker: str, periodo: str, intervalo: str):
    p = {"6mo": "6mo", "1y": "1y", "2y": "2y", "5y": "5y"}.get(periodo, "1y")
    try:
        return _hist_yahoo_ok(normaliza(ticker), p, intervalo), None
    except Exception as e:
        return pd.DataFrame(), str(e)


# Mapeamento de tickers para os códigos microeconômicos correspondentes
MAPEAMENTO_MICRO = {
    "PETR4": {
        "tipo": "ipca",
        "codigo": "4812",  # Código do subitem 'Combustíveis (automotivos)' no IPCA
        "nome_exibicao": "Preço dos Combustíveis (IPCA)"
    },
    "ABCB4": {
        "tipo": "credito",
        "codigo": "20539",  # Exemplo de código do Banco Central para concessão de crédito
        "nome_exibicao": "Concessão de Crédito - Setor Privado"
    },
    "BBAS3": {
        "tipo": "credito",
        "codigo": "20539",
        "nome_exibicao": "Inadimplência Geral do Crédito"
    },
    "INBR32": {
        "tipo": "pmc",
        "codigo": "11046",  # Código geral do volume de vendas no Comércio (PMC)
        "nome_exibicao": "Volume de Vendas do Varejo (PMC)"
    }
}