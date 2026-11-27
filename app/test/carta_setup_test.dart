import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/carta_setup.dart';

Map<String, dynamic> _setup(String id, {String rar = 'rara', String tipo = 'candle', String dir = 'compra', bool equipado = false}) => {
      'id': id, 'nome': 'Engolfo de Alta', 'subtitulo': 'Possível reversão de alta', 'raridade': rar, 'tipo': tipo, 'direcao': dir, 'equipado': equipado,
      'cores': {'principal': '#FF4D6D', 'brilho': '#FFC2CC'}, 'indicadores': ['Corpos dos dois últimos candles', 'Região de suporte marcada por você'], 'resumo': 'Resumo do padrão.',
      'estatisticas': {'ativacoes': 6, 'entradas': 4, 'recusadas': 1, 'expiradas': 1, 'com_resultado': 3, 'vitorias': 2, 'taxa': 67, 'retorno_medio': 1.25},
      'carta': {
        'gatilho': 'Candle de alta que engole o de baixa, em um suporte marcado por você.', 'stop': 'Abaixo da menor mínima dos dois candles', 'alvo': '2 vezes o risco (2:1)', 'alvo_curto': 'Alvo 2:1',
        'melhor': 'Funciona melhor em suportes com confirmação de volume ou tendência.', 'autor': 'Padrão de candle clássico', 'regiao': 'Suporte', 'saida': 'Stop ou alvo',
      },
    };

/// Todo o texto que aparece na árvore de widgets (inclui Text.rich).
String _tudo(WidgetTester t) {
  final b = StringBuffer();
  for (final w in t.widgetList<Text>(find.byType(Text))) {
    b.writeln(w.data ?? w.textSpan?.toPlainText() ?? '');
  }
  return b.toString();
}

Future<void> _mostra(WidgetTester t, Widget w) async {
  t.view.physicalSize = const Size(900, 1400);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  await t.pumpWidget(MaterialApp(home: Scaffold(body: Center(child: w))));
  await t.pump(const Duration(milliseconds: 300));
}

void main() {
  const ids = ['engolfo_alta', 'estrela_cadente', 'martelo', 'larry_williams', 'mark_minervini', 'setup_classico', 'turtle_trading'];

  testWidgets('frente (300 px): nome, raridade, tipo, alvo e direção vêm do cadastro', (t) async {
    await _mostra(t, CartaSetup(setup: _setup('engolfo_alta'), largura: 300));
    final txt = _tudo(t);
    for (final s in ['ENGOLFO DE ALTA', 'SETUP · RARA', 'Possível reversão de alta', 'Candle', 'Alvo 2:1', '▲ Compra']) {
      expect(txt, contains(s), reason: s);
    }
    expect(t.takeException(), isNull);
  });

  testWidgets('direção e tipo mudam o rótulo: venda, ambos e método', (t) async {
    await _mostra(t, CartaSetup(setup: _setup('turtle_trading', tipo: 'estrategia', dir: 'ambos'), largura: 300));
    expect(_tudo(t), allOf(contains('Método'), contains('▲▼ Ambos')));
    await _mostra(t, CartaSetup(setup: _setup('estrela_cadente', dir: 'venda'), largura: 300));
    expect(_tudo(t), contains('▼ Venda'));
  });

  testWidgets('verso (300 px): gatilho, stop, alvo, quando funciona melhor, indicador, região, saída e os números do jogador', (t) async {
    await _mostra(t, CartaSetup(setup: _setup('engolfo_alta'), largura: 300, verso: true));
    final txt = _tudo(t);
    for (final s in ['GATILHO', 'STOP', 'ALVO', 'QUANDO FUNCIONA MELHOR', 'Região: Suporte · Saída: Stop ou alvo', 'Padrão de candle clássico', 'INDICADORES', 'Corpos dos dois últimos candles', 'ATIVAÇÕES', 'ENTRADAS', 'ACERTO · MÉDIA']) {
      expect(txt, contains(s), reason: s);
    }
    expect(find.text('6', findRichText: true), findsOneWidget);
    expect(find.text('4', findRichText: true), findsOneWidget);
    expect(find.text('67% · +1,3%', findRichText: true), findsOneWidget);          // retorno médio com uma casa, vírgula e sinal
  });

  testWidgets('sem ativações ainda: zeros e traço, sem inventar acerto', (t) async {
    final s = _setup('martelo')..['estatisticas'] = {'ativacoes': 0, 'entradas': 0, 'taxa': null, 'retorno_medio': null};
    await _mostra(t, CartaSetup(setup: s, largura: 300, verso: true));
    expect(find.text('0', findRichText: true), findsNWidgets(2));
    expect(find.text('—', findRichText: true), findsOneWidget);
    final sem = _setup('martelo')..remove('estatisticas');                          // servidor antigo: sem o campo
    await _mostra(t, CartaSetup(setup: sem, largura: 300, verso: true));
    expect(find.text('—', findRichText: true), findsOneWidget);
    expect(t.takeException(), isNull);
  });

  testWidgets('carta pequena (150 px) mostra só o desenho e o nome', (t) async {
    await _mostra(t, CartaSetup(setup: _setup('engolfo_alta'), largura: 150));
    final txt = _tudo(t);
    expect(txt, contains('ENGOLFO DE ALTA'));
    expect(txt, isNot(contains('SETUP · RARA')));
    await _mostra(t, CartaSetup(setup: _setup('engolfo_alta'), largura: 150, verso: true));
    expect(_tudo(t), isNot(contains('GATILHO')));
  });

  testWidgets('sem os textos curtos do servidor a carta não quebra (usa o resumo como gatilho)', (t) async {
    final s = _setup('martelo')..remove('carta');
    await _mostra(t, CartaSetup(setup: s, largura: 300, verso: true));
    expect(_tudo(t), contains('Resumo do padrão.'));
    expect(t.takeException(), isNull);
  });

  testWidgets('os 7 setups em 4 raridades, frente e verso, em 3 larguras, sem estourar', (t) async {
    for (final id in ids) {
      for (final rar in ['comum', 'rara', 'epica', 'lendaria']) {
        for (final w in [150.0, 230.0, 340.0]) {
          await _mostra(t, Column(mainAxisSize: MainAxisSize.min, children: [CartaSetup(setup: _setup(id, rar: rar), largura: w), CartaSetup(setup: _setup(id, rar: rar), largura: w, verso: true)]));
        }
      }
    }
    expect(t.takeException(), isNull);
  });

  testWidgets('tocar na carta vira para o verso e de volta', (t) async {
    await _mostra(t, CartaGirando(setup: _setup('engolfo_alta'), largura: 300));
    expect(_tudo(t), isNot(contains('QUANDO FUNCIONA MELHOR')));
    await t.tap(find.byType(CartaSetup));
    await t.pump(const Duration(milliseconds: 50));      // o relógio da animação só começa no primeiro quadro depois do toque
    await t.pump(const Duration(milliseconds: 700));
    expect(_tudo(t), contains('QUANDO FUNCIONA MELHOR'));
    await t.tap(find.byType(CartaSetup));
    await t.pump(const Duration(milliseconds: 50));      // o relógio da animação só começa no primeiro quadro depois do toque
    await t.pump(const Duration(milliseconds: 700));
    expect(_tudo(t), isNot(contains('QUANDO FUNCIONA MELHOR')));
    expect(t.takeException(), isNull);
  });

  group('desempenho', () {
    Future<void> grade(WidgetTester t, {bool verso = false}) => _mostra(
        t,
        SingleChildScrollView(child: Wrap(children: [for (final id in ids) CartaSetup(setup: _setup(id), largura: 168, verso: verso), for (final id in ids) CartaSetup(setup: _setup(id, rar: 'epica'), largura: 168, verso: verso)])));

    testWidgets('reconstruir as mesmas cartas não mede o texto de novo (tamanho de letra em memória)', (t) async {
      await grade(t);
      final depoisDaPrimeira = TextoAjustado.calculos;
      await grade(t);                                   // outra árvore com as mesmas cartas
      await t.pumpWidget(const SizedBox());
      await grade(t);
      expect(TextoAjustado.calculos, depoisDaPrimeira, reason: 'a segunda montagem deveria usar a memória');
    });

    testWidgets('a virada não remonta nem mede nada a cada quadro: só a rotação muda', (t) async {
      await _mostra(t, CartaGirando(setup: _setup('engolfo_alta'), largura: 300));
      await t.tap(find.byType(CartaSetup));
      await t.pump(const Duration(milliseconds: 50));
      await t.pump(const Duration(milliseconds: 700));               // verso montado pela primeira vez
      final aposPrimeira = TextoAjustado.calculos;
      for (var i = 0; i < 4; i++) {
        await t.tap(find.byType(CartaSetup));
        await t.pump(const Duration(milliseconds: 50));
        for (var q = 0; q < 12; q++) {
          await t.pump(const Duration(milliseconds: 50));          // 12 quadros de animação por virada
        }
      }
      expect(TextoAjustado.calculos, aposPrimeira, reason: 'quadros da animação não devem refazer medições de texto');
    });

    testWidgets('medida (só informativa, no teste e não no aparelho): montar 14 cartas', (t) async {
      final sw = Stopwatch()..start();
      await grade(t);
      final primeira = sw.elapsedMilliseconds;
      sw.reset();
      await t.pumpWidget(const SizedBox());
      await grade(t);
      final segunda = sw.elapsedMilliseconds;
      // ignore: avoid_print
      print('MEDIDA 14 cartas: 1ª montagem ${primeira} ms, 2ª montagem ${segunda} ms');
      expect(segunda, lessThanOrEqualTo(primeira + 50));
    });
  });
}
