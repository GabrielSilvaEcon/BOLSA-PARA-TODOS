# Arquitetura — Bússola B3

## Visão geral
`app.py` monta as páginas (`st.navigation`) e o menu; cada área vive em módulos próprios. Convenção: `nome.py` = lógica pura (testável sem
Streamlit); `nome_app.py` = tela. Todos os módulos ficam na raiz do repositório (o Streamlit Cloud exige o `app.py` na raiz).
```
app.py ─ páginas e menu ── *_app.py (telas) ── módulos de lógica ── dados.py / fontes ── banco.py (SQLite local ou Supabase)
                                  └── usuarios.py / contas.py / permissoes.py / seguranca.py (conta, sessão, permissões, auditoria)
monitor.py (GitHub Actions, fora do Streamlit) ── notif.py / canais.py ── banco.py (Supabase)
```

## Módulos por área
| Área | Arquivos principais |
|---|---|
| Dados e fontes | `dados.py` (Yahoo, Brapi, Fundamentus, reserva), `fonte_reserva.py`, `mercados.py` (Tesouro/CDI), `moeda.py`, `recursos.py`, `http_seguro.py` |
| Ações e fundamentalista | `motor_fundamentalista.py`, `tecnica.py`, `analise_tecnica.py(_app)`, `setorial.py`, `crescimento.py`, `evolucao.py`, `glossario.py`, `guias.py` |
| FIIs, ETFs e fundos | `fiis.py`, `fiis_cvm.py`, `fiis_app.py`, `fundos.py`, `fundos_analise.py`, `fundos_app.py` |
| Criptomoedas | `cripto.py`, `cripto_analise.py`, `cripto_app.py`, `fundamentalista_cripto.py`, `analise_defi.py` |
| Renda fixa | `renda_fixa.py`, `renda_fixa_app.py` |
| Carteira, risco, simulação, relatórios | `carteira.py`, `gestao.py(_app/_otimiza)`, `risco.py(_app)`, `simulador*.py`, `relatorios*.py`, `comparador*.py` |
| Inteligência e IA | `assistente.py` (motor de IA e filtros), `intel.py(_app)`, `noticias_eventos.py`, `noticias_app.py`, `*_ia.py` |
| Notificações | `notif.py`, `canais.py`, `monitor.py`, `notif_app.py`, `.github/workflows/monitor.yml` |
| Educação | `edu_conteudo.py`, `educacao.py`, `educacao_app.py`, `modos.py` |
| Conta e segurança | `usuarios.py`, `contas.py`, `conta_app.py`, `permissoes.py`, `seguranca.py`, `protecao.py`, `backup_seg.py`, `alertas_seg.py`, `auditoria_codigo.py`, `email_envio.py` |
| Visual | `tema.py`, `paleta.py`, `marca.py`, `prefs.py` |

## Dados e cálculos (regras de convivência)
- **Um só cálculo por conceito.** Volatilidade, queda máxima, Sharpe, Sortino, VaR/CVaR, TWR e XIRR vivem em `gestao.py`; juros, inflação e taxas em
  `simulador.py`; a educação reutiliza esses mesmos (não reimplementa). `tests/test_calculos_conhecidos.py` confere casos resolvidos à mão.
- **Premissas:** 252 pregões por ano (volatilidade, Sharpe, Sortino); XIRR em 365 dias; CAGR em 365,25 dias; VaR histórico escalado por raiz do tempo; Sharpe
  e Sortino anualizados pela média aritmética dos retornos diários.
- **Dado ausente nunca vira número.** As funções devolvem `None` e a tela mostra "indisponível" com o motivo. Fontes e datas são exibidas junto do dado.
- **Cache:** `st.cache_data` com TTL (15 min para cotações e históricos) e um disjuntor por fonte em `dados.py` (após falhas repetidas, deixa de insistir por um tempo).

## Fontes de dados e limites (gratuitas)
Yahoo Finance (cotação, histórico, indicadores; sem garantia de serviço e com bloqueios ocasionais), Brapi (token grátis opcional; limite mensal),
Fundamentus (leitura de página pública, só para uso pessoal/educacional), CVM e Tesouro Transparente (dados abertos), Banco Central/IBGE (séries), Binance
(dados públicos de mercado), CoinGecko, DefiLlama, mempool.space, FMP (plano grátis, reserva para ações dos EUA). Estratégia de contingência: fonte
principal → reserva (`fonte_reserva.py`) → mensagem de indisponibilidade. A lista de domínios permitidos está em `http_seguro.py`.
**Licenciamento:** os termos de cada provedor mudam e alguns restringem uso comercial (em especial Yahoo e Fundamentus). Revise-os antes de cobrar pelo
app ou abri-lo a um público amplo; o app não usa nenhuma API paga.

## Banco de dados
- **Local (SQLite)** em desenvolvimento; **Supabase (Postgres)** em produção. O esquema é criado de forma idempotente por `banco.py`
  (`sql_supabase()` gera o script; rode-o em Administração > Sistema). Versões: `SCHEMA_VERSAO=1` (conta/perfil) e `SCHEMA_NOTIF=2` (notificações e monitor).
- Tabelas: contas, sessões, perfis (JSON por conta), auditoria, erros, notificações, execuções e estado do monitor.
- **Isolamento:** toda função de dados recebe o `ator` e confere dono (e-mail) e permissão; testado em `tests/test_banco*.py` e `test_isolamento_estatico.py`.
- **Migrações:** somente aditivas (criar tabela/índice se não existir). Nunca apague colunas ou tabelas em produção sem backup.
- **Retenção:** notificações 180 dias; execuções do monitor 30 dias; auditoria e erros conforme `SEGURANCA.md`.

## Implantação (Streamlit Cloud)
1. Repositório público ou privado no GitHub com `app.py` na raiz. 2. Em Settings > Secrets, cole os blocos do `secrets.toml.example` que for usar.
3. Dependências: `requirements.txt` (Python 3.12). 4. Para o monitor: segredos no GitHub (`BPT_SUPABASE_URL`, `BPT_SUPABASE_KEY`, opcionais de e-mail/Telegram)
e o workflow `monitor.yml`. 5. Depois de subir arquivos, faça Reboot app. Credenciais nunca vão para o repositório (`auditoria_codigo.py` e o workflow
`seguranca.yml` verificam).
**Logs:** Manage app > Logs no Streamlit Cloud; erros do app ficam na tabela de erros (Administração > Erros); execuções do monitor em Administração > Sistema.

## Backup e recuperação
- Backup cifrado dos dados pela tela Administração > Segurança (`backup_seg.py`, chave em `[backup]`); guarde a chave fora do app.
- **Supabase:** além disso, use o backup do próprio projeto (Database > Backups) e exporte periodicamente. Teste a restauração em um projeto separado.
- **Recuperação:** crie um projeto Supabase novo, rode o script SQL, restaure o backup cifrado e atualize `[supabase]` nos Secrets.

## Guia de manutenção
- Após qualquer mudança: `pytest` (a suíte roda sem internet). Atualize `requirements.txt` ao importar pacote novo (há teste para isso).
- A cada trimestre: revisar regras tributárias em `edu_conteudo.py` (`REVISAO`), limites e termos das fontes, e os avisos do Dependabot.
- O GitHub desliga agendamentos de repositório sem atividade por 60 dias: um commit reativa o monitor.

## Como adicionar uma nova classe de ativos
1. **Classe:** inclua o código em `notif.CLASSES` e, se tiver tipos de alerta próprios, em `notif.TIPOS_MON`/`INDICADORES` (quais regras valem para ela).
2. **Dados:** crie `nova.py` (lógica pura, devolvendo `None` quando faltar dado) e `nova_app.py` (tela); reutilize `gestao.py` para risco e retorno.
3. **Página:** declare `PG_NOVA = st.Page(...)` em `app.py`, inclua no menu e (se quiser) em `educacao_app.registrar_paginas`.
4. **Educação:** adicione o assunto em `edu_conteudo.ASSUNTOS` (com a classe), aulas e, em `INDICADORES`, os indicadores com `classes=["nova"]`.
5. **Monitor:** ensine `monitor.classe_do_ticker` e o coletor de preços (`coletor_padrao`) a reconhecer a classe.
6. **Testes:** copie o padrão de `tests/test_educacao.py` e de `tests/test_plataforma.py` (que já confere classes coerentes entre módulos).

## Limitações conhecidas
Veja `AUDITORIA.md` (seção de pendências e limitações).
