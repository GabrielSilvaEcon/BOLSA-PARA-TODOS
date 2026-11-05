"""
Página "Análise de títulos" de renda fixa (Passo 11): coleta de dados reais e telas.

Fontes (gratuitas e oficiais):
  - Tesouro Transparente (PrecoTaxaTesouroDireto.csv): taxas e preços de compra e venda de todos os títulos do Tesouro
    Direto, com histórico. É a base da marcação a mercado oficial e da curva de juros de referência.
  - Banco Central (SGS): CDI diário (12), IPCA mensal (433), Selic meta (432), CDI anual (4389), IPCA 12 meses (13522).
  - Banco Central (Focus, API Olinda): expectativas de IPCA e Selic por ano, usadas como cenário (premissa).
  - Títulos privados (CDB, LCI, LCA, debêntures, CRI, CRA…): os dados do contrato são informados pelo usuário (ou lidos
    da descrição que ele colar); não há base pública gratuita com taxa e preço de cada título privado.
Cálculos em renda_fixa.py. Ferramenta educacional, não é recomendação de investimento.
"""
from __future__ import annotations

import math
import re
from dataclasses import replace
from datetime import date, timedelta

import pandas as pd
import streamlit as st

import profundidade_app

import comparador
import evolucao
import fundos as fd
import renda_fixa as rf
import tema

try:
    import requests
except Exception:                       # pragma: no cover
    requests = None
try:
    import dados
except Exception:                       # pragma: no cover
    dados = None

URL_FOCUS = ("https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/ExpectativasMercadoAnuais"
             "?$top=200&$filter=Indicador%20eq%20'IPCA'%20or%20Indicador%20eq%20'Selic'&$orderby=Data%20desc"
             "&$format=json&$select=Indicador,Data,DataReferencia,Mediana,baseCalculo")
CHAVE_CARTEIRA = "cart_rf"            # lista de títulos (dicts) — o prefixo cart_ é salvo na conta do usuário
SIGLAS_TD = {"tesouro_selic": "SELIC", "tesouro_prefixado": "PRE", "tesouro_prefixado_juros": "PREJS",
             "tesouro_ipca": "IPCA", "tesouro_ipca_juros": "IPCAJS", "tesouro_renda": "RENDA", "tesouro_educa": "EDUCA"}
ABAS = ["Visão geral", "Características", "Rentabilidade", "Tributação", "Riscos", "Liquidez", "Marcação a mercado",
        "Simulador", "Comparação", "Histórico", "Análise inteligente"]
NOTA_LEGAL = ("Ferramenta educacional, não é recomendação de investimento. Taxa contratada só é garantida até o vencimento "
              "e depende do emissor pagar; projeções usam premissas de CDI e IPCA; preços estimados não são executáveis.")


# =============================================================================== formatação
def _p(v, casas: int = 2, sinal: bool = False) -> str:
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "n/d"
    return (f"{v * 100:+,.{casas}f}" if sinal else f"{v * 100:,.{casas}f}").replace(",", "X").replace(".", ",").replace("X", ".") + "%"


def _r(v) -> str:
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "n/d"
    return "R$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _dt(d) -> str:
    try:
        return pd.Timestamp(d).strftime("%d/%m/%Y")
    except Exception:
        return "n/d"


def _n(v, casas: int = 1) -> str:
    if v is None or not isinstance(v, (int, float)) or not math.isfinite(v):
        return "n/d"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _cartoes(itens: list, por_linha: int = 4):
    for k in range(0, len(itens), por_linha):
        for col, (rot, val, cls, *det) in zip(st.columns(por_linha), itens[k:k + por_linha]):
            col.markdown(tema.card_status(rot, val, cls, det[0] if det else "", det[1] if len(det) > 1 else ""),
                         unsafe_allow_html=True)


# =============================================================================== coleta (dados reais)
def _sgs_ultimo(codigo: int) -> tuple[float | None, str | None]:
    """Último valor de uma série do SGS (fração) e a data."""
    s = _sgs_hist(codigo, 1)
    if s is None or s.empty:
        return None, None
    return float(s.iloc[-1]) / 100, s.index[-1].date().isoformat()


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _sgs_hist(codigo: int, anos: int) -> pd.Series:
    if dados is None:
        return pd.Series(dtype=float)
    try:
        df = dados.buscar_macro_bcb(codigo, anos)
        return df["valor"] if not df.empty else pd.Series(dtype=float)
    except Exception:
        return pd.Series(dtype=float)


def ler_focus(js: dict) -> dict:
    """JSON da API Focus (Olinda) → {"ipca": {ano: fração}, "selic": {ano: fração}, "data": "AAAA-MM-DD"}. Usa a pesquisa
    mais recente de cada indicador, base de cálculo 0 (todas as respostas). Vazio se o formato não bater."""
    out = {"ipca": {}, "selic": {}, "data": None}
    linhas = (js or {}).get("value") or []
    if not linhas:
        return out
    df = pd.DataFrame(linhas)
    if not {"Indicador", "Data", "DataReferencia", "Mediana"} <= set(df.columns):
        return out
    if "baseCalculo" in df:
        df = df[pd.to_numeric(df["baseCalculo"], errors="coerce").fillna(0) == 0]
    for nome, chave in (("IPCA", "ipca"), ("Selic", "selic")):
        x = df[df["Indicador"].astype(str).str.lower() == nome.lower()]
        if x.empty:
            continue
        ult = x["Data"].max()
        x = x[x["Data"] == ult]
        for r in x.itertuples():
            try:
                out[chave][int(str(r.DataReferencia)[:4])] = float(r.Mediana) / 100
            except (TypeError, ValueError):
                continue
        out["data"] = max(filter(None, [out["data"], str(ult)[:10]]))
    return out


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _focus() -> dict:
    if requests is None:
        return {}
    try:
        r = requests.get(URL_FOCUS, timeout=15, headers={"User-Agent": "bolsa-para-todos/1.0"})
        if r.status_code != 200:
            return {}
        return ler_focus(r.json())
    except Exception:
        return {}


def mercado() -> dict:
    """Tudo o que os cálculos precisam de dado real, já coletado (com cache) e com os avisos do que faltou."""
    b = evolucao.coletar_bcb()
    t = evolucao.coletar_tesouro()
    cdi, d_cdi = _sgs_ultimo(4389)
    ipca, d_ipca = _sgs_ultimo(13522)
    selic, _ = _sgs_ultimo(432)
    av = list(b.get("avisos", [])) + list(t.get("avisos", []))
    if cdi is None:
        av.append("CDI anual do Banco Central indisponível agora: o cenário 'de hoje' usa 14,90% a.a. (edite no cenário personalizado).")
    if ipca is None:
        av.append("IPCA 12 meses indisponível agora: o cenário 'de hoje' usa 4,50% a.a. (edite no cenário personalizado).")
    return {"cdi_idx": b.get("cdi_idx"), "ipca": b.get("ipca"), "td": t.get("t", pd.DataFrame()),
            "cdi_aa": cdi, "ipca_12m": ipca, "selic": selic, "data_cdi": d_cdi, "data_ipca": d_ipca,
            "focus": _focus(), "avisos": av}


def cenarios(m: dict) -> dict:
    cdi = m.get("cdi_aa") if m.get("cdi_aa") is not None else 0.149
    ipca = m.get("ipca_12m") if m.get("ipca_12m") is not None else 0.045
    out = {"hoje": rf.cenario_fixo(cdi, ipca, "Juros e inflação de hoje",
                                   f"CDI {_p(cdi)} a.a. e IPCA 12 meses {_p(ipca)} (Banco Central)")}
    fc = rf.cenario_focus(m.get("focus") or {}, cdi, ipca)
    if fc:
        out["focus"] = fc
    return out


# =============================================================================== Tesouro Direto (dados oficiais)
def titulos_tesouro_hoje(td: pd.DataFrame, hoje: date | None = None) -> pd.DataFrame:
    """Títulos do Tesouro na data mais recente do arquivo, ainda não vencidos, com taxas e preços de compra e venda."""
    if td is None or td.empty:
        return pd.DataFrame()
    hoje = hoje or date.today()
    ult = td["data"].max()
    x = td[(td["data"] == ult) & (td["venc"] > pd.Timestamp(hoje))].copy()
    x["tipo"] = x["titulo"].map(rf.tipo_do_tesouro)
    x = x[x["tipo"].notna()]
    x["codigo"] = [f"TD-{SIGLAS_TD[k]}-{v.year}" for k, v in zip(x["tipo"], x["venc"])]
    return x.sort_values(["tipo", "venc"]).reset_index(drop=True)


def titulo_do_tesouro(linha, valor: float, aplicacao: date | None = None) -> rf.Titulo:
    """Título do Tesouro comprado (simulação) na data base do arquivo, pela taxa de compra oficial."""
    k = linha["tipo"]
    venc_arq = pd.Timestamp(linha["venc"]).date()
    venc = venc_arq
    if k in ("tesouro_renda", "tesouro_educa"):
        # O arquivo traz o ano do título (início das parcelas). As parcelas mensais vão de janeiro desse ano até dezembro,
        # 5 anos depois (Educa+, 60 parcelas) ou 20 anos depois (Renda+, 240): ex.: Educa+ 2030 paga de 01/2030 a 12/2034.
        n = rf.PARCELAS_RENDA if k == "tesouro_renda" else rf.PARCELAS_EDUCA
        venc = date(venc_arq.year + n // 12 - 1, 12, 15)
    tx = linha.get("taxa_compra")
    if tx is None or (isinstance(tx, float) and math.isnan(tx)):
        tx = linha.get("taxa_venda")
    return rf.Titulo(tipo=k, indexador=rf.TIPOS[k].indexadores[0], taxa=float(tx) / 100,
                     aplicacao=aplicacao or pd.Timestamp(linha["data"]).date(), vencimento=venc,
                     valor=valor, emissor="Tesouro Nacional", nome=f"{linha['titulo']} {pd.Timestamp(linha['venc']).year}",
                     liquidez="diaria", pagamento=rf.TIPOS[k].pagamento_padrao, td_titulo=str(linha["titulo"]),
                     td_venc=pd.Timestamp(linha["venc"]).date(), id=f"{SIGLAS_TD[k]}{pd.Timestamp(linha['venc']).year}".lower())


def precos_oficiais(t: rf.Titulo, td: pd.DataFrame) -> dict:
    """Para um título do Tesouro: PU de compra na data da aplicação (→ quantidade), PU e taxa de venda mais recentes
    (preço oficial de recompra pelo Tesouro). Série histórica do PU para gráficos."""
    if not t.td_titulo or td is None or td.empty:
        return {"ok": False}
    s = td[(td["titulo"] == t.td_titulo) & (td["venc"] == pd.Timestamp(t.td_venc or t.vencimento))].sort_values("data")
    if s.empty:
        return {"ok": False, "motivo": "título não encontrado no arquivo do Tesouro"}
    antes = s[s["data"] <= pd.Timestamp(t.aplicacao)]
    if antes.empty:
        return {"ok": False, "motivo": "sem preço do Tesouro na data da aplicação"}
    a = antes.iloc[-1]
    pu_c = a.get("pu_compra") if pd.notna(a.get("pu_compra")) else a["pu"]
    u = s.iloc[-1]
    pu_v = u.get("pu_venda") if pd.notna(u.get("pu_venda")) else u["pu"]
    tx_v = u.get("taxa_venda") if pd.notna(u.get("taxa_venda")) else u.get("taxa_compra")
    qtd = t.valor / float(pu_c) if pu_c else None
    return {"ok": qtd is not None, "qtd": qtd, "pu_compra": float(pu_c), "data_compra": a["data"].date(),
            "pu_venda": float(pu_v), "taxa_venda": None if tx_v is None or pd.isna(tx_v) else float(tx_v) / 100,
            "data": u["data"].date(), "valor_mercado": qtd * float(pu_v) if qtd else None,
            "serie": s.set_index("data")[["pu", "taxa_compra"] + [c for c in ("pu_venda", "taxa_venda") if c in s]]}


def resolver_td(codigo: str, td: pd.DataFrame) -> pd.Series | None:
    m = re.fullmatch(r"TD-([A-Z]+)-(\d{4})", (codigo or "").upper().strip())
    if not m:
        return None
    hoje = titulos_tesouro_hoje(td)
    x = hoje[hoje["codigo"] == m.group(0)] if not hoje.empty else hoje
    return None if x.empty else x.iloc[0]


# =============================================================================== análise completa de um título
def analisar(t: rf.Titulo, m: dict, cen: rf.Cenario, hoje: date | None = None, spread_delta: float = 0.0,
             emissor_pct: float | None = None) -> dict:
    """Junta todas as análises do título: curva (realizado), até o vencimento (esperado), marcação a mercado (oficial
    para Tesouro; estimada para os demais), riscos, nota educacional e o texto da análise inteligente."""
    hoje = hoje or date.today()
    erros = rf.validar(t)
    if erros:
        return {"ok": False, "erros": erros}
    curva = rf.valor_na_curva(t, m, cen, hoje)
    venc = rf.resultado_ate_vencimento(t, cen, m, hoje)
    oficial = precos_oficiais(t, m.get("td")) if t.td_titulo else {"ok": False}
    tm = {"ok": False}
    if t.indexador in ("pre", "ipca"):
        if oficial.get("ok") and oficial.get("taxa_venda") is not None:
            tm = {"ok": True, "taxa": oficial["taxa_venda"], "origem": f"taxa de venda do Tesouro ({_dt(oficial['data'])})"}
        else:
            tm = rf.taxa_de_mercado_estimada(t, m.get("td"), hoje)
            if tm.get("ok"):
                tm["origem"] = ("curva do Tesouro hoje + o prêmio que o título pagava sobre o Tesouro na aplicação "
                                f"({_p(tm['premio'], sinal=True)})")
    elif t.indexador in ("cdi_pct", "cdi_mais", "selic"):
        novo = t.taxa + (spread_delta if t.indexador != "cdi_pct" else spread_delta / max(cenarios(m)["hoje"].cdi_de(hoje.year), 1e-6))
        tm = {"ok": True, "taxa": novo, "origem": "prêmio do emissor igual ao da compra" if not spread_delta else
              f"prêmio do emissor {_p(spread_delta, sinal=True)} em relação à compra (premissa sua)"}
    mam = rf.preco_pela_taxa(t, tm["taxa"], m, cen, hoje) if tm.get("ok") and t.aplicacao <= hoje < t.vencimento else {"ok": False}
    if oficial.get("ok") and mam.get("ok") and oficial.get("valor_mercado"):
        mam["preco"] = oficial["valor_mercado"]                     # Tesouro: o preço é o oficial, não o estimado
        mam["oficial"] = True
    rs = rf.riscos(t, mam if mam.get("ok") and mam.get("tipo_risco") == "juros" else None, hoje, emissor_pct)
    rc = rf.risco_credito(t)
    ind = {"taxa_real_aa": venc.get("taxa_real_aa"), "risco_credito": rc["nivel"], "liquidez_dias": rf.dias_ate_liquidez(t, hoje),
           "duration": mam.get("mod") if mam.get("ok") else None}
    nota = rf.pontuar(ind)
    cdi_ref = cenarios(m)["hoje"].cdi_de(hoje.year)
    ipca_ref = cenarios(m)["hoje"].ipca_de(hoje.year)
    rel = rf.relatorio(t, curva, venc, mam, rs, cdi_ref, ipca_ref, hoje)
    return {"ok": True, "t": t, "curva": curva, "venc": venc, "oficial": oficial, "tm": tm, "mam": mam, "riscos": rs,
            "credito": rc, "nota": nota, "ind": ind, "relatorio": rel, "cenario": cen, "hoje": hoje}


def realizado_vs_indices(t: rf.Titulo, m: dict, cen: rf.Cenario, hoje: date | None = None) -> dict:
    """Mesmo período (aplicação → hoje): título na curva × CDI × Selic × IPCA (dados reais do Banco Central)."""
    hoje = hoje or date.today()
    fim = min(hoje, t.vencimento)
    if fim <= t.aplicacao:
        return {"ok": False}
    cdi, ate = rf.fator_cdi_realizado("cdi_pct", 1.0, t.aplicacao, fim, m.get("cdi_idx"))
    selic, _ = rf.fator_cdi_realizado("selic", 0.0, t.aplicacao, fim, m.get("cdi_idx"))
    ipca, ate_i = rf.fator_ipca_realizado(t.aplicacao, fim, m.get("ipca"))
    c = rf.valor_na_curva(t, m, cen, hoje)
    tit = c.get("acumulado") if c.get("ok") else None
    return {"ok": True, "titulo": tit, "cdi": None if cdi is None else cdi - 1, "selic": None if selic is None else selic - 1,
            "ipca": None if ate_i is None else ipca - 1, "ate_cdi": ate, "ate_ipca": ate_i,
            "pct_cdi": (tit / (cdi - 1)) if tit is not None and cdi and cdi > 1 else None}


# =============================================================================== comparador (Passo 6)
def ativo_de_analise(a: dict, chave: str, preco_hist: pd.Series | None = None) -> comparador.Ativo:
    t = a["t"]
    v, n = a["venc"], a["nota"]
    I = comparador.Ind
    mam = a.get("mam") or {}
    ind = {
        "taxa_bruta_aa": I(None if v.get("taxa_bruta_aa") is None else v["taxa_bruta_aa"] * 100, "estimado", "até o vencimento"),
        "taxa_liquida_aa": I(None if v.get("taxa_liquida_aa") is None else v["taxa_liquida_aa"] * 100, "estimado", "até o vencimento"),
        "taxa_real_aa": I(None if v.get("taxa_real_aa") is None else v["taxa_real_aa"] * 100, "estimado", "até o vencimento"),
        "prazo_anos": I(rf.du(a["hoje"], t.vencimento) / 252, "calculado"),
        "duration": I(mam.get("mod") if mam.get("ok") else None, "calculado", aplica=t.indexador in ("pre", "ipca")),
        "liquidez_dias": I(float(rf.dias_ate_liquidez(t, a["hoje"])), "calculado"),
        "risco_credito": I(float(a["credito"]["nivel"]), "calculado"),
        "isento": I(1.0 if t.t.isento_ir_pf else 0.0, "dado"),
        "fgc": I(1.0 if t.t.fgc else 0.0, "dado"),
        "protecao_inflacao": I(2.0 if t.indexador == "ipca" else 1.0 if t.indexador in ("cdi_pct", "cdi_mais", "selic") else 0.0, "dado"),
        "sens_1pp": I(mam["sens"].get(0.01, mam["sens"].get(0.005)) * 100 if mam.get("ok") and mam.get("sens") else None, "estimado"),
    }
    if preco_hist is not None and len(preco_hist) > 30:                 # Tesouro: preço de mercado real (PU)
        ind.update(comparador.inds_de_preco(comparador.metricas_preco(preco_hist)))
    else:
        r12 = None
        c = a.get("curva") or {}
        if c.get("ok") and c.get("dias", 0) >= 365:
            ini = a["hoje"] - timedelta(days=365)
            f0 = rf.fator_realizado(t, ini, a.get("_m") or {}, a["cenario"])["fator"]
            f1 = rf.fator_realizado(t, a["hoje"], a.get("_m") or {}, a["cenario"])["fator"]
            r12 = (f1 / f0 - 1) * 100
        ind["ret12m"] = I(r12, "calculado", "12m (na curva)")
        ind["vol"] = I(None, aplica=False)
        ind["dd_max"] = I(None, aplica=False)
    pont = comparador.Pontuacao(None if n["nota"] is None else n["nota"], n["pilares"], n["pesos"], n["cobertura"],
                                metodo="Renda fixa: retorno real esperado, crédito, liquidez e risco de mercado",
                                provisoria=n["provisoria"])
    avisos = []
    if v.get("ok"):
        avisos.append(f"Retornos esperados sob o cenário '{v['cenario']}' (premissa, não promessa).")
    return comparador.Ativo(chave, t.nome or t.rotulo(), "renda_fixa", "BRL", a["hoje"].isoformat(),
                            "Tesouro Transparente/BCB" if t.t.grupo == "tesouro" else "dados do contrato + BCB",
                            ind, pont, avisos, subgrupo=t.indexador, subgrupo_nome=rf.INDEXADORES[t.indexador].split(" (")[0])


def _titulos_carteira() -> list[rf.Titulo]:
    out = []
    for d in st.session_state.get(CHAVE_CARTEIRA, []) or []:
        try:
            out.append(rf.Titulo.de_dict(d))
        except Exception:
            continue
    return out


def ativo_rf(codigo: str) -> comparador.Ativo:
    """Para a página Comparar: TD-IPCA-2035 (Tesouro, preço oficial de hoje) ou RF-<id> (título salvo na carteira)."""
    cod = (codigo or "").strip().upper()
    try:
        m = mercado()
        cen = cenarios(m)["hoje"]
        if cod.startswith("TD-"):
            linha = resolver_td(cod, m["td"])
            if linha is None:
                return comparador.Ativo(cod, cod, "renda_fixa", erro="título do Tesouro não encontrado (confira o código)")
            t = titulo_do_tesouro(linha, 1000.0)
            a = analisar(t, m, cen)
            a["_m"] = m
            serie = precos_oficiais(t, m["td"]).get("serie")
            return ativo_de_analise(a, cod, None if serie is None else serie["pu"])
        if cod.startswith("RF-"):
            alvo = cod[3:].lower()
            t = next((x for x in _titulos_carteira() if x.id.lower() == alvo), None)
            if t is None:
                return comparador.Ativo(cod, cod, "renda_fixa", erro="título não encontrado na sua carteira de renda fixa")
            a = analisar(t, m, cen)
            if not a["ok"]:
                return comparador.Ativo(cod, cod, "renda_fixa", erro="; ".join(a["erros"]))
            a["_m"] = m
            serie = precos_oficiais(t, m["td"]).get("serie") if t.td_titulo else None
            return ativo_de_analise(a, cod, None if serie is None else serie["pu"])
    except Exception as e:
        return comparador.Ativo(cod, cod, "renda_fixa", erro=f"erro inesperado ({e.__class__.__name__})")
    return comparador.Ativo(cod, cod, "renda_fixa", erro="código de renda fixa desconhecido (use TD-… ou RF-…)")


def codigo_de(t: rf.Titulo) -> str:
    if t.td_titulo and t.tipo in SIGLAS_TD and not any(x.id == t.id for x in _titulos_carteira()):
        return f"TD-{SIGLAS_TD[t.tipo]}-{(t.td_venc or t.vencimento).year}"
    return f"RF-{t.id.upper()}"


# =============================================================================== formulário do título
def _padrao(chave: str, valor) -> dict:
    """value= só na primeira vez: com a chave já na sessão, o Streamlit avisa se receber os dois."""
    return {} if chave in st.session_state else {"value": valor}


def _form_titulo(prefixo: str, base: rf.Titulo | None = None) -> rf.Titulo | None:
    """Campos do título. A descrição colada (opcional) preenche o que der; o resto o usuário escolhe."""
    hoje = date.today()
    ss = st.session_state
    with st.expander("Colar a descrição do título (preenche automaticamente)", expanded=base is None):
        txt = st.text_input("Descrição", key=f"{prefixo}_txt", placeholder="Ex.: CDB Banco X 110% do CDI venc. 15/03/2028 liquidez diária")
        if st.button("Ler descrição", key=f"{prefixo}_ler") and txt:
            r = rf.interpretar(txt)
            if not r.get("achados"):
                st.warning("Não reconheci nada nessa descrição. Preencha os campos abaixo.")
            else:
                if "tipo" in r:
                    ss[f"{prefixo}_tipo"] = r["tipo"]
                if "indexador" in r:
                    ss[f"{prefixo}_idx"] = r["indexador"]
                if "taxa" in r:
                    ss[f"{prefixo}_taxa"] = round(r["taxa"] * 100, 4)
                if "vencimento" in r:
                    ss[f"{prefixo}_venc"] = r["vencimento"]
                elif "ano_vencimento" in r:
                    ss[f"{prefixo}_venc"] = date(r["ano_vencimento"], 1, 1)
                if "liquidez" in r:
                    ss[f"{prefixo}_liq"] = r["liquidez"]
                if "pagamento" in r:
                    ss[f"{prefixo}_pag"] = r["pagamento"]
                if "emissor" in r:
                    ss[f"{prefixo}_em"] = r["emissor"]
                st.success("Identificado: " + ", ".join(r["achados"]) + ". Confira os campos"
                           + (" (só o ano do vencimento foi informado: ajuste o dia)." if "ano_vencimento" in r else "."))
    if base is not None and not ss.get(f"{prefixo}_carregado") == base.id:
        ss.update({f"{prefixo}_tipo": base.tipo, f"{prefixo}_idx": base.indexador,
                   f"{prefixo}_taxa": round(base.taxa * 100, 4), f"{prefixo}_apl": base.aplicacao,
                   f"{prefixo}_venc": base.vencimento, f"{prefixo}_valor": float(base.valor), f"{prefixo}_em": base.emissor,
                   f"{prefixo}_liq": base.liquidez, f"{prefixo}_pag": base.pagamento, f"{prefixo}_gar": base.garantia,
                   f"{prefixo}_rat": base.rating, f"{prefixo}_tk": base.emissor_ticker, f"{prefixo}_carregado": base.id})
        if base.carencia:
            ss[f"{prefixo}_car"] = base.carencia
    tipos = [k for k in rf.TIPOS if rf.TIPOS[k].grupo != "tesouro"] + [k for k in rf.TIPOS if rf.TIPOS[k].grupo == "tesouro"]
    c1, c2, c3 = st.columns(3)
    tp = c1.selectbox("Tipo", tipos, key=f"{prefixo}_tipo", format_func=lambda k: rf.TIPOS[k].nome)
    idxs = list(rf.TIPOS[tp].indexadores)
    if ss.get(f"{prefixo}_idx") not in idxs:
        ss[f"{prefixo}_idx"] = idxs[0]
    ix = c2.selectbox("Indexador", idxs, key=f"{prefixo}_idx", format_func=lambda k: rf.INDEXADORES[k])
    tx = c3.number_input("% do CDI" if ix == "cdi_pct" else "Taxa (% a.a.)", key=f"{prefixo}_taxa", min_value=-5.0,
                         max_value=300.0, step=0.05, format="%.2f", **_padrao(f"{prefixo}_taxa", 110.0 if ix == "cdi_pct" else 6.0))
    c4, c5, c6 = st.columns(3)
    apl = c4.date_input("Data da aplicação", key=f"{prefixo}_apl", format="DD/MM/YYYY", **_padrao(f"{prefixo}_apl", hoje),
                        min_value=date(2000, 1, 1), max_value=hoje + timedelta(days=30))
    venc = c5.date_input("Vencimento", key=f"{prefixo}_venc", format="DD/MM/YYYY", **_padrao(f"{prefixo}_venc", hoje + timedelta(days=730)),
                         min_value=date(2000, 1, 2), max_value=date(2100, 12, 31))
    valor = c6.number_input("Valor aplicado (R$)", key=f"{prefixo}_valor", min_value=0.0, step=100.0, **_padrao(f"{prefixo}_valor", 1000.0))
    c7, c8, c9 = st.columns(3)
    em = c7.text_input("Emissor", key=f"{prefixo}_em", placeholder="Ex.: Banco X, Empresa Y",
                       disabled=rf.TIPOS[tp].grupo == "tesouro")
    liq = c8.selectbox("Liquidez", list(rf.LIQUIDEZ), key=f"{prefixo}_liq", format_func=lambda k: rf.LIQUIDEZ[k],
                       disabled=rf.TIPOS[tp].grupo == "tesouro")
    pag = c9.selectbox("Pagamento", list(rf.PAGAMENTOS), key=f"{prefixo}_pag", format_func=lambda k: rf.PAGAMENTOS[k],
                       disabled=rf.TIPOS[tp].grupo == "tesouro")
    if tp in ("tesouro_renda", "tesouro_educa"):
        st.caption("Renda+ e Educa+: informe como vencimento a data da ÚLTIMA parcela (ex.: Educa+ 2030 → 15/12/2034).")
    car = None
    if liq == "carencia" and rf.TIPOS[tp].grupo != "tesouro":
        car = st.date_input("Fim da carência", key=f"{prefixo}_car", format="DD/MM/YYYY", **_padrao(f"{prefixo}_car", min(apl + timedelta(days=180), venc)))
    with st.expander("Garantias, rating e emissor (opcional)"):
        g1, g2, g3 = st.columns(3)
        gar = g1.text_input("Garantia", key=f"{prefixo}_gar", placeholder="Ex.: alienação fiduciária, fiança")
        rat = g2.text_input("Rating", key=f"{prefixo}_rat", placeholder="Ex.: AA+ (Fitch)")
        tk = g3.text_input("Código na bolsa do emissor", key=f"{prefixo}_tk", placeholder="Ex.: PETR4 (saúde financeira)")
    grupo = rf.TIPOS[tp].grupo
    return rf.Titulo(tipo=tp, indexador=ix, taxa=tx / 100, aplicacao=apl, vencimento=venc, valor=valor,
                     emissor="Tesouro Nacional" if grupo == "tesouro" else (em or "").strip(),
                     liquidez="diaria" if grupo == "tesouro" else liq,
                     carencia=car, pagamento=rf.TIPOS[tp].pagamento_padrao if grupo == "tesouro" else pag,
                     garantia=(gar or "").strip(), rating=(rat or "").strip(), emissor_ticker=(tk or "").strip().upper(),
                     id=base.id if base is not None else ss.setdefault(f"{prefixo}_id", _novo_id()))


def _novo_id() -> str:
    return rf.Titulo.__dataclass_fields__["id"].default_factory()


def salvar_na_carteira(t: rf.Titulo):
    lista = list(st.session_state.get(CHAVE_CARTEIRA, []) or [])
    lista = [d for d in lista if d.get("id") != t.id] + [t.para_dict()]
    st.session_state[CHAVE_CARTEIRA] = lista


def remover_da_carteira(id_: str):
    st.session_state[CHAVE_CARTEIRA] = [d for d in st.session_state.get(CHAVE_CARTEIRA, []) or [] if d.get("id") != id_]


# =============================================================================== abas
def _aba_visao(a: dict):
    t, c, v, mam = a["t"], a["curva"], a["venc"], a["mam"]
    st.caption(f"{t.t.nome} · {t.emissor or 'emissor não informado'} · {rf.texto_taxa(t)} · vence {_dt(t.vencimento)}")
    n = a["nota"]
    itens = [("Nota educacional", "n/d" if n["nota"] is None else f"{n['nota']:.0f}/100",
              "na" if n["nota"] is None else "good" if n["nota"] >= 70 else "fair" if n["nota"] >= 50 else "bad",
              f"cobertura {n['cobertura'] * 100:.0f}%" + (" · provisória" if n["provisoria"] else "")),
             ("Valor hoje (na curva)", _r(c.get("valor_atual")) if c.get("ok") else "n/d", "info",
              ("+ recebido " + _r(c["recebido"])) if c.get("ok") and c.get("recebido") else "pela taxa contratada"),
             ("Rendimento acumulado", _p(c.get("acumulado"), sinal=True) if c.get("ok") else "n/d",
              "na" if not c.get("ok") else "good" if c["acumulado"] >= 0 else "bad",
              ("realizado" + (" (parte projetada)" if c.get("parcial") else "")) if c.get("ok") else c.get("motivo", "")),
             ("Líquido esperado (a.a.)", _p(v.get("taxa_liquida_aa")), "info", "até o vencimento, cenário"),
             ("Real esperado (a.a.)", _p(v.get("taxa_real_aa"), sinal=True),
              "na" if v.get("taxa_real_aa") is None else "good" if v["taxa_real_aa"] >= 0.04 else "fair" if v["taxa_real_aa"] >= 0.02 else "bad",
              "descontada a inflação"),
             ("Risco de crédito", f"{a['credito']['nivel']}/5", "good" if a["credito"]["nivel"] <= 2 else "fair" if a["credito"]["nivel"] == 3 else "bad",
              a["credito"]["texto"]),
             ("Liquidez", f"{a['ind']['liquidez_dias']} dia(s)" if a["ind"]["liquidez_dias"] > 1 else "diária",
              "good" if a["ind"]["liquidez_dias"] <= 1 else "fair" if a["ind"]["liquidez_dias"] <= 365 else "bad",
              rf.LIQUIDEZ.get(t.liquidez, "") if t.t.grupo != "tesouro" else "recompra do Tesouro"),
             ("Preço de mercado", _r(mam.get("preco")) if mam.get("ok") else "n/d",
              "info" if mam.get("ok") else "na", ("oficial do Tesouro" if mam.get("oficial") else "estimado") if mam.get("ok") else
              (a["tm"].get("motivo") or mam.get("motivo") or ""))]
    _cartoes(itens)
    st.caption(f"Cenário: {a['cenario'].nome}" + (f" ({a['cenario'].origem})" if a["cenario"].origem else "")
               + ". Retorno esperado é premissa, não promessa.")
    st.caption(t.t.descricao)


def _aba_caracteristicas(a: dict):
    t = a["t"]
    tp = t.t
    hoje = a["hoje"]
    rc = a["credito"]
    linhas = [("Tipo de título", tp.nome, "informado" if tp.grupo != "tesouro" else "Tesouro Transparente"),
              ("Emissor", t.emissor or "n/d", "lei (Tesouro Nacional)" if tp.grupo == "tesouro" else "informado"),
              ("Indexador", rf.INDEXADORES[t.indexador], "informado"),
              ("Taxa contratada", rf.texto_taxa(t), "Tesouro Transparente (taxa de compra)" if t.td_titulo else "informado"),
              ("Data de aplicação", _dt(t.aplicacao), "informado"),
              ("Data de vencimento", _dt(t.vencimento), "informado"),
              ("Prazo restante", f"{rf.dc(hoje, t.vencimento)} dias corridos · {rf.du(hoje, t.vencimento)} dias úteis"
               if t.vencimento > hoje else "vencido", "calculado (calendário ANBIMA)"),
              ("Liquidez", tp.liquidez_tipica if tp.grupo == "tesouro" else rf.LIQUIDEZ.get(t.liquidez, t.liquidez), "regra/informado"),
              ("Carência", _dt(t.carencia) if t.carencia else "não", "informado"),
              ("Forma de pagamento", rf.PAGAMENTOS[rf._pagamento(t)], "lei" if tp.grupo == "tesouro" else "informado"),
              ("Regime tributário", "Isento de IR (pessoa física)" if tp.isento_ir_pf else "IR regressivo (22,5% a 15%)"
               + ("" if not tp.iof else " + IOF se resgatar em menos de 30 dias"), "lei"),
              ("Garantias", "Tesouro Nacional (soberano)" if tp.grupo == "tesouro" else
               ("FGC até R$ 250 mil por instituição" if tp.fgc else "sem FGC") + (f"; {t.garantia}" if t.garantia else ""),
               "lei/informado"),
              ("Classificação de risco", t.rating or "não informada", "informado (o app não tem base gratuita de ratings)"),
              ("Risco de crédito (régua do app)", f"{rc['nivel']}/5 ({rc['texto']}): {rc['motivo']}", "calculado")]
    st.dataframe(pd.DataFrame(linhas, columns=["Característica", "Valor", "Origem"]), hide_index=True, width="stretch",
                 column_config={"Valor": st.column_config.TextColumn(width="large")})


def _aba_rentabilidade(a: dict, m: dict, cen_todos: dict):
    t, c, v = a["t"], a["curva"], a["venc"]
    st.markdown("**Contratada × realizada × esperada**")
    linhas = [("Contratada", rf.texto_taxa(t), "o que o título promete pagar até o vencimento"),
              ("Realizada (acumulada)", _p(c.get("acumulado"), sinal=True) if c.get("ok") else "n/d",
               ("desde " + _dt(t.aplicacao) + (f"; dado real até {_dt(c['real_ate'])}" if c.get("real_ate") else "")) if c.get("ok") else c.get("motivo", "")),
              ("Realizada (ao ano)", _p(c.get("anualizado")) if c.get("ok") else "n/d", "só com 3 meses ou mais"),
              ("Bruta esperada (ao ano)", _p(v.get("taxa_bruta_aa")), f"até o vencimento, cenário: {v.get('cenario', 'n/d')}"),
              ("Líquida esperada (ao ano)", _p(v.get("taxa_liquida_aa")), "depois de IR, IOF e custódia"),
              ("Real esperada (ao ano)", _p(v.get("taxa_real_aa"), sinal=True), "líquida, descontada a inflação"),
              ("Total recebido até o vencimento", _r(v.get("liquido_total")) + " líquido", f"bruto {_r(v.get('bruto_total'))}")]
    st.dataframe(pd.DataFrame(linhas, columns=["Rentabilidade", "Valor", "Como ler"]), hide_index=True, width="stretch")
    rv = realizado_vs_indices(t, m, a["cenario"], a["hoje"])
    if rv.get("ok"):
        st.markdown("**No mesmo período, contra os índices (dados do Banco Central)**")
        st.dataframe(pd.DataFrame([("Este título (na curva)", _p(rv["titulo"], sinal=True)),
                                   ("CDI", _p(rv["cdi"], sinal=True)), ("Selic (≈ CDI + 0,10 p.p.)", _p(rv["selic"], sinal=True)),
                                   ("IPCA", _p(rv["ipca"], sinal=True) + (f" (até {_dt(rv['ate_ipca'])})" if rv.get("ate_ipca") else "")),
                                   ("% do CDI", "n/d" if rv["pct_cdi"] is None else f"{rv['pct_cdi'] * 100:.0f}%".replace(".", ","))],
                                  columns=["Comparação", "Acumulado"]), hide_index=True, width="stretch")
    st.markdown("**Retorno até o vencimento em cenários diferentes (premissas, não previsões)**")
    tab = rf.tabela_cenarios(t, a["cenario"], m, a["hoje"])
    if tab.empty:
        st.caption("Sem cenários calculáveis.")
    else:
        mostrar = tab.assign(**{"CDI": tab["CDI"].map(lambda x: _p(x, 1, True) if x else "base"),
                                "IPCA": tab["IPCA"].map(lambda x: _p(x, 1, True) if x else "base"),
                                "Total líquido": tab["liquido_total"].map(_r), "Líquido a.a.": tab["taxa_liquida_aa"].map(_p),
                                "Real a.a.": tab["taxa_real_aa"].map(lambda x: _p(x, sinal=True))})
        if t.indexador == "pre":
            mostrar = mostrar[mostrar["CDI"] == "base"]
            st.caption("Prefixado: o CDI não muda o que o título paga; só a inflação muda o ganho real.")
        elif t.indexador in ("cdi_pct", "cdi_mais", "selic"):
            st.caption("Pós-fixado: o CDI muda o que o título paga; a inflação muda o ganho real.")
        st.dataframe(mostrar[["CDI", "IPCA", "Total líquido", "Líquido a.a.", "Real a.a."]], hide_index=True, width="stretch")
    if "focus" in cen_todos:
        f = cen_todos["focus"]
        st.caption("Focus (Banco Central, " + str(f.origem or "") + "): IPCA " + ", ".join(f"{k}: {_p(v, 1)}" for k, v in sorted(f.ipca.items()) if k)
                   + " · CDI médio estimado " + ", ".join(f"{k}: {_p(v, 1)}" for k, v in sorted(f.cdi.items()) if k) + ".")


def _aba_tributacao(a: dict):
    t, c, v = a["t"], a["curva"], a["venc"]
    hoje = a["hoje"]
    tp = t.t
    dias = rf.dc(t.aplicacao, hoje)
    st.markdown("**Regras deste título**")
    regras = [("Imposto de Renda", "Isento para pessoa física (lei)" if tp.isento_ir_pf else
               f"Tabela regressiva: hoje {_p(rf.aliquota_ir(max(dias, 1)), 1)} sobre o rendimento; no vencimento "
               f"{_p(rf.aliquota_ir(rf.dc(t.aplicacao, t.vencimento)), 1)}"),
              ("IOF", "Não se aplica na prática (isento ou com carência maior que 30 dias)" if not tp.iof else
               ("Resgate no mesmo dia: ainda não há rendimento" if dias < 1 else
                f"Hoje: {_p(rf.aliquota_iof(dias), 0)} do rendimento (zera no 30º dia)" if dias < 30 else "Zero (mais de 30 dias)")),
              ("Custódia", "Tesouro: 0,20% a.a. (B3); Tesouro Selic isento até R$ 10 mil; Renda+/Educa+ sem taxa até o vencimento"
               if tp.grupo == "tesouro" else "Em geral sem taxa (confira a corretora)"),
              ("FGC", "Não se aplica (risco soberano)" if tp.grupo == "tesouro" else
               "Coberto até R$ 250 mil por CPF/CNPJ por instituição ou conglomerado; teto de R$ 1 milhão a cada 4 anos" if tp.fgc
               else "NÃO coberto pelo FGC")]
    st.dataframe(pd.DataFrame(regras, columns=["Item", "Regra"]), hide_index=True, width="stretch",
                 column_config={"Regra": st.column_config.TextColumn(width="large")})
    st.markdown("**Bruto e líquido**")
    linhas = []
    if c.get("ok") and hoje < t.vencimento and c.get("valor_atual"):
        anos = rf.du(t.aplicacao, hoje) / 252
        cust = rf.custodia_tesouro(t.tipo, (t.valor + c["valor_atual"]) / 2, anos, ate_vencimento=False)
        x = rf.tributar(t.valor, c["valor_atual"], dias, t.tipo, cust)
        linhas.append(("Se resgatar hoje pela curva" + ("" if t.liquidez == "diaria" or tp.grupo == "tesouro" else " (se o título permitir)"),
                       _r(x["bruto"]), _r(x["iof"]), _r(x["ir"]), _r(x["custodia"]), _r(x["liquido"])))
    if v.get("ok"):
        linhas.append(("Até o vencimento (cenário)", _r(v["bruto_total"]), "—", _r(v["imposto_total"] - v["custodia"]),
                       _r(v["custodia"]), _r(v["liquido_total"])))
    if linhas:
        st.dataframe(pd.DataFrame(linhas, columns=["Situação", "Bruto", "IOF", "IR", "Custódia", "Líquido"]), hide_index=True, width="stretch")
    prazo = rf.dc(t.aplicacao, t.vencimento)
    if tp.isento_ir_pf and v.get("taxa_bruta_aa"):
        st.caption(f"Equivalência: para empatar com este isento, um título tributável no mesmo prazo precisaria render "
                   f"{_p(rf.taxa_equivalente_tributavel(v['taxa_bruta_aa'], prazo))} a.a. bruto.")
    elif not tp.isento_ir_pf and v.get("taxa_bruta_aa"):
        st.caption(f"Equivalência: um isento (LCI/LCA) no mesmo prazo empata com {_p(v['taxa_bruta_aa'] * (1 - rf.aliquota_ir(prazo)))} a.a.")
    st.caption("Juros periódicos pagam IR em cada pagamento, com a alíquota do prazo desde a aplicação. Custódia aproximada "
               "pelo valor médio do período. Regras gerais para pessoa física; confira as vigentes.")


def _aba_riscos(a: dict):
    t = a["t"]
    cor = {"baixo": "🟢", "médio": "🟡", "alto": "🔴", "n.a.": "⚪"}
    st.dataframe(pd.DataFrame([(cor.get(r["nivel"], "") + " " + r["nivel"], r["risco"], r["explicacao"]) for r in a["riscos"]],
                              columns=["Nível", "Risco", "Por quê"]), hide_index=True, width="stretch",
                 column_config={"Por quê": st.column_config.TextColumn(width="large")})
    st.markdown("**Saúde financeira do emissor**")
    if t.t.grupo == "tesouro":
        st.caption("Risco soberano: o emissor é o Tesouro Nacional.")
    elif t.emissor_ticker and dados is not None:
        d = _emissor(t.emissor_ticker)
        if d.get("erro") or d.get("roe") is None and d.get("div_pl") is None:
            st.caption(f"Não consegui os dados de {t.emissor_ticker} agora.")
        else:
            _cartoes([("ROE", _p(d.get("roe"), 1), "info"), ("Margem líquida", _p(d.get("margem_liq"), 1), "info"),
                      ("Dívida/Patrimônio", _p(d.get("div_pl"), 0), "info"),
                      ("Dívida líquida", _r(d.get("divida_liq")) if d.get("divida_liq") is not None else "n/d", "info")])
            st.caption(f"{d.get('nome') or t.emissor_ticker}: dados da empresa listada (mesma fonte das páginas de ações). "
                       "Não substitui a análise do documento da oferta nem um rating.")
    else:
        st.caption("Sem dado confiável e gratuito no app para este emissor. Bancos: o Banco Central publica dados por "
                   "instituição (IF.data), ainda não integrados. Empresas listadas: informe o código na bolsa no cadastro do título.")


@st.cache_data(ttl=3600, show_spinner=False)
def _emissor(tk: str) -> dict:
    try:
        d = dados.buscar_yahoo(tk)
        return {k: d.get(k) for k in ("nome", "roe", "margem_liq", "div_pl", "divida_liq", "erro")}
    except Exception as e:
        return {"erro": e.__class__.__name__}


def _aba_liquidez(a: dict):
    t = a["t"]
    hoje = a["hoje"]
    d = a["ind"]["liquidez_dias"]
    _cartoes([("Dinheiro disponível em", "D+1" if d <= 1 else f"{d} dias", "good" if d <= 1 else "fair" if d <= 365 else "bad"),
              ("Carência até", _dt(t.carencia) if t.carencia else "sem carência", "info"),
              ("Vencimento", _dt(t.vencimento), "info", f"{rf.dc(hoje, t.vencimento)} dias"),
              ("Mercado secundário", "Tesouro recompra" if t.t.grupo == "tesouro" else
               ("não depende" if t.liquidez == "diaria" else "incerto"), "good" if t.t.grupo == "tesouro" or t.liquidez == "diaria" else "fair")])
    st.markdown(t.t.liquidez_tipica)
    if t.t.grupo != "tesouro" and t.liquidez == "diaria":
        st.caption("Liquidez diária de título bancário costuma pagar a CURVA (sem marcação a mercado). Confira no contrato.")
    if t.t.grupo == "tesouro" or t.t.grupo == "credito_privado":
        st.caption("Vender antes do vencimento é pelo preço do dia (veja a aba Marcação a mercado), que pode estar abaixo do aplicado.")


def _aba_mam(a: dict, chave: str):
    t, mam, tm = a["t"], a["mam"], a["tm"]
    if t.vencimento <= a["hoje"]:
        st.info("Título vencido: não há marcação a mercado.")
        return
    if not mam.get("ok"):
        st.info("Marcação a mercado indisponível: " + (tm.get("motivo") or mam.get("motivo") or "sem taxa de referência") + ".")
        return
    dif = mam["preco"] / mam["curva"] - 1 if mam.get("curva") else None
    _cartoes([("Preço " + ("oficial (Tesouro)" if mam.get("oficial") else "estimado"), _r(mam["preco"]), "info",
               _dt(a["oficial"]["data"]) if mam.get("oficial") else "não é preço executável"),
              ("Valor na curva", _r(mam.get("curva")), "info", "pela taxa contratada"),
              ("Diferença", _p(dif, 1, True), "na" if dif is None else "good" if dif >= 0 else "bad", "preço − curva"),
              ("Duration modificada", _n(mam.get("mod")) if mam.get("tipo_risco") == "juros" else "≈ 0", "info",
               "sensibilidade a juros" if mam.get("tipo_risco") == "juros" else f"prazo do prêmio: {_n(mam.get('duration_spread'))} anos")])
    st.caption("Taxa de referência: " + _p(tm.get("taxa")) + (" a.a." if t.indexador != "cdi_pct" else " do CDI") + " · "
               + (tm.get("origem") or ""))
    st.markdown("**Se as taxas mudarem**")
    sens = mam.get("sens") or {}
    st.dataframe(pd.DataFrame([(f"{_p(k, 1, True).replace('%', ' p.p.')}", _p(v, 2, True), _r(mam["preco"] * (1 + v))) for k, v in sorted(sens.items())],
                              columns=["Variação da taxa" if mam.get("tipo_risco") == "juros" else "Variação do prêmio do emissor",
                                       "Preço muda", "Preço estimado"]), hide_index=True, width="stretch")
    st.markdown("**Simular venda antecipada**")
    base_tx = float(tm.get("taxa") or t.taxa) * 100
    nova = st.number_input("Taxa de mercado na venda (% a.a.)" if t.indexador != "cdi_pct" else "Percentual do CDI na venda (%)",
                           value=round(base_tx, 2), step=0.1, key=f"rf_mam_tx_{chave}")
    p2 = rf.preco_pela_taxa(t, nova / 100, a.get("_m") or {}, a["cenario"], a["hoje"])
    if p2.get("ok"):
        preco = p2["preco"] * (mam["preco"] / rf.preco_pela_taxa(t, tm["taxa"], a.get("_m") or {}, a["cenario"], a["hoje"])["preco"]
                               if mam.get("oficial") else 1.0)
        dias = rf.dc(t.aplicacao, a["hoje"])
        anos = rf.du(t.aplicacao, a["hoje"]) / 252
        x = rf.tributar(t.valor, preco, dias, t.tipo, rf.custodia_tesouro(t.tipo, (t.valor + preco) / 2, anos, ate_vencimento=False))
        v = a["venc"]
        _cartoes([("Venda hoje (bruto)", _r(preco), "info"), ("Venda hoje (líquido)", _r(x["liquido"]), "good" if x["liquido"] >= t.valor else "bad"),
                  ("Resultado da venda", _p(x["liquido"] / t.valor - 1, 1, True), "good" if x["liquido"] >= t.valor else "bad"),
                  ("Se levar ao vencimento (líquido)", _r(v.get("liquido_total")), "info", "cenário")])
    st.caption("Preço estimado: depende da taxa de referência e não é um preço garantido de venda. "
               + ("Pós-fixados quase não variam com os juros; variam com o prêmio de risco do emissor." if mam.get("tipo_risco") == "spread" else ""))


def _aba_simulador(a: dict, cen_todos: dict, chave: str):
    t = a["t"]
    c1, c2, c3 = st.columns(3)
    inicial = c1.number_input("Aplicação inicial (R$)", min_value=0.0, value=float(t.valor), step=500.0, key=f"rf_sim_ini_{chave}")
    aporte = c2.number_input("Aporte mensal (R$)", min_value=0.0, value=0.0, step=100.0, key=f"rf_sim_ap_{chave}")
    meses_venc = max(int(round(rf.dc(a["hoje"], t.vencimento) / 30.4375)), 1)
    meses = int(c3.number_input("Prazo (meses)", min_value=1, max_value=600, value=min(meses_venc, 600), step=1, key=f"rf_sim_m_{chave}"))
    c4, c5, c6 = st.columns(3)
    reinv = c4.checkbox("Reinvestir os juros", value=True, key=f"rf_sim_re_{chave}",
                        help="Desmarcado: os juros de cada mês são sacados (com IR) e não rendem mais.")
    antec = c5.checkbox("Resgatar antes", value=False, key=f"rf_sim_ant_{chave}")
    resg = int(c6.number_input("Mês do resgate", min_value=1, max_value=max(meses - 1, 1), value=max(min(12, meses - 1), 1), step=1,
                               key=f"rf_sim_rm_{chave}", disabled=not antec))
    choque = 0.0
    if antec and t.indexador in ("pre", "ipca"):
        choque = st.slider("Mudança das taxas até o resgate (p.p.)", -3.0, 3.0, 0.0, 0.25, key=f"rf_sim_ch_{chave}") / 100
    nomes = {"hoje": "Juros e inflação de hoje", "focus": "Focus (mercado)", "custom": "Personalizado"}
    ops = [k for k in ("hoje", "focus") if k in cen_todos] + ["custom"]
    esc = st.radio("Cenário", ops, format_func=nomes.get, horizontal=True, key=f"rf_sim_cen_{chave}")
    if esc == "custom":
        k1, k2 = st.columns(2)
        cdi = k1.number_input("CDI (% a.a.)", value=round(cen_todos["hoje"].cdi_de(a["hoje"].year) * 100, 2), step=0.25, key=f"rf_sim_cdi_{chave}")
        ipca = k2.number_input("IPCA (% a.a.)", value=round(cen_todos["hoje"].ipca_de(a["hoje"].year) * 100, 2), step=0.25, key=f"rf_sim_ipca_{chave}")
        cen = rf.cenario_fixo(cdi / 100, ipca / 100, "Personalizado")
    else:
        cen = cen_todos[esc]
    alvo = _escolher_comparado(a, chave)
    r = rf.simular(inicial, aporte, meses, t.indexador, t.taxa, cen, t.tipo, a["hoje"], resg if antec else None, choque, reinv)
    nome = t.nome or t.t.nome
    df = pd.DataFrame(r["linhas"]).set_index("mes")
    series = {"Investido": df["investido"], f"{nome} (líquido)": df["liquido"], f"{nome} (real)": df["real"]}
    if alvo is None:
        _cartoes([("Investido", _r(r["investido"]), "info"), ("Bruto", _r(r["bruto"]), "info"),
                  ("Líquido", _r(r["liquido"]), "good"), ("Real (poder de compra de hoje)", _r(r["real"]), "fair")])
    else:
        tp2, ix2, tx2, nome2 = alvo
        b = rf.simular(inicial, aporte, meses, ix2, tx2, cen, tp2, a["hoje"], resg if antec else None, choque, reinv)
        series[f"{nome2} (líquido)"] = pd.DataFrame(b["linhas"]).set_index("mes")["liquido"]
        dif = r["liquido"] - b["liquido"]
        st.dataframe(pd.DataFrame([
            ("Investido", _r(r["investido"]), _r(b["investido"])), ("Bruto", _r(r["bruto"]), _r(b["bruto"])),
            ("Imposto", _r(r["imposto"]), _r(b["imposto"])), ("Líquido", _r(r["liquido"]), _r(b["liquido"])),
            ("Real (poder de compra de hoje)", _r(r["real"]), _r(b["real"]))], columns=["", nome, nome2]),
            hide_index=True, width="stretch")
        _cartoes([("Diferença no líquido", _r(abs(dif)), "good" if dif >= 0 else "bad",
                   f"a favor de {nome if dif >= 0 else nome2}"),
                  ("Diferença no real", _r(abs(r["real"] - b["real"])), "info", "descontada a inflação do cenário")], por_linha=2)
        if (t.t.isento_ir_pf != rf.tipo(tp2).isento_ir_pf):
            st.caption("Um é isento de IR e o outro não: a comparação justa é no LÍQUIDO (já está descontado).")
        if ix2 != t.indexador:
            st.caption(f"Indexadores diferentes: o resultado depende do cenário '{cen.nome}'. Mude o cenário acima para ver "
                       "quando um passa o outro.")
    if r["antecipado"] and r["ajuste_mam"]:
        st.caption(f"Resgate antecipado no mês {r['meses']}: marcação a mercado de {_p(r['ajuste_mam'], 1, True)} pela mudança de taxas.")
    st.plotly_chart(evolucao.grafico_linhas(series, "Evolução simulada (R$)"), width="stretch", key=f"rf_sim_g_{chave}")
    st.caption("Simulação: aportes no fim de cada mês, IR por aporte (com a idade de cada parcela), IOF se < 30 dias. "
               "Não considera custódia nem feriados móveis no cálculo mês a mês. Premissas, não promessa.")


def _escolher_comparado(a: dict, chave: str):
    """Outro título para o simulador: CDB de 100% do CDI, um título da carteira, um do Tesouro de hoje ou personalizado.
    Devolve (tipo, indexador, taxa, nome) ou None."""
    t = a["t"]
    m = a.get("_m") or {}
    ops = {"nada": "Não comparar", "cdb100": "CDB de 100% do CDI"}
    cart = {f"RF-{x.id.upper()}": x for x in _titulos_carteira() if x.id != t.id}
    ops.update({k: x.rotulo() for k, x in cart.items()})
    tdh = titulos_tesouro_hoje(m.get("td"))
    for r_ in tdh.itertuples() if not tdh.empty else []:
        tx = r_.taxa_compra if pd.notna(r_.taxa_compra) else r_.taxa_venda
        if pd.notna(tx) and r_.tipo not in ("tesouro_renda", "tesouro_educa"):
            ops[r_.codigo] = f"{r_.titulo} {r_.venc.year} ({_n(tx, 2)}% hoje) · {r_.codigo}"
    ops["custom"] = "Outro (informar tipo e taxa)"
    k = st.selectbox("Comparar com", list(ops), format_func=ops.get, index=1, key=f"rf_sim_alvo_{chave}")
    if k == "nada":
        return None
    if k == "cdb100":
        return ("cdb", "cdi_pct", 1.0, "CDB 100% do CDI")
    if k in cart:
        x = cart[k]
        return (x.tipo, x.indexador, x.taxa, x.nome or f"{x.t.nome} {x.emissor}".strip())
    if k == "custom":
        c1, c2, c3 = st.columns(3)
        tp = c1.selectbox("Tipo", [x for x in rf.TIPOS if rf.TIPOS[x].grupo != "tesouro"], key=f"rf_sim_ct_{chave}",
                          format_func=lambda x: rf.TIPOS[x].nome)
        ix = c2.selectbox("Indexador", list(rf.TIPOS[tp].indexadores), key=f"rf_sim_ci_{chave}", format_func=rf.INDEXADORES.get)
        kx = f"rf_sim_cx_{chave}_{ix}"                     # um campo por indexador: 100% do CDI não vira 100% a.a.
        tx = c3.number_input("% do CDI" if ix == "cdi_pct" else "Taxa (% a.a.)", key=kx,
                             **_padrao(kx, 100.0 if ix == "cdi_pct" else 6.0), step=0.5)
        return (tp, ix, tx / 100, f"{rf.TIPOS[tp].nome} {rf.texto_taxa(rf.Titulo(tp, ix, tx / 100, a['hoje'], a['hoje']))}")
    linha = tdh[tdh["codigo"] == k].iloc[0]
    tx = linha["taxa_compra"] if pd.notna(linha["taxa_compra"]) else linha["taxa_venda"]
    return (linha["tipo"], rf.TIPOS[linha["tipo"]].indexadores[0], float(tx) / 100, f"{linha['titulo']} {linha['venc'].year}")


def _aba_comparacao(a: dict, m: dict, cen: rf.Cenario, chave: str, atalho_comparar=None):
    t = a["t"]
    tdh = titulos_tesouro_hoje(m.get("td"))
    cart = _titulos_carteira()
    ops = {f"RF-{x.id.upper()}": x.rotulo() for x in cart if x.id != t.id}
    if not tdh.empty:
        ops.update({r.codigo: f"{r.titulo} {r.venc.year} (Tesouro hoje: {_n(r.taxa_compra if pd.notna(r.taxa_compra) else r.taxa_venda, 2)}%) · {r.codigo}"
                    for r in tdh.itertuples()})
    escolha = st.multiselect("Comparar com", list(ops), format_func=lambda k: ops.get(k, k), key=f"rf_cmp_{chave}", max_selections=5,
                             placeholder="Títulos da sua carteira ou do Tesouro Direto")
    if not escolha:
        st.info("Escolha pelo menos um título para comparar. Indexadores diferentes são comparados pelo retorno esperado "
                "líquido e real, sob o mesmo cenário (premissa explícita).")
    else:
        a["_m"] = m
        base = ativo_de_analise(a, codigo_de(t))
        outros = [ativo_rf(k) for k in escolha]
        c = comparador.comparar([base] + outros)
        st.dataframe(pd.DataFrame(comparador.tabela(c)), hide_index=True, width="stretch")
        idxs = {x.subgrupo for x in [base] + outros if not x.erro}
        if len(idxs) > 1:
            st.caption(f"Indexadores diferentes: retornos esperados sob o cenário '{cen.nome}'. Se o CDI ou o IPCA vierem "
                       "diferentes, a ordem pode mudar (veja os cenários na aba Rentabilidade).")
        for al in c.alertas:
            st.caption("• " + al)
    if atalho_comparar:
        st.markdown("**Comparar com ações, ETFs, FIIs, fundos ou cripto**")
        st.caption("Na página Comparar, títulos de renda fixa entram só pelos critérios comuns. O retorno de 12 meses de um "
                   "título é o REALIZADO (preço do Tesouro ou curva), não a taxa contratada: são coisas diferentes.")
        atalho_comparar([codigo_de(t)], f"rf_{chave}", "Levar este título para Comparar ativos")


def _aba_historico(a: dict, m: dict, chave: str):
    t = a["t"]
    st.markdown("**Selic, CDI e IPCA (Banco Central)**")
    s_selic, s_cdi, s_ipca = _sgs_hist(432, 9), _sgs_hist(4389, 9), _sgs_hist(13522, 9)   # séries diárias: até 10 anos por consulta
    series = {k: v for k, v in (("Selic meta (% a.a.)", s_selic), ("CDI (% a.a.)", s_cdi), ("IPCA 12 meses (%)", s_ipca)) if len(v)}
    if series:
        st.plotly_chart(evolucao.grafico_linhas(series, "Juros e inflação (9 anos)", "%"), width="stretch", key=f"rf_h_ind_{chave}")
    else:
        st.caption("Séries do Banco Central indisponíveis agora.")
    td = m.get("td")
    if td is not None and not td.empty and t.indexador in ("pre", "ipca", "selic"):
        st.markdown("**Evolução das taxas do Tesouro**")
        if t.td_titulo:
            s = td[(td["titulo"] == t.td_titulo) & (td["venc"] == pd.Timestamp(t.td_venc or t.vencimento))].set_index("data").sort_index()
            nome = f"{t.td_titulo} {(t.td_venc or t.vencimento).year}"
        else:
            tipos = rf.CURVA_PRE[:1] if t.indexador == "pre" else rf.CURVA_REAL[:1] if t.indexador == "ipca" else ("tesouro_selic",)
            x = td[td["titulo"].map(lambda n: rf.tipo_do_tesouro(n) in tipos)]
            if x.empty:
                s, nome = pd.DataFrame(), ""
            else:
                alvo = pd.Timestamp(t.vencimento)
                vs = sorted(x["venc"].unique(), key=lambda v: abs((pd.Timestamp(v) - alvo).days))
                s = x[x["venc"] == vs[0]].set_index("data").sort_index()
                nome = f"{s['titulo'].iloc[0]} {pd.Timestamp(vs[0]).year} (vencimento mais próximo do seu título)"
        if len(s):
            st.plotly_chart(evolucao.grafico_linhas({f"Taxa de compra — {nome}": s["taxa_compra"].dropna()}, "Taxa (% a.a.)", "%"),
                            width="stretch", key=f"rf_h_tx_{chave}")
            if t.td_titulo:
                st.plotly_chart(evolucao.grafico_linhas({"PU (preço unitário)": s["pu"]}, "Histórico de preço (R$)"),
                                width="stretch", key=f"rf_h_pu_{chave}")
    st.markdown("**Rentabilidade do título desde a aplicação (na curva)**")
    hoje = a["hoje"]
    if t.aplicacao < hoje:
        datas = pd.date_range(t.aplicacao, min(hoje, t.vencimento), freq="MS")
        datas = [d.date() for d in datas if d.date() > t.aplicacao] + [min(hoje, t.vencimento)]
        tit = pd.Series({pd.Timestamp(d): rf.fator_realizado(t, d, m, a["cenario"])["fator"] * 100 for d in datas})
        cdi = pd.Series({pd.Timestamp(d): (rf.fator_cdi_realizado("cdi_pct", 1.0, t.aplicacao, d, m.get("cdi_idx"))[0] or float("nan")) * 100 for d in datas})
        ipca = pd.Series({pd.Timestamp(d): rf.fator_ipca_realizado(t.aplicacao, d, m.get("ipca"))[0] * 100 for d in datas})
        st.plotly_chart(evolucao.grafico_linhas({"Título": tit, "CDI": cdi.dropna(), "IPCA": ipca}, "Base 100 na aplicação"),
                        width="stretch", key=f"rf_h_tit_{chave}")
    else:
        st.caption("Aplicação de hoje: ainda não há histórico do título.")
    st.markdown("**Prêmio de crédito (spread)**")
    tm = a.get("tm") or {}
    if tm.get("premio") is not None:
        st.caption(f"Na aplicação, este título pagava {_p(tm['premio'], 2, True)} a.a. acima do Tesouro de prazo parecido "
                   f"({_p(tm['tesouro_aplicacao'])} a.a.). Histórico de spreads de crédito por emissor: sem fonte gratuita no app.")
    else:
        st.caption("Histórico de spreads de crédito: sem fonte gratuita no app (ANBIMA e B3 publicam com restrições de uso).")


def _aba_inteligente(a: dict):
    for sec, itens in a["relatorio"].items():
        st.markdown(f"**{sec}**")
        for x in itens or ["Nada a destacar com os dados disponíveis."]:
            st.markdown(f"- {x}")
    n = a["nota"]
    st.markdown("**Como a nota educacional foi feita**")
    st.dataframe(pd.DataFrame([(k, "sem dado" if v is None else f"{v:.0f}", f"{n['pesos'][k]}%") for k, v in n["pilares"].items()],
                              columns=["Pilar", "Nota (0-100)", "Peso"]), hide_index=True, width="stretch")
    st.caption("A nota compara títulos entre si pelos critérios acima; não diz se o título é bom para você.")


def mostrar(a: dict, m: dict, cen_todos: dict, chave: str, atalho_comparar=None):
    if not a.get("ok"):
        for e in a.get("erros", []):
            st.error(e)
        return
    a["_m"] = m
    st.markdown(f"### {a['t'].nome or a['t'].t.nome}")
    abas = profundidade_app.abas("renda_fixa", ABAS)
    if abas[0] is not None:
        with abas[0]:
            _aba_visao(a)
    if abas[1] is not None:
        with abas[1]:
            _aba_caracteristicas(a)
    if abas[2] is not None:
        with abas[2]:
            _aba_rentabilidade(a, m, cen_todos)
    if abas[3] is not None:
        with abas[3]:
            _aba_tributacao(a)
    if abas[4] is not None:
        with abas[4]:
            _aba_riscos(a)
    if abas[5] is not None:
        with abas[5]:
            _aba_liquidez(a)
    if abas[6] is not None:
        with abas[6]:
            _aba_mam(a, chave)
    if abas[7] is not None:
        with abas[7]:
            _aba_simulador(a, cen_todos, chave)
    if abas[8] is not None:
        with abas[8]:
            _aba_comparacao(a, m, a["cenario"], chave, atalho_comparar)
    if abas[9] is not None:
        with abas[9]:
            _aba_historico(a, m, chave)
    if abas[10] is not None:
        with abas[10]:
            _aba_inteligente(a)
    for av in m.get("avisos", []):
        st.caption("⚠️ " + av)
    st.caption(NOTA_LEGAL)


# =============================================================================== página
def pagina_renda_fixa(atalho_comparar=None):
    st.markdown(tema.cabecalho("🏦", "Análise de títulos",
                               "Tesouro Direto, CDB, LCI, LCA, LC, LF, debêntures, CRI e CRA: rentabilidade, impostos, riscos, "
                               "marcação a mercado e simulação."), unsafe_allow_html=True)
    with st.spinner("Buscando Tesouro Direto e Banco Central..."):
        m = mercado()
    cen_todos = cenarios(m)
    modos = ["Tesouro Direto", "Novo título", "Meus títulos"]
    modo = st.segmented_control("Origem", modos, default=modos[0], key="rf_modo", label_visibility="collapsed") or modos[0]
    nomes_cen = {"hoje": "Juros e inflação de hoje", "focus": "Focus (expectativas do mercado)"}
    esc = st.radio("Cenário para projeções", [k for k in ("hoje", "focus") if k in cen_todos], format_func=nomes_cen.get,
                   horizontal=True, key="rf_cen")
    cen = cen_todos[esc]
    st.caption(f"{cen.nome}: " + (cen.origem or "") + ". O cenário só afeta o que é projetado (CDI/IPCA futuros).")
    t = None
    if modo == "Tesouro Direto":
        tdh = titulos_tesouro_hoje(m.get("td"))
        if tdh.empty:
            st.warning("Não consegui os títulos do Tesouro Direto agora. Use 'Novo título' para analisar um título informado por você.")
            return
        cod = st.selectbox("Título", list(tdh["codigo"]), key="rf_td_sel",
                           format_func=lambda k: (lambda r: f"{r['titulo']} {r['venc'].year} · compra {_n(r['taxa_compra'], 2) if pd.notna(r['taxa_compra']) else 'n/d'}% · venda {_n(r['taxa_venda'], 2) if pd.notna(r.get('taxa_venda')) else 'n/d'}%")(tdh[tdh["codigo"] == k].iloc[0]))
        linha = tdh[tdh["codigo"] == cod].iloc[0]
        valor = st.number_input("Valor para simular a compra (R$)", min_value=1.0, value=1000.0, step=100.0, key="rf_td_valor")
        st.caption(f"Taxas e preços oficiais do Tesouro Transparente em {_dt(linha['data'])}. "
                   + ("Sem taxa de compra hoje (título fora de venda): usei a taxa de venda." if pd.isna(linha["taxa_compra"]) else ""))
        t = titulo_do_tesouro(linha, valor)
        if st.button("Salvar na minha carteira de renda fixa", key="rf_td_salvar"):
            salvar_na_carteira(replace(t, id=_novo_id()))           # cada compra salva é uma posição própria
            st.success("Salvo em 'Meus títulos'.")
    elif modo == "Novo título":
        t = _form_titulo("rf_novo")
        if st.button("Salvar na minha carteira de renda fixa", key="rf_novo_salvar"):
            if rf.validar(t):
                st.error("Corrija antes de salvar: " + "; ".join(rf.validar(t)))
            else:
                salvar_na_carteira(t)
                st.session_state.pop("rf_novo_id", None)               # o próximo título novo ganha outro código
                st.success("Salvo em 'Meus títulos'.")
    else:
        cart = _titulos_carteira()
        if not cart:
            st.info("Nenhum título salvo. Analise um título do Tesouro ou informe um novo e toque em 'Salvar'.")
            return
        sel = st.selectbox("Título", [x.id for x in cart], key="rf_cart_sel",
                           format_func=lambda i: next(x.rotulo() for x in cart if x.id == i))
        base = next(x for x in cart if x.id == sel)
        if base.td_titulo:
            t = base
            st.caption("Título do Tesouro: o preço de mercado é o oficial.")
        else:
            with st.expander("Editar este título"):
                t = _form_titulo("rf_ed", base)
                if st.button("Salvar alterações", key="rf_ed_salvar"):
                    if rf.validar(t):
                        st.error("; ".join(rf.validar(t)))
                    else:
                        salvar_na_carteira(t)
                        st.success("Alterações salvas.")
            t = t if t is not None else base
        if st.button("Remover da carteira", key="rf_cart_rm"):
            remover_da_carteira(sel)
            st.rerun()
    if t is None:
        return
    delta = 0.0
    if t.indexador in ("cdi_pct", "cdi_mais", "selic") and t.t.grupo != "tesouro":
        delta = st.slider("Premissa para marcação a mercado: mudança do prêmio do emissor desde a compra (p.p.)",
                          -2.0, 2.0, 0.0, 0.1, key="rf_spread") / 100
    a = analisar(t, m, cen, spread_delta=delta, emissor_pct=_peso_emissor(t, m, cen))
    mostrar(a, m, cen_todos, f"pag_{t.id}", atalho_comparar)


def _peso_emissor(t: rf.Titulo, m: dict, cen: rf.Cenario) -> float | None:
    cart = _titulos_carteira()
    if not cart or not any(x.id == t.id for x in cart):
        return None
    vals = {}
    for x in cart:
        c = rf.valor_na_curva(x, m, cen)
        vals[x.id] = c.get("valor_atual") if c.get("ok") else None
    tot = sum(v for v in vals.values() if v)
    if not tot:
        return None
    mesmo = sum(vals[x.id] or 0 for x in cart if rf.emissor_chave(x) == rf.emissor_chave(t))
    return mesmo / tot * 100


# =============================================================================== carteira (Passo 11, integração)
def painel_carteira_rf():
    """Bloco da página Carteira: exposição por emissor/indexador/tipo, FGC, vencimentos, liquidez e fluxo de recebimentos.
    Só lê o que o usuário salvou; nada é comprado, vendido ou alterado."""
    cart = _titulos_carteira()
    st.caption("Mostra só os títulos salvos em Renda fixa → Análise de títulos. Nada é comprado, vendido ou alterado por aqui.")
    if not cart:
        st.info("Nenhum título de renda fixa salvo. Use a página 'Análise de títulos' para cadastrar (Tesouro, CDB, LCI, debêntures...).")
        return
    m = mercado()
    cen = cenarios(m)["hoje"]
    hoje = date.today()
    vals, fls, linhas = {}, {}, []
    for t in cart:
        c = rf.valor_na_curva(t, m, cen, hoje) if t.aplicacao < hoje else {"ok": True, "valor_atual": t.valor, "acumulado": 0.0}
        vals[t.id] = c.get("valor_atual") if c.get("ok") else None
        fls[t.id] = rf.fluxos(t, cen, m, hoje)
        rc = rf.risco_credito(t)
        linhas.append({"Título": t.rotulo(), "Código": f"RF-{t.id.upper()}", "Aplicado": _r(t.valor),
                       "Valor hoje (curva)": _r(vals[t.id]), "Rendimento": _p(c.get("acumulado"), 1, True) if c.get("ok") else "n/d",
                       "Crédito": f"{rc['nivel']}/5", "FGC": "sim" if t.t.fgc else "não"})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    an = rf.analisar_carteira(cart, vals, fls, hoje)
    if an.get("total", 0) <= 0:
        for al in an["alertas"]:
            st.info(al)
        return
    _cartoes([("Renda fixa (curva)", _r(an["total"]), "info", f"{an['n']} título(s)"),
              ("Prazo até o vencimento", f"{_n(an['prazo_medio_anos'])} anos", "info", "média ponderada pelo valor"),
              ("Liquidez em até 1 dia", _p(an["liquidez"]["Em até 1 dia"] / an["total"], 0), "info"),
              ("Maior emissor privado", _p(max([v for k, v in an["por_emissor"].items() if k != "Tesouro Nacional"] or [0]) / an["total"], 0),
               "info", "do total de renda fixa")])
    for al in an["alertas"]:
        st.warning(al)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Por emissor**")
        st.dataframe(pd.DataFrame([(k, _r(v), _p(v / an["total"], 0)) for k, v in an["por_emissor"].items()],
                                  columns=["Emissor", "Valor", "%"]), hide_index=True, width="stretch")
        st.markdown("**Por indexador**")
        st.dataframe(pd.DataFrame([(k, _r(v), _p(v / an["total"], 0)) for k, v in an["por_indexador"].items()],
                                  columns=["Indexador", "Valor", "%"]), hide_index=True, width="stretch")
    with c2:
        st.markdown("**Liquidez (quando o dinheiro fica disponível)**")
        st.dataframe(pd.DataFrame([(k, _r(v), _p(v / an["total"], 0)) for k, v in an["liquidez"].items()],
                                  columns=["Prazo", "Valor", "%"]), hide_index=True, width="stretch")
        st.markdown("**Vencimentos por ano**")
        st.dataframe(pd.DataFrame([(k, _r(v)) for k, v in an["vencimentos_por_ano"].items()], columns=["Ano", "Valor"]),
                     hide_index=True, width="stretch")
    if an.get("fgc"):
        st.markdown("**Cobertura do FGC por emissor** (limite de R$ 250 mil por CPF e instituição/conglomerado)")
        st.dataframe(pd.DataFrame([(x["emissor"], _r(x["valor"]), _r(x["coberto_pelo_fgc"]), _r(x["excedente"])) for x in an["fgc"]],
                                  columns=["Emissor", "Valor com FGC", "Coberto", "Acima do limite"]), hide_index=True, width="stretch")
    if an.get("fluxo_24m"):
        st.markdown("**Recebimentos previstos nos próximos 24 meses** (juros e vencimentos, cenário de hoje, valores brutos)")
        fl = pd.Series({pd.Timestamp(k): v for k, v in an["fluxo_24m"].items()})
        st.plotly_chart(evolucao.grafico_barras(pd.DataFrame({"Recebimentos (R$)": fl}), ["Recebimentos (R$)"], "Fluxo de recebimentos"),
                        width="stretch", key="rf_cart_fluxo")
    if an.get("proximos"):
        st.markdown("**Vencem em até 12 meses**")
        st.dataframe(pd.DataFrame([(_dt(d), r, _r(v)) for d, r, v in an["proximos"]], columns=["Vencimento", "Título", "Valor (curva)"]),
                     hide_index=True, width="stretch")
    st.caption("Valores pela curva (taxa contratada), não a preço de mercado. FGC: o app agrupa pelo nome do emissor digitado; "
               "o limite real é por conglomerado. " + NOTA_LEGAL)
