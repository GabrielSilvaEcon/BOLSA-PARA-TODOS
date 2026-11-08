# Competição de carteiras virtuais

Cada pessoa recebe R$ 100.000 virtuais, monta uma carteira com ativos líquidos e disputa um ranking de **retorno em %**. O lucro vira
capital e pode ser reinvestido (manualmente ou com reinvestimento automático de proventos). Sem aportes, sem dinheiro real.

## Arquivos
| Arquivo | Papel |
|---|---|
| `competicao.py` | Regras e cálculos (lógica pura): ordens, fechamento do dia, proventos, desdobramentos, ranking |
| `competicao_job.py` | Fechamento diário (fora do Streamlit): baixa cotações, valoriza carteiras, publica o ranking |
| `competicao_app.py` | Tela: ranking, ligas, minha carteira, negociar, regras |
| `competicao_ligas.py` | **Etapa 2** · ligas de amigos e avisos de posição (lógica pura) |
| `banco.py` (final) | Funções `comp_*`, `comp_liga_*` e `sis_comp_*`; **sem tabela nova** (usa `monitor_estado` e `config_sistema`) |
| `planos.py` | `comp_ordens_dia` (ordens por dia: 0 / 5 / 20 / 60) e, na etapa 2, `comp_ligas_criar`, `comp_ligas_entrar`, `comp_liga_membros` |
| `.github/workflows/competicao.yml` | Agenda o fechamento (18h30 de Brasília, dias úteis, com tentativa de reserva) |

## Como funciona
1. A pessoa entra na competição (apelido público + aceite) e envia ordens. Elas ficam em `comp_ordens` (só o app grava).
2. Depois do pregão, `competicao_job.py` baixa o fechamento do universo líquido, aplica cada pregão a cada carteira (`comp_cart`, só o job grava) e
   publica `comp_ranking` (apelido e retorno %) e `comp_precos` (cotações). A tela só lê esses documentos: sem consulta de preço por usuário.
3. Ordens executam no **preço de fechamento** (até as 17h valem para o mesmo dia; depois, para o próximo pregão).

## Etapa 2 · Ligas de amigos e avisos de posição
- **Liga privada por código ou link.** Quem tem plano Plus ou Premium cria a liga (nome + código de 8 caracteres, ex.: `K7QM-2XPA`) e compartilha o código ou o link
  `…/competicao?liga=K7QM2XPA`. **Qualquer pessoa entra** (inclusive no plano Gratuito); criar é o diferencial pago. A liga global continua sendo o ranking geral.
- **Limites por plano** (editáveis em Administração > Consumo > Planos e limites): criar ligas 0 / 0 / 3 / 10, entrar em ligas 0 / 3 / 10 / 30, membros por liga criada 0 / 0 / 30 / 100
  (Visitante / Gratuito / Plus / Premium). O limite de membros é gravado na liga no momento da criação.
- **Ranking da liga:** mesmas regras do geral (retorno em %, 5 pregões), com Geral, Mês e Semana. Quem ainda não tem pregões suficientes aparece em "ainda sem pregões".
  Mostra só apelido e retorno %, e só para os membros.
- **Avisos** (notificação no app e, se a pessoa ligou, e-mail/Telegram/push, com as regras de horário e importância dela):
  ranking geral: entrada no ranking, chegada ao Top 100, Top 10, Top 3 e 1º lugar, e perda da liderança; ligas: um aviso por dia reunindo todas as ligas em que a posição mudou.
  Cada tipo se desliga na aba Ligas. Não há valores em reais nos avisos.
- **Como é guardado (sem tabela nova):** `comp_ligas` (documento da pessoa, só ela grava) · `comp_liga|CÓDIGO` (definição: nome, limite, hash do dono; sem e-mail) ·
  `comp_lr|CÓDIGO` (ranking da liga, só o fechamento grava). Entrar numa liga é gravar o código no próprio documento, então não há disputa de escrita entre amigos.
- **Isolamento:** `comp_liga_ranking_ler` só entrega o ranking a quem tem o código no próprio documento; `comp_liga_encerrar` só aceita o dono; a consulta de uma liga antes de entrar
  devolve só nome e tamanho. Código errado: 6 tentativas por sessão e limite de rajada por minuto.
- **Liga cheia:** vale quem entrou primeiro; os excedentes veem o aviso de liga lotada. **Encerrar:** só o dono (apaga liga e ranking). **Excluir a conta** apaga as ligas que a pessoa criou.
- **Convite por link:** o código fica na sessão e aparece na aba Ligas; se a pessoa ainda não está na competição, ela entra primeiro e aceita depois.

## Regras fixas (constantes em `competicao.py`)
Capital inicial 100 mil · custo 0,05% por operação · no máximo 40% do patrimônio em um ativo · 5 pregões para entrar no ranking · ordens só em cotas inteiras.

## Ativar
1. Suba os arquivos novos e os três alterados (`banco.py`, `planos.py`, `app.py`); faça Reboot no Streamlit Cloud.
   **Etapa 2:** suba também `competicao_ligas.py` (novo) e as versões novas de `banco.py`, `planos.py`, `competicao_app.py`, `competicao_job.py` e `tests/test_competicao_ligas.py`. O `app.py` não muda.
   Não há tabela nem script SQL novo. O workflow continua o mesmo.
2. Confirme que o banco de configuração (`config_sistema`) e o monitor (`monitor_estado`) já existem no Supabase (rode o script SQL de Administração > Sistema se faltar).
3. No GitHub, use os mesmos segredos do monitor (`BPT_SUPABASE_URL`, `BPT_SUPABASE_KEY`). Rode o workflow **competicao** uma vez manualmente
   (Actions > competicao > Run workflow). Fora do horário, o job não faz nada; para testar, rode `python competicao_job.py --forcar` localmente com as variáveis.
4. Na tela Administração > Consumo > Páginas por plano, a página **Competição** nasce liberada para todos (não está na lista de páginas trancadas).

## Testes (sem internet)
`pytest tests/test_competicao.py tests/test_competicao_job.py tests/test_competicao_app_fumaca.py tests/test_competicao_ligas.py`
(o último cobre a etapa 2: códigos, ranking das ligas, isolamento no banco, fechamento completo com avisos, e preferências).

## Limites conhecidos
- Cotações do Yahoo são gratuitas, podem atrasar ou falhar: se mais da metade falhar, o fechamento não publica nada e tenta de novo.
- Dividendos entram no caixa na data "ex"; desdobramentos ajustam a quantidade. Eventos raros (bonificação, subscrição) não são tratados.
- O apelido é único por conferência no cadastro; cadastros simultâneos com o mesmo apelido são resolvidos no fechamento (fica o mais antigo).
- Com mais de alguns milhares de participantes, vale migrar `comp_cart` para uma tabela própria e o ranking para uma consulta no banco.
- Ligas: a contagem de vagas e o ranking usam leitura de todos os documentos `comp_ligas` (como a conferência de apelido); com milhares de participantes, vale migrar para tabelas próprias.
- Quem sai da liga ou é suspenso deixa de aparecer no próximo fechamento; o aviso de posição usa o ranking do fechamento anterior, então nunca há aviso no primeiro dia.
- Um link de convite aberto por quem ainda não fez login depende de o login preservar o endereço; se perder, a pessoa digita o código na aba Ligas.
- Prêmios em dinheiro exigem análise jurídica (promoção comercial). A competição nasce sem prêmios.
