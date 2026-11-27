import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/api.dart';
import 'package:tickerhunters/confronto.dart';
import 'package:tickerhunters/ticker_online.dart';

final _dados = {
  'voce': {'nome': 'ANA_H', 'avatar_img': null, 'trofeus': 40, 'divisao': {'id': 'bronze', 'nome': 'Bronze', 'cor': '#CD7F32', 'nivel': 0}},
  'adversarios': [
    {'nome': 'Rafa_Trader_com_um_nome_bem_comprido', 'avatar_img': null, 'trofeus': 230, 'divisao': {'id': 'prata', 'nome': 'Prata', 'cor': '#C0C0C0', 'nivel': 1}}
  ],
};

Future<void> _abre(WidgetTester t, Size tela, void Function(BuildContext) fim, {bool semAnimacao = false}) async {
  t.view.physicalSize = tela;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  await t.pumpWidget(MaterialApp(
    builder: (c, child) => MediaQuery(data: MediaQuery.of(c).copyWith(disableAnimations: semAnimacao), child: child!),
    home: ConfrontoTela(dados: _dados, aoTerminar: fim),
  ));
}

/// Avança o relógio do teste em passos de 100 ms: a cadeia (entrar na fila, buscar o confronto, trocar de rota) precisa de vários quadros.
Future<void> _avanca(WidgetTester t, int ms) async {
  for (var i = 0; i < ms ~/ 100; i++) {
    await t.pump(const Duration(milliseconds: 100));
  }
}

class _ApiFalsa extends Api {
  _ApiFalsa({this.confrontoOk = true, this.demora = Duration.zero}) : super(tokenAtual: () => null);
  final bool confrontoOk;
  final Duration demora;
  @override
  Future<Map<String, dynamic>> get(String caminho) async {
    if (caminho == '/eu') return {'perfil': {'usuario': 'ANA_H'}, 'nivel': {'nivel': 3}, 'trofeus': 40};
    if (caminho.endsWith('/confronto')) {
      await Future<void>.delayed(demora);
      if (!confrontoOk) throw ApiErro('sem confronto');
      return _dados;
    }
    return {'estado': 'fila'};
  }

  @override
  Future<Map<String, dynamic>> post(String caminho, [Map<String, dynamic>? corpo]) async => {'ok': true};
}

void main() {
  for (final tela in const [Size(390, 844), Size(360, 640)]) {
    testWidgets('confronto (${tela.width.toInt()}x${tela.height.toInt()}): você, VS e adversário com divisão, sem estourar, e segue sozinho', (t) async {
      var fim = 0;
      await _abre(t, tela, (_) => fim++);
      await t.pump(const Duration(milliseconds: 1500));
      for (final txt in ['VOCÊ', 'ADVERSÁRIO', 'VS', 'ANA_H', 'Bronze · 40', 'Prata · 230', 'TRADE BATTLE']) {
        expect(find.text(txt), findsOneWidget, reason: txt);
      }
      expect(fim, 0);
      await t.pump(const Duration(seconds: 2));
      expect(fim, 1, reason: 'segue sozinho para a partida, uma vez só');
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox());
    });
  }

  testWidgets('tocar pula o confronto (uma vez só, mesmo tocando de novo e depois do tempo)', (t) async {
    var fim = 0;
    await _abre(t, const Size(390, 844), (_) => fim++);
    await t.pump(const Duration(milliseconds: 300));
    await t.tapAt(const Offset(200, 400));
    await t.tapAt(const Offset(200, 420));
    await t.pump(const Duration(seconds: 4));
    expect(fim, 1);
    await t.pumpWidget(const SizedBox());
  });

  testWidgets('com as animações desligadas no aparelho: aparece por um instante e segue', (t) async {
    var fim = 0;
    await _abre(t, const Size(390, 844), (_) => fim++, semAnimacao: true);
    await t.pump();
    expect(find.text('VS'), findsOneWidget);
    await t.pump(const Duration(milliseconds: 700));
    expect(fim, 1);
    await t.pumpWidget(const SizedBox());
  });

  group('na busca do Trade Battle', () {
    Future<void> busca(WidgetTester t, Api api) async {
      t.view.physicalSize = const Size(390, 844);
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.reset);
      await t.pumpWidget(MaterialApp(
        home: BuscaTela(
          api: api,
          rota: '/trade/fila',
          confronto: (id) => '/trade/salas/$id/confronto',
          abrir: (id) => MaterialPageRoute<void>(builder: (_) => Scaffold(body: Text('PARTIDA $id'))),
          entrar: () async => {'estado': 'partida', 'id': 'P1'},
        ),
      ));
    }

    testWidgets('achou o adversário: mostra o confronto e depois abre a partida', (t) async {
      await busca(t, _ApiFalsa());
      await _avanca(t, 1200);
      expect(find.text('VS'), findsOneWidget);
      expect(find.text('PARTIDA P1'), findsNothing);
      await _avanca(t, 4000);
      expect(find.text('PARTIDA P1'), findsOneWidget);
      await t.pumpWidget(const SizedBox());
    });

    testWidgets('se o confronto falha ou demora, a partida abre direto (nunca atrasa o jogo)', (t) async {
      await busca(t, _ApiFalsa(confrontoOk: false));
      await _avanca(t, 1500);
      expect(find.text('PARTIDA P1'), findsOneWidget);
      expect(find.text('VS'), findsNothing);
      await t.pumpWidget(const SizedBox());
      await busca(t, _ApiFalsa(demora: const Duration(seconds: 5)));
      await _avanca(t, 4000);                                   // o confronto tem até 2,5 s para chegar; passou disso, a partida abre direto
      expect(find.text('PARTIDA P1'), findsOneWidget);
      expect(find.text('VS'), findsNothing);
      await _avanca(t, 3000);
      await t.pumpWidget(const SizedBox());
    });
  });
}
