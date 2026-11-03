"""
Página "Análise Fundamentalista" dos criptoativos: coleta os dados (reaproveitando o cripto.py) e mostra o resultado
do motor_fundamentalista.py (sete pilares, nota 0 a 100, pontos fortes e fracos, riscos, justificativa e conclusão).

NÃO altera os módulos existentes. O que é reaproveitado, sem nova consulta (tudo já em cache):
  - cripto.analisar_moeda      -> preço, valor de mercado, FDV, oferta, volume, ranking, histórico de 12 meses
  - cripto._gecko_coin_raw     -> data de criação, categorias e repositórios (mesma ficha da CoinGecko)
  - cripto.coletar_dados       -> TVL, taxas, receita, volume DEX, TPS, DAU, inflação, dominância (por categoria)
  - cripto.inflacao_anual, _cadeia_da_moeda, _total30_cadeia, _tvl_hist_cadeia, listar_protocolos, slugs_defi,
    moedas_do_setor, listar_setores, _cadeias_llama, _resumo_llama, _total_30d
Consultas novas (cada uma em cache e compartilhada por todos os ativos):
  - DefiLlama /overview/fees (1 por hora): crescimento das taxas e taxas dos pares
  - DefiLlama /summary/fees/<slug>?dataType=dailyHoldersRevenue (1 por protocolo): o que chega ao detentor do token
  - DefiLlama stablecoins (1 por hora): lastro, redes, oferta e variação
  - CoinGecko /coins/<id> com developer_data (1 por moeda, só se houver repositório público)
  - blockchain.com charts (só Bitcoin): hashrate e endereços ativos
Dado que nenhuma API gratuita fornece (desbloqueios, auditorias, governança, Nakamoto, reservas, papéis do token)
só entra se o próprio usuário informar; caso contrário fica "n/d" e não entra na nota.
Ferramenta educacional, não é recomendação de investimento.
"""
from __future__ import annotations

import html as _html
from datetime import date
from statistics import median

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import assistente
import cripto
import motor_fundamentalista as mf
import setorial
import tema

STABLES_URL = "https://stablecoins.llama.fi/stablecoins"
BTC_CHARTS = "https://api.blockchain.info/charts"
MAX_MOEDAS = 3          # cada moeda faz algumas consultas novas; o limite protege a cota da CoinGecko
ICONE_PILAR = {"util": "🎯", "adocao": "👥", "saude": "💰", "token": "🪙", "seg": "🛡️", "dev": "🧑‍💻", "val": "⚖️"}
_TIPO_DE_SETORIAL = {"reserva": "reserva", "l1_contratos": "blockchain", "l1_performance": "blockchain",
                     "defi": "defi", "geral": "outros"}
_CATS_DEFI = ["decentralized-exchange", "lending-borrowing", "liquid-staking-governance-tokens", "yield-aggregator",
              "derivatives", "perpetuals"]


def _md(h: str):
    cripto._md(h)


# =============================================================================== coleta (novas consultas, em cache)
@st.cache_data(ttl=3600, show_spinner=False)
def _stablecoins_llama() -> dict:
    """{gecko_id: ficha} de todas as stablecoins do DefiLlama (uma consulta para o app inteiro).
    Levanta ErroAPI se falhar (erro não fica em cache)."""
    dados = cripto._get_json(STABLES_URL, {"includePrices": "true"}, 2)
    lista = dados.get("peggedAssets") if isinstance(dados, dict) else None
    if not isinstance(lista, list):
        raise cripto.ErroAPI("resposta inesperada do DefiLlama (stablecoins)")
    return {a["gecko_id"]: a for a in lista if isinstance(a, dict) and a.get("gecko_id")}


@st.cache_data(ttl=3600, show_spinner=False)
def _taxas_visao() -> dict:
    """Taxas de TODOS os protocolos numa só consulta: {slug: {t30, t60_30, parent}}. Levanta ErroAPI se falhar."""
    dados = cripto._get_json(f"{cripto.LLAMA}/overview/fees", {
        "excludeTotalDataChart": "true", "excludeTotalDataChartBreakdown": "true", "dataType": "dailyFees"}, 2)
    lista = dados.get("protocols") if isinstance(dados, dict) else None
    if not isinstance(lista, list):
        raise cripto.ErroAPI("resposta inesperada do DefiLlama (taxas)")
    out = {}
    for p in lista:
        if not isinstance(p, dict):
            continue
        slug = p.get("slug") or p.get("module")
        if slug:
            pai = str(p.get("parentProtocol") or "")
            out[slug] = {"t30": p.get("total30d"), "t60_30": p.get("total60dto30d"),
                         "parent": pai[7:] if pai.startswith("parent#") else pai}
    return out


def _taxas_slug(mapa: dict, slug: str | None) -> dict | None:
    """Soma o protocolo-pai e seus filhos (ex.: Uniswap v2 + v3 + v4). Retorna {t30, cresc}."""
    if not slug:
        return None
    itens = [v for k, v in mapa.items() if k == slug or v["parent"] == slug]
    if not itens:
        return None
    t30s = [v["t30"] for v in itens if isinstance(v["t30"], (int, float))]
    t30 = float(sum(t30s)) if t30s else None
    prev = [v["t60_30"] for v in itens]
    cresc = None
    if t30 is not None and all(isinstance(p, (int, float)) for p in prev) and sum(prev) > 0:
        cresc = t30 / sum(prev) - 1
    return {"t30": t30, "cresc": cresc}


@st.cache_data(ttl=900, show_spinner=False)
def _holders_protocolo(slug: str) -> float | None:
    """Receita dos últimos 30 dias entregue ao detentor do token (recompra, queima, dividendos). None = sem dado."""
    return cripto._total_30d(cripto._resumo_llama("fees", slug, "dailyHoldersRevenue"))


@st.cache_data(ttl=3600, show_spinner=False)
def _dev_gecko(gid: str) -> dict:
    """Atividade de desenvolvimento (CoinGecko, developer_data). Levanta ErroAPI se falhar."""
    d = cripto._get_json(f"{cripto.GECKO}/coins/{gid}", {
        "localization": "false", "tickers": "false", "market_data": "false", "community_data": "false",
        "developer_data": "true", "sparkline": "false"})
    dd = d.get("developer_data") or {}
    return {"commits_4w": dd.get("commit_count_4_weeks"), "contribuidores": dd.get("pull_request_contributors"),
            "stars": dd.get("stars"), "issues_total": dd.get("total_issues"), "issues_fechadas": dd.get("closed_issues")}


@st.cache_data(ttl=3600, show_spinner=False)
def _btc_serie(nome: str) -> list[tuple]:
    """Série diária do blockchain.com (hash-rate, n-unique-addresses): [(unix, valor)]. Levanta ErroAPI se falhar."""
    d = cripto._get_json(f"{BTC_CHARTS}/{nome}", {"timespan": "1year", "format": "json", "cors": "true"}, 2)
    return [(float(v["x"]), float(v["y"])) for v in (d.get("values") or [])
            if isinstance(v, dict) and v.get("x") is not None and v.get("y") is not None]


def _var_90d(serie: list[tuple]) -> float | None:
    """Média dos últimos 7 dias contra a média de uma janela de 14 dias centrada 90 dias antes (fração)."""
    if len(serie) < 30:
        return None
    fim = serie[-1][0]
    rec = [y for x, y in serie if x >= fim - 7 * 86400]
    ant = [y for x, y in serie if fim - 97 * 86400 <= x <= fim - 83 * 86400]
    if not rec or not ant:
        return None
    a = sum(ant) / len(ant)
    return sum(rec) / len(rec) / a - 1 if a > 0 else None


def _var_tvl(hist: list, dias: int) -> float | None:
    """Variação do TVL em `dias` dias (fração), a partir do histórico que o cripto.py já trouxe."""
    if len(hist) < 2:
        return None
    ordenado = sorted(hist, key=lambda x: x[0])
    fim_t, fim_v = ordenado[-1]
    antes = [v for t, v in ordenado if t <= fim_t - pd.Timedelta(days=dias)]
    return float(fim_v / antes[-1] - 1) if antes and antes[-1] and antes[-1] > 0 else None


@st.cache_data(ttl=600, show_spinner=False)
def _coleta(gid: str, cat_setorial: str, slug_defi: str | None):
    """cripto.coletar_dados não tem cache próprio (reconsulta a receita do DefiLlama a cada interação).
    Este invólucro guarda o resultado por 10 min. Levanta ErroAPI se a CoinGecko falhar."""
    m = cripto.analisar_moeda(gid)
    return cripto.coletar_dados(gid, m, cat_setorial, slug_defi)


# ------------------------------------------------------------------------------- pares (valuation relativo)
@st.cache_data(ttl=900, show_spinner=False)
def _pares_blockchain(gid: str) -> dict | None:
    try:
        moedas = cripto.moedas_do_setor("layer-1", 20)
        tvl_por = {c.get("gecko_id"): c.get("tvl") for c in cripto._cadeias_llama() if c.get("gecko_id")}
    except cripto.ErroAPI:
        return None
    r = [c["mcap"] / tvl_por[c["id"]] for c in moedas
         if c["id"] != gid and c.get("mcap") and (tvl_por.get(c["id"]) or 0) > 0]
    return {"n": len(r), "mc_tvl_mediana": median(r), "p_taxas_mediana": None, "grupo": "Layer 1"} if len(r) >= 3 else None


@st.cache_data(ttl=900, show_spinner=False)
def _pares_defi(gid: str, categorias: tuple) -> dict | None:
    try:
        todos = cripto.listar_setores()
        inv = {n.lower(): i for i, n in todos.items()}
        ids = [inv.get(c.lower()) for c in categorias]
        cid = next((p for p in _CATS_DEFI if p in ids), None)
        if not cid:
            return None
        moedas = cripto.moedas_do_setor(cid, 20)
        lista = cripto.listar_protocolos()
    except cripto.ErroAPI:
        return None
    try:
        taxas = _taxas_visao()
    except cripto.ErroAPI:
        taxas = {}
    r_tvl, r_tax = [], []
    for c in moedas:
        if c["id"] == gid or not c.get("mcap"):
            continue
        tvl = sum(p["tvl"] or 0 for p in lista if p["gecko_id"] == c["id"])
        if tvl > 0:
            r_tvl.append(c["mcap"] / tvl)
        slugs = cripto.slugs_defi(c["id"], lista)
        t = _taxas_slug(taxas, slugs[0]) if slugs and taxas else None
        if t and t["t30"] and t["t30"] > 0:
            r_tax.append(c["mcap"] / (t["t30"] * 365 / 30))
    if len(r_tvl) < 3:
        return None
    return {"n": len(r_tvl), "mc_tvl_mediana": median(r_tvl), "grupo": todos.get(cid, cid),
            "p_taxas_mediana": median(r_tax) if len(r_tax) >= 3 else None}


# =============================================================================== montagem dos dados do motor
def _detectar_tipo(gid: str, m: dict) -> str:
    if gid == "bitcoin":
        return "bitcoin"
    try:
        stable = gid in _stablecoins_llama()
    except cripto.ErroAPI:
        stable = False
    cats = [c.lower() for c in (m.get("categorias_todas") or [])]
    if stable or any(c.endswith(("stablecoin", "stablecoins")) for c in cats):
        return "stablecoin"
    return _TIPO_DE_SETORIAL[setorial.classificar(gid, m.get("categorias_todas"))]


def _idade_anos(raw: dict) -> float | None:
    g = raw.get("genesis_date")
    try:
        return (date.today() - date.fromisoformat(str(g)[:10])).days / 365.25
    except (TypeError, ValueError):
        return None


def _primeiro_num(dic) -> float | None:
    for v in (dic or {}).values():
        if isinstance(v, (int, float)):
            return float(v)
    return None


def _dados_stable(m: dict, ficha: dict | None) -> dict:
    s: dict = {}
    if ficha:
        s["peg_tipo"] = ficha.get("pegType")
        s["mecanismo"] = ficha.get("pegMechanism")
        circ, ant = _primeiro_num(ficha.get("circulating")), _primeiro_num(ficha.get("circulatingPrevMonth"))
        s["circulante_usd"] = circ
        if circ and ant and ant > 0:
            s["cresc30"] = circ / ant - 1
        if isinstance(ficha.get("chains"), list):
            s["n_cadeias"] = len(ficha["chains"])
    if s.get("peg_tipo") == "peggedUSD":
        precos = [p for _, p in (m.get("hist") or []) if p and p > 0]
        if len(precos) >= 60:
            desv = [abs(p - 1) for p in precos]
            s["dias_na_faixa"] = sum(1 for x in desv if x <= 0.005) / len(desv)
            s["desvio_max"] = max(desv)
    return s


def montar_dados(gid: str, m: dict, tipo: str, slug_defi: str | None, manual: dict) -> tuple[dict, list[str]]:
    """Junta tudo o que o motor precisa, reaproveitando o que o cripto.py já coleta. Retorna (dados, avisos)."""
    avisos: list[str] = []
    cat = {"bitcoin": "reserva", "reserva": "reserva", "defi": "defi", "stablecoin": "geral", "outros": "geral",
           "blockchain": "l1_performance" if gid in setorial.L1_PERFORMANCE else "l1_contratos"}[tipo]
    d0, extras, av = _coleta(gid, cat, slug_defi if tipo == "defi" else None)
    avisos += av
    raw = cripto._gecko_coin_raw(gid)                              # já em cache (mesma ficha da análise da moeda)
    d = dict(d0)
    d.update(tipo=tipo, nome=m["nome"], performance=(cat == "l1_performance"), rank=m.get("rank"),
             vol_anual=m.get("vol"), queda=m.get("queda"), tendencia=m.get("tendencia"), idade_anos=_idade_anos(raw),
             manual={k: v for k, v in (manual or {}).items() if v not in (None, [], "")})
    hist = extras.get("hist_tvl") or []
    d["tvl_var90"] = _var_tvl(hist, 90) if hist else None

    if tipo in ("bitcoin", "reserva"):                              # taxas da rede, para o orçamento de segurança
        cad = cripto._cadeia_da_moeda(gid)
        if cad:
            d["fees30"] = cripto._total30_cadeia("fees", cad["name"])
    if tipo == "bitcoin":
        btc = {}
        for chave, nome in (("hash_var90", "hash-rate"), ("enderecos_var90", "n-unique-addresses")):
            try:
                btc[chave] = _var_90d(_btc_serie(nome))
            except cripto.ErroAPI:
                avisos.append("O blockchain.com não respondeu agora: hashrate e endereços ativos ficam sem dados.")
                break
        d["btc"] = btc
    if tipo == "blockchain":
        if extras.get("cadeia") and not d.get("tem_queima"):
            d["holders30"] = cripto._total30_cadeia("fees", extras["cadeia"], "dailyHoldersRevenue")
        d["pares"] = _pares_blockchain(gid)
    if tipo == "defi":
        slug = (extras.get("protocolo") or {}).get("slug")
        if slug:
            d["holders30"] = _holders_protocolo(slug)
            try:
                t = _taxas_slug(_taxas_visao(), slug)
                d["fees_cresc"] = t["cresc"] if t else None
            except cripto.ErroAPI:
                avisos.append("O DefiLlama não entregou a série de taxas: o crescimento das taxas e as taxas dos pares ficam sem dados.")
        d["pares"] = _pares_defi(gid, tuple(m.get("categorias_todas") or []))
    if tipo == "stablecoin":
        try:
            ficha = _stablecoins_llama().get(gid)
        except cripto.ErroAPI:
            ficha = None
            avisos.append("O DefiLlama (stablecoins) não respondeu agora: lastro, redes e oferta ficam sem dados.")
        if ficha is None and not avisos:
            avisos.append("Esta moeda não está na lista de stablecoins do DefiLlama: lastro, redes e oferta ficam sem dados.")
        d["stable"] = _dados_stable(m, ficha)
    # desenvolvimento: a lista de repositórios vem da ficha já em cache; só consulta a CoinGecko se houver repositório público
    repos = [r for r in (((raw.get("links") or {}).get("repos_url") or {}).get("github") or []) if r]
    if repos:
        try:
            d["dev"] = {"repos": len(repos), **_dev_gecko(gid)}
        except cripto.ErroAPI:
            avisos.append("A CoinGecko não entregou dados de desenvolvimento agora.")
    return d, avisos


# =============================================================================== apresentação
def _cor(cls: str) -> str:
    return cripto.COR_CLS.get(cls, (cripto.MUTED, ""))[0]


def _faixa_nota(res: dict):
    cor = _cor(res["cls"])
    nota = "—" if res["nota"] is None else f"{res['nota']:.0f}"
    prov = " · provisória" if res["provisoria"] and res["nota"] is not None else ""
    faixa = ""
    if res["nota"] is not None and res.get("piso") is not None and res["teto"] - res["piso"] >= 5:
        faixa = (f"<div style='font-size:.8rem;color:{cripto.MUTED};margin-top:4px;'>Se os dados que faltam valessem 0 ou 100, "
                 f"a nota ficaria entre <b>{res['piso']:.0f}</b> e <b>{res['teto']:.0f}</b>. Dado ausente não é ponto a favor.</div>")
    esc = _html.escape
    _md(f'<div style="background:{cripto.SURFACE};border:1px solid {cripto.BORDER};border-left:6px solid {cor};border-radius:14px;'
        f'padding:14px 18px;margin:8px 0 10px;"><div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;">'
        f'<span style="font-size:2.6rem;font-weight:900;line-height:1;color:{cor};">{nota}</span>'
        f'<span style="font-size:.95rem;color:{cripto.MUTED};">/ 100</span>'
        f'<span style="font-weight:800;font-size:1.05rem;color:{cor};">{esc(res["rotulo"])}{prov}</span></div>'
        f'<div style="font-size:.85rem;color:{cripto.MUTED};margin-top:6px;"><b>{esc(res["tipo_rotulo"])}.</b> {esc(res["foco"])} '
        f'Cobertura dos dados: {res["cobertura"]:.0%}.</div>{faixa}</div>')


def _grafico_pilares(res: dict, gid: str):
    ps = list(reversed(res["pilares"]))
    nomes = [f"{ICONE_PILAR[p['chave']]} {p['nome'].split(' e ')[0].split(' (')[0]}" for p in ps]
    valores = [p["nota"] if p["nota"] is not None else 0 for p in ps]
    cores = [_cor(p["cls"]) if p["nota"] is not None else "#C9CFD6" for p in ps]
    textos = [f"{p['nota']:.0f}  (peso {p['peso_pct']:.0f}%)" if p["nota"] is not None else
              ("peso 0%" if p["peso"] <= 0 else "sem dados") for p in ps]
    fig = go.Figure(go.Bar(x=valores, y=nomes, orientation="h", marker_color=cores, text=textos, textposition="outside",
                           cliponaxis=False, hovertemplate="%{y}: %{x:.0f}<extra></extra>"))
    fig.update_layout(height=330, margin=dict(l=0, r=70, t=6, b=6), xaxis=dict(range=[0, 100], showgrid=False, visible=False),
                      yaxis=dict(automargin=True), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(size=12), showlegend=False)
    st.plotly_chart(fig, width="stretch", key=f"fund_pilares_{gid}", config={"displayModeBar": False})


def _cards(metricas: list):
    for i in range(0, len(metricas), 3):
        for col, x in zip(st.columns(3), metricas[i:i + 3]):
            cls = "na" if x.nota is None and x.peso > 0 else ("info" if x.peso <= 0 else mf.cls_nota(x.nota))
            nota = f"nota {x.nota:.0f}" if x.nota is not None else ("informativa" if x.peso <= 0 else "sem dado")
            origem = {"manual": "dado informado por você", "calculado": "calculado", "api": ""}.get(x.origem, "")
            detalhe = " · ".join(t for t in (x.leitura, nota, f"peso {x.peso:g}" if x.peso > 0 else "", origem, x.fonte) if t)
            col.markdown(tema.card_status(x.nome, x.valor, cls, detalhe, dica=x.dica).replace("$", "&#36;"), unsafe_allow_html=True)


def _bloco_captura(cap: dict, gid: str):
    esc = _html.escape
    cor = _cor(cap["cls"])
    linhas = ""
    for rot, v, frac in cap["etapas"]:
        pct = 0 if frac is None else max(0.0, min(1.0, frac))
        linhas += (f'<div style="margin:7px 0;"><div style="display:flex;justify-content:space-between;font-size:.85rem;color:{cripto.TEXT};">'
                   f'<span>{esc(rot)}</span><b>{esc(setorial.fmt_usd(v))}'
                   f'{"" if frac is None else " · " + esc(setorial.fmt_pct(frac * 100, 1))}</b></div>'
                   f'<div style="background:#E8ECF0;border-radius:6px;height:8px;"><div style="width:{pct * 100:.1f}%;background:{cor};'
                   f'height:8px;border-radius:6px;"></div></div></div>')
    _md(f'<div style="background:{cripto.SURFACE};border:1px solid {cripto.BORDER};border-radius:14px;padding:12px 16px;margin:6px 0 10px;">'
        f'<div style="font-weight:800;color:{cor};">{esc(cap["veredito"])}</div>'
        f'<div style="font-size:.78rem;color:{cripto.MUTED};margin:2px 0 6px;">Últimos 30 dias. Barras em % das taxas pagas pelos usuários.</div>'
        f'{linhas}<div style="font-size:.85rem;color:{cripto.TEXT};margin-top:8px;line-height:1.45;">{esc(cap["texto"])}</div></div>')


def _lista_md(itens: list[dict], vazio: str):
    if not itens:
        st.caption(vazio)
        return
    for x in itens:
        st.markdown(f"- **{x['metrica']}** ({x['valor']}, nota {x['nota']:.0f}): {x['texto']}".replace("$", "&#36;"), unsafe_allow_html=True)


def _mostrar_resultado(res: dict, gid: str):
    _faixa_nota(res)
    st.markdown("**Nota por pilar**")
    _grafico_pilares(res, gid)

    if res.get("captura"):
        st.markdown("**Receita do protocolo × valor capturado pelo token**")
        _bloco_captura(res["captura"], gid)

    st.markdown("**Detalhe dos pilares**")
    for p in res["pilares"]:
        nota = "sem dados" if p["nota"] is None else f"{p['nota']:.0f}/100"
        sufixo = "peso 0%" if p["peso"] <= 0 else f"peso {p['peso_pct']:.0f}%"
        with st.expander(f"{ICONE_PILAR[p['chave']]} {p['nome']} · {nota} · {sufixo}"):
            st.caption(dict(res["justificativas"])[p["nome"]].replace("$", "&#36;"))
            _cards(p["metricas"])

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("**✅ Pontos fortes**")
        _lista_md(res["fortes"], "Nenhuma métrica atingiu nota 70 ou mais.")
    with c2:
        st.markdown("**⚠️ Pontos fracos**")
        _lista_md(res["fracos"], "Nenhuma métrica ficou com nota 40 ou menos.")

    st.markdown("**🚩 Principais riscos**")
    marca = {"alto": "🔴", "médio": "🟠", "info": "ℹ️"}
    est = [t for n, t in res["riscos"] if n == "estrutural"]
    for n, t in res["riscos"]:
        if n != "estrutural":
            st.markdown(f"- {marca[n]} {t}")
    if est:
        with st.expander("Riscos estruturais deste tipo de ativo (regra geral, não vem dos dados)"):
            for t in est:
                st.markdown(f"- {t}")

    with st.expander("📝 Justificativa das notas"):
        for nome, txt in res["justificativas"]:
            st.markdown(f"**{nome}.** {txt}".replace("$", "&#36;"))

    cor = _cor(res["cls"])
    _md(f'<div style="background:{cripto.SURFACE};border:1px solid {cripto.BORDER};border-left:5px solid {cor};border-radius:12px;'
        f'padding:12px 16px;margin:10px 0;"><div style="font-weight:800;color:{cripto.TEXT};margin-bottom:4px;">Conclusão fundamentalista</div>'
        f'<div style="font-size:.9rem;color:{cripto.TEXT};line-height:1.5;">{_html.escape(res["conclusao"])}</div></div>')


# ------------------------------------------------------------------------------- painel de pesos e dados manuais
def _restaurar_pesos(gid: str, tipo: str):
    for k, v in mf.PESOS_PADRAO[tipo].items():
        st.session_state[f"fw_{gid}_{tipo}_{k}"] = v


def _painel_config(gid: str, tipo: str) -> tuple[dict, dict]:
    """Pesos dos pilares e dados manuais do ativo. Retorna (pesos, manual)."""
    pesos, manual = {}, {}
    with st.expander("⚙️ Pesos dos pilares e dados informados por você"):
        st.caption(f"Os pesos padrão são os de **{mf.TIPOS[tipo]}** e somam 100. Você pode mudá-los: o app normaliza para 100 na conta.")
        cols = st.columns(2)
        for i, (k, nome) in enumerate(mf.PILARES):
            pesos[k] = cols[i % 2].slider(nome, 0, 50, mf.PESOS_PADRAO[tipo][k], step=5, key=f"fw_{gid}_{tipo}_{k}")
        soma = sum(pesos.values())
        st.caption(f"Soma atual: {soma}" + ("" if soma == 100 else " (será normalizada para 100)"))
        st.button("Restaurar pesos padrão", key=f"fw_reset_{gid}_{tipo}", on_click=_restaurar_pesos, args=(gid, tipo))
        st.markdown("**Dados que nenhuma API gratuita fornece** (opcional; sem eles a métrica fica *n/d* e fora da nota)")
        if tipo != "stablecoin":
            manual["papeis"] = st.multiselect("Para que serve o token?", mf.PAPEIS, key=f"fm_pap_{gid}")
            manual["unlock12m"] = st.number_input("Suprimento a ser desbloqueado em 12 meses (% do total)", 0.0, 100.0,
                                                  value=None, step=1.0, key=f"fm_unl_{gid}", placeholder="Não informado")
        if tipo in ("bitcoin", "reserva", "blockchain"):
            manual["nakamoto"] = st.number_input("Coeficiente de Nakamoto", 1, 1000, value=None, step=1,
                                                 key=f"fm_nak_{gid}", placeholder="Não informado")
        if tipo in ("defi", "stablecoin", "outros"):
            manual["auditoria"] = st.selectbox("Auditorias de segurança", list(mf.AUDITORIA), index=None,
                                               placeholder="Não informado", key=f"fm_aud_{gid}")
        if tipo == "stablecoin":
            manual["reservas"] = st.selectbox("Transparência das reservas", list(mf.RESERVAS), index=None,
                                              placeholder="Não informado", key=f"fm_res_{gid}")
        manual["governanca"] = st.selectbox("Modelo de governança", list(mf.GOVERNANCA), index=None,
                                            placeholder="Não informado", key=f"fm_gov_{gid}")
    return pesos, manual


def _mostrar_moeda(gid: str):
    try:
        with st.spinner(f"Consultando a CoinGecko para “{gid}”…"):
            m = cripto.analisar_moeda(gid)
    except cripto.ErroAPI as e:
        st.error(f"Não consegui analisar “{gid}”: {e}. Remova da lista ou tente de novo em instantes.")
        return
    except Exception as e:  # erro inesperado não derruba o app
        st.error(f"Erro inesperado ao analisar “{gid}”: {e.__class__.__name__}.")
        return

    esc = _html.escape
    img = (f'<img src="{esc(m["logo"])}" width="40" height="40" style="border-radius:10px;background:#fff;padding:3px;'
           f'border:1px solid {cripto.BORDER};object-fit:contain;flex-shrink:0;">' if m["logo"].startswith("https://") else "")
    sim = f" ({esc(m['simbolo'])})" if m["simbolo"] else ""
    _md(f'<div style="display:flex;align-items:center;gap:12px;margin:6px 0 2px;">{img}<div>'
        f'<div style="font-size:1.2rem;font-weight:800;color:{cripto.TEXT};">{esc(m["nome"])}{sim} · {cripto._preco_usd(m["preco"])}</div>'
        f'<div style="font-size:.8rem;color:{cripto.MUTED};">{"Ranking #" + str(m["rank"]) if m["rank"] else "Sem ranking"}</div></div></div>')

    auto = _detectar_tipo(gid, m)
    chaves = list(mf.TIPOS)
    tipo = st.selectbox("Tipo do ativo", chaves, index=chaves.index(auto), key=f"fund_tipo_{gid}",
                        format_func=lambda k: mf.TIPOS[k] + (" (automático)" if k == auto else ""),
                        help="O tipo define as métricas e os pesos. Bitcoin, stablecoins, blockchains e DeFi não usam a mesma régua.")
    slug_defi = None
    if tipo == "defi":
        try:
            slugs = cripto.slugs_defi(gid, cripto.listar_protocolos())[:5]
        except Exception:
            slugs = []
        if len(slugs) > 1:
            slug_defi = st.selectbox("Protocolo (DefiLlama)", slugs, key=f"fund_slug_{gid}")

    pesos, manual = _painel_config(gid, tipo)
    try:
        with st.spinner("Reunindo dados e calculando os sete pilares…"):
            dados, avisos = montar_dados(gid, m, tipo, slug_defi, manual)
            res = mf.analisar(dados, pesos)
    except cripto.ErroAPI as e:
        st.warning(f"Não consegui reunir os dados agora ({e}). Tente de novo em instantes.")
        return
    except Exception as e:
        st.error(f"Erro inesperado na análise: {e.__class__.__name__}.")
        return
    for av in dict.fromkeys(avisos):
        st.caption(f"ℹ️ {av}")
    assistente.painel_resumo_auto(m["nome"], lambda: assistente.resumo_cripto(m["nome"], res))
    _mostrar_resultado(res, gid)


def pagina_fundamentalista():
    _md(tema.cabecalho("📊", "Análise Fundamentalista",
                       "Sete pilares, nota de 0 a 100 e conclusão, com critérios diferentes para Bitcoin, stablecoins, blockchains e DeFi."))
    st.session_state.setdefault("cripto_ativos", [])
    st.session_state.setdefault("cripto_nomes", {})
    if not cripto._chave_gecko():
        st.caption("⚠️ Sem chave da CoinGecko: as consultas podem falhar com frequência. Veja como configurar (grátis) na página Visão Geral & Tokenomics.")

    busca = st.segmented_control("Buscar por", ["Moeda", "Setor"], default="Moeda", key="cripto_modo",
                                 label_visibility="collapsed") or "Moeda"
    sel = st.session_state["cripto_ativos"]
    if busca == "Moeda":
        with st.form("form_cripto_busca"):
            c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
            c1.text_input("Buscar moeda", key="cripto_q", label_visibility="collapsed",
                          placeholder="Nome ou símbolo: Bitcoin, ETH, Solana, Uniswap, Aave, USDT…")
            c2.form_submit_button("Buscar", type="primary", width="stretch")
        termo = (st.session_state.get("cripto_q") or "").strip()
        if termo:
            try:
                achadas = cripto.buscar_moedas(termo)
            except cripto.ErroAPI as e:
                achadas = None
                st.warning(f"Não consegui buscar agora ({e}). Tente de novo em instantes.")
            if achadas:
                cripto._render_resultados(achadas, sel)
            elif achadas is not None:
                st.caption("Digite pelo menos 2 letras.") if len(cripto._norm(termo)) < 2 else st.info(
                    "Não encontrei essa moeda. Confira o nome ou tente o símbolo.")
        elif not sel:
            atalhos = [(n, g) for n, g in cripto.POPULARES.items() if n in ("Bitcoin", "Ethereum", "Uniswap", "Aave")] \
                or list(cripto.POPULARES.items())[:4]
            for col, (nome, gid) in zip(st.columns(4), atalhos):
                col.button(nome, key=f"fund_pop_{gid}", on_click=cripto._adicionar_cripto, args=(gid, nome), width="stretch")
    else:
        cripto._secao_setor(sel)

    nomes = {**{v: k for k, v in cripto.POPULARES.items()}, **st.session_state["cripto_nomes"]}
    opcoes = list(dict.fromkeys(sel + list(cripto.POPULARES.values())))
    st.multiselect("Moedas em análise", options=opcoes, key="cripto_ativos",
                   format_func=lambda g: nomes.get(g) or g.replace("-", " ").title(),
                   placeholder="Nenhuma moeda ainda: busque acima")
    sel = st.session_state["cripto_ativos"]
    if not sel:
        _md(tema.vazio("moeda", "Nenhuma moeda em análise",
                       "Busque pelo nome, símbolo ou setor e toque em Adicionar para ver a análise fundamentalista."))
        return

    for gid in sel[:MAX_MOEDAS]:
        st.divider()
        _mostrar_moeda(gid)
    if len(sel) > MAX_MOEDAS:
        st.caption(f"Mostrando {MAX_MOEDAS} de {len(sel)} moedas, para não estourar o limite de consultas da CoinGecko. "
                   "Remova alguma da lista para ver as demais.")

    with st.expander("Como a nota é calculada (e o que ela deixa de fora)"):
        st.markdown(
            "- **Cada tipo tem a sua régua.** Bitcoin é avaliado por escassez, aceitação e segurança; stablecoin por paridade, lastro e "
            "transparência; blockchain por uso real, quem paga a segurança e o que chega ao token; DeFi pela receita e, sobretudo, "
            "pelo que chega ao detentor.\n"
            "- **Receita do protocolo não é valor do token.** O app separa taxas pagas pelos usuários, receita do protocolo e "
            "o que é de fato queimado, recomprado ou distribuído ao detentor.\n"
            "- **Sem Graham, Bazin ou fluxo de caixa descontado.** Não há lucro contábil, dividendos regulares nem fluxo de caixa "
            "estável a descontar. O valuation usa P/S, Preço/Taxas, rendimento efetivo ao detentor e comparação com pares. "
            "Para Bitcoin e stablecoins o pilar de valuation não se aplica.\n"
            "- **Dado ausente fica fora da nota**, não vira zero nem valor neutro. Um pilar só recebe nota com pelo menos 40% dos seus "
            "dados; a nota geral só aparece com pelo menos 50% de cobertura, e abaixo de 70% é marcada como provisória. "
            "A faixa mostra o efeito do que falta.\n"
            "- **Pesos configuráveis** no painel de cada moeda; os dados informados por você aparecem identificados.\n"
            "- Os limites das notas são regras educacionais e podem ser contestados.")
    st.caption("Dados de mercado, desenvolvimento e oferta por [CoinGecko](https://www.coingecko.com); TVL, taxas, receita, stablecoins e "
               "pares por [DefiLlama](https://defillama.com); hashrate e endereços do Bitcoin por blockchain.com (dados públicos, "
               "cache de 10 min a 1 h). Ferramenta educacional, não é recomendação de investimento. Criptomoedas são muito voláteis "
               "e você pode perder todo o valor investido.")
