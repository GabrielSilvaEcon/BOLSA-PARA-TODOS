# Etapa 1 — Auditoria de APIs, fontes de dados e custos

Data: 2026-11-05. Só análise: nenhum código, chave ou cálculo foi alterado. Tudo abaixo foi confirmado lendo o código do repositório; o que não foi possível confirmar está marcado como **desconhecido**, com o jeito de verificar. Nenhuma fonte paga está ativa por decisão do projeto.

## 1. Fontes e provedores (confirmados no código)

| Provedor | Tipo | O que fornece | Classes | Chave | Custo | Módulos (arquivos principais) |
|---|---|---|---|---|---|---|
| Yahoo Finance (yfinance) | não oficial | cotação, histórico, fundamentos, proventos, caixa | ações, ETFs, FIIs, fundos no exterior, câmbio, treasuries | não | grátis | dados, mercados, evolucao, fundos_app, recursos, crescimento, app |
| Brapi | grátis c/ chave | cotação, proventos, caixa | ações, FIIs, ETFs BR | BRAPI_TOKEN | grátis | dados, fonte_reserva, comparador_fontes, monitor |
| Fundamentus | raspagem de página pública | indicadores fundamentalistas | ações e FIIs BR | não | grátis | dados, fiis, fiis_app, intel, risco, gestao_app |
| Financial Modeling Prep | grátis c/ chave (reserva) | cotação e fundamentos EUA | ações EUA | FMP_API_KEY | grátis | fonte_reserva |
| CVM dados abertos | oficial | fundos, FIIs | fundos, FIIs | não | grátis | fiis_cvm, fundos, fundos_app |
| Banco Central (SGS, Olinda) | oficial | Selic, CDI, IPCA, câmbio, expectativas | macro, renda fixa | não | grátis | dados, mercados, renda_fixa_app, noticias_* |
| IBGE, Ipeadata | oficial | inflação, séries macro | macro | não | grátis | dados, leitura_macro, noticias_* |
| Tesouro Transparente | oficial | preços e taxas do Tesouro Direto | renda fixa | não | grátis | mercados, renda_fixa |
| Fed, BLS, SEC, BCE | oficial | calendários e dados macro EUA/UE | macro | não | grátis | noticias_app, noticias_eventos |
| B3, ANBIMA | oficial | páginas de apoio/links | — | não | licenciados para dados | recursos, edu_conteudo (só referência) |
| CoinGecko (Demo) | grátis | preço, mercado, tokenomics | cripto | COINGECKO_KEY (opcional) | grátis | cripto, cripto_analise, cripto_app, analise_defi, fundamentalista_cripto, setorial, comparador_dados |
| Binance (dados públicos, ccxt) | grátis | velas e preço | cripto | não | grátis | app (técnica), cripto, monitor, comparador_dados |
| CoinMarketCap (Basic) | grátis c/ chave (reserva) | preço | cripto | CMC_API_KEY | grátis | comparador_dados/fontes |
| DefiLlama | grátis | TVL, stablecoins, receitas | cripto/DeFi | não | grátis | analise_defi, cripto, fundamentalista_cripto |
| mempool.space, Blockchair, Blockchain.info, Snapshot, Dune | grátis | dados on-chain e governança | cripto | Dune: DUNE_API_KEY | grátis | cripto_analise, cripto_app, noticias_eventos |
| Google Notícias (RSS) | público | manchetes | todas | não | grátis | noticias_app, intel_app |
| TradingView (widget) | embutido | gráfico no navegador do usuário | todas | não | grátis | app, tecnica, guias |
| Google Gemini | IA | assistente | todas | GEMINI_API_KEY | grátis (cota do Google) | assistente, educacao_app |
| Anthropic (Claude) | IA | assistente (opcional) | todas | ANTHROPIC_API_KEY | **PAGA** | assistente |
| Supabase | banco | contas, perfis, notificações | — | URL/KEY | grátis (plano free) | banco, monitor |
| ntfy.sh, Telegram, SMTP | notificação | entrega de alertas | — | tópico/token/senha | grátis | canais, notif |
| GitHub Actions | agendador | roda o monitor | — | secrets | grátis em repositório público | monitor.yml |

Catalogados no código mas **sem uso ativo** (desativados): Twelve Data, Alpha Vantage, Finnhub, HG Brasil, B3 licenciada (`comparador_fontes.py`). Não aparece no código: Polygon, APIs de corretoras.

**Único ponto potencialmente pago:** `assistente.py` aceita ANTHROPIC_API_KEY. Se a chave do Gemini existir, o Gemini é usado; se só a da Anthropic existir, cada pergunta de usuário gera cobrança. **Ação sua (sem me mandar a chave):** conferir nos Secrets do Streamlit se ANTHROPIC_API_KEY existe; se existir e você não quer cobrança, apagá-la.

## 2. Limites e consumo

Limites **já documentados no próprio código** (`comparador_fontes.py`, conferidos em 2026-11-04 nos sites dos provedores):
- CoinGecko Demo: 100/min e 10 mil créditos/mês. CoinMarketCap Basic: 50/min e 15 mil créditos/mês.
- Brapi grátis: 15.000 requisições/mês, 1 ativo por consulta, histórico de 3 meses.
- FMP grátis: 250/dia, só bolsas dos EUA; exibir/redistribuir exige licença de dados.
- Twelve Data 8/min e 800/dia; Alpha Vantage 25/dia; HG Brasil 400/dia (desativados).

**Desconhecidos (não confirmados):** limite do Yahoo (não publicado, bloqueia por IP do servidor); limites de Binance (por peso/IP), DefiLlama, mempool, Blockchair, Snapshot, Dune, Google Notícias, Fundamentus (raspagem, sem contrato); cota do Gemini (muda com o modelo; ver ai.google.dev/pricing); capacidade do Streamlit Cloud (CPU/memória por app; ver docs.streamlit.io). Como verificar: página de preços/termos de cada provedor; não presumir.

**Uso comercial (muito importante antes de cobrar assinatura):** Yahoo e Fundamentus não têm licença comercial; FMP exige contrato para exibir dados; Brapi trata o plano grátis como "protótipo sem receita"; CoinGecko Demo não informa licença comercial; CoinMarketCap Basic permite uso integrado ao produto, sem revenda. Fontes oficiais (BCB, CVM, IBGE, Tesouro) são dados abertos. **Conclusão: a base de ações/FIIs depende de fontes não licenciadas para uso comercial. É o maior risco jurídico da Fase 2.**

## 3. Mecanismos que já existem
- **Cache:** `st.cache_data` com TTL em ~20 arquivos (cotações 10 s–15 min, fundamentos 1 h, histórico 6 h, cadastro 24 h). O cache do Streamlit é compartilhado por todos os usuários da mesma instância, mas **apaga quando o app dorme ou reinicia**.
- **TTL padrão do projeto** em `comparador_fontes.TTL` (cotação 15 min, histórico 6 h, câmbio 1 h, macro 12 h, cadastro 24 h) — usado só pelo comparador; os demais módulos têm TTL próprio.
- **Limitador e tentativas** (`Limitador`, `com_tentativas`) — usados só pelo comparador.
- **Tratamento de 429 e espera:** cripto.py e analise_defi.py (respeita Retry-After), fonte_reserva (pausa de 10 min após limite).
- **Contingência:** Yahoo → Brapi/Fundamentus (ações BR); Yahoo → FMP (EUA); CoinGecko → Binance/CMC (cripto); aviso explícito quando nenhuma responde, sem inventar valor.
- **Monitor:** máx. 80 ativos distintos por execução, cache dentro da execução, para após falhas seguidas.
- **Rede:** `http_seguro` registra domínios e impede SSRF (não conta consumo).

## 4. Consumo por módulo
Ações/fundamentalista/DCF/múltiplos/dividendos: Yahoo + Fundamentus + Brapi (+FMP). Técnica de ações: Yahoo; técnica cripto: Binance (ccxt). FIIs: Fundamentus + CVM + Yahoo. Cripto: CoinGecko + DefiLlama + on-chain. ETFs/fundos: Yahoo + CVM. Renda fixa: BCB + Tesouro. Comparador: Yahoo, BCB, Tesouro, CoinGecko, Binance. Scanner/Ranking: Yahoo + Fundamentus em lote (4 threads). Carteira/gestão/risco: Yahoo + Fundamentus (8 threads no risco). Notícias: Google RSS + oficiais (6 threads). IA: Gemini. Alertas/monitor: mesmas fontes de cotação, via GitHub Actions. Simuladores, relatórios, educação: dados já obtidos (educação usa cotação com cache de 15 min).

## 5. Pontos de desperdício / risco (confirmados)
1. **Cache por módulo, não central:** o mesmo ativo pode ser buscado por funções diferentes (preço justo, técnica, carteira, risco, comparador) com chaves de cache distintas, multiplicando chamadas ao Yahoo.
2. **Cache some quando o app dorme/reinicia**, repetindo tudo ao acordar.
3. **Atualização automática de 30 s** (`st.fragment run_every=30`) na análise técnica de cripto por sessão aberta; depende do cache de 10–15 s para não multiplicar por usuário.
4. **Monitor:** ~44 execuções/dia úteis (a cada 15 min, 12h–22h UTC) + 6/dia a cada 4 h. Com até 80 ativos por execução, o teto teórico é ~4.000 leituras/dia, sem cache entre execuções. Confirmado no código: cripto vai para a Binance; ações vão para o Yahoo e só caem na Brapi se o Yahoo falhar. Ou seja, o monitor pressiona o **Yahoo** (risco de bloqueio do IP do GitHub) e, nas falhas, a Brapi (15.000/mês acabariam em ~4 dias se todas as leituras caíssem nela). *(O volume real por execução não foi medido.)*
5. **Sem limitador global:** só o comparador usa o `Limitador`; Yahoo, Fundamentus e Binance não têm controle de ritmo próprio além do cache.
6. **Sem contador de consumo:** o app não registra quantas chamadas fez a cada provedor, então hoje não dá para saber quanto da cota foi gasta.
7. **Concorrência:** threads (4–8) disparam várias consultas em paralelo ao mesmo provedor; não há trava para o mesmo ativo pedido por duas sessões ao mesmo tempo (comportamento do `cache_data` nesse caso: não confirmado).
8. **Yahoo bloqueia IP do servidor**, não usuário: qualquer pico pode derrubar todos (o próprio app já avisa isso na tela).
9. **IA:** cada pergunta é uma chamada individual, sem cache e sem limite por usuário no código (não confirmado limite por plano).

## 6. Oportunidades de economia
Cache central único por (ativo, tipo de dado) com TTL por tipo; persistir o cache no Supabase (sobrevive a reinício e é compartilhado com o monitor); contador e limitador por provedor; atualização programada (GitHub Actions) dos ativos mais vistos, em vez de sob demanda; dados lentos (cadastro, balanços, macro) com TTL de dia/semana, dados rápidos (cotação) em minutos; mesma rodada do monitor aproveitar o cache do app; limitar IA por usuário/plano; preferir fontes oficiais onde existirem (CVM, BCB, Tesouro) e reservar Yahoo para cotação/histórico.

## 7. Cenários de crescimento (HIPÓTESES, não medições)
Premissas: cada usuário ativo olha ~5 ativos/dia; 50% se repetem entre usuários; universo ~2.000 ativos (ações, FIIs, ETFs, cripto); cache médio de 1 h com ~3 chamadas por ativo por consulta e ~8 janelas de uso por dia; 5% dos usuários usa a IA, 10 mensagens/dia; cache zera em reinício.

| Usuários | Ativos distintos/dia (hip.) | Chamadas de mercado/dia (hip.) | Mensagens de IA/dia (hip.) |
|---|---|---|---|
| 100 | ~600 | ~14 mil | ~50 |
| 500 | ~1.800 | ~43 mil | ~250 |
| 1.000 | ~2.000 (teto) | ~48 mil | ~500 |
| 5.000 | ~2.000 | ~48 mil | ~2.500 |
| 10.000 | ~2.000 | ~48 mil | ~5.000 |

Leitura: com cache compartilhado o consumo de mercado depende de **quantos ativos distintos**, não de quantos usuários, e se achata no teto; o que cresce com usuários é a **IA**, o **banco/Supabase**, as **notificações** e a **CPU/memória de uma única instância** do Streamlit Cloud (limite desconhecido, é o primeiro gargalo provável acima de algumas centenas de usuários simultâneos). Esgotamento provável: Brapi (500/dia) já em qualquer cenário se for a fonte principal; FMP (250/dia) acima de ~100 ativos EUA/dia; Yahoo por bloqueio de IP em picos; Gemini a depender da cota (desconhecida). Não há custo em R$ estimado: todas as fontes ativas são gratuitas e os preços de upgrade não foram pesquisados.

## 8. Arquitetura recomendada (não implementada)
Uma camada única `provedores` (novo módulo) entre os módulos e as fontes, reaproveitando `comparador_fontes` (catálogo, TTL, Limitador, cadeia de fontes):
1. **Catálogo + limites configuráveis** (diário/mensal/por minuto) guardados no Supabase e editáveis no painel Administração.
2. **Contador de consumo** por provedor/módulo/usuário (tabela nova `consumo`).
3. **Cache central** (memória + Supabase) por (ativo, tipo), com TTL por tipo.
4. **Fila e prioridade:** usuário pago > gratuito > monitor; consultas não essenciais suspensas quando a cota chega a um limite (ex.: 80%).
5. **Chamada única:** todos os módulos pedem dados por essa camada; nenhum chama `yf`/`requests` direto.
6. **Painel admin:** consumo, cota restante, erros, chave de suspensão por provedor.
Arquivos envolvidos: dados.py, recursos.py, mercados.py, cripto*.py, fundos*.py, fiis*.py, comparador_*.py, monitor.py, assistente.py, banco.py (novas tabelas), conta_app.py (painel), app.py (leituras diretas de yfinance/ccxt).

## 9. Ordem recomendada
1. Conferir os Secrets (ANTHROPIC_API_KEY) e consultar os termos de uso comercial (Yahoo, Fundamentus, Brapi, FMP, CoinGecko). 2. Contador de consumo (só medir). 3. Cache central + persistência. 4. Limitador por provedor. 5. Painel admin de consumo e limites. 6. Atualização programada e prioridade. 7. Limites por plano (IA primeiro). 8. Só então preços/assinaturas (Fase 2), já sabendo o custo real e as licenças.

## 10. Limites desta auditoria
Leitura de código e de catálogo; sem medição em produção, sem chamadas reais aos provedores e sem consulta atual aos sites de termos (as datas de conferência vêm do catálogo do projeto). Cenários são hipóteses.
