import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:webview_flutter/webview_flutter.dart';

/// Mesa de jogo no celular (APK): a página original da mesa numa WebView.
/// Dentro da WebView a página é a janela principal, então as mensagens que ela "manda para o Streamlit" voltam para ela mesma:
/// um ouvinte instalado ao carregar repassa essas mensagens para o app pelo canal "Mesa".
class MesaHost {
  MesaHost({required this.aoEvento, required this.aoPronto}) {
    _c = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF0B0828))
      ..addJavaScriptChannel('Mesa', onMessageReceived: (m) => _mensagem(m.message))
      ..setNavigationDelegate(NavigationDelegate(onPageFinished: (_) => _carregou()))
      ..loadFlutterAsset('assets/mesa/index.html');
  }

  final void Function(Map<String, dynamic> valor) aoEvento;
  final void Function() aoPronto;
  late final WebViewController _c;
  bool _pronta = false;
  Map<String, dynamic>? _pendente;

  Future<void> _carregou() async {
    await _c.runJavaScript(
      "window.addEventListener('message',function(e){var d=e.data;"
      "if(d&&d.isStreamlitMessage&&d.type!=='streamlit:render'){Mesa.postMessage(JSON.stringify(d));}});",
    );
    _pronta = true;
    aoPronto();
    final p = _pendente;
    if (p != null) desenhar(p);
  }

  void _mensagem(String texto) {
    final d = jsonDecode(texto);
    if (d is! Map || d['type'] != 'streamlit:setComponentValue') return;
    final v = d['value'];
    if (v is Map) aoEvento(Map<String, dynamic>.from(v));
  }

  Widget widget() => WebViewWidget(controller: _c);

  /// Manda os dados da partida para a mesa desenhar (o mesmo "args" que o Streamlit mandava).
  void desenhar(Map<String, dynamic> args) {
    _pendente = args;
    if (!_pronta) return;
    _c.runJavaScript("window.postMessage({type:'streamlit:render',args:${jsonEncode(args)}},'*');");
  }

  void fechar() {}
}

/// Relatório do fim da partida no celular: a página HTML pronta do servidor numa WebView.
class RelatorioView {
  RelatorioView(this.html) {
    _c = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0x00000000))
      ..loadHtmlString(html);
  }

  final String html;
  late final WebViewController _c;

  Widget widget() => WebViewWidget(controller: _c);
}
