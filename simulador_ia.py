"""
Passo 18 · Assistente do simulador (integra o Passo 13) e documentação das fórmulas.

Sem Streamlit e sem rede. Toda resposta usa SÓ os números que o simulador calculou (contexto `ctx`); nada é inventado, nenhuma rentabilidade
é prometida e o assistente não recomenda comprar ou vender.

ctx (montado por simulador_app.contexto_ia):
 {"gerado_em", "juros": {"p", "resumo"}, "aposentadoria": {...}, "renda": {...}, "cenarios": {nome: {"p","resumo"}}, "classe": {...},
  "crise": [{"nome","resumo_base","resumo_crise"}], "carteira": {...}, "historico": [...], "metas": [avaliar_meta...]}
"""
from __future__ import annotations

import math
import re

import intel as I
import simulador as S

# ---------------------------------------------------------------- fórmulas documentadas
FORMULAS = [
    ("Taxa efetiva → mensal", "i_m = (1 + i_a)^(1/12) − 1", "Taxas anuais são tratadas como EFETIVAS (juros sobre juros). Equivalência, não divisão por 12."),
    ("Taxa nominal → efetiva", "i_ef = (1 + i_nom/m)^m − 1   e   i_nom = m·((1+i_ef)^(1/m) − 1)", "m = capitalizações por ano (12 = mensal). Use quando a taxa vier como 'a.a. capitalizada mensalmente'."),
    ("Valor futuro com aportes", "VF = PV·(1+i)^n + PMT·[((1+i)^n − 1)/i]·(1+i)^k", "k = 0 se o aporte é no FIM do período, k = 1 se no INÍCIO. Conferido contra a projeção mês a mês."),
    ("Aporte necessário", "PMT = (FV − PV·(1+i)^n) · i / [((1+i)^n − 1)·(1+i)^k]", "Com impostos/custos o app resolve por bissecção sobre a projeção completa; a fórmula fechada vale para conferir o caso simples."),
    ("Taxa líquida de custos", "i_liq = (1 + i_bruta)/(1 + c) − 1", "c = taxa de administração/custódia a.a. cobrada sobre o patrimônio."),
    ("Rentabilidade real (Fisher)", "r = (1 + i_nom)/(1 + π) − 1", "Não é a subtração i − π. Valor real = valor nominal / fator de inflação acumulado (R$ de hoje)."),
    ("Inflação variável", "F_t = Π (1 + π_ano)^(1/12) mês a mês", "Aceita uma inflação por ano; o fator acumula mês a mês."),
    ("Rentabilidade anualizada", "TIR: Σ fluxos/(1+r)^t = 0, depois (1+r_m)^12 − 1", "Considera QUANDO cada aporte entrou (não é lucro/aportado). Resolvida por bissecção."),
    ("Rentabilidade acumulada", "(total líquido + renda recebida)/total investido − 1", "Líquida de custos e impostos."),
    ("Imposto de renda", "Renda fixa: regressivo 22,5% / 20% / 17,5% / 15% (181, 361, 721 dias) + IOF < 30 dias, lote a lote; ações 15%; FIIs 20%; cripto 15%; isentos 0%", "Aplicado sobre o GANHO na saída (liquidação hipotética). Alíquotas editáveis; confira a regra vigente do seu caso."),
    ("Patrimônio para renda", "P = renda_anual / yield", "Com imposto sobre as distribuições: yield líquido = yield · (1 − IR)."),
    ("Patrimônio de aposentadoria", "P = saque · [1 − (1+r)^−n]/r · (1+r)^k", "Valor presente de uma anuidade em termos REAIS (r = retorno real na aposentadoria); n = meses entre a aposentadoria e a idade-limite."),
    ("Saque sustentável", "saque = P · r / [1 − (1+r)^−n]", "Se r = 0: P/n. 'Perpétuo' quando a retirada inicial anual ≤ r real."),
    ("Meta financeira", "alvo_nominal = alvo_hoje·(1+π)^(n/12);  PMT pela fórmula do aporte", "Metas podem ser corrigidas pela inflação até o prazo."),
    ("Monte Carlo", "retorno_mês ~ lognormal(μ, σ), semente fixa 42", "σ = volatilidade da classe (hipótese). Mostra a faixa de resultados e a chance de atingir a meta; não é previsão."),
    ("Risco da carteira simulada", "σ_c = √(Σ wᵢ²σᵢ² + ρ·Σᵢ≠ⱼ wᵢwⱼσᵢσⱼ)", "ρ = correlação média única (hipótese editável). Estimativa de planejamento, não medida de mercado."),
    ("Simulação histórica", "Decisão do dia t usa apenas preços até t−1", "Sem olhar o futuro; média de 200 dias calculada até o dia anterior."),
]

LIMITE = ("Simulações são hipóteses de planejamento com as premissas que você definiu, não previsões nem promessas de rentabilidade. "
          "Nada é comprado ou vendido pelo app.")


def _brl(v) -> str:
    if v is None or (isinstance(v, float) and not math.isfinite(v)):
        return "—"
    s = f"{abs(float(v)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return ("−" if v < 0 else "") + "R$ " + s


def _pct(v, casas=1) -> str:
    return "—" if v is None or not math.isfinite(float(v)) else f"{float(v) * 100:.{casas}f}%".replace(".", ",")


# ---------------------------------------------------------------- premissas otimistas
def identificar_premissas_otimistas(p: dict, classe: str | None = None, cdi: float | None = None, ipca: float | None = None) -> list[dict]:
    """Alertas sobre premissas fortes demais. Limiares são referências de bom senso (documentados na mensagem), não verdades de mercado.
    Cada alerta: {'gravidade': 'alta'|'media', 'tema', 'texto'}."""
    out: list[dict] = []
    infl = p.get("inflacao", 0.045)
    infl_m = float(infl) if S.np.isscalar(infl) else float(sum(infl) / len(infl))
    taxa = p.get("taxa_aa")
    dy = p.get("dy_aa") or 0.0
    if taxa is not None:
        real = S.fisher(taxa, infl_m)
        teto = {"cripto": 0.20, "acao": 0.10, "fii": 0.07, "etf": 0.08, "fundo": 0.07, "renda_fixa": 0.08}.get(classe or "", 0.08)
        if real > teto:
            out.append({"gravidade": "alta", "tema": "Rentabilidade", "texto": f"Retorno de {_pct(taxa)} a.a. equivale a {_pct(real)} acima da inflação ({_pct(infl_m)}). "
                        f"Para esta classe, acima de {_pct(teto, 0)} real por muitos anos é uma premissa forte; teste um cenário mais baixo."})
        if cdi and taxa > cdi * 1.3 and classe in (None, "renda_fixa"):
            out.append({"gravidade": "alta", "tema": "Rentabilidade", "texto": f"A taxa ({_pct(taxa)}) está bem acima do CDI de referência ({_pct(cdi)}); em renda fixa isso exige risco de crédito ou prazo longo."})
    if dy > 0.12:
        out.append({"gravidade": "alta", "tema": "Yield", "texto": f"Yield de {_pct(dy)} ao ano é alto e raramente se sustenta; costuma refletir queda de cotas ou distribuição extraordinária."})
    elif dy > 0.10:
        out.append({"gravidade": "media", "tema": "Yield", "texto": f"Yield de {_pct(dy)} ao ano está no topo do que se vê em FIIs/ações; teste um corte de distribuições."})
    cd = p.get("cresc_dist_aa")
    if dy > 0 and cd is not None and taxa is not None and cd > taxa + 0.02:
        out.append({"gravidade": "media", "tema": "Distribuições", "texto": "As distribuições crescem mais que o preço; isso eleva o yield com o tempo e é uma premissa otimista."})
    if infl_m < 0.03:
        out.append({"gravidade": "media", "tema": "Inflação", "texto": f"Inflação de {_pct(infl_m)} é menor que a meta usual de longo prazo; subestimá-la superestima o poder de compra futuro."})
    if (p.get("custo_aa") or 0) == 0 and classe in ("etf", "fundo"):
        out.append({"gravidade": "media", "tema": "Custos", "texto": "Sem taxa de administração informada; ETFs e fundos cobram taxa que reduz o retorno todo ano."})
    if p.get("ir") == "isento" and classe in ("acao", "cripto", "etf", "fundo", "renda_fixa"):
        out.append({"gravidade": "media", "tema": "Impostos", "texto": "Sem imposto de renda na saída; para esta classe há tributação sobre o ganho em regra geral."})
    meses = p.get("meses") or 0
    if meses >= 360 and taxa is not None and S.fisher(taxa, infl_m) > 0.05:
        out.append({"gravidade": "media", "tema": "Prazo", "texto": f"Mais de 30 anos com {_pct(S.fisher(taxa, infl_m))} real ao ano sem nenhuma crise é um caminho liso demais; veja a aba Crises."})
    ra = p.get("reajuste_aporte")
    if ra is not None and ra != "inflacao" and isinstance(ra, (int, float)) and ra > infl_m + 0.03:
        out.append({"gravidade": "media", "tema": "Aportes", "texto": f"O aporte cresce {_pct(ra)} ao ano, acima da inflação; confirme se sua renda acompanha."})
    return out


# ---------------------------------------------------------------- impacto do aporte
def impacto_aporte(p: dict, variacoes: tuple = (-0.5, -0.25, 0.25, 0.5, 1.0), valores_abs: tuple = ()) -> list[dict]:
    """Recalcula a projeção com o aporte alterado (percentual sobre o atual e/ou valores absolutos). Linhas: aporte, total líquido, real, diferença."""
    base = S.projetar(p, detalhado=False)["resumo"]
    ap0 = float(p.get("aporte") or 0.0)
    casos = [(f"{v:+.0%}".replace("+", "+"), ap0 * (1 + v)) for v in variacoes] + [(f"aporte de {_brl(v)}", float(v)) for v in valores_abs]
    linhas = [{"rotulo": "atual", "aporte": ap0, "total_liquido": base["total_liquido"], "valor_real": base["valor_real"], "dif": 0.0, "dif_real": 0.0, "total_investido": base["total_investido"]}]
    for rot, ap in casos:
        if ap < 0:
            continue
        r = S.projetar({**p, "aporte": ap}, detalhado=False)["resumo"]
        linhas.append({"rotulo": rot, "aporte": ap, "total_liquido": r["total_liquido"], "valor_real": r["valor_real"], "dif": r["total_liquido"] - base["total_liquido"],
                       "dif_real": r["valor_real"] - base["valor_real"], "total_investido": r["total_investido"]})
    return linhas


def sugestoes_alternativas(ctx: dict) -> list[str]:
    """Simulações que valem a pena rodar a seguir, com base no que já foi calculado."""
    s: list[str] = []
    j = ctx.get("juros")
    if j:
        s.append("Rode a mesma projeção nos três cenários (aba Cenários) para ver a faixa de resultados.")
        s.append("Aumente o aporte em 25% e veja a diferença (aba Aportes e metas ou pergunte 'e se eu aportar mais?').")
        if (j["p"].get("inflacao") or 0) < 0.06:
            s.append("Teste inflação mais alta (6% a 8%) para ver o efeito no poder de compra.")
    if ctx.get("aposentadoria"):
        s.append("Teste aposentar 3 a 5 anos mais tarde ou reduzir a renda desejada para ver quando o patrimônio deixa de se esgotar.")
    if ctx.get("carteira"):
        s.append("Compare a carteira atual com uma versão rebalanceada anualmente e com novos aportes.")
    if not ctx.get("crise"):
        s.append("Simule uma queda de 30% logo no início (aba Crises) para ver quanto o prazo da meta se alonga.")
    if not ctx.get("historico"):
        s.append("Rode a estratégia em períodos históricos reais (aba Histórico) e compare com aportes mensais.")
    return s[:5]


# ---------------------------------------------------------------- perguntas
_GATILHO = re.compile(r"simula|juros compostos|aposentad|independencia financeira|minhas? metas?|\bmeta\b|aporte|projecao|projetad|poder de compra|renda passiva|premissa|"
                      r"quanto (eu )?(preciso|falta)|patrimonio (final|futuro|projetado|necessario)|cenario (otimista|moderado|conservador)|inflacao|rentabilidade real|"
                      r"explica(r)? (o )?(resultado|simulacao)|e se eu|quanto tempo (para|ate)|reserva de emergencia")
_COMPRA = re.compile(r"\b(comprar|compro|comprei|vender|vendo|vendi)\b|devo (investir|aplicar)|vale a pena (comprar|investir)|melhor (acao|fii|ativo|investimento)|indica")


def eh_pergunta_simulador(pergunta: str) -> bool:
    return bool(_GATILHO.search(I._norm(pergunta)))


def responder_simulador(pergunta: str, ctx: dict | None) -> dict:
    ctx = ctx or {}
    q = I._norm(pergunta)
    gerado = ctx.get("gerado_em")
    tem = any(ctx.get(k) for k in ("juros", "aposentadoria", "renda", "cenarios", "classe", "crise", "carteira", "historico", "metas"))
    base = {"limite": LIMITE, "referencia": f"Simulação calculada em {gerado[:16].replace('T', ' ')}" if gerado else "Nenhuma simulação carregada",
            "consultado": "Consultei: " + (", ".join(k for k in ("juros", "aposentadoria", "renda", "cenarios", "classe", "crise", "carteira", "historico", "metas") if ctx.get(k)) or "nada (rode uma simulação na página Simulador).")}

    def resp(texto, linhas=None, falta=False):
        return {**base, "texto": texto, "linhas": linhas or [], "sem_dados": falta}
    if not q:
        return resp("Escreva uma pergunta sobre a sua simulação.", falta=True)
    if I._PEDIDO_INDICACAO.search(q) or _COMPRA.search(q):
        return resp("Não indico compra, venda nem qual ativo é melhor. Posso explicar o que a simulação mostra e testar premissas diferentes com você.",
                    ["Pergunte, por exemplo: 'e se eu aportar 25% a mais?' ou 'minhas premissas estão otimistas?'."])
    if not tem:
        return resp("Ainda não há simulação calculada nesta sessão. Abra a página Simulador, preencha as premissas e volte aqui.", falta=True)

    j, ap, ce, cr, ca, hi, me, rp = (ctx.get(k) for k in ("juros", "aposentadoria", "cenarios", "crise", "carteira", "historico", "metas", "renda"))

    # premissas otimistas
    if re.search(r"otimist\w* demais|premissa|realista|exagerad|muito alta", q) and j:
        al = identificar_premissas_otimistas(j["p"], j.get("classe"), ctx.get("cdi"), ctx.get("ipca"))
        if not al:
            return resp("Pelos limiares de referência, nenhuma das premissas da sua última projeção parece exagerada. Isso não garante o resultado: teste também um cenário pior.",
                        ["Limiares: retorno real > 8% a.a. (cripto 20%), yield > 10%, inflação < 3%, sem custos/impostos em classes que os têm."])
        return resp(f"Encontrei {len(al)} premissa(s) que merecem atenção:", [f"[{a['gravidade']}] {a['tema']}: {a['texto']}" for a in al])
    # impacto do aporte
    if re.search(r"e se eu (aportar|investir|guardar)|aportar mais|aumentar (o )?aporte|dobrar (o )?aporte|reduzir (o )?aporte|impacto d[oa]s? aporte", q) and j:
        m = re.search(r"(\d+(?:[.,]\d+)?)\s*%", q)
        var = (float(m.group(1).replace(",", ".")) / 100.0,) if m else (0.25, 0.5, 1.0)
        if m and re.search(r"reduz|menos|diminu", q):
            var = (-var[0],)
        tab = impacto_aporte(j["p"], variacoes=var)
        at = tab[0]
        ls = [f"Aporte atual {_brl(at['aporte'])}: patrimônio líquido {_brl(at['total_liquido'])} (real {_brl(at['valor_real'])})."]
        for t in tab[1:]:
            ls.append(f"Aporte {_brl(t['aporte'])} ({t['rotulo']}): {_brl(t['total_liquido'])}, diferença {_brl(t['dif'])} (real {_brl(t['dif_real'])}); investido {_brl(t['total_investido'])}.")
        return resp("Recalculei a projeção só mudando o aporte, com as demais premissas iguais:", ls)
    # inflação / poder de compra
    if re.search(r"inflacao|poder de compra|valor real|rentabilidade real", q) and j:
        r = j["resumo"]
        return resp(f"Em valores de hoje, o patrimônio projetado de {_brl(r['total_liquido'])} equivale a {_brl(r['valor_real'])} (perda de {_brl(r['total_liquido'] - r['valor_real'])} para a inflação).",
                    [f"Inflação média no período: {_pct(r.get('inflacao_media_aa'), 2)} ao ano.",
                     f"Rentabilidade líquida anualizada nominal: {_pct(r.get('rentabilidade_anualizada'), 2)}; real: {_pct(r.get('rentabilidade_real_anualizada'), 2)} (Fisher, não subtração).",
                     "Valor real = valor nominal ÷ inflação acumulada; mostra o que o dinheiro compraria com os preços de hoje."])
    # aposentadoria
    if re.search(r"aposenta|independencia|esgot|durar|saque|renda mensal possivel", q) and ap:
        ls = [f"Patrimônio necessário: {_brl(ap['necessario_real'])} em valores de hoje ({_brl(ap['necessario_nominal'])} nominais na aposentadoria).",
              f"Patrimônio projetado: {_brl(ap['patrimonio_real'])} em valores de hoje ({_brl(ap['patrimonio_nominal'])} nominais).",
              ("Há lacuna de " + _brl(ap['lacuna_real']) + " em valores de hoje.") if not ap["suficiente"] else "Projeção cobre o patrimônio necessário nas premissas usadas.",
              f"Renda mensal sustentável com o projetado: {_brl(ap['renda_possivel_real'])} (valores de hoje)."]
        if ap.get("aporte_necessario", {}).get("aporte") is not None:
            ls.append(f"Aporte necessário para fechar a lacuna: {_brl(ap['aporte_necessario']['aporte'])} por período.")
        ls.append("O patrimônio dura até a idade-limite." if ap["dura_ate_idade_fim"] else f"Com a renda desejada o patrimônio se esgota aos {ap['idade_esgotamento']:.1f} anos.")
        return resp("Resumo da aposentadoria simulada:", ls)
    # metas
    if re.search(r"\bmetas?\b|reserva|imovel|veiculo|viagem|educacao", q) and me:
        ls = []
        for m_ in me:
            ls.append(f"{m_['nome']}: {_pct(m_['pct'])} atingido ({_brl(m_['acumulado'])} de {_brl(m_['alvo_hoje'])}); faltam {m_['meses_restantes']} meses; "
                      f"aporte necessário {_brl(m_['aporte_necessario'])}/mês vs. planejado {_brl(m_['aporte_planejado'])}; situação: {m_['status']}.")
        return resp(f"Você acompanha {len(me)} meta(s):", ls)
    # cenários
    if re.search(r"cenario|conservador|otimista|moderado|compar", q) and ce:
        ls = [f"{S.NOMES_CENARIO.get(k, k)}: líquido {_brl(v['resumo']['total_liquido'])}, real {_brl(v['resumo']['valor_real'])}, rent. anualizada {_pct(v['resumo']['rentabilidade_anualizada'], 2)}."
              for k, v in ce.items() if v.get("resumo")]
        ordem = sorted((v["resumo"]["total_liquido"], k) for k, v in ce.items() if v.get("resumo"))
        extra = f"A distância entre o pior ({S.NOMES_CENARIO.get(ordem[0][1], ordem[0][1])}) e o melhor ({S.NOMES_CENARIO.get(ordem[-1][1], ordem[-1][1])}) é de {_brl(ordem[-1][0] - ordem[0][0])}." if len(ordem) > 1 else ""
        return resp("Comparação dos cenários (hipóteses, não previsões). " + extra, ls)
    # crise
    if re.search(r"crise|queda|perda|estresse|desvaloriz", q) and cr:
        ls = []
        for c in cr:
            b, k = c.get("resumo_base"), c.get("resumo_crise")
            if b and k:
                ls.append(f"{c['nome']}: patrimônio {_brl(k['total_liquido'])} contra {_brl(b['total_liquido'])} sem crise (diferença {_brl(k['total_liquido'] - b['total_liquido'])}).")
        return resp("Efeito das crises simuladas sobre a projeção:", ls or ["Nenhuma crise com resultado calculado."])
    # carteira
    if re.search(r"carteira|rebalance|alocacao|diversific|concentra", q) and ca:
        r = ca.get("resumo") or {}
        ls = [f"Patrimônio projetado: {_brl(r.get('total_liquido'))} (real {_brl(r.get('valor_real'))}); aportes totais {_brl(r.get('total_investido'))}.",
              f"Rentabilidade anualizada hipotética: {_pct(r.get('rentabilidade_anualizada'), 2)}; volatilidade estimada {_pct(r.get('vol_estimada_final'))} (correlação média {r.get('rho', 0.5):.2f}, hipótese)."]
        if ca.get("comparacao"):
            c = ca["comparacao"]
            ls.append(f"Frente à carteira original: patrimônio {_brl(c.get('dif_patrimonio'))}, volatilidade {_pct(c.get('dif_vol'))} p.p., renda anual {_brl(c.get('dif_renda_anual'))}.")
        return resp("Resumo da simulação da carteira:", ls)
    # histórico
    if re.search(r"historic|passado|periodo|backtest", q) and hi:
        ls = [f"{h['rotulo']}: líquido {_brl(h['valor_liquido'])} sobre {_brl(h['investido'])} investidos; TIR {_pct(h.get('tir_aa'), 2)} a.a.; queda máxima {_pct(h.get('mdd'))}." for h in hi]
        return resp("Estratégias simuladas com preços reais do período (resultado passado, sem olhar o futuro):", ls)
    # renda passiva
    if re.search(r"renda passiva|dividend|yield|distribuic|proventos", q) and rp:
        return resp(f"Renda passiva simulada: {_brl(rp.get('mensal_final'))} por mês no fim do período ({_brl(rp.get('anual_final'))} por ano), "
                    f"contra {_brl(rp.get('mensal_inicial'))} por mês no início.",
                    [f"Yield médio sobre o patrimônio inicial: {_pct(rp.get('yield_inicial'), 2)}.",
                     "Distribuições não são constantes: veja o corte de dividendos para testar uma queda."] + ([f"Patrimônio necessário para a renda desejada: {_brl(rp['patrimonio_necessario'])}."] if rp.get("patrimonio_necessario") else []))
    # sugestões
    if re.search(r"sugir|sugest|que mais|outras? simula|proxim", q):
        return resp("Simulações alternativas que valem testar:", sugestoes_alternativas(ctx))
    # risco
    if re.search(r"risco", q):
        ls = []
        if j and j.get("classe"):
            from simulador import PREMISSAS_CLASSE as PC
            c = PC.get(j["classe"])
            if c:
                ls.append(f"{c['nome']}: {c['riscos']}")
        if j:
            al = identificar_premissas_otimistas(j["p"], j.get("classe"), ctx.get("cdi"), ctx.get("ipca"))
            ls += [f"Premissa: {a['texto']}" for a in al[:3]]
        return resp("Riscos que a simulação não mostra por si só:", ls or ["Rode a simulação por classe para ver os riscos específicos."])
    # explicação geral (padrão)
    if j:
        r = j["resumo"]
        ls = [f"Total investido: {_brl(r['total_investido'])}; patrimônio bruto {_brl(r['patrimonio_bruto'])}; imposto {_brl(r['imposto'])}; líquido {_brl(r['patrimonio_liquido'])}.",
              f"Rendimentos líquidos: {_brl(r['rendimentos_liquidos'])}; rentabilidade acumulada {_pct(r.get('rentabilidade_acumulada'))}; anualizada {_pct(r.get('rentabilidade_anualizada'), 2)}.",
              f"Em valores de hoje: {_brl(r['valor_real'])}. Rentabilidade real anualizada {_pct(r.get('rentabilidade_real_anualizada'), 2)}."]
        al = identificar_premissas_otimistas(j["p"], j.get("classe"), ctx.get("cdi"), ctx.get("ipca"))
        if al:
            ls.append(f"Atenção: {al[0]['texto']}")
        return resp("Explicação da última projeção:", ls)
    return resp("Tenho simulações calculadas, mas não entendi qual delas você quer. Pergunte sobre: aposentadoria, metas, cenários, crises, carteira, histórico, renda passiva ou inflação.")
