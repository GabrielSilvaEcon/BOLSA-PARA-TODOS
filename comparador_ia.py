"""
Passo 20 · IA do comparador universal (sem Streamlit e sem rede).

Explica a comparação usando SÓ os números que o comparador já calculou (contexto `ctx`). Nada é inventado: o que falta aparece como dado
ausente. Cada linha traz uma etiqueta que separa:
  ✔ Dado       valor vindo de uma fonte ou conta direta
  ≈ Estimativa cálculo sobre o passado (volatilidade, VaR, retorno anualizado...)
  💬 Opinião   leitura educativa do app, sempre com a justificativa ao lado. Não é recomendação nem promessa de retorno.

ctx = {"gerado_em", "periodo": {"ini","fim","moeda","modo"}, "ativos": [{"chave","nome","classe","classe_nome","nota","faixa","provisoria","fonte","data_ref",
       "vantagens":[...],"desvantagens":[...],"ausentes":[...], "nota_hist"}], "retornos": {chave: {"Período escolhido","Anualizado (a.a.)","Retorno real"}},
       "bench": {nome: retorno}, "risco": {chave: {"vol_anual","mdd","sharpe","var95","n_dias"}}, "correlacao": [(a, b, c)], "alertas": [...], "fontes": [...]}
"""
from __future__ import annotations

import re

import comparador_desempenho as D
import intel as I
import relatorios as R

LIMITE = ("Os números vêm dos dados coletados na data indicada e descrevem o passado. Rentabilidade passada não garante rentabilidade futura. "
          "A pontuação é educacional e cada classe usa a sua própria régua. Isto não é recomendação de compra ou venda.")
_GATILHO = re.compile(r"compar\w+ (entre|os|as|esses|estes|ativos|investimentos)|diferenc\w+ entre|qual .{0,20}(mais|menos) (arrisc|volatil|oscil)|"
                      r"ponto[s]? (forte|fraco)|resumo comparativ|perfil de investidor|(quem|qual perfil) .{0,25}(entende|compreend|combina)|"
                      r"dados? (ausente|faltando|indisponiv)\w* .{0,25}compar|o que (falta|esta faltando) .{0,20}compar", re.I)
_PERFIL = {
    "acao": "quem aceita o risco de uma empresa específica (resultado, setor, gestão) e pensa em prazos longos",
    "etf": "quem quer exposição a um índice inteiro, com custo baixo e sem escolher empresas",
    "fii": "quem busca renda periódica de aluguéis ou recebíveis e aceita que o preço da cota oscile",
    "cripto": "quem tolera oscilações muito fortes, entende custódia e regulação e usa uma fatia pequena do patrimônio",
    "fundo": "quem prefere delegar a gestão e aceita taxas e regras de resgate do fundo",
    "renda_fixa": "quem valoriza previsibilidade, conhece prazo e emissor e aceita a liquidez do título",
}


def eh_pergunta_comparacao(pergunta: str) -> bool:
    return bool(_GATILHO.search(I._norm(pergunta)))


def _p(v, c=1, s=False):
    return R.pct(v, c, s)


def _num(v, c=2):
    return "n/d" if not R._ok(v) else f"{float(v):.{c}f}".replace(".", ",")


def _ativo(ctx, chave):
    return next((a for a in ctx.get("ativos", []) if a["chave"] == chave), None)


def _ret(ctx):
    return {k: v.get("Período escolhido") for k, v in (ctx.get("retornos") or {}).items() if R._ok(v.get("Período escolhido"))}


def _secao(titulo, linhas):
    return {"titulo": titulo, "linhas": [(t, x) for t, x in linhas if x]}


def _resumo(ctx) -> dict:
    per = ctx.get("periodo") or {}
    L = []
    nomes = [a["chave"] for a in ctx.get("ativos", [])]
    L.append(("✔ Dado", f"Comparação de {', '.join(nomes)} de {per.get('ini', 'n/d')} a {per.get('fim', 'n/d')}, em {per.get('moeda', 'moeda de cada ativo')}."))
    ret = _ret(ctx)
    if len(ret) >= 2:
        mx, mn = max(ret, key=ret.get), min(ret, key=ret.get)
        L.append(("✔ Dado", f"Retorno no período: {mx} {_p(ret[mx], 1, True)} (maior) e {mn} {_p(ret[mn], 1, True)} (menor)."))
    for nome, v in (ctx.get("bench") or {}).items():
        if R._ok(v):
            acima = [k for k, r in ret.items() if r > v]
            L.append(("✔ Dado", f"{nome} no mesmo período: {_p(v, 1, True)}; acima dele: {', '.join(acima) if acima else 'nenhum dos comparados'}."))
    vol = {k: m.get("vol_anual") for k, m in (ctx.get("risco") or {}).items() if R._ok(m.get("vol_anual"))}
    if len(vol) >= 2:
        mx, mn = max(vol, key=vol.get), min(vol, key=vol.get)
        L.append(("≈ Estimativa", f"Volatilidade anual: {mx} {_p(vol[mx], 1)} contra {mn} {_p(vol[mn], 1)} (calculada sobre o passado)."))
    if len(ret) >= 2 and len(vol) >= 2:
        efic = {k: ret[k] / vol[k] for k in ret if k in vol and vol[k] > 0}
        if len(efic) >= 2:
            b = max(efic, key=efic.get)
            L.append(("💬 Opinião", f"No período, {b} entregou mais retorno por unidade de oscilação (retorno ÷ volatilidade = {_num(efic[b])}). "
                                    "Isso descreve o que aconteceu, não o que vai acontecer."))
    if len({a["classe"] for a in ctx.get("ativos", [])}) > 1:
        L.append(("💬 Opinião", "Há classes diferentes na comparação: só retorno, risco e liquidez são comparáveis; as notas de cada classe usam réguas próprias "
                                "e não devem ser colocadas lado a lado."))
    return _secao("Resumo comparativo", L)


def _fortes_fracos(ctx) -> dict:
    L = []
    for a in ctx.get("ativos", []):
        for t in (a.get("vantagens") or [])[:4]:
            L.append(("✔ Dado", f"{a['chave']} · ponto forte: {t}"))
        for t in (a.get("desvantagens") or [])[:4]:
            L.append(("✔ Dado", f"{a['chave']} · ponto fraco: {t}"))
        if not a.get("vantagens") and not a.get("desvantagens"):
            L.append(("✔ Dado", f"{a['chave']}: sem diferenças marcantes nos indicadores comparáveis."))
    return _secao("Pontos fortes e fracos (a partir dos indicadores da tabela)", L)


def _riscos(ctx) -> dict:
    L = []
    risco = ctx.get("risco") or {}
    L += [("≈ Estimativa", t) for t in D.diferencas_de_risco(risco, {a["chave"]: a["classe"] for a in ctx.get("ativos", [])})]
    for k, m in risco.items():
        if R._ok(m.get("var95")):
            L.append(("≈ Estimativa", f"{k}: em 95% dos dias, a perda de um dia foi menor que {_p(m['var95'], 1)} (VaR histórico; em 5% dos dias foi maior)."))
    cor = ctx.get("correlacao") or []
    if cor:
        a, b, c = max(cor, key=lambda x: abs(x[2]))
        L.append(("≈ Estimativa", f"Par que mais andou junto: {a} e {b} (correlação {_num(c)}). Quanto mais perto de 1, menos diversificação um traz ao outro."))
    return _secao("Diferenças de risco", L)


def _indicadores(ctx) -> dict:
    L = []
    for a in ctx.get("ativos", []):
        if a.get("nota") is not None:
            prov = " (provisória: poucos dados)" if a.get("provisoria") else ""
            L.append(("✔ Dado", f"{a['chave']}: nota da classe {a['nota']:.0f}/100, faixa {a.get('faixa', 'n/d')}{prov}."))
        else:
            L.append(("✔ Dado", f"{a['chave']}: sem nota da classe (dados insuficientes)."))
        if a.get("nota_hist") is not None:
            L.append(("≈ Estimativa", f"{a['chave']}: perfil histórico {a['nota_hist']:.0f}/100 (volatilidade, queda máxima, Sharpe e consistência com âncoras da classe)."))
    return _secao("Indicadores e notas", L)


def _ausentes(ctx) -> dict:
    L = []
    for a in ctx.get("ativos", []):
        aus = a.get("ausentes") or []
        if aus:
            L.append(("✔ Dado", f"{a['chave']}: sem dado para {', '.join(aus[:8])}" + (f" e mais {len(aus) - 8}" if len(aus) > 8 else "") + "."))
    L += [("? Limite", t) for t in (ctx.get("alertas") or [])[:6]]
    if not L:
        L.append(("✔ Dado", "Nenhum dado ausente relevante foi identificado."))
    return _secao("Dados ausentes e limites", L)


def _perfis(ctx) -> dict:
    L = []
    risco = ctx.get("risco") or {}
    for a in ctx.get("ativos", []):
        base = _PERFIL.get(a["classe"])
        if not base:
            continue
        m = risco.get(a["chave"]) or {}
        j = f" Medido: volatilidade {_p(m['vol_anual'], 1)} ao ano e queda máxima {_p(m.get('mdd'), 1)}." if R._ok(m.get("vol_anual")) else ""
        L.append(("💬 Opinião", f"{a['chave']} costuma ser melhor compreendido por {base}.{j} Justificativa: características da classe "
                                f"({a.get('classe_nome', a['classe'])}) e os números acima. Não é recomendação personalizada."))
    return _secao("Que perfil de investidor compreende melhor cada alternativa", L)


def resumo_comparativo(ctx: dict | None) -> dict:
    """Relatório completo em seções. Sem ativos: pede para fazer a comparação primeiro."""
    ctx = ctx or {}
    base = {"limite": LIMITE, "gerado_em": ctx.get("gerado_em"), "fontes": ctx.get("fontes") or []}
    if len(ctx.get("ativos") or []) < 2:
        return {**base, "texto": "Ainda não há comparação calculada. Escolha pelo menos 2 ativos e toque em Comparar.", "secoes": [], "sem_dados": True}
    secs = [_resumo(ctx), _fortes_fracos(ctx), _riscos(ctx), _indicadores(ctx), _ausentes(ctx), _perfis(ctx)]
    return {**base, "texto": "Resumo da comparação, com cada conclusão separada em dado, estimativa e opinião.", "secoes": [s for s in secs if s["linhas"]], "sem_dados": False}


def responder_comparacao(pergunta: str, ctx: dict | None) -> dict:
    """Responde a uma pergunta sobre a comparação atual. Recusa pedido de compra/venda e pergunta sem dados."""
    ctx = ctx or {}
    q = I._norm(pergunta)
    base = {"limite": LIMITE, "gerado_em": ctx.get("gerado_em"), "fontes": ctx.get("fontes") or []}
    if not q:
        return {**base, "texto": "Escreva uma pergunta sobre a comparação.", "secoes": [], "sem_dados": True}
    if I._PEDIDO_INDICACAO.search(q):
        return {**base, "texto": "Não indico compra, venda nem qual ativo é melhor. Posso explicar o que a comparação mostra: retorno, risco, indicadores, dados ausentes e que perfil costuma compreender cada alternativa.",
                "secoes": [], "sem_dados": False}
    if len(ctx.get("ativos") or []) < 2:
        return {**base, "texto": "Ainda não há comparação calculada. Escolha pelo menos 2 ativos e toque em Comparar.", "secoes": [], "sem_dados": True}
    mapa = [(r"arrisc|risco|volatil|oscil|queda|var\b|drawdown", ("Diferenças de risco", _riscos)),
            (r"ausent|falt|indisponiv|confiab|qualidade", ("Dados ausentes e limites", _ausentes)),
            (r"perfil|quem|entende|compreend", ("Perfil de investidor", _perfis)),
            (r"forte|fraco|vantage|desvantage|favoravel|desfavoravel", ("Pontos fortes e fracos", _fortes_fracos)),
            (r"nota|pontuac|score|indicador", ("Indicadores e notas", _indicadores))]
    for padrao, (tit, f) in mapa:
        if re.search(padrao, q):
            s = f(ctx)
            return {**base, "texto": tit + ":", "secoes": [s] if s["linhas"] else [], "sem_dados": not s["linhas"]}
    return resumo_comparativo(ctx)
