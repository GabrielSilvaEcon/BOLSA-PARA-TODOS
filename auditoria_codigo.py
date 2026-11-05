"""Auditoria estática do próprio código (Passo 22). Módulo puro: só lê arquivos, não executa nada do app.

Procura, de forma preventiva: segredos escritos no código, chamadas perigosas (eval, exec, pickle, shell, SQL montado com
texto), pedidos de rede sem tempo limite, certificados desligados, abertura de arquivos com caminho dinâmico e HTML montado
sem escape. Cada achado traz severidade (critico, alto, medio, baixo) e a linha. Segredos nunca aparecem inteiros no relatório.
"""
from __future__ import annotations

import ast
import os
import re
import subprocess
from dataclasses import dataclass

SEVERIDADES = ("critico", "alto", "medio", "baixo")

# padrões de credenciais conhecidas (formato do emissor) -> (nome, severidade)
_SEGREDOS = [
    ("chave Google/Gemini", re.compile(r"AIza[0-9A-Za-z_\-]{30,}"), "critico"),
    ("token GitHub", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr)_[0-9A-Za-z]{30,}\b|github_pat_[0-9A-Za-z_]{40,}"), "critico"),
    ("chave secreta tipo sk-", re.compile(r"\bsk-[A-Za-z0-9_\-]{30,}"), "critico"),
    ("chave AWS", re.compile(r"\bAKIA[0-9A-Z]{16}\b"), "critico"),
    ("token Slack", re.compile(r"\bxox[abprs]-[0-9A-Za-z\-]{20,}"), "critico"),
    ("chave privada", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"), "critico"),
    ("chave secreta do Supabase", re.compile(r"\bsb_secret_[0-9A-Za-z_\-]{16,}"), "critico"),
    ("JWT (token de serviço)", re.compile(r"\beyJ[0-9A-Za-z_\-]{15,}\.eyJ[0-9A-Za-z_\-]{15,}\.[0-9A-Za-z_\-]{15,}"), "alto"),
    ("atribuição de segredo no código",
     re.compile(r"""(?ix)\b(?:client_secret|cookie_secret|api[_-]?key|secret[_-]?key|password|senha|token)\b\s*[:=]\s*["']([^"'\s]{16,})["']"""), "alto"),
    ("URL com senha embutida", re.compile(r"\b[a-z][a-z0-9+.\-]*://[^/\s:@]+:[^/\s:@]{4,}@"), "alto"),
]
_PLACEHOLDER = re.compile(r"(?i)(xxx|seu[_-]|sua[_-]|senha-de|de-16|exemplo|example|changeme|troque|gere-um|placeholder|\.\.\.|<.*>|\$\{|%s|\{\w*\}|aaaa|0000)")

_IGNORAR_DIRS = {".git", "__pycache__", ".pytest_cache", ".venv", "venv", "node_modules", ".mypy_cache", ".ruff_cache"}
_TEXTO = (".py", ".toml", ".txt", ".md", ".json", ".yml", ".yaml", ".cfg", ".ini", ".env", ".html", ".js", ".sql", ".sh")


@dataclass(frozen=True)
class Achado:
    arquivo: str
    linha: int
    severidade: str
    categoria: str
    detalhe: str

    def como_dict(self) -> dict:
        return {"arquivo": self.arquivo, "linha": self.linha, "severidade": self.severidade,
                "categoria": self.categoria, "detalhe": self.detalhe}


def mascarar(valor: str) -> str:
    """Mostra só o começo e o fim; nada que permita reaproveitar o segredo."""
    v = str(valor)
    return v[:3] + "…" + v[-2:] if len(v) > 8 else "…"


def varrer_segredos(texto: str, arquivo: str = "?") -> list[Achado]:
    out = []
    for n, linha in enumerate(texto.splitlines(), 1):
        for nome, rx, sev in _SEGREDOS:
            for m in rx.finditer(linha):
                valor = m.group(1) if m.groups() else m.group(0)
                if _PLACEHOLDER.search(valor) or _PLACEHOLDER.search(linha) and nome == "atribuição de segredo no código":
                    continue
                if nome == "atribuição de segredo no código" and ("st.secrets" in linha or "os.environ" in linha or "getenv" in linha):
                    continue
                out.append(Achado(arquivo, n, sev, "segredo", f"{nome}: {mascarar(valor)}"))
    return out


# ------------------------------------------------------------------ análise por AST
_REDE = {"get", "post", "put", "delete", "patch", "head", "request", "urlopen"}
_PERIGOSAS = {"eval": "alto", "exec": "alto", "compile": "baixo"}
_SQL_RX = re.compile(r"(?i)\b(select|insert|update|delete|drop|alter)\b[\s\S]{0,60}\b(from|into|set|table|where)\b")


def _nome_atributo(n) -> str:
    partes = []
    while isinstance(n, ast.Attribute):
        partes.append(n.attr)
        n = n.value
    if isinstance(n, ast.Name):
        partes.append(n.id)
    return ".".join(reversed(partes))


def _tem_kw(call: ast.Call, nome: str) -> bool:
    return any(k.arg == nome for k in call.keywords)


def _kw_valor(call: ast.Call, nome: str):
    for k in call.keywords:
        if k.arg == nome:
            return k.value
    return None


def _dinamico(n) -> bool:
    """Texto montado em tempo de execução (f-string, concatenação, .format, %)."""
    if isinstance(n, ast.JoinedStr):
        return any(isinstance(v, ast.FormattedValue) for v in n.values)
    if isinstance(n, ast.BinOp) and isinstance(n.op, (ast.Add, ast.Mod)):
        return not (isinstance(n.left, ast.Constant) and isinstance(n.right, ast.Constant))
    if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "format":
        return True
    return False


def _texto_constante(n) -> str:
    if isinstance(n, ast.Constant) and isinstance(n.value, str):
        return n.value
    if isinstance(n, ast.JoinedStr):
        return "".join(v.value for v in n.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    if isinstance(n, ast.BinOp):
        return _texto_constante(n.left) + _texto_constante(n.right)
    return ""


def varrer_python(src: str, arquivo: str = "?") -> list[Achado]:
    try:
        arv = ast.parse(src)
    except SyntaxError as e:
        return [Achado(arquivo, e.lineno or 0, "medio", "sintaxe", "arquivo não pôde ser analisado")]
    out: list[Achado] = []
    for n in ast.walk(arv):
        if isinstance(n, ast.Call):
            nome = _nome_atributo(n.func) if isinstance(n.func, ast.Attribute) else (n.func.id if isinstance(n.func, ast.Name) else "")
            base = nome.split(".")[-1]
            ln = n.lineno
            if nome in _PERIGOSAS and isinstance(n.func, ast.Name):
                if n.args and not isinstance(n.args[0], ast.Constant):
                    out.append(Achado(arquivo, ln, _PERIGOSAS[nome], "execucao-dinamica", f"{nome}() com argumento variável"))
            if nome in ("pickle.load", "pickle.loads", "marshal.load", "marshal.loads", "shelve.open", "dill.load", "dill.loads"):
                out.append(Achado(arquivo, ln, "alto", "desserializacao", f"{nome}() lê objetos arbitrários"))
            if nome in ("yaml.load",) and not _tem_kw(n, "Loader"):
                out.append(Achado(arquivo, ln, "alto", "desserializacao", "yaml.load sem Loader seguro"))
            if nome in ("os.system", "os.popen") or nome.startswith("subprocess."):
                shell = _kw_valor(n, "shell")
                sev = "alto" if (isinstance(shell, ast.Constant) and shell.value is True) or nome.startswith("os.") else "medio"
                out.append(Achado(arquivo, ln, sev, "comando", f"{nome}() executa programa externo"))
            if base in _REDE and (nome.startswith(("requests.", "httpx.", "urllib")) or nome.endswith(".urlopen")):
                if not _tem_kw(n, "timeout"):
                    out.append(Achado(arquivo, ln, "medio", "rede-sem-timeout", f"{nome}() sem timeout"))
                v = _kw_valor(n, "verify")
                if isinstance(v, ast.Constant) and v.value is False:
                    out.append(Achado(arquivo, ln, "alto", "tls-desligado", f"{nome}() com verify=False"))
                if n.args and _dinamico(n.args[0]):
                    out.append(Achado(arquivo, ln, "baixo", "ssrf-possivel", f"{nome}() com URL montada; confira se o domínio é fixo"))
            if base in ("execute", "executemany", "executescript") and n.args:
                a0 = n.args[0]
                if _dinamico(a0) and _SQL_RX.search(_texto_constante(a0) or ""):
                    out.append(Achado(arquivo, ln, "alto", "sql-injection", f"{nome}() com SQL montado por texto"))
            if nome == "open" and n.args and not isinstance(n.args[0], ast.Constant):
                out.append(Achado(arquivo, ln, "baixo", "path-traversal", "open() com caminho variável; valide o nome do arquivo"))
            if base == "file_uploader":
                out.append(Achado(arquivo, ln, "baixo", "upload", "upload de arquivo: confira tipo, tamanho e que nunca é executado"))
            if base in ("markdown", "html", "write", "caption") and _kw_valor(n, "unsafe_allow_html") is not None:
                v = _kw_valor(n, "unsafe_allow_html")
                if isinstance(v, ast.Constant) and v.value is True and n.args and _dinamico(n.args[0]):
                    fonte = ast.unparse(n.args[0]) if hasattr(ast, "unparse") else ""
                    if not re.search(r"escape|_e\(|html\.escape|tema\.|_kpi|_msg|_chip|_linha|_titulo|_grade", fonte):
                        out.append(Achado(arquivo, ln, "baixo", "xss-possivel", "HTML dinâmico sem escape visível; confirme a origem dos dados"))
    linhas = src.splitlines()
    return [a for a in out if not (0 < a.linha <= len(linhas) and "seg-ok" in linhas[a.linha - 1])]


def checar_gitignore(texto: str) -> list[Achado]:
    """Garante que arquivos sensíveis continuam fora do GitHub."""
    linhas = {l.strip() for l in texto.splitlines() if l.strip() and not l.strip().startswith("#")}
    exigidos = {".streamlit/secrets.toml": "critico", ".env": "alto", "*.db": "alto", "*.pem": "alto", "*.key": "alto", "*.log": "baixo"}
    out = []
    for item, sev in exigidos.items():
        equivalentes = {item, "**/" + item, ".streamlit/secrets*", "**/secrets.toml"} if "secrets" in item else {item, "**/" + item}
        if not (linhas & equivalentes):
            out.append(Achado(".gitignore", 0, sev, "gitignore", f"falta ignorar {item}"))
    return out


def _arquivos(raiz: str):
    for d, subs, nomes in os.walk(raiz):
        subs[:] = [s for s in subs if s not in _IGNORAR_DIRS]
        for nome in nomes:
            if nome.endswith(_TEXTO) or nome in (".gitignore", "Dockerfile"):
                yield os.path.join(d, nome)


def arquivos_sensiveis_rastreados(raiz: str) -> list[Achado]:
    """Arquivos que NÃO deveriam estar no repositório (segredos reais, bancos, chaves)."""
    out = []
    ruins = (re.compile(r"(^|/)secrets\.toml$"), re.compile(r"(^|/)\.env(\..+)?$"), re.compile(r"\.(pem|key|p12|pfx|db|sqlite3?)$"),
             re.compile(r"client_secret.*\.json$"), re.compile(r"service-account.*\.json$"))
    exemplos = re.compile(r"\.(example|sample)$|\.env\.example$")
    for caminho in _arquivos_todos(raiz):
        rel = os.path.relpath(caminho, raiz).replace(os.sep, "/")
        if exemplos.search(rel):
            continue
        if any(r.search(rel) for r in ruins):
            out.append(Achado(rel, 0, "critico" if "secret" in rel or rel.endswith((".pem", ".key", ".env")) else "alto",
                              "arquivo-sensivel", "arquivo que não deve ficar no repositório"))
    return out


def _arquivos_todos(raiz: str):
    for d, subs, nomes in os.walk(raiz):
        subs[:] = [s for s in subs if s not in _IGNORAR_DIRS]
        for nome in nomes:
            yield os.path.join(d, nome)


def historico_git(raiz: str, limite: int = 400) -> list[Achado]:
    """Procura segredos no histórico (git log -p), se houver um repositório git disponível. Sem git, devolve vazio."""
    if not os.path.isdir(os.path.join(raiz, ".git")):
        return []
    try:
        p = subprocess.run(["git", "-C", raiz, "log", "-p", f"-n{int(limite)}", "--no-color"], capture_output=True, text=True, timeout=60)  # seg-ok: comando fixo, sem shell e sem texto do usuário
    except Exception:
        return []
    out = []
    for a in varrer_segredos(p.stdout or "", "histórico-git"):
        out.append(Achado(a.arquivo, 0, a.severidade, "segredo-no-historico", a.detalhe))
    return out


def varrer_repositorio(raiz: str, incluir_testes: bool = False) -> list[Achado]:
    out: list[Achado] = []
    for caminho in _arquivos(raiz):
        rel = os.path.relpath(caminho, raiz).replace(os.sep, "/")
        if not incluir_testes and rel.startswith("tests/"):
            continue
        if rel.endswith((".example", ".md")):
            continue
        try:
            with open(caminho, encoding="utf-8", errors="ignore") as f:
                txt = f.read()
        except OSError:
            continue
        if rel == ".gitignore":
            out += checar_gitignore(txt)
            continue
        out += varrer_segredos(txt, rel)
        if rel.endswith(".py"):
            out += varrer_python(txt, rel)
    ign = os.path.join(raiz, ".gitignore")
    if os.path.isfile(ign):
        pass
    else:
        out.append(Achado(".gitignore", 0, "critico", "gitignore", "arquivo .gitignore não existe"))
    out += arquivos_sensiveis_rastreados(raiz)
    return out


def resumo(achados: list[Achado]) -> dict:
    por_sev = {s: 0 for s in SEVERIDADES}
    for a in achados:
        por_sev[a.severidade] = por_sev.get(a.severidade, 0) + 1
    return por_sev
