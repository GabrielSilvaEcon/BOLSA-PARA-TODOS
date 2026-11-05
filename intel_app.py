"""
Passo 13 — Central de inteligência: oportunidades, riscos, notícias, alertas, rankings, monitoramento, previsões, assistente e
relatório, sobre os ativos que a pessoa acompanha (favoritos + carteira + renda fixa + criptomoedas já escolhidas no app).

COMO FUNCIONA (camadas separadas):
  coleta    → o app já sabe montar o Ativo de cada classe (Comparador, Passos 6–11); esta tela só recebe essa função (`coletor`)
              e acrescenta histórico de preços, demonstrativos (Passo 7), alertas de cripto (Passo 9), notícias (RSS) e a carteira (Passo 12);
  processo  → intel.py (sem Streamlit): anomalias, oportunidades, notícias, alertas, rankings, cenários, assistente;
  tela      → este arquivo.
A leitura é feita só quando a pessoa clica em "Atualizar leitura" (custo e desempenho sob controle; as demais telas não são afetadas).
Nada é comprado, vendido ou alterado. "Inteligência" aqui = regras e estatística explicáveis, sem chamada paga de IA.
"""
from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo
from urllib.parse import quote_plus

import numpy as np
import pandas as pd
import streamlit as st

import comparador
import crescimento as cr
import evolucao
import analise_tecnica as T
import intel as I
import noticias_eventos as NE
import risco as RK
import simulador_ia as SIM_IA
import relatorios_ia as REL_IA
import comparador_ia as CMP_IA
import tema


class _Plotly:
    def __getattr__(self, nome):
        import plotly.graph_objects as _go
        return getattr(_go, nome)


go = _Plotly()
CH_PREFS, CH_REGRAS, CH_HIST, CH_FOTO = "intel_prefs", "intel_regras", "intel_hist", "intel_fotos"
CH_CACHE = "_intel_cache"            # só em memória da sessão (não é gravado no perfil do usuário)
MAX_ATIVOS = 25                      # custo/desempenho: limite de ativos por leitura
MAX_COM_NOTICIA = 12
VALIDADE_H = 6                       # leitura mais velha que isso é marcada como desatualizada
URL_NOTICIAS = "https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"
CONSULTA_GERAL = "Copom Selic inflação IPCA juros Brasil when:7d"
TRANSP = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", margin=dict(l=10, r=10, t=40, b=10))
SUGESTOES = ["Quais ativos apresentaram melhora nos fundamentos?", "Quais ativos estão com riscos crescentes?",
             "Quais FIIs possuem maior consistência de rendimentos?", "Quais criptomoedas apresentam crescimento de utilização?",
             "Quais ETFs possuem menores custos?", "Quais títulos de renda fixa apresentam características mais interessantes?",
             "Como está minha carteira atualmente?", "Onde existe concentração excessiva?", "O que mudou nos ativos que acompanho?",
             "Quais acontecimentos merecem minha atenção?",
             "Qual a situação técnica dos ativos da carteira?", "Há rompimentos recentes nos ativos que acompanho?",
             "Quais os próximos eventos econômicos?", "Quais notícias podem afetar minha carteira?"]
PILARES_CONHECIDOS = ("Valor", "Qualidade", "Dividendos", "Solidez", "Tendência", "Risco", "Retorno", "Custos e porte", "Renda", "Liquidez", "Valuation (P/VP)",
                      "Qualidade dos ativos", "Consistência", "Crédito", "Retorno real esperado", "Risco de mercado", "Porte e liquidez", "Custos")
SEM_FONTE = [
    "Notícias: só o RSS público do Google Notícias (títulos, fonte e data; sem o texto completo). Não há feed próprio de fatos relevantes da CVM.",
    "Alertas: aparecem nesta tela. Não há envio por e-mail, push ou WhatsApp (exigiria servidor próprio e conta de envio).",
    "Desbloqueio de tokens: só eventos que você informar com link de fonte (Criptomoedas → Tokenomics); não há calendário automático.",
    "Resultados trimestrais e fatos relevantes de ações: o app usa os demonstrativos anuais do Yahoo; não há agenda de resultados.",
    "Dados on-chain e de utilização: TVL (DefiLlama) e transações do Blockchair onde houver; não mede toda atividade de uma rede.",
    "ETFs: custos (taxa de administração) dependem de fonte ainda não integrada; o assistente diz 'sem dado' em vez de estimar.",
    "Indicadores técnicos avançados e fluxo de ordens: fora do escopo desta leitura (a página Análise Técnica tem os setups).",
]


def _ss():
    return st.session_state


def _padrao(chave: str, valor) -> dict:
    return {} if chave in st.session_state else {"value": valor}


def _cartoes(itens: list, por_linha: int = 4):
    for k in range(0, len(itens), por_linha):
        for col, (rot, val, cls, *det) in zip(st.columns(por_linha), itens[k:k + por_linha]):
            col.markdown(tema.card_status(rot, val, cls, det[0] if det else "", det[1] if len(det) > 1 else ""), unsafe_allow_html=True)


def _agora() -> datetime:
    """Hora de Brasília (sem fuso), pois o servidor roda em UTC."""
    try:
        return datetime.now(ZoneInfo("America/Sao_Paulo")).replace(tzinfo=None)
    except Exception:
        return datetime.now()


def _md(t) -> str:
    return I.escapar_md(t)


def prefs() -> dict:
    p = I.normalizar_prefs(_ss().get(CH_PREFS))
    _ss()[CH_PREFS] = p
    return p


# =============================================================================== coleta
@st.cache_data(ttl=1800, show_spinner=False)
def _noticias_rss(consulta: str) -> dict:
    """RSS do Google Notícias. Falha de rede vira aviso (nunca notícia inventada). Nada do usuário além do termo de busca é enviado."""
    out = {"itens": [], "erro": None, "quando": _agora().isoformat(timespec="minutes"), "fonte": "Google Notícias (RSS)"}
    try:
        import requests
        r = requests.get(URL_NOTICIAS.format(q=quote_plus(consulta)), timeout=8, headers={"User-Agent": "BussolaB3/1.0 (educacional)"})
        if r.status_code != 200:
            out["erro"] = f"HTTP {r.status_code}"
        else:
            out["itens"] = I.parse_rss(r.text)
    except Exception as e:
        out["erro"] = e.__class__.__name__
    return out


def _nome_busca(a) -> str:
    """Nome curto para buscar notícias: o do catálogo do app (ex.: Petrobras) ou o nome do ativo sem parênteses."""
    try:
        import recursos as rec
        curto = rec.nome_curto(a.chave)
        if curto and curto.upper() != a.chave.upper():
            return curto
    except Exception:
        pass
    return re.sub(r"\s*\(.*?\)\s*", " ", a.nome or "").strip()


def _valores(ind: dict) -> dict:
    return {k: (v.valor if hasattr(v, "valor") else v) for k, v in (ind or {}).items()}


def _pct_serie(s: pd.Series, n: int):
    s = I._serie(s)
    if len(s) <= n:
        return None
    return float(s.iloc[-1] / s.iloc[-1 - n] - 1) * 100


def _var_dividendos(div: pd.Series):
    """Proventos dos últimos 12 meses contra os 12 meses anteriores (%). None se não houver os dois períodos."""
    if div is None or len(div) == 0:
        return None
    d = div[div > 0]
    if len(d) == 0:
        return None
    fim = pd.Timestamp(date.today())
    a = float(d[(d.index > fim - pd.Timedelta(days=365)) & (d.index <= fim)].sum())
    b = float(d[(d.index > fim - pd.Timedelta(days=730)) & (d.index <= fim - pd.Timedelta(days=365))].sum())
    if b <= 0:
        return None             # sem proventos no período anterior não há base de comparação
    return (a / b - 1) * 100


def _dados_de_preco(tk: str) -> dict:
    p = evolucao.coletar_precos(tk)
    return {"preco": p["preco"], "volume": p["volume"], "div": p["div"], "avisos": p.get("avisos", [])}


def _extras_cripto(gid: str) -> dict:
    """Alertas com fonte (motor de monitoramento do Passo 9) e desbloqueios informados pela pessoa. Falha = sem esses dados."""
    import cripto_app
    d = cripto_app._preparar(gid)
    an = []
    for a in d.get("alertas") or []:
        grav = {"alto": "alta", "atencao": "media"}.get(a.get("nivel"), "baixa")
        sent = "negativo" if a.get("nivel") in ("alto", "atencao") else "neutro"
        an.append({"tipo": a.get("tipo", "cripto"), "sentido": sent, "gravidade": grav, "texto": f"{a.get('titulo')}. {a.get('texto')}",
                   "natureza": f"alerta calculado de dado verificável ({a.get('fonte', 'fonte n/d')})", "data": a.get("data"), "valor": None, "limiar": None})
    desb = [{"dias": e.get("dias"), "data": e.get("data"), "fonte": e.get("fonte")} for e in ((d.get("desb") or {}).get("proximos") or [])]
    return {"anomalias": an, "desbloqueios": desb}


def _dias_rf(ind: dict):
    pa = ind.get("prazo_anos")
    return float(pa) * 365.0 if I._ok(pa) else None


def _resumo_tecnico(ps, vol, tk: str, cl: str):
    """Resumo da Análise técnica avançada (Passo 14) para o ativo, com os MESMOS preços já lidos. Só fechamento e volume: sem máximas/mínimas
    a leitura de padrões e ATR é limitada, e o resumo avisa. None se não houver histórico ou se a leitura falhar."""
    try:
        d = pd.DataFrame({"Close": I._serie(ps)})
        v = I._serie(vol)
        if len(v):
            d["Volume"] = v.reindex(d.index)
        r = T.resumo_tecnico(d, "acao" if cl == "bdr" else cl, tk, {"fonte": "Yahoo Finance (Passo 13)"}, "BRL", "diário")
        return r if r.get("disponivel") else None
    except Exception:
        return None


def riscos_tecnicos(item: dict) -> list[str]:
    """Riscos que a leitura técnica mostra (descritivos; não são previsão)."""
    r = item.get("tecnica")
    if not r or not r.get("disponivel"):
        return []
    out, t = [], r["tendencia"]
    if t.get("tendencia") == "baixa":
        out.append(f"Tendência técnica de baixa (confiança {t.get('confianca') or 'n/d'}).")
    if (r.get("volatilidade") or {}).get("elevada"):
        out.append("Volatilidade técnica elevada em relação ao normal recente do próprio ativo.")
    if (r.get("osciladores") or {}).get("geral") == "sobrecompra":
        out.append("Osciladores em sobrecompra (movimento esticado; não indica reversão por si só).")
    if (r.get("liquidez") or {}).get("aviso"):
        out.append(r["liquidez"]["aviso"])
    return out


def analisar_ativo(a, origem: list[str], noticias: list[dict]) -> dict:
    """Ativo do Comparador → dicionário de leitura. Todo campo vem de um motor existente ou de cálculo explícito; sem dado = None."""
    ind = _valores(a.ind)
    pont = a.pontuacao
    item = {"id": a.chave, "nome": a.nome, "classe": a.classe, "origem": origem, "fonte": a.fonte, "data_ref": a.data_ref,
            "avisos": list(a.avisos or []), "ind": ind, "nota": pont.nota if pont else None, "pilares": dict(pont.pilares) if pont else {},
            "pesos": dict(pont.pesos) if pont else {}, "cobertura": pont.cobertura if pont else None,
            "provisoria": bool(pont.provisoria) if pont else False, "erro": a.erro, "subgrupo": a.subgrupo_nome or None,
            "achados": [], "anomalias": [], "tendencia": {}, "bandeiras": [], "noticias": noticias, "desbloqueios": [], "preco": None,
            "var_1d": None, "var_5d": None, "vol_razao": None, "volume_x": None, "div_var_pct": None, "dias_vencimento": None,
            "resultado": None, "tecnica": None, "analisado_em": _agora().isoformat(timespec="minutes")}
    if a.erro:
        return item
    tk, cl = a.chave, a.classe
    if cl in ("acao", "bdr", "fii", "etf"):
        try:
            pr = _dados_de_preco(tk)
            item["avisos"] += [x for x in pr["avisos"] if x not in item["avisos"]]
            ps, vol = pr["preco"], pr["volume"]
            if len(ps):
                item["preco"] = float(ps.iloc[-1])
                item["var_1d"], item["var_5d"] = _pct_serie(ps, 1), _pct_serie(ps, 5)
                item["anomalias"] = I.cruzar_anomalias_noticias(I.anomalias_preco(ps, vol), noticias)
                item["tendencia"] = I.tendencia(ps)
                r = I._serie(ps).pct_change().dropna()
                if len(r) >= 140 and float(r.iloc[-120:].std()) > 0:
                    item["vol_razao"] = float(r.iloc[-20:].std() / r.iloc[-120:].std())
                v = I._serie(vol)
                if len(v) >= 25 and float(v.iloc[-21:-1].median()) > 0:
                    item["volume_x"] = float(v.iloc[-1] / v.iloc[-21:-1].median())
            item["div_var_pct"] = _var_dividendos(pr["div"])
            item["tecnica"] = _resumo_tecnico(ps, vol, tk, cl)
        except Exception as e:
            item["avisos"].append(f"Histórico de preços indisponível ({e.__class__.__name__}).")
    if cl in ("acao", "bdr"):
        try:
            dm = evolucao.coletar_demonstrativos(tk)
            df = dm["anual"]
            if df is not None and len(df) >= 3:
                item["achados"] = [{"chave": x.chave, "tom": x.tom, "titulo": x.titulo, "texto": x.texto}
                                   for x in cr.diagnosticar(df, financeira=evolucao.eh_financeira(tk))]
            if df is not None and len(df):
                item["resultado"] = I._iso(df.index[-1])
        except Exception as e:
            item["avisos"].append(f"Demonstrativos indisponíveis ({e.__class__.__name__}).")
    if cl == "cripto":
        try:
            x = _extras_cripto(tk)
            item["anomalias"], item["desbloqueios"] = x["anomalias"], x["desbloqueios"]
        except Exception as e:
            item["avisos"].append(f"Monitoramento de cripto indisponível ({e.__class__.__name__}).")
    if cl == "renda_fixa":
        item["dias_vencimento"] = _dias_rf(ind)
    pr_ = prefs()
    item["bandeiras"] = I.bandeiras_de(item["achados"], item["anomalias"], ind, pr_["risco"], cl)
    extras = I.extras_de_achados(item["achados"])
    if item["tendencia"].get("rotulo"):
        extras["Tendência de preço"] = {"alta": True, "baixa": False}.get(item["tendencia"]["rotulo"])
    extras = {k: v for k, v in extras.items() if v is not None}
    op = I.avaliar_oportunidade(cl, item["pilares"], item["bandeiras"], extras, prioritarios=pr_["pilares_prioritarios"])
    item["oportunidade"], item["status"], item["texto_oportunidade"] = op, op["status"], op["texto"]
    item["riscos"] = list(item["bandeiras"]) + [x["texto"] for x in item["anomalias"] if x.get("sentido") == "negativo"]
    saldo = sum(1 for x in item["achados"] if x["tom"] == "positivo") - sum(1 for x in item["achados"] if x["tom"] == "atencao")
    item["ind"]["saldo_fundamentos"] = float(saldo) if item["achados"] else None
    item["ind"]["pilar_renda"] = item["pilares"].get("Renda")
    return item


def universo(p: dict) -> dict:
    """Códigos que a pessoa acompanha, com a origem de cada um. Limite por leitura para controlar custo e tempo."""
    ss = _ss()
    origem: dict[str, list[str]] = {}
    criptos: dict[str, list[str]] = {}

    def add(cod, orig):
        if cod:
            origem.setdefault(cod, [])
            if orig not in origem[cod]:
                origem[cod].append(orig)

    try:
        import cripto_app
    except Exception:
        cripto_app = None
    for chave in ("cart_real", "cart_ficticia"):
        for l in ss.get(chave, []) or []:
            if not isinstance(l, dict) or not l.get("ticker"):
                continue
            t = str(l["ticker"]).upper().replace(".SA", "")
            simb = cripto_app.simbolo_cripto(t) if cripto_app else None
            gid = cripto_app._gid_do_simbolo(simb) if simb else None
            if gid:
                criptos.setdefault(gid, []).append("carteira")
            elif not simb:
                add(t, "carteira")
    try:
        import renda_fixa_app as rfa
        for t in rfa._titulos_carteira():
            add(rfa.codigo_de(t), "carteira")
    except Exception:
        pass
    for f in ss.get("cart_fundos_cvm", []) or []:
        cn = f.get("cnpj") if isinstance(f, dict) else f
        add(str(cn) if cn else None, "carteira")
    for t in p["favoritos"]:
        add(t, "favorito")
    for gid in ss.get("cripto_ativos", []) or []:
        criptos.setdefault(gid, []).append("favorito")
    return {"codigos": origem, "criptos": criptos}


def _classe_permitida(classe: str, p: dict) -> bool:
    return classe in p["classes"]


def atualizar(coletor, perfil: str = "Moderado") -> dict:
    """Leitura completa (chamada só pelo botão). `coletor(codigos, criptos, perfil)` devolve os Ativos já pontuados."""
    p = prefs()
    u = universo(p)
    codigos = list(u["codigos"])[:MAX_ATIVOS]
    criptos = list(u["criptos"])[: max(0, MAX_ATIVOS - len(codigos))]
    corte = len(u["codigos"]) + len(u["criptos"]) > MAX_ATIVOS
    agora = _agora()
    avisos: list[str] = []
    if corte:
        avisos.append(f"Há mais de {MAX_ATIVOS} ativos: a leitura usou os {MAX_ATIVOS} primeiros (carteira antes dos favoritos) para limitar tempo e consultas.")
    if not codigos and not criptos:
        return {"quando": agora.isoformat(timespec="seconds"), "ativos": [], "noticias": [], "avisos": ["Nada para ler: adicione favoritos ou registre posições na Carteira."],
                "carteira": None, "mudancas": [], "estado": {}, "fontes_noticias": {}, "universo_total": 0}
    ativos = coletor(codigos, criptos, perfil)
    itens: list[dict] = []
    com_noticia = 0
    todas_noticias: list[dict] = []
    status_noticias = {"ok": 0, "erro": 0, "detalhe": None}
    falhas_seguidas = 0
    ordem = sorted(ativos, key=lambda a: (0 if "carteira" in (u["codigos"].get(a.chave) or u["criptos"].get(a.chave) or []) else 1))
    for a in ordem:
        if not _classe_permitida(a.classe, p):
            continue
        nt = []
        if com_noticia < MAX_COM_NOTICIA and falhas_seguidas < 2 and not a.erro and a.classe in ("acao", "bdr", "fii", "etf", "cripto"):
            nome = _nome_busca(a)
            consulta = f'"{nome}" when:14d' if nome and nome.upper() != a.chave.upper() else f"{a.chave} when:14d"
            r = _noticias_rss(consulta)
            com_noticia += 1
            if r["erro"]:
                status_noticias["erro"] += 1
                status_noticias["detalhe"] = r["erro"]
                falhas_seguidas += 1
            else:
                status_noticias["ok"] += 1
                falhas_seguidas = 0
            nt = I.processar_noticias(r["itens"], a.chave, nome or None, agora)
            nt = [n for n in nt if n["relevancia"] >= 20][:6]
        todas_noticias += nt
        itens.append(analisar_ativo(a, list(dict.fromkeys(u["codigos"].get(a.chave, []) + u["criptos"].get(a.chave, []))), nt))
    if falhas_seguidas >= 2:
        avisos.append("O serviço de notícias não respondeu duas vezes seguidas: as consultas restantes foram puladas para não travar a leitura.")
    geral = _noticias_rss(CONSULTA_GERAL) if falhas_seguidas < 2 else {"itens": [], "erro": status_noticias["detalhe"] or "indisponível"}
    gn = [n for n in I.processar_noticias(geral["itens"], None, None, agora) if n["relevancia"] >= 20][:8]
    for n in gn:
        n["ativo"] = None
    status_noticias["ok" if not geral["erro"] else "erro"] += 1
    if geral["erro"]:
        status_noticias["detalhe"] = geral["erro"]
    todas_noticias += gn
    cart = None
    try:
        import gestao_app
        chave = "cart_real" if (_ss().get("cart_real") or _ss().get("cart_fundos_cvm")) else "cart_ficticia"
        cart = gestao_app.contexto_para_inteligencia(chave)
    except Exception:
        avisos.append("A carteira não pôde ser lida agora (Gestão de carteira).")
    estado = {}
    for it in itens:
        if it["erro"]:
            continue
        ind_e = {k: v for k, v in it["ind"].items() if I._ok(v)}
        if I._ok(it["nota"]):
            ind_e["nota"] = it["nota"]
        estado[it["id"]] = {"preco": it["preco"], "var_1d": it["var_1d"], "var_5d": it["var_5d"], "ind": ind_e, "div_var_pct": it["div_var_pct"],
                            "resultado_novo": None, "vol_razao": it["vol_razao"], "volume_x": it["volume_x"], "noticias": it["noticias"],
                            "anomalias": it["anomalias"], "bandeiras": it["bandeiras"], "desbloqueios": it["desbloqueios"],
                            "dias_vencimento": it["dias_vencimento"]}
    if cart:
        estado["_carteira"] = {"maior_peso": cart.get("maior_peso"), "pesos_classe": cart.get("pesos_classe") or {}}
    fotos = _ss().get(CH_FOTO) or {}
    hoje = agora.date().isoformat()
    anteriores = sorted(d for d in fotos if d < hoje)
    foto_ant = fotos[anteriores[-1]] if anteriores else None
    novas = {it["id"]: I.fotografia(it, agora) | {"resultado": it["resultado"]} for it in itens if not it["erro"]}
    for tk, f in novas.items():
        if foto_ant and tk in foto_ant and f.get("resultado") and foto_ant[tk].get("resultado") and f["resultado"] != foto_ant[tk]["resultado"]:
            estado[tk]["resultado_novo"] = f["resultado"]
    mudancas = I.comparar_fotografias(foto_ant, novas) if foto_ant else []
    fc = _ss().get(CH_FOTO + "_carteira") or {}
    ant_c = fc[sorted(d for d in fc if d < hoje)[-1]] if any(d < hoje for d in fc) else None
    if cart:
        mudancas += I.comparar_carteira(ant_c, {"maior_peso": cart.get("maior_peso"), "corr_media": cart.get("corr_media"), "n_efetivo": cart.get("n_efetivo"),
                                                "data": hoje}) if ant_c else []
        fc[hoje] = {"maior_peso": cart.get("maior_peso"), "corr_media": cart.get("corr_media"), "n_efetivo": cart.get("n_efetivo"), "data": hoje}
        _ss()[CH_FOTO + "_carteira"] = {d: fc[d] for d in sorted(fc)[-8:]}
    fotos[hoje] = novas
    _ss()[CH_FOTO] = {d: fotos[d] for d in sorted(fotos)[-6:]}
    if not foto_ant:
        avisos.append("Primeira leitura: as mudanças aparecem a partir da próxima leitura em outro dia.")
    # alertas
    disp = I.avaliar_alertas(_ss().get(CH_REGRAS) or [], estado, agora)
    novos, hist, supr = I.filtrar_repetidos(disp, _ss().get(CH_HIST) or [], agora, p["frequencia"], tipos_permitidos=p["tipos_alerta"] or None)
    _ss()[CH_HIST] = hist
    novos += _alertas_tecnicos(itens, agora)
    try:                                  # Passo 23: guarda na Central de notificações (nunca atrapalha esta página)
        import notif_app
        notif_app.registrar_disparos(novos, "intel")
    except Exception:
        pass
    res = {"quando": agora.isoformat(timespec="seconds"), "ativos": itens, "noticias": todas_noticias, "avisos": avisos, "carteira": cart,
           "mudancas": mudancas, "alertas": novos, "suprimidos": supr, "estado": estado, "fontes_noticias": status_noticias,
           "universo_total": len(u["codigos"]) + len(u["criptos"])}
    _ss()[CH_CACHE] = res
    return res


def _alertas_tecnicos(itens: list, agora) -> list:
    """Regras criadas na Análise técnica avançada (tec_av_regras), avaliadas sobre os ativos já lidos aqui (sem novas consultas).
    Usa o histórico próprio dessas regras (tec_av_hist) para não repetir o mesmo evento."""
    regras = [r for r in (_ss().get("tec_av_regras") or []) if r.get("ativa", True)]
    if not regras:
        return []
    try:
        series = {}
        for a in itens:
            t_ = a.get("tecnica")
            if t_ and a.get("preco") is not None:
                ps = _dados_de_preco(a["id"])
                d = pd.DataFrame({"Close": I._serie(ps["preco"])})
                v = I._serie(ps["volume"])
                if len(v):
                    d["Volume"] = v.reindex(d.index)
                series[a["id"]] = {"df": d, "classe": "acao" if a["classe"] == "bdr" else a["classe"]}
        series = {k: v for k, v in series.items() if any(r["ativo"] in ("*", k) for r in regras)}
        if not series:
            return []
        disp, _av = T.avaliar_alertas_tec(regras, series, agora)
        novos, hist, _s = T.filtrar_por_frequencia(disp, _ss().get("tec_av_hist") or [], regras, agora)
        _ss()["tec_av_hist"] = hist
        return novos
    except Exception:
        return []


def leitura() -> dict | None:
    return _ss().get(CH_CACHE)


def _idade_h(res) -> float | None:
    try:
        return (_agora() - datetime.fromisoformat(res["quando"])).total_seconds() / 3600
    except Exception:
        return None


def _ctx_noticias() -> dict | None:
    """Contexto da Central de notícias (Passo 15), se ela já foi atualizada nesta sessão. Só leitura do que ela guardou."""
    r = _ss().get("_ne_leitura")
    if not r:
        return None
    return {"noticias": r["grupos"], "eventos": r["eventos"] + r["corporativo"] + r["cripto"], "impactos": r["impactos"], "sentimento": r["sentimento"], "carteira": r["carteira"],
            "historico": r["historico"], "ativos": r["ativos"], "gerado_em": r["quando"]}


def _ctx_risco() -> dict | None:
    """Resultado do último cálculo da página Risco (Passo 16), se existir nesta sessão. Só leitura."""
    col = _ss().get("_risco_coleta")
    if not col:
        return None
    try:
        import risco_app
        c = risco_app.contexto_ia(col)
        return c if c and (c.get("carteira") or {}).get("ok") else None
    except Exception:
        return None


def _ctx_relatorios() -> dict | None:
    """Resultados do último relatório calculado na página Relatórios (Passo 19), se houver nesta sessão. Só leitura."""
    try:
        import relatorios_app
        return relatorios_app.contexto_ia()
    except Exception:
        return None


def _ctx_comparador() -> dict | None:
    """Última comparação de desempenho calculada na página Comparar (Passo 20), se houver nesta sessão. Só leitura."""
    try:
        c = st.session_state.get("_cmp_ctx")
        return c if c and len(c.get("ativos") or []) >= 2 else None
    except Exception:
        return None


def _ctx_simulador() -> dict | None:
    """Resultados da última simulação feita no Simulador financeiro (Passo 18), se houver nesta sessão. Só leitura."""
    try:
        import simulador_app
        return simulador_app.contexto_ia()
    except Exception:
        return None


def riscos_noticiados() -> list[str]:
    r = _ss().get("_ne_leitura")
    return list(((r or {}).get("carteira") or {}).get("riscos") or [])[:8]


def contexto_assistente(res: dict) -> dict:
    return {"gerado_em": res["quando"], "ativos": res["ativos"], "carteira": res.get("carteira"), "noticias": res["noticias"],
            "mudancas": res["mudancas"], "alertas": res.get("alertas") or [],
            "tecnica": {a["id"]: a["tecnica"] for a in res["ativos"] if a.get("tecnica")}, "carteira_tecnica": _ss().get("_tec_cart")}


# =============================================================================== telas
def _cab(res):
    idade = _idade_h(res)
    velho = idade is not None and idade > VALIDADE_H
    q = res["quando"][:16]
    quando = f"{q[8:10]}/{q[5:7]} {q[11:16]}"
    ok = [a for a in res["ativos"] if not a["erro"]]
    _cartoes([("Ativos lidos", f"{len(ok)} de {len(res['ativos'])}", "info", "com dados suficientes"),
              ("Leitura de", quando, "bad" if velho else "good", "desatualizada: atualize" if velho else f"há {idade:.1f} h" if idade is not None else ""),
              ("Merecem estudo", str(sum(1 for a in ok if a["status"] == "merece_estudo")), "good", "evidências em vários critérios"),
              ("Com bandeiras", str(sum(1 for a in ok if a["bandeiras"])), "bad" if any(a["bandeiras"] for a in ok) else "good", "riscos que pedem atenção")])
    for a in res["avisos"]:
        st.caption("⚠️ " + a)
    fn = res.get("fontes_noticias") or {}
    if fn.get("erro"):
        st.caption(f"⚠️ Notícias: {fn['erro']} consulta(s) falharam ({fn.get('detalhe')}). As demais análises não dependem delas.")


def _aba_oportunidades(res):
    ok = [a for a in res["ativos"] if not a["erro"]]
    st.caption("Um ativo só aparece como “Merece estudo” quando ao menos 3 critérios diferentes são favoráveis e não há bandeira de risco. "
               "É um ponto de partida para estudar, não uma recomendação.")
    classes = [c for c in I.CLASSES_TODAS if any(a["classe"] == c for a in ok)]
    if not ok:
        st.info("Nenhum ativo com dados. Verifique as mensagens acima ou tente atualizar de novo.")
        return
    filtro = st.segmented_control("Classe", ["Todas"] + [I.ROTULO_CLASSE[c] for c in classes], default="Todas", key="intel_f_classe") or "Todas"
    status_f = st.multiselect("Situação", list(I.ROTULO_STATUS.values()), default=[I.ROTULO_STATUS["merece_estudo"], I.ROTULO_STATUS["sinais_parciais"]],
                              key="intel_f_status")
    linhas = []
    for a in ok:
        if filtro != "Todas" and I.ROTULO_CLASSE[a["classe"]] != filtro:
            continue
        if I.ROTULO_STATUS[a["status"]] not in status_f:
            continue
        op = a["oportunidade"]
        linhas.append({"Ativo": a["id"], "Classe": I.ROTULO_CLASSE.get(a["classe"], a["classe"]), "Situação": op["rotulo"],
                       "Nota": a["nota"], "Critérios favoráveis": ", ".join(op["favoraveis"][:5]) or "—",
                       "Atenção": ", ".join(op["desfavoraveis"][:3] + op["bandeiras"][:1]) or "—", "Dados até": a["data_ref"] or "n/d"})
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch",
                     column_config={"Nota": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f")})
    else:
        st.info("Nenhum ativo com essa situação e essa classe. Mude os filtros acima.")
    with st.expander("Como a leitura é feita, por classe"):
        for c in classes:
            st.markdown(f"**{I.ROTULO_CLASSE[c]}:** {I.FILTROS_CLASSE.get(c, '')}")
        st.markdown(f"Critério favorável: nota do pilar ≥ {I.LIM_FAVORAVEL:.0f}. Bandeira: pilar ≤ {I.LIM_BANDEIRA:.0f} só entra como “desfavorável”; "
                    "bandeira de risco vem de prejuízo, alavancagem alta, fluxo de caixa negativo, anomalia grave ou do seu perfil de risco.")
    sel = st.selectbox("Ver o detalhe de um ativo", [a["id"] for a in ok], key="intel_det_ativo")
    if sel:
        _detalhe(next(a for a in ok if a["id"] == sel))


def _detalhe(a: dict):
    op = a["oportunidade"]
    st.markdown(f"##### {a['id']} · {a['nome']}")
    st.markdown(f"**{op['rotulo']}.** {op['texto']}")
    if a["pilares"]:
        st.dataframe(pd.DataFrame([{"Critério": k, "Nota": v} for k, v in a["pilares"].items()]), hide_index=True, width="stretch",
                     column_config={"Nota": st.column_config.ProgressColumn(min_value=0, max_value=100, format="%.0f")})
    if a["achados"]:
        st.markdown("**Fundamentos (diagnóstico do Passo 7):**")
        for x in a["achados"]:
            st.markdown(f"- {'✅' if x['tom'] == 'positivo' else '⚠️' if x['tom'] == 'atencao' else '•'} {_md(x['titulo'])}: {_md(x['texto'])}")
    t = a["tendencia"]
    if t.get("rotulo"):
        st.caption(f"Tendência de preço (120 pregões): {t['rotulo']}, inclinação {I._br(t['inclinacao_aa'])}% a.a., R² {I._br(t['r2'], 2)}. "
                   "É descrição do passado, não previsão.")
    st.caption(f"Fonte: {a['fonte'] or 'n/d'} · dados até {a['data_ref'] or 'n/d'} · analisado em {a['analisado_em'][:16].replace('T', ' ')}"
               + (" · nota provisória (poucos critérios com dado)" if a["provisoria"] else ""))
    for av in a["avisos"][:4]:
        st.caption("⚠️ " + _md(av))


def _aba_riscos(res):
    ok = [a for a in res["ativos"] if not a["erro"]]
    st.caption("Anomalias são desvios ESTATÍSTICOS (não confirmados). Só viram evento quando há notícia ou alerta com fonte, e mesmo assim a coincidência não prova causa.")
    linhas = []
    for a in ok:
        for b in a["bandeiras"]:
            linhas.append({"Ativo": a["id"], "Tipo": "Bandeira de risco", "Gravidade": "alta", "O que foi visto": b, "Natureza": "regra sobre dado (balanço, preço ou seu perfil)", "Data": a["data_ref"] or ""})
        for x in a["anomalias"]:
            if x.get("sentido") == "negativo":
                linhas.append({"Ativo": a["id"], "Tipo": x["tipo"].replace("_", " "), "Gravidade": x["gravidade"], "O que foi visto": x["texto"],
                               "Natureza": x.get("status") or x["natureza"], "Data": x.get("data") or ""})
        for txt in riscos_tecnicos(a):
            linhas.append({"Ativo": a["id"], "Tipo": "análise técnica", "Gravidade": "media", "O que foi visto": txt,
                           "Natureza": "indicadores sobre o histórico de preços (Passo 14)", "Data": (a["tecnica"].get("ate") or "")[:10]})
        for x in a["achados"]:
            if x["tom"] == "atencao":
                linhas.append({"Ativo": a["id"], "Tipo": "fundamentos", "Gravidade": "media", "O que foi visto": f"{x['titulo']}: {x['texto']}",
                               "Natureza": "diagnóstico dos balanços anuais (Yahoo)", "Data": a["resultado"] or ""})
    ordem = {"alta": 0, "media": 1, "baixa": 2}
    linhas.sort(key=lambda r: (ordem.get(r["Gravidade"], 3), r["Ativo"]))
    if linhas:
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    else:
        st.success("Nenhuma bandeira, anomalia negativa ou sinal de deterioração nos ativos lidos. Isso não elimina riscos que os dados não mostram.")
    pos = [(a["id"], x) for a in ok for x in a["anomalias"] if x.get("sentido") == "positivo"]
    if pos:
        with st.expander(f"Anomalias de alta ({len(pos)})"):
            for tk, x in pos:
                st.markdown(f"- **{tk}**: {_md(x['texto'])} *({_md(x['natureza'])})*")
    rn = riscos_noticiados()
    if rn:
        with st.expander(f"Riscos noticiados nas posições ({len(rn)}) — Central de notícias"):
            for t in rn:
                st.markdown("- " + _md(t))
    sem = [a["id"] for a in res["ativos"] if a["erro"]]
    if sem:
        st.caption("Sem dados agora (não analisados): " + ", ".join(sem))
    st.caption("Riscos de crédito, liquidez e câmbio da carteira inteira ficam em Gestão de carteira → Risco.")


def _aba_noticias(res):
    nots = [n for n in res["noticias"]]
    st.caption("Títulos, fontes e datas vêm do RSS do Google Notícias, sem texto completo. O tom é uma leitura aproximada por palavras e "
               "NÃO prevê preço. Clique na fonte original para ler. Conteúdo suspeito é ocultado.")
    if not nots:
        st.info("Nenhuma notícia relevante nas fontes consultadas (ou o serviço de notícias não respondeu agora).")
        return
    c1, c2, c3 = st.columns(3)
    nivel = c1.selectbox("Relevância mínima", ["media", "alta", "baixa"], key="intel_n_nivel")
    cats = c2.multiselect("Categorias", list(I.CATEGORIAS_NOTICIA), key="intel_n_cats")
    tom = c3.selectbox("Tom", ["todos", "positivo", "negativo", "neutro"], key="intel_n_tom")
    lim = {"baixa": 0, "media": 35, "alta": 60}[nivel]
    ocultas = sum(1 for n in nots if n.get("conteudo_suspeito"))
    mostrar = [n for n in nots if n["relevancia"] >= lim and not n.get("conteudo_suspeito") and (not cats or set(cats) & set(n["categorias"]))
               and (tom == "todos" or n["tom"] == tom)]
    mostrar.sort(key=lambda n: (-n["relevancia"], n.get("data") or ""))
    for n in mostrar[:25]:
        icone = {"positivo": "🟢", "negativo": "🔴", "neutro": "⚪"}[n["tom"]]
        alvo = n.get("ativo") or "Mercado"
        link = f" · [fonte original]({n['url']})" if n.get("url") else ""
        st.markdown(f"{icone} **{_md(alvo)}** · {_md(n['titulo'])}{link}")
        extra = f" · {n['repetidas']} repetida(s) agrupada(s) ({_md(', '.join(n['fontes'][:3]))})" if n.get("repetidas") else ""
        alt = " · **pode alterar fundamentos**" if n.get("pode_alterar_fundamentos") else ""
        st.caption(f"{_md(n['fonte'])} · {(n.get('data') or 'data n/d')[:10]} · relevância {n['nivel']} ({n['relevancia']}) · "
                   f"{', '.join(n['categorias']) or 'sem categoria'}{alt}{extra}")
    if not mostrar:
        st.info("Nenhuma notícia com esses filtros.")
    if ocultas:
        st.caption(f"{ocultas} notícia(s) com texto de aparência suspeita (tentando dar ordens ao sistema) foram ocultadas e não entram em alertas nem no assistente.")


def _padroes_alerta():
    return [I.nova_regra("variacao_preco", "*", {"limite_pct": 5, "direcao": "queda", "janela": "1d"}, "alta"),
            I.nova_regra("risco", "*", {"gravidade_min": "alta"}, "alta"),
            I.nova_regra("noticia", "*", {"relevancia_min": 60}, "media"),
            I.nova_regra("vencimento_rf", "*", {"dias": 30}, "media"),
            I.nova_regra("carteira", "*", {"tipo": "concentracao_max", "limite": 25}, "media"),
            I.nova_regra("dividendo", "*", {"limite_pct": 25}, "baixa")]


def _add_regra():
    ss = _ss()
    tipo = ss.get("intel_r_tipo")
    ativo = (ss.get("intel_r_ativo") or "*").strip() or "*"
    pri = {"Alta": "alta", "Média": "media", "Baixa": "baixa"}.get(ss.get("intel_r_pri", "Média"), "media")
    num = float(ss.get("intel_r_num") or 0)
    params = {"variacao_preco": {"limite_pct": num, "direcao": ss.get("intel_r_dir", "ambas"), "janela": "1d"},
              "nivel_preco": {"nivel": num, "sentido": ss.get("intel_r_sent", "acima")},
              "dividendo": {"limite_pct": num}, "volatilidade": {"razao": num}, "noticia": {"relevancia_min": num},
              "risco": {"gravidade_min": "media"}, "liquidez": {"alta_x": num or 3}, "desbloqueio": {"dias": num}, "vencimento_rf": {"dias": num},
              "resultado": {}, "indicador": {"campo": (ss.get("intel_r_campo") or "pvp").strip(), "op": ss.get("intel_r_op", "<="), "valor": num},
              "carteira": {"tipo": "concentracao_max", "limite": num}}.get(tipo, {})
    try:
        r = I.nova_regra(tipo, ativo, params, pri)
    except ValueError:
        return
    regras = [x for x in (ss.get(CH_REGRAS) or []) if x["id"] != r["id"]]
    ss[CH_REGRAS] = regras + [r]


def _rm_regra(rid: str):
    _ss()[CH_REGRAS] = [r for r in (_ss().get(CH_REGRAS) or []) if r["id"] != rid]


def _aba_alertas(res):
    ss = _ss()
    st.caption("Alertas aparecem aqui quando você atualiza a leitura. Não há envio por e-mail ou push. Para não repetir, o mesmo alerta só volta depois do "
               "período de frequência escolhido em Preferências (ou se o valor mudar de faixa).")
    novos = res.get("alertas") or []
    if novos:
        st.markdown(f"#### Novos nesta leitura ({len(novos)})")
        for a in novos:
            icone = {"alta": "🔴", "media": "🟠", "baixa": "🟡"}[a["prioridade"]]
            st.markdown(f"{icone} **{_md(a['titulo'])}** — {_md(a['texto'])}")
    else:
        st.info("Nenhum alerta novo nesta leitura." + (f" {res['suprimidos']} repetido(s) suprimido(s)." if res.get("suprimidos") else ""))
    regras = ss.get(CH_REGRAS) or []
    st.markdown("#### Suas regras")
    if not regras:
        st.caption("Você ainda não criou regras.")
        if st.button("Criar regras sugeridas", key="intel_regras_sug", icon=":material/notifications_active:"):
            ss[CH_REGRAS] = _padroes_alerta()
            st.rerun()
    for r in regras:
        c1, c2, c3 = st.columns([5, 2, 1])
        c1.markdown(f"**{I.TIPOS_ALERTA[r['tipo']]}** · {_md(r['ativo'] if r['ativo'] != '*' else 'todos os ativos')} · {_md(', '.join(f'{k}={v}' for k, v in r['params'].items()) or 'sem parâmetros')}")
        c2.caption(f"prioridade {r['prioridade']}")
        c3.button("Remover", key=f"intel_rm_{r['id']}", on_click=_rm_regra, args=(r["id"],))
    with st.expander("Nova regra", icon=":material/add_alert:"):
        c1, c2 = st.columns(2)
        c1.selectbox("Tipo", list(I.TIPOS_ALERTA), key="intel_r_tipo", format_func=lambda t: I.TIPOS_ALERTA[t])
        c2.text_input("Ativo (código ou * para todos)", key="intel_r_ativo", **_padrao("intel_r_ativo", "*"))
        c3, c4 = st.columns(2)
        c3.number_input("Valor do limite (%, nível, dias, razão ou relevância, conforme o tipo)", key="intel_r_num", step=1.0, **_padrao("intel_r_num", 5.0))
        c4.selectbox("Prioridade", ["Alta", "Média", "Baixa"], key="intel_r_pri", index=1)
        c5, c6, c7 = st.columns(3)
        c5.selectbox("Direção (variação)", ["queda", "alta", "ambas"], key="intel_r_dir")
        c6.selectbox("Sentido (nível de preço)", ["acima", "abaixo"], key="intel_r_sent")
        c7.text_input("Indicador (para tipo Indicador)", key="intel_r_campo", **_padrao("intel_r_campo", "pvp"))
        st.selectbox("Operador (indicador)", ["<=", ">=", "<", ">"], key="intel_r_op")
        st.button("Adicionar regra", key="intel_r_add", on_click=_add_regra, icon=":material/add:")
        st.caption("Campos de indicador: os da tabela de cada ativo (ex.: pvp, dy, vol, ret12m, nota). Regra sem dado do ativo simplesmente não dispara.")
    hist = ss.get(CH_HIST) or []
    if hist:
        with st.expander(f"Histórico de alertas ({len(hist)})"):
            for h in reversed(hist[-40:]):
                st.markdown(f"- {h['quando'][:16].replace('T', ' ')} · **{_md(h['titulo'])}** ({h['prioridade']})")
            st.button("Limpar histórico", key="intel_hist_limpar", on_click=lambda: _ss().__setitem__(CH_HIST, []))


def _tabela_ranking(rk: dict):
    st.markdown(f"**{rk['titulo']}**")
    st.caption(f"Critérios: {rk['criterios']} · atualização: {rk['atualizacao'] or 'n/d'}" + (f" · prioridades suas aplicadas: {', '.join(rk['prioridades_aplicadas'])}" if rk.get("prioridades_aplicadas") else ""))
    linhas = []
    for i in rk["itens"]:
        if "nota" in i:
            linhas.append({"#": i["posicao"], "Ativo": i["id"], "Nota": i["nota"], "Cobertura (%)": (i["cobertura"] or 0) * 100,
                           "Principais riscos": ("; ".join(i.get("riscos") or [])[:140] or "—"), "Justificativa": i["justificativa"],
                           "Dados até": i.get("data_ref") or "n/d"})
        else:
            linhas.append({"#": i["posicao"], "Ativo": i["id"], "Valor": i["valor"], "Principais riscos": ("; ".join(i.get("riscos") or [])[:140] or "—"),
                           "Justificativa": i["justificativa"], "Dados até": i.get("data_ref") or "n/d"})
    st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
    if rk.get("sem_dado"):
        st.caption("Sem o dado (fora do ranking): " + ", ".join(rk["sem_dado"]))
    st.caption(rk["aviso"])


def montar_rankings(res: dict) -> dict:
    ok = [a for a in res["ativos"] if not a["erro"]]
    p = prefs()
    out = {}
    for c in I.CLASSES_TODAS:
        itens = [a for a in ok if a["classe"] == c]
        if itens:
            out[c] = I.montar_ranking(itens, c, prefs=p)
    temas = {}
    acoes = [a for a in ok if a["classe"] == "acao"]
    if any(a["ind"].get("saldo_fundamentos") is not None for a in acoes):
        temas["acao_fundamentos"] = I.ranking_por_valor(acoes, "acao", "saldo_fundamentos", "Ações com fundamentos em melhora", False,
                                                         "Sinais de melhora menos sinais de atenção no diagnóstico de balanços")
    fiis = [a for a in ok if a["classe"] == "fii"]
    if any(a["ind"].get("pilar_renda") is not None for a in fiis):
        temas["fii_renda"] = I.ranking_por_valor(fiis, "fii", "pilar_renda", "FIIs com renda mais consistente", False, "Nota do pilar Renda (0–100)")
    etfs = [a for a in ok if a["classe"] == "etf"]
    temas["etf_custo"] = I.ranking_por_valor(etfs, "etf", "taxa_adm", "ETFs de menor custo", True, "Taxa de administração", "% a.a.") if etfs else None
    crip = [a for a in ok if a["classe"] == "cripto"]
    temas["cripto_uso"] = I.ranking_por_valor(crip, "cripto", "tvl", "Criptomoedas com maior utilização (TVL)", False, "TVL em US$") if crip else None
    out["_temas"] = {k: v for k, v in temas.items() if v and v["itens"]}
    return out


def _aba_rankings(res):
    rks = montar_rankings(res)
    st.caption("Cada ranking compara só ativos da MESMA classe, com a régua própria dela. Nota é triagem educacional, não ordem de compra.")
    classes = [c for c in I.CLASSES_TODAS if c in rks]
    if not classes:
        st.info("Nenhum ativo com dados para ranquear. Adicione favoritos ou posições e atualize a leitura.")
        return
    c = st.radio("Classe", classes, format_func=lambda x: I.ROTULO_CLASSE[x], horizontal=True, key="intel_rk_classe")
    _tabela_ranking(rks[c])
    if len(rks[c]["itens"]) < 2:
        st.caption("Só há um ativo desta classe na leitura: adicione outros aos favoritos para formar um ranking.")
    temas = rks["_temas"]
    if temas:
        st.markdown("#### Rankings temáticos")
        for t in temas.values():
            _tabela_ranking(t)
    elif any(a["classe"] == "etf" for a in res["ativos"]):
        st.caption("Ranking de custo de ETFs indisponível: a taxa de administração ainda não tem fonte integrada.")


def _aba_monitoramento(res):
    st.caption("Compara esta leitura com a de outro dia. Guarda só nota, preço e sinais (nunca quantidades nem valores da carteira).")
    ms = res.get("mudancas") or []
    if ms:
        for m in ms:
            st.markdown(f"{'🟢' if m['sentido'] == 'positivo' else '🔴'} **{_md(m['ativo'])}** — {_md(m['texto'])}")
    else:
        st.info("Nenhuma mudança relevante desde a leitura anterior (ou esta é a primeira leitura; o app guarda uma por dia).")
    c = res.get("carteira")
    st.markdown("#### Carteira")
    if c:
        _cartoes([("Maior posição", f"{I._br(c['maior_peso'])}%" if I._ok(c.get("maior_peso")) else "n/d", "bad" if (c.get("maior_peso") or 0) > 25 else "good", c.get("maior_ativo") or ""),
                  ("Posições efetivas", I._br(c.get("n_efetivo")), "info", "número efetivo de apostas"),
                  ("Correlação média", I._br(c.get("corr_media"), 2), "info", "entre os ativos, ponderada"),
                  ("Leitura de", c["data"], "info", "Gestão de carteira (Passo 12)")])
        st.markdown(_md(c["resumo"]))
        for t in c.get("pontos", [])[:8]:
            st.markdown(f"- {_md(t)}")
    else:
        st.caption("Sem carteira para monitorar: registre posições em Carteira.")
    prov = [a for a in res["ativos"] if I._ok(a.get("div_var_pct"))]
    if prov:
        st.markdown("#### Dividendos e rendimentos")
        st.dataframe(pd.DataFrame([{"Ativo": a["id"], "Proventos 12m vs 12m anteriores (%)": a["div_var_pct"]} for a in prov]), hide_index=True, width="stretch")
        st.caption("Fonte: histórico de proventos do Yahoo Finance (data com, não a data de pagamento).")
    st.markdown("#### Quem acompanha")
    st.dataframe(pd.DataFrame([{"Ativo": a["id"], "Classe": I.ROTULO_CLASSE.get(a["classe"], a["classe"]), "Origem": ", ".join(a["origem"]) or "—",
                                "Situação": a["oportunidade"]["rotulo"] if not a["erro"] else "sem dados", "Nota": a["nota"],
                                "Tendência": (a["tendencia"] or {}).get("rotulo") or "—"} for a in res["ativos"]]), hide_index=True, width="stretch")


def _aba_previsoes(res):
    p = prefs()
    st.caption("Cenários probabilísticos do histórico de preços, com premissas, período, método, limites e intervalo de incerteza. "
               "NÃO é previsão e não promete acerto.")
    cand = [a["id"] for a in res["ativos"] if not a["erro"] and a["classe"] in ("acao", "bdr", "fii", "etf") and a["preco"]]
    if not cand:
        st.info("Preciso de um ativo de bolsa com histórico de preços para projetar (ações, BDRs, FIIs ou ETFs).")
        return
    tk = st.selectbox("Ativo", cand, key="intel_prev_ativo")
    h = I.HORIZONTES[p["horizonte"]]
    dias = st.selectbox("Horizonte (pregões à frente)", [21, 63, 126, 252], key="intel_prev_dias", **_opt("intel_prev_dias", "index", [21, 63, 126, 252].index(h)))
    ps = evolucao.coletar_precos(tk)["preco"]
    cond = {"Calmaria (volatilidade ×0,7)": 0.7, "Histórico (×1)": 1.0, "Estresse (volatilidade ×1,5)": 1.5}
    proj = {k: I.projecao_preco(ps, dias, escala_vol=v) for k, v in cond.items()}
    base = proj["Histórico (×1)"]
    if not base["ok"]:
        st.warning(f"Sem projeção: {base['motivo']}")
    else:
        q = base["percentis"]
        _cartoes([("Preço de hoje", f"{base['p0']:.2f}", "info", f"dados até {base['periodo'][1]}"),
                  ("Faixa de 90%", f"{q[5]:.2f} a {q[95]:.2f}", "info", f"em {dias} pregões"),
                  ("Faixa central (50%)", f"{q[25]:.2f} a {q[75]:.2f}", "info", "quartis 25–75"),
                  ("Chance de ficar abaixo de hoje", f"{base['prob_abaixo'] * 100:.0f}%", "fair", "no modelo, sem tendência")], por_linha=2)
        linhas = [{"Condição de mercado": k, "5%": v["percentis"][5], "25%": v["percentis"][25], "Mediana": v["percentis"][50], "75%": v["percentis"][75],
                   "95%": v["percentis"][95], "Chance abaixo de hoje (%)": v["prob_abaixo"] * 100} for k, v in proj.items() if v["ok"]]
        st.dataframe(pd.DataFrame(linhas), hide_index=True, width="stretch")
        fig = go.Figure()
        for k, v in proj.items():
            if v["ok"]:
                fig.add_trace(go.Scatter(x=["5%", "25%", "50%", "75%", "95%"], y=[v["percentis"][i] for i in (5, 25, 50, 75, 95)], mode="lines+markers", name=k))
        fig.update_layout(height=320, yaxis_title="Preço possível", legend={"orientation": "h", "y": -0.25}, **TRANSP)
        st.plotly_chart(fig, width="stretch", key="intel_prev_fig", config={"displayModeBar": False})
        with st.expander("Premissas, método e limitações"):
            st.markdown(f"**Método:** {base['metodo']}. **Período analisado:** {base['periodo'][0]} a {base['periodo'][1]} ({base['periodo'][2]} pregões).")
            for t in base["premissas"]:
                st.markdown(f"- {t}")
            for t in base["limitacoes"]:
                st.markdown(f"- ⚠️ {t}")
    t = next((a["tendencia"] for a in res["ativos"] if a["id"] == tk), {})
    if t.get("rotulo"):
        st.markdown(f"**Tendência observada:** {t['rotulo']} (inclinação {I._br(t['inclinacao_aa'])}% a.a., R² {I._br(t['r2'], 2)}, t={I._br(t['t'], 1)}). "
                    f"{'Acima' if t.get('acima_mm200') else 'Abaixo'} da média de 200 pregões.")
    try:
        df = evolucao.coletar_demonstrativos(tk)["anual"]
    except Exception:
        df = pd.DataFrame()
    for col in ("Receita líquida", "Lucro líquido"):
        if df is not None and col in df:
            pi = I.projetar_indicador(df[col].dropna())
            if pi["ok"]:
                st.markdown(f"**{col} (projeção linear, 2 exercícios):** " + "; ".join(
                    f"+{x['passo']} ano: {x['estimativa'] / 1e9:,.2f} bi (faixa {x['inferior'] / 1e9:,.2f} a {x['superior'] / 1e9:,.2f})" for x in pi["projecao"]))
            else:
                st.caption(f"{col}: sem projeção ({pi['motivo']})")
    st.caption(I.AVISO_LEGAL)


def _aba_assistente(res):
    ss = _ss()
    st.caption("O assistente responde só com os dados já lidos nesta central (cada resposta diz o que foi consultado e a data). "
               "Não recomenda compra ou venda e não inventa o que não está nos dados.")
    cols = st.columns(2)
    for i, s in enumerate(SUGESTOES):
        if cols[i % 2].button(s, key=f"intel_sug_{i}"):
            ss["intel_q"] = s
    q = st.text_input("Pergunte sobre seus ativos", key="intel_q", max_chars=300, **_padrao("intel_q", ""))
    if q and q.strip():
        ctx = contexto_assistente(res)
        cn = _ctx_noticias()
        if T.eh_pergunta_tecnica(q.strip()):
            r = T.responder_tecnica(q.strip(), ctx)
        elif REL_IA.eh_pergunta_relatorio(q.strip()) and (cl_ := _ctx_relatorios()):
            r = REL_IA.responder_relatorio(q.strip(), cl_)
        elif CMP_IA.eh_pergunta_comparacao(q.strip()) and (cc_ := _ctx_comparador()):
            r = CMP_IA.responder_comparacao(q.strip(), cc_)
            r = {**r, "linhas": [f"{t} · {x}" for sec in r.get("secoes", []) for t, x in sec["linhas"]], "referencia": f"Comparação calculada em {str(r.get('gerado_em') or '')[:16].replace('T', ' ')}",
                 "consultado": "Consultei: a última comparação da página Comparar.", "fontes": r.get("fontes") or []}
        elif SIM_IA.eh_pergunta_simulador(q.strip()) and (cs_ := _ctx_simulador()):
            r = SIM_IA.responder_simulador(q.strip(), cs_)
        elif RK.eh_pergunta_risco(q.strip()) and (cr_ := _ctx_risco()):
            r = RK.responder_risco(q.strip(), cr_)
        elif cn and NE.eh_pergunta_noticia(q.strip()):
            r = NE.responder_noticias(q.strip(), cn)
            if r.get("sem_dados"):
                r = I.responder(q.strip(), ctx)
        else:
            r = I.responder(q.strip(), ctx)
        import comparador_app as CMP_APP
        CMP_APP.resposta_em_cards(r, st)
        st.caption(f"{r['referencia']}. {r['consultado']} {r['limite']}")


def _aba_relatorio(res):
    md = I.relatorio_markdown(contexto_assistente(res))
    st.markdown(md)
    st.download_button("Baixar relatório (Markdown)", md.encode("utf-8"), file_name=f"relatorio_inteligencia_{date.today():%Y%m%d}.md",
                       mime="text/markdown", key="intel_dl")


def _opt(chave: str, nome: str, valor) -> dict:
    """Valor inicial só na primeira vez: com a chave já na sessão, passar default/index de novo faz o Streamlit avisar ou reiniciar o widget."""
    return {} if chave in st.session_state else {nome: valor}


_CAMPOS_PREFS = {"intel_p_classes": "classes", "intel_p_risco": "risco", "intel_p_hor": "horizonte", "intel_p_pil": "pilares_prioritarios",
                 "intel_p_tipos": "tipos_alerta", "intel_p_freq": "frequencia", "intel_p_bench": "benchmarks"}


def _salvar_prefs():
    """Lê os campos da aba Preferências e grava as preferências validadas. Roda como on_change (antes de redesenhar a página)."""
    ss = _ss()
    novo = dict(I.normalizar_prefs(ss.get(CH_PREFS)))
    for k, campo in _CAMPOS_PREFS.items():
        if k in ss:
            novo[campo] = ss[k]
    if "intel_p_fav" in ss:
        novo["favoritos"] = [x for x in re.split(r"[,\s;]+", ss["intel_p_fav"] or "") if x]
    ss[CH_PREFS] = I.normalizar_prefs(novo)


def _aba_preferencias():
    p = prefs()
    st.caption("A leitura respeita estas escolhas: classes lidas, favoritos, seu perfil de risco (limites de volatilidade e queda), horizonte, "
               "critérios prioritários nos rankings, tipos de alerta, frequência e referências de comparação.")
    c1, c2 = st.columns(2)
    c1.multiselect("Classes de interesse", I.CLASSES_TODAS, key="intel_p_classes", format_func=lambda x: I.ROTULO_CLASSE[x],
                   on_change=_salvar_prefs, **_opt("intel_p_classes", "default", p["classes"]))
    c2.text_input("Ativos favoritos (códigos separados por vírgula)", key="intel_p_fav", on_change=_salvar_prefs,
                  **_padrao("intel_p_fav", ", ".join(p["favoritos"])))
    c3, c4 = st.columns(2)
    c3.selectbox("Nível de risco desejado", list(I.LIMITES_RISCO), key="intel_p_risco", on_change=_salvar_prefs,
                 **_opt("intel_p_risco", "index", list(I.LIMITES_RISCO).index(p["risco"])))
    c4.selectbox("Horizonte de investimento", list(I.HORIZONTES), key="intel_p_hor", on_change=_salvar_prefs,
                 **_opt("intel_p_hor", "index", list(I.HORIZONTES).index(p["horizonte"])))
    st.multiselect("Indicadores (pilares) prioritários", sorted(PILARES_CONHECIDOS), key="intel_p_pil", on_change=_salvar_prefs,
                   **_opt("intel_p_pil", "default", [x for x in p["pilares_prioritarios"] if x in PILARES_CONHECIDOS]))
    c5, c6 = st.columns(2)
    c5.multiselect("Tipos de alerta ativos (vazio = todos)", list(I.TIPOS_ALERTA), key="intel_p_tipos", format_func=lambda x: I.TIPOS_ALERTA[x],
                   on_change=_salvar_prefs, **_opt("intel_p_tipos", "default", p["tipos_alerta"]))
    c6.selectbox("Frequência das notificações", list(I.FREQUENCIAS), key="intel_p_freq", format_func=lambda x: I.ROTULO_FREQ[x],
                 on_change=_salvar_prefs, **_opt("intel_p_freq", "index", list(I.FREQUENCIAS).index(p["frequencia"])))
    bench = ["CDI", "Ibovespa", "IPCA", "Dólar", "S&P 500"]
    st.multiselect("Referências de comparação", bench, key="intel_p_bench", on_change=_salvar_prefs,
                   **_opt("intel_p_bench", "default", [b for b in p["benchmarks"] if b in bench]))
    _salvar_prefs()
    st.caption("As preferências ficam salvas no seu perfil (se você estiver logado). A leitura só muda quando você atualiza.")
    with st.expander("O que ainda depende de novas fontes (limites desta versão)"):
        for t in SEM_FONTE:
            st.markdown(f"- {t}")


def pagina_intel(coletor, perfil: str = "Moderado"):
    st.markdown(tema.cabecalho("🧭", "Central de inteligência", "Oportunidades para estudar, riscos, notícias, alertas, rankings e o que mudou nos ativos que você acompanha."),
                unsafe_allow_html=True)
    p = prefs()
    u = universo(p)
    n = len(u["codigos"]) + len(u["criptos"])
    c1, c2 = st.columns([1, 3])
    clicou = c1.button("Atualizar leitura", key="intel_atualizar", type="primary", icon=":material/refresh:", disabled=n == 0)
    c2.caption(f"{n} ativo(s) acompanhado(s) (favoritos, carteira, renda fixa e cripto). Limite por leitura: {MAX_ATIVOS}. "
               "Clique para ler dados, notícias e carteira agora; as outras telas não são afetadas.")
    if n == 0:
        st.markdown(tema.vazio("busca", "Nada para acompanhar ainda", "Registre posições em Carteira ou escreva favoritos na aba Preferências (ex.: PETR4, HGLG11, BOVA11)."),
                    unsafe_allow_html=True)
    if clicou:
        with st.spinner("Lendo ativos, notícias e carteira..."):
            atualizar(coletor, perfil)
    res = leitura()
    abas = ["Oportunidades", "Riscos", "Notícias", "Alertas", "Rankings", "Monitoramento", "Previsões", "Assistente", "Relatório", "Preferências"]
    tabs = st.tabs(abas)
    with tabs[-1]:
        _aba_preferencias()
    if res is None:
        for t in tabs[:-1]:
            with t:
                st.info("Clique em “Atualizar leitura” para começar." if n else "Adicione ativos para acompanhar.")
        st.caption(I.AVISO_LEGAL)
        return
    with tabs[0]:
        _cab(res)
        _aba_oportunidades(res)
    for t, f in zip(tabs[1:-1], [_aba_riscos, _aba_noticias, _aba_alertas, _aba_rankings, _aba_monitoramento, _aba_previsoes, _aba_assistente, _aba_relatorio]):
        with t:
            f(res)
    st.caption(I.AVISO_LEGAL)


def painel_ativo(codigo: str, coletor, perfil: str = "Moderado", cripto: bool = False):
    """Bloco compacto para as páginas de cada ativo e da carteira: usa a leitura da central, se existir; senão oferece analisar só este ativo."""
    res = leitura()
    item = next((a for a in (res or {}).get("ativos", []) if a["id"].upper() == str(codigo).upper() and not a["erro"]), None)
    with st.expander("Inteligência: sinais, riscos e notícias deste ativo", icon=":material/psychology:"):
        if item is None:
            st.caption("Este ativo ainda não está na leitura da Central de inteligência.")
            if st.button("Analisar este ativo agora", key=f"intel_um_{codigo}"):
                try:
                    a = (coletor([], [codigo], perfil) if cripto else coletor([codigo], [], perfil))[0]
                    nt = I.processar_noticias(_noticias_rss(f"{codigo} when:14d")["itens"], codigo, None, _agora())
                    item = analisar_ativo(a, ["consulta"], [n for n in nt if n["relevancia"] >= 20][:5])
                    st.session_state[f"_intel_um_{codigo}"] = item
                except Exception as e:
                    st.warning(f"Não consegui analisar agora ({e.__class__.__name__}).")
            item = st.session_state.get(f"_intel_um_{codigo}")
            if item is None:
                return
        if item.get("erro"):
            st.warning(f"Sem dados agora: {item['erro']}")
            return
        _detalhe(item)
        for x in item["anomalias"]:
            st.markdown(f"- 📈 {_md(x['texto'])} *({_md(x.get('status') or x['natureza'])})*")
        for n in item["noticias"][:4]:
            if not n.get("conteudo_suspeito"):
                st.markdown(f"- 📰 {_md(I.resumo_noticia(n))}" + (f" [fonte]({n['url']})" if n.get("url") else ""))
        st.caption(I.AVISO_LEGAL)
