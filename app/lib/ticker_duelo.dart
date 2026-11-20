import 'dart:math';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import 'animacoes.dart';
import 'api.dart';
import 'ticker.dart';

/// Duelo Clássico do Ticker Battle contra o Sistema (3 rodadas), feito no app:
///   1. escolher a carta (as que sobraram na mão);
///   2. ver a carta do sistema (escolhida por regra fixa, valores escondidos) e escolher o indicador;
///   3. revelação: a carta do sistema vira, os valores sobem, a vencedora brilha e o Raio-X explica por quê;
///   4. no fim, a faixa de Vitória/Derrota/Empate e o resumo das rodadas com o Raio-X completo.
class DueloTela extends StatefulWidget {
  const DueloTela({super.key, required this.api, required this.inicio, required this.indicadores});
  final Api api;
  final Map<String, dynamic> inicio;
  final Map<String, dynamic> indicadores;

  @override
  State<DueloTela> createState() => _DueloTelaState();
}

class _DueloTelaState extends State<DueloTela> with TickerProviderStateMixin {
  late Map<String, dynamic> _e = widget.inicio;
  String? _carta;
  Map<String, dynamic>? _adv;
  String? _ind;
  bool _ocupado = false;
  Map<String, dynamic>? _revelada; // última rodada, enquanto a revelação está na tela
  bool _verResultado = false;
  late final AnimationController _rev = AnimationController(vsync: this, duration: const Duration(milliseconds: 2600));

  @override
  void dispose() {
    _rev.dispose();
    super.dispose();
  }

  String get _id => '${_e['id']}';
  Map get _placar => (_e['placar'] as Map?) ?? const {};
  Map _meta(String? i) => (widget.indicadores[i] as Map?) ?? const {};

  Future<void> _escolher(String tk) async {
    setState(() {
      _carta = tk;
      _adv = null;
      _ind = null;
    });
    try {
      final r = await widget.api.get('/ticker/duelo/$_id/adversaria?carta=${Uri.encodeQueryComponent(tk)}');
      if (mounted && _carta == tk) setState(() => _adv = r);
    } catch (e) {
      if (mounted) {
        setState(() => _carta = null);
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
      }
    }
  }

  Future<void> _disputar() async {
    if (_carta == null || _ind == null || _ocupado) return;
    setState(() => _ocupado = true);
    try {
      final r = await widget.api.post('/ticker/duelo/$_id/rodada', {'carta': _carta, 'ind': _ind});
      if (!mounted) return;
      HapticFeedback.mediumImpact();
      setState(() {
        _e = r;
        _revelada = ((r['rodadas'] as List).last as Map).cast<String, dynamic>();
        _carta = null;
        _adv = null;
        _ind = null;
      });
      _rev.forward(from: 0);
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  void _proxima() => setState(() {
        _revelada = null;
        if (_e['final'] != null) _verResultado = true;
      });

  Future<void> _deNovo() async {
    setState(() => _ocupado = true);
    try {
      final r = await widget.api.post('/ticker/duelo');
      if (mounted) {
        setState(() {
          _e = r;
          _verResultado = false;
          _revelada = null;
        });
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(e.toString())));
    } finally {
      if (mounted) setState(() => _ocupado = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final Widget corpo;
    if (_verResultado) {
      corpo = _resultado();
    } else if (_revelada != null) {
      corpo = _revelacao(_revelada!);
    } else if (_carta == null) {
      corpo = _escolhaCarta();
    } else {
      corpo = _disputa();
    }
    return Scaffold(
      backgroundColor: const Color(0xFF0B0828),
      body: Stack(fit: StackFit.expand, children: [
        const DecoratedBox(
          decoration: BoxDecoration(
            gradient: RadialGradient(center: Alignment(0, -0.3), radius: 1.2, colors: [Color(0xFF2A1690), Color(0xFF120A4E), Color(0xFF070420)]),
          ),
        ),
        SafeArea(
          child: Column(children: [
            if (!_verResultado) _topo(),
            Expanded(child: AnimatedSwitcher(duration: const Duration(milliseconds: 350), child: KeyedSubtree(key: ValueKey('${corpo.runtimeType}$_carta${_revelada?['n']}$_verResultado'), child: corpo))),
          ]),
        ),
      ]),
    );
  }

  Widget _topo() {
    final n = _revelada != null ? (_revelada!['n'] as num).toInt() : (_e['rodada'] as num).toInt();
    return Padding(
      padding: const EdgeInsets.fromLTRB(4, 4, 12, 4),
      child: Row(children: [
        IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.arrow_back_rounded, color: Colors.white)),
        Image.asset('assets/ticker/rodada_${n.clamp(1, 3)}.webp', height: 34),
        const SizedBox(width: 6),
        Text('Rodada $n de ${_e['total']}', style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
        const Spacer(),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(999), color: const Color(0xFF1B1462), border: Border.all(color: const Color(0xFF8B6CFF))),
          child: AnimatedBuilder(
            animation: _rev,
            builder: (ctx, _) {
              // durante a revelação, o placar só muda quando a vencedora aparece (sem estragar a surpresa)
              var j = (_placar['jogador'] as num?)?.toInt() ?? 0, s = (_placar['adversario'] as num?)?.toInt() ?? 0;
              final r = _revelada;
              if (r != null && _rev.value < 0.7) {
                if (r['venc'] == 'jogador') j--;
                if (r['venc'] == 'adversario') s--;
              }
              return Text('Você $j × $s Sistema', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white));
            },
          ),
        ),
      ]),
    );
  }

  // ---------------------------------------------------------------- 1. escolher a carta
  Widget _escolhaCarta() {
    final mao = ((_e['mao'] as List?) ?? const []).cast<Map>();
    final decisiva = (_e['rodada'] as num) >= (_e['total'] as num) && _placar['jogador'] == _placar['adversario'] && (_placar['jogador'] as num) > 0;
    return ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 20), children: [
      if (decisiva)
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: const Duration(milliseconds: 700),
          curve: Curves.elasticOut,
          builder: (ctx, v, f) => Transform.scale(scale: v, child: f),
          child: Image.asset('assets/ticker/faixa_decisiva.webp', height: 120),
        ),
      const Text('Escolha a carta que vai entrar nesta rodada', textAlign: TextAlign.center, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.white)),
      const SizedBox(height: 4),
      const Text('Cada carta joga uma vez. Toque para ver a carta do sistema.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12.5, color: lilas)),
      const SizedBox(height: 12),
      Wrap(alignment: WrapAlignment.center, spacing: 10, runSpacing: 12, children: [
        for (final (k, c) in mao.indexed)
          Entrada(
            ordem: k,
            child: Column(children: [
              Pressionavel(
                aoTocar: c['sem_adv'] == true ? null : () => _escolher('${c['tk']}'),
                child: CartaTk(tk: '${c['tk']}', largura: 104, travada: c['sem_adv'] == true),
              ),
              const SizedBox(height: 4),
              SizedBox(
                width: 104,
                child: Column(children: [
                  for (final i in ((c['ind'] as List?) ?? const []).cast<Map>().take(3))
                    Row(children: [
                      Expanded(child: Text('${_meta('${i['id']}')['curto'] ?? i['id']}', overflow: TextOverflow.ellipsis, style: const TextStyle(fontSize: 10, color: lilas))),
                      Text('${i['txt']}', style: const TextStyle(fontSize: 10.5, fontWeight: FontWeight.w800, color: Colors.white)),
                    ]),
                ]),
              ),
            ]),
          ),
      ]),
    ]);
  }

  // ---------------------------------------------------------------- 2. carta do sistema e indicador
  Widget _disputa() {
    final minha = ((_e['mao'] as List?) ?? const []).cast<Map>().firstWhere((c) => c['tk'] == _carta, orElse: () => const {});
    final adv = (_adv?['adversaria'] as Map?) ?? const {};
    final disp = ((_adv?['disputaveis'] as List?) ?? const []).cast<String>();
    final bloq = ((_adv?['bloqueados'] as Map?) ?? const {});
    final valores = {for (final i in ((minha['ind'] as List?) ?? const []).cast<Map>()) '${i['id']}': '${i['txt']}'};
    return ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 20), children: [
      Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
        Expanded(child: Column(children: [CartaTk(tk: '$_carta', largura: 130), const SizedBox(height: 4), const Text('Você', style: TextStyle(color: lilas))])),
        const _Vs(),
        Expanded(
          child: Column(children: [
            _adv == null
                ? const SizedBox(width: 130, height: 175, child: Center(child: CircularProgressIndicator()))
                : Stack(alignment: Alignment.center, children: [
                    CartaTk(tk: '${adv['tk']}', largura: 130),
                    Container(
                      width: 54,
                      height: 54,
                      alignment: Alignment.center,
                      decoration: BoxDecoration(shape: BoxShape.circle, color: const Color(0xDD1B1462), border: Border.all(color: const Color(0xFFF2B84B), width: 2)),
                      child: const Text('?', style: TextStyle(fontSize: 30, fontWeight: FontWeight.w900, color: Color(0xFFFFD66B))),
                    ),
                  ]),
            const SizedBox(height: 4),
            const Text('Sistema', style: TextStyle(color: lilas)),
          ]),
        ),
      ]),
      const SizedBox(height: 6),
      Center(
        child: TextButton.icon(
          onPressed: () => setState(() => _carta = null),
          icon: const Icon(Icons.swap_horiz_rounded),
          label: const Text('Trocar carta'),
        ),
      ),
      const Text('Os valores do sistema aparecem quando você disputar.', textAlign: TextAlign.center, style: TextStyle(fontSize: 12.5, color: lilas)),
      const SizedBox(height: 10),
      const Text('Escolha o indicador desta rodada', textAlign: TextAlign.center, style: TextStyle(fontSize: 16, fontWeight: FontWeight.w800, color: Colors.white)),
      const SizedBox(height: 8),
      if (_adv != null && disp.isEmpty) const Text('Estas cartas não têm indicador comparável. Troque a carta.', textAlign: TextAlign.center, style: TextStyle(color: Color(0xFFFF8FA3))),
      LayoutBuilder(builder: (ctx, c) {
        final w = (c.maxWidth - 8) / 2;
        return Wrap(spacing: 8, runSpacing: 8, children: [
          for (final i in disp)
            SizedBox(
              width: w,
              child: Pressionavel(
                aoTocar: () => setState(() => _ind = i),
                child: AnimatedContainer(
                  duration: const Duration(milliseconds: 200),
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 10),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(14),
                    gradient: _ind == i ? const LinearGradient(colors: [Color(0xFFF2B84B), Color(0xFFD98E1F)]) : null,
                    color: _ind == i ? null : const Color(0xFF1B1462),
                    border: Border.all(color: _ind == i ? const Color(0xFFFFE08A) : const Color(0xFF6A4FE6), width: 1.5),
                    boxShadow: _ind == i ? const [BoxShadow(color: Color(0x88F2B84B), blurRadius: 12)] : null,
                  ),
                  child: Row(children: [
                    Icon(iconesInd[_meta(i)['icone']] ?? Icons.analytics_rounded, size: 20, color: _ind == i ? const Color(0xFF2A1A00) : const Color(0xFFB59BFF)),
                    const SizedBox(width: 6),
                    Expanded(
                      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                        Text('${_meta(i)['nome'] ?? i}', maxLines: 1, overflow: TextOverflow.ellipsis,
                            style: TextStyle(fontWeight: FontWeight.w900, color: _ind == i ? const Color(0xFF2A1A00) : Colors.white)),
                        Text('Você: ${valores[i] ?? '—'}', style: TextStyle(fontSize: 11, color: _ind == i ? const Color(0xFF3B2600) : lilas)),
                      ]),
                    ),
                  ]),
                ),
              ),
            ),
        ]);
      }),
      for (final e in bloq.entries)
        Padding(
          padding: const EdgeInsets.only(top: 6),
          child: Text('🔒 ${_meta('${e.key}')['nome'] ?? e.key}: ${e.value}', style: const TextStyle(fontSize: 12, color: lilas)),
        ),
      if (_ind != null) ...[
        const SizedBox(height: 10),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0x331B1462), border: Border.all(color: const Color(0x668B6CFF))),
          child: Text('${_meta(_ind)['nome']}. ${_meta(_ind)['significa']} Regra: ${_meta(_ind)['regra']}',
              style: const TextStyle(fontSize: 13, height: 1.35, color: Color(0xFFEDE9FF))),
        ),
      ],
      const SizedBox(height: 14),
      SizedBox(
        height: 54,
        child: FilledButton.icon(
          style: FilledButton.styleFrom(
            backgroundColor: const Color(0xFF12A83C),
            disabledBackgroundColor: const Color(0x5512A83C),
            textStyle: const TextStyle(fontSize: 18, fontWeight: FontWeight.w900),
          ),
          onPressed: _ind == null || _ocupado ? null : _disputar,
          icon: _ocupado ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2.5, color: Colors.white)) : const Icon(Icons.bolt_rounded),
          label: Text(_ind == null ? 'Escolha um indicador' : 'DISPUTAR'),
        ),
      ),
    ]);
  }

  // ---------------------------------------------------------------- 3. revelação da rodada
  Widget _revelacao(Map r) {
    final venc = '${r['venc']}';
    final ga = venc == 'jogador', gb = venc == 'adversario';
    final cor = ga ? const Color(0xFF26D07C) : (gb ? const Color(0xFFFF4D6D) : const Color(0xFFF2B84B));
    final titulo = ga ? 'Você venceu a rodada!' : (gb ? 'O sistema venceu a rodada.' : 'Rodada empatada.');
    final rx = (r['raio_x'] as Map?) ?? const {};
    final ultima = _e['final'] != null;
    return AnimatedBuilder(
      animation: _rev,
      builder: (ctx, _) {
        final t = _rev.value;
        final vira = Curves.easeInOut.transform((t / 0.35).clamp(0.0, 1.0));
        final conta = Curves.easeOutCubic.transform(((t - 0.35) / 0.35).clamp(0.0, 1.0));
        final fim = Curves.elasticOut.transform(((t - 0.7) / 0.3).clamp(0.0, 1.0));
        final angulo = (1 - vira) * pi;
        Widget valor(num v, String txt, bool ganhou) => Text(
              conta < 1 ? _contar(v.toDouble(), txt, conta) : txt,
              style: TextStyle(
                fontSize: 24,
                fontWeight: FontWeight.w900,
                color: fim > 0 && ganhou ? cor : Colors.white,
                shadows: fim > 0 && ganhou ? [Shadow(color: cor, blurRadius: 14)] : null,
              ),
            );
        return ListView(padding: const EdgeInsets.fromLTRB(12, 4, 12, 20), children: [
          Text('${r['nome_ind']}', textAlign: TextAlign.center, style: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900, color: Color(0xFFFFD66B))),
          const SizedBox(height: 8),
          Row(children: [
            Expanded(
              child: Column(children: [
                Transform.scale(
                  scale: 1 + (ga ? 0.06 * fim : 0),
                  child: CartaTk(tk: '${(r['jog'] as Map)['tk']}', largura: 130, brilho: fim > 0.2 && ga ? cor : null, apagada: fim > 0.2 && gb),
                ),
                const SizedBox(height: 6),
                valor(r['va'] as num, '${r['txt_a']}', ga),
              ]),
            ),
            const _Vs(),
            Expanded(
              child: Column(children: [
                Transform(
                  alignment: Alignment.center,
                  transform: Matrix4.identity()
                    ..setEntry(3, 2, 0.0015)
                    ..rotateY(angulo),
                  child: angulo > pi / 2
                      ? Image.asset('assets/ticker/pilha.webp', width: 130, height: 175, fit: BoxFit.cover)
                      : Transform.scale(
                          scale: 1 + (gb ? 0.06 * fim : 0),
                          child: CartaTk(tk: '${(r['adv'] as Map)['tk']}', largura: 130, brilho: fim > 0.2 && gb ? cor : null, apagada: fim > 0.2 && ga),
                        ),
                ),
                const SizedBox(height: 6),
                valor(r['vb'] as num, '${r['txt_b']}', gb),
              ]),
            ),
          ]),
          const SizedBox(height: 10),
          _Barra(a: ((r['barra_a'] as num?) ?? 0.5).toDouble() * conta + 0.5 * (1 - conta), maior: r['melhor'] == 'maior'),
          const SizedBox(height: 12),
          Opacity(
            opacity: fim.clamp(0.0, 1.0),
            child: Transform.scale(
              scale: 0.6 + 0.4 * fim,
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 12, horizontal: 10),
                decoration: BoxDecoration(
                  borderRadius: BorderRadius.circular(16),
                  color: cor.withValues(alpha: 0.18),
                  border: Border.all(color: cor, width: 2),
                  boxShadow: [BoxShadow(color: cor.withValues(alpha: 0.4), blurRadius: 16)],
                ),
                child: Text(titulo, textAlign: TextAlign.center, style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: cor)),
              ),
            ),
          ),
          const SizedBox(height: 10),
          Opacity(
            opacity: ((t - 0.8) / 0.2).clamp(0.0, 1.0),
            child: Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0x331B1462), border: Border.all(color: const Color(0x668B6CFF))),
              child: Text('Raio-X rápido · ${rx['nome']}. ${rx['significa']} ${rx['porque']}', style: const TextStyle(fontSize: 13, height: 1.35, color: Color(0xFFEDE9FF))),
            ),
          ),
          const SizedBox(height: 14),
          SizedBox(
            height: 52,
            child: FilledButton.icon(
              style: FilledButton.styleFrom(backgroundColor: const Color(0xFF5B4BD6), textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900)),
              onPressed: t < 0.7 ? null : _proxima,
              icon: const Icon(Icons.arrow_forward_rounded),
              label: Text(ultima ? 'VER RESULTADO FINAL' : 'PRÓXIMA RODADA'),
            ),
          ),
        ]);
      },
    );
  }

  /// Número subindo até o valor final, no mesmo formato do texto (% ou x).
  String _contar(double v, String txt, double f) {
    final x = v * f;
    if (txt.endsWith('x')) return '${x.toStringAsFixed(1).replaceAll('.', ',')}x';
    return '${(x * 100).toStringAsFixed(1).replaceAll('.', ',')}%';
  }

  // ---------------------------------------------------------------- 4. resultado
  Widget _resultado() {
    final f = '${_e['final']}';
    final faixa = {'vitoria': 'faixa_vitoria', 'derrota': 'faixa_derrota', 'empate': 'faixa_empate'}[f] ?? 'faixa_empate';
    final rods = ((_e['rodadas'] as List?) ?? const []).cast<Map>();
    return ListView(padding: const EdgeInsets.fromLTRB(12, 8, 12, 24), children: [
      Row(children: [
        IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.close_rounded, color: Colors.white)),
      ]),
      Stack(alignment: Alignment.center, clipBehavior: Clip.none, children: [
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: 1),
          duration: const Duration(milliseconds: 900),
          curve: Curves.elasticOut,
          builder: (ctx, v, c) => Transform.scale(scale: v, child: c),
          child: Image.asset('assets/ticker/$faixa.webp', height: 170),
        ),
        if (f == 'vitoria')
          Positioned(right: 0, bottom: -10, child: Flutua(child: Image.asset('assets/home/mascote_principal.webp', height: 90))),
      ]),
      const SizedBox(height: 8),
      Text('Você ${_placar['jogador']} × ${_placar['adversario']} Sistema', textAlign: TextAlign.center,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white)),
      if ((_placar['empates'] as num? ?? 0) > 0)
        Text('${_placar['empates']} rodada(s) empatada(s)', textAlign: TextAlign.center, style: const TextStyle(color: lilas)),
      const SizedBox(height: 14),
      const Text('Resumo das rodadas e Raio-X', style: TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
      const SizedBox(height: 8),
      for (final (k, r) in rods.indexed) Entrada(ordem: k, child: _cartaoRodada(r, k == 0)),
      const SizedBox(height: 12),
      SizedBox(
        height: 54,
        child: FilledButton.icon(
          style: FilledButton.styleFrom(backgroundColor: const Color(0xFF12A83C), textStyle: const TextStyle(fontSize: 17, fontWeight: FontWeight.w900)),
          onPressed: _ocupado ? null : _deNovo,
          icon: const Icon(Icons.replay_rounded),
          label: const Text('Jogar de novo'),
        ),
      ),
      const SizedBox(height: 8),
      OutlinedButton.icon(
        style: OutlinedButton.styleFrom(foregroundColor: Colors.white, minimumSize: const Size.fromHeight(46), side: const BorderSide(color: Color(0xFF8B6CFF))),
        onPressed: () => Navigator.of(context).maybePop(),
        icon: const Icon(Icons.home_rounded),
        label: const Text('Voltar à central'),
      ),
      const SizedBox(height: 8),
      const Text('Educacional: dados reais, sem recomendação de investimento. Duelos contra o sistema não pagam XP nem moedas.',
          textAlign: TextAlign.center, style: TextStyle(fontSize: 11.5, color: lilas)),
    ]);
  }

  Widget _cartaoRodada(Map r, bool aberto) {
    final venc = '${r['venc']}';
    final cor = venc == 'jogador' ? const Color(0xFF26D07C) : (venc == 'adversario' ? const Color(0xFFFF4D6D) : const Color(0xFFF2B84B));
    final rx = (r['raio_x'] as Map?) ?? const {};
    return Container(
      margin: const EdgeInsets.only(bottom: 10),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xCC1B1462), border: Border.all(color: cor.withValues(alpha: 0.7))),
      child: Theme(
        data: Theme.of(context).copyWith(dividerColor: Colors.transparent),
        child: ExpansionTile(
          initiallyExpanded: aberto,
          iconColor: Colors.white,
          collapsedIconColor: Colors.white,
          title: Row(children: [
            CartaTk(tk: '${(r['jog'] as Map)['tk']}', largura: 40),
            const SizedBox(width: 6),
            Expanded(
              child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text('Rodada ${r['n']} · ${r['nome_ind']}', style: const TextStyle(fontSize: 13.5, fontWeight: FontWeight.w900, color: Colors.white)),
                Text('${(r['jog'] as Map)['tk']} ${r['txt_a']} × ${r['txt_b']} ${(r['adv'] as Map)['tk']}', style: const TextStyle(fontSize: 12, color: lilas)),
              ]),
            ),
            Text(venc == 'jogador' ? 'Venceu' : (venc == 'adversario' ? 'Perdeu' : 'Empate'), style: TextStyle(fontWeight: FontWeight.w900, color: cor)),
          ]),
          childrenPadding: const EdgeInsets.fromLTRB(14, 0, 14, 12),
          expandedCrossAxisAlignment: CrossAxisAlignment.start,
          children: [
            for (final (t, k) in const [
              ('O que significa', 'significa'),
              ('Por que importa', 'relevancia'),
              ('Regra', 'regra'),
              ('Resultado', 'porque'),
              ('Limitações', 'limites'),
              ('O que não dá para concluir', 'nao_conclui'),
            ])
              Padding(
                padding: const EdgeInsets.only(bottom: 6),
                child: Text.rich(TextSpan(children: [
                  TextSpan(text: '$t: ', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
                  TextSpan(text: '${rx[k] ?? ''}', style: const TextStyle(color: Color(0xFFEDE9FF))),
                ]), style: const TextStyle(fontSize: 12.5, height: 1.35)),
              ),
          ],
        ),
      ),
    );
  }
}

/// "VS" da arte, pulsando entre as duas cartas.
class _Vs extends StatelessWidget {
  const _Vs();

  @override
  Widget build(BuildContext context) => SizedBox(width: 62, child: Flutua(altura: 4, child: Image.asset('assets/ticker/vs.webp', width: 62)));
}

/// Barra de comparação (só visual: a proporção dos dois valores), com quem vence a regra embaixo.
class _Barra extends StatelessWidget {
  const _Barra({required this.a, required this.maior});
  final double a;
  final bool maior;

  @override
  Widget build(BuildContext context) {
    return Column(children: [
      ClipRRect(
        borderRadius: BorderRadius.circular(999),
        child: SizedBox(
          height: 12,
          child: Row(children: [
            Expanded(flex: max(1, (a * 1000).round()), child: Container(color: const Color(0xFF8B6CFF))),
            Expanded(flex: max(1, ((1 - a) * 1000).round()), child: Container(color: const Color(0xFFF2B84B))),
          ]),
        ),
      ),
      const SizedBox(height: 4),
      Text(maior ? 'Vence o maior valor' : 'Vence o menor valor', style: const TextStyle(fontSize: 12, color: lilas)),
    ]);
  }
}
