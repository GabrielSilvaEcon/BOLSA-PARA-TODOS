import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'animacoes.dart';
import 'api.dart';
import 'arte_cartao.dart';
import 'navegacao.dart';
import 'tour.dart';

/// Aprender (a Jornada do app antigo: jornada.py e jornada_player.py): trilha de unidades com lições curtas no estilo Duolingo.
/// Nada fica trancado; o erro volta ao fim da fila (sem vidas) e vai para a revisão. XP só por estudar.
/// Quem corrige e paga XP e TickerCoins é sempre o servidor; o app só mostra a pergunta e manda a resposta.
class AprenderTela extends StatefulWidget {
  const AprenderTela({super.key, required this.api});
  final Api api;

  @override
  State<AprenderTela> createState() => _AprenderTelaState();
}

const _lilas = Color(0xFFD4E2F7);

Color _hex(Object? h, [Color p = const Color(0xFF6CA3FF)]) {
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
    await _carregar();
    saldoMudou.value++; // XP e moedas novos no cabeçalho
    // tour guiado: a lição voltou concluída
    for (final u in ((_d?['mapa'] as List?) ?? const []).cast<Map>()) {
      for (final l in ((u['licoes'] as List?) ?? const []).cast<Map>()) {
        if ('${l['id']}' == lid && l['estado'] == 'concluida') Tour.evento('licao');
      }
    }
  }

  /// Marca um elemento para o tour guiado (sem id, devolve o próprio elemento).
  Widget _alvo(String? id, Widget w) => id == null ? w : TourAlvo(id: id, child: w);

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
        gradient: const LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color(0xFF1C50A0), Color(0xFF0A2755)]),
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
                        child: LinearProgressIndicator(value: v, minHeight: 12, backgroundColor: const Color(0x334B82D6), color: const Color(0xFF26D07C)),
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
            gradient: const LinearGradient(colors: [Color(0xFF5A2A20), Color(0xFF102046)]),
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
    final bola = _alvo(
        prox ? 'aprender_proxima' : null,
        Pressionavel(
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
        ));
    return Column(
      children: [
        prox ? _Pulsando(cor: const Color(0xFF12A83C), child: bola) : bola,
        const SizedBox(height: 4),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 4),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(12),
            color: const Color(0xE00E2952),
            border: Border.all(color: (feita || prox ? anel : const Color(0xFF4F88E6)).withValues(alpha: 0.7)),
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
      backgroundColor: const Color(0xFF10274A),
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
                  side: const BorderSide(color: Color(0xFF6CA3FF)),
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
          const ColoredBox(color: Color(0xFF0B1A47)),
          Image.asset('assets/home/cidade_dia.webp', fit: BoxFit.cover, alignment: Alignment.topCenter),
          // camada azul-marinho por cima da cidade: as telas de conteúdo ficam legíveis (a tela inicial usa a cidade mais aberta)
          const DecoratedBox(
            decoration: BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topCenter,
                end: Alignment.bottomCenter,
                colors: [Color(0x880B1A47), Color(0xA60B1A47), Color(0xD90B1A47), Color(0xF20B1A47)],
                stops: [0, 0.35, 0.7, 1],
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
          ..color = feitos[i] ? const Color(0xFFF2B84B) : const Color(0xAA6CA3FF)
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
                    style: TextStyle(color: Color(0xFF9BBFFF), fontWeight: FontWeight.w900),
                  ),
                for (final (i, p) in partes.indexed)
                  TextSpan(
                    text: p,
                    style: TextStyle(fontWeight: i.isOdd ? FontWeight.w900 : FontWeight.w400),
                  ),
              ],
            ),
            style: const TextStyle(fontSize: 15, height: 1.45, color: Color(0xFFE9F1FF)),
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
      backgroundColor: const Color(0xFF0C1E3A),
      appBar: AppBar(
        backgroundColor: const Color(0xFF0C1E3A),
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
    final r = _retorno;
    return Scaffold(
      backgroundColor: const Color(0xFF0B1A47),
      body: Stack(fit: StackFit.expand, children: [
        const FundoCidade(),
        SafeArea(
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 640),
              child: _fim != null
                  ? _Fim(fim: _fim!, aoFechar: () => Navigator.of(context).maybePop())
                  : _erro != null
                      ? Center(
                          child: Padding(
                            padding: const EdgeInsets.all(24),
                            child: Column(mainAxisSize: MainAxisSize.min, children: [
                              Text(_erro!, textAlign: TextAlign.center, style: const TextStyle(color: Colors.white, fontSize: 16)),
                              const SizedBox(height: 12),
                              FilledButton(onPressed: () => Navigator.of(context).maybePop(), child: const Text('Voltar')),
                            ]),
                          ),
                        )
                      : _ex == null
                          ? const Center(child: CircularProgressIndicator())
                          : Column(children: [
                              _barra(),
                              Expanded(
                                child: AnimatedBuilder(
                                  animation: _tremor,
                                  builder: (ctx, f) => Transform.translate(offset: Offset(sin(_tremor.value * pi * 6) * 10 * (1 - _tremor.value), 0), child: f),
                                  child: AnimatedSwitcher(
                                    duration: const Duration(milliseconds: 320),
                                    transitionBuilder: (c, a) => FadeTransition(
                                      opacity: a,
                                      child: ScaleTransition(scale: Tween(begin: 0.96, end: 1.0).animate(a), child: c),
                                    ),
                                    child: KeyedSubtree(
                                      key: ValueKey('${_ex!['id']}-${r == null ? 'p' : 'r'}'),
                                      child: r == null ? _pergunta(_ex!) : _resultado(_ex!, r),
                                    ),
                                  ),
                                ),
                              ),
                              _rodape(),
                            ]),
            ),
          ),
        ),
      ]),
    );
  }

  Widget _barra() {
    final pct = ((_s?['pct'] as num?) ?? 0).toDouble();
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 4, 14, 2),
      child: Row(children: [
        IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.close_rounded, color: Colors.white)),
        Expanded(
          child: TweenAnimationBuilder<double>(
            tween: Tween(end: pct),
            duration: const Duration(milliseconds: 500),
            curve: Curves.easeOutCubic,
            builder: (ctx, v, _) => Container(
              height: 14,
              padding: const EdgeInsets.all(2),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xFF07112E), border: Border.all(color: const Color(0xFF2B4F9E))),
              child: Align(
                alignment: Alignment.centerLeft,
                child: FractionallySizedBox(
                  widthFactor: v.clamp(0.02, 1.0),
                  child: Container(
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(999),
                      gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF6BFF8A), Color(0xFF12A83C)]),
                    ),
                  ),
                ),
              ),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Text('${_s?['feitos'] ?? 0}/${_s?['total'] ?? 0}', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
      ]),
    );
  }

  static const _rotulos = {'escolha': 'Escolha a resposta', 'completar': 'Complete a frase', 'vf': 'Verdadeiro ou falso?', 'ordenar': 'Coloque na ordem', 'pares': 'Ligue os pares'};

  /// Pergunta (referência "Escolha a resposta"): o urso espiando, a etiqueta inclinada, o cartão da pergunta e as opções.
  Widget _pergunta(Map ex) {
    final t = ex['tipo'];
    return ListView(
      padding: const EdgeInsets.fromLTRB(14, 4, 14, 16),
      children: [
        SizedBox(
          height: 96,
          child: Stack(clipBehavior: Clip.none, children: [
            Positioned(left: -6, bottom: -14, child: Flutua(altura: 3, child: Image.asset('assets/aprender/licao_urso_pergunta.webp', height: 116))),
            Positioned(left: 128, right: 0, bottom: 6, child: _Etiqueta(texto: '${_rotulos[t] ?? ''}'.toUpperCase())),
          ]),
        ),
        Container(
          padding: const EdgeInsets.fromLTRB(14, 16, 14, 16),
          decoration: _cartaoPergunta(),
          child: Row(children: [
            const Icon(Icons.insights_rounded, color: Colors.white, size: 34),
            const SizedBox(width: 12),
            Expanded(child: Text('${ex['pergunta']}', style: const TextStyle(fontSize: 18, height: 1.3, fontWeight: FontWeight.w800, color: Colors.white))),
          ]),
        ),
        const SizedBox(height: 16),
        ..._opcoesDe(ex, null),
      ],
    );
  }

  BoxDecoration _cartaoPergunta() => BoxDecoration(
        borderRadius: BorderRadius.circular(20),
        gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF16306E), Color(0xFF0B1A47)]),
        border: Border.all(color: const Color(0xFF3FA8FF), width: 2.2),
        boxShadow: const [BoxShadow(color: Color(0x663FA8FF), blurRadius: 14)],
      );

  /// As opções da pergunta. Com a correção (`r`), pinta a certa de verde e a escolhida errada de vermelho, e trava tudo.
  List<Widget> _opcoesDe(Map ex, Map? r) {
    final t = ex['tipo'];
    final travado = r != null;
    final certa = '${r?['certa'] ?? ''}';
    String? estado(String texto, bool escolhida) {
      if (!travado) return escolhida ? 'sel' : null;
      if (texto == certa) return 'certa';
      if (escolhida) return 'errada';
      return 'apagada';
    }

    if (t == 'escolha' || t == 'completar') {
      return [
        for (final (i, o) in ((ex['opcoes'] as List?) ?? const []).indexed) _opcao('$o', estado('$o', _escolha == i), travado ? null : () => setState(() => _escolha = i)),
      ];
    }
    if (t == 'vf') {
      return [
        Row(children: [
          Expanded(child: _opcao('Verdadeiro', estado('Verdadeiro', _vf == true), travado ? null : () => setState(() => _vf = true))),
          const SizedBox(width: 10),
          Expanded(child: _opcao('Falso', estado('Falso', _vf == false), travado ? null : () => setState(() => _vf = false))),
        ]),
      ];
    }
    if (t == 'ordenar') return _ordenar(ex, travado);
    if (t == 'pares') return [_paresW(ex, travado)];
    return const [];
  }

  /// Opção: pílula azul com o círculo à esquerda. Estados: null (livre), sel, certa, errada, apagada.
  Widget _opcao(String t, String? estado, VoidCallback? f) {
    final (fundo, borda, brilho) = switch (estado) {
      'sel' => (const [Color(0xFF2A62C8), Color(0xFF173E8A)], const Color(0xFF7FD3FF), const Color(0x887FD3FF)),
      'certa' => (const [Color(0xFF1FB45A), Color(0xFF0E7A3A)], const Color(0xFF6BFF8A), const Color(0x886BFF8A)),
      'errada' => (const [Color(0xFFD93448), Color(0xFF8E1424)], const Color(0xFFFF7A8A), const Color(0x88FF4D6D)),
      'apagada' => (const [Color(0xFF173A7A), Color(0xFF0F2758)], const Color(0xFF2E5AB0), const Color(0x00000000)),
      _ => (const [Color(0xFF1C4AA0), Color(0xFF123276)], const Color(0xFF3FA8FF), const Color(0x443FA8FF)),
    };
    final Widget marca = switch (estado) {
      'certa' => _bolinha(const Color(0xFF16A34A), Icons.check_rounded),
      'errada' => _bolinha(const Color(0xFFE5243B), Icons.close_rounded),
      'sel' => Container(
          width: 28,
          height: 28,
          padding: const EdgeInsets.all(5),
          decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: const Color(0xFF7FD3FF), width: 3)),
          child: Container(decoration: const BoxDecoration(shape: BoxShape.circle, color: Color(0xFF7FD3FF))),
        ),
      'apagada' => const SizedBox(width: 28),
      _ => Container(width: 28, height: 28, decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: const Color(0xFF5BC8FF), width: 3))),
    };
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Pressionavel(
        aoTocar: f,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 13),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(999),
            gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: fundo),
            border: Border.all(color: borda, width: 2),
            boxShadow: [BoxShadow(color: brilho, blurRadius: 12)],
          ),
          child: Row(children: [
            marca,
            const SizedBox(width: 14),
            Expanded(child: Text(t, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w700, color: Colors.white))),
          ]),
        ),
      ),
    );
  }

  Widget _bolinha(Color c, IconData ic) => Container(
        width: 30,
        height: 30,
        decoration: BoxDecoration(shape: BoxShape.circle, color: Colors.white, border: Border.all(color: c, width: 2)),
        child: Container(margin: const EdgeInsets.all(2), decoration: BoxDecoration(shape: BoxShape.circle, color: c), child: Icon(ic, color: Colors.white, size: 18)),
      );

  /// Depois de responder (referências "Que pena!" e acerto): o urso com a faixa, a pergunta, as opções pintadas,
  /// a resposta certa (se errou) e a dica do TickerHunters.
  Widget _resultado(Map ex, Map r) {
    final ok = r['ok'] == true;
    return ListView(
      padding: const EdgeInsets.fromLTRB(14, 0, 14, 16),
      children: [
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: const Duration(milliseconds: 520),
          curve: Curves.easeOutBack,
          builder: (ctx, v, f) => Transform.scale(scale: 0.7 + 0.3 * v, child: Opacity(opacity: v.clamp(0.0, 1.0), child: f)),
          child: ok
              ? Column(children: [
                  Image.asset('assets/aprender/licao_certo_urso.webp', height: 150),
                  Transform.translate(offset: const Offset(0, -18), child: const _Bandeira(titulo: 'MANDOU BEM!', sub: 'Você acertou a questão!', verde: true)),
                ])
              : Image.asset('assets/aprender/licao_erro.webp', height: 210),
        ),
        // etiqueta "ESCOLHA A RESPOSTA" presa no cartão da pergunta
        Align(
          alignment: Alignment.centerLeft,
          child: Container(
            margin: const EdgeInsets.only(left: 12),
            padding: const EdgeInsets.fromLTRB(14, 5, 22, 4),
            decoration: const BoxDecoration(
              borderRadius: BorderRadius.vertical(top: Radius.circular(14)),
              color: Color(0xFF16306E),
              border: Border(top: BorderSide(color: Color(0xFF3FA8FF), width: 2), left: BorderSide(color: Color(0xFF3FA8FF), width: 2), right: BorderSide(color: Color(0xFF3FA8FF), width: 2)),
            ),
            child: Text('${_rotulos[ex['tipo']] ?? ''}'.toUpperCase(),
                style: const TextStyle(fontSize: 13, letterSpacing: 0.5, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Color(0xFF5BE0FF))),
          ),
        ),
        Container(
          padding: const EdgeInsets.fromLTRB(8, 10, 12, 10),
          decoration: _cartaoPergunta(),
          child: Row(children: [
            ClipRRect(borderRadius: BorderRadius.circular(12), child: Image.asset('assets/aprender/licao_urso_pergunta.webp', width: 62, height: 56, fit: BoxFit.cover)),
            const SizedBox(width: 10),
            Expanded(child: Text('${ex['pergunta']}', style: const TextStyle(fontSize: 16, height: 1.3, fontWeight: FontWeight.w700, color: Colors.white))),
          ]),
        ),
        const SizedBox(height: 12),
        ..._opcoesDe(ex, r),
        if (!ok) ...[
          const SizedBox(height: 4),
          _cartaoDica(const Text('💡', style: TextStyle(fontSize: 34)), 'Resposta Correta:', '${r['certa']}'),
        ],
        if ('${r['explicacao']}'.isNotEmpty) _cartaoDica(const Icon(Icons.school_rounded, color: Color(0xFFF7C84A), size: 36), 'Dica do TickerHunters:', '${r['explicacao']}'),
        if (!ok)
          const Padding(
            padding: EdgeInsets.only(top: 2),
            child: Text('Essa pergunta volta no fim da lição.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12.5, color: _lilas)),
          ),
      ],
    );
  }

  Widget _cartaoDica(Widget icone, String titulo, String texto) => Container(
        margin: const EdgeInsets.only(bottom: 10),
        padding: const EdgeInsets.fromLTRB(12, 12, 14, 12),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1A3A80), Color(0xFF0E2257)]),
          border: Border.all(color: const Color(0xFF6C8BFF), width: 1.8),
          boxShadow: const [BoxShadow(color: Color(0x556C8BFF), blurRadius: 12)],
        ),
        child: Row(children: [
          SizedBox(width: 50, child: Center(child: icone)),
          const SizedBox(width: 8),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(titulo, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Color(0xFFF7C84A))),
              const SizedBox(height: 2),
              Text(texto, style: const TextStyle(fontSize: 14.5, height: 1.35, color: Colors.white)),
            ]),
          ),
        ]),
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
          border: Border.all(color: const Color(0xFF4F88E6), width: 1.5),
          color: const Color(0x22143362),
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
            for (final (k, i) in _ordem.indexed) ActionChip(label: Text('${k + 1}. $i'), backgroundColor: const Color(0xFF2A579E), onPressed: travado ? null : () => setState(() => _ordem.remove(i))),
          ],
        ),
      ),
      const SizedBox(height: 12),
      Wrap(
        spacing: 8,
        runSpacing: 8,
        children: [for (final i in sobra) ActionChip(label: Text(i), backgroundColor: const Color(0xFF143362), onPressed: travado ? null : () => setState(() => _ordem.add(i)))],
      ),
    ];
  }

  Widget _paresW(Map ex, bool travado) {
    final esq = ((ex['esquerda'] as List?) ?? const []).cast<String>();
    final dir = ((ex['direita'] as List?) ?? const []).cast<String>();
    const cores = [Color(0xFF26D07C), Color(0xFF38B6FF), Color(0xFFF2B84B), Color(0xFFFF6AD5), Color(0xFF9BBFFF)];
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
                color: cor?.withValues(alpha: 0.22) ?? (sel ? const Color(0xFF2A579E) : const Color(0xFF143362)),
                border: Border.all(color: cor ?? (sel ? const Color(0xFF9BBFFF) : const Color(0xFF3B66AA)), width: 2),
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
        padding: const EdgeInsets.fromLTRB(30, 6, 30, 14),
        child: _BotaoJogo(
          texto: 'VERIFICAR',
          icone: Icons.check_rounded,
          cores: const [Color(0xFF6BFF5A), Color(0xFF12A83C)],
          sombra: const Color(0xFF0B6B26),
          letra: Colors.white,
          ocupado: _ocupado,
          aoTocar: pode ? _verificar : null,
        ),
      );
    }
    final ok = r['ok'] == true;
    return Padding(
      padding: const EdgeInsets.fromLTRB(30, 6, 30, 14),
      child: _BotaoJogo(
        texto: 'CONTINUAR',
        iconeDepois: Icons.play_arrow_rounded,
        cores: ok ? const [Color(0xFF6BFF5A), Color(0xFF12A83C)] : const [Color(0xFFFFE27A), Color(0xFFF5A623)],
        sombra: ok ? const Color(0xFF0B6B26) : const Color(0xFF8A4E00),
        letra: ok ? Colors.white : const Color(0xFF3B2600),
        aoTocar: _continuar,
      ),
    );
  }
}

/// Botão grande de jogo (VERIFICAR / CONTINUAR): pílula com degradê, degrau escuro embaixo, brilho e reflexo.
class _BotaoJogo extends StatelessWidget {
  const _BotaoJogo({required this.texto, required this.cores, required this.sombra, required this.letra, this.aoTocar, this.icone, this.iconeDepois, this.ocupado = false});
  final String texto;
  final List<Color> cores;
  final Color sombra, letra;
  final VoidCallback? aoTocar;
  final IconData? icone, iconeDepois;
  final bool ocupado;

  @override
  Widget build(BuildContext context) {
    final ativo = aoTocar != null;
    return Opacity(
      opacity: ativo || ocupado ? 1 : 0.45,
      child: Pressionavel(
        aoTocar: aoTocar,
        child: Reflexo(
          raio: 999,
          child: Container(
            height: 62,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(999),
              gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: cores),
              border: Border.all(color: Color.lerp(cores.first, Colors.white, 0.5)!, width: 2.5),
              boxShadow: [BoxShadow(color: sombra, offset: const Offset(0, 5)), BoxShadow(color: cores.last.withValues(alpha: 0.55), blurRadius: 18)],
            ),
            child: Center(
              child: ocupado
                  ? SizedBox(width: 26, height: 26, child: CircularProgressIndicator(strokeWidth: 3, color: letra))
                  : Row(mainAxisSize: MainAxisSize.min, children: [
                      if (icone != null) ...[
                        Container(
                          width: 34,
                          height: 34,
                          decoration: const BoxDecoration(shape: BoxShape.circle, color: Colors.white),
                          child: Icon(icone, color: cores.last, size: 26),
                        ),
                        const SizedBox(width: 12),
                      ],
                      Text(texto,
                          style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, letterSpacing: 1, color: letra, shadows: const [
                            Shadow(color: Color(0x66000000), offset: Offset(0, 2)),
                          ])),
                      if (iconeDepois != null) ...[const SizedBox(width: 6), Icon(iconeDepois, color: letra, size: 32)],
                    ]),
            ),
          ),
        ),
      ),
    );
  }
}

/// Etiqueta inclinada "ESCOLHA A RESPOSTA" (fundo escuro, letras douradas em itálico, riscos no fim).
class _Etiqueta extends StatelessWidget {
  const _Etiqueta({required this.texto});
  final String texto;

  @override
  Widget build(BuildContext context) => Transform(
        transform: Matrix4.skewX(-0.25),
        child: Container(
          padding: const EdgeInsets.fromLTRB(16, 8, 26, 8),
          decoration: BoxDecoration(
            gradient: const LinearGradient(colors: [Color(0xFF0B1638), Color(0xFF1A2E6E), Color(0xFF3B5BD6)], stops: [0, 0.75, 1]),
            border: Border.all(color: const Color(0xFF6C8BFF), width: 1.5),
            boxShadow: const [BoxShadow(color: Color(0x886C8BFF), blurRadius: 12)],
          ),
          child: Transform(
            transform: Matrix4.skewX(0.25),
            child: FittedBox(
              fit: BoxFit.scaleDown,
              alignment: Alignment.centerLeft,
              child: Text(texto,
                  style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, letterSpacing: 0.6, color: Color(0xFFFFD34A), shadows: [
                    Shadow(color: Color(0xFF3B2600), offset: Offset(0, 2)),
                  ])),
            ),
          ),
        ),
      );
}

/// Faixa inclinada com título grande (acerto: verde; o erro usa a arte "QUE PENA!").
class _Bandeira extends StatelessWidget {
  const _Bandeira({required this.titulo, required this.sub, this.verde = false});
  final String titulo, sub;
  final bool verde;

  @override
  Widget build(BuildContext context) => Column(children: [
        Transform(
          alignment: Alignment.center,
          transform: Matrix4.skewX(-0.18)..rotateZ(-0.04),
          child: Container(
            padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 6),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              gradient:
                  LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: verde ? const [Color(0xFF3FE07A), Color(0xFF0E7A3A)] : const [Color(0xFFE5243B), Color(0xFF8E1424)]),
              border: Border.all(color: Colors.white, width: 3),
              boxShadow: [BoxShadow(color: (verde ? const Color(0xFF2EE88A) : const Color(0xFFFF4D6D)).withValues(alpha: 0.6), blurRadius: 18)],
            ),
            child: Transform(
              transform: Matrix4.skewX(0.18),
              child: _titulo3d(titulo, 38, const [Colors.white, Color(0xFFE6FFE9)]),
            ),
          ),
        ),
        const SizedBox(height: 4),
        Transform.rotate(angle: -0.04, child: Text(sub, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w800, fontStyle: FontStyle.italic, color: Colors.white))),
      ]);
}

/// Título de jogo: letras grossas em itálico com degradê, contorno escuro e sombra.
Widget _titulo3d(String t, double tam, List<Color> cores) {
  final estilo = TextStyle(fontSize: tam, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, height: 1.05);
  return Stack(children: [
    Text(t,
        style: estilo.copyWith(
            shadows: const [Shadow(color: Color(0xAA000000), offset: Offset(0, 3), blurRadius: 3)],
            foreground: Paint()
              ..style = PaintingStyle.stroke
              ..strokeWidth = tam / 6
              ..strokeJoin = StrokeJoin.round
              ..color = const Color(0xFF14102E))),
    ShaderMask(
      blendMode: BlendMode.srcIn,
      shaderCallback: (r) => LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: cores).createShader(r),
      child: Text(t, style: estilo.copyWith(color: Colors.white)),
    ),
  ]);
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
    final titulo = f['revisao'] == true ? 'Revisão concluída!' : (f['perfeita'] == true ? 'Lição perfeita!' : 'Lição concluída!');
    return AnimatedBuilder(
      animation: _c,
      builder: (ctx, _) {
        final t = _c.value;
        double fase(double a, double b) => Curves.easeOutBack.transform(((t - a) / (b - a)).clamp(0.0, 1.0));
        return Stack(children: [
          Positioned.fill(child: IgnorePointer(child: CustomPaint(painter: _Confete(_conf, t)))),
          ListView(padding: const EdgeInsets.fromLTRB(16, 8, 16, 20), children: [
            // urso comemorando e a faixa com o título
            Transform.scale(scale: Curves.elasticOut.transform((t / 0.45).clamp(0.0, 1.0)), child: Image.asset('assets/aprender/licao_certo_urso.webp', height: 210)),
            Transform.translate(
              offset: const Offset(0, -34),
              child: Transform.scale(
                scale: fase(0.15, 0.5),
                child: SizedBox(
                  height: 112,
                  child: Stack(alignment: Alignment.center, clipBehavior: Clip.none, children: [
                    Positioned.fill(top: 22, child: CustomPaint(painter: _FaixaCurva())),
                    // medalha com a estrela no topo da faixa
                    Positioned(
                      top: 0,
                      child: Container(
                        width: 46,
                        height: 46,
                        decoration: BoxDecoration(
                          shape: BoxShape.circle,
                          gradient: const RadialGradient(colors: [Color(0xFFFFE27A), Color(0xFFE09A1E)]),
                          border: Border.all(color: const Color(0xFF8A4E00), width: 2.5),
                          boxShadow: const [BoxShadow(color: Color(0xAAFFC93C), blurRadius: 16)],
                        ),
                        child: const Icon(Icons.star_rounded, color: Color(0xFFFFF6D0), size: 32),
                      ),
                    ),
                    Padding(
                      padding: const EdgeInsets.only(top: 34),
                      child: FittedBox(child: _titulo3d(titulo, 44, const [Color(0xFFFFF3B0), Color(0xFFFFD34A), Color(0xFFF5A623)])),
                    ),
                  ]),
                ),
              ),
            ),
            Transform.translate(
              offset: const Offset(0, -26),
              child: Column(children: [
                Text.rich(
                  TextSpan(children: [
                    TextSpan(text: f['perfeita'] == true ? 'Você acertou ' : 'Você finalizou '),
                    const TextSpan(text: 'todas', style: TextStyle(color: Color(0xFFFFD34A))),
                    TextSpan(text: f['perfeita'] == true ? ' as questões de primeira!' : ' as questões desta lição!'),
                  ]),
                  textAlign: TextAlign.center,
                  style: const TextStyle(fontSize: 19, fontWeight: FontWeight.w800, fontStyle: FontStyle.italic, color: Colors.white),
                ),
                Text('${f['acertos_primeira']} de ${f['total']} de primeira', style: const TextStyle(fontSize: 12.5, color: _lilas)),
                const SizedBox(height: 14),
                Row(children: [
                  _quadro(
                      const Text('⭐', style: TextStyle(fontSize: 30)), const Color(0xFFFFC93C), '+${(xp * Curves.easeOut.transform(((t - 0.3) / 0.4).clamp(0.0, 1.0))).round()}', 'XP', fase(0.3, 0.6)),
                  const SizedBox(width: 8),
                  _quadro(
                      const Text('🔥', style: TextStyle(fontSize: 30)), const Color(0xFFFF8A3D), '${f['ofensiva'] ?? 0}', (f['ofensiva'] ?? 0) == 1 ? 'dia seguido' : 'dias seguidos', fase(0.4, 0.7)),
                  const SizedBox(width: 8),
                  _quadro(Image.asset('assets/home/ic_moeda.webp', height: 34), const Color(0xFFB88BFF), tc > 0 ? '+$tc' : '0', 'Ticker Coins', fase(0.5, 0.8)),
                ]),
                const SizedBox(height: 12),
                if (f['meta_nova'] == true) _faixa('🎯', 'Meta do dia batida!', 'Você é um verdadeiro investidor!', fase(0.6, 0.9)),
                if (subiu) _faixa('⬆️', 'Nível ${f['nivel_depois']}!', 'Você subiu de nível. Continue assim!', fase(0.65, 0.95)),
                for (final c in conq) _faixa('🏅', 'Conquista nova!', c, fase(0.7, 1)),
                const SizedBox(height: 10),
                _BotaoJogo(
                  texto: 'CONTINUAR',
                  icone: Icons.play_arrow_rounded,
                  cores: const [Color(0xFF6BFF5A), Color(0xFF12A83C)],
                  sombra: const Color(0xFF0B6B26),
                  letra: Colors.white,
                  aoTocar: widget.aoFechar,
                ),
                const SizedBox(height: 18),
                Row(children: [
                  const Expanded(child: Divider(color: Color(0x88F7C84A), indent: 10, endIndent: 8)),
                  const Icon(Icons.bar_chart_rounded, color: Color(0xFF5BC8FF), size: 34),
                  const SizedBox(width: 6),
                  Text.rich(
                    const TextSpan(children: [
                      TextSpan(text: 'Continue estudando e evoluindo\ncom o '),
                      TextSpan(text: 'TickerHunters!', style: TextStyle(color: Color(0xFFFFD34A))),
                    ]),
                    style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w800, fontStyle: FontStyle.italic, color: Colors.white),
                  ),
                  const Expanded(child: Divider(color: Color(0x88F7C84A), indent: 8, endIndent: 10)),
                ]),
              ]),
            ),
          ]),
        ]);
      },
    );
  }

  Widget _quadro(Widget ic, Color c, String v, String t, double e) => Expanded(
        child: Transform.scale(
          scale: e,
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 12),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(16),
              gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF16306E), Color(0xFF0B1A47)]),
              border: Border.all(color: c, width: 2.4),
              boxShadow: [BoxShadow(color: c.withValues(alpha: 0.5), blurRadius: 14)],
            ),
            child: Column(children: [
              SizedBox(height: 36, child: Center(child: ic)),
              FittedBox(child: Text(v, style: TextStyle(fontSize: 30, fontWeight: FontWeight.w900, color: c, shadows: const [Shadow(color: Colors.black54, offset: Offset(0, 2))]))),
              Text(t, textAlign: TextAlign.center, style: const TextStyle(fontSize: 13, fontWeight: FontWeight.w700, color: Colors.white)),
            ]),
          ),
        ),
      );

  Widget _faixa(String emoji, String titulo, String sub, double e) => Transform.scale(
        scale: e,
        child: Container(
          margin: const EdgeInsets.only(bottom: 10),
          padding: const EdgeInsets.fromLTRB(14, 12, 14, 12),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(22),
            gradient: const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF1A3A80), Color(0xFF0E2257)]),
            border: Border.all(color: const Color(0xFF6C8BFF), width: 2),
            boxShadow: const [BoxShadow(color: Color(0x556C8BFF), blurRadius: 14)],
          ),
          child: Row(children: [
            Text(emoji, style: const TextStyle(fontSize: 46)),
            const SizedBox(width: 14),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(titulo, style: const TextStyle(fontSize: 21, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white)),
                Text(sub, style: const TextStyle(fontSize: 14, fontStyle: FontStyle.italic, color: Color(0xFFC9D8FF))),
              ]),
            ),
          ]),
        ),
      );
}

/// Faixa curva atrás do título da conclusão: arco azul-marinho com borda dourada e brilho.
class _FaixaCurva extends CustomPainter {
  @override
  void paint(Canvas c, Size s) {
    final w = s.width, h = s.height;
    final p = Path()
      ..moveTo(0, h * 0.22)
      ..quadraticBezierTo(w / 2, -h * 0.12, w, h * 0.22)
      ..lineTo(w - 14, h * 0.62)
      ..lineTo(w, h * 0.98)
      ..quadraticBezierTo(w / 2, h * 0.62, 0, h * 0.98)
      ..lineTo(14, h * 0.62)
      ..close();
    c.drawShadow(p, const Color(0xFFB06BFF), 10, true);
    c.drawPath(p, Paint()..shader = const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFF2A4BB8), Color(0xFF14286A)]).createShader(Offset.zero & s));
    c.drawPath(
        p,
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = 3
          ..shader = const LinearGradient(colors: [Color(0xFFB06BFF), Color(0xFFFFD34A), Color(0xFFB06BFF)]).createShader(Offset.zero & s));
  }

  @override
  bool shouldRepaint(covariant CustomPainter oldDelegate) => false;
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
