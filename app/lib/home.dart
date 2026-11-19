import 'package:flutter/material.dart';

import 'api.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

/// Home no estilo de jogo (primeira versão). Mostra a conexão com o servidor; o HUD completo vem na próxima parte.
class HomeTela extends StatefulWidget {
  const HomeTela({super.key, required this.api});
  final Api api;

  @override
  State<HomeTela> createState() => _HomeTelaState();
}

class _HomeTelaState extends State<HomeTela> {
  String _estado = 'Conectando ao servidor…';
  bool _ok = false;
  String? _nome;
  Map<String, dynamic>? _placar;
  String? _erroEu;

  @override
  void initState() {
    super.initState();
    _conferirServidor();
    _carregarEu();
  }

  /// Seus dados vindos do servidor (mesmo login do Supabase). Mostra o erro se o servidor não reconhecer a sessão.
  Future<void> _carregarEu() async {
    try {
      final r = await widget.api.get('/eu');
      final perfil = (r['perfil'] as Map?) ?? {};
      final conta = (r['conta'] as Map?) ?? {};
      setState(() {
        _nome = (perfil['nome'] as String?)?.trim().isNotEmpty == true ? perfil['nome'] as String : (conta['nome'] as String?) ?? conta['email'] as String?;
        _placar = r['placar'] as Map<String, dynamic>?;
        _erroEu = null;
      });
    } catch (e) {
      setState(() => _erroEu = 'Não consegui carregar seus dados ($e)');
    }
  }

  Future<void> _conferirServidor() async {
    try {
      final r = await widget.api.get('/saude');
      setState(() {
        _ok = r['ok'] == true && r['banco'] == true;
        _estado = _ok ? 'Servidor pronto' : 'Servidor no ar, mas o banco não respondeu';
      });
    } catch (e) {
      setState(() {
        _ok = false;
        _estado = 'Sem conexão com o servidor ($e)';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Text('TickerHunters', style: tema.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 8),
                Text('Aprenda, analise e suba no ranking', style: tema.textTheme.bodyMedium),
                const SizedBox(height: 32),
                Icon(_ok ? Icons.check_circle : Icons.sync, size: 48, color: _ok ? Colors.greenAccent : Colors.amberAccent),
                const SizedBox(height: 12),
                Text(_estado, textAlign: TextAlign.center),
                const SizedBox(height: 20),
                if (_nome != null)
                  Text('Olá, $_nome', style: tema.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w800)),
                if (_placar != null) ...[
                  const SizedBox(height: 8),
                  Text(
                    'Partidas: ${_placar!['partidas'] ?? 0}  ·  Vitórias: ${_placar!['vitorias'] ?? 0}',
                    textAlign: TextAlign.center,
                  ),
                ],
                if (_erroEu != null) ...[
                  const SizedBox(height: 8),
                  Text(_erroEu!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
                  TextButton(onPressed: _carregarEu, child: const Text('Tentar de novo')),
                ],
                const SizedBox(height: 24),
                TextButton(onPressed: () => Supabase.instance.client.auth.signOut(), child: const Text('Sair')),
                if (!_ok)
                  OutlinedButton(onPressed: _conferirServidor, child: const Text('Tentar de novo')),
                const SizedBox(height: 32),
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
    );
  }
}
