"""Alertas do cenário econômico para a CARTEIRA REAL (puro: sem Streamlit e sem rede; usado pela página e pelo monitor).

Regras de ouro:
  - só ativos da carteira real da própria conta geram alerta (nunca pesquisados, exemplos, fictícia, simulações ou listas de acompanhamento);
  - a primeira leitura de cada ativo só registra o ponto de partida: não avisa nada (o cenário "continuar igual" nunca vira notificação);
  - avisa quando o veredito do ativo MUDA (neutro<->bom/ruim, bom<->ruim), quando a nota se move muito desde o último aviso, ou quando
    aparece um fator de risco forte e novo para aquele ativo. Mudanças de vários ativos do mesmo setor viram UM aviso;
  - sem duplicidade: chave de deduplicação por setor, transição e semana, e intervalo mínimo entre avisos parecidos (do notif.suprimir);
  - cada aviso diz o que mudou, quais indicadores causaram, o cenário anterior e o atual, a confiança e que não é recomendação.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import macro_ativos as MA
import macro_cenario as MC
import macro_fontes as MF

SALTO_NOTA = 0.30           # mudança de nota (de -1 a +1) desde o último aviso que justifica um novo aviso sem troca de veredito
FORCA_RISCO = 0.70          # valor do fator (0 a 1) a partir do qual ele é um "risco forte"
REPETE_RISCO_DIAS = 14      # o mesmo risco, para o mesmo ativo, não se repete antes disso
PREFS_MACRO_PADRAO = {"ativo": True, "mudanca": True, "intensidade": True, "risco": True, "neutro": False, "somente_ruim": False}
_ORDEM = {"BOM": 2, "NEUTRO": 1, "RUIM": 0}


def normalizar_prefs_macro(p) -> dict:
    p = p if isinstance(p, dict) else {}
    return {k: bool(p.get(k, v)) for k, v in PREFS_MACRO_PADRAO.items()}


def _iso(agora):
    a = agora or datetime.now(timezone.utc)
    return (a.astimezone(timezone.utc) if a.tzinfo else a.replace(tzinfo=timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _de_iso(t):
    try:
        return datetime.strptime(str(t), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


# ------------------------------------------------------------------ cenário de cada posição
def avaliar_posicoes(posicoes: list[dict], fatores: dict, indicadores: dict | None = None, anteriores: dict | None = None,
                     infos: dict | None = None, div_pl: dict | None = None, pesos: dict | None = None) -> list[dict]:
    """Uma linha por posição da carteira real: perfil + cenário próprio do ativo. `anteriores` = {ticker: veredito} (histerese)."""
    out = []
    for p in posicoes or []:
        tk = p["ativo"]
        if p.get("setor_chave"):
            perf = {"ticker": tk, "classe": p["classe"], "classe_rotulo": MA.CLASSES_ROTULO.get(p["classe"], p["classe"]), "setor_chave": p["setor_chave"],
                    "setor": MA.SETORES_ROT.get(p["setor_chave"], ""), "origem": "classe", "ajuste": {},
                    "justificativa": "Título de renda fixa da sua carteira: o cenário depende do indexador (pós-fixado ou prefixado/IPCA+).",
                    "sens": MA.sensibilidades(p["setor_chave"], {}, None)}
        else:
            perf = MA.perfil(tk, (infos or {}).get(tk), p.get("classe"), (div_pl or {}).get(tk))
        row = {**perf, "peso": (pesos or {}).get(tk)}
        if perf["setor_chave"]:
            c = MC.avaliar(perf["setor_chave"], fatores, (anteriores or {}).get(tk), perf.get("ajuste"), indicadores)
            row.update({"veredito": c["veredito"], "nota": c["nota"], "confianca": c["confianca"], "confianca_pontos": c["confianca_pontos"],
                        "cenario": c})
        else:
            row.update({"veredito": None, "nota": None, "confianca": None, "cenario": None})
        out.append(row)
    return out


# ------------------------------------------------------------------ detecção de mudanças e montagem do aviso
def _indicadores_da_causa(cen: dict, fatores: dict, ind: dict | None, n: int = 3) -> list[dict]:
    """Os indicadores dos fatores que mais pesaram, com valor e data, para o aviso mostrar o que causou a classificação."""
    out, vistos = [], set()
    for c in (cen.get("contribuicoes") or [])[:n]:
        for i in fatores.get(c["fator"], {}).get("usa", [])[:2]:
            r = (ind or {}).get(i)
            if r and i not in vistos and r.get("valor") is not None:
                vistos.add(i)
                out.append({"id": i, "nome": r["nome"], "valor": round(r["valor"], 4), "unidade": r["unidade"], "data": r.get("data"), "fonte": r.get("fonte")})
    return out


def _mensagem(setor_nome: str, ativos: list[str], antes: str, depois: str, cen: dict, causas: list[dict]) -> tuple[str, str]:
    rot = {"BOM": "favorável", "NEUTRO": "neutro", "RUIM": "desfavorável"}
    titulo = f"Cenário econômico: {setor_nome} passou de {antes.lower()} para {depois.lower()}"
    mec = [c["mecanismo"] for c in (cen.get("favor") if depois == "BOM" else cen.get("contra") if depois == "RUIM" else cen.get("contribuicoes") or [])[:2] if c.get("mecanismo")]
    nomes = ", ".join(c["nome"] for c in causas[:3])
    partes = [f"O ambiente econômico para {setor_nome.lower()} ficou {rot[depois]} (antes: {rot[antes]}). Ativos seus afetados: {', '.join(ativos[:6])}."]
    if mec:
        partes.append("Por quê: " + "; ".join(mec) + ".")
    if nomes:
        partes.append(f"Indicadores que mais pesaram: {nomes}.")
    partes.append(f"Confiança da análise: {cen['confianca'].lower()}. É uma leitura do ambiente, não prevê o preço do ativo nem é recomendação.")
    return titulo, " ".join(partes)


def avaliar_conta(posicoes: list[dict], fatores: dict, indicadores: dict | None, estado: dict | None, prefs: dict | None,
                  agora: datetime | None = None, pesos: dict | None = None, infos: dict | None = None, div_pl: dict | None = None) -> tuple[list[dict], dict]:
    """Devolve (notificações no formato do app, novo estado da conta). `estado` = {'ativos': {ticker: {...}}, 'riscos': {chave: iso}}."""
    import notif as N
    agora = agora or datetime.now(timezone.utc)
    prefs = normalizar_prefs_macro(prefs)
    est = {"ativos": dict((estado or {}).get("ativos") or {}), "riscos": dict((estado or {}).get("riscos") or {})}
    anter = {tk: v.get("v") for tk, v in est["ativos"].items()}
    linhas = avaliar_posicoes(posicoes, fatores, indicadores, anter, infos, div_pl, pesos)
    atuais = {l["ticker"]: l for l in linhas if l["veredito"]}
    est["ativos"] = {tk: v for tk, v in est["ativos"].items() if tk in atuais}          # sai da carteira real = sai do acompanhamento
    est["riscos"] = {k: v for k, v in est["riscos"].items() if k.split("|")[0] in atuais}
    if not prefs["ativo"]:
        for tk, l in atuais.items():
            est["ativos"][tk] = {"v": l["veredito"], "nota": l["nota"], "nota_ref": l["nota"], "em": _iso(agora)}
        return [], est
    mudancas: dict = {}          # (setor, antes, depois) -> [linhas]
    notifs = []
    for tk, l in atuais.items():
        ant = est["ativos"].get(tk)
        if ant is None:                                              # primeira leitura: só registra o ponto de partida
            est["ativos"][tk] = {"v": l["veredito"], "nota": l["nota"], "nota_ref": l["nota"], "em": _iso(agora)}
            continue
        antes, depois = ant["v"], l["veredito"]
        base_nota = ant.get("nota_ref", ant.get("nota", l["nota"]))
        if antes != depois:
            para_neutro = depois == "NEUTRO"
            if prefs["mudanca"] and not (para_neutro and not prefs["neutro"]) and not (prefs["somente_ruim"] and depois != "RUIM"):
                mudancas.setdefault((l["setor_chave"], antes, depois), []).append(l)
            est["ativos"][tk] = {"v": depois, "nota": l["nota"], "nota_ref": l["nota"], "em": _iso(agora)}
        elif prefs["intensidade"] and abs(l["nota"] - base_nota) >= SALTO_NOTA and depois != "NEUTRO" and not (prefs["somente_ruim"] and depois != "RUIM"):
            mudancas.setdefault((l["setor_chave"], antes, "INTENSIDADE:" + ("piorou" if l["nota"] < base_nota else "melhorou")), []).append(l)
            est["ativos"][tk] = {"v": depois, "nota": l["nota"], "nota_ref": l["nota"], "em": _iso(agora)}
        else:
            est["ativos"][tk] = {"v": depois, "nota": l["nota"], "nota_ref": base_nota, "em": ant.get("em") or _iso(agora)}
    semana = agora.isocalendar()
    for (setor, antes, depois), ls in mudancas.items():
        ls = sorted(ls, key=lambda x: -(x.get("peso") or 0))
        cen = ls[0]["cenario"]
        causas = _indicadores_da_causa(cen, fatores, indicadores)
        nome_setor = ls[0]["setor"]
        ativos = [x["ticker"] for x in ls]
        peso_tot = sum((x.get("peso") or 0) for x in ls)
        if depois.startswith("INTENSIDADE:"):
            sentido = depois.split(":")[1]
            alvo = antes
            titulo = f"Cenário econômico: o quadro para {nome_setor.lower()} {sentido} ({antes.lower()} com nota mais {'fraca' if sentido == 'piorou' else 'forte'})"
            texto = (f"Sem mudar de classificação ({antes.lower()}), a nota do cenário para {nome_setor.lower()} {sentido} de forma relevante. "
                     f"Ativos seus afetados: {', '.join(ativos[:6])}. Indicadores que mais pesaram: {', '.join(c['nome'] for c in causas[:3])}. "
                     f"Confiança: {cen['confianca'].lower()}. Leitura do ambiente, não recomendação.")
            imp = "media" if sentido == "piorou" and antes == "RUIM" else "baixa"
            tipo = "intensidade"
            dedup_dest = f"{antes}-{sentido}"
        else:
            alvo = depois
            titulo, texto = _mensagem(nome_setor, ativos, antes, depois, cen, causas)
            virada = {antes, depois} == {"BOM", "RUIM"}
            imp = "alta" if virada or (depois == "RUIM" and peso_tot >= 5) else "media" if depois == "RUIM" else "baixa" if depois == "NEUTRO" else "media"
            tipo = "mudanca"
            dedup_dest = f"{antes}-{depois}"
        notifs.append({"tipo": "macro_" + tipo, "regra_id": f"macro_{tipo}_{setor}", "ativo": ativos[0], "prioridade": imp, "titulo": titulo, "texto": texto,
                       "assinatura": f"{setor}|{dedup_dest}|{semana[0]}-{semana[1]}",
                       "dados": {"fonte": "Banco Central, IBGE, Ipeadata e FRED", "cenario_anterior": antes, "cenario_atual": alvo if tipo == "mudanca" else antes,
                                 "setor": nome_setor, "ativos_afetados": ativos, "confianca": cen["confianca"], "nota": cen["nota"],
                                 "indicadores": causas, "dados_ate": cen.get("dados_ate"), "fonte_oficial": True}})
    # riscos novos e fortes para ativos da carteira real
    if prefs["risco"]:
        for tk, l in atuais.items():
            cen = l["cenario"]
            for c in (cen.get("riscos") or []):
                if c["efeito"] > -0.15 or abs(c["valor"]) < FORCA_RISCO:
                    continue
                chave = f"{tk}|{c['fator']}"
                ult = _de_iso(est["riscos"].get(chave))
                if ult and agora - ult < timedelta(days=REPETE_RISCO_DIAS):
                    continue
                est["riscos"][chave] = _iso(agora)
                if chave not in (estado or {}).get("riscos", {}) and tk not in (estado or {}).get("ativos", {}):
                    continue                                          # ativo recém-adicionado: só registra, sem avisar
                notifs.append({"tipo": "macro_risco", "regra_id": f"macro_risco_{c['fator']}", "ativo": tk, "prioridade": "media",
                               "titulo": f"Risco econômico a acompanhar em {tk}: {c['nome'].lower()}",
                               "texto": f"{c['texto']} Para {l['setor'].lower()}, isso pesa contra: {c['mecanismo']}. Confiança: {cen['confianca'].lower()}. "
                                        f"É um risco potencial do ambiente, não uma previsão sobre o preço de {tk}.",
                               "assinatura": f"{tk}|{c['fator']}|{semana[0]}-{semana[1]}",
                               "dados": {"fonte": "Banco Central, IBGE, Ipeadata e FRED", "cenario_atual": l["veredito"], "setor": l["setor"], "fator": c["fator"],
                                         "ativos_afetados": [tk], "confianca": cen["confianca"], "fonte_oficial": True}})
    return [N.de_disparo(d, "macro", agora) for d in notifs], est
