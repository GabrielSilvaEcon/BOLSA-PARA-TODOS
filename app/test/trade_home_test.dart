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
    testWidgets('home do Trade Battle (${tela.width.toInt()}x${tela.height.toInt()}) tem BATALHAR, os dois modos (Replay e Ao vivo) e Meus Setups, sem solo nem amigo, sem estourar', (t) async {
      t.view.physicalSize = tela;
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.resetPhysicalSize);
      await t.pumpWidget(MaterialApp(home: TradeTela(api: _ApiFalsa())));
      await t.pump(const Duration(seconds: 2));
      expect(t.takeException(), isNull);
      expect(find.text('BATALHAR'), findsOneWidget);
      expect(find.text('REPLAY'), findsOneWidget);             // os dois modos têm as mesmas funções
      expect(find.text('🔴 AO VIVO'), findsOneWidget);
      expect(find.text('MEUS SETUPS'), findsOneWidget);
      expect(find.text('ATIVO'), findsNWidgets(2));
      await t.tap(find.text('🔴 AO VIVO'));                     // trocar de modo não estoura a tela
      await t.pump();
      expect(t.takeException(), isNull);
      expect(find.text('Solo'), findsNothing);                 // sem treino solo nem convite de amigo nesta tela
      expect(find.text('Amigo'), findsNothing);
      await t.pumpWidget(const SizedBox());
    });
  }
}
