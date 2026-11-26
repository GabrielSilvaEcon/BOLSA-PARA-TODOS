import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/diag/diag.dart';
import 'package:tickerhunters/diag/diag_args.dart';

void main() {
  test('args do teste automático: 356 candles e evento de setup só quando pedido', () {
    final sem = diagArgs(evento: false);
    final com = diagArgs(evento: true, n: 2);
    expect((sem['candles'] as List).length, 356);
    expect((sem['setup'] as Map)['evento'], isNull);
    final ev = (com['setup'] as Map)['evento'] as Map;
    expect(ev['sinal'], 'p:1:355:2');
    expect(ev['anim_ms'], 4000);
    expect(ev['destaque_ms'], 5000);
    expect(() => jsonEncode(com), returnsNormally);
  });

  test('relatório e texto saem sem dados medidos (sem inventar números)', () {
    final r = Diag.relatorio();
    expect(r['limitacoes'], isNotEmpty);
    final t = Diag.texto();
    expect(t, contains('LIMITAÇÕES'));
    expect(t, contains('RELATÓRIO DE DIAGNÓSTICO'));
  });

  test('mensagem do coletor registra marcas e tolera lixo', () {
    final id = Diag.novaMesa('teste');
    Diag.mesaMsg(id, jsonEncode({'k': 'pronto', 'ep': 1234}));
    expect(Diag.mesaMarca(id, 'mesa_primeiro_desenho'), 1234);
    Diag.mesaMsg(id, 'isto não é json');
    Diag.mesaMsg(999, jsonEncode({'k': 'pronto', 'ep': 1}));
  });
}
