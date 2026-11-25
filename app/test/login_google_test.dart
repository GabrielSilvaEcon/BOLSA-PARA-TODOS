import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/login.dart';

void main() {
  testWidgets('a tela de entrada tem o botão Entrar com o Google (quem entrava assim no app antigo)', (t) async {
    await t.pumpWidget(const MaterialApp(home: LoginTela()));
    expect(find.byKey(const Key('entrar_google')), findsOneWidget);
    expect(find.text('Entrar com o Google'), findsOneWidget);
    expect(find.text('Entrar'), findsOneWidget); // o e-mail e senha continuam
  });
}
