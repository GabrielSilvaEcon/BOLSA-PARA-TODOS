import 'package:flutter/material.dart';

import 'api.dart';

/// Cabeçalho do jogo, igual em todas as telas: nível (com barra de XP), Ticker Coins e posição no ranking.
/// Dados do servidor (`GET /eu`). Sem dados, mostra traços e não derruba a tela.
class Cabecalho extends StatefulWidget {
  const Cabecalho({super.key, required this.api});
  final Api api;

  @override
  State<Cabecalho> createState() => _CabecalhoState();
}

class _CabecalhoState extends State<Cabecalho> {
  Map<String, dynamic>? _eu;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/eu');
      if (mounted) setState(() => _eu = r);
    } catch (_) {
      // sem dados: o cabeçalho continua com traços
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final nivel = _eu?['nivel'] as Map?;
    final moedas = _eu?['moedas'];
    final pct = (nivel?['pct'] as num?)?.toDouble() ?? 0;
    final rk = (_eu?['ranking'] as Map?) ?? {};
    final pos = rk['pos'];
    final legenda = _eu == null
        ? 'ranking'
        : (pos != null || rk['participa'] == true)
            ? (rk['total'] == null ? 'ranking' : 'de ${rk['total']}')
            : 'Entre na competição';
    return Row(
      children: [
        Expanded(
          flex: 5,
          child: _cartao(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  nivel == null ? 'Nível —' : 'Nível ${nivel['nivel']}',
                  style: tema.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w900),
                ),
                const SizedBox(height: 4),
                ClipRRect(
                  borderRadius: BorderRadius.circular(4),
                  child: LinearProgressIndicator(
                    value: pct.clamp(0, 1).toDouble(),
                    minHeight: 6,
                    color: Colors.lightBlueAccent,
                    backgroundColor: Colors.white12,
                  ),
                ),
                const SizedBox(height: 2),
                Text(_eu?['xp'] == null ? '' : '${_eu!['xp']} XP', style: tema.textTheme.labelSmall),
              ],
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          flex: 3,
          child: _cartao(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.toll, color: Color(0xFFFFD76A), size: 22),
                Text(
                  moedas == null ? '—' : '$moedas',
                  style: tema.textTheme.titleMedium?.copyWith(color: const Color(0xFFFFD76A), fontWeight: FontWeight.w900),
                ),
                const Text('TC', style: TextStyle(fontSize: 11)),
              ],
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          flex: 3,
          child: _cartao(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.emoji_events, color: Color(0xFFFFD76A), size: 22),
                Text(
                  pos == null ? '—' : '#$pos',
                  style: tema.textTheme.titleMedium?.copyWith(color: const Color(0xFFFFD76A), fontWeight: FontWeight.w900),
                ),
                Text(legenda, style: const TextStyle(fontSize: 11), textAlign: TextAlign.center),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _cartao({required Widget child}) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [Color(0xFF28245C), Color(0xFF16134A)],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF7A5CFF), width: 1.5),
      ),
      child: child,
    );
  }
}
