# Auditoria da nota dos desenhos (nov/2026)

Ferramenta: `python3 tools/trapaca/simular.py [N]` roda "jogadores sem leitura" (só truques) sobre N cenários por formato e mede a nota
de `trader_leitura.avaliar_desenhos`. Ponto neutro do jogo: nota 50 (`qual + (nota/50 − 1)` em trader_battle), acima disso a nota SOMA pontos.

## Resultado (cenários simulados, 200 por formato; compara truques entre si, não prevê notas reais)

| Truque, sem ler o gráfico | Nota média | % acima de 50 |
|---|---|---|
| Nenhum desenho | sem nota | – |
| Rompimento a 1 ATR, dois lados | 31,6 | 0% |
| Rompimento a 2 ATR, dois lados | 50,7 | 26% |
| **Resistência acima + suporte abaixo (2 ATR)** | **66,1** | **75%** |
| 6 níveis variados | 58,7 | 64% |
| 4 tendências planas coladas no preço | 51,5 | 54% |
| Tudo junto | 53,4 | 55% |
| Oráculo (vê o futuro, teto) | 81,2 | 100% |

## Conclusões
1. O peso por distância funciona: desenho colado no preço (1 ATR) rende pouco (31,6).
2. **Suporte/resistência a ~2 ATR rendem 62–66 sem nenhuma leitura**, bem acima do neutro (50): é pontuação de graça. A reação "tocou e voltou em 5 candles" é fácil
   de cumprir por acaso com candles curtos.
3. Endurecer a reação (exigir quique de 0,5 a 1,5 ATR) derruba a nota do chute, mas derruba igual a de quem acerta (testado com pivôs reais): só desloca a escala.
4. **Limite da medição:** o cenário simulado é passeio aleatório, não tem suporte nem resistência de verdade, então ele não mede habilidade, só o piso do acaso.
   Medir se ler bem supera o acaso exige cenários REAIS (guardados no banco do servidor, indisponíveis no ambiente de desenvolvimento).

## Direção proposta
Pontuar o que o desenho supera o ACASO naquele gráfico: para cada desenho, calcular no mesmo replay a taxa de acerto de desenhos do mesmo tipo e distância
colocados em outros preços; o valor do desenho = acerto − acaso (normalizado). Funciona com qualquer mercado (usa o próprio caminho do preço) e
elimina a pontuação de graça sem mudar a liberdade de desenhar.
