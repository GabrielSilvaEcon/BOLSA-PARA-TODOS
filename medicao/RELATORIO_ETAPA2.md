# Etapa 2 — Otimização de backend, consultas e cache

Medido com os mesmos scripts da Etapa 1 (`MEDIR=1 python -m pytest medicao -s`), mesmos dados de teste, banco SQLite local. **Não é medição de produção**: os ganhos de latência em produção dependem de Render e Supabase, que não pude medir.

## Comparação antes × depois
| Indicador | Linha de base | Depois | Meta | Situação |
|---|---|---|---|---|
| Chamadas /loja | 50 | **8** | ≤ 8 | atingida |
| Chamadas /perfil | 15 | **6** | ≤ 6 | atingida |
| Chamadas /eu | 11 | **6** (2 são a validação da sessão do app; **4** com a sessão do Supabase já em cache) | ≤ 5 | atingida no caminho de produção com Supabase |
| /trade/central | 7 | 3 | n/a | |
| /ranking/trade/tela (chamadas) | 5 | 3 | n/a | |
| Ranking, bytes decodificados | 135.078 | 135.078 | ≤ 20 KB | **não reduzido** (ver abaixo) |
| Ranking, bytes na rede (gzip, já existia) | n/m* | **9.016** | ≤ 20 KB | atingida (medido agora) |
| Partida sem novidades, resposta | 27.206 B (decodificado) | **131 B** (mediana) | ≤ 2 KB | atingida |
| Partida, resposta mediana por consulta | 27.206 B | **2.300 B** (decodificada) / 1.026 B na rede | – | |
| Partida completa, dados decodificados | 5.926 KB | **482 KB** (−91,9%) | – | |
| Partida completa, dados na rede (gzip) | 1.404 KB | **212 KB** (−84,9%) | – | |
| Consultas ao banco por consulta sem novidades | 3 (2 de sessão local + 1) | **1** (caminho Supabase) | ≤ 1 | atingida |
| Processamento por consulta (p50) | 13,8 ms | 9,6 ms | – | |
| Conflitos / erros / timeouts (local) | 0 / 0 / 0 | 0–1 (resolvido pelo CAS) / 0 / 0 | – | |

\* a linha de base da Etapa 1 mediu só bytes decodificados; a compressão (gzip) já estava ativa no servidor, então o volume real na rede era menor do que os 135 KB e os 6,8 MB que eu reportei lá. Registro a correção.

Respostas de `/loja`, `/perfil` e `/eu` são **idênticas** às de antes (teste compara com a execução sem pré-carga e sem paralelismo).

Tipos de resposta numa partida de 228 consultas: 59 mínimas, 167 com cauda de candles, 2 completas. A maioria é "cauda" porque o candle em formação muda a cada segundo (2,3 KB), então a meta de 2 KB vale para consultas sem novidade (131 B).

## Mudanças (arquivos)
- `banco.py`: **sessão HTTP reutilizada por thread** (`requests.Session`, pool e keep-alive; timeouts 5 s conectar / 10 s ler; retentativa só de falha de conexão antes de a requisição sair; GET refeito uma vez com sessão nova se a conexão reaproveitada caiu; escritas nunca são repetidas); operador `in` em `_selecionar`; `pre_carregar_estados` (uma consulta traz vários estados da pessoa, só na requisição, descartada por gravação); `sis_comp_todos(cache_s=)` e `comp_publico_ler` com cache; `ident_bd()` na chave de todo cache.
- `cache_servidor.py` (novo): cache TTL em memória, cópias na saída, invalidação, tolerante a falha.
- `paralelo.py` (novo): leituras independentes em paralelo, com o contexto da requisição e erro por tarefa.
- `tickercoins.py`: `vigentes()` e `pode_comprar(ativos_ja_lidos=)` (a loja relia os pedidos duas vezes por produto).
- `api/main.py`: `/loja` (compras lidas uma vez, saldo vem do histórico, leituras em paralelo), `/perfil` e `/eu` (pré-carga, leitura única de dados de estudo, loja lida uma vez, paralelo no `/eu`), rankings com cache de 15 s, protocolo incremental da partida (`_com_etag`, `_enxuga`) em `GET /trade/salas/{pid}` e `GET /trade/solo/{pid}`.
- `trader_dados.py`: índice dos gráficos com cache de 30 s.
- `app/lib/estado_partida.dart` (novo) e `app/lib/partida.dart`: o app guarda o último estado completo e pede só o incremental; a cada 20 respostas seguidas pede o completo; qualquer inconsistência descarta e pede o completo.
- Testes: `test_banco_desempenho.py` (11), `test_etapa2_desempenho.py` (19), `app/test/estado_partida_test.dart` (6) e extensões em `medicao/`.

## Como o protocolo incremental funciona
O servidor sempre monta o estado completo (a verdade é dele). Respostas completas levam `e` (hash do estado sem `seg` e `prox_ms`). O app consulta com `e`, `n` (quantos candles tem), `u` (soma do penúltimo candle) e `fk` (fase/rodada). Igual a `e` → `{sem_mudanca, vol:{seg, prox_ms}}`. Diferente com candles compatíveis → estado completo com só a cauda dos candles (o candle em formação é reenviado). Candles a menos, soma diferente, outra fase/rodada ou fim de partida → completo. Sem parâmetros (app antigo) → completo, como antes. O controle de concorrência (versão e CAS) não foi tocado.

## Riscos
- **Cache desatualizado:** só dado público ou igual para todos; TTL de 15–30 s; invalidado na hora no mesmo processo; com mais de um worker, vale o TTL (o Render atual roda um processo). Saldo, inventário, resultados, operações e estado de partida **não** entram em cache.
- **Sessão HTTP:** uma por thread (sem compartilhar `Session`); conexão derrubada → refaz leitura uma vez; escrita não é repetida. Nenhum header ou chave alterado.
- **Paralelismo:** só leituras independentes; cada thread do pool mantém a sua sessão; falha de uma tarefa só aparece quando o resultado dela é lido.
- **Incremental:** resposta antiga que chegue fora de ordem é descartada pelo guard existente (`_ordem`); se mesmo assim encaixar, a versão `e` diverge e a consulta seguinte corrige. Um app antigo continua funcionando (recebe completo).

## Problemas que permaneceram
- **Ranking decodificado continua 135 KB** (avatares "raposa" são data URI de 7 KB cada; só 6 dos 64 avatares são feitos em código, mas o padrão é um deles). Na rede já são ~9 KB. Reduzir o decodificado exige incluir essas imagens como assets do app (nova versão do APK) e mudar o que o servidor devolve: **não feito** nesta etapa por exigir mudança visível/coordenada de versão.
- **Validação da sessão do app (e-mail e senha) faz 2 consultas a cada requisição.** É autenticação; não alterei. Cache curto da validação reduziria, mas atrasa a revogação de sessão: decisão sua.
- `/ticker/central` (7 chamadas, 39 KB) e `/trade/central` não foram o foco.
- Concorrência real no Postgres e latência Render↔Supabase continuam **sem medição**.

## Confirmação de funcionalidade
Nada foi removido: regras do jogo, pontuação, setups, ranking, autenticação, multiplayer e interface Flutter (telas, cartas, animações, canvas, HTML da mesa) não foram alterados. A mudança no app é só de rede (`partida.dart` e o novo `estado_partida.dart`).

## Implantação e reversão
Implantação: mesclar o PR; o Render faz o deploy sozinho (`autoDeploy`). O servidor é compatível com o app atual (sem parâmetros recebe a resposta completa); o ganho de partida só aparece com o app novo. Reversão: reverter o PR (`git revert`); o app novo continua funcionando com o servidor antigo (sem `e` na resposta o app pede sempre o completo). Não houve mudança de banco.
