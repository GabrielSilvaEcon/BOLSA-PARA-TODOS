import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/perfil_jogador.dart';

Future<void> _mostra(WidgetTester t, Map<String, dynamic> p, Size tela) async {
  t.view.physicalSize = tela;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  await t.pumpWidget(MaterialApp(home: Scaffold(body: PerfilJogadorConteudo(p: p))));
  await t.pump();
}

void main() {
  final completo = <String, dynamic>{
    'usuario': 'bia_h', 'nome': 'Bia', 'titulo': 'Caçadora', 'bio': 'Gosto de swing trade', 'desde': '2026-01', 'nivel': 7, 'xp': 840, 'xp_pct': 0.4, 'xp_max': false,
    'estat': {'partidas': 10, 'vitorias': 6, 'empates': 1, 'derrotas': 3, 'taxa': 60.0},
    'jogos': {
      'trade': {'pontos': 12.5, 'partidas': 8, 'vitorias': 3, 'posicao': 4},
      'ticker': {'vitorias': 5, 'empates': 1, 'derrotas': 2, 'posicao': null},
    },
    'conquistas': {'ok': 3, 'total': 20},
    'medalhas': [
      {'emblema': '🏆', 'nome': 'Primeira vitória'},
    ],
    'historico': [
      {'em': '2026-11-20T10:30', 'jogo': 'trade', 'pts': 7.5, 'pos': 1, 'n': 2},
      {'em': '2026-11-19T09:00', 'jogo': 'ticker', 'r': 'd'},
    ],
    'restrito': false,
  };

  for (final tela in const [Size(390, 844), Size(360, 640)]) {
    testWidgets('perfil completo mostra as seções do Streamlit (${tela.width.toInt()}x${tela.height.toInt()}), sem estourar', (t) async {
      await _mostra(t, completo, tela);
      for (final txt in ['Bia', '@bia_h · Caçadora', 'No TickerHunters desde 01/2026', '⭐ 840 XP', 'Nível 7', '📊 Desempenho', '60%', '🎮 Jogos e rankings', '#4', '🏅 Conquistas e medalhas', '3 de 20', '🏆 Primeira vitória']) {
        await t.scrollUntilVisible(find.text(txt), 120, scrollable: find.byType(Scrollable).first);
        expect(find.text(txt), findsOneWidget, reason: txt);
      }
      await t.scrollUntilVisible(find.text('🕑 Últimas partidas'), 200, scrollable: find.byType(Scrollable).first);
      expect(find.text('Derrota'), findsOneWidget);
      expect(t.takeException(), isNull);
    });
  }

  testWidgets('perfil só para amigos mostra o cadeado e nada de desempenho', (t) async {
    await _mostra(t, {'usuario': 'x', 'nome': 'X', 'restrito': true, 'avatar_img': null}, const Size(390, 844));
    expect(find.textContaining('visível só para amigos'), findsOneWidget);
    expect(find.text('📊 Desempenho'), findsNothing);
    expect(t.takeException(), isNull);
  });

  testWidgets('vitrine: divisão de cada jogo e os setups equipados aparecem; sem vitrine (privacidade) a seção some', (t) async {
    final com = {
      ...completo,
      'vitrine': {
        'divisao': {
          'trade': {'id': 'bronze', 'nome': 'Bronze', 'cor': '#CD7F32', 'nivel': 0, 'trofeus': 40},
          'ticker': {'id': 'prata', 'nome': 'Prata', 'cor': '#C0C0C0', 'nivel': 1, 'trofeus': 230},
        },
        'setups': [
          {'id': 'martelo', 'nome': 'Martelo', 'raridade': 'comum', 'subtitulo': 'x', 'tipo': 'candle', 'direcao': 'compra', 'cores': {'principal': '#2EE59D', 'brilho': '#FFD76A'}, 'carta': {}},
        ],
      },
    };
    await _mostra(t, com, const Size(390, 844));
    for (final txt in ['🏆 Vitrine', 'Bronze · 40', 'Prata · 230']) {
      expect(find.text(txt), findsOneWidget, reason: txt);
    }
    expect(find.text('Trade Battle'), findsWidgets);      // também aparece no cartão de "Jogos e rankings"
    expect(find.text('Ticker Battle'), findsWidgets);
    expect(find.text('MARTELO', findRichText: true), findsOneWidget);
    expect(t.takeException(), isNull);
    await _mostra(t, completo, const Size(390, 844));
    expect(find.text('🏆 Vitrine'), findsNothing);
    await _mostra(t, {...completo, 'vitrine': {'divisao': <String, dynamic>{}, 'setups': <Map>[]}}, const Size(360, 640));
    expect(t.takeException(), isNull);
  });
}
