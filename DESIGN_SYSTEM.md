# TickerHunters · Design system

**Chave:** `DESIGN_V2` no `app.py` (False = visual de antes). Código em `design/` e `marca.py`; testes em `test_design.py`.
**Regra:** só apresentação. Nenhuma regra financeira, API, banco, login ou assinatura é tocada.

## Marca (`marca.py`)
`NOME`, `SLOGAN`, `DESCRICAO`, cores da marca, logo SVG (`LOGO_SVG`), PNGs em base64 (`LOGO_PEQ`, `LOGO_GRANDE`, `FAVICON`) e `wordmark_html()`. Mudar o nome do produto = mudar `NOME` (e os arquivos estáticos: manifest, index.html, sw.js).
Conceito do logo: mira (alvo) com três candles em alta; roxo profundo + verde-limão.

## Fases
| Fase | Entrega | Situação |
|---|---|---|
| 1 | Diagnóstico (`DIAGNOSTICO_FASE1.md`) | feita |
| 2 | Conceito: roxo profundo, verde-limão de marca, dourado no Wallet Game, Inter, ícones de traço único | feita |
| 3 | Design system ampliado (abaixo) | feita |
| 4 | Navegação mobile: atalho da conta (`TOPO_PERFIL`), chip "voltar" nas sub-páginas, slogan no menu | feita (aguarda conferência no celular) |
| 5 | Redesign: camada `legado()` leva cartões, KPIs, cabeçalhos, métricas, expansores e formulários antigos para as cores de cada área; Wallet Game sem tabelas cruas (ranking, temporadas, ligas, posições, extrato viram cartões) | feita (aguarda conferência no celular) |
| 6 | Acabamento: entrada suave das telas, anéis/barras animados, medalhas no ranking | feita em parte (ilustrações próprias ficam para depois) |
| 7 | Validação (testes + fumaça com Streamlit falso) | feita; remover `_TROCA_COR`/`_cromatico` de `tema.py` só depois da conferência visual |

## Tokens (`design/tokens.py`)
Fonte Inter; texto 12/14/16/20/24/32; espaço 4 a 32; raios 8/12/16/pílula; elevação 0 a 3; ícones 18/24/32; camadas (barra 990, folha 1100, aviso 1200); toque mínimo 48; barra 64 + área segura; cabeçalho 48; movimento 160 ms. `tokens.como_json()` exporta tudo (útil num app Android futuro).

## Temas (`design/temas.py`)
`aprender` (índigo e verde-limão), `analise` (azul-noite e violeta), `wallet` (carvão e dourado). Cada área tem o seu fundo + `MARCA` (verde-limão) + "concha" da barra inferior. Contraste conferido (WCAG) em `test_design.py`.

## Ícones (`design/icones.py`)
23 ícones próprios em SVG, traço de 2 px, cor = a do texto (`currentColor`). `icones.icone("alvo", 24)`.

## Componentes (`design/componentes.py`, classes `dz-*` em `design/css.py`)
`cartao`, `indicador`, `selo`, `skeleton`, **`mensagem`** (info, sucesso, aviso, erro), **`vazio`**, **`barra_progresso`**, **`anel`** (nota/nível), **`conquista`**, **`etapas`**, **`grade`**, **`lista_ranking`** (ranking e extrato em cartões, com medalhas) e **`cartao_posicao`**. Texto de fora sempre escapado; dado ausente nunca vira número inventado.

## Widgets do Streamlit padronizados (`design/css.py › widgets()`)
Botão primário (cor de destaque, raio 16, toque 48, feedback ao apertar), foco visível, campos e avisos com raios do sistema, abas com alvo de toque, **folha inferior** para `st.dialog` no celular (sobe do rodapé, respeita área segura), campos com 16 px (sem zoom ao focar). A barra inferior fica de fora.

## Preparado para o futuro APK
- Tokens, temas e ícones são Python puro e exportáveis.
- Sem dependência de recursos só de desktop: CSS com `env(safe-area-inset-*)`, `dvh`, alvos de 48 px e `prefers-reduced-motion`.
- Pontos que pedem ponte nativa numa WebView (isolar quando for a hora): cookie via `window.parent` (`usuarios.py`), downloads (`st.download_button`), links `target=_blank`, pagamento web (Play Billing no Android).

## Limites do Streamlit
Sem transição entre telas (cada troca reexecuta o script), sem gestos nativos e sem offline. Os skeletons e microanimações disfarçam, mas o comportamento nativo só virá com uma camada mobile.

## Camada de compatibilidade (`design/css.py › legado()`)
As classes antigas (`.card`, `.kpi`, `.cartao`, `.pghead`, métricas, expansores, formulários) passam a usar as variáveis `--dz-*` da área aberta. Elementos com `border` ou `background` no atributo `style` (status, alertas) ficam como estão. Para desligar tudo: `DESIGN_V2 = False` no `app.py`.
