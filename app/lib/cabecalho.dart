import 'dart:convert';

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
  bool _falhou = false;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/eu');
      if (mounted) {
        setState(() {
          _eu = r;
          _falhou = false;
        });
      }
    } catch (_) {
      if (mounted) setState(() => _falhou = true);
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
          child: GestureDetector(
            onTap: _falhou ? _carregar : null,
            child: _cartao(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _avatar(_eu?['avatar_img']),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        nivel == null ? (_falhou ? 'Toque para atualizar' : 'Nível —') : 'Nível ${nivel['nivel']}',
                        style: tema.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w900),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 6),
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

  /// Avatar equipado (arquivo em assets/avatares). Sem ele, ou sem arquivo, mostra o mascote.
  Widget _avatar(Object? img) {
    final texto = img is String && img.isNotEmpty ? img : null;
    final mascote = Image.asset('assets/home/mascote_principal.webp', fit: BoxFit.cover);
    return Container(
      width: 40,
      height: 40,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: const Color(0xFF1A1650),
        border: Border.all(color: const Color(0xFF6BE58A), width: 2),
      ),
      child: ClipOval(
        child: texto == null
            ? mascote
            : texto.startsWith('data:')
                ? Image.memory(
                    base64Decode(texto.substring(texto.indexOf(',') + 1)),
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => mascote,
                  )
                : Image.asset(
                    'assets/$texto',
                    fit: BoxFit.cover,
                    errorBuilder: (_, __, ___) => mascote,
                  ),
      ),
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
