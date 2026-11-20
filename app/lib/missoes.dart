import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'api.dart';
import 'aprender.dart' show FundoCidade;
import 'arte_cartao.dart';
import 'carteira.dart';
import 'navegacao.dart';

/// Todas as missões: as de estudo (as 3 do dia e o desafio da semana, jogar.py) e as da carteira (do dia, da semana e especiais,
/// wallet_game.py), com progresso e recompensa. Só leitura: quem conclui e paga é o próprio jogo, como no app antigo.
class MissoesTela extends StatefulWidget {
  const MissoesTela({super.key, required this.api});
  final Api api;

  @override
  State<MissoesTela> createState() => _MissoesTelaState();
}

const _lilas = Color(0xFFD9D4F7);
const _verde = Color(0xFF26D07C);
const _ouro = Color(0xFFF2B84B);

class _MissoesTelaState extends State<MissoesTela> {
  Map<String, dynamic>? _d;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    setState(() => _erro = null);
    try {
      final r = await widget.api.get('/missoes');
      if (mounted) setState(() => _d = r);
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  void _estudar() {
    Navigator.of(context).popUntil((r) => r.isFirst);
    abrirAba(2);
  }

  void _carteira() => Navigator.of(context).push(MaterialPageRoute(builder: (_) => CarteiraTela(api: widget.api)));

  @override
  Widget build(BuildContext context) {
    final d = _d;
    final est = (d?['estudo'] as Map?) ?? const {};
    final cart = ((d?['carteira'] as List?) ?? const []).cast<Map>();
    final grupos = [
      ('Carteira · hoje', cart.where((m) => m['periodo'] == 'dia').toList()),
      ('Carteira · esta semana', cart.where((m) => m['periodo'] == 'semana').toList()),
      ('Carteira · especiais', cart.where((m) => m['periodo'] == 'especial').toList()),
    ];
    var ordem = 0;
    return Scaffold(
      backgroundColor: const Color(0xFF140A55),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        RefreshIndicator(
          onRefresh: _carregar,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 30), children: [
                Row(children: [
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
                  const Expanded(child: Text('Missões', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white))),
                ]),
                if (d == null && _erro == null) const Padding(padding: EdgeInsets.all(40), child: Center(child: CircularProgressIndicator())),
                if (d == null && _erro != null)
                  Padding(
                    padding: const EdgeInsets.all(20),
                    child: Column(children: [
                      Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white)),
                      const SizedBox(height: 10),
                      FilledButton.icon(onPressed: _carregar, icon: const Icon(Icons.refresh_rounded), label: const Text('Tentar de novo')),
                    ]),
                  ),
                if (d != null) ...[
                  if (est.isNotEmpty) Entrada(ordem: ordem++, child: _semana(est)),
                  if (est.isNotEmpty) ...[
                    _titulo('Estudo · hoje', Icons.menu_book_rounded, const Color(0xFF8DF5C1)),
                    for (final m in ((est['dia'] as List?) ?? const []).cast<Map>())
                      Entrada(
                        ordem: ordem++,
                        child: _missao(m['titulo'], m['texto'], (m['atual'] as num?) ?? 0, (m['alvo'] as num?) ?? 1, m['ok'] == true, ['+${m['pontos']} pts'], const Color(0xFF26D07C), 'velas',
                            _estudar, 'Estudar'),
                      ),
                    if (est['semana'] is Map) ...[
                      _titulo('Desafio da semana', Icons.event_available_rounded, const Color(0xFFFFD27A)),
                      Builder(builder: (ctx) {
                        final s = est['semana'] as Map;
                        return Entrada(
                          ordem: ordem++,
                          child: _missao(s['titulo'], s['texto'], (s['atual'] as num?) ?? 0, (s['alvo'] as num?) ?? 1, s['ok'] == true, ['+${s['pontos']} pts'], _ouro, 'loja', _estudar, 'Estudar'),
                        );
                      }),
                    ],
                  ],
                  if (cart.isEmpty) ...[
                    _titulo('Carteira', Icons.account_balance_wallet_rounded, const Color(0xFF9AD8FF)),
                    _missao('Missões da carteira', 'Comece a sua carteira virtual para liberar as missões de investir (do dia, da semana e especiais).', 0, 1, false,
                        const [], const Color(0xFF4F9BFF), 'cofre', _carteira, 'Abrir carteira'),
                  ],
                  for (final (titulo, itens) in grupos)
                    if (itens.isNotEmpty) ...[
                      _titulo(titulo, Icons.account_balance_wallet_rounded, const Color(0xFF9AD8FF)),
                      for (final m in itens)
                        Entrada(
                          ordem: ordem++,
                          child: _missao(m['nome'], m['descricao'], (m['progresso'] as num?) ?? 0, (m['meta'] as num?) ?? 1, m['feita'] == true, _premios((m['recompensa'] as Map?) ?? const {}),
                              const Color(0xFF4F9BFF), arteDe('${m['id']}'), _carteira, 'Abrir carteira',
                              objetivo: m['objetivo']),
                        ),
                    ],
                  const SizedBox(height: 14),
                  Text('${d['regra'] ?? ''}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 11.5, color: _lilas)),
                ],
              ]),
            ),
          ),
        ),
      ]),
    );
  }

  List<String> _premios(Map r) => [
        if ((r['xp'] as num? ?? 0) > 0) '+${r['xp']} XP',
        if ((r['tc'] as num? ?? 0) > 0) '+${r['tc']} TC',
        if ((r['capital'] as num? ?? 0) > 0) '+T\$ ${(r['capital'] as num).round()}',
      ];

  Widget _titulo(String t, IconData ic, Color cor) => Padding(
        padding: const EdgeInsets.fromLTRB(4, 16, 4, 8),
        child: Row(children: [
          Icon(ic, color: cor, size: 20),
          const SizedBox(width: 6),
          Expanded(child: Text(t, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white))),
        ]),
      );

  Widget _semana(Map est) {
    final p = (est['pontos'] as Map?) ?? const {};
    Widget item(IconData ic, Color cor, String v, String t) => Expanded(
          child: Container(
            margin: const EdgeInsets.symmetric(horizontal: 3),
            padding: const EdgeInsets.symmetric(vertical: 10),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [cor.withValues(alpha: 0.42), cor.withValues(alpha: 0.12)]),
              border: Border.all(color: cor.withValues(alpha: 0.85), width: 1.5),
            ),
            child: Column(children: [
              Icon(ic, color: cor, size: 24),
              FittedBox(child: Text(v, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Colors.white))),
              Text(t, style: const TextStyle(fontSize: 11, color: Colors.white)),
            ]),
          ),
        );
    final of = (est['ofensiva'] as num?)?.toInt() ?? 0;
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: _ouro, width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF6B3A12), Color(0xFF2A1046)]),
        image: arteCartao('moedas', opacidade: 0.4),
        boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 16)],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Image.asset('assets/home/trofeu.webp', height: 44),
          const SizedBox(width: 8),
          const Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Pontos da semana', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
              Text('Estudo, missões e desafio. Lucro e risco nunca valem pontos.', style: TextStyle(fontSize: 11.5, color: Color(0xFFFFE6C2))),
            ]),
          ),
          TweenAnimationBuilder<double>(
            tween: Tween(begin: 0, end: ((p['total'] as num?) ?? 0).toDouble()),
            duration: const Duration(milliseconds: 1000),
            builder: (ctx, v, _) => Text('${v.round()}', style: const TextStyle(fontSize: 30, fontWeight: FontWeight.w900, color: _ouro)),
          ),
        ]),
        const SizedBox(height: 10),
        Row(children: [
          item(Icons.local_fire_department_rounded, const Color(0xFFFF8A3D), '$of ${of == 1 ? 'dia' : 'dias'}', 'Sequência'),
          item(Icons.bolt_rounded, const Color(0xFFFFC93C), '${est['xp_hoje'] ?? 0}', 'XP hoje'),
          item(Icons.task_alt_rounded, _verde, '${p['missoes'] ?? 0}', 'pts missões'),
          item(Icons.emoji_events_rounded, const Color(0xFFB54BFF), '${p['desafio'] ?? 0}', 'pts desafio'),
        ]),
      ]),
    );
  }

  Widget _missao(Object? titulo, Object? texto, num atual, num alvo, bool ok, List<String> premios, Color cor, String arte, VoidCallback ir, String rotuloIr, {Object? objetivo}) {
    final c = ok ? _verde : cor;
    final pct = alvo <= 0 ? 0.0 : (atual / alvo).clamp(0, 1).toDouble();
    return Container(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: c.withValues(alpha: 0.9), width: 1.6),
        gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color.lerp(c, const Color(0xFF160B5E), 0.5)!, Color.lerp(c, const Color(0xFF120850), 0.8)!]),
        image: arteCartao(arte, opacidade: 0.4),
        boxShadow: [BoxShadow(color: c.withValues(alpha: 0.3), blurRadius: 12)],
      ),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          AnimatedContainer(
            duration: const Duration(milliseconds: 400),
            width: 34,
            height: 34,
            decoration: BoxDecoration(shape: BoxShape.circle, color: ok ? _verde : c.withValues(alpha: 0.25), border: Border.all(color: Colors.white.withValues(alpha: 0.7))),
            child: Icon(ok ? Icons.check_rounded : Icons.flag_rounded, color: Colors.white, size: 19),
          ),
          const SizedBox(width: 10),
          Expanded(child: Text('${titulo ?? ''}', style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: Colors.white))),
          for (final p in premios)
            Container(
              margin: const EdgeInsets.only(left: 4),
              padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 2),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0x99120850), border: Border.all(color: _ouro)),
              child: Text(p, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: _ouro)),
            ),
        ]),
        const SizedBox(height: 6),
        Text('${texto ?? ''}', style: const TextStyle(fontSize: 12.5, color: Colors.white)),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(
            child: TweenAnimationBuilder<double>(
              tween: Tween(begin: 0, end: pct),
              duration: const Duration(milliseconds: 900),
              curve: Curves.easeOutCubic,
              builder: (ctx, v, _) => ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: LinearProgressIndicator(value: v, minHeight: 9, backgroundColor: const Color(0x55120850), color: ok ? _verde : const Color(0xFFFFD76A)),
              ),
            ),
          ),
          const SizedBox(width: 8),
          Text(ok ? 'Feita!' : '${atual.round()} / ${alvo.round()}', style: TextStyle(fontWeight: FontWeight.w900, color: ok ? _verde : Colors.white)),
        ]),
        if (!ok)
          Align(
            alignment: Alignment.centerRight,
            child: TextButton.icon(
              onPressed: ir,
              icon: const Icon(Icons.arrow_forward_rounded, size: 18),
              label: Text(rotuloIr),
              style: TextButton.styleFrom(foregroundColor: Colors.white, visualDensity: VisualDensity.compact),
            ),
          ),
      ]),
    );
  }
}
