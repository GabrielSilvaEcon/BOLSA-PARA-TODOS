"""Passo 15 — Central de notícias e eventos (tela e coleta). O motor está em noticias_eventos.py.

Coleta: RSS/JSON de fontes públicas (Google Notícias para veículos; Federal Reserve, SEC e IBGE como fontes oficiais), calendários oficiais
(Copom, FOMC, IBGE, BLS), resultados e expectativas do Banco Central (SGS e Boletim Focus) e altura de bloco do Bitcoin. Falha de uma fonte
vira aviso na aba Fontes; nunca vira notícia inventada. Cache em memória com validade curta para não repetir consultas; consultas em paralelo
e com limite. Texto externo é tratado como dado não confiável (nada é executado; texto que tenta dar ordens ao sistema é descartado).

Hooks (opcionais; sem eles a página funciona só com o que tem):
    ativos() -> [{"id","nome","classe","setor","subgrupo","peso"}]   carteira (peso em %) e favoritos (peso 0)
    rf_vencimentos() -> [{"id","nome","vencimento"}]                 renda fixa da carteira
"""
from __future__ import annotations

import html
import logging
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from urllib.parse import quote_plus

import pandas as pd
import streamlit as st

import intel as I
import intel_app as IA
import noticias_eventos as N
import noticias_foto as NF
import tema

log = logging.getLogger("noticias")
CH_REGRAS, CH_HIST, CH_EVENTOS, CH_LOG, CH_PREFS = "ne_regras", "ne_hist", "ne_eventos", "ne_log", "ne_prefs"
CH_LEITURA = "_ne_leitura"
UA = {"User-Agent": "BussolaB3/1.0 (educacional)"}
# Alguns órgãos (BLS, IBGE) recusam ou ignoram clientes sem cara de navegador: para eles o pedido leva um cabeçalho comum de navegador.
UA_NAVEGADOR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
                "Accept": "text/calendar,text/html,application/json,*/*;q=0.8", "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8"}
HOSTS_NAVEGADOR = ("bls.gov", "ibge.gov.br")
URL_GOOGLE = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
URL_FED = "https://www.federalreserve.gov/feeds/press_monetary.xml"
URL_FED_TODOS = "https://www.federalreserve.gov/feeds/press_all.xml"
URL_SEC = "https://www.sec.gov/news/pressreleases.rss"
URL_IBGE_NOT = "https://servicodados.ibge.gov.br/api/v3/noticias/?qtd=20"
URL_IBGE_CAL = "https://servicodados.ibge.gov.br/api/v3/calendario/"
URL_BLS = "https://www.bls.gov/schedule/news_release/bls.ics"
URL_SGS = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.{n}/dados"
_OLINDA = "https://olinda.bcb.gov.br/olinda/servico/Expectativas/versao/v1/odata/"
_Q = "?$top=120&$filter=Indicador%20eq%20'{ind}'%20and%20baseCalculo%20eq%200&$orderby=Data%20desc&$format=json&$select=Indicador,Data,{ref},Mediana,baseCalculo"
URL_FOCUS_IPCA = _OLINDA + "ExpectativaMercadoMensais" + _Q.format(ind="IPCA", ref="DataReferencia")      # o Olinda recusa espaço como "+": a consulta vai já codificada
URL_FOCUS_SELIC = _OLINDA + "ExpectativasMercadoSelic" + _Q.format(ind="Selic", ref="Reuniao")
URL_BLOCO = "https://mempool.space/api/blocks/tip/height"
MAX_ATIVOS_BUSCA = 10
TEMAS = [  # (consulta, rótulo do tema, classes, país padrão)
    ("Copom Selic juros Brasil", "Política monetária e juros", ["renda_fixa", "acao", "fii"], "Brasil"),
    ("inflação IPCA Brasil", "Inflação", ["renda_fixa", "acao", "fii"], "Brasil"),
    ("dólar câmbio real Brasil", "Câmbio", ["acao", "etf", "cripto"], "Brasil"),
    ("Federal Reserve juros economia americana", "Economia dos EUA", ["acao", "etf", "cripto", "renda_fixa"], "Estados Unidos"),
    ("economia global China Europa mercados", "Economia global", ["acao", "etf"], None),
    ("Ibovespa bolsa de valores ações empresas resultado", "Mercado de ações", ["acao"], "Brasil"),
    ("fundos imobiliários FIIs mercado imobiliário", "FIIs e mercado imobiliário", ["fii"], "Brasil"),
    ("bitcoin ethereum criptomoedas blockchain", "Criptomoedas e blockchain", ["cripto"], None),
    ("ETFs fundos de investimento gestoras", "ETFs e fundos", ["etf", "fundo"], "Brasil"),
    ("Tesouro Direto renda fixa CDB crédito privado", "Renda fixa", ["renda_fixa", "fundo"], "Brasil"),
    ("bancos setor financeiro Banco Central regulação", "Bancos e instituições financeiras", ["acao"], "Brasil"),
    ("petróleo commodities minério Vale Petrobras", "Commodities e setores", ["acao"], None),
    ("geopolítica guerra sanções mercados", "Geopolítica", ["acao", "etf", "cripto"], None),
]
ROT_CLASSE = {"acao": "Ações", "bdr": "BDRs", "fii": "FIIs", "etf": "ETFs", "cripto": "Criptomoedas", "fundo": "Fundos", "renda_fixa": "Renda fixa"}


def _ss():
    return st.session_state


def _agora() -> datetime:
    return IA._agora()


# =============================================================================== coleta (cache em memória, consultas em paralelo)
_CACHE: dict = {}
_LOCK = threading.Lock()
AUTO_MINUTOS = 30        # a página atualiza sozinha ao abrir e quando a leitura passa desse tempo


def _get(url: str, ttl: int = 900, params: dict | None = None, json_: bool = False, max_bytes: int = 3_000_000, timeout: int = 8):
    """(conteúdo|None, erro|None). Cache em memória por `ttl` segundos (também para falhas, por 60 s, para não insistir numa fonte fora do ar)."""
    chave = (url, tuple(sorted((params or {}).items())), json_)
    with _LOCK:
        c = _CACHE.get(chave)
    agora = time.time()
    if c and agora - c["t"] < c["ttl"]:
        return c["v"], c["e"]
    v, e = None, None
    try:
        import requests
        cab = UA_NAVEGADOR if any(h in url for h in HOSTS_NAVEGADOR) else UA
        tent = 2 if any(h in url for h in ("ibge.gov.br",)) else 1          # o IBGE às vezes demora para atender: uma segunda tentativa resolve a maioria
        for k in range(tent):
            try:
                r = requests.get(url, params=params, headers=cab, timeout=(max(timeout, 12) if tent > 1 else min(timeout, 6), timeout + 8 if tent > 1 else timeout))
                break
            except Exception:
                if k == tent - 1:
                    raise
        if r.status_code != 200:
            e = f"HTTP {r.status_code}"
        elif len(r.content) > max_bytes:
            e = "resposta grande demais"
        else:
            v = r.json() if json_ else r.text
    except Exception as ex:
        e = ex.__class__.__name__
        log.warning("falha ao consultar %s: %s", url.split("?")[0], e)
    with _LOCK:
        _CACHE[chave] = {"t": agora, "v": v, "e": e, "ttl": ttl if e is None else 60}
        if len(_CACHE) > 400:
            for k in sorted(_CACHE, key=lambda k: _CACHE[k]["t"])[:100]:
                _CACHE.pop(k, None)
    return v, e


def _feed(url: str, nome: str, fonte_padrao: str | None = None, ttl: int = 900) -> dict:
    txt, e = _get(url, ttl, timeout=10 if "ibge.gov.br" in url else 8)
    itens = N.parse_feed(txt, fonte_padrao=fonte_padrao) if txt else []
    if txt and not itens and not e and not re.search(r"<(rss|feed|rdf:RDF)\b", txt[:2000]):
        e = "formato inesperado"           # feed válido e vazio (ex.: nenhuma notícia na semana) não é erro
    return {"fonte": nome, "itens": itens, "erro": e, "quando": _agora().isoformat(timespec="minutes"), "url": url}


def _google(consulta: str, nome: str) -> dict:
    return _feed(URL_GOOGLE.format(q=quote_plus(consulta + " when:7d")), nome)


def _nome_busca(a: dict) -> str:
    try:
        import recursos as rec
        curto = rec.nome_curto(a["id"])
        if curto and curto.upper() != a["id"].upper():
            return curto
    except Exception:
        pass
    return re.sub(r"\s*\(.*?\)\s*", " ", a.get("nome") or "").strip() or a["id"]


def coletar_noticias(ativos: list[dict]) -> tuple[list[dict], list[dict]]:
    """[(notícias brutas com origem/classes/país/ativos)], [status por fonte]. Até 13 temas + 10 ativos + 3 fontes oficiais, em paralelo."""
    tarefas = [("tema", t, lambda t=t: _google(t[0], f"Google Notícias — {t[1]}")) for t in TEMAS]
    for a in [x for x in ativos if x.get("classe") in ("acao", "bdr", "fii", "etf", "cripto")][:MAX_ATIVOS_BUSCA]:
        cons = f"{a['id']} {_nome_busca(a)}" if a.get("classe") != "cripto" else f"{_nome_busca(a)} criptomoeda"
        tarefas.append(("ativo", a, lambda c=cons, a=a: _google(c, f"Google Notícias — {a['id']}")))
    tarefas += [("oficial", ("Federal Reserve", ["acao", "etf", "cripto", "renda_fixa"], "Estados Unidos"), lambda: _fed()),
                ("oficial", ("SEC", ["cripto", "etf", "acao"], "Estados Unidos"), lambda: _feed(URL_SEC, "SEC (comunicados à imprensa)", "SEC")),
                ("oficial", ("IBGE", ["renda_fixa", "acao"], "Brasil"), lambda: _ibge_noticias())]
    with ThreadPoolExecutor(max_workers=6) as ex:
        resultados = list(ex.map(lambda t: t[2](), tarefas))
    brutas, status = [], []
    for (tipo, meta, _), r in zip(tarefas, resultados):
        status.append({"fonte": r["fonte"], "ok": r["erro"] is None, "n": len(r["itens"]), "erro": r["erro"], "quando": r["quando"], "url": r.get("url"), "oficial": tipo == "oficial"})
        for n in r["itens"]:
            if tipo == "tema":
                n.update({"origem": meta[1], "classes": list(meta[2]), "pais_padrao": meta[3]})
            elif tipo == "ativo":
                n.update({"origem": f"ativo:{meta['id']}", "classes": [meta["classe"]], "alvo": meta["id"], "pais_padrao": "Brasil" if meta["classe"] != "cripto" else None})
            else:
                n.update({"origem": meta[0], "classes": list(meta[1]), "pais_padrao": meta[2]})
            brutas.append(n)
    return brutas, status


def _fed() -> dict:
    """Comunicados de política monetária; se esse feed vier vazio, usa o feed geral de comunicados do Fed."""
    r = _feed(URL_FED, "Federal Reserve (comunicados de política monetária)", "Federal Reserve")
    if not r["itens"]:
        r2 = _feed(URL_FED_TODOS, "Federal Reserve (todos os comunicados)", "Federal Reserve")
        if r2["itens"] or r["erro"]:
            return r2
    return r


def _ibge_noticias() -> dict:
    dados, e = _get(URL_IBGE_NOT, 900, json_=True, timeout=10)
    itens = N.parse_ibge_noticias(dados) if dados else []
    if dados and not itens and not e:
        e = "formato inesperado"
    return {"fonte": "IBGE (notícias)", "itens": itens, "erro": e, "quando": _agora().isoformat(timespec="minutes"), "url": URL_IBGE_NOT}


def coletar_calendarios(agora: datetime) -> dict:
    """Calendários e indicadores oficiais. Cada fonte devolve (dados, erro); quem falhar fica de fora e aparece na aba Fontes."""
    st_ = []

    def reg(nome, url, ok, n, erro=None):
        st_.append({"fonte": nome, "ok": ok, "n": n, "erro": erro, "quando": agora.isoformat(timespec="minutes"), "url": url, "oficial": True})

    ini, fim = agora - timedelta(days=15), agora + timedelta(days=75)
    jobs = {
        "ibge": lambda: _get(URL_IBGE_CAL, 3600, params={"de": ini.strftime("%m-%d-%Y"), "ate": fim.strftime("%m-%d-%Y"), "qtd": "200", "tipo": "1"}, json_=True, timeout=10),
        "bls": lambda: _get(URL_BLS, 6 * 3600),
        "focus_ipca": lambda: _get(URL_FOCUS_IPCA, 3600, json_=True),
        "focus_selic": lambda: _get(URL_FOCUS_SELIC, 3600, json_=True),
        "bloco": lambda: _get(URL_BLOCO, 600),
    }
    for k, (nome, (n_sgs, _r, _u, _m)) in enumerate(N.SERIES_BCB.items()):
        di = "01/01/2017" if nome == "Selic meta" else (agora - timedelta(days=800)).strftime("%d/%m/%Y")
        jobs[f"sgs:{nome}"] = lambda n_sgs=n_sgs, di=di: _get(URL_SGS.format(n=n_sgs), 3600, params={"formato": "json", "dataInicial": di, "dataFinal": agora.strftime("%d/%m/%Y")}, json_=True)
    with ThreadPoolExecutor(max_workers=6) as ex:
        res = dict(zip(jobs, ex.map(lambda f: f(), jobs.values())))
    out = {}
    d, e = res["ibge"]
    ev_ibge = N.parse_ibge_calendario(d, agora) if d else []
    reg("IBGE — calendário de divulgações", URL_IBGE_CAL, e is None and bool(ev_ibge), len(ev_ibge), e or (None if ev_ibge else "nenhuma divulgação relevante no formato esperado"))
    t, e = res["bls"]
    ev_bls = N.parse_ics_bls(t, agora) if t else []
    reg("BLS — calendário de divulgações (EUA)", URL_BLS, e is None and bool(ev_bls), len(ev_bls), e or (None if ev_bls else "formato inesperado"))
    resultados, historico = {}, {}
    for nome, (n_sgs, rot, un, mensal) in N.SERIES_BCB.items():
        d, e = res[f"sgs:{nome}"]
        serie = N.parse_sgs(d) if d else []
        u = N.ultimos_indicador(serie, mensal)
        if u:
            resultados[nome] = {**u, "unidade": un, "rotulo": rot, "serie": n_sgs}
        if nome == "Selic meta":
            historico[nome] = [r for i, r in enumerate(serie) if i == 0 or r["valor"] != serie[i - 1]["valor"] or i == len(serie) - 1]
        reg(f"Banco Central — SGS {n_sgs} ({rot})", URL_SGS.format(n=n_sgs), e is None and bool(u), len(serie), e or (None if u else "série vazia"))
    d, e = res["focus_ipca"]
    f_ipca = N.parse_focus(d, "IPCA") if d else []
    reg("Banco Central — Boletim Focus (IPCA)", URL_FOCUS_IPCA, e is None and bool(f_ipca), len(f_ipca), e or (None if f_ipca else "sem expectativas no formato esperado"))
    d, e = res["focus_selic"]
    f_selic = N.parse_focus(d, "Selic") if d else []
    reg("Banco Central — Boletim Focus (Selic)", URL_FOCUS_SELIC, e is None and bool(f_selic), len(f_selic), e or (None if f_selic else "sem expectativas no formato esperado"))
    t, e = res["bloco"]
    altura = int(t) if t and str(t).strip().isdigit() else None
    reg("mempool.space — altura do bloco do Bitcoin", URL_BLOCO, altura is not None, 1 if altura else 0, e or (None if altura else "formato inesperado"))
    eventos = N.enriquecer_eventos(N.unir_eventos(N.calendario_copom(), N.calendario_fomc(), ev_ibge, ev_bls), resultados, f_ipca, f_selic, agora)
    return {"eventos": eventos, "resultados": resultados, "historico": historico, "altura_bloco": altura, "status": st_}


def _var5d(df) -> float | None:
    try:
        c = df["Close"].dropna()
        return float((c.iloc[-1] / c.iloc[-6] - 1) * 100) if len(c) >= 6 else None
    except Exception:
        return None


def coletar_corporativo(ativos: list[dict], hooks: dict, agora: datetime) -> tuple[list[dict], list[dict], dict]:
    """Proventos e desdobramentos registrados no Yahoo (até 10 ativos), vencimentos da renda fixa da carteira e eventos informados pela pessoa."""
    import analise_tecnica_app as ATA
    alvo = [a for a in ativos if a.get("classe") in ("acao", "bdr", "fii", "etf")][:MAX_ATIVOS_BUSCA]
    eventos, status, var5 = [], [], {}

    def um(a):
        try:
            b = ATA._baixar(ATA._simbolo_yahoo(a["id"], a["classe"]), "2y", "1d")
        except Exception as ex:
            return a, None, ex.__class__.__name__
        return a, b, b.get("erro")
    with ThreadPoolExecutor(max_workers=4) as ex:
        for a, b, erro in ex.map(um, alvo):
            if b and not erro:
                eventos += N.eventos_proventos(a["id"], b.get("div"), b.get("splits"), agora)
                v = _var5d(b.get("df"))
                if v is not None:
                    var5[a["id"]] = v
            status.append({"fonte": f"Yahoo Finance — proventos de {a['id']}", "ok": not erro, "n": len(b.get("div", [])) if b and not erro and b.get("div") is not None else 0, "erro": erro, "quando": agora.isoformat(timespec="minutes"), "url": None, "oficial": False})
    try:
        eventos += N.eventos_vencimento_rf((hooks.get("rf_vencimentos") or (lambda: []))() or [])
    except Exception:
        pass
    for m in _ss().get(CH_EVENTOS) or []:
        eventos.append(m)
    return sorted(eventos, key=lambda e: e["data"]), status, var5


# =============================================================================== leitura completa
def _classes_noticia(n: dict, ativos: list[dict]) -> list[str]:
    cl = set(n.get("classes") or [])
    for a in ativos:
        if a["id"] in n.get("ativos", []):
            cl.add("acao" if a.get("classe") == "bdr" else a.get("classe"))
    return sorted(c for c in cl if c)


def atualizar(hooks: dict | None = None) -> dict:
    hooks = hooks or {}
    agora = _agora()
    ativos = []
    try:
        ativos = list((hooks.get("ativos") or (lambda: []))() or [])
    except Exception as e:
        log.warning("hook ativos falhou: %s", e.__class__.__name__)
    t_ini = time.time()
    with ThreadPoolExecutor(max_workers=2) as _ex:           # notícias e calendários andam em paralelo com o corporativo (que usa o session_state e fica na thread principal)
        f_noticias = _ex.submit(coletar_noticias, ativos)
        f_cal = _ex.submit(coletar_calendarios, agora)
        corp, status_c, var5 = coletar_corporativo(ativos, hooks, agora)
        brutas, status_n = f_noticias.result()
        cal = f_cal.result()
    corp = [{**e, "status": N._status_evento(e["data"], agora, False)} for e in corp]
    ocultas = N.ocultas_suspeitas(brutas)
    noticias = []
    for n in N.processar(brutas, "", agora):
        d = next((b for b in brutas if b["titulo"] == n["titulo"] and b.get("fonte") == n["fonte"]), {})
        texto = f"{n['titulo']} {n['resumo']}"
        n["ativos"] = [a["id"] for a in N.mencoes(texto, ativos)] or []
        if d.get("alvo") and d["alvo"] not in n["ativos"] and I._norm(d["alvo"]) in I._norm(texto):
            n["ativos"].append(d["alvo"])
        n["origem"], n["classes"] = d.get("origem", "n/d"), d.get("classes", [])
        n["classes"] = _classes_noticia(n, ativos)
        n["paises"] = N.paises_do_texto(texto, d.get("pais_padrao"))
        n["setores"] = N.setores_do_texto(texto)
        noticias.append(n)
    grupos = N.agrupar_acontecimentos(noticias)
    for g in grupos:
        for k in ("classes", "paises", "setores"):
            g[k] = sorted({x for m in g["membros"] for x in m.get(k, [])})
    halving = N.proximo_halving(cal["altura_bloco"], agora)
    manuais_cripto = [e for e in (_ss().get(CH_EVENTOS) or []) if e.get("escopo") == "cripto"]
    ev_cripto = N.eventos_cripto(halving, hooks.get("cripto_desbloqueios") or _ss().get("cripto_desbloqueios"), manuais_cripto, [g for g in grupos if "cripto" in g["classes"]], agora)
    ev_cripto = [{**e, "status": N._status_evento(e["data"], agora, False)} for e in ev_cripto]
    eventos = cal["eventos"]
    impactos = []
    for g in grupos[:60]:
        impactos += N.analisar_impacto(g, ativos)
    for e in eventos:
        if e["status"] in ("hoje", "futuro") and (date.fromisoformat(e["data"]) - agora.date()).days <= 14 or (e["status"] == "divulgado" and (agora.date() - date.fromisoformat(e["data"])).days <= 2):
            impactos += N.impactos_de_evento(e, ativos)
    sentimento = {"_geral": N.sentimento_agregado(noticias, agora)}
    ids_pos = {a["id"] for a in ativos if (a.get("peso") or 0) > 0}
    sub_c = [n for n in noticias if set(n["ativos"]) & ids_pos]
    if sub_c:
        sentimento["_carteira"] = N.sentimento_agregado(sub_c, agora)
    for a in ativos:
        sub = [n for n in noticias if a["id"] in n["ativos"]]
        if sub:
            sentimento[a["id"]] = N.sentimento_agregado(sub, agora)
    div_preco = []
    for k, v in var5.items():
        t = N.divergencia_preco(sentimento.get(k), v)
        if t:
            div_preco.append({"ativo": k, "texto": t})
    pos = [a for a in ativos if (a.get("peso") or 0) > 0]
    cart = N.resumo_carteira(pos, grupos, eventos + corp + ev_cripto, impactos, sentimento, agora) if pos else None
    res = {"quando": agora.isoformat(timespec="seconds"), "ativos": ativos, "noticias": noticias, "grupos": grupos, "eventos": eventos, "corporativo": corp, "cripto": ev_cripto,
           "impactos": impactos, "sentimento": sentimento, "carteira": cart, "resultados": cal["resultados"], "historico": cal["historico"], "halving": halving,
           "duracao": round(time.time() - t_ini, 1),
           "fontes": status_n + cal["status"] + status_c, "ocultas": ocultas, "divergencias_preco": div_preco, "var5d": var5}
    log_ = list(_ss().get(CH_LOG) or [])
    log_.append({"quando": res["quando"], "n_noticias": len(noticias), "n_grupos": len(grupos), "fontes_ok": sum(1 for f in res["fontes"] if f["ok"]), "fontes_erro": sum(1 for f in res["fontes"] if not f["ok"]),
                 "erros": [f"{f['fonte']}: {f['erro']}" for f in res["fontes"] if not f["ok"]][:8]})
    _ss()[CH_LOG] = log_[-30:]
    _ss()[CH_LEITURA] = res
    _alertas(res, agora)
    return res


def estado_alertas(res: dict) -> dict:
    return {"noticias": res["grupos"], "eventos": res["eventos"] + res["corporativo"] + res["cripto"], "sentimento": res["sentimento"],
            "acompanhados": [a["id"] for a in res["ativos"]]}


def _alertas(res: dict, agora: datetime):
    regras = [r for r in (_ss().get(CH_REGRAS) or []) if r.get("ativa", True)]
    res["alertas"], res["suprimidos"] = [], 0
    if not regras:
        return
    import analise_tecnica as T
    disp = N.avaliar_alertas_ne(regras, estado_alertas(res), agora)
    novos, hist, supr = T.filtrar_por_frequencia(disp, _ss().get(CH_HIST) or [], regras, agora)
    _ss()[CH_HIST] = hist
    res["alertas"], res["suprimidos"] = novos, supr
    try:                                  # Passo 23: guarda na Central de notificações (nunca atrapalha esta página)
        import notif_app
        notif_app.registrar_disparos(novos, "noticias")
    except Exception:
        pass


def leitura() -> dict | None:
    return _ss().get(CH_LEITURA)


def contexto_ia(res: dict) -> dict:
    return {"noticias": res["grupos"], "eventos": res["eventos"] + res["corporativo"] + res["cripto"], "impactos": res["impactos"], "sentimento": res["sentimento"], "carteira": res["carteira"],
            "historico": res["historico"], "ativos": res["ativos"], "gerado_em": res["quando"], "fontes_status": res["fontes"]}


# =============================================================================== filtros (puros, testáveis)
def filtrar(grupos: list[dict], classe: str | None = None, ativo: str | None = None, setor: str | None = None, pais: str | None = None, fonte: str | None = None,
            dias: int | None = None, rel_min: int = 0, texto: str | None = None, agora: datetime | None = None) -> list[dict]:
    """Filtros do §1: classe, ativo, empresa/texto, setor, país, fonte, data e relevância. Campo vazio = sem filtro."""
    agora = agora or _agora()
    q = I._norm(texto or "").strip()
    out = []
    for g in grupos:
        if classe and classe not in g.get("classes", []):
            continue
        if ativo and ativo.upper() not in [a.upper() for a in g.get("ativos", [])]:
            continue
        if setor and setor not in g.get("setores", []):
            continue
        if pais and pais not in g.get("paises", []):
            continue
        if fonte and fonte not in g.get("fontes", []):
            continue
        if g.get("relevancia", 0) < rel_min:
            continue
        if dias is not None:
            try:
                d = (agora - pd.Timestamp(g.get("ultima_publicacao") or g.get("publicada_em")).to_pydatetime().replace(tzinfo=None)).total_seconds() / 86400
            except Exception:
                continue
            if d > dias:
                continue
        if q and q not in I._norm(g["titulo"] + " " + " ".join(m.get("resumo", "") for m in g.get("membros", []))):
            continue
        out.append(g)
    return out


def ativos_do_evento(e: dict, impactos: list[dict], limite: int = 8) -> list[str]:
    ids = []
    for im in impactos:
        if im.get("origem") == "evento" and im.get("titulo") == e.get("evento"):
            ids += [a["id"] for a in im["ativos"]]
    if e.get("ativo"):
        ids.insert(0, e["ativo"])
    return list(dict.fromkeys(ids))[:limite]


def _fmt_valor(v, un) -> str:
    if v is None:
        return "—"
    return f"{v:g}{(' ' + un) if un else ''}"


# =============================================================================== telas
_SENT = {"positivo": "🟢 positivo", "negativo": "🔴 negativo", "neutro": "⚪ neutro", "incerto": "🟡 incerto"}
_NIVEL = {"alta": "🔴 alta", "media": "🟠 média", "baixa": "🟡 baixa"}


def _link(txt: str, url: str | None) -> str:
    return f"[{I.escapar_md(txt)}]({url})" if url and I.url_segura(url) else I.escapar_md(txt)


_TOM = {"positivo": ("good", "▲ Positivo"), "negativo": ("bad", "▼ Negativo"), "neutro": ("na", "● Neutro"), "incerto": ("fair", "? Incerto")}
_CONF = {"oficial": ("info", "Fonte oficial"), "veiculo": ("good", "Veículo reconhecido"), "nao_verificada": ("na", "Não verificada")}

CSS_NOTICIAS = """
<style>
.nw-bar{display:flex;height:12px;border-radius:999px;overflow:hidden;background:rgba(189,181,230,.15);margin:6px 0 4px}
.nw-bar i{display:block;height:100%}
.nw-leg{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.78rem;color:#D3CCF2;margin-bottom:10px}
.nw-leg b{display:inline-block;width:9px;height:9px;border-radius:50%;margin-right:5px}
.nw{position:relative;overflow:hidden;border-radius:16px;padding:16px 18px 14px 22px;margin:0 0 10px;border:1px solid var(--c-line,rgba(189,181,230,.25));
    background:linear-gradient(180deg,var(--c-bg,rgba(189,181,230,.08)),rgba(27,20,66,.35));box-shadow:0 8px 22px rgba(0,0,0,.22);transition:transform .15s ease,box-shadow .15s ease}
.nw:hover{transform:translateY(-2px);box-shadow:0 12px 28px rgba(0,0,0,.32)}
.nw::before{content:"";position:absolute;left:0;top:0;bottom:0;width:6px;background:var(--c,#BDB5E6)}
.nw.good{--c:#3DDC97;--c-bg:rgba(61,220,151,.10);--c-line:rgba(61,220,151,.30)}
.nw.bad{--c:#FF6B6B;--c-bg:rgba(255,107,107,.10);--c-line:rgba(255,107,107,.30)}
.nw.fair{--c:#F2B84B;--c-bg:rgba(242,184,75,.10);--c-line:rgba(242,184,75,.30)}
.nw.na{--c:#BDB5E6;--c-bg:rgba(189,181,230,.07);--c-line:rgba(189,181,230,.24)}
.nw.hero{padding:22px 24px 18px 28px;background:linear-gradient(135deg,var(--c-bg,rgba(142,162,255,.12)),rgba(13,53,70,.55))}
.nw.hero .nw-t{font-size:clamp(1.25rem,1rem + 1.2vw,1.7rem)}
.nw-img{margin:-16px -18px 12px -22px;height:150px;overflow:hidden;background:rgba(189,181,230,.12)}
.nw-img.off{display:none}
.nw-img img{width:100%;height:100%;object-fit:cover;display:block}
.nw.hero .nw-img{margin:-22px -24px 14px -28px;height:230px}
.nw-top{display:flex;flex-wrap:wrap;align-items:center;gap:6px 8px;margin-bottom:8px}
.nw-k{font-family:var(--mono,ui-monospace,monospace);font-size:.66rem;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:#D3CCF2}
.nw-t{display:block;font-weight:700;font-size:1.05rem;line-height:1.3;color:#FFFFFF!important;text-decoration:none!important;
      display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}
a.nw-t:hover{text-decoration:underline!important}
.nw-m{display:flex;flex-wrap:wrap;align-items:center;gap:4px 12px;margin-top:9px;font-size:.8rem;color:#D3CCF2}
.nw-dot{display:inline-block;width:8px;height:8px;border-radius:50%;margin-right:5px;vertical-align:baseline}
.nw-chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}
.nw-c{display:inline-block;padding:2px 10px;border-radius:999px;font-size:.72rem;font-weight:600;border:1px solid rgba(189,181,230,.3);color:#FFFFFF;background:rgba(189,181,230,.10)}
.nw-c.good{color:#3DDC97;border-color:rgba(61,220,151,.45);background:rgba(61,220,151,.12)}
.nw-c.bad{color:#FF6B6B;border-color:rgba(255,107,107,.45);background:rgba(255,107,107,.12)}
.nw-c.fair{color:#F2B84B;border-color:rgba(242,184,75,.45);background:rgba(242,184,75,.12)}
.nw-c.info{color:#8EA2FF;border-color:rgba(142,162,255,.45);background:rgba(142,162,255,.12)}
.nw-c.tk{font-family:var(--mono,ui-monospace,monospace);letter-spacing:.03em}
.nw-u{color:#FF6B6B;font-weight:800;font-size:.7rem;letter-spacing:.08em;animation:nwp 1.6s ease-in-out infinite}
@keyframes nwp{50%{opacity:.45}}
.nw-r{display:inline-flex;align-items:center;gap:6px}
.nw-r i{display:inline-block;width:46px;height:5px;border-radius:99px;background:rgba(189,181,230,.25);overflow:hidden;position:relative}
.nw-r i::after{content:"";position:absolute;left:0;top:0;bottom:0;width:var(--w,50%);background:var(--c,#BDB5E6);border-radius:99px}
.nw-w{margin-top:9px;font-size:.78rem;color:#F2B84B;border-left:3px solid #F2B84B;padding:2px 0 2px 9px}
@media (max-width:640px){.nw{padding:14px 14px 12px 18px}.nw-t{font-size:1rem}}
.nw .nw-m,.nw .nw-m span,.nw .nw-k,.nw-leg,.nw-leg span{color:#D3CCF2!important}
.nw .nw-r.good{color:#3DDC97!important}.nw .nw-r.bad{color:#FF6B6B!important}.nw .nw-r.fair{color:#F2B84B!important}.nw .nw-r.na{color:#D3CCF2!important}
.nw .nw-m b,.nw-leg b{color:inherit}
</style>
"""


def idade_txt(iso: str | None, agora: datetime | None = None) -> str:
    """'há 25 min', 'há 3 h', 'há 2 dias' (ou data n/d). Só aparência: a data exata continua no texto da fonte."""
    try:
        h = ((agora or _agora()) - pd.Timestamp(iso).to_pydatetime().replace(tzinfo=None)).total_seconds() / 3600
    except Exception:
        return "data n/d"
    if h != h:
        return "data n/d"
    if h < 0:
        return "agora"
    if h < 1:
        return f"há {max(1, int(h * 60))} min"
    if h < 24:
        return f"há {int(h)} h"
    return f"há {int(h // 24)} dia(s)"


def _e(t) -> str:
    return html.escape(str(t if t is not None else ""), quote=True)


def card_html(g: dict, agora: datetime | None = None, destaque: bool = False) -> str:
    """Cartão visual de um acontecimento. TODO texto externo passa por html.escape; o link só entra se for http(s) seguro."""
    cor, tom_rot = _TOM.get(g.get("sentimento_grupo") or g.get("sentimento"), ("na", "● Neutro"))
    conf_cls, conf_rot = _CONF.get(g.get("melhor_fonte"), ("na", "Não verificada"))
    url = I.url_segura(g.get("url"))
    titulo = _e(g["titulo"])
    tit = (f'<a class="nw-t" href="{_e(url)}" target="_blank" rel="noopener noreferrer nofollow">{titulo}</a>' if url else f'<span class="nw-t">{titulo}</span>')
    tema_ = (g.get("origem") or "").split(":")[0]
    topo = "".join([f'<span class="nw-c {cor}">{tom_rot}</span>', '<span class="nw-u">● URGENTE</span>' if g.get("urgente") else "",
                    f'<span class="nw-k">{_e(tema_)}</span>' if tema_ and not tema_.startswith("ativo") else ""])
    fontes = _e(g["fonte"]) + (f' <b>+{g["n_fontes"] - 1}</b>' if g.get("n_fontes", 1) > 1 else "")
    cores = {"info": "#8EA2FF", "good": "#3DDC97", "na": "#BDB5E6"}
    meta = (f'<span><span class="nw-dot" style="background:{cores.get(conf_cls, "#BDB5E6")}"></span>{fontes}</span>'
            f'<span>{_e(idade_txt(g.get("ultima_publicacao") or g.get("publicada_em"), agora))}</span>'
            f'<span class="nw-r {cor}" style="--w:{int(g.get("relevancia", 0))}%" title="Relevância {int(g.get("relevancia", 0))} de 100">Relevância<i></i>{int(g.get("relevancia", 0))}</span>')
    chips = [f'<span class="nw-c {conf_cls}">{_e(conf_rot)}</span>']
    if not str(g.get("status", "")).startswith("reportado"):                       # "reportado por veículo" já está dito pelo selo de cima
        chips.append(f'<span class="nw-c {"fair" if g.get("especulativo") else "info"}">{_e(g["status"])}</span>')
    chips += [f'<span class="nw-c tk">{_e(a)}</span>' for a in (g.get("ativos") or [])[:6]]
    chips += [f'<span class="nw-c fair">{_e(t)}</span>' for t in (g.get("importantes") or [])[:3]]
    avisos = ""
    if g.get("contraditoria"):
        avisos += '<div class="nw-w">As fontes divergem no tom (há notícias positivas e negativas sobre o mesmo fato). Compare antes de concluir.</div>'
    if g.get("numeros_divergentes"):
        avisos += '<div class="nw-w">Os números citados diferem entre as fontes. Confira na fonte original.</div>'
    img = N.imagem_segura(g.get("imagem"))
    foto = (f'<div class="nw-img"><img src="{_e(img)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer" '
            f'onerror="this.parentNode.classList.add(\'off\');this.remove()"></div>' if img else "")
    return (f'<div class="nw {cor}{" hero" if destaque else ""}{" com-foto" if img else ""}">{foto}<div class="nw-top">{topo}</div>{tit}'
            f'<div class="nw-m">{meta}</div><div class="nw-chips">{"".join(chips)}</div>{avisos}</div>')


def barra_sentimento_html(s: dict | None) -> str:
    """Barra empilhada com a proporção de cada tom nos últimos 3 dias (cobertura, não preço)."""
    r = (s or {}).get("recente") or {}
    tot = r.get("total") or 0
    if not tot:
        return ""
    cores = [("positivo", "#3DDC97", "Positivas"), ("neutro", "#BDB5E6", "Neutras"), ("incerto", "#F2B84B", "Incertas"), ("negativo", "#FF6B6B", "Negativas")]
    barra = "".join(f'<i style="width:{r[k] / tot * 100:.1f}%;background:{c}"></i>' for k, c, _ in cores if r.get(k))
    leg = "".join(f'<span><b style="background:{c}"></b>{n} {r.get(k, 0)}</span>' for k, c, n in cores)
    return f'<div class="nw-bar">{barra}</div><div class="nw-leg">{leg}</div>'


def _cartao_grupo(g: dict, chave: str, destaque: bool = False):
    NF.foto_do_grupo(g)                                 # foto já achada para este grupo (só memória, sem rede)
    st.markdown(card_html(g, _agora(), destaque), unsafe_allow_html=True)
    if g["n_noticias"] > 1:
        with st.expander(f"Ver as {g['n_noticias']} publicações agrupadas", icon=":material/layers:"):
            for m in g["membros"]:
                st.markdown(f"- {_link(m['titulo'], m.get('url'))} — {I.escapar_md(m['fonte'])} ({ROT(m['fonte_nivel'])}; {(m.get('publicada_em') or 'data n/d')[:16].replace('T', ' ')})")


def _grade(grupos: list[dict], prefixo: str):
    """Cartões em 2 colunas (empilham sozinhas no celular)."""
    NF.pre_carregar(grupos, tempo=6.0)                  # busca as fotos que faltam, em paralelo e com limite de tempo
    for k in range(0, len(grupos), 2):
        for col, (i, x) in zip(st.columns(2), list(enumerate(grupos))[k:k + 2]):
            with col:
                _cartao_grupo(x, f"{prefixo}{i}")


def ROT(n):
    return N.ROTULO_NIVEL.get(n, n)


def _filtros(res: dict) -> dict:
    ativos = sorted({a for g in res["grupos"] for a in g.get("ativos", [])})
    setores = sorted({s for g in res["grupos"] for s in g.get("setores", [])})
    paises = sorted({p for g in res["grupos"] for p in g.get("paises", [])})
    fontes = sorted({f for g in res["grupos"] for f in g.get("fontes", [])})
    with st.expander("Filtros", icon=":material/filter_alt:"):
        c1, c2, c3 = st.columns(3)
        classe = c1.selectbox("Classe de ativo", [""] + list(ROT_CLASSE), key="ne_f_classe", format_func=lambda x: ROT_CLASSE.get(x, "Todas"))
        ativo = c2.selectbox("Ativo", [""] + ativos, key="ne_f_ativo", format_func=lambda x: x or "Todos")
        texto = c3.text_input("Empresa ou palavra", key="ne_f_texto", max_chars=60, **_opt("ne_f_texto", "value", ""))
        c4, c5, c6 = st.columns(3)
        setor = c4.selectbox("Setor", [""] + setores, key="ne_f_setor", format_func=lambda x: x or "Todos")
        pais = c5.selectbox("País", [""] + paises, key="ne_f_pais", format_func=lambda x: x or "Todos")
        fonte = c6.selectbox("Fonte", [""] + fontes, key="ne_f_fonte", format_func=lambda x: x or "Todas")
        c7, c8 = st.columns(2)
        dias = c7.selectbox("Data", [1, 2, 3, 7], key="ne_f_dias", format_func=lambda d: f"últimos {d} dia(s)", **_opt("ne_f_dias", "index", 3))
        st.session_state.setdefault("ne_f_rel", 0)
        rel = c8.slider("Relevância mínima", 0, 100, key="ne_f_rel")
    return {"classe": classe or None, "ativo": ativo or None, "texto": texto, "setor": setor or None, "pais": pais or None, "fonte": fonte or None, "dias": dias, "rel_min": rel}


def _aba_principais(res, f):
    st.markdown(CSS_NOTICIAS, unsafe_allow_html=True)
    g = [x for x in filtrar(res["grupos"], **f) if not x.get("desatualizada")]
    urg = sum(1 for x in g if x.get("urgente"))
    ok = sum(1 for x in res["fontes"] if x["ok"])
    IA._cartoes([("Acontecimentos", str(len(g)), "info"), ("Urgentes", str(urg), "bad" if urg else "na"),
                 ("Fontes no ar", f"{ok}/{len(res['fontes'])}", "good" if ok == len(res["fontes"]) else "fair"), ("Atualizado", idade_txt(res["quando"]), "na")], 4)
    st.markdown("**Clima das notícias (últimos 3 dias)**")
    st.markdown(barra_sentimento_html(res["sentimento"].get("_geral")), unsafe_allow_html=True)
    st.caption("Mostra a cobertura, não o preço: muitas notícias positivas não garantem valorização.")
    top = sorted(g, key=lambda x: (-x["relevancia"], x.get("ultima_publicacao") or ""))[:13]
    if not top:
        st.info("Nenhuma notícia com esses filtros nas fontes consultadas. Veja a aba Fontes para saber se alguma fonte falhou.")
        return
    with st.spinner("Buscando as fotos das matérias..."):
        NF.pre_carregar(top, tempo=8.0)
    st.markdown("#### Em destaque")
    _cartao_grupo(top[0], "h", destaque=True)
    rep = [x for x in N.grande_repercussao(g) if x["id"] != top[0]["id"]][:2]
    if rep:
        st.markdown("#### Grande repercussão")
        st.caption("Cobertas por 4 ou mais fontes diferentes. Repercussão não é sinônimo de impacto no preço.")
        _grade(rep, "r")
    ids = {top[0]["id"]} | {x["id"] for x in rep}
    resto = [x for x in top if x["id"] not in ids]
    if resto:
        st.markdown("#### Também relevantes")
        _grade(resto, "p")


def _aba_ultimas(res, f):
    st.markdown(CSS_NOTICIAS, unsafe_allow_html=True)
    g = sorted(filtrar(res["grupos"], **f), key=lambda x: x.get("ultima_publicacao") or "", reverse=True)
    st.caption(f"{len(g)} acontecimento(s) · mais recentes primeiro. Notícias com mais de 7 dias aparecem marcadas como desatualizadas.")
    _grade([{**x, "status": ("🕰️ desatualizada · " + x["status"]) if x.get("desatualizada") else x["status"]} for x in g[:60]], "u")
    if res.get("ocultas"):
        st.caption(f"{res['ocultas']} notícia(s) com texto de aparência suspeita (tentando dar ordens ao sistema) foram ocultadas.")


def _tabela_eventos(eventos: list[dict], impactos: list[dict], com_valores: bool):
    if not eventos:
        st.caption("Nada nesta seção.")
        return
    linhas = []
    for e in eventos:
        un = e.get("unidade")
        l = {"Data": e["data"], "Hora (Brasília)": e.get("hora") or "—", "País": e["pais"], "Evento": e["evento"], "Relevância": e["relevancia"]}
        if com_valores:
            l.update({"Anterior": _fmt_valor(e.get("anterior"), un), "Esperado (mercado)": _fmt_valor(e.get("esperado"), un), "Divulgado": _fmt_valor(e.get("divulgado"), un)})
        l.update({"Ativos que podem ser afetados": ", ".join(ativos_do_evento(e, impactos)) or "—", "Fonte": e["fonte"]})
        linhas.append(l)
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    obs = [e for e in eventos if e.get("observacao") or e.get("referencia")]
    if obs:
        with st.expander("Detalhes e fontes dos eventos", icon=":material/info:"):
            for e in obs[:40]:
                st.markdown(f"- **{I.escapar_md(e['evento'])}** ({e['data']}): {I.escapar_md((e.get('referencia') or '') + ' ' + (e.get('observacao') or ''))} {_link('Fonte', e.get('url'))}")


def _aba_economico(res):
    ev = res["eventos"]
    c1, c2 = st.columns(2)
    pais = c1.selectbox("País", [""] + sorted({e["pais"] for e in ev}), key="ne_e_pais", format_func=lambda x: x or "Todos")
    rel = c2.selectbox("Relevância", ["", "alta", "media"], key="ne_e_rel", format_func=lambda x: {"": "Todas", "alta": "só alta", "media": "média ou alta"}[x])
    ev = [e for e in ev if (not pais or e["pais"] == pais) and (not rel or (e["relevancia"] == "alta" or (rel == "media" and e["relevancia"] == "media")))]
    st.markdown("#### 🔜 Eventos futuros (ainda não divulgados)")
    st.caption("“Anterior” é o último valor divulgado; “Esperado” é a mediana do Boletim Focus quando existe. Campo “—” = fonte não entregou o dado.")
    fut = [e for e in ev if e["status"] in ("hoje", "futuro")]
    limite = (_agora().date() + timedelta(days=90)).isoformat()
    _tabela_eventos([e for e in fut if e["data"] <= limite], res["impactos"], True)
    longe = [e for e in fut if e["data"] > limite]
    if longe:
        with st.expander(f"Datas mais distantes ({len(longe)}, além de 90 dias)", icon=":material/event_upcoming:"):
            _tabela_eventos(longe, res["impactos"], True)
    st.markdown("#### ✅ Já divulgados")
    _tabela_eventos(sorted([e for e in ev if e["status"] == "divulgado"], key=lambda e: e["data"], reverse=True)[:40], res["impactos"], True)
    if res.get("resultados"):
        with st.expander("Últimos valores oficiais lidos (Banco Central)", icon=":material/monitoring:"):
            for nome, r in res["resultados"].items():
                st.markdown(f"- **{nome}**: {r['valor']:g} {r.get('unidade') or ''} (ref. {r['ref']}) — SGS {r['serie']}")
    st.caption("Datas de Copom e FOMC vêm de calendários oficiais conferidos em " + N.CONFERIDO_EM + ". Calendário do IBGE e do BLS são lidos ao vivo; se uma fonte falhar, o evento some em vez de ser estimado.")


def _aba_corporativo(res):
    ativos = res["ativos"]
    if not ativos:
        st.info("Adicione ativos à carteira ou aos favoritos para ver seus eventos.")
    ev = res["corporativo"]
    ids = sorted({e.get("ativo") for e in ev if e.get("ativo")})
    a = st.selectbox("Ativo", [""] + ids, key="ne_c_ativo", format_func=lambda x: x or "Todos")
    ev = [e for e in ev if not a or e.get("ativo") == a]
    st.markdown("#### 🔜 Próximos")
    _tabela_eventos([e for e in ev if e["status"] in ("hoje", "futuro")], res["impactos"], False)
    st.markdown("#### ✅ Passados (últimos 18 meses)")
    _tabela_eventos(sorted([e for e in ev if e["status"] == "divulgado"], key=lambda e: e["data"], reverse=True)[:40], res["impactos"], False)
    st.caption("Proventos e desdobramentos vêm do Yahoo Finance (podem ter atraso ou lacunas); vencimentos vêm da sua carteira de renda fixa. "
               "Datas de resultados, assembleias, ofertas e comunicados exigem a CVM/B3, que o app ainda não lê: registre-os abaixo, com o link da fonte.")
    with st.expander("Registrar um evento (com link da fonte)", icon=":material/add_circle:"):
        c1, c2 = st.columns(2)
        c1.selectbox("Tipo", list(N.TIPOS_CORPORATIVOS), key="ne_m_tipo", format_func=lambda t: N.TIPOS_CORPORATIVOS[t])
        c2.text_input("Ativo", key="ne_m_ativo", max_chars=24, **_opt("ne_m_ativo", "value", ""))
        c3, c4 = st.columns(2)
        c3.date_input("Data", key="ne_m_data", **_opt("ne_m_data", "value", date.today()))
        c4.text_input("Descrição curta", key="ne_m_desc", max_chars=160, **_opt("ne_m_desc", "value", ""))
        st.text_input("Link da fonte (RI da empresa, CVM, B3...)", key="ne_m_url", max_chars=300, **_opt("ne_m_url", "value", ""))
        st.button("Registrar", key="ne_m_add", on_click=_add_evento, icon=":material/add:")
        if _ss().get("ne_m_msg"):
            st.caption(_ss()["ne_m_msg"])
    meus = _ss().get(CH_EVENTOS) or []
    for i, m in enumerate(meus):
        c1, c2 = st.columns([6, 1])
        c1.markdown(f"{m['data']} · {I.escapar_md(m['evento'])} — {_link('fonte', m.get('url'))}")
        c2.button("Remover", key=f"ne_m_rm_{i}", on_click=_rm_evento, args=(i,))


def _add_evento():
    ss = _ss()
    try:
        d = ss.get("ne_m_data")
        e = N.evento_manual(ss.get("ne_m_tipo"), ss.get("ne_m_ativo") or "", d.isoformat() if hasattr(d, "isoformat") else str(d), ss.get("ne_m_desc") or "", ss.get("ne_m_url") or "")
    except ValueError as ex:
        ss["ne_m_msg"] = f"Não registrado: {ex}"
        return
    ss[CH_EVENTOS] = ((ss.get(CH_EVENTOS) or []) + [e])[-60:]
    ss["ne_m_msg"] = "Registrado. Aparece na próxima atualização."


def _rm_evento(i: int):
    lst = list(_ss().get(CH_EVENTOS) or [])
    if 0 <= i < len(lst):
        lst.pop(i)
    _ss()[CH_EVENTOS] = lst


def _aba_cripto(res):
    h = res.get("halving")
    if h:
        st.markdown(f"**Próximo halving do Bitcoin:** bloco {h['bloco_alvo']:,} (faltam {h['blocos_restantes']:,} blocos), data ESTIMADA {h['estimativa']}. "
                    "A data real varia com o ritmo da rede.".replace(",", "."))
    else:
        st.caption("Altura do bloco do Bitcoin indisponível agora: sem estimativa de halving.")
    _tabela_eventos(res["cripto"], res["impactos"], False)
    st.caption("Notícias sobre upgrades, forks, governança, exchanges e regulação aparecem como “reportadas” (a data é a da publicação). Desbloqueios de tokens e "
               "eventos de projetos entram quando você os informa, com link da fonte (página do ativo cripto e aba Corporativo). O app não consulta calendários de projetos por conta própria.")


def _aba_carteira(res):
    c = res.get("carteira")
    if not c:
        st.info("Registre posições em Carteira para ver o resumo diário, os riscos e a exposição a acontecimentos.")
        return
    st.markdown("#### Resumo do dia")
    for l in c["linhas"]:
        st.markdown("- " + I.escapar_md(l))
    s = res["sentimento"].get("_carteira")
    if s and s["recente"]["total"]:
        r = s["recente"]
        st.caption(f"Cobertura recente das suas posições: {r['positivo']} positivas, {r['negativo']} negativas, {r['neutro']} neutras, {r['incerto']} incertas. {s['aviso']}")
    if c["riscos"]:
        st.markdown("#### ⚠️ Riscos noticiados")
        for r in c["riscos"][:8]:
            st.markdown("- " + I.escapar_md(r))
    st.markdown("#### Notícias por posição")
    for k, lst in c["noticias_por_ativo"].items():
        with st.expander(f"{k} ({len(lst)})"):
            for g in lst:
                st.markdown(f"- {_link(g['titulo'], g.get('url'))} — {I.escapar_md(g['fonte'])}, {(g.get('publicada_em') or 'data n/d')[:10]} ({I.escapar_md(g['status'])})")
    st.markdown("#### Próximos eventos das posições")
    _tabela_eventos(c["proximos_eventos"], res["impactos"], True)
    if c["multiplos"]:
        st.markdown("#### Acontecimentos que podem afetar várias posições")
        for m in c["multiplos"]:
            st.markdown(f"- **{I.escapar_md(m['titulo'])}** — {len(m['ativos_carteira'])} posições, {m['peso_total_pct']:.0f}% da carteira: {', '.join(a['id'] for a in m['ativos_carteira'])}")
    st.markdown("#### Exposição a cenários econômicos")
    st.caption("Mapa de sensibilidade pelas regras de exposição (% da carteira). Não é previsão: a reação real depende da surpresa e de cada empresa.")
    df = pd.DataFrame([{"Cenário": x["cenario"], "Pode se beneficiar (%)": round(x["beneficia_pct"], 1), "Pode ser pressionada (%)": round(x["pressiona_pct"], 1),
                        "Efeito misto (%)": round(x["misto_pct"], 1), "Sem regra (%)": round(x["sem_regra_pct"], 1), "Mais expostas": ", ".join(x["ativos_pressionados"]) or "—"} for x in c["exposicao"]])
    st.dataframe(df, hide_index=True, width="stretch")


def _aba_impacto(res):
    st.caption("Leitura por regras: cada acontecimento mostra quais ativos seus PODEM ser afetados e por quê. Não afirma valorização nem queda.")
    s = res["sentimento"].get("_geral")
    if s:
        r = s["recente"]
        _cartoes = IA._cartoes
        _cartoes([("Positivas", str(r["positivo"]), "good"), ("Negativas", str(r["negativo"]), "bad"), ("Neutras", str(r["neutro"]), "na"), ("Incertas", str(r["incerto"]), "fair")], 4)
        for k, t in s["sinais"]:
            st.info(t)
        st.caption(s["aviso"])
    for d in res.get("divergencias_preco") or []:
        st.warning(f"{d['ativo']}: {d['texto']}")
    ids = ["_geral"] + sorted(k for k in res["sentimento"] if not k.startswith("_"))
    k = st.selectbox("Sentimento de", ids, key="ne_s_ativo", format_func=lambda x: "Mercado em geral (todas as notícias lidas)" if x == "_geral" else x)
    sk = res["sentimento"].get(k)
    if sk:
        r, a = sk["recente"], sk["anterior"]
        st.markdown(f"Últimos 3 dias: {r['positivo']} positivas · {r['negativo']} negativas · {r['neutro']} neutras · {r['incerto']} incertas. Antes: {a['positivo']} · {a['negativo']} · {a['neutro']} · {a['incerto']}.")
        for _, t in sk["sinais"]:
            st.caption(t)
    st.markdown("#### Impactos possíveis")
    imp = sorted(res["impactos"], key=lambda i: -i["relevancia"])
    if not res["ativos"]:
        st.info("Sem ativos cadastrados, os impactos aparecem sem lista de ativos afetados. Adicione ativos à carteira ou aos favoritos.")
    if not imp:
        st.caption("Nenhum acontecimento relevante associado aos seus ativos nesta leitura.")
    for i in imp[:25]:
        with st.expander(f"{_NIVEL[i['nivel']]} · {I.escapar_md(i['titulo'][:110])} — {I.escapar_md(i.get('nome_regra') or i['tipo_impacto'])}"):
            st.markdown(f"**Justificativa:** {I.escapar_md(i['justificativa'])}")
            st.markdown(f"**Horizonte provável:** {I.escapar_md(i['horizonte'])} · **Confiança da análise:** {i['confianca']} · **Origem:** {I.escapar_md(i.get('fonte') or 'n/d')} ({I.escapar_md(i.get('status') or '')})")
            if i.get("setores"):
                st.markdown("**Setores relacionados:** " + ", ".join(i["setores"]))
            for a in i["ativos"][:12]:
                st.markdown(f"- **{I.escapar_md(a['id'])}** — pode ser {I.escapar_md(a['direcao'])}: {I.escapar_md(a['porque'])}")
            if not i["ativos"]:
                st.caption("Nenhum ativo seu se encaixa nesta regra (classes/setores expostos: " + ", ".join(i.get("classes_expostas") or i.get("setores") or ["n/d"]) + ").")
            if i.get("url"):
                st.markdown(_link("Fonte original", i["url"]))
            st.caption(i["limite"])


def _padroes_ne():
    return [N.nova_regra_ne("noticia_urgente", "*", None, "cada_atualizacao", "alta"), N.nova_regra_ne("juros", "*", None, "diaria", "alta"),
            N.nova_regra_ne("indicador", "*", None, "diaria", "media"), N.nova_regra_ne("noticia_ativo", "*", None, "diaria", "media"),
            N.nova_regra_ne("dividendo", "*", None, "diaria", "baixa"), N.nova_regra_ne("cripto_evento", "*", None, "diaria", "media"),
            N.nova_regra_ne("regulatorio", "*", None, "diaria", "media"), N.nova_regra_ne("sentimento", "*", None, "diaria", "media")]


def _add_regra_ne():
    ss = _ss()
    tipo = ss.get("ne_r_tipo")
    num = int(ss.get("ne_r_num") or 0)
    chave = {"resultado_empresa": "dias_antes", "juros": "dias_antes", "dividendo": "dias_antes", "cripto_evento": "dias_antes", "noticia_ativo": "relevancia_min", "regulatorio": "relevancia_min"}.get(tipo)
    params = {chave: num} if chave else ({"relevancia": ss.get("ne_r_relev", "alta")} if tipo == "indicador" else {})
    pri = {"Alta": "alta", "Média": "media", "Baixa": "baixa"}.get(ss.get("ne_r_pri", "Média"), "media")
    try:
        r = N.nova_regra_ne(tipo, ss.get("ne_r_ativo") or "*", params, ss.get("ne_r_freq", "diaria"), pri)
    except ValueError as ex:
        ss["ne_r_msg"] = str(ex)
        return
    ss[CH_REGRAS] = [x for x in (ss.get(CH_REGRAS) or []) if x["id"] != r["id"]] + [r]
    ss["ne_r_msg"] = "Regra adicionada. Vale na próxima atualização."


def _rm_regra_ne(rid: str):
    _ss()[CH_REGRAS] = [r for r in (_ss().get(CH_REGRAS) or []) if r["id"] != rid]


FREQ_ROT = {"cada_atualizacao": "a cada atualização", "diaria": "no máximo uma vez por dia", "semanal": "no máximo uma vez por semana"}


def _aba_alertas(res):
    st.caption("Os alertas aparecem aqui ao atualizar a central; não há e-mail nem aviso no celular (dependem de um serviço externo). "
               "Cada regra tem sua frequência e o mesmo alerta não se repete dentro dela.")
    novos = res.get("alertas") or []
    if novos:
        st.markdown(f"#### Novos nesta leitura ({len(novos)})")
        for a in novos:
            st.markdown(f"{ {'alta': '🔴', 'media': '🟠', 'baixa': '🟡'}[a['prioridade']] } **{I.escapar_md(a['titulo'])}** — {I.escapar_md(a['texto'])}")
    else:
        st.info("Nenhum alerta novo nesta leitura." + (f" {res['suprimidos']} repetido(s) suprimido(s)." if res.get("suprimidos") else ""))
    regras = _ss().get(CH_REGRAS) or []
    st.markdown("#### Suas regras")
    if not regras:
        st.caption("Você ainda não criou regras.")
        if st.button("Criar regras sugeridas", key="ne_regras_sug", icon=":material/notifications_active:"):
            _ss()[CH_REGRAS] = _padroes_ne()
            st.rerun()
    for r in regras:
        c1, c2, c3 = st.columns([5, 2, 1])
        c1.markdown(f"**{I.escapar_md(N.descrever_regra_ne(r))}** · {I.escapar_md(r['ativo'] if r['ativo'] != '*' else 'todos os ativos')}")
        c2.caption(f"{r['prioridade']} · {FREQ_ROT[r['frequencia']]}")
        c3.button("Remover", key=f"ne_rm_{r['id']}", on_click=_rm_regra_ne, args=(r["id"],))
    with st.expander("Nova regra", icon=":material/add_alert:"):
        c1, c2 = st.columns(2)
        c1.selectbox("Tipo", list(N.TIPOS_ALERTA_NE), key="ne_r_tipo", format_func=lambda t: N.TIPOS_ALERTA_NE[t])
        c2.text_input("Ativo (código ou * para todos)", key="ne_r_ativo", **_opt("ne_r_ativo", "value", "*"))
        c3, c4, c5 = st.columns(3)
        c3.number_input("Dias de antecedência ou relevância mínima (conforme o tipo)", min_value=0, max_value=100, step=1, key="ne_r_num", **_opt("ne_r_num", "value", 3))
        c4.selectbox("Prioridade", ["Alta", "Média", "Baixa"], key="ne_r_pri", index=1)
        c5.selectbox("Frequência", list(N.FREQ_NE), key="ne_r_freq", index=1, format_func=lambda x: FREQ_ROT[x])
        st.selectbox("Relevância (só para Indicador econômico)", ["alta", "media"], key="ne_r_relev")
        st.button("Adicionar regra", key="ne_r_add", on_click=_add_regra_ne, icon=":material/add:")
        if _ss().get("ne_r_msg"):
            st.caption(_ss()["ne_r_msg"])
    hist = _ss().get(CH_HIST) or []
    if hist:
        with st.expander(f"Histórico de alertas ({len(hist)})"):
            for h in reversed(hist[-40:]):
                st.markdown(f"- {h['quando'][:16].replace('T', ' ')} · **{I.escapar_md(h['titulo'])}** ({h['prioridade']})")
            st.button("Limpar histórico", key="ne_hist_limpar", on_click=lambda: _ss().__setitem__(CH_HIST, []))


SUGESTOES = ["Quais as principais notícias de hoje?", "Quais os próximos eventos econômicos?", "O que saiu de dados de inflação?", "Como as notícias podem afetar minha carteira?",
             "Há notícias contraditórias?", "Como está o sentimento do mercado?"]


def _aba_assistente(res):
    st.caption("Responde só com o que a central já leu, citando fontes e separando fato de interpretação. Não recomenda compra ou venda.")
    cols = st.columns(2)
    for i, s in enumerate(SUGESTOES):
        if cols[i % 2].button(s, key=f"ne_sug_{i}"):
            _ss()["ne_q"] = s
    q = st.text_input("Pergunte sobre notícias e eventos", key="ne_q", max_chars=300, **_opt("ne_q", "value", ""))
    if q and q.strip():
        r = N.responder_noticias(q.strip(), contexto_ia(res))
        st.markdown(f"**{I.escapar_md(r['texto'])}**")
        for l in r["fatos"]:
            st.markdown("- ✅ **Fato:** " + I.escapar_md(l))
        for l in r["interpretacoes"]:
            st.markdown("- 💭 **Interpretação:** " + I.escapar_md(l))
        if r["fontes"]:
            with st.expander("Fontes usadas"):
                for s in r["fontes"]:
                    st.markdown("- " + I.escapar_md(s))
        st.caption(f"{r['referencia']}. {r['consultado']} {r['limite']}")
    st.download_button("Baixar relatório (Markdown)", N.relatorio_md(contexto_ia(res)).encode("utf-8"), file_name=f"noticias_{date.today():%Y%m%d}.md", mime="text/markdown", key="ne_dl")


def _aba_fontes(res):
    st.caption("Situação de cada fonte na última atualização. Uma fonte com falha não gera dado inventado: ela simplesmente fica de fora.")
    df = pd.DataFrame([{"Fonte": f["fonte"], "Situação": "✅ ok" if f["ok"] else f"⚠️ {f['erro']}", "Itens": f["n"], "Oficial": "sim" if f.get("oficial") else "não", "Consulta": (f["quando"] or "")[:16].replace("T", " ")}
                       for f in res["fontes"]])
    st.dataframe(df, hide_index=True, width="stretch")
    _diag_fotos(res)


def _diag_fotos(res):
    """Diagnóstico das fotos: mostra, passo a passo, onde a foto das 3 notícias mais relevantes se perde. Só roda ao clicar no botão."""
    with st.expander("Diagnóstico das fotos", icon=":material/image_search:"):
        st.caption("Testa o caminho da foto das 3 notícias mais relevantes (decodificar o link, abrir a matéria, ler a imagem de capa). Só roda quando você clica.")
        if not st.button("Rodar diagnóstico", key="ne_diag_fotos"):
            return
        import requests
        from urllib.parse import urljoin, urlparse
        try:
            import googlenewsdecoder as _gnd
            st.write(f"Pacote googlenewsdecoder: carregou (versão {getattr(_gnd, '__version__', 'n/d')}).")
        except Exception as e:
            st.error(f"O pacote googlenewsdecoder NÃO carregou: {e.__class__.__name__}: {str(e)[:150]}")
        grupos = sorted([g for g in res["grupos"] if not g.get("desatualizada")], key=lambda x: -x.get("relevancia", 0))[:3]
        if not grupos:
            st.info("Nenhuma notícia recente para testar.")
            return
        for g in grupos:
            st.markdown(f"**{str(g['titulo'])[:90]}**")
            st.write(f"Foto vinda do feed: {'sim' if g.get('imagem') else 'não'}.")
            links = NF._links_do_grupo(g, 1)
            if not links:
                st.write("Este grupo não tem link para testar.")
                continue
            link = links[0]
            gid = NF.id_google(link)
            real = None
            if not gid:
                real = link
                st.write("1) Link direto (não é do Google Notícias).")
            else:
                real = NF.decodificar_legado(gid)
                if real:
                    st.write("1) Link antigo do Google Notícias: endereço da matéria obtido sem rede.")
                else:
                    st.write("1) Link novo do Google Notícias: pedindo o endereço real ao decodificador...")
                    try:
                        from googlenewsdecoder import gnewsdecoder
                        t0 = time.time()
                        r = gnewsdecoder(link, interval=0)
                        dt = time.time() - t0
                        if r and str(r.get("decoded_url", "")).startswith("http"):
                            real = r["decoded_url"]
                            st.write(f"   Decodificador respondeu em {dt:.1f} s: ok.")
                        else:
                            st.error(f"   Decodificador respondeu em {dt:.1f} s, mas sem endereço. Resposta completa abaixo:")
                            st.code(repr(r)[:600])
                    except Exception as e:
                        st.error(f"   Decodificador falhou: {e.__class__.__name__}: {str(e)[:150]}")
            if not real:
                st.write("→ Sem o endereço da matéria, não há como achar a foto.")
                continue
            atual = real
            html_txt = None
            for _ in range(4):
                host = urlparse(atual).hostname or "?"
                if not NF.host_publico(atual):
                    st.write(f"2) Endereço {host} recusado pela regra de segurança (só https e sites públicos).")
                    break
                try:
                    t0 = time.time()
                    resp = requests.get(atual, headers=NF.UA, timeout=(3, 5), stream=True, allow_redirects=False)
                    dt = time.time() - t0
                    try:
                        cod = resp.status_code
                        if cod in (301, 302, 303, 307, 308) and resp.headers.get("location"):
                            atual = urljoin(atual, resp.headers["location"])
                            st.write(f"2) {host}: redireciona ({cod}) para {urlparse(atual).hostname}.")
                            continue
                        if cod != 200:
                            st.write(f"2) {host}: respondeu código {cod} em {dt:.1f} s (o site recusou ou falhou).")
                            break
                        dados = b""
                        for parte in resp.iter_content(16384):
                            dados += parte
                            if len(dados) >= NF.MAX_BYTES:
                                break
                        html_txt = dados[:NF.MAX_BYTES].decode(resp.encoding or "utf-8", "ignore")
                        st.write(f"2) {host}: página aberta em {dt:.1f} s ({len(dados) // 1024} KB).")
                    finally:
                        resp.close()
                except Exception as e:
                    st.error(f"2) {host}: falha ao abrir ({e.__class__.__name__}: {str(e)[:120]}).")
                break
            if html_txt is not None:
                img = NF.imagem_de_html(html_txt, atual)
                st.write("3) Imagem de capa achada." if img else "3) A página abriu, mas não declara imagem de capa (og:image / twitter:image).")
                if img:
                    st.caption(f"Imagem: {urlparse(img).hostname}")


LIMITES = [
    "CVM e B3 (fatos relevantes, resultados, assembleias, ofertas): não têm API aberta simples; use o cadastro de eventos com link da fonte.",
    "Resultados de empresas americanas e calendário de bancos centrais fora Copom/FOMC: não integrados (exigem chave ou fonte adicional).",
    "Sentimento é uma contagem de palavras em títulos e resumos: aproximada, não entende ironia nem contexto.",
    "Impacto é por regras de exposição (classe, setor, tipo): mostra o que pode ser afetado, nunca o tamanho nem o sinal do efeito no preço.",
    "Alertas só aparecem no aplicativo; e-mail e celular exigem um serviço externo.",
    "O site do BLS (Payroll e CPI dos EUA) recusa leitura automática (erro 403) e o IBGE pode demorar a responder; nesses casos o evento some em vez de ser estimado.",
    "Datas do Copom de 2027 ainda não foram publicadas na conferência feita; por isso não aparecem.",
]


def pagina_noticias(hooks: dict | None = None):
    hooks = hooks or {}
    st.markdown(tema.cabecalho("📰", "Central de notícias e eventos", "Notícias, calendário econômico e corporativo, eventos cripto, sentimento e possíveis impactos nos seus ativos."),
                unsafe_allow_html=True)
    try:
        n_at = len((hooks.get("ativos") or (lambda: []))() or [])
    except Exception:
        n_at = 0
    c1, c2 = st.columns([1, 3])
    clicou = c1.button("Atualizar notícias", key="ne_atualizar", type="primary", icon=":material/refresh:")
    c2.caption(f"{n_at} ativo(s) acompanhado(s) (carteira e favoritos). Busca em ~25 fontes, com cache de 15 minutos. Nada é negociado.")
    ant = leitura()
    velha = ant is None or (_agora() - datetime.fromisoformat(ant["quando"])).total_seconds() > AUTO_MINUTOS * 60
    if clicou:
        st.session_state.pop("ne_auto_falhou", None)
    if clicou or (velha and not st.session_state.get("ne_auto_falhou")):       # ao entrar (ou se a leitura ficou velha), atualiza sozinho
        with st.spinner("Lendo notícias, calendários e indicadores..."):
            try:
                atualizar(hooks)
            except Exception as ex:
                log.exception("falha na atualização")
                st.session_state["ne_auto_falhou"] = True                       # não fica tentando de novo a cada clique
                st.error(f"A atualização falhou ({ex.__class__.__name__}). Clique em “Atualizar notícias” para tentar de novo; o problema foi registrado.")
    res = leitura()
    abas = ["Principais", "Últimas", "Econômico", "Corporativo", "Cripto", "Carteira", "Impacto e sentimento", "Alertas", "Assistente", "Fontes"]
    tabs = st.tabs(abas)
    if res is None:
        for t in tabs:
            with t:
                st.info("Clique em “Atualizar notícias” para começar.")
        st.caption(N.AVISO_LEGAL)
        return
    idade = (_agora() - datetime.fromisoformat(res["quando"])).total_seconds() / 3600
    st.caption(f"Última leitura: {res['quando'][:16].replace('T', ' ')} ({idade:.1f} h atrás) · {len(res['noticias'])} notícias em {len(res['grupos'])} acontecimentos · "
               f"{sum(1 for f in res['fontes'] if not f['ok'])} fonte(s) com falha" + (f" · leitura levou {res['duracao']:.0f} s." if res.get("duracao") is not None else "."))
    f = _filtros(res)
    for t, fn, usa in zip(tabs, [_aba_principais, _aba_ultimas, _aba_economico, _aba_corporativo, _aba_cripto, _aba_carteira, _aba_impacto, _aba_alertas, _aba_assistente, _aba_fontes],
                          [True, True, False, False, False, False, False, False, False, False]):
        with t:
            fn(res, f) if usa else fn(res)
    st.caption(N.AVISO_LEGAL)


def _opt(chave: str, nome: str, valor) -> dict:
    return {} if chave in st.session_state else {nome: valor}
