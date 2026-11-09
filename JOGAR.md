# Missões (página `missoes`, área Aprender)

> Mudança: a antiga área "Jogar" foi dividida. **Wallet Game** (área `wallet`) é só a carteira virtual (`competicao`). Missões, desafio da semana e desafios por tema vivem na área **Aprender**, página `missoes`. O ranking de alunos (liga de estudo) fica no fim da Jornada.


Área **Jogar** do app (PLANO_AREAS.md, J1 a J4). Página nova `jogar` + a página `competicao` (carteira virtual) que continua como era.

## O que a página Jogar mostra
| Bloco | Como funciona |
|---|---|
| Pontos da semana | XP de estudo + 5 por missão do dia cumprida + 30 do desafio da semana + 20 da boa decisão |
| Missões do dia | Estude hoje (XP > 0) · Bata a meta do dia · Dia dourado (2x a meta). Todas saem do XP por dia da Jornada |
| Desafio da semana | Gira entre "estude em 5 dias", "meta batida 3 vezes" e "150 XP de estudo" (segunda a domingo, Brasília) |
| Boa decisão da semana | Carteira virtual com 5+ ativos (peso mínimo 5%) e nenhum acima de 25% do patrimônio. Mede só **como** a carteira foi montada |
| Desafios por tema | Concluir todas as lições de uma unidade da Jornada abre o desafio dela: 5 perguntas sorteadas da unidade, no player da Jornada |
| Ranking da liga | Reaproveita a **liga de estudo** (`jornada_liga_app.py`): só apelido e XP da semana, desligada por padrão |

## Regras fixas
- **Pontos nunca vêm de lucro, retorno, risco ou número de ordens.** `jogar.pontos_semana(p, agora, boa_decisao)` só recebe o progresso de estudo e um sim/não de processo. Há teste que barra o uso de funções de retorno/risco em `jogar.py`.
- **Nada é bloqueado.** O desafio é a única coisa que abre ao concluir uma unidade; lições, aulas e páginas da Jornada seguem livres.
- **Sem tabela nem documento novo.** Tudo é calculado de `edu_progresso["jornada"]` (XP por dia e lições concluídas) e da carteira virtual já gravada.
- O desafio usa uma sessão no formato de revisão (`revisao: True`, com `nome`): vale o XP de revisão e os erros entram na fila de revisão, como em qualquer lição.

## Arquivos
`jogar.py` (lógica pura) · `jogar_app.py` (tela) · `test_jogar.py` · `jornada_player.py` (ganhou `iniciar_sessao` e o nome da sessão) · `areas.py` (Jogar = `jogar` + `competicao`) · `app.py` (página `PG_JOGAR`, menu e navegação).

## Limites conhecidos
- Pontos por dia usam a meta diária **atual**; se a pessoa mudar a meta, a semana é recalculada com ela.
- O ranking da liga mostra XP (estudo), não os pontos do jogo: os pontos aparecem só para a própria pessoa.
- O desafio pode ser repetido; cada rodada vale o XP de revisão (como repetir uma lição na Jornada).
- Visitante joga na sessão, sem gravar.
