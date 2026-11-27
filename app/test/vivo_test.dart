import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/api.dart';
import 'package:tickerhunters/vivo.dart';

class _ApiFalsa extends Api {
  _ApiFalsa() : super(tokenAtual: () => null);
  final gets = <String>[];
  @override
  Future<Map<String, dynamic>> get(String caminho) async {
    gets.add(caminho);
    if (caminho == '/vivo/moedas') {
      return {
        'moedas': [
          {'id': 'BTC', 'nome': 'Bitcoin'},
          {'id': 'ETH', 'nome': 'Ethereum'}
        ],
        'duracoes': [
          {'id': '1m', 'candles': 15, 'segundos': 900},
          {'id': '5m', 'candles': 12, 'segundos': 3600}
        ]
      };
    }
    if (caminho == '/vivo/previsoes') {
      return {
        'itens': [
          {'id': 'a', 'moeda': 'BTC', 'tf': '5m', 'direcao': 'alta', 'estado': 'aberta', 'horizonte': 12, 'faltam': 5},
          {
            'id': 'b',
            'moeda': 'ETH',
            'tf': '1m',
            'direcao': 'baixa',
            'estado': 'conferida',
            'resultado': {'nota': 82.0, 'real': 'baixa', 'mov_pct': -0.42, 'direcao_ok': true}
          },
          {'id': 'c', 'moeda': 'BTC', 'tf': '1m', 'direcao': null, 'estado': 'expirada'}
        ]
      };
    }
    throw ApiErro('sem rota $caminho');
  }
}

void main() {
  for (final tela in const [Size(390, 844), Size(360, 640)]) {
    testWidgets('Ao vivo (${tela.width.toInt()}x${tela.height.toInt()}) mostra moedas, duração e as leituras sem estourar', (t) async {
      t.view.physicalSize = tela;
      t.view.devicePixelRatio = 1;
      addTearDown(t.view.reset);
      final api = _ApiFalsa();
      await t.pumpWidget(MaterialApp(home: VivoTela(api: api)));
      await t.pump(const Duration(milliseconds: 300));
      expect(find.text('Bitcoin'), findsNothing); // as moedas são chips com o código
      expect(find.text('BTC'), findsOneWidget);
      expect(find.text('ETH'), findsOneWidget);
      expect(find.textContaining('A conferência sai em ~60 min'), findsOneWidget); // 5m (padrão): 12 candles = 60 min
      await t.tap(find.text('1m'));
      await t.pump();
      expect(find.textContaining('A conferência sai em ~15 min'), findsOneWidget);
      final rol = find.byType(Scrollable).first;
      for (final txt in ["LER O GRÁFICO AO VIVO", "TRADE AO VIVO · 30 min · candles de 1 min", "TRADE AO VIVO · 60 min · candles de 5 min", 'Minhas leituras', 'Bitcoin · 5m · Subir', 'Aguardando 5 candles fecharem', '82', 'O preço caiu (-0.42%). Você acertou a direção.', 'Encerrada sem nota']) {
        await t.scrollUntilVisible(find.textContaining(txt), 120, scrollable: rol);
        expect(find.textContaining(txt), findsWidgets, reason: txt);
      }
      expect(t.takeException(), isNull);
      await t.pumpWidget(const SizedBox()); // desmonta (cancela o relógio)
    });
  }
}
