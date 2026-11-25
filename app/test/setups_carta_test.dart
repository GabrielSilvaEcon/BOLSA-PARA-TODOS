import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/setups.dart';

void main() {
  for (final raridade in ['comum', 'rara', 'epica', 'lendaria']) {
    for (final largura in [90.0, 150.0, 190.0]) {
      testWidgets('carta provisória $raridade a $largura px desenha sem estourar o layout', (t) async {
        final s = {
          'id': 'turtle_trading',
          'nome': 'Turtle Trading',
          'raridade': raridade,
          'caracteristicas': ['Compra no rompimento da máxima dos últimos 200 candles', 'Venda no rompimento da mínima', 'Só o primeiro rompimento do canal'],
          'assets': {'carta': null},
        };
        await t.pumpWidget(MaterialApp(home: Scaffold(body: Center(child: SetupCarta(setup: s, largura: largura)))));
        expect(tester(t), isNull);
        expect(find.text('ARTE PROVISÓRIA'), findsOneWidget);
      });
    }
  }
}

Object? tester(WidgetTester t) => t.takeException();
