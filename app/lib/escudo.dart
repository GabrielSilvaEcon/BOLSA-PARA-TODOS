import 'dart:math';

import 'package:flutter/material.dart';

import 'api.dart';
import 'social.dart';

/// Escudo de uma divisão (Bronze, Prata, Ouro, Platina, Diamante e Lenda). Se existir a arte em assets/ranking/<id>.webp ela é
/// usada; enquanto não existir, o escudo é desenhado aqui, na cor da divisão, com o ícone e o número de estrelas do nível.
class Escudo extends StatelessWidget {
  const Escudo({super.key, required this.id, required this.cor, this.tamanho = 48, this.nivel = 0});
  final String id;
  final Color cor;
  final double tamanho;
  final int nivel;

  static Color corDe(Object? hex) {
    final s = '${hex ?? ''}'.replaceFirst('#', '');
    final v = s.length == 6 ? int.tryParse(s, radix: 16) : null;
    return v == null ? const Color(0xFFCD7F32) : Color(0xFF000000 | v);
  }

  /// Escudo de um mapa {id, cor, nivel} que o servidor manda.
  static Widget de(Map? d, {double tamanho = 48}) => Escudo(id: '${d?['id'] ?? 'bronze'}', cor: corDe(d?['cor']), nivel: (d?['nivel'] as num?)?.toInt() ?? 0, tamanho: tamanho);

  @override
  Widget build(BuildContext context) => SizedBox(
        width: tamanho,
        height: tamanho,
        child: Image.asset('assets/ranking/$id.webp', fit: BoxFit.contain, errorBuilder: (_, __, ___) => CustomPaint(painter: _Desenho(cor, nivel))),
      );
}

class _Desenho extends CustomPainter {
  _Desenho(this.cor, this.nivel);
  final Color cor;
  final int nivel;

  Path _forma(Size s, double m) {
    final w = s.width, h = s.height;
    return Path()
      ..moveTo(w * 0.5, h * 0.04 + m)
      ..lineTo(w * 0.92 - m, h * 0.18 + m)
      ..quadraticBezierTo(w * 0.92 - m, h * 0.68, w * 0.5, h * 0.96 - m)
      ..quadraticBezierTo(w * 0.08 + m, h * 0.68, w * 0.08 + m, h * 0.18 + m)
      ..close();
  }

  @override
  void paint(Canvas c, Size s) {
    final w = s.width;
    c.drawShadow(_forma(s, 0), cor, w * 0.08, false);
    c.drawPath(
        _forma(s, 0),
        Paint()
          ..shader = LinearGradient(begin: Alignment.topLeft, end: Alignment.bottomRight, colors: [Color.lerp(cor, Colors.white, 0.45)!, cor, Color.lerp(cor, Colors.black, 0.45)!])
              .createShader(Offset.zero & s));
    c.drawPath(_forma(s, w * 0.09),
        Paint()..shader = RadialGradient(colors: [Color.lerp(cor, const Color(0xFF2A1A6E), 0.35)!, Color.lerp(cor, const Color(0xFF120850), 0.75)!]).createShader(Offset.zero & s));
    c.drawPath(
        _forma(s, 0),
        Paint()
          ..style = PaintingStyle.stroke
          ..strokeWidth = w * 0.035
          ..color = Colors.white.withValues(alpha: 0.75));
    // coroa no meio
    final cx = w * 0.5, cy = s.height * 0.47, r = w * 0.2;
    final coroa = Path()
      ..moveTo(cx - r, cy + r * 0.55)
      ..lineTo(cx - r, cy - r * 0.35)
      ..lineTo(cx - r * 0.5, cy + r * 0.05)
      ..lineTo(cx, cy - r * 0.65)
      ..lineTo(cx + r * 0.5, cy + r * 0.05)
      ..lineTo(cx + r, cy - r * 0.35)
      ..lineTo(cx + r, cy + r * 0.55)
      ..close();
    c.drawPath(coroa, Paint()..color = Color.lerp(cor, Colors.white, 0.6)!);
    // estrelas do nível (Bronze 0 … Lenda 5)
    final n = nivel.clamp(0, 5);
    for (var i = 0; i < n; i++) {
      final x = cx + (i - (n - 1) / 2) * w * 0.11, y = s.height * 0.75;
      final p = Path();
      for (var k = 0; k < 10; k++) {
        final a = -pi / 2 + k * pi / 5, rr = k.isEven ? w * 0.05 : w * 0.022;
        final o = Offset(x + rr * cos(a), y + rr * sin(a));
        k == 0 ? p.moveTo(o.dx, o.dy) : p.lineTo(o.dx, o.dy);
      }
      c.drawPath(p..close(), Paint()..color = const Color(0xFFFFE08A));
    }
  }

  @override
  bool shouldRepaint(_Desenho o) => o.cor != cor || o.nivel != nivel;
}

/// Troféus ganhos ou perdidos numa partida online, com a divisão atual. Se subiu de divisão, vem com a comemoração.
class TrofeusGanhos extends StatelessWidget {
  const TrofeusGanhos({super.key, required this.t});
  final Map t;

  @override
  Widget build(BuildContext context) {
    final d = (t['delta'] as num?)?.toInt() ?? 0;
    final cor = d >= 0 ? const Color(0xFF26D07C) : const Color(0xFFFF5A7A);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 900),
      curve: Curves.elasticOut,
      builder: (ctx, s, c) => Transform.scale(scale: s, child: c),
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 8),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          color: const Color(0xCC120850),
          border: Border.all(color: t['subiu'] == true ? const Color(0xFFF2B84B) : cor, width: 2),
          boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.5), blurRadius: 16)],
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Row(mainAxisSize: MainAxisSize.min, children: [
            const Icon(Icons.emoji_events_rounded, color: Color(0xFFF2B84B), size: 30),
            const SizedBox(width: 6),
            Text('${d >= 0 ? '+' : ''}$d troféus', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: cor)),
          ]),
          Text(
              t['subiu'] == true
                  ? 'Você subiu para ${t['divisao']}!'
                  : t['caiu'] == true
                      ? 'Você caiu para ${t['divisao']}.'
                      : '${t['t']} troféus · ${t['divisao']}',
              style: TextStyle(fontWeight: FontWeight.w900, color: t['subiu'] == true ? const Color(0xFFF2B84B) : Colors.white)),
        ]),
      ),
    );
  }
}

/// Tela cheia depois de uma partida online (como a arte de referência): VITÓRIA / DERROTA / EMPATE, os troféus ganhos ou
/// perdidos, o escudo e a barra da divisão (subindo ou caindo na hora) e o botão Continuar.
class ResultadoTrofeusTela extends StatelessWidget {
  const ResultadoTrofeusTela({super.key, required this.t, this.api});
  final Map t;
  final Api? api;

  static Future<void> abrir(BuildContext context, Map t, {Api? api}) => Navigator.of(context, rootNavigator: true)
      .push(PageRouteBuilder<void>(opaque: false, pageBuilder: (_, __, ___) => ResultadoTrofeusTela(t: t, api: api), transitionsBuilder: (_, a, __, c) => FadeTransition(opacity: a, child: c)));

  @override
  Widget build(BuildContext context) {
    final d = (t['delta'] as num?)?.toInt() ?? 0;
    final res = '${t['resultado'] ?? (d >= 0 ? 'vitoria' : 'derrota')}';
    final dv = (t['dv'] as Map?) ?? const {};
    final cor = Escudo.corDe(dv['cor']);
    final total = (t['t'] as num?)?.toInt() ?? 0;
    final prox = dv['prox'] as Map?;
    final pct = ((dv['pct'] as num?) ?? 0).toDouble();
    final antes = prox == null ? 1.0 : ((total - d - ((dv['min'] as num?) ?? 0)) / (((prox['min'] as num?) ?? 1) - ((dv['min'] as num?) ?? 0))).clamp(0.0, 1.0).toDouble();
    final (titulo, sub, corT) = switch (res) {
      'vitoria' => ('VITÓRIA!', 'Você mostrou que entende do mercado!', const Color(0xFFFFC93C)),
      'empate' => ('EMPATE', 'Duelo equilibrado. Na próxima, você leva!', const Color(0xFFB9C4FF)),
      _ => ('DERROTA', 'Faz parte. Estude o gráfico e volte mais forte!', const Color(0xFFFF8FA3)),
    };
    return Scaffold(
      backgroundColor: const Color(0xF20B0930),
      body: SafeArea(
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 520),
            child: ListView(padding: const EdgeInsets.fromLTRB(18, 10, 18, 24), shrinkWrap: true, children: [
              if (res == 'vitoria')
                TweenAnimationBuilder<double>(
                  tween: Tween(begin: 0.6, end: 1),
                  duration: const Duration(milliseconds: 900),
                  curve: Curves.elasticOut,
                  builder: (ctx, s, c) => Transform.scale(scale: s, child: c),
                  child: Image.asset('assets/ranking/urso_vitoria.webp', height: 230),
                ),
              const SizedBox(height: 6),
              TweenAnimationBuilder<double>(
                tween: Tween(begin: 0, end: 1),
                duration: const Duration(milliseconds: 700),
                curve: Curves.easeOutBack,
                builder: (ctx, s, c) => Transform.scale(scale: s, child: c),
                child: ShaderMask(
                  shaderCallback: (r) => LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color.lerp(corT, Colors.white, 0.5)!, corT]).createShader(r),
                  child: FittedBox(child: Text(titulo, style: const TextStyle(fontSize: 56, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white))),
                ),
              ),
              Text(sub, textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, fontStyle: FontStyle.italic, color: Colors.white)),
              const SizedBox(height: 18),
              Center(
                child: Container(
                  padding: const EdgeInsets.symmetric(horizontal: 26, vertical: 10),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(18),
                    color: const Color(0xE6160B5E),
                    border: Border.all(color: _ouroT, width: 2),
                    boxShadow: const [BoxShadow(color: Color(0x88F2B84B), blurRadius: 22)],
                  ),
                  child: Row(mainAxisSize: MainAxisSize.min, children: [
                    const Icon(Icons.emoji_events_rounded, color: _ouroT, size: 46),
                    const SizedBox(width: 8),
                    TweenAnimationBuilder<double>(
                      tween: Tween(begin: 0, end: d.toDouble()),
                      duration: const Duration(milliseconds: 1000),
                      builder: (ctx, v, _) =>
                          Text('${d >= 0 ? '+' : ''}${v.round()}', style: TextStyle(fontSize: 52, fontWeight: FontWeight.w900, color: d >= 0 ? const Color(0xFF6BFF8A) : const Color(0xFFFF6B87))),
                    ),
                  ]),
                ),
              ),
              const SizedBox(height: 18),
              Container(
                padding: const EdgeInsets.fromLTRB(10, 10, 14, 12),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(20),
                  color: const Color(0xE6160B5E),
                  border: Border.all(color: cor, width: 2),
                  boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.5), blurRadius: 16)],
                ),
                child: Row(children: [
                  Escudo.de(dv, tamanho: 86),
                  const SizedBox(width: 10),
                  Expanded(
                    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                      Text('${dv['nome'] ?? t['divisao'] ?? ''}', style: TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: Color.lerp(cor, Colors.white, 0.3))),
                      Text(prox == null ? 'Divisão máxima!' : 'Próxima: ${prox['nome']} (${prox['min']} troféus)', style: const TextStyle(fontSize: 12.5, color: Color(0xFFD9D4F7))),
                      const SizedBox(height: 8),
                      TweenAnimationBuilder<double>(
                        tween: Tween(begin: antes, end: pct),
                        duration: const Duration(milliseconds: 1400),
                        curve: Curves.easeOutCubic,
                        builder: (ctx, v, _) => ClipRRect(
                          borderRadius: BorderRadius.circular(999),
                          child: LinearProgressIndicator(value: v, minHeight: 14, backgroundColor: const Color(0x55120850), color: cor),
                        ),
                      ),
                      const SizedBox(height: 4),
                      Align(
                        alignment: Alignment.centerRight,
                        child: Text(prox == null ? '$total troféus' : '$total / ${prox['min']}', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                      ),
                    ]),
                  ),
                ]),
              ),
              const SizedBox(height: 12),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xCC1B1462), border: Border.all(color: const Color(0xFF6A4FE6))),
                child: Text(
                    t['subiu'] == true
                        ? 'Você subiu para ${dv['nome']}!'
                        : t['caiu'] == true
                            ? 'Você caiu para ${dv['nome']}. Bora recuperar!'
                            : d >= 0
                                ? 'Sua barra da divisão subiu!'
                                : 'Sua barra da divisão desceu um pouco.',
                    textAlign: TextAlign.center,
                    style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: t['subiu'] == true ? _ouroT : Colors.white)),
              ),
              const SizedBox(height: 18),
              if (api != null && (t['revanche'] as Map?)?['amigo'] == true) ...[
                if ((t['revanche'] as Map)['placar'] is Map)
                  Padding(
                    padding: const EdgeInsets.only(bottom: 8),
                    child: Text('Você ${((t['revanche'] as Map)['placar'] as Map)['v'] ?? 0} × ${((t['revanche'] as Map)['placar'] as Map)['d'] ?? 0} ${(t['revanche'] as Map)['nome'] ?? ''}',
                        textAlign: TextAlign.center, style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
                  ),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(
                    foregroundColor: _ouroT,
                    side: const BorderSide(color: _ouroT, width: 2),
                    minimumSize: const Size.fromHeight(52),
                    textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
                  ),
                  onPressed: () {
                    final nav = Navigator.of(context, rootNavigator: true);
                    nav.pop();
                    desafiarAmigo(nav.context, api!, t['revanche'] as Map, '${t['jogo'] ?? 'ticker'}');
                  },
                  icon: const Icon(Icons.replay_rounded),
                  label: const Text('REVANCHE'),
                ),
                const SizedBox(height: 10),
              ],
              FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF7B4BEE),
                  minimumSize: const Size.fromHeight(56),
                  textStyle: const TextStyle(fontSize: 19, fontWeight: FontWeight.w900),
                ),
                onPressed: () => Navigator.of(context).pop(),
                child: const Text('CONTINUAR  »'),
              ),
            ]),
          ),
        ),
      ),
    );
  }
}

const _ouroT = Color(0xFFF2B84B);
