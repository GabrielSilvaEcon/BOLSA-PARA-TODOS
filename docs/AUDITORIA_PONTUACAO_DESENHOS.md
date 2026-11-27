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


## Depois da correção ("acima do acaso", PR de nov/2026)
Cada nível e cada zona agora vale `0,5 + peso × (acerto − acaso)/2`, onde `acaso` é a taxa de acerto de desenhos do mesmo tipo em outras distâncias
(0,6×, 0,8×, 1,2× e 1,4× a distância original) no MESMO replay. Mesma simulação (200 cenários por formato):

| Truque, sem ler o gráfico | Antes | Depois |
|---|---|---|
| Rompimento 1 ATR, dois lados | 31,6 | 50,0 |
| Rompimento 2 ATR, dois lados | 50,7 | 49,5 |
| Resistência acima + suporte abaixo (2 ATR) | 66,1 | 49,8 |
| 6 níveis variados | 58,7 | 49,8 |
| 4 tendências planas coladas no preço | 51,5 | 51,5 (sem mudança) |
| Tudo junto | 53,4 | 50,3 |
| Oráculo (vê o futuro) | 81,2 | 70,3 |

O chute às cegas cai para ~50 (neutro) e o oráculo continua separado (70). Pendências: a linha de tendência ainda não usa o acaso (rende ~51,5 com
linhas planas); e a medição de HABILIDADE real (quem lê bem passa de 50?) precisa de cenários reais, não do simulado.
