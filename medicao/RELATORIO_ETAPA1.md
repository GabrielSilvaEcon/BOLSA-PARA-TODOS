# Etapa 1 — Medição e linha de base (Trade Game)

Nada do jogo, do banco ou da infraestrutura foi alterado. Foram criados apenas scripts de medição em `medicao/` (ignorados na suíte normal; rodam com `MEDIR=1`).

## 1. Métricas encontradas

### 1.1 Backend por rota (banco = SQLite local; 15 repetições após a 1ª)
Valem: nº de chamadas, bytes, sequência e tempo de processamento Python. **Não valem como tempo de produção:** o tempo de "banco" aqui é local; no Supabase cada chamada é uma ida pela rede (o código usa `requests.request` sem reaproveitar conexão).

| Rota | Total p50 (ms) | p95 (ms) | Interno¹ p50 (ms) | Banco local p50 (ms) | Chamadas ao banco | Sequenciais / paralelas | Bytes | 1ª chamada (ms) | Erros |
|---|---|---|---|---|---|---|---|---|---|
| /loja | 30,0 | 48,2 | 6,5 | 23,4 | **50** | 50 / 0 | 6.731 | 611,8 | 0 |
| /perfil | 9,1 | 12,5 | 5,0 | 4,4 | **15** | 15 / 0 | 10.565 | 32,1 | 0 |
| /eu | 9,5 | 16,7 | 4,9 | 3,7 | **11** | 11 / 0 | 11.242 | 8,7 | 0 |
| /ticker/central | 12,6 | 20,7 | 9,1 | 3,4 | 7 | 7 / 0 | 39.258 | 19,2 | 0 |
| /trade/central | 6,4 | 8,0 | 3,4 | 3,2 | 7 | 7 / 0 | 295 | 7,0 | 0 |
| /carteira | 6,3 | 9,0 | 4,1 | 2,2 | 7 | 7 / 0 | 223 | 7,6 | 0 |
| /ranking/trade/tela | 7,3 | 8,3 | 5,5 | 1,8 | 5 | 5 / 0 | **135.078** | 9,6 | 0 |
| /trofeus | 5,0 | 5,4 | 3,4 | 1,5 | 3 | 3 / 0 | 917 | 8,3 | 0 |
| /setups | 5,2 | 5,7 | 3,9 | 1,3 | 3 | 3 / 0 | 11.409 | 7,6 | 0 |
| /missoes | 6,8 | 8,6 | 3,9 | 3,2 | 4 | 4 / 0 | 903 | 10,7 | 0 |

¹ Interno = total menos o tempo dentro de `banco.py` (processamento Python, serialização, FastAPI). Todo o código é síncrono: **nenhuma consulta é paralela** (máx. simultâneas = 1). Erros e timeouts em produção: **não medidos** (sem acesso aos logs).

### 1.2 Partida (contra o bot, 15 min de jogo; relógio simulado a 1 consulta/s como o app; 28 jogadas)
| Medida | Valor |
|---|---|
| Duração simulada | 228 s |
| Consultas por minuto | **60** (1 por segundo, por jogador) |
| Dados por consulta | mediana **27.206 B**, máximo 69.013 B |
| Candles por consulta | mediana **329**, máximo 356 (todos, em toda consulta) |
| Total baixado na partida | **≈ 6.961 KB** (≈ 6,8 MB) |
| Chamadas ao banco por consulta | mediana 3, máximo 15 |
| Processamento por consulta | p50 13,8 ms · p95 20,3 ms |
| Jogada (comprar/zerar/estratégia) | processamento p50 **17,9 ms**; 4 chamadas ao banco (via API) ; resposta 27.149 B |
| Gravações da partida / conflitos | 40 / 0 |

### 1.3 Dois jogadores operando ao mesmo tempo (threads, 24 jogadas)
Jogada p50 26,3 ms · p95 32,2 ms · máx 40,1 ms; 24 respostas 200; **0 conflitos**. Limite: SQLite serializa gravações; **não representa o Postgres do Supabase**, onde o conflito de versão (CAS) pode ocorrer e o código tenta até 8 vezes.

### 1.4 Mesa (WebView) — Chromium headless, desktop, render por software (**proxy; não é Android**)
Estrangulamento de CPU emulado (1×, 4×, 6×) para imitar aparelhos mais fracos.

| Cenário | CPU | HTML carregado (ms) | Render até 2 quadros (ms) | FPS (5 s) | Quadros > 34 ms | Pior quadro (ms) | CPU de tarefa em 5 s (s) | Heap JS (MB) |
|---|---|---|---|---|---|---|---|---|
| Repouso | 1× | 278 | 115 | 60,2 | 0 | 16,8 | 0,39 | 2,4 |
| Repouso | 4× | 227 | 226 | 60,2 | 0 | 16,8 | 1,37 | 2,3 |
| Repouso | 6× | 349 | 363 | 60,0 | 0 | 33,3 | 2,08 | 2,3 |
| Destaque do padrão (efeitos) | 1× | 24* | 113 | **35,9** | 27 | 183 | 3,92 | 2,5 |
| Destaque do padrão (efeitos) | 4× | 238 | 271 | **12,1** | 21 | 883 | 5,45 | 2,6 |
| Destaque do padrão (efeitos) | 6× | 309 | 369 | **6,5** | 38 | 1.567 | 4,65 | 2,5 |

\* o 1º carregamento é mais lento que os seguintes (cache do navegador). HTML de 219 KB (1.457 linhas, fundo em base64 embutido).

### 1.5 Rede e infraestrutura
**Não medido.** Do ambiente desta sessão, o Render (`tickerhunters-api.onrender.com`) e o Supabase não são acessíveis (o proxy bloqueia) e não tenho as credenciais. Portanto não há número de latência Render↔Supabase, de acordar o servidor, nem de Wi-Fi × 4G.

## 2. Metodologia
Scripts em `medicao/`: `test_baseline_backend.py` (conta e cronometra chamadas ao banco por rota, tamanhos, erros), `test_baseline_partida.py` (partida completa e dois jogadores com threads), `mesa_chromium.js` (Playwright + CDP: tempo de carga, FPS por `requestAnimationFrame`, métricas de CPU e memória do Chromium). Repetições: 15 por rota, 1 partida completa, 3 níveis de estrangulamento de CPU. Reprodutível: `MEDIR=1 python -m pytest medicao -s` e `node medicao/mesa_chromium.js`.

## 3. Testes que não puderam ser executados
Aparelho Android real (inicialização, abertura de telas, resposta de botões, FPS no Flutter, memória, partida longa); tempo de resposta do Render e do Supabase, Render↔Supabase, primeira × demais requisições, Render dormindo, Wi-Fi × 4G; consumo de rede real; FPS do Flutter e dos efeitos de cartas fora do WebView; erros e timeouts de produção. Para todos: `medicao/ROTEIRO_ANDROID.md` (passo a passo e planilha).

## 4. Gargalos confirmados (por medida)
1. **Excesso de chamadas ao banco por rota:** /loja 50, /perfil 15, /eu 11, todas sequenciais (nenhuma paralela). Confirmado por contagem.
2. **Payload da partida cheio a cada consulta:** 329 candles (mediana) e 27 KB por segundo por jogador, ≈ 6,8 MB por partida, mesmo sem mudança. Confirmado.
3. **Ranking com 135 KB** para poucas linhas. Confirmado o tamanho (a causa provável, avatares embutidos, ainda não foi isolada).
4. **Efeitos do destaque do padrão derrubam o FPS** na mesa: 35,9 fps a 1× e 6,5 fps a 6× contra 60 fps em repouso (no proxy). Confirmado no proxy, e o custo aparece em tarefa/composição, não em JavaScript (script ≈ 0,1–0,2 s de 4–5 s).
5. **Processamento Python é pequeno:** 5–10 ms por rota, 14 ms por consulta de partida, 18 ms por jogada. Então o tempo percebido não vem do código Python.

## 5. Gargalos ainda não comprovados
- **Falta de reaproveitamento de conexão HTTP** com o Supabase (visível no código, `banco.py:383`), mas o custo real do handshake em produção não foi medido.
- Latência Render↔Supabase, tempo de acordar o Render, impacto de 4G.
- Qual parte exata dos efeitos custa mais (sombras de canvas, zoom por CSS, partículas) e se o mesmo ocorre em GPU Android.
- Concorrência real de dois jogadores no Postgres.
- FPS, memória e jank do Flutter e tempo de inicialização do app.
- Primeira chamada de `/loja` de 612 ms local (provável carga de catálogo) precisa ser reconferida em produção.

## 6. Valores de referência (linha de base para comparar depois)
Os da §1.1 a §1.4 (mesmo script, mesmos dados de teste). Para comparação justa, rodar de novo com o mesmo comando e conferir: chamadas por rota, bytes por consulta, candles por consulta, FPS dos efeitos em 1×/4×/6×.

## 7. Metas recomendadas (a validar após a linha de base real em aparelho)
- Chamadas ao banco: /loja ≤ 8, /perfil ≤ 6, /eu ≤ 5 (hoje 50/15/11).
- Consulta de partida sem novidade: ≤ 2 KB (hoje 27 KB) e ≤ 1 chamada ao banco; candles novos apenas.
- Ranking: ≤ 20 KB (hoje 135 KB).
- Efeitos de ativação: ≥ 50 fps a 4× e nenhum quadro > 100 ms no proxy (hoje 12 fps e 883 ms); depois confirmar em Android.
- Metas de tempo de tela, inicialização e FPS do Flutter: **só definir após a medição no aparelho** (não há dado).

## 8. Arquivos que serão modificados na etapa 2 (previsão)
`banco.py` (sessão HTTP reutilizável em `_rest`); `api/main.py` (/loja, /perfil, /eu, ranking: menos chamadas, cache controlado); funções chamadas por essas rotas (`tickercoins*`, `loja_vitrine`, `perfis`, `trofeus`); `trader_online_dados.py`, `trader_grafico.py` e `trader_battle.py` (resposta de partida sem reenviar candles); `app/lib/api.dart` e `partida.dart` (cache local e consulta incremental); `trader_front/index.html` (efeitos); testes novos de regressão por contagem de chamadas. Etapa 2 só começa com sua autorização.
