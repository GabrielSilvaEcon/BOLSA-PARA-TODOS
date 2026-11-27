import 'package:audioplayers/audioplayers.dart';
import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

/// Efeitos sonoros curtos (gerados por tools/som/gerar.py). Nunca quebra o app: sem plugin (testes) ou sem áudio, fica mudo.
class Som {
  Som._();
  static final ligado = ValueNotifier<bool>(true);
  static final Map<String, AudioPlayer> _players = {};
  static bool _carregado = false;

  /// Lê a preferência salva (chamar uma vez ao abrir o app).
  static Future<void> iniciar() async {
    if (_carregado) return;
    _carregado = true;
    try {
      final sp = await SharedPreferences.getInstance();
      ligado.value = sp.getBool('som_ligado') ?? true;
    } catch (_) {}
  }

  static Future<void> definir(bool v) async {
    ligado.value = v;
    try {
      final sp = await SharedPreferences.getInstance();
      await sp.setBool('som_ligado', v);
    } catch (_) {}
  }

  /// Toca `assets/som/<nome>.wav`. Respeita o botão de som; falhas são engolidas.
  static Future<void> tocar(String nome) async {
    if (!ligado.value) return;
    try {
      final p = _players.putIfAbsent(nome, () => AudioPlayer()..setReleaseMode(ReleaseMode.stop));
      await p.stop();
      await p.play(AssetSource('som/$nome.wav'), volume: 0.7, mode: PlayerMode.lowLatency);
    } catch (_) {}
  }
}
