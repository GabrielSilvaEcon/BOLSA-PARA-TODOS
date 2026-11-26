// Painel de diagnóstico (só no APK de testes). Abre com DOIS TOQUES na pastilha discreta da borda esquerda da tela.
import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:wakelock_plus/wakelock_plus.dart';

import '../mesa/mesa_app.dart';
import 'diag.dart';
import 'diag_args.dart';

final GlobalKey<NavigatorState> diagNavKey = GlobalKey<NavigatorState>();
final ValueNotifier<bool> diagBenchAtivo = ValueNotifier(false);

/// Pastilha quase invisível na borda esquerda; dois toques abrem o painel. Não mostra FPS nem nada que mude (não interfere nas medições).
class DiagAlca extends StatelessWidget {
  const DiagAlca({super.key});

  @override
  Widget build(BuildContext context) {
    return ValueListenableBuilder<bool>(
      valueListenable: diagBenchAtivo,
      builder: (_, bench, __) => bench
          ? const SizedBox.shrink()
          : Positioned(
              left: 0,
              top: MediaQuery.of(context).size.height * 0.42,
              child: GestureDetector(
                behavior: HitTestBehavior.opaque,
                onDoubleTap: () => diagNavKey.currentState?.push(MaterialPageRoute(builder: (_) => const DiagPainel())),
                child: Container(
                  width: 14,
                  height: 72,
                  decoration: const BoxDecoration(color: Color(0x33FFFFFF), borderRadius: BorderRadius.horizontal(right: Radius.circular(7))),
                ),
              ),
            ),
    );
  }
}

class DiagPainel extends StatefulWidget {
  const DiagPainel({super.key});

  @override
  State<DiagPainel> createState() => _DiagPainelState();
}

class _DiagPainelState extends State<DiagPainel> {
  String _texto = '';
  String _aviso = '';

  @override
  void initState() {
    super.initState();
    _atualizar();
  }

  void _atualizar() => setState(() => _texto = Diag.texto());

  Future<void> _bench(bool longo) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) => DiagBenchTela(longo: longo)));
    if (mounted) _atualizar();
  }

  @override
  Widget build(BuildContext context) {
    final b = ButtonStyle(minimumSize: WidgetStateProperty.all(const Size.fromHeight(46)));
    return Scaffold(
      backgroundColor: const Color(0xFF0B1220),
      appBar: AppBar(title: Text('Diagnóstico · versão $kDiagRotulo (build $kDiagVersao)', style: const TextStyle(fontSize: 15)), backgroundColor: const Color(0xFF111B30)),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(14),
          children: [
            const Text(
              'Como usar: 1) toque em um teste e deixe o celular parado até terminar; 2) repita 3 vezes; 3) toque em Exportar relatório e compartilhe o arquivo (WhatsApp, e-mail, Drive…). Instale a outra versão (ANTES/DEPOIS) e repita igual. Partidas jogadas normalmente também são medidas sozinhas.',
              style: TextStyle(fontSize: 12.5, color: Colors.white70),
            ),
            const SizedBox(height: 12),
            FilledButton(style: b, onPressed: () => _bench(false), child: const Text('Teste automático da mesa (≈ 1 min 45 s)')),
            const SizedBox(height: 8),
            FilledButton.tonal(style: b, onPressed: () => _bench(true), child: const Text('Uso contínuo da mesa (10 min)')),
            const SizedBox(height: 8),
            FilledButton(
              style: b,
              onPressed: () async {
                try {
                  final p = await Diag.exportar();
                  setState(() => _aviso = 'Arquivo gerado: $p');
                } catch (e) {
                  setState(() => _aviso = 'Falha ao exportar: $e');
                }
              },
              child: const Text('Exportar relatório (.txt + .json)'),
            ),
            const SizedBox(height: 8),
            Row(children: [
              Expanded(
                child: OutlinedButton(
                  onPressed: () async {
                    await Clipboard.setData(ClipboardData(text: Diag.texto()));
                    setState(() => _aviso = 'Relatório copiado (cole numa conversa).');
                  },
                  child: const Text('Copiar texto'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(child: OutlinedButton(onPressed: _atualizar, child: const Text('Atualizar'))),
              const SizedBox(width: 8),
              Expanded(
                child: OutlinedButton(
                  onPressed: () {
                    Diag.zerar();
                    _atualizar();
                  },
                  child: const Text('Zerar'),
                ),
              ),
            ]),
            if (_aviso.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8), child: Text(_aviso, style: const TextStyle(fontSize: 12, color: Color(0xFFFFD76A)))),
            const SizedBox(height: 12),
            SelectableText(_texto, style: const TextStyle(fontFamily: 'monospace', fontSize: 10.5, color: Colors.white)),
          ],
        ),
      ),
    );
  }
}

/// Teste automático: abre a MESMA mesa do jogo (mesma ponte Flutter→WebView) com dados fixos e roda clássico → mira → destaque → decisão,
/// várias ativações, e sair/entrar de novo. Mesmos dados e mesmos tempos nas duas versões, então os números são comparáveis.
class DiagBenchTela extends StatefulWidget {
  const DiagBenchTela({super.key, required this.longo});
  final bool longo;

  @override
  State<DiagBenchTela> createState() => _DiagBenchTelaState();
}

class _DiagBenchTelaState extends State<DiagBenchTela> {
  MesaHost? _mesa;
  String _status = 'Preparando…';
  bool _cancelar = false;
  bool _fim = false;
  int _n = 0;
  final _etapas = <Map<String, dynamic>>[];

  @override
  void initState() {
    super.initState();
    diagBenchAtivo.value = true;
    WakelockPlus.enable();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.immersiveSticky);
    _rodar();
  }

  @override
  void dispose() {
    _cancelar = true;
    _mesa?.fechar();
    WakelockPlus.disable();
    SystemChrome.setEnabledSystemUIMode(SystemUiMode.edgeToEdge);
    diagBenchAtivo.value = false;
    super.dispose();
  }

  Future<bool> _esp(int ms) async {
    final fim = DateTime.now().add(Duration(milliseconds: ms));
    while (DateTime.now().isBefore(fim)) {
      if (_cancelar || !mounted) return false;
      await Future.delayed(const Duration(milliseconds: 50));
    }
    return !_cancelar && mounted;
  }

  void _st(String s) {
    _etapas.add({'etapa': s, 'ep': DateTime.now().millisecondsSinceEpoch});
    if (mounted) setState(() => _status = s);
  }

  Future<bool> _abrirMesa(String rot) async {
    _mesa?.fechar();
    Diag.rot = rot;
    final m = MesaHost(aoEvento: (_) {}, aoPronto: () {}, origem: 'teste_$rot');
    setState(() => _mesa = m);
    // espera a página carregar e o coletor entrar
    for (var i = 0; i < 300; i++) {
      if (m.diagMarca('coletor_pronto') != null) break;
      if (!await _esp(100)) return false;
    }
    m.diagJs("__diag.rot('$rot')");
    m.desenhar(diagArgs(evento: false));
    for (var i = 0; i < 300; i++) {
      if (m.diagMarca('mesa_primeiro_desenho') != null) return true;
      if (!await _esp(100)) return false;
    }
    _st('AVISO: a mesa não ficou pronta em 30 s');
    return true;
  }

  Future<bool> _ciclo(String rot, {bool memNoDestaque = false}) async {
    final m = _mesa!;
    _n++;
    _st('Ativação $_n: mira (4 s)');
    m.desenhar(diagArgs(evento: true, n: _n));
    if (!await _esp(4000)) return false;
    _st('Ativação $_n: destaque do padrão (5 s)');
    if (!await _esp(2500)) return false;
    if (memNoDestaque) m.diagJs("__diag.mem('durante_destaque')");
    if (!await _esp(2500)) return false;
    _st('Ativação $_n: decisão (8 s)');
    if (!await _esp(8000)) return false;
    _st('Ativação $_n encerrada: mesa clássica (3 s)');
    m.desenhar(diagArgs(evento: false));
    return _esp(3000);
  }

  Future<void> _rodar() async {
    final inicio = DateTime.now().millisecondsSinceEpoch;
    final nome = widget.longo ? 'auto_10min' : 'auto_rapido';
    try {
      Diag.pontoMemoria('$nome:inicial_antes_da_mesa');
      _st('Abrindo a mesa…');
      if (!await _abrirMesa(nome)) return;
      _mesa!.diagJs("__diag.mem('mesa_pronta')");
      _st('Mesa clássica (8 s)');
      if (!await _esp(8000)) return;
      if (!widget.longo) {
        for (var i = 0; i < 3; i++) {
          if (!await _ciclo(nome, memNoDestaque: i == 0)) return;
        }
        _mesa!.diagJs("__diag.mem('apos_3_ativacoes')");
        await _esp(600);
        _st('Saindo e entrando de novo na mesa…');
        if (!await _abrirMesa('${nome}_reentrada')) return;
        _mesa!.diagJs("__diag.mem('apos_reentrada')");
        if (!await _esp(5000)) return;
        if (!await _ciclo('${nome}_reentrada')) return;
        _mesa!.diagJs("__diag.mem('fim_apos_reentrada')");
      } else {
        for (var r = 1; r <= 20; r++) {
          _st('Uso contínuo: rodada $r de 20');
          if (!await _esp(10000)) return;
          if (!await _ciclo(nome)) return;
          if (r % 2 == 0) _mesa!.diagJs("__diag.mem('minuto_${r ~/ 2}')");
        }
      }
      _mesa!.diagJs('__diag.enviar()');
      await _esp(800);
      _st('Concluído.');
      Diag.testes.add({'teste': nome, 'inicioEp': inicio, 'fimEp': DateTime.now().millisecondsSinceEpoch, 'etapas': _etapas});
      if (mounted) setState(() => _fim = true);
    } catch (e) {
      Diag.ultimoErro = 'bench: $e';
      if (mounted) setState(() => _status = 'Erro no teste: $e');
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFF081528),
      body: Stack(children: [
        Positioned.fill(child: SafeArea(child: _mesa?.widget() ?? const SizedBox.shrink())),
        Positioned(
          left: 6,
          top: 28,
          child: IgnorePointer(
            child: Text(_status, style: const TextStyle(fontSize: 10, color: Color(0x88FFFFFF))),
          ),
        ),
        Positioned(
          right: 6,
          top: 20,
          child: _fim
              ? FilledButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Voltar ao painel'))
              : TextButton(onPressed: () => Navigator.of(context).pop(), child: const Text('Cancelar', style: TextStyle(fontSize: 11, color: Color(0x88FFFFFF)))),
        ),
      ]),
    );
  }
}
