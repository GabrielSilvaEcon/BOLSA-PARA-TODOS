import 'package:flutter/material.dart';

import 'api.dart';
import 'cartas.dart' show coresRaridade, rotulosRaridade;

/// Setups colecionáveis. Tudo vem do servidor (`GET /setups`): a tela só mostra o que a pessoa conquistou e deixa equipar um.
/// A arte de cada setup mora em assets/setups/<id>/ (o servidor já manda o caminho só quando o arquivo existe); sem arte, entra o
/// espaço provisório, claramente marcado, e nunca uma arte inventada.

IconData _iconeDe(String id) => switch (id) {
      'larry_williams' => Icons.bolt,
      'turtle_trading' => Icons.waves,
      'mark_minervini' => Icons.rocket_launch,
      'martelo' => Icons.vertical_align_bottom,
      'engolfo_alta' => Icons.stacked_bar_chart,
      'estrela_cadente' => Icons.star_border,
      _ => Icons.ssid_chart,
    };

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
    // Carta feita em código enquanto a arte final não chega: moldura da raridade, ícone do setup e as características do próprio cadastro.
    Widget provisoria() {
      final (_, clara, escura) = coresRaridade[setup['raridade']] ?? coresRaridade['comum']!;
      final linhas = ((setup['caracteristicas'] as List?) ?? const []).take(3).map((e) => '$e').toList();
      final u = largura / 150; // tudo escala com a largura da carta
      return Container(
        decoration: BoxDecoration(borderRadius: borda, gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [escura, const Color(0xFF0C1330)])),
        padding: EdgeInsets.fromLTRB(9 * u, 8 * u, 9 * u, 8 * u),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Row(children: [
              Flexible(child: FittedBox(fit: BoxFit.scaleDown, child: Container(
                padding: EdgeInsets.symmetric(horizontal: 6 * u, vertical: 2 * u),
                decoration: BoxDecoration(color: cor, borderRadius: BorderRadius.circular(6 * u)),
                child: Text(rotulosRaridade[setup['raridade']] ?? '', style: TextStyle(color: const Color(0xFF0C1330), fontWeight: FontWeight.w900, fontSize: 8 * u)),
              ))),
              const Spacer(),
              Flexible(child: FittedBox(fit: BoxFit.scaleDown, child: Text('SETUP', style: TextStyle(color: clara, fontWeight: FontWeight.w900, fontSize: 9 * u, letterSpacing: 1)))),
            ]),
            SizedBox(height: 8 * u),
            Expanded(
              flex: 5,
              child: Container(
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(10 * u),
                  border: Border.all(color: cor.withValues(alpha: .6)),
                  gradient: RadialGradient(colors: [cor.withValues(alpha: .45), Colors.transparent]),
                ),
                child: Center(child: Icon(_iconeDe('${setup['id']}'), size: 46 * u, color: Colors.white)),
              ),
            ),
            SizedBox(height: 7 * u),
            FittedBox(fit: BoxFit.scaleDown, child: Text('${setup['nome']}'.toUpperCase(), style: TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 13 * u))),
            SizedBox(height: 4 * u),
            Expanded(
              flex: 4,
              child: Align(
                alignment: Alignment.topLeft,
                child: Text(linhas.map((l) => '• $l').join('\n'), maxLines: 6, overflow: TextOverflow.ellipsis, style: TextStyle(color: Colors.white70, fontSize: 8 * u, height: 1.25)),
              ),
            ),
            Text('ARTE PROVISÓRIA', textAlign: TextAlign.center, style: TextStyle(color: Colors.white38, fontWeight: FontWeight.w700, fontSize: 6.5 * u, letterSpacing: .8)),
          ],
        ),
      );
    }

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
Future<void> revelarSetup(BuildContext context, Map<String, dynamic> setup, {VoidCallback? abrirMeusSetups, String titulo = 'NOVA CARTA DE SETUP!'}) {
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
            Text(titulo, style: TextStyle(color: Color(0xFFFFD76A), fontWeight: FontWeight.w900, fontSize: 16)),
            const SizedBox(height: 12),
            SetupCarta(setup: setup, largura: 170),
            const SizedBox(height: 10),
            Text('${setup['nome']}', style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900, fontSize: 18)),
            Text(rotulosRaridade[setup['raridade']] ?? '', style: TextStyle(color: cor, fontWeight: FontWeight.w800)),
            const SizedBox(height: 6),
            const Text('Com esta carta você já pode usar o setup. Equipe em Meus Setups (até 2) para usar nas partidas X1 e solo.', textAlign: TextAlign.center, style: TextStyle(color: Colors.white70, fontSize: 12.5)),
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

/// "Meus Setups": as cartas de setup que a pessoa tem, as características de cada uma e quais estão equipadas (até 2; valem sozinhas nas partidas X1 e solo).
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

  bool get _liberados => _d?['todos_liberados'] == true;
  int get _limite => ((_d?['limite'] as num?) ?? 2).toInt();
  int get _nEquipados => (_d?['equipados'] as List? ?? []).length;

  Future<void> _equipar(String id, {bool tirar = false}) async {
    if (_salvando != null) return;
    setState(() => _salvando = id);
    try {
      await widget.api.post(tirar ? '/setups/desequipar' : '/setups/equipar', {'id': id});
      await _carregar();
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString().contains('Desequipe') ? 'Você já está usando $_limite setups. Desequipe um para equipar outro.' : 'Não foi possível salvar agora. Tente de novo.')));
      }
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
          final cheio = !equipado && _nEquipados >= _limite;
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
                if ('${s['fonte_regra'] ?? ''}'.isNotEmpty)
                  Padding(padding: const EdgeInsets.only(top: 8), child: Text('${s['fonte_regra']}', style: const TextStyle(color: Colors.white54, fontStyle: FontStyle.italic, fontSize: 11.5, height: 1.3))),
                _bloco('Como entra', [if ('${(s['regra'] as Map)['compra']}'.isNotEmpty) 'Compra: ${(s['regra'] as Map)['compra']}', if ('${(s['regra'] as Map)['venda']}'.isNotEmpty) 'Venda: ${(s['regra'] as Map)['venda']}']),
                _bloco('Características', (s['caracteristicas'] as List).map((e) => '$e').toList()),
                _bloco('Indicadores', (s['indicadores'] as List).map((e) => '$e').toList()),
                const SizedBox(height: 16),
                FilledButton(
                  onPressed: _salvando != null || cheio
                      ? null
                      : () async {
                          await _equipar('${s['id']}', tirar: equipado);
                          set(() {});
                        },
                  child: Text(equipado ? 'DESEQUIPAR' : (cheio ? 'DESEQUIPE UM SETUP PRIMEIRO' : 'USAR ESTE SETUP')),
                ),
                const SizedBox(height: 6),
                Text(_liberados
                    ? 'Você pode usar até $_limite setups ao mesmo tempo. Eles são usados automaticamente nas partidas X1 e solo, sem escolher antes de cada partida.'
                    : 'Você pode usar até $_limite setups ao mesmo tempo, só os das cartas que você tem. Eles são usados automaticamente nas partidas X1 e solo, sem escolher antes de cada partida.',
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
                    Text(_liberados ? '${itens.length} setups disponíveis · $_nEquipados/$_limite equipados' : '${itens.length} de $total cartas de setup · $_nEquipados/$_limite equipados', style: const TextStyle(color: Colors.white70, fontWeight: FontWeight.w700)),
                    const SizedBox(height: 4),
                    Text(
                        _liberados
                            ? 'Por enquanto todos os setups estão liberados: escolha até 2 para serem monitorados em tempo real nas suas partidas X1 e solo (menos no Desafio do dia, que é igual para todos).'
                            : 'As cartas de setup vêm dos baús. Sem a carta, não há setup para usar. Equipe até 2 para serem monitorados em tempo real nas suas partidas X1 e solo (menos no Desafio do dia, que é igual para todos).',
                        style: const TextStyle(color: Colors.white54, fontSize: 12.5)),
                    const SizedBox(height: 14),
                    if (itens.isEmpty)
                      Container(
                        padding: const EdgeInsets.all(18),
                        decoration: BoxDecoration(color: const Color(0xFF10274A), borderRadius: BorderRadius.circular(14)),
                        child: const Text('Você ainda não tem nenhuma carta de setup. Abra baús na Loja para tentar.', style: TextStyle(color: Colors.white70)),
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
                    if (!_liberados && itens.length < total) ...[
                      const SizedBox(height: 22),
                      Center(child: Text('${total - itens.length} ainda para descobrir', style: const TextStyle(color: Colors.white38, fontWeight: FontWeight.w700))),
                    ],
                  ],
                ),
    );
  }
}
