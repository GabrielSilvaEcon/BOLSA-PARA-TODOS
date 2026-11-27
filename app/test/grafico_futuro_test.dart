import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/grafico/grafico.dart';
import 'package:tickerhunters/grafico/modelo.dart';

List<Vela> _velas(int n) => [
      for (var i = 0; i < n; i++)
        Vela.de({'o': 30.0 + (i % 9) * 0.2, 'h': 31.0 + (i % 9) * 0.2, 'l': 29.5 + (i % 9) * 0.2, 'c': 30.4 + (i % 7) * 0.15, 'v': 1000, 't': '2026-01-05T10:00'}),
    ];

Future<dynamic> _monta(WidgetTester t, List<Desenho> desenhos, {Ferramenta? ferramenta, int n = 120, bool leitura = false}) async {
  t.view.physicalSize = const Size(400, 320);
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  await t.pumpWidget(MaterialApp(
    home: Scaffold(
      body: SizedBox(
        width: 400,
        height: 320,
        child: GraficoNativo(velas: _velas(n), desenhos: desenhos, ferramenta: ferramenta, somenteLeitura: leitura, aoMudar: ({bool usouFerramenta = false}) {}, pedirTexto: () async => null),
      ),
    ),
  ));
  await t.pump(const Duration(milliseconds: 1300));
  return t.state(find.byType(GraficoNativo));
}

void main() {
  testWidgets('ao abrir, o último candle não fica colado no canto: sobra espaço para o futuro', (t) async {
    final g = await _monta(t, []);
    final pw = g.larguraUtilPx as double;
    expect(g.margemDireitaPx as double, greaterThan(pw * 0.2));
    expect(t.takeException(), isNull);
  });

  testWidgets('arrastar até o fim para a direita para no espaço do futuro (antes parava com o candle no canto); para trás continua livre', (t) async {
    final g = await _monta(t, []);
    final pw = g.larguraUtilPx as double;
    await t.drag(find.byType(GraficoNativo), const Offset(-3000, 0));          // dedo para a esquerda: vai para os candles atuais
    await t.pump(const Duration(milliseconds: 600));
    final fim = g.margemDireitaPx as double;
    expect(fim, greaterThan(pw * 0.2), reason: 'o último candle não pode encostar no eixo');
    expect(fim, lessThan(pw * 0.34), reason: 'e também não pode fugir da tela');
    await t.drag(find.byType(GraficoNativo), const Offset(400, 0));            // dedo para a direita: candles antigos
    await t.pump(const Duration(milliseconds: 600));
    expect(g.margemDireitaPx as double, lessThan(fim - 100), reason: 'voltar no tempo leva o último candle para fora, à direita');
    expect(t.takeException(), isNull);
  });

  testWidgets('dá para desenhar no espaço do futuro: a tendência ganha índices à frente do último candle', (t) async {
    final ds = <Desenho>[];
    final g = await _monta(t, ds, ferramenta: Ferramenta.tendencia);
    final pw = g.larguraUtilPx as double;
    await t.tapAt(Offset(pw - 70, 150));
    await t.pump();
    await t.tapAt(Offset(pw - 12, 90));
    await t.pump();
    expect(ds, hasLength(1));
    expect(ds.single.i2, greaterThan(119), reason: 'o 2º ponto está no futuro');
    expect(ds.single.i1! < ds.single.i2!, isTrue);
  });

  testWidgets('no relatório (só leitura) não aparece a faixa do futuro, mas o espaço à direita continua', (t) async {
    final g = await _monta(t, [], leitura: true);
    expect(g.margemDireitaPx as double, greaterThan((g.larguraUtilPx as double) * 0.2));
    expect(t.takeException(), isNull);
  });
}
