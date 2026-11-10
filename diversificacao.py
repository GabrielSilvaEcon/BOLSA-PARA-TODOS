"""Diversificação da carteira virtual: o motor didático do Wallet Game. Lógica pura (sem Streamlit, banco ou rede).

A ideia do jogo é ensinar a montar uma carteira diversificada, então esta análise olha só COMO a carteira foi montada:
quantas classes de ativos, quantos ativos, quanto pesa o maior e quanta reserva existe. Nunca olha lucro, retorno nem risco medido,
e a nota não entra no ranking (que continua sendo por retorno). Só a "boa decisão de processo" semanal (jogar.py) usa a mesma régua.

Os perfis abaixo são EXEMPLOS DIDÁTICOS de distribuição por classe, para comparar com a sua carteira. Não são recomendação de investimento.
"""
from __future__ import annotations

import ativos_jogo as A

PESO_RELEVANTE = 0.03          # a partir de 3% do patrimônio a posição conta como "ativo da carteira"
PESO_CLASSE = 0.05             # a partir de 5% do patrimônio a classe conta como "presente"
PESO_ALERTA = 0.25             # nenhum ativo acima de 25%
CRIPTO_ALERTA = 0.10           # cripto: poucos pontos percentuais bastam
MIN_INVESTIDO = 0.20           # abaixo disso a carteira ainda "não começou"

# Exemplos didáticos por perfil: fração do patrimônio em cada grupo. Reserva = renda fixa + caixa.
PERFIS = {
    "conservador": {"nome": "Conservador", "icone": "🛡️", "texto": "Prefere dormir tranquilo: bastante renda fixa e pouca oscilação.",
                    "alvo": {"reserva": 0.60, "fundo": 0.10, "fii": 0.10, "acao": 0.10, "etf": 0.10, "cripto": 0.0}},
    "moderado":    {"nome": "Moderado", "icone": "⚖️", "texto": "Equilibra segurança e crescimento: renda fixa de um lado, bolsa do outro.",
                    "alvo": {"reserva": 0.35, "fundo": 0.10, "fii": 0.15, "acao": 0.20, "etf": 0.15, "cripto": 0.05}},
    "arrojado":    {"nome": "Arrojado", "icone": "🚀", "texto": "Aceita oscilar mais em busca de crescimento: maior fatia em bolsa.",
                    "alvo": {"reserva": 0.15, "fundo": 0.10, "fii": 0.15, "acao": 0.30, "etf": 0.20, "cripto": 0.10}},
}
PERFIL_PADRAO = "moderado"
GRUPOS = ("reserva", "acao", "fii", "etf", "fundo", "cripto")
NOME_GRUPO = {"reserva": "Reserva (renda fixa e caixa)", "acao": "Ações", "fii": "FIIs", "etf": "ETFs", "fundo": "Fundos", "cripto": "Criptomoedas"}
COR_GRUPO = {"reserva": "#3DDC97", "acao": "#8B6CFF", "fii": "#2BA7C9", "etf": "#D23FC8", "fundo": "#7A8CFF", "cripto": "#F2B84B"}

# Por que cada classe ajuda a diversificar (uma frase, linguagem simples)
PORQUE = {
    "reserva": "segura a carteira quando a bolsa cai e é onde fica o dinheiro para emergências e oportunidades",
    "acao": "é onde mora o crescimento de longo prazo, ao custo de oscilar bastante",
    "fii": "paga renda todo mês e depende de imóveis e crédito, não só da bolsa",
    "etf": "traz dezenas de ativos numa única cota, uma forma simples de espalhar o risco",
    "fundo": "entrega a escolha dos ativos a um gestor e abre estratégias que você não monta sozinho",
    "cripto": "se move diferente dos outros ativos, mas é muito volátil: poucos pontos percentuais bastam",
}


# Mini-aulas do Wallet Game (a tela do Streamlit e o app de celular mostram o mesmo texto)
AULAS = (
    ("🥚 Por que não colocar todos os ovos na mesma cesta?",
     "Cada ativo pode cair por um motivo próprio: uma empresa com problema, um setor em crise, uma moeda que desvaloriza. "
     "Quando você espalha o dinheiro, o tombo de um deles pesa pouco no total. Diversificar não impede perdas, mas reduz o susto de perder tudo de uma vez."),
    ("🧩 As seis classes do jogo",
     "Ações (crescimento e dividendos), FIIs (renda de imóveis e crédito), ETFs (cestas prontas, no Brasil e nos EUA), fundos (gestão profissional), "
     "renda fixa (CDI e Tesouro, mais estável) e cripto (muito volátil). Cada uma reage de um jeito ao mesmo acontecimento."),
    ("🛡️ Reserva: a classe que segura a carteira",
     "Renda fixa de liquidez diária (como CDI e Tesouro Selic) não costuma despencar quando a bolsa cai. Ela é a sua reserva: protege e ainda rende. "
     "No jogo, CDI e Tesouro Selic ficam de fora do limite de 40% por ativo justamente por isso."),
    ("⚖️ Rebalancear",
     "Com o tempo, o que subiu fica pesado e o que caiu fica leve, e a carteira foge do plano. Rebalancear é vender um pouco do que cresceu demais e comprar o que ficou pequeno, "
     "voltando às proporções que você escolheu."),
    ("🎯 Cuidado com a falsa diversificação",
     "Dez ações do mesmo setor não são dez cestas: caem juntas. Misture classes, setores e países. E lembre: mais ativos não é melhor em si, o que importa é eles se comportarem de formas diferentes."),
)


def _grupo(classe: str | None) -> str | None:
    if classe == "rf":
        return "reserva"
    return classe if classe in GRUPOS else None


def pesos(estado: dict) -> dict:
    """Fotografia da carteira: patrimônio, peso de cada posição e de cada grupo (todos como fração do patrimônio)."""
    pos = (estado or {}).get("pos") or {}
    ult = (estado or {}).get("ult") or {}
    caixa = max(0.0, float((estado or {}).get("caixa") or 0.0))
    valores = {}
    for tk, p in pos.items():
        px = ult.get(tk) or p.get("pm") or 0.0
        v = p["q"] * px
        if v > 0 and A.valido(tk):
            valores[tk] = v
    pat = caixa + sum(valores.values())
    if pat <= 0:
        return {"pat": 0.0, "posicoes": {}, "grupos": {g: 0.0 for g in GRUPOS}, "caixa": 0.0, "investido": 0.0}
    posicoes = {tk: v / pat for tk, v in valores.items()}
    grupos = {g: 0.0 for g in GRUPOS}
    for tk, w in posicoes.items():
        g = _grupo(A.classe(tk))
        if g:
            grupos[g] += w
    grupos["reserva"] += caixa / pat
    return {"pat": pat, "posicoes": posicoes, "grupos": grupos, "caixa": caixa / pat, "investido": sum(posicoes.values())}


def _pontos_classes(n: int) -> int:
    return {0: 0, 1: 4, 2: 12, 3: 22}.get(n, 30)


def _pontos_concentracao(maior: float, tem: bool) -> int:
    if not tem:
        return 0
    return 25 if maior <= 0.15 else 20 if maior <= 0.20 else 15 if maior <= 0.25 else 8 if maior <= 0.35 else 2


def _pontos_ativos(n: int) -> int:
    return 20 if n >= 10 else 17 if n >= 8 else 14 if n >= 6 else 11 if n >= 5 else 6 if n >= 3 else 2 if n >= 1 else 0


def _pontos_setores(n_acoes: int, n_setores: int) -> int:
    if n_acoes < 2:
        return 5                                   # sem várias ações, esse quesito não pesa contra nem a favor
    return 10 if n_setores >= 4 else 7 if n_setores >= 3 else 4 if n_setores >= 2 else 1


def _pontos_reserva(w: float) -> int:
    return 15 if 0.10 <= w <= 0.70 else 8 if (0.05 <= w < 0.10 or 0.70 < w <= 0.85) else 3


def _nivel(nota: int, investido: float) -> tuple[str, str]:
    if investido < MIN_INVESTIDO:
        return "Largada", "Sua carteira ainda é quase só caixa. Comece escolhendo ativos de classes diferentes."
    if nota >= 85:
        return "Carteira equilibrada", "Seus ovos estão em várias cestas. É assim que se reduz o impacto de um tombo isolado."
    if nota >= 65:
        return "Bem encaminhada", "Boa base. Mais um ajuste ou dois e a carteira fica bem espalhada."
    if nota >= 40:
        return "Em construção", "Já há alguma variedade, mas ainda dá para espalhar melhor."
    return "Concentrada", "Muito dinheiro em poucas cestas. Um tombo em uma delas pesa demais na carteira."


def analisar(estado: dict, perfil: str = PERFIL_PADRAO) -> dict:
    """Nota de diversificação (0 a 100) com o detalhe de cada quesito, comparação com o perfil de exemplo e dicas."""
    f = pesos(estado)
    perfil = perfil if perfil in PERFIS else PERFIL_PADRAO
    posicoes, grupos = f["posicoes"], f["grupos"]
    relevantes = {tk: w for tk, w in posicoes.items() if w >= PESO_RELEVANTE}
    de_risco = {tk: w for tk, w in posicoes.items() if not A.isento_peso(tk)}      # CDI e Tesouro Selic são a reserva: não contam como concentração
    maior_tk, maior = (max(de_risco.items(), key=lambda kv: kv[1]) if de_risco else (None, 0.0))
    classes_presentes = [g for g in GRUPOS if g != "reserva" and grupos[g] >= PESO_CLASSE]
    if sum(w for tk, w in posicoes.items() if _grupo(A.classe(tk)) == "reserva") >= PESO_CLASSE:
        classes_presentes.append("reserva")                    # só conta como classe a renda fixa de verdade, não o caixa parado
    acoes = [tk for tk in relevantes if A.classe(tk) == "acao"]
    setores = {A.setor(tk) for tk in acoes if A.setor(tk)}
    # "ativos efetivos": quantas posições iguais teriam a mesma concentração (1 / soma dos pesos ao quadrado)
    soma_inv = sum(posicoes.values())
    hhi = sum((w / soma_inv) ** 2 for w in posicoes.values()) if soma_inv > 0 else 0.0
    efetivos = 1 / hhi if hhi > 0 else 0.0

    itens = [
        {"id": "classes", "titulo": "Classes de ativos", "max": 30, "pontos": _pontos_classes(len(classes_presentes)),
         "valor": f"{len(classes_presentes)} de 6", "ok": len(classes_presentes) >= 3,
         "texto": "Ações, FIIs, ETFs, fundos, renda fixa e cripto reagem de formas diferentes. Ter 3 ou mais já ajuda muito."},
        {"id": "concentracao", "titulo": "Peso do maior ativo", "max": 25, "pontos": _pontos_concentracao(maior, bool(posicoes)),
         "valor": f"{maior:.0%}" if de_risco else "—", "ok": bool(posicoes) and maior <= PESO_ALERTA,
         "texto": "Se um único ativo concentra mais de um quarto da carteira, o tombo dele vira o tombo seu. (CDI e Tesouro Selic, a reserva, não contam aqui.)"},
        {"id": "ativos", "titulo": "Quantidade de ativos", "max": 20, "pontos": _pontos_ativos(len(relevantes)),
         "valor": f"{len(relevantes)} (mín. 5)", "ok": len(relevantes) >= 5,
         "texto": "Cinco ou mais ativos com peso relevante (3% ou mais cada) já espalham o risco de empresa."},
        {"id": "setores", "titulo": "Setores das ações", "max": 10, "pontos": _pontos_setores(len(acoes), len(setores)),
         "valor": (f"{len(setores)} setor(es)" if len(acoes) >= 2 else "n/d"), "ok": len(acoes) < 2 or len(setores) >= 3,
         "texto": "Bancos, energia e varejo sofrem por motivos diferentes. Evite deixar todas as ações no mesmo setor."},
        {"id": "reserva", "titulo": "Reserva e proteção", "max": 15, "pontos": _pontos_reserva(grupos["reserva"]),
         "valor": f"{grupos['reserva']:.0%}", "ok": 0.10 <= grupos["reserva"] <= 0.70,
         "texto": "Renda fixa e caixa seguram a carteira nas quedas. Pouco demais deixa tudo exposto; demais deixa o dinheiro parado."},
    ]
    nota = sum(i["pontos"] for i in itens)
    if f["investido"] < MIN_INVESTIDO:
        nota = min(nota, 25)
    nota = int(max(0, min(100, nota)))
    nivel, resumo = _nivel(nota, f["investido"])

    alvo = PERFIS[perfil]["alvo"]
    comparacao = [{"grupo": g, "nome": NOME_GRUPO[g], "atual": grupos[g], "alvo": alvo[g], "dif": grupos[g] - alvo[g], "cor": COR_GRUPO[g]} for g in GRUPOS]

    out = {"pat": f["pat"], "grupos": grupos, "posicoes": posicoes, "caixa": f["caixa"], "investido": f["investido"],
           "nota": nota, "nivel": nivel, "resumo": resumo, "itens": itens, "perfil": perfil, "comparacao": comparacao,
           "maior": (maior_tk, maior), "n_ativos": len(relevantes), "classes": classes_presentes, "setores": sorted(setores),
           "efetivos": efetivos}
    out["dicas"] = dicas(out)
    out["desafio"] = desafio(out)
    return out


def dicas(a: dict) -> list[dict]:
    """Lições práticas e curtas, da mais importante para a menos. Cada uma: {titulo, texto, tom} com tom 'bom', 'atencao' ou 'info'."""
    out: list[dict] = []
    g = a["grupos"]
    if a["investido"] < MIN_INVESTIDO:
        out.append({"titulo": "Comece pela variedade", "tom": "info",
                    "texto": "Em vez de colocar tudo em um ativo, escolha de 5 a 8 ativos de pelo menos 3 classes. Compre aos poucos e veja a nota subir."})
        return out
    tk, w = a["maior"]
    if tk and w > PESO_ALERTA:
        out.append({"titulo": f"{A.rotulo(tk)} pesa {w:.0%}", "tom": "atencao",
                    "texto": "Quando um ativo passa de 25% da carteira, a vida dele manda na sua. Venda uma parte ou compre outros para diluir."})
    if len(a["classes"]) < 3:
        faltam = [x for x in ("reserva", "fii", "etf", "acao", "fundo", "cripto") if x not in a["classes"] and x != "cripto"][:2]
        sug = " e ".join(NOME_GRUPO[x].split(" (")[0].lower() for x in faltam)
        out.append({"titulo": "Poucas classes de ativos", "tom": "atencao",
                    "texto": f"Você tem {len(a['classes'])} classe(s) relevante(s). Que tal estudar {sug}? "
                             + " ".join(f"{NOME_GRUPO[x].split(' (')[0]}: {PORQUE[x]}." for x in faltam)})
    if a["n_ativos"] < 5:
        out.append({"titulo": "Poucos ativos", "tom": "atencao",
                    "texto": f"Você tem {a['n_ativos']} ativo(s) com peso relevante. Com 5 ou mais, o problema de uma empresa pesa menos no total."})
    if g["cripto"] > CRIPTO_ALERTA:
        out.append({"titulo": f"Cripto com {g['cripto']:.0%}", "tom": "atencao",
                    "texto": "Cripto pode cair 50% em poucas semanas. Quem usa costuma manter uma fatia pequena, pensando no que aguenta perder."})
    if a["caixa"] > 0.40:
        out.append({"titulo": f"{a['caixa']:.0%} do dinheiro está parado", "tom": "atencao",
                    "texto": "Caixa sem render perde para a inflação. A renda fixa (CDI ou Tesouro Selic) é o jeito de manter a segurança e ainda render."})
    if g["reserva"] < 0.05 and a["investido"] >= MIN_INVESTIDO:
        out.append({"titulo": "Sem reserva de proteção", "tom": "atencao",
                    "texto": "Sem renda fixa, uma queda geral da bolsa atinge tudo ao mesmo tempo. Uma parte em CDI ou Tesouro Selic funciona como amortecedor."})
    if len([s for s in a["setores"]]) == 1 and any(A.classe(t) == "acao" for t in a["posicoes"]):
        out.append({"titulo": "Todas as ações no mesmo setor", "tom": "atencao",
                    "texto": "Se o setor passar por uma crise, todas caem juntas. Misturar setores (bancos, energia, consumo, saúde) distribui esse risco."})
    if not any(d["tom"] == "atencao" for d in out):
        out.append({"titulo": "Boa distribuição", "tom": "bom",
                    "texto": "Sua carteira tem várias classes, vários ativos e nenhum pesando demais. Agora é manter o equilíbrio ao longo do tempo (rebalancear)."})
    # a maior diferença para o perfil de exemplo
    c = max(a["comparacao"], key=lambda x: abs(x["dif"]))
    if abs(c["dif"]) >= 0.15:
        sinal = "acima" if c["dif"] > 0 else "abaixo"
        out.append({"titulo": f"{c['nome'].split(' (')[0]} {sinal} do exemplo {PERFIS[a['perfil']]['nome'].lower()}", "tom": "info",
                    "texto": f"Você tem {c['atual']:.0%} nesse grupo e o exemplo didático do perfil tem {c['alvo']:.0%}. Não é regra: serve para você enxergar a diferença."})
    return out[:5]


def desafio(a: dict) -> list[dict]:
    """O desafio 'Monte uma carteira diversificada': 6 etapas, cada uma com feito/não feito. Ensina o processo, sem olhar retorno."""
    g, classes = a["grupos"], a["classes"]
    n_acoes = len([t for t in a["posicoes"] if A.classe(t) == "acao" and a["posicoes"][t] >= PESO_RELEVANTE])
    etapas = [
        ("ativos", "Tenha 5 ou mais ativos", a["n_ativos"] >= 5, f"{a['n_ativos']}/5"),
        ("classes", "Use pelo menos 3 classes diferentes", len(classes) >= 3, f"{len(classes)}/3"),
        ("peso", "Nenhum ativo acima de 25%", bool(a["posicoes"]) and a["maior"][1] <= PESO_ALERTA, f"maior: {a['maior'][1]:.0%}" if a["posicoes"] else "—"),
        ("reserva", "Tenha de 10% a 70% em renda fixa ou caixa", 0.10 <= g["reserva"] <= 0.70, f"{g['reserva']:.0%}"),
        ("setores", "Se tiver ações, use 3 setores diferentes", n_acoes < 2 or len(a["setores"]) >= 3, f"{len(a['setores'])} setor(es)" if n_acoes >= 2 else "n/d"),
        ("cripto", "Mantenha a cripto em até 10%", g["cripto"] <= CRIPTO_ALERTA, f"{g['cripto']:.0%}"),
    ]
    investido = a["investido"] >= MIN_INVESTIDO
    return [{"id": i, "titulo": t, "ok": bool(ok and investido), "progresso": p} for i, t, ok, p in etapas]


def concluido(d: list[dict]) -> bool:
    return bool(d) and all(e["ok"] for e in d)


def boa_decisao(estado: dict) -> dict:
    """A régua dos pontos semanais do jogo (jogar.py): 5+ ativos relevantes, 3+ classes e nenhum ativo acima de 25%.
    Olha só o processo de montar a carteira: lucro, retorno e risco medido não entram."""
    a = analisar(estado)
    ok = a["n_ativos"] >= 5 and len(a["classes"]) >= 3 and (not a["posicoes"] or a["maior"][1] <= PESO_ALERTA) and a["investido"] >= MIN_INVESTIDO
    return {"ok": ok, "ativos": a["n_ativos"], "classes": len(a["classes"]), "maior_peso": a["maior"][1], "nota": a["nota"]}
