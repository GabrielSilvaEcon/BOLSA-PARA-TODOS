"""
Página Carteira: carteira fictícia (simulação) e carteira real (registro), com desempenho.

Os dados ficam na sessão do navegador. Para não perder, use Exportar CSV e depois Importar CSV.
Preços e históricos vêm do Yahoo Finance (via dados.py). Não inclui dividendos, custos nem impostos.
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import tema

from dados import brl, buscar_yahoo, historico_yahoo, normaliza

try:
    import recursos as rec
except Exception:  # sem o catálogo, aceita só o ticker digitado
    rec = None

COLUNAS = ["ticker", "qtd", "preco_medio", "data"]
TRANSP = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=40, b=10))


# ---------------------------------------------------------------- dados
@st.cache_data(ttl=600, show_spinner=False)
def _preco_atual(tk: str):
    try:
        d = buscar_yahoo(tk)
        return d.get("preco"), d.get("nome")
    except Exception:
        return None, None


@st.cache_data(ttl=3600, show_spinner=False)
def _hist(tk: str, periodo: str) -> pd.Series:
    try:
        df, _ = historico_yahoo(tk, periodo, "1d")
    except Exception:
        return pd.Series(dtype=float)
    if df is None or df.empty or "Close" not in df:
        return pd.Series(dtype=float)
    s = df["Close"].dropna()
    idx = pd.DatetimeIndex(s.index)
    if idx.tz is not None:
        idx = idx.tz_convert(None)
    s.index = idx.normalize()
    return s[~s.index.duplicated(keep="last")]


def _resolver(termo: str):
    termo = (termo or "").strip()
    if not termo:
        return None
    tk = None
    if rec is not None:
        try:
            tk = rec.resolver_termo(termo)
        except Exception:
            tk = None
    return normaliza(tk or termo)


# ---------------------------------------------------------------- cálculos
def _tabela(lotes: list) -> pd.DataFrame:
    df = pd.DataFrame(lotes)
    linhas = []
    for tk, g in df.groupby("ticker"):
        qtd = int(g["qtd"].sum())
        custo = float((g["qtd"] * g["preco_medio"]).sum())
        preco, _ = _preco_atual(tk)
        valor = qtd * preco if preco else None
        linhas.append({
            "Ativo": tk, "Qtd": qtd, "Preço médio": custo / qtd if qtd else None, "Preço atual": preco,
            "Custo": custo, "Valor atual": valor,
            "Resultado (R$)": valor - custo if valor is not None else None,
            "Resultado (%)": (valor / custo - 1) * 100 if valor is not None and custo > 0 else None,
        })
    out = pd.DataFrame(linhas)
    total = out["Valor atual"].sum(skipna=True)
    out["Peso (%)"] = out["Valor atual"] / total * 100 if total > 0 else None
    return out


def _evolucao(lotes: list):
    """Valor da carteira ao longo do tempo (a partir da data de cada compra) e custo acumulado."""
    df = pd.DataFrame(lotes)
    df["data"] = pd.to_datetime(df["data"]).dt.normalize()
    inicio = df["data"].min()
    periodo = "2y" if inicio >= pd.Timestamp.today().normalize() - pd.Timedelta(days=700) else "5y"
    valores, custos = {}, {}
    for tk, g in df.groupby("ticker"):
        s = _hist(tk, periodo)
        if s.empty:
            continue
        s = s[s.index >= inicio]
        if s.empty:
            continue
        v = pd.Series(0.0, index=s.index)
        c = pd.Series(0.0, index=s.index)
        for _, lote in g.iterrows():
            m = s.index >= lote["data"]
            v[m] = v[m] + s[m] * lote["qtd"]
            c[m] = c[m] + lote["qtd"] * lote["preco_medio"]
        valores[tk], custos[tk] = v, c
    if not valores:
        return None, None
    dv = pd.DataFrame(valores).sort_index().ffill().fillna(0).sum(axis=1)
    dc = pd.DataFrame(custos).sort_index().ffill().fillna(0).sum(axis=1)
    return dv, dc


# ---------------------------------------------------------------- interface
def _form(chave: str, caixa):
    with st.form(f"form_{chave}", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 1, 1.2, 1.2])
        termo = c1.text_input("Empresa ou ticker", placeholder="Ex.: Petrobras ou PETR4")
        qtd = c2.number_input("Quantidade", min_value=1, step=1, value=100)
        pm = c3.number_input("Preço pago (R$)", min_value=0.0, step=0.01, format="%.2f",
                             help="Deixe 0 para usar o preço atual da ação.")
        dt = c4.date_input("Data da compra", value=date.today(), max_value=date.today(), format="DD/MM/YYYY")
        ok = st.form_submit_button("➕ Adicionar à carteira")
    if not ok:
        return
    tk = _resolver(termo)
    if not tk:
        st.warning("Digite o nome ou o ticker da empresa.")
        return
    preco = pm
    if preco <= 0:
        atual, _ = _preco_atual(tk)
        if not atual:
            st.error(f"Não consegui o preço atual de {tk}. Confira o ticker ou informe o preço pago.")
            return
        preco = float(atual)
    custo = qtd * preco
    if caixa is not None and custo > caixa + 1e-9:
        st.error(f"Essa compra custa {brl(custo)}, mas o caixa disponível é {brl(caixa)}.")
        return
    st.session_state[chave].append({"ticker": tk, "qtd": int(qtd), "preco_medio": float(preco),
                                    "data": dt.isoformat()})
    st.rerun()


def _arquivo(chave: str):
    lotes = st.session_state[chave]
    with st.expander("💾 Salvar ou carregar (CSV)"):
        st.caption("Os dados ficam só nesta sessão do navegador. Exporte para guardar e importe quando voltar.")
        if lotes:
            st.download_button("⬇️ Exportar CSV", pd.DataFrame(lotes).to_csv(index=False).encode("utf-8"),
                               file_name=f"{chave}.csv", mime="text/csv", key=f"dl_{chave}")
        arq = st.file_uploader("Importar CSV", type="csv", key=f"up_{chave}")
        if arq is not None and st.button("Carregar arquivo", key=f"load_{chave}"):
            try:
                novo = pd.read_csv(arq)
                if not set(COLUNAS).issubset(novo.columns):
                    st.error("O arquivo precisa ter as colunas: " + ", ".join(COLUNAS))
                else:
                    novo = novo[COLUNAS].dropna()
                    novo["ticker"] = novo["ticker"].map(normaliza)
                    novo["qtd"] = novo["qtd"].astype(int)
                    novo["preco_medio"] = novo["preco_medio"].astype(float)
                    novo["data"] = pd.to_datetime(novo["data"]).dt.date.astype(str)
                    st.session_state[chave] = novo.to_dict("records")
                    st.rerun()
            except Exception as e:
                st.error(f"Não consegui ler o arquivo: {e}")


def _lancamentos(chave: str):
    lotes = st.session_state[chave]
    with st.expander("🧾 Compras registradas e remoção"):
        df = pd.DataFrame(lotes).rename(columns={"ticker": "Ativo", "qtd": "Qtd", "preco_medio": "Preço pago",
                                                 "data": "Data"})
        st.dataframe(df, hide_index=True, width="stretch",
                     column_config={"Preço pago": st.column_config.NumberColumn(format="R$ %.2f")})
        i = st.selectbox("Remover uma compra", range(len(lotes)), key=f"rm_{chave}",
                         format_func=lambda k: f"{lotes[k]['ticker']} · {lotes[k]['qtd']} un. · {lotes[k]['data']}")
        c1, c2 = st.columns(2)
        if c1.button("Remover compra", key=f"rmb_{chave}"):
            lotes.pop(i)
            st.rerun()
        if c2.checkbox("Confirmo zerar toda a carteira", key=f"zc_{chave}") and c2.button("🗑️ Zerar", key=f"zb_{chave}"):
            st.session_state[chave] = []
            st.rerun()


def _render(chave: str, ficticia: bool):
    st.session_state.setdefault(chave, [])
    lotes = st.session_state[chave]
    caixa = None
    if ficticia:
        capital = st.number_input("Capital inicial da simulação (R$)", min_value=1000.0, value=100000.0,
                                  step=1000.0, format="%.2f", key="cart_capital")
        caixa = capital - sum(l["qtd"] * l["preco_medio"] for l in lotes)
    _form(chave, caixa)

    if not lotes:
        st.markdown(tema.vazio("carteira",
                               "Nenhuma compra registrada ainda" if not ficticia else "Carteira vazia",
                               "Adicione a primeira compra acima para ver valor, ganho e alocação." if not ficticia else
                               "Escolha as empresas e as quantidades para simular o desempenho."),
                    unsafe_allow_html=True)
        _arquivo(chave)
        return

    with st.spinner("Buscando os preços atuais..."):
        tab = _tabela(lotes)
    sem_preco = tab[tab["Valor atual"].isna()]["Ativo"].tolist()
    if sem_preco:
        st.warning("Sem preço atual para: " + ", ".join(sem_preco) + ". Eles ficam fora do valor atual da carteira.")

    custo_total = float(tab["Custo"].sum())
    valor_total = float(tab["Valor atual"].sum(skipna=True))
    custo_ok = float(tab.loc[tab["Valor atual"].notna(), "Custo"].sum())
    res = valor_total - custo_ok
    res_pct = (valor_total / custo_ok - 1) * 100 if custo_ok > 0 else None

    cols = st.columns(5 if ficticia else 4)
    cols[0].metric("Investido", brl(custo_total))
    cols[1].metric("Valor atual", brl(valor_total))
    cols[2].metric("Resultado", brl(res), delta=f"{res_pct:+.2f}%".replace(".", ",") if res_pct is not None else None)
    if ficticia:
        cols[3].metric("Caixa", brl(caixa))
        cols[4].metric("Patrimônio total", brl(caixa + valor_total))
    else:
        cols[3].metric("Posições", str(len(tab)))

    st.markdown("#### Posições")
    st.dataframe(tab, hide_index=True, width="stretch", column_config={
        "Qtd": st.column_config.NumberColumn(format="%d"),
        "Preço médio": st.column_config.NumberColumn(format="R$ %.2f"),
        "Preço atual": st.column_config.NumberColumn(format="R$ %.2f"),
        "Custo": st.column_config.NumberColumn(format="R$ %.2f"),
        "Valor atual": st.column_config.NumberColumn(format="R$ %.2f"),
        "Resultado (R$)": st.column_config.NumberColumn(format="R$ %.2f"),
        "Resultado (%)": st.column_config.NumberColumn(format="%.1f%%"),
        "Peso (%)": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.1f%%"),
    })
    com_res = tab.dropna(subset=["Resultado (%)"])
    if len(com_res) >= 2:
        melhor, pior = com_res.loc[com_res["Resultado (%)"].idxmax()], com_res.loc[com_res["Resultado (%)"].idxmin()]
        maior = tab.loc[tab["Peso (%)"].idxmax()] if tab["Peso (%)"].notna().any() else None
        txt = (f"Melhor: **{melhor['Ativo']}** ({melhor['Resultado (%)']:+.1f}%) · "
               f"Pior: **{pior['Ativo']}** ({pior['Resultado (%)']:+.1f}%)")
        if maior is not None:
            txt += f" · Maior peso: **{maior['Ativo']}** ({maior['Peso (%)']:.0f}% da carteira)"
        st.caption(txt.replace(".", ","))

    g1, g2 = st.columns(2)
    with g1:
        aloc = tab.dropna(subset=["Valor atual"])
        if not aloc.empty:
            fig = go.Figure(go.Pie(labels=aloc["Ativo"], values=aloc["Valor atual"], hole=0.55,
                                   textinfo="label+percent"))
            fig.update_layout(title="Alocação por ativo", height=320, showlegend=False, **TRANSP)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    with g2:
        if not com_res.empty:
            ordem = com_res.sort_values("Resultado (%)")
            fig = go.Figure(go.Bar(
                x=ordem["Resultado (%)"], y=ordem["Ativo"], orientation="h",
                marker_color=["#15803D" if v >= 0 else "#C62828" for v in ordem["Resultado (%)"]],
                text=[f"{v:+.1f}%".replace(".", ",") for v in ordem["Resultado (%)"]], textposition="outside"))
            fig.update_layout(title="Resultado por ativo (%)", height=320, **TRANSP)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    with st.spinner("Montando a evolução da carteira..."):
        dv, dc = _evolucao(lotes)
    if dv is not None and len(dv) > 1:
        fig = go.Figure()
        fig.add_scatter(x=dv.index, y=dv.values, mode="lines", name="Valor da carteira", line=dict(width=2.5))
        fig.add_scatter(x=dc.index, y=dc.values, mode="lines", name="Total investido",
                        line=dict(width=2, dash="dot"))
        fig.update_layout(title="Evolução do valor da carteira", height=340,
                          legend=dict(orientation="h", y=-0.15, x=0), **TRANSP)
        st.plotly_chart(fig, width="stretch")
        st.caption("A evolução considera que cada compra entrou na data informada, com os preços de fechamento "
                   "diários. Não inclui dividendos, custos nem impostos.")
    else:
        st.caption("Não consegui montar a evolução (histórico indisponível para os ativos).")

    _lancamentos(chave)
    _arquivo(chave)


def pagina_carteira():
    st.markdown("#### 💼 Minha carteira")
    st.caption("Simule uma carteira de ações sem risco ou registre a sua carteira real e acompanhe o desempenho.")
    t1, t2 = st.tabs(["🧪 Carteira fictícia", "📒 Carteira real"])
    with t1:
        st.caption("Escolha um capital inicial e monte uma carteira de teste. Nada aqui usa dinheiro de verdade.")
        _render("cart_ficticia", ficticia=True)
    with t2:
        st.caption("Registre o que você realmente comprou (quantidade, preço pago e data) para acompanhar o resultado.")
        _render("cart_real", ficticia=False)
    st.caption("Ferramenta educacional. Preços do Yahoo Finance, podem ter atraso. Confira sempre os extratos da sua corretora.")
