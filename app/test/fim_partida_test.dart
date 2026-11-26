import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/fim_partida.dart';

void main() {
  Future<void> abre(WidgetTester t, {VoidCallback? novo, VoidCallback? menu}) async {
    await t.pumpWidget(MaterialApp(
        home: Builder(
            builder: (ctx) => Scaffold(body: Center(child: TextButton(onPressed: () => mostrarFimDePartida(ctx, jogarNovamente: novo ?? () {}, voltarAoMenu: menu ?? () {}), child: const Text('abrir')))))));
    await t.tap(find.text('abrir'));
    await t.pumpAndSettle();
  }

  testWidgets('o pop-up de fim de partida mostra só os dois botões e não fecha tocando fora nem no voltar', (t) async {
    await abre(t);
    expect(find.text('PARTIDA ENCERRADA'), findsOneWidget);
    expect(find.text('Jogar novamente'), findsOneWidget);
    expect(find.text('Voltar ao menu'), findsOneWidget);
    await t.tapAt(const Offset(4, 4)); // fora do pop-up
    await t.pumpAndSettle();
    expect(find.text('PARTIDA ENCERRADA'), findsOneWidget);
    await t.binding.handlePopRoute(); // botão voltar do aparelho
    await t.pumpAndSettle();
    expect(find.text('PARTIDA ENCERRADA'), findsOneWidget);
  });

  testWidgets('cada botão fecha o pop-up e chama a sua ação', (t) async {
    var novo = 0, menu = 0;
    await abre(t, novo: () => novo++, menu: () => menu++);
    await t.tap(find.text('Jogar novamente'));
    await t.pumpAndSettle();
    expect([novo, menu], [1, 0]);
    expect(find.text('PARTIDA ENCERRADA'), findsNothing);
    await t.tap(find.text('abrir'));
    await t.pumpAndSettle();
    await t.tap(find.text('Voltar ao menu'));
    await t.pumpAndSettle();
    expect([novo, menu], [1, 1]);
  });
}
