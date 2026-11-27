import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'escudo.dart';
import 'perfil.dart' show imagemAvatar;

/// Tela de confronto antes do duelo: você de um lado, o adversário do outro, o "VS" no meio, com o avatar, o nome e a divisão de cada um.
/// Dura ~2,6 s e segue sozinha para a partida; um toque pula. Com "remover animações" ligado no aparelho, só aparece por um instante.
/// `dados` vem de GET /trade/salas/{id}/confronto: {voce: {...}, adversarios: [{nome, avatar_img, trofeus, divisao: {id, nome, cor, nivel}}]}.
class ConfrontoTela extends StatefulWidget {
  const ConfrontoTela({super.key, required this.dados, required this.aoTerminar, this.duracao = const Duration(milliseconds: 2600)});
  final Map<String, dynamic> dados;
  final void Function(BuildContext context) aoTerminar;
  final Duration duracao;

  @override
  State<ConfrontoTela> createState() => _ConfrontoTelaState();
}

class _ConfrontoTelaState extends State<ConfrontoTela> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: widget.duracao);
  bool _iniciou = false, _fim = false, _bateu = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_iniciou) return;
    _iniciou = true;
    final reduzido = MediaQuery.of(context).disableAnimations;
    _c.addListener(() {
      if (!_bateu && _c.value >= 0.42) {
        _bateu = true;
        HapticFeedback.heavyImpact();                       // o "VS" bate
      }
    });
    _c.addStatusListener((st) {
      if (st == AnimationStatus.completed) _seguir();
    });
    if (reduzido) {
      _c.value = 1;
      Future<void>.delayed(const Duration(milliseconds: 500), _seguir);
    } else {
      _c.forward();
    }
  }

  void _seguir() {
    if (_fim || !mounted) return;
    _fim = true;
    widget.aoTerminar(context);
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  double _f(double a, double b, Curve cv) => cv.transform(((_c.value - a) / (b - a)).clamp(0.0, 1.0));

  Widget _lado(Map lado, {required bool esquerda, required String rotulo, required Color cor}) {
    final desl = (1 - _f(0.0, 0.38, Curves.easeOutBack)) * (esquerda ? -1 : 1);
    final dv = (lado['divisao'] as Map?) ?? const {};
    final nomeOp = _f(0.45, 0.72, Curves.easeOut);
    return Expanded(
      child: FractionalTranslation(
        translation: Offset(desl * 1.1, 0),
        child: Opacity(
          opacity: _f(0.0, 0.2, Curves.easeOut),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(rotulo, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w900, letterSpacing: 2, color: cor)),
            const SizedBox(height: 8),
            Container(
              width: 112,
              height: 112,
              decoration: BoxDecoration(shape: BoxShape.circle, border: Border.all(color: cor, width: 3.5), color: const Color(0xFF152845), boxShadow: [BoxShadow(color: cor.withValues(alpha: .55), blurRadius: 24)]),
              child: ClipOval(child: imagemAvatar(lado['avatar_img'])),
            ),
            const SizedBox(height: 10),
            Opacity(
              opacity: nomeOp,
              child: Column(children: [
                Text('${lado['nome']}', maxLines: 1, overflow: TextOverflow.ellipsis, textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
                const SizedBox(height: 4),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  Escudo.de(dv, tamanho: 26),
                  const SizedBox(width: 5),
                  Flexible(child: Text('${dv['nome'] ?? ''} · ${lado['trofeus'] ?? 0}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 12.5, fontWeight: FontWeight.w700, color: Color(0xFFD4E2F7)))),
                ]),
              ]),
            ),
          ]),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final voce = (widget.dados['voce'] as Map?) ?? const {};
    final adv = ((widget.dados['adversarios'] as List?)?.whereType<Map>().firstOrNull) ?? const {};
    return Scaffold(
      backgroundColor: const Color(0xFF050E2C),
      body: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTap: _seguir,
        child: Stack(fit: StackFit.expand, children: [
          Image.asset('assets/jogos/fundo_arena.webp', fit: BoxFit.cover),
          const DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xE6050E2C), Color(0xB3050E2C), Color(0xF2050E2C)]))),
          SafeArea(
            child: AnimatedBuilder(
              animation: _c,
              builder: (ctx, _) {
                final pop = _f(0.34, 0.62, Curves.elasticOut);
                return Column(children: [
                  const SizedBox(height: 28),
                  const Text('TRADE BATTLE', style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, letterSpacing: 4, color: Color(0xFF9BBFFF))),
                  const Spacer(),
                  Padding(
                    padding: const EdgeInsets.symmetric(horizontal: 10),
                    child: Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
                      _lado(voce, esquerda: true, rotulo: 'VOCÊ', cor: const Color(0xFF4FC3FF)),
                      SizedBox(
                        width: 78,
                        child: Transform.scale(
                          scale: 0.4 + 0.6 * pop,
                          child: Opacity(
                            opacity: pop.clamp(0.0, 1.0),
                            child: ShaderMask(
                              shaderCallback: (r) => const LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0xFFFFF0B0), Color(0xFFF2B84B), Color(0xFFB5720A)]).createShader(r),
                              child: const Padding(padding: EdgeInsets.fromLTRB(4, 0, 12, 0), child: FittedBox(child: Text('VS', style: TextStyle(fontSize: 64, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Colors.white, shadows: [Shadow(color: Color(0xCCF2B84B), blurRadius: 20)])))),
                            ),
                          ),
                        ),
                      ),
                      _lado(adv, esquerda: false, rotulo: 'ADVERSÁRIO', cor: const Color(0xFFFF6A7F)),
                    ]),
                  ),
                  const Spacer(),
                  Padding(
                    padding: const EdgeInsets.fromLTRB(40, 0, 40, 26),
                    child: Column(children: [
                      const Text('Prepare-se…', style: TextStyle(fontSize: 14, fontStyle: FontStyle.italic, color: Color(0xFFD4E2F7))),
                      const SizedBox(height: 8),
                      ClipRRect(borderRadius: BorderRadius.circular(4), child: LinearProgressIndicator(value: _c.value, minHeight: 5, backgroundColor: Colors.white12, color: const Color(0xFFF2B84B))),
                      const SizedBox(height: 6),
                      const Text('toque para pular', style: TextStyle(fontSize: 11, color: Color(0x99FFFFFF))),
                    ]),
                  ),
                ]);
              },
            ),
          ),
        ]),
      ),
    );
  }
}
