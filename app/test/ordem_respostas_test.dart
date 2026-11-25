import 'package:tickerhunters/ordem_respostas.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  test('resposta que chega na ordem vale', () {
    final o = OrdemRespostas();
    final a = o.novo(), b = o.novo();
    expect(o.aceitar(a), isTrue);
    expect(o.aceitar(b), isTrue);
  });

  test('resposta atrasada de um pedido mais velho é descartada', () {
    // O caso do bug: o relógio dispara um GET, o jogador confirma a estratégia logo depois,
    // o POST é atendido primeiro (fase=replay) e só então chega o GET antigo (fase=analise).
    final o = OrdemRespostas();
    final consulta = o.novo();      // GET do relógio, retrato de antes da confirmação
    final confirma = o.novo();      // POST da estratégia, retrato de depois
    expect(o.aceitar(confirma), isTrue, reason: 'o retrato mais novo deve valer');
    expect(o.aceitar(consulta), isFalse, reason: 'o retrato velho não pode voltar a valer');
  });

  test('depois de descartar uma atrasada, as próximas continuam valendo', () {
    final o = OrdemRespostas();
    final velho = o.novo(), novo = o.novo();
    o.aceitar(novo);
    o.aceitar(velho);
    expect(o.aceitar(o.novo()), isTrue);
  });
}
