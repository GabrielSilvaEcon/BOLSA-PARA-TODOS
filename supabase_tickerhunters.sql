-- Bússola B3 · Passo 21 · contas, sessões, auditoria. Seguro para rodar mais de uma vez.
begin;
create table if not exists schema_versao (
  versao integer primary key,
  aplicada_em text not null,
  descricao text not null default ''
);
create table if not exists contas (
  id text primary key,
  email text not null unique,
  nome text not null default '',
  senha_hash text,
  papel text not null default 'usuario' check (papel in ('usuario','suporte','admin')),
  status text not null default 'ativa' check (status in ('ativa','suspensa','pendente')),
  email_verificado integer not null default 0,
  provedor text not null default 'senha',
  criado_em text not null,
  ultimo_login text,
  aceite_em text
);
create table if not exists sessoes (
  token_hash text primary key,
  conta_id text not null references contas(id) on delete cascade,
  criado_em text not null,
  ultimo_uso text not null,
  expira_em text not null,
  ocioso_s integer not null default 3600,
  revogada integer not null default 0
);
create table if not exists tokens (
  token_hash text primary key,
  conta_id text not null references contas(id) on delete cascade,
  tipo text not null check (tipo in ('verificar','redefinir')),
  criado_em text not null,
  expira_em text not null,
  usado integer not null default 0
);
create table if not exists tentativas (
  id bigint generated always as identity primary key,
  chave text not null,
  tipo text not null,
  quando text not null
);
create table if not exists auditoria (
  id bigint generated always as identity primary key,
  quando text not null,
  ator_id text,
  acao text not null,
  alvo_id text,
  detalhes text not null default ''
);
create table if not exists erros (
  id bigint generated always as identity primary key,
  quando text not null,
  modulo text not null default '',
  tipo text not null default '',
  mensagem text not null default ''
);
create table if not exists perfis (
  email text primary key,
  dados jsonb,
  atualizado text
);
create table if not exists notificacoes (
  id text primary key,
  chave text not null unique,
  email text not null references contas(email) on delete cascade,
  categoria text not null,
  ativo text not null default '',
  importancia text not null default 'media',
  titulo text not null,
  texto text not null default '',
  origem text not null default '',
  regra_id text not null default '',
  grupo text not null default '',
  pagina text not null default '',
  quando text not null,
  lida integer not null default 0,
  arquivada integer not null default 0,
  dados jsonb
);
create table if not exists monitor_exec (
  id text primary key,
  inicio text not null,
  fim text,
  status text not null default 'rodando',
  resumo jsonb
);
create table if not exists monitor_estado (
  id text primary key,
  email text not null references contas(email) on delete cascade,
  chave text not null,
  dados jsonb,
  atualizado text
);
create table if not exists tc_livro (
  id text primary key,
  conta_id text not null,
  seq integer not null,
  delta integer not null default 0,
  saldo_apos integer not null default 0,
  tipo text not null check (tipo in ('credito','debito','estorno','ajuste','pendente')),
  estado text not null default 'confirmada' check (estado in ('confirmada','pendente','cancelada','estornada')),
  origem text not null default '',
  descricao text not null default '',
  chave text not null unique,
  ref text not null default '',
  criado_em text not null,
  dados jsonb
);
create table if not exists tc_compras (
  id text primary key,
  conta_id text not null,
  produto_id text not null,
  preco integer not null default 0,
  estado text not null default 'confirmada' check (estado in ('confirmada','estornada','expirada')),
  criado_em text not null,
  expira_em text,
  usos_restantes integer,
  livro_chave text not null default '',
  dados jsonb
);
create table if not exists wg_creditos (
  id text primary key,
  email text not null,
  conta_id text not null,
  chave text not null unique,
  tipo text not null,
  valor real not null default 0,
  dia text not null default '',
  descricao text not null default '',
  criado_em text not null,
  dados jsonb
);
create table if not exists config_sistema (
  id text primary key,
  dados jsonb,
  atualizado text
);
create index if not exists ix_wg_creditos_email on wg_creditos (email, dia);
create unique index if not exists ux_tc_livro_seq on tc_livro (conta_id, seq);
create index if not exists ix_tc_livro_conta on tc_livro (conta_id, criado_em);
create index if not exists ix_tc_compras_conta on tc_compras (conta_id, produto_id);
create index if not exists ix_contas_status on contas (status);
create index if not exists ix_contas_criado on contas (criado_em);
create index if not exists ix_sessoes_conta on sessoes (conta_id);
create index if not exists ix_sessoes_expira on sessoes (expira_em);
create index if not exists ix_tokens_conta on tokens (conta_id);
create index if not exists ix_tentativas on tentativas (chave, tipo, quando);
create index if not exists ix_auditoria_ator on auditoria (ator_id, quando);
create index if not exists ix_auditoria_quando on auditoria (quando);
create index if not exists ix_erros_quando on erros (quando);
create index if not exists ix_notif_email on notificacoes (email, quando);
create index if not exists ix_notif_estado on notificacoes (email, lida, arquivada);
create index if not exists ix_monitor_exec on monitor_exec (inicio);
create index if not exists ix_monitor_estado on monitor_estado (email);
-- contas para quem já usava o app (entrava com Google): nada se perde
insert into contas (id, email, nome, papel, status, email_verificado, provedor, criado_em)
select gen_random_uuid()::text, p.email, split_part(p.email, '@', 1), 'usuario', 'ativa',
       case when p.email like '%@%' then 1 else 0 end, 'google',
       to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"')
from perfis p on conflict (email) do nothing;
-- integridade: perfil sempre pertence a uma conta; apagar a conta apaga o perfil
do $$ begin
  alter table perfis add constraint perfis_email_fk foreign key (email) references contas (email) on delete cascade;
exception when duplicate_object then null; end $$;
-- proteção: tabelas fechadas para a chave pública; só a chave secreta do servidor entra
alter table schema_versao enable row level security;
alter table contas enable row level security;
alter table sessoes enable row level security;
alter table tokens enable row level security;
alter table tentativas enable row level security;
alter table auditoria enable row level security;
alter table erros enable row level security;
alter table perfis enable row level security;
alter table notificacoes enable row level security;
alter table monitor_exec enable row level security;
alter table monitor_estado enable row level security;
alter table tc_livro enable row level security;
alter table tc_compras enable row level security;
alter table wg_creditos enable row level security;
alter table config_sistema enable row level security;
insert into schema_versao (versao, aplicada_em, descricao) values (1, to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'), 'Passo 21: contas, sessões, tokens, auditoria') on conflict (versao) do nothing;
insert into schema_versao (versao, aplicada_em, descricao) values (2, to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'), 'Passo 23: notificações e monitoramento') on conflict (versao) do nothing;
insert into schema_versao (versao, aplicada_em, descricao) values (3, to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'), 'TickerCoins: livro-razão e compras da Loja Ticker') on conflict (versao) do nothing;
insert into schema_versao (versao, aplicada_em, descricao) values (4, to_char(now() at time zone 'utc', 'YYYY-MM-DD"T"HH24:MI:SS.MS"Z"'), 'Wallet Game: livro de créditos virtuais') on conflict (versao) do nothing;
commit;
