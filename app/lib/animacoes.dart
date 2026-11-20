import 'dart:math';

import 'package:flutter/material.dart';

/// Pequenas animações reaproveitáveis do app. Todas respeitam "reduzir movimento" do sistema (mostram direto o estado final).

bool _parado(BuildContext c) => MediaQuery.maybeOf(c)?.disableAnimations ?? false;

/// Entra na tela subindo e aparecendo, com atraso pela [ordem] (cartões em sequência).
class Entrada extends StatelessWidget {
  const Entrada({super.key, required this.ordem, required this.child});
  final int ordem;
  final Widget child;

  @override
  Widget build(BuildContext context) {
    if (_parado(context)) return child;
    final atraso = 0.12 * min(ordem, 6);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 520 + (atraso * 1000).round()),
      builder: (ctx, v, f) {
        final t = Curves.easeOutCubic.transform(((v * (1 + atraso) - atraso)).clamp(0.0, 1.0));
        return Opacity(opacity: t, child: Transform.translate(offset: Offset(0, 28 * (1 - t)), child: f));
      },
      child: child,
    );
  }
}

/// Afunda um pouco quando o dedo encosta e volta com mola ao soltar.
class Pressionavel extends StatefulWidget {
  const Pressionavel({super.key, required this.child, required this.aoTocar});
  final Widget child;
  final VoidCallback? aoTocar;

  @override
  State<Pressionavel> createState() => _PressionavelState();
}

class _PressionavelState extends State<Pressionavel> {
  bool _baixo = false;

  @override
  Widget build(BuildContext context) => GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) => setState(() => _baixo = true),
        onTapCancel: () => setState(() => _baixo = false),
        onTapUp: (_) => setState(() => _baixo = false),
        onTap: widget.aoTocar,
        child: AnimatedScale(
          scale: _baixo ? 0.95 : 1,
          duration: Duration(milliseconds: _baixo ? 90 : 260),
          curve: _baixo ? Curves.easeOut : Curves.elasticOut,
          child: widget.child,
        ),
      );
}

/// Reflexo de luz que atravessa o cartão de tempos em tempos (como um brilho passando no vidro).
class Reflexo extends StatefulWidget {
  const Reflexo({super.key, required this.child, this.raio = 18, this.intervalo = const Duration(milliseconds: 3800), this.atraso = Duration.zero});
  final Widget child;
  final double raio;
  final Duration intervalo;
  final Duration atraso;

  @override
  State<Reflexo> createState() => _ReflexoState();
}

class _ReflexoState extends State<Reflexo> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.intervalo);

  @override
  void initState() {
    super.initState();
    Future.delayed(widget.atraso, () {
      if (mounted) _c.repeat();
    });
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_parado(context)) return widget.child;
    return Stack(
      children: [
        widget.child,
        Positioned.fill(
          child: IgnorePointer(
            child: ClipRRect(
              borderRadius: BorderRadius.circular(widget.raio),
              child: AnimatedBuilder(
                animation: _c,
                builder: (ctx, _) {
                  // a faixa passa nos primeiros 30% do ciclo; no resto, descansa fora do cartão
                  final p = (_c.value / 0.3).clamp(0.0, 1.0);
                  final x = -1.6 + 3.2 * Curves.easeInOut.transform(p);
                  return DecoratedBox(
                    decoration: BoxDecoration(
                      gradient: LinearGradient(
                        begin: Alignment(x - 0.5, -1),
                        end: Alignment(x + 0.5, 1),
                        colors: const [Color(0x00FFFFFF), Color(0x40FFFFFF), Color(0x00FFFFFF)],
                        stops: const [0.35, 0.5, 0.65],
                      ),
                    ),
                  );
                },
              ),
            ),
          ),
        ),
      ],
    );
  }
}

/// Moldura que pulsa (brilho que cresce e diminui) em volta do item escolhido.
class Pulso extends StatefulWidget {
  const Pulso({super.key, required this.cor, this.raio = 18, this.largura = 3});
  final Color cor;
  final double raio;
  final double largura;

  @override
  State<Pulso> createState() => _PulsoState();
}

class _PulsoState extends State<Pulso> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1400))..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => AnimatedBuilder(
        animation: _c,
        builder: (ctx, _) {
          final t = _parado(context) ? 0.6 : Curves.easeInOut.transform(_c.value);
          return DecoratedBox(
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(widget.raio),
              border: Border.all(color: widget.cor, width: widget.largura),
              boxShadow: [
                BoxShadow(color: widget.cor.withValues(alpha: 0.35 + 0.4 * t), blurRadius: 10 + 16 * t, spreadRadius: 1 + 2 * t),
              ],
            ),
          );
        },
      );
}

/// Sobe e desce devagar (flutuando), para dar vida a artes paradas.
class Flutua extends StatefulWidget {
  const Flutua({super.key, required this.child, this.altura = 4, this.periodo = const Duration(milliseconds: 2600)});
  final Widget child;
  final double altura;
  final Duration periodo;

  @override
  State<Flutua> createState() => _FlutuaState();
}

class _FlutuaState extends State<Flutua> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.periodo)..repeat(reverse: true);

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_parado(context)) return widget.child;
    return AnimatedBuilder(
      animation: _c,
      builder: (ctx, f) => Transform.translate(offset: Offset(0, -widget.altura * Curves.easeInOut.transform(_c.value)), child: f),
      child: widget.child,
    );
  }
}
