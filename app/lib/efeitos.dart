import 'dart:math';

import 'package:flutter/material.dart';

/// Efeitos de comemoração do app (reaproveitáveis): raios girando, explosão de moedas e brilhos, contador que sobe.
/// Tudo é só apresentação: quem sorteia e credita é o servidor. Com "reduzir movimento" do sistema, mostra direto o estado final.

const rotRaridade = {'comum': 'Comum', 'raro': 'Raro', 'epico': 'Épico', 'lendario': 'Lendário'};
const corRaridade = {'comum': Color(0xFF9FB2C8), 'raro': Color(0xFF4DA3FF), 'epico': Color(0xFFB06BFF), 'lendario': Color(0xFFFFB938)};

/// Carrega antes as imagens da comemoração (para o baú não aparecer em branco no primeiro quadro).
void precarregarEfeitos(BuildContext context) {
  for (final a in ['assets/loja/bau_comum.webp', 'assets/loja/bau_raro.webp', 'assets/loja/bau_epico.webp', 'assets/loja/bau_lendario.webp',
    'assets/loja/tc.webp']) {
    precacheImage(AssetImage(a), context);
  }
}

/// Quantas partículas cada raridade solta (comum é discreto, lendário é festa).
const _particulas = {'comum': 10, 'raro': 16, 'epico': 22, 'lendario': 30};

double _faixa(double t, double a, double b) => ((t - a) / (b - a)).clamp(0.0, 1.0);

/// Baú abrindo DENTRO do cartão, com o "Você ganhou!" fazendo parte da animação (sem pop-up):
///   1. o baú treme e a luz da raridade vaza por trás;
///   2. clarão, os raios começam a girar e moedas e brilhos explodem para fora;
///   3. o baú vai para a esquerda, "Você ganhou!" aparece e o prêmio entra à direita com a moeda girando e o número subindo;
///   4. por último, o nome do baú e a raridade.
/// [animar] falso (baú já aberto antes) mostra o resultado parado, só com os raios girando devagar.
class BauAnimado extends StatefulWidget {
  const BauAnimado({super.key, required this.raridade, required this.valor, this.rotulo = 'Ticker Coins', this.animar = true, this.titulo});
  final String raridade;
  final int valor;
  final String rotulo;
  final bool animar;

  /// Nome do baú no fim (padrão: "Baú Épico aberto!").
  final String? titulo;

  @override
  State<BauAnimado> createState() => _BauAnimadoState();
}

class _BauAnimadoState extends State<BauAnimado> with TickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 3600));
  late final AnimationController _giro = AnimationController(vsync: this, duration: const Duration(seconds: 14))..repeat();
  late final List<_Particula> _ps = _gerar();

  String get _r => rotRaridade.containsKey(widget.raridade) ? widget.raridade : 'comum';

  List<_Particula> _gerar() {
    final rnd = Random(widget.valor * 31 + _r.length);
    final n = _particulas[_r]!;
    return [
      for (var i = 0; i < n; i++)
        _Particula(
          angulo: -pi / 2 + (rnd.nextDouble() - 0.5) * pi * 1.5,
          forca: 90 + rnd.nextDouble() * 110,
          giro: (rnd.nextDouble() - 0.5) * 8,
          moeda: i % 3 != 2,
          tam: 14 + rnd.nextDouble() * 14,
          atraso: rnd.nextDouble() * 0.06,
        ),
    ];
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final parado = !widget.animar || MediaQuery.of(context).disableAnimations;
    if (parado) {
      _c.value = 1;
    } else if (!_c.isAnimating && _c.value == 0) {
      _c.forward();
    }
  }

  @override
  void dispose() {
    _c.dispose();
    _giro.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cor = corRaridade[_r]!;
    return AnimatedBuilder(
      animation: Listenable.merge([_c, _giro]),
      builder: (ctx, _) {
        final t = _c.value;
        final treme = _faixa(t, 0.0, 0.30);
        final clarao = t < 0.30 ? 0.0 : (1 - (_faixa(t, 0.30, 0.42) - 0.35).abs() / 0.65).clamp(0.0, 1.0);
        final explode = _faixa(t, 0.32, 0.80);
        final recua = Curves.easeInOutCubic.transform(_faixa(t, 0.40, 0.58));
        final titulo = Curves.elasticOut.transform(_faixa(t, 0.46, 0.70));
        final premio = Curves.easeOutCubic.transform(_faixa(t, 0.62, 0.82));
        final numero = Curves.easeOutExpo.transform(_faixa(t, 0.64, 0.92));
        final nome = Curves.easeOutBack.transform(_faixa(t, 0.82, 0.98));
        final raios = Curves.easeOut.transform(_faixa(t, 0.30, 0.55));
        final luz = 0.25 + 0.75 * max(treme, raios);

        return Container(
          clipBehavior: Clip.antiAlias,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: cor, width: 2),
            gradient: RadialGradient(
              center: const Alignment(0, -0.5),
              radius: 1.25,
              colors: [Color.lerp(const Color(0xFF2A1E86), cor, 0.30 * luz)!, const Color(0xFF15104F), const Color(0xFF0D0A33)],
              stops: const [0, 0.55, 1],
            ),
            boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.25 + 0.35 * luz), blurRadius: 18 + 16 * luz)],
          ),
          child: Stack(
            children: [
              // raios de luz girando atrás de tudo
              Positioned.fill(
                child: Opacity(
                  opacity: (0.18 + 0.5 * raios).clamp(0.0, 1.0),
                  child: CustomPaint(painter: _Raios(cor: cor, angulo: _giro.value * 2 * pi, centro: const Alignment(0, -0.42))),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(14, 14, 14, 16),
                child: Column(
                  children: [
                    // "Você ganhou!" (entra com pulo elástico)
                    SizedBox(
                      height: 44,
                      child: Opacity(
                        opacity: _faixa(t, 0.46, 0.56),
                        child: Transform.scale(
                          scale: 0.4 + 0.6 * titulo,
                          child: const Text.rich(
                            TextSpan(children: [
                              TextSpan(text: 'Você '),
                              TextSpan(text: 'ganhou!', style: TextStyle(color: Color(0xFF5BF5A0))),
                            ]),
                            style: TextStyle(
                              fontSize: 30,
                              fontWeight: FontWeight.w900,
                              fontStyle: FontStyle.italic,
                              color: Color(0xFFEDE9FF),
                              shadows: [Shadow(color: Color(0x995BF5A0), blurRadius: 14)],
                            ),
                          ),
                        ),
                      ),
                    ),
                    SizedBox(
                      height: 168,
                      child: LayoutBuilder(
                        builder: (ctx, c) {
                          final w = c.maxWidth;
                          // o baú começa no meio e vai para a esquerda; o prêmio entra à direita (os dois lado a lado, centralizados)
                          final bauX = w / 2 - (w / 2 - w * 0.33) * recua;
                          final bauEscala = (0.85 + 0.25 * treme + 0.2 * clarao) * (1 - 0.12 * recua);
                          final balanco = treme < 1 ? sin(t * 70) * 0.10 * treme : 0.0;
                          return Stack(
                            clipBehavior: Clip.none,
                            children: [
                              // luz da raridade vazando atrás do baú
                              Positioned(
                                left: bauX - 90,
                                top: 84 - 90,
                                child: Container(
                                  width: 180,
                                  height: 180,
                                  decoration: BoxDecoration(
                                    shape: BoxShape.circle,
                                    gradient: RadialGradient(colors: [cor.withValues(alpha: 0.75 * luz * (1 - 0.5 * recua)), cor.withValues(alpha: 0)]),
                                  ),
                                ),
                              ),
                              // baú
                              Positioned(
                                left: bauX - 60,
                                top: 84 - 60,
                                child: Transform.rotate(
                                  angle: balanco,
                                  child: Transform.scale(scale: bauEscala, child: Image.asset('assets/loja/bau_$_r.webp', width: 120, height: 120)),
                                ),
                              ),
                              // prêmio: moeda girando e número subindo
                              Positioned(
                                left: w * 0.67 - w * 0.17,
                                top: 22,
                                width: w * 0.34,
                                child: Opacity(
                                  opacity: premio,
                                  child: Transform.translate(
                                    offset: Offset(50 * (1 - premio), 0),
                                    child: Column(
                                      children: [
                                        Transform(
                                          alignment: Alignment.center,
                                          transform: Matrix4.identity()..rotateY((1 - numero) * pi * 4),
                                          child: Image.asset('assets/loja/tc.webp', height: 56),
                                        ),
                                        FittedBox(
                                          child: Text(
                                            '+${(widget.valor * numero).round()}',
                                            style: const TextStyle(
                                              fontSize: 44,
                                              fontWeight: FontWeight.w900,
                                              color: Color(0xFFFFD66B),
                                              shadows: [Shadow(color: Color(0x88000000), offset: Offset(0, 2))],
                                            ),
                                          ),
                                        ),
                                        Text(widget.rotulo,
                                            textAlign: TextAlign.center,
                                            style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: Color(0xFFBDB5E6))),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                              // explosão de moedas e brilhos saindo do baú
                              if (explode > 0 && explode < 1)
                                for (final p in _ps) _particula(p, explode, Offset(w / 2, 84), cor),
                              // clarão
                              if (clarao > 0)
                                Positioned.fill(
                                  child: IgnorePointer(
                                    child: DecoratedBox(
                                      decoration: BoxDecoration(
                                        gradient: RadialGradient(
                                          center: const Alignment(0, 0),
                                          radius: 0.8,
                                          colors: [Colors.white.withValues(alpha: 0.85 * clarao), cor.withValues(alpha: 0.3 * clarao), Colors.transparent],
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                            ],
                          );
                        },
                      ),
                    ),
                    const SizedBox(height: 4),
                    Opacity(
                      opacity: nome.clamp(0.0, 1.0),
                      child: Transform.translate(
                        offset: Offset(0, 16 * (1 - nome)),
                        child: Column(
                          children: [
                            Text(widget.titulo ?? 'Baú ${rotRaridade[_r]} aberto!',
                                textAlign: TextAlign.center, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900, color: Color(0xFFFFD66B))),
                            const SizedBox(height: 6),
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 3),
                              decoration: BoxDecoration(
                                borderRadius: BorderRadius.circular(999),
                                gradient: LinearGradient(colors: [cor, Color.lerp(cor, Colors.black, 0.35)!]),
                                border: Border.all(color: Color.lerp(cor, Colors.white, 0.5)!),
                                boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.6), blurRadius: 12)],
                              ),
                              child: Text(rotRaridade[_r]!.toUpperCase(),
                                  style: const TextStyle(fontSize: 11.5, letterSpacing: 1.2, fontWeight: FontWeight.w900, color: Colors.white)),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        );
      },
    );
  }

  Widget _particula(_Particula p, double e, Offset origem, Color cor) {
    final k = ((e - p.atraso) / (1 - p.atraso)).clamp(0.0, 1.0);
    final dx = cos(p.angulo) * p.forca * k;
    final dy = sin(p.angulo) * p.forca * k + 160 * k * k; // sobe e cai (gravidade)
    final alfa = (1 - k).clamp(0.0, 1.0);
    return Positioned(
      left: origem.dx + dx - p.tam / 2,
      top: origem.dy + dy - p.tam / 2,
      child: Opacity(
        opacity: alfa,
        child: Transform.rotate(
          angle: p.giro * k,
          child: p.moeda
              ? Image.asset('assets/loja/tc.webp', width: p.tam, height: p.tam)
              : Icon(Icons.auto_awesome, size: p.tam, color: Color.lerp(Colors.white, cor, 0.4)),
        ),
      ),
    );
  }
}

class _Particula {
  _Particula({required this.angulo, required this.forca, required this.giro, required this.moeda, required this.tam, required this.atraso});
  final double angulo, forca, giro, tam, atraso;
  final bool moeda;
}

/// Leque de raios de luz saindo de um ponto, girando.
class _Raios extends CustomPainter {
  _Raios({required this.cor, required this.angulo, required this.centro});
  final Color cor;
  final double angulo;
  final Alignment centro;

  @override
  void paint(Canvas canvas, Size s) {
    final c = centro.alongSize(s);
    final r = s.longestSide;
    const n = 14;
    final p = Paint()
      ..shader = RadialGradient(colors: [cor.withValues(alpha: 0.55), cor.withValues(alpha: 0)]).createShader(Rect.fromCircle(center: c, radius: r * 0.7));
    for (var i = 0; i < n; i++) {
      final a = angulo + i * 2 * pi / n;
      final path = Path()
        ..moveTo(c.dx, c.dy)
        ..lineTo(c.dx + cos(a - 0.07) * r, c.dy + sin(a - 0.07) * r)
        ..lineTo(c.dx + cos(a + 0.07) * r, c.dy + sin(a + 0.07) * r)
        ..close();
      canvas.drawPath(path, p);
    }
  }

  @override
  bool shouldRepaint(_Raios o) => o.angulo != angulo || o.cor != cor;
}
