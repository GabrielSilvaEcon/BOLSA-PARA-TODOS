"""
Página Carteira: carteira fictícia (simulação) e carteira real (registro), com desempenho.

Os dados ficam na sessão do navegador. Para não perder, use Exportar CSV e depois Importar CSV.
Preços e históricos vêm do Yahoo Finance (via dados.py). Não inclui dividendos, custos nem impostos.
"""

import html
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import moeda
import seguranca as seg
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
    """Uma linha por ativo. Preços na moeda do ativo; custo, valor e resultado sempre em reais
    (ativo em US$: custo pelo dólar do dia da compra, valor pelo dólar de hoje)."""
    df = pd.DataFrame(lotes)
    fx = moeda.cambio_serie() if any(moeda.eh_dolar(t) for t in df["ticker"]) else None
    fx_hoje = moeda.cambio_em(fx)
    linhas = []
    for tk, g in df.groupby("ticker"):
        usd = moeda.eh_dolar(tk)
        qtd = float(g["qtd"].sum())
        custo_nat = float((g["qtd"] * g["preco_medio"]).sum())
        custo = sum(moeda.custo_lote_brl(l, fx) or float("nan") for l in g.to_dict("records"))
        preco, _ = _preco_atual(tk)
        valor = qtd * preco * (fx_hoje if usd else 1.0) if preco and (fx_hoje or not usd) else None
        ok = valor is not None and custo == custo
        linhas.append({
            "Ativo": tk, "Moeda": "US$" if usd else "R$", "Qtd": qtd,
            "Preço médio": custo_nat / qtd if qtd else None, "Preço atual": preco,
            "Custo": custo if custo == custo else None, "Valor atual": valor,
            "Resultado (R$)": valor - custo if ok else None,
            "Resultado (%)": (valor / custo - 1) * 100 if ok and custo > 0 else None,
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
    fx = moeda.cambio_serie() if any(moeda.eh_dolar(t) for t in df["ticker"]) else None
    for tk, g in df.groupby("ticker"):
        s = _hist(tk, periodo)
        if s.empty:
            continue
        s = s[s.index >= inicio]
        if s.empty:
            continue
        usd = moeda.eh_dolar(tk)
        if usd:                                           # ativo em US$: série em reais pelo dólar de cada dia
            if fx is None or len(fx) == 0:
                continue
            f = fx.copy()
            f.index = pd.DatetimeIndex(f.index).tz_localize(None).normalize()
            f = f[~f.index.duplicated(keep="last")]
            idx = pd.DatetimeIndex(s.index).tz_localize(None).normalize()
            cam = f.reindex(f.index.union(idx)).ffill().reindex(idx)
            s = pd.Series(s.values * cam.values, index=s.index).dropna()
            if s.empty:
                continue
        v = pd.Series(0.0, index=s.index)
        c = pd.Series(0.0, index=s.index)
        for _, lote in g.iterrows():
            m = s.index >= lote["data"]
            v[m] = v[m] + s[m] * lote["qtd"]
            c[m] = c[m] + (moeda.custo_lote_brl(lote.to_dict(), fx) or 0.0)
        valores[tk], custos[tk] = v, c
    if not valores:
        return None, None
    dv = pd.DataFrame(valores).sort_index().ffill().fillna(0).sum(axis=1)
    dc = pd.DataFrame(custos).sort_index().ffill().fillna(0).sum(axis=1)
    return dv, dc


# ---------------------------------------------------------------- interface
def _rotulo_opcao(t) -> str:
    """Texto de cada opção da lista (ex.: 'PETR4 · Petrobras'); aceita também o que a pessoa digitou."""
    try:
        return rec.rotulo(t) if rec is not None else str(t)
    except Exception:
        return str(t)


def _ao_escolher(chave: str):
    """Ao escolher a empresa: busca o preço atual e já o coloca no campo 'Preço pago'."""
    sel = st.session_state.get(f"sel_{chave}")
    tk = _resolver(sel) if sel else None
    atual = _preco_atual(tk)[0] if tk else None
    st.session_state[f"pm_{chave}"] = round(float(atual), 2) if atual else 0.0


def _registrar(chave: str, caixa):
    """Valida a compra e a adiciona à carteira; deixa o aviso em session_state para aparecer uma vez."""
    ss = st.session_state
    sel = ss.get(f"sel_{chave}")
    tk = _resolver(sel) if sel else None
    if not tk:
        ss[f"flash_{chave}"] = ("warn", "Escolha a empresa na lista ou digite o ticker.")
        return
    qtd = int(ss.get(f"qtd_{chave}") or 0)
    preco = float(ss.get(f"pm_{chave}") or 0.0)
    dt = ss.get(f"dt_{chave}") or date.today()
    if qtd < 1:
        ss[f"flash_{chave}"] = ("warn", "A quantidade precisa ser de pelo menos 1.")
        return
    if preco <= 0:
        atual, _ = _preco_atual(tk)
        if not atual:
            ss[f"flash_{chave}"] = ("err", f"Não consegui o preço atual de {tk}. Confira o ticker ou informe o preço pago.")
            return
        preco = float(atual)
    custo = qtd * preco
    usd = moeda.eh_dolar(tk)
    custo_brl = custo
    if usd:
        f = moeda.cambio_em(moeda.cambio_serie(), dt)
        if not f:
            ss[f"flash_{chave}"] = ("err", "Não consegui a cotação do dólar para converter essa compra. Tente de novo em instantes.")
            return
        custo_brl = custo * f
    if caixa is not None and custo_brl > caixa + 1e-9:
        ss[f"flash_{chave}"] = ("err", f"Essa compra custa {brl(custo_brl)}, mas o caixa disponível é {brl(caixa)}.")
        return
    ss[chave].append({"ticker": tk, "qtd": qtd, "preco_medio": preco, "data": dt.isoformat()})
    ss[f"sel_{chave}"], ss[f"qtd_{chave}"], ss[f"pm_{chave}"] = None, 1, 0.0
    ss[f"_pmtk_{chave}"] = None
    txt = f"US$ {preco:,.2f} × {qtd} = US$ {custo:,.2f} (≈ {brl(custo_brl)})".replace(",", "X").replace(".", ",").replace("X", ".") if usd \
        else f"{qtd} × {brl(preco)} = {brl(custo)}"
    ss[f"flash_{chave}"] = ("ok", f"{tk} adicionada: {txt}.")


def _moeda_txt(tk: str, v: float) -> str:
    if not moeda.eh_dolar(tk):
        return brl(v)
    return "US$ " + f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _preencher_preco(chave: str):
    """Ao escolher (ou digitar) o ativo, o preço atual entra sozinho no campo 'Preço pago'. Feito ANTES de desenhar os campos
    para valer também para ticker digitado e não depender do callback. Só preenche uma vez por ativo, para não apagar um preço que a pessoa editou."""
    ss = st.session_state
    sel = ss.get(f"sel_{chave}")
    tk = _resolver(sel) if sel else None
    if not tk:
        ss[f"_pmtk_{chave}"] = None
        return
    if ss.get(f"_pmtk_{chave}") == tk:
        return
    atual, _ = _preco_atual(tk)
    if atual:
        ss[f"pm_{chave}"] = round(float(atual), 2)
        ss[f"_pmtk_{chave}"] = tk


def _form(chave: str, caixa):
    opcoes = list(getattr(rec, "TODOS_TICKERS", []) or []) if rec is not None else []
    _preencher_preco(chave)
    st.markdown("<div class='ct-sec'>Nova compra</div>", unsafe_allow_html=True)
    with st.container(border=True, key=f"form_{chave}"):
        c1, c2, c3, c4 = st.columns([2.2, 1, 1.2, 1.2])
        c1.selectbox("Empresa ou ticker", opcoes, index=None, key=f"sel_{chave}", format_func=_rotulo_opcao,
                     accept_new_options=True, placeholder="Digite o nome ou o ticker: petr, vale, itau…",
                     on_change=_ao_escolher, args=(chave,),
                     help="Comece a digitar e escolha na lista. Ticker fora da lista também vale.")
        c2.number_input("Quantidade", min_value=1, step=1, value=1, key=f"qtd_{chave}")
        c3.number_input("Preço pago", min_value=0.0, step=0.01, format="%.2f", value=0.0, key=f"pm_{chave}",
                        help="Na moeda do ativo: R\\$ para a B3, US\\$ para ativos do exterior (AAPL, VOO). Já vem com o preço atual; 0 usa o preço atual.")
        c4.date_input("Data da compra", value=date.today(), max_value=date.today(), format="DD/MM/YYYY",
                      key=f"dt_{chave}")

        sel = st.session_state.get(f"sel_{chave}")
        tk = _resolver(sel) if sel else None
        if tk:
            with st.spinner("Buscando o preço atual…"):
                atual, nome = _preco_atual(tk)
            if atual:
                qtd = int(st.session_state.get(f"qtd_{chave}") or 0)
                ref = float(st.session_state.get(f"pm_{chave}") or 0.0) or float(atual)
                extra = f" · caixa disponível {brl(caixa)}" if caixa is not None else ""
                st.markdown(
                    f"<div class='pv'><span class='dot'></span><div><div class='pv-t'>{html.escape(str(tk))}"
                    f"{' · ' + html.escape(str(nome)) if nome else ''}</div><div class='pv-s'>Preço atual "
                    f"<b>{_moeda_txt(tk, float(atual))}</b> · custo desta compra <b>{_moeda_txt(tk, qtd * ref)}</b>{extra}</div></div></div>",
                    unsafe_allow_html=True)
            else:
                st.warning(f"Não consegui o preço atual de {tk} agora. Informe o preço pago ou tente de novo.")
        st.button("Adicionar à carteira", icon=":material/add:", type="primary", key=f"add_{chave}",
                  on_click=_registrar, args=(chave, caixa), width="stretch")

    flash = st.session_state.pop(f"flash_{chave}", None)
    if flash:
        {"ok": st.success, "warn": st.warning, "err": st.error}.get(flash[0], st.info)(flash[1])


def _arquivo(chave: str):
    lotes = st.session_state[chave]
    with st.expander("💾 Salvar ou carregar (CSV)"):
        st.caption("Os dados ficam só nesta sessão do navegador. Exporte para guardar e importe quando voltar.")
        if lotes:
            st.download_button("⬇️ Exportar CSV", seg.neutralizar_tabela(pd.DataFrame(lotes)).to_csv(index=False).encode("utf-8"),
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
                    novo["qtd"] = novo["qtd"].astype(float).map(lambda x: int(x) if float(x).is_integer() else x)
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


_CSS = """<style>
.ct-sec{font-weight:800;color:#CFC8EE;font-size:.82rem;letter-spacing:.04em;text-transform:uppercase;margin:16px 2px 6px}
.ct-k{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin:6px 0 10px}
.ct-kc{background:linear-gradient(145deg,#1E1650,#160F36);border:1px solid #3D3182;border-left:5px solid var(--c,#8B6CFF);border-radius:16px;padding:10px 12px;min-width:0}
.ct-kc.larg{grid-column:1/-1}
.ct-kl{font-size:.72rem;font-weight:800;letter-spacing:.05em;text-transform:uppercase;color:#C5B3FF}
.ct-kv{font-size:1.3rem;font-weight:800;color:#F6F3FF;line-height:1.25;word-break:break-word}
.ct-ks{font-size:.82rem;font-weight:700;color:#CFC8EE}
.ct-kc.p .ct-kv,.ct-kc.p .ct-ks{color:#3DDC97}.ct-kc.n .ct-kv,.ct-kc.n .ct-ks{color:#FF6B8A}
.ct-p{background:linear-gradient(145deg,#1E1650,#160F36);border:1px solid #3D3182;border-radius:16px;padding:11px 13px;margin:8px 0}
.ct-pt{display:flex;justify-content:space-between;align-items:center;gap:8px}
.ct-pn{font-weight:800;font-size:1.02rem;color:#F6F3FF}
.ct-pr{font-weight:800;font-size:.9rem;border-radius:999px;padding:3px 10px;background:rgba(255,255,255,.08);color:#CFC8EE}
.ct-pr.p{background:rgba(61,220,151,.16);color:#3DDC97}.ct-pr.n{background:rgba(255,107,138,.16);color:#FF6B8A}
.ct-pl{margin-top:6px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:4px 10px;font-size:.84rem;color:#CFC8EE}
.ct-pl b{color:#F6F3FF}
.ct-bar{height:8px;background:#2A2060;border-radius:99px;overflow:hidden;margin-top:8px}.ct-bar i{display:block;height:100%;background:linear-gradient(90deg,#7C5CFF,#2DD4A0)}
.ct-chips{display:flex;flex-wrap:wrap;gap:6px;margin:4px 0 8px}
.ct-chip{font-weight:800;font-size:.82rem;border-radius:999px;padding:4px 11px}.ct-chip.g{background:rgba(61,220,151,.16);color:#3DDC97}.ct-chip.r{background:rgba(255,107,138,.16);color:#FF6B8A}
html body .stApp.stApp [class*="st-key-form_"] [data-testid="stWidgetLabel"] p{font-weight:800 !important;color:#CFC8EE !important;font-size:.82rem !important}
</style>"""


def _pct(v) -> str:
    return f"{v:+.1f}%".replace(".", ",")


def _kpis(investido, valor, res, res_pct, caixa) -> str:
    sinal = "p" if res > 0 else ("n" if res < 0 else "")
    cs = [("Investido", brl(investido), "", "#8B6CFF", ""), ("Valor atual", brl(valor), "", "#2BA7C9", ""),
          ("Resultado", brl(res), _pct(res_pct) if res_pct is not None else "", "#3DDC97" if res >= 0 else "#FF6B8A", sinal)]
    if caixa is not None:
        cs += [("Caixa", brl(caixa), "", "#F2B84B", ""), ("Patrimônio total", brl(caixa + valor), "", "#B02FC8", "larg")]
    out = "<div class='ct-k'>"
    for t, v, sub, cor, cls in cs:
        out += (f"<div class='ct-kc {cls}' style='--c:{cor}'><div class='ct-kl'>{t}</div><div class='ct-kv'>{html.escape(v)}</div>"
                f"{f'<div class=ct-ks>{html.escape(sub)}</div>' if sub else ''}</div>")
    return out + "</div>"


def _cartoes_posicoes(tab) -> str:
    out = ""
    for _, r in tab.sort_values("Valor atual", ascending=False, na_position="last").iterrows():
        tk = str(r["Ativo"])
        rp = r["Resultado (%)"]
        cls = "" if rp != rp or rp is None else ("p" if rp > 0 else ("n" if rp < 0 else ""))
        chip = _pct(rp) if rp == rp and rp is not None else "n/d"
        va = "n/d" if r["Valor atual"] != r["Valor atual"] else brl(float(r["Valor atual"]))
        rr = "n/d" if r["Resultado (R$)"] != r["Resultado (R$)"] else brl(float(r["Resultado (R$)"]))
        pm = "n/d" if r["Preço médio"] is None or r["Preço médio"] != r["Preço médio"] else _moeda_txt(tk, float(r["Preço médio"]))
        pa = "n/d" if r["Preço atual"] is None or r["Preço atual"] != r["Preço atual"] else _moeda_txt(tk, float(r["Preço atual"]))
        peso = r["Peso (%)"]
        peso_ok = peso == peso and peso is not None
        out += (f"<div class='ct-p'><div class='ct-pt'><span class='ct-pn'>{html.escape(tk)}</span><span class='ct-pr {cls}'>{chip}</span></div>"
                f"<div class='ct-pl'><span>Quantidade <b>{float(r['Qtd']):g}</b></span><span>Valor atual <b>{html.escape(va)}</b></span>"
                f"<span>Preço médio <b>{html.escape(pm)}</b></span><span>Preço atual <b>{html.escape(pa)}</b></span>"
                f"<span>Resultado <b>{html.escape(rr)}</b></span><span>Peso <b>{f'{peso:.1f}%'.replace('.', ',') if peso_ok else 'n/d'}</b></span></div>"
                f"<div class='ct-bar'><i style='width:{min(100, max(0, float(peso))) if peso_ok else 0:.0f}%'></i></div></div>")
    return out


def _render(chave: str, ficticia: bool):
    st.session_state.setdefault(chave, [])
    lotes = st.session_state[chave]
    caixa = None
    if ficticia:
        st.markdown("<div class='ct-sec'>Capital inicial da simulação (R$)</div>", unsafe_allow_html=True)
        capital = st.number_input("Capital inicial da simulação (R$)", min_value=1000.0, value=100000.0,
                                  step=1000.0, format="%.2f", key="cart_capital", label_visibility="collapsed")
        gasto = moeda.custo_total_brl(lotes)
        if gasto is None:
            st.warning("Sem a cotação do dólar agora: o caixa não pôde ser calculado com os ativos em US$.")
            gasto = sum(l["qtd"] * l["preco_medio"] for l in lotes if not moeda.eh_dolar(l["ticker"]))
        caixa = capital - gasto
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

    st.markdown(_kpis(custo_total, valor_total, res, res_pct, caixa), unsafe_allow_html=True)

    try:                                                  # leitura em palavras conforme o modo de experiência
        import experiencia_app as _ea
        import leitura as _lt
        _cr = tab.dropna(subset=["Resultado (%)"])
        _mel = _pio = _mai = None
        if len(_cr) >= 2:
            _a, _b = _cr.loc[_cr["Resultado (%)"].idxmax()], _cr.loc[_cr["Resultado (%)"].idxmin()]
            _mel, _pio = (_a["Ativo"], float(_a["Resultado (%)"])), (_b["Ativo"], float(_b["Resultado (%)"]))
        if tab["Peso (%)"].notna().any():
            _c = tab.loc[tab["Peso (%)"].idxmax()]
            _mai = (_c["Ativo"], float(_c["Peso (%)"]))
        _ea.mostrar(_lt.carteira(custo_total, valor_total, res, res_pct, len(tab), _mel, _pio, _mai, ficticia, _ea.modo()))
    except Exception:
        pass
    st.markdown("<div class='ct-sec'>Posições</div>", unsafe_allow_html=True)
    st.markdown(_cartoes_posicoes(tab), unsafe_allow_html=True)
    com_res = tab.dropna(subset=["Resultado (%)"])
    if len(com_res) >= 2:
        melhor, pior = com_res.loc[com_res["Resultado (%)"].idxmax()], com_res.loc[com_res["Resultado (%)"].idxmin()]
        st.markdown(f"<div class='ct-chips'><span class='ct-chip g'>Melhor: {html.escape(str(melhor['Ativo']))} {_pct(melhor['Resultado (%)'])}</span>"
                    f"<span class='ct-chip r'>Pior: {html.escape(str(pior['Ativo']))} {_pct(pior['Resultado (%)'])}</span></div>", unsafe_allow_html=True)

    with st.expander("Gráficos da carteira", icon=":material/insights:"):
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
    st.markdown(tema.cabecalho("💼", "Minha carteira", "Monte uma carteira de teste e acompanhe o desempenho, sem risco."), unsafe_allow_html=True)
    st.markdown(_CSS, unsafe_allow_html=True)
    st.caption("Nada aqui usa dinheiro de verdade. É uma simulação livre e só sua: para competir no ranking, use o Wallet Game.")
    _render("cart_ficticia", ficticia=True)
    st.caption("Ferramenta educacional. Preços do Yahoo Finance, podem ter atraso.")
