"""Coleta dos indicadores macro nas fontes públicas e gratuitas: Banco Central (SGS e Focus), IBGE (SIDRA), Ipeadata e FRED.

Cada coletor devolve (DataFrame com coluna 'valor' e índice de datas, meta) ou levanta FonteErro com a CAUSA em português:
código inexistente, série descontinuada, resposta vazia, formato novo, limite de consultas, tempo esgotado. É essa causa que aparece no
diagnóstico da página, para corrigir o problema real em vez de trocar códigos às cegas.

Consumo: um indicador = uma consulta por fonte, no máximo, e só quando o cache central (1 a 6 h) expirou. O resultado é compartilhado por
TODOS os usuários (e pelo monitor), nunca refeito por pessoa. Sem chave de API e sem custo.
"""
from __future__ import annotations

import csv
import io
import re
import unicodedata
from datetime import date, timedelta

import pandas as pd
import requests

import cache_central
import macro_fontes as MF
from macro_fontes import FonteErro

_UA = {"User-Agent": "Mozilla/5.0 (compatible; BussolaB3/1.0)", "Accept": "application/json"}
_TEMPO = 12


def _sem_acento(t) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")


def _get(url: str, params=None, acei_json=True):
    try:
        r = requests.get(url, params=params, headers=_UA, timeout=_TEMPO)
    except requests.exceptions.Timeout:
        raise FonteErro("tempo esgotado: a fonte não respondeu em 12 segundos")
    except requests.exceptions.RequestException as e:
        raise FonteErro(f"falha de conexão ({e.__class__.__name__})")
    if r.status_code == 200:
        return r
    causas = {400: "consulta recusada pela fonte (parâmetros ou janela de datas inválidos)", 403: "acesso negado pela fonte (403)",
              404: "endereço ou série não encontrados (404)", 429: "limite de consultas atingido (429): a fonte pede para tentar mais tarde",
              500: "erro interno da fonte (500)", 502: "fonte fora do ar (502)", 503: "fonte indisponível (503)", 504: "a fonte demorou demais (504)"}
    raise FonteErro(causas.get(r.status_code, f"resposta HTTP {r.status_code}"))


def _json(r):
    try:
        return r.json()
    except ValueError:
        raise FonteErro("a fonte respondeu em formato que não é JSON (a estrutura pode ter mudado)")


# ------------------------------------------------------------------ Banco Central: SGS
def coletar_sgs(f: dict):
    fim = date.today()
    ini = fim - timedelta(days=int(365.25 * f.get("anos", 10)))
    r = _get(f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.{f['codigo']}/dados",
             {"formato": "json", "dataInicial": f"{ini:%d/%m/%Y}", "dataFinal": f"{fim:%d/%m/%Y}"})
    dados = _json(r)
    if not isinstance(dados, list) or not dados:
        raise FonteErro("a série existe, mas não devolveu observações na janela pedida")
    df = pd.DataFrame(dados)
    if not {"data", "valor"} <= set(df.columns):
        raise FonteErro(f"formato inesperado: campos {sorted(df.columns)[:6]} em vez de data/valor")
    df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y", errors="coerce")
    df["valor"] = pd.to_numeric(df["valor"], errors="coerce")
    df = df.dropna(subset=["data", "valor"]).set_index("data").sort_index()
    if df.empty:
        raise FonteErro("todas as observações vieram sem data ou valor numérico válidos")
    return df[["valor"]], {"codigo": f"SGS {f['codigo']}"}


# ------------------------------------------------------------------ Banco Central: Focus (expectativas)
def coletar_focus(f: dict):
    ano = date.today().year + (1 if f.get("ref") == "proximo" else 0)
    filtro = f"Indicador eq '{f['indicador']}' and DataReferencia eq '{ano}' and baseCalculo eq 0"
    r = _get("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais",
             {"$top": 700, "$format": "json", "$filter": filtro, "$orderby": "Data desc", "$select": "Indicador,Data,Mediana,DataReferencia"})
    linhas = _json(r).get("value") or []
    if not linhas:
        raise FonteErro(f"a pesquisa Focus não trouxe expectativas de {f['indicador']} para {ano}")
    df = pd.DataFrame(linhas)
    if not {"Data", "Mediana"} <= set(df.columns):
        raise FonteErro("formato inesperado na pesquisa Focus")
    df["Data"] = pd.to_datetime(df["Data"], errors="coerce")
    df["Mediana"] = pd.to_numeric(df["Mediana"], errors="coerce")
    df = df.dropna().set_index("Data").sort_index().rename(columns={"Mediana": "valor"})[["valor"]]
    return df, {"codigo": f"Focus {f['indicador']} {ano}", "nome": f"Mediana das expectativas de {f['indicador']} para {ano}"}


# ------------------------------------------------------------------ FRED
def coletar_fred(f: dict):
    ini = date.today() - timedelta(days=365 * 8)
    r = _get("https://fred.stlouisfed.org/graph/fredgraph.csv", {"id": f["codigo"], "cosd": f"{ini:%Y-%m-%d}"})
    linhas = list(csv.reader(io.StringIO(r.text)))
    if len(linhas) < 3 or len(linhas[0]) < 2:
        raise FonteErro("o FRED não devolveu a tabela esperada (série inexistente ou formato novo)")
    datas, vals = [], []
    for ln in linhas[1:]:
        if len(ln) < 2 or ln[1] in (".", ""):
            continue
        try:
            datas.append(pd.Timestamp(ln[0]))
            vals.append(float(ln[1]))
        except (ValueError, TypeError):
            continue
    if not vals:
        raise FonteErro("o FRED respondeu sem observações numéricas")
    return pd.DataFrame({"valor": vals}, index=pd.DatetimeIndex(datas)).sort_index(), {"codigo": f"FRED {f['codigo']}"}


# ------------------------------------------------------------------ Ipeadata
_IPEA = "https://www.ipeadata.gov.br/api/odata4"


def _meta_ipea(codigo: str):
    r = _get(f"{_IPEA}/Metadados", {"$filter": f"SERCODIGO eq '{codigo}'", "$select": "SERCODIGO,SERNOME,SERSTATUS,PERNOME,UNINOME"})
    return (_json(r).get("value") or [None])[0]


def _valores_ipea(codigo: str):
    r = _get(f"{_IPEA}/ValoresSerie(SERCODIGO='{codigo}')")
    dados = _json(r).get("value") or []
    if not dados:
        try:
            m = _meta_ipea(codigo)
        except FonteErro:
            m = "?"
        if m is None:
            raise FonteErro("código inexistente no catálogo do Ipeadata")
        if m != "?" and str(m.get("SERSTATUS", "A")).upper() != "A":
            raise FonteErro(f"série descontinuada no Ipeadata ({m.get('SERNOME', '')[:70]})")
        raise FonteErro("o código existe, mas a série não tem observações publicadas")
    df = pd.DataFrame(dados)
    cd = next((c for c in ("VALDATA", "Data") if c in df.columns), None)
    cv = next((c for c in ("VALVALOR", "Valor") if c in df.columns), None)
    if not (cd and cv):
        raise FonteErro(f"formato inesperado: campos {sorted(df.columns)[:6]}")
    df[cd] = pd.to_datetime(df[cd], errors="coerce", utc=True).dt.tz_localize(None)
    df[cv] = pd.to_numeric(df[cv], errors="coerce")
    df = df.dropna(subset=[cd, cv]).set_index(cd).sort_index()
    if df.empty:
        raise FonteErro("as observações vieram sem data ou valor numérico válidos")
    return df[[cv]].rename(columns={cv: "valor"})


def coletar_ipea(f: dict):
    return _valores_ipea(f["codigo"]), {"codigo": f"Ipeadata {f['codigo']}"}


def escolher_serie_ipea(candidatas: list, termos: list, preferir: list, evitar: list):
    """Pontua as séries do catálogo do Ipeadata pelo NOME (puro, testável). Só séries ativas e mensais."""
    melhor, pontos = None, 0.0
    for c in candidatas:
        nome = _sem_acento(c.get("SERNOME", ""))
        if str(c.get("SERSTATUS", "A")).upper() != "A" or not all(_sem_acento(t) in nome for t in termos):
            continue
        p = 1.0 + (1.0 if _sem_acento(c.get("PERNOME", "")).startswith("mensal") else -2.0)
        p += sum(2.0 for k in preferir if _sem_acento(k) in nome) - sum(4.0 for k in evitar if _sem_acento(k) in nome)
        p -= len(nome) / 400                                   # a igualdade favorece o nome mais curto (mais genérico)
        if p > pontos:
            melhor, pontos = c, p
    return melhor


def coletar_ipea_busca(f: dict):
    r = _get(f"{_IPEA}/Metadados", {"$filter": f"contains(SERNOME,'{f['termos'][0]}')", "$select": "SERCODIGO,SERNOME,SERSTATUS,PERNOME,UNINOME", "$top": 200})
    cand = _json(r).get("value") or []
    if not cand:
        raise FonteErro(f"nenhuma série do Ipeadata contém '{f['termos'][0]}' no nome")
    c = escolher_serie_ipea(cand, f["termos"], f["preferir"], f["evitar"])
    if not c:
        raise FonteErro(f"{len(cand)} séries encontradas, nenhuma ativa e mensal que combine com o pedido")
    return _valores_ipea(c["SERCODIGO"]), {"codigo": f"Ipeadata {c['SERCODIGO']}", "nome": c.get("SERNOME", "")}


# ------------------------------------------------------------------ IBGE: SIDRA
def interpretar_sidra(linhas: list, incl: list, excl: list, freq: str):
    """Transforma a resposta da SIDRA (1ª linha = descrição das colunas) em série. Escolhe a variável/classificação pelo NOME,
    não por número, para não quebrar quando o IBGE renumera. Puro e testável."""
    if len(linhas) < 2:
        raise FonteErro("a SIDRA respondeu sem dados para esta tabela e período")
    cab = linhas[0]
    dims = [k[:-1] for k in cab if re.fullmatch(r"D\d+N", k)]
    per = next((d for d in dims if re.match(r"(m[eê]s|trimestre|ano)", _sem_acento(cab[d + "N"]))), None)
    if per is None:
        raise FonteErro("formato inesperado: a SIDRA não trouxe a coluna de período")
    movel = "movel" in _sem_acento(cab[per + "N"])
    trim = _sem_acento(cab[per + "N"]).startswith("trimestre") and not movel
    grupos: dict = {}
    for ln in linhas[1:]:
        desc = " | ".join(str(ln.get(d + "N", "")) for d in dims if d != per)
        cod = str(ln.get(per + "C", ""))
        try:
            v = float(str(ln.get("V", "")).replace(",", "."))
        except ValueError:
            continue
        try:
            if trim:
                ano, q = int(cod[:4]), int(cod[4:6])
                data = pd.Timestamp(year=ano, month=(q - 1) * 3 + 1, day=1)
            else:
                data = pd.Timestamp(year=int(cod[:4]), month=int(cod[4:6]), day=1)
        except (ValueError, TypeError):
            continue
        grupos.setdefault(desc, {})[data] = v
    if not grupos:
        raise FonteErro("a SIDRA respondeu, mas sem valores numéricos")
    ok = [d for d in grupos if all(_sem_acento(i) in _sem_acento(d) for i in incl) and not any(_sem_acento(x) in _sem_acento(d) for x in excl)]
    if not ok:
        amostra = "; ".join(sorted(grupos)[:5])
        raise FonteErro(f"nenhuma variável combina com {incl}. Disponíveis: {amostra}")
    escolhida = min(ok, key=len)
    s = pd.Series(grupos[escolhida]).sort_index()
    return pd.DataFrame({"valor": s}), {"codigo": "IBGE SIDRA", "nome": escolhida}


def coletar_sidra(f: dict):
    caminho = f"/values/t/{f['tabela']}/n1/all/v/all/p/last%20{f['periodos']}" + (f"/{f['classif']}" if f.get("classif") else "")
    r = _get("https://apisidra.ibge.gov.br" + caminho)
    linhas = _json(r)
    if not isinstance(linhas, list):
        raise FonteErro("formato inesperado na resposta da SIDRA")
    df, meta = interpretar_sidra(linhas, f["incl"], f["excl"], "mensal")
    meta["codigo"] = f"SIDRA tabela {f['tabela']}"
    return df, meta


def buscadores_padrao() -> dict:
    return {"sgs": coletar_sgs, "ipea": coletar_ipea, "ipea_busca": coletar_ipea_busca, "sidra": coletar_sidra, "fred": coletar_fred, "focus": coletar_focus}


# ------------------------------------------------------------------ com cache central (compartilhado entre usuários e monitor)
def _bom(r) -> bool:
    return bool(r) and r.get("status") != "indisponivel"


@cache_central.dados(ttl=3 * 3600, ok=_bom, nome="macro.indicador")
def indicador(ind_id: str) -> dict:
    """Um indicador resolvido pela cadeia de fontes. Sucesso fica 3 h no cache; falha, só 2 min (para tentar de novo logo)."""
    return MF.resolver(ind_id, buscadores_padrao())
