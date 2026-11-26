import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/api.dart';
import 'package:tickerhunters/trade.dart';

class _ApiFalsa extends Api {
  _ApiFalsa() : super(tokenAtual: () => null);
  @override
  Future<Map<String, dynamic>> get(String caminho) async {
    if (caminho == '/setups') {
      return {
        'limite': 2,
        'itens': [
          {'id': 'estrela_cadente', 'nome': 'Estrela Cadente', 'equipado': true},
          {'id': 'setup_classico', 'nome': 'Setup Clássico', 'equipado': true},
        ]
      };
    }
    return {'corridas': [{'id': 'rapida', 'reais': 3}], 'ativa': null};
  }
}

void main() {
  for (final tela in [const Size(390, 844), const Size(360, 640)]) {
    testWidgets('home do Trade Battle (${tela.width.toInt()}x${tela.height.toInt()}) tem BATALHAR, Meus Setups e atalhos, sem estourar', (t) async {
      t.view.physicalSize = tela;
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      await t.pumpWidget(MaterialApp(home: TradeTela(api: _ApiFalsa())));
      await t.pump(const Duration(seconds: 2));
      expect(t.takeException(), isNull);
      expect(find.text('BATALHAR'), findsOneWidget);
      expect(find.text('MEUS SETUPS'), findsOneWidget);
      expect(find.text('ATIVO'), findsNWidgets(2));
      expect(find.text('Solo'), findsOneWidget);
      expect(find.text('Amigo'), findsOneWidget);
      expect(find.text('Ranking'), findsOneWidget);
      await t.pumpWidget(const SizedBox());
    });
  }
}
