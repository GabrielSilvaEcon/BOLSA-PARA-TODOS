"""Onboarding de novos jogadores — regras puras (sem Streamlit, sem banco). A tela fica em onboarding_app.py.

Tela 1 (Seu Perfil): perfil de investidor + NickName. As telas 2 (Sua Jornada) e 3 (Pronto para Caçar) ainda não existem:
por isso esta etapa NUNCA marca o onboarding como concluído, só guarda as escolhas em `onb` para a próxima etapa.
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
    return {"v": VERSAO, "etapa": min(max(etapa, 1), len(ETAPAS)), "perfil": pid, "nick": nick if C.apelido_valido(nick)[0] else "",
            "concluido": d.get("concluido") is True}


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


ETAPAS_PRONTAS = 1             # quantas telas já existem (hoje só a Tela 1). Ao criar a Tela 2, subir para 2, e assim por diante


def precisa(onb, criado_em: str = "", doc_novo: bool = False, desde: str = DESDE) -> bool:
    """Mostrar o onboarding? Sim para toda conta (nova ou antiga) que ainda não concluiu e cuja próxima etapa já existe.
    Quem já fez a Tela 1 (etapa guardada ≥ 2) não a vê de novo enquanto a Tela 2 não existir; quando existir, volta na etapa 2."""
    n = normalizar(onb)
    if n["concluido"]:
        return False
    return n["etapa"] <= ETAPAS_PRONTAS
