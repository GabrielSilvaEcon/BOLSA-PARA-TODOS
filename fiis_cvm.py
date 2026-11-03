"""
Informe mensal de FIIs da CVM (dados abertos): patrimônio líquido, valor patrimonial por cota, nº de cotas e de cotistas,
rentabilidade/DY do mês e passivo. Dá o HISTÓRICO que o Fundamentus (só o dia de hoje) e o Yahoo não têm.

Parte pura (padronizar/derivar) não usa rede. A coleta lê o zip anual da CVM com detecção de colunas: se o layout mudar,
levanta LayoutInesperado com as colunas recebidas, e a tela explica em vez de mostrar número errado.
Vacância, receita imobiliária, inquilinos e carteira de CRIs NÃO estão neste arquivo (estão nos relatórios gerenciais).
"""
from __future__ import annotations

import io
import re
import unicodedata
import zipfile

import pandas as pd

import crescimento as cr
from fundos import baixar, cnpj_valido, formatar_cnpj, so_digitos   # reutiliza download e validação de CNPJ

URL_INF_MENSAL = "https://dados.cvm.gov.br/dados/FII/DOC/INF_MENSAL/DADOS/inf_mensal_fii_{ano}.zip"


class LayoutInesperado(Exception):
    pass


def _chave(s) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _achar(colunas, *cands):
    mapa = {_chave(c): c for c in colunas}
    for c in cands:
        if _chave(c) in mapa:
            return mapa[_chave(c)]
    return None


CAMPOS = {
    "cnpj": ("CNPJ_Fundo_Classe", "CNPJ_Fundo", "CNPJ Fundo"),
    "data": ("Data_Referencia", "Data Referencia", "DT_COMPTC"),
    "versao": ("Versao", "Versão"),
    "nome": ("Nome_Fundo_Classe", "Nome_Fundo", "Nome Fundo"),
    "segmento": ("Segmento_Atuacao", "Segmento Atuacao"),
    "isin": ("Codigo_ISIN", "ISIN"),
    "pl": ("Patrimonio_Liquido", "Patrimonio Liquido"),
    "vp_cota": ("Valor_Patrimonial_Cotas", "Valor_Patrimonial_Cota", "Valor Patrimonial Cotas"),
    "cotas": ("Cotas_Emitidas", "Total_Numero_Cotas_Emitidas", "Numero_Cotas_Emitidas"),
    "cotistas": ("Total_Numero_Cotistas", "Numero_Cotistas", "Total Numero Cotistas"),
    "dy_mes": ("Percentual_Dividend_Yield_Mes", "Dividend_Yield_Mes"),
    "rent_efetiva": ("Percentual_Rentabilidade_Efetiva_Mes", "Rentabilidade_Efetiva_Mes"),
    "rent_patrim": ("Percentual_Rentabilidade_Patrimonial_Mes", "Rentabilidade_Patrimonial_Mes"),
    "passivo": ("Total_Passivo", "Passivo_Total", "Total Passivo"),
    "ativo": ("Total_Ativo", "Ativo_Total", "Total Ativo", "Ativo"),
}
ESSENCIAIS_DADOS = ("pl", "vp_cota")


def _num(x):
    if x is None or (isinstance(x, float) and pd.isna(x)):
        return None
    s = str(x).strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        v = float(s)
    except ValueError:
        return None
    return v if pd.notna(v) and abs(v) != float("inf") else None


def _ler_csv(conteudo: bytes) -> pd.DataFrame:
    for enc in ("utf-8", "latin1"):
        try:
            return pd.read_csv(io.BytesIO(conteudo), sep=";", encoding=enc, dtype=str)
        except UnicodeDecodeError:
            continue
    raise LayoutInesperado("não foi possível ler o CSV (codificação desconhecida)")


def ler_zip(conteudo: bytes) -> dict[str, pd.DataFrame]:
    """{'geral'|'complemento'|'ativo_passivo': df} do zip anual. Arquivos fora desse padrão são ignorados."""
    out = {}
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        for nome in z.namelist():
            n = nome.lower()
            if not n.endswith(".csv"):
                continue
            tipo = "ativo_passivo" if "ativo_passivo" in n else "complemento" if "complemento" in n else "geral" if "geral" in n else None
            if tipo:
                out[tipo] = _ler_csv(z.read(nome))
    if not out:
        raise LayoutInesperado("o zip não contém os arquivos esperados (geral, complemento, ativo_passivo)")
    return out


def _versao_final(df: pd.DataFrame, c_cnpj, c_data, c_ver) -> pd.DataFrame:
    """Mantém só a última versão (reapresentação) de cada fundo e data."""
    if c_ver is None:
        return df.drop_duplicates([c_cnpj, c_data], keep="last")
    d = df.copy()
    d["_v"] = pd.to_numeric(d[c_ver], errors="coerce").fillna(0)
    return d.sort_values("_v").drop_duplicates([c_cnpj, c_data], keep="last").drop(columns="_v")


def padronizar(tabelas: dict[str, pd.DataFrame], cnpj: str) -> pd.DataFrame:
    """Série mensal do fundo (índice = data de referência). Colunas: pl, vp_cota, cotas, cotistas, dy_mes, rent_efetiva,
    rent_patrim, passivo, ativo, alavancagem. Falta de coluna opcional deixa a coluna ausente; falta de essencial levanta."""
    alvo = so_digitos(cnpj)
    partes = []
    visto = {}
    for tipo, df in tabelas.items():
        if df is None or df.empty:
            continue
        c_cnpj, c_data, c_ver = (_achar(df.columns, *CAMPOS[k]) for k in ("cnpj", "data", "versao"))
        if c_cnpj is None or c_data is None:
            raise LayoutInesperado(f"arquivo '{tipo}' sem coluna de CNPJ/data; recebi: {', '.join(map(str, df.columns))}")
        d = df[df[c_cnpj].map(so_digitos) == alvo]
        if d.empty:
            continue
        d = _versao_final(d, c_cnpj, c_data, c_ver)
        idx = pd.to_datetime(d[c_data], errors="coerce")
        res = pd.DataFrame(index=idx)
        for k in ("pl", "vp_cota", "cotas", "cotistas", "dy_mes", "rent_efetiva", "rent_patrim", "passivo", "ativo"):
            col = _achar(d.columns, *CAMPOS[k])
            if col is not None and k not in visto:
                res[k] = d[col].map(_num).to_numpy()
                visto[k] = col
        if res.shape[1]:
            partes.append(res[~res.index.isna()])
    if not partes:
        return pd.DataFrame()
    out = pd.concat(partes, axis=1)
    out = out.loc[:, ~out.columns.duplicated()].sort_index()
    out = out[~out.index.duplicated(keep="last")]
    faltam = [k for k in ESSENCIAIS_DADOS if k not in out.columns]
    if faltam:
        raise LayoutInesperado("colunas essenciais ausentes (" + ", ".join(faltam) + "); recebi: "
                               + ", ".join(sorted({c for t in tabelas.values() for c in t.columns})[:30]))
    if "passivo" in out and "pl" in out:
        out["alavancagem"] = (out["passivo"] / out["pl"]).where(out["pl"] > 0)
    return out


def validar(df: pd.DataFrame, tol: float = 0.03) -> list[str]:
    """Consistência: PL ≈ VP/cota × nº de cotas (±3%). Devolve avisos; vazio = coerente."""
    avisos = []
    if df is None or df.empty or not {"pl", "vp_cota", "cotas"} <= set(df.columns):
        return avisos
    d = df.dropna(subset=["pl", "vp_cota", "cotas"])
    d = d[(d["pl"] > 0) & (d["vp_cota"] > 0) & (d["cotas"] > 0)]
    if d.empty:
        return avisos
    desvio = (d["vp_cota"] * d["cotas"] / d["pl"] - 1).abs()
    ruins = desvio[desvio > tol]
    if len(ruins):
        avisos.append(f"{len(ruins)} de {len(d)} meses têm patrimônio ≠ valor por cota × cotas (mais de {tol * 100:.0f}% de "
                      f"diferença): confira o informe original. Último mês incoerente: {ruins.index[-1]:%m/%Y}.")
    if (df["pl"].dropna() < 0).any():
        avisos.append("Há mês com patrimônio líquido negativo na fonte.")
    return avisos


def pontos_anuais(s: pd.Series, tol_dias: int = 20) -> pd.Series:
    """De uma série mensal, pega o último mês e o mesmo mês de cada ano anterior (comparação igual com igual). Resultado em
    frequência anual, que o motor de CAGR do passo 7 aceita. Mês faltando no ano: o ano fica de fora (sem estimar)."""
    s = cr.serie_limpa(s)
    if s.empty:
        return s
    fim = s.index[-1]
    pts = {fim: s.iloc[-1]}
    k = 1
    while True:
        alvo = fim - pd.DateOffset(years=k)
        if alvo < s.index[0] - pd.Timedelta(days=tol_dias):
            break
        dist = abs((s.index - alvo).days)
        i = int(dist.argmin())
        if dist[i] <= tol_dias:
            pts[s.index[i]] = s.iloc[i]
        k += 1
    return pd.Series(pts).sort_index()


def cagr_mensal(s: pd.Series, periodos=(1, 3, 5)) -> dict:
    return cr.cagr_periodos(pontos_anuais(s), periodos)


def serie_anual(s: pd.Series, como: str = "ultimo") -> pd.Series:
    """Mensal → anual por 'ultimo' (estoque: PL, cotistas) ou 'soma' (fluxo: DY do mês somado ≈ DY do ano, aproximado)."""
    s = cr.serie_limpa(s)
    if s.empty:
        return s
    g = s.groupby(s.index.year)
    r = g.last() if como == "ultimo" else g.sum(min_count=1)
    n = g.size()
    r = r[n >= (12 if como == "soma" else 1)] if como == "soma" else r
    r.index = pd.to_datetime([f"{a}-12-31" for a in r.index])
    return r


def pvp_historico(precos: pd.Series, vp_cota: pd.Series) -> pd.Series:
    """P/VP ao fim de cada mês = último preço do mês ÷ VP/cota do mês (informado pelo fundo depois do fechamento)."""
    p, v = cr.serie_limpa(precos), cr.serie_limpa(vp_cota)
    if p.empty or v.empty:
        return pd.Series(dtype=float)
    pm = p.groupby(p.index.to_period("M")).last()
    vm = v.groupby(v.index.to_period("M")).last()
    r = (pm / vm).dropna()
    r = r[vm.reindex(r.index) > 0]
    r.index = r.index.to_timestamp(how="end").normalize()
    return r


def buscar_por_nome(geral: pd.DataFrame, texto: str, limite: int = 15) -> list[tuple[str, str]]:
    """Fundos cujo nome contém o texto (para o usuário escolher o CNPJ quando o ticker não casa sozinho)."""
    if geral is None or geral.empty or not texto or len(texto.strip()) < 3:
        return []
    c_n, c_c = _achar(geral.columns, *CAMPOS["nome"]), _achar(geral.columns, *CAMPOS["cnpj"])
    if c_n is None or c_c is None:
        return []
    alvo = _chave(texto)
    d = geral[[c_c, c_n]].drop_duplicates(c_c)
    ach = d[d[c_n].map(_chave).str.contains(alvo, regex=False)]
    return [(formatar_cnpj(r[c_c]), str(r[c_n])) for _, r in ach.head(limite).iterrows()]


def cnpj_por_isin(geral: pd.DataFrame, isin_prefixo: str) -> str | None:
    """Casa por ISIN se o arquivo trouxer a coluna (BRXXXXCTF...). None se não houver coluna ou se houver ambiguidade."""
    if geral is None or geral.empty:
        return None
    c_i, c_c = _achar(geral.columns, *CAMPOS["isin"]), _achar(geral.columns, *CAMPOS["cnpj"])
    if c_i is None or c_c is None or not isin_prefixo:
        return None
    ach = geral[geral[c_i].fillna("").str.upper().str.startswith(isin_prefixo.upper())][c_c].dropna().unique()
    return formatar_cnpj(ach[0]) if len(ach) == 1 else None


# =============================================================================== coleta (rede)
def coletar_anos(anos: list[int]) -> dict[int, dict[str, pd.DataFrame]]:
    out = {}
    for a in anos:
        c = baixar(URL_INF_MENSAL.format(ano=a))
        if c is not None:
            out[a] = ler_zip(c)
    return out


def juntar_anos(por_ano: dict[int, dict[str, pd.DataFrame]]) -> dict[str, pd.DataFrame]:
    tipos = {t for d in por_ano.values() for t in d}
    return {t: pd.concat([d[t] for d in por_ano.values() if t in d], ignore_index=True) for t in tipos}
