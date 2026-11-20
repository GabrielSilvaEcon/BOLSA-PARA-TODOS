import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'animacoes.dart';
import 'api.dart';
import 'arte_cartao.dart';
import 'navegacao.dart';

/// Aprender (a Jornada do app antigo: jornada.py e jornada_player.py): trilha de unidades com lições curtas no estilo Duolingo.
/// Nada fica trancado; o erro volta ao fim da fila (sem vidas) e vai para a revisão. XP só por estudar.
/// Quem corrige e paga XP e TickerCoins é sempre o servidor; o app só mostra a pergunta e manda a resposta.
class AprenderTela extends StatefulWidget {
  const AprenderTela({super.key, required this.api});
  final Api api;

  @override
  State<AprenderTela> createState() => _AprenderTelaState();
}

const _lilas = Color(0xFFD9D4F7);

Color _hex(Object? h, [Color p = const Color(0xFF8B6CFF)]) {
  final s = '${h ?? ''}'.replaceFirst('#', '');
  final v = s.length == 6 ? int.tryParse(s, radix: 16) : null;
  return v == null ? p : Color(0xFF000000 | v);
}

class _AprenderTelaState extends State<AprenderTela> {
  Map<String, dynamic>? _d;
  String? _erro;

  @override
  void initState() {
    super.initState();
    _carregar();
  }

  Future<void> _carregar() async {
    try {
      final r = await widget.api.get('/aprender');
      if (mounted) {
        setState(() {
          _d = r;
          _erro = null;
        });
      }
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  Future<void> _abrir(String lid) async {
    // a lição abre em tela cheia (por cima do cabeçalho e da barra de baixo), para nenhum toque sair dela sem querer
    await Navigator.of(context, rootNavigator: true).push(
      MaterialPageRoute(
        builder: (_) => LicaoTela(api: widget.api, licao: lid),
      ),
    );
    _carregar();
    saldoMudou.value++; // XP e moedas novos no cabeçalho
  }

  Future<void> _aula(String aid) => Navigator.of(context).push(
        MaterialPageRoute(
          builder: (_) => AulaTela(api: widget.api, aula: aid),
        ),
      );

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Stack(
      fit: StackFit.expand,
      children: [
        const FundoCidade(),
        RefreshIndicator(
          onRefresh: _carregar,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 720),
              child: ListView(
                padding: const EdgeInsets.fromLTRB(10, 10, 10, 30),
                children: [
                  if (d == null && _erro == null)
                    const Padding(
                      padding: EdgeInsets.all(40),
                      child: Center(child: CircularProgressIndicator()),
                    ),
                  if (d == null && _erro != null) Text(_erro!, style: const TextStyle(color: Colors.white)),
                  if (d != null) ...[
                    Entrada(ordem: 0, child: _topo(d)),
                    const SizedBox(height: 10),
                    if (((d['resumo'] as Map)['erros'] as num? ?? 0) > 0) Entrada(ordem: 1, child: _revisao(d)),
                    for (final (k, u) in ((d['mapa'] as List?) ?? const []).cast<Map>().indexed) Entrada(ordem: 2 + k, child: _unidade(u, k)),
                  ],
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }

  Widget _topo(Map d) {
    final r = (d['resumo'] as Map?) ?? const {};
    final meta = ((r['meta_dia'] as num?) ?? 20).toDouble(), hoje = ((r['xp_hoje'] as num?) ?? 0).toDouble();
    final of = (r['ofensiva'] as num?)?.toInt() ?? 0;
    return Container(
      clipBehavior: Clip.antiAlias,
      padding: const EdgeInsets.fromLTRB(4, 8, 14, 12),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(22),
        border: Border.all(color: const Color(0xFFF2B84B), width: 2),
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF2E1CA0), Color(0xFF140A55)]),
        boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 16)],
      ),
      child: Stack(
        children: [
          const Positioned.fill(child: GraficoEnfeite()),
          Row(
            children: [
              Flutua(child: Image.asset('assets/aprender/touro.webp', height: 104)),
              const SizedBox(width: 6),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Sua Jornada',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, color: Colors.white),
                    ),
                    Text(
                      r['meta_atingida'] == true ? 'Meta do dia batida! 🎉' : 'Meta do dia: ${hoje.round()}/${meta.round()} XP',
                      style: TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: r['meta_atingida'] == true ? const Color(0xFF8DF5C1) : _lilas),
                    ),
                    const SizedBox(height: 6),
                    TweenAnimationBuilder<double>(
                      tween: Tween(begin: 0, end: (hoje / meta).clamp(0.0, 1.0)),
                      duration: const Duration(milliseconds: 1100),
                      curve: Curves.easeOutCubic,
                      builder: (ctx, v, _) => ClipRRect(
                        borderRadius: BorderRadius.circular(999),
                        child: LinearProgressIndicator(value: v, minHeight: 12, backgroundColor: const Color(0x335B4BD6), color: const Color(0xFF26D07C)),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        _chip(Icons.local_fire_department_rounded, '$of ${of == 1 ? 'dia' : 'dias'}', const Color(0xFFFF8A3D)),
                        const SizedBox(width: 6),
                        _chip(Icons.star_rounded, '${r['xp'] ?? 0} XP', const Color(0xFFFFC93C)),
                        const SizedBox(width: 6),
                        _chip(Icons.check_circle_rounded, '${r['licoes_feitas'] ?? 0} lições', const Color(0xFF26D07C)),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Widget _chip(IconData ic, String t, Color c) => Flexible(
        child: Container(
          padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            color: c.withValues(alpha: 0.16),
            border: Border.all(color: c.withValues(alpha: 0.7)),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(ic, size: 14, color: c),
              const SizedBox(width: 3),
              Flexible(
                child: Text(
                  t,
                  overflow: TextOverflow.ellipsis,
                  style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: c),
                ),
              ),
            ],
          ),
        ),
      );

  Widget _revisao(Map d) {
    final n = ((d['resumo'] as Map)['erros'] as num).toInt();
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Pressionavel(
        aoTocar: () => _abrir('revisao'),
        child: Container(
          padding: const EdgeInsets.fromLTRB(14, 12, 12, 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: const Color(0xFFFF8A3D), width: 2),
            gradient: const LinearGradient(colors: [Color(0xFF5A2A20), Color(0xFF2A1046)]),
          ),
          child: Row(
            children: [
              const Icon(Icons.refresh_rounded, color: Color(0xFFFFB27A), size: 30),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text(
                      'Revisar o que errou',
                      style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white),
                    ),
                    Text('$n ${n == 1 ? 'pergunta espera' : 'perguntas esperam'} por você · +5 XP', style: const TextStyle(fontSize: 12.5, color: Color(0xFFFFD6B8))),
                  ],
                ),
              ),
              const Icon(Icons.chevron_right_rounded, color: Colors.white),
            ],
          ),
        ),
      ),
    );
  }

  // ---- unidade: cabeçalho colorido e a trilha de lições em zigue-zague, ligadas por uma linha
  Widget _unidade(Map u, int k) {
    final cor = _hex(u['cor']);
    final ls = ((u['licoes'] as List?) ?? const []).cast<Map>();
    final feitas = (u['feitas'] as num?)?.toInt() ?? 0, total = (u['total'] as num?)?.toInt() ?? 1;
    return Padding(
      padding: const EdgeInsets.only(bottom: 14),
      child: Column(
        children: [
          Container(
            padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(20),
              gradient: LinearGradient(colors: [Color.lerp(cor, Colors.white, 0.05)!, Color.lerp(cor, Colors.black, 0.3)!]),
              border: Border.all(color: Color.lerp(cor, Colors.white, 0.5)!, width: 1.5),
              image: arteCartao(artesCartao[k % artesCartao.length], opacidade: 0.45),
              boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.55), blurRadius: 16)],
            ),
            child: Row(
              children: [
                Text('${u['icone'] ?? '📘'}', style: const TextStyle(fontSize: 30)),
                const SizedBox(width: 10),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Text(
                        'Unidade ${k + 1} · ${u['titulo']}',
                        style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white),
                      ),
                      Text('${u['descricao'] ?? ''}', style: const TextStyle(fontSize: 12, color: Color(0xEEFFFFFF))),
                    ],
                  ),
                ),
                const SizedBox(width: 6),
                Column(
                  children: [
                    Text(
                      '$feitas/$total',
                      style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white),
                    ),
                    if (u['completa'] == true) const Icon(Icons.verified_rounded, color: Colors.white, size: 18),
                  ],
                ),
              ],
            ),
          ),
          const SizedBox(height: 10),
          LayoutBuilder(
            builder: (ctx, c) {
              const passo = 124.0, topo = 30.0;
              final w = c.maxWidth;
              double x(int i) => w / 2 + sin(i * 1.1) * w * 0.26;
              return SizedBox(
                height: passo * ls.length + topo,
                child: Stack(
                  clipBehavior: Clip.none,
                  children: [
                    Positioned.fill(
                      child: CustomPaint(painter: _Caminho([for (var i = 0; i < ls.length; i++) Offset(x(i), topo + passo * i + 34)], [for (final l in ls) l['estado'] == 'concluida'], cor)),
                    ),
                    for (final (i, l) in ls.indexed) Positioned(left: x(i) - 60, top: topo + passo * i, width: 120, child: _no(l, cor)),
                  ],
                ),
              );
            },
          ),
        ],
      ),
    );
  }

  Widget _no(Map l, Color cor) {
    final est = '${l['estado']}';
    final feita = est == 'concluida', prox = est == 'proxima';
    final img = _iconeLicao['${l['id']}'];
    final anel = feita ? const Color(0xFFF2B84B) : (prox ? const Color(0xFF2EE88A) : const Color(0xFF4F7BFF));
    final bola = Pressionavel(
      aoTocar: () => _opcoes(l),
      child: Stack(
        clipBehavior: Clip.none,
        children: [
          Container(
            width: 72,
            height: 72,
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color.lerp(anel, Colors.white, 0.45)!, anel, Color.lerp(anel, Colors.black, 0.35)!]),
              boxShadow: [
                BoxShadow(color: Color.lerp(anel, Colors.black, 0.55)!, offset: const Offset(0, 5)),
                BoxShadow(
                  color: anel.withValues(alpha: prox ? 0.8 : 0.45),
                  blurRadius: prox ? 20 : 12,
                ),
              ],
            ),
            child: ClipOval(
              child: img != null
                  ? Image.asset('assets/aprender/lic_$img.webp', fit: BoxFit.cover)
                  : DecoratedBox(
                      decoration: const BoxDecoration(gradient: RadialGradient(colors: [Color(0xFF3A3FD0), Color(0xFF1A1A86)])),
                      child: Center(child: Text('${l['icone'] ?? '⭐'}', style: const TextStyle(fontSize: 30))),
                    ),
            ),
          ),
          if (feita)
            Positioned(
              right: -2,
              bottom: -2,
              child: Container(
                width: 26,
                height: 26,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: const Color(0xFFF2B84B),
                  border: Border.all(color: Colors.white, width: 2),
                ),
                child: const Icon(Icons.check_rounded, size: 17, color: Color(0xFF3B2600)),
              ),
            ),
        ],
      ),
    );
    return Column(
      children: [
        prox ? _Pulsando(cor: const Color(0xFF12A83C), child: bola) : bola,
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            color: const Color(0xE0160E52),
            border: Border.all(color: (feita || prox ? anel : const Color(0xFF6A4FE6)).withValues(alpha: 0.7)),
          ),
          child: Text(
            '${l['titulo']}',
            maxLines: 2,
            textAlign: TextAlign.center,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontSize: 11.5, height: 1.15, fontWeight: FontWeight.w800, color: Colors.white),
          ),
        ),
      ],
    );
  }

  void _opcoes(Map l) {
    final feita = l['estado'] == 'concluida';
    showModalBottomSheet<void>(
      context: context,
      backgroundColor: const Color(0xFF16104A),
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
      builder: (ctx) => Padding(
        padding: const EdgeInsets.fromLTRB(18, 18, 18, 28),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text(
              '${l['icone'] ?? ''} ${l['titulo']}',
              style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: Colors.white),
            ),
            const SizedBox(height: 4),
            Text(
              feita
                  ? 'Lição concluída · melhor resultado ${(((l['melhor'] as num?) ?? 0) * 100).round()}% de acertos de primeira. Refaça para treinar (+10 XP).'
                  : '${l['exercicios']} perguntas rápidas · +10 XP (+5 se acertar tudo de primeira).',
              style: const TextStyle(color: _lilas),
            ),
            const SizedBox(height: 14),
            FilledButton.icon(
              style: FilledButton.styleFrom(
                minimumSize: const Size.fromHeight(52),
                backgroundColor: const Color(0xFF12A83C),
                textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
              ),
              onPressed: () {
                Navigator.of(ctx).pop();
                _abrir('${l['id']}');
              },
              icon: const Icon(Icons.play_arrow_rounded),
              label: Text(feita ? 'Refazer lição' : 'Começar lição'),
            ),
            if (l['aula'] != null) ...[
              const SizedBox(height: 8),
              OutlinedButton.icon(
                style: OutlinedButton.styleFrom(
                  minimumSize: const Size.fromHeight(46),
                  foregroundColor: Colors.white,
                  side: const BorderSide(color: Color(0xFF8B6CFF)),
                ),
                onPressed: () {
                  Navigator.of(ctx).pop();
                  _aula('${l['aula']}');
                },
                icon: const Icon(Icons.menu_book_rounded),
                label: const Text('Ler a aula antes'),
              ),
            ],
          ],
        ),
      ),
    );
  }
}

/// Ícone desenhado de cada lição (assets/aprender/lic_*.webp); as outras usam o emoji num disco azul.
const _iconeLicao = {
  'l_risco': 'balanca',
  'l_val': 'balanca',
  'l_juros': 'grafico',
  'l_acoes': 'grafico',
  'l_tec': 'grafico',
  'l_risc2': 'grafico',
  'l_inflacao': 'carrinho',
  'l_reserva': 'boia',
  'l_risc1': 'boia',
  'l_rf_como': 'banco',
  'l_fundos': 'banco',
  'l_rf_taxa': 'ampulheta',
};

/// Fundo da cidade roxa (Aprender e Perfil), parado atrás da rolagem e escurecido para não brigar com os cartões.
class FundoCidade extends StatelessWidget {
  const FundoCidade({super.key});

  @override
  Widget build(BuildContext context) => Stack(
        fit: StackFit.expand,
        children: [
          const ColoredBox(color: Color(0xFF140A55)),
          Image.asset('assets/aprender/fundo.webp', fit: BoxFit.cover, alignment: Alignment.topCenter),
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0xCC0A0A5A), Color(0x33140A55), Color(0x44140A55), Color(0xCC050038)],
                stops: [0, 0.3, 0.7, 1],
              ),
            ),
          ),
        ],
      );
}

/// Velas e seta subindo, apagadas, no canto direito dos cartões de destaque (Jornada e Perfil).
class GraficoEnfeite extends StatelessWidget {
  const GraficoEnfeite({super.key});

  @override
  Widget build(BuildContext context) => IgnorePointer(child: CustomPaint(painter: _Enfeite()));
}

class _Enfeite extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    final w = s.width, h = s.height;
    const altas = [0.55, 0.42, 0.5, 0.3, 0.38, 0.22, 0.28, 0.12];
    for (var i = 0; i < altas.length; i++) {
      final x = w * (0.6 + i * 0.05), y = h * altas[i];
      final sobe = i.isEven;
      final p = Paint()..color = (sobe ? const Color(0xFF26D07C) : const Color(0xFFFF5A7A)).withValues(alpha: 0.22);
      c.drawLine(Offset(x, y - 8), Offset(x, y + 26), p..strokeWidth = 1.5);
      c.drawRRect(RRect.fromRectAndRadius(Rect.fromLTWH(x - 3.5, y, 7, 18), const Radius.circular(1.5)), p);
    }
    final seta = Path()
      ..moveTo(w * 0.62, h * 0.95)
      ..lineTo(w * 0.74, h * 0.72)
      ..lineTo(w * 0.8, h * 0.82)
      ..lineTo(w * 0.95, h * 0.18);
    c.drawPath(
      seta,
      Paint()
        ..shader = const LinearGradient(colors: [Color(0x00FF9A3C), Color(0x88FFB84D)]).createShader(Rect.fromLTWH(w * 0.6, 0, w * 0.4, h))
        ..style = PaintingStyle.stroke
        ..strokeWidth = 7
        ..strokeCap = StrokeCap.round
        ..strokeJoin = StrokeJoin.round,
    );
    final ponta = Path()
      ..moveTo(w * 0.95 + 4, h * 0.18 - 14)
      ..lineTo(w * 0.95 + 8, h * 0.18 + 12)
      ..lineTo(w * 0.95 - 16, h * 0.18 + 2)
      ..close();
    c.drawPath(ponta, Paint()..color = const Color(0x88FFB84D));
  }

  @override
  bool shouldRepaint(_Enfeite o) => false;
}

/// Linha da trilha ligando as lições: dourada onde já foi feita, apagada no resto.
class _Caminho extends CustomPainter {
  _Caminho(this.pts, this.feitos, this.cor);
  final List<Offset> pts;
  final List<bool> feitos;
  final Color cor;

  @override
  void paint(Canvas c, Size s) {
    for (var i = 0; i + 1 < pts.length; i++) {
      final a = pts[i], b = pts[i + 1];
      final p = Path()
        ..moveTo(a.dx, a.dy)
        ..cubicTo(a.dx, (a.dy + b.dy) / 2, b.dx, (a.dy + b.dy) / 2, b.dx, b.dy);
      c.drawPath(
        p,
        Paint()
          ..color = feitos[i] ? const Color(0xFFF2B84B) : const Color(0xAA8B6CFF)
          ..style = PaintingStyle.stroke
          ..strokeWidth = feitos[i] ? 7 : 4
          ..strokeCap = StrokeCap.round,
      );
    }
  }

  @override
  bool shouldRepaint(_Caminho o) => true;
}

/// A próxima lição pulsa e mostra "COMEÇAR" em cima.
class _Pulsando extends StatefulWidget {
  const _Pulsando({required this.cor, required this.child});
  final Color cor;
  final Widget child;

  @override
  State<_Pulsando> createState() => _PulsandoState();
}

class _PulsandoState extends State<_Pulsando> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1100))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (ctx, f) => Stack(
          clipBehavior: Clip.none,
          alignment: Alignment.center,
          children: [
            Container(
              width: 72 + 24 * _c.value,
              height: 72 + 24 * _c.value,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: widget.cor.withValues(alpha: 0.25 * (1 - _c.value)),
              ),
            ),
            f!,
            Positioned(
              top: -24,
              child: Transform.translate(
                offset: Offset(0, -3 * _c.value),
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(10),
                    gradient: const LinearGradient(colors: [Color(0xFF2EE88A), Color(0xFF12A83C)]),
                    border: Border.all(color: const Color(0xFFB8FFD9)),
                    boxShadow: const [BoxShadow(color: Color(0x8812A83C), blurRadius: 10)],
                  ),
                  child: const Text(
                    'COMEÇAR',
                    style: TextStyle(fontSize: 11, fontWeight: FontWeight.w900, color: Colors.white),
                  ),
                ),
              ),
            ),
          ],
        ),
        child: widget.child,
      );
}

/// Texto da aula (o mesmo do app antigo), com títulos e negrito simples.
class AulaTela extends StatefulWidget {
  const AulaTela({super.key, required this.api, required this.aula});
  final Api api;
  final String aula;

  @override
  State<AulaTela> createState() => _AulaTelaState();
}

class _AulaTelaState extends State<AulaTela> {
  Map<String, dynamic>? _d;

  @override
  void initState() {
    super.initState();
    widget.api.get('/aprender/aula/${widget.aula}').then((r) {
      if (mounted) setState(() => _d = r);
    }).catchError((_) {});
  }

  /// Markdown simples do app antigo: "## " vira título, "**x**" vira negrito, "- " vira item.
  List<Widget> _md(String t) {
    final out = <Widget>[];
    for (final linha in t.split('\n')) {
      final l = linha.trimRight();
      if (l.trim().isEmpty) {
        out.add(const SizedBox(height: 8));
        continue;
      }
      if (l.startsWith('#')) {
        out.add(
          Padding(
            padding: const EdgeInsets.only(top: 8, bottom: 4),
            child: Text(
              l.replaceAll(RegExp(r'^#+\s*'), ''),
              style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Color(0xFFFFD66B)),
            ),
          ),
        );
        continue;
      }
      final item = l.trimLeft().startsWith('- ') || l.trimLeft().startsWith('* ');
      final txt = item ? l.trimLeft().substring(2) : l;
      final partes = txt.split('**');
      out.add(
        Padding(
          padding: EdgeInsets.only(left: item ? 10 : 0, bottom: 2),
          child: Text.rich(
            TextSpan(
              children: [
                if (item)
                  const TextSpan(
                    text: '•  ',
                    style: TextStyle(color: Color(0xFFB59BFF), fontWeight: FontWeight.w900),
                  ),
                for (final (i, p) in partes.indexed)
                  TextSpan(
                    text: p,
                    style: TextStyle(fontWeight: i.isOdd ? FontWeight.w900 : FontWeight.w400),
                  ),
              ],
            ),
            style: const TextStyle(fontSize: 15, height: 1.45, color: Color(0xFFEDE9FF)),
          ),
        ),
      );
    }
    return out;
  }

  @override
  Widget build(BuildContext context) {
    final d = _d;
    return Scaffold(
      backgroundColor: const Color(0xFF110C3A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF110C3A),
        title: const Text('Aula', style: TextStyle(fontWeight: FontWeight.w900)),
      ),
      body: d == null
          ? const Center(child: CircularProgressIndicator())
          : ListView(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 30),
              children: [
                Text(
                  '${d['titulo']}',
                  style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white),
                ),
                if (d['min'] != null) Text('Leitura de ${d['min']} min', style: const TextStyle(color: _lilas)),
                const SizedBox(height: 10),
                ..._md('${d['texto'] ?? ''}'),
              ],
            ),
    );
  }
}

/// A lição: uma pergunta por vez (escolha, completar, verdadeiro/falso, ordenar, ligar pares), com a barra de progresso,
/// a faixa de acerto/erro com a explicação e, no fim, a comemoração com XP, sequência, moedas e conquistas.
class LicaoTela extends StatefulWidget {
  const LicaoTela({super.key, required this.api, required this.licao});
  final Api api;
  final String licao;

  @override
  State<LicaoTela> createState() => _LicaoTelaState();
}

class _LicaoTelaState extends State<LicaoTela> with TickerProviderStateMixin {
  Map<String, dynamic>? _s; // sessão (título, progresso) e exercício atual
  Map<String, dynamic>? _ex;
  Map<String, dynamic>? _retorno; // resposta corrigida (faixa de baixo)
  Map<String, dynamic>? _proximo; // o que veio junto com a correção
  Map<String, dynamic>? _fim;
  String? _erro;
  bool _ocupado = false;
  // resposta em montagem
  int? _escolha;
  bool? _vf;
  final List<String> _ordem = [];
  final Map<String, String> _pares = {};
  String? _parEsq;
  late final AnimationController _tremor = AnimationController(vsync: this, duration: const Duration(milliseconds: 420));

  @override
  void initState() {
    super.initState();
    _comecar();
  }

  @override
  void dispose() {
    _tremor.dispose();
    super.dispose();
  }

  Future<void> _comecar() async {
    try {
      final r = await widget.api.post('/aprender/licao/${widget.licao}');
      if (mounted) {
        setState(() {
          _s = (r['sessao'] as Map?)?.cast<String, dynamic>();
          _ex = (r['exercicio'] as Map?)?.cast<String, dynamic>();
        });
      }
    } catch (e) {
      if (mounted) setState(() => _erro = e.toString());
    }
  }

  void _limpar() {
    _escolha = null;
    _vf = null;
    _ordem.clear();
    _pares.clear();
    _parEsq = null;
  }

  Object? get _resposta {
    final t = _ex?['tipo'];
    if (t == 'escolha' || t == 'completar') return _escolha;
    if (t == 'vf') return _vf;
    if (t == 'ordenar') return (_ordem.length == ((_ex?['itens'] as List?)?.length ?? 0)) ? List<String>.from(_ordem) : null;
    if (t == 'pares') return _pares.length == ((_ex?['esquerda'] as List?)?.length ?? 0) ? Map<String, String>.from(_pares) : null;
    return null;
  }

  Future<void> _verificar() async {
    final r = _resposta;
    if (r == null || _ocupado) return;
    setState(() => _ocupado = true);
    try {
      final res = await widget.api.post('/aprender/responder', {'id': _ex!['id'], 'resposta': r});
      if (!mounted) return;
      final ok = res['ok'] == true;
      ok ? HapticFeedback.lightImpact() : HapticFeedback.heavyImpact();
      if (!ok) _tremor.forward(from: 0);
      setState(() {
        _retorno = res;
        _proximo = res;
      });
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  void _continuar() {
    final p = _proximo;
    if (p == null) return;
    setState(() {
      _retorno = null;
      _limpar();
      if (p['fim'] != null) {
        _fim = (p['fim'] as Map).cast<String, dynamic>();
      } else {
        _s = (p['sessao'] as Map?)?.cast<String, dynamic>();
        _ex = (p['exercicio'] as Map?)?.cast<String, dynamic>();
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF0E0A33),
      body: SafeArea(
        child: _fim != null
            ? _Fim(fim: _fim!, aoFechar: () => Navigator.of(context).maybePop())
            : _erro != null
                ? Center(
                    child: Padding(
                      padding: const EdgeInsets.all(24),
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Text(
                            _erro!,
                            textAlign: TextAlign.center,
                            style: const TextStyle(color: Colors.white, fontSize: 16),
                          ),
                          const SizedBox(height: 12),
                          FilledButton(onPressed: () => Navigator.of(context).maybePop(), child: const Text('Voltar')),
                        ],
                      ),
                    ),
                  )
                : _ex == null
                    ? const Center(child: CircularProgressIndicator())
                    : Column(
                        children: [
                          _barra(),
                          Expanded(
                            child: AnimatedBuilder(
                              animation: _tremor,
                              builder: (ctx, f) => Transform.translate(offset: Offset(sin(_tremor.value * pi * 6) * 10 * (1 - _tremor.value), 0), child: f),
                              child: AnimatedSwitcher(
                                duration: const Duration(milliseconds: 300),
                                transitionBuilder: (c, a) => SlideTransition(
                                  position: Tween(begin: const Offset(0.25, 0), end: Offset.zero).animate(a),
                                  child: FadeTransition(opacity: a, child: c),
                                ),
                                child: KeyedSubtree(key: ValueKey(_ex!['id']), child: _pergunta(_ex!)),
                              ),
                            ),
                          ),
                          _rodape(),
                        ],
                      ),
      ),
    );
  }

  Widget _barra() {
    final pct = ((_s?['pct'] as num?) ?? 0).toDouble();
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 6, 14, 6),
      child: Row(
        children: [
          IconButton(
            onPressed: () => Navigator.of(context).maybePop(),
            icon: const Icon(Icons.close_rounded, color: Colors.white),
          ),
          Expanded(
            child: TweenAnimationBuilder<double>(
              tween: Tween(end: pct),
              duration: const Duration(milliseconds: 500),
              curve: Curves.easeOutCubic,
              builder: (ctx, v, _) => ClipRRect(
                borderRadius: BorderRadius.circular(999),
                child: LinearProgressIndicator(value: v, minHeight: 14, backgroundColor: const Color(0x335B4BD6), color: const Color(0xFF26D07C)),
              ),
            ),
          ),
          const SizedBox(width: 10),
          Text(
            '${_s?['feitos'] ?? 0}/${_s?['total'] ?? 0}',
            style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white),
          ),
        ],
      ),
    );
  }

  Widget _pergunta(Map ex) {
    final t = ex['tipo'];
    final travado = _retorno != null;
    final rotulo = {'escolha': 'Escolha a resposta', 'completar': 'Complete a frase', 'vf': 'Verdadeiro ou falso?', 'ordenar': 'Coloque na ordem', 'pares': 'Ligue os pares'}[t] ?? '';
    return ListView(
      padding: const EdgeInsets.fromLTRB(16, 6, 16, 16),
      children: [
        Text(
          rotulo.toUpperCase(),
          style: const TextStyle(fontSize: 12, letterSpacing: 1, fontWeight: FontWeight.w900, color: Color(0xFFB59BFF)),
        ),
        const SizedBox(height: 6),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Image.asset('assets/home/mascote_principal.webp', height: 64),
            const SizedBox(width: 8),
            Expanded(
              child: Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  color: const Color(0xFF1B1462),
                  border: Border.all(color: const Color(0xFF6A4FE6)),
                ),
                child: Text(
                  '${ex['pergunta']}',
                  style: const TextStyle(fontSize: 17, height: 1.35, fontWeight: FontWeight.w700, color: Colors.white),
                ),
              ),
            ),
          ],
        ),
        const SizedBox(height: 16),
        if (t == 'escolha' || t == 'completar')
          for (final (i, o) in ((ex['opcoes'] as List?) ?? const []).indexed) _opcao('$o', _escolha == i, travado ? null : () => setState(() => _escolha = i)),
        if (t == 'vf')
          Row(
            children: [
              Expanded(child: _opcao('Verdadeiro', _vf == true, travado ? null : () => setState(() => _vf = true), icone: Icons.check_rounded)),
              const SizedBox(width: 10),
              Expanded(child: _opcao('Falso', _vf == false, travado ? null : () => setState(() => _vf = false), icone: Icons.close_rounded)),
            ],
          ),
        if (t == 'ordenar') ..._ordenar(ex, travado),
        if (t == 'pares') _paresW(ex, travado),
      ],
    );
  }

  Widget _opcao(String t, bool sel, VoidCallback? f, {IconData? icone}) => Padding(
        padding: const EdgeInsets.only(bottom: 10),
        child: Pressionavel(
          aoTocar: f,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 180),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              color: sel ? const Color(0xFF3B2A9E) : const Color(0xFF1B1462),
              border: Border.all(color: sel ? const Color(0xFFB59BFF) : const Color(0xFF4A3BAA), width: 2),
              boxShadow: [BoxShadow(color: sel ? const Color(0xFF7B63F0) : const Color(0xFF0B0828), offset: const Offset(0, 4))],
            ),
            child: Row(
              children: [
                if (icone != null) ...[Icon(icone, color: Colors.white), const SizedBox(width: 8)],
                Expanded(
                  child: Text(
                    t,
                    style: const TextStyle(fontSize: 15.5, fontWeight: FontWeight.w700, color: Colors.white),
                  ),
                ),
              ],
            ),
          ),
        ),
      );

  List<Widget> _ordenar(Map ex, bool travado) {
    final itens = ((ex['itens'] as List?) ?? const []).cast<String>();
    final sobra = itens.where((i) => !_ordem.contains(i)).toList();
    return [
      Container(
        constraints: const BoxConstraints(minHeight: 60),
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          border: Border.all(color: const Color(0xFF6A4FE6), width: 1.5),
          color: const Color(0x221B1462),
        ),
        child: Wrap(
          spacing: 6,
          runSpacing: 6,
          children: [
            if (_ordem.isEmpty)
              const Padding(
                padding: EdgeInsets.all(8),
                child: Text('Toque nos itens na ordem certa', style: TextStyle(color: _lilas)),
              ),
            for (final (k, i) in _ordem.indexed) ActionChip(label: Text('${k + 1}. $i'), backgroundColor: const Color(0xFF3B2A9E), onPressed: travado ? null : () => setState(() => _ordem.remove(i))),
          ],
        ),
      ),
      const SizedBox(height: 12),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [for (final i in sobra) ActionChip(label: Text(i), backgroundColor: const Color(0xFF1B1462), onPressed: travado ? null : () => setState(() => _ordem.add(i)))],
      ),
    ];
  }

  Widget _paresW(Map ex, bool travado) {
    final esq = ((ex['esquerda'] as List?) ?? const []).cast<String>();
    final dir = ((ex['direita'] as List?) ?? const []).cast<String>();
    const cores = [Color(0xFF26D07C), Color(0xFF38B6FF), Color(0xFFF2B84B), Color(0xFFFF6AD5), Color(0xFFB59BFF)];
    Color? corDe(String e) => _pares.containsKey(e) ? cores[esq.indexOf(e) % cores.length] : null;
    Widget bloco(String t, Color? cor, bool sel, VoidCallback? f) => Padding(
          padding: const EdgeInsets.only(bottom: 8),
          child: Pressionavel(
            aoTocar: f,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 180),
              padding: const EdgeInsets.all(10),
              decoration: BoxDecoration(
                borderRadius: BorderRadius.circular(12),
                color: cor?.withValues(alpha: 0.22) ?? (sel ? const Color(0xFF3B2A9E) : const Color(0xFF1B1462)),
                border: Border.all(color: cor ?? (sel ? const Color(0xFFB59BFF) : const Color(0xFF4A3BAA)), width: 2),
              ),
              child: Text(
                t,
                style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w700, color: Colors.white),
              ),
            ),
          ),
        );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Text('Toque num item da esquerda e depois no par dele à direita.', style: TextStyle(fontSize: 12.5, color: _lilas)),
        const SizedBox(height: 8),
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Expanded(
              child: Column(
                children: [
                  for (final e in esq)
                    bloco(
                      e,
                      corDe(e),
                      _parEsq == e,
                      travado
                          ? null
                          : () => setState(() {
                                _pares.remove(e);
                                _parEsq = e;
                              }),
                    ),
                ],
              ),
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                children: [
                  for (final d in dir)
                    bloco(
                      d,
                      _pares.entries.where((x) => x.value == d).map((x) => corDe(x.key)).firstOrNull,
                      false,
                      travado || _parEsq == null
                          ? null
                          : () => setState(() {
                                _pares.removeWhere((k, v) => v == d);
                                _pares[_parEsq!] = d;
                                _parEsq = null;
                              }),
                    ),
                ],
              ),
            ),
          ],
        ),
      ],
    );
  }

  Widget _rodape() {
    final r = _retorno;
    if (r == null) {
      final pode = _resposta != null && !_ocupado;
      return Padding(
        padding: const EdgeInsets.fromLTRB(16, 4, 16, 14),
        child: SizedBox(
          width: double.infinity,
          height: 54,
          child: FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: const Color(0xFF12A83C),
              disabledBackgroundColor: const Color(0x3312A83C),
              textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
            ),
            onPressed: pode ? _verificar : null,
            child: _ocupado ? const SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white)) : const Text('VERIFICAR'),
          ),
        ),
      );
    }
    final ok = r['ok'] == true;
    final cor = ok ? const Color(0xFF26D07C) : const Color(0xFFFF4D6D);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 1, end: 0),
      duration: const Duration(milliseconds: 320),
      curve: Curves.easeOutCubic,
      builder: (ctx, v, f) => Transform.translate(offset: Offset(0, 80 * v), child: f),
      child: Container(
        width: double.infinity,
        padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
        decoration: BoxDecoration(
          color: cor.withValues(alpha: 0.18),
          border: Border(top: BorderSide(color: cor, width: 2)),
        ),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(ok ? Icons.check_circle_rounded : Icons.cancel_rounded, color: cor, size: 28),
                const SizedBox(width: 8),
                Text(
                  ok ? 'Mandou bem!' : 'Quase!',
                  style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: cor),
                ),
              ],
            ),
            if (!ok)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(
                  'Resposta certa: ${r['certa']}',
                  style: const TextStyle(fontWeight: FontWeight.w800, color: Colors.white),
                ),
              ),
            if ('${r['explicacao']}'.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text('${r['explicacao']}', style: const TextStyle(color: Color(0xFFEDE9FF), height: 1.35)),
              ),
            if (!ok)
              const Padding(
                padding: EdgeInsets.only(top: 4),
                child: Text('Essa pergunta volta no fim da lição.', style: TextStyle(fontSize: 12, color: _lilas)),
              ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              height: 50,
              child: FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: cor,
                  foregroundColor: ok ? const Color(0xFF06361F) : Colors.white,
                  textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900),
                ),
                onPressed: _continuar,
                child: const Text('CONTINUAR'),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

/// Fim da lição: confete, o touro comemorando, XP subindo, sequência, moedas, nível novo e conquistas.
class _Fim extends StatefulWidget {
  const _Fim({required this.fim, required this.aoFechar});
  final Map<String, dynamic> fim;
  final VoidCallback aoFechar;

  @override
  State<_Fim> createState() => _FimState();
}

class _FimState extends State<_Fim> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 2600))..forward();
  late final List<(double, double, double, Color)> _conf = [
    for (var i = 0; i < 40; i++)
      (Random(i).nextDouble(), Random(i * 7).nextDouble(), Random(i * 13).nextDouble(), [const Color(0xFF26D07C), const Color(0xFFF2B84B), const Color(0xFFFF6AD5), const Color(0xFF38B6FF)][i % 4]),
  ];

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final f = widget.fim;
    final xp = (f['xp'] as num?)?.toInt() ?? 0;
    final subiu = (f['nivel_depois'] as num? ?? 0) > (f['nivel_antes'] as num? ?? 0);
    final conq = ((f['conquistas_novas'] as List?) ?? const []).cast<String>();
    final tc = (f['tc'] as num?)?.toInt() ?? 0;
    return AnimatedBuilder(
      animation: _c,
      builder: (ctx, _) {
        final t = _c.value;
        return Stack(
          children: [
            // confete caindo
            Positioned.fill(
              child: IgnorePointer(child: CustomPaint(painter: _Confete(_conf, t))),
            ),
            ListView(
              padding: const EdgeInsets.fromLTRB(18, 30, 18, 24),
              children: [
                Transform.scale(scale: Curves.elasticOut.transform((t / 0.5).clamp(0.0, 1.0)), child: Image.asset('assets/home/mascote_principal.webp', height: 170)),
                const SizedBox(height: 8),
                Text(
                  f['revisao'] == true ? 'Revisão concluída!' : (f['perfeita'] == true ? 'Lição perfeita!' : 'Lição concluída!'),
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: Color(0xFFFFD66B)),
                ),
                Text(
                  '${f['acertos_primeira']} de ${f['total']} de primeira',
                  textAlign: TextAlign.center,
                  style: const TextStyle(color: _lilas),
                ),
                const SizedBox(height: 16),
                Row(
                  children: [
                    _quadro(Icons.star_rounded, const Color(0xFFFFC93C), '+${(xp * Curves.easeOut.transform(((t - 0.3) / 0.4).clamp(0.0, 1.0))).round()}', 'XP'),
                    const SizedBox(width: 8),
                    _quadro(Icons.local_fire_department_rounded, const Color(0xFFFF8A3D), '${f['ofensiva'] ?? 0}', (f['ofensiva'] ?? 0) == 1 ? 'dia seguido' : 'dias seguidos'),
                    const SizedBox(width: 8),
                    _quadro(Icons.toll_rounded, const Color(0xFFF2B84B), tc > 0 ? '+$tc' : '0', 'Ticker Coins'),
                  ],
                ),
                const SizedBox(height: 12),
                if (f['meta_nova'] == true) _faixa('🎯 Meta do dia batida!', const Color(0xFF26D07C)),
                if (subiu) _faixa('⬆️ Você subiu para o nível ${f['nivel_depois']}!', const Color(0xFFF2B84B)),
                for (final c in conq) _faixa('🏅 Conquista nova: $c', const Color(0xFFB59BFF)),
                const SizedBox(height: 16),
                SizedBox(
                  height: 54,
                  child: FilledButton(
                    style: FilledButton.styleFrom(
                      backgroundColor: const Color(0xFF12A83C),
                      textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                    ),
                    onPressed: widget.aoFechar,
                    child: const Text('CONTINUAR'),
                  ),
                ),
              ],
            ),
          ],
        );
      },
    );
  }

  Widget _quadro(IconData ic, Color c, String v, String t) => Expanded(
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            color: c.withValues(alpha: 0.14),
            border: Border.all(color: c, width: 2),
          ),
          child: Column(
            children: [
              Icon(ic, color: c, size: 28),
              Text(
                v,
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: c),
              ),
              Text(
                t,
                textAlign: TextAlign.center,
                style: const TextStyle(fontSize: 11.5, color: _lilas),
              ),
            ],
          ),
        ),
      );

  Widget _faixa(String t, Color c) => Container(
        margin: const EdgeInsets.only(bottom: 8),
        padding: const EdgeInsets.all(12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          color: c.withValues(alpha: 0.16),
          border: Border.all(color: c),
        ),
        child: Text(
          t,
          textAlign: TextAlign.center,
          style: TextStyle(fontWeight: FontWeight.w900, color: c),
        ),
      );
}

class _Confete extends CustomPainter {
  _Confete(this.p, this.t);
  final List<(double, double, double, Color)> p;
  final double t;

  @override
  void paint(Canvas c, Size s) {
    for (final (x, v, g, cor) in p) {
      final y = (-0.1 + t * (0.8 + v)) * s.height;
      if (y > s.height) continue;
      c.save();
      c.translate(x * s.width + sin(t * 8 + g * 6) * 14, y);
      c.rotate(t * 10 * (g - 0.5));
      c.drawRect(const Rect.fromLTWH(-4, -7, 8, 14), Paint()..color = cor.withValues(alpha: (1 - t).clamp(0.0, 1.0)));
      c.restore();
    }
  }

  @override
  bool shouldRepaint(_Confete o) => o.t != t;
}
