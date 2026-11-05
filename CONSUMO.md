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
