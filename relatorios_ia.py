"""
Passo 19 · Assistente dos relatórios (integra a Central de inteligência, Passo 13). Sem Streamlit e sem rede.

Responde SÓ com os números já calculados pelos relatórios (contexto `ctx`). Cada resposta separa:
 · dados confirmados (valores das fontes e contas diretas), · estimativas, · hipóteses/limites, e informa a fonte e a data.
Não recomenda compra ou venda e não promete rentabilidade.

ctx (montado por relatorios_app.contexto_ia):
 {"gerado_em", "carteira", "periodo", "resumo", "desemp", "periodos": [linhas], "classes": [{"nome","valor","pct"}], "ativos": [{"nome","valor","pct"}],
  "ranking", "qualidade": [...], "nao_calc": {...}, "risco": {...}, "concentracao": {...}, "fontes": [...], "fotos": {...} | None}
"""
from __future__ import annotations

import math
import re

import intel as I
import relatorios as R

LIMITE = ("Os números vêm dos dados que o aplicativo coletou na data indicada e podem ter defasagem ou lacunas. "
          "Rentabilidade passada não garante rentabilidade futura. Isto não é recomendação de compra ou venda.")
_GATILHO = re.compile(r"relatorio|resum\w+ (d[ao]s?|minha|a) (carteira|patrimonio)|resum\w+ executiv|dashboard|painel executivo|"
                      r"(explique|explica|explicar|por que|porque|como) .{0,25}(ganh|perd|resultado|rentabilidade|patrimonio)|"
                      r"o que mudou|contribu\w+|maior (ganho|perda)|qualidade dos dados|dados .{0,20}(ausente|desatualizad|faltando|problema)|"
                      r"compar\w+ .{0,30}(cdi|ibovespa|benchmark|s&p|ipca)|(cdi|ibovespa|benchmark).{0,25}(carteira|bati|supero)")


def eh_pergunta_relatorio(pergunta: str) -> bool:
    return bool(_GATILHO.search(I._norm(pergunta)))


def _v(x, f="brl"):
    return R.brl(x) if f == "brl" else R.pct(x, 2, True) if f == "pct_s" else R.pct(x)


def responder_relatorio(pergunta: str, ctx: dict | None) -> dict:
    ctx = ctx or {}
    q = I._norm(pergunta)
    gerado = ctx.get("gerado_em")
    base = {"limite": LIMITE, "referencia": f"Relatório calculado em {str(gerado)[:16].replace('T', ' ')}" if gerado else "Nenhum relatório carregado",
            "consultado": "Consultei: " + (", ".join(k for k in ("resumo", "desemp", "periodos", "classes", "ranking", "qualidade", "risco", "fotos") if ctx.get(k))
                                          or "nada (abra a página Relatórios)."),
            "fontes": ctx.get("fontes") or []}

    def resp(texto, confirmados=None, estimativas=None, hipoteses=None, falta=False):
        linhas = [f"✔ Dado: {x}" for x in confirmados or []] + [f"≈ Estimativa: {x}" for x in estimativas or []] + [f"? Hipótese/limite: {x}" for x in hipoteses or []]
        return {**base, "texto": texto, "linhas": linhas, "sem_dados": falta}
    if not q:
        return resp("Escreva uma pergunta sobre o seu relatório.", falta=True)
    if I._PEDIDO_INDICACAO.search(q):
        return resp("Não indico compra, venda nem qual ativo é melhor. Posso explicar o que o relatório mostra: resultado, contribuição de cada posição, concentração e qualidade dos dados.")
    if not ctx.get("resumo"):
        return resp("Ainda não há relatório calculado. Abra a página Relatórios (Carteira) com a carteira preenchida e volte aqui.", falta=True)

    r, d = ctx["resumo"], ctx.get("desemp") or {}
    qual = ctx.get("qualidade") or []
    grave = [x for x in qual if x["nivel"] in ("alto", "medio")]

    if re.search(r"qualidade|ausente|desatualiz|faltando|confi|problema", q):
        if not qual:
            return resp("Não encontrei problemas de qualidade nos dados desta carteira.", [f"{r['n_posicoes']} posições com cotação."])
        return resp(f"Há {len(grave)} ponto(s) de atenção nos dados (e {len(qual) - len(grave)} informativo(s)):", [f"[{x['nivel']}] {x['texto']}" for x in qual[:10]],
                    hipoteses=["Indicadores que dependem dos itens acima ficam como n/d em vez de serem estimados."])

    if re.search(r"o que mudou|desde a ultima|fotografia|snapshot", q):
        f = ctx.get("fotos")
        if not f:
            return resp("Ainda não há duas fotografias para comparar. Salve uma fotografia hoje e outra depois, na aba Histórico.", falta=True)
        conf = [f"Em {f['dias']} dia(s) o patrimônio variou {_v(f.get('dif_patrimonio'))}; o investido variou {_v(f.get('dif_investido'))}."]
        if f.get("novos"):
            conf.append("Entraram: " + ", ".join(f["novos"]) + ".")
        if f.get("saiu"):
            conf.append("Saíram: " + ", ".join(f["saiu"]) + ".")
        return resp("Comparação entre as duas últimas fotografias:", conf,
                    hipoteses=["A variação do patrimônio mistura aportes/retiradas e variação de preço; ela NÃO é rentabilidade. Veja o TWR no período."])

    if re.search(r"benchmark|cdi|ibovespa|s&p|ipca|compar", q):
        tab = ctx.get("periodos") or []
        if not tab:
            return resp("Não há tabela de períodos (falta histórico de preços da carteira).", falta=True)
        ls = []
        for t in tab:
            if t.get("Carteira (TWR)") is None or (isinstance(t.get("Carteira (TWR)"), float) and math.isnan(t["Carteira (TWR)"])):
                continue
            cdi = t.get("CDI")
            ls.append(f"{t['Período']}: carteira {R.pct(t['Carteira (TWR)'], 2, True)}" + (f" × CDI {R.pct(cdi, 2, True)}" if R._ok(cdi) else " (CDI n/d)")
                      + (f" × Ibovespa {R.pct(t['Ibovespa'], 2, True)}" if R._ok(t.get("Ibovespa")) else ""))
        return resp("Carteira (TWR, sem efeito de aportes) contra os benchmarks disponíveis:", ls[:8],
                    hipoteses=["Cada benchmark só entra se a série cobre o período inteiro; comparar carteira mista com um único índice é uma referência, não um veredito."])

    if re.search(r"ganh|perd|resultado|contribu|rentabilidade|explique|explica", q):
        conf = [f"Patrimônio atual {_v(r['patrimonio'])}."]
        if r.get("investido") is not None:
            conf.append(f"Custo das posições com custo informado: {_v(r['investido'])}; ganho não realizado {_v(r['ganho'])} ({_v(r.get('ganho_pct'), 'pct_s')}).")
        if r.get("proventos"):
            conf.append(f"Proventos recebidos registrados: {_v(r['proventos'])}.")
        est = []
        if d.get("ok"):
            conf.append(f"Crescimento do patrimônio no período: {_v(d.get('crescimento'))}, sendo {_v(d.get('aportes_liquidos'))} de aportes líquidos e {_v(d.get('resultado_investimentos'))} de resultado dos investimentos.")
            est.append(f"Rentabilidade ponderada pelo tempo (TWR): {_v(d['twr'], 'pct_s')} no período; MWR (XIRR) {_v(d.get('mwr_aa'), 'pct_s') if d.get('mwr_aa') is not None else 'n/d'} ao ano.")
        rk = ctx.get("ranking") or {}
        if rk.get("melhores"):
            conf.append("Maiores ganhos: " + ", ".join(f"{a} ({R.pct(b, 1, True)})" for a, b, _ in rk["melhores"][:3]) + ".")
        if rk.get("piores"):
            conf.append("Maiores perdas: " + ", ".join(f"{a} ({R.pct(b, 1, True)})" for a, b, _ in rk["piores"][:3]) + ".")
        hip = [f"{len(r.get('sem_custo') or [])} posição(ões) sem custo informado ficam fora do ganho."] if r.get("sem_custo") else []
        hip.append("Retornos brutos de impostos e taxas não lançadas.")
        return resp("O que explica o resultado da carteira:", conf, est, hip)

    if re.search(r"concentra|diversific|exposic|classe|setor|pais|moeda", q):
        cl = ctx.get("classes") or []
        at = ctx.get("ativos") or []
        conf = ["Por classe: " + "; ".join(f"{x['nome']} {R.pct(x['pct'], 1)}" for x in cl[:6]) + "."] if cl else []
        if at:
            conf.append("Maiores posições: " + "; ".join(f"{x['nome']} {R.pct(x['pct'], 1)}" for x in at[:5]) + ".")
        c = ctx.get("concentracao") or {}
        est = [f"Número efetivo de posições {c['n_efetivo']:.1f} (HHI {c['hhi']:.3f})."] if c.get("ok") and R._ok(c.get("n_efetivo")) else []
        return resp("Como a carteira está distribuída:", conf, est, ["Concentração é descrição, não julgamento: o app não diz qual é a alocação correta para você."])

    # resumo geral
    conf = [f"Patrimônio {_v(r['patrimonio'])} em {r['n_posicoes']} posições."]
    if r.get("ganho") is not None:
        conf.append(f"Ganho não realizado {_v(r['ganho'])} ({_v(r.get('ganho_pct'), 'pct_s')}) sobre o custo informado.")
    est = [f"TWR do período {_v(d['twr'], 'pct_s')}."] if d.get("ok") else []
    cl = ctx.get("classes") or []
    if cl:
        conf.append("Maior classe: " + f"{cl[0]['nome']} ({R.pct(cl[0]['pct'], 1)}).")
    ri = ctx.get("risco") or {}
    if R._ok(ri.get("vol")):
        est.append(f"Volatilidade anualizada {R.pct(ri['vol'], 1)}; maior queda {R.pct(ri.get('mdd'), 1) if R._ok(ri.get('mdd')) else 'n/d'}.")
    hip = [f"{len(grave)} ponto(s) de atenção na qualidade dos dados." if grave else "Sem alertas de qualidade dos dados."]
    return resp("Resumo do relatório da carteira:", conf, est, hip)
