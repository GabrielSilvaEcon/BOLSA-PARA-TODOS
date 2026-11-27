import 'dart:io';
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:share_plus/share_plus.dart';

import 'escudo.dart';
import 'resultado_partida.dart';

/// Entrega a imagem ao menu de compartilhar do Android. Os testes trocam esta função por uma falsa.
Future<void> Function(Uint8List png, String texto) compartilharPng = _compartilharDeVerdade;

Future<void> _compartilharDeVerdade(Uint8List png, String texto) async {
  final f = File('${Directory.systemTemp.path}/resultado_tickerhunters.png');
  await f.writeAsBytes(png, flush: true);
  await Share.shareXFiles([XFile(f.path, mimeType: 'image/png')], text: texto);
}

String _textoDe(ResultadoPartida r) => switch (r.estado) {
      'vitoria' => 'Venci um duelo de trading no TickerHunters! 🏆 Bora tentar me vencer?',
      'empate' => 'Empatei um duelo de trading no TickerHunters. Bora a revanche?',
      _ => 'Perdi um duelo no TickerHunters, mas aprendi. Bora a revanche?',
    };

/// A imagem que vai para as redes (4:5): arte do resultado, lucro, pontos, troféus e divisão. Nada que identifique a conta (sem e-mail e sem o nome do adversário).
class CartaCompartilhar extends StatelessWidget {
  const CartaCompartilhar({super.key, required this.r});
  final ResultadoPartida r;

  static const largura = 300.0, altura = 375.0;

  @override
  Widget build(BuildContext context) {
    final cor = switch (r.estado) { 'vitoria' => const Color(0xFFFFC93C), 'empate' => const Color(0xFF5CC8FF), _ => const Color(0xFFFF4D6D) };
    final topo = switch (r.estado) { 'vitoria' => 'topo_vitoria', 'empate' => 'topo_empate', _ => 'topo_derrota' };
    final t = r.trofeus;
    final delta = (t?['delta'] as num?)?.toInt();
    final dv = (t?['dv'] as Map?) ?? const {};
    Widget numero(String rot, String valor, Color c) => Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 8),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), color: c.withValues(alpha: .14), border: Border.all(color: c.withValues(alpha: .9), width: 1.4)),
            child: Column(children: [
              Text(rot, style: const TextStyle(fontSize: 9, fontWeight: FontWeight.w800, color: Colors.white)),
              const SizedBox(height: 2),
              Padding(padding: const EdgeInsets.symmetric(horizontal: 6), child: FittedBox(child: Text(valor, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: c)))),
            ]),
          ),
        );
    return SizedBox(
      width: largura,
      height: altura,
      child: DecoratedBox(
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), border: Border.all(color: cor, width: 2.5), color: const Color(0xFF060B26)),
        child: ClipRRect(
          borderRadius: BorderRadius.circular(16),
          child: Column(children: [
            Expanded(
              flex: 5,
              child: Stack(fit: StackFit.expand, children: [
                // brilho na cor do resultado atrás da arte (a arte da vitória é larga e baixa; a do empate e da derrota é quase quadrada: as duas cabem inteiras)
                DecoratedBox(decoration: BoxDecoration(gradient: RadialGradient(center: const Alignment(0, 0.1), radius: 0.9, colors: [cor.withValues(alpha: .30), const Color(0xFF060B26)]))),
                const Align(alignment: Alignment.topCenter, child: Padding(padding: EdgeInsets.only(top: 10), child: Text('TICKERHUNTERS · DUELO DE TRADING', style: TextStyle(fontSize: 8.5, fontWeight: FontWeight.w900, letterSpacing: 1.4, color: Color(0xCCD4E2F7))))),
                Padding(padding: const EdgeInsets.only(top: 18), child: Image.asset('assets/resultado/$topo.webp', fit: BoxFit.contain)),
              ]),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(12, 0, 12, 10),
              child: Column(children: [
                Row(children: [
                  numero('LUCRO', r.pnl == null ? '—' : ResultadoPartida.moeda(r.pnl!), (r.pnl ?? 0) < 0 ? const Color(0xFFFF4D6D) : const Color(0xFF26D07C)),
                  const SizedBox(width: 6),
                  numero('PONTOS', r.pontos == null ? '—' : ResultadoPartida.num1(r.pontos!), const Color(0xFF4FC3FF)),
                  if (delta != null) ...[const SizedBox(width: 6), numero('TROFÉUS', '${delta >= 0 ? '+' : ''}$delta', const Color(0xFFF2B84B))],
                ]),
                const SizedBox(height: 8),
                Row(mainAxisAlignment: MainAxisAlignment.center, children: [
                  if (dv.isNotEmpty) ...[Escudo.de(dv, tamanho: 26), const SizedBox(width: 6)],
                  Flexible(child: Text(dv.isNotEmpty ? 'Divisão ${dv['nome']} · TickerHunters' : 'TickerHunters · Duelo de trading', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 11.5, fontWeight: FontWeight.w800, color: Color(0xFFD4E2F7)))),
                ]),
              ]),
            ),
          ]),
        ),
      ),
    );
  }
}

/// Abre a prévia da imagem e o botão que manda para o menu de compartilhar.
Future<void> abrirCompartilhar(BuildContext context, ResultadoPartida r) {
  final chave = GlobalKey();
  return showModalBottomSheet<void>(
    context: context,
    isScrollControlled: true,                       // sem isto a folha ocupa só 9/16 da tela e a prévia (375 px) estoura
    useSafeArea: true,
    backgroundColor: const Color(0xFF0B1A3A),
    shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(22))),
    builder: (ctx) {
      var enviando = false;
      return StatefulBuilder(
        builder: (ctx, setS) => SafeArea(
          child: SingleChildScrollView(
            padding: const EdgeInsets.fromLTRB(20, 18, 20, 18),
            child: Column(mainAxisSize: MainAxisSize.min, children: [
              const Text('Compartilhar o resultado', style: TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Colors.white)),
              const SizedBox(height: 12),
              RepaintBoundary(key: chave, child: CartaCompartilhar(r: r)),
              const SizedBox(height: 14),
              SizedBox(
                width: double.infinity,
                height: 50,
                child: FilledButton.icon(
                  onPressed: enviando
                      ? null
                      : () async {
                          setS(() => enviando = true);
                          try {
                            final b = chave.currentContext!.findRenderObject() as RenderRepaintBoundary;
                            final img = await b.toImage(pixelRatio: 1080 / CartaCompartilhar.largura);
                            final bytes = (await img.toByteData(format: ui.ImageByteFormat.png))!.buffer.asUint8List();
                            await compartilharPng(bytes, _textoDe(r));
                            if (ctx.mounted) Navigator.of(ctx).pop();
                          } catch (e) {
                            if (ctx.mounted) {
                              setS(() => enviando = false);
                              ScaffoldMessenger.of(ctx).showSnackBar(SnackBar(content: Text('Não consegui compartilhar agora: $e')));
                            }
                          }
                        },
                  icon: const Icon(Icons.ios_share_rounded),
                  label: Text(enviando ? 'Preparando…' : 'Compartilhar', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
                ),
              ),
            ]),
          ),
        ),
      );
    },
  );
}
