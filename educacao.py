"""Passo 24 — Lógica da educação financeira (pura, sem Streamlit): progresso, quiz, trilhas, conquistas, sugestões, glossário e
métricas didáticas calculadas com dados reais passados pela tela.

Princípios:
- Os três modos (iniciante/intermediário/avançado) só mudam a apresentação (modos.por_modo); todo o conteúdo fica aberto para todos.
- Pontos e conquistas premiam ESTUDO (aulas, acertos, trilhas), nunca operações ou risco. Um teste não mede capacidade de investir.
- Nada de número de mercado inventado: métricas vêm de séries reais passadas à função; sem série, devolvem None.
- O progresso é um dicionário pequeno em st.session_state["edu_progresso"], gravado no perfil da conta (usuarios.CHAVES): isolado por conta.
"""
from __future__ import annotations

import math
from datetime import datetime, timezone

import edu_conteudo as E
import modos

LIMITE_ATIVIDADE = 150
PONTOS_AULA, PONTOS_ACERTO, PONTOS_TRILHA = 10, 5, 50
MIN_ACERTO_TRILHA = 0.70


def _agora_iso(agora: datetime | None = None) -> str:
    return (agora or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat(timespec="seconds")


# ------------------------------------------------------------------ progresso
def novo_progresso() -> dict:
    return {"v": 1, "modo": modos.PADRAO, "aulas": {}, "quiz": {}, "trilhas": {}, "certificados": {}, "vistos": [], "ativos": 0,
            "atividade": [], "meta_semana": 3}


def normalizar(p) -> dict:
    """Aceita lixo/ausente e devolve sempre um progresso válido (descarta ids que não existem mais)."""
    base = novo_progresso()
    if not isinstance(p, dict):
        return base
    base["modo"] = modos.modo_valido(p.get("modo"))
    base["aulas"] = {k: v for k, v in (p.get("aulas") or {}).items() if k in E.POR_ID and isinstance(v, dict)}
    base["quiz"] = {k: v for k, v in (p.get("quiz") or {}).items() if k in E.QUIZ_POR_ID and isinstance(v, dict)}
    base["trilhas"] = {k: str(v) for k, v in (p.get("trilhas") or {}).items() if k in E.TRILHA_POR_ID}
    base["certificados"] = {k: str(v) for k, v in (p.get("certificados") or {}).items() if k in E.TRILHA_POR_ID}
    base["vistos"] = [str(x) for x in (p.get("vistos") or []) if str(x) in E.INDICADORES][:60]
    for chave, minimo, maximo in (("ativos", 0, 10**6), ("meta_semana", 1, 21)):
        try:
            base[chave] = min(maximo, max(minimo, int(p.get(chave) or base[chave])))
        except (TypeError, ValueError):
            pass
    base["atividade"] = [a for a in (p.get("atividade") or []) if isinstance(a, dict)][-LIMITE_ATIVIDADE:]
    return base


def _log(p: dict, tipo: str, ref: str, agora: datetime | None = None, extra: str = "") -> None:
    p["atividade"].append({"t": _agora_iso(agora), "tipo": tipo, "ref": ref, "x": extra})
    del p["atividade"][:-LIMITE_ATIVIDADE]


def registrar_aula(p: dict, aula_id: str, agora: datetime | None = None) -> dict:
    p = normalizar(p)
    if aula_id not in E.POR_ID:
        return p
    a = p["aulas"].setdefault(aula_id, {"primeira": _agora_iso(agora), "n": 0})
    a["n"] = int(a.get("n", 0)) + 1
    a["ultima"] = _agora_iso(agora)
    if a["n"] == 1:
        _log(p, "aula", aula_id, agora)
    return p


def registrar_indicador_visto(p: dict, sigla: str) -> dict:
    p = normalizar(p)
    if sigla in E.INDICADORES and sigla not in p["vistos"]:
        p["vistos"].append(sigla)
    return p


def registrar_ativo_estudado(p: dict, agora: datetime | None = None) -> dict:
    p = normalizar(p)
    p["ativos"] += 1
    _log(p, "ativo", "estudo com dados reais", agora)
    return p


def corrigir(qid: str, escolha: int) -> tuple[bool, str]:
    """(acertou, explicação). Escolha inválida conta como erro sem exceção."""
    q = E.QUIZ_POR_ID.get(qid)
    if not q:
        return False, ""
    return escolha == q["correta"], q["explicacao"]


def responder(p: dict, qid: str, escolha: int, agora: datetime | None = None) -> tuple[bool, dict]:
    """Corrige e registra. Pontos por acerto só na PRIMEIRA vez que a pergunta é acertada (sem farmar pontos repetindo)."""
    p = normalizar(p)
    ok, _ = corrigir(qid, escolha)
    if qid not in E.QUIZ_POR_ID:
        return False, p
    r = p["quiz"].setdefault(qid, {"tent": 0, "acertos": 0, "ok": False})
    r["tent"] += 1
    r["ok"] = bool(ok)                      # o estado atual é o da última resposta
    if ok:
        r["acertos"] += 1
        r.setdefault("pontuou", True)
    r["ultima"] = _agora_iso(agora)
    _log(p, "quiz", qid, agora, "acerto" if ok else "erro")
    return ok, p


def pontos(p: dict) -> int:
    p = normalizar(p)
    aulas = len(p["aulas"]) * PONTOS_AULA
    acertos = sum(1 for r in p["quiz"].values() if r.get("acertos", 0) > 0) * PONTOS_ACERTO
    return aulas + acertos + len(p["certificados"]) * PONTOS_TRILHA


# ------------------------------------------------------------------ trilhas
def perguntas_da_trilha(trilha: dict) -> list[dict]:
    return [q for q in E.QUIZ if q["aula"] in trilha["aulas"]]


def progresso_trilha(p: dict, trilha_id: str) -> dict:
    p = normalizar(p)
    t = E.TRILHA_POR_ID[trilha_id]
    lidas = [a for a in t["aulas"] if a in p["aulas"]]
    qs = perguntas_da_trilha(t)
    resp = [q for q in qs if q["id"] in p["quiz"]]
    certas = [q for q in resp if p["quiz"][q["id"]].get("ok")]
    acerto = (len(certas) / len(resp)) if resp else 0.0
    etapas_ok = len(lidas) + len(resp)
    total = len(t["aulas"]) + len(qs)
    concluida = (len(lidas) == len(t["aulas"]) and len(resp) == len(qs) and acerto >= MIN_ACERTO_TRILHA)
    return {"lidas": len(lidas), "aulas": len(t["aulas"]), "respondidas": len(resp), "perguntas": len(qs), "acerto": acerto,
            "pct": (etapas_ok / total) if total else 0.0, "concluida": concluida, "iniciada": bool(lidas or resp),
            "proxima": next((a for a in t["aulas"] if a not in p["aulas"]), None)}


def iniciar_trilha(p: dict, trilha_id: str, agora: datetime | None = None) -> dict:
    p = normalizar(p)
    if trilha_id in E.TRILHA_POR_ID and trilha_id not in p["trilhas"]:
        p["trilhas"][trilha_id] = _agora_iso(agora)
        _log(p, "trilha", trilha_id, agora, "iniciada")
    return p


def atualizar_certificados(p: dict, agora: datetime | None = None) -> tuple[dict, list[str]]:
    """Emite o certificado interno (educacional) das trilhas concluídas. Devolve (progresso, novos)."""
    p = normalizar(p)
    novos = []
    for t in E.TRILHAS:
        if t["id"] not in p["certificados"] and progresso_trilha(p, t["id"])["concluida"]:
            p["certificados"][t["id"]] = _agora_iso(agora)
            _log(p, "trilha", t["id"], agora, "concluída")
            novos.append(t["id"])
    return p, novos


# ------------------------------------------------------------------ conquistas, metas, dificuldades, sugestões
CONQUISTAS = [
    ("primeira_aula", "Primeira aula", "Leu a primeira aula.", lambda p: len(p["aulas"]) >= 1),
    ("cinco_aulas", "Estudioso", "Leu 5 aulas.", lambda p: len(p["aulas"]) >= 5),
    ("dez_acertos", "Afiado", "Acertou 10 perguntas diferentes.", lambda p: sum(1 for r in p["quiz"].values() if r.get("acertos", 0) > 0) >= 10),
    ("primeiro_certificado", "Trilha concluída", "Concluiu uma trilha.", lambda p: len(p["certificados"]) >= 1),
    ("tres_trilhas", "Aprendiz constante", "Concluiu 3 trilhas.", lambda p: len(p["certificados"]) >= 3),
    ("indicadores", "Decifrador de indicadores", "Abriu 8 explicações de indicadores.", lambda p: len(p["vistos"]) >= 8),
    ("dado_real", "Mão na massa", "Estudou 3 ativos com dados reais do app.", lambda p: p["ativos"] >= 3),
]


def conquistas(p: dict) -> list[dict]:
    p = normalizar(p)
    return [{"id": i, "titulo": t, "descricao": d, "ok": bool(f(p))} for i, t, d, f in CONQUISTAS]


def aulas_na_semana(p: dict, agora: datetime | None = None) -> int:
    """Aulas lidas pela primeira vez nos últimos 7 dias (meta de aprendizagem)."""
    p = normalizar(p)
    ref = (agora or datetime.now(timezone.utc)).astimezone(timezone.utc)
    n = 0
    for a in p["aulas"].values():
        try:
            d = datetime.fromisoformat(a.get("primeira"))
        except (TypeError, ValueError):
            continue
        if 0 <= (ref - d).total_seconds() <= 7 * 86400:
            n += 1
    return n


def dificuldades(p: dict) -> list[dict]:
    """Assuntos em que a última resposta de pelo menos 2 perguntas indica acerto abaixo de 60%."""
    p = normalizar(p)
    por: dict = {}
    for qid, r in p["quiz"].items():
        assunto = E.POR_ID[E.QUIZ_POR_ID[qid]["aula"]]["assunto"]
        por.setdefault(assunto, []).append(bool(r.get("ok")))
    out = []
    for assunto, lst in por.items():
        if len(lst) >= 2 and sum(lst) / len(lst) < 0.6:
            out.append({"assunto": assunto, "rotulo": E.ROTULO_ASSUNTO[assunto], "acerto": sum(lst) / len(lst), "n": len(lst)})
    return sorted(out, key=lambda d: d["acerto"])


def sugerir(p: dict, n: int = 3) -> list[dict]:
    """Próximos conteúdos: (1) reforço onde errou, (2) continuação de trilha iniciada, (3) aulas do nível escolhido ainda não lidas."""
    p = normalizar(p)
    out: list[dict] = []

    def add(aula_id, motivo):
        if aula_id and aula_id in E.POR_ID and all(o["aula"] != aula_id for o in out) and len(out) < n:
            out.append({"aula": aula_id, "motivo": motivo})

    for d in dificuldades(p):
        for a in E.AULAS:
            if a["assunto"] == d["assunto"]:
                add(a["id"], f"Reforço: {d['rotulo']}")
    for tid in p["trilhas"]:
        pr = progresso_trilha(p, tid)
        if not pr["concluida"] and pr["proxima"]:
            add(pr["proxima"], f"Continuar: {E.TRILHA_POR_ID[tid]['titulo']}")
    alvo = p["modo"]
    for a in E.AULAS:
        if a["id"] not in p["aulas"] and a["dificuldade"] == alvo:
            add(a["id"], f"Nível {modos.ROTULOS[alvo].lower()}")
    for a in E.AULAS:
        if a["id"] not in p["aulas"]:
            add(a["id"], "Ainda não lida")
    return out


# ------------------------------------------------------------------ conteúdo por modo
def texto_aula(aula: dict, modo: str | None = None) -> str:
    return modos.por_modo(aula.get("iniciante"), aula.get("intermediario"), aula.get("avancado"), modo=modo) or ""


def aulas_do_assunto(assunto: str | None = None, dificuldade: str | None = None) -> list[dict]:
    return [a for a in E.AULAS if (not assunto or a["assunto"] == assunto) and (not dificuldade or a["dificuldade"] == dificuldade)]


def fontes_da_aula(aula: dict) -> list[tuple[str, str]]:
    return [E.FONTES[k] for k in aula.get("fontes", []) if k in E.FONTES]


# ------------------------------------------------------------------ indicadores e glossário
def chave_indicador(termo: str) -> str | None:
    t = str(termo or "").strip()
    if t in E.INDICADORES:
        return t
    return E.ALIAS_IND.get(t.lower())


def explicar_indicador(termo: str) -> dict | None:
    k = chave_indicador(termo)
    if not k:
        return None
    return {"sigla": k, **E.INDICADORES[k]}


def indicadores_da_classe(classe: str | None) -> list[str]:
    """Indicadores aplicáveis à classe. classes=[] vale para qualquer ativo com histórico de preços (RSI, volatilidade...)."""
    return [k for k, v in E.INDICADORES.items() if (not v["classes"]) or classe in v["classes"]]


def aplicavel(sigla: str, classe: str) -> bool:
    k = chave_indicador(sigla)
    return bool(k) and ((not E.INDICADORES[k]["classes"]) or classe in E.INDICADORES[k]["classes"])


def buscar_glossario(consulta: str = "", glossario_app: dict | None = None) -> list[dict]:
    """Junta o glossário do app (glossario.py), as explicações de indicadores e os termos extras. Busca sem acento/caixa."""
    import unicodedata

    def norm(s):
        return "".join(c for c in unicodedata.normalize("NFD", str(s).lower()) if unicodedata.category(c) != "Mn")

    itens: dict[str, dict] = {}
    for k, v in (glossario_app or {}).items():
        itens[norm(k)] = {"termo": k, "definicao": v[0], "uso": v[1], "formula": "", "aulas": []}
    for k, v in E.INDICADORES.items():
        itens[norm(k)] = {"termo": k, "definicao": f"{v['nome']}. {v['significa']}", "uso": v["serve"], "formula": v["calculo"],
                          "aulas": [], "indicador": k, "relacionados": v["relacionados"]}
    for k, (d, ex, f, aulas) in E.GLOSSARIO_EXTRA.items():
        itens.setdefault(norm(k), {"termo": k, "definicao": d, "uso": ex, "formula": f, "aulas": aulas})
    try:                                                  # glossário central: nome completo, níveis, fórmula, exemplo e limitações
        import glossario_central as _gc
        for e in _gc.todos():
            itens[norm(e["sigla"])] = {"termo": _gc.nome_completo(e["sigla"]), "definicao": e["definicao"], "uso": e["exemplo"], "formula": e["formula"],
                                      "aulas": itens.get(norm(e["sigla"]), {}).get("aulas", []), "central": e["sigla"],
                                      "indicador": itens.get(norm(e["sigla"]), {}).get("indicador"),
                                      "relacionados": itens.get(norm(e["sigla"]), {}).get("relacionados", [])}
            itens[norm(e["sigla"])]["busca"] = " ".join(norm(x) for x in (e["sigla"], e["pt"], e["en"], *e["alias"]))
    except Exception:
        pass
    q = norm(consulta).strip()
    out = [v for k, v in itens.items() if not q or q in k or q in norm(v["definicao"]) or q in v.get("busca", "")]
    return sorted(out, key=lambda v: (norm(v["termo"]) != q, not norm(v["termo"]).startswith(q), norm(v["termo"])))


# ------------------------------------------------------------------ leitura de um indicador real (regras, sem julgamento de compra)
def _f(v):
    try:
        x = float(v)
        return x if math.isfinite(x) else None
    except (TypeError, ValueError):
        return None


def ler_indicador(sigla: str, valor) -> str:
    """Tradução didática de um valor REAL em palavras. Sem valor: diz que está indisponível. Nunca opina sobre comprar ou vender."""
    v = _f(valor)
    k = chave_indicador(sigla)
    return _virgula(_ler(k, v))


def _virgula(txt: str) -> str:
    import re
    return re.sub(r"(?<=\d)\.(?=\d)", ",", txt)


def _ler(k, v) -> str:
    if v is None:
        return "Dado indisponível nas fontes do app neste momento. Não estimamos números para completar."
    if k == "P/L":
        if v <= 0:
            return "P/L negativo ou zero costuma indicar prejuízo: o indicador perde o sentido."
        return f"Com P/L de {v:.1f}, o preço equivale a cerca de {v:.1f} anos do lucro atual, se o lucro se mantivesse. Compare com o setor e com o histórico da própria empresa."
    if k == "P/VP":
        rel = "abaixo" if v < 1 else ("próximo de" if abs(v - 1) < 0.05 else "acima")
        return f"P/VP de {v:.2f}: o mercado paga {rel} do valor patrimonial contábil. Verifique a qualidade dos ativos antes de concluir algo."
    if k == "Dividend yield":
        return f"Nos últimos 12 meses, os proventos equivaleram a {v:.1f}% do preço atual. Veja se o pagamento é recorrente: yields muito altos pedem cautela."
    if k == "ROE":
        return f"Para cada R$ 100 de patrimônio, a empresa gerou cerca de R$ {v:.1f} de lucro no período. Veja a dívida: alavancagem alta infla o ROE."
    if k == "Margem líquida":
        return f"De cada R$ 100 de receita, sobraram cerca de R$ {v:.1f} de lucro líquido. Compare com empresas do mesmo setor."
    if k == "EBITDA":
        return f"EV/EBITDA de {v:.1f}: o valor da firma equivale a cerca de {v:.1f} anos do EBITDA atual. Compare com pares do setor."
    return f"Valor atual: {v:.2f}."


# ------------------------------------------------------------------ métricas didáticas sobre séries reais
def _serie(precos):
    """Lista/Series de fechamentos → pd.Series limpa (só preços positivos e finitos) ou None."""
    import pandas as pd
    try:
        s = pd.to_numeric(pd.Series(list(precos)), errors="coerce").dropna()
    except (TypeError, ValueError):
        return None
    s = s[(s > 0) & s.map(math.isfinite)].reset_index(drop=True)
    return s if len(s) >= 30 else None


def metricas_risco(precos, dias_ano: int = 252) -> dict | None:
    """Com uma série de preços real: retorno do período, volatilidade anualizada e queda máxima. Usa as MESMAS funções do módulo de
    gestão de carteira (gestao.vol_anual e gestao.drawdown), para que o número seja idêntico em toda a plataforma.
    Devolve None se a série for curta (< 30 pontos) ou inválida."""
    import gestao
    s = _serie(precos)
    if s is None:
        return None
    r = s.pct_change().dropna()
    vol = gestao.vol_anual(r, minimo=30)
    dd = gestao.drawdown(s)
    if vol is None or not dd.get("ok"):
        return None
    return {"retorno": float(s.iloc[-1] / s.iloc[0] - 1), "volatilidade": vol, "drawdown": dd["maximo"], "pontos": len(s)}


def sharpe_simples(precos, taxa_livre_aa: float, dias_ano: int = 252) -> float | None:
    """Sharpe didático: delega a gestao.sharpe, com a taxa livre de risco anual convertida em taxa diária equivalente."""
    import gestao
    s = _serie(precos)
    if s is None:
        return None
    rf_dia = (1 + float(taxa_livre_aa)) ** (1 / dias_ano) - 1
    return gestao.sharpe(s.pct_change().dropna(), rf=rf_dia, minimo=30)


# ------------------------------------------------------------------ simulações educativas (HIPOTÉTICAS)
def juros_compostos(inicial: float, aporte_mensal: float, taxa_aa: float, anos: int, inflacao_aa: float = 0.0) -> dict:
    """Evolução mensal hipotética com aportes no fim de cada mês. Usa as funções do simulador (Passo 18) para taxa mensal e inflação."""
    import simulador as sim
    anos = max(1, min(int(anos), 60))
    im = sim.mensal(taxa_aa)
    saldo, aportado, serie = float(inicial), float(inicial), []
    for m in range(1, anos * 12 + 1):
        saldo = saldo * (1 + im) + aporte_mensal
        aportado += aporte_mensal
        if m % 12 == 0:
            serie.append({"ano": m // 12, "saldo": saldo, "aportado": aportado, "juros": saldo - aportado,
                          "saldo_real": saldo / sim.fatores_inflacao(inflacao_aa, m)[-1] if inflacao_aa else saldo})
    return {"hipotetico": True, "final": saldo, "aportado": aportado, "juros": saldo - aportado,
            "final_real": serie[-1]["saldo_real"] if serie else saldo, "serie": serie, "taxa_real_aa": sim.fisher(taxa_aa, inflacao_aa)}


def queda_e_recuperacao(queda: float) -> float:
    """Ganho necessário para recuperar uma queda (0,5 → 100%). Didático: perdas pesam mais que ganhos iguais."""
    q = min(max(float(queda), 0.0), 0.99)
    return 1 / (1 - q) - 1


# ------------------------------------------------------------------ professor: instruções por modo
def instrucao_modo(modo: str | None) -> str:
    return modos.por_modo(
        iniciante="Nível da pessoa: INICIANTE. Use linguagem simples, poucos termos técnicos (explique cada um), exemplos do dia a dia e passo a passo.",
        intermediario="Nível da pessoa: INTERMEDIÁRIO. Use indicadores e métricas, compare ativos, interprete resultados e fale de diversificação e riscos.",
        avancado="Nível da pessoa: AVANÇADO. Pode usar modelos quantitativos, valuation aprofundado, métricas estatísticas e cenários, com rigor e ressalvas.",
        modo=modo) or ""


PROFESSOR_REGRAS = (
    "Você é um professor de investimentos. Seu papel é EDUCAR: explicar conceitos, indicadores, gráficos e relatórios, criar exemplos didáticos "
    "(sempre avisando quando o número do exemplo é hipotético) e sugerir o que estudar depois. Diferencie educação de recomendação: nunca diga o que a "
    "pessoa deve comprar, vender ou manter, e não faça carteira personalizada. Não trate previsões como certezas. Não invente dados: use só os do contexto "
    "e diga quando faltarem. Cite que regras tributárias mudam e remeta às fontes oficiais (CVM, Banco Central, B3, Tesouro Direto, ANBIMA, Receita).")


def contexto_professor(modo: str | None, aula_id: str | None = None, dados_reais: str = "") -> str:
    partes = [PROFESSOR_REGRAS, instrucao_modo(modo)]
    a = E.POR_ID.get(aula_id or "")
    if a:
        partes.append(f"Aula que a pessoa está lendo: {a['titulo']}. Texto da aula: {texto_aula(a, modo)}")
    if dados_reais:
        partes.append("Dados reais do app para usar nos exemplos (com fonte e data): " + dados_reais)
    return "\n\n".join(partes)
