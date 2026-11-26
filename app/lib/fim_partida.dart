import 'package:flutter/material.dart';

/// Fim da partida: um pop-up que prende a tela (não fecha tocando fora nem no botão voltar do aparelho).
/// Só dois caminhos: jogar novamente ou voltar ao menu.
Future<void> mostrarFimDePartida(BuildContext context, {required VoidCallback jogarNovamente, required VoidCallback voltarAoMenu}) {
  return showDialog<void>(
    context: context,
    barrierDismissible: false,
    barrierColor: const Color(0xCC03061A),
    builder: (ctx) => PopScope(
      canPop: false,
      child: Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.symmetric(horizontal: 28),
        child: Container(
          padding: const EdgeInsets.fromLTRB(20, 22, 20, 20),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(24),
            border: Border.all(color: const Color(0xFF5C9AFF), width: 2),
            gradient: const RadialGradient(center: Alignment.topCenter, radius: 1.3, colors: [Color(0xFF2A579E), Color(0xFF122E58), Color(0xFF0D0A33)], stops: [0, .45, 1]),
            boxShadow: const [BoxShadow(color: Color(0x8C5C9AFF), blurRadius: 30)],
          ),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            const Text('PARTIDA ENCERRADA',
                textAlign: TextAlign.center, style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, fontStyle: FontStyle.italic, color: Color(0xFF4FC3FF), letterSpacing: .6)),
            const SizedBox(height: 6),
            const Text('O que você quer fazer agora?', textAlign: TextAlign.center, style: TextStyle(fontSize: 13.5, color: Color(0xFFCFE3FF))),
            const SizedBox(height: 18),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: FilledButton.icon(
                style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                onPressed: () {
                  Navigator.of(ctx).pop();
                  jogarNovamente();
                },
                icon: const Icon(Icons.replay_rounded),
                label: const Text('Jogar novamente', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
              ),
            ),
            const SizedBox(height: 10),
            SizedBox(
              width: double.infinity,
              height: 54,
              child: OutlinedButton.icon(
                style: OutlinedButton.styleFrom(foregroundColor: Colors.white, side: const BorderSide(color: Color(0xFF4F88E6), width: 1.8), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16))),
                onPressed: () {
                  Navigator.of(ctx).pop();
                  voltarAoMenu();
                },
                icon: const Icon(Icons.home_rounded),
                label: const Text('Voltar ao menu', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
              ),
            ),
          ]),
        ),
      ),
    ),
  );
}
