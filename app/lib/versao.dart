import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:url_launcher/url_launcher.dart';

/// Aviso de versão nova do APK de teste (enquanto o app não está na Play Store).
/// Cada APK leva o número da compilação (`--dart-define=VERSAO_APP`); a mesma compilação publica `versao.json` ao lado do APK.
/// Ao abrir o app (e a cada 30 min), compara os dois: se saiu uma versão mais nova, mostra uma faixa com o botão "Atualizar",
/// que baixa o APK novo. Na versão web não aparece (ela já se atualiza sozinha).
const int versaoApp = int.fromEnvironment('VERSAO_APP', defaultValue: 0);
const _base = 'https://github.com/GabrielSilvaEcon/BOLSA-PARA-TODOS/releases/download/apk-teste';
const urlApk = '$_base/tickerhunters.apk';

/// Número da versão nova publicada (null = o app está em dia ou não deu para saber).
final versaoNova = ValueNotifier<int?>(null);
Timer? _relogio;

/// Começa a conferir (uma vez agora e depois a cada 30 minutos). Falha de rede não mostra nada.
void conferirVersaoSempre() {
  if (kIsWeb || versaoApp == 0) return;
  _conferir();
  _relogio ??= Timer.periodic(const Duration(minutes: 30), (_) => _conferir());
}

Future<void> _conferir() async {
  try {
    final r = await http.get(Uri.parse('$_base/versao.json?t=${DateTime.now().millisecondsSinceEpoch}')).timeout(const Duration(seconds: 20));
    if (r.statusCode != 200) return;
    final v = (jsonDecode(r.body) as Map)['versao'];
    final n = v is num ? v.toInt() : int.tryParse('$v');
    if (n != null && n > versaoApp) versaoNova.value = n;
  } catch (_) {
    // sem internet ou arquivo ainda não publicado: tenta de novo mais tarde
  }
}

/// Faixa "Nova versão disponível" logo abaixo do cabeçalho. Entra deslizando, o ícone pulsa, e some no X (até a próxima versão).
class AvisoVersao extends StatefulWidget {
  const AvisoVersao({super.key});

  @override
  State<AvisoVersao> createState() => _AvisoVersaoState();
}

class _AvisoVersaoState extends State<AvisoVersao> with SingleTickerProviderStateMixin {
  int? _dispensada;
  late final AnimationController _pulso = AnimationController(vsync: this, duration: const Duration(milliseconds: 1200))..repeat(reverse: true);

  @override
  void dispose() {
    _pulso.dispose();
    super.dispose();
  }

  Future<void> _atualizar() async {
    final ok = await launchUrl(Uri.parse(urlApk), mode: LaunchMode.externalApplication);
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Não consegui abrir o navegador. Baixe pelo link de sempre.')));
    }
  }

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<int?>(
      valueListenable: versaoNova,
      builder: (ctx, nova, _) {
        final mostrar = nova != null && nova != _dispensada;
        return AnimatedSize(
          duration: const Duration(milliseconds: 380),
          curve: Curves.easeOutCubic,
          child: !mostrar
              ? const SizedBox(width: double.infinity)
              : TweenAnimationBuilder<double>(
                  key: ValueKey(nova),
                  tween: Tween(begin: 0, end: 1),
                  duration: const Duration(milliseconds: 500),
                  curve: Curves.easeOutBack,
                  builder: (ctx, v, f) => Opacity(opacity: v.clamp(0.0, 1.0), child: Transform.translate(offset: Offset(0, -16 * (1 - v)), child: f)),
                  child: Container(
                    margin: const EdgeInsets.fromLTRB(10, 6, 10, 2),
                    padding: const EdgeInsets.fromLTRB(10, 6, 4, 6),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(16),
                      gradient: const LinearGradient(colors: [Color(0xFF18A865), Color(0xFF0E6B52)]),
                      border: Border.all(color: const Color(0xFF5BF5A0), width: 1.5),
                      boxShadow: const [BoxShadow(color: Color(0x6626D07C), blurRadius: 12)],
                    ),
                    child: Row(
                      children: [
                        AnimatedBuilder(
                          animation: _pulso,
                          builder: (ctx, f) => Transform.scale(scale: 0.9 + 0.15 * Curves.easeInOut.transform(_pulso.value), child: f),
                          child: const Icon(Icons.system_update_rounded, color: Colors.white, size: 26),
                        ),
                        const SizedBox(width: 8),
                        const Expanded(
                          child: Text('Nova versão disponível!',
                              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w800, color: Colors.white)),
                        ),
                        FilledButton(
                          style: FilledButton.styleFrom(
                            backgroundColor: Colors.white,
                            foregroundColor: const Color(0xFF0B5A3A),
                            visualDensity: VisualDensity.compact,
                            textStyle: const TextStyle(fontWeight: FontWeight.w900),
                          ),
                          onPressed: _atualizar,
                          child: const Text('Atualizar'),
                        ),
                        IconButton(
                          tooltip: 'Agora não',
                          visualDensity: VisualDensity.compact,
                          onPressed: () => setState(() => _dispensada = nova),
                          icon: const Icon(Icons.close_rounded, color: Colors.white70, size: 20),
                        ),
                      ],
                    ),
                  ),
                ),
        );
      },
    );
  }
}
