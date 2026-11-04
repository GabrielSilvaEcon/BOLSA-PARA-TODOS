"""
Passo 19 — Relatórios inteligentes e dashboard executivo (tela). Os cálculos estão em relatorios.py e relatorios_ia.py (sem Streamlit nem rede);
aqui ficam a leitura da carteira do Passo 12 (gestao_app.ler_carteira), os filtros, os gráficos e as exportações.

Só lê e calcula: nada compra, vende ou altera posição. Persistência (usuarios.CHAVES): rel_fotos (fotografias do histórico) e rel_cfg (filtros e gráficos escolhidos).
Cada pessoa vê apenas a própria carteira (a sessão é dela) e nenhum dado pessoal vai para registros ou exportações além do que está no relatório.
"""
from __future__ import annotations

import logging
from datetime import date, datetime

import numpy as np
import pandas as pd
import streamlit as st

import gestao as g
import relatorios as R
import relatorios_ia as RI
import tema

log = logging.getLogger("relatorios_app")

CH_FOTOS, CH_CFG = "rel_fotos", "rel_cfg"
CTX = "_rel_ctx"
ABAS = ["Painel executivo", "Desempenho", "Alocação", "Por ativo e classe", "Risco", "Histórico", "Qualidade dos dados", "Exportar", "Assistente"]
GRAFICOS = {"evolucao": "Evolução do patrimônio × aportes", "benchmarks": "Carteira × benchmarks (base 100)", "classe": "Distribuição por classe",
            "posicoes": "Maiores posições", "ranking": "Melhores e piores", "aportes": "Aportes e retiradas por mês", "proventos": "Proventos por mês",
            "drawdown": "Queda desde o pico (drawdown)"}
CARTEIRAS = {"cart_real": "Carteira real", "cart_ficticia": "Carteira fictícia"}
# fornecido por app.py: função(chave_classe, id) -> comparador.Ativo | None (mesmo caminho do Comparar, com os indicadores da classe)
PROVEDOR_ATIVO = None


def _ss():
    return st.session_state


def _padrao(chave: str, valor) -> dict:
    return {} if chave in st.session_state else {"value": valor}


def _opt(chave: str, valor) -> dict:
    return {} if chave in st.session_state else {"default": valor}


class _Plotly:
    def __getattr__(self, nome):
        import plotly.graph_objects as _go
        return getattr(_go, nome)


go = _Plotly()


def _cartoes(itens: list, por_linha: int = 4):
    for k in range(0, len(itens), por_linha):
        for col, (rot, val, cls, *det) in zip(st.columns(por_linha), itens[k:k + por_linha]):
            col.markdown(tema.card_status(rot, val, cls, det[0] if det else "", det[1] if len(det) > 1 else ""), unsafe_allow_html=True)


def _grafico(fig, altura: int = 340):
    """Gráfico no padrão visual do app (fundo branco, texto escuro, zoom, dica ao passar o mouse)."""
    fig.update_layout(height=altura, margin=dict(l=10, r=10, t=40, b=10))
    st.plotly_chart(fig, width="stretch", theme=None, config={"displayModeBar": False})


def _cls(v) -> str:
    return "na" if v is None or (isinstance(v, float) and not np.isfinite(v)) else ("good" if v > 0 else ("bad" if v < 0 else "info"))


def tabela(df: pd.DataFrame, chave: str, ganho=(), formatos=None, busca: bool = True, por_pagina=(10, 25, 50), altura: int | None = None):
    """Tabela padrão do app: busca por texto, ordenação (clique no cabeçalho), paginação, formato monetário/percentual e cores de ganho/perda."""
    if df is None or df.empty:
        st.caption("Sem dados para mostrar.")
        return
    x = df
    if busca and len(x) > 8:
        q = st.text_input("Buscar na tabela", key=f"{chave}_busca", placeholder="digite parte do nome", max_chars=60)
        if q and q.strip():
            m = x.astype(str).apply(lambda col: col.str.contains(q.strip(), case=False, regex=False)).any(axis=1)
            x = x[m]
    n = len(x)
    pp = int(st.selectbox("Linhas por página", list(por_pagina), key=f"{chave}_pp")) if n > min(por_pagina) else n
    paginas = max(1, int(np.ceil(n / pp))) if pp else 1
    pg = int(st.number_input("Página", 1, paginas, 1, key=f"{chave}_pg")) if paginas > 1 else 1
    x = x.iloc[(pg - 1) * pp: pg * pp] if paginas > 1 else x
    kw = {"hide_index": True, "width": "stretch"}
    if altura:
        kw["height"] = altura
    st.dataframe(tema.estilizar_tabela(x, ganho=ganho, formatos=formatos), **kw)
    st.caption(f"{n} linha(s)" + (f" · página {pg} de {paginas}" if paginas > 1 else "") + ". Clique no título da coluna para ordenar.")


# =============================================================================== coleta e cálculo
def _ipca_idx() -> pd.Series | None:
    ss = _ss()
    if "_rel_ipca" not in ss:
        try:
            import evolucao
            s = evolucao.coletar_bcb().get("ipca_idx")
            ss["_rel_ipca"] = s if s is not None and len(s) > 1 else None
        except Exception as e:
            log.warning("IPCA indisponível: %s", e)
            ss["_rel_ipca"] = None
    return ss["_rel_ipca"]


def _ler(chave: str):
    try:
        import gestao_app
        return gestao_app.ler_carteira(chave)
    except Exception as e:
        log.exception("falha ao ler a carteira")
        st.error(f"Não consegui ler a carteira agora ({e.__class__.__name__}). Tente de novo em instantes.")
        return None


def _periodo_escolhido(rot: str, D: dict, hoje: date):
    if rot == "Personalizado":
        c1, c2 = st.columns(2)
        a = c1.date_input("De", value=date(hoje.year, 1, 1), key="rel_de", max_value=hoje)
        b = c2.date_input("Até", value=hoje, key="rel_ate", max_value=hoje)
        if a > b:
            st.warning("A data inicial é depois da final: usei o período inteiro.")
            return None, None, "Desde o início"
        return pd.Timestamp(a) - pd.Timedelta(days=1), pd.Timestamp(b), f"{a:%d/%m/%Y} a {b:%d/%m/%Y}"
    m = R.PERIODOS.get(rot)
    vh = D.get("valor_hist")
    fim = pd.Timestamp(vh.index[-1]) if vh is not None and len(vh) else pd.Timestamp(hoje)
    return R._inicio(m, fim), None, rot


def _filtros(C: dict) -> dict:
    pos = R.validas(C.get("posicoes") or [])
    opc = lambda campo: sorted({(p.get(campo) or "Não informado") for p in pos})  # noqa: E731
    cfg = _ss().get(CH_CFG) or {}
    with st.expander("Filtros e indicadores", expanded=False):
        c1, c2, c3 = st.columns(3)
        cl = c1.multiselect("Classe", [g.CLASSES.get(x, x) for x in opc("classe")], key="rel_f_classe")
        inv = {v: k for k, v in g.CLASSES.items()}
        se = c2.multiselect("Setor", opc("setor"), key="rel_f_setor")
        pa = c3.multiselect("País", opc("pais"), key="rel_f_pais")
        c4, c5, c6 = st.columns(3)
        mo = c4.multiselect("Moeda", opc("moeda"), key="rel_f_moeda")
        at = c5.multiselect("Ativo", [p["id"] for p in pos], key="rel_f_ativo")
        insts = sorted({(p.get("instituicao") or p.get("custodiante") or "Não informado") for p in pos})
        ins = c6.multiselect("Conta / instituição", insts, key="rel_f_inst") if len(insts) > 1 else []
        if len(insts) <= 1:
            c6.caption("Conta/instituição: o app ainda não tem esse dado cadastrado nos lançamentos.")
        gr = st.multiselect("Gráficos do painel", list(GRAFICOS), format_func=GRAFICOS.get, key="rel_graficos", **_opt("rel_graficos", cfg.get("graficos") or ["evolucao", "classe", "posicoes", "benchmarks"]))
    return {"classes": [inv.get(x, x) for x in cl], "setores": se, "paises": pa, "moedas": mo, "ativos": at, "instituicoes": ins, "_graficos": gr}


def preparar() -> dict | None:
    """Lê a carteira, aplica filtros e período, calcula tudo e guarda o resultado na sessão (para a IA e as exportações)."""
    ss = _ss()
    c1, c2 = st.columns([2, 2])
    chave = c1.radio("Carteira", list(CARTEIRAS), format_func=CARTEIRAS.get, horizontal=True, key="rel_cart")
    rot = c2.selectbox("Período", list(R.PERIODOS) + ["Personalizado"], index=5, key="rel_periodo")
    with st.spinner("Lendo a carteira..."):
        lido = _ler(chave)
    if lido is None:
        st.markdown(tema.vazio("carteira", "Nenhuma posição nesta carteira", "Cadastre ativos na página Carteira, ou escolha a outra carteira, para ver os relatórios."), unsafe_allow_html=True)
        ss.pop(CTX, None)
        return None
    C, D = lido
    f = _filtros(C)
    graficos = f.pop("_graficos")
    ini, fim, rotulo = _periodo_escolhido(rot, D, C.get("hoje") or date.today())
    X = R.calcular(C, D, f, ini, fim, _ipca_idx(), rotulo, CARTEIRAS[chave])
    X["chave"], X["C"], X["D"], X["graficos_sel"] = chave, C, D, graficos
    ss[CH_CFG] = {**(ss.get(CH_CFG) or {}), "graficos": graficos}
    ss[CTX] = X
    return X


# =============================================================================== gráficos
def _g_evolucao(X):
    cv = X["curva"]
    if len(cv) < 3:
        st.caption("Evolução: precisa de histórico de preços da carteira.")
        return
    fig = go.Figure()
    fig.add_scatter(x=cv["data"], y=cv["patrimonio"], name="Patrimônio de mercado", line=dict(color="#2563EB", width=2.5), hovertemplate="R$ %{y:,.2f}")
    fig.add_scatter(x=cv["data"], y=cv["aportes_acum"], name="Aportes líquidos acumulados", line=dict(color="#64748B", dash="dot"), hovertemplate="R$ %{y:,.2f}")
    i_max, i_min = cv["patrimonio"].idxmax(), cv["patrimonio"].idxmin()
    fig.add_scatter(x=[cv["data"][i_max], cv["data"][i_min]], y=[cv["patrimonio"][i_max], cv["patrimonio"][i_min]], mode="markers+text", name="Máximo / mínimo",
                    text=["máx.", "mín."], textposition="top center", marker=dict(size=9, color=["#1F7A55", "#B83A3A"]), hoverinfo="skip")
    fig.update_layout(title="Evolução do patrimônio × aportes (histórico realizado)")
    _grafico(fig)
    st.caption("A distância entre as linhas é o resultado dos investimentos; a linha pontilhada é só dinheiro que você colocou. Não há projeção neste gráfico.")


def _g_benchmarks(X):
    r, idx = X["desemp"], X["indice"]
    if not r.get("ok") or idx is None or len(idx) < 3:
        st.caption("Comparação com benchmarks: precisa de histórico.")
        return
    fig = go.Figure()
    base = pd.Series(100 * idx.values, index=idx.index)
    fig.add_scatter(x=base.index, y=base.values, name="Carteira (TWR)", line=dict(color="#2563EB", width=3), hovertemplate="%{y:.1f}")
    ini = pd.Timestamp(r["inicio"])
    for k, s in (X["refs"] or {}).items():
        try:
            x = s.dropna()
            x.index = pd.DatetimeIndex(x.index).tz_localize(None) if pd.DatetimeIndex(x.index).tz is not None else pd.DatetimeIndex(x.index)
            x = x.loc[ini - pd.Timedelta(days=5):]
            if len(x) > 2 and x.index[0] <= ini + pd.Timedelta(days=5):
                fig.add_scatter(x=x.index, y=100 * x / float(x.iloc[0]), name=k, line=dict(width=1.6), hovertemplate="%{y:.1f}")
        except Exception:
            continue
    fig.update_layout(title="Carteira × benchmarks (base 100 no início do período)")
    _grafico(fig)
    st.caption("A carteira é medida por TWR (aportes não contam como lucro). Cada benchmark só aparece se tem dados desde o início do período.")


def _g_classe(X):
    d = X["dist"]["classe"]
    if d.empty:
        return
    fig = go.Figure(go.Pie(labels=[g.CLASSES.get(n, n) for n in d["nome"]], values=d["valor"], hole=0.55, textinfo="label+percent", sort=False))
    fig.update_layout(title="Distribuição por classe", showlegend=False)
    _grafico(fig, 320)


def _g_posicoes(X):
    t = X["tabela_posicoes"].head(10)
    if t.empty:
        return
    fig = go.Figure(go.Bar(x=t["Peso"][::-1] * 100, y=t["Ativo"][::-1], orientation="h", marker_color="#2563EB", text=[f"{v * 100:.1f}%" for v in t["Peso"][::-1]], textposition="outside",
                           hovertemplate="%{y}: %{x:.1f}%<extra></extra>"))
    fig.update_layout(title="Maiores posições (% do patrimônio)", xaxis_title="% da carteira")
    _grafico(fig, 340)


def _g_ranking(X):
    rk = X["ranking"]
    itens = rk["melhores"][:5] + [x for x in rk["piores"][:5] if x not in rk["melhores"][:5]]
    if not itens:
        st.caption("Melhores e piores: nenhuma posição com custo informado.")
        return
    itens = sorted(itens, key=lambda x: x[1])
    fig = go.Figure(go.Bar(x=[x[1] * 100 for x in itens], y=[x[0] for x in itens], orientation="h", marker_color=[("#1F7A55" if x[1] >= 0 else "#B83A3A") for x in itens],
                           hovertemplate="%{y}: %{x:+.1f}%<extra></extra>"))
    fig.update_layout(title="Melhores e piores (resultado sobre o custo, %)", xaxis_title="%")
    _grafico(fig, 320)


def _g_aportes(X):
    a = X["aportes_mes"]
    if a.empty:
        st.caption("Aportes e retiradas: nenhum lançamento no período.")
        return
    fig = go.Figure()
    fig.add_bar(x=a["mes"], y=a["aportes"], name="Aportes", marker_color="#2563EB")
    fig.add_bar(x=a["mes"], y=-a["retiradas"], name="Retiradas", marker_color="#F59E0B")
    fig.update_layout(title="Aportes e retiradas por mês (R$)", barmode="relative")
    _grafico(fig, 300)


def _g_proventos(X):
    r = X["rend_mes"]
    if r.empty:
        st.caption("Proventos: nenhum registro no período.")
        return
    fig = go.Figure()
    for k, df in r.groupby("tipo"):
        fig.add_bar(x=df["mes"], y=df["valor"], name=str(k).replace("_", " "))
    fig.update_layout(title="Proventos por mês (R$)", barmode="stack")
    _grafico(fig, 300)


def _g_drawdown(X):
    s = X["risco"].get("dd_serie")
    if s is None or len(s) < 3:
        st.caption("Drawdown: precisa de histórico.")
        return
    fig = go.Figure(go.Scatter(x=s.index, y=s.values * 100, fill="tozeroy", line=dict(color="#B83A3A"), name="Queda desde o pico", hovertemplate="%{y:.1f}%"))
    fig.update_layout(title="Queda desde o pico (%)", yaxis_title="%")
    _grafico(fig, 280)


_FUNCS = {"evolucao": _g_evolucao, "benchmarks": _g_benchmarks, "classe": _g_classe, "posicoes": _g_posicoes, "ranking": _g_ranking,
          "aportes": _g_aportes, "proventos": _g_proventos, "drawdown": _g_drawdown}


# =============================================================================== abas
def _aba_painel(X):
    r, d = X["resumo"], X["desemp"]
    st.markdown(f"##### {X['identificacao']} · {X['periodo']}")
    if X["filtros"]:
        st.caption("Filtros ativos: " + "; ".join(f"{k}: {', '.join(v)}" for k, v in X["filtros"].items()))
    _cartoes([("Patrimônio total", R.brl(r["patrimonio"]), "info", f"{r['n_posicoes']} posições"),
              ("Total investido (custo)", R.brl(r["investido"]), "info" if r["investido"] is not None else "na", "só posições com custo informado"),
              ("Ganho / perda não realizado", R.brl(r["ganho"]), _cls(r["ganho"]), R.pct(r["ganho_pct"], 2, True)),
              ("Proventos recebidos", R.brl(r["proventos"]), "good" if r["proventos"] else "na", "dividendos, rendimentos e juros")])
    if d.get("ok"):
        _cartoes([("Rentabilidade (TWR)", R.pct(d["twr"], 2, True), _cls(d["twr"]), f"{d['inicio']:%d/%m/%Y} a {d['fim']:%d/%m/%Y}"),
                  ("MWR (XIRR) a.a.", R.pct(d["mwr_aa"], 2, True) if d.get("mwr_aa") is not None else "n/d", _cls(d.get("mwr_aa")), d.get("motivo_mwr") or "considera quando cada aporte entrou"),
                  ("Aportes líquidos", R.brl(d["aportes_liquidos"]), "info", "aportes − retiradas; não é lucro"),
                  ("Resultado dos investimentos", R.brl(d["resultado_investimentos"]), _cls(d["resultado_investimentos"]), "crescimento − aportes líquidos")])
        if X.get("retorno_real") is not None:
            st.caption(f"Retorno real (acima da inflação, IPCA) no período: {R.pct(X['retorno_real'], 2, True)}; nominal {R.pct(d['twr'], 2, True)}.")
    else:
        st.info(f"Rentabilidade não calculada: {d.get('motivo', 'sem histórico')}.")
    graf = X["graficos_sel"]
    cols = st.columns(2)
    for k, gid in enumerate(graf):
        with cols[k % 2]:
            try:
                _FUNCS[gid](X)
            except Exception as e:
                log.exception("gráfico falhou")
                st.warning(f"O gráfico “{GRAFICOS[gid]}” falhou ({e.__class__.__name__}).")
    if not graf:
        st.caption("Escolha gráficos em “Filtros e indicadores”.")
    st.markdown("##### Posições")
    t = X["tabela_posicoes"]
    tabela(t, "rel_pos", ganho=["Resultado (R$)", "Resultado (%)"],
           formatos={"Valor (R$)": "R$ {:,.2f}", "Custo (R$)": "R$ {:,.2f}", "Resultado (R$)": "R$ {:+,.2f}", "Peso": "{:.1%}", "Resultado (%)": "{:+.2%}"})
    for z in X["qualidade"][:3]:
        if z["nivel"] in ("alto", "medio"):
            st.warning(z["texto"])


def _aba_desempenho(X):
    st.markdown("##### Rentabilidade por período")
    t = X["tabela_periodos"]
    if t.empty:
        st.info("Sem histórico de preços suficiente. A rentabilidade só é calculada com dados reais; nada é estimado.")
    else:
        fm = {c: "{:+.2%}" for c in t.columns if c not in ("Período", "vs CDI (p.p.)")}
        fm["vs CDI (p.p.)"] = "{:+.2f}"
        tabela(t, "rel_per", ganho=list(fm), formatos=fm, busca=False)
        st.caption("TWR: retorno ponderado pelo tempo, aporte e retirada não contam. MWR: retorno do dinheiro (XIRR), anualizado, só com 90+ dias. "
                   "“n/d” = a série não cobre o período inteiro. Retornos brutos de impostos.")
    d = X["desemp"]
    if d.get("ok"):
        st.markdown("##### De onde veio o crescimento")
        _cartoes([("Valor no início", R.brl(d["valor_inicial"]), "info"), ("Aportes líquidos", R.brl(d["aportes_liquidos"]), "info", "dinheiro que entrou"),
                  ("Resultado dos investimentos", R.brl(d["resultado_investimentos"]), _cls(d["resultado_investimentos"]), "valorização do que você tinha"),
                  ("Valor no fim", R.brl(d["valor_final"]), "info", f"inclui {R.brl(d['proventos'])} de proventos pagos no período" if d["proventos"] else "")])
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Retorno por classe (preço, ponderado pelo valor)**")
        pc = X["por_classe"]
        if pc.empty:
            st.caption("Sem ativos com histórico para este período.")
        else:
            fig = go.Figure(go.Bar(x=pc["Classe"], y=pc["Retorno"] * 100, marker_color=["#1F7A55" if v >= 0 else "#B83A3A" for v in pc["Retorno"]], hovertemplate="%{x}: %{y:+.1f}%<extra></extra>"))
            fig.update_layout(yaxis_title="%")
            _grafico(fig, 280)
    with c2:
        st.markdown("**Retorno por ativo (preço)**")
        pa = X["por_ativo"].dropna(subset=["Retorno"]) if len(X["por_ativo"]) else X["por_ativo"]
        if pa.empty:
            st.caption("Sem ativos com histórico para este período.")
        else:
            tabela(pa.assign(Retorno=pa["Retorno"]), "rel_pa", ganho=["Retorno"], formatos={"Retorno": "{:+.2%}", "Valor": "R$ {:,.2f}"}, busca=False)
    m = R.retornos_mensais_carteira(X["retornos"])
    if len(m):
        fig = go.Figure(go.Bar(x=m.index, y=m.values * 100, marker_color=["#1F7A55" if v >= 0 else "#B83A3A" for v in m.values], hovertemplate="%{x|%m/%Y}: %{y:+.2f}%<extra></extra>"))
        fig.update_layout(title="Retorno mensal da carteira (TWR, %)")
        _grafico(fig, 280)


def _aba_alocacao(X):
    campos = {"classe": "Classe", "setor": "Setor", "pais": "País", "moeda": "Moeda"}
    sel = st.radio("Agrupar por", list(campos), format_func=campos.get, horizontal=True, key="rel_aloc")
    d = X["dist"][sel]
    if d.empty:
        st.caption("Sem dados.")
        return
    nomes = [g.CLASSES.get(n, n) if sel == "classe" else n for n in d["nome"]]
    c1, c2 = st.columns([1, 1])
    with c1:
        fig = go.Figure(go.Pie(labels=nomes, values=d["valor"], hole=0.55, textinfo="label+percent", sort=False))
        fig.update_layout(title=f"Por {campos[sel].lower()}", showlegend=False)
        _grafico(fig, 340)
    with c2:
        tabela(pd.DataFrame({campos[sel]: nomes, "Valor (R$)": d["valor"].values, "Peso": d["pct"].values}), "rel_aloc_t", formatos={"Valor (R$)": "R$ {:,.2f}", "Peso": "{:.1%}"}, busca=False)
    c = X["conc"]
    if c.get("ok"):
        st.markdown("##### Concentração")
        _cartoes([("Maior posição", R.pct(c["top1"], 1), "info"), ("3 maiores", R.pct(c["top3"], 1), "info"), ("5 maiores", R.pct(c["top5"], 1), "info"),
                  ("Nº efetivo de posições", f"{c['n_efetivo']:.1f}".replace(".", ","), "info", f"HHI {c['hhi']:.3f}".replace(".", ","))])
    for a in X["alertas_conc"][:6]:
        st.warning(a["texto"])
    st.caption("Concentração é descrição da carteira; os limites usados são referências editáveis na página Gestão de risco, não regras do mercado.")


def _indicadores_posicao(p: dict) -> pd.DataFrame:
    linhas = [("Valor atual", R.brl(p.get("valor"))), ("Quantidade", "n/d" if not R._ok(p.get("qtd")) else f"{p['qtd']:,.4f}".replace(",", "X").replace(".", ",").replace("X", ".")),
              ("Custo", R.brl(p.get("custo")) if R._ok(p.get("custo")) and p["custo"] > 0 else "n/d")]
    if R._ok(p.get("custo")) and p["custo"] > 0 and R._ok(p.get("valor")):
        linhas.append(("Resultado", f"{R.brl(p['valor'] - p['custo'])} ({R.pct(p['valor'] / p['custo'] - 1, 2, True)})"))
    for k, rot in (("indexador", "Indexador"), ("duracao", "Duração (anos)"), ("aplicacao", "Data da aplicação"), ("vencimento", "Vencimento"), ("emissor", "Emissor"), ("gestor", "Gestor")):
        if p.get(k) not in (None, ""):
            linhas.append((rot, str(p[k])))
    linhas.append(("Fonte", p.get("fonte") or "n/d"))
    linhas.append(("Data do preço", p["data_preco"].strftime("%d/%m/%Y") if hasattr(p.get("data_preco"), "strftime") else "n/d"))
    return pd.DataFrame(linhas, columns=["Item", "Valor"])


def _aba_ativo(X):
    pos = R.validas(X["posicoes"])
    if not pos:
        st.caption("Sem posições na seleção.")
        return
    classes = sorted({p["classe"] for p in pos})
    cl = st.selectbox("Classe", ["Todas"] + classes, format_func=lambda x: x if x == "Todas" else g.CLASSES.get(x, x), key="rel_cl")
    sub = [p for p in pos if cl == "Todas" or p["classe"] == cl]
    sm = R.resumo(sub, [e for e in (X["C"].get("eventos") or []) if e.get("fonte") in {p["id"] for p in sub}])
    _cartoes([("Valor da seleção", R.brl(sm["patrimonio"]), "info", f"{len(sub)} ativos"), ("Ganho não realizado", R.brl(sm["ganho"]), _cls(sm["ganho"]), R.pct(sm["ganho_pct"], 2, True)),
              ("Proventos", R.brl(sm["proventos"]), "good" if sm["proventos"] else "na"), ("Peso na carteira", R.pct(sm["patrimonio"] / X["resumo"]["patrimonio"], 1) if X["resumo"]["patrimonio"] else "n/d", "info")])
    tabela(R.tabela_posicoes(sub), "rel_cl_t", ganho=["Resultado (R$)", "Resultado (%)"],
           formatos={"Valor (R$)": "R$ {:,.2f}", "Custo (R$)": "R$ {:,.2f}", "Resultado (R$)": "R$ {:+,.2f}", "Peso": "{:.1%}", "Resultado (%)": "{:+.2%}"})
    st.markdown("##### Relatório individual")
    ids = [p["id"] for p in sub]
    a = st.selectbox("Ativo", ids, key="rel_at")
    p = next(x for x in sub if x["id"] == a)
    st.markdown(f"**{p.get('nome') or a}** · {g.CLASSES.get(p['classe'], p['classe'])} · {p.get('setor') or 'Não informado'}")
    tabela(_indicadores_posicao(p), "rel_ind_pos", busca=False)
    if p["classe"] in ("renda_fixa", "fundo", "caixa"):
        st.caption("Para renda fixa e fundos, o relatório usa os dados da própria aplicação (indexador, vencimento, custo). Indicadores de mercado como P/L não se aplicam.")
        return
    if PROVEDOR_ATIVO is None:
        st.caption("Indicadores da classe disponíveis na página Comparar ativos.")
        return
    if st.button("Carregar indicadores da classe (fundamentos, valuation, risco)", key="rel_btn_ind"):
        with st.spinner("Buscando os indicadores..."):
            try:
                _ss()["_rel_ind_" + a] = PROVEDOR_ATIVO(p["classe"], a)
            except Exception as e:
                log.exception("indicadores falharam")
                _ss()["_rel_ind_" + a] = None
                st.warning(f"Não consegui os indicadores agora ({e.__class__.__name__}).")
    at = _ss().get("_rel_ind_" + a)
    if at is not None:
        ls = R.linhas_ativo(at)
        if ls:
            tabela(pd.DataFrame(ls), "rel_ind_cl", busca=False)
            st.caption("Só aparecem os indicadores que pertencem à classe do ativo, com a origem (dado da fonte, calculado ou estimativa) e a data.")


def _aba_risco(X):
    ri = X["risco"]
    fmt = lambda v, p=True: "n/d" if v is None else (R.pct(v, 2) if p else f"{v:.2f}".replace(".", ","))  # noqa: E731
    _cartoes([("Volatilidade anual", fmt(ri.get("vol")), "info" if ri.get("vol") is not None else "na", ri["motivos"].get("vol", "desvio dos retornos diários")),
              ("Maior queda (drawdown)", fmt(ri.get("mdd")), "bad" if ri.get("mdd") is not None else "na", ri["motivos"].get("mdd", "do pico ao vale")),
              ("Sharpe", fmt(ri.get("sharpe"), False), "info" if ri.get("sharpe") is not None else "na", ri["motivos"].get("sharpe", "contra o CDI")),
              ("Sortino", fmt(ri.get("sortino"), False), "info" if ri.get("sortino") is not None else "na", ri["motivos"].get("sortino", "só queda conta como risco"))])
    _cartoes([("VaR 95% (1 dia)", fmt(ri.get("var95")), "info" if ri.get("var95") is not None else "na", ri["motivos"].get("var95", "perda não excedida em 95% dos dias")),
              ("CVaR 95% (1 dia)", fmt(ri.get("cvar95")), "info" if ri.get("cvar95") is not None else "na", ri["motivos"].get("cvar95", "média dos piores dias")),
              ("Queda atual", fmt(ri.get("dd_atual")), "info" if ri.get("dd_atual") is not None else "na"), ("Dias de retorno", str(ri["n_dias"]), "info")])
    _g_drawdown(X)
    D = X["D"]
    ids = [p["id"] for p in R.validas(X["posicoes"])]
    rets = D.get("rets")
    cols = [c for c in (rets.columns if rets is not None else []) if c in ids]
    if len(cols) >= 2:
        corr = rets[cols].corr()
        fig = go.Figure(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index), zmin=-1, zmax=1, colorscale="RdBu_r", text=np.round(corr.values, 2), texttemplate="%{text}"))
        fig.update_layout(title="Correlação entre os ativos (retornos diários)")
        _grafico(fig, 380)
    else:
        st.caption("Correlação: precisa de 2+ ativos com 60+ dias de histórico.")
    st.info("Liquidez, estresse por cenário, limites e alertas completos estão na página Gestão de risco (Passo 16). Os números acima usam o mesmo cálculo de risco da carteira.")
    if X["nao_calc"]:
        st.markdown("##### Indicadores que não puderam ser calculados")
        for k, v in X["nao_calc"].items():
            st.markdown(f"- **{k}**: {v}")


def _aba_historico(X):
    ss = _ss()
    fotos = [f for f in (ss.get(CH_FOTOS) or []) if f.get("carteira") == X["chave"]]
    st.caption("Uma fotografia guarda o estado da carteira hoje (valores, classes, qualidade dos dados). Assim você compara períodos sem recalcular o passado. "
               "Fotografias antigas nunca são apagadas em silêncio.")
    if st.button("Salvar fotografia de hoje", key="rel_foto"):
        nova = R.fotografia(X["chave"], X["C"], X["D"], X["quando"], X["desemp"], X["qualidade"])
        ss[CH_FOTOS], msg = R.guardar_fotografia(list(ss.get(CH_FOTOS) or []), nova)
        st.success(msg)
        fotos = [f for f in ss[CH_FOTOS] if f.get("carteira") == X["chave"]]
    ativas = sorted([f for f in fotos if not f.get("substituida_por")], key=lambda f: f["gerado_em"])
    if not ativas:
        st.markdown(tema.vazio("grafico", "Nenhuma fotografia ainda", "Salve a primeira para começar o histórico."), unsafe_allow_html=True)
        return
    df = pd.DataFrame([{"Data": f["data"], "Patrimônio": f["patrimonio"], "Investido": f["investido"], "Ganho": f["ganho"], "Proventos": f["proventos"],
                        "TWR acumulado": f.get("twr_total"), "Posições": f["n_posicoes"], "Alertas de dados": f["qualidade"]["alto"] + f["qualidade"]["medio"]} for f in ativas])
    if len(df) >= 2:
        fig = go.Figure(go.Scatter(x=df["Data"], y=df["Patrimônio"], mode="lines+markers", line=dict(color="#2563EB"), hovertemplate="R$ %{y:,.2f}"))
        fig.update_layout(title="Patrimônio nas fotografias")
        _grafico(fig, 280)
    tabela(df, "rel_hist", ganho=["Ganho"], formatos={"Patrimônio": "R$ {:,.2f}", "Investido": "R$ {:,.2f}", "Ganho": "R$ {:+,.2f}", "Proventos": "R$ {:,.2f}", "TWR acumulado": "{:+.2%}"}, busca=False)
    if len(ativas) >= 2:
        datas = [f["data"] for f in ativas]
        c1, c2 = st.columns(2)
        a = c1.selectbox("De", datas[:-1], index=0, key="rel_cmp_a")
        b = c2.selectbox("Até", datas[1:], index=len(datas) - 2, key="rel_cmp_b")
        fa, fb = next(f for f in ativas if f["data"] == a), next(f for f in ativas if f["data"] == b)
        if fa["data"] >= fb["data"]:
            st.warning("Escolha uma data inicial anterior à final.")
        else:
            cmp_ = R.comparar_fotografias(fa, fb)
            ss["_rel_cmp"] = cmp_
            _cartoes([("Dias", str(cmp_["dias"]), "info"), ("Variação do patrimônio", R.brl(cmp_["dif_patrimonio"]), _cls(cmp_["dif_patrimonio"]), "inclui aportes: não é rentabilidade"),
                      ("Variação do investido", R.brl(cmp_["dif_investido"]), "info"), ("Variação do TWR acumulado", R.pct(cmp_["dif_twr"], 2, True), _cls(cmp_["dif_twr"]))])
            if cmp_["novos"] or cmp_["saiu"]:
                st.caption(("Entraram: " + ", ".join(cmp_["novos"]) + ". ") * bool(cmp_["novos"]) + ("Saíram: " + ", ".join(cmp_["saiu"]) + ".") * bool(cmp_["saiu"]))
            tabela(pd.DataFrame(cmp_["classes"]).rename(columns={"classe": "Classe", "antes": "Antes", "depois": "Depois"}), "rel_cmp_t", formatos={"Antes": "R$ {:,.2f}", "Depois": "R$ {:,.2f}"}, busca=False)
    ant = [f for f in fotos if f.get("substituida_por")]
    if ant:
        with st.expander(f"Histórico de alterações ({len(ant)} fotografia(s) substituída(s))"):
            tabela(pd.DataFrame([{"Data": f["data"], "Gerada em": f["gerado_em"], "Substituída em": f["substituida_por"], "Patrimônio": f["patrimonio"]} for f in ant]), "rel_hist_ant",
                   formatos={"Patrimônio": "R$ {:,.2f}"}, busca=False)


def _aba_qualidade(X):
    q = X["qualidade"]
    n_a, n_m = sum(1 for z in q if z["nivel"] == "alto"), sum(1 for z in q if z["nivel"] == "medio")
    _cartoes([("Problemas graves", str(n_a), "bad" if n_a else "good"), ("Atenção", str(n_m), "fair" if n_m else "good"),
              ("Informativos", str(len(q) - n_a - n_m), "info"), ("Dados de", X["C"]["hoje"].strftime("%d/%m/%Y") if hasattr(X["C"].get("hoje"), "strftime") else "n/d", "info", "data da coleta")])
    if q:
        tabela(pd.DataFrame([{"Nível": z["nivel"], "Tipo": z["tipo"], "O que houve": z["texto"]} for z in q]), "rel_q", busca=False)
    else:
        st.success("Nenhum problema de qualidade encontrado.")
    st.markdown("##### Origem e atualização de cada posição")
    linhas = []
    hoje = X["C"].get("hoje") or date.today()
    for p in R.validas(X["posicoes"]):
        dp = R._d(p.get("data_preco"))
        linhas.append({"Ativo": p["id"], "Fonte": p.get("fonte") or "n/d", "Preço de": dp.strftime("%d/%m/%Y") if dp else "n/d", "Defasagem (dias)": (hoje - dp).days if dp else None})
    tabela(pd.DataFrame(linhas), "rel_orig", busca=False)
    if X["nao_calc"]:
        st.markdown("##### Indicadores que não puderam ser calculados")
        for k, v in X["nao_calc"].items():
            st.markdown(f"- **{k}**: {v}")


def _aba_exportar(X):
    disp = R.disponibilidade_exportacao()
    nomes = {"resumo": "Resumo executivo", "desempenho": "Rentabilidade por período", "posicoes": "Posições", "alocacao": "Alocação", "risco": "Risco e concentração", "qualidade": "Qualidade dos dados"}
    sel = st.multiselect("O que incluir", list(nomes), format_func=nomes.get, key="rel_ex_sel", **_opt("rel_ex_sel", list(nomes)))
    if not sel:
        st.info("Escolha ao menos uma seção.")
        return
    doc, graficos, numericas = R.documento_da_carteira(X, sel)
    carimbo = X["quando"].strftime("%Y%m%d_%H%M")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.markdown("**PDF**")
        if disp["pdf"]:
            if st.button("Gerar PDF", key="rel_b_pdf"):
                try:
                    _ss()["_rel_pdf"] = R.pdf_bytes(doc, graficos)
                except Exception as e:
                    log.exception("pdf falhou")
                    st.error(f"Não consegui gerar o PDF ({e.__class__.__name__}). Use o Excel ou o CSV.")
            if _ss().get("_rel_pdf"):
                st.download_button("Baixar PDF", _ss()["_rel_pdf"], f"relatorio_carteira_{carimbo}.pdf", "application/pdf", key="rel_d_pdf")
        else:
            st.caption("PDF indisponível neste ambiente (falta a biblioteca reportlab).")
    with c2:
        st.markdown("**Excel**")
        if disp["excel"]:
            if st.button("Gerar Excel", key="rel_b_xls"):
                try:
                    _ss()["_rel_xls"] = R.excel_bytes(doc, numericas)
                except Exception as e:
                    log.exception("excel falhou")
                    st.error(f"Não consegui gerar o Excel ({e.__class__.__name__}). Use o CSV.")
            if _ss().get("_rel_xls"):
                st.download_button("Baixar Excel", _ss()["_rel_xls"], f"relatorio_carteira_{carimbo}.xlsx",
                                   "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key="rel_d_xls")
        else:
            st.caption("Excel indisponível neste ambiente (falta a biblioteca openpyxl).")
    with c3:
        st.markdown("**CSV (posições)**")
        st.download_button("Baixar CSV", R.csv_bytes(X["tabela_posicoes"]), f"posicoes_{carimbo}.csv", "text/csv", key="rel_d_csv")
        st.caption("Separador “;” e vírgula decimal: abre direto no Excel brasileiro.")
    st.caption("Os arquivos trazem data e hora, período, filtros, indicadores, fontes e avisos de dados. Dados pessoais além da própria carteira não são incluídos. " + R.AVISO)
    if "_rel_pdf" in _ss() or "_rel_xls" in _ss():
        st.caption("Mudou filtro ou período? Gere o arquivo de novo para refletir a seleção atual.")


def contexto_ia() -> dict | None:
    """Resultados já calculados, para o assistente (Passo 13). Só leitura."""
    X = _ss().get(CTX)
    if not X:
        return None
    fotos = _ss().get("_rel_cmp")
    return {"gerado_em": X["quando"].isoformat(timespec="seconds"), "carteira": X["identificacao"], "periodo": X["periodo"], "resumo": X["resumo"], "desemp": {k: v for k, v in X["desemp"].items() if k != "indice"},
            "periodos": X["tabela_periodos"].to_dict("records") if len(X["tabela_periodos"]) else [],
            "classes": [{"nome": g.CLASSES.get(r.nome, r.nome), "valor": r.valor, "pct": r.pct} for r in X["dist"]["classe"].itertuples()],
            "ativos": [{"nome": r["Ativo"], "valor": r["Valor (R$)"], "pct": r["Peso"]} for r in X["tabela_posicoes"].head(8).to_dict("records")],
            "ranking": X["ranking"], "qualidade": X["qualidade"], "nao_calc": X["nao_calc"], "risco": {k: v for k, v in X["risco"].items() if k != "dd_serie"},
            "concentracao": X["conc"], "fontes": X["fontes"], "fotos": fotos}


def _aba_assistente(X):
    st.markdown("##### Assistente dos relatórios")
    st.caption("Explica os números destes relatórios, separando dado, estimativa e hipótese. Não indica compra ou venda.")
    ctx = contexto_ia()
    exemplos = ["Resuma minha carteira", "Explique meus ganhos e perdas", "Compare com o CDI", "Como está a concentração?", "Quais dados estão com problema?", "O que mudou desde a última fotografia?"]
    cols = st.columns(3)
    for k, e in enumerate(exemplos):
        if cols[k % 3].button(e, key=f"rel_ex_{k}"):
            _ss()["rel_q"] = e
    q = st.text_input("Pergunte sobre o relatório", key="rel_q", max_chars=300, placeholder="Ex.: o que explica o meu resultado?")
    if q and q.strip():
        r = RI.responder_relatorio(q.strip(), ctx)
        st.markdown(f"**{r['texto']}**")
        for l in r["linhas"]:
            st.markdown(f"- {l}")
        st.caption(f"{r['referencia']} · {r['consultado']}" + (f" · Fontes: {', '.join(r['fontes'])}" if r["fontes"] else ""))
        st.caption(r["limite"])


# =============================================================================== página
def pagina_relatorios():
    st.markdown(tema.cabecalho("grafico", "Relatórios e dashboard", "Visão executiva da carteira, rentabilidade correta (aporte não é lucro), risco, qualidade dos dados e exportação em PDF, Excel e CSV."),
                unsafe_allow_html=True)
    st.caption(R.AVISO)
    X = preparar()
    if X is None:
        return
    tabs = st.tabs(ABAS)
    fs = [_aba_painel, _aba_desempenho, _aba_alocacao, _aba_ativo, _aba_risco, _aba_historico, _aba_qualidade, _aba_exportar, _aba_assistente]
    for t, f in zip(tabs, fs):
        with t:
            try:
                f(X)
            except Exception as e:
                log.exception("falha na aba de relatórios")
                st.error(f"Esta aba falhou ({e.__class__.__name__}). Os outros relatórios continuam disponíveis; o problema foi registrado.")
