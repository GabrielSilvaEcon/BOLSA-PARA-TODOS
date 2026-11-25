import 'package:flutter/material.dart';

import 'api.dart';
import 'cartas.dart' show coresRaridade, rotulosRaridade;

/// Setups colecionáveis. Tudo vem do servidor (`GET /setups`): a tela só mostra o que a pessoa conquistou e deixa equipar um.
/// A arte de cada setup mora em assets/setups/<id>/ (o servidor já manda o caminho só quando o arquivo existe); sem arte, entra o
/// espaço provisório, claramente marcado, e nunca uma arte inventada.

Color _corDe(Map s) => (coresRaridade[s['raridade']] ?? coresRaridade['comum']!).$1;

/// Carta do setup: a arte enviada, ou o espaço provisório (marcado) quando ela ainda não existe ou não carrega.
class SetupCarta extends StatelessWidget {
  const SetupCarta({super.key, required this.setup, this.largura = 150});
  final Map<String, dynamic> setup;
  final double largura;

  @override
  Widget build(BuildContext context) {
    final cor = _corDe(setup);
    final arte = (setup['assets'] as Map?)?['carta'] as String?;
    final borda = BorderRadius.circular(largura * 0.08);
    Widget provisoria() => Container(
          decoration: BoxDecoration(
            borderRadius: borda,
            gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [cor.withValues(alpha: .55), const Color(0xFF0C192E)]),
          ),
          padding: const EdgeInsets.all(10),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.gps_fixed, size: largura * 0.32, color: Colors.white70),
              const SizedBox(height: 8),
              Text('${setup['nome']}', textAlign: TextAlign.center, style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: largura * 0.1)),
              const SizedBox(height: 6),
              Text('ARTE PROVISÓRIA', style: TextStyle(color: Colors.white54, fontWeight: FontWeight.w700, fontSize: largura * 0.062, letterSpacing: .6)),
            ],
          ),
        );
    return Container(
      width: largura,
      height: largura * 1.4,
      decoration: BoxDecoration(borderRadius: borda, border: Border.all(color: cor, width: 2), boxShadow: [BoxShadow(color: cor.withValues(alpha: .45), blurRadius: 14)]),
      child: ClipRRect(
        borderRadius: borda,
        child: arte == null ? provisoria() : Image.asset(arte, fit: BoxFit.cover, errorBuilder: (_, __, ___) => provisoria()),
      ),
    );
  }
}

/// Aviso de setup novo vindo de um baú.
Future<void> revelarSetup(BuildContext context, Map<String, dynamic> setup, {VoidCallback? abrirMeusSetups}) {
  final cor = _corDe(setup);
  return showDialog<void>(
    context: context,
    barrierColor: const Color(0xE6030A1C),
    builder: (ctx) => Dialog(
      backgroundColor: const Color(0xFF10274A),
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20), side: BorderSide(color: cor, width: 1.5)),
      child: Padding(
        padding: const EdgeInsets.all(18),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text('NOVO SETUP CONQUISTADO!', style: TextStyle(color: Color(0xFFFFD76A), fontWeight: FontWeight.w900, fontSize: 16)),
            const SizedBox(height: 12),
            SetupCarta(setup: setup, largura: 170),
            const SizedBox(height: 10),
            Text('${setup['nome']}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 18)),
            Text(rotulosRaridade[setup['raridade']] ?? '', style: TextStyle(color: cor, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            const Text('Ele já está na sua coleção. Equipe em Meus Setups para usar nas partidas X1.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 12.5)),
            const SizedBox(height: 14),
            Row(children: [
              Expanded(child: OutlinedButton(onPressed: () => Navigator.of(ctx).pop(), child: const Text('OK'))),
              if (abrirMeusSetups != null) ...[
                const SizedBox(width: 8),
                Expanded(
                    child: FilledButton(
                        onPressed: () {
                          Navigator.of(ctx).pop();
                          abrirMeusSetups();
                        },
                        child: const Text('Meus Setups'))),
              ],
            ]),
          ],
        ),
      ),
    ),
  );
}

/// "Meus Setups": o que a pessoa conquistou, as características de cada um e qual está equipado (vale sozinho nas partidas X1).
class SetupsTela extends StatefulWidget {
  const SetupsTela({super.key, required this.api});
  final Api api;

  @override
  State<SetupsTela> createState() => _SetupsTelaState();
}

class _SetupsTelaState extends State<SetupsTela> {
  Map<String, dynamic>? _d;
  String? _erro;
  String? _salvando;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/setups');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = 'Não foi possível carregar seus setups agora.');
    }
  }

  Future<void> _equipar(String id) async {
    if (_salvando != null) return;
    setState(() => _salvando = id);
    try {
      await widget.api.post('/setups/equipar', {'id': id});
      await _carregar();
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Não foi possível equipar agora. Tente de novo.')));
    } finally {
      if (mounted) setState(() => _salvando = null);
    }
  }

  void _detalhe(Map<String, dynamic> s) {
    showModalBottomSheet<void>(
      context: context,
      isScrollControlled: true,
      backgroundColor: const Color(0xFF10274A),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
      builder: (ctx) => StatefulBuilder(
        builder: (ctx, set) {
          final atual = (_d?['itens'] as List? ?? []).cast<Map>().firstWhere((x) => x['id'] == s['id'], orElse: () => s);
          final equipado = atual['equipado'] == true;
          return DraggableScrollableSheet(
            expand: false,
            initialChildSize: .9,
            maxChildSize: .95,
            builder: (_, rolagem) => ListView(
              controller: rolagem,
              padding: const EdgeInsets.fromLTRB(18, 18, 18, 28),
              children: [
                Center(child: SetupCarta(setup: s, largura: 190)),
                const SizedBox(height: 12),
                Text('${s['nome']}', textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 20)),
                Text(rotulosRaridade[s['raridade']] ?? '', textAlign: TextAlign.center, style: TextStyle(color: _corDe(s), fontWeight: FontWeight.w800)),
                if ('${s['resumo']}'.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 10), child: Text('${s['resumo']}', style: const TextStyle(color: Colors.white70, height: 1.35))),
                _bloco('Como entra', [if ('${(s['regra'] as Map)['compra']}'.isNotEmpty) 'Compra: ${(s['regra'] as Map)['compra']}', if ('${(s['regra'] as Map)['venda']}'.isNotEmpty) 'Venda: ${(s['regra'] as Map)['venda']}']),
                _bloco('Características', (s['caracteristicas'] as List).map((e) => '$e').toList()),
                _bloco('Indicadores', (s['indicadores'] as List).map((e) => '$e').toList()),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: equipado || _salvando != null
                      ? null
                      : () async {
                          await _equipar('${s['id']}');
                          set(() {});
                        },
                  child: Text(equipado ? 'EQUIPADO' : 'EQUIPAR'),
                ),
                const SizedBox(height: 6),
                const Text('O setup equipado é usado automaticamente nas partidas X1. Você não precisa escolher antes de cada partida.',
                    textAlign: TextAlign.center, style: TextStyle(color: Colors.white54, fontSize: 11.5)),
              ],
            ),
          );
        },
      ),
    );
  }

  Widget _bloco(String titulo, List<String> linhas) {
    if (linhas.isEmpty) return const SizedBox.shrink();
    return Padding(
      padding: const EdgeInsets.only(top: 14),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Text(titulo.toUpperCase(), style: const TextStyle(color: Color(0xFFFFD76A), fontWeight: FontWeight.w900, fontSize: 12, letterSpacing: .8)),
        const SizedBox(height: 4),
        for (final l in linhas) Padding(padding: const EdgeInsets.only(top: 3), child: Text('• $l', style: const TextStyle(color: Colors.white, height: 1.3))),
      ]),
    );
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    final itens = (d?['itens'] as List? ?? []).cast<Map>().map((m) => m.cast<String, dynamic>()).toList();
    final total = ((d?['total'] as num?) ?? 0).toInt();
    return Scaffold(
      backgroundColor: const Color(0xFF0C192E),
      appBar: AppBar(backgroundColor: const Color(0xFF0C192E), title: const Text('Meus Setups')),
      body: _erro != null
          ? Center(child: Text(_erro!, style: const TextStyle(color: Colors.white70)))
          : d == null
              ? const Center(child: CircularProgressIndicator())
              : ListView(
                  padding: const EdgeInsets.all(16),
                  children: [
                    Text('${itens.length} de $total setups conquistados', style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    const Text('Setups vêm dos baús. Equipe um para ele ser monitorado em tempo real nas suas partidas X1.', style: TextStyle(color: Colors.white54, fontSize: 12.5)),
                    const SizedBox(height: 14),
                    if (itens.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(18),
                        decoration: BoxDecoration(color: const Color(0xFF10274A), borderRadius: BorderRadius.circular(14)),
                        child: const Text('Você ainda não conquistou nenhum setup. Abra baús na Loja para tentar.', style: TextStyle(color: Colors.white70)),
                      )
                    else
                      Wrap(
                        spacing: 14,
                        runSpacing: 18,
                        alignment: WrapAlignment.center,
                        children: [
                          for (final s in itens)
                            GestureDetector(
                              onTap: () => _detalhe(s),
                              child: Column(children: [
                                Stack(children: [
                                  SetupCarta(setup: s, largura: 150),
                                  if (s['equipado'] == true)
                                    Positioned(
                                        top: 6,
                                        left: 6,
                                        child: Container(
                                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                                            decoration: BoxDecoration(color: const Color(0xFF2EE59D), borderRadius: BorderRadius.circular(8)),
                                            child: const Text('EQUIPADO', style: TextStyle(color: Color(0xFF04281a), fontWeight: FontWeight.w900, fontSize: 10)))),
                                ]),
                                const SizedBox(height: 6),
                                Text('${s['nome']}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w800)),
                              ]),
                            ),
                        ],
                      ),
                    if (itens.length < total) ...[
                      const SizedBox(height: 22),
                      Center(child: Text('${total - itens.length} ainda para descobrir', style: const TextStyle(color: Colors.white38, fontWeight: FontWeight.w700))),
                    ],
                  ],
                ),
    );
  }
}
