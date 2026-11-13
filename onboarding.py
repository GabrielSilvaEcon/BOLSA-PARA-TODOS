"""Onboarding de novos jogadores — regras puras (sem Streamlit, sem banco). A tela fica em onboarding_app.py.

Tela 1 (Seu Perfil): perfil + NickName. Tela 2 (Sua Jornada): interesses (múltiplos) + nível de conhecimento. Tela 3 (Seu objetivo): um objetivo principal; "Concluir e entrar" marca `concluido`. As escolhas ficam em `onb` (etapa = tela a mostrar);
não há moedas, XP nem missões: o onboarding só registra preferências.
"""
from __future__ import annotations

import competicao as C

CHAVE = "onb"                   # chave do session_state gravada junto com os dados da conta (usuarios.CHAVES)
VERSAO = 1
DESDE = "2026-11-13"            # só contas criadas a partir desta data (ISO) entram no onboarding; as anteriores seguem como estavam
ETAPAS = ("Seu Perfil", "Sua Jornada", "Pronto para Caçar!")
MAX_NICK = 20
MIN_NICK = 3

PERFIS = (
    {"id": "arrojado", "titulo": "Arrojado", "desc": "Busco alto potencial de retorno, mesmo com mais riscos.", "cor": "#22d3ee"},
    {"id": "equilibrado", "titulo": "Equilibrado", "desc": "Busco um bom equilíbrio entre risco e retorno.", "cor": "#a78bfa"},
    {"id": "conservador", "titulo": "Conservador", "desc": "Prefiro segurança e investimentos mais estáveis.", "cor": "#34d399"},
    {"id": "iniciante", "titulo": "Iniciante", "desc": "Estou começando e quero aprender mais.", "cor": "#fbbf24"},
    {"id": "explorador", "titulo": "Explorador", "desc": "Gosto de testar novas estratégias e ativos.", "cor": "#fb923c"},
)
IDS = tuple(p["id"] for p in PERFIS)

# Tela 2 — Sua Jornada
INTERESSES = (
    {"id": "acoes", "titulo": "Ações"}, {"id": "fiis", "titulo": "FIIs"}, {"id": "cripto", "titulo": "Cripto"},
    {"id": "rendafixa", "titulo": "Renda Fixa"}, {"id": "etfs", "titulo": "ETFs"}, {"id": "commodities", "titulo": "Commodities"},
    {"id": "tecnologia", "titulo": "Tecnologia"}, {"id": "esg", "titulo": "ESG"}, {"id": "outros", "titulo": "Outros"},
)
IDS_INT = tuple(i["id"] for i in INTERESSES)
NIVEIS = (
    {"id": "iniciante", "titulo": "Iniciante", "desc": "Estou começando a aprender."},
    {"id": "intermediario", "titulo": "Intermediário", "desc": "Já conheço os principais conceitos."},
    {"id": "avancado", "titulo": "Avançado", "desc": "Tenho experiência e analiso o mercado."},
)
IDS_NIV = tuple(n["id"] for n in NIVEIS)

# Tela 3 — Seu objetivo (um só objetivo principal). `icone` é o nome da imagem em arte_onboarding.
OBJETIVOS = (
    {"id": "aprender", "titulo": "Aprender a investir", "icone": "chapeu",
     "desc": "Quero aprender sobre o mercado financeiro e desenvolver meus conhecimentos."},
    {"id": "oportunidades", "titulo": "Encontrar oportunidades", "icone": "etfs",
     "desc": "Quero descobrir ativos interessantes e identificar possíveis oportunidades no mercado."},
    {"id": "analises", "titulo": "Aprimorar minhas análises", "icone": "niv_intermediario",
     "desc": "Quero evoluir na análise técnica e fundamentalista."},
    {"id": "patrimonio", "titulo": "Construir patrimônio", "icone": "rendafixa",
     "desc": "Quero encontrar investimentos alinhados aos meus objetivos de longo prazo."},
    {"id": "estrategia", "titulo": "Desenvolver estratégia", "icone": "equilibrado",
     "desc": "Quero melhorar minhas decisões e criar estratégias de investimento."},
    {"id": "competir", "titulo": "Competir e evoluir", "icone": "niv_avancado",
     "desc": "Quero completar desafios, conquistar recompensas e subir no ranking."},
)
IDS_OBJ = tuple(o["id"] for o in OBJETIVOS)


def perfil(pid) -> dict | None:
    return next((p for p in PERFIS if p["id"] == pid), None)


def normalizar(onb) -> dict:
    """Estado guardado, com tipos conferidos. Nunca devolve 'concluido' verdadeiro por engano: só True literal conta."""
    d = onb if isinstance(onb, dict) else {}
    pid = d.get("perfil") if d.get("perfil") in IDS else ""
    nick = str(d.get("nick") or "").strip()[:MAX_NICK]
    try:
        etapa = int(d.get("etapa") or 1)
    except (TypeError, ValueError):
        etapa = 1
    ints = d.get("interesses")
    ints = [i for i in IDS_INT if isinstance(ints, (list, tuple)) and i in ints]      # só ids conhecidos, sem repetir, na ordem do catálogo
    return {"v": VERSAO, "etapa": min(max(etapa, 1), len(ETAPAS)), "perfil": pid, "nick": nick if C.apelido_valido(nick)[0] else "",
            "interesses": ints, "nivel": d.get("nivel") if d.get("nivel") in IDS_NIV else "",
            "objetivo": d.get("objetivo") if d.get("objetivo") in IDS_OBJ else "", "concluido": d.get("concluido") is True}


def formato_ok(texto: str) -> tuple[bool, str]:
    """Confere só o formato (sem banco). Devolve (ok, mensagem). Vazio não é erro: a mensagem fica vazia."""
    t = str(texto or "")
    if not t.strip():
        return False, ""
    if t != t.strip() or " " in t:
        return False, "Sem espaços: use letras, números, ponto, hífen ou sublinhado."
    if len(t) < MIN_NICK:
        return False, f"Use pelo menos {MIN_NICK} caracteres."
    if len(t) > MAX_NICK:
        return False, f"Use no máximo {MAX_NICK} caracteres."
    return C.apelido_valido(t)


def verificar_nick(texto: str, livre=None) -> tuple[str, str]:
    """('vazio'|'invalido'|'ocupado'|'ok'|'erro', mensagem). `livre(chave)` diz se o apelido ainda está disponível (None = não confere)."""
    ok, msg = formato_ok(texto)
    if not str(texto or "").strip():
        return "vazio", ""
    if not ok:
        return "invalido", msg
    if livre is not None:
        try:
            if not livre(C.chave_apelido(texto)):
                return "ocupado", "Esse NickName já está em uso. Escolha outro."
        except Exception:
            return "erro", "Não consegui conferir agora. Tente de novo em instantes."
    return "ok", "NickName disponível!"


def pode_continuar(pid, estado_nick: str) -> bool:
    return pid in IDS and estado_nick == "ok"


ETAPAS_PRONTAS = 3             # quantas telas já existem (hoje as 3). Ao criar a Tela 2, subir para 2, e assim por diante


def pode_continuar_2(interesses, nivel) -> bool:
    """Tela 2: pelo menos um interesse e um nível de conhecimento."""
    return bool([i for i in (interesses or []) if i in IDS_INT]) and nivel in IDS_NIV


def pode_concluir(objetivo) -> bool:
    """Tela 3: só conclui com um objetivo principal escolhido."""
    return objetivo in IDS_OBJ


def perfil_do_usuario(onb) -> dict:
    """O que o onboarding registrou, para personalizações futuras (missões, conteúdos, recomendações). Vazio até concluir."""
    n = normalizar(onb)
    if not n["concluido"]:
        return {}
    return {"perfil_investidor": n["perfil"], "interesses": n["interesses"], "nivel": n["nivel"], "objetivo": n["objetivo"]}


def alternar_interesse(atual, iid: str) -> list:
    """Marca ou desmarca um interesse (seleção múltipla), mantendo a ordem do catálogo."""
    cur = {i for i in (atual or []) if i in IDS_INT}
    cur ^= {iid} if iid in IDS_INT else set()
    return [i for i in IDS_INT if i in cur]


def precisa(onb, criado_em: str = "", doc_novo: bool = False, desde: str = DESDE) -> bool:
    """Mostrar o onboarding? Sim para toda conta (nova ou antiga) que ainda não concluiu; volta na etapa em que parou."""
    n = normalizar(onb)
    if n["concluido"]:
        return False
    return n["etapa"] <= ETAPAS_PRONTAS
