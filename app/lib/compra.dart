import 'package:flutter/material.dart';

import 'api.dart';
import 'cabecalho.dart';

/// Compra e venda na hora, ao preço atual (servidor: `POST /carteira/ordem`). Mesmas regras do jogo.
class CompraTela extends StatefulWidget {
  const CompraTela({super.key, required this.api, this.ladoInicial = 'C'});
  final Api api;
  final String ladoInicial;

  @override
  State<CompraTela> createState() => _CompraTelaState();
}

class _CompraTelaState extends State<CompraTela> {
  final _ativo = TextEditingController();
  final _qtd = TextEditingController();
  late String _lado = widget.ladoInicial;
  Map<String, dynamic>? _preco;
  String? _aviso;
  bool _ocupado = false;

  @override
  void dispose() {
    _ativo.dispose();
    _qtd.dispose();
    super.dispose();
  }

  Future<void> _verPreco() async {
    final tk = _ativo.text.trim().toUpperCase();
    if (tk.isEmpty) {
      setState(() => _aviso = 'Digite o ativo, por exemplo PETR4.');
      return;
    }
    setState(() {
      _ocupado = true;
      _aviso = null;
      _preco = null;
    });
    try {
      final r = await widget.api.get('/carteira/preco?ativo=${Uri.encodeQueryComponent(tk)}');
      if (mounted) setState(() => _preco = r);
    } catch (e) {
      if (mounted) setState(() => _aviso = e.toString());
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  Future<void> _enviar() async {
    final tk = _ativo.text.trim().toUpperCase();
    final qtd = double.tryParse(_qtd.text.trim().replaceAll(',', '.'));
    if (tk.isEmpty) {
      setState(() => _aviso = 'Digite o ativo, por exemplo PETR4.');
      return;
    }
    if (qtd == null || qtd <= 0) {
      setState(() => _aviso = 'Digite a quantidade.');
      return;
    }
    setState(() {
      _ocupado = true;
      _aviso = null;
    });
    try {
      final r = await widget.api.post('/carteira/ordem', {'ativo': tk, 'qtd': qtd, 'lado': _lado});
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(r['msg']?.toString() ?? 'Ordem executada.')));
      Navigator.of(context).pop(true);
    } catch (e) {
      if (mounted) setState(() => _aviso = e.toString());
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  /// 12.5 vira "R$ 12,50" (cotação em reais).
  String _rs(num v) => 'R\$ ${v.toStringAsFixed(2).replaceAll('.', ',')}';

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final compra = _lado == 'C';
    return Scaffold(
      appBar: AppBar(title: const Text('Comprar ativo')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            Cabecalho(api: widget.api),
            const SizedBox(height: 12),
            _cartao(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  TextField(
                    controller: _ativo,
                    textCapitalization: TextCapitalization.characters,
                    decoration: const InputDecoration(labelText: 'Ativo (ex.: PETR4)'),
                  ),
                  const SizedBox(height: 12),
                  SegmentedButton<String>(
                    segments: const [
                      ButtonSegment(value: 'C', label: Text('Comprar')),
                      ButtonSegment(value: 'V', label: Text('Vender')),
                    ],
                    selected: {_lado},
                    onSelectionChanged: (s) => setState(() => _lado = s.first),
                  ),
                  const SizedBox(height: 12),
                  TextField(
                    controller: _qtd,
                    keyboardType: const TextInputType.numberWithOptions(decimal: true),
                    decoration: const InputDecoration(labelText: 'Quantidade'),
                  ),
                  const SizedBox(height: 12),
                  OutlinedButton(
                    onPressed: _ocupado ? null : _verPreco,
                    child: const Text('Ver preço atual'),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            if (_preco != null)
              _cartao(
                child: Text(
                  '${_preco!['rotulo'] ?? _preco!['ativo']} · cotação agora: ${_rs((_preco!['px'] as num?) ?? 0)}',
                  style: tema.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w800),
                ),
              ),
            if (_aviso != null) ...[
              const SizedBox(height: 12),
              Text(_aviso!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
            ],
            const SizedBox(height: 16),
            FilledButton(
              onPressed: _ocupado ? null : _enviar,
              child: Text(compra ? 'Confirmar compra' : 'Confirmar venda'),
            ),
            const SizedBox(height: 12),
            Text(
              'A ordem é executada na hora, pela cotação do momento, como no jogo.',
              style: tema.textTheme.bodySmall,
              textAlign: TextAlign.center,
            ),
          ],
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
