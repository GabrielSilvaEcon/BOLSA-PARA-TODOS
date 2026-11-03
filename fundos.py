"""
Fundos de investimento (informe diário da CVM) e Tesouro Direto (preços e taxas do Tesouro Transparente).

Os arquivos são lidos com detecção de colunas: se o layout mudar e uma coluna essencial não for encontrada, a leitura
levanta LayoutInesperado com a lista de colunas que chegaram, e a tela mostra isso em vez de números errados.
A parte pura (padronizar, métricas) não acessa a internet; a coleta é a única que faz requisições.
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile
from datetime import date

import pandas as pd

import crescimento as cr

try:
    import requests
except Exception:                         # pragma: no cover
    requests = None

URL_INF_DIARIO = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/inf_diario_fi_{ym}.zip"
URL_INF_DIARIO_HIST = "https://dados.cvm.gov.br/dados/FI/DOC/INF_DIARIO/DADOS/HIST/inf_diario_fi_{ano}.zip"
URL_TESOURO = ("https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/"
               "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/PrecoTaxaTesouroDireto.csv")
UA = {"User-Agent": "Mozilla/5.0 (Bolsa para Todos)"}


class LayoutInesperado(Exception):
    """Arquivo sem alguma coluna essencial (o layout da fonte pode ter mudado)."""


def _chave(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _achar(colunas, *candidatos) -> str | None:
    por_chave = {_chave(c): c for c in colunas}
    for c in candidatos:
        if _chave(c) in por_chave:
            return por_chave[_chave(c)]
    return None


# =============================================================================== CNPJ
def so_digitos(cnpj) -> str:
    return re.sub(r"\D", "", str(cnpj or ""))


def cnpj_valido(cnpj) -> bool:
    d = so_digitos(cnpj)
    if len(d) != 14 or len(set(d)) == 1:
        return False

    def dv(base, pesos):
        r = sum(int(x) * p for x, p in zip(base, pesos)) % 11
        return "0" if r < 2 else str(11 - r)
    p1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    p2 = [6] + p1
    return d[12] == dv(d[:12], p1) and d[13] == dv(d[:13], p2)


def formatar_cnpj(cnpj) -> str:
    d = so_digitos(cnpj)
    return f"{d[:2]}.{d[2:5]}.{d[5:8]}/{d[8:12]}-{d[12:]}" if len(d) == 14 else str(cnpj)


# =============================================================================== informe diário
CAMPOS_INFORME = {"cnpj": ("CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO"), "data": ("DT_COMP",), "cota": ("VL_QUOTA",),
                  "pl": ("VL_PATRIM_LIQ",), "cotistas": ("NR_COTST",), "captacao": ("CAPTC_DIA",), "resgate": ("RESG_DIA",)}
ESSENCIAIS_INFORME = ("cnpj", "data", "cota")


def colunas_desejadas() -> set:
    return {c for cs in CAMPOS_INFORME.values() for c in cs}


def padronizar_informe(df: pd.DataFrame, cnpj: str | None = None) -> pd.DataFrame:
    """Informe diário → índice = data; colunas cota, pl, cotistas, captacao, resgate (as que existirem).
    Filtra o CNPJ pedido. Aceita o layout antigo (CNPJ_FUNDO) e o novo (CNPJ_FUNDO_CLASSE). Números no padrão
    do arquivo (ponto decimal)."""
    if df is None or df.empty:
        return pd.DataFrame()
    cols = {k: _achar(df.columns, *v) for k, v in CAMPOS_INFORME.items()}
    faltam = [k for k in ESSENCIAIS_INFORME if cols[k] is None]
    if faltam:
        raise LayoutInesperado(f"colunas essenciais ausentes ({', '.join(faltam)}); recebi: {', '.join(map(str, df.columns))}")
    d = df
    if cnpj:
        alvo = so_digitos(cnpj)
        d = d[d[cols["cnpj"]].map(so_digitos) == alvo]
    if d.empty:
        return pd.DataFrame()
    out = pd.DataFrame({"data": pd.to_datetime(d[cols["data"]], errors="coerce")})
    for k in ("cota", "pl", "cotistas", "captacao", "resgate"):
        if cols[k] is not None:
            out[k] = pd.to_numeric(d[cols[k]], errors="coerce").values
    out = out.dropna(subset=["data"]).drop_duplicates("data", keep="last").set_index("data").sort_index()
    out["cota"] = out["cota"].where(out["cota"] > 0)
    return out.dropna(subset=["cota"])


def meses_necessarios(hoje: date, n: int) -> list[str]:
    """['202601', '202512', ...] do mês atual para trás (n meses). O informe do mês corrente pode não existir ainda."""
    out, a, m = [], hoje.year, hoje.month
    for _ in range(n):
        out.append(f"{a}{m:02d}")
        m -= 1
        if m == 0:
            a, m = a - 1, 12
    return out


def metricas_fundo(df: pd.DataFrame) -> dict:
    """Rentabilidade, risco e evolução do patrimônio a partir da série padronizada. Nada é preenchido: faltou = None."""
    if df is None or df.empty or len(df) < 2:
        return {"ok": False, "motivo": "sem dados suficientes"}
    cota = df["cota"]
    rent = {n: cr.cagr_periodos(cota, (n,), tol_dias=10)[n] for n in (1, 3, 5)}
    rets = cota.pct_change().dropna()
    pico = cota.cummax()
    mensal = cota.resample("ME").last().pct_change().dropna()
    m = {"ok": True, "inicio": cota.index[0], "fim": cota.index[-1], "dias": len(cota),
         "rentabilidade": rent,
         "acumulado": float(cota.iloc[-1] / cota.iloc[0] - 1),
         "vol_anual": float(rets.std() * (252 ** 0.5)) if len(rets) > 20 else None,
         "queda_max": float((cota / pico - 1).min()),
         "meses_positivos": float((mensal > 0).mean() * 100) if len(mensal) >= 3 else None,
         "n_meses": int(len(mensal))}
    for k in ("pl", "cotistas"):
        if k in df and df[k].notna().any():
            s = df[k].dropna()
            c = cr.cagr_periodos(s, (1,), tol_dias=10)[1]
            m[f"{k}_atual"] = float(s.iloc[-1])
            m[f"{k}_var12m"] = c.variacao_total if c.ok else None
        else:
            m[f"{k}_atual"], m[f"{k}_var12m"] = None, None
    if "captacao" in df and "resgate" in df and df[["captacao", "resgate"]].notna().all(axis=1).any():
        j = df[["captacao", "resgate"]].dropna().tail(252)
        m["captacao_liquida_12m"] = float((j["captacao"] - j["resgate"]).sum())
    else:
        m["captacao_liquida_12m"] = None
    return m


# =============================================================================== coleta (única parte com rede)
def _ler_zip_csv(conteudo: bytes, cnpj: str) -> pd.DataFrame:
    partes = []
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        for nome in z.namelist():
            if not nome.lower().endswith(".csv"):
                continue
            with z.open(nome) as f:
                cab = pd.read_csv(f, sep=";", encoding="latin1", dtype=str, nrows=0)
            usar = [c for c in cab.columns if c in colunas_desejadas()]
            with z.open(nome) as f:
                for pedaco in pd.read_csv(f, sep=";", encoding="latin1", dtype=str, usecols=usar, chunksize=250_000):
                    col = _achar(pedaco.columns, *CAMPOS_INFORME["cnpj"])
                    if col is None:
                        raise LayoutInesperado(f"coluna de CNPJ ausente; recebi: {', '.join(pedaco.columns)}")
                    partes.append(pedaco[pedaco[col].map(so_digitos) == so_digitos(cnpj)])
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def baixar(url: str, timeout: int = 90) -> bytes | None:
    if requests is None:
        return None
    r = requests.get(url, headers=UA, timeout=timeout)
    if r.status_code == 404:
        return None
    r.raise_for_status()
    return r.content


def informe_do_mes(cnpj: str, ym: str) -> pd.DataFrame:
    """Linhas do fundo em um mês (bruto). Tenta o arquivo mensal; se não existir, o anual (HIST). None/vazio = sem dado."""
    conteudo = baixar(URL_INF_DIARIO.format(ym=ym))
    if conteudo is None:
        conteudo = baixar(URL_INF_DIARIO_HIST.format(ano=ym[:4]))
        if conteudo is None:
            return pd.DataFrame()
        df = _ler_zip_csv(conteudo, cnpj)
        col = _achar(df.columns, *CAMPOS_INFORME["data"]) if not df.empty else None
        return df[df[col].str.startswith(f"{ym[:4]}-{ym[4:]}")] if col else df
    return _ler_zip_csv(conteudo, cnpj)


# =============================================================================== Tesouro Direto
CAMPOS_TESOURO = {"titulo": ("Tipo Titulo", "Tipo Título"), "venc": ("Data Vencimento",), "data": ("Data Base",),
                  "taxa_compra": ("Taxa Compra Manha", "Taxa Compra Manhã"), "pu": ("PU Base Manha", "PU Base Manhã")}


def _num_br(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip().replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def padronizar_tesouro(df: pd.DataFrame) -> pd.DataFrame:
    """Tabela do Tesouro Transparente → colunas titulo, venc, data, taxa_compra (% a.a.), pu. Datas dd/mm/aaaa e
    números com vírgula decimal."""
    if df is None or df.empty:
        return pd.DataFrame()
    cols = {k: _achar(df.columns, *v) for k, v in CAMPOS_TESOURO.items()}
    faltam = [k for k in ("titulo", "venc", "data", "pu") if cols[k] is None]
    if faltam:
        raise LayoutInesperado(f"colunas ausentes ({', '.join(faltam)}); recebi: {', '.join(map(str, df.columns))}")
    out = pd.DataFrame({"titulo": df[cols["titulo"]].astype(str).str.strip(),
                        "venc": pd.to_datetime(df[cols["venc"]], format="%d/%m/%Y", errors="coerce"),
                        "data": pd.to_datetime(df[cols["data"]], format="%d/%m/%Y", errors="coerce"),
                        "pu": df[cols["pu"]].map(_num_br)})
    out["taxa_compra"] = df[cols["taxa_compra"]].map(_num_br) if cols["taxa_compra"] else None
    return out.dropna(subset=["venc", "data", "pu"]).query("pu > 0")


def titulos_disponiveis(t: pd.DataFrame) -> list[tuple[str, pd.Timestamp]]:
    return sorted({(a, b) for a, b in zip(t["titulo"], t["venc"])}, key=lambda x: (x[0], x[1]))


def serie_titulo(t: pd.DataFrame, titulo: str, venc) -> pd.DataFrame:
    s = t[(t["titulo"] == titulo) & (t["venc"] == pd.Timestamp(venc))].drop_duplicates("data", keep="last")
    return s.set_index("data").sort_index()[["pu", "taxa_compra"]]


def contratado_vs_realizado(s: pd.DataFrame, anos: int = 1) -> dict:
    """Taxa de compra na data inicial (a.a., o que o título prometia) contra o retorno a.a. do PU marcado a mercado
    no mesmo período. Só são iguais se o título for levado até o vencimento: o PU oscila com os juros."""
    r = cr.cagr_periodos(s["pu"], (anos,), tol_dias=10)[anos]
    if not r.ok:
        return {"ok": False, "motivo": r.texto}
    ini = pd.Timestamp(r.inicio[0])
    taxa = s["taxa_compra"].get(ini) if "taxa_compra" in s else None
    taxa = None if taxa is None or pd.isna(taxa) else float(taxa)
    return {"ok": True, "inicio": r.inicio[0], "fim": r.fim[0], "anos": r.anos, "realizado_aa": r.valor * 100,
            "acumulado": r.variacao_total * 100, "contratada_aa": taxa}
