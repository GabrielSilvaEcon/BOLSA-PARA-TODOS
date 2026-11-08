# Plano: Educação financeira no estilo Duolingo

Objetivo: transformar **Aprender > Educação financeira** em uma jornada de lições curtas, com trilha visual, exercícios variados, XP, ofensiva (streak) e revisão de erros, **sem quebrar** o que já existe (Painel, Trilhas, Biblioteca, Praticar, Professor, Glossário).

## Decisões de projeto (adaptadas às regras do app)
| Duolingo | Aqui | Motivo |
|---|---|---|
| Vidas que bloqueiam | **Sem bloqueio.** Erro volta para o fim da fila e entra em "Revisar erros" | `EDUCACAO.md`: todo conteúdo aberto, sem planos nem bloqueios |
| Lição trancada | Estados `concluída`, `próxima`, `livre` (nada trancado) | idem |
| Gemas / loja | Não terá | Não há monetização na educação |
| Ligas competitivas | Opcional, só na Etapa 6, ligada a `competicao_ligas.py` | Fora do escopo inicial |
| XP | Só por **estudar** (lição, revisão). Nunca por operar ou assumir risco | Regra existente de pontos/conquistas |
| Números de mercado | Só exemplos marcados como **hipotéticos** | Regra existente |

## Modelo
`Unidade` (tema) → `Lição` (5 a 7 exercícios, ~3 min) → `Exercício`.
Tipos: `escolha`, `vf` (verdadeiro/falso), `completar`, `ordenar`, `pares`.
Progresso em `edu_progresso["jornada"]` (já é gravado no perfil da conta; visitante só na sessão).

## Etapas
| # | Entrega | Como validar |
|---|---|---|
| **1 (feita)** | Base lógica: `jornada_conteudo.py` (dados + 3 lições-semente), `jornada.py` (correção, sessão, XP, ofensiva, meta diária, revisão, mapa), integração em `educacao.normalizar`, testes | `pytest test_jornada.py` |
| **2 (feita)** | Aba **Jornada**: trilha em zigue-zague com unidades, ícones de estado e botão "Começar" | Rodar o app e ver o mapa |
| **3 (feita)** | Player de lição: 1 exercício por vez, barra de progresso, feedback verde/vermelho, tela final com XP | Fazer uma lição completa |
| **4 (feita)** | Topo de tela com ofensiva, XP do dia e meta diária (ajustável); botão **Revisar erros** | Estudar em 2 dias seguidos |
| **5 (feita)** | Conteúdo: 21 aulas viraram 21 lições (111 exercícios) em 7 unidades, em `jornada_conteudo_mais.py` (as 3 sementes seguem em `jornada_conteudo.py`) | `validar_conteudo()` vazio e `test_jornada_etapa4_5.py` |
| 6a (feita) | Efeitos: sons gerados em código (`jornada_som.py`) com botão Som salvo na conta; animações (barra, feedback, medalha, contagem de XP, confete, ícone da lição concluída, chama); conquistas novas (lição perfeita, ofensiva de 3/7/30 dias); lembrete diário de estudo (`notif.lembrete_estudo` + `monitor.avisar_estudo`, desligado por padrão) | `pytest test_jornada_etapa6.py`; testar o som no celular e no computador |
| 6b (feita) | Liga de estudo opcional (`jornada_liga.py` + `jornada_liga_app.py`, sobre as ligas de `competicao_ligas.py`); estudo com dado real no fim da unidade (`jornada.ESTUDO_REAL` + `educacao_app._estudo_unidade`); revisão do PWA (`sw.js` v2, manifest alinhado) | `pytest test_jornada_etapa6b.py`; entrar em uma liga, ligar a opção com 2 contas e concluir uma unidade |

## Riscos
- `educacao_app.py` e `app.py` são grandes: a Jornada entra como **aba nova** e arquivo novo (`jornada_app.py`), sem refatorar o resto.
- Streak depende de fuso: usa horário de Brasília (UTC-3, sem horário de verão).
