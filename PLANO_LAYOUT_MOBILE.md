# Plano: layout compacto para smartphones (Bússola B3)

**Regra nº 1:** a identidade visual não muda. A camada nova (`layout_mobile.py`) só mexe em `padding`, `margin`, `gap` e `min-height`, só em telas de até 640 px, e há teste (`test_layout_mobile.py`) que barra qualquer cor, gradiente, fonte, borda, arredondamento, sombra, ícone ou largura.
**Chave:** `LAYOUT_COMPACTO` no `app.py` (False = espaçamento de sempre). Tablet e computador não mudam.

## Etapa 1 · Auditoria (feita)
| # | Achado | Onde | Efeito no celular |
|---|---|---|---|
| 1 | Gap padrão de 16 px entre **todos** os elementos | Streamlit (`stVerticalBlock`) | Principal fonte de comprimento |
| 2 | Cada `st.markdown("<style>…")` deixa um item vazio que também ganha 16 px de gap; o app injeta vários no topo de cada tela (`tema.css`, CSS das áreas, CSS da página, Jornada, Jogar, Educação…) | `app.py`, `jornada_app.py`, `educacao_app.py`, `jogar_app.py`… | Faixa vazia no topo das telas (causa provável do espaço em branco do Início; não confirmada sem ver o app rodando) |
| 3 | Tokens de espaço grandes: `.card` 16/24, `.cartao` 24, `.vazio` 32/24, `.pghead` margem 24, `hr` 24, `.sec-sub` 16/8, `.rs-top` 18/20, `.rs-box` 16/18, `.sc` 16/18 | `tema.py` | Cartões altos com ar dentro |
| 4 | Faixa do Início: 40 px em cima e 88 px embaixo (a busca sobrepõe 56 px) | `tema.py` (`.hero2`) | ~36 px a mais que o necessário |
| 5 | Títulos com `padding` de 8 a 16 px acima e abaixo | Streamlit (h1 a h4) | Espaço extra em cada seção |
| 6 | Rodapé da página com 7 a 7,5 rem para uma barra de ~4,6 rem | `tema.py`, `app.py` | ~2,5 rem vazios no fim de toda página |
| 7 | Margens laterais de 1 rem (0,7 rem só abaixo de 400 px) | `tema.py` | Largura útil pequena |
| 8 | Colunas empilhadas com gap de 1 rem (≈ 36 `st.columns` só no `app.py`; muitas no Simulador, Análise técnica, Conta, Alertas, Risco) | várias telas | Espaço entre blocos que eram lado a lado |
| 9 | `min-height` grande: `.rc` 190 px e `.pl-frase` (já zerados no celular); `cripto.py:388` 235 px **inline** | `tema.py`, `planos_app.py`, `cripto.py` | O inline do Cripto não é alcançável por CSS global |

## Etapa 2 · Base global (feita)
Margens laterais .75 rem · topo 3,85 rem (cabeçalho fixo tem 3,75 rem) · rodapé 6 rem · gap vertical 16 → ~10 px e horizontal .5 rem (com `:where()`, para nunca vencer o gap próprio de um componente) · remoção do item vazio dos blocos só de `<style>` (o CSS continua valendo) · parágrafos, títulos e `hr` mais curtos.

## Etapa 3 · Componentes comuns (feita)
`.pghead`, `.card`, `.kpi/.mini/.ctx`, `.cartao`, `.vazio`, `.sc`, `.rc`, `.rs-*`, `.pv`, `.sec-sub`, métricas, formulários, conteúdo de expansores e alertas: mesmos valores em todas as telas, ajustáveis em três variáveis (`--m-gap`, `--m-pad`, `--m-sec`).

## Etapa 4 · Telas específicas (feita)
Início (faixa e busca flutuante, com a mesma sobreposição), Jornada (`.jor-un`, `.jor-real`, indicadores), Jogar, Educação. Notícias, Planos, Login, Competição, Cripto e as demais recebem só a base e os componentes comuns.

## Etapa 5 · Verificação
- [x] Testes automáticos (`test_layout_mobile.py`): só espaço, só ≤ 640 px, sem tocar em menu lateral, barra de baixo, abas ou botões, nenhum `min-height` abaixo de 44 px.
- [ ] **Conferir no celular** (390 px e 360 px) estas telas, antes e depois: Início, Jornada (trilha e player), Jogar, Competição, Carteira, Ações (Preço justo), Notícias, Planos, Minha conta. Procurar: sobreposição da busca com a faixa do Início, conector da trilha da Jornada encostando nos nós, algum cartão com texto colado na borda.
- [ ] Se algo ficar apertado demais: aumentar `--m-gap`, `--m-pad` ou `--m-sec` em `layout_mobile.py` (afeta o app todo de uma vez), ou pôr `LAYOUT_COMPACTO = False`.

## Fora desta camada (de propósito)
Tamanho de fonte e de botões (conforto de leitura e de toque), altura dos gráficos Plotly (é definida no Python de cada gráfico), nós da trilha da Jornada (76 px, parte da identidade), barra de baixo e menu lateral, e o `min-height:235px` escrito dentro do HTML do `cripto.py`.
