-- Trader Battle multiplayer · tabelas tb_partidas e tb_jogadores. Seguro para rodar mais de uma vez. Cole tudo e clique em Run.
begin;
create table if not exists tb_partidas (
  id text primary key,
  codigo text,
  status text not null default 'aguardando' check (status in ('aguardando','em_jogo','finalizada','cancelada')),
  criador text not null references contas(email) on delete cascade,
  versao integer not null default 1,
  criado_em text not null,
  atualizado text not null,
  finalizada_em text,
  dados jsonb
);
create table if not exists tb_jogadores (
  id text primary key,
  partida_id text not null references tb_partidas(id) on delete cascade,
  email text not null references contas(email) on delete cascade,
  entrou_em text not null,
  ativo integer not null default 1
);
create unique index if not exists ux_tb_codigo on tb_partidas (codigo) where codigo is not null and status = 'aguardando';
create unique index if not exists ux_tb_ativo on tb_jogadores (email) where ativo = 1;
create index if not exists ix_tb_status on tb_partidas (status, atualizado);
create index if not exists ix_tb_jog_partida on tb_jogadores (partida_id);
-- Segurança: RLS ligado e sem nenhuma política = só o servidor do app (chave secreta) lê e escreve; ele entrega a cada jogador só o que ele pode ver.
alter table tb_partidas enable row level security;
alter table tb_jogadores enable row level security;
revoke all on tb_partidas from anon, authenticated;
revoke all on tb_jogadores from anon, authenticated;
commit;
