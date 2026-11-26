import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/ajuda.dart';
import 'package:tickerhunters/api.dart';

class _ApiFalsa extends Api {
  _ApiFalsa({this.novaRota = true}) : super(tokenAtual: () => null);
  final bool novaRota;
  @override
  Future<Map<String, dynamic>> get(String caminho) async {
    if (caminho == '/ajuda/glossario/completo') {
      if (!novaRota) throw ApiErro('rota nova indisponível');
      return {
        'termos': [
          {
            'termo': 'Preço sobre Lucro (P/L)', 'definicao': 'Relação entre o preço da ação e o lucro.', 'uso': 'Ação a R\$ 30 com lucro de R\$ 3: P/L = 10.', 'formula': 'P/L = Preço ÷ LPA',
            'central': {
              'pt': 'Preço sobre Lucro', 'en': 'Price-to-Earnings (P/E)', 'alias': ['P/E'], 'classes': ['Ações brasileiras', 'Ações dos EUA'],
              'niveis': {
                'iniciante': [{'r': 'O que é', 't': 'Quantos anos de lucro para devolver o preço.'}],
                'intermediario': [{'r': 'Como ler', 't': 'Compare com o setor.'}],
                'avancado': [{'r': 'Metodologia', 't': 'Usa lucro contábil de 12 meses.'}],
              },
            },
          },
          {'termo': 'Aderência', 'definicao': 'Quanto o gráfico segue o padrão.', 'uso': 'Usada nos setups.', 'formula': ''},
        ]
      };
    }
    if (caminho == '/ajuda/glossario') {
      return {
        'termos': [
          {'termo': 'Aderência', 'oque': 'Quanto o gráfico segue o padrão.', 'pra_que': 'Usada nos setups.'}
        ]
      };
    }
    return {};
  }
}

Future<void> _abre(WidgetTester t, Api api, Size tela) async {
  t.view.physicalSize = tela;
  t.view.devicePixelRatio = 1;
  addTearDown(t.view.reset);
  await t.pumpWidget(MaterialApp(home: AjudaTela(api: api)));
  await t.pump(const Duration(milliseconds: 400));
}

void main() {
  for (final tela in const [Size(390, 844), Size(360, 640)]) {
    testWidgets('glossário completo (${tela.width.toInt()}x${tela.height.toInt()}): termo central abre com os três níveis e a busca acha pelo nome em inglês', (t) async {
      await _abre(t, _ApiFalsa(), tela);
      final rol = find.byType(Scrollable).first;
      await t.scrollUntilVisible(find.text('Preço sobre Lucro (P/L)'), 200, scrollable: rol);
      await t.tap(find.text('Preço sobre Lucro (P/L)'));
      await t.pump(const Duration(milliseconds: 400));
      await t.scrollUntilVisible(find.text('Quantos anos de lucro para devolver o preço.'), 100, scrollable: rol);
      expect(find.text('Quantos anos de lucro para devolver o preço.'), findsOneWidget);       // nível Iniciante por padrão
      await t.tap(find.text('Avançado'));
      await t.pump(const Duration(milliseconds: 300));
      await t.scrollUntilVisible(find.text('Usa lucro contábil de 12 meses.'), 100, scrollable: rol);
      expect(find.text('Usa lucro contábil de 12 meses.'), findsOneWidget);
      await t.scrollUntilVisible(find.text('P/E'), 100, scrollable: rol);
      expect(find.text('Ações brasileiras · Ações dos EUA'), findsOneWidget);
      expect(find.text('P/E'), findsOneWidget);                                                // "Também chamado de"
      await t.drag(rol, const Offset(0, 5000));                                                // volta ao topo, onde fica a busca
      await t.pump(const Duration(milliseconds: 300));
      await t.enterText(find.byType(TextField).first, 'price-to-earnings');
      await t.pump(const Duration(milliseconds: 300));
      expect(find.text('Preço sobre Lucro (P/L)'), findsOneWidget);
      expect(find.text('Aderência'), findsNothing);
      expect(t.takeException(), isNull);
    });
  }

  testWidgets('se a rota nova não existir, usa a antiga e mostra "Para que serve"', (t) async {
    await _abre(t, _ApiFalsa(novaRota: false), const Size(390, 844));
    final rol = find.byType(Scrollable).first;
    await t.scrollUntilVisible(find.text('Aderência'), 200, scrollable: rol);
    await t.tap(find.text('Aderência'));
    await t.pump(const Duration(milliseconds: 300));
    expect(find.text('Usada nos setups.'), findsOneWidget);
    expect(t.takeException(), isNull);
  });
}
