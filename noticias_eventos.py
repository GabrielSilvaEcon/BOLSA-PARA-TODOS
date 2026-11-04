"""Passo 15 — Central de notícias, eventos econômicos, calendários e análise de impacto (motor, sem tela e sem rede).

Separação de camadas: a COLETA (requests, cache) fica em noticias_app.py; aqui entram só os TEXTOS/JSON já baixados. Tudo que vem de fora é
tratado como dado não confiável: limpo, truncado e nunca executado; textos que tentam dar ordens ao sistema são marcados e ficam fora de
alertas e do assistente. Nada é inventado: sem fonte, sem dado — o resultado diz o que faltou.

Reaproveita o Passo 13 (intel.py): limpeza de texto, categorias, léxico de tom, relevância, alertas e filtro de repetição.
Fatos (a publicação existe; o calendário oficial diz a data; o indicador foi divulgado) ficam separados de INTERPRETAÇÕES (tom do texto,
exposição de um ativo a um acontecimento): estas dizem "pode", nunca "vai", e não preveem preço.
"""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

import pandas as pd

import intel as I

AVISO_LEGAL = ("Ferramenta educacional. Notícias, tom e impactos são leituras aproximadas de fontes públicas e regras simples: não preveem preço, "
               "não são recomendação e podem estar atrasadas ou incompletas. Confira sempre a fonte original.")


# =============================================================================== fontes e confiabilidade
# Domínios oficiais (órgãos reguladores, bancos centrais, estatística, bolsa) e veículos/agências reconhecidos (por nome, pois o Google Notícias
# entrega o NOME do veículo). Fonte fora das listas = "não verificada": entra, mas com aviso e peso menor.
DOMINIOS_OFICIAIS = {
    "bcb.gov.br": "Banco Central do Brasil", "gov.br": "Governo federal", "ibge.gov.br": "IBGE", "cvm.gov.br": "CVM", "b3.com.br": "B3",
    "tesourotransparente.gov.br": "Tesouro Nacional", "tesouro.gov.br": "Tesouro Nacional", "anbima.com.br": "ANBIMA", "federalreserve.gov": "Federal Reserve",
    "sec.gov": "SEC (EUA)", "bls.gov": "BLS (EUA)", "ecb.europa.eu": "Banco Central Europeu", "bankofengland.co.uk": "Banco da Inglaterra",
    "boj.or.jp": "Banco do Japão", "treasury.gov": "Tesouro dos EUA", "bea.gov": "BEA (EUA)", "imf.org": "FMI", "worldbank.org": "Banco Mundial",
}
NOMES_OFICIAIS = ["banco central do brasil", "banco central", "bcb", "ibge", "cvm", "b3", "tesouro nacional", "anbima", "federal reserve", "sec ",
                  "u.s. securities", "bls", "bureau of labor", "gov.br", "ministério da fazenda", "ministerio da fazenda"]
VEICULOS_RECONHECIDOS = ["reuters", "bloomberg", "valor", "infomoney", "folha", "estadão", "estadao", "o globo", "globo", "cnn", "exame", "financial times",
                         "wall street journal", "wsj", "cnbc", "associated press", "ap news", "bbc", "agência estado", "agencia estado", "broadcast", "money times",
                         "moneytimes", "istoé dinheiro", "istoe dinheiro", "forbes", "g1", "uol", "veja", "suno", "seu dinheiro", "investing.com", "marketwatch",
                         "yahoo finance", "agência brasil", "agencia brasil", "coindesk", "cointelegraph", "the block", "decrypt", "bitcoin.com", "livecoins", "portal do bitcoin", "criptofacil"]


def _host(url) -> str:
    try:
        return (urlparse(str(url or "")).hostname or "").lower().removeprefix("www.")
    except Exception:
        return ""


def nivel_fonte(fonte: str | None, url: str | None = None, fonte_url: str | None = None) -> dict:
    """{'nivel': 'oficial'|'veiculo'|'nao_verificada', 'nome'}. Domínio oficial (do link ou do atributo da fonte) ou nome oficial → oficial."""
    for u in (url, fonte_url):
        h = _host(u)
        for dom, nome in DOMINIOS_OFICIAIS.items():
            if h == dom or h.endswith("." + dom):
                return {"nivel": "oficial", "nome": nome}
    f = I._norm(fonte or "")
    if any(n in f for n in map(I._norm, NOMES_OFICIAIS)):
        return {"nivel": "oficial", "nome": (fonte or "").strip()[:60]}
    if any(v in f for v in map(I._norm, VEICULOS_RECONHECIDOS)):
        return {"nivel": "veiculo", "nome": (fonte or "").strip()[:60]}
    return {"nivel": "nao_verificada", "nome": (fonte or "fonte não informada").strip()[:60]}


ROTULO_NIVEL = {"oficial": "fonte oficial", "veiculo": "veículo reconhecido", "nao_verificada": "fonte não verificada"}


# =============================================================================== leitura de feeds (RSS, Atom, JSON do IBGE)
def _txt(el, *nomes) -> str:
    for n in nomes:
        for c in el:
            if c.tag.split("}")[-1] == n and (c.text or "").strip():
                return c.text
    return ""


def parse_feed(texto: str, max_itens: int = 40, fonte_padrao: str | None = None) -> list[dict]:
    """RSS 2.0 ou Atom → [{titulo, fonte, fonte_url, url, data, resumo}]. Entrada inválida, enorme ou com entidades externas → []."""
    if not texto or len(texto) > 3_000_000 or "<!ENTITY" in texto:
        return []
    try:
        raiz = ET.fromstring(texto)
    except ET.ParseError:
        return []
    itens = []
    for it in [e for e in raiz.iter() if isinstance(e.tag, str) and e.tag.split("}")[-1] in ("item", "entry")]:      # RSS 2.0, Atom e RSS 1.0 (com namespace)
        titulo = I._limpar_texto(_txt(it, "title"), I.MAX_TITULO)
        if not titulo:
            continue
        src = next((c for c in it if c.tag.split("}")[-1] == "source"), None)
        fonte = I._limpar_texto(src.text if src is not None else "", 60)
        fonte_url = I.url_segura(src.attrib.get("url")) if src is not None else None
        if fonte and titulo.endswith(" - " + fonte):
            titulo = titulo[: -len(fonte) - 3].strip()
        elif not fonte and " - " in titulo and not fonte_padrao:
            titulo, _, fonte = titulo.rpartition(" - ")
            fonte = fonte[:60]
        link = _txt(it, "link")
        if not link:
            for c in it:
                if c.tag.split("}")[-1] == "link" and c.attrib.get("href"):
                    link = c.attrib["href"]
                    break
        itens.append({"titulo": titulo, "fonte": fonte or fonte_padrao or "fonte não informada", "fonte_url": fonte_url, "url": I.url_segura(link),
                      "data": I._data_noticia(_txt(it, "pubDate", "published", "updated", "date")),
                      "resumo": I._limpar_texto(_txt(it, "description", "summary", "content"), I.MAX_RESUMO)})
        if len(itens) >= max_itens:
            break
    return itens


def _data_br(txt) -> str | None:
    """'dd/mm/aaaa [hh:mm[:ss]]' ou ISO → ISO (minutos). None se inválido."""
    if not txt:
        return None
    try:
        s = str(txt).strip()
        d = pd.to_datetime(s, dayfirst=not re.match(r"^\d{4}-", s))
        return d.tz_localize(None).isoformat(timespec="minutes") if getattr(d, "tzinfo", None) else d.isoformat(timespec="minutes")
    except Exception:
        return None


def parse_ibge_noticias(dados, max_itens: int = 30) -> list[dict]:
    """JSON de https://servicodados.ibge.gov.br/api/v3/noticias → notícias oficiais do IBGE. Formato inesperado → []."""
    try:
        itens = dados.get("items") if isinstance(dados, dict) else None
        out = []
        for x in itens or []:
            titulo = I._limpar_texto(x.get("titulo"), I.MAX_TITULO)
            link = I.url_segura(x.get("link"))
            if not titulo:
                continue
            out.append({"titulo": titulo, "fonte": "IBGE", "fonte_url": "https://www.ibge.gov.br", "url": link,
                        "data": _data_br(x.get("data_publicacao")), "resumo": I._limpar_texto(x.get("introducao"), I.MAX_RESUMO)})
            if len(out) >= max_itens:
                break
        return out
    except Exception:
        return []


# =============================================================================== normalização, qualidade e sentimento
ESPECULATIVO = ["rumor", "rumores", "boato", "boatos", "especula", "especulacao", "segundo fontes", "teria", "poderia", "pode ", "deve ", "avalia", "estuda", "cogita",
                "diz fonte", "fontes dizem", "reportedly", "rumour", "sources say", "may ", "could ", "might ", "alegedly", "supostamente", "aposta", "projeta", "preve"]
URGENTE = ["urgente", "ultima hora", "última hora", "breaking", "fato relevante", "comunicado ao mercado", "suspende negociacao", "suspensao das negociacoes",
           "intervencao", "liquidacao extrajudicial", "recuperacao judicial", "falencia", "calote", "default", "fraude", "hack", "hacker", "exploit", "invasao",
           "halted", "bankruptcy", "emergency", "emergencia", "circuit breaker"]
EVENTOS_IMPORTANTES = {
    "Comunicado oficial": ["fato relevante", "comunicado ao mercado", "comunicado oficial", "nota oficial", "press release", "comunicado do copom", "ata do copom", "statement"],
    "Mudança regulatória": ["resolucao", "regulament", "nova regra", "norma", "marco regulatorio", "licenca", "proibe", "libera", "aprova regra", "sec aprova", "sec sues", "regulation"],
    "Crise empresarial": ["recuperacao judicial", "falencia", "crise", "rombo", "calote", "default", "concordata", "liquidacao", "bankruptcy"],
    "Fraude ou investigação": ["fraude", "investigacao", "operacao da pf", "policia federal", "cvm abre", "inquerito", "lavagem", "manipulacao", "scam", "investigation", "indicted"],
    "Problema de liquidez": ["liquidez", "resgate suspenso", "resgates suspensos", "congela resgates", "saques suspensos", "withdrawals halted", "insolvencia", "corrida bancaria"],
    "Risco de crédito": ["rebaixa de rating", "rebaixamento", "downgrade", "inadimplencia", "credito podre", "calote", "rating"],
    "Política monetária": ["copom", "selic", "politica monetaria", "fomc", "federal reserve", "fed ", "bce", "juros basicos", "decisao de juros", "rate decision"],
    "Geopolítica": ["guerra", "conflito", "sancoes", "sanctions", "embargo", "tarifa", "tarifaco", "opep", "opec", "ataque militar", "cessar-fogo", "invasao", "tensao"],
    "Problema em exchange ou protocolo": ["exchange suspende", "saques suspensos", "hack", "exploit", "ataque ao protocolo", "bridge", "drained", "stolen", "rug pull", "depeg", "outage", "falha na rede"],
}


def _tem(t: str, termos) -> bool:
    return any(_norm_termo(k) in t for k in termos)


def _norm_termo(k: str) -> str:
    return I._norm(k) if not k.endswith(" ") else I._norm(k) + " "


def contar_tom(texto: str) -> tuple[int, int]:
    """(positivos, negativos) pelo léxico do Passo 13, com inversão por negação. Usado para o tom, o 'incerto' e a mistura de sinais."""
    t = I._norm(texto)
    pos = neg = 0
    for lista, sinal in ((I.PALAVRAS_POSITIVAS, 1), (I.PALAVRAS_NEGATIVAS, -1)):
        for termo in lista:
            for ini in I._casa_termo(t, termo):
                inv = any(a in I.NEGACOES for a in t[:ini].split()[-2:])
                if (sinal > 0) != inv:
                    pos += 1
                else:
                    neg += 1
    return pos, neg


def classificar_sentimento(texto: str, especulativo: bool = False) -> dict:
    """positivo | negativo | neutro | incerto. 'Incerto' = texto especulativo ou com sinais positivos E negativos na mesma notícia.
    É leitura APROXIMADA por palavras do título/resumo: não mede o efeito no preço."""
    pos, neg = contar_tom(texto)
    if especulativo or (pos > 0 and neg > 0 and abs(pos - neg) <= 1):
        rot = "incerto"
    else:
        rot = "positivo" if pos > neg else "negativo" if neg > pos else "neutro"
    return {"sentimento": rot, "pos": pos, "neg": neg}


def normalizar_noticia(n: dict, origem: str = "", agora: datetime | None = None, ticker: str | None = None, nome: str | None = None,
                       max_idade_dias: int = 7) -> dict:
    """Notícia bruta → registro completo (Passo 15 §12): fonte, link, data de publicação, horário, status de confirmação, nível da fonte,
    categorias, sentimento, urgência, tipo de evento importante, especulação, atraso e relevância (0-100)."""
    agora = agora or datetime.now()
    base = I.classificar_noticia(n, ticker, nome, agora)
    texto = I._norm(base["titulo"] + " " + base["resumo"])
    nf = nivel_fonte(base.get("fonte"), base.get("url"), n.get("fonte_url"))
    espec = _tem(texto, ESPECULATIVO)
    sent = classificar_sentimento(base["titulo"] + " " + base["resumo"], espec and nf["nivel"] != "oficial")
    importantes = [k for k, kws in EVENTOS_IMPORTANTES.items() if _tem(texto, kws)]
    urgente = _tem(texto, URGENTE) and nf["nivel"] != "nao_verificada"
    dias = base.get("dias")
    desatual = dias is not None and dias > max_idade_dias
    rel = base["relevancia"] + {"oficial": 12, "veiculo": 4, "nao_verificada": -12}[nf["nivel"]] + (10 if importantes else 0) + (8 if urgente else 0) - (8 if espec else 0)
    rel = max(0, min(100, int(rel - (15 if desatual else 0))))
    if nf["nivel"] == "oficial" and not espec:
        status = "confirmado (fonte oficial)"
    elif espec:
        status = "especulativo (não confirmado)"
    elif nf["nivel"] == "veiculo":
        status = "reportado por veículo reconhecido"
    else:
        status = "não verificado (fonte desconhecida)"
    ident = hashlib.sha1(f"{I._norm(base['titulo'])}|{I._norm(base.get('fonte') or '')}|{(base.get('data') or '')[:10]}".encode()).hexdigest()[:12]
    data = base.get("data")
    return {**base, "id": ident, "origem": origem or "n/d", "fonte_nivel": nf["nivel"], "fonte_nome": nf["nome"], "status": status,
            "especulativo": espec, "sentimento": sent["sentimento"], "tom_pos": sent["pos"], "tom_neg": sent["neg"], "urgente": urgente,
            "importantes": importantes, "desatualizada": desatual, "relevancia": rel,
            "nivel": "alta" if rel >= 60 else "media" if rel >= 35 else "baixa",
            "publicada_em": data, "data_acontecimento": n.get("data_acontecimento"), "horario": data[11:16] if data and len(data) >= 16 else None,
            "ativos": list(n.get("ativos") or ([ticker] if ticker else [])), "fonte_url": n.get("fonte_url"),
            "natureza": "fato: a publicação existe (fonte, link e data acima) · sentimento e impacto: interpretação aproximada"}


def processar(brutas: list[dict], origem: str = "", agora: datetime | None = None, ticker: str | None = None, nome: str | None = None,
              max_idade_dias: int = 7) -> list[dict]:
    """Normaliza e remove o que tem aparência de injeção de comandos (nunca entra em alertas nem no assistente)."""
    return [x for x in (normalizar_noticia(n, origem, agora, ticker, nome, max_idade_dias) for n in brutas or []) if not x.get("conteudo_suspeito")]


def ocultas_suspeitas(brutas: list[dict]) -> int:
    return sum(1 for n in brutas or [] if I.classificar_noticia(n).get("conteudo_suspeito"))


# =============================================================================== duplicidade, agrupamento por acontecimento, contradições
def _numeros(t: str) -> set[str]:
    return set(re.findall(r"\d+[.,]?\d*\s?%?", t))


def agrupar_acontecimentos(noticias: list[dict], limiar: float = 0.5) -> list[dict]:
    """Junta notícias sobre o MESMO acontecimento (palavras em comum ≥ limiar, no mesmo intervalo de 3 dias). Cada grupo traz as fontes distintas,
    o nível da melhor fonte, se as fontes DIVERGEM no sentimento e se os números citados divergem. Duplicadas exatas viram 1 só."""
    grupos: list[dict] = []
    for n in sorted(noticias, key=lambda x: (-x.get("relevancia", 0), x.get("publicada_em") or "")):
        tk = set(I._tokens(n["titulo"]))
        alvo = None
        for g in grupos:
            u = tk | g["_tk"]
            if not u or len(tk & g["_tk"]) / len(u) < limiar:
                continue
            try:
                if abs((pd.Timestamp(n["publicada_em"]) - pd.Timestamp(g["publicada_em"])).total_seconds()) > 3 * 86400:
                    continue
            except Exception:
                pass
            alvo = g
            break
        if alvo is None:
            grupos.append({**n, "_tk": tk, "membros": [n], "fontes": [n["fonte"]]})
        else:
            if any(I._norm(m["titulo"]) == I._norm(n["titulo"]) and m["fonte"] == n["fonte"] for m in alvo["membros"]):
                continue                                   # mesma manchete da mesma fonte (cópia exata): conta uma vez
            alvo["membros"].append(n)
            if n["fonte"] not in alvo["fontes"]:
                alvo["fontes"].append(n["fonte"])
    ordem = {"oficial": 0, "veiculo": 1, "nao_verificada": 2}
    for g in grupos:
        g.pop("_tk", None)
        m = g["membros"]
        g["n_noticias"] = len(m)
        g["n_fontes"] = len(g["fontes"])
        g["melhor_fonte"] = min((x["fonte_nivel"] for x in m), key=lambda k: ordem[k])
        tons = {x["sentimento"] for x in m} - {"neutro", "incerto"}
        g["contraditoria"] = {"positivo", "negativo"} <= tons
        nums = [_numeros(x["titulo"]) for x in m]
        g["numeros_divergentes"] = len(m) > 1 and len({frozenset(s) for s in nums if s}) > 1 and all(s for s in nums)
        g["sentimento_grupo"] = "incerto" if g["contraditoria"] else g["sentimento"]
        datas = [x["publicada_em"] for x in m if x.get("publicada_em")]
        g["primeira_publicacao"], g["ultima_publicacao"] = (min(datas), max(datas)) if datas else (None, None)
        g["links"] = [{"fonte": x["fonte"], "url": x["url"]} for x in m if x.get("url")][:6]
        g["importantes"] = sorted({i for x in m for i in x["importantes"]})
        g["urgente"] = any(x["urgente"] for x in m)
        g["ativos"] = sorted({a for x in m for a in x["ativos"]})
        g["relevancia"] = min(100, max(x["relevancia"] for x in m) + (6 if g["n_fontes"] >= 3 else 0))
        g["nivel"] = "alta" if g["relevancia"] >= 60 else "media" if g["relevancia"] >= 35 else "baixa"
        g["especulativo"] = all(x["especulativo"] for x in m)
        if g["especulativo"] and g["melhor_fonte"] != "oficial":
            g["status"] = "especulativo (não confirmado)"
    return sorted(grupos, key=lambda g: (-g["relevancia"], g.get("publicada_em") or ""), reverse=False)


def sentimento_agregado(noticias: list[dict], agora: datetime | None = None, janela_dias: int = 3) -> dict:
    """Contagem por sentimento nos últimos `janela_dias` e nos `janela_dias` anteriores; mudança do saldo e sinais de virada.
    Saldo = (positivas - negativas) / total, de -1 a +1. Exige ao menos 4 notícias em cada janela para apontar mudança (amostra pequena engana)."""
    agora = agora or datetime.now()

    def faixa(a, b):
        out = []
        for n in noticias:
            try:
                d = (agora - pd.Timestamp(n["publicada_em"]).to_pydatetime().replace(tzinfo=None)).total_seconds() / 86400
            except Exception:
                continue
            if a <= d < b and not n.get("desatualizada"):
                out.append(n)
        return out

    def resumo(lst):
        c = {k: sum(1 for n in lst if n["sentimento"] == k) for k in ("positivo", "negativo", "neutro", "incerto")}
        tot = sum(c.values())
        return {**c, "total": tot, "saldo": ((c["positivo"] - c["negativo"]) / tot) if tot else None}

    r, a = resumo(faixa(0, janela_dias)), resumo(faixa(janela_dias, 2 * janela_dias))
    sinais = []
    if r["total"] >= 4 and a["total"] >= 4 and r["saldo"] is not None and a["saldo"] is not None:
        d = r["saldo"] - a["saldo"]
        if d <= -0.25:
            sinais.append(("aumento_negativas", f"Aumento de notícias negativas: saldo foi de {a['saldo']:+.2f} para {r['saldo']:+.2f} ({r['negativo']} negativas e {r['positivo']} positivas nos últimos {janela_dias} dias)."))
        elif d >= 0.25:
            sinais.append(("aumento_positivas", f"Aumento de notícias positivas: saldo foi de {a['saldo']:+.2f} para {r['saldo']:+.2f} ({r['positivo']} positivas e {r['negativo']} negativas nos últimos {janela_dias} dias)."))
        if r["saldo"] * a["saldo"] < 0 and abs(d) >= 0.4:
            sinais.append(("mudanca", f"Mudança de sentimento: o saldo trocou de sinal ({a['saldo']:+.2f} → {r['saldo']:+.2f})."))
    elif r["total"] < 4:
        sinais.append(("amostra_pequena", f"Só {r['total']} notícia(s) nos últimos {janela_dias} dias: pouco para falar em mudança de sentimento."))
    return {"recente": r, "anterior": a, "mudanca": None if (r["saldo"] is None or a["saldo"] is None) else r["saldo"] - a["saldo"], "sinais": sinais,
            "aviso": "Contagem de notícias descreve a cobertura, não o preço: muitas notícias positivas não garantem valorização."}


def divergencia_preco(sent: dict, var_5d_pct: float | None) -> str | None:
    """Texto de alerta quando o saldo de notícias e a variação de preço de 5 dias apontam para lados opostos. Nunca afirma causa."""
    s = (sent or {}).get("recente") or {}
    if var_5d_pct is None or s.get("saldo") is None or s.get("total", 0) < 3:
        return None
    if s["saldo"] >= 0.3 and var_5d_pct <= -3:
        return f"Divergência: notícias predominantemente positivas (saldo {s['saldo']:+.2f}), mas o preço caiu {abs(var_5d_pct):.1f}% em 5 pregões. A coincidência não prova causa."
    if s["saldo"] <= -0.3 and var_5d_pct >= 3:
        return f"Divergência: notícias predominantemente negativas (saldo {s['saldo']:+.2f}), mas o preço subiu {var_5d_pct:.1f}% em 5 pregões. A coincidência não prova causa."
    return None


def grande_repercussao(grupos: list[dict]) -> list[dict]:
    """Acontecimentos cobertos por ≥ 4 fontes distintas, com relevância alta (candidatos a grande repercussão)."""
    return [g for g in grupos if g["n_fontes"] >= 4 and g["relevancia"] >= 60][:8]


# =============================================================================== setores, ativos e exposição (interpretação por regras)
SETORES = {
    "Bancos e financeiras": ["banco", "bancos", "bancario", "financeir", "credito", "seguradora", "seguros", "bank"],
    "Petróleo, gás e combustíveis": ["petroleo", "petroleira", "gas natural", "combustiv", "refin", "oil", "opep", "brent", "petrobras"],
    "Mineração e siderurgia": ["mineracao", "minerio", "siderurg", "cobre", "aco "],
    "Energia elétrica": ["energia eletrica", "aneel", "distribuidora de energia", "geradora", "transmissora", "eletrica", "bandeira tarifaria"],
    "Varejo e consumo": ["varejo", "consumo", "supermercado", "e-commerce", "vestuario", "alimentos", "bebidas"],
    "Saúde": ["saude", "hospital", "plano de saude", "farmac", "laboratorio", "medicamento"],
    "Telecom e tecnologia": ["telecom", "telefonia", "tecnologia", "software", "semicondutor", "internet"],
    "Construção e imobiliário": ["construcao", "construtora", "incorporadora", "imobiliar", "habitac", "minha casa"],
    "Agronegócio": ["agro", "agricola", "soja", "milho", "frigorific", "etanol", "acucar"],
    "Transporte e logística": ["aereo", "aviacao", "companhia aerea", "logistica", "ferrovia", "rodovia", "frete", "transporte"],
    "Saneamento": ["saneamento", "agua e esgoto"],
    "Papel e celulose": ["celulose"],
}


def setores_do_texto(texto: str) -> list[str]:
    t = " " + I._norm(texto) + " "
    return [s for s, kws in SETORES.items() if any(" " + I._norm(k).strip() in t for k in kws)]


def tipo_renda_fixa(a: dict) -> str:
    t = I._norm(f"{a.get('id', '')} {a.get('nome', '')}")
    if "ipca" in t or "inflacao" in t:
        return "ipca"
    if "prefix" in t or "pre fix" in t:
        return "pre"
    if "selic" in t or "cdi" in t or "pos" in t or "lci" in t or "lca" in t:
        return "pos"
    return "outro"


def subtipo_fii(a: dict) -> str:
    t = I._norm(f"{a.get('subgrupo', '')} {a.get('nome', '')}")
    return "papel" if any(k in t for k in ("papel", "recebiveis", "cri", "credito")) else "tijolo" if any(k in t for k in ("tijolo", "logistic", "shopping", "lajes", "corporativ", "renda urbana", "hospital", "agencia")) else "outro"


def _casa_alvo(alvo: dict, a: dict) -> bool:
    """O alvo da regra ('classe', 'rf', 'fii', 'setor', 'tema') casa com o ativo? Sem informação suficiente do ativo → não casa (não adivinha)."""
    cl = "acao" if a.get("classe") == "bdr" else a.get("classe")
    if "classe" in alvo and cl != alvo["classe"]:
        return False
    if "rf" in alvo and tipo_renda_fixa(a) != alvo["rf"]:
        return False
    if "fii" in alvo and subtipo_fii(a) != alvo["fii"]:
        return False
    if "setor" in alvo:
        st = setores_do_texto(f"{a.get('setor') or ''} {a.get('subgrupo') or ''}")
        if alvo["setor"] not in st:
            return False
    return True


def _e(alvo: dict, direcao: str, porque: str) -> dict:
    return {"alvo": alvo, "direcao": direcao, "porque": porque}


B, P, M = "pode beneficiar", "pode pressionar", "efeito misto"
RENDA_VAR = {"classe": "acao"}
# "hack"/"ataque" aparecem em notícias que nada têm com cripto (ex.: ataque a supermercados): a regra de cripto só vale se o texto também fala de cripto
CONTEXTO_CRIPTO = ["cripto", "bitcoin", "btc", "ethereum", "ether", "eth", "blockchain", "token", "defi", "stablecoin", "usdt", "usdc", "solana", "binance", "coinbase", "exchange",
                   "carteira digital", "wallet", "altcoin", "ativos digitais", "mercado bitcoin", "protocolo", "rede"]
REGRAS_IMPACTO = [
    {"id": "juros_alta", "nome": "Alta de juros", "tipo": "macro", "horizonte": "imediato (dias) e médio (meses)",
     "gatilhos": ["alta da selic", "eleva a selic", "elevacao da selic", "sobe a selic", "eleva juros", "elevar juros", "aumento da selic", "juros sobem", "juros futuros sobem", "aperto monetario",
                  "yield sobe", "treasury yields rise", "fed raises", "fed sobe juros", "rate hike", "dispara juros", "juros em alta"],
     "efeitos": [_e({"classe": "renda_fixa", "rf": "pos"}, B, "títulos pós-fixados passam a render mais conforme a Selic/CDI sobe"),
                 _e({"classe": "renda_fixa", "rf": "pre"}, P, "o preço de mercado de prefixados cai quando as taxas sobem (marcação a mercado); mantido ao vencimento, a taxa contratada vale"),
                 _e({"classe": "renda_fixa", "rf": "ipca"}, P, "o preço de mercado de títulos IPCA+ pode cair com taxas reais maiores; ao vencimento vale a taxa contratada"),
                 _e({"classe": "fii", "fii": "tijolo"}, P, "juros maiores elevam a taxa de desconto e a concorrência da renda fixa com os rendimentos dos FIIs de tijolo"),
                 _e({"classe": "fii", "fii": "papel"}, M, "FIIs de papel costumam ter recebíveis atrelados a CDI/IPCA (podem ganhar), mas o preço da cota pode sofrer com taxas maiores"),
                 _e({"classe": "acao", "setor": "Construção e imobiliário"}, P, "financiamento e crédito mais caros costumam reduzir vendas e margens do setor"),
                 _e({"classe": "acao", "setor": "Varejo e consumo"}, P, "crédito mais caro e custo de capital maior pesam sobre consumo e empresas endividadas"),
                 _e({"classe": "acao", "setor": "Bancos e financeiras"}, M, "spreads podem subir, mas a inadimplência e o custo de captação também"),
                 _e(RENDA_VAR, P, "juros mais altos reduzem o valor presente dos lucros futuros e elevam o custo da dívida das empresas"),
                 _e({"classe": "cripto"}, P, "ambiente de juros altos tende a reduzir o apetite por ativos de risco")]},
    {"id": "juros_queda", "nome": "Queda de juros", "tipo": "macro", "horizonte": "imediato (dias) e médio (meses)",
     "gatilhos": ["corte da selic", "reduz a selic", "reducao da selic", "baixa a selic", "corta a selic", "corta juros", "reduz juros", "queda da selic", "juros caem", "juros futuros recuam",
                  "afrouxamento monetario", "corte de juros", "fed cuts", "fed corta", "rate cut", "juros em queda"],
     "efeitos": [_e({"classe": "renda_fixa", "rf": "pos"}, P, "o rendimento de pós-fixados acompanha a queda da Selic/CDI"),
                 _e({"classe": "renda_fixa", "rf": "pre"}, B, "o preço de mercado de prefixados tende a subir quando as taxas caem (marcação a mercado)"),
                 _e({"classe": "renda_fixa", "rf": "ipca"}, B, "o preço de mercado de títulos IPCA+ pode subir com taxas reais menores"),
                 _e({"classe": "fii", "fii": "tijolo"}, B, "taxa de desconto menor e renda fixa menos atraente tendem a favorecer cotas de tijolo"),
                 _e({"classe": "fii", "fii": "papel"}, M, "recebíveis atrelados ao CDI rendem menos, mas o preço da cota pode se valorizar"),
                 _e({"classe": "acao", "setor": "Construção e imobiliário"}, B, "crédito mais barato costuma ajudar vendas e financiamento do setor"),
                 _e({"classe": "acao", "setor": "Varejo e consumo"}, B, "crédito mais barato e menor custo de dívida podem ajudar consumo e empresas alavancadas"),
                 _e(RENDA_VAR, B, "juros menores elevam o valor presente dos lucros futuros e reduzem despesa financeira"),
                 _e({"classe": "cripto"}, B, "juros menores tendem a elevar o apetite por ativos de risco")]},
    {"id": "juros_decisao", "nome": "Decisão ou comunicação de política monetária", "tipo": "macro", "horizonte": "imediato (dias)",
     "gatilhos": ["copom", "fomc", "decisao de juros", "ata do copom", "politica monetaria", "reuniao do fed", "federal reserve", "rate decision", "mantem a selic", "mantem juros"],
     "efeitos": [_e({"classe": "renda_fixa"}, M, "o que move taxas e preços é o resultado frente à expectativa do mercado, não a decisão em si"),
                 _e({"classe": "fii"}, M, "FIIs reagem à trajetória esperada dos juros"),
                 _e(RENDA_VAR, M, "ações sensíveis a juros costumam reagir à surpresa em relação ao esperado"),
                 _e({"classe": "cripto"}, M, "o tom do banco central afeta o apetite por risco")]},
    {"id": "inflacao_alta", "nome": "Inflação acima do esperado", "tipo": "macro", "horizonte": "imediato (dias) e médio (meses)",
     "gatilhos": ["inflacao acelera", "ipca acima", "ipca sobe", "ipca surpreende", "inflacao surpreende", "inflacao em alta", "cpi acima", "cpi rises", "inflation rises", "inflation accelerates", "igp-m sobe", "inflacao maior"],
     "efeitos": [_e({"classe": "renda_fixa", "rf": "ipca"}, B, "o principal de títulos IPCA+ acompanha a inflação, o que protege o ganho real se mantidos"),
                 _e({"classe": "renda_fixa", "rf": "pre"}, P, "inflação maior pode elevar juros futuros e reduzir o preço de mercado de prefixados"),
                 _e({"classe": "fii", "fii": "tijolo"}, M, "contratos de aluguel costumam ser reajustados pela inflação, mas juros maiores pesam nas cotas"),
                 _e(RENDA_VAR, P, "inflação maior eleva custos e a expectativa de juros; empresas com poder de repasse sofrem menos"),
                 _e({"classe": "cripto"}, M, "efeito indireto, via juros e apetite por risco")]},
    {"id": "inflacao_queda", "nome": "Inflação abaixo do esperado", "tipo": "macro", "horizonte": "imediato (dias) e médio (meses)",
     "gatilhos": ["inflacao desacelera", "ipca abaixo", "ipca recua", "ipca cai", "inflacao em queda", "cpi falls", "inflation cools", "inflation eases", "deflacao"],
     "efeitos": [_e({"classe": "renda_fixa", "rf": "pre"}, B, "inflação menor pode reduzir juros futuros e elevar o preço de mercado de prefixados"),
                 _e({"classe": "renda_fixa", "rf": "ipca"}, M, "o ganho com a correção pela inflação diminui, mas taxas menores ajudam o preço de mercado"),
                 _e(RENDA_VAR, B, "inflação menor abre espaço para juros menores e alivia custos"),
                 _e({"classe": "fii"}, M, "reajuste de aluguéis menor, mas juros menores favorecem as cotas")]},
    {"id": "dolar_alta", "nome": "Alta do dólar", "tipo": "macro", "horizonte": "imediato (dias)",
     "gatilhos": ["dolar sobe", "dolar dispara", "dolar em alta", "dolar renova maxima", "real se desvaloriza", "alta do dolar", "dolar acima de", "dollar rises", "dollar surges", "dolar fecha em alta"],
     "efeitos": [_e({"classe": "acao", "setor": "Mineração e siderurgia"}, B, "receitas em dólar com custos em reais costumam se favorecer"),
                 _e({"classe": "acao", "setor": "Petróleo, gás e combustíveis"}, B, "preços ligados ao dólar podem elevar a receita em reais"),
                 _e({"classe": "acao", "setor": "Agronegócio"}, B, "exportadores recebem em dólar"),
                 _e({"classe": "acao", "setor": "Transporte e logística"}, P, "custos como combustível, leasing e peças são dolarizados (aéreas em especial)"),
                 _e({"classe": "acao", "setor": "Varejo e consumo"}, P, "importados e insumos mais caros pressionam margens"),
                 _e({"classe": "etf"}, M, "ETFs com carteira no exterior sobem em reais; os locais dependem das empresas"),
                 _e({"classe": "cripto"}, M, "cripto é cotada em dólar: em reais pode subir mesmo com preço estável em dólar")]},
    {"id": "dolar_queda", "nome": "Queda do dólar", "tipo": "macro", "horizonte": "imediato (dias)",
     "gatilhos": ["dolar cai", "dolar recua", "dolar em queda", "dolar despenca", "real se valoriza", "queda do dolar", "dolar fecha em queda", "dollar falls", "dollar weakens"],
     "efeitos": [_e({"classe": "acao", "setor": "Mineração e siderurgia"}, P, "receitas em dólar valem menos em reais"),
                 _e({"classe": "acao", "setor": "Agronegócio"}, P, "exportadores recebem menos em reais"),
                 _e({"classe": "acao", "setor": "Transporte e logística"}, B, "custos dolarizados ficam menores (aéreas em especial)"),
                 _e({"classe": "acao", "setor": "Varejo e consumo"}, B, "importados e insumos mais baratos aliviam margens"),
                 _e({"classe": "etf"}, M, "ETFs com carteira no exterior perdem em reais; os locais dependem das empresas"),
                 _e({"classe": "cripto"}, M, "cripto cotada em dólar rende menos em reais quando o dólar cai")]},
    {"id": "petroleo_alta", "nome": "Alta do petróleo", "tipo": "macro", "horizonte": "imediato (dias)",
     "gatilhos": ["petroleo sobe", "petroleo dispara", "brent sobe", "brent dispara", "alta do petroleo", "oil rises", "oil surges", "petroleo em alta", "opep corta", "opec cuts"],
     "efeitos": [_e({"classe": "acao", "setor": "Petróleo, gás e combustíveis"}, B, "preços maiores elevam a receita de produtoras"),
                 _e({"classe": "acao", "setor": "Transporte e logística"}, P, "combustível é custo relevante (aéreas, frete)"),
                 _e({"classe": "acao", "setor": "Varejo e consumo"}, P, "frete e energia mais caros pressionam margens e inflação")]},
    {"id": "petroleo_queda", "nome": "Queda do petróleo", "tipo": "macro", "horizonte": "imediato (dias)",
     "gatilhos": ["petroleo cai", "petroleo recua", "brent cai", "brent recua", "queda do petroleo", "oil falls", "oil drops", "petroleo em queda", "petroleo despenca"],
     "efeitos": [_e({"classe": "acao", "setor": "Petróleo, gás e combustíveis"}, P, "preços menores reduzem a receita de produtoras"),
                 _e({"classe": "acao", "setor": "Transporte e logística"}, B, "combustível mais barato alivia custos")]},
    {"id": "risco_fiscal", "nome": "Risco fiscal ou político", "tipo": "macro", "horizonte": "médio (semanas a meses)",
     "gatilhos": ["risco fiscal", "arcabouco fiscal", "meta fiscal", "deficit fiscal", "gasto publico", "divida publica", "pacote fiscal", "rombo fiscal", "teto de gastos", "fiscal framework"],
     "efeitos": [_e({"classe": "renda_fixa", "rf": "pre"}, P, "incerteza fiscal costuma elevar juros futuros, o que reduz o preço de mercado de prefixados"),
                 _e({"classe": "renda_fixa", "rf": "ipca"}, P, "taxas reais mais altas reduzem o preço de mercado de títulos IPCA+"),
                 _e(RENDA_VAR, P, "prêmio de risco maior pesa sobre o preço das ações locais"),
                 _e({"classe": "fii"}, P, "juros longos mais altos pesam nas cotas")]},
    {"id": "atividade_fraca", "nome": "Atividade econômica fraca", "tipo": "macro", "horizonte": "médio (meses)",
     "gatilhos": ["pib cai", "pib recua", "pib decepciona", "recessao", "economia encolhe", "economia desacelera", "atividade fraca", "gdp contracts", "recession", "desemprego sobe", "desemprego aumenta"],
     "efeitos": [_e({"classe": "acao", "setor": "Varejo e consumo"}, P, "menor renda e emprego reduzem consumo"),
                 _e({"classe": "acao", "setor": "Bancos e financeiras"}, P, "inadimplência pode subir e a demanda por crédito, cair"),
                 _e({"classe": "renda_fixa", "rf": "pre"}, M, "atividade fraca pode levar a juros menores (favorece prefixados), mas aumenta o risco de crédito")]},
    {"id": "emprego_eua", "nome": "Dados de emprego e inflação dos EUA", "tipo": "macro", "horizonte": "imediato (dias)",
     "gatilhos": ["payroll", "nonfarm", "folha de pagamento", "pedidos de auxilio-desemprego", "jobless claims", "us jobs", "empregos nos eua", "cpi americano", "inflacao americana", "pce"],
     "efeitos": [_e({"classe": "cripto"}, M, "dados fortes ou fracos mudam a expectativa de juros dos EUA e o apetite por risco"),
                 _e({"classe": "etf"}, M, "ETFs ligados ao mercado americano reagem à expectativa de juros do Fed"),
                 _e(RENDA_VAR, M, "bolsa local costuma acompanhar o apetite global por risco"),
                 _e({"classe": "renda_fixa", "rf": "pre"}, M, "juros dos EUA influenciam as taxas locais")]},
    {"id": "inflacao_evento", "nome": "Divulgação de índice de inflação", "tipo": "macro", "horizonte": "imediato (dias)", "gatilhos": [],
     "efeitos": [_e({"classe": "renda_fixa"}, M, "o resultado frente ao esperado muda as taxas e os preços de títulos; IPCA+ acompanha o índice"),
                 _e({"classe": "fii"}, M, "reajuste de aluguéis e expectativa de juros mexem com as cotas"),
                 _e(RENDA_VAR, M, "inflação surpreendendo muda a expectativa de juros, que pesa sobre as ações")]},
    {"id": "atividade_evento", "nome": "Divulgação de indicador de atividade ou emprego", "tipo": "macro", "horizonte": "imediato (dias)", "gatilhos": [],
     "efeitos": [_e({"classe": "acao", "setor": "Varejo e consumo"}, M, "renda, emprego e consumo influenciam vendas e margens"),
                 _e({"classe": "acao", "setor": "Bancos e financeiras"}, M, "atividade e emprego influenciam crédito e inadimplência"),
                 _e(RENDA_VAR, M, "atividade mais forte ou mais fraca que o esperado muda lucros e expectativa de juros"),
                 _e({"classe": "renda_fixa"}, M, "atividade forte pode elevar juros esperados; fraca, reduzir")]},
    {"id": "crise_credito", "nome": "Estresse de crédito ou liquidez", "tipo": "macro", "horizonte": "médio (semanas a meses)",
     "gatilhos": ["recuperacao judicial", "calote", "inadimplencia sobe", "rebaixa de rating", "rebaixamento", "credito privado", "default", "liquidacao extrajudicial", "resgates suspensos", "emissor"],
     "efeitos": [_e({"classe": "fii", "fii": "papel"}, P, "recebíveis de empresas em dificuldade elevam o risco de inadimplência dos CRI"),
                 _e({"classe": "fundo"}, M, "fundos de crédito privado podem marcar perdas se emissores da carteira forem afetados"),
                 _e({"classe": "acao", "setor": "Bancos e financeiras"}, P, "mais provisões e menor apetite por crédito")]},
    {"id": "geopolitica", "nome": "Evento geopolítico", "tipo": "macro", "horizonte": "imediato (dias)",
     "gatilhos": ["guerra", "conflito armado", "sancoes", "ataque militar", "tensao geopolitica", "cessar-fogo", "embargo", "invasao", "war", "sanctions"],
     "efeitos": [_e({"classe": "acao", "setor": "Petróleo, gás e combustíveis"}, M, "risco de oferta pode elevar o petróleo, mas a volatilidade é alta"),
                 _e(RENDA_VAR, P, "aversão a risco costuma pesar sobre bolsas, em especial emergentes"),
                 _e({"classe": "cripto"}, M, "a reação costuma ser volátil nos dois sentidos")]},
    {"id": "cripto_seguranca", "nome": "Falha de segurança em cripto", "tipo": "cripto", "horizonte": "imediato (dias)", "exige": CONTEXTO_CRIPTO,
     "gatilhos": ["hack", "hacker", "exploit", "drained", "stolen", "rug pull", "depeg", "saques suspensos", "withdrawals halted", "vulnerabilidade", "ataque ao protocolo"],
     "efeitos": [_e({"classe": "cripto"}, P, "perdas de fundos e perda de confiança no projeto ou na exchange afetada podem pressionar o preço do ativo envolvido e, em menor grau, do setor")]},
    {"id": "cripto_protocolo", "nome": "Atualização de protocolo ou rede", "tipo": "cripto", "horizonte": "curto a médio", "exige": CONTEXTO_CRIPTO,
     "gatilhos": ["hard fork", "mainnet", "atualizacao de rede", "network upgrade", "halving", "upgrade da rede", "atualizacao do protocolo", "protocol upgrade", "testnet", "eip-"],
     "efeitos": [_e({"classe": "cripto"}, M, "mudanças de emissão, taxas ou segurança podem alterar a percepção sobre o projeto; o efeito no preço é incerto")]},
    {"id": "cripto_regulacao", "nome": "Regulação ou ETF de cripto", "tipo": "cripto", "horizonte": "curto a médio",
     "gatilhos": ["etf de bitcoin", "etf de ether", "etf de cripto", "bitcoin etf", "ether etf", "sec cripto", "sec aprova", "regulacao de criptoativos", "marco das criptomoedas", "crypto regulation", "regulamenta criptoativos", "stablecoin"],
     "efeitos": [_e({"classe": "cripto"}, M, "regra mais clara pode atrair ou afastar investidores; os efeitos variam por ativo"),
                 _e({"classe": "etf"}, M, "ETFs de cripto ou ligados ao setor podem ser afetados diretamente")]},
]
REGRA_POR_ID = {r["id"]: r for r in REGRAS_IMPACTO}
REGRA_DE_EVENTO = {"juros": "juros_decisao", "inflacao": "inflacao_evento", "atividade": "atividade_evento", "emprego": "atividade_evento"}


def impactos_de_evento(e: dict, ativos: list[dict]) -> list[dict]:
    """Impacto de um evento do calendário (juros, inflação, atividade, emprego) sobre os ativos cadastrados, por regra de exposição."""
    rid = REGRA_DE_EVENTO.get(e.get("categoria"))
    if not rid or (e.get("categoria") == "emprego" and e.get("pais") == "Estados Unidos"):
        rid = "emprego_eua" if e.get("categoria") == "emprego" and e.get("pais") == "Estados Unidos" else rid
    if not rid:
        return []
    item = {"titulo": e["evento"], "evento": e["evento"], "data": e["data"], "fonte": e["fonte"], "url": e.get("url"), "relevancia_rotulo": e["relevancia"],
            "relevancia": {"alta": 70, "media": 45, "baixa": 20}[e["relevancia"]], "melhor_fonte": "oficial"}
    return analisar_impacto(item, ativos, "evento", [rid])


def mencoes(texto: str, ativos: list[dict]) -> list[dict]:
    """Ativos citados DIRETAMENTE no texto (ticker ou palavra-chave do nome). Não adivinha: sem citação, sem associação direta."""
    t = I._norm(texto)
    achados = []
    for a in ativos or []:
        alvos = [a.get("id")] + I._tokens_nome(a.get("nome"))
        if any(x and len(I._norm(str(x))) >= 3 and re.search(r"(?<![a-z0-9])" + re.escape(I._norm(str(x))) + r"(?![a-z0-9])", t) for x in alvos):
            achados.append(a)
    return achados


def regras_acionadas(texto: str) -> list[dict]:
    t = " " + I._norm(texto) + " "
    out = []
    for r in REGRAS_IMPACTO:
        hit = next((g for g in r["gatilhos"] if re.search(r"(?<![a-z0-9])" + re.escape(I._norm(g)) + r"(?![a-z0-9])", t)), None)
        if hit and r.get("exige") and not any(re.search(r"(?<![a-z0-9])" + re.escape(I._norm(k)) + r"(?![a-z0-9])", t) for k in r["exige"]):
            hit = None
        if hit:
            out.append({**r, "gatilho_visto": hit})
    # alta e queda de juros/inflação/dólar/petróleo se contradizem no mesmo texto: não escolhemos lado (cai na regra de decisão/mista)
    ids = {r["id"] for r in out}
    for a, b in (("juros_alta", "juros_queda"), ("inflacao_alta", "inflacao_queda"), ("dolar_alta", "dolar_queda"), ("petroleo_alta", "petroleo_queda")):
        if a in ids and b in ids:
            out = [r for r in out if r["id"] not in (a, b)]
    return out


def _confianca(origem: dict, direta: bool, n_fontes: int, especulativo: bool, nivel: str) -> str:
    if especulativo:
        return "baixa"
    if direta and (nivel == "oficial" or n_fontes >= 3):
        return "alta"
    if (direta and nivel in ("oficial", "veiculo")) or (not direta and (nivel == "oficial" or n_fontes >= 2)):
        return "média"
    return "baixa"


def analisar_impacto(item: dict, ativos: list[dict], tipo_origem: str = "noticia", forcadas: list[str] | None = None) -> list[dict]:
    """Relaciona UMA notícia (grupo) ou evento aos ativos cadastrados. Devolve 0..n impactos, cada um com: ativos afetados (direção
    possível e motivo), setores, tipo, justificativa, horizonte, relevância e confiança. Sempre 'pode', nunca 'vai'."""
    texto = f"{item.get('titulo', '')} {item.get('resumo', '')} {item.get('evento', '')} {item.get('descricao', '')}"
    diretos = mencoes(texto, ativos) if tipo_origem != "evento" else []
    regras = [{**REGRA_POR_ID[i], "gatilho_visto": "evento do calendário"} for i in (forcadas or []) if i in REGRA_POR_ID] if forcadas else regras_acionadas(texto)
    n_fontes = int(item.get("n_fontes") or 1)
    nivel = item.get("melhor_fonte") or item.get("fonte_nivel") or ("oficial" if tipo_origem == "evento" else "nao_verificada")
    espec = bool(item.get("especulativo")) and nivel != "oficial"
    rel = int(item.get("relevancia") or {"alta": 70, "media": 45, "baixa": 20}.get(item.get("relevancia_rotulo"), 40))
    out = []
    base = {"origem": tipo_origem, "titulo": item.get("titulo") or item.get("evento"), "fonte": item.get("fonte"), "url": item.get("url"),
            "data": item.get("publicada_em") or item.get("data"), "relevancia": rel, "nivel": "alta" if rel >= 60 else "media" if rel >= 35 else "baixa",
            "status": "evento do calendário" if tipo_origem == "evento" else item.get("status"),
            "limite": "Interpretação por regras de exposição, não previsão: o efeito real depende da surpresa, do que já estava no preço e de cada empresa."}
    if diretos:
        out.append({**base, "associacao": "menção direta", "tipo_impacto": "empresa/ativo", "regra": "mencao_direta", "setores": sorted({s for a in diretos for s in setores_do_texto(f"{a.get('setor') or ''} {a.get('subgrupo') or ''}")}),
                    "ativos": [{"id": a["id"], "classe": a.get("classe"), "peso": a.get("peso"), "direcao": "depende do conteúdo",
                                "porque": "o ativo é citado diretamente; leia a fonte para ver se o fato é favorável ou desfavorável"} for a in diretos],
                    "justificativa": f"Cita {', '.join(a['id'] for a in diretos)} no título ou no resumo.", "horizonte": "imediato a médio, conforme o fato",
                    "confianca": _confianca(item, True, n_fontes, espec, nivel)})
    for r in regras:
        afet = []
        for ef in r["efeitos"]:
            for a in ativos or []:
                if _casa_alvo(ef["alvo"], a):
                    afet.append({"id": a["id"], "classe": a.get("classe"), "peso": a.get("peso"), "direcao": ef["direcao"], "porque": ef["porque"]})
        vistos, uniq = set(), []
        for x in afet:                     # a regra mais específica (setor/subtipo) vem antes da genérica da classe; fica a primeira por ativo
            if x["id"] not in vistos:
                vistos.add(x["id"])
                uniq.append(x)
        out.append({**base, "associacao": "exposição por regra", "tipo_impacto": r["tipo"], "regra": r["id"], "nome_regra": r["nome"],
                    "setores": sorted({ef["alvo"]["setor"] for ef in r["efeitos"] if "setor" in ef["alvo"]}),
                    "classes_expostas": sorted({ef["alvo"]["classe"] for ef in r["efeitos"] if "classe" in ef["alvo"]}),
                    "ativos": uniq, "justificativa": (f"Texto menciona “{r['gatilho_visto']}”: " if tipo_origem != "evento" else "Evento do calendário: ") + f"{r['nome'].lower()} costuma atingir esses ativos por esses caminhos.",
                    "horizonte": r["horizonte"], "confianca": _confianca(item, False, n_fontes, espec, nivel)})
    cats = set(item.get("categorias") or [])
    if cats & {"Mudanças regulatórias", "Decisões governamentais"}:
        for setor in setores_do_texto(texto):
            afet = [{"id": a["id"], "classe": a.get("classe"), "peso": a.get("peso"), "direcao": M, "porque": "mudança de regra ou de política pode alterar margens, custos ou demanda do setor"}
                    for a in ativos or [] if _casa_alvo({"classe": "acao", "setor": setor}, a)]
            out.append({**base, "associacao": "exposição por regra", "tipo_impacto": "setorial", "regra": "regulatorio_setor", "nome_regra": f"Mudança regulatória/política em {setor}",
                        "setores": [setor], "ativos": afet, "justificativa": f"A notícia trata de regra ou política e cita o setor {setor.lower()}.",
                        "horizonte": "médio (meses)", "confianca": _confianca(item, False, n_fontes, espec, nivel)})
    return out


# =============================================================================== calendário econômico
# Datas de reuniões vêm de calendários OFICIAIS publicados com antecedência. Cada tabela guarda a fonte e a data da última conferência.
# O que não consta aqui (ex.: Copom de 2027, ainda não divulgado nesta conferência) simplesmente não aparece: nada é estimado.
CONFERIDO_EM = "2026-11-04"
COPOM_DECISOES = {
    2026: ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-08-05", "2026-09-16", "2026-11-04", "2026-12-09"],
}
FONTE_COPOM = {"fonte": "Banco Central do Brasil — calendário de reuniões do Copom", "url": "https://www.bcb.gov.br/controleinflacao/calendarioreunioes"}
FOMC_DECISOES = {
    2026: ["2026-01-28", "2026-03-18", "2026-04-29", "2026-06-17", "2026-07-29", "2026-09-16", "2026-10-28", "2026-12-09"],
    2027: ["2027-01-27", "2027-03-17", "2027-04-28", "2027-06-09", "2027-07-28", "2027-09-15", "2027-10-27", "2027-12-08"],
}
FONTE_FOMC = {"fonte": "Federal Reserve — calendário do FOMC", "url": "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"}
CATEGORIAS_EVENTO = {"juros": "Juros", "inflacao": "Inflação", "atividade": "Atividade", "emprego": "Emprego", "outro": "Outro"}


def _status_evento(dt_ev: str, agora: datetime, tem_hora: bool) -> str:
    try:
        d = pd.Timestamp(dt_ev)
    except Exception:
        return "futuro"
    if d.date() < agora.date():
        return "divulgado"
    if d.date() == agora.date():
        return "hoje"
    return "futuro"


def novo_evento(data: str, evento: str, pais: str, categoria: str, relevancia: str, fonte: str, url: str | None, hora: str | None = None, **extra) -> dict:
    ident = hashlib.sha1(f"{data}|{evento}|{pais}".encode()).hexdigest()[:10]
    return {"id": ident, "data": data, "hora": hora, "pais": pais, "evento": evento, "categoria": categoria if categoria in CATEGORIAS_EVENTO else "outro",
            "relevancia": relevancia, "fonte": fonte, "url": I.url_segura(url), "anterior": None, "esperado": None, "divulgado": None, "unidade": None,
            "referencia": None, "observacao": None, **extra}


def calendario_copom(agora: datetime | None = None) -> list[dict]:
    out = []
    for ano, datas in COPOM_DECISOES.items():
        for i, d in enumerate(datas, 1):
            out.append(novo_evento(d, f"Decisão do Copom — {i}ª reunião de {ano} (Selic)", "Brasil", "juros", "alta", FONTE_COPOM["fonte"], FONTE_COPOM["url"],
                                   observacao="A reunião dura dois dias; a decisão é divulgada no 2º dia, normalmente após o fechamento do mercado (confirme o horário na fonte).",
                                   reuniao=f"R{i}/{ano}", conferido_em=CONFERIDO_EM))
    return sorted(out, key=lambda e: e["data"])


def calendario_fomc() -> list[dict]:
    out = []
    for ano, datas in FOMC_DECISOES.items():
        for i, d in enumerate(datas, 1):
            out.append(novo_evento(d, f"Decisão do FOMC (Federal Reserve) — reunião {i}/{ano}", "Estados Unidos", "juros", "alta", FONTE_FOMC["fonte"], FONTE_FOMC["url"],
                                   observacao="Decisão no 2º dia da reunião (comunicado normalmente às 14h, horário de Nova York). A data é tentativa até ser confirmada na reunião anterior, segundo o Fed.",
                                   conferido_em=CONFERIDO_EM))
    return sorted(out, key=lambda e: e["data"])


RELEVANCIA_IBGE = [("ipca-15", "IPCA-15", "inflacao", "media"), ("ipca", "IPCA", "inflacao", "alta"), ("inpc", "INPC", "inflacao", "alta"),
                   ("contas nacionais trimestrais", "PIB (Contas Nacionais Trimestrais)", "atividade", "alta"), ("pib", "PIB", "atividade", "alta"),
                   ("pnad continua", "PNAD Contínua (desemprego)", "emprego", "alta"), ("producao industrial", "Produção industrial", "atividade", "media"),
                   ("comercio", "Vendas do comércio (PMC)", "atividade", "media"), ("servicos", "Volume de serviços (PMS)", "atividade", "media"),
                   ("ipp", "Preços ao produtor (IPP)", "inflacao", "baixa")]


def parse_ibge_calendario(dados, agora: datetime | None = None) -> list[dict]:
    """JSON de https://servicodados.ibge.gov.br/api/v3/calendario → divulgações de indicadores relevantes. Formato inesperado → []."""
    try:
        itens = dados.get("items") if isinstance(dados, dict) else None
        out = []
        for x in itens or []:
            tipo = I._norm(str(x.get("tipo") or ""))
            if tipo and "divulg" not in tipo:
                continue
            tit = str(x.get("titulo") or x.get("produto") or "")
            norm = I._norm(f"{tit} {x.get('produto') or ''}")
            m = next(((rot, cat, rel) for k, rot, cat, rel in RELEVANCIA_IBGE if re.search(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", norm.replace("-", " ").replace("ipca 15", "ipca-15"))), None)
            if not m:
                continue
            di = _data_br(x.get("data_inicio") or x.get("data_divulgacao"))
            if not di:
                continue
            hora = di[11:16] if len(di) >= 16 and di[11:16] != "00:00" else None
            ref = I._limpar_texto(tit, 120)
            out.append(novo_evento(di[:10], f"{m[0]} — {ref}" if ref and I._norm(ref) != I._norm(m[0]) else m[0], "Brasil", m[1], m[2], "IBGE — calendário de divulgações", x.get("link") or "https://www.ibge.gov.br/calendario-indicadores.html",
                                   hora=hora, indicador=m[0]))
        return sorted(out, key=lambda e: (e["data"], e["hora"] or ""))
    except Exception:
        return []


BLS_RELEVANTES = [("employment situation", "Payroll — Situação do emprego (EUA)", "emprego", "alta"), ("consumer price index", "Inflação ao consumidor — CPI (EUA)", "inflacao", "alta"),
                  ("producer price index", "Inflação ao produtor — PPI (EUA)", "inflacao", "media"), ("job openings", "Vagas abertas — JOLTS (EUA)", "emprego", "media"),
                  ("employment cost index", "Custo do emprego — ECI (EUA)", "emprego", "baixa")]


def parse_ics_bls(texto: str, agora: datetime | None = None) -> list[dict]:
    """Calendário iCal do BLS (https://www.bls.gov/schedule/news_release/bls.ics) → Payroll, CPI, PPI e afins. Horário convertido para Brasília."""
    if not texto or len(texto) > 3_000_000 or "BEGIN:VEVENT" not in texto:
        return []
    out = []
    try:
        from zoneinfo import ZoneInfo
        for bloco in texto.split("BEGIN:VEVENT")[1:]:
            bloco = bloco.split("END:VEVENT")[0].replace("\r", "")
            bloco = re.sub(r"\n[ \t]", "", bloco)                     # linhas dobradas do iCal
            resumo = re.search(r"^SUMMARY[^:]*:(.*)$", bloco, flags=re.M)
            ini = re.search(r"^DTSTART([^:\n]*):(\d{8})(?:T(\d{6})Z?)?", bloco, flags=re.M)
            if not resumo or not ini:
                continue
            m = next(((rot, cat, rel) for k, rot, cat, rel in BLS_RELEVANTES if k in resumo.group(1).lower()), None)
            if not m:
                continue
            params, dia, hh = ini.group(1), ini.group(2), ini.group(3)
            d = datetime.strptime(dia, "%Y%m%d")
            hora_et = hora_br = None
            if hh:
                dt = datetime.strptime(dia + hh, "%Y%m%d%H%M%S")
                tz = re.search(r"TZID=([^;:]+)", params)
                if tz:
                    local = dt.replace(tzinfo=ZoneInfo(tz.group(1)))
                else:
                    from datetime import timezone
                    local = dt.replace(tzinfo=timezone.utc)
                br = local.astimezone(ZoneInfo("America/Sao_Paulo"))
                et = local.astimezone(ZoneInfo("America/New_York"))
                hora_br, hora_et, d = br.strftime("%H:%M"), et.strftime("%H:%M"), br.replace(tzinfo=None)
            out.append(novo_evento(d.strftime("%Y-%m-%d"), m[0], "Estados Unidos", m[1], m[2], "BLS — calendário de divulgações", "https://www.bls.gov/schedule/news_release/",
                                   hora=hora_br, observacao=f"Horário de Brasília (divulgação às {hora_et} em Nova York)." if hora_et else None, indicador=m[0]))
    except Exception:
        return []
    return sorted(out, key=lambda e: (e["data"], e["hora"] or ""))


# ---- resultados (Banco Central, SGS) e expectativas (Focus)
SERIES_BCB = {  # indicador → (série SGS, rótulo, unidade, mensal?)
    "IPCA": (433, "IPCA (variação mensal)", "% a.m.", True), "INPC": (188, "INPC (variação mensal)", "% a.m.", True), "IGP-M": (189, "IGP-M (variação mensal)", "% a.m.", True),
    "Selic meta": (432, "Meta da taxa Selic", "% a.a.", False), "Desemprego": (24369, "Taxa de desocupação (PNAD Contínua)", "%", True),
}


def parse_sgs(dados) -> list[dict]:
    """JSON do SGS ([{'data':'dd/mm/aaaa','valor':'0.52'}]) → [{'data':'aaaa-mm-dd','valor':float}] em ordem. Linhas inválidas são descartadas."""
    out = []
    try:
        for x in dados or []:
            d = pd.to_datetime(str(x.get("data")), format="%d/%m/%Y", errors="coerce")
            v = pd.to_numeric(str(x.get("valor")).replace(",", "."), errors="coerce")
            if pd.notna(d) and pd.notna(v):
                out.append({"data": d.strftime("%Y-%m-%d"), "valor": float(v)})
    except Exception:
        return []
    return sorted(out, key=lambda r: r["data"])


def ultimos_indicador(serie: list[dict], mensal: bool = True) -> dict | None:
    """Último valor divulgado e o anterior (com o período de referência). None se a série for curta."""
    if not serie:
        return None
    u = serie[-1]
    ant = serie[-2] if len(serie) > 1 else None
    f = (lambda d: d[5:7] + "/" + d[:4]) if mensal else (lambda d: d[8:10] + "/" + d[5:7] + "/" + d[:4])
    return {"valor": u["valor"], "ref": f(u["data"]), "anterior": ant["valor"] if ant else None, "ref_anterior": f(ant["data"]) if ant else None}


def parse_focus(dados, indicador: str) -> list[dict]:
    """JSON OData do Focus (olinda.bcb.gov.br ... ExpectativaMercadoMensais / ExpectativasMercadoSelic) → [{ref, mediana, data}] mais recentes primeiro."""
    try:
        linhas = dados.get("value") if isinstance(dados, dict) else dados
        out = []
        for x in linhas or []:
            ref = x.get("DataReferencia") or x.get("Reuniao")
            med = pd.to_numeric(x.get("Mediana"), errors="coerce")
            if ref and pd.notna(med) and (not indicador or I._norm(str(x.get("Indicador") or indicador)) == I._norm(indicador)):
                out.append({"ref": str(ref), "mediana": float(med), "data": str(x.get("Data") or "")[:10]})
        return sorted(out, key=lambda r: r["data"], reverse=True)
    except Exception:
        return []


def enriquecer_eventos(eventos: list[dict], resultados: dict[str, dict], focus_ipca: list[dict], focus_selic: list[dict], agora: datetime | None = None) -> list[dict]:
    """Preenche anterior / esperado pelo mercado / divulgado, só com o que as fontes entregaram.
    - Evento FUTURO: 'anterior' = último valor divulgado; 'esperado' = mediana do Focus (IPCA do mês anterior; Selic da reunião).
    - Evento PASSADO: 'divulgado' = último valor da série (com o mês de referência, para conferência) e 'anterior' = o valor anterior a ele.
    Sem série ou sem Focus, o campo fica vazio (nunca estimado)."""
    agora = agora or datetime.now()
    out = []
    for e in eventos:
        e = dict(e)
        e["status"] = _status_evento(e["data"], agora, bool(e.get("hora")))
        ind = e.get("indicador")
        res = resultados.get(ind) if ind else None
        if e.get("reuniao") and resultados.get("Selic meta"):
            res = resultados["Selic meta"]
        if res:
            e["unidade"] = res.get("unidade")
            if e["status"] == "divulgado":
                e["divulgado"], e["anterior"] = res["valor"], res.get("anterior")
                e["referencia"] = f"último valor da série: ref. {res['ref']}"
            else:
                e["anterior"] = res["valor"]
                e["referencia"] = f"último divulgado: ref. {res['ref']}"
        if e["status"] != "divulgado":
            if ind in ("IPCA",) and focus_ipca:
                try:
                    d = pd.Timestamp(e["data"])
                    ref = (d.replace(day=1) - pd.Timedelta(days=1)).strftime("%m/%Y")
                    m = next((f for f in focus_ipca if f["ref"] == ref), None)
                    if m:
                        e["esperado"], e["unidade"] = m["mediana"], "% a.m."
                        e["observacao"] = ((e.get("observacao") or "") + f" Esperado: mediana do Boletim Focus (BC) de {m['data']} para {ref}.").strip()
                except Exception:
                    pass
            if e.get("reuniao") and focus_selic:
                m = next((f for f in focus_selic if f["ref"].upper() == e["reuniao"].upper()), None)
                if m:
                    e["esperado"], e["unidade"] = m["mediana"], "% a.a."
                    e["observacao"] = ((e.get("observacao") or "") + f" Esperado: mediana do Boletim Focus (BC) de {m['data']} para a Selic ao fim desta reunião.").strip()
        out.append(e)
    return out


def unir_eventos(*listas) -> list[dict]:
    """Junta calendários sem repetir (mesmo dia, mesmo evento e país) e ordena por data e hora."""
    vistos, out = set(), []
    for lst in listas:
        for e in lst or []:
            k = (e["data"], I._norm(e["evento"]), e["pais"])
            if k not in vistos:
                vistos.add(k)
                out.append(e)
    return sorted(out, key=lambda e: (e["data"], e.get("hora") or "99:99"))


def proximos(eventos: list[dict], agora: datetime | None = None, dias: int = 14, relevancia_min: str = "baixa") -> list[dict]:
    agora = agora or datetime.now()
    ordem = {"alta": 2, "media": 1, "baixa": 0}
    lim = agora.date() + timedelta(days=dias)
    return [e for e in eventos if agora.date() <= date.fromisoformat(e["data"]) <= lim and ordem.get(e["relevancia"], 0) >= ordem[relevancia_min]]


# =============================================================================== calendário corporativo
TIPOS_CORPORATIVOS = {"resultado": "Divulgação de resultado / balanço", "data_com": "Data com (provento)", "pagamento": "Pagamento de provento", "assembleia": "Assembleia",
                      "oferta": "Oferta pública", "desdobramento": "Desdobramento / grupamento", "vencimento": "Vencimento", "leilao": "Leilão", "societario": "Evento societário",
                      "comunicado": "Comunicado relevante"}


def eventos_proventos(ativo: str, div, splits=None, agora: datetime | None = None, meses: int = 18) -> list[dict]:
    """Proventos e desdobramentos que o Yahoo Finance REGISTRA (data ex = 'data com' + 1 pregão) para o ativo, dos últimos `meses`.
    São fatos históricos da fonte; datas futuras só aparecem se a fonte já as trouxer (normalmente não trazem)."""
    agora = agora or datetime.now()
    out = []
    corte = pd.Timestamp(agora) - pd.DateOffset(months=meses)
    try:
        for d, v in (div.items() if div is not None else []):
            if pd.Timestamp(d) >= corte and pd.notna(v):
                out.append({**novo_evento(pd.Timestamp(d).strftime("%Y-%m-%d"), f"{ativo}: provento de {float(v):,.4f} por cota/ação (data ex)", "Brasil", "outro", "media", "Yahoo Finance",
                                          None, tipo="data_com", ativo=ativo, valor=float(v)), "tipo": "data_com", "ativo": ativo})
        for d, v in (splits.items() if splits is not None else []):
            if pd.Timestamp(d) >= corte:
                out.append({**novo_evento(pd.Timestamp(d).strftime("%Y-%m-%d"), f"{ativo}: desdobramento/grupamento {v}", "Brasil", "outro", "alta", "Yahoo Finance", None), "tipo": "desdobramento", "ativo": ativo})
    except Exception:
        return out
    return sorted(out, key=lambda e: e["data"], reverse=True)


def evento_manual(tipo: str, ativo: str, data: str, descricao: str, url: str, escopo: str = "corporativo") -> dict:
    """Evento que a PESSOA informa com o link da fonte (ex.: aviso de resultado no RI, fato relevante na CVM). Sem link válido, é recusado:
    o app não registra evento sem fonte. Fica marcado como 'informado por você' e não como dado do app."""
    link = I.url_segura(url)
    if not link:
        raise ValueError("Informe o link da fonte (começando por http:// ou https://).")
    if tipo not in TIPOS_CORPORATIVOS and escopo == "corporativo":
        raise ValueError("Tipo de evento desconhecido.")
    try:
        d = pd.Timestamp(data).strftime("%Y-%m-%d")
    except Exception:
        raise ValueError("Data inválida.")
    a = re.sub(r"[^A-Za-z0-9.\-]", "", str(ativo or "")).upper()[:24]
    if not a:
        raise ValueError("Informe o ativo.")
    desc = I._limpar_texto(descricao, 160)
    if not desc:
        raise ValueError("Descreva o evento em poucas palavras.")
    rot = TIPOS_CORPORATIVOS.get(tipo, tipo)
    return {**novo_evento(d, f"{a}: {rot} — {desc}", "—", "outro", "media", "Informado por você", link, tipo=tipo, ativo=a), "tipo": tipo, "ativo": a, "manual": True, "escopo": escopo,
            "observacao": "Informado por você com este link; o app não confirmou o conteúdo."}


def eventos_vencimento_rf(titulos: list[dict]) -> list[dict]:
    """Vencimentos da renda fixa da CARTEIRA do usuário (dados dele). Entrada: [{'id','vencimento'(aaaa-mm-dd),'nome'}]."""
    out = []
    for t in titulos or []:
        try:
            d = pd.Timestamp(t["vencimento"]).strftime("%Y-%m-%d")
        except Exception:
            continue
        out.append({**novo_evento(d, f"{t.get('nome') or t['id']}: vencimento do título", "Brasil", "outro", "media", "Sua carteira de renda fixa", None), "tipo": "vencimento", "ativo": t["id"]})
    return sorted(out, key=lambda e: e["data"])


# =============================================================================== calendário de criptomoedas
HALVING_BLOCOS = 210_000
BTC_BLOCO_SEGUNDOS = 600


def proximo_halving(altura: int | None, agora: datetime | None = None) -> dict | None:
    """Próximo halving do Bitcoin pela regra do protocolo (a cada 210.000 blocos) e pela altura ATUAL do bloco (fonte externa). A data é
    ESTIMATIVA (ritmo médio de 10 min por bloco), não confirmação. Sem altura, devolve None."""
    if not isinstance(altura, int) or altura <= 0:
        return None
    agora = agora or datetime.now()
    alvo = (altura // HALVING_BLOCOS + 1) * HALVING_BLOCOS
    falta = alvo - altura
    quando = agora + timedelta(seconds=falta * BTC_BLOCO_SEGUNDOS)
    return {"bloco_alvo": alvo, "blocos_restantes": falta, "estimativa": quando.strftime("%Y-%m-%d"), "recompensa_atual_btc": 50 / 2 ** (altura // HALVING_BLOCOS),
            "recompensa_apos_btc": 50 / 2 ** (altura // HALVING_BLOCOS + 1)}


def eventos_cripto(halving: dict | None, desbloqueios: dict | None, manuais: list[dict] | None, noticias: list[dict], agora: datetime | None = None) -> list[dict]:
    """Calendário de cripto: (1) halving pela regra do protocolo (estimativa); (2) desbloqueios que a pessoa informou com fonte (Passo 9);
    (3) eventos informados com link; (4) notícias sobre eventos de rede/regulação/exchange (reportadas, não confirmadas, salvo fonte oficial)."""
    agora = agora or datetime.now()
    out = []
    if halving:
        out.append({**novo_evento(halving["estimativa"], f"Halving do Bitcoin (bloco {halving['bloco_alvo']:,}): recompensa de {halving['recompensa_atual_btc']:g} para {halving['recompensa_apos_btc']:g} BTC".replace(",", "."),
                                  "Global", "outro", "alta", "Protocolo Bitcoin (regra) + altura do bloco (mempool.space)", "https://mempool.space/", observacao=f"Data ESTIMADA: faltam {halving['blocos_restantes']:,} blocos × ~10 min. A data real varia.".replace(",", "."),
                                  estimado=True), "tipo": "halving", "ativo": "bitcoin", "confirmado": False})
    for gid, lst in (desbloqueios or {}).items():
        for ev in lst or []:
            try:
                d = pd.Timestamp(ev["data"]).strftime("%Y-%m-%d")
            except Exception:
                continue
            out.append({**novo_evento(d, f"{gid}: desbloqueio de tokens" + (f" ({ev.get('descricao')})" if ev.get("descricao") else ""), "Global", "outro", "alta", "Informado por você (Passo 9)", ev.get("fonte"),
                                      observacao="Informado por você com link da fonte."), "tipo": "desbloqueio", "ativo": gid, "confirmado": bool(ev.get("fonte"))})
    for m in manuais or []:
        out.append({**m, "confirmado": False})
    pal = ["hard fork", "mainnet", "atualizacao de rede", "network upgrade", "upgrade", "halving", "governanca", "governance", "votacao", "proposta", "listagem", "delisting", "exchange",
           "regulacao", "regulat", "etf", "sec ", "desbloqueio", "unlock", "tokenomics", "queima", "burn", "airdrop"]
    for n in noticias or []:
        if _tem(I._norm(n["titulo"]), pal) and (n.get("ativos") or n.get("origem") == "cripto"):
            out.append({**novo_evento((n.get("publicada_em") or agora.isoformat())[:10], n["titulo"], "Global", "outro", n.get("nivel", "media"), n["fonte"], n.get("url"),
                                      observacao=f"Notícia ({n.get('status')}); a data é a da publicação, não necessariamente a do evento."), "tipo": "noticia_cripto",
                        "ativo": (n.get("ativos") or [None])[0], "confirmado": n.get("fonte_nivel") == "oficial"})
    return sorted(out, key=lambda e: e["data"])


# =============================================================================== alertas
TIPOS_ALERTA_NE = {
    "noticia_urgente": "Notícia urgente", "resultado_empresa": "Resultado ou balanço de empresa", "juros": "Decisão ou mudança de juros", "indicador": "Indicador econômico",
    "dividendo": "Evento de dividendos", "comunicado": "Comunicado oficial", "cripto_evento": "Evento de criptomoeda", "noticia_ativo": "Notícia sobre ativo acompanhado",
    "regulatorio": "Alteração regulatória", "sentimento": "Mudança relevante no sentimento",
}
PARAMS_NE = {"noticia_urgente": {}, "resultado_empresa": {"dias_antes": 3}, "juros": {"dias_antes": 2}, "indicador": {"relevancia": "alta"}, "dividendo": {"dias_antes": 5},
             "comunicado": {}, "cripto_evento": {"dias_antes": 7}, "noticia_ativo": {"relevancia_min": 50}, "regulatorio": {"relevancia_min": 40}, "sentimento": {}}
CANAIS_NE = {"app": "No aplicativo"}      # e-mail e push dependem de um serviço externo que o app não tem
FREQ_NE = ("cada_atualizacao", "diaria", "semanal")


def nova_regra_ne(tipo: str, ativo: str = "*", params: dict | None = None, frequencia: str = "diaria", prioridade: str = "media", canal: str = "app", ativa: bool = True,
                  id_: str | None = None) -> dict:
    if tipo not in TIPOS_ALERTA_NE:
        raise ValueError(f"Tipo de alerta desconhecido: {tipo}")
    if frequencia not in FREQ_NE:
        raise ValueError("Frequência inválida.")
    if canal not in CANAIS_NE:
        raise ValueError("Canal indisponível: hoje só existe o aviso dentro do aplicativo (e-mail e celular exigem um serviço externo).")
    if prioridade not in I.PRIORIDADES:
        raise ValueError("Prioridade inválida.")
    p = {**PARAMS_NE[tipo], **(params or {})}
    for k in ("dias_antes", "relevancia_min"):
        if k in p:
            try:
                p[k] = max(0, min(60 if k == "dias_antes" else 100, int(p[k])))
            except Exception:
                raise ValueError(f"Valor inválido em {k}.")
    a = re.sub(r"[^A-Za-z0-9.*\-]", "", str(ativo or "*")).upper()[:24] or "*"
    base = f"ne:{tipo}:{a}:" + ",".join(f"{k}={v}" for k, v in sorted(p.items()))
    return {"id": id_ or re.sub(r"[^a-z0-9]+", "-", base.lower()).strip("-")[:90], "tipo": tipo, "ativo": a, "params": p, "frequencia": frequencia, "prioridade": prioridade,
            "canal": canal, "ativa": bool(ativa), "origem": "noticias"}


def descrever_regra_ne(r: dict) -> str:
    p = r.get("params") or {}
    det = {"resultado_empresa": lambda: f"avisar {p.get('dias_antes', 3)} dia(s) antes e quando sair", "juros": lambda: f"avisar {p.get('dias_antes', 2)} dia(s) antes da decisão e quando sair",
           "indicador": lambda: f"relevância {p.get('relevancia', 'alta')}", "dividendo": lambda: f"avisar {p.get('dias_antes', 5)} dia(s) antes",
           "cripto_evento": lambda: f"avisar {p.get('dias_antes', 7)} dia(s) antes", "noticia_ativo": lambda: f"relevância mínima {p.get('relevancia_min', 50)}",
           "regulatorio": lambda: f"relevância mínima {p.get('relevancia_min', 40)}"}.get(r["tipo"], lambda: "")()
    return f"{TIPOS_ALERTA_NE[r['tipo']]}" + (f" · {det}" if det else "")


def _escopo_ok(regra: dict, ativos_item: list[str], todos: set[str]) -> bool:
    a = regra.get("ativo", "*")
    if a == "*":
        return True
    return a.upper() in {x.upper() for x in ativos_item}


def avaliar_alertas_ne(regras: list[dict], estado: dict, agora: datetime | None = None) -> list[dict]:
    """Avalia as regras ativas. `estado`: {'noticias': grupos, 'eventos': eventos enriquecidos, 'sentimento': {'_geral'|ativo: agregado},
    'acompanhados': [ids da carteira e favoritos]}. Só dispara com dado presente; texto especulativo ou de fonte desconhecida não dispara
    alerta de urgência. A assinatura é o id da notícia/evento, então o mesmo fato não vira dois alertas."""
    agora = agora or datetime.now()
    out = []
    grupos = [g for g in estado.get("noticias") or [] if not g.get("desatualizada")]
    eventos = estado.get("eventos") or []
    acomp = {str(x).upper() for x in estado.get("acompanhados") or []}

    def disparo(r, ativo, titulo, texto, assin, quando, fonte=None, url=None, extra=None):
        out.append({"regra_id": r["id"], "ativo": ativo or "mercado", "tipo": r["tipo"], "prioridade": r["prioridade"], "titulo": titulo, "texto": texto, "valor": None,
                    "assinatura": str(assin), "data": agora.isoformat(timespec="minutes"), "detectado_em": quando, "dados": {"fonte": fonte, "url": url, **(extra or {})}, "origem": "noticias"})

    def dias_ate(e):
        return (date.fromisoformat(e["data"]) - agora.date()).days

    for r in regras or []:
        if not r.get("ativa", True):
            continue
        t, P = r["tipo"], r.get("params") or {}
        if t in ("noticia_urgente", "resultado_empresa", "dividendo", "comunicado", "noticia_ativo", "regulatorio", "cripto_evento"):
            for g in grupos:
                if not _escopo_ok(r, g.get("ativos") or [], acomp):
                    continue
                if g.get("especulativo") and g["melhor_fonte"] != "oficial":
                    continue
                cats = set(g.get("categorias") or [])
                ok = ((t == "noticia_urgente" and g.get("urgente") and g["melhor_fonte"] != "nao_verificada")
                      or (t == "resultado_empresa" and "Resultados financeiros" in cats and g["relevancia"] >= 35)
                      or (t == "dividendo" and "Dividendos" in cats and g["relevancia"] >= 30)
                      or (t == "comunicado" and "Comunicado oficial" in g.get("importantes", []) and g["melhor_fonte"] == "oficial")
                      or (t == "noticia_ativo" and g.get("ativos") and (not acomp or {x.upper() for x in g["ativos"]} & acomp) and g["relevancia"] >= int(P.get("relevancia_min", 50)))
                      or (t == "regulatorio" and ("Mudança regulatória" in g.get("importantes", []) or "Mudanças regulatórias" in cats) and g["relevancia"] >= int(P.get("relevancia_min", 40)))
                      or (t == "cripto_evento" and "Problema em exchange ou protocolo" in g.get("importantes", [])))
                if ok:
                    disparo(r, (g.get("ativos") or [None])[0], f"{TIPOS_ALERTA_NE[t]}: {g['titulo'][:110]}", f"{g['fonte']} ({g['status']}). {g['n_fontes']} fonte(s) · relevância {g['nivel']}.",
                            g["id"], g.get("publicada_em"), g["fonte"], g.get("url"))
        if t in ("juros", "indicador", "resultado_empresa", "dividendo", "cripto_evento"):
            for e in eventos:
                if not _escopo_ok(r, [e.get("ativo")] if e.get("ativo") else [], acomp) and r.get("ativo", "*") != "*":
                    continue
                d = dias_ate(e)
                cat, tipo_e = e.get("categoria"), e.get("tipo")
                if t == "juros" and cat == "juros":
                    if e["status"] == "hoje" or 0 < d <= int(P.get("dias_antes", 2)) or (e["status"] == "divulgado" and d >= -1):
                        rot = {"hoje": "acontece hoje", "futuro": f"em {d} dia(s)", "divulgado": "já foi realizada"}[e["status"]]
                        disparo(r, None, f"{e['evento']} — {rot}", f"{e['pais']} · {e['data']}" + (f" · esperado {e['esperado']}{e.get('unidade') or ''}" if e.get("esperado") is not None else ""),
                                f"{e['id']}:{e['status']}", e["data"], e["fonte"], e.get("url"))
                elif t == "indicador" and cat in ("inflacao", "atividade", "emprego"):
                    ordem = {"alta": 2, "media": 1, "baixa": 0}
                    if ordem[e["relevancia"]] >= ordem.get(P.get("relevancia", "alta"), 2) and (e["status"] == "hoje" or (e["status"] == "divulgado" and d >= -1)):
                        disparo(r, None, f"{e['evento']} — {'sai hoje' if e['status'] == 'hoje' else 'divulgado'}",
                                f"{e['pais']} · {e['data']}" + (f" · resultado {e['divulgado']}{e.get('unidade') or ''}" if e.get("divulgado") is not None else "")
                                + (f" · esperado {e['esperado']}{e.get('unidade') or ''}" if e.get("esperado") is not None else ""), f"{e['id']}:{e['status']}", e["data"], e["fonte"], e.get("url"))
                elif t in ("resultado_empresa", "dividendo") and e.get("manual"):
                    alvo = {"resultado_empresa": ("resultado",), "dividendo": ("data_com", "pagamento")}[t]
                    if tipo_e in alvo and (e["status"] == "hoje" or 0 < d <= int(P.get("dias_antes", 3))):
                        disparo(r, e.get("ativo"), e["evento"], f"{e['data']} · informado por você", f"{e['id']}", e["data"], e["fonte"], e.get("url"))
                elif t == "cripto_evento" and tipo_e in ("halving", "desbloqueio", "noticia_cripto") and e["status"] != "divulgado" and 0 <= d <= int(P.get("dias_antes", 7)) and tipo_e != "noticia_cripto":
                    disparo(r, e.get("ativo"), e["evento"], e.get("observacao") or "", f"{e['id']}", e["data"], e["fonte"], e.get("url"))
        if t == "sentimento":
            for chave, ag in (estado.get("sentimento") or {}).items():
                if r["ativo"] != "*" and chave.upper() != r["ativo"].upper():
                    continue
                for tipo_s, txt in ag.get("sinais") or []:
                    if tipo_s in ("aumento_negativas", "aumento_positivas", "mudanca"):
                        disparo(r, None if chave == "_geral" else chave, f"Sentimento {'do mercado' if chave == '_geral' else 'de ' + chave}: {tipo_s.replace('_', ' ')}", txt,
                                f"{chave}:{tipo_s}:{agora.date().isoformat()}", agora.date().isoformat(), "Contagem de notícias (Passo 15)")
    return out


# =============================================================================== carteira
CENARIOS_MACRO = [("juros_alta", "Alta de juros"), ("juros_queda", "Queda de juros"), ("inflacao_alta", "Inflação acima do esperado"), ("dolar_alta", "Alta do dólar"),
                  ("dolar_queda", "Queda do dólar"), ("petroleo_alta", "Alta do petróleo"), ("risco_fiscal", "Risco fiscal"), ("geopolitica", "Evento geopolítico")]


def exposicao_macro(posicoes: list[dict]) -> list[dict]:
    """Para cada cenário macro, quanto da carteira (em % do total) PODE ser beneficiado, pressionado ou ter efeito misto, segundo as regras de
    exposição. 'Sem regra' = sem caminho conhecido de exposição (ou falta o setor do ativo para aplicar a regra setorial). É mapa de sensibilidade,
    não previsão."""
    tot = sum(float(p.get("peso") or 0) for p in posicoes) or 0.0
    out = []
    for rid, nome in CENARIOS_MACRO:
        regra = REGRA_POR_ID[rid]
        acc = {B: 0.0, P: 0.0, M: 0.0}
        pior = []
        livre = 0.0
        for a in posicoes:
            w = float(a.get("peso") or 0)
            ef = next((e for e in regra["efeitos"] if _casa_alvo(e["alvo"], a)), None)
            if ef is None:
                livre += w
            else:
                acc[ef["direcao"]] += w
                if ef["direcao"] == P:
                    pior.append((w, a["id"]))
        k = (100.0 / tot) if tot else 0.0
        out.append({"cenario": nome, "regra": rid, "beneficia_pct": acc[B] * k, "pressiona_pct": acc[P] * k, "misto_pct": acc[M] * k, "sem_regra_pct": livre * k,
                    "ativos_pressionados": [i for _, i in sorted(pior, reverse=True)[:5]]})
    return out


def impactos_multiplos(impactos: list[dict], posicoes: list[dict], minimo: int = 2) -> list[dict]:
    """Acontecimentos que atingem VÁRIAS posições ao mesmo tempo (com o peso somado). Só conta posições da carteira."""
    ids = {p["id"]: float(p.get("peso") or 0) for p in posicoes}
    out = []
    for im in impactos:
        afet = [a for a in im["ativos"] if a["id"] in ids]
        if len(afet) >= minimo:
            out.append({**im, "ativos_carteira": afet, "peso_total_pct": sum(ids[a["id"]] for a in afet)})
    return sorted(out, key=lambda x: -x["peso_total_pct"])


def resumo_carteira(posicoes: list[dict], grupos: list[dict], eventos: list[dict], impactos: list[dict], sentimento: dict | None = None,
                    agora: datetime | None = None) -> dict:
    """Resumo diário da carteira (Passo 12 × Passo 15): notícias por posição, próximos eventos, riscos, exposição macro e acontecimentos
    que afetam várias posições. Só lê; não altera posições nem envia ordens."""
    agora = agora or datetime.now()
    ids = {p["id"].upper() for p in posicoes}
    por_ativo: dict[str, list[dict]] = {}
    for g in grupos:
        if g.get("desatualizada"):
            continue
        for a in g.get("ativos") or []:
            if a.upper() in ids:
                por_ativo.setdefault(a.upper(), []).append(g)
    prox = [e for e in eventos if e.get("status") in ("futuro", "hoje") and (e.get("ativo", "").upper() in ids or (not e.get("ativo") and e["relevancia"] == "alta"))
            and (date.fromisoformat(e["data"]) - agora.date()).days <= 30][:15]
    riscos = []
    for g in grupos:
        if g.get("desatualizada") or (g.get("especulativo") and g["melhor_fonte"] != "oficial"):
            continue
        if any(a.upper() in ids for a in g.get("ativos") or []) and (g.get("urgente") or set(g.get("importantes", [])) & {"Crise empresarial", "Fraude ou investigação", "Problema de liquidez", "Risco de crédito"}):
            riscos.append(f"{', '.join(g['ativos'])}: {g['titulo']} ({g['fonte']}, {(g.get('publicada_em') or 'data n/d')[:10]}; {g['status']})")
    multi = impactos_multiplos(impactos, posicoes)
    exp = exposicao_macro(posicoes)
    linhas = []
    n_not = sum(len(v) for v in por_ativo.values())
    linhas.append(f"{n_not} notícia(s) recente(s) citando {len(por_ativo)} de {len(posicoes)} posição(ões)." if n_not else "Nenhuma notícia recente citando diretamente suas posições nas fontes consultadas.")
    if prox:
        linhas.append(f"{len(prox)} evento(s) nos próximos 30 dias; o primeiro: {prox[0]['evento']} em {prox[0]['data']}.")
    if riscos:
        linhas.append(f"{len(riscos)} notícia(s) de risco sobre posições.")
    if multi:
        m = multi[0]
        linhas.append(f"Acontecimento que pode afetar várias posições: {m['titulo']} — {len(m['ativos_carteira'])} posições, {m['peso_total_pct']:.0f}% da carteira.")
    return {"data": agora.date().isoformat(), "n_posicoes": len(posicoes), "noticias_por_ativo": {k: v[:3] for k, v in por_ativo.items()}, "proximos_eventos": prox, "riscos": riscos,
            "exposicao": exp, "multiplos": multi[:5], "linhas": linhas, "sentimento": (sentimento or {}).get("_carteira")}


# =============================================================================== assistente de notícias e eventos
_GATILHO_NOTICIA = re.compile(r"\b(noticia|noticias|manchete|evento|eventos|calendario|agenda|copom|fomc|selic|ipca|inpc|pib|payroll|fed|juros|inflacao|dolar|cambio|sentimento|fonte|fontes|"
                              r"contradi\w*|divergen\w*|impact\w*|afet\w*|consequenc\w*|aconteceu|aconteceram|resum\w*|halving|desbloque\w*|dividendo\w*|balanco|resultado)\b", re.I)


def eh_pergunta_noticia(pergunta: str) -> bool:
    return bool(_GATILHO_NOTICIA.search(I._norm(pergunta)))


def _fonte_txt(g: dict) -> str:
    return f"{g.get('fonte', 'fonte n/d')}, {(g.get('publicada_em') or 'data n/d')[:10]}" + (f" — {g['url']}" if g.get("url") else "")


def _linha_grupo(g: dict) -> str:
    extra = []
    if g.get("n_fontes", 1) > 1:
        extra.append(f"{g['n_fontes']} fontes")
    if g.get("contraditoria"):
        extra.append("fontes divergem no tom")
    if g.get("numeros_divergentes"):
        extra.append("números diferentes entre fontes")
    return f"{g['titulo']} ({_fonte_txt(g)}; {g['status']}{'; ' + ', '.join(extra) if extra else ''})"


def _achar_ativo(q: str, ctx: dict):
    nomes = set()
    for g in ctx.get("noticias") or []:
        nomes.update(g.get("ativos") or [])
    for a in ctx.get("ativos") or []:
        nomes.add(a.get("id"))
    for a in sorted(filter(None, nomes), key=len, reverse=True):
        if re.search(r"(?<![a-z0-9])" + re.escape(I._norm(a)) + r"(?![a-z0-9])", q):
            return a
    return None


def responder_noticias(pergunta: str, ctx: dict | None) -> dict:
    """Responde SÓ com o que está em `ctx`: {'noticias': grupos, 'eventos': eventos enriquecidos, 'impactos': [...], 'sentimento': {...}, 'carteira': resumo_carteira,
    'historico': {'Selic meta': [...]}, 'ativos': [...], 'gerado_em', 'fontes_status'}. Separa FATOS (publicações, datas oficiais, valores divulgados)
    de INTERPRETAÇÕES (tom, impacto por regra) e cita as fontes. Recusa compra/venda. Sem dado, diz que não tem."""
    ctx = ctx or {}
    q = I._norm(pergunta)
    grupos = [g for g in ctx.get("noticias") or [] if not g.get("desatualizada")]
    eventos = ctx.get("eventos") or []
    gerado = ctx.get("gerado_em")
    cab = f"Notícias e eventos lidos em {gerado[:16].replace('T', ' ')}" if gerado else "Sem leitura de notícias carregada"
    cons = []
    if grupos:
        cons.append(f"{len(grupos)} acontecimento(s) noticiado(s)")
    if eventos:
        cons.append(f"{len(eventos)} evento(s) de calendário")
    rodape = f"Consultei: {', '.join(cons)}." if cons else "Não consultei nenhum dado: a Central de notícias ainda não foi atualizada."
    base = {"limite": "Resumo de fontes públicas e regras simples, não recomendação. Impactos são possibilidades, não previsões.", "referencia": cab, "consultado": rodape}

    def resp(texto, fatos=None, interp=None, fontes=None, falta=False):
        return {**base, "texto": texto, "fatos": fatos or [], "interpretacoes": interp or [], "fontes": list(dict.fromkeys(fontes or []))[:12], "sem_dados": falta,
                "linhas": [f"Fato: {x}" for x in (fatos or [])] + [f"Interpretação: {x}" for x in (interp or [])]}

    if not q:
        return resp("Escreva uma pergunta sobre notícias, eventos, calendário, sentimento ou impacto.", falta=True)
    if I._PEDIDO_INDICACAO.search(q):
        return resp("Eu não indico compra ou venda. Posso resumir o que foi noticiado, mostrar os próximos eventos e explicar por que um acontecimento pode afetar seus ativos, com as fontes.")
    if not grupos and not eventos:
        return resp("Ainda não tenho notícias nem eventos carregados. Atualize a Central de notícias para eu consultar.", falta=True)
    ativo = _achar_ativo(q, ctx)

    if re.search(r"contradi|divergen|fontes diferentes|comparar fontes|compare as fontes|informacoes conflit", q):
        cs = [g for g in grupos if g.get("contraditoria") or g.get("numeros_divergentes")]
        if not cs:
            return resp("Nas notícias lidas não encontrei acontecimentos em que as fontes se contradigam.", [f"{len(grupos)} acontecimento(s) comparados por fonte e tom."], fontes=[])
        return resp(f"Encontrei {len(cs)} acontecimento(s) com fontes divergentes.", [_linha_grupo(g) for g in cs[:5]],
                    ["A divergência pode ser de enfoque ou de data; leia as fontes originais antes de concluir."], [_fonte_txt(g) for g in cs[:5]])

    if re.search(r"historic|passado|ciclo|ja aconteceu|compar\w* .*cenario|cenario atual", q):
        h = (ctx.get("historico") or {}).get("Selic meta") or []
        if len(h) < 3:
            return resp("Não tenho série histórica carregada para comparar o cenário atual com o passado. Atualize a Central de notícias (a série da Selic vem do Banco Central).", falta=True)
        atual = h[-1]
        antes = {n: next((r for r in reversed(h) if r["data"] <= (pd.Timestamp(atual["data"]) - pd.DateOffset(years=n)).strftime("%Y-%m-%d")), None) for n in (1, 3, 5)}
        fatos = [f"Meta da Selic atual: {atual['valor']:.2f}% a.a. (série do Banco Central, {atual['data']})."]
        for n, r in antes.items():
            if r:
                fatos.append(f"Há {n} ano(s) ({r['data']}): {r['valor']:.2f}% a.a. (diferença de {atual['valor'] - r['valor']:+.2f} p.p.).")
        maxi = max(h, key=lambda r: r["valor"])
        mini = min(h, key=lambda r: r["valor"])
        fatos.append(f"No período da série carregada, a máxima foi {maxi['valor']:.2f}% ({maxi['data']}) e a mínima {mini['valor']:.2f}% ({mini['data']}).")
        return resp("Comparação do nível atual da Selic com o histórico carregado.", fatos, ["Ciclos passados não se repetem de forma previsível: o contexto (inflação, câmbio, fiscal) muda."],
                    ["Banco Central do Brasil — SGS série 432 — https://api.bcb.gov.br/dados/serie/bcdata.sgs.432/dados"])

    if re.search(r"calend|proxim|agenda|quando|copom|fomc|ipca|inpc|pib|payroll|decisao|divulg", q):
        ev = [e for e in eventos if e["status"] in ("futuro", "hoje")]
        if re.search(r"copom|selic", q):
            ev = [e for e in ev if "Copom" in e["evento"]] or ev
        elif re.search(r"fomc|fed\b|juros americanos", q):
            ev = [e for e in ev if "FOMC" in e["evento"]] or ev
        elif re.search(r"ipca|inpc|inflacao", q):
            ev = [e for e in ev if e["categoria"] == "inflacao"] or ev
        elif re.search(r"payroll|emprego", q):
            ev = [e for e in ev if e["categoria"] == "emprego"] or ev
        elif re.search(r"pib", q):
            ev = [e for e in ev if "PIB" in e["evento"]] or ev
        if ativo:
            ev = [e for e in ev if (e.get("ativo") or "").upper() == ativo.upper()] or ev
        if not ev:
            return resp("Não há eventos futuros nos calendários carregados para essa pergunta.", falta=True)
        ev = sorted(ev, key=lambda e: (e["data"], e.get("hora") or ""))[:6]
        fatos = [f"{e['data']}{(' ' + e['hora']) if e.get('hora') else ''} · {e['pais']} · {e['evento']}" + (f" · anterior {e['anterior']}{e.get('unidade') or ''}" if e.get("anterior") is not None else "")
                 + (f" · esperado pelo mercado {e['esperado']}{e.get('unidade') or ''} (Focus/BC)" if e.get("esperado") is not None else "") + f" [{e['fonte']}]" for e in ev]
        return resp(f"Próximos eventos ({len(ev)}):", fatos, ["A reação do mercado costuma depender do resultado frente à expectativa, não do evento em si."], [f"{e['fonte']} — {e.get('url') or ''}" for e in ev])

    if re.search(r"carteira|minhas posicoes|meus ativos|minha posicao", q) and ctx.get("carteira"):
        c = ctx["carteira"]
        fatos = list(c["linhas"]) + [f"{k}: {_linha_grupo(v[0])}" for k, v in list(c["noticias_por_ativo"].items())[:4]]
        interp = [f"{x['cenario']}: pode pressionar {x['pressiona_pct']:.0f}% e pode beneficiar {x['beneficia_pct']:.0f}% da carteira (por regras de exposição)." for x in c["exposicao"] if x["pressiona_pct"] or x["beneficia_pct"]][:4]
        return resp("Situação da carteira frente a notícias e eventos:", fatos, interp, [_fonte_txt(v[0]) for v in c["noticias_por_ativo"].values()])

    if re.search(r"sentimento|otimis|pessimis", q):
        sg = (ctx.get("sentimento") or {})
        ag = sg.get(ativo) if ativo else sg.get("_geral")
        if not ag or not ag["recente"]["total"]:
            return resp("Não há notícias suficientes para medir o sentimento agora.", falta=True)
        r = ag["recente"]
        fatos = [f"Últimos dias: {r['positivo']} positivas, {r['negativo']} negativas, {r['neutro']} neutras e {r['incerto']} incertas (de {r['total']})."]
        return resp(f"Sentimento {'de ' + ativo if ativo else 'geral'} nas notícias lidas.", fatos, [t for _, t in ag["sinais"]] + [ag["aviso"]], [])

    if re.search(r"impact\w*|afet\w*|consequenc\w*|efeito", q):
        imp = ctx.get("impactos") or []
        if ativo:
            imp = [i for i in imp if any(a["id"].upper() == ativo.upper() for a in i["ativos"])]
        elif re.search(r"selic|juros|copom", q):
            imp = [i for i in imp if i.get("regra", "").startswith("juros")]
        elif re.search(r"dolar|cambio", q):
            imp = [i for i in imp if i.get("regra", "").startswith("dolar")]
        elif re.search(r"inflacao|ipca", q):
            imp = [i for i in imp if i.get("regra", "").startswith("inflacao")]
        if not imp:
            return resp("Não encontrei, nas notícias e eventos lidos, acontecimentos com impacto mapeado para essa pergunta.", falta=True)
        imp = sorted(imp, key=lambda i: -i["relevancia"])[:3]
        fatos = [f"{i['titulo']} ({i.get('fonte') or 'calendário'}, {(i.get('data') or '')[:10]})" for i in imp]
        interp = []
        for i in imp:
            exemplos = "; ".join(f"{a['id']} {a['direcao']}" for a in i["ativos"][:4]) or "sem ativo seu mapeado"
            interp.append(f"{i.get('nome_regra') or 'Menção direta'}: {i['justificativa']} {exemplos}. Horizonte provável: {i['horizonte']}. Confiança da associação: {i['confianca']}.")
        return resp("Possíveis impactos (interpretação por regras):", fatos, interp, [f"{i.get('fonte')} — {i.get('url') or ''}" for i in imp])

    if re.search(r"risco|urgente|crise|fraude", q):
        rs = [g for g in grupos if g.get("urgente") or set(g.get("importantes", [])) & {"Crise empresarial", "Fraude ou investigação", "Problema de liquidez", "Risco de crédito", "Geopolítica"}]
        rs = [g for g in rs if not (g.get("especulativo") and g["melhor_fonte"] != "oficial")]
        if not rs:
            return resp("Nas notícias lidas não há acontecimentos de risco ou urgentes com fonte confirmada.", [f"{len(grupos)} acontecimento(s) verificados."], fontes=[])
        return resp(f"{len(rs)} acontecimento(s) de risco ou urgentes:", [_linha_grupo(g) for g in rs[:5]], ["Risco noticiado não significa perda; avalie o que a fonte confirma."], [_fonte_txt(g) for g in rs[:5]])

    alvo = [g for g in grupos if ativo and ativo.upper() in {a.upper() for a in g.get("ativos", [])}] if ativo else grupos
    if ativo and not alvo:
        return resp(f"Não encontrei notícias recentes sobre {ativo} nas fontes lidas.", falta=True)
    top = sorted(alvo, key=lambda g: -g["relevancia"])[:5]
    interp = []
    if ativo:
        ag = (ctx.get("sentimento") or {}).get(ativo)
        if ag and ag["recente"]["total"]:
            r = ag["recente"]
            interp.append(f"Tom das notícias sobre {ativo}: {r['positivo']} positivas, {r['negativo']} negativas ({r['total']} no total); descreve a cobertura, não o preço.")
    return resp(f"Principais notícias{' sobre ' + ativo if ativo else ''}:", [_linha_grupo(g) for g in top], interp, [_fonte_txt(g) for g in top])


def relatorio_md(ctx: dict, titulo: str = "Notícias e eventos") -> str:
    """Relatório em Markdown com data, fontes e a separação entre fato e interpretação."""
    L = [f"# {titulo}", f"_Gerado em {(ctx.get('gerado_em') or '')[:16].replace('T', ' ')} — {AVISO_LEGAL}_", ""]
    L += ["## Principais notícias (fatos publicados)"]
    for g in sorted(ctx.get("noticias") or [], key=lambda g: -g["relevancia"])[:10]:
        L.append(f"- {I.escapar_md(g['titulo'])} — {g['fonte']}, {(g.get('publicada_em') or 'data n/d')[:10]} ({g['status']}) {g.get('url') or ''}")
    L += ["", "## Próximos eventos"]
    for e in [e for e in ctx.get("eventos") or [] if e["status"] in ("futuro", "hoje")][:12]:
        L.append(f"- {e['data']} {e.get('hora') or ''} · {e['pais']} · {e['evento']} [{e['fonte']}]")
    L += ["", "## Possíveis impactos (interpretação, não previsão)"]
    for i in sorted(ctx.get("impactos") or [], key=lambda i: -i["relevancia"])[:6]:
        L.append(f"- {i['titulo']}: {i['justificativa']} Confiança {i['confianca']}.")
    return "\n".join(L)


# =============================================================================== país e classe (filtros)
PAISES = {"Brasil": ["brasil", "brasileir", "copom", "selic", "ibovespa", "b3", "ipca", "petrobras", "banco central do brasil", "bcb", "ibge", "real "],
          "Estados Unidos": ["eua", "estados unidos", "federal reserve", "fed ", "wall street", "dow jones", "nasdaq", "s&p", "treasury", "casa branca", "norte-americ", "u.s."],
          "China": ["china", "chinesa", "chines", "pequim"], "Europa": ["europa", "europeu", "bce", "zona do euro", "uniao europeia", "alemanha", "franca"],
          "Argentina": ["argentina"], "Japão": ["japao", "japones", "boj"], "Reino Unido": ["reino unido", "londres", "banco da inglaterra"]}


def paises_do_texto(texto: str, padrao: str | None = None) -> list[str]:
    t = " " + I._norm(texto) + " "
    achados = [p for p, kws in PAISES.items() if any(" " + I._norm(k).strip() in t for k in kws)]
    return achados or ([padrao] if padrao else ["Global"])
