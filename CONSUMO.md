# Controle de consumo das APIs (Etapa 2)

**O que faz:** conta os pedidos a cada fonte de dados (por dia e por mês), mostra no painel **Administração > Consumo** e, se o administrador quiser, bloqueia uma fonte quando o limite estoura ou quando ela é suspensa.

**Padrão seguro:** todas as fontes começam em modo **avisar** (só contam). Nada é bloqueado sem você escolher "bloquear".

## Como usar
1. Entre como administrador > Administração > **Consumo**.
2. Cada cartão mostra pedidos de hoje, do mês, limite e situação (verde = dentro, amarelo = perto, vermelho = estourou).
3. **Editar limites e bloqueios:** defina limites por minuto, dia e mês (0 = sem limite), escolha o modo e/ou marque Suspender. Salvar vale em até 1 minuto.
4. Se aparecer o aviso de tabela inexistente: no Supabase, rode o script SQL de novo (o mesmo de antes; é seguro repetir). Sem a tabela a contagem existe só enquanto o app está ligado.

## Como funciona
- Pedidos feitos com `requests` passam por `http_seguro`, que chama `consumo.antes(url)`; o domínio define o provedor.
- Yahoo (yfinance) é contado nos pontos de chamada de `dados.py` (não usa `requests`).
- O monitor (GitHub Actions) usa a mesma proteção e grava na mesma contagem.
- Limites iniciais vêm do catálogo conferido em 2026-11-04 (Brapi 15.000/mês, FMP 250/dia, CoinGecko 100/min e 10.000/mês, CoinMarketCap 50/min e 15.000/mês). As demais fontes não têm limite configurado: são desconhecidos.

## Limitações conhecidas
- Conta **pedidos**, não **créditos** (CoinGecko e outros podem cobrar mais de um crédito por pedido).
- O limite por minuto vale por processo (app e monitor separados).
- Dois processos gravando ao mesmo tempo podem perder poucos pedidos.
- Yahoo é contado só onde `dados.py` chama; usos do yfinance em outros módulos (mercados, fundos, evolução, recursos) ainda **não** entram na contagem.
- Chamadas do Gemini/Anthropic feitas por `urllib` (assistente) não passam por `requests` e ainda não são contadas.
- Bloquear uma fonte faz o módulo mostrar "dado indisponível"; a contingência existente (outra fonte) continua valendo.

# Cache central (Etapa 3)

`cache_central.py` substitui o cache padrão nas coletas de dados externos mais usadas (demonstrativos, preços e histórico longo do Yahoo, cripto, FIIs, BCB, Tesouro, ETFs e índices dos EUA).

- **Falha não fica guardada por horas.** Antes, se o Yahoo falhava, o "sem dados" ficava de 1 a 24 h no cache. Agora uma falha dura só 2 minutos.
- **Um pedido por vez.** Se vários usuários pedem o mesmo ativo ao mesmo tempo, a fonte recebe 1 pedido e os outros reaproveitam.
- **Dado antigo, com aviso.** Se a fonte cai e há um dado real anterior (até 24 h), ele é mostrado com a frase "A fonte não respondeu agora: estes são os últimos dados obtidos, de há X". Nada é inventado.
- **Painel:** em Administração > Consumo, os cartões "Cache central" mostram % de consultas evitadas, pedidos à fonte, dados antigos servidos e falhas.
- O botão **Atualizar dados** (menu lateral > Ajustes) limpa também este cache.

Limitações: o cache fica na memória do app (some quando o app dorme ou reinicia); as funções de `dados.py` (ações BR) continuam com o cache padrão, que já só guarda sucesso; guardar o cache no Supabase para sobreviver a reinícios ficou para uma próxima etapa.

# Atualização automática e prioridades (Etapa 4)

- **Cache que sobrevive a reinícios.** `cache_central` grava no Supabase (tabela `config_sistema`, ids `cache|...`) os resultados bons de até 250 KB, em formato JSON próprio (sem pickle). Quando o app acorda, lê de volta em vez de repetir tudo na fonte. Se a fonte cair, mostra o último dado real (até 24 h) com aviso. Cópias com mais de 3 dias são apagadas pelo monitor.
- **Aquecimento pelo monitor.** A cada execução (~15 min) o monitor lê alguns **ativos prioritários**, em rodízio, depois de cuidar dos alertas dos usuários. Os dados ficam prontos no cache. Não repete o que acabou de ler para os alertas, respeita o limite de 80 ativos por execução, e para depois de 3 falhas seguidas.
- **Lista editável:** Administração > Consumo > "Editar ativos prioritários" (padrão: 16 ações e 6 FIIs muito conhecidos e BTC, ETH, SOL). Dá para mudar a quantidade por execução (0 a 40) e desligar o aquecimento.
- **Ações brasileiras (Yahoo, Brapi, Fundamentus)** agora também usam o cache central.
- **Bloqueio do Yahoo:** se o administrador escolher "bloquear" ou "suspender" o Yahoo, as chamadas do `dados.py` passam a respeitar (antes só contavam).

Limitações: o aquecimento só vale para o que o monitor lê (histórico de 1 ano e indicadores do Yahoo); telas que pedem outro período ou outra fonte continuam indo à fonte na primeira vez. A cópia no banco depende do Supabase (plano grátis: cuide do espaço; cada item tem no máximo 250 KB). O monitor só roda se o repositório tiver atividade (o GitHub pausa agendamentos após 60 dias sem uso).

# Planos e limites de uso (Etapa 5)

Três planos (**Gratuito**, **Investidor Plus**, **Investidor Premium**) mais o **visitante** (sem conta). Os modos Iniciante, Intermediário e Avançado valem em todos os planos. Ainda não existe preço nem pagamento (Fase 2): o administrador define o plano de cada conta.

| Recurso | Visitante | Gratuito | Plus | Premium | Onde vale |
|---|---|---|---|---|---|
| Mensagens ao assistente de IA (por dia) | 3 | 5 | 30 | 100 | chat do assistente |
| Resumos com IA (ativos distintos, por dia) | 5 | 10 | 40 | 120 | resumos fundamentalista, cripto, ETF |
| Botão "Atualizar dados" (por dia) | 2 | 3 | 10 | 30 | menu lateral (limpa o cache de todos) |
| Alertas de mercado ativos | 3 | 3 | 15 | 50 | Central de notificações |
| Intervalo mínimo do monitor (min) | 60 | 60 | 30 | 15 | monitor automático |
| Posições na carteira / ativos no comparador | — | 15 / 3 | 60 / 6 | 300 / 10 | **ainda não aplicado** (só catalogado) |

- **Os números são pontos de partida**, escolhidos para proteger as cotas gratuitas; não vêm de custo medido. Edite em Administração > Consumo > Planos e limites.
- Administrador e suporte usam os limites do Premium. Conta sem registro = Gratuito.
- O uso diário conta pelo dia de Brasília e renova à meia-noite. Resumos de IA do mesmo ativo no mesmo dia contam uma vez só.
- A pessoa vê seu plano e o uso do dia em **Minha conta > Painel**.
- Se o banco falhar, o recurso é liberado (nunca se bloqueia por falha nossa).
- Limites do visitante valem por sessão do navegador (quem abre outra sessão recomeça). O limite real fica nas contas.

# Proteção contra esgotamento das APIs gratuitas (Etapa 6)

- **Modo "proteger"** (padrão para toda fonte com limite conhecido: Brapi, FMP, CoinGecko, CoinMarketCap): o **aquecimento** do monitor para ao chegar na **reserva** (padrão 70% do limite), guardando o resto para quem está usando o app; tudo para em **100%**. Os modos "avisar" (só conta) e "bloquear" (tudo para em 100%, sem reserva) continuam disponíveis por fonte.
- **Disjuntor:** se uma fonte falha 6 vezes seguidas em 5 minutos (ou devolve erro 429, que pesa 3), ela é **pausada por 10 minutos** para todos. Nesse tempo o app usa a fonte reserva ou o último dado guardado (cache central), em vez de insistir e ser bloqueado. Valores editáveis no painel; o botão de suspender continua valendo em qualquer modo.
- **Aviso ao administrador:** o monitor cria uma notificação na Central quando uma fonte passa de **80%** e de **100%** do limite diário ou mensal (uma vez por nível por dia).
- **Total do mês** agora fica em um único registro (leitura barata). Meses anteriores à Etapa 6 são somados dia a dia na primeira leitura.
- **Painel:** Administração > Consumo mostra "Pausada por falhas (N min)" nas fontes com disjuntor aberto, e permite mudar modo, reserva, número de falhas e pausa.

Limitações: o disjuntor vale por processo (o app e o monitor têm o seu); só fontes contadas entram (as que usam `requests` e o Yahoo via `dados.py`; os outros usos do yfinance e as chamadas de IA por urllib ainda não); os limites padrão vêm do catálogo conferido em 2026-11-04 e podem mudar nos provedores; limites de fontes sem valor conhecido (Yahoo, Binance etc.) precisam ser definidos por você depois de observar o consumo.

## Etapa 7 — Painel de custos e consumo (administração > Custos)

- **custos.py**: o administrador informa o orçamento mensal, os custos fixos (hospedagem, domínio…) e o preço por 1.000 pedidos de cada fonte paga. O app calcula gasto até agora, projeção do mês (ritmo médio) e % do orçamento. São **estimativas** a partir dos valores informados; o app não enxerga faturas.
- **Painel**: cartões de gasto/projeção/orçamento, cartão por fonte, gráfico dos últimos 14 dias, uso por recurso hoje (`planos.uso_agregado_hoje`), CSV do histórico (`consumo.historico`) e edição do orçamento/custos (auditada em `custos.config`).
- **Alertas**: o monitor avisa os administradores quando a projeção chega a 80% do orçamento ou o ultrapassa (uma vez por nível e mês).
- Nenhuma tabela nova; usa `config_sistema` (`custos_cfg`).

## Etapa 8 — Preços, receita e margem (administração > Preços)

- **precificacao.py**: o administrador define o preço mensal dos planos Plus e Premium, a taxa do meio de pagamento (% + valor fixo) e a margem alvo. Com o número real de contas por plano (`planos.contagem_por_plano`) e o custo projetado do mês (`custos.calcular`), calcula receita bruta, taxas, receita líquida, lucro, margem, ponto de equilíbrio por plano e o preço mínimo para a margem alvo.
- **Simulador** no painel: "e se eu tivesse N assinantes?" (não altera nada).
- Preços, taxas e meta ficam em `config_sistema` (`precos_cfg`). Taxas começam em 0 até a escolha do meio de pagamento (Etapa 9). Ainda **não há cobrança**: tudo é estimativa.

## Etapa 9 — Planos e assinaturas (sem provedor de pagamento)

- **Validade**: `planos.definir_plano(email, plano, dias=None)` grava plano, validade (`ate`), início e origem. Sem `dias` = sem validade. Plano vencido volta ao Gratuito sozinho (o último dia ainda vale); nada é apagado. Admin/suporte seguem Premium.
- `planos.renovar` soma dias a partir do vencimento (ou de hoje, se já venceu); `listar_assinaturas`, `assinatura_de` e `contagem_por_plano` (ignora vencidas) alimentam os painéis.
- **Admin** (Consumo > Assinaturas): em dia / vencem em 7 dias / vencidas, tabela de assinantes, dar-renovar plano com validade de 30/90/180/365 dias ou sem validade. Cancelar = aplicar Gratuito.
- **Usuário** (Minha conta): cartão "Validade do plano" (alerta em 7 e 3 dias) e aviso se a assinatura venceu.
- **Pagamento automático não foi ligado**: fica no trabalho sujo (TRABALHO_SUJO.md). O admin ativa o plano à mão depois de receber o pagamento.

## Etapa 10 — Controle de acesso por assinatura

- O plano efetivo da conta (`planos.plano_de`, já considerando a validade) decide os limites em todos os pontos de uso. Agora os 7 recursos catalogados são aplicados:
  - **Posições na carteira** (`carteira_posicoes`): ao adicionar um ativo NOVO à carteira (real ou fictícia). Mais lotes de um ativo que já está na carteira não contam.
  - **Ativos no comparador** (`comparador_ativos`): o comparador usa os N primeiros e avisa; nunca passa do teto técnico do app (8). Padrões: visitante 3, gratuito 4, plus 6, premium 8.
  - Já aplicados antes: mensagens e resumos de IA, atualizar dados, alertas, intervalo do monitor.
- Nada é removido de nenhum plano: todos continuam acessando todos os módulos; só mudam as quantidades, ajustáveis em Administração > Consumo > Planos e limites.
- Falha ao ler o plano nunca bloqueia (`limite_atual` devolve "sem limite"). Assinatura vencida volta ao limite do Gratuito.

## Etapas 11, 12 e 13 — Carência, cancelamento, renovação, cupons e teste grátis (assinaturas.py)

Sem provedor de pagamento: o administrador ativa/renova à mão; o resto é automático. Tudo em Administração > Assinaturas (regras e cupons) e Minha conta > "Assinatura: cupom, teste grátis e cancelamento".

- **Carência / inadimplência (11)**: depois do vencimento o plano continua valendo por N dias (padrão 3); passado o prazo volta ao Gratuito sozinho (nada é apagado). Renovar dentro da carência continua a contar do vencimento antigo. Painel mostra "Em carência" e "Vencidas".
- **Cancelamento (11)**: o usuário cancela a renovação e mantém o plano até a validade (pode desfazer); plano sem validade volta ao Gratuito na hora. Histórico das últimas 20 mudanças fica na assinatura (visível ao usuário).
- **Avisos de renovação (11)**: o monitor (a cada execução) notifica o usuário N dias antes (padrão 7, 3, 1), no dia, durante a carência e quando o plano acaba; uma notificação por data/situação.
- **Cupons (12)**: código de 3–20 caracteres que dá X dias de Plus ou Premium; limite de usos, data de validade e liga/desliga. Uma vez por conta, 5 tentativas por dia por conta, não rebaixa quem já tem plano melhor, soma dias se já tem o mesmo plano.
- **Teste grátis (13)**: desligado até o administrador ligar; escolhe plano e dias (1–30); uma vez por conta e só para quem nunca teve plano pago; termina sozinho.
- Chaves em `config_sistema`: `assin_cfg`, `cupom|CÓDIGO`, `resgate|CÓDIGO|hash`, `cupom_tent|dia|hash`, `teste|hash`.
- Cupom e teste grátis usam um trinco no processo (sem uso duplo no mesmo instante). Vale por processo do app; o monitor não resgata cupons.

## Etapas 14 e 15 — Custo por usuário/recurso e prevenção de abuso (Administração > Uso)

- **custo_usuario.py (14)**: soma, nos últimos 1/3/7 dias, o uso de cada recurso diário por conta e multiplica pelo custo por uso (informado em Uso; padrão: IA = preço por 1.000 pedidos da fonte "ia" ÷ 1.000; demais R$ 0). Mostra por plano (usuários ativos, custo médio/mês projetado por usuário, receita líquida de uma assinatura, quanto sobra), por recurso e os 10 maiores consumos. Só o administrador vê e-mails (guardados em `uso|dia|hash` como `_e`).
- **abuso.py (15)**: (1) rajada: no máximo N usos por minuto de IA/atualizar dados por pessoa (padrão 8; visitante por sessão); (2) cada vez que alguém bate no limite do plano o app conta (`_neg`); passando de X no dia (padrão 15) a conta aparece em "Uso fora do padrão" e o monitor avisa os administradores (uma vez por conta/dia). **O app nunca suspende conta sozinho.**
- Já existiam: login com bloqueio por tentativas (seguranca), 5 tentativas/dia de cupom (Etapa 12), SSRF/limites HTTP (http_seguro).
- Limites: a rajada vive na memória do processo (reinicia com o app); o custo mede só recursos limitados por plano — o custo de leitura de dados é compartilhado (cache) e aparece em Custos.

## Etapas 16, 17 e 18 — Otimização, continuidade e carga

- **manutencao.py (16)**: faxina diária (monitor) de contadores antigos; buscas por prefixo (`comeca`) no banco; painel "Tamanho do banco" em Administração > Continuidade.
- **Continuidade (17)**: verificações reais (banco, monitor, cache, fontes pausadas, backup) e backup/restauração cifrados das configurações (planos e validades, cupons, resgates, testes, regras). Contadores e cache não entram no backup.
- **Carga (18)**: `tests/test_carga.py` com threads reais. Achou e corrigiu corridas nos limites do plano, nos limites de fonte e no uso de cupom. Números e limites em AUDITORIA_FINAL.md.
- **Etapa 19**: AUDITORIA_FINAL.md (rentabilidade, segurança, o que ainda não foi comprovado).

## Meu modo de experiência (troca livre Iniciante · Intermediário · Avançado)
- Regras em `experiencia.py` (puro); telas em `experiencia_app.py`. O modo fica em `prefs["modo"]` (salvo na conta, vale em qualquer aparelho e após novo login).
- Troca: grátis, ilimitada, sem justificativa; seletor no menu lateral, no menu do celular e em Minha conta > Preferências, sempre com **prévia e confirmação**.
- Muda só a apresentação: menu (Iniciante agrupa as ferramentas avançadas em "Mais ferramentas"; Avançado as coloca no topo), faixa explicativa/nota técnica por tela, painel (Iniciante mais enxuto se a pessoa nunca o personalizou), colunas de indicadores nas tabelas (favoritos primeiro; "Ver todos" sempre disponível), grade/guias dos gráficos, tom do assistente de IA e dos resumos, explicações e detalhes técnicos dos alertas, nível de leitura da Educação.
- Personalização dentro do modo (`prefs["exp"]`): quantidade de informações, explicações educativas, dicas nas telas; mais indicadores/ativos/painel favoritos em Preferências.
- Nunca toca carteiras, operações, histórico, alertas, relatórios, cálculos, progresso educacional, assinatura ou preço. Os três modos têm as mesmas ferramentas e classes de ativos. Auditoria: `experiencia.modo_trocado`.
- Testes: `tests/test_experiencia.py`.

### Leitura por modo nas telas (leitura.py)
Cada tela de análise mostra, no topo, "Leitura do resultado": o mesmo resultado explicado para cada nível (Iniciante sem siglas e com "o que significa"; Intermediário com os números principais; Avançado com fórmula e entradas). Cobertas: Preço justo, Múltiplos, Dividendos, DCF, Saúde financeira, Análise técnica (ações), Economia e Ranking. No Iniciante, os cabeçalhos das tabelas de Múltiplos, Dividendos e Saúde financeira aparecem por extenso. Só texto de apresentação: números e cálculos vêm da própria tela.

Segunda leva: o rótulo de TODO cartão de indicador do app (`tema.card_status`: Fundos, ETFs, Risco, Gestão, Relatórios, Renda fixa, Simulador, Comparar, Inteligência) ganha, no Iniciante, nome por extenso e uma explicação em palavras simples; no Avançado, a definição técnica (dicionário em `leitura.DICIONARIO`). Leituras próprias também em FIIs, simulação de Tesouro/CDI e Criptomoedas. Intermediário não muda.
