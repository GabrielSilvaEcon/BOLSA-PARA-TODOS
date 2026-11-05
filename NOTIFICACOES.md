# Notificações inteligentes e monitoramento (Passo 23)

## Visão geral
- **Central de notificações** (menu Inteligência > Notificações): caixa de entrada, histórico, meus alertas, preferências/canais, monitoramento.
- **Monitor automático** (`monitor.py`): roda fora do Streamlit, no GitHub Actions (grátis), mesmo com o app fechado.
- **Motores já existentes foram reaproveitados**: Central de inteligência (`intel.py`), Notícias e eventos (`noticias_eventos.py`),
  Análise técnica avançada (`analise_tecnica.py`) e Gestão de risco (`risco.py`). Eles continuam nas páginas deles; os avisos que geram
  agora também são guardados na Central (`notif_app.registrar_disparos`).
- **Regras novas** (`notif.py`): preço acima/abaixo, valorização/queda %, máxima/mínima do período, variação incomum, mudança de indicador
  fundamentalista e limites de carteira, só para as classes compatíveis.

## Arquitetura
| Peça | Arquivo | Papel |
|---|---|---|
| Regras puras | `notif.py` | avaliação, compatibilidade por classe, deduplicação, agrupamento, prioridade, explicação, preferências |
| Banco | `banco.py` | tabelas `notificacoes`, `monitor_exec`, `monitor_estado`; posse conferida em cada função |
| Canais | `canais.py` | e-mail, Telegram, ntfy (push), com retentativas; nada é simulado |
| Monitor | `monitor.py` | trava por janela, cache, limites, retentativas, registro das execuções |
| Tela | `notif_app.py` | Central de notificações |
| Agendador | `.github/workflows/monitor.yml` | chama `python monitor.py` a cada 15 min (dias úteis, 9h–19h de Brasília) e a cada 4 h |

Fluxo de uma verificação: trava da janela → para cada conta ativa lê regras e preferências → busca cotações (cache entre contas, no máximo
80 consultas por execução, disjuntor se a fonte cair) → avalia → filtra por preferências → eleva prioridade se o ativo pesa na carteira →
remove repetidas e avisos parecidos dentro do intervalo mínimo → agrupa por ativo/categoria → grava → entrega nos canais permitidos.

## Canais realmente disponíveis
- **No aplicativo**: sempre. Guarda histórico por 180 dias.
- **E-mail**: usa o SMTP do Passo 21. Limite do Gmail: cerca de 500 por dia.
- **Telegram**: precisa do `bot_token` (BotFather, grátis). A pessoa vincula o chat enviando um código ao bot.
- **Push no celular (ntfy)**: grátis e sem cadastro; a pessoa assina um tópico secreto no app ntfy. Quem souber o tópico recebe os avisos.
- **Não existem**: push web nativo (exige service worker, impossível no Streamlit), SMS e WhatsApp (pagos).

## Como ligar o monitor (uma vez, no GitHub)
1. No Supabase, rode de novo o script SQL (Administração > Sistema). Ele é seguro de repetir e cria as tabelas novas.
2. GitHub > Settings > Secrets and variables > Actions > New repository secret. Crie:
   `BPT_SUPABASE_URL`, `BPT_SUPABASE_KEY` (a chave SECRETA, a mesma dos secrets do app).
   Opcionais: `BPT_EMAIL_SERVIDOR`, `BPT_EMAIL_PORTA`, `BPT_EMAIL_USUARIO`, `BPT_EMAIL_SENHA`, `BPT_EMAIL_REMETENTE`,
   `BPT_TELEGRAM_BOT_TOKEN`, `BPT_APP_URL`, `BRAPI_TOKEN`.
3. Aba Actions > "monitor" > Run workflow (primeira execução manual). Depois roda sozinho.
4. No app, aba Monitoramento mostra a última verificação.

## Limitações (sem rodeios)
- O GitHub pode atrasar execuções agendadas em alguns minutos, e desliga agendamentos de repositórios sem atividade por 60 dias (basta um commit).
- O monitor exige Supabase. Com SQLite local não há banco compartilhado.
- Notícias e eventos só são avaliados quando a pessoa atualiza a página (dependem de leitura de feeds); o monitor cobre preço, técnica, carteira e
  indicadores. Indicadores para criptomoedas (rede, oferta, TVL) e vacância de FIIs ficam na Central de inteligência, sem alerta automático.
- Cotações vêm de fontes gratuitas (Yahoo, Brapi, Binance de dados públicos) e podem atrasar ou falhar; quando falham, o monitor registra e tenta na próxima janela.
- O aviso de carteira usa as quantidades atuais da Carteira real e os limites de Gestão de risco; drawdown é uma aproximação.
- Nada compra, vende ou rebalanceia. Os avisos não são recomendação.

## Segurança e privacidade
- Posse conferida em `banco.py` (id + e-mail do ator); uma conta não lê, marca, arquiva nem apaga notificação de outra.
- Mensagens externas levam só o aviso (sem valores da carteira). Tokens vêm dos secrets e são mascarados nos logs.
- O monitor usa a chave secreta do Supabase só no GitHub Actions (Secrets do GitHub); o resumo das execuções não tem dados pessoais.
- Exportar meus dados (LGPD) inclui as notificações; excluir dados/conta apaga notificações e estado do monitor.
- Retenção: notificações 180 dias; registro do monitor 30 dias.

## Categoria "macro" (cenário econômico × carteira real)
- Só a carteira real (e renda fixa real) é cruzada; fictícia e ativos pesquisados nunca geram alerta.
- Tipos: mudança de cenário (neutro→bom/ruim, bom↔ruim), intensidade (nota mudou ≥0,30), risco forte novo (repete só após 14 dias). Mudança para neutro só avisa se a pessoa ativar. Primeira leitura só registra o ponto de partida.
- Ativos do mesmo setor viram um aviso só; dedup por semana; passa pelas preferências, pontuação e intervalo mínimo já existentes.
- O monitor recalcula o cenário no máximo a cada 3 h; o estado fica em `monitor_estado` (chave "macro").
