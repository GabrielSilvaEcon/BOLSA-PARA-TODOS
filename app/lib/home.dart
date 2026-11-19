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

  @override
  void initState() {
    super.initState();
    _conferirServidor();
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
