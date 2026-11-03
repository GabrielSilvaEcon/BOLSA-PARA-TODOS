"""
Motor de Análise Setorial para criptoativos (puro: sem Streamlit, sem rede; recebe um dicionário de dados).

Cada categoria tem a sua própria régua: métricas, pesos e limites diferentes, e uma lista do que é
DESCONSIDERADO de propósito (ex.: TVL não entra na nota de uma L1 de alta performance).

Uso:
    cat = classificar(gecko_id, categorias_coingecko, categoria_defillama)      # -> "reserva" | "l1_contratos" | ...
    res = analisar(cat, dados)                                                  # -> {"metricas": [...], "nota": ...}

`dados` aceita estas chaves (todas opcionais; ausente = None = "sem dados"):
    preco, mcap, fdv, circ, maximo, vol24, mcap_total (mercado cripto inteiro), infl (% a.a. da oferta em circulação),
    tvl, tvl_var30 (fração), fees30, rev30 (receita retida pela rede/protocolo, 30 dias), dex30 (volume DEX, 30 dias),
    tps (transações reais por segundo, sem votos), dau (endereços ativos por dia), tem_queima (bool),

Os limites são regras educacionais, não recomendação de investimento.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- classificação
RESERVA = {"bitcoin", "litecoin", "bitcoin-cash", "monero", "dogecoin", "bitcoin-sv", "ethereum-classic", "zcash"}
L1_CONTRATOS = {"ethereum", "cardano", "polkadot", "cosmos", "algorand", "tezos", "internet-computer",
                "avalanche-2", "tron", "binancecoin", "the-open-network", "ripple", "stellar", "hedera-hashgraph"}
L1_PERFORMANCE = {"solana", "sui", "aptos", "near", "sei-network", "fantom", "sonic-3", "hyperliquid", "monad"}
# avalanche, tron, bnb, ton ficam em contratos "tradicionais" por padrão; o usuário pode trocar a categoria na tela.

_DEFI_TERMOS = ("decentralized finance", "defi", "decentralized exchange", "dex", "lending", "borrowing", "yield",
                "liquid staking", "derivatives", "stablecoin issuer", "automated market maker", "amm", "perpetuals")
_L1_TERMOS = ("layer 1", "smart contract platform", "layer-1")
_RESERVA_TERMOS = ("store of value", "proof of work", "pow")


def classificar(gecko_id: str, categorias: list[str] | None = None, categoria_llama: str | None = None) -> str:
    """Escolhe a categoria: primeiro a lista curada, depois os rótulos da CoinGecko/DefiLlama."""
    gid = (gecko_id or "").lower()
    if gid in RESERVA:
        return "reserva"
    if gid in L1_PERFORMANCE:
        return "l1_performance"
    if gid in L1_CONTRATOS:
        return "l1_contratos"
    texto = " | ".join([*(categorias or []), categoria_llama or ""]).lower()
    if _tem(texto, _L1_TERMOS) and not _tem(texto, ("lending", "dex")):
        return "l1_contratos"
    if _tem(texto, _DEFI_TERMOS):
        return "defi"
    if _tem(texto, _RESERVA_TERMOS):
        return "reserva"
    return "geral"


def _tem(texto: str, termos) -> bool:
    """Casa palavras inteiras (aceita plural): 'dex' não casa com 'index', nem 'pow' com 'power'."""
    return any(re.search(rf"(?<![a-z0-9]){re.escape(t)}(?:s|es)?(?![a-z0-9])", texto) for t in termos)


# --------------------------------------------------------------------------- formatação
def _num(v, casas=2):
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_usd(v) -> str:
    if v is None:
        return "n/d"
    for lim, suf in ((1e12, " tri"), (1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return f"US$ {_num(v / lim)}{suf}"
    return f"US$ {_num(v)}"


def fmt_pct(v, casas=1, sinal=False) -> str:
    return "n/d" if v is None else (f"{v:+.{casas}f}%" if sinal else f"{v:.{casas}f}%").replace(".", ",")


def fmt_x(v, casas=1) -> str:
    return "n/d" if v is None else f"{_num(v, casas)}x"


def fmt_qtd(v) -> str:
    if v is None:
        return "n/d"
    for lim, suf in ((1e9, " bi"), (1e6, " mi"), (1e3, " mil")):
        if abs(v) >= lim:
            return _num(v / lim) + suf
    return _num(v, 0)


# --------------------------------------------------------------------------- estrutura
@dataclass
class Metrica:
    chave: str
    nome: str
    grupo: str            # "visao" (tokenomics/valuation) | "onchain" (adoção) | "receitas" (emissão e receita)
    peso: float           # 0 = só informativa
    valor: str
    status: str           # good | fair | bad | na
    leitura: str
    dica: str = ""


@dataclass
class Categoria:
    chave: str
    rotulo: str
    exemplo: str
    foco: str
    desconsiderados: list[tuple[str, str]] = field(default_factory=list)


CATEGORIAS: dict[str, Categoria] = {
    "reserva": Categoria(
        "reserva", "Moedas & Reserva de Valor", "BTC",
        "Escassez, emissão e dominância: o ativo vale por ser raro, previsível e o mais aceito do mercado.",
        [("TVL e receita de taxas", "Não é uma plataforma de aplicações: o valor vem da escassez, não do uso de contratos."),
         ("P/S e múltiplos corporativos", "Não há 'empresa' nem receita retida para descontar.")]),
    "l1_contratos": Categoria(
        "l1_contratos", "Layer 1 de Contratos Inteligentes", "ETH",
        "Impacto de taxas e queima (EIP-1559), TVL e segurança: a rede é paga por quem a usa e protegida pelo capital em jogo.",
        [("Múltiplos de empresa (P/S)", "A receita da rede é queimada ou paga a validadores; não é lucro distribuído."),
         ("TPS bruto", "Redes seguras e descentralizadas escalam por camadas; throughput isolado distorce a leitura.")]),
    "l1_performance": Categoria(
        "l1_performance", "Layer 1 de Alta Performance", "SOL",
        "Volume em DEX, endereços ativos diários (DAU) e throughput real: a rede compete por velocidade e uso.",
        [("Régua rígida de TVL", "Redes rápidas têm capital girando (volume) mais do que parado; TVL baixo não é sinal de fraqueza."),
         ("Queima de taxas (EIP-1559)", "Mecanismo específico do Ethereum.")]),
    "defi": Categoria(
        "defi", "Finanças Descentralizadas (DeFi)", "UNI, AAVE",
        "Múltiplos corporativos: P/S (valor de mercado ÷ receita do protocolo) e P/Taxas, como numa ação.",
        [("Escassez de oferta e dominância", "São atributos de reserva de valor, não de protocolo."),
         ("Throughput e DAU de rede", "O protocolo roda sobre outra rede.")]),
    "geral": Categoria(
        "geral", "Outros criptoativos", "—",
        "Categoria não reconhecida: usamos só uma régua básica (oferta, diluição, liquidez e tendência). "
        "Escolha a categoria correta na lista acima, se souber qual é.",
        []),
}

GRUPOS = {"visao": "Visão geral e tokenomics", "onchain": "Adoção e on-chain", "receitas": "Emissão e receitas"}


def _m(chave, nome, grupo, peso, valor, status, leitura, dica=""):
    return Metrica(chave, nome, grupo, peso, valor, status, leitura, dica)


def _faixa(v, bom, medio, maior_melhor=True):
    """good/fair/bad por dois cortes. maior_melhor=False inverte (menor é melhor)."""
    if v is None:
        return "na"
    if maior_melhor:
        return "good" if v >= bom else ("fair" if v >= medio else "bad")
    return "good" if v <= bom else ("fair" if v <= medio else "bad")


def _sem(chave, nome, grupo, peso, por_que):
    return _m(chave, nome, grupo, peso, "n/d", "na", por_que)


# --------------------------------------------------------------------------- métricas reutilizáveis
def _m_diluicao(d):
    mc, fdv = d.get("mcap"), d.get("fdv")
    r = mc / fdv if mc and fdv else None
    if r is None:
        return _sem("mc_fdv", "Diluição (Mcap ÷ FDV)", "visao", 2, "Sem FDV para comparar.")
    st = _faixa(r, 0.8, 0.5)
    txt = {"good": "Quase tudo já circula: pouca pressão de novos tokens.",
           "fair": "Parte relevante do suprimento ainda vai entrar no mercado.",
           "bad": "Menos da metade circula: forte risco de diluição."}[st]
    return _m("mc_fdv", "Diluição (Mcap ÷ FDV)", "visao", 2, fmt_pct(r * 100, 0), st, txt,
              "Verde ≥ 80% em circulação; vermelho < 50%.")


def _m_inflacao(d, peso, bom=2.0, medio=5.0):
    i = d.get("infl")
    if i is None:
        return _sem("infl", "Inflação anual (estimada)", "receitas", peso, "Sem histórico de oferta na CoinGecko.")
    st = _faixa(i, bom, medio, maior_melhor=False)
    txt = ("Oferta encolhendo: o ativo é deflacionário." if i < 0 else
           {"good": "Emissão baixa: pouca diluição para quem já detém.",
            "fair": "Emissão moderada: o preço precisa de demanda nova para compensar.",
            "bad": "Emissão alta: a oferta cresce rápido e dilui os detentores."}[st])
    return _m("infl", "Inflação anual (estimada)", "receitas", peso, fmt_pct(i, 2, True), st, txt,
              f"Crescimento da oferta em circulação em 12 meses. Verde ≤ {bom:g}%; vermelho > {medio:g}%.")




def _m_liquidez(d, peso=1):
    v, mc = d.get("vol24"), d.get("mcap")
    g = v / mc if v and mc else None
    if g is None:
        return _sem("liq", "Liquidez (volume 24h ÷ Mcap)", "visao", peso, "Sem volume ou valor de mercado.")
    st = "good" if 0.01 <= g <= 0.3 else ("fair" if 0.003 <= g < 0.01 or g > 0.3 else "bad")
    return _m("liq", "Liquidez (volume 24h ÷ Mcap)", "visao", peso, fmt_pct(g * 100, 2), st,
              f"Volume 24h de {fmt_usd(v)}. Muito baixo = difícil sair; muito alto = especulação excessiva.",
              "Verde entre 1% e 30%.")


def _m_tvl_var(d, peso):
    v = d.get("tvl_var30")
    if v is None:
        return _sem("tvl_var", "TVL: variação em 30 dias", "onchain", peso, "Sem histórico de TVL no DefiLlama.")
    st = _faixa(v * 100, 5, -10)
    return _m("tvl_var", "TVL: variação em 30 dias", "onchain", peso, fmt_pct(v * 100, 1, True), st,
              {"good": "Capital entrando.", "fair": "Capital estável.", "bad": "Capital saindo da rede/protocolo."}[st],
              "Verde ≥ +5%; vermelho < −10%.")


def _m_mc_tvl(d, peso, bom=1.0, ruim=3.0):
    mc, tvl = d.get("mcap"), d.get("tvl")
    r = mc / tvl if mc and tvl else None
    if r is None:
        return _sem("mc_tvl", "Mcap ÷ TVL", "onchain", peso, "Sem TVL ou valor de mercado.")
    st = _faixa(r, bom, ruim, maior_melhor=False)
    return _m("mc_tvl", "Mcap ÷ TVL", "onchain", peso, fmt_x(r, 2), st,
              "Quanto o mercado paga por cada dólar depositado.", f"Verde ≤ {bom:g}x; vermelho > {ruim:g}x.")


# --------------------------------------------------------------------------- regras por categoria
def _reserva(d):
    out = []
    circ, mx = d.get("circ"), d.get("maximo")
    if mx and circ:
        r = circ / mx
        st = _faixa(r, 0.9, 0.7)
        out.append(_m("escassez", "Escassez: oferta emitida ÷ teto", "visao", 3, fmt_pct(r * 100, 1), st,
                      f"Teto fixo de {fmt_qtd(mx)} unidades; já circulam {fmt_qtd(circ)}. Quanto mais perto do teto, "
                      "menos novas unidades podem surgir.", "Verde ≥ 90%; vermelho < 70%."))
    elif circ is None:
        out.append(_sem("escassez", "Escassez: oferta emitida ÷ teto", "visao", 3, "Sem dados de oferta."))
    else:
        out.append(_m("escassez", "Escassez: oferta emitida ÷ teto", "visao", 3, "Sem teto", "bad",
                      "Sem limite máximo de oferta: a escassez depende de decisão futura da rede."))
    dom = d["mcap"] / d["mcap_total"] * 100 if d.get("mcap") and d.get("mcap_total") else None
    out.append(_m("dom", "Dominância no mercado cripto", "visao", 3, fmt_pct(dom, 1),
                  _faixa(dom, 40, 10), "Fatia do valor de mercado de todas as criptomoedas. Reserva de valor precisa de aceitação ampla.",
                  "Verde ≥ 40%; vermelho < 10%.") if dom is not None
               else _sem("dom", "Dominância no mercado cripto", "visao", 3, "Sem valor de mercado total (CoinGecko)."))
    out.append(_m_inflacao(d, 3, bom=2.0, medio=4.0))
    i = d.get("infl")
    if i is not None and i > 0:
        s2f = 100 / i
        out.append(_m("s2f", "Estoque ÷ fluxo (anos de emissão)", "receitas", 1, f"{_num(s2f, 0)} anos",
                      _faixa(s2f, 50, 20),
                      "Quantos anos a emissão atual levaria para criar a oferta existente. Maior = mais escasso.",
                      "Verde ≥ 50 anos; vermelho < 20."))
    out.append(_m_liquidez(d, 1))
    return out


def _l1_contratos(d):
    out = [_m_inflacao(d, 3, bom=1.0, medio=3.0)]
    preco, circ = d.get("preco"), d.get("circ") or (d["mcap"] / d["preco"] if d.get("mcap") and d.get("preco") else None)
    rev30 = d.get("rev30")
    if not d.get("tem_queima"):
        out.append(_sem("queima", "Queima de taxas (EIP-1559)", "receitas", 0,
                        "Esta rede não queima taxas como o Ethereum; métrica não se aplica."))
    elif rev30 is None or not preco or not circ:
        out.append(_sem("queima", "Queima de taxas (EIP-1559)", "receitas", 2, "Sem dados de taxas queimadas (DefiLlama)."))
    else:
        queima_pct = rev30 * 365 / 30 / preco / circ * 100
        infl = d.get("infl")
        if infl is None:
            out.append(_m("queima", "Queima de taxas (EIP-1559)", "receitas", 2, fmt_pct(queima_pct, 2), "na",
                          f"Queima estimada de {fmt_pct(queima_pct, 2)} da oferta por ano; sem inflação para comparar."))
        else:
            bruta = infl + queima_pct  # emissão bruta = variação líquida + o que foi queimado
            cob = queima_pct / bruta if bruta > 0 else None
            st = "good" if infl <= 0 else ("fair" if cob is not None and cob >= 0.3 else "bad")
            out.append(_m("queima", "Queima de taxas (EIP-1559)", "receitas", 2, fmt_pct(queima_pct, 2), st,
                          f"Queima ≈ {fmt_pct(queima_pct, 2)} da oferta/ano contra emissão bruta ≈ {fmt_pct(bruta, 2)}"
                          + (f": cobre {cob:.0%} da emissão." if cob is not None else "."),
                          "Verde: a queima supera a emissão (oferta líquida cai). Âmbar: cobre ≥ 30%."))
    out.append(_m("fees", "Taxas pagas à rede (30 dias)", "receitas", 0, fmt_usd(d.get("fees30")),
                  "na" if d.get("fees30") is None else "info",
                  "Demanda real por espaço no bloco. Só informativa." if d.get("fees30") is not None
                  else "Sem dados de taxas."))
    tvl = d.get("tvl")
    out.append(_m("tvl", "TVL da rede", "onchain", 1, fmt_usd(tvl), "na" if tvl is None else "info",
                  "Capital depositado em aplicações da rede." if tvl else "Sem TVL no DefiLlama.") )
    out += [_m_tvl_var(d, 2), _m_mc_tvl(d, 1, bom=2.0, ruim=8.0)]
    mc = d.get("mcap")
    out.append(_m("seg", "Segurança (proxy: valor de mercado)", "visao", 3, fmt_usd(mc),
                  _faixa(mc, 1e11, 1e10),
                  "Quanto maior o valor do token, mais caro atacar a rede. Taxa de staking não entra: não há fonte gratuita.",
                  "Verde ≥ US$ 100 bi; vermelho < US$ 10 bi.") if mc
               else _sem("seg", "Segurança (proxy: valor de mercado)", "visao", 3, "Sem valor de mercado."))
    out.append(_m_diluicao(d))
    return out


def _l1_performance(d):
    mc = d.get("mcap")
    dex = d.get("dex30")
    giro = dex / mc if dex and mc else None
    out = [_m("dex", "Volume em DEX (30 dias)", "onchain", 3, fmt_usd(dex), _faixa(giro, 0.5, 0.15),
              f"Equivale a {_num(giro, 2)}x o valor de mercado por mês: capital girando na rede." if giro is not None else "",
              "Verde: volume 30d ≥ 50% do Mcap; vermelho < 15%.") if giro is not None
           else _sem("dex", "Volume em DEX (30 dias)", "onchain", 3, "Sem volume de DEX no DefiLlama.")]
    dau = d.get("dau")
    out.append(_m("dau", "Endereços ativos diários (DAU)", "onchain", 3, fmt_qtd(dau), _faixa(dau, 1e6, 1e5),
                  "Usuários distintos por dia.", "Verde ≥ 1 mi; vermelho < 100 mil.") if dau is not None
               else _sem("dau", "Endereços ativos diários (DAU)", "onchain", 3,
                         "Sem fonte gratuita: configure DUNE_API_KEY e a consulta da rede nos Secrets (veja o rodapé)."))
    tps = d.get("tps")
    out.append(_m("tps", "Throughput real (TPS, sem votos)", "onchain", 3, _num(tps, 0) if tps is not None else "n/d",
                  _faixa(tps, 1000, 300), "Transações úteis por segundo medidas na rede (não é o limite teórico).",
                  "Verde ≥ 1.000; vermelho < 300.") if tps is not None
               else _sem("tps", "Throughput real (TPS, sem votos)", "onchain", 3,
                         "Medição direta só para Solana; outras redes precisam de um provedor."))
    f = d.get("fees30")
    pf = mc / (f * 365 / 30) if f and mc else None
    out.append(_m("pf", "Preço/Taxas da rede", "receitas", 1, fmt_x(pf, 1), _faixa(pf, 60, 200, maior_melhor=False),
                  f"Taxas de 30 dias: {fmt_usd(f)}.", "Verde ≤ 60x; vermelho > 200x.") if pf is not None
               else _sem("pf", "Preço/Taxas da rede", "receitas", 1, "Sem dados de taxas."))
    out += [_m_inflacao(d, 1, bom=3.0, medio=8.0), _m_diluicao(d), _m_liquidez(d, 1)]
    tvl = d.get("tvl")
    out.append(_m("tvl", "TVL da rede (informativo)", "onchain", 0, fmt_usd(tvl), "na" if tvl is None else "info",
                  "Não entra na nota desta categoria." if tvl else "Sem TVL."))
    return out


def _defi(d):
    mc = d.get("mcap")
    rev, fees = d.get("rev30"), d.get("fees30")
    rev_a = rev * 365 / 30 if rev else None
    ps = mc / rev_a if mc and rev_a else None
    out = []
    if ps is not None:
        out.append(_m("ps", "P/S (Mcap ÷ receita do protocolo)", "receitas", 4, fmt_x(ps, 1),
                      _faixa(ps, 15, 40, maior_melhor=False),
                      f"Receita retida em 30 dias: {fmt_usd(rev)} (anualizada {fmt_usd(rev_a)}). Como o P/L de uma ação.",
                      "Verde ≤ 15x; vermelho > 40x."))
    elif rev is not None and rev == 0:
        out.append(_m("ps", "P/S (Mcap ÷ receita do protocolo)", "receitas", 4, "Sem receita", "bad",
                      "As taxas vão integralmente a quem fornece liquidez; o token não captura receita (por ora)."))
    else:
        out.append(_sem("ps", "P/S (Mcap ÷ receita do protocolo)", "receitas", 4, "O DefiLlama não informa receita deste protocolo."))
    fees_a = fees * 365 / 30 if fees else None
    pf = mc / fees_a if mc and fees_a else None
    out.append(_m("pf", "P/Taxas (Mcap ÷ taxas totais)", "receitas", 2, fmt_x(pf, 1), _faixa(pf, 20, 60, maior_melhor=False),
                  f"Taxas pagas pelos usuários em 30 dias: {fmt_usd(fees)}.", "Verde ≤ 20x; vermelho > 60x.") if pf is not None
               else _sem("pf", "P/Taxas (Mcap ÷ taxas totais)", "receitas", 2, "Sem taxas no DefiLlama."))
    tk = rev / fees * 100 if rev is not None and fees else None
    out.append(_m("take", "Retenção (receita ÷ taxas)", "receitas", 1, fmt_pct(tk, 1), _faixa(tk, 20, 5),
                  "Parte das taxas que fica com o protocolo/token, o resto vai a provedores de liquidez.",
                  "Verde ≥ 20%; vermelho < 5%.") if tk is not None
               else _sem("take", "Retenção (receita ÷ taxas)", "receitas", 1, "Sem receita ou taxas."))
    tvl = d.get("tvl")
    out.append(_m("tvl", "TVL do protocolo", "onchain", 0, fmt_usd(tvl), "na" if tvl is None else "info",
                  "Capital depositado." if tvl else "Sem TVL."))
    out += [_m_mc_tvl(d, 2), _m_tvl_var(d, 1), _m_diluicao(d)]
    return out


def _geral(d):
    return [_m_diluicao(d), _m_inflacao(d, 2, 3.0, 8.0), _m_liquidez(d, 1)]


_REGRAS = {"reserva": _reserva, "l1_contratos": _l1_contratos, "l1_performance": _l1_performance,
           "defi": _defi, "geral": _geral}
_SCORE = {"good": 1.0, "fair": 0.5, "bad": 0.0}


def analisar(categoria: str, dados: dict) -> dict:
    """Aplica a régua da categoria. Retorna métricas, nota ponderada (0 a 1) e o rótulo do veredito."""
    cat = CATEGORIAS.get(categoria) or CATEGORIAS["geral"]
    metricas = _REGRAS.get(cat.chave, _geral)(dados)
    com_peso = [m for m in metricas if m.peso > 0]
    total = sum(m.peso for m in com_peso)
    validos = [m for m in com_peso if m.status in _SCORE]
    cobertos = sum(m.peso for m in validos)
    nota = sum(m.peso * _SCORE[m.status] for m in validos) / cobertos if cobertos else None
    cobertura = cobertos / total if total else 0.0
    if nota is None or cobertura < 0.5:
        veredito, cls = "Dados insuficientes", "na"
    elif nota >= 0.7:
        veredito, cls = "Quadro forte", "good"
    elif nota >= 0.45:
        veredito, cls = "Quadro equilibrado", "fair"
    else:
        veredito, cls = "Quadro frágil", "bad"
    return {"categoria": cat, "metricas": metricas, "nota": nota, "cobertura": cobertura,
            "veredito": veredito, "cls": cls}
