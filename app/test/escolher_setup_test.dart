import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/api.dart';
import 'package:tickerhunters/setups.dart';

Map<String, dynamic> _s(String id, String nome, String rar, String tipo, String dir, String reg, {bool eq = false}) => {
      'id': id, 'nome': nome, 'raridade': rar, 'tipo': tipo, 'direcao': dir, 'regiao': reg, 'subtitulo': 'Sub $nome', 'stop_texto': 'Stop $nome', 'alvo_texto': 'Alvo $nome',
      'caracteristicas': ['Condição A', 'Condição B', 'Condição C'], 'cores': {'principal': '#2EE59D', 'brilho': '#FFD76A'}, 'assets': {'carta': null}, 'equipado': eq, 'fonte_regra': '',
    };

Map<String, dynamic> _dados() => {
      'limite': 2,
      'itens': [
        _s('martelo', 'Martelo', 'comum', 'candle', 'compra', 'Suporte / Zona de alta', eq: true),
        _s('engolfo_alta', 'Engolfo de Alta', 'rara', 'candle', 'compra', 'Suporte / Zona de alta'),
        _s('estrela_cadente', 'Estrela Cadente', 'comum', 'candle', 'venda', 'Resistência / Zona de baixa'),
        _s('turtle_trading', 'Turtle Trading', 'epica', 'estrategia', 'ambos', 'Qualquer região'),
        _s('larry_williams', 'Larry Williams', 'epica', 'estrategia', 'ambos', 'Qualquer região'),
        _s('mark_minervini', 'Mark Minervini', 'epica', 'estrategia', 'compra', 'Qualquer região'),
        _s('setup_classico', 'Setup Clássico', 'epica', 'estrategia', 'compra', 'Qualquer região'),
      ],
    };

Future<void> _abre(WidgetTester t, Size tela) async {
  t.view.physicalSize = tela;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.resetPhysicalSize);
  final api = Api(tokenAtual: () => null);
  await t.pumpWidget(MaterialApp(home: Scaffold(body: Builder(builder: (ctx) => TextButton(onPressed: () => escolherSetups(ctx, api, inicial: _dados()), child: const Text('abrir'))))));
  await t.tap(find.text('abrir'));
  await t.pumpAndSettle();
}

Finder _carta(String nome) => find.ancestor(of: find.text(nome).first, matching: find.byType(GestureDetector)).first;

void main() {
  for (final tela in [const Size(390, 800), const Size(900, 700)]) {
    testWidgets('pop-up Escolher setup desenha sem estourar o layout em ${tela.width.toInt()}x${tela.height.toInt()}', (t) async {
      await _abre(t, tela);
      expect(t.takeException(), isNull);
      expect(find.text('ESCOLHER SETUP'), findsOneWidget);
      expect(find.text('Confirmar setup'), findsOneWidget);
      expect(find.textContaining('MARTELO'), findsWidgets);
    });
  }

  testWidgets('filtros: Venda mostra a Estrela e as estratégias de compra ou venda; Padrões de candle mostra só as 3 cartas', (t) async {
    await _abre(t, const Size(390, 800));
    await t.ensureVisible(find.text('Venda').first);
    await t.tap(find.text('Venda').first);
    await t.pumpAndSettle();
    expect(find.text('ESTRELA CADENTE'), findsWidgets);
    expect(find.text('TURTLE TRADING'), findsWidgets);
    expect(find.text('MARTELO'), findsNothing);
    await t.ensureVisible(find.text('Padrões de candle'));
    await t.tap(find.text('Padrões de candle'));
    await t.pumpAndSettle();
    expect(find.text('TURTLE TRADING'), findsNothing);
    expect(find.text('ENGOLFO DE ALTA'), findsWidgets);
  });

  testWidgets('escolha: o martelo já vem marcado (1/2); marcar mais um fecha em 2/2 e o terceiro é recusado com aviso', (t) async {
    await _abre(t, const Size(390, 800));
    expect(find.textContaining('Ativos: 1/2'), findsOneWidget);
    await t.ensureVisible(find.text('ENGOLFO DE ALTA').first);
    await t.tap(_carta('ENGOLFO DE ALTA'));
    await t.pumpAndSettle();
    expect(find.textContaining('Ativos: 2/2'), findsOneWidget);
    await t.ensureVisible(find.text('ESTRELA CADENTE').first);
    await t.tap(_carta('ESTRELA CADENTE'));
    await t.pumpAndSettle();
    expect(find.textContaining('Ativos: 2/2'), findsOneWidget);
    expect(find.textContaining('até 2 setups por partida'), findsWidgets);
  });

  testWidgets('sem o painel de detalhe embaixo: tocar só marca a carta (nada de Stop/Alvo/Condições abaixo)', (t) async {
    await _abre(t, const Size(390, 800));
    await t.ensureVisible(find.text('ENGOLFO DE ALTA').first);
    await t.tap(_carta('ENGOLFO DE ALTA'));
    await t.pumpAndSettle();
    expect(find.textContaining('CONDIÇÕES DO SETUP'), findsNothing);
    expect(find.text('STOP'), findsNothing);
    expect(find.textContaining('Ativos: 2/2'), findsOneWidget);
  });

  testWidgets('segurar a carta por 2 segundos abre o verso virado e NÃO marca nem desmarca o setup', (t) async {
    await _abre(t, const Size(390, 800));
    expect(find.textContaining('Ativos: 1/2'), findsOneWidget);
    await t.ensureVisible(find.text('ENGOLFO DE ALTA').first);
    final g = await t.startGesture(t.getCenter(_carta('ENGOLFO DE ALTA')));
    await t.pump(const Duration(milliseconds: 50));
    await t.pump(const Duration(milliseconds: 1000));
    await t.pump(const Duration(milliseconds: 1100));
    await g.up();
    await t.pumpAndSettle();
    expect(find.textContaining('Toque na carta para voltar à frente'), findsOneWidget);       // a carta abriu virada (o verso)
    expect(find.textContaining('Ativos: 1/2'), findsOneWidget);                                // o toque ao soltar não marcou a carta
    await t.tap(find.text('Fechar'));
    await t.pumpAndSettle();
    expect(find.textContaining('Toque na carta para voltar à frente'), findsNothing);
    expect(t.takeException(), isNull);
  });
}
