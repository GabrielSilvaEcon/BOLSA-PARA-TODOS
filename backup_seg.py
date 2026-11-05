"""Backup cifrado e restauração testada (Passo 22).

Um backup só é considerado bom depois de restaurado e conferido: `testar_restauracao()` faz o ciclo inteiro (copia, cifra,
decifra, restaura em arquivo novo, confere integridade e contagem de linhas) e devolve o resultado.
A cifra é Fernet (AES-128-CBC + HMAC-SHA256, biblioteca `cryptography`, já instalada junto com o Authlib). A chave vem dos
secrets (`[backup] chave`) e nunca é gravada junto do arquivo. Sem a chave não há como abrir o backup: guarde-a à parte.
No modo Supabase o banco em si é copiado pelo próprio Supabase (painel > Database > Backups); aqui sai só o resumo das contas.
"""
from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
from pathlib import Path

import seguranca as seg

TABELAS_ESPERADAS = ("schema_versao", "contas", "sessoes", "tokens", "tentativas", "auditoria", "erros", "perfis")


_CONTAR = {
    "schema_versao": "select count(*) from schema_versao", "contas": "select count(*) from contas",
    "sessoes": "select count(*) from sessoes", "tokens": "select count(*) from tokens",
    "tentativas": "select count(*) from tentativas", "auditoria": "select count(*) from auditoria",
    "erros": "select count(*) from erros", "perfis": "select count(*) from perfis",
}


class ErroBackup(Exception):
    pass


def nova_chave() -> str:
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode()


def _fernet(chave: str):
    from cryptography.fernet import Fernet
    try:
        return Fernet(chave.encode() if isinstance(chave, str) else chave)
    except Exception as e:
        raise ErroBackup("chave de backup inválida") from e


def cifrar(dados: bytes, chave: str) -> bytes:
    return _fernet(chave).encrypt(dados)


def decifrar(dados: bytes, chave: str) -> bytes:
    from cryptography.fernet import InvalidToken
    try:
        return _fernet(chave).decrypt(dados)
    except InvalidToken as e:
        raise ErroBackup("chave errada ou arquivo corrompido/adulterado") from e


def impressao(dados: bytes) -> str:
    """SHA-256 do conteúdo: anote junto do arquivo para provar que não foi trocado."""
    return hashlib.sha256(dados).hexdigest()


def verificar_sqlite(caminho: str | Path) -> dict:
    """Confere integridade e conteúdo de um arquivo SQLite. Levanta ErroBackup se não servir."""
    caminho = str(caminho)
    try:
        con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)
    except sqlite3.Error as e:
        raise ErroBackup("não foi possível abrir o arquivo") from e
    try:
        if con.execute("pragma integrity_check").fetchone()[0] != "ok":
            raise ErroBackup("o arquivo falhou na verificação de integridade")
        tabelas = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        faltam = [t for t in TABELAS_ESPERADAS if t not in tabelas]
        if faltam:
            raise ErroBackup("faltam tabelas: " + ", ".join(faltam))
        return {t: con.execute(_CONTAR[t]).fetchone()[0] for t in TABELAS_ESPERADAS}
    except sqlite3.Error as e:
        raise ErroBackup("arquivo SQLite inválido") from e
    finally:
        con.close()


def criar_backup_cifrado(origem_sqlite: str | Path, chave: str) -> tuple[bytes, str]:
    """(bytes cifrados, impressão SHA-256 do arquivo cifrado). Confere o banco antes de cifrar."""
    verificar_sqlite(origem_sqlite)
    bruto = Path(origem_sqlite).read_bytes()
    cif = cifrar(bruto, chave)
    return cif, impressao(cif)


def restaurar(cifrado: bytes, chave: str, destino: str | Path, impressao_esperada: str | None = None,
              sobrescrever: bool = False) -> dict:
    """Decifra, confere e grava em `destino` (arquivo NOVO por padrão: nunca sobrescreve o banco em uso sem pedido explícito)."""
    if impressao_esperada and not _igual(impressao(cifrado), impressao_esperada):
        raise ErroBackup("a impressão digital não confere: o arquivo foi alterado")
    destino = Path(destino)
    if destino.exists() and not sobrescrever:
        raise ErroBackup("o destino já existe; escolha outro nome ou confirme a substituição")
    bruto = decifrar(cifrado, chave)
    destino.parent.mkdir(parents=True, exist_ok=True)
    tmp = destino.with_suffix(destino.suffix + ".tmp")
    tmp.write_bytes(bruto)
    try:
        contagem = verificar_sqlite(tmp)
    except ErroBackup:
        tmp.unlink(missing_ok=True)
        raise
    os.replace(tmp, destino)
    return contagem


def _igual(a: str, b: str) -> bool:
    import hmac
    return hmac.compare_digest(str(a).lower(), str(b).lower())


def backup_json_cifrado(dados: dict, chave: str) -> tuple[bytes, str]:
    """Resumo administrativo (contas sem senhas, auditoria, erros) cifrado; serve também no modo Supabase."""
    bruto = json.dumps(dados, ensure_ascii=False, default=str).encode("utf-8")
    cif = cifrar(bruto, chave)
    return cif, impressao(cif)


def testar_restauracao(origem_sqlite: str | Path, chave: str | None = None) -> dict:
    """Ciclo completo em pasta temporária. Resultado: {'ok': bool, 'etapas': [...], 'contagem': {...}}."""
    etapas: list[tuple[str, bool, str]] = []
    chave = chave or nova_chave()       # sem chave nos secrets, o teste usa uma chave descartável
    try:
        antes = verificar_sqlite(origem_sqlite)
        etapas.append(("Banco de origem íntegro", True, f"{sum(antes.values())} linhas em {len(antes)} tabelas"))
        cif, imp = criar_backup_cifrado(origem_sqlite, chave)
        etapas.append(("Backup cifrado criado", True, f"{len(cif)} bytes, SHA-256 {imp[:12]}…"))
        with tempfile.TemporaryDirectory() as d:
            alvo = Path(d) / "restaurado.db"
            depois = restaurar(cif, chave, alvo, imp)
            etapas.append(("Restauração em arquivo novo", True, "arquivo aberto e íntegro"))
            igual = depois == antes
            etapas.append(("Contagem de linhas confere", igual, "iguais ao original" if igual else f"diferem: {antes} x {depois}"))
            try:
                restaurar(cif[:-4] + b"AAAA", chave, Path(d) / "adulterado.db")
                etapas.append(("Arquivo adulterado é recusado", False, "aceitou um arquivo alterado"))
            except ErroBackup:
                etapas.append(("Arquivo adulterado é recusado", True, "recusado como esperado"))
        ok = all(e[1] for e in etapas)
        return {"ok": ok, "etapas": etapas, "contagem": antes, "quando": seg.iso()}
    except ErroBackup as e:
        etapas.append(("Falha no teste", False, str(e)))
        return {"ok": False, "etapas": etapas, "contagem": {}, "quando": seg.iso()}
