# Educação financeira (Passo 24)

Página **Aprender > Educação financeira**. Conteúdo aberto a todos; progresso salvo na conta (individual e isolado).

## Arquivos
| Arquivo | Papel |
|---|---|
| `edu_conteudo.py` | Só dados: assuntos, aulas (3 textos por aula), indicadores (7 campos), glossário extra, perguntas, trilhas, fontes |
| `educacao.py` | Lógica pura: progresso, correção, trilhas, certificados internos, conquistas, sugestões, glossário, métricas, simulação |
| `educacao_app.py` | Tela: Painel, Trilhas, Biblioteca, Praticar, Com ativos reais, Simulações, Professor, Glossário; `explicador()` reutilizável |
| `modos.py` | Os três modos (iniciante, intermediário, avançado): só mudam a apresentação |

## Como ampliar
- **Nova aula:** adicione um dicionário em `AULAS` (3 textos). Aparece sozinha na biblioteca. Para entrar numa trilha, inclua o id em `TRILHAS`.
- **Nova pergunta:** adicione em `QUIZ` com `aula` e `correta` (índice). **Novo indicador:** `INDICADORES` com `classes` (vazio = qualquer ativo com preço).
- **Usar em outra tela:** `educacao_app.explicador("P/L", "chave")` mostra o botão "O que é P/L?" (só para indicadores conhecidos).

## Regras de projeto
- Os modos não são planos: sem preço, assinatura ou bloqueio. Pontos e conquistas só premiam estudo.
- Dados reais só com fonte e data; sem dado, a tela diz "indisponível". Exemplos numéricos fora disso são marcados como hipotéticos.
- Certificado interno é educacional, não é certificação nem mede capacidade de investir.
- Regras tributárias têm data de revisão (`REVISAO`) e remetem à fonte oficial. Revise-as quando a lei mudar.
- Professor com IA reutiliza `assistente.py` (mesma chave, mesmos limites e filtro contra recomendação).

## Jornada estilo Duolingo
Plano em `PLANO_DUOLINGO.md`. `jornada_conteudo.py` (dados: unidades, lições, exercícios) e `jornada.py` (lógica pura: sessão, XP, ofensiva, revisão, mapa). Estado em `edu_progresso["jornada"]`. Sem vidas que bloqueiam; XP só por estudo. Nova lição: adicione em `LICOES` e no `licoes` da unidade; rode `pytest test_jornada.py`.
