"""
Passo 16 — Página de Risco (tela + coleta). O cálculo está em risco.py (sem Streamlit nem rede); aqui ficam a leitura da carteira do Passo 12,
o histórico de preços/volume (Yahoo), o cache e as 12 abas. Nada compra, vende ou altera posição: só lê e calcula.

Persistência (usuarios.CHAVES): risco_limites (limites escolhidos), risco_regras (regras de alerta), risco_hist (alertas já mostrados),
risco_notas (histórico das classificações), risco_cfg (custodiante, prazo de resgate e cenário personalizado).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime

import numpy as np
import pandas as pd
import streamlit as st

import analise_tecnica as T
import gestao as g
import intel as I
import risco as R
import tema
from renda_fixa_app import _n, _p, _r as _brl

log = logging.getLogger("risco_app")

CH_LIM, CH_REGRAS, CH_HIST, CH_NOTAS, CH_CFG = "risco_limites", "risco_regras", "risco_hist", "risco_notas", "risco_cfg"
RES = "_risco_coleta"          # coleta em memória (não é gravada)
ALERTAS = "_risco_alertas"
PERIODOS = {"6 meses": 190, "12 meses": 370, "2 anos": 740, "Máximo disponível": 0}
ABAS = ["Painel", "Ativos", "Volatilidade", "Indicadores", "Concentração", "Correlação", "Liquidez", "Estresse", "Limites e alertas", "Posição", "Metodologia", "Assistente"]
FREQ_ROT = {"cada_atualizacao": "a cada atualização", "diaria": "1× por dia", "semanal": "1× por semana"}
COR_NIVEL = {"Muito baixo": "good", "Baixo": "good", "Moderado": "fair", "Alto": "bad", "Muito alto": "bad", "Indeterminado": "na", "Sem medida": "na"}
TRANSP = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=40, b=10))


class _Plotly:
    def __getattr__(self, nome):
        import plotly.graph_objects as _go
        return getattr(_go, nome)


go = _Plotly()


def _ss():
    return st.session_state


def _opt(chave: str, nome: str, valor) -> dict:
    return {} if chave in st.session_state else {nome: valor}


def _cartoes(itens: list, por_linha: int = 4):
    for k in range(0, len(itens), por_linha):
        for col, (rot, val, cls, *det) in zip(st.columns(por_linha), itens[k:k + por_linha]):
            col.markdown(tema.card_status(rot, val, cls, det[0] if det else "", det[1] if len(det) > 1 else ""), unsafe_allow_html=True)


def _grafico(fig, altura: int = 320):
    fig.update_layout(height=altura, **TRANSP)
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


def _md(t) -> str:
    return I.escapar_md(str(t))


# =============================================================================== coleta (rede com cache; só leitura)
@st.cache_data(ttl=3600, show_spinner=False)
def _ohlcv(simbolo: str) -> pd.DataFrame | None:
    try:
        import analise_tecnica_app as A
        r = A._baixar(simbolo, "1y", "1d")
        df = r.get("df")
        return df if df is not None and len(df) >= 25 else None
    except Exception:
        return None


@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _fundamentos(tk: str, classe: str) -> dict:
    """Só o que as fontes do app entregam: dívida/patrimônio (Yahoo) para ações e BDRs; vacância e nº de imóveis (Fundamentus) para FIIs."""
    out: dict = {}
    try:
        if classe in ("acao", "bdr"):
            import dados
            d = dados.buscar_yahoo(tk)
            if isinstance(d.get("div_pl"), (int, float)):
                out["div_pl"] = float(d["div_pl"])
        elif classe == "fii":
            import fiis_app
            df = fiis_app.lista_fiis().get("df")
            if df is not None and len(df) and tk.upper() in df.index:
                row = df.loc[tk.upper()]
                for k in ("vacancia", "qtd_imoveis"):
                    if k in row.index and pd.notna(row[k]):
                        out[k] = float(row[k])
    except Exception:
        pass
    return out


def _simbolo(p: dict) -> str:
    import analise_tecnica_app as A
    return A._simbolo_yahoo(p["id"], p.get("classe", "acao"))


def coletar(chave: str) -> dict | None:
    """Lê a carteira do Passo 12 (preços em R$, referências, CDI) e acrescenta volume (Yahoo) e fundamentos. Devolve None sem posições."""
    import gestao_app
    lido = gestao_app.ler_carteira(chave)
    if lido is None:
        return None
    C, D = lido
    cfg = _ss().get(CH_CFG) or {}
    pos = []
    for p in C["posicoes"]:
        if not (isinstance(p.get("valor"), (int, float)) and np.isfinite(p["valor"]) and p["valor"] > 0):
            continue
        q = dict(p)
        q["custodiante"] = (cfg.get("custodia") or {}).get(q["id"]) or q.get("custodiante") or q.get("corretora")
        if (cfg.get("resgate") or {}).get(q["id"]) is not None:
            q["dias_resgate"] = cfg["resgate"][q["id"]]
        if (cfg.get("gestao") or {}).get(q["id"]):
            q["gestao_tipo"] = cfg["gestao"][q["id"]]
        pos.append(q)
    mercado = [p for p in pos if p.get("classe") in ("acao", "bdr", "fii", "etf", "cripto")][:30]
    with ThreadPoolExecutor(max_workers=8) as ex:
        ohl = dict(zip([p["id"] for p in mercado], ex.map(lambda p: _ohlcv(_simbolo(p)), mercado)))
        fund = dict(zip([p["id"] for p in mercado], ex.map(lambda p: _fundamentos(p["id"], p["classe"]), mercado)))
    refs = {k: v for k, v in (C.get("referencias", {}).get("series") or {}).items() if v is not None and len(v)}
    return {"chave": chave, "posicoes": pos, "series": dict(D.get("series") or {}), "ohlcv": ohl, "fund": fund, "refs": refs, "cdi": D.get("cdi_diario"),
            "valor_hist": D.get("valor_hist"), "avisos": list(D.get("avisos") or []), "quando": datetime.now().isoformat(timespec="seconds"),
            "hoje": date.today().isoformat(), "fontes": ["Carteira (Passo 12): preços em R$ do Yahoo Finance, câmbio e CDI do BCB", "Volume e máx./mín.: Yahoo Finance (1 ano)",
                                                         "Dívida/patrimônio: Yahoo Finance · Vacância e imóveis de FIIs: Fundamentus"]}


def _recorte(s: pd.Series, dias_cal: int) -> pd.Series:
    if not dias_cal or s is None or not len(s):
        return s
    return s[s.index >= s.index[-1] - pd.Timedelta(days=dias_cal)]


def analisar(col: dict, classes=None, ativos=None, dias_cal: int = 0, limites: dict | None = None, hoje: date | None = None) -> dict:
    """Roda o motor de risco sobre a coleta, já com os filtros (classes, ativos, período). Notas dos ativos usam sempre 12 meses; indicadores,
    correlação e drawdown da carteira usam o período escolhido."""
    hoje = hoje or date.today()
    pos = [p for p in col["posicoes"] if (not classes or p["classe"] in classes) and (not ativos or p["id"] in ativos)]
    ids = {p["id"] for p in pos}
    ser_full = {k: v for k, v in col["series"].items() if k in ids}
    liq, ava = {}, {}
    refs = col["refs"]
    for p in pos:
        i, c = p["id"], p["classe"]
        df = col["ohlcv"].get(i)
        if c in ("acao", "bdr", "fii", "etf", "cripto"):
            fc = 1.0
            if df is not None and p.get("moeda", "BRL") != "BRL" and len(ser_full.get(i, [])) and len(df):
                fc = float(ser_full[i].iloc[-1] / df["Close"].iloc[-1]) if df["Close"].iloc[-1] else 1.0
            liq[i] = R.liquidez_negociavel(df, p["valor"], fator_cambio=fc)
        elif c == "renda_fixa":
            liq[i] = R.liquidez_renda_fixa(p)
        elif c == "fundo":
            liq[i] = R.liquidez_fundo(p)
        te = None
        if c == "etf" and i in ser_full:
            rb = R.retornos(refs.get("S&P 500 (em R$)" if p.get("moeda", "BRL") != "BRL" else "Ibovespa"))
            te = R.tracking_error(R.retornos(ser_full[i]), rb) if len(rb) else None
            te = te * 100 if te is not None else None
        ava[i] = R.avaliar_ativo(p, {"serie": ser_full.get(i), "liq": liq.get(i), "ind": col["fund"].get(i, {}), "te": te}, hoje)
    ser = {k: _recorte(v, dias_cal) for k, v in ser_full.items()}
    cart = R.risco_carteira(pos, ser, ava, liq, refs, col.get("cdi"), limites, hoje)
    vh = _recorte(col.get("valor_hist"), dias_cal) if col.get("valor_hist") is not None else None
    ret = {k: R.retornos(v) for k, v in ser_full.items()}
    return {"pos": pos, "ava": ava, "liq": liq, "cart": cart, "ser": ser, "ser_full": ser_full, "ret": ret, "refs": refs,
            "vol": {k: R.mudanca_volatilidade(r) for k, r in ret.items()}, "limites": R.avaliar_limites(pos, limites, hoje),
            "indiretas": R.exposicoes_indiretas(pos), "valor_hist": vh, "hoje": hoje}


def _limites_atuais() -> dict:
    return dict(_ss().get(CH_LIM) or {})


def _noticias_risco() -> list[dict]:
    out = []
    for t in list((((_ss().get("_ne_leitura") or {}).get("carteira") or {}).get("riscos")) or [])[:12]:
        cab, _, resto = str(t).partition(":")
        ativo = cab.split(",")[0].strip().upper()
        fonte = resto[resto.rfind("(") + 1:resto.rfind(")")] if "(" in resto else None
        out.append({"ativo": ativo, "titulo": resto[:resto.rfind("(")].strip() if "(" in resto else resto.strip(), "fonte": fonte})
    return out


def contexto_ia(col: dict | None, an: dict | None = None) -> dict | None:
    """Contexto para o assistente (Passo 13/15): só resultados já calculados."""
    if not col:
        return None
    ss = _ss()
    chave = repr((col["quando"], sorted((k, str(v)) for k, v in _limites_atuais().items()), repr(ss.get(CH_CFG))))
    if an is None:
        c = ss.get("_risco_ctx")
        if c and c[0] == chave:
            return c[1]
        an = analisar(col, limites=_limites_atuais())
    ctx = {"carteira": an["cart"], "avaliacoes": an["ava"], "posicoes": an["pos"], "limites": an["limites"], "vol": an["vol"], "noticias": _noticias_risco(),
           "gerado_em": col["quando"], "liq": an["liq"]}
    ctx["cenarios"] = R.comparar_cenarios(an["pos"], {**R.CENARIOS_RISCO, **(_ss().get(CH_CFG) or {}).get("cenarios", {})}, an["liq"])
    try:
        ctx["corr"] = R.mudancas_de_correlacao({k: v for k, v in an["ser_full"].items()})
    except Exception:
        ctx["corr"] = []
    if _ss().get("_risco_ctx_ok", True):
        ss["_risco_ctx"] = (chave, ctx)
    return ctx


def atualizar(chave: str) -> dict | None:
    """Coleta + análise completa + histórico de notas + alertas (com filtro de repetição). Tudo fica na sessão."""
    ss = _ss()
    col = coletar(chave)
    ss[RES] = col
    if col is None:
        ss[ALERTAS] = {"novos": [], "suprimidos": 0, "quando": datetime.now().isoformat(timespec="seconds")}
        return None
    an = analisar(col, limites=_limites_atuais())
    hist, mudancas = dict(ss.get(CH_NOTAS) or {}), {}
    for i, a in an["ava"].items():
        hist, m = R.registrar_nota(hist, a)
        if m:
            mudancas[i] = m
    ss[CH_NOTAS] = hist
    ctx = contexto_ia(col, an) or {}
    ctx.update({"mudancas_nota": mudancas, "drawdown": R.monitorar_drawdown(an["valor_hist"], (_limites_atuais().get("perda_drawdown_pct") or -20.0)) if an["valor_hist"] is not None else {}})
    regras = ss.get(CH_REGRAS) or []
    agora = datetime.now()
    disparos = R.avaliar_alertas_risco(regras, ctx, agora)
    novos, h2, supr = T.filtrar_por_frequencia(disparos, ss.get(CH_HIST) or [], regras, agora)
    ss[CH_HIST] = h2
    ss[ALERTAS] = {"novos": novos, "suprimidos": supr, "quando": agora.isoformat(timespec="seconds"), "mudancas": mudancas}
    return col


def _regras_padrao() -> list[dict]:
    return [R.nova_regra_risco("nota_ativo_alta", "*", {"nota_min": 70}, "media"), R.nova_regra_risco("nota_subiu", "*", {"pontos": 10}, "alta"),
            R.nova_regra_risco("limite_excedido", "*", {"gravidade_min": "media"}, "alta"), R.nova_regra_risco("drawdown_carteira", "*", {"limite_pct": -15.0}, "alta"),
            R.nova_regra_risco("volatilidade_subiu", "*", {"razao": 1.5}, "media"), R.nova_regra_risco("estresse_perda", "*", {"perda_pct": 25.0}, "media"),
            R.nova_regra_risco("dado_insuficiente", "*", {"pct_min": 20.0}, "baixa", "semanal"), R.nova_regra_risco("noticia_risco", "*", {}, "media")]


# =============================================================================== telas
def _selo_nivel(nota, nivel) -> str:
    return f"{nota:.0f}/100 · {nivel}" if nota is not None else nivel


def _aba_painel(col, an):
    c = an["cart"]
    if not c.get("ok"):
        st.info(c.get("motivo", "Sem dados para calcular o risco."))
        return
    ind, est = c["indicadores"], c["estresse_geral"]
    al = (_ss().get(ALERTAS) or {}).get("novos") or []
    dd_txt = f"{ind['dd_atual'] * 100:.1f}% agora · máx. {ind['mdd'] * 100:.1f}%" if ind.get("ok") and ind.get("mdd") is not None else "sem histórico"
    _cartoes([("Risco da carteira", _selo_nivel(c["nota"], c["nivel"]), COR_NIVEL.get(c["nivel"], "na"), f"confiança {c['confianca_rotulo'].lower()}" + (" · provisória" if c["status"] == "provisória" else "")),
              ("Patrimônio analisado", _brl(c["patrimonio"]), "info", f"{len(an['pos'])} posições · {c['cobertura_nota_pct']:.0f}% classificado"),
              ("Queda do pico", dd_txt.split(" · ")[0], "fair", dd_txt.split(" · ")[1] if " · " in dd_txt else ""),
              ("Perda no estresse geral", f"{est['pct']:.1f}%" if est.get("antes") else "n/d", "bad" if est.get("pct", 0) <= -25 else "fair", "hipótese, não previsão"),
              ("Limites excedidos", str(len(an["limites"])), "bad" if an["limites"] else "good", "seus limites em Limites e alertas"),
              ("Alertas novos", str(len(al)), "bad" if any(a["prioridade"] == "alta" for a in al) else "fair" if al else "good", "desta leitura"),
              ("Volatilidade anual", f"{ind['vol_anual'] * 100:.1f}%" if ind.get("ok") and ind.get("vol_anual") is not None else "n/d", "info", f"{ind.get('n_dias', 0)} dias úteis"),
              ("Nº efetivo de ativos", f"{c['hhi']['n_efetivo']:.1f}" if c.get("hhi") else "n/d", "info", "1 ÷ HHI")], 4)
    st.markdown(f"**{_md(c['texto'])}**")
    for a in col.get("avisos", [])[:3]:
        st.caption("⚠️ " + a)
    e1, e2 = st.columns([3, 2])
    with e1:
        st.markdown("##### Mapa de exposição (tamanho = valor, cor = nota de risco)")
        labs, pais_, vals, cores, txt = ["Carteira"], [""], [0], [None], [""]
        for k in sorted({p["classe"] for p in an["pos"]}):
            labs.append(g.CLASSES.get(k, k)); pais_.append("Carteira"); vals.append(0); cores.append(None); txt.append("")
        for p in an["pos"]:
            a = an["ava"].get(p["id"]) or {}
            labs.append(p["id"]); pais_.append(g.CLASSES.get(p["classe"], p["classe"])); vals.append(p["valor"])
            cores.append(a.get("nota") if a.get("nota") is not None else 50); txt.append(a.get("nivel", "sem nota"))
        fig = go.Figure(go.Treemap(labels=labs, parents=pais_, values=vals, text=txt, textinfo="label+text", branchvalues="remainder",
                                   marker=dict(colors=[x if x is not None else 0 for x in cores], colorscale=[[0, "#1f8a5b"], [0.5, "#e0a82e"], [1, "#c0392b"]], cmin=0, cmax=100, showscale=False)))
        _grafico(fig, 340)
    with e2:
        st.markdown("##### Distribuição por classe")
        d = g.distribuicao(an["pos"], "classe")
        fig = go.Figure(go.Pie(labels=[g.CLASSES.get(x["nome"], x["nome"]) for x in d], values=[x["valor"] for x in d], hole=0.55, textinfo="label+percent"))
        fig.update_layout(showlegend=False)
        _grafico(fig, 340)
    st.markdown("##### Perfil dos 14 riscos")
    st.caption("Calculado = medido nos dados · estimado = depende de premissa · proxy = regra qualitativa fixa. “Sem medida” significa que não há dado real para medir (não é risco zero).")
    df = pd.DataFrame([{"Risco": x["rotulo"], "Nota": x["nota"], "Nível": x["nivel"], "Tipo": x["tipo"], "Como é medido": x["formula"]} for x in c["perfil"]])
    st.dataframe(df, hide_index=True, width="stretch", column_config={"Nota": st.column_config.ProgressColumn("Nota", min_value=0, max_value=100, format="%.0f")})
    f1, f2 = st.columns(2)
    with f1:
        st.markdown("##### O que mais contribui para o risco")
        if c["contribuicoes"]:
            top = c["contribuicoes"][:8]
            fig = go.Figure(go.Bar(x=[x["contribuicao_pct"] for x in top][::-1], y=[x["id"] for x in top][::-1], orientation="h", text=[f"{x['contribuicao_pct']:.0f}%" for x in top][::-1]))
            fig.update_layout(xaxis_title="% da variância da carteira")
            _grafico(fig, 300)
            st.caption("Fatores: " + " · ".join(f"{k} {v:.0f}%" for k, v in list(c["por_fator"].items())[:4]))
        else:
            st.caption("Sem histórico comum suficiente para calcular contribuições.")
    with f2:
        st.markdown("##### Fragilidades e alertas prioritários")
        fr = R.fragilidades(c, 6)
        for x in fr:
            st.markdown(f"{ {3: '🔴', 2: '🟠', 1: '🟡'}[x['gravidade']] } **{_md(x['titulo'])}** — {_md(x['texto'])}")
        for a in al[:4]:
            st.markdown(f"{ {'alta': '🔴', 'media': '🟠', 'baixa': '🟡'}[a['prioridade']] } **{_md(a['titulo'])}** — causa: {_md(a['texto'])}")
        if not fr and not al:
            st.caption("Nenhuma fragilidade acima dos limites com os dados disponíveis.")
    with st.expander("Como a nota da carteira foi calculada"):
        st.dataframe(pd.DataFrame([{"Componente": x["rotulo"], "Valor": round(x["valor"], 2), "Nota": round(x["nota"], 1), "Peso efetivo": f"{x['peso'] * 100:.0f}%", "Tipo": x["tipo"]} for x in c["componentes"]]),
                     hide_index=True, width="stretch")
        st.caption(f"Nota = soma(nota × peso). Pesos-base: {R.PESOS_NOTA_CARTEIRA}. Componente sem dado sai do cálculo e reduz a confiança ({c['confianca'] * 100:.0f}%). Metodologia v{R.VERSAO_METODOLOGIA}.")


def _aba_ativos(col, an):
    if not an["ava"]:
        st.info("Sem ativos nos filtros escolhidos.")
        return
    tot = sum(p["valor"] for p in an["pos"])
    peso = {p["id"]: p["valor"] / tot * 100 for p in an["pos"]}
    df = pd.DataFrame([{"Ativo": a["id"], "Classe": g.CLASSES.get(a["classe"], a["classe"]), "Peso %": round(peso.get(a["id"], 0), 1), "Nota": a["nota"], "Nível": a["nivel"],
                        "Confiança": a["confianca_rotulo"], "Situação": a["status"], "Principais fatores": "; ".join(f["rotulo"] for f in a["fatores"]) or "—"}
                       for a in sorted(an["ava"].values(), key=lambda a: -(a["nota"] if a["nota"] is not None else -1))])
    st.caption("Cada classe usa a SUA metodologia (veja a aba Metodologia). Nota alta = risco alto. “Indeterminado” = faltou dado, não é sinal de segurança.")
    st.dataframe(df, hide_index=True, width="stretch", column_config={"Nota": st.column_config.ProgressColumn("Nota", min_value=0, max_value=100, format="%.0f")})
    sel = st.selectbox("Explicar a classificação de", list(an["ava"]), key="rk_sel_ativo")
    a = an["ava"][sel]
    for l in R.explicar_nota(a):
        st.markdown(_md(l) if not l.startswith("•") else "- " + _md(l[2:]))
    st.dataframe(pd.DataFrame([{"Componente": c["rotulo"], "Valor": round(c["valor"], 2), "Nota": round(c["nota"], 0) if c["nota"] is not None else None, "Peso": f"{c['peso'] * 100:.0f}%",
                                "Tipo": c["tipo"], "Fonte": c["fonte"]} for c in a["componentes"]]), hide_index=True, width="stretch")
    h = (_ss().get(CH_NOTAS) or {}).get(sel) or []
    if h:
        with st.expander(f"Histórico de alterações da classificação ({len(h)})"):
            st.dataframe(pd.DataFrame([{"Data": x["data"], "Nota": x["nota"], "Nível": x["nivel"], "Confiança": x["confianca"], "Situação": x["status"], "Metodologia": x["versao"]} for x in reversed(h)]),
                         hide_index=True, width="stretch")
            st.caption("Uma linha nova é gravada quando a nota muda 5 pontos ou mais, o nível muda, a situação muda ou a metodologia é atualizada.")
    with st.expander("Completar dados que o app não tem (custódia, prazo de resgate, tipo de gestão)"):
        cfg = dict(_ss().get(CH_CFG) or {})
        base = pd.DataFrame([{"Ativo": p["id"], "Custodiante / corretora / exchange": (cfg.get("custodia") or {}).get(p["id"], ""),
                              "Prazo de resgate (dias, fundos)": (cfg.get("resgate") or {}).get(p["id"]), "Gestão (ativa/passiva, fundos)": (cfg.get("gestao") or {}).get(p["id"], "")}
                             for p in col["posicoes"] if p["classe"] != "caixa"])
        ed = st.data_editor(base, hide_index=True, width="stretch", key="rk_editor_dados", disabled=["Ativo"],
                            column_config={"Gestão (ativa/passiva, fundos)": st.column_config.SelectboxColumn(options=["", "ativo", "passivo"])})
        if st.button("Salvar dados complementares", key="rk_salvar_dados", icon=":material/save:"):
            cfg["custodia"] = {r["Ativo"]: str(r["Custodiante / corretora / exchange"]).strip() for _, r in ed.iterrows() if str(r["Custodiante / corretora / exchange"]).strip()}
            cfg["resgate"] = {r["Ativo"]: float(r["Prazo de resgate (dias, fundos)"]) for _, r in ed.iterrows() if pd.notna(r["Prazo de resgate (dias, fundos)"])}
            cfg["gestao"] = {r["Ativo"]: r["Gestão (ativa/passiva, fundos)"] for _, r in ed.iterrows() if r["Gestão (ativa/passiva, fundos)"]}
            _ss()[CH_CFG] = cfg
            st.success("Salvo. Clique em “Atualizar análise de risco” para recalcular com esses dados.")


def _aba_volatilidade(col, an):
    ids = [i for i in an["ret"] if i in an["ava"]]
    if not ids:
        st.info("Sem séries de preço para calcular volatilidade.")
        return
    st.caption("Todas as volatilidades usam retornos diários de DIAS ÚTEIS e √252, para serem comparáveis entre classes. Cripto negocia 24h: os fins de semana entram no retorno de segunda-feira, "
               "então a volatilidade aqui pode diferir da de sites que usam 365 dias. Não compare números de metodologias diferentes.")
    bench_nome = st.selectbox("Benchmark para a volatilidade relativa", [k for k in an["refs"] if k != "CDI"] or ["—"], key="rk_vol_bench")
    rb = R.retornos(an["refs"].get(bench_nome)) if bench_nome in an["refs"] else None
    linhas = []
    for i in ids:
        r = an["ret"][i]
        vj = R.vol_janelas(r)
        df = col["ohlcv"].get(i)
        atr = R.atr(df)
        rel = R.vol_relativa(r, rb) if rb is not None and len(rb) else {"ok": False}
        mv = an["vol"].get(i) or {}
        linhas.append({"Ativo": i, **{f"Vol. {k}": (v["vol_anual"] * 100 if v["vol_anual"] is not None else None) for k, v in vj.items() if k != "2 anos"},
                       "Realizada 21d": (R.vol_realizada(r, 21) or float("nan")) * 100 if R.vol_realizada(r, 21) is not None else None,
                       "ATR (14) % do preço": atr["pct_preco"] * 100 if atr.get("ok") and atr.get("pct_preco") else None,
                       f"÷ {bench_nome}": rel.get("razao") if rel.get("ok") else None, "21d ÷ 12m": mv.get("razao") if mv.get("ok") else None, "Tendência": mv.get("sinal", "—")})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    st.caption("Vol. = desvio-padrão diário × √252 (% ao ano). Realizada = √(Σr²·252/n). ATR = média de Wilder do verdadeiro intervalo (só onde há máxima e mínima). "
               "“21d ÷ 12m” ≥ 1,5 indica risco subindo. Células vazias: histórico insuficiente (nunca zero).")
    mud = [(i, m) for i, m in an["vol"].items() if m.get("ok") and (m["razao"] >= 1.5 or m["razao"] <= 1 / 1.5)]
    for i, m in mud[:8]:
        st.markdown(f"{'🔺' if m['razao'] >= 1.5 else '🔻'} **{i}**: {_md(m['texto'])}")
    esc = st.multiselect("Volatilidade rolante de 63 dias úteis", ids, default=ids[:3], key="rk_vol_rol")
    if esc:
        fig = go.Figure()
        for i in esc:
            v = R.vol_rolante(an["ret"][i], 63)
            if len(v):
                fig.add_trace(go.Scatter(x=v.index, y=v * 100, name=i, mode="lines"))
        fig.update_layout(yaxis_title="% ao ano", legend=dict(orientation="h"))
        _grafico(fig, 320)


def _aba_indicadores(col, an):
    c = an["cart"]
    ids = ["Carteira"] + [i for i in an["ret"] if i in an["ava"]]
    sel = st.selectbox("Indicadores de", ids, key="rk_ind_sel")
    bn = st.selectbox("Benchmark (beta, correlação, tracking error)", [k for k in an["refs"] if k != "CDI"] or ["—"], key="rk_ind_bench")
    if sel == "Carteira":
        pesos = {p["id"]: p["valor"] for p in an["pos"]}
        rets = g.matriz_retornos({k: R.padronizar_dias_uteis(v) for k, v in an["ser"].items() if k in pesos}, 120)
        r = g.retornos_da_carteira(rets, pesos)[0] if not rets.empty else pd.Series(dtype=float)
    else:
        r = an["ret"][sel]
        dias = PERIODOS.get(_ss().get("rk_per", "12 meses"))
        if dias and len(r):
            r = r[r.index >= r.index[-1] - pd.Timedelta(days=dias)]
    rb = R.retornos(an["refs"].get(bn)) if bn in an["refs"] else None
    ind = R.indicadores(r, rb, col.get("cdi"))
    if not ind.get("ok"):
        st.warning(f"Sem indicadores: {ind.get('motivo')}.")
        return
    _cartoes([("Volatilidade anual", _p(ind["vol_anual"], 1), "info"), ("Maior queda", _p(ind["mdd"], 1), "bad"), ("Queda atual", _p(ind["dd_atual"], 1), "fair"),
              ("Retorno anualizado", _p(ind["cagr"], 1) if ind.get("cagr") is not None else "n/d", "info", "CAGR do período"),
              ("Sharpe", _n(ind.get("sharpe"), 2), "info", "excesso sobre o CDI"), ("Sortino", _n(ind.get("sortino"), 2), "info"), ("Calmar", _n(ind.get("calmar"), 2), "info", "CAGR ÷ |maior queda|"),
              ("Beta", _n(ind.get("beta"), 2), "info", bn)], 4)
    if rb is not None:
        _cartoes([("Correlação", _n(ind.get("correlacao_ref"), 2), "info", bn), ("Tracking error", _p(ind.get("tracking_error"), 1) if ind.get("tracking_error") is not None else "n/d", "info", "vs. " + bn),
                  ("Information ratio", _n(ind.get("information_ratio"), 2), "info"), ("Vol. relativa", _n((ind.get("vol_relativa") or {}).get("razao"), 2), "info", "ativo ÷ benchmark")], 4)
    rows = []
    for h in (1, 10):
        for nv in (95, 99):
            k = f"{nv}_{h}d"
            rows.append({"Horizonte": f"{h} dia(s)", "Confiança": f"{nv}%", "VaR histórico": ind.get("var_hist_" + k), "VaR paramétrico (normal)": ind.get("var_param_" + k),
                         "VaR EWMA (λ=0,94)": ind.get("var_ewma_" + k), "CVaR histórico": ind.get("cvar_" + k)})
    d = pd.DataFrame(rows)
    for cname in d.columns[2:]:
        d[cname] = d[cname].map(lambda x: _p(x, 2) if x is not None else "n/d")
    st.markdown("##### VaR e CVaR (perda como % do valor)")
    st.dataframe(d, hide_index=True, width="stretch")
    if sel == "Carteira" and c.get("patrimonio") and ind.get("var_hist_95_1d") is not None:
        st.caption(f"Em R$: VaR histórico 95% de 1 dia ≈ {_brl(ind['var_hist_95_1d'] * c['patrimonio'])} sobre {_brl(c['patrimonio'])}.")
    dd = ind["dd"]
    if dd.get("ok"):
        fig = go.Figure(go.Scatter(x=dd["serie"].index, y=dd["serie"] * 100, fill="tozeroy", name="Queda do pico"))
        fig.update_layout(yaxis_title="% abaixo do pico", title="Drawdown")
        _grafico(fig, 280)
    with st.expander("Limitações de cada indicador"):
        for k, t in R.LIMITES_INDICADORES.items():
            st.markdown(f"- **{k.replace('_', ' ')}**: {_md(t)}")
    st.caption(f"{ind['n_dias']} dias úteis. Indicadores do passado não limitam perdas futuras; horizontes de 10 dias escalam o de 1 dia por √10 (assume retornos independentes).")


def _aba_concentracao(col, an):
    pos = an["pos"]
    conc = c = an["cart"].get("concentracao") or R.concentracao_completa(pos)
    hh = an["cart"].get("hhi") or {}
    _cartoes([("Maior posição", _p(hh.get("top1"), 1) if hh.get("top1") is not None else "n/d", "bad" if (hh.get("top1") or 0) >= 0.3 else "info"),
              ("3 maiores", _p(hh.get("top3"), 1) if hh.get("top3") is not None else "n/d", "info"), ("HHI", _n(hh.get("hhi"), 3) if hh.get("hhi") is not None else "n/d", "info", "0 a 1; menor = mais diversificado"),
              ("Nº efetivo de ativos", _n(hh.get("n_efetivo"), 1) if hh.get("n_efetivo") is not None else "n/d", "info", "1 ÷ HHI")], 4)
    eixo = st.selectbox("Concentração por", list(R.EIXOS), format_func=lambda e: R.EIXOS[e], key="rk_eixo")
    e = conc["eixos"][eixo]
    if not e["avaliavel"]:
        st.warning(f"{e['pct_nao_informado']:.0f}% do patrimônio está sem essa informação (“Não informado”): o eixo não é avaliável. "
                   "Informe a custódia na aba Ativos → Completar dados." if eixo == "custodiante" else f"{e['pct_nao_informado']:.0f}% do patrimônio sem essa informação: eixo não avaliável.")
    d = e["dist"][:15]
    if d:
        fig = go.Figure(go.Bar(x=[x["pct"] for x in d][::-1], y=[x["nome"] for x in d][::-1], orientation="h", text=[f"{x['pct']:.1f}%" for x in d][::-1]))
        fig.update_layout(xaxis_title="% do patrimônio")
        lim = {**R.LIMITES_PADRAO_RISCO, **_limites_atuais()}.get(eixo)
        if isinstance(lim, (int, float)):
            fig.add_vline(x=lim, line_dash="dash", annotation_text=f"seu limite {lim:g}%")
        _grafico(fig, max(240, 34 * len(d) + 80))
        st.dataframe(pd.DataFrame([{e["rotulo"]: x["nome"], "Valor": _brl(x["valor"]), "%": round(x["pct"], 1), "Ativos": ", ".join(x["ativos"][:6])} for x in e["dist"]]), hide_index=True, width="stretch")
    st.markdown("##### Exposições indiretas: ativos diferentes, mesmo fator")
    ind = an["indiretas"]
    if ind:
        for x in ind[:6]:
            st.markdown(f"- {_md(x['texto'])}")
    else:
        st.caption("Nenhum fator comum a 2 ou mais ativos.")
    c1, c2, c3 = st.columns(3)
    cam, ju, cr = an["cart"].get("cambio") or {}, an["cart"].get("juros") or {}, an["cart"].get("credito") or {}
    with c1:
        st.markdown("**Câmbio**")
        if cam.get("ok"):
            st.markdown(f"Direta {cam['direta_pct']:.0f}% · indireta {cam['indireta_pct']:.0f}%")
            st.caption(cam["texto"])
    with c2:
        st.markdown("**Juros**")
        if ju.get("ok"):
            st.markdown(f"+1 p.p. ≈ {ju['pct_1pp']:.2f}% ({_brl(ju['delta_1pp'])})")
            st.caption(ju["premissa"])
    with c3:
        st.markdown("**Crédito**")
        if cr.get("ok") and cr["renda_fixa_pct"]:
            st.markdown(f"Renda fixa {cr['renda_fixa_pct']:.0f}% · privada sem FGC {cr['privado_sem_fgc_pct']:.0f}%")
            st.caption(cr["texto"])
        else:
            st.caption("Sem renda fixa na seleção.")
    if an["limites"]:
        st.markdown("##### Acima dos seus limites")
        for x in an["limites"][:10]:
            st.markdown(f"{ {'alta': '🔴', 'media': '🟠', 'baixa': '🟡'}[x['gravidade']] } {_md(x['texto'])}")


def _series_corr(an, incluir_refs: bool) -> dict:
    s = {k: v for k, v in an["ser_full"].items()}
    if incluir_refs:
        s.update({k: v for k, v in an["refs"].items() if k != "CDI" or True})
    return s


def _aba_correlacao(col, an):
    st.caption(R.AVISO_CORRELACAO)
    incl = st.checkbox("Incluir índices e moedas (CDI, Ibovespa, S&P 500 em R$, dólar)", value=True, key="rk_corr_refs")
    janela = st.selectbox("Janela", ["3 meses", "6 meses", "12 meses", "Todo o histórico"], index=2, key="rk_corr_jan")
    n = {"3 meses": 63, "6 meses": 126, "12 meses": 252, "Todo o histórico": None}[janela]
    ser = _series_corr(an, incl)
    corr = R.matriz_corr(ser, n, minimo=min(60, n or 60))
    if corr.empty:
        st.info("Histórico comum curto demais para esta janela (mínimo de 60 dias úteis em comum e 2 ativos).")
        return
    fig = go.Figure(go.Heatmap(z=corr.values, x=list(corr.columns), y=list(corr.index), zmin=-1, zmax=1, colorscale="RdBu_r", text=np.round(corr.values, 2), texttemplate="%{text}"))
    fig.update_layout(yaxis=dict(autorange="reversed"))
    _grafico(fig, max(320, 36 * len(corr)))
    st.caption(f"{len(corr)} séries · {janela.lower()} · retornos diários de dias úteis em datas comuns. Ativos com pouco histórico ficam de fora.")
    gr = R.grupos_semelhantes(corr, 0.70)
    st.markdown("##### Grupos de comportamento parecido (correlação ≥ 0,70)")
    if gr:
        for x in gr[:8]:
            st.markdown("- " + ", ".join(x))
    else:
        st.caption("Nenhum grupo com correlação ≥ 0,70 nesta janela.")
    st.markdown("##### Correlações que mudaram (3 meses × 12 meses)")
    mud = R.mudancas_de_correlacao(ser)
    if mud:
        for x in mud[:10]:
            st.markdown(f"{'🔺' if x['mudanca'] > 0 else '🔻'} {_md(x['texto'])}")
    else:
        st.caption("Nenhum par mudou 0,30 ou mais.")
    pesos = {p["id"]: p["valor"] for p in an["pos"]}
    pd_ = R.correlacao_nos_piores_dias(an["ser_full"], pesos)
    if pd_.get("ok"):
        st.markdown(f"**Nos 10% piores dias da carteira**, a correlação média entre os ativos foi {pd_['piores_dias']:+.2f}, contra {pd_['todos']:+.2f} em todos os dias "
                    f"({pd_['n_cauda']} dias na cauda). " + ("A diversificação encolhe quando mais importa." if pd_["aumento"] > 0.05 else "Sem aumento relevante nesta amostra."))
    else:
        st.caption("Correlação nos piores dias: " + pd_.get("motivo", "n/d") + ".")
    c = an["cart"]
    if c.get("ok") and c["indicadores"].get("ok"):
        with st.expander("Quanto a diversificação depende da correlação do passado"):
            try:
                import gestao_otimiza as O
                pes = {p["id"]: p["valor"] for p in an["pos"] if p["id"] in an["ser"]}
                rets = g.matriz_retornos({k: R.padronizar_dias_uteis(v) for k, v in an["ser"].items() if k in pes}, 120)
                w = pd.Series({k: pes[k] for k in rets.columns})
                w = w / w.sum()
                vols = rets.std(ddof=1) * np.sqrt(252)
                linhas = [{"Cenário de correlação": nome, "Volatilidade da carteira": _p(O.vol_com_correlacao(w, vols, rets.corr(), k), 1)} for nome, k in (("Histórica", 0.0), ("Metade do caminho até 1", 0.5), ("Todas iguais a 1 (sem diversificação)", 1.0))]
                st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
            except Exception:
                st.caption("Sem histórico comum suficiente.")


def _fmt_adv(x):
    return _brl(x) if x is not None else "n/d"


def _aba_liquidez(col, an):
    liq, pos = an["liq"], {p["id"]: p for p in an["pos"]}
    lc = an["cart"].get("liquidez")
    if lc:
        n, e = lc["normal"], lc["estresse"]
        _cartoes([("Em até 1 dia", f"{n['em_1d']:.0f}%", "good", f"estresse: {e['em_1d']:.0f}%"), ("De 2 a 5 dias", f"{n['em_5d']:.0f}%", "info", f"estresse: {e['em_5d']:.0f}%"),
                  ("De 6 a 30 dias", f"{n['em_30d']:.0f}%", "fair", f"estresse: {e['em_30d']:.0f}%"), ("Mais de 30 dias", f"{n['mais_30d']:.0f}%", "bad" if n["mais_30d"] > 5 else "info", f"estresse: {e['mais_30d']:.0f}%"),
                  ("Sem dado", f"{n['sem_dado']:.0f}%", "na", "liquidez não medida")], 5)
        st.caption(lc["aviso"])
    linhas = []
    for i, L in liq.items():
        p = pos.get(i, {})
        linhas.append({"Ativo": i, "Classe": g.CLASSES.get(p.get("classe"), p.get("classe")), "Valor": _brl(p.get("valor")), "Liquidez média diária": _fmt_adv(L.get("adv")),
                       "Dias com negociação (60)": f"{L['freq'] * 100:.0f}%" if L.get("freq") is not None else "—", "Dias para liquidar": round(L["dias_liquidar"], 2) if L.get("ok") else None,
                       "Em estresse": round(L["dias_liquidar_estresse"], 2) if L.get("ok") else None, "Impacto potencial no preço": f"{L['impacto_pct']:.2f}%" if L.get("impacto_pct") is not None else "—",
                       "Spread": "n/d", "Profundidade": "n/d", "Situação": "medido" if L.get("ok") else L.get("motivo", "sem dado")})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    st.caption("Ações, FIIs, ETFs e cripto: liquidez média = preço × volume dos últimos 20 pregões; dias para liquidar = valor ÷ (liquidez × 10% de participação); impacto = σ·√(valor ÷ liquidez), "
               "uma ESTIMATIVA. Renda fixa: prazo de carência ou vencimento (a venda antecipada pode ter perda de marcação a mercado). Fundos: prazo de resgate que você informar (aba Ativos). "
               "Spread e profundidade do livro de ofertas não estão disponíveis nas fontes gratuitas. Estresse = volume cai à metade.")
    if lc and lc["dificeis"]:
        st.markdown("##### Podem ter dificuldade de negociação em estresse")
        for x in lc["dificeis"][:8]:
            st.markdown(f"- **{x['id']}**: ~{x['dias']:.1f} dias para sair ({x['pct']:.0f}% do patrimônio)")


def _aba_estresse(col, an):
    st.warning(R.AVISO_ESTRESSE)
    cfg = dict(_ss().get(CH_CFG) or {})
    custom = dict(cfg.get("cenarios") or {})
    todos = {**R.CENARIOS_RISCO, **custom}
    lista = R.comparar_cenarios(an["pos"], todos, an["liq"])
    st.markdown("##### Todos os cenários, do pior ao menos severo")
    st.dataframe(pd.DataFrame([{"Cenário": x["nome"], "Variação": round(x["pct"], 2), "Em R$": _brl(x["delta"]), "Patrimônio depois": _brl(x["depois"]), "Maior fonte de perda": x["maior_fonte"] or "—",
                                "Pior ativo": x["pior_ativo"] or "—"} for x in lista]), hide_index=True, width="stretch")
    escolha = st.selectbox("Ver detalhes do cenário", list(todos), key="rk_cen_sel")
    with st.expander("Criar ou alterar um cenário personalizado", icon=":material/tune:"):
        nome = st.text_input("Nome", key="rk_cen_nome", **_opt("rk_cen_nome", "value", "Meu cenário"), max_chars=50)
        vals = {}
        cols = st.columns(2)
        for k, (ch, rot) in enumerate(R.CHOQUES_ROTULO.items()):
            vals[ch] = cols[k % 2].number_input(rot, -100.0, 100.0, float(todos.get(escolha, {}).get(ch, 0.0)), 0.5, key=f"rk_cen_{ch}_{escolha}")
        c1, c2 = st.columns(2)
        if c1.button("Salvar cenário", key="rk_cen_salvar", icon=":material/save:") and nome.strip():
            custom[nome.strip()] = {k: v for k, v in vals.items() if v}
            cfg["cenarios"] = custom
            _ss()[CH_CFG] = cfg
            st.rerun()
        if nome.strip() in custom and c2.button("Remover este cenário", key="rk_cen_rm"):
            custom.pop(nome.strip(), None)
            cfg["cenarios"] = custom
            _ss()[CH_CFG] = cfg
            st.rerun()
    s = R.simular_estresse(an["pos"], todos[escolha], an["liq"], nome=escolha)
    _cartoes([("Patrimônio hoje", _brl(s["antes"]), "info"), ("Depois do cenário", _brl(s["depois"]), "fair"), ("Variação", f"{s['pct']:+.1f}%", "bad" if s["pct"] < -10 else "fair", _brl(s["delta"]))], 3)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**Por classe**")
        fig = go.Figure(go.Bar(x=[g.CLASSES.get(k, k) for k in s["por_classe"]], y=list(s["por_classe"].values())))
        fig.update_layout(yaxis_title="R$")
        _grafico(fig, 260)
    with c2:
        st.markdown("**Principais fontes de perda**")
        fig = go.Figure(go.Bar(x=list(s["fontes"].values()), y=list(s["fontes"].keys()), orientation="h"))
        _grafico(fig, 260)
    st.dataframe(pd.DataFrame([{"Ativo": l["id"], "Classe": g.CLASSES.get(l["classe"], l["classe"]), "Valor": _brl(l["valor"]), "Variação %": round(l["pct"], 2), "Em R$": _brl(l["delta"]),
                                "Causas": "; ".join(f"{k} {v:+.1f}%" for k, v in l["partes"].items() if abs(v) > 0.005), "Premissa": l["premissa"]} for l in s["posicoes"]]), hide_index=True, width="stretch")
    with st.expander("Premissas usadas"):
        for t in s["premissas"]:
            st.markdown("- " + _md(t))
        st.caption(s["aviso"])


def _rm_regra(rid: str):
    _ss()[CH_REGRAS] = [r for r in (_ss().get(CH_REGRAS) or []) if r["id"] != rid]


def _add_regra():
    ss = _ss()
    t = ss.get("rk_r_tipo")
    pri = {"Alta": "alta", "Média": "media", "Baixa": "baixa"}[ss.get("rk_r_pri", "Média")]
    num = {"nota_ativo_alta": "nota_min", "nota_subiu": "pontos", "nota_carteira_alta": "nota_min", "drawdown_carteira": "limite_pct", "perda_sobre_custo": "limite_pct",
           "volatilidade_subiu": "razao", "correlacao_subiu": "mudanca", "liquidez_baixa": "dias", "estresse_perda": "perda_pct", "dado_insuficiente": "pct_min"}.get(t)
    params = {num: float(ss.get("rk_r_num", 0))} if num else {}
    if t == "limite_excedido":
        params = {"gravidade_min": ss.get("rk_r_grav", "media")}
    try:
        r = R.nova_regra_risco(t, ss.get("rk_r_ativo") or "*", params, pri, ss.get("rk_r_freq", "diaria"))
    except ValueError as e:
        ss["rk_r_msg"] = str(e)
        return
    regras = [x for x in (ss.get(CH_REGRAS) or []) if x["id"] != r["id"]]
    ss[CH_REGRAS] = regras + [r]
    ss["rk_r_msg"] = "Regra adicionada."


def _aba_limites(col, an):
    lim_salvo = _limites_atuais()
    base = {**R.LIMITES_PADRAO_RISCO, **lim_salvo}
    st.caption("Limites são suas referências pessoais, em % do patrimônio — não são regras do mercado. O app só avisa: nunca vende nem compra nada sozinho.")
    with st.expander("Seus limites de exposição", expanded=not lim_salvo, icon=":material/tune:"):
        cols = st.columns(3)
        novo = {}
        for k, e in enumerate(x for x in R.EIXOS if x not in ("empresa",)):
            novo[e] = cols[k % 3].number_input(f"{R.EIXOS[e]} (máx. %)", 1.0, 100.0, float(base[e]), 1.0, key=f"rk_lim_{e}")
        c1, c2 = st.columns(2)
        novo["perda_drawdown_pct"] = c1.number_input("Queda máxima aceitável da carteira (%)", -95.0, -1.0, float(base["perda_drawdown_pct"]), 1.0, key="rk_lim_dd")
        novo["perda_sobre_custo_pct"] = c2.number_input("Perda máxima por ativo sobre o custo (%)", -95.0, -1.0, float(base["perda_sobre_custo_pct"]), 1.0, key="rk_lim_custo")
        st.markdown("**Limites específicos** (valem no lugar do geral)")
        esp = pd.DataFrame([{"Tipo": "ativo", "Nome": k, "Limite %": v} for k, v in (base.get("por_ativo") or {}).items()] + [{"Tipo": "classe", "Nome": k, "Limite %": v} for k, v in (base.get("por_classe") or {}).items()]
                           + [{"Tipo": "setor", "Nome": k, "Limite %": v} for k, v in (base.get("por_setor") or {}).items()], columns=["Tipo", "Nome", "Limite %"])
        ed = st.data_editor(esp, num_rows="dynamic", hide_index=True, width="stretch", key="rk_lim_esp",
                            column_config={"Tipo": st.column_config.SelectboxColumn(options=["ativo", "classe", "setor"], required=True), "Limite %": st.column_config.NumberColumn(min_value=0.0, max_value=100.0)})
        st.caption("Classe: use o nome como aparece (ex.: Ações, FIIs, Criptomoedas). Setor: como aparece na Concentração.")
        if st.button("Salvar limites", key="rk_lim_salvar", icon=":material/save:"):
            for tipo, chave in (("ativo", "por_ativo"), ("classe", "por_classe"), ("setor", "por_setor")):
                novo[chave] = {str(r["Nome"]).strip(): float(r["Limite %"]) for _, r in ed.iterrows() if r["Tipo"] == tipo and str(r["Nome"]).strip() and pd.notna(r["Limite %"])}
            _ss()[CH_LIM] = novo
            st.success("Limites salvos.")
            st.rerun()
        if lim_salvo and st.button("Voltar aos limites padrão", key="rk_lim_reset"):
            _ss()[CH_LIM] = {}
            st.rerun()
    ex = an["limites"]
    st.markdown(f"##### Limites excedidos ({len(ex)})")
    if ex:
        st.dataframe(pd.DataFrame([{"Eixo": x["rotulo"], "Item": x["nome"], "Atual %": round(x["pct"], 1), "Limite %": x["limite"], "Excesso %": round(x["excesso_pct"], 1), "Excesso R$": _brl(x["excesso_brl"]), "Gravidade": x["gravidade"]} for x in ex]),
                     hide_index=True, width="stretch")
    else:
        st.success("Nenhum limite excedido.")
    ni = [e for e, v in (an["cart"].get("concentracao") or {}).get("eixos", {}).items() if not v["avaliavel"]]
    if ni:
        st.caption("Eixos sem dados suficientes para checar o limite: " + ", ".join(R.EIXOS[e].lower() for e in ni) + ".")
    st.markdown("##### Queda da carteira e perda sobre o custo")
    dd = R.monitorar_drawdown(an["valor_hist"], base["perda_drawdown_pct"]) if an["valor_hist"] is not None else {"ok": False, "motivo": "sem histórico de valor da carteira"}
    if dd.get("ok"):
        (st.error if dd["situacao"] == "excedido" else st.warning if dd["situacao"] == "atenção" else st.success)(dd["texto"])
    else:
        st.caption("Drawdown da carteira: " + dd.get("motivo", "n/d") + ".")
    pc = R.perdas_sobre_custo(an["pos"], base["perda_sobre_custo_pct"])
    for x in pc:
        st.markdown(f"🟠 {_md(x['texto'])} Perda de {_brl(-x['perda_brl'])}.")
    if not pc:
        st.caption(f"Nenhuma posição com perda sobre o custo de {base['perda_sobre_custo_pct']:g}% ou pior (considera só ativos com custo informado).")
    st.markdown("##### Simular redução de exposição (sem executar nada)")
    modo = st.radio("Como definir a redução", ["Voltar aos meus limites", "Escolher ativos e valores"], horizontal=True, key="rk_red_modo")
    if modo == "Voltar aos meus limites":
        red = R.sugerir_reducoes(an["pos"], lim_salvo)
    else:
        esc = st.multiselect("Ativos a reduzir", [p["id"] for p in an["pos"] if p["classe"] != "caixa"], key="rk_red_ids")
        red = {}
        for i in esc:
            v = next(p["valor"] for p in an["pos"] if p["id"] == i)
            red[i] = st.number_input(f"Reduzir {i} em R$ (de {_brl(v)})", 0.0, float(v), 0.0, 100.0, key=f"rk_red_{i}")
    dest = st.radio("Destino do dinheiro", ["caixa", "fora"], horizontal=True, key="rk_red_dest", format_func=lambda x: "fica em caixa" if x == "caixa" else "sai da carteira")
    if red:
        sim = R.simular_reducao(an["pos"], red, lim_salvo, None, an["liq"], dest)
        a, d = sim["antes"], sim["depois"]
        st.dataframe(pd.DataFrame([{"Ativo": i, "Reduzir R$": _brl(v)} for i, v in red.items() if v > 0]), hide_index=True, width="stretch")
        st.dataframe(pd.DataFrame([{"": "Limites excedidos", "Antes": a["n_excessos"], "Depois": d["n_excessos"]}, {"": "Maior posição", "Antes": f"{a['maior'][0]} {a['maior'][1]:.1f}%" if a["maior"] else "—", "Depois": f"{d['maior'][0]} {d['maior'][1]:.1f}%" if d["maior"] else "—"},
                                   {"": "Nº efetivo de ativos", "Antes": round(a["n_efetivo"], 1) if a["n_efetivo"] else None, "Depois": round(d["n_efetivo"], 1) if d["n_efetivo"] else None},
                                   {"": "Perda no estresse geral", "Antes": _brl(a["perda_estresse"]), "Depois": _brl(d["perda_estresse"])}]), hide_index=True, width="stretch")
        st.caption(sim["aviso"])
    else:
        st.caption("Nada a reduzir: " + ("você está dentro dos limites." if modo == "Voltar aos meus limites" else "escolha ativos."))
    _alertas_ui()


def _alertas_ui():
    ss = _ss()
    st.markdown("##### Alertas de risco")
    st.caption("Aparecem ao atualizar a análise; não há e-mail nem aviso no celular (dependem de serviço externo). Cada alerta mostra a causa, os dados usados e a data da detecção; o mesmo alerta não se repete dentro da frequência da regra.")
    res = ss.get(ALERTAS) or {}
    for a in res.get("novos") or []:
        with st.expander(f"{ {'alta': '🔴', 'media': '🟠', 'baixa': '🟡'}[a['prioridade']] } {a['titulo']}"):
            st.markdown(f"**Causa:** {_md(a['texto'])}")
            st.markdown(f"**Detectado em:** {a['data'][:16].replace('T', ' ')}")
            st.json(a["dados"], expanded=False)
    if not res.get("novos"):
        st.info("Nenhum alerta novo na última atualização." + (f" {res['suprimidos']} repetido(s) suprimido(s)." if res.get("suprimidos") else ""))
    regras = ss.get(CH_REGRAS) or []
    if not regras and st.button("Criar regras sugeridas", key="rk_regras_sug", icon=":material/notifications_active:"):
        ss[CH_REGRAS] = _regras_padrao()
        st.rerun()
    for r in regras:
        c1, c2, c3 = st.columns([5, 2, 1])
        c1.markdown(f"**{_md(R.descrever_regra_risco(r))}**")
        c2.caption(f"{r['prioridade']} · {FREQ_ROT[r['frequencia']]}")
        c3.button("Remover", key=f"rk_rm_{r['id']}", on_click=_rm_regra, args=(r["id"],))
    with st.expander("Nova regra", icon=":material/add_alert:"):
        c1, c2 = st.columns(2)
        c1.selectbox("Tipo", list(R.TIPOS_ALERTA_RISCO), key="rk_r_tipo", format_func=lambda t: R.TIPOS_ALERTA_RISCO[t])
        c2.text_input("Ativo (código ou * para todos)", key="rk_r_ativo", **_opt("rk_r_ativo", "value", "*"))
        c3, c4, c5 = st.columns(3)
        c3.number_input("Valor do parâmetro (nota, pontos, %, razão ou dias, conforme o tipo)", -100.0, 1000.0, 70.0, 1.0, key="rk_r_num")
        c4.selectbox("Prioridade", ["Alta", "Média", "Baixa"], key="rk_r_pri", index=1)
        c5.selectbox("Frequência", list(FREQ_ROT), key="rk_r_freq", index=1, format_func=lambda x: FREQ_ROT[x])
        st.selectbox("Gravidade mínima (só para Limite excedido)", ["baixa", "media", "alta"], key="rk_r_grav", index=1)
        st.button("Adicionar regra", key="rk_r_add", on_click=_add_regra, icon=":material/add:")
        if ss.get("rk_r_msg"):
            st.caption(ss["rk_r_msg"])
    hist = ss.get(CH_HIST) or []
    if hist:
        with st.expander(f"Histórico de alertas ({len(hist)})"):
            for h in reversed(hist[-40:]):
                st.markdown(f"- {h['quando'][:16].replace('T', ' ')} · **{_md(h['titulo'])}** ({h['prioridade']})")
            st.button("Limpar histórico", key="rk_hist_limpar", on_click=lambda: ss.__setitem__(CH_HIST, []))


def _aba_posicao(col, an):
    st.caption("Calcula o MAIOR tamanho de posição compatível com o risco que você aceita perder, mostrando todas as premissas. Não é recomendação de compra e não envia ordens.")
    pos = [p for p in an["pos"] if p["classe"] != "caixa"]
    tot = sum(p["valor"] for p in an["pos"])
    caixa = sum(p["valor"] for p in an["pos"] if p["classe"] == "caixa")
    ref = st.selectbox("Ativo de referência (preenche volatilidade, ATR e exposição atual)", ["— informar à mão —"] + [p["id"] for p in pos], key="rk_pos_ref")
    p0 = next((p for p in pos if p["id"] == ref), None)
    vol0 = atr0 = preco0 = perda0 = None
    if p0:
        vv = R.vol_janelas(an["ret"].get(ref, pd.Series(dtype=float)), {"12 meses": 252}).get("12 meses", {}).get("vol_anual")
        vol0 = vv * 100 if vv else None
        a_ = R.atr(col["ohlcv"].get(ref))
        atr0 = a_.get("atr") if a_.get("ok") else None
        preco0 = float(col["ohlcv"][ref]["Close"].iloc[-1]) if col["ohlcv"].get(ref) is not None else None
        e = R.simular_estresse([p0], R.CENARIOS_RISCO["Estresse geral"], an["liq"])
        perda0 = -e["pct"] if e["pct"] < 0 else None
    c1, c2, c3 = st.columns(3)
    pat = c1.number_input("Patrimônio total (R$)", 0.0, 1e12, float(round(tot, 2)), 1000.0, key=f"rk_pos_pat_{ref}")
    disp = c2.number_input("Valor disponível (R$)", 0.0, 1e12, float(round(caixa, 2)), 500.0, key=f"rk_pos_disp_{ref}")
    risco = c3.number_input("Risco máximo desejado (% do patrimônio)", 0.1, 100.0, 1.0, 0.25, key="rk_pos_risco")
    c4, c5, c6 = st.columns(3)
    expo = c4.number_input("Exposição atual no ativo (R$)", 0.0, 1e12, float(round(p0["valor"], 2)) if p0 else 0.0, 500.0, key=f"rk_pos_expo_{ref}")
    entrada = c5.number_input("Preço de entrada (0 = não se aplica)", 0.0, 1e9, float(round(preco0, 2)) if preco0 else 0.0, 0.01, key=f"rk_pos_ent_{ref}")
    stop = c6.number_input("Stop (0 = sem stop)", 0.0, 1e9, 0.0, 0.01, key=f"rk_pos_stop_{ref}")
    c7, c8, c9 = st.columns(3)
    vol = c7.number_input("Volatilidade anual do ativo (%; 0 = não usar)", 0.0, 500.0, float(round(vol0, 1)) if vol0 else 0.0, 1.0, key=f"rk_pos_vol_{ref}")
    atr_v = c8.number_input("ATR (R$; 0 = não usar)", 0.0, 1e9, float(round(atr0, 3)) if atr0 else 0.0, 0.01, key=f"rk_pos_atr_{ref}")
    est = c9.number_input("Perda de estresse (%; para ativos sem stop)", 0.0, 100.0, float(round(perda0, 1)) if perda0 else 0.0, 1.0, key=f"rk_pos_est_{ref}",
                          help="Para fundos e renda fixa, que não têm stop: quanto você admite perder numa situação ruim.")
    c10, c11 = st.columns(2)
    lim_at = c10.number_input("Limite por ativo (% do patrimônio)", 1.0, 100.0, float({**R.LIMITES_PADRAO_RISCO, **_limites_atuais()}["ativo"]), 1.0, key="rk_pos_lim")
    hor = c11.number_input("Horizonte para a volatilidade (dias úteis)", 1, 252, 21, 1, key="rk_pos_hor")
    r = R.dimensionar_posicao(pat, disp, risco, entrada or None, stop or None, vol / 100 if vol else None, expo, lim_at, atr_v or None, est or None, int(hor))
    if not r["ok"]:
        st.warning(r["erro"])
    else:
        _cartoes([("Valor máximo compatível", _brl(r["valor_max"]), "info", f"{r['pct_patrimonio']:.1f}% do patrimônio"),
                  ("Quantidade", f"{r['quantidade']:,}".replace(",", ".") if r["quantidade"] is not None else "—", "info", "lotes inteiros"),
                  ("Perda estimada no cenário", _brl(r["perda_estimada"]), "fair", f"{r['perda_estimada_pct_patrimonio']:.2f}% do patrimônio"),
                  ("O que limitou", r["restricao"], "na")], 4)
        st.dataframe(pd.DataFrame([{"Método": m["metodo"], "Valor máximo": _brl(m["valor_max"]), "Perda adversa considerada": f"{m['perda_pct_adversa']:.1f}%", "Cálculo": m["formula"]} for m in r["metodos"]]), hide_index=True, width="stretch")
        st.dataframe(pd.DataFrame([{"Teto": k, "Valor": _brl(v)} for k, v in r["tetos"].items()]), hide_index=True, width="stretch")
    with st.expander("Premissas usadas", expanded=True):
        for t in r["premissas"]:
            st.markdown("- " + _md(t))
        if r["ok"]:
            st.caption(r["aviso"])
    st.caption("Fundos e renda fixa: sem stop nem negociação contínua, use a perda de estresse. Escolha o método mais conservador (o app já usa o menor valor).")


def _aba_metodologia(col, an):
    st.markdown(f"**Versão da metodologia: {R.VERSAO_METODOLOGIA}.** Nota 0–100 (maior = mais risco) → nível: Muito baixo (<20), Baixo (<40), Moderado (<60), Alto (<80), Muito alto (≥80).")
    st.markdown("- **Risco ≠ incerteza**: componente sem dado sai da média (pesos renormalizados) e reduz a *confiança*. Com menos de 40% da metodologia medida a nota é *provisória*; com menos de 25% fica *indeterminada*.\n"
                "- **Calculado** = medido em dados reais · **estimado** = depende de premissa do modelo · **proxy** = regra qualitativa fixa (regulatório, operacional, contraparte), nunca apresentada como medida.\n"
                "- Cada componente: nota = interpolação linear entre duas âncoras (valor que vale 0 e valor que vale 100). Mudar âncora ou peso exige subir a versão.")
    for cl, comps in R.METODOLOGIA.items():
        if cl == "outro":
            continue
        with st.expander(g.CLASSES.get(cl, cl)):
            st.dataframe(pd.DataFrame([{"Componente": c["rotulo"], "Peso": f"{c['peso'] * 100:.0f}%", "Tipo": c["tipo"], "Como é calculado": c["formula"]} for c in comps]), hide_index=True, width="stretch")
    with st.expander("Fórmulas dos indicadores"):
        st.markdown("- **Volatilidade**: σ(retornos diários) × √252 · **Realizada**: √(Σr² × 252 / n) · **ATR**: média móvel de Wilder do verdadeiro intervalo (n=14)\n"
                    "- **VaR histórico**: −quantil(1−nível) dos retornos × √dias · **VaR paramétrico**: z·σ − μ · **EWMA**: σ ponderado (λ=0,94) · **CVaR**: média das perdas além do VaR\n"
                    "- **Drawdown**: valor ÷ máximo anterior − 1 · **Sharpe**: média do excesso sobre o CDI ÷ σ do excesso (anualizado) · **Sortino**: só desvios negativos · **Calmar**: CAGR ÷ |maior queda|\n"
                    "- **Beta**: cov(ativo, benchmark) ÷ var(benchmark) · **Tracking error**: σ(ativo − benchmark) × √252 · **Information ratio**: retorno ativo anualizado ÷ tracking error\n"
                    "- **Concentração**: HHI = Σ(peso²); nº efetivo = 1 ÷ HHI · **Contribuição ao risco**: wᵢ·(Σw)ᵢ ÷ wᵀΣw\n"
                    "- **Liquidez**: ADV = média(preço × volume) 20 pregões; dias = valor ÷ (ADV × 10%); impacto ≈ σ·√(valor ÷ ADV)\n"
                    "- **Estresse**: perda por ativo = beta × choque de mercado, −duration × choque de juros, câmbio, spread, FIIs, exchange e iliquidez (premissas editáveis nos cenários)")
    with st.expander("Fontes de dados"):
        for f in col["fontes"]:
            st.markdown("- " + f)
        st.caption(f"Coleta em {col['quando'][:16].replace('T', ' ')}. Preços com mais de {R.DIAS_DADO_VELHO} dias derrubam a confiança do ativo (ações, FIIs, ETFs, cripto).")
    with st.expander("Limites desta versão"):
        for t in ["Spread e profundidade do livro de ofertas não estão disponíveis nas fontes gratuitas (aparecem como n/d).",
                  "Concentração de tokens, desbloqueios e risco de smart contract (cripto) só entram com dado informado; sem ele o componente fica sem medida.",
                  "Inadimplência, concentração de inquilinos e carteira de CRIs dos FIIs dependem de relatório gerencial; entram só se a base tiver o dado.",
                  "Regulatório, operacional e contraparte são proxies qualitativos por classe e setor, não medidas de mercado.",
                  "Tracking error só é calculado para ETFs com benchmark adequado (Ibovespa ou S&P 500 em R$); fundos ficam sem esse componente.",
                  "Correlações e volatilidades vêm do passado e mudam em crises; os cenários de estresse são hipóteses com betas e durations simplificados.",
                  "Alertas aparecem dentro do app; e-mail e aviso no celular dependem de serviço externo."]:
            st.markdown("- " + t)
    st.caption(R.AVISO_LEGAL)


SUGESTOES = ["Qual o risco da minha carteira?", "Quais são as fragilidades da carteira?", "O que mais contribui para o risco?", "Compare os cenários de estresse",
             "Estou concentrado demais?", "Qual a liquidez da carteira?", "Houve mudança na volatilidade?", "Quais notícias afetam o risco dos meus ativos?"]


def _aba_assistente(col, an):
    st.caption("Responde só com os números já calculados nesta página, citando premissas e limites. Não recomenda compra ou venda.")
    cs = st.columns(2)
    for i, s in enumerate(SUGESTOES):
        if cs[i % 2].button(s, key=f"rk_sug_{i}"):
            _ss()["rk_q"] = s
    q = st.text_input("Pergunte sobre o risco (ex.: “por que PETR4 tem essa nota?”)", key="rk_q", max_chars=300, **_opt("rk_q", "value", ""))
    ctx = contexto_ia(col, an)
    if q and q.strip():
        r = R.responder_risco(q.strip(), ctx)
        st.markdown(f"**{_md(r['texto'])}**")
        for l in r["linhas"]:
            st.markdown("- " + _md(l))
        st.caption(f"{r['referencia']}. {r['consultado']} {r['limite']}")
    st.download_button("Baixar relatório de risco (Markdown)", R.relatorio_md(an["cart"], an["ava"], ctx["cenarios"] if ctx else None, an["limites"], (_ss().get(ALERTAS) or {}).get("novos")).encode("utf-8"),
                       file_name=f"risco_{date.today():%Y%m%d}.md", mime="text/markdown", key="rk_dl")


# =============================================================================== página
def pagina_risco():
    st.markdown(tema.cabecalho("alerta", "Gestão de risco", "Nota de risco por classe, volatilidade, VaR, concentração, correlação, liquidez, estresse, limites e tamanho de posição."), unsafe_allow_html=True)
    ss = _ss()
    reais = [l for l in ss.get("cart_real", []) if isinstance(l, dict)]
    fict = [l for l in ss.get("cart_ficticia", []) if isinstance(l, dict)]
    opcoes = ["Carteira real", "Carteira fictícia"]
    esc = st.radio("Carteira", opcoes, horizontal=True, key="rk_cart", **({} if "rk_cart" in ss else {"index": 0 if (reais or ss.get("cart_rf") or not fict) else 1}))
    chave = "cart_real" if esc == opcoes[0] else "cart_ficticia"
    c1, c2 = st.columns([1, 3])
    clicou = c1.button("Atualizar análise de risco", key="rk_atualizar", type="primary", icon=":material/refresh:")
    c2.caption("Lê sua carteira (Gestão), o histórico de preços e volume, e calcula tudo. Dados com cache de até 1 hora. Nada é negociado.")
    if clicou:
        with st.spinner("Lendo preços, volume e calculando o risco..."):
            try:
                atualizar(chave)
            except Exception as ex:
                log.exception("falha no cálculo de risco")
                st.error(f"O cálculo falhou ({ex.__class__.__name__}). Tente de novo; o problema foi registrado.")
    col = ss.get(RES)
    if col is None or col.get("chave") != chave:
        st.markdown(tema.vazio("alerta", "Clique em “Atualizar análise de risco”", "Usamos as posições da página Carteira (e a renda fixa e os fundos que você cadastrou). Sem posições, não há o que analisar."), unsafe_allow_html=True)
        st.caption(R.AVISO_LEGAL)
        return
    f1, f2, f3 = st.columns([2, 3, 3])
    f1.selectbox("Período dos indicadores", list(PERIODOS), index=1, key="rk_per")
    classes_disp = sorted({p["classe"] for p in col["posicoes"]})
    cls = f2.multiselect("Classes", classes_disp, key="rk_cls", format_func=lambda c: g.CLASSES.get(c, c))
    ats = f3.multiselect("Ativos", [p["id"] for p in col["posicoes"] if not cls or p["classe"] in cls], key="rk_ats")
    lim = _limites_atuais()
    chave_an = repr((col["quando"], tuple(cls), tuple(ats), ss["rk_per"], sorted((k, str(v)) for k, v in lim.items()), repr(ss.get(CH_CFG))))
    cache = ss.get("_risco_an")
    if not cache or cache[0] != chave_an:
        with st.spinner("Calculando..."):
            ss["_risco_an"] = (chave_an, analisar(col, cls, ats, PERIODOS[ss["rk_per"]], lim))
    an = ss["_risco_an"][1]
    if not an["pos"]:
        st.info("Nenhuma posição nos filtros escolhidos.")
        return
    st.caption(f"Dados lidos em {col['quando'][:16].replace('T', ' ')} · metodologia v{R.VERSAO_METODOLOGIA} · {len(an['pos'])} posição(ões).")
    tabs = st.tabs(ABAS)
    fs = [_aba_painel, _aba_ativos, _aba_volatilidade, _aba_indicadores, _aba_concentracao, _aba_correlacao, _aba_liquidez, _aba_estresse, _aba_limites, _aba_posicao, _aba_metodologia, _aba_assistente]
    for t, f in zip(tabs, fs):
        with t:
            try:
                f(col, an)
            except Exception as ex:
                log.exception("falha na aba %s", f.__name__)
                st.error(f"Esta aba falhou ({ex.__class__.__name__}). O restante da página continua funcionando.")
    st.caption(R.AVISO_LEGAL)
