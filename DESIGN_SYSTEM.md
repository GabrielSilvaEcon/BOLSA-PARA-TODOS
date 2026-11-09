# Design system v2 (redesign app-first)

**Chave:** `DESIGN_V2` no `app.py` (False = visual de antes). Código em `design/`; testes em `test_design.py`.

## Estado por etapa
| Etapa | Entrega | Situação |
|---|---|---|
| 2 | Pacote `design/`, barra inferior estilo Android, cabeçalho compacto, componentes `dz-*` | feita (aguarda validação no celular) |
| 3 | Tema Aprender nas telas (Jornada, Educação, Missões, Glossário) | pendente |
| 4 | Tema Análise (gráficos, tabelas, indicadores) | pendente |
| 5 | Tema Wallet Game (Competição) | pendente |
| 7 | Remover `_TROCA_COR`, `_cromatico` e camadas antigas de `tema.py` | pendente |

## Tokens (`design/tokens.py`)
Fonte Inter; texto 12/14/16/20/24/32; espaço 4/8/12/16/24/32; raios 8/12/16/pílula; toque mínimo 48; barra 64 + área segura; cabeçalho 48; movimento 160 ms.

## Temas (`design/temas.py`)
`aprender` (claro, roxo), `analise` (escuro, roxo, verde/vermelho), `wallet` (carvão, dourado). A página aberta define o tema (`tema_da_pagina`); Início, Conta, Planos e Ajuda usam `analise`. A barra inferior ("concha") é igual nos três; só a cor do item ativo acompanha o ambiente. Todos os pares texto/fundo são conferidos em `test_design.py` (WCAG).

## Componentes (`design/componentes.py`)
`cartao`, `indicador` (valor + variação; dado ausente = "indisponível"), `selo`, `skeleton`, `numero_br`. Só formatam o que recebem; nenhuma regra financeira.

## Como usar numa tela
`st.markdown(componentes.indicador("Preço", "R$ 12,34", 1.5), unsafe_allow_html=True)`. As cores vêm das variáveis `--dz-*` do tema da página.

## Pontos reaproveitáveis numa futura camada mobile (React Native / Flutter)
- `design/tokens.py` e `design/temas.py` são Python puro; `tokens.como_json()` exporta os tokens.
- `areas.py`, `paleta.py`, `jogar.py`, `competicao*.py` e os módulos de cálculo não dependem do Streamlit.
- Dependem do Streamlit e precisarão de camada de serviço antes de migrar: `dados`, `banco`, `planos`, `usuarios`, `carteira`, `cripto`, `evolucao`, `mercados`, `pagamentos`, `assistente`, `comparador_dados`, `comparador_fontes`, `fonte_reserva`, `fundamentalista_cripto`, `guias`, `jornada_player`, `secoes`.

## Limites do Streamlit
Sem navegação nativa de Android, sem gestos reais, sem transições entre telas (trocar de tela reexecuta o script) e sem offline. O visual se aproxima de app; o comportamento nativo só virá com uma camada mobile.
