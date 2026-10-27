"""
Recursos do Painel B3: catálogo de empresas, busca por nome, logos, perfis do investidor
e critérios do buscador de oportunidades.

Módulo sem dependência do Streamlit (pode ser testado isoladamente).
"""

from __future__ import annotations

import base64
import difflib
import re
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor

import requests

# ------------------------------------------------------------------ catálogo
# nome | tickers (o primeiro é o principal) | setor | domínio do site (logo reserva) | apelidos de busca
_CATALOGO_TXT = """
Petrobras|PETR4 PETR3|Petróleo e Gás|petrobras.com.br|petroleo oil
PRIO|PRIO3|Petróleo e Gás|prio3.com.br|petrorio
Vibra Energia|VBBR3|Petróleo e Gás|vibraenergia.com.br|br distribuidora
Ultrapar|UGPA3|Petróleo e Gás|ultra.com.br|ipiranga ultragaz
Brava Energia|BRAV3|Petróleo e Gás|bravaenergia.com.br|3r petroleum petroreconcavo
Cosan|CSAN3|Petróleo e Gás|cosan.com.br|rumo moove
Raízen|RAIZ4|Petróleo e Gás|raizen.com.br|shell etanol
Axia Energia (ex-Eletrobras)|AXIA3 AXIA6|Energia Elétrica|eletrobras.com|eletrobras elet3
Taesa|TAEE11|Energia Elétrica|taesa.com.br|transmissao
Equatorial|EQTL3|Energia Elétrica|equatorialenergia.com.br|distribuidora
CPFL Energia|CPFE3|Energia Elétrica|cpfl.com.br|
Energisa|ENGI11|Energia Elétrica|energisa.com.br|
Engie Brasil|EGIE3|Energia Elétrica|engie.com.br|
Cemig|CMIG4 CMIG3|Energia Elétrica|cemig.com.br|minas gerais
Copel|CPLE3|Energia Elétrica|copel.com|parana
Neoenergia|NEOE3|Energia Elétrica|neoenergia.com|
Auren Energia|AURE3|Energia Elétrica|aurenenergia.com.br|
Alupar|ALUP11|Energia Elétrica|alupar.com.br|transmissao
ISA Energia|ISAE4|Energia Elétrica|isaenergia.com.br|cteep
Sabesp|SBSP3|Saneamento|sabesp.com.br|agua esgoto
Copasa|CSMG3|Saneamento|copasa.com.br|agua esgoto
Sanepar|SAPR11 SAPR4|Saneamento|sanepar.com.br|agua esgoto
Itaú Unibanco|ITUB4 ITUB3|Bancos|itau.com.br|itau
Bradesco|BBDC4 BBDC3|Bancos|bradesco.com.br|
Banco do Brasil|BBAS3|Bancos|bb.com.br|bb
Santander Brasil|SANB11 SANB4|Bancos|santander.com.br|
BTG Pactual|BPAC11|Bancos|btgpactual.com|
Itaúsa|ITSA4 ITSA3|Bancos|itausa.com.br|holding itau
Banco Inter|INBR32|Bancos|inter.co|inter
Nubank|ROXO34|Bancos|nubank.com.br|nu holdings
Banrisul|BRSR6|Bancos|banrisul.com.br|
Banco Pan|BPAN4|Bancos|bancopan.com.br|
Banco ABC Brasil|ABCB4|Bancos|abcbrasil.com.br|
XP Inc|XPBR31|Seguros e Serviços Financeiros|xpinc.com|corretora
B3|B3SA3|Seguros e Serviços Financeiros|b3.com.br|bolsa
BB Seguridade|BBSE3|Seguros e Serviços Financeiros|bbseguridade.com.br|seguros
Caixa Seguridade|CXSE3|Seguros e Serviços Financeiros|caixaseguridade.com.br|seguros
Porto Seguro|PSSA3|Seguros e Serviços Financeiros|portoseguro.com.br|seguros
Vale|VALE3|Mineração e Siderurgia|vale.com|minerio de ferro
CSN|CSNA3|Mineração e Siderurgia|csn.com.br|siderurgica nacional
CSN Mineração|CMIN3|Mineração e Siderurgia|csnmineracao.com.br|minerio
Gerdau|GGBR4 GGBR3|Mineração e Siderurgia|gerdau.com|aco
Metalúrgica Gerdau|GOAU4|Mineração e Siderurgia|gerdau.com|aco
Usiminas|USIM5|Mineração e Siderurgia|usiminas.com|aco
Ferbasa|FESA4|Mineração e Siderurgia|ferbasa.com.br|
Suzano|SUZB3|Papel e Celulose|suzano.com.br|
Klabin|KLBN11 KLBN4|Papel e Celulose|klabin.com.br|
Braskem|BRKM5|Química|braskem.com.br|petroquimica
Unipar|UNIP6|Química|unipar.com|
Magazine Luiza|MGLU3|Varejo|magazineluiza.com.br|magalu
Lojas Renner|LREN3|Varejo|lojasrenner.com.br|renner
C&A|CEAB3|Varejo|cea.com.br|
Azzas 2154|AZZA3|Varejo|azzas2154.com.br|arezzo soma
Casas Bahia|BHIA3|Varejo|casasbahia.com.br|via varejo
Assaí|ASAI3|Varejo|assai.com.br|atacarejo
Pão de Açúcar|PCAR3|Varejo|gpabr.com|gpa
Carrefour Brasil|CRFB3|Varejo|carrefour.com.br|atacadao
Raia Drogasil|RADL3|Varejo|rd.com.br|farmacia
Vivara|VIVA3|Varejo|vivara.com.br|joias
Lojas Quero-Quero|LJQQ3|Varejo|lojasqueroquero.com.br|
Grupo Mateus|GMAT3|Varejo|grupomateus.com.br|supermercado
Smart Fit|SMFT3|Consumo|smartfit.com.br|academia
Natura|NATU3|Consumo|natura.com.br|cosmeticos
Ambev|ABEV3|Alimentos e Bebidas|ambev.com.br|cerveja
JBS|JBSS3|Alimentos e Bebidas|jbs.com.br|carne frango
MBRF (Marfrig + BRF)|MBRF3|Alimentos e Bebidas|mbrf.com|marfrig brf sadia perdigao
Minerva|BEEF3|Alimentos e Bebidas|minervafoods.com|carne
M. Dias Branco|MDIA3|Alimentos e Bebidas|mdiasbranco.com.br|massas biscoitos
Camil|CAML3|Alimentos e Bebidas|camil.com.br|arroz feijao
Cury|CURY3|Construção e Imobiliário|cury.net|
Direcional|DIRR3|Construção e Imobiliário|direcional.com.br|
MRV|MRVE3|Construção e Imobiliário|mrv.com.br|
Cyrela|CYRE3|Construção e Imobiliário|cyrela.com.br|
Eztec|EZTC3|Construção e Imobiliário|eztec.com.br|
Plano&Plano|PLPL3|Construção e Imobiliário|planoeplano.com.br|
Multiplan|MULT3|Construção e Imobiliário|multiplan.com.br|shopping
Iguatemi|IGTI11|Construção e Imobiliário|iguatemi.com.br|shopping
Allos|ALOS3|Construção e Imobiliário|allos.co|shopping
Localiza|RENT3|Transporte e Logística|localiza.com|aluguel de carros
Movida|MOVI3|Transporte e Logística|movida.com.br|aluguel de carros
Vamos|VAMO3|Transporte e Logística|vamos.com.br|caminhoes
Rumo|RAIL3|Transporte e Logística|rumolog.com|ferrovia
Motiva (ex-CCR)|MOTV3|Transporte e Logística|motiva.com.br|ccr rodovias ccro3
Ecorodovias|ECOR3|Transporte e Logística|ecorodovias.com.br|rodovias
Santos Brasil|STBP3|Transporte e Logística|santosbrasil.com.br|porto
WEG|WEGE3|Indústria e Bens de Capital|weg.net|motores
Embraer|EMBR3|Indústria e Bens de Capital|embraer.com|avioes
Randon|RAPT4|Indústria e Bens de Capital|randon.com.br|
Marcopolo|POMO4|Indústria e Bens de Capital|marcopolo.com.br|onibus
Tupy|TUPY3|Indústria e Bens de Capital|tupy.com.br|
Romi|ROMI3|Indústria e Bens de Capital|romi.com|
Rede D'Or|RDOR3|Saúde|rededorsaoluiz.com.br|hospitais
Hapvida|HAPV3|Saúde|hapvida.com.br|plano de saude
Fleury|FLRY3|Saúde|fleury.com.br|exames
Dasa|DASA3|Saúde|dasa.com.br|exames
Odontoprev|ODPV3|Saúde|odontoprev.com.br|dentista
Hypera|HYPE3|Saúde|hypera.com.br|farmaceutica
Cogna|COGN3|Educação|cogna.com.br|kroton
YDUQS|YDUQ3|Educação|yduqs.com.br|estacio
Ser Educacional|SEER3|Educação|sereducacional.com|
Vivo (Telefônica Brasil)|VIVT3|Telecom e Tecnologia|vivo.com.br|telefonica
TIM|TIMS3|Telecom e Tecnologia|tim.com.br|
TOTVS|TOTS3|Telecom e Tecnologia|totvs.com|software
Locaweb|LWSA3|Telecom e Tecnologia|locaweb.com.br|
Intelbras|INTB3|Telecom e Tecnologia|intelbras.com|
Positivo|POSI3|Telecom e Tecnologia|positivotecnologia.com.br|
SLC Agrícola|SLCE3|Agronegócio|slcagricola.com.br|soja algodao
São Martinho|SMTO3|Agronegócio|saomartinho.com.br|acucar etanol
3tentos|TTEN3|Agronegócio|3tentos.com.br|soja
BrasilAgro|AGRO3|Agronegócio|brasil-agro.com|terras
"""

POPULARES = ["PETR4", "VALE3", "ITUB4", "BBAS3", "WEGE3", "ABEV3", "B3SA3", "SUZB3"]
REGEX_TICKER = re.compile(r"[A-Z]{4}\d{1,2}")


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", str(s).lower())
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def _carregar() -> list[dict]:
    itens = []
    for linha in _CATALOGO_TXT.strip().splitlines():
        p = [x.strip() for x in linha.split("|")]
        if len(p) < 4:
            continue
        nome, tks, setor, dominio = p[:4]
        alias = p[4] if len(p) > 4 else ""
        texto = _norm(" ".join([nome, alias, setor, tks]))
        itens.append({
            "nome": nome, "tickers": tks.split(), "setor": setor, "dominio": dominio,
            "ticker": tks.split()[0],
            "_nome": _norm(nome + " " + alias),
            "_palavras": set(re.findall(r"[a-z0-9]+", texto)),
        })
    itens.sort(key=lambda e: _norm(e["nome"]))
    return itens


CATALOGO = _carregar()
POR_TICKER = {t: e for e in CATALOGO for t in e["tickers"]}
TODOS_TICKERS = [t for e in CATALOGO for t in e["tickers"]]
PRINCIPAIS = [e["ticker"] for e in CATALOGO]
SETORES = sorted({e["setor"] for e in CATALOGO})


def publico(e: dict) -> dict:
    return {k: v for k, v in e.items() if not k.startswith("_")}


def normalizar_ticker(t: str) -> str:
    return str(t).upper().strip().replace(".SA", "")


def info(tk: str) -> dict | None:
    return POR_TICKER.get(normalizar_ticker(tk))


def rotulo(tk: str) -> str:
    """Texto exibido nos seletores: 'Petrobras · PETR4' (permite achar o ticker pelo nome)."""
    e = info(tk)
    return f"{e['nome']} · {normalizar_ticker(tk)}" if e else normalizar_ticker(tk)


def nome_curto(tk: str) -> str:
    e = info(tk)
    return e["nome"] if e else normalizar_ticker(tk)


def por_setor(setor: str) -> list[dict]:
    return [publico(e) for e in CATALOGO if e["setor"] == setor]


def populares() -> list[dict]:
    return [publico(POR_TICKER[t]) for t in POPULARES if t in POR_TICKER]


# ------------------------------------------------------------------ busca
def _pontuar(e: dict, q: str, tokens: list[str]) -> float:
    tks = [t.lower() for t in e["tickers"]]
    if q in tks:
        return 100
    if len(q) >= 2 and any(t.startswith(q) for t in tks):
        return 92
    if _norm(e["nome"]).startswith(q):
        return 88
    if all(any(w.startswith(t) for w in e["_palavras"]) for t in tokens):
        return 73 if all(t in e["_nome"] for t in tokens) else 65
    if len(q) >= 4:  # tolerância a erro de digitação ("petrobas")
        melhor = max((difflib.SequenceMatcher(None, q, w).ratio() for w in e["_palavras"]), default=0)
        if melhor >= 0.78:
            return 40 + 20 * melhor
    return 0


def buscar_catalogo(consulta: str, n: int = 12) -> list[dict]:
    """Busca por nome, apelido, ticker ou setor. Aceita acentos e pequenos erros de digitação."""
    q = _norm(consulta).strip()
    if not q:
        return []
    tokens = q.split()
    pont = []
    for e in CATALOGO:
        p = _pontuar(e, q, tokens)
        if p > 0:
            pont.append((p, e))
    pont.sort(key=lambda x: (-x[0], _norm(x[1]["nome"])))
    if pont and pont[0][0] >= 65:  # há acerto direto: descarta as sugestões por semelhança (ruído)
        pont = [x for x in pont if x[0] >= 65]
    return [publico(e) for _, e in pont[:n]]


def resolver_termo(termo: str) -> str | None:
    """Devolve um ticker a partir de um ticker ou de um nome de empresa."""
    tk = normalizar_ticker(termo)
    if REGEX_TICKER.fullmatch(tk):
        return tk
    res = buscar_catalogo(termo, 1)
    return res[0]["ticker"] if res else None


def buscar_online(consulta: str, n: int = 8) -> list[dict]:
    """Reserva: procura no Yahoo Finance empresas da B3 que não estão no catálogo."""
    try:
        import yfinance as yf
        quotes = yf.Search(consulta, max_results=n, news_count=0).quotes
    except Exception:
        return []
    out = []
    for r in quotes or []:
        sym = str(r.get("symbol", ""))
        if not sym.endswith(".SA"):
            continue
        tk = sym[:-3]
        if tk in POR_TICKER or not REGEX_TICKER.fullmatch(tk):
            continue
        out.append({"nome": r.get("longname") or r.get("shortname") or tk,
                    "tickers": [tk], "ticker": tk, "setor": "Resultado da internet", "dominio": ""})
    return out


# ------------------------------------------------------------------ logos
_LOGO_CACHE: dict[str, tuple[float, str, bool]] = {}
_LOGO_RETENTAR_S = 600


def _iniciais_svg(tk: str) -> str:
    letras = re.sub(r"\d+$", "", tk)[:2] or tk[:2]
    matiz = sum(map(ord, tk)) % 360
    svg = ('<svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 64 64">'
           f'<rect width="64" height="64" rx="14" fill="hsl({matiz},40%,30%)"/>'
           '<text x="32" y="41" font-family="Arial,sans-serif" font-size="24" font-weight="700" '
           f'text-anchor="middle" fill="#ffffff">{letras}</text></svg>')
    return "data:image/svg+xml;base64," + base64.b64encode(svg.encode()).decode()


def _baixar_imagem(url: str) -> str | None:
    try:
        r = requests.get(url, timeout=4, headers={"User-Agent": "Mozilla/5.0"})
        tipo = r.headers.get("content-type", "").split(";")[0].strip().lower()
        if r.status_code == 200 and tipo.startswith("image/") and 100 < len(r.content) < 150_000:
            return f"data:{tipo};base64," + base64.b64encode(r.content).decode()
    except Exception:
        pass
    return None


def logo_uri(tk: str) -> str:
    """Logo da empresa como data-URI. Tenta Brapi, depois o ícone do site; senão, iniciais."""
    tk = normalizar_ticker(tk)
    agora = time.time()
    hit = _LOGO_CACHE.get(tk)
    if hit and (hit[2] or agora - hit[0] < _LOGO_RETENTAR_S):
        return hit[1]
    uri = _baixar_imagem(f"https://icons.brapi.dev/icons/{tk}.svg")
    if not uri:
        e = info(tk)
        if e and e.get("dominio"):
            uri = _baixar_imagem(f"https://www.google.com/s2/favicons?domain={e['dominio']}&sz=128")
    _LOGO_CACHE[tk] = (agora, uri or _iniciais_svg(tk), bool(uri))
    return _LOGO_CACHE[tk][1]


def logos_em_lote(tickers: list[str], max_workers: int = 8) -> dict[str, str]:
    tks = list(dict.fromkeys(normalizar_ticker(t) for t in tickers))
    if not tks:
        return {}
    with ThreadPoolExecutor(max_workers=max_workers) as ex:
        return dict(zip(tks, ex.map(logo_uri, tks)))


# ------------------------------------------------------------------ perfis do investidor
# Percentuais em pontos (13.0 = 13%). Os pesos somam 100.
PERFIS = {
    "Conservador": dict(
        icone="🛡️",
        resumo="Prioriza preservar o capital e receber renda previsível. Exige mais margem de segurança, "
               "dividendos consistentes, pouca dívida e baixa oscilação.",
        pesos={"Valor": 15, "Qualidade": 20, "Dividendos": 20, "Solidez": 20, "Tendência": 5, "Risco": 20},
        yield_alvo=8.0, margem_alvo=30, taxa=15.0, g=2.0, gp=2.0, vol_tol=25.0, nota_min=65),
    "Moderado": dict(
        icone="⚖️",
        resumo="Busca equilíbrio entre crescimento e proteção. Aceita oscilação moderada em troca de "
               "retorno acima da renda fixa.",
        pesos={"Valor": 25, "Qualidade": 25, "Dividendos": 15, "Solidez": 10, "Tendência": 10, "Risco": 15},
        yield_alvo=6.0, margem_alvo=20, taxa=13.0, g=4.0, gp=3.0, vol_tol=35.0, nota_min=60),
    "Arrojado": dict(
        icone="🚀",
        resumo="Aceita oscilações maiores em busca de valorização. Dá mais peso à tendência de preço "
               "e exige menos margem de segurança.",
        pesos={"Valor": 25, "Qualidade": 20, "Dividendos": 5, "Solidez": 5, "Tendência": 35, "Risco": 10},
        yield_alvo=5.0, margem_alvo=10, taxa=11.0, g=6.0, gp=3.5, vol_tol=50.0, nota_min=55),
}

# ------------------------------------------------------------------ critérios do buscador
# tipo "max": valor <= limite | tipo "min": valor >= limite
CRITERIOS = {
    "pl": dict(rotulo="P/L máximo", tipo="max", padrao=15.0, min=3.0, max=40.0, passo=0.5, glos="P/L"),
    "pvp": dict(rotulo="P/VP máximo", tipo="max", padrao=2.5, min=0.3, max=6.0, passo=0.1, glos="P/VP"),
    "ev_ebitda": dict(rotulo="EV/EBITDA máximo", tipo="max", padrao=8.0, min=2.0, max=20.0, passo=0.5, glos="EV/EBITDA"),
    "dy": dict(rotulo="Dividend yield mínimo (%)", tipo="min", padrao=4.0, min=0.0, max=15.0, passo=0.5, glos="DY 12m (%)"),
    "anos_div": dict(rotulo="Anos com dividendos (de 5)", tipo="min", padrao=4, min=1, max=5, passo=1, glos="Anos c/ dividendos"),
    "roe": dict(rotulo="ROE mínimo (%)", tipo="min", padrao=12.0, min=0.0, max=40.0, passo=1.0, glos="ROE (%)"),
    "margem_liq": dict(rotulo="Margem líquida mínima (%)", tipo="min", padrao=8.0, min=0.0, max=40.0, passo=1.0, glos="Margem líq. (%)"),
    "div_pl": dict(rotulo="Dív./PL máximo (%)", tipo="max", padrao=150.0, min=0.0, max=400.0, passo=10.0, glos="Dív./PL (%)"),
    "margem_seg": dict(rotulo="Margem de segurança mínima (%)", tipo="min", padrao=15.0, min=-20.0, max=60.0, passo=5.0, glos="Margem (%)"),
    "mcap": dict(rotulo="Valor de mercado mínimo (R$ bi)", tipo="min", padrao=3.0, min=0.0, max=100.0, passo=1.0, glos="Valor de mercado"),
}

PRESETS = {
    "🏅 Boa empresa (equilíbrio)": {"pl": 15.0, "roe": 12.0, "margem_liq": 8.0, "div_pl": 150.0, "dy": 4.0, "mcap": 3.0},
    "💰 Renda com dividendos": {"dy": 6.0, "anos_div": 5, "roe": 10.0, "div_pl": 150.0, "mcap": 3.0},
    "🏷️ Barata (Graham)": {"pl": 12.0, "pvp": 1.5, "margem_seg": 20.0, "roe": 8.0},
    "🛡️ Defensiva": {"div_pl": 80.0, "roe": 12.0, "margem_liq": 10.0, "dy": 3.0, "mcap": 5.0},
    "🚀 Qualidade": {"roe": 18.0, "margem_liq": 15.0, "div_pl": 100.0, "ev_ebitda": 10.0},
}
PRESET_PADRAO = "🏅 Boa empresa (equilíbrio)"
