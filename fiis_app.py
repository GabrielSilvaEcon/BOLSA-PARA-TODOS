"""
Página de FIIs (passo 8): coleta, preparação dos dados e telas. A lógica de análise está em fiis.py e fiis_cvm.py (puros).

Fontes: lista de FIIs e fotografia atual do Fundamentus; preços e proventos do Yahoo Finance; informe mensal oficial da
CVM (histórico de patrimônio, valor patrimonial, cotistas e passivo). O que nenhuma dessas fontes entrega aparece como
"indisponível", com a explicação. Nada é estimado.
"""
from __future__ import annotations

import re
from datetime import date

import pandas as pd
import streamlit as st

import comparador
import crescimento as cr
import evolucao
import fiis
import fiis_cvm
import tema

try:
    import requests
except Exception:                         # pragma: no cover
    requests = None

URL_LISTA = "https://www.fundamentus.com.br/fii_resultado.php"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
      "Referer": "https://www.fundamentus.com.br/"}
NIVEL = {"alto": ("🔴", "Alto"), "medio": ("🟡", "Médio"), "baixo": ("🟢", "Baixo"), "indisponivel": ("⚪", "Sem dado")}


# =============================================================================== formatação
def _f(v, casas: int = 2, suf: str = "", pre: str = "") -> str:
    if not fiis._ok(v):
        return "n/d"
    t = f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{pre}{t}{suf}"


def _brl_g(v) -> str:
    if not fiis._ok(v):
        return "n/d"
    for lim, suf in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return _f(v / lim, 2, suf, "R$ ")
    return _f(v, 2, "", "R$ ")


def _data_br(iso) -> str:
    try:
        return pd.Timestamp(iso).strftime("%d/%m/%Y")
    except Exception:
        return "—"


# =============================================================================== coleta (rede, com cache)
@st.cache_data(ttl=6 * 3600, show_spinner=False)
def lista_fiis() -> dict:
    """Todos os FIIs do Fundamentus, já classificados. Falha = df vazio + aviso (nunca dado inventado)."""
    out = {"df": pd.DataFrame(), "data": date.today().isoformat(), "aviso": None}
    if requests is None:
        out["aviso"] = "Biblioteca de rede indisponível."
        return out
    try:
        r = requests.get(URL_LISTA, headers=UA, timeout=25)
        r.raise_for_status()
        out["df"] = fiis.classificar_lista(fiis.ler_lista_fundamentus(r.text))
    except fiis.LayoutInesperado as e:
        out["aviso"] = f"O layout da lista do Fundamentus mudou ({e})."
    except Exception as e:
        out["aviso"] = f"Lista de FIIs indisponível agora ({e.__class__.__name__})."
    return out


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _zip_cvm(ano: int):
    try:
        c = fiis_cvm.baixar(fiis_cvm.URL_INF_MENSAL.format(ano=ano))
        return fiis_cvm.ler_zip(c) if c is not None else None
    except fiis_cvm.LayoutInesperado:
        raise
    except Exception:
        return None


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def historico_cvm(cnpj: str, hoje_ano: int, n_anos: int = 6) -> dict:
    out = {"df": pd.DataFrame(), "avisos": [], "erro": None, "anos": []}
    tabs = {}
    for ano in range(hoje_ano, hoje_ano - n_anos, -1):
        try:
            t = _zip_cvm(ano)
        except fiis_cvm.LayoutInesperado as e:
            out["erro"] = str(e)
            return out
        if t:
            tabs[ano] = t
            out["anos"].append(ano)
    if not tabs:
        out["avisos"].append("A CVM não devolveu os arquivos de informe mensal agora.")
        return out
    try:
        out["df"] = fiis_cvm.padronizar(fiis_cvm.juntar_anos(tabs), cnpj)
    except fiis_cvm.LayoutInesperado as e:
        out["erro"] = str(e)
        return out
    if out["df"].empty:
        out["avisos"].append("Esse CNPJ não aparece nos informes mensais de FIIs da CVM.")
    out["avisos"] += fiis_cvm.validar(out["df"])
    return out


@st.cache_data(ttl=24 * 3600, show_spinner=False)
def _geral_cvm(hoje_ano: int):
    for ano in (hoje_ano, hoje_ano - 1):
        try:
            t = _zip_cvm(ano)
        except Exception:
            t = None
        if t and "geral" in t:
            return t["geral"]
    return pd.DataFrame()


# =============================================================================== preparação (testável)
def preparar(tk: str, lista: pd.DataFrame, snap: dict | None, precos: dict | None, cvm_df: pd.DataFrame | None,
             hoje: str | None = None) -> dict:
    """Junta tudo o que a página mostra. Sem Streamlit: recebe os dados já coletados."""
    hoje = hoje or date.today().isoformat()
    precos = precos or {}
    row = lista.loc[tk].to_dict() if lista is not None and not lista.empty and tk in lista.index else {}
    snap = (snap or {}).get("dados", snap or {}) if isinstance(snap, dict) else {}
    seg = row.get("segmento") or snap.get("segmento")
    cls = fiis.classificar(seg)
    pm = comparador.metricas_preco(precos.get("ajustado", pd.Series(dtype=float)))
    dist = comparador.metricas_distribuicao(precos.get("div"), precos.get("preco", pd.Series(dtype=float)))
    ind, fontes = fiis.montar_indicadores(row, snap, pm, dist, cvm_df, hoje)
    if "liquidez" not in ind:                       # sem a lista do Fundamentus: média de 90 dias do Yahoo
        liq = comparador.liquidez_diaria(precos.get("preco"), precos.get("volume"))
        if fiis._ok(liq):
            ind["liquidez"] = float(liq)
            fontes["liquidez"] = ("Yahoo Finance (média de 90 dias)", None)
    div = fiis.analisar_dividendos(precos.get("div"), ind.get("cotacao"))
    if div.get("ok") and fiis._ok(div.get("dy_recorrente")):
        ind["dy_rec"] = div["dy_recorrente"]
        fontes["dy_rec"] = ("calculado (Yahoo Finance)", div.get("ultimo"))
    peers, desc = fiis.pares(lista, tk) if row else (pd.DataFrame(), "sem lista de FIIs")
    pinfo = {"descricao": desc, "dy_mediana": fiis.mediana_pares(peers, "dy"), "pvp_mediana": fiis.mediana_pares(peers, "pvp"),
             "vacancia_mediana": fiis.mediana_pares(peers, "vacancia")}
    riscos = fiis.avaliar_riscos(cls, ind, div, pinfo)
    datas = {f"{k}": f"{v[0]}" + (f" ({_data_br(v[1])})" if v[1] else "") for k, v in fontes.items() if k != "pvp_aviso"}
    rel = fiis.montar_relatorio(tk, cls, ind, div, riscos, pinfo, datas)
    return {"tk": tk, "row": row, "classe": cls, "ind": ind, "fontes": fontes, "div": div, "pares": peers, "pares_info": pinfo,
            "riscos": riscos, "relatorio": rel, "pm": pm, "dist": dist, "datas": datas, "tem_lista": bool(row)}


def inds_comparador(d: dict) -> dict:
    """Indicadores no formato do comparador (passo 6)."""
    I = comparador.Ind
    ind, fo, pm = d["ind"], d["fontes"], d["pm"]
    out = comparador.inds_de_preco(pm)

    def mk(k, origem="dado", periodo=None):
        v = ind.get(k)
        f = fo.get(k, (None, None))
        return I(v, origem, periodo, f[1] if isinstance(f[1], str) and re.match(r"\d{4}-\d{2}-\d{2}", f[1] or "") else None)
    out.update({"dy12m": mk("dy12m", "calculado", "12m"), "meses_pagos": mk("meses_pagos", "calculado", "12m"),
                "liq": mk("liquidez", "dado", "2 meses"), "pvp": mk("pvp"), "dy_rec": mk("dy_rec", "calculado", "12m"),
                "cotistas": mk("cotistas"), "qtd_imoveis": mk("qtd_imoveis")})
    tijolo = d["classe"].estrategia in ("tijolo", "hibrido")
    out["vacancia"] = mk("vacancia") if tijolo else I(None, aplica=False)
    return out


# =============================================================================== telas
def _linha_ind(nome, chave, d, fmt):
    v = d["ind"].get(chave)
    fonte, data = d["fontes"].get(chave, ("—", None))
    return {"Indicador": nome, "Valor": fmt(v) if v is not None else "indisponível", "Fonte": fonte if v is not None else "—",
            "Referência": (_data_br(data) if data else "—") if v is not None else "—"}


INDICADORES = [
    ("Cotação", "cotacao", lambda v: _f(v, 2, "", "R$ ")), ("P/VP", "pvp", lambda v: _f(v, 2)),
    ("Valor patrimonial por cota", "vp_cota", lambda v: _f(v, 2, "", "R$ ")),
    ("Dividend Yield (anual, fonte)", "dy", lambda v: _f(v, 1, "%")),
    ("Dividend Yield 12 meses (calculado)", "dy12m", lambda v: _f(v, 1, "%")),
    ("Dividend Yield sem pagamentos acima do normal", "dy_rec", lambda v: _f(v, 1, "%")),
    ("Rendimento do último mês informado", "dy_mes", lambda v: _f(v, 2, "%")),
    ("Valor de mercado", "valor_mercado", _brl_g), ("Patrimônio líquido", "patrimonio", _brl_g),
    ("Liquidez média diária", "liquidez", lambda v: _brl_g(v)), ("Número de cotistas", "cotistas", lambda v: _f(v, 0)),
    ("Número de cotas", "cotas", lambda v: _f(v, 0)), ("Número de imóveis", "qtd_imoveis", lambda v: _f(v, 0)),
    ("Vacância média", "vacancia", lambda v: _f(v, 1, "%")), ("Cap rate", "cap_rate", lambda v: _f(v, 1, "%")),
    ("Preço por m²", "preco_m2", lambda v: _f(v, 0, "", "R$ ")), ("Aluguel por m²", "aluguel_m2", lambda v: _f(v, 0, "", "R$ ")),
    ("FFO Yield", "ffo_yield", lambda v: _f(v, 1, "%")),
    ("Alavancagem (passivo ÷ patrimônio)", "alavancagem", lambda v: _f(v * 100, 0, "%")),
    ("Retorno 12 meses (com rendimentos)", "ret12m", lambda v: _f(v, 1, "%")),
    ("Volatilidade anual", "vol", lambda v: _f(v, 1, "%")), ("Maior queda em 12 meses", "dd_max", lambda v: _f(v, 1, "%")),
]
SEM_FONTE_IND = ["Vacância financeira", "Receita imobiliária", "Resultado distribuível", "Reservas acumuladas",
                 "Concentração de inquilinos", "Concentração geográfica"]


def _aba_visao(d):
    c, ind = d["classe"], d["ind"]
    st.markdown(f"**{c.rotulo}**" + ("" if c.confianca == "alta" else " · classificação de baixa confiança"))
    if not d["tem_lista"]:
        st.warning("Este código não está na lista de FIIs do Fundamentus agora: os indicadores de P/VP, vacância e liquidez "
                   "podem faltar. Confira o código.")
    a, b = st.columns(2)
    a.metric("Cotação", _f(ind.get("cotacao"), 2, "", "R$ "))
    b.metric("P/VP", _f(ind.get("pvp"), 2))
    a, b = st.columns(2)
    a.metric("Dividend Yield (anual)", _f(ind.get("dy"), 1, "%"))
    b.metric("Liquidez diária", _brl_g(ind.get("liquidez")))
    if c.estrategia in ("tijolo", "hibrido"):
        a, b = st.columns(2)
        a.metric("Vacância média", _f(ind.get("vacancia"), 1, "%"))
        b.metric("Imóveis", _f(ind.get("qtd_imoveis"), 0))
    for k, (txt, _) in d["fontes"].items():
        if k == "pvp_aviso":
            st.caption("⚠️ " + txt)
    altos = [r for r in d["riscos"] if r.nivel == "alto"]
    if altos:
        st.error("Pontos de atenção: " + "; ".join(r.nome for r in altos) + ". Veja a aba Riscos.")
    st.caption("Fontes: Fundamentus (indicadores de hoje), Yahoo Finance (preço e rendimentos) e CVM (informe mensal, quando o "
               "CNPJ é informado). " + comparador.AVISO_LEGAL)


def _aba_indicadores(d):
    linhas = [_linha_ind(n, k, d, f) for n, k, f in INDICADORES]
    df = pd.DataFrame(linhas)
    st.dataframe(df, hide_index=True, width="stretch")
    st.markdown("**Sem fonte integrada:** " + ", ".join(SEM_FONTE_IND) + ". Estão nos relatórios gerenciais dos fundos.")
    st.caption("Cada valor mostra de onde veio e a data de referência. Fundamentus traz o valor de hoje; a CVM traz o último "
               "informe mensal (sai com atraso).")


def _aba_dividendos(d, precos):
    div = d["div"]
    s = precos.get("div", pd.Series(dtype=float))
    if not div.get("ok"):
        st.info(div.get("motivo") or "Sem histórico de rendimentos.")
        return
    k, mot = fiis.classe_dividendo(div)
    rot = {"boa": "🟢 Distribuição regular", "atencao": "🟡 Distribuição com pontos de atenção", "fraca": "🔴 Distribuição fraca",
           "insuficiente": "⚪ Histórico insuficiente"}[k]
    st.markdown(f"**{rot}**")
    for m in mot:
        st.write("• " + m[0].upper() + m[1:] + ".")
    a, b = st.columns(2)
    a.metric("DY 12 meses", _f(div.get("dy_12m"), 1, "%"))
    b.metric("DY sem pagamentos acima do normal", _f(div.get("dy_recorrente"), 1, "%"))
    a, b = st.columns(2)
    a.metric("Meses pagos (12m)", _f(div.get("meses_pagos_12"), 0))
    b.metric("Variação 12m vs 12m anteriores", _f(div["var_12m"] * 100, 1, "%") if div.get("var_12m") is not None else "n/d")
    mensal = s.groupby(s.index.to_period("M")).sum()
    mensal.index = mensal.index.to_timestamp(how="end").normalize()
    df = pd.DataFrame({"Rendimento por cota (R$)": mensal.tail(36)})
    st.plotly_chart(evolucao.grafico_barras(df, ["Rendimento por cota (R$)"], "Rendimento por cota (últimos 36 meses)"),
                    width="stretch", key=f"fii_div_{d['tk']}", config={"displayModeBar": False})
    if div.get("extraordinarios"):
        st.markdown("**Pagamentos bem acima do normal (possíveis extraordinários)**")
        st.dataframe(pd.DataFrame([{"Mês": e.mes, "Valor por cota": _f(e.valor, 2, "", "R$ "), "Vezes a mediana": _f(e.razao, 1, "×")}
                                   for e in div["extraordinarios"][-8:]]), hide_index=True, width="stretch")
        st.caption("É um indício estatístico (acima de 1,5× a mediana dos 12 meses anteriores), não uma confirmação.")
    an = div.get("anuais")
    if an is not None and len(an) >= 2:
        st.plotly_chart(evolucao.grafico_barras(pd.DataFrame({"Total no ano (R$/cota)": an}), ["Total no ano (R$/cota)"],
                                                "Rendimentos por ano"), width="stretch", key=f"fii_divan_{d['tk']}",
                        config={"displayModeBar": False})
        cg = cr.cagr_periodos(an, (3, 5))
        st.caption("Crescimento anual dos rendimentos por cota: " + " · ".join(f"{n} anos: {cg[n].texto}" for n in (3, 5)))
    st.markdown("**Indisponível (precisa do relatório gerencial):** " + ", ".join(div["indisponivel"]) + ".")


def _escolher_cnpj(tk: str) -> str | None:
    chave = f"fii_cnpj_{tk}"
    atual = st.session_state.get(chave, "")
    c = st.text_input("CNPJ do fundo (para buscar o histórico oficial na CVM)", value=atual, key=f"in_{chave}",
                      placeholder="00.000.000/0000-00")
    if c and fiis_cvm.cnpj_valido(c):
        st.session_state[chave] = fiis_cvm.formatar_cnpj(c)
    elif c:
        st.warning("CNPJ inválido.")
    with st.expander("Não sei o CNPJ: buscar pelo nome"):
        nome = st.text_input("Parte do nome do fundo", key=f"nome_{chave}", placeholder="Ex.: logistica, kinea, xp malls")
        if nome and len(nome.strip()) >= 3:
            ach = fiis_cvm.buscar_por_nome(_geral_cvm(date.today().year), nome)
            if not ach:
                st.caption("Nenhum fundo com esse nome (a CVM usa o nome completo do regulamento).")
            for cn, nm in ach:
                if st.button(f"{nm} — {cn}", key=f"pick_{chave}_{cn}"):
                    st.session_state[chave] = cn
                    st.session_state[f"in_{chave}"] = cn
                    st.rerun()
    return st.session_state.get(chave)


def _recorte(s: pd.Series, vista: str, como: str = "ultimo") -> pd.Series:
    s = cr.serie_limpa(s)
    if vista == "Anual":
        return fiis_cvm.serie_anual(s, como)
    if vista == "Trimestral":
        return s[s.index.month.isin([3, 6, 9, 12])]
    return s


def _ligar_cvm(tk: str, cnpj: str):
    st.session_state[f"fii_cvm_ok_{tk}"] = cnpj


def _cvm_do_fundo(tk: str) -> pd.DataFrame | None:
    cn = st.session_state.get(f"fii_cvm_ok_{tk}")
    if not cn:
        return None
    h = historico_cvm(cn, date.today().year)
    return h["df"] if not h["df"].empty else None


def _aba_historico(d, precos):
    tk = d["tk"]
    cnpj = _escolher_cnpj(tk)
    if not cnpj:
        st.info("Informe o CNPJ para ver o histórico oficial (patrimônio, valor patrimonial, cotistas, rendimento do mês e passivo).")
    else:
        st.button("Carregar histórico da CVM", key=f"fii_cvm_btn_{tk}", type="primary", on_click=_ligar_cvm, args=(tk, cnpj))
        if st.session_state.get(f"fii_cvm_ok_{tk}") == cnpj:
            h = historico_cvm(cnpj, date.today().year)
            if h["erro"]:
                st.error("O layout do arquivo da CVM não é o esperado: " + h["erro"])
            for a in h["avisos"]:
                st.caption("⚠️ " + a)
            if not h["df"].empty:
                _mostrar_cvm(d, h["df"], precos)
        else:
            st.caption("Toque em **Carregar histórico da CVM** (arquivos grandes: leva alguns segundos na primeira vez).")
    st.markdown("**Vacância, receita imobiliária e inquilinos ao longo do tempo:** a CVM não publica no informe mensal "
                "(estão nos relatórios gerenciais), então não há série histórica no app. Só o valor de hoje, na aba Indicadores.")


def _mostrar_cvm(d, df, precos):
    ult = df.index[-1]
    st.caption(f"Informes de {df.index[0]:%m/%Y} a {ult:%m/%Y}. A CVM publica com atraso: o último mês disponível é {ult:%m/%Y}.")
    vista = st.radio("Periodicidade", ["Mensal", "Trimestral", "Anual"], horizontal=True, key=f"fii_vista_{d['tk']}")
    graf = [("pl", "Patrimônio líquido (R$)", "ultimo"), ("vp_cota", "Valor patrimonial por cota (R$)", "ultimo"),
            ("cotistas", "Número de cotistas", "ultimo")]
    for col, titulo, como in graf:
        if col in df:
            s = _recorte(df[col], vista, como)
            if len(s) >= 2:
                st.plotly_chart(evolucao.grafico_linhas({titulo: s}, titulo), width="stretch",
                                key=f"fii_h_{col}_{d['tk']}_{vista}", config={"displayModeBar": False})
    if "vp_cota" in df and len(precos.get("preco", [])):
        pvp = fiis_cvm.pvp_historico(precos["preco"], df["vp_cota"])
        pvp = _recorte(pvp, vista) if vista != "Anual" else fiis_cvm.serie_anual(pvp, "ultimo")
        if len(pvp) >= 2:
            st.plotly_chart(evolucao.grafico_linhas({"P/VP": pvp}, "P/VP no fim de cada período"), width="stretch",
                            key=f"fii_h_pvp_{d['tk']}_{vista}", config={"displayModeBar": False})
            st.caption("P/VP = último preço do mês ÷ valor patrimonial por cota informado pelo fundo para o mês.")
    if "dy_mes" in df and vista == "Mensal" and df["dy_mes"].notna().sum() >= 2:
        st.plotly_chart(evolucao.grafico_barras(pd.DataFrame({"Rendimento do mês (%)": df["dy_mes"].tail(36)}),
                                                ["Rendimento do mês (%)"], "Rendimento do mês (% sobre o valor da cota)"),
                        width="stretch", key=f"fii_h_dym_{d['tk']}", config={"displayModeBar": False})
    linhas = []
    for col, nome in (("pl", "Patrimônio líquido"), ("vp_cota", "Valor patrimonial por cota"), ("cotistas", "Número de cotistas")):
        if col in df:
            r = fiis_cvm.cagr_mensal(df[col], (1, 3, 5))
            linhas.append({"Indicador": nome, **{f"{n} ano" + ("s" if n > 1 else ""): r[n].texto for n in (1, 3, 5)}})
    if linhas:
        st.markdown("**Crescimento anual composto (CAGR), mesmo mês de cada ano**")
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        st.caption("Patrimônio líquido cresce também por novas emissões de cotas: o CAGR do valor patrimonial por cota mostra "
                   "o crescimento sem esse efeito.")


def _aba_imoveis(d):
    c, ind = d["classe"], d["ind"]
    if c.estrategia in ("tijolo", "hibrido"):
        st.markdown("**Carteira de imóveis (resumo)**")
        a, b = st.columns(2)
        a.metric("Imóveis", _f(ind.get("qtd_imoveis"), 0))
        b.metric("Vacância média", _f(ind.get("vacancia"), 1, "%"))
        a, b = st.columns(2)
        a.metric("Cap rate", _f(ind.get("cap_rate"), 1, "%"))
        b.metric("Aluguel por m²", _f(ind.get("aluguel_m2"), 0, "", "R$ "))
        st.metric("Preço por m²", _f(ind.get("preco_m2"), 0, "", "R$ "))
        st.caption("Dados do Fundamentus (valor de hoje).")
    if c.estrategia in ("papel", "hibrido"):
        st.markdown("**Carteira de recebíveis (CRIs)**")
    st.markdown("**Ainda sem fonte integrada no app** (estão no relatório gerencial mensal do fundo):")
    falta = {"tijolo": ["Lista e localização de cada imóvel", "Perfil e concentração de inquilinos", "Prazo médio e tipo dos contratos",
                        "Reajustes contratuais", "Vacância física × financeira", "Inadimplência de inquilinos"],
             "papel": ["Lista de CRIs e devedores", "Indexadores (CDI, IPCA, prefixado) e taxas", "Prazo médio dos recebíveis",
                       "Garantias e LTV", "Concentração por devedor e por setor", "Inadimplência"],
             "fof": ["Fundos em que investe e peso de cada um"], "desenvolvimento": ["Cronograma e custo das obras"]}
    chaves = ["tijolo", "papel"] if c.estrategia == "hibrido" else [c.estrategia]
    itens = [i for k in chaves for i in falta.get(k, ["Composição da carteira"])]
    for i in dict.fromkeys(itens):
        st.write("• " + i)
    st.info("Procure o **relatório gerencial** do fundo no site do gestor ou na B3. Quando o app integrar essa leitura, estes "
            "campos aparecem aqui.")


def _aba_riscos(d):
    for r in sorted(d["riscos"], key=lambda r: ["alto", "medio", "baixo", "indisponivel"].index(r.nivel)):
        ico, nome = NIVEL[r.nivel]
        with st.container(border=True):
            st.markdown(f"{ico} **{r.nome}** · {nome}")
            st.write(r.texto)
            for e in r.evidencias:
                st.caption(e)
    st.caption("Os limites (vacância acima de 15%, liquidez abaixo de R$ 300 mil/dia etc.) são regras educacionais para "
               "chamar atenção, não uma recomendação. Risco 'sem dado' não significa risco baixo.")


def _aba_comparacao(d, atalho_comparar):
    peers, pi = d["pares"], d["pares_info"]
    if peers is None or peers.empty:
        st.info("Sem fundos semelhantes na lista (" + str(pi.get("descricao")) + ").")
        return
    st.markdown(f"**Fundos semelhantes:** {pi['descricao']}")
    a, b, c = st.columns(3)
    a.metric("P/VP mediano", _f(pi.get("pvp_mediana"), 2), delta=None if not fiis._ok(d["ind"].get("pvp")) or not fiis._ok(pi.get("pvp_mediana"))
             else _f(d["ind"]["pvp"] - pi["pvp_mediana"], 2) + " este fundo", delta_color="off")
    b.metric("DY mediano", _f(pi.get("dy_mediana"), 1, "%"))
    c.metric("Vacância mediana", _f(pi.get("vacancia_mediana"), 1, "%"))
    crit = st.selectbox("Ranking entre os semelhantes", list(fiis.CRITERIOS_RANKING), key=f"fii_rank_{d['tk']}",
                        format_func=lambda k: {"valuation": "Valuation (P/VP)", "renda": "Renda (DY)", "liquidez": "Liquidez",
                                               "vacancia": "Qualidade dos imóveis (vacância)", "tamanho": "Porte"}[k])
    crit = crit or "valuation"
    base = pd.concat([peers, pd.DataFrame([d["row"]], index=[d["tk"]])]) if d["row"] else peers
    rk = fiis.ranking(base, crit)
    if rk.empty:
        st.caption("Sem dado suficiente para este ranking.")
    else:
        col = fiis.CRITERIOS_RANKING[crit][0]
        tab = pd.DataFrame({"FII": rk.index, fiis.CRITERIOS_RANKING[crit][2].split(" (")[0]: rk[col].map(lambda v: _f(v, 2)).values})
        tab["FII"] = tab["FII"].map(lambda x: x + " ◀" if x == d["tk"] else x)
        st.dataframe(tab, hide_index=True, width="stretch")
        st.caption(fiis.CRITERIOS_RANKING[crit][2] + ". Só entram fundos com liquidez de pelo menos R$ 100 mil/dia. "
                   "Ranking só entre fundos da mesma estratégia; DY muito acima dos pares vai para o fim da lista.")
    if atalho_comparar is not None:
        top = [t for t in fiis.ranking(peers, "liquidez", topo=3).index]
        atalho_comparar([d["tk"], *top], f"fii_{d['tk']}", "Comparar com os 3 mais líquidos do mesmo grupo")


def _aba_analise(d):
    for titulo, linhas in d["relatorio"].items():
        if titulo == "Fontes e datas":
            continue
        st.markdown(f"**{titulo}**")
        for l in linhas:
            st.write("• " + l)
    with st.expander("De onde vem cada dado"):
        st.dataframe(pd.DataFrame([{"Indicador": k, "Fonte": v[0], "Referência": _data_br(v[1]) if v[1] else "—"}
                                   for k, v in d["fontes"].items() if k != "pvp_aviso"]), hide_index=True, width="stretch")
    st.caption("Relatório gerado por regras sobre os dados disponíveis. Não é recomendação de investimento. "
               + comparador.AVISO_LEGAL)


# =============================================================================== página
def pagina_fii(atalho_comparar=None, atalho_evolucao=None):
    st.markdown(tema.cabecalho("🏢", "FIIs", "Análise completa de fundos imobiliários: indicadores, rendimentos, riscos e comparação."),
                unsafe_allow_html=True)
    L = lista_fiis()
    lista = L["df"]
    if L["aviso"]:
        st.warning(L["aviso"] + " Os indicadores que dependem dessa lista ficam indisponíveis.")
    pre = st.session_state.pop("fii_pre", None)
    if pre:
        st.session_state["fii_tk"] = pre
    opcoes = sorted(lista.index) if not lista.empty else []
    if opcoes:
        tk = st.selectbox("FII", opcoes, key="fii_tk", index=None, placeholder="Digite o código. Ex.: HGLG11, KNCR11",
                          accept_new_options=True)
    else:
        tk = st.text_input("Código do FII", key="fii_tk", placeholder="Ex.: HGLG11")
    m = re.search(r"[A-Z]{4}\d{1,2}", re.sub(r"[^A-Z0-9 ]", " ", (tk or "").upper()))
    tk = m.group(0) if m else re.sub(r"[^A-Z0-9]", "", (tk or "").upper())
    if not tk:
        st.info("Escolha um FII para ver a análise.")
        return
    if not re.fullmatch(r"[A-Z]{4}1[0-9]?", tk):
        st.warning("Código de FII costuma ter 4 letras e o número 11 (ex.: HGLG11).")
    with st.spinner("Coletando dados do fundo..."):
        precos = evolucao.coletar_precos(tk)
        snap = evolucao.coletar_fii_fundamentus(tk)
        cvm_df = _cvm_do_fundo(tk)
        d = preparar(tk, lista, snap, precos, cvm_df)
    for av in precos.get("avisos", []) + snap.get("avisos", []):
        st.caption("⚠️ " + av)
    # monitoramento: compara com a última vez que este FII foi aberto NESTA sessão
    foto = {k: d["ind"].get(k) for k in fiis.LIM_MUDANCA}
    ant = st.session_state.setdefault("fii_fotos", {}).get(tk)
    mud = fiis.detectar_mudancas(ant, foto)
    if mud:
        st.warning("Mudanças desde a última consulta nesta sessão: " + " ".join(mud))
    st.session_state["fii_fotos"][tk] = foto
    abas = st.tabs(["Visão geral", "Indicadores", "Dividendos", "Histórico", "Imóveis ou recebíveis", "Riscos", "Comparação",
                    "Análise inteligente"])
    with abas[0]:
        _aba_visao(d)
        if atalho_evolucao is not None:
            atalho_evolucao(tk, "fii", "Evolução e crescimento deste FII")
    with abas[1]:
        _aba_indicadores(d)
    with abas[2]:
        _aba_dividendos(d, precos)
    with abas[3]:
        _aba_historico(d, precos)
    with abas[4]:
        _aba_imoveis(d)
    with abas[5]:
        _aba_riscos(d)
    with abas[6]:
        _aba_comparacao(d, atalho_comparar)
    with abas[7]:
        _aba_analise(d)


# =============================================================================== carteira
def painel_carteira(lotes: list):
    """FIIs dentro da carteira do usuário: concentração e renda estimada. Somente leitura: nada é alterado."""
    L = lista_fiis()
    if L["df"].empty:
        return
    a = fiis.analisar_carteira(lotes, L["df"])
    if not a["fiis"]:
        return
    st.markdown("#### Meus FIIs")
    st.dataframe(pd.DataFrame([{"FII": i["ticker"], "Peso": _f(i["peso"], 1, "%"), "Estratégia": fiis.ESTRATEGIAS.get(i["estrategia"], "—"),
                                "Segmento": i["segmento"], "DY": _f(i["dy"], 1, "%"), "P/VP": _f(i["pvp"], 2)} for i in a["fiis"]]),
                 hide_index=True, width="stretch")
    por = pd.DataFrame({"Segmento": list(a["por_segmento"]), "Peso (%)": [round(v, 1) for v in a["por_segmento"].values()]})
    st.dataframe(por, hide_index=True, width="stretch")
    for al in a["alertas"]:
        st.warning(al)
    if a["renda_mensal_estimada"] is not None:
        st.metric("Renda mensal de referência", _brl_g(a["renda_mensal_estimada"]))
        st.caption("Referência: valor atual dos FIIs × Dividend Yield anual da fonte ÷ 12. Não é garantia: os rendimentos variam todo mês.")
    st.caption("Concentração por gestor, por imóvel e por devedor: " + ", ".join(a["indisponivel"][:2]).lower()
               + " ainda não têm fonte no app. Esta análise não altera a sua carteira.")
