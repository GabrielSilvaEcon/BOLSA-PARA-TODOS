import 'package:flutter/material.dart';

import 'api.dart';

/// Alertas da pessoa (o sino do cabeçalho). Os mesmos da tela Alertas do app antigo. Dados do servidor (`GET /alertas`).
class AlertasTela extends StatefulWidget {
  const AlertasTela({super.key, required this.api});
  final Api api;

  @override
  State<AlertasTela> createState() => _AlertasTelaState();
}

class _AlertasTelaState extends State<AlertasTela> {
  List<Map<String, dynamic>> _itens = [];
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
      final r = await widget.api.get('/alertas');
      setState(() => _itens = ((r['itens'] as List?) ?? const []).cast<Map<String, dynamic>>());
    } catch (e) {
      setState(() => _erro = 'Não consegui carregar os alertas agora.');
    } finally {
      if (mounted) setState(() => _carregando = false);
    }
  }

  Future<void> _marcarTodas() async {
    final ids = [for (final n in _itens) if (n['lida'] != true && n['id'] != null) n['id'].toString()];
    if (ids.isEmpty) return;
    try {
      await widget.api.post('/alertas/lidas', {'ids': ids});
      await _carregar();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    }
  }

  /// '2026-11-19T13:05:00+00:00' vira '19/11 10:05' (horário do aparelho).
  String _quando(Object? v) {
    final d = DateTime.tryParse(v?.toString() ?? '');
    if (d == null) return '';
    final l = d.toLocal();
    String dois(int n) => n.toString().padLeft(2, '0');
    return '${dois(l.day)}/${dois(l.month)} ${dois(l.hour)}:${dois(l.minute)}';
  }

  Color _cor(Object? importancia) {
    switch (importancia) {
      case 'alta':
        return const Color(0xFFFF6B7A);
      case 'media':
        return const Color(0xFFF5B841);
      default:
        return const Color(0xFF7A5CFF);
    }
  }

  @override
  Widget build(BuildContext context) {
    final tema = Theme.of(context);
    final temNova = _itens.any((n) => n['lida'] != true);
    return Scaffold(
      appBar: AppBar(
        title: const Text('Alertas'),
        actions: [
          if (temNova) TextButton(onPressed: _marcarTodas, child: const Text('Marcar todas como lidas')),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _carregar,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            if (_carregando && _itens.isEmpty)
              const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator()))
            else if (_erro != null && _itens.isEmpty) ...[
              Text(_erro!, textAlign: TextAlign.center, style: TextStyle(color: tema.colorScheme.error)),
              const SizedBox(height: 8),
              OutlinedButton(onPressed: _carregar, child: const Text('Tentar de novo')),
            ] else if (_itens.isEmpty)
              const Padding(
                padding: EdgeInsets.all(40),
                child: Text('Nenhum alerta por enquanto.', textAlign: TextAlign.center),
              )
            else
              for (final n in _itens) ...[
                Container(
                  padding: const EdgeInsets.all(14),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(
                      begin: Alignment.topCenter,
                      end: Alignment.bottomCenter,
                      colors: [Color(0xFF28245C), Color(0xFF16134A)],
                    ),
                    borderRadius: BorderRadius.circular(16),
                    border: Border.all(color: _cor(n['importancia']), width: n['lida'] == true ? 1 : 2),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              '${n['titulo'] ?? ''}',
                              style: tema.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w900),
                            ),
                          ),
                          if (n['lida'] != true)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                              decoration: BoxDecoration(color: const Color(0xFFF5B841), borderRadius: BorderRadius.circular(8)),
                              child: const Text('Novo', style: TextStyle(color: Color(0xFF2B1A00), fontWeight: FontWeight.w900, fontSize: 11)),
                            ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      Text('${n['texto'] ?? ''}', style: tema.textTheme.bodyMedium),
                      const SizedBox(height: 6),
                      Text(
                        [_quando(n['quando']), if ((n['ativo'] ?? '').toString().isNotEmpty) n['ativo'].toString()].join(' · '),
                        style: tema.textTheme.bodySmall,
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
              ],
          ],
        ),
      ),
    );
  }
}
