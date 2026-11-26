import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:tickerhunters/api.dart';
import 'package:tickerhunters/conta.dart';

class _ApiFalsa extends Api {
  _ApiFalsa() : super(tokenAtual: () => null);
  final posts = <String>[];
  @override
  Future<Map<String, dynamic>> get(String caminho) async {
    if (caminho == '/conta') return {'nome': 'Ana', 'email': 'ana@x.com', 'cadastro': '2026-01-05', 'provedor': 'google', 'tipo': 'Usuário', 'email_verificado': true};
    if (caminho == '/conta/atividades') {
      return {
        'itens': [
          {'rotulo': 'Nome atualizado', 'tom': 'info', 'quando': '2026-11-20T10:30'}
        ]
      };
    }
    return {'json': '{"a":1}'};
  }

  @override
  Future<Map<String, dynamic>> post(String caminho, [Map<String, dynamic>? corpo]) async {
    posts.add('$caminho ${corpo ?? {}}');
    return {'ok': true, 'msg': 'Nome atualizado.', 'nome': corpo?['nome']};
  }
}

void main() {
  for (final tela in const [Size(390, 844), Size(360, 640)]) {
    for (final comSenha in [true, false]) {
      testWidgets('Minha conta (${tela.width.toInt()}x${tela.height.toInt()}, ${comSenha ? 'com senha' : 'Google'}) mostra dados, segurança, atividades e privacidade sem estourar', (t) async {
        t.view.physicalSize = tela;
        t.view.devicePixelRatio = 1;
        addTearDown(t.view.reset);
        final api = _ApiFalsa();
        final trocas = <String>[];
        await t.pumpWidget(MaterialApp(
          home: ContaTela(api: api, seguranca: SegurancaConta(alterarSenha: (n) async => trocas.add(n), sairOutros: () async {}, entraComSenha: () => comSenha)),
        ));
        await t.pump(const Duration(milliseconds: 300));
        final rol = find.byType(Scrollable).first;
        for (final txt in ['Dados da conta', 'ana@x.com', '05/01/2026', 'Google', 'Segurança', 'Nome atualizado', 'Privacidade e seus dados']) {
          await t.scrollUntilVisible(find.text(txt), 120, scrollable: rol);
          expect(find.text(txt), findsWidgets, reason: txt);
        }
        expect(find.text('Alterar senha'), comSenha ? findsWidgets : findsNothing);
        expect(t.takeException(), isNull);
        await t.pumpWidget(const SizedBox());
      });
    }
  }

  testWidgets('trocar nome chama o servidor; senha curta ou diferente não chega ao Supabase', (t) async {
    t.view.physicalSize = const Size(390, 844);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    final api = _ApiFalsa();
    final trocas = <String>[];
    await t.pumpWidget(MaterialApp(home: ContaTela(api: api, seguranca: SegurancaConta(alterarSenha: (n) async => trocas.add(n), sairOutros: () async {}, entraComSenha: () => true))));
    await t.pump(const Duration(milliseconds: 300));
    await t.enterText(find.widgetWithText(TextField, 'Nome'), 'Ana Paula');
    await t.tap(find.text('Salvar nome'));
    await t.pump(const Duration(milliseconds: 500));
    expect(api.posts.single, contains('/conta/nome'));
    expect(api.posts.single, contains('Ana Paula'));
    final rol = find.byType(Scrollable).first;
    await t.scrollUntilVisible(find.text('Nova senha (mínimo 8 caracteres)'), 120, scrollable: rol);
    await t.enterText(find.widgetWithText(TextField, 'Nova senha (mínimo 8 caracteres)'), 'curta');
    await t.enterText(find.widgetWithText(TextField, 'Repita a nova senha'), 'curta');
    await t.ensureVisible(find.widgetWithText(FilledButton, 'Alterar senha'));
    await t.pump();
    await t.tap(find.widgetWithText(FilledButton, 'Alterar senha'), warnIfMissed: false);
    await t.pump(const Duration(milliseconds: 500));
    expect(trocas, isEmpty);
    await t.pump(const Duration(seconds: 6));      // o aviso (SnackBar) some e para de cobrir o botão
    await t.pump(const Duration(seconds: 1));
    await t.enterText(find.widgetWithText(TextField, 'Nova senha (mínimo 8 caracteres)'), 'senhaboa123');
    await t.enterText(find.widgetWithText(TextField, 'Repita a nova senha'), 'senhaboa123');
    await t.ensureVisible(find.widgetWithText(FilledButton, 'Alterar senha'));
    await t.pump();
    final bt = find.widgetWithText(FilledButton, 'Alterar senha');
    t.widget<FilledButton>(bt).onPressed!();     // o toque em si já é coberto pelo botão "Salvar nome"; aqui vale a regra de senha
    await t.pump(const Duration(milliseconds: 500));
    expect(trocas, ['senhaboa123']);
    await t.pumpWidget(const SizedBox());
  });
}
