# Etapa 3 — Otimização gráfica e de renderização

## Arquivos alterados
- `trader_front/index.html` (mesa: canvas/efeitos)
- `app/lib/mesa/mesa_app.dart` (ponte Flutter→JS: `JSON.parse`)
- `medicao/*` (scripts de medição e capturas; sem impacto em produção)

## Diagnóstico
Medido em Chromium headless com render por software (proxy, NÃO é Android). O custo dominante era rasterização de operações de área grande e `shadowBlur` repetidos por frame (brilho da mira, colchetes, anel, vinheta, apagão, partículas). JS era pequeno (~0,2–0,7 s a cada 3,5 s). Refutado por medição: clearRect total, svZoom, svUI.

## Otimizações (sem remover efeitos)
- Sprites/camadas auxiliares reaproveitadas (`svOff`, tamanho em degraus de 64).
- Brilho calculado uma vez em baixa resolução (`svSombraUnica`) e brilho "assado" em cache (`svAssado`).
- Partículas por sprite; vinheta e brilho radial em baixa resolução.
- Camada de fundo `#cvfxb` redesenhada só quando a assinatura muda (`svFundo`).
- Ponte: `JSON.parse` em vez de literal JS (~2× mais rápido).
- Flutter: nenhum RepaintBoundary/cacheWidth aplicado — sem benefício comprovado (imagens já ≤ tamanho útil).

## Métricas (proxy, CPU 4×, FPS antes→depois)
- Mira: ~10–15 → ~19–20
- Destaque: ~13 → ~29–38
- Decisão: ~14 → ~36–54
- **Meta ≥50 fps a 4× NÃO foi atingida em mira/destaque no proxy.**
- **Aparelho Android real NÃO foi medido** (roteiro em `medicao/ROTEIRO_ANDROID.md`). Memória e abertura do jogo não foram medidas.

## Equivalência visual
Capturas antes/depois por fase (`medicao/capturas_efeitos.js`). Padrão: ≤0,8% dos pixels com diferença >24. Clássico: diferenças concentradas nas bordas de texto do card HTML (fase da animação CSS), canvas fora do card praticamente igual. Pequenas diferenças residuais por brilho/vinheta em baixa resolução são possíveis; validar em aparelho.

## Testes
pytest 657 ok (4 skipped); harness da mesa 54 ok; `flutter test` não executado (Flutter indisponível neste ambiente).

## Riscos
Brilho em baixa resolução pode diferir sutilmente; camada extra `#cvfxb` (mais memória de canvas); `JSON.parse` depende de escape duplo correto (coberto em `ponte_js.js`).

## Reversão
`git revert` do commit desta etapa (reverte index.html e mesa_app.dart). Nenhum deploy realizado; aguardando autorização.

## Validação final (Android)
- `flutter test`: **38 testes passaram**, 0 falhas.
- **Aparelho Android real: não medido.** Sem FPS/p95/travamentos, memória (inicial, destaque, após ativações, reentrada, crescimento), abertura do jogo nem teste de 10 minutos. Nenhum número do Chromium substitui isso.
- **Decisão do responsável:** o PR #162 foi mesclado sem a medição em aparelho real.
- Para medir depois, sem computador: APKs de diagnóstico `diag-antes` e `diag-depois` (releases do GitHub, branches de mesmo nome), com teste automático da mesa e exportação do relatório. Roteiro com computador em `medicao/ROTEIRO_ANDROID.md`.
- Reversão, se algo piorar no celular: `git revert` do merge do PR #162.
