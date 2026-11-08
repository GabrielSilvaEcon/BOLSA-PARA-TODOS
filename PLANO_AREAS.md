# Plano: dividir o app em áreas (estilo super app)

**Quando fazer:** a Jornada (Etapas 1 a 6b do `PLANO_DUOLINGO.md`) já está concluída.
**Objetivo:** o app ter 3 áreas, cada uma com navegação própria, e trocar de área com um toque.

## As áreas
| Área | O que entra |
|---|---|
| Aprender | Jornada, Educação financeira, Glossário |
| Analisar | Carteira (primeira página), Gestão de carteira, Risco, Relatórios, Simulador, Calculadoras, Ações, FIIs, Fundos, ETFs, Cripto, Renda fixa, Tesouro/CDI, Economia, Comparar, Evolução, Notícias, Inteligência, Alertas |
| Jogar | Competição reapresentada como jogo educativo |
| Fora das áreas | Início, Minha conta, Planos, Administração, Ajuda: sempre acessíveis |

## O que o código tem hoje (levantado em `app.py`)
- O menu da barra lateral é montado à mão, em blocos `cat(...)` (linhas ~4086 a 4150).
- O `st.navigation` fica escondido (`position="hidden"`) e registra todas as páginas.
- Jornada e Glossário são **abas dentro de Educação financeira**, não páginas.

## Regras de segurança (valem para toda etapa)
1. Todas as páginas continuam registradas no `st.navigation`. Só muda o que aparece no menu. Links, busca global, alertas e `switch_page` seguem funcionando.
2. Só se mexe no bloco do menu e em arquivos novos. Nenhum arquivo de cálculo ou de integração é alterado.
3. Cada recurso novo tem uma chave que o desliga (ex.: `AREAS_ATIVAS = False`). Desligada, o menu fica igual ao de hoje.
4. Antes e depois de cada etapa: rodar todos os testes e abrir cada página.
5. Um commit por etapa, para poder voltar atrás.
6. Máximo de 3 ou 4 áreas, para a barra caber no celular.

## Etapas
Marque cada uma ao concluir.

| # | Entrega | Como validar | Risco |
|---|---|---|---|
| [ ] 0 | Commit do estado atual, rodar `pytest` e anotar o resultado como referência | Testes passam como antes | Nenhum |
| [ ] A1 | Criar `areas.py` (lista das áreas + funções puras: páginas de cada área, área de uma página, última página lembrada) e `test_areas.py`. Ninguém usa ainda | `pytest test_areas.py` | Nenhum |
| [ ] A2a | O menu passa a ler `areas.py`, com a chave **desligada**: menu idêntico ao de hoje | Comparar o menu antes e depois | Baixo |
| [ ] A2b | Ligar a chave: o menu mostra só as páginas da área ativa; Início, Conta e Ajuda sempre visíveis | Abrir cada área e ver só as suas páginas | Baixo |
| [ ] A3 | Seletor de área: botões no topo, em qualquer tela; cada área lembra a última página | Trocar de área e voltar na mesma página | Baixo |
| [ ] A4 | Barra fixa no rodapé para o celular (CSS), com chave própria. Plano B: ficar só com os botões do topo | Testar no celular | Médio |
| [ ] A5 | Início com 3 cartões grandes das áreas e atalho direto para a Carteira | Abrir o app e ver os cartões | Baixo |
| [ ] A6 | (Opcional) Páginas finas para Jornada e Glossário, que só chamam o que já existe em `jornada_app` e `glossario_app` | Abrir cada uma pelo menu | Baixo |

## Jogar: Competição como jogo educativo
Base existente: `competicao.py`, `competicao_ligas.py`, `competicao_temporadas.py`, `competicao_job.py`, `competicao_app.py`.
Só começa depois do A5. Antes do J1, confirmar o formato do jogo com o dono do projeto.

| # | Entrega |
|---|---|
| [ ] J1 | Revisar o que a Competição faz hoje e definir o formato: desafios curtos, missões e ranking |
| [ ] J2 | Pontuação que premia estudo e boas decisões, nunca risco ou lucro (mesma regra da Educação) |
| [ ] J3 | Telas novas no estilo da Jornada: missões do dia, desafio da semana, ranking da liga |
| [ ] J4 | Ligação com a Jornada: lições concluídas desbloqueiam desafios, sem bloquear conteúdo |

## Riscos
- `app.py` tem mais de 4.000 linhas: a mudança fica num trecho pequeno, perto de onde o menu é montado.
- A barra fixa depende de CSS e do que o Streamlit permite; o plano B já está previsto.
- Estado da área ativa e da última página fica em `st.session_state`; no visitante vale só para a sessão.
