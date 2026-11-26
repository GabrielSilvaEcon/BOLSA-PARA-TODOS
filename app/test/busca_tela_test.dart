import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/api.dart';
import 'package:tickerhunters/ticker_online.dart';

class _ApiFalsa extends Api {
  _ApiFalsa(this.respostas) : super(tokenAtual: () => null);
  final List<Map<String, dynamic>> respostas; // o que GET /fila devolve, na ordem
  @override
  Future<Map<String, dynamic>> get(String caminho) async {
    if (caminho == '/eu') return {'perfil': {'usuario': 'Bússola'}, 'nivel': {'nivel': 12}, 'trofeus': 1245};
    return respostas.isEmpty ? {'estado': 'fila'} : respostas.removeAt(0);
  }

  @override
  Future<Map<String, dynamic>> post(String caminho, [Map<String, dynamic>? corpo]) async => {'ok': true};
}

Future<void> _abre(WidgetTester t, Size tela, Api api, {bool avisoBot = true}) async {
  t.view.physicalSize = tela;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  await t.pumpWidget(MaterialApp(home: BuscaTela(api: api, rota: '/trade/fila', titulo: 'Trade Battle · Online', avisoBot: avisoBot)));
  await t.pump(const Duration(milliseconds: 100));
}

void main() {
  for (final tela in [const Size(390, 800), const Size(900, 700)]) {
    testWidgets('tela de busca (${tela.width.toInt()}x${tela.height.toInt()}) mostra você, o jogador buscando, a dica e o cancelar, sem estourar', (t) async {
      await _abre(t, tela, _ApiFalsa([]));
      expect(t.takeException(), isNull);
      expect(find.textContaining('PROCURANDO'), findsOneWidget);
      expect(find.text('Bússola'), findsOneWidget);
      expect(find.text('Nível 12'), findsOneWidget);
      expect(find.text('Buscando…'), findsOneWidget);
      expect(find.text('CANCELAR'), findsOneWidget);
      await t.pumpWidget(const SizedBox()); // desmonta (cancela os temporizadores)
    });
  }

  testWidgets('quando o servidor devolve a partida, a tela abre direto, sem aviso de bot', (t) async {
    await _abre(t, const Size(390, 800), _ApiFalsa([{'estado': 'partida', 'id': 'p1'}]));
    await t.pump(const Duration(seconds: 3));
    expect(find.textContaining('bot'), findsNothing);
    await t.pumpWidget(const SizedBox());
  });
}
