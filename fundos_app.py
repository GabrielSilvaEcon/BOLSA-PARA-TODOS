"""
ETFs e fundos de investimento (Passo 10): coleta de dados reais e páginas com 10 abas.

Os cálculos ficam em fundos_analise.py (puro e testado). Aqui há só coleta (Yahoo Finance, CVM, Banco Central) e tela.
Fontes: ETFs → Yahoo Finance (preço, volume, proventos, taxa, patrimônio e carteira quando a fonte entrega);
fundos → CVM (cadastro, informe diário e carteira CDA); referências → Banco Central (CDI, IPCA) e índices do Yahoo.
Nada é estimado: o que a fonte não entrega aparece como "n/d" com o motivo.
"""
from __future__ import annotations

import io
import math
import re
import zipfile
from datetime import date

import pandas as pd
import streamlit as st

import profundidade_app

import cache_central

import comparador
import crescimento as cr
import evolucao
import fundos as fd
import fundos_analise as fa
import moeda
import tema

URL_CAD = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/cad_fi.csv"
URL_REGISTRO = "https://dados.cvm.gov.br/dados/FI/CAD/DADOS/registro_fundo_classe.zip"
URL_CDA = "https://dados.cvm.gov.br/dados/FI/DOC/CDA/DADOS/cda_fi_{ym}.zip"
URL_EXTRATO = "https://dados.cvm.gov.br/dados/FI/DOC/EXTRATO/DADOS/extrato_fi.csv"
URL_LAMINA = "https://dados.cvm.gov.br/dados/FI/DOC/LAMINA/DADOS/lamina_fi_{ym}.zip"
FUNDOS = {
    "acoes": ("📊", "Fundos de Ações", "Fundos de ações: rentabilidade contra o Ibovespa, taxas, patrimônio, cotistas, risco e carteira (CVM)."),
    "multi": ("🎛️", "Multimercados", "Multimercados: rentabilidade contra o CDI, volatilidade, Sharpe, taxas e consistência (CVM)."),
    "rf": ("💵", "Fundos de Renda Fixa", "Fundos de renda fixa: rentabilidade contra o CDI e a inflação, taxas, risco de crédito e carteira (CVM)."),
}
CHAVES_CLASSE = {"acoes": {"acoes"}, "multi": {"multimercado"}, "rf": {"renda_fixa", "referenciado_di"}}
ETFS_POPULARES = ["BOVA11", "IVVB11", "VOO", "QQQ", "SCHD", "IMAB11"]
NOTA_LEGAL = ("Ferramenta educacional, não é recomendação de investimento. " + fa.AVISO_PASSADO)
FILTROS_CLASSE = {"acoes": ("acoes", "acao"), "multi": ("multimercado",), "rf": ("renda fixa", "referenciado")}
ABAS = ["Visão geral", "Indicadores", "Estratégia", "Composição", "Rentabilidade", "Risco", "Custos", "Histórico",
        "Comparação", "Análise inteligente"]


# =============================================================================== formatação
def _p(v, d: int = 1, sinal: bool = True) -> str:
    """Fração → '12,3%'. None = 'n/d'."""
    if v is None or not fa._ok(v):
        return "n/d"
    return (f"{v * 100:+.{d}f}%" if sinal else f"{v * 100:.{d}f}%").replace(".", ",")


def _pp(v, d: int = 2) -> str:
    """Número já em % ('0,35')."""
    return "n/d" if v is None or not fa._ok(v) else f"{v:.{d}f}%".replace(".", ",")


def _num(v, d: int = 2) -> str:
    return "n/d" if v is None or not fa._ok(v) else f"{v:.{d}f}".replace(".", ",")


def _grande(v, moeda: str = "BRL") -> str:
    if v is None or not fa._ok(v):
        return "n/d"
    pre = "US$ " if moeda == "USD" else "R$ "
    for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return pre + f"{v / lim:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + suf
    return pre + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _data(d) -> str:
    try:
        return pd.Timestamp(d).strftime("%d/%m/%Y")
    except Exception:
        return "n/d"


def _cartoes(itens: list, por_linha: int = 4):
    for k in range(0, len(itens), por_linha):
        for col, (rot, val, cls, *det) in zip(st.columns(por_linha), itens[k:k + por_linha]):
            col.markdown(tema.card_status(rot, val, cls, det[0] if det else "", det[1] if len(det) > 1 else ""),
                         unsafe_allow_html=True)


def _cls_ret(v):
    return "na" if v is None else ("good" if v > 0 else "bad")


def _ticker_yahoo(t: str) -> str:
    """ETFs da B3 (BOVA11…) precisam do sufixo .SA; os americanos (VOO…) não."""
    t = (t or "").strip().upper().replace(" ", "")
    return t + ".SA" if re.fullmatch(r"[A-Z]{4}\d{1,2}", t) else t


# =============================================================================== coleta: referências
@st.cache_data(ttl=12 * 3600, show_spinner=False)
def _bcb() -> dict:
    return evolucao.coletar_bcb()


@cache_central.dados(ttl=3600)
def _serie_yahoo(simbolo: str) -> pd.Series:
    """Fechamento diário de um símbolo do Yahoo (índice, câmbio). Vazio se falhar."""
    try:
        import yfinance as yf
        h = yf.Ticker(simbolo).history(period="max", auto_adjust=False)
        return fa.serie(h["Close"]) if h is not None and not h.empty else pd.Series(dtype=float)
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=12 * 3600, show_spinner=False)
def _rf_usd() -> pd.Series:
    """Taxa livre de risco em dólar: índice acumulado a partir do T-bill de 13 semanas (^IRX, % a.a.)."""
    try:
        import yfinance as yf
        h = yf.Ticker("^IRX").history(period="max", auto_adjust=False)
        y = cr.serie_limpa(h["Close"]) if h is not None and not h.empty else pd.Series(dtype=float)
        y = y[y >= 0]
        return ((1 + y / 100) ** (1 / 252)).cumprod() * 100 if len(y) else pd.Series(dtype=float)
    except Exception:
        return pd.Series(dtype=float)


def _serie_referencia(chave: str | None, bcb: dict) -> tuple[pd.Series | None, str]:
    """Série do índice de referência pela chave (cdi, ibov, ipca, dolar, sp500). (None, motivo) se não houver."""
    if chave == "cdi":
        s = bcb.get("cdi_idx")
        return (s, "") if s is not None and len(s) else (None, "CDI indisponível agora")
    if chave == "ipca":
        s = bcb.get("ipca_idx")
        return (s, "") if s is not None and len(s) else (None, "IPCA indisponível agora")
    if chave == "ibov":
        s = _serie_yahoo("^BVSP")
        return (s, "") if len(s) else (None, "Ibovespa indisponível agora")
    if chave == "dolar":
        s = _serie_yahoo("BRL=X")
        return (s, "") if len(s) else (None, "Dólar indisponível agora")
    if chave == "sp500":
        a, b = _serie_yahoo("^GSPC"), _serie_yahoo("BRL=X")
        if len(a) and len(b):
            j = pd.concat([a, b.reindex(a.index.union(b.index)).ffill().reindex(a.index)], axis=1).dropna()
            return (j.iloc[:, 0] * j.iloc[:, 1]), ""
        return None, "S&P 500 indisponível agora"
    return None, "sem benchmark"


# =============================================================================== coleta: ETFs (Yahoo Finance)
@cache_central.dados(ttl=3600)
def _coleta_etf(simbolo: str) -> dict:
    out = {"hist": pd.DataFrame(), "info": {}, "holdings": None, "setores": None, "classes": None, "avisos": []}
    try:
        import yfinance as yf
        t = yf.Ticker(simbolo)
    except Exception:
        out["avisos"].append("Yahoo Finance indisponível.")
        return out
    try:
        h = t.history(period="max", auto_adjust=False)
        if h is not None and not h.empty:
            h = h.copy()
            h.index = pd.DatetimeIndex(h.index).tz_localize(None) if getattr(h.index, "tz", None) is not None else h.index
            out["hist"] = h
    except Exception as e:
        out["avisos"].append(f"Histórico de preços indisponível ({e.__class__.__name__}).")
    try:
        inf = t.info or {}
        chaves = ("longName", "shortName", "category", "fundFamily", "totalAssets", "netExpenseRatio",
                  "annualReportExpenseRatio", "yield", "currency", "quoteType", "legalType", "longBusinessSummary",
                  "navPrice", "averageVolume", "fundInceptionDate")
        out["info"] = {k: inf.get(k) for k in chaves if inf.get(k) is not None}
    except Exception:
        out["avisos"].append("Dados cadastrais do ETF indisponíveis na fonte.")
    try:
        fdta = t.funds_data
        try:
            th = fdta.top_holdings
            if th is not None and len(th):
                nomes = th["Name"] if "Name" in th else pd.Series(th.index, index=th.index)
                pct = th["Holding Percent"] if "Holding Percent" in th else th.iloc[:, -1]
                out["holdings"] = [{"simbolo": str(i), "nome": str(nomes.get(i, i)), "peso": float(pct[i]) * 100}
                                   for i in th.index if pd.notna(pct[i])]
        except Exception:
            pass
        try:
            sw = fdta.sector_weightings
            if sw:
                out["setores"] = {str(k): float(v) * 100 for k, v in dict(sw).items() if v is not None}
        except Exception:
            pass
        try:
            ac = fdta.asset_classes
            if ac:
                out["classes"] = {str(k): float(v) * 100 for k, v in dict(ac).items() if v is not None}
        except Exception:
            pass
    except Exception:
        pass
    return out


def _taxa_do_yahoo(info: dict) -> float | None:
    """Taxa de administração (% a.a.) do Yahoo: netExpenseRatio já vem em %, annualReportExpenseRatio em fração."""
    v = info.get("netExpenseRatio")
    if fa._ok(v) and 0 < v < 5:
        return float(v)
    v = info.get("annualReportExpenseRatio")
    if fa._ok(v) and 0 < v < 0.05:
        return float(v) * 100
    return None


VERSAO = "10.8"


def preparar_etf(tk: str) -> dict:
    """Dicionário pronto para fa.analisar_tudo, com tudo que a fonte entregou e os avisos do que faltou."""
    tk = (tk or "").strip().upper().replace(".SA", "")
    sym = _ticker_yahoo(tk)
    c = _coleta_etf(sym)
    h, info = c["hist"], c["info"]
    fx = {"tipo": "etf", "id": tk, "nome": info.get("longName") or info.get("shortName") or tk, "avisos": list(c["avisos"]),
          "fonte": "Yahoo Finance", "erro": None}
    if h.empty or len(h) < 30:
        fx["erro"] = "sem histórico de preços suficiente no Yahoo Finance"
        return fx
    close, limpeza = fa.limpar_serie(h["Close"])
    adj = fa.serie(h["Adj Close"]).reindex(close.index).dropna() if "Adj Close" in h else close
    if limpeza["aviso"]:
        fx["avisos"].append(limpeza["aviso"])
    fx["limpeza"] = limpeza
    vol = cr.serie_limpa(h["Volume"]) if "Volume" in h else None
    divs = fa.serie_proventos(h["Dividends"]) if "Dividends" in h else None
    if limpeza["cortada"]:
        vol = vol[vol.index >= limpeza["inicio"]] if vol is not None else None
        divs = divs[divs.index >= limpeza["inicio"]] if divs is not None else None
    fx.update(serie=adj, preco=close, serie_tracking=close, volume=vol,
              dividendos=divs,
              moeda=info.get("currency") or ("BRL" if sym.endswith(".SA") else "USD"), data_ref=close.index[-1].date().isoformat(),
              info=info)
    fx["rotulos"] = fa.classificar_etf(tk, fx["nome"], info.get("category") or "")
    fx["categoria"] = fa.categoria_principal(fx["rotulos"]) if fx["rotulos"] else "outros"
    fx["distribuicao"] = fa.politica_distribuicao(fx["dividendos"])
    ref = fa.indice_de_referencia(tk)
    fx["indice"] = ref
    bcb = _bcb()
    fx["cdi_idx"], fx["ipca_idx"] = bcb.get("cdi_idx"), bcb.get("ipca_idx")
    fx["rf_idx"] = fx["cdi_idx"] if fx["moeda"] == "BRL" else _rf_usd()
    fx["rf_nome"] = "CDI" if fx["moeda"] == "BRL" else "T-bill de 13 semanas (^IRX)"
    fx["ref"], fx["ref_nome"], fx["ref_freq"], fx["ref_tipo"] = None, ref["nome"], "D", "preço"
    if ref.get("yahoo_tr"):
        # ETF que distribui dividendos: compara retorno total do ETF com o índice de RETORNO TOTAL (dividendos reinvestidos).
        # Preço contra índice de preço erra no dia da data-com do ETF (o preço cai pelo dividendo, o índice não).
        rtr = _serie_yahoo(ref["yahoo_tr"])
        if len(rtr) >= 250 and (adj.index[-1] - rtr.index[-1]).days <= 10:
            fx["ref"], fx["serie_tracking"], fx["ref_tipo"] = rtr, adj, "retorno total"
            fx["ref_nome"] = f"{ref['nome']} (retorno total)"
    if fx["ref"] is None and ref["yahoo"]:
        r = _serie_yahoo(ref["yahoo"])
        if len(r):
            if ref["em_reais"]:
                fx_ = _serie_yahoo("BRL=X")
                if len(fx_):
                    j = pd.concat([r, fx_.reindex(r.index.union(fx_.index)).ffill().reindex(r.index)], axis=1).dropna()
                    r = j.iloc[:, 0] * j.iloc[:, 1]
                    fx["ref_freq"] = "W"
                else:
                    r = pd.Series(dtype=float)
            elif fx["moeda"] == "BRL" and ref["yahoo"] not in ("^BVSP",):
                fx["ref_freq"] = "W"
            fx["ref"] = r if len(r) else None
        if fx["ref"] is None:
            fx["avisos"].append(f"Série do índice de referência ({ref['nome']}) indisponível agora: tracking não calculado.")
    elif fx["ref"] is not None:
        pass
    elif ref["nome"]:
        fx["avisos"].append(f"Índice de referência: {ref['nome']}. Não há série gratuita deste índice no app, então tracking "
                            "error e tracking difference ficam sem cálculo.")
    else:
        fx["avisos"].append("Índice de referência desconhecido (ETF fora da lista do app): consulte o regulamento.")
    taxa = _taxa_do_yahoo(info)
    manual = st.session_state.get(f"fa_taxa_{tk}")
    custos = {"taxa_adm": taxa, "taxa_perf": None, "fonte": "Yahoo Finance" if taxa is not None else "sem dado na fonte"}
    if manual:
        custos.update(taxa_adm=float(manual), fonte="informada por você")
    fx["custos"] = custos
    pl = info.get("totalAssets")
    fx["pl"] = float(pl) if fa._ok(pl) else None
    fx["pl_texto"] = _grande(fx["pl"], fx["moeda"]) if fx["pl"] else None
    if c["holdings"]:
        fx["pesos"] = {x["simbolo"]: x["peso"] for x in c["holdings"]}
        fx["nomes_pos"] = {x["simbolo"]: x["nome"] for x in c["holdings"]}
    fx["setores"], fx["classes_ativo"] = c["setores"], c["classes"]
    fx["estrategia"] = None
    if not fx.get("pesos"):
        pass      # sem a carteira divulgada, as partes de composição simplesmente ficam sem dados (o aviso em texto saiu da tela)
    return fx


# =============================================================================== coleta: fundos (CVM)
def _colunas_cadastro(cab) -> list:
    quer = {"CNPJ_FUNDO", "CNPJ_Classe", "CNPJ_FUNDO_CLASSE", "DENOM_SOCIAL", "Denominacao_Social", "CLASSE", "Tipo_Classe",
            "Classificacao", "CLASSE_ANBIMA", "Classificacao_Anbima", "SIT", "Situacao", "RENTAB_FUNDO", "Indicador_Desempenho",
            "TAXA_ADM", "Taxa_Administracao", "TAXA_PERFM", "Taxa_Performance", "PUBLICO_ALVO", "Publico_Alvo", "CONDOM",
            "Forma_Condominio", "FUNDO_EXCLUSIVO", "Exclusivo", "FUNDO_COTAS", "GESTOR", "Gestor", "ADMIN", "Administrador",
            "VL_PATRIM_LIQ", "Patrimonio_Liquido", "DT_PATRIM_LIQ", "Data_Patrimonio_Liquido"}
    return [c for c in cab if c in quer]


def _ler_cad_fi() -> pd.DataFrame:
    """Cadastro ANTIGO (cad_fi.csv). Desde a Resolução CVM 175 os fundos adaptados saem dele ou aparecem como CANCELADA;
    serve só para fundos ainda não adaptados e como fonte de taxas antigas. Lê tudo (inclusive cancelados)."""
    conteudo = fd.baixar(URL_CAD, timeout=120)
    if conteudo is None:
        return pd.DataFrame()
    cab = pd.read_csv(io.BytesIO(conteudo), sep=";", encoding="latin1", dtype=str, nrows=0)
    return pd.read_csv(io.BytesIO(conteudo), sep=";", encoding="latin1", dtype=str, usecols=_colunas_cadastro(cab.columns),
                       quoting=3, on_bad_lines="skip")   # quoting=3: aspas soltas em campos de texto não "engolem" o arquivo


def _ler_registro() -> pd.DataFrame:
    """Cadastro NOVO (registro_fundo_classe.zip, Resolução CVM 175): uma linha por CLASSE (o CNPJ que aparece no informe
    diário), com gestor e administrador vindos do registro do fundo."""
    conteudo = fd.baixar(URL_REGISTRO, timeout=120)
    if conteudo is None:
        return pd.DataFrame()
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        nomes = {n.lower(): n for n in z.namelist()}
        n_cls = next((n for k, n in nomes.items() if "registro_classe" in k and k.endswith(".csv")), None)
        n_fun = next((n for k, n in nomes.items() if "registro_fundo" in k and "classe" not in k and k.endswith(".csv")), None)
        if not n_cls:
            return pd.DataFrame()
        with z.open(n_cls) as f:
            cls = pd.read_csv(f, sep=";", encoding="latin1", dtype=str, quoting=3, on_bad_lines="skip")
        fun = None
        if n_fun:
            with z.open(n_fun) as f:
                fun = pd.read_csv(f, sep=";", encoding="latin1", dtype=str, quoting=3, on_bad_lines="skip")
    cols = _colunas_cadastro(cls.columns)
    id_f = fd._achar(cls.columns, "ID_Registro_Fundo")
    if fun is not None and id_f and fd._achar(fun.columns, "ID_Registro_Fundo"):
        extra = [c for c in ("Gestor", "Administrador") if c in fun.columns and c not in cls.columns]
        if extra:
            f2 = fun[[fd._achar(fun.columns, "ID_Registro_Fundo")] + extra].drop_duplicates()
            f2.columns = [id_f] + extra
            cls = cls.merge(f2, on=id_f, how="left")
            cols += extra
    return cls[cols]


DE_ANTIGO_PARA_NOVO = {"CNPJ_FUNDO": "CNPJ_Classe", "DENOM_SOCIAL": "Denominacao_Social", "CLASSE": "Classificacao",
                       "CLASSE_ANBIMA": "Classificacao_Anbima", "SIT": "Situacao", "RENTAB_FUNDO": "Indicador_Desempenho",
                       "PUBLICO_ALVO": "Publico_Alvo", "CONDOM": "Forma_Condominio", "FUNDO_EXCLUSIVO": "Exclusivo",
                       "GESTOR": "Gestor", "ADMIN": "Administrador", "VL_PATRIM_LIQ": "Patrimonio_Liquido",
                       "DT_PATRIM_LIQ": "Data_Patrimonio_Liquido"}


def _funcionando(df: pd.DataFrame) -> pd.DataFrame:
    sit = fd._achar(df.columns, "Situacao", "SIT")
    return df[df[sit].fillna("").str.upper().str.contains("FUNCIONAMENTO")] if sit else df


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _cadastro() -> dict:
    """Cadastro de fundos em funcionamento (CVM). Fonte principal: registro novo de classes (Resolução CVM 175), onde estão
    os fundos ativos. Complemento: cad_fi.csv antigo, para fundos ainda não adaptados e para a taxa de administração e de
    performance (o registro novo não traz taxas; as do cadastro antigo são marcadas como possivelmente desatualizadas).
    Devolve {df, fonte, avisos}; df vazio se nada pôde ser lido."""
    out = {"df": pd.DataFrame(), "fonte": "CVM (cadastro de fundos)", "avisos": []}
    novo = antigo = pd.DataFrame()
    try:
        novo = _ler_registro()
    except Exception as e:
        out["avisos"].append(f"Registro de classes da CVM indisponível ({e.__class__.__name__}).")
    try:
        antigo = _ler_cad_fi()
    except Exception as e:
        out["avisos"].append(f"Cadastro antigo da CVM indisponível ({e.__class__.__name__}).")
    if novo.empty and antigo.empty:
        out["avisos"].append("Não consegui ler o cadastro da CVM agora. Você ainda pode digitar o CNPJ do fundo.")
        return out
    if novo.empty:
        out["df"] = _funcionando(antigo).reset_index(drop=True)
        out["avisos"].append("Só o cadastro antigo da CVM respondeu: fundos já adaptados à Resolução CVM 175 podem não aparecer.")
        return out
    novo = _funcionando(novo).copy()
    c_n = fd._achar(novo.columns, "CNPJ_Classe", "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")
    novo["_cnpj"] = novo[c_n].map(fd.so_digitos)
    if not antigo.empty:
        c_a = fd._achar(antigo.columns, "CNPJ_FUNDO", "CNPJ_FUNDO_CLASSE")
        antigo = antigo.copy()
        antigo["_cnpj"] = antigo[c_a].map(fd.so_digitos)
        taxas = [c for c in ("TAXA_ADM", "TAXA_PERFM") if c in antigo.columns and c not in novo.columns]
        if taxas:                                               # taxas do cadastro antigo, pelo mesmo CNPJ
            t = antigo.dropna(subset=taxas, how="all").drop_duplicates("_cnpj", keep="last")[["_cnpj"] + taxas]
            novo = novo.merge(t, on="_cnpj", how="left")
            novo["ORIGEM_TAXA"] = novo[taxas].notna().any(axis=1).map(
                {True: "cadastro antigo da CVM (pode estar desatualizada: confira a lâmina)", False: None})
        ativos_antigos = _funcionando(antigo)
        so_antigos = ativos_antigos[~ativos_antigos["_cnpj"].isin(novo["_cnpj"])]
        if len(so_antigos):                                     # fundos ainda não adaptados à 175, com os nomes de coluna novos
            so_antigos = so_antigos.rename(columns={k: v for k, v in DE_ANTIGO_PARA_NOVO.items() if v in novo.columns or k == c_a})
            if c_a in DE_ANTIGO_PARA_NOVO and DE_ANTIGO_PARA_NOVO[c_a] != c_n:
                so_antigos = so_antigos.rename(columns={DE_ANTIGO_PARA_NOVO[c_a]: c_n})
            if "TAXA_ADM" in so_antigos.columns and "ORIGEM_TAXA" in novo.columns:
                so_antigos["ORIGEM_TAXA"] = so_antigos["TAXA_ADM"].notna().map({True: "cadastro da CVM", False: None})
            novo = pd.concat([novo, so_antigos], ignore_index=True)
    out["df"] = novo.drop(columns="_cnpj").reset_index(drop=True)
    return out


def buscar_fundos(q: str, df: pd.DataFrame, filtro: tuple | None = None, limite: int = 40) -> list[dict]:
    """Busca por CNPJ (14 dígitos) ou por todas as palavras do nome. `filtro`: trechos da classe/ANBIMA aceitos."""
    if df is None or df.empty or not (q or "").strip():
        return []
    c_cnpj = fd._achar(df.columns, "CNPJ_FUNDO", "CNPJ_Classe", "CNPJ_FUNDO_CLASSE")
    c_nome = fd._achar(df.columns, "DENOM_SOCIAL", "Denominacao_Social")
    if c_cnpj is None or c_nome is None:
        return []
    d = df
    dig = fd.so_digitos(q)
    if len(dig) >= 5 and re.fullmatch(r"[\d\s./-]+", q.strip()):          # só números e pontuação = busca por CNPJ
        d = d[d[c_cnpj].map(fd.so_digitos).str.contains(dig, regex=False)]
    else:
        nomes = d[c_nome].fillna("").map(fa._norm)
        for palavra in fa._norm(q).split():
            nomes = nomes[nomes.str.contains(re.escape(palavra), regex=True)]
        d = d.loc[nomes.index]
    if filtro:
        cls = [fd._achar(d.columns, "CLASSE", "Tipo_Classe", "Classificacao"), fd._achar(d.columns, "CLASSE_ANBIMA", "Classificacao_Anbima")]
        txt = d[[c for c in cls if c]].fillna("").agg(" | ".join, axis=1).map(fa._norm) if any(cls) else None
        if txt is not None:
            d = d[txt.map(lambda t: fa._tem(t, filtro))]
    return [fa.cadastro_para_dict(r) for r in d.head(limite).to_dict("records")]


def linha_cadastro(cnpj: str) -> dict | None:
    df = _cadastro()["df"]
    if df.empty:
        return None
    c = fd._achar(df.columns, "CNPJ_FUNDO", "CNPJ_Classe", "CNPJ_FUNDO_CLASSE")
    if c is None:
        return None
    d = df[df[c].map(fd.so_digitos) == fd.so_digitos(cnpj)]
    return fa.cadastro_para_dict(d.iloc[0].to_dict()) if len(d) else None


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _cda_mes(cnpj: str, ym: str) -> pd.DataFrame:
    """Carteira (CDA) do fundo em um mês: todos os blocos do zip, só as linhas do CNPJ. Arquivo grande."""
    conteudo = fd.baixar(URL_CDA.format(ym=ym), timeout=240)
    if conteudo is None:
        return pd.DataFrame()
    alvo, partes = fd.so_digitos(cnpj), []
    with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
        for nome in z.namelist():
            if not nome.lower().endswith(".csv") or "blc" not in nome.lower():
                continue
            with z.open(nome) as f:
                for pedaco in pd.read_csv(f, sep=";", encoding="latin1", dtype=str, chunksize=200_000):
                    col = fd._achar(pedaco.columns, "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")
                    if col is None:
                        continue
                    sel = pedaco[pedaco[col].map(fd.so_digitos) == alvo]
                    if len(sel):
                        p = fa.padronizar_composicao(sel)
                        if len(p):
                            p["bloco"] = nome
                            partes.append(p)
    return pd.concat(partes, ignore_index=True) if partes else pd.DataFrame()


def coletar_composicao(cnpj: str, hoje: date | None = None) -> dict:
    """Carteira mais recente disponível (a CVM publica com ~2 meses de atraso) e a anterior, para ver mudanças."""
    out = {"atual": pd.DataFrame(), "ym": None, "anterior": pd.DataFrame(), "ym_ant": None, "avisos": []}
    meses = fd.meses_necessarios(hoje or date.today(), 6)[1:]
    achados = []
    for ym in meses:
        try:
            d = _cda_mes(cnpj, ym)
        except Exception as e:
            out["avisos"].append(f"Carteira de {ym[4:]}/{ym[:4]} não pôde ser lida ({e.__class__.__name__}).")
            continue
        if d is not None and len(d):
            achados.append((ym, d))
        if len(achados) == 2:
            break
    if achados:
        out["ym"], out["atual"] = achados[0]
    if len(achados) > 1:
        out["ym_ant"], out["anterior"] = achados[1]
    if not achados:
        out["avisos"].append("A CVM não divulgou a carteira deste fundo nos últimos meses (fundos de cotas, exclusivos ou com "
                             "sigilo podem não aparecer) ou o CNPJ não tem posições.")
    return out


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _extrato(cnpj: str) -> dict:
    """Campos de prazo (cotização, resgate, carência) do extrato da CVM, exatamente como a fonte traz."""
    try:
        conteudo = fd.baixar(URL_EXTRATO, timeout=240)
        if conteudo is None:
            return {}
        alvo = fd.so_digitos(cnpj)
        for pedaco in pd.read_csv(io.BytesIO(conteudo), sep=";", encoding="latin1", dtype=str, chunksize=100_000):
            col = fd._achar(pedaco.columns, "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")
            if col is None:
                return {}
            sel = pedaco[pedaco[col].map(fd.so_digitos) == alvo]
            if len(sel):
                return fa.prazos_do_extrato(sel.iloc[0].to_dict())
    except Exception:
        return {}
    return {}


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _lamina_taxas_mes(ym: str) -> pd.DataFrame:
    """Taxas declaradas nas lâminas do mês (CVM). Guarda só CNPJ e as colunas de taxa que existirem com nome conhecido;
    vazio se o arquivo não existir ou não tiver essas colunas (nada é adivinhado)."""
    try:
        conteudo = fd.baixar(URL_LAMINA.format(ym=ym), timeout=180)
        if conteudo is None:
            return pd.DataFrame()
        with zipfile.ZipFile(io.BytesIO(conteudo)) as z:
            nome = next((n for n in z.namelist() if re.fullmatch(r"lamina_fi_\d{6}\.csv", n.lower().split("/")[-1])), None)
            if not nome:
                return pd.DataFrame()
            with z.open(nome) as f:
                cab = pd.read_csv(f, sep=";", encoding="latin1", dtype=str, nrows=0, quoting=3)
            c_cnpj = fd._achar(cab.columns, "CNPJ_FUNDO_CLASSE", "CNPJ_FUNDO")
            c_adm = next((c for c in cab.columns if c.upper() == "TAXA_ADM"), None)
            c_perf = next((c for c in cab.columns if c.upper() in ("TAXA_PERFM", "TAXA_PERF", "TAXA_PERFORMANCE")), None)
            if c_cnpj is None or (c_adm is None and c_perf is None):
                return pd.DataFrame()
            usar = [c for c in (c_cnpj, c_adm, c_perf) if c]
            with z.open(nome) as f:
                df = pd.read_csv(f, sep=";", encoding="latin1", dtype=str, usecols=usar, quoting=3, on_bad_lines="skip")
        df = df.rename(columns={c_cnpj: "cnpj", **({c_adm: "taxa_adm"} if c_adm else {}), **({c_perf: "taxa_perf"} if c_perf else {})})
        df["cnpj"] = df["cnpj"].map(fd.so_digitos)
        return df.drop_duplicates("cnpj", keep="last")
    except Exception:
        return pd.DataFrame()


def _taxas_da_lamina(cnpj: str, hoje: date | None = None, meses: int = 4) -> dict:
    """Taxa de administração e de performance da lâmina mais recente (até 4 meses para trás). {} se não houver."""
    alvo, ref = fd.so_digitos(cnpj), pd.Timestamp(hoje or date.today())
    for k in range(1, meses + 1):
        ym = (ref - pd.DateOffset(months=k)).strftime("%Y%m")
        df = _lamina_taxas_mes(ym)
        if df.empty:
            continue
        sel = df[df["cnpj"] == alvo]
        if len(sel):
            def num(v):
                try:
                    x = float(str(v).replace(",", "."))
                    return x if math.isfinite(x) else None
                except (TypeError, ValueError):
                    return None
            linha = sel.iloc[0]
            return {"taxa_adm": num(linha.get("taxa_adm")), "taxa_perf": num(linha.get("taxa_perf")),
                    "origem": f"lâmina do fundo na CVM ({ym[4:]}/{ym[:4]})"}
    return {}


def preparar_fundo(cnpj: str, meses: int = 37) -> dict:
    cnpj = fd.formatar_cnpj(cnpj)
    fx = {"tipo": "fundo", "id": cnpj, "nome": cnpj, "avisos": [], "fonte": "CVM (cadastro e informe diário)", "erro": None}
    cad = linha_cadastro(cnpj) or {}
    fx["cad"] = cad
    if cad.get("nome"):
        fx["nome"] = cad["nome"]
    f = evolucao.coletar_fundo(cnpj, meses)
    fx["avisos"] += f["avisos"]
    df = f["df"]
    if df is None or df.empty or len(df) < 30:
        fx["erro"] = "sem informe diário suficiente na CVM para este CNPJ"
        return fx
    cota, limpeza = fa.limpar_serie(df["cota"])
    if limpeza["aviso"]:
        fx["avisos"].append(limpeza["aviso"])
    if limpeza["alterada"]:
        df = df.reindex(cota.index)
    fx["limpeza"] = limpeza
    fx["df"] = df
    fx.update(serie=cota, moeda="BRL", data_ref=df.index[-1].date().isoformat())
    fx["rotulos"] = fa.classificar_fundo(cad)
    fx["categoria"] = fa.categoria_principal(fx["rotulos"]) if fx["rotulos"] else "outros"
    if not cad:
        fx["avisos"].append("Fundo fora do cadastro lido (ou cadastro indisponível): sem classe, taxas e benchmark.")
    bcb = _bcb()
    fx["cdi_idx"], fx["ipca_idx"], fx["rf_idx"], fx["rf_nome"] = bcb.get("cdi_idx"), bcb.get("ipca_idx"), bcb.get("cdi_idx"), "CDI"
    bench = fa.benchmark_do_texto(cad.get("benchmark"), fx["categoria"])
    fx["bench"] = bench
    fx["ref"], fx["ref_nome"], fx["ref_freq"] = None, bench["nome"], "D"
    if bench["chave"]:
        s, motivo = _serie_referencia(bench["chave"], bcb)
        fx["ref"] = s
        if s is None:
            fx["avisos"].append(f"Benchmark {bench['nome']}: {motivo}.")
    ta, tp, origem = cad.get("taxa_adm"), cad.get("taxa_perf"), cad.get("taxa_origem") or "cadastro da CVM"
    lam = _taxas_da_lamina(cnpj) if (ta is None or cad.get("taxa_origem")) else {}   # lâmina é mais recente que o cadastro antigo
    if lam and (lam.get("taxa_adm") is not None or lam.get("taxa_perf") is not None):
        ta, tp, origem = lam.get("taxa_adm"), lam.get("taxa_perf"), lam["origem"]
    ta = ta if fa._ok(ta) and 0 <= ta < 20 else None
    tp = tp if fa._ok(tp) and 0 <= tp <= 100 else None
    fx["custos"] = {"taxa_adm": ta, "taxa_perf": tp,
                    "fonte": origem if (ta is not None or tp is not None) else
                    "sem dado na fonte: o cadastro novo da CVM não traz taxas e a lâmina não foi encontrada"}
    m = fd.metricas_fundo(df)
    fx["metricas"] = m
    fx["pl"] = m.get("pl_atual")
    fx["pl_var12m"], fx["cotistas_var12m"], fx["captacao_12m"] = m.get("pl_var12m"), m.get("cotistas_var12m"), m.get("captacao_liquida_12m")
    fx["pl_texto"] = _grande(fx["pl"]) if fx["pl"] else None
    fx["estrategia"] = None
    return fx


# =============================================================================== telas: peças comuns
def _alertas(an: dict):
    for a in an["alertas"]:
        (st.warning if a["nivel"] == "atencao" else st.info)(f"**{a['titulo']}.** {a['texto']}")


def _grafico(series: dict, titulo: str, chave: str, sufixo: str = ""):
    s = {k: v for k, v in series.items() if v is not None and len(v)}
    if s:
        st.plotly_chart(evolucao.grafico_linhas(s, titulo, sufixo), width="stretch", key=chave)


def _base100(s: pd.Series, inicio=None) -> pd.Series:
    s = fa.serie(s)
    if inicio is not None:
        s = s[s.index >= inicio]
    return s / float(s.iloc[0]) * 100 if len(s) else s


def _tabela_janelas(r: dict) -> pd.DataFrame:
    linhas = {"Dia": r.get("dia"), "Mês atual": r.get("mes"), "No ano": r.get("ytd"), **r.get("janelas", {}),
              "Desde o início": r.get("acumulado")}
    return pd.DataFrame({"Retorno": {k: _p(v) for k, v in linhas.items()}})


def _tabela_calendario(cal: dict) -> pd.DataFrame:
    m = cal["mensal"]
    if m.empty:
        return pd.DataFrame()
    d = pd.DataFrame({"ano": m.index.year, "mes": m.index.month, "r": m.values})
    pv = d.pivot(index="ano", columns="mes", values="r").sort_index(ascending=False)
    nomes_mes = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"]
    pv.columns = [nomes_mes[i - 1] for i in pv.columns]
    out = pv.map(lambda v: _p(v)) if hasattr(pv, "map") else pv.applymap(lambda v: _p(v))
    anual = cal["anual"]
    out["Ano"] = [(_p(anual.loc[a, "retorno"]) + (" *" if anual.loc[a, "parcial"] else "")) if a in anual.index else "n/d" for a in out.index]
    return out


# =============================================================================== abas
def _aba_visao(fx, an, atalho_comparar):
    r, rk, nota = an["rent"], an["risco"], an["nota"]
    j = r.get("janelas", {})
    ref = an["vs_ref"]
    st.caption(" · ".join(x["rotulo"] for x in fx["rotulos"]) or "Categoria não identificada")
    cls_nota = "na" if nota["nota"] is None else ("good" if nota["nota"] >= 70 else "fair" if nota["nota"] >= 50 else "bad")
    itens = [("Nota educacional", "n/d" if nota["nota"] is None else f"{nota['nota']:.0f}/100", cls_nota,
              f"cobertura {nota['cobertura'] * 100:.0f}%" + (" · provisória" if nota["provisoria"] else ""),
              "Média ponderada de retorno, risco, consistência, custos e porte, só com os pilares que têm dado."),
             ("Retorno 12 meses", _p(j.get("12 meses")), _cls_ret(j.get("12 meses"))),
             ("Contra a referência", "n/d" if not ref.get("ok") else
              ("0,0 p.p." if abs(ref["dif_pp"]) < 0.05 else f"{ref['dif_pp']:+.1f}".replace(".", ",") + " p.p."),
              "na" if not ref.get("ok") else ("good" if ref["dif_pp"] >= 0.5 else "bad" if ref["dif_pp"] <= -0.5 else "info"),
              f"{ref['nome']} · {ref['anos']} ano(s)" if ref.get("ok") else ref.get("motivo", "")),
             ("Volatilidade anual", _p(rk["vol"], 1, False), "na" if rk["vol"] is None else "info"),
             ("Pior queda", _p(rk["dd"]["max"]), "na" if rk["dd"]["max"] is None else "info"),
             ("Taxa de administração", _pp((fx.get("custos") or {}).get("taxa_adm")),
              fa.faixa_taxa((fx.get("custos") or {}).get("taxa_adm"), fx.get("categoria") or "")[0],
              "% ao ano"),
             ("Patrimônio", fx.get("pl_texto") or "n/d", "info" if fx.get("pl") else "na"),
             ("Liquidez" if fx["tipo"] == "etf" else "Cotistas",
              an["liq_texto"] if fx["tipo"] == "etf" else (f"{fx['metricas']['cotistas_atual']:,.0f}".replace(",", ".") if fx["metricas"].get("cotistas_atual") else "n/d"),
              an["liq_classe"] if fx["tipo"] == "etf" else "info")]
    try:                                                  # leitura em palavras conforme o modo de experiência
        import experiencia_app as _ea
        import leitura as _lt
        _ea.mostrar(_lt.fundo(fx.get("nome") or fx.get("id"), fx["tipo"], j.get("12 meses"), ref.get("dif_pp") if ref.get("ok") else None,
                              ref.get("nome") if ref.get("ok") else None, rk["vol"], rk["dd"]["max"], (fx.get("custos") or {}).get("taxa_adm"),
                              nota["nota"], _ea.modo(), ref.get("anos") if ref.get("ok") else None))
    except Exception:
        pass
    _cartoes(itens)
    _alertas(an)
    for av in fx["avisos"]:
        st.caption("⚠️ " + av)
    st.caption(f"Fonte: {fx['fonte']} · dados até {_data(fx.get('data_ref'))}. " + NOTA_LEGAL + f" (versão da análise: {VERSAO} · cálculos {getattr(fa, 'VERSAO', 'antigos')})")
    if atalho_comparar and fx["tipo"] == "etf":
        atalho_comparar([fx["id"]], f"fa_{fx['id']}", "Comparar este ETF com outros ativos")
    elif atalho_comparar and fx["tipo"] == "fundo":
        atalho_comparar([fd.so_digitos(fx["id"])], f"fa_{fd.so_digitos(fx['id'])}", "Comparar este fundo com outros ativos")


def _aba_indicadores(fx, an):
    r, rk, cs, c = an["rent"], an["risco"], an["consist"], an["conc"]
    cu = fx.get("custos") or {}
    linhas = []

    def L(grupo, nome, valor, nota=""):
        linhas.append({"Grupo": grupo, "Indicador": nome, "Valor": valor, "Observação": nota})
    L("Porte", "Patrimônio", fx.get("pl_texto") or "n/d", "ETF: total de ativos (Yahoo). Fundo: informe diário da CVM.")
    if fx["tipo"] == "etf":
        L("Porte", "Volume médio negociado (90 dias)", _grande(an["liquidez"], fx["moeda"]) if an["liquidez"] else "n/d", an["liq_texto"])
        L("Porte", "Moeda de negociação", fx["moeda"])
        L("Estratégia", "Distribuição de rendimentos", fx["distribuicao"]["rotulo"], fx["distribuicao"]["nota"])
        L("Estratégia", "Índice de referência", (fx["indice"]["nome"] or "n/d"), fx["indice"]["fonte"])
        jan = rk.get("janela_ref")
        jan_txt = f" Janela: {_data(jan[0])} a {_data(jan[1])}." if jan else ""
        sem = " Retornos semanais (datas desencontradas na fonte)." if rk.get("freq_ref_usada") == "W" else ""
        L("Custos", "Tracking error (a.a.)", _p(rk.get("te"), 2, False),
          (f"Volatilidade da diferença contra o índice ({fx.get('ref_tipo', 'preço')}), pelo preço de mercado: inclui o "
           "ágio/deságio diário do ETF, por isso costuma ficar acima do que a gestora divulga (calculado pela cota)." + jan_txt + sem) if rk.get("te") is not None else rk["motivos"].get("ref", ""))
        L("Custos", "Tracking difference (acumulada)", _p(rk.get("td"), 2),
          ("Retorno do ETF menos o do índice." + jan_txt) if rk.get("td") is not None else "")
        L("Custos", "Tracking difference (ao ano)", _p(rk.get("td_anual"), 2),
          "Quanto o ETF fica atrás (ou à frente) do índice por ano; o normal é perto da taxa de administração." if rk.get("td_anual") is not None else "")
    else:
        m = fx["metricas"]
        L("Porte", "Cotistas", f"{m['cotistas_atual']:,.0f}".replace(",", ".") if m.get("cotistas_atual") else "n/d")
        L("Porte", "Variação do patrimônio (12m)", _p(fx.get("pl_var12m")))
        L("Porte", "Captação líquida (12m)", _grande(fx.get("captacao_12m")) if fx.get("captacao_12m") is not None else "n/d", "Aplicações − resgates, informe diário.")
        L("Estratégia", "Benchmark", (fx["bench"]["nome"] or "n/d"), fx["bench"]["origem"])
    L("Custos", "Taxa de administração", _pp(cu.get("taxa_adm")), cu.get("fonte", ""))
    L("Custos", "Taxa de performance", _pp(cu.get("taxa_perf"), 0) if fx["tipo"] == "fundo" else "n/d", "Só fundos; ETFs em geral não cobram.")
    for rot, k in (("12 meses", "12 meses"), ("36 meses", "36 meses"), ("60 meses", "60 meses")):
        L("Rentabilidade", f"Retorno em {rot}", _p(r.get("janelas", {}).get(k)))
    L("Rentabilidade", "CAGR 3 anos", _p(r.get("cagr", {}).get(3)), "a.a.")
    L("Risco", "Volatilidade anual", _p(rk["vol"], 1, False))
    L("Risco", "Drawdown máximo", _p(rk["dd"]["max"]))
    L("Risco", "Sharpe", _num(rk["sharpe"]), rk["motivos"].get("sharpe", f"contra {fx.get('rf_nome', '')}"))
    L("Risco", "Sortino", _num(rk["sortino"]), rk["motivos"].get("sortino", ""))
    L("Risco", "Beta contra a referência", _num(rk["beta"]), rk["motivos"].get("ref", ""))
    L("Risco", "Correlação com a referência", _num(rk["corr"]))
    L("Consistência", "Meses positivos", _p(cs["meses_positivos"], 0, False), f"{cs['n_meses']} meses")
    L("Consistência", "Meses acima da referência", _p(cs["meses_acima_ref"], 0, False))
    L("Carteira", "Maior posição", _pp(c.get("top1"), 1) if c.get("ok") else "n/d", "" if c.get("ok") else "carteira não divulgada")
    L("Carteira", "10 maiores posições", _pp(c.get("top10"), 1) if c.get("ok") else "n/d")
    cfg = {"Grupo": st.column_config.TextColumn("Grupo", width="small"),
           "Indicador": st.column_config.TextColumn("Indicador", width="medium"),
           "Valor": st.column_config.TextColumn("Valor", width="large"),
           "Observação": st.column_config.TextColumn("Observação", width="large", help="Passe o dedo na célula para ler o texto inteiro.")}
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch", column_config=cfg)
    st.caption("n/d = a fonte não entrega ou o histórico é curto demais. Nada é preenchido com zero nem estimado.")


def _aba_estrategia(fx, an):
    st.markdown("**Classificação (pode ter mais de um rótulo)**")
    for r in fx["rotulos"] or []:
        st.markdown(f"- {r['rotulo']} · _{r['motivo']}_")
    if not fx["rotulos"]:
        st.caption("Nenhuma categoria identificada pelos dados disponíveis.")
    if fx["tipo"] == "etf":
        ind, d = fx["indice"], fx["distribuicao"]
        st.markdown(f"**Índice de referência:** {ind['nome'] or 'n/d'} · _{ind['fonte']}_")
        st.markdown(f"**Política de rendimentos:** {d['rotulo']}. {d['nota']}")
        info = fx["info"]
        for k, rot in (("fundFamily", "Gestora"), ("category", "Categoria na fonte"), ("legalType", "Tipo legal")):
            if info.get(k):
                st.markdown(f"**{rot}:** {info[k]}")
        if info.get("longBusinessSummary"):
            with st.expander("Descrição da fonte (em inglês)"):
                st.write(info["longBusinessSummary"])
    else:
        cad = fx.get("cad") or {}
        for k, rot in (("classe", "Classe (CVM)"), ("classe_anbima", "Classificação ANBIMA"), ("publico", "Público-alvo"),
                       ("condominio", "Condomínio"), ("gestor", "Gestor"), ("administrador", "Administrador")):
            if cad.get(k):
                st.markdown(f"**{rot}:** {cad[k]}")
        st.markdown(f"**Benchmark:** {fx['bench']['nome'] or 'n/d'} · _{fx['bench']['origem']}_")
        cn = fd.so_digitos(fx["id"])
        if st.button("Buscar prazos de cotização e resgate no extrato da CVM", key=f"fa_prazo_{cn}", icon=":material/schedule:"):
            with st.spinner("Lendo o extrato da CVM (arquivo grande)..."):
                st.session_state[f"fa_prazos_{cn}"] = _extrato(fx["id"])
        pz = st.session_state.get(f"fa_prazos_{cn}")
        if pz is not None:
            if pz:
                for k, v in pz.items():
                    st.markdown(f"- **{k}:** {v}")
                st.caption("Campos exatamente como a CVM entrega; confira o regulamento.")
            else:
                st.caption("O extrato da CVM não informa prazos para este fundo (ou o layout mudou). Veja o regulamento.")
    st.markdown("**Riscos típicos desta estratégia**")
    for t in an["riscos_estrategia"] or ["Sem riscos catalogados para esta categoria."]:
        st.markdown(f"- {t}")


def _aba_composicao(fx, an):
    if fx["tipo"] == "etf":
        pesos, nomes = fx.get("pesos"), fx.get("nomes_pos", {})
        c = an["conc"]
        if not pesos:
            st.info("A fonte não divulga a carteira deste ETF.")
        else:
            cl, rot, txt = fa.qualidade_diversificacao(c)
            _cartoes([("Maior posição", _pp(c["top1"], 1), "info"), ("5 maiores", _pp(c["top5"], 1), "info"),
                      ("10 maiores", _pp(c["top10"], 1), "info"), ("Qualidade", rot.split(" (")[0], cl, txt)], 4)
            df = pd.DataFrame([{"Ativo": k, "Nome": nomes.get(k, ""), "Peso (%)": round(v, 2)} for k, v in sorted(pesos.items(), key=lambda x: -x[1])])
            st.dataframe(df, hide_index=True, width="stretch")
            st.caption("A fonte divulga só as maiores posições; concentração e sobreposição valem sobre essa parte.")
        if fx.get("setores"):
            s = pd.DataFrame({"Setor": list(fx["setores"]), "Peso (%)": [round(v, 2) for v in fx["setores"].values()]}).sort_values("Peso (%)", ascending=False)
            st.markdown("**Exposição setorial**")
            st.dataframe(s, hide_index=True, width="stretch")
        else:
            st.caption("Exposição setorial: a fonte não entrega para este ETF.")
        if fx.get("classes_ativo"):
            st.markdown("**Por classe de ativo (Yahoo)**")
            st.dataframe(pd.DataFrame({"Classe": list(fx["classes_ativo"]), "Peso (%)": [round(v, 2) for v in fx["classes_ativo"].values()]}), hide_index=True, width="stretch")
        ind = fx["indice"]["nome"]
        st.caption("Exposição geográfica: a fonte não entrega a divisão por país. "
                   + (f"Pelo índice de referência ({ind}) e pela moeda ({fx['moeda']}), confira o regulamento." if ind else "Confira o regulamento."))
        return
    cn = fd.so_digitos(fx["id"])
    chave = f"fa_cda_{cn}"
    if st.button("Carregar a carteira divulgada pela CVM (arquivo grande, pode demorar)", key=f"btn_{chave}", icon=":material/pie_chart:"):
        with st.spinner("Lendo a carteira (CDA) da CVM..."):
            st.session_state[chave] = coletar_composicao(fx["id"])
    comp = st.session_state.get(chave)
    if comp is None:
        st.info("A composição da carteira vem da CDA da CVM, publicada com cerca de 2 meses de atraso. Toque no botão para carregar.")
        return
    for av in comp["avisos"]:
        st.caption("⚠️ " + av)
    if comp["atual"].empty:
        return
    d = comp["atual"]
    ym = comp["ym"]
    st.caption(f"Carteira de {ym[4:]}/{ym[:4]} (CDA, CVM). Pesos sobre as posições divulgadas.")
    por_tipo = fa.composicao_por_tipo(d)
    st.markdown("**Por tipo de aplicação**")
    st.dataframe(pd.DataFrame({"Tipo": por_tipo.index, "Peso (%)": por_tipo.round(2).values}), hide_index=True, width="stretch")
    ex = por_tipo[por_tipo.index.str.contains("exterior", case=False, na=False)].sum()
    st.caption(f"Exposição ao exterior (pelo tipo informado): {_pp(ex, 1)}.")
    pesos = d.groupby("ativo")["valor"].sum()
    pesos = pesos / pesos.sum() * 100
    c = fa.concentracao(pesos)
    cl, rot, txt = fa.qualidade_diversificacao(c)
    _cartoes([("Maior posição", _pp(c["top1"], 1), "info"), ("5 maiores", _pp(c["top5"], 1), "info"),
              ("10 maiores", _pp(c["top10"], 1), "info"), ("Qualidade", rot, cl, txt)], 4)
    top = pesos.sort_values(ascending=False).head(15)
    st.dataframe(pd.DataFrame({"Ativo": top.index, "Peso (%)": top.round(2).values}), hide_index=True, width="stretch")
    if not comp["anterior"].empty:
        a = comp["anterior"].groupby("ativo")["valor"].sum()
        a = a / a.sum() * 100
        dif = (pesos.reindex(pesos.index.union(a.index)).fillna(0) - a.reindex(pesos.index.union(a.index)).fillna(0)).sort_values()
        mud = pd.concat([dif.head(5), dif.tail(5)]).drop_duplicates()
        st.markdown(f"**Maiores mudanças desde {comp['ym_ant'][4:]}/{comp['ym_ant'][:4]} (p.p.)**")
        st.dataframe(pd.DataFrame({"Ativo": mud.index, "Variação (p.p.)": mud.round(2).values}), hide_index=True, width="stretch")
    st.session_state[f"fa_pesos_{cn}"] = pesos.to_dict()


def _aba_rentabilidade(fx, an):
    r, cal = an["rent"], an["cal"]
    if not r.get("ok"):
        st.info("Histórico insuficiente.")
        return
    st.dataframe(_tabela_janelas(r), width="stretch")
    cg = r["cagr"]
    st.caption("CAGR (a.a.): " + " · ".join(f"{n} ano(s): {_p(cg.get(n))}" for n in (1, 3, 5)) + f" · período: {_data(r['inicio'])} a {_data(r['fim'])}")
    st.caption("Janelas sem ponto de partida a ~10 dias ficam n/d (nada é estimado). O preço/cota " + (
        "de ETF usa o preço ajustado por proventos (retorno total)." if fx["tipo"] == "etf" else "do fundo já é líquido da taxa de administração (não de impostos)."))
    tc = _tabela_calendario(cal)
    if not tc.empty:
        st.markdown("**Retorno mês a mês**")
        st.dataframe(tc, width="stretch")
        st.caption("* ano parcial (histórico começa no meio do ano ou o ano ainda não terminou).")
    st.markdown("**Contra referências**")
    linhas = []
    for n, x in an["vs_cdi"].items():
        linhas.append({"Referência": "CDI", "Período": f"{n} ano(s)", "Ativo": _p(x.get("ativo")) if x["ok"] else x["motivo"],
                       "Referência (ret.)": _p(x.get("ref")) if x["ok"] else "—", "% da referência": f"{x['pct_ref']:.0f}%" if x["ok"] and x["pct_ref"] else "—"})
    x = an["vs_ref"]
    if x.get("nome"):
        linhas.append({"Referência": x["nome"], "Período": f"{x['anos']} ano(s)", "Ativo": _p(x.get("ativo")) if x["ok"] else x["motivo"],
                       "Referência (ret.)": _p(x.get("ref")) if x["ok"] else "—", "% da referência": f"{x['pct_ref']:.0f}%" if x["ok"] and x["pct_ref"] else "—"})
    for n, y in an["real"].items():
        linhas.append({"Referência": "IPCA (retorno real)", "Período": f"{n} ano(s)", "Ativo": _p(y.get("nominal")) if y["ok"] else y["motivo"],
                       "Referência (ret.)": _p(y.get("ipca")) if y["ok"] else "—",
                       "% da referência": f"real {_p(y.get('real_anual'))} a.a." if y["ok"] and y.get("real_anual") is not None else "—"})
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    if fx["tipo"] == "etf" and fx.get("ref_nome") and fx.get("ref") is not None:
        st.caption(f"ETF contra {fx['ref_nome']}: preço de fechamento contra índice de PREÇO (ambos sem proventos).")
    ref = fx.get("ref")
    series = {fx["id"]: _base100(fx["serie"])}
    if ref is not None and len(ref):
        series[fx.get("ref_nome") or "Referência"] = _base100(ref, fx["serie"].index[0] if len(fx["serie"]) else None)
    if fx.get("cdi_idx") is not None and len(fx["cdi_idx"]) and fx["moeda"] == "BRL":
        series["CDI"] = _base100(fx["cdi_idx"], fx["serie"].index[0])
    _grafico(series, "Evolução (base 100)", f"fa_rent_{fx['id']}")


def _aba_risco(fx, an):
    rk = an["risco"]
    if not rk["ok"]:
        st.info(rk["motivos"].get("geral", "Histórico insuficiente."))
        return
    dd = rk["dd"]
    _cartoes([("Volatilidade anual", _p(rk["vol"], 1, False), "info", "desvio-padrão dos retornos, anualizado"),
              ("Drawdown máximo", _p(dd["max"]), "bad" if dd["max"] <= -0.3 else "fair" if dd["max"] <= -0.15 else "good",
               f"pico {_data(dd['pico'])} → fundo {_data(dd['fundo'])}" + (f" · recuperado em {_data(dd['recuperado'])}" if dd["recuperado"] is not None else " · ainda não recuperado")),
              ("Queda atual do pico", _p(dd["atual"]), "info"),
              ("Sharpe", _num(rk["sharpe"]), "na" if rk["sharpe"] is None else ("good" if rk["sharpe"] > 1 else "fair" if rk["sharpe"] > 0 else "bad"),
               rk["motivos"].get("sharpe", f"contra {fx.get('rf_nome', '')}")),
              ("Sortino", _num(rk["sortino"]), "na" if rk["sortino"] is None else "info", rk["motivos"].get("sortino", "só retornos negativos no denominador")),
              ("Beta", _num(rk["beta"]), "na" if rk["beta"] is None else "info", fx.get("ref_nome") or rk["motivos"].get("ref", "")),
              ("Correlação", _num(rk["corr"]), "na" if rk["corr"] is None else "info", fx.get("ref_nome") or ""),
              ("Tracking error", _p(rk["te"], 2, False), "na" if rk["te"] is None else "info", "a.a., contra o índice")], 4)
    st.markdown("**Outros riscos**")
    cambio = "Sim: negocia/investe em moeda diferente do real." if (fx.get("moeda") not in (None, "BRL") or any(r["chave"] in ("internacional", "cambial") for r in fx["rotulos"])) else "Não identificado nos dados."
    st.markdown(f"- **Risco cambial:** {cambio}")
    if fx["tipo"] == "etf":
        st.markdown(f"- **Risco de liquidez:** {an['liq_texto']}.")
    else:
        st.markdown("- **Risco de liquidez:** depende do prazo de resgate e da carteira (veja a aba Estratégia e o regulamento).")
    cred = any(r["chave"] in ("renda_fixa", "credito_privado", "referenciado_di") for r in fx["rotulos"])
    st.markdown("- **Risco de crédito:** " + ("aplicável: depende dos emissores da carteira; FGC não cobre fundos." if cred else "não se aplica pela classificação."))
    st.markdown("- **Risco de estratégia:** " + (" ".join(an["riscos_estrategia"][:2]) or "sem dado."))
    with st.expander("O que significa cada indicador"):
        st.markdown("- **Volatilidade:** quanto o preço oscila; não é perda.\n- **Drawdown:** queda do pico ao vale.\n"
                    "- **Sharpe:** retorno acima da taxa livre de risco por unidade de volatilidade.\n"
                    "- **Sortino:** igual ao Sharpe, mas só penaliza os retornos ruins.\n- **Beta:** quanto o ativo se move para cada 1% da referência.\n"
                    "- **Correlação:** de −1 a +1, o quanto anda junto com a referência.\n"
                    "- **Tracking error:** variação da diferença para o índice; quanto menor, mais fiel é a réplica.\n"
                    "- Risco baixo não significa seguro: os números olham só o passado.")
    s = fa.serie(fx["serie"])
    dds = (s / s.cummax() - 1) * 100
    _grafico({"Queda do pico (%)": dds}, "Queda desde o pico", f"fa_dd_{fx['id']}", "%")


def _aba_custos(fx, an):
    cu = fx.get("custos") or {}
    if fx["tipo"] == "etf":
        v = st.number_input("Sua taxa de administração (% a.a.), se você souber", min_value=0.0, max_value=10.0, step=0.05,
                            value=float(st.session_state.get(f"fa_taxa_{fx['id']}") or 0.0), key=f"fa_taxa_in_{fx['id']}",
                            help="Use se a fonte não trouxe a taxa (ETFs brasileiros: veja a lâmina). Fica marcada como informada por você.")
        if v and v != st.session_state.get(f"fa_taxa_{fx['id']}"):
            st.session_state[f"fa_taxa_{fx['id']}"] = v
            st.rerun()
    ta = cu.get("taxa_adm")
    cls, txt = fa.faixa_taxa(ta, fx.get("categoria") or "")
    itens = [("Taxa de administração", _pp(ta), cls, txt, f"fonte: {cu.get('fonte', 'n/d')}"),
             ("Taxa de performance", _pp(cu.get("taxa_perf"), 0) if fx["tipo"] == "fundo" else "n/d",
              "info" if cu.get("taxa_perf") else "na", "% sobre o que superar o benchmark" if fx["tipo"] == "fundo" else "ETFs em geral não cobram"),
             ("Custo em 5 anos", _p(fa.custo_acumulado(ta, 5), 1, False), "info" if ta is not None else "na", "parte do patrimônio consumida"),
             ("Custo em 10 anos", _p(fa.custo_acumulado(ta, 10), 1, False), "info" if ta is not None else "na", "efeito composto")]
    _cartoes(itens, 4)
    cg = an["rent"].get("cagr", {}).get(3) or an["rent"].get("cagr", {}).get(1)
    bruto = fa.retorno_bruto_aprox(cg, ta)
    if bruto is not None:
        st.caption(f"Retorno líquido de taxa (já no preço/cota): {_p(cg)} a.a. · bruto aproximado antes da taxa de administração: {_p(bruto)} a.a. "
                   "(não inclui custos de negociação, spread nem impostos).")
    else:
        st.caption("Sem taxa e/ou CAGR suficiente: retorno bruto não estimado.")
    cat = fx.get("categoria")
    st.markdown("**Tributação (regras gerais, confira as vigentes)**")
    if fx["tipo"] == "etf":
        st.markdown("- ETFs de renda variável: 15% sobre o ganho na venda, sem isenção dos R$ 20 mil mensais; ETFs de renda fixa: tabela regressiva. "
                    "ETFs no exterior têm regras próprias.")
    elif cat in ("renda_fixa", "referenciado_di", "credito_privado"):
        st.markdown("- Renda fixa: come-cotas em maio e novembro (15% ou 20%) e IR regressivo no resgate (22,5% a 15%).")
    elif cat == "acoes":
        st.markdown("- Fundos de ações: 15% sobre o ganho no resgate; sem come-cotas.")
    elif cat == "multimercado":
        st.markdown("- Multimercados: em geral come-cotas semestral e IR regressivo conforme o prazo.")
    else:
        st.markdown("- Consulte o regulamento: a tributação depende do tipo de fundo.")
    st.caption((f"Fonte da taxa: {cu.get('fonte') or 'n/d'}. A taxa declarada pode ser a máxima prevista no regulamento e diferir da efetivamente cobrada.") if fx["tipo"] == "fundo" else
               "Custos de corretagem e spread de negociação não estão incluídos.")


def _aba_historico(fx, an):
    s = fa.serie(fx["serie"])
    cal = an["cal"]
    if fx["tipo"] == "fundo":
        df = fx["df"]
        _grafico({"Patrimônio líquido": df["pl"].dropna()} if "pl" in df else {}, "Evolução do patrimônio líquido (R$)", f"fa_h_pl_{fx['id']}")
        if "cotistas" in df and df["cotistas"].notna().any():
            _grafico({"Cotistas": df["cotistas"].dropna()}, "Número de cotistas", f"fa_h_cot_{fx['id']}")
        if {"captacao", "resgate"} <= set(df.columns):
            liq = (df["captacao"] - df["resgate"]).dropna()
            if len(liq):
                _grafico({"Captação líquida acumulada": liq.cumsum()}, "Captação líquida acumulada (R$)", f"fa_h_cap_{fx['id']}")
    elif fx.get("pl"):
        st.caption(f"Patrimônio atual: {fx['pl_texto']}. O Yahoo não entrega o histórico do patrimônio do ETF.")
    anual = cal["anual"]
    if len(anual):
        d = pd.DataFrame({"Retorno (%)": (anual["retorno"] * 100).round(2)}, index=[f"{a}{'*' if p else ''}" for a, p in zip(anual.index, anual["parcial"])])
        st.plotly_chart(evolucao.grafico_barras(d.set_axis([pd.Timestamp(year=int(str(i).strip('*')), month=12, day=31) for i in d.index]), ["Retorno (%)"], "Retorno por ano-calendário (* parcial)", True),
                        width="stretch", key=f"fa_h_ano_{fx['id']}")
    if len(s) > 260:
        j12 = (s / s.shift(252) - 1).dropna() * 100
        _grafico({"Retorno em 12 meses móveis (%)": j12}, "Retorno móvel de 12 meses", f"fa_h_j12_{fx['id']}", "%")
        r = s.pct_change()
        vol = (r.rolling(252).std() * (252 ** 0.5) * 100).dropna()
        _grafico({"Volatilidade móvel de 12 meses (%)": vol}, "Histórico de risco (volatilidade móvel)", f"fa_h_vol_{fx['id']}", "%")
    if fx["tipo"] == "etf" and fx.get("dividendos") is not None and len(fx["dividendos"]):
        dv = fx["dividendos"].resample("YE").sum()
        st.plotly_chart(evolucao.grafico_barras(dv.to_frame("Proventos por cota"), ["Proventos por cota"], "Proventos por cota e por ano"),
                        width="stretch", key=f"fa_h_div_{fx['id']}")
    st.caption("Sem fonte gratuita no app: evolução histórica das taxas, da composição e da exposição setorial (só a carteira mais recente "
               "e, nos fundos, a comparação entre os dois últimos meses da CDA, na aba Composição). CAGR: aba Rentabilidade.")


def _aba_comparacao(fx, an, atalho_comparar):
    st.caption("Compare só ETFs/fundos do mesmo objetivo. O app avisa quando as categorias ou os benchmarks diferem.")
    txt = st.text_input("Outros códigos de ETF ou CNPJs de fundos (separe por vírgula)", key=f"fa_cmp_{fx['id']}",
                        placeholder="Ex.: IVVB11, VOO, 00.000.000/0001-00")
    pares = [x.strip() for x in re.split(r"[,;\s]+", txt or "") if x.strip()][:5]
    base = {"id": fx["id"], "nome": fx["nome"], "categoria": fx.get("categoria"), "benchmark": fx.get("ref_nome"), "an": an, "fx": fx}
    itens = [base]
    for p in pares:
        try:
            outro = preparar_fundo(p) if len(fd.so_digitos(p)) == 14 else preparar_etf(p)
        except Exception as e:
            st.caption(f"⚠️ {p}: não consegui os dados ({e.__class__.__name__}).")
            continue
        if outro.get("erro"):
            st.caption(f"⚠️ {p}: {outro['erro']}.")
            continue
        itens.append({"id": outro["id"], "nome": outro["nome"], "categoria": outro.get("categoria"), "benchmark": outro.get("ref_nome"),
                      "an": fa.analisar_tudo(outro), "fx": outro})
    if len(itens) < 2:
        st.info("Digite ao menos um outro código para comparar.")
        return
    for it in itens[1:]:
        ok, aviso = fa.comparavel({"categoria": base["categoria"], "benchmark": base["benchmark"]},
                                  {"categoria": it["categoria"], "benchmark": it["benchmark"]})
        if not ok:
            st.error(f"{it['id']} × {base['id']}: {aviso}")
        elif aviso:
            st.warning(f"{it['id']} × {base['id']}: {aviso}")
    linhas = []
    for it in itens:
        a, f_ = it["an"], it["fx"]
        j = a["rent"].get("janelas", {})
        linhas.append({"Ativo": it["id"], "Categoria": ", ".join(r["rotulo"] for r in f_["rotulos"][:2]) or "n/d",
                       "Taxa adm. (% a.a.)": (f_.get("custos") or {}).get("taxa_adm"), "Retorno 12m (%)": None if j.get("12 meses") is None else j["12 meses"] * 100,
                       "CAGR 3a (%)": None if a["rent"]["cagr"].get(3) is None else a["rent"]["cagr"][3] * 100,
                       "Volatilidade (%)": None if a["risco"]["vol"] is None else a["risco"]["vol"] * 100,
                       "Pior queda (%)": None if a["risco"]["dd"]["max"] is None else a["risco"]["dd"]["max"] * 100,
                       "Sharpe": a["risco"].get("sharpe"), "Meses positivos (%)": None if a["consist"]["meses_positivos"] is None else a["consist"]["meses_positivos"] * 100,
                       "Maior posição (%)": a["conc"].get("top1"), "Nota": a["nota"]["nota"]})
    df = pd.DataFrame(linhas)
    st.dataframe(df.round(2), hide_index=True, width="stretch")
    st.markdown("**Ranking por critério (só entre quem tem o dado)**")
    for rot, ch, alto in (("Menor taxa", "Taxa adm. (% a.a.)", False), ("Maior retorno 12m", "Retorno 12m (%)", True),
                          ("Menor volatilidade", "Volatilidade (%)", False), ("Melhor Sharpe", "Sharpe", True), ("Maior nota", "Nota", True)):
        rk = [r for r in fa.ranking([{"Ativo": x["Ativo"], ch: x[ch]} for x in linhas], ch, alto) if r["pos"]]
        if rk:
            st.caption(f"{rot}: " + " > ".join(f"{r['Ativo']} ({_num(r[ch], 2)})" for r in rk))
    ov = None
    if len(itens) > 1 and itens[0]["fx"].get("pesos") and itens[1]["fx"].get("pesos"):
        ov = fa.sobreposicao(itens[0]["fx"]["pesos"], itens[1]["fx"]["pesos"])
        if ov["ok"]:
            st.caption(f"Sobreposição de carteira entre {itens[0]['id']} e {itens[1]['id']}: {_pp(ov['valor'], 1)}"
                       + (" (mínimo: só as maiores posições são divulgadas)" if ov.get("parcial") else "") + f" · ativos em comum: {', '.join(ov['comuns'][:8]) or 'nenhum'}.")
    _grafico({it["id"]: _base100(it["fx"]["serie"], max(x["fx"]["serie"].index[0] for x in itens)) for it in itens}, "Evolução na mesma janela (base 100)", f"fa_cmp_g_{fx['id']}")


def _aba_analise(fx, an):
    rel = an["relatorio"]
    for sec, frases in rel.items():
        st.markdown(f"**{sec}**")
        for fr in frases:
            st.markdown(f"- {fr}")
    st.caption(NOTA_LEGAL + " O relatório é gerado por regras sobre os números das outras abas; não considera seu perfil.")


def mostrar(fx: dict, atalho_comparar=None):
    """As 10 abas para um ETF ou fundo já preparado."""
    if fx.get("erro"):
        st.warning(f"Não consegui analisar {fx['id']}: {fx['erro']}.")
        for av in fx.get("avisos", []):
            st.caption("⚠️ " + av)
        return
    an = fa.analisar_tudo(fx)
    try:                                  # abertura padrão do app: nome, categoria, nota e os números que mais pesam
        from design import componentes as DC
        _r, _rk, _nt = an["rent"], an["risco"], an["nota"]
        _j = _r.get("janelas", {})
        _tom = "neutro" if _nt["nota"] is None else ("positivo" if _nt["nota"] >= 70 else "negativo" if _nt["nota"] < 50 else "neutro")
        st.markdown(DC.hero_ativo(str(fx["nome"]), " · ".join(x["rotulo"] for x in fx["rotulos"]) or "Categoria não identificada", "",
                                  "" if _nt["nota"] is None else f"Nota {_nt['nota']:.0f}/100", _tom,
                                  [("Retorno 12 meses", _p(_j.get("12 meses"))), ("Volatilidade anual", _p(_rk["vol"], 1, False)),
                                   ("Pior queda", _p(_rk["dd"]["max"])), ("Taxa de administração", _pp((fx.get("custos") or {}).get("taxa_adm")))]),
                    unsafe_allow_html=True)
    except Exception:
        st.markdown(f"### {fx['nome']}")
    try:                                  # resultado de cada análise na própria barra (as barras abrem e fecham)
        _rr, _rrk, _nn = an["rent"], an["risco"], an["nota"]
        _res = {"Visão geral": None if _nn["nota"] is None else f"Nota {_nn['nota']:.0f}/100",
                "Estratégia": (fx["rotulos"][0]["rotulo"] if fx.get("rotulos") else None),
                "Rentabilidade": f"12 meses {_p(_rr.get('janelas', {}).get('12 meses'))}",
                "Risco": f"vol. {_p(_rrk['vol'], 1, False)} · queda {_p(_rrk['dd']['max'])}",
                "Custos": f"taxa {_pp((fx.get('custos') or {}).get('taxa_adm'))}"}
        _res = {k: v for k, v in _res.items() if v}
    except Exception:
        _res = {}
    abas = profundidade_app.abas("fundo", ABAS, _res)
    if abas[0] is not None:
        with abas[0]:
            _aba_visao(fx, an, atalho_comparar)
    if abas[1] is not None:
        with abas[1]:
            _aba_indicadores(fx, an)
    if abas[2] is not None:
        with abas[2]:
            _aba_estrategia(fx, an)
    if abas[3] is not None:
        with abas[3]:
            _aba_composicao(fx, an)
    if abas[4] is not None:
        with abas[4]:
            _aba_rentabilidade(fx, an)
    if abas[5] is not None:
        with abas[5]:
            _aba_risco(fx, an)
    if abas[6] is not None:
        with abas[6]:
            _aba_custos(fx, an)
    if abas[7] is not None:
        with abas[7]:
            _aba_historico(fx, an)
    if abas[8] is not None:
        with abas[8]:
            _aba_comparacao(fx, an, atalho_comparar)
    if abas[9] is not None:
        with abas[9]:
            _aba_analise(fx, an)


# =============================================================================== páginas
def pagina_etfs(atalho_comparar=None, atalho_evolucao=None, botao_carteira=None):
    st.markdown(tema.cabecalho("🧺", "ETFs", "Fundos de índice negociados em bolsa, brasileiros e americanos: classificação, custos, "
                               "tracking, risco, carteira e comparação."), unsafe_allow_html=True)
    with st.form("form_fa_etf"):
        c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
        c1.text_input("ETF", key="fa_etf_q", label_visibility="collapsed", placeholder="Ex.: BOVA11, IVVB11, VOO, QQQ, SCHD, IMAB11")
        c2.form_submit_button("Analisar", type="primary", width="stretch")
    for col, t in zip(st.columns(len(ETFS_POPULARES)), ETFS_POPULARES):
        col.button(t, key=f"fa_pop_{t}", width="stretch", on_click=lambda x=t: st.session_state.update(fa_etf_q=x))
    tk = (st.session_state.get("fa_etf_q") or "").strip().upper().replace(".SA", "")
    if not tk:
        st.info("Digite o código de um ETF ou toque em um atalho.")
        return
    with st.spinner(f"Consultando {tk}..."):
        fx = preparar_etf(tk)
    if not fx.get("erro"):
        try:                                             # resumo automático da assistente (como na página antiga de ETFs)
            import assistente
            import mercados
            ind = mercados.indicadores_eua(fx["preco"])
            cu, dist = fx.get("custos") or {}, fx.get("distribuicao") or {}
            ind.update(taxa_txt=None if cu.get("taxa_adm") is None else _pp(cu["taxa_adm"]) + " ao ano",
                       pl_txt=fx.get("pl_texto"),
                       comp_txt=(f"divulgadas as {len(fx['pesos'])} maiores posições" if fx.get("pesos") else None),
                       div_txt=(dist.get("rotulo") if dist.get("tipo") == "distribuicao" else None), moeda=fx.get("moeda"))
            assistente.painel_resumo_auto(tk, lambda: assistente.resumo_etf(tk, ind))
        except Exception:
            pass
    if botao_carteira is not None and not fx.get("erro"):
        try:
            botao_carteira(tk, float(fx["preco"].dropna().iloc[-1]), "_etf")
        except Exception:
            pass
    mostrar(fx, atalho_comparar)
    if atalho_evolucao and not fx.get("erro"):
        atalho_evolucao(tk, "etf", "Evolução e crescimento deste ETF")


def pagina_fundos(chave: str, atalho_comparar=None):
    ic, nome, texto = FUNDOS[chave]
    st.markdown(tema.cabecalho(ic, nome, texto), unsafe_allow_html=True)
    filtro = FILTROS_CLASSE.get(chave)
    with st.form(f"form_fa_{chave}"):
        c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
        c1.text_input("Fundo", key=f"fa_q_{chave}", label_visibility="collapsed", placeholder="Nome do fundo ou CNPJ")
        c2.form_submit_button("Buscar", type="primary", width="stretch")
    q = (st.session_state.get(f"fa_q_{chave}") or "").strip()
    if not q:
        st.info("Digite parte do nome do fundo (ex.: “verde”, “itaú ações”) ou o CNPJ.")
        return
    cnpj = None
    if len(fd.so_digitos(q)) == 14 and fd.cnpj_valido(q):
        cnpj = fd.formatar_cnpj(q)
    else:
        with st.spinner("Lendo o cadastro de fundos da CVM (na primeira vez demora)..."):
            cad = _cadastro()
        for av in cad["avisos"]:
            st.caption("⚠️ " + av)
        res = buscar_fundos(q, cad["df"], filtro)
        if not res:
            st.warning("Nenhum fundo encontrado nesta classe com esse nome. Tente menos palavras ou digite o CNPJ.")
            return
        rot = {fd.formatar_cnpj(r["cnpj"]): f"{r['nome']} · {fd.formatar_cnpj(r['cnpj'])}" for r in res}
        cnpj = st.selectbox("Fundos encontrados", list(rot), format_func=lambda k: rot[k], key=f"fa_sel_{chave}")
    janela = st.radio("Histórico lido da CVM", ["1 ano", "3 anos", "5 anos"], index=1, horizontal=True, key=f"fa_jan_{chave}",
                      help="Quanto mais anos, mais arquivos mensais da CVM são lidos (demora na primeira vez, depois fica em cache).")
    meses = {"1 ano": 13, "3 anos": 37, "5 anos": 61}[janela]
    with st.spinner("Baixando o informe diário da CVM..."):
        fx = preparar_fundo(cnpj, meses)
    if filtro and not fx.get("erro") and not ({r["chave"] for r in fx.get("rotulos") or []} & CHAVES_CLASSE[chave]):
        st.caption("⚠️ Este CNPJ não parece ser da classe desta página; a análise vale pela classificação mostrada.")
    if not fx.get("erro"):
        botao_carteira_fundo(fx)
    mostrar(fx, atalho_comparar)


def botao_carteira_fundo(fx: dict):
    """Leva o fundo (por CNPJ) para a carteira escolhida (Virtual ou Real), guardando o CNPJ e o valor aplicado."""
    import carteira_destino as cd
    import moeda

    def _form(destino):
        vv = st.number_input("Valor aplicado (R$)", min_value=0.0, step=100.0, key=f"cwf_v_{fx['id']}")
        if not st.button("Confirmar", type="primary", key=f"cwf_ok_{fx['id']}"):
            return False
        if vv <= 0:
            st.error("Informe o valor aplicado.")
            return False
        d = cd.normalizar(destino)
        lista = st.session_state.setdefault(cd.CHAVE_FUNDOS[d], [])
        if d == cd.VIRTUAL:                                    # simulação respeita o caixa da carteira virtual
            gasto = moeda.custo_total_brl(st.session_state.get(cd.CHAVE_LOTES[d], []) or [])
            if gasto is None:
                st.error("Não consegui a cotação do dólar para conferir o caixa da carteira virtual. Tente de novo em instantes.")
                return False
            caixa = float(st.session_state.get("cart_capital", 100000.0)) - gasto - sum(float(x.get("valor", 0) or 0) for x in lista)
            if vv > caixa + 1e-9:
                st.error(f"Esse valor passa do caixa disponível na carteira virtual ({caixa:,.2f}).".replace(",", "X").replace(".", ",").replace("X", "."))
                return False
        lista.append({"cnpj": fx["id"], "valor": float(vv)})
        st.toast(f"Fundo adicionado à {cd.ROTULOS[d]}.", icon="✅")
        return True

    cd.popover_destino(f"f_{fx['id']}", _form)


# =============================================================================== ligação com o comparador (Passo 6)
def enriquecer_etf(a) -> None:
    """Acrescenta ao Ativo de ETF do comparador: taxa, patrimônio, tracking error, Sharpe, categoria (subgrupo) e fonte."""
    try:
        fx = preparar_etf(a.chave)
    except Exception as e:
        a.avisos.append(f"Dados adicionais do ETF indisponíveis ({e.__class__.__name__}).")
        return
    if fx.get("erro"):
        a.avisos.append("Dados adicionais do ETF: " + fx["erro"] + ".")
        return
    an = fa.analisar_tudo(fx)
    I = comparador.Ind
    cu = fx.get("custos") or {}
    a.ind["taxa_adm"] = I(cu.get("taxa_adm"), "dado", None, fx.get("data_ref"))
    a.ind["pl"] = I(fx.get("pl"), "dado", None, fx.get("data_ref"))
    a.ind["tracking_error"] = I(None if an["risco"].get("te") is None else an["risco"]["te"] * 100, "calculado", "período", fx.get("data_ref"))
    a.ind["sharpe"] = I(an["risco"].get("sharpe"), "calculado", "período", fx.get("data_ref"))
    if fx.get("rotulos"):
        a.subgrupo = fx["categoria"]
        a.subgrupo_nome = fa.ROTULOS_ETF.get(fx["categoria"], fx["categoria"])
    a.fonte = "Yahoo Finance"
    if fx.get("limpeza", {}).get("alterada"):                  # fonte com buracos: refaz retorno/risco com a série limpa
        a.ind.update(comparador.inds_de_preco(comparador.metricas_preco(fx["preco"])))
        a.avisos.append(fx["limpeza"]["aviso"])
    if cu.get("taxa_adm") is None:
        a.avisos.append("Taxa de administração sem dado na fonte: o pilar de custos fica fora da nota.")
    a.pontuacao = comparador.pontuar_etf(a.ind)


def ativo_fundo(cnpj: str) -> comparador.Ativo:
    """Fundo (CVM) como Ativo do comparador, classe 'fundo'."""
    cn = fd.formatar_cnpj(cnpj)
    try:
        fx = preparar_fundo(cn, 37)
    except Exception as e:
        return comparador.Ativo(cn, cn, "fundo", erro=f"erro inesperado ({e.__class__.__name__})")
    if fx.get("erro"):
        return comparador.Ativo(cn, fx["nome"], "fundo", erro=fx["erro"])
    an = fa.analisar_tudo(fx)
    ind = fa.inds_para_comparador(an["rent"], an["risco"], an["consist"], fx["custos"], fx.get("pl"), fx.get("data_ref"))
    a = comparador.Ativo(cn, fx["nome"], "fundo", "BRL", fx.get("data_ref"), "CVM", ind, subgrupo=fx.get("categoria") or "",
                         subgrupo_nome=fa.ROTULOS_FUNDO.get(fx.get("categoria"), fx.get("categoria") or ""))
    n = an["nota"]
    a.pontuacao = comparador.Pontuacao(n["nota"], {k: v for k, v in n["pilares"].items()}, n["pesos"], n["cobertura"], [],
                                       "Fundos: retorno, risco, consistência, custos e porte", n["provisoria"])
    a.avisos += fx["avisos"]
    if fx["bench"]["nome"]:
        a.avisos.append(f"Benchmark: {fx['bench']['nome']} ({fx['bench']['origem']}).")
    return a


# =============================================================================== carteira (Passo 10, seção 11)
def painel_carteira(lotes: list, valores: dict | None = None):
    """ETFs e fundos na carteira: exposição por classe, concentração e sobreposição entre ETFs, exposição indireta a ações já
    na carteira e correlação. Só mostra; não altera nada. `lotes`: lançamentos da carteira ({ticker, qtd, preco_medio})."""
    tks = list(dict.fromkeys((l.get("ticker") or "").upper().replace(".SA", "") for l in lotes if isinstance(l, dict) and l.get("ticker")))
    etfs = []
    for tk in tks:
        cl, conf = comparador.identificar_classe(tk)
        if cl != "etf" and conf == "provável" and re.fullmatch(r"[A-Z]{4}11", tk):       # XXXX11 fora da lista: o Yahoo diz se é ETF
            try:
                if _coleta_etf(_ticker_yahoo(tk))["info"].get("quoteType") == "ETF":
                    cl = "etf"
            except Exception:
                pass
        if cl == "etf":
            etfs.append(tk)
    st.caption("Mostra só o que a carteira já tem. Nada é comprado, vendido ou alterado por aqui.")
    fx_cart = moeda.cambio_serie() if any(isinstance(l, dict) and moeda.eh_dolar(l.get("ticker", "")) for l in lotes) else None
    valor_de = {}
    for l in lotes:
        if isinstance(l, dict) and l.get("ticker"):
            k = (l["ticker"] or "").upper().replace(".SA", "")
            valor_de[k] = valor_de.get(k, 0.0) + (moeda.custo_lote_brl(l, fx_cart) or 0.0)
    posicoes, series, nomes_etf = [], {}, {}
    if etfs:
        with st.spinner("Lendo os ETFs da carteira..."):
            for tk in etfs:
                fx = preparar_etf(tk)
                if fx.get("erro"):
                    st.caption(f"⚠️ {tk}: {fx['erro']}.")
                    continue
                nomes_etf[tk] = fx
                series[tk] = fx["serie"]
                posicoes.append({"nome": tk, "valor": valor_de.get(tk, 0.0), "pesos": fx.get("pesos"), "classe": fa.classe_de_ativo(fx["rotulos"])})
    st.markdown("**Fundos fora da bolsa (por CNPJ)**")
    fundos = st.session_state.setdefault("cart_fundos_cvm", [])
    with st.form("form_cart_fundo", clear_on_submit=True):
        c1, c2, c3 = st.columns([3, 2, 1.4], vertical_alignment="bottom")
        cn = c1.text_input("CNPJ do fundo")
        vv = c2.number_input("Valor aplicado (R$)", min_value=0.0, step=100.0)
        if c3.form_submit_button("Adicionar", width="stretch") and fd.cnpj_valido(cn) and vv > 0:
            fundos.append({"cnpj": fd.formatar_cnpj(cn), "valor": float(vv)})
            st.rerun()
    for i, f_ in enumerate(list(fundos)):
        cc = st.columns([5, 1.2])
        cc[0].caption(f"{f_['cnpj']} · {_grande(f_['valor'])}")
        if cc[1].button("Remover", key=f"cart_f_rm_{i}"):
            fundos.pop(i)
            st.rerun()
    for f_ in fundos:
        fx = preparar_fundo(f_["cnpj"], 37)
        if fx.get("erro"):
            st.caption(f"⚠️ {f_['cnpj']}: {fx['erro']}.")
            continue
        nomes_etf[f_["cnpj"]] = fx
        series[f_["cnpj"]] = fx["serie"]
        posicoes.append({"nome": fx["nome"], "valor": f_["valor"], "pesos": st.session_state.get(f"fa_pesos_{fd.so_digitos(f_['cnpj'])}"),
                         "classe": fa.classe_de_ativo(fx["rotulos"])})
    if not posicoes:
        st.info("Nenhum ETF ou fundo identificado na carteira. Adicione ETFs (ex.: BOVA11, VOO) ou fundos por CNPJ acima.")
        return
    total = sum(p["valor"] for p in posicoes)
    if total > 0:
        por_classe: dict[str, float] = {}
        for p in posicoes:
            por_classe[p["classe"]] = por_classe.get(p["classe"], 0.0) + p["valor"]
        st.markdown("**Exposição por classe de ativo (pela classificação de cada fundo/ETF)**")
        st.dataframe(pd.DataFrame({"Classe": list(por_classe), "% dos fundos/ETFs": [round(v / total * 100, 1) for v in por_classe.values()]}),
                     hide_index=True, width="stretch")
    # exposição indireta e sobreposição
    pos_pesos = [p for p in posicoes if p.get("pesos")]
    if pos_pesos:
        diretos = {k: v for k, v in valor_de.items() if k not in nomes_etf}
        ex = fa.exposicao_total(posicoes + [{"nome": k, "valor": v, "pesos": {k: 100.0}} for k, v in diretos.items() if v > 0])
        if ex["ok"]:
            top = ex["ativos"].head(10)
            st.markdown("**Maiores exposições somando posição direta + via ETFs/fundos**")
            st.dataframe(pd.DataFrame({"Ativo": top.index, "% da carteira": top.round(2).values}), hide_index=True, width="stretch")
            ind = [k for k in diretos if k in ex["ativos"].index and any(k in (p["pesos"] or {}) for p in pos_pesos)]
            if ind:
                st.warning("Exposição indireta a ativos que você já tem diretamente: " + ", ".join(ind) + ". Você está mais concentrado neles do que parece.")
            st.caption(f"{ex['sem_composicao_pct']:.0f}% do valor está em posições sem composição divulgada (não entram nas exposições).")
    if len(pos_pesos) >= 2:
        linhas = []
        for i in range(len(pos_pesos)):
            for j in range(i + 1, len(pos_pesos)):
                ov = fa.sobreposicao(pos_pesos[i]["pesos"], pos_pesos[j]["pesos"])
                if ov["ok"]:
                    linhas.append({"Par": f"{pos_pesos[i]['nome']} × {pos_pesos[j]['nome']}", "Sobreposição (%)": round(ov["valor"], 1),
                                   "Em comum": ", ".join(ov["comuns"][:5])})
        if linhas:
            st.markdown("**Sobreposição entre ETFs/fundos**")
            st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
            st.caption("Com composição parcial é um valor mínimo. Alta sobreposição = diversificação menor que a quantidade de fundos sugere.")
    corr = fa.correlacao_carteira(series)
    if not corr.empty:
        st.markdown("**Correlação semanal entre as posições**")
        st.dataframe(corr.round(2), width="stretch")
        st.caption("Perto de +1: andam juntas (pouca diversificação). Perto de 0 ou negativo: se compensam.")
