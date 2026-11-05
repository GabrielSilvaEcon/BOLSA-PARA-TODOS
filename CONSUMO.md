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
