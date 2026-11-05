"""Segurança de contas (Passo 21): senhas, e-mail, tokens e limpeza de logs.

Módulo puro: não importa Streamlit e não acessa banco nem internet, por isso é fácil de testar.

- Senhas: hash scrypt (hashlib, padrão do Python; algoritmo memória-dura recomendado pelo OWASP), com sal aleatório
  por senha e parâmetros gravados dentro do próprio hash. Isso permite aumentar o custo no futuro (precisa_rehash)
  ou trocar de algoritmo sem invalidar contas antigas. Senha nunca é guardada nem registrada em texto puro.
- Tokens (sessão, verificação de e-mail, redefinição de senha): aleatórios (secrets) e guardados só como SHA-256,
  então um vazamento do banco não entrega tokens utilizáveis.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets
import unicodedata
from datetime import datetime, timedelta, timezone

# ------------------------------------------------------------------ relógio (trocável nos testes)
_agora_fn = lambda: datetime.now(timezone.utc)  # noqa: E731


def agora() -> datetime:
    return _agora_fn()


def iso(dt: datetime | None = None) -> str:
    """Data/hora UTC em texto ISO (ordena corretamente como texto, por isso serve de filtro no banco)."""
    return (dt or agora()).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def de_iso(txt: str | None) -> datetime | None:
    if not txt:
        return None
    try:
        return datetime.strptime(str(txt)[:23].rstrip("Z"), "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            return datetime.strptime(str(txt)[:19], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def somar(segundos: float, base: datetime | None = None) -> str:
    return iso((base or agora()) + timedelta(seconds=segundos))


# ------------------------------------------------------------------ e-mail e nome
_EMAIL = re.compile(r"^[a-z0-9._%+\-]{1,64}@[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?(?:\.[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?)+$")


def normalizar_email(email: str | None) -> str:
    return unicodedata.normalize("NFKC", str(email or "")).strip().lower()


def validar_email(email: str | None) -> tuple[bool, str, str]:
    """(ok, e-mail normalizado, mensagem). Só formato: a posse do e-mail é provada pelo link enviado."""
    e = normalizar_email(email)
    if not e:
        return False, e, "Informe o e-mail."
    if len(e) > 254 or ".." in e or not _EMAIL.match(e):
        return False, e, "Esse e-mail não parece válido. Confira se há erro de digitação (exemplo: nome@dominio.com)."
    return True, e, ""


def validar_nome(nome: str | None) -> tuple[bool, str, str]:
    n = " ".join(unicodedata.normalize("NFKC", str(nome or "")).split())
    if len(n) < 2:
        return False, n, "Informe seu nome (mínimo 2 letras)."
    if len(n) > 80:
        return False, n, "O nome pode ter no máximo 80 caracteres."
    if any(unicodedata.category(c).startswith("C") for c in n) or any(c in n for c in "<>"):
        return False, n, "O nome tem caracteres que não são permitidos."
    return True, n, ""


# ------------------------------------------------------------------ política de senha
SENHA_MIN, SENHA_MAX = 10, 128
_COMUNS = {"1234567890", "12345678910", "123456789012", "qwertyuiop", "senha12345", "password123", "senha123456",
           "brasil12345", "abc1234567", "1q2w3e4r5t", "minhasenha1", "mudar12345", "admin12345", "password1234",
           "0123456789", "senhasenha1", "corinthians1", "flamengo123", "123456abcd", "abcd123456"}


def validar_senha(senha: str | None, email: str = "", nome: str = "") -> list[str]:
    """Lista de problemas (vazia = senha aceita). Mensagens em português, uma por regra."""
    s = senha or ""
    erros = []
    if len(s) < SENHA_MIN:
        erros.append(f"Use pelo menos {SENHA_MIN} caracteres.")
    if len(s) > SENHA_MAX:
        erros.append(f"Use no máximo {SENHA_MAX} caracteres.")
    if s and not any(c.isalpha() for c in s):
        erros.append("Inclua pelo menos uma letra.")
    if s and not any(c.isdigit() for c in s):
        erros.append("Inclua pelo menos um número.")
    baixa = s.lower()
    if baixa in _COMUNS or (s and len(set(baixa)) <= 3):
        erros.append("Essa senha é muito comum ou repetitiva. Escolha outra.")
    local = normalizar_email(email).split("@")[0]
    if len(local) >= 4 and local in baixa:
        erros.append("A senha não deve conter o seu e-mail.")
    primeiro = (nome or "").strip().lower().split(" ")[0] if nome else ""
    if len(primeiro) >= 4 and primeiro in baixa:
        erros.append("A senha não deve conter o seu nome.")
    return erros


def forca_senha(senha: str | None) -> tuple[int, str]:
    """(0 a 4, rótulo) só para a barra de força na tela; a regra de aceitação é validar_senha."""
    s = senha or ""
    pts = sum([len(s) >= 10, len(s) >= 14, any(c.islower() for c in s) and any(c.isupper() for c in s),
               any(c.isdigit() for c in s) and any(c.isalpha() for c in s), any(not c.isalnum() for c in s)])
    pts = min(4, max(0, pts - (1 if len(s) < SENHA_MIN else 0)))
    return pts, ("muito fraca", "fraca", "razoável", "boa", "forte")[pts]


# ------------------------------------------------------------------ hash de senha (scrypt)
_N, _R, _P, _DK = 2 ** 15, 8, 1, 32
_MEM = 64 * 1024 * 1024


def _b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def _scrypt(senha: str, sal: bytes, n: int, r: int, p: int, dk: int) -> bytes:
    senha_b = unicodedata.normalize("NFKC", senha).encode("utf-8")
    return hashlib.scrypt(senha_b, salt=sal, n=n, r=r, p=p, maxmem=max(_MEM, 256 * n * r), dklen=dk)


def hash_senha(senha: str, n: int = _N, r: int = _R, p: int = _P) -> str:
    """'scrypt$n$r$p$sal$hash'. Sal novo a cada chamada: a mesma senha gera hashes diferentes."""
    sal = secrets.token_bytes(16)
    return f"scrypt${n}${r}${p}${_b64(sal)}${_b64(_scrypt(senha, sal, n, r, p, _DK))}"


def _partes(h: str):
    try:
        alg, n, r, p, sal, dig = (h or "").split("$")
        if alg != "scrypt":
            return None
        return int(n), int(r), int(p), base64.b64decode(sal), base64.b64decode(dig)
    except Exception:
        return None


def verificar_senha(senha: str, h: str | None) -> bool:
    """Compara em tempo constante. Hash ausente ou malformado nunca confere."""
    pt = _partes(h or "")
    if not pt or not senha or len(senha) > 1024:
        return False
    n, r, p, sal, dig = pt
    try:
        calc = _scrypt(senha, sal, n, r, p, len(dig))
    except Exception:
        return False
    return hmac.compare_digest(calc, dig)


def precisa_rehash(h: str | None) -> bool:
    pt = _partes(h or "")
    return not pt or (pt[0], pt[1], pt[2]) != (_N, _R, _P)


_FALSO = None


def gastar_tempo_falso(senha: str) -> None:
    """Quando o e-mail não existe, gasta o mesmo tempo de uma verificação real: o tempo de resposta não revela
    se a conta existe."""
    global _FALSO
    if _FALSO is None:
        _FALSO = hash_senha("senha-falsa-para-igualar-o-tempo")
    verificar_senha(senha or "x", _FALSO)


# ------------------------------------------------------------------ tokens
def novo_token(bytes_: int = 32) -> tuple[str, str]:
    """(token para entregar ao usuário, hash para guardar no banco)."""
    t = secrets.token_urlsafe(bytes_)
    return t, hash_token(t)


def hash_token(token: str | None) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def novo_id() -> str:
    return secrets.token_hex(16)


def hash_curto(txt: str) -> str:
    """Identificador não reversível (para limitar tentativas sem guardar o e-mail em claro)."""
    return hashlib.sha256(("bpt|" + txt).encode("utf-8")).hexdigest()[:24]


# ------------------------------------------------------------------ logs sem dados sensíveis
_PADROES_SENSIVEIS = [
    (re.compile(r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+"), "[e-mail]"),
    (re.compile(r"(?i)(senha|password|passwd|secret|token|apikey|api_key|authorization|bearer|cookie)\s*[:=]\s*\S+"), r"\1=[oculto]"),
    (re.compile(r"\b[A-Za-z0-9_\-]{32,}\b"), "[código]"),
    (re.compile(r"(?i)\bscrypt\$[^\s]+"), "[hash]"),
]


def limpar_para_log(txt, limite: int = 300) -> str:
    """Remove e-mails, senhas, tokens e chaves de um texto antes de guardá-lo ou mostrá-lo."""
    s = str(txt or "")
    for rx, sub in _PADROES_SENSIVEIS:
        s = rx.sub(sub, s)
    return s[:limite]
