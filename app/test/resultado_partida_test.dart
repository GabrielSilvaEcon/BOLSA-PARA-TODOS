import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/resultado_partida.dart';

List<Map<String, dynamic>> _velas() => [
      for (var i = 0; i < 40; i++) {'o': 30.0 + i * 0.1, 'h': 30.5 + i * 0.1, 'l': 29.8 + i * 0.1, 'c': 30.2 + i * 0.1, 't': '2026-01-05T10:00'},
    ];

Map<String, dynamic> _tela({List<Map>? ops}) => {
      'candles': _velas(),
      'revelados': 20,
      'mesa': {
        'operacoes': ops ??
            [
              {'direcao': 'alta', 'q': 10, 'val': 180.0},
              {'direcao': 'baixa', 'q': 10, 'val': 120.0},
              {'direcao': 'alta', 'q': 10, 'val': -75.0},
              {'direcao': 'baixa', 'q': 10, 'val': 0.0},
              {'direcao': 'alta', 'q': 10, 'val': 130.0},
              {'direcao': 'alta', 'q': 5, 'val': 20.0},
            ],
      },
    };

Map<String, dynamic> _fim({required double meu, required double rival, double pnl = 1250, Map? trofeus}) => {
      'resultado': {'pontos': meu, 'fin': {'pnl': pnl, 'pct_aposta': 12.5}},
      'revelado': {'ticker': 'PETR4', 'nome': 'Petrobras PN', 'de': '05/01/2026', 'ate': '06/01/2026', 'tf_nome': '15 minutos'},
      'placar': [
        {'rotulo': 'Você', 'voce': true, 'pos': 1, 'pontos': meu, 'ret_pct': 12.5},
        {'rotulo': 'Rival', 'voce': false, 'pos': 2, 'pontos': rival, 'ret_pct': 3.0},
      ],
      'xp': {'xp': 40},
      if (trofeus != null) 'trofeus': trofeus,
    };

final _tr = {
  'delta': 20, 't': 40, 'divisao': 'Bronze', 'resultado': 'vitoria',
  'dv': {'id': 'bronze', 'nome': 'Bronze', 'cor': '#CD7F32', 'nivel': 0, 'pct': 0.2, 'prox': {'nome': 'Prata', 'min': 200}},
};

Future<void> _mostra(WidgetTester t, ResultadoPartida r, Size tela) async {
  t.view.physicalSize = tela;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  await t.pumpWidget(MaterialApp(home: ResultadoPartidaTela(r: r, continuar: () {}, analise: () {})));
  await t.pump(const Duration(seconds: 2));
}

void main() {
  group('modelo', () {
    test('estado vem dos pontos contra o adversário e as contas fecham com as operações', () {
      final r = ResultadoPartida.de(_fim(meu: 50, rival: 30), _tela());
      expect(r.estado, 'vitoria');
      expect(ResultadoPartida.de(_fim(meu: 30, rival: 50), _tela()).estado, 'derrota');
      expect(ResultadoPartida.de(_fim(meu: 40, rival: 40.02), _tela()).estado, 'empate');
      expect([r.vitorias, r.derrotas, r.empates], [4, 1, 1]);
      expect(r.vitorias + r.derrotas + r.empates, r.operacoes.length);
      expect([r.compras, r.vendas], [4, 2]);
      expect(r.compras + r.vendas, r.operacoes.length);
    });

    test('troféus do servidor valem quando existem; variação e preço final saem dos candles reais', () {
      final r = ResultadoPartida.de(_fim(meu: 10, rival: 90, trofeus: {..._tr, 'resultado': 'derrota', 'delta': -12}), _tela());
      expect(r.estado, 'derrota');
      expect(r.precoFinal, closeTo(30.2 + 39 * 0.1, 1e-9));
      final base = 30.2 + 19 * 0.1;                                   // fecha do candle logo antes do início da partida
      expect(r.variacao, closeTo((r.precoFinal! / base - 1) * 100, 1e-9));
    });

    test('a frase respeita o que aconteceu: derrota com lucro e vitória com prejuízo', () {
      expect(ResultadoPartida.de(_fim(meu: 10, rival: 90, pnl: 300), _tela()).subtitulo, contains('lucrou'));
      expect(ResultadoPartida.de(_fim(meu: 10, rival: 90, pnl: -300), _tela()).subtitulo, contains('nem todo dia'));
      expect(ResultadoPartida.de(_fim(meu: 90, rival: 10, pnl: -300), _tela()).subtitulo, contains('prejuízo'));
    });

    test('só há tela de duelo com adversário no placar; sem operações no painel usa as do resultado', () {
      expect(ResultadoPartida.temAdversario({'placar': null}), isFalse);
      expect(ResultadoPartida.temAdversario({'placar': [{'voce': true, 'pontos': 1}]}), isFalse);
      expect(ResultadoPartida.temAdversario(_fim(meu: 1, rival: 2)), isTrue);
      final f = _fim(meu: 5, rival: 1);
      (f['resultado'] as Map)['operacoes'] = [{'direcao': 'alta', 'pnl': 12.0}];
      expect(ResultadoPartida.de(f, {'candles': <Map>[], 'revelados': 0}).operacoes.length, 1);
    });

    test('formatação em T\$ com milhar e sinal', () {
      expect(ResultadoPartida.moeda(1250), '+T\$ 1.250,00');
      expect(ResultadoPartida.moeda(-320.5), '−T\$ 320,50');
      expect(ResultadoPartida.num1(3480.04), '+3480,0');
    });
  });

  for (final tela in const [Size(390, 844), Size(360, 640)]) {
    for (final e in [(50.0, 30.0, 'vitoria'), (40.0, 40.0, 'empate'), (30.0, 50.0, 'derrota')]) {
      testWidgets('tela ${e.$3} (${tela.width.toInt()}x${tela.height.toInt()}) mostra lucro, pontos, troféus, placar, operações e divisão sem estourar', (t) async {
        final r = ResultadoPartida.de(_fim(meu: e.$1, rival: e.$2, trofeus: {..._tr, 'resultado': e.$3}), _tela());
        await _mostra(t, r, tela);
        final rol = find.byType(Scrollable).first;
        for (final txt in ['LUCRO DA PARTIDA', '+T\$ 1.250,00', 'PONTUAÇÃO', 'TROFÉUS', '+20', 'PLACAR DO DUELO', 'OPERAÇÕES REALIZADAS', 'PETR4', 'Variação no jogo', 'SEQUÊNCIA DAS OPERAÇÕES', 'SUA DIVISÃO', 'Próxima: Prata (200 troféus)', '40 / 200', 'CONTINUAR  »']) {
          await t.scrollUntilVisible(find.text(txt), 150, scrollable: rol);
          expect(find.text(txt), findsWidgets, reason: txt);
        }
        expect(t.takeException(), isNull);
      });
    }
  }

  testWidgets('sem troféus (sala de amigos) mostra XP no lugar e esconde a divisão; "Ver todas" abre o resto', (t) async {
    final r = ResultadoPartida.de(_fim(meu: 50, rival: 30), _tela());
    await _mostra(t, r, const Size(390, 844));
    final rol = find.byType(Scrollable).first;
    await t.scrollUntilVisible(find.text('XP'), 150, scrollable: rol);
    expect(find.text('+40'), findsOneWidget);
    expect(find.text('SUA DIVISÃO'), findsNothing);
    await t.scrollUntilVisible(find.textContaining('Ver todas as operações'), 150, scrollable: rol);
    await t.ensureVisible(find.textContaining('Ver todas as operações'));   // scrollUntilVisible só garante que o item foi construído, não que está na tela
    await t.pump();
    await t.tap(find.textContaining('Ver todas as operações'));
    await t.pump();
    expect(find.text('Mostrar menos'), findsOneWidget);
    expect(t.takeException(), isNull);
  });
}
