"""Camada de acesso a dados das contas (Passo 21). SQLite local ou Supabase (PostgREST), com o mesmo comportamento.

Regras desta camada:
- Nomes de tabela e coluna só passam se existirem no esquema (TABELAS); valores nunca entram no texto do SQL
  (SQLite usa parâmetros "?") nem montados à mão na URL (Supabase recebe `params=`, codificados pela biblioteca).
  Por isso e-mails ou textos com aspas, "&", "--" ou "%" não alteram a consulta.
- Dados privados só saem por funções que recebem o Ator (quem está logado) e conferem a posse AQUI, na camada de
  dados, e não só na tela: ler_dados/gravar_dados/apagar_dados/sessoes_do_ator/atividades_do_ator.
- Funções sis_* são as do fluxo de credenciais (cadastro, login, tokens), que acontecem antes de existir um Ator.
  Elas só devem ser chamadas por contas.py.
- Funções admin_* exigem permissão, nunca devolvem senha_hash, tokens nem dados de carteira/perfil.
- Segredos (chave do Supabase, senhas, tokens) nunca vão para log: erros passam por seguranca.limpar_para_log.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

import permissoes as perm
import seguranca as seg

SCHEMA_VERSAO = 1


class ErroBanco(Exception):
    pass


class Duplicado(ErroBanco):
    pass


class SemPermissao(PermissionError):
    pass


class Ator(NamedTuple):
    """Quem está agindo. Só se constrói a partir de uma sessão já validada (contas.ator_de)."""
    id: str
    email: str
    papel: str = "usuario"


# ------------------------------------------------------------------ esquema (uma definição gera SQLite e Postgres)
# {AUTO} = chave numérica automática; {JSON} = jsonb no Postgres e texto no SQLite.
TABELAS: dict[str, list[str]] = {
    "schema_versao": [
        "versao integer primary key", "aplicada_em text not null", "descricao text not null default ''"],
    "contas": [
        "id text primary key",
        "email text not null unique",
        "nome text not null default ''",
        "senha_hash text",
        "papel text not null default 'usuario' check (papel in ('usuario','suporte','admin'))",
        "status text not null default 'ativa' check (status in ('ativa','suspensa','pendente'))",
        "email_verificado integer not null default 0",
        "provedor text not null default 'senha'",
        "criado_em text not null",
        "ultimo_login text",
        "aceite_em text"],
    "sessoes": [
        "token_hash text primary key",
        "conta_id text not null references contas(id) on delete cascade",
        "criado_em text not null", "ultimo_uso text not null", "expira_em text not null",
        "ocioso_s integer not null default 3600", "revogada integer not null default 0"],
    "tokens": [
        "token_hash text primary key",
        "conta_id text not null references contas(id) on delete cascade",
        "tipo text not null check (tipo in ('verificar','redefinir'))",
        "criado_em text not null", "expira_em text not null", "usado integer not null default 0"],
    "tentativas": [
        "id {AUTO}", "chave text not null", "tipo text not null", "quando text not null"],
    "auditoria": [
        "id {AUTO}", "quando text not null", "ator_id text", "acao text not null", "alvo_id text",
        "detalhes text not null default ''"],
    "erros": [
        "id {AUTO}", "quando text not null", "modulo text not null default ''", "tipo text not null default ''",
        "mensagem text not null default ''"],
    "perfis": [
        "email text primary key", "dados {JSON}", "atualizado text"],
}
INDICES = [
    "create index if not exists ix_contas_status on contas (status)",
    "create index if not exists ix_contas_criado on contas (criado_em)",
    "create index if not exists ix_sessoes_conta on sessoes (conta_id)",
    "create index if not exists ix_sessoes_expira on sessoes (expira_em)",
    "create index if not exists ix_tokens_conta on tokens (conta_id)",
    "create index if not exists ix_tentativas on tentativas (chave, tipo, quando)",
    "create index if not exists ix_auditoria_ator on auditoria (ator_id, quando)",
    "create index if not exists ix_auditoria_quando on auditoria (quando)",
    "create index if not exists ix_erros_quando on erros (quando)",
]
COLUNAS = {t: [c.split()[0] for c in cols] for t, cols in TABELAS.items()}
PUBLICAS_CONTA = ["id", "email", "nome", "papel", "status", "email_verificado", "provedor", "criado_em",
                  "ultimo_login", "aceite_em"]   # tudo menos senha_hash


def _ddl(dialeto: str) -> list[str]:
    auto = "integer primary key autoincrement" if dialeto == "sqlite" else "bigint generated always as identity primary key"
    js = "text" if dialeto == "sqlite" else "jsonb"
    out = []
    for t, cols in TABELAS.items():
        c = [x.replace("{AUTO}", auto).replace("{JSON}", js) for x in cols]
        if t == "perfis" and dialeto == "sqlite":
            c[0] = "email text primary key references contas(email) on delete cascade"
        out.append(f"create table if not exists {t} (\n  " + ",\n  ".join(c) + "\n)")
    return out + INDICES


def sql_supabase() -> str:
    """Script para colar no SQL Editor do Supabase. É idempotente: pode ser executado de novo sem estragar nada."""
    partes = [
        "-- Bússola B3 · Passo 21 · contas, sessões, auditoria. Seguro para rodar mais de uma vez.",
        "begin;",
        *[s + ";" for s in _ddl("postgres")],
        "-- contas para quem já usava o app (entrava com Google): nada se perde",
        "insert into contas (id, email, nome, papel, status, email_verificado, provedor, criado_em)\n"
        "select gen_random_uuid()::text, p.email, split_part(p.email, '@', 1), 'usuario', 'ativa',\n"
        "       case when p.email like '%@%' then 1 else 0 end, 'google',\n"
        "       to_char(now() at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"')\n"
        "from perfis p on conflict (email) do nothing;",
        "-- integridade: perfil sempre pertence a uma conta; apagar a conta apaga o perfil",
        "do $$ begin\n  alter table perfis add constraint perfis_email_fk foreign key (email) "
        "references contas (email) on delete cascade;\nexception when duplicate_object then null; end $$;",
        "-- proteção: tabelas fechadas para a chave pública; só a chave secreta do servidor entra",
        *[f"alter table {t} enable row level security;" for t in TABELAS],
        "insert into schema_versao (versao, aplicada_em, descricao) values "
        f"({SCHEMA_VERSAO}, to_char(now() at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"'), "
        "'Passo 21: contas, sessões, tokens, auditoria') on conflict (versao) do nothing;",
        "commit;",
    ]
    return "\n".join(partes) + "\n"


# ------------------------------------------------------------------ configuração
_caminho_sqlite: Path = Path(__file__).with_name("usuarios.db")
_forcar_sqlite = False
_pronto_cache: dict = {}


def usar_sqlite(caminho: str | Path | None) -> None:
    """Força o SQLite (testes e uso local). caminho=None volta ao automático."""
    global _caminho_sqlite, _forcar_sqlite
    _pronto_cache.clear()
    if caminho is None:
        _forcar_sqlite = False
        _caminho_sqlite = Path(__file__).with_name("usuarios.db")
    else:
        _forcar_sqlite, _caminho_sqlite = True, Path(caminho)


def secrets_secao(nome: str) -> dict:
    """Seção dos secrets do Streamlit como dict (vazio se não existir). Não levanta erro."""
    try:
        import streamlit as st
        return dict(st.secrets[nome])
    except Exception:
        return {}


def _supabase():
    """(url, chave) do Supabase nos secrets, com a URL corrigida se vier sem https:// ou com /rest/v1 no fim."""
    if _forcar_sqlite:
        return None
    cfg = secrets_secao("supabase")
    try:
        url = str(cfg["url"]).strip().strip("\"'").rstrip("/")
        key = str(cfg["key"]).strip().strip("\"'")
    except Exception:
        return None
    if "=" in url:
        url = url.rsplit("=", 1)[1].strip().strip("\"'")
    if "=" in key and not key.startswith(("sb_", "eyJ")):
        key = key.rsplit("=", 1)[1].strip().strip("\"'")
    if url.endswith("/rest/v1"):
        url = url[: -len("/rest/v1")]
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    if "." not in url.split("//", 1)[1]:
        url += ".supabase.co"
    return url, key


def _cab(key: str) -> dict:
    """Chaves novas (sb_secret_...) vão só em apikey; a service_role antiga (JWT) também em Authorization."""
    h = {"apikey": key}
    if key.startswith("eyJ"):
        h["Authorization"] = f"Bearer {key}"
    return h


def tipo_de_chave() -> str:
    """'secreta', 'publica' ou 'desconhecida': a pública não pode ser usada aqui (as tabelas ficam fechadas a ela)."""
    sb = _supabase()
    if not sb:
        return "desconhecida"
    k = sb[1]
    if k.startswith("sb_secret_"):
        return "secreta"
    if k.startswith("sb_publishable_"):
        return "publica"
    if k.startswith("eyJ"):
        try:
            import base64
            p = k.split(".")[1]
            papel = json.loads(base64.urlsafe_b64decode(p + "=" * (-len(p) % 4))).get("role")
            return "secreta" if papel == "service_role" else "publica" if papel == "anon" else "desconhecida"
        except Exception:
            return "desconhecida"
    return "desconhecida"


def backend() -> str:
    return "supabase" if _supabase() else "sqlite"


# ------------------------------------------------------------------ acesso genérico (privado)
_OPS = {"eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "contem": "like"}


def _conferir(tabela: str, cols=()):
    if tabela not in TABELAS:
        raise ErroBanco("tabela desconhecida")
    for c in cols:
        if c not in COLUNAS[tabela]:
            raise ErroBanco("coluna desconhecida")


def _filtros_norm(tabela: str, filtros: dict | None):
    out = []
    for col, v in (filtros or {}).items():
        op, val = (v if isinstance(v, tuple) else ("eq", v))
        if op not in _OPS:
            raise ErroBanco("operador desconhecido")
        _conferir(tabela, [col])
        out.append((col, op, val))
    return out


def _con():
    _caminho_sqlite.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(_caminho_sqlite, timeout=10)
    con.row_factory = sqlite3.Row
    con.execute("pragma foreign_keys = on")
    return con


def _like(txt: str) -> str:
    return "%" + str(txt).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def _rest(metodo: str, tabela: str, params=None, corpo=None, prefer: str | None = None, contar: bool = False):
    import requests
    sb = _supabase()
    if not sb:
        raise ErroBanco("Supabase não configurado")
    url, key = sb
    h = {**_cab(key), "Content-Type": "application/json"}
    if prefer:
        h["Prefer"] = prefer
    if contar:
        h["Prefer"] = "count=exact"
        h["Range"] = "0-0"
    r = requests.request(metodo, f"{url}/rest/v1/{tabela}", params=params, json=corpo, headers=h, timeout=10)
    if r.status_code == 409 or (r.status_code == 400 and "23505" in (r.text or "")):
        raise Duplicado("registro já existe")
    if r.status_code >= 400:
        raise ErroBanco(f"HTTP {r.status_code}")
    return r


def _params(tabela, filtros):
    p = []
    for col, op, val in _filtros_norm(tabela, filtros):
        if op == "contem":
            v = "*" + str(val).replace("*", "") + "*"
            p.append((col, "ilike." + v))
        else:
            p.append((col, f"{op}.{val}"))
    return p


def _selecionar(tabela: str, filtros=None, colunas=None, ordem: str | None = None, limite: int | None = None,
                desc: bool = False) -> list[dict]:
    _conferir(tabela)
    cols = list(colunas or COLUNAS[tabela])
    _conferir(tabela, cols)
    if ordem:
        _conferir(tabela, [ordem])
    if backend() == "supabase":
        p = [("select", ",".join(cols))] + _params(tabela, filtros)
        if ordem:
            p.append(("order", f"{ordem}.{'desc' if desc else 'asc'}"))
        if limite:
            p.append(("limit", str(int(limite))))
        return _rest("GET", tabela, params=p).json()
    f = _filtros_norm(tabela, filtros)
    sql = f"select {', '.join(cols)} from {tabela}"
    args = []
    if f:
        sql += " where " + " and ".join(
            f"{c} like ? escape '\\'" if op == "contem" else f"{c} {_OPS[op]} ?" for c, op, _ in f)
        args = [_like(v) if op == "contem" else v for _, op, v in f]
    if ordem:
        sql += f" order by {ordem} {'desc' if desc else 'asc'}"
    if limite:
        sql += f" limit {int(limite)}"
    with _con() as con:
        return [dict(r) for r in con.execute(sql, args).fetchall()]


def _contar(tabela: str, filtros=None) -> int:
    _conferir(tabela)
    if backend() == "supabase":
        p = [("select", COLUNAS[tabela][0])] + _params(tabela, filtros)
        r = _rest("GET", tabela, params=p, contar=True)
        cr = r.headers.get("Content-Range", "")
        return int(cr.rsplit("/", 1)[1]) if "/" in cr and cr.rsplit("/", 1)[1].isdigit() else len(r.json())
    f = _filtros_norm(tabela, filtros)
    sql = f"select count(*) from {tabela}"
    if f:
        sql += " where " + " and ".join(
            f"{c} like ? escape '\\'" if op == "contem" else f"{c} {_OPS[op]} ?" for c, op, _ in f)
    with _con() as con:
        return int(con.execute(sql, [_like(v) if op == "contem" else v for _, op, v in f]).fetchone()[0])


def _inserir(tabela: str, linha: dict) -> None:
    _conferir(tabela, linha.keys())
    if backend() == "supabase":
        _rest("POST", tabela, corpo=linha, prefer="return=minimal")
        return
    cols = list(linha)
    try:
        with _con() as con:
            con.execute(f"insert into {tabela} ({', '.join(cols)}) values ({', '.join('?' * len(cols))})",
                        [linha[c] for c in cols])
    except sqlite3.IntegrityError as e:
        if "UNIQUE" in str(e).upper() or "PRIMARY" in str(e).upper():
            raise Duplicado("registro já existe") from e
        raise ErroBanco(e.__class__.__name__) from e


def _atualizar(tabela: str, filtros: dict, campos: dict) -> None:
    _conferir(tabela, campos.keys())
    if not filtros:
        raise ErroBanco("atualização sem filtro não é permitida")
    if backend() == "supabase":
        _rest("PATCH", tabela, params=_params(tabela, filtros), corpo=campos, prefer="return=minimal")
        return
    f = _filtros_norm(tabela, filtros)
    sql = (f"update {tabela} set {', '.join(c + ' = ?' for c in campos)} where "
           + " and ".join(f"{c} {_OPS[op]} ?" for c, op, _ in f))
    with _con() as con:
        con.execute(sql, [*campos.values(), *[v for _, _, v in f]])


def _apagar(tabela: str, filtros: dict) -> None:
    if not filtros:
        raise ErroBanco("apagar sem filtro não é permitido")
    if backend() == "supabase":
        _rest("DELETE", tabela, params=_params(tabela, filtros), prefer="return=minimal")
        return
    f = _filtros_norm(tabela, filtros)
    sql = f"delete from {tabela} where " + " and ".join(f"{c} {_OPS[op]} ?" for c, op, _ in f)
    with _con() as con:
        con.execute(sql, [v for _, _, v in f])


# ------------------------------------------------------------------ migração e prontidão
def migrar_sqlite() -> None:
    """Cria o que falta no SQLite (seguro de repetir) e traz para 'contas' quem já tinha perfil salvo."""
    with _con() as con:
        for s in _ddl("sqlite"):
            con.execute(s)
        con.execute("insert or ignore into contas (id, email, nome, papel, status, email_verificado, provedor, criado_em) "
                    "select lower(hex(randomblob(16))), email, substr(email, 1, instr(email || '@', '@') - 1), 'usuario', "
                    "'ativa', case when email like '%@%' then 1 else 0 end, 'google', "
                    "strftime('%Y-%m-%dT%H:%M:%fZ','now') from perfis")
        con.execute("insert or ignore into schema_versao (versao, aplicada_em, descricao) values (?,?,?)",
                    (SCHEMA_VERSAO, seg.iso(), "Passo 21: contas, sessões, tokens, auditoria"))


def pronto(forcar: bool = False) -> tuple[bool, str]:
    """(ok, motivo). No Supabase, as tabelas precisam ter sido criadas com o script SQL; resultado guardado por 60 s."""
    chave = (backend(), str(_caminho_sqlite))
    agora = seg.agora().timestamp()
    c = _pronto_cache.get(chave)
    if c and not forcar and agora - c[0] < 60:
        return c[1], c[2]
    try:
        if backend() == "sqlite":
            migrar_sqlite()
            res = (True, "")
        else:
            v = _selecionar("schema_versao", colunas=["versao"], ordem="versao", desc=True, limite=1)
            res = (True, "") if v and v[0]["versao"] >= SCHEMA_VERSAO else (False, "O banco ainda não recebeu a atualização do Passo 21 (script SQL).")
            if res[0] and tipo_de_chave() == "publica":
                res = (False, "A chave do Supabase nos secrets é a pública; use a chave secreta.")
    except Exception as e:
        res = (False, f"Banco indisponível ({e.__class__.__name__}).")
    _pronto_cache[chave] = (agora, *res)
    return res


# ------------------------------------------------------------------ erros e auditoria
def registrar_erro(modulo: str, erro) -> None:
    """Guarda o tipo e uma mensagem limpa (sem e-mail, senha ou token). Nunca levanta erro."""
    try:
        tipo = erro.__class__.__name__ if isinstance(erro, BaseException) else "Aviso"
        _inserir("erros", {"quando": seg.iso(), "modulo": str(modulo)[:60], "tipo": tipo[:60],
                           "mensagem": seg.limpar_para_log(erro, 300)})
    except Exception:
        pass


ACOES_VISIVEIS_AO_USUARIO = ("conta.criada", "conta.verificada", "login", "login.google", "logout", "senha.alterada",
                             "senha.redefinida", "perfil.nome", "sessoes.encerradas", "dados.exportados",
                             "conta.suspensa", "conta.reativada", "preferencias.salvas")


def auditar(ator_id: str | None, acao: str, alvo_id: str | None = None, detalhes: dict | None = None,
            obrigatorio: bool = False) -> bool:
    """Registra um evento. Detalhes passam pela limpeza (sem senha/token/e-mail). Com obrigatorio=True a falha
    interrompe a operação (usado nas ações administrativas: sem registro, sem ação)."""
    try:
        det = seg.limpar_para_log(json.dumps(detalhes or {}, ensure_ascii=False, default=str), 400)
        _inserir("auditoria", {"quando": seg.iso(), "ator_id": ator_id, "acao": str(acao)[:60], "alvo_id": alvo_id,
                               "detalhes": det})
        return True
    except Exception as e:
        if obrigatorio:
            raise ErroBanco("não foi possível registrar a auditoria") from e
        return False


# ------------------------------------------------------------------ perfis (dados privados): posse conferida aqui
def exigir_dono(ator: Ator | None, email: str) -> None:
    if not ator or not ator.email or ator.email != seg.normalizar_email(email):
        raise SemPermissao("Esses dados pertencem a outra conta.")


def ler_dados(ator: Ator | None, email: str) -> dict:
    exigir_dono(ator, email)
    r = _selecionar("perfis", {"email": ator.email}, ["dados"], limite=1)
    if not r:
        return {}
    d = r[0]["dados"]
    return json.loads(d) if isinstance(d, str) else (d or {})


def gravar_dados(ator: Ator | None, email: str, dados: dict) -> None:
    exigir_dono(ator, email)
    agora = seg.iso()
    if backend() == "supabase":
        _rest("POST", "perfis", params=[("on_conflict", "email")],
              corpo={"email": ator.email, "dados": dados, "atualizado": agora},
              prefer="resolution=merge-duplicates,return=minimal")
        return
    txt = json.dumps(dados, ensure_ascii=False)
    with _con() as con:
        con.execute("insert into perfis (email, dados, atualizado) values (?,?,?) on conflict(email) do update set "
                    "dados=excluded.dados, atualizado=excluded.atualizado", (ator.email, txt, agora))


def apagar_dados(ator: Ator | None, email: str) -> None:
    exigir_dono(ator, email)
    _apagar("perfis", {"email": ator.email})


def sessoes_do_ator(ator: Ator | None) -> list[dict]:
    """Sessões de senha da própria conta (sem o token)."""
    if not ator:
        raise SemPermissao("Faça login.")
    return _selecionar("sessoes", {"conta_id": ator.id, "revogada": 0}, ["criado_em", "ultimo_uso", "expira_em"],
                       ordem="ultimo_uso", desc=True, limite=50)


def atividades_do_ator(ator: Ator | None, limite: int = 40) -> list[dict]:
    """Histórico da própria conta: só eventos em que ela foi o ator e que são do tipo visível."""
    if not ator:
        raise SemPermissao("Faça login.")
    linhas = _selecionar("auditoria", {"ator_id": ator.id}, ["quando", "acao"], ordem="quando", desc=True,
                         limite=limite * 3)
    return [x for x in linhas if x["acao"] in ACOES_VISIVEIS_AO_USUARIO][:limite]


# ------------------------------------------------------------------ fluxo de credenciais (antes do login)
def sis_conta_por_email(email: str, com_senha: bool = False) -> dict | None:
    r = _selecionar("contas", {"email": seg.normalizar_email(email)},
                    PUBLICAS_CONTA + (["senha_hash"] if com_senha else []), limite=1)
    return r[0] if r else None


def sis_conta_por_id(conta_id: str, com_senha: bool = False) -> dict | None:
    r = _selecionar("contas", {"id": str(conta_id)}, PUBLICAS_CONTA + (["senha_hash"] if com_senha else []), limite=1)
    return r[0] if r else None


def sis_criar_conta(conta: dict) -> None:
    _inserir("contas", conta)


def sis_atualizar_conta(conta_id: str, campos: dict) -> None:
    if "id" in campos:
        raise ErroBanco("o identificador não muda")
    _atualizar("contas", {"id": conta_id}, campos)


def sis_apagar_conta(conta_id: str, email: str) -> None:
    _apagar("perfis", {"email": email})
    _apagar("sessoes", {"conta_id": conta_id})
    _apagar("tokens", {"conta_id": conta_id})
    _apagar("contas", {"id": conta_id})


def sis_gravar_token(linha: dict) -> None:
    _inserir("tokens", linha)


def sis_token(token_hash: str) -> dict | None:
    r = _selecionar("tokens", {"token_hash": token_hash}, limite=1)
    return r[0] if r else None


def sis_usar_token(token_hash: str) -> None:
    _atualizar("tokens", {"token_hash": token_hash}, {"usado": 1})


def sis_invalidar_tokens(conta_id: str, tipo: str) -> None:
    _atualizar("tokens", {"conta_id": conta_id, "tipo": tipo, "usado": 0}, {"usado": 1})


def sis_gravar_sessao(linha: dict) -> None:
    _inserir("sessoes", linha)


def sis_sessao(token_hash: str) -> dict | None:
    r = _selecionar("sessoes", {"token_hash": token_hash}, limite=1)
    return r[0] if r else None


def sis_tocar_sessao(token_hash: str, quando: str) -> None:
    _atualizar("sessoes", {"token_hash": token_hash}, {"ultimo_uso": quando})


def sis_revogar_sessao(token_hash: str) -> None:
    _atualizar("sessoes", {"token_hash": token_hash}, {"revogada": 1})


def sis_revogar_sessoes_da_conta(conta_id: str, exceto_hash: str | None = None) -> None:
    if exceto_hash:
        _atualizar("sessoes", {"conta_id": conta_id, "revogada": 0, "token_hash": ("neq", exceto_hash)}, {"revogada": 1})
    else:
        _atualizar("sessoes", {"conta_id": conta_id, "revogada": 0}, {"revogada": 1})


# limite de tentativas ----------------------------------------------------------------
def tentativa_registrar(chave: str, tipo: str) -> None:
    try:
        _inserir("tentativas", {"chave": chave, "tipo": tipo, "quando": seg.iso()})
    except Exception as e:
        registrar_erro("banco.tentativa", e)


def tentativas_desde(chave: str, tipo: str, desde_iso: str) -> int:
    try:
        return _contar("tentativas", {"chave": chave, "tipo": tipo, "quando": ("gte", desde_iso)})
    except Exception as e:
        registrar_erro("banco.tentativas", e)
        return 0


def tentativas_limpar(chave: str, tipo: str) -> None:
    try:
        _apagar("tentativas", {"chave": chave, "tipo": tipo})
    except Exception:
        pass


def limpar_antigos() -> None:
    """Remove tentativas com mais de 1 dia, sessões vencidas há 30 dias e tokens vencidos há 7 dias."""
    try:
        _apagar("tentativas", {"quando": ("lt", seg.somar(-86400))})
        _apagar("sessoes", {"expira_em": ("lt", seg.somar(-30 * 86400))})
        _apagar("tokens", {"expira_em": ("lt", seg.somar(-7 * 86400))})
    except Exception as e:
        registrar_erro("banco.limpeza", e)


# ------------------------------------------------------------------ administração (permissão conferida aqui)
def _exigir(ator: Ator | None, permissao: str) -> Ator:
    if not ator or not perm.tem(ator.papel, permissao):
        raise SemPermissao("Você não tem permissão para esta operação.")
    return ator


def admin_resumo(ator: Ator | None) -> dict:
    _exigir(ator, "admin.resumo")
    d7, d30, d1 = seg.somar(-7 * 86400), seg.somar(-30 * 86400), seg.somar(-86400)
    return {
        "total": _contar("contas"),
        "ativas": _contar("contas", {"status": "ativa"}),
        "suspensas": _contar("contas", {"status": "suspensa"}),
        "pendentes": _contar("contas", {"status": "pendente"}),
        "admins": _contar("contas", {"papel": "admin"}),
        "suporte": _contar("contas", {"papel": "suporte"}),
        "novos_7d": _contar("contas", {"criado_em": ("gte", d7)}),
        "novos_30d": _contar("contas", {"criado_em": ("gte", d30)}),
        "ativos_30d": _contar("contas", {"ultimo_login": ("gte", d30)}),
        "sessoes_validas": _contar("sessoes", {"revogada": 0, "expira_em": ("gte", seg.iso())}),
        "erros_24h": _contar("erros", {"quando": ("gte", d1)}),
        "logins_falhos_24h": _contar("tentativas", {"tipo": "login", "quando": ("gte", d1)}),
        "backend": backend(),
    }


def admin_listar_usuarios(ator: Ator | None, busca: str = "", status: str | None = None, limite: int = 200) -> list[dict]:
    _exigir(ator, "admin.usuarios.ver")
    f: dict = {}
    if busca.strip():
        f["email"] = ("contem", busca.strip()[:80])
    if status in ("ativa", "suspensa", "pendente"):
        f["status"] = status
    return _selecionar("contas", f, PUBLICAS_CONTA, ordem="criado_em", desc=True, limite=min(int(limite), 500))


def admin_definir_status(ator: Ator | None, alvo_id: str, status: str, motivo: str = "") -> None:
    perm_nec = "admin.usuarios.suspender" if status == "suspensa" else "admin.usuarios.reativar"
    _exigir(ator, perm_nec)
    if status not in ("suspensa", "ativa"):
        raise ErroBanco("status inválido")
    if alvo_id == ator.id:
        raise SemPermissao("Você não pode alterar a própria conta por aqui.")
    alvo = sis_conta_por_id(alvo_id)
    if not alvo:
        raise ErroBanco("conta não encontrada")
    if status == "suspensa" and alvo["papel"] == "admin":
        raise SemPermissao("Rebaixe o administrador antes de suspender a conta.")
    if status == "ativa" and not alvo["email_verificado"]:
        raise ErroBanco("a conta ainda não confirmou o e-mail")
    auditar(ator.id, "conta.suspensa" if status == "suspensa" else "conta.reativada", alvo_id,
            {"motivo": motivo[:120]}, obrigatorio=True)
    sis_atualizar_conta(alvo_id, {"status": status})
    if status == "suspensa":
        sis_revogar_sessoes_da_conta(alvo_id)


def admin_definir_papel(ator: Ator | None, alvo_id: str, papel: str) -> None:
    _exigir(ator, "admin.usuarios.papel")
    if papel not in perm.PAPEIS:
        raise ErroBanco("papel inválido")
    if alvo_id == ator.id:
        raise SemPermissao("Você não pode alterar o próprio papel.")
    alvo = sis_conta_por_id(alvo_id)
    if not alvo:
        raise ErroBanco("conta não encontrada")
    if alvo["status"] != "ativa" and papel != "usuario":
        raise ErroBanco("só contas ativas podem receber privilégios")
    auditar(ator.id, "conta.papel", alvo_id, {"de": alvo["papel"], "para": papel}, obrigatorio=True)
    sis_atualizar_conta(alvo_id, {"papel": papel})


def admin_auditoria(ator: Ator | None, limite: int = 200, acao: str | None = None) -> list[dict]:
    _exigir(ator, "admin.auditoria.ver")
    f = {"acao": acao} if acao else None
    return _selecionar("auditoria", f, ["quando", "ator_id", "acao", "alvo_id", "detalhes"], ordem="quando",
                       desc=True, limite=min(int(limite), 1000))


def admin_erros(ator: Ator | None, limite: int = 100) -> list[dict]:
    _exigir(ator, "admin.erros.ver")
    return _selecionar("erros", None, ["quando", "modulo", "tipo", "mensagem"], ordem="quando", desc=True,
                       limite=min(int(limite), 500))


def admin_backup(ator: Ator | None) -> dict:
    """Cópia das contas (SEM senhas), da auditoria e dos erros. Dados de carteira e preferências não entram:
    administrador não os vê."""
    _exigir(ator, "admin.backup")
    auditar(ator.id, "backup.contas", obrigatorio=True)
    return {"gerado_em": seg.iso(), "versao_esquema": SCHEMA_VERSAO,
            "contas": _selecionar("contas", None, PUBLICAS_CONTA, ordem="criado_em"),
            "auditoria": _selecionar("auditoria", None, ordem="quando", limite=5000),
            "erros": _selecionar("erros", None, ordem="quando", limite=2000)}


def backup_sqlite(destino: str | Path) -> Path:
    """Cópia consistente do arquivo SQLite (inclui tudo). Só existe para o modo local; no Supabase use o backup do próprio Supabase."""
    if backend() != "sqlite":
        raise ErroBanco("backup de arquivo só existe no modo local")
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with _con() as origem, sqlite3.connect(destino) as copia:
        origem.backup(copia)
    return destino


def host_do_banco() -> str:
    sb = _supabase()
    return (urlparse(sb[0]).netloc if sb else "arquivo local (usuarios.db)")

