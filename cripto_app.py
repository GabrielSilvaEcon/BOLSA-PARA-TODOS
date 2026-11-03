"""
Página de criptomoedas — análise avançada (Passo 9): coleta e telas. Os cálculos estão em cripto_analise.py (puro).

Reaproveita as integrações que o app já tem (cripto.py, fundamentalista_cripto.py, evolucao.py): CoinGecko, DefiLlama,
blockchain.com (Bitcoin), RPC da Solana e GitHub. Nada é inventado: o que nenhuma fonte entrega aparece como "sem fonte".
"""
from __future__ import annotations

import html as _html
import re
from datetime import date, datetime, timezone

import pandas as pd
import streamlit as st

import cripto
import cripto_analise as ca
import evolucao
import fundamentalista_cripto as fc
import tema

try:
    import requests
except Exception:                         # pragma: no cover
    requests = None

NIVEL = {"alto": ("🔴", "Alto"), "medio": ("🟡", "Médio"), "baixo": ("🟢", "Baixo"), "indeterminado": ("⚪", "Sem dado")}
SELO = {"provedor": "dado do provedor", "calculado": "calculado pelo app", "blockchain": "registrado na blockchain",
        "estimativa": "estimativa de provedor", "sem_fonte": "sem fonte"}
UA = {"User-Agent": "BolsaParaTodos/1.0", "Accept": "application/vnd.github+json"}


# =============================================================================== formatação
def _n(v, casas=2) -> str:
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt(v, tipo: str) -> str:
    if v is None or (isinstance(v, float) and v != v):
        return "n/d"
    if tipo in ("usd", "usd_p"):
        if tipo == "usd_p":
            casas = 2 if abs(v) >= 1 else 4 if abs(v) >= 0.01 else 8
            return f"US$ {_n(v, casas)}"
        for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
            if abs(v) >= lim:
                return f"US$ {_n(v / lim)}{suf}"
        return f"US$ {_n(v)}"
    if tipo == "pct_f":
        return f"{_n(v, 1)}%" if abs(v) < 1000 else f"{_n(v, 0)}%"
    if tipo == "pct_s":
        return f"{v:+.1f}%".replace(".", ",")
    if tipo == "ratio":
        return f"{_n(v, 2)}×"
    if tipo == "qtd":
        for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi")):
            if abs(v) >= lim:
                return f"{_n(v / lim)}{suf}"
        return _n(v, 0)
    return str(v)


def _data_br(iso) -> str:
    try:
        return datetime.fromisoformat(str(iso)[:10]).strftime("%d/%m/%Y")
    except Exception:
        return "—"


def _tabela(linhas: list[dict], com_nota: bool = True) -> pd.DataFrame:
    rows = []
    for l in linhas:
        rows.append({"Indicador": l["rotulo"], "Valor": fmt(l["valor"], l["fmt"]), "Origem": l["fonte"],
                     "Tipo": SELO.get(l["tipo"], l["tipo"]), "Data": _data_br(l["data"]) if l.get("data") else "—",
                     **({"Observação": l.get("nota") or ""} if com_nota else {})})
    return pd.DataFrame(rows)


# =============================================================================== coleta (com cache)
@st.cache_data(ttl=3600, show_spinner=False)
def _hacks():
    """Lista de incidentes do DefiLlama. None = fonte indisponível (não é o mesmo que 'nenhum incidente')."""
    try:
        d = cripto._get_json(f"{cripto.LLAMA}/hacks", None, 2)
    except Exception:
        return None
    return d if isinstance(d, list) else None


@st.cache_data(ttl=3600, show_spinner=False)
def _proto_raw(slug: str):
    try:
        d = cripto._get_json(f"{cripto.LLAMA}/protocol/{slug}", None, 2)
    except Exception:
        return None
    return d if isinstance(d, dict) else None


@st.cache_data(ttl=3600, show_spinner=False)
def _github(repo_url: str):
    """Última versão publicada e último push de um repositório público. None se não responder."""
    m = re.match(r"https?://github\.com/([^/]+)/([^/#?]+)", repo_url or "")
    if not m or requests is None:
        return None
    dono, nome = m.group(1), m.group(2).removesuffix(".git")
    out = {"repo": f"{dono}/{nome}", "url": f"https://github.com/{dono}/{nome}"}
    try:
        r = requests.get(f"https://api.github.com/repos/{dono}/{nome}", headers=UA, timeout=8)
        if r.status_code == 200:
            j = r.json()
            out.update(push=str(j.get("pushed_at") or "")[:10], estrelas=j.get("stargazers_count"), arquivado=bool(j.get("archived")))
        rr = requests.get(f"https://api.github.com/repos/{dono}/{nome}/releases/latest", headers=UA, timeout=8)
        if rr.status_code == 200:
            j = rr.json()
            d = str(j.get("published_at") or "")[:10]
            out.update(tag=j.get("tag_name"), data=d, release_url=j.get("html_url"))
            try:
                out["dias"] = (date.today() - date.fromisoformat(d)).days
            except ValueError:
                pass
    except Exception:
        return None
    return out if len(out) > 2 else None


def _serie_btc(nome: str):
    try:
        s = fc._btc_serie(nome)
    except Exception:
        return None
    if len(s) < 30:
        return None
    recente = [y for x, y in s if x >= s[-1][0] - 7 * 86400]
    v90 = fc._var_90d(s)
    return {"valor": sum(recente) / len(recente), "var_90d": v90 * 100 if v90 is not None else None,
            "data": datetime.fromtimestamp(s[-1][0], tz=timezone.utc).date().isoformat()}


def _tipo_stable(ficha: dict | None) -> str:
    p = str((ficha or {}).get("pegMechanism") or "").lower()
    return "fiat" if "fiat" in p else "cripto" if "crypto" in p else "algoritmica" if "algorithm" in p else "desconhecido"


@st.cache_data(ttl=900, show_spinner=False)
def pares_da_categoria(gid: str, categorias: tuple, princ: str, quantos: int = 10) -> dict:
    """Maiores moedas da mesma categoria (CoinGecko). {'categoria', 'moedas'}; vazio se não houver rótulo ou a fonte falhar."""
    rotulo = ca.categoria_para_pares(list(categorias), princ)
    if not rotulo:
        return {"categoria": None, "moedas": []}
    try:
        inv = {n.lower(): i for i, n in cripto.listar_setores().items()}
        sid = inv.get(rotulo.lower())
        if not sid:
            return {"categoria": rotulo, "moedas": []}
        return {"categoria": rotulo, "moedas": [c for c in cripto.moedas_do_setor(sid, quantos + 1) if c["id"] != gid][:quantos]}
    except Exception:
        return {"categoria": rotulo, "moedas": []}


@st.cache_data(ttl=600, show_spinner=False)
def coletar(gid: str) -> dict:
    """Tudo o que a página precisa para uma moeda. Levanta cripto.ErroAPI só se a CoinGecko não tiver a moeda;
    as demais falhas viram avisos e o item correspondente fica 'sem fonte'."""
    avisos: list[str] = []
    m = cripto.analisar_moeda(gid)
    raw = cripto._gecko_coin_raw(gid)
    try:
        glob = {"total_mcap": cripto._mercado_total_usd(), "data": date.today().isoformat()}
    except Exception:
        glob = None
    # a categoria do DefiLlama só vem do protocolo; primeiro a classificação pelos rótulos da CoinGecko
    classes = ca.classificar(gid, m.get("categorias_todas"))
    chaves = [c["chave"] for c in classes]
    princ = ca.principal(classes)

    proto = proto_raw = cadeia = None
    tvl = fees30 = rev30 = dex30 = None
    hist_tvl: list = []
    if {"defi", "staking", "governanca", "oraculo", "exchange"} & set(chaves):
        try:
            slugs = cripto.slugs_defi(gid, cripto.listar_protocolos())[:3]
        except Exception:
            slugs = []
            avisos.append("O DefiLlama não respondeu agora: TVL, taxas e receita do protocolo ficaram sem dados.")
        for slug in slugs:
            try:
                proto = cripto.analisar_protocolo(slug)
                proto_raw = _proto_raw(slug)
                tvl, fees30, hist_tvl = proto.get("tvl"), proto.get("fees30"), proto.get("hist_tvl") or []
                rev30 = cripto._total_30d(cripto._resumo_llama("fees", slug, "dailyRevenue"))
                break                                      # o primeiro protocolo que responder (como o cripto.coletar_dados)
            except Exception:
                proto = None
    if gid != "bitcoin" and ({"layer1", "layer2", "infra"} & set(chaves) or proto is None):
        # Bitcoin fica de fora: o "TVL" do DefiLlama para a rede Bitcoin é BTC embrulhado em outras redes e as taxas
        # não são as da rede; usar isso geraria múltiplos sem sentido (ex.: Preço/Taxas de 230 mil vezes).
        cad = cripto._cadeia_da_moeda(gid)
        if cad:
            cadeia = cad
            tvl = tvl if tvl is not None else cad.get("tvl")
            fees30 = fees30 if fees30 is not None else cripto._total30_cadeia("fees", cad["name"])
            rev30 = rev30 if rev30 is not None else cripto._total30_cadeia("fees", cad["name"], "dailyRevenue")
            dex30 = cripto._total30_cadeia("dexs", cad["name"])
            hist_tvl = hist_tvl or cripto._tvl_hist_cadeia(cad["name"])

    eh_stable = "stablecoin" in chaves
    ficha = None
    if eh_stable or princ == "stablecoin":
        try:
            ficha = fc._stablecoins_llama().get(gid)
            eh_stable = eh_stable or ficha is not None
        except Exception:
            avisos.append("O DefiLlama (stablecoins) não respondeu agora: tipo de lastro e redes ficaram sem dados.")

    onchain_in: dict = {"tvl": {"valor": tvl, "data": date.today().isoformat()} if tvl else None,
                        "taxas_30d": fees30, "receita_30d": rev30, "volume_dex_30d": dex30}
    if gid == "bitcoin":
        onchain_in["hash_rate"] = _serie_btc("hash-rate")
        onchain_in["enderecos_ativos"] = _serie_btc("n-unique-addresses")
        if onchain_in["hash_rate"] is None:
            avisos.append("O blockchain.com não respondeu agora: hash rate e endereços ativos ficaram sem dados.")
    if gid == "solana":
        onchain_in["tps"] = cripto.tps_solana()
    if "layer1" in chaves and gid != "bitcoin":
        onchain_in["usuarios_ativos"] = cripto.dau_rede(m.get("simbolo") or "")

    repos = [r for r in (((raw.get("links") or {}).get("repos_url") or {}).get("github") or []) if r]
    dev = None
    if repos:
        try:
            dev = {"repos": len(repos), **fc._dev_gecko(gid)}
            onchain_in["commits_4w"] = dev.get("commits_4w")
        except Exception:
            avisos.append("A CoinGecko não entregou dados de desenvolvimento agora.")
    gh = _github(repos[0]) if repos else None

    infl = cripto.inflacao_anual(gid)
    ev = evolucao.coletar_cripto(gid)
    fund = None
    try:
        tipo = fc._detectar_tipo(gid, m)
        dados, av = fc.montar_dados(gid, m, tipo, None, {})
        res = fc.mf.analisar(dados)
        fund = {"nota": res.get("nota"), "veredito": res.get("veredito"),
                "tipo": res.get("tipo_rotulo"), "cobertura": res.get("cobertura")}
    except Exception:
        avisos.append("A nota fundamentalista não pôde ser calculada agora.")

    merc = ca.mercado(raw, glob, m.get("hist"))
    nome_proj = (proto or {}).get("nome") or m["nome"]
    expl = ca.exploits_do_projeto(_hacks(), nome_proj, (proto_raw or {}).get("id"))
    aud = ca.auditorias(proto_raw)
    peg = None
    if eh_stable and merc["calc"]["preco"]:
        peg = (merc["calc"]["preco"] - 1) * 100            # preço-alvo em dólar; stablecoins de outras moedas ficam sem desvio
        if "eur" in " ".join(m.get("categorias_todas") or []).lower() or "euro" in m["nome"].lower():
            peg = None
    cats_txt = " ".join(m.get("categorias_todas") or []).lower()
    ponte = bool(re.search(r"bridged|wrapped|bridge", cats_txt + " " + m["nome"].lower())) or any(i["ponte"] for i in expl["itens"])
    return {"m": m, "raw": raw, "glob": glob, "classes": classes, "chaves": chaves, "princ": princ, "mercado": merc,
            "proto": proto, "proto_raw": proto_raw, "cadeia": cadeia, "tvl": tvl, "fees30": fees30, "rev30": rev30,
            "dex30": dex30, "hist_tvl": hist_tvl, "eh_stable": eh_stable, "tipo_stable": _tipo_stable(ficha) if eh_stable else None,
            "peg": peg, "onchain_in": onchain_in, "dev": dev, "github": gh, "infl": infl, "ev": ev, "fund": fund,
            "expl": expl, "aud": aud, "ponte": ponte, "plataforma": raw.get("asset_platform_id") or None,
            "avisos": list(dict.fromkeys(avisos + m.get("avisos", []) + ev.get("avisos", [])))}


@st.cache_data(ttl=900, show_spinner=False)
def linha_comparacao(gid: str) -> dict:
    """Uma linha de comparação (indicadores de mercado, valuation e histórico) de uma moeda. Falha → {'erro': ...}."""
    try:
        m = cripto.analisar_moeda(gid)
    except Exception as e:
        return {"gid": gid, "nome": gid, "erro": str(e)}
    mc, fdv, v24 = m.get("mcap"), m.get("fdv"), m.get("vol24")
    s = ca.serie_de_pares(m.get("hist"))
    classes = ca.classificar(gid, m.get("categorias_todas"))
    princ = ca.principal(classes)
    tvl = fees30 = None
    try:
        cad = cripto._cadeia_da_moeda(gid)
        if cad:
            tvl = cad.get("tvl")
            fees30 = cripto._total30_cadeia("fees", cad["name"])
        elif princ in ("defi", "staking", "oraculo", "governanca", "exchange"):
            for sl in cripto.slugs_defi(gid, cripto.listar_protocolos())[:3]:
                try:
                    a = cripto.analisar_protocolo(sl)
                except Exception:
                    continue
                tvl, fees30 = a.get("tvl"), a.get("fees30")
                break
    except Exception:
        pass
    val = ca.valuation(princ, mc, fdv, tvl, fees30)
    vd = {i["chave"]: i["valor"] for i in val["itens"]}
    return {"gid": gid, "nome": m["nome"], "simbolo": m["simbolo"], "princ": princ, "mcap": mc,
            "giro": (v24 / mc) if mc and v24 is not None else None, "var30": m.get("var30"), "var1a": m.get("var1a"),
            "vol_anual": ca.volatilidade(s), "dd_max": ca.drawdown_maximo(s), "mc_fdv": (mc / fdv) if mc and fdv else None,
            "tvl": tvl if tvl and tvl > 0 else None, "mc_tvl": vd.get("mc_tvl"), "p_taxas": vd.get("p_taxas")}


# =============================================================================== telas
def _aviso_fonte(d):
    m = d["mercado"]
    st.caption(f"Fonte: {m['fonte']} · dados de {_data_br(m['data'])}. " + " ".join(m["avisos"]))


def _aba_visao(d, alertas):
    mc = d["mercado"]["calc"]
    st.markdown("**Classificação:** " + " · ".join(f"`{c['rotulo']}`" for c in d["classes"]))
    with st.expander("Por que esta classificação?"):
        for c in d["classes"]:
            st.markdown(f"- **{c['rotulo']}**: {c['motivo']}")
        st.caption("Um projeto pode ter mais de uma categoria. A principal (a primeira) define com quem ele é comparado.")
    a, b = st.columns(2)
    a.metric("Preço", fmt(mc["preco"], "usd_p"))
    b.metric("Valor de mercado", fmt(mc["mcap"], "usd"))
    a, b = st.columns(2)
    a.metric("FDV", fmt(mc["fdv"], "usd"))
    b.metric("Ranking", f"#{mc['rank']}" if mc.get("rank") else "n/d")
    if d.get("fund") and d["fund"].get("nota") is not None:
        st.metric("Nota fundamentalista (7 pilares)", f"{d['fund']['nota']:.0f}/100",
                  help="A mesma nota da página Análise Fundamentalista. " + (d["fund"].get("veredito") or ""))
    rk = d["riscos"]
    ic, rot = NIVEL[rk["geral"]]
    st.markdown(f"**Risco geral nas fontes integradas:** {ic} {rot} — cobertura {rk['cobertura']:.0%} dos riscos medidos. "
                "Veja a aba Segurança.")
    if alertas:
        for al in alertas[:4]:
            (st.error if al["nivel"] == "alto" else st.warning if al["nivel"] == "atencao" else st.info)(
                f"**{al['titulo']}** — {al['texto']} _(fonte: {al['fonte']})_")
    else:
        st.caption("Nenhum alerta com dado verificável agora. Isso não significa ausência de eventos: veja o que não é monitorado na aba Análise inteligente.")
    for av in d["avisos"]:
        st.caption("⚠️ " + av)
    _aviso_fonte(d)


def _aba_mercado(d):
    st.dataframe(_tabela(d["mercado"]["linhas"]), hide_index=True, width="stretch")
    s = d["ev"]["series"]
    preco = s.get("Preço (USD)")
    if preco is not None and len(preco):
        st.plotly_chart(evolucao.grafico_linhas({"Preço (USD)": preco}, "Preço (USD), últimos 365 dias"), use_container_width=True)
    vol = s.get("Volume diário (USD)")
    if vol is not None and len(vol):
        st.plotly_chart(evolucao.grafico_linhas({"Volume diário (USD)": vol}, "Volume diário (USD)"), use_container_width=True)
    st.caption("Dominância = valor de mercado da moeda ÷ valor de mercado total das criptomoedas (CoinGecko). "
               "Liquidez aqui é o giro (volume ÷ valor de mercado); a profundidade do livro de ofertas não tem fonte integrada.")
    _aviso_fonte(d)


def _aba_fundamentos(d):
    f = ca.fundamentos(d["raw"], d.get("dev"), d.get("github"), d.get("proto_raw"), d["chaves"])
    it = f["itens"]
    if it["objetivo"]:
        st.markdown("**Objetivo e problema que procura resolver** (texto do projeto):")
        st.write(it["objetivo"])
    else:
        st.info("A CoinGecko não traz descrição deste projeto.")
    linhas = [("Tecnologia", it["tecnologia"]), ("Início (gênese)", _data_br(it["inicio"]) if it["inicio"] else None),
              ("Categoria no DefiLlama", it["categoria_defillama"]),
              ("Ecossistema (redes)", ", ".join(it["ecossistema"]) if it["ecossistema"] else None)]
    st.dataframe(pd.DataFrame([{"Item": k, "Informação": v or "sem fonte"} for k, v in linhas]), hide_index=True, width="stretch")
    st.markdown("**Utilidade do token**")
    st.write(it["utilidade_token"])
    st.caption(f["utilidade_nota"])
    if it["site"]:
        st.markdown(f"Site oficial: [{it['site']}]({it['site']})")
    for r in it["repositorios"]:
        st.markdown(f"Repositório: [{r}]({r})")
    dv, gh = it["dev"], it["github"]
    if dv:
        a, b, c = st.columns(3)
        a.metric("Commits (4 sem.)", fmt(dv.get("commits_4w"), "qtd"))
        b.metric("Contribuidores", fmt(dv.get("contribuidores"), "qtd"))
        c.metric("Estrelas", fmt(dv.get("stars"), "qtd"))
    if gh:
        txt = f"GitHub {gh['repo']}: último push em {_data_br(gh.get('push'))}" if gh.get("push") else f"GitHub {gh['repo']}"
        if gh.get("tag"):
            txt += f"; última versão {gh['tag']} ({_data_br(gh.get('data'))})"
        st.caption(txt + (" — repositório arquivado." if gh.get("arquivado") else "."))
    if not dv and not gh:
        st.caption("Sem repositório público informado: desenvolvimento não medido.")
    ra = d["aud"]
    if ra["disponivel"]:
        st.markdown(f"**Auditorias listadas (DefiLlama):** {ra['n']}")
        for l in ra["links"]:
            st.markdown(f"- [{l}]({l})")
    with st.expander("O que não conseguimos verificar"):
        for l in f["lacunas"]:
            st.markdown("- " + l)
    st.caption(f["aviso"])


def _add_desbloqueio(gid: str):
    ss = st.session_state
    ev = {"data": ss.get("ub_data"), "quantidade": ss.get("ub_qtd"), "fonte": (ss.get("ub_fonte") or "").strip(),
          "descricao": (ss.get("ub_desc") or "").strip()}
    teste = ca.desbloqueios([ev], 1.0, None)
    if teste["recusados"]:
        ss["ub_msg"] = "Evento recusado: " + teste["recusados"][0]["motivo"] + "."
        return
    ss.setdefault("cripto_desbloqueios", {}).setdefault(gid, []).append({**ev, "data": ev["data"].isoformat()})
    ss["ub_msg"] = "Evento guardado nesta sessão."


def _rm_desbloqueio(gid: str, i: int):
    lst = st.session_state.get("cripto_desbloqueios", {}).get(gid, [])
    if 0 <= i < len(lst):
        lst.pop(i)


def _aba_tokenomics(d, tk, desb):
    c1, c2 = st.columns(2)
    c1.metric("Oferta circulante", fmt(tk["circ"], "qtd"))
    c2.metric("Oferta máxima", fmt(tk["maximo"], "qtd") if tk["teto_definido"] else "sem teto")
    c1, c2 = st.columns(2)
    c1.metric("Ainda por circular", fmt(tk["pct_a_entrar"], "pct_f"), help="Parte da oferta final (máxima ou total) que ainda não circula.")
    c2.metric("Inflação da oferta (12m)", fmt(tk["inflacao_12m"], "pct_s"), help=tk["nota_inflacao"])
    linhas = [
        ("Oferta total", fmt(tk["total"], "qtd")), ("Circulante ÷ máxima", fmt(tk["circ_max"] * 100 if tk["circ_max"] is not None else None, "pct_f")),
        ("Circulante ÷ total", fmt(tk["circ_total"] * 100 if tk["circ_total"] is not None else None, "pct_f")),
        ("FDV ÷ valor de mercado", fmt(tk["fdv_mc"], "ratio")), ("Risco de diluição", tk["diluicao"]),
        ("Faixa de inflação", tk["faixa_inflacao"]),
        ("Receita ao detentor (30d)", fmt(tk["receita_ao_detentor_30d"], "usd")),
    ]
    st.dataframe(pd.DataFrame(linhas, columns=["Indicador", "Valor"]), hide_index=True, width="stretch")
    for a in tk["avisos"]:
        st.caption("⚠️ " + a)
    st.caption(tk["nota_inflacao"])
    with st.expander("O que não conseguimos medir (sem fonte gratuita integrada)"):
        for nome, porque in tk["lacunas"]:
            st.markdown(f"- **{nome}** — {porque}")
    st.markdown("#### Desbloqueios que você acompanha")
    st.caption("Informe um evento com o link da fonte (documentação oficial, painel de vesting). Sem link, o evento é recusado.")
    with st.form("form_desbloqueio"):
        a, b = st.columns(2)
        a.date_input("Data do desbloqueio", key="ub_data", value=date.today())
        b.number_input("Quantidade de tokens", key="ub_qtd", min_value=0.0, value=0.0, format="%.2f")
        st.text_input("Link da fonte", key="ub_fonte", placeholder="https://...")
        st.text_input("Descrição (opcional)", key="ub_desc", placeholder="Ex.: liberação da equipe")
        st.form_submit_button("Guardar evento", on_click=_add_desbloqueio, args=(d["m"]["id"],))
    if st.session_state.get("ub_msg"):
        st.caption(st.session_state["ub_msg"])
    for i, e in enumerate(desb["eventos"]):
        pct = f"{e['pct_circulante']:.2f}% da oferta circulante" if e["pct_circulante"] is not None else "sem oferta circulante para comparar"
        quando = "passado" if e["passado"] else "em " + str(e["dias"]) + " dias"
        st.markdown(f"- {_data_br(e['data'])} ({quando}): {_n(e['quantidade'], 0)} tokens, "
                    f"{pct}, {fmt(e['valor_usd'], 'usd')} · [{e['nivel'] or 'n/d'}]({e['fonte']})")
        st.button("Remover", key=f"ub_rm_{i}", on_click=_rm_desbloqueio, args=(d["m"]["id"], i))
    if desb["eventos"]:
        st.caption(desb["aviso"])


def gid_btc(d) -> bool:
    return d["m"]["id"] == "bitcoin"


def _aba_onchain(d, oc):
    st.markdown("**Registrado na blockchain** (lido diretamente da rede)")
    if oc["registrados"]:
        for i in oc["registrados"]:
            extra = f" · variação ~90 dias: {fmt(i['var_90d'], 'pct_s')}" if i.get("var_90d") is not None else ""
            st.markdown(f"- **{i['rotulo']}:** {fmt(i['valor'], i['fmt'])}{extra} — _{i['fonte']}_")
    else:
        st.caption("Nenhum indicador lido direto da blockchain para este ativo. Só a rede Bitcoin (blockchain.com) e a Solana (RPC) estão integradas.")
    st.markdown("**Estimativas e agregações de provedores** (metodologia do provedor)")
    if oc["estimativas"]:
        for i in oc["estimativas"]:
            st.markdown(f"- **{i['rotulo']}:** {fmt(i['valor'], i['fmt'])} — _{i['fonte']}_")
    else:
        st.caption("Sem TVL, taxas ou volume medidos para este ativo.")
    var30 = ca.variacao(d["ev"].get("tvl"), 30) if d["ev"].get("tvl") is not None and len(d["ev"]["tvl"]) else None
    if var30 is not None:
        st.caption(f"TVL: variação em 30 dias {fmt(var30, 'pct_s')} (DefiLlama).")
    so_de = {"tps": "solana", "hash_rate": "bitcoin", "enderecos_ativos": "bitcoin"}
    aus = [a for a in oc["ausentes"] if so_de.get(a["chave"], d["m"]["id"]) == d["m"]["id"]]
    if gid_btc(d):
        st.caption("Bitcoin: TVL, taxas e volume em DEXs do DefiLlama não são usados (medem BTC embrulhado em outras redes, não a rede Bitcoin).")
    if aus:
        with st.expander("Indicadores sem dado para este ativo"):
            for a in aus:
                st.markdown(f"- {a['rotulo']} — fonte possível: {a['fonte_possivel']}")
    with st.expander("O que nenhuma fonte gratuita integrada entrega"):
        for l in oc["lacunas"]:
            st.markdown("- " + l)
    st.caption("TVL e taxas são estimativas do DefiLlama sobre contratos monitorados; não são lidas por este app direto na blockchain.")


def _aba_seguranca(d, rk):
    ic, rot = NIVEL[rk["geral"]]
    st.markdown(f"### {ic} Risco geral: {rot}")
    st.caption(rk["aviso"])
    for r in rk["riscos"]:
        ic, rot = NIVEL[r["nivel"]]
        with st.expander(f"{ic} {r['rotulo']} — {rot}"):
            st.write(r["texto"])
            st.caption(f"Base: {r['base']}")
    ex = d["expl"]
    if ex["disponivel"] and ex["itens"]:
        st.markdown("**Incidentes registrados (DefiLlama):**")
        for i in ex["itens"][:8]:
            st.markdown(f"- {_data_br(i['data'])}: {fmt(i['valor_usd'], 'usd')}" + (f" · {i['tecnica']}" if i.get("tecnica") else "")
                        + (f" · [fonte]({i['fonte']})" if str(i.get("fonte") or "").startswith("http") else ""))
    st.caption(d["aud"].get("aviso") or "")


def _aba_valuation(d, va):
    c = d["mercado"]["calc"]
    if d["pares_lista"] and st.checkbox("Comparar com os concorrentes da categoria (consulta até 6 projetos; demora mais)",
                                         key=f"val_pares_{d['m']['id']}"):
        with st.spinner("Coletando os concorrentes..."):
            pares = [linha_comparacao(p["id"]) for p in d["pares_lista"][:6]]
        va = ca.valuation(d["princ"], c["mcap"], c["fdv"], d["tvl"], d["fees30"], d["rev30"], c["vol24"],
                          [p for p in pares if not p.get("erro")])
        st.caption("Pares usados: " + ", ".join(p["nome"] for p in pares if not p.get("erro")) + ". A mediana só aparece com 3 ou mais pares com o dado.")
    st.caption(f"Família econômica: **{va['familia']}**. Múltiplos só aparecem quando o dado existe e a categoria comporta.")
    rows = []
    for i in va["itens"]:
        rows.append({"Indicador": i["rotulo"], "Valor": fmt(i["valor"], i["fmt"]),
                     "Mediana dos pares": fmt(i["mediana_pares"], i["fmt"]) if i["mediana_pares"] is not None else "—",
                     "Posição": i["posicao"] or "—", "Como ler": i["nota"]})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if va["nao_aplicaveis"]:
        with st.expander("Não calculados (e por quê)", expanded=not [i for i in va["itens"] if i["fmt"] == "ratio"]):
            for n in va["nao_aplicaveis"]:
                st.markdown("- " + n)
    st.caption(va["aviso"])


def _aba_historico(d, h):
    s = d["ev"]["series"]
    p = h["preco"]
    a, b = st.columns(2)
    a.metric("Retorno de preço 1 ano", fmt(p["ret"].get(365), "pct_s"))
    b.metric("Volatilidade anualizada", fmt(p["vol"], "pct_f"))
    a, b = st.columns(2)
    a.metric("Drawdown máximo", fmt(p["dd_max"], "pct_s"))
    b.metric("Drawdown atual", fmt(p["dd_atual"], "pct_s"))
    cg = p["cagr"]
    if cg["cagr"] is not None:
        st.metric(f"CAGR do preço ({cg['anos']:.1f} anos)", fmt(cg["cagr"], "pct_s"),
                  help=f"{_data_br(cg['inicio'])} a {_data_br(cg['fim'])}. " + cg["nota"])
    else:
        st.caption("CAGR do preço: " + cg["nota"])
    st.caption(h["retorno_nota"])
    rets = pd.DataFrame([{"Período": f"{k} dias", "Retorno de preço": fmt(v, "pct_s")} for k, v in p["ret"].items()])
    st.dataframe(rets, hide_index=True, width="stretch")
    graficos = [("Preço (USD)", "Evolução do preço"), ("Valor de mercado (USD)", "Evolução da capitalização"),
                ("Volume diário (USD)", "Volume diário"), ("Oferta circulante (calculada)", "Oferta circulante (calculada)")]
    for nome, tit in graficos:
        ser = s.get(nome)
        if ser is not None and len(ser):
            st.plotly_chart(evolucao.grafico_linhas({nome: ser}, tit), use_container_width=True)
    if h["oferta"]:
        st.caption(h["oferta"]["nota"])
    tvl = d["ev"].get("tvl")
    if tvl is not None and len(tvl):
        st.plotly_chart(evolucao.grafico_linhas({"TVL (USD)": tvl}, "Histórico de TVL"), use_container_width=True)
        if h["tvl"]:
            st.caption(f"TVL: 30 dias {fmt(h['tvl']['var_30'], 'pct_s')} · 90 dias {fmt(h['tvl']['var_90'], 'pct_s')} · 12 meses {fmt(h['tvl']['var_365'], 'pct_s')}.")
    else:
        st.caption("Histórico de TVL: sem dados para este ativo.")
    st.caption("Histórico de receitas/taxas e de atividade da rede por período: sem série diária integrada (só o total de 30 dias). "
               "Valor de mercado, volume e oferta: a CoinGecko gratuita entrega 365 dias.")
    if p["usou_longo"]:
        st.caption("O CAGR usa o histórico longo do Yahoo Finance, conferido com a CoinGecko.")


def _aba_comparacao(d, atalho_comparar):
    par = pares_da_categoria(d["m"]["id"], tuple(d["m"].get("categorias_todas") or []), d["princ"])
    if not par["moedas"]:
        st.info("Não encontrei concorrentes da mesma categoria agora (a categoria não existe na CoinGecko ou a fonte não respondeu).")
        return
    st.caption(f"Concorrentes da categoria **{par['categoria']}** (CoinGecko). Compare só projetos com o mesmo modelo econômico.")
    ops = {c["id"]: f"{c['nome']} ({c['simbolo']})" for c in par["moedas"]}
    padrao = list(ops)[:3]
    esc = st.multiselect("Concorrentes", list(ops), default=padrao, format_func=lambda g: ops[g], key=f"cp_pares_{d['m']['id']}", max_selections=5)
    if not esc:
        return
    with st.spinner("Coletando os concorrentes..."):
        linhas = [linha_comparacao(d["m"]["id"])] + [linha_comparacao(g) for g in esc]
    ok = [l for l in linhas if not l.get("erro")]
    for l in linhas:
        if l.get("erro"):
            st.caption(f"⚠️ {l['nome']}: sem dados agora ({l['erro']}).")
    av = ca.compatibilidade({l["nome"]: l["princ"] for l in ok})
    for a in av:
        st.warning(a)
    cols = [("nome", "Projeto"), ("mcap", "Valor de mercado"), ("giro", "Giro (vol/mcap)"), ("var30", "30 dias"), ("var1a", "1 ano"),
            ("vol_anual", "Volatilidade"), ("dd_max", "Drawdown máx."), ("mc_fdv", "Mcap ÷ FDV"), ("tvl", "TVL"),
            ("mc_tvl", "Mcap ÷ TVL"), ("p_taxas", "Preço ÷ Taxas")]
    fm = {"mcap": "usd", "giro": "pct_f", "var30": "pct_s", "var1a": "pct_s", "vol_anual": "pct_f", "dd_max": "pct_s", "mc_fdv": "ratio",
          "tvl": "usd", "mc_tvl": "ratio", "p_taxas": "ratio"}
    tab = pd.DataFrame([{rot: (l["nome"] if k == "nome" else fmt(l[k] * 100 if k == "giro" and l[k] is not None else l[k], fm[k]))
                         for k, rot in cols} for l in ok])
    st.dataframe(tab, hide_index=True, width="stretch")
    st.markdown("#### Rankings dentro do grupo")
    crit = st.selectbox("Critério", [k for k in ca.CRITERIOS_RANKING if k != "nota"], format_func=lambda k: ca.CRITERIOS_RANKING[k][0], key=f"cp_crit_{d['m']['id']}")
    rk = ca.ranking(ok, crit)
    esc_v = 100 if crit == "giro" else 1
    st.dataframe(pd.DataFrame([{"#": r["posicao"] or "—", "Projeto": r["nome"],
                                "Valor": fmt(r["valor"] * esc_v if r["valor"] is not None else None, fm.get(crit, "pct_f"))} for r in rk]),
                 hide_index=True, width="stretch")
    st.caption("Quem não tem o dado fica no fim, sem posição. Múltiplos (Mcap ÷ TVL, Preço ÷ Taxas) só valem entre projetos com TVL/taxas medidos.")
    if atalho_comparar is not None:
        atalho_comparar([d["m"]["id"]] + esc)


def _aba_analise(d, rel, alertas):
    for s in rel["secoes"]:
        st.markdown(f"#### {s['titulo']}")
        for it in s["itens"]:
            st.markdown("- " + it)
    st.markdown("#### Monitoramento")
    if alertas:
        for al in alertas:
            st.markdown(f"- **{al['titulo']}** — {al['texto']} _(fonte: {al['fonte']}, {_data_br(al['data'])})_")
    else:
        st.caption("Nenhum alerta com dado verificável agora.")
    with st.expander("O que o monitoramento não cobre"):
        for l in ca.SEM_FONTE_MONITOR:
            st.markdown("- " + l)
    st.caption(rel["aviso"])


# =============================================================================== página
def _preparar(gid: str) -> dict:
    d = coletar(gid)
    d = dict(d)
    c = d["mercado"]["calc"]
    tk = ca.tokenomics(c, d["infl"], None)
    d["tk"] = tk
    eventos = st.session_state.get("cripto_desbloqueios", {}).get(gid, [])
    d["desb"] = ca.desbloqueios(eventos, c["circ"], c["preco"])
    h = ca.historico(d["ev"]["series"], (d["ev"].get("longo") or {}).get("preco"))
    d["hist_res"] = h
    d["oc"] = ca.onchain(d["onchain_in"])
    pares = pares_da_categoria(gid, tuple(d["m"].get("categorias_todas") or []), d["princ"])
    d["pares_lista"] = pares["moedas"]
    peers_val = []
    d["val"] = ca.valuation(d["princ"], c["mcap"], c["fdv"], d["tvl"], d["fees30"], d["rev30"], c["vol24"], peers_val)
    d["riscos"] = ca.avaliar_riscos({
        "classes": d["chaves"], "princ": d["princ"], "mcap": c["mcap"], "giro": c["giro"], "fdv_mc": c["fdv_mc"],
        "eh_stable": d["eh_stable"], "tipo_stable": d["tipo_stable"], "peg_desvio": d["peg"], "exploits": d["expl"],
        "auditorias": d["aud"], "plataforma": d["plataforma"], "ponte": d["ponte"], "gid": gid})
    vol = d["ev"]["series"].get("Volume diário (USD)")
    vol_media30 = float(vol.tail(31).head(30).mean()) if vol is not None and len(vol) >= 31 else None
    oferta = d["ev"]["series"].get("Oferta circulante (calculada)")
    tvl_s = d["ev"].get("tvl")
    rel = (d["github"] or {})
    d["alertas"] = ca.monitorar({
        "var24": c["var24"], "vol24": c["vol24"], "vol_media30": vol_media30,
        "oferta_var30": ca.variacao(oferta, 30) if oferta is not None and len(oferta) >= 60 else None,
        "tvl_var30": ca.variacao(tvl_s, 30) if tvl_s is not None and len(tvl_s) >= 30 else None,
        "eh_stable": d["eh_stable"], "peg_desvio": d["peg"], "exploits": d["expl"], "desbloqueios": d["desb"],
        "release": {"tag": rel.get("tag"), "dias": rel.get("dias"), "url": rel.get("release_url")} if rel.get("tag") else None,
        "data": d["mercado"]["data"] or date.today().isoformat()})
    d["relatorio"] = ca.relatorio({
        "nome": d["m"]["nome"], "simbolo": d["m"]["simbolo"], "classes": d["classes"], "mercado": c, "tokenomics": tk,
        "onchain": d["oc"], "valuation": d["val"], "riscos": d["riscos"], "historico": h,
        "pares": [p["nome"] for p in d["pares_lista"]], "nota": (d.get("fund") or {}).get("nota"), "alertas": d["alertas"],
        "fundamentos": ca.fundamentos(d["raw"], d["dev"], d["github"], d["proto_raw"], d["chaves"])})
    return d


def _adicionar_e_escolher(gid: str, nome: str):
    cripto._adicionar_cripto(gid, nome)
    st.session_state["cripto_av_gid"] = gid


def _resultados(res: list[dict], sel: list[str]):
    """Resultados da busca (texto com a cor do tema, legível no fundo escuro)."""
    for c in res:
        with st.container(border=True):
            a, b = st.columns([5, 1.6], vertical_alignment="center")
            rank = f"Ranking #{c['rank']}" if c.get("rank") else "Sem ranking"
            a.markdown(f"**{c['nome']} ({c['simbolo']})**  \n{rank}")
            b.button("Analisar", key=f"cripto_av_add_{c['id']}", on_click=_adicionar_e_escolher, args=(c["id"], c["nome"]),
                     width="stretch")


def pagina_cripto_avancada(atalho_comparar=None):
    st.markdown(tema.cabecalho("🪙", "Criptomoedas: análise avançada",
                               "Classificação, mercado, tokenomics, on-chain, segurança, valuation, histórico e comparação."),
                unsafe_allow_html=True)
    st.session_state.setdefault("cripto_ativos", [])
    st.session_state.setdefault("cripto_nomes", {})
    with st.form("form_cripto_av"):
        c1, c2 = st.columns([5, 1.6], vertical_alignment="center")
        c1.text_input("Buscar moeda", key="cripto_av_q", label_visibility="collapsed",
                      placeholder="Nome ou símbolo: Bitcoin, ETH, Solana, Uniswap, USDT…")
        c2.form_submit_button("Buscar", type="primary", width="stretch")
    termo = (st.session_state.get("cripto_av_q") or "").strip()
    sel = st.session_state["cripto_ativos"]
    if termo and len(termo) >= 2:
        try:
            achadas = cripto.buscar_moedas(termo)
        except cripto.ErroAPI as e:
            achadas = None
            st.warning(f"Não consegui buscar agora ({e}). Tente de novo em instantes.")
        if achadas:
            _resultados(achadas, sel)
        elif achadas is not None:
            st.info("Não encontrei essa moeda. Confira o nome ou tente o símbolo.")
    nomes = {**{v: k for k, v in cripto.POPULARES.items()}, **st.session_state["cripto_nomes"]}
    opcoes = list(dict.fromkeys(sel + list(cripto.POPULARES.values())))
    gid = st.selectbox("Moeda em análise", opcoes, key="cripto_av_gid", index=None, placeholder="Escolha uma moeda",
                       format_func=lambda g: nomes.get(g) or g.replace("-", " ").title())
    if not gid:
        st.info("Busque ou escolha uma moeda para ver a análise.")
        return
    try:
        with st.spinner("Coletando dados da moeda..."):
            d = _preparar(gid)
    except cripto.ErroAPI as e:
        st.warning(f"A CoinGecko não respondeu para esta moeda ({e}). Tente novamente em instantes.")
        return
    abas = st.tabs(["Visão geral", "Mercado", "Fundamentos", "Tokenomics", "On-chain", "Segurança", "Valuation", "Histórico",
                    "Comparação", "Análise inteligente"])
    with abas[0]:
        _aba_visao(d, d["alertas"])
    with abas[1]:
        _aba_mercado(d)
    with abas[2]:
        _aba_fundamentos(d)
    with abas[3]:
        _aba_tokenomics(d, d["tk"], d["desb"])
    with abas[4]:
        _aba_onchain(d, d["oc"])
    with abas[5]:
        _aba_seguranca(d, d["riscos"])
    with abas[6]:
        _aba_valuation(d, d["val"])
    with abas[7]:
        _aba_historico(d, d["hist_res"])
    with abas[8]:
        _aba_comparacao(d, atalho_comparar)
    with abas[9]:
        _aba_analise(d, d["relatorio"], d["alertas"])


# =============================================================================== carteira
_PAR = re.compile(r"^([A-Z0-9]{2,10})[-/](USD|USDT|BRL|EUR)$")


def simbolo_cripto(ticker: str) -> str | None:
    """'BTC-USD' / 'eth/usdt' → 'BTC'. Outros códigos (ações, FIIs, ETFs) → None."""
    m = _PAR.match(str(ticker or "").strip().upper())
    return m.group(1) if m else None


@st.cache_data(ttl=3600, show_spinner=False)
def _gid_do_simbolo(simbolo: str):
    try:
        res = cripto.buscar_moedas(simbolo)
    except Exception:
        return None
    exatos = [r for r in res if str(r["simbolo"]).upper() == simbolo]
    exatos.sort(key=lambda r: r["rank"] or 10 ** 9)
    return exatos[0]["id"] if exatos else None


def painel_carteira(lotes: list):
    """Análise das criptomoedas da carteira (nada é negociado nem alterado)."""
    cripto_lotes = [(simbolo_cripto(l.get("ticker")), l) for l in lotes if isinstance(l, dict)]
    cripto_lotes = [(s, l) for s, l in cripto_lotes if s]
    if not cripto_lotes:
        st.caption("Nenhuma criptomoeda na carteira (use códigos como BTC-USD ou ETH-USD).")
        return
    pos, nao = [], []
    with st.spinner("Analisando as criptomoedas da carteira..."):
        for simb, l in cripto_lotes:
            gid = _gid_do_simbolo(simb)
            if not gid:
                nao.append(simb)
                continue
            try:
                m = cripto.analisar_moeda(gid)
                raw = cripto._gecko_coin_raw(gid)
            except Exception:
                nao.append(simb)
                continue
            classes = ca.classificar(gid, m.get("categorias_todas"))
            pos.append({"gid": gid, "simbolo": m["simbolo"] or simb, "qtd": l.get("qtd"), "preco": m.get("preco"),
                        "classes": [c["chave"] for c in classes], "princ": ca.principal(classes),
                        "rede": raw.get("asset_platform_id") or gid, "serie": ca.serie_de_pares(m.get("hist"))})
    r = ca.analisar_carteira(pos)
    if nao:
        st.caption("Não identifiquei na CoinGecko: " + ", ".join(sorted(set(nao))) + ".")
    for av in r["avisos"]:
        st.caption("⚠️ " + av)
    if not r["linhas"]:
        return
    st.metric("Valor da parte cripto (preços de hoje)", fmt(r["total_usd"], "usd"))
    st.dataframe(pd.DataFrame([{"Ativo": l["simbolo"], "Categoria": ca.CATEGORIAS[l["princ"]], "Rede": l["rede"], "Peso": fmt(l["peso"], "pct_f")}
                               for l in r["linhas"]]), hide_index=True, width="stretch")
    a, b = st.columns(2)
    a.metric("Exposição a stablecoins", fmt(r["stable_pct"], "pct_f"))
    b.metric("Concentração (HHI)", f"{r['hhi']:.2f}", help="De 0 a 1: perto de 1 = tudo em poucos ativos.")
    st.markdown("**Por categoria principal:** " + " · ".join(f"{ca.CATEGORIAS[k]} {fmt(v, 'pct_f')}"
                                                              for k, v in sorted(r["por_categoria"].items(), key=lambda x: -x[1])))
    st.markdown("**Por rede (moeda nativa + tokens que rodam nela):** " + " · ".join(
        f"{k} {fmt(v, 'pct_f')}" for k, v in sorted(r["redes"].items(), key=lambda x: -x[1])))
    if r["vol_anual"] is not None:
        a, b = st.columns(2)
        a.metric("Volatilidade anualizada", fmt(r["vol_anual"], "pct_f"))
        b.metric("Drawdown máximo (12m)", fmt(r["dd_max"], "pct_s"))
    for al in r["alertas"]:
        st.warning(al)
    st.caption("Informação educacional: o app não executa nem sugere operações.")
