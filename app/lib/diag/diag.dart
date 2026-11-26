// DIAGNÓSTICO (só no APK de testes: compilado com --dart-define=DIAGNOSTICO=true; no app normal nada disto roda).
// Mede no próprio celular, sem ADB e sem computador: quadros da mesa por fase, quadros do Flutter, memória do app, abertura e tempo até a mesa ficar pronta.
// O que NÃO dá para medir sem computador está listado em [limitacoes] e vai no relatório (nada é inventado).
import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:device_info_plus/device_info_plus.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/widgets.dart';
import 'package:share_plus/share_plus.dart';

const bool kDiag = bool.fromEnvironment('DIAGNOSTICO');
const String kDiagRotulo = String.fromEnvironment('DIAG_ROTULO', defaultValue: 'sem-rotulo');
const String kDiagVersao = String.fromEnvironment('VERSAO_APP', defaultValue: '?');

const limitacoes = [
  'FPS da mesa = cadência de requestAnimationFrame dentro da WebView (inclui a espera do render); o tempo de GPU/raster por quadro NÃO é exposto sem ferramentas de computador.',
  'Memória: o app lê o próprio processo (RSS/PSS em /proc). O processo de renderização da WebView (onde ficam os canvases) é separado e NÃO é legível pelo app; no lugar dele vão a memória de JS (performance.memory, aproximada) e uma estimativa dos canvases vivos (largura×altura×4).',
  'Tempo de abertura: idade do processo lida de /proc (assume 100 ticks/s). Vale só para abertura a frio (app fechado antes); se o app já estava na memória, a idade do processo é maior e o relatório marca "morno".',
  'Temperatura e bateria só aparecem se o Android deixar o app ler /sys (muitos aparelhos bloqueiam); senão ficam "n/d".',
  'Tempo da ponte Flutter→JS dentro do app não é medido (só na simulação de computador da Etapa 3).',
  'Um aparelho só e uma rodada não são estatística: repita 3 vezes cada versão e compare medianas.',
];

class Diag {
  static final Map<String, int> _marcas = {}; // nome -> epoch ms
  static int _epoch0 = 0;
  static double _idade0 = 0;
  static Map<String, dynamic> aparelho = {};
  static final List<Map<String, dynamic>> memoria = []; // pontos nomeados + série
  static final Map<int, _Mesa> _mesas = {};
  static int _proxId = 0;
  static final List<Map<String, dynamic>> testes = []; // execuções do teste automático
  static String rot = 'partida';
  static final _fl = _FrameFlutter();
  static String? ultimoErro;

  static Future<void> iniciar() async {
    _epoch0 = DateTime.now().millisecondsSinceEpoch;
    _idade0 = _idadeProcessoMs();
    _marcas['main_dart'] = _epoch0;
    SchedulerBinding.instance.addTimingsCallback(_fl.aoTempos);
    WidgetsBinding.instance.waitUntilFirstFrameRasterized.then((_) => marca('primeiro_quadro'));
    Timer.periodic(const Duration(seconds: 5), (_) => memoria.add(_lerMemoria('serie')));
    unawaited(_lerAparelho());
  }

  static void marca(String nome, {int? mesa}) {
    final t = DateTime.now().millisecondsSinceEpoch;
    if (mesa != null) {
      _mesas[mesa]?.marcas[nome] = t;
    } else {
      _marcas.putIfAbsent(nome, () => t); // marcas globais valem a 1ª vez (abertura do app)
    }
  }

  static void marcaSempre(String nome) => _marcas[nome] = DateTime.now().millisecondsSinceEpoch;

  // ---------- mesa ----------
  static int novaMesa(String origem) {
    final id = ++_proxId;
    _mesas[id] = _Mesa(origem)..marcas['mesa_criada'] = DateTime.now().millisecondsSinceEpoch;
    return id;
  }

  static void mesaMsg(int id, String texto) {
    try {
      final m = _mesas[id];
      if (m == null) return;
      final d = jsonDecode(texto) as Map<String, dynamic>;
      switch (d['k']) {
        case 'ok':
          m.marcas['coletor_pronto'] = (d['ep'] as num).toInt();
        case 'pronto':
          m.marcas.putIfAbsent('mesa_primeiro_desenho', () => (d['ep'] as num).toInt());
        case 'fase':
          m.fases.add({'fase': d['fase'], 'ep': d['ep']});
        case 'snap':
          m.snap = Map<String, dynamic>.from(d['d'] as Map);
        case 'mem':
          final j = Map<String, dynamic>.from(d['d'] as Map);
          final p = _lerMemoria(j['marco']?.toString() ?? 'ponto');
          p['js'] = j;
          memoria.add(p);
      }
    } catch (e) {
      ultimoErro = 'mesaMsg: $e';
    }
  }

  static int? mesaMarca(int id, String nome) => _mesas[id]?.marcas[nome];

  static void mesaFechou(int id) => _mesas[id]?.fechada = DateTime.now().millisecondsSinceEpoch;

  // ---------- leituras do sistema ----------
  static double _idadeProcessoMs() {
    try {
      final up = double.parse(File('/proc/uptime').readAsStringSync().split(' ').first);
      final st = File('/proc/self/stat').readAsStringSync();
      final depois = st.substring(st.lastIndexOf(')') + 2).split(' ');
      final ticks = double.parse(depois[19]); // campo 22 (starttime), contando a partir do "state" (campo 3)
      return (up - ticks / 100.0) * 1000.0;
    } catch (_) {
      return -1;
    }
  }

  static int? _kb(String txt, String chave) {
    final m = RegExp('^$chave:\\s+(\\d+) kB', multiLine: true).firstMatch(txt);
    return m == null ? null : int.parse(m.group(1)!);
  }

  static Map<String, dynamic> _lerMemoria(String marco) {
    final r = <String, dynamic>{'marco': marco, 'ep': DateTime.now().millisecondsSinceEpoch, 'rot': rot};
    try {
      r['rssDartMB'] = double.parse((ProcessInfo.currentRss / 1048576).toStringAsFixed(1));
    } catch (_) {}
    try {
      final s = File('/proc/self/smaps_rollup').readAsStringSync();
      r['pssMB'] = _mb(_kb(s, 'Pss'));
      r['pssAnonMB'] = _mb(_kb(s, 'Pss_Anon'));
      r['pssFileMB'] = _mb(_kb(s, 'Pss_File'));
      r['privDirtyMB'] = _mb(_kb(s, 'Private_Dirty'));
    } catch (_) {}
    try {
      final s = File('/proc/self/status').readAsStringSync();
      r['vmRssMB'] = _mb(_kb(s, 'VmRSS'));
      r['vmSwapMB'] = _mb(_kb(s, 'VmSwap'));
      r['threads'] = int.tryParse(RegExp(r'^Threads:\s+(\d+)', multiLine: true).firstMatch(s)?.group(1) ?? '');
    } catch (_) {}
    try {
      final s = File('/proc/meminfo').readAsStringSync();
      r['sistemaLivreMB'] = _mb(_kb(s, 'MemAvailable'));
    } catch (_) {}
    r['bateriaTempC'] = _lerNum('/sys/class/power_supply/battery/temp', 10);
    r['bateriaPct'] = _lerNum('/sys/class/power_supply/battery/capacity', 1);
    return r;
  }

  static double? _mb(int? kb) => kb == null ? null : double.parse((kb / 1024).toStringAsFixed(1));
  static double? _lerNum(String caminho, double div) {
    try {
      return double.parse((double.parse(File(caminho).readAsStringSync().trim()) / div).toStringAsFixed(1));
    } catch (_) {
      return null;
    }
  }

  static Map<String, dynamic> pontoMemoria(String marco) {
    final p = _lerMemoria(marco);
    memoria.add(p);
    return p;
  }

  static Future<void> _lerAparelho() async {
    final a = <String, dynamic>{};
    try {
      final i = await DeviceInfoPlugin().androidInfo;
      a['modelo'] = '${i.manufacturer} ${i.model}';
      a['marca'] = i.brand;
      a['dispositivo'] = i.device;
      a['hardware'] = i.hardware;
      a['android'] = i.version.release;
      a['sdk'] = i.version.sdkInt;
      a['abis'] = i.supportedAbis;
      try {
        a['ramTotalMB'] = (_kb(File('/proc/meminfo').readAsStringSync(), 'MemTotal') ?? 0) ~/ 1024;
      } catch (_) {}
      a['pouca_ram'] = i.isLowRamDevice;
    } catch (e) {
      a['erro_info'] = '$e';
    }
    try {
      final v = WidgetsBinding.instance.platformDispatcher.views.first;
      a['telaPx'] = '${v.physicalSize.width.round()}x${v.physicalSize.height.round()}';
      a['dpr'] = v.devicePixelRatio;
      a['hz'] = v.display.refreshRate;
    } catch (_) {}
    aparelho = a;
  }

  // ---------- relatório ----------
  static void zerar() {
    memoria.clear();
    _mesas.removeWhere((_, m) => m.fechada != 0);
    for (final m in _mesas.values) {
      m.snap = null;
    }
    testes.clear();
    _fl.zerar();
  }

  static Map<String, dynamic> relatorio() {
    final idadeMain = _idade0;
    int? ms(String n) => _marcas[n] == null ? null : (idadeMain + (_marcas[n]! - _epoch0)).round();
    final aberturaMarcas = {for (final e in _marcas.entries) e.key: ms(e.key)};
    final frio = idadeMain >= 0 && idadeMain < 8000;
    final mesas = <Map<String, dynamic>>[];
    for (final e in _mesas.entries) {
      final m = e.value;
      int? d(String a, String b) => (m.marcas[a] != null && m.marcas[b] != null) ? m.marcas[b]! - m.marcas[a]! : null;
      mesas.add({
        'id': e.key,
        'origem': m.origem,
        'criadaAteCarregarPaginaMs': d('mesa_criada', 'mesa_pagina_carregada'),
        'criadaAtePrimeiroDesenhoMs': d('mesa_criada', 'mesa_primeiro_desenho'),
        'paginaAtePrimeiroDesenhoMs': d('mesa_pagina_carregada', 'mesa_primeiro_desenho'),
        'renderEnviadoAtePrimeiroDesenhoMs': d('mesa_render_enviado', 'mesa_primeiro_desenho'),
        'fechada': m.fechada != 0,
        'js': m.snap,
      });
    }
    return {
      'rotulo': kDiagRotulo,
      'versaoBuild': kDiagVersao,
      'gerado': DateTime.now().toIso8601String(),
      'aparelho': aparelho,
      'abertura': {
        'idadeProcessoNoMainMs': idadeMain.round(),
        'tipo': frio ? 'frio' : 'morno (processo já existia: tempos de abertura não valem)',
        'marcasMsDesdeInicioDoProcesso': aberturaMarcas,
      },
      'mesas': mesas,
      'testesAutomaticos': testes,
      'memoria': List.of(memoria),
      'flutterQuadros': _fl.resumo(),
      'limitacoes': limitacoes,
      'erroDoDiagnostico': ultimoErro,
    };
  }

  static String texto() {
    final r = relatorio();
    final b = StringBuffer();
    void l([String s = '']) => b.writeln(s);
    l('RELATÓRIO DE DIAGNÓSTICO · versão ${r['rotulo']} (build ${r['versaoBuild']})');
    l('Gerado: ${r['gerado']}');
    final a = r['aparelho'] as Map;
    l('Aparelho: ${a['modelo'] ?? 'n/d'} · Android ${a['android'] ?? '?'} (SDK ${a['sdk'] ?? '?'}) · ${a['hardware'] ?? ''} · RAM ${a['ramTotalMB'] ?? '?'} MB · tela ${a['telaPx'] ?? '?'} @${a['dpr'] ?? '?'}x · ${a['hz'] ?? '?'} Hz · ABI ${a['abis'] ?? '?'}');
    l();
    final ab = r['abertura'] as Map;
    l('ABERTURA (ms desde o início do processo) · ${ab['tipo']}');
    for (final e in (ab['marcasMsDesdeInicioDoProcesso'] as Map).entries) {
      l('  ${e.key}: ${e.value ?? 'n/d'}');
    }
    l();
    l('MESA — tempo até ficar pronta (ms)');
    for (final m in r['mesas'] as List) {
      l('  mesa #${m['id']} (${m['origem']}): criada→página ${m['criadaAteCarregarPaginaMs'] ?? 'n/d'} · criada→1º desenho ${m['criadaAtePrimeiroDesenhoMs'] ?? 'n/d'} · render enviado→1º desenho ${m['renderEnviadoAtePrimeiroDesenhoMs'] ?? 'n/d'}');
    }
    l();
    l('FPS E QUADROS DA MESA POR FASE (cadência de requestAnimationFrame)');
    for (final m in r['mesas'] as List) {
      final js = m['js'] as Map?;
      if (js == null) continue;
      l('  mesa #${m['id']} · canvases criados: ${js['canvasCriadosTotal']} · pausas: ${js['pausas']} · erros JS: ${(js['erros'] as List).length}${(js['erros'] as List).isEmpty ? '' : ' ${js['erros']}'}');
      for (final f in js['fases'] as List) {
        l('    [${f['rot']}] ${(f['fase'] as String).padRight(8)} ${f['quadros']} q/${f['segundos']}s · FPS médio ${f['fpsMedio']} · mín(1s) ${f['fpsMinSeg'] ?? 'n/d'} · p5(1s) ${f['fpsP5Seg'] ?? 'n/d'} · quadro p50 ${f['quadroP50Ms']} p95 ${f['quadroP95Ms']} p99 ${f['quadroP99Ms']} máx ${f['quadroMaxMs']} ms · >25ms ${f['quadrosAcima25ms']} >34ms ${f['quadrosAcima34ms']} >50ms ${f['quadrosAcima50ms']} >100ms ${f['quadrosAcima100ms']} · JS draw méd ${f['drawMedioMs']} p95 ${f['drawP95Ms']} máx ${f['drawMaxMs']} ms · efeitos méd ${f['efeitosMedioMs']} p95 ${f['efeitosP95Ms']} máx ${f['efeitosMaxMs']} ms · canvases criados ${f['canvasCriados']}');
      }
      final jank = (js['jank'] as List);
      if (jank.isNotEmpty) {
        final pior = List<Map>.from(jank)..sort((x, y) => (y['dt'] as num).compareTo(x['dt'] as num));
        l('    Maiores travamentos (quadro > 34 ms): total ${jank.length}; piores: ${pior.take(10).map((j) => '${j['dt']}ms ${j['fase']}@${j['t']}ms').join(' · ')}');
      }
    }
    l();
    l('FLUTTER (quadros renderizados pelo app)');
    l('  ${r['flutterQuadros']}');
    l();
    l('MEMÓRIA (MB) — app (PSS/RSS do processo do app) + JS e canvases da mesa');
    for (final p in r['memoria'] as List) {
      if (p['marco'] == 'serie') continue;
      final js = p['js'] as Map?;
      l('  ${p['marco']}: PSS ${p['pssMB'] ?? 'n/d'} · RSS ${p['vmRssMB'] ?? p['rssDartMB'] ?? 'n/d'} · swap ${p['vmSwapMB'] ?? 'n/d'}${js == null ? '' : ' · JS ${_mbJs(js['jsUsado'])} · canvases vivos ${js['canvasVivosCriados']} (+${js['canvasNoDom']} no DOM) ≈ ${js['canvasMB']} MB · nós DOM ${js['nos']}'} · livre sistema ${p['sistemaLivreMB'] ?? 'n/d'} · bateria ${p['bateriaTempC'] ?? 'n/d'}°C ${p['bateriaPct'] ?? ''}%');
    }
    final serie = (r['memoria'] as List).where((p) => p['marco'] == 'serie' && p['pssMB'] != null).toList();
    if (serie.length >= 4) {
      final t0 = (serie.first['ep'] as int);
      final dx = serie.map((p) => ((p['ep'] as int) - t0) / 60000.0).toList();
      final dy = serie.map((p) => (p['pssMB'] as num).toDouble()).toList();
      l('  Tendência do PSS (série a cada 5 s, ${serie.length} amostras, ${dx.last.toStringAsFixed(1)} min): ${_inclina(dx, dy).toStringAsFixed(2)} MB/min · início ${dy.first} → fim ${dy.last} MB');
    }
    l();
    l('LIMITAÇÕES');
    for (final s in limitacoes) {
      l('  - $s');
    }
    return b.toString();
  }

  static String _mbJs(Object? v) => v is num ? '${(v / 1048576).toStringAsFixed(1)} MB' : 'n/d';
  static double _inclina(List<double> x, List<double> y) {
    final n = x.length;
    final mx = x.reduce((a, b) => a + b) / n, my = y.reduce((a, b) => a + b) / n;
    var num = 0.0, den = 0.0;
    for (var i = 0; i < n; i++) {
      num += (x[i] - mx) * (y[i] - my);
      den += (x[i] - mx) * (x[i] - mx);
    }
    return den == 0 ? 0 : num / den;
  }

  /// Grava o relatório (.txt legível e .json completo) na pasta temporária do app e abre o menu de compartilhar do Android.
  static Future<String> exportar() async {
    final dir = Directory.systemTemp;
    final carimbo = DateTime.now().toIso8601String().replaceAll(RegExp(r'[^0-9]'), '').substring(0, 14);
    final base = 'th_diag_${kDiagRotulo}_$carimbo';
    final txt = File('${dir.path}/$base.txt')..writeAsStringSync(texto());
    final js = File('${dir.path}/$base.json')..writeAsStringSync(const JsonEncoder.withIndent(' ').convert(relatorio()));
    await Share.shareXFiles([XFile(txt.path, mimeType: 'text/plain'), XFile(js.path, mimeType: 'application/json')], subject: 'Diagnóstico TickerHunters ($kDiagRotulo)');
    return txt.path;
  }
}

class _Mesa {
  _Mesa(this.origem);
  final String origem;
  final Map<String, int> marcas = {};
  final List<Map<String, dynamic>> fases = [];
  Map<String, dynamic>? snap;
  int fechada = 0;
}

class _FrameFlutter {
  final List<double> _build = [], _raster = [], _total = [];
  final List<Map<String, num>> _piores = [];
  int _acima34 = 0, _acima50 = 0;

  void zerar() {
    _build.clear();
    _raster.clear();
    _total.clear();
    _piores.clear();
    _acima34 = _acima50 = 0;
  }

  void aoTempos(List<FrameTiming> ts) {
    for (final t in ts) {
      final b = t.buildDuration.inMicroseconds / 1000, r = t.rasterDuration.inMicroseconds / 1000, tot = t.totalSpan.inMicroseconds / 1000;
      if (_total.length < 60000) {
        _build.add(b);
        _raster.add(r);
        _total.add(tot);
      }
      if (tot > 34) _acima34++;
      if (tot > 50) _acima50++;
      if (tot > 34) {
        _piores.add({'totalMs': double.parse(tot.toStringAsFixed(1)), 'buildMs': double.parse(b.toStringAsFixed(1)), 'rasterMs': double.parse(r.toStringAsFixed(1))});
        _piores.sort((x, y) => y['totalMs']!.compareTo(x['totalMs']!));
        if (_piores.length > 15) _piores.removeLast();
      }
    }
  }

  static double _p(List<double> v, double q) {
    if (v.isEmpty) return 0;
    final s = List<double>.of(v)..sort();
    return double.parse(s[((s.length - 1) * q).round()].toStringAsFixed(1));
  }

  Map<String, dynamic> resumo() => {
        'quadros': _total.length,
        'buildP50Ms': _p(_build, .5),
        'buildP95Ms': _p(_build, .95),
        'rasterP50Ms': _p(_raster, .5),
        'rasterP95Ms': _p(_raster, .95),
        'totalP95Ms': _p(_total, .95),
        'totalMaxMs': _p(_total, 1),
        'acima34ms': _acima34,
        'acima50ms': _acima50,
        'piores': _piores,
      };
}
