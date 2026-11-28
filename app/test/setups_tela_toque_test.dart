import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/api.dart';
import 'package:tickerhunters/setups.dart';

Map<String, dynamic> _s(String id, String nome, bool eq) => {
      'id': id, 'nome': nome, 'raridade': 'comum', 'tipo': 'candle', 'direcao': 'compra', 'regiao': 'Suporte', 'subtitulo': 'Sub $nome', 'resumo': 'Resumo $nome',
      'caracteristicas': ['Condição A'], 'indicadores': ['Ind A'], 'regra': {'compra': 'x', 'venda': ''}, 'cores': {'principal': '#2EE59D', 'brilho': '#FFD76A'}, 'assets': {'carta': null},
      'equipado': eq, 'fonte_regra': '', 'estatisticas': {'ativacoes': 0, 'entradas': 0},
      'carta': {'gatilho': 'Gatilho $nome', 'stop': 'Stop', 'alvo': 'Alvo', 'alvo_curto': 'Alvo', 'regiao': 'Suporte'},
    };

class _ApiFalsa extends Api {
  _ApiFalsa(this.equipados) : super(tokenAtual: () => null);
  final Set<String> equipados;
  final posts = <String>[];
  final nomes = {'martelo': 'Martelo', 'engolfo_alta': 'Engolfo de Alta', 'estrela_cadente': 'Estrela Cadente'};

  @override
  Future<Map<String, dynamic>> get(String caminho) async => {
        'limite': 2,
        'todos_liberados': true,
        'total': 3,
        'equipados': equipados.toList(),
        'itens': [for (final e in nomes.entries) _s(e.key, e.value, equipados.contains(e.key))],
      };

  @override
  Future<Map<String, dynamic>> post(String caminho, [Map<String, dynamic>? corpo]) async {
    posts.add('$caminho ${corpo?['id']}');
    if (caminho == '/setups/equipar') equipados.add('${corpo!['id']}');
    if (caminho == '/setups/desequipar') equipados.remove('${corpo!['id']}');
    return {'ok': true};
  }
}

Future<_ApiFalsa> _abre(WidgetTester t, Set<String> equipados) async {
  t.view.physicalSize = const Size(900, 1600);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  final api = _ApiFalsa(equipados);
  await t.pumpWidget(MaterialApp(home: SetupsTela(api: api)));
  await t.pumpAndSettle();                                                    // as cartas entram deslizando: espera assentarem antes de tocar
  return api;
}

void main() {
  testWidgets('tocar numa carta a coloca em uso; tocar de novo tira; no limite avisa e não equipa', (t) async {
    final api = await _abre(t, {});
    expect(find.text('EM USO'), findsNothing);
    await t.tap(find.text('Martelo'));
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));                           // (pumpAndSettle esperaria o aviso sumir sozinho)
    expect(api.posts, ['/setups/equipar martelo']);
    expect(find.text('EM USO'), findsOneWidget);
    expect(find.textContaining('Martelo agora é um setup em uso'), findsOneWidget);
    await t.tap(find.text('Engolfo de Alta'));
    await t.pumpAndSettle();
    expect(find.text('EM USO'), findsNWidgets(2));
    await t.pump(const Duration(seconds: 3));                                   // o aviso anterior some sozinho (senão cobre a última carta)
    await t.pumpAndSettle();
    await t.tap(find.text('Estrela Cadente'));                                  // já são 2 em uso: avisa, não chama o servidor
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(api.posts.length, 2);
    expect(find.textContaining('Você já está usando 2 setups'), findsOneWidget);
    await t.pump(const Duration(seconds: 3));
    await t.pumpAndSettle();
    await t.tap(find.text('Martelo'));                                          // tocar numa carta em uso tira
    await t.pump();
    await t.pump(const Duration(milliseconds: 400));
    expect(api.posts.last, '/setups/desequipar martelo');
    expect(find.text('EM USO'), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('segurar 2 segundos abre o detalhe já no verso e NÃO muda o setup em uso', (t) async {
    final api = await _abre(t, {});
    final g = await t.startGesture(t.getCenter(find.text('Martelo')));
    await t.pump(const Duration(milliseconds: 50));
    await t.pump(const Duration(milliseconds: 1000));
    await t.pump(const Duration(milliseconds: 1100));
    await g.up();
    await t.pumpAndSettle();
    expect(find.textContaining('Toque na carta para voltar à frente'), findsOneWidget);       // o detalhe abriu com a carta virada
    expect(find.text('USAR ESTE SETUP'), findsOneWidget);
    expect(api.posts, isEmpty);                                                               // o toque ao soltar não equipou
    expect(t.takeException(), isNull);
  });
}
