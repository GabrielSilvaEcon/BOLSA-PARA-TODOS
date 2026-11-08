# Plano: dividir o app em áreas (estilo super app)

**Quando fazer:** só depois de concluir a Jornada (Etapas 3 a 6 do `PLANO_DUOLINGO.md`).
**Objetivo:** o app ter 3 áreas separadas, cada uma com navegação própria, e trocar de área com um toque.

## As áreas
| Área | O que entra |
|---|---|
| 🎓 **Aprender** | Jornada, Educação financeira, Glossário |
| 📊 **Analisar** | Carteira (primeira página), Ações, Fundos, ETFs, Cripto, Renda fixa, Economia, Comparar, Notícias e Inteligência, Risco, Simulador, Relatórios |
| 🎮 **Jogar** | Competição reapresentada como jogo educativo |
| fora das áreas | Início, Conta e Ajuda, sempre acessíveis |

## Regras de projeto
- Nenhuma tela existente é reescrita: só muda **quais páginas aparecem no menu** conforme a área ativa.
- A divisão fica numa lista simples em `areas.py`. Mudar ou criar uma área (por exemplo, uma quarta só para a Carteira) é editar essa lista.
- Cada área lembra a última página aberta.
- Máximo de 3 ou 4 áreas, para a barra caber no celular.

## Etapas
| # | Entrega | Como validar |
|---|---|---|
| A1 | `areas.py`: definição das áreas e funções puras (páginas de cada área, área de uma página, última página lembrada) + testes | `pytest test_areas.py` |
| A2 | `app.py`: o menu (`st.navigation`) passa a mostrar só as páginas da área ativa; Início, Conta e Ajuda ficam sempre visíveis | Abrir cada área e ver só as suas páginas |
| A3 | Seletor de área: botões no topo (funciona em qualquer tela) | Trocar de área e voltar na mesma página |
| A4 | Barra fixa no rodapé para o celular (CSS), com plano B de ficar só no topo se der problema | Testar no celular |
| A5 | Tela Início com cartões grandes das 3 áreas e atalho direto para a Carteira | Abrir o app e ver os cartões |

## Jogar: Competição como jogo educativo
Base já existente: `competicao.py`, `competicao_ligas.py`, `competicao_temporadas.py`, `competicao_job.py`, `competicao_app.py`.

| # | Entrega |
|---|---|
| J1 | Revisar o que a Competição faz hoje e definir o formato do jogo: desafios curtos, missões e ranking |
| J2 | Pontuação que premia **estudo e boas decisões**, nunca risco ou lucro (mesma regra da Educação) |
| J3 | Telas novas no estilo da Jornada: missões do dia, desafio da semana, ranking da liga |
| J4 | Ligação com a Jornada: lições concluídas desbloqueiam desafios, sem bloquear conteúdo |

## Riscos
- `app.py` tem mais de 4.000 linhas: a mudança deve ficar num trecho pequeno, perto de onde o menu é montado.
- A barra fixa depende de CSS e do que o Streamlit permite; o plano B (botões no topo) já está previsto.
- Antes de começar o Jogar, confirmar com você o formato do jogo (J1).
