import 'package:flutter/material.dart';

import 'api.dart';

/// Tela da Carteira: patrimônio e caixa livre de quem joga (dados do servidor, `GET /eu`).
/// As posições por ativo entram na próxima etapa.
class CarteiraTela extends StatefulWidget {
  const CarteiraTela({super.key, required this.api});
  final Api api;

  @override
  State<CarteiraTela> createState() => _CarteiraTelaState();
}

class _CarteiraTelaState extends State<CarteiraTela> {
  Map<String, dynamic>? _cart;
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
      setState(() => _cart = (r['carteira'] as Map?)?.cast<String, dynamic>());
    } catch (e) {
      setState(() => _erro = 'Não consegui carregar a sua carteira agora.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  /// 1234.5 vira "R$ 1.234,50". Sem valor, mostra um traço.
  String _moeda(Object? v) {
    if (v is! num) return '—';
    final neg = v < 0;
    final cents = (v.abs() * 100).round();
    final inteiro = (cents ~/ 100).toString();
    final centavos = (cents % 100).toString().padLeft(2, '0');
    final buf = StringBuffer();
    for (var i = 0; i < inteiro.length; i++) {
      if (i > 0 && (inteiro.length - i) % 3 == 0) buf.write('.');
      buf.write(inteiro[i]);
    }
    return '${neg ? '-' : ''}R\$ $buf,$centavos';
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final pat = _cart?['pat'];
    final caixa = _cart?['caixa'];
    return Scaffold(
      appBar: AppBar(title: const Text('Carteira')),
      body: SafeArea(
        child: RefreshIndicator(
          onRefresh: _carregar,
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_carregando && _cart == null)
                const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
              else if (_erro != null && _cart == null) ...[
                Text(_erro!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
                const SizedBox(height: 8),
                OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
              ] else ...[
                _cartao(
                  child: Row(
                    children: [
                      Image.asset('assets/carteira/carteira.webp', width: 56, height: 56),
                      const SizedBox(width: 12),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('Patrimônio', style: tema.textTheme.labelLarge),
                            const SizedBox(height: 4),
                            Text(
                              _moeda(pat),
                              style: tema.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w900, color: const Color(0xFFFFD76A)),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                _cartao(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text('Caixa livre', style: tema.textTheme.labelLarge),
                      const SizedBox(height: 4),
                      Text(_moeda(caixa), style: tema.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w900)),
                    ],
                  ),
                ),
                const SizedBox(height: 12),
                _cartao(
                  child: Text(
                    'Suas posições por ativo aparecem aqui na próxima etapa.',
                    style: tema.textTheme.bodyMedium,
                  ),
                ),
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

  Widget _cartao({required Widget child}) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(14),
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
