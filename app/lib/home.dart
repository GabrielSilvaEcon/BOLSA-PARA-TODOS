import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';

import 'api.dart';

/// Home no estilo de jogo: cabeçalho (nível, Ticker Coins e ranking), banner do Hunter Pass e os três acessos.
/// Os dados vêm do servidor (`GET /eu`). Ranking e telas de destino entram nas próximas partes.
class HomeTela extends StatefulWidget {
  const HomeTela({super.key, required this.api});
  final Api api;

  @override
  State<HomeTela> createState() => _HomeTelaState();
}

class _HomeTelaState extends State<HomeTela> {
  Map<String, dynamic>? _eu;
  String? _erro;
  bool _carregando = true;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() {
      _carregando = true;
      _erro = null;
    });
    try {
      final r = await widget.api.get('/eu');
      setState(() => _eu = r);
    } catch (e) {
      setState(() => _erro = 'Não consegui carregar a sua Home agora.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  String get _nome {
    final perfil = (_eu?['perfil'] as Map?) ?? {};
    final conta = (_eu?['conta'] as Map?) ?? {};
    final n = (perfil['nome'] as String?)?.trim();
    if (n != null && n.isNotEmpty) return n;
    return (conta['nome'] as String?) ?? (conta['email'] as String?) ?? 'Jogador';
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    return Scaffold(
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _carregar,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              _cabecalho(tema),
              const SizedBox(height: 14),
              if (_carregando && _eu == null)
                const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
              else if (_erro != null && _eu == null)
                _erroTela(tema)
              else ...[
                _bannerPasse(tema),
                const SizedBox(height: 14),
                _acessos(tema),
              ],
              const SizedBox(height: 24),
              Text(
                'Jogo educativo. Sem recomendação de compra ou venda.',
                style: tema.textTheme.bodySmall,
                textAlign: TextAlign.center,
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// Linha de cima: nível (com barra de XP), Ticker Coins e ranking.
  Widget _cabecalho(ThemeData tema) {
    final nivel = _eu?['nivel'] as Map?;
    final moedas = _eu?['moedas'];
    final pct = (nivel?['pct'] as num?)?.toDouble() ?? 0;
    return Row(
      children: [
        Expanded(
          flex: 5,
          child: _cartao(
            tema,
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
                  child: LinearProgressIndicator(value: pct.clamp(0, 1), minHeight: 6, color: Colors.lightBlueAccent, backgroundColor: Colors.white12),
                ),
                const SizedBox(height: 2),
                Text(
                  _eu?['xp'] == null ? '' : '${_eu!['xp']} XP',
                  style: tema.textTheme.labelSmall,
                ),
              ],
            ),
          ),
        ),
        const SizedBox(width: 8),
        Expanded(
          flex: 3,
          child: _cartao(
            tema,
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
            tema,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Icon(Icons.emoji_events, color: Color(0xFFFFD76A), size: 22),
                Text('—', style: tema.textTheme.titleMedium?.copyWith(color: const Color(0xFFFFD76A), fontWeight: FontWeight.w900)),
                const Text('ranking', style: TextStyle(fontSize: 11)),
              ],
            ),
          ),
        ),
      ],
    );
  }

  /// Banner: nome do jogador e o Hunter Pass da temporada com a barra de progresso.
  Widget _bannerPasse(ThemeData tema) {
    final passe = _eu?['passe'] as Map?;
    final feitos = passe?['feitos'] ?? 0;
    final total = passe?['total'] ?? 0;
    final pct = (passe?['pct'] as num?)?.toDouble() ?? 0;
    return _cartao(
      tema,
      destaque: true,
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Olá, $_nome', style: tema.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 4),
                Text('TICKER HUNTERS', style: tema.textTheme.labelMedium?.copyWith(color: const Color(0xFFCFC8F5), letterSpacing: 1.2)),
              ],
            ),
          ),
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              gradient: const LinearGradient(colors: [Color(0xFFFFD76A), Color(0xFFC98A1A)]),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                const Text('HUNTER PASS', style: TextStyle(color: Color(0xFF2B1A00), fontWeight: FontWeight.w900, fontSize: 11)),
                Text('$feitos/$total', style: const TextStyle(color: Color(0xFF2B1A00), fontWeight: FontWeight.w900)),
                SizedBox(
                  width: 90,
                  child: ClipRRect(
                    borderRadius: BorderRadius.circular(4),
                    child: LinearProgressIndicator(value: pct.clamp(0, 1), minHeight: 5, color: const Color(0xFF2B1A00), backgroundColor: Colors.white30),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// Os três acessos da Home. Os destinos chegam nas próximas partes.
  Widget _acessos(ThemeData tema) {
    return Row(
      children: [
        Expanded(child: _acesso(tema, 'Carteira', Icons.account_balance_wallet, const Color(0xFF3D8BFF))),
        const SizedBox(width: 8),
        Expanded(flex: 2, child: _acesso(tema, 'Jogar agora', Icons.play_arrow_rounded, const Color(0xFFB6FF3D))),
        const SizedBox(width: 8),
        Expanded(child: _acesso(tema, 'Mercado', Icons.show_chart, const Color(0xFFFF3D7A))),
      ],
    );
  }

  Widget _acesso(ThemeData tema, String rotulo, IconData icone, Color cor) {
    return InkWell(
      borderRadius: BorderRadius.circular(16),
      onTap: () => ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$rotulo: em breve'))),
      child: Container(
        height: 110,
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: cor.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(16),
          border: Border.all(color: cor, width: 1.5),
        ),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(icone, color: cor, size: 34),
            const SizedBox(height: 6),
            Text(rotulo, style: tema.textTheme.labelLarge?.copyWith(fontWeight: FontWeight.w900), textAlign: TextAlign.center),
          ],
        ),
      ),
    );
  }

  Widget _erroTela(ThemeData tema) {
    return Column(
      children: [
        Text(_erro!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
        const SizedBox(height: 8),
        OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
        TextButton(onPressed: () => Supabase.instance.client.auth.signOut(), child: const Text('Sair')),
      ],
    );
  }

  Widget _cartao(ThemeData tema, {required Widget child, bool destaque = false}) {
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: destaque ? const [Color(0xFF3B2A9E), Color(0xFF1A1258)] : const [Color(0xFF28245C), Color(0xFF16134A)],
        ),
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFF7A5CFF), width: 1.5),
      ),
      child: child,
    );
  }
}
