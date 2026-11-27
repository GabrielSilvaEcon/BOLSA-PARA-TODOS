import 'package:flutter/material.dart';

import 'package:flutter/services.dart';

import 'animacoes.dart';
import 'confete.dart';
import 'escudo.dart';
import 'relatorio.dart' show AnaliseDesenhos;

const _ouro = Color(0xFFFFC93C);
const _azulEmpate = Color(0xFF5CC8FF);
const _vermelho = Color(0xFFFF4D6D);
const _verde = Color(0xFF26D07C);
const _lilas = Color(0xFFC8D6EE);

/// Tudo o que a tela de resultado mostra, calculado dos dados REAIS da partida (nada digitado à mão):
/// o veredito vem dos pontos contra o adversário (ou dos troféus, que o servidor já calculou com a mesma regra).
class ResultadoPartida {
  ResultadoPartida({
    required this.estado, required this.pnl, required this.pct, required this.pontos, required this.placar, required this.operacoes, required this.vitorias,
    required this.derrotas, required this.empates, required this.compras, required this.vendas, required this.ticker, required this.nome, required this.periodo,
    required this.variacao, required this.precoFinal, required this.velas, required this.trofeus, required this.xp,
  });

  final String estado; // vitoria | empate | derrota
  final double? pnl, pct, pontos, variacao, precoFinal;
  final List<Map<String, dynamic>> placar, operacoes;
  final int vitorias, derrotas, empates, compras, vendas;
  final String ticker, nome, periodo;
  final List<Map<String, dynamic>> velas;
  final Map? trofeus;
  final int? xp;

  /// Só há tela de duelo quando existe adversário no placar (treino solo continua com o relatório de sempre).
  static bool temAdversario(Map<String, dynamic> fim) {
    final l = [for (final x in (fim['placar'] as List? ?? const [])) if (x is Map) x];
    return l.any((x) => x['voce'] == true) && l.any((x) => x['voce'] != true);
  }

  static String _estadoDe(List<Map<String, dynamic>> placar, Map? trofeus) {
    final r = trofeus?['resultado'];
    if (r == 'vitoria' || r == 'empate' || r == 'derrota') return '$r';
    double pt(Map x) => (x['pontos'] as num?)?.toDouble() ?? 0;
    final eu = placar.where((x) => x['voce'] == true).firstOrNull;
    final outros = placar.where((x) => x['voce'] != true).toList();
    if (eu == null || outros.isEmpty) return 'empate';
    final rival = outros.map(pt).reduce((a, b) => a > b ? a : b);
    if ((pt(eu) - rival).abs() < 0.05) return 'empate';
    return pt(eu) > rival ? 'vitoria' : 'derrota';
  }

  factory ResultadoPartida.de(Map<String, dynamic> fim, Map<String, dynamic> tela) {
    final res = (fim['resultado'] as Map?)?.cast<String, dynamic>() ?? const {};
    final fin = (res['fin'] as Map?) ?? const {};
    final placar = [for (final x in (fim['placar'] as List? ?? const [])) if (x is Map) x.cast<String, dynamic>()];
    final trofeus = fim['trofeus'] is Map ? fim['trofeus'] as Map : null;
    final meu = placar.where((x) => x['voce'] == true).firstOrNull;
    // operações: as do painel da mesa (já com quantidade e valor); se faltarem, as do resultado
    final doPainel = ((tela['mesa'] as Map?)?['operacoes'] as List?) ?? const [];
    final bruto = doPainel.isNotEmpty ? doPainel : ((res['operacoes'] as List?) ?? const []);
    final ops = <Map<String, dynamic>>[];
    for (final o in bruto) {
      if (o is! Map) continue;
      final val = (o['val'] ?? o['pnl']) as num?;
      ops.add({'direcao': '${o['direcao']}', 'q': o['q'], 'val': val?.toDouble() ?? 0.0});
    }
    final velas = [for (final c in (tela['candles'] as List? ?? const [])) if (c is Map) c.cast<String, dynamic>()];
    final rev = (fim['revelado'] as Map?) ?? const {};
    final reveladas = (tela['revelados'] as num?)?.toInt() ?? 0;
    final ini = (velas.length - reveladas).clamp(0, velas.length);
    double? variacao, preco;
    if (velas.isNotEmpty) {
      preco = (velas.last['c'] as num?)?.toDouble();
      final base = ini > 0 ? (velas[ini - 1]['c'] as num?)?.toDouble() : (velas.first['o'] as num?)?.toDouble();
      if (preco != null && base != null && base != 0) variacao = (preco / base - 1) * 100;
    }
    return ResultadoPartida(
      estado: _estadoDe(placar, trofeus),
      pnl: (fin['pnl'] as num?)?.toDouble(),
      pct: (fin['pct_aposta'] as num?)?.toDouble(),
      pontos: (meu?['pontos'] as num?)?.toDouble() ?? (res['pontos'] as num?)?.toDouble(),
      placar: placar,
      operacoes: ops,
      vitorias: ops.where((o) => (o['val'] as double) > 0).length,
      derrotas: ops.where((o) => (o['val'] as double) < 0).length,
      empates: ops.where((o) => (o['val'] as double) == 0).length,
      compras: ops.where((o) => o['direcao'] == 'alta').length,
      vendas: ops.where((o) => o['direcao'] == 'baixa').length,
      ticker: '${rev['ticker'] ?? '—'}',
      nome: '${rev['nome'] ?? ''}',
      periodo: [if ('${rev['de'] ?? ''}'.isNotEmpty) '${rev['de']} a ${rev['ate']}', if ('${rev['tf_nome'] ?? ''}'.isNotEmpty) '${rev['tf_nome']}'].join(' · '),
      variacao: variacao,
      precoFinal: preco,
      velas: velas.sublist(ini > 0 ? ini : 0),
      trofeus: trofeus,
      xp: ((fim['xp'] as Map?)?['xp'] as num?)?.toInt(),
    );
  }

  /// Frase de apoio: depende do que aconteceu DE VERDADE (a derrota pode vir com lucro, a vitória com prejuízo).
  String get subtitulo {
    final lucro = (pnl ?? 0) > 0, prejuizo = (pnl ?? 0) < 0;
    switch (estado) {
      case 'vitoria':
        return prejuizo ? 'Você venceu nos pontos, mesmo com prejuízo: boa leitura!' : 'Você mostrou que entende do mercado!';
      case 'empate':
        return 'Duelo equilibrado. Na próxima, você leva!';
      default:
        return lucro ? 'Você lucrou, mas o adversário fez mais pontos. A próxima é sua!' : 'O mercado é assim… nem todo dia é de lucro!';
    }
  }

  String get rodape => switch (estado) {
        'vitoria' => 'Excelente desempenho! Continue evoluindo e conquiste novas recompensas!',
        'empate' => 'O equilíbrio também é parte da estratégia! Analise suas operações e volte ainda mais forte!',
        _ => 'Tudo bem! Isso faz parte do jogo. Aprenda com suas decisões e volte mais forte!',
      };

  static String moeda(num v, {bool sinal = true}) {
    final s = v.abs().toStringAsFixed(2).split('.');
    final b = StringBuffer();
    for (var i = 0; i < s[0].length; i++) {
      if (i > 0 && (s[0].length - i) % 3 == 0) b.write('.');
      b.write(s[0][i]);
    }
    final sg = v < 0 ? '−' : (sinal ? '+' : '');
    return '${sg}T\$ $b,${s[1]}';
  }

  static String num1(num v, {bool sinal = true}) => '${v > 0 && sinal ? '+' : (v < 0 ? '−' : '')}${v.abs().toStringAsFixed(1).replaceAll('.', ',')}';
}

/// Tela de resultado de um duelo em três páginas que se deslizam: Resultado (VITÓRIA / EMPATE / DERROTA, lucro, pontos, troféus, placar, divisão),
/// Operações (ativo, rosca, gráfico e sequência) e Análise (o gráfico real com os desenhos ✔/✖). O botão Continuar fica sempre à vista.
class ResultadoPartidaTela extends StatefulWidget {
  const ResultadoPartidaTela({super.key, required this.r, required this.continuar, this.fim, this.tela});
  final ResultadoPartida r;
  final VoidCallback continuar;

  /// Dados da partida para a página de análise (gráfico com os desenhos). Sem eles, a tela fica com duas páginas.
  final Map<String, dynamic>? fim, tela;

  @override
  State<ResultadoPartidaTela> createState() => _ResultadoPartidaTelaState();
}

class _ResultadoPartidaTelaState extends State<ResultadoPartidaTela> with SingleTickerProviderStateMixin {
  final _pc = PageController();
  // Os números sobem até o valor final (lucro, pontos, troféus) e a barra da divisão anda de onde estava até onde chegou.
  late final AnimationController _c = AnimationController(vsync: this, duration: const Duration(milliseconds: 1700));
  int _pag = 0;
  bool _iniciou = false;
  bool _animar = true;
  ResultadoPartida get r => widget.r;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_iniciou) return;
    _iniciou = true;
    _animar = !MediaQuery.of(context).disableAnimations;          // quem desligou as animações no aparelho vê tudo pronto, sem confete
    if (!_animar) {
      _c.value = 1;
      return;
    }
    _c.forward();
    _vibrar();
  }

  /// O toque do resultado: vitória é forte e em dois tempos; empate e derrota são leves (a derrota não é castigo).
  Future<void> _vibrar() async {
    if (r.estado == 'vitoria') {
      HapticFeedback.heavyImpact();
      await Future<void>.delayed(const Duration(milliseconds: 260));
      HapticFeedback.mediumImpact();
    } else {
      HapticFeedback.lightImpact();
    }
  }

  /// 0 a 1, com saída suave, dentro da janela [a, b] da animação (cada número entra um pouco depois do anterior).
  double _fase(double a, double b) => Curves.easeOutCubic.transform(((_c.value - a) / (b - a)).clamp(0.0, 1.0));

  @override
  void dispose() {
    _pc.dispose();
    _c.dispose();
    super.dispose();
  }

  Color get _cor => switch (r.estado) { 'vitoria' => _ouro, 'empate' => _azulEmpate, _ => _vermelho };

  Widget _caixa({required Widget child, Color? borda, EdgeInsets padding = const EdgeInsets.all(12)}) => Container(
        padding: padding,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          color: const Color(0xCC0A1F47),
          border: Border.all(color: (borda ?? const Color(0xFF3F78D8)).withValues(alpha: 0.85), width: 1.6),
        ),
        child: child,
      );

  Widget _numero(IconData ic, String rot, String valor, Color c, {String? nota}) => Expanded(
        child: Container(
          padding: const EdgeInsets.symmetric(vertical: 10, horizontal: 6),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(16), color: c.withValues(alpha: 0.14), border: Border.all(color: c.withValues(alpha: 0.9), width: 1.6)),
          child: Column(children: [
            Icon(ic, color: c, size: 24),
            const SizedBox(height: 2),
            Text(rot, textAlign: TextAlign.center, style: const TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: Colors.white)),
            const SizedBox(height: 2),
            FittedBox(child: Text(valor, style: TextStyle(fontSize: 21, fontWeight: FontWeight.w900, color: c))),
            if (nota != null) FittedBox(child: Text(nota, style: const TextStyle(fontSize: 10.5, color: _lilas))),
          ]),
        ),
      );

  Widget _adversarios() {
    final lista = [...r.placar]..sort((a, b) => ((b['pontos'] as num?) ?? 0).compareTo((a['pontos'] as num?) ?? 0));
    return _caixa(
      borda: _cor,
      child: Column(children: [
        const Align(alignment: Alignment.centerLeft, child: Text('PLACAR DO DUELO', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w900, color: Colors.white))),
        const SizedBox(height: 6),
        for (final (i, x) in lista.indexed)
          Container(
            margin: const EdgeInsets.only(top: 4),
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 8),
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(12),
              color: x['voce'] == true ? _cor.withValues(alpha: 0.18) : Colors.white.withValues(alpha: 0.06),
              border: Border.all(color: x['voce'] == true ? _cor : Colors.transparent),
            ),
            child: Row(children: [
              SizedBox(width: 26, child: Text('${i + 1}º', style: const TextStyle(fontWeight: FontWeight.w900, color: _lilas))),
              Expanded(child: Text(x['voce'] == true ? 'Você' : '${x['rotulo'] ?? 'Adversário'}', maxLines: 1, overflow: TextOverflow.ellipsis, style: const TextStyle(fontWeight: FontWeight.w800, color: Colors.white))),
              if (x['ret_pct'] is num) Padding(padding: const EdgeInsets.only(right: 10), child: Text('${ResultadoPartida.num1(x['ret_pct'] as num)}%', style: TextStyle(fontSize: 12, color: (x['ret_pct'] as num) >= 0 ? _verde : _vermelho))),
              Text('${ResultadoPartida.num1((x['pontos'] as num?) ?? 0)} pts', style: const TextStyle(fontWeight: FontWeight.w900, color: Colors.white)),
            ]),
          ),
      ]),
    );
  }

  Widget _operacoes(BuildContext context) {
    final total = r.operacoes.length;
    Widget item(String rot, String v, Color c) => Padding(
          padding: const EdgeInsets.symmetric(vertical: 2),
          child: Row(children: [
            Container(width: 10, height: 10, decoration: BoxDecoration(shape: BoxShape.circle, color: c)),
            const SizedBox(width: 8),
            Expanded(child: Text(rot, style: const TextStyle(fontSize: 12, color: Colors.white))),
            Text(v, style: TextStyle(fontWeight: FontWeight.w900, color: c)),
          ]),
        );
    return _caixa(
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          const Icon(Icons.insights_rounded, color: Color(0xFF4FC3FF)),
          const SizedBox(width: 6),
          const Expanded(child: Text('OPERAÇÕES REALIZADAS', style: TextStyle(fontSize: 14.5, fontWeight: FontWeight.w900, color: Colors.white))),
        ]),
        const SizedBox(height: 8),
        Container(
          padding: const EdgeInsets.all(10),
          decoration: BoxDecoration(borderRadius: BorderRadius.circular(14), color: const Color(0x3322C55E), border: Border.all(color: _verde.withValues(alpha: 0.6))),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(r.ticker, style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Colors.white)),
            if (r.nome.isNotEmpty && r.nome.toUpperCase() != r.ticker.toUpperCase()) Text(r.nome, style: const TextStyle(fontSize: 12.5, color: _lilas)),
            if (r.periodo.isNotEmpty) Text(r.periodo, style: const TextStyle(fontSize: 11.5, color: _lilas)),
            const SizedBox(height: 6),
            Row(children: [
              Expanded(child: _mini('Variação no jogo', r.variacao == null ? '—' : '${ResultadoPartida.num1(r.variacao!)}%', (r.variacao ?? 0) >= 0 ? _verde : _vermelho)),
              const SizedBox(width: 8),
              Expanded(child: _mini('Preço final', r.precoFinal == null ? '—' : 'T\$ ${r.precoFinal!.toStringAsFixed(2).replaceAll('.', ',')}', Colors.white)),
            ]),
          ]),
        ),
        const SizedBox(height: 8),
        Row(crossAxisAlignment: CrossAxisAlignment.center, children: [
          SizedBox(
            width: 92,
            height: 92,
            child: CustomPaint(
              painter: _Rosca(r.vitorias, r.derrotas, r.empates),
              child: Center(child: Column(mainAxisSize: MainAxisSize.min, children: [
                Text('$total', style: const TextStyle(fontSize: 24, fontWeight: FontWeight.w900, color: Colors.white)),
                const Text('operações', style: TextStyle(fontSize: 9.5, color: _lilas)),
              ])),
            ),
          ),
          const SizedBox(width: 12),
          Expanded(child: Column(children: [item('Vitórias', '${r.vitorias}', _verde), item('Derrotas', '${r.derrotas}', _vermelho), item('Empates', '${r.empates}', const Color(0xFF8FA3D6))])),
        ]),
        const SizedBox(height: 8),
        Row(children: [
          Expanded(child: _mini('Compras', '${r.compras}', _verde, icone: Icons.arrow_upward_rounded)),
          const SizedBox(width: 8),
          Expanded(child: _mini('Vendas', '${r.vendas}', _vermelho, icone: Icons.arrow_downward_rounded)),
        ]),
        const Padding(
          padding: EdgeInsets.only(top: 8),
          child: Text('A vitória é decidida pelos pontos do duelo, não por quantas operações deram lucro.', style: TextStyle(fontSize: 11, fontStyle: FontStyle.italic, color: _lilas)),
        ),
        if (r.velas.length > 2) ...[
          const SizedBox(height: 10),
          const Text('A PARTIDA NO GRÁFICO', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: _lilas)),
          const SizedBox(height: 4),
          ClipRRect(borderRadius: BorderRadius.circular(12), child: SizedBox(height: 110, width: double.infinity, child: CustomPaint(painter: _Velas(r.velas)))),
        ],
        if (total > 0) ...[
          const SizedBox(height: 10),
          const Text('SEQUÊNCIA DAS OPERAÇÕES', style: TextStyle(fontSize: 11.5, fontWeight: FontWeight.w900, color: _lilas)),
          _Sequencia(ops: r.operacoes),
        ],
      ]),
    );
  }

  Widget _mini(String rot, String v, Color c, {IconData? icone}) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 7),
        decoration: BoxDecoration(borderRadius: BorderRadius.circular(12), color: Colors.white.withValues(alpha: 0.07)),
        child: Row(children: [
          if (icone != null) Padding(padding: const EdgeInsets.only(right: 6), child: Icon(icone, color: c, size: 18)),
          Expanded(child: Text(rot, style: const TextStyle(fontSize: 11.5, color: _lilas))),
          Text(v, style: TextStyle(fontSize: 14, fontWeight: FontWeight.w900, color: c)),
        ]),
      );

  Widget _divisao() {
    final t = r.trofeus!;
    final dv = (t['dv'] as Map?) ?? const {};
    final prox = dv['prox'] as Map?;
    final total = (t['t'] as num?)?.toInt() ?? 0;
    final pct = ((dv['pct'] as num?) ?? 0).toDouble().clamp(0.0, 1.0);
    final cor = Escudo.corDe(dv['cor']);
    return _caixa(
      borda: const Color(0xFFF2B84B),
      child: Row(children: [
        Escudo.de(dv, tamanho: 58),
        const SizedBox(width: 12),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            const Text('SUA DIVISÃO', style: TextStyle(fontSize: 11, fontWeight: FontWeight.w800, color: _lilas)),
            Text('${dv['nome'] ?? t['divisao'] ?? ''}', style: TextStyle(fontSize: 22, fontWeight: FontWeight.w900, color: Color.lerp(cor, Colors.white, 0.25))),
            if (t['subiu'] == true) const Text('Você subiu de divisão!', style: TextStyle(fontWeight: FontWeight.w900, color: _ouro)),
            if (t['caiu'] == true) const Text('Você caiu de divisão.', style: TextStyle(fontWeight: FontWeight.w800, color: Color(0xFFFF8FA3))),
          ]),
        ),
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(prox == null ? 'Divisão máxima' : 'Próxima: ${prox['nome']} (${prox['min']} troféus)', style: const TextStyle(fontSize: 11.5, color: Colors.white)),
            const SizedBox(height: 6),
            AnimatedBuilder(
              animation: _c,
              builder: (ctx, _) {
                final f = _fase(0.4, 1.0);
                final delta = (t['delta'] as num?)?.toInt() ?? 0;
                final minAtual = ((dv['min'] as num?) ?? 0).toDouble();
                final minProx = ((prox?['min'] as num?) ?? 1).toDouble();
                final antes = prox == null ? 1.0 : ((total - delta - minAtual) / (minProx - minAtual)).clamp(0.0, 1.0); // onde a barra estava antes da partida
                final agora = (antes + (pct - antes) * f).clamp(0.0, 1.0);
                final tro = (total - delta + delta * f).round();
                return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  ClipRRect(borderRadius: BorderRadius.circular(6), child: LinearProgressIndicator(value: agora, minHeight: 9, backgroundColor: Colors.white12, color: const Color(0xFFF2B84B))),
                  const SizedBox(height: 3),
                  Text(prox == null ? '$tro troféus' : '$tro / ${prox['min']}', style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w800, color: Colors.white)),
                ]);
              },
            ),
          ]),
        ),
      ]),
    );
  }

  Widget _pagina(List<Widget> filhos) => Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 560),
          child: ListView(padding: const EdgeInsets.fromLTRB(14, 0, 14, 12), children: filhos),
        ),
      );

  Widget _paginaResultado(BuildContext context) {
    final trofeus = r.trofeus;
    final delta = (trofeus?['delta'] as num?)?.toInt();
    final topo = switch (r.estado) { 'vitoria' => 'topo_vitoria', 'empate' => 'topo_empate', _ => 'topo_derrota' };
    var ordem = 0;
    return _pagina([
      Entrada(
        ordem: ordem++,
        child: Stack(children: [
          Image.asset('assets/resultado/$topo.webp', width: double.infinity, fit: BoxFit.fitWidth),
          const Positioned(left: 0, right: 0, bottom: 0, height: 36, child: DecoratedBox(decoration: BoxDecoration(gradient: LinearGradient(begin: Alignment.topCenter, end: Alignment.bottomCenter, colors: [Color(0x00060B26), Color(0xFF060B26)])))),
        ]),
      ),
      Text(r.subtitulo, textAlign: TextAlign.center, style: const TextStyle(fontSize: 15.5, fontStyle: FontStyle.italic, fontWeight: FontWeight.w600, color: Colors.white)),
      const SizedBox(height: 14),
      Entrada(
        ordem: ordem++,
        child: AnimatedBuilder(
          animation: _c,
          builder: (ctx, _) => IntrinsicHeight(
            child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
              _numero(Icons.emoji_events_rounded, 'LUCRO DA PARTIDA', r.pnl == null ? '—' : ResultadoPartida.moeda(r.pnl! * _fase(0.0, 0.6)), (r.pnl ?? 0) < 0 ? _vermelho : _verde,
                  nota: r.pct == null ? null : '${ResultadoPartida.num1(r.pct! * _fase(0.0, 0.6))}% do capital'),
              const SizedBox(width: 8),
              _numero(Icons.star_rounded, 'PONTUAÇÃO', r.pontos == null ? '—' : ResultadoPartida.num1(r.pontos! * _fase(0.15, 0.75)), const Color(0xFF4FC3FF)),
              const SizedBox(width: 8),
              if (delta != null)
                _numero(Icons.shield_rounded, 'TROFÉUS', () {
                  final v = (delta * _fase(0.3, 0.9)).round();
                  return '${v >= 0 ? '+' : ''}$v';
                }(), delta >= 0 ? const Color(0xFFF2B84B) : const Color(0xFFFF8FA3))
              else
                _numero(Icons.bolt_rounded, 'XP', r.xp == null ? '—' : '+${(r.xp! * _fase(0.3, 0.9)).round()}', const Color(0xFFF2B84B), nota: r.xp == 0 ? 'limite do dia' : null),
            ]),
          ),
        ),
      ),
      const SizedBox(height: 12),
      if (r.placar.length > 1) ...[Entrada(ordem: ordem++, child: _adversarios()), const SizedBox(height: 12)],
      if (trofeus != null) ...[Entrada(ordem: ordem++, child: _divisao()), const SizedBox(height: 12)],
      _caixa(
        borda: _cor,
        child: Row(children: [
          Icon(r.estado == 'derrota' ? Icons.trending_down_rounded : Icons.trending_up_rounded, color: _cor),
          const SizedBox(width: 10),
          Expanded(child: Text(r.rodape, style: const TextStyle(fontSize: 12.5, fontStyle: FontStyle.italic, color: Colors.white))),
        ]),
      ),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final temAnalise = widget.fim != null && widget.tela != null;
    final nomes = ['Resultado', 'Operações', if (temAnalise) 'Análise'];
    return PopScope(
      canPop: false,
      child: Scaffold(
        backgroundColor: const Color(0xFF060B26),
        body: Stack(children: [
          SafeArea(
          child: Column(children: [
            Expanded(
              child: PageView(
                controller: _pc,
                onPageChanged: (i) => setState(() => _pag = i),
                children: [
                  _paginaResultado(context),
                  _pagina([const SizedBox(height: 10), _operacoes(context)]),
                  if (temAnalise) _pagina([const SizedBox(height: 10), AnaliseDesenhos(fim: widget.fim!, tela: widget.tela!)]),
                ],
              ),
            ),
            Padding(
              padding: const EdgeInsets.fromLTRB(14, 4, 14, 10),
              child: Center(
                child: ConstrainedBox(
                  constraints: const BoxConstraints(maxWidth: 560),
                  child: Column(mainAxisSize: MainAxisSize.min, children: [
                    Row(children: [
                      for (final (i, n) in nomes.indexed)
                        Expanded(
                          child: GestureDetector(
                            behavior: HitTestBehavior.opaque,
                            onTap: () => _pc.animateToPage(i, duration: const Duration(milliseconds: 280), curve: Curves.easeOut),
                            child: Padding(
                              padding: const EdgeInsets.symmetric(vertical: 4, horizontal: 3),
                              child: Column(children: [
                                Text(n, style: TextStyle(fontSize: 12.5, fontWeight: _pag == i ? FontWeight.w900 : FontWeight.w600, color: _pag == i ? _cor : _lilas)),
                                const SizedBox(height: 4),
                                AnimatedContainer(duration: const Duration(milliseconds: 200), height: 4, decoration: BoxDecoration(borderRadius: BorderRadius.circular(2), color: _pag == i ? _cor : Colors.white24)),
                              ]),
                            ),
                          ),
                        ),
                    ]),
                    const SizedBox(height: 6),
                    SizedBox(
                      width: double.infinity,
                      height: 54,
                      child: FilledButton(
                        style: FilledButton.styleFrom(backgroundColor: const Color(0xFF2F7BFF), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(28))),
                        onPressed: widget.continuar,
                        child: const Text('CONTINUAR  »', style: TextStyle(fontSize: 20, fontWeight: FontWeight.w900, letterSpacing: 0.5)),
                      ),
                    ),
                  ]),
                ),
              ),
            ),
          ]),
        ),
          if (r.estado == 'vitoria' && _animar) const Positioned.fill(child: ConfeteLeve()),
        ]),
      ),
    );
  }
}

/// Lista das operações: as 5 primeiras e "Ver todas" para abrir o resto, sem sair da tela.
class _Sequencia extends StatefulWidget {
  const _Sequencia({required this.ops});
  final List<Map<String, dynamic>> ops;

  @override
  State<_Sequencia> createState() => _SequenciaState();
}

class _SequenciaState extends State<_Sequencia> {
  bool _todas = false;

  @override
  Widget build(BuildContext context) {
    final lista = _todas ? widget.ops : widget.ops.take(5).toList();
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Padding(
        padding: const EdgeInsets.only(top: 4),
        child: Row(children: const [
          SizedBox(width: 30),
          Expanded(child: Text('TIPO', style: TextStyle(fontSize: 10, color: _lilas))),
          SizedBox(width: 60, child: Text('QTD.', style: TextStyle(fontSize: 10, color: _lilas))),
          SizedBox(width: 96, child: Text('RESULTADO', textAlign: TextAlign.right, style: TextStyle(fontSize: 10, color: _lilas))),
        ]),
      ),
      for (final o in lista)
        Container(
          padding: const EdgeInsets.symmetric(vertical: 6),
          decoration: const BoxDecoration(border: Border(top: BorderSide(color: Color(0x22FFFFFF)))),
          child: Row(children: [
            Icon(o['direcao'] == 'alta' ? Icons.arrow_circle_up_rounded : Icons.arrow_circle_down_rounded, size: 22, color: o['direcao'] == 'alta' ? _verde : _vermelho),
            const SizedBox(width: 8),
            Expanded(child: Text(o['direcao'] == 'alta' ? 'Compra' : 'Venda', style: const TextStyle(fontSize: 13, color: Colors.white))),
            SizedBox(width: 60, child: Text('${o['q'] ?? '—'}', style: const TextStyle(fontSize: 13, color: Colors.white))),
            SizedBox(
              width: 96,
              child: Text(ResultadoPartida.moeda(o['val'] as double), textAlign: TextAlign.right, style: TextStyle(fontSize: 13, fontWeight: FontWeight.w800, color: (o['val'] as double) < 0 ? _vermelho : ((o['val'] as double) > 0 ? _verde : _lilas))),
            ),
          ]),
        ),
      if (widget.ops.length > 5)
        Align(
          alignment: Alignment.centerRight,
          child: TextButton(onPressed: () => setState(() => _todas = !_todas), child: Text(_todas ? 'Mostrar menos' : 'Ver todas as operações (${widget.ops.length})  →', style: const TextStyle(color: Color(0xFF9BBFFF), fontSize: 12.5))),
        ),
    ]);
  }
}

class _Rosca extends CustomPainter {
  _Rosca(this.v, this.d, this.e);
  final int v, d, e;

  @override
  void paint(Canvas c, Size s) {
    final total = v + d + e;
    final rect = Rect.fromLTWH(6, 6, s.width - 12, s.height - 12);
    final base = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 9
      ..color = Colors.white12;
    c.drawArc(rect, 0, 6.2832, false, base);
    if (total == 0) return;
    var ang = -1.5708;
    for (final (n, cor) in [(v, _verde), (d, _vermelho), (e, const Color(0xFF8FA3D6))]) {
      if (n == 0) continue;
      final varre = 6.2832 * n / total;
      c.drawArc(rect, ang, varre - (total > n ? 0.06 : 0), false, Paint()..style = PaintingStyle.stroke..strokeWidth = 9..strokeCap = StrokeCap.butt..color = cor);
      ang += varre;
    }
  }

  @override
  bool shouldRepaint(_Rosca o) => o.v != v || o.d != d || o.e != e;
}

/// Mini gráfico de velas da partida (só o trecho jogado), desenhado aqui mesmo: leve e sem depender do gráfico da mesa.
class _Velas extends CustomPainter {
  _Velas(this.velas);
  final List<Map<String, dynamic>> velas;

  @override
  void paint(Canvas c, Size s) {
    c.drawRect(Offset.zero & s, Paint()..color = const Color(0x66061633));
    final lista = velas.length > 90 ? velas.sublist(velas.length - 90) : velas;
    double hi = -1e18, lo = 1e18;
    for (final v in lista) {
      hi = hi > ((v['h'] as num?) ?? 0).toDouble() ? hi : ((v['h'] as num?) ?? 0).toDouble();
      lo = lo < ((v['l'] as num?) ?? 0).toDouble() ? lo : ((v['l'] as num?) ?? 0).toDouble();
    }
    if (hi <= lo) return;
    double y(double p) => 6 + (hi - p) / (hi - lo) * (s.height - 12);
    final w = s.width / lista.length;
    for (final (i, v) in lista.indexed) {
      final o = (v['o'] as num).toDouble(), cl = (v['c'] as num).toDouble(), h = (v['h'] as num).toDouble(), l = (v['l'] as num).toDouble();
      final cor = cl >= o ? _verde : _vermelho;
      final x = i * w + w / 2;
      c.drawLine(Offset(x, y(h)), Offset(x, y(l)), Paint()..color = cor..strokeWidth = 1);
      final top = y(o > cl ? o : cl), base = y(o > cl ? cl : o);
      c.drawRect(Rect.fromLTRB(x - w * 0.33, top, x + w * 0.33, base < top + 1 ? top + 1 : base), Paint()..color = cor);
    }
  }

  @override
  bool shouldRepaint(_Velas o) => o.velas != velas;
}
