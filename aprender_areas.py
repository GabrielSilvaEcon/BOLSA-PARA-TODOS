"""Áreas do APRENDER (navegação por nichos) · regras puras, sem banco e sem rede.

A tela inicial do Aprender mostra um card por ÁREA; cada área abre uma tela própria com as suas trilhas (as unidades de
jornada_conteudo.py). As unidades e lições existentes NÃO mudam: aqui só se diz a que área cada unidade pertence.
Certificações têm um nível a mais (a certificação), e cada certificação tem as suas trilhas e o seu simulado.

O progresso continua o mesmo (por id de lição, em jornada.py): XP, ofensiva, recompensas e conquistas não mudam.
"""
from __future__ import annotations

import jornada_conteudo as J

# (id, título, descrição, cor, ícone, arte de fundo do card)
AREAS = [
    dict(id="financas", titulo="Educação financeira", icone="💰", cor="#2DD4A0", arte="moedas",
         descricao="Orçamento, cartão, dívidas, reserva e patrimônio."),
    dict(id="cartoes", titulo="Cartões e milhas", icone="💳", cor="#FF8A3D", arte="loja",
         descricao="Cartões, pontos, milhas, cashback e benefícios."),
    dict(id="investimentos", titulo="Investimentos", icone="📊", cor="#4DA3FF", arte="seta",
         descricao="Renda fixa, ações, FIIs, fundos, análise e carteira."),
    dict(id="trading", titulo="Trading", icone="🕯️", cor="#FF5A7A", arte="velas",
         descricao="Bolsa, candles, tendência, price action e gestão de risco."),
    dict(id="cripto", titulo="Criptomoedas", icone="🪙", cor="#F7C84A", arte="cofre",
         descricao="Bitcoin, blockchain, carteiras, segurança e DeFi."),
    dict(id="certificacoes", titulo="Certificações", icone="🎓", cor="#B07CFF", arte="arena",
         descricao="Preparação para CPA, C-Pro R, C-Pro I e outras."),
    dict(id="especializacoes", titulo="Especializações", icone="🧭", cor="#38D0E0", arte="touro",
         descricao="Empreender, autônomos, família, aposentadoria e golpes."),
]
AREA_POR_ID = {a["id"]: a for a in AREAS}

# Certificações (dentro da área "certificacoes"): cada uma com as suas trilhas e o seu simulado, sem misturar.
CERTIFICACOES = [
    dict(id="cpa", titulo="CPA", sub="ANBIMA · antiga CPA-10", cor="#4DA3FF", descricao="Para quem atende investidores em agências e plataformas."),
    dict(id="cpro_r", titulo="C-Pro R", sub="ANBIMA · antiga CPA-20", cor="#B07CFF", descricao="Para quem atende o varejo de alta renda."),
    dict(id="cpro_i", titulo="C-Pro I", sub="ANBIMA · antiga CEA", cor="#F7C84A", descricao="Para quem orienta investidores e indica produtos."),
]
CERT_POR_ID = {c["id"]: c for c in CERTIFICACOES}

# Unidade -> área (e certificação, quando houver). As 7 unidades que já existiam ficam assim:
AREA_DA_UNIDADE: dict[str, str] = {
    "u_inicio": "financas",
    "u_rf": "investimentos", "u_onde": "investimentos", "u_carteira": "investimentos",
    "u_analise": "investimentos", "u_riscos": "investimentos", "u_imp": "investimentos",
}
CERT_DA_UNIDADE: dict[str, str] = {}

# Nível de cada lição (selo na trilha). Lição sem nível aqui é "iniciante".
NIVEIS = ("iniciante", "intermediario", "avancado")
NIVEL_DA_LICAO: dict[str, str] = {
    "l_fa": "intermediario", "l_ind": "intermediario", "l_div": "intermediario", "l_val": "avancado", "l_tec": "intermediario",
    "l_risc1": "intermediario", "l_risc2": "avancado", "l_trib": "intermediario", "l_carteira": "intermediario", "l_div2": "intermediario",
}


def area_da_unidade(uid: str) -> str:
    u = J.UNIDADE_POR_ID.get(uid) or {}
    return u.get("area") or AREA_DA_UNIDADE.get(uid, "investimentos")


def area_da_licao(lid: str) -> str | None:
    l = J.LICAO_POR_ID.get(lid)
    return area_da_unidade(l["unidade"]) if l else None


def nivel(lid: str) -> str:
    return NIVEL_DA_LICAO.get(lid) or J.NIVEIS_NOVOS.get(lid, "iniciante")


# Ordem das trilhas dentro da área, quando a ordem do conteúdo não é a melhor (trilhas novas perto do assunto que aprofundam).
ORDEM_TRILHAS = {
    "investimentos": ["u_rf", "ui_rf_pratica", "u_onde", "u_carteira", "ui_gestao", "u_analise", "u_riscos", "u_imp"],
}


def unidades_da_area(area: str, cert: str | None = None) -> list[dict]:
    """Unidades (trilhas) da área, na ordem do conteúdo. Em Certificações, só as da certificação pedida."""
    out = [u for u in J.UNIDADES if area_da_unidade(u["id"]) == area]
    ordem = ORDEM_TRILHAS.get(area)
    if ordem:
        out.sort(key=lambda u: ordem.index(u["id"]) if u["id"] in ordem else len(ordem))
    if area == "certificacoes":
        out = [u for u in out if CERT_DA_UNIDADE.get(u["id"]) == cert]
    return out


def licoes_da_area(area: str, cert: str | None = None) -> set[str]:
    return {lid for u in unidades_da_area(area, cert) for lid in u["licoes"]}


def mapa_area(feitas: dict, area: str, cert: str | None = None) -> list[dict]:
    """Como jornada.mapa, mas só com as trilhas da área e com a "próxima lição" contada dentro da área."""
    achou = False
    out = []
    for u in unidades_da_area(area, cert):
        ls = []
        for lid in u["licoes"]:
            l = J.LICAO_POR_ID[lid]
            feita = lid in feitas
            estado = "concluida" if feita else ("livre" if achou else "proxima")
            achou = achou or not feita
            ls.append({"id": lid, "titulo": l["titulo"], "icone": l["icone"], "svg": l.get("icone_svg", "estrela"), "estado": estado, "aula": l.get("aula"),
                       "melhor": feitas.get(lid, {}).get("melhor", 0.0), "exercicios": len(l["exercicios"]), "nivel": nivel(lid)})
        n = sum(1 for x in ls if x["estado"] == "concluida")
        out.append({**{k: u[k] for k in ("id", "titulo", "icone", "cor", "descricao")}, "svg": u.get("icone_svg", "estrela"), "licoes": ls, "feitas": n,
                    "total": len(ls), "completa": bool(ls) and n == len(ls)})
    return out


def resumo_areas(feitas: dict, erros: list[str]) -> list[dict]:
    """Um card por área: lições feitas/total, trilhas completas e quantos erros esperam revisão ali."""
    out = []
    for a in AREAS:
        if a["id"] == "certificacoes":
            ids = {lid for c in CERTIFICACOES for lid in licoes_da_area("certificacoes", c["id"])}
        else:
            ids = licoes_da_area(a["id"])
        ex = [e for e in erros if J.EX_POR_ID.get(e, {}).get("licao") in ids]
        out.append({**a, "feitas": sum(1 for lid in ids if lid in feitas), "total": len(ids), "erros": len(ex), "em_breve": not ids})
    return out


def erros_da_area(erros: list[str], area: str, cert: str | None = None) -> list[str]:
    ids = licoes_da_area(area, cert)
    return [e for e in erros if J.EX_POR_ID.get(e, {}).get("licao") in ids]


def certificacoes(feitas: dict) -> list[dict]:
    out = []
    for c in CERTIFICACOES:
        ids = licoes_da_area("certificacoes", c["id"])
        out.append({**c, "feitas": sum(1 for lid in ids if lid in feitas), "total": len(ids), "em_breve": not ids})
    return out


def iniciar_revisao_area(erros: list[str], area: str, cert: str | None = None, n: int = 5) -> dict | None:
    """Revisão só com os erros da área (o mesmo formato de sessão de jornada.iniciar_revisao). None se não houver nada."""
    ids = erros_da_area(erros, area, cert)[:n]
    if not ids:
        return None
    return {"licao": None, "fila": list(ids), "total": len(ids), "feitos": 0, "erros_ids": [], "revisao": True, "ids": list(ids)}


# ------------------------------------------------------------------ teste de nivelamento (opcional, por área)
# Uma pergunta da primeira e uma da última lição de cada trilha. Não dá XP, não muda o progresso nem a fila de revisão:
# só recomenda a primeira trilha em que a pessoa errou alguma pergunta de primeira.
MIN_TRILHAS_NIVEL = 2


def tem_nivelamento(area: str) -> bool:
    return area != "certificacoes" and len([u for u in unidades_da_area(area) if u["licoes"]]) >= MIN_TRILHAS_NIVEL


def iniciar_nivelamento(area: str) -> dict | None:
    if not tem_nivelamento(area):
        return None
    ids = []
    for u in unidades_da_area(area):
        if not u["licoes"]:
            continue
        for lid in dict.fromkeys([u["licoes"][0], u["licoes"][-1]]):
            ids.append(J.LICAO_POR_ID[lid]["exercicios"][0]["id"])
    return {"licao": None, "fila": list(ids), "total": len(ids), "feitos": 0, "erros_ids": [], "revisao": False, "ids": list(ids),
            "nivelamento": area}


def resultado_nivelamento(s: dict) -> dict:
    """Por trilha: acertou tudo de primeira? A recomendada é a primeira trilha (na ordem da área) com algum erro."""
    area = s["nivelamento"]
    erros = set(s.get("erros_ids") or [])
    trilhas = []
    for u in unidades_da_area(area):
        meus = [e for e in s["ids"] if J.LICAO_POR_ID[J.EX_POR_ID[e]["licao"]]["unidade"] == u["id"]]
        if meus:
            trilhas.append({"id": u["id"], "titulo": u["titulo"], "ok": not any(e in erros for e in meus)})
    rec = next((t for t in trilhas if not t["ok"]), None)
    return {"nivelamento": True, "area": area, "trilhas": trilhas, "recomendada": rec, "acertos_primeira": s["total"] - len(erros), "total": s["total"],
            "xp": 0, "tc": 0, "ofensiva": None, "conquistas_novas": [], "meta_nova": False}
