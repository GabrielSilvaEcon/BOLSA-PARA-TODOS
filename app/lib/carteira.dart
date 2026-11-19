import 'package:flutter/material.dart';

import 'api.dart';

/// Tela da Carteira: patrimônio, caixa livre e as posições por ativo (dados do servidor, `GET /carteira`).
class CarteiraTela extends StatefulWidget {
  const CarteiraTela({super.key, required this.api});
  final Api api;

  @override
  State<CarteiraTela> createState() => _CarteiraTelaState();
}

/// Abas da Carteira: (chave da classe no servidor, rótulo). `null` = todas.
const _abas = <(String?, String)>[
  (null, 'Todos'),
  ('acao', 'Ações'),
  ('cripto', 'Cripto'),
  ('etf', 'ETFs'),
  ('fundo', 'Fundos'),
  ('fii', 'FIIs'),
  ('rf', 'Renda fixa'),
];

class _CarteiraTelaState extends State<CarteiraTela> {
  Map<String, dynamic>? _cart;
  String? _erro;
  bool _carregando = true;
  String? _aba;

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
      final r = await widget.api.get('/carteira');
      setState(() => _cart = r);
    } catch (e) {
      setState(() => _erro = 'Não consegui carregar a sua carteira agora.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  List<Map<String, dynamic>> get _posicoes {
    final lista = ((_cart?['posicoes'] as List?) ?? const []).cast<Map<String, dynamic>>();
    if (_aba == null) return lista;
    return lista.where((p) => p['classe'] == _aba).toList();
  }

  /// 1234.5 vira "T$ 1.234,50" (dinheiro virtual do jogo). Sem valor, mostra um traço.
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
    return '${neg ? '-' : ''}T\$ $buf,$centavos';
  }

  /// 0.1234 vira "+12,34%".
  String _percentual(Object? v) {
    if (v is! num) return '—';
    final p = v * 100;
    final sinal = p > 0 ? '+' : '';
    return '$sinal${p.toStringAsFixed(2).replaceAll('.', ',')}%';
  }

  /// Quantidade: sem casas decimais se for inteira.
  String _quantidade(Object? v) {
    if (v is! num) return '—';
    final inteiro = v == v.roundToDouble();
    return inteiro ? v.toInt().toString() : v.toStringAsFixed(4).replaceAll('.', ',');
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final pat = _cart?['patrimonio'];
    final caixa = _cart?['disponivel'];
    final temRf = ((_cart?['posicoes'] as List?) ?? const []).any((p) => p is Map && p['classe'] == 'rf');
    final abas = _abas.where((a) => a.$1 != 'rf' || temRf).toList();
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
                const SizedBox(height: 16),
                Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    for (final (chave, rotulo) in abas)
                      ChoiceChip(
                        label: Text(rotulo),
                        selected: _aba == chave,
                        onSelected: (_) => setState(() => _aba = chave),
                      ),
                  ],
                ),
                const SizedBox(height: 12),
                if (_posicoes.isEmpty)
                  _cartao(
                    child: Text(
                      _aba == null
                          ? 'Você ainda não tem posições. Compre um ativo no jogo para ele aparecer aqui.'
                          : 'Nenhuma posição nesta aba.',
                      style: tema.textTheme.bodyMedium,
                    ),
                  )
                else
                  for (final p in _posicoes) ...[
                    _posicao(tema, p),
                    const SizedBox(height: 10),
                  ],
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

  Widget _posicao(ThemeData tema, Map<String, dynamic> p) {
    final pct = p['pct'] as num?;
    final cor = (pct ?? 0) >= 0 ? const Color(0xFF6BE58A) : const Color(0xFFFF6B7A);
    return _cartao(
      child: Row(
        children: [
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(p['nome']?.toString() ?? p['id']?.toString() ?? '—', style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900)),
                const SizedBox(height: 4),
                Text(
                  '${_quantidade(p['qtd'])} cotas · preço médio ${_moeda(p['pm'])}',
                  style: tema.textTheme.bodySmall,
                ),
              ],
            ),
          ),
          Column(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              Text(_moeda(p['valor']), style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900)),
              const SizedBox(height: 4),
              Text(_percentual(pct), style: tema.textTheme.bodySmall?.copyWith(color: cor, fontWeight: FontWeight.w800)),
            ],
          ),
        ],
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
