# Roteiro de medição em Android real (a executar por você; não foi possível aqui)

Ferramentas gratuitas: Flutter DevTools, `adb`, Chrome `chrome://inspect` (para o WebView da mesa), Android Studio Profiler (opcional).
Regras: aparelho de entrada **e** um intermediário; build `flutter run --profile` (nunca debug); bateria > 50%, modo avião desligado, app fechado e sem outros apps pesados. **3 repetições por item, anote a mediana.** Faça tudo em **Wi-Fi** e repita o bloco de rede em **4G**.

## 0. Preparação
1. `flutter run --profile -d <aparelho>`; abra o DevTools (Performance, Memory, Network).
2. Descubra o pacote: `adb shell pm list packages | grep ticker`.
3. Para o WebView: no app, ative a depuração do WebView (hoje não ativada: pedir na etapa 2) e abra `chrome://inspect`.

## 1. Inicialização (frio e morno)
- Frio: `adb shell am force-stop <pacote>` e depois `adb shell am start -W -n <pacote>/<activity>` → anote **TotalTime** e **WaitTime**.
- Morno: volte à home do Android e reabra → mesmo comando.
- Com o Render **dormindo** (20+ min sem uso) e **acordado**: repita o frio e anote também o tempo até a Home mostrar dados (cronômetro de tela).

## 2. Abertura de cada tela (cronômetro de vídeo ou DevTools Timeline)
Do toque até a tela completa: Home → Trade Battle → Meus Setups (e Escolher setup) → Loja → Perfil → Ranking → Ticker Battle → Carteira → Mercado. Anote: tempo até aparecer a interface e tempo até os dados chegarem (1ª visita e 2ª visita).

## 3. Resposta dos botões
Grave a tela a 60 fps (`adb shell screenrecord`) e conte quadros entre o toque e a 1ª mudança visual, em: BATALHAR, equipar setup, COMPRAR, VENDER, ZERAR, confirmar estratégia, ENTRAR/RECUSAR no setup. Anote **toque → mudança visual** e **toque → confirmação do servidor**.

## 4. FPS e quadros perdidos
- DevTools → Performance: grave 30 s em cada cenário e anote **% de quadros acima de 16 ms (jank)** e o **pior quadro**: transição entre telas; rolagem da Loja e do Ranking; abrir o pop-up de setups.
- `adb shell dumpsys gfxinfo <pacote> reset` antes e `adb shell dumpsys gfxinfo <pacote>` depois: anote **Janky frames %** e percentis 90/95/99.
- **Efeitos das cartas / ativação do setup:** a mesa roda no WebView. Dispare um setup (ou use uma partida contra o bot até ativar) e grave a sequência mira → destaque de 5 s → cartão. Anote o FPS (DevTools do WebView, painel Performance) e quadros > 34 ms.

## 5. Memória e CPU
- DevTools → Memory: snapshot na Home, depois após navegar por 10 telas e voltar à Home 3 vezes; compare (vazamento = só cresce).
- `adb shell dumpsys meminfo <pacote>` (TOTAL PSS) em: Home, durante a partida (minuto 1 e minuto 5), após a partida.
- CPU: `adb shell top -H -n 1 | grep <pacote>` a cada 10 s durante uma partida de 5 min.

## 6. Partida longa
Jogue 1 partida completa (15 min) e anote a cada 2 min: FPS, PSS, CPU, temperatura (`adb shell dumpsys battery`), e se houve congelamento. Repita com 2 aparelhos jogando um contra o outro e operando ao mesmo tempo.

## 7. Rede
- Dados transferidos: DevTools → Network (ou `adb shell dumpsys netstats`) durante a partida completa; anote bytes por consulta e total.
- Compare **Wi-Fi × 4G**, e **primeira requisição × seguintes** (a primeira abre conexão nova).
- Com o Render dormindo: tempo da 1ª requisição (`/saude`) até responder.

## Planilha de resultados (preencher)
| Item | Aparelho | Rede | Mediana de 3 | Observação |
|---|---|---|---|---|
| Inicialização fria | | | | |
| ... | | | | |
