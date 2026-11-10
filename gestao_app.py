"""
Passo 12 — página "Gestão de carteira": painel, alocação, diversificação, risco, rentabilidade, renda passiva, otimização,
rebalanceamento, cenários e relatório, sobre a carteira que a pessoa já registrou no app.

Reaproveita (sem duplicar): lotes de carteira.py, preços/histórico/câmbio de dados.py, FIIs (fiis_app), ETFs e fundos (fundos_app e
fundos_analise), renda fixa (renda_fixa e renda_fixa_app), CDI/IPCA (evolucao.coletar_bcb). Os cálculos puros ficam em gestao.py e
gestao_otimiza.py. SOMENTE LEITURA e simulação: nenhuma posição é alterada e nenhuma ordem é enviada. Os únicos dados gravados são
as preferências da própria tela (metas por classe, tolerâncias, limites) e as vendas/retiradas que a pessoa registrar.
"""
from __future__ import annotations

import json
import math
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st
import secoes

import comparador
import dados
import evolucao
import fiis_app
import fundos_analise as fa
import fundos_app
import gestao as g
import moeda
import gestao_otimiza as o
import renda_fixa as rf
import renda_fixa_app as rfa
import tema
from renda_fixa_app import _n, _p, _r
from design import componentes as DC

try:
    import recursos as rec
except Exception:
    rec = None



class _Plotly:
    """plotly só é carregado quando um gráfico é desenhado (como em evolucao.py): importar o módulo não exige plotly."""

    def __getattr__(self, nome):
        import plotly.graph_objects as _go
        return getattr(_go, nome)


go = _Plotly()
ABAS = ["Painel", "Alocação", "Diversificação", "Risco", "Rentabilidade", "Renda passiva", "Otimização", "Rebalanceamento",
        "Cenários", "Relatório"]
MIN_DIAS_XIRR = 90
K_ALVOS, K_TOL, K_LIM = "cart_alvos", "cart_tol", "cart_lim"
K_VENDAS = {"cart_real": "cart_vendas_real", "cart_ficticia": "cart_vendas_ficticia"}
TRANSP = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=40, b=10))
NOTA = ("Ferramenta educacional, não é recomendação de investimento. Estatísticas históricas não garantem o futuro; simulações "
        "dependem das premissas mostradas. Nada aqui compra, vende ou altera sua carteira.")


def _cartoes(itens: list, por_linha: int = 4):
    for k in range(0, len(itens), por_linha):
        for col, (rot, val, cls, *det) in zip(st.columns(por_linha), itens[k:k + por_linha]):
            col.markdown(tema.card_status(rot, val, cls, det[0] if det else "", det[1] if len(det) > 1 else ""), unsafe_allow_html=True)


def _padrao(chave: str, valor) -> dict:
    """value= só na primeira vez: com a chave já na sessão o Streamlit avisa se receber os dois."""
    return {} if chave in st.session_state else {"value": valor}


# =============================================================================== coleta (cache; só leitura)
@st.cache_data(ttl=900, show_spinner=False)
def _info(tk: str) -> dict:
    try:
        d = dados.buscar_yahoo(tk)
        return {"preco": d.get("preco"), "nome": d.get("nome") or tk, "moeda": d.get("moeda"), "setor": d.get("setor")}
    except Exception:
        return {"preco": None, "nome": tk, "moeda": None, "setor": None}


@st.cache_data(ttl=3600, show_spinner=False)
def _proventos_papel(tk: str) -> pd.DataFrame:
    try:
        res, _ = dados._chart_yahoo(tk, "5y", "1d", "div")
        return g.parse_proventos_chart(res)
    except Exception:
        return pd.DataFrame(columns=["data", "valor"])


@st.cache_data(ttl=3600, show_spinner=False)
def _cambio() -> pd.Series:
    try:
        return dados.serie_cambio()
    except Exception:
        return pd.Series(dtype=float)


@st.cache_data(ttl=3600, show_spinner=False)
def _referencias() -> dict:
    """Benchmarks em R$ (índices do Yahoo e do BCB). O que faltar vem vazio e a tela avisa."""
    out, av = {}, []
    b = evolucao.coletar_bcb()
    if len(b.get("cdi_idx", [])):
        out["CDI"] = b["cdi_idx"]
    else:
        av.append("CDI indisponível agora.")
    for nome, sim in (("Ibovespa", "^BVSP"), ("S&P 500 (em R$)", "^GSPC")):
        try:
            s = fundos_app._serie_yahoo(sim)
        except Exception:
            s = pd.Series(dtype=float)
        if len(s):
            out[nome] = s
        else:
            av.append(f"{nome} indisponível agora.")
    fx = _cambio()
    if "S&P 500 (em R$)" in out and len(fx):
        sp = out["S&P 500 (em R$)"]
        sp = pd.Series(sp.values, index=pd.DatetimeIndex(sp.index).tz_localize(None).normalize())
        sp = sp[~sp.index.duplicated(keep="last")]
        out["S&P 500 (em R$)"] = sp * fx.reindex(sp.index.union(fx.index)).ffill().reindex(sp.index)
    elif "S&P 500 (em R$)" in out:
        del out["S&P 500 (em R$)"]
        av.append("S&P 500 em R$ indisponível (sem câmbio).")
    if len(fx):
        out["Dólar"] = fx
    return {"series": out, "avisos": av}


def _historico(tk: str) -> pd.Series:
    import carteira as cart_mod          # carteira.py carrega plotly no topo: só entra aqui, quando há histórico a buscar
    return cart_mod._hist(tk, "5y")


def _classe_do_ticker(tk: str, fii_lista) -> tuple[str, str]:
    """(classe, motivo). Código de FII da lista do Fundamentus → FII; BDR pelo formato; ETF pelo catálogo ou pelo tipo no Yahoo."""
    if g.eh_bdr(tk):
        return "bdr", "formato de BDR"
    if fii_lista is not None and tk in fii_lista:
        return "fii", "lista de FIIs"
    cl, conf = comparador.identificar_classe(tk, getattr(rec, "TODOS_TICKERS", []) if rec is not None else [])
    if cl == "acao" and conf == "provável" or (cl == "fii" and conf == "provável"):
        import re
        if re.fullmatch(r"[A-Z]{4}11", tk):
            try:
                if fundos_app._coleta_etf(fundos_app._ticker_yahoo(tk))["info"].get("quoteType") == "ETF":
                    return "etf", "tipo ETF no Yahoo"
            except Exception:
                pass
    return ("fii" if cl == "fii" else cl), "formato do código" if conf == "provável" else "lista conhecida"


def _fx_em(fx: pd.Series, d) -> float | None:
    if fx is None or fx.empty:
        return None
    f = fx.loc[:pd.Timestamp(d)]
    return float(f.iloc[-1]) if len(f) else float(fx.iloc[0])


@st.cache_data(ttl=600, show_spinner=False)
def coletar(lotes_json: str, vendas_json: str, rf_json: str, fundos_json: str, caixa: float | None, hoje_iso: str) -> dict:
    """Junta tudo o que a página precisa. Cada falha vira aviso: nunca preenche dado ausente."""
    hoje = date.fromisoformat(hoje_iso)
    lotes, vendas = json.loads(lotes_json), json.loads(vendas_json)
    titulos_rf = [rf.Titulo.de_dict(d) for d in json.loads(rf_json)]
    fundos = json.loads(fundos_json)
    C: dict = {"hoje": hoje, "avisos": [], "posicoes": [], "series": {}, "classes": {}, "moedas": {}}
    movs, av = g.normalizar_movs(lotes, vendas)
    C["avisos"] += av
    C["movs"] = movs
    fx = _cambio()
    C["cambio"] = fx
    lista = fiis_app.lista_fiis()
    fiis_idx = set(lista["df"].index) if isinstance(lista.get("df"), pd.DataFrame) and not lista["df"].empty else set()
    fii_df = lista["df"] if fiis_idx else None
    if lista.get("aviso"):
        C["avisos"].append(lista["aviso"])
    # movimentos em R$ (câmbio da data) para custo e resultado de quem investe em reais
    moedas, classes = {}, {}
    infos = {}
    for tk in dict.fromkeys(m["ticker"] for m in movs):
        i = _info(tk)
        infos[tk] = i
        moedas[tk] = (i.get("moeda") or g.moeda_do_ticker(tk)).upper()
        moedas[tk] = "BRL" if moedas[tk] == "BRL" else moedas[tk]
        classes[tk], _ = _classe_do_ticker(tk, fiis_idx)
        if "-USD" in tk or "-BRL" in tk or "/" in tk:
            classes[tk] = "cripto"
    C["moedas"], C["classes"] = moedas, classes
    movs_brl = []
    for m in movs:
        f = 1.0 if moedas[m["ticker"]] == "BRL" else (_fx_em(fx, m["data"]) or float("nan"))
        movs_brl.append({**m, "preco": m["preco"] * f})
    pos_nat = g.posicoes_de_movs(movs)
    pos_brl = g.posicoes_de_movs([m for m in movs_brl if math.isfinite(m["preco"])])
    fx_atual = float(fx.iloc[-1]) if len(fx) else None
    precos = {}
    for tk, e in pos_nat.items():
        i = infos[tk]
        s = _historico(tk)
        if len(s):
            precos[tk] = s
        if e["qtd"] <= 0:
            continue
        preco = i.get("preco")
        mo = moedas[tk]
        cambio = 1.0 if mo == "BRL" else fx_atual
        valor = e["qtd"] * preco * cambio if preco and cambio else None
        cl = classes[tk]
        setor = g.SETORES_PT.get(i.get("setor") or "", i.get("setor")) if cl in ("acao", "bdr") else None
        if cl == "fii" and fii_df is not None and tk in fii_df.index:
            setor = fii_df.loc[tk].get("segmento_nome") or "FIIs"
        setor = setor or {"etf": "ETFs", "cripto": "Criptomoedas", "fii": "FIIs", "fundo": "Fundos"}.get(cl, "Não informado")
        d_preco = s.index[-1].date() if len(s) else None
        C["posicoes"].append({
            "id": tk, "nome": i.get("nome") or tk, "classe": cl, "moeda": mo, "pais": g.pais_do_ticker(tk, cl), "setor": setor,
            "emissor": None, "gestor": None, "qtd": e["qtd"], "preco": preco, "cambio": cambio, "valor": valor,
            "custo": pos_brl.get(tk, {}).get("custo"), "data_preco": d_preco, "realizado": pos_brl.get(tk, {}).get("realizado", 0.0),
            "fonte": "Yahoo Finance"})
    C["precos_brl"], av = g.precos_em_brl(precos, moedas, fx)
    C["avisos"] += av
    C["fluxos"] = g.fluxos_externos(movs, moedas, fx)

    # renda fixa (curva) e fundos por CNPJ
    C["rf"], C["rf_fluxos"], C["rf_eventos"] = [], [], []
    if titulos_rf:
        try:
            m = rfa.mercado()
            cen = rfa.cenarios(m)["hoje"]
            for t in titulos_rf:
                cur = rf.valor_na_curva(t, m, cen, hoje) if t.aplicacao < hoje else {"ok": True, "valor_atual": t.valor}
                if not cur.get("ok") or not cur.get("valor_atual"):
                    continue
                dur = None
                try:
                    a = rfa.analisar(t, m, cen, hoje)
                    dur = (a.get("mam") or {}).get("mod") if a.get("ok") else None
                except Exception:
                    pass
                emissor = t.emissor or ("Tesouro Nacional" if t.t.grupo == "tesouro" else "Emissor não informado")
                C["posicoes"].append({
                    "id": rfa.codigo_de(t), "nome": t.rotulo(), "classe": "renda_fixa", "moeda": "BRL", "pais": "Brasil", "setor": "Renda fixa",
                    "emissor": emissor, "gestor": None, "qtd": 1.0, "preco": cur["valor_atual"], "cambio": 1.0, "valor": cur["valor_atual"],
                    "custo": t.valor, "data_preco": hoje, "indexador": t.indexador, "duracao": dur,
                    "liquidez_dias": rf.dias_ate_liquidez(t, hoje), "credito": rf.risco_credito(t)["nivel"], "fgc": bool(t.t.fgc),
                    "vencimento": t.vencimento, "aplicacao": t.aplicacao, "fonte": "Curva do título (renda fixa)"})
                fl = rf.fluxos(t, cen, m, hoje)
                if fl is not None and not fl.empty:
                    tipo = "amortizacao" if t.tipo in ("tesouro_renda", "tesouro_educa") else (
                        "cupom" if t.t.grupo == "tesouro" else "juros")
                    periodico = rf._pagamento(t) != "vencimento"          # tudo no vencimento = devolução do capital, não renda
                    coluna = "total" if t.tipo in ("tesouro_renda", "tesouro_educa") else "juros"   # parcelas Renda+/Educa+ são renda; demais, só os juros
                    for r in fl.itertuples():
                        d = g._data(r.data)
                        v = getattr(r, coluna, None)
                        if not periodico or d is None or not _fin(v) or v <= 0:
                            continue
                        if r.passado and d <= hoje:
                            C["rf_eventos"].append({"data": d, "fonte": rfa.codigo_de(t), "valor": float(v), "tipo": tipo, "efetivo": True})
                        elif d > hoje:
                            C["rf_fluxos"].append({"data": d, "valor": float(v), "fonte": rfa.codigo_de(t)})
                C["rf"].append(t)
        except Exception as e:
            C["avisos"].append(f"Renda fixa não pôde ser lida agora ({e.__class__.__name__}).")
    C["fundos"] = []
    for f_ in fundos:
        try:
            fx_ = fundos_app.preparar_fundo(f_["cnpj"], 37)
        except Exception as e:
            C["avisos"].append(f"Fundo {f_.get('cnpj')}: {e.__class__.__name__}.")
            continue
        if fx_.get("erro"):
            C["avisos"].append(f"Fundo {f_['cnpj']}: {fx_['erro']}.")
        cl_ativo = fa.classe_de_ativo(fx_.get("rotulos") or []) if not fx_.get("erro") else "Não classificado"
        C["posicoes"].append({
            "id": f_["cnpj"], "nome": fx_.get("nome") or f_["cnpj"], "classe": "fundo", "moeda": "BRL", "pais": "Brasil",
            "setor": cl_ativo, "emissor": fx_.get("nome") or f_["cnpj"], "gestor": (fx_.get("cad") or {}).get("gestor") or "Não informado",
            "qtd": 1.0, "preco": f_["valor"], "cambio": 1.0, "valor": float(f_["valor"]), "custo": float(f_["valor"]),
            "data_preco": None, "fonte": "CVM (valor informado por você)", "categoria": fx_.get("categoria")})
        if fx_.get("serie") is not None and len(fx_["serie"]) > 60:
            C["series"][f_["cnpj"]] = fx_["serie"]
    if caixa is not None and caixa > 0:
        C["posicoes"].append({"id": "CAIXA", "nome": "Caixa da simulação", "classe": "caixa", "moeda": "BRL", "pais": "Brasil", "setor": "Caixa",
                              "emissor": "Caixa", "gestor": None, "qtd": 1.0, "preco": caixa, "cambio": 1.0, "valor": float(caixa),
                              "custo": float(caixa), "data_preco": hoje, "fonte": "Capital inicial − compras"})
    # proventos pagos pelos papéis de mercado
    prov = {tk: _proventos_papel(tk) for tk in pos_nat if classes.get(tk) not in ("cripto",)}
    C["prov_papel"] = prov
    C["eventos"] = g.proventos_recebidos(movs, prov, moedas, classes, fx, hoje) + C["rf_eventos"]
    C["referencias"] = _referencias()
    return C


def _fin(x) -> bool:
    try:
        return math.isfinite(float(x))
    except (TypeError, ValueError):
        return False


# =============================================================================== derivados (rápidos, sem rede)
def _series_historicas(C: dict) -> dict:
    """Valor da carteira, retornos por ativo e série de CDI para as estatísticas. Tudo do que já foi coletado."""
    D: dict = {"avisos": []}
    P = C["precos_brl"]
    ativos_pos = {p["id"]: p for p in C["posicoes"]}
    series = {tk: P[tk].dropna() for tk in P.columns if tk in ativos_pos}
    series.update({k: v for k, v in C["series"].items() if k in ativos_pos})
    D["rets"] = g.matriz_retornos(series, 60)
    D["series"] = series
    pesos = {p["id"]: p["valor"] for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0}
    tot = sum(pesos.values())
    D["pesos_total"] = pd.Series({k: v / tot for k, v in pesos.items()}) if tot > 0 else pd.Series(dtype=float)
    cdi = C["referencias"]["series"].get("CDI")
    D["cdi_diario"] = cdi.pct_change().dropna() if cdi is not None and len(cdi) else None
    sel_mkt = [m for m in C["movs"]]
    if C["precos_brl"].empty or not sel_mkt:
        D["twr_preco"] = D["twr_total"] = {"ok": False, "motivo": "sem histórico de preços"}
        D["valor_hist"] = pd.Series(dtype=float)
        return D
    qtd = g.quantidades_no_tempo(sel_mkt, C["precos_brl"].index)
    vh, av = g.valor_historico(qtd, C["precos_brl"])
    D["avisos"] += av
    D["valor_hist"] = vh
    fl = [(d, v) for d, v in C["fluxos"] if True]
    # só fluxos dos ativos que entraram na série de valor
    cols = set(C["precos_brl"].columns)
    mov_ok = [m for m in sel_mkt if m["ticker"] in cols]
    fl = g.fluxos_externos(mov_ok, C["moedas"], C["cambio"])
    D["fluxos_mercado"] = fl
    ev_mkt = [e for e in C["eventos"] if e["fonte"] in cols]
    D["eventos_mercado"] = ev_mkt
    D["twr_preco"] = g.twr(vh, fl)
    D["twr_total"] = g.twr(vh, fl, g.acumulado_proventos(ev_mkt))
    return D


def _beta_historico(C: dict, D: dict) -> dict:
    ibov = C["referencias"]["series"].get("Ibovespa")
    out = {}
    if ibov is None or not len(ibov):
        return out
    rb = ibov.copy()
    rb.index = pd.DatetimeIndex(rb.index).tz_localize(None).normalize() if pd.DatetimeIndex(rb.index).tz is not None else pd.DatetimeIndex(rb.index).normalize()
    rb = rb[~rb.index.duplicated(keep="last")].pct_change().dropna()
    for tk in D["rets"].columns:
        p = next((x for x in C["posicoes"] if x["id"] == tk), None)
        if p and p["classe"] in ("acao", "etf", "fundo", "fii") and p["moeda"] == "BRL":
            b = g.beta(D["rets"][tk], rb, 120)
            if b is not None:
                out[tk] = b
    return out


# =============================================================================== apresentação comum
def _pie(nomes, valores, titulo, altura=300):
    fig = go.Figure(go.Pie(labels=nomes, values=valores, hole=0.55, textinfo="label+percent"))
    fig.update_layout(title=dict(text=titulo, x=0.02, xanchor="left"), height=altura, showlegend=False,
                      **{**TRANSP, "margin": dict(l=10, r=10, t=64, b=10)})
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _dist_view(posicoes: list[dict], campo: str, titulo: str, chave: str, rotulo=lambda x: x):
    d = g.distribuicao(posicoes, campo)
    if not d:
        st.caption("Sem dados.")
        return
    modo = st.radio("Ver como", ["Gráfico", "Tabela"], horizontal=True, key=f"gc_v_{chave}", label_visibility="collapsed")
    if modo == "Gráfico":
        _pie([rotulo(x["nome"]) for x in d], [x["valor"] for x in d], titulo)
    else:
        st.dataframe(pd.DataFrame([{titulo: rotulo(x["nome"]), "Valor": _r(x["valor"]), "%": _p(x["pct"], 1)} for x in d]),
                     hide_index=True, width="stretch")


def _graf_linhas(series: dict, titulo: str, suf: str = ""):
    st.plotly_chart(evolucao.grafico_linhas(series, titulo, suf), width="stretch", config={"displayModeBar": False})


def _base100(s: pd.Series, ini) -> pd.Series:
    x = s.copy()
    x.index = pd.DatetimeIndex(x.index).normalize()
    x = x[~x.index.duplicated(keep="last")]
    x = x[x.index >= pd.Timestamp(ini)]
    return x / x.iloc[0] * 100 if len(x) else x


# =============================================================================== abas
def _aba_painel(C, D, chave_cart):
    pos = C["posicoes"]
    vals = [p for p in pos if _fin(p.get("valor")) and p["valor"] > 0]
    total = sum(p["valor"] for p in vals)
    custo = sum(p["custo"] for p in vals if _fin(p.get("custo")))
    res = total - custo
    ev = [e for e in C["eventos"] if e.get("efetivo")]
    rp = o.renda_passiva(ev, C["hoje"])
    tw = D.get("twr_total", {})
    xir = _xirr_total(C)
    _cartoes([("Patrimônio total", _r(total), "info", f"{len(vals)} posição(ões)"),
              ("Valor investido", _r(custo), "info", "custo médio em R$"),
              ("Lucro/prejuízo", _r(res), "good" if res >= 0 else "bad", _p(res / custo, 2, True) if custo > 0 else ""),
              ("Proventos recebidos", _r(rp["total"]) if rp.get("ok") else "n/d", "info", "desde a primeira compra")], por_linha=2)
    _cartoes([("Renda passiva (média/mês)", _r(rp["media_mensal_12m"]) if rp.get("ok") else "n/d", "info", "últimos 12 meses"),
              ("Renda passiva (12 meses)", _r(rp["ultimos_12m"]) if rp.get("ok") else "n/d", "info", ""),
              ("Retorno TWR", _p(tw.get("total"), 2, True) if tw.get("ok") else "n/d", "info", "ativos de mercado, com proventos"),
              ("Retorno XIRR a.a.", _p(xir, 2, True) if xir is not None else "n/d", "info", "ponderado pelo dinheiro" if xir is not None else f"precisa de {MIN_DIAS_XIRR}+ dias de histórico")], por_linha=2)
    for q in g.avaliar_qualidade(pos, C["hoje"]):
        st.warning(q)
    for a in C["avisos"] + D.get("avisos", []):
        st.caption("⚠️ " + a)
    st.markdown("#### Posições")
    linhas = []
    for p in sorted(vals, key=lambda x: -x["valor"]):
        linhas.append({"Ativo": p["id"], "Classe": g.CLASSES.get(p["classe"], p["classe"]), "Qtd": p["qtd"] if p["classe"] not in ("renda_fixa", "fundo", "caixa") else None,
                       "Preço atual": p.get("preco") if p["classe"] not in ("renda_fixa", "fundo", "caixa") else None, "Moeda": p["moeda"],
                       "Valor (R$)": p["valor"], "Peso (%)": p["valor"] / total * 100,
                       "Resultado (%)": (p["valor"] / p["custo"] - 1) * 100 if _fin(p.get("custo")) and p["custo"] > 0 else None})
    if linhas:
        def _num(v, casas=2):
            return "—" if v is None or (isinstance(v, float) and math.isnan(v)) else f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
        cab = ["Ativo", "Qtd", "Preço atual", "Valor", "Peso", "Resultado"]
        corpo = []
        for x in linhas:
            corpo.append([f"{x['Ativo']} · {x['Classe']}", _num(x["Qtd"], 4).rstrip("0").rstrip(",") if x["Qtd"] is not None else None,
                          f"{x['Moeda']} {_num(x['Preço atual'])}" if x["Preço atual"] is not None else None, _r(x["Valor (R$)"]),
                          _num(x["Peso (%)"], 1) + "%", (_num(x["Resultado (%)"], 1) + "%") if x["Resultado (%)"] is not None else None])
        if hasattr(DC, "tabela_cartoes"):
            st.markdown(DC.tabela_cartoes(cab, corpo), unsafe_allow_html=True)
        else:    # módulo de design antigo ainda carregado: mostra como tabela comum até o app reiniciar
            st.dataframe(pd.DataFrame(corpo, columns=cab), hide_index=True, width="stretch")
    sem = [p["id"] for p in pos if not _fin(p.get("valor")) or p["valor"] <= 0]
    if sem:
        st.caption("Sem cotação (fora do valor): " + ", ".join(sem))
    st.markdown("#### Distribuição")
    abas = secoes.abas(["Classe", "Setor", "País", "Moeda", "Emissor / gestor"])
    with abas[0]:
        _dist_view(vals, "classe", "Classe", "classe", lambda x: g.CLASSES.get(x, x))
    with abas[1]:
        _dist_view(vals, "setor", "Setor", "setor")
    with abas[2]:
        _dist_view(vals, "pais", "País", "pais")
    with abas[3]:
        _dist_view(vals, "moeda", "Moeda", "moeda")
    with abas[4]:
        com = [p for p in vals if p["classe"] in ("renda_fixa", "fundo")]
        if com:
            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Emissor** (renda fixa)")
                _dist_view([p for p in com if p["classe"] == "renda_fixa"], "emissor", "Emissor", "emissor")
            with c2:
                st.markdown("**Gestor** (fundos por CNPJ)")
                _dist_view([p for p in com if p["classe"] == "fundo"], "gestor", "Gestor", "gestor")
        else:
            st.caption("Aparece quando houver renda fixa (emissor) ou fundos por CNPJ (gestor). Para ações, FIIs e ETFs a empresa/fundo já é o ativo.")
    _vendas(C, chave_cart)


def _xirr_total(C) -> float | None:
    """XIRR do patrimônio: aportes (−), vendas (+), proventos (+), e o valor de hoje (+). Fundos por CNPJ e caixa ficam fora
    (não têm data de aplicação)."""
    fl = []
    ids_mkt = {p["id"] for p in C["posicoes"] if p["classe"] not in ("fundo", "caixa", "renda_fixa")}
    ativos = [m for m in C["movs"] if m["ticker"] in ids_mkt]
    for d, v in g.fluxos_externos(ativos, C["moedas"], C["cambio"]):
        fl.append((d, -v))
    for p in C["posicoes"]:
        if p["classe"] == "renda_fixa" and p.get("aplicacao"):
            fl.append((p["aplicacao"], -p["custo"]))
    for e in C["eventos"]:
        fl.append((e["data"], e["valor"]))
    fim = sum(p["valor"] for p in C["posicoes"] if p["classe"] not in ("fundo", "caixa") and _fin(p.get("valor")))
    if fim > 0:
        fl.append((C["hoje"], fim))
    datas = [g._data(d) for d, _ in fl if g._data(d)]
    if datas and (max(datas) - min(datas)).days < MIN_DIAS_XIRR:
        return None             # anualizar poucos dias engana (0,09% em 10 dias viraria +7% ao ano): só com 90+ dias de história
    return g.xirr(fl)


def _vendas(C, chave_cart):
    ss = st.session_state
    kv = K_VENDAS[chave_cart]
    ss.setdefault(kv, [])
    with st.expander("Registrar venda ou retirada (só registro: nada é negociado)"):
        st.caption("Para o desempenho considerar saídas de dinheiro. A posição é reduzida pelo custo médio. Fica salvo na sua conta.")
        tks = [p["id"] for p in C["posicoes"] if p["classe"] not in ("renda_fixa", "fundo", "caixa")]
        if not tks:
            st.caption("Sem posições de mercado para vender.")
        else:
            c1, c2, c3, c4 = st.columns([1.4, 1, 1.2, 1.2])
            tk = c1.selectbox("Ativo", tks, key="gc_v_tk")
            qtd = c2.number_input("Quantidade", min_value=0.0, step=1.0, key="gc_v_q")
            pr = c3.number_input("Preço de venda", min_value=0.0, step=0.01, key="gc_v_p")
            dt = c4.date_input("Data", value=date.today(), max_value=date.today(), format="DD/MM/YYYY", key="gc_v_d")
            if st.button("Registrar", key="gc_v_ok"):
                atual = next((p["qtd"] for p in C["posicoes"] if p["id"] == tk), 0.0)
                if qtd <= 0 or pr <= 0:
                    st.error("Informe quantidade e preço maiores que zero.")
                elif qtd > atual + 1e-9:
                    st.error(f"Você tem {atual:g} de {tk}: não dá para registrar a venda de {qtd:g}.")
                else:
                    ss[kv].append({"ticker": tk, "qtd": float(qtd), "preco_medio": float(pr), "data": dt.isoformat()})
                    st.rerun()
        if ss[kv]:
            st.dataframe(pd.DataFrame(ss[kv]).rename(columns={"ticker": "Ativo", "qtd": "Qtd", "preco_medio": "Preço", "data": "Data"}),
                         hide_index=True, width="stretch")
            i = st.selectbox("Remover registro", range(len(ss[kv])), key="gc_v_rm",
                             format_func=lambda k: f"{ss[kv][k]['ticker']} · {ss[kv][k]['qtd']:g} · {ss[kv][k]['data']}")
            if st.button("Remover", key="gc_v_rmb"):
                ss[kv].pop(i)
                st.rerun()


def _alvos_atuais() -> dict:
    return dict(st.session_state.get(K_ALVOS) or {})


def _aba_alocacao(C, D):
    pos = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
    if not pos:
        st.info("Sem posições com valor.")
        return
    ss = st.session_state
    lim_salvo = ss.get(K_LIM) or {}
    with st.expander("Limites dos alertas de concentração (referências suas)"):
        c = st.columns(3)
        lim = {}
        defs = [("ativo", "Por ativo (%)", 20), ("setor", "Por setor (%)", 40), ("classe", "Por classe (%)", 80), ("emissor", "Por emissor (%)", 25),
                ("exterior", "No exterior (%)", 60), ("moeda_estrangeira", "Em moeda estrangeira (%)", 60), ("fator", "Por fator de risco (%)", 60)]
        for i, (k, rot, d) in enumerate(defs):
            lim[k] = c[i % 3].number_input(rot, min_value=1.0, max_value=100.0, step=1.0, key=f"gc_lim_{k}",
                                           **_padrao(f"gc_lim_{k}", float(lim_salvo.get(k, d / 100) * 100 if k in lim_salvo else d))) / 100
        ss[K_LIM] = lim
    for p in pos:
        p["fator"] = g.fator_de_risco(p)
    conc = g.concentracao([p["valor"] for p in pos])
    _cartoes([("Ativos efetivos", _n(conc["n_efetivo"], 1), "info", f"de {conc['n']} posições (1/HHI)"),
              ("Maior posição", _p(conc["top1"], 0), "bad" if conc["top1"] > lim["ativo"] else "good", ""),
              ("3 maiores", _p(conc["top3"], 0), "info", ""),
              ("HHI", _n(conc["hhi"], 3), "info", "Σ pesos², 1 = tudo em um ativo")], por_linha=2)
    st.markdown("#### Pontos de atenção")
    al = g.avaliar_concentracao(pos, lim)
    if not al:
        st.success("Nenhum limite ultrapassado.")
    for a in al:
        st.warning(a["texto"])
    st.markdown("#### Dependência de fatores econômicos")
    d = g.distribuicao(pos, "fator")
    st.dataframe(pd.DataFrame([{"Fator": x["nome"], "Valor": _r(x["valor"]), "%": _p(x["pct"], 1)} for x in d]), hide_index=True, width="stretch")
    st.caption("Fator = a principal fonte de retorno e de risco da posição (bolsa brasileira, bolsa do exterior e dólar, juros, imóveis…). "
               "Posições no mesmo fator tendem a cair juntas.")
    st.markdown("#### Meta de alocação por classe")
    atual = g.distribuicao(pos, "classe")
    classes = list(dict.fromkeys([x["nome"] for x in atual] + [k for k in ("acao", "fii", "etf", "cripto", "renda_fixa") if k not in [y["nome"] for y in atual]]))
    salvo, tols = _alvos_atuais(), dict(ss.get(K_TOL) or {})
    st.caption("Informe o percentual desejado para cada classe (soma 100%) e a tolerância em pontos percentuais. Fica salvo na sua conta.")
    novos, novas_tol = {}, {}
    for c_ in classes:
        a, b = st.columns(2)
        novos[c_] = a.number_input(f"{g.CLASSES.get(c_, c_)} — alvo (%)", min_value=0.0, max_value=100.0, step=1.0, key=f"gc_alvo_{c_}",
                                   **_padrao(f"gc_alvo_{c_}", float(salvo.get(c_, 0.0))))
        novas_tol[c_] = b.number_input("Tolerância (± p.p.)", min_value=0.0, max_value=50.0, step=0.5, key=f"gc_tol_{c_}",
                                       **_padrao(f"gc_tol_{c_}", float(tols.get(c_, 5.0))))
    soma = sum(novos.values())
    if abs(soma - 100) > 0.01:
        st.info(f"Os alvos somam {soma:.1f}%. Ajuste para 100% para ver a comparação.")
        ss[K_TOL] = novas_tol
        return
    ss[K_ALVOS], ss[K_TOL] = novos, novas_tol
    vals = {x["nome"]: x["valor"] for x in atual}
    des = g.desvios_do_alvo(vals, novos, novas_tol)
    st.dataframe(pd.DataFrame([{"Classe": g.CLASSES.get(x["classe"], x["classe"]), "Atual (%)": x["atual"], "Alvo (%)": x["alvo"], "Desvio (p.p.)": x["desvio"],
                                "Situação": {"dentro": "dentro da tolerância", "acima": "acima do alvo", "abaixo": "abaixo do alvo"}[x["status"]]}
                               for x in des]), hide_index=True, width="stretch",
                 column_config={k: st.column_config.NumberColumn(format="%.1f") for k in ("Atual (%)", "Alvo (%)", "Desvio (p.p.)")})
    fig = go.Figure()
    nomes = [g.CLASSES.get(x["classe"], x["classe"]) for x in des]
    fig.add_bar(x=nomes, y=[x["atual"] for x in des], name="Atual")
    fig.add_bar(x=nomes, y=[x["alvo"] for x in des], name="Alvo")
    fig.update_layout(title="Alocação atual × alvo (%)", barmode="group", height=320, legend=dict(orientation="h", y=-0.2), **TRANSP)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _cobertura(C, D):
    P = D["pesos_total"]
    cols = [c for c in D["rets"].columns if c in P.index]
    return float(P[cols].sum()) if cols else 0.0


def _aba_diversificacao(C, D):
    rets = D["rets"]
    if rets.empty or rets.shape[1] < 2:
        st.info("A análise de correlação precisa de pelo menos 2 ativos com histórico de preço em comum (≥ 60 dias).")
    else:
        P = D["pesos_total"]
        cols = [c for c in rets.columns if c in P.index]
        w = P[cols] / P[cols].sum()
        cov = o.covariancia(rets[cols], False)
        corr = g.correlacao(rets[cols])
        enb = g.n_efetivo_de_apostas(w, cov)
        cm = g.correlacao_media(corr, w)
        _cartoes([("Ativos com histórico", str(len(cols)), "info", f"{len(rets)} dias em comum"),
                  ("Apostas independentes", _n(enb, 1) if enb else "n/d", "good" if enb and enb >= 0.6 * len(cols) else "fair", "número efetivo (Meucci)"),
                  ("Correlação média", _n(cm, 2) if cm is not None else "n/d", "bad" if cm and cm > 0.6 else "info", "ponderada pelos pesos"),
                  ("Cobertura", _p(_cobertura(C, D), 0), "info", "do patrimônio nesta análise")], por_linha=2)
        st.markdown("#### Correlação entre ativos")
        fig = go.Figure(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index), zmin=-1, zmax=1, colorscale="RdBu_r",
                                   text=np.round(corr.values, 2), texttemplate="%{text}"))
        fig.update_layout(height=max(320, 50 * len(cols)), **TRANSP)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        st.caption("Correlação dos retornos diários no período em comum. Perto de 1: andam juntos; perto de 0: independentes; negativa: se compensam.")
        pares = g.pares_correlacionados(corr, 0.8)
        for a, b, v in pares[:5]:
            st.warning(f"{a} e {b}: correlação {_n(v, 2)} — contam como quase a mesma aposta.")
        if enb is not None and enb < max(2.0, 0.4 * len(cols)):
            st.warning(f"Diversificação menor do que parece: {len(cols)} ativos, mas só ≈ {_n(enb, 1)} apostas independentes.")
        cl_series = {}
        for cl in {p["classe"] for p in C["posicoes"]}:
            ids = [c for c in cols if next((p["classe"] for p in C["posicoes"] if p["id"] == c), None) == cl]
            if ids:
                ww = w[ids] / w[ids].sum()
                cl_series[g.CLASSES.get(cl, cl)] = (rets[ids] * ww).sum(axis=1)
        if len(cl_series) >= 2:
            st.markdown("#### Correlação entre classes")
            cc = pd.DataFrame(cl_series).corr()
            st.dataframe(cc.round(2), width="stretch")
    pos = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
    for p in pos:
        p["fator"] = g.fator_de_risco(p)
    fat = g.distribuicao(pos, "fator")
    if fat:
        st.markdown("#### Fatores de risco")
        st.dataframe(pd.DataFrame([{"Fator": x["nome"], "%": _p(x["pct"], 1)} for x in fat]), hide_index=True, width="stretch")
        if fat[0]["pct"] > 0.6:
            st.warning(f"{_p(fat[0]['pct'], 0)} do patrimônio depende de um mesmo fator: {fat[0]['nome']}.")
    st.markdown("#### Exposição indireta e sobreposição (ETFs e fundos)")
    etfs = [p for p in pos if p["classe"] == "etf"]
    if not etfs:
        st.caption("Sem ETFs na carteira. Fundos por CNPJ entram quando a CVM divulga a composição.")
    elif st.button("Ler a composição dos ETFs (consulta as fontes)", key="gc_comp"):
        st.session_state["gc_comp_res"] = _composicao(pos)
    res = st.session_state.get("gc_comp_res")
    if res:
        for t in res["avisos"]:
            st.caption("⚠️ " + t)
        if res.get("expo") is not None and len(res["expo"]):
            st.dataframe(pd.DataFrame({"Ativo": res["expo"].head(10).index, "% da carteira": res["expo"].head(10).round(2).values}), hide_index=True, width="stretch")
        for t in res["indiretas"]:
            st.warning(t)
        for a, b, v in res["sobrep"]:
            st.warning(f"{a} e {b}: sobreposição de pelo menos {_n(v, 1)}% do patrimônio de cada um.")
        st.caption(f"{_n(res.get('sem_composicao', 0), 0)}% do valor está em posições sem composição divulgada: ficam fora destas exposições.")


def _composicao(pos: list[dict]) -> dict:
    out = {"avisos": [], "expo": None, "indiretas": [], "sobrep": [], "sem_composicao": 0.0}
    itens, pesos = [], {}
    with st.spinner("Lendo ETFs..."):
        for p in pos:
            if p["classe"] != "etf":
                continue
            try:
                fx = fundos_app.preparar_etf(p["id"])
            except Exception as e:
                out["avisos"].append(f"{p['id']}: {e.__class__.__name__}.")
                continue
            if fx.get("erro"):
                out["avisos"].append(f"{p['id']}: {fx['erro']}.")
                continue
            pesos[p["id"]] = fx.get("pesos")
            itens.append({"nome": p["id"], "valor": p["valor"], "pesos": fx.get("pesos"), "classe": fa.classe_de_ativo(fx["rotulos"])})
    diretos = [{"nome": p["id"], "valor": p["valor"], "pesos": {p["id"]: 100.0}} for p in pos if p["classe"] in ("acao", "fii", "bdr")]
    ex = fa.exposicao_total(itens + diretos) if itens else {"ok": False}
    if ex.get("ok"):
        out["expo"] = ex["ativos"]
        out["sem_composicao"] = ex["sem_composicao_pct"]
        ids_dir = {d["nome"] for d in diretos}
        ind = [k for k in ids_dir if k in ex["ativos"].index and any(k in (pp or {}) for pp in pesos.values())]
        if ind:
            out["indiretas"].append("Exposição indireta a ativos que você já tem diretamente: " + ", ".join(sorted(ind)) + ". Você está mais concentrado neles do que parece.")
    nomes = [i for i in itens if i.get("pesos")]
    for i, a in enumerate(nomes):
        for b in nomes[i + 1:]:
            s = fa.sobreposicao(a["pesos"], b["pesos"])
            if s.get("ok") and s["valor"] >= 20:
                out["sobrep"].append((a["nome"], b["nome"], s["valor"]))
    return out


def _metricas_risco(C, D) -> dict:
    P = D["pesos_total"]
    rets = D["rets"]
    cols = [c for c in rets.columns if c in P.index]
    if not cols:
        return {}
    r, info = g.retornos_da_carteira(rets, {c: float(P[c]) for c in cols})
    if len(r) < 60:
        return {}
    idx = (1 + r).cumprod()
    dd = g.drawdown(idx)
    rfd = D.get("cdi_diario")
    ibov = C["referencias"]["series"].get("Ibovespa")
    b = None
    if ibov is not None and len(ibov):
        rb = pd.Series(ibov.values, index=pd.DatetimeIndex(ibov.index).tz_localize(None).normalize() if pd.DatetimeIndex(ibov.index).tz is not None else pd.DatetimeIndex(ibov.index).normalize())
        b = g.beta(r, rb[~rb.index.duplicated(keep="last")].pct_change().dropna(), 120)
    return {"r": r, "idx": idx, "dd": dd, "vol": g.vol_anual(r), "mdd": dd.get("maximo"), "sharpe": g.sharpe(r, rfd), "sortino": g.sortino(r, rfd),
            "beta": b, "var95": g.var_historico(r, 0.95), "var99": g.var_historico(r, 0.99), "var95p": g.var_parametrico(r, 0.95),
            "cvar95": g.cvar_historico(r, 0.95), "cvar99": g.cvar_historico(r, 0.99), "var95_10": g.var_historico(r, 0.95, 10),
            "cobertura": info["cobertura"], "dias": info["dias"], "usados": info["usados"]}


def _riscos_qualitativos(C) -> dict:
    pos = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
    tot = sum(p["valor"] for p in pos) or 1.0
    rf_ = [p for p in pos if p["classe"] == "renda_fixa"]
    liq30 = sum(p["valor"] for p in rf_ if (p.get("liquidez_dias") or 0) > 30) / tot
    priv = sum(p["valor"] for p in rf_ if (p.get("credito") or 0) >= 3) / tot
    cambio = sum(p["valor"] for p in pos if p["moeda"] != "BRL") / tot
    cred_medio = (sum(p["valor"] * p["credito"] for p in rf_) / sum(p["valor"] for p in rf_)) if rf_ else None
    return {"liquidez_baixa": liq30, "credito_privado": priv, "cambial": cambio, "credito_medio": cred_medio, "tem_rf": bool(rf_),
            "bolsa": sum(p["valor"] for p in pos if p["classe"] in ("acao", "bdr", "etf", "fii", "cripto")) / tot}


def _aba_risco(C, D):
    M = _metricas_risco(C, D)
    Q = _riscos_qualitativos(C)
    if not M:
        st.info("Estatísticas de risco precisam de ≥ 60 dias de histórico comum dos ativos de mercado. Veja abaixo os riscos que não dependem de histórico.")
    else:
        _cartoes([("Volatilidade anual", _p(M["vol"], 1), "info", "desvio-padrão diário × √252"),
                  ("Queda máxima", _p(M["mdd"], 1), "bad" if M["mdd"] < -0.25 else "fair", f"{M['dd']['pico']:%d/%m/%Y} → {M['dd']['vale']:%d/%m/%Y}"),
                  ("Sharpe", _n(M["sharpe"], 2) if M["sharpe"] is not None else "n/d", "info", "excesso sobre o CDI"),
                  ("Sortino", _n(M["sortino"], 2) if M["sortino"] is not None else "n/d", "info", "só a queda conta como risco")], por_linha=2)
        _cartoes([("Beta vs Ibovespa", _n(M["beta"], 2) if M["beta"] is not None else "n/d", "info", "1 = oscila como o índice"),
                  ("VaR 95% (1 dia)", _p(M["var95"], 2) if M["var95"] is not None else "n/d", "info", "histórico"),
                  ("VaR 99% (1 dia)", _p(M["var99"], 2) if M["var99"] is not None else "n/d", "info", "histórico"),
                  ("CVaR 95% (1 dia)", _p(M["cvar95"], 2) if M["cvar95"] is not None else "n/d", "info", "perda média na cauda")], por_linha=2)
        st.caption(f"Base: carteira atual com pesos constantes sobre {M['dias']} dias em comum; cobre {_p(M['cobertura'], 0)} do patrimônio "
                   f"({', '.join(M['usados'])}). Renda fixa e fundos sem histórico ficam fora deste cálculo.")
        _graf_linhas({"Queda desde o pico (%)": M["dd"]["serie"] * 100}, "Queda desde o último pico", "%")
        P = D["pesos_total"]
        cov = o.covariancia(D["rets"][M["usados"]], False)
        cr_ = g.contribuicao_risco(P[M["usados"]] / P[M["usados"]].sum(), cov)
        st.markdown("#### Quem contribui para o risco")
        st.dataframe(pd.DataFrame({"Ativo": cr_.index, "Peso (%)": (P[M["usados"]] / P[M["usados"]].sum() * 100).round(1).values,
                                   "Parcela do risco (%)": (cr_.values * 100).round(1)}).sort_values("Parcela do risco (%)", ascending=False),
                     hide_index=True, width="stretch")
        with st.expander("Metodologia e limites do VaR e do CVaR"):
            st.markdown(
                "- **VaR histórico**: perda que não foi excedida em 95% (ou 99%) dos dias do passado. Em 5% (1%) dos dias a perda foi **maior**.\n"
                f"- **VaR paramétrico (normal) 95%**: {_p(M['var95p'], 2) if M['var95p'] is not None else 'n/d'}. Supõe retornos em forma de sino; "
                "subestima crises.\n"
                f"- **VaR 95% em 10 dias** (√10 × 1 dia): {_p(M['var95_10'], 2) if M['var95_10'] is not None else 'n/d'}.\n"
                "- **CVaR**: média das perdas nos dias piores que o VaR (precisa de ≥ 10 dias na cauda).\n"
                "- Nenhum desses números é a perda máxima possível. O passado pode não conter o pior cenário.")
    st.markdown("#### Riscos em linguagem simples")
    linhas = []
    if M:
        linhas.append(("Mercado", "atenção" if M["vol"] > 0.25 else "ok", f"A carteira oscilou {_p(M['vol'], 1)} ao ano e já caiu {_p(abs(M['mdd']), 1)} do pico ao vale no período."))
    linhas.append(("Cambial", "atenção" if Q["cambial"] > 0.3 else "ok", f"{_p(Q['cambial'], 0)} do patrimônio está em moeda estrangeira: a cotação do dólar mexe no valor em R$."))
    if Q["tem_rf"]:
        linhas.append(("Crédito", "atenção" if Q["credito_privado"] > 0.3 else "ok",
                       f"{_p(Q['credito_privado'], 0)} do patrimônio está em crédito privado (banco ou empresa). Nível médio de crédito da renda fixa: {_n(Q['credito_medio'], 1)}/5 (1 = soberano)."))
        linhas.append(("Liquidez", "atenção" if Q["liquidez_baixa"] > 0.3 else "ok",
                       f"{_p(Q['liquidez_baixa'], 0)} do patrimônio leva mais de 30 dias para virar dinheiro (renda fixa com carência ou só no vencimento). Ações e FIIs vendem em D+2; cripto e ETFs no exterior podem ter prazos e custos próprios."))
    else:
        linhas.append(("Crédito e liquidez da renda fixa", "info", "Sem títulos de renda fixa salvos: use Renda fixa → Análise de títulos para incluí-los."))
    pos = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
    cn = g.concentracao([p["valor"] for p in pos])
    if cn.get("ok"):
        linhas.append(("Concentração", "atenção" if cn["top1"] > 0.3 else "ok", f"A maior posição pesa {_p(cn['top1'], 0)}; equivalem a ≈ {_n(cn['n_efetivo'], 1)} posições de mesmo tamanho."))
    for n, s, t in linhas:
        (st.warning if s == "atenção" else st.info if s == "info" else st.success)(f"**{n}.** {t}")


def _aba_rentabilidade(C, D):
    tw, tp = D.get("twr_total", {}), D.get("twr_preco", {})
    if not tw.get("ok"):
        st.info(f"Rentabilidade por tempo indisponível: {tw.get('motivo', 'sem histórico')}.")
        return
    dias = (pd.Timestamp(tw["fim"]) - pd.Timestamp(tw["inicio"])).days
    cg = g.cagr(tw["total"], dias)
    xir = _xirr_total(C)
    _cartoes([("TWR (retorno total)", _p(tw["total"], 2, True), "info", "com proventos, sem efeito dos aportes"),
              ("TWR (só preço)", _p(tp.get("total"), 2, True) if tp.get("ok") else "n/d", "info", "sem proventos"),
              ("XIRR a.a.", _p(xir, 2, True) if xir is not None else "n/d", "info", "ponderado pelo dinheiro"),
              ("CAGR (TWR)", _p(cg, 2, True) if cg is not None else "n/d", "info", f"{dias} dias")], por_linha=2)
    st.caption(f"Escopo: ativos de mercado com histórico de preço ({_p(_cobertura(C, D), 0)} do patrimônio atual). Renda fixa tem rentabilidade própria "
               "(curva do título, veja a aba Renda fixa) e entra no XIRR. Retorno de preço × retorno total: a diferença são os proventos.")
    jan = g.janelas(tw["indice"])
    if jan:
        st.dataframe(pd.DataFrame([{"Período": k, "Retorno": _p(v, 2, True)} for k, v in jan.items()]), hide_index=True, width="stretch")
    refs = C["referencias"]["series"]
    escolha = st.multiselect("Comparar com", [k for k in refs], default=[k for k in ("CDI", "Ibovespa") if k in refs], key="gc_bench")
    ini = tw["indice"].index[0]
    linhas = {"Carteira (TWR total)": tw["indice"] / tw["indice"].iloc[0] * 100}
    if tp.get("ok"):
        linhas["Carteira (só preço)"] = tp["indice"] / tp["indice"].iloc[0] * 100
    for k in escolha:
        b = _base100(refs[k], ini)
        if len(b):
            linhas[k] = b
    _graf_linhas(linhas, "Evolução (base 100)")
    st.caption("A carteira usa as compras reais, nas datas reais. Cada benchmark começa em 100 na primeira data da carteira.")
    for k in escolha:
        b = _base100(refs[k], ini)
        if len(b) > 1:
            dif = tw["total"] - (b.iloc[-1] / 100 - 1)
            st.caption(f"Frente ao {k}: {_p(dif, 2, True)} no período ({_p(b.iloc[-1] / 100 - 1, 2, True)} do índice).")
    m = g.retorno_por_periodo(tw["retornos"], "M")
    a = g.retorno_por_periodo(tw["retornos"], "Y")
    c1, c2 = st.columns(2)
    with c1:
        if len(m):
            fig = go.Figure(go.Bar(x=[str(i) for i in m.index], y=(m.values * 100), marker_color=["#15803D" if v >= 0 else "#C62828" for v in m.values]))
            fig.update_layout(title="Rentabilidade mensal (%)", height=300, **TRANSP)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with c2:
        if len(a):
            st.markdown("**Por ano**")
            st.dataframe(pd.DataFrame({"Ano": [str(i) for i in a.index], "Retorno": [_p(v, 2, True) for v in a.values]}), hide_index=True, width="stretch")
    cons = g.consistencia(tw["retornos"], None)
    if cons.get("ok"):
        st.caption(f"{_p(cons['pct_positivos'], 0)} dos {cons['meses']} meses foram positivos; melhor {_p(cons['melhor'], 1, True)}, pior {_p(cons['pior'], 1, True)}.")
    st.markdown("#### Por ativo e por classe")
    linhas_a = []
    ev_por = {}
    for e in C["eventos"]:
        ev_por[e["fonte"]] = ev_por.get(e["fonte"], 0.0) + e["valor"]
    for p in C["posicoes"]:
        if not _fin(p.get("valor")) or not _fin(p.get("custo")) or p["custo"] <= 0:
            continue
        real = p.get("realizado", 0.0) or 0.0
        prov = ev_por.get(p["id"], 0.0)
        linhas_a.append({"Ativo": p["id"], "Classe": g.CLASSES.get(p["classe"], p["classe"]), "Custo": p["custo"], "Valor": p["valor"],
                         "Proventos": prov, "Preço (%)": (p["valor"] / p["custo"] - 1) * 100,
                         "Total (%)": ((p["valor"] + prov + real) / p["custo"] - 1) * 100})
    if linhas_a:
        df = pd.DataFrame(linhas_a)
        st.dataframe(df, hide_index=True, width="stretch", column_config={
            "Custo": st.column_config.NumberColumn(format="R$ %.2f"), "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
            "Proventos": st.column_config.NumberColumn(format="R$ %.2f"), "Preço (%)": st.column_config.NumberColumn(format="%.1f"),
            "Total (%)": st.column_config.NumberColumn(format="%.1f")})
        gc = df.groupby("Classe")[["Custo", "Valor", "Proventos"]].sum()
        gc["Total (%)"] = (gc["Valor"] + gc["Proventos"]) / gc["Custo"] * 100 - 100
        st.dataframe(gc.reset_index(), hide_index=True, width="stretch", column_config={
            "Custo": st.column_config.NumberColumn(format="R$ %.2f"), "Valor": st.column_config.NumberColumn(format="R$ %.2f"),
            "Proventos": st.column_config.NumberColumn(format="R$ %.2f"), "Total (%)": st.column_config.NumberColumn(format="%.1f")})
        st.caption("Por ativo, o retorno de preço usa o custo médio em R$ (inclui o efeito do câmbio). Retorno total soma proventos e ganhos já realizados nas vendas. "
                   "Taxas, impostos e eventos corporativos (desdobramentos, bonificações) NÃO estão incluídos: os preços do Yahoo já vêm ajustados a desdobramentos, "
                   "mas as quantidades lançadas por você não — se houve desdobramento, atualize a quantidade.")


def _aba_renda(C, D):
    ev = C["eventos"]
    rp = o.renda_passiva(ev, C["hoje"])
    if not rp.get("ok"):
        st.info("Nenhum provento encontrado ainda para os seus ativos (ações, FIIs, ETFs que pagam, cupons de renda fixa).")
    else:
        _cartoes([("Recebido (12 meses)", _r(rp["ultimos_12m"]), "info", ""),
                  ("Média mensal", _r(rp["media_mensal_12m"]), "info", "últimos 12 meses"),
                  ("Meses com pagamento", f"{rp['meses_com_pagamento_12m']}/{rp['meses_janela']}", "good" if rp["meses_com_pagamento_12m"] >= 10 else "fair", "regularidade"),
                  ("Variação vs 12 meses antes", _p(rp["crescimento_12m"], 1, True) if rp["crescimento_12m"] is not None else "n/d", "info", "")], por_linha=2)
        m = rp["mensal"].iloc[-24:]
        fig = go.Figure(go.Bar(x=[str(i) for i in m.index], y=m.values, name="Recebido"))
        fig.update_layout(title="Renda recebida por mês (R$)", height=300, **TRANSP)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
        if len(rp["rolante_12m"]):
            _graf_linhas({"Soma dos últimos 12 meses (R$)": pd.Series(rp["rolante_12m"].values, index=rp["rolante_12m"].index.to_timestamp())}, "Evolução da renda passiva")
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Por ano**")
            st.dataframe(pd.DataFrame({"Ano": rp["anual"].index.astype(str), "Recebido": [_r(v) for v in rp["anual"].values]}), hide_index=True, width="stretch")
            st.markdown("**Por tipo**")
            st.dataframe(pd.DataFrame({"Tipo": [o.TIPOS_PROVENTO.get(k, k) for k in rp["por_tipo"].index], "Recebido": [_r(v) for v in rp["por_tipo"].values]}),
                         hide_index=True, width="stretch")
        with c2:
            st.markdown("**Fonte pagadora**")
            st.dataframe(pd.DataFrame({"Fonte": rp["por_fonte"].index, "Recebido": [_r(v) for v in rp["por_fonte"].values],
                                       "%": [_p(v, 1) for v in rp["por_fonte_pct"].values]}), hide_index=True, width="stretch")
        if rp["top_fonte"][1] > 0.4:
            st.warning(f"{rp['top_fonte'][0]} responde por {_p(rp['top_fonte'][1], 0)} da renda recebida: dependência de uma fonte pagadora.")
        if rp["cv_12m"] is not None and rp["cv_12m"] > 1.0:
            st.info("Os valores mensais variam bastante (concentrados em poucos meses): a renda é irregular.")
    st.markdown("#### Projeções (separadas do que foi recebido)")
    ult = [e for e in ev if e.get("efetivo") and e["fonte"] in C["classes"] and (C["hoje"] - e["data"]).days <= 365]
    # quantidade atual × valor por papel dos últimos 12 meses
    ref_ev = []
    for tk, df in C["prov_papel"].items():
        q = next((p["qtd"] for p in C["posicoes"] if p["id"] == tk), 0.0)
        if df is None or df.empty or q <= 0:
            continue
        f = 1.0 if C["moedas"].get(tk, "BRL") == "BRL" else (float(C["cambio"].iloc[-1]) if len(C["cambio"]) else None)
        if f is None:
            continue
        for r in df.itertuples():
            d = g._data(r.data)
            if d and 0 <= (C["hoje"] - d).days <= 365:
                ref_ev.append({"data": d, "valor": q * float(r.valor) * f})
    pr = o.projetar_repetindo_12m(ref_ev, C["hoje"])
    pc = o.projetar_contratual(C["rf_fluxos"], C["hoje"])
    if pr.sum() <= 0 and pc.sum() <= 0:
        st.caption("Sem base para projetar.")
        return
    fig = go.Figure()
    fig.add_bar(x=[str(i) for i in pc.index], y=pc.values, name="Contratual (renda fixa)")
    fig.add_bar(x=[str(i) for i in pr.index], y=pr.values, name="Referência (repete os últimos 12 meses)")
    fig.update_layout(barmode="stack", title="Próximos 12 meses (R$)", height=300, legend=dict(orientation="h", y=-0.2), **TRANSP)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("**Contratual**: cupons, juros e amortizações dos títulos de renda fixa salvos (cenário de CDI/IPCA de hoje para pós-fixados e IPCA — é estimativa, não garantia). "
               "**Referência**: repete, com a quantidade ATUAL, o que cada papel pagou nos últimos 12 meses; dividendos e rendimentos podem mudar ou não ser pagos. "
               "A fonte informa a data-com, não a data do crédito. Valores brutos, antes de eventual imposto.")


def _aba_otimizacao(C, D):
    rets = D["rets"]
    if rets.empty or rets.shape[1] < 2:
        st.info("A otimização precisa de ≥ 2 ativos com ≥ 120 dias de histórico em comum.")
        return
    cols = list(rets.columns)
    P = D["pesos_total"]
    st.caption("Simulação sobre o passado. Retornos e correlações históricas podem não se repetir, e o retorno esperado (média histórica) é a estimativa menos estável. "
               "Nada é executado: o resultado é uma referência para você decidir.")
    obj = st.radio("Objetivo", ["Menor oscilação (variância mínima)", "Melhor retorno por risco (máximo Sharpe)", "Dividir o risco igualmente (paridade de risco)"],
                   key="gc_obj")
    metodo = {"Menor": "min_var", "Melhor": "max_sharpe", "Dividir": "paridade"}[obj.split()[0]]
    c1, c2 = st.columns(2)
    teto = c1.number_input("Máximo por ativo (%)", min_value=5.0, max_value=100.0, value=40.0, step=5.0, key="gc_teto") / 100
    piso = c2.number_input("Mínimo por ativo (%)", min_value=0.0, max_value=20.0, value=0.0, step=1.0, key="gc_piso") / 100
    cl_de = {p["id"]: p["classe"] for p in C["posicoes"]}
    classes = sorted({cl_de[c] for c in cols if c in cl_de})
    caps = {}
    with st.expander("Tetos por classe (opcional)"):
        for cl in classes:
            v = st.number_input(f"{g.CLASSES.get(cl, cl)} — máximo (%)", min_value=0.0, max_value=100.0, value=100.0, step=5.0, key=f"gc_cap_{cl}")
            if v < 100:
                caps[cl] = v / 100
    cdi = D.get("cdi_diario")
    rf_aa = float((1 + cdi.loc[rets.index[0]:rets.index[-1]].mean()) ** 252 - 1) if cdi is not None and len(cdi.loc[rets.index[0]:rets.index[-1]]) > 20 else 0.0
    res = o.otimizar(rets, metodo, rf_aa, (piso, teto), cl_de, caps or None)
    if not res["ok"]:
        st.warning(res["motivo"].capitalize() + ".")
        return
    for a in res["avisos"]:
        st.caption("⚠️ " + a)
    atual = P.reindex(cols).fillna(0.0)
    atual = atual / atual.sum() if atual.sum() > 0 else atual
    ig = pd.Series(1 / len(cols), index=cols)
    tab = pd.DataFrame({"Ativo": cols, "Atual (%)": (atual * 100).round(1).values, "Sugerida (%)": (res["pesos"] * 100).round(1).values,
                        "Diferença (p.p.)": ((res["pesos"] - atual) * 100).round(1).values})
    st.dataframe(tab, hide_index=True, width="stretch")
    cmp_ = o.comparar_carteiras(rets, {"Atual": atual.to_dict(), "Sugerida": res["pesos"].to_dict(), "Pesos iguais": ig.to_dict()}, cdi)
    if len(cmp_):
        for c_ in ("Retorno a.a.", "Volatilidade a.a.", "Queda máxima", "VaR 95% (1 dia)"):
            cmp_[c_] = cmp_[c_] * 100                               # a tela mostra em %, o motor devolve fração
        st.dataframe(cmp_, hide_index=True, width="stretch", column_config={
            "Retorno a.a.": st.column_config.NumberColumn(format="%.2f%%"), "Volatilidade a.a.": st.column_config.NumberColumn(format="%.2f%%"),
            "Sharpe": st.column_config.NumberColumn(format="%.2f"), "Queda máxima": st.column_config.NumberColumn(format="%.2f%%"),
            "VaR 95% (1 dia)": st.column_config.NumberColumn(format="%.2f%%")})
    fr = o.fronteira_eficiente(rets, 12, rf_aa, (piso, teto))
    if len(fr):
        fig = go.Figure()
        fig.add_scatter(x=fr["vol"] * 100, y=fr["retorno"] * 100, mode="lines+markers", name="Fronteira (histórica)")
        ea = o.estatisticas_anuais(rets, atual.values, rf_aa)
        fig.add_scatter(x=[ea["vol"] * 100], y=[ea["retorno"] * 100], mode="markers", name="Atual", marker=dict(size=12))
        fig.add_scatter(x=[res["vol"] * 100], y=[res["retorno"] * 100], mode="markers", name="Sugerida", marker=dict(size=12))
        fig.update_layout(title="Risco × retorno histórico (% a.a.)", height=330, xaxis_title="Volatilidade", yaxis_title="Retorno", legend=dict(orientation="h", y=-0.25), **TRANSP)
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    mg = o.impacto_marginal(rets, atual.to_dict(), 0.05)
    if len(mg):
        st.markdown("#### O que acontece ao dar mais peso a cada ativo (+5% do patrimônio)")
        st.dataframe(mg, hide_index=True, width="stretch", column_config={
            "Peso atual": st.column_config.NumberColumn(format="%.3f"), "Δ volatilidade (p.p.)": st.column_config.NumberColumn(format="%.2f"),
            "Δ concentração (HHI)": st.column_config.NumberColumn(format="%.4f")})
        st.caption("Δ negativo = reduz a volatilidade/a concentração (ajuda a diversificar); positivo = aumenta.")
    if st.button("Usar a distribuição por classe da sugerida como meu alvo", key="gc_usar"):
        porcl: dict[str, float] = {}
        for c, w in res["pesos"].items():
            porcl[cl_de.get(c, "outro")] = porcl.get(cl_de.get(c, "outro"), 0.0) + float(w) * 100
        fora = 100 - sum(porcl.values())
        st.session_state[K_ALVOS] = {k: round(v, 1) for k, v in porcl.items()}
        for k in list(st.session_state):
            if str(k).startswith("gc_alvo_"):
                del st.session_state[k]
        st.success("Alvos por classe atualizados (só preferência da tela; nenhuma posição foi alterada). Veja a aba Alocação.")


def _aba_rebalanceamento(C, D):
    pos = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
    alvos, tols = _alvos_atuais(), dict(st.session_state.get(K_TOL) or {})
    if not pos:
        st.info("Sem posições com valor.")
        return
    if not alvos or abs(sum(alvos.values()) - 100) > 0.01:
        st.info("Defina os percentuais-alvo por classe (somando 100%) na aba Alocação para ver o rebalanceamento.")
        return
    vals: dict[str, float] = {}
    custos: dict[str, float] = {}
    for p in pos:
        vals[p["classe"]] = vals.get(p["classe"], 0.0) + p["valor"]
        custos[p["classe"]] = custos.get(p["classe"], 0.0) + (p["custo"] if _fin(p.get("custo")) else p["valor"])
    des = g.desvios_do_alvo(vals, alvos, tols or 5.0)
    st.dataframe(pd.DataFrame([{"Classe": g.CLASSES.get(x["classe"], x["classe"]), "Atual (%)": round(x["atual"], 1), "Alvo (%)": x["alvo"],
                                "Desvio (p.p.)": round(x["desvio"], 1), "Tolerância": x["tolerancia"],
                                "Situação": {"dentro": "ok", "acima": "acima", "abaixo": "abaixo"}[x["status"]],
                                "Ajuste para o alvo (R$)": x["ajuste"]} for x in des]), hide_index=True, width="stretch",
                 column_config={"Ajuste para o alvo (R$)": st.column_config.NumberColumn(format="R$ %.2f")})
    fora = [x for x in des if x["status"] != "dentro"]
    if not fora:
        st.success("Todas as classes estão dentro da tolerância.")
    a_min = o.aporte_para_rebalancear(vals, alvos)
    st.markdown("#### 1. Rebalancear só com aportes (sem vender)")
    if a_min is None:
        st.caption("Há classe com saldo e alvo zero: só vendendo.")
    else:
        st.caption(f"Aporte mínimo para trazer todas as classes ao alvo sem vender: **{_r(a_min)}**.")
    ap = st.number_input("Quanto você pretende aportar (R$)", min_value=0.0, step=500.0, key="gc_aporte")
    ra = o.rebalancear_com_aporte(vals, alvos, ap) if ap > 0 else None
    if ra and ra["ok"]:
        st.dataframe(pd.DataFrame([{"Classe": g.CLASSES.get(c, c), "Comprar (R$)": ra["comprar"].get(c, 0.0), "Fica em (%)": round(ra["pct_final"][c], 1),
                                    "Alvo (%)": alvos.get(c, 0.0)} for c in ra["pct_final"]]), hide_index=True, width="stretch",
                     column_config={"Comprar (R$)": st.column_config.NumberColumn(format="R$ %.2f")})
        st.caption("Alvo atingido." if ra["atinge_alvo"] else "O aporte não chega a todos os alvos: só as classes mais defasadas recebem.")
        for c, v in ra["comprar"].items():
            ids = sorted([p for p in pos if p["classe"] == c], key=lambda p: p["valor"])
            if ids:
                st.caption(f"Dentro de {g.CLASSES.get(c, c)}, os ativos de menor peso hoje: " + ", ".join(p["id"] for p in ids[:3]) + ".")
    st.markdown("#### 2. Rebalancear vendendo o excesso")
    corr = st.number_input("Corretagem e custos (% sobre o valor negociado)", min_value=0.0, max_value=5.0, value=0.0, step=0.05, key="gc_corr")
    rv = o.rebalancear_com_vendas(vals, custos, alvos, tols or 5.0, corr)
    if rv["ok"] and (rv["vender"] or rv["comprar"]):
        st.dataframe(pd.DataFrame([{"Classe": g.CLASSES.get(c, c), "Vender (R$)": rv["vender"].get(c, 0.0), "Imposto estimado (R$)": rv["imposto"].get(c, 0.0),
                                    "Comprar (R$)": rv["comprar"].get(c, 0.0), "Fica em (%)": round(rv["pct_final"][c], 1), "Alvo (%)": alvos.get(c, 0.0)}
                                   for c in rv["pct_final"]]), hide_index=True, width="stretch",
                     column_config={k: st.column_config.NumberColumn(format="R$ %.2f") for k in ("Vender (R$)", "Imposto estimado (R$)", "Comprar (R$)")})
        st.caption(f"Custo do rebalanceamento por vendas: imposto estimado {_r(rv['imposto_total'])} + corretagem {_r(rv['corretagem_total'])}."
                   + (f" Isentas pela regra mensal: {', '.join(g.CLASSES.get(c, c) for c in rv['isentos'])}." if rv["isentos"] else ""))
        for a in rv["avisos"]:
            st.caption("⚠️ " + a)
        if a_min is not None:
            st.info(f"Comparação: por aportes você precisa colocar {_r(a_min)} e paga ≈ R$ 0,00 de imposto; por vendas o custo estimado é {_r(rv['perda_pelo_custo'])}, sem aporte novo.")
    elif rv["ok"]:
        st.success("Nada a vender: as classes fora da tolerância só precisam de aporte.")


def _aba_cenarios(C, D):
    pos = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
    if not pos:
        st.info("Sem posições com valor.")
        return
    betas = _beta_historico(C, D)
    for p in pos:
        p["beta"] = betas.get(p["id"])
    st.caption("Estimativa por premissas (betas, durações, sensibilidades), NÃO previsão. Cada premissa aparece na tabela abaixo.")
    nome = st.selectbox("Cenário", ["Personalizado"] + list(o.CENARIOS_PRONTOS), key="gc_cen")
    base = o.CENARIOS_PRONTOS.get(nome, {})
    ks = st.session_state
    c = st.columns(3)
    ch = {
        "bolsa_br": c[0].number_input("Bolsa brasileira (%)", min_value=-90.0, max_value=200.0, value=float(base.get("bolsa_br", 0.0)), step=5.0, key=f"gc_c1_{nome}"),
        "bolsa_ext": c[1].number_input("Bolsa do exterior, em moeda local (%)", min_value=-90.0, max_value=200.0, value=float(base.get("bolsa_ext", 0.0)), step=5.0, key=f"gc_c2_{nome}"),
        "cripto": c[2].number_input("Criptomoedas, em dólar (%)", min_value=-95.0, max_value=500.0, value=float(base.get("cripto", 0.0)), step=5.0, key=f"gc_c3_{nome}"),
        "juros_pp": c[0].number_input("Juros (variação em p.p.)", min_value=-10.0, max_value=15.0, value=float(base.get("juros_pp", 0.0)), step=0.5, key=f"gc_c4_{nome}"),
        "inflacao_pp": c[1].number_input("Inflação (surpresa em p.p.)", min_value=-5.0, max_value=15.0, value=float(base.get("inflacao_pp", 0.0)), step=0.5, key=f"gc_c5_{nome}"),
        "usd": c[2].number_input("Dólar (%)", min_value=-50.0, max_value=100.0, value=float(base.get("usd", 0.0)), step=5.0, key=f"gc_c6_{nome}"),
    }
    res = o.simular_cenario(pos, ch)
    _cartoes([("Patrimônio hoje", _r(res["antes"]), "info", ""), ("Depois do cenário", _r(res["depois"]), "good" if res["delta"] >= 0 else "bad", ""),
              ("Variação", _r(res["delta"]), "good" if res["delta"] >= 0 else "bad", _p(res["pct"] / 100, 1, True))], por_linha=3)
    st.dataframe(pd.DataFrame([{"Classe": g.CLASSES.get(k, k), "Variação (R$)": v} for k, v in sorted(res["por_classe"].items(), key=lambda x: x[1])]),
                 hide_index=True, width="stretch", column_config={"Variação (R$)": st.column_config.NumberColumn(format="R$ %.2f")})
    with st.expander("Impacto por posição e premissas usadas", expanded=False):
        st.dataframe(pd.DataFrame([{"Ativo": x["id"], "Valor": x["valor"], "Variação (%)": round(x["pct"], 2), "Variação (R$)": x["delta"], "Premissa": x["premissa"]}
                                   for x in res["posicoes"]]), hide_index=True, width="stretch",
                     column_config={"Valor": st.column_config.NumberColumn(format="R$ %.2f"), "Variação (R$)": st.column_config.NumberColumn(format="R$ %.2f")})
        st.markdown("- Ações, ETFs, BDRs: variação = beta × choque da bolsa (beta histórico contra o Ibovespa quando há ≥ 120 dias; senão assumido).\n"
                    "- FIIs: beta assumido 0,6 e −3% por +1 p.p. de juros.\n- Renda fixa prefixada e IPCA+: −duração × variação dos juros; IPCA+: soma a surpresa de inflação (efeito de 1 ano); pós-fixados: sem efeito de preço.\n"
                    "- Ativos em moeda estrangeira e BDRs: (1 + choque local) × (1 + dólar) − 1. Cripto: choque em dólar × câmbio.")
    antes = {p["id"]: p["valor"] / res["antes"] for p in pos}
    st.markdown("#### Distribuição depois do cenário")
    st.dataframe(pd.DataFrame([{"Ativo": k, "Antes (%)": round(antes[k] * 100, 1), "Depois (%)": round(v * 100, 1)} for k, v in res["pesos_depois"].items()]),
                 hide_index=True, width="stretch")
    st.markdown("#### Se as correlações subirem")
    M = _metricas_risco(C, D)
    if M:
        P = D["pesos_total"][M["usados"]]
        P = P / P.sum()
        rets = D["rets"][M["usados"]]
        vols = rets.std(ddof=1) * math.sqrt(252)
        corr = g.correlacao(rets)
        linhas = []
        for k, rot in ((0.0, "Correlações históricas"), (0.5, "Metade do caminho até 1"), (1.0, "Tudo se move junto (correlação 1)")):
            v = o.vol_com_correlacao(P, vols, corr, k)
            if v is not None:
                linhas.append({"Hipótese": rot, "Volatilidade a.a.": _p(v, 1)})
        if linhas:
            st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
            st.caption("Em crises as correlações costumam subir: parte da proteção da diversificação some.")
        pp = o.piores_periodos(M["r"])
        if pp:
            st.markdown("#### Piores momentos do histórico (carteira atual)")
            rot = {"pior_dia": "Pior dia", "pior_mes": "Pior mês", "pior_ano": "Pior ano"}
            st.dataframe(pd.DataFrame([{"Período": rot.get(k, k), "Quando": str(v[0]), "Retorno": _p(v[1], 2, True)} for k, v in pp.items()]),
                         hide_index=True, width="stretch")
            st.caption("Anos e meses incompletos contam só os dias com dados.")
    st.markdown("#### Aporte e retirada")
    vals: dict[str, float] = {}
    for p in pos:
        vals[p["classe"]] = vals.get(p["classe"], 0.0) + p["valor"]
    a, b = st.columns(2)
    ap = a.number_input("Aporte (R$)", min_value=0.0, step=1000.0, key="gc_fl_ap")
    rt = b.number_input("Retirada (R$)", min_value=0.0, step=1000.0, key="gc_fl_rt")
    alvos = _alvos_atuais()
    sf = o.simular_fluxo(vals, ap, rt, alvos if alvos and abs(sum(alvos.values()) - 100) < 0.01 else None)
    if not sf["ok"]:
        st.warning(sf["motivo"].capitalize() + ".")
    elif ap or rt:
        st.dataframe(pd.DataFrame([{"Classe": g.CLASSES.get(c, c), "Antes (%)": round(sf["pct_antes"].get(c, 0), 1), "Depois (%)": round(sf["pct_depois"].get(c, 0), 1)}
                                   for c in sf["depois"]]), hide_index=True, width="stretch")
        st.caption(f"Patrimônio: {_r(sf['total_antes'])} → {_r(sf['total_depois'])}. Aporte vai para as classes abaixo do alvo (se houver alvo); retirada sai proporcionalmente.")


def _contexto_relatorio(C, D) -> dict:
    pos = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
    for p in pos:
        p["fator"] = g.fator_de_risco(p)
    tot = sum(p["valor"] for p in pos)
    M = _metricas_risco(C, D)
    Q = _riscos_qualitativos(C)
    ctx = {"patrimonio": tot, "conc": g.concentracao([p["valor"] for p in pos]), "alertas_conc": g.avaliar_concentracao(pos, st.session_state.get(K_LIM)),
           "risco": {k: M.get(k) for k in ("vol", "mdd", "sharpe", "var95", "cvar95", "dias", "cobertura")} if M else {},
           "exposicao_cambial": Q["cambial"], "liquidez_baixa_pct": Q["liquidez_baixa"], "credito_privado_pct": Q["credito_privado"],
           "qualidade": g.avaliar_qualidade(C["posicoes"], C["hoje"]),
           "resultado": sum(p["valor"] - p["custo"] for p in pos if _fin(p.get("custo")))}
    fat = g.distribuicao(pos, "fator")
    d = {}
    if M and D["rets"].shape[1] >= 2:
        P = D["pesos_total"]
        cols = [c for c in D["rets"].columns if c in P.index]
        w = P[cols] / P[cols].sum()
        corr = g.correlacao(D["rets"][cols])
        d = {"enb": g.n_efetivo_de_apostas(w, o.covariancia(D["rets"][cols], False)), "n_ativos": len(cols), "corr_media": g.correlacao_media(corr, w),
             "pares": g.pares_correlacionados(corr, 0.8)}
    if fat:
        d["fator_dominante"] = (fat[0]["nome"], fat[0]["pct"])
    res = st.session_state.get("gc_comp_res")
    if res:
        d["indiretas"] = res.get("indiretas", [])
    ctx["diversificacao"] = d
    tw = D.get("twr_total", {})
    if tw.get("ok"):
        ctx["desempenho"] = {"twr": tw["total"], "xirr": _xirr_total(C)}
        refs = C["referencias"]["series"]
        for nome in ("CDI", "Ibovespa"):
            if nome in refs:
                b = _base100(refs[nome], tw["indice"].index[0])
                if len(b) > 1:
                    ctx["desempenho"].update(bench_nome=nome, bench=float(b.iloc[-1] / 100 - 1))
                    break
        ctx["consistencia"] = g.consistencia(tw["retornos"])
    rc: dict[str, list] = {}
    for p in pos:
        if _fin(p.get("custo")) and p["custo"] > 0:
            rc.setdefault(p["classe"], [0.0, 0.0])
            rc[p["classe"]][0] += p["valor"]
            rc[p["classe"]][1] += p["custo"]
    ctx["retorno_por_classe"] = {k: v[0] / v[1] - 1 for k, v in rc.items()}
    ctx["renda_passiva"] = o.renda_passiva(C["eventos"], C["hoje"])
    alvos = _alvos_atuais()
    if alvos and abs(sum(alvos.values()) - 100) < 0.01:
        vals: dict[str, float] = {}
        for p in pos:
            vals[p["classe"]] = vals.get(p["classe"], 0.0) + p["valor"]
        ctx["desvios"] = g.desvios_do_alvo(vals, alvos, dict(st.session_state.get(K_TOL) or {}) or 5.0)
    ativos = []
    for p in pos:
        s = D["series"].get(p["id"])
        item = {"id": p["id"], "peso": p["valor"] / tot if tot else None}
        if s is not None and len(s) > 252:
            item["ret12m"] = float(s.iloc[-1] / s.iloc[-253] - 1)
            item["dd_atual"] = float(s.iloc[-1] / s.max() - 1)
        ativos.append(item)
    ativos += [{"id": p["id"], "sem_cotacao": True} for p in C["posicoes"] if not _fin(p.get("valor")) or p["valor"] <= 0]
    ctx["ativos"] = ativos
    return ctx


def _aba_relatorio(C, D):
    R = o.diagnostico(_contexto_relatorio(C, D))
    st.markdown(f"**Diagnóstico geral.** {R['resumo']}")
    titulos = [("pontos_fortes", "Pontos fortes"), ("fragilidades", "Fragilidades"), ("concentracoes", "Concentrações"), ("riscos", "Riscos identificados"),
               ("diversificacao", "Diversificação real"), ("evolucao", "Evolução patrimonial e desempenho"), ("consistencia", "Consistência"),
               ("classes", "Desempenho por classe"), ("melhorias", "Possíveis melhorias"), ("atencao", "Ativos que merecem atenção")]
    md = ["# Relatório da carteira", f"_Gerado em {date.today():%d/%m/%Y}._", "", R["resumo"], ""]
    for chave, tit in titulos:
        itens = R[chave]
        if not itens:
            continue
        st.markdown(f"#### {tit}")
        md.append(f"## {tit}")
        for it in itens:
            icone = {"ok": "✅", "atencao": "⚠️", "info": "•"}[it["nivel"]]
            st.markdown(f"{icone} {it['texto']}")
            md.append(f"- {icone} {it['texto']}")
        md.append("")
    md.append(f"_{NOTA}_")
    st.download_button("Baixar relatório (Markdown)", "\n".join(md).encode("utf-8"), file_name="relatorio_carteira.md", mime="text/markdown", key="gc_dl")
    st.caption(NOTA)


# =============================================================================== página
def _lotes_da_carteira(chave: str) -> list:
    return [l for l in st.session_state.get(chave, []) if isinstance(l, dict)]


def ler_carteira(chave: str):
    """(C, D) da carteira escolhida ('cart_real' ou 'cart_ficticia'), com a mesma coleta da página; None se não houver posições.
    Usada também pela Central de inteligência (Passo 13) para monitorar a carteira sem refazer os cálculos."""
    ss = st.session_state
    lotes = _lotes_da_carteira(chave)
    usa_extras = chave == "cart_real"
    rf_dicts = list(ss.get(rfa.CHAVE_CARTEIRA, []) or []) if usa_extras else []
    fundos = list(ss.get("cart_fundos_cvm", []) or []) if usa_extras else []
    caixa = None
    if chave == "cart_ficticia":
        gasto = moeda.custo_total_brl(lotes)
        caixa = None if gasto is None else float(ss.get("cart_capital", 100000.0)) - gasto
    if not lotes and not (rf_dicts or fundos):
        return None
    ss.setdefault(K_VENDAS[chave], [])
    C = coletar(json.dumps(lotes, default=str, sort_keys=True), json.dumps(ss[K_VENDAS[chave]], default=str, sort_keys=True),
                json.dumps(rf_dicts, default=str, sort_keys=True), json.dumps(fundos, default=str, sort_keys=True), caixa, date.today().isoformat())
    return C, _series_historicas(C)


def contexto_para_inteligencia(chave: str) -> dict | None:
    """Resumo da carteira para a Central de inteligência: maiores pesos, concentração, correlação e o diagnóstico do Passo 12.
    Só leitura. None se a carteira estiver vazia."""
    lido = ler_carteira(chave)
    if lido is None:
        return None
    C, D = lido
    ctx = _contexto_relatorio(C, D)
    R = o.diagnostico(ctx)
    pos = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
    tot = sum(p["valor"] for p in pos)
    classes: dict[str, float] = {}
    for p in pos:
        classes[p["classe"]] = classes.get(p["classe"], 0.0) + p["valor"]
    div = ctx.get("diversificacao") or {}
    return {"chave": chave, "data": C["hoje"].isoformat() if hasattr(C["hoje"], "isoformat") else str(C["hoje"]),
            "n_posicoes": len(pos), "maior_peso": (max(p["valor"] for p in pos) / tot * 100) if tot else None,
            "maior_ativo": max(pos, key=lambda p: p["valor"])["id"] if pos else None,
            "pesos_classe": {k: v / tot * 100 for k, v in classes.items()} if tot else {},
            "n_efetivo": div.get("enb") if div.get("enb") is not None else (ctx.get("conc") or {}).get("n_efetivo"),
            "corr_media": div.get("corr_media"), "resumo": R["resumo"],
            "pontos": [i["texto"] for sec in ("fragilidades", "concentracoes", "riscos", "atencao", "pontos_fortes") for i in R[sec]][:14],
            "concentracoes": [i["texto"] for i in R["concentracoes"]],
            "tickers": [p["id"] for p in pos]}


def posicoes_para_tecnica(chave: str = "cart_real") -> list[dict]:
    """[{"id","peso" (%),"classe"}] das posições da carteira para a Análise técnica avançada (Passo 14). Só leitura; lista vazia se não houver."""
    try:
        lido = ler_carteira(chave)
    except Exception:
        return []
    if lido is None:
        return []
    pos = [p for p in lido[0]["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0 and p.get("id") != "CAIXA"]
    tot = sum(p["valor"] for p in pos)
    return [{"id": p["id"], "peso": p["valor"] / tot * 100, "classe": p.get("classe", "acao")} for p in pos] if tot else []


def posicoes_para_noticias(chave: str = "cart_real") -> list[dict]:
    """[{"id","nome","classe","setor","subgrupo","peso" (%)}] das posições da carteira para a Central de notícias (Passo 15). Só leitura."""
    try:
        lido = ler_carteira(chave)
    except Exception:
        return []
    if lido is None:
        return []
    pos = [p for p in lido[0]["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0 and p.get("id") != "CAIXA"]
    tot = sum(p["valor"] for p in pos)
    return [{"id": p["id"], "nome": p.get("nome") or p["id"], "classe": p.get("classe", "acao"), "setor": p.get("setor"), "subgrupo": p.get("subgrupo"),
             "peso": p["valor"] / tot * 100} for p in pos] if tot else []


def pagina_gestao():
    st.markdown(tema.cabecalho("💼", "Gestão de carteira", "Alocação, risco, desempenho, renda passiva, otimização e cenários da sua carteira inteira."),
                unsafe_allow_html=True)
    ss = st.session_state
    real, fict = _lotes_da_carteira("cart_real"), _lotes_da_carteira("cart_ficticia")
    rf_dicts = list(ss.get(rfa.CHAVE_CARTEIRA, []) or [])
    fundos = list(ss.get("cart_fundos_cvm", []) or [])
    opcoes = ["Carteira real", "Carteira fictícia"]
    escolha = st.radio("Carteira", opcoes, horizontal=True, key="gc_carteira", index=0 if (real or rf_dicts or fundos or not fict) else 1)
    chave = "cart_real" if escolha == opcoes[0] else "cart_ficticia"
    lotes = real if chave == "cart_real" else fict
    usa_extras = chave == "cart_real"
    caixa = None
    if chave == "cart_ficticia":
        cap = float(ss.get("cart_capital", 100000.0))
        gasto = moeda.custo_total_brl(lotes)
        if gasto is None:
            st.warning("Sem a cotação do dólar agora: o caixa da simulação não foi calculado.")
        caixa = None if gasto is None else cap - gasto
    if not lotes and not (usa_extras and (rf_dicts or fundos)):
        st.markdown(tema.vazio("carteira", "Sem posições para analisar", "Registre compras em Carteira (ações, FIIs, ETFs, cripto) ou salve títulos em Renda fixa → Análise de títulos."),
                    unsafe_allow_html=True)
        return
    with st.spinner("Lendo preços, proventos e histórico da sua carteira..."):
        C, D = ler_carteira(chave)
    if usa_extras and (rf_dicts or fundos):
        st.caption("Inclui renda fixa (Renda fixa → Análise de títulos) e fundos por CNPJ (Carteira → ETFs e fundos).")
    try:                                  # resultado na barra de cada seção
        _vals = [p for p in C["posicoes"] if _fin(p.get("valor")) and p["valor"] > 0]
        _tot = sum(p["valor"] for p in _vals)
        _cus = sum(p["custo"] for p in _vals if _fin(p.get("custo")))
        _rp = o.renda_passiva([e for e in C["eventos"] if e.get("efetivo")], C["hoje"])
        _tw = D.get("twr_total", {})
        _res = {"Painel": (f"{_r(_tot)}" + (f" · {_p(_tot / _cus - 1, 1, True)}" if _cus > 0 else "")) if _tot > 0 else None,
                "Alocação": f"{len({p['classe'] for p in _vals})} classe(s)" if _vals else None,
                "Renda passiva": f"{_r(_rp['media_mensal_12m'])}/mês" if _rp.get("ok") else None,
                "Rentabilidade": f"TWR {_p(_tw.get('total'), 1, True)}" if _tw.get("ok") else None}
        _res = {k: v for k, v in _res.items() if v}
    except Exception:
        _res = {}
    tabs = secoes.abas(ABAS, resumos=_res)
    funcs = [lambda: _aba_painel(C, D, chave), lambda: _aba_alocacao(C, D), lambda: _aba_diversificacao(C, D), lambda: _aba_risco(C, D),
             lambda: _aba_rentabilidade(C, D), lambda: _aba_renda(C, D), lambda: _aba_otimizacao(C, D), lambda: _aba_rebalanceamento(C, D),
             lambda: _aba_cenarios(C, D), lambda: _aba_relatorio(C, D)]
    for t, f in zip(tabs, funcs):
        with t:
            f()
    st.caption(NOTA)
