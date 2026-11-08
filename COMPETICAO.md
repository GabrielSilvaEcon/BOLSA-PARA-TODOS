# Competição de carteiras virtuais

Cada pessoa recebe R$ 100.000 virtuais, monta uma carteira com ativos líquidos e disputa um ranking de **retorno em %**. O lucro vira
capital e pode ser reinvestido (manualmente ou com reinvestimento automático de proventos). Sem aportes, sem dinheiro real.

## Arquivos
| Arquivo | Papel |
|---|---|
| `competicao.py` | Regras e cálculos (lógica pura): ordens, fechamento do dia, proventos, desdobramentos, ranking |
| `competicao_job.py` | Fechamento diário (fora do Streamlit): baixa cotações, valoriza carteiras, publica o ranking |
| `competicao_app.py` | Tela: ranking, minha carteira, negociar, regras |
| `banco.py` (final) | Funções `comp_*` e `sis_comp_*`; **sem tabela nova** (usa `monitor_estado` e `config_sistema`) |
| `planos.py` | Recurso `comp_ordens_dia` (ordens por dia: 0 / 5 / 20 / 60 nos planos Visitante / Gratuito / Plus / Premium) |
| `.github/workflows/competicao.yml` | Agenda o fechamento (18h30 de Brasília, dias úteis, com tentativa de reserva) |

## Como funciona
1. A pessoa entra na competição (apelido público + aceite) e envia ordens. Elas ficam em `comp_ordens` (só o app grava).
2. Depois do pregão, `competicao_job.py` baixa o fechamento do universo líquido, aplica cada pregão a cada carteira (`comp_cart`, só o job grava) e
   publica `comp_ranking` (apelido e retorno %) e `comp_precos` (cotações). A tela só lê esses documentos: sem consulta de preço por usuário.
3. Ordens executam no **preço de fechamento** (até as 17h valem para o mesmo dia; depois, para o próximo pregão).

## Regras fixas (constantes em `competicao.py`)
Capital inicial 100 mil · custo 0,05% por operação · no máximo 40% do patrimônio em um ativo · 5 pregões para entrar no ranking · ordens só em cotas inteiras.

## Ativar
1. Suba os arquivos novos e os três alterados (`banco.py`, `planos.py`, `app.py`); faça Reboot no Streamlit Cloud.
2. Confirme que o banco de configuração (`config_sistema`) e o monitor (`monitor_estado`) já existem no Supabase (rode o script SQL de Administração > Sistema se faltar).
3. No GitHub, use os mesmos segredos do monitor (`BPT_SUPABASE_URL`, `BPT_SUPABASE_KEY`). Rode o workflow **competicao** uma vez manualmente
   (Actions > competicao > Run workflow). Fora do horário, o job não faz nada; para testar, rode `python competicao_job.py --forcar` localmente com as variáveis.
4. Na tela Administração > Consumo > Páginas por plano, a página **Competição** nasce liberada para todos (não está na lista de páginas trancadas).

## Testes (sem internet)
`pytest tests/test_competicao.py tests/test_competicao_job.py tests/test_competicao_app_fumaca.py`

## Limites conhecidos
- Cotações do Yahoo são gratuitas, podem atrasar ou falhar: se mais da metade falhar, o fechamento não publica nada e tenta de novo.
- Dividendos entram no caixa na data "ex"; desdobramentos ajustam a quantidade. Eventos raros (bonificação, subscrição) não são tratados.
- O apelido é único por conferência no cadastro; cadastros simultâneos com o mesmo apelido são resolvidos no fechamento (fica o mais antigo).
- Com mais de alguns milhares de participantes, vale migrar `comp_cart` para uma tabela própria e o ranking para uma consulta no banco.
- Prêmios em dinheiro exigem análise jurídica (promoção comercial). A competição nasce sem prêmios.
