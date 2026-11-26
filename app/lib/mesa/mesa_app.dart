import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart' show rootBundle;
import 'package:webview_flutter/webview_flutter.dart';

import '../diag/diag.dart';

/// Mesa de jogo no celular (APK): a página original da mesa numa WebView.
/// Dentro da WebView a página é a janela principal, então as mensagens que ela "manda para o Streamlit" voltam para ela mesma:
/// um ouvinte instalado ao carregar repassa essas mensagens para o app pelo canal "Mesa".
class MesaHost {
  MesaHost({required this.aoEvento, required this.aoPronto, String origem = 'partida'}) {
    if (kDiag) _diagId = Diag.novaMesa(origem);
    _c = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF081528))
      ..addJavaScriptChannel('Mesa', onMessageReceived: (m) => _mensagem(m.message))
      ..setNavigationDelegate(NavigationDelegate(onPageFinished: (_) => _carregou()));
    if (kDiag) _c.addJavaScriptChannel('Diag', onMessageReceived: (m) => Diag.mesaMsg(_diagId, m.message));
    _c.loadFlutterAsset('assets/mesa/index.html');
  }

  // --- só no APK de diagnóstico (kDiag); no app normal estes trechos nunca rodam ---
  int _diagId = 0;
  static String? _coletor;
  int? diagMarca(String nome) => Diag.mesaMarca(_diagId, nome);
  void diagJs(String js) {
    if (kDiag) _c.runJavaScript(js);
  }

  final void Function(Map<String, dynamic> valor) aoEvento;
  final void Function() aoPronto;
  late final WebViewController _c;
  bool _pronta = false;
  Map<String, dynamic>? _pendente;

  Future<void> _carregou() async {
    if (kDiag) {
      Diag.marca('mesa_pagina_carregada', mesa: _diagId);
      _coletor ??= await rootBundle.loadString('assets/diag/coletor.js');
      await _c.runJavaScript(_coletor!);
    }
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
    if (kDiag) Diag.marca('mesa_render_enviado', mesa: _diagId);
    // JSON.parse de uma string é bem mais rápido de processar no WebView do que um objeto literal de dezenas de KB (medido: ~2x), e chega ao mesmo objeto.
    _c.runJavaScript("window.postMessage({type:'streamlit:render',args:JSON.parse(${jsonEncode(jsonEncode(args))})},'*');");
  }

  /// No celular a tela do app por cima da WebView já recebe os toques (nada a fazer).
  void toques(bool ligados) {}

  void fechar() {
    if (kDiag && _diagId != 0) {
      try {
        _c.runJavaScript('__diag.enviar()'); // melhor esforço: o coletor também envia sozinho a cada 10 s
      } catch (_) {}
      Diag.mesaFechou(_diagId);
    }
  }
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
