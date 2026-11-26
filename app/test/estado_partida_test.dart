import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/estado_partida.dart';

Map<String, dynamic> candle(int i) => {'t': 'D1 10:${i.toString().padLeft(2, '0')}', 'o': 10.0 + i, 'h': 10.5 + i, 'l': 9.5 + i, 'c': 10.2 + i, 'v': 100};

Map<String, dynamic> completa(int n, {String e = 'A', int seg = 50, String fk = '1-replay'}) => {
      'estado': 'jogo',
      'id': 'p1',
      'fase': 'replay',
      'e': e,
      'tela': {'candles': [for (var i = 0; i < n; i++) candle(i)], 'fase_key': fk, 'seg': seg, 'prox_ms': 1000, 'ref': 11.0},
    };

void main() {
  test('sem base, a consulta é a completa; depois da primeira resposta completa, pede só o incremental', () {
    final inc = EstadoIncremental();
    expect(inc.consulta('/trade/salas/p1'), '/trade/salas/p1');
    expect(inc.aplicar(completa(5)), isNotNull);
    final q = inc.consulta('/trade/salas/p1');
    expect(q, startsWith('/trade/salas/p1?e=A&n=5&u='));
    expect(q, contains('fk=1-replay'));
  });

  test('sem mudança: reaproveita o estado e atualiza só seg e prox_ms', () {
    final inc = EstadoIncremental()..aplicar(completa(5));
    final r = inc.aplicar({'estado': 'jogo', 'id': 'p1', 'fase': 'replay', 'e': 'A', 'sem_mudanca': true, 'vol': {'seg': 49, 'prox_ms': 400}})!;
    final t = r['tela'] as Map;
    expect((t['candles'] as List).length, 5);
    expect(t['seg'], 49);
    expect(t['prox_ms'], 400);
    expect(r.containsKey('sem_mudanca'), isFalse);
  });

  test('cauda de candles é juntada e o resultado é igual ao estado completo', () {
    final inc = EstadoIncremental()..aplicar(completa(5));
    final novo = completa(7, e: 'B');
    final tela = Map<String, dynamic>.from(novo['tela'] as Map)..remove('candles');
    tela
      ..['candles_desde'] = 4
      ..['candles_cauda'] = (novo['tela'] as Map)['candles'].sublist(4)
      ..['candles_total'] = 7;
    final r = inc.aplicar({...novo, 'tela': tela})!;
    expect((r['tela'] as Map)['candles'], (novo['tela'] as Map)['candles']);
    expect(inc.consulta('/x'), contains('e=B&n=7'));
  });

  test('inconsistências descartam a resposta e a próxima consulta volta a ser completa', () {
    final inc = EstadoIncremental()..aplicar(completa(5));
    final tela = {'candles_desde': 9, 'candles_cauda': [candle(9)], 'candles_total': 10, 'fase_key': '1-replay'};
    expect(inc.aplicar({'estado': 'jogo', 'e': 'B', 'tela': tela}), isNull); // cauda que não encaixa (faltam candles)
    expect(inc.consulta('/x'), '/x');
    final inc2 = EstadoIncremental();
    expect(inc2.aplicar({'estado': 'jogo', 'e': 'A', 'sem_mudanca': true, 'vol': {}}), isNull); // "sem mudança" sem ter base
    final inc3 = EstadoIncremental()..aplicar(completa(5));
    expect(inc3.aplicar({'estado': 'jogo', 'e': 'Z', 'sem_mudanca': true, 'vol': {}}), isNull); // versão diferente da que o app tem
    expect(inc3.consulta('/x'), '/x');
  });

  test('rede de segurança: a cada 20 respostas incrementais seguidas, pede o estado completo', () {
    final inc = EstadoIncremental()..aplicar(completa(5));
    for (var i = 0; i < EstadoIncremental.maxIncrementais; i++) {
      expect(inc.consulta('/x'), contains('?e=A'));
      inc.aplicar({'estado': 'jogo', 'e': 'A', 'sem_mudanca': true, 'vol': {'seg': 40 - i, 'prox_ms': 1}});
    }
    expect(inc.consulta('/x'), '/x'); // chegou ao limite
    inc.aplicar(completa(5)); // a completa zera a contagem
    expect(inc.consulta('/x'), contains('?e=A'));
  });

  test('fim da partida e respostas sem candles não viram base incremental', () {
    final inc = EstadoIncremental()..aplicar(completa(5));
    inc.aplicar({'estado': 'jogo', 'id': 'p1', 'fase': 'fim', 'tela': {'candles': [candle(1), candle(2)], 'fase_key': 'x'}, 'fim': {}}); // sem `e`
    expect(inc.consulta('/x'), '/x');
    expect(inc.temBase, isFalse);
  });
}
