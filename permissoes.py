"""Permissões modulares (Passo 21). Módulo puro.

Ninguém recebe privilégio administrativo por padrão: todo cadastro nasce 'usuario'. O primeiro administrador é
informado pelos secrets ([admin] emails = [...]); depois disso, administradores promovem ou rebaixam outros.
Administrador e suporte NÃO veem dados de carteira, preferências, senhas nem tokens de ninguém: as permissões
abaixo cobrem só gestão de contas e operação do sistema.
"""
from __future__ import annotations

PAPEIS = ("usuario", "suporte", "admin")
ROTULOS = {"usuario": "Usuário", "suporte": "Suporte", "admin": "Administrador"}

PERM_USUARIO = frozenset({"proprios.ler", "proprios.gravar", "proprios.apagar"})
PERM_SUPORTE = PERM_USUARIO | {"admin.resumo", "admin.usuarios.ver", "admin.auditoria.ver", "admin.erros.ver", "sistema.dados"}
PERM_ADMIN = PERM_SUPORTE | {"admin.usuarios.suspender", "admin.usuarios.reativar", "admin.usuarios.papel",
                             "admin.backup", "admin.banco", "admin.seguranca"}

PERMISSOES = {"usuario": PERM_USUARIO, "suporte": PERM_SUPORTE, "admin": PERM_ADMIN}


def papel_valido(papel: str | None) -> str:
    """Papel desconhecido vira 'usuario' (nunca eleva privilégio)."""
    return papel if papel in PAPEIS else "usuario"


def tem(papel: str | None, permissao: str) -> bool:
    return permissao in PERMISSOES[papel_valido(papel)]


def pode_acessar_admin(papel: str | None) -> bool:
    return tem(papel, "admin.resumo")


def papel_efetivo(papel_gravado: str | None, email: str, admins_secrets: list[str] | tuple[str, ...]) -> str:
    """Papel usado na sessão: o gravado no banco, elevado a 'admin' se o e-mail estiver na lista dos secrets.
    A lista dos secrets só eleva; nunca rebaixa nem cria outros papéis."""
    lista = {str(e).strip().lower() for e in (admins_secrets or [])}
    if (email or "").strip().lower() in lista:
        return "admin"
    return papel_valido(papel_gravado)
