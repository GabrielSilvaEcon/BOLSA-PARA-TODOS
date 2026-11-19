// Mesa de jogo do Trade Battle: a MESMA tela do app antigo (trader_front/index.html), aberta dentro do app.
// Na web ela roda num iframe e conversa por mensagens (o mesmo protocolo que usava com o Streamlit).
export 'mesa_stub.dart' if (dart.library.js_interop) 'mesa_web.dart';
