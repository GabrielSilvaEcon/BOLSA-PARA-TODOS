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
Plano em `PLANO_DUOLINGO.md`. `jornada_conteudo.py` (unidades e 3 lições-semente) e `jornada_conteudo_mais.py` (as outras 18 lições; 21 no total, uma por aula) e `jornada.py` (lógica pura: sessão, XP, ofensiva, revisão, mapa). Estado em `edu_progresso["jornada"]`. Sem vidas que bloqueiam; XP só por estudo. Nova lição: adicione em `LICOES` e no `licoes` da unidade; rode `pytest test_jornada.py`.

### Efeitos, conquistas e lembrete (etapa 6a)
- **Sons:** `jornada_som.py` sintetiza 4 WAVs curtos (acerto, erro, lição concluída, meta do dia) sem arquivos de terceiros. O player toca o som pendente uma única vez (`st.audio` com autoplay, invisível). Botão **Som** na Jornada e no player, salvo em `edu_progresso["jornada"]["som"]` (padrão: ligado). Falha de áudio nunca quebra a lição. iPhone/Safari pode bloquear autoplay ou ficar mudo com a chave de silêncio.
- **Animações:** só CSS (sem script), com `prefers-reduced-motion` respeitado. A contagem de XP usa `@property`; em navegador sem suporte mostra direto o valor final.
- **Conquistas novas** (`educacao.CONQUISTAS`): Lição perfeita e Ofensiva de 3, 7 e 30 dias. A ofensiva usa a *melhor* sequência já feita, então a conquista não some se a sequência atual se perder.
- **Lembrete de estudo:** em Notificações > Preferências (desligado por padrão; hora padrão 18:00, Brasília). O monitor (`monitor.avisar_estudo`) cria um aviso por dia, só se a pessoa ainda não estudou hoje, e respeita dias/horários permitidos e a categoria "Lembrete de estudo". Chega na primeira execução do monitor depois da hora: de segunda a sexta a cada 15 min até cerca de 19h50 de Brasília; fora disso, a cada 4 h.

### Liga de estudo, dado real e PWA (etapa 6b)
- **Liga de estudo (opcional):** no fim da aba Jornada. Reaproveita o código de convite das ligas da Competição, mas é um placar **só de estudo**: apelido da Competição e XP da semana (segunda a domingo, Brasília). Desligada por padrão; quem não ligar não aparece. Cada pessoa grava só o próprio documento `edu_liga` (`{ligado, semana, xp, apelido}`); `banco.edu_liga_ranking` só entrega a membros da liga e nunca devolve e-mail. O ranking é montado na hora (`jornada_liga.montar`), sem mexer no fechamento diário da competição. Documento de semana antiga vale 0 XP. Sem login, sem liga ou sem apelido, a tela explica o que falta. Qualquer falha mostra aviso e não derruba a trilha.
- **Dado real no fim da unidade:** ao concluir uma unidade com roteiro em `jornada.ESTUDO_REAL` (Primeiros passos, Onde investir, Montando a carteira, Analisando ativos e Risco na prática), aparece o botão **Estudar com um ativo real**. Usa as mesmas fontes e regras da aba "Com ativos reais" (fonte e data, ou "indisponível"; nada é estimado). É opcional e **não dá XP**. Renda fixa e impostos ficam sem roteiro porque o app não tem fonte de preço para eles nessa tela. Novo roteiro: adicione em `ESTUDO_REAL` (só indicadores que existem em `INDICADORES`; `validar_conteudo()` confere).
- **PWA:** `sw.js` passou para `bolsa-para-todos-v2` (os caches antigos são apagados), inclui o ícone maskable e só guarda respostas 200 do próprio site. O estudo continua exigindo internet. Os manifests (`manifest.webmanifest` e `static/manifest.json`) não foram alterados. Ao mudar a lista `SHELL`, aumente a versão do cache.

