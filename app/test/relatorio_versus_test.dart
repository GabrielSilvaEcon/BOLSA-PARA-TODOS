import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/relatorio.dart';

void main() {
  Map<String, dynamic> j(String r, bool eu, double pts) => {'rotulo': r, 'voce': eu, 'pontos': pts};

  test('vitória, derrota e empate comparam você com o adversário (pelos pontos)', () {
    final v = RelatorioTela.versus([j('Você', true, 12.5), j('Jogador 2', false, 8.0)])!;
    expect(v.$1, 'VOCÊ VENCEU!');
    expect(v.$2, contains('12,5'));
    expect(v.$2, contains('Jogador 2'));
    final d = RelatorioTela.versus([j('Jogador 2', false, 20.0), j('Você', true, 14.0)])!;
    expect(d.$1, 'JOGADOR 2 VENCEU');
    expect(d.$2, contains('Faltaram 6,0'));
    final e = RelatorioTela.versus([j('Você', true, 5.0), j('Jogador 2', false, 5.0)])!;
    expect(e.$1, 'EMPATE');
  });

  test('perder em pontos é derrota mesmo com lucro; sem adversário (treino solo) não há veredito de comparação', () {
    expect(RelatorioTela.versus([j('Você', true, -3.0), j('Jogador 2', false, 1.0)])!.$1, 'JOGADOR 2 VENCEU');
    expect(RelatorioTela.versus([j('Você', true, 7.0)]), isNull);
    expect(RelatorioTela.versus(null), isNull);
  });
}
