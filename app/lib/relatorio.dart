import 'package:flutter/material.dart';

import 'animacoes.dart';
import 'grafico/grafico.dart';
import 'grafico/modelo.dart';

/// Resultado da partida do Trade Battle, feito no próprio app:
///   · o ativo revelado (nome e período), que entra virando;
///   · os pontos subindo até o valor final, com o lucro, a nota da leitura e o XP;
///   · o gráfico REAL: a partida aparece andando depois da linha "início da partida" e os desenhos ganham ✔/✖ um a um;
///   · a lista "Seus desenhos" com a explicação de cada um.
/// O relatório completo (o mesmo do app antigo) continua a um toque.
class RelatorioTela extends StatefulWidget {
  const RelatorioTela({super.key, required this.fim, required this.tela, required this.aoCompleto, required this.acao, required this.rotuloAcao});
  final Map<String, dynamic> fim;
  final Map<String, dynamic> tela;
  final VoidCallback aoCompleto;
  final VoidCallback acao;
  final String rotuloAcao;

  @override
  State<RelatorioTela> createState() => _RelatorioTelaState();
}

class _RelatorioTelaState extends State<RelatorioTela> with SingleTickerProviderStateMixin {
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 3600))..forward();
  late final List<Vela> _velas = [for (final c in (widget.tela['candles'] as List? ?? const [])) if (c is Map) Vela.de(c)];
  late final int _divisor = (_velas.length - ((widget.tela['revelados'] as num?)?.toInt() ?? 0)).clamp(0, _velas.length);
  late final Map<String, dynamic> _res = (widget.fim['resultado'] as Map?)?.cast<String, dynamic>() ?? const {};
  late final Map<String, dynamic> _lt = (_res['leitura'] as Map?)?.cast<String, dynamic>() ?? const {};
  late final List<Map> _itens = ((_lt['itens'] as List?) ?? const []).cast<Map>();
  late final List<Desenho> _desenhos = [for (final x in _itens) if (_desenho(x) case final d?) d];
  late final List<bool?> _ok = [for (final x in _itens) if (_desenho(x) != null) x['ok'] as bool?];

  static const _papel = {'suporte': Ferramenta.suporte, 'resistencia': Ferramenta.resistencia, 'rompimento': Ferramenta.rompimento, 'alvo': Ferramenta.alvo};

  Desenho? _desenho(Map x) {
    double n(Object? v) => (v as num).toDouble();
    switch (x['tipo']) {
      case 'nivel':
        final f = _papel[x['papel']];
        return f == null ? null : Desenho.nivel(f, n(x['preco']));
      case 'tendencia':
        return Desenho.dois(Ferramenta.tendencia, (x['i1'] as num).toInt(), n(x['p1']), (x['i2'] as num).toInt(), n(x['p2']));
      case 'zona':
        return Desenho.dois(x['reacao'] == 'alta' ? Ferramenta.zonaAlta : Ferramenta.zonaBaixa, (x['i1'] as num).toInt(), n(x['p1']),
            (x['i2'] as num).toInt(), n(x['p2']));
    }
    return null;
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  String _moeda(num v) {
    final s = v.abs().toStringAsFixed(2).split('.');
    final b = StringBuffer();
    for (var i = 0; i < s[0].length; i++) {
      if (i > 0 && (s[0].length - i) % 3 == 0) b.write('.');
      b.write(s[0][i]);
    }
    return '${v < 0 ? '−' : '+'}T\$ $b,${s[1]}';
  }

  @override
  Widget build(BuildContext context) {
    final rev = (widget.fim['revelado'] as Map?) ?? const {};
    final pts = (_res['pontos'] as num?)?.toDouble() ?? 0;
    final fin = (_res['fin'] as Map?) ?? const {};
    final xp = ((widget.fim['xp'] as Map?)?['xp'] as num?)?.toInt();
    final nota = (_lt['nota'] as num?)?.toDouble();
    return Scaffold(
      backgroundColor: const Color(0xFF0B0828),
      body: Stack(
        fit: StackFit.expand,
        children: [
          Image.asset('assets/jogos/fundo_arena.webp', fit: BoxFit.cover),
          const ColoredBox(color: Color(0xB3060226)),
          SafeArea(
            child: ListView(
              padding: const EdgeInsets.fromLTRB(12, 6, 12, 20),
              children: [
                Row(children: [
                  const Expanded(child: Text('Resultado da partida', style: TextStyle(fontSize: 19, fontWeight: FontWeight.w900, color: Colors.white))),
                  IconButton(onPressed: () => Navigator.of(context).maybePop(), icon: const Icon(Icons.close_rounded, color: Colors.white), tooltip: 'Fechar'),
                ]),
                const SizedBox(height: 4),
                Entrada(ordem: 0, child: _revelado(rev)),
                const SizedBox(height: 10),
                Entrada(ordem: 1, child: _placar(pts, fin, nota, xp)),
                const SizedBox(height: 10),
                Entrada(ordem: 2, child: _grafico(rev)),
                const SizedBox(height: 12),
                Entrada(ordem: 3, child: _lista()),
                const SizedBox(height: 14),
                FilledButton.icon(
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xFF12A83C),
                    minimumSize: const Size.fromHeight(52),
                    textStyle: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900),
                  ),
                  onPressed: widget.acao,
                  icon: const Icon(Icons.replay_rounded),
                  label: Text(widget.rotuloAcao),
                ),
                const SizedBox(height: 8),
                OutlinedButton.icon(
                  style: OutlinedButton.styleFrom(foregroundColor: Colors.white, minimumSize: const Size.fromHeight(46), side: const BorderSide(color: Color(0xFF7A5CFF))),
                  onPressed: widget.aoCompleto,
                  icon: const Icon(Icons.bar_chart_rounded),
                  label: const Text('Relatório completo'),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _revelado(Map rev) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: const Duration(milliseconds: 900),
      curve: Curves.easeOutBack,
      builder: (ctx, v, f) => Transform(
        alignment: Alignment.center,
        transform: Matrix4.identity()
          ..setEntry(3, 2, 0.002)
          ..rotateX((1 - v) * 1.4),
        child: f,
      ),
      child: Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(20),
          border: Border.all(color: const Color(0xFFF2B84B), width: 2),
          gradient: const LinearGradient(colors: [Color(0xFF2A1E86), Color(0xFF140E4A)]),
          boxShadow: const [BoxShadow(color: Color(0x66F2B84B), blurRadius: 16)],
        ),
        child: Row(children: [
          const Icon(Icons.lock_open_rounded, color: Color(0xFFFFD66B), size: 30),
          const SizedBox(width: 10),
          Expanded(
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              const Text('O ativo era', style: TextStyle(fontSize: 12, color: Color(0xFFCFC8EE))),
              Text('${rev['ticker'] ?? '—'}', style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w900, color: Color(0xFFFFD66B))),
              Text('${rev['nome'] ?? ''} · ${rev['de'] ?? ''} a ${rev['ate'] ?? ''} · ${rev['tf_nome'] ?? ''}',
                  style: const TextStyle(fontSize: 12, color: Color(0xFFCFC8EE))),
            ]),
          ),
        ]),
      ),
    );
  }

  Widget _placar(double pts, Map fin, double? nota, int? xp) {
    final cor = pts > 0 ? const Color(0xFF26D07C) : (pts < 0 ? const Color(0xFFFF4D6D) : Colors.white);
    final pnl = (fin['pnl'] as num?)?.toDouble();
    final pct = (fin['pct_aposta'] as num?)?.toDouble();
    Widget chip(String t, String v, Color c) => Expanded(
          child: Container(
            padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
            decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0xFF1B1462), border: Border.all(color: c.withValues(alpha: 0.6))),
            child: Column(children: [
              Text(t, style: const TextStyle(fontSize: 11, color: Color(0xFFBDB5E6))),
              FittedBox(child: Text(v, style: TextStyle(fontSize: 15, fontWeight: FontWeight.w900, color: c))),
            ]),
          ),
        );
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(20), color: const Color(0xCC160B5E), border: Border.all(color: cor.withValues(alpha: 0.7), width: 2)),
      child: Column(children: [
        TweenAnimationBuilder<double>(
          tween: Tween(begin: 0, end: pts),
          duration: const Duration(milliseconds: 1600),
          curve: Curves.easeOutCubic,
          builder: (ctx, v, _) => Text('${v > 0 ? '+' : ''}${v.toStringAsFixed(1).replaceAll('.', ',')} pts',
              style: TextStyle(fontSize: 38, fontWeight: FontWeight.w900, color: cor, shadows: [Shadow(color: cor.withValues(alpha: 0.6), blurRadius: 16)])),
        ),
        const Text('70% operação · 30% leitura', style: TextStyle(fontSize: 11.5, color: Color(0xFFBDB5E6))),
        const SizedBox(height: 10),
        Row(children: [
          chip('Lucro', pnl == null ? '—' : '${_moeda(pnl)}${pct == null ? '' : ' (${pct >= 0 ? '+' : ''}${pct.toStringAsFixed(2).replaceAll('.', ',')}%)'}',
              (pnl ?? 0) >= 0 ? const Color(0xFF26D07C) : const Color(0xFFFF4D6D)),
          const SizedBox(width: 6),
          chip('Desenhos', nota == null ? '—' : '${nota.toStringAsFixed(0)}/100', const Color(0xFFB59BFF)),
          const SizedBox(width: 6),
          chip('XP', xp == null ? '—' : '+$xp', const Color(0xFFFFD66B)),
        ]),
      ]),
    );
  }

  Widget _grafico(Map rev) {
    return Container(
      height: 320,
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(18), border: Border.all(color: const Color(0xFF5B4BD6), width: 2)),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(16),
        child: ColoredBox(
          color: const Color(0x99060226),
          child: _velas.isEmpty
              ? const SizedBox()
              : AnimatedBuilder(
                  animation: _c,
                  builder: (ctx, _) => GraficoNativo(
                    velas: _velas,
                    desenhos: _desenhos,
                    ferramenta: null,
                    somenteLeitura: true,
                    divisor: _divisor,
                    revelacao: Curves.easeInOut.transform((_c.value / 0.6).clamp(0.0, 1.0)),
                    resultados: _ok,
                    selos: ((_c.value - 0.6) / 0.4).clamp(0.0, 1.0),
                    tfNome: '${rev['tf_nome'] ?? ''}',
                    pedirTexto: () async => null,
                    aoMudar: ({bool usouFerramenta = false}) {},
                  ),
                ),
        ),
      ),
    );
  }

  Widget _lista() {
    if (_itens.isEmpty) {
      return Container(
        padding: const EdgeInsets.all(14),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: const Color(0xCC1B1462), border: Border.all(color: const Color(0x667A5CFF))),
        child: const Text('Na próxima partida, desenhe sua leitura na estratégia (suporte, resistência, zona…): cada desenho que se confirmar soma na nota.',
            style: TextStyle(color: Color(0xFFCFC8EE), height: 1.35)),
      );
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Text('Seus desenhos · ${_lt['acertos'] ?? 0} de ${_lt['avaliados'] ?? 0} se confirmaram',
          style: const TextStyle(fontSize: 16, fontWeight: FontWeight.w900, color: Colors.white)),
      const SizedBox(height: 8),
      for (final (k, x) in _itens.indexed)
        Entrada(
          ordem: 4 + k,
          child: Container(
            margin: const EdgeInsets.only(bottom: 6),
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(14),
              color: const Color(0xCC1B1462),
              border: Border.all(color: _cor(x['ok']).withValues(alpha: 0.7)),
            ),
            child: Row(children: [
              Container(
                width: 28,
                height: 28,
                alignment: Alignment.center,
                decoration: BoxDecoration(shape: BoxShape.circle, color: _cor(x['ok'])),
                child: Text(x['ok'] == true ? '✔' : (x['ok'] == false ? '✖' : '•'),
                    style: const TextStyle(color: Colors.white, fontWeight: FontWeight.w900)),
              ),
              const SizedBox(width: 10),
              Expanded(child: Text('${x['texto'] ?? ''}', style: const TextStyle(fontSize: 13.5, color: Colors.white, height: 1.3))),
            ]),
          ),
        ),
    ]);
  }

  Color _cor(Object? ok) => ok == true ? const Color(0xFF26D07C) : (ok == false ? const Color(0xFFFF4D6D) : const Color(0xFF8A86A8));
}
