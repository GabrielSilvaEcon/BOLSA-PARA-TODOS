# TickerCoins (TC) — como funciona e como configurar

TickerCoins são créditos de uso dentro do app. Não são dinheiro, investimento nem valor mobiliário; não têm saque, transferência, venda nem conversão. São independentes do XP da Jornada, dos pontos do Wallet Game e das carteiras de investimento.

## Onde aparece
Aprender → **Minha carteira de moedas** (saldo, histórico, benefícios ativos), **Central de recompensas** (como ganhar, limite do dia, anúncios) e **Loja Ticker**. No topo da Jornada há uma faixa com o saldo e atalhos. Ao terminar uma lição aparece "+N TickerCoins".

## Como ganha
Valores em `tickercoins.CFG_PADRAO` (e editáveis no painel): lição concluída (5), lição sem erro (+2), revisão diária (1), conquista (10), desafio (8). Cada fato paga uma vez só. Teto diário de ganhos por estudo: 40 TC.

## Segurança
Saldo = última linha do livro-razão (`tc_livro`), no servidor. Cada lançamento tem chave única (idempotência) e número de ordem por conta com índice único (concorrência: dois pedidos simultâneos nunca passam do saldo). O navegador nunca envia valores.

## Loja
Só o que o app entrega de verdade: distintivos e molduras (personalização) e "+10 atualizações de notícias / mensagens de IA / resumos de IA hoje" (válidos até a meia-noite). Quem já tem Premium não compra os extras de limite. Educação e Experiências aparecem como "em preparação" (não há conteúdo exclusivo real ainda). Falha na entrega devolve as moedas.

## Administrador (Administração → TickerCoins)
Estatísticas, buscar conta por e-mail, histórico e integridade do livro, ajuste (+/−) com justificativa obrigatória, preços e ativação de produtos, valores das recompensas, limite diário, anúncios, compras recentes com estorno e tentativas suspeitas. Tudo é auditado. Só administrador altera; suporte só vê.
Campanhas (multiplicador por período) ficam em `tc_config.campanhas`: `[{"id","rotulo","multiplicador","inicio","fim"}]` com datas ISO UTC.

## Supabase
Rode de novo o script SQL de Administração → banco (é idempotente): cria `tc_livro` e `tc_compras`. No SQLite local as tabelas são criadas sozinhas.

## Anúncios recompensados (para ligar de verdade)
Não há simulação. Falta: (1) contratar um provedor (ex.: AdMob no app Android; um provedor web no navegador); (2) criar uma classe que herde `ProvedorAnuncio` com `configurado()` e `verificar(payload)` (valida a assinatura/SSV do provedor e devolve `{"tx","conta_id"}`); (3) registrá-la com `registrar_provedor`; (4) guardar as chaves nos secrets, nunca no código; (5) ligar "Anúncios" no painel. Enquanto isso a tela mostra "em preparação".
