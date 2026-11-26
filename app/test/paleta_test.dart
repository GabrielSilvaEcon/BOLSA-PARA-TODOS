import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/grafico/modelo.dart';

void main() {
  test('a estratégia não oferece mais Alvo nem Zonas (stop e alvo vêm do setup)', () {
    expect(Ferramenta.paleta, isNot(contains(Ferramenta.alvo)));
    expect(Ferramenta.paleta, isNot(contains(Ferramenta.zonaAlta)));
    expect(Ferramenta.paleta, isNot(contains(Ferramenta.zonaBaixa)));
    expect(Ferramenta.paleta, containsAll([Ferramenta.suporte, Ferramenta.resistencia, Ferramenta.rompimento, Ferramenta.tendencia, Ferramenta.nota, Ferramenta.apagar]));
  });

  test('os valores antigos continuam existindo para o relatório mostrar partidas passadas', () {
    expect(Ferramenta.values, containsAll([Ferramenta.alvo, Ferramenta.zonaAlta, Ferramenta.zonaBaixa]));
  });
}
