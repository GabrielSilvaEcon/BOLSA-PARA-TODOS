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
import re
import os
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
    # Passo 23 — notificações e monitoramento (tabelas novas: o resto do app continua funcionando sem elas)
    "notificacoes": [
        "id text primary key",
        "chave text not null unique",            # email|dedup: impede a mesma notificação duas vezes
        "email text not null references contas(email) on delete cascade",
        "categoria text not null", "ativo text not null default ''",
        "importancia text not null default 'media'",
        "titulo text not null", "texto text not null default ''",
        "origem text not null default ''", "regra_id text not null default ''",
        "grupo text not null default ''", "pagina text not null default ''",
        "quando text not null",
        "lida integer not null default 0", "arquivada integer not null default 0",
        "dados {JSON}"],
    "monitor_exec": [
        "id text primary key",                   # um por janela de tempo: é a trava contra execução duplicada
        "inicio text not null", "fim text", "status text not null default 'rodando'", "resumo {JSON}"],
    "monitor_estado": [
        "id text primary key",                   # email|chave
        "email text not null references contas(email) on delete cascade",
        "chave text not null", "dados {JSON}", "atualizado text"],
    "config_sistema": [                          # Etapa 2: configuração e contagem de consumo das APIs (sem dados de usuários)
        "id text primary key", "dados {JSON}", "atualizado text"],
}
SCHEMA_NOTIF = 2
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
    "create index if not exists ix_notif_email on notificacoes (email, quando)",
    "create index if not exists ix_notif_estado on notificacoes (email, lida, arquivada)",
    "create index if not exists ix_monitor_exec on monitor_exec (inicio)",
    "create index if not exists ix_monitor_estado on monitor_estado (email)",
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
        "insert into schema_versao (versao, aplicada_em, descricao) values "
        f"({SCHEMA_NOTIF}, to_char(now() at time zone 'utc', 'YYYY-MM-DD\"T\"HH24:MI:SS.MS\"Z\"'), "
        "'Passo 23: notificações e monitoramento') on conflict (versao) do nothing;",
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
    """Seção dos secrets do Streamlit como dict (vazio se não existir). Não levanta erro.
    Fora do Streamlit (monitor automático no GitHub Actions) lê variáveis de ambiente BPT_<SEÇÃO>_<CHAVE>, ex.: BPT_SUPABASE_URL."""
    try:
        import streamlit as st
        d = dict(st.secrets[nome])
        if d:
            return d
    except Exception:
        pass
    pre = f"BPT_{nome.upper()}_"
    return {k[len(pre):].lower(): v for k, v in os.environ.items() if k.startswith(pre) and v}


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
_OPS = {"eq": "=", "neq": "!=", "gt": ">", "gte": ">=", "lt": "<", "lte": "<=", "contem": "like", "comeca": "like"}


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


def _like(txt: str, inicio: bool = False) -> str:
    esc = str(txt).replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return esc + "%" if inicio else "%" + esc + "%"


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
        elif op == "comeca":
            p.append((col, "like." + str(val).replace("*", "") + "*"))
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
            f"{c} like ? escape '\\'" if op in ("contem", "comeca") else f"{c} {_OPS[op]} ?" for c, op, _ in f)
        args = [_like(v, op == "comeca") if op in ("contem", "comeca") else v for _, op, v in f]
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
            f"{c} like ? escape '\\'" if op in ("contem", "comeca") else f"{c} {_OPS[op]} ?" for c, op, _ in f)
    with _con() as con:
        return int(con.execute(sql, [_like(v, op == "comeca") if op in ("contem", "comeca") else v for _, op, v in f]).fetchone()[0])


def _inserir(tabela: str, linha: dict) -> None:
    _conferir(tabela, linha.keys())
    if backend() == "supabase":
        _rest("POST", tabela, corpo=linha, prefer="return=minimal")
        return
    cols = list(linha)
    try:
        with _con() as con:
            con.execute(f"insert into {tabela} ({', '.join(cols)}) values ({', '.join('?' * len(cols))})",  # seg-ok: tabela/colunas validadas por _conferir; valores por ?
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
        con.execute("insert or ignore into schema_versao (versao, aplicada_em, descricao) values (?,?,?)",
                    (SCHEMA_NOTIF, seg.iso(), "Passo 23: notificações e monitoramento"))


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
    try:
        _apagar("notificacoes", {"email": ator.email})
        _apagar("monitor_estado", {"email": ator.email})
    except Exception as e:      # tabelas do Passo 23 ainda não criadas: o resto da exclusão já foi feito
        registrar_erro("banco.apagar_dados.notif", e)
    comp_ligas_do_dono_apagar(ator.email)


# ------------------------------------------------------------------ notificações (Passo 23): sempre do próprio ator
CATEGORIAS_NOTIF = ("preco", "tecnico", "fundamentalista", "carteira", "noticia", "evento", "macro", "estudo", "sistema")
IMPORTANCIAS_NOTIF = ("alta", "media", "baixa")


def _js(v):
    """JSON no formato da coluna: texto no SQLite, objeto no Supabase (jsonb)."""
    if backend() == "supabase":
        return v if isinstance(v, (dict, list)) else (json.loads(v) if v else {})
    return json.dumps(v if v is not None else {}, ensure_ascii=False, default=str)


def _de_js(v):
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError:
            return {}
    return v or {}


def _linha_notif(email: str, n: dict) -> dict:
    """Valida e completa uma notificação. A chave de deduplicação nasce do e-mail dono + `dedup`."""
    dedup = str(n.get("dedup") or n.get("id") or "")[:300]
    if not dedup:
        raise ErroBanco("notificação sem identificador de deduplicação")
    cat = n.get("categoria") if n.get("categoria") in CATEGORIAS_NOTIF else "sistema"
    imp = n.get("importancia") if n.get("importancia") in IMPORTANCIAS_NOTIF else "media"
    return {
        "id": str(n.get("id") or seg.novo_id()),
        "chave": f"{email}|{dedup}", "email": email, "categoria": cat,
        "ativo": str(n.get("ativo") or "")[:24].upper(), "importancia": imp,
        "titulo": str(n.get("titulo") or "")[:200], "texto": str(n.get("texto") or "")[:1500],
        "origem": str(n.get("origem") or "")[:30], "regra_id": str(n.get("regra_id") or "")[:120],
        "grupo": str(n.get("grupo") or "")[:120], "pagina": str(n.get("pagina") or "")[:60],
        "quando": str(n.get("quando") or seg.iso()), "lida": 0, "arquivada": 0, "dados": _js(n.get("dados") or {}),
    }


def notif_inserir(ator: Ator | None, n: dict) -> bool:
    """Grava uma notificação para o próprio ator. False se já existia (deduplicação)."""
    if not ator:
        raise SemPermissao("Faça login.")
    try:
        _inserir("notificacoes", _linha_notif(ator.email, n))
        return True
    except Duplicado:
        return False


def _tratar_notif(r: dict) -> dict:
    r["dados"] = _de_js(r.get("dados"))
    r["lida"], r["arquivada"] = bool(r.get("lida")), bool(r.get("arquivada"))
    return r


def notif_listar(ator: Ator | None, lida: bool | None = None, arquivada: bool = False, categoria: str | None = None,
                 ativo: str | None = None, importancia: str | None = None, limite: int = 300) -> list[dict]:
    if not ator:
        raise SemPermissao("Faça login.")
    f: dict = {"email": ator.email, "arquivada": 1 if arquivada else 0}
    if lida is not None:
        f["lida"] = 1 if lida else 0
    if categoria in CATEGORIAS_NOTIF:
        f["categoria"] = categoria
    if importancia in IMPORTANCIAS_NOTIF:
        f["importancia"] = importancia
    if ativo:
        f["ativo"] = str(ativo).upper()[:24]
    return [_tratar_notif(r) for r in _selecionar("notificacoes", f, ordem="quando", desc=True, limite=max(1, min(int(limite), 1000)))]


def notif_contar(ator: Ator | None, lida: bool | None = False, arquivada: bool = False) -> int:
    if not ator:
        raise SemPermissao("Faça login.")
    f: dict = {"email": ator.email, "arquivada": 1 if arquivada else 0}
    if lida is not None:
        f["lida"] = 1 if lida else 0
    return _contar("notificacoes", f)


def _ids(ids) -> list[str]:
    return [str(i)[:64] for i in list(ids or [])[:500]]


def notif_marcar(ator: Ator | None, ids, lida: bool = True) -> int:
    """Marca como lida/não lida. Cada atualização exige id E e-mail do ator: id de outra conta não faz nada."""
    if not ator:
        raise SemPermissao("Faça login.")
    n = 0
    for i in _ids(ids):
        _atualizar("notificacoes", {"id": i, "email": ator.email}, {"lida": 1 if lida else 0})
        n += 1
    return n


def notif_arquivar(ator: Ator | None, ids, arquivada: bool = True) -> int:
    if not ator:
        raise SemPermissao("Faça login.")
    n = 0
    for i in _ids(ids):
        _atualizar("notificacoes", {"id": i, "email": ator.email}, {"arquivada": 1 if arquivada else 0})
        n += 1
    return n


def notif_excluir(ator: Ator | None, ids) -> int:
    if not ator:
        raise SemPermissao("Faça login.")
    n = 0
    for i in _ids(ids):
        _apagar("notificacoes", {"id": i, "email": ator.email})
        n += 1
    return n


def notif_disponivel() -> bool:
    """False enquanto as tabelas do Passo 23 não existirem (Supabase sem o script SQL novo)."""
    try:
        _contar("notificacoes", {"email": "-"})
        return True
    except Exception:
        return False


# ------------------------------------------------------------------ monitor automático (sem Ator: roda fora do navegador)
# Estas funções só são chamadas por monitor.py, com a chave secreta do servidor. Nenhuma devolve senha_hash.
def sis_contas_monitoraveis(limite: int = 500) -> list[dict]:
    return _selecionar("contas", {"status": "ativa"}, ["id", "email", "nome", "papel"], ordem="criado_em", limite=limite)


def sis_dados_de(email: str) -> dict:
    r = _selecionar("perfis", {"email": seg.normalizar_email(email)}, ["dados"], limite=1)
    return _de_js(r[0]["dados"]) if r else {}


def sis_notif_inserir(email: str, n: dict) -> str | None:
    """Grava uma notificação para a conta. Devolve o id novo, ou None se já existia (deduplicação)."""
    linha = _linha_notif(seg.normalizar_email(email), n)
    try:
        _inserir("notificacoes", linha)
        return linha["id"]
    except Duplicado:
        return None


def sis_notif_recentes(email: str, desde_iso: str, limite: int = 500) -> list[dict]:
    return [_tratar_notif(r) for r in _selecionar(
        "notificacoes", {"email": seg.normalizar_email(email), "quando": ("gte", desde_iso)},
        ["id", "regra_id", "ativo", "categoria", "importancia", "quando", "dados"], ordem="quando", desc=True, limite=limite)]


def sis_notif_atualizar_dados(notif_id: str, dados: dict) -> None:
    _atualizar("notificacoes", {"id": str(notif_id)}, {"dados": _js(dados)})


def sis_estado_ler(email: str, chave: str) -> dict:
    r = _selecionar("monitor_estado", {"id": f"{seg.normalizar_email(email)}|{chave}"}, ["dados"], limite=1)
    return _de_js(r[0]["dados"]) if r else {}


def sis_estado_gravar(email: str, chave: str, dados: dict) -> None:
    email = seg.normalizar_email(email)
    linha = {"id": f"{email}|{chave}", "email": email, "chave": str(chave)[:60], "dados": _js(dados), "atualizado": seg.iso()}
    if backend() == "supabase":
        _rest("POST", "monitor_estado", params=[("on_conflict", "id")], corpo=linha, prefer="resolution=merge-duplicates,return=minimal")
        return
    with _con() as con:
        con.execute("insert into monitor_estado (id, email, chave, dados, atualizado) values (?,?,?,?,?) "
                    "on conflict(id) do update set dados=excluded.dados, atualizado=excluded.atualizado",
                    (linha["id"], email, linha["chave"], linha["dados"], linha["atualizado"]))


def cfg_disponivel() -> bool:
    """False enquanto a tabela config_sistema (Etapa 2) não existir no Supabase."""
    try:
        _contar("config_sistema", {"id": "-"})
        return True
    except Exception:
        return False


def cfg_ler(chave: str) -> dict:
    r = _selecionar("config_sistema", {"id": str(chave)[:80]}, ["dados"], limite=1)
    return _de_js(r[0]["dados"]) if r else {}


def cfg_gravar(chave: str, dados: dict) -> None:
    linha = {"id": str(chave)[:80], "dados": _js(dados), "atualizado": seg.iso()}
    if backend() == "supabase":
        _rest("POST", "config_sistema", params=[("on_conflict", "id")], corpo=linha, prefer="resolution=merge-duplicates,return=minimal")
        return
    with _con() as con:
        con.execute("insert into config_sistema (id, dados, atualizado) values (?,?,?) "
                    "on conflict(id) do update set dados=excluded.dados, atualizado=excluded.atualizado",
                    (linha["id"], linha["dados"], linha["atualizado"]))


def cfg_apagar(chave: str) -> None:
    _apagar("config_sistema", {"id": str(chave)[:80]})


def cfg_limpar_cache(antes_iso: str, limite: int = 50) -> int:
    """Apaga cópias antigas do cache central (só ids 'cache|...'). Devolve quantas apagou."""
    try:
        velhos = _selecionar("config_sistema", {"id": ("comeca", "cache|"), "atualizado": ("lt", antes_iso)}, ["id"], limite=limite)
        for r in velhos:
            _apagar("config_sistema", {"id": r["id"]})
        return len(velhos)
    except Exception:
        return 0


def sis_exec_iniciar(slot: str) -> bool:
    """Trava de execução: só um processo consegue registrar a mesma janela (slot). False = já está rodando/rodou."""
    try:
        _inserir("monitor_exec", {"id": str(slot)[:60], "inicio": seg.iso(), "status": "rodando", "resumo": _js({})})
        return True
    except Duplicado:
        return False


def sis_exec_finalizar(slot: str, status: str, resumo: dict) -> None:
    _atualizar("monitor_exec", {"id": str(slot)[:60]}, {"fim": seg.iso(), "status": status[:20], "resumo": _js(resumo)})


def sis_exec_liberar(slot: str) -> None:
    """Libera uma janela que travou (status 'rodando' há muito tempo) para nova tentativa."""
    _apagar("monitor_exec", {"id": str(slot)[:60]})


def monitor_estado_ler(ator: Ator | None) -> dict:
    """Estado do monitor da própria conta (o que já avisou), usado também na verificação manual."""
    if not ator:
        raise SemPermissao("Faça login.")
    return sis_estado_ler(ator.email, "mon")


def monitor_estado_gravar(ator: Ator | None, dados: dict) -> None:
    if not ator:
        raise SemPermissao("Faça login.")
    sis_estado_gravar(ator.email, "mon", dados)


def monitor_execucoes(ator: Ator | None, limite: int = 30) -> list[dict]:
    """Últimas verificações automáticas (administração). Sem dados de usuários."""
    _exigir(ator, "admin.seguranca")
    return [dict(r, resumo=_de_js(r.get("resumo"))) for r in _selecionar("monitor_exec", ordem="inicio", desc=True, limite=limite)]


def monitor_ultima(limite: int = 1) -> list[dict]:
    """Última verificação (qualquer usuário pode ver QUANDO foi, sem detalhes)."""
    try:
        return [{"inicio": r["inicio"], "fim": r["fim"], "status": r["status"]}
                for r in _selecionar("monitor_exec", None, ["inicio", "fim", "status"], ordem="inicio", desc=True, limite=limite)]
    except Exception:
        return []


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
    try:                                   # plano/assinatura e uso diário da conta (contêm o e-mail): apagados junto com a conta
        import planos
        planos.apagar_conta(email)
    except Exception as e:
        registrar_erro("banco.sis_apagar_conta.planos", e)
    for t in ("notificacoes", "monitor_estado"):
        try:
            _apagar(t, {"email": email})
        except Exception:      # tabelas do Passo 23 ainda não criadas no Supabase: não impede a exclusão da conta
            pass
    comp_ligas_do_dono_apagar(email)
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


RETENCAO_ERROS_DIAS = 90          # política de retenção (revisar com orientação jurídica)
RETENCAO_NOTIF_DIAS = 180         # notificações (lidas ou não) somem depois de ~6 meses; a pessoa pode apagar antes
RETENCAO_MONITOR_DIAS = 30        # registro das verificações automáticas
RETENCAO_AUDITORIA_DIAS = 400     # ~13 meses: o suficiente para investigar um incidente, sem guardar para sempre


def limpar_antigos() -> None:
    """Remove tentativas com mais de 1 dia, sessões vencidas há 30 dias, tokens vencidos há 7 dias, erros com mais de 90 dias
    e registros de auditoria com mais de ~13 meses (política de retenção)."""
    try:
        _apagar("tentativas", {"quando": ("lt", seg.somar(-86400))})
        _apagar("sessoes", {"expira_em": ("lt", seg.somar(-30 * 86400))})
        _apagar("tokens", {"expira_em": ("lt", seg.somar(-7 * 86400))})
        _apagar("erros", {"quando": ("lt", seg.somar(-RETENCAO_ERROS_DIAS * 86400))})
        _apagar("auditoria", {"quando": ("lt", seg.somar(-RETENCAO_AUDITORIA_DIAS * 86400))})
        _apagar("notificacoes", {"quando": ("lt", seg.somar(-RETENCAO_NOTIF_DIAS * 86400))})
        _apagar("monitor_exec", {"inicio": ("lt", seg.somar(-RETENCAO_MONITOR_DIAS * 86400))})
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


def admin_eventos_seguranca(ator: Ator | None, horas: int = 48) -> dict:
    """Registros recentes (auditoria e erros) para a análise de atividade suspeita. Só administrador."""
    _exigir(ator, "admin.seguranca")
    desde = seg.somar(-int(horas) * 3600)
    return {"auditoria": _selecionar("auditoria", {"quando": ("gte", desde)}, ["quando", "ator_id", "acao", "alvo_id", "detalhes"],
                                     ordem="quando", desc=True, limite=2000),
            "erros": _selecionar("erros", {"quando": ("gte", desde)}, ["quando", "modulo", "tipo", "mensagem"], ordem="quando",
                                 desc=True, limite=500)}


def admin_testar_backup(ator: Ator | None, chave: str | None = None) -> dict:
    """Ciclo completo de backup cifrado + restauração em arquivo temporário (só no modo SQLite local)."""
    _exigir(ator, "admin.backup")
    import tempfile
    import backup_seg
    auditar(ator.id, "backup.teste", obrigatorio=True)
    if backend() != "sqlite":
        return {"ok": None, "etapas": [("Banco em nuvem", True, "o Supabase faz a cópia do banco; teste a restauração no painel dele (Database > Backups)")],
                "contagem": {}, "quando": seg.iso()}
    with tempfile.TemporaryDirectory() as d:
        copia = backup_sqlite(Path(d) / "origem.db")
        return backup_seg.testar_restauracao(copia, chave)


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


# ------------------------------------------------------------------ competição de carteiras virtuais (sem tabela nova)
# Usa os mesmos documentos do monitor (monitor_estado, um por conta e chave) e a configuração do sistema (config_sistema):
#   comp_ordens (a pessoa grava) · comp_cart (só o fechamento diário grava) · comp_ranking e comp_precos (públicos, gerados no fechamento).
# Cada pessoa só lê e grava os próprios documentos; o ranking público tem apenas apelido e retorno %, nunca e-mail nem valores em reais.
def comp_ordens_ler(ator: Ator | None) -> dict:
    if not ator:
        raise SemPermissao("Faça login.")
    return sis_estado_ler(ator.email, "comp_ordens")


def comp_ordens_gravar(ator: Ator | None, dados: dict) -> None:
    if not ator:
        raise SemPermissao("Faça login.")
    sis_estado_gravar(ator.email, "comp_ordens", dados)


def comp_carteira_ler(ator: Ator | None) -> dict:
    """Carteira virtual da própria conta (somente leitura: quem grava é o fechamento diário)."""
    if not ator:
        raise SemPermissao("Faça login.")
    return sis_estado_ler(ator.email, "comp_cart")


def comp_publico_ler(chave: str) -> dict:
    """Documento público da competição (ranking ou preços). Sem banco de configuração, devolve vazio."""
    if chave not in ("comp_ranking", "comp_precos"):
        raise ValueError("documento público desconhecido")
    try:
        return cfg_ler(chave)
    except Exception:
        return {}


def comp_apelido_livre(ator: Ator | None, apelido_k: str) -> bool:
    """O apelido (em minúsculas) ainda não é de outra conta? Confere só o campo apelido_k dos documentos."""
    if not ator:
        raise SemPermissao("Faça login.")
    return all(r["email"] == ator.email or (r["dados"] or {}).get("apelido_k") != apelido_k for r in sis_comp_todos("comp_ordens"))


def sis_comp_todos(chave: str, limite: int = 5000) -> list[dict]:
    """[{email, dados}] de todas as contas para uma chave da competição. Só o fechamento diário e o próprio banco usam (sem Ator)."""
    if chave not in ("comp_ordens", "comp_cart", "comp_ligas", "edu_liga"):
        raise ValueError("chave desconhecida")
    return [{"email": r["email"], "dados": _de_js(r["dados"])} for r in _selecionar("monitor_estado", {"chave": chave}, ["email", "dados"], limite=limite)]


_ID_TEMP = r"\d{4}-(?:0[1-9]|1[0-2]|T[1-4])"


def comp_temp_ler(tid: str) -> dict:
    """Ranking público de uma temporada (mensal `2026-11` ou trimestral `2026-T4`): só apelido e retorno %. Sem banco de configuração, devolve vazio."""
    if not re.fullmatch(_ID_TEMP, str(tid)):
        raise ValueError("temporada inválida")
    try:
        return cfg_ler("comp_temp|" + str(tid))
    except Exception:
        return {}


def sis_comp_publicar(chave: str, dados: dict) -> None:
    if (chave not in ("comp_ranking", "comp_precos") and not re.fullmatch(r"comp_lr\|[A-Z2-9]{8}", str(chave))
            and not re.fullmatch(r"comp_temp\|" + _ID_TEMP, str(chave))):
        raise ValueError("documento público desconhecido")
    cfg_gravar(chave, dados)


# ------------------------------------------------------------------ competição · etapa 2: ligas de amigos por convite (sem tabela nova)
# Documentos: comp_ligas (da pessoa; só ela grava) · comp_liga|CÓDIGO (definição; só o dono cria e encerra) · comp_lr|CÓDIGO (ranking da liga;
# só o fechamento diário grava, e só um membro da liga consegue ler). A definição guarda um hash do dono, nunca o e-mail.
_COD_LIGA = re.compile(r"[A-Z2-9]{8}")


def _cod_liga(codigo: str) -> str:
    c = str(codigo or "").strip().upper()
    if not _COD_LIGA.fullmatch(c):
        raise ValueError("código de liga inválido")
    return c


def comp_ligas_ler(ator: Ator | None) -> dict:
    """Ligas da própria conta."""
    if not ator:
        raise SemPermissao("Faça login.")
    return sis_estado_ler(ator.email, "comp_ligas")


def comp_ligas_gravar(ator: Ator | None, dados: dict) -> None:
    if not ator:
        raise SemPermissao("Faça login.")
    sis_estado_gravar(ator.email, "comp_ligas", dados)


def comp_liga_definicao(ator: Ator | None, codigo: str) -> dict | None:
    """Nome e tamanho máximo da liga, para quem tem o código (nunca o dono). None se não existir."""
    if not ator:
        raise SemPermissao("Faça login.")
    c = _cod_liga(codigo)
    d = cfg_ler("comp_liga|" + c)
    if not d or not d.get("nome"):
        return None
    return {"codigo": c, "nome": str(d["nome"])[:30], "max": int(d.get("max") or 30), "criada": str(d.get("criada") or "")[:10]}


def comp_liga_contagem(ator: Ator | None, codigo: str) -> int:
    """Quantas contas têm o código da liga no próprio documento (conferência de vaga antes de entrar)."""
    if not ator:
        raise SemPermissao("Faça login.")
    c = _cod_liga(codigo)
    n = 0
    for r in sis_comp_todos("comp_ligas"):
        if any(isinstance(x, dict) and x.get("c") == c for x in (r["dados"] or {}).get("ligas") or []):
            n += 1
    return n


def comp_liga_criar(ator: Ator | None, definicao: dict) -> str:
    """Grava a definição de uma liga nova com um código inédito e devolve o código. O hash do dono vem do ator (não da tela)."""
    if not ator:
        raise SemPermissao("Faça login.")
    import hashlib
    import secrets
    alfabeto = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"
    doc = {"v": 1, "nome": str(definicao["nome"])[:30], "max": int(definicao["max"]), "criada": str(definicao.get("criada") or "")[:10],
           "dono_h": hashlib.sha256(ator.email.strip().lower().encode()).hexdigest()[:24]}
    for _ in range(8):
        c = "".join(secrets.choice(alfabeto) for _ in range(8))
        if not cfg_ler("comp_liga|" + c):
            cfg_gravar("comp_liga|" + c, doc)
            return c
    raise ErroBanco("não foi possível gerar um código de liga inédito")


def comp_liga_encerrar(ator: Ator | None, codigo: str) -> bool:
    """Só o dono encerra a liga (apaga a definição e o ranking). False se a liga não existe; SemPermissao se não for o dono."""
    if not ator:
        raise SemPermissao("Faça login.")
    import hashlib
    c = _cod_liga(codigo)
    d = cfg_ler("comp_liga|" + c)
    if not d:
        return False
    if d.get("dono_h") != hashlib.sha256(ator.email.strip().lower().encode()).hexdigest()[:24]:
        raise SemPermissao("Só quem criou a liga pode encerrá-la.")
    cfg_apagar("comp_liga|" + c)
    cfg_apagar("comp_lr|" + c)
    return True


def comp_liga_ranking_ler(ator: Ator | None, codigo: str) -> dict:
    """Ranking publicado da liga. Só entrega a quem tem o código no próprio documento (membro); para os demais, SemPermissao."""
    if not ator:
        raise SemPermissao("Faça login.")
    c = _cod_liga(codigo)
    meus = (sis_estado_ler(ator.email, "comp_ligas") or {}).get("ligas") or []
    if not any(isinstance(x, dict) and x.get("c") == c for x in meus):
        raise SemPermissao("Você não participa dessa liga.")
    try:
        return cfg_ler("comp_lr|" + c)
    except Exception:
        return {}


def edu_liga_ler(ator: Ator | None) -> dict:
    """Documento da própria conta na liga de estudo (opcional): {ligado, semana, xp, apelido}."""
    if not ator:
        raise SemPermissao("Faça login.")
    return sis_estado_ler(ator.email, "edu_liga")


def edu_liga_gravar(ator: Ator | None, dados: dict) -> None:
    if not ator:
        raise SemPermissao("Faça login.")
    sis_estado_gravar(ator.email, "edu_liga", dados)


def edu_liga_ranking(ator: Ator | None, codigo: str) -> list[dict]:
    """Linhas brutas da liga de estudo ([{apelido, ligado, semana, xp, eu}]) dos membros da liga `codigo`. Só entrega a quem é membro.
    Nunca devolve e-mail; a ordenação e o filtro de quem ligou a opção ficam em jornada_liga.montar."""
    if not ator:
        raise SemPermissao("Faça login.")
    c = _cod_liga(codigo)
    meus = (sis_estado_ler(ator.email, "comp_ligas") or {}).get("ligas") or []
    if not any(isinstance(x, dict) and x.get("c") == c for x in meus):
        raise SemPermissao("Você não participa dessa liga.")
    membros = {r["email"] for r in sis_comp_todos("comp_ligas")
               if any(isinstance(x, dict) and x.get("c") == c for x in (r["dados"] or {}).get("ligas") or [])}
    out = []
    for r in sis_comp_todos("edu_liga"):
        if r["email"] in membros:
            d = r["dados"] or {}
            out.append({"apelido": d.get("apelido"), "ligado": d.get("ligado"), "semana": d.get("semana"), "xp": d.get("xp"), "eu": r["email"] == ator.email})
    return out


def sis_comp_ligas_def(limite: int = 5000) -> dict:
    """{código: definição} de todas as ligas. Só o fechamento diário usa (sem Ator)."""
    out = {}
    for l in _selecionar("config_sistema", {"id": ("comeca", "comp_liga|")}, ["id", "dados"], limite=limite):
        cod = str(l["id"])[len("comp_liga|"):]
        if str(l["id"]).startswith("comp_liga|") and _COD_LIGA.fullmatch(cod):
            out[cod] = _de_js(l["dados"]) or {}
    return out


def comp_ligas_do_dono_apagar(email: str) -> int:
    """Exclusão de conta: apaga as ligas criadas por ela (a definição só guarda o hash do dono). Nunca impede a exclusão."""
    try:
        import hashlib
        h = hashlib.sha256(str(email).strip().lower().encode()).hexdigest()[:24]
        n = 0
        for cod, d in sis_comp_ligas_def().items():
            if d.get("dono_h") == h:
                cfg_apagar("comp_liga|" + cod)
                cfg_apagar("comp_lr|" + cod)
                n += 1
        return n
    except Exception as e:
        registrar_erro("banco.comp_ligas_do_dono_apagar", e)
        return 0
