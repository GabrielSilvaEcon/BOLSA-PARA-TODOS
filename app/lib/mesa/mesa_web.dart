import 'dart:js_interop';
import 'dart:ui_web' as ui_web;

import 'package:flutter/material.dart';
import 'package:web/web.dart' as web;

/// Mesa de jogo na web: iframe com a página original (assets/mesa/index.html, copiada de trader_front/index.html no build).
/// O app manda os dados com "streamlit:render" e recebe as jogadas com "streamlit:setComponentValue", como fazia o Streamlit.
class MesaHost {
  MesaHost({required this.aoEvento, required this.aoPronto}) {
    ui_web.platformViewRegistry.registerViewFactory(_tipo, (int _) {
      final f = web.HTMLIFrameElement()
        ..src = 'assets/assets/mesa/index.html'
        ..style.border = '0'
        ..style.width = '100%'
        ..style.height = '100%'
        ..allow = 'fullscreen';
      _iframe = f;
      return f;
    });
    web.window.addEventListener('message', _ouvinte);
  }

  final void Function(Map<String, dynamic> valor) aoEvento;
  final void Function() aoPronto;
  final String _tipo = 'mesa-${DateTime.now().microsecondsSinceEpoch}';
  web.HTMLIFrameElement? _iframe;
  bool _pronta = false;
  Map<String, dynamic>? _pendente;

  late final JSFunction _ouvinte = ((web.Event ev) {
    final dados = (ev as web.MessageEvent).data.dartify();
    if (dados is! Map || dados['isStreamlitMessage'] != true) return;
    switch (dados['type']) {
      case 'streamlit:componentReady':
        _pronta = true;
        aoPronto();
        final p = _pendente;
        if (p != null) desenhar(p);
        break;
      case 'streamlit:setComponentValue':
        final v = dados['value'];
        if (v is Map) aoEvento(Map<String, dynamic>.from(v.map((k, x) => MapEntry('$k', x))));
        break;
    }
  }).toJS;

  Widget widget() => HtmlElementView(viewType: _tipo);

  /// Manda os dados da partida para a mesa desenhar (o mesmo "args" que o Streamlit mandava).
  void desenhar(Map<String, dynamic> args) {
    _pendente = args;
    final janela = _iframe?.contentWindow;
    if (!_pronta || janela == null) return;
    janela.postMessage({'type': 'streamlit:render', 'args': args}.jsify(), '*'.toJS);
  }

  void fechar() => web.window.removeEventListener('message', _ouvinte);
}

/// Relatório do fim da partida: a página HTML pronta que o servidor manda, mostrada num iframe (mesmo visual do app antigo).
class RelatorioView {
  RelatorioView(this.html) {
    ui_web.platformViewRegistry.registerViewFactory(_tipo, (int _) {
      return web.HTMLIFrameElement()
        ..srcdoc = html.toJS
        ..style.border = '0'
        ..style.width = '100%'
        ..style.height = '100%';
    });
  }

  final String html;
  final String _tipo = 'relatorio-${DateTime.now().microsecondsSinceEpoch}';

  Widget widget() => HtmlElementView(viewType: _tipo);
}
