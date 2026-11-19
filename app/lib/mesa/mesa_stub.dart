import 'package:flutter/material.dart';

/// Fora da web (APK) a mesa entra numa próxima etapa (WebView). Por enquanto, um aviso.
class MesaHost {
  MesaHost({required this.aoEvento, required this.aoPronto});
  final void Function(Map<String, dynamic> valor) aoEvento;
  final void Function() aoPronto;

  Widget widget() => const Center(child: Text('A partida ainda não abre nesta versão do app. Use o link do navegador.'));

  void desenhar(Map<String, dynamic> args) {}

  void fechar() {}
}

/// Fora da web o relatório entra junto com a mesa (WebView), numa próxima etapa.
class RelatorioView {
  RelatorioView(this.html);
  final String html;

  Widget widget() => const Center(child: Text('Relatório disponível na versão do navegador.'));
}
