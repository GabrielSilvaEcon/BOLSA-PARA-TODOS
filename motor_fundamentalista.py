"""
Motor da Análise Fundamentalista de criptoativos (puro: sem Streamlit e sem rede; recebe um dicionário de dados).

Avalia sete pilares, cada um com métricas próprias do TIPO do ativo (Bitcoin, moeda de reserva, blockchain, DeFi,
stablecoin, outros). A mesma régua NÃO é usada para todos: cada tipo tem pesos de pilar e métricas diferentes.

Regras de honestidade dos dados:
  - dado ausente = None = "n/d": a métrica sai da média (não vira zero nem valor neutro) e a cobertura cai;
  - um pilar só recebe nota se pelo menos 40% do peso das suas métricas tiver dado;
  - a nota geral só aparece se os pilares com dado cobrirem pelo menos 50% do peso total;
  - receita do protocolo e valor capturado pelo token são medidos separadamente (ver captura_valor).
Não usa Graham, Bazin nem fluxo de caixa descontado: criptoativos não têm lucro contábil, dividendos regulares nem
fluxo de caixa estável a descontar. O valuation usa múltiplos de receita (P/S, P/Taxas), rendimento efetivo ao
detentor e comparação com pares.

`dados` aceita (todas as chaves opcionais):
  tipo, nome, performance (bool: L1 de alta performance), preco, mcap, fdv, circ, maximo, vol24, rank, mcap_total,
  infl (% a.a.), tem_queima, idade_anos, vol_anual (%), queda (%), tendencia,
  tvl, tvl_var30, tvl_var90 (frações), fees30, fees_cresc (fração), rev30, holders30, dex30, tps, dau,
  pares {n, mc_tvl_mediana, p_taxas_mediana, grupo},
  dev {repos, commits_4w, contribuidores, stars, issues_total, issues_fechadas},
  btc {hash_var90, enderecos_var90},
  stable {peg_tipo, mecanismo, circulante_usd, cresc30, n_cadeias, dias_na_faixa, desvio_max},
  manual {papeis, auditoria, nakamoto, governanca, unlock12m, reservas}.

Os limites são regras educacionais, não recomendação de investimento.
"""
from __future__ import annotations

from dataclasses import dataclass
from math import log10

from setorial import fmt_pct, fmt_qtd, fmt_usd, fmt_x

# --------------------------------------------------------------------------- catálogo
PILARES = [
    ("util", "Utilidade e proposta de valor"),
    ("adocao", "Adoção e crescimento da rede"),
    ("saude", "Saúde econômica e receitas"),
    ("token", "Tokenomics"),
    ("seg", "Segurança e descentralização"),
    ("dev", "Desenvolvimento e governança"),
    ("val", "Valuation e comparação com similares"),
]
NOME_PILAR = dict(PILARES)

TIPOS = {
    "bitcoin": "Bitcoin",
    "reserva": "Moeda de reserva de valor (outras)",
    "blockchain": "Blockchain (Layer 1 / Layer 2)",
    "defi": "Protocolo DeFi",
    "stablecoin": "Stablecoin",
    "outros": "Outros criptoativos",
}

# pesos padrão (somam 100). O usuário pode mudá-los na tela; são normalizados na hora do cálculo.
PESOS_PADRAO = {
    "bitcoin":    {"util": 15, "adocao": 20, "saude": 10, "token": 20, "seg": 25, "dev": 10, "val": 0},
    "reserva":    {"util": 15, "adocao": 20, "saude": 10, "token": 20, "seg": 25, "dev": 10, "val": 0},
    "blockchain": {"util": 15, "adocao": 20, "saude": 15, "token": 15, "seg": 10, "dev": 10, "val": 15},
    "defi":       {"util": 10, "adocao": 15, "saude": 20, "token": 15, "seg": 10, "dev": 5,  "val": 25},
    "stablecoin": {"util": 20, "adocao": 20, "saude": 15, "token": 5,  "seg": 35, "dev": 5,  "val": 0},
    "outros":     {"util": 10, "adocao": 15, "saude": 10, "token": 20, "seg": 15, "dev": 15, "val": 15},
}

FOCO_TIPO = {
    "bitcoin": "Reserva de valor: escassez, aceitação, segurança da rede e histórico. Não há receita nem lucro para descontar.",
    "reserva": "Moeda de reserva de valor: escassez, emissão, aceitação e segurança. Sem fluxo de caixa a descontar.",
    "blockchain": "Rede de contratos: uso real (taxas e capital), quem paga a segurança, quanto das taxas chega ao token e valuation por múltiplos.",
    "defi": "Protocolo: receita retida pelo protocolo e, principalmente, quanto dela chega de fato ao detentor do token.",
    "stablecoin": "Moeda estável: o que importa é manter US$ 1, o lastro, o emissor e a transparência. Valuation não se aplica.",
    "outros": "Categoria não reconhecida: régua básica (oferta, diluição, segurança). Escolha o tipo correto se souber qual é.",
}

PAPEIS = ["Pagamento de taxas / gás", "Governança (voto)", "Colateral ou garantia", "Staking / segurança da rede",
          "Desconto ou acesso a serviços", "Direito a receita (queima, recompra ou dividendos)"]
AUDITORIA = {"Sem auditoria pública": 5, "Uma auditoria": 55, "Várias auditorias + recompensa por bugs": 90}
GOVERNANCA = {"Centralizada (equipe ou fundação decide)": 25, "Híbrida (fundação + voto do token)": 60,
              "Descentralizada (voto on-chain / DAO)": 80, "Consenso social aberto (ex.: Bitcoin)": 80}
RESERVAS = {"Sem transparência": 5, "Atestação periódica de contador": 60,
            "Auditoria completa, reservas líquidas": 90}
MECANISMO = {"fiat-backed": ("lastro em moeda fiduciária", 70), "crypto-backed": ("lastro em criptoativos", 65),
             "algorithmic": ("algorítmica, sem lastro integral", 10)}

COBERTURA_MIN_PILAR = 0.40
COBERTURA_MIN_GERAL = 0.50
COBERTURA_CONFIAVEL = 0.70


# --------------------------------------------------------------------------- estrutura
@dataclass
class Metrica:
    pilar: str
    chave: str
    nome: str
    valor: str
    nota: float | None          # 0 a 100; None = sem dado
    peso: float                 # dentro do pilar; 0 = só informativa
    leitura: str
    fonte: str = ""
    origem: str = "api"         # api | calculado | manual
    dica: str = ""


def _m(pilar, chave, nome, peso, valor, nota, leitura, fonte="", origem="api", dica=""):
    n = None if nota is None else max(0.0, min(100.0, float(nota)))
    return Metrica(pilar, chave, nome, valor, n, peso, leitura, fonte, origem, dica)


def _nd(pilar, chave, nome, peso, motivo, origem="api", fonte="", dica=""):
    return Metrica(pilar, chave, nome, "n/d", None, peso, motivo, fonte, origem, dica)


def _info(pilar, chave, nome, valor, leitura, fonte="", origem="api"):
    return Metrica(pilar, chave, nome, valor, None, 0, leitura, fonte, origem)


def cls_nota(n: float | None) -> str:
    return "na" if n is None else ("good" if n >= 70 else ("fair" if n >= 45 else "bad"))


def _lin(x, pts):
    """Interpolação linear por partes entre pontos (x, nota); fora da faixa vale a nota da ponta."""
    if x is None:
        return None
    pts = sorted(pts)
    if x <= pts[0][0]:
        return float(pts[0][1])
    if x >= pts[-1][0]:
        return float(pts[-1][1])
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return float(y1) if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return None


def _lin_log(x, pts):
    if x is None:
        return None
    if x <= 0:
        return float(sorted(pts)[0][1])
    return _lin(log10(x), [(log10(a), b) for a, b in pts])


def _n(v, casas=1):
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _anual(v30):
    return None if v30 is None else v30 * 365 / 30


def _razao(a, b):
    return a / b if a is not None and b not in (None, 0) else None


# --------------------------------------------------------------------------- receita × valor capturado
def captura_valor(d: dict) -> dict | None:
    """Separa três coisas que costumam ser confundidas:
       1) taxas pagas pelos usuários; 2) receita do protocolo (o que sobra depois de pagar provedores/validadores);
       3) valor efetivamente entregue ao detentor do token (queima, recompra ou dividendos).
    A receita do protocolo pode ir para o tesouro/DAO e nunca chegar ao token."""
    fees, rev, hol = d.get("fees30"), d.get("rev30"), d.get("holders30")
    if fees is None and rev is None and hol is None:
        return None
    via_queima = False
    if d.get("tipo") == "blockchain" and d.get("tem_queima") and rev is not None:
        hol, via_queima = rev, True            # Ethereum: a receita da rede é a base fee queimada (EIP-1559)
    sh_rev = _razao(rev, fees)
    sh_hol = _razao(hol, fees)
    etapas = []
    if fees is not None:
        etapas.append(("Taxas pagas pelos usuários", fees, 1.0))
        if rev is not None:
            etapas.append(("Ficam com provedores de liquidez / validadores", max(fees - rev, 0), _razao(max(fees - rev, 0), fees)))
    if rev is not None:
        etapas.append(("Receita do protocolo" if not via_queima else "Receita da rede (base fee)", rev, sh_rev))
    if hol is not None:
        etapas.append(("Chega ao detentor do token" + (" (queimado)" if via_queima else ""), hol, sh_hol))
        if rev is not None and not via_queima:
            etapas.append(("Fica no tesouro / DAO, sem ir ao token", max(rev - hol, 0), _razao(max(rev - hol, 0), fees)))

    if hol is not None and hol > 0 and fees:
        forte = (sh_hol or 0) >= 0.05
        ver, cls = ("Captura direta pelo token", "good" if forte else "fair")
        txt = (f"{fmt_pct((sh_hol or 0) * 100, 1)} de tudo que os usuários pagam chega ao detentor"
               f"{' por queima' if via_queima else ' (recompra, queima ou dividendos)'}."
               + ("" if forte else " É uma fração pequena das taxas."))
    elif hol is not None and hol == 0 and rev is not None and rev > 0:
        ver, cls = "Receita existe, mas não chega ao token", "fair"
        txt = ("O protocolo retém receita, mas o DefiLlama não registra nenhuma distribuição ao detentor (queima, recompra ou dividendos): "
               "ela não existe ou não é rastreada. Se não existir, a receita fica no tesouro/DAO e o token só captura valor quando "
               "a governança ativar a distribuição. Confirme na governança do protocolo.")
    elif rev is not None and rev == 0 and fees:
        ver, cls = "Sem captura de valor", "bad"
        txt = "O DefiLlama registra receita zero: a taxa vai toda a quem fornece liquidez ou valida a rede, e o protocolo e o token não retêm nada."
    elif hol is None and rev is not None and rev > 0:
        ver, cls = "Captura não confirmada", "na"
        txt = ("Há receita do protocolo, mas não há dado de quanto chega ao detentor do token. "
               "Receita do protocolo não é o mesmo que valor capturado pelo token.")
    else:
        ver, cls, txt = "Sem dados suficientes", "na", "Não há receita ou taxas publicadas para este ativo."
    return {"fees": fees, "rev": rev, "holders": hol, "share_rev": sh_rev, "share_hol": sh_hol, "via_queima": via_queima,
            "etapas": etapas, "veredito": ver, "cls": cls, "texto": txt}


# --------------------------------------------------------------------------- métricas por pilar
def _m_rank(d):
    r = d.get("rank")
    if not r:
        return _nd("util", "rank", "Posição por valor de mercado", 1, "Sem ranking na CoinGecko.", fonte="CoinGecko")
    return _m("util", "rank", "Posição por valor de mercado", 1, f"#{r}",
              _lin_log(r, [(1, 100), (5, 92), (20, 78), (100, 55), (500, 30), (2000, 10)]),
              "Quanto mais alto o ranking, mais o mercado já reconhece e negocia o ativo.", "CoinGecko",
              dica="Proxy de aceitação, não de qualidade.")


def _m_liquidez(pilar, peso):
    def f(d):
        g = _razao(d.get("vol24"), d.get("mcap"))
        if g is None:
            return _nd(pilar, "liq", "Liquidez (volume 24h ÷ valor de mercado)", peso, "Sem volume ou valor de mercado.", fonte="CoinGecko")
        nota = _lin(g, [(0.001, 15), (0.005, 45), (0.01, 75), (0.03, 100), (0.3, 100), (0.6, 60), (1.5, 30)])
        return _m(pilar, "liq", "Liquidez (volume 24h ÷ valor de mercado)", peso, fmt_pct(g * 100, 2), nota,
                  f"Volume de {fmt_usd(d.get('vol24'))} em 24h. Muito baixo dificulta sair; muito alto indica especulação.",
                  "CoinGecko", dica="Faixa saudável: de 3% a 30% do valor de mercado ao dia.")
    return f


def _util(d):
    t, out = d["tipo"], [_m_rank(d)]
    if t in ("bitcoin", "reserva"):
        dom = _razao(d.get("mcap"), d.get("mcap_total"))
        out.append(_m("util", "dom", "Dominância no mercado cripto", 3, fmt_pct(dom * 100, 1),
                      _lin(dom, [(0.001, 10), (0.02, 30), (0.1, 55), (0.4, 85), (0.55, 100)]),
                      "Fatia do valor de todo o mercado cripto. Reserva de valor precisa de aceitação ampla.",
                      "CoinGecko", "calculado") if dom is not None
                   else _nd("util", "dom", "Dominância no mercado cripto", 3, "Sem valor de mercado total.", fonte="CoinGecko"))
    if t in ("blockchain", "defi", "outros"):
        fa = _anual(d.get("fees30"))
        out.append(_m("util", "demanda", "Demanda real paga (taxas anualizadas)", 3, fmt_usd(fa),
                      _lin_log(fa, [(1e5, 10), (1e6, 30), (1e7, 55), (1e8, 80), (1e9, 100)]),
                      "Quanto os usuários pagam por ano para usar a rede/protocolo: prova de que alguém precisa dele.",
                      "DefiLlama", "calculado") if fa is not None
                   else _nd("util", "demanda", "Demanda real paga (taxas anualizadas)", 3, "O DefiLlama não publica taxas deste ativo.", fonte="DefiLlama"))
    if t == "stablecoin":
        s = d.get("stable") or {}
        circ = s.get("circulante_usd") or d.get("mcap")
        out.append(_m("util", "circ", "Oferta em circulação (tamanho de uso)", 3, fmt_usd(circ),
                      _lin_log(circ, [(1e8, 20), (1e9, 50), (1e10, 80), (5e10, 100)]),
                      "Quanto maior a oferta, mais a moeda é usada como dólar digital.", "DefiLlama") if circ
                   else _nd("util", "circ", "Oferta em circulação (tamanho de uso)", 3, "Sem dado de oferta.", fonte="DefiLlama"))
        nc = s.get("n_cadeias")
        out.append(_m("util", "cadeias", "Redes em que circula", 1, str(nc), _lin(nc, [(1, 20), (3, 50), (8, 80), (15, 100)]),
                      "Presença em mais redes = mais utilidade e menos dependência de uma só.", "DefiLlama") if nc
                   else _nd("util", "cadeias", "Redes em que circula", 1, "Sem dado de redes.", fonte="DefiLlama"))
    if t != "stablecoin":
        pap = (d.get("manual") or {}).get("papeis")
        if pap:
            out.append(_m("util", "papeis", "Papéis do token (informado por você)", 2, f"{len(pap)} de {len(PAPEIS)}",
                          _lin(len(pap), [(0, 10), (1, 40), (2, 65), (3, 85), (4, 100)]),
                          "Funções declaradas: " + "; ".join(pap).lower() + ". Confira se o papel é real e usado.",
                          origem="manual", dica="Papel declarado não é papel comprovado: veja o pilar de saúde econômica."))
        else:
            out.append(_nd("util", "papeis", "Papéis do token (informado por você)", 2,
                           "Nenhuma API gratuita diz para que serve o token. Informe no painel de dados manuais.", origem="manual"))
    return out


def _adocao(d):
    t, out = d["tipo"], []
    if t == "bitcoin":
        v = (d.get("btc") or {}).get("enderecos_var90")
        out.append(_m("adocao", "enderecos", "Endereços únicos ativos: variação em 90 dias", 3, fmt_pct(v * 100, 1) if v is not None else "n/d",
                      _lin(v, [(-0.3, 10), (-0.1, 35), (0, 55), (0.15, 80), (0.4, 100)]),
                      "Mais endereços usando a rede = adoção crescendo.", "blockchain.com") if v is not None
                   else _nd("adocao", "enderecos", "Endereços únicos ativos: variação em 90 dias", 3, "blockchain.com indisponível agora.", fonte="blockchain.com"))
        out.append(_m_liquidez("adocao", 1)(d))
    elif t in ("reserva", "outros"):
        out.append(_m_liquidez("adocao", 2)(d))
    elif t == "blockchain":
        perf = bool(d.get("performance"))
        out.append(_var_tvl(d, "tvl_var30", "30 dias", 2))
        out.append(_var_tvl(d, "tvl_var90", "90 dias", 2))
        giro = _razao(d.get("dex30"), d.get("mcap"))
        w = 3 if perf else 1
        out.append(_m("adocao", "dex", "Volume em DEX (30 dias) ÷ valor de mercado", w, f"{fmt_usd(d.get('dex30'))}",
                      _lin(giro, [(0.05, 15), (0.15, 40), (0.5, 80), (1, 100)]),
                      f"Equivale a {_n(giro, 2)}x o valor de mercado por mês: capital girando na rede.", "DefiLlama", "calculado") if giro is not None
                   else _nd("adocao", "dex", "Volume em DEX (30 dias) ÷ valor de mercado", w, "Sem volume de DEX no DefiLlama.", fonte="DefiLlama"))
        if perf:
            dau, tps = d.get("dau"), d.get("tps")
            out.append(_m("adocao", "dau", "Endereços ativos diários (DAU)", 3, fmt_qtd(dau),
                          _lin_log(dau, [(1e4, 20), (1e5, 50), (1e6, 85), (5e6, 100)]), "Usuários distintos por dia.", "Dune (opcional)") if dau
                       else _nd("adocao", "dau", "Endereços ativos diários (DAU)", 3, "Sem fonte gratuita: exige DUNE_API_KEY e consulta nos Secrets.", fonte="Dune (opcional)"))
            out.append(_m("adocao", "tps", "Throughput real (TPS, sem votos)", 2, _n(tps, 0),
                          _lin_log(tps, [(10, 20), (100, 50), (1000, 80), (3000, 100)]), "Transações úteis por segundo medidas na rede.", "RPC Solana") if tps
                       else _nd("adocao", "tps", "Throughput real (TPS, sem votos)", 2, "Medição direta só existe para a Solana.", fonte="RPC público"))
        out.append(_info("adocao", "tvl", "TVL da rede", fmt_usd(d.get("tvl")), "Capital depositado em aplicações da rede." if d.get("tvl") else "Sem TVL no DefiLlama.", "DefiLlama"))
    elif t == "defi":
        out.append(_var_tvl(d, "tvl_var30", "30 dias", 2))
        out.append(_var_tvl(d, "tvl_var90", "90 dias", 1))
        c = d.get("fees_cresc")
        out.append(_m("adocao", "fees_cresc", "Taxas: últimos 30 dias vs 30 anteriores", 3, fmt_pct(c * 100, 1, True) if c is not None else "n/d",
                      _lin(c, [(-0.4, 0), (-0.1, 30), (0, 50), (0.15, 75), (0.5, 100)]),
                      "Uso crescendo ou encolhendo, medido pelo que os usuários pagam.", "DefiLlama") if c is not None
                   else _nd("adocao", "fees_cresc", "Taxas: últimos 30 dias vs 30 anteriores", 3, "O DefiLlama não tem a série de taxas deste protocolo.", fonte="DefiLlama"))
        out.append(_info("adocao", "tvl", "TVL do protocolo", fmt_usd(d.get("tvl")), "Dinheiro depositado." if d.get("tvl") else "Sem TVL no DefiLlama.", "DefiLlama"))
    elif t == "stablecoin":
        s = d.get("stable") or {}
        c = s.get("cresc30")
        out.append(_m("adocao", "cresc30", "Oferta: variação em 30 dias", 3, fmt_pct(c * 100, 1, True) if c is not None else "n/d",
                      _lin(c, [(-0.3, 0), (-0.1, 30), (-0.03, 55), (0, 70), (0.05, 90), (0.25, 85), (0.6, 55)]),
                      "Crescimento moderado indica demanda; queda forte pode indicar resgates em massa, e salto muito grande, risco.", "DefiLlama") if c is not None
                   else _nd("adocao", "cresc30", "Oferta: variação em 30 dias", 3, "Sem histórico de oferta no DefiLlama.", fonte="DefiLlama"))
        out.append(_m_liquidez("adocao", 1)(d))
    return out


def _var_tvl(d, chave, rot, peso):
    v = d.get(chave)
    nome = f"TVL: variação em {rot}"
    if v is None:
        return _nd("adocao", chave, nome, peso, "Sem histórico de TVL no DefiLlama.", fonte="DefiLlama")
    return _m("adocao", chave, nome, peso, fmt_pct(v * 100, 1, True), _lin(v, [(-0.3, 0), (-0.1, 25), (0, 50), (0.1, 75), (0.3, 100)]),
              "Capital entrando." if v >= 0.05 else ("Capital estável." if v >= -0.10 else "Capital saindo."), "DefiLlama")


def _m_orcamento_seguranca(d, peso):
    nome = "Segurança paga pelos usuários (taxas ÷ custo da emissão)"
    fees, mc, infl = d.get("fees30"), d.get("mcap"), d.get("infl")
    if fees is None or not mc:
        return _nd("saude", "orcamento", nome, peso, "Sem taxas da rede no DefiLlama ou sem valor de mercado.", fonte="DefiLlama")
    if infl is None:
        return _nd("saude", "orcamento", nome, peso, "Sem inflação estimada para calcular o custo da emissão.", fonte="CoinGecko")
    fa = _anual(fees)
    if infl <= 0:
        return _m("saude", "orcamento", nome, peso, "Sem emissão líquida", 90,
                  "A oferta não cresce: a segurança não depende de diluição dos detentores.", "DefiLlama + CoinGecko", "calculado")
    custo = infl / 100 * mc
    r = fa / custo
    return _m("saude", "orcamento", nome, peso, fmt_pct(r * 100, 1), _lin(r, [(0, 5), (0.05, 20), (0.25, 45), (0.75, 70), (1.5, 90), (3, 100)]),
              f"Usuários pagam ≈ {fmt_usd(fa)}/ano em taxas; a emissão custa ≈ {fmt_usd(custo)}/ano em diluição. "
              f"Só {fmt_pct(min(r, 9.99) * 100, 0)} do custo é coberto por quem usa a rede.",
              "DefiLlama + CoinGecko", "calculado",
              "Quem faz staking é compensado pela emissão; a métrica mostra quem paga a segurança, não perda de quem faz staking.")


def _saude(d):
    t, out = d["tipo"], []
    cap = captura_valor(d)
    if t == "bitcoin" or t == "reserva":
        out.append(_m_orcamento_seguranca(d, 2))
    elif t == "blockchain":
        out.append(_m_orcamento_seguranca(d, 3))
        if cap and cap["share_hol"] is not None:
            sh = cap["share_hol"]
            out.append(_m("saude", "captura", "Valor capturado pelo token (queima ou recompra ÷ taxas)", 3, fmt_pct(sh * 100, 1),
                          _lin(sh, [(0, 10), (0.1, 35), (0.3, 60), (0.6, 85), (1, 100)]), cap["texto"], "DefiLlama", "calculado",
                          "Receita da rede não é o mesmo que valor para o token: só conta o que é queimado, recomprado ou distribuído."))
        else:
            out.append(_nd("saude", "captura", "Valor capturado pelo token (queima ou recompra ÷ taxas)", 3,
                           "Não há dado de quanto das taxas chega ao detentor (a queima só é medida no Ethereum).", fonte="DefiLlama"))
        out.append(_info("saude", "fees", "Taxas pagas à rede (30 dias)", fmt_usd(d.get("fees30")), "Só informativa: a demanda já entra no pilar de utilidade.", "DefiLlama"))
    elif t == "defi":
        rev, fees = d.get("rev30"), d.get("fees30")
        ra = _anual(rev)
        if rev is None:
            out.append(_nd("saude", "receita", "Receita retida pelo protocolo (anualizada)", 2, "O DefiLlama não informa receita deste protocolo.", fonte="DefiLlama"))
        elif rev == 0:
            out.append(_m("saude", "receita", "Receita retida pelo protocolo (anualizada)", 2, "US$ 0", 5, "O protocolo não retém receita: tudo vai a provedores de liquidez.", "DefiLlama"))
        else:
            out.append(_m("saude", "receita", "Receita retida pelo protocolo (anualizada)", 2, fmt_usd(ra),
                          _lin_log(ra, [(1e5, 10), (1e6, 30), (1e7, 55), (1e8, 80), (5e8, 100)]),
                          f"Receita de 30 dias: {fmt_usd(rev)}. Ainda não diz se chega ao token (veja a métrica abaixo).", "DefiLlama", "calculado"))
        tk = _razao(rev, fees)
        out.append(_m("saude", "take", "Retenção do protocolo (receita ÷ taxas)", 1, fmt_pct(tk * 100, 1),
                      _lin(tk, [(0, 10), (0.05, 35), (0.15, 60), (0.3, 85), (0.5, 100)]),
                      "Parte das taxas que fica com o protocolo; o resto remunera provedores de liquidez.", "DefiLlama", "calculado") if tk is not None
                   else _nd("saude", "take", "Retenção do protocolo (receita ÷ taxas)", 1, "Sem receita ou taxas.", fonte="DefiLlama"))
        if cap and cap["share_hol"] is not None:
            sh = cap["share_hol"]
            out.append(_m("saude", "captura", "Valor capturado pelo token (chega ao detentor ÷ taxas)", 4, fmt_pct(sh * 100, 1),
                          _lin(sh, [(0, 5), (0.02, 30), (0.05, 50), (0.15, 80), (0.3, 100)]), cap["texto"], "DefiLlama", "calculado",
                          "Mede quanto das taxas chega de fato ao detentor (recompra, queima ou dividendos), e não só ao protocolo."))
        else:
            out.append(_nd("saude", "captura", "Valor capturado pelo token (chega ao detentor ÷ taxas)", 4,
                           "O DefiLlama não informa receita distribuída ao detentor. Receita do protocolo não prova captura pelo token.", fonte="DefiLlama"))
    elif t == "stablecoin":
        res = (d.get("manual") or {}).get("reservas")
        out.append(_m("saude", "reservas", "Transparência das reservas (informado por você)", 3, res, RESERVAS.get(res),
                      "Composição e auditoria das reservas não vêm de API gratuita; esta nota reflete o que você informou.", origem="manual") if res in RESERVAS
                   else _nd("saude", "reservas", "Transparência das reservas (informado por você)", 3,
                            "Nenhuma API gratuita traz a composição das reservas. Informe no painel de dados manuais.", origem="manual"))
    else:  # outros
        out.append(_nd("saude", "receita", "Receita e captura de valor", 2, "Sem modelo de receita publicado para esta categoria.", fonte="DefiLlama"))
    return out


def _m_inflacao(d, bom, medio, peso=3):
    i = d.get("infl")
    nome = "Inflação anual da oferta (estimada)"
    if i is None:
        return _nd("token", "infl", nome, peso, "Sem histórico de oferta na CoinGecko.", fonte="CoinGecko")
    nota = _lin(i, [(-1, 100), (0, 95), (bom, 80), (medio, 50), (medio * 2.5, 15), (medio * 5, 0)])
    txt = ("Oferta encolhendo: o ativo é deflacionário." if i < 0 else
           "Emissão baixa: pouca diluição." if i <= bom else "Emissão moderada: precisa de demanda nova para compensar." if i <= medio
           else "Emissão alta: a oferta cresce rápido e dilui os detentores.")
    return _m("token", "infl", nome, peso, fmt_pct(i, 2, True), nota, txt, "CoinGecko", "calculado",
              f"Crescimento da oferta em circulação em 12 meses. Referência desta categoria: bom até {bom:g}% e fraco acima de {medio:g}%.")


def _token(d):
    t, out = d["tipo"], []
    mc, fdv = d.get("mcap"), d.get("fdv")
    man = d.get("manual") or {}
    if t in ("bitcoin", "reserva"):
        circ, mx = d.get("circ"), d.get("maximo")
        if circ and mx:
            r = circ / mx
            out.append(_m("token", "escassez", "Escassez: oferta emitida ÷ teto", 3, fmt_pct(r * 100, 1),
                          _lin(r, [(0.5, 10), (0.7, 30), (0.9, 70), (0.97, 90), (1, 100)]),
                          f"Teto de {fmt_qtd(mx)}; já circulam {fmt_qtd(circ)}. Perto do teto, quase não nascem novas unidades.", "CoinGecko", "calculado"))
        elif circ:
            out.append(_nd("token", "escassez", "Escassez: oferta emitida ÷ teto", 3,
                           "A CoinGecko não informa teto de oferta: pode não haver teto ou o dado estar ausente. Sem confirmação, não pontuamos.",
                           fonte="CoinGecko"))
        else:
            out.append(_nd("token", "escassez", "Escassez: oferta emitida ÷ teto", 3, "Sem dados de oferta.", fonte="CoinGecko"))
        out.append(_m_inflacao(d, 2.0, 4.0))
    elif t == "blockchain":
        perf = bool(d.get("performance"))
        r = _razao(mc, fdv)
        out.append(_m("token", "dil", "Diluição (valor de mercado ÷ FDV)", 3, fmt_pct(r * 100, 0),
                      _lin(r, [(0.2, 0), (0.5, 40), (0.8, 80), (0.95, 100)]),
                      "Parte do suprimento total que já circula; o resto ainda vai entrar no mercado.", "CoinGecko", "calculado") if r is not None
                   else _nd("token", "dil", "Diluição (valor de mercado ÷ FDV)", 3, "Sem FDV para comparar.", fonte="CoinGecko"))
        out.append(_m_inflacao(d, 3.0 if perf else 1.0, 8.0 if perf else 3.0))
        if d.get("tem_queima"):
            rev, preco = d.get("rev30"), d.get("preco")
            circ = d.get("circ") or (_razao(mc, preco))
            infl = d.get("infl")
            if rev is not None and preco and circ and infl is not None:
                q = _anual(rev) / preco / circ * 100
                bruta = infl + q
                cob = q / bruta if bruta > 0 else None
                nota = 100 if infl <= 0 else _lin(cob, [(0, 25), (0.3, 55), (1, 100)]) if cob is not None else None
                out.append(_m("token", "queima", "Queima de taxas ÷ emissão bruta", 2, fmt_pct(q, 2),
                              nota, f"Queima ≈ {fmt_pct(q, 2)} da oferta/ano contra emissão bruta ≈ {fmt_pct(bruta, 2)}.", "DefiLlama + CoinGecko", "calculado"))
            else:
                out.append(_nd("token", "queima", "Queima de taxas ÷ emissão bruta", 2, "Sem dados de taxas queimadas.", fonte="DefiLlama"))
    elif t in ("defi", "outros"):
        r = _razao(mc, fdv)
        out.append(_m("token", "dil", "Diluição (valor de mercado ÷ FDV)", 3, fmt_pct(r * 100, 0),
                      _lin(r, [(0.2, 0), (0.5, 40), (0.8, 80), (0.95, 100)]),
                      "Parte do suprimento total que já circula; o resto ainda vai entrar no mercado.", "CoinGecko", "calculado") if r is not None
                   else _nd("token", "dil", "Diluição (valor de mercado ÷ FDV)", 3, "Sem FDV para comparar.", fonte="CoinGecko"))
        out.append(_m_inflacao(d, 3.0, 8.0))
    elif t == "stablecoin":
        mec = (d.get("stable") or {}).get("mecanismo")
        if mec in MECANISMO:
            rot, nota = MECANISMO[mec]
            out.append(_m("token", "mecanismo", "Mecanismo de criação e destruição da oferta", 3, rot, nota,
                          "Como a moeda mantém US$ 1 define o risco de a oferta perder o valor.", "DefiLlama",
                          dica="Escala educacional: lastro simples e verificável pontua mais que mecanismos algorítmicos."))
        else:
            out.append(_nd("token", "mecanismo", "Mecanismo de criação e destruição da oferta", 3, "O DefiLlama não classifica o mecanismo desta moeda.", fonte="DefiLlama"))
    if t != "stablecoin":
        u = man.get("unlock12m")
        out.append(_m("token", "unlock", "Desbloqueios nos próximos 12 meses (informado por você)", 3, f"{_n(u, 1)}% do suprimento",
                      _lin(u, [(0, 100), (5, 85), (10, 65), (20, 35), (40, 10), (60, 0)]),
                      "Tokens de equipe, investidores e tesouro que podem entrar no mercado e pressionar o preço.", origem="manual") if u is not None
                   else _nd("token", "unlock", "Desbloqueios nos próximos 12 meses (informado por você)", 3,
                            "Não há fonte gratuita e confiável de calendário de desbloqueios. Informe no painel de dados manuais.", origem="manual"))
    return out


def _seg(d):
    t, out = d["tipo"], []
    man = d.get("manual") or {}
    a = d.get("idade_anos")
    out.append(_m("seg", "idade", "Tempo em operação", 2, f"{_n(a, 1)} anos", _lin(a, [(0, 5), (1, 25), (3, 50), (6, 75), (10, 92), (15, 100)]),
                  "Quanto mais tempo no ar sem falha grave, mais testada a rede/protocolo (não prova ausência de risco).", "CoinGecko", "calculado") if a is not None
               else _nd("seg", "idade", "Tempo em operação", 2, "A CoinGecko não informa a data de criação.", fonte="CoinGecko"))
    mc = d.get("mcap")
    if t in ("bitcoin", "reserva", "blockchain", "outros"):
        out.append(_m("seg", "mcap", "Custo de atacar a rede (proxy: valor de mercado)", 2, fmt_usd(mc),
                      _lin_log(mc, [(1e8, 10), (1e9, 30), (1e10, 55), (1e11, 85), (5e11, 100)]),
                      "Quanto maior o valor do token, mais caro é comprar o controle da rede.", "CoinGecko", dica="Proxy simples; não mede a distribuição real do poder.") if mc
                   else _nd("seg", "mcap", "Custo de atacar a rede (proxy: valor de mercado)", 2, "Sem valor de mercado.", fonte="CoinGecko"))
    if t == "bitcoin":
        h = (d.get("btc") or {}).get("hash_var90")
        out.append(_m("seg", "hash", "Poder de mineração (hashrate): variação em 90 dias", 3, fmt_pct(h * 100, 1, True),
                      _lin(h, [(-0.3, 10), (-0.1, 40), (0, 60), (0.2, 85), (0.5, 100)]),
                      "Hashrate crescendo = mais energia protegendo a rede; queda forte enfraquece a segurança.", "blockchain.com") if h is not None
                   else _nd("seg", "hash", "Poder de mineração (hashrate): variação em 90 dias", 3, "blockchain.com indisponível agora.", fonte="blockchain.com"))
    if t in ("bitcoin", "reserva", "blockchain"):
        nk = man.get("nakamoto")
        out.append(_m("seg", "nakamoto", "Coeficiente de Nakamoto (informado por você)", 3, _n(nk, 0),
                      _lin(nk, [(1, 5), (3, 25), (10, 60), (20, 80), (35, 100)]),
                      "Número mínimo de entidades (validadores, pools) que juntas controlam mais da metade da rede. Maior = mais descentralizada.",
                      origem="manual") if nk
                   else _nd("seg", "nakamoto", "Coeficiente de Nakamoto (informado por você)", 3, "Sem API gratuita confiável. Informe no painel de dados manuais.", origem="manual"))
    if t == "defi":
        tvl = d.get("tvl")
        out.append(_m("seg", "tvl", "Capital confiado ao protocolo (TVL)", 2, fmt_usd(tvl),
                      _lin_log(tvl, [(1e7, 15), (1e8, 40), (1e9, 70), (1e10, 95)]),
                      "Mais capital em jogo aumenta o incentivo de ataque, mas também mostra confiança acumulada.", "DefiLlama") if tvl
                   else _nd("seg", "tvl", "Capital confiado ao protocolo (TVL)", 2, "Sem TVL no DefiLlama.", fonte="DefiLlama"))
    if t in ("defi", "stablecoin", "outros"):
        au = man.get("auditoria")
        out.append(_m("seg", "auditoria", "Auditorias de segurança (informado por você)", 3 if t != "outros" else 2, au, AUDITORIA.get(au),
                      "Auditorias reduzem, mas não eliminam, o risco de falhas em contratos.", origem="manual") if au in AUDITORIA
                   else _nd("seg", "auditoria", "Auditorias de segurança (informado por você)", 3 if t != "outros" else 2,
                            "Sem fonte gratuita. Informe no painel de dados manuais.", origem="manual"))
    if t == "stablecoin":
        s = d.get("stable") or {}
        if s.get("peg_tipo") != "peggedUSD":
            msg = "A paridade só é avaliada para stablecoins atreladas ao dólar (o DefiLlama não confirmou esta)."
            out.append(_nd("seg", "dias", "Dias dentro de ±0,5% de US$ 1 (12 meses)", 3, msg, fonte="CoinGecko"))
            out.append(_nd("seg", "desvio", "Maior desvio de US$ 1 (12 meses)", 3, msg, fonte="CoinGecko"))
        else:
            dias, dv = s.get("dias_na_faixa"), s.get("desvio_max")
            out.append(_m("seg", "dias", "Dias dentro de ±0,5% de US$ 1 (12 meses)", 3, fmt_pct(dias * 100, 1),
                          _lin(dias, [(0.8, 0), (0.95, 35), (0.99, 75), (1, 100)]),
                          "Quanto tempo a moeda ficou perto de US$ 1 nos últimos 12 meses.", "CoinGecko", "calculado") if dias is not None
                       else _nd("seg", "dias", "Dias dentro de ±0,5% de US$ 1 (12 meses)", 3, "Sem histórico de preços.", fonte="CoinGecko"))
            out.append(_m("seg", "desvio", "Maior desvio de US$ 1 (12 meses)", 3, fmt_pct(dv * 100, 2),
                          _lin(dv, [(0, 100), (0.005, 90), (0.01, 70), (0.03, 35), (0.1, 0)]),
                          "Pior momento de perda da paridade no período (preço de fechamento diário).", "CoinGecko", "calculado") if dv is not None
                       else _nd("seg", "desvio", "Maior desvio de US$ 1 (12 meses)", 3, "Sem histórico de preços.", fonte="CoinGecko"))
    return out


def _dev(d):
    t, out = d["tipo"], []
    dv = d.get("dev")
    man = d.get("manual") or {}
    zerado = bool(dv) and not any(dv.get(k) for k in ("commits_4w", "contribuidores", "stars", "issues_total"))
    if not dv or not dv.get("repos") or zerado:
        mot = ("A CoinGecko devolveu apenas zeros: o repositório provavelmente não é rastreado, e zero não prova abandono." if zerado
               else "A CoinGecko não lista repositório público (código fechado ou não rastreado).")
        out += [_nd("dev", "commits", "Atividade de código (commits em 4 semanas)", 3, mot, fonte="CoinGecko"),
                _nd("dev", "contrib", "Contribuidores", 2, mot, fonte="CoinGecko")]
    else:
        c, ct = dv.get("commits_4w"), dv.get("contribuidores")
        out.append(_m("dev", "commits", "Atividade de código (commits em 4 semanas)", 3, _n(c, 0),
                      _lin(c, [(0, 0), (5, 20), (30, 50), (100, 75), (300, 95), (800, 100)]),
                      f"{dv['repos']} repositório(s) público(s) rastreado(s). Zero commits pode ser abandono ou repositório não acompanhado.", "CoinGecko") if c is not None
                   else _nd("dev", "commits", "Atividade de código (commits em 4 semanas)", 3, "A CoinGecko não trouxe commits.", fonte="CoinGecko"))
        out.append(_m("dev", "contrib", "Contribuidores (pull requests)", 2, _n(ct, 0),
                      _lin(ct, [(1, 10), (5, 35), (20, 60), (60, 85), (200, 100)]),
                      "Mais gente diferente contribuindo reduz a dependência de uma equipe.", "CoinGecko") if ct is not None
                   else _nd("dev", "contrib", "Contribuidores (pull requests)", 2, "A CoinGecko não trouxe contribuidores.", fonte="CoinGecko"))
        it, itf = dv.get("issues_total"), dv.get("issues_fechadas")
        if it and it >= 20 and itf is not None:
            r = itf / it
            out.append(_m("dev", "issues", "Problemas resolvidos (issues fechadas ÷ total)", 1, fmt_pct(r * 100, 0),
                          _lin(r, [(0.3, 20), (0.6, 55), (0.85, 90), (1, 100)]), "Equipe que fecha problemas tende a manter o projeto.", "CoinGecko", "calculado"))
        if dv.get("stars") is not None:
            out.append(_info("dev", "stars", "Estrelas no GitHub", fmt_qtd(dv["stars"]), "Interesse da comunidade de desenvolvedores; não entra na nota.", "CoinGecko"))
    g = man.get("governanca")
    out.append(_m("dev", "gov", "Modelo de governança (informado por você)", 3, g, GOVERNANCA.get(g),
                  "Quem decide mudanças no protocolo e como. Governança concentrada é risco de decisão unilateral.", origem="manual") if g in GOVERNANCA
               else _nd("dev", "gov", "Modelo de governança (informado por você)", 3, "Sem API gratuita. Informe no painel de dados manuais.", origem="manual"))
    return out


def _razao_pares(valor, mediana):
    return valor / mediana if valor is not None and mediana not in (None, 0) else None


def _val(d):
    t, out = d["tipo"], []
    mc = d.get("mcap")
    par = d.get("pares") or {}
    if t in ("bitcoin", "reserva"):
        i = d.get("infl")
        if i is not None and i > 0:
            s2f = 100 / i
            out.append(_info("val", "s2f", "Estoque ÷ fluxo (anos de emissão atual)", f"{_n(s2f, 0)} anos",
                             "Quantos anos a emissão atual levaria para criar a oferta existente. Mede escassez, não preço justo; o modelo é contestado e não entra na nota.",
                             "CoinGecko", "calculado"))
        else:
            out.append(_info("val", "s2f", "Estoque ÷ fluxo (anos de emissão atual)", "n/d", "Sem inflação positiva para calcular.", "CoinGecko"))
        out.append(_info("val", "ancora", "Âncora de preço", "n/d",
                         "Reserva de valor não tem receita nem lucro: não existe valor justo por múltiplos, Graham, Bazin ou fluxo de caixa descontado, nem comparável direto. Por isso este pilar tem peso zero por padrão."))
    elif t == "blockchain":
        fa = _anual(d.get("fees30"))
        pt = _razao(mc, fa)
        out.append(_m("val", "p_taxas", "Preço/Taxas (valor de mercado ÷ taxas anualizadas)", 3, _fx(pt),
                      _lin(pt, [(20, 100), (60, 80), (120, 55), (200, 30), (500, 5)]),
                      f"Taxas de 30 dias: {fmt_usd(d.get('fees30'))}. Quanto menor, menos o mercado paga por cada dólar de uso.", "DefiLlama + CoinGecko", "calculado") if pt is not None
                   else _nd("val", "p_taxas", "Preço/Taxas (valor de mercado ÷ taxas anualizadas)", 3, "Sem taxas da rede ou sem valor de mercado.", fonte="DefiLlama"))
        mt = _razao(mc, d.get("tvl"))
        rel = _razao_pares(mt, par.get("mc_tvl_mediana"))
        out.append(_m("val", "pares_tvl", "Valor de mercado ÷ TVL, comparado aos pares", 3, f"{_fx(mt)} (mediana {_fx(par['mc_tvl_mediana'])})",
                      _lin(rel, [(0.25, 100), (0.6, 80), (1, 55), (1.7, 30), (3, 10)]),
                      f"Pares: {par.get('grupo', 'Layer 1')} ({par.get('n', 0)} redes com dados). Abaixo da mediana = mais barato para o capital que a rede abriga.",
                      "CoinGecko + DefiLlama", "calculado") if rel is not None
                   else _nd("val", "pares_tvl", "Valor de mercado ÷ TVL, comparado aos pares", 3, "Sem TVL ou sem pares suficientes (mínimo 3) para comparar.", fonte="CoinGecko + DefiLlama"))
    elif t == "defi":
        rev = d.get("rev30")
        ra = _anual(rev)
        if mc and rev is not None and rev == 0:
            out.append(_m("val", "ps", "P/S (valor de mercado ÷ receita do protocolo)", 3, "Sem receita", 5,
                          "O protocolo não retém receita: não há receita para comparar com o preço.", "DefiLlama"))
        else:
            ps = _razao(mc, ra)
            out.append(_m("val", "ps", "P/S (valor de mercado ÷ receita do protocolo)", 3, _fx(ps),
                          _lin(ps, [(5, 100), (15, 80), (25, 60), (40, 35), (100, 10)]),
                          f"Receita de 30 dias: {fmt_usd(rev)}. Parecido com o P/L de uma ação, mas sobre a receita do protocolo.", "DefiLlama + CoinGecko", "calculado") if ps is not None
                       else _nd("val", "ps", "P/S (valor de mercado ÷ receita do protocolo)", 3, "Sem receita publicada ou sem valor de mercado.", fonte="DefiLlama"))
        pt = _razao(mc, _anual(d.get("fees30")))
        out.append(_m("val", "p_taxas", "Preço/Taxas (valor de mercado ÷ taxas anualizadas)", 2, _fx(pt),
                      _lin(pt, [(10, 100), (20, 80), (40, 55), (60, 35), (150, 10)]),
                      f"Taxas de 30 dias: {fmt_usd(d.get('fees30'))}.", "DefiLlama + CoinGecko", "calculado") if pt is not None
                   else _nd("val", "p_taxas", "Preço/Taxas (valor de mercado ÷ taxas anualizadas)", 2, "Sem taxas ou sem valor de mercado.", fonte="DefiLlama"))
        cap = captura_valor(d)
        ha = _anual(cap["holders"]) if cap else None
        y = _razao(ha, mc)
        out.append(_m("val", "yield", "Rendimento efetivo ao detentor (recompra, queima ou dividendos ÷ valor de mercado)", 3, fmt_pct(y * 100, 2),
                      _lin(y, [(0, 0), (0.005, 30), (0.02, 60), (0.05, 85), (0.1, 100)]),
                      f"Distribuído ao detentor em 30 dias: {fmt_usd(cap['holders'])}. É o único retorno que o token captura de fato; não é DCF nem Bazin.",
                      "DefiLlama + CoinGecko", "calculado") if y is not None
                   else _nd("val", "yield", "Rendimento efetivo ao detentor (recompra, queima ou dividendos ÷ valor de mercado)", 3,
                            "Sem dado do que chega ao detentor do token.", fonte="DefiLlama"))
        mt = _razao(mc, d.get("tvl"))
        rel = _razao_pares(mt, par.get("mc_tvl_mediana"))
        out.append(_m("val", "pares_tvl", "Valor de mercado ÷ TVL, comparado aos pares", 2, f"{_fx(mt)} (mediana {_fx(par['mc_tvl_mediana'])})",
                      _lin(rel, [(0.25, 100), (0.6, 80), (1, 55), (1.7, 30), (3, 10)]),
                      f"Pares: {par.get('grupo', 'mesmo setor')} ({par.get('n', 0)} protocolos com dados).", "CoinGecko + DefiLlama", "calculado") if rel is not None
                   else _nd("val", "pares_tvl", "Valor de mercado ÷ TVL, comparado aos pares", 2, "Sem pares suficientes (mínimo 3) no mesmo setor.", fonte="CoinGecko + DefiLlama"))
        ptx_rel = _razao_pares(pt, par.get("p_taxas_mediana"))
        if ptx_rel is not None:
            out.append(_m("val", "pares_taxas", "Preço/Taxas, comparado aos pares", 2, f"{_fx(pt)} (mediana {_fx(par['p_taxas_mediana'])})",
                          _lin(ptx_rel, [(0.25, 100), (0.6, 80), (1, 55), (1.7, 30), (3, 10)]),
                          "Abaixo da mediana do setor = mais barato para o quanto os usuários pagam.", "CoinGecko + DefiLlama", "calculado"))
    elif t == "stablecoin":
        out.append(_info("val", "na", "Valuation", "Não se aplica", "O preço-alvo é US$ 1. Comparar múltiplos ou 'barato/caro' não faz sentido para uma moeda estável."))
    else:
        out.append(_nd("val", "na", "Valuation", 2, "Sem modelo de valuation confiável para esta categoria."))
    return out


def _fx(v):
    return "n/d" if v is None else fmt_x(v, 1)


_CONSTRUTORES = {"util": _util, "adocao": _adocao, "saude": _saude, "token": _token, "seg": _seg, "dev": _dev, "val": _val}


# --------------------------------------------------------------------------- riscos, forças e conclusão
_RISCOS_TIPO = {
    "bitcoin": ["Segurança de longo prazo: o subsídio de blocos cai a cada halving e precisará ser compensado por taxas.",
                "Sem receita ou lucro: o preço depende de aceitação contínua como reserva de valor.",
                "Risco regulatório e de concentração de mineração e custódia."],
    "reserva": ["Sem receita ou lucro: o preço depende de aceitação e liquidez.",
                "Redes menores de prova de trabalho têm segurança mais barata de atacar."],
    "blockchain": ["Concorrência entre redes: o capital e os desenvolvedores podem migrar.",
                   "Parte da receita vai a validadores e não ao token: taxas altas não garantem valor para o detentor.",
                   "Concentração de validadores e de tokens em poucas mãos."],
    "defi": ["Falhas em contratos inteligentes e ataques podem causar perdas totais.",
             "Receita do protocolo pode vir de incentivos pagos em tokens novos, o que dilui o detentor.",
             "Risco regulatório sobre exchanges e empréstimos descentralizados."],
    "stablecoin": ["Risco do emissor e das reservas: a paridade depende de ativos que o usuário não controla.",
                   "Risco regulatório e de congelamento de endereços.",
                   "Perda de paridade em momentos de estresse de mercado."],
    "outros": ["Categoria não reconhecida: a régua é básica e pode ignorar riscos específicos do projeto."],
}


def _scored(res):
    return [m for p in res["pilares"] for m in p["metricas"] if m.peso > 0 and m.nota is not None]


def _riscos(d, res):
    t, r = d["tipo"], []
    mc, fdv = d.get("mcap"), d.get("fdv")
    dil = _razao(mc, fdv)
    if dil is not None and dil < 0.5:
        r.append(("alto", f"Só {fmt_pct(dil * 100, 0)} do suprimento circula: tokens novos podem pressionar o preço."))
    elif dil is not None and dil < 0.8 and t not in ("bitcoin", "reserva", "stablecoin"):
        r.append(("médio", f"{fmt_pct((1 - dil) * 100, 0)} do suprimento ainda vai entrar no mercado."))
    i = d.get("infl")
    if i is not None and i > (8 if t in ("defi", "outros") else 4):
        r.append(("alto", f"Emissão alta ({fmt_pct(i, 1, True)} ao ano) dilui quem já detém o ativo."))
    u = (d.get("manual") or {}).get("unlock12m")
    if u is not None and u >= 20:
        r.append(("alto", f"{_n(u, 0)}% do suprimento será desbloqueado em 12 meses (dado informado por você)."))
    cap = captura_valor(d)
    if t == "defi" and cap:
        if cap["cls"] == "bad":
            r.append(("alto", "O token não captura valor: o DefiLlama registra receita zero para o protocolo."))
        elif cap["veredito"].startswith("Receita existe"):
            r.append(("médio", "Nenhuma distribuição da receita ao detentor foi registrada: o token só captura valor se a governança ativar isso."))
        elif cap["cls"] == "na" and cap["rev"]:
            r.append(("médio", "Não há dado de quanto da receita chega ao detentor do token."))
    for k, rot in (("tvl_var30", "30 dias"), ("tvl_var90", "90 dias")):
        v = d.get(k)
        if v is not None and v <= -0.15:
            r.append(("médio", f"O capital depositado caiu {fmt_pct(abs(v) * 100, 0)} em {rot}."))
            break
    s = d.get("stable") or {}
    if t == "stablecoin":
        if s.get("desvio_max") is not None and s["desvio_max"] >= 0.03:
            r.append(("alto", f"A moeda se afastou {fmt_pct(s['desvio_max'] * 100, 1)} de US$ 1 nos últimos 12 meses."))
        if s.get("mecanismo") == "algorithmic":
            r.append(("alto", "Mecanismo algorítmico: moedas assim já perderam a paridade de forma permanente no passado."))
    if d.get("vol_anual") is not None and d["vol_anual"] > 100 and t != "stablecoin":
        r.append(("médio", f"Volatilidade anual de {fmt_pct(d['vol_anual'], 0)}: variações bruscas de preço são comuns."))
    if d.get("queda") is not None and d["queda"] <= -60 and t != "stablecoin":
        r.append(("médio", f"O preço está {fmt_pct(abs(d['queda']), 0)} abaixo da máxima de 12 meses."))
    g = _razao(d.get("vol24"), mc)
    if g is not None and g < 0.003:
        r.append(("médio", "Liquidez muito baixa: pode ser difícil comprar ou vender sem mexer no preço."))
    dv = d.get("dev")
    if dv and dv.get("repos") and dv.get("commits_4w") == 0:
        r.append(("médio", "Nenhum commit nas últimas 4 semanas nos repositórios rastreados."))
    if t == "bitcoin" and any(m.chave == "orcamento" and m.nota is not None and m.nota < 30 for m in _scored(res)):
        r.append(("médio", "As taxas pagam uma fração pequena do custo de segurança; o resto vem da emissão de novos bitcoins."))
    sem = [p["nome"] for p in res["pilares"] if p["peso"] > 0 and p["nota"] is None]
    if sem:
        r.append(("info", "Análise incompleta: sem dados suficientes em " + "; ".join(sem) + ". A nota geral ignora esses pilares."))
    for txt in _RISCOS_TIPO.get(t, []):
        r.append(("estrutural", txt))
    ordem = {"alto": 0, "médio": 1, "info": 2, "estrutural": 3}
    return sorted(r, key=lambda x: ordem[x[0]])


def _fortes_fracos(res):
    ms = [(p["peso_pct"], p["nome"], m) for p in res["pilares"] if p["peso"] > 0 for m in p["metricas"] if m.peso > 0 and m.nota is not None]
    fortes = sorted((x for x in ms if x[2].nota >= 70), key=lambda x: -(x[0] * x[2].peso * x[2].nota))[:5]
    fracos = sorted((x for x in ms if x[2].nota <= 40), key=lambda x: -(x[0] * x[2].peso * (100 - x[2].nota)))[:5]
    fmt = lambda x: {"pilar": x[1], "metrica": x[2].nome, "valor": x[2].valor, "nota": x[2].nota, "texto": x[2].leitura}
    return [fmt(x) for x in fortes], [fmt(x) for x in fracos]


def _justificar(p):
    sc = sorted((m for m in p["metricas"] if m.peso > 0 and m.nota is not None), key=lambda m: -m.nota)
    sem = [m.nome for m in p["metricas"] if m.peso > 0 and m.nota is None]
    if not any(m.peso > 0 for m in p["metricas"]):
        return "Não se aplica a este tipo de ativo: não há método confiável de pontuação, então o pilar fica fora da nota geral."
    if p["peso"] <= 0:
        return "Peso zerado: este pilar não entra na nota geral."
    if p["nota"] is None:
        base = (f"Sem dados suficientes (cobertura de {p['cobertura']:.0%}, mínimo {COBERTURA_MIN_PILAR:.0%}): o pilar foi excluído da nota geral "
                "e os pesos dos demais foram redistribuídos.")
        if sc:
            base += f" Nota parcial dos dados disponíveis: {p['nota_parcial']:.0f}."
    else:
        pos = [m for m in sc if m.nota >= 60][:2]
        neg = [m for m in reversed(sc) if m.nota < 45][:2]
        base = f"Nota {p['nota']:.0f}/100 (peso {p['peso_pct']:.0f}%, cobertura de dados {p['cobertura']:.0%})."
        if pos:
            base += " A favor: " + "; ".join(f"{m.nome} ({m.valor}, {m.nota:.0f})" for m in pos) + "."
        if neg:
            base += " Contra: " + "; ".join(f"{m.nome} ({m.valor}, {m.nota:.0f})" for m in neg) + "."
    if sem and p["nota"] is not None:
        base += " Sem dados: " + "; ".join(sem) + "."
    return base


def _conclusao(d, res):
    nome = d.get("nome") or "O ativo"
    t = TIPOS[d["tipo"]]
    if res["nota"] is None or res["cobertura"] < COBERTURA_MIN_GERAL:
        return (f"{nome}, avaliado como {t}, tem dados insuficientes para uma nota geral confiável "
                f"(cobertura de {res['cobertura']:.0%}; mínimo {COBERTURA_MIN_GERAL:.0%}). "
                "Preencha os dados manuais ou tente de novo quando as APIs responderem. Ferramenta educacional, não é recomendação.")
    n = res["nota"]
    pi = [p for p in res["pilares"] if p["nota"] is not None and p["peso"] > 0]
    mel, pio = max(pi, key=lambda p: p["nota"]), min(pi, key=lambda p: p["nota"])
    txt = f"{nome}, avaliado como {t}, recebe nota {n:.0f}/100: {res['rotulo'].lower()}. "
    if mel is not pio:
        txt += f"O ponto mais forte é {mel['nome'].lower()} ({mel['nota']:.0f}); o mais fraco, {pio['nome'].lower()} ({pio['nota']:.0f}). "
    cap = res.get("captura")
    if cap and d["tipo"] in ("defi", "blockchain"):
        txt += cap["texto"] + " "
    val = next((p for p in res["pilares"] if p["chave"] == "val"), None)
    if val and val["nota"] is not None and val["peso"] > 0 and d["tipo"] in ("blockchain", "defi"):
        txt += ("Nos múltiplos e comparações com pares usados, o valuation aparece " + ("favorável frente aos limites de referência. " if val["nota"] >= 65 else
                "intermediário. " if val["nota"] >= 40 else "exigente (caro) frente aos limites de referência. "))
    if res["cobertura"] < COBERTURA_CONFIAVEL:
        txt += f"Atenção: a cobertura de dados é de {res['cobertura']:.0%}, então a nota é provisória. "
    if res["piso"] is not None and res["teto"] is not None and res["teto"] - res["piso"] >= 10:
        txt += (f"Se tudo o que falta valesse 0 ou 100, a nota ficaria entre {res['piso']:.0f} e {res['teto']:.0f}: "
                "dado ausente não é ponto a favor. ")
    txt += "Ferramenta educacional: a nota resume fundamentos medidos, não prevê preço nem é recomendação de compra ou venda."
    return txt


# --------------------------------------------------------------------------- cálculo
def analisar(d: dict, pesos: dict | None = None) -> dict:
    """Calcula pilares, nota geral e textos. `pesos` sobrescreve os pesos padrão do tipo (qualquer escala; é normalizado)."""
    d = dict(d)
    if d.get("tipo") not in TIPOS:
        d["tipo"] = "outros"
    tipo = d["tipo"]
    pes = dict(PESOS_PADRAO[tipo])
    for k, v in (pesos or {}).items():
        if k in pes:
            pes[k] = max(0.0, float(v))
    soma_pesos = sum(pes.values())
    pilares = []
    for chave, nome in PILARES:
        ms = _CONSTRUTORES[chave](d)
        com_peso = [m for m in ms if m.peso > 0]
        total = sum(m.peso for m in com_peso)
        validos = [m for m in com_peso if m.nota is not None]
        cob = sum(m.peso for m in validos) / total if total else 0.0
        parcial = sum(m.peso * m.nota for m in validos) / sum(m.peso for m in validos) if validos else None
        ok = parcial is not None and cob >= COBERTURA_MIN_PILAR
        nota = parcial if ok else None
        soma_n = sum(m.peso * m.nota for m in validos)
        falta = sum(m.peso for m in com_peso if m.nota is None)
        piso = soma_n / total if total else 0.0
        teto = (soma_n + falta * 100) / total if total else 100.0
        pilares.append({"chave": chave, "nome": nome, "peso": pes[chave], "peso_pct": pes[chave] / soma_pesos * 100 if soma_pesos else 0.0,
                        "nota": nota, "nota_parcial": parcial, "cobertura": cob, "cls": cls_nota(nota), "metricas": ms,
                        "piso": piso, "teto": teto})
    usados = [p for p in pilares if p["nota"] is not None and p["peso"] > 0]
    w_usado = sum(p["peso"] for p in usados)
    w_total = sum(p["peso"] for p in pilares if p["peso"] > 0)
    nota_geral = sum(p["peso"] * p["nota"] for p in usados) / w_usado if w_usado else None
    cobertura = sum(p["peso"] * p["cobertura"] for p in usados) / w_total if w_total else 0.0
    pesados = [p for p in pilares if p["peso"] > 0 and any(m.peso > 0 for m in p["metricas"])]
    wp = sum(p["peso"] for p in pesados)
    piso = sum(p["peso"] * p["piso"] for p in pesados) / wp if wp else None
    teto = sum(p["peso"] * p["teto"] for p in pesados) / wp if wp else None
    if nota_geral is None or cobertura < COBERTURA_MIN_GERAL:
        rotulo, cls = "Dados insuficientes", "na"
    elif nota_geral >= 75:
        rotulo, cls = "Fundamentos fortes", "good"
    elif nota_geral >= 60:
        rotulo, cls = "Fundamentos sólidos, com ressalvas", "good"
    elif nota_geral >= 45:
        rotulo, cls = "Fundamentos mistos", "fair"
    elif nota_geral >= 30:
        rotulo, cls = "Fundamentos fracos", "bad"
    else:
        rotulo, cls = "Fundamentos muito frágeis", "bad"
    res = {"tipo": tipo, "tipo_rotulo": TIPOS[tipo], "foco": FOCO_TIPO[tipo], "pilares": pilares,
           "nota": nota_geral if cobertura >= COBERTURA_MIN_GERAL else None, "nota_bruta": nota_geral, "cobertura": cobertura,
           "piso": piso, "teto": teto,
           "provisoria": cobertura < COBERTURA_CONFIAVEL, "rotulo": rotulo, "cls": cls,
           "captura": captura_valor(d) if tipo in ("defi", "blockchain", "outros") else None}
    res["fortes"], res["fracos"] = _fortes_fracos(res)
    res["riscos"] = _riscos(d, res)
    res["justificativas"] = [(p["nome"], _justificar(p)) for p in pilares]
    res["conclusao"] = _conclusao(d, res)
    return res
