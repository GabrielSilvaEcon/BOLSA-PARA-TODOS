import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'config.dart';

/// Entrar, criar conta e recuperar a senha, pelo Supabase Auth (e-mail e senha).
class LoginTela extends StatefulWidget {
  const LoginTela({super.key});

  @override
  State<LoginTela> createState() => _LoginTelaState();
}

class _LoginTelaState extends State<LoginTela> {
  final _email = TextEditingController();
  final _senha = TextEditingController();
  final _nome = TextEditingController();
  bool _criando = false;
  bool _ocupado = false;
  String? _aviso;

  @override
  void dispose() {
    _email.dispose();
    _senha.dispose();
    _nome.dispose();
    super.dispose();
  }

  Future<void> _enviar() async {
    final email = _email.text.trim();
    final senha = _senha.text;
    if (!email.contains('@') || senha.length < 6) {
      setState(() => _aviso = 'Informe um e-mail válido e uma senha de pelo menos 6 caracteres.');
      return;
    }
    setState(() {
      _ocupado = true;
      _aviso = null;
    });
    try {
      final auth = Supabase.instance.client.auth;
      if (_criando) {
        await auth.signUp(email: email, password: senha, data: {'full_name': _nome.text.trim()}, emailRedirectTo: linkDeTeste);
        setState(() => _aviso = 'Enviamos um e-mail para confirmar sua conta. Abra o link e depois entre.');
      } else {
        await auth.signInWithPassword(email: email, password: senha);
        // a tela principal troca sozinha quando o login acontece (ver main.dart)
      }
    } on AuthException catch (e) {
      setState(() => _aviso = _traduzir(e.message));
    } catch (_) {
      setState(() => _aviso = 'Não consegui entrar agora. Tente de novo em instantes.');
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _esqueci() async {
    final email = _email.text.trim();
    if (!email.contains('@')) {
      setState(() => _aviso = 'Digite seu e-mail acima, depois toque em "Esqueci a senha".');
      return;
    }
    try {
      await Supabase.instance.client.auth.resetPasswordForEmail(email, redirectTo: linkDeTeste);
      setState(() => _aviso = 'Se o e-mail estiver cadastrado, você recebe o link para trocar a senha.');
    } catch (_) {
      setState(() => _aviso = 'Não consegui enviar agora. Tente de novo em instantes.');
    }
  }

  String _traduzir(String msg) {
    final m = msg.toLowerCase();
    if (m.contains('invalid login')) return 'E-mail ou senha incorretos.';
    if (m.contains('not confirmed')) return 'Confirme seu e-mail antes de entrar. Abra o link que enviamos.';
    if (m.contains('already registered') || m.contains('already been registered')) return 'Este e-mail já tem conta. Toque em "Já tenho conta".';
    return msg;
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: [Color(0xFF3B2A9E), Color(0xFF1A1258), Color(0xFF0B0828)],
          ),
        ),
        child: SafeArea(
          child: Center(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: ConstrainedBox(
                constraints: const BoxConstraints(maxWidth: 420),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Image.asset('assets/mascote.webp', height: 160, fit: BoxFit.contain),
                    const SizedBox(height: 8),
                    Text('TickerHunters', textAlign: TextAlign.center, style: tema.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w900, color: Colors.white)),
                    const SizedBox(height: 4),
                    Text(_criando ? 'Crie sua conta de jogador' : 'Entre para jogar', textAlign: TextAlign.center, style: tema.textTheme.bodyMedium?.copyWith(color: const Color(0xFFCFC8F5))),
                    const SizedBox(height: 28),
                  if (_criando) ...[
                    TextField(controller: _nome, decoration: const InputDecoration(labelText: 'Nome de jogador'), textInputAction: TextInputAction.next),
                    const SizedBox(height: 12),
                  ],
                  TextField(
                    controller: _email,
                    keyboardType: TextInputType.emailAddress,
                    autofillHints: const [AutofillHints.email],
                    decoration: const InputDecoration(labelText: 'E-mail'),
                    textInputAction: TextInputAction.next,
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _senha,
                    obscureText: true,
                    autofillHints: const [AutofillHints.password],
                    decoration: const InputDecoration(labelText: 'Senha (mínimo 6 caracteres)'),
                    onSubmitted: (_) => _enviar(),
                  ),
                  const SizedBox(height: 8),
                  if (_aviso != null)
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      child: Text(_aviso!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
                    ),
                  const SizedBox(height: 12),
                  FilledButton(
                    onPressed: _ocupado ? null : _enviar,
                    child: Padding(
                      padding: const EdgeInsets.symmetric(vertical: 10),
                      child: Text(_ocupado ? 'Aguarde…' : (_criando ? 'Criar conta' : 'Entrar')),
                    ),
                  ),
                  const SizedBox(height: 12),
                  TextButton(
                    onPressed: _ocupado ? null : () => setState(() {
                      _criando = !_criando;
                      _aviso = null;
                    }),
                    child: Text(_criando ? 'Já tenho conta' : 'Quero criar uma conta'),
                  ),
                  if (!_criando)
                    TextButton(onPressed: _ocupado ? null : _esqueci, child: const Text('Esqueci a senha')),
                  const SizedBox(height: 16),
                  Text(
                    'Jogo educativo. Sem recomendação de compra ou venda.',
                    style: tema.textTheme.bodySmall,
                    textAlign: TextAlign.center,
                  ),
                ],
              ),
            ),
          ),
        ),
        ),
      ),
    );
  }
}
