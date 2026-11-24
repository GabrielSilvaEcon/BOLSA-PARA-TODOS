// Mesa de jogo do Trade Battle: a MESMA tela do app antigo (trader_front/index.html, copiada para assets/mesa/ no build).
// Na web ela roda num iframe; no celular (APK), numa WebView. Nos dois casos conversa por mensagens, com o mesmo
// protocolo que usava com o Streamlit ("streamlit:render" para desenhar, "streamlit:setComponentValue" para as jogadas).
export 'mesa_app.dart' if (dart.library.js_interop) 'mesa_web.dart';
