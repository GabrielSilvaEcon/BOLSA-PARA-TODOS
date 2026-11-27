import 'dart:math';

import 'package:flutter/material.dart';

/// Confete de comemoração: uma chuva curta de papeizinhos (uma passada de ~2,8 s e some). Leve: um único controlador e uma pintura só.
/// Para quem desligou as animações do aparelho, não aparece.
class ConfeteLeve extends StatefulWidget {
  const ConfeteLeve({super.key, this.quantidade = 38, this.duracao = const Duration(milliseconds: 2800)});
  final int quantidade;
  final Duration duracao;

  static const cores = [Color(0xFF26D07C), Color(0xFFF2B84B), Color(0xFFFF6AD5), Color(0xFF4FC3FF), Color(0xFFFFE08A)];

  @override
  State<ConfeteLeve> createState() => _ConfeteLeveState();
}

class _ConfeteLeveState extends State<ConfeteLeve> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.duracao);
  late final List<(double, double, double, Color)> _p = [
    for (var i = 0; i < widget.quantidade; i++) (Random(i).nextDouble(), Random(i * 7 + 3).nextDouble(), Random(i * 13 + 5).nextDouble(), ConfeteLeve.cores[i % ConfeteLeve.cores.length]),
  ];
  bool _iniciou = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_iniciou) {
      _iniciou = true;
      if (!MediaQuery.of(context).disableAnimations) _c.forward();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => IgnorePointer(
        child: RepaintBoundary(
          child: AnimatedBuilder(animation: _c, builder: (ctx, _) => _c.value == 0 || _c.isCompleted ? const SizedBox.expand() : CustomPaint(size: Size.infinite, painter: _Pintura(_p, _c.value))),
        ),
      );
}

class _Pintura extends CustomPainter {
  _Pintura(this.p, this.t);
  final List<(double, double, double, Color)> p;
  final double t;

  @override
  void paint(Canvas c, Size s) {
    for (final (x, v, g, cor) in p) {
      final y = (-0.08 + t * (0.75 + v * 0.6)) * s.height;
      if (y > s.height) continue;
      c.save();
      c.translate(x * s.width + sin(t * 8 + g * 6) * 14, y);
      c.rotate(t * 10 * (g - 0.5));
      c.drawRect(const Rect.fromLTWH(-4, -7, 8, 14), Paint()..color = cor.withValues(alpha: (1.15 - t).clamp(0.0, 1.0)));
      c.restore();
    }
  }

  @override
  bool shouldRepaint(_Pintura o) => o.t != t;
}
