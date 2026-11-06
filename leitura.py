"""Leitura de cada tela por modo de experiência (puro, sem Streamlit).

Recebe os números JÁ CALCULADOS pela tela e devolve o texto que explica o resultado:
- Iniciante: para quem nunca investiu. Sem siglas, frases curtas, "o que isso significa" e "o que fazer com isso".
- Intermediário: resumo direto, com os termos do mercado e os números principais.
- Avançado: fórmulas, entradas usadas, limites do método e sensibilidade.
Não calcula nada novo e nunca recomenda compra ou venda.

Retorno: {"titulo", "nivel": "bom"|"ok"|"ruim"|"na", "resumo", "pontos": [...], "rodape"}.
"""
from __future__ import annotations

MODOS = ("iniciante", "intermediario", "avancado")
AVISO = "Isto é uma conta educativa feita com dados públicos. Não é recomendação de compra nem de venda."


def _n(v, casas=2):
    if v is None or v != v:
        return "sem dado"
    return f"{v:,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")


def brl(v):
    return "sem dado" if v is None or v != v else "R$ " + _n(v, 2)


def pct(v, casas=1):
    return "sem dado" if v is None or v != v else _n(v, casas) + "%"


def _m(modo):
    return modo if modo in MODOS else "intermediario"


def _card(titulo, nivel, resumo, pontos, rodape=AVISO):
    return {"titulo": titulo, "nivel": nivel, "resumo": resumo, "pontos": [p for p in pontos if p], "rodape": rodape}


# ------------------------------------------------------------------ preço justo
def preco_justo(nome, preco, graham, bazin, mg, mb, margem_alvo, lpa=None, vpa=None, div_med=None, yield_alvo=None, modo="intermediario"):
    modo = _m(modo)
    ms = [(n, j, m) for n, j, m in (("Graham", graham, mg), ("Bazin", bazin, mb)) if j is not None and m is not None]
    titulo = f"{nome}: o preço está justo?" if modo == "iniciante" else f"{nome}: preço justo"
    if not ms or preco is None:
        txt = {"iniciante": f"Não deu para calcular um preço justo para {nome}. Isso costuma acontecer quando a empresa teve prejuízo ou não paga dividendos (a parte do lucro que é repartida com quem tem ações). Nesse caso, olhe as outras telas.",
               "intermediario": f"Sem preço justo para {nome}: Graham e Bazin não se aplicam (LPA/VPA negativos ou sem dividendos).",
               "avancado": f"Graham e Bazin indisponíveis para {nome}: exigem LPA>0, VPA>0 (Graham) e dividendos médios>0 (Bazin). LPA {_n(lpa)}, VPA {_n(vpa)}, dividendo médio {_n(div_med)}."}[modo]
        return _card(titulo, "na", txt, [])
    media_m = sum(m for _, _, m in ms) / len(ms)
    nivel = "bom" if media_m >= margem_alvo else ("ok" if media_m >= 0 else "ruim")
    if modo == "iniciante":
        veredito = {"bom": f"Pelas nossas contas, a ação está **mais barata do que deveria**: o preço está {pct(media_m, 0)} abaixo do que ela parece valer. Isso é um sinal para você estudar melhor essa empresa, não uma ordem de compra.",
                    "ok": "Pelas nossas contas, o preço está **perto do que a ação parece valer**: nem barata, nem cara.",
                    "ruim": f"Pelas nossas contas, a ação está **mais cara do que deveria**: o preço está {pct(-media_m, 0)} acima do que ela parece valer. Pagar mais que o valor justo deixa você mais exposto a perdas."}[nivel]
        pts = [f"Hoje, uma ação de {nome} custa **{brl(preco)}**."]
        for n, j, m in ms:
            if n == "Graham":
                pts.append(f"Primeira conta (compara com o lucro e o patrimônio da empresa): a ação valeria **{brl(j)}**.")
            else:
                pts.append(f"Segunda conta (compara com os dividendos, a parte do lucro que a empresa reparte com os sócios): a ação valeria **{brl(j)}**.")
        pts.append(f"“Folga de segurança” é a diferença entre o preço de hoje e o valor justo. Quanto maior a folga, mais protegido você fica se a conta estiver um pouco errada. Para o seu perfil, o ideal é pelo menos {pct(margem_alvo, 0)}.")
        return _card(titulo, nivel, veredito, pts)
    if modo == "intermediario":
        partes = " · ".join(f"{n} {brl(j)} (margem {pct(m)})" for n, j, m in ms)
        res = f"{nome} a {brl(preco)}. {partes}. Margem média {pct(media_m)} contra alvo de {pct(margem_alvo, 0)}: " + \
              {"bom": "abaixo do preço justo.", "ok": "perto do preço justo.", "ruim": "acima do preço justo."}[nivel]
        return _card(titulo, nivel, res, ["Margem = (justo − preço) ÷ justo. Quando um método não se aplica, ele fica de fora da média."])
    pts = []
    if graham is not None:
        pts.append(f"Graham = √(22,5 × LPA × VPA) = √(22,5 × {_n(lpa)} × {_n(vpa)}) = {brl(graham)}; margem {pct(mg)}.")
    if bazin is not None:
        pts.append(f"Bazin = dividendo médio 5 anos ÷ yield alvo = {brl(div_med)} ÷ {pct((yield_alvo or 0) * 100 if (yield_alvo or 0) < 1 else yield_alvo)} = {brl(bazin)}; margem {pct(mb)}.")
    pts.append(f"Margem = (justo − preço) ÷ justo, com preço {brl(preco)}; alvo do perfil {pct(margem_alvo, 0)}.")
    pts.append("Limites: Graham ignora crescimento e setor; Bazin depende da regularidade dos proventos; ambos usam dados passados.")
    return _card(titulo, nivel, f"Margem média {pct(media_m)} (alvo {pct(margem_alvo, 0)}).", pts)


# ------------------------------------------------------------------ múltiplos
def multiplos(nome, preco, pl, pvp, dy, roe, margem, div_pl, ev_ebitda=None, modo="intermediario"):
    modo = _m(modo)
    sinais_bons = sum([pl is not None and 0 < pl <= 15, pvp is not None and 0 < pvp <= 1.5, dy is not None and dy >= 5,
                       roe is not None and roe >= 15, margem is not None and margem >= 10, div_pl is not None and div_pl <= 100])
    dados_ok = sum(x is not None for x in (pl, pvp, dy, roe, margem, div_pl))
    nivel = "na" if dados_ok < 3 else ("bom" if sinais_bons >= 4 else ("ok" if sinais_bons >= 2 else "ruim"))
    titulo = f"{nome}: como a empresa se compara" if modo == "iniciante" else f"{nome}: múltiplos"
    if modo == "iniciante":
        pts = []
        if pl is not None and pl > 0:
            pts.append(f"Você paga **{_n(pl, 1)} vezes o lucro anual** por ação. Se o lucro continuasse igual, seriam cerca de {_n(pl, 0)} anos para o lucro cobrir o que você pagou.")
        if pvp is not None and pvp > 0:
            pts.append(f"O preço é **{_n(pvp, 1)} vez(es) o patrimônio** da empresa (o que ela tem menos o que deve)." + (" Abaixo de 1, você paga menos do que ela vale nos livros." if pvp < 1 else ""))
        if dy is not None:
            pts.append(f"Nos últimos 12 meses ela devolveu **{pct(dy)} do preço** em dividendos: a cada R$ 100 aplicados, cerca de R$ {_n(dy, 0)} voltaram para o seu bolso.")
        if roe is not None:
            pts.append(f"Para cada R$ 100 de patrimônio, a empresa gerou **R$ {_n(roe, 0)} de lucro** no ano. Quanto maior, mais eficiente.")
        if margem is not None:
            pts.append(f"De cada R$ 100 que vende, **R$ {_n(margem, 0)} sobram como lucro**.")
        if div_pl is not None:
            pts.append(f"A dívida é de **{pct(div_pl, 0)} do patrimônio**." + (" Dívida alta pede cuidado." if div_pl > 150 else ""))
        res = {"bom": "Vários números estão em faixa saudável. Parece uma empresa sólida, mas confira o setor e as notícias.",
               "ok": "Os números estão mistos: alguns bons, outros fracos. Vale comparar com empresas parecidas.",
               "ruim": "Poucos números estão em faixa saudável. Estude o motivo antes de qualquer decisão.",
               "na": "Faltam dados para avaliar esta empresa com segurança."}[nivel]
        return _card(titulo, nivel, res, pts + ["Compare sempre com empresas do mesmo setor: o que é normal em um setor pode ser ruim em outro."])
    if modo == "intermediario":
        itens = [f"P/L {_n(pl, 1)}", f"P/VP {_n(pvp, 1)}", f"DY {pct(dy)}", f"ROE {pct(roe)}", f"margem líq. {pct(margem)}", f"Dív./PL {pct(div_pl, 0)}"]
        return _card(titulo, nivel, " · ".join(itens), [f"{sinais_bons} de {dados_ok} indicadores em faixa saudável (referências gerais, não substituem a comparação com o setor)."])
    pts = [f"P/L = preço ÷ LPA = {_n(pl, 2)}; P/VP = preço ÷ VPA = {_n(pvp, 2)}; EV/EBITDA {_n(ev_ebitda, 1)}.",
           f"DY = proventos 12m ÷ preço = {pct(dy, 2)}; ROE = lucro ÷ patrimônio = {pct(roe, 2)}; margem líquida {pct(margem, 2)}; Dív./PL {pct(div_pl, 1)}.",
           "Referências usadas: P/L ≤ 15, P/VP ≤ 1,5, DY ≥ 5%, ROE ≥ 15%, margem ≥ 10%, Dív./PL ≤ 100%. Múltiplos dependem da data do balanço e do setor; bancos e empresas cíclicas distorcem P/L e dívida."]
    return _card(titulo, nivel, f"{sinais_bons}/{dados_ok} indicadores dentro das referências.", pts)


# ------------------------------------------------------------------ dividendos
def dividendos(nome, preco, d12, dmed, dy, dy_med, modo="intermediario"):
    modo = _m(modo)
    titulo = f"{nome}: quanto ela paga aos sócios" if modo == "iniciante" else f"{nome}: dividendos"
    if d12 is None and dmed is None:
        return _card(titulo, "na", f"Não encontramos dividendos recentes de {nome}." if modo == "iniciante" else f"Sem proventos para {nome}.", [])
    ref = dy if dy is not None else dy_med
    nivel = "na" if ref is None else ("bom" if 4 <= ref <= 12 else ("ok" if ref > 0 else "ruim"))
    if modo == "iniciante":
        res = (f"Quem tem ações de {nome} recebeu **{brl(d12)} por ação** nos últimos 12 meses, o que equivale a **{pct(dy)} do preço**." if d12 is not None
               else f"Em média, {nome} pagou {brl(dmed)} por ação por ano.")
        pts = ["Dividendo é a parte do lucro que a empresa divide com quem tem ações. Cai na sua conta da corretora.",
               f"Em média nos últimos 5 anos: {brl(dmed)} por ação ao ano ({pct(dy_med)} do preço de hoje).",
               "Cuidado: um rendimento muito alto (acima de uns 12%) pode ser pontual ou sinal de que o preço caiu. Veja se a empresa paga todo ano." if ref is not None and ref > 12 else "Dividendo passado não é garantia de dividendo futuro."]
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"Proventos 12m {brl(d12)} (DY {pct(dy)}) · média 5 anos {brl(dmed)} (DY s/ média {pct(dy_med)}).",
                     ["DY muito alto merece checagem de recorrência e de payout."])
    return _card(titulo, nivel, f"DY 12m = {brl(d12)} ÷ {brl(preco)} = {pct(dy, 2)}; DY s/ média 5a = {brl(dmed)} ÷ {brl(preco)} = {pct(dy_med, 2)}.",
                 ["Anos sem pagamento entram como zero na média; o ano em curso fica de fora.", "Sem payout nem fluxo de caixa aqui: um DY alto não prova sustentabilidade."])


# ------------------------------------------------------------------ DCF
def dcf(nome, preco, valor, margem, potencial, pct_terminal, taxa, g, gp, horizonte, base, modo="intermediario"):
    modo = _m(modo)
    titulo = f"{nome}: quanto ela vale pelo dinheiro que vai gerar" if modo == "iniciante" else f"{nome}: DCF"
    nivel = "na" if margem is None else ("bom" if margem >= 20 else ("ok" if margem >= 0 else "ruim"))
    frágil = pct_terminal is not None and pct_terminal > 75
    if modo == "iniciante":
        res = {"bom": f"Esta conta indica que a ação vale **{brl(valor)}**, mais do que o preço de hoje ({brl(preco)}).",
               "ok": f"Esta conta indica que a ação vale **{brl(valor)}**, perto do preço de hoje ({brl(preco)}).",
               "ruim": f"Esta conta indica que a ação vale **{brl(valor)}**, menos do que o preço de hoje ({brl(preco)}).",
               "na": "Não deu para calcular."}[nivel]
        pts = ["Como funciona: imaginamos quanto dinheiro livre a empresa vai gerar nos próximos anos e trazemos esse total para os valores de hoje (R$ 100 daqui a um ano valem menos que R$ 100 hoje).",
               f"Para isso foram usadas suposições: a empresa cresce {pct(g * 100)} ao ano por {horizonte} anos e, depois, {pct(gp * 100)}. Se o futuro for diferente, o resultado muda.",
               "Cuidado: esta é a conta mais sensível a suposições. Mudar um pouco o crescimento pode mudar muito o valor." + (f" Aqui, {pct(pct_terminal, 0)} do valor vem do futuro distante, o que deixa o resultado ainda mais incerto." if frágil else "")]
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"Valor DCF {brl(valor)} vs. preço {brl(preco)}: margem {pct(margem)}, potencial {pct(potencial)}. Taxa {pct(taxa * 100)}, crescimento {pct(g * 100)}, perpetuidade {pct(gp * 100)}.",
                     [f"Valor terminal = {pct(pct_terminal, 0)} do valor da firma." + (" Resultado muito sensível às premissas de longo prazo." if frágil else "")])
    return _card(titulo, nivel, f"Valor = Σ FCLₜ/(1+r)ᵗ + VT/(1+r)ⁿ, com FCL base {_n((base or 0) / 1e6, 1)} mi, r {pct(taxa * 100)}, g {pct(g * 100)} por {horizonte} anos, g∞ {pct(gp * 100)} → {brl(valor)}.",
                 [f"Margem de segurança {pct(margem)}; potencial {pct(potencial)}; valor terminal {pct(pct_terminal, 1)} do total.",
                  "Veja a tabela de sensibilidade (taxa × perpetuidade) antes de confiar no ponto central."])


# ------------------------------------------------------------------ saúde financeira
def saude(nome, lpa, vpa, roe, margem, div_pl, dy, modo="intermediario"):
    modo = _m(modo)
    titulo = f"{nome}: a empresa está saudável?" if modo == "iniciante" else f"{nome}: saúde financeira"
    pts_ok = sum([lpa is not None and lpa > 0, roe is not None and roe >= 10, margem is not None and margem >= 8, div_pl is not None and div_pl <= 120])
    dados = sum(x is not None for x in (lpa, roe, margem, div_pl))
    nivel = "na" if dados < 2 else ("bom" if pts_ok >= 3 else ("ok" if pts_ok == 2 else "ruim"))
    if modo == "iniciante":
        pts = []
        if lpa is not None:
            pts.append(f"A empresa teve **{'lucro' if lpa > 0 else 'prejuízo'}** de {brl(abs(lpa))} por ação no último ano." + ("" if lpa > 0 else " Prejuízo é sinal de alerta."))
        if roe is not None:
            pts.append(f"Ela transforma o dinheiro dos donos em lucro a uma taxa de **{pct(roe, 0)} ao ano**. Acima de 10% é considerado bom.")
        if margem is not None:
            pts.append(f"Sobram **{pct(margem, 0)}** de lucro sobre tudo que ela vende.")
        if div_pl is not None:
            pts.append(f"A dívida equivale a **{pct(div_pl, 0)} do que a empresa tem de patrimônio**." + (" Está alta: em crises, dívida grande pesa." if div_pl > 120 else " Está em nível confortável."))
        res = {"bom": "A empresa parece financeiramente saudável.", "ok": "A saúde financeira é mediana: há pontos fortes e fracos.",
               "ruim": "Há sinais de fragilidade. Estude melhor antes de qualquer decisão.", "na": "Faltam dados para avaliar."}[nivel]
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"LPA {brl(lpa)} · VPA {brl(vpa)} · ROE {pct(roe)} · margem líq. {pct(margem)} · Dív./PL {pct(div_pl, 0)}.",
                     [f"{pts_ok} de 4 critérios atendidos (lucro positivo, ROE ≥ 10%, margem ≥ 8%, Dív./PL ≤ 120%)."])
    return _card(titulo, nivel, f"LPA {brl(lpa)}, VPA {brl(vpa)}, ROE {pct(roe, 2)}, margem líquida {pct(margem, 2)}, Dív./PL {pct(div_pl, 1)}, DY {pct(dy, 2)}.",
                 ["Critérios: LPA>0, ROE≥10%, margem≥8%, Dív./PL≤120%. Balanço na data do último demonstrativo; bancos e seguradoras têm outra lógica de alavancagem."])


# ------------------------------------------------------------------ tendência (análise técnica)
def tendencia(nome, veredito, placar, alta, baixa, neutros, modo="intermediario"):
    modo = _m(modo)
    titulo = f"{nome}: para onde o preço está indo" if modo == "iniciante" else f"{nome}: tendência"
    if veredito is None:
        return _card(titulo, "na", "Ainda não há histórico suficiente para ler a tendência." if modo == "iniciante" else "Histórico insuficiente para o veredito.", [])
    nivel = {"Alta": "bom", "Lateral": "ok", "Baixa": "ruim"}[veredito]
    if modo == "iniciante":
        res = {"Alta": "O preço vem **subindo** de forma consistente.", "Lateral": "O preço está **andando de lado**, sem direção clara.",
               "Baixa": "O preço vem **caindo** de forma consistente."}[veredito]
        pts = ["Esta leitura olha só o passado do preço no gráfico, como quem observa o caminho de um carro para tentar prever a curva. Pode errar.",
               f"De {alta + baixa + neutros} sinais analisados, {alta} apontam para cima, {baixa} para baixo e {neutros} não mostram direção.",
               "Preço subindo não significa que vai continuar subindo, e o contrário também vale."]
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"Tendência de {veredito.lower()}: {alta} sinais de alta, {baixa} de baixa e {neutros} neutros (placar {placar:+.2f}).".replace(".", ","),
                     ["Médias móveis, IFR e MACD medem o passado; confirmam, não preveem."])
    return _card(titulo, nivel, f"Placar ponderado {placar:+.2f} → {veredito}.".replace(".", ","),
                 [f"{alta} sinais de alta, {baixa} de baixa, {neutros} neutros; cada sinal vota +1/0/−1 vezes o seu peso.", "Sem teste de acerto histórico aqui: use a Análise técnica avançada para validar setups."])


# ------------------------------------------------------------------ economia
def macro(selic, ipca, dolar, desemprego, modo="intermediario"):
    modo = _m(modo)
    real = None if selic is None or ipca is None else ((1 + selic / 100) / (1 + ipca / 100) - 1) * 100
    nivel = "na" if real is None else ("bom" if real >= 4 else ("ok" if real >= 0 else "ruim"))
    titulo = "Como está a economia" if modo == "iniciante" else "Cenário macro"
    if modo == "iniciante":
        pts = []
        if selic is not None:
            pts.append(f"**Juros básicos do país: {pct(selic, 2)} ao ano.** É o que os bancos usam como base. Juros altos deixam a renda fixa mais atraente e o crédito mais caro.")
        if ipca is not None:
            pts.append(f"**Inflação em 12 meses: {pct(ipca, 2)}.** É o quanto os preços subiram. Seu dinheiro parado perde esse valor de compra.")
        if real is not None:
            pts.append(f"**Ganho acima da inflação: {pct(real, 1)} ao ano.** É o que sobra dos juros depois de descontar a alta dos preços." + (" Ganhar acima da inflação é o objetivo mínimo de investir." if real > 0 else ""))
        if dolar is not None:
            pts.append(f"**Dólar: {brl(dolar)}.** Dólar alto encarece produtos importados e ajuda empresas que vendem para o exterior.")
        if desemprego is not None:
            pts.append(f"**Desemprego: {pct(desemprego, 1)}.** Menos desemprego costuma significar mais consumo e lucro das empresas.")
        res = {"bom": "Os juros estão bem acima da inflação: a renda fixa paga bem. Ações precisam compensar esse risco extra.",
               "ok": "Os juros estão um pouco acima da inflação.", "ruim": "A inflação está comendo os juros.", "na": "Sem dados suficientes agora."}[nivel]
        return _card(titulo, nivel, res, pts, rodape="Leitura educativa do cenário; não prevê o mercado.")
    if modo == "intermediario":
        return _card(titulo, nivel, f"Selic {pct(selic, 2)} · IPCA 12m {pct(ipca, 2)} · juro real {pct(real, 1)} · dólar {brl(dolar)} · desemprego {pct(desemprego, 1)}.",
                     ["Juro real alto tende a pressionar o valor das ações e favorecer a renda fixa."], rodape="Séries do Banco Central.")
    return _card(titulo, nivel, f"Juro real ex-post = (1+Selic)/(1+IPCA12m) − 1 = {pct(real, 2)}.",
                 [f"Selic meta {pct(selic, 2)}, IPCA 12m {pct(ipca, 2)}, USD/BRL {_n(dolar, 4)}, desemprego PNAD {pct(desemprego, 1)}.",
                  "Juro real ex-post usa a inflação passada; o ex-ante depende das expectativas (Focus)."], rodape="Séries do Banco Central.")


# ------------------------------------------------------------------ rótulos sem sigla (Iniciante)
ROTULOS_LEIGOS = {
    "P/L": "Preço ÷ lucro", "P/VP": "Preço ÷ patrimônio", "EV/EBITDA": "Valor da empresa ÷ lucro operacional",
    "DY 12m (%)": "Dividendos em 12 meses (% do preço)", "DY s/ média 5a (%)": "Dividendos médios de 5 anos (% do preço)",
    "ROE (%)": "Lucro sobre o patrimônio (%)", "Margem líq. (%)": "Lucro sobre as vendas (%)", "Dív./PL (%)": "Dívida sobre o patrimônio (%)",
    "LPA": "Lucro por ação", "VPA": "Patrimônio por ação", "Proventos 12m": "Dividendos em 12 meses", "Média 5 anos": "Média de 5 anos",
    "Margem Graham (%)": "Folga no 1º método (%)", "Margem Bazin (%)": "Folga no 2º método (%)",
}


def _nome_cheio(c):
    """'P/L' -> 'Preço sobre Lucro (P/L)'; 'ROE (%)' -> 'Retorno sobre o Patrimônio Líquido (ROE) (%)'. Sem termo conhecido: o próprio texto."""
    try:
        import glossario_central as g
        base, un = (c[:-4], " (%)") if str(c).endswith(" (%)") else (c, "")
        e = g.achar(base)
        return g.nome_completo(e["sigla"]) + un if e else c
    except Exception:
        return c


def rotular(colunas, modo):
    """Mapa {nome_original: rótulo} para exibição. Iniciante: nome simples sem sigla. Demais níveis: nome completo com a sigla ao lado."""
    if _m(modo) == "iniciante":
        return {c: ROTULOS_LEIGOS.get(c, c) for c in colunas}
    return {c: _nome_cheio(c) for c in colunas}


# ------------------------------------------------------------------ ranking
_PILAR_LEIGO = {"Valor": "preço em relação ao que a empresa vale", "Qualidade": "lucro e eficiência", "Dividendos": "pagamento de dividendos",
                "Solidez": "baixo endividamento", "Tendência": "movimento recente do preço", "Risco": "estabilidade do preço"}


def ranking(linhas, perfil, modo="intermediario"):
    """linhas: [{'nome', 'nota', 'pilares': {pilar: nota|None}}] já ordenadas da maior para a menor nota."""
    modo = _m(modo)
    ok = [l for l in linhas if l.get("nota") is not None and l["nota"] == l["nota"]]
    titulo = "Quem ficou na frente" if modo == "iniciante" else "Leitura do ranking"
    if not ok:
        return _card(titulo, "na", "Não foi possível calcular as notas agora." if modo == "iniciante" else "Sem notas calculadas.", [])
    top = ok[0]
    nivel = "bom" if top["nota"] >= 70 else ("ok" if top["nota"] >= 50 else "ruim")

    def forte_fraco(l):
        v = {k: x for k, x in l["pilares"].items() if x is not None and x == x}
        return (max(v, key=v.get), min(v, key=v.get)) if len(v) >= 2 else (None, None)
    f, fr = forte_fraco(top)
    if modo == "iniciante":
        res = f"**{top['nome']}** teve a maior nota ({_n(top['nota'], 0)} de 100) entre as empresas escolhidas, para o perfil {perfil.lower()}."
        pts = ["A nota resume vários critérios de uma vez e serve para separar as empresas que merecem mais estudo. Não é indicação de compra.",
               f"O ponto mais forte dela é **{_PILAR_LEIGO.get(f, f)}**; o mais fraco é **{_PILAR_LEIGO.get(fr, fr)}**." if f else "",
               "As notas mudam se você mudar o perfil ou os pesos. Teste os dois e veja se a ordem se mantém: se se mantiver, a conclusão é mais firme."]
        if len(ok) > 1:
            pts.insert(1, f"Em último lugar ficou **{ok[-1]['nome']}**, com {_n(ok[-1]['nota'], 0)}.")
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"1º {top['nome']} ({_n(top['nota'], 0)}) · " + " · ".join(f"{l['nome']} {_n(l['nota'], 0)}" for l in ok[1:4]),
                     [f"Pilar mais forte do líder: {f}; mais fraco: {fr}." if f else "", f"Perfil {perfil}: os pesos e as metas mudam com ele."])
    return _card(titulo, nivel, f"Líder {top['nome']} com {_n(top['nota'], 1)}.",
                 [" · ".join(f"{k} {_n(v, 0)}" for k, v in top["pilares"].items() if v is not None),
                  "Nota = média ponderada dos pilares disponíveis, com pesos reponderados quando faltam dados; cada indicador é normalizado entre piso e teto fixos."])


# ------------------------------------------------------------------ explicação de cada indicador mostrado em cartão (vale para o app inteiro)
import re as _re

# (padrão no rótulo em minúsculas, rótulo para leigos ou None, explicação simples, nota técnica)
DICIONARIO = [
    (r"p/vp", "Preço ÷ patrimônio", "Quanto você paga por cada R$ 1 do patrimônio do fundo ou da empresa. Abaixo de 1, paga menos do que o patrimônio vale.", "P/VP = preço ÷ valor patrimonial por cota/ação."),
    (r"p/l\b", "Preço ÷ lucro", "Quantos anos de lucro seriam necessários para pagar o preço da ação.", "P/L = preço ÷ lucro por ação (12m)."),
    (r"dividend yield|\bdy\b", "Rendimento em dividendos", "Quanto a empresa ou o fundo devolveu em dinheiro, em um ano, comparado ao preço.", "DY = proventos 12m ÷ preço."),
    (r"vol[aá]til|oscil", "Quanto o preço balança", "Mede o tamanho dos sobe e desce. Quanto maior, mais o valor muda de um dia para o outro.", "Desvio-padrão dos retornos diários × √252."),
    (r"pior queda|maior queda|drawdown", "Maior queda já vista", "O quanto o valor despencou, no pior momento, desde o ponto mais alto.", "Drawdown máximo = menor (preço ÷ máximo anterior − 1)."),
    (r"sharpe", "Retorno por unidade de risco", "Mostra se o ganho compensou o balanço do preço. Quanto maior, melhor.", "Sharpe = (retorno − taxa livre de risco) ÷ volatilidade."),
    (r"taxa de administra", "Taxa de administração", "O que o fundo cobra por ano para administrar seu dinheiro. Sai do rendimento, sem você ver a cobrança.", "% a.a. sobre o patrimônio, descontada diariamente da cota."),
    (r"patrim[oô]nio", None, "Tamanho total do dinheiro aplicado. Fundos maiores tendem a ser mais estáveis.", "Patrimônio líquido do fundo na data de referência."),
    (r"liquidez", "Facilidade para vender", "Mostra quanto dinheiro é negociado por dia. Quanto maior, mais fácil comprar e vender sem mexer no preço.", "Volume financeiro médio diário negociado."),
    (r"vac[aâ]ncia", "Imóveis vazios", "Parte dos imóveis sem inquilino. Quanto menor, mais aluguel entrando.", "Área vaga ÷ área total (informada pelo gestor)."),
    (r"nota", "Nota de 0 a 100", "Resume vários critérios em um número. Serve para comparar, não para decidir sozinha.", "Média ponderada dos pilares com dado; pesos reponderados."),
    (r"cobertura", "Quantos critérios entraram", "Quanto da análise tinha dados disponíveis. Cobertura baixa = nota menos confiável.", "Fração dos pilares com dado."),
    (r"margem de seguran", "Folga de segurança", "A diferença entre o preço de hoje e o valor justo calculado. Maior folga protege de erros na conta.", "(justo − preço) ÷ justo."),
    (r"pre[cç]o justo|valor justo", "Valor que a ação parece valer", "Estimativa de quanto a ação deveria custar, segundo o método usado. É uma referência, não um alvo.", "Resultado do método indicado (Graham, Bazin ou DCF)."),
    (r"selic", "Juros básicos do país", "Taxa que serve de base para todos os juros. Quando sobe, a renda fixa rende mais e o crédito fica mais caro.", "Meta definida pelo Copom (% a.a.)."),
    (r"\bcdi\b", "Taxa dos bancos entre si", "Referência de rendimento da renda fixa. Costuma andar junto com a Selic.", "Média das taxas dos depósitos interfinanceiros (% a.a.)."),
    (r"ipca|infla", "Alta dos preços", "Quanto os preços subiram. Seu dinheiro precisa render mais que isso para não perder valor.", "Índice de preços ao consumidor amplo (IBGE)."),
    (r"juro real|rentabilidade real|retorno real", "Ganho acima da inflação", "O que sobra do rendimento depois de descontar a alta dos preços. É o ganho de verdade.", "(1+nominal)/(1+inflação) − 1."),
    (r"imposto|imp\. de renda", "Imposto de Renda", "Parte do ganho que vai para o governo. Quanto mais tempo o dinheiro fica aplicado, menor a alíquota na renda fixa.", "Tabela regressiva: 22,5% até 180 dias, 15% após 720."),
    (r"valor l[ií]quido|resultado l[ií]quido|l[ií]quido", "Quanto sobra no seu bolso", "Valor final depois de descontar impostos e custos.", "Bruto − IR − custódia."),
    (r"valor bruto|bruto", "Valor antes de descontos", "Quanto o dinheiro virou antes de impostos e custos.", "Montante acumulado antes de IR e taxas."),
    (r"total investido|investido", "Quanto você colocou", "A soma do que saiu do seu bolso: valor inicial mais aportes.", "Principal + Σ aportes."),
    (r"\bvar\b|valor em risco", "Perda provável em dias ruins", "Estima a perda que pode acontecer em um dia ruim, não no pior dos casos.", "Quantil histórico dos retornos no nível de confiança escolhido."),
    (r"beta", "Sensibilidade ao mercado", "Se for maior que 1, a carteira costuma balançar mais que o mercado; menor que 1, balança menos.", "Beta = cov(ativo, mercado) ÷ var(mercado)."),
    (r"correla", "Quanto andam juntos", "Perto de 1: sobem e caem juntos, protegem pouco um ao outro. Perto de 0 ou negativo: ajudam a diversificar.", "Coeficiente de Pearson dos retornos."),
    (r"concentra", "Dinheiro em poucos lugares", "Quanto maior, mais seu resultado depende de poucos ativos. Isso aumenta o risco.", "Peso do maior ativo / índice HHI."),
    (r"diversifica", "Dinheiro bem espalhado", "Quanto mais espalhado entre tipos diferentes de ativos, menos um problema isolado pesa.", "Número efetivo de ativos = 1 ÷ Σ peso²."),
    (r"retorno|rentabilidade|ganho", None, "Quanto o investimento rendeu no período, já com o que foi pago de rendimentos.", "Variação percentual do valor da cota/preço com proventos reinvestidos, quando informado."),
    (r"contra a refer|contra o cdi|contra o ibov|vs\.? ", "Contra o comparativo", "Mostra se o investimento rendeu mais ou menos que a referência escolhida. Positivo significa que ganhou dela.", "Diferença em pontos percentuais entre os retornos."),
    (r"aporte", "Depósito mensal", "Dinheiro novo que você coloca todo mês. Aportar com regularidade pesa mais que acertar o momento.", "Fluxo periódico somado ao principal."),
    (r"roe", "Lucro sobre o patrimônio", "Quanto a empresa lucra para cada R$ 100 que os donos têm nela.", "ROE = lucro líquido ÷ patrimônio líquido."),
    (r"d[ií]vida", "Dívida", "Quanto a empresa deve em relação ao que tem. Dívida alta pesa em momentos de crise.", "Dívida líquida ou Dív./PL."),
]
_DIC = [(_re.compile(p), r, s, t) for p, r, s, t in DICIONARIO]


def explicar_rotulo(rotulo: str, modo: str):
    """(rótulo para exibir, linha extra ou '') de um cartão. Intermediário: nada muda."""
    modo = _m(modo)
    if not rotulo:
        return rotulo, ""
    if modo == "intermediario":
        return _nome_cheio(rotulo), ""                     # nome completo com a sigla ao lado, sem texto extra
    baixo = rotulo.lower()
    for rx, leigo, simples, tecnico in _DIC:
        if rx.search(baixo):
            if modo == "iniciante":
                return (leigo or rotulo), simples
            return _nome_cheio(rotulo), tecnico
    return (rotulo if modo == "iniciante" else _nome_cheio(rotulo)), ""


# ------------------------------------------------------------------ simulação de renda fixa (Tesouro / CDB / LCI)
def simulacao_rf(investido, bruto, imposto, liquido, rendimento, taxa_anual_pct, meses, indexador, modo="intermediario"):
    modo = _m(modo)
    anos = meses / 12
    titulo = "O que esta simulação mostra" if modo == "iniciante" else "Leitura da simulação"
    nivel = "na" if not investido else ("bom" if rendimento > 0 else "ruim")
    ganho_pct = (liquido / investido - 1) * 100 if investido else None
    if modo == "iniciante":
        res = (f"Se você colocar {brl(investido)} ao longo de {_n(anos, 1)} ano(s), esse dinheiro viraria cerca de **{brl(liquido)}** já com o imposto descontado, ou seja, um ganho de **{brl(rendimento)}**.")
        pts = [f"Antes dos descontos seria {brl(bruto)}. Foram {brl(imposto)} entre imposto e taxas.",
               f"O rendimento usado foi de {pct(taxa_anual_pct, 2)} ao ano ({ {'CDI': 'ligado à taxa dos bancos', 'Prefixado': 'taxa fixa combinada na compra', 'IPCA+': 'inflação mais uma taxa fixa'}.get(indexador, indexador) }).",
               "Quanto mais tempo o dinheiro fica aplicado, menos imposto você paga sobre o ganho (na renda fixa, até 15% no longo prazo).",
               "É uma conta simplificada: os juros do futuro podem ser diferentes dos usados aqui."]
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"Investido {brl(investido)} → líquido {brl(liquido)} em {meses} meses ({pct(ganho_pct)} sobre o investido). Taxa bruta {pct(taxa_anual_pct, 2)} a.a.",
                     [f"IR + custódia: {brl(imposto)}. Rendimento líquido: {brl(rendimento)}."])
    return _card(titulo, nivel, f"Taxa efetiva {pct(taxa_anual_pct, 3)} a.a. ({indexador}), {meses} meses → bruto {brl(bruto)}, líquido {brl(liquido)}.",
                 [f"Retorno líquido total {pct(ganho_pct, 2)}; IR + custódia {brl(imposto)}.", "Cada aporte tem alíquota própria pelo seu prazo; sem IOF, marcação a mercado ou variação futura de CDI/IPCA."])


# ------------------------------------------------------------------ FII
def fii(nome, cotacao, pvp, dy, liquidez, vacancia, estrategia, riscos_altos, modo="intermediario"):
    modo = _m(modo)
    titulo = f"{nome}: o que este fundo imobiliário é" if modo == "iniciante" else f"{nome}: visão do FII"
    sinais = [pvp is not None and pvp <= 1.05, dy is not None and 6 <= dy <= 15, vacancia is None or vacancia <= 10, bool(liquidez and liquidez >= 1e6), not riscos_altos]
    nivel = "ruim" if riscos_altos else ("bom" if sum(sinais) >= 4 else "ok")
    if cotacao is None and pvp is None and dy is None:
        return _card(titulo, "na", "Sem dados suficientes deste fundo agora.", [])
    tipo = {"tijolo": "imóveis físicos (como galpões e lajes)", "papel": "títulos de dívida ligados a imóveis", "hibrido": "imóveis e títulos"}.get(estrategia, "ativos imobiliários")
    if modo == "iniciante":
        res = f"Um fundo imobiliário reúne o dinheiro de muitas pessoas para investir em {tipo}. Você compra uma pequena parte, chamada cota, e recebe uma fatia dos rendimentos todo mês."
        pts = [f"A cota custa **{brl(cotacao)}**." if cotacao else "",
               f"Ela rende **{pct(dy, 1)} ao ano** em distribuições, comparado ao preço." if dy is not None else "",
               f"Você paga **{_n(pvp, 2)} vez(es)** o valor do patrimônio do fundo." + (" Abaixo de 1 pode indicar desconto." if pvp is not None and pvp < 1 else "") if pvp is not None else "",
               f"Cerca de **{pct(vacancia, 0)} dos imóveis estão vazios**." if vacancia is not None else "",
               "**Pontos de atenção graves encontrados.** Veja a aba Riscos antes de qualquer decisão." if riscos_altos else "",
               "Rendimento passado não garante o futuro, e a cota pode cair."]
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"Cota {brl(cotacao)} · P/VP {_n(pvp, 2)} · DY {pct(dy, 1)} · vacância {pct(vacancia, 1)} · liquidez {brl(liquidez)}/dia.",
                     [f"{sum(sinais)} de 5 critérios gerais atendidos.", "Riscos altos: " + ", ".join(riscos_altos) if riscos_altos else ""])
    return _card(titulo, nivel, f"P/VP {_n(pvp, 3)}, DY {pct(dy, 2)}, vacância {pct(vacancia, 2)}, liquidez {brl(liquidez)}/dia ({estrategia or 'n/c'}).",
                 ["Referências: P/VP ≤ 1,05, DY entre 6% e 15%, vacância ≤ 10%, liquidez ≥ R$ 1 mi/dia, sem riscos altos.",
                  "Para papel, vacância não se aplica; qualidade de crédito e indexador pesam mais.", "Riscos altos: " + ", ".join(riscos_altos) if riscos_altos else ""])


# ------------------------------------------------------------------ renda fixa (título)
def renda_fixa(nome, emissor, taxa_txt, vencimento_txt, nota, real_aa, credito, liquidez_dias, modo="intermediario"):
    """Leitura em palavras de um título de renda fixa, no nível do usuário. real_aa em fração (0,04 = 4% ao ano acima da inflação)."""
    modo = _m(modo)
    sinais = [nota is not None and nota >= 70, real_aa is not None and real_aa >= 0.02, credito is not None and credito <= 2,
              liquidez_dias is not None and liquidez_dias <= 30]
    conhecidos = sum(1 for x in (nota, real_aa, credito, liquidez_dias) if x is not None)
    if conhecidos == 0:
        return _card(f"{nome}: o que é este título", "na", "Sem dados suficientes deste título agora.", [])
    nivel = "ruim" if (credito is not None and credito >= 4) or (real_aa is not None and real_aa < 0) else ("bom" if sum(sinais) >= 3 else "ok")
    liq = ("a qualquer momento" if liquidez_dias is not None and liquidez_dias <= 1 else f"em cerca de {liquidez_dias} dia(s)" if liquidez_dias is not None else None)
    if modo == "iniciante":
        titulo = f"{nome}: o que é este título"
        res = (f"Na renda fixa você empresta dinheiro para {emissor or 'o emissor'} e recebe de volta com juros. "
               + ("O ganho esperado fica acima da inflação." if real_aa is not None and real_aa >= 0.02 else
                  "O ganho esperado fica pouco acima da inflação." if real_aa is not None and real_aa >= 0 else
                  "O ganho esperado fica abaixo da inflação: o dinheiro rende, mas perde poder de compra." if real_aa is not None else ""))
        pts = [f"Taxa: **{taxa_txt}**, com vencimento em **{vencimento_txt}**." if taxa_txt else "",
               f"Se precisar do dinheiro, dá para resgatar **{liq}**." if liq else "",
               "O risco de o emissor não pagar é **baixo**." if credito is not None and credito <= 2 else
               "O risco de o emissor não pagar é **médio**." if credito == 3 else
               "O risco de o emissor não pagar é **alto**: leia a aba Riscos antes de decidir." if credito is not None else "",
               "A taxa contratada só é garantida até o vencimento e depende de o emissor pagar."]
        return _card(titulo, nivel, res, pts)
    titulo = f"{nome}: visão do título"
    if modo == "intermediario":
        return _card(titulo, nivel, f"{taxa_txt} · vence {vencimento_txt} · nota {_n(nota, 0)}/100 · juro real {pct(real_aa * 100 if real_aa is not None else None, 1)} a.a. · crédito {credito}/5.",
                     [f"{sum(sinais)} de 4 critérios gerais atendidos.", "Liquidez: " + liq if liq else ""])
    return _card(titulo, nivel, f"Taxa {taxa_txt}; vencimento {vencimento_txt}; nota {_n(nota, 1)}; juro real esperado {pct(real_aa * 100 if real_aa is not None else None, 2)} a.a.; risco de crédito {credito}/5; liquidez {liquidez_dias} dia(s).",
                 ["Referências: nota ≥ 70, juro real ≥ 2% a.a., crédito ≤ 2/5, liquidez ≤ 30 dias.", "Retorno esperado depende das premissas de CDI e IPCA do cenário escolhido."])


# ------------------------------------------------------------------ criptoativo
def cripto(nome, preco_txt, mcap_txt, fdv_txt, nota, risco_geral, modo="intermediario"):
    """Textos já formatados pela tela (moeda e escala variam). nota: 0-100 ou None. risco_geral: 'baixo'|'medio'|'alto'|None."""
    modo = _m(modo)
    titulo = f"{nome}: o que você precisa saber" if modo == "iniciante" else f"{nome}: visão geral"
    nivel = {"alto": "ruim", "medio": "ok", "baixo": "bom"}.get(risco_geral) if risco_geral else ("na" if nota is None else ("bom" if nota >= 70 else "ok" if nota >= 50 else "ruim"))
    if modo == "iniciante":
        res = f"{nome} é um ativo digital. Hoje custa **{preco_txt}** e o valor total de tudo o que existe dele é **{mcap_txt}**."
        pts = ["Criptomoedas costumam oscilar muito mais que ações: o preço pode cair ou subir dezenas de por cento em poucos dias.",
               f"Nota de 0 a 100 que o app dá aos fundamentos do projeto: **{nota:.0f}**." if nota is not None else "",
               f"Risco geral encontrado: **{ {'baixo': 'baixo', 'medio': 'médio', 'alto': 'alto'}.get(risco_geral, 'não avaliado') }**." if risco_geral else "",
               "Só invista o que você aceitaria ver cair muito, e estude antes." ]
        return _card(titulo, nivel or "na", res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel or "na", f"Preço {preco_txt} · valor de mercado {mcap_txt} · FDV {fdv_txt}" + (f" · nota {nota:.0f}/100" if nota is not None else "") + ".",
                     ["FDV bem acima do valor de mercado sugere muita oferta ainda a liberar (diluição)."])
    return _card(titulo, nivel or "na", f"Preço {preco_txt}; market cap {mcap_txt}; FDV {fdv_txt}" + (f"; nota fundamentalista {nota:.0f}/100 (7 pilares)." if nota is not None else "."),
                 ["Razão mcap/FDV indica o quanto da oferta máxima já circula. Fontes: CoinGecko, DefiLlama e on-chain; sem dado, sem nota."])


# ------------------------------------------------------------------ carteira
def carteira(investido, valor, res, res_pct, n_pos, melhor=None, pior=None, maior=None, ficticia=False, modo="intermediario"):
    """melhor/pior: (nome, %) · maior: (nome, % da carteira) · valores em R$."""
    modo = _m(modo)
    titulo = "Como está o seu dinheiro" if modo == "iniciante" else "Leitura da carteira"
    nivel = "na" if res_pct is None else ("bom" if res_pct > 0 else ("ok" if res_pct > -3 else "ruim"))
    conc = maior is not None and maior[1] is not None and maior[1] >= 40 and n_pos > 1
    if modo == "iniciante":
        quem = "Na carteira de treino (de mentirinha)" if ficticia else "Na sua carteira"
        if res_pct is None:
            res_t = "Ainda não dá para dizer se você está ganhando ou perdendo, porque faltam preços atuais de algum ativo."
        elif res_pct >= 0:
            res_t = f"{quem}, você colocou **{brl(investido)}** e hoje esse dinheiro vale **{brl(valor)}**. Isso é um ganho de **{brl(res)}** ({pct(res_pct)})."
        else:
            res_t = f"{quem}, você colocou **{brl(investido)}** e hoje esse dinheiro vale **{brl(valor)}**. Isso é uma perda de **{brl(-res)}** ({pct(-res_pct)}) por enquanto."
        pts = ["Perda ou ganho só se realiza quando você vende. Enquanto isso, o valor muda todo dia com o mercado.",
               f"O melhor desempenho é de **{melhor[0]}** ({pct(melhor[1])}) e o pior é de **{pior[0]}** ({pct(pior[1])})." if melhor and pior else "",
               (f"Atenção: **{maior[0]}** representa **{pct(maior[1], 0)}** de tudo o que você tem. Quando muito dinheiro está em um só lugar, um problema nele pesa muito no total. Espalhar entre vários ativos reduz esse risco.") if conc else
               (f"Seu maior investimento é **{maior[0]}**, com {pct(maior[1], 0)} do total. Está bem espalhado." if maior and n_pos > 1 else ""),
               "Esta conta usa os preços de fechamento e não desconta impostos nem taxas."]
        return _card(titulo, nivel, res_t, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"Investido {brl(investido)} → valor {brl(valor)}: resultado {brl(res)} ({pct(res_pct)}) em {n_pos} posições.",
                     [f"Melhor {melhor[0]} ({pct(melhor[1])}), pior {pior[0]} ({pct(pior[1])})." if melhor and pior else "",
                      f"Maior peso: {maior[0]} com {pct(maior[1], 0)}." + (" Concentração elevada." if conc else "") if maior else ""])
    return _card(titulo, nivel, f"Resultado = valor atual − custo = {brl(valor)} − {brl(investido)} = {brl(res)} ({pct(res_pct, 2)}).",
                 [f"Posições: {n_pos}. Melhor {melhor[0]} {pct(melhor[1], 2)}; pior {pior[0]} {pct(pior[1], 2)}." if melhor and pior else "",
                  f"Peso máximo {maior[0]}: {pct(maior[1], 1)} (limite de atenção 40%)." if maior else "",
                  "Custo em R$: ativos em US$ usam o dólar da data da compra; valor atual usa o dólar de hoje. Sem dividendos, impostos ou custos."])


# ------------------------------------------------------------------ evolução e crescimento
def crescimento(nome, cagr_preco, cagr_retorno, anos, modo="intermediario"):
    """CAGRs em % ao ano (None se indisponível) para `anos` anos."""
    modo = _m(modo)
    titulo = f"{nome}: quanto cresceu" if modo == "iniciante" else f"{nome}: crescimento"
    base = cagr_retorno if cagr_retorno is not None else cagr_preco
    nivel = "na" if base is None else ("bom" if base >= 10 else ("ok" if base >= 0 else "ruim"))
    if base is None:
        return _card(titulo, "na", "Ainda não há histórico suficiente para calcular o crescimento." if modo == "iniciante" else "Histórico insuficiente para o CAGR.", [])
    if modo == "iniciante":
        v = (1 + base / 100) ** anos
        res = (f"Quem investiu {anos} anos atrás e deixou o dinheiro parado teria hoje cerca de **R$ {_n(100 * v, 0)} para cada R$ 100** investidos."
               if base > -100 else "O investimento perdeu praticamente todo o valor no período.")
        pts = [f"Isso dá, em média, **{pct(base, 1)} por ano**, contando os dividendos que a empresa pagou." if cagr_retorno is not None else f"Isso dá, em média, **{pct(base, 1)} por ano** só pela mudança do preço.",
               f"Só pela mudança do preço, a média foi de {pct(cagr_preco, 1)} ao ano. A diferença vem dos dividendos." if cagr_preco is not None and cagr_retorno is not None else "",
               "Resultado do passado não garante o futuro. Compare com a inflação e com a renda fixa para saber se valeu a pena."]
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"CAGR {anos}a: preço {pct(cagr_preco, 1)} · retorno total {pct(cagr_retorno, 1)}.",
                     ["A diferença entre retorno total e preço é a contribuição dos proventos."])
    return _card(titulo, nivel, f"CAGR = (valor final ÷ valor inicial)^(1/{anos}) − 1: preço {pct(cagr_preco, 2)} a.a.; retorno total {pct(cagr_retorno, 2)} a.a.",
                 ["Pontas do período influenciam muito o CAGR; confira o gráfico acumulado. Retorno total reinveste proventos."])


# ------------------------------------------------------------------ fundo / ETF (visão geral)
def fundo(nome, tipo, ret12, dif_ref_pp, ref_nome, vol, dd, taxa_adm, nota, modo="intermediario", anos_ref=None):
    """ret12, vol, dd em fração (0,12 = 12%); dif_ref_pp em pontos percentuais; taxa_adm em % a.a.; nota 0-100."""
    modo = _m(modo)
    rot = ("fundo de índice" if modo == "iniciante" else "ETF") if tipo == "etf" else "fundo"
    titulo = f"Este {rot}: vale a pena olhar?" if modo == "iniciante" else f"{nome}: visão do {rot}"
    pos = ret12 is not None and ret12 > 0
    bate = dif_ref_pp is not None and dif_ref_pp >= 0.5
    caro = taxa_adm is not None and taxa_adm >= 2
    nivel = "na" if ret12 is None and nota is None else ("bom" if (bate and not caro) else ("ruim" if (ret12 is not None and ret12 < 0 and dif_ref_pp is not None and dif_ref_pp < 0) else "ok"))
    P = lambda v, c=1: pct(None if v is None else v * 100, c)
    if modo == "iniciante":
        if ref_nome and "CDI" in str(ref_nome).upper():
            ref_nome = "o rendimento da renda fixa"
        explic = "Um fundo de índice copia uma lista de empresas, como o Ibovespa, e é comprado na bolsa como se fosse uma ação." if tipo == "etf" else "Um fundo junta o dinheiro de muita gente, e um gestor decide onde investir."
        pts = [explic,
               f"Nos últimos 12 meses ele {'rendeu' if pos else 'perdeu'} **{P(abs(ret12))}**." if ret12 is not None else "",
               (f"Olhando {anos_ref or 'o período'} {'ano(s)' if anos_ref else ''} e comparando com {ref_nome}, ficou **{_n(abs(dif_ref_pp), 1)} pontos {'acima' if dif_ref_pp >= 0 else 'abaixo'}**. " + ("Rendeu mais do que a referência." if dif_ref_pp >= 0 else "Rendeu menos do que a referência.")) if dif_ref_pp is not None and ref_nome else "",
               f"O maior tombo já registrado foi de **{P(abs(dd), 0)}**. Isso mostra o quanto o valor pode cair em fase ruim." if dd is not None else "",
               f"Ele cobra **{pct(taxa_adm, 2)} ao ano** de taxa de administração. {'Isso é alto: taxa grande come parte do seu ganho.' if caro else 'Taxas menores deixam mais rendimento para você.'}" if taxa_adm is not None else "",
               f"Nota do app: **{nota:.0f} de 100**. Serve para comparar, não para decidir sozinha." if nota is not None else ""]
        res = ("Os números estão bons, mas confira o risco antes." if nivel == "bom" else "Os números não são ruins, mas há pontos de atenção." if nivel == "ok" else "Os números estão fracos agora. Estude o motivo antes de qualquer decisão.") if nivel != "na" else "Faltam dados para avaliar este investimento."
        return _card(titulo, nivel, res, pts)
    if modo == "intermediario":
        return _card(titulo, nivel, f"Retorno 12m {P(ret12)} · vs {ref_nome or 'referência'}: {pct(dif_ref_pp)} p.p. · volatilidade {P(vol)} · pior queda {P(dd)} · taxa adm. {pct(taxa_adm, 2)}.",
                     [f"Nota educacional {nota:.0f}/100." if nota is not None else ""])
    return _card(titulo, nivel, f"Retorno 12m {P(ret12, 2)}; excesso vs {ref_nome or 'ref.'} {pct(dif_ref_pp, 2)} p.p.; vol. anual {P(vol, 2)}; máx. drawdown {P(dd, 2)}; taxa adm. {pct(taxa_adm, 2)} a.a.",
                 [f"Nota {nota:.0f}/100 (pilares com dado; cobertura varia)." if nota is not None else "", "Janela de 12 meses é curta: confira 3 e 5 anos, custos e consistência na aba Rentabilidade."])


# ------------------------------------------------------------------ cripto: abas de detalhe
def cripto_aba(aba, nome, modo="intermediario", **k):
    """aba: 'mercado' (mcap, vol24) · 'fundamentos' (tem_objetivo, tem_tecnologia, inicio) ·
    'onchain' (n_lidos, n_estimados) · 'valuation' (familia, n_indicadores, n_nao)."""
    modo = _m(modo)
    if aba == "mercado":
        mc, v = k.get("mcap"), k.get("vol24")
        giro = (v / mc * 100) if mc and v and mc > 0 else None
        nivel = "na" if giro is None else ("bom" if giro >= 3 else ("ok" if giro >= 0.5 else "ruim"))
        if modo == "iniciante":
            r = ("Ainda não há dados de negociação suficientes." if giro is None else
                 f"Por dia, cerca de **{_n(giro, 1)}%** de tudo o que existe de {nome} muda de mãos.")
            return _card(f"{nome}: quanto se negocia", nivel, r, [
                "Quanto mais gente comprando e vendendo, mais fácil é sair do investimento quando quiser, sem derrubar o preço.",
                "Valor muito baixo indica pouca procura: pode ser difícil vender na hora certa." if giro is not None else ""])
        if modo == "intermediario":
            return _card(f"{nome}: liquidez", nivel, "Sem dados de volume." if giro is None else f"Giro diário (volume ÷ valor de mercado): {_n(giro, 2)}%.",
                         ["Giro baixo sugere pouca liquidez; picos podem indicar movimento atípico."])
        return _card(f"{nome}: liquidez", nivel, "Sem dados." if giro is None else f"Giro = volume 24h ÷ market cap = {_n(giro, 3)}%.",
                     ["Não mede profundidade do livro de ofertas nem slippage; volume reportado por agregadores pode incluir negociações artificiais."])
    if aba == "fundamentos":
        ok = bool(k.get("tem_objetivo")) + bool(k.get("tem_tecnologia"))
        nivel = "bom" if ok == 2 else ("ok" if ok == 1 else "na")
        if modo == "iniciante":
            return _card(f"{nome}: para que serve", nivel, "Aqui você vê o que o projeto promete resolver, como ele funciona e desde quando existe.",
                         ["Antes de investir, consiga explicar com suas palavras para que serve. Se não conseguir, vale estudar mais.",
                          f"Existe desde {k['inicio']}. Projetos mais antigos têm mais histórico para você avaliar." if k.get("inicio") else ""])
        if modo == "intermediario":
            return _card(f"{nome}: fundamentos", nivel, "Objetivo, tecnologia, início e ecossistema do projeto.", ["Descrições vêm do próprio projeto: confronte com outras fontes."])
        return _card(f"{nome}: fundamentos", nivel, "Campos: objetivo, tecnologia, gênese, categoria e ecossistema; atividade de desenvolvimento quando há repositório.",
                     ["Texto de objetivo é autodeclarado (CoinGecko). Sem fonte, o campo aparece como 'sem fonte' em vez de estimativa."])
    if aba == "onchain":
        a, b = k.get("n_lidos", 0), k.get("n_estimados", 0)
        nivel = "bom" if a else ("ok" if b else "na")
        if modo == "iniciante":
            return _card(f"{nome}: uso real da rede", nivel, "Aqui o app mostra números que indicam se a rede está sendo usada de verdade." if (a or b) else "Não há números de uso da rede disponíveis para este ativo.",
                         [f"{a} número(s) lidos direto da rede e {b} estimativa(s) feitas por outros sites." if (a or b) else "",
                          "Rede muito usada costuma ser sinal de interesse real, mas não garante que o preço vai subir."])
        if modo == "intermediario":
            return _card(f"{nome}: on-chain", nivel, f"{a} indicador(es) lido(s) da blockchain e {b} estimativa(s) de provedores.", ["Dado lido da rede é mais confiável que estimativa de provedor."])
        return _card(f"{nome}: on-chain", nivel, f"Registrados: {a}; estimados: {b}.",
                     ["TVL e taxas vêm do DefiLlama (contratos monitorados), não da leitura direta da rede; cobertura direta: Bitcoin, Solana e Blockchair."])
    if aba == "valuation":
        n, nn = k.get("n_indicadores", 0), k.get("n_nao", 0)
        nivel = "ok" if n else "na"
        if modo == "iniciante":
            return _card(f"{nome}: está caro ou barato?", nivel, "O app compara o valor do projeto com o quanto ele realmente movimenta e arrecada." if n else "Faltam dados para comparar o valor deste projeto.",
                         ["Não existe preço justo exato para criptomoeda: estas comparações são só um ponto de partida.",
                          f"{nn} comparação(ões) não puderam ser feitas por falta de dado ou porque não se aplicam." if nn else ""])
        if modo == "intermediario":
            return _card(f"{nome}: valuation", nivel, f"{n} múltiplo(s) calculado(s) · família: {k.get('familia', 'n/d')}.", ["Compare com pares da mesma categoria; mediana só com 3 ou mais."])
        return _card(f"{nome}: valuation", nivel, f"{n} razão(ões) (ex.: mcap/TVL, mcap/receita anualizada); família: {k.get('familia', 'n/d')}; {nn} não aplicável(is).",
                     ["Múltiplos dependem da definição de receita do provedor; amostra pequena de pares distorce a mediana."])
    return _card(nome, "na", "Sem leitura para esta aba.", [])


# ------------------------------------------------------------------ cripto: resumo executivo por regras
_CRIPTO_LEIGO = (
    ("hashrate", "Muitos computadores protegem a rede e esse número está crescendo"),
    ("mineração", "Muitos computadores protegem a rede e esse número está crescendo"),
    ("inflação", "A quantidade de moedas novas criadas por ano é pequena, o que ajuda a manter o valor"),
    ("escassez", "Já existe uma grande parte de todas as moedas que poderão existir, e o total é limitado"),
    ("tempo em operação", "O projeto existe há bastante tempo e já passou por várias crises"),
    ("custo de atacar", "Seria muito caro tentar enganar ou derrubar a rede"),
    ("endereços", "O número de carteiras ativas usando a rede não está crescendo"),
    ("segurança paga pelos usuários", "As taxas pagas pelos usuários ainda cobrem pouco do custo de manter a rede segura"),
    ("tvl", "Pouco dinheiro está guardado dentro dos serviços ligados a esta moeda"),
    ("receita", "O projeto arrecada pouco com o uso da rede"),
    ("volatilidade", "O preço de criptomoedas oscila muito e pode cair forte em poucos dias, além de regras do governo poderem mudar"),
    ("cobertura de dados", "Há poucos dados disponíveis, então a nota pode estar imprecisa"),
)


def cripto_item_leigo(texto):
    """Troca um item técnico do resumo por frase simples (Iniciante). Sem correspondência: tira só o nome do pilar entre parênteses."""
    t = str(texto)
    for chave, frase in _CRIPTO_LEIGO:
        if chave in t.lower():
            return frase
    import re
    return re.sub(r"\s*\([^)]*\)\s*$", "", t).strip() or t


def cripto_resumo_modo(modo, ver, nota, fortes, aten):
    """Devolve (resumo, fortes, aten, conclusao) em texto conforme o modo; Intermediário não muda."""
    modo = _m(modo)
    n = "sem nota por falta de dados" if nota is None else f"nota {nota:.0f}/100"
    if modo == "iniciante":
        fr = {"BOM": "no geral, os sinais são bons", "RUIM": "no geral, os sinais são fracos", "NEUTRO": "no geral, os sinais são mistos"}[ver]
        res = f"Resumo: {fr} ({'sem nota por falta de dados' if nota is None else f'nota {nota:.0f} de 100'}). Isto avalia a qualidade do projeto, não diz que o preço vai subir."
        f2 = list(dict.fromkeys(cripto_item_leigo(x) for x in fortes)) or ["Nenhum ponto forte se destacou."]
        a2 = list(dict.fromkeys(cripto_item_leigo(x) for x in aten)) or ["Sem alertas."]
        return res, f2, a2, f"A nota é uma leitura automática do app. Use como ponto de partida e estude o projeto antes de colocar dinheiro nele."
    if modo == "avancado":
        return (f"Quadro geral **{ver}** ({n}; média ponderada de 7 pilares, só os com dado).", fortes, aten,
                f"Leitura por regras (≥65 BOM, <40 RUIM); nota provisória se a cobertura for baixa. Confira pilares e fontes.")
    return None
