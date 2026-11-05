"""
Passo 14 — Análise técnica avançada (tela).

CAMADAS: coleta (`_baixar`, `_parse_chart`: Yahoo; Binance via `hooks`) → motor (`analise_tecnica.py`, sem Streamlit) → esta tela.
Reaproveita `tecnica.py` (candles e topos/fundos), `intel.py` (alertas e histórico do Passo 13) e a carteira do Passo 12 (via `hooks`).
Nada é comprado ou vendido; nenhum candle, preço ou volume é inventado: dado ausente = indicador indisponível, com o motivo.

`pagina_tecnica_avancada(hooks)` — hooks fornecidos pelo app.py:
    classe_de(codigo) -> "acao"|"fii"|"etf"|"cripto"|...   (classificação do Comparador, Passo 6)
    carteira() -> [{"id","peso","classe"}]                (posições da carteira, Passo 12) ou []
    binance_ohlcv(par, timeframe, limite) -> DataFrame     (opcional; cripto)
    favoritos() -> [códigos]                               (opcional; ativos acompanhados)
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st

import analise_tecnica as T
import intel as I
import tema

CH_CONFIG, CH_REGRAS, CH_HIST, CH_SINAIS = "tec_av_config", "tec_av_regras", "tec_av_hist", "tec_av_sinais"
CH_CACHE_CART, CH_BT = "_tec_cart", "_tec_bt"            # só em memória da sessão
MAX_ATIVOS_ALERTA = 12
MAX_POSICOES = 15

PERIODOS = {"1 mês": 21, "3 meses": 63, "6 meses": 126, "1 ano": 252, "2 anos": 504, "5 anos": 1260, "Tudo": 0}
VISOES = ["Diário", "Semanal", "Mensal", "Anual", "Intraday 5 min", "Intraday 15 min", "Intraday 1 hora"]
_INTRA = {"Intraday 5 min": ("5m", "1mo"), "Intraday 15 min": ("15m", "1mo"), "Intraday 1 hora": ("60m", "3mo")}
_BINANCE_TF = {"Diário": "1d", "Semanal": "1w", "Mensal": "1M", "Anual": "1M", "Intraday 5 min": "5m", "Intraday 15 min": "15m", "Intraday 1 hora": "1h"}
CLASSES_UI = {"Ação": "acao", "ETF": "etf", "FII": "fii", "Criptomoeda": "cripto", "Fundo (cotas, sem volume)": "fundo", "Renda fixa": "renda_fixa"}
REFERENCIAS = {"Ibovespa": "^BVSP", "S&P 500": "^GSPC", "Dólar (BRL=X)": "BRL=X", "Nasdaq": "^IXIC"}
TIPOS_GRAFICO = ["Candlestick", "Linha", "Área", "Barras (OHLC)"]

UP, DOWN, MUTED, ACCENT, GOLD, TEXTO, GRADE = "#6f9c85", "#b0706b", "#8b919c", "#A59DD0", "#c2ad7e", "#cfd3da", "#2c3650"
FUNDO = "#0f1a2f"          # fundo explícito: não depende do tema do navegador (no tablet o fundo saiu branco)
CORES = ["#A59DD0", "#c2ad7e", "#a78bb5", "#6fb0b5", "#d19a66", "#9bb56f", "#c27c8c", "#7f8fa9"]


class _Plotly:
    def __getattr__(self, nome):
        import plotly.graph_objects as _go
        return getattr(_go, nome)


go = _Plotly()


def _make_subplots(*a, **k):
    from plotly.subplots import make_subplots
    return make_subplots(*a, **k)


def _ss():
    return st.session_state


def _opt(chave: str, nome: str, valor) -> dict:
    """Valor inicial só quando a chave ainda não existe na sessão (evita o aviso do Streamlit e o reinício do widget)."""
    return {} if chave in st.session_state else {nome: valor}


def _cartoes(itens: list, por_linha: int = 4):
    for k in range(0, len(itens), por_linha):
        for col, (rot, val, cls, *det) in zip(st.columns(por_linha), itens[k:k + por_linha]):
            col.markdown(tema.card_status(rot, val, cls, det[0] if det else "", det[1] if len(det) > 1 else ""), unsafe_allow_html=True)


def _md(t) -> str:
    return I.escapar_md(t)


def _agora() -> datetime:
    from zoneinfo import ZoneInfo
    try:
        return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    except Exception:
        return datetime.now()


# =============================================================================== coleta
def _simbolo_yahoo(codigo: str, classe: str) -> str:
    c = str(codigo or "").strip().upper().replace(" ", "")
    if classe == "cripto":
        if "/" in c:
            c = c.split("/")[0] + "-USD"
        elif "-" not in c:
            c += "-USD"
        return c
    import dados
    return dados.sym_yf(c)         # B3 leva o sufixo .SA; ações americanas ficam como estão


def _parse_chart(res: dict, intraday: bool = False) -> dict:
    """Resposta da API de gráfico do Yahoo → {'df','adj','div','splits','meta','erro'}. Sem dado devolve erro; nada é preenchido."""
    try:
        ts = res.get("timestamp") or []
        ind = res.get("indicators") or {}
        q = (ind.get("quote") or [{}])[0]
        meta = res.get("meta") or {}
        tz = meta.get("exchangeTimezoneName") or "America/Sao_Paulo"
        idx = pd.to_datetime(ts, unit="s", utc=True).tz_convert(tz).tz_localize(None)
        if not intraday:
            idx = idx.normalize()
        df = pd.DataFrame({"Open": q.get("open"), "High": q.get("high"), "Low": q.get("low"), "Close": q.get("close"), "Volume": q.get("volume")}, index=idx)
        adj = None
        a = (ind.get("adjclose") or [{}])[0].get("adjclose")
        if a:
            adj = pd.Series(a, index=idx, dtype=float)
            adj = adj[~adj.index.duplicated(keep="last")]
        ev = res.get("events") or {}
        divs = pd.Series({pd.to_datetime(int(v["date"]), unit="s").normalize(): float(v["amount"]) for v in (ev.get("dividends") or {}).values()
                          if v.get("amount") is not None and v.get("date") is not None}, dtype=float).sort_index()
        spl = pd.Series({pd.to_datetime(int(v["date"]), unit="s").normalize(): str(v.get("splitRatio") or f"{v.get('numerator')}:{v.get('denominator')}")
                         for v in (ev.get("splits") or {}).values() if v.get("date") is not None}, dtype=object).sort_index()
        rt = meta.get("regularMarketTime")
        atual = (pd.to_datetime(int(rt), unit="s", utc=True).tz_convert(tz).tz_localize(None).isoformat(timespec="minutes") if rt else None)
        return {"df": df, "adj": adj, "div": divs, "splits": spl, "erro": None,
                "meta": {"moeda": meta.get("currency") or "", "fuso": tz, "bolsa": meta.get("exchangeName") or "", "ultimo_negocio": atual,
                         "granularidade": meta.get("dataGranularity") or ""}}
    except Exception as e:
        return {"erro": f"histórico em formato inesperado ({e.__class__.__name__})"}


@st.cache_data(ttl=900, show_spinner=False)
def _baixar(simbolo: str, periodo: str, intervalo: str) -> dict:
    """Histórico do Yahoo (preços, volume, proventos e desdobramentos) com cache curto. Erro não fica em cache útil (ttl curto)."""
    import dados
    res, err = dados._chart_yahoo(simbolo, periodo, intervalo, "div,splits")
    if not res:
        return {"erro": err or "sem dados"}
    return _parse_chart(res, intraday=intervalo.endswith("m") and intervalo != "1mo")


def _ajustar_proventos(df: pd.DataFrame, adj: pd.Series | None) -> tuple[pd.DataFrame, bool]:
    if adj is None or len(adj) == 0:
        return df, False
    f = (adj.reindex(df.index) / df["Close"]).where(lambda s: s > 0)
    if f.notna().mean() < 0.9:
        return df, False
    f = f.ffill().bfill()
    out = df.copy()
    for c in ("Open", "High", "Low", "Close"):
        if c in out.columns:
            out[c] = out[c] * f
    return out, True


def carregar(codigo: str, classe: str, visao: str, ajustar: bool, hooks: dict, usar_binance: bool = True) -> dict:
    """Coleta + validação. Devolve {'df' (histórico completo, validado), 'rel', 'meta', 'div', 'splits', 'lacunas', 'avisos', 'erro'}.
    Cripto tenta a Binance (par à vista) e cai para o Yahoo se ela não responder."""
    out = {"df": None, "rel": None, "meta": None, "div": pd.Series(dtype=float), "splits": pd.Series(dtype=object), "lacunas": [], "avisos": [], "erro": None}
    cod = str(codigo or "").strip().upper()
    if not cod:
        out["erro"] = "Informe um código."
        return out
    raw, fonte, moeda, fuso, atrasado, ajustado, obs, atualizado = None, "Yahoo Finance", "BRL", "America/Sao_Paulo", True, False, "", None
    freq_txt = "diário"
    intra = visao in _INTRA
    try:
        if classe == "cripto" and usar_binance and hooks.get("binance_ohlcv"):
            par = cod.replace("-", "/") if "/" in cod or "-" in cod else f"{cod}/USDT"
            if par.endswith("/USD"):
                par += "T"
            try:
                raw = hooks["binance_ohlcv"](par, _BINANCE_TF[visao], 1000)
                fonte, moeda, fuso, atrasado, freq_txt = f"Binance (par {par}, à vista)", par.split("/")[1], "America/Sao_Paulo", False, visao.lower()
                obs = "Preço e volume refletem este par e esta exchange; outras exchanges e pares podem diferir."
                atualizado = _agora().isoformat(timespec="minutes")
            except Exception as e:
                out["avisos"].append(f"Binance indisponível ({e.__class__.__name__}); usando o Yahoo Finance (preço agregado em dólar).")
                raw = None
        if raw is None:
            simb = _simbolo_yahoo(cod, classe)
            if intra:
                iv, per = _INTRA[visao]
                b = _baixar(simb, per, iv)
                freq_txt = visao.lower()
            else:
                b = _baixar(simb, "10y" if visao == "Diário" else "max", "1d")
                freq_txt = "diário" if visao == "Diário" else f"{visao.lower()} (agregado do diário)"
            if b.get("erro"):
                out["erro"] = f"Não consegui o histórico de {cod} agora ({b['erro']})."
                return out
            raw, mt = b["df"], b["meta"]
            moeda, fuso = mt["moeda"] or ("USD" if classe == "cripto" else "BRL"), mt["fuso"]
            atualizado = mt.get("ultimo_negocio")
            atrasado = None if classe == "cripto" else (False if intra and classe == "cripto" else True)
            out["div"], out["splits"] = b["div"], b["splits"]
            obs = "Preços ajustados por desdobramentos e grupamentos pela fonte." + (" Cripto no Yahoo é preço agregado em dólar." if classe == "cripto" else "")
            if ajustar and not intra and classe != "cripto":
                raw, ajustado = _ajustar_proventos(raw, b["adj"])
                if not ajustado:
                    out["avisos"].append("Ajuste por proventos indisponível nesta série: preços sem ajuste de proventos.")
    except Exception as e:
        out["erro"] = f"Falha ao coletar dados ({e.__class__.__name__})."
        return out
    df, rel = T.limpar_ohlcv(raw)
    if df.empty:
        out["erro"] = "A fonte não devolveu candles válidos para este código."
        out["rel"] = rel
        return out
    if visao in ("Semanal", "Mensal", "Anual") and not intra:
        df = T.reamostrar(df, {"Semanal": "W", "Mensal": "M", "Anual": "Y"}[visao])
        rel = {**rel, "n": len(df), "primeira": T._dia(df.index[0]), "ultima": T._dia(df.index[-1])}
    out["df"], out["rel"] = df, rel
    out["avisos"] += rel["problemas"]
    out["lacunas"] = T.detectar_lacunas(df.index, T.inferir_frequencia(df.index), cripto=classe == "cripto")
    out["meta"] = T.meta_fonte(fonte, freq_txt, moeda, atrasado, ajustado if classe != "cripto" else None, fuso, atualizado, obs)
    return out


def carregar_diario_simples(codigo: str, classe: str, hooks: dict) -> pd.DataFrame | None:
    """Histórico diário validado (para carteira e alertas). None se a fonte falhar."""
    r = carregar(codigo, classe, "Diário", False, hooks, usar_binance=False)
    return r["df"] if r["df"] is not None and not r["erro"] else None


# =============================================================================== gráficos
def _eixos_comuns(fig, intradia: bool, cripto: bool, n_linhas: int):
    breaks = [] if (intradia or cripto) else [{"bounds": ["sat", "mon"]}]
    fig.update_xaxes(showgrid=True, gridcolor=GRADE, rangebreaks=breaks, showspikes=True, spikemode="across", spikethickness=1)
    fig.update_yaxes(showgrid=True, gridcolor=GRADE, zeroline=False)


def _hover_fmt(moeda: str) -> str:
    return "%{y:,.2f}"


def construir_figura(df: pd.DataFrame, cfg: dict, resumo: dict | None, janela_n: int, eventos: dict | None, moeda: str, classe: str,
                     titulo: str = "") -> tuple[object, list[str]]:
    """Gráfico principal. Indicadores são calculados no histórico COMPLETO (aquecimento) e só então cortados para o período mostrado.
    Devolve (figura, avisos). Indicador indisponível vira aviso, nunca curva inventada."""
    avisos: list[str] = []
    n_total = len(df)
    ini = max(0, n_total - janela_n) if janela_n else 0
    v = df.iloc[ini:]
    tem_ohlc = {"Open", "High", "Low"}.issubset(df.columns)
    tem_vol = "Volume" in df.columns
    tipo = cfg.get("tipo", "Candlestick")
    if tipo in ("Candlestick", "Barras (OHLC)") and not tem_ohlc:
        avisos.append("Esta série só tem fechamento (sem abertura, máxima e mínima): exibindo linha.")
        tipo = "Linha"
    subs, over = [], []
    for item in cfg.get("indicadores") or []:
        ind, motivo = T.tentar(item["nome"], df, **item.get("params", {}))
        rot = _rotulo_ind(item)
        if ind is None:
            avisos.append(f"{rot}: {motivo}")
            continue
        (over if T.INDICADORES[item["nome"]]["painel"] == "preco" else subs).append((item, ind.iloc[ini:], rot))
    if len(subs) > 4:
        avisos.append("Mais de 4 indicadores em painéis separados: mostrando os 4 primeiros (reduza a seleção para ver os demais).")
        subs = subs[:4]
    painel_vol = bool(cfg.get("volume", True) and tem_vol)
    n_rows = 1 + (1 if painel_vol else 0) + len(subs)
    alturas = [0.55] + ([0.15] if painel_vol else []) + [0.30 / max(1, len(subs))] * len(subs)
    s = sum(alturas)
    fig = _make_subplots(rows=n_rows, cols=1, shared_xaxes=True, vertical_spacing=0.02, row_heights=[a / s for a in alturas])
    x = v.index
    if tipo == "Candlestick":
        fig.add_trace(go.Candlestick(x=x, open=v["Open"], high=v["High"], low=v["Low"], close=v["Close"], name="Preço", increasing_line_color=UP, decreasing_line_color=DOWN,
                                     increasing_fillcolor=UP, decreasing_fillcolor=DOWN), row=1, col=1)
    elif tipo == "Barras (OHLC)":
        fig.add_trace(go.Ohlc(x=x, open=v["Open"], high=v["High"], low=v["Low"], close=v["Close"], name="Preço", increasing_line_color=UP, decreasing_line_color=DOWN), row=1, col=1)
    elif tipo == "Área":
        fig.add_trace(go.Scatter(x=x, y=v["Close"], name="Fechamento", mode="lines", line={"color": ACCENT, "width": 1.6}, fill="tozeroy", fillcolor="rgba(138,160,184,0.12)"), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(x=x, y=v["Close"], name="Fechamento", mode="lines", line={"color": ACCENT, "width": 1.8}), row=1, col=1)
    ci = 0
    for item, ind, rot in over:
        nome = item["nome"]
        if nome == "BOLLINGER":
            for c, dash in (("BOLL_SUP", "dot"), ("BOLL_INF", "dot")):
                fig.add_trace(go.Scatter(x=x, y=ind[c], name=f"{rot} {'sup.' if c.endswith('SUP') else 'inf.'}", mode="lines", line={"color": CORES[ci % 8], "width": 1, "dash": dash}), row=1, col=1)
            fig.add_trace(go.Scatter(x=x, y=ind["BOLL_MEDIA"], name=f"{rot} média", mode="lines", line={"color": CORES[ci % 8], "width": 1}), row=1, col=1)
        elif nome == "ICHIMOKU":
            fig.add_trace(go.Scatter(x=x, y=ind["SENKOU_A"], name="Senkou A", mode="lines", line={"color": "rgba(111,156,133,0.6)", "width": 1}), row=1, col=1)
            fig.add_trace(go.Scatter(x=x, y=ind["SENKOU_B"], name="Senkou B", mode="lines", line={"color": "rgba(176,112,107,0.6)", "width": 1}, fill="tonexty", fillcolor="rgba(139,145,156,0.12)"), row=1, col=1)
            fig.add_trace(go.Scatter(x=x, y=ind["TENKAN"], name="Tenkan", mode="lines", line={"color": ACCENT, "width": 1}), row=1, col=1)
            fig.add_trace(go.Scatter(x=x, y=ind["KIJUN"], name="Kijun", mode="lines", line={"color": GOLD, "width": 1}), row=1, col=1)
        else:
            for c in [c for c in ind.columns if c != "CHIKOU"]:
                fig.add_trace(go.Scatter(x=x, y=ind[c], name=rot if len(ind.columns) == 1 else f"{rot} {c.split('_')[-1].lower()}", mode="lines",
                                         line={"color": CORES[ci % 8], "width": 1.3}), row=1, col=1)
        ci += 1
    if cfg.get("niveis", True) and resumo and resumo.get("niveis"):
        for z in (resumo["niveis"]["suportes"] + resumo["niveis"]["resistencias"]):
            cor = "rgba(111,156,133,0.16)" if z["tipo"] == "Suporte" else "rgba(176,112,107,0.16)"
            fig.add_hrect(y0=z["zona"][0], y1=z["zona"][1] if z["zona"][1] > z["zona"][0] else z["zona"][0] * 1.002, fillcolor=cor, line_width=0, layer="below", row=1, col=1)
            fig.add_hline(y=z["preco"], line={"color": UP if z["tipo"] == "Suporte" else DOWN, "width": 1, "dash": "dot"}, row=1, col=1,
                          annotation_text=f"{z['tipo']} {z['preco']:,.2f} ({z['toques']}x)", annotation_position="top left", annotation_font_size=11, annotation_font_color="#ffffff", annotation_bgcolor="rgba(15,26,47,0.75)")
    if cfg.get("tendencia", True):
        for lt in T.linhas_de_tendencia(df):
            a0, p0, a1, p1 = lt["linha"]
            a0, p0 = _cortar_inicio(a0, p0, a1, p1, v.index[0])
            if a0 is None:
                continue
            fig.add_trace(go.Scatter(x=[a0, a1], y=[p0, p1], mode="lines", name=lt["tipo"], line={"color": GOLD, "width": 1.2, "dash": "dash"}), row=1, col=1)
    if cfg.get("padroes", True) and resumo and resumo.get("padroes"):
        for p in resumo["padroes"][:4]:
            if p["estado"] == "invalidado":
                continue
            r = dict(p["regiao"])
            if pd.Timestamp(r["x1"]) < v.index[0]:
                continue                                  # padrão antigo, fora do período mostrado
            r["x0"] = max(pd.Timestamp(r["x0"]), v.index[0])
            fig.add_shape(type="rect", x0=r["x0"], x1=r["x1"], y0=r["y0"], y1=r["y1"], line={"color": "rgba(194,173,126,0.8)", "width": 1, "dash": "dot"}, row=1, col=1)
            fig.add_annotation(x=r["x1"], y=r["y1"], text=f"{p['nome']} ({p['estado']})", showarrow=False, font={"size": 10, "color": GOLD}, xanchor="right", yanchor="bottom", row=1, col=1)
            for a0, p0, a1, p1 in p["linhas"]:
                a0, p0 = _cortar_inicio(a0, p0, a1, p1, v.index[0])
                if a0 is None:
                    continue
                fig.add_trace(go.Scatter(x=[a0, a1], y=[p0, p1], mode="lines", line={"color": GOLD, "width": 1}, showlegend=False, hoverinfo="skip"), row=1, col=1)
    if cfg.get("extremos", True) and len(v):
        hi = v["High"] if tem_ohlc else v["Close"]
        lo = v["Low"] if tem_ohlc else v["Close"]
        fig.add_annotation(x=hi.idxmax(), y=float(hi.max()), text=f"Máx {hi.max():,.2f}", showarrow=True, arrowhead=2, ay=-28, font={"size": 10, "color": TEXTO}, row=1, col=1)
        fig.add_annotation(x=lo.idxmin(), y=float(lo.min()), text=f"Mín {lo.min():,.2f}", showarrow=True, arrowhead=2, ay=28, font={"size": 10, "color": TEXTO}, row=1, col=1)
    if cfg.get("eventos", True) and eventos:
        d = eventos.get("div")
        if d is not None and len(d):
            d = d[(d.index >= v.index[0]) & (d.index <= v.index[-1])]
            if len(d):
                base = (v["Low"] if tem_ohlc else v["Close"]).reindex(d.index, method="nearest")
                fig.add_trace(go.Scatter(x=d.index, y=base * 0.985, mode="markers", name="Proventos", marker={"symbol": "triangle-up", "size": 9, "color": GOLD},
                                         text=[f"Provento {moeda} {val:,.4f}" for val in d.values], hoverinfo="text+x"), row=1, col=1)
        s_ = eventos.get("splits")
        if s_ is not None and len(s_):
            s_ = s_[(s_.index >= v.index[0]) & (s_.index <= v.index[-1])]
            if len(s_):
                fig.add_trace(go.Scatter(x=s_.index, y=v["Close"].reindex(s_.index, method="nearest"), mode="markers+text", name="Desdobramento/grupamento",
                                         marker={"symbol": "diamond", "size": 10, "color": ACCENT}, text=[str(t) for t in s_.values], textposition="top center"), row=1, col=1)
    if resumo and resumo.get("sinais") and cfg.get("sinais", True) and len(v):
        tit = [s["titulo"] for s in resumo["sinais"] if s["tipo"] != "sem_sinal"]
        if tit:
            fig.add_trace(go.Scatter(x=[v.index[-1]], y=[float(v["Close"].iloc[-1])], mode="markers", name="Sinais do último candle",
                                     marker={"symbol": "star", "size": 12, "color": GOLD}, text=["<br>".join(tit)], hoverinfo="text"), row=1, col=1)
    row = 2
    if painel_vol:
        cores = [UP if c >= o else DOWN for o, c in zip(v["Open"] if tem_ohlc else v["Close"].shift(1).fillna(v["Close"]), v["Close"])]
        fig.add_trace(go.Bar(x=x, y=v["Volume"], name="Volume", marker={"color": cores, "opacity": 0.7}), row=row, col=1)
        fig.update_yaxes(title_text="Volume", row=row, col=1)
        row += 1
    for item, ind, rot in subs:
        nome = item["nome"]
        esp = T.INDICADORES[nome]
        for c in ind.columns:
            if c == "MACD_HIST":
                fig.add_trace(go.Bar(x=x, y=ind[c], name="Histograma", marker={"color": [UP if (z or 0) >= 0 else DOWN for z in ind[c]], "opacity": 0.6}), row=row, col=1)
            elif c in ("OBV", "AD") or True:
                if c in ("ATR_PCT", "DESVIO_PCT", "VOL_RAZAO", "BOLL_LARG", "BOLL_B") and len(ind.columns) > 1:
                    continue
                fig.add_trace(go.Scatter(x=x, y=ind[c], name=f"{rot} {c.split('_')[-1].lower()}" if len(ind.columns) > 1 else rot, mode="lines",
                                         line={"color": CORES[(ci + row) % 8], "width": 1.3}), row=row, col=1)
        for ref in esp.get("linhas", ()):
            fig.add_hline(y=ref, line={"color": MUTED, "width": 1, "dash": "dot"}, row=row, col=1)
        if esp.get("faixa"):
            fig.update_yaxes(range=list(esp["faixa"]), row=row, col=1)
        fig.update_yaxes(title_text=nome.title() if len(nome) > 4 else nome, row=row, col=1)
        row += 1
    intradia = T.inferir_frequencia(df.index) == "intra"
    _eixos_comuns(fig, intradia, classe == "cripto", n_rows)
    altura = int(560 + 150 * (n_rows - 1)) if cfg.get("altura", "Média") == "Média" else int({"Compacta": 440, "Alta": 760}.get(cfg.get("altura"), 560) + 150 * (n_rows - 1))
    botoes = [] if intradia else [{"count": 1, "label": "1m", "step": "month", "stepmode": "backward"}, {"count": 3, "label": "3m", "step": "month", "stepmode": "backward"},
                                   {"count": 6, "label": "6m", "step": "month", "stepmode": "backward"}, {"count": 1, "label": "1a", "step": "year", "stepmode": "backward"},
                                   {"step": "all", "label": "tudo"}]
    fig.update_layout(template="plotly_dark", height=altura, margin={"l": 8, "r": 8, "t": 30, "b": 70}, paper_bgcolor=FUNDO, plot_bgcolor=FUNDO, font={"color": TEXTO, "size": 12},
                      hovermode="x unified", dragmode="pan", xaxis_rangeslider_visible=False,
                      legend={"orientation": "h", "yanchor": "top", "y": -0.04, "x": 0, "font": {"size": 10, "color": TEXTO}})
    if len(v) > 1:
        fig.update_xaxes(autorange=False, range=[v.index[0].strftime("%Y-%m-%d %H:%M:%S"), (v.index[-1] + (v.index[-1] - v.index[-2]) * 2).strftime("%Y-%m-%d %H:%M:%S")])
    fig.update_xaxes(tickfont={"color": "#ffffff"}).update_yaxes(tickfont={"color": "#ffffff"})
    fig.update_annotations(font_color="#ffffff")
    return fig, avisos


def _cortar_inicio(a0, p0, a1, p1, inicio):
    """Corta o início de uma reta que começa antes do período mostrado (sem isso o eixo do tempo se estica e os candles ficam espremidos)."""
    t0, t1 = pd.Timestamp(a0), pd.Timestamp(a1)
    if t1 < inicio:
        return None, None
    if t0 >= inicio or t1 == t0:
        return t0, p0
    return inicio, p0 + (p1 - p0) * ((inicio - t0) / (t1 - t0))


def _rotulo_ind(item: dict) -> str:
    ps = ",".join(str(v) for v in (item.get("params") or {}).values())
    return f"{item['nome']}({ps})" if ps else item["nome"]


CONFIG_PLOTLY = {"displaylogo": False, "scrollZoom": True, "responsive": True,
                 "modeBarButtonsToRemove": ["select2d", "lasso2d", "autoScale2d"]}


def figura_comparacao(series: dict[str, pd.Series], titulo: str = "") -> object:
    """Linhas rebaseadas em 100 na primeira data em comum a TODAS as séries (comparação justa, sem preencher lacunas)."""
    m = pd.concat([s.rename(k) for k, s in series.items()], axis=1, join="inner").dropna()
    fig = go.Figure()
    if len(m):
        base = m / m.iloc[0] * 100
        for i, c in enumerate(base.columns):
            fig.add_trace(go.Scatter(x=base.index, y=base[c], name=c, mode="lines", line={"width": 2 if i == 0 else 1.4, "color": CORES[i % 8]}))
    fig.update_layout(template="plotly_dark", height=460, margin={"l": 8, "r": 8, "t": 36, "b": 8}, paper_bgcolor=FUNDO, plot_bgcolor=FUNDO, hovermode="x unified", dragmode="pan",
                      title={"text": titulo, "x": 0.01, "font": {"size": 14}}, font={"color": TEXTO}, legend={"orientation": "h", "y": 1.02, "x": 0},
                      yaxis={"title": "Base 100", "gridcolor": GRADE}, xaxis={"gridcolor": GRADE})
    return fig


def figura_backtest(df: pd.DataFrame, res: dict) -> object:
    """Preço com as entradas e saídas simuladas; curva do capital × comprar e manter; drawdown."""
    eq = res["equity"]
    fig = _make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.45, 0.35, 0.20])
    v = df.loc[eq.index[0]:eq.index[-1]]
    fig.add_trace(go.Scatter(x=v.index, y=v["Close"], name="Preço", mode="lines", line={"color": ACCENT, "width": 1.4}), row=1, col=1)
    ent = [t for t in res["trades"]]
    if ent:
        fig.add_trace(go.Scatter(x=[pd.Timestamp(t["entrada_data"]) for t in ent], y=[t["entrada_preco"] for t in ent], mode="markers", name="Entrada simulada",
                                 marker={"symbol": "triangle-up", "size": 10, "color": UP}), row=1, col=1)
        fig.add_trace(go.Scatter(x=[pd.Timestamp(t["saida_data"]) for t in ent], y=[t["saida_preco"] for t in ent], mode="markers", name="Saída simulada",
                                 marker={"symbol": "triangle-down", "size": 10, "color": DOWN},
                                 text=[f"{t['motivo_saida']} · {t['retorno_pct']:+.1f}%" for t in ent], hoverinfo="text+x"), row=1, col=1)
    fig.add_trace(go.Scatter(x=eq.index, y=eq, name="Estratégia", mode="lines", line={"color": GOLD, "width": 1.8}), row=2, col=1)
    bh = (res.get("benchmark") or {}).get("comprar_e_manter", {}).get("serie")
    if bh is not None:
        fig.add_trace(go.Scatter(x=bh.index, y=bh, name="Comprar e manter", mode="lines", line={"color": MUTED, "width": 1.3, "dash": "dot"}), row=2, col=1)
    dd = (eq / eq.cummax() - 1) * 100
    fig.add_trace(go.Scatter(x=dd.index, y=dd, name="Drawdown (%)", mode="lines", fill="tozeroy", line={"color": DOWN, "width": 1}, fillcolor="rgba(176,112,107,0.25)"), row=3, col=1)
    fig.update_layout(template="plotly_dark", height=700, margin={"l": 8, "r": 8, "t": 24, "b": 8}, paper_bgcolor=FUNDO, plot_bgcolor=FUNDO, hovermode="x unified", dragmode="pan",
                      font={"color": TEXTO}, legend={"orientation": "h", "y": 1.04, "x": 0})
    fig.update_xaxes(gridcolor=GRADE)
    fig.update_yaxes(gridcolor=GRADE)
    return fig


# =============================================================================== estado, configuração salva
_SALVAR = ["tecav_tipo", "tecav_vol", "tecav_ind", "tecav_ma_tipos", "tecav_ma_n", "tecav_tend", "tecav_niv", "tecav_pad", "tecav_ext", "tecav_ev", "tecav_sin",
           "tecav_altura", "tecav_periodo", "tecav_visao", "tecav_ajuste"]


def _restaurar_config():
    ss = _ss()
    cfg = ss.get(CH_CONFIG)
    if isinstance(cfg, dict) and not ss.get("_tecav_restaurado"):
        for k, v in cfg.items():
            if k in _SALVAR and k not in ss:
                ss[k] = v
        for k, v in (cfg.get("_params") or {}).items():
            if k not in ss:
                ss[k] = v
    ss["_tecav_restaurado"] = True


def _salvar_config():
    ss = _ss()
    cfg = {k: ss[k] for k in _SALVAR if k in ss}
    cfg["_params"] = {k: v for k, v in ss.items() if str(k).startswith("tecav_p_") and isinstance(v, (int, float, str, bool))}
    ss[CH_CONFIG] = cfg


def _limpar_config():
    ss = _ss()
    for k in [k for k in list(ss.keys()) if str(k).startswith("tecav_") and k != "tecav_ativo"]:
        del ss[k]
    ss.pop(CH_CONFIG, None)


# =============================================================================== formulários de configuração
def _params_ui(nome: str, rotulo_prefixo: str = "") -> dict:
    esp = T.INDICADORES[nome]
    out = {}
    cols = st.columns(max(1, min(3, len(esp["params"])))) if esp["params"] else []
    for col, (k, s) in zip(cols * 2 if cols else [], esp["params"].items()):
        chave = f"tecav_p_{nome}_{k}"
        if isinstance(s["padrao"], float):
            out[k] = col.number_input(s["rotulo"], min_value=float(s["min"]), max_value=float(s["max"]), step=0.5, key=chave, **_opt(chave, "value", float(s["padrao"])))
        else:
            out[k] = int(col.number_input(s["rotulo"], min_value=int(s["min"]), max_value=int(s["max"]), step=1, key=chave, **_opt(chave, "value", int(s["padrao"]))))
    return out


def _cfg_grafico(perfil: dict) -> dict:
    """Lê os controles do gráfico (dentro do expander) e monta a configuração."""
    perm = perfil["permitidos"]
    cfg: dict = {}
    c1, c2, c3 = st.columns(3)
    cfg["tipo"] = c1.selectbox("Tipo de gráfico", TIPOS_GRAFICO, key="tecav_tipo")
    cfg["altura"] = c2.selectbox("Altura", ["Compacta", "Média", "Alta"], key="tecav_altura", **_opt("tecav_altura", "index", 1))
    cfg["volume"] = c3.toggle("Volume negociado", key="tecav_vol", **_opt("tecav_vol", "value", True))
    cfg["indicadores"] = []
    mm = [n for n in ("SMA", "EMA", "WMA") if n in perm]
    if mm:
        a, b = st.columns([1.3, 1])
        tipos = a.multiselect("Médias móveis", mm, key="tecav_ma_tipos", **_opt("tecav_ma_tipos", "default", ["SMA"]))
        txt = b.text_input("Períodos (separe por vírgula)", key="tecav_ma_n", **_opt("tecav_ma_n", "value", "20,50"), help="Ex.: 9,21 ou 20,50,200")
        periodos = []
        for p in re.split(r"[,\s;]+", txt or ""):
            if p.isdigit() and 2 <= int(p) <= 400 and int(p) not in periodos:
                periodos.append(int(p))
        for t in tipos:
            for p in periodos[:4]:
                cfg["indicadores"].append({"nome": t, "params": {"n": p}})
    outros = [n for n in perm if n not in ("SMA", "EMA", "WMA")]
    if outros:
        sel = st.multiselect("Outros indicadores (escolha quantos quiser)", outros, key="tecav_ind", format_func=lambda n: f"{T.INDICADORES[n]['grupo']} · {T.INDICADORES[n]['nome']}")
        for n in sel:
            if T.INDICADORES[n]["params"]:
                with st.expander(f"Parâmetros · {T.INDICADORES[n]['nome']}"):
                    p = _params_ui(n)
            else:
                p = {}
            cfg["indicadores"].append({"nome": n, "params": p})
    st.caption("Indicadores indisponíveis para este ativo (sem máxima/mínima, sem volume ou classe inadequada): " +
               (", ".join(f"{n} ({m})" for n, m in list(perfil["bloqueados"].items())[:6]) or "nenhum") if perfil["bloqueados"] else "")
    t1, t2, t3 = st.columns(3)
    cfg["tendencia"] = t1.toggle("Linhas de tendência", key="tecav_tend", **_opt("tecav_tend", "value", True))
    cfg["niveis"] = t2.toggle("Suportes e resistências", key="tecav_niv", **_opt("tecav_niv", "value", True))
    cfg["padroes"] = t3.toggle("Padrões gráficos", key="tecav_pad", **_opt("tecav_pad", "value", True))
    t4, t5, t6 = st.columns(3)
    cfg["extremos"] = t4.toggle("Máximas e mínimas", key="tecav_ext", **_opt("tecav_ext", "value", True))
    cfg["eventos"] = t5.toggle("Proventos e desdobramentos", key="tecav_ev", **_opt("tecav_ev", "value", True))
    cfg["sinais"] = t6.toggle("Marcar sinais", key="tecav_sin", **_opt("tecav_sin", "value", True))
    b1, b2 = st.columns(2)
    b1.button("💾 Salvar esta configuração", key="tecav_salvar", on_click=_salvar_config)
    b2.button("Restaurar padrão", key="tecav_restaurar", on_click=_limpar_config)
    if _ss().get(CH_CONFIG):
        st.caption("Configuração salva: volta automaticamente quando você abrir esta página.")
    return cfg


def _tabela_valores(df: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    linhas = []
    for item in cfg.get("indicadores") or []:
        ind, motivo = T.tentar(item["nome"], df, **item.get("params", {}))
        rot = _rotulo_ind(item)
        if ind is None:
            linhas.append({"Indicador": rot, "Valor atual": "indisponível", "Leitura": motivo})
            continue
        for c in ind.columns:
            if c == "CHIKOU":
                continue
            val = ind[c].iloc[-1]
            if not T._ok(val):
                continue
            leitura = ""
            if c in T.ZONAS:
                lo, hi = T.ZONAS[c]
                leitura = "sobrecompra" if val >= hi else "sobrevenda" if val <= lo else "zona neutra"
            elif c == "MACD_HIST":
                leitura = "momento de alta" if val > 0 else "momento de baixa"
            elif c == "ADX":
                leitura = "tendência definida" if val >= 25 else "pouca força" if val < 20 else "força moderada"
            linhas.append({"Indicador": f"{rot} · {c}", "Valor atual": T.fmt_num(val, 2), "Leitura": leitura})
    return pd.DataFrame(linhas)


# =============================================================================== abas
def _cls_tend(t):
    return {"alta": "good", "baixa": "bad", "lateral": "fair"}.get(t, "na")


def _aba_grafico(X):
    df, r, cfg, hooks = X["df"], X["resumo"], X["cfg"], X["hooks"]
    ativo, moeda = X["ativo"], X["moeda"]
    modo = st.segmented_control("Visão", ["Preço do ativo", "Comparar com outros ativos e índices"], default="Preço do ativo", key="tecav_modo", label_visibility="collapsed") or "Preço do ativo"
    if modo.startswith("Comparar"):
        _comparar(X)
    else:
        fig, avisos = construir_figura(df, cfg, r, X["janela"], {"div": X["dados"]["div"], "splits": X["dados"]["splits"]}, moeda, X["classe"], f"{ativo} · {X['visao']}")
        st.plotly_chart(fig, width="stretch", config=CONFIG_PLOTLY, theme=None, key=f"tecav_fig_{ativo}_{X['visao']}")
        for a in avisos:
            st.caption("⚠️ " + _md(a))
        tab = _tabela_valores(df, cfg)
        if len(tab):
            with st.expander("Valores atuais e comparação entre indicadores"):
                st.dataframe(tab, hide_index=True, width="stretch")
        if cfg["indicadores"]:
            with st.expander("O que significam os indicadores escolhidos"):
                for nome in dict.fromkeys(i["nome"] for i in cfg["indicadores"]):
                    e = T.INDICADORES[nome]
                    st.markdown(f"**{e['nome']}** ({e['grupo']}): {e['explicacao']}")
    _assistente(X)


def _comparar(X):
    ativo, hooks, classe = X["ativo"], X["hooks"], X["classe"]
    st.caption("As séries são rebaseadas em 100 na primeira data em comum a todas. Só dados reais; datas sem negociação em algum ativo ficam de fora.")
    c1, c2 = st.columns([1.4, 1])
    extra = c1.text_input("Outros ativos (separe por vírgula)", key="tecav_comp_extra", placeholder="VALE3, BOVA11, HGLG11")
    refs = c2.multiselect("Índices de referência", list(REFERENCIAS), key="tecav_comp_refs", **_opt("tecav_comp_refs", "default", ["Ibovespa"]))
    nomes = [x for x in re.split(r"[,\s;]+", extra or "") if x][:5]
    series = {ativo: X["df"]["Close"]}
    falhas = []
    ini = X["df"].index[max(0, len(X["df"]) - X["janela"])] if X["janela"] else X["df"].index[0]
    for nm in nomes:
        cl = hooks["classe_de"](nm) if hooks.get("classe_de") else "acao"
        d = carregar_diario_simples(nm, _classe_ui(cl), hooks)
        if d is None:
            falhas.append(nm)
        else:
            series[nm.upper()] = d["Close"]
    for rf in refs:
        d = carregar_diario_simples(REFERENCIAS[rf], "acao", hooks)
        if d is None:
            falhas.append(rf)
        else:
            series[rf] = d["Close"]
    for f in falhas:
        st.caption(f"⚠️ Sem dados de {f} agora; ficou fora da comparação.")
    series = {k: s[s.index >= ini] for k, s in series.items()}
    if len(series) < 2:
        st.info("Adicione ao menos um ativo ou índice para comparar.")
        return
    st.plotly_chart(figura_comparacao(series, f"{ativo} × outros (base 100)"), width="stretch", config=CONFIG_PLOTLY, theme=None, key="tecav_fig_comp")
    m = pd.concat([s.rename(k) for k, s in series.items()], axis=1, join="inner").dropna()
    if len(m) >= 2:
        ret = (m.iloc[-1] / m.iloc[0] - 1) * 100
        st.dataframe(pd.DataFrame({"Ativo/índice": ret.index, "Retorno no período (%)": ret.round(1).values}), hide_index=True, width="stretch")
        if len(m) >= 30 and m.shape[1] >= 2:
            cr = m.pct_change().dropna().corr().round(2)
            with st.expander("Correlação entre os retornos diários"):
                st.dataframe(cr, width="stretch")


def _classe_ui(classe: str) -> str:
    return T._classe_tec(classe)


def _aba_sinais(X):
    r = X["resumo"]
    t, mt, o, v, vol, liq = r["tendencia"], r["multitemporal"], r["osciladores"], r["volatilidade"], r["volume"], r.get("liquidez") or {}
    _cartoes([("Tendência", (t["tendencia"] or "n/d").capitalize(), _cls_tend(t["tendencia"]), f"confiança {t['confianca'] or 'n/d'}" + (" · critérios divergentes" if t.get("divergentes") else "")),
              ("Multitemporal", {"concordam_alta": "Concordam: alta", "concordam_baixa": "Concordam: baixa", "concordam_lateral": "Concordam: lateral", "divergem": "Divergem",
                                 "parcial": "Parcial", "insuficiente": "Insuficiente"}[mt["concordancia"]], {"concordam_alta": "good", "concordam_baixa": "bad", "divergem": "bad"}.get(mt["concordancia"], "fair"), "curto, médio e longo prazo"),
              ("Osciladores", o["geral"].capitalize(), {"sobrecompra": "bad", "sobrevenda": "fair"}.get(o["geral"], "good"), f"{len(o['itens'])} indicador(es)"),
              ("Volatilidade", "Elevada" if v["elevada"] else "Normal", "bad" if v["elevada"] else "good", f"20/120 = {T.fmt_num(v['razao_20_120'], 1)}×" if v["razao_20_120"] else "sem dado suficiente")])
    _cartoes([("Volume", (vol["estado"] or "n/d").capitalize(), {"alto": "fair", "baixo": "fair"}.get(vol["estado"], "good" if vol["disponivel"] else "na"), f"{T.fmt_num(vol['razao'], 1)}× a mediana" if vol["razao"] else "sem volume confiável"),
              ("Liquidez", (liq.get("nivel") or "n/d").replace("_", " ").capitalize(), {"adequada": "good", "baixa": "fair", "muito_baixa": "bad"}.get(liq.get("nivel"), "na"), "pelo volume financeiro"),
              ("Consolidação", "Sim" if (r.get("consolidacao") or {}).get("ativa") else "Não", "fair" if (r.get("consolidacao") or {}).get("ativa") else "info", "bandas estreitas e ADX baixo"),
              ("Sinais", str(len([s for s in r["sinais"] if s["tipo"] != "sem_sinal"])), "info", f"dados até {r.get('ate')}")])
    for a in r["avisos"]:
        if "lacuna" not in a:
            st.caption("⚠️ " + _md(a))
    st.markdown("#### Sinais identificados")
    st.caption("Cada sinal mostra o que o sustenta e o que o invalida. Não são recomendações de compra ou venda e não garantem resultado.")
    for s in r["sinais"]:
        ic = {1: "🟢", -1: "🔴"}.get(s["direcao"], "⚪")
        with st.expander(f"{ic} {s['titulo']} · evidência {s['confianca']}", expanded=s["tipo"] != "sem_sinal"):
            st.markdown(f"**Ativo:** {_md(s['ativo'])}  \n**Indicadores:** {_md(', '.join(s['indicadores']) or '—')}  \n**Período analisado:** {_md(s['periodo'])}")
            st.markdown(f"**Justificativa:** {_md(s['justificativa'])}")
            dados = [f"{k}: {T.fmt_num(v_, 2) if isinstance(v_, (int, float)) else _md(v_)}" for k, v_ in (s.get("dados") or {}).items() if v_ is not None and not isinstance(v_, (list, dict))]
            if dados:
                st.markdown("**Dados que sustentam:** " + "; ".join(dados))
            st.markdown(f"**Nível de evidência:** {s['confianca']} ({s['evidencia']} de {s['total_criterios']} critérios).")
            st.markdown("**O que pode invalidar:**\n" + "\n".join(f"- {_md(x)}" for x in s["invalida"]))
    st.markdown("#### Como a tendência foi lida")
    st.dataframe(pd.DataFrame([{"Critério": c["nome"], "Voto": {1: "alta", -1: "baixa", 0: "neutro"}[c["voto"]], "Leitura": c["texto"]} for c in t["criterios"]]), hide_index=True, width="stretch")
    st.caption("Alta ou baixa só quando 60%+ dos critérios apontam o mesmo lado e nenhum aponta o contrário; um cruzamento isolado não define tendência.")
    if r["divergencias"]:
        st.markdown("#### Divergências")
        for d in r["divergencias"]:
            st.markdown(f"- **{d['tipo'].capitalize()}**: {_md(d['texto'])} ({d['de']} a {d['ate']})")
    st.markdown("#### Histórico de sinais")
    hist = [h for h in (_ss().get(CH_SINAIS) or []) if st.session_state.get("tecav_hist_todos") or h["ativo"] == X["ativo"]]
    st.toggle("Mostrar de todos os ativos", key="tecav_hist_todos", **_opt("tecav_hist_todos", "value", False))
    if hist:
        st.dataframe(pd.DataFrame([{"Candle": h["data"], "Ativo": h["ativo"], "Sinal": h["titulo"], "Evidência": h["confianca"], "Registrado em": str(h["registrado_em"])[:16].replace("T", " ")}
                                   for h in hist[::-1][:60]]), hide_index=True, width="stretch")
        st.button("Limpar histórico de sinais", key="tecav_hist_limpar", on_click=lambda: _ss().__setitem__(CH_SINAIS, []))
    else:
        st.caption("Ainda sem sinais registrados. Cada sinal novo (diferente por ativo, tipo e candle) é registrado aqui uma única vez ao abrir a análise diária.")


def _aba_padroes(X):
    r = X["resumo"]
    moeda = X["moeda"]
    niv = r["niveis"]
    st.markdown("#### Suportes e resistências")
    st.caption("Zonas de preço tocadas várias vezes por topos e fundos. São regiões, não linhas exatas, e podem ser rompidas.")
    linhas = [{"Tipo": z["tipo"], "Preço médio": T.fmt_preco(z["preco"], moeda), "Faixa": f"{T.fmt_preco(z['zona'][0], moeda)} a {T.fmt_preco(z['zona'][1], moeda)}", "Toques": z["toques"],
               "Último toque": z["ultimo_toque"], "Distância (%)": round(z["distancia_pct"], 1)} for z in niv["resistencias"][::-1] + niv["dentro"] + niv["suportes"]]
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    else:
        st.caption("Nenhuma zona com toques suficientes neste histórico.")
    ex = r.get("extremos") or {}
    if ex:
        c = []
        for rot, e in (("No período carregado", ex.get("periodo")), ("Últimos ~12 meses", ex.get("ano"))):
            if e:
                c.append({"Janela": rot, "Máxima": f"{T.fmt_preco(e['max']['preco'], moeda)} em {e['max']['data']}", "Mínima": f"{T.fmt_preco(e['min']['preco'], moeda)} em {e['min']['data']}"})
        st.markdown("#### Máximas e mínimas")
        st.dataframe(pd.DataFrame(c), hide_index=True, width="stretch")
    lt = T.linhas_de_tendencia(X["df"])
    if lt:
        st.markdown("#### Linhas de tendência")
        for x in lt:
            st.markdown(f"- {x['tipo']}: de {T.fmt_preco(x['pontos'][0][1], moeda)} em {x['pontos'][0][0]} a {T.fmt_preco(x['pontos'][1][1], moeda)} em {x['pontos'][1][0]}")
        st.caption("Reta ligando os dois últimos fundos/topos: só tem valor se o preço a respeitar.")
    st.markdown("#### Padrões gráficos")
    st.caption("Padrão 'em formação' NÃO está confirmado; confirmado significa que o preço já rompeu o critério do padrão, o que ainda não garante o cenário.")
    if not r["padroes"]:
        st.info("Nenhum padrão identificado com os critérios do app neste histórico (ou histórico curto).")
    for p in r["padroes"]:
        ic = {"alta": "🟢", "baixa": "🔴"}.get(p["direcao"], "⚪")
        with st.expander(f"{ic} {p['nome']} · {p['estado']} · confiança {p['confianca_rotulo']} ({p['confianca']}/100)"):
            st.markdown(f"**Período de formação:** {p['inicio']} a {p['fim']} ({p['candles']} candles)  \n**Região no gráfico:** {T.fmt_preco(p['regiao']['y0'], moeda)} a {T.fmt_preco(p['regiao']['y1'], moeda)}  \n**Viés:** {p['direcao']}")
            st.markdown("**Critérios usados:**\n" + "\n".join(f"- {_md(c)}" for c in p["criterios"]))
            st.markdown("**Possíveis cenários:**\n" + "\n".join(f"- {_md(c)}" for c in p["cenarios"]))
            st.markdown(f"**O que invalida:** {_md(p['invalidacao'])}")
            if p.get("alvo"):
                st.caption(f"Projeção pela altura do padrão: {T.fmt_preco(p['alvo'], moeda)} (referência geométrica, não previsão).")
    try:
        import tecnica
        cs = tecnica.so_atuais([s for s in tecnica.candlesticks(X["df"]) if s["sinal"] != "Doji"], X["df"], 3) if {"Open", "High", "Low"}.issubset(X["df"].columns) else []
    except Exception:
        cs = []
    if cs:
        st.markdown("#### Candles recentes (últimos 3)")
        st.dataframe(pd.DataFrame([{"Data": T._dia(c["data"]), "Candle": c["sinal"], "Viés": c["tipo"]} for c in cs]), hide_index=True, width="stretch")


def _aba_multi(X):
    mt = X["resumo"]["multitemporal"]
    st.markdown("#### Curto, médio e longo prazo")
    st.caption("Mesmo ativo em vários períodos: semanal e mensal são agregados do histórico diário carregado.")
    st.dataframe(pd.DataFrame([{"Horizonte": p["horizonte"], "Período": p["rotulo"], "Candles": p["candles"], "Tendência": (p["tendencia"] or "sem leitura"),
                                "Confiança": p.get("confianca") or "—", "Observação": p.get("motivo") or ("último candle em formação" if p.get("parcial") else "")} for p in mt["periodos"]]),
                 hide_index=True, width="stretch")
    st.markdown("**Conclusão:** " + _md(mt["conclusao"]))
    for p in mt["periodos"]:
        if p["criterios"]:
            with st.expander(f"Critérios · {p['horizonte']} ({p['rotulo']})"):
                for c in p["criterios"]:
                    st.markdown(f"- **{_md(c['nome'])}** ({ {1: 'alta', -1: 'baixa', 0: 'neutro'}[c['voto']] }): {_md(c['texto'])}")
    for l in mt["limites"]:
        st.caption("ℹ️ " + _md(l))


def _editor_operando(chave: str, rotulo: str, perm: list, lado_direito: bool = False) -> dict:
    ops = (["VALOR"] if lado_direito else []) + ["PRECO"] + [n for n in perm if n not in ("VOL_MEDIO",)]
    c1, c2 = st.columns([1.2, 1])
    ind = c1.selectbox(rotulo, ops, key=f"{chave}_i", format_func=lambda n: "Valor fixo" if n == "VALOR" else "Preço" if n == "PRECO" else T.INDICADORES[n]["nome"],
                       **_opt(f"{chave}_i", "index", 1 if lado_direito else 0))
    if ind == "VALOR":
        return T.operando(valor=c2.number_input("Valor", key=f"{chave}_v", **_opt(f"{chave}_v", "value", 30.0)))
    if ind == "PRECO":
        col = c2.selectbox("Qual preço", ["Close", "Open", "High", "Low"], key=f"{chave}_c", format_func=lambda x: {"Close": "Fechamento", "Open": "Abertura", "High": "Máxima", "Low": "Mínima"}[x])
        return T.operando("PRECO", col=col)
    esp = T.INDICADORES[ind]
    colunas = [c for c in esp["colunas"] if c not in T.COLUNAS_PROIBIDAS_BACKTEST]
    col = c2.selectbox("Linha do indicador", colunas, key=f"{chave}_c_{ind}")
    params = {}
    if esp["params"]:
        cs = st.columns(min(3, len(esp["params"])))
        for cc, (k, s) in zip(cs * 2, esp["params"].items()):
            kk = f"{chave}_p_{ind}_{k}"
            params[k] = (cc.number_input(s["rotulo"], min_value=float(s["min"]), max_value=float(s["max"]), step=0.5, key=kk, **_opt(kk, "value", float(s["padrao"])))
                         if isinstance(s["padrao"], float) else int(cc.number_input(s["rotulo"], min_value=int(s["min"]), max_value=int(s["max"]), key=kk, **_opt(kk, "value", int(s["padrao"])))))
    return T.operando(ind, params, col)


def _editor_condicoes(prefixo: str, titulo: str, perm: list, padrao: int = 1) -> list:
    st.markdown(f"**{titulo}**")
    n = st.selectbox("Quantas condições (todas precisam valer ao mesmo tempo)", [1, 2, 3], key=f"{prefixo}_n", **_opt(f"{prefixo}_n", "index", padrao - 1))
    out = []
    for i in range(n):
        with st.container(border=True):
            esq = _editor_operando(f"{prefixo}_{i}_e", "Indicador (esquerda)", perm)
            op = st.selectbox("Condição", list(T.OPS_ROTULO), key=f"{prefixo}_{i}_o", format_func=lambda o: T.OPS_ROTULO[o])
            dire = _editor_operando(f"{prefixo}_{i}_d", "Comparar com (direita)", perm, lado_direito=True)
            out.append(T.condicao(esq, op, dire))
    return out


def _aba_backtest(X):
    df, classe, moeda = X["df"], X["classe"], X["moeda"]
    perm = X["perfil"]["permitidos"]
    st.caption("Teste de estratégias com dados históricos. O sinal usa só dados até o fechamento do candle e a ordem é executada no candle seguinte; custos e liquidez entram na conta.")
    st.warning(T.AVISO_BACKTEST)
    nomes = {k: v["nome"] for k, v in T.ESTRATEGIAS_PADRAO.items()}
    escolha = st.selectbox("Estratégia", list(nomes) + ["personalizada"], key="tecav_bt_estrat", format_func=lambda k: nomes.get(k, "Personalizada (monte as condições)"))
    if escolha != "personalizada":
        e0 = T.ESTRATEGIAS_PADRAO[escolha]
        st.info(e0["descricao"])
        estr = {"nome": e0["nome"], "entrada": e0["entrada"], "saida": e0["saida"]}
        indisp = [m for it in (e0["entrada"] + e0["saida"]) for m in [_requisitos_ok(df, it)] if m]
    else:
        entrada = _editor_condicoes("tecav_bt_ent", "Condições de ENTRADA", perm)
        saida = _editor_condicoes("tecav_bt_sai", "Condições de SAÍDA (opcional; sem saída, só stop/alvo/prazo encerram)", perm, 1)
        estr = {"nome": "Estratégia personalizada", "entrada": entrada, "saida": saida}
        indisp = []
    with st.expander("Capital, custos, stop e período", expanded=False):
        c1, c2, c3 = st.columns(3)
        capital = c1.number_input("Capital inicial", min_value=100.0, value=10000.0, step=500.0, key="tecav_bt_cap")
        expo = c2.slider("Exposição do capital (%)", 10, 100, 100, key="tecav_bt_expo")
        rf = c3.number_input("Taxa livre de risco (% a.a.) para o Sharpe", min_value=0.0, max_value=100.0, value=0.0, step=0.5, key="tecav_bt_rf", help="Informe o CDI do período se quiser Sharpe em excesso ao CDI.")
        pad = T.custos_padrao(classe)
        k1, k2, k3, k4 = st.columns(4)
        cor_fixa = k1.number_input("Corretagem fixa por ordem", min_value=0.0, value=float(pad["corretagem_fixa"]), key="tecav_bt_c1")
        cor_pct = k2.number_input("Corretagem (%)", min_value=0.0, value=float(pad["corretagem_pct"]), step=0.01, format="%.3f", key="tecav_bt_c2")
        emol = k3.number_input("Emolumentos/taxas (%)", min_value=0.0, value=float(pad["emolumentos_pct"]), step=0.001, format="%.3f", key="tecav_bt_c3")
        slip = k4.number_input("Slippage (%)", min_value=0.0, value=float(pad["slippage_pct"]), step=0.01, format="%.3f", key="tecav_bt_c4", help="Diferença entre o preço do gráfico e o preço realmente obtido.")
        st.caption("Custos iniciais são estimativas editáveis; confira na sua corretora/exchange. Imposto de renda não é simulado.")
        s1, s2, s3, s4 = st.columns(4)
        stop = s1.number_input("Stop (%) — 0 = sem", min_value=0.0, max_value=90.0, value=0.0, step=0.5, key="tecav_bt_stop")
        alvo = s2.number_input("Alvo (%) — 0 = sem", min_value=0.0, max_value=500.0, value=0.0, step=0.5, key="tecav_bt_alvo")
        prazo = s3.number_input("Prazo máx. (candles) — 0 = sem", min_value=0, max_value=1000, value=0, key="tecav_bt_prazo")
        part = s4.number_input("Máx. % do volume do candle", min_value=1.0, max_value=100.0, value=float(pad["max_participacao_pct"]), key="tecav_bt_part")
        d1, d2, d3 = st.columns(3)
        de = d1.date_input("Início do teste", value=df.index[min(len(df) - 1, 60)].date(), min_value=df.index[0].date(), max_value=df.index[-1].date(), key="tecav_bt_de")
        ate = d2.date_input("Fim do teste", value=df.index[-1].date(), min_value=df.index[0].date(), max_value=df.index[-1].date(), key="tecav_bt_ate")
        dividir = d3.slider("Separar amostra de fora (%) — 0 = não", 0, 80, 0, step=10, key="tecav_bt_div", help="Mostra o resultado separado no último trecho, para checar se a regra se sustenta fora do trecho em que foi observada.")
        comp_ibov = st.checkbox("Comparar com o Ibovespa", value=False, key="tecav_bt_ibov")
        comparar = st.multiselect("Comparar com outras estratégias prontas", [k for k in nomes if k != escolha], key="tecav_bt_comp", format_func=lambda k: nomes[k])
    for m in indisp:
        st.caption("⚠️ " + _md(m))
    if st.button("▶ Executar teste", key="tecav_bt_run", type="primary"):
        estr = {**estr, "stop_pct": stop or None, "alvo_pct": alvo or None, "max_candles": int(prazo) or None}
        bench = None
        if comp_ibov:
            b = carregar_diario_simples("^BVSP", "acao", X["hooks"])
            bench = b["Close"] if b is not None else None
        custos = {"corretagem_fixa": cor_fixa, "corretagem_pct": cor_pct, "emolumentos_pct": emol, "slippage_pct": slip, "max_participacao_pct": part}
        kw = dict(capital=capital, custos=custos, classe=classe, proventos=None if X["meta"].get("ajustado") else X["dados"]["div"], ajustado=X["meta"].get("ajustado"),
                  de=pd.Timestamp(de), ate=pd.Timestamp(ate) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1), benchmark=bench, rf_anual=rf / 100, dividir=(dividir / 100) or None, exposicao=expo / 100)
        res = T.backtest(df, estr, **kw)
        auditoria = T.sinais_sem_futuro(df, estr["entrada"] + estr["saida"]) if res["ok"] else []
        cmp_ = None
        if comparar and res["ok"]:
            cmp_ = T.comparar_estrategias(df, [estr] + [{**T.ESTRATEGIAS_PADRAO[k], "stop_pct": stop or None, "alvo_pct": alvo or None} for k in comparar], **kw)
        _ss()[CH_BT] = {"chave": (X["ativo"], X["visao"]), "res": res, "auditoria": auditoria, "comparacao": cmp_, "estrategia": estr["nome"], "quando": _agora().isoformat(timespec="minutes")}
    bt = _ss().get(CH_BT)
    if not bt or bt["chave"] != (X["ativo"], X["visao"]):
        st.caption("Escolha a estratégia e toque em “Executar teste”.")
        return
    res = bt["res"]
    if not res["ok"]:
        st.error(res["motivo"] or "Não foi possível executar o teste.")
        return
    m = res["metricas"]
    bh = (res["benchmark"] or {}).get("comprar_e_manter", {})
    st.markdown(f"#### Resultado · {_md(bt['estrategia'])}")
    pct = lambda v: "n/d" if v is None else f"{T.fmt_num(v, 1)}%"  # noqa: E731
    _cartoes([("Retorno acumulado", pct(m["retorno_pct"]), "good" if (m["retorno_pct"] or 0) > 0 else "bad", f"comprar e manter: {pct(bh.get('retorno_pct'))}"),
              ("Retorno anualizado", pct(m["anualizado_pct"]), "info", "pouco confiável (menos de 1 ano)" if m["anualizacao_curta"] else "composto"),
              ("Drawdown máximo", pct(m["drawdown_max_pct"]), "bad", f"comprar e manter: {pct(bh.get('drawdown_max_pct'))}"),
              ("Taxa de acerto", pct(m["taxa_acerto_pct"]), "info", f"{m['n_operacoes']} operação(ões)")])
    _cartoes([("Risco/retorno", T.fmt_num(m["retorno_dd"], 2) if m["retorno_dd"] is not None else "n/d", "info", "anualizado ÷ |drawdown|"),
              ("Sharpe", T.fmt_num(m["sharpe"], 2) if m["sharpe"] is not None else "n/d", "info", "mín. 30 retornos; n/d no intraday"),
              ("Payoff", T.fmt_num(m["payoff"], 2) if m["payoff"] is not None else "n/d", "info", "ganho médio ÷ perda média"),
              ("Tempo no mercado", pct(m["tempo_no_mercado_pct"]), "info", f"execução: {res['execucao']}")])
    ref = (res["benchmark"] or {}).get("referencia")
    if ref:
        st.caption(f"Ibovespa no mesmo período: {pct(ref['retorno_pct'])} (drawdown máx. {pct(ref['drawdown_max_pct'])}).")
    st.plotly_chart(figura_backtest(df, res), width="stretch", config=CONFIG_PLOTLY, theme=None, key="tecav_fig_bt")
    if bt["auditoria"]:
        st.error("Auditoria anti look-ahead encontrou divergência: " + " ".join(bt["auditoria"]))
    else:
        st.caption("✅ Auditoria anti look-ahead: o sinal em cada ponto testado é igual com e sem os dados futuros.")
    if res["trades"]:
        with st.expander(f"Operações simuladas ({len(res['trades'])})"):
            st.dataframe(pd.DataFrame([{"Entrada": t["entrada_data"], "Preço entrada": round(t["entrada_preco"], 2), "Saída": t["saida_data"], "Preço saída": round(t["saida_preco"], 2),
                                        "Qtd": round(t["qtd"], 4), "Custos": round(t["custos"], 2), "Resultado": round(t["pnl"], 2), "Retorno (%)": round(t["retorno_pct"], 1), "Dias": t["dias"], "Motivo": t["motivo_saida"]}
                                       for t in res["trades"]]), hide_index=True, width="stretch")
    if res.get("posicao_aberta"):
        po = res["posicao_aberta"]
        st.caption(f"Posição aberta no fim do teste: entrada em {po['entrada_data']}, resultado em aberto {T.fmt_num(po['resultado_aberto'], 2)} (fora da taxa de acerto).")
    if res.get("amostras"):
        a = res["amostras"]
        st.markdown(f"**Amostra dentro × fora (corte em {a['corte']})**")
        st.dataframe(pd.DataFrame([{"Trecho": rot, "Retorno (%)": None if x["retorno_pct"] is None else round(x["retorno_pct"], 1), "Drawdown (%)": None if x["drawdown_max_pct"] is None else round(x["drawdown_max_pct"], 1),
                                    "Operações": x["n_operacoes"], "Acerto (%)": None if x["taxa_acerto_pct"] is None else round(x["taxa_acerto_pct"], 0)} for rot, x in (("Dentro", a["dentro"]), ("Fora", a["fora"]))]), hide_index=True, width="stretch")
        st.caption(a["aviso"])
    if bt.get("comparacao"):
        st.markdown("**Comparação entre estratégias** (mesmos dados e custos; sem eleger a 'melhor')")
        st.dataframe(pd.DataFrame([{"Estratégia": l["estrategia"], "Retorno (%)": None if l["retorno_pct"] is None else round(l["retorno_pct"], 1), "Anualizado (%)": None if l["anualizado_pct"] is None else round(l["anualizado_pct"], 1),
                                    "Drawdown (%)": None if l["drawdown_max_pct"] is None else round(l["drawdown_max_pct"], 1), "Operações": l["n_operacoes"], "Sharpe": None if l["sharpe"] is None else round(l["sharpe"], 2),
                                    "Observação": l["motivo"] or ""} for l in bt["comparacao"]["linhas"]]), hide_index=True, width="stretch")
    for a in res["avisos"]:
        st.caption("ℹ️ " + _md(a))


def _requisitos_ok(df, cond) -> str | None:
    for lado in ("esq", "dir"):
        s = cond[lado]
        if s.get("ind") and s["ind"] != "PRECO":
            ok, motivo = T.disponibilidade(s["ind"], df, s.get("params"))
            if not ok:
                return f"{T.INDICADORES[s['ind']]['nome']}: {motivo}"
    return None


# =============================================================================== alertas
FREQ_ROTULO = {"cada_atualizacao": "A cada atualização", "diaria": "No máximo 1 vez por dia", "semanal": "No máximo 1 vez por semana"}
_RE_DATA = re.compile(r"(\d{4}-\d{2}-\d{2}(?: \d{2}:\d{2})?)$")


def _params_alerta(tipo: str, ativo_atual: str, perm: list) -> dict:
    P = dict(T.PADROES_PARAMS[tipo])
    k = f"tecav_al_{tipo}"
    if tipo == "cruz_medias":
        a, b, c, d = st.columns(4)
        P.update({"tipo_media": a.selectbox("Média", ["SMA", "EMA"], key=f"{k}_tm"), "rapida": int(b.number_input("Rápida", min_value=2, max_value=200, value=9, key=f"{k}_r")),
                  "lenta": int(c.number_input("Lenta", min_value=3, max_value=400, value=21, key=f"{k}_l")), "direcao": d.selectbox("Direção", ["ambas", "alta", "baixa"], key=f"{k}_d")})
    elif tipo == "rsi_zona":
        a, b, c, d = st.columns(4)
        P.update({"n": int(a.number_input("Períodos", min_value=2, max_value=100, value=14, key=f"{k}_n")), "sobrecompra": float(b.number_input("Sobrecompra", min_value=50.0, max_value=99.0, value=70.0, key=f"{k}_sc")),
                  "sobrevenda": float(c.number_input("Sobrevenda", min_value=1.0, max_value=50.0, value=30.0, key=f"{k}_sv")), "zona": d.selectbox("Zona", ["ambas", "sobrecompra", "sobrevenda"], key=f"{k}_z")})
    elif tipo == "macd_cruz":
        a, b, c, d = st.columns(4)
        P.update({"rapida": int(a.number_input("Rápida", min_value=2, max_value=100, value=12, key=f"{k}_r")), "lenta": int(b.number_input("Lenta", min_value=3, max_value=200, value=26, key=f"{k}_l")),
                  "sinal": int(c.number_input("Sinal", min_value=2, max_value=100, value=9, key=f"{k}_s")), "direcao": d.selectbox("Direção", ["ambas", "alta", "baixa"], key=f"{k}_d")})
    elif tipo in ("volume_alto", "volatilidade"):
        P["razao"] = float(st.number_input("Razão mínima (vezes o normal)", min_value=1.05, max_value=20.0, value=2.0 if tipo == "volume_alto" else 1.8, step=0.1, key=f"{k}_x"))
    elif tipo == "mudanca_tendencia":
        P["candles_atras"] = int(st.number_input("Comparar com quantos candles atrás", min_value=1, max_value=20, value=3, key=f"{k}_c"))
    elif tipo == "padrao":
        a, b = st.columns(2)
        P.update({"min_confianca": float(a.number_input("Confiança mínima (0 a 100)", min_value=0.0, max_value=100.0, value=60.0, key=f"{k}_m")), "confirmados": b.checkbox("Só padrões confirmados", key=f"{k}_c")})
    elif tipo == "personalizada":
        P["nome"] = st.text_input("Nome do alerta", key=f"{k}_nome", max_chars=60, **_opt(f"{k}_nome", "value", "Minha condição"))
        esq = _editor_operando(f"{k}_e", "Indicador (esquerda)", perm)
        op = st.selectbox("Condição", list(T.OPS_ROTULO), key=f"{k}_o", format_func=lambda o: T.OPS_ROTULO[o])
        dire = _editor_operando(f"{k}_d", "Comparar com (direita)", perm, lado_direito=True)
        P["condicao"] = T.condicao(esq, op, dire)
    return P


def _remover_regra(rid: str):
    _ss()[CH_REGRAS] = [r for r in (_ss().get(CH_REGRAS) or []) if r["id"] != rid]


def _alvos_alerta(regras: list, X: dict) -> list[str]:
    alvos = []
    hooks = X["hooks"]
    for r in regras:
        if r["ativo"] != "*":
            alvos.append(r["ativo"])
    if any(r["ativo"] == "*" for r in regras):
        alvos += [X["ativo"]] + [str(c).upper() for c in ((hooks.get("favoritos") or (lambda: []))() or [])]
        alvos += [p["id"] for p in ((hooks.get("carteira") or (lambda: []))() or []) if _classe_ui(p.get("classe", "acao")) in ("acao", "etf", "fii", "cripto")]
    return list(dict.fromkeys(alvos))[:MAX_ATIVOS_ALERTA]


def _avaliar(regras: list, X: dict, so_atual: bool = False) -> dict:
    ss = _ss()
    series = {}
    alvos = [X["ativo"]] if so_atual else _alvos_alerta(regras, X)
    for a in alvos:
        if a == X["ativo"] and X["visao"] == "Diário":
            series[a] = {"df": X["df"], "classe": X["classe"]}
            continue
        cl = _classe_ui(X["hooks"]["classe_de"](a)) if X["hooks"].get("classe_de") else "acao"
        d = carregar_diario_simples(a, cl, X["hooks"])
        if d is not None:
            series[a] = {"df": d, "classe": cl}
    disp, avisos = T.avaliar_alertas_tec(regras, series, _agora())
    novos, hist, supr = T.filtrar_por_frequencia(disp, ss.get(CH_HIST) or [], regras, _agora())
    ss[CH_HIST] = hist
    faltou = [a for a in alvos if a not in series]
    return {"novos": novos, "suprimidos": supr, "avisos": avisos + [f"{a}: sem histórico agora." for a in faltou], "quando": _agora().isoformat(timespec="minutes"), "n_ativos": len(series)}


def _aba_alertas(X):
    ss = _ss()
    perm = X["perfil"]["permitidos"]
    st.caption("Alertas de condições técnicas. Cada condição detectada é registrada uma única vez (por ativo, regra e candle) e fica no histórico com a data do candle em que apareceu.")
    st.markdown("#### Novo alerta")
    c1, c2, c3 = st.columns([1.2, 1.4, 1])
    ativo = c1.text_input("Ativo (ou * para todos os acompanhados)", key="tecav_al_ativo", **_opt("tecav_al_ativo", "value", X["ativo"]))
    tipo = c2.selectbox("Indicador / condição", list(T.TIPOS_ALERTA_TEC), key="tecav_al_tipo", format_func=lambda t: T.TIPOS_ALERTA_TEC[t])
    per = c3.selectbox("Período", list(T.PERIODOS_ALERTA), key="tecav_al_per", format_func=lambda p: T.PERIODOS_ALERTA[p])
    P = _params_alerta(tipo, X["ativo"], perm)
    d1, d2, d3 = st.columns(3)
    freq = d1.selectbox("Frequência", list(I.FREQUENCIAS), key="tecav_al_freq", format_func=lambda f: FREQ_ROTULO[f], index=1)
    canal = d2.selectbox("Canal de notificação", list(T.CANAIS), key="tecav_al_canal", format_func=lambda c: T.CANAIS[c])
    prio = d3.selectbox("Prioridade", ["alta", "media", "baixa"], key="tecav_al_prio", index=1)
    st.caption("Canal: hoje os avisos aparecem aqui e na Central de inteligência. E-mail e notificação no celular dependem de um serviço externo que este app ainda não tem.")
    if st.button("➕ Criar alerta", key="tecav_al_criar"):
        try:
            r = T.nova_regra_tec(tipo, ativo or "*", P, per, freq, canal, prio)
            regras = [x for x in (ss.get(CH_REGRAS) or []) if x["id"] != r["id"]]
            ss[CH_REGRAS] = regras + [r]
            st.success("Alerta salvo.")
        except ValueError as e:
            st.error(str(e))
    regras = ss.get(CH_REGRAS) or []
    st.markdown(f"#### Seus alertas ({len(regras)})")
    if not regras:
        st.caption("Nenhum alerta criado.")
    for r in regras:
        a, b, c = st.columns([5, 1.3, 1.3], vertical_alignment="center")
        a.markdown(f"**{_md(r['ativo'])}** · {_md(T.descrever_regra_tec(r))}  \n<span style='opacity:.7'>{FREQ_ROTULO[r['frequencia']]} · prioridade {r['prioridade']} · {T.CANAIS[r['canal']]}</span>", unsafe_allow_html=True)
        novo = b.checkbox("Ativo", value=r.get("ativa", True), key=f"tecav_al_on_{r['id']}")
        if novo != r.get("ativa", True):
            r["ativa"] = novo
        c.button("Remover", key=f"tecav_al_rm_{r['id']}", on_click=_remover_regra, args=(r["id"],))
    ativas = [r for r in regras if r.get("ativa", True)]
    if ativas and st.button("🔔 Avaliar alertas agora", key="tecav_al_avaliar"):
        with st.spinner("Lendo o histórico dos ativos dos alertas…"):
            ss["_tecav_aval"] = _avaliar(ativas, X)
    av = ss.get("_tecav_aval")
    if av:
        st.markdown(f"**Última avaliação:** {av['quando'].replace('T', ' ')} · {av['n_ativos']} ativo(s) · {len(av['novos'])} novo(s) · {av['suprimidos']} repetido(s) suprimido(s)")
        for d in av["novos"]:
            st.warning(f"**{_md(d['titulo'])}**  \n{_md(d['texto'])}  \n_Detectado no candle de {d['detectado_em']} · {d['periodo']}_")
        for a_ in av["avisos"][:6]:
            st.caption("ℹ️ " + _md(a_))
        if not av["novos"]:
            st.caption("Nenhuma condição nova detectada.")
    hist = ss.get(CH_HIST) or []
    st.markdown("#### Histórico de alertas")
    if hist:
        st.dataframe(pd.DataFrame([{"Detectado no candle": (_RE_DATA.search(h["assinatura"]).group(1) if _RE_DATA.search(h["assinatura"]) else ""), "Registrado em": str(h["quando"])[:16].replace("T", " "),
                                    "Ativo": h["ativo"], "Alerta": h["titulo"], "Prioridade": h["prioridade"]} for h in hist[::-1][:60]]), hide_index=True, width="stretch")
        st.button("Limpar histórico de alertas", key="tecav_al_limpar", on_click=lambda: _ss().__setitem__(CH_HIST, []))
    else:
        st.caption("Sem alertas registrados ainda.")


# =============================================================================== carteira
def _posicoes_carteira(hooks) -> list[dict]:
    try:
        return list((hooks.get("carteira") or (lambda: []))() or [])
    except Exception:
        return []


def _ler_carteira_tecnica(hooks) -> dict:
    pos = sorted(_posicoes_carteira(hooks), key=lambda p: -float(p.get("peso") or 0))[:MAX_POSICOES]
    itens = []
    for p in pos:
        cl = _classe_ui(p.get("classe", "acao"))
        df = carregar_diario_simples(p["id"], cl, hooks) if cl in ("acao", "etf", "fii", "cripto") else None
        itens.append({"id": p["id"], "peso": float(p.get("peso") or 0), "classe": cl, "df": df})
    v = T.visao_carteira(itens)
    v["quando"] = _agora().isoformat(timespec="minutes")
    v["n_total"] = len(_posicoes_carteira(hooks))
    return v


def _aba_carteira(X):
    hooks = X["hooks"]
    pos = _posicoes_carteira(hooks)
    st.caption("Leitura técnica das posições da sua carteira (Passo 12): tendência de cada ativo, peso por tendência, ativos que se movem juntos e riscos técnicos. Só leitura: nada é negociado.")
    if not pos:
        st.info("Sem posições na carteira. Registre compras em Carteira para ver a visão técnica consolidada.")
        return
    if st.button(f"Ler a carteira ({min(len(pos), MAX_POSICOES)} maiores posições)", key="tecav_cart_run"):
        with st.spinner("Lendo o histórico de preços das posições…"):
            _ss()[CH_CACHE_CART] = _ler_carteira_tecnica(hooks)
    v = _ss().get(CH_CACHE_CART)
    if not v:
        st.caption("Toque no botão para ler. A leitura busca até 15 históricos e só roda quando você pede.")
        return
    pt = v["peso_por_tendencia_pct"]
    pl = v["placar_ponderado"]
    _cartoes([("Alta", f"{T.fmt_num(pt['alta'], 0)}%", "good", "do patrimônio com leitura"), ("Lateral", f"{T.fmt_num(pt['lateral'], 0)}%", "fair", "do patrimônio com leitura"), ("Baixa", f"{T.fmt_num(pt['baixa'], 0)}%", "bad", "do patrimônio com leitura"),
              ("Cobertura técnica", f"{T.fmt_num(v['cobertura_pct'], 0)}%", "info", f"lido em {v['quando'][:16].replace('T', ' ')}")])
    st.markdown("**" + _md(v["resumo"]) + "**")
    st.dataframe(pd.DataFrame([{"Ativo": x["id"], "Classe": T.ROTULO_CLASSE.get(x["classe"], x["classe"]), "Peso (%)": round(x["peso"], 1), "Tendência": x["tendencia"] or "sem leitura", "Confiança": x["confianca"] or "—",
                                "Osciladores": x["osciladores"] or "—", "Volatilidade": "elevada" if x["volatilidade_elevada"] else ("normal" if x["tendencia"] else "—"), "Liquidez": (x["liquidez"] or "—").replace("_", " "),
                                "Prazos": (x["multitemporal"] or "—").replace("_", " ")} for x in v["linhas"]]), hide_index=True, width="stretch")
    if v["grupos"]:
        st.markdown("#### Ativos com tendência semelhante")
        for g in v["grupos"]:
            st.markdown(f"- Tendência de **{g['tendencia']}**: {_md(', '.join(g['ativos']))} somam {T.fmt_num(g['peso_pct'], 0)}% da carteira" + (f"; correlação média {T.fmt_num(g['correlacao_media'], 2)}" if g["correlacao_media"] is not None else "") + (" ⚠️ **concentração técnica**" if g["concentrada"] else ""))
    st.markdown("#### Riscos técnicos")
    if v["riscos"]:
        for r_ in v["riscos"]:
            st.markdown(f"- ⚠️ {_md(r_)}")
    else:
        st.caption("Nenhum risco técnico relevante nos critérios do app (posições de 10%+ da carteira).")
    if v["sem_leitura"]:
        st.caption("Sem leitura técnica (histórico insuficiente ou classe não aplicável, como renda fixa e fundos de cotas): " + _md(", ".join(v["sem_leitura"])))
    st.caption("Alertas sobre os ativos acompanhados: crie regras com ativo * na aba Alertas; a Central de inteligência também as avalia.")


# =============================================================================== dados e ajuda
def _aba_dados(X):
    meta, rel, r = X["meta"], X["dados"]["rel"], X["resumo"]
    st.info(T.descrever_fonte(meta, rel, X["dados"]["lacunas"]))
    st.markdown("#### Qualidade dos dados")
    st.dataframe(pd.DataFrame([{"Candles recebidos": rel["n_original"], "Candles válidos": rel["n"], "Sem preço (removidos)": rel["removidas_sem_preco"], "Duplicados (removidos)": rel["duplicadas"],
                                "Inconsistentes (removidos)": rel["removidas_inconsistentes"], "Tem abertura/máx./mín.": "sim" if rel["tem_ohlc"] else "não", "Tem volume": "sim" if rel["tem_volume"] else "não"}]), hide_index=True, width="stretch")
    if X["dados"]["lacunas"]:
        st.markdown("**Lacunas no histórico** (nada foi preenchido):")
        st.dataframe(pd.DataFrame(X["dados"]["lacunas"]).rename(columns={"de": "De", "ate": "Até", "dias": "Dias"}), hide_index=True, width="stretch")
    liq = r.get("liquidez") or {}
    if liq.get("mediana_financeira"):
        st.caption(f"Liquidez: volume financeiro mediano de {T.fmt_preco(liq['mediana_financeira'], X['moeda'])} por candle nos últimos 60 candles; {T.fmt_num(liq['dias_sem_negocio_pct'], 0)}% sem negócio. " + (liq.get("aviso") or ""))
    if X["classe"] in ("fii", "acao", "etf") and X["visao"] == "Diário":
        v = X["df"].iloc[max(0, len(X["df"]) - X["janela"]):] if X["janela"] else X["df"]
        sp = T.separar_proventos(v, X["dados"]["div"], X["meta"].get("ajustado"))
        st.markdown("#### Preço e proventos, separados")
        if sp["retorno_preco_pct"] is not None and not X["meta"].get("ajustado"):
            st.dataframe(pd.DataFrame([{"Janela": f"{T._dia(v.index[0])} a {T._dia(v.index[-1])}", "Variação do preço (%)": round(sp["retorno_preco_pct"], 1),
                                        "Proventos / preço inicial (%)": None if sp["proventos_pct"] is None else round(sp["proventos_pct"], 1), "Soma dos proventos": None if sp["soma_proventos"] is None else round(sp["soma_proventos"], 2),
                                        "Nº de proventos": sp["n"], "Retorno total (%)": None if sp["total_pct"] is None else round(sp["total_pct"], 1)}]), hide_index=True, width="stretch")
        if sp["aviso"]:
            st.caption("ℹ️ " + _md(sp["aviso"]))
    for a in X["perfil"]["avisos"]:
        st.caption("ℹ️ " + _md(a))
    st.markdown("#### Glossário de indicadores")
    nome = st.selectbox("Indicador", list(T.INDICADORES), key="tecav_gl", format_func=lambda n: f"{T.INDICADORES[n]['grupo']} · {T.INDICADORES[n]['nome']}")
    e = T.INDICADORES[nome]
    st.markdown(f"**{e['nome']}** — {e['explicacao']}")
    st.caption("Parâmetros padrão: " + (", ".join(f"{s['rotulo']} {s['padrao']}" for s in e["params"].values()) or "nenhum") + f" · mínimo de {T.minimo_candles(nome)} candles")
    if nome in X["perfil"]["bloqueados"]:
        st.warning("Não é mostrado para este ativo: " + X["perfil"]["bloqueados"][nome])
    else:
        ok, motivo = T.disponibilidade(nome, X["df"])
        st.caption("✅ Disponível para este ativo." if ok else "⚠️ Indisponível agora: " + motivo)
    st.markdown("#### Limitações")
    for l in ["Indicadores e padrões usam o passado do preço; podem falhar e não são recomendação.",
              "Dados do Yahoo Finance são atrasados e podem ter lacunas; confira na B3 ou na sua corretora antes de decidir.",
              "Intraday e volume de FIIs/ações pequenas podem ter negociações irregulares.",
              "Renda fixa e fundos de cotas não recebem indicadores de ações automaticamente.",
              "Alertas só existem dentro do app: e-mail e notificação no celular dependem de serviço externo."]:
        st.caption("• " + l)


# =============================================================================== assistente
SUGESTOES = ["Qual a tendência deste ativo?", "Há rompimento recente?", "Quais são os suportes e resistências?", "Quais os riscos técnicos?",
             "Compare a análise técnica com os fundamentos", "O que significa o RSI?"]


def contexto_ia(X: dict) -> dict:
    ss = _ss()
    resumos = dict(ss.get("_tecav_resumos") or {})
    resumos[X["ativo"]] = X["resumo"]
    cache = ss.get("_intel_cache")
    ativos = (cache or {}).get("ativos") if isinstance(cache, dict) else None
    return {"tecnica": resumos, "foco": X["ativo"], "gerado_em": _agora().isoformat(timespec="minutes"), "ativos": ativos or [], "carteira_tecnica": ss.get(CH_CACHE_CART)}


def _assistente(X):
    ss = _ss()
    st.markdown("#### Pergunte sobre o gráfico")
    st.caption("O assistente responde só com os dados lidos aqui (cita valores e datas) e não recomenda compra ou venda.")
    cols = st.columns(2)
    for i, s in enumerate(SUGESTOES):
        if cols[i % 2].button(s, key=f"tecav_sug_{i}"):
            ss["tecav_q"] = s
    q = st.text_input("Sua pergunta", key="tecav_q", max_chars=300, **_opt("tecav_q", "value", ""))
    if q and q.strip():
        r = T.responder_tecnica(q.strip(), contexto_ia(X)) if T.eh_pergunta_tecnica(q) or X["ativo"].lower() in q.lower() else I.responder(q.strip(), {"ativos": []})
        st.markdown(f"**{_md(r['texto'])}**")
        for l in r["linhas"]:
            st.markdown("- " + _md(l[2:] if l.startswith("- ") else l))
        st.caption(f"{r['referencia']}. {r['consultado']} {r['limite']}")


# =============================================================================== página
def _chave_resumo(ativo, classe, visao, df) -> tuple:
    return (ativo, classe, visao, len(df), str(df.index[-1]), round(float(df["Close"].iloc[-1]), 6))


def _janela(visao: str, rotulo: str, n_df: int) -> int:
    dias = PERIODOS.get(rotulo, 0)
    if not dias or visao in _INTRA:
        return 0
    fator = {"Semanal": 5, "Mensal": 21, "Anual": 252}.get(visao, 1)
    return min(n_df, max(12, round(dias / fator)))


def pagina_tecnica_avancada(hooks: dict | None = None):
    hooks = hooks or {}
    ss = _ss()
    st.markdown(tema.cabecalho("📈", "Análise técnica avançada", "Gráficos, indicadores, tendências, padrões, sinais, backtest e alertas, com dados reais e cada conclusão explicada."), unsafe_allow_html=True)
    _restaurar_config()
    favs = (hooks.get("favoritos") or (lambda: []))() or []
    c1, c2, c3 = st.columns([1.3, 1.2, 1.2])
    ativo = (c1.text_input("Ativo (código)", key="tecav_ativo", max_chars=24, **_opt("tecav_ativo", "value", (str(favs[0]) if favs else "PETR4"))) or "").strip().upper()
    if not ativo:
        st.markdown(tema.vazio("grafico", "Escolha um ativo", "Digite um código: PETR4, HGLG11, BOVA11, BTC-USD, AAPL…"), unsafe_allow_html=True)
        return
    cache = ss.setdefault("_tecav_classe", {})
    if ativo not in cache:
        try:
            cache[ativo] = _classe_ui((hooks.get("classe_de") or (lambda c: "acao"))(ativo))
        except Exception:
            cache[ativo] = "acao"
    if ss.get("_tecav_ativo_prev") != ativo:                  # troca de ativo: reajusta classe e opção de ajuste por proventos
        ss["_tecav_ativo_prev"] = ativo
        ss["tecav_classe"] = next((k for k, v in CLASSES_UI.items() if v == cache[ativo]), "Ação")
        ss["tecav_ajuste"] = cache[ativo] in ("acao", "etf")
    classe_lbl = c2.selectbox("Classe do ativo", list(CLASSES_UI), key="tecav_classe", help="Define quais indicadores fazem sentido. O app tenta identificar sozinho.")
    classe = CLASSES_UI[classe_lbl]
    visao = c3.selectbox("Intervalo dos candles", VISOES, key="tecav_visao", **_opt("tecav_visao", "index", 0))
    d1, d2, d3 = st.columns([1.2, 1.2, 1.6])
    periodo = d1.selectbox("Período mostrado", list(PERIODOS) if visao not in _INTRA else ["Tudo"], key="tecav_periodo", **_opt("tecav_periodo", "index", 3 if visao not in _INTRA else 0))
    ajuste = d2.checkbox("Ajustar por proventos", key="tecav_ajuste", help="Ajusta os preços históricos pelos proventos pagos (comum em ações e ETFs). Em FIIs costuma ficar desligado para ver o preço real da cota.", disabled=classe in ("cripto", "renda_fixa"))
    usar_binance = d3.checkbox("Cripto: usar a Binance (par à vista)", value=True, key="tecav_binance", disabled=classe != "cripto") if hooks.get("binance_ohlcv") else False
    if classe == "renda_fixa":
        perfil = T.perfil_classe("renda_fixa", None)
        st.info(perfil["motivo"])
        st.caption("Para renda fixa use Renda fixa → Análise de títulos (taxas, curva de juros e marcação a mercado).")
        return
    with st.spinner(f"Lendo o histórico de {ativo}…"):
        dados = carregar(ativo, classe, visao, ajuste, hooks, usar_binance)
    if dados["erro"]:
        st.warning(dados["erro"] + " Confira o código e a classe, ou tente de novo em instantes.")
        for a in dados["avisos"]:
            st.caption("ℹ️ " + _md(a))
        return
    df, meta = dados["df"], dados["meta"]
    perfil = T.perfil_classe(classe, df)
    if not perfil["liberada"]:
        st.info(perfil["motivo"])
        return
    moeda = meta["moeda"] or "BRL"
    rkey = _chave_resumo(ativo, classe, visao, df)
    box = ss.setdefault("_tecav_res", {})
    if box.get("chave") != rkey:
        box["chave"], box["res"] = rkey, T.resumo_tecnico(df, classe, ativo, meta, moeda, visao.lower())
        rs = ss.setdefault("_tecav_resumos", {})
        rs[ativo] = box["res"]
        if len(rs) > 12:
            rs.pop(next(iter(rs)))
    resumo = box["res"]
    if not resumo["disponivel"]:
        st.warning("Sem leitura técnica utilizável: " + " ".join(resumo["avisos"]))
        return
    janela = _janela(visao, periodo, len(df))
    with st.expander("Intervalo personalizado de datas"):
        if st.checkbox("Usar datas escolhidas", key="tecav_datas"):
            a_, b_ = st.columns(2)
            de = a_.date_input("De", value=df.index[max(0, len(df) - 126)].date(), min_value=df.index[0].date(), max_value=df.index[-1].date(), key="tecav_de")
            ate = b_.date_input("Até", value=df.index[-1].date(), min_value=df.index[0].date(), max_value=df.index[-1].date(), key="tecav_ate")
            sub = df[(df.index >= pd.Timestamp(de)) & (df.index < pd.Timestamp(ate) + pd.Timedelta(days=1))]
            janela = max(12, len(df) - int(df.index.searchsorted(pd.Timestamp(de)))) if len(sub) >= 12 else janela
            if len(sub) < 12:
                st.caption("Intervalo muito curto (menos de 12 candles): usando o período padrão.")
    X = {"df": df, "dados": dados, "meta": meta, "resumo": resumo, "classe": classe, "ativo": ativo, "visao": visao, "moeda": moeda, "hooks": hooks, "janela": janela, "perfil": perfil}
    # registro automático (uma vez por sinal) e alertas do ativo atual (análise diária)
    if visao == "Diário":
        ss[CH_SINAIS], _ = T.registrar_sinais(ss.get(CH_SINAIS), resumo["sinais"])
        regras_atual = [r for r in (ss.get(CH_REGRAS) or []) if r.get("ativa", True) and r["ativo"] == ativo]
        if regras_atual and ss.get("_tecav_auto") != rkey:
            ss["_tecav_auto"] = rkey
            ss["_tecav_novos"] = _avaliar(regras_atual, X, so_atual=True)["novos"]
    for d in ss.get("_tecav_novos") or []:
        if d["ativo"] == ativo:
            st.warning(f"🔔 **{_md(d['titulo'])}**  \n{_md(d['texto'])}  \n_Detectado no candle de {d['detectado_em']}_")
    ult = float(df["Close"].iloc[-1])
    var = (ult / float(df["Close"].iloc[-2]) - 1) * 100 if len(df) > 1 else None
    t = resumo["tendencia"]
    _cartoes([("Último fechamento", T.fmt_preco(ult, moeda), "info", f"{T.fmt_num(var, 2)}% no candle · {T._dia(df.index[-1])}" if var is not None else T._dia(df.index[-1])),
              ("Tendência", (t["tendencia"] or "n/d").capitalize(), _cls_tend(t["tendencia"]), f"confiança {t['confianca'] or 'n/d'}"),
              ("Dados", meta["fonte"].split(" (")[0], "info", ("atrasados" if meta.get("atrasado") else "quase em tempo real" if meta.get("atrasado") is False else "atraso não informado") + f" · {len(df)} candles"),
              ("Moeda e fuso", moeda, "info", str(meta["fuso"]).replace("America/", ""))])
    abas = st.tabs(["Gráfico", "Sinais", "Padrões e níveis", "Multitemporal", "Backtest", "Alertas", "Carteira", "Dados e ajuda"])
    with abas[0]:
        with st.expander("⚙️ Indicadores, ferramentas e aparência", expanded=False):
            X["cfg"] = _cfg_grafico(perfil)
        if "cfg" not in X:
            X["cfg"] = {}
        _aba_grafico(X)
    for aba, fn in zip(abas[1:], (_aba_sinais, _aba_padroes, _aba_multi, _aba_backtest, _aba_alertas, _aba_carteira, _aba_dados)):
        with aba:
            fn(X)
    st.caption(T.AVISO_LEGAL)
